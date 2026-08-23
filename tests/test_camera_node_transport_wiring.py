"""Tier 1/2: the Camera Node app's transport wiring -- `/queue/evidence`,
`/node/v1/transport/status`, and transport-credential mint/persist/revoke
at pairing time.

Uses the same hand-built fake-provider convention as
tests/test_camera_node.py (`ProfiledProvider`-style), driven over
`httpx.ASGITransport` -- no real sockets. See
tests/test_camera_node_transport_acceptance.py for the real end-to-end
delivery proof.
"""

from __future__ import annotations

import httpx
import pytest

from mockingbird_node.app import create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node.providers import NodeCamera, NodeCaptureProfile
from mockingbird_node.transport_credential import load_transport_credential

_JPEG = b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeProvider:
    def __init__(self) -> None:
        self.snapshot_calls = 0

    def cameras(self):
        return [NodeCamera("cam-1", "Feeder view", "available", snapshot_supported=True, provider_type="test")]

    def capture_profiles(self, camera_id):
        return [
            NodeCaptureProfile(
                profile_id="evidence-profile",
                purposes=("evidence",),
                width=1,
                height=1,
                jpeg_supported=True,
                max_expected_bytes=1_500_000,
                capture_class="warm",
                geometry_group=None,
                same_fov=True,
            )
        ]

    def capture_readiness(self, _camera_id):
        return "ready"

    def capture_profile_status(self, _camera_id):
        return []

    def snapshot(self, camera_id, *, profile_id=None):
        self.snapshot_calls += 1
        return _JPEG

    def close(self) -> None:
        pass


def _config(tmp_path, **overrides) -> CameraNodeConfig:
    defaults = dict(
        display_name="test-node",
        bind_host="127.0.0.1",
        port=8787,
        provider_key="synthetic",
        camera_identifier=None,
        max_image_bytes=1_500_000,
        max_image_width=1920,
        max_image_height=1080,
        pairing_ttl_seconds=600,
        max_preview_viewers=2,
        testing=True,
        enabled_providers=("synthetic",),
        transport_spool_dir=tmp_path / "spool",
        transport_credential_state_path=tmp_path / "transport-credential.json",
    )
    defaults.update(overrides)
    return CameraNodeConfig(**defaults)


def _client_for(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://node")


async def _pair(client: httpx.AsyncClient, app) -> dict:
    response = await client.post("/node/v1/pair", json={"pairing_code": app.state.pairing_code})
    return response.json()


@pytest.mark.anyio
async def test_queue_evidence_enqueues_into_the_spool_and_returns_202(tmp_path) -> None:
    provider = _FakeProvider()
    app = create_node_app(_config(tmp_path), provider=provider)
    async with _client_for(app) as client:
        credential = (await _pair(client, app))["credential"]
        response = await client.post(
            "/node/v1/cameras/cam-1/queue/evidence",
            json={"profile_id": "evidence-profile", "priority": 100, "reason": "manual"},
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert response.status_code == 202
        item_id = response.json()["item_id"]
        assert response.json()["status"] == "queued"

    spool = app.state.transport_spool
    item = spool.get(item_id)
    assert item is not None
    assert item.metadata["camera_id"] == "cam-1"
    assert item.metadata["profile_id"] == "evidence-profile"
    assert spool.read_payload(item_id) == _JPEG


@pytest.mark.anyio
async def test_queue_evidence_without_transport_configured_is_503(tmp_path) -> None:
    provider = _FakeProvider()
    config = _config(tmp_path, transport_spool_dir=None)  # mirrors direct CameraNodeConfig(...) construction
    app = create_node_app(config, provider=provider)
    async with _client_for(app) as client:
        credential = (await _pair(client, app))["credential"]
        response = await client.post(
            "/node/v1/cameras/cam-1/queue/evidence",
            json={"profile_id": "evidence-profile"},
            headers={"Authorization": f"Bearer {credential}"},
        )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_transport_status_reflects_spool_diagnostics(tmp_path) -> None:
    provider = _FakeProvider()
    app = create_node_app(_config(tmp_path), provider=provider)
    async with _client_for(app) as client:
        credential = (await _pair(client, app))["credential"]
        await client.post(
            "/node/v1/cameras/cam-1/queue/evidence",
            json={"profile_id": "evidence-profile"},
            headers={"Authorization": f"Bearer {credential}"},
        )
        status_response = await client.get("/node/v1/transport/status", headers={"Authorization": f"Bearer {credential}"})
    body = status_response.json()
    assert body["transport_enabled"] is False  # no host_base_address configured in this test
    assert body["pending_count"] == 1


@pytest.mark.anyio
async def test_pairing_mints_transport_credential_only_when_transport_enabled(tmp_path) -> None:
    # Disabled: no host_base_address configured.
    disabled_app = create_node_app(_config(tmp_path / "disabled"), provider=_FakeProvider())
    async with _client_for(disabled_app) as client:
        disabled_pair_body = await _pair(client, disabled_app)
    assert disabled_pair_body["transport_credential"] is None

    # Enabled: host_base_address configured.
    enabled_app = create_node_app(
        _config(tmp_path / "enabled", host_base_address="http://198.51.100.1:9000"), provider=_FakeProvider()
    )
    async with _client_for(enabled_app) as client:
        enabled_pair_body = await _pair(client, enabled_app)
    assert enabled_pair_body["transport_credential"]
    assert len(enabled_pair_body["transport_credential"]) >= 16


@pytest.mark.anyio
async def test_transport_credential_survives_a_simulated_restart(tmp_path) -> None:
    credential_path = tmp_path / "transport-credential.json"
    config = _config(tmp_path, host_base_address="http://198.51.100.1:9000", transport_credential_state_path=credential_path)
    first_app = create_node_app(config, provider=_FakeProvider())
    async with _client_for(first_app) as client:
        first_pair_body = await _pair(client, first_app)
    minted = first_pair_body["transport_credential"]
    assert minted

    persisted = load_transport_credential(credential_path, expected_node_id=_node_id_of(first_app))
    assert persisted == minted

    # A fresh app construction against the same paths simulates a process
    # restart (Phase I): the transport credential must be available without
    # re-pairing, exactly like the pairing credential's own digest already
    # is.
    restarted_app = create_node_app(config, provider=_FakeProvider())
    assert restarted_app.state.transport_credential_holder["value"] == minted


@pytest.mark.anyio
async def test_revoke_clears_the_transport_credential(tmp_path) -> None:
    credential_path = tmp_path / "transport-credential.json"
    config = _config(tmp_path, host_base_address="http://198.51.100.1:9000", transport_credential_state_path=credential_path)
    app = create_node_app(config, provider=_FakeProvider())
    async with _client_for(app) as client:
        pair_body = await _pair(client, app)
        await client.post("/node/v1/pair/revoke", headers={"Authorization": f"Bearer {pair_body['credential']}"})
    assert app.state.transport_credential_holder["value"] is None
    assert not credential_path.exists()


def _node_id_of(app) -> str:
    # `node_id` isn't directly exposed on app.state; derive it the same way
    # `create_node_app` does, from the fixed `display_name` this test suite
    # always uses.
    import hashlib

    return f"node-{hashlib.sha256(b'test-node').hexdigest()[:16]}"
