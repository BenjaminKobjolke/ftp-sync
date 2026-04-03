"""Tests for hash_db module."""

from pathlib import Path

from hash_db import (
    compute_file_hash,
    delete_paths,
    filter_changed_files,
    find_deleted_paths,
    get_stored_hashes,
    open_hash_db,
    upsert_hashes,
)


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_consistent_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hello world")
        h1 = compute_file_hash(str(f))
        h2 = compute_file_hash(str(f))
        assert h1 == h2

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert compute_file_hash(str(f1)) != compute_file_hash(str(f2))

    def test_same_size_different_content(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("aaaa")
        f2.write_text("bbbb")
        assert compute_file_hash(str(f1)) != compute_file_hash(str(f2))


class TestOpenHashDb:
    """Tests for open_hash_db function."""

    def test_creates_database(self, tmp_path: Path) -> None:
        db_path = tmp_path / "cache.db"
        session = open_hash_db(str(db_path))
        assert db_path.exists()
        session.close()

    def test_empty_db_returns_no_hashes(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        assert get_stored_hashes(session) == {}
        session.close()


class TestUpsertAndGetHashes:
    """Tests for upsert_hashes and get_stored_hashes."""

    def test_insert_and_retrieve(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "hash_a", "b.txt": "hash_b"})
        stored = get_stored_hashes(session)
        assert stored == {"a.txt": "hash_a", "b.txt": "hash_b"}
        session.close()

    def test_update_existing(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "old_hash"})
        upsert_hashes(session, {"a.txt": "new_hash"})
        stored = get_stored_hashes(session)
        assert stored["a.txt"] == "new_hash"
        session.close()


class TestDeletePaths:
    """Tests for delete_paths function."""

    def test_delete_existing(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "h1", "b.txt": "h2", "c.txt": "h3"})
        delete_paths(session, ["a.txt", "c.txt"])
        stored = get_stored_hashes(session)
        assert stored == {"b.txt": "h2"}
        session.close()

    def test_delete_empty_list(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "h1"})
        delete_paths(session, [])
        assert get_stored_hashes(session) == {"a.txt": "h1"}
        session.close()


class TestFilterChangedFiles:
    """Tests for filter_changed_files function."""

    def test_all_new_files(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        f = tmp_path / "file.txt"
        f.write_text("content")
        merged = {"file.txt": str(f)}
        changed, hashes = filter_changed_files(session, merged)
        assert "file.txt" in changed
        assert "file.txt" in hashes
        session.close()

    def test_unchanged_files_skipped(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        f = tmp_path / "file.txt"
        f.write_text("content")
        file_hash = compute_file_hash(str(f))
        upsert_hashes(session, {"file.txt": file_hash})
        merged = {"file.txt": str(f)}
        changed, hashes = filter_changed_files(session, merged)
        assert changed == {}
        assert hashes == {"file.txt": file_hash}
        session.close()

    def test_changed_file_detected(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        f = tmp_path / "file.txt"
        f.write_text("old content")
        upsert_hashes(session, {"file.txt": compute_file_hash(str(f))})
        f.write_text("new content")
        merged = {"file.txt": str(f)}
        changed, _ = filter_changed_files(session, merged)
        assert "file.txt" in changed
        session.close()


class TestFindDeletedPaths:
    """Tests for find_deleted_paths function."""

    def test_finds_deleted(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "h1", "b.txt": "h2", "c.txt": "h3"})
        deleted = find_deleted_paths(session, {"a.txt", "c.txt"})
        assert deleted == ["b.txt"]
        session.close()

    def test_no_deletions(self, tmp_path: Path) -> None:
        session = open_hash_db(str(tmp_path / "cache.db"))
        upsert_hashes(session, {"a.txt": "h1"})
        deleted = find_deleted_paths(session, {"a.txt"})
        assert deleted == []
        session.close()
