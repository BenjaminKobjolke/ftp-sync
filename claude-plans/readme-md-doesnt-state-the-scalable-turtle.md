# Add `--hash-cache-file` CLI Override

## Context

`HASH_CACHE_FILE` is currently INI-only. The user wants to call `ftp-sync` from `D:\wamp64\www\ax-suite-contest\deploy\ftp-sync-appcentrics-vendor.bat` and pass a custom cache file path per invocation without maintaining a separate INI file per bat. README also fails to document any CLI arg for the cache path because none exists. This plan adds a `--hash-cache-file` flag and documents it.

## Approach

Follow the existing `--local-dir` / `--ftp-dir` / `--delete-source-after-days` override pattern in `config.py`. Wire the override so it works for both INI configs and PHP deploy configs (the latter currently hardcodes the cache path in `main.py:109`).

## Changes

### 1. `config.py` — add CLI flag + override

**`parse_arguments()`** (after line 103, before `return parser.parse_args()`):
```python
parser.add_argument(
    "--hash-cache-file",
    help="Override HASH_CACHE_FILE from INI file (path to SQLite hash cache)",
)
```

**`apply_overrides()`** (after line 114, before `return result`):
```python
if args.hash_cache_file:
    result = replace(result, hash_cache_file=args.hash_cache_file)
```

### 2. `main.py` — make PHP path respect the CLI override

Currently `_run_php_config` (line 109) hardcodes:
```python
hash_cache_file = os.path.join(local_directories[0], ".ftp_sync_cache.db")
```

Replace with:
```python
hash_cache_file = getattr(args, "hash_cache_file", None) or os.path.join(
    local_directories[0], ".ftp_sync_cache.db"
)
```

This keeps the existing default for PHP configs while letting `--hash-cache-file` win when provided. (User's bat file may be INI- or PHP-based; either path now honors the flag.)

### 3. `tests/test_config.py` — add coverage

In `TestApplyOverrides`, update all existing `argparse.Namespace(...)` calls to include `hash_cache_file=None` (currently 5 tests at lines 200, 206, 213, 220, 227, 233 use `Namespace` without it — required, since `apply_overrides` will now read the attribute).

Add new test:
```python
def test_hash_cache_file_override(self) -> None:
    settings = self._base_settings()
    args = argparse.Namespace(
        local_dir=None, ftp_dir=None,
        delete_source_after_days=None,
        hash_cache_file="C:\\new\\cache.db",
    )
    result = apply_overrides(settings, args)
    assert result.hash_cache_file == "C:\\new\\cache.db"
```

### 4. `README.md` — document the flag

- Update Usage line (around line 35) to include `[--hash-cache-file <path>]`.
- Add new example block under "Examples":
  ```
  Use a custom hash cache file location:
  ```
  ```
  uv run python main.py settings.ini --hash-cache-file "C:\caches\app-vendor.db"
  ```
- Add bullet to Features list mentioning CLI override for hash cache file.

## Files Modified

- `config.py` — lines 90-104 (parser), 107-116 (overrides)
- `main.py` — line 109 (PHP cache path)
- `tests/test_config.py` — `TestApplyOverrides` class (lines 186-235)
- `README.md` — usage section, examples, features list

## Reused Code

- `replace()` from `dataclasses` — already imported in `config.py:6`, used for all other CLI overrides
- `getattr(args, ..., None)` defensive read pattern — already used in `main.py` for `resync` and `watcher`

## Verification

1. Run tests: `tools\run_tests.bat`
   - All existing `TestApplyOverrides` tests still pass with the added `hash_cache_file=None` field
   - New `test_hash_cache_file_override` passes
2. Lint/type check: `uv run ruff check .` and `uv run mypy .`
3. Manual smoke test with an INI that omits `HASH_CACHE_FILE`:
   ```
   uv run python main.py settings.ini --hash-cache-file "C:\tmp\test.db"
   ```
   - Confirm log shows hash cache mode active and DB created at the given path
4. Update the user's `ftp-sync-appcentrics-vendor.bat` to append `--hash-cache-file "<path>"` to its invocation
