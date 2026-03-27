"""FTP connection management and file operations."""

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
        ftp_conn = ftplib.FTP(settings.ftp_host)
        ftp_conn.login(settings.ftp_user, settings.ftp_pass)
        if settings.ftp_directory:
            ftp_conn.cwd(settings.ftp_directory)
        _thread_local.ftp = ftp_conn
    return ftp_conn


def get_ftp_files_recursive(ftp: ftplib.FTP, path: str = ".") -> list[str]:
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
                subpath = os.path.join(path, item).replace("\\", "/")
                files.extend(get_ftp_files_recursive(ftp, subpath))
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
                ftp.mkd(current)


def upload_file(args: tuple[str, Settings, list[str]]) -> str | None:
    """Upload a single file to the FTP server."""
    local_file, settings, ftp_files = args
    if local_file in (".", ".."):
        return None

    try:
        ftp = get_ftp_connection(settings)

        local_file_path = os.path.join(settings.local_directory, local_file)
        ftp_file_path = local_file.replace("\\", "/")
        ftp_base = settings.ftp_directory.rstrip("/")
        ftp_absolute_path = f"{ftp_base}/{ftp_file_path}"
        ftp_dir = os.path.dirname(ftp_absolute_path)

        if ftp_dir:
            ensure_ftp_dir(ftp, ftp_dir)

        total_size = os.path.getsize(local_file_path)

        if local_file in ftp_files:
            try:
                ftp_size = ftp.size(ftp_absolute_path)
                if ftp_size == total_size:
                    logger.info("Skipping %s (already exists with same size)", local_file)
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

        local_file_path = os.path.join(settings.local_directory, ftp_file)
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
