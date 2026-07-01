from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    configure_repository(repository)
    yield
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def zeros(width: int = 4, height: int = 4) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def frame_with(pixels: list[tuple[int, int]]) -> list[list[int]]:
    frame = zeros()
    for y, x in pixels:
        frame[y][x] = 255
    return frame


def feeder_zone() -> dict[str, float | str]:
    return {
        "zone_id": FEEDER_ZONE_ID,
        "left": 0.0,
        "top": 0.0,
        "right": 0.5,
        "bottom": 0.5,
    }


def ground_zone() -> dict[str, float | str]:
    return {
        "zone_id": GROUND_ZONE_ID,
        "left": 0.5,
        "top": 0.5,
        "right": 1.0,
        "bottom": 1.0,
    }


def sequence_payload(**overrides):
    payload = {
        "frames": [zeros(), zeros(), zeros()],
        "zones": [feeder_zone()],
        "source_id": SOURCE_ID,
        "stream_id": STREAM_ID,
        "frame_index_start": 0,
        "pixel_delta_threshold": 25.0,
        "min_changed_ratio": 0.25,
        "min_triggered_frames": 2,
        "max_gap_frames": 1,
        "create_motion_evidence": False,
    }
    payload.update(overrides)
    return payload


async def truth_counts(client: httpx.AsyncClient) -> dict[str, int]:
    events = await client.get("/api/events")
    visits = await client.get("/api/visits")
    review_labels = await client.get("/api/review-labels")
    exports = await client.get("/api/dataset-exports")
    coverage = await client.get("/api/dataset-coverage/summary")

    assert events.status_code == 200
    assert visits.status_code == 200
    assert review_labels.status_code == 200
    assert exports.status_code == 200
    assert coverage.status_code == 200

    coverage_summary = coverage.json()
    return {
        "events": len(events.json()),
        "visits": len(visits.json()),
        "review_labels": len(review_labels.json()),
        "exports": len(exports.json()),
        "export_ready_count": coverage_summary["export_ready_count"],
        "reviewed_record_count": coverage_summary["reviewed_record_count"],
    }


async def motion_evidence_count(client: httpx.AsyncClient) -> int:
    response = await client.get("/api/motion/evidence")
    assert response.status_code == 200
    return len(response.json()["motion_evidence"])


async def test_evaluate_sequence_with_no_motion_returns_no_candidates(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/motion/evaluate-sequence", json=sequence_payload())

    assert response.status_code == 200
    result = response.json()
    assert [score["frame_index"] for score in result["frame_scores"]] == [1, 2]
    assert result["candidates"] == []
    assert result["created_evidence"] == []
    assert all(score["triggered_zone_ids"] == [] for score in result["frame_scores"])


async def test_evaluate_sequence_returns_candidate_with_strongest_best_frame(
    client: httpx.AsyncClient,
) -> None:
    frames = [
        zeros(),
        frame_with([(0, 0)]),
        frame_with([(0, 0), (0, 1), (1, 0), (1, 1)]),
    ]

    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(frames=frames, frame_index_start=10),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["candidates"] == [
        {
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 11,
            "end_frame_index": 12,
            "best_frame_index": 12,
            "peak_changed_ratio": 0.75,
            "triggered_frame_count": 2,
        }
    ]


async def test_evaluate_sequence_without_create_does_not_create_motion_evidence(
    client: httpx.AsyncClient,
) -> None:
    before_count = await motion_evidence_count(client)
    frames = [
        zeros(),
        frame_with([(0, 0)]),
        frame_with([(0, 0), (0, 1), (1, 0), (1, 1)]),
    ]

    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(frames=frames, create_motion_evidence=False),
    )

    assert response.status_code == 200
    assert response.json()["candidates"]
    assert response.json()["created_evidence"] == []
    assert await motion_evidence_count(client) == before_count


async def test_evaluate_sequence_can_create_pending_motion_evidence_without_truth(
    client: httpx.AsyncClient,
) -> None:
    before_truth = await truth_counts(client)
    before_evidence_count = await motion_evidence_count(client)
    frames = [
        zeros(),
        frame_with([(0, 0)]),
        frame_with([(0, 0), (0, 1), (1, 0), (1, 1)]),
    ]

    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(
            frames=frames,
            create_motion_evidence=True,
            notes="Sequence-created feeder motion evidence.",
        ),
    )

    assert response.status_code == 200
    result = response.json()
    assert len(result["created_evidence"]) == 1
    evidence = result["created_evidence"][0]
    assert evidence["status"] == "pending"
    assert evidence["source_id"] == SOURCE_ID
    assert evidence["stream_id"] == STREAM_ID
    assert evidence["zone_id"] == FEEDER_ZONE_ID
    assert evidence["start_frame_index"] == 1
    assert evidence["end_frame_index"] == 2
    assert evidence["best_frame_index"] == 2
    assert evidence["peak_changed_ratio"] == 0.75
    assert evidence["triggered_frame_count"] == 2
    assert evidence["scoring_config"] == {
        "source": "frame_sequence_evaluation",
        "pixel_delta_threshold": 25.0,
        "min_changed_ratio": 0.25,
        "min_triggered_frames": 2,
        "max_gap_frames": 1,
        "frame_index_start": 0,
    }
    assert await motion_evidence_count(client) == before_evidence_count + 1
    assert await truth_counts(client) == before_truth


async def test_evaluate_sequence_rejects_short_sequence(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(frames=[zeros()]),
    )

    assert response.status_code == 422


async def test_evaluate_sequence_rejects_invalid_frame_dimensions(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(frames=[[[0, 0]], [[0, 0], [0, 0]]]),
    )

    assert response.status_code == 400
    assert "dimensions" in response.json()["detail"]


async def test_evaluate_sequence_rejects_empty_zones(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(zones=[]),
    )

    assert response.status_code == 422


async def test_evaluate_sequence_bridges_short_gap(client: httpx.AsyncClient) -> None:
    frames = [
        zeros(),
        frame_with([(0, 0)]),
        frame_with([(0, 0)]),
        zeros(),
    ]

    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(frames=frames, max_gap_frames=1),
    )

    assert response.status_code == 200
    assert response.json()["candidates"] == [
        {
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 1,
            "end_frame_index": 3,
            "best_frame_index": 1,
            "peak_changed_ratio": 0.25,
            "triggered_frame_count": 2,
        }
    ]


async def test_evaluate_sequence_creates_evidence_for_multiple_zones(
    client: httpx.AsyncClient,
) -> None:
    frames = [
        zeros(),
        frame_with([(0, 0), (3, 3)]),
        frame_with(
            [
                (0, 0),
                (0, 1),
                (1, 0),
                (1, 1),
                (2, 2),
                (2, 3),
                (3, 2),
                (3, 3),
            ]
        ),
    ]

    response = await client.post(
        "/api/motion/evaluate-sequence",
        json=sequence_payload(
            frames=frames,
            zones=[feeder_zone(), ground_zone()],
            create_motion_evidence=True,
        ),
    )

    assert response.status_code == 200
    result = response.json()
    assert [candidate["zone_id"] for candidate in result["candidates"]] == [
        FEEDER_ZONE_ID,
        GROUND_ZONE_ID,
    ]
    assert [evidence["zone_id"] for evidence in result["created_evidence"]] == [
        FEEDER_ZONE_ID,
        GROUND_ZONE_ID,
    ]
    assert all(evidence["status"] == "pending" for evidence in result["created_evidence"])
