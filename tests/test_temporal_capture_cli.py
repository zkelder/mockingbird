"""Hardware-free tests for the Stage 6.6 `temporal-capture` CLI: the bounded
retention loop (`_CaptureLoop._process_result`, tested directly to avoid
concurrency/coalescing nondeterminism) and full CLI wiring with a fake
Camera Node transport and a fake ONNX Runtime session. No real network
connection, GPU, or product database is touched. Numbered sections mirror
the task's required hardware-free-test list.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image, ImageDraw

from mockingbird.observation.contracts import (
    DetectionObservation,
    EvidenceCandidate,
    FramePacket,
    ObservationResult,
    TrackUpdate,
)
from mockingbird.observation.media_contracts import AnalysisFrameEnvelope, EvidenceBurstResult
from mockingbird.observation.onnx_provider import BUNDLE_SCHEMA_VERSION
from mockingbird.observation.temporal_capture import (
    STOP_HIGH_RESOLUTION_LIMIT,
    TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY,
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_OPERATOR_MARKER,
    TRIGGER_POST_TRIGGER_CONTEXT,
    TRIGGER_PRETRIGGER_CONTEXT,
    CaptureBounds,
)
from mockingbird.observation.temporal_capture_cli import _CaptureLoop, run_capture
from mockingbird.observation.temporal_capture_io import write_operator_marker


def _jpeg(color: tuple[int, int, int], *, box=None) -> bytes:
    image = Image.new("RGB", (320, 240), color=color)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=(255, 255, 255))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _packet(frame_id: str, *, payload: bytes, offset_ms: int = 0, generation: str = "gen-a", sequence: int = 0, received_at=None) -> FramePacket:
    return FramePacket(
        stream_id="stream-1", media_asset_id=f"shadow-frame:{frame_id}", captured_at=datetime(2026, 8, 5, tzinfo=UTC) + timedelta(milliseconds=offset_ms),
        frame_id=frame_id, source_offset_ms=offset_ms, width=320, height=240, payload=payload,
        frame_sequence=sequence, provider_generation=generation, received_at=received_at or datetime.now(UTC),
    )


def _result(frame: FramePacket, *, detections=(), track_updates=(), evidence_candidates=()) -> ObservationResult:
    return ObservationResult(
        "frame-driven-onnx-cuda", "live_shadow", frame.stream_id, frame.captured_at,
        frame_packets=(frame,), detection_observations=detections, track_updates=track_updates,
        evidence_candidates=evidence_candidates,
    )


def _det(box, score) -> DetectionObservation:
    return DetectionObservation("fixture", "animal", score, datetime.now(UTC), bounding_box=box, is_animal=True)


def _track(generation_id="track-1", lifecycle="confirmed") -> TrackUpdate:
    return TrackUpdate(track_id="t1", generation_id=generation_id, captured_at=datetime.now(UTC), status="started", lifecycle_state=lifecycle, bounding_box=(0.1, 0.1, 0.2, 0.2))


def _loop(tmp_path: Path, **bound_overrides) -> _CaptureLoop:
    fake_session = SimpleNamespace(provider=SimpleNamespace(active_track_count=0))
    return _CaptureLoop(
        session=fake_session, output_directory=tmp_path, bounds=CaptureBounds(**bound_overrides),
        shadow_operating_point=0.5, review_floor=0.1, privacy_regions=(),
    )


# --------------------------------------------------------------------------
# 4. Pretrigger and post-trigger retention
# --------------------------------------------------------------------------


def test_pretrigger_frames_are_retained_once_a_later_frame_triggers(tmp_path: Path) -> None:
    # max_periodic_negative_samples=0 isolates pretrigger-context retention
    # from the scheduler's own always-fires-on-the-first-call baseline sample.
    loop = _loop(tmp_path, pretrigger_frame_count=2, post_trigger_frame_count=0, max_periodic_negative_samples=0)
    blank = _jpeg((30, 30, 30))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0)))
    loop._process_result(_result(_packet("f1", payload=blank, offset_ms=500, sequence=1)))
    # f2 triggers on a real animal detection.
    loop._process_result(_result(
        _packet("f2", payload=blank, offset_ms=1000, sequence=2),
        detections=(_det((0.1, 0.1, 0.2, 0.2), 0.9),),
    ))
    retained_ids = [item.frame_id for item in loop.retained]
    assert retained_ids == ["f0", "f1", "f2"]
    assert TRIGGER_PRETRIGGER_CONTEXT in loop.retained[0].trigger_reasons
    assert TRIGGER_PRETRIGGER_CONTEXT in loop.retained[1].trigger_reasons


def test_post_trigger_frames_are_retained_for_the_configured_count(tmp_path: Path) -> None:
    loop = _loop(tmp_path, pretrigger_frame_count=0, post_trigger_frame_count=2, periodic_negative_interval_seconds=3600)
    blank = _jpeg((30, 30, 30))
    loop._process_result(_result(
        _packet("f0", payload=blank, offset_ms=0, sequence=0),
        detections=(_det((0.1, 0.1, 0.2, 0.2), 0.9),),
    ))
    loop._process_result(_result(_packet("f1", payload=blank, offset_ms=500, sequence=1)))
    loop._process_result(_result(_packet("f2", payload=blank, offset_ms=1000, sequence=2)))
    loop._process_result(_result(_packet("f3", payload=blank, offset_ms=1500, sequence=3)))
    retained_ids = [item.frame_id for item in loop.retained]
    assert retained_ids == ["f0", "f1", "f2"]
    assert loop.retained[1].trigger_reasons == (TRIGGER_POST_TRIGGER_CONTEXT,)
    assert loop.retained[2].trigger_reasons == (TRIGGER_POST_TRIGGER_CONTEXT,)
    assert "f3" not in retained_ids


# --------------------------------------------------------------------------
# 8. Operator marker without detector activity
# --------------------------------------------------------------------------


def test_operator_marker_alone_retains_a_frame_with_zero_detections(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    # max_periodic_negative_samples=0 isolates the marker trigger from the
    # scheduler's own always-fires-on-the-first-call baseline sample.
    loop = _loop(tmp_path, max_periodic_negative_samples=0)
    # The marker is logged a few seconds *after* the frame it refers to
    # ("wildlife was visible") -- realistic operator timing, and required by
    # markers_near's own backward-looking lookback semantics.
    frame_received_at = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    marker_time = frame_received_at + timedelta(seconds=5)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "wildlife_visible_now", marker_time.isoformat(), lookback_seconds=60))
    loop._refresh_markers()  # normally done once per batch inside _CaptureLoop.run()
    blank = _jpeg((30, 30, 30))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=frame_received_at)))
    assert len(loop.retained) == 1
    assert TRIGGER_OPERATOR_MARKER in loop.retained[0].trigger_reasons
    assert loop.retained[0].animal_detection_count == 0


# --------------------------------------------------------------------------
# 9. Exactly bounded high-resolution burst retention
# --------------------------------------------------------------------------


def test_high_resolution_burst_evidence_marks_the_frame_high_resolution(tmp_path: Path) -> None:
    loop = _loop(tmp_path)
    blank = _jpeg((30, 30, 30))
    candidate = EvidenceCandidate(media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst", captured_at=datetime.now(UTC))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), evidence_candidates=(candidate,)))
    assert len(loop.retained) == 1
    assert loop.retained[0].high_resolution is True
    assert TRIGGER_HIGH_RESOLUTION_BURST in loop.retained[0].trigger_reasons
    assert (tmp_path / "high-resolution" / "f0.jpg").is_file()


def test_bounds_exceeded_reports_high_resolution_limit(tmp_path: Path) -> None:
    loop = _loop(tmp_path, max_high_resolution_frames=1)
    blank = _jpeg((30, 30, 30))
    candidate = EvidenceCandidate(media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst", captured_at=datetime.now(UTC))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), evidence_candidates=(candidate,)))
    assert loop._bounds_exceeded() == STOP_HIGH_RESOLUTION_LIMIT


# --------------------------------------------------------------------------
# 10. Sequence-gap recording (source-level; exercised via CameraNodeAnalysisSource itself)
# --------------------------------------------------------------------------


def test_sequence_gap_is_visible_on_the_analysis_source_status() -> None:
    from mockingbird.observation.camera_node_live import CameraNodeAnalysisSource

    source = CameraNodeAnalysisSource("stream-1")
    payload = _jpeg((10, 10, 10))
    digest = hashlib.sha256(payload).hexdigest()

    def envelope(sequence: int) -> AnalysisFrameEnvelope:
        return AnalysisFrameEnvelope(
            stream_id="stream-1", node_session_id="node-1", sequence=sequence, frame_id=f"f{sequence}",
            captured_at=datetime(2026, 8, 5, tzinfo=UTC) + timedelta(seconds=sequence), source_monotonic_ns=sequence * 10**9,
            width=320, height=240, content_type="image/jpeg", provider_generation="gen-a", payload=payload, content_hash=digest,
        )

    source.offer(envelope(0))
    source.offer(envelope(3))  # two-frame gap
    assert source.status().sequence_gaps == 2


# --------------------------------------------------------------------------
# 11. Provider-generation reset
# --------------------------------------------------------------------------


def test_generation_change_clears_pretrigger_and_plane_cache_and_adds_discontinuity_trigger(tmp_path: Path) -> None:
    loop = _loop(tmp_path, pretrigger_frame_count=2, periodic_negative_interval_seconds=3600)
    blank = _jpeg((30, 30, 30))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, generation="gen-a")))
    assert loop.last_frame_id == "f0"
    loop._process_result(_result(_packet("f1", payload=blank, offset_ms=1000, sequence=1, generation="gen-b")))
    assert loop.generation_reset_count == 1
    assert len(loop.pretrigger) <= 1  # cleared, then this frame itself may requeue as pretrigger context
    retained = [item for item in loop.retained if item.frame_id == "f1"]
    assert retained and TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY in retained[0].trigger_reasons


def test_generation_change_prevents_a_motion_proposal_across_the_boundary(tmp_path: Path) -> None:
    loop = _loop(tmp_path, periodic_negative_interval_seconds=3600)
    blank = _jpeg((30, 30, 30))
    changed = _jpeg((30, 30, 30), box=(120, 90, 180, 150))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, generation="gen-a")))
    loop._process_result(_result(_packet("f1", payload=changed, offset_ms=1000, sequence=1, generation="gen-b")))
    retained = [item for item in loop.retained if item.frame_id == "f1"]
    assert retained
    assert retained[0].motion_proposal_count == 0


# --------------------------------------------------------------------------
# 12. Duplicate-frame identity handling
# --------------------------------------------------------------------------


def test_retaining_the_same_frame_id_twice_does_not_duplicate_or_double_write(tmp_path: Path) -> None:
    loop = _loop(tmp_path)
    blank = _jpeg((30, 30, 30))
    detections = (_det((0.1, 0.1, 0.2, 0.2), 0.9),)
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), detections=detections))
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), detections=detections))
    assert len(loop.retained) == 1


# --------------------------------------------------------------------------
# 35. Bounds hold in memory and on disk
# --------------------------------------------------------------------------


def test_plane_cache_never_exceeds_its_bound(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture_cli import MAX_PLANE_CACHE
    loop = _loop(tmp_path, periodic_negative_interval_seconds=3600)
    blank = _jpeg((30, 30, 30))
    for index in range(MAX_PLANE_CACHE + 5):
        loop._process_result(_result(_packet(f"f{index}", payload=blank, offset_ms=index * 200, sequence=index)))
    assert len(loop.plane_cache) <= MAX_PLANE_CACHE


def test_retained_frames_never_exceed_the_configured_analysis_frame_bound(tmp_path: Path) -> None:
    loop = _loop(tmp_path, max_analysis_frames=2, periodic_negative_interval_seconds=1)
    blank = _jpeg((30, 30, 30))
    for index in range(5):
        loop._process_result(_result(_packet(f"f{index}", payload=blank, offset_ms=index * 2000, sequence=index)))
        if loop._bounds_exceeded():
            break
    assert len(loop.retained) <= 2


# --------------------------------------------------------------------------
# 33/34. No product repository, truth-write, or product-record dependency
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", [
    "mockingbird.observation.temporal_capture",
    "mockingbird.observation.temporal_capture_io",
    "mockingbird.observation.temporal_capture_cli",
    "mockingbird.observation.temporal_annotation",
    "mockingbird.observation.temporal_review_io",
    "mockingbird.observation.temporal_review_cli",
])
def test_stage_6_6_modules_never_reference_product_truth_tables(module_name: str) -> None:
    import importlib
    module = importlib.import_module(module_name)
    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.persistence", "sqlalchemy", "mockingbird.api.main",
        "ReviewLabel(", "MotionEvidence(", "class Event(", "class Visit(", "class MediaAsset(",
    )
    for token in forbidden:
        assert token not in source, f"{module_name} references {token}"


# --------------------------------------------------------------------------
# 15. Clean stop releases stream and temporary state + full CLI wiring
# --------------------------------------------------------------------------


class FakeSession:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def get_providers(self):
        return ["CUDAExecutionProvider"]

    def run(self, outputs, inputs):
        self.calls.append((outputs, inputs))
        return self.outputs

    def execution_assignment(self):
        return {"classification": "cuda_only_verified", "cuda_executed_nodes": max(1, len(self.calls)), "cpu_executed_nodes": 0, "unknown_executed_nodes": 0}

    def close(self):
        pass


class FakeRuntime:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def available_providers(self):
        return ("CUDAExecutionProvider",)

    def create_session(self, model_path, *, input_name, output_names):
        return self._session_factory()


def _no_detections_output():
    return np.asarray([[[0.0, 0.0, 1.0, 1.0, 0.01, 0]]], dtype=np.float32)


class FakeTransport:
    def __init__(self, frames):
        self._frames = list(frames)
        self.closed = False

    def iter_analysis_frames(self, *, maximum_frames: int):
        batch = self._frames[:maximum_frames]
        self._frames = self._frames[maximum_frames:]
        return iter(batch)

    def request_evidence_burst(self, request):
        return EvidenceBurstResult(request.request_id, "failed", failure_code="fixture_no_burst")

    def close(self):
        self.closed = True


def _bundle_dir(tmp_path: Path) -> Path:
    config_dir = tmp_path / "provider-config"
    config_dir.mkdir()
    model = config_dir / "detector.onnx"
    model.write_bytes(b"fake-onnx-model")
    payload = {
        "schema_version": BUNDLE_SCHEMA_VERSION, "model_key": "fixture", "model_version": "1",
        "model_file": model.name, "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "model_format": "ONNX", "license": "fixture-only", "redistribution": "not-redistributable",
        "input_name": "images", "input_width": 4, "input_height": 4, "input_dtype": "float32",
        "input_scale": 0.0039, "channel_order": "NCHW", "color_format": "RGB", "letterbox_fill": [114, 114, 114],
        "normalization_mean": [0.0, 0.0, 0.0], "normalization_std": [1.0, 1.0, 1.0], "resize_mode": "letterbox",
        "output_names": ["detections"], "decoder_key": "xyxy-score-class-v1",
        "broad_classes": ["animal", "person", "vehicle"], "animal_classes": ["animal"],
        "taxonomy": "fixture", "provenance": "fixture", "provider_compatibility": ["onnx-cuda"],
        "limitations": ["fixture"], "score_threshold": 0.02, "max_observations_per_frame": 10,
    }
    (config_dir / "bundle.json").write_text(json.dumps(payload))
    frame_driven_payload = {
        "schema_version": 1, "model_bundle": "bundle.json",
        "settings": {
            "source_nominal_fps": 5, "baseline_detector_fps": 5, "candidate_detector_fps": 5,
            "strong_detection_threshold": 0.5, "minimum_detector_confirmations": 1,
            "minimum_tracker_support_frames": 1, "maximum_missed_frames": 2, "maximum_frame_gap_ms": 2000,
            "tracker_expiry_ms": 2000, "maximum_track_duration_ms": 30000, "maximum_active_tracks": 8,
            "evidence_ring_size": 4, "pretrigger_frame_count": 1,
        },
    }
    (config_dir / "frame-driven-config.json").write_text(json.dumps(frame_driven_payload))
    return config_dir


def _camera_node_config(tmp_path: Path) -> Path:
    payload = {
        "base_address": "http://192.0.2.1:8787", "credential": "fixture-credential-value",
        "camera_id": "camera-0", "stream_id": "stream-fixture", "evidence_profile_id": "profile-1",
    }
    path = tmp_path / "camera-node-config.json"
    path.write_text(json.dumps(payload))
    return path


def test_run_capture_end_to_end_stops_cleanly_and_writes_no_credential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import mockingbird.observation.onnx_provider as onnx_provider_module
    import mockingbird.observation.temporal_capture_cli as cli_module

    monkeypatch.setattr(onnx_provider_module, "OptionalOrtCudaRuntime", lambda: FakeRuntime(lambda: FakeSession([_no_detections_output()])))

    config_dir = _bundle_dir(tmp_path)
    camera_node_config = _camera_node_config(tmp_path)

    payload = _jpeg((20, 20, 20))
    digest = hashlib.sha256(payload).hexdigest()
    frames = [AnalysisFrameEnvelope(
        stream_id="stream-fixture", node_session_id="node-session-fixture", sequence=0,
        frame_id=f"gen-a:0:{digest[:8]}", captured_at=datetime(2026, 8, 5, tzinfo=UTC),
        source_monotonic_ns=0, width=320, height=240, content_type="image/jpeg",
        provider_generation="gen-a", payload=payload, content_hash=digest,
    )]
    fake_transport = FakeTransport(frames)
    monkeypatch.setattr(cli_module, "CameraNodeHttpTransport", lambda **kwargs: fake_transport)

    destination = tmp_path / "capture-out"
    exit_code = run_capture([
        "--camera-node-config", str(camera_node_config), "--provider", "frame-driven-onnx-cuda",
        "--provider-config", str(config_dir / "frame-driven-config.json"), "--output", str(destination),
        "--duration", "5",
    ])
    assert exit_code == 0
    assert fake_transport.closed is True  # clean stop releases the transport
    manifest_text = (destination / "capture-session-manifest.json").read_text()
    assert "fixture-credential-value" not in manifest_text
    assert str(tmp_path) not in manifest_text
    manifest = json.loads(manifest_text)
    assert manifest["creates_truth"] is False
    assert manifest["production_proposal_authority"] is False


class FakeTransportWithBurst(FakeTransport):
    def __init__(self, frames, *, burst_payload: bytes):
        super().__init__(frames)
        self._burst_payload = burst_payload
        self.burst_requests = []

    def request_evidence_burst(self, request):
        self.burst_requests.append(request)
        from mockingbird.observation.media_contracts import EvidenceBurstFrame
        digest = hashlib.sha256(self._burst_payload).hexdigest()
        frame = EvidenceBurstFrame(
            sequence=1, captured_at=request.trigger_captured_at, width=320, height=240,
            content_type="image/jpeg", content_hash=digest, payload=self._burst_payload,
            parent_frame_id=request.trigger_frame_id, provider_generation="validation-gen",
            request_to_capture_ms=5, temporal_alignment="supported",
        )
        return EvidenceBurstResult(request.request_id, "captured", (frame,))


def test_validation_burst_retains_one_explicitly_labeled_high_resolution_frame_with_no_wildlife(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import mockingbird.observation.onnx_provider as onnx_provider_module
    import mockingbird.observation.temporal_capture_cli as cli_module

    monkeypatch.setattr(onnx_provider_module, "OptionalOrtCudaRuntime", lambda: FakeRuntime(lambda: FakeSession([_no_detections_output()])))

    config_dir = _bundle_dir(tmp_path)
    camera_node_config = _camera_node_config(tmp_path)
    burst_payload = _jpeg((5, 5, 5))
    fake_transport = FakeTransportWithBurst([], burst_payload=burst_payload)
    monkeypatch.setattr(cli_module, "CameraNodeHttpTransport", lambda **kwargs: fake_transport)

    destination = tmp_path / "capture-out-burst"
    exit_code = run_capture([
        "--camera-node-config", str(camera_node_config), "--provider", "frame-driven-onnx-cuda",
        "--provider-config", str(config_dir / "frame-driven-config.json"), "--output", str(destination),
        "--duration", "5", "--validation-burst",
    ])
    assert exit_code == 0
    assert len(fake_transport.burst_requests) == 1
    manifest = json.loads((destination / "capture-session-manifest.json").read_text())
    validation_frames = [item for item in manifest["frames"] if item["frame_id"].startswith("validation-burst-")]
    assert len(validation_frames) == 1
    assert validation_frames[0]["high_resolution"] is True
    assert validation_frames[0]["trigger_reasons"] == ["high_resolution_burst"]
    assert validation_frames[0]["animal_detection_count"] == 0  # never represents wildlife
    assert (destination / "high-resolution" / f"{validation_frames[0]['frame_id']}.jpg").is_file()


# --------------------------------------------------------------------------
# Reconnect resilience: a fresh transport connection per batch is expected
# to reset the Node's own per-connection sequence counter (observed against
# real hardware); the loop must recover with a fresh source rather than
# aborting the whole bounded capture.
# --------------------------------------------------------------------------


def test_run_recovers_from_a_sequence_reset_by_rebuilding_the_source(tmp_path: Path) -> None:
    from mockingbird.observation.camera_node_live import CameraNodeAnalysisSource
    from mockingbird.observation.temporal_capture_cli import MAX_CONSECUTIVE_RECONNECTS

    restart_calls = []
    fake_provider = SimpleNamespace(
        active_track_count=0,
        restart_live_generation=lambda stream_id, reason: restart_calls.append((stream_id, reason)),
    )
    calls = {"count": 0}

    class RaisingThenWorkingSession:
        def __init__(self) -> None:
            self.source = CameraNodeAnalysisSource("stream-1")
            self.provider = fake_provider

        async def run(self, *, maximum_frames: int):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ValueError("analysis_frame_sequence")
            return ()  # second attempt: clean stream-ended stop

    session = RaisingThenWorkingSession()
    loop = _CaptureLoop(session=session, output_directory=tmp_path, bounds=CaptureBounds(), shadow_operating_point=0.5, review_floor=0.1, privacy_regions=())
    original_source = session.source
    import asyncio
    result = asyncio.run(loop.run(started_wall=datetime.now(UTC), duration_seconds=30))
    assert result == "stream_ended"
    assert calls["count"] == 2
    assert session.source is not original_source  # rebuilt, not reused
    assert calls["count"] <= MAX_CONSECUTIVE_RECONNECTS + 1
    # The provider's live tracker must also be restarted against the fresh
    # source, or its stale offset tracking treats the next frame as going
    # backwards in time (the real-hardware failure mode this recovers from).
    assert restart_calls == [("stream-1", "capture_transport_reconnect")]
    assert loop.generation_reset_count == 1


def test_run_recovers_from_a_non_monotonic_tracking_frame_after_reconnect(tmp_path: Path) -> None:
    """Confirmed against the real Camera Node: its per-connection sequence
    header restarts at 1 on every fresh connection while
    provider_generation stays unchanged. A rebuilt source re-zeroes
    source_offset_ms, which -- if the provider's live tracker is not also
    restarted -- makes the very next frame look like it goes backwards in
    time, raising `ReplayValidationError("non_monotonic_tracking_frame")`
    (a ValueError subclass) from deeper inside `session.run()` than the
    plain sequence-reset case. This must be recovered the same way."""
    from mockingbird.observation.camera_node_live import CameraNodeAnalysisSource
    from mockingbird.observation.replay import ReplayValidationError

    restart_calls = []
    fake_provider = SimpleNamespace(
        active_track_count=0,
        restart_live_generation=lambda stream_id, reason: restart_calls.append((stream_id, reason)),
    )
    calls = {"count": 0}

    class RaisingThenWorkingSession:
        def __init__(self) -> None:
            self.source = CameraNodeAnalysisSource("stream-1")
            self.provider = fake_provider

        async def run(self, *, maximum_frames: int):
            calls["count"] += 1
            if calls["count"] == 1:
                raise ReplayValidationError("non_monotonic_tracking_frame")
            return ()

    session = RaisingThenWorkingSession()
    loop = _CaptureLoop(session=session, output_directory=tmp_path, bounds=CaptureBounds(), shadow_operating_point=0.5, review_floor=0.1, privacy_regions=())
    loop.last_frame_id = "some-frame-before-the-reconnect"
    original_source = session.source
    import asyncio
    result = asyncio.run(loop.run(started_wall=datetime.now(UTC), duration_seconds=30))
    assert result == "stream_ended"
    assert calls["count"] == 2
    assert session.source is not original_source
    assert restart_calls == [("stream-1", "capture_transport_reconnect")]
    assert loop.generation_reset_count == 1
    # The pre-reconnect frame is not a valid motion-proposal predecessor for
    # whatever arrives after the gap.
    assert loop.last_frame_id is None


# --------------------------------------------------------------------------
# Periodic negative sampling must survive reconnects: observed against real
# hardware, source_offset_ms is zeroed against each transport connection's
# first frame (see the reconnect-resilience section above), so on a real
# capture -- where a fresh connection is the normal outcome of every batch
# boundary -- it rarely climbs far enough within one connection's lifetime
# to ever cross periodic_negative_interval_seconds. The scheduler must be
# driven by the host receive clock instead.
# --------------------------------------------------------------------------


def test_periodic_negative_sample_fires_on_host_clock_even_when_source_offset_resets(tmp_path: Path) -> None:
    loop = _loop(tmp_path, periodic_negative_interval_seconds=30, max_periodic_negative_samples=5)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    # f0: bootstrap sample (the scheduler always fires on its first call).
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=base)))
    assert loop.retained[-1].frame_id == "f0"
    # f1: simulates the first frame of a reconnected source -- offset_ms
    # resets to near zero (just like a real fresh connection), but only 5
    # real seconds have passed, well under the 30s interval.
    loop._process_result(_result(_packet("f1", payload=blank, offset_ms=100, sequence=0, received_at=base + timedelta(seconds=5))))
    assert all(item.frame_id != "f1" for item in loop.retained)  # not (yet) retained: too soon
    # f2: another reconnect-reset offset, but 40 real seconds after f0 --
    # past the 30s interval. Must fire even though offset_ms is tiny again.
    loop._process_result(_result(_packet("f2", payload=blank, offset_ms=50, sequence=0, received_at=base + timedelta(seconds=40))))
    retained_ids = [item.frame_id for item in loop.retained]
    assert "f2" in retained_ids
    from mockingbird.observation.temporal_capture import TRIGGER_PERIODIC_NEGATIVE_SAMPLE
    f2 = next(item for item in loop.retained if item.frame_id == "f2")
    assert TRIGGER_PERIODIC_NEGATIVE_SAMPLE in f2.trigger_reasons


def test_periodic_negative_sample_does_not_fire_from_source_offset_alone(tmp_path: Path) -> None:
    # A large source_offset_ms gap with almost no real elapsed host time
    # (e.g. a burst of buffered frames delivered in a tight loop) must not,
    # by itself, trigger a periodic sample.
    loop = _loop(tmp_path, periodic_negative_interval_seconds=30, max_periodic_negative_samples=5)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=base)))
    loop._process_result(_result(_packet(
        "f1", payload=blank, offset_ms=60_000, sequence=1, received_at=base + timedelta(milliseconds=10),
    )))
    assert all(item.frame_id != "f1" for item in loop.retained)


# --------------------------------------------------------------------------
# Retroactive operator-marker rescue: confirmed against real hardware that
# `_refresh_markers()` only runs at a batch boundary, immediately *before*
# fetching new (future) frames -- so a marker discovered there can never
# correlate to anything about to be received (markers_near only looks
# backward). It can only ever rescue frames that were already processed,
# under the stale marker set, in an earlier batch.
# --------------------------------------------------------------------------


def test_marker_discovered_after_a_frame_was_already_processed_retroactively_retains_it(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    # Isolate the rescue path: no periodic sampling competing for retention.
    loop = _loop(tmp_path, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    frame_received_at = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)

    # This mirrors the real sequence of events: the frame is processed with
    # no marker on disk yet (self.markers_seen is empty), so nothing fires
    # for it and it only lands in the rescue buffer.
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=frame_received_at)))
    assert loop.retained == []
    assert any(entry[0].frame_id == "f0" for entry in loop.recent_frames)

    # The operator marks a possible miss a few seconds later, referring
    # back to roughly when f0 was received.
    marker_time = frame_received_at + timedelta(seconds=5)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "uncertain_possible_wildlife", marker_time.isoformat(), lookback_seconds=20))

    # Only now -- at the next batch boundary -- does the loop discover it.
    loop._refresh_markers()

    retained_ids = [item.frame_id for item in loop.retained]
    assert retained_ids == ["f0"]
    assert TRIGGER_OPERATOR_MARKER in loop.retained[0].trigger_reasons
    assert loop.retained[0].animal_detection_count == 0
    # Post-trigger context should now be armed for frames arriving next.
    assert loop.post_trigger_remaining == loop.bounds.post_trigger_frame_count


def test_marker_rescue_does_not_retain_frames_outside_its_lookback_window(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    loop = _loop(tmp_path, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=base)))

    # Marker refers to a moment 60 real seconds after f0 -- well outside
    # even a generous 20s lookback.
    marker_time = base + timedelta(seconds=60)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "uncertain_possible_wildlife", marker_time.isoformat(), lookback_seconds=20))
    loop._refresh_markers()

    assert loop.retained == []


def test_recent_frames_rescue_buffer_never_exceeds_its_bound(tmp_path: Path) -> None:
    loop = _loop(tmp_path, adjacent_context_frame_count=3, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    for index in range(10):
        loop._process_result(_result(_packet(
            f"f{index}", payload=blank, offset_ms=index * 500, sequence=index, received_at=base + timedelta(seconds=index),
        )))
    assert len(loop.recent_frames) <= 3
    assert [entry[0].frame_id for entry in loop.recent_frames] == ["f7", "f8", "f9"]


def test_adjacent_context_frame_count_zero_disables_marker_rescue(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    loop = _loop(tmp_path, adjacent_context_frame_count=0, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=base)))
    assert len(loop.recent_frames) == 0  # nothing kept: rescue is off

    marker_time = base + timedelta(seconds=5)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "uncertain_possible_wildlife", marker_time.isoformat(), lookback_seconds=20))
    loop._refresh_markers()
    assert loop.retained == []
