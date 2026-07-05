from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import struct
import zlib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MediaAssetModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"


@pytest.fixture
def repository(tmp_path: Path) -> Iterator[ProductRepository]:
    active_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(active_repository)
    yield active_repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def png_bytes(rows: list[list[int]]) -> bytes:
    height = len(rows)
    width = len(rows[0])
    raw = b"".join(bytes([0, *row]) for row in rows)

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        checksum = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return (
            len(data).to_bytes(4, "big")
            + chunk_type
            + data
            + checksum.to_bytes(4, "big")
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(
        b"IDAT",
        zlib.compress(raw),
    ) + chunk(b"IEND", b"")


def blank_frame() -> list[list[int]]:
    return [[0, 0, 0, 0] for _ in range(4)]


def frame_with(points: list[tuple[int, int]]) -> list[list[int]]:
    frame = blank_frame()
    for y, x in points:
        frame[y][x] = 255
    return frame


async def import_png(
    client: httpx.AsyncClient,
    *,
    filename: str,
    frame: list[list[int]],
) -> dict:
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "subject_label": "unknown_animal",
        },
        files={"file": (filename, png_bytes(frame), "image/png")},
    )
    assert response.status_code == 201
    return response.json()["media_asset"]


async def import_motion_frames(client: httpx.AsyncClient) -> list[dict]:
    return [
        await import_png(client, filename="motion-0.png", frame=blank_frame()),
        await import_png(client, filename="motion-1.png", frame=frame_with([(1, 1)])),
        await import_png(
            client,
            filename="motion-2.png",
            frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        ),
    ]


async def truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = await asyncio_gather(
        client.get("/api/events"),
        client.get("/api/visits"),
        client.get("/api/review-labels"),
        client.get("/api/dataset-exports"),
        client.get("/api/dataset-coverage/summary"),
    )
    for response in responses:
        assert response.status_code == 200
    coverage = responses[4].json()
    return {
        "events": len(responses[0].json()),
        "visits": len(responses[1].json()),
        "review_labels": len(responses[2].json()),
        "exports": len(responses[3].json()),
        "reviewed_record_count": coverage["reviewed_record_count"],
        "export_ready_count": coverage["export_ready_count"],
    }


async def asyncio_gather(*awaitables):
    import asyncio

    return await asyncio.gather(*awaitables)


async def motion_evidence_count(client: httpx.AsyncClient) -> int:
    response = await client.get("/api/motion/evidence")
    assert response.status_code == 200
    return len(response.json()["motion_evidence"])


async def test_saved_media_motion_scores_sequence_without_creating_records(
    client: httpx.AsyncClient,
) -> None:
    assets = await import_motion_frames(client)
    before_truth = await truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "zone_ids": [FEEDER_ZONE_ID],
            "create_motion_evidence": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["created_evidence"] == []
    assert result["best_media_asset_id"] == assets[2]["id"]
    assert result["strongest_zone_id"] == FEEDER_ZONE_ID
    assert len(result["frame_scores"]) == 2
    assert result["candidates"][0]["zone_id"] == FEEDER_ZONE_ID
    assert await motion_evidence_count(client) == before_evidence_count
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_can_create_pending_evidence_with_best_snapshot(
    client: httpx.AsyncClient,
) -> None:
    assets = await import_motion_frames(client)
    before_truth = await truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "zone_ids": [FEEDER_ZONE_ID],
            "create_motion_evidence": True,
            "attach_best_snapshot": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert len(result["created_evidence"]) == 1
    evidence = result["created_evidence"][0]
    assert evidence["status"] == "pending"
    assert evidence["source_id"] == SOURCE_ID
    assert evidence["stream_id"] == STREAM_ID
    assert evidence["zone_id"] == FEEDER_ZONE_ID
    assert evidence["snapshot_media_asset_id"] == assets[2]["id"]
    assert evidence["scoring_config"]["source"] == "saved_media_motion"
    assert await motion_evidence_count(client) == before_evidence_count + 1
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_excludes_privacy_and_ignore_zones(
    client: httpx.AsyncClient,
) -> None:
    privacy_response = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Porch privacy",
            "zone_type": "privacy",
            "polygon": [
                {"x": 0.75, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 0.25},
                {"x": 0.75, "y": 0.25},
            ],
            "is_active": True,
        },
    )
    assert privacy_response.status_code == 201
    privacy_zone_id = privacy_response.json()["zone"]["id"]
    assets = [
        await import_png(client, filename="ignore-0.png", frame=blank_frame()),
        await import_png(client, filename="ignore-1.png", frame=frame_with([(0, 0), (1, 0)])),
        await import_png(client, filename="ignore-2.png", frame=frame_with([(0, 0), (2, 0)])),
    ]

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "zone_ids": [IGNORE_ZONE_ID, privacy_zone_id, FEEDER_ZONE_ID],
            "create_motion_evidence": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert [zone["zone_id"] for zone in result["zones"]] == [FEEDER_ZONE_ID]
    assert result["activity_detected"] is False
    assert result["created_evidence"] == []
    assert any("Ignore Zone skipped" in warning for warning in result["warnings"])
    assert any("Privacy Zone skipped" in warning for warning in result["warnings"])


async def test_saved_media_motion_rejects_invalid_media_ids(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": ["missing-media-a", "missing-media-b"],
        },
    )

    assert response.status_code == 404
    assert "missing-media-a" in response.json()["detail"]


async def test_saved_media_motion_rejects_non_image_media(
    client: httpx.AsyncClient,
) -> None:
    image = await import_png(client, filename="motion-image.png", frame=blank_frame())
    video_response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "subject_label": "unknown_animal",
        },
        files={"file": ("clip.mp4", b"not really video", "video/mp4")},
    )
    assert video_response.status_code == 201
    video = video_response.json()["media_asset"]

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [image["id"], video["id"]],
        },
    )

    assert response.status_code == 400
    assert "saved image snapshots" in response.json()["detail"]


async def test_saved_media_motion_rejects_media_from_different_stream(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    assets = await import_motion_frames(client)
    with repository.session_factory() as session:
        with session.begin():
            media_asset = session.get(MediaAssetModel, assets[1]["id"])
            assert media_asset is not None
            media_asset.stream_id = "stream-other-source"

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [assets[0]["id"], assets[1]["id"]],
        },
    )

    assert response.status_code == 400
    assert "selected Stream" in response.json()["detail"]
