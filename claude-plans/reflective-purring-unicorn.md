# Feature: Delete Old Source Files After Sync

## Context

The user wants to download files from an FTP server and keep local copies forever, but automatically delete files from the FTP server that are older than a configurable number of days (e.g., 30). This is a retention policy on the source — the local copy acts as a permanent archive while the FTP server has a rolling cleanup window.

Currently, the download mode never deletes anything from FTP. This feature adds a `DELETE_SOURCE_AFTER_DAYS` setting that, after a successful download sync, queries file modification times on the FTP server and deletes files older than the threshold.

## Implementation Plan

### Step 1: Add setting to `config.py`

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\config.py`**

1. Add field to `Settings` dataclass (after `ftp_port`):
   ```python
   delete_source_after_days: int = 0
   ```
   `0` means disabled.

2. In `load_settings()`, parse from INI after the `hash_cache_file` line:
   ```python
   delete_source_after_days = int(ftp_section.get("DELETE_SOURCE_AFTER_DAYS", "0"))
   if delete_source_after_days < 0:
       raise ValueError(f"DELETE_SOURCE_AFTER_DAYS must be >= 0, got {delete_source_after_days}")
   ```
   Pass to `Settings()` constructor.

3. In `parse_arguments()`, add CLI argument:
   ```python
   parser.add_argument("--delete-source-after-days", type=int, default=None,
                        help="Delete source files older than N days after sync (0=disabled)")
   ```

4. In `apply_overrides()`, add override:
   ```python
   if args.delete_source_after_days is not None:
       result = replace(result, delete_source_after_days=args.delete_source_after_days)
   ```

### Step 2: Add FTP mtime retrieval and deletion to `ftp_ops.py`

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\ftp_ops.py`**

1. Add `import datetime` at the top.

2. Add `_parse_mdtm_response()` helper:
   - Parses FTP `MDTM` response format `"213 YYYYMMDDHHmmss[.sss]"` into a UTC `datetime`.
   - Returns `None` on invalid format.

3. Add `get_ftp_file_mtimes(ftp, file_paths)` function:
   - Iterates over `file_paths`, sends `MDTM <absolute_path>` for each using `build_ftp_path()`.
   - Returns `dict[str, datetime.datetime]` mapping relative path to UTC mtime.
   - Catches `ftplib.error_perm` and `ftplib.error_temp` per file, logs warnings, skips.
   - If no mtimes could be retrieved at all, logs a warning that the server may not support MDTM.

4. Add `delete_old_ftp_files(ftp, settings, ftp_files, max_age_days)` function:
   - Calls `get_ftp_file_mtimes()` to get timestamps.
   - Computes cutoff: `datetime.now(UTC) - timedelta(days=max_age_days)`.
   - Filters files where `mtime < cutoff`.
   - Deletes each using existing `delete_ftp_file()`.
   - Calls existing `remove_empty_ftp_dirs()` to clean up empty directories.
   - Returns count of successfully deleted files.

Estimated addition: ~60 lines. File stays under 300-line limit (currently 230).

### Step 3: Wire into main sync flow in `main.py`

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\main.py`**

1. Add `delete_old_ftp_files` to imports from `ftp_ops`.

2. In `_run_sync()`, in the download branch (after `handle_old_files()` at line 198), add:
   ```python
   if settings.delete_source_after_days > 0:
       logger.info("Checking for FTP source files older than %d days...",
                   settings.delete_source_after_days)
       deleted = delete_old_ftp_files(ftp, settings, ftp_files,
                                      settings.delete_source_after_days)
       if deleted:
           logger.info("Source cleanup: deleted %d old files from FTP", deleted)
   ```

3. In the upload branch (after existing upload logic), add a warning if the setting is used:
   ```python
   if settings.delete_source_after_days > 0:
       logger.warning("DELETE_SOURCE_AFTER_DAYS is not yet supported for upload direction")
   ```

### Step 4: Update example config

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\settings_example.ini`**

Add after the `HASH_CACHE_FILE` line:
```ini
# Delete source files older than N days after sync (default: 0 = disabled)
# When DIRECTION = down, deletes files from FTP older than this many days
# DELETE_SOURCE_AFTER_DAYS = 30
```

### Step 5: Add tests

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\tests\test_config.py`**

- Test default value is 0
- Test parsing from INI file
- Test negative value raises ValueError
- Test CLI override via `apply_overrides()`

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\tests\test_ftp_mtime.py`** (new)

- Test `_parse_mdtm_response()` with valid responses, fractional seconds, invalid formats
- Test `get_ftp_file_mtimes()` with mocked FTP connection
- Test `delete_old_ftp_files()` with mocked FTP — verifies only old files deleted

### Step 6: Update README

**File: `D:\GIT\BenjaminKobjolke\ftp-sync\README.md`**

1. Add feature bullet to the Features list:
   ```
   - **Source retention cleanup** — optionally delete source files older than N days after sync (e.g., download from FTP, then purge FTP files older than 30 days)
   ```

2. Add `DELETE_SOURCE_AFTER_DAYS` to the INI file format example (commented out, matching `settings_example.ini`).

3. Add a CLI override example:
   ```
   uv run python main.py settings.ini --delete-source-after-days 30
   ```

## Key Design Decisions

- **MDTM over MLSD**: Uses per-file `MDTM` command rather than refactoring the recursive listing to use `MLSD`. More widely supported, simpler to implement, and only runs after downloads complete.
- **UTC timestamps**: Both MDTM responses and cutoff calculation use UTC to avoid timezone issues.
- **Retention policy, not per-sync**: Deletes any FTP file older than N days, not just files downloaded in this run. The local copy is the permanent archive.
- **Uses absolute FTP paths**: `MDTM` commands use `build_ftp_path()` for consistency with `delete_ftp_file()`.
- **Sequential deletion**: Runs on the main FTP connection after downloads, not in the thread pool, to avoid FTP stateful protocol issues.

## Interactions with Existing Features

- **deployignore**: `ftp_files` is already filtered before reaching source cleanup — ignored files won't be deleted.
- **ignore_dirs**: Already filtered out by `get_ftp_files_recursive()`.
- **watcher mode**: Source cleanup runs on every sync cycle; idempotent since it only deletes past-threshold files.
- **hash_cache**: Not used in download mode; no interaction.

## Verification

1. Run `uv run pytest tests/ -v` to verify all tests pass
2. Run `uv run ruff check .` and `uv run mypy .` for lint/type checks
3. Manual test with a real FTP server:
   - Set `DIRECTION = down` and `DELETE_SOURCE_AFTER_DAYS = 30`
   - Run sync — files should download, then old FTP files should be deleted
   - Run sync again — already-downloaded files should be skipped, no new deletions
   - Verify local files are untouched
