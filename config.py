"""Configuration loading and settings for FTP Sync."""

import argparse
import configparser
import logging
from dataclasses import dataclass, replace

logger = logging.getLogger(__name__)

REQUIRED_SETTINGS = ["FTP_HOST", "FTP_USER", "FTP_PASS"]
VALID_DIRECTIONS = ("up", "down")


@dataclass(frozen=True)
class Settings:
    """FTP sync configuration settings."""

    local_directories: tuple[str, ...]
    ftp_directory: str
    ftp_host: str
    ftp_user: str
    ftp_pass: str
    direction: str = "down"
    concurrent_operations: int = 1
    ignore_dirs: tuple[str, ...] = ()
    hash_cache_file: str = ""
    transfer_type: str = "FTP"
    ftp_port: int = 0
    delete_source_after_days: int = 0


def _parse_comma_list(raw: str) -> tuple[str, ...]:
    """Parse a comma-separated list into a tuple of stripped, non-empty strings."""
    if not raw:
        return ()
    return tuple(d.strip() for d in raw.split(",") if d.strip())


def _parse_delete_source_after_days(ftp_section: configparser.SectionProxy) -> int:
    """Parse and validate DELETE_SOURCE_AFTER_DAYS from INI section."""
    value = int(ftp_section.get("DELETE_SOURCE_AFTER_DAYS", "0"))
    if value < 0:
        raise ValueError(f"DELETE_SOURCE_AFTER_DAYS must be >= 0, got {value}")
    return value


def load_settings(ini_file: str) -> Settings:
    """Load and validate settings from an INI file."""
    config = configparser.ConfigParser()
    if not config.read(ini_file):
        raise FileNotFoundError(f"Could not read settings file: {ini_file}")

    if "FTP" not in config:
        raise ValueError("Missing [FTP] section in settings file")

    ftp_section = config["FTP"]

    for setting in REQUIRED_SETTINGS:
        if setting not in ftp_section:
            raise ValueError(f"Missing required setting: {setting}")

    direction = ftp_section.get("DIRECTION", "down").lower()
    if direction not in VALID_DIRECTIONS:
        raise ValueError(f"Invalid DIRECTION '{direction}', must be one of: {', '.join(VALID_DIRECTIONS)}")

    concurrent_ops = int(ftp_section.get("CONCURRENT_UPLOADS_OR_DOWNLOADS", "1"))
    if concurrent_ops < 1:
        raise ValueError(f"CONCURRENT_UPLOADS_OR_DOWNLOADS must be >= 1, got {concurrent_ops}")

    local_directories = _parse_comma_list(ftp_section.get("LOCAL_DIRECTORY", ""))
    ignore_dirs = _parse_comma_list(ftp_section.get("IGNORE_DIRS", ""))

    if len(local_directories) > 1 and direction != "up":
        raise ValueError("Multiple LOCAL_DIRECTORY paths are only supported with DIRECTION = up")

    return Settings(
        local_directories=local_directories,
        ftp_directory=ftp_section.get("FTP_DIRECTORY", ""),
        ftp_host=ftp_section["FTP_HOST"],
        ftp_user=ftp_section["FTP_USER"],
        ftp_pass=ftp_section["FTP_PASS"],
        direction=direction,
        concurrent_operations=concurrent_ops,
        ignore_dirs=ignore_dirs,
        hash_cache_file=ftp_section.get("HASH_CACHE_FILE", ""),
        delete_source_after_days=_parse_delete_source_after_days(ftp_section),
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="FTP Sync Tool")
    parser.add_argument("settings_file", help="Path to the settings INI file")
    parser.add_argument(
        "--local-dir", "-l", help="Override LOCAL_DIRECTORY from INI file (comma-separated for multiple)"
    )
    parser.add_argument("--ftp-dir", "-f", help="Override FTP_DIRECTORY from INI file")
    parser.add_argument("--resync", action="store_true", help="Clear hash cache and re-upload all files")
    parser.add_argument("--watcher", "-w", action="store_true", help="Watch for file changes and sync automatically")
    parser.add_argument(
        "--delete-source-after-days", type=int, default=None,
        help="Delete source files older than N days after sync (0=disabled)",
    )
    return parser.parse_args()


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """Apply CLI argument overrides to settings."""
    result = settings
    if args.local_dir:
        result = replace(result, local_directories=_parse_comma_list(args.local_dir))
    if args.ftp_dir:
        result = replace(result, ftp_directory=args.ftp_dir)
    if args.delete_source_after_days is not None:
        result = replace(result, delete_source_after_days=args.delete_source_after_days)
    return result


def settings_from_php_entry(
    ftp_host: str,
    ftp_user: str,
    ftp_pass: str,
    ftp_directory: str,
    local_directories: tuple[str, ...],
    transfer_type: str = "FTP",
    ftp_port: int = 0,
    hash_cache_file: str = "",
) -> Settings:
    """Create Settings from PHP deploy config entry values."""
    return Settings(
        local_directories=local_directories,
        ftp_directory=ftp_directory,
        ftp_host=ftp_host,
        ftp_user=ftp_user,
        ftp_pass=ftp_pass,
        direction="up",
        transfer_type=transfer_type,
        ftp_port=ftp_port,
        hash_cache_file=hash_cache_file,
    )
