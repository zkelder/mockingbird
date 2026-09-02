"""Host <-> Camera Node Release-Compatibility Preflight v1: the real API
wiring, driven end to end over real HTTP through the real, unmodified
`POST /api/streams/{stream_id}/observation/start` route -- proves the gate
`api/main.py:start_stream_observation` inserts actually fires for a
field-acceptance credential's own session start and never fires for an
ordinary signed-in human session, mirroring `test_camera_node.py`'s own
real pairing/setup flow (`_FakeNodeRequester`-style fake wire transport,
real production pairing/setup/observation-start code underneath) and
`test_field_acceptance_authentication.py`'s own bearer-credential
provisioning flow -- never a third, parallel test methodology."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import time

import httpx
import pytest

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository, drain_background_tasks
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient

pytestmark = pytest.mark.anyio

ADMIN_BODY = {"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"}
_CAMERA_ID = "opaque-camera-1"

_OLD_NODE_HEALTH = {"node_id": "node-test", "display_name": "Test node", "api_version": "v1"}
# A sentinel, not a literal payload: `_ConfigurableRequester` recognizes this
# and computes `node_receive_time`/`node_time` live (real `datetime.now(UTC)`
# plus a tiny fixed processing delta) on every `/health` call instead of a
# fixed string -- five *real*, sequential HTTP calls through the ASGI
# transport span real (if small) wall-clock time, and a fixed timestamp
# would otherwise manufacture an artificial, ever-widening drift across the
# batch that no real current Node would ever exhibit (`RttRoundTrip`'s own
# per-sample bound is only ever as wide as that one call's own real RTT).
_CURRENT_NODE_HEALTH: dict[str, object] = {**_OLD_NODE_HEALTH, "_dynamic_rtt_fields": True}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _ConfigurableRequester:
    """Mirrors `test_camera_node.py`'s own `_FakeNodeRequester` seam --
    the same `CameraNodeClient(requester=...)` injection point, extended
    with a swappable `/health` body so one paired Stream can be probed as
    both an old and a current Node across different assertions in the same
    test, without a real re-pair."""

    def __init__(self) -> None:
        self.health_body: dict[str, object] = dict(_OLD_NODE_HEALTH)

    def request(self, *, method, url, headers, body, max_bytes, timing):
        if url.endswith("/health"):
            payload = dict(self.health_body)
            if payload.pop("_dynamic_rtt_fields", False):
                # A real Node always has some non-zero request/response gap;
                # an in-process fake called directly (no real socket) can
                # otherwise measure an RTT so close to zero that its own
                # bound degenerates to a single point, making ordinary
                # floating-point jitter across five samples look like
                # genuine clock inconsistency. This tiny, deliberate delay
                # keeps the simulated round trip realistic, matching what
                # every prior RTT-bounded-calibration test (`test_camera_
                # node.py`, `test_clock_calibration.py`) already assumes.
                time.sleep(0.002)
                now = datetime.now(UTC)
                payload["node_receive_time"] = now.isoformat()
                payload["node_time"] = (now + timedelta(milliseconds=2)).isoformat()
            return 200, {"Content-Type": "application/json"}, json.dumps(payload).encode()
        if url.endswith("/pair"):
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "node_id": "node-test", "display_name": "Test node", "api_version": "v1",
                "credential": "never-echo-node-credential",
                "cameras": [{"camera_id": _CAMERA_ID, "display_name": "Feeder view", "status": "available", "snapshot_supported": True}],
            }).encode()
        if url.endswith("/capabilities"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"recommended_snapshot_timeout_seconds": 8.0}).encode()
        if url.endswith("/cameras"):
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "items": [{"camera_id": _CAMERA_ID, "display_name": "Feeder view", "status": "available", "snapshot_supported": True, "provider_type": "v4l2"}]
            }).encode()
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


@pytest.fixture
def isolated_repository(tmp_path) -> ProductRepository:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
async def requester(isolated_repository: ProductRepository):
    fake = _ConfigurableRequester()
    api_main._camera_node_client = CameraNodeClient(requester=fake)
    yield fake
    await drain_background_tasks()
    api_main._camera_node_client = None


@pytest.fixture
async def admin_client(requester):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        bootstrap = await client.post("/api/setup/administrator", json=ADMIN_BODY)
        assert bootstrap.status_code == 201, bootstrap.text
        yield client


async def _pair_and_complete_setup(admin_client: httpx.AsyncClient) -> str:
    """The real pairing/setup flow, identical in shape to
    `test_camera_node.py::test_pairing_guided_setup_keeps_credential_masked_
    and_creates_no_truth` -- produces one genuinely paired camera_node
    Stream (base_address/credential/camera_id/evidence_profile_id all
    resolved through real product code, never hand-inserted rows)."""

    pair = await admin_client.post(
        "/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"},
    )
    assert pair.status_code == 200, pair.text
    token = pair.json()["pairing_token"]
    validation = await admin_client.post(
        "/api/camera-setup/validate",
        json={"provider_key": "camera_node", "config": {"node_camera_id": _CAMERA_ID}, "node_pairing_token": token},
    )
    assert validation.status_code == 200 and validation.json()["can_continue"] is True, validation.text
    completed = await admin_client.post(
        "/api/camera-setup/complete",
        json={
            "camera_name": "Node feeder camera",
            "stream_name": "Node feeder view",
            "provider_key": "camera_node",
            "config": {"node_camera_id": _CAMERA_ID},
            "node_pairing_token": token,
            "zones": [{"name": "Feeder", "zone_type": "feeder", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
            "enable_monitoring": False,
            "idempotency_key": "node-compat-api-test-001",
        },
    )
    assert completed.status_code == 200, completed.text
    return completed.json()["stream"]["id"]


async def _create_field_acceptance_token(admin_client: httpx.AsyncClient) -> str:
    response = await admin_client.post(
        "/api/admin/field-acceptance-credentials", json={"label": "Field Acceptance Operator", "expires_in_hours": 24},
    )
    assert response.status_code == 201, response.text
    return response.json()["token"]


async def test_field_acceptance_start_is_blocked_by_the_v8_class_old_node(
    admin_client: httpx.AsyncClient, requester: _ConfigurableRequester,
) -> None:
    stream_id = await _pair_and_complete_setup(admin_client)
    token = await _create_field_acceptance_token(admin_client)
    requester.health_body = dict(_OLD_NODE_HEALTH)  # the exact real v8 shape: no node_receive_time/node_time

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"Authorization": f"Bearer {token}"}) as client:
        response = await client.post(f"/api/streams/{stream_id}/observation/start")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["state"] == "needs_attention"
        assert body["observing"] is False
        assert "Upgrade the Camera Node" in body["message"]
        assert body["advanced"]["node_compatibility_state"] == "incompatible_missing_capability"
        # The critical fail-closed assertion: no Observation Engine session
        # was actually started for this Stream.
        status = await client.get(f"/api/streams/{stream_id}/observation/status")
        assert status.json()["observing"] is False


async def test_field_acceptance_start_proceeds_past_the_gate_for_a_current_node(
    admin_client: httpx.AsyncClient, requester: _ConfigurableRequester,
) -> None:
    stream_id = await _pair_and_complete_setup(admin_client)
    token = await _create_field_acceptance_token(admin_client)
    requester.health_body = dict(_CURRENT_NODE_HEALTH)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers={"Authorization": f"Bearer {token}"}) as client:
        response = await client.post(f"/api/streams/{stream_id}/observation/start")

    assert response.status_code == 200, response.text
    body = response.json()
    # The compatibility gate must not be what blocks this attempt -- it may
    # still legitimately report a downstream engine-level reason (e.g. no
    # detector model installed in this test environment), but never this
    # milestone's own "needs_attention" + node_compatibility_state shape.
    assert body.get("advanced", {}).get("node_compatibility_state") is None
    assert "Upgrade the Camera Node" not in body.get("message", "")


async def test_ordinary_signed_in_session_is_never_blocked_by_the_compatibility_gate(
    admin_client: httpx.AsyncClient, requester: _ConfigurableRequester,
) -> None:
    """Section 15/30: an ordinary signed-in Administrator's own Start
    observing must behave exactly as it always has, regardless of the
    Node's RTT capability -- the gate only ever engages for a
    field-acceptance credential."""

    stream_id = await _pair_and_complete_setup(admin_client)
    requester.health_body = dict(_OLD_NODE_HEALTH)

    response = await admin_client.post(f"/api/streams/{stream_id}/observation/start")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("advanced", {}).get("node_compatibility_state") is None
    assert "Upgrade the Camera Node" not in body.get("message", "")
