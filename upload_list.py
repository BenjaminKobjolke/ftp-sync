"""Build read-only JSON listings of files an upload would send."""

import json
import logging
import os
import sys
from dataclasses import dataclass

from config import (
    DIRECTION_UP,
    Settings,
    _parse_comma_list,
    apply_overrides,
    entry_hash_cache_file,
    load_settings,
    settings_from_php_entry,
)
from deployignore import load_deployignore_patterns, load_ignore_file, strip_subfolder_prefix
from php_config import parse_php_config
from sync import build_merged_file_map

logger = logging.getLogger(__name__)

UNSUPPORTED_TRANSFER_TYPES = ("SFTP",)


@dataclass(frozen=True)
class UploadConfig:
    """Settings and ignore patterns for one upload configuration."""

    settings: Settings
    extra_ignore_patterns: tuple[str, ...]


def php_upload_configs(args: object) -> list[UploadConfig]:
    """Build per-entry upload settings from a PHP deploy config."""
    local_dir = getattr(args, "local_dir", None)
    if not local_dir:
        logger.error("--local-dir is required when using a PHP config file")
        sys.exit(1)

    entries = parse_php_config(args.settings_file)  # type: ignore[attr-defined]
    if not entries:
        logger.error("No deployment entries found in %s", args.settings_file)  # type: ignore[attr-defined]
        sys.exit(1)

    local_directories = _parse_comma_list(local_dir)
    extra_ignore_patterns = load_ignore_file(getattr(args, "ignore_file", None))
    upload_configs: list[UploadConfig] = []

    for entry in entries:
        logger.info("=== Processing: %s ===", entry.name)

        if entry.transfer_type in UNSUPPORTED_TRANSFER_TYPES:
            logger.error("Transfer type '%s' is not supported, skipping entry", entry.transfer_type)
            continue

        entry_local_dirs = local_directories
        root_ignore_patterns: list[str] = []
        if entry.subfolder:
            entry_local_dirs = tuple(os.path.join(d, entry.subfolder) for d in local_directories)
            logger.info("Using subfolder: %s", entry.subfolder)
            root_patterns = load_deployignore_patterns(local_directories[0])
            root_ignore_patterns = strip_subfolder_prefix(root_patterns, entry.subfolder)

        extra_ignore = entry.ignore_patterns + tuple(root_ignore_patterns) + extra_ignore_patterns
        hash_cache_file = entry_hash_cache_file(
            getattr(args, "hash_cache_file", None) or os.path.join(local_directories[0], ".ftp_sync_cache.db"),
            entry,
            len(entries),
        )
        settings = settings_from_php_entry(
            entry,
            entry_local_dirs,
            hash_cache_file,
            verify_remote=getattr(args, "verify_remote", False),
        )
        upload_configs.append(UploadConfig(settings, extra_ignore))

    return upload_configs


def write_upload_list(configs: list[UploadConfig], output_file: str) -> None:
    """Write the final merged upload map without touching sync state or FTP."""
    roots: list[str] = []
    seen_roots: set[str] = set()
    files: dict[str, str] = {}

    for upload_config in configs:
        settings = upload_config.settings
        if settings.direction != DIRECTION_UP:
            logger.error("--list-files only lists uploads; DIRECTION = %s", settings.direction)
            sys.exit(1)

        absolute_roots = tuple(os.path.abspath(root) for root in settings.local_directories)
        for root in absolute_roots:
            if root not in seen_roots:
                roots.append(root)
                seen_roots.add(root)

        existing_roots = tuple(root for root in absolute_roots if os.path.isdir(root))
        for root in absolute_roots:
            if not os.path.isdir(root):
                logger.warning("Local upload root does not exist; listing it without files: %s", root)

        merged_files = build_merged_file_map(
            existing_roots,
            settings.ignore_dirs,
            upload_config.extra_ignore_patterns,
            assume_default_deployignore=True,
        )
        for relative_path, local_path in merged_files.items():
            absolute_path = os.path.abspath(local_path)
            if relative_path in files and files[relative_path] != absolute_path:
                logger.warning(
                    "Duplicate upload path %s from %s; keeping first source %s",
                    relative_path,
                    absolute_path,
                    files[relative_path],
                )
                continue
            files[relative_path] = absolute_path

    with open(output_file, "w", encoding="utf-8") as output:
        json.dump({"roots": roots, "files": dict(sorted(files.items()))}, output, ensure_ascii=False, indent=2)
    logger.info("Wrote %d upload files from %d roots to %s", len(files), len(roots), output_file)


def run_list_files(args: object) -> None:
    """Build and write the final upload listing for INI or PHP settings."""
    settings_file = args.settings_file  # type: ignore[attr-defined]
    if settings_file.endswith(".php"):
        upload_configs = php_upload_configs(args)
    else:
        settings = apply_overrides(load_settings(settings_file), args)  # type: ignore[arg-type]
        if settings.direction != DIRECTION_UP:
            logger.error("--list-files only lists uploads; %s has DIRECTION = %s", settings_file, settings.direction)
            sys.exit(1)
        upload_configs = [UploadConfig(settings, load_ignore_file(getattr(args, "ignore_file", None)))]

    write_upload_list(upload_configs, args.list_files)  # type: ignore[attr-defined]
