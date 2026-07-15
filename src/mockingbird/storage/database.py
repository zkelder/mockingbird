"""Database setup for local-first MockingBird state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from typing import Callable

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Integer,
    MetaData,
    Table,
    create_engine,
    event,
    inspect,
    select,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from mockingbird.storage.models import Base

DEFAULT_DB_URL = "sqlite:///data/mockingbird.sqlite3"
DB_URL_ENV_VAR = "MOCKINGBIRD_DB_URL"
DEFAULT_MEDIA_ROOT = "data/media/imports"
MEDIA_ROOT_ENV_VAR = "MOCKINGBIRD_MEDIA_ROOT"
CURRENT_DATABASE_SCHEMA_VERSION = 1

_SCHEMA_METADATA = MetaData()
_SCHEMA_VERSION_TABLE = Table(
    "mockingbird_schema",
    _SCHEMA_METADATA,
    Column("singleton_id", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


class DatabaseSchemaCompatibilityError(RuntimeError):
    """Raised before startup can modify a database with an unsupported version."""


@dataclass(frozen=True)
class DatabaseSchemaStatus:
    version: int
    current_version: int
    integrity_check: str
    initialized_schema_record: bool


SchemaMigration = Callable[[Connection], None]
_SCHEMA_MIGRATIONS: dict[int, SchemaMigration] = {}


def database_url_from_env() -> str:
    return os.getenv(DB_URL_ENV_VAR, DEFAULT_DB_URL)


def resolve_database_url(db_url: str | None = None) -> str:
    return db_url or database_url_from_env()


def media_root_from_env() -> str:
    return os.getenv(MEDIA_ROOT_ENV_VAR, DEFAULT_MEDIA_ROOT)


def resolve_media_root(media_root: str | Path | None = None) -> Path:
    return Path(media_root or media_root_from_env())


def sqlite_database_path(db_url: str) -> Path:
    """Return the file path for a supported SQLite database URL.

    Backup and recovery is intentionally file-based. Keeping this validation in
    the storage layer prevents operational code from guessing at other database
    URL formats or treating an in-memory database as recoverable.
    """

    if not db_url.startswith("sqlite:///"):
        raise ValueError("local_backup_requires_sqlite")

    value = db_url.removeprefix("sqlite:///")
    if value in {"", ":memory:"}:
        raise ValueError("local_backup_requires_sqlite_file")
    return Path(value)


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
    engine = create_engine(resolved_url, connect_args=connect_args)
    if resolved_url.startswith("sqlite"):
        # A short local write should wait briefly instead of making the app look
        # unavailable during another in-process transaction.
        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
            finally:
                cursor.close()
    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _sqlite_integrity_check(engine: Engine) -> str:
    if engine.dialect.name != "sqlite":
        return "not_applicable"
    try:
        with engine.connect() as connection:
            results = connection.exec_driver_sql("PRAGMA quick_check").scalars().all()
    except SQLAlchemyError as error:
        raise DatabaseSchemaCompatibilityError(
            "MockingBird could not safely read its local database."
        ) from error
    if results != ["ok"]:
        raise DatabaseSchemaCompatibilityError(
            "MockingBird's local database did not pass its integrity check."
        )
    return "ok"


def _read_recorded_schema_version(engine: Engine) -> int | None:
    if not inspect(engine).has_table(_SCHEMA_VERSION_TABLE.name):
        return None
    with engine.connect() as connection:
        row = connection.execute(
            select(_SCHEMA_VERSION_TABLE.c.version).where(
                _SCHEMA_VERSION_TABLE.c.singleton_id == 1
            )
        ).one_or_none()
    if row is None:
        raise DatabaseSchemaCompatibilityError(
            "MockingBird's database schema record is incomplete."
        )
    return int(row.version)


def _validate_or_migrate_schema_version(engine: Engine, recorded_version: int) -> int:
    if recorded_version > CURRENT_DATABASE_SCHEMA_VERSION:
        raise DatabaseSchemaCompatibilityError(
            "This MockingBird database was created by a newer app version. "
            "Upgrade MockingBird before opening it."
        )

    version = recorded_version
    if version < CURRENT_DATABASE_SCHEMA_VERSION:
        with engine.begin() as connection:
            while version < CURRENT_DATABASE_SCHEMA_VERSION:
                target_version = version + 1
                migration = _SCHEMA_MIGRATIONS.get(target_version)
                if migration is None:
                    raise DatabaseSchemaCompatibilityError(
                        "This MockingBird database needs an explicit migration before it "
                        "can be opened safely."
                    )
                migration(connection)
                connection.execute(
                    _SCHEMA_VERSION_TABLE.update()
                    .where(_SCHEMA_VERSION_TABLE.c.singleton_id == 1)
                    .values(version=target_version, updated_at=datetime.now(UTC))
                )
                version = target_version
    return version


def initialize_database(engine: Engine) -> DatabaseSchemaStatus:
    """Validate compatibility, create the current schema, and record its version."""

    integrity_check = _sqlite_integrity_check(engine)
    recorded_version = _read_recorded_schema_version(engine)
    if recorded_version is not None:
        recorded_version = _validate_or_migrate_schema_version(engine, recorded_version)

    # Product tables are created only after a recorded version is known to be
    # compatible, so a newer database is never modified by an older app.
    Base.metadata.create_all(bind=engine)
    _SCHEMA_METADATA.create_all(bind=engine)

    initialized_schema_record = recorded_version is None
    if initialized_schema_record:
        with engine.begin() as connection:
            connection.execute(
                _SCHEMA_VERSION_TABLE.insert().values(
                    singleton_id=1,
                    version=CURRENT_DATABASE_SCHEMA_VERSION,
                    updated_at=datetime.now(UTC),
                )
            )
        recorded_version = CURRENT_DATABASE_SCHEMA_VERSION

    return DatabaseSchemaStatus(
        version=recorded_version,
        current_version=CURRENT_DATABASE_SCHEMA_VERSION,
        integrity_check=integrity_check,
        initialized_schema_record=initialized_schema_record,
    )
