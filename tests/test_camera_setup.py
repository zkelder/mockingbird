import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    CameraSetupCompleteRequest,
    CameraSetupValidationRequest,
    Point,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)


def _repository(tmp_path):
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'camera-setup.sqlite3'}",
        media_root=tmp_path / "media",
    )
    return repository


def _request(
    *,
    key: str,
    enable_monitoring: bool = False,
    zone_type: str = "feeder",
    camera_name: str = "Feeder camera",
) -> CameraSetupCompleteRequest:
    return CameraSetupCompleteRequest(
        camera_name=camera_name,
        stream_name="Feeder view",
        provider_key="external_url",
        config={
            "url": "https://camera.local/still.jpg",
            "auth_password": "never-return-this",
        },
        zones=[
            {
                "name": "Feeder",
                "zone_type": zone_type,
                "polygon": [
                    Point(x=0.2, y=0.2),
                    Point(x=0.8, y=0.2),
                    Point(x=0.8, y=0.8),
                    Point(x=0.2, y=0.8),
                ],
                "monitoring_policy": (
                    None
                    if zone_type in {"privacy", "ignore"}
                    else {"activity_sensitivity": "normal"}
                ),
            }
        ],
        enable_monitoring=enable_monitoring,
        idempotency_key=key,
    )


def _product_counts(repository: ProductRepository) -> tuple[int, int, int, int, int, int]:
    with repository.session_factory() as session:
        return (
            session.scalar(select(func.count(CameraSourceModel.id))) or 0,
            session.scalar(select(func.count(StreamModel.id))) or 0,
            session.scalar(select(func.count(ZoneModel.id))) or 0,
            session.scalar(select(func.count(EventModel.id))) or 0,
            session.scalar(select(func.count(VisitModel.id))) or 0,
            session.scalar(select(func.count(MediaAssetModel.id))) or 0,
        )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client(tmp_path):
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'camera-setup-api.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
            yield api_client
    finally:
        configure_repository(None)


def test_camera_setup_is_secret_safe_and_validation_creates_no_product_records(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        before = _product_counts(repository)
        validation = repository.validate_camera_setup(
            CameraSetupValidationRequest(
                provider_key="external_url",
                config={"url": "https://camera.local/still.jpg", "auth_password": "secret"},
            )
        )
        assert validation.status == "configuration_valid"
        assert validation.can_continue is True
        assert validation.preview_available is False
        assert validation.safe_config_preview["auth_password"] == "configured"
        assert "secret" not in str(validation)
        assert _product_counts(repository) == before
    finally:
        repository.close()


def test_camera_setup_completion_links_stream_zone_and_default_off_policy_idempotently(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        result = repository.complete_camera_setup(_request(key="camera-setup-key"))
        repeated = repository.complete_camera_setup(_request(key="camera-setup-key"))
        assert result.source.id == result.stream.source_id
        assert result.zones[0].stream_id == result.stream.id
        assert result.monitoring_policy.mode == "off"
        assert repeated.idempotent is True
        assert repeated.stream.id == result.stream.id
    finally:
        repository.close()


def test_camera_setup_only_arms_monitoring_when_explicitly_selected(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        result = repository.complete_camera_setup(
            _request(key="camera-setup-armed-key", enable_monitoring=True)
        )
        assert result.monitoring_policy.mode == "armed"
    finally:
        repository.close()


def _camera_node_request(*, key: str, enable_monitoring: bool) -> CameraSetupCompleteRequest:
    return CameraSetupCompleteRequest(
        camera_name="Camera Node feeder",
        stream_name="Camera Node feeder view",
        provider_key="camera_node",
        config={
            "node_base_address": "http://192.168.1.50:8787",
            "node_credential": "test-credential",
            "node_camera_id": "opaque-camera-1",
            "node_id": "opaque-node-1",
        },
        zones=[
            {
                "name": "Feeder",
                "zone_type": "feeder",
                "polygon": [
                    Point(x=0.2, y=0.2),
                    Point(x=0.8, y=0.2),
                    Point(x=0.8, y=0.8),
                    Point(x=0.2, y=0.8),
                ],
                "monitoring_policy": {"activity_sensitivity": "normal"},
            }
        ],
        enable_monitoring=enable_monitoring,
        idempotency_key=key,
    )


def test_camera_setup_rejects_enable_monitoring_for_camera_node(tmp_path) -> None:
    """CAMERA NODE LEGACY-MONITORING BACKEND GUARD v1: Add Camera's guided
    setup is the second authoritative place that can arm the legacy durable
    monitoring policy (`payload.enable_monitoring`), independent of the
    dedicated Enable-monitoring toggle. A Camera Node Stream must reject that
    combination outright rather than silently create the camera with
    monitoring off, or silently arm a competing runtime -- and a Camera Node
    Stream with monitoring left off must still complete normally."""

    repository = _repository(tmp_path)
    try:
        before = _product_counts(repository)
        with pytest.raises(ValueError, match="camera_node_legacy_monitoring_unsupported"):
            repository.complete_camera_setup(
                _camera_node_request(key="camera-node-reject", enable_monitoring=True)
            )
        assert _product_counts(repository) == before

        result = repository.complete_camera_setup(
            _camera_node_request(key="camera-node-ok", enable_monitoring=False)
        )
        assert result.monitoring_policy.mode == "off"
        assert result.stream.source_id == result.source.id
    finally:
        repository.close()


@pytest.mark.anyio
async def test_camera_setup_api_rejects_enable_monitoring_for_camera_node(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same guard through the real HTTP surface: a clear 400, not a 500, and
    no product records created.

    The route's own `_camera_node_prepared_config` normally requires a real
    Node pairing token before it ever reaches `complete_camera_setup` --
    orthogonal to this guard, so it is bypassed here to isolate the behavior
    under test (mirrors the already-prepared config shape the real pairing
    flow would hand off)."""

    monkeypatch.setattr(
        api_main,
        "_camera_node_prepared_config",
        lambda *, provider_key, config, pairing_token, verify_camera=False: config,
    )

    paths = ("/api/sources", "/api/streams", "/api/zones")
    before = {path: (await client.get(path)).json() for path in paths}

    response = await client.post(
        "/api/camera-setup/complete",
        json={
            "camera_name": "Camera Node feeder",
            "stream_name": "Camera Node feeder view",
            "provider_key": "camera_node",
            "config": {
                "node_base_address": "http://192.168.1.50:8787",
                "node_credential": "test-credential",
                "node_camera_id": "opaque-camera-1",
                "node_id": "opaque-node-1",
            },
            "zones": [
                {
                    "name": "Feeder",
                    "zone_type": "feeder",
                    "polygon": [
                        {"x": 0.2, "y": 0.2},
                        {"x": 0.8, "y": 0.2},
                        {"x": 0.8, "y": 0.8},
                        {"x": 0.2, "y": 0.8},
                    ],
                    "monitoring_policy": {"activity_sensitivity": "normal"},
                }
            ],
            "enable_monitoring": True,
            "idempotency_key": "api-camera-node-reject",
        },
    )

    assert response.status_code == 400
    assert "Observation Engine" in response.text
    after = {path: (await client.get(path)).json() for path in paths}
    assert after == before


def test_camera_setup_capabilities_and_incomplete_or_unsupported_validation_are_honest(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        options = repository.camera_setup_options()
        external_url = next(option for option in options.options if option.provider_key == "external_url")
        assert external_url.availability == "available_now"
        assert "does not contact a camera" in external_url.message

        incomplete = repository.validate_camera_setup(
            CameraSetupValidationRequest(provider_key="external_url", config={})
        )
        assert incomplete.status == "configuration_incomplete"
        assert incomplete.can_continue is False
        assert incomplete.preview_available is False

        unsupported = repository.validate_camera_setup(
            CameraSetupValidationRequest(provider_key="folder_import_future", config={})
        )
        assert unsupported.status == "unsupported_on_this_computer"
        assert unsupported.can_continue is False
        assert unsupported.preview_available is False
    finally:
        repository.close()


def test_camera_setup_privacy_and_ignore_zones_remain_suppression_only(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        privacy = repository.complete_camera_setup(
            _request(key="camera-setup-privacy-key", zone_type="privacy")
        )
        ignored = repository.complete_camera_setup(
            _request(
                key="camera-setup-ignore-key",
                zone_type="ignore",
                camera_name="Ignored camera",
            )
        )
        assert privacy.zones[0].monitoring_policy is None
        assert ignored.zones[0].monitoring_policy is None
    finally:
        repository.close()


@pytest.mark.anyio
async def test_camera_setup_api_validation_is_secret_safe_and_side_effect_free(
    client: httpx.AsyncClient,
) -> None:
    paths = ("/api/sources", "/api/streams", "/api/zones", "/api/events", "/api/visits")
    before = {path: (await client.get(path)).json() for path in paths}

    options = await client.get("/api/camera-setup/options")
    assert options.status_code == 200
    assert any(option["provider_key"] == "external_url" for option in options.json()["options"])

    validation = await client.post(
        "/api/camera-setup/validate",
        json={
            "provider_key": "external_url",
            "config": {"url": "https://camera.local/still.jpg", "auth_password": "secret"},
        },
    )
    assert validation.status_code == 200
    assert validation.json()["status"] == "configuration_valid"
    assert validation.json()["preview_available"] is False
    assert "secret" not in validation.text

    unsupported = await client.post(
        "/api/camera-setup/validate",
        json={"provider_key": "folder_import_future", "config": {}},
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["status"] == "unsupported_on_this_computer"

    rejected = await client.post(
        "/api/camera-setup/validate",
        json={"provider_key": "external_url", "config": {"unsupported": "value"}},
    )
    assert rejected.status_code == 400
    assert "unsupported settings" in rejected.text
    after = {path: (await client.get(path)).json() for path in paths}
    assert after == before
