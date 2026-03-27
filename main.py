"""FTP Sync Tool - entry point."""

import ftplib
import logging
import os
import sys

from config import apply_overrides, load_settings, parse_arguments
from ftp_ops import delete_ftp_files, download_file, ensure_ftp_dir, get_ftp_files_recursive, upload_file
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

    logger.info("Getting file lists...")
    ftp_files = get_ftp_files_recursive(ftp)

    try:
        if settings.direction == "up":
            merged_files = build_merged_file_map(settings.local_directories)
            logger.info(
                "Merged %d files from %d local directories",
                len(merged_files),
                len(settings.local_directories),
            )

            logger.info("Syncing local files to FTP...")
            upload_args = [(rel, abs_path, settings, ftp_files) for rel, abs_path in merged_files.items()]
            sync_files(settings, upload_file, upload_args)

            delete_ftp_files(settings, ftp_files, set(merged_files.keys()))
        else:
            local_files = get_local_files_recursive(settings.local_directories[0])
            logger.info("Syncing FTP files to local...")
            download_args = [(f, settings, local_files) for f in ftp_files]
            completed_files = sync_files(settings, download_file, download_args)
            handle_old_files(settings, completed_files, local_files)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main()
