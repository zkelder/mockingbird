from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from sqlalchemy import func, inspect, select

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.backup import LocalBackupManager
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION
from mockingbird.storage.models import (
    ReviewLabelModel,
    CameraSourceModel,
    MediaAssetModel,
    StreamMonitoringPolicyModel,
    StreamModel,
    VisitModel,
    YardMapModel,
    YardMapStreamPlacementModel,
    YardMapZonePlacementModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source


PNG_64 = (
    b"\x89PNG\r\n\x1a\n"
    + b"\x00\x00\x00\rIHDR"
    + (64).to_bytes(4, "big")
    + (64).to_bytes(4, "big")
    + b"\x08\x02\x00\x00\x00"
)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)
    repository.close()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def test_current_schema_creates_no_map_or_placements(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'migration.sqlite3'}",
        media_root=tmp_path / "media",
    )
    assert CURRENT_DATABASE_SCHEMA_VERSION == 59
    table_names = set(inspect(repository.engine).get_table_names())
    assert {"yard_maps", "yard_map_stream_placements", "yard_map_zone_placements"}.issubset(table_names)
    with repository.session_factory() as session:
        assert session.scalar(select(YardMapModel.id).limit(1)) is None
        assert session.scalar(select(YardMapStreamPlacementModel.stream_id).limit(1)) is None
        assert session.scalar(select(YardMapZonePlacementModel.zone_id).limit(1)) is None
    repository.close()


async def test_yard_map_is_local_bounded_and_does_not_change_product_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    with isolated_repository.session_factory() as session:
        visits_before = session.scalar(select(func.count(VisitModel.id))) or 0
        labels_before = session.scalar(select(func.count(ReviewLabelModel.id))) or 0
        policies_before = session.scalar(select(func.count(StreamMonitoringPolicyModel.stream_id))) or 0
        media_before = session.scalar(select(func.count(MediaAssetModel.id))) or 0
        zone = session.scalar(select(ZoneModel).order_by(ZoneModel.id))
        assert zone is not None
        zone_polygon_before = zone.polygon_json

    empty = await client.get("/api/yard-map")
    assert empty.status_code == 200
    assert empty.json()["map"] is None
    assert empty.json()["warnings"]

    created = await client.post(
        "/api/yard-map/blank",
        json={"canvas_width": 1200, "canvas_height": 800, "idempotency_key": "map-blank"},
    )
    assert created.status_code == 201
    initial = created.json()
    assert initial["map"]["background"] is None
    stream = initial["streams"][0]
    placed = await client.put(
        f"/api/yard-map/streams/{stream['id']}",
        json={
            "x": 0.25,
            "y": 0.75,
            "heading_degrees": 35,
            "field_of_view_degrees": 80,
            "display_scale": 1,
            "idempotency_key": "place-stream",
        },
    )
    assert placed.status_code == 200
    stream_after = next(item for item in placed.json()["streams"] if item["id"] == stream["id"])
    assert stream_after["placement"]["x"] == 0.25
    repeated = await client.put(
        f"/api/yard-map/streams/{stream['id']}",
        json={
            "x": 0.25,
            "y": 0.75,
            "heading_degrees": 35,
            "field_of_view_degrees": 80,
            "display_scale": 1,
            "idempotency_key": "place-stream",
        },
    )
    assert repeated.status_code == 200
    stale = await client.put(
        f"/api/yard-map/streams/{stream['id']}",
        json={
            "x": 0.3,
            "y": 0.75,
            "heading_degrees": 35,
            "field_of_view_degrees": 80,
            "expected_state_token": "yard-map-stream:stale",
            "idempotency_key": "stale-stream",
        },
    )
    assert stale.status_code == 409

    zone_placed = await client.put(
        f"/api/yard-map/zones/{zone.id}",
        json={
            "x": 0.5,
            "y": 0.5,
            "area": [
                {"x": 0.4, "y": 0.4},
                {"x": 0.6, "y": 0.4},
                {"x": 0.5, "y": 0.6},
            ],
            "idempotency_key": "place-zone",
        },
    )
    assert zone_placed.status_code == 200
    placed_zone = next(item for item in zone_placed.json()["zones"] if item["id"] == zone.id)
    assert placed_zone["placement"]["area"] == [
        {"x": 0.4, "y": 0.4},
        {"x": 0.6, "y": 0.4},
        {"x": 0.5, "y": 0.6},
    ]
    with isolated_repository.session_factory() as session:
        assert session.get(ZoneModel, zone.id).polygon_json == zone_polygon_before

    out_of_bounds = await client.put(
        f"/api/yard-map/streams/{stream['id']}",
        json={
            "x": 1.01,
            "y": 0.75,
            "heading_degrees": 35,
            "field_of_view_degrees": 80,
            "idempotency_key": "out-of-bounds-stream",
        },
    )
    assert out_of_bounds.status_code == 422
    invalid_area = await client.put(
        f"/api/yard-map/zones/{zone.id}",
        json={"x": 0.5, "y": 0.5, "area": [{"x": 0.5, "y": 0.5}], "idempotency_key": "invalid-area"},
    )
    assert invalid_area.status_code == 422

    uploaded = await client.post(
        "/api/yard-map/background",
        files={"file": ("yard.png", PNG_64, "image/png")},
        data={"expected_state_token": zone_placed.json()["map"]["state_token"], "idempotency_key": "yard-image"},
    )
    assert uploaded.status_code == 200
    background = uploaded.json()["map"]["background"]
    assert background["preview_url"] == "/api/yard-map/background"
    assert "tmp" not in str(background)
    served = await client.get(background["preview_url"])
    assert served.status_code == 200
    assert served.content == PNG_64
    media_assets = await client.get("/api/media")
    assert media_assets.status_code == 200
    assert all("property-map" not in str(item) for item in media_assets.json())

    backup = LocalBackupManager(
        db_url=isolated_repository.db_url,
        media_root=isolated_repository.media_root,
        backup_root=tmp_path / "backups",
    ).create_backup()
    with ZipFile(backup.backup.archive_path) as archive:
        assert any(name.startswith("media/property-map/") for name in archive.namelist())

    with isolated_repository.session_factory() as session:
        assert (session.scalar(select(func.count(VisitModel.id))) or 0) == visits_before
        assert (session.scalar(select(func.count(ReviewLabelModel.id))) or 0) == labels_before
        assert (session.scalar(select(func.count(StreamMonitoringPolicyModel.stream_id))) or 0) == policies_before
        assert (session.scalar(select(func.count(MediaAssetModel.id))) or 0) == media_before

    deleted = await client.request(
        "DELETE",
        f"/api/yard-map/zones/{zone.id}",
        json={
            "expected_state_token": placed_zone["placement"]["state_token"],
            "idempotency_key": "remove-zone",
        },
    )
    assert deleted.status_code == 200
    repeated_delete = await client.request(
        "DELETE",
        f"/api/yard-map/zones/{zone.id}",
        json={
            "expected_state_token": placed_zone["placement"]["state_token"],
            "idempotency_key": "remove-zone",
        },
    )
    assert repeated_delete.status_code == 200

    managed_background = next((isolated_repository.media_root / "property-map").iterdir())
    managed_background.unlink()
    missing_background = await client.get("/api/yard-map")
    assert missing_background.status_code == 200
    assert missing_background.json()["map"]["background"] is None
    assert missing_background.json()["map"]["background_missing"] is True
    assert (await client.get("/api/yard-map/background")).status_code == 404


async def test_yard_map_activity_is_stream_scoped_and_uses_reviewed_truth_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    # Analytics & Local Data Truth Consistency v1: `_yard_map_activity_
    # summary` now shows "no activity yet" for a demo-sourced Stream. This
    # test's own actual subject is stream-scoping and reviewed-truth-only
    # display, exercised against the seeded `stream-backyard-feeder`'s two
    # Visits purely as convenient plumbing -- not demo-exclusion itself
    # (`tests/test_demo_source_exclusion.py`'s own dedicated Yard Map
    # tests already cover that) -- so repurpose it first, the same
    # established mechanism Review Queue Count Truth Consistency v1 used
    # for the identical situation.
    de_demo_seeded_source(isolated_repository)

    suggestion = await client.post("/api/species-suggestions/mock", json={"visit_id": "visit-bird-feeder-001"})
    assert suggestion.status_code == 201

    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                id="source-yard-map-archived",
                name="Archived yard-map source",
                kind="manual_upload",
                status="connected",
                description="Isolated Yard Map fixture source.",
            ))
            session.add(StreamModel(
                id="stream-yard-map-archived",
                source_id="source-yard-map-archived",
                name="Archived map camera",
                description="Isolated Yard Map fixture stream.",
                is_live=False,
            ))

    before_correction = isolated_repository.yard_map(
        activity_range="last_24_hours",
        now=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    primary = next(item for item in before_correction.streams if item.id == "stream-backyard-feeder")
    assert primary.activity.needs_review_count == 1
    assert primary.activity.latest_confirmed_label is None

    corrected = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": "visit-bird-feeder-001",
            "label": "northern_cardinal",
        },
    )
    assert corrected.status_code == 201
    after_correction = isolated_repository.yard_map(
        activity_range="last_24_hours",
        now=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    primary_after = next(item for item in after_correction.streams if item.id == "stream-backyard-feeder")
    archived_candidate = next(item for item in after_correction.streams if item.id == "stream-yard-map-archived")
    assert primary_after.activity.needs_review_count == 0
    assert primary_after.activity.latest_confirmed_label == "northern_cardinal"
    assert archived_candidate.activity.needs_review_count == 0

    with isolated_repository.session_factory() as session:
        with session.begin():
            source = session.get(CameraSourceModel, "source-yard-map-archived")
            assert source is not None
            source.status = "archived"
            visit = session.get(VisitModel, "visit-bird-feeder-001")
            assert visit is not None
            visit.is_superseded = True

    after_archive = isolated_repository.yard_map(
        activity_range="last_24_hours",
        now=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    assert "stream-yard-map-archived" not in {item.id for item in after_archive.streams}
    primary_archived = next(item for item in after_archive.streams if item.id == "stream-backyard-feeder")
    assert primary_archived.activity.latest_visit_id == "visit-squirrel-ground-001"
    assert primary_archived.activity.latest_confirmed_label is None


def test_yard_map_backup_restore_preserves_local_configuration_media(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source = ProductRepository(
        db_url=f"sqlite:///{source_root / 'mockingbird.sqlite3'}",
        media_root=source_root / "media",
    )
    source.replace_yard_map_background(
        content=PNG_64,
        content_type="image/png",
        expected_state_token=None,
        idempotency_key="source-yard-image",
    )
    source_manager = LocalBackupManager(
        db_url=source.db_url,
        media_root=source.media_root,
        backup_root=tmp_path / "backups",
    )
    backup = source_manager.create_backup()
    source.close()

    target_root = tmp_path / "target"
    target = ProductRepository(
        db_url=f"sqlite:///{target_root / 'mockingbird.sqlite3'}",
        media_root=target_root / "media",
    )
    target.close()
    target_manager = LocalBackupManager(
        db_url=f"sqlite:///{target_root / 'mockingbird.sqlite3'}",
        media_root=target_root / "media",
        backup_root=tmp_path / "backups",
    )
    verified = target_manager.verify_backup(backup.backup.id)
    plan = target_manager.create_restore_plan(verified, rebind_managed_storage=True)
    assert plan.restore_allowed is True
    transaction = target_manager.replace_live_files(
        verified,
        rebind_managed_storage=True,
        plan=plan,
    )
    restored = ProductRepository(
        db_url=f"sqlite:///{target_root / 'mockingbird.sqlite3'}",
        media_root=target_root / "media",
    )
    try:
        background = restored.yard_map_background_file()
        assert background is not None
        assert background[0].read_bytes() == PNG_64
        assert restored.yard_map().map is not None
        transaction.commit()
    finally:
        restored.close()
