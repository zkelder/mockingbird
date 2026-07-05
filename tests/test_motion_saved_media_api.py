from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import struct
import zlib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import MediaAssetModel, StreamModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
IGNORE_ZONE_ID = "zone-ignore-driveway-edge"
AUTO_STREAM_ID = "stream-auto-regions-test"
AUTO_CLUSTER_STREAM_ID = "stream-auto-regions-cluster-test"
AUTO_PRIVACY_STREAM_ID = "stream-auto-regions-privacy-test"


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


def blank_frame(*, width: int = 4, height: int = 4) -> list[list[int]]:
    return [[0 for _x in range(width)] for _y in range(height)]


def frame_with(
    points: list[tuple[int, int]],
    *,
    width: int = 4,
    height: int = 4,
) -> list[list[int]]:
    frame = blank_frame(width=width, height=height)
    for y, x in points:
        frame[y][x] = 255
    return frame


def frame_with_rectangles(
    rectangles: list[tuple[int, int, int, int]],
    *,
    width: int,
    height: int,
) -> list[list[int]]:
    points: list[tuple[int, int]] = []
    for top, left, bottom, right in rectangles:
        points.extend(
            (y, x)
            for y in range(top, bottom)
            for x in range(left, right)
        )
    return frame_with(points, width=width, height=height)


async def import_png(
    client: httpx.AsyncClient,
    *,
    filename: str,
    frame: list[list[int]],
    stream_id: str = STREAM_ID,
    zone_id: str | None = FEEDER_ZONE_ID,
) -> dict:
    data = {
        "stream_id": stream_id,
        "subject_label": "unknown_animal",
    }
    if zone_id is not None:
        data["zone_id"] = zone_id
    response = await client.post(
        "/api/media/import",
        data=data,
        files={"file": (filename, png_bytes(frame), "image/png")},
    )
    assert response.status_code == 201
    return response.json()["media_asset"]


def add_stream_without_zones(
    repository: ProductRepository,
    *,
    stream_id: str = AUTO_STREAM_ID,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            if session.get(StreamModel, stream_id) is None:
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=SOURCE_ID,
                        name="Auto region test stream",
                        description="Synthetic stream for automatic activity area tests.",
                        is_live=False,
                    )
                )


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
    assert result["best_snapshot_media_asset_id"] == assets[2]["id"]
    assert result["strongest_zone_id"] == FEEDER_ZONE_ID
    assert result["session_key"]
    assert result["session_status"] == "new_activity"
    assert result["should_create_review_activity"] is True
    assert result["quiet_period_seconds"] == 30
    assert result["cooldown_seconds"] == 30
    assert result["max_snapshots_per_session"] == 3
    assert len(result["frame_scores"]) == 2
    assert result["candidates"][0]["zone_id"] == FEEDER_ZONE_ID
    assert await motion_evidence_count(client) == before_evidence_count
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_uses_auto_regions_without_user_zones(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    add_stream_without_zones(repository)
    assets = [
        await import_png(
            client,
            filename="auto-0.png",
            frame=blank_frame(),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="auto-1.png",
            frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="auto-2.png",
            frame=blank_frame(),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
    ]
    before_truth = await truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": AUTO_STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "create_motion_evidence": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["uses_auto_regions"] is True
    assert result["region_source"] == "auto_regions"
    assert result["activity_detected"] is True
    assert result["can_create_review_activity"] is False
    assert result["review_activity_created"] is False
    assert result["session_key"]
    assert result["session_status"] == "new_activity"
    assert result["should_create_review_activity"] is False
    assert result["created_evidence"] == []
    assert len(result["activity_areas"]) == 1
    assert result["activity_areas"][0]["area_id"] == result["strongest_activity_area_id"]
    assert result["strongest_activity_area_label"]
    assert result["best_media_asset_id"] in {assets[1]["id"], assets[2]["id"]}
    assert len(result["candidates"]) == 1
    assert len(result["debug_cell_zones"]) > 0
    assert await motion_evidence_count(client) == before_evidence_count
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_auto_region_create_request_is_result_only(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    add_stream_without_zones(repository)
    assets = [
        await import_png(
            client,
            filename="auto-create-0.png",
            frame=blank_frame(),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="auto-create-1.png",
            frame=frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="auto-create-2.png",
            frame=blank_frame(),
            stream_id=AUTO_STREAM_ID,
            zone_id=None,
        ),
    ]
    before_truth = await truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": AUTO_STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "create_motion_evidence": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["uses_auto_regions"] is True
    assert result["can_create_review_activity"] is False
    assert result["session_status"] == "new_activity"
    assert result["should_create_review_activity"] is False
    assert result["review_activity_created"] is False
    assert result["creation_skipped_reason"] == "auto_region_review_activity_requires_user_zone"
    assert result["created_evidence"] == []
    assert any("review activity creation still requires a named Zone" in warning for warning in result["warnings"])
    assert await motion_evidence_count(client) == before_evidence_count
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_auto_regions_cluster_and_cap_candidates(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    add_stream_without_zones(repository, stream_id=AUTO_CLUSTER_STREAM_ID)
    changed_frame = frame_with_rectangles(
        [
            (0, 0, 6, 4),
            (0, 20, 6, 24),
            (18, 0, 24, 4),
            (18, 20, 24, 24),
        ],
        width=24,
        height=24,
    )
    assets = [
        await import_png(
            client,
            filename="auto-cluster-0.png",
            frame=blank_frame(width=24, height=24),
            stream_id=AUTO_CLUSTER_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="auto-cluster-1.png",
            frame=changed_frame,
            stream_id=AUTO_CLUSTER_STREAM_ID,
            zone_id=None,
        ),
    ]

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": AUTO_CLUSTER_STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "create_motion_evidence": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["uses_auto_regions"] is True
    assert len(result["debug_cell_zones"]) == 24
    assert len(result["activity_areas"]) == 3
    assert len(result["candidates"]) == 3
    assert len(result["candidates"]) < 4
    assert all(area["cell_ids"] for area in result["activity_areas"])


async def test_saved_media_motion_prefers_user_zones_when_available(
    client: httpx.AsyncClient,
) -> None:
    assets = await import_motion_frames(client)

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "create_motion_evidence": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["uses_auto_regions"] is False
    assert result["region_source"] == "user_zones"
    assert result["can_create_review_activity"] is True
    assert FEEDER_ZONE_ID in [zone["zone_id"] for zone in result["zones"]]
    assert FEEDER_ZONE_ID in [area["zone_id"] for area in result["activity_areas"]]


async def test_saved_media_motion_auto_regions_skip_privacy_ignore_areas(
    client: httpx.AsyncClient,
    repository: ProductRepository,
) -> None:
    add_stream_without_zones(repository, stream_id=AUTO_PRIVACY_STREAM_ID)
    privacy_response = await client.post(
        "/api/zones",
        json={
            "stream_id": AUTO_PRIVACY_STREAM_ID,
            "name": "Patio privacy",
            "zone_type": "privacy",
            "polygon": [
                {"x": 0.0, "y": 0.0},
                {"x": 0.5, "y": 0.0},
                {"x": 0.5, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
            "is_active": True,
        },
    )
    assert privacy_response.status_code == 201
    assets = [
        await import_png(
            client,
            filename="privacy-auto-0.png",
            frame=blank_frame(),
            stream_id=AUTO_PRIVACY_STREAM_ID,
            zone_id=None,
        ),
        await import_png(
            client,
            filename="privacy-auto-1.png",
            frame=frame_with([(1, 0), (1, 1), (2, 0), (2, 1)]),
            stream_id=AUTO_PRIVACY_STREAM_ID,
            zone_id=None,
        ),
    ]

    response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": AUTO_PRIVACY_STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "create_motion_evidence": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["uses_auto_regions"] is True
    assert result["suppressed_auto_region_count"] > 0
    assert result["activity_detected"] is False
    assert result["session_status"] == "no_activity"
    assert result["should_create_review_activity"] is False
    assert result["created_evidence"] == []
    assert any("Privacy/ignore areas were skipped" in warning for warning in result["warnings"])


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
    assert result["session_status"] == "new_activity"
    assert result["should_create_review_activity"] is True
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


async def test_saved_media_motion_suppresses_same_activity_review_creation(
    client: httpx.AsyncClient,
) -> None:
    assets = await import_motion_frames(client)
    before_truth = await truth_counts(client)

    first_response = await client.post(
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
    assert first_response.status_code == 200
    first_result = first_response.json()
    assert first_result["session_status"] == "new_activity"
    assert first_result["should_create_review_activity"] is True
    assert len(first_result["created_evidence"]) == 1
    first_evidence_id = first_result["created_evidence"][0]["id"]
    evidence_count = await motion_evidence_count(client)

    second_response = await client.post(
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

    assert second_response.status_code == 200
    second_result = second_response.json()
    assert second_result["activity_detected"] is True
    assert second_result["created_evidence"] == []
    assert second_result["review_activity_created"] is False
    assert second_result["session_status"] == "ongoing_activity"
    assert second_result["should_create_review_activity"] is False
    assert second_result["existing_activity_reference"] == first_evidence_id
    assert second_result["creation_skipped_reason"] == "activity_session_duplicate_suppressed"
    assert any("same recent activity" in warning for warning in second_result["warnings"])
    assert await motion_evidence_count(client) == evidence_count
    assert await truth_counts(client) == before_truth


async def test_saved_media_motion_allows_separate_zone_activity(
    client: httpx.AsyncClient,
) -> None:
    assets = await import_motion_frames(client)
    zone_response = await client.post(
        "/api/zones",
        json={
            "stream_id": STREAM_ID,
            "name": "Whole yard activity",
            "zone_type": "yard",
            "polygon": [
                {"x": 0.0, "y": 0.0},
                {"x": 1.0, "y": 0.0},
                {"x": 1.0, "y": 1.0},
                {"x": 0.0, "y": 1.0},
            ],
            "is_active": True,
        },
    )
    assert zone_response.status_code == 201
    yard_zone_id = zone_response.json()["zone"]["id"]

    first_response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "zone_ids": [FEEDER_ZONE_ID],
            "create_motion_evidence": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 2,
        },
    )
    assert first_response.status_code == 200
    assert len(first_response.json()["created_evidence"]) == 1

    second_response = await client.post(
        "/api/motion/evaluate-saved-media",
        json={
            "stream_id": STREAM_ID,
            "media_asset_ids": [asset["id"] for asset in assets],
            "zone_ids": [yard_zone_id],
            "create_motion_evidence": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert second_response.status_code == 200
    second_result = second_response.json()
    assert second_result["session_status"] == "new_activity"
    assert second_result["should_create_review_activity"] is True
    assert len(second_result["created_evidence"]) == 1
    assert second_result["created_evidence"][0]["zone_id"] == yard_zone_id


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
