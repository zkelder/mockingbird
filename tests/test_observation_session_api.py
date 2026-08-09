"""API contract for the simple observation control (Product requirement 1):
start/stop/status over HTTP, Camera Node unavailable state, and
side-effect-free status reads. The underlying session lifecycle itself is
covered in depth by `tests/test_engine_runtime.py`; this file only proves
the FastAPI route wiring and response shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.demo_data import STREAM_ID as DEMO_STREAM_ID
from mockingbird.repository.product_repository import ProductRepository


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def client(repository: ProductRepository) -> TestClient:
    return TestClient(app)


def test_start_on_unknown_stream_returns_404(client: TestClient) -> None:
    response = client.post("/api/streams/does-not-exist/observation/start")
    assert response.status_code == 404


def test_status_on_unknown_stream_returns_404(client: TestClient) -> None:
    response = client.get("/api/streams/does-not-exist/observation/status")
    assert response.status_code == 404


def test_stop_on_unknown_stream_returns_404(client: TestClient) -> None:
    response = client.post("/api/streams/does-not-exist/observation/stop")
    assert response.status_code == 404


def test_status_before_start_is_stopped_and_side_effect_free(
    client: TestClient, repository: ProductRepository,
) -> None:
    response = client.get(f"/api/streams/{DEMO_STREAM_ID}/observation/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "stopped"
    assert payload["observing"] is False
    assert payload["stream_id"] == DEMO_STREAM_ID
    # Side-effect-free: no session was created, no authority state touched.
    assert repository.get_observation_authority_state().mode == "shadow"


def test_start_on_non_camera_node_stream_is_honest_not_a_crash(
    client: TestClient, repository: ProductRepository,
) -> None:
    """The demo/seed stream is not a paired Camera Node. Product requirement
    1 requires a calm, honest status here -- never a 500, never a silent
    fallback to a different runtime."""

    response = client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["observing"] is False
    assert "Camera Node" in payload["camera_message"]
    # Never expose internal Stage numbers/vendor terms in this basic contract.
    for forbidden in ("Stage 7", "AssembledVisitProposal", "ONNX", "CUDA", "candidate_visit_authority"):
        assert forbidden not in payload["message"]
        assert forbidden not in payload["camera_message"]


def test_stop_without_a_running_session_is_a_clean_no_op(
    client: TestClient, repository: ProductRepository,
) -> None:
    response = client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/stop")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "stopped"
    assert payload["observing"] is False


def test_status_response_never_exposes_internal_vocabulary(
    client: TestClient, repository: ProductRepository,
) -> None:
    client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start")
    response = client.get(f"/api/streams/{DEMO_STREAM_ID}/observation/status")
    body = response.text
    for forbidden in ("Stage 7", "AssembledVisitProposal", "provider_generation", "candidate_visit_authority"):
        assert forbidden not in body
