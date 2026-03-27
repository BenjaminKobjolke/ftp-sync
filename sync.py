"""File sync orchestration and local file operations."""

import logging
import os
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import Settings
from ftp_ops import ensure_local_dir

logger = logging.getLogger(__name__)

FileOpArgs = tuple[str, Settings, list[str]]


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


def sync_files(
    settings: Settings,
    operation_func: Callable[[FileOpArgs], str | None],
    file_list: list[str],
    reference_list: list[str],
) -> list[str]:
    """Sync files using concurrent operations."""
    max_workers = settings.concurrent_operations
    completed_files: list[str] = []

    logger.info("Starting sync with %d concurrent operations...", max_workers)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        args_list: list[FileOpArgs] = [(f, settings, reference_list) for f in file_list]

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
    old_subfolder = os.path.join(settings.local_directory, "old")
    os.makedirs(old_subfolder, exist_ok=True)

    for local_file in local_files:
        if local_file not in completed_files:
            local_path = os.path.join(settings.local_directory, local_file)
            old_path = os.path.join(old_subfolder, local_file)
            ensure_local_dir(os.path.dirname(old_path))
            if os.path.exists(local_path):
                shutil.move(local_path, old_path)
