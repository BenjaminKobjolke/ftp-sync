"""Tests for the sync entry point."""

import dataclasses
import ftplib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main
import remote_verify
from config import Settings
from hash_db import RemoteFact, compute_file_hash, get_stored_rows, open_hash_db, upsert_hashes


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


class TestUploadWithHashCacheVerifyRemote:
    def _setup(self, tmp_path: Path, verify_remote: bool) -> tuple[Settings, dict[str, str]]:
        local = tmp_path / "local"
        (local / "composer").mkdir(parents=True)
        (local / "composer" / "autoload_real.php").write_bytes(b"new hash")
        (local / "same.php").write_bytes(b"same")
        merged = {
            "composer/autoload_real.php": str(local / "composer" / "autoload_real.php"),
            "same.php": str(local / "same.php"),
        }
        settings = dataclasses.replace(
            _settings(local, str(tmp_path / "cache.db")), ftp_directory="/vendor", verify_remote=verify_remote
        )
        session = open_hash_db(settings.hash_cache_file)
        facts = {
            "composer/autoload_real.php": RemoteFact(8, "20261001000000"),
            "same.php": RemoteFact(4, "20261001000000"),
        }
        upsert_hashes(session, {rel: compute_file_hash(p) for rel, p in merged.items()}, facts)
        session.close()
        return settings, merged

    def test_drifted_file_is_reuploaded_and_facts_recorded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings, merged = self._setup(tmp_path, verify_remote=True)
        listings = [
            {
                "composer/autoload_real.php": RemoteFact(8, "20261024072300"),
                "same.php": RemoteFact(4, "20261001000000"),
            },
            {"composer/autoload_real.php": RemoteFact(8, "20261030070700")},
        ]
        calls: list[set[str] | None] = []

        def fake_list(ftp: object, root: str, ignore_dirs: tuple[str, ...] = (), subdirs: set[str] | None = None):
            calls.append(subdirs)
            return listings[len(calls) - 1]

        uploaded: list[str] = []

        def fake_sync(settings: Settings, func: object, args_list: list[tuple[str, ...]]) -> list[str]:
            uploaded.extend(args[0] for args in args_list)
            return [args[0] for args in args_list]

        monkeypatch.setattr(remote_verify, "list_remote_facts", fake_list)
        monkeypatch.setattr(main, "sync_files", fake_sync)

        main._upload_with_hash_cache(settings, merged, MagicMock(spec=ftplib.FTP))

        assert uploaded == ["composer/autoload_real.php"]
        assert calls == [None, {"composer"}]
        session = open_hash_db(settings.hash_cache_file)
        row = get_stored_rows(session)["composer/autoload_real.php"]
        assert (row.remote_size, row.remote_modify) == (8, "20261030070700")
        session.close()

    def test_without_flag_remote_is_not_listed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        settings, merged = self._setup(tmp_path, verify_remote=False)
        monkeypatch.setattr(remote_verify, "list_remote_facts", MagicMock(side_effect=AssertionError("must not list")))
        sync = MagicMock(return_value=[])
        monkeypatch.setattr(main, "sync_files", sync)

        main._upload_with_hash_cache(settings, merged, MagicMock(spec=ftplib.FTP))

        sync.assert_not_called()
