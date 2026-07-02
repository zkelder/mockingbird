from __future__ import annotations

import ipaddress
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SourceKind, SourceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers import external_url_preview
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
OTHER_SOURCE_ID = "source-other-saved-preview"
OTHER_STREAM_ID = "stream-other-saved-preview"
OTHER_ZONE_ID = "zone-other-saved-preview"
PRIVATE_PREVIEW_URL = "http://192.168.1.50/camera/path/still.jpg"


class FakeResponse:
    def __init__(self, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.body = body
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> None:
        return None


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response

    def open(self, request, timeout: float):  # noqa: ANN001
        return self.response


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


@pytest.fixture(autouse=True)
def allow_private_lan_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve(hostname: str):
        try:
            return [ipaddress.ip_address(hostname)]
        except ValueError:
            return [ipaddress.ip_address("192.168.1.50")]

    monkeypatch.setattr(external_url_preview, "_resolve_host_addresses", resolve)


async def configure_external_url(client: httpx.AsyncClient) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": PRIVATE_PREVIEW_URL}},
    )
    assert response.status_code == 200


async def save_preview_media_asset(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    await configure_external_url(client)
    opener = FakeOpener(FakeResponse(b"image-bytes", {"Content-Type": "image/jpeg"}))
    monkeypatch.setattr(external_url_preview, "_build_no_redirect_opener", lambda: opener)

    response = await client.post(
        f"/api/sources/{SOURCE_ID}/external-url/preview/save",
        json={"stream_id": STREAM_ID, "note": "Saved preview for review."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["media_asset_id"]
    return body["media_asset_id"]


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
        "media_assets": await client.get("/api/media"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
        "media_assets": len(responses["media_assets"].json()),
    }


def media_file_snapshot(repository: ProductRepository) -> dict[str, int]:
    if not repository.media_root.exists():
        return {}
    return {
        str(path.relative_to(repository.media_root)): path.stat().st_size
        for path in repository.media_root.rglob("*")
        if path.is_file()
    }


def add_other_stream(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=OTHER_SOURCE_ID,
                    name="Other saved preview source",
                    kind=SourceKind.webhook.value,
                    status=SourceStatus.connected.value,
                    description="Another source for stream ownership validation.",
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
                    polygon_json='[{"x": 0.1, "y": 0.1}, {"x": 0.2, "y": 0.1}, {"x": 0.2, "y": 0.2}]',
                    is_active=True,
                )
            )


def assert_only_motion_evidence_changed(
    before: dict[str, int],
    after: dict[str, int],
) -> None:
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
        "media_assets",
    ):
        assert after[key] == before[key]


async def test_saved_preview_media_asset_creates_pending_motion_evidence_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    before = await product_counts(client)
    before_files = media_file_snapshot(isolated_repository)

    def fail_if_called(*args, **kwargs):  # noqa: ANN002, ANN003
        raise AssertionError("Saved media handoff must not fetch URLs or call model runtimes")

    monkeypatch.setattr(external_url_preview, "fetch_external_url_preview", fail_if_called)
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
        json={"reason": "Visible outdoor activity.", "note": "Review this saved still."},
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
        "source": "saved_preview_media_asset",
    }
    assert "Visible outdoor activity." in evidence["notes"]
    assert "Review this saved still." in evidence["notes"]

    assert_only_motion_evidence_changed(before, await product_counts(client))
    assert media_file_snapshot(isolated_repository) == before_files


async def test_saved_preview_motion_evidence_preserves_supplied_reviewable_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": GROUND_ZONE_ID},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["zone_id"] == GROUND_ZONE_ID
    assert body["warnings"] == []
    assert_only_motion_evidence_changed(before, await product_counts(client))


async def test_saved_preview_motion_evidence_requires_existing_media_asset(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)

    response = await client.post("/api/media/media-missing/create-motion-evidence", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Media asset 'media-missing' was not found."
    assert await product_counts(client) == before


async def test_saved_preview_motion_evidence_rejects_privacy_or_ignore_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": IGNORE_ZONE_ID},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Motion Evidence cannot be created for privacy or ignore zones."
    )
    assert await product_counts(client) == before


async def test_saved_preview_motion_evidence_rejects_zone_from_other_stream(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_other_stream(isolated_repository)
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": OTHER_ZONE_ID},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Motion evidence zone does not belong to the selected stream."
    )
    assert await product_counts(client) == before


async def test_saved_preview_motion_evidence_rejects_other_stream(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    add_other_stream(isolated_repository)
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    before = await product_counts(client)

    response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"stream_id": OTHER_STREAM_ID},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Motion evidence snapshot media must belong to the selected stream."
    )
    assert await product_counts(client) == before


async def test_saved_preview_motion_evidence_promotes_only_through_existing_promote_route(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    media_asset_id = await save_preview_media_asset(client, monkeypatch)
    created_response = await client.post(
        f"/api/media/{media_asset_id}/create-motion-evidence",
        json={"zone_id": FEEDER_ZONE_ID},
    )
    assert created_response.status_code == 201
    evidence_id = created_response.json()["motion_evidence_id"]
    before = await product_counts(client)

    response = await client.post(f"/api/motion/evidence/{evidence_id}/promote")

    assert response.status_code == 200
    promoted = response.json()
    assert promoted["evidence"]["id"] == evidence_id
    assert promoted["evidence"]["status"] == "promoted"
    assert promoted["evidence"]["snapshot_media_asset_id"] == media_asset_id
    assert promoted["event_id"] is not None
    assert promoted["visit_id"] is not None

    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["motion_evidence"] == before["motion_evidence"]
    for key in (
        "review_labels",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
        "media_assets",
    ):
        assert after[key] == before[key]
