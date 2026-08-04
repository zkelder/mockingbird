from __future__ import annotations

from datetime import UTC, datetime, timedelta
import asyncio
import hashlib
from io import BytesIO

import pytest
from fastapi import HTTPException

from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    LiveCameraNodeShadowSession,
    CameraNodeHttpTransport,
    _analysis_envelope,
    _jpeg_dimensions,
)
from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    AnalysisStreamCapability,
    EvidenceBurstCapability,
    EvidenceBurstFrame,
    EvidenceBurstResult,
    EvidenceBurstRequest,
)
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
) -> AnalysisFrameEnvelope:
    captured = captured_at or datetime(2026, 8, 4, tzinfo=UTC) + timedelta(milliseconds=sequence * 200)
    digest = hashlib.sha256(payload).hexdigest()
    return AnalysisFrameEnvelope(
        stream_id="stream-yard",
        node_session_id="node-session-a",
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
    assert [item.role for item in first.evidence_candidates] == ["high_resolution_burst"]
    assert first.creates_truth is False
    assert session.status().production_proposal_authority is False
    session.stop()
    assert transport.closed is True
    assert session.status().state == "stopped"


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
