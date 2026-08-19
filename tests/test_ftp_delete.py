"""Tests for FTP deletion helpers."""

import ftplib
from unittest.mock import MagicMock

from config import Settings
from ftp_delete import clear_remote_dirs


def _settings() -> Settings:
    return Settings(
        local_directories=("C:\\local",),
        ftp_directory="/",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
        direction="up",
        clear_remote_dirs=("cache/css",),
    )


def _mock_ftp(listings: dict[str, list[str]]) -> MagicMock:
    """Mock FTP where listings maps absolute dir path to entry basenames."""
    ftp = MagicMock(spec=ftplib.FTP)

    def nlst(path: str) -> list[str]:
        if path not in listings:
            raise ftplib.error_perm("550 No such directory")
        return listings[path]

    def cwd(path: str) -> None:
        if path != "/" and path not in listings:
            raise ftplib.error_perm("550 Not a directory")

    ftp.nlst.side_effect = nlst
    ftp.cwd.side_effect = cwd
    return ftp


class TestClearRemoteDirs:
    """Tests for clear_remote_dirs."""

    def test_deletes_all_files_recursively(self) -> None:
        ftp = _mock_ftp(
            {
                "/cache/css": ["a.css", "sub"],
                "/cache/css/sub": ["b.css"],
            }
        )
        deleted = clear_remote_dirs(ftp, _settings(), ("cache/css",))
        assert deleted == 2
        deleted_paths = {call.args[0] for call in ftp.delete.call_args_list}
        assert deleted_paths == {"/cache/css/a.css", "/cache/css/sub/b.css"}

    def test_removes_empty_subdirs_but_keeps_listed_dir(self) -> None:
        ftp = _mock_ftp(
            {
                "/cache/css": ["sub"],
                "/cache/css/sub": ["b.css"],
            }
        )
        clear_remote_dirs(ftp, _settings(), ("cache/css",))
        removed = {call.args[0] for call in ftp.rmd.call_args_list}
        assert removed == {"/cache/css/sub"}

    def test_missing_dir_skipped_without_raising(self) -> None:
        ftp = _mock_ftp({})
        deleted = clear_remote_dirs(ftp, _settings(), ("cache/css",))
        assert deleted == 0
        ftp.delete.assert_not_called()

    def test_multiple_dirs(self) -> None:
        ftp = _mock_ftp(
            {
                "/cache/css": ["a.css"],
                "/cache/js": ["b.js"],
            }
        )
        deleted = clear_remote_dirs(ftp, _settings(), ("cache/css", "cache/js"))
        assert deleted == 2

    def test_restores_base_directory(self) -> None:
        ftp = _mock_ftp({"/cache/css": ["a.css"]})
        clear_remote_dirs(ftp, _settings(), ("cache/css",))
        assert ftp.cwd.call_args_list[-1].args[0] == "/"
