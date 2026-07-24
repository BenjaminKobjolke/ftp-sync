"""FTP file and directory deletion."""

import ftplib
import logging

from config import Settings
from ftp_ops import build_ftp_path, get_ftp_connection

logger = logging.getLogger(__name__)


def delete_ftp_file(ftp: ftplib.FTP, settings: Settings, relative_path: str) -> bool:
    """Delete a single file from the FTP server."""
    ftp_absolute_path = build_ftp_path(settings, relative_path)
    try:
        ftp.delete(ftp_absolute_path)
        logger.info("Deleted FTP file: %s", relative_path)
        return True
    except ftplib.error_perm:
        logger.warning("Could not delete FTP file: %s", relative_path)
        return False


def remove_empty_ftp_dirs(ftp: ftplib.FTP, settings: Settings, deleted_paths: list[str]) -> None:
    """Try to remove FTP directories that were emptied by file deletions.

    Collects parent directories of deleted files and attempts removal
    deepest-first. Silently skips non-empty or non-existent directories.
    """
    dirs: set[str] = set()
    for path in deleted_paths:
        parts = path.replace("\\", "/").split("/")
        for i in range(1, len(parts)):
            dirs.add("/".join(parts[:i]))

    for d in sorted(dirs, key=lambda x: x.count("/"), reverse=True):
        ftp_abs = build_ftp_path(settings, d)
        try:
            ftp.rmd(ftp_abs)
            logger.info("Removed empty FTP directory: %s", d)
        except ftplib.error_perm:
            pass


def delete_ftp_files(settings: Settings, ftp_files: list[str], local_files: set[str]) -> int:
    """Delete FTP files that are not present in any local directory."""
    to_delete = [f for f in ftp_files if f not in local_files]
    if not to_delete:
        logger.info("No FTP files to delete.")
        return 0

    logger.info("Deleting %d files from FTP that are no longer in any local directory...", len(to_delete))
    deleted_count = 0

    ftp = get_ftp_connection(settings)
    for rel_path in to_delete:
        if delete_ftp_file(ftp, settings, rel_path):
            deleted_count += 1

    logger.info("Deleted %d files from FTP.", deleted_count)
    return deleted_count
