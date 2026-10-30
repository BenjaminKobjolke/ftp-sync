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
- **Clear remote dirs after upload** — `CLEAR_REMOTE_DIRS` / `clearAfterUpload` empties configured remote folders (e.g. server-side caches) after each upload, keeping the folders themselves
- **No-delete upload** — `--no-delete` / `NO_DELETE` uploads and updates files but never deletes remote files absent locally (keeps existing remote files)
- **Verify remote** — `--verify-remote` / `VERIFY_REMOTE` (hash-cache upload) lists the server first and re-uploads files that changed or went missing there. The hash cache alone only knows what this machine uploaded, so a file overwritten from elsewhere (another machine, another cache, a manual upload) would otherwise be skipped forever, even when it has the same size
- **Ignore directories** — configurable list of directory names to skip during sync (both directions)
- **`.deployignore`** — gitignore-style file placed in synced directories to exclude files/folders from sync
- **PHP deploy config** — supports PHP config files from the deploy-tool (alternative to INI files)
- **FTP and FTPS** — plain FTP and FTPS (FTP over TLS) connections
- **Watcher mode** — `--watcher` watches local files for changes and auto-syncs to FTP (2s debounce)
- **Compare mode** — `--compare <file>` writes a read-only report of remote files missing or different locally
- **Source retention cleanup** — optionally delete source files older than N days after sync (e.g., download from FTP, then purge FTP files older than 30 days)
- **Resync** — `--resync` flag clears the hash cache to force a full re-upload
- **CLI overrides** — override `LOCAL_DIRECTORY`, `FTP_DIRECTORY`, and `HASH_CACHE_FILE` from the command line
- **Auto-create FTP directories** — target FTP directory is created if it does not exist

## Install

- Make sure you have Python 3.11+ installed
- Install [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Run `install.bat` or `uv sync --all-extras`
- Copy `settings_example.ini` and fill in the required fields

## Usage

```
uv run python main.py <settings_file> [--local-dir <path>] [--ftp-dir <path>] [--hash-cache-file <path>] [--compare <output file>] [--resync] [--watcher] [--delete-source-after-days N] [--no-delete] [--verify-remote]
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

Download and delete FTP files older than 30 days:
```
uv run python main.py settings.ini --delete-source-after-days 30
```

Force full re-upload by clearing the hash cache:
```
uv run python main.py settings.ini --resync
```

Upload without deleting remote files that are absent locally (additive upload):
```
uv run python main.py settings.ini --no-delete
```

Hash-cache upload that also re-uploads files changed or missing on the server (works with PHP configs too):
```
uv run python main.py config_myapp_vendor.php --local-dir ./vendor --hash-cache-file ./deploy/vendor.db --verify-remote
```
The first run with an older cache adopts the server's timestamps for files whose size matches, and re-uploads the ones whose size differs.

Use a custom hash cache file location (overrides `HASH_CACHE_FILE` from INI):
```
uv run python main.py settings.ini --hash-cache-file "C:\caches\app-vendor.db"
```

Compare the remote tree with the first `LOCAL_DIRECTORY` and write differences as they are found:
```
uv run python main.py settings.ini --compare gaps.tsv
```

### Compare mode

Compare mode walks `FTP_DIRECTORY` and checks files against the first `LOCAL_DIRECTORY`. It honors
`IGNORE_DIRS`; it does not apply `.deployignore`. It is read-only: it does not upload, download,
delete, or create local or remote directories. The server must support MLSD listings.

The UTF-8 output file is overwritten and written line by line, so findings remain available if
the run stops early. Each finding is tab-separated:

- `MISSING<TAB><remote path><TAB><remote size>` — no local file exists (the size field is empty if the server omits it).
- `SIZE<TAB><remote path><TAB>remote=<n> local=<m>` — sizes differ after checking for ASCII-mode CRLF conversion.
- `LISTFAIL<TAB><remote dir><TAB><error>` — the directory could not be listed; remaining directories are still checked.
- `VIRUS<TAB><remote path><TAB><remote size>` — the remote filename starts with `VIRUS_`, regardless of local state.

The final line is `DONE: <dirs> dirs, <files> remote files, <problems> problems`. Progress is logged
every 25 directories with completed and queued directory counts, files checked, and problems found.

### INI file format

```ini
[FTP]
LOCAL_DIRECTORY = c:\ftp_backup
FTP_DIRECTORY = /remote/path
FTP_HOST = server.com
FTP_USER = user
FTP_PASS = password

# Custom FTP port (default: 21)
# FTP_PORT = 2121

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

# Delete source files older than N days after sync (default: 0 = disabled)
# When DIRECTION = down, deletes files from FTP older than this many days
# DELETE_SOURCE_AFTER_DAYS = 30

# Upload only: never delete remote files that are absent locally (default: false)
# NO_DELETE = false

# Upload with hash cache only: list the server first and re-upload files changed or missing
# there (the cache cannot see uploads made from elsewhere). Costs one MLSD walk per run.
# VERIFY_REMOTE = false

# Upload only: comma-separated remote dirs (relative to FTP_DIRECTORY) emptied after upload
# All files and empty subdirs inside are deleted; the listed dirs themselves are kept
# CLEAR_REMOTE_DIRS = cache/css, cache/js, cache/smarty/templates_c
```

`LOCAL_DIRECTORY` and `FTP_DIRECTORY` are optional in the INI file if provided via `--local-dir` / `--ftp-dir` CLI arguments.

See [docs/SETTINGS_INI.md](docs/SETTINGS_INI.md) for the full reference of every INI setting.

### PHP deploy config format

As an alternative to INI files, you can use PHP config files from the deploy-tool. See `tools/config_example.php` for the format.

```
uv run python main.py config_myapp.php --local-dir "C:\my\local\folder"
```

- `--local-dir` is required when using a PHP config
- All entries in the config are processed sequentially
- Ignore patterns from `git.ignore` / `svn.ignore` are applied automatically
- Supports FTP and FTPS transfer types (SFTP is not supported)
- `ftp.clearAfterUpload` (array of remote dirs) empties those folders after each upload, keeping the folders themselves
- Preset inheritance is supported via `preset_<name>.php` files in the same directory
- A config with several entries keeps one hash cache per entry, named `<cache>_<host>_<ftp dir>.db`
  next to the given `--hash-cache-file` (e.g. `vendor_server.com_api_vendor.db`). A cache shared
  by all entries made every entry after the first skip its uploads; such an old shared file is no
  longer read, so the first run after upgrading uploads everything once. Single-entry configs keep
  the plain file name.

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

If a synced directory has no `.deployignore`, a default one (excluding `.git/`, `node_modules/`, `__pycache__/`, `.env`, OS junk files, etc.) is created automatically at sync startup. See [docs/DEPLOYIGNORE.md](docs/DEPLOYIGNORE.md) for full documentation.

## Development

```bash
# Initial setup
install.bat

# Run tests
tools\run_tests.bat

# Update dependencies
update.bat
```
