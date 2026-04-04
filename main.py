"""FTP Sync Tool - entry point."""

import ftplib
import logging
import os
import sys

from config import Settings, apply_overrides, load_settings, parse_arguments, settings_from_php_entry
from deployignore import (
    filter_ignored_paths,
    load_deployignore,
    load_deployignore_patterns,
    strip_subfolder_prefix,
)
from ftp_ops import (
    delete_ftp_file,
    delete_ftp_files,
    download_file,
    ensure_ftp_dir,
    get_ftp_files_recursive,
    remove_empty_ftp_dirs,
    upload_file,
)
from hash_db import delete_paths, filter_changed_files, find_deleted_paths, open_hash_db, upsert_hashes
from php_config import parse_php_config
from sync import build_merged_file_map, get_local_files_recursive, handle_old_files, sync_files

logger = logging.getLogger(__name__)

UNSUPPORTED_TRANSFER_TYPES = ("SFTP",)


def setup_logging() -> None:
    """Configure root logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _connect_ftp(settings: Settings) -> ftplib.FTP:
    """Create an FTP connection based on transfer type."""
    port = settings.ftp_port or 21
    ftp: ftplib.FTP

    if settings.transfer_type == "FTPS":
        ftp_tls = ftplib.FTP_TLS()
        ftp_tls.connect(settings.ftp_host, port)
        ftp_tls.login(settings.ftp_user, settings.ftp_pass)
        ftp_tls.prot_p()
        ftp = ftp_tls
    else:
        ftp = ftplib.FTP()
        ftp.connect(settings.ftp_host, port)
        ftp.login(settings.ftp_user, settings.ftp_pass)

    return ftp


def main() -> None:
    """Run the FTP sync tool."""
    setup_logging()
    args = parse_arguments()

    if args.settings_file.endswith(".php"):
        _run_php_config(args)
    else:
        _run_ini_config(args)


def _run_php_config(args: object) -> None:
    """Process a PHP deploy config file with all its entries."""
    local_dir = getattr(args, "local_dir", None)
    if not local_dir:
        logger.error("--local-dir is required when using a PHP config file")
        sys.exit(1)

    entries = parse_php_config(args.settings_file)  # type: ignore[attr-defined]
    if not entries:
        logger.error("No deployment entries found in %s", args.settings_file)  # type: ignore[attr-defined]
        sys.exit(1)

    from config import _parse_comma_list

    local_directories = _parse_comma_list(local_dir)

    for entry in entries:
        logger.info("=== Processing: %s ===", entry.name)

        if entry.transfer_type in UNSUPPORTED_TRANSFER_TYPES:
            logger.error("Transfer type '%s' is not supported, skipping entry", entry.transfer_type)
            continue

        entry_local_dirs = local_directories
        root_ignore_patterns: list[str] = []
        if entry.subfolder:
            entry_local_dirs = tuple(os.path.join(d, entry.subfolder) for d in local_directories)
            logger.info("Using subfolder: %s", entry.subfolder)
            root_patterns = load_deployignore_patterns(local_directories[0])
            root_ignore_patterns = strip_subfolder_prefix(root_patterns, entry.subfolder)

        extra_ignore = entry.ignore_patterns + tuple(root_ignore_patterns)
        hash_cache_file = os.path.join(local_directories[0], ".ftp_sync_cache.db")

        settings = settings_from_php_entry(
            ftp_host=entry.ftp_host,
            ftp_user=entry.ftp_user,
            ftp_pass=entry.ftp_pass,
            ftp_directory=entry.ftp_directory,
            local_directories=entry_local_dirs,
            transfer_type=entry.transfer_type,
            ftp_port=entry.ftp_port,
            hash_cache_file=hash_cache_file,
        )

        _run_sync(settings, extra_ignore, resync=getattr(args, "resync", False))


def _run_ini_config(args: object) -> None:
    """Process an INI config file."""
    settings = load_settings(args.settings_file)  # type: ignore[attr-defined]
    settings = apply_overrides(settings, args)  # type: ignore[arg-type]
    _run_sync(settings, (), resync=getattr(args, "resync", False))


def _run_sync(settings: Settings, extra_ignore_patterns: tuple[str, ...], resync: bool) -> None:
    """Execute sync for a single settings configuration."""
    if resync and settings.hash_cache_file and os.path.exists(settings.hash_cache_file):
        os.remove(settings.hash_cache_file)
        logger.info("Cleared hash cache: %s", settings.hash_cache_file)

    if not settings.local_directories:
        logger.error("LOCAL_DIRECTORY must be set in INI file or via --local-dir argument")
        sys.exit(1)
    if not settings.ftp_directory:
        logger.error("FTP_DIRECTORY must be set in INI file or via --ftp-dir argument")
        sys.exit(1)

    for local_dir in settings.local_directories:
        os.makedirs(local_dir, exist_ok=True)

    ftp = _connect_ftp(settings)
    ensure_ftp_dir(ftp, settings.ftp_directory)
    ftp.cwd(settings.ftp_directory)

    try:
        if settings.direction == "up":
            merged_files = build_merged_file_map(
                settings.local_directories, settings.ignore_dirs, extra_ignore_patterns
            )
            logger.info(
                "Merged %d files from %d local directories",
                len(merged_files),
                len(settings.local_directories),
            )

            if settings.hash_cache_file:
                _upload_with_hash_cache(settings, merged_files, ftp)
            else:
                _upload_with_ftp_scan(settings, merged_files, ftp)
        else:
            logger.info("Getting file lists...")
            deploy_spec = load_deployignore(settings.local_directories[0], extra_ignore_patterns)
            ftp_files = get_ftp_files_recursive(ftp, ignore_dirs=settings.ignore_dirs)
            ftp_files = filter_ignored_paths(ftp_files, deploy_spec)
            local_files = get_local_files_recursive(
                settings.local_directories[0],
                ignore_dirs=settings.ignore_dirs,
                deploy_spec=deploy_spec,
            )
            logger.info("Syncing FTP files to local...")
            download_args = [(f, settings, local_files) for f in ftp_files]
            completed_files = sync_files(settings, download_file, download_args)
            handle_old_files(settings, completed_files, local_files)
    finally:
        ftp.quit()


def _upload_with_hash_cache(
    settings: Settings, merged_files: dict[str, str], ftp: ftplib.FTP
) -> None:
    """Upload using local hash database for change detection (no FTP scan)."""
    session = open_hash_db(settings.hash_cache_file)

    changed_files, current_hashes = filter_changed_files(session, merged_files)
    logger.info(
        "Hash check: %d changed, %d unchanged",
        len(changed_files),
        len(merged_files) - len(changed_files),
    )

    if changed_files:
        logger.info("Syncing changed local files to FTP...")
        upload_args = [(rel, abs_path, settings, None) for rel, abs_path in changed_files.items()]
        completed = sync_files(settings, upload_file, upload_args)
        upsert_hashes(session, {rel: current_hashes[rel] for rel in completed})

    deleted = find_deleted_paths(session, set(merged_files.keys()))
    if deleted:
        logger.info("Deleting %d files from FTP that were removed locally...", len(deleted))
        for rel in deleted:
            delete_ftp_file(ftp, settings, rel)
        delete_paths(session, deleted)
        remove_empty_ftp_dirs(ftp, settings, deleted)

    session.close()


def _upload_with_ftp_scan(
    settings: Settings, merged_files: dict[str, str], ftp: ftplib.FTP
) -> None:
    """Upload using FTP scan and size-based skip (legacy mode)."""
    logger.info("Getting file lists...")
    ftp_files = get_ftp_files_recursive(ftp, ignore_dirs=settings.ignore_dirs)

    logger.info("Syncing local files to FTP...")
    upload_args = [(rel, abs_path, settings, ftp_files) for rel, abs_path in merged_files.items()]
    sync_files(settings, upload_file, upload_args)

    delete_ftp_files(settings, ftp_files, set(merged_files.keys()))


if __name__ == "__main__":
    main()
