# ftp-sync

Sync a local folder with an FTP folder. Supports both download and upload directions with concurrent operations and recursive subfolder syncing.

## Features

- **Bidirectional sync** — download from FTP to local (`down`) or upload from local to FTP (`up`)
- **Recursive subfolder sync** — syncs all files and subdirectories, creating missing directories automatically
- **Concurrent operations** — configurable number of parallel uploads/downloads
- **Skip unchanged files** — files with matching sizes are skipped (legacy mode), or via local SHA-256 hash cache (hash mode)
- **Hash-based change detection** — optional SQLite cache tracks file hashes locally, skipping FTP scanning entirely and only uploading files whose content actually changed
- **Old file handling** — when downloading, local files no longer on the server are moved to an `old` subfolder
- **Multi-directory upload** — sync multiple local folders into one FTP directory (newer file wins on conflicts)
- **FTP deletion** — files removed from all local folders are deleted from FTP (upload mode)
- **Ignore directories** — configurable list of directory names to skip during sync (both directions)
- **Resync** — `--resync` flag clears the hash cache to force a full re-upload
- **CLI overrides** — override `LOCAL_DIRECTORY` and `FTP_DIRECTORY` from the command line
- **Auto-create FTP directories** — target FTP directory is created if it does not exist

## Install

- Make sure you have Python 3.11+ installed
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Run `install.bat` or `uv sync --all-extras`
- Copy `settings_example.ini` and fill in the required fields

## Usage

```
uv run python main.py <settings_file> [--local-dir <path>] [--ftp-dir <path>] [--resync]
```

### Examples

Basic usage with INI file:
```
uv run python main.py settings.ini
```

Override directories via CLI:
```
uv run python main.py settings.ini --local-dir "C:\my\local\folder" --ftp-dir "/remote/path"
```

Force full re-upload by clearing the hash cache:
```
uv run python main.py settings.ini --resync
```

### INI file format

```ini
[FTP]
LOCAL_DIRECTORY = c:\ftp_backup
FTP_DIRECTORY = /remote/path
FTP_HOST = server.com
FTP_USER = user
FTP_PASS = password

# Direction of sync: down = FTP to local, up = local to FTP
DIRECTION = down

# Number of concurrent uploads or downloads (default: 1)
CONCURRENT_UPLOADS_OR_DOWNLOADS = 1

# Comma-separated directory names to skip during sync (default: none)
# The 'old' directory is always skipped automatically
# IGNORE_DIRS = _old, _alt, _before_2023, Unsortiert

# Path to SQLite hash cache file for tracking local file changes (upload only)
# When set, skips FTP scanning and only uploads files whose content has changed
# HASH_CACHE_FILE = c:\ftp_backup\.ftp_sync_cache.db
```

`LOCAL_DIRECTORY` and `FTP_DIRECTORY` are optional in the INI file if provided via `--local-dir` / `--ftp-dir` CLI arguments.

## Development

```bash
# Initial setup
install.bat

# Run tests
tools\run_tests.bat

# Update dependencies
update.bat
```
