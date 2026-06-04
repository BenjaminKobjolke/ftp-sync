# Plan: Run code analysis and fix issues

## Context

Ran the project's configured analysis tools (per `CLAUDE.md` → ruff + mypy + pytest). No dedicated `analyze` bat exists; analysis is defined as `uv run ruff check .` and `uv run mypy .`. Goal: surface and fix any issues.

## Analysis results

| Check | Command | Result |
|-------|---------|--------|
| Lint | `uv run ruff check .` | ✅ All checks passed |
| Types | `uv run mypy .` | ✅ No issues in 15 source files |
| Tests | `uv run pytest tests/ -q` | ✅ 85 passed |
| Format | `uv run ruff format --check .` | ❌ 9 files would be reformatted |

## Only issue: formatting

9 files need reformatting. All changes are cosmetic — line wrapping and whitespace (e.g. collapsing multi-line signatures that fit the configured line length, slice spacing `[len(prefix) :]`). No logic changes.

Affected files: `config.py`, `deployignore.py`, `ftp_ops.py`, `main.py`, `php_config.py`, `sync.py`, `tests/test_config.py`, `tests/test_ftp_mtime.py`, `tests/test_sync.py`.

## Fix

```
uv run ruff format .
```

## Verification

```
uv run ruff format --check .   # → all files already formatted
uv run ruff check .            # → still clean
uv run mypy .                  # → still clean
uv run pytest tests/ -q        # → 85 passed
```
