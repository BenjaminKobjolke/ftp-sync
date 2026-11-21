"""Shared settings factories for tests of the main sync entry point."""

from pathlib import Path

from config import Settings


def make_settings(tmp_path: Path, hash_cache_file: str) -> Settings:
    return Settings(
        local_directories=(str(tmp_path),),
        ftp_directory="/",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
        direction="up",
        hash_cache_file=hash_cache_file,
    )


def write_ini(path: Path, local: Path) -> Path:
    ini = path / "settings.ini"
    ini.write_text(
        "[FTP]\n"
        f"LOCAL_DIRECTORY = {local}\n"
        "FTP_DIRECTORY = /remote\n"
        "FTP_HOST = host\n"
        "FTP_USER = user\n"
        "FTP_PASS = pass\n"
        "DIRECTION = up\n"
    )
    return ini
