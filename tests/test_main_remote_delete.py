"""Tests for preserving remote files excluded from uploads."""

import dataclasses
import ftplib
import logging
from pathlib import Path
from unittest.mock import MagicMock

import main
import pytest
from config import Settings
from hash_db import get_stored_rows, open_hash_db, upsert_hashes
from run_failures import run_failures
from tests.main_test_helpers import make_settings


def _settings(local: Path, cache: Path) -> Settings:
    return dataclasses.replace(
        make_settings(local, str(cache)), ftp_directory="/remote", no_delete=False
    )


def _seed_cache(cache: str, path: str) -> None:
    session = open_hash_db(cache)
    upsert_hashes(session, {path: "previous-hash"})
    session.close()


def _cached_paths(cache: str) -> set[str]:
    session = open_hash_db(cache)
    paths = set(get_stored_rows(session))
    session.close()
    return paths


def test_newly_ignored_file_is_dropped_from_cache_without_remote_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    local = tmp_path / "local"
    ignored_dir = local / "data" / "mcp-tool-cache"
    ignored_dir.mkdir(parents=True)
    (ignored_dir / "x.ser").write_text("runtime cache")
    (local / ".deployignore").write_text("data/mcp-tool-cache/\n")
    cache = str(tmp_path / "cache.db")
    _seed_cache(cache, "data/mcp-tool-cache/x.ser")
    settings = _settings(local, Path(cache))
    ftp = MagicMock(spec=ftplib.FTP)
    monkeypatch.setattr(main, "sync_files", lambda *args: [])
    caplog.set_level(logging.INFO)

    main._upload_with_hash_cache(settings, {}, ftp, ())

    ftp.delete.assert_not_called()
    assert _cached_paths(cache) == set()
    assert "Dropping 1 hash cache entries now excluded by ignore rules" in caplog.text


def test_truly_removed_file_is_deleted_and_removed_from_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "local"
    local.mkdir()
    cache = str(tmp_path / "cache.db")
    _seed_cache(cache, "gone.txt")
    settings = _settings(local, Path(cache))
    ftp = MagicMock(spec=ftplib.FTP)
    monkeypatch.setattr(main, "sync_files", lambda *args: [])

    main._upload_with_hash_cache(settings, {}, ftp, ())

    ftp.delete.assert_called_once_with("/remote/gone.txt")
    assert _cached_paths(cache) == set()


def test_failed_remote_delete_keeps_cache_row_for_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    local = tmp_path / "local"
    local.mkdir()
    cache = str(tmp_path / "cache.db")
    _seed_cache(cache, "gone.txt")
    settings = _settings(local, Path(cache))
    ftp = MagicMock(spec=ftplib.FTP)
    ftp.delete.side_effect = ftplib.error_perm("550 Permission denied")
    remove_dirs = MagicMock()
    monkeypatch.setattr(main, "sync_files", lambda *args: [])
    monkeypatch.setattr(main, "remove_empty_ftp_dirs", remove_dirs)

    main._upload_with_hash_cache(settings, {}, ftp, ())

    assert _cached_paths(cache) == {"gone.txt"}
    assert run_failures.count == 1
    remove_dirs.assert_not_called()


def test_ftp_scan_keeps_ignored_remote_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    local = tmp_path / "local"
    local.mkdir()
    (local / ".deployignore").write_text("data/mcp-tool-cache/\n")
    settings = dataclasses.replace(make_settings(local, ""), ftp_directory="/remote", no_delete=False)
    ftp_files = ["data/mcp-tool-cache/x.ser", "obsolete.txt"]
    monkeypatch.setattr(main, "get_ftp_files_recursive", lambda *args, **kwargs: ftp_files)
    monkeypatch.setattr(main, "sync_files", lambda *args: [])
    delete = MagicMock()
    monkeypatch.setattr(main, "delete_ftp_files", delete)

    main._upload_with_ftp_scan(settings, {}, MagicMock(spec=ftplib.FTP), ())

    assert delete.call_args.args[2] == {"data/mcp-tool-cache/x.ser", "deploy.ver"}
