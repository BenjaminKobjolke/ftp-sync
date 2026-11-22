"""Read the local Git revision and record it on the FTP server."""

import ftplib
import io
import logging
import re
import subprocess

from config import Settings
from ftp_ops import build_ftp_path
from run_failures import run_failures

logger = logging.getLogger(__name__)

_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}\Z")


def local_git_commit(local_dir: str) -> str | None:
    """Return the local HEAD hash, or None when the directory is not a usable Git checkout."""
    try:
        result = subprocess.run(
            ["git", "-C", local_dir, "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.info("Skipping version file: git is not installed")
        return None

    commit = result.stdout.strip()
    if result.returncode != 0 or not _COMMIT_RE.fullmatch(commit):
        logger.info("Skipping version file: %s is not a Git checkout", local_dir)
        return None

    try:
        status = subprocess.run(
            ["git", "-C", local_dir, "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        logger.info("Skipping dirty-tree check: git is no longer available")
        return commit

    if status.stdout.strip():
        logger.warning("Git checkout has uncommitted changes; version file will use HEAD: %s", local_dir)
    return commit


def upload_version_file(ftp: ftplib.FTP, settings: Settings, commit: str) -> None:
    """Upload a commit hash as plain ASCII to the configured FTP version file."""
    ftp_path = build_ftp_path(settings, settings.version_file)
    try:
        ftp.storbinary(f"STOR {ftp_path}", io.BytesIO(commit.encode("ascii")))
    except ftplib.all_errors as exc:
        logger.error("Failed to write version file %s: %s", settings.version_file, exc)
        run_failures.record("transfer", settings.version_file)
        return

    logger.info("Wrote %s = %s", settings.version_file, commit)
