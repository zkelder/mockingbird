"""Database setup for local-first MockingBird state."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from mockingbird.storage.models import Base

DEFAULT_DB_URL = "sqlite:///data/mockingbird.sqlite3"
DB_URL_ENV_VAR = "MOCKINGBIRD_DB_URL"


def database_url_from_env() -> str:
    return os.getenv(DB_URL_ENV_VAR, DEFAULT_DB_URL)


def resolve_database_url(db_url: str | None = None) -> str:
    return db_url or database_url_from_env()


def _ensure_sqlite_parent(db_url: str) -> None:
    if not db_url.startswith("sqlite:///"):
        return

    path = db_url.removeprefix("sqlite:///")
    if path in {":memory:", ""}:
        return

    Path(path).parent.mkdir(parents=True, exist_ok=True)


def create_database_engine(db_url: str | None = None) -> Engine:
    resolved_url = resolve_database_url(db_url)
    _ensure_sqlite_parent(resolved_url)
    connect_args = {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    return create_engine(resolved_url, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database(engine: Engine) -> None:
    Base.metadata.create_all(bind=engine)
