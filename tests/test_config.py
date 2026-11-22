"""Tests for config module."""

import argparse
import dataclasses
from pathlib import Path

import pytest

from config import Settings, apply_overrides, load_settings


def write_ftp_ini(tmp_path: Path, *entries: str) -> Path:
    ini_file = tmp_path / "settings.ini"
    ftp_settings = ["FTP_HOST = host", "FTP_USER = user", "FTP_PASS = pass", *entries]
    ini_file.write_text("[FTP]\n" + "\n".join(ftp_settings) + "\n")
    return ini_file


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
        assert settings.no_delete is False
        assert settings.version_file == "deploy.ver"


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
        ini_file = write_ftp_ini(tmp_path, "DIRECTION = invalid")
        with pytest.raises(ValueError, match="Invalid DIRECTION"):
            load_settings(str(ini_file))

    def test_invalid_concurrent_operations_raises_error(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "CONCURRENT_UPLOADS_OR_DOWNLOADS = 0")
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
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.local_directories == ()
        assert settings.ftp_directory == ""
        assert settings.direction == "down"
        assert settings.concurrent_operations == 1
        assert settings.hash_cache_file == ""
        assert settings.delete_source_after_days == 0
        assert settings.no_delete is False

    def test_no_delete_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "NO_DELETE = true")
        settings = load_settings(str(ini_file))
        assert settings.no_delete is True

    def test_verify_remote_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "VERIFY_REMOTE = true")
        assert load_settings(str(ini_file)).verify_remote is True

    def test_verify_remote_defaults_to_false(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        assert load_settings(str(ini_file)).verify_remote is False

    def test_version_file_defaults_when_missing(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        assert load_settings(str(ini_file)).version_file == "deploy.ver"

    def test_empty_version_file_disables_setting(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "VERSION_FILE =")
        assert load_settings(str(ini_file)).version_file == ""


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
        args = argparse.Namespace(
            local_dir=None, ftp_dir=None, delete_source_after_days=None, hash_cache_file=None, no_delete=False
        )
        result = apply_overrides(settings, args)
        assert result is settings

    def test_local_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir="new_local", ftp_dir=None, delete_source_after_days=None, hash_cache_file=None, no_delete=False
        )
        result = apply_overrides(settings, args)
        assert result.local_directories == ("new_local",)
        assert result.ftp_directory == "/original_remote"

    def test_ftp_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir=None, ftp_dir="/new_remote", delete_source_after_days=None, hash_cache_file=None, no_delete=False
        )
        result = apply_overrides(settings, args)
        assert result.local_directories == ("original_local",)
        assert result.ftp_directory == "/new_remote"

    def test_both_overrides(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir="new_local",
            ftp_dir="/new_remote",
            delete_source_after_days=None,
            hash_cache_file=None,
            no_delete=False,
        )
        result = apply_overrides(settings, args)
        assert result.local_directories == ("new_local",)
        assert result.ftp_directory == "/new_remote"

    def test_comma_separated_local_dir_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir="C:\\a, C:\\b", ftp_dir=None, delete_source_after_days=None, hash_cache_file=None, no_delete=False
        )
        result = apply_overrides(settings, args)
        assert result.local_directories == ("C:\\a", "C:\\b")

    def test_delete_source_after_days_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir=None,
            ftp_dir=None,
            delete_source_after_days=45,
            hash_cache_file=None,
            no_delete=False,
        )
        result = apply_overrides(settings, args)
        assert result.delete_source_after_days == 45

    def test_hash_cache_file_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir=None,
            ftp_dir=None,
            delete_source_after_days=None,
            hash_cache_file="C:\\new\\cache.db",
            no_delete=False,
        )
        result = apply_overrides(settings, args)
        assert result.hash_cache_file == "C:\\new\\cache.db"

    def test_no_delete_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir=None,
            ftp_dir=None,
            delete_source_after_days=None,
            hash_cache_file=None,
            no_delete=True,
        )
        result = apply_overrides(settings, args)
        assert result.no_delete is True

    def test_no_delete_override_absent_defaults_false(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(local_dir=None, ftp_dir=None, delete_source_after_days=None, hash_cache_file=None)
        result = apply_overrides(settings, args)
        assert result.no_delete is False

    def test_verify_remote_override(self) -> None:
        settings = self._base_settings()
        args = argparse.Namespace(
            local_dir=None, ftp_dir=None, delete_source_after_days=None, hash_cache_file=None, verify_remote=True
        )
        assert apply_overrides(settings, args).verify_remote is True


