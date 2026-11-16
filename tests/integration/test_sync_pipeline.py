"""Integration tests for the local sync pipeline.

Exercises several modules together on a real temporary filesystem — config
loading (``config.load_settings``), ``.deployignore`` filtering
(``deployignore``), and merged file-map building (``sync.build_merged_file_map``)
— without contacting a real FTP server.
"""

from pathlib import Path

import pytest

from config import load_settings, parse_arguments
from deployignore import ensure_deployignore, load_ignore_file
from sync import build_merged_file_map


def _write_ini(tmp_path: Path, local_dir: Path) -> Path:
    ini_file = tmp_path / "settings.ini"
    ini_file.write_text(
        "[FTP]\n"
        f"LOCAL_DIRECTORY = {local_dir}\n"
        "FTP_DIRECTORY = /remote\n"
        "FTP_HOST = ftp.example.com\n"
        "FTP_USER = admin\n"
        "FTP_PASS = secret\n"
        "DIRECTION = up\n"
    )
    return ini_file


class TestLocalSyncPipeline:
    """End-to-end: INI settings drive a deployignore-filtered merged file map."""

    def test_merged_map_respects_settings_and_deployignore(self, tmp_path: Path) -> None:
        local_dir = tmp_path / "project"
        (local_dir / "src").mkdir(parents=True)
        (local_dir / "src" / "app.py").write_text("print('hi')")
        (local_dir / "keep.txt").write_text("keep me")
        (local_dir / "secret.log").write_text("ignore me")
        (local_dir / ".deployignore").write_text("*.log\n")

        settings = load_settings(str(_write_ini(tmp_path, local_dir)))

        merged = build_merged_file_map(
            settings.local_directories,
            settings.ignore_dirs,
        )

        assert "src/app.py" in merged
        assert "keep.txt" in merged
        assert "secret.log" not in merged  # excluded by .deployignore
        assert merged["keep.txt"].endswith("keep.txt")

    def test_newest_file_wins_across_directories(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        (dir_a / "shared.txt").write_text("old")
        newer = dir_b / "shared.txt"
        newer.write_text("new")
        # Force dir_b copy to be newer than dir_a copy.
        import os

        os.utime(dir_a / "shared.txt", (1_000_000_000, 1_000_000_000))
        os.utime(newer, (2_000_000_000, 2_000_000_000))

        merged = build_merged_file_map((str(dir_a), str(dir_b)))

        assert merged["shared.txt"] == os.path.join(str(dir_b), "shared.txt")

    def test_environment_ignore_file_filters_automation_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local_dir = tmp_path / "project"
        (local_dir / "tickets" / "5").mkdir(parents=True)
        (local_dir / "index.php").write_text("app")
        (local_dir / "CODING_RULES.md").write_text("local rules")
        (local_dir / "tickets" / "5" / "ticket.md").write_text("local ticket")
        ensure_deployignore(str(local_dir))

        ignore_file = tmp_path / "automation.ignore"
        ignore_file.write_text("CODING_RULES*.md\ntickets/[0-9]*/\n")
        monkeypatch.setenv("FTP_SYNC_IGNORE_FILE", str(ignore_file))
        monkeypatch.setattr("sys.argv", ["main.py", "settings.ini"])
        args = parse_arguments()
        patterns = load_ignore_file(args.ignore_file)

        merged = build_merged_file_map((str(local_dir),), extra_ignore_patterns=patterns)

        assert "index.php" in merged
        assert "CODING_RULES.md" not in merged
        assert "tickets/5/ticket.md" not in merged
