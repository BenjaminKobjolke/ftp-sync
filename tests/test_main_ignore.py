"""Tests for extra ignore-file handling in the sync entry point."""

import argparse
import dataclasses
import ftplib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import main
import upload_list
from config import Settings
from php_config import PhpDeployEntry
from tests.main_test_helpers import make_settings, write_ini


class TestExtraIgnoreFile:
    def test_ini_passes_extra_patterns_to_sync(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        local = tmp_path / "local"
        local.mkdir()
        ini = write_ini(tmp_path, local)
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
        ini = write_ini(tmp_path, local)
        missing = str(tmp_path / "missing.ignore")
        sync = MagicMock(spec=main._run_sync)
        connect = MagicMock(spec=main.connect_ftp)
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
        monkeypatch.setattr(upload_list, "parse_php_config", lambda path: [entry])
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
        settings = dataclasses.replace(make_settings(local, ""), no_delete=True)
        ftp = MagicMock(spec=ftplib.FTP)
        uploads: list[str] = []

        def record_upload(settings: Settings, args_list: list[tuple[object, ...]]) -> list[str]:
            uploads.extend(args[0] for args in args_list)  # type: ignore[arg-type]
            return []

        monkeypatch.setattr(main, "connect_ftp", lambda value: ftp)
        monkeypatch.setattr(main, "get_ftp_files_recursive", lambda value, ignore_dirs: [])
        monkeypatch.setattr(main, "sync_files", lambda value, operation, args: record_upload(value, args))
        delete_files = MagicMock(spec=main.delete_ftp_files)
        monkeypatch.setattr(main, "delete_ftp_files", delete_files)

        main._run_sync(settings, main.load_ignore_file(str(ignore_file)), resync=False)

        assert uploads == ["index.php"]
        delete_files.assert_not_called()
