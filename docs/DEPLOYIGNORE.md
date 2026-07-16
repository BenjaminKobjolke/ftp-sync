# .deployignore

Excludes files and folders from sync. Works like `.gitignore`, but for ftp-sync.

## Location

Place a `.deployignore` file in the **root of each synced local directory** (the folder set via
`LOCAL_DIRECTORY` in the INI file or `--local-dir`). Each local directory gets its own file.

It applies to both directions:

- **Upload** (`direction = up`): matching local files are never uploaded (loaded per local
  directory in `sync.py`).
- **Download** (`direction = down`): matching remote files are never downloaded, and matching
  local files are excluded from the comparison (loaded from the first local directory in
  `main.py`).

## Auto-creation

If a synced local directory has no `.deployignore`, ftp-sync creates one at sync startup with
these defaults:

```
# Default .deployignore created by ftp-sync
# Uses .gitignore syntax. Edit as needed.
# Folders excluded at any depth
.git/
.svn/
.hg/
.claude/
node_modules/
__pycache__/
claude-plans/
code_analysis_results/
graphify-out/
tmp/
# Folders excluded at root only
/tests/
/tools/
*.pyc
.DS_Store
Thumbs.db
.env
.deployignore
.gitignore
.gitattributes
.phpunit.result.cache
CLAUDE.md
config.php
config_example.php
code_analysis_rules.json
```

An existing file is never overwritten — edit it freely. Delete lines you actually want to sync.

## Syntax

Standard `.gitignore` syntax (implemented via the `pathspec` library):

| Pattern | Meaning |
|---------|---------|
| `docs/` | Exclude the `docs` folder and everything inside |
| `*.log` | Exclude all `.log` files, in any subfolder |
| `build/output.txt` | Exclude a specific path (relative to the synced directory root) |
| `!important.log` | Negation — re-include a file matched by an earlier pattern |
| `# comment` | Comment line, ignored |

Blank lines are skipped, leading/trailing whitespace is stripped.

Example:

```
# Exclude docs and test files
docs/
tests/
*.log

# But keep important.log
!important.log
```

## Rules

- The `.deployignore` file itself is **always excluded** from sync — it never reaches the FTP
  server, even without a matching pattern.
- If the file is missing (and before auto-creation runs), only that self-exclusion applies.

## Interaction with other settings

- **PHP deploy configs**: ignore patterns from `git.ignore` / `svn.ignore` entries are combined
  with `.deployignore` patterns. When a config entry uses a `subfolder`, root-level
  `.deployignore` patterns are rewritten relative to that subfolder (e.g.
  `wp-content/themes/x/docs/` becomes `docs/` when syncing that theme).
- **`IGNORE_DIRS` (INI setting)**: a separate, simpler mechanism — a comma-separated list of
  directory *names* skipped everywhere (e.g. `IGNORE_DIRS = node_modules, .git, tmp`). It does
  not use gitignore syntax. Both mechanisms can be used together; `.deployignore` is the one for
  fine-grained path patterns.
