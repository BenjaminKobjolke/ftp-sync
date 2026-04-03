# CLAUDE.md — ftp-sync

## Project Overview

FTP sync CLI tool — syncs a local folder with an FTP folder. Supports bidirectional sync, concurrent operations, and recursive subfolder syncing.

## Package Manager

- Use **uv** for dependency management
- `pyproject.toml` is the single source of truth for dependencies and tool config
- Commit `uv.lock` for reproducible installs
- Runtime dependency: SQLAlchemy (hash cache database)

## Project Structure

```
ftp-sync/
├── main.py           # Entry point, logging setup, orchestration
├── config.py         # Settings dataclass, INI loading, CLI parsing
├── ftp_ops.py        # FTP connection, file listing, upload, download
├── sync.py           # Sync orchestration, local file listing, old file handling
├── tests/
│   └── test_config.py
├── tools/
│   └── run_tests.bat
├── pyproject.toml
├── install.bat
├── update.bat
├── start.bat
└── sync_example.bat
```

## Code Rules

### Type Hints
- All public functions must have typed parameters and return types
- Use modern syntax: `list[str]`, `str | None`, `dict[str, str]`
- Avoid `Any` unless at I/O boundaries

### Structured Logging
- Use `logging` module, never `print()`
- Each module: `logger = logging.getLogger(__name__)`
- Log levels: `debug` for skip/trace, `info` for operations, `warning` for recoverable issues, `error` for failures

### Settings
- `Settings` is a frozen dataclass — never use plain dicts for configuration
- Use `dataclasses.replace()` for immutable updates
- Validate inputs in `load_settings()`: direction, concurrent_operations, required fields

### Error Handling
- No bare `except:` clauses — always catch specific exceptions
- Use `logger.exception()` for unexpected errors (includes traceback)
- Validate at boundaries (INI file loading, CLI arguments)

### File Length
- Maximum 300 lines per file
- Split by domain concern, not by type

### Naming Conventions
- Files: `snake_case.py`
- Functions/methods: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`

### DRY
- Extract shared logic into reusable functions
- Use constants for repeated values (see `REQUIRED_SETTINGS`, `VALID_DIRECTIONS` in config.py)

### Security
- Never commit secrets (`.env`, credentials, INI files with real passwords)
- `.gitignore` covers `.env` and IDE files

## Testing

- Framework: `pytest`
- Run tests: `tools\run_tests.bat` or `uv run pytest tests/ -v`
- Test config validation, settings parsing, and CLI overrides
- Use `tmp_path` fixture for file-based tests

## Linting & Type Checking

- `ruff` for linting and formatting
- `mypy` with strict mode for type checking
- Run: `uv run ruff check .` and `uv run mypy .`

## Batch Files

- `start.bat` — runs the application
- `install.bat` — initial project setup (uv sync + tests)
- `update.bat` — update dependencies + lint + test
- `tools/run_tests.bat` — run test suite

## Confirm Dependency Versions

Before adding any new package, confirm the version with the user. Do not assume which version to use.
