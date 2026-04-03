"""FTP Sync Tool - entry point."""

import ftplib
import logging
import os
import sys

from config import Settings, apply_overrides, load_settings, parse_arguments
from ftp_ops import (
    delete_ftp_file,
    delete_ftp_files,
    download_file,
    ensure_ftp_dir,
    get_ftp_files_recursive,
    upload_file,
)
from hash_db import delete_paths, filter_changed_files, find_deleted_paths, open_hash_db, upsert_hashes
from sync import build_merged_file_map, get_local_files_recursive, handle_old_files, sync_files

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure root logger."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Run the FTP sync tool."""
    setup_logging()

    args = parse_arguments()
    settings = load_settings(args.settings_file)
    settings = apply_overrides(settings, args)

    if args.resync and settings.hash_cache_file and os.path.exists(settings.hash_cache_file):
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

    ftp = ftplib.FTP(settings.ftp_host)
    ftp.login(settings.ftp_user, settings.ftp_pass)

    ensure_ftp_dir(ftp, settings.ftp_directory)
    ftp.cwd(settings.ftp_directory)

    try:
        if settings.direction == "up":
            merged_files = build_merged_file_map(settings.local_directories, settings.ignore_dirs)
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
            ftp_files = get_ftp_files_recursive(ftp, ignore_dirs=settings.ignore_dirs)
            local_files = get_local_files_recursive(
                settings.local_directories[0], ignore_dirs=settings.ignore_dirs
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
