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
- **`.deployignore`** — gitignore-style file placed in synced directories to exclude files/folders from sync
- **PHP deploy config** — supports PHP config files from the deploy-tool (alternative to INI files)
- **FTP and FTPS** — plain FTP and FTPS (FTP over TLS) connections
- **Watcher mode** — `--watcher` watches local files for changes and auto-syncs to FTP (2s debounce)
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
uv run python main.py <settings_file> [--local-dir <path>] [--ftp-dir <path>] [--resync] [--watcher]
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

Watch for changes and auto-sync:
```
uv run python main.py settings.ini --watcher
uv run python main.py config_myapp.php --local-dir ./myproject --watcher
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

### PHP deploy config format

As an alternative to INI files, you can use PHP config files from the deploy-tool. See `tools/config_example.php` for the format.

```
uv run python main.py config_myapp.php --local-dir "C:\my\local\folder"
```

- `--local-dir` is required when using a PHP config
- All entries in the config are processed sequentially
- Ignore patterns from `git.ignore` / `svn.ignore` are applied automatically
- Supports FTP and FTPS transfer types (SFTP is not supported)
- Preset inheritance is supported via `preset_<name>.php` files in the same directory

### `.deployignore`

Place a `.deployignore` file in the root of any synced directory to exclude files and folders. Uses `.gitignore` syntax:

```
# Exclude docs and test files
docs/
tests/
*.log

# But keep important.log
!important.log
```

The `.deployignore` file itself is always excluded from sync. Patterns from `.deployignore` are combined with ignore patterns from PHP config files when both are present.

## Development

```bash
# Initial setup
install.bat

# Run tests
tools\run_tests.bat

# Update dependencies
update.bat
```
