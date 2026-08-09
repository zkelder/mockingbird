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
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import DetectionObservation, FramePacket
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
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig

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


def _wait_until(predicate, *, timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


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
    assert repository.get_observation_authority_state().mode == "shadow"


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
    assert repository.get_observation_authority_state().mode == "shadow"


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
            "authority_settings": session.scalar(select(func.count(ObservationAuthoritySettingsModel.singleton_id))),
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
    assert repository.get_observation_authority_state().mode == "shadow"


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

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, now=NOW)

    def _slow_loader(path: Path):
        time.sleep(0.3)
        raise ValueError("fixture_stop_race")

    manager = _manager(repository, provider_loader=_slow_loader)
    manager.start(STREAM_ID, _camera_node_config())
    status = manager.stop(STREAM_ID)
    assert status is not None
    assert status.state == "stopped"
    assert repository.get_observation_authority_state().mode == "shadow"


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


class _FixtureTransport:
    """Yields one real bounded batch of frames once, then an empty stream --
    a deterministic, natural end so the session loop exits on its own."""

    def __init__(self, frame_count: int = 4) -> None:
        self._frames = [_envelope(index) for index in range(1, frame_count + 1)]
        self._served = False
        self.burst_requests: list[object] = []
        self.closed = False
        self.payload = _jpeg_bytes()

    def iter_analysis_frames(self, *, maximum_frames: int):
        if self._served:
            return iter(())
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
    assert repository.get_observation_authority_state().mode == "shadow"


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
    assert repository.get_observation_authority_state().mode == "shadow"
    # A second status read after stop must stay stable (side-effect-free).
    assert manager.status(STREAM_ID).state == "stopped"
