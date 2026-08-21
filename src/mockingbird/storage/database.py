"""Database setup for local-first MockingBird state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
import shutil
import sys
import tempfile
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
CURRENT_DATABASE_SCHEMA_VERSION = 37

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


class UnsafeDefaultStorageAccessError(RuntimeError):
    """Raised when a test process is about to fall back to MockingBird's
    persistent default *database* path with no isolation configured (see
    docs/test-repository-isolation-contract.md, "Test / Development
    Repository Isolation v1"). Only `database_url_from_env` raises this
    today -- see its own docstring, and `media_root_from_env`'s, for why the
    identical-looking media-root default is deliberately not guarded the
    same way.

    This is a test-only fail-closed guard, not a product behavior change:
    it only ever fires while running under pytest (see
    `_running_under_pytest`), so ordinary local development and the
    packaged Windows runtime -- neither of which ever imports pytest --
    resolve `DEFAULT_DB_URL` exactly as before. An explicit `db_url`
    argument or `MOCKINGBIRD_DB_URL` environment variable is never
    second-guessed by this check, no matter where it points, so a test that
    deliberately wants a real, on-disk, persistent-format integration
    repository remains fully able to construct one (see
    `tests/conftest.py`).
    """


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


def _migrate_to_monitoring_exposure_intervals(connection: Connection) -> None:
    """Add empty durable healthy-frame history without backfilling uptime."""

    Base.metadata.tables["monitoring_exposure_intervals"].create(
        bind=connection,
        checkfirst=True,
    )


def _migrate_to_high_resolution_crop_refinement(connection: Connection) -> None:
    """Add empty v26 reviewer-crop lineage fields without changing evidence or truth."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "High-resolution crop refinement migration requires local SQLite storage."
        )
    Base.metadata.tables["media_assets"].create(bind=connection, checkfirst=True)
    columns = {
        column["name"] for column in inspect(connection).get_columns("media_assets")
    }
    for column, definition in (
        ("normalized_crop_box_json", "TEXT"),
        ("derived_from_visit_id", "VARCHAR"),
        ("derived_from_event_id", "VARCHAR"),
        ("derived_from_zone_id", "VARCHAR"),
        ("parent_image_width", "INTEGER"),
        ("parent_image_height", "INTEGER"),
        ("content_sha256", "VARCHAR"),
        ("derivation_source", "VARCHAR"),
        ("previous_effective_crop_media_asset_id", "VARCHAR"),
    ):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE media_assets ADD COLUMN {column} {definition}"
            )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_media_assets_refined_crop_lookup "
        "ON media_assets(derived_from_visit_id, parent_media_asset_id, derivation_source)"
    )


def _migrate_to_observation_candidate_authority(connection: Connection) -> None:
    """Add empty Stage 7 candidate-Visit authority state and ledger tables.

    No row is seeded here: `ProductRepository` lazily creates the single
    `observation_authority_settings` row, defaulted to `shadow`, on first
    read or write. An existing installation upgrading through this
    migration therefore gains no candidate authority -- it stays exactly as
    absent as every other not-yet-touched settings row until an operator
    explicitly enables it (see docs/candidate-visit-authority-contract.md,
    "Default must remain shadow" / "No migration should enable candidate
    authority automatically")."""

    Base.metadata.tables["observation_authority_settings"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["observation_candidate_visits"].create(bind=connection, checkfirst=True)
    # Defensive column check, mirroring `_migrate_to_species_candidate_packs`'s
    # established pattern: `.create(checkfirst=True)` only creates a table
    # that does not exist yet, so a table already created by an earlier,
    # additive version of this same migration (development-time only --
    # this stage has never shipped) would otherwise be silently missing a
    # later column forever, since a schema migration only ever runs once
    # per recorded version.
    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Observation candidate-authority migration requires local SQLite storage."
        )
    ledger_columns = {
        column["name"] for column in inspect(connection).get_columns("observation_candidate_visits")
    }
    if "supporting_frame_ids_json" not in ledger_columns:
        connection.exec_driver_sql(
            "ALTER TABLE observation_candidate_visits ADD COLUMN supporting_frame_ids_json TEXT NOT NULL DEFAULT '[]'"
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


def _migrate_to_species_candidate_packs(connection: Connection) -> None:
    """Add empty versioned candidate-pack storage without rewriting suggestion evidence."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Species candidate-pack migration requires local SQLite storage."
        )
    Base.metadata.tables["species_candidate_packs"].create(bind=connection, checkfirst=True)
    Base.metadata.tables["species_candidate_pack_members"].create(
        bind=connection,
        checkfirst=True,
    )
    Base.metadata.tables["stream_species_candidate_pack_selections"].create(
        bind=connection,
        checkfirst=True,
    )
    Base.metadata.tables["bioclip_identification_attempts"].create(
        bind=connection,
        checkfirst=True,
    )
    attempt_columns = {
        column["name"]
        for column in inspect(connection).get_columns("bioclip_identification_attempts")
    }
    for column, definition in (
        ("candidate_pack_id", "VARCHAR"),
        ("candidate_pack_version", "INTEGER"),
        ("candidate_pack_sha256", "VARCHAR"),
    ):
        if column not in attempt_columns:
            connection.exec_driver_sql(
                f"ALTER TABLE bioclip_identification_attempts ADD COLUMN {column} {definition}"
            )


def _migrate_to_app_setup_state(connection: Connection) -> None:
    """Mark a pre-existing database as already past first-run onboarding.

    A database reaching this migration already existed before the setup-state
    concept did, so it is by definition not a fresh install -- seed it
    `completed` so an established installation never sees the onboarding
    wizard. A genuinely new database instead gets its `app_setup_state` row
    from `initialize_database` below, seeded `completed=False`.

    Guards against a row already existing (never overwrites it): a schema
    downgrade/replay test harness can rerun this migration against a database
    that kept this table from an earlier, already-current copy, and product
    code never re-runs a migration against a database already at the current
    version, so the only real caller of this guard is that kind of replay.
    """

    table = Base.metadata.tables["app_setup_state"]
    table.create(bind=connection, checkfirst=True)
    existing = connection.execute(
        select(table.c.singleton_id).where(table.c.singleton_id == 1)
    ).first()
    if existing is not None:
        return
    connection.execute(
        table.insert().values(
            singleton_id=1,
            completed=True,
            current_step="done",
            last_created_stream_id=None,
            updated_at=datetime.now(UTC),
        )
    )


def _migrate_to_observation_confidence_evidence(connection: Connection) -> None:
    """Add the Detection Quality Accounting v1 diagnostic lineage column to
    the existing Stage 7 candidate-Visit ledger (see
    docs/detection-quality-accounting-contract.md).

    Nullable, no default: every row that already exists at migration time
    reads back `confidence_evidence_json=None` -- the honest "this candidate
    predates confidence lineage" fact, never a fabricated summary (see "no
    fabricated confidence for legacy records" in product-doctrine.md). This
    migration writes no data of its own, mirroring `_migrate_to_
    observation_candidate_authority`'s own additive-column pattern.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Observation confidence-evidence migration requires local SQLite storage."
        )
    ledger_columns = {
        column["name"] for column in inspect(connection).get_columns("observation_candidate_visits")
    }
    if "confidence_evidence_json" not in ledger_columns:
        connection.exec_driver_sql(
            "ALTER TABLE observation_candidate_visits ADD COLUMN confidence_evidence_json TEXT"
        )


def _migrate_to_camera_node_pending_setup(connection: Connection) -> None:
    """Add durable pending-pairing storage; no existing Source/Stream changes.

    A brand-new, always-empty-on-migration table: a pairing handoff that was
    still only in the previous ten-minute in-memory store at upgrade time was
    already gone before this migration could ever see it, so there is
    nothing to backfill.
    """

    Base.metadata.tables["camera_node_pending_setups"].create(bind=connection, checkfirst=True)


def _migrate_to_review_decision_provenance(connection: Connection) -> None:
    """Add the Review Decision Provenance / Truth Boundary v1 columns to the
    existing `review_labels` table (see
    docs/review-decision-provenance-contract.md).

    Every row that already exists at migration time is backfilled to the
    explicit `"legacy_unattributed"` sentinel (`mockingbird.
    review_provenance.LEGACY_UNATTRIBUTED_ORIGIN`) -- never a fabricated
    `"human"`, and never left `NULL`. This is a deliberate, honest fact
    ("reviewer origin cannot be proven for this pre-existing row"), not a
    claim about who reviewed it; `review_provenance.is_authority_eligible`
    separately, deliberately treats that sentinel as still authoritative so
    existing users' reviewed history, exports, and training eligibility do
    not silently regress on upgrade (see "Avoid breaking existing users'
    history unnecessarily" in this milestone's own instructions). Crucially,
    backfilling away from `NULL` here means `review_origin IS NULL` can
    only mean one thing from this point forward -- a create request made
    after this migration existed that omitted the field -- so
    `is_authority_eligible` needs no activation-boundary timestamp to tell
    a genuinely legacy row apart from a new one that simply didn't send
    the field; see that function's own docstring. This migration does not
    touch any existing row's `review_status`/`reviewed_label` -- truth a
    pre-existing row already established is preserved exactly as it was.

    `review_labels` predates every numbered migration (present since
    schema v1), so a real upgrading database always already has it by the
    time this runs. The existence check below is defensive only, for the
    same reason `_read_recorded_schema_version` checks
    `has_table(...)` -- `initialize_database` runs every numbered
    migration *before* `Base.metadata.create_all`, so a database that
    somehow reaches this migration without the table yet (for example a
    minimal synthetic fixture in a migration-chain test that only creates
    the tables its own scenario touches) safely does nothing here; the
    table is created immediately afterward already carrying these columns
    from the current model definition.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Review Decision provenance migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("review_labels"):
        return
    columns = {
        column["name"] for column in inspect(connection).get_columns("review_labels")
    }
    for column in ("review_origin", "reviewer_identity"):
        if column not in columns:
            connection.exec_driver_sql(
                f"ALTER TABLE review_labels ADD COLUMN {column} TEXT"
            )
    connection.exec_driver_sql(
        "UPDATE review_labels SET review_origin = 'legacy_unattributed' WHERE review_origin IS NULL"
    )


def _migrate_to_observation_geometry_lineage(connection: Connection) -> None:
    """Add the Localization Attribution / Detection Geometry Lineage v1
    diagnostic lineage column to the existing `media_assets` table (see
    docs/localization-attribution-contract.md).

    Nullable, no default: every row that already exists at migration time
    reads back `geometry_attribution_json=None` -- the honest "this evidence
    item predates geometry lineage" fact, never a fabricated attribution
    (see "no fabricated confidence for legacy records" in
    product-doctrine.md). This migration writes no data of its own,
    mirroring `_migrate_to_observation_confidence_evidence`'s own
    additive-column pattern. `media_assets` predates every numbered
    migration (present since schema v1), so a real upgrading database
    always already has it by the time this runs -- the existence check
    below is defensive only, for the same reason
    `_migrate_to_review_decision_provenance`'s own `has_table` check is.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Observation geometry-lineage migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("media_assets"):
        return
    columns = {column["name"] for column in inspect(connection).get_columns("media_assets")}
    if "geometry_attribution_json" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE media_assets ADD COLUMN geometry_attribution_json TEXT"
        )


def _migrate_to_scene_confusor_regions(connection: Connection) -> None:
    """Add the empty, bounded, per-Stream scene-confusor recurring-geometry
    table (see docs/scene-confusor-suspicion-contract.md).

    No row is seeded here: the table starts genuinely empty for every
    installation, including one upgrading from real historical candidate
    Visits -- this migration never backfills recurring-geometry history
    from pre-existing `observation_candidate_visits`/`media_assets` rows,
    so an upgraded installation's scene-confusor mechanism starts exactly
    as cold as a brand-new one, never silently retroactive. Mirrors
    `_migrate_to_observation_candidate_authority`'s own
    "additive table, no seeded row" pattern exactly.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Scene-confusor-region migration requires local SQLite storage."
        )
    Base.metadata.tables["scene_confusor_regions"].create(bind=connection, checkfirst=True)


def _migrate_to_per_stream_observation_authority(connection: Connection) -> None:
    """Re-key `observation_authority_settings` from a single global singleton
    row (`singleton_id=1`) to one row per Stream (`stream_id` primary key) --
    see docs/candidate-visit-authority-contract.md, "Session/Stream scope."

    Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: a real,
    demonstrated 2026-08-19 field defect traced to this table being a single
    global row shared by every Stream -- one Stream's Stop silently reverted
    a *different*, still-running Stream's candidate authority to shadow, and
    the session/hourly candidate-budget count was a cross-Stream total
    despite its name. Fixing this requires the primary key itself to change,
    which SQLite cannot do in place.

    The old row is dropped, never migrated forward: it only ever held
    lazily-created diagnostic/mode state (current mode, activation boundary,
    bounded lifetime counters), never reviewed truth, dataset truth, or any
    fact this contract promises to preserve across a migration -- see
    `_migrate_to_observation_candidate_authority`'s own "no row is seeded"
    precedent. Every Stream reverting to the safe `shadow` default on
    upgrade is the *correct* direction (mirrors the original migration's own
    "an existing installation upgrading through this migration therefore
    gains no candidate authority" guarantee) -- it also happens to be the
    exact fix for the demonstrated defect itself: any installation carrying
    a stale, silently-exhausted `candidate_visit` row from before this
    migration is unconditionally reset by it, not merely by the next
    process restart. The durable candidate ledger
    (`observation_candidate_visits`, keyed by `proposal_id` and already
    carrying its own `stream_id` on every row) is completely untouched --
    every previously-created candidate Visit remains exactly as reviewable
    as before.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Per-Stream observation-authority migration requires local SQLite storage."
        )
    connection.exec_driver_sql("DROP TABLE IF EXISTS observation_authority_settings")
    Base.metadata.tables["observation_authority_settings"].create(bind=connection, checkfirst=True)


def _migrate_to_concurrent_sibling_lineage(connection: Connection) -> None:
    """Add the Multi-Subject Visit Assembly & Review v1, Phase 2 diagnostic
    lineage column to the existing `observation_candidate_visits` table (see
    docs/multi-subject-visit-assembly-review-v1.md).

    Nullable, no default: every row created before this column existed reads
    back `concurrent_sibling_proposal_ids_json=None` -- the honest "this
    candidate predates concurrent-sibling bookkeeping" fact, never a
    fabricated relationship. This migration writes no data of its own and
    never re-groups a pre-existing candidate's `event_id` retroactively --
    Event-reuse only ever happens at the moment a *new* candidate is
    created, never as a backfill. Mirrors `_migrate_to_observation_geometry_
    lineage`'s own additive-column pattern exactly. `observation_candidate_
    visits` predates this migration (schema v28), so a real upgrading
    database always already has it by the time this runs -- the existence
    check below is defensive only, for the same reason that migration's own
    `has_table` check is.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Concurrent-sibling lineage migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("observation_candidate_visits"):
        return
    columns = {column["name"] for column in inspect(connection).get_columns("observation_candidate_visits")}
    if "concurrent_sibling_proposal_ids_json" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE observation_candidate_visits ADD COLUMN concurrent_sibling_proposal_ids_json TEXT"
        )


def _migrate_to_camera_node_boot_identity(connection: Connection) -> None:
    """Add the Boot Identity + Autonomous Recovery v1 durable last-seen/
    boot-identity columns to the existing `camera_sources` table (see
    "Host-side state" in docs/camera-node-installer-design.md).

    Nullable, no default, additive only -- exactly the same shape as
    `_migrate_to_concurrent_sibling_lineage`. Every Source created before
    this column existed (a `camera_node` Source or otherwise) reads back
    `camera_node_last_seen_at=None`/`camera_node_boot_id=None`: the honest
    "not tracked yet" fact, never a fabricated timestamp or boot id. The
    next real Observation Engine checkpoint for that Stream (see
    `ProductRepository.record_observation_exposure_frame`) populates them
    going forward; this migration writes no data of its own.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Camera Node boot-identity migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("camera_sources"):
        return
    columns = {column["name"] for column in inspect(connection).get_columns("camera_sources")}
    additions = (
        ("camera_node_last_seen_at", "DATETIME"),
        ("camera_node_boot_id", "TEXT"),
        ("camera_node_boot_first_seen_at", "DATETIME"),
        ("camera_node_service_version", "TEXT"),
        ("camera_node_recent_boot_transitions_json", "TEXT"),
    )
    for name, sql_type in additions:
        if name not in columns:
            connection.exec_driver_sql(f"ALTER TABLE camera_sources ADD COLUMN {name} {sql_type}")


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
    25: _migrate_to_species_candidate_packs,
    26: _migrate_to_high_resolution_crop_refinement,
    27: _migrate_to_monitoring_exposure_intervals,
    28: _migrate_to_observation_candidate_authority,
    29: _migrate_to_app_setup_state,
    30: _migrate_to_camera_node_pending_setup,
    31: _migrate_to_observation_confidence_evidence,
    32: _migrate_to_review_decision_provenance,
    33: _migrate_to_observation_geometry_lineage,
    34: _migrate_to_scene_confusor_regions,
    35: _migrate_to_per_stream_observation_authority,
    36: _migrate_to_concurrent_sibling_lineage,
    37: _migrate_to_camera_node_boot_identity,
}


def database_schema_version_is_compatible(version: int) -> bool:
    """Return whether a recorded schema can reach the current schema safely."""

    if version < 1 or version > CURRENT_DATABASE_SCHEMA_VERSION:
        return False
    return all(
        target_version in _SCHEMA_MIGRATIONS
        for target_version in range(version + 1, CURRENT_DATABASE_SCHEMA_VERSION + 1)
    )


def _running_under_pytest() -> bool:
    """Detect a test process, not real product startup.

    Mirrors the exact convention `mockingbird.api.main._patch_testclient_
    for_pytest` already established for the same purpose: true for the
    whole pytest session (collection through teardown, regardless of which
    test is currently running), never true for the packaged Windows
    runtime or an ordinary `python -m mockingbird` launch -- pytest is a
    `[project.optional-dependencies] test` extra that no runtime import
    path ever pulls in, so `sys.modules` only contains it when something
    (virtually always pytest's own bootstrap) explicitly imported it.
    """

    return "pytest" in sys.modules


def _under_pytest_tempdir(path: Path) -> bool:
    """True when `path` is pytest's own temp root or lies beneath it.

    The one place both the fail-closed default-storage guard (below) and
    the ephemeral-test-database fast path (`_is_ephemeral_pytest_sqlite_
    database`) decide "is this a throwaway path pytest itself made," so
    the two safety-relevant checks can never silently drift apart.
    """

    resolved = path.resolve()
    safe_root = Path(tempfile.gettempdir()).resolve()
    return resolved == safe_root or safe_root in resolved.parents


def _reject_unconfigured_default_outside_test_temp(path: Path, *, what: str) -> None:
    """Fail closed rather than silently open a persistent default path.

    Test / Development Repository Isolation v1: called only on the
    *fallback* branch of `database_url_from_env` (see that function's own
    docstring for why `media_root_from_env` deliberately does not call
    this), after confirming neither an explicit constructor argument nor
    the environment variable was supplied. An explicit choice is never
    second-guessed here, no matter where it points -- this only stops the
    silent, nobody-decided-anything default from resolving outside the
    test process's own temp root (exactly what pytest's `tmp_path` already
    builds under) while running under pytest. See
    docs/test-repository-isolation-contract.md.
    """

    if not _running_under_pytest():
        return
    if _under_pytest_tempdir(path):
        return
    raise UnsafeDefaultStorageAccessError(
        f"Refusing to let a test fall back to MockingBird's default {what} "
        f"path ({path.resolve()}) with no repository explicitly configured. "
        "Inject an isolated ProductRepository(db_url=...), call "
        "configure_repository(...), or rely on the autouse "
        "tests/conftest.py fixture. A test that deliberately needs the "
        "real default-resolution behavior itself (for example "
        "runtime.run_preflight()) must point MOCKINGBIRD_HOME at an "
        "isolated directory first, exactly like the existing "
        "test_single_app_runtime.py coverage does."
    )


def database_url_from_env() -> str:
    """Explicit `MOCKINGBIRD_DB_URL` wins unconditionally; otherwise fail
    closed under pytest (see `_reject_unconfigured_default_outside_test_
    temp`) instead of silently returning `DEFAULT_DB_URL`."""

    configured = os.getenv(DB_URL_ENV_VAR)
    if configured:
        return configured
    _reject_unconfigured_default_outside_test_temp(
        sqlite_database_path(DEFAULT_DB_URL), what="database"
    )
    return DEFAULT_DB_URL


def resolve_database_url(db_url: str | None = None) -> str:
    return db_url or database_url_from_env()


def media_root_from_env() -> str:
    # Deliberately *not* guarded like `database_url_from_env` below: every
    # `ProductRepository(db_url=...)` construction across the test suite
    # already passes an explicit, isolated `db_url` (confirmed by an
    # exhaustive Part 1 sweep of this milestone), but roughly a sixth of
    # them never pass `media_root` because they never touch media at all --
    # merely resolving this default does not write anything (unlike
    # `database_url_from_env`, whose result `ProductRepository.__init__`
    # unconditionally opens/migrates/seeds). Guarding it identically would
    # reject those existing, already-safe tests for no matching safety gain
    # -- confirmed against `data/media/imports`'s own last-modified time,
    # which shows no test-run pollution. A test that *does* deliberately
    # write media without configuring `media_root` remains exactly as
    # responsible for that as it was before this milestone; see
    # docs/test-repository-isolation-contract.md's "Scope boundary".
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


# Below this line: low-space is a large fraction of the host volume being
# full, not managed-media exceeding a configured retention target. That
# media-relative signal already exists on `StorageSummary.storage_warning`;
# this is the separate, more basic "is the disk itself okay" fact a normal
# local application answers regardless of retention configuration.
LOW_DISK_FREE_BYTES_THRESHOLD = 1_000_000_000
LOW_DISK_FREE_RATIO_THRESHOLD = 0.05


@dataclass(frozen=True)
class LocalStorageDiskStatus:
    total_bytes: int
    free_bytes: int
    is_writable: bool

    @property
    def is_low_space(self) -> bool:
        if self.total_bytes <= 0:
            return False
        return (
            self.free_bytes < LOW_DISK_FREE_BYTES_THRESHOLD
            or (self.free_bytes / self.total_bytes) < LOW_DISK_FREE_RATIO_THRESHOLD
        )


def probe_local_storage_disk(directory: Path) -> LocalStorageDiskStatus:
    """Report host disk capacity/writability for the directory holding local data.

    This is deliberately a real bounded write-and-delete probe rather than
    `os.access`, which can misreport effective writability (notably on
    Windows ACLs). It never touches managed media or the database file
    itself -- only a small throwaway sentinel beside them.
    """

    try:
        usage = shutil.disk_usage(directory)
        total_bytes, free_bytes = usage.total, usage.free
    except OSError:
        total_bytes, free_bytes = 0, 0

    probe_path = directory / f".mockingbird-write-check-{os.getpid()}.tmp"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        with open(probe_path, "wb") as handle:
            handle.write(b"ok")
        is_writable = True
    except OSError:
        is_writable = False
    finally:
        try:
            probe_path.unlink(missing_ok=True)
        except OSError:
            pass
    return LocalStorageDiskStatus(total_bytes=total_bytes, free_bytes=free_bytes, is_writable=is_writable)


def _is_ephemeral_pytest_sqlite_database(resolved_url: str) -> bool:
    """True only for a SQLite *file* pytest itself created under its own tempdir.

    Test Suite Runtime & Baseline Reliability v1: profiling this milestone
    (a `cProfile` run over one `ProductRepository()` construction) found
    `Base.metadata.create_all`'s ~200 CREATE TABLE/INDEX statements costing
    ~1.4s of a ~1.8s total -- not seeding or product logic -- almost
    entirely `sqlite3.Cursor.execute` time under this sandbox's WSL2
    filesystem. Each DDL statement fsyncs its own implicit commit under
    SQLite's default `synchronous=FULL`; a throwaway per-test database
    that never survives past its own test (`tests/conftest.py`'s autouse
    fixture, and the ~90 existing test-owned fixtures that already pass an
    isolated `tmp_path`-derived `db_url`) has no real crash-durability
    requirement, so skipping that fsync is free correctness-wise -- this
    changes no on-disk journal format, so a mid-test file copy (backup/
    restore tests) observes exactly the same committed bytes it always
    did; only durability against a hard power-loss/OS-crash is relaxed,
    which no test in this suite exercises or depends on.

    Reuses the exact pytest+tempdir detection `_reject_unconfigured_
    default_outside_test_temp` already established (see docs/test-
    repository-isolation-contract.md) so this can never fire for a
    production/packaged launch (which never imports pytest) or for an
    explicit on-disk path outside pytest's own temp root -- an explicit
    `db_url`/`MOCKINGBIRD_DB_URL` pointing at a real location is never
    second-guessed, exactly like that guard.
    """

    if not _running_under_pytest() or not resolved_url.startswith("sqlite:///"):
        return False
    try:
        path = sqlite_database_path(resolved_url)
    except ValueError:
        return False
    return _under_pytest_tempdir(path)


def create_database_engine(db_url: str | None = None) -> Engine:
    resolved_url = resolve_database_url(db_url)
    _ensure_sqlite_parent(resolved_url)
    connect_args = (
        {"check_same_thread": False} if resolved_url.startswith("sqlite") else {}
    )
    engine = create_engine(resolved_url, connect_args=connect_args)
    if resolved_url.startswith("sqlite"):
        ephemeral_test_database = _is_ephemeral_pytest_sqlite_database(resolved_url)

        # A short local write should wait briefly instead of making the app look
        # unavailable during another in-process transaction.
        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA busy_timeout=5000")
                if ephemeral_test_database:
                    cursor.execute("PRAGMA synchronous=OFF")
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
            # A database created fresh right now (as opposed to one that
            # migrated up to this version from an older release) is the one
            # genuine "new installation" signal: seed onboarding as not yet
            # completed. An upgraded database is seeded `completed` instead,
            # by `_migrate_to_app_setup_state` above.
            connection.execute(
                Base.metadata.tables["app_setup_state"].insert().values(
                    singleton_id=1,
                    completed=False,
                    current_step="welcome",
                    last_created_stream_id=None,
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
