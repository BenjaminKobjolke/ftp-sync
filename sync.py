"""File sync orchestration and local file operations."""

import logging
import os
import shutil
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from config import Settings
from ftp_ops import ensure_local_dir

logger = logging.getLogger(__name__)

MergedFileMap = dict[str, str]


def get_local_files_recursive(local_dir: str, base_dir: str | None = None) -> list[str]:
    """Recursively list files in a local directory."""
    if base_dir is None:
        base_dir = local_dir

    files: list[str] = []
    for item in os.listdir(local_dir):
        full_path = os.path.join(local_dir, item)
        if os.path.isfile(full_path):
            rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
            files.append(rel_path)
        elif os.path.isdir(full_path) and item != "old":
            files.extend(get_local_files_recursive(full_path, base_dir))
    return files


def build_merged_file_map(local_directories: tuple[str, ...]) -> MergedFileMap:
    """Build a merged map of relative_path -> absolute_local_path from multiple directories.

    When a file exists at the same relative path in multiple directories,
    the file with the most recent modification time wins.
    """
    merged: MergedFileMap = {}
    mtimes: dict[str, float] = {}

    for local_dir in local_directories:
        for rel_path in get_local_files_recursive(local_dir):
            abs_path = os.path.join(local_dir, rel_path)
            mtime = os.path.getmtime(abs_path)

            if rel_path not in merged or mtime > mtimes[rel_path]:
                merged[rel_path] = abs_path
                mtimes[rel_path] = mtime

    return merged


def sync_files(
    settings: Settings,
    operation_func: Callable[[Any], str | None],
    args_list: Sequence[tuple[Any, ...]],
) -> list[str]:
    """Execute file operations concurrently with a pre-built args list."""
    max_workers = settings.concurrent_operations
    completed_files: list[str] = []

    logger.info("Starting sync with %d concurrent operations...", max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(operation_func, args): args[0] for args in args_list}

        for future in as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result:
                    completed_files.append(result)
            except Exception:
                logger.exception("Operation failed for %s", file)

    return completed_files


def handle_old_files(settings: Settings, completed_files: list[str], local_files: list[str]) -> None:
    """Move local files not present on the FTP server to an 'old' subdirectory."""
    local_dir = settings.local_directories[0]
    old_subfolder = os.path.join(local_dir, "old")
    os.makedirs(old_subfolder, exist_ok=True)

    for local_file in local_files:
        if local_file not in completed_files:
            local_path = os.path.join(local_dir, local_file)
            old_path = os.path.join(old_subfolder, local_file)
            ensure_local_dir(os.path.dirname(old_path))
            if os.path.exists(local_path):
                shutil.move(local_path, old_path)
