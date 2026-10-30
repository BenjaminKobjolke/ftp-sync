"""Read-only comparison of a remote FTP tree with a local directory."""

import contextlib
import ftplib
import logging
import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TextIO

from config import Settings
from ftp_ops import connect_ftp
from hash_db import RemoteFact

logger = logging.getLogger(__name__)

PROGRESS_EVERY_DIRS = 25
VIRUS_PREFIX = "VIRUS_"
MISSING = "MISSING"
SIZE = "SIZE"
LISTFAIL = "LISTFAIL"
VIRUS = "VIRUS"
MLSD_FACTS = ["type", "size", "modify"]


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


def sizes_match(local_path: str, remote_size: int) -> bool:
    """True when the remote size equals the local file, also as an ASCII-mode (CRLF to LF) copy."""
    local_bytes = os.path.getsize(local_path)
    if local_bytes == remote_size:
        return True
    return local_bytes > remote_size and _ascii_converted(local_path, remote_size)


def _classify(remote_path: str, name: str, facts: dict[str, str], local_path: str) -> str | None:
    if name.startswith(VIRUS_PREFIX):
        return f"{VIRUS}\t{remote_path}\t{facts.get('size', '')}"

    if not os.path.isfile(local_path):
        return f"{MISSING}\t{remote_path}\t{facts.get('size', '')}"

    remote_size = facts.get("size")
    if remote_size is None:
        return None
    remote_bytes = int(remote_size)
    if sizes_match(local_path, remote_bytes):
        return None
    return f"{SIZE}\t{remote_path}\tremote={remote_bytes} local={os.path.getsize(local_path)}"


@dataclass(frozen=True)
class _Listing:
    directory: str
    files: list[tuple[str, dict[str, str]]]
    error: Exception | None
    queued: int


def _join(directory: str, name: str) -> str:
    return f"{directory.rstrip('/')}/{name}" if directory != "/" else f"/{name}"


def _relative(root: str, remote_path: str) -> str:
    return remote_path[len(root) :].lstrip("/") if root != "/" else remote_path.lstrip("/")


def _walk(
    ftp: ftplib.FTP, start_dirs: list[str], ignore_dirs: tuple[str, ...], recursive: bool = True
) -> Iterator[_Listing]:
    """List each directory once with MLSD, depth-first; a failed listing is yielded with its error."""
    stack = list(start_dirs)
    while stack:
        directory = stack.pop()
        try:
            entries = list(ftp.mlsd(directory or "/", facts=MLSD_FACTS))
        except ftplib.all_errors as error:
            yield _Listing(directory, [], error, len(stack))
            continue
        files: list[tuple[str, dict[str, str]]] = []
        for name, facts in entries:
            if name in (".", ".."):
                continue
            if facts.get("type") == "dir":
                if recursive and name not in ignore_dirs:
                    stack.append(_join(directory, name))
            elif facts.get("type") == "file":
                files.append((name, facts))
        yield _Listing(directory, files, None, len(stack))


def _normalize_root(remote_root: str) -> str:
    return remote_root.rstrip("/") or "/"


def compare_tree(
    ftp: ftplib.FTP,
    remote_root: str,
    local_root: str,
    out: TextIO,
    ignore_dirs: tuple[str, ...] = (),
) -> CompareStats:
    """Walk remote directories and write each local mismatch as it is found."""
    root = _normalize_root(remote_root)
    dirs = files = problems = 0

    for listing in _walk(ftp, [root], ignore_dirs):
        dirs += 1
        if listing.error is not None:
            fail_line = f"{LISTFAIL}\t{listing.directory}\t{listing.error}"
            out.write(fail_line + "\n")
            logger.warning("%s", fail_line)
            problems += 1
        for name, facts in listing.files:
            files += 1
            remote_path = _join(listing.directory, name)
            local_path = os.path.join(local_root, *_relative(root, remote_path).split("/"))
            line = _classify(remote_path, name, facts, local_path)
            if line is not None:
                out.write(line + "\n")
                logger.warning("%s", line)
                problems += 1

        if dirs % PROGRESS_EVERY_DIRS == 0:
            logger.info("%d dirs done, %d queued, %d files, %d problems", dirs, listing.queued, files, problems)

    stats = CompareStats(dirs, files, problems)
    final_line = f"DONE: {dirs} dirs, {files} remote files, {problems} problems"
    out.write(final_line + "\n")
    logger.info("%s", final_line)
    return stats


def list_remote_facts(
    ftp: ftplib.FTP,
    remote_root: str,
    ignore_dirs: tuple[str, ...] = (),
    subdirs: set[str] | None = None,
) -> dict[str, RemoteFact]:
    """Map each remote file's path relative to remote_root to its size and modify fact.

    With subdirs (relative, "" for the root itself) only those directories are listed,
    not recursively. Files in a directory that cannot be listed are left out.
    """
    root = _normalize_root(remote_root)
    if subdirs is None:
        listings = _walk(ftp, [root], ignore_dirs)
    else:
        listings = _walk(ftp, [_join(root, d) if d else root for d in sorted(subdirs)], ignore_dirs, recursive=False)

    facts: dict[str, RemoteFact] = {}
    for listing in listings:
        if listing.error is not None:
            logger.warning("Could not list %s: %s", listing.directory, listing.error)
        for name, file_facts in listing.files:
            relative = _relative(root, _join(listing.directory, name))
            facts[relative] = RemoteFact(int(file_facts.get("size", -1)), file_facts.get("modify", ""))
    return facts


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
