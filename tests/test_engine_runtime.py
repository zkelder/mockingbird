"""App-owned Observation Engine lifecycle (Product requirement 1):
start/stop/status contract, kill switch, Camera Node unavailable state,
Privacy/Ignore preservation, and a full hardware-free end-to-end candidate
creation using fake transport/detector -- the real Camera Node/CUDA
construction (`_load_real_provider`/`_default_transport_factory`) is
intentionally never exercised here (see docs/candidate-visit-authority
-contract.md's own real-hardware trial for that).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import threading
import time

import pytest
from PIL import Image

from mockingbird.observation import engine_runtime
from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import (
    DetectionObservation,
    EvidenceCandidate,
    FramePacket,
    ObservationResult,
    TrackUpdate,
)
from mockingbird.observation.engine_runtime import (
    ObservationEngineSessionManager,
    resolve_provider_config_path,
)
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    EvidenceBurstFrame,
    EvidenceBurstResult,
)
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
    StreamLivePlaybackConfig,
)
from mockingbird.source_providers.camera_node import (
    CameraNodeCamera,
    CameraNodeCaptureProfile,
    CameraNodeClientError,
)
from mockingbird.storage.models import MonitoringExposureIntervalModel
from mockingbird.time_utils import normalize_utc

STREAM_ID = "stream-backyard-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _camera_node_config(**overrides: object) -> StreamLivePlaybackConfig:
    values: dict[str, object] = dict(
        stream_id=STREAM_ID, source_id="source-backyard-feeder", provider_key="camera_node",
        live_stream_url=None, live_stream_type="camera_node",
        camera_node_base_address="http://192.168.1.50:8787", camera_node_credential="fixture-credential",
        camera_node_camera_id="cam-1", camera_node_id="node-1",
        camera_node_monitoring_profile_id="monitoring-profile", camera_node_evidence_profile_id="evidence-profile",
    )
    values.update(overrides)
    return StreamLivePlaybackConfig(**values)


def _non_camera_node_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID, source_id="source-backyard-feeder", provider_key="local_usb",
        live_stream_url=None, live_stream_type="local_usb",
    )


def _manager(repository: ProductRepository, **kwargs: object) -> ObservationEngineSessionManager:
    return ObservationEngineSessionManager(repository_factory=lambda: repository, **kwargs)


# --------------------------------------------------------------------------
# _default_capture_profile_alignment (Source-Resolution + Multi-Frame
# Species Evidence v1): the one bounded, session-start Camera Node metadata
# fetch that resolves whether this Stream's monitoring/evidence capture
# profiles are FOV-aligned. Never blocks/fails Observation Engine startup.
# --------------------------------------------------------------------------


def _capture_profile(
    *, profile_id: str, purposes: tuple[str, ...], width: int, height: int,
    geometry_group: str | None, same_fov: bool,
) -> CameraNodeCaptureProfile:
    return CameraNodeCaptureProfile(
        profile_id=profile_id, purposes=purposes, width=width, height=height,
        jpeg_supported=True, max_expected_bytes=16_000_000, capture_class="warm_concurrent",
        geometry_group=geometry_group, orientation="normal", mirrored=False, same_fov=same_fov,
    )


def _fake_camera_node_client(cameras: list[CameraNodeCamera]):
    class _FakeClient:
        def cameras(self, *, base_address: str, credential: str):
            return cameras

    return lambda: _FakeClient()


def test_capture_profile_alignment_missing_config_returns_none_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engine_runtime, "CameraNodeClient",
        lambda: (_ for _ in ()).throw(AssertionError("must not contact the Node")),
    )
    config = _camera_node_config(camera_node_monitoring_profile_id=None)
    assert engine_runtime._default_capture_profile_alignment(config) is None


def test_capture_profile_alignment_resolves_aligned_when_profiles_prove_shared_fov(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = CameraNodeCamera(
        camera_id="cam-1", display_name="Cam", status="available", snapshot_supported=True,
        capture_profiles=(
            _capture_profile(
                profile_id="monitoring-profile", purposes=("monitoring", "preview"),
                width=1920, height=1440, geometry_group="shared-fov", same_fov=True,
            ),
            _capture_profile(
                profile_id="evidence-profile", purposes=("evidence",),
                width=4624, height=3472, geometry_group="shared-fov", same_fov=True,
            ),
        ),
    )
    monkeypatch.setattr(engine_runtime, "CameraNodeClient", _fake_camera_node_client([camera]))
    decision = engine_runtime._default_capture_profile_alignment(_camera_node_config())
    assert decision is not None
    assert decision.status == "aligned"
    assert decision.transform is not None


def test_capture_profile_alignment_is_none_when_geometry_groups_differ(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = CameraNodeCamera(
        camera_id="cam-1", display_name="Cam", status="available", snapshot_supported=True,
        capture_profiles=(
            _capture_profile(
                profile_id="monitoring-profile", purposes=("monitoring", "preview"),
                width=1920, height=1440, geometry_group="fov-a", same_fov=True,
            ),
            _capture_profile(
                profile_id="evidence-profile", purposes=("evidence",),
                width=4624, height=3472, geometry_group="fov-b", same_fov=True,
            ),
        ),
    )
    monkeypatch.setattr(engine_runtime, "CameraNodeClient", _fake_camera_node_client([camera]))
    decision = engine_runtime._default_capture_profile_alignment(_camera_node_config())
    assert decision is not None
    assert decision.status == "full_only"


def test_capture_profile_alignment_none_when_profile_id_not_advertised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = CameraNodeCamera(
        camera_id="cam-1", display_name="Cam", status="available", snapshot_supported=True,
        capture_profiles=(
            _capture_profile(
                profile_id="some-other-profile", purposes=("monitoring",),
                width=1920, height=1440, geometry_group="fov-a", same_fov=True,
            ),
        ),
    )
    monkeypatch.setattr(engine_runtime, "CameraNodeClient", _fake_camera_node_client([camera]))
    assert engine_runtime._default_capture_profile_alignment(_camera_node_config()) is None


def test_capture_profile_alignment_none_when_camera_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(engine_runtime, "CameraNodeClient", _fake_camera_node_client([]))
    assert engine_runtime._default_capture_profile_alignment(_camera_node_config()) is None


def test_capture_profile_alignment_none_on_client_error_never_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Camera Node that is temporarily unreachable at session start must
    never block/fail Observation Engine startup -- see "Camera/provider
    failure behavior" in the milestone contract."""

    class _RaisingClient:
        def cameras(self, *, base_address: str, credential: str):
            raise CameraNodeClientError("node_unavailable")

    monkeypatch.setattr(engine_runtime, "CameraNodeClient", lambda: _RaisingClient())
    assert engine_runtime._default_capture_profile_alignment(_camera_node_config()) is None


def test_capture_profile_alignment_none_for_non_camera_node_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        engine_runtime, "CameraNodeClient",
        lambda: (_ for _ in ()).throw(AssertionError("must not contact the Node")),
    )
    assert engine_runtime._default_capture_profile_alignment(_non_camera_node_config()) is None


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=UTC) if value is not None and value.tzinfo is None else value


def _intervals(repository: ProductRepository, stream_id: str) -> list[MonitoringExposureIntervalModel]:
    with repository.session_factory() as session:
        return (
            session.query(MonitoringExposureIntervalModel)
            .filter_by(stream_id=stream_id)
            .order_by(MonitoringExposureIntervalModel.started_at, MonitoringExposureIntervalModel.id)
            .all()
        )


# --- Product contract: Camera Node unavailable / engine unconfigured -------


def test_non_camera_node_stream_reports_honest_unavailable_state(repository: ProductRepository) -> None:
    manager = _manager(repository)
    status = manager.start(STREAM_ID, _non_camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    final = manager.status(STREAM_ID)
    assert final.state == "error"
    assert final.observing is False
    assert final.camera_connected is False
    assert "Camera Node" in final.camera_message
    # No fabricated confidence: authority was never touched.
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_provider_load_failure_reports_honest_unavailable_engine(repository: ProductRepository) -> None:
    def _failing_loader(path: Path):
        raise ValueError("onnx_cuda_unavailable")

    manager = _manager(repository, provider_loader=_failing_loader)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    status = manager.status(STREAM_ID)
    assert status.state == "error"
    assert status.engine_available is False
    assert "onnx_cuda_unavailable" in status.engine_message
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_real_provider_loader_reports_honest_missing_model_end_to_end(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    """Exercises `engine_runtime._load_real_provider` itself (never faked
    here, unlike every other test in this module) against a genuinely
    missing packaged provider config -- the exact packaged-Windows-artifact
    defect this milestone fixes, proven end to end through the real
    loading path a normal install actually takes, not just its
    `FrameDrivenProviderConfiguration.load` unit underneath."""

    missing_config_path = tmp_path / "observation_runtime" / "provider-config.json"
    manager = _manager(repository)  # default provider_loader = the real _load_real_provider
    manager.start(STREAM_ID, _camera_node_config(), provider_config_path=missing_config_path)
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting", timeout=10.0)
    status = manager.status(STREAM_ID)

    assert status.state == "error"
    assert status.camera_connected is True  # never a contradictory "not connected"
    assert status.engine_available is False
    assert "model bundle" in status.engine_message.lower()
    assert "invalid_frame_driven_configuration" in status.engine_message
    assert status.advanced.get("engine_error_category") == "missing_model_or_runtime"


# --- Camera health/status correction: never contradict a paired camera -----


def test_engine_load_failure_leaves_camera_reported_ready(repository: ProductRepository) -> None:
    """Product requirement: a Camera Node whose pairing is already fully
    configured must never show a stale "not yet connected" camera fact next
    to an unrelated Observation runtime failure -- the exact packaged-
    runtime defect this contract fixes. `camera_connected`/`camera_message`
    must report the camera as configured, and the headline `message` (what
    the basic panel actually shows) must be the *engine's* honest reason,
    not a generic camera placeholder."""

    def _failing_loader(path: Path):
        raise ValueError("invalid_frame_driven_configuration")

    manager = _manager(repository, provider_loader=_failing_loader)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    status = manager.status(STREAM_ID)

    assert status.state == "error"
    assert status.camera_connected is True
    assert "not yet connected" not in status.camera_message.lower()
    assert "not connected" not in status.message.lower()
    assert status.engine_available is False
    assert "model bundle" in status.engine_message.lower()
    assert "invalid_frame_driven_configuration" in status.engine_message
    # The env var name must not appear in the basic-tier message -- a
    # normal packaged install never requires the user to know it.
    assert engine_runtime.PROVIDER_CONFIG_PATH_ENV not in status.engine_message
    # The headline message the basic panel renders is the real engine
    # failure, not a benign camera placeholder.
    assert status.message == status.engine_message


def test_unsupported_gpu_failure_reports_distinct_honest_category(repository: ProductRepository) -> None:
    """A CUDA/GPU-shaped failure code must produce different, honestly
    distinct wording from a missing-model-bundle failure -- "Observation
    runtime: ... Unsupported GPU" as its own recognizable state, per the
    Camera-vs-Observation health contract."""

    def _failing_loader(path: Path):
        raise ValueError("onnx_cuda_no_fallback")

    manager = _manager(repository, provider_loader=_failing_loader)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    status = manager.status(STREAM_ID)

    assert status.camera_connected is True
    assert status.engine_available is False
    assert "gpu" in status.engine_message.lower()
    assert status.advanced.get("engine_error_category") == "unsupported_gpu"


def test_missing_model_bundle_and_unsupported_gpu_are_distinct_categories(
    repository: ProductRepository,
) -> None:
    def _missing_model(path: Path):
        raise ValueError("invalid_model_bundle_path")

    def _bad_gpu(path: Path):
        raise ValueError("onnx_cuda_unavailable")

    manager = _manager(repository, provider_loader=_missing_model)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    missing_model_status = manager.status(STREAM_ID)

    manager = _manager(repository, provider_loader=_bad_gpu)
    manager.start("stream-2", _camera_node_config(stream_id="stream-2"))
    assert _wait_until(lambda: manager.status("stream-2").state != "starting")
    bad_gpu_status = manager.status("stream-2")

    assert missing_model_status.advanced.get("engine_error_category") == "missing_model_or_runtime"
    assert bad_gpu_status.advanced.get("engine_error_category") == "unsupported_gpu"
    assert missing_model_status.engine_message != bad_gpu_status.engine_message


def test_model_load_failure_is_logged_alongside_the_existing_status_fields(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("B4
    structured logging" -- model invocation failure): additive only -- the
    basic message/advanced-dict behavior test_missing_model_bundle_and_
    unsupported_gpu_are_distinct_categories above already covers is
    unchanged; this proves the new log line fires alongside it."""

    logged: list[dict] = []
    monkeypatch.setattr(
        engine_runtime,
        "log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    def _missing_model(path: Path):
        raise ValueError("invalid_model_bundle_path")

    manager = _manager(repository, provider_loader=_missing_model)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")

    assert len(logged) == 1
    assert logged[0]["component"] == "model_runtime"
    assert logged[0]["event"] == "observation_engine_load_failed"
    assert logged[0]["code"] == "invalid_model_bundle_path"
    assert logged[0]["stream_id"] == STREAM_ID
    assert logged[0]["category"] == "missing_model_or_runtime"


def test_session_start_and_stop_are_each_logged_once(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("B4
    structured logging" -- Observation Engine session start/stop)."""

    logged: list[dict] = []
    monkeypatch.setattr(
        engine_runtime,
        "log_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    manager = _manager(repository, provider_loader=lambda path: _fixture_provider())
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    manager.stop(STREAM_ID)

    session_events = [entry for entry in logged if entry["component"] == "observation_engine"]
    assert session_events == [
        {"component": "observation_engine", "event": "session_start", "stream_id": STREAM_ID},
        {"component": "observation_engine", "event": "session_stop", "stream_id": STREAM_ID},
    ]


def test_pairing_incomplete_still_reports_camera_as_the_problem(repository: ProductRepository) -> None:
    """The other side of the same fix: when pairing itself is genuinely
    incomplete, the headline message must be the specific camera reason,
    never a generic engine placeholder (a pre-existing latent mismatch in
    the same ternary this contract corrects)."""

    manager = _manager(repository)
    manager.start(STREAM_ID, _non_camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    status = manager.status(STREAM_ID)

    assert status.camera_connected is False
    assert status.message == status.camera_message
    assert "Camera Node" in status.message


def test_engine_load_duration_is_measured_and_status_never_reloads(repository: ProductRepository) -> None:
    """Performance requirement: Observation Start latency/model-init time is
    measured and surfaced (advanced diagnostics), and repeated status polls
    never re-invoke the provider loader (no repeated model loading)."""

    load_calls: list[Path] = []

    def _counting_loader(path: Path):
        load_calls.append(path)
        raise ValueError("onnx_cuda_unavailable")

    manager = _manager(repository, provider_loader=_counting_loader)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")

    for _ in range(5):
        status = manager.status(STREAM_ID)

    assert len(load_calls) == 1
    duration = status.advanced.get("engine_load_duration_ms")
    assert isinstance(duration, (int, float))
    assert duration >= 0


def _table_counts(repository: ProductRepository) -> dict[str, int]:
    from sqlalchemy import func, select

    from mockingbird.repository.product_repository import (
        EventModel,
        MediaAssetModel,
        ObservationAuthoritySettingsModel,
        ObservationCandidateVisitModel,
        ReviewLabelModel,
        VisitModel,
    )

    with repository.session_factory() as session:
        return {
            "visits": session.scalar(select(func.count(VisitModel.id))),
            "events": session.scalar(select(func.count(EventModel.id))),
            "media_assets": session.scalar(select(func.count(MediaAssetModel.id))),
            "review_labels": session.scalar(select(func.count(ReviewLabelModel.id))),
            "candidate_ledger": session.scalar(select(func.count(ObservationCandidateVisitModel.proposal_id))),
            "authority_settings": session.scalar(select(func.count(ObservationAuthoritySettingsModel.stream_id))),
        }


def test_unavailable_camera_node_makes_no_unexpected_product_writes(repository: ProductRepository) -> None:
    before = _table_counts(repository)
    manager = _manager(repository)
    manager.start(STREAM_ID, _non_camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    assert _table_counts(repository) == before


def test_provider_load_failure_makes_no_unexpected_product_writes(repository: ProductRepository) -> None:
    before = _table_counts(repository)

    def _failing_loader(path: Path):
        raise ValueError("onnx_cuda_unavailable")

    manager = _manager(repository, provider_loader=_failing_loader)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state != "starting")
    assert _table_counts(repository) == before


# --- Packaged-runtime configuration resolution (no env var required) -------


def test_resolve_provider_config_path_falls_back_to_workspace_relative_dev_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no packaged install and no env override, a development checkout
    still resolves the historical `data/models/...` convention -- but
    anchored to the discovered workspace root, never to `os.getcwd()`, so it
    keeps working regardless of which directory the process was started
    from (the exact defect that produced `invalid_frame_driven_configuration`
    on the packaged Windows artifact)."""

    monkeypatch.delenv(engine_runtime.PROVIDER_CONFIG_PATH_ENV, raising=False)
    monkeypatch.setattr(engine_runtime, "packaged_observation_runtime_root", lambda: Path("/no/such/packaged/root"))
    resolved = resolve_provider_config_path()
    assert resolved.is_absolute()
    assert resolved == Path(__file__).resolve().parents[1] / engine_runtime.DEFAULT_PROVIDER_CONFIG_PATH


def test_resolve_provider_config_path_prefers_packaged_root_over_dev_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A normal packaged install resolves its default provider config
    without any environment variable -- the packaged production
    configuration wins over the development-checkout fallback."""

    monkeypatch.delenv(engine_runtime.PROVIDER_CONFIG_PATH_ENV, raising=False)
    packaged_root = tmp_path / "observation_runtime"
    packaged_root.mkdir()
    packaged_config = packaged_root / engine_runtime.PACKAGED_PROVIDER_CONFIG_FILENAME
    packaged_config.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(engine_runtime, "packaged_observation_runtime_root", lambda: packaged_root)

    assert resolve_provider_config_path() == packaged_config


def test_resolve_provider_config_path_independent_of_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Restarting MockingBird from another working directory (exactly what
    `runtime.py`'s `run_preflight` does by `os.chdir`-ing to the runtime
    home before the API ever loads) must not change which provider config
    resolves."""

    monkeypatch.delenv(engine_runtime.PROVIDER_CONFIG_PATH_ENV, raising=False)
    packaged_root = tmp_path / "observation_runtime"
    packaged_root.mkdir()
    (packaged_root / engine_runtime.PACKAGED_PROVIDER_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(engine_runtime, "packaged_observation_runtime_root", lambda: packaged_root)

    elsewhere = tmp_path / "some" / "other" / "working" / "directory"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    assert resolve_provider_config_path() == packaged_root / engine_runtime.PACKAGED_PROVIDER_CONFIG_FILENAME


def test_resolve_provider_config_path_env_and_explicit_override_still_win(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The advanced/developer environment override, and an explicit
    caller-supplied override, both still work -- they are just never
    required for a normal packaged install."""

    packaged_root = tmp_path / "observation_runtime"
    packaged_root.mkdir()
    (packaged_root / engine_runtime.PACKAGED_PROVIDER_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(engine_runtime, "packaged_observation_runtime_root", lambda: packaged_root)

    monkeypatch.setenv(engine_runtime.PROVIDER_CONFIG_PATH_ENV, "/tmp/custom-provider-config.json")
    assert resolve_provider_config_path() == Path("/tmp/custom-provider-config.json")
    assert resolve_provider_config_path(Path("/explicit.json")) == Path("/explicit.json")


# --- Lifecycle API contract --------------------------------------------------


def test_status_before_start_is_none_and_side_effect_free(repository: ProductRepository) -> None:
    manager = _manager(repository)
    assert manager.status(STREAM_ID) is None
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_stop_before_start_is_a_no_op(repository: ProductRepository) -> None:
    manager = _manager(repository)
    assert manager.stop(STREAM_ID) is None


def test_start_is_idempotent_while_active(repository: ProductRepository) -> None:
    def _never_ready_loader(path: Path):
        time.sleep(1.0)
        raise ValueError("still_loading")

    manager = _manager(repository, provider_loader=_never_ready_loader)
    first = manager.start(STREAM_ID, _camera_node_config())
    second = manager.start(STREAM_ID, _camera_node_config())
    assert first.state == "starting"
    assert second.state == "starting"
    manager.stop(STREAM_ID)


def test_stop_is_the_kill_switch(repository: ProductRepository) -> None:
    """Even mid-startup, Stop must always return authority to shadow."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)

    def _slow_loader(path: Path):
        time.sleep(0.3)
        raise ValueError("fixture_stop_race")

    manager = _manager(repository, provider_loader=_slow_loader)
    manager.start(STREAM_ID, _camera_node_config())
    status = manager.stop(STREAM_ID)
    assert status is not None
    assert status.state == "stopped"
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


# --- Fake end-to-end: real assembler/quality-gate/repository wiring --------


HIGH_RESOLUTION_BURST_SIZE = (1920, 1080)  # realistic evidence-burst dimensions; a
# tiny fixture image (for example 64x48) makes the fixture subject's own real
# pixel area fall under the evidence scorer's existing, unmodified
# `subject_too_small` floor, which is correct scorer behavior, not a bug.


def _jpeg_bytes(size: tuple[int, int] = HIGH_RESOLUTION_BURST_SIZE) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color="green").save(buffer, format="JPEG")
    return buffer.getvalue()


def _envelope(
    sequence: int,
    *,
    generation: str = "generation-a",
    payload: bytes = b"\xff\xd8analysis\xff\xd9",
) -> AnalysisFrameEnvelope:
    captured = NOW + timedelta(milliseconds=sequence * 200)
    digest = sha256(payload).hexdigest()
    return AnalysisFrameEnvelope(
        stream_id=STREAM_ID, node_session_id="node-session-a", sequence=sequence,
        frame_id=f"{generation}:{sequence}:{digest[:12]}", captured_at=captured,
        source_monotonic_ns=sequence * 200_000_000, width=640, height=480, content_type="image/jpeg",
        provider_generation=generation, payload=payload, content_hash=digest,
        timing_facts=(("timestamp_precision", "microsecond"),),
    )


class _ConfirmingDetector:
    """Unconditionally confirms one animal near the frame center."""

    provider_id = "fixture-detector"

    def __init__(self, *, bounding_box: tuple[float, float, float, float] = (0.4, 0.4, 0.6, 0.6)) -> None:
        self._bounding_box = bounding_box

    def probe(self):
        return {"cuda_available": True, "model_bundle_compatible": True}

    def load(self):
        pass

    async def infer_frame(self, frame: FramePacket):
        return (
            DetectionObservation(
                "fixture-detector", "animal", 0.95, frame.captured_at, frame_id=frame.frame_id,
                bounding_box=self._bounding_box, is_animal=True,
            ),
        )

    def finalize_replay(self):
        pass

    def close(self):
        pass

    def report_metadata(self):
        return {"model": {"key": "fixture"}}

    def execution_facts(self):
        return {}


def _fixture_provider() -> tuple[FrameDrivenObservationProvider, _ConfirmingDetector]:
    settings = FrameDrivenSettings(
        source_nominal_fps=5, baseline_detector_fps=5, candidate_detector_fps=5,
        strong_detection_threshold=0.8, minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1, maximum_missed_frames=2, maximum_frame_gap_ms=2000,
        tracker_expiry_ms=2000, maximum_track_duration_ms=30000, maximum_active_tracks=4,
        evidence_ring_size=4, pretrigger_frame_count=1,
    )
    detector = _ConfirmingDetector()
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=settings, tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    return provider, detector


class _TeardownFailingDetector(_ConfirmingDetector):
    """Camera Node Connectivity & Recovery Diagnosis v1: mirrors the real
    `OnnxCudaObservationProvider.finalize_replay`'s ability to raise during
    teardown (see `_verify_cuda_execution`'s own direct unit coverage in
    `test_observation_onnx_cuda.py`). `_ConfirmingDetector.finalize_replay`
    is a no-op -- exactly why no existing reconnect/retry test in this
    module could ever have caught the real defect this proves: a teardown
    exception used to skip the finalize assembly tick and `provider.close()`
    (never called here -- `close_calls` stays 0) and could clobber an
    already-diagnosed `camera_message`."""

    def __init__(self, *, error: Exception, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._error = error
        self.finalize_replay_calls = 0
        self.close_calls = 0

    def finalize_replay(self) -> None:
        self.finalize_replay_calls += 1
        raise self._error

    def close(self) -> None:
        self.close_calls += 1


def _teardown_failing_provider(
    *, error: Exception,
) -> tuple[FrameDrivenObservationProvider, _TeardownFailingDetector]:
    settings = FrameDrivenSettings(
        source_nominal_fps=5, baseline_detector_fps=5, candidate_detector_fps=5,
        strong_detection_threshold=0.8, minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1, maximum_missed_frames=2, maximum_frame_gap_ms=2000,
        tracker_expiry_ms=2000, maximum_track_duration_ms=30000, maximum_active_tracks=4,
        evidence_ring_size=4, pretrigger_frame_count=1,
    )
    detector = _TeardownFailingDetector(error=error)
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=settings, tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    return provider, detector


class _FixtureTransport:
    """Yields one real bounded batch of frames once, then ends the session
    deliberately and terminally -- a real live-camera analysis-stream never
    has a legitimate "no more frames, ever" signal of its own (see
    `engine_runtime.AnalysisStreamRetryPolicy`'s own docstring: every batch
    is already a fresh bounded connection, and the fixed engine now
    correctly treats an *empty* batch as recoverable and retries it rather
    than stopping -- see `_RenewingTransport` below for that shape
    specifically). This fixture's own scripted frames are a deliberately
    bounded, finite script, so once they are served it raises the one
    unambiguous terminal condition (`authentication_rejected`) instead, the
    same deterministic, near-instant "the session loop exits on its own"
    convergence every test in this module already depends on."""

    def __init__(self, frame_count: int = 4) -> None:
        self._frames = [_envelope(index) for index in range(1, frame_count + 1)]
        self._served = False
        self.burst_requests: list[object] = []
        self.closed = False
        self.payload = _jpeg_bytes()

    def iter_analysis_frames(self, *, maximum_frames: int):
        if self._served:
            raise CameraNodeClientError("authentication_rejected")
        self._served = True
        return self._paced_frames()

    def _paced_frames(self):
        # A real transport paces frames over real network time; yielding
        # instantly would let the receiver thread dump every frame into the
        # bounded source queue before the asyncio consumer loop ever wakes,
        # so `pop_latest()`'s "keep only the newest" policy would coalesce
        # away most of them -- exactly the real-world behavior the source
        # queue is deliberately designed for, but not what this fixture
        # needs to prove a multi-frame track actually gets tracked/confirmed.
        for envelope in self._frames:
            time.sleep(0.06)
            yield envelope

    def request_evidence_burst(self, request):
        self.burst_requests.append(request)
        width, height = HIGH_RESOLUTION_BURST_SIZE
        frame = EvidenceBurstFrame(
            1, request.trigger_captured_at + timedelta(milliseconds=5), width, height, "image/jpeg",
            sha256(self.payload).hexdigest(), self.payload, request.trigger_frame_id, "generation-a", 5, "supported",
        )
        return EvidenceBurstResult(request.request_id, "captured", (frame,))

    def close(self) -> None:
        self.closed = True


class _NoBurstTransport(_FixtureTransport):
    """Same real frame sequence, but every evidence-burst request fails --
    proving the quality gate's own suppression path, not a transport bug."""

    def request_evidence_burst(self, request):
        self.burst_requests.append(request)
        return EvidenceBurstResult(request.request_id, "failed", failure_code="fixture_no_burst")


def test_end_to_end_creates_one_candidate_and_activates_authority(repository: ProductRepository) -> None:
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    assert status.counts.candidates_created == 1
    assert status.last_candidate_visit_id is not None

    with repository.session_factory() as session:
        from mockingbird.repository.product_repository import VisitModel

        visit = session.get(VisitModel, status.last_candidate_visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"
        assert visit.reviewed_label is None  # no automatic reviewed truth

    # Stop already fired naturally on stream end; authority is back to shadow.
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_acceptance_recording_is_off_by_default_and_never_touches_admission(
    repository: ProductRepository,
) -> None:
    """No `acceptance_recording_root` supplied -- the manager's own default
    -- must behave byte-for-byte like every other test in this module: no
    new directory, no new behavior, zero coupling to normal product Start."""

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)
    assert manager.status(STREAM_ID).counts.candidates_created == 1


def test_acceptance_recording_captures_frames_independent_of_admission_outcome(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    """Independent biological-encounter denominator (see docs/independent-
    encounter-denominator-design.md): when explicitly configured, every real
    Start records a bounded, timestamped sample of the exact already-decoded
    analysis frames this session itself used for inference -- proving the
    tee is wired into the real product Start path, not just the standalone
    module under test in test_acceptance_recorder.py."""

    recording_root = tmp_path / "acceptance-recordings"
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
        acceptance_recording_root=recording_root,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    session_dirs = list((recording_root / STREAM_ID).iterdir())
    assert len(session_dirs) == 1
    saved = list(session_dirs[0].glob("*.jpg"))
    assert len(saved) >= 1  # the fixture's own real 4-frame batch was sampled
    assert (session_dirs[0] / "manifest.jsonl").is_file()

    # Never becomes evidence: still exactly one candidate Visit, and the
    # candidate count is unaffected by whether recording is on.
    assert manager.status(STREAM_ID).counts.candidates_created == 1


def test_acceptance_recorder_config_factory_is_used_for_real_starts(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    """End-to-End Bird Encounter Recall Closure v1: an explicit
    `acceptance_recorder_config_factory` (in the real product, `main.py`
    wiring `acceptance_recorder.acceptance_recorder_config_from_env`) must
    actually decide the recorder's bounds for a real Start -- proving the
    injection point works, not just that `acceptance_recorder_config_
    from_env` itself parses env vars correctly (covered separately in
    test_acceptance_recorder.py)."""

    recording_root = tmp_path / "acceptance-recordings"
    seen_output_dirs: list[Path] = []

    def _tiny_bound_factory(output_dir: Path) -> engine_runtime.AcceptanceRecorderConfig:
        seen_output_dirs.append(output_dir)
        # A deliberately tiny, easy-to-observe override -- proves this
        # factory's own return value, not the module's built-in default,
        # is what the manager actually constructs the recorder from.
        return engine_runtime.AcceptanceRecorderConfig(output_dir=output_dir, max_frames=1)

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
        acceptance_recording_root=recording_root,
        acceptance_recorder_config_factory=_tiny_bound_factory,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    assert len(seen_output_dirs) == 1  # called exactly once, for this one real Start
    session_dirs = list((recording_root / STREAM_ID).iterdir())
    assert seen_output_dirs[0] == session_dirs[0]
    saved = list(session_dirs[0].glob("*.jpg"))
    assert len(saved) == 1  # the injected max_frames=1 bound actually took effect


# --- Visit Authority Budget + Ambiguous-Boundary Recall Closure v1 ---------
# (see docs/candidate-visit-authority-contract.md "Fresh-session activation"
# and "Session/Stream scope"). Real, demonstrated 2026-08-19 field defect,
# reproduced end to end through the actual product Start path.


def test_start_after_ungraceful_process_end_gets_a_fresh_budget(repository: ProductRepository) -> None:
    """The exact real defect: a prior process that never reached `stop()`'s
    kill switch (crash, `kill -9`, a mid-session redeploy) leaves this
    Stream's own authority row stuck at `candidate_visit` with a stale,
    possibly-already-exhausted activation boundary. A brand-new
    `_EngineSession` (this test's own `manager.start(...)` call -- a fresh
    Python object/manager, simulating a fresh process) must still get a
    genuinely fresh budget for this Stream."""

    stale_boundary = NOW - timedelta(days=1)
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=stale_boundary,
    )
    # Simulate the stale session having already exhausted its own budget
    # (mirrors the real 2026-08-19 field finding: 88 pre-existing Visits
    # against a default-50 budget).
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit,
        stream_id=STREAM_ID,
        now=stale_boundary,
        max_candidates_per_session=1,
    )
    exhausting = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=CandidateVisitProposalFacts(
                proposal_id="visit-episode:stale-session-exhaust",
                stream_id=STREAM_ID,
                zone_id=None,
                broad_class="animal",
                start_offset_ms=0,
                end_offset_ms=1000,
                constituent_generation_ids=("gen-stale",),
                constituent_track_ids=("track-stale",),
                source_capture_frame_ids=(),
                supporting_frame_ids=("frame-stale-1",),
                evidence_candidate_ids=(),
                limitation_facts=(),
                ambiguous_adjacent_proposal_ids=(),
                assembler_version="tracklet-visit-assembler-v1",
            ),
            observed_at=stale_boundary,
            evidence_items=(
                CandidateEvidenceItem(
                    engine_media_id="shadow-burst:stale",
                    role="identification",
                    content=_jpeg_bytes(),
                    content_type="image/jpeg",
                    width=1920,
                    height=1080,
                    captured_at=stale_boundary,
                    subject_geometry=(0.4, 0.4, 0.6, 0.6),
                ),
            ),
        )
    )
    assert exhausting.outcome == "created"
    # The process "crashes" here -- never calls .stop(), so mode is left at
    # candidate_visit with a stale, already-exhausted boundary, exactly like
    # the real field defect.

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    # The genuinely new session must have been able to create its own
    # candidate -- never silently blocked by the stale, already-exhausted
    # budget from the "crashed" prior process. (The session already ended
    # naturally here, so its own kill switch has already cleared
    # `activation_boundary_at` back to `None` -- the same honest fact
    # `test_end_to_end_creates_one_candidate_and_activates_authority` above
    # already asserts; a fresh, non-poisoned budget is proven by the two
    # facts below, not by inspecting the now-cleared boundary itself.)
    assert status.counts.candidates_created == 1
    assert "blocked_session_limit" not in dict(status.counts.suppressed_reasons)


def test_multi_stream_stop_does_not_kill_a_different_streams_authority(
    repository: ProductRepository,
) -> None:
    """A real, demonstrated cross-Stream hazard of the old global-singleton
    design: Stream B's Stop must never silently revert Stream A's own,
    independently-still-running authority to shadow."""

    other_stream_id = "stream-second-camera"
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    manager.start(other_stream_id, _camera_node_config(stream_id=other_stream_id))
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
    assert _wait_until(lambda: manager.status(other_stream_id).state == "observing", timeout=10.0)

    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "candidate_visit"
    assert repository.get_observation_authority_state(stream_id=other_stream_id).mode == "candidate_visit"

    manager.stop(other_stream_id)
    assert manager.status(other_stream_id).state == "stopped"

    # Stream A's own authority must be completely unaffected by Stream B's
    # Stop -- and its session must still be genuinely running.
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "candidate_visit"
    assert repository.get_observation_authority_state(stream_id=other_stream_id).mode == "shadow"
    assert manager.status(STREAM_ID).state == "observing"

    manager.stop(STREAM_ID)
    assert manager.status(STREAM_ID).state == "stopped"


def test_candidate_authority_exhausted_flag_is_truthful_and_sticky(
    repository: ProductRepository,
) -> None:
    """Health/diagnostic truth for budget exhaustion: a session that is
    still genuinely `observing` but has exhausted its own in-session budget
    must say so plainly, and the fact must stay true for the rest of this
    session (see "Health/diagnostic truth for budget exhaustion" in
    docs/candidate-visit-authority-contract.md)."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, max_candidates_per_session=1,
        fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    # Two well-separated, independently-confirmable encounters -- the
    # second must be legitimately blocked by the (now-exhausted) budget,
    # never by ambiguity/continuation timing.
    first_updates = list(_tick_track_updates("gen-first", 0, 1_000))
    second_updates = list(_tick_track_updates("gen-second", 100_000, 101_000))
    evidence_first, bytes_first = _tick_evidence("gen-first", "identification", "hash-first")
    evidence_second, bytes_second = _tick_evidence("gen-second", "identification", "hash-second")
    burst_bytes_cache = {
        evidence_first.media_asset_id: bytes_first, evidence_second.media_asset_id: bytes_second,
    }
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=first_updates, all_evidence_candidates=[evidence_first],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert session._candidate_authority_exhausted is False
    assert session.snapshot().candidate_authority_exhausted is False

    session._run_assembly_tick(
        all_track_updates=first_updates + second_updates,
        all_evidence_candidates=[evidence_first, evidence_second],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        finalize=True,
    )
    assert session._suppressed.get("blocked_session_limit") == 1
    assert session._candidate_authority_exhausted is True
    assert session._candidate_authority_message is not None

    snapshot = session.snapshot()
    assert snapshot.candidate_authority_exhausted is True
    assert snapshot.candidate_authority_message is not None
    # Still genuinely observing-shaped facts -- exhaustion is reported
    # alongside them, never by falsely degrading `engine_available`/camera
    # health, which stay reserved for actual camera/engine problems.
    assert snapshot.counts.candidates_created == 1


class _RecordingAutomaticIdentificationAssist:
    """A bounded double for `AutomaticReviewIdentificationAssist`: records
    every `.schedule()` call without running any real BioCLIP inference.
    The real assist class already has its own dedicated test coverage
    (tests/test_automatic_review_identification.py); this only proves the
    engine-session integration boundary -- correct visit_id, correct
    repository type, and (see the failure test below) that a raising assist
    can never take down candidate admission."""

    def __init__(self, *, raises: bool = False) -> None:
        self.raises = raises
        self.calls: list[tuple[object, str]] = []

    def schedule(self, repository: object, *, visit_id: str, on_update: object) -> bool:
        self.calls.append((repository, visit_id))
        if self.raises:
            raise RuntimeError("fixture_automatic_identification_failure")
        return True


def test_end_to_end_schedules_automatic_identification_for_the_created_visit(
    repository: ProductRepository,
) -> None:
    """Automatic Species Suggestion v1: a durably-created candidate Visit is
    handed to the bounded automatic identification assist, non-blocking and
    without altering ordinary candidate creation."""

    assist = _RecordingAutomaticIdentificationAssist()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
        automatic_identification_assist=assist,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    assert status.counts.candidates_created == 1
    assert assist.calls == [(repository, status.last_candidate_visit_id)]


def test_end_to_end_survives_automatic_identification_assist_raising(
    repository: ProductRepository,
) -> None:
    """A species-model problem must never take down candidate admission or
    this Stream's own tick loop (species inference MUST NOT block Visit
    creation)."""

    assist = _RecordingAutomaticIdentificationAssist(raises=True)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
        automatic_identification_assist=assist,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    assert status.state == "stopped"
    assert status.counts.candidates_created == 1
    assert status.last_candidate_visit_id is not None
    assert len(assist.calls) == 1

    with repository.session_factory() as session:
        from mockingbird.repository.product_repository import VisitModel

        visit = session.get(VisitModel, status.last_candidate_visit_id)
        assert visit is not None
        assert visit.review_status == "needs_review"


def test_end_to_end_suppresses_insufficient_evidence_without_creating_a_visit(
    repository: ProductRepository,
) -> None:
    """A confirmed track with no retrievable burst evidence must never
    become a Review Queue candidate (Product requirement 2/8): "nothing
    surfaced" over "please review this meaningless dark patch.\""""

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _NoBurstTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    assert status.counts.candidates_created == 0
    assert status.last_candidate_visit_id is None

    # The fixture repository seeds two demo Visits by default; only observation
    # -engine candidates matter here, so count by the Stage 7 event type
    # rather than an absolute total.
    with repository.session_factory() as session:
        from sqlalchemy import func, select

        from mockingbird.repository.product_repository import EventModel

        candidate_events = session.scalar(
            select(func.count(EventModel.id)).where(
                EventModel.event_type == "observation_engine_candidate"
            )
        )
        assert candidate_events == 0


def test_privacy_zone_excluded_subject_never_becomes_a_candidate(repository: ProductRepository) -> None:
    """The excluded region covers the fixture's whole detection box: the
    frame-driven tracker must discard it before a track ever forms (Product
    requirement 10: Privacy/Ignore behavior preserved)."""

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
    )
    manager.start(
        STREAM_ID, _camera_node_config(), privacy_ignore_regions=((0.0, 0.0, 1.0, 1.0),),
    )
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    assert status.counts.candidates_created == 0
    assert status.counts.proposals_observed == 0


def test_stop_all_stops_every_running_session(repository: ProductRepository) -> None:
    def _never_ready_loader(path: Path):
        time.sleep(2.0)
        raise ValueError("fixture_never_ready")

    manager = _manager(repository, provider_loader=_never_ready_loader)
    manager.start("stream-a", _camera_node_config(stream_id="stream-a"))
    manager.start("stream-b", _camera_node_config(stream_id="stream-b"))
    manager.stop_all()
    assert manager.status("stream-a").state == "stopped"
    assert manager.status("stream-b").state == "stopped"


class _SlowIndefiniteTransport(_FixtureTransport):
    """Keeps offering frames across many calls, well past a normal test's
    patience -- proves Stop is bounded even while genuinely `observing`, not
    only while `starting`/idle. Each `iter_analysis_frames` call still
    honestly respects its own `maximum_frames` bound and returns, exactly
    like the real bounded-per-connection transport contract
    (`CameraNodeHttpTransport.iter_analysis_frames`) -- an unbounded
    generator here would be an unrealistic fixture, not a real product gap:
    `session.run()` only ever awaits one such bounded call at a time."""

    def __init__(self) -> None:
        super().__init__(frame_count=0)
        self._sequence = 0

    def iter_analysis_frames(self, *, maximum_frames: int):
        return self._paced_frames(maximum_frames)

    def _paced_frames(self, maximum_frames: int):
        for _ in range(maximum_frames):
            self._sequence += 1
            time.sleep(0.05)
            yield _envelope(self._sequence)


def test_stop_is_bounded_while_actively_observing(repository: ProductRepository) -> None:
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)

    started = time.monotonic()
    status = manager.stop(STREAM_ID)
    elapsed = time.monotonic() - started

    assert status is not None
    assert status.state == "stopped"
    assert elapsed < 15.0  # well under the hard join timeout; a clean, bounded stop
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"
    # A second status read after stop must stay stable (side-effect-free).
    assert manager.status(STREAM_ID).state == "stopped"


# =============================================================================
# Sustained-Activity Visit Admission Starvation & Stop-Finalization
# Correctness v1: the "open, disclosed, unresolved question" Representative
# Daylight Gate A Field Acceptance v4 left open -- stopping the session
# *should* have force-finalized every pending proposal, yet the real stop
# response still showed zero admits. Root cause, confirmed here directly:
# `_EngineSession.stop()`'s own kill-switch revert (see its docstring)
# always reverted authority to shadow the instant its own bounded
# `thread.join()` returned, *whether or not the background thread had
# actually finished* -- including on a bare timeout, while the thread might
# still be completing its own `finally:` teardown (session.stop()'s tracker
# finalize, then the forced-decision finalize tick, then that same thread's
# own later revert). A finalize tick that reaches `create_candidate_visit_
# from_proposal` *after* this premature external revert reads authority
# fresh from the repository (by design -- see that method's own docstring)
# and sees `shadow`, silently discarding a genuine, already-force-decided
# candidate as `blocked_shadow_mode`. These tests drive the real
# `ObservationEngineSessionManager.start`/`.stop()` orchestration boundary
# production uses -- never a bypassed helper -- forcing the exact race
# deterministically (never a real-time coin flip) via a controllable
# blocking transport plus a monkeypatched, tiny join timeout.
# =============================================================================


class _BlockingAfterFirstBatchTransport(_FixtureTransport):
    """Yields one real, bounded batch (enough to confirm and start one
    track), then blocks -- deterministically, on a caller-controlled
    `threading.Event`, never a real-time sleep race -- before yielding
    anything further. `session.run()`'s own receiver thread
    (`camera_node_live.LiveCameraNodeShadowSession.run`) iterates this
    generator on its own dedicated thread, so blocking here blocks that one
    real batch call from ever returning, without blocking the asyncio event
    loop itself -- exactly the shape needed to force `_EngineSession.stop()`
    's own bounded `thread.join()` to observe a genuinely still-running
    background thread, deterministically, rather than only 'usually.'"""

    def __init__(self, *, release_event: threading.Event, frame_count: int = 4) -> None:
        super().__init__(frame_count=frame_count)
        self._release_event = release_event
        self._first_call_done = False

    def iter_analysis_frames(self, *, maximum_frames: int):
        if not self._first_call_done:
            self._first_call_done = True
            return self._paced_frames()
        return self._blocked_frames()

    def _blocked_frames(self):
        self._release_event.wait()
        return
        yield  # pragma: no cover - unreachable; makes this a generator function


def test_stop_does_not_race_the_kill_switch_against_a_still_finalizing_session(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct, deterministic reproduction of the real field mechanism: force
    `stop()`'s own bounded join to time out while the background thread is
    still genuinely mid-batch (never yet reached its own finalize tick),
    then prove the already-confirmed, already-started track's own eventual
    candidate Visit still gets created once the thread actually finishes --
    not silently discarded by a premature kill-switch revert."""
    monkeypatch.setattr(engine_runtime, "_STOP_JOIN_TIMEOUT_SECONDS", 0.05)
    release_event = threading.Event()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _BlockingAfterFirstBatchTransport(release_event=release_event),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
    # Let the one real batch actually land (the confirmed track has formed
    # and is genuinely still open/active) before the second, blocking call
    # is ever reached.
    assert _wait_until(lambda: manager.status(STREAM_ID).counts.track_updates_observed > 0, timeout=10.0)

    status = manager.stop(STREAM_ID)

    # The join genuinely timed out against a thread that is still alive
    # (blocked in the second, deliberately-withheld batch call) -- this
    # must be reported honestly, never silently claimed as a clean, fully
    # -finalized stop.
    assert status is not None
    assert status.state == "stopping"
    assert status.advanced.get("stop_finalization_pending") is True
    # The kill switch's own defensive revert must NOT have fired yet --
    # this is the exact race: reverting here, before the background
    # thread's own finalize tick runs, is what silently discarded the real
    # candidate before this fix.
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "candidate_visit"

    # Now let the background thread actually proceed: it notices the
    # withheld batch, treats it as an empty/no-frames result, sees
    # `_stop_event` already set, and falls through to its own real teardown
    # -- tracker finalize, the forced-decision finalize tick, then its own
    # authority revert -- all on the same thread, in the correct order.
    release_event.set()
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final_status = manager.status(STREAM_ID)
    assert final_status is not None
    assert final_status.advanced.get("stop_finalization_pending") is not True
    assert final_status.counts.candidates_created == 1, (
        f"the already-confirmed track's candidate must survive a timed-out stop() join; "
        f"suppressed={final_status.counts.suppressed_reasons}"
    )
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_repeated_stop_while_finalization_is_still_pending_is_safe(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling `stop()` again while a prior call's own join already timed
    out (finalization still pending) must stay safe: no duplicate revert
    side effect, no exception, no duplicate Visit once finalization
    actually completes."""
    monkeypatch.setattr(engine_runtime, "_STOP_JOIN_TIMEOUT_SECONDS", 0.05)
    release_event = threading.Event()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _BlockingAfterFirstBatchTransport(release_event=release_event),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
    assert _wait_until(lambda: manager.status(STREAM_ID).counts.track_updates_observed > 0, timeout=10.0)

    first = manager.stop(STREAM_ID)
    second = manager.stop(STREAM_ID)
    assert first is not None and second is not None
    assert first.state == "stopping"
    assert second.state == "stopping"

    release_event.set()
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)
    assert manager.status(STREAM_ID).counts.candidates_created == 1
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"

    # A third stop, now that the session has genuinely finished, stays the
    # existing, already-tested safe no-op.
    third = manager.stop(STREAM_ID)
    assert third is not None
    assert third.state == "stopped"
    assert manager.status(STREAM_ID).counts.candidates_created == 1


# --- Camera session collision fix: pause/resume the legacy live session ----
#
# "Fix Observation camera session collision": Observation Engine used to
# open its own Node connection with no awareness of an already-running
# legacy live-view/monitoring camera session for the same physical camera.
# These tests prove the coordination handshake -- pause right before this
# session starts pulling frames, resume on every exit path, best-effort
# either way -- without a real LiveCameraSessionManager (see
# tests/test_live_camera_session.py for that side, in isolation).


class _RecordingCameraCoordinator:
    """Fake `engine_runtime.LiveCameraSessionCoordinator`, recording calls
    in call order. Can be made to fail either call to prove a coordinator
    bug never breaks Start or Stop (both calls are best-effort)."""

    def __init__(self, *, fail_pause: bool = False, fail_resume: bool = False) -> None:
        self.pause_calls: list[str] = []
        self.resume_calls: list[StreamLivePlaybackConfig] = []
        self._fail_pause = fail_pause
        self._fail_resume = fail_resume

    def pause_for_observation(self, stream_id: str) -> None:
        self.pause_calls.append(stream_id)
        if self._fail_pause:
            raise RuntimeError("fixture_pause_failure")

    def resume_after_observation(self, config: StreamLivePlaybackConfig) -> None:
        self.resume_calls.append(config)
        if self._fail_resume:
            raise RuntimeError("fixture_resume_failure")


def test_start_pauses_live_session_and_stop_resumes_it(repository: ProductRepository) -> None:
    coordinator = _RecordingCameraCoordinator()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        live_camera_sessions=coordinator,
    )
    config = _camera_node_config()
    manager.start(STREAM_ID, config)
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)

    # Paused before this session ever pulled a frame from the Node, not
    # lazily/after the fact.
    assert coordinator.pause_calls == [STREAM_ID]
    assert coordinator.resume_calls == []

    manager.stop(STREAM_ID)

    assert coordinator.resume_calls == [config]


def test_session_ending_without_explicit_stop_still_resumes_the_live_session(
    repository: ProductRepository,
) -> None:
    """Resume must fire on *every* exit path, not only an explicit Stop --
    here, `_FixtureTransport`'s own deliberate terminal signal once its
    scripted frames are exhausted (see its docstring: a real live-camera
    analysis-stream has no legitimate "natural end" of its own after
    Observation Engine Session-Renewal Continuity v1)."""

    coordinator = _RecordingCameraCoordinator()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
        live_camera_sessions=coordinator,
    )
    config = _camera_node_config()
    manager.start(STREAM_ID, config)
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    assert coordinator.pause_calls == [STREAM_ID]
    assert coordinator.resume_calls == [config]


def test_camera_unavailable_mid_session_also_resumes_the_live_session(
    repository: ProductRepository,
) -> None:
    """A persistent Node transport failure -- recoverable-shaped, but never
    once recovering -- still eventually ends the session exactly like an
    explicit Stop from this coordination's point of view, once the bounded
    `AnalysisStreamRetryPolicy` budget is exhausted: the physical camera
    must still come back to the legacy live session, not sit paused
    forever."""

    class _FailingTransport(_FixtureTransport):
        def iter_analysis_frames(self, *, maximum_frames: int):
            self.calls += 1
            raise CameraNodeClientError("analysis_stream_unavailable")

    coordinator = _RecordingCameraCoordinator()
    failing_transport = _FailingTransport()
    failing_transport.calls = 0
    policy = engine_runtime.AnalysisStreamRetryPolicy(maximum_consecutive_failures=3, backoff_seconds=0.01)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: failing_transport,
        live_camera_sessions=coordinator,
        analysis_stream_retry_policy=policy,
    )
    config = _camera_node_config()
    manager.start(STREAM_ID, config)
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.stopped_reason == "camera_unavailable"
    assert final.camera_connected is False
    # Bounded, not instant and not infinite: every recoverable attempt was
    # actually retried up to the policy's own exact bound, never more.
    assert failing_transport.calls == policy.maximum_consecutive_failures
    assert final.advanced.get("analysis_stream_consecutive_failures") == policy.maximum_consecutive_failures

    assert coordinator.pause_calls == [STREAM_ID]
    assert coordinator.resume_calls == [config]


def test_pairing_incomplete_never_touches_the_live_session(repository: ProductRepository) -> None:
    """Observation never even validates its own config here -- it must not
    interfere with an unrelated, perfectly healthy live view."""

    coordinator = _RecordingCameraCoordinator()
    manager = _manager(repository, live_camera_sessions=coordinator)
    manager.start(STREAM_ID, _camera_node_config(camera_node_credential=None))
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "error", timeout=5.0)

    assert coordinator.pause_calls == []
    assert coordinator.resume_calls == []


def test_provider_load_failure_never_touches_the_live_session(repository: ProductRepository) -> None:
    """Observation Engine never reached the point of needing the physical
    camera -- a missing model bundle must not pause a healthy live view."""

    def _failing_loader(path: Path):
        raise ValueError("invalid_model_bundle_path")

    coordinator = _RecordingCameraCoordinator()
    manager = _manager(repository, provider_loader=_failing_loader, live_camera_sessions=coordinator)
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "error", timeout=5.0)

    assert coordinator.pause_calls == []
    assert coordinator.resume_calls == []


def test_pause_failure_never_prevents_observation_from_starting(repository: ProductRepository) -> None:
    coordinator = _RecordingCameraCoordinator(fail_pause=True)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        live_camera_sessions=coordinator,
    )
    manager.start(STREAM_ID, _camera_node_config())

    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
    assert coordinator.pause_calls == [STREAM_ID]
    manager.stop(STREAM_ID)


def test_resume_failure_never_prevents_stop_or_authority_revert(repository: ProductRepository) -> None:
    coordinator = _RecordingCameraCoordinator(fail_resume=True)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        live_camera_sessions=coordinator,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)

    status = manager.stop(STREAM_ID)

    assert status is not None
    assert status.state == "stopped"
    assert coordinator.resume_calls  # it was at least attempted
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_repeated_start_stop_observing_pauses_and_resumes_each_time(
    repository: ProductRepository,
) -> None:
    """Idempotent repeated Start/Stop observing: each cycle must pause and
    resume exactly once, never accumulate stale calls or skip a step."""

    coordinator = _RecordingCameraCoordinator()
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        live_camera_sessions=coordinator,
    )
    config = _camera_node_config()

    for cycle in range(1, 4):
        manager.start(STREAM_ID, config)
        assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
        manager.stop(STREAM_ID)
        assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)
        assert len(coordinator.pause_calls) == cycle
        assert len(coordinator.resume_calls) == cycle

    # Repeated Stop (already stopped) must stay a safe no-op: no extra calls.
    manager.stop(STREAM_ID)
    assert len(coordinator.pause_calls) == 3
    assert len(coordinator.resume_calls) == 3


# =============================================================================
# Visit Continuity / Provisional Admission Fix v1 (see
# docs/tracklet-visit-assembly-contract.md "Episode finality" and the real
# 2026-08-10 fresh-cohort candidate-004/005 field defect: a provisional
# tracklet was admitted as its own candidate Visit, then a same-encounter
# continuation tracklet merged into it and was admitted *again* 56 seconds
# later -- two persisted Visits for one real ~75-second encounter). These
# tests drive `_EngineSession._run_assembly_tick` directly -- the actual
# live production code path, not a reimplementation of it -- across
# multiple simulated ticks, which the timer-paced end-to-end tests above
# cannot exercise without a real multi-tick wall-clock wait.
# =============================================================================


def _tick_session(repository: ProductRepository) -> engine_runtime._EngineSession:
    return engine_runtime._EngineSession(
        stream_id=STREAM_ID,
        playback_config=_camera_node_config(),
        provider_config_path=Path("unused-for-this-test"),
        privacy_ignore_regions=(),
        repository_factory=lambda: repository,
    )


def _tick_adapter(repository: ProductRepository) -> CandidateVisitAuthorityAdapter:
    return CandidateVisitAuthorityAdapter(
        repository, detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda",
        provider_key="frame-driven-onnx-cuda",
    )


def _tick_track_updates(generation_id: str, start_ms: int, end_ms: int) -> tuple[TrackUpdate, ...]:
    """One minimal confirmed-and-ended generation -- exactly what
    `build_tracklets` requires: a `started` update and a terminal `ended`
    update carrying `lifecycle_state == 'ended'`."""
    box = (0.47, 0.58, 0.51, 0.63)
    return (
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=start_ms), status="started", lifecycle_state="confirmed",
            frame_id=f"frame-{generation_id}-start", source_offset_ms=start_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-start",),
            support_state="weak_detector_supported", detector_ran=True,
        ),
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=end_ms), status="ended", lifecycle_state="ended",
            frame_id=f"frame-{generation_id}-end", source_offset_ms=end_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-end",),
            support_state="weak_detector_supported", detector_ran=True,
            terminal_reason="maximum_unsupported_duration",
        ),
    )


def _tick_evidence(generation_id: str, role: str, suffix: str) -> tuple[EvidenceCandidate, bytes]:
    candidate = EvidenceCandidate(
        media_asset_id=f"shadow-burst:{suffix}", stream_id=STREAM_ID, role=role, captured_at=NOW,
        frame_id=f"frame-{generation_id}-start", subject_geometry=(0.47, 0.58, 0.51, 0.63),
        track_generation_id=generation_id,
    )
    return candidate, _jpeg_bytes()


def test_continuation_pending_defers_admission_until_encounter_resolves(repository: ProductRepository) -> None:
    """Direct reproduction of the real 004/005 field defect at the actual
    `_EngineSession._run_assembly_tick` call site: a tracklet that
    finalizes alone must not be admitted before its own continuation
    window closes; once a genuine continuation tracklet merges into it,
    only the merged episode is ever admitted -- one encounter, one Visit,
    never two."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_early, gen_continuation = "gen-early", "gen-continuation"
    early_updates = list(_tick_track_updates(gen_early, 0, 5_000))
    # Within merge_gap_ms (15,000ms) of gen_early's own end -- a same
    # -encounter continuation after a brief reacquisition gap, exactly the
    # real attempt-3/004-005 shape.
    continuation_updates = list(_tick_track_updates(gen_continuation, 12_000, 17_000))

    evidence_a, bytes_a = _tick_evidence(gen_early, "high_resolution_burst", "hash-a")
    evidence_b, bytes_b = _tick_evidence(gen_continuation, "context", "hash-b")
    burst_bytes_cache = {evidence_a.media_asset_id: bytes_a, evidence_b.media_asset_id: bytes_b}
    attempted_proposal_ids: set[str] = set()

    # Tick 1: only the early generation has finalized. Its own continuation
    # window (`ambiguous_gap_ms`=45,000ms past its own end) has not closed
    # -- this is the exact moment the real, pre-fix pipeline admitted
    # candidate-004.
    session._run_assembly_tick(
        all_track_updates=early_updates, all_evidence_candidates=[evidence_a],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=5_100,
    )
    assert session._counts.candidates_created == 0
    assert attempted_proposal_ids == set()  # never permanently remembered -- must be retried
    assert session._suppressed.get("blocked_continuation_pending") == 1

    # Tick 2: the continuation generation has now also finalized and merges
    # with the early one (real code path: the unmodified `assemble_visit_
    # episodes` itself decides this). The *merged* proposal's own window
    # has also not closed yet -- still correctly deferred.
    all_updates = early_updates + continuation_updates
    all_evidence = [evidence_a, evidence_b]
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=17_100,
    )
    assert session._counts.candidates_created == 0
    assert attempted_proposal_ids == set()
    assert session._suppressed.get("blocked_continuation_pending") == 2

    # Tick 3: enough of the stream has now been observed with nothing
    # further arriving -- the merged episode finally becomes eligible.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=17_000 + 45_000 + 1,
    )
    assert session._counts.candidates_created == 1
    assert len(attempted_proposal_ids) == 1

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    final_proposal_id = next(iter(attempted_proposal_ids))
    with repository.session_factory() as db_session:
        import json as _json

        ledger = db_session.get(ObservationCandidateVisitModel, final_proposal_id)
        assert ledger is not None
        assert _json.loads(ledger.constituent_generation_ids_json) == [gen_early, gen_continuation]
        assert ledger.visit_id == session._last_candidate_visit_id


def test_finalize_tick_admits_a_still_pending_singleton_immediately(repository: ProductRepository) -> None:
    """Session end (`finalize=True`, real code path: the `finally:` block's
    own last tick in `_run_async`) must treat a still-pending proposal as
    final right away -- the stream itself has ended, so no continuation
    could ever arrive. This is the exact real shape of the fresh cohort's
    own candidate-006 (created during the session's graceful-teardown
    window) and proves the fix does not silently swallow a genuine
    encounter that simply never got a chance to wait out its own window."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    updates = list(_tick_track_updates("gen-solo", 0, 1_000))
    evidence_a, bytes_a = _tick_evidence("gen-solo", "high_resolution_burst", "hash-solo-a")
    evidence_b, bytes_b = _tick_evidence("gen-solo", "context", "hash-solo-b")
    burst_bytes_cache = {evidence_a.media_asset_id: bytes_a, evidence_b.media_asset_id: bytes_b}
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[evidence_a, evidence_b],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=1_100, finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert session._suppressed.get("blocked_continuation_pending") is None


def test_finalize_tick_resolves_a_still_ambiguous_pair_to_exactly_one_visit(repository: ProductRepository) -> None:
    """Test-matrix item (brief §16, "Stop finalization"): stop with a
    pending *ambiguous* (not merely continuation-pending) episode must
    still behave according to the existing, unmodified ambiguity contract
    at the session-ending tick -- arbitration runs, the single
    best-evidenced sibling is admitted, and the weaker one stays
    permanently blocked. Never both, never neither, exactly like an
    ordinary mid-session ambiguous resolution."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-finalize-strong", "gen-finalize-weak"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.8))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.2))
    all_updates = strong_updates + weak_updates

    evidence_strong, bytes_strong = _tick_evidence(gen_strong, "high_resolution_burst", "hash-finalize-strong")
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-finalize-weak")
    burst_bytes_cache = {evidence_strong.media_asset_id: bytes_strong, evidence_weak.media_asset_id: bytes_weak}
    attempted_proposal_ids: set[str] = set()

    # A single session-ending tick, exactly like a real stream that ends
    # (or is explicitly stopped) shortly after this ambiguous pair formed --
    # never given the chance to individually stabilize mid-session first.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=[evidence_strong, evidence_weak],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_100, finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert session._suppressed.get("blocked_ambiguous_boundary") == 1
    assert len(attempted_proposal_ids) == 2  # both permanently resolved: one create, one block, never deferred


# =============================================================================
# Admission Recall Investigation + Conditional Fix v1 (see "Ambiguous
# boundary arbitration" in docs/tracklet-visit-assembly-contract.md): a real
# ~94-minute accepted daily-use session found `blocked_ambiguous_boundary`,
# unlike `blocked_continuation_pending`, was a genuinely *permanent* verdict
# -- including for a confirmed detection above the strong-detection
# threshold (0.795) and for a well-evidenced, cleanly-merged 14-generation
# episode that kept absorbing continuation evidence without ever being
# reconsidered. These tests drive `_EngineSession._run_assembly_tick`
# directly across multiple simulated ticks -- the actual live production
# code path -- mirroring the Visit Continuity tests above exactly.
# =============================================================================


def _tick_track_updates_with_confidence(
    generation_id: str, start_ms: int, end_ms: int, *, confidence: float,
) -> tuple[TrackUpdate, ...]:
    """`_tick_track_updates` with an explicit detector confidence carried
    on both updates -- `Tracklet.confidence`/`ConfidenceEvidenceSummary.
    max_confidence` are both derived from `TrackUpdate.confidence` (see
    `build_tracklets`), so this is what actually differentiates two
    otherwise-identical tracklets for arbitration purposes."""
    box = (0.47, 0.58, 0.51, 0.63)
    return (
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=start_ms), status="started", lifecycle_state="confirmed",
            frame_id=f"frame-{generation_id}-start", source_offset_ms=start_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-start",),
            support_state="weak_detector_supported", detector_ran=True, confidence=confidence,
        ),
        TrackUpdate(
            track_id=f"{generation_id}-track", generation_id=generation_id,
            captured_at=NOW + timedelta(milliseconds=end_ms), status="ended", lifecycle_state="ended",
            frame_id=f"frame-{generation_id}-end", source_offset_ms=end_ms, broad_class="animal",
            bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-end",),
            support_state="weak_detector_supported", detector_ran=True, confidence=confidence,
            terminal_reason="maximum_unsupported_duration",
        ),
    )


def test_ambiguous_boundary_arbitration_admits_the_stronger_of_two_stable_siblings(
    repository: ProductRepository,
) -> None:
    """Direct reproduction, at the real `_EngineSession._run_assembly_tick`
    call site, of the real accepted session's own concrete finding: two
    confirmed, geometrically-compatible tracklets ~20s apart (beyond
    `merge_gap_ms`=15,000ms, so they do not silently merge; inside
    `ambiguous_gap_ms`=45,000ms, so the assembler correctly reports the
    boundary as ambiguous rather than `keep_separate`) -- the same shape as
    the real field pair (0.795 vs 0.590 confidence, 1.7s apart, both
    single-generation, both permanently lost before this fix). Before this
    fix both would be blocked forever; after it, exactly the stronger one
    is admitted and the weaker one stays suppressed -- never both, never
    neither."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-strong", "gen-weak"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.8))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.2))
    all_updates = strong_updates + weak_updates

    evidence_strong, bytes_strong = _tick_evidence(gen_strong, "high_resolution_burst", "hash-strong")
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-weak")
    burst_bytes_cache = {evidence_strong.media_asset_id: bytes_strong, evidence_weak.media_asset_id: bytes_weak}
    all_evidence = [evidence_strong, evidence_weak]
    attempted_proposal_ids: set[str] = set()

    # Tick 1: both generations have already finalized, but neither
    # proposal's own continuation window (`ambiguous_gap_ms` past its own
    # end) has closed yet -- arbitration must defer both rather than lock
    # in a premature verdict while either could still grow.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_100,
    )
    assert session._counts.candidates_created == 0
    assert attempted_proposal_ids == set()

    # Tick 2: enough of the stream has now been observed for both
    # proposals' own tails to finalize -- arbitration now runs. The
    # stronger (0.8) generation is admitted; the weaker (0.2) one stays
    # blocked, permanently, as a genuinely resolved fact about that exact
    # proposal id -- exactly the duplicate-Visit protection the original,
    # unconditional block existed to provide, still intact.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 1,
    )
    assert session._counts.candidates_created == 1
    assert len(attempted_proposal_ids) == 2  # both now permanently resolved: one create, one block
    assert session._suppressed.get("blocked_ambiguous_boundary") == 1

    import json as _json

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    assert len(created_rows) == 1
    assert _json.loads(created_rows[0].constituent_generation_ids_json) == [gen_strong]
    assert created_rows[0].visit_id == session._last_candidate_visit_id

    # Tick 3: nothing changed -- both ids are permanently attempted, so a
    # repeated tick must never create a second Visit for the same pair.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 5_000,
    )
    assert session._counts.candidates_created == 1


def test_resolved_component_falls_back_when_top_member_evidence_was_evicted(
    repository: ProductRepository,
) -> None:
    """Pending-Proposal Evidence Preservation & Arbitration Fallback
    Correctness v1 -- permanent regression test for the Representative
    Daylight Gate A Field Acceptance v6 loss class (real, live, 106.63-
    minute session: a real arbitration winner permanently failed the
    downstream evidence-availability gate, 48/263 distinct proposals,
    18.3%, with no runner-up ever attempted, silently losing entire real
    activity components). Before this fix (RED on accepted `b37656d`):
    arbitration was single-shot, not a retry chain -- if the single
    best-evidenced member of a stabilized ambiguous cluster failed a
    *later* gate (here, `blocked_missing_evidence` -- no persistable
    evidence bytes at all for the winner), the weaker sibling was never
    promoted, and the entire real, confirmed encounter was lost. After this
    fix: the next-best *other* stable member of the exact same resolved
    component -- which does have real, usable evidence -- is tried next,
    in the deterministic order `resolve_ambiguous_boundary_arbitration`
    already ranks, and is admitted. Never "try everything until something
    passes" -- exactly one other member exists here, and it succeeds on
    its own genuine merits (real evidence bytes, same quality bar as
    always), not because the bar was lowered."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-strong-no-evidence", "gen-weak-with-evidence"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.9))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.1))
    all_updates = strong_updates + weak_updates

    # Only the *weaker* generation has real, byte-backed evidence; the
    # stronger one's evidence candidate exists (so it is still a
    # structurally valid proposal) but no bytes are cached for it -- exactly
    # the real v6 shape: evidence genuinely captured, then evicted (or, as
    # here, never harvested at all) before this specific winner's own
    # delayed admission attempt ever ran.
    evidence_strong, _unused_bytes = _tick_evidence(gen_strong, "high_resolution_burst", "hash-strong-empty")
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-weak-real")
    burst_bytes_cache = {evidence_weak.media_asset_id: bytes_weak}  # deliberately no entry for evidence_strong
    all_evidence = [evidence_strong, evidence_weak]
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 1,
    )
    # The real activity is no longer lost: the component still yields
    # exactly one Visit (never both, never a duplicate), and both members
    # are still permanently, individually resolved -- fallback changes
    # *which* member wins, never the "at most one Visit per component"
    # invariant itself.
    assert session._counts.candidates_created == 1
    assert len(attempted_proposal_ids) == 2
    # The stronger member's own true reason is preserved verbatim -- it
    # genuinely had no evidence, and that fact is not hidden by the
    # fallback that rescued its sibling.
    assert session._suppressed.get("blocked_missing_evidence") == 1
    # Neither member is a "loser" of an ordinary, un-rescued ambiguous
    # comparison anymore -- the old contract's own diagnostic signature is
    # gone.
    assert "blocked_ambiguous_boundary" not in session._suppressed
    # Diagnostics (brief §19): exactly one component needed fallback, and it
    # succeeded -- never "exhausted", never counted more than once.
    assert session._fallback_attempted_count == 1
    assert session._fallback_admitted_count == 1
    assert session._fallback_exhausted_count == 0

    import json as _json

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    assert len(created_rows) == 1
    # The *weaker* generation -- the one with real evidence -- is the one
    # actually admitted, never the evidence-less "winner" and never a
    # fabricated mix of both.
    assert _json.loads(created_rows[0].constituent_generation_ids_json) == [gen_weak]

    # The ledger's own record for the admitted fallback member is honestly
    # marked as such -- a reviewer/auditor can tell "this was admitted via
    # fallback, at position 1" apart from an ordinary direct win, without a
    # new schema field (reuses the existing free-form `reason` string, the
    # same additive-suffix convention `candidate_visit_adapter.py` already
    # uses for a retry-exhausted persistence failure).
    window = session.counterfactual_query(start_offset_ms=0, end_offset_ms=10_000_000)
    outcomes_by_generation = {
        tuple(record.constituent_generation_ids): record for record in window.proposal_outcomes
    }
    assert outcomes_by_generation[(gen_weak,)].reason.endswith(":fallback_position_1")
    assert outcomes_by_generation[(gen_weak,)].outcome == "created"
    # The strong (evidence-less) member's own record is never suffixed --
    # it was the primary attempt, not a fallback attempt.
    assert outcomes_by_generation[(gen_strong,)].reason == "no_persistable_evidence_bytes"


def test_fallback_is_correct_regardless_of_which_component_member_the_assembler_lists_first(
    repository: ProductRepository,
) -> None:
    """Adversarial self-review finding (brief §31), fixed before it ever
    reached a committed test: `new_proposals`' own list order (the
    assembler's own emission order, close to tracklet arrival/temporal
    order) has no guaranteed relationship to arbitration rank. Every other
    fallback test in this file happens to construct the *winner* as the
    temporally-earliest member, which also makes it first in `assemble_
    visit_episodes`'s own output -- silently masking a real bug where a
    losing sibling reached first took the ordinary path (permanently
    `blocked_ambiguous_boundary`) *before* its own winner's chain ever
    ran, then was attempted a second time once the chain reached it,
    corrupting `proposals_observed`/the ledger with a duplicate record.
    Reversed here on purpose: the weaker (fallback-admitted) member is
    temporally *first*; the stronger (evidence-less) winner is temporally
    *second*, and therefore last in the assembler's own emission order."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_weak, gen_strong = "gen-weak-first-in-list", "gen-strong-second-in-list"
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 0, 5_000, confidence=0.1))
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 25_000, 30_000, confidence=0.9))
    all_updates = weak_updates + strong_updates  # weak's own tracklet is fed to the assembler first

    evidence_strong, _unused_bytes = _tick_evidence(gen_strong, "high_resolution_burst", "hash-strong-empty-order")
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-weak-real-order")
    burst_bytes_cache = {evidence_weak.media_asset_id: bytes_weak}
    all_evidence = [evidence_strong, evidence_weak]
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 1,
    )
    assert session._counts.candidates_created == 1
    # Exactly two real proposals exist in this component -- exactly two
    # must be observed, never three from a spurious re-attempt.
    assert session._counts.proposals_observed == 2
    assert len(attempted_proposal_ids) == 2
    assert "blocked_ambiguous_boundary" not in session._suppressed
    assert session._suppressed.get("blocked_missing_evidence") == 1

    window = session.counterfactual_query(start_offset_ms=0, end_offset_ms=10_000_000)
    # Exactly one ledger record per real proposal -- never two for the
    # fallback-admitted one (one premature `blocked_ambiguous_boundary`,
    # one later `created`).
    assert len(window.proposal_outcomes) == 2
    outcomes_by_generation = {
        tuple(record.constituent_generation_ids): record for record in window.proposal_outcomes
    }
    assert outcomes_by_generation[(gen_weak,)].outcome == "created"
    assert outcomes_by_generation[(gen_weak,)].reason.endswith(":fallback_position_1")
    assert outcomes_by_generation[(gen_strong,)].reason == "no_persistable_evidence_bytes"


def test_component_with_no_viable_member_admits_nothing_and_diagnoses_honestly(
    repository: ProductRepository,
) -> None:
    """Tier 1 matrix (brief §28): "winner missing + all alternatives missing
    -> no admission, honest diagnostic." Fallback tries every stable member
    of a resolved component, in order -- it must never fabricate an
    admission when *none* of them can actually produce one. Every member
    still gets its own true, individually-recorded outcome; the session's
    own diagnostics honestly show fallback was invoked and exhausted,
    never silently swallowed into an ordinary, unremarkable loss."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_a, gen_b, gen_c = "gen-a-no-evidence", "gen-b-no-evidence", "gen-c-no-evidence"
    updates_a = list(_tick_track_updates_with_confidence(gen_a, 0, 5_000, confidence=0.9))
    updates_b = list(_tick_track_updates_with_confidence(gen_b, 25_000, 30_000, confidence=0.5))
    updates_c = list(_tick_track_updates_with_confidence(gen_c, 50_000, 55_000, confidence=0.1))
    all_updates = updates_a + updates_b + updates_c

    # Every member's evidence candidate exists (structurally valid
    # proposals), but not one of them has real bytes anywhere -- the
    # component is genuinely, honestly unrepresentable.
    evidence_a, _ = _tick_evidence(gen_a, "high_resolution_burst", "hash-a-empty")
    evidence_b, _ = _tick_evidence(gen_b, "high_resolution_burst", "hash-b-empty")
    evidence_c, _ = _tick_evidence(gen_c, "high_resolution_burst", "hash-c-empty")
    burst_bytes_cache: dict[str, bytes] = {}
    all_evidence = [evidence_a, evidence_b, evidence_c]
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=55_000 + 45_000 + 1,
    )
    assert session._counts.candidates_created == 0
    assert len(attempted_proposal_ids) == 3
    # All three members honestly, individually record `blocked_missing_
    # evidence` -- fallback tried every one of them, it did not skip any
    # or merge them into one generic verdict.
    assert session._suppressed.get("blocked_missing_evidence") == 3
    assert "blocked_ambiguous_boundary" not in session._suppressed

    assert session._fallback_attempted_count == 1
    assert session._fallback_admitted_count == 0
    assert session._fallback_exhausted_count == 1

    window = session.counterfactual_query(start_offset_ms=0, end_offset_ms=10_000_000)
    outcomes_by_generation = {
        tuple(record.constituent_generation_ids): record for record in window.proposal_outcomes
    }
    # The winner (highest confidence, gen_a) is the primary attempt, never
    # suffixed; the two fallback attempts are honestly marked with their
    # own chain position.
    assert outcomes_by_generation[(gen_a,)].reason == "no_persistable_evidence_bytes"
    assert outcomes_by_generation[(gen_b,)].reason == "no_persistable_evidence_bytes:fallback_position_1"
    assert outcomes_by_generation[(gen_c,)].reason == "no_persistable_evidence_bytes:fallback_position_2"

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    assert created_rows == []


def test_fallback_never_mixes_evidence_across_two_independent_simultaneous_components(
    repository: ProductRepository,
) -> None:
    """Multi-subject safety (brief §17): two entirely separate, genuinely
    simultaneous ambiguous components -- two different real subjects at
    two different places in frame -- both resolve on the same tick, and
    both winners lack evidence. Each must independently fall back to its
    *own* other member and nowhere else: no cross-subject evidence reuse,
    no collapsing the two sibling candidates into one, no cross-track
    contamination."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    feeder_box = (0.47, 0.58, 0.51, 0.63)
    perch_box = (0.05, 0.05, 0.15, 0.15)  # geometrically incompatible with feeder_box -- a distinct subject

    def _pair_updates(prefix: str, box: tuple[float, float, float, float]):
        strong = _tick_track_updates_with_confidence(f"gen-{prefix}-strong", 0, 5_000, confidence=0.9)
        weak = _tick_track_updates_with_confidence(f"gen-{prefix}-weak", 25_000, 30_000, confidence=0.1)
        return [
            replace(update, bounding_box=box) for update in (*strong, *weak)
        ]

    all_updates = _pair_updates("feeder", feeder_box) + _pair_updates("perch", perch_box)

    evidence_feeder_strong, _ = _tick_evidence("gen-feeder-strong", "high_resolution_burst", "hash-feeder-strong-empty")
    evidence_feeder_weak, bytes_feeder_weak = _tick_evidence(
        "gen-feeder-weak", "high_resolution_burst", "hash-feeder-weak-real",
    )
    evidence_perch_strong, _ = _tick_evidence("gen-perch-strong", "high_resolution_burst", "hash-perch-strong-empty")
    evidence_perch_weak, bytes_perch_weak = _tick_evidence(
        "gen-perch-weak", "high_resolution_burst", "hash-perch-weak-real",
    )
    all_evidence = [evidence_feeder_strong, evidence_feeder_weak, evidence_perch_strong, evidence_perch_weak]
    burst_bytes_cache = {
        evidence_feeder_weak.media_asset_id: bytes_feeder_weak,
        evidence_perch_weak.media_asset_id: bytes_perch_weak,
    }
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 1,
    )
    # Both components independently rescued -- never merged into one, never
    # only one of the two.
    assert session._counts.candidates_created == 2
    assert len(attempted_proposal_ids) == 4
    assert session._fallback_attempted_count == 2
    assert session._fallback_admitted_count == 2
    assert session._fallback_exhausted_count == 0

    import json as _json

    from mockingbird.repository.product_repository import MediaAssetModel, ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    created_generations = {
        tuple(_json.loads(row.constituent_generation_ids_json))[0] for row in created_rows
    }
    # Exactly the two *weak* (real-evidence) members were admitted, one per
    # subject -- never the evidence-less strong ones, never a mix, never a
    # duplicate of either.
    assert created_generations == {"gen-feeder-weak", "gen-perch-weak"}
    # Every persisted evidence row's own `trigger_id` (the engine-side
    # proposal id it was actually built from) matches the Visit it is
    # attached to -- proof, at the persistence boundary, that neither
    # subject's own fallback attempt could have reused the other's bytes.
    with repository.session_factory() as db_session:
        for row in created_rows:
            persisted_ids = _json.loads(row.persisted_media_asset_ids_json)
            assert persisted_ids, f"Visit {row.visit_id} has no persisted evidence"
            for media_id in persisted_ids:
                media = db_session.get(MediaAssetModel, media_id)
                assert media is not None
                assert media.trigger_id == row.proposal_id


def test_fallback_admission_persists_the_admitted_members_own_capture_time_not_the_failed_winners(
    repository: ProductRepository,
) -> None:
    """Gate A Measurement Closure v1 §21 regression: when fallback admits a
    lower-ranked component member, every persisted evidence timestamp must
    trace to *that* member's own evidence, never the failed winner's --
    the exact property Gate A Measurement Closure v1's own new latency
    instrumentation (`capture_to_visible_latency.py`) depends on being
    true. Not a new behavior: `_attempt_resolved_component` already looks
    up each chain member's own `AssembledVisitProposal`/evidence fresh by
    id (`engine_runtime.py`) -- this pins that existing, correct behavior
    down at the actual persistence boundary so a future change cannot
    silently regress it."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-strong-no-evidence", "gen-weak-with-evidence"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.9))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.1))
    all_updates = strong_updates + weak_updates

    # Two evidence candidates whose own `captured_at` values are far apart
    # and unmistakable -- if the fallback admission ever persisted the
    # winner's own evidence/timestamp by mistake, this test would catch it
    # directly, not merely infer it from generation ids as the sibling
    # test above does.
    winner_captured_at = NOW
    fallback_captured_at = NOW + timedelta(minutes=5)
    evidence_strong, _unused_bytes = _tick_evidence(gen_strong, "high_resolution_burst", "hash-strong-empty")
    evidence_strong = replace(evidence_strong, captured_at=winner_captured_at)
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-weak-real")
    evidence_weak = replace(evidence_weak, captured_at=fallback_captured_at)
    burst_bytes_cache = {evidence_weak.media_asset_id: bytes_weak}  # no bytes for the winner -- it must fail
    all_evidence = [evidence_strong, evidence_weak]
    attempted_proposal_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=all_evidence,
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_000 + 45_000 + 1,
    )
    assert session._fallback_admitted_count == 1

    import json as _json

    from mockingbird.repository.product_repository import MediaAssetModel, ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    assert len(created_rows) == 1
    with repository.session_factory() as db_session:
        persisted_ids = _json.loads(created_rows[0].persisted_media_asset_ids_json)
        assert persisted_ids
        # `normalize_utc`, not a raw `==`: SQLite round-trips a `DateTime
        # (timezone=True)` column back as a naive `datetime` (a pre-existing,
        # unrelated storage-layer fact, not something this milestone
        # changes) -- the *wall-clock value* is still what is being proven
        # correct here, exactly the "legacy naive persisted values" case
        # `time_utils.normalize_utc` already exists to handle.
        captured_at_values = [
            normalize_utc(db_session.get(MediaAssetModel, media_id).captured_at) for media_id in persisted_ids
        ]
    # Every persisted evidence item's own capture time is the *admitted*
    # (fallback) member's, never the failed winner's, and never a mix of
    # both.
    assert captured_at_values
    assert all(value == fallback_captured_at for value in captured_at_values)
    assert winner_captured_at not in captured_at_values


def test_fallback_works_during_stop_finalization(repository: ProductRepository) -> None:
    """Stop-finalization (brief §20): the exact `test_finalize_tick_
    resolves_a_still_ambiguous_pair_to_exactly_one_visit` scenario above,
    except the naturally-stronger member now has no evidence -- fallback
    must work identically at the session-ending `finalize=True` tick as it
    does mid-session."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-finalize-strong-no-evidence", "gen-finalize-weak-with-evidence"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.8))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.2))
    all_updates = strong_updates + weak_updates

    evidence_strong, _unused_bytes = _tick_evidence(gen_strong, "high_resolution_burst", "hash-finalize-strong-empty")
    evidence_weak, bytes_weak = _tick_evidence(gen_weak, "high_resolution_burst", "hash-finalize-weak-real")
    burst_bytes_cache = {evidence_weak.media_asset_id: bytes_weak}  # deliberately no entry for evidence_strong
    attempted_proposal_ids: set[str] = set()

    # A single session-ending tick -- stop is called shortly after this
    # ambiguous pair formed, never given the chance to individually
    # stabilize mid-session first.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=[evidence_strong, evidence_weak],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_100, finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert len(attempted_proposal_ids) == 2
    assert session._fallback_attempted_count == 1
    assert session._fallback_admitted_count == 1

    import json as _json

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]
    assert len(created_rows) == 1
    assert _json.loads(created_rows[0].constituent_generation_ids_json) == [gen_weak]

    # Repeated stop/finalize does not duplicate (brief §15/§20): a second,
    # identical finalize tick over the same unchanged state must not admit
    # a second Visit -- both proposal ids are already permanently resolved.
    session._run_assembly_tick(
        all_track_updates=all_updates, all_evidence_candidates=[evidence_strong, evidence_weak],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=30_100, finalize=True,
    )
    assert session._counts.candidates_created == 1


# =============================================================================
# Sustained-Activity Visit Admission Starvation & Stop-Finalization
# Correctness v1: Representative Daylight Gate A Field Acceptance v4's own
# real ~112-minute field session found sustained, near-continuous multi-bird
# feeder activity produces `candidates_created == 0` for an *entire live
# session* -- not merely a longer delay than usual. Root cause: every
# successive `maximum_episode_duration_ms`-capped episode fragment stays
# transitively ambiguous-linked to the next one, and because a connected
# component's own currently-active tail is, by construction, still growing
# for as long as raw activity continues, the *whole* component stays
# deferred for the entire remaining life of the session. These tests drive
# `_EngineSession._run_assembly_tick` directly across many simulated ticks
# -- the real production code path -- with large, purely-synthetic
# (never wall-clock) offsets, exactly mirroring how every other multi-tick
# test above already proves this without a real multi-minute wait.
# =============================================================================


def _sustained_activity_tick_session(repository: ProductRepository) -> tuple[
    engine_runtime._EngineSession, CandidateVisitAuthorityAdapter,
]:
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    return _tick_session(repository), _tick_adapter(repository)


def _drive_sustained_activity(
    session: engine_runtime._EngineSession,
    adapter: CandidateVisitAuthorityAdapter,
    *,
    total_simulated_ms: int,
    spacing_ms: int = 5_000,
    tracklet_duration_ms: int = 1_000,
    tick_every_ms: int = 60_000,
) -> tuple[list[TrackUpdate], list[EvidenceCandidate], dict[str, bytes], set[str], list[int]]:
    """Feeds one uniform, continuous, always-merge-eligible (gap well under
    `merge_gap_ms`=15,000ms) sequence of confirmed tracklets -- the same
    fixed geometry/broad_class `_tick_track_updates` already uses -- through
    the real `_run_assembly_tick` call site at a coarse, bounded cadence.
    Uniform spacing well under `maximum_episode_duration_ms`=1,200,000ms
    reliably produces at least one forced max-duration split once
    `total_simulated_ms` exceeds it, and the tie between the frozen prior
    chain and the fresh one immediately after a split reliably produces a
    real `ambiguous_adjacent_proposal_ids` link between them (the exact
    mechanism `assemble_visit_episodes` uses for a genuine multi-way merge
    tie) -- never hand-constructed, always the real assembler's own output.
    A deliberately *unbounded* local evidence cache (not the real, bounded
    128-entry one) isolates the arbitration/authority mechanism this test
    targets from the separate evidence-cache-capacity concern already
    covered by the tests above.

    Returns the accumulated state plus the list of `candidates_created`
    counts observed after every tick, so a caller can assert not just the
    final count but *when* (relative to `total_simulated_ms`) admission
    first happened."""

    all_updates: list[TrackUpdate] = []
    all_evidence: list[EvidenceCandidate] = []
    burst_bytes_cache: dict[str, bytes] = {}
    attempted_proposal_ids: set[str] = set()
    candidates_created_after_each_tick: list[int] = []

    generation_index = 0
    next_start_ms = 0
    next_tick_at_ms = tick_every_ms
    while next_start_ms + tracklet_duration_ms <= total_simulated_ms:
        generation_id = f"gen-sustained-{generation_index}"
        generation_index += 1
        all_updates.extend(_tick_track_updates(generation_id, next_start_ms, next_start_ms + tracklet_duration_ms))
        evidence, payload = _tick_evidence(generation_id, "high_resolution_burst", f"hash-{generation_id}")
        all_evidence.append(evidence)
        burst_bytes_cache[evidence.media_asset_id] = payload

        known_horizon_ms = next_start_ms + tracklet_duration_ms
        if known_horizon_ms >= next_tick_at_ms:
            session._run_assembly_tick(
                all_track_updates=all_updates, all_evidence_candidates=all_evidence,
                attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache,
                adapter=adapter, known_horizon_ms=known_horizon_ms,
            )
            next_tick_at_ms += tick_every_ms
            candidates_created_after_each_tick.append(session._counts.candidates_created)
        next_start_ms += spacing_ms

    return all_updates, all_evidence, burst_bytes_cache, attempted_proposal_ids, candidates_created_after_each_tick


def test_sustained_activity_does_not_starve_admission_forever(repository: ProductRepository) -> None:
    """Direct reproduction of the real field defect: simulates 26 minutes of
    continuous, merge-eligible activity -- comfortably past one
    `maximum_episode_duration_ms` (20-minute) forced split, with activity
    still ongoing throughout. Before the fix, the resulting ambiguous
    component (the frozen pre-split chain plus the still-growing post-split
    one) defers forever, no matter how long it has been waiting; after it,
    a bounded Visit is admitted well before the simulated activity itself
    ever stops -- proving this is a live-session admission fix, not merely
    a session-end rescue."""
    session, adapter = _sustained_activity_tick_session(repository)
    *_, candidates_created_after_each_tick = _drive_sustained_activity(
        session, adapter, total_simulated_ms=26 * 60_000,
    )
    assert candidates_created_after_each_tick, "the drive helper must have run at least one tick"
    assert max(candidates_created_after_each_tick) > 0, (
        "expected at least one admitted Visit before 26 simulated minutes of continuous activity ended "
        f"-- per-tick candidates_created history: {candidates_created_after_each_tick}; "
        f"final suppressed reasons: {session._suppressed}"
    )
    # Non-starvation, not fragmentation: 26 minutes of one continuous
    # encounter must not explode into dozens of tiny duplicate Visits
    # either -- bounded, not "every tick creates a new Visit."
    assert session._counts.candidates_created <= 3


def test_sustained_activity_admission_happens_within_the_pending_horizon_not_only_at_the_very_end(
    repository: ProductRepository,
) -> None:
    """Sharper timing assertion than the test above: the very first
    admission must land at (or shortly after) the bounded decision horizon
    -- roughly the 20-minute mark -- never only in the session's final
    minutes, which would just be a smaller-scale version of the same
    starvation defect."""
    session, adapter = _sustained_activity_tick_session(repository)
    _, _, _, _, candidates_created_after_each_tick = _drive_sustained_activity(
        session, adapter, total_simulated_ms=40 * 60_000,
    )
    first_tick_index_with_admission = next(
        (index for index, count in enumerate(candidates_created_after_each_tick) if count > 0), None,
    )
    assert first_tick_index_with_admission is not None
    first_admission_at_simulated_minute = (first_tick_index_with_admission + 1)  # tick_every_ms=60_000 => 1 tick/min
    assert first_admission_at_simulated_minute <= 25, (
        f"first admission landed at simulated minute {first_admission_at_simulated_minute}, expected at or "
        "shortly after the 20-minute bounded decision horizon, not deferred toward the end of a 40-minute run"
    )


def test_sustained_activity_does_not_duplicate_or_explode_visits_over_a_long_run(
    repository: ProductRepository,
) -> None:
    """Performance/fragmentation guard (see brief §19): a much longer, 65
    -minute continuous run must still produce a small, bounded number of
    Visits -- not an explosion, not a duplicate-per-tick runaway -- and
    must complete in a reasonable amount of real time despite the fully
    unmodified, from-scratch-every-tick assembler re-running over an
    ever-growing track-update history."""
    session, adapter = _sustained_activity_tick_session(repository)
    started = time.monotonic()
    *_, candidates_created_after_each_tick = _drive_sustained_activity(
        session, adapter, total_simulated_ms=65 * 60_000,
    )
    elapsed_seconds = time.monotonic() - started
    assert max(candidates_created_after_each_tick) > 0
    # ~65 minutes / a ~20-25-minute bounded horizon: a handful of Visits,
    # nowhere near "one per tick" (65 ticks) or "one per generation" (780).
    assert 1 <= session._counts.candidates_created <= 6
    assert elapsed_seconds < 60.0, f"65-minute simulated replay took {elapsed_seconds:.1f}s of real time"


def test_field_derived_multi_subject_stress_replay(repository: ProductRepository) -> None:
    """Field-derived stress replay (brief §18/§10): a product-shaped
    synthetic sequence approximating the real field pattern -- continuous
    tracks/proposals, >100 simulated minutes, repeated feeder-region
    activity, plus a second, distinct, geometrically-separate subject
    (a different part of the frame) active *throughout*, simultaneously
    with the first -- one real, joint `_run_assembly_tick` history, never
    two independent runs stitched together after the fact. Proves the
    bounded-decision fix does not regress multi-subject/component
    awareness (§10): the two subjects' own connected components are never
    conflated by a forced decision, even while both are being force
    -decided on the same ticks. Measures and asserts every fact §18 asks
    for: logical Visit-group count, maximum admitted-episode lifetime,
    duplicate count, and evidence retention -- an invariant (bounded,
    non-starving, non-contaminating), never an assumed precise count."""
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    feeder_box = (0.47, 0.58, 0.51, 0.63)
    perch_box = (0.05, 0.05, 0.15, 0.15)  # far corner: never geometry-compatible with the feeder
    spacing_ms = 5_000
    tracklet_duration_ms = 1_000
    tick_every_ms = 60_000
    total_simulated_ms = 105 * 60_000  # >100 simulated minutes, per brief §18

    def _updates_and_evidence(generation_id: str, start_ms: int, box: tuple[float, float, float, float]):
        end_ms = start_ms + tracklet_duration_ms
        updates = (
            TrackUpdate(
                track_id=f"{generation_id}-track", generation_id=generation_id,
                captured_at=NOW + timedelta(milliseconds=start_ms), status="started", lifecycle_state="confirmed",
                frame_id=f"frame-{generation_id}-start", source_offset_ms=start_ms, broad_class="animal",
                bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-start",),
                support_state="weak_detector_supported", detector_ran=True,
            ),
            TrackUpdate(
                track_id=f"{generation_id}-track", generation_id=generation_id,
                captured_at=NOW + timedelta(milliseconds=end_ms), status="ended", lifecycle_state="ended",
                frame_id=f"frame-{generation_id}-end", source_offset_ms=end_ms, broad_class="animal",
                bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-end",),
                support_state="weak_detector_supported", detector_ran=True,
                terminal_reason="maximum_unsupported_duration",
            ),
        )
        evidence, payload = _tick_evidence(generation_id, "high_resolution_burst", f"hash-{generation_id}")
        return updates, evidence, payload

    all_updates: list[TrackUpdate] = []
    all_evidence: list[EvidenceCandidate] = []
    burst_bytes_cache: dict[str, bytes] = {}  # deliberately unbounded -- isolates arbitration from cache capacity
    attempted_proposal_ids: set[str] = set()
    candidates_created_after_each_tick: list[int] = []

    index = 0
    next_start_ms = 0
    next_tick_at_ms = tick_every_ms
    started = time.monotonic()
    while next_start_ms + tracklet_duration_ms <= total_simulated_ms:
        # Subject A (feeder), every tick offset; Subject B (perch), offset by
        # half a spacing so the two are genuinely interleaved/simultaneous in
        # stream time, never accidentally sequential.
        updates_a, evidence_a, payload_a = _updates_and_evidence(f"gen-feeder-{index}", next_start_ms, feeder_box)
        updates_b, evidence_b, payload_b = _updates_and_evidence(
            f"gen-perch-{index}", next_start_ms + spacing_ms // 2, perch_box,
        )
        all_updates.extend(updates_a)
        all_updates.extend(updates_b)
        all_evidence.append(evidence_a)
        all_evidence.append(evidence_b)
        burst_bytes_cache[evidence_a.media_asset_id] = payload_a
        burst_bytes_cache[evidence_b.media_asset_id] = payload_b
        index += 1

        known_horizon_ms = next_start_ms + spacing_ms // 2 + tracklet_duration_ms
        if known_horizon_ms >= next_tick_at_ms:
            session._run_assembly_tick(
                all_track_updates=all_updates, all_evidence_candidates=all_evidence,
                attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache,
                adapter=adapter, known_horizon_ms=known_horizon_ms,
            )
            next_tick_at_ms += tick_every_ms
            candidates_created_after_each_tick.append(session._counts.candidates_created)
        next_start_ms += spacing_ms
    elapsed_seconds = time.monotonic() - started

    # --- Non-starvation: bounded admission happened, well before the end ---
    assert max(candidates_created_after_each_tick) > 0
    first_admission_tick = next(i for i, c in enumerate(candidates_created_after_each_tick) if c > 0)
    assert (first_admission_tick + 1) <= 25, "first admission must land near the ~20-minute horizon, not the end"

    import json as _json

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]

    # --- Measured facts (brief §18): report, never force an exact count ---
    logical_visit_groups = len(created_rows)
    max_episode_lifetime_ms = max((row.end_offset_ms - row.start_offset_ms for row in created_rows), default=0)
    proposal_ids_seen = [row.proposal_id for row in created_rows]
    duplicate_count = len(proposal_ids_seen) - len(set(proposal_ids_seen))

    assert logical_visit_groups > 0
    # Bounded, not starved and not exploded: ~105 min / a ~20-25-min horizon,
    # times two independently-decided subjects -- comfortably under both a
    # "zero" floor and a "hundreds of tiny duplicate Visits" ceiling.
    assert logical_visit_groups <= 20, f"expected a bounded Visit-group count, got {logical_visit_groups}"
    # No giant infinite episode: every admitted candidate's own span is
    # bounded by the same `maximum_episode_duration_ms` this milestone
    # reuses as the forced-decision horizon (a little slack for the
    # coarse, 60s tick cadence this test itself uses).
    assert max_episode_lifetime_ms <= engine_runtime._MAXIMUM_COMPONENT_PENDING_MS + tick_every_ms
    assert duplicate_count == 0

    # --- No cross-subject contamination under forced decisions (brief §10) ---
    for row in created_rows:
        generation_ids = _json.loads(row.constituent_generation_ids_json)
        assert generation_ids, "a created candidate must have real constituent lineage"
        prefixes = {gen_id.rsplit("-", 1)[0] for gen_id in generation_ids}
        assert prefixes in ({"gen-feeder"}, {"gen-perch"}), (
            f"candidate {row.proposal_id} mixed subjects across a forced decision: {generation_ids}"
        )
    subjects_represented = {
        "gen-feeder" if _json.loads(row.constituent_generation_ids_json)[0].startswith("gen-feeder") else "gen-perch"
        for row in created_rows
    }
    assert subjects_represented == {"gen-feeder", "gen-perch"}, (
        f"expected both simultaneously-active subjects to be independently admitted, got {subjects_represented}"
    )

    # --- Evidence retention: every created candidate kept real, byte-backed
    # evidence (never an empty/unsupported Visit) ---
    for row in created_rows:
        assert _json.loads(row.persisted_media_asset_ids_json), (
            f"candidate {row.proposal_id} has no persisted evidence"
        )

    # --- Performance guard (brief §19) ---
    assert elapsed_seconds < 90.0, f"105-minute two-subject simulated replay took {elapsed_seconds:.1f}s of real time"


# =============================================================================
# Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness
# v1: the v6-shaped long-run replay (brief §7/§22). The stress test
# immediately above already proves multi-subject/forced-decision correctness
# against a deliberately *unbounded* local cache -- isolating arbitration
# from cache-capacity concerns, exactly as its own docstring says. This one
# restores the one dimension that isolation deliberately removed: the REAL,
# bounded 128-entry evidence-byte cache, with real eviction pressure and real
# protection, over the same >100-simulated-minute, two-simultaneous-subject
# shape -- approximating Representative Daylight Gate A Field Acceptance v6
# itself (long sustained activity, hundreds of proposals, natural component
# resolution, evidence churn, real viable proposals later in the component).
# =============================================================================


def test_v6_shaped_replay_does_not_lose_viable_activity_to_cache_exhaustion(
    repository: ProductRepository,
) -> None:
    """Pre-fix (RED on accepted `b37656d`): the real, bounded, insertion
    -order-only 128-entry cache, churned by two simultaneously-active
    subjects over a long run, evicts a real, resolved arbitration winner's
    own evidence before its own (correctly, if belatedly, computed)
    admission attempt ever runs -- the precise v6 mechanism -- permanently
    losing real, viable activity with no fallback and no protection.
    Post-fix (GREEN): bounded, non-zero, non-duplicated Visit admission
    from both subjects survives real cache pressure. Never an exact
    asserted Visit count (brief §7's own explicit instruction) -- only the
    core invariant this whole milestone exists to prove: real viable
    activity is not permanently lost merely because one arbitration
    member's own bytes expired first."""
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    feeder_box = (0.47, 0.58, 0.51, 0.63)
    perch_box = (0.05, 0.05, 0.15, 0.15)
    spacing_ms = 5_000
    tracklet_duration_ms = 1_000
    tick_every_ms = 60_000
    total_simulated_ms = 105 * 60_000

    def _updates_and_evidence(generation_id: str, start_ms: int, box: tuple[float, float, float, float]):
        end_ms = start_ms + tracklet_duration_ms
        updates = (
            TrackUpdate(
                track_id=f"{generation_id}-track", generation_id=generation_id,
                captured_at=NOW + timedelta(milliseconds=start_ms), status="started", lifecycle_state="confirmed",
                frame_id=f"frame-{generation_id}-start", source_offset_ms=start_ms, broad_class="animal",
                bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-start",),
                support_state="weak_detector_supported", detector_ran=True,
            ),
            TrackUpdate(
                track_id=f"{generation_id}-track", generation_id=generation_id,
                captured_at=NOW + timedelta(milliseconds=end_ms), status="ended", lifecycle_state="ended",
                frame_id=f"frame-{generation_id}-end", source_offset_ms=end_ms, broad_class="animal",
                bounding_box=box, supporting_frame_ids=(f"frame-{generation_id}-end",),
                support_state="weak_detector_supported", detector_ran=True,
                terminal_reason="maximum_unsupported_duration",
            ),
        )
        evidence, payload = _tick_evidence(generation_id, "high_resolution_burst", f"hash-{generation_id}")
        return updates, evidence, payload

    all_updates: list[TrackUpdate] = []
    all_evidence: list[EvidenceCandidate] = []
    burst_bytes_cache: dict[str, bytes] = {}  # the REAL bounded cache, not an unbounded test double
    attempted_proposal_ids: set[str] = set()
    protected_evidence_ids: set[str] = set()
    candidates_created_after_each_tick: list[int] = []
    max_cache_size = 0
    max_protected_size = 0

    index = 0
    next_start_ms = 0
    next_tick_at_ms = tick_every_ms
    started = time.monotonic()
    while next_start_ms + tracklet_duration_ms <= total_simulated_ms:
        updates_a, evidence_a, payload_a = _updates_and_evidence(f"gen-feeder-{index}", next_start_ms, feeder_box)
        updates_b, evidence_b, payload_b = _updates_and_evidence(
            f"gen-perch-{index}", next_start_ms + spacing_ms // 2, perch_box,
        )
        all_updates.extend(updates_a)
        all_updates.extend(updates_b)
        all_evidence.append(evidence_a)
        all_evidence.append(evidence_b)
        # Real bounded eviction with real protection, matching
        # `engine_runtime._harvest_burst_bytes` exactly -- the one thing the
        # stress test above deliberately does not do.
        for evidence, payload in ((evidence_a, payload_a), (evidence_b, payload_b)):
            burst_bytes_cache[evidence.media_asset_id] = payload
            while len(burst_bytes_cache) > engine_runtime._MAX_CACHED_BURST_BYTES:
                burst_bytes_cache.pop(
                    engine_runtime._select_eviction_victim(burst_bytes_cache, protected_evidence_ids)
                )
        max_cache_size = max(max_cache_size, len(burst_bytes_cache))
        index += 1

        known_horizon_ms = next_start_ms + spacing_ms // 2 + tracklet_duration_ms
        if known_horizon_ms >= next_tick_at_ms:
            session._run_assembly_tick(
                all_track_updates=all_updates, all_evidence_candidates=all_evidence,
                attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache,
                adapter=adapter, known_horizon_ms=known_horizon_ms, protected_evidence_ids=protected_evidence_ids,
            )
            max_protected_size = max(max_protected_size, len(protected_evidence_ids))
            next_tick_at_ms += tick_every_ms
            candidates_created_after_each_tick.append(session._counts.candidates_created)
        next_start_ms += spacing_ms
    elapsed_seconds = time.monotonic() - started

    # --- Core invariant: real activity is not permanently lost ---
    assert max(candidates_created_after_each_tick) > 0, (
        f"real, sustained, multi-subject activity under real cache pressure produced zero admissions -- "
        f"suppressed={session._suppressed}; fallback_attempted={session._fallback_attempted_count}; "
        f"fallback_admitted={session._fallback_admitted_count}; fallback_exhausted={session._fallback_exhausted_count}"
    )

    import json as _json

    from mockingbird.repository.product_repository import ObservationCandidateVisitModel

    with repository.session_factory() as db_session:
        created_rows = [
            row for row in (
                db_session.get(ObservationCandidateVisitModel, proposal_id)
                for proposal_id in attempted_proposal_ids
            )
            if row is not None
        ]

    # --- Bounded, not exploded; no duplicates (brief §16) ---
    logical_visit_groups = len(created_rows)
    assert 0 < logical_visit_groups <= 20, f"expected a bounded Visit-group count, got {logical_visit_groups}"
    proposal_ids_seen = [row.proposal_id for row in created_rows]
    assert len(proposal_ids_seen) == len(set(proposal_ids_seen))

    # --- No cross-subject contamination, even via fallback (brief §17) ---
    for row in created_rows:
        generation_ids = _json.loads(row.constituent_generation_ids_json)
        prefixes = {gen_id.rsplit("-", 1)[0] for gen_id in generation_ids}
        assert prefixes in ({"gen-feeder"}, {"gen-perch"}), (
            f"candidate {row.proposal_id} mixed subjects: {generation_ids}"
        )
        assert _json.loads(row.persisted_media_asset_ids_json), f"candidate {row.proposal_id} has no persisted evidence"

    # --- Cache/protection bounds (brief §18/§26): always bounded, never
    # growing without limit regardless of how long the run continues ---
    assert max_cache_size <= engine_runtime._MAX_CACHED_BURST_BYTES
    assert max_protected_size <= engine_runtime._MAX_PROTECTED_EVIDENCE_IDS

    # --- Diagnostics (brief §19): report what actually happened, whatever
    # it was -- this replay does not assert fallback *must* have fired
    # (whether it does depends on the exact churn/timing this synthetic
    # shape produces), only that whatever happened is internally consistent
    # and bounded. ---
    assert session._fallback_admitted_count <= session._fallback_attempted_count
    assert (session._fallback_attempted_count - session._fallback_admitted_count) == session._fallback_exhausted_count

    # --- Performance guard (brief §26/§19) ---
    assert elapsed_seconds < 90.0, f"105-minute v6-shaped replay took {elapsed_seconds:.1f}s of real time"


def test_forced_decision_winner_survives_the_real_bounded_evidence_cache(repository: ProductRepository) -> None:
    """Direct, deterministic reproduction of a real defect this milestone's
    own investigation found and fixed (see "Selection-priority and
    generation-scope fixes" in docs/candidate-visit-authority-contract.md):
    the 128-entry evidence-byte cache was field-validated against delays of
    tens of seconds to a few minutes, not the tens-of-minutes delay a
    forced decision can now legitimately produce. A single ~26-minute
    continuous encounter (one real, uniform, merge-eligible tracklet
    sequence -- the same shape `_drive_sustained_activity` above uses, but
    against the REAL, bounded `_MAX_CACHED_BURST_BYTES` cache instead of an
    unbounded local one) forces a decision on its own pre-split (older)
    chain, whose own earliest evidence is, by construction, the very first
    ever inserted into the cache -- guaranteed evicted by the time 26
    minutes' worth of real evidence-candidate insertions have occurred.
    Before the three fixes this reproduces together (forced-decision
    recency preference, byte-availability-preferring truncation, and
    multi-generation `track_generation_id` scope), this proposal correctly
    won arbitration but still reached `blocked_missing_evidence`, silently
    discarding a real, evidence-backed encounter -- the identical "zero
    Visits" symptom the starvation fix itself closes, recurring one gate
    later. After all three, it reaches `create`."""
    session, adapter = _sustained_activity_tick_session(repository)

    spacing_ms = 5_000
    tracklet_duration_ms = 1_000
    tick_every_ms = 60_000
    total_simulated_ms = 26 * 60_000

    all_updates: list[TrackUpdate] = []
    all_evidence: list[EvidenceCandidate] = []
    burst_bytes_cache: dict[str, bytes] = {}  # the REAL bounded cache, not an unbounded test double
    attempted_proposal_ids: set[str] = set()

    generation_index = 0
    next_start_ms = 0
    next_tick_at_ms = tick_every_ms
    while next_start_ms + tracklet_duration_ms <= total_simulated_ms:
        generation_id = f"gen-sustained-{generation_index}"
        generation_index += 1
        all_updates.extend(_tick_track_updates(generation_id, next_start_ms, next_start_ms + tracklet_duration_ms))
        evidence, payload = _tick_evidence(generation_id, "high_resolution_burst", f"hash-{generation_id}")
        all_evidence.append(evidence)
        burst_bytes_cache[evidence.media_asset_id] = payload
        # Real bounded eviction, matching `engine_runtime._harvest_burst_bytes`
        # exactly -- this is the one thing `_drive_sustained_activity`'s own
        # local cache deliberately does NOT do, to isolate the
        # arbitration/authority mechanism from this separate concern.
        while len(burst_bytes_cache) > engine_runtime._MAX_CACHED_BURST_BYTES:
            burst_bytes_cache.pop(next(iter(burst_bytes_cache)))

        known_horizon_ms = next_start_ms + tracklet_duration_ms
        if known_horizon_ms >= next_tick_at_ms:
            session._run_assembly_tick(
                all_track_updates=all_updates, all_evidence_candidates=all_evidence,
                attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache,
                adapter=adapter, known_horizon_ms=known_horizon_ms,
            )
            next_tick_at_ms += tick_every_ms
        next_start_ms += spacing_ms

    assert session._counts.candidates_created == 1, (
        f"expected the forced-decision winner to survive the real bounded evidence cache; "
        f"suppressed={session._suppressed}"
    )
    assert "blocked_missing_evidence" not in session._suppressed


# =============================================================================
# Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: evidence-
# cache capacity. Real, evidenced 2026-08-19 field defect: reconstructing
# the two missed strong encounters (~5.0min/34-generation/0.889-confidence
# and ~8.67min/40-generation/0.846-confidence) against the real captured
# counterfactual ledger found that in both clusters, the proposal that
# actually escaped `blocked_ambiguous_boundary` (either never ambiguous, or
# an arbitration winner) still permanently failed at evidence admission
# (`reject_no_identification_or_context`) -- not because no evidence was
# ever captured, but because `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_
# SAME_FRAME_BYTES` (previously 8) is a session-global cache evicted purely
# by insertion count, with no awareness of which pending proposal still
# needs which bytes. A proposal legitimately delayed by ambiguous-boundary/
# continuation-pending resolution (which can span the full `ambiguous_gap_
# ms`, 45s, or longer for a still-growing cluster) can easily have its own
# already-captured evidence evicted by unrelated activity elsewhere in a
# busy real stream before its own delayed admission attempt ever runs. See
# "Why the evidence-admission-escaping winner has no usable evidence" in
# docs/candidate-visit-authority-contract.md.
# =============================================================================


def test_evidence_cache_bound_has_real_headroom_over_the_old_undersized_default() -> None:
    """Not a magic-number regression alone: this pins the *reasoning*, not
    just a value -- the bound must comfortably exceed the old, demonstrated-
    insufficient default (8) by a real margin, for both the burst and
    same-frame caches (the identical mechanism, same reasoning, on the
    identical timing pressure)."""

    assert engine_runtime._MAX_CACHED_BURST_BYTES >= 24
    assert engine_runtime._MAX_CACHED_SAME_FRAME_BYTES >= 24


def test_delayed_proposal_still_finds_its_evidence_after_unrelated_cache_churn(
    repository: ProductRepository,
) -> None:
    """Direct reproduction of the real defect's own mechanism: a proposal's
    evidence is captured and harvested while still `blocked_continuation_
    pending` (a legitimate, real delay -- not a bug in itself, see the
    Visit Continuity tests above); while it waits, unrelated activity
    elsewhere in the stream captures more bursts than the *old* 8-slot cache
    could hold; once the proposal's own continuation window finally closes,
    its own already-captured evidence must still be there."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    subject_updates = list(_tick_track_updates("gen-subject", 0, 1_000))
    subject_evidence, subject_bytes = _tick_evidence("gen-subject", "high_resolution_burst", "hash-subject")
    burst_bytes_cache: dict[str, bytes] = {}
    attempted_proposal_ids: set[str] = set()

    # Tick 1: still inside the continuation window -- correctly deferred,
    # never permanently attempted. This is the exact real moment a live
    # session's own `_harvest_burst_bytes` would have already copied this
    # subject's evidence into the shared cache.
    burst_bytes_cache[subject_evidence.media_asset_id] = subject_bytes
    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=1_100,
    )
    assert session._counts.candidates_created == 0
    assert attempted_proposal_ids == set()
    assert session._suppressed.get("blocked_continuation_pending") == 1

    # Meanwhile: unrelated real activity elsewhere in the stream keeps
    # capturing bursts, cycling the shared cache exactly the way
    # `_harvest_burst_bytes` already does live -- more than the old 8-slot
    # bound, fewer than the new one, so this test discriminates the fix.
    for index in range(20):
        candidate, payload = _tick_evidence(
            f"gen-unrelated-{index}", "high_resolution_burst", f"hash-unrelated-{index}",
        )
        burst_bytes_cache[candidate.media_asset_id] = payload
        while len(burst_bytes_cache) > engine_runtime._MAX_CACHED_BURST_BYTES:
            burst_bytes_cache.pop(next(iter(burst_bytes_cache)))

    # Tick 2: the continuation window has now closed (finalize=True, the
    # real session-end shape, but an equally-real mid-session horizon tick
    # past the window would behave identically) -- the subject's own
    # already-captured evidence must still be retrievable.
    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert "reject_no_identification_or_context" not in session._suppressed
    assert "blocked_missing_evidence" not in session._suppressed


# =============================================================================
# Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness
# v1: RED reproducer A (see the milestone's own governing brief §6). The test
# immediately above already proves the *raw* 128-entry bound survives a
# realistic amount of unrelated churn (20 insertions). This section proves
# the fix is genuinely lifecycle-aware *preservation*, not merely a bigger
# number: churn well past 128 -- more than any single generous bump the
# milestone's own brief would accept -- still must not evict a proposal that
# is legitimately still pending, because that proposal's own priority
# evidence is now explicitly protected while it waits, not merely lucky to
# still be near the front of an oversized queue.
# =============================================================================


def test_pending_component_preserves_minimum_viable_evidence_under_cache_pressure(
    repository: ProductRepository,
) -> None:
    """RED on accepted `b37656d`: a proposal that is legitimately still
    pending (`blocked_continuation_pending` -- a real, honest delay, never
    a bug) loses its own already-captured evidence the moment *unrelated*
    activity elsewhere in the same session churns the shared, bounded
    128-entry evidence-byte cache past its own numeric capacity while it
    waits -- eviction is purely insertion-order, with zero awareness of
    which pending proposal still needs which bytes, so 200 unrelated
    insertions guarantee this proposal's own real evidence (inserted
    first) is long gone by the time its continuation window finally
    closes. This is proven through the exact real eviction policy
    (`_select_eviction_victim`, the same function `_harvest_burst_bytes`
    calls live) -- never by deleting bytes directly after the fact.

    GREEN after this fix: `_run_assembly_tick`'s own `protected_evidence_
    ids` parameter marks this proposal's own priority evidence as
    still-actionable every tick it remains pending, so the real eviction
    policy skips it in favor of the (truly disposable) unrelated churn --
    surviving even 200 unrelated insertions, comfortably more than *any*
    single numeric bump this milestone's own governing brief would accept
    in place of a real fix (see "Do not just increase 128")."""
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    subject_updates = list(_tick_track_updates("gen-subject", 0, 1_000))
    subject_evidence, subject_bytes = _tick_evidence("gen-subject", "high_resolution_burst", "hash-subject")
    burst_bytes_cache: dict[str, bytes] = {}
    attempted_proposal_ids: set[str] = set()
    protected_evidence_ids: set[str] = set()

    # Tick 1: still inside the continuation window -- correctly deferred,
    # never permanently attempted. This is the exact real moment a live
    # session's own `_harvest_burst_bytes` would already have copied this
    # subject's evidence into the shared cache, and the exact moment this
    # tick's own protection computation must mark it as still-actionable.
    burst_bytes_cache[subject_evidence.media_asset_id] = subject_bytes
    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=1_100, protected_evidence_ids=protected_evidence_ids,
    )
    assert session._counts.candidates_created == 0
    assert attempted_proposal_ids == set()
    assert session._suppressed.get("blocked_continuation_pending") == 1
    assert subject_evidence.media_asset_id in protected_evidence_ids, (
        "the still-pending proposal's own priority evidence must be protected the moment it is known pending"
    )

    # Meanwhile: unrelated real activity elsewhere in the stream keeps
    # capturing bursts -- 200 insertions, not merely the 20 the test above
    # uses, deliberately past the raw 128-entry bound many times over --
    # through the real eviction policy, exactly as `_harvest_burst_bytes`
    # calls it live.
    for index in range(200):
        candidate, payload = _tick_evidence(
            f"gen-unrelated-{index}", "high_resolution_burst", f"hash-unrelated-{index}",
        )
        burst_bytes_cache[candidate.media_asset_id] = payload
        while len(burst_bytes_cache) > engine_runtime._MAX_CACHED_BURST_BYTES:
            burst_bytes_cache.pop(engine_runtime._select_eviction_victim(burst_bytes_cache, protected_evidence_ids))

    assert subject_evidence.media_asset_id in burst_bytes_cache, (
        "the pending proposal's own protected evidence must survive unrelated churn that would otherwise "
        "exceed the raw 128-entry bound many times over"
    )
    # The cache itself never grew past its own bound to accomplish this --
    # protection changes *which* entry is evicted, never *whether* one is.
    assert len(burst_bytes_cache) == engine_runtime._MAX_CACHED_BURST_BYTES

    # Tick 2: the continuation window has now closed -- the subject's own
    # already-captured evidence must still be retrievable.
    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        finalize=True, protected_evidence_ids=protected_evidence_ids,
    )
    assert session._counts.candidates_created == 1
    assert "reject_no_identification_or_context" not in session._suppressed
    assert "blocked_missing_evidence" not in session._suppressed
    # Resolution/release timing (protection is recomputed at the *start* of
    # each tick, so a proposal resolved by *this* tick's own attempt loop is
    # still reflected as protected in this same call's own snapshot) is
    # covered precisely by the dedicated release test below -- this test's
    # own scope is survival under pressure, not release timing.


def test_protection_releases_automatically_once_a_proposal_is_permanently_blocked(
    repository: ProductRepository,
) -> None:
    """No leak after a proposal becomes permanently *ineligible* either
    (never resolved into a Visit at all): once a proposal is durably
    resolved -- created, or permanently blocked -- it drops out of the very
    next tick's own protected set with no separate release step, exactly
    like the created case above."""
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    # No `source_capture_frame_ids`/`supporting_frame_ids` at all -- fails
    # gate 4 (`blocked_invalid_lineage`), a permanent, non-retryable outcome,
    # deliberately chosen so protection release can be observed on an
    # *ordinary* tick rather than only at `finalize=True`.
    updates = list(_tick_track_updates("gen-invalid-lineage", 0, 1_000))
    updates = tuple(replace(update, supporting_frame_ids=()) for update in updates)
    evidence, payload = _tick_evidence("gen-invalid-lineage", "high_resolution_burst", "hash-invalid-lineage")
    burst_bytes_cache = {evidence.media_asset_id: payload}
    attempted_proposal_ids: set[str] = set()
    protected_evidence_ids: set[str] = set()

    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=45_100, protected_evidence_ids=protected_evidence_ids,
    )
    assert session._suppressed.get("blocked_invalid_lineage") == 1
    assert len(attempted_proposal_ids) == 1
    # Protection is recomputed at the *start* of every tick, so this same
    # tick's own snapshot still reflects the proposal as protected -- it
    # was still-actionable when this call began. The next tick, with
    # nothing else changed, is what actually proves release: `attempted_
    # proposal_ids` already names this proposal permanently resolved
    # before protection is (re)computed this time.
    assert evidence.media_asset_id in protected_evidence_ids

    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=45_200, protected_evidence_ids=protected_evidence_ids,
    )
    assert protected_evidence_ids == set(), "a permanently-resolved (even if blocked) proposal must not stay protected"


def _pending_proposal_with_evidence(
    index: int, *, adapter: CandidateVisitAuthorityAdapter,
) -> tuple[AssembledVisitProposal, EvidenceCandidate, bytes]:
    """One independently-constructed, still-pending proposal plus its own
    single real evidence candidate/bytes -- bypasses `build_tracklets`/
    `assemble_visit_episodes` entirely (unlike every other test in this
    file) so `test_protected_capacity_is_bounded_and_degrades_
    deterministically` can drive `_compute_protected_evidence_ids` directly
    with an exact, controlled number of genuinely simultaneous pending
    proposals -- constructing this many truly-simultaneous, mutually-
    non-ambiguous proposals through the real assembler would require
    either widely-separated (and therefore *not* simultaneously pending)
    or geometrically-adjacent (and therefore merged/ambiguous, collapsing
    back to a handful of proposals) tracklets; this helper isolates the
    one unit under test (the bounding/degradation policy itself) from
    that unrelated assembly concern, the same way `test_candidate_visit_
    authority.py`'s own `_arbitration_proposal` helper isolates arbitration
    from assembly."""
    generation_id = f"gen-pending-{index}"
    evidence, payload = _tick_evidence(generation_id, "high_resolution_burst", f"hash-pending-{index}")
    proposal = AssembledVisitProposal(
        proposal_id=f"visit-episode:pending-{index}",
        stream_id=STREAM_ID,
        broad_class="animal",
        start_offset_ms=index * 1_000,
        end_offset_ms=index * 1_000 + 500,
        constituent_generation_ids=(generation_id,),
        constituent_track_ids=(f"{generation_id}-track",),
        supporting_frame_ids=(f"frame-{generation_id}-start",),
        source_capture_frame_ids=(),
        evidence_candidate_ids=(evidence.media_asset_id,),
        assembly_decisions=(),
        continuation_pending=True,
    )
    return proposal, evidence, payload


def test_protected_capacity_is_bounded_and_degrades_deterministically(
    repository: ProductRepository,
) -> None:
    """Cache bounds (brief §18): a pathological number of *simultaneously*
    pending proposals must not make the protected set itself unbounded --
    `_MAX_PROTECTED_EVIDENCE_IDS` caps the total, and exceeding it is
    diagnosed (a returned `capacity_exhausted` flag; see `_EngineSession.
    _protected_evidence_capacity_exhausted_count` for the live counter this
    same fact feeds), never a silent, unbounded grant. Direct unit test of
    `_compute_protected_evidence_ids` itself (see `_pending_proposal_with_
    evidence`'s own docstring for why): the oldest pending proposals -- the
    ones genuinely at risk of eviction -- are protected first; the newest
    simply receive no *additional* protection this round, which is safe
    precisely because their own evidence is, by construction, also the
    cache's own most recent insertion."""
    adapter = _tick_adapter(repository)

    # 80 independent, simultaneously-pending proposals, each with exactly
    # one evidence candidate of its own (so each can contribute at most one
    # id to the protected set) -- still comfortably more than `_MAX_
    # PROTECTED_EVIDENCE_IDS` (64), so exhaustion is guaranteed regardless
    # of how many ids any single proposal's own priority preview picks.
    built = [_pending_proposal_with_evidence(index, adapter=adapter) for index in range(80)]
    proposals = tuple(item[0] for item in built)
    candidates_by_id = {item[1].media_asset_id: item[1] for item in built}
    media_lookup = {item[1].media_asset_id: item[2] for item in built}

    protected, capacity_exhausted = engine_runtime._compute_protected_evidence_ids(
        proposals, attempted_proposal_ids=set(), candidates_by_id=candidates_by_id,
        media_lookup=media_lookup, adapter=adapter,
    )
    assert len(protected) <= engine_runtime._MAX_PROTECTED_EVIDENCE_IDS
    assert capacity_exhausted is True

    # The *oldest* pending proposal's own evidence is protected -- it is the
    # one actually at risk (its own `start_offset_ms` is earliest, so
    # `_compute_protected_evidence_ids`'s own oldest-first processing order
    # reaches it before the budget could possibly already be exhausted).
    assert built[0][1].media_asset_id in protected


def test_delayed_proposal_survives_a_busier_real_session_shape_than_the_32_bound_covers(
    repository: ProductRepository,
) -> None:
    """End-to-End Bird Encounter Recall Closure v1: a real, evidenced
    2026-08-19 field defect -- a busier real session than the one that
    motivated the 8->32 fix still exhausted the 32-entry bound. Direct
    reconstruction of the real failure shape from that session's own live
    counterfactual ledger (`GET .../observation/counterfactual`, queried
    after Stop): a genuine 149.6s, 6-generation, 0.816-max-confidence
    encounter (six `maximum_unsupported_duration`/`maximum_duration`
    generations at stable feeder-perch geometry -- one real, mostly-
    stationary bird, not six separate subjects) was legitimately deferred
    `blocked_continuation_pending` across 5 real assembly ticks spanning
    183.5 real seconds (22:26:09Z first attempt to 22:29:12Z final
    decision) before permanently failing `reject_no_identification_or_
    context` -- despite 22 detections including 6 strong (>=0.70) hits in
    its own penultimate generation. This session's own measured evidence-
    candidate rate (1336 over 5512s, ~0.242/s) projected across that same
    183.5s real delay is ~44 candidates -- comfortably past the 32 bound,
    comfortably under a 128 bound. A second, independent real case in the
    same session (30.3s, single-generation, 0.815 max confidence, 12
    strong detections, only a ~34s delay) reached `blocked_missing_
    evidence` even faster, confirming this is not a one-off."""

    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW, fresh_session=True,
    )
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    subject_updates = list(_tick_track_updates("gen-subject", 0, 1_000))
    subject_evidence, subject_bytes = _tick_evidence("gen-subject", "high_resolution_burst", "hash-subject")
    burst_bytes_cache: dict[str, bytes] = {}
    attempted_proposal_ids: set[str] = set()

    burst_bytes_cache[subject_evidence.media_asset_id] = subject_bytes
    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=1_100,
    )
    assert session._counts.candidates_created == 0
    assert session._suppressed.get("blocked_continuation_pending") == 1

    # ~44 unrelated real-shaped burst insertions -- this session's own
    # measured 0.242 evidence-candidates/second rate projected across the
    # real 183.5s delay this exact proposal was actually subjected to (see
    # docstring). Deliberately real-measured, not a round number picked to
    # make the test pass.
    for index in range(44):
        candidate, payload = _tick_evidence(
            f"gen-unrelated-{index}", "high_resolution_burst", f"hash-unrelated-{index}",
        )
        burst_bytes_cache[candidate.media_asset_id] = payload
        while len(burst_bytes_cache) > engine_runtime._MAX_CACHED_BURST_BYTES:
            burst_bytes_cache.pop(next(iter(burst_bytes_cache)))

    session._run_assembly_tick(
        all_track_updates=subject_updates, all_evidence_candidates=[subject_evidence],
        attempted_proposal_ids=attempted_proposal_ids, burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        finalize=True,
    )
    assert session._counts.candidates_created == 1
    assert "reject_no_identification_or_context" not in session._suppressed
    assert "blocked_missing_evidence" not in session._suppressed


# =============================================================================
# Rejected / Suppressed Detection Attribution v1 (see
# docs/rejected-detection-attribution-contract.md): every admission outcome
# -- not only a bare `_suppressed[reason] += 1` count -- is now retained
# with full, reconstructable lineage in `session._counterfactual`, queryable
# through `session.counterfactual_query`/`ObservationEngineSessionManager.
# counterfactual_query`. These tests drive the real `_run_assembly_tick`
# code path directly, mirroring the Visit Continuity tests immediately
# above.
# =============================================================================


def test_run_assembly_tick_records_full_lineage_for_a_created_candidate(repository: ProductRepository) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    updates = list(_tick_track_updates("gen-solo", 0, 1_000))
    evidence_a, bytes_a = _tick_evidence("gen-solo", "high_resolution_burst", "hash-solo-a")
    evidence_b, bytes_b = _tick_evidence("gen-solo", "context", "hash-solo-b")
    burst_bytes_cache = {evidence_a.media_asset_id: bytes_a, evidence_b.media_asset_id: bytes_b}

    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[evidence_a, evidence_b],
        attempted_proposal_ids=set(), burst_bytes_cache=burst_bytes_cache, adapter=adapter,
        known_horizon_ms=1_100, finalize=True,
    )
    assert session._counts.candidates_created == 1

    window = session.counterfactual_query(start_offset_ms=0, end_offset_ms=1_000)
    assert len(window.proposal_outcomes) == 1
    outcome = window.proposal_outcomes[0]
    assert outcome.outcome == "created"
    assert outcome.admitted is True
    assert outcome.constituent_generation_ids == ("gen-solo",)
    assert outcome.visit_id == session._last_candidate_visit_id


def test_suppressed_proposal_creates_no_visit_but_retains_exact_lineage(repository: ProductRepository) -> None:
    """The exact real shape `_suppressed` alone already counted
    (`blocked_missing_evidence`): no burst evidence ever became available,
    so authority never even reaches the quality gate. Proves both halves of
    the truth boundary at once: nothing about this attempt is visible as a
    Visit/Event/ReviewLabel, and the *reason* the counterfactual ledger
    retains is the real repository-level outcome code, not a guess."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    from sqlalchemy import func, select

    from mockingbird.repository.product_repository import EventModel, ReviewLabelModel

    with repository.session_factory() as db_session:
        # The fixture repository seeds demo data (including a demo
        # ReviewLabel) by default -- compare before/after rather than an
        # absolute total, matching `test_end_to_end_suppresses_insufficient_
        # evidence_without_creating_a_visit`'s own established convention.
        review_labels_before = db_session.scalar(select(func.count(ReviewLabelModel.id)))

    updates = list(_tick_track_updates("gen-no-evidence", 0, 1_000))

    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[],
        attempted_proposal_ids=set(), burst_bytes_cache={}, adapter=adapter,
        known_horizon_ms=1_100, finalize=True,
    )
    assert session._counts.candidates_created == 0
    assert session._suppressed.get("blocked_missing_evidence") == 1

    window = session.counterfactual_query(start_offset_ms=0, end_offset_ms=1_000)
    assert len(window.proposal_outcomes) == 1
    outcome = window.proposal_outcomes[0]
    assert outcome.outcome == "blocked_missing_evidence"
    assert outcome.reason == "no_persistable_evidence_bytes"
    assert outcome.admitted is False
    assert outcome.visit_id is None

    with repository.session_factory() as db_session:
        candidate_events = db_session.scalar(
            select(func.count(EventModel.id)).where(EventModel.event_type == "observation_engine_candidate")
        )
        assert candidate_events == 0
        review_labels_after = db_session.scalar(select(func.count(ReviewLabelModel.id)))
        assert review_labels_after == review_labels_before


def test_counterfactual_query_advertises_bounded_eviction_accounting_in_status(
    repository: ProductRepository,
) -> None:
    """The existing advanced-diagnostics status surface also gets a
    lightweight, always-fresh eviction summary -- no query parameters
    needed for the at-a-glance case."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)
    updates = list(_tick_track_updates("gen-solo", 0, 1_000))
    session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[], attempted_proposal_ids=set(),
        burst_bytes_cache={}, adapter=adapter, known_horizon_ms=1_100, finalize=True,
    )

    status = session.snapshot()
    ledger_summary = status.advanced["counterfactual_ledger"]
    assert ledger_summary["proposal_outcomes"]["retained_count"] == 1
    assert ledger_summary["proposal_outcomes"]["evicted_count"] == 0


def test_a_fresh_session_never_mixes_counterfactual_records_with_a_prior_one(
    repository: ProductRepository,
) -> None:
    """Session reset/restart safety (Rejected / Suppressed Detection
    Attribution v1): `ObservationEngineSessionManager.start` always
    constructs a brand-new `_EngineSession`, so a brand-new
    `CounterfactualLedger` is structurally guaranteed too -- proven directly
    here rather than only inferred from that construction."""

    first_session = _tick_session(repository)
    adapter = _tick_adapter(repository)
    updates = list(_tick_track_updates("gen-first-session", 0, 1_000))
    first_session._run_assembly_tick(
        all_track_updates=updates, all_evidence_candidates=[], attempted_proposal_ids=set(),
        burst_bytes_cache={}, adapter=adapter, known_horizon_ms=1_100, finalize=True,
    )
    first_window = first_session.counterfactual_query(start_offset_ms=0, end_offset_ms=1_000)
    assert len(first_window.proposal_outcomes) == 1

    # A second Start for the identical Stream -- exactly what
    # `ObservationEngineSessionManager.start` does after a prior session
    # has stopped -- must begin with a completely empty ledger.
    second_session = _tick_session(repository)
    second_window = second_session.counterfactual_query(start_offset_ms=0, end_offset_ms=1_000)
    assert second_window.proposal_outcomes == ()
    assert second_window.track_generations == ()
    assert second_window.coverage.session_first_offset_ms is None

    # The first session's own records remain intact and unaffected.
    first_window_again = first_session.counterfactual_query(start_offset_ms=0, end_offset_ms=1_000)
    assert first_window_again == first_window


# =============================================================================
# Observation Engine Session-Renewal Continuity v1 (see docs/observation
# -session-renewal-continuity-contract.md and the real 2026-08-16 field
# defect: the underlying Camera Node session/transport can renew/reconnect
# normally, but the pre-fix outer loop treated any `session.run()`
# interruption -- raised, or a batch that completed with zero frames -- as
# unconditionally fatal, so a normal, bounded renewal silently and
# permanently stopped Observation until a human noticed and pressed Start
# again. Root-caused precisely: `mockingbird_node.app.analysis_parts`
# already tolerates sustained `camera_busy` contention across a whole
# ~10-second analysis-stream batch by ending that one batch cleanly with
# zero frames (see its own `test_analysis_stream_ends_cleanly_when_camera_
# never_recovers`, whose docstring explicitly assumes "the client's
# existing reconnect logic can take over") -- but no such logic existed at
# this outer layer before this fix.
# =============================================================================


class _RenewingTransport(_FixtureTransport):
    """Simulates one or more bounded Camera Node analysis-stream
    interruptions -- the real Observation Engine Session-Renewal Continuity
    v1 shape (see `engine_runtime.AnalysisStreamRetryPolicy`) -- interleaved
    with real frame batches, all under the *same* `provider_generation` (a
    genuine bounded renewal never changes Node/Stream/camera identity by
    itself -- see docs/reconnect-continuity-contract.md's own "three
    separate concepts"). `script` is consumed in order, one entry per
    `iter_analysis_frames` call:

    - a positive int N: yield N further real frames from this transport's
      own running sequence counter (same paced shape as `_FixtureTransport`
      itself, just repeatable across many calls instead of a single batch).
    - `"empty"`: return zero frames, no error -- the dominant real shape
      proven server-side in `mockingbird_node.app.analysis_parts`: an
      entire batch lost to sustained `camera_busy` contention (e.g. a
      concurrent evidence-burst-triggered warm-profile teardown/rebuild
      that legitimately outlasts one ~10-second analysis-stream batch).
    - `"raise"`: raise `CameraNodeClientError("analysis_stream_unavailable")`
      -- a bounded, recoverable transport-level interruption.
    - `"auth"`: raise `CameraNodeClientError("authentication_rejected")` --
      the one genuinely terminal condition this fixture can produce.

    Once `script` is exhausted, every further call raises the same terminal
    `"auth"` condition `_FixtureTransport` itself now uses, so a test that
    never explicitly stops still converges deterministically.
    """

    def __init__(self, script: list[object], *, generation: str = "generation-a") -> None:
        super().__init__(frame_count=0)
        self._script = list(script)
        self._generation = generation
        self._next_sequence = 1
        self.calls = 0

    def iter_analysis_frames(self, *, maximum_frames: int):
        self.calls += 1
        outcome = self._script.pop(0) if self._script else "auth"
        if outcome == "raise":
            raise CameraNodeClientError("analysis_stream_unavailable")
        if outcome == "auth":
            raise CameraNodeClientError("authentication_rejected")
        if outcome == "empty":
            return iter(())
        return self._yield_frames(int(outcome))

    def _yield_frames(self, count: int):
        # Same real-network-time pacing rationale as `_FixtureTransport.
        # _paced_frames` -- yielding instantly would let the source queue
        # coalesce away most frames before the consumer ever wakes.
        for _ in range(count):
            envelope = _envelope(self._next_sequence, generation=self._generation)
            self._next_sequence += 1
            time.sleep(0.06)
            yield envelope


def _fast_retry_policy(**overrides: object) -> engine_runtime.AnalysisStreamRetryPolicy:
    values: dict[str, object] = dict(maximum_consecutive_failures=6, backoff_seconds=0.01)
    values.update(overrides)
    return engine_runtime.AnalysisStreamRetryPolicy(**values)


def test_bounded_transport_error_recovers_without_stopping_or_duplicating_the_visit(
    repository: ProductRepository,
) -> None:
    """The exact real field defect: two bounded, recoverable `session.run()`
    errors before any frame of a real encounter ever arrives must not stop
    Observation, and the one real encounter spanning them must still yield
    exactly one candidate Visit -- never zero (Observation gave up), never
    two (the renewal was mistaken for a new encounter)."""

    transport = _RenewingTransport(["raise", "raise", 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    # The script's own eventual terminal fallback (`"auth"`) converges the
    # session on its own, forcing the immediate `finalize=True` tick exactly
    # like every other end-to-end fixture in this module -- never a real
    # wait on the slow 10-second periodic tick.
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.counts.candidates_created == 1
    assert final.last_candidate_visit_id is not None
    # The two `"raise"` batches were genuinely retried and recovered --
    # never treated as fatal -- before the real encounter's own 4 frames
    # ever arrived.
    assert final.advanced.get("analysis_stream_reconnect_recoveries") == 1
    assert transport.calls == 4  # 2 failed + 1 successful (4 frames) + 1 terminal fallback
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_reconnect_recovery_is_logged_alongside_the_existing_counter(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """First-Hour Onboarding + Whole-Product Observability Closure v1 ("B4
    structured logging" -- reconnect attempts): additive only -- the
    in-memory `analysis_stream_reconnect_recoveries` counter the test above
    already covers is unchanged; this proves the new log line fires
    alongside it, reusing that same real two-failure-then-recover
    transport fixture."""

    logged: list[dict] = []
    monkeypatch.setattr(
        engine_runtime,
        "log_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    transport = _RenewingTransport(["raise", "raise", 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    reconnect_events = [entry for entry in logged if entry["event"] == "reconnect_recovered"]
    assert len(reconnect_events) == 1
    assert reconnect_events[0]["component"] == "camera_node"
    assert reconnect_events[0]["stream_id"] == STREAM_ID
    assert reconnect_events[0]["consecutive_failures_before_recovery"] == 2


def test_empty_batch_interruption_recovers_without_stopping_observation(
    repository: ProductRepository,
) -> None:
    """The dominant *real* shape (see this section's own header comment):
    `session.run()` completing with zero frames and no exception at all --
    proven server-side to mean "an entire batch was lost to sustained
    camera_busy contention," not "the stream is permanently over." Must
    recover exactly like the raised-exception shape `test_bounded_
    transport_error_recovers_without_stopping_or_duplicating_the_visit`
    already proves."""

    transport = _RenewingTransport(["empty", "empty", 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.counts.candidates_created == 1
    assert final.advanced.get("analysis_stream_reconnect_recoveries") == 1
    assert transport.calls == 4


def test_repeated_bounded_renewals_all_recover_one_encounter_one_visit(
    repository: ProductRepository,
) -> None:
    """Multiple separate renewal episodes across one session -- a mix of
    both real shapes (raised and empty) -- must each recover independently,
    and the one continuous real encounter spanning all of them must still
    yield exactly one candidate Visit."""

    transport = _RenewingTransport(
        ["raise", "empty", 1, "raise", "raise", "empty", 1, "empty", 2],
        generation="generation-a",
    )
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.counts.candidates_created == 1
    assert final.advanced.get("analysis_stream_reconnect_recoveries") == 3


def test_user_stop_during_reconnect_backoff_is_prompt(repository: ProductRepository) -> None:
    """An explicit Stop mid-backoff must not wait out the full backoff
    window -- `_await_transport_retry` uses `Event.wait`, which returns the
    instant `_stop_event` is set, mirroring `session.run()`'s own
    `available.wait` pattern for the identical reason."""

    class _AlwaysFailingTransport(_FixtureTransport):
        def iter_analysis_frames(self, *, maximum_frames: int):
            raise CameraNodeClientError("analysis_stream_unavailable")

    policy = _fast_retry_policy(maximum_consecutive_failures=30, backoff_seconds=5.0)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _AlwaysFailingTransport(),
        analysis_stream_retry_policy=policy,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(
        lambda: (manager.status(STREAM_ID).advanced.get("analysis_stream_consecutive_failures") or 0) >= 1,
        timeout=5.0,
    )

    started = time.monotonic()
    status = manager.stop(STREAM_ID)
    elapsed = time.monotonic() - started

    assert status is not None
    assert status.state == "stopped"
    assert elapsed < 3.0  # well under the 5-second backoff -- Stop cut the wait short
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_permanently_unavailable_camera_eventually_terminates_within_the_bound(
    repository: ProductRepository,
) -> None:
    """A recoverable-shaped failure that never once recovers must still end
    the session -- "persistent provider failure after bounded recovery" is
    terminal, exhausting the exact bounded budget, never fewer attempts
    (giving up too early) and never more (an unbounded busy retry loop)."""

    class _AlwaysFailingTransport(_FixtureTransport):
        def __init__(self) -> None:
            super().__init__(frame_count=0)
            self.calls = 0

        def iter_analysis_frames(self, *, maximum_frames: int):
            self.calls += 1
            raise CameraNodeClientError("analysis_stream_unavailable")

    transport = _AlwaysFailingTransport()
    policy = _fast_retry_policy(maximum_consecutive_failures=4)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=policy,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.stopped_reason == "camera_unavailable"
    assert final.camera_connected is False
    assert transport.calls == policy.maximum_consecutive_failures
    assert final.advanced.get("analysis_stream_consecutive_failures") == policy.maximum_consecutive_failures
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_teardown_failure_after_retry_exhaustion_preserves_the_diagnosed_reason_and_still_cleans_up(
    repository: ProductRepository,
) -> None:
    """Camera Node Connectivity & Recovery Diagnosis v1: the exact real
    2026-08-20 field incident shape (proven independently, at the real
    provider's own boundary, in `test_observation_onnx_cuda.py`) --
    `finalize_replay()` can raise during teardown after a session's bounded
    reconnect budget exhausts with zero frames ever received. Before this
    fix, that teardown exception (1) overwrote the already-correct
    `"Camera Node connection stopped: analysis_stream_unavailable."` message
    with a bare, misleading CUDA-flavored string, and (2) skipped the
    finalize assembly tick and `provider.close()` entirely -- a resource
    leak: a fresh Start looked externally clean but the prior session's
    detector was never released."""

    class _AlwaysFailingTransport(_FixtureTransport):
        def __init__(self) -> None:
            super().__init__(frame_count=0)
            self.calls = 0

        def iter_analysis_frames(self, *, maximum_frames: int):
            self.calls += 1
            raise CameraNodeClientError("analysis_stream_unavailable")

    transport = _AlwaysFailingTransport()
    teardown_error = ValueError("onnx_cuda_verification_insufficient")
    provider, detector = _teardown_failing_provider(error=teardown_error)
    policy = _fast_retry_policy(maximum_consecutive_failures=4)
    manager = _manager(
        repository,
        provider_loader=lambda path: (provider, detector),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=policy,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    # The already-diagnosed connectivity reason survives -- never clobbered
    # by the secondary teardown-time exception.
    assert final.stopped_reason == "camera_unavailable"
    assert "analysis_stream_unavailable" in final.camera_message
    assert "onnx_cuda_verification_insufficient" not in final.camera_message
    # The teardown exception is still recorded, just as auxiliary detail.
    assert final.advanced.get("analysis_stream_teardown_error") == "onnx_cuda_verification_insufficient"
    # Cleanup still ran despite the exception: finalize was attempted
    # exactly once, and `provider.close()` (-> `detector.close()`) was not
    # skipped.
    assert detector.finalize_replay_calls == 1
    assert detector.close_calls == 1
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_teardown_failure_with_no_prior_camera_diagnosis_is_still_reported_honestly(
    repository: ProductRepository,
) -> None:
    """Regression guard for the fix above: a genuine teardown-time failure
    with no prior camera-connectivity diagnosis -- for example real CUDA
    mixed-execution discovered only at Stop -- must still become the
    primary camera-facing reason exactly as it always has. The fix only
    protects an *already-diagnosed* connectivity reason; it must not start
    silently swallowing a genuinely new problem, and must not widen
    `stopped_reason` beyond what this module already sets it to."""

    teardown_error = ValueError("onnx_cuda_mixed_execution")
    provider, detector = _teardown_failing_provider(error=teardown_error)
    manager = _manager(
        repository,
        provider_loader=lambda path: (provider, detector),
        transport_factory=lambda config, stream_id: _FixtureTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=5.0)

    status = manager.stop(STREAM_ID)

    assert status is not None
    assert status.state == "stopped"
    assert status.camera_message == "onnx_cuda_mixed_execution"
    # `stopped_reason` stays exactly what the ordinary user-stop path
    # already set -- the fix never widens it to "camera_unavailable" for a
    # problem that has nothing to do with camera connectivity.
    assert status.stopped_reason == "user_stopped"
    assert detector.finalize_replay_calls == 1
    assert detector.close_calls == 1


def test_analysis_stream_failure_class_is_surfaced_for_diagnosis(repository: ProductRepository) -> None:
    """Camera Node Connectivity & Recovery Diagnosis v1 (Section 10): the
    real 2026-08-20 field incident could not distinguish connection-refused
    from timed-out from a bad HTTP response using only the host-side API --
    `analysis_stream_unavailable` collapsed every one of them into one
    opaque string. `CameraNodeClientError.failure_class`, when the raising
    site provides one (see `camera_node_live._classify_analysis_stream_
    transport_error`), must reach `advanced` diagnostics without changing
    the primary retry-controlling `code` any existing check matches."""

    class _RefusedTransport(_FixtureTransport):
        def __init__(self) -> None:
            super().__init__(frame_count=0)

        def iter_analysis_frames(self, *, maximum_frames: int):
            raise CameraNodeClientError("analysis_stream_unavailable", failure_class="connect_refused")

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _RefusedTransport(),
        analysis_stream_retry_policy=_fast_retry_policy(maximum_consecutive_failures=2),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.advanced.get("analysis_stream_failure_class") == "connect_refused"
    assert "analysis_stream_unavailable" in final.camera_message


def test_node_identity_pairing_failure_remains_immediately_terminal(
    repository: ProductRepository,
) -> None:
    """A `CameraNodeClientError("authentication_rejected")` -- the "node
    identity/pairing invalid" terminal category -- must never be retried,
    even once: retrying a rejected credential only delays the honest
    terminal status the user actually needs to see and act on (re-pair)."""

    class _RejectedCredentialTransport(_FixtureTransport):
        def __init__(self) -> None:
            super().__init__(frame_count=0)
            self.calls = 0

        def iter_analysis_frames(self, *, maximum_frames: int):
            self.calls += 1
            raise CameraNodeClientError("authentication_rejected")

    transport = _RejectedCredentialTransport()
    # A long backoff/high attempt budget -- if the terminal classification
    # were not checked first, this test would time out well before 5s.
    policy = _fast_retry_policy(maximum_consecutive_failures=10, backoff_seconds=5.0)
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=policy,
    )

    started = time.monotonic()
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=5.0)
    elapsed = time.monotonic() - started

    assert transport.calls == 1
    assert elapsed < 3.0
    final = manager.status(STREAM_ID)
    assert final.stopped_reason == "camera_unavailable"
    assert "authentication_rejected" in final.camera_message
    # Never entered the bounded-retry bookkeeping at all -- a genuinely
    # different code path from the recoverable one.
    assert final.advanced.get("analysis_stream_consecutive_failures") is None
    assert repository.get_observation_authority_state(stream_id=STREAM_ID).mode == "shadow"


def test_reconnect_retry_policy_validates_its_own_bounds() -> None:
    """Mirrors `ReconnectBridgeConfig.__post_init__`'s own bounded-and-
    validated convention -- an out-of-range policy must never silently
    become an effectively-unbounded or effectively-instant retry loop."""

    with pytest.raises(ValueError):
        engine_runtime.AnalysisStreamRetryPolicy(maximum_consecutive_failures=0)
    with pytest.raises(ValueError):
        engine_runtime.AnalysisStreamRetryPolicy(backoff_seconds=-1.0)


def test_default_retry_policy_budget_covers_a_real_measured_pi_reboot() -> None:
    """Regression guard for the real defect Camera Node Installer v1 found:
    a genuinely unreachable Node (a device mid-reboot, not merely degraded)
    fails each attempt in about a second rather than a full batch timeout,
    so the *effective* worst-case budget is dominated by
    `backoff_seconds` alone, not by the batch-duration assumption the old
    2.0s default was implicitly sized against. A real reboot of the
    reference Pi 4 measured ~55s to become healthy again; at the old
    default the host gave up after only ~38s. This asserts the *default*
    policy (the one every real session actually uses -- `_EngineSession`/
    `ObservationEngineSessionManager` both fall back to
    `AnalysisStreamRetryPolicy()` with no arguments) budgets comfortably
    past that real measurement even in the worst case of a connection that
    fails instantly on every attempt, so this exact regression -- a future
    edit quietly shrinking `backoff_seconds` again -- fails a fast, offline
    test rather than only being caught on the next real device reboot. See
    "backoff_seconds raised from 2.0 to 12.0" in
    docs/observation-session-renewal-continuity-contract.md."""

    policy = engine_runtime.AnalysisStreamRetryPolicy()
    measured_real_pi4_reboot_recovery_seconds = 55.2
    worst_case_budget_seconds = policy.maximum_consecutive_failures * policy.backoff_seconds
    assert worst_case_budget_seconds > measured_real_pi4_reboot_recovery_seconds
    # Still strictly bounded -- never widened into an effectively-unbounded
    # retry loop merely as insurance.
    assert worst_case_budget_seconds < 180.0


# =============================================================================
# Today Coverage Truth v1 (see docs/todays-coverage-truth-contract.md):
# lifecycle integration between `_EngineSession` and durable
# `MonitoringExposureIntervalModel` history -- the fact `ProductRepository.
# place_activity_report`'s coverage figure reads. Complements the pure
# ledger-level tests in tests/test_monitoring_exposure_history.py with the
# real session lifecycle (healthy run, user Stop, recoverable reconnect,
# terminal failure) that actually drives those two repository calls.
#
# `_FakeClock` is this section's own test-only override of `_EngineSession
# .clock` (mirroring `DurableMonitoringSupervisor`'s own established `clock`
# parameter): every checkpoint/close call in this loop is already only ever
# compared to *itself* (`now == healthy_at` at checkpoint time -- see
# `_checkpoint_monitoring_exposure_interval`), so durable exposure's
# bounded-cadence checkpoint bump (45s) and zero-length-interval discard
# (`test_zero_length_interval_is_not_preserved...`) both depend on genuine
# elapsed time *between* separate calls, not on how fast this fixture's own
# frames are paced. Jumping 90 simulated seconds per call lets a fast,
# millisecond-scale test still produce the same real, positive-duration,
# correctly-checkpointed interval a real multi-minute session would.
# =============================================================================


class _FakeClock:
    """Deterministic, monotonically-advancing clock: returns `start` on the
    first call, then jumps forward by `step` (default 90s -- comfortably
    past `DURABLE_EXPOSURE_CHECKPOINT_INTERVAL`'s 45s) on every subsequent
    call. Never depends on real wall-clock time, so a test asserting on
    exact recorded timestamps stays fully deterministic."""

    def __init__(self, start: datetime, *, step: timedelta = timedelta(seconds=90)) -> None:
        self._next = start
        self._step = step

    def __call__(self) -> datetime:
        value = self._next
        self._next = self._next + self._step
        return value


def test_healthy_observation_session_records_monitoring_exposure_with_no_legacy_state(
    repository: ProductRepository,
) -> None:
    """The core "no longer depends on the legacy supervisor" proof at the
    session-lifecycle level: this Stream is never enabled for legacy
    monitoring, yet a real, correctly-attributed durable exposure interval
    -- spanning two real checkpointed batches -- is still recorded."""

    assert repository.list_enabled_monitoring_candidates(limit=10) == []
    transport = _RenewingTransport([4, 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    intervals = _intervals(repository, STREAM_ID)
    assert len(intervals) == 1
    interval = intervals[0]
    assert interval.stream_id == STREAM_ID
    assert interval.source_id == "source-backyard-demo"
    assert _utc(interval.started_at) == NOW
    assert interval.ended_at is not None
    assert _utc(interval.ended_at) == NOW + timedelta(seconds=90)
    # The script's own exhaustion falls back to a terminal rejection -- a
    # real provider failure, not a clean stop.
    assert interval.close_reason == "provider_failure"
    assert interval.runtime_generation_id

    assert repository.list_enabled_monitoring_candidates(limit=10) == []


def test_coverage_checkpoint_failure_is_logged_without_corrupting_exposure_history(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-Freeze Operability Gap Closure v1 ("A3 coverage-accounting
    failures"): disclosed as absent-of-any-durable-evidence in
    docs/observability-error-taxonomy-contract.md. `_checkpoint_observation_
    exposure`'s own except block already swallowed this failure
    unconditionally before this change ("exposure accounting must never be
    able to break live analysis") -- this proves the new structured record
    fires, *and* that no partial/fabricated `MonitoringExposureInterval`
    row is ever left behind: every checkpoint attempt in this run fails, so
    the honest outcome is zero rows, never a corrupt one."""

    logged: list[dict] = []
    monkeypatch.setattr(
        engine_runtime,
        "log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated coverage-accounting write failure")

    monkeypatch.setattr(repository, "record_observation_exposure_frame", _raise)

    transport = _RenewingTransport([4, 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    # The session still runs to its own normal completion -- a coverage-
    # accounting bug must never itself break live analysis.
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    checkpoint_events = [entry for entry in logged if entry["event"] == "coverage_checkpoint_failed"]
    assert len(checkpoint_events) >= 1
    assert checkpoint_events[0]["component"] == "observation_engine"
    assert checkpoint_events[0]["code"] == "storage_write_failed"
    assert checkpoint_events[0]["stream_id"] == STREAM_ID
    assert "exception" in checkpoint_events[0]

    # No corruption: every write attempt failed, so no interval was ever
    # created -- never a partial/fabricated row standing in for real
    # coverage evidence.
    assert _intervals(repository, STREAM_ID) == []


def test_close_exposure_failure_is_logged_and_swallowed(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sibling of the checkpoint-failure test above for the session-stop
    path (`_close_observation_exposure`'s own except block): additive
    only -- Stop must still complete cleanly even when the durable close
    write itself fails."""

    logged: list[dict] = []
    monkeypatch.setattr(
        engine_runtime,
        "log_error_event",
        lambda component, event, **fields: logged.append({"component": component, "event": event, **fields}),
    )

    def _raise(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated coverage-accounting close failure")

    monkeypatch.setattr(repository, "close_observation_exposure", _raise)

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)

    status = manager.stop(STREAM_ID)
    assert status is not None
    assert status.state == "stopped"

    close_events = [entry for entry in logged if entry["event"] == "coverage_exposure_close_failed"]
    assert len(close_events) == 1
    assert close_events[0]["component"] == "observation_engine"
    assert close_events[0]["code"] == "storage_write_failed"
    assert close_events[0]["stream_id"] == STREAM_ID


def test_user_stop_closes_monitoring_exposure_interval_as_session_stopped(
    repository: ProductRepository,
) -> None:
    def _has_multi_checkpoint_interval() -> bool:
        rows = _intervals(repository, STREAM_ID)
        return bool(rows) and _utc(rows[0].last_confirmed_fresh_at) > _utc(rows[0].started_at)

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _SlowIndefiniteTransport(),
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "observing", timeout=10.0)
    # Let at least two real checkpoints land -- a positive-duration open
    # interval -- before Stop is requested.
    assert _wait_until(_has_multi_checkpoint_interval, timeout=10.0)

    status = manager.stop(STREAM_ID)
    assert status is not None
    assert status.state == "stopped"

    intervals = _intervals(repository, STREAM_ID)
    assert len(intervals) == 1
    interval = intervals[0]
    assert interval.close_reason == "session_stopped"
    assert interval.ended_at is not None
    assert _utc(interval.started_at) < _utc(interval.ended_at)


def test_recoverable_reconnect_does_not_fragment_or_prematurely_close_monitoring_exposure(
    repository: ProductRepository,
) -> None:
    """The exact Observation Engine Session-Renewal Continuity v1 shape
    (`_RenewingTransport`, mirroring `test_bounded_transport_error_
    recovers_without_stopping_or_duplicating_the_visit` above): two bounded,
    recoverable interruptions before real frames arrive must never close or
    fragment this session's own coverage interval -- exactly as `_state`/
    `observing` are never touched during a bounded reconnect
    (docs/observation-session-renewal-continuity-contract.md), coverage
    must not regress that guarantee either."""

    transport = _RenewingTransport(["raise", "raise", 4, 4], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(),
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.advanced.get("analysis_stream_reconnect_recoveries") == 1

    intervals = _intervals(repository, STREAM_ID)
    assert len(intervals) == 1  # never fragmented by the two recoverable interruptions
    assert intervals[0].close_reason == "provider_failure"  # the fixture's own eventual terminal end
    assert _utc(intervals[0].started_at) < _utc(intervals[0].ended_at)


def test_terminal_retry_exhaustion_closes_monitoring_exposure_as_provider_failure(
    repository: ProductRepository,
) -> None:
    """A recoverable-shaped interruption that never once recovers still
    honestly closes coverage once the bounded retry budget is exhausted --
    "genuine terminal camera failure should stop or gap coverage
    honestly," not leave a stale open interval."""

    transport = _RenewingTransport([4, 4, "raise", "raise", "raise"], generation="generation-a")
    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: transport,
        analysis_stream_retry_policy=_fast_retry_policy(maximum_consecutive_failures=3),
        clock=_FakeClock(NOW),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    final = manager.status(STREAM_ID)
    assert final.stopped_reason == "camera_unavailable"

    intervals = _intervals(repository, STREAM_ID)
    assert len(intervals) == 1
    assert intervals[0].close_reason == "provider_failure"
    assert intervals[0].ended_at is not None
    assert _utc(intervals[0].started_at) < _utc(intervals[0].ended_at)


def test_immediately_terminal_failure_before_any_frame_records_no_exposure(
    repository: ProductRepository,
) -> None:
    """Mirrors `test_node_identity_pairing_failure_remains_immediately_
    terminal`: zero real frames were ever received, so durable exposure
    history -- which begins only on a Stream's first fresh monitoring frame
    -- must never open an interval at all, not even a zero-length one."""

    class _RejectedCredentialTransport(_FixtureTransport):
        def iter_analysis_frames(self, *, maximum_frames: int):
            raise CameraNodeClientError("authentication_rejected")

    manager = _manager(
        repository,
        provider_loader=lambda path: _fixture_provider(),
        transport_factory=lambda config, stream_id: _RejectedCredentialTransport(),
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    assert manager.status(STREAM_ID).stopped_reason == "camera_unavailable"
    assert _intervals(repository, STREAM_ID) == []


def test_idle_configured_stream_never_started_records_no_exposure(
    repository: ProductRepository,
) -> None:
    """A Stream fully configured for Observation Engine (`_camera_node_
    config`, a real paired Camera Node) but never actually started must
    contribute nothing to durable exposure history -- a configured-but-idle
    camera is never counted as coverage."""

    assert _intervals(repository, STREAM_ID) == []


# =============================================================================
# Harvested Evidence Issuance / Missing-Evidence Closure v1: a real, distinct
# defect from the evidence-cache-capacity section above, found while
# investigating the 2026-08-20 field session's own 4 real-bird
# `blocked_missing_evidence` cases that showed only 8-22% of the 128-entry
# cache's own capacity in use during their delay window -- too low for that
# cache's own eviction to plausibly explain them (see
# docs/cache-128-live-daylight-acceptance-v1-report.md §7). Root cause:
# `LiveCameraNodeShadowSession._temporary_payloads`/`_same_frame_temporary_
# payloads` (camera_node_live.py) are each their OWN small, fixed,
# content-hash-keyed cache -- capped at 8, entirely independent of
# `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES` above -- and were
# only ever harvested into this module's own longer-lived caches once per
# whole `session.run()` *batch* (`for result in results: _harvest_burst_
# bytes(...)`, reached only after the entire up-to-`_BATCH_FRAMES`-frame
# batch had already returned). A batch busy enough for more than 8 *separate*
# frames to each successfully capture a burst -- several concurrent
# generations, or several distinct subjects in sequence, well within one
# real ~20-frame batch -- silently evicted an early capture from that small
# cache before the old harvest loop ever got to copy it out, so a proposal
# could legitimately reach admission with its own evidence already captured
# and already lost, long before the much larger, properly-sized cache this
# module owns ever had a chance to hold it. Fixed by harvesting immediately,
# per frame, via `LiveCameraNodeShadowSession.run`'s new `on_result`
# callback -- not by enlarging any cache. See "Evidence-cache capacity" in
# docs/candidate-visit-authority-contract.md.
# =============================================================================


class _ManyGenerationsProvider:
    """Fake Observation Engine provider giving one exact, hand-scripted pair
    of `TrackUpdate`s per `frame_id` -- deliberately sidesteps real tracker
    matching/expiry internals so this test can precisely control how many
    *separate* track generations each successfully capture evidence within
    one `session.run()` batch, which is exactly the real mechanism under
    test below. Mirrors `_FakeSameFrameProvider` in
    tests/test_observation_camera_node_live.py, the established pattern for
    this exact kind of precise-control fixture."""

    provider_id = "fixture-many-generations"

    def __init__(self, updates_by_frame_id: dict[str, tuple[TrackUpdate, TrackUpdate]]) -> None:
        self._updates_by_frame_id = updates_by_frame_id
        self.settings = FrameDrivenSettings(
            source_nominal_fps=5, baseline_detector_fps=5, candidate_detector_fps=5,
            strong_detection_threshold=0.8, minimum_detector_confirmations=2,
            minimum_tracker_support_frames=1, maximum_missed_frames=2, maximum_frame_gap_ms=2000,
            tracker_expiry_ms=2000, maximum_track_duration_ms=30000, maximum_active_tracks=16,
            evidence_ring_size=4, pretrigger_frame_count=1,
        )
        self.live_reset_count = 0

    def start_live(self, stream_id: str) -> None:
        pass

    async def observe_live_frame(self, frame: FramePacket) -> ObservationResult:
        updates = self._updates_by_frame_id.get(frame.frame_id, ())
        return ObservationResult(
            "fixture-many-generations", "live_shadow", frame.stream_id, frame.captured_at,
            frame_packets=(frame,), track_updates=updates, detector_ran=True,
        )

    def stop_live(self, reason: str = "provider_reset") -> tuple[ObservationResult, ...]:
        return ()

    def close(self) -> None:
        pass


def _burst_trigger_updates(
    generation_id: str, frame_id: str, index: int,
) -> tuple[TrackUpdate, TrackUpdate]:
    """A `started`+`confirmed` update (the sole "meaningful" one -- it alone
    triggers exactly one burst opportunity) immediately followed by its own
    terminal `ended` update, both delivered on this generation's single
    triggering frame: a brief, single-instant sighting, exactly the real
    "single generation" shape several of the real field session's own
    `blocked_missing_evidence` cases share (see docs/cache-128-live-
    daylight-acceptance-v1-report.md §7, "Gens: 1"). Each generation is
    logically 60 real seconds apart from the next -- comfortably beyond
    both `merge_gap_ms` and `ambiguous_gap_ms` -- so `assemble_visit_
    episodes` treats every one as its own independent encounter rather than
    a continuation/ambiguity candidate; only this logical spacing matters,
    never real wall-clock test-execution time, which stays a fraction of a
    second regardless. Subject geometry also shifts per `index`: distinct
    enough (IoU/centroid) that the real, unmodified burst scheduler treats
    every generation as its own new recurrence group rather than a
    suppressed repeat of the same static geometry, which is not what this
    test is about."""

    offset = index * 0.05
    box = (0.05 + offset, 0.05 + offset, 0.12 + offset, 0.12 + offset)
    start_ms = index * 60_000
    # Deliberately a *different* id from the real envelope's own `frame_id`
    # (the dict key this update is registered under) -- not the same value.
    # `_process_frame`'s same-frame-capture eligibility requires `update.
    # frame_id == frame.frame_id` (proof the geometry and the pixels come
    # from the identical captured frame); every envelope in this test
    # shares one fixed, identical `payload` (see `_envelope`'s own
    # default), so if same-frame capture *were* eligible here, all 9
    # generations' same-frame candidates would collide on one identical
    # content hash and trivially "never evict" regardless of the real
    # defect -- masking the exact terminal reason this test exists to
    # prove. Mismatching the id keeps this test isolated to the
    # `high_resolution_burst` mechanism alone, which is what the real
    # field session's own `blocked_missing_evidence` cases actually are.
    unrelated_frame_id = f"{frame_id}-not-same-frame-eligible"
    started = TrackUpdate(
        track_id=f"{generation_id}-track", generation_id=generation_id,
        captured_at=NOW + timedelta(milliseconds=start_ms), status="started",
        lifecycle_state="confirmed", frame_id=unrelated_frame_id, source_offset_ms=start_ms,
        broad_class="animal", bounding_box=box, confidence=0.9,
        supporting_frame_ids=(unrelated_frame_id,), support_state="weak_detector_supported", detector_ran=True,
    )
    ended = TrackUpdate(
        track_id=f"{generation_id}-track", generation_id=generation_id,
        captured_at=NOW + timedelta(milliseconds=start_ms + 40), status="ended",
        lifecycle_state="ended", frame_id=unrelated_frame_id, source_offset_ms=start_ms + 40,
        broad_class="animal", bounding_box=box, supporting_frame_ids=(unrelated_frame_id,),
        support_state="weak_detector_supported", detector_ran=True,
        terminal_reason="maximum_unsupported_duration",
    )
    return started, ended


def _distinct_burst_jpeg(index: int) -> bytes:
    """A genuinely distinct, real, decodable JPEG per capture -- large
    enough to clear the evidence scorer's own minimum-subject-size floor
    (see `HIGH_RESOLUTION_BURST_SIZE`'s own comment) -- mirroring how a
    real Camera Node always returns a genuinely distinct frame per burst,
    which matters here because `_temporary_payloads` is keyed by content
    hash: an identical payload on every request would silently collapse
    every capture onto one dict entry instead of exercising its real,
    insertion-count-based FIFO bound."""

    buffer = BytesIO()
    color = (index * 20 % 256, (index * 53) % 256, (index * 97) % 256)
    Image.new("RGB", HIGH_RESOLUTION_BURST_SIZE, color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


class _ManyGenerationsTransport:
    """Paced (never-instant) frame delivery -- see `_FixtureTransport.
    _paced_frames`'s own docstring for why real-time pacing, not an
    artificial coalescing workaround, is required for `session.run()` to
    actually process each of several distinct frames rather than
    coalescing all but the newest away. Ends deterministically the same way
    `_FixtureTransport` does: once every scripted frame has been served, the
    next call raises the one unambiguous terminal condition
    (`authentication_rejected`) rather than blocking forever."""

    def __init__(self, envelopes: list[AnalysisFrameEnvelope]) -> None:
        self._envelopes = envelopes
        self._served = False
        self.burst_requests: list[object] = []
        self.closed = False

    def iter_analysis_frames(self, *, maximum_frames: int):
        if self._served:
            raise CameraNodeClientError("authentication_rejected")
        self._served = True
        return self._paced_frames()

    def _paced_frames(self):
        for envelope in self._envelopes:
            time.sleep(0.06)
            yield envelope

    def request_evidence_burst(self, request):
        self.burst_requests.append(request)
        payload = _distinct_burst_jpeg(len(self.burst_requests))
        width, height = HIGH_RESOLUTION_BURST_SIZE
        frame = EvidenceBurstFrame(
            1, request.trigger_captured_at + timedelta(milliseconds=5), width, height, "image/jpeg",
            sha256(payload).hexdigest(), payload, request.trigger_frame_id, "generation-a", 5, "supported",
        )
        return EvidenceBurstResult(request.request_id, "captured", (frame,))

    def close(self) -> None:
        self.closed = True


def test_batch_internal_burst_capture_no_longer_starves_an_early_generations_evidence(
    repository: ProductRepository,
) -> None:
    """Direct reproduction, through the real, unmodified production path
    (`ObservationEngineSessionManager.start()` -> `_EngineSession._run_
    async` -> `LiveCameraNodeShadowSession.run()`), of the real 2026-08-20
    field defect: a real, confirmed, single-generation bird can reach
    terminal `blocked_missing_evidence` even though the outer 128-entry
    evidence cache is nowhere near full -- because its own already-captured
    evidence was lost one stage further upstream, inside the live session's
    own small internal cache, before this module's harvest ever ran.

    9 distinct, single-frame, real (fake-tracker-scripted) track generations
    land in one `session.run()` batch, each successfully capturing a burst.
    `gen-early` -- the first to capture -- is the one whose evidence the old,
    once-per-batch harvest lost to the other 8's later-in-the-same-batch
    captures; the other 8 are unaffected."""

    generation_count = 9
    generations = ["gen-early"] + [f"gen-unrelated-{i}" for i in range(generation_count - 1)]

    updates_by_frame_id: dict[str, tuple[TrackUpdate, TrackUpdate]] = {}
    envelopes: list[AnalysisFrameEnvelope] = []
    for index, generation_id in enumerate(generations):
        envelope = _envelope(index + 1)
        envelopes.append(envelope)
        updates_by_frame_id[envelope.frame_id] = _burst_trigger_updates(generation_id, envelope.frame_id, index)

    provider = _ManyGenerationsProvider(updates_by_frame_id)
    transport = _ManyGenerationsTransport(envelopes)
    manager = _manager(
        repository,
        provider_loader=lambda path: (provider, provider),
        transport_factory=lambda config, stream_id: transport,
    )
    manager.start(STREAM_ID, _camera_node_config())
    assert _wait_until(lambda: manager.status(STREAM_ID).state == "stopped", timeout=10.0)

    status = manager.status(STREAM_ID)
    # A real burst request happened for every one of the 9 generations,
    # `gen-early` included -- ruling out "the scheduler never issued a
    # request for it" as the cause of whatever its own outcome turns out
    # to be.
    assert len(transport.burst_requests) == generation_count

    suppressed = dict(status.counts.suppressed_reasons)
    # THE FIX: every generation's own evidence survives to admission --
    # `gen-early`'s included -- because harvesting no longer waits for the
    # whole batch to finish. Before the fix, `gen-early` alone reached
    # `blocked_missing_evidence` here despite `transport.burst_requests`
    # proving its evidence really was captured.
    assert "blocked_missing_evidence" not in suppressed
    assert status.counts.candidates_created == generation_count


# =============================================================================
# Boot Identity + Autonomous Recovery v1 (see docs/camera-node-installer
# -design.md): `_checkpoint_observation_exposure` reuses the exact existing
# ~45s-throttled exposure checkpoint to also durably record the Camera
# Node's boot identity, and surfaces a detected boot transition into
# `advanced` for the currently-running session -- "same node, fresh
# reboot," distinguishable from an ordinary benign reconnect (same
# boot_id).
# =============================================================================


def test_checkpoint_surfaces_a_detected_boot_transition_into_advanced(repository: ProductRepository) -> None:
    session = _tick_session(repository)
    first = datetime.now(UTC)
    session._checkpoint_observation_exposure(repository, healthy_at=first, node_boot_id="boot-A")
    assert "camera_node_fresh_boot_detected" not in session._advanced  # first observation is not a transition

    rebooted = first + timedelta(minutes=1)
    session._checkpoint_observation_exposure(repository, healthy_at=rebooted, node_boot_id="boot-B")
    assert session._advanced["camera_node_fresh_boot_detected"] is True
    assert session._advanced["camera_node_boot_transitions_this_session"] == 1

    # A benign reconnect back to the same already-known boot id must not
    # count as a second transition.
    reconnected = rebooted + timedelta(seconds=30)
    session._checkpoint_observation_exposure(repository, healthy_at=reconnected, node_boot_id="boot-B")
    assert session._advanced["camera_node_boot_transitions_this_session"] == 1


def test_checkpoint_without_a_boot_id_never_reports_a_transition(repository: ProductRepository) -> None:
    """An older Node (or a transport hop that omitted the header) reports
    no boot id at all -- this must never be misread as a transition."""

    session = _tick_session(repository)
    healthy_at = datetime.now(UTC)
    session._checkpoint_observation_exposure(repository, healthy_at=healthy_at)
    assert "camera_node_fresh_boot_detected" not in session._advanced
    assert "camera_node_boot_transitions_this_session" not in session._advanced


# =============================================================================
# Camera Node -> Host Clock Normalization v1 (see docs/camera-node-host
# -clock-normalization-latency-v1-report.md): a Camera Node session's own
# `_counterfactual` ledger is constructed to *expect* clock calibration
# (`clock_calibration_expected=True`); `_refresh_clock_calibration` drains
# whatever `(node_captured_at, host_received_at)` pairs the per-packet loop
# already buffered into one new calibration record per assembly tick. Only
# `_refresh_clock_calibration` and the buffer/ledger wiring are unit-tested
# here directly (matching this file's own established pattern for other
# small `_EngineSession` helpers, e.g. `_checkpoint_observation_exposure`
# immediately above) -- the per-packet buffering line itself is a trivial,
# already-covered-by-every-passing-test-in-this-file two-line guarded
# append inside the real `_run_async` loop, not independently re-tested.
# =============================================================================


def test_camera_node_session_ledger_expects_clock_calibration(repository: ProductRepository) -> None:
    session = _tick_session(repository)  # _camera_node_config() -- provider_key == "camera_node"
    assert session._counterfactual.clock_calibration_expected is True


def test_non_camera_node_session_ledger_never_expects_clock_calibration(repository: ProductRepository) -> None:
    session = engine_runtime._EngineSession(
        stream_id=STREAM_ID, playback_config=_non_camera_node_config(),
        provider_config_path=Path("unused-for-this-test"), privacy_ignore_regions=(),
        repository_factory=lambda: repository,
    )
    assert session._counterfactual.clock_calibration_expected is False
    # This source never populates `FramePacket.received_at` -- the buffer
    # stays empty for the lifetime of such a session, so a tick refresh is
    # always a safe no-op, never a spurious `insufficient_samples` record.
    session._refresh_clock_calibration(source_offset_ms=5_000)
    window = session._counterfactual.query(start_offset_ms=0, end_offset_ms=10_000)
    assert window.clock_calibrations == ()
    assert window.clock_calibration_required is False


def test_refresh_clock_calibration_records_a_calibration_from_buffered_camera_node_packets(
    repository: ProductRepository,
) -> None:
    session = _tick_session(repository)
    node_t0 = NOW
    session._clock_calibration_buffer.extend(
        (node_t0 + timedelta(milliseconds=i), node_t0 + timedelta(milliseconds=i + 2_000)) for i in range(5)
    )

    session._refresh_clock_calibration(source_offset_ms=5_000)

    assert session._clock_calibration_buffer == []  # drained, never left to double-count next tick
    window = session._counterfactual.query(start_offset_ms=0, end_offset_ms=10_000)
    assert len(window.clock_calibrations) == 1
    assert window.clock_calibration_required is True
    calibration = window.clock_calibrations[0]
    assert calibration.state == "calibrated"
    assert calibration.source_offset_ms == 5_000
    assert calibration.offset_ms == pytest.approx(2_000.0)
    assert calibration.clock_jump_detected is False


def test_refresh_clock_calibration_is_a_no_op_when_the_buffer_is_empty(repository: ProductRepository) -> None:
    """A tick where zero packets happened to arrive (or none carried
    `received_at`) must never append a spurious record."""
    session = _tick_session(repository)
    session._refresh_clock_calibration(source_offset_ms=1_000)
    window = session._counterfactual.query(start_offset_ms=0, end_offset_ms=2_000)
    assert window.clock_calibrations == ()


def test_refresh_clock_calibration_across_two_ticks_detects_a_clock_jump(repository: ProductRepository) -> None:
    session = _tick_session(repository)
    node_t0 = NOW
    session._clock_calibration_buffer.extend(
        (node_t0 + timedelta(milliseconds=i), node_t0 + timedelta(milliseconds=i + 100)) for i in range(5)
    )
    session._refresh_clock_calibration(source_offset_ms=0)

    jumped_base = node_t0 + timedelta(seconds=10)
    huge_offset_ms = 100 + 60_000  # far beyond DEFAULT_CLOCK_JUMP_THRESHOLD_MS
    session._clock_calibration_buffer.extend(
        (jumped_base + timedelta(milliseconds=i), jumped_base + timedelta(milliseconds=i + huge_offset_ms))
        for i in range(5)
    )
    session._refresh_clock_calibration(source_offset_ms=10_000)

    window = session._counterfactual.query(start_offset_ms=0, end_offset_ms=20_000)
    assert len(window.clock_calibrations) == 2
    assert window.clock_calibrations[0].clock_jump_detected is False
    assert window.clock_calibrations[1].clock_jump_detected is True
