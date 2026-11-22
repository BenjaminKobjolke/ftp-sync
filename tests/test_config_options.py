"""Tests for optional INI settings parsed by config."""

from pathlib import Path

import pytest

from config import load_settings
from tests.test_config import write_ftp_ini


class TestLoadSettingsOptions:
    def test_delete_source_after_download_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "DELETE_SOURCE_AFTER_DOWNLOAD = true")
        assert load_settings(str(ini_file)).delete_source_after_download is True

    def test_no_delete_defaults_to_false(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.no_delete is False

    def test_hash_cache_file_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "HASH_CACHE_FILE = C:\\cache\\sync.db")
        settings = load_settings(str(ini_file))
        assert settings.hash_cache_file == "C:\\cache\\sync.db"

    def test_comma_separated_local_directories(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(
            tmp_path,
            "LOCAL_DIRECTORY = C:\\folder1, C:\\folder2",
            "FTP_DIRECTORY = /remote",
            "DIRECTION = up",
        )
        settings = load_settings(str(ini_file))
        assert settings.local_directories == ("C:\\folder1", "C:\\folder2")

    def test_single_local_directory_becomes_tuple(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "LOCAL_DIRECTORY = C:\\backup")
        settings = load_settings(str(ini_file))
        assert settings.local_directories == ("C:\\backup",)

    def test_ignore_dirs_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "IGNORE_DIRS = _old, _alt, Unsortiert")
        settings = load_settings(str(ini_file))
        assert settings.ignore_dirs == ("_old", "_alt", "Unsortiert")

    def test_ignore_dirs_defaults_to_empty(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.ignore_dirs == ()

    def test_clear_remote_dirs_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "CLEAR_REMOTE_DIRS = cache/css, cache/images")
        settings = load_settings(str(ini_file))
        assert settings.clear_remote_dirs == ("cache/css", "cache/images")

    def test_clear_remote_dirs_defaults_to_empty(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.clear_remote_dirs == ()

    def test_delete_source_after_days_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "DELETE_SOURCE_AFTER_DAYS = 30")
        settings = load_settings(str(ini_file))
        assert settings.delete_source_after_days == 30

    def test_delete_source_after_days_negative_raises_error(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "DELETE_SOURCE_AFTER_DAYS = -1")
        with pytest.raises(ValueError, match="DELETE_SOURCE_AFTER_DAYS must be >= 0"):
            load_settings(str(ini_file))

    def test_ftp_port_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "FTP_PORT = 2121")
        settings = load_settings(str(ini_file))
        assert settings.ftp_port == 2121

    def test_ftp_port_defaults_to_zero(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.ftp_port == 0

    def test_ftp_port_negative_raises_error(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "FTP_PORT = -1")
        with pytest.raises(ValueError, match="FTP_PORT must be >= 0"):
            load_settings(str(ini_file))

    def test_transfer_type_ftps_parsed(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "TRANSFER_TYPE = FTPS")
        settings = load_settings(str(ini_file))
        assert settings.transfer_type == "FTPS"

    def test_transfer_type_defaults_to_ftp(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path)
        settings = load_settings(str(ini_file))
        assert settings.transfer_type == "FTP"

    def test_invalid_transfer_type_raises_error(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(tmp_path, "TRANSFER_TYPE = SFTP")
        with pytest.raises(ValueError, match="Invalid TRANSFER_TYPE"):
            load_settings(str(ini_file))

    def test_multi_directory_with_direction_down_raises_error(self, tmp_path: Path) -> None:
        ini_file = write_ftp_ini(
            tmp_path,
            "LOCAL_DIRECTORY = C:\\a, C:\\b",
            "FTP_DIRECTORY = /remote",
            "DIRECTION = down",
        )
        with pytest.raises(ValueError, match="Multiple LOCAL_DIRECTORY.*only supported.*up"):
            load_settings(str(ini_file))


