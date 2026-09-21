from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository, SourceProviderConfigurationModel
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
PRIVACY_ZONE_ID = "zone-folder-privacy"
OTHER_SOURCE_ID = "source-other-folder-import"
OTHER_STREAM_ID = "stream-other-folder-import"
OTHER_ZONE_ID = "zone-other-folder-import"
SIDE_STREAM_ID = "stream-side-folder-import"
SIDE_ZONE_ID = "zone-side-folder-import"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    # Pre-Release Trust & Correctness Correction v1 (UI-01): this file's
    # fixtures build Visits on the seeded demo Source's own STREAM_ID, which
    # Dashboard/Bird Log now correctly exclude from real history like every
    # other surface (see `_real_source_condition` in product_repository.py).
    # "De-demo" the seeded Source in place -- the same real-product
    # mechanism (an effective, non-"demo" provider configuration)
    # `_real_source_condition` already recognizes for a Source repurposed
    # after creation.
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                SourceProviderConfigurationModel(
                    source_id=SOURCE_ID, provider_key="manual_upload",
                    config_json="{}", updated_at=datetime.now(UTC),
                )
            )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def configure_folder_source(client: httpx.AsyncClient, folder: Path) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "folder_import_future",
            "config": {
                "folder_path": str(folder),
                "allowed_extensions": "jpg,jpeg,png,webp",
                "default_stream_id": STREAM_ID,
                "default_zone_id": FEEDER_ZONE_ID,
            },
        },
    )
    assert response.status_code == 200


def write_file(path: Path, content: bytes = b"image bytes") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


async def import_folder_media_asset(
    client: httpx.AsyncClient,
    tmp_path: Path,
    *,
    file_name: str = "bird.jpg",
) -> str:
    folder = tmp_path / "trailcam"
    write_file(folder / file_name, b"folder import image bytes")
    await configure_folder_source(client, folder)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/folder-import",
        json={
            "relative_paths": [file_name],
            "default_stream_id": STREAM_ID,
            "default_zone_id": FEEDER_ZONE_ID,
            "note": "Folder import handoff fixture.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["total_imported"] == 1
    assert body["creates_media_assets"] is True
    assert body["creates_motion_evidence"] is False
    assert body["creates_events"] is False
    assert body["creates_visits"] is False
    assert body["creates_truth"] is False
    return body["imported"][0]["media_asset_id"]


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "media_assets": await client.get("/api/media"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())
    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


def assert_only_motion_evidence_changed(
    before: dict[str, int],
    after: dict[str, int],
) -> None:
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "media_assets",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
    ):
        assert after[key] == before[key]


def add_stream_validation_records(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other folder source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.connected.value,
                    description="Other source for folder handoff validation.",
                )
            )
            session.add(
                StreamModel(
                    id=OTHER_STREAM_ID,
                    source_id=OTHER_SOURCE_ID,
                    name="Other stream",
                    description="Belongs to another source.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=OTHER_ZONE_ID,
                    stream_id=OTHER_STREAM_ID,
                    name="Other feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            session.add(
                StreamModel(
                    id=SIDE_STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Side yard",
                    description="Same Source, different Stream.",
                    is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=SIDE_ZONE_ID,
                    stream_id=SIDE_STREAM_ID,
                    name="Side yard zone",
                    zone_type="yard",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            session.add(
                ZoneModel(
                    id=PRIVACY_ZONE_ID,
                    stream_id=STREAM_ID,
                    name="Folder privacy zone",
                    zone_type="privacy",
                    polygon_json="[]",
                    is_active=True,
                )
            )


async def test_folder_import_itself_creates_media_assets_only(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    before = await product_counts(client)

    media_asset_id = await import_folder_media_asset(client, tmp_path)

    assert media_asset_id.startswith("media-asset-")
    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "motion_evidence",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
    ):
        assert after[key] == before[key]


async def test_folder_imported_media_asset_creates_pending_motion_evidence_only(
    client: httpx.AsyncClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    before = await product_counts(client)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("Folder media handoff must not call model runtimes")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_local_image_detector",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.run_megadetector_on_image",
        fail_if_called,
    )

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={
            "reason": "Visible outdoor activity in imported media.",
            "note": "Review this folder import.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["motion_evidence_id"].startswith("motion-evidence-")
    assert body["media_asset_id"] == media_asset_id
    assert body["source_id"] == SOURCE_ID
    assert body["stream_id"] == STREAM_ID
    assert body["zone_id"] == FEEDER_ZONE_ID
    assert body["status"] == "pending"
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["duplicate_skipped"] is False
    assert body["existing_motion_evidence_id"] is None
    assert body["provenance_kind"] == "folder_import"
    assert body["warnings"] == [
        "No zone was supplied; MockingBird used the first active reviewable zone for this stream."
    ]

    detail_response = await client.get(f"/api/motion/evidence/{body['motion_evidence_id']}")
    assert detail_response.status_code == 200
    evidence = detail_response.json()
    assert evidence["snapshot_media_asset_id"] == media_asset_id
    assert evidence["status"] == "pending"
    assert evidence["promoted_event_id"] is None
    assert evidence["promoted_visit_id"] is None
    assert evidence["scoring_config"] == {
        "media_asset_id": media_asset_id,
        "motion_score_available": False,
        "requires_review": True,
        "source": "folder_import_media_asset",
    }
    assert "folder-imported MediaAsset" in evidence["notes"]
    assert "Visible outdoor activity in imported media." in evidence["notes"]
    assert "Review this folder import." in evidence["notes"]

    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_folder_import_motion_evidence_preserves_supplied_reviewable_zone(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": GROUND_ZONE_ID},
    )

    assert response.status_code == 201
    assert response.json()["zone_id"] == GROUND_ZONE_ID
    assert response.json()["warnings"] == []
    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_folder_import_motion_evidence_validates_stream_and_zone_context(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    add_stream_validation_records(isolated_repository)
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    before = await product_counts(client)

    wrong_stream = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"stream_id": OTHER_STREAM_ID},
    )
    wrong_zone = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": SIDE_ZONE_ID},
    )

    assert wrong_stream.status_code == 400
    assert wrong_stream.json()["detail"] == (
        "Motion evidence snapshot media must belong to the selected stream."
    )
    assert wrong_zone.status_code == 400
    assert wrong_zone.json()["detail"] == (
        "Motion evidence zone does not belong to the selected stream."
    )
    assert await product_counts(client) == before


async def test_folder_import_motion_evidence_rejects_privacy_and_ignore_zones(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    add_stream_validation_records(isolated_repository)
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    before = await product_counts(client)

    privacy = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": PRIVACY_ZONE_ID},
    )
    ignore = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": IGNORE_ZONE_ID},
    )

    assert privacy.status_code == 400
    assert privacy.json()["detail"] == (
        "Motion Evidence cannot be created for privacy or ignore zones."
    )
    assert ignore.status_code == 400
    assert ignore.json()["detail"] == (
        "Motion Evidence cannot be created for privacy or ignore zones."
    )
    assert await product_counts(client) == before


async def test_folder_import_motion_evidence_rejects_missing_local_media_file(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    media_response = await client.get(f"/api/media/{media_asset_id}")
    assert media_response.status_code == 200
    # SEC-2: GET /api/media/{id} now redacts local_path; the real path to
    # delete (simulating a missing file) is read from the repository.
    real_asset = isolated_repository.get_media_asset(media_asset_id)
    assert real_asset is not None
    Path(real_asset.local_path).unlink()
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Motion evidence media file is missing."
    assert await product_counts(client) == before


async def test_folder_import_motion_evidence_skips_duplicate_by_default(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    created = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert created.status_code == 201
    evidence_id = created.json()["motion_evidence_id"]
    before_duplicate = await product_counts(client)

    duplicate = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )

    assert duplicate.status_code == 200
    body = duplicate.json()
    assert body["duplicate_skipped"] is True
    assert body["motion_evidence_id"] == evidence_id
    assert body["existing_motion_evidence_id"] == evidence_id
    assert body["provenance_kind"] == "folder_import"
    assert "No duplicate evidence was created" in body["message"]
    assert any("no duplicate pending evidence was created" in warning for warning in body["warnings"])
    assert await product_counts(client) == before_duplicate


async def test_folder_import_motion_evidence_default_skips_ignored_duplicate(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    created = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert created.status_code == 201
    evidence_id = created.json()["motion_evidence_id"]
    ignored = await client.post(f"/api/motion/evidence/{evidence_id}/ignore")
    assert ignored.status_code == 200
    before_duplicate = await product_counts(client)

    duplicate = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )

    assert duplicate.status_code == 200
    body = duplicate.json()
    assert body["duplicate_skipped"] is True
    assert body["motion_evidence_id"] == evidence_id
    assert body["existing_motion_evidence_id"] == evidence_id
    assert await product_counts(client) == before_duplicate


async def test_folder_import_motion_evidence_allows_explicit_duplicate(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    media_asset_id = await import_folder_media_asset(client, tmp_path)
    created = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert created.status_code == 201
    before_duplicate = await product_counts(client)

    duplicate = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID, "duplicate_policy": "allow_duplicate"},
    )

    assert duplicate.status_code == 201
    assert duplicate.json()["duplicate_skipped"] is False
    assert duplicate.json()["motion_evidence_id"] != created.json()["motion_evidence_id"]
    assert_only_motion_evidence_changed(before_duplicate, await product_counts(client))
