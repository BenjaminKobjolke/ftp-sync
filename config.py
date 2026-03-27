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

    local_directory: str
    ftp_directory: str
    ftp_host: str
    ftp_user: str
    ftp_pass: str
    direction: str = "down"
    concurrent_operations: int = 1


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

    return Settings(
        local_directory=ftp_section.get("LOCAL_DIRECTORY", ""),
        ftp_directory=ftp_section.get("FTP_DIRECTORY", ""),
        ftp_host=ftp_section["FTP_HOST"],
        ftp_user=ftp_section["FTP_USER"],
        ftp_pass=ftp_section["FTP_PASS"],
        direction=direction,
        concurrent_operations=concurrent_ops,
    )


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="FTP Sync Tool")
    parser.add_argument("settings_file", help="Path to the settings INI file")
    parser.add_argument("--local-dir", "-l", help="Override LOCAL_DIRECTORY from INI file")
    parser.add_argument("--ftp-dir", "-f", help="Override FTP_DIRECTORY from INI file")
    return parser.parse_args()


def apply_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    """Apply CLI argument overrides to settings."""
    result = settings
    if args.local_dir:
        result = replace(result, local_directory=args.local_dir)
    if args.ftp_dir:
        result = replace(result, ftp_directory=args.ftp_dir)
    return result
