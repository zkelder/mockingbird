from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio


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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


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


def fail_provider_work(*_args, **_kwargs) -> None:
    raise AssertionError("Worker status must not run provider work")


async def test_worker_status_contract_is_read_only_no_runtime(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.external_url_preview.fetch_external_url_preview",
        fail_provider_work,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import",
        fail_provider_work,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.folder_import_preview.preview_folder_import_relative_paths",
        fail_provider_work,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.classify_webhook_payload",
        fail_provider_work,
    )

    before = await product_counts(client)

    response = await client.get("/api/workers/status")

    assert response.status_code == 200
    body = response.json()
    assert body["read_only"] is True

    worker_keys = {worker["worker_key"] for worker in body["workers"]}
    assert worker_keys == {
        "external_url_preview_scheduler_future",
        "folder_import_scan_future",
        "webhook_ingest_queue_future",
        "saved_media_retention_future",
        "model_suggestion_job_future",
    }

    for worker in body["workers"]:
        assert worker["enabled"] is False
        assert worker["implemented"] is False
        assert worker["state"] == "disabled"
        assert worker["last_run_at"] is None
        assert worker["next_run_at"] is None
        assert worker["last_error"] is None
        assert worker["can_create_media_assets"] is False
        assert worker["can_create_motion_evidence"] is False
        assert worker["can_create_events"] is False
        assert worker["can_create_visits"] is False
        assert worker["can_create_review_labels"] is False
        assert worker["can_create_truth"] is False
        assert "future" in worker["worker_key"]
        assert "not implemented" in " ".join(worker["warnings"])

    summary = body["summary"]
    assert summary["total_workers"] == 5
    assert summary["implemented_workers"] == 0
    assert summary["enabled_workers"] == 0
    assert summary["running_workers"] == 0
    assert summary["failed_workers"] == 0
    assert summary["truth_creating_workers"] == 0
    assert summary["warnings"] == [
        "Worker status is read-only placeholder data; no worker runtime exists yet."
    ]

    assert await product_counts(client) == before
