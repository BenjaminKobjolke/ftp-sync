"""FTP file and directory deletion."""

import contextlib
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


def _clear_ftp_dir(ftp: ftplib.FTP, settings: Settings, relative_dir: str, keep_dir: bool) -> int:
    """Recursively delete all files under a remote dir; remove emptied subdirs unless keep_dir."""
    abs_dir = build_ftp_path(settings, relative_dir)
    try:
        names = ftp.nlst(abs_dir)
    except ftplib.error_perm:
        logger.debug("Remote directory not found or empty, skipping: %s", relative_dir)
        return 0

    deleted = 0
    for name in names:
        # nlst may return absolute paths or bare names depending on the server
        base = name.replace("\\", "/").rsplit("/", 1)[-1]
        if base in (".", ".."):
            continue
        rel_item = f"{relative_dir}/{base}"
        try:
            ftp.cwd(build_ftp_path(settings, rel_item))
            deleted += _clear_ftp_dir(ftp, settings, rel_item, keep_dir=False)
        except ftplib.error_perm:
            if delete_ftp_file(ftp, settings, rel_item):
                deleted += 1

    if not keep_dir:
        with contextlib.suppress(ftplib.error_perm):
            ftp.rmd(abs_dir)
            logger.info("Removed empty FTP directory: %s", relative_dir)
    return deleted


def clear_remote_dirs(ftp: ftplib.FTP, settings: Settings, dirs: tuple[str, ...]) -> int:
    """Delete all files and empty subdirs under each remote dir; preserve the listed dirs."""
    total = 0
    for d in dirs:
        count = _clear_ftp_dir(ftp, settings, d.strip("/"), keep_dir=True)
        logger.info("Cleared %d files from remote dir: %s", count, d)
        total += count
    # cwd was used for directory detection; restore the sync base directory
    ftp.cwd(settings.ftp_directory)
    return total


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
