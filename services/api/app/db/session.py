"""Database engine + session management.

The module-level ``engine`` / ``SessionLocal`` are used by the running app.
Tests build their own engine and override the ``get_db`` FastAPI dependency, so
nothing here couples the app to a specific database instance.
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """Create the SQLite file's parent directory when missing.

    ``sqlite3`` refuses to open a database file whose parent directory does
    not exist — e.g. on ephemeral filesystems (Render Free) where the whole
    data root (``/tmp/metrasight``) starts absent on every cold start.
    In-memory and existing relative-path databases are unaffected.
    """
    path = make_url(database_url).database
    if path and path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)


def make_engine(settings: Settings) -> Engine:
    connect_args: dict = {}
    if settings.is_sqlite:
        # Allow use across FastAPI's threadpool.
        connect_args["check_same_thread"] = False
        _ensure_sqlite_parent_dir(settings.database_url)
    return create_engine(
        settings.database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


_settings = get_settings()
engine: Engine = make_engine(_settings)
SessionLocal: sessionmaker[Session] = make_session_factory(engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
