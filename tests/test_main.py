"""Tests for the sync entry point."""

import dataclasses
import ftplib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main
import remote_verify
import upload_list
from config import Settings
from hash_db import RemoteFact, compute_file_hash, get_stored_rows, open_hash_db, upsert_hashes
from run_failures import run_failures
from tests.main_test_helpers import make_settings, write_ini


class TestOperationFailureExitCode:
    def _run_ini(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        failure: bool,
    ) -> dict[str, object]:
        caplog.set_level(logging.INFO)
        local = tmp_path / "local"
        local.mkdir()
        (local / "bad.txt").write_text("failed contents")
        (local / "good.txt").write_text("successful contents")
        cache = tmp_path / "cache.db"
        ini = write_ini(tmp_path, local)
        monkeypatch.setattr(
            "sys.argv",
            ["main.py", str(ini), "--local-dir", str(local), "--hash-cache-file", str(cache)],
        )
        ftp = MagicMock(spec=ftplib.FTP)
        monkeypatch.setattr(main, "connect_ftp", lambda settings: ftp)

        def upload(args: tuple[str, str, Settings, list[str] | None]) -> str:
            if failure and args[0] == "bad.txt":
                raise ftplib.error_temp("write refused")
            return args[0]

        monkeypatch.setattr(main, "upload_file", upload)
        if failure:
            with pytest.raises(SystemExit) as exc_info:
                main.main()
            exit_code = exc_info.value.code
        else:
            main.main()
            exit_code = None

        session = open_hash_db(str(cache))
        rows = get_stored_rows(session)
        session.close()
        return {"exit_code": exit_code, "rows": rows, "logs": caplog.text}

    def test_failed_upload_exits_nonzero_and_is_not_cached(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = self._run_ini(tmp_path, monkeypatch, caplog, failure=True)

        assert result["exit_code"] == 1
        assert set(result["rows"]) == {"good.txt"}
        assert "Finished: 1 operations failed" in str(result["logs"])

    def test_successful_uploads_keep_zero_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        result = self._run_ini(tmp_path, monkeypatch, caplog, failure=False)

        assert result["exit_code"] is None
        assert set(result["rows"]) == {"bad.txt", "good.txt"}
        assert "Finished: 0 operations failed" in str(result["logs"])

    def test_php_entries_share_failure_count(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = make_settings(Path("."), "")
        configs = [
            upload_list.UploadConfig(settings, ()),
            upload_list.UploadConfig(settings, ()),
        ]
        monkeypatch.setattr("sys.argv", ["main.py", "config.php", "--local-dir", "."])
        monkeypatch.setattr(main, "php_upload_configs", lambda args: configs)
        calls: list[int] = []

        def run_sync(settings: Settings, patterns: tuple[str, ...], resync: bool) -> None:
            calls.append(len(calls))
            if len(calls) == 1:
                run_failures.record("transfer", "bad.txt")

        monkeypatch.setattr(main, "_run_sync", run_sync)

        with pytest.raises(SystemExit) as exc_info:
            main.main()

        assert exc_info.value.code == 1
        assert calls == [0, 1]


class TestRunSyncHashCacheFolder:
    def test_missing_folder_exits_before_connecting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        def fail_connect(settings: Settings) -> None:
            raise AssertionError("must not connect when the hash cache folder is missing")

        monkeypatch.setattr(main, "connect_ftp", fail_connect)
        missing_dir = tmp_path / "missing"

        with pytest.raises(SystemExit) as exc_info:
            main._run_sync(make_settings(tmp_path, str(missing_dir / "cache.db")), (), resync=False)

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
            make_settings(local, str(tmp_path / "cache.db")), ftp_directory="/vendor", verify_remote=verify_remote
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


class TestRunSyncDeleteSourceAfterDownload:
    def _run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: bool) -> list[str]:
        calls: list[str] = []
        monkeypatch.setattr(main, "connect_ftp", lambda s: MagicMock(spec=ftplib.FTP))
        monkeypatch.setattr(main, "get_ftp_files_recursive", lambda ftp, ignore_dirs: ["run/a.txt"])
        monkeypatch.setattr(main, "sync_files", lambda s, f, a: [])
        monkeypatch.setattr(main, "handle_old_files", lambda *a: calls.append("old"))
        monkeypatch.setattr(main, "delete_downloaded_ftp_files", lambda ftp, s, files: calls.append("delete") or 1)
        settings = dataclasses.replace(
            make_settings(tmp_path, ""), direction="down", delete_source_after_download=flag
        )
        main._run_sync(settings, (), resync=False)
        return calls

    def test_flag_deletes_remote_and_keeps_local_files_in_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._run(tmp_path, monkeypatch, flag=True) == ["delete"]

    def test_without_flag_old_files_are_moved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(tmp_path, monkeypatch, flag=False) == ["old"]
