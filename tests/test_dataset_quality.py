from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
VISIT_ID = "visit-bird-feeder-001"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
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


async def import_unknown_bird(client: httpx.AsyncClient, *, zone_id: str | None = FEEDER_ZONE_ID):
    data = {
        "stream_id": STREAM_ID,
        "title": "Unknown bird import",
        "subject_label": "unknown_bird",
        "species_guess": "unknown_bird",
        "notes": "Local media for dataset QA.",
    }
    if zone_id is not None:
        data["zone_id"] = zone_id

    return await client.post(
        "/api/media/import",
        data=data,
        files={"file": ("qa-bird.png", b"quality image bytes", "image/png")},
    )


def issues_by_type(summary: dict) -> dict[str, list[dict]]:
    issues: dict[str, list[dict]] = {}
    for issue in summary["issues"]:
        issues.setdefault(issue["issue_type"], []).append(issue)
    return issues


async def test_dataset_quality_summary_shape(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/dataset-quality/summary")

    assert response.status_code == 200
    summary = response.json()
    assert summary["issue_count"] == 1
    assert summary["high_count"] == 1
    assert summary["medium_count"] == 0
    assert summary["low_count"] == 0
    assert summary["export_ready_count"] == 1
    assert summary["needs_review_count"] == 1
    assert "corrected labels as local dataset truth" in summary["local_first_note"]
    assert issues_by_type(summary)["needs_review"][0]["target_type"] == "visit"


async def test_unknown_bird_issue_decreases_after_species_correction(
    client: httpx.AsyncClient,
) -> None:
    imported = (await import_unknown_bird(client)).json()
    before = (await client.get("/api/dataset-quality/summary")).json()

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": imported["visit"]["id"],
            "label": "Northern Cardinal",
            "notes": "Resolved unknown bird for QA.",
        },
    )
    after = (await client.get("/api/dataset-quality/summary")).json()

    assert correction_response.status_code == 201
    assert before["unknown_label_count"] >= 1
    assert after["unknown_label_count"] == before["unknown_label_count"] - 1
    assert all(issue["label"] != "unknown_bird" for issue in after["issues"])


async def test_freeform_label_creates_low_priority_quality_issue(
    client: httpx.AsyncClient,
) -> None:
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "mystery feeder guest",
            "notes": "Allowed local label outside taxonomy.",
        },
    )
    summary = (await client.get("/api/dataset-quality/summary")).json()
    freeform_issue = issues_by_type(summary)["freeform_label"][0]

    assert correction_response.status_code == 201
    assert summary["freeform_label_count"] == 1
    assert freeform_issue["severity"] == "low"
    assert freeform_issue["label"] == "mystery_feeder_guest"


async def test_conflicting_corrections_are_reported(client: httpx.AsyncClient) -> None:
    first = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "Northern Cardinal",
            "notes": "First correction.",
        },
    )
    second = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "Blue Jay",
            "notes": "Conflicting correction.",
        },
    )
    summary = (await client.get("/api/dataset-quality/summary")).json()
    conflict_issue = issues_by_type(summary)["conflicting_corrections"][0]

    assert first.status_code == 201
    assert second.status_code == 201
    assert summary["conflicting_correction_count"] == 1
    assert conflict_issue["severity"] == "medium"
    assert conflict_issue["target_id"] == VISIT_ID


async def test_missing_zone_context_is_reported_for_export_ready_record(
    client: httpx.AsyncClient,
) -> None:
    imported = (await import_unknown_bird(client, zone_id=None)).json()

    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": imported["visit"]["id"],
            "label": "Northern Cardinal",
            "notes": "Reviewed import without zone context.",
        },
    )
    summary = (await client.get("/api/dataset-quality/summary")).json()
    missing_zone_issue = next(
        issue
        for issue in issues_by_type(summary)["missing_zone"]
        if issue["visit_id"] == imported["visit"]["id"]
    )

    assert correction_response.status_code == 201
    assert summary["missing_zone_count"] >= 1
    assert missing_zone_issue["severity"] == "medium"


async def test_false_positive_is_counted_but_not_species_truth(client: httpx.AsyncClient) -> None:
    correction_response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", 
            "target_type": "visit",
            "target_id": VISIT_ID,
            "label": "false_positive",
            "notes": "Not an animal visit.",
        },
    )
    quality = (await client.get("/api/dataset-quality/summary")).json()
    coverage = (await client.get("/api/dataset-coverage/summary")).json()

    assert correction_response.status_code == 201
    assert quality["false_positive_count"] == 1
    assert coverage["reviewed_species_count"] == 0


async def test_dataset_quality_issue_list_is_bounded_but_counts_stay_exact(
    client: httpx.AsyncClient,
) -> None:
    """v0.1 Product Flow Gap Pass v1: a real installation's Dataset QA panel
    (Insights/Analytics page) rendered its full, unbounded `issues` array
    with no cap -- a real 420-issue history produced a 51,000+px page
    section. The detailed `issues` list must be bounded, but the aggregate
    counts (`issue_count`, `high_count`, `unknown_label_count`, ...) --
    already correctly computed from every qualifying record -- must stay
    exact, not silently shrink to match the now-truncated list."""

    before = (await client.get("/api/dataset-quality/summary")).json()

    # Each uncorrected "unknown bird" import creates exactly two issues
    # (needs_review + unknown_label): 30 imports comfortably exceeds the
    # bounded display limit while keeping this test fast (local sqlite
    # writes only, no real media/model work).
    for _ in range(30):
        response = await import_unknown_bird(client)
        assert response.status_code == 201

    after = (await client.get("/api/dataset-quality/summary")).json()

    assert after["issue_count"] == before["issue_count"] + 60
    assert after["high_count"] == before["high_count"] + 30
    assert after["unknown_label_count"] == before["unknown_label_count"] + 30
    assert after["needs_review_count"] == before["needs_review_count"] + 30
    assert len(after["issues"]) <= 50
    assert len(after["issues"]) < after["issue_count"]


async def test_dataset_quality_aligns_with_coverage_and_ignores_raw_proposal_truth(
    client: httpx.AsyncClient,
) -> None:
    media_asset = (await import_unknown_bird(client)).json()["media_asset"]
    before_quality = (await client.get("/api/dataset-quality/summary")).json()

    demo_response = await client.post(
        "/api/detection-runs/demo",
        json={
            "media_asset_id": media_asset["id"],
            "label": "candidate_hawk",
            "confidence": 0.72,
            "suggested_subject_label": "unknown_bird",
            "suggested_species": "blue_jay",
            "notes": "Proposal evidence should not become export truth.",
        },
    )
    proposal = demo_response.json()["proposals"][0]
    decision_response = await client.post(
        f"/api/detection-proposals/{proposal['id']}/decision",
        json={"decision": "convert_to_event"},
    )
    quality = (await client.get("/api/dataset-quality/summary")).json()
    coverage = (await client.get("/api/dataset-coverage/summary")).json()

    assert demo_response.status_code == 201
    assert decision_response.status_code == 200
    assert quality["export_ready_count"] == coverage["export_ready_count"]
    assert quality["needs_review_count"] == coverage["needs_review_count"]
    assert quality["export_ready_count"] == before_quality["export_ready_count"]
    assert all(issue["label"] != "candidate_hawk" for issue in quality["issues"])
