from pathlib import Path

import pytest

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
        )
    )

    reloaded_repository = repository_for(db_path)

    assert all(item.visit_id != BIRD_VISIT_ID for item in reloaded_repository.review_queue_items())


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
        )
    )

    reloaded_repository = repository_for(db_path)
    analytics = reloaded_repository.analytics_summary()

    assert analytics.needs_review_count == 0
    assert analytics.species_counts["carolina_wren"] == 1


def test_repeated_initialization_does_not_duplicate_seed_records(tmp_path: Path) -> None:
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


def test_newer_database_version_is_rejected_without_modification(tmp_path: Path) -> None:
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

