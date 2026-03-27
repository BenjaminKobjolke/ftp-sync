"""Tests for config module."""

import argparse
import dataclasses
from pathlib import Path

import pytest

from config import Settings, apply_overrides, load_settings


class TestSettings:
    """Tests for the Settings dataclass."""

    def test_settings_is_frozen(self) -> None:
        settings = Settings(
            local_directory="local",
            ftp_directory="/remote",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.ftp_host = "other"  # type: ignore[misc]

    def test_settings_defaults(self) -> None:
        settings = Settings(
            local_directory="local",
            ftp_directory="/remote",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )
        assert settings.direction == "down"
        assert settings.concurrent_operations == 1


class TestLoadSettings:
    """Tests for load_settings function."""

    def test_missing_file_raises_error(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Could not read settings file"):
            load_settings(str(tmp_path / "nonexistent.ini"))

    def test_missing_ftp_section_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[OTHER]\nkey = value\n")
        with pytest.raises(ValueError, match="Missing \\[FTP\\] section"):
            load_settings(str(ini_file))

    def test_missing_required_setting_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[FTP]\nFTP_HOST = host\nFTP_USER = user\n")
        with pytest.raises(ValueError, match="Missing required setting: FTP_PASS"):
            load_settings(str(ini_file))

    def test_invalid_direction_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\nDIRECTION = invalid\n")
        with pytest.raises(ValueError, match="Invalid DIRECTION"):
            load_settings(str(ini_file))

    def test_invalid_concurrent_operations_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\nCONCURRENT_UPLOADS_OR_DOWNLOADS = 0\n"
        )
        with pytest.raises(ValueError, match="CONCURRENT_UPLOADS_OR_DOWNLOADS must be >= 1"):
            load_settings(str(ini_file))

    def test_valid_ini_parses_correctly(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\n"
            "LOCAL_DIRECTORY = C:\\backup\n"
            "FTP_DIRECTORY = /remote/path\n"
            "FTP_HOST = ftp.example.com\n"
            "FTP_USER = admin\n"
            "FTP_PASS = secret\n"
            "DIRECTION = up\n"
            "CONCURRENT_UPLOADS_OR_DOWNLOADS = 4\n"
        )
        settings = load_settings(str(ini_file))
        assert settings.local_directory == "C:\\backup"
        assert settings.ftp_directory == "/remote/path"
        assert settings.ftp_host == "ftp.example.com"
        assert settings.ftp_user == "admin"
        assert settings.ftp_pass == "secret"
        assert settings.direction == "up"
        assert settings.concurrent_operations == 4

    def test_defaults_when_optional_fields_missing(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\n")
        settings = load_settings(str(ini_file))
        assert settings.local_directory == ""
        assert settings.ftp_directory == ""
        assert settings.direction == "down"
        assert settings.concurrent_operations == 1


class TestApplyOverrides:
    """Tests for apply_overrides function."""

    def _base_settings(self) -> Settings:
        return Settings(
            local_directory="original_local",
            ftp_directory="/original_remote",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )

    def test_no_overrides(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir=None)
        result = apply_overrides(settings, args)
        assert result is settings

    def test_local_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir="new_local", ftp_dir=None)
        result = apply_overrides(settings, args)
        assert result.local_directory == "new_local"
        assert result.ftp_directory == "/original_remote"

    def test_ftp_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir="/new_remote")
        result = apply_overrides(settings, args)
        assert result.local_directory == "original_local"
        assert result.ftp_directory == "/new_remote"

    def test_both_overrides(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir="new_local", ftp_dir="/new_remote")
        result = apply_overrides(settings, args)
        assert result.local_directory == "new_local"
        assert result.ftp_directory == "/new_remote"
