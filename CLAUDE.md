# Version
2

# Coding Rules (Pointer)

This project's rules live in two files in the project root:

- `CODING_RULES.md` — code quality and conventions. BINDING for all code work in
  this repository, always.
- `IMPLEMENTATION_FLOW.md` — the end-to-end flow to follow when planning and
  implementing a change (checks, gates, Definition of Done).

MANDATORY: Before writing or editing ANY code, you MUST Read BOTH files in full
**in the current session**. Do not rely on memory of a previous session, a
summary, or partial reads.

If you are about to make a code change and have not read both files in this
session: STOP, read them, then continue.

An external tool may orchestrate the implementation itself. When a skill or run
states that the implementation is orchestrated, ignore `IMPLEMENTATION_FLOW.md`
entirely — the orchestrator runs those steps as its own phases. `CODING_RULES.md`
stays binding either way.

Do not inline rules back into this file and do not use `@import` for either file —
they are intentionally referenced, not imported.


# CLAUDE.md — ftp-sync

## Project Overview

FTP sync CLI tool — syncs a local folder with an FTP folder. Supports bidirectional sync, concurrent operations, and recursive subfolder syncing.

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
├── hash_db.py        # Local file hash database for change detection
├── ftp_compare.py    # Read-only comparison of a remote FTP tree with a local directory
├── ftp_delete.py     # FTP file and directory deletion
├── ftp_mtime.py      # FTP modification-time retrieval and age-based source cleanup
├── tests/
│   └── test_config.py
├── tools/
│   ├── run_tests.bat
│   ├── run_integration_tests.bat
│   └── graphify_update.bat
├── pyproject.toml
├── install.bat
├── update.bat
├── start.bat
└── sync_example.bat
```

## Project-specific notes

- `Settings` is a frozen dataclass in `config.py`, updated with `dataclasses.replace()` and validated in `load_settings()` (direction, concurrent operations, required fields, `REQUIRED_SETTINGS` and `VALID_DIRECTIONS`).
- Modules still use `logger = logging.getLogger(__name__)`; migrate to `AppLogger` incrementally, and prefer it for new modules.
- Run tests with `tools\run_tests.bat` or `uv run pytest tests/ -v`.

## graphify

This project's code directory is . (repo root; non-code files are excluded via .graphifyignore).
