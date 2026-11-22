"""Tests for command-line configuration arguments."""

from pathlib import Path

import pytest

from config import Settings, apply_overrides, parse_arguments


def test_parse_arguments_verify_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini", "--verify-remote"])
    assert parse_arguments().verify_remote is True


def test_parse_arguments_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini", "--compare", "out.tsv"])
    args = parse_arguments()
    assert args.compare == "out.tsv"


def test_parse_arguments_compare_defaults_to_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini"])
    args = parse_arguments()
    assert args.compare is None


def test_parse_arguments_delete_source_after_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini", "--delete-source-after-download"])
    settings = Settings(local_directories=("l",), ftp_directory="/", ftp_host="h", ftp_user="u", ftp_pass="p")
    assert apply_overrides(settings, parse_arguments()).delete_source_after_download is True
    assert settings.delete_source_after_download is False


def test_parse_arguments_ignore_file_defaults_to_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ignore_file = str(tmp_path / "extra.ignore")
    monkeypatch.setenv("FTP_SYNC_IGNORE_FILE", ignore_file)
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini"])

    assert parse_arguments().ignore_file == ignore_file


def test_parse_arguments_ignore_file_flag_overrides_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FTP_SYNC_IGNORE_FILE", "from-env.ignore")
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini", "--ignore-file", "from-flag.ignore"])

    assert parse_arguments().ignore_file == "from-flag.ignore"


@pytest.mark.parametrize("environment_value", [None, ""])
def test_parse_arguments_ignore_file_defaults_to_none_when_unset_or_empty(
    monkeypatch: pytest.MonkeyPatch, environment_value: str | None
) -> None:
    monkeypatch.delenv("FTP_SYNC_IGNORE_FILE", raising=False)
    if environment_value is not None:
        monkeypatch.setenv("FTP_SYNC_IGNORE_FILE", environment_value)
    monkeypatch.setattr("sys.argv", ["main.py", "settings.ini"])

    assert parse_arguments().ignore_file is None
