"""Local file hash database for change detection."""

import hashlib
import logging
from dataclasses import dataclass

from sqlalchemy import Engine, Integer, String, create_engine, delete, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

HASH_CHUNK_SIZE = 8192
# Added after the first release; old caches get them via ALTER TABLE in open_hash_db.
REMOTE_COLUMNS = {"remote_size": "INTEGER", "remote_modify": "VARCHAR"}


@dataclass(frozen=True)
class RemoteFact:
    """Size and MLSD modify timestamp of a file as listed on the server ("" when not reported)."""

    size: int
    modify: str


class Base(DeclarativeBase):
    pass


class FileHash(Base):
    """Tracks the SHA-256 hash of a synced file."""

    __tablename__ = "files"

    path: Mapped[str] = mapped_column(String, primary_key=True)
    hash: Mapped[str] = mapped_column(String, nullable=False)
    remote_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remote_modify: Mapped[str | None] = mapped_column(String, nullable=True)


def compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hex digest of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def open_hash_db(db_path: str) -> Session:
    """Open or create the hash database and return a session."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    return sessionmaker(bind=engine)()


def _add_missing_columns(engine: Engine) -> None:
    existing = {column["name"] for column in inspect(engine).get_columns(FileHash.__tablename__)}
    with engine.begin() as connection:
        for name, sql_type in REMOTE_COLUMNS.items():
            if name not in existing:
                connection.execute(text(f"ALTER TABLE {FileHash.__tablename__} ADD COLUMN {name} {sql_type}"))


def get_stored_rows(session: Session) -> dict[str, FileHash]:
    """Read all cache rows, keyed by relative path."""
    rows = session.execute(select(FileHash)).scalars().all()
    return {row.path: row for row in rows}


def get_stored_hashes(session: Session) -> dict[str, str]:
    """Read all stored hashes into a dict."""
    return {path: row.hash for path, row in get_stored_rows(session).items()}


def upsert_hashes(
    session: Session,
    entries: dict[str, str],
    remote_facts: dict[str, RemoteFact] | None = None,
) -> None:
    """Insert or update hash entries with the remote facts seen after upload.

    A path without a fact gets NULL facts: facts from an older upload would be stale.
    """
    facts = remote_facts or {}
    for path, file_hash in entries.items():
        fact = facts.get(path)
        row = session.get(FileHash, path) or FileHash(path=path)
        row.hash = file_hash
        row.remote_size = fact.size if fact else None
        row.remote_modify = fact.modify if fact else None
        session.add(row)
    session.commit()


def delete_paths(session: Session, paths: list[str]) -> None:
    """Remove entries by path."""
    if not paths:
        return
    session.execute(delete(FileHash).where(FileHash.path.in_(paths)))
    session.commit()


def filter_changed_files(
    session: Session,
    merged_files: dict[str, str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Identify files whose content has changed since last sync.

    Returns:
        (changed_files, current_hashes) where changed_files is the subset
        of merged_files that need uploading, and current_hashes maps all
        relative paths to their computed SHA-256 hashes.
    """
    stored = get_stored_hashes(session)
    changed: dict[str, str] = {}
    current_hashes: dict[str, str] = {}

    for rel_path, abs_path in merged_files.items():
        file_hash = compute_file_hash(abs_path)
        current_hashes[rel_path] = file_hash

        if rel_path not in stored or stored[rel_path] != file_hash:
            changed[rel_path] = abs_path

    return changed, current_hashes


def find_deleted_paths(session: Session, current_files: set[str]) -> list[str]:
    """Find paths in DB that no longer exist locally."""
    stored = get_stored_hashes(session)
    return [path for path in stored if path not in current_files]
