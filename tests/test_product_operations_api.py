"""Product Operations & First-Observation Completion v1: the new
Administrator-tier HTTP surfaces this milestone adds.

- `GET /api/product/doctor`: a thin passthrough wrapper around the existing,
  unmodified `diagnostics.doctor.run_doctor()` -- previously CLI-only.
- `GET /api/streams/{id}/camera-node-hardware-health`: a bounded, live,
  on-demand, non-persisting check of a paired Camera Node's own storage/
  hardware-quality facts, reusing the existing, unmodified
  `CameraNodeClient.health()` -- never a schema change, never a change to
  Doctor's own read-only/DB-only design.

Auth-tier correctness itself (a Viewer gets 403) is proven once, centrally,
in test_local_identity_multi_user.py, following that file's own established
one-representative-example-per-tier convention -- not re-proven per route
here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import CameraSourceCreate, SourceProviderConfigurationUpdate
from mockingbird.diagnostics.doctor import DoctorOverallStatus, run_doctor
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient, CameraNodeClientError

_BASE_ADDRESS = "http://127.0.0.1:8787"


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
def client(repository: ProductRepository) -> LegacyAuthenticatedSyncTestClient:
    return LegacyAuthenticatedSyncTestClient(app)


def _paired_camera_node_stream(
    repository: ProductRepository,
    *,
    base_address: str = _BASE_ADDRESS,
) -> str:
    """Mirrors `test_camera_node_transport_consumption.py`'s own
    `_pair_camera_node_source` exactly: a real Source/Stream with a real
    `camera_node_base_address` set directly at the repository layer (the
    same secret-config-update path the real pairing handshake itself uses
    underneath), never through the HTTP PATCH endpoint's own
    secret-masking `secret_actions` mechanism, which is orthogonal to what
    this file is testing."""

    created = repository.create_camera_source(CameraSourceCreate(name="Yard Node"))
    repository.update_source_provider_configuration(
        created.source.id,
        SourceProviderConfigurationUpdate(
            provider_key="camera_node",
            config={
                "node_base_address": base_address,
                "node_credential": "pairing-credential-value",
                "node_camera_id": "cam-1",
                "node_id": "node-abc123",
                "node_pairing_state": "paired",
            },
        ),
    )
    return created.stream.id


class _FakeRequester:
    """Mirrors `test_node_compatibility.py`'s own `_FakeRequester` seam
    exactly -- a controllable fake wire transport under the real,
    unmodified `CameraNodeClient`."""

    def __init__(self, *, health_body: dict[str, object] | None, status: int = 200) -> None:
        self.health_body = health_body
        self.status = status

    def request(self, *, method, url, headers, body, max_bytes, timing):
        if url.endswith("/health"):
            payload = self.health_body if self.health_body is not None else {}
            return self.status, {"Content-Type": "application/json"}, json.dumps(payload).encode()
        return 404, {"Content-Type": "application/json"}, b"{}"


class _RaisingClient:
    def health(self, base_address: str) -> dict[str, object]:
        raise CameraNodeClientError("node_unavailable")


# ---------------------------------------------------------------------------
# GET /api/product/doctor
# ---------------------------------------------------------------------------


def test_doctor_report_endpoint_matches_direct_run_doctor(
    client: LegacyAuthenticatedSyncTestClient,
) -> None:
    response = client.get("/api/product/doctor")
    assert response.status_code == 200
    body = response.json()

    direct = run_doctor()
    assert body["overall_status"] == direct.overall_status.value
    assert len(body["checks"]) == len(direct.checks)
    codes = {check["code"] for check in body["checks"]}
    assert codes == {check.code.value for check in direct.checks}
    # A fresh, empty-but-real database/media root is a genuinely healthy
    # install by Doctor's own contract (nothing configured yet is not a
    # problem) -- a real, meaningful assertion, not merely "200 OK".
    assert body["overall_status"] in {
        DoctorOverallStatus.HEALTHY.value,
        DoctorOverallStatus.DEGRADED.value,
    }


def test_doctor_report_endpoint_check_shape(client: LegacyAuthenticatedSyncTestClient) -> None:
    body = client.get("/api/product/doctor").json()
    for check in body["checks"]:
        assert check["status"] in {"PASS", "WARN", "FAIL", "SKIPPED"}
        assert isinstance(check["summary"], str) and check["summary"]
        assert check["component"]
        # Never a raw exception string in the always-shown fields (Doctor's
        # own privacy/security contract) -- a cheap, real regression guard
        # at the HTTP boundary too, not only inside diagnostics/doctor.py's
        # own unit tests.
        for sensitive in ("credential", "bearer", "password", "api_key", "secret", "token"):
            assert sensitive not in (check["summary"] + str(check["detail"])).lower()


# ---------------------------------------------------------------------------
# GET /api/streams/{id}/camera-node-hardware-health
# ---------------------------------------------------------------------------


def test_camera_node_hardware_health_not_applicable_for_non_camera_node_stream(
    client: LegacyAuthenticatedSyncTestClient, repository: ProductRepository,
) -> None:
    created = repository.create_camera_source(CameraSourceCreate(name="RTSP Camera"))
    repository.update_source_provider_configuration(
        created.source.id,
        SourceProviderConfigurationUpdate(
            provider_key="external_url", config={"url": "rtsp://example.invalid/stream"}
        ),
    )

    response = client.get(f"/api/streams/{created.stream.id}/camera-node-hardware-health")
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is False
    assert body["reachable"] is False
    assert body["storage"] is None
    assert body["hardware"] is None


def test_camera_node_hardware_health_reachable_parses_real_shape(
    client: LegacyAuthenticatedSyncTestClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_id = _paired_camera_node_stream(repository)
    health_body = {
        "node_id": "node-abc123",
        "api_version": "v1",
        "storage": {"total_bytes": 32_000_000_000, "free_bytes": 100_000_000, "storage_health_tier": "critical"},
        "hardware": {
            "undervoltage_active": True,
            "throttled_active": False,
            "undervoltage_occurred": True,
            "throttled_occurred": False,
            "temperature_celsius": 61.4,
        },
    }
    monkeypatch.setattr(
        "mockingbird.api.main.get_camera_node_client",
        lambda: CameraNodeClient(requester=_FakeRequester(health_body=health_body)),
    )

    response = client.get(f"/api/streams/{stream_id}/camera-node-hardware-health")
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert body["reachable"] is True
    assert body["storage"] == {
        "total_bytes": 32_000_000_000, "free_bytes": 100_000_000, "storage_health_tier": "critical",
    }
    assert body["hardware"]["undervoltage_active"] is True
    assert body["hardware"]["temperature_celsius"] == 61.4


def test_camera_node_hardware_health_handles_off_pi_node(
    client: LegacyAuthenticatedSyncTestClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real, current Node reached successfully, but off Raspberry Pi (or
    with no probe directory configured) -- `storage`/`hardware` are `None`
    exactly as the Node's own response says, never fabricated."""

    stream_id = _paired_camera_node_stream(repository)
    health_body = {"node_id": "node-abc123", "api_version": "v1", "storage": None, "hardware": None}
    monkeypatch.setattr(
        "mockingbird.api.main.get_camera_node_client",
        lambda: CameraNodeClient(requester=_FakeRequester(health_body=health_body)),
    )

    body = client.get(f"/api/streams/{stream_id}/camera-node-hardware-health").json()
    assert body["applicable"] is True
    assert body["reachable"] is True
    assert body["storage"] is None
    assert body["hardware"] is None


def test_camera_node_hardware_health_unreachable_degrades_honestly(
    client: LegacyAuthenticatedSyncTestClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream_id = _paired_camera_node_stream(repository)
    monkeypatch.setattr("mockingbird.api.main.get_camera_node_client", lambda: _RaisingClient())

    response = client.get(f"/api/streams/{stream_id}/camera-node-hardware-health")
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert body["reachable"] is False
    assert body["storage"] is None
    assert body["hardware"] is None


def test_camera_node_hardware_health_malformed_node_response_degrades_not_crashes(
    client: LegacyAuthenticatedSyncTestClient, repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A genuinely malformed/unexpected shape from the Node's own response
    (a future/older/broken Node) must never 500 the Host -- degrade the one
    affected field to `None`, never the whole response."""

    stream_id = _paired_camera_node_stream(repository)
    health_body = {
        "node_id": "node-abc123",
        "api_version": "v1",
        "storage": {"total_bytes": "not-a-number", "free_bytes": 1, "storage_health_tier": "healthy"},
        "hardware": "unexpected-string-shape",
    }
    monkeypatch.setattr(
        "mockingbird.api.main.get_camera_node_client",
        lambda: CameraNodeClient(requester=_FakeRequester(health_body=health_body)),
    )

    response = client.get(f"/api/streams/{stream_id}/camera-node-hardware-health")
    assert response.status_code == 200
    body = response.json()
    assert body["applicable"] is True
    assert body["reachable"] is True
    assert body["storage"] is None
    assert body["hardware"] is None


def test_camera_node_hardware_health_missing_stream_404s(
    client: LegacyAuthenticatedSyncTestClient,
) -> None:
    response = client.get("/api/streams/does-not-exist/camera-node-hardware-health")
    assert response.status_code == 404
