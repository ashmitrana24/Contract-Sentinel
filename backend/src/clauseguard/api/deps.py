"""FastAPI dependency providers."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from clauseguard.config import Settings, get_settings
from clauseguard.db.session import get_session_factory
from clauseguard.storage.file_store import FileStore

_file_store: FileStore | None = None


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yield a DB session."""
    factory = get_session_factory()
    session: Session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_cfg() -> Settings:
    return get_settings()


def get_store(cfg: Settings = Depends(get_cfg)) -> FileStore:
    """FastAPI dependency: return FileStore configured with the current storage_dir."""
    return FileStore(cfg.storage_dir)
