from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, VisitModel


pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"


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


async def import_review_visit(
    client: httpx.AsyncClient,
    *,
    title: str,
    subject_label: str = "unknown_bird",
    species_guess: str = "unknown_bird",
) -> dict[str, object]:
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": ZONE_ID,
            "title": title,
            "subject_label": subject_label,
            "species_guess": species_guess,
        },
        files={"file": (f"{title}.png", b"saved review evidence", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def add_unresolved_visit_without_media(repository: ProductRepository, visit_id: str) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title="Unresolved Visit without saved evidence",
                    event_type="manual_review_fixture",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                    primary_zone_id=ZONE_ID,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess="unknown_bird",
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )


async def product_snapshot(client: httpx.AsyncClient) -> dict[str, int]:
    local_data, suggestions, labels = await asyncio.gather(
        client.get("/api/settings/local-data"),
        client.get("/api/species-suggestions"),
        client.get("/api/review-labels"),
    )
    assert local_data.status_code == 200
    assert suggestions.status_code == 200
    assert labels.status_code == 200
    return {
        "events": local_data.json()["event_count"],
        "visits": local_data.json()["visit_count"],
        "suggestions": len(suggestions.json()["species_suggestions"]),
        "review_labels": len(labels.json()),
    }


async def test_species_suggestion_batch_preflight_bounds_25_targets_and_stays_read_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    imported = [
        await import_review_visit(client, title=f"Batch target {index}")
        for index in range(25)
    ]
    visit_ids = [str(item["visit"]["id"]) for item in imported]
    media_asset_ids = [str(item["media_asset"]["id"]) for item in imported]
    before = await product_snapshot(client)

    original_summary = ProductRepository._review_identification_summary_for_item

    def runnable_summary(
        self: ProductRepository,
        *args: object,
        **kwargs: object,
    ):
        return original_summary(self, *args, **kwargs).model_copy(update={"can_run": True})

    monkeypatch.setattr(
        ProductRepository,
        "_review_identification_summary_for_item",
        runnable_summary,
    )

    def fail_if_single_visit_analysis_is_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Batch preflight must not invoke the single-Visit analyzer")

    monkeypatch.setattr(
        ProductRepository,
        "start_visit_identification_assistant",
        fail_if_single_visit_analysis_is_called,
    )
    response = await client.post(
        "/api/review-queue/species-suggestions/prepare",
        json={"visit_ids": visit_ids},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 25
    assert body["queued_count"] == 25
    assert body["skipped_count"] == 0
    assert body["setup_required_count"] == 0
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert [result["visit_id"] for result in body["results"]] == visit_ids
    assert [result["status"] for result in body["results"]] == ["queued"] * 25
    assert [result["media_asset_id"] for result in body["results"]] == media_asset_ids
    assert await product_snapshot(client) == before

    oversized = await client.post(
        "/api/review-queue/species-suggestions/prepare",
        json={"visit_ids": [*visit_ids, visit_ids[0]]},
    )
    assert oversized.status_code == 422
    assert await product_snapshot(client) == before


async def test_species_suggestion_batch_preflight_skips_ineligible_targets_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    eligible = await import_review_visit(client, title="Eligible bird Visit")
    non_bird = await import_review_visit(
        client,
        title="Known non-bird Visit",
        subject_label="squirrel",
        species_guess="squirrel",
    )
    reviewed = await import_review_visit(client, title="Reviewed bird Visit")
    reviewed_visit_id = str(reviewed["visit"]["id"])
    correction = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": reviewed_visit_id,
            "label": "northern_cardinal",
        },
    )
    assert correction.status_code == 201
    no_media_visit_id = "visit-batch-without-media"
    add_unresolved_visit_without_media(isolated_repository, no_media_visit_id)
    before = await product_snapshot(client)
    eligible_visit_id = str(eligible["visit"]["id"])

    response = await client.post(
        "/api/review-queue/species-suggestions/prepare",
        json={
            "visit_ids": [
                eligible_visit_id,
                no_media_visit_id,
                str(non_bird["visit"]["id"]),
                reviewed_visit_id,
                eligible_visit_id,
                "visit-batch-missing",
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requested_count"] == 6
    assert body["queued_count"] == 0
    assert body["skipped_count"] == 5
    assert body["setup_required_count"] == 1
    assert [result["status"] for result in body["results"]] == [
        "setup_required",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
        "skipped",
    ]
    assert body["results"][0]["media_asset_id"] == eligible["media_asset"]["id"]
    assert "setup is required" in body["results"][0]["message"]
    assert "No usable saved image" in body["results"][1]["message"]
    assert "not currently a bird-review candidate" in body["results"][2]["message"]
    assert "no longer unresolved" in body["results"][3]["message"]
    assert "Duplicate Visit id" in body["results"][4]["message"]
    assert "unavailable" in body["results"][5]["message"]
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert await product_snapshot(client) == before


async def test_species_suggestion_batch_preflight_continues_after_setup_required_item(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runnable = await import_review_visit(client, title="Runnable batch bird Visit")
    setup_required = await import_review_visit(client, title="Setup-required batch bird Visit")
    runnable_visit_id = str(runnable["visit"]["id"])
    original_summary = ProductRepository._review_identification_summary_for_item

    def summary_with_one_runnable_target(
        self: ProductRepository,
        session: object,
        item: object,
        **kwargs: object,
    ):
        summary = original_summary(self, session, item, **kwargs)
        if getattr(item, "target_id", None) == runnable_visit_id:
            return summary.model_copy(update={"can_run": True})
        return summary

    monkeypatch.setattr(
        ProductRepository,
        "_review_identification_summary_for_item",
        summary_with_one_runnable_target,
    )
    before = await product_snapshot(client)

    response = await client.post(
        "/api/review-queue/species-suggestions/prepare",
        json={"visit_ids": [runnable_visit_id, setup_required["visit"]["id"]]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["queued_count"] == 1
    assert body["setup_required_count"] == 1
    assert body["skipped_count"] == 0
    assert [result["status"] for result in body["results"]] == [
        "queued",
        "setup_required",
    ]
    assert body["results"][0]["media_asset_id"] == runnable["media_asset"]["id"]
    assert body["results"][1]["media_asset_id"] == setup_required["media_asset"]["id"]
    assert await product_snapshot(client) == before


@pytest.mark.parametrize(
    "unexpected_input",
    [
        {"media_asset_id": "media-unrelated"},
        {"image_path": "/tmp/untrusted-image.jpg"},
        {"url": "https://example.invalid/untrusted-image.jpg"},
        {"model_path": "/tmp/untrusted-model.bin"},
    ],
)
async def test_species_suggestion_batch_preflight_rejects_arbitrary_input(
    client: httpx.AsyncClient,
    unexpected_input: dict[str, str],
) -> None:
    imported = await import_review_visit(client, title="Strict batch boundary Visit")
    before = await product_snapshot(client)

    response = await client.post(
        "/api/review-queue/species-suggestions/prepare",
        json={"visit_ids": [imported["visit"]["id"]], **unexpected_input},
    )

    assert response.status_code == 422
    assert await product_snapshot(client) == before
