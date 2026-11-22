"""Tests for PHP deploy entry settings and cache paths."""

import dataclasses
from pathlib import Path

from config import entry_hash_cache_file, settings_from_php_entry
from php_config import PhpDeployEntry


def _entry(host: str, directory: str = "/api/vendor") -> PhpDeployEntry:
    return PhpDeployEntry(
        name=host, ftp_host=host, ftp_user="user", ftp_pass="pass", ftp_directory=directory, ignore_patterns=()
    )


class TestEntryHashCacheFile:
    """Tests for the per-entry hash cache path of multi-entry PHP configs."""

    BASE = str(Path("caches") / "vendor.db")

    def test_single_entry_keeps_base(self) -> None:
        assert entry_hash_cache_file(self.BASE, _entry("a.example.com"), 1) == self.BASE

    def test_entries_on_different_hosts_get_different_files(self) -> None:
        first = Path(entry_hash_cache_file(self.BASE, _entry("a.example.com"), 2))
        second = Path(entry_hash_cache_file(self.BASE, _entry("b.example.com"), 2))
        assert first != second
        assert first.parent == second.parent == Path(self.BASE).parent
        assert first.suffix == second.suffix == ".db"

    def test_same_host_different_directory_get_different_files(self) -> None:
        first = entry_hash_cache_file(self.BASE, _entry("a.example.com", "/v1/vendor"), 2)
        second = entry_hash_cache_file(self.BASE, _entry("a.example.com", "/v2/vendor"), 2)
        assert first != second

    def test_name_is_filename_safe(self) -> None:
        name = Path(entry_hash_cache_file(self.BASE, _entry("a.example.com:2121", "/api/v 1/vendor"), 2)).name
        assert name == "vendor_a.example.com_2121_api_v_1_vendor.db"


class TestSettingsFromPhpEntry:
    def test_maps_version_file_from_php_entry(self) -> None:
        entry = dataclasses.replace(_entry("host"), version_file="custom.ver")

        settings = settings_from_php_entry(entry, ("local",))

        assert settings.version_file == "custom.ver"

    def test_defaults_version_file_for_php_entry(self) -> None:
        settings = settings_from_php_entry(_entry("host"), ("local",))

        assert settings.version_file == "deploy.ver"

def test_settings_from_php_entry_passes_verify_remote() -> None:
    settings = settings_from_php_entry(_entry("server.com"), ("local",), "cache.db", verify_remote=True)
    assert settings.verify_remote is True
    assert settings_from_php_entry(_entry("server.com"), ("local",)).verify_remote is False


def test_settings_from_php_entry_uses_concurrent_uploads() -> None:
    default_settings = settings_from_php_entry(_entry("server.com"), ("local",))
    parallel_entry = dataclasses.replace(_entry("server.com"), concurrent_uploads=4)

    assert default_settings.concurrent_operations == 1
    assert settings_from_php_entry(parallel_entry, ("local",)).concurrent_operations == 4


