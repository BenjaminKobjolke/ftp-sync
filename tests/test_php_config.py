"""Tests for PHP deploy config parser."""

from pathlib import Path

from php_config import parse_php_config


class TestParsePhpConfig:
    """Tests for parse_php_config."""

    def test_single_entry(self, tmp_path: Path) -> None:
        config = tmp_path / "config_test.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'Test App',
                    'git' => array(
                        'root' => 'https://example.com/repo.git',
                        'ignore' => array('docs/', 'tests/')
                    ),
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
        assert len(entries) == 1
        assert entries[0].name == "Test App"
        assert entries[0].ftp_host == "ftp.example.com"
        assert entries[0].ftp_user == "user"
        assert entries[0].ftp_pass == "pass"
        assert entries[0].ftp_directory == "/www"
        assert entries[0].ignore_patterns == ("docs/", "tests/")

    def test_multiple_entries(self, tmp_path: Path) -> None:
        config = tmp_path / "config_multi.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'App A',
                    'ftp' => array(
                        'root' => '/a',
                        'server' => 'ftp.a.com',
                        'username' => 'ua',
                        'password' => 'pa',
                    )
                ),
                array(
                    'name' => 'App B',
                    'ftp' => array(
                        'root' => '/b',
                        'server' => 'ftp.b.com',
                        'username' => 'ub',
                        'password' => 'pb',
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert len(entries) == 2
        assert entries[0].name == "App A"
        assert entries[1].name == "App B"
        assert entries[0].ftp_directory == "/a"
        assert entries[1].ftp_directory == "/b"

    def test_variable_substitution(self, tmp_path: Path) -> None:
        config = tmp_path / "config_vars.php"
        config.write_text("""<?php
            $ftpServer = 'myhost.com';
            $ftpUser = 'admin';
            $ftpPassword = 'secret123';
            return array(
                array(
                    'name' => 'Var Test',
                    'ftp' => array(
                        'root' => '/',
                        'server' => $ftpServer,
                        'username' => $ftpUser,
                        'password' => $ftpPassword,
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert entries[0].ftp_host == "myhost.com"
        assert entries[0].ftp_user == "admin"
        assert entries[0].ftp_pass == "secret123"

    def test_transfer_type_and_port(self, tmp_path: Path) -> None:
        config = tmp_path / "config_ftps.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'FTPS App',
                    'ftp' => array(
                        'root' => '/',
                        'server' => 'secure.com',
                        'username' => 'u',
                        'password' => 'p',
                        'transferType' => 'FTPS',
                        'port' => 990,
                    )
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert entries[0].transfer_type == "FTPS"
        assert entries[0].ftp_port == 990

    def test_defaults_for_transfer_type_and_port(self, tmp_path: Path) -> None:
        config = tmp_path / "config_defaults.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'Default',
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
        assert entries[0].transfer_type == "FTP"
        assert entries[0].ftp_port == 0

    def test_skips_entry_without_ftp(self, tmp_path: Path) -> None:
        config = tmp_path / "config_noftp.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'No FTP',
                    'git' => array('root' => 'https://example.com/repo.git')
                )
            );
        ?>""")
        entries = parse_php_config(str(config))
        assert len(entries) == 0

    def test_svn_ignore_patterns(self, tmp_path: Path) -> None:
        config = tmp_path / "config_svn.php"
        config.write_text("""<?php
            return array(
                array(
                    'name' => 'SVN App',
                    'svn' => array(
                        'root' => 'https://svn.example.com',
                        'ignore' => array('nbproject/', 'vendor/')
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
        assert entries[0].ignore_patterns == ("nbproject/", "vendor/")

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
