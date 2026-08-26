"""API-surface tests for Ecological Interoperability & Submission Workflows
v1's HTTP routes. Real eligibility/prepare/export behavior is already
exercised thoroughly in `tests/test_ecological_interoperability_repository.
py`; these tests only cover request/response wiring and error mapping --
mirroring `tests/test_research_export_api.py`'s identical, established
scope.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio


class _StaticTaxonomyRequester:
    """Never opens a real socket -- every API-level test here only cares
    about HTTP wiring, not live taxonomy resolution (that's covered
    thoroughly in tests/test_ecological_interoperability_repository.py)."""

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        if "Cardinal" in url:
            return json.dumps(
                {"results": [{"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"}]}
            ).encode("utf-8")
        return json.dumps({"results": []}).encode("utf-8")


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
        ecological_export_root=tmp_path / "ecological_exports",
        inaturalist_taxonomy_requester=_StaticTaxonomyRequester(),
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def test_list_destinations_reports_ebird_as_not_offered_with_a_reason(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/ecological/destinations")
    assert response.status_code == 200
    body = {entry["key"]: entry for entry in response.json()}
    assert body["inaturalist"]["offered"] is True
    assert body["ebird"]["offered"] is False
    assert "feeder" in body["ebird"]["offered_reason"].lower()


async def test_eligibility_preview_round_trips(client: httpx.AsyncClient, isolated_repository: ProductRepository) -> None:
    visits = isolated_repository.review_queue_items()
    visit_id = next(item.target_id for item in visits if item.target_type == "visit")
    isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label="northern_cardinal",
            review_origin="human", reviewer_identity="jane researcher",
        )
    )
    response = await client.post("/api/ecological/eligibility-preview", json={"destination": "inaturalist"})
    assert response.status_code == 200
    body = response.json()
    assert body["destination"]["key"] == "inaturalist"
    assert any(item["visit_id"] == visit_id for item in body["items"])


async def test_prepare_requires_authentication(isolated_repository: ProductRepository) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as anonymous_client:
        response = await anonymous_client.post(
            "/api/ecological/submissions", json={"visit_ids": ["visit-1"], "destination": "inaturalist"},
        )
    assert response.status_code == 401


async def test_prepare_list_get_and_export_round_trip(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    visits = isolated_repository.review_queue_items()
    visit_id = next(item.target_id for item in visits if item.target_type == "visit")
    isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label="northern_cardinal",
            review_origin="human", reviewer_identity="jane researcher",
        )
    )

    prepare_response = await client.post(
        "/api/ecological/submissions", json={"visit_ids": [visit_id], "destination": "inaturalist"},
    )
    assert prepare_response.status_code == 201
    record = prepare_response.json()[0]
    submission_id = record["id"]

    list_response = await client.get(f"/api/ecological/submissions?visit_id={visit_id}")
    assert list_response.status_code == 200
    assert any(item["id"] == submission_id for item in list_response.json())

    get_response = await client.get(f"/api/ecological/submissions/{submission_id}")
    assert get_response.status_code == 200
    assert get_response.json()["visit_id"] == visit_id

    missing_response = await client.get("/api/ecological/submissions/does-not-exist")
    assert missing_response.status_code == 404

    export_response = await client.post(
        "/api/ecological/submissions/export", json={"submission_ids": [submission_id]},
    )
    assert export_response.status_code == 201
    export_body = export_response.json()
    assert export_body["included_count"] == 1
    assert "inaturalist_import.csv" in {f["name"] for f in export_body["files"]}

    result_response = await client.post(
        f"/api/ecological/submissions/{submission_id}/record-result",
        json={"external_id": "12345", "external_url": "https://www.inaturalist.org/observations/12345"},
    )
    assert result_response.status_code == 200
    assert result_response.json()["status"] == "submitted"

    missing_result_response = await client.post(
        "/api/ecological/submissions/does-not-exist/record-result", json={"external_id": "1"},
    )
    assert missing_result_response.status_code == 404


async def test_record_result_rejects_a_javascript_scheme_external_url(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    visits = isolated_repository.review_queue_items()
    visit_id = next(item.target_id for item in visits if item.target_type == "visit")
    isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label="northern_cardinal",
            review_origin="human", reviewer_identity="jane researcher",
        )
    )
    prepare_response = await client.post(
        "/api/ecological/submissions", json={"visit_ids": [visit_id], "destination": "inaturalist"},
    )
    submission_id = prepare_response.json()[0]["id"]

    response = await client.post(
        f"/api/ecological/submissions/{submission_id}/record-result",
        json={"external_url": "javascript:alert(1)"},
    )
    assert response.status_code == 422


async def test_prepare_rejects_an_empty_visit_id_list(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/ecological/submissions", json={"visit_ids": [], "destination": "inaturalist"})
    assert response.status_code == 422


async def test_location_input_rejects_a_choice_without_coordinates(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/ecological/submissions",
        json={
            "visit_ids": ["visit-1"], "destination": "inaturalist",
            "location": {"choice": "exact", "latitude": None, "longitude": None},
        },
    )
    assert response.status_code == 422
