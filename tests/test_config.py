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
            local_directories=("local",),
            ftp_directory="/remote",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            settings.ftp_host = "other"  # type: ignore[misc]

    def test_settings_defaults(self) -> None:
        settings = Settings(
            local_directories=("local",),
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
        assert settings.local_directories == ("C:\\backup",)
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
        assert settings.local_directories == ()
        assert settings.ftp_directory == ""
        assert settings.direction == "down"
        assert settings.concurrent_operations == 1
        assert settings.hash_cache_file == ""
        assert settings.delete_source_after_days == 0

    def test_hash_cache_file_parsed(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\n"
            "FTP_HOST = host\n"
            "FTP_USER = user\n"
            "FTP_PASS = pass\n"
            "HASH_CACHE_FILE = C:\\cache\\sync.db\n"
        )
        settings = load_settings(str(ini_file))
        assert settings.hash_cache_file == "C:\\cache\\sync.db"

    def test_comma_separated_local_directories(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\n"
            "LOCAL_DIRECTORY = C:\\folder1, C:\\folder2\n"
            "FTP_DIRECTORY = /remote\n"
            "FTP_HOST = host\n"
            "FTP_USER = user\n"
            "FTP_PASS = pass\n"
            "DIRECTION = up\n"
        )
        settings = load_settings(str(ini_file))
        assert settings.local_directories == ("C:\\folder1", "C:\\folder2")

    def test_single_local_directory_becomes_tuple(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[FTP]\nLOCAL_DIRECTORY = C:\\backup\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\n")
        settings = load_settings(str(ini_file))
        assert settings.local_directories == ("C:\\backup",)

    def test_ignore_dirs_parsed(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\n"
            "FTP_HOST = host\n"
            "FTP_USER = user\n"
            "FTP_PASS = pass\n"
            "IGNORE_DIRS = _old, _alt, Unsortiert\n"
        )
        settings = load_settings(str(ini_file))
        assert settings.ignore_dirs == ("_old", "_alt", "Unsortiert")

    def test_ignore_dirs_defaults_to_empty(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text("[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\n")
        settings = load_settings(str(ini_file))
        assert settings.ignore_dirs == ()

    def test_delete_source_after_days_parsed(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\n"
            "DELETE_SOURCE_AFTER_DAYS = 30\n"
        )
        settings = load_settings(str(ini_file))
        assert settings.delete_source_after_days == 30

    def test_delete_source_after_days_negative_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\nFTP_HOST = host\nFTP_USER = user\nFTP_PASS = pass\n"
            "DELETE_SOURCE_AFTER_DAYS = -1\n"
        )
        with pytest.raises(ValueError, match="DELETE_SOURCE_AFTER_DAYS must be >= 0"):
            load_settings(str(ini_file))

    def test_multi_directory_with_direction_down_raises_error(self, tmp_path: Path) -> None:
        ini_file = tmp_path / "settings.ini"
        ini_file.write_text(
            "[FTP]\n"
            "LOCAL_DIRECTORY = C:\\a, C:\\b\n"
            "FTP_DIRECTORY = /remote\n"
            "FTP_HOST = host\n"
            "FTP_USER = user\n"
            "FTP_PASS = pass\n"
            "DIRECTION = down\n"
        )
        with pytest.raises(ValueError, match="Multiple LOCAL_DIRECTORY.*only supported.*up"):
            load_settings(str(ini_file))


class TestApplyOverrides:
    """Tests for apply_overrides function."""

    def _base_settings(self) -> Settings:
        return Settings(
            local_directories=("original_local",),
            ftp_directory="/original_remote",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )

    def test_no_overrides(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir=None, delete_source_after_days=None)
        result = apply_overrides(settings, args)
        assert result is settings

    def test_local_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir="new_local", ftp_dir=None, delete_source_after_days=None)
        result = apply_overrides(settings, args)
        assert result.local_directories == ("new_local",)
        assert result.ftp_directory == "/original_remote"

    def test_ftp_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir="/new_remote", delete_source_after_days=None)
        result = apply_overrides(settings, args)
        assert result.local_directories == ("original_local",)
        assert result.ftp_directory == "/new_remote"

    def test_both_overrides(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir="new_local", ftp_dir="/new_remote", delete_source_after_days=None)
        result = apply_overrides(settings, args)
        assert result.local_directories == ("new_local",)
        assert result.ftp_directory == "/new_remote"

    def test_comma_separated_local_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir="C:\\a, C:\\b", ftp_dir=None, delete_source_after_days=None)
        result = apply_overrides(settings, args)
        assert result.local_directories == ("C:\\a", "C:\\b")

    def test_delete_source_after_days_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir=None, delete_source_after_days=45)
        result = apply_overrides(settings, args)
        assert result.delete_source_after_days == 45
