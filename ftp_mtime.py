"""FTP modification-time retrieval and age-based source cleanup."""

import datetime
import ftplib
import logging

from config import Settings
from ftp_delete import delete_ftp_file, remove_empty_ftp_dirs
from ftp_ops import build_ftp_path

logger = logging.getLogger(__name__)


def _parse_mdtm_response(response: str) -> datetime.datetime | None:
    """Parse an MDTM response '213 YYYYMMDDHHmmss[.sss]' into a UTC datetime."""
    parts = response.split(None, 1)
    if len(parts) != 2 or parts[0] != "213":
        return None
    timestamp_str = parts[1].split(".")[0]
    try:
        return datetime.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").replace(tzinfo=datetime.UTC)
    except ValueError:
        return None


def get_ftp_file_mtimes(
    ftp: ftplib.FTP,
    settings: Settings,
    file_paths: list[str],
) -> dict[str, datetime.datetime]:
    """Get modification times for FTP files using the MDTM command.

    Returns a dict mapping relative paths to UTC datetimes.
    Files whose mtime cannot be determined are omitted.
    """
    mtimes: dict[str, datetime.datetime] = {}
    for path in file_paths:
        ftp_absolute_path = build_ftp_path(settings, path)
        try:
            response = ftp.sendcmd(f"MDTM {ftp_absolute_path}")
            mtime = _parse_mdtm_response(response)
            if mtime:
                mtimes[path] = mtime
            else:
                logger.warning("Unexpected MDTM response for %s: %s", path, response)
        except ftplib.error_perm:
            logger.warning("MDTM not supported or failed for %s", path)
        except ftplib.error_temp as exc:
            logger.warning("Temporary FTP error getting mtime for %s: %s", path, exc)
    if not mtimes and file_paths:
        logger.warning(
            "Could not retrieve modification times for any files. "
            "The FTP server may not support the MDTM command. "
            "Source cleanup will be skipped."
        )
    return mtimes


def delete_old_ftp_files(
    ftp: ftplib.FTP,
    settings: Settings,
    ftp_files: list[str],
    max_age_days: int,
) -> int:
    """Delete FTP files older than max_age_days.

    Returns the number of files successfully deleted.
    """
    mtimes = get_ftp_file_mtimes(ftp, settings, ftp_files)
    if not mtimes:
        return 0

    cutoff = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=max_age_days)
    old_files = [path for path, mtime in mtimes.items() if mtime < cutoff]

    if not old_files:
        logger.debug("No FTP files older than %d days.", max_age_days)
        return 0

    logger.info("Deleting %d FTP files older than %d days...", len(old_files), max_age_days)
    deleted: list[str] = []
    for rel_path in old_files:
        if delete_ftp_file(ftp, settings, rel_path):
            deleted.append(rel_path)

    if deleted:
        remove_empty_ftp_dirs(ftp, settings, deleted)

    return len(deleted)
