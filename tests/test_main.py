"""Tests for the sync entry point."""

import argparse
import dataclasses
import ftplib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main
import remote_verify
from config import Settings
from hash_db import RemoteFact, compute_file_hash, get_stored_rows, open_hash_db, upsert_hashes
from php_config import PhpDeployEntry


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


class TestExtraIgnoreFile:
    def _write_ini(self, path: Path, local: Path) -> Path:
        ini = path / "settings.ini"
        ini.write_text(
            "[FTP]\n"
            f"LOCAL_DIRECTORY = {local}\n"
            "FTP_DIRECTORY = /remote\n"
            "FTP_HOST = host\n"
            "FTP_USER = user\n"
            "FTP_PASS = pass\n"
            "DIRECTION = up\n"
        )
        return ini

    def test_ini_passes_extra_patterns_to_sync(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        local = tmp_path / "local"
        local.mkdir()
        ini = self._write_ini(tmp_path, local)
        ignore_file = tmp_path / "extra.ignore"
        ignore_file.write_text("tickets/[0-9]*/\n")
        calls: list[tuple[str, ...]] = []
        monkeypatch.setattr(main, "_run_sync", lambda settings, patterns, resync: calls.append(patterns))
        args = argparse.Namespace(
            settings_file=str(ini),
            ignore_file=str(ignore_file),
            local_dir=None,
            ftp_dir=None,
            delete_source_after_days=None,
            hash_cache_file=None,
            no_delete=False,
        )

        main._run_ini_config(args)

        assert calls == [("tickets/[0-9]*/",)]

    def test_missing_ini_ignore_file_stops_before_sync_or_connect(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local = tmp_path / "local"
        local.mkdir()
        ini = self._write_ini(tmp_path, local)
        missing = str(tmp_path / "missing.ignore")
        sync = MagicMock()
        connect = MagicMock()
        monkeypatch.setattr(main, "_run_sync", sync)
        monkeypatch.setattr(main, "connect_ftp", connect)
        args = argparse.Namespace(
            settings_file=str(ini),
            ignore_file=missing,
            local_dir=None,
            ftp_dir=None,
            delete_source_after_days=None,
            hash_cache_file=None,
            no_delete=False,
        )

        with pytest.raises(FileNotFoundError) as exc_info:
            main._run_ini_config(args)
        assert missing in str(exc_info.value)

        sync.assert_not_called()
        connect.assert_not_called()

    def test_php_combines_entry_root_and_extra_ignore_patterns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local = tmp_path / "local"
        local.mkdir()
        (local / ".deployignore").write_text("themes/demo/cache/\nother/path\n")
        ignore_file = tmp_path / "extra.ignore"
        ignore_file.write_text("tickets/[0-9]*/\n")
        entry = PhpDeployEntry(
            name="site",
            ftp_host="host",
            ftp_user="user",
            ftp_pass="pass",
            ftp_directory="/remote",
            ignore_patterns=("vendor/cache/",),
            subfolder="themes/demo",
        )
        monkeypatch.setattr(main, "parse_php_config", lambda path: [entry])
        calls: list[tuple[str, ...]] = []
        monkeypatch.setattr(main, "_run_sync", lambda settings, patterns, resync: calls.append(patterns))

        main._run_php_config(
            type(
                "Args",
                (),
                {"settings_file": "deploy.php", "local_dir": str(local), "ignore_file": str(ignore_file)},
            )()
        )

        assert calls == [("vendor/cache/", "cache/", "other/path", "tickets/[0-9]*/")]

    def test_no_delete_upload_selection_skips_extra_ignored_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local = tmp_path / "local"
        private = local / "tickets" / "7" / "plan.md"
        private.parent.mkdir(parents=True)
        private.write_text("local plan")
        (local / "index.php").write_text("home")
        ignore_file = tmp_path / "extra.ignore"
        ignore_file.write_text("tickets/[0-9]*/\n")
        settings = dataclasses.replace(_settings(local, ""), no_delete=True)
        ftp = MagicMock(spec=ftplib.FTP)
        uploads: list[str] = []

        def record_upload(settings: Settings, args_list: list[tuple[object, ...]]) -> list[str]:
            uploads.extend(args[0] for args in args_list)  # type: ignore[arg-type]
            return []

        monkeypatch.setattr(main, "connect_ftp", lambda value: ftp)
        monkeypatch.setattr(main, "get_ftp_files_recursive", lambda value, ignore_dirs: [])
        monkeypatch.setattr(main, "sync_files", lambda value, operation, args: record_upload(value, args))
        delete_files = MagicMock()
        monkeypatch.setattr(main, "delete_ftp_files", delete_files)

        main._run_sync(settings, main.load_ignore_file(str(ignore_file)), resync=False)

        assert uploads == ["index.php"]
        delete_files.assert_not_called()


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


class TestRunSyncDeleteSourceAfterDownload:
    def _run(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flag: bool) -> list[str]:
        calls: list[str] = []
        monkeypatch.setattr(main, "connect_ftp", lambda s: MagicMock(spec=ftplib.FTP))
        monkeypatch.setattr(main, "get_ftp_files_recursive", lambda ftp, ignore_dirs: ["run/a.txt"])
        monkeypatch.setattr(main, "sync_files", lambda s, f, a: [])
        monkeypatch.setattr(main, "handle_old_files", lambda *a: calls.append("old"))
        monkeypatch.setattr(main, "delete_downloaded_ftp_files", lambda ftp, s, files: calls.append("delete") or 1)
        settings = dataclasses.replace(
            _settings(tmp_path, ""), direction="down", delete_source_after_download=flag
        )
        main._run_sync(settings, (), resync=False)
        return calls

    def test_flag_deletes_remote_and_keeps_local_files_in_place(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert self._run(tmp_path, monkeypatch, flag=True) == ["delete"]

    def test_without_flag_old_files_are_moved(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self._run(tmp_path, monkeypatch, flag=False) == ["old"]
