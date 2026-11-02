"""Tests for FTP deletion helpers."""

import ftplib
from pathlib import Path
from unittest.mock import MagicMock

from config import Settings
from ftp_delete import clear_remote_dirs, delete_downloaded_ftp_files


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


class TestDeleteDownloadedFtpFiles:
    def _run(self, tmp_path: Path, remote_sizes: dict[str, int | Exception]) -> tuple[int, MagicMock]:
        settings = Settings(
            local_directories=(str(tmp_path),),
            ftp_directory="/ev",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
        )
        ftp = MagicMock(spec=ftplib.FTP)

        def size(path: str) -> int:
            value = remote_sizes[path.removeprefix("/ev/")]
            if isinstance(value, Exception):
                raise value
            return value

        ftp.size.side_effect = size
        ftp.rmd.side_effect = ftplib.error_perm("550 not empty")
        return delete_downloaded_ftp_files(ftp, settings, list(remote_sizes)), ftp

    def test_deletes_only_files_with_matching_local_copy(self, tmp_path: Path) -> None:
        (tmp_path / "run").mkdir()
        (tmp_path / "run" / "same.txt").write_bytes(b"abc")
        (tmp_path / "run" / "partial.txt").write_bytes(b"a")
        (tmp_path / "run" / "err.txt").write_bytes(b"abc")

        deleted, ftp = self._run(
            tmp_path,
            {
                "run/same.txt": 3,
                "run/partial.txt": 3,
                "run/missing.txt": 3,
                "run/err.txt": ftplib.error_perm("550 no size"),
            },
        )

        assert deleted == 1
        ftp.delete.assert_called_once_with("/ev/run/same.txt")
        ftp.rmd.assert_called_once_with("/ev/run")
