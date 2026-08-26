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
CURRENT_DATABASE_SCHEMA_VERSION = 57

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
    # Release Engineering Foundation v1: set only when *this* call actually
    # ran the migration chain (never on a brand-new database, never on an
    # already-current one) -- the one genuine "an upgrade just happened"
    # signal, distinct from `version`/`current_version` which describe
    # steady-state facts true on every ordinary launch too.
    migrated_from_version: int | None = None
    pre_migration_backup_id: str | None = None


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


def _migrate_to_camera_node_replacement_provenance(connection: Connection) -> None:
    """Add the Reprovision / Replacement Recovery v1 bounded hardware-
    replacement provenance columns to `camera_sources` (see "Provenance" in
    docs/camera-node-reprovision-recovery-design.md).

    Nullable, no default, additive only -- exactly the same shape as
    `_migrate_to_camera_node_boot_identity`. Every Source predating this
    column, and any Source whose Camera Node was never replaced, reads back
    `camera_node_identity_replaced_at=None`: honest "never replaced," never
    a fabricated event. Only a confirmed replacement (see
    `_camera_configuration_proposed_config`'s `confirm_node_identity_change`
    override) ever writes these; this migration writes no data of its own.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Camera Node replacement-provenance migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("camera_sources"):
        return
    columns = {column["name"] for column in inspect(connection).get_columns("camera_sources")}
    additions = (
        ("camera_node_prior_node_id", "TEXT"),
        ("camera_node_identity_replaced_at", "DATETIME"),
        ("camera_node_replacement_reason", "TEXT"),
    )
    for name, sql_type in additions:
        if name not in columns:
            connection.exec_driver_sql(f"ALTER TABLE camera_sources ADD COLUMN {name} {sql_type}")


def _migrate_to_camera_onvif_profiles(connection: Connection) -> None:
    """Add the empty, bounded, per-Source ONVIF device/media-profile
    provenance table (v0.1 Acquisition/Ingest Interoperability Closure v1,
    "II.4 ONVIF"; see `mockingbird.storage.models.CameraOnvifProfileModel`
    and mockingbird.source_providers.onvif_client's module docstring).

    No row is seeded here: the table starts genuinely empty for every
    installation, including one upgrading from a real Source that already
    happens to be an RTSP camera some ONVIF-capable device also serves --
    this migration never infers or backfills ONVIF provenance for an
    existing Source; only an explicit, future ONVIF setup/re-discovery
    action ever writes a row here. Mirrors `_migrate_to_scene_confusor_
    regions`'s identical "additive table, no seeded row" pattern.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "ONVIF profile-provenance migration requires local SQLite storage."
        )
    Base.metadata.tables["camera_onvif_profiles"].create(bind=connection, checkfirst=True)


def _migrate_to_media_asset_duration(connection: Connection) -> None:
    """Add the nullable `duration_seconds` column to `media_assets` (v0.1
    Acquisition/Ingest Interoperability Closure v1, "II.8 Offline recorded
    video" / "II.20 provenance bridge"): the one small, honest metadata
    field recorded video/camera-trap clip ingest needs so a bounded,
    known-duration acquisition effort can be represented as MediaAsset
    provenance without ever being wired into `MonitoringExposureInterval
    Model`/Today's coverage math (see "II.10 Offline vs monitoring
    coverage" -- importing a clip must never imply continuous monitoring).

    Nullable, no default: every row that already exists at migration time
    (every image, and every video imported before this migration existed)
    correctly reads back `duration_seconds=None` -- an honest "not known,"
    never a fabricated zero -- mirroring `_migrate_to_observation_
    confidence_evidence`'s identical nullable-no-backfill discipline.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "MediaAsset duration migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("media_assets"):
        return
    columns = {column["name"] for column in inspect(connection).get_columns("media_assets")}
    if "duration_seconds" not in columns:
        connection.exec_driver_sql("ALTER TABLE media_assets ADD COLUMN duration_seconds FLOAT")


def _migrate_to_recorded_media_analysis_runs(connection: Connection) -> None:
    """Add the empty, bounded `recorded_media_analysis_runs` progress/
    diagnostics/idempotency table (Offline / Recorded Observation Ingest v1,
    see docs/offline-recorded-media-observation-contract.md). Mirrors
    `_migrate_to_scene_confusor_regions`'s own "additive table, no seeded
    row" pattern exactly: an installation upgrading from schema 40 has never
    analyzed any recorded video, so it correctly starts with no run history
    at all, never a fabricated backfill from pre-existing `media_assets`
    rows."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Recorded-media analysis run migration requires local SQLite storage."
        )
    Base.metadata.tables["recorded_media_analysis_runs"].create(bind=connection, checkfirst=True)


def _migrate_to_research_collections(connection: Connection) -> None:
    """Add the empty, bounded `research_collections` table (Research/
    Conservation/Export Interoperability v1, see docs/research-conservation-
    export-contract.md "Collection/contributor model" and
    `mockingbird.storage.models.ResearchCollectionModel`). Mirrors
    `_migrate_to_recorded_media_analysis_runs`'s own "additive table, no
    seeded row" pattern exactly: an installation upgrading from schema 41
    has never created a research collection, so it correctly starts with
    none at all."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Research collections migration requires local SQLite storage."
        )
    Base.metadata.tables["research_collections"].create(bind=connection, checkfirst=True)


def _migrate_to_acoustic_observation_foundation(connection: Connection) -> None:
    """Acoustic / BirdNET Observation Foundation v1 (see docs/acoustic-
    birdnet-observation-foundation-v1-contract.md): three small, additive
    changes in one migration, deliberately not three separate schema bumps
    -- they all land together in the same milestone and none is useful
    without the others.

    - `media_assets` gains nullable `audio_sample_rate_hz`/
      `audio_channel_count` (the audio analog of `image_width`/
      `image_height`), mirroring `_migrate_to_media_asset_duration`'s exact
      "nullable, no default, no backfill" discipline.
    - `species_suggestions` gains nullable `window_start_ms`/`window_end_ms`
      (the temporal analog of `evidence_region_json`) and
      `model_provenance_json` (adapter-neutral model/runtime provenance).
    - The new, empty `acoustic_analysis_runs` table, mirroring
      `_migrate_to_recorded_media_analysis_runs`'s own "additive table, no
      seeded row" pattern exactly: an installation upgrading from schema 42
      has never analyzed any audio, so it correctly starts with no run
      history at all.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Acoustic observation foundation migration requires local SQLite storage."
        )
    if inspect(connection).has_table("media_assets"):
        media_asset_columns = {
            column["name"] for column in inspect(connection).get_columns("media_assets")
        }
        if "audio_sample_rate_hz" not in media_asset_columns:
            connection.exec_driver_sql(
                "ALTER TABLE media_assets ADD COLUMN audio_sample_rate_hz INTEGER"
            )
        if "audio_channel_count" not in media_asset_columns:
            connection.exec_driver_sql(
                "ALTER TABLE media_assets ADD COLUMN audio_channel_count INTEGER"
            )
    if inspect(connection).has_table("species_suggestions"):
        suggestion_columns = {
            column["name"] for column in inspect(connection).get_columns("species_suggestions")
        }
        if "window_start_ms" not in suggestion_columns:
            connection.exec_driver_sql(
                "ALTER TABLE species_suggestions ADD COLUMN window_start_ms INTEGER"
            )
        if "window_end_ms" not in suggestion_columns:
            connection.exec_driver_sql(
                "ALTER TABLE species_suggestions ADD COLUMN window_end_ms INTEGER"
            )
        if "model_provenance_json" not in suggestion_columns:
            connection.exec_driver_sql(
                "ALTER TABLE species_suggestions ADD COLUMN model_provenance_json TEXT"
            )
    Base.metadata.tables["acoustic_analysis_runs"].create(bind=connection, checkfirst=True)


def _migrate_to_acoustic_runtime_queue(connection: Connection) -> None:
    """Acoustic Runtime & Quality v1 (see docs/acoustic-runtime-quality-v1-
    contract.md): small, nullable/defaulted additive columns so one
    `acoustic_analysis_runs` row can serve as both a durable queue entry
    and its own attempt-history record -- no new table, no change to the
    existing `status` vocabulary (it already included `queued`; nothing
    ever inserted a row with it before this milestone). Also adds the
    explicit `media_assets.acoustic_working_segment` marker
    `run_working_audio_retention_sweep` requires (see that method's own
    docstring for why an explicit positive marker, not an inferred one, is
    required), and the `acoustic_analysis_runs` status/created_at index
    already declared on the model but never actually created for an
    upgraded (as opposed to freshly-created) database -- found via review:
    `initialize_database`'s `Base.metadata.create_all(checkfirst=True)`
    skips index creation for a table that already exists, so this
    migration must create it explicitly or every upgraded installation
    would silently full-table-scan the claim/reclaim/capacity/diagnostics
    queries this milestone adds, while a fresh database would not.

    An installation upgrading from schema 43 has real `acoustic_analysis_
    runs` rows, but every one of them is already terminal (`completed`/
    `failed` -- the prior milestone only ever created rows directly as
    `processing` then completed them synchronously in the same request), so
    backfilling `consecutive_failure_count=0`/`next_retry_at=NULL`/
    `claimed_by=NULL`/`claimed_at=NULL` for existing rows is exactly the
    truthful state: none of them were ever retried or claimed by the new
    reconcile loop. Every existing `media_assets` row backfills `acoustic_
    working_segment=0` -- also exactly truthful: no automatic capture
    pipeline existed before this milestone, so nothing could have been
    imported by it."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Acoustic runtime queue migration requires local SQLite storage."
        )
    if inspect(connection).has_table("acoustic_analysis_runs"):
        run_columns = {
            column["name"] for column in inspect(connection).get_columns("acoustic_analysis_runs")
        }
        if "consecutive_failure_count" not in run_columns:
            connection.exec_driver_sql(
                "ALTER TABLE acoustic_analysis_runs "
                "ADD COLUMN consecutive_failure_count INTEGER NOT NULL DEFAULT 0"
            )
        if "next_retry_at" not in run_columns:
            connection.exec_driver_sql(
                "ALTER TABLE acoustic_analysis_runs ADD COLUMN next_retry_at DATETIME"
            )
        if "claimed_by" not in run_columns:
            connection.exec_driver_sql(
                "ALTER TABLE acoustic_analysis_runs ADD COLUMN claimed_by TEXT"
            )
        if "claimed_at" not in run_columns:
            connection.exec_driver_sql(
                "ALTER TABLE acoustic_analysis_runs ADD COLUMN claimed_at DATETIME"
            )
        connection.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_acoustic_analysis_runs_status_created "
            "ON acoustic_analysis_runs (status, created_at)"
        )
    if inspect(connection).has_table("media_assets"):
        media_asset_columns = {
            column["name"] for column in inspect(connection).get_columns("media_assets")
        }
        if "acoustic_working_segment" not in media_asset_columns:
            connection.exec_driver_sql(
                "ALTER TABLE media_assets "
                "ADD COLUMN acoustic_working_segment BOOLEAN NOT NULL DEFAULT 0"
            )


def _migrate_to_acoustic_species_scoped_idempotency(connection: Connection) -> None:
    """Multimodal Observation & Soundscape v1, Phase B (see docs/
    multimodal-observation-soundscape-v1-contract.md, "Acoustic
    idempotency"): add the species-scoped unique index backstopping
    `SpeciesSuggestionModel.__table_args__` on `species_suggestions`.

    Provably safe to add on any pre-existing real database without a
    defensive cleanup pass first: the *prior* idempotency key --
    `(media_asset_id, window_start_ms, window_end_ms, adapter_id)`, with no
    species column at all -- already guaranteed at most one row could ever
    exist per that 4-tuple, regardless of species. The new key is that same
    4-tuple plus `suggested_label`; since the old code already permitted at
    most one row for the whole 4-tuple, no two rows can already share the
    *stricter* 5-tuple either. A pre-fix installation that hit the actual
    defect (two distinct species detected in one identical merged window)
    has exactly one persisted row for that window today, not two
    duplicates -- the second species' row was silently never created at
    all, not created twice and left behind. This migration only ever adds
    an index; it writes no data.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Acoustic species-scoped idempotency migration requires local SQLite storage."
        )
    # Mirrors `_migrate_to_acoustic_runtime_queue`'s own `has_table` guard,
    # immediately above: a handful of narrow migration-path tests construct
    # a deliberately minimal ad-hoc database (only the handful of tables
    # their own specific version range needs) rather than a full schema, so
    # this must not assume `species_suggestions` exists.
    if inspect(connection).has_table("species_suggestions"):
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_species_suggestions_acoustic_idempotency "
            "ON species_suggestions (media_asset_id, window_start_ms, window_end_ms, adapter_id, suggested_label) "
            "WHERE window_start_ms IS NOT NULL"
        )


def _migrate_to_visit_multimodal_association(connection: Connection) -> None:
    """Multimodal Observation & Soundscape v1, Phase D/E: add the empty,
    additive `visit_associations` table (see docs/multimodal-observation-
    soundscape-v1-contract.md).

    No row is seeded here: the table starts genuinely empty for every
    installation, including one upgrading from real historical acoustic and
    visual candidate Visits -- this migration never backfills association
    history retroactively (an upgraded installation's multimodal
    association mechanism starts exactly as cold as a brand-new one),
    mirroring `_migrate_to_scene_confusor_regions`'s own "additive table, no
    seeded row" precedent exactly.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Visit multimodal association migration requires local SQLite storage."
        )
    Base.metadata.tables["visit_associations"].create(bind=connection, checkfirst=True)


def _migrate_to_cross_camera_visit_association(connection: Connection) -> None:
    """Camera / Source + Multi-Camera Maturity v1, Phase I: add the empty,
    additive `cross_camera_visit_associations` table (see
    docs/camera-source-multi-camera-maturity-v1-contract.md).

    A deliberate sibling table, not an ALTER of `visit_associations`: that
    table's `acoustic_visit_id` is `NOT NULL` and SQLite has no `ALTER
    COLUMN` to loosen it, so a same-modality (visual+visual) pair gets its
    own honestly-named columns instead (see `CrossCameraVisitAssociationModel`'s
    own docstring). No row is seeded here, mirroring `_migrate_to_visit_
    multimodal_association`'s own "additive table, no seeded row, no
    retroactive backfill" precedent exactly -- an upgraded installation's
    cross-camera association mechanism starts exactly as cold as a
    brand-new one.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Cross-camera visit association migration requires local SQLite storage."
        )
    Base.metadata.tables["cross_camera_visit_associations"].create(bind=connection, checkfirst=True)


def _migrate_to_camera_node_transport_ingestion(connection: Connection) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase E: add the empty,
    additive `camera_node_transport_ingestions` table (see
    docs/appliance-storage-privacy-recovery-v1-contract.md). Closes the
    standing gap where a completed Camera Node WAN-transport item had a
    durable filesystem home
    (`mockingbird.storage.camera_node_transport_ledger.TransportLedger`)
    but no durable, idempotent record of whether it had been consumed into
    a MediaAsset -- see `CameraNodeTransportIngestionModel`'s own docstring
    and `ProductRepository.consume_camera_node_transport_item`.

    No backfill, no seeded row -- mirrors every other additive-table
    migration in this file. An upgraded installation's existing
    completed-but-unconsumed transport items (if any) are picked up by the
    very next consumption sweep, exactly like a brand-new installation
    would be; nothing about the transport ledger's own filesystem layout
    changes.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Camera Node transport ingestion migration requires local SQLite storage."
        )
    Base.metadata.tables["camera_node_transport_ingestions"].create(bind=connection, checkfirst=True)


def _migrate_to_rejected_analysis_media_retention(connection: Connection) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase D: add the
    nullable `rejected_analysis_media_age_days` column to
    `storage_retention_settings` -- the one new, opt-in retention lever for
    the `linked_evidence_or_analysis` category (see `StorageRetentionSettingsModel`'s
    own docstring). `None` for every existing row (and the default for a
    freshly-created one), preserving today's exact protected-forever
    behavior for this category on every installation until a user
    explicitly opts in -- an honest "not configured," never a fabricated
    threshold, mirroring `_migrate_to_media_asset_duration`'s identical
    nullable-no-backfill discipline.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Rejected-analysis-media retention migration requires local SQLite storage."
        )
    if not inspect(connection).has_table("storage_retention_settings"):
        return
    columns = {
        column["name"] for column in inspect(connection).get_columns("storage_retention_settings")
    }
    if "rejected_analysis_media_age_days" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE storage_retention_settings ADD COLUMN rejected_analysis_media_age_days INTEGER"
        )


def _migrate_to_local_identity_multi_user_access(connection: Connection) -> None:
    """Local Identity, Multi-User & Organization Access v1: add local human
    accounts, server-side sessions, a generic audit trail, and installation
    display metadata -- see docs/local-identity-multi-user-contract.md.

    Every operation here is additive (new tables, or one new nullable
    column on the pre-existing `review_labels` table) and nothing is
    backfilled: an upgraded installation starts with zero `users` rows,
    exactly the "no users exist" state first-run bootstrap already expects
    (see `mockingbird.api.auth`), and every pre-existing `review_labels`
    row simply gets `reviewed_by_user_id = NULL` -- honestly representing
    "no signed-in actor," never fabricating one (mirrors this same table's
    existing `review_origin`/`reviewer_identity` "legacy_unattributed"/
    `NULL` discipline from the schema-32 migration above).
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Local identity / multi-user migration requires local SQLite storage."
        )
    for table_name in (
        "users",
        "user_sessions",
        "audit_log_entries",
        "installation_settings",
    ):
        Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)

    if inspect(connection).has_table("review_labels"):
        columns = {
            column["name"] for column in inspect(connection).get_columns("review_labels")
        }
        if "reviewed_by_user_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE review_labels ADD COLUMN reviewed_by_user_id VARCHAR"
            )


def _migrate_to_environmental_context_foundation(connection: Connection) -> None:
    """Environmental Context Foundation v1: add the opt-in Place location
    setting and the provider-neutral environmental-context observation
    table -- see docs/environmental-context-foundation-v1-contract.md.

    Purely additive (two new tables, nothing backfilled): an upgraded
    installation starts with no configured location and zero context
    records, identical to a brand-new install -- this milestone's own
    "local-first, absence-safe" contract applies to itself, not only to
    installations created after it shipped.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Environmental context migration requires local SQLite storage."
        )
    for table_name in (
        "environmental_context_settings",
        "environmental_context_records",
    ):
        Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)


def _migrate_to_habitat_phenology_foundation(connection: Connection) -> None:
    """Habitat & Phenology Foundation v1: add the durable Place habitat
    profile table and the dated/interval phenology observation table --
    see docs/habitat-phenology-foundation-v1-contract.md.

    Purely additive (two new tables, nothing backfilled): an upgraded
    installation starts with zero habitat facts and zero phenology
    observations, identical to a brand-new install -- this feature's own
    "absence must not imply false, only 'not recorded'" contract applies
    to itself, not only to installations created after it shipped. Neither
    table touches `visits`, `events`, `review_labels`, or any other
    wildlife-truth table.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Habitat & Phenology migration requires local SQLite storage."
        )
    for table_name in (
        "place_habitat_facts",
        "place_phenology_observations",
    ):
        Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)


def _migrate_to_scene_confusor_reviewed_evidence_learning(connection: Connection) -> None:
    """Site-Specific Learning & Local Adaptation v1: two small, additive
    columns closing a real gap found in the already-shipped scene-confusor
    suspicion mechanism (schema 34) -- see docs/scene-confusor-suspicion-
    contract.md, "Reviewed-negative-evidence suspicion" and "Reset /
    disable."

    `review_labels.scene_confusor_region_id` (nullable, no default):
    records which region, if any, a specific reviewed correction actually
    incremented, so a later revision or reopen of that exact correction can
    retract exactly that contribution instead of leaving it stale forever.
    Every row that already exists at migration time reads back `NULL` --
    honest "this historical row predates the column," never a fabricated
    retroactive link (mirrors `_migrate_to_media_asset_duration`'s identical
    nullable-no-backfill discipline). A pre-existing region's own
    `reviewed_real_count`/`reviewed_false_count` totals are themselves left
    exactly as they already were: this migration does not, and cannot
    honestly, reconstruct which historical label produced which increment.

    `observation_authority_settings.scene_confusor_reviewed_evidence_enabled`
    (`NOT NULL DEFAULT 0`): the new operator-facing production-activation
    control for the reviewed-negative-evidence suspicion path. Every Stream
    that already has a settings row starts *without* it applying to
    production admission -- conservative by default (acceptance correction,
    2026-08-24), not merely "harmless by default": `min_reviewed_false_to_
    suspect` (see `scene_confusor.DEFAULT_MIN_REVIEWED_FALSE_TO_SUSPECT`) is
    disclosed as a candidate threshold pending organic field validation, so
    activating it for any given Stream's own production admission is left to
    an explicit operator decision (`ProductRepository.set_scene_confusor_
    reviewed_evidence_enabled`), not a silent migration default. This gates
    production admission only -- reviewed-evidence state accumulation,
    provenance, reversibility, and status/counterfactual reporting are all
    unconditional and unaffected by this column's value.

    Purely additive: neither column touches `visits`, `events`, or any
    other wildlife-truth table.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Scene confusor reviewed-evidence learning migration requires local SQLite storage."
        )
    if inspect(connection).has_table("review_labels"):
        columns = {column["name"] for column in inspect(connection).get_columns("review_labels")}
        if "scene_confusor_region_id" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE review_labels ADD COLUMN scene_confusor_region_id VARCHAR"
            )
    if inspect(connection).has_table("observation_authority_settings"):
        columns = {
            column["name"] for column in inspect(connection).get_columns("observation_authority_settings")
        }
        if "scene_confusor_reviewed_evidence_enabled" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE observation_authority_settings "
                "ADD COLUMN scene_confusor_reviewed_evidence_enabled BOOLEAN NOT NULL DEFAULT 0"
            )


def _migrate_to_environmental_context_weather(connection: Connection) -> None:
    """Environmental Context v2: one additive, `NOT NULL DEFAULT 0` column
    gating outbound weather-provider network requests -- see
    docs/environmental-context-v2-contract.md "Phase 1" / "Phase 26".

    `environmental_context_records` (schema 51) needs no migration at all:
    its `value_numeric`/`value_text`/`unit`/`observed_at_end` columns were
    already shaped, at v1, to hold a future provider's numeric metrics
    without a schema change -- confirmed by direct inspection before this
    migration was written. The only genuine gap is consent: v1's
    `environmental_context_settings` has no notion of "the user has agreed
    to an outbound network call," because its only v1 writer (`solar_local`)
    never makes one.

    `weather_enabled` (`NOT NULL DEFAULT 0`): every existing installation --
    including one that already has `coarse_latitude`/`coarse_longitude`
    configured for local solar computation -- starts with weather requests
    off. Configuring a location for offline solar/daylight must never
    silently also start sending that location to an external provider over
    the network; that remains a second, explicit, separate opt-in (Phase 16
    / "Privacy / location"). A brand-new installation starts identically:
    `weather_enabled=False` until the user explicitly enables it.

    Purely additive: does not touch `visits`, `events`, `review_labels`, or
    any other wildlife-truth table.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Environmental Context v2 migration requires local SQLite storage."
        )
    if inspect(connection).has_table("environmental_context_settings"):
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("environmental_context_settings")
        }
        if "weather_enabled" not in columns:
            connection.exec_driver_sql(
                "ALTER TABLE environmental_context_settings "
                "ADD COLUMN weather_enabled BOOLEAN NOT NULL DEFAULT 0"
            )


def _migrate_to_place_features_habitat_change(connection: Connection) -> None:
    """Place Features & Habitat Change v2: add the durable Place Feature
    table and the Place Feature Change Event table -- see
    docs/place-features-habitat-change-v2-contract.md.

    Purely additive (two new tables, nothing backfilled), mirroring
    `_migrate_to_habitat_phenology_foundation` exactly: an upgraded
    installation starts with zero Features and zero change events,
    identical to a brand-new install. Neither table touches `visits`,
    `events`, `review_labels`, or any other wildlife-truth table.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Place Features & Habitat Change migration requires local SQLite storage."
        )
    for table_name in (
        "place_features",
        "place_feature_change_events",
    ):
        Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)


def _migrate_to_notification_preferences(connection: Connection) -> None:
    """Calm Attention & Notifications v1: add the per-user notification
    preferences table (see docs/calm-attention-notifications-v1-report.md).

    Purely additive (one new table, nothing backfilled): an upgraded
    installation starts with zero preference rows, and every existing
    `get_notification_preferences` caller lazily creates a row with the
    same conservative defaults a brand-new installation would get --
    identical to a fresh install. Does not touch `product_alerts`,
    `users`, or any other existing table; `ProductAlertModel.category`
    is a plain `String` column with no database-level enum/check
    constraint, so the new `"insight"` category value needs no migration
    of its own.
    """

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Calm Attention & Notifications migration requires local SQLite storage."
        )
    Base.metadata.tables["user_notification_preferences"].create(bind=connection, checkfirst=True)


def _migrate_to_ecological_interoperability(connection: Connection) -> None:
    """Ecological Interoperability & Submission Workflows v1: add the two
    additive, empty-on-upgrade tables (see docs/ecological-interoperability-
    submission-v1-contract.md) -- `ecological_taxonomy_mappings` (a bounded,
    reusable "MockingBird label -> destination taxon" resolution cache) and
    `ecological_submission_records` (a durable per-Visit external-submission-
    preparation record). Mirrors `_migrate_to_research_collections`'s own
    "additive table(s), no seeded row" pattern exactly: an installation
    upgrading from schema 56 has never prepared an external submission or
    resolved a destination taxonomy mapping, so it correctly starts with
    none of either."""

    if connection.dialect.name != "sqlite":
        raise DatabaseSchemaCompatibilityError(
            "Ecological Interoperability migration requires local SQLite storage."
        )
    for table_name in ("ecological_taxonomy_mappings", "ecological_submission_records"):
        Base.metadata.tables[table_name].create(bind=connection, checkfirst=True)


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
    38: _migrate_to_camera_node_replacement_provenance,
    39: _migrate_to_camera_onvif_profiles,
    40: _migrate_to_media_asset_duration,
    41: _migrate_to_recorded_media_analysis_runs,
    42: _migrate_to_research_collections,
    43: _migrate_to_acoustic_observation_foundation,
    44: _migrate_to_acoustic_runtime_queue,
    45: _migrate_to_acoustic_species_scoped_idempotency,
    46: _migrate_to_visit_multimodal_association,
    47: _migrate_to_cross_camera_visit_association,
    48: _migrate_to_camera_node_transport_ingestion,
    49: _migrate_to_rejected_analysis_media_retention,
    50: _migrate_to_local_identity_multi_user_access,
    51: _migrate_to_environmental_context_foundation,
    52: _migrate_to_habitat_phenology_foundation,
    53: _migrate_to_scene_confusor_reviewed_evidence_learning,
    54: _migrate_to_environmental_context_weather,
    55: _migrate_to_place_features_habitat_change,
    56: _migrate_to_notification_preferences,
    57: _migrate_to_ecological_interoperability,
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
#
# Appliance / Storage / Privacy / Recovery v1, Phase C: a graduated
# healthy/getting_low/action_recommended/critical ladder, not a single
# binary threshold -- `LOW_DISK_FREE_BYTES_THRESHOLD`/`LOW_DISK_FREE_RATIO_
# THRESHOLD` are unchanged and remain exactly the "action_recommended"
# boundary (so `is_low_space`, already read by Doctor and `/api/product/
# health`, keeps its existing meaning and trigger point for every current
# caller). `GETTING_LOW_*` is a new, earlier warning; `CRITICAL_*` is a new,
# more severe tier for "ingestion genuinely at risk." Like `BACKUP_STALE_
# AFTER_DAYS`, these are this milestone's own disclosed judgment call --
# no pre-existing canonical policy existed for either new tier.
GETTING_LOW_DISK_FREE_BYTES_THRESHOLD = 5_000_000_000
GETTING_LOW_DISK_FREE_RATIO_THRESHOLD = 0.15
LOW_DISK_FREE_BYTES_THRESHOLD = 1_000_000_000
LOW_DISK_FREE_RATIO_THRESHOLD = 0.05
CRITICAL_DISK_FREE_BYTES_THRESHOLD = 200_000_000
CRITICAL_DISK_FREE_RATIO_THRESHOLD = 0.01


@dataclass(frozen=True)
class LocalStorageDiskStatus:
    total_bytes: int
    free_bytes: int
    is_writable: bool

    @property
    def storage_health_tier(self) -> str:
        """One of `healthy`/`getting_low`/`action_recommended`/`critical` --
        see the module-level threshold comment above for the defensible,
        disclosed boundaries. `total_bytes <= 0` (disk usage could not be
        read at all) reads as `healthy` rather than fabricating alarm from
        a fact this probe does not actually have -- the separate
        `is_writable` flag already carries the "something is genuinely
        wrong" signal for that case."""

        if self.total_bytes <= 0:
            return "healthy"
        free_ratio = self.free_bytes / self.total_bytes
        if (
            self.free_bytes < CRITICAL_DISK_FREE_BYTES_THRESHOLD
            or free_ratio < CRITICAL_DISK_FREE_RATIO_THRESHOLD
        ):
            return "critical"
        if (
            self.free_bytes < LOW_DISK_FREE_BYTES_THRESHOLD
            or free_ratio < LOW_DISK_FREE_RATIO_THRESHOLD
        ):
            return "action_recommended"
        if (
            self.free_bytes < GETTING_LOW_DISK_FREE_BYTES_THRESHOLD
            or free_ratio < GETTING_LOW_DISK_FREE_RATIO_THRESHOLD
        ):
            return "getting_low"
        return "healthy"

    @property
    def is_low_space(self) -> bool:
        # Unchanged trigger point (existing callers, e.g. Doctor and
        # `/api/product/health`'s `storage_low_space`, keep today's exact
        # behavior) -- now expressed in terms of the tier above rather than
        # a second, independently-maintained copy of the same comparison.
        return self.storage_health_tier in {"action_recommended", "critical"}


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


def _run_schema_migration_loop(connection: Connection, version: int) -> int:
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


def _run_migrations_with_transactional_ddl(engine: Engine, version: int) -> int:
    """Run the schema-migration loop against a dedicated, short-lived
    engine with genuine transactional DDL -- never the shared, long-lived
    `engine` the rest of the application (and every concurrent request-
    handling connection, for the entire remaining process lifetime)
    continues to use afterward.

    First-Hour Onboarding + Whole-Product Observability Closure v1 ("C4
    migration hardening"): a real, confirmed gap found by this milestone's
    own new mid-chain-migration-failure test -- pysqlite's default DBAPI
    behavior implicitly commits before a DDL statement (CREATE TABLE/ALTER
    TABLE), regardless of an enclosing SQLAlchemy `engine.begin()` block.
    Before this fix, a migration function that successfully ran a
    `CREATE TABLE` and then a *later* migration in the same upgrade chain
    raised left that new, half-migrated table permanently in place even
    though the schema-version row correctly rolled back to the pre-upgrade
    version -- a partially-applied upgrade silently disguised as a cleanly
    -rejected one. The fix is SQLAlchemy's own documented pysqlite
    "Serializable isolation / Savepoints / Transactional DDL" recipe
    (disable pysqlite's own implicit transaction handling entirely via
    `isolation_level = None`, and issue every `BEGIN` explicitly instead,
    which pysqlite *does* honor for DDL) -- but a first attempt applying it
    to `create_database_engine` itself (the shared engine/connection-pool
    factory the rest of the app also uses) measurably changed SQLite
    locking/timing behavior for ordinary concurrent request handling,
    found via this milestone's own repeated real-test comparison: a
    consistent, reproducible failure-rate increase (0/4 at baseline vs.
    2/3 with the shared-engine version) in an unrelated multi-stream
    concurrent-authority test. Scoping the fix to a dedicated engine used
    only for this one, synchronous, once-per-startup call -- before the
    shared engine's own connection pool is used for anything else, so a
    second temporary connection to the same SQLite file adds no real
    contention -- keeps the correctness fix without that side effect.
    """

    ephemeral_test_database = _is_ephemeral_pytest_sqlite_database(str(engine.url))
    migration_engine = create_engine(engine.url, connect_args={"check_same_thread": False})

    @event.listens_for(migration_engine, "connect")
    def _configure_for_transactional_ddl(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=5000")
            if ephemeral_test_database:
                cursor.execute("PRAGMA synchronous=OFF")
        finally:
            cursor.close()
        dbapi_connection.isolation_level = None

    @event.listens_for(migration_engine, "begin")
    def _emit_explicit_begin(connection: Connection) -> None:
        connection.exec_driver_sql("BEGIN")

    try:
        with migration_engine.begin() as connection:
            version = _run_schema_migration_loop(connection, version)
    finally:
        migration_engine.dispose()
    return version


def _validate_or_migrate_schema_version(
    engine: Engine,
    recorded_version: int,
    *,
    pre_migration_hook: Callable[[int, int], str | None] | None = None,
) -> tuple[int, str | None]:
    if recorded_version > CURRENT_DATABASE_SCHEMA_VERSION:
        raise DatabaseSchemaCompatibilityError(
            "This MockingBird database was created by a newer app version. "
            "Upgrade MockingBird before opening it."
        )
    if recorded_version < CURRENT_DATABASE_SCHEMA_VERSION and not database_schema_version_is_compatible(
        recorded_version
    ):
        # Checked upfront, before the pre-migration-backup hook below ever
        # fires -- a database with no complete registered migration chain to
        # `CURRENT_DATABASE_SCHEMA_VERSION` is never going to migrate
        # successfully regardless (this is the same fact `_run_schema_
        # migration_loop` would eventually discover mid-chain), so there is
        # no reason to attempt a backup of it first. Real installations never
        # hit this -- `database_schema_version_is_compatible` reuses the
        # exact same registered-migration-chain check `LocalBackupManager`
        # itself already enforces before accepting a backup's own recorded
        # version, so a database this old could not have been safely backed
        # up here either.
        raise DatabaseSchemaCompatibilityError(
            "This MockingBird database needs an explicit migration before it "
            "can be opened safely."
        )

    version = recorded_version
    backup_id: str | None = None
    if version < CURRENT_DATABASE_SCHEMA_VERSION:
        # Appliance / Update / Recovery: a real migration is genuinely about
        # to mutate this database, in place, with no way back except a
        # restored backup (see docs/appliance-storage-privacy-recovery-v1-
        # contract.md's "Bounded update-readiness review" -- this hook is
        # exactly the "pre-upgrade backup trigger" that review named and
        # deliberately deferred). Firing it here, before either migration
        # branch below runs, and letting any exception it raises propagate
        # unmodified, means a safety backup that cannot be created safely
        # stops the upgrade before any destructive mutation -- never after.
        if pre_migration_hook is not None:
            backup_id = pre_migration_hook(version, CURRENT_DATABASE_SCHEMA_VERSION)
        if engine.dialect.name == "sqlite":
            version = _run_migrations_with_transactional_ddl(engine, version)
        else:
            # Structurally unreachable in practice -- every migration
            # function itself immediately raises DatabaseSchemaCompatibilityError
            # for a non-SQLite dialect (see e.g. _migrate_to_zone_optional_
            # motion_evidence) -- kept only so a hypothetical future non-
            # SQLite engine still fails the same way it always has, rather
            # than through this SQLite-specific transactional-DDL path.
            with engine.begin() as connection:
                version = _run_schema_migration_loop(connection, version)
    return version, backup_id


def initialize_database(
    engine: Engine,
    *,
    pre_migration_hook: Callable[[int, int], str | None] | None = None,
) -> DatabaseSchemaStatus:
    """Validate compatibility, create the current schema, and record its version.

    `pre_migration_hook`, when given, is called at most once -- only when a
    pre-existing (not brand-new) database is about to be migrated forward --
    as `(from_version, to_version) -> backup_id | None`, before any migration
    runs. It never fires for a brand-new database (nothing to preserve yet)
    or an already-current one (no mutation about to happen). See
    `_validate_or_migrate_schema_version` for the exact fail-closed contract.
    """

    integrity_check = _sqlite_integrity_check(engine)
    recorded_version = _read_recorded_schema_version(engine)
    migrated_from_version: int | None = None
    pre_migration_backup_id: str | None = None
    if recorded_version is not None:
        starting_version = recorded_version
        recorded_version, pre_migration_backup_id = _validate_or_migrate_schema_version(
            engine, recorded_version, pre_migration_hook=pre_migration_hook
        )
        if recorded_version != starting_version:
            migrated_from_version = starting_version
            # docs/appliance-storage-privacy-recovery-v1-contract.md's
            # "Bounded update-readiness review" named this exactly: "a
            # health check *after* migration but *before* declaring the
            # upgrade successful." A migration completing without raising
            # only proves no *exception* happened, not that the resulting
            # database is actually healthy -- re-running the same integrity
            # check the pre-migration snapshot above already used (never
            # skipped, never assumed) is what actually proves that, and its
            # result -- not the pre-migration one -- is what gets reported
            # and gates readiness below. Only paid on a genuine migration;
            # an ordinary already-current launch checks integrity once, same
            # as before this change.
            integrity_check = _sqlite_integrity_check(engine)

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
        migrated_from_version=migrated_from_version,
        pre_migration_backup_id=pre_migration_backup_id,
    )
