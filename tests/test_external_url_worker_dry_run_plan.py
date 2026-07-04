from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
DRY_RUN_ROUTE = "/api/workers/external-url-preview/dry-run"
WORKER_KEY = "external_url_preview_scheduler_future"


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


async def configure_external_url(
    client: httpx.AsyncClient,
    config: dict[str, str] | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": config or {}},
    )
    assert response.status_code == 200


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "media_assets": await client.get("/api/media"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "review_labels": await client.get("/api/review-labels"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "media_assets": len(responses["media_assets"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


def fail_fetch(*_args, **_kwargs) -> None:
    raise AssertionError("External URL worker dry-run must not fetch")


def assert_no_work_planned(item: dict) -> None:
    assert item["would_fetch"] is False
    assert item["would_create_media_asset"] is False
    assert item["would_create_motion_evidence"] is False
    assert item["would_create_event"] is False
    assert item["would_create_visit"] is False
    assert item["would_create_review_label"] is False
    assert item["would_create_truth"] is False


async def test_external_url_worker_dry_run_is_read_only_no_fetch_no_records(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_external_url(client, {"url": "http://example.local/still.jpg"})
    monkeypatch.setattr(
        "mockingbird.api.main.external_url_preview.fetch_external_url_preview",
        fail_fetch,
    )
    before = await product_counts(client)

    response = await client.get(DRY_RUN_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["worker_key"] == WORKER_KEY
    assert body["provider_key"] == "external_url"
    assert body["read_only"] is True
    assert body["dry_run"] is True

    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["source_id"] == SOURCE_ID
    assert item["provider_key"] == "external_url"
    assert item["worker_key"] == WORKER_KEY
    assert item["eligible"] is True
    assert item["state"] == "disabled"
    assert item["reasons"] == [
        "external_url provider configured",
        "future scheduler disabled",
        "dry run only; no fetch performed",
    ]
    assert_no_work_planned(item)

    summary = body["summary"]
    assert summary["total_sources_considered"] == 1
    assert summary["eligible_sources"] == 1
    assert summary["ineligible_sources"] == 0
    assert summary["would_fetch_count"] == 0
    assert summary["would_create_media_asset_count"] == 0
    assert summary["would_create_motion_evidence_count"] == 0
    assert summary["would_create_truth_count"] == 0

    assert await product_counts(client) == before


async def test_external_url_worker_dry_run_reports_missing_url_configuration(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url(client)

    response = await client.get(DRY_RUN_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["eligible"] is False
    assert item["state"] == "disabled"
    assert "missing external URL configuration" in item["reasons"]
    assert_no_work_planned(item)
    assert body["summary"]["eligible_sources"] == 0
    assert body["summary"]["ineligible_sources"] == 1


async def test_external_url_worker_dry_run_ignores_non_external_url_sources(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(DRY_RUN_ROUTE)

    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["summary"]["total_sources_considered"] == 0
    assert body["summary"]["would_fetch_count"] == 0
    assert body["summary"]["would_create_truth_count"] == 0
