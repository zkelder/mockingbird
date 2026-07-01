from pathlib import Path

from mockingbird.api.schemas import (
    DatasetExportCreate,
    Point,
    ReviewCorrectionCreate,
    ZoneCreate,
    ZoneUpdate,
)
from mockingbird.repository.product_repository import ProductRepository

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

