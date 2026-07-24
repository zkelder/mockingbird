import json

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.playback.camera_node_bridge import CameraNodeSnapshotProcess
from mockingbird.repository.product_repository import ProductRepository, SourceProviderConfigurationModel
from mockingbird.source_providers.camera_node import CameraNodeClient, CameraNodeClientError, normalize_camera_node_address
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine, initialize_database
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitModel,
)
from mockingbird_node.app import create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node.providers import (
    CompositeCameraProvider,
    NodeCamera,
    PiCamera2Provider,
    SyntheticCameraProvider,
    V4L2CameraProvider,
    create_camera_provider,
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _FakeNodeRequester:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    def request(self, *, method, url, headers, body, max_bytes):
        self.requests.append((method, url, headers))
        if url.endswith("/health"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"node_id": "node-test", "display_name": "Test node", "api_version": "v1"}).encode()
        if url.endswith("/pair"):
            assert body and b"pairing_code" in body
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "node_id": "node-test",
                "display_name": "Test node",
                "api_version": "v1",
                "credential": "never-echo-node-credential",
                "cameras": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True}],
            }).encode()
        if url.endswith("/pair/revoke"):
            return 204, {}, b""
        if url.endswith("/cameras"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"items": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True, "provider_type": "v4l2"}]}).encode()
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


def _repository(tmp_path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'camera-node.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _counts(repository: ProductRepository) -> tuple[int, int, int, int, int]:
    with repository.session_factory() as session:
        return tuple(
            session.scalar(select(func.count(model.id))) or 0
            for model in (CameraSourceModel, StreamModel, EventModel, VisitModel, MediaAssetModel)
        )


def test_camera_node_address_and_client_are_pinned_to_one_local_base_address() -> None:
    requester = _FakeNodeRequester()
    client = CameraNodeClient(requester=requester)
    assert normalize_camera_node_address("http://192.168.10.8:8787/") == "http://192.168.10.8:8787"
    with pytest.raises(CameraNodeClientError, match="node_address_requires_lan_ip"):
        client.health("http://camera-node.local:8787")
    with pytest.raises(CameraNodeClientError, match="node_address_not_local"):
        client.health("https://8.8.8.8")
    pairing = client.pair("http://127.0.0.1:8787", "correct-one-time-code")
    assert pairing.cameras[0].camera_id == "opaque-camera-1"
    assert "never-echo-node-credential" not in str(pairing.cameras)
    assert all(url.startswith("http://127.0.0.1:8787/node/v1/") for _, url, _ in requester.requests)
    assert all("never-echo-node-credential" not in str(headers) for _, _, headers in requester.requests)


def _node_config(*, provider_key: str = "v4l2", enabled_providers: tuple[str, ...] = ()) -> CameraNodeConfig:
    return CameraNodeConfig("Test Node", "127.0.0.1", 8787, provider_key, None, 1_500_000, 1920, 1080, 60, 2, testing=True, enabled_providers=enabled_providers)


def test_production_defaults_exclude_synthetic_and_unknown_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_NODE_PROVIDER", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_NODE_PROVIDERS", raising=False)
    config = CameraNodeConfig.from_environment()
    assert config.enabled_providers == ("v4l2", "picamera2")
    assert "synthetic" not in config.enabled_providers
    monkeypatch.setenv("MOCKINGBIRD_NODE_PROVIDERS", "v4l2,not_a_provider")
    with pytest.raises(ValueError, match="provider_invalid"):
        CameraNodeConfig.from_environment()


def test_v4l2_enumeration_is_bounded_opaque_and_capture_releases_resources() -> None:
    class Capture:
        released = False
        def isOpened(self): return True
        def set(self, *_args): return True
        def read(self): return True, object()
        def release(self): self.released = True

    class Cv2:
        CAP_PROP_FRAME_WIDTH = 1
        CAP_PROP_FRAME_HEIGHT = 2
        def __init__(self): self.capture = Capture(); self.paths = []
        def VideoCapture(self, path): self.paths.append(path); return self.capture
        def imencode(self, _suffix, _frame): return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    cv2 = Cv2()
    provider = V4L2CameraProvider(_node_config(), device_enumerator=lambda: [(index, f"/dev/video{index}") for index in range(10, -1, -1)], cv2_module=cv2)
    cameras = provider.cameras()
    assert [camera.camera_id for camera in cameras] == [f"v4l2-camera-{index}" for index in range(8)]
    assert "/dev/" not in str(cameras)
    assert provider.snapshot("v4l2-camera-0").startswith(b"\xff\xd8")
    assert cv2.capture.released is True
    assert cv2.paths == ["/dev/video0"]


def test_v4l2_busy_and_picamera2_missing_are_safe_setup_states() -> None:
    provider = V4L2CameraProvider(_node_config(), device_enumerator=lambda: [(0, "/dev/video0")], cv2_module=object())
    provider._lock.acquire()
    try:
        with pytest.raises(ValueError, match="camera_busy"):
            provider.snapshot("v4l2-camera-0")
    finally:
        provider._lock.release()
    pi = PiCamera2Provider(_node_config(provider_key="picamera2"), module=False, cv2_module=object())
    assert pi.cameras()[0].status == "setup_required"


def test_picamera2_fake_runtime_keeps_opaque_identity_and_releases_camera() -> None:
    class Camera:
        stopped = closed = False
        def create_still_configuration(self, **_kwargs): return object()
        def configure(self, _configuration): return None
        def start(self): return None
        def capture_array(self): return object()
        def stop(self): self.stopped = True
        def close(self): self.closed = True
    class Picamera2:
        camera = Camera()
        @staticmethod
        def global_camera_info(): return [{"ignored": "not exposed"}]
        def __new__(cls, _index): return cls.camera
    module = type("Module", (), {"Picamera2": Picamera2})
    class Encoder:
        def imencode(self, _suffix, _frame): return True, bytearray(b"\xff\xd8\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x11\x00\xff\xd9")

    provider = PiCamera2Provider(_node_config(provider_key="picamera2"), module=module, cv2_module=Encoder())
    assert provider.cameras()[0].camera_id == "picamera2-camera-0"
    assert provider.snapshot("picamera2-camera-0").startswith(b"\xff\xd8")
    assert Picamera2.camera.stopped and Picamera2.camera.closed


def test_composite_provider_keeps_other_camera_available_when_one_fails() -> None:
    class Failing:
        def cameras(self): return [NodeCamera("v4l2-camera-0", "Linux camera 1", "unavailable", provider_type="v4l2")]
        def snapshot(self, _camera_id): raise ValueError("camera_unavailable")
        def close(self): return None
    provider = CompositeCameraProvider([Failing(), SyntheticCameraProvider()])
    assert provider.snapshot("synthetic-camera-1").startswith(b"\xff\xd8")
    assert provider.cameras()[1].provider_type == "synthetic"


def test_node_snapshot_failure_stops_for_durable_bounded_recovery() -> None:
    class UnavailableClient:
        def snapshot(self, **_kwargs):
            raise CameraNodeClientError("authentication_rejected")

    class Configuration:
        stream_id = "node-stream"
        camera_node_base_address = "http://127.0.0.1:8787"
        camera_node_credential = "masked-local-only"
        camera_node_camera_id = "opaque-camera-1"

    process = CameraNodeSnapshotProcess(Configuration(), client=UnavailableClient())
    assert process.wait(timeout=1) == 1
    assert process.safe_failure_code == "authentication_rejected"
    assert process.stdout.read() == b""


@pytest.mark.anyio
async def test_node_requires_authentication_and_one_time_pairing_is_bounded() -> None:
    config = CameraNodeConfig(
        display_name="Synthetic Node",
        bind_host="127.0.0.1",
        port=8787,
        provider_key="synthetic",
        camera_identifier=None,
        max_image_bytes=1_500_000,
        max_image_width=1920,
        max_image_height=1080,
        pairing_ttl_seconds=60,
        max_preview_viewers=0,
        testing=True,
    )
    node = create_node_app(config, provider=SyntheticCameraProvider())
    transport = httpx.ASGITransport(app=node)
    async with httpx.AsyncClient(transport=transport, base_url="http://node") as client:
        unauthenticated = await client.get("/node/v1/cameras")
        assert unauthenticated.status_code == 401
        paired = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        assert paired.status_code == 200
        credential = paired.json()["credential"]
        assert credential not in (await client.get("/node/v1/health")).text
        repeated = await client.post("/node/v1/pair", json={"pairing_code": node.state.pairing_code})
        assert repeated.status_code == 409
        snapshot = await client.get(
            "/node/v1/cameras/synthetic-camera-1/snapshot",
            headers={"Authorization": f"Bearer {credential}"},
        )
        assert snapshot.status_code == 200
        assert snapshot.headers["content-type"].startswith("image/jpeg")
        revoked = await client.post("/node/v1/pair/revoke", headers={"Authorization": f"Bearer {credential}"})
        assert revoked.status_code == 204
        assert (await client.get("/node/v1/cameras", headers={"Authorization": f"Bearer {credential}"})).status_code == 401


@pytest.mark.anyio
async def test_pairing_guided_setup_keeps_credential_masked_and_creates_no_truth(tmp_path) -> None:
    repository = _repository(tmp_path)
    requester = _FakeNodeRequester()
    api_main._camera_node_client = CameraNodeClient(requester=requester)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            before = _counts(repository)
            pair = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"})
            assert pair.status_code == 200
            assert "never-echo-node-credential" not in pair.text
            token = pair.json()["pairing_token"]
            assert _counts(repository) == before

            preview = await client.post(
                "/api/camera-nodes/preview",
                json={"pairing_token": token, "camera_id": "opaque-camera-1"},
            )
            assert preview.status_code == 200
            assert preview.headers["content-type"].startswith("image/jpeg")
            assert preview.headers["cache-control"] == "no-store"
            assert _counts(repository) == before

            validation = await client.post("/api/camera-setup/validate", json={
                "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"},
                "node_pairing_token": token,
            })
            assert validation.status_code == 200
            assert validation.json()["can_continue"] is True
            assert "127.0.0.1" not in validation.text
            assert "never-echo-node-credential" not in validation.text
            assert _counts(repository) == before

            complete_payload = {
                "camera_name": "Node feeder camera",
                "stream_name": "Node feeder view",
                "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"},
                "node_pairing_token": token,
                "zones": [{"name": "Feeder", "zone_type": "feeder", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False,
                "idempotency_key": "camera-node-setup-001",
            }
            completed = await client.post("/api/camera-setup/complete", json=complete_payload)
            assert completed.status_code == 200
            assert completed.json()["monitoring_policy"]["mode"] == "off"
            assert "never-echo-node-credential" not in completed.text
            stream_id = completed.json()["stream"]["id"]
            playback = await client.get(f"/api/streams/{stream_id}/playback")
            assert playback.status_code == 200
            assert playback.json()["supports_live_playback"] is True
            assert "127.0.0.1" not in playback.text

            with repository.session_factory() as session:
                stored = session.scalar(select(SourceProviderConfigurationModel))
                assert stored is not None
                config = json.loads(stored.config_json)
                assert config["node_credential"] == "never-echo-node-credential"
                assert config["node_pairing_state"] == "paired"
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


@pytest.mark.anyio
async def test_disappeared_camera_cannot_complete_node_setup(tmp_path) -> None:
    class DisappearedRequester(_FakeNodeRequester):
        def request(self, **kwargs):
            if kwargs["url"].endswith("/cameras"):
                return 200, {"Content-Type": "application/json"}, b'{"items": []}'
            return super().request(**kwargs)

    repository = _repository(tmp_path)
    api_main._camera_node_client = CameraNodeClient(requester=DisappearedRequester())
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            paired = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"})
            before = _counts(repository)
            completed = await client.post("/api/camera-setup/complete", json={
                "camera_name": "Missing Node camera", "stream_name": "Missing Node view", "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"}, "node_pairing_token": paired.json()["pairing_token"],
                "zones": [{"name": "Yard", "zone_type": "yard", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False, "idempotency_key": "camera-node-disappeared-camera",
            })
            assert completed.status_code == 400
            assert _counts(repository) == before
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


@pytest.mark.anyio
async def test_node_repair_uses_in_place_preview_and_explicit_revocation(tmp_path) -> None:
    repository = _repository(tmp_path)
    api_main._camera_node_client = CameraNodeClient(requester=_FakeNodeRequester())
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            pairing = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "first-code"})
            token = pairing.json()["pairing_token"]
            created = await client.post("/api/camera-setup/complete", json={
                "camera_name": "Repairable Node camera", "stream_name": "Node view", "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"}, "node_pairing_token": token,
                "zones": [{"name": "Yard", "zone_type": "yard", "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}]}],
                "enable_monitoring": False, "idempotency_key": "camera-node-repair-setup",
            })
            assert created.status_code == 200
            stream_id = created.json()["stream"]["id"]
            source_id = created.json()["source"]["id"]
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            repair_pairing = await client.post("/api/camera-nodes/pair", json={"base_address": "http://127.0.0.1:8787", "pairing_code": "repair-code"})
            repair_token = repair_pairing.json()["pairing_token"]
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json={
                "provider_key": "camera_node", "config": {"node_camera_id": "opaque-camera-1"}, "secret_actions": {},
                "node_pairing_token": repair_token, "expected_state_token": edit.json()["state_token"],
            })
            assert preview.status_code == 200
            # Re-pairing to the same advertised Node/camera leaves the existing
            # runtime configuration intact; a changed credential would require restart.
            assert preview.json()["restart_required"] is False
            assert "127.0.0.1" not in preview.text
            applied = await client.post(f"/api/streams/{stream_id}/camera-configuration/apply", json={
                "provider_key": "camera_node", "config": {"node_camera_id": "opaque-camera-1"}, "secret_actions": {},
                "node_pairing_token": repair_token, "expected_state_token": edit.json()["state_token"],
                "preview_token": preview.json()["preview_token"], "idempotency_key": "camera-node-repair-apply", "restart_monitoring": False,
            })
            assert applied.status_code == 200
            assert applied.json()["configuration"]["source_id"] == source_id
            assert "never-echo-node-credential" not in applied.text
            revoked = await client.post("/api/camera-nodes/pair/revoke", json={"stream_id": stream_id})
            assert revoked.status_code == 204
            after = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            assert after.status_code == 200
            assert after.json()["field_states"]["node_credential"] == "not_configured"
            assert "never-echo-node-credential" not in after.text
    finally:
        configure_repository(None)
        api_main._camera_node_client = None


def test_schema_v23_adds_no_camera_node_configuration_to_existing_sources(tmp_path) -> None:
    database_path = tmp_path / "migration.sqlite3"
    engine = create_database_engine(f"sqlite:///{database_path}")
    try:
        status = initialize_database(engine)
        assert status.version == CURRENT_DATABASE_SCHEMA_VERSION == 23
        with engine.connect() as connection:
            count = connection.exec_driver_sql("SELECT COUNT(*) FROM source_provider_configurations WHERE provider_key = 'camera_node'").scalar_one()
        assert count == 0
    finally:
        engine.dispose()
