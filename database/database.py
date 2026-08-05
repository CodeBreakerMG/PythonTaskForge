from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from database.models import Base

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None
_db_path: Optional[Path] = None


def get_db_path() -> Path:
    if _db_path is None:
        raise RuntimeError("Database is not configured. Call configure_database() first.")
    return _db_path


def configure_database(db_path: Path | str) -> Path:
    """Point SQLAlchemy at a SQLite file. Safe to call again when the path changes."""
    global _engine, _SessionLocal, _db_path

    path = Path(db_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    if _engine is not None:
        _engine.dispose()

    _db_path = path
    _engine = create_engine(f"sqlite:///{path}", echo=False, future=True)
    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, autocommit=False, future=True
    )
    return path


def init_db(db_path: Path | str | None = None) -> Path:
    """Configure (if needed) and create tables."""
    if db_path is not None:
        configure_database(db_path)
    elif _engine is None:
        from config.settings import load_settings

        configure_database(load_settings().db_path)

    assert _engine is not None
    Base.metadata.create_all(bind=_engine)
    return get_db_path()


def get_session() -> Session:
    """Caller must close the session (or use a context manager)."""
    if _SessionLocal is None:
        init_db()
    assert _SessionLocal is not None
    return _SessionLocal()
