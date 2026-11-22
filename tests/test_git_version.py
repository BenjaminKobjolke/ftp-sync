"""Tests for writing the uploaded Git revision to the FTP server."""

import ftplib
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

from git_version import local_git_commit, upload_version_file
from run_failures import run_failures
from tests.main_test_helpers import make_settings


def test_local_git_commit_returns_head_for_repository(tmp_path: Path) -> None:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
         "commit", "--allow-empty", "-m", "initial"],
        check=True,
        capture_output=True,
    )

    result = local_git_commit(str(tmp_path))

    expected = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert result == expected


def test_local_git_commit_returns_none_outside_repository(tmp_path: Path) -> None:
    assert local_git_commit(str(tmp_path)) is None


def test_local_git_commit_returns_none_when_git_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    def missing_git(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr("git_version.subprocess.run", missing_git)

    assert local_git_commit(str(tmp_path)) is None


def test_upload_version_file_stores_exact_hash_bytes(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, "")
    ftp = MagicMock(spec=ftplib.FTP)
    uploaded: list[tuple[str, bytes]] = []

    def store(command: str, content: BytesIO) -> None:
        uploaded.append((command, content.read()))

    ftp.storbinary.side_effect = store

    upload_version_file(ftp, settings, "a" * 40)

    assert uploaded == [("STOR /deploy.ver", b"a" * 40)]


def test_upload_version_file_records_ftp_failure(tmp_path: Path) -> None:
    run_failures.reset()
    ftp = MagicMock(spec=ftplib.FTP)
    ftp.storbinary.side_effect = ftplib.error_perm("write refused")

    try:
        upload_version_file(ftp, make_settings(tmp_path, ""), "a" * 40)
        assert run_failures.count == 1
    finally:
        run_failures.reset()
