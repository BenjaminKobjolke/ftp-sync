"""Tests for sync module."""

import os
from pathlib import Path

from sync import build_merged_file_map


class TestBuildMergedFileMap:
    """Tests for build_merged_file_map function."""

    def test_single_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "src"
        d.mkdir()
        (d / "file.txt").write_text("hello")
        result = build_merged_file_map((str(d),))
        assert "file.txt" in result
        assert result["file.txt"] == str(d / "file.txt")

    def test_newer_file_wins(self, tmp_path: Path) -> None:
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        f1 = d1 / "file.txt"
        f2 = d2 / "file.txt"
        f1.write_text("old")
        f2.write_text("new")
        os.utime(str(f1), (1000, 1000))
        os.utime(str(f2), (2000, 2000))
        result = build_merged_file_map((str(d1), str(d2)))
        assert result["file.txt"] == str(f2)

    def test_union_of_files(self, tmp_path: Path) -> None:
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        (d1 / "a.txt").write_text("a")
        (d2 / "b.txt").write_text("b")
        result = build_merged_file_map((str(d1), str(d2)))
        assert set(result.keys()) == {"a.txt", "b.txt"}

    def test_subdirectories_included(self, tmp_path: Path) -> None:
        d = tmp_path / "src"
        sub = d / "sub"
        sub.mkdir(parents=True)
        (sub / "nested.txt").write_text("content")
        result = build_merged_file_map((str(d),))
        assert "sub/nested.txt" in result

    def test_empty_directory(self, tmp_path: Path) -> None:
        d = tmp_path / "empty"
        d.mkdir()
        result = build_merged_file_map((str(d),))
        assert result == {}
