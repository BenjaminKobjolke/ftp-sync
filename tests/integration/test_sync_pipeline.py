"""Integration tests for the local sync pipeline.

Exercises several modules together on a real temporary filesystem — config
loading (``config.load_settings``), ``.deployignore`` filtering
(``deployignore``), and merged file-map building (``sync.build_merged_file_map``)
— without contacting a real FTP server.
"""

from pathlib import Path

from config import load_settings
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
