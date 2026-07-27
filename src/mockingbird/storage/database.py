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
    exists,
    inspect,
    literal,
    select,
)
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from mockingbird.storage.models import (
    Base,
    DEFAULT_STREAM_MONITORING_INTERVAL_SECONDS,
    DEFAULT_STREAM_MONITORING_MINIMUM_DETECTIONS,
    DEFAULT_STREAM_MONITORING_MODE,
    DEFAULT_STREAM_MONITORING_QUIET_SECONDS,
    DEFAULT_STREAM_RUNTIME_STATE,
)

DEFAULT_DB_URL = "sqlite:///data/mockingbird.sqlite3"
DB_URL_ENV_VAR = "MOCKINGBIRD_DB_URL"
DEFAULT_MEDIA_ROOT = "data/media/imports"
MEDIA_ROOT_ENV_VAR = "MOCKINGBIRD_MEDIA_ROOT"
CURRENT_DATABASE_SCHEMA_VERSION = 24

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


def _migrate_to_stream_monitoring_contract(connection: Connection) -> None:
    """Add inert Stream continuity records without arming any existing Stream."""

    policies = Base.metadata.tables["stream_monitoring_policies"]
    checkpoints = Base.metadata.tables["stream_runtime_checkpoints"]
    streams = Base.metadata.tables["streams"]
    policies.create(bind=connection, checkfirst=True)
    checkpoints.create(bind=connection, checkfirst=True)

    migrated_at = datetime.now(UTC)
    connection.execute(
        policies.insert().from_select(
            [
                "stream_id",
                "mode",
                "auto_create_review_candidates",
                "evaluation_interval_seconds",
                "quiet_period_seconds",
                "minimum_detection_count",
                "policy_revision",
                "updated_at",
            ],
            select(
                streams.c.id,
                literal(DEFAULT_STREAM_MONITORING_MODE),
                literal(False),
                literal(DEFAULT_STREAM_MONITORING_INTERVAL_SECONDS),
                literal(DEFAULT_STREAM_MONITORING_QUIET_SECONDS),
                literal(DEFAULT_STREAM_MONITORING_MINIMUM_DETECTIONS),
                literal(1),
                literal(migrated_at),
            ).where(
                ~exists(
                    select(policies.c.stream_id).where(
                        policies.c.stream_id == streams.c.id
                    )
                )
            ),
        )
    )
    connection.execute(
        checkpoints.insert().from_select(
            [
                "stream_id",
                "observed_policy_revision",
                "actual_state",
                "consecutive_failure_count",
                "last_stop_reason",
                "start_count",
                "failure_count",
                "evidence_handoff_count",
                "safety_hold_active",
                "updated_at",
            ],
            select(
                streams.c.id,
                literal(1),
                literal(DEFAULT_STREAM_RUNTIME_STATE),
                literal(0),
                literal("policy_off"),
                literal(0),
                literal(0),
                literal(0),
                literal(False),
                literal(migrated_at),
            ).where(
                ~exists(
                    select(checkpoints.c.stream_id).where(
                        checkpoints.c.stream_id == streams.c.id
                    )
                )
            ),
        )
    )


def _migrate_to_zone_optional_motion_evidence(connection: Connection) -> None:
    """Allow automatic whole-stream activity to become reviewable evidence.

    SQLite cannot remove a NOT NULL constraint in place. Rebuilding only this
    table preserves every existing evidence row and foreign-key target while
    making Zone context optional for automatic activity areas.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Zone-optional MotionEvidence migration requires local SQLite storage."
        )

    connection.exec_driver_sql(
        """
        CREATE TABLE motion_evidence_zone_optional (
            id VARCHAR NOT NULL,
            source_id VARCHAR,
            stream_id VARCHAR,
            zone_id VARCHAR,
            start_frame_index INTEGER,
            end_frame_index INTEGER,
            best_frame_index INTEGER,
            start_time VARCHAR,
            end_time VARCHAR,
            best_frame_time VARCHAR,
            peak_changed_ratio FLOAT NOT NULL,
            triggered_frame_count INTEGER NOT NULL,
            scoring_config_json TEXT NOT NULL,
            snapshot_media_asset_id VARCHAR,
            status VARCHAR NOT NULL,
            promoted_event_id VARCHAR,
            promoted_visit_id VARCHAR,
            created_at DATETIME NOT NULL,
            notes TEXT,
            PRIMARY KEY (id),
            FOREIGN KEY(source_id) REFERENCES camera_sources (id),
            FOREIGN KEY(stream_id) REFERENCES streams (id),
            FOREIGN KEY(zone_id) REFERENCES zones (id),
            FOREIGN KEY(snapshot_media_asset_id) REFERENCES media_assets (id),
            FOREIGN KEY(promoted_event_id) REFERENCES events (id),
            FOREIGN KEY(promoted_visit_id) REFERENCES visits (id)
        )
        """
    )
    connection.exec_driver_sql(
        """
        INSERT INTO motion_evidence_zone_optional (
            id, source_id, stream_id, zone_id, start_frame_index,
            end_frame_index, best_frame_index, start_time, end_time,
            best_frame_time, peak_changed_ratio, triggered_frame_count,
            scoring_config_json, snapshot_media_asset_id, status,
            promoted_event_id, promoted_visit_id, created_at, notes
        )
        SELECT
            id, source_id, stream_id, zone_id, start_frame_index,
            end_frame_index, best_frame_index, start_time, end_time,
            best_frame_time, peak_changed_ratio, triggered_frame_count,
            scoring_config_json, snapshot_media_asset_id, status,
            promoted_event_id, promoted_visit_id, created_at, notes
        FROM motion_evidence
        """
    )
    connection.exec_driver_sql("DROP TABLE motion_evidence")
    connection.exec_driver_sql(
        "ALTER TABLE motion_evidence_zone_optional RENAME TO motion_evidence"
    )


def _migrate_to_bioclip_identification_attempt_evidence(connection: Connection) -> None:
    """Add an empty evidence table without inventing historical model attempts."""

    attempts = Base.metadata.tables["bioclip_identification_attempts"]
    attempts.create(bind=connection, checkfirst=True)


def _migrate_to_review_identification_assistant_runs(connection: Connection) -> None:
    """Add empty reviewer-request provenance without modifying prior evidence or truth."""

    Base.metadata.tables["review_identification_assistant_runs"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_visit_organization(connection: Connection) -> None:
    """Add empty user organization state without changing historical truth or Visits."""
    Base.metadata.tables["visit_organization"].create(bind=connection, checkfirst=True)


def _migrate_to_visit_collections(connection: Connection) -> None:
    """Add empty private Collection records without changing Visits, media, or truth."""

    Base.metadata.tables["visit_collections"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["visit_collection_memberships"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_visit_tags(connection: Connection) -> None:
    """Add empty local tag records without creating memberships or reviewed truth."""

    Base.metadata.tables["visit_tags"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["visit_tag_memberships"].create(bind=connection, checkfirst=True)


def _migrate_to_yard_map(connection: Connection) -> None:
    """Add empty local map tables without changing Streams, Zones, media, or truth."""

    Base.metadata.tables["yard_maps"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["yard_map_stream_placements"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["yard_map_zone_placements"].create(bind=connection, checkfirst=True)


def _migrate_to_camera_health_incidents(connection: Connection) -> None:
    """Add bounded operational health state without modifying evidence or truth."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Camera health migration requires local SQLite storage."
        )
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("stream_runtime_checkpoints")
    }
    for column, definition in (
        ("last_evidence_persisted_at", "DATETIME"),
        ("last_evidence_failure_at", "DATETIME"),
        ("evidence_failure_code", "VARCHAR"),
    ):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE stream_runtime_checkpoints ADD COLUMN {column} {definition}"
            )
    Base.metadata.tables["camera_health_incidents"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_camera_configuration_revisions(connection: Connection) -> None:
    """Add empty, bounded configuration history without touching camera state or media."""

    Base.metadata.tables["camera_configuration_revisions"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_camera_node_provider_contract(connection: Connection) -> None:
    """Reserve v23 for Camera Node configuration without inventing paired devices.

    Node identity, opaque selected camera ID, pairing state, and credential stay
    in the existing local Source provider configuration. No Source, Stream,
    pairing, media, evidence, alert, or truth record is created by migration.
    """

    Base.metadata.tables["source_provider_configurations"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_high_resolution_activity_evidence(connection: Connection) -> None:
    """Add empty v24 evidence lineage fields without changing existing media or Visits."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "High-resolution evidence migration requires local SQLite storage."
        )
    # Complete historical databases already have both tables.  Creating empty
    # missing tables is still safer than failing an otherwise recoverable
    # partial local database, and never creates media, Visits, or truth rows.
    Base.metadata.tables["media_assets"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["visit_evidence_links"].create(bind=connection, checkfirst=True)
    media_columns = {
        column["name"] for column in inspect(connection).get_columns("media_assets")
    }
    for column, definition in (
        ("parent_media_asset_id", "VARCHAR"),
        ("evidence_role", "VARCHAR"),
        ("image_width", "INTEGER"),
        ("image_height", "INTEGER"),
        ("capture_profile_id", "VARCHAR"),
        ("normalized_track_box_json", "TEXT"),
        ("normalized_padded_crop_box_json", "TEXT"),
        ("geometry_transform_id", "VARCHAR"),
        ("trigger_id", "VARCHAR"),
        ("trigger_started_at", "DATETIME"),
        ("capture_requested_at", "DATETIME"),
        ("captured_at", "DATETIME"),
        ("alignment_status", "VARCHAR"),
        ("alignment_failure_code", "VARCHAR"),
    ):
        if column not in media_columns:
            connection.exec_driver_sql(
                f"ALTER TABLE media_assets ADD COLUMN {column} {definition}"
            )
    evidence_columns = {
        column["name"]
        for column in inspect(connection).get_columns("visit_evidence_links")
    }
    if "evidence_role" not in evidence_columns:
        connection.exec_driver_sql(
            "ALTER TABLE visit_evidence_links ADD COLUMN evidence_role "
            "VARCHAR NOT NULL DEFAULT 'monitoring_frame'"
        )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_media_assets_parent_media_asset "
        "ON media_assets(parent_media_asset_id)"
    )


def _migrate_to_zone_monitoring_policy_overrides(connection: Connection) -> None:
    """Add empty per-Zone overrides without changing existing Zone behavior."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Zone monitoring policy migration requires local SQLite storage."
        )
    columns = {
        column["name"]
        for column in inspect(connection).get_columns("zones")
    }
    if "monitoring_policy_json" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE zones ADD COLUMN monitoring_policy_json TEXT"
        )


def _migrate_to_fast_review_reversals(connection: Connection) -> None:
    """Add append-only Fast Review undo metadata without changing prior truth."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Fast Review reversal migration requires local SQLite storage."
        )
    columns = {
        column["name"] for column in inspect(connection).get_columns("review_labels")
    }
    for column, definition in (
        ("reversal_of_review_label_id", "TEXT"),
        ("prior_review_status", "TEXT"),
        ("prior_reviewed_label", "TEXT"),
        ("prior_event_review_status", "TEXT"),
        ("fast_review_session_id", "TEXT"),
        ("fast_review_idempotency_key", "TEXT"),
    ):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE review_labels ADD COLUMN {column} {definition}"
            )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS review_labels_fast_review_idempotency_key "
        "ON review_labels(fast_review_idempotency_key) "
        "WHERE fast_review_idempotency_key IS NOT NULL"
    )


def _migrate_to_review_label_revisions(connection: Connection) -> None:
    """Add append-only reviewed-Visit revision metadata without changing old truth."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Review-label revision migration requires local SQLite storage."
        )
    columns = {
        column["name"] for column in inspect(connection).get_columns("review_labels")
    }
    for column in (
        "supersedes_review_label_id",
        "review_action",
        "revision_idempotency_key",
    ):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE review_labels ADD COLUMN {column} TEXT"
            )
    connection.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS review_labels_revision_idempotency_key "
        "ON review_labels(revision_idempotency_key) "
        "WHERE revision_idempotency_key IS NOT NULL"
    )


def _migrate_to_visit_curation(connection: Connection) -> None:
    """Add durable Visit curation links without changing historical media or truth."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Visit curation migration requires local SQLite storage."
        )
    columns = {column["name"] for column in inspect(connection).get_columns("visits")}
    if "zone_id" not in columns:
        connection.exec_driver_sql("ALTER TABLE visits ADD COLUMN zone_id VARCHAR")
    if "is_superseded" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE visits ADD COLUMN is_superseded BOOLEAN NOT NULL DEFAULT 0"
        )
    connection.exec_driver_sql(
        "UPDATE visits SET zone_id = ("
        "SELECT primary_zone_id FROM events WHERE events.id = visits.event_id"
        ") WHERE zone_id IS NULL"
    )
    Base.metadata.tables["visit_evidence_links"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["visit_relationships"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["visit_curation_history"].create(bind=connection, checkfirst=True)


def _migrate_to_activity_library(connection: Connection) -> None:
    """Add local Activity Library preferences and optional bounded export scope."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Activity Library migration requires local SQLite storage."
        )
    columns = {
        column["name"] for column in inspect(connection).get_columns("dataset_exports")
    }
    if "selected_visit_ids_json" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE dataset_exports ADD COLUMN selected_visit_ids_json TEXT"
        )
    Base.metadata.tables["activity_library_saved_views"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_durable_monitoring_operations(connection: Connection) -> None:
    """Add durable idempotency records without changing any Stream's safe-off intent."""

    Base.metadata.tables["stream_monitoring_operations"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_storage_retention(connection: Connection) -> None:
    """Add safe-disabled retention state without touching existing managed media."""

    Base.metadata.tables["storage_retention_settings"].create(
        bind=connection,
        checkfirst=True,
    )
    Base.metadata.tables["storage_cleanup_batches"].create(
        bind=connection,
        checkfirst=True,
    )
    Base.metadata.tables["storage_cleanup_items"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_storage_retention_settings_idempotency(
    connection: Connection,
) -> None:
    """Add request identity without changing an existing retention policy."""

    columns = {
        column["name"]
        for column in inspect(connection).get_columns("storage_retention_settings")
    }
    if "last_settings_idempotency_key" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE storage_retention_settings "
            "ADD COLUMN last_settings_idempotency_key VARCHAR"
        )


def _migrate_to_storage_cleanup_action_idempotency(connection: Connection) -> None:
    """Record restore and purge retries without changing retained media."""

    columns = {
        column["name"]
        for column in inspect(connection).get_columns("storage_cleanup_batches")
    }
    for column in ("last_restore_idempotency_key", "last_purge_idempotency_key"):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE storage_cleanup_batches ADD COLUMN {column} VARCHAR"
            )


def _migrate_to_camera_setup_operations(connection: Connection) -> None:
    """Add completion idempotency only; existing Sources and Streams stay unchanged."""

    Base.metadata.tables["camera_setup_operations"].create(bind=connection, checkfirst=True)


def _migrate_to_product_alerts(connection: Connection) -> None:
    """Add an empty local inbox; existing product state never produces alerts on migration."""

    Base.metadata.tables["product_alerts"].create(bind=connection, checkfirst=True)


_SCHEMA_MIGRATIONS: dict[int, SchemaMigration] = {
    2: _migrate_to_stream_monitoring_contract,
    3: _migrate_to_zone_optional_motion_evidence,
    4: _migrate_to_bioclip_identification_attempt_evidence,
    5: _migrate_to_zone_monitoring_policy_overrides,
    6: _migrate_to_fast_review_reversals,
    7: _migrate_to_review_label_revisions,
    8: _migrate_to_visit_curation,
    9: _migrate_to_activity_library,
    10: _migrate_to_durable_monitoring_operations,
    11: _migrate_to_storage_retention,
    12: _migrate_to_storage_retention_settings_idempotency,
    13: _migrate_to_storage_cleanup_action_idempotency,
    14: _migrate_to_camera_setup_operations,
    15: _migrate_to_product_alerts,
    16: _migrate_to_review_identification_assistant_runs,
    17: _migrate_to_visit_organization,
    18: _migrate_to_visit_collections,
    19: _migrate_to_visit_tags,
    20: _migrate_to_yard_map,
    21: _migrate_to_camera_health_incidents,
    22: _migrate_to_camera_configuration_revisions,
    23: _migrate_to_camera_node_provider_contract,
    24: _migrate_to_high_resolution_activity_evidence,
}


def database_schema_version_is_compatible(version: int) -> bool:
    """Return whether a recorded schema can reach the current schema safely."""

    if version < 1 or version > CURRENT_DATABASE_SCHEMA_VERSION:
        return False
    return all(
        target_version in _SCHEMA_MIGRATIONS
        for target_version in range(version + 1, CURRENT_DATABASE_SCHEMA_VERSION + 1)
    )


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
    connect_args = (
        {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    )
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
