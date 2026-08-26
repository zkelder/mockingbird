"""API-surface tests for Research / Conservation / Export Interoperability
v1's HTTP routes. The real eligibility/export/mapping behavior is already
exercised thoroughly in `tests/test_research_export_repository.py`; these
tests only cover request/response wiring and error mapping -- mirroring
`tests/test_recorded_media_analysis_api.py`'s identical, established scope.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def test_research_export_dry_run_round_trips(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/research/export", json={"dry_run": True})
    assert response.status_code == 201
    body = response.json()
    assert body["dry_run"] is True
    assert body["manifest"]["schema_version"] == "research-export-v1"
    assert "observations.csv" in {f["name"] for f in body["files"]}


async def test_camtrap_dp_export_dry_run_round_trips(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/research/export-camtrap-dp", json={"dry_run": True})
    assert response.status_code == 201
    body = response.json()
    assert body["profile_version"] == "1.0.2"
    assert body["validation"]["valid"] is True


async def test_conservation_report_round_trips(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/research/conservation-report",
        json={"start_at": "2026-08-01T00:00:00Z", "end_at": "2026-08-08T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "population" not in body
    assert "abundance" not in body
    assert body["maturity"] in ("no_data", "sparse", "usable")


async def test_conservation_report_rejects_an_inverted_range(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/research/conservation-report",
        json={"start_at": "2026-08-08T00:00:00Z", "end_at": "2026-08-01T00:00:00Z"},
    )
    assert response.status_code == 422


async def test_research_collection_create_list_and_get(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    visits = isolated_repository.review_queue_items()
    assert visits, "seeded demo data must include at least one reviewable item"
    visit_id = next(item.target_id for item in visits if item.target_type == "visit")
    isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label="northern_cardinal",
            review_origin="human", reviewer_identity="jane researcher",
        )
    )

    create_response = await client.post(
        "/api/research/collections",
        json={"name": "API Test Collection", "curator_identity": "jane researcher", "visit_ids": [visit_id]},
    )
    assert create_response.status_code == 201
    collection_id = create_response.json()["id"]
    assert create_response.json()["eligible_observation_count"] == 1

    list_response = await client.get("/api/research/collections")
    assert list_response.status_code == 200
    assert any(entry["id"] == collection_id for entry in list_response.json())

    get_response = await client.get(f"/api/research/collections/{collection_id}")
    assert get_response.status_code == 200
    assert get_response.json()["curator_identity"] == "jane researcher"

    missing_response = await client.get("/api/research/collections/does-not-exist")
    assert missing_response.status_code == 404


async def test_research_collection_create_requires_at_least_one_visit(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/research/collections", json={"name": "Empty", "visit_ids": []})
    assert response.status_code == 422


async def test_darwin_core_export_dry_run_round_trips(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/research/export-darwin-core", json={"dry_run": True})
    assert response.status_code == 201
    body = response.json()
    assert body["dry_run"] is True
    assert body["schema_version"] == "darwin-core-archive-v1"
    assert {"occurrence.csv", "meta.xml", "eml.xml"} == {f["name"] for f in body["files"]}


async def test_darwin_core_export_writes_real_files(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/research/export-darwin-core",
        json={"site_name": "Example Yard", "latitude": 40.015, "longitude": -105.2705},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["dry_run"] is False
    assert body["output_directory"] is not None
    output_dir = Path(body["output_directory"])
    assert (output_dir / "occurrence.csv").exists()
    assert (output_dir / "meta.xml").exists()
    assert (output_dir / "eml.xml").exists()
