# CLAUDE.md — ftp-sync

## Project Overview

FTP sync CLI tool — syncs a local folder with an FTP folder. Supports bidirectional sync, concurrent operations, and recursive subfolder syncing.

## Coding Rules Source

Shared rules live at `D:\GIT\BenjaminKobjolke\claude-code\coding-rules`.
Relevant files: `COMMON_RULES.md` (all languages) and `PYTHON_RULES.md` (this project).
Web-only Python rules (Jinja2 templates, localization, async, Pydantic API validation) do not
apply — this is a CLI tool. Keep the rules below in sync when the source files change.

## Package Manager

- Use **uv** for dependency management
- `pyproject.toml` is the single source of truth for dependencies and tool config
- Commit `uv.lock` for reproducible installs
- Runtime dependencies: SQLAlchemy (hash cache database), pathspec (deployignore pattern matching), watchdog (file watcher)

## Project Structure

```
ftp-sync/
├── main.py           # Entry point, logging setup, orchestration
├── config.py         # Settings dataclass, INI loading, CLI parsing
├── deployignore.py   # .deployignore loading and path filtering
├── ftp_ops.py        # FTP/FTPS connection, file listing, upload, download
├── php_config.py     # PHP deploy config parser (deploy-tool format)
├── watcher.py        # File system watcher for auto-sync on changes
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
- Prefer a centralized handling/logging strategy over ad-hoc try/catch scattered everywhere
- Include context in log messages (module, operation, relevant IDs)

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
- Use parameterized queries / ORM methods — never concatenate input into queries
- Validate and sanitize all external input at boundaries
- Keep dependencies updated to avoid known vulnerabilities

### Data Objects over Many Parameters
- Bundle related values into a dedicated object (`Settings`/DTO) instead of passing many params
- Improves readability, reduces call-site churn, makes changes safer

### Typed Returns at Module Boundaries
- Public functions crossing a module boundary return typed objects (dataclass/value object) — never
  a raw `dict` indexed by string keys (a missing key silently reads as `None`)
- Lists vs single must be obvious from type and name: `get_thing() -> Thing | None` vs
  `get_things() -> list[Thing]`
- Distinguish absent (`None`) from empty (empty collection)
- Internal private helpers may stay as dicts

### Reuse Existing Models
- Before inventing a new DTO/dict shape, grep for an existing domain class that owns the same data
- Reuse it rather than mirroring its columns in a parallel shape

### Prefer Type-Safe Values
- Use typed DTOs, enums, `Literal`, typed settings over stringly-typed values
- Catches mistakes at type-check time / in tests early

### String Constants
- Centralize repeated string constants in a dedicated module — do not scatter raw strings
- See `REQUIRED_SETTINGS`, `VALID_DIRECTIONS` in `config.py`

### No God Classes
- Keep each class focused on a single purpose
- Warning signs: >5 public methods, >4 constructor deps, methods spanning unrelated domains
- Split by responsibility (extract `Validator`/`Repository`/`Notifier`) rather than piling into one
- Complements the 300-line rule — a short class can still be a god class

### Self-Describing Classes
- When behavior depends on which fields a class has (serialization, display, validation), the class
  declares those fields via a contract (`Protocol`/ABC method or dataclass field metadata) — never
  hardcode field lists in consumers

### Database Access
- If a database is needed, use SQLAlchemy ORM (not raw SQL) — see hash cache DB

### Reusable Tooling
- Before building project-specific infra scripts, check the matching `*_setup_files/` folder under
  the coding-rules repo for an existing equivalent; copy/reference it, then document new ones there

## Testing

- Framework: `pytest`
- Run tests: `tools\run_tests.bat` or `uv run pytest tests/ -v`
- Test config validation, settings parsing, and CLI overrides
- Use `tmp_path` fixture for file-based tests

### TDD for Features and Bug Fixes
1. Write tests first
2. Run and confirm they fail
3. Implement the change/fix
4. Run again and confirm they pass

### Refactor Safety
- When converting a dict return to a typed object, write a characterization test first that locks
  current behavior, run it green, then refactor; the same test must stay green afterward

### Test Quality
- Unit tests are fast and isolated — no network, no reliance on developer machine state
- Use `tmp_path` / fixtures for filesystem tests
- Provide integration tests in addition to unit tests; add `tools/run_integration_tests.bat`
- `MagicMock` must use `spec=ClassName` to validate against the real interface (catches typos and
  non-existent attributes); mock methods as methods (`mock.get_body.return_value = ...`)

## Linting & Type Checking

- `ruff` for linting and formatting
- `mypy` with strict mode for type checking
- Run: `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy .`
- CI must run all three; ruff replaces black/isort/flake8

## Batch Files

- `start.bat` — runs the application
- `install.bat` — initial project setup (uv sync + tests)
- `update.bat` — update dependencies + lint + test
- `tools/run_tests.bat` — run unit test suite
- `tools/run_integration_tests.bat` — run integration tests

## Documentation

- `README.md` is mandatory: project name/description, install/setup, usage examples, dependencies

## Confirm Dependency Versions

Before adding any new package, confirm the version with the user. Do not assume which version to use.
