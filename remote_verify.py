"""Detect remote files that changed since the hash cache recorded them (--verify-remote).

The hash cache only knows what this machine uploaded. Anything else writing to the server
(another machine, another cache file, a manual upload) leaves the cache saying "unchanged"
while the remote holds different content - often with the same size.
"""

import ftplib
import logging
import posixpath

from sqlalchemy.orm import Session

from config import Settings
from ftp_compare import list_remote_facts, sizes_match
from hash_db import RemoteFact, get_stored_rows, upsert_hashes

logger = logging.getLogger(__name__)


def with_remote_drift(
    ftp: ftplib.FTP,
    settings: Settings,
    session: Session,
    merged_files: dict[str, str],
    changed_files: dict[str, str],
) -> dict[str, str]:
    """Return changed_files plus every unchanged file the server no longer matches."""
    remote = list_remote_facts(ftp, settings.ftp_directory, settings.ignore_dirs)
    unchanged = {rel: path for rel, path in merged_files.items() if rel not in changed_files}
    drift = find_remote_drift(session, unchanged, remote)
    if drift:
        logger.warning("Remote check: %d files changed or missing on server, re-uploading", len(drift))
    return {**changed_files, **{rel: merged_files[rel] for rel in drift}}


def uploaded_facts(ftp: ftplib.FTP, settings: Settings, uploaded: list[str]) -> dict[str, RemoteFact]:
    """List only the directories that received uploads, so the cache records what the server now holds."""
    subdirs = {posixpath.dirname(rel) for rel in uploaded}
    return list_remote_facts(ftp, settings.ftp_directory, subdirs=subdirs)


def find_remote_drift(
    session: Session,
    unchanged_files: dict[str, str],
    remote_facts: dict[str, RemoteFact],
) -> list[str]:
    """Return the cache-unchanged paths that must be re-uploaded.

    Rows cached before remote facts existed have none to compare: a matching size is
    adopted as the baseline, a different size counts as drift.
    """
    rows = get_stored_rows(session)
    drift: list[str] = []
    adopted: dict[str, RemoteFact] = {}

    for rel_path, abs_path in unchanged_files.items():
        fact = remote_facts.get(rel_path)
        row = rows[rel_path]
        if fact is None:
            drift.append(rel_path)
        elif row.remote_size is None:
            if sizes_match(abs_path, fact.size):
                adopted[rel_path] = fact
            else:
                drift.append(rel_path)
        elif (row.remote_size, row.remote_modify) != (fact.size, fact.modify):
            drift.append(rel_path)

    if adopted:
        logger.warning("Remote check: %d cached files had no remote facts; assumed in sync by size", len(adopted))
        upsert_hashes(session, {rel: rows[rel].hash for rel in adopted}, adopted)
    return drift
