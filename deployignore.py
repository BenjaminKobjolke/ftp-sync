"""Load and apply .deployignore patterns for file filtering."""

import logging
import os

import pathspec

logger = logging.getLogger(__name__)

DEPLOYIGNORE_FILENAME = ".deployignore"


def load_deployignore(
    directory: str, extra_patterns: tuple[str, ...] = ()
) -> pathspec.PathSpec:
    """Load .deployignore patterns from a directory root.

    Returns a PathSpec matcher using gitignore syntax.
    Always auto-excludes the .deployignore file itself.
    Extra patterns (e.g. from a PHP deploy config) are prepended.
    """
    patterns: list[str] = [DEPLOYIGNORE_FILENAME]
    patterns.extend(extra_patterns)
    ignore_path = os.path.join(directory, DEPLOYIGNORE_FILENAME)

    if os.path.isfile(ignore_path):
        logger.info("Loading %s from %s", DEPLOYIGNORE_FILENAME, directory)
        with open(ignore_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    patterns.append(stripped)
        logger.debug("Loaded %d patterns (including auto-exclude)", len(patterns))
    else:
        logger.debug("No %s found in %s", DEPLOYIGNORE_FILENAME, directory)

    return pathspec.PathSpec.from_lines("gitignore", patterns)


def load_deployignore_patterns(directory: str) -> list[str]:
    """Load raw pattern strings from a .deployignore file.

    Returns an empty list if the file does not exist.
    """
    ignore_path = os.path.join(directory, DEPLOYIGNORE_FILENAME)
    if not os.path.isfile(ignore_path):
        return []

    patterns: list[str] = []
    with open(ignore_path, encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)
    return patterns


def strip_subfolder_prefix(patterns: list[str], subfolder: str) -> list[str]:
    """Strip a subfolder prefix from patterns so they match relative to the subfolder.

    E.g. with subfolder 'wp-content/themes/xida2k19':
      'wp-content/themes/xida2k19/screenshot.psd' -> 'screenshot.psd'
      'wp-content/themes/xida2k19/docs/'           -> 'docs/'
      'unrelated/file.txt'                         -> 'unrelated/file.txt' (unchanged)
    """
    prefix = subfolder.rstrip("/") + "/"
    result: list[str] = []
    for p in patterns:
        if p.startswith(prefix):
            result.append(p[len(prefix):])
        elif p.rstrip("/") == subfolder.rstrip("/"):
            result.append("/")
        else:
            result.append(p)
    return result


def filter_ignored_paths(paths: list[str], spec: pathspec.PathSpec) -> list[str]:
    """Return only paths that are NOT matched by the deployignore spec."""
    return [p for p in paths if not spec.match_file(p)]
