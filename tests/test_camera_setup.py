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


@pytest.mark.anyio
async def test_camera_setup_rtsps_gets_the_specific_honest_refusal_not_a_generic_invalid_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1
    ("A3/A6 honest RTSPS refusal"): before this fix, an rtsps:// URL at
    setup time was rejected with the same generic "Enter a valid URL"
    message as a typo -- never disclosing that RTSPS specifically isn't
    supported, even though the product already writes that exact honest
    explanation elsewhere (playback status, session start). Still refused
    either way -- this only fixes *why* the refusal says what it says."""

    response = await client.post(
        "/api/camera-setup/validate",
        json={
            "provider_key": "external_url",
            "config": {"live_stream_url": "rtsps://camera.local:322/stream"},
        },
    )
    assert response.status_code == 400
    assert "RTSPS" in response.text
    assert "not currently supported" in response.text
    assert "Enter a valid URL for the selected provider." not in response.text

    completion = await client.post(
        "/api/camera-setup/complete",
        json={
            "provider_key": "external_url",
            "config": {"live_stream_url": "rtsps://camera.local:322/stream"},
            "camera_name": "Backyard camera",
            "stream_name": "Backyard view",
            "zones": [
                {
                    "name": "Feeder",
                    "zone_type": "feeder",
                    "polygon": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, {"x": 0.5, "y": 0.9}],
                }
            ],
            "enable_monitoring": False,
            "idempotency_key": "rtsps-refusal-test-key",
        },
    )
    assert completion.status_code == 400
    assert "RTSPS" in completion.text

    # An ordinary rtsp:// URL (never rtsps://) must never trigger the RTSPS
    # refusal -- this fix is scheme-specific, not a broader RTSP change.
    # Live Setup Validation v1: a plain rtsp:// URL now also gets a bounded
    # live probe (see rtsp_bridge.probe_rtsp_stream) -- irrelevant to what
    # *this* test proves, so it is stubbed out to a deterministic success
    # rather than actually reaching for "camera.local" over the network.
    from mockingbird.playback.rtsp_bridge import RtspProbeResult

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.probe_rtsp_stream",
        lambda url, **kwargs: RtspProbeResult(True, "ready", None, 0.01),
    )
    plain_rtsp = await client.post(
        "/api/camera-setup/validate",
        json={
            "provider_key": "external_url",
            "config": {"live_stream_url": "rtsp://camera.local:554/stream", "live_stream_type": "rtsp"},
        },
    )
    assert plain_rtsp.status_code == 200
    assert "RTSPS" not in plain_rtsp.text


# ---------------------------------------------------------------------------
# Live Setup Validation v1 (Pre-Freeze Operability Gap Closure v1, Part B):
# manual RTSP setup must not claim a source is ready merely because its URL
# is syntactically valid. `rtsp_bridge.probe_rtsp_stream` itself is unit-
# tested directly in tests/test_rtsp_probe.py (including a real local
# ffmpeg decode and the bounded-timeout/process-cleanup contract); these
# tests prove the *wiring* through the real Camera Setup validation path.
# ---------------------------------------------------------------------------

_RTSP_CONFIG = {
    "url": "https://camera.local/still.jpg",
    "live_stream_url": "rtsp://camera.local:554/stream",
    "live_stream_type": "rtsp",
}


def _stub_probe(monkeypatch: pytest.MonkeyPatch, result) -> None:
    from mockingbird.playback.rtsp_bridge import RtspProbeResult

    if not isinstance(result, RtspProbeResult):
        ready, code = result
        result = RtspProbeResult(ready, code, None, 0.01)
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.probe_rtsp_stream",
        lambda url, **kwargs: result,
    )


@pytest.mark.anyio
async def test_rtsp_setup_validation_requires_more_than_url_syntax(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B1: a syntactically valid rtsp:// URL alone must not be enough --
    the exact same request must succeed or fail purely on the bounded live
    probe's own outcome."""

    _stub_probe(monkeypatch, (False, "camera_setup_rtsp_unreachable"))
    unreachable = await client.post(
        "/api/camera-setup/validate", json={"provider_key": "external_url", "config": _RTSP_CONFIG},
    )
    assert unreachable.status_code == 200
    body = unreachable.json()
    assert body["can_continue"] is False
    assert body["status"] == "camera_setup_rtsp_unreachable"
    assert body["message"]

    _stub_probe(monkeypatch, (True, "ready"))
    ready = await client.post(
        "/api/camera-setup/validate", json={"provider_key": "external_url", "config": _RTSP_CONFIG},
    )
    assert ready.status_code == 200
    ready_body = ready.json()
    assert ready_body["can_continue"] is True
    assert ready_body["status"] == "configuration_valid"
    assert "decoded a real frame" in ready_body["message"]


@pytest.mark.anyio
async def test_rtsp_setup_validation_reports_bounded_distinguishable_errors(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B4: every probe outcome the taxonomy defines round-trips into a
    normal (never 500), actionable response -- no HTTP-level crash, no
    generic catch-all message hiding what actually failed."""

    codes = (
        "camera_setup_rtsp_unreachable",
        "camera_setup_rtsp_authentication_failed",
        "camera_setup_rtsp_negotiation_failed",
        "camera_setup_rtsp_unsupported_codec",
        "camera_setup_rtsp_decode_failed",
        "camera_setup_rtsp_validation_timed_out",
        "camera_setup_rtsp_ffmpeg_unavailable",
    )
    seen_messages = set()
    for code in codes:
        _stub_probe(monkeypatch, (False, code))
        response = await client.post(
            "/api/camera-setup/validate", json={"provider_key": "external_url", "config": _RTSP_CONFIG},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["can_continue"] is False
        assert body["status"] == code
        assert body["message"]
        seen_messages.add(body["message"])
    # Each code gets its own distinct, specific text -- not one generic
    # catch-all string reused for every failure.
    assert len(seen_messages) == len(codes)


@pytest.mark.anyio
async def test_rtsp_setup_validation_can_be_corrected_and_retried_without_recreating_source(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B7: a failed validation must preserve the entered configuration
    sufficiently to correct and retry -- no Source/Stream exists to delete
    at any point in this sequence (`validate_camera_setup` never persists
    anything; only Complete Setup does)."""

    paths = ("/api/sources", "/api/streams")
    before = {path: (await client.get(path)).json() for path in paths}

    _stub_probe(monkeypatch, (False, "camera_setup_rtsp_unreachable"))
    first = await client.post(
        "/api/camera-setup/validate",
        json={"provider_key": "external_url", "config": {**_RTSP_CONFIG, "live_stream_url": "rtsp://typo.local/stream"}},
    )
    assert first.json()["can_continue"] is False

    # Correct the URL and retry -- no delete/recreate step in between.
    _stub_probe(monkeypatch, (True, "ready"))
    second = await client.post(
        "/api/camera-setup/validate", json={"provider_key": "external_url", "config": _RTSP_CONFIG},
    )
    assert second.json()["can_continue"] is True

    after = {path: (await client.get(path)).json() for path in paths}
    assert after == before


@pytest.mark.anyio
async def test_rtsp_setup_validation_covers_onvif_shaped_credentialed_urls(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B9 #10: an ONVIF-discovered stream URI (`embedOnvifCredentials`'
    exact `rtsp://user:pass@host/...` shape) goes through the identical
    `provider_key="external_url"`/`live_stream_type="rtsp"` validation path
    a manually-entered RTSP camera already uses -- and never leaks its
    embedded credential doing so."""

    _stub_probe(monkeypatch, (True, "ready"))
    response = await client.post(
        "/api/camera-setup/validate",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "https://camera.local/still.jpg",
                "live_stream_url": "rtsp://onvif-user:UnmistakableOnvifSecret42@camera.local:554/onvif/profile1",
                "live_stream_type": "rtsp",
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["can_continue"] is True
    assert "UnmistakableOnvifSecret42" not in response.text


@pytest.mark.anyio
async def test_rtsp_setup_validation_never_leaks_credentials_in_response_or_logs(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B6 (mandatory): drives the *real* `probe_rtsp_stream` -- real
    threading/timeout/redaction code, only the ffmpeg subprocess itself is
    faked -- with a fake ffmpeg stderr that echoes the credentialed URL
    verbatim (a real, observed ffmpeg behavior for several RTSP I/O error
    paths). An unmistakable fake password must be absent from the API
    response *and* from every structured log record this flow produces."""

    class _FakeStream:
        def __init__(self, chunks: list[bytes]) -> None:
            self._chunks = list(chunks)

        def read(self, size: int = -1) -> bytes:
            return self._chunks.pop(0) if self._chunks else b""

    class _FakeProcess:
        def __init__(self, stderr_text: bytes) -> None:
            # One junk byte (never a valid JPEG marker) so the probe's own
            # "did anything respond at all" signal fires immediately rather
            # than waiting out the real connect-timeout window -- keeps
            # this test fast while still reaching the real stderr-based
            # classifier below.
            self.stdout = _FakeStream([b"x"])
            self.stderr = _FakeStream([stderr_text])
            self.returncode: int | None = None

        def poll(self) -> int | None:
            return self.returncode

        def terminate(self) -> None:
            self.returncode = 1

        def kill(self) -> None:
            self.returncode = -9

        def wait(self, timeout: float | None = None) -> int:
            return self.returncode or 0

    unmistakable_password = "tR0ub4dor&ExtremelyUnmistakable"
    fake_stderr = (
        f"[rtsp @ 0x0] rtsp://setup-user:{unmistakable_password}@camera.local:554/stream: "
        "Server returned 404 Not Found"
    ).encode("utf-8")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.start_rtsp_mjpeg_process",
        lambda url, **kwargs: _FakeProcess(fake_stderr),
    )
    logged: list[dict] = []
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    response = await client.post(
        "/api/camera-setup/validate",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "https://camera.local/still.jpg",
                "live_stream_url": f"rtsp://setup-user:{unmistakable_password}@camera.local:554/stream",
                "live_stream_type": "rtsp",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["can_continue"] is False
    assert unmistakable_password not in response.text
    assert unmistakable_password not in body["message"]
    assert unmistakable_password not in str(body.get("safe_config_preview", {}))

    assert len(logged) == 1
    assert unmistakable_password not in str(logged[0])
