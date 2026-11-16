"""Tests for the read-only upload file list."""

import json
import os
import sys
from pathlib import Path

import main
import upload_list
import pytest


def _guard_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("list-files mode must not connect or open the hash cache")

    monkeypatch.setattr(main, "connect_ftp", unexpected)
    monkeypatch.setattr(main, "open_hash_db", unexpected)
    monkeypatch.setattr(upload_list, "open_hash_db", unexpected, raising=False)


def _write_ini(path: Path, local_directory: str, *, direction: str = "up", cache: str = "") -> None:
    path.write_text(
        "[FTP]\n"
        f"LOCAL_DIRECTORY = {local_directory}\n"
        "FTP_DIRECTORY = /remote\n"
        "FTP_HOST = example.test\n"
        "FTP_USER = user\n"
        "FTP_PASS = password\n"
        f"DIRECTION = {direction}\n"
        f"HASH_CACHE_FILE = {cache}\n",
        encoding="utf-8",
    )


def _run_main(monkeypatch: pytest.MonkeyPatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["main.py", *args])
    main.main()


def test_ini_lists_merged_upload_map_without_side_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _guard_side_effects(monkeypatch)
    root_a = tmp_path / "root-a"
    root_b = tmp_path / "root-b"
    root_a.mkdir()
    root_b.mkdir()
    (root_a / ".deployignore").write_text("secret/\n", encoding="utf-8")
    (root_a / "shared.txt").write_text("older", encoding="utf-8")
    (root_b / "shared.txt").write_text("newer", encoding="utf-8")
    (root_b / "visible.txt").write_text("visible", encoding="utf-8")
    (root_b / "CLAUDE.md").write_text("private", encoding="utf-8")
    (root_a / "secret").mkdir()
    (root_a / "secret" / "hidden.txt").write_text("hidden", encoding="utf-8")
    os.utime(root_a / "shared.txt", (1, 1))
    os.utime(root_b / "shared.txt", (2, 2))
    cache = tmp_path / "cache.db"
    settings = tmp_path / "settings.ini"
    _write_ini(settings, f"{root_a},{root_b}", cache=str(cache))
    output = tmp_path / "upload-list.json"

    _run_main(monkeypatch, str(settings), "--list-files", str(output))

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "roots": [os.path.abspath(root_a), os.path.abspath(root_b)],
        "files": {
            "shared.txt": os.path.abspath(root_b / "shared.txt"),
            "visible.txt": os.path.abspath(root_b / "visible.txt"),
        },
    }
    assert cache.exists() is False
    assert (root_b / ".deployignore").exists() is False


def test_local_dir_overrides_ini_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_side_effects(monkeypatch)
    configured = tmp_path / "configured"
    override = tmp_path / "override"
    configured.mkdir()
    override.mkdir()
    (configured / "configured.txt").write_text("old", encoding="utf-8")
    (override / "override.txt").write_text("new", encoding="utf-8")
    settings = tmp_path / "settings.ini"
    _write_ini(settings, str(configured))
    output = tmp_path / "upload-list.json"

    _run_main(monkeypatch, str(settings), "--local-dir", str(override), "--list-files", str(output))

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "roots": [os.path.abspath(override)],
        "files": {"override.txt": os.path.abspath(override / "override.txt")},
    }


def test_ignore_file_is_applied_and_empty_env_value_is_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _guard_side_effects(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    (root / "keep.txt").write_text("keep", encoding="utf-8")
    (root / "private.txt").write_text("private", encoding="utf-8")
    settings = tmp_path / "settings.ini"
    _write_ini(settings, str(root))
    ignore_file = tmp_path / "extra.ignore"
    ignore_file.write_text("private.txt\n", encoding="utf-8")
    output = tmp_path / "upload-list.json"

    _run_main(monkeypatch, str(settings), "--ignore-file", str(ignore_file), "--list-files", str(output))
    assert json.loads(output.read_text(encoding="utf-8"))["files"] == {
        "keep.txt": os.path.abspath(root / "keep.txt")
    }

    monkeypatch.setenv("FTP_SYNC_IGNORE_FILE", "")
    output_env = tmp_path / "upload-list-env.json"
    _run_main(monkeypatch, str(settings), "--list-files", str(output_env))
    assert json.loads(output_env.read_text(encoding="utf-8"))["files"] == {
        "keep.txt": os.path.abspath(root / "keep.txt"),
        "private.txt": os.path.abspath(root / "private.txt"),
    }


def test_php_config_merges_subfolder_and_entry_ignore_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _guard_side_effects(monkeypatch)
    root = tmp_path / "repo"
    subfolder = root / "themes" / "demo"
    (subfolder / "cache").mkdir(parents=True)
    (subfolder / "cache" / "cached.txt").write_text("cache", encoding="utf-8")
    (subfolder / "index.php").write_text("theme", encoding="utf-8")
    (subfolder / "private.txt").write_text("private", encoding="utf-8")
    (root / "site.txt").write_text("site", encoding="utf-8")
    (root / ".deployignore").write_text("themes/demo/private.txt\n", encoding="utf-8")
    config = tmp_path / "deploy.php"
    config.write_text(
        """<?php
        return array(
            array(
                'name' => 'Theme',
                'git' => array('subfolder' => 'themes/demo', 'ignore' => array('cache/')),
                'ftp' => array('root' => '/theme', 'server' => 'host', 'username' => 'u', 'password' => 'p')
            ),
            array(
                'name' => 'Site',
                'git' => array('ignore' => array('site.txt', 'themes/demo/cache/')),
                'ftp' => array('root' => '/site', 'server' => 'host', 'username' => 'u', 'password' => 'p')
            )
        );
        ?>""",
        encoding="utf-8",
    )
    output = tmp_path / "upload-list.json"

    _run_main(monkeypatch, str(config), "--local-dir", str(root), "--list-files", str(output))

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "roots": [os.path.abspath(subfolder), os.path.abspath(root)],
        "files": {
            "index.php": os.path.abspath(subfolder / "index.php"),
            "themes/demo/index.php": os.path.abspath(subfolder / "index.php"),
        },
    }


def test_missing_root_is_listed_but_not_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_side_effects(monkeypatch)
    missing = tmp_path / "missing"
    settings = tmp_path / "settings.ini"
    _write_ini(settings, str(missing))
    output = tmp_path / "upload-list.json"

    _run_main(monkeypatch, str(settings), "--list-files", str(output))

    assert json.loads(output.read_text(encoding="utf-8")) == {
        "roots": [os.path.abspath(missing)],
        "files": {},
    }
    assert missing.exists() is False


def test_download_direction_fails_without_writing_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _guard_side_effects(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    settings = tmp_path / "settings.ini"
    _write_ini(settings, str(root), direction="down")
    output = tmp_path / "upload-list.json"

    with pytest.raises(SystemExit) as exc_info:
        _run_main(monkeypatch, str(settings), "--list-files", str(output))

    assert exc_info.value.code == 1
    assert f"--list-files only lists uploads; {settings} has DIRECTION = down" in caplog.text
    assert output.exists() is False


def test_php_config_still_requires_local_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _guard_side_effects(monkeypatch)
    config = tmp_path / "deploy.php"
    config.write_text("<?php return array(); ?>", encoding="utf-8")
    output = tmp_path / "upload-list.json"

    with pytest.raises(SystemExit) as exc_info:
        _run_main(monkeypatch, str(config), "--list-files", str(output))

    assert exc_info.value.code == 1
    assert output.exists() is False
