"""Tests for deployignore module."""

from pathlib import Path

from deployignore import DEPLOYIGNORE_FILENAME, filter_ignored_paths, load_deployignore


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
