from datetime import UTC, datetime
from pathlib import Path

import pytest
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
