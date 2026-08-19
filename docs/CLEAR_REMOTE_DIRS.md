# Clear remote directories after upload

Empties configured remote folders on the FTP server after every upload sync. Typical use:
purging server-side generated caches (compiled CSS/JS, Smarty `templates_c`, image caches)
so the deployed site regenerates them from the freshly uploaded sources.

## Behavior

- Runs **after** the upload completes, on the same FTP connection, once per sync run.
- Deletes **all files recursively** under each listed directory.
- Removes subdirectories that become empty — but **keeps the listed directories themselves**
  (PHP apps usually need the cache folders to exist).
- A listed directory that does not exist (or is already empty) is skipped silently.
- Upload direction only (`DIRECTION = up`). Ignored for downloads.
- Runs even when `NO_DELETE` is set — the explicit clear list overrides the generic
  no-delete flag.
- Watcher mode (`--watcher`): the clear runs after every debounced re-sync too.

## Configuration

### INI file

Comma-separated paths, relative to `FTP_DIRECTORY`:

```ini
[FTP]
DIRECTION = up
# ...
CLEAR_REMOTE_DIRS = cache/css, cache/js, cache/smarty/templates_c
```

### PHP deploy config

Array `clearAfterUpload` inside the `ftp` section, paths relative to `ftp.root`:

```php
'ftp' => array(
    'root'     => '/',
    'server'   => $ftpServer,
    'username' => $ftpUser,
    'password' => $ftpPassword,
    'clearAfterUpload' => array(
        'cache/css',
        'cache/images',
        'cache/js',
        'cache/loader',
        'cache/smarty/templates_c',
    ),
),
```

There is no CLI flag — configure it in the INI or PHP config.

## Log output

```
2026-08-19 12:00:05 [INFO] Clearing remote directories after upload...
2026-08-19 12:00:06 [INFO] Deleted FTP file: cache/css/main.css
2026-08-19 12:00:07 [INFO] Removed empty FTP directory: cache/css/sub
2026-08-19 12:00:07 [INFO] Cleared 42 files from remote dir: cache/css
```

## Implementation

- Setting: `Settings.clear_remote_dirs` (`config.py`), INI key `CLEAR_REMOTE_DIRS`,
  PHP key `ftp.clearAfterUpload` (`php_config.py`).
- Deletion: `clear_remote_dirs()` in `ftp_delete.py` — walks each directory with absolute
  FTP paths, reusing `delete_ftp_file()` and `build_ftp_path()`.
- Hook: called from `_run_sync()` in `main.py` right after the upload branch finishes.

See [SETTINGS_INI.md](SETTINGS_INI.md) for the full INI reference.
