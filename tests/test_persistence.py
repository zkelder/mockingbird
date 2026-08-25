from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mockingbird.api.schemas import (
    DatasetExportCreate,
    MotionEvidenceCreateRequest,
    Point,
    ReviewCorrectionCreate,
    ZoneCreate,
    ZoneUpdate,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    DatabaseSchemaCompatibilityError,
    create_database_engine,
)
from mockingbird.storage.models import (
    BioClipIdentificationAttemptModel,
    CameraSourceModel,
    EnvironmentalContextSettingsModel,
    MediaAssetModel,
    StreamModel,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
BIRD_VISIT_ID = "visit-bird-feeder-001"


def repository_for(path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{path}")


def test_seed_data_loads_into_new_database(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "mockingbird.sqlite3")

    assert repository.list_sources()[0].id == "source-backyard-demo"
    assert repository.list_streams()[0].id == STREAM_ID
    assert len(repository.zones_for_stream(STREAM_ID)) == 3
    assert repository.review_queue_items()


def test_created_zone_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    created_zone = repository.create_zone(
        ZoneCreate(
            stream_id=STREAM_ID,
            name="Birdbath corner",
            zone_type="birdbath",
            polygon=[
                Point(x=0.68, y=0.18),
                Point(x=0.88, y=0.18),
                Point(x=0.88, y=0.42),
                Point(x=0.68, y=0.42),
            ],
        )
    )

    reloaded_repository = repository_for(db_path)
    persisted_zone = reloaded_repository.get_zone(created_zone.id)

    assert persisted_zone is not None
    assert persisted_zone.name == "Birdbath corner"
    assert persisted_zone.zone_type == "birdbath"


def test_zone_update_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    repository.update_zone(
        FEEDER_ZONE_ID,
        ZoneUpdate(name="Feeder perch", zone_type="perch", is_active=False),
    )

    reloaded_repository = repository_for(db_path)
    persisted_zone = reloaded_repository.get_zone(FEEDER_ZONE_ID)

    assert persisted_zone is not None
    assert persisted_zone.name == "Feeder perch"
    assert persisted_zone.zone_type == "perch"
    assert persisted_zone.is_active is False


def test_review_correction_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="carolina_wren",
            notes="Persisted correction.",
            review_origin="human",
        )
    )

    reloaded_repository = repository_for(db_path)
    persisted_visit = reloaded_repository.get_visit(BIRD_VISIT_ID)
    persisted_labels = reloaded_repository.list_review_labels()

    assert persisted_visit is not None
    assert persisted_visit.reviewed_label == "carolina_wren"
    assert any(label.target_id == BIRD_VISIT_ID for label in persisted_labels)


def test_review_queue_reflects_persisted_correction_state(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            review_origin="human",
        )
    )

    reloaded_repository = repository_for(db_path)

    assert all(
        item.visit_id != BIRD_VISIT_ID
        for item in reloaded_repository.review_queue_items()
    )


def test_dataset_export_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    dataset_export = repository.create_dataset_export(
        DatasetExportCreate(name="Persisted reviewed dataset")
    )

    reloaded_repository = repository_for(db_path)
    persisted_export = reloaded_repository.get_dataset_export(dataset_export.id)
    persisted_manifest = reloaded_repository.build_dataset_manifest(dataset_export.id)

    assert persisted_export is not None
    assert persisted_export.name == "Persisted reviewed dataset"
    assert persisted_manifest is not None
    assert persisted_manifest.export.id == dataset_export.id


def test_analytics_summary_reflects_persisted_correction_state(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)

    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="carolina_wren",
            review_origin="human",
        )
    )

    reloaded_repository = repository_for(db_path)
    analytics = reloaded_repository.analytics_summary()

    assert analytics.needs_review_count == 0
    assert analytics.species_counts["carolina_wren"] == 1


def test_repeated_initialization_does_not_duplicate_seed_records(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"

    repository_for(db_path)
    reloaded_repository = repository_for(db_path)

    assert len(reloaded_repository.list_sources()) == 1
    assert len(reloaded_repository.zones_for_stream(STREAM_ID)) == 3
    assert len(reloaded_repository.list_dataset_exports()) == 1


def test_database_schema_record_and_integrity_survive_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    first_repository = repository_for(db_path)
    reloaded_repository = repository_for(db_path)

    assert first_repository.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
    assert first_repository.schema_status.initialized_schema_record is True
    assert first_repository.schema_status.integrity_check == "ok"
    assert reloaded_repository.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
    assert reloaded_repository.schema_status.initialized_schema_record is False
    assert reloaded_repository.schema_status.integrity_check == "ok"


def test_bioclip_attempt_schema_supports_incomplete_then_terminal_evidence(
    tmp_path: Path,
) -> None:
    repository = repository_for(tmp_path / "mockingbird.sqlite3")
    started_at = datetime.now(UTC)
    with repository.engine.begin() as connection:
        connection.execute(
            MediaAssetModel.__table__.insert().values(
                id="media-bioclip-schema",
                source_id="source-backyard-demo",
                stream_id=STREAM_ID,
                filename="bioclip-schema.jpg",
                content_type="image/jpeg",
                media_type="image",
                local_path="managed://bioclip-schema.jpg",
                original_filename="bioclip-schema.jpg",
                file_size_bytes=64,
                created_at=started_at,
                notes=None,
            )
        )
        connection.execute(
            BioClipIdentificationAttemptModel.__table__.insert().values(
                id="bioclip-attempt-schema",
                target_type="visit",
                target_id=BIRD_VISIT_ID,
                event_id="event-bird-feeder-001",
                visit_id=BIRD_VISIT_ID,
                media_asset_id="media-bioclip-schema",
                source_id="source-backyard-demo",
                stream_id=STREAM_ID,
                zone_id=FEEDER_ZONE_ID,
                motion_evidence_id=None,
                detection_proposal_id=None,
                resulting_species_suggestion_id=None,
                adapter_id="bioclip-2",
                started_at=started_at,
                completed_at=None,
                duration_ms=None,
                timeout_limit_ms=30_000,
                timeout_exceeded=False,
                outcome=None,
                crop_source="activity",
                crop_provenance_json='{"source":"activity"}',
                model_provenance_json=None,
                preprocessing_json=None,
                candidate_manifest_json=None,
                candidate_set_count=None,
                candidate_set_sha256=None,
                candidate_set_version=None,
                candidate_manifest_complete=False,
                error_code=None,
                error_stage=None,
                error_detail=None,
                provenance_schema_version=1,
            )
        )

    completed_at = datetime.now(UTC)
    with repository.engine.begin() as connection:
        connection.execute(
            BioClipIdentificationAttemptModel.__table__.update()
            .where(BioClipIdentificationAttemptModel.id == "bioclip-attempt-schema")
            .values(
                completed_at=completed_at,
                duration_ms=19,
                outcome="succeeded",
                resulting_species_suggestion_id="species-suggestion-schema-link",
                model_provenance_json='{"model_id":"bioclip-2"}',
                preprocessing_json='{"input":"rgb"}',
                candidate_manifest_json='[{"normalized_label":"unknown_bird"}]',
                candidate_set_count=1,
                candidate_set_sha256="a" * 64,
                candidate_set_version="labels-sha256-v1",
                candidate_manifest_complete=True,
            )
        )

    with repository.engine.connect() as connection:
        persisted = (
            connection.execute(
                BioClipIdentificationAttemptModel.__table__.select().where(
                    BioClipIdentificationAttemptModel.id == "bioclip-attempt-schema"
                )
            )
            .mappings()
            .one()
        )
    assert persisted["outcome"] == "succeeded"
    assert persisted["resulting_species_suggestion_id"] == (
        "species-suggestion-schema-link"
    )
    assert persisted["candidate_manifest_complete"] is True

    with pytest.raises(IntegrityError):
        with repository.engine.begin() as connection:
            connection.execute(
                BioClipIdentificationAttemptModel.__table__.insert().values(
                    id="bioclip-attempt-invalid-timeout",
                    target_type="visit",
                    target_id=BIRD_VISIT_ID,
                    event_id="event-bird-feeder-001",
                    visit_id=BIRD_VISIT_ID,
                    media_asset_id="media-bioclip-schema",
                    adapter_id="bioclip-2",
                    started_at=started_at,
                    completed_at=completed_at,
                    duration_ms=30_000,
                    timeout_limit_ms=30_000,
                    timeout_exceeded=False,
                    outcome="timed_out",
                    candidate_manifest_complete=False,
                    error_code="inference_timeout",
                    error_stage="inference",
                    error_detail="The local inference limit was exceeded.",
                    provenance_schema_version=1,
                )
            )
    repository.close()


def test_schema_two_migrates_motion_evidence_to_optional_zone_without_data_loss(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing = repository.create_motion_evidence(
        MotionEvidenceCreateRequest(
            stream_id=STREAM_ID,
            zone_id=FEEDER_ZONE_ID,
            peak_changed_ratio=0.25,
            triggered_frame_count=2,
            scoring_config={"source": "schema_two_fixture"},
        )
    )
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE motion_evidence_schema_two (
                id VARCHAR NOT NULL PRIMARY KEY,
                source_id VARCHAR,
                stream_id VARCHAR,
                zone_id VARCHAR NOT NULL,
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
                notes TEXT
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO motion_evidence_schema_two SELECT * FROM motion_evidence"
        )
        connection.exec_driver_sql("DROP TABLE motion_evidence")
        connection.exec_driver_sql(
            "ALTER TABLE motion_evidence_schema_two RENAME TO motion_evidence"
        )
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 2 WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        persisted = migrated.get_motion_evidence(existing.id)
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert persisted is not None
        assert persisted.zone_id == FEEDER_ZONE_ID

        zone_optional = migrated.create_motion_evidence(
            MotionEvidenceCreateRequest(
                stream_id=STREAM_ID,
                zone_id=None,
                peak_changed_ratio=0.2,
                triggered_frame_count=1,
                scoring_config={
                    "source": "automatic_activity",
                    "activity_region_kind": "auto_area",
                    "activity_region_id": "auto-region:migration-test",
                },
            )
        )
        assert zone_optional.zone_id is None

        with migrated.engine.connect() as connection:
            zone_column = next(
                row
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(motion_evidence)"
                )
                if row[1] == "zone_id"
            )
        assert zone_column[3] == 0
    finally:
        migrated.close()


def test_schema_three_adds_empty_bioclip_attempt_evidence_without_data_loss(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_motion = repository.create_motion_evidence(
        MotionEvidenceCreateRequest(
            stream_id=STREAM_ID,
            zone_id=FEEDER_ZONE_ID,
            peak_changed_ratio=0.31,
            triggered_frame_count=3,
            scoring_config={"source": "schema_three_fixture"},
        )
    )
    existing_label = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            notes="Preserved across the attempt-evidence migration.",
            review_origin="human",
        )
    ).review_label
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE bioclip_identification_attempts")
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 3 WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert migrated.get_motion_evidence(existing_motion.id) is not None
        assert any(
            label.id == existing_label.id for label in migrated.list_review_labels()
        )
        with migrated.engine.connect() as connection:
            attempt_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM bioclip_identification_attempts"
            ).scalar_one()
        assert attempt_count == 0
    finally:
        migrated.close()


def test_newer_database_version_is_rejected_without_modification(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    newer_version = CURRENT_DATABASE_SCHEMA_VERSION + 1
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = ? WHERE singleton_id = 1",
            (newer_version,),
        )
    repository.engine.dispose()

    with pytest.raises(DatabaseSchemaCompatibilityError, match="newer app version"):
        repository_for(db_path)

    inspection_engine = create_database_engine(f"sqlite:///{db_path}")
    try:
        with inspection_engine.connect() as connection:
            recorded_version = connection.exec_driver_sql(
                "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
            ).scalar_one()
    finally:
        inspection_engine.dispose()
    assert recorded_version == newer_version


def test_schema_38_upgrades_to_current_with_onvif_profiles_and_media_duration(
    tmp_path: Path,
) -> None:
    """v0.1 Acquisition/Ingest Interoperability Closure v1: a real database
    at the previously-current schema (v38) upgrades cleanly through the
    two new additive migrations -- the empty `camera_onvif_profiles` table
    (see `mockingbird.storage.models.CameraOnvifProfileModel`) and
    `media_assets.duration_seconds` -- without disturbing existing data,
    exactly mirroring `test_schema_two_migrates_motion_evidence_to_
    optional_zone_without_data_loss`'s upgrade-in-place proof for an
    earlier migration.
    """

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE camera_onvif_profiles")
        connection.exec_driver_sql("ALTER TABLE media_assets DROP COLUMN duration_seconds")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 38 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        # Existing product data survived the upgrade untouched.
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(camera_onvif_profiles)").fetchall()
            }
            assert {"source_id", "onvif_host", "profile_token", "resolved_at"} <= columns
            media_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(media_assets)").fetchall()
            }
            assert "duration_seconds" in media_columns
    finally:
        migrated.close()


def test_schema_40_upgrades_to_current_with_recorded_media_analysis_runs(
    tmp_path: Path,
) -> None:
    """Offline / Recorded Observation Ingest v1: a real database at the
    previously-current schema (v40) upgrades cleanly through the new
    additive `recorded_media_analysis_runs` table without disturbing
    existing data, mirroring `test_schema_38_upgrades_to_current_with_onvif_
    profiles_and_media_duration`'s own upgrade-in-place proof."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE recorded_media_analysis_runs")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 40 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(recorded_media_analysis_runs)"
                ).fetchall()
            }
            assert {
                "id", "media_asset_id", "stream_id", "pipeline_version", "status",
                "sample_fps", "frames_considered", "frames_analyzed", "visits_created",
            } <= columns
    finally:
        migrated.close()


def test_schema_41_upgrades_to_current_with_research_collections(
    tmp_path: Path,
) -> None:
    """Research / Conservation / Export Interoperability v1: a real database
    at the previously-current schema (v41) upgrades cleanly through the new
    additive `research_collections` table without disturbing existing data,
    mirroring `test_schema_40_upgrades_to_current_with_recorded_media_
    analysis_runs`'s own upgrade-in-place proof."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE research_collections")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 41 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(research_collections)").fetchall()
            }
            assert {
                "id", "name", "description", "curator_identity",
                "visit_ids_json", "eligibility_policy_version", "created_at", "updated_at",
            } <= columns
    finally:
        migrated.close()


def test_schema_42_upgrades_to_current_with_acoustic_observation_foundation(
    tmp_path: Path,
) -> None:
    """Acoustic / BirdNET Observation Foundation v1: a real database at the
    previously-current schema (v42) upgrades cleanly through the new
    additive `acoustic_analysis_runs` table and the new `media_assets`/
    `species_suggestions` columns without disturbing existing data,
    mirroring `test_schema_41_upgrades_to_current_with_research_
    collections`'s own upgrade-in-place proof."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE acoustic_analysis_runs")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 42 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            acoustic_run_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(acoustic_analysis_runs)").fetchall()
            }
            assert {
                "id", "media_asset_id", "stream_id", "pipeline_version", "status", "min_confidence",
                "source_duration_seconds", "windows_analyzed", "detections_above_threshold",
                "species_suggestions_created", "events_created", "visits_created",
                "error_code", "error_message", "started_at", "completed_at", "created_at",
            } <= acoustic_run_columns

            media_asset_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(media_assets)").fetchall()
            }
            assert {"audio_sample_rate_hz", "audio_channel_count"} <= media_asset_columns

            species_suggestion_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(species_suggestions)").fetchall()
            }
            assert {"window_start_ms", "window_end_ms", "model_provenance_json"} <= species_suggestion_columns
    finally:
        migrated.close()


def test_schema_43_upgrades_to_current_with_acoustic_runtime_queue(
    tmp_path: Path,
) -> None:
    """Acoustic Runtime & Quality v1: a real database at the previously-
    current schema (v43), with a real, pre-existing `acoustic_analysis_
    runs` row (from the prior milestone's manual-analysis path), upgrades
    cleanly through the new additive retry/claim columns without disturbing
    that existing row's data -- mirroring `test_schema_42_upgrades_to_
    current_with_acoustic_observation_foundation`'s own upgrade-in-place
    proof for the table itself."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        for column in ("consecutive_failure_count", "next_retry_at", "claimed_by", "claimed_at"):
            try:
                connection.exec_driver_sql(f"ALTER TABLE acoustic_analysis_runs DROP COLUMN {column}")
            except Exception:  # pragma: no cover - only if the host sqlite predates DROP COLUMN support
                pytest.skip("This host's sqlite3 does not support ALTER TABLE DROP COLUMN.")
        connection.exec_driver_sql("DROP INDEX IF EXISTS ix_acoustic_analysis_runs_status_created")
        connection.exec_driver_sql("ALTER TABLE media_assets DROP COLUMN acoustic_working_segment")
        # A real pre-migration row, exactly as the v43 manual path would
        # have left it: only the original v43 columns exist at this point.
        connection.execute(
            text(
                "INSERT INTO acoustic_analysis_runs "
                "(id, media_asset_id, stream_id, pipeline_version, status, min_confidence, "
                "windows_analyzed, detections_above_threshold, species_suggestions_created, "
                "events_created, visits_created, started_at, created_at) "
                "VALUES ('acoustic-analysis-run-legacy', 'media-legacy', :stream_id, "
                "'birdnet-analyzer-global-6k-v2.4-v1', 'completed', 0.5, 3, 1, 1, 1, 1, "
                ":now, :now)"
            ),
            {"stream_id": STREAM_ID, "now": datetime.now(UTC)},
        )
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 43 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            run_columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(acoustic_analysis_runs)").fetchall()
            }
            assert {"consecutive_failure_count", "next_retry_at", "claimed_by", "claimed_at"} <= run_columns

            index_names = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA index_list(acoustic_analysis_runs)"
                ).fetchall()
            }
            assert "ix_acoustic_analysis_runs_status_created" in index_names

            media_asset_columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(media_assets)").fetchall()
            }
            assert "acoustic_working_segment" in media_asset_columns

        # The pre-existing row survived, and the new columns backfilled to
        # the truthful "never retried, never claimed by the new reconcile
        # loop" state for a row that predates it.
        legacy_run = migrated.get_acoustic_analysis_run("acoustic-analysis-run-legacy")
        assert legacy_run is not None
        assert legacy_run.status == "completed"
        assert legacy_run.windows_analyzed == 3
        assert legacy_run.consecutive_failure_count == 0
        assert legacy_run.next_retry_at is None
        assert legacy_run.claimed_by is None
        assert legacy_run.claimed_at is None
    finally:
        migrated.close()


def test_schema_44_upgrades_to_current_with_acoustic_species_scoped_idempotency(
    tmp_path: Path,
) -> None:
    """Multimodal Observation & Soundscape v1, Phase B: a real database at
    the previously-current schema (v44), with a real pre-existing
    `species_suggestions` row (from before the species-scoped idempotency
    fix existed), upgrades cleanly through the new unique index without
    disturbing that row -- mirroring `test_schema_43_upgrades_to_current_
    with_acoustic_runtime_queue`'s own upgrade-in-place proof."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX IF EXISTS ux_species_suggestions_acoustic_idempotency")
        # A real pre-migration row, exactly as the v44 acoustic path would
        # have left it: only the original columns matter here.
        connection.execute(
            text(
                "INSERT INTO species_suggestions "
                "(id, adapter_id, adapter_name, suggested_label, rank, alternatives_json, status, "
                "created_at, window_start_ms, window_end_ms) "
                "VALUES ('species-suggestion-legacy', 'birdnet', 'BirdNET-Analyzer', "
                "'northern_cardinal', 1, '[]', 'pending', :now, 0, 3000)"
            ),
            {"now": datetime.now(UTC)},
        )
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 44 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            index_names = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA index_list(species_suggestions)").fetchall()
            }
            assert "ux_species_suggestions_acoustic_idempotency" in index_names

            row = connection.execute(
                text("SELECT suggested_label, window_start_ms FROM species_suggestions WHERE id = :id"),
                {"id": "species-suggestion-legacy"},
            ).first()
            assert row is not None
            assert row[0] == "northern_cardinal"
            assert row[1] == 0
    finally:
        migrated.close()


def test_schema_45_upgrades_to_current_with_visit_multimodal_association(
    tmp_path: Path,
) -> None:
    """Multimodal Observation & Soundscape v1, Phase D/E: a real database at
    the previously-current schema (v45) upgrades cleanly through the new
    additive `visit_associations` table -- mirroring `_migrate_to_scene_
    confusor_regions`'s own "additive table, no seeded row" proof pattern
    (`test_schema_34...` equivalent) applied to this milestone's table."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE visit_associations")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 45 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(visit_associations)").fetchall()
            }
            assert {
                "id", "visual_visit_id", "acoustic_visit_id", "tier", "overlap_ms", "gap_ms",
                "engine_version", "created_at", "updated_at",
            } <= columns
            count = connection.exec_driver_sql("SELECT COUNT(*) FROM visit_associations").scalar()
            assert count == 0
    finally:
        migrated.close()


def test_schema_47_upgrades_to_current_with_camera_node_transport_ingestion(
    tmp_path: Path,
) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase E: a real database
    at the previously-current schema (v47) upgrades cleanly through the new
    additive `camera_node_transport_ingestions` table -- mirroring
    `test_schema_45_upgrades_to_current_with_visit_multimodal_association`'s
    own "additive table, no seeded row" proof pattern applied to this
    milestone's table."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE camera_node_transport_ingestions")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 47 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(camera_node_transport_ingestions)"
                ).fetchall()
            }
            assert {
                "id", "node_id", "item_id", "source_id", "content_sha256", "content_length",
                "status", "media_asset_id", "error_reason", "attempt_count", "blob_deleted_at",
                "created_at", "updated_at",
            } <= columns
            count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM camera_node_transport_ingestions"
            ).scalar()
            assert count == 0
    finally:
        migrated.close()


def test_schema_48_upgrades_to_current_with_rejected_analysis_media_retention(
    tmp_path: Path,
) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase D: a real database
    at the previously-current schema (v48) upgrades cleanly through the new
    nullable `rejected_analysis_media_age_days` column on the existing
    `storage_retention_settings` table -- same add-column shape as
    `_migrate_to_media_asset_duration`, proven the same way
    `test_schema_37_adds_camera_node_boot_identity_columns_without_data_loss`
    proves its own add-column migration: rebuild the pre-migration table
    shape, roll the recorded version back, then reopen and confirm the new
    column exists and every pre-existing row survived untouched."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "ALTER TABLE storage_retention_settings RENAME TO storage_retention_settings_v48"
        )
        connection.exec_driver_sql(
            "CREATE TABLE storage_retention_settings AS SELECT "
            "singleton_id, automatic_cleanup_enabled, cleanup_frequency, "
            "retain_unresolved_visit_evidence, retain_reviewed_bird_wildlife_evidence, "
            "reviewed_non_bird_age_days, superseded_evidence_age_days, orphaned_media_age_days, "
            "maximum_managed_media_bytes, policy_revision, updated_at, last_automatic_run_at, "
            "last_automatic_result, last_settings_idempotency_key "
            "FROM storage_retention_settings_v48"
        )
        connection.exec_driver_sql("DROP TABLE storage_retention_settings_v48")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 48 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(storage_retention_settings)"
                ).fetchall()
            }
            assert "rejected_analysis_media_age_days" in columns

        settings = migrated.storage_retention_settings()
        assert settings.rejected_analysis_media_age_days is None  # honest "not configured," never fabricated
    finally:
        migrated.close()


def test_schema_50_upgrades_to_current_with_environmental_context_foundation(
    tmp_path: Path,
) -> None:
    """Environmental Context Foundation v1: a real database at the
    previously-current schema (v50) upgrades cleanly through the two new
    additive tables (`environmental_context_settings`,
    `environmental_context_records`) -- mirroring `test_schema_45_upgrades_
    to_current_with_visit_multimodal_association`'s own "additive table(s),
    no seeded row" proof pattern applied to this milestone's tables."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE environmental_context_records")
        connection.exec_driver_sql("DROP TABLE environmental_context_settings")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 50 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            settings_columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(environmental_context_settings)"
                ).fetchall()
            }
            assert {"singleton_id", "coarse_latitude", "coarse_longitude", "updated_at"} <= settings_columns
            records_columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(environmental_context_records)"
                ).fetchall()
            }
            assert {
                "id", "source_id", "provider_key", "information_class", "metric",
                "value_numeric", "value_text", "unit", "observed_at", "observed_at_end",
                "for_date", "retrieved_at", "basis_latitude", "basis_longitude",
                "provenance_json", "provenance_schema_version", "created_at",
            } <= records_columns
            settings_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM environmental_context_settings"
            ).scalar()
            records_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM environmental_context_records"
            ).scalar()
            assert settings_count == 0
            assert records_count == 0

        settings = migrated.get_environmental_context_settings()
        assert settings.configured is False  # honest "not configured," never fabricated
    finally:
        migrated.close()


def test_schema_51_upgrades_to_current_with_habitat_phenology_foundation(
    tmp_path: Path,
) -> None:
    """Habitat & Phenology Foundation v1: a real database at the
    previously-current schema (v51) upgrades cleanly through the two new
    additive tables (`place_habitat_facts`, `place_phenology_observations`)
    -- mirroring `test_schema_50_upgrades_to_current_with_environmental_
    context_foundation`'s own "additive table(s), no seeded row" proof
    pattern applied to this milestone's tables."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE place_phenology_observations")
        connection.exec_driver_sql("DROP TABLE place_habitat_facts")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 51 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(migrated.list_sources()) == existing_source_count

        with migrated.engine.connect() as connection:
            habitat_columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(place_habitat_facts)"
                ).fetchall()
            }
            assert {
                "id", "source_id", "category", "label", "note",
                "information_class", "provenance", "created_at", "updated_at",
            } <= habitat_columns
            phenology_columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(place_phenology_observations)"
                ).fetchall()
            }
            assert {
                "id", "source_id", "subject_label", "phenomenon", "information_class",
                "provenance", "observed_start_date", "observed_end_date", "note",
                "created_at", "updated_at",
            } <= phenology_columns
            habitat_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM place_habitat_facts"
            ).scalar()
            phenology_count = connection.exec_driver_sql(
                "SELECT COUNT(*) FROM place_phenology_observations"
            ).scalar()
            assert habitat_count == 0
            assert phenology_count == 0

        # Honest "nothing recorded yet," never fabricated -- same discipline
        # as the environmental-context settings assertion above.
        assert migrated.list_place_habitat_facts() == []
        assert migrated.list_place_phenology_observations() == []
    finally:
        migrated.close()


def test_a_mid_chain_migration_failure_rolls_back_every_step_not_only_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("C4
    migration hardening"): every existing migration test above proves a
    *successful* upgrade; none proves what happens when a migration
    function itself raises partway through a multi-step chain. The whole
    `while` loop in `_validate_or_migrate_schema_version` runs inside one
    `engine.begin()` transaction (see storage/database.py) -- this proves
    that guarantee for real: rewinds a real database two versions back
    (v40), injects a synthetic failure into the *second* of the two
    migrations that would run (v41->v42), and confirms not only that the
    recorded version never advances, but that the *first* migration's own
    already-successful table creation (v40->v41) is rolled back too -- a
    partial upgrade must never be left half-applied."""

    from mockingbird.storage import database as database_module

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    existing_source_count = len(repository.list_sources())
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE research_collections")
        connection.exec_driver_sql("DROP TABLE recorded_media_analysis_runs")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 40 WHERE singleton_id = 1")
    engine.dispose()

    def _broken_research_collections_migration(connection) -> None:
        raise RuntimeError("synthetic mid-chain migration failure")

    monkeypatch.setitem(
        database_module._SCHEMA_MIGRATIONS, 42, _broken_research_collections_migration
    )

    with pytest.raises(RuntimeError, match="synthetic mid-chain migration failure"):
        repository_for(db_path)

    # Re-read raw, bypassing the ORM/repository layer entirely -- the same
    # discipline `_read_recorded_schema_version` itself uses -- so this
    # assertion cannot be fooled by any in-process caching.
    verify_engine = create_database_engine(f"sqlite:///{db_path}")
    with verify_engine.connect() as connection:
        recorded_version = connection.exec_driver_sql(
            "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
        ).scalar_one()
        table_names = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    verify_engine.dispose()

    assert recorded_version == 40  # never advanced to 41, even though that migration itself succeeded
    assert "recorded_media_analysis_runs" not in table_names  # v40->v41's own successful work, rolled back too
    assert "research_collections" not in table_names  # the migration that actually raised

    # The database is still genuinely usable afterward -- a failed upgrade
    # attempt must not corrupt or strand it. Undo the monkeypatch's
    # not-yet-restored failure by opening fresh (monkeypatch already
    # restores the real migration function at teardown, but this repeats
    # the same explicit-teardown pattern the rest of this file uses).
    monkeypatch.undo()
    recovered = repository_for(db_path)
    try:
        assert recovered.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert len(recovered.list_sources()) == existing_source_count
    finally:
        recovered.close()


def test_reopening_an_old_database_creates_a_verified_pre_migration_safety_backup(
    tmp_path: Path,
) -> None:
    """Release Engineering Foundation v1: closes the "pre-upgrade backup
    trigger" docs/appliance-storage-privacy-recovery-v1-contract.md's own
    "Bounded update-readiness review" named and deliberately deferred.
    Rewinds a real database one version back and confirms reopening it (the
    same thing replacing an old app bundle with a new one and relaunching
    does) creates a real, verified, restorable `.mbbackup` archive *before*
    migrating -- not merely records that it should have."""

    from mockingbird.storage.backup import LocalBackupManager

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE mockingbird_schema SET version = {CURRENT_DATABASE_SCHEMA_VERSION - 1} "
            "WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert migrated.schema_status.migrated_from_version == CURRENT_DATABASE_SCHEMA_VERSION - 1
        backup_id = migrated.schema_status.pre_migration_backup_id
        assert backup_id is not None

        manager = LocalBackupManager(db_url=migrated.db_url, media_root=media_root)
        library = manager.list_backups()
        [backup] = [entry for entry in library.backups if entry.id == backup_id]
        assert backup.kind == "pre_migration"
        # The archived database is the *pre*-migration state, not the
        # already-upgraded one this process is now running.
        assert backup.database_schema_version == CURRENT_DATABASE_SCHEMA_VERSION - 1
        assert backup.verification_status == "verified"
        assert backup.restore_compatible is True
    finally:
        migrated.close()


def test_no_pre_migration_backup_on_a_brand_new_database(tmp_path: Path) -> None:
    """A first-ever launch has nothing pre-upgrade to preserve -- confirms
    the hook stays silent for the one case it must never fire on."""

    from mockingbird.storage.backup import LocalBackupManager

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert repository.schema_status.migrated_from_version is None
        assert repository.schema_status.pre_migration_backup_id is None
        manager = LocalBackupManager(db_url=repository.db_url, media_root=media_root)
        assert manager.list_backups().backups == []
    finally:
        repository.close()


def test_no_pre_migration_backup_when_reopening_an_already_current_database(
    tmp_path: Path,
) -> None:
    """An ordinary daily relaunch -- already at the current schema version --
    must stay exactly as side-effect-free as it always was; only a genuine
    forward migration should ever create a backup here."""

    from mockingbird.storage.backup import LocalBackupManager

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = repository_for(db_path)
    repository.close()

    reopened = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert reopened.schema_status.migrated_from_version is None
        assert reopened.schema_status.pre_migration_backup_id is None
        manager = LocalBackupManager(db_url=reopened.db_url, media_root=media_root)
        assert manager.list_backups().backups == []
    finally:
        reopened.close()


def test_a_failed_pre_migration_backup_blocks_the_migration_entirely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failure must be recoverable or must fail before destructive mutation
    -- if the safety backup itself cannot be created and verified, the
    migration that would follow it must never run at all, exactly mirroring
    `test_a_mid_chain_migration_failure_rolls_back_every_step_not_only_its_
    own`'s own verification style for the in-migration failure case."""

    from mockingbird.storage import backup as backup_module

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE mockingbird_schema SET version = {CURRENT_DATABASE_SCHEMA_VERSION - 1} "
            "WHERE singleton_id = 1"
        )
    engine.dispose()

    def _broken_create_backup(self, *, kind: str = "manual"):
        raise RuntimeError("synthetic pre-migration backup failure")

    monkeypatch.setattr(backup_module.LocalBackupManager, "create_backup", _broken_create_backup)

    with pytest.raises(RuntimeError, match="synthetic pre-migration backup failure"):
        ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)

    verify_engine = create_database_engine(f"sqlite:///{db_path}")
    with verify_engine.connect() as connection:
        recorded_version = connection.exec_driver_sql(
            "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
        ).scalar_one()
    verify_engine.dispose()
    assert recorded_version == CURRENT_DATABASE_SCHEMA_VERSION - 1  # never touched

    monkeypatch.undo()
    recovered = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert recovered.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert recovered.schema_status.pre_migration_backup_id is not None
    finally:
        recovered.close()


def test_integrity_is_checked_again_after_a_real_migration_not_only_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/appliance-storage-privacy-recovery-v1-contract.md's own
    deferred "health check *after* migration but *before* declaring the
    upgrade successful" -- a migration completing without raising only
    proves no exception happened, not that the resulting database is
    actually healthy. An ordinary already-current launch must stay exactly
    as cheap as before (one check, not two)."""

    from mockingbird.storage import database as database_module

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()

    real_check = database_module._sqlite_integrity_check
    call_count = 0

    def _counting_check(engine):
        nonlocal call_count
        call_count += 1
        return real_check(engine)

    monkeypatch.setattr(database_module, "_sqlite_integrity_check", _counting_check)
    reopened = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    reopened.close()
    assert call_count == 1  # already current -- one check, same as always

    call_count = 0
    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE mockingbird_schema SET version = {CURRENT_DATABASE_SCHEMA_VERSION - 1} "
            "WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert call_count == 2  # pre-migration snapshot, then a real post-migration re-check
        assert migrated.schema_status.integrity_check == "ok"
    finally:
        migrated.close()


def test_a_post_migration_integrity_failure_blocks_the_upgrade_from_completing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Even though the migration's own transaction already committed (SQL-
    level, it genuinely succeeded), a failed post-migration integrity check
    must still stop this process from ever reporting readiness -- the
    pre-migration safety backup remains the recovery path, exactly as
    documented in "Upgrading MockingBird" in docs/using-mockingbird.md."""

    from mockingbird.storage import database as database_module

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            f"UPDATE mockingbird_schema SET version = {CURRENT_DATABASE_SCHEMA_VERSION - 1} "
            "WHERE singleton_id = 1"
        )
    engine.dispose()

    real_check = database_module._sqlite_integrity_check
    call_count = 0

    def _fail_on_second_call(engine):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise DatabaseSchemaCompatibilityError("synthetic post-migration integrity failure")
        return real_check(engine)

    monkeypatch.setattr(database_module, "_sqlite_integrity_check", _fail_on_second_call)

    with pytest.raises(DatabaseSchemaCompatibilityError, match="synthetic post-migration"):
        ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)

    # The migration itself really did commit (a real, if now moot,
    # SQL-level fact) -- this failure mode is about the app refusing to
    # ever *serve* on top of it, not about the migration transaction lying.
    verify_engine = create_database_engine(f"sqlite:///{db_path}")
    with verify_engine.connect() as connection:
        recorded_version = connection.exec_driver_sql(
            "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
        ).scalar_one()
    verify_engine.dispose()
    assert recorded_version == CURRENT_DATABASE_SCHEMA_VERSION


def test_database_needing_unknown_migration_is_rejected(tmp_path: Path) -> None:
    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    with repository.engine.begin() as connection:
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 0 WHERE singleton_id = 1"
        )
    repository.engine.dispose()

    with pytest.raises(DatabaseSchemaCompatibilityError, match="explicit migration"):
        repository_for(db_path)


def test_corrupted_database_is_refused_without_modification_and_recoverable_from_backup(
    tmp_path: Path,
) -> None:
    """v0.1 Release Hardening v1 -- 2c: grounds docs/using-mockingbird.md's
    corrupted-database recovery guidance in real, executed behavior rather
    than an untested claim. `test_newer_database_version_is_rejected_
    without_modification`/`test_database_needing_unknown_migration_is_
    rejected` above already prove the schema-incompatibility branches of
    this same `_sqlite_integrity_check` gate; this test exercises genuine
    byte-level corruption (a failed `PRAGMA quick_check`, not a version
    mismatch) and then proves the composed operator recovery procedure
    end-to-end: move the corrupt file aside, let MockingBird start fresh,
    then restore the most recent backup."""

    from mockingbird.storage.backup import LocalBackupManager

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    known_zone_name = repository.zones_for_stream("stream-backyard-feeder")[0].name
    manager = LocalBackupManager(
        db_url=repository.db_url, media_root=media_root, backup_root=tmp_path / "backups",
    )
    backup = manager.create_backup()
    repository.close()

    # Genuine corruption: overwrite the live file's own bytes in place (not
    # a schema-version edit through a real connection) so PRAGMA quick_check
    # itself fails, exercising the "could not safely read" branch the two
    # tests above do not reach.
    original_bytes = db_path.read_bytes()
    db_path.write_bytes(b"not a sqlite database" * 64)

    with pytest.raises(DatabaseSchemaCompatibilityError):
        ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)

    # MockingBird must never modify a file it refused to open -- still
    # exactly the corrupted bytes, not the original, valid ones.
    assert db_path.read_bytes() == b"not a sqlite database" * 64
    assert original_bytes != b"not a sqlite database" * 64

    # Operator recovery: move the corrupt file aside (MockingBird itself
    # never does this automatically -- no silent auto-recreate/auto-restore
    # exists, matching the two schema-incompatibility tests above), then a
    # fresh launch against the same path succeeds normally.
    db_path.unlink()
    fresh = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    assert fresh.zones_for_stream("stream-backyard-feeder") != []  # ordinary fresh-install seed data
    fresh.close()

    # Then restore the pre-corruption backup through the exact same,
    # already-thoroughly-tested restore mechanism test_local_backup_
    # recovery.py exercises -- recovery does not require inventing any new
    # mechanism.
    transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
    restored = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        assert restored.zones_for_stream("stream-backyard-feeder")[0].name == known_zone_name
        transaction.commit()
    finally:
        restored.close()


def test_schema_37_adds_camera_node_boot_identity_columns_without_data_loss(
    tmp_path: Path,
) -> None:
    """Boot Identity + Autonomous Recovery v1: `camera_sources` gains five
    new nullable columns. A pre-existing installation's own Source rows
    (any kind, not only `camera_node`) must survive the migration
    byte-identical on every pre-existing field, reading back `None`/
    "not tracked yet" for every new one -- see
    `_migrate_to_camera_node_boot_identity` in storage/database.py."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    with repository.session_factory() as session:
        source_id = session.get(StreamModel, STREAM_ID).source_id
        original = session.get(CameraSourceModel, source_id)
        original_name, original_kind, original_status = (
            original.name,
            original.kind,
            original.status,
        )
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        # Mirror `test_schema_two_migrates_motion_evidence_to_optional_zone_
        # without_data_loss`'s exact rebuild-in-place idiom: recreate
        # `camera_sources` in its pre-migration (five-column) shape, copy
        # every existing row across unchanged, then roll the recorded
        # schema version back to 36 so the next open must migrate forward
        # for real.
        connection.exec_driver_sql(
            """
            CREATE TABLE camera_sources_schema_36 (
                id VARCHAR NOT NULL PRIMARY KEY,
                name VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                description TEXT NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO camera_sources_schema_36 (id, name, kind, status, description) "
            "SELECT id, name, kind, status, description FROM camera_sources"
        )
        connection.exec_driver_sql("DROP TABLE camera_sources")
        connection.exec_driver_sql(
            "ALTER TABLE camera_sources_schema_36 RENAME TO camera_sources"
        )
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 36 WHERE singleton_id = 1"
        )
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        with migrated.session_factory() as session:
            source = session.get(CameraSourceModel, source_id)
            assert source is not None
            # Every pre-existing field survives untouched.
            assert (source.name, source.kind, source.status) == (
                original_name,
                original_kind,
                original_status,
            )
            # Every new field reads back the honest "not tracked yet" state
            # -- never a fabricated timestamp or boot id.
            assert source.camera_node_last_seen_at is None
            assert source.camera_node_boot_id is None
            assert source.camera_node_boot_first_seen_at is None
            assert source.camera_node_service_version is None
            assert source.camera_node_recent_boot_transitions_json is None

        with migrated.engine.connect() as connection:
            columns = {
                row[1] for row in connection.exec_driver_sql("PRAGMA table_info(camera_sources)")
            }
        assert {
            "camera_node_last_seen_at",
            "camera_node_boot_id",
            "camera_node_boot_first_seen_at",
            "camera_node_service_version",
            "camera_node_recent_boot_transitions_json",
        } <= columns
    finally:
        migrated.close()


def test_schema_53_upgrades_to_current_with_environmental_context_weather(
    tmp_path: Path,
) -> None:
    """Environmental Context v2: a real database at the previously-current
    schema (v53) upgrades cleanly through the one new additive column
    (`environmental_context_settings.weather_enabled`) -- mirroring this
    file's own `test_schema_37_adds_camera_node_boot_identity_columns_
    without_data_loss`, above: "rebuild the pre-migration table shape, roll
    the recorded version back, reopen," applied to a column addition
    rather than a whole-table drop. `environmental_context_records` needs
    no migration at all (see docs/environmental-context-v2-contract.md
    "Phase 1/26") -- only `environmental_context_settings` is touched
    here."""

    db_path = tmp_path / "mockingbird.sqlite3"
    repository = repository_for(db_path)
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EnvironmentalContextSettingsModel(
                    singleton_id=1, coarse_latitude=40.7, coarse_longitude=-74.0, updated_at=now,
                )
            )
    repository.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        # Rebuild the table in its pre-migration (v53, no `weather_enabled`)
        # shape, copying the existing row across unchanged (deliberately
        # not `weather_enabled` -- that column did not exist at v53, so a
        # real pre-existing row could never have carried a value for it),
        # then roll the recorded schema version back so the next open must
        # migrate forward for real.
        connection.exec_driver_sql(
            """
            CREATE TABLE environmental_context_settings_schema_53 (
                singleton_id INTEGER NOT NULL PRIMARY KEY,
                coarse_latitude FLOAT,
                coarse_longitude FLOAT,
                updated_at DATETIME NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO environmental_context_settings_schema_53 "
            "(singleton_id, coarse_latitude, coarse_longitude, updated_at) "
            "SELECT singleton_id, coarse_latitude, coarse_longitude, updated_at "
            "FROM environmental_context_settings"
        )
        connection.exec_driver_sql("DROP TABLE environmental_context_settings")
        connection.exec_driver_sql(
            "ALTER TABLE environmental_context_settings_schema_53 "
            "RENAME TO environmental_context_settings"
        )
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 53 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        settings = migrated.get_environmental_context_settings()
        # Every pre-existing field survives untouched.
        assert settings.coarse_latitude == 40.7
        assert settings.coarse_longitude == -74.0
        # The new column reads back the honest, conservative default --
        # an upgraded installation that already has a location configured
        # for solar does not silently start making outbound weather
        # requests (see docs/environmental-context-v2-contract.md
        # "Phase 16" / "Privacy / location").
        assert settings.weather_enabled is False

        with migrated.engine.connect() as connection:
            columns = {
                row[1]
                for row in connection.exec_driver_sql(
                    "PRAGMA table_info(environmental_context_settings)"
                ).fetchall()
            }
        assert "weather_enabled" in columns
    finally:
        migrated.close()
