"""FTP connection management and file operations."""

import contextlib
import ftplib
import logging
import os
import threading

from config import Settings

logger = logging.getLogger(__name__)

_thread_local = threading.local()


def get_ftp_connection(settings: Settings) -> ftplib.FTP:
    """Create or get a thread-local FTP connection."""
    ftp_conn: ftplib.FTP | None = getattr(_thread_local, "ftp", None)
    if ftp_conn is None:
        port = settings.ftp_port or 21
        if settings.transfer_type == "FTPS":
            ftp_conn = ftplib.FTP_TLS()
            ftp_conn.connect(settings.ftp_host, port)
            ftp_conn.login(settings.ftp_user, settings.ftp_pass)
            ftp_conn.prot_p()
        else:
            ftp_conn = ftplib.FTP()
            ftp_conn.connect(settings.ftp_host, port)
            ftp_conn.login(settings.ftp_user, settings.ftp_pass)
        if settings.ftp_directory:
            ftp_conn.cwd(settings.ftp_directory)
        _thread_local.ftp = ftp_conn
    return ftp_conn


def get_ftp_files_recursive(
    ftp: ftplib.FTP,
    path: str = ".",
    ignore_dirs: tuple[str, ...] = (),
) -> list[str]:
    """Recursively list files on the FTP server."""
    files: list[str] = []
    try:
        ftp.cwd(path)
        items = ftp.nlst()

        for item in items:
            if item in (".", ".."):
                continue

            try:
                ftp.cwd(item)
                ftp.cwd("..")
                if item in ignore_dirs:
                    logger.debug("Skipping ignored FTP directory: %s", item)
                    continue
                subpath = os.path.join(path, item).replace("\\", "/")
                files.extend(get_ftp_files_recursive(ftp, subpath, ignore_dirs))
            except ftplib.error_perm:
                file_path = os.path.join(path, item).replace("\\", "/")
                if path == ".":
                    files.append(item)
                else:
                    files.append(file_path)

        if path != ".":
            ftp.cwd("..")

    except ftplib.error_perm as e:
        logger.error("Error accessing path %s: %s", path, e)

    return files


def ensure_local_dir(path: str) -> None:
    """Create a local directory if it doesn't exist."""
    if not os.path.exists(path):
        os.makedirs(path)


def ensure_ftp_dir(ftp: ftplib.FTP, path: str) -> None:
    """Create an FTP directory and any missing parent directories."""
    try:
        ftp.cwd(path)
        ftp.cwd("/")
    except ftplib.error_perm:
        parts = path.split("/")
        current = ""
        for part in parts:
            if not part:
                continue
            current = f"{current}/{part}"
            try:
                ftp.cwd(current)
            except ftplib.error_perm:
                with contextlib.suppress(ftplib.error_perm):
                    ftp.mkd(current)


def build_ftp_path(settings: Settings, relative_path: str) -> str:
    """Build an absolute FTP path from a relative path."""
    ftp_base = settings.ftp_directory.rstrip("/")
    return f"{ftp_base}/{relative_path}"


def upload_file(args: tuple[str, str, Settings, list[str] | None]) -> str | None:
    """Upload a single file to the FTP server."""
    local_file, local_file_path, settings, ftp_files = args
    if local_file in (".", ".."):
        return None

    try:
        ftp = get_ftp_connection(settings)

        ftp_file_path = local_file.replace("\\", "/")
        ftp_absolute_path = build_ftp_path(settings, ftp_file_path)
        ftp_dir = os.path.dirname(ftp_absolute_path)

        if ftp_dir:
            ensure_ftp_dir(ftp, ftp_dir)

        total_size = os.path.getsize(local_file_path)

        if ftp_files is not None and local_file in ftp_files:
            try:
                ftp_size = ftp.size(ftp_absolute_path)
                if ftp_size == total_size:
                    logger.info("Skipping %s (already exists with same size)", local_file)
                    return local_file
            except (ftplib.error_perm, ftplib.error_temp):
                pass

        logger.info("Uploading %s", local_file)
        with open(local_file_path, "rb") as file:
            ftp.storbinary(f"STOR {ftp_absolute_path}", file, 1024)

        logger.info("Completed upload of %s", local_file)
        return local_file
    except Exception:
        logger.exception("Error uploading %s", local_file)
        return None


def download_file(args: tuple[str, Settings, list[str]]) -> str | None:
    """Download a single file from the FTP server."""
    ftp_file, settings, local_files = args
    if ftp_file.endswith(".") or ftp_file.endswith(".."):
        return None

    try:
        ftp = get_ftp_connection(settings)

        local_file_path = os.path.join(settings.local_directories[0], ftp_file)
        local_dir = os.path.dirname(local_file_path)
        ensure_local_dir(local_dir)

        try:
            total_size = ftp.size(ftp_file)
        except (ftplib.error_perm, ftplib.error_temp):
            logger.warning("Couldn't get size for %s, skipping", ftp_file)
            return None

        if os.path.exists(local_file_path):
            local_size = os.path.getsize(local_file_path)
            if local_size == total_size:
                logger.info("Skipping %s (already exists with same size)", ftp_file)
                return None

        logger.info("Downloading %s", ftp_file)
        with open(local_file_path, "wb") as file:
            ftp.retrbinary(f"RETR {ftp_file}", file.write, 1024)

        logger.info("Completed download of %s", ftp_file)
        return ftp_file
    except Exception:
        logger.exception("Error downloading %s", ftp_file)
        return None


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
