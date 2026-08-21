"""App-owned Observation Engine lifecycle (Product requirement 1):
start/stop/status contract, kill switch, Camera Node unavailable state,
Privacy/Ignore preservation, and a full hardware-free end-to-end candidate
creation using fake transport/detector -- the real Camera Node/CUDA
construction (`_load_real_provider`/`_default_transport_factory`) is
intentionally never exercised here (see docs/candidate-visit-authority
-contract.md's own real-hardware trial for that).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
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


def test_ambiguous_boundary_arbitration_does_not_cascade_to_the_next_sibling(
    repository: ProductRepository,
) -> None:
    """Arbitration is single-shot, not a retry chain: if the single
    best-evidenced member of a stabilized ambiguous cluster fails a *later*
    gate (here, `blocked_missing_evidence` -- no persistable evidence bytes
    at all for the winner), the weaker sibling is not automatically
    promoted as a fallback. This is a deliberate, disclosed scope boundary
    (see "Ambiguous boundary arbitration" in docs/tracklet-visit-assembly
    -contract.md), not an oversight -- cascading arbitration would let
    progressively weaker evidence keep trying until *something* is
    admitted, which is exactly the "meaningless dark patch" the evidence
    -quality boundary exists to prevent."""
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    session = _tick_session(repository)
    adapter = _tick_adapter(repository)

    gen_strong, gen_weak = "gen-strong-no-evidence", "gen-weak-with-evidence"
    strong_updates = list(_tick_track_updates_with_confidence(gen_strong, 0, 5_000, confidence=0.9))
    weak_updates = list(_tick_track_updates_with_confidence(gen_weak, 25_000, 30_000, confidence=0.1))
    all_updates = strong_updates + weak_updates

    # Only the *weaker* generation has real, byte-backed evidence; the
    # stronger one's evidence candidate exists (so it is still a
    # structurally valid proposal) but no bytes are cached for it, so the
    # quality gate correctly rejects it once authority stops blocking it
    # on ambiguity alone.
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
    assert session._counts.candidates_created == 0
    assert len(attempted_proposal_ids) == 2
    assert session._suppressed.get("blocked_ambiguous_boundary") == 1  # the weaker sibling, unaffected
    assert session._suppressed.get("blocked_missing_evidence") == 1  # the winner, no evidence bytes -- not rescued


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
