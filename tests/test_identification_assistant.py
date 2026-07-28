from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import VisitEvidenceFrame, VisitIdentificationEvidenceMode
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import ReviewIdentificationAssistantRunModel


STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", raising=False)
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


async def create_visit(client: httpx.AsyncClient) -> dict[str, object]:
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": ZONE_ID,
            "title": "Assistant evidence",
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
        },
        files={"file": ("assistant.png", b"saved evidence", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


async def test_assistant_is_read_only_until_explicit_request(
    client: httpx.AsyncClient,
) -> None:
    imported = await create_visit(client)
    visit_id = imported["visit"]["id"]
    before = (await client.get("/api/settings/local-data")).json()

    response = await client.get(f"/api/visits/{visit_id}/identification-assistant")

    assert response.status_code == 200
    payload = response.json()
    assert payload["visit_id"] == visit_id
    assert payload["attempts"] == []
    assert payload["run"] is None
    assert payload["creates_truth"] is False
    assert payload["creates_export"] is False
    after = (await client.get("/api/settings/local-data")).json()
    assert after["review_label_count"] == before["review_label_count"]
    assert after["event_count"] == before["event_count"]


async def test_unavailable_assistant_request_is_durable_and_idempotent(
    client: httpx.AsyncClient,
) -> None:
    imported = await create_visit(client)
    visit_id = imported["visit"]["id"]
    request = {
        "evidence_mode": "primary_only",
        "idempotency_key": "assistant-request-once",
    }
    before = (await client.get("/api/settings/local-data")).json()

    first = await client.post(f"/api/visits/{visit_id}/identification-assistant", json=request)
    second = await client.post(f"/api/visits/{visit_id}/identification-assistant", json=request)

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["run"]["id"] == second_payload["run"]["id"]
    assert first_payload["run"]["request_origin"] == "user_triggered_review_assistance"
    assert first_payload["run"]["evidence_mode"] == "primary_only"
    assert first_payload["run"]["status"] == "unavailable"
    assert len(first_payload["selected_evidence_frames"]) == 1
    assert first_payload["attempts"]
    assert first_payload["attempts"][0]["outcome"] in {"unsupported", "failed"}
    assert second_payload["message"] == "This identification request was already recorded."
    status = (await client.get("/api/settings/local-data")).json()
    assert status["review_label_count"] == before["review_label_count"]


async def test_completed_identical_input_returns_existing_assistant_run(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    imported = await create_visit(client)
    visit_id = str(imported["visit"]["id"])
    media_asset_id = str(imported["media_asset"]["id"])
    assistant = (
        await client.get(f"/api/visits/{visit_id}/identification-assistant")
    ).json()
    input_hash = hashlib.sha256(
        json.dumps(
            {
                "visit_id": visit_id,
                "evidence_mode": "primary_only",
                "media_asset_ids": [media_asset_id],
                "adapter_id": assistant["availability"]["adapter_id"],
                "candidate_pack_sha256": assistant["availability"]["candidate_pack"]["content_sha256"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                ReviewIdentificationAssistantRunModel(
                    id="review-identification-assistant-existing",
                    visit_id=visit_id,
                    idempotency_key="completed-original-input",
                    evidence_mode="primary_only",
                    selected_media_asset_ids_json=json.dumps([media_asset_id]),
                    input_configuration_sha256=input_hash,
                    request_origin="user_triggered_review_assistance",
                    status="succeeded",
                    started_at=datetime.now(UTC),
                    completed_at=datetime.now(UTC),
                    attempt_ids_json="[]",
                    error_code=None,
                )
            )

    response = await client.post(
        f"/api/visits/{visit_id}/identification-assistant",
        json={
            "evidence_mode": "primary_only",
            "idempotency_key": "completed-repeat-input",
        },
    )

    assert response.status_code == 200
    assert response.json()["run"]["id"] == "review-identification-assistant-existing"
    assert response.json()["message"] == (
        "This exact saved input already has identification evidence."
    )


async def test_reviewed_visit_analysis_does_not_change_existing_truth(
    client: httpx.AsyncClient,
) -> None:
    imported = await create_visit(client)
    visit_id = imported["visit"]["id"]
    correction = await client.post(
        "/api/review-labels",
        json={"target_type": "visit", "target_id": visit_id, "label": "northern_cardinal"},
    )
    assert correction.status_code == 201

    response = await client.post(
        f"/api/visits/{visit_id}/identification-assistant",
        json={
            "evidence_mode": "all_retained_evidence",
            "idempotency_key": "reviewed-visit-assistant",
        },
    )

    assert response.status_code == 200
    visit = (await client.get(f"/api/visits/{visit_id}")).json()
    assert visit["review_status"] == "reviewed"
    assert visit["reviewed_label"] == "northern_cardinal"
    history = (await client.get(f"/api/visits/{visit_id}/correction-history")).json()
    assert len(history["entries"]) == 1


def test_assistant_frame_selection_never_exceeds_retained_evidence_cap(
    isolated_repository: ProductRepository,
) -> None:
    frames = [
        VisitEvidenceFrame(
            media_asset_id=f"media-{index}",
            preview_url=f"/api/media/media-{index}/file",
            captured_at=datetime.now(UTC),
            relative_position=index / 4,
            frame_sequence=index,
            is_primary=index == 2,
            content_type="image/png",
        )
        for index in range(5)
    ]

    primary = isolated_repository._review_identification_assistant_frames(
        frames,
        VisitIdentificationEvidenceMode.primary_only,
    )
    retained = isolated_repository._review_identification_assistant_frames(
        frames,
        VisitIdentificationEvidenceMode.all_retained_evidence,
    )

    assert [frame.media_asset_id for frame in primary] == ["media-2"]
    assert [frame.media_asset_id for frame in retained] == ["media-2"]


def test_assistant_high_resolution_fallback_order(
    isolated_repository: ProductRepository,
) -> None:
    captured_at = datetime.now(UTC)
    monitoring = VisitEvidenceFrame(
        media_asset_id="monitoring-frame",
        preview_url="/api/media/monitoring-frame/preview",
        captured_at=captured_at,
        relative_position=0.0,
        frame_sequence=1,
        is_primary=True,
        content_type="image/jpeg",
    )
    full = monitoring.model_copy(
        update={
            "media_asset_id": "high-resolution-full",
            "is_primary": False,
            "evidence_role": "high_resolution_original",
        }
    )
    crop = monitoring.model_copy(
        update={
            "media_asset_id": "high-resolution-crop",
            "is_primary": False,
            "evidence_role": "activity_crop",
        }
    )

    assert [frame.media_asset_id for frame in isolated_repository._review_identification_assistant_frames(
        [monitoring, full, crop], VisitIdentificationEvidenceMode.primary_only
    )] == ["high-resolution-crop"]
    assert [frame.media_asset_id for frame in isolated_repository._review_identification_assistant_frames(
        [monitoring, full], VisitIdentificationEvidenceMode.primary_only
    )] == ["high-resolution-full"]
    assert [frame.media_asset_id for frame in isolated_repository._review_identification_assistant_frames(
        [monitoring], VisitIdentificationEvidenceMode.primary_only
    )] == ["monitoring-frame"]


async def test_prior_repeated_suggestions_are_displayed_without_double_counting_support(
    client: httpx.AsyncClient,
) -> None:
    imported = await create_visit(client)
    visit_id = imported["visit"]["id"]
    for _ in range(2):
        created = await client.post(
            "/api/species-suggestions/mock",
            json={
                "visit_id": visit_id,
                "adapter_id": "prior-local-analyzer",
                "adapter_name": "Prior local analyzer",
                "suggested_label": "northern_cardinal",
            },
        )
        assert created.status_code == 201

    response = await client.get(f"/api/visits/{visit_id}/identification-assistant")

    assert response.status_code == 200
    rows = [
        row
        for row in response.json()["suggestions"]
        if row["label"] == "northern_cardinal"
    ]
    assert len(rows) == 2
    assert {row["origin"] for row in rows} == {"previously_generated"}
    assert {row["support_count"] for row in rows} == {1}
    assert all("combined_probability" not in row for row in rows)
