"""Local file hash database for change detection."""

import hashlib
import logging

from sqlalchemy import String, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)

HASH_CHUNK_SIZE = 8192


class Base(DeclarativeBase):
    pass


class FileHash(Base):
    """Tracks the SHA-256 hash of a synced file."""

    __tablename__ = "files"

    path: Mapped[str] = mapped_column(String, primary_key=True)
    hash: Mapped[str] = mapped_column(String, nullable=False)


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
    return sessionmaker(bind=engine)()


def get_stored_hashes(session: Session) -> dict[str, str]:
    """Read all stored hashes into a dict."""
    rows = session.execute(select(FileHash)).scalars().all()
    return {row.path: row.hash for row in rows}


def upsert_hashes(session: Session, entries: dict[str, str]) -> None:
    """Insert or update hash entries."""
    for path, file_hash in entries.items():
        existing = session.get(FileHash, path)
        if existing:
            existing.hash = file_hash
        else:
            session.add(FileHash(path=path, hash=file_hash))
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
