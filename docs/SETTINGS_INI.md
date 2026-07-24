# Settings INI reference

All settings live in a single `[FTP]` section of the INI file passed as the first CLI argument
(see `settings_example.ini` and `examples/*.ini` for full working configs). Parsed and validated
in `load_settings()` (`config.py`).

## Required

| Key | Description |
|-----|--------------|
| `FTP_HOST` | FTP/FTPS server hostname or IP |
| `FTP_USER` | Login username |
| `FTP_PASS` | Login password. Never commit an INI file with a real password. |

## Optional

| Key | Default | Description |
|-----|---------|--------------|
| `LOCAL_DIRECTORY` | *(empty)* | Local folder to sync. Comma-separated for multiple sources — **only valid when `DIRECTION = up`** (`config.py:76`); a comma-separated list with `DIRECTION = down` raises an error. Can be overridden with `--local-dir` / `-l`. |
| `FTP_DIRECTORY` | *(empty)* | Remote base path on the FTP server. Can be overridden with `--ftp-dir` / `-f`. |
| `DIRECTION` | `down` | `down` = FTP → local, `up` = local → FTP. |
| `TRANSFER_TYPE` | `FTP` | `FTP` or `FTPS` (FTP over TLS). Invalid values raise an error. FTPS resumes the control channel's TLS session on data connections (see `_ReusedTLSSession` in `ftp_ops.py`), which servers hardened with SSL-session-reuse requirements (e.g. FileZilla Server, vsftpd `require_ssl_reuse`) demand — without it, data transfers fail with `425 ... TLS session of data connection not resumed`. |
| `FTP_PORT` | `0` | Custom port, set per job for non-standard servers. `0` means use the protocol default (21). Passed straight to `ftplib` in `connect_ftp()` (`ftp_ops.py`). |
| `CONCURRENT_UPLOADS_OR_DOWNLOADS` | `1` | Number of concurrent transfer workers. Must be `>= 1`. |
| `IGNORE_DIRS` | *(none)* | Comma-separated directory *names* skipped everywhere, e.g. `IGNORE_DIRS = _old, _alt, Unsortiert`. The `old` directory is always skipped automatically. For gitignore-style path patterns, use `.deployignore` instead — see [DEPLOYIGNORE.md](DEPLOYIGNORE.md). |
| `HASH_CACHE_FILE` | *(empty)* | Path to a SQLite hash cache DB (upload direction only). When set, skips scanning the FTP server and uploads only files whose content hash changed. Can be overridden with `--hash-cache-file`. |
| `DELETE_SOURCE_AFTER_DAYS` | `0` | When `DIRECTION = down`, deletes files from the FTP server older than N days after a successful sync. `0` disables. Not yet supported for `DIRECTION = up`. Must be `>= 0`. Can be overridden with `--delete-source-after-days`. |
| `NO_DELETE` | `false` | Upload direction only: never delete remote files that are absent locally (keeps stray remote files). Can be forced on with `--no-delete`. |

## CLI overrides

Some settings can be overridden per run without editing the INI file, via `apply_overrides()`
(`config.py`):

| Flag | Overrides |
|------|-----------|
| `--local-dir`, `-l` | `LOCAL_DIRECTORY` |
| `--ftp-dir`, `-f` | `FTP_DIRECTORY` |
| `--delete-source-after-days` | `DELETE_SOURCE_AFTER_DAYS` |
| `--hash-cache-file` | `HASH_CACHE_FILE` |
| `--no-delete` | `NO_DELETE` (forces `true`) |
| `--resync` | not an INI setting — clears the hash cache DB before syncing |
| `--watcher`, `-w` | not an INI setting — watches `LOCAL_DIRECTORY` for changes and re-syncs automatically |

## Example: custom port per job

```ini
[FTP]
LOCAL_DIRECTORY = c:\project_a
FTP_DIRECTORY = /data
FTP_HOST = server.com
FTP_USER = user
FTP_PASS = password
FTP_PORT = 2121
```

Each INI file is a separate job, so different jobs can use different ports on the same or
different hosts.

## Debugging connection failures

Set the `FTP_SYNC_DEBUG=1` environment variable to dump the raw FTP control conversation
(commands, responses, AUTH/PROT/PASV negotiation) to stdout — useful when a sync fails with
an FTP or TLS error and the reason isn't obvious from the summary log line.
