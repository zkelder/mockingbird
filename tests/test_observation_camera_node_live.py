from __future__ import annotations

from datetime import UTC, datetime, timedelta
import asyncio
import hashlib
from io import BytesIO
import socket

import pytest
from fastapi import HTTPException

from mockingbird.observation.burst_scheduler import (
    DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED,
    DECISION_SUPPRESSED_RECURRING_GEOMETRY,
    DECISION_SUPPRESSED_SESSION_BUDGET,
    RESET_GENERATION_REPLACEMENT,
    RESET_REASONS,
    RESET_SESSION_STOP,
    BurstScheduler,
    BurstSchedulerConfig,
)
from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    LiveCameraNodeShadowSession,
    CameraNodeHttpTransport,
    _analysis_envelope,
    _classify_analysis_stream_transport_error,
    _jpeg_dimensions,
)
from mockingbird.observation.contracts import (
    CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
    DetectionObservation,
    FramePacket,
    ObservationResult,
    TrackUpdate,
)
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    AnalysisStreamCapability,
    EvidenceBurstCapability,
    EvidenceBurstFrame,
    EvidenceBurstResult,
    EvidenceBurstRequest,
)
from mockingbird.source_providers.camera_node import CameraNodeClientError
from mockingbird_node.app import EvidenceBurstNodeRequest, create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node.providers import SyntheticCameraProvider
from PIL import Image


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _config(tmp_path) -> CameraNodeConfig:
    return CameraNodeConfig(
        "Stage 5 test node", "127.0.0.1", 8787, "synthetic", None,
        1_500_000, 1920, 1080, 60, 2,
        testing=True,
        enabled_providers=("synthetic",),
        pairing_state_path=tmp_path / "pairing.json",
    )


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


def _frame(
    sequence: int,
    *,
    generation: str = "generation-a",
    captured_at: datetime | None = None,
    payload: bytes = b"\xff\xd8frame\xff\xd9",
    node_session_id: str = "node-session-a",
) -> AnalysisFrameEnvelope:
    captured = captured_at or datetime(2026, 8, 4, tzinfo=UTC) + timedelta(milliseconds=sequence * 200)
    digest = hashlib.sha256(payload).hexdigest()
    return AnalysisFrameEnvelope(
        stream_id="stream-yard",
        node_session_id=node_session_id,
        sequence=sequence,
        frame_id=f"{generation}:{sequence}:{digest[:12]}",
        captured_at=captured,
        source_monotonic_ns=sequence * 200_000_000,
        width=640,
        height=480,
        content_type="image/jpeg",
        provider_generation=generation,
        payload=payload,
        content_hash=digest,
        timing_facts=(("timestamp_precision", "microsecond"),),
    )


def test_provider_neutral_media_capabilities_are_bounded_and_honest() -> None:
    analysis = AnalysisStreamCapability(
        transport_key="camera-node-multipart-jpeg-v1",
        stream_mode="continuous",
        content_type="image/jpeg",
        width=1280,
        height=720,
        nominal_fps=2.0,
        maximum_fps=4.0,
        sequence_supported=True,
        capture_timestamp_supported=True,
        monotonic_timestamp_supported=True,
        timestamp_precision="microsecond",
        hardware_encoding_available=False,
        simultaneous_evidence_capture="provider_dependent",
        availability="available",
        limitations=("one authenticated connection",),
    )
    burst = EvidenceBurstCapability(
        availability="available",
        available_profiles=("evidence-large",),
        maximum_frames_per_burst=1,
        minimum_interval_ms=1000,
        expected_latency_ms=(0, 10_000),
        analysis_continues="provider_dependent",
        exposure_may_change=True,
        focus_may_change=True,
        source_provenance_supported=True,
        limitations=("single still",),
    )
    assert analysis.transport_key == "camera-node-multipart-jpeg-v1"
    assert burst.maximum_frames_per_burst == 1
    assert "picamera2" not in repr((analysis, burst)).lower()


def test_analysis_source_preserves_identity_reports_gaps_and_bounds_latest_work() -> None:
    source = CameraNodeAnalysisSource("stream-yard", maximum_queue_frames=2, maximum_frame_bytes=1024)
    received = datetime(2026, 8, 4, 12, tzinfo=UTC)
    source.offer(_frame(1), received_at=received)
    source.offer(_frame(3), received_at=received + timedelta(milliseconds=5))
    source.offer(_frame(4), received_at=received + timedelta(milliseconds=10))
    packet = source.pop_latest(now=received + timedelta(milliseconds=20))
    assert packet is not None
    assert packet.frame_id.startswith("generation-a:4:")
    assert packet.payload == b"\xff\xd8frame\xff\xd9"
    assert packet.frame_sequence == 4
    status = source.status(now=received + timedelta(milliseconds=20))
    assert status.sequence_gaps == 1
    assert status.dropped_frames == 1
    assert status.coalesced_frames == 1
    assert status.queue_depth == 0


def test_generation_change_resets_transient_queue_and_stale_frames_drop() -> None:
    source = CameraNodeAnalysisSource("stream-yard", maximum_queue_frames=3, maximum_frame_age_ms=500)
    received = datetime(2026, 8, 4, 12, tzinfo=UTC)
    source.offer(_frame(1), received_at=received)
    source.offer(_frame(1, generation="generation-b"), received_at=received + timedelta(seconds=1))
    assert source.status(now=received + timedelta(seconds=1)).generation_resets == 1
    assert source.pop_latest(now=received + timedelta(seconds=2)) is None
    assert source.status(now=received + timedelta(seconds=2)).stale_frames == 1


def test_invalid_frame_dimensions_content_and_hash_are_rejected() -> None:
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    with pytest.raises(ValueError, match="analysis_frame_dimensions"):
        source.offer(AnalysisFrameEnvelope(**{**_frame(1).__dict__, "width": 0}))
    with pytest.raises(ValueError, match="analysis_frame_content"):
        source.offer(AnalysisFrameEnvelope(**{**_frame(1).__dict__, "content_type": "text/plain"}))
    with pytest.raises(ValueError, match="analysis_frame_hash"):
        source.offer(AnalysisFrameEnvelope(**{**_frame(1).__dict__, "content_hash": "0" * 64}))


@pytest.mark.anyio
async def test_camera_node_stream_and_burst_require_pairing_and_remain_bounded(tmp_path) -> None:
    app = create_node_app(_config(tmp_path), provider=SyntheticCameraProvider())
    routes = {getattr(route, "path", ""): route for route in app.routes}
    stream_route = routes["/node/v1/cameras/{camera_id}/analysis-stream"]
    burst_route = routes["/node/v1/cameras/{camera_id}/evidence-burst"]
    for route in (stream_route, burst_route):
        assert any(
            getattr(item.call, "__name__", "") == "require_pairing"
            for item in route.dependant.dependencies
        )
    capabilities = routes["/node/v1/capabilities"].endpoint("paired")
    assert capabilities["analysis_stream"]["transport_key"] == "camera-node-multipart-jpeg-v1"
    assert capabilities["evidence_burst"]["maximum_frames_per_burst"] == 1
    stream = await stream_route.endpoint(
        "synthetic-camera-1", _ConnectedRequest(), "2", "paired"
    )
    content = b"".join([part async for part in stream.body_iterator])
    assert stream.media_type.startswith("multipart/x-mixed-replace")
    assert content.count(b"Content-Type: image/jpeg") == 2
    request = EvidenceBurstRequest(
        request_id="burst-test-1",
        stream_id="stream-yard",
        node_session_id="engineering-validation",
        track_generation_id="track-generation-test",
        trigger_frame_id="generation-a:1:test",
        trigger_captured_at=datetime(2026, 8, 4, tzinfo=UTC),
        requested_frame_count=1,
        requested_profile_id="synthetic-monitoring",
        cadence_ms=0,
        subject_geometry=(0.1, 0.1, 0.2, 0.2),
        zone_id=None,
        deadline_at=datetime(2026, 8, 4, tzinfo=UTC) + timedelta(seconds=10),
        shadow_only=True,
    )
    burst = burst_route.endpoint(
        "synthetic-camera-1",
        EvidenceBurstNodeRequest(
            request_id=request.request_id,
            profile_id=request.requested_profile_id,
            frame_count=request.requested_frame_count,
        ),
        "paired",
    )
    assert burst.status_code == 200
    assert burst.headers["x-mockingbird-burst-request"] == request.request_id
    assert burst.headers["x-mockingbird-content-sha256"] == hashlib.sha256(burst.body).hexdigest()


@pytest.mark.anyio
async def test_camera_node_early_disconnect_releases_bounded_stream_slot(tmp_path) -> None:
    app = create_node_app(_config(tmp_path), provider=SyntheticCameraProvider())
    routes = {getattr(route, "path", ""): route for route in app.routes}
    endpoint = routes["/node/v1/cameras/{camera_id}/analysis-stream"].endpoint

    first = await endpoint("synthetic-camera-1", _ConnectedRequest(), "1200", "paired")
    second = await endpoint("synthetic-camera-1", _ConnectedRequest(), "1200", "paired")
    await anext(first.body_iterator)
    await anext(second.body_iterator)
    with pytest.raises(HTTPException) as rejected:
        await endpoint("synthetic-camera-1", _ConnectedRequest(), "1", "paired")
    assert rejected.value.status_code == 429

    await first.body_iterator.aclose()
    replacement = await endpoint(
        "synthetic-camera-1", _ConnectedRequest(), "1", "paired"
    )
    replacement_content = b"".join(
        [part async for part in replacement.body_iterator]
    )
    assert replacement_content.count(b"Content-Type: image/jpeg") == 1
    await second.body_iterator.aclose()


class _LiveDetector:
    def __init__(self) -> None:
        self.loaded = False

    def probe(self): return {"cuda_available": True, "model_bundle_compatible": True}
    def load(self): self.loaded = True
    async def infer_frame(self, frame: FramePacket):
        return (DetectionObservation(
            "fixture", "animal", 0.95, frame.captured_at, frame_id=frame.frame_id,
            bounding_box=(0.2, 0.2, 0.4, 0.4), is_animal=True,
        ),)
    def finalize_replay(self): pass
    def close(self): self.loaded = False
    def report_metadata(self): return {"model": {"key": "fixture"}}
    def execution_facts(self): return {}


class _BurstTransport:
    def __init__(self, *, fail: bool = False, stale: bool = False) -> None:
        image = BytesIO()
        Image.new("RGB", (32, 24), color="white").save(image, format="JPEG")
        self.payload = image.getvalue()
        self.requests = []
        self.fail = fail
        self.stale = stale
        self.closed = False

    def iter_analysis_frames(self, *, maximum_frames: int): return iter(())
    def request_evidence_burst(self, request):
        self.requests.append(request)
        if self.fail:
            return EvidenceBurstResult(request.request_id, "failed", failure_code="fixture_failure")
        frame = EvidenceBurstFrame(
            1, request.trigger_captured_at + timedelta(milliseconds=5), 32, 24, "image/jpeg",
            hashlib.sha256(self.payload).hexdigest(), self.payload, request.trigger_frame_id,
            "stale-generation" if self.stale else "generation-a", 5, "supported",
        )
        return EvidenceBurstResult(request.request_id, "captured", (frame,))
    def close(self): self.closed = True


def _live_provider() -> FrameDrivenObservationProvider:
    settings = FrameDrivenSettings(
        source_nominal_fps=5, baseline_detector_fps=5, candidate_detector_fps=5,
        strong_detection_threshold=0.8, minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1, maximum_missed_frames=2, maximum_frame_gap_ms=1000,
        tracker_expiry_ms=1000, maximum_track_duration_ms=10000, maximum_active_tracks=4,
        evidence_ring_size=4, pretrigger_frame_count=1,
    )
    provider = FrameDrivenObservationProvider(
        detector=_LiveDetector(), settings=settings, tracker_support=lambda frame, track: track.bounding_box
    )
    provider.load()
    return provider


@pytest.mark.anyio
async def test_live_shadow_requests_one_burst_and_never_writes_product_truth() -> None:
    transport = _BurstTransport()
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=transport, provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    received = datetime(2026, 8, 4, tzinfo=UTC)
    first = await session.process_envelope(_frame(1), received_at=received)
    second = await session.process_envelope(_frame(2), received_at=received + timedelta(milliseconds=200))
    assert first is not None and second is not None
    assert len(transport.requests) == 1
    assert [item.role for item in first.evidence_candidates] == [
        "high_resolution_burst", "classifier_same_frame",
    ]
    assert first.creates_truth is False
    assert session.status().production_proposal_authority is False
    session.stop()
    assert transport.closed is True
    assert session.status().state == "stopped"


@pytest.mark.anyio
async def test_live_shadow_burst_evidence_carries_geometry_attribution_with_real_measured_gap() -> None:
    """Localization Attribution / Detection Geometry Lineage v1 (see
    docs/localization-attribution-contract.md): a high-resolution burst
    capture is a genuinely separate, later real capture event -- its own
    `geometry_attribution` must honestly say so (`same_frame=False`) and
    carry the transport's own real measured round-trip
    (`request_to_capture_ms`), never a fabricated zero, and must attribute
    the geometry to the genuine strong detector hit that actually supplied
    it (`_LiveDetector` always reports confidence 0.95, above `_live_
    provider`'s own `strong_detection_threshold` of 0.8 -- a brand-new
    generation's very first observation is always a genuine, non-`None`
    source, see `frame_tracker._start`)."""
    transport = _BurstTransport()
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=transport, provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    result = await session.process_envelope(_frame(1), received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert result is not None
    assert len(result.evidence_candidates) == 2
    candidate = result.evidence_candidates[0]
    assert candidate.role == "high_resolution_burst"
    attribution = candidate.geometry_attribution
    assert attribution is not None
    assert attribution.same_frame is False
    # `_BurstTransport.request_evidence_burst` always reports a fixed 5ms
    # `request_to_capture_ms` -- the exact, real transport-measured delta,
    # reused verbatim rather than re-derived from offsets.
    assert attribution.geometry_evidence_gap_ms == 5
    assert attribution.geometry_source == "detector"
    assert attribution.geometry_source_confidence == 0.95
    assert attribution.geometry_source_offset_ms == candidate.source_offset_ms

    # Same-Frame Species Evidence v1: the exact analysis-stream frame that
    # produced this same track update's subject box is persisted alongside
    # the burst above, and -- unlike the burst -- its own geometry
    # attribution honestly proves `same_frame=True` with a zero gap, because
    # its pixels and `subject_geometry` really do come from the identical
    # captured frame (`_frame(1)`), not a later, separate capture.
    same_frame_candidate = result.evidence_candidates[1]
    assert same_frame_candidate.role == "classifier_same_frame"
    assert same_frame_candidate.media_asset_id.startswith("shadow-same-frame:")
    assert same_frame_candidate.frame_id == candidate.frame_id
    assert same_frame_candidate.subject_geometry == candidate.subject_geometry
    assert same_frame_candidate.width == 640 and same_frame_candidate.height == 480
    same_frame_attribution = same_frame_candidate.geometry_attribution
    assert same_frame_attribution is not None
    assert same_frame_attribution.same_frame is True
    assert same_frame_attribution.geometry_evidence_gap_ms == 0
    assert same_frame_attribution.geometry_source == "detector"
    assert same_frame_attribution.geometry_source_confidence == 0.95
    session.stop()


@pytest.mark.anyio
async def test_live_shadow_reports_one_pending_operation_and_clears_generation_on_stop() -> None:
    provider = _live_provider()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_inference(frame: FramePacket):
        entered.set()
        await release.wait()
        return ()

    provider.detector.infer_frame = slow_inference
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(),
        provider=provider,
        evidence_profile_id="evidence-large",
    )
    session.start()
    task = asyncio.create_task(
        session.process_envelope(
            _frame(1), received_at=datetime(2026, 8, 4, tzinfo=UTC)
        )
    )
    await entered.wait()
    assert session.status().pending_inference == 1
    release.set()
    await task
    assert session.status().pending_inference == 0
    assert session.status().provider_generation == "generation-a"
    session.stop()
    assert session.status().provider_generation is None


@pytest.mark.anyio
@pytest.mark.parametrize(("fail", "stale", "failure_count", "stale_count"), [
    (True, False, 1, 0), (False, True, 0, 1),
])
async def test_burst_failure_or_stale_generation_does_not_stop_analysis(
    fail: bool, stale: bool, failure_count: int, stale_count: int,
) -> None:
    transport = _BurstTransport(fail=fail, stale=stale)
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=transport, provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    result = await session.process_envelope(
        _frame(1), received_at=datetime(2026, 8, 4, tzinfo=UTC)
    )
    assert result is not None and result.evidence_candidates == ()
    status = session.status()
    assert status.state == "running"
    assert status.burst_failures == failure_count
    assert status.stale_bursts == stale_count
    session.stop()


def test_live_shadow_module_has_structural_no_write_boundary() -> None:
    source = __import__("pathlib").Path("src/mockingbird/observation/camera_node_live.py").read_text()
    forbidden = ("mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence", "StreamMonitoringPolicy")
    assert not any(token in source for token in forbidden)


# --------------------------------------------------------------------------
# Same-Frame Species Evidence v1: precise control over `TrackUpdate.
# support_state`/`frame_id`, which the real tracker fixture cannot reliably
# manufacture (a stale/carried-forward update with a still-high leftover
# confidence is an edge case the real tracker rarely produces on demand).
# `_FakeSameFrameProvider` implements exactly the surface
# `LiveCameraNodeShadowSession` touches on `self.provider`, nothing more.
# --------------------------------------------------------------------------


class _FakeSettings:
    def __init__(self, *, strong_detection_threshold: float = 0.8) -> None:
        self.strong_detection_threshold = strong_detection_threshold


class _FakeSameFrameProvider:
    def __init__(self, updates_by_frame_id: dict[str, tuple[TrackUpdate, ...]]) -> None:
        self._updates_by_frame_id = updates_by_frame_id
        self.settings = _FakeSettings()
        self.live_reset_count = 0
        # Set by a test right before `process_envelope` to simulate the real
        # provider having internally reset its tracking generation for the
        # frame about to be processed (see `LiveCameraNodeShadowSession.
        # _process_frame`'s before/after `live_reset_count` comparison).
        self.pending_reset = False

    def start_live(self, stream_id: str) -> None:
        pass

    async def observe_live_frame(self, frame: FramePacket) -> ObservationResult:
        if self.pending_reset:
            self.live_reset_count += 1
            self.pending_reset = False
        updates = self._updates_by_frame_id.get(frame.frame_id, ())
        return ObservationResult(
            "fake-same-frame-provider", "live_shadow", frame.stream_id, frame.captured_at,
            frame_packets=(frame,), track_updates=updates, detector_ran=True,
        )

    def stop_live(self, reason: str = "provider_reset") -> tuple[ObservationResult, ...]:
        return ()


def _confirmed_update(
    *, generation_id: str, frame_id: str, source_offset_ms: int,
    box: tuple[float, float, float, float] = (0.2, 0.2, 0.4, 0.4),
    support_state: str = "strong_detector_supported",
    lifecycle_state: str = "confirmed",
    confidence: float = 0.9,
) -> TrackUpdate:
    return TrackUpdate(
        track_id=generation_id, generation_id=generation_id,
        captured_at=datetime(2026, 8, 4, tzinfo=UTC) + timedelta(milliseconds=source_offset_ms),
        status="updated", lifecycle_state=lifecycle_state, frame_id=frame_id,
        source_offset_ms=source_offset_ms, broad_class="animal", bounding_box=box,
        confidence=confidence, support_state=support_state,
        bounding_box_source_offset_ms=source_offset_ms,
    )


def _generous_scheduler() -> BurstScheduler:
    return BurstScheduler(
        session_id="same-frame-test",
        config=BurstSchedulerConfig(
            minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0,
            novelty_reserve_capacity=8, max_bursts_per_session=8,
        ),
    )


@pytest.mark.anyio
async def test_same_frame_evidence_persisted_once_per_generation_with_proven_geometry() -> None:
    """Exactly one `classifier_same_frame` candidate is ever produced for one
    track generation, even across multiple later meaningful updates -- "at
    most one same-frame evidence image per Visit/candidate", not one per
    detector frame."""

    frame_one = _frame(1)
    frame_two = _frame(2, payload=b"\xff\xd8second-frame\xff\xd9")
    provider = _FakeSameFrameProvider({
        frame_one.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id=frame_one.frame_id, source_offset_ms=0,
        ),),
        frame_two.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id=frame_two.frame_id, source_offset_ms=200,
            box=(0.5, 0.5, 0.7, 0.7),
        ),),
    })
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=4096),
        transport=_BurstTransport(), provider=provider, evidence_profile_id="evidence-large",
        scheduler=_generous_scheduler(),
    )
    session.start()
    received = datetime(2026, 8, 4, tzinfo=UTC)
    first = await session.process_envelope(frame_one, received_at=received)
    second = await session.process_envelope(frame_two, received_at=received + timedelta(milliseconds=200))
    assert first is not None and second is not None
    first_same_frame = [item for item in first.evidence_candidates if item.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE]
    second_same_frame = [item for item in second.evidence_candidates if item.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE]
    assert len(first_same_frame) == 1
    assert second_same_frame == []
    candidate = first_same_frame[0]
    assert candidate.geometry_attribution is not None
    assert candidate.geometry_attribution.same_frame is True
    assert candidate.subject_geometry == (0.2, 0.2, 0.4, 0.4)
    session.stop()


@pytest.mark.anyio
async def test_same_frame_payload_matches_exact_analysis_frame_bytes() -> None:
    """The persisted same-frame payload is the exact analysis-stream frame's
    own bytes -- never the (different, larger) burst payload -- recoverable
    through `temporary_same_frame_payload` exactly like a burst payload is
    through `temporary_burst_payload`."""

    frame_one = _frame(1)
    provider = _FakeSameFrameProvider({
        frame_one.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id=frame_one.frame_id, source_offset_ms=0,
        ),),
    })
    transport = _BurstTransport()
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=4096),
        transport=transport, provider=provider, evidence_profile_id="evidence-large",
        scheduler=_generous_scheduler(),
    )
    session.start()
    result = await session.process_envelope(frame_one, received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert result is not None
    candidate = next(item for item in result.evidence_candidates if item.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE)
    content_hash = candidate.media_asset_id.removeprefix("shadow-same-frame:")
    recovered = session.temporary_same_frame_payload(content_hash)
    assert recovered == frame_one.payload
    assert recovered != transport.payload
    assert content_hash == hashlib.sha256(frame_one.payload).hexdigest()
    session.stop()


@pytest.mark.anyio
async def test_same_frame_evidence_rejects_stale_carried_forward_geometry() -> None:
    """A `temporarily_lost` update -- the geometry tracker's own "no fresh
    observation this frame, box simply carried forward" state -- must never
    become same-frame evidence even if it happens to still carry a leftover
    high confidence from an earlier genuine detection (the "meaningful"
    burst-opportunity check in `_process_frame` reads `confidence`, not
    `support_state`). `frame.frame_id == update.frame_id` alone is not
    proof of fresh geometry; this is the concrete scenario that distinction
    exists for."""

    frame_one = _frame(1)
    provider = _FakeSameFrameProvider({
        frame_one.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id=frame_one.frame_id, source_offset_ms=0,
            support_state="temporarily_lost", lifecycle_state="temporarily_lost", confidence=0.95,
        ),),
    })
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=4096),
        transport=_BurstTransport(), provider=provider, evidence_profile_id="evidence-large",
        scheduler=_generous_scheduler(),
    )
    session.start()
    result = await session.process_envelope(frame_one, received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert result is not None
    # The burst itself still fires (a stale-but-high-confidence update is
    # still a real, if imperfect, "meaningful" burst opportunity today --
    # unrelated, pre-existing behavior this milestone leaves untouched).
    assert any(item.role == "high_resolution_burst" for item in result.evidence_candidates)
    assert not any(item.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE for item in result.evidence_candidates)
    session.stop()


@pytest.mark.anyio
async def test_same_frame_evidence_requires_matching_frame_id() -> None:
    """Defense in depth: even a fresh, strongly-supported update is never
    treated as same-frame evidence if its own `frame_id` does not match the
    frame actually being processed -- `same_frame` must be earned, never
    assumed from role/timing alone."""

    frame_one = _frame(1)
    provider = _FakeSameFrameProvider({
        frame_one.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id="a-different-frame-id", source_offset_ms=0,
        ),),
    })
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=4096),
        transport=_BurstTransport(), provider=provider, evidence_profile_id="evidence-large",
        scheduler=_generous_scheduler(),
    )
    session.start()
    result = await session.process_envelope(frame_one, received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert result is not None
    assert not any(item.role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE for item in result.evidence_candidates)
    session.stop()


@pytest.mark.anyio
async def test_same_frame_evidence_cache_cleared_on_generation_reset() -> None:
    """The bounded same-frame payload cache and per-generation capture set
    are cleared on a genuine provider reset, mirroring `_temporary_payloads`
    exactly -- a stale cross-generation entry must never survive a reset."""

    frame_one = _frame(1)
    provider = _FakeSameFrameProvider({
        frame_one.frame_id: (_confirmed_update(
            generation_id="gen-1", frame_id=frame_one.frame_id, source_offset_ms=0,
        ),),
    })
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=4096),
        transport=_BurstTransport(), provider=provider, evidence_profile_id="evidence-large",
        scheduler=_generous_scheduler(),
    )
    session.start()
    await session.process_envelope(frame_one, received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert session._same_frame_captured_generations == {"gen-1"}
    assert len(session._same_frame_temporary_payloads) == 1
    provider.pending_reset = True  # simulate the provider resetting internally on the next frame
    await session.process_envelope(
        _frame(2, generation="generation-b"), received_at=datetime(2026, 8, 4, tzinfo=UTC) + timedelta(seconds=1),
    )
    assert session._same_frame_captured_generations == set()
    assert len(session._same_frame_temporary_payloads) == 0
    session.stop()


class _RapidTransport(_BurstTransport):
    def iter_analysis_frames(self, *, maximum_frames: int):
        return iter(_frame(index) for index in range(1, maximum_frames + 1))


@pytest.mark.anyio
async def test_run_receives_concurrently_and_coalesces_slow_inference_to_newest_work() -> None:
    provider = _live_provider()

    async def slow_empty_inference(frame: FramePacket):
        await asyncio.sleep(0.02)
        return ()

    provider.detector.infer_frame = slow_empty_inference
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource(
            "stream-yard", maximum_queue_frames=2, maximum_frame_bytes=1024
        ),
        transport=_RapidTransport(), provider=provider, evidence_profile_id="evidence-large",
    )
    results = await session.run(maximum_frames=12)
    status = session.status()
    assert status.source.received_frames == 12
    assert status.source.dropped_frames + status.source.coalesced_frames >= 10
    assert 1 <= len(results) <= 2
    assert results[-1].frame_packets[0].frame_sequence == 12
    session.stop()


def test_http_transport_rejects_burst_profile_mismatch_without_network() -> None:
    transport = CameraNodeHttpTransport(
        base_address="http://127.0.0.1:8787",
        credential="paired",
        camera_id="camera-a",
        stream_id="stream-yard",
        evidence_profile_id="evidence-large",
    )
    request = EvidenceBurstRequest(
        request_id="burst-profile-mismatch",
        stream_id="stream-yard",
        node_session_id="node-session-a",
        track_generation_id="track-a",
        trigger_frame_id="frame-a",
        trigger_captured_at=datetime(2026, 8, 4, tzinfo=UTC),
        requested_frame_count=1,
        requested_profile_id="different-profile",
        cadence_ms=0,
        subject_geometry=None,
        zone_id=None,
        deadline_at=datetime(2026, 8, 4, tzinfo=UTC) + timedelta(seconds=10),
    )
    result = transport.request_evidence_burst(request)
    assert result.status == "failed"
    assert result.failure_code == "evidence_profile_mismatch"


# --- Camera Node Connectivity & Recovery Diagnosis v1 (Section 10): the real
# 2026-08-20 field incident could not distinguish "Camera Node refused the
# connection" from "it timed out" from "it sent a bad response" using only
# the host-side API -- every one of those collapsed into the same bare
# `analysis_stream_unavailable` string, and the underlying exception detail
# was discarded before it ever reached diagnostics. -------------------------


def test_transport_error_classification_is_a_bounded_safe_vocabulary() -> None:
    """Pure classification function: every branch, and the safe fallback for
    an exception type none of the specific branches recognize."""

    assert _classify_analysis_stream_transport_error(ConnectionRefusedError()) == "connect_refused"
    assert _classify_analysis_stream_transport_error(ConnectionResetError()) == "connection_reset"
    assert _classify_analysis_stream_transport_error(socket.timeout()) == "timeout"
    assert _classify_analysis_stream_transport_error(TimeoutError()) == "timeout"
    assert _classify_analysis_stream_transport_error(socket.gaierror()) == "dns_unresolved"
    assert _classify_analysis_stream_transport_error(OSError("unrecognized")) == "os_error"


def test_real_connection_refused_is_classified_and_never_leaks_raw_text() -> None:
    """A real OS-level connection refusal (not a fake/simulated one) against
    the real `CameraNodeHttpTransport.iter_analysis_frames` -- the exact
    transport a live session's receiver thread calls. Binds and immediately
    releases a real socket to get a genuinely unbound local port, so the
    ensuing connection attempt gets a real `ConnectionRefusedError` from the
    OS, not a mock."""

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    transport = CameraNodeHttpTransport(
        base_address=f"http://127.0.0.1:{port}",
        credential="paired",
        camera_id="camera-a",
        stream_id="stream-yard",
        evidence_profile_id="evidence-large",
    )
    with pytest.raises(CameraNodeClientError) as excinfo:
        next(transport.iter_analysis_frames(maximum_frames=1))
    error = excinfo.value
    # The primary retry-controlling code stays exactly what every existing
    # terminal/retry check already matches -- classification is additive.
    assert str(error) == "analysis_stream_unavailable"
    assert error.failure_class == "connect_refused"


def test_multipart_header_and_jpeg_parsers_use_wire_bytes() -> None:
    image = BytesIO()
    Image.new("RGB", (32, 24), color="white").save(image, format="JPEG")
    payload = image.getvalue()
    digest = hashlib.sha256(payload).hexdigest()
    headers = (
        "Content-Type: image/jpeg\r\n"
        f"Content-Length: {len(payload)}\r\n"
        "X-MockingBird-Sequence: 1\r\n"
        "X-MockingBird-Frame-Id: frame-1\r\n"
        "X-MockingBird-Captured-At: 2026-08-04T00:00:00+00:00\r\n"
        "X-MockingBird-Source-Monotonic-Ns: 100\r\n"
        "X-MockingBird-Width: 32\r\n"
        "X-MockingBird-Height: 24\r\n"
        "X-MockingBird-Provider-Generation: generation-a\r\n"
        "X-MockingBird-Node-Session: session-a\r\n"
        f"X-MockingBird-Content-Sha256: {digest}\r\n\r\n"
    ).encode("ascii")
    parsed = CameraNodeHttpTransport._read_part_headers(BytesIO(headers))
    envelope = _analysis_envelope("stream-yard", parsed, payload)
    assert envelope.sequence == 1
    assert envelope.content_hash == digest
    assert _jpeg_dimensions(payload) == (32, 24)


# --------------------------------------------------------------------------
# Stage 6.9: recurrence-aware burst scheduler wiring
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_live_shadow_status_exposes_scheduler_diagnostics_and_health() -> None:
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(), provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    await session.process_envelope(_frame(1), received_at=datetime(2026, 8, 4, tzinfo=UTC))
    status = session.status()
    assert status.scheduler_diagnostics is not None
    assert status.scheduler_diagnostics.issued_count == 1
    assert status.scheduler_health is not None
    assert status.scheduler_health.burst_capability_available is True
    session.stop()


@pytest.mark.anyio
async def test_live_shadow_scheduler_suppresses_once_session_budget_exhausted() -> None:
    """A track generation is a burst opportunity, not authority: the
    scheduler -- not generation-id-seen-before bookkeeping -- controls
    whether a second, still-meaningful update actually reaches the
    transport. Same-track-generation cooldown and recurrence-group cooldown
    are both disabled here so the ordinary session budget itself -- with the
    Stage 6.12 fairness reserve also disabled -- is the one isolated,
    exhausted channel; without disabling them, this same second, still-
    meaningful update would correctly be suppressed by whichever bound it
    reaches first instead."""

    transport = _BurstTransport()
    scheduler = BurstScheduler(session_id="live-shadow-test", config=BurstSchedulerConfig(
        max_bursts_per_session=1, minimum_burst_interval_ms=0, recurrence_group_cooldown_ms=0,
        novelty_reserve_capacity=0,
    ))
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=transport, provider=_live_provider(), evidence_profile_id="evidence-large",
        scheduler=scheduler,
    )
    session.start()
    received = datetime(2026, 8, 4, tzinfo=UTC)
    first = await session.process_envelope(_frame(1), received_at=received)
    second = await session.process_envelope(_frame(2), received_at=received + timedelta(milliseconds=200))
    assert first is not None and second is not None
    assert len(transport.requests) == 1
    assert [item.role for item in second.evidence_candidates] == []
    diagnostics = session.status().scheduler_diagnostics
    assert diagnostics is not None
    assert diagnostics.issued_count == 1
    # With the ordinary budget exhausted and the fairness reserve disabled,
    # a materially novel repeat (a genuine time-gap escape past the now-
    # zeroed recurrence cooldown) is rejected by the more precise Stage 6.12
    # code -- proven not a suppressible recurrence, but no capacity (ordinary
    # or reserve) remains -- rather than the older, less specific budget
    # code, which this stage now reserves for the override channel (see
    # tests/test_burst_scheduler.py::test_override_respects_hard_session_budget).
    assert dict(diagnostics.suppression_reason_distribution).get(DECISION_SUPPRESSED_NOVELTY_RESERVE_EXHAUSTED) == 1
    assert dict(diagnostics.suppression_reason_distribution).get(DECISION_SUPPRESSED_SESSION_BUDGET) is None
    session.stop()


@pytest.mark.anyio
async def test_provider_generation_change_resets_scheduler_state() -> None:
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(), provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    received = datetime(2026, 8, 4, tzinfo=UTC)
    await session.process_envelope(_frame(1), received_at=received)
    assert session.status().scheduler_diagnostics.issued_count == 1

    await session.process_envelope(_frame(1, generation="generation-b"), received_at=received + timedelta(seconds=1))
    assert session.status().scheduler_diagnostics.issued_count == 1
    assert session.status().scheduler_diagnostics.recurrence_group_count <= 1
    session.stop()


@pytest.mark.anyio
async def test_stop_resets_scheduler_state() -> None:
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(), provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    await session.process_envelope(_frame(1), received_at=datetime(2026, 8, 4, tzinfo=UTC))
    assert session.scheduler.diagnostics().issued_count == 1
    session.stop()
    assert session.scheduler.diagnostics().issued_count == 0
    assert session.scheduler.recurrence_groups() == ()


def test_default_scheduler_reset_reasons_are_reachable() -> None:
    # Documents which reset reasons the live wiring actually uses -- both
    # are exercised end-to-end by the async tests above.
    assert {RESET_GENERATION_REPLACEMENT, RESET_SESSION_STOP}.issubset(set(RESET_REASONS))


# =============================================================================
# Stage 6.11B: reconnect-safe tracker continuity on the *live* Camera Node
# path. Before this stage, `CameraNodeAnalysisSource` treated a fresh HTTP
# connection's restarted sequence header (`x-mockingbird-sequence` back to a
# low value) as a fatal "analysis_frame_sequence" violation whenever
# `provider_generation` had not also changed -- forcing `_CaptureLoop` to
# rebuild the whole source and restart the live tracker generation on every
# ordinary reconnect (roughly every ten seconds on the real Node). This
# section proves the source itself now distinguishes a benign transport
# reconnect (same provider_generation, new node_session_id) from a genuine
# source-generation reset, using the identical Stage 6.11 decision contract
# already proven in replay. See docs/reconnect-continuity-contract.md.
# =============================================================================


def test_committed_stage611b_scenario_catalog_exists() -> None:
    import json
    from pathlib import Path

    catalog = json.loads(Path("tests/fixtures/observation_stage611b/scenarios.json").read_text(encoding="utf-8"))
    all_scenarios = [name for group in catalog["scenarios"].values() for name in group]
    assert len(all_scenarios) == len(set(all_scenarios)) >= 30


# --------------------------------------------------------------------------
# 1/2/3/4/5: source-level reconnect continuity -- same provider_generation,
# new node_session_id, no exception raised, a new segment recorded, and the
# delivered source_offset_ms/timing facts remain monotonic across it.
# --------------------------------------------------------------------------


def test_source_reconnect_with_same_generation_preserves_state_and_records_new_segment() -> None:
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    received = datetime(2026, 8, 6, 12, tzinfo=UTC)
    source.offer(_frame(1, node_session_id="conn-a"), received_at=received)
    first = source.pop_latest(now=received)
    assert first is not None
    assert dict(first.timing_facts)["connection_segment_id"] == "conn-a"
    assert dict(first.timing_facts)["connection_segment_ordinal"] == 0
    assert dict(first.timing_facts)["temporal_discontinuity"] is False

    # A fresh HTTP connection: sequence restarts at a low value, a new
    # node_session_id, but the SAME provider_generation -- must not raise.
    source.offer(_frame(1, node_session_id="conn-b"), received_at=received + timedelta(seconds=3))
    second = source.pop_latest(now=received + timedelta(seconds=3))
    assert second is not None
    facts = dict(second.timing_facts)
    assert facts["connection_segment_id"] == "conn-b"
    assert facts["connection_segment_ordinal"] == 1  # 4. new transport segment is recorded
    assert facts["temporal_discontinuity"] is True
    status = source.status(now=received + timedelta(seconds=3))
    assert status.transport_reconnect_count == 1
    assert status.current_connection_segment_ordinal == 1
    assert status.generation_resets == 0  # no generation reset -- this was a benign reconnect


def test_sequence_reset_alone_does_not_raise_or_reset_generation() -> None:
    """Scenario 2: the Node's own per-connection sequence header restarting
    at 1 on a fresh connection, with provider_generation unchanged, must not
    raise `analysis_frame_sequence` -- the Stage 6.6-era failure mode this
    stage removes."""
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    received = datetime(2026, 8, 6, 12, tzinfo=UTC)
    source.offer(_frame(5, node_session_id="conn-a"), received_at=received)
    source.pop_latest(now=received)
    # Sequence goes from 5 back down to 1 -- would have raised before this
    # stage -- but arrives on a new connection (conn-b).
    source.offer(_frame(1, node_session_id="conn-b"), received_at=received + timedelta(seconds=2))
    packet = source.pop_latest(now=received + timedelta(seconds=2))
    assert packet is not None
    assert packet.frame_sequence == 1
    assert source.status().generation_resets == 0


def test_source_offset_reset_alone_does_not_reset_generation() -> None:
    """Scenario 3: a fresh connection's own connection-local source offset
    resetting near zero (preserved separately as original_source_offset_ms)
    must not, by itself, force a generation reset or a non-monotonic
    session-relative source_offset_ms."""
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    received = datetime(2026, 8, 6, 12, tzinfo=UTC)
    source.offer(_frame(8, node_session_id="conn-a"), received_at=received)
    source.pop_latest(now=received)
    source.offer(_frame(9, node_session_id="conn-a"), received_at=received + timedelta(milliseconds=200))
    first = source.pop_latest(now=received + timedelta(milliseconds=200))
    source.offer(_frame(1, node_session_id="conn-b"), received_at=received + timedelta(seconds=2))
    second = source.pop_latest(now=received + timedelta(seconds=2))
    assert first is not None and second is not None
    # The connection-local offset resets near zero on the new connection
    # (preserved, unchanged transport-segment provenance)...
    assert dict(second.timing_facts)["original_source_offset_ms"] < dict(first.timing_facts)["original_source_offset_ms"]
    # ...but the session-relative coordinate the tracker actually consumes
    # never goes backwards.
    assert second.source_offset_ms > first.source_offset_ms
    assert source.status().generation_resets == 0


def test_session_timeline_remains_monotonic_across_several_reconnects() -> None:
    """Scenario 5: three connection segments in a row, each delivering a
    handful of frames -- source_offset_ms strictly increases throughout."""
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    received = datetime(2026, 8, 6, 12, tzinfo=UTC)
    offsets: list[int] = []
    moment = received
    for segment_index, segment in enumerate(("conn-a", "conn-b", "conn-c")):
        for local_sequence in range(1, 4):
            moment = moment + timedelta(milliseconds=300)
            source.offer(_frame(local_sequence, node_session_id=segment), received_at=moment)
            packet = source.pop_latest(now=moment)
            assert packet is not None
            offsets.append(packet.source_offset_ms)
        moment = moment + timedelta(seconds=2)  # the reconnect gap before the next segment
    assert offsets == sorted(offsets)
    assert len(set(offsets)) == len(offsets)
    status = source.status()
    assert status.transport_reconnect_count == 2
    assert status.current_connection_segment_ordinal == 2


# --------------------------------------------------------------------------
# 22/23/26/30: `LiveCameraNodeShadowSession` preserves its provider instance,
# burst-scheduler continuity, and clean-stop behavior across a benign
# reconnect, while a true reset still clears both -- exercised through the
# full session (real CameraNodeAnalysisSource + real
# FrameDrivenObservationProvider), not just the provider in isolation.
# --------------------------------------------------------------------------


@pytest.mark.anyio
async def test_live_session_preserves_provider_and_burst_scheduler_state_across_benign_reconnect() -> None:
    provider = _live_provider()
    scheduler = BurstScheduler(session_id="live-shadow-reconnect-test", config=BurstSchedulerConfig())
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(), provider=provider, evidence_profile_id="evidence-large",
        scheduler=scheduler,
    )
    session.start()
    same_provider = session.provider
    received = datetime(2026, 8, 6, tzinfo=UTC)
    await session.process_envelope(_frame(1, node_session_id="conn-a"), received_at=received)
    await session.process_envelope(_frame(2, node_session_id="conn-a"), received_at=received + timedelta(milliseconds=200))
    diagnostics_before = session.scheduler.diagnostics()
    assert diagnostics_before.issued_count >= 1
    assert diagnostics_before.recurrence_group_count == 1

    # A benign reconnect: new node_session_id, same provider_generation.
    await session.process_envelope(_frame(3, node_session_id="conn-b"), received_at=received + timedelta(seconds=3))
    assert session.provider is same_provider  # never rebuilt
    diagnostics_after = session.scheduler.diagnostics()
    # Recurrence-group bookkeeping survives the reconnect -- it is not
    # rebuilt into a fresh, first-ever-seen group (Stage 6.9's whole point
    # would otherwise be defeated on every reconnect): still one group, and
    # the suppressed-as-recurring reason already fired at least once across
    # the sequence, which could only happen if this group's occurrence
    # history genuinely carried across the reconnect rather than resetting.
    assert diagnostics_after.recurrence_group_count == 1
    assert dict(diagnostics_after.suppression_reason_distribution).get(DECISION_SUPPRESSED_RECURRING_GEOMETRY, 0) >= 1

    status = session.status()
    assert status.reconnect_diagnostics is not None
    assert status.reconnect_diagnostics.benign_reconnect_count == 1
    assert status.reconnect_diagnostics.true_reset_count == 0
    assert status.reconnect_diagnostics.last_reconnect_classification == "continue_across_transport_reconnect"
    assert status.reconnect_diagnostics.current_connection_segment_ordinal == 1
    session.stop()


@pytest.mark.anyio
async def test_live_session_true_reset_still_clears_scheduler_and_reports_diagnostics() -> None:
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=_BurstTransport(), provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    received = datetime(2026, 8, 6, tzinfo=UTC)
    await session.process_envelope(_frame(1), received_at=received)
    assert session.status().scheduler_diagnostics.issued_count == 1

    await session.process_envelope(_frame(1, generation="generation-b"), received_at=received + timedelta(seconds=1))
    status = session.status()
    assert status.reconnect_diagnostics is not None
    assert status.reconnect_diagnostics.true_reset_count == 1
    assert status.reconnect_diagnostics.benign_reconnect_count == 0
    assert status.reconnect_diagnostics.last_reconnect_classification == "reset_source_generation"
    session.stop()


@pytest.mark.anyio
async def test_live_session_clean_stop_releases_transport_and_tracker_state() -> None:
    """Scenario 26: a clean stop still releases the transport/source/tracker
    exactly as before this stage; reconnect diagnostics remain honestly
    readable afterward rather than silently vanishing."""
    transport = _BurstTransport()
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024),
        transport=transport, provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    received = datetime(2026, 8, 6, tzinfo=UTC)
    await session.process_envelope(_frame(1, node_session_id="conn-a"), received_at=received)
    await session.process_envelope(_frame(2, node_session_id="conn-b"), received_at=received + timedelta(seconds=3))
    session.stop()
    assert transport.closed is True
    status = session.status()
    assert status.state == "stopped"
    assert status.source.state == "stopped"
    assert status.reconnect_diagnostics is not None
    assert status.reconnect_diagnostics.benign_reconnect_count == 1  # last-known value, not cleared


@pytest.mark.anyio
async def test_live_privacy_ignore_exclusion_unaffected_by_benign_reconnect_bridging() -> None:
    """Scenario 29: Privacy/Ignore exclusion still masks a detection inside
    an excluded region across a benign reconnect through the full live
    session -- the bridge changes tracker-continuity handling only, never
    detection filtering."""
    excluded_region = (0.0, 0.0, 0.5, 0.5)  # covers _LiveDetector's fixed (0.2, 0.2, 0.4, 0.4) box
    session = LiveCameraNodeShadowSession(
        source=CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024, analysis_excluded_regions=(excluded_region,)),
        transport=_BurstTransport(), provider=_live_provider(), evidence_profile_id="evidence-large",
    )
    session.start()
    received = datetime(2026, 8, 6, tzinfo=UTC)
    first = await session.process_envelope(_frame(1, node_session_id="conn-a"), received_at=received)
    second = await session.process_envelope(_frame(2, node_session_id="conn-b"), received_at=received + timedelta(seconds=3))
    assert first is not None and second is not None
    assert first.detection_observations == () and second.detection_observations == ()
    assert first.track_updates == () and second.track_updates == ()
    assert first.visit_proposals == () and second.visit_proposals == ()
    session.stop()


def test_generation_change_still_resets_the_source_and_segment_ordinal() -> None:
    """A true provider_generation change remains a hard reset even when it
    also happens to coincide with a new node_session_id (the normal shape
    of a genuine Camera Node/process restart)."""
    source = CameraNodeAnalysisSource("stream-yard", maximum_frame_bytes=1024)
    received = datetime(2026, 8, 6, 12, tzinfo=UTC)
    source.offer(_frame(1, node_session_id="conn-a"), received_at=received)
    source.pop_latest(now=received)
    source.offer(_frame(1, generation="generation-b", node_session_id="conn-b"), received_at=received + timedelta(seconds=1))
    packet = source.pop_latest(now=received + timedelta(seconds=1))
    assert packet is not None
    assert source.status().generation_resets == 1
    assert source.status().transport_reconnect_count == 1  # the connection itself still changed
    assert source.status().current_connection_segment_ordinal == 0  # segment numbering restarts fresh
    assert packet.source_offset_ms == 0
