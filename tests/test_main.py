"""Tests for the sync entry point."""

from pathlib import Path

import pytest

import main
from config import Settings


def _settings(tmp_path: Path, hash_cache_file: str) -> Settings:
    return Settings(
        local_directories=(str(tmp_path),),
        ftp_directory="/",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
        direction="up",
        hash_cache_file=hash_cache_file,
    )


class TestRunSyncHashCacheFolder:
    def test_missing_folder_exits_before_connecting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def fail_connect(settings: Settings) -> None:
            raise AssertionError("must not connect when the hash cache folder is missing")

        monkeypatch.setattr(main, "connect_ftp", fail_connect)
        missing_dir = tmp_path / "missing"

        with pytest.raises(SystemExit) as exc_info:
            main._run_sync(_settings(tmp_path, str(missing_dir / "cache.db")), (), resync=False)

        assert exc_info.value.code == 1
        assert str(missing_dir) in caplog.text
