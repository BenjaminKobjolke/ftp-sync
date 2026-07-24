"""Tests for FTP connection setup."""

import ftplib
import ssl
from unittest.mock import MagicMock, patch

from config import Settings
from ftp_ops import _make_ftps_context, _ReusedTLSSession, connect_ftp


def _make_settings(*, transfer_type: str = "FTP", ftp_port: int = 0) -> Settings:
    return Settings(
        local_directories=("C:\\backup",),
        ftp_directory="/remote",
        ftp_host="host",
        ftp_user="user",
        ftp_pass="pass",
        transfer_type=transfer_type,
        ftp_port=ftp_port,
    )


class TestReusedTLSSession:
    """Tests for the require_ssl_reuse-compatible FTP_TLS subclass."""

    def test_subclasses_ftp_tls(self) -> None:
        assert issubclass(_ReusedTLSSession, ftplib.FTP_TLS)

    def test_overrides_ntransfercmd(self) -> None:
        assert _ReusedTLSSession.ntransfercmd is not ftplib.FTP_TLS.ntransfercmd

    def test_wraps_data_socket_with_control_session_when_protected(self) -> None:
        session = _ReusedTLSSession.__new__(_ReusedTLSSession)
        session._data_protected = True
        session.host = "host"
        session.sock = MagicMock(spec=ssl.SSLSocket)
        session.context = MagicMock()
        raw_conn = MagicMock()
        wrapped_conn = MagicMock()
        session.context.wrap_socket.return_value = wrapped_conn

        with patch.object(ftplib.FTP, "ntransfercmd", return_value=(raw_conn, 123)):
            conn, size = session.ntransfercmd("RETR foo")

        session.context.wrap_socket.assert_called_once_with(
            raw_conn, server_hostname="host", session=session.sock.session
        )
        assert conn is wrapped_conn
        assert size == 123

    def test_leaves_data_socket_alone_when_not_protected(self) -> None:
        session = _ReusedTLSSession.__new__(_ReusedTLSSession)
        session._data_protected = False
        session.context = MagicMock()
        raw_conn = MagicMock()

        with patch.object(ftplib.FTP, "ntransfercmd", return_value=(raw_conn, None)):
            conn, size = session.ntransfercmd("RETR foo")

        session.context.wrap_socket.assert_not_called()
        assert conn is raw_conn
        assert size is None

    def test_prot_p_marks_data_channel_protected(self) -> None:
        session = _ReusedTLSSession.__new__(_ReusedTLSSession)
        session._data_protected = False

        with patch.object(ftplib.FTP_TLS, "prot_p", return_value="200 Protection level set to P"):
            session.prot_p()

        assert session._data_protected is True


class TestMakeFtpsContext:
    """Tests for the FTPS SSL context used by _ReusedTLSSession."""

    def test_does_not_verify_certificates(self) -> None:
        # Matches ftplib.FTP_TLS's own default context (ssl._create_stdlib_context):
        # unverified, since most FTPS servers use self-signed certs.
        context = _make_ftps_context()
        assert context.check_hostname is False
        assert context.verify_mode == ssl.CERT_NONE


class TestConnectFtp:
    """Tests for connect_ftp."""

    def test_ftps_uses_reused_tls_session(self) -> None:
        settings = _make_settings(transfer_type="FTPS", ftp_port=2199)
        with (
            patch.object(_ReusedTLSSession, "connect") as mock_connect,
            patch.object(_ReusedTLSSession, "login") as mock_login,
            patch.object(_ReusedTLSSession, "prot_p") as mock_prot_p,
        ):
            ftp = connect_ftp(settings)

        assert isinstance(ftp, _ReusedTLSSession)
        mock_connect.assert_called_once_with("host", 2199)
        mock_login.assert_called_once_with("user", "pass")
        mock_prot_p.assert_called_once()

    def test_plain_ftp_uses_default_port(self) -> None:
        settings = _make_settings(transfer_type="FTP")
        with patch.object(ftplib.FTP, "connect") as mock_connect, patch.object(ftplib.FTP, "login") as mock_login:
            ftp = connect_ftp(settings)

        assert type(ftp) is ftplib.FTP
        mock_connect.assert_called_once_with("host", 21)
        mock_login.assert_called_once_with("user", "pass")
