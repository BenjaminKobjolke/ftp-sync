"""Read-only comparison of a remote FTP tree with a local directory."""

import contextlib
import ftplib
import logging
import os
from dataclasses import dataclass
from typing import TextIO

from config import Settings
from ftp_ops import connect_ftp

logger = logging.getLogger(__name__)

PROGRESS_EVERY_DIRS = 25
VIRUS_PREFIX = "VIRUS_"
MISSING = "MISSING"
SIZE = "SIZE"
LISTFAIL = "LISTFAIL"
VIRUS = "VIRUS"


@dataclass(frozen=True)
class CompareStats:
    dirs: int
    files: int
    problems: int


def _ascii_converted(local_path: str, remote_size: int) -> bool:
    # ponytail: the ceiling is reading one whole file into memory; chunk this if huge text files appear.
    with open(local_path, "rb") as local_file:
        data = local_file.read()
    return len(data) - data.count(b"\r\n") == remote_size


def _classify(remote_path: str, name: str, facts: dict[str, str], local_path: str) -> str | None:
    if name.startswith(VIRUS_PREFIX):
        return f"{VIRUS}\t{remote_path}\t{facts.get('size', '')}"

    if not os.path.isfile(local_path):
        return f"{MISSING}\t{remote_path}\t{facts.get('size', '')}"

    remote_size = facts.get("size")
    if remote_size is None:
        return None
    remote_bytes = int(remote_size)
    local_bytes = os.path.getsize(local_path)
    if local_bytes == remote_bytes:
        return None
    if local_bytes > remote_bytes and _ascii_converted(local_path, remote_bytes):
        return None
    return f"{SIZE}\t{remote_path}\tremote={remote_bytes} local={local_bytes}"


def compare_tree(
    ftp: ftplib.FTP,
    remote_root: str,
    local_root: str,
    out: TextIO,
    ignore_dirs: tuple[str, ...] = (),
) -> CompareStats:
    """Walk remote directories and write each local mismatch as it is found."""
    root = remote_root.rstrip("/") or "/"
    stack = [root]
    dirs = files = problems = 0

    while stack:
        directory = stack.pop()
        dirs += 1
        try:
            entries = list(ftp.mlsd(directory or "/", facts=["type", "size"]))
        except ftplib.all_errors as error:
            line = f"{LISTFAIL}\t{directory}\t{error}"
            out.write(line + "\n")
            logger.warning("%s", line)
            problems += 1
        else:
            for name, facts in entries:
                if name in (".", ".."):
                    continue
                remote_path = f"{directory.rstrip('/')}/{name}" if directory != "/" else f"/{name}"
                if facts.get("type") == "dir":
                    if name not in ignore_dirs:
                        stack.append(remote_path)
                    continue
                if facts.get("type") != "file":
                    continue
                files += 1
                relative = remote_path[len(root):].lstrip("/") if root != "/" else remote_path.lstrip("/")
                local_path = os.path.join(local_root, *relative.split("/"))
                line = _classify(remote_path, name, facts, local_path)
                if line is not None:
                    out.write(line + "\n")
                    logger.warning("%s", line)
                    problems += 1

        if dirs % PROGRESS_EVERY_DIRS == 0:
            logger.info("%d dirs done, %d queued, %d files, %d problems", dirs, len(stack), files, problems)

    stats = CompareStats(dirs, files, problems)
    final_line = f"DONE: {dirs} dirs, {files} remote files, {problems} problems"
    out.write(final_line + "\n")
    logger.info("%s", final_line)
    return stats


def run_compare(settings: Settings, output_file: str) -> None:
    """Validate paths and run a compare using the configured FTP connection."""
    if not settings.ftp_directory:
        logger.error("FTP_DIRECTORY must be set in INI file or via --ftp-dir argument")
        raise SystemExit(1)
    if not settings.local_directories or not os.path.isdir(settings.local_directories[0]):
        logger.error("LOCAL_DIRECTORY must be an existing directory for compare mode")
        raise SystemExit(1)
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.isdir(output_dir):
        logger.error("Compare output folder does not exist: %s", output_dir)
        raise SystemExit(1)

    ftp = connect_ftp(settings)
    try:
        with open(output_file, "w", encoding="utf-8", buffering=1) as out:
            compare_tree(ftp, settings.ftp_directory, settings.local_directories[0], out, settings.ignore_dirs)
    finally:
        with contextlib.suppress(Exception):
            ftp.quit()
