"""FTP Sync Tool - entry point."""

import ftplib
import logging
import os
import sys

from config import apply_overrides, load_settings, parse_arguments
from ftp_ops import download_file, ensure_ftp_dir, get_ftp_files_recursive, upload_file
from sync import get_local_files_recursive, handle_old_files, sync_files

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

    if not settings.local_directory:
        logger.error("LOCAL_DIRECTORY must be set in INI file or via --local-dir argument")
        sys.exit(1)
    if not settings.ftp_directory:
        logger.error("FTP_DIRECTORY must be set in INI file or via --ftp-dir argument")
        sys.exit(1)

    os.makedirs(settings.local_directory, exist_ok=True)

    ftp = ftplib.FTP(settings.ftp_host)
    ftp.login(settings.ftp_user, settings.ftp_pass)

    ensure_ftp_dir(ftp, settings.ftp_directory)
    ftp.cwd(settings.ftp_directory)

    logger.info("Getting file lists...")
    ftp_files = get_ftp_files_recursive(ftp)
    local_files = get_local_files_recursive(settings.local_directory)

    try:
        if settings.direction == "up":
            logger.info("Syncing local files to FTP...")
            sync_files(settings, upload_file, local_files, ftp_files)
        else:
            logger.info("Syncing FTP files to local...")
            completed_files = sync_files(settings, download_file, ftp_files, local_files)
            handle_old_files(settings, completed_files, local_files)
    finally:
        ftp.quit()


if __name__ == "__main__":
    main()
