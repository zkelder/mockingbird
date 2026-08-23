from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def zeros(width: int, height: int) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def evaluate_payload(**overrides):
    payload = {
        "previous_frame": zeros(4, 4),
        "current_frame": zeros(4, 4),
        "zones": [
            {
                "zone_id": "feeder",
                "left": 0.0,
                "top": 0.0,
                "right": 0.5,
                "bottom": 0.5,
            }
        ],
        "frame_index": 3,
        "pixel_delta_threshold": 25.0,
        "min_changed_ratio": 0.02,
    }
    payload.update(overrides)
    return payload


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    events = await client.get("/api/events")
    visits = await client.get("/api/visits")
    review_labels = await client.get("/api/review-labels")
    exports = await client.get("/api/dataset-exports")

    assert events.status_code == 200
    assert visits.status_code == 200
    assert review_labels.status_code == 200
    assert exports.status_code == 200

    return {
        "events": len(events.json()),
        "visits": len(visits.json()),
        "review_labels": len(review_labels.json()),
        "exports": len(exports.json()),
    }


async def test_evaluate_frame_with_no_motion_returns_no_triggered_zones(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/motion/evaluate-frame", json=evaluate_payload())

    assert response.status_code == 200
    result = response.json()
    assert result["frame_index"] == 3
    assert result["triggered_zone_ids"] == []
    assert result["strongest_zone_id"] == "feeder"
    assert result["strongest_changed_ratio"] == 0.0
    assert result["scores"][0]["changed_pixels"] == 0
    assert result["scores"][0]["triggered"] is False


async def test_evaluate_frame_motion_inside_zone_triggers_that_zone(
    client: httpx.AsyncClient,
) -> None:
    current_frame = zeros(4, 4)
    current_frame[1][1] = 255

    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(current_frame=current_frame, min_changed_ratio=0.25),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["triggered_zone_ids"] == ["feeder"]
    assert result["scores"][0]["changed_pixels"] == 1
    assert result["scores"][0]["changed_ratio"] == 0.25
    assert result["scores"][0]["triggered"] is True


async def test_evaluate_frame_motion_outside_zone_does_not_trigger_that_zone(
    client: httpx.AsyncClient,
) -> None:
    current_frame = zeros(4, 4)
    current_frame[3][3] = 255

    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(current_frame=current_frame),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["triggered_zone_ids"] == []
    assert result["scores"][0]["changed_pixels"] == 0
    assert result["scores"][0]["triggered"] is False


async def test_evaluate_frame_multiple_zones_return_independent_scores(
    client: httpx.AsyncClient,
) -> None:
    current_frame = zeros(4, 4)
    current_frame[0][0] = 255
    current_frame[3][3] = 255
    zones = [
        {"zone_id": "feeder", "left": 0.0, "top": 0.0, "right": 0.5, "bottom": 0.5},
        {"zone_id": "ground", "left": 0.5, "top": 0.5, "right": 1.0, "bottom": 1.0},
    ]

    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(current_frame=current_frame, zones=zones),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["triggered_zone_ids"] == ["feeder", "ground"]
    assert {score["zone_id"]: score["changed_pixels"] for score in result["scores"]} == {
        "feeder": 1,
        "ground": 1,
    }


async def test_evaluate_frame_returns_strongest_zone(client: httpx.AsyncClient) -> None:
    current_frame = zeros(4, 4)
    current_frame[0][0] = 255
    for y in range(2):
        for x in range(2, 4):
            current_frame[y][x] = 255
    zones = [
        {"zone_id": "feeder", "left": 0.0, "top": 0.0, "right": 0.5, "bottom": 0.5},
        {"zone_id": "birdbath", "left": 0.5, "top": 0.0, "right": 1.0, "bottom": 0.5},
    ]

    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(current_frame=current_frame, zones=zones),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["strongest_zone_id"] == "birdbath"
    assert result["strongest_changed_ratio"] == 1.0


async def test_evaluate_frame_rejects_invalid_frame_dimensions(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(
            previous_frame=[[0, 0]],
            current_frame=[[0, 0], [0, 0]],
        ),
    )

    assert response.status_code == 400
    assert "dimensions" in response.json()["detail"]


async def test_evaluate_frame_rejects_invalid_zone_bounds(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(
            zones=[
                {
                    "zone_id": "bad-zone",
                    "left": 0.5,
                    "top": 0.0,
                    "right": 0.5,
                    "bottom": 1.0,
                }
            ],
        ),
    )

    assert response.status_code == 400
    assert "left < right" in response.json()["detail"]


async def test_evaluate_frame_allows_empty_zones(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(zones=[]),
    )

    assert response.status_code == 200
    assert response.json() == {
        "frame_index": 3,
        "scores": [],
        "triggered_zone_ids": [],
        "strongest_zone_id": None,
        "strongest_changed_ratio": 0.0,
    }


async def test_extract_candidates_returns_candidate_after_enough_triggered_frames(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/motion/extract-candidates",
        json={
            "frame_scores": [
                {
                    "frame_index": 0,
                    "scores": [
                        {
                            "zone_id": "feeder",
                            "changed_pixels": 40,
                            "total_pixels": 100,
                            "changed_ratio": 0.4,
                            "mean_delta": 60.0,
                            "triggered": True,
                        }
                    ],
                    "triggered_zone_ids": ["feeder"],
                    "strongest_zone_id": "feeder",
                    "strongest_changed_ratio": 0.4,
                },
                {
                    "frame_index": 1,
                    "scores": [
                        {
                            "zone_id": "feeder",
                            "changed_pixels": 70,
                            "total_pixels": 100,
                            "changed_ratio": 0.7,
                            "mean_delta": 90.0,
                            "triggered": True,
                        }
                    ],
                    "triggered_zone_ids": ["feeder"],
                    "strongest_zone_id": "feeder",
                    "strongest_changed_ratio": 0.7,
                },
            ],
            "min_triggered_frames": 2,
            "max_gap_frames": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["candidates"] == [
        {
            "zone_id": "feeder",
            "start_frame_index": 0,
            "end_frame_index": 1,
            "best_frame_index": 1,
            "peak_changed_ratio": 0.7,
            "triggered_frame_count": 2,
        }
    ]


async def test_extract_candidates_bridges_short_gap(client: httpx.AsyncClient) -> None:
    frame_scores = []
    for frame_index, ratio, triggered in [
        (0, 0.4, True),
        (1, 0.0, False),
        (2, 0.6, True),
    ]:
        frame_scores.append(
            {
                "frame_index": frame_index,
                "scores": [
                    {
                        "zone_id": "feeder",
                        "changed_pixels": int(ratio * 100),
                        "total_pixels": 100,
                        "changed_ratio": ratio,
                        "mean_delta": ratio * 255,
                        "triggered": triggered,
                    }
                ],
                "triggered_zone_ids": ["feeder"] if triggered else [],
                "strongest_zone_id": "feeder",
                "strongest_changed_ratio": ratio,
            }
        )

    response = await client.post(
        "/api/motion/extract-candidates",
        json={
            "frame_scores": frame_scores,
            "min_triggered_frames": 2,
            "max_gap_frames": 1,
        },
    )

    assert response.status_code == 200
    candidate = response.json()["candidates"][0]
    assert candidate["start_frame_index"] == 0
    assert candidate["end_frame_index"] == 2
    assert candidate["best_frame_index"] == 2
    assert candidate["triggered_frame_count"] == 2


async def test_motion_api_does_not_create_product_truth(client: httpx.AsyncClient) -> None:
    before_counts = await product_counts(client)
    current_frame = zeros(4, 4)
    current_frame[1][1] = 255

    evaluate_response = await client.post(
        "/api/motion/evaluate-frame",
        json=evaluate_payload(current_frame=current_frame, min_changed_ratio=0.25),
    )
    candidates_response = await client.post(
        "/api/motion/extract-candidates",
        json={
            "frame_scores": [evaluate_response.json()],
            "min_triggered_frames": 1,
            "max_gap_frames": 0,
        },
    )

    assert evaluate_response.status_code == 200
    assert candidates_response.status_code == 200
    assert candidates_response.json()["candidates"]
    assert await product_counts(client) == before_counts
    response_text = str(candidates_response.json())
    assert "event_id" not in response_text
    assert "visit_id" not in response_text
    assert "review_label" not in response_text
    assert "export" not in response_text
