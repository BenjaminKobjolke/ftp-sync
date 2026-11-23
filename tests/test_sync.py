"""Tests for sync module."""

import os
from pathlib import Path

from config import Settings
from deployignore import load_ignore_file
from run_failures import run_failures
from sync import build_merged_file_map, excluded_paths, get_local_files_recursive, sync_files


def test_sync_files_records_failed_operation(tmp_path: Path) -> None:
    settings = Settings(
        local_directories=(str(tmp_path),),
        ftp_directory="/remote",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
    )

    def operate(args: tuple[str, ...]) -> str:
        if args[0] == "bad.txt":
            raise OSError("upload failed")
        return args[0]

    completed = sync_files(settings, operate, [("bad.txt",), ("good.txt",)])

    assert completed == ["good.txt"]
    assert run_failures.count == 1


def test_sync_files_does_not_record_successful_operations(tmp_path: Path) -> None:
    settings = Settings(
        local_directories=(str(tmp_path),),
        ftp_directory="/remote",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
    )

    completed = sync_files(settings, lambda args: args[0], [("good.txt",)])

    assert completed == ["good.txt"]
    assert run_failures.count == 0


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

    def test_extra_ignore_file_filters_paths_from_all_roots(self, tmp_path: Path) -> None:
        root_one = tmp_path / "root-one"
        root_two = tmp_path / "root-two"
        (root_one / "sub").mkdir(parents=True)
        (root_one / "index.php").write_text("index")
        (root_one / "sub" / "CLAUDE.md").write_text("local notes")
        (root_one / "app" / "tickets").mkdir(parents=True)
        (root_one / "app" / "tickets" / "list.php").write_text("ticket app")
        (root_two / "tickets" / "123").mkdir(parents=True)
        (root_two / "tickets" / "123" / "plan.md").write_text("plan")
        ignore_file = tmp_path / "watcher.ignore"
        ignore_file.write_text("tickets/[0-9]*/\nCLAUDE.md\n")

        patterns = load_ignore_file(str(ignore_file))
        merged = build_merged_file_map((str(root_one), str(root_two)), extra_ignore_patterns=patterns)

        assert "tickets/123/plan.md" not in merged
        assert "sub/CLAUDE.md" not in merged
        assert {"index.php", "app/tickets/list.php"} <= set(merged)

        without_extra_patterns = build_merged_file_map((str(root_one), str(root_two)))
        assert {"tickets/123/plan.md", "sub/CLAUDE.md"} <= set(without_extra_patterns)


class TestGetLocalFilesRecursive:
    """Tests for get_local_files_recursive function."""

    def test_skips_old_directory_by_default(self, tmp_path: Path) -> None:
        (tmp_path / "old").mkdir()
        (tmp_path / "old" / "archived.txt").write_text("archived")
        (tmp_path / "keep.txt").write_text("keep")
        result = get_local_files_recursive(str(tmp_path))
        assert "keep.txt" in result
        assert "old/archived.txt" not in result

    def test_skips_ignore_dirs(self, tmp_path: Path) -> None:
        (tmp_path / "_alt").mkdir()
        (tmp_path / "_alt" / "file.txt").write_text("alt")
        (tmp_path / "Unsortiert").mkdir()
        (tmp_path / "Unsortiert" / "file.txt").write_text("unsorted")
        (tmp_path / "keep.txt").write_text("keep")
        result = get_local_files_recursive(str(tmp_path), ignore_dirs=("_alt", "Unsortiert"))
        assert "keep.txt" in result
        assert "_alt/file.txt" not in result
        assert "Unsortiert/file.txt" not in result

    def test_ignore_dirs_works_at_nested_level(self, tmp_path: Path) -> None:
        sub = tmp_path / "level1" / "_old"
        sub.mkdir(parents=True)
        (sub / "nested.txt").write_text("nested")
        (tmp_path / "level1" / "visible.txt").write_text("visible")
        result = get_local_files_recursive(str(tmp_path), ignore_dirs=("_old",))
        assert "level1/visible.txt" in result
        assert "level1/_old/nested.txt" not in result


class TestExcludedPaths:
    """Tests for paths excluded from local upload by deployignore rules."""

    def test_excludes_path_under_deployignore_directory_pattern(self, tmp_path: Path) -> None:
        (tmp_path / ".deployignore").write_text("data/mcp-tool-cache/\n")

        result = excluded_paths(
            ("data/mcp-tool-cache/x.ser",), (str(tmp_path),), (), ()
        )

        assert result == {"data/mcp-tool-cache/x.ser"}

    def test_excludes_path_matched_by_extra_pattern(self, tmp_path: Path) -> None:
        result = excluded_paths(("private/cache.bin",), (str(tmp_path),), (), ("private/",))

        assert result == {"private/cache.bin"}

    def test_excludes_paths_under_skipped_directory_segments(self, tmp_path: Path) -> None:
        result = excluded_paths(
            ("a/_old/b.txt", "old/archive.txt"), (str(tmp_path),), ("_old",), ()
        )

        assert result == {"a/_old/b.txt", "old/archive.txt"}

    def test_keeps_plain_path_not_matched_by_ignore_rules(self, tmp_path: Path) -> None:
        assert excluded_paths(("index.php",), (str(tmp_path),), (), ()) == set()

    def test_uses_ignore_rules_from_any_local_directory(self, tmp_path: Path) -> None:
        first = tmp_path / "first"
        second = tmp_path / "second"
        first.mkdir()
        second.mkdir()
        (second / ".deployignore").write_text("private/\n")

        result = excluded_paths(("private/cache.bin",), (str(first), str(second)), (), ())

        assert result == {"private/cache.bin"}
