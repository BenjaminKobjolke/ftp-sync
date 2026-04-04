"""PHP deploy config parser."""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(
    r"""
    (?P<STRING>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    |(?P<VARIABLE>\$\w+)
    |(?P<ARRAY>\barray\b)
    |(?P<ARROW>=>)
    |(?P<LPAREN>\()
    |(?P<RPAREN>\))
    |(?P<COMMA>,)
    |(?P<SEMICOLON>;)
    |(?P<RETURN>\breturn\b)
    |(?P<TRUE>\btrue\b)
    |(?P<FALSE>\bfalse\b)
    |(?P<NUMBER>-?\d+)
    |(?P<SKIP>\s+|//[^\n]*|/\*.*?\*/|<\?php|\?>)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass(frozen=True)
class PhpDeployEntry:
    """A single deployment entry from a PHP config file."""

    name: str
    ftp_host: str
    ftp_user: str
    ftp_pass: str
    ftp_directory: str
    ignore_patterns: tuple[str, ...]
    subfolder: str = ""
    transfer_type: str = "FTP"
    ftp_port: int = 0


def _extract_variables(content: str) -> dict[str, str]:
    """Extract PHP variable assignments like $var = 'value';."""
    variables: dict[str, str] = {}
    for match in re.finditer(r"\$(\w+)\s*=\s*'([^']*)'", content):
        variables[match.group(1)] = match.group(2)
    for match in re.finditer(r'\$(\w+)\s*=\s*"([^"]*)"', content):
        variables[match.group(1)] = match.group(2)
    return variables


def _tokenize(content: str) -> list[tuple[str, str]]:
    """Tokenize PHP content into a list of (kind, value) pairs."""
    tokens: list[tuple[str, str]] = []
    for m in _TOKEN_RE.finditer(content):
        kind = m.lastgroup
        if kind and kind != "SKIP":
            tokens.append((kind, m.group()))
    return tokens


def _parse_value(
    tokens: list[tuple[str, str]], pos: int, variables: dict[str, str]
) -> tuple[Any, int]:
    """Parse a PHP value at the given token position."""
    kind, val = tokens[pos]

    if kind == "STRING":
        return val[1:-1], pos + 1
    if kind == "VARIABLE":
        return variables.get(val[1:], ""), pos + 1
    if kind == "TRUE":
        return True, pos + 1
    if kind == "FALSE":
        return False, pos + 1
    if kind == "NUMBER":
        return int(val), pos + 1
    if kind == "ARRAY":
        pos += 1  # skip 'array'
        if pos < len(tokens) and tokens[pos][0] == "LPAREN":
            pos += 1  # skip '('
        return _parse_array_body(tokens, pos, variables)
    raise ValueError(f"Unexpected token at position {pos}: {kind} = {val!r}")


def _parse_array_body(
    tokens: list[tuple[str, str]], pos: int, variables: dict[str, str]
) -> tuple[list[Any] | dict[str, Any], int]:
    """Parse array contents after '('. Returns (list_or_dict, pos_after_rparen)."""
    items: list[Any] = []
    is_dict = False

    while pos < len(tokens) and tokens[pos][0] != "RPAREN":
        val, pos = _parse_value(tokens, pos, variables)

        if pos < len(tokens) and tokens[pos][0] == "ARROW":
            pos += 1  # skip '=>'
            actual_val, pos = _parse_value(tokens, pos, variables)
            items.append((val, actual_val))
            is_dict = True
        else:
            items.append(val)

        if pos < len(tokens) and tokens[pos][0] == "COMMA":
            pos += 1

    if pos < len(tokens) and tokens[pos][0] == "RPAREN":
        pos += 1

    if is_dict:
        return {k: v for k, v in items if isinstance(k, str)}, pos
    return items, pos


def _entry_from_dict(data: dict[str, Any]) -> PhpDeployEntry | None:
    """Convert a parsed PHP array dict to a PhpDeployEntry, or None if no FTP section."""
    ftp = data.get("ftp")
    if not isinstance(ftp, dict):
        return None

    ignore_patterns: tuple[str, ...] = ()
    subfolder = ""
    for source_key in ("git", "svn"):
        source = data.get(source_key)
        if isinstance(source, dict):
            if "ignore" in source:
                ignore_raw = source["ignore"]
                if isinstance(ignore_raw, list):
                    ignore_patterns = tuple(str(p) for p in ignore_raw)
            if not subfolder and source.get("subfolder"):
                subfolder = str(source["subfolder"])
            break

    transfer_type = str(ftp.get("transferType", "FTP")).upper()
    raw_port = ftp.get("port", 0)
    ftp_port = int(raw_port) if isinstance(raw_port, (int, str)) and str(raw_port).isdigit() else 0

    return PhpDeployEntry(
        name=str(data.get("name", "")),
        ftp_host=str(ftp.get("server", "")),
        ftp_user=str(ftp.get("username", "")).strip(),
        ftp_pass=str(ftp.get("password", "")),
        ftp_directory=str(ftp.get("root", "")),
        ignore_patterns=ignore_patterns,
        subfolder=subfolder,
        transfer_type=transfer_type,
        ftp_port=ftp_port,
    )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base (like PHP array_replace_recursive)."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _parse_php_file(file_path: str) -> list[Any] | dict[str, Any]:
    """Parse a PHP file and return the value from its 'return' statement."""
    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    variables = _extract_variables(content)
    tokens = _tokenize(content)

    pos = 0
    while pos < len(tokens) and tokens[pos][0] != "RETURN":
        pos += 1
    if pos >= len(tokens):
        raise ValueError(f"No 'return' statement found in {file_path}")

    pos += 1  # skip 'return'
    result, _ = _parse_value(tokens, pos, variables)
    if not isinstance(result, (list, dict)):
        raise ValueError(f"Expected array from 'return' in {file_path}")
    return result


def _load_preset(preset_name: str, config_dir: str) -> dict[str, Any]:
    """Load a preset file and return its data as a dict."""
    preset_path = os.path.join(config_dir, f"preset_{preset_name}.php")
    if not os.path.isfile(preset_path):
        logger.warning("Preset file not found: %s", preset_path)
        return {}

    result = _parse_php_file(preset_path)
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
        return result[0]
    logger.warning("Preset '%s' has unexpected structure, skipping", preset_name)
    return {}


def parse_php_config(file_path: str) -> list[PhpDeployEntry]:
    """Parse a PHP deploy config file and return deployment entries."""
    result = _parse_php_file(file_path)
    config_dir = os.path.dirname(os.path.abspath(file_path))

    if not isinstance(result, list):
        raise ValueError(f"Expected array of entries in {file_path}")

    entries: list[PhpDeployEntry] = []
    for item in result:
        if not isinstance(item, dict):
            continue

        preset_name = item.get("preset")
        if isinstance(preset_name, str) and preset_name:
            preset_data = _load_preset(preset_name, config_dir)
            if preset_data:
                item = _deep_merge(preset_data, item)

        entry = _entry_from_dict(item)
        if entry:
            entries.append(entry)

    logger.info("Parsed %d deployment entries from %s", len(entries), file_path)
    return entries
