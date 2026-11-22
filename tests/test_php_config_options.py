"""Tests for preset and optional values in PHP deploy configs."""

from pathlib import Path

from php_config import parse_php_config


class TestParsePhpConfig:
    def test_preset_merging(self, tmp_path: Path) -> None:
        preset = tmp_path / "preset_base.php"
        preset.write_text("""<?php
            return array(
                'name' => 'Base Name',
                'ftp' => array(
                    'root' => '/default',
                    'server' => 'base.com',
                    'username' => 'baseuser',
                    'password' => 'basepass',
                )
            );
        ?>""")
        config = tmp_path / "config_with_preset.php"
        config.write_text("""<?php
            return array(
                array(
                    'preset' => 'base',
                    'name' => 'Override Name',
                    'ftp' => array(
                        'root' => '/custom',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert len(entries) == 1
        assert entries[0].name == "Override Name"
        assert entries[0].ftp_directory == "/custom"
        assert entries[0].ftp_host == "base.com"
        assert entries[0].ftp_user == "baseuser"

    def test_preset_not_found_still_parses(self, tmp_path: Path) -> None:
        config = tmp_path / "config_missing_preset.php"
        config.write_text("""<?php
            return array(
                array(
                    'preset' => 'nonexistent',
                    'name' => 'App',
                    'ftp' => array(
                        'root' => '/',
                        'server' => 'host',
                        'username' => 'u',
                        'password' => 'p',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert len(entries) == 1
        assert entries[0].name == "App"

    def test_boolean_values(self, tmp_path: Path) -> None:
        config = tmp_path / "config_bools.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'Bool Test',
                    'verbose' => true,
                    'debug' => false,
                    'ftp' => array(
                        'root' => '/',
                        'server' => 'host',
                        'username' => 'u',
                        'password' => 'p',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert len(entries) == 1
        assert entries[0].name == "Bool Test"

    def test_subfolder_parsed(self, tmp_path: Path) -> None:
        config = tmp_path / "config_sub.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'Subfolder App',
                    'git' => array(
                        'root' => 'https://example.com/repo.git',
                        'subfolder' => 'wp-content/themes/mytheme',
                        'ignore' => array('docs/')
                    ),
                    'ftp' => array(
                        'root' => '/wp-content/themes/mytheme',
                        'server' => 'host',
                        'username' => 'u',
                        'password' => 'p',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert entries[0].subfolder == "wp-content/themes/mytheme"

    def test_empty_subfolder_defaults(self, tmp_path: Path) -> None:
        config = tmp_path / "config_nosub.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'No Sub',
                    'git' => array(
                        'root' => 'https://example.com/repo.git',
                        'subfolder' => ''
                    ),
                    'ftp' => array(
                        'root' => '/',
                        'server' => 'host',
                        'username' => 'u',
                        'password' => 'p',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert entries[0].subfolder == ""

    def test_version_file_is_parsed_from_entry(self, tmp_path: Path) -> None:
        config = tmp_path / "config_version.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'Versioned App',
                    'version_file' => 'custom.ver',
                    'ftp' => array(
                        'root' => '/www',
                        'server' => 'ftp.example.com',
                        'username' => 'user',
                        'password' => 'pass',
                    )
                )
            );
        ?>""")

        entries = parse_php_config(str(config))

        assert entries[0].version_file == "custom.ver"

    def test_version_file_defaults_when_missing_or_empty(self, tmp_path: Path) -> None:
        for name, setting in (("missing", ""), ("empty", "'version_file' => '',")):
            config = tmp_path / f"config_version_{name}.php"
            config.write_text(f"""<?php
                return array(
                    array(
                        'name' => 'Versioned App',
                        {setting}
                        'ftp' => array(
                            'root' => '/www',
                            'server' => 'ftp.example.com',
                            'username' => 'user',
                            'password' => 'pass',
                        )
                    )
                );
            ?>""")

            assert parse_php_config(str(config))[0].version_file == "deploy.ver"
