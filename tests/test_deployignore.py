"""Tests for deployignore module."""

from pathlib import Path

from deployignore import (
    DEPLOYIGNORE_FILENAME,
    ensure_deployignore,
    filter_ignored_paths,
    load_deployignore,
)


class TestLoadDeployignore:
    """Tests for load_deployignore."""

    def test_loads_patterns_from_file(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("docs\n*.log\n")
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file("docs/readme.md")
        assert spec.match_file("error.log")
        assert not spec.match_file("src/main.py")

    def test_strips_whitespace_and_blanks(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("  docs  \n\n  \n*.log\n")
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file("docs/file.txt")
        assert spec.match_file("error.log")

    def test_skips_comment_lines(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("# this is a comment\ndocs\n# another comment\n")
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file("docs/file.txt")
        assert not spec.match_file("src/main.py")

    def test_always_excludes_deployignore(self, tmp_path: Path) -> None:
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file(DEPLOYIGNORE_FILENAME)

    def test_returns_default_when_no_file(self, tmp_path: Path) -> None:
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file(DEPLOYIGNORE_FILENAME)
        assert not spec.match_file("src/main.py")


class TestEnsureDeployignore:
    """Tests for ensure_deployignore."""

    def test_creates_default_file_when_missing(self, tmp_path: Path) -> None:
        created = ensure_deployignore(str(tmp_path))
        assert created is True
        content = (tmp_path / DEPLOYIGNORE_FILENAME).read_text(encoding="utf-8")
        assert ".git/" in content

    def test_does_not_overwrite_existing_file(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("custom\n")
        created = ensure_deployignore(str(tmp_path))
        assert created is False
        assert ignore_file.read_text() == "custom\n"

    def test_default_patterns_match_expected_paths(self, tmp_path: Path) -> None:
        ensure_deployignore(str(tmp_path))
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file(".git/config")
        assert spec.match_file("node_modules/pkg/index.js")
        assert spec.match_file("sub/__pycache__/mod.pyc")
        assert spec.match_file(".env")
        assert spec.match_file(".DS_Store")
        assert spec.match_file("claude-plans/plan.md")
        assert spec.match_file("tests/test_foo.php")
        assert spec.match_file("CLAUDE.md")
        assert spec.match_file("config.php")
        assert spec.match_file(".gitignore")
        assert not spec.match_file("src/main.py")
        assert not spec.match_file("index.php")

    def test_root_only_vs_any_depth_folders(self, tmp_path: Path) -> None:
        ensure_deployignore(str(tmp_path))
        spec = load_deployignore(str(tmp_path))
        assert spec.match_file("tools/build.bat")
        assert not spec.match_file("src/tools/helper.py")
        assert not spec.match_file("module/tests/test_x.php")
        assert spec.match_file("sub/__pycache__/mod.pyc")
        assert spec.match_file("vendor/pkg/.git/config")
        assert spec.match_file("sub/tmp/cache.txt")
        assert spec.match_file("sub/graphify-out/graph.json")
        assert spec.match_file("sub/claude-plans/plan.md")
        assert spec.match_file("sub/code_analysis_results/report.md")
        assert spec.match_file("sub/.claude/settings.json")


class TestFilterIgnoredPaths:
    """Tests for filter_ignored_paths."""

    def test_filters_matching_paths(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("docs\n*.log\n")
        spec = load_deployignore(str(tmp_path))
        paths = ["src/main.py", "docs/readme.md", "error.log", "lib/utils.py"]
        result = filter_ignored_paths(paths, spec)
        assert result == ["src/main.py", "lib/utils.py"]

    def test_empty_spec_returns_all(self, tmp_path: Path) -> None:
        spec = load_deployignore(str(tmp_path))
        paths = ["src/main.py", "lib/utils.py"]
        result = filter_ignored_paths(paths, spec)
        assert result == paths

    def test_prefix_directory_match(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("wp-content/themes/xida2k19/docs\n")
        spec = load_deployignore(str(tmp_path))
        paths = [
            "wp-content/themes/xida2k19/docs/guide.md",
            "wp-content/themes/xida2k19/style.css",
            "index.php",
        ]
        result = filter_ignored_paths(paths, spec)
        assert result == ["wp-content/themes/xida2k19/style.css", "index.php"]

    def test_exact_filename_match(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("install.ahk\nnul\n")
        spec = load_deployignore(str(tmp_path))
        paths = ["install.ahk", "nul", "main.py", "sub/nul"]
        result = filter_ignored_paths(paths, spec)
        assert result == ["main.py"]

    def test_wildcard_pattern(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("*.pyc\n")
        spec = load_deployignore(str(tmp_path))
        paths = ["main.pyc", "sub/util.pyc", "main.py"]
        result = filter_ignored_paths(paths, spec)
        assert result == ["main.py"]

    def test_negation_pattern(self, tmp_path: Path) -> None:
        ignore_file = tmp_path / DEPLOYIGNORE_FILENAME
        ignore_file.write_text("*.log\n!important.log\n")
        spec = load_deployignore(str(tmp_path))
        paths = ["error.log", "important.log", "main.py"]
        result = filter_ignored_paths(paths, spec)
        assert result == ["important.log", "main.py"]
