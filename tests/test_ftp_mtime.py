"""Tests for FTP modification time retrieval and old file deletion."""

import datetime
import ftplib
from unittest.mock import MagicMock, patch

from config import Settings
from ftp_ops import _parse_mdtm_response, delete_old_ftp_files, get_ftp_file_mtimes


def _make_settings() -> Settings:
    return Settings(
        local_directories=("C:\\backup",),
        ftp_directory="/remote",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
    )


class TestParseMdtmResponse:
    """Tests for _parse_mdtm_response."""

    def test_valid_response(self) -> None:
        result = _parse_mdtm_response("213 20240115143022")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 22, tzinfo=datetime.UTC)

    def test_fractional_seconds_stripped(self) -> None:
        result = _parse_mdtm_response("213 20240115143022.123")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 22, tzinfo=datetime.UTC)

    def test_invalid_code(self) -> None:
        assert _parse_mdtm_response("550 No such file") is None

    def test_missing_timestamp(self) -> None:
        assert _parse_mdtm_response("213") is None

    def test_malformed_timestamp(self) -> None:
        assert _parse_mdtm_response("213 notadate") is None

    def test_empty_string(self) -> None:
        assert _parse_mdtm_response("") is None


class TestGetFtpFileMtimes:
    """Tests for get_ftp_file_mtimes."""

    def test_returns_mtimes_for_valid_files(self) -> None:
        ftp = MagicMock(spec=ftplib.FTP)
        ftp.sendcmd.return_value = "213 20240115143022"
        settings = _make_settings()

        result = get_ftp_file_mtimes(ftp, settings, ["file1.txt", "file2.txt"])

        assert len(result) == 2
        assert result["file1.txt"] == datetime.datetime(
            2024, 1, 15, 14, 30, 22, tzinfo=datetime.UTC
        )

    def test_skips_files_with_perm_error(self) -> None:
        ftp = MagicMock(spec=ftplib.FTP)
        ftp.sendcmd.side_effect = [
            "213 20240115143022",
            ftplib.error_perm("550 Not found"),
        ]
        settings = _make_settings()

        result = get_ftp_file_mtimes(ftp, settings, ["good.txt", "bad.txt"])

        assert len(result) == 1
        assert "good.txt" in result

    def test_empty_file_list(self) -> None:
        ftp = MagicMock(spec=ftplib.FTP)
        settings = _make_settings()

        result = get_ftp_file_mtimes(ftp, settings, [])

        assert result == {}
        ftp.sendcmd.assert_not_called()


class TestDeleteOldFtpFiles:
    """Tests for delete_old_ftp_files."""

    @patch("ftp_ops.remove_empty_ftp_dirs")
    @patch("ftp_ops.delete_ftp_file")
    @patch("ftp_ops.get_ftp_file_mtimes")
    def test_deletes_only_old_files(
        self,
        mock_mtimes: MagicMock,
        mock_delete: MagicMock,
        mock_remove_dirs: MagicMock,
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)
        mock_mtimes.return_value = {
            "old.txt": now - datetime.timedelta(days=60),
            "recent.txt": now - datetime.timedelta(days=5),
        }
        mock_delete.return_value = True
        settings = _make_settings()
        ftp = MagicMock(spec=ftplib.FTP)

        result = delete_old_ftp_files(ftp, settings, ["old.txt", "recent.txt"], 30)

        assert result == 1
        mock_delete.assert_called_once_with(ftp, settings, "old.txt")
        mock_remove_dirs.assert_called_once()

    @patch("ftp_ops.get_ftp_file_mtimes")
    def test_no_files_deleted_when_all_recent(
        self,
        mock_mtimes: MagicMock,
    ) -> None:
        now = datetime.datetime.now(datetime.UTC)
        mock_mtimes.return_value = {
            "file1.txt": now - datetime.timedelta(days=5),
            "file2.txt": now - datetime.timedelta(days=10),
        }
        settings = _make_settings()
        ftp = MagicMock(spec=ftplib.FTP)

        result = delete_old_ftp_files(ftp, settings, ["file1.txt", "file2.txt"], 30)

        assert result == 0

    @patch("ftp_ops.get_ftp_file_mtimes")
    def test_returns_zero_when_no_mtimes(
        self,
        mock_mtimes: MagicMock,
    ) -> None:
        mock_mtimes.return_value = {}
        settings = _make_settings()
        ftp = MagicMock(spec=ftplib.FTP)

        result = delete_old_ftp_files(ftp, settings, ["file.txt"], 30)

        assert result == 0
