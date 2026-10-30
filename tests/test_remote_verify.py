"""Tests for remote drift detection used by --verify-remote."""

from pathlib import Path

from hash_db import RemoteFact, compute_file_hash, get_stored_rows, open_hash_db, upsert_hashes
from remote_verify import find_remote_drift


def _cached_file(tmp_path: Path, name: str, content: bytes) -> tuple[str, str]:
    path = tmp_path / name
    path.write_bytes(content)
    return name, str(path)


def test_remote_modify_changed_is_drift(tmp_path: Path) -> None:
    # The incident: same size, but something else overwrote the remote file.
    rel, abs_path = _cached_file(tmp_path, "autoload_real.php", b"new hash")
    session = open_hash_db(str(tmp_path / "cache.db"))
    upsert_hashes(session, {rel: compute_file_hash(abs_path)}, {rel: RemoteFact(8, "20261001000000")})

    drift = find_remote_drift(session, {rel: abs_path}, {rel: RemoteFact(8, "20261024072300")})

    assert drift == [rel]
    session.close()


def test_recorded_facts_matching_is_not_drift(tmp_path: Path) -> None:
    rel, abs_path = _cached_file(tmp_path, "a.php", b"same")
    session = open_hash_db(str(tmp_path / "cache.db"))
    upsert_hashes(session, {rel: compute_file_hash(abs_path)}, {rel: RemoteFact(4, "20261001000000")})

    assert find_remote_drift(session, {rel: abs_path}, {rel: RemoteFact(4, "20261001000000")}) == []
    session.close()


def test_missing_on_remote_is_drift(tmp_path: Path) -> None:
    rel, abs_path = _cached_file(tmp_path, "a.php", b"same")
    session = open_hash_db(str(tmp_path / "cache.db"))
    upsert_hashes(session, {rel: compute_file_hash(abs_path)}, {rel: RemoteFact(4, "20261001000000")})

    assert find_remote_drift(session, {rel: abs_path}, {}) == [rel]
    session.close()


def test_old_row_with_size_mismatch_is_drift(tmp_path: Path) -> None:
    rel, abs_path = _cached_file(tmp_path, "a.php", b"local content")
    session = open_hash_db(str(tmp_path / "cache.db"))
    upsert_hashes(session, {rel: compute_file_hash(abs_path)})

    assert find_remote_drift(session, {rel: abs_path}, {rel: RemoteFact(3, "20261001000000")}) == [rel]
    session.close()


def test_old_row_with_matching_size_adopts_remote_facts(tmp_path: Path) -> None:
    rel, abs_path = _cached_file(tmp_path, "crlf.txt", b"one\r\ntwo\r\n")
    session = open_hash_db(str(tmp_path / "cache.db"))
    file_hash = compute_file_hash(abs_path)
    upsert_hashes(session, {rel: file_hash})

    # Remote got the ASCII-mode (LF) copy, so its size is smaller by one byte per CRLF.
    drift = find_remote_drift(session, {rel: abs_path}, {rel: RemoteFact(8, "20261001000000")})

    assert drift == []
    row = get_stored_rows(session)[rel]
    assert (row.hash, row.remote_size, row.remote_modify) == (file_hash, 8, "20261001000000")
    session.close()
