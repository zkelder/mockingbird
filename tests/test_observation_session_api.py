"""API contract for the simple observation control (Product requirement 1)
and its Unified Observation Experience v1 lane routing: start/stop/status
over HTTP for the Camera Node lane specifically, honest "no runtime here"
behavior for a Stream with no integrated observation lane at all, and
side-effect-free status reads. The underlying Camera Node session lifecycle
itself is covered in depth by `tests/test_engine_runtime.py`; the other
lanes (live monitoring, Snapshot monitor) are covered by
`tests/test_observation_unified_api.py`. This file proves the FastAPI route
wiring and response shape.
"""

from __future__ import annotations

from pathlib import Path
import time

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


def configure_unpaired_camera_node(client: TestClient) -> None:
    """A real `camera_node` Source (so lane resolution routes to the
    accepted engine) that has never completed pairing."""

    response = client.patch(
        "/api/sources/source-backyard-demo/provider-configuration",
        json={"provider_key": "camera_node", "config": {}},
    )
    assert response.status_code == 200


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


def test_start_on_stream_with_no_observation_runtime_is_honest_not_a_crash(
    client: TestClient, repository: ProductRepository,
) -> None:
    """The demo/seed stream has no provider configured at all, so it has no
    integrated observation runtime (Unified Observation Experience v1: an
    honest unavailable state, never scaffolded fake support). Product
    requirement 1 requires a calm, honest status here -- never a 500, never
    a silent fallback to a runtime this Stream doesn't use."""

    response = client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start")
    assert response.status_code == 200
    payload = response.json()
    assert payload["observing"] is False
    assert payload["runtime_available"] is False
    # Never expose internal Stage numbers/vendor terms in this basic contract.
    for forbidden in ("Stage 7", "AssembledVisitProposal", "ONNX", "CUDA", "candidate_visit_authority"):
        assert forbidden not in payload["message"]
        assert forbidden not in payload["camera_message"]
    # No Stage 7 authority was ever touched for a Stream with no runtime.
    assert repository.get_observation_authority_state().mode == "shadow"


def test_start_on_unpaired_camera_node_stream_reports_pairing_reason(
    client: TestClient, repository: ProductRepository,
) -> None:
    """A genuine `camera_node` Source still routes to the accepted engine
    lane and keeps its existing pairing-required message -- only a Stream
    whose provider isn't `camera_node` at all skips the engine now."""

    configure_unpaired_camera_node(client)

    response = client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start")
    assert response.status_code == 200

    # The engine's own pairing check runs on its background thread (see
    # `test_engine_runtime.py`'s identical `_wait_until` convention); poll
    # status instead of asserting on the transient initial "starting" snapshot.
    payload = response.json()
    deadline = time.monotonic() + 5.0
    while payload["state"] == "starting" and time.monotonic() < deadline:
        time.sleep(0.02)
        payload = client.get(f"/api/streams/{DEMO_STREAM_ID}/observation/status").json()

    assert payload["observing"] is False
    assert payload["runtime_available"] is True
    assert payload["state"] == "needs_attention"
    assert "Camera Node" in payload["camera_message"]
    assert repository.get_observation_authority_state().mode == "shadow"


def test_camera_node_status_advanced_diagnostics_report_runtime_kind(
    client: TestClient, repository: ProductRepository,
) -> None:
    configure_unpaired_camera_node(client)

    response = client.get(f"/api/streams/{DEMO_STREAM_ID}/observation/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["advanced"]["runtime_kind"] == "camera_node_engine"


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


# =============================================================================
# Rejected / Suppressed Detection Attribution v1 (see
# docs/rejected-detection-attribution-contract.md): the read-only ROI/
# time-window diagnostic surface.
# =============================================================================


def test_counterfactual_on_unknown_stream_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/streams/does-not-exist/observation/counterfactual",
        params={"start_offset_ms": 0, "end_offset_ms": 1000},
    )
    assert response.status_code == 404


def test_counterfactual_before_any_session_is_honest_and_side_effect_free(
    client: TestClient, repository: ProductRepository,
) -> None:
    response = client.get(
        f"/api/streams/{DEMO_STREAM_ID}/observation/counterfactual",
        params={"start_offset_ms": 0, "end_offset_ms": 1000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_detections"] == []
    assert payload["attribution"] == "insufficient_counterfactual_lineage"
    # Side-effect-free: no session was created, no authority state touched.
    assert repository.get_observation_authority_state().mode == "shadow"


def test_counterfactual_rejects_invalid_window_and_partial_roi(
    client: TestClient, repository: ProductRepository,
) -> None:
    bad_window = client.get(
        f"/api/streams/{DEMO_STREAM_ID}/observation/counterfactual",
        params={"start_offset_ms": 1000, "end_offset_ms": 0},
    )
    assert bad_window.status_code == 400

    partial_roi = client.get(
        f"/api/streams/{DEMO_STREAM_ID}/observation/counterfactual",
        params={"start_offset_ms": 0, "end_offset_ms": 1000, "roi_left": 0.1, "roi_top": 0.1},
    )
    assert partial_roi.status_code == 400
