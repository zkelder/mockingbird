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
    STOP_FRAME_LIMIT,
    STOP_HIGH_RESOLUTION_LIMIT,
    STOP_TRANSPORT_ERROR,
    TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY,
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_OPERATOR_MARKER,
    TRIGGER_POST_TRIGGER_CONTEXT,
    TRIGGER_PRETRIGGER_CONTEXT,
    CaptureBounds,
)
from mockingbird.observation.temporal_capture_cli import _CaptureLoop, run_capture
from mockingbird.observation.temporal_capture_io import write_operator_marker
from mockingbird.source_providers.camera_node import CameraNodeClientError


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


class _FakeBurstSession:
    """Stand-in for `LiveCameraNodeShadowSession`: the real burst payload
    bytes a captured evidence-burst already fetched live only ever exist in
    that session's own bounded `temporary_burst_payload` cache (see
    `_retain_high_resolution_evidence`) -- never on `EvidenceCandidate`
    itself. Tests populate `payloads` to simulate a payload still being
    cached, and leave a hash absent to simulate one already evicted."""

    def __init__(self) -> None:
        self.provider = SimpleNamespace(active_track_count=0)
        self.payloads: dict[str, bytes] = {}

    def temporary_burst_payload(self, content_hash: str) -> bytes | None:
        return self.payloads.get(content_hash)


def _loop(tmp_path: Path, **bound_overrides) -> _CaptureLoop:
    fake_session = _FakeBurstSession()
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
    burst_payload = _jpeg((9, 9, 9))
    burst_hash = hashlib.sha256(burst_payload).hexdigest()
    loop.session.payloads[burst_hash] = burst_payload
    candidate = EvidenceCandidate(
        media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), quality_facts=(("content_hash", burst_hash),),
    )
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), evidence_candidates=(candidate,)))
    # Two retained records: the low-resolution trigger frame itself (never
    # high-resolution -- see test_high_resolution_evidence_retains_the_real_burst_payload...
    # below) plus the dedicated high-resolution record for the captured burst.
    assert len(loop.retained) == 2
    high_res = [item for item in loop.retained if item.high_resolution]
    assert len(high_res) == 1
    assert TRIGGER_HIGH_RESOLUTION_BURST in high_res[0].trigger_reasons
    assert (tmp_path / "high-resolution" / f"{high_res[0].frame_id}.jpg").is_file()
    low_res = [item for item in loop.retained if item.frame_id == "f0"][0]
    assert low_res.high_resolution is False
    assert TRIGGER_HIGH_RESOLUTION_BURST in low_res.trigger_reasons  # context is preserved


def test_bounds_exceeded_reports_high_resolution_limit(tmp_path: Path) -> None:
    loop = _loop(tmp_path, max_high_resolution_frames=1)
    blank = _jpeg((30, 30, 30))
    burst_payload = _jpeg((9, 9, 9))
    burst_hash = hashlib.sha256(burst_payload).hexdigest()
    loop.session.payloads[burst_hash] = burst_payload
    candidate = EvidenceCandidate(
        media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), quality_facts=(("content_hash", burst_hash),),
    )
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), evidence_candidates=(candidate,)))
    assert loop._bounds_exceeded() == STOP_HIGH_RESOLUTION_LIMIT


def test_high_resolution_evidence_retains_the_real_burst_payload_not_the_analysis_frame(tmp_path: Path) -> None:
    """Integration/accounting defect (session-01, 2026-08-07): every live
    high-resolution retention wrote `frame.payload` -- the low-resolution
    analysis-stream bytes that merely triggered the burst -- because the
    real bytes `request_evidence_burst` fetched from the Camera Node are
    never carried on `EvidenceCandidate` and nothing downstream of
    `_process_result` ever read the live session's own
    `temporary_burst_payload` cache to recover them. Confirmed against the
    real session-01 capture: 31/32 retained "high-resolution" files on disk
    were the same 1920x1440 analysis resolution as every ordinary low-res
    frame; only the separately-coded validation-burst frame was genuinely
    4624x3472."""
    loop = _loop(tmp_path)
    analysis_payload = _jpeg((30, 30, 30))
    burst_payload = _jpeg((250, 5, 5))  # deliberately distinct bytes from the analysis frame
    burst_hash = hashlib.sha256(burst_payload).hexdigest()
    assert burst_hash != hashlib.sha256(analysis_payload).hexdigest()
    loop.session.payloads[burst_hash] = burst_payload
    candidate = EvidenceCandidate(
        media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), frame_id="f0", track_generation_id="track-1",
        quality_facts=(("content_hash", burst_hash),),
    )
    loop._process_result(_result(
        _packet("f0", payload=analysis_payload, offset_ms=0, sequence=0), evidence_candidates=(candidate,),
    ))
    high_res = [item for item in loop.retained if item.high_resolution]
    assert len(high_res) == 1
    written = (tmp_path / "high-resolution" / f"{high_res[0].frame_id}.jpg").read_bytes()
    assert written == burst_payload
    assert written != analysis_payload
    assert high_res[0].content_hash == burst_hash


def test_two_simultaneous_captured_bursts_on_one_frame_are_both_retained_and_counted(tmp_path: Path) -> None:
    """Integration/accounting defect: two simultaneous meaningful track
    updates on the same processed analysis frame can each independently win
    their own scheduler-issued, Camera-Node-captured burst (confirmed
    structurally possible in session-01: 14/32 retained high-resolution
    frames had active_track_count >= 2). Before the fix, `_process_result`
    folded every evidence candidate for one processed frame into a single
    boolean, so only one of the two captured bursts was ever retained or
    counted toward `max_high_resolution_frames` -- the other was silently
    discarded with no trace in the manifest."""
    loop = _loop(tmp_path, max_high_resolution_frames=2)
    analysis_payload = _jpeg((30, 30, 30))
    payload_a, payload_b = _jpeg((250, 5, 5)), _jpeg((5, 250, 5))
    hash_a, hash_b = hashlib.sha256(payload_a).hexdigest(), hashlib.sha256(payload_b).hexdigest()
    loop.session.payloads[hash_a] = payload_a
    loop.session.payloads[hash_b] = payload_b
    candidate_a = EvidenceCandidate(
        media_asset_id="shadow-burst:a", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), frame_id="f0", track_generation_id="track-a",
        quality_facts=(("content_hash", hash_a),),
    )
    candidate_b = EvidenceCandidate(
        media_asset_id="shadow-burst:b", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), frame_id="f0", track_generation_id="track-b",
        quality_facts=(("content_hash", hash_b),),
    )
    loop._process_result(_result(
        _packet("f0", payload=analysis_payload, offset_ms=0, sequence=0),
        evidence_candidates=(candidate_a, candidate_b),
    ))
    high_res = [item for item in loop.retained if item.high_resolution]
    assert len(high_res) == 2
    assert {item.content_hash for item in high_res} == {hash_a, hash_b}
    # The cap must trip on the second real burst, not silently accept a
    # third without ever having "seen" the second.
    assert loop._bounds_exceeded() == STOP_HIGH_RESOLUTION_LIMIT


def test_high_resolution_evidence_without_a_recoverable_payload_is_not_fabricated(tmp_path: Path) -> None:
    """An evidence candidate whose real bytes are no longer cached (or whose
    session cannot supply them at all) must never be retained using
    substitute bytes -- honest omission, not a mislabeled duplicate."""
    loop = _loop(tmp_path)
    blank = _jpeg((30, 30, 30))
    candidate = EvidenceCandidate(
        media_asset_id="shadow-burst:x", stream_id="stream-1", role="high_resolution_burst",
        captured_at=datetime.now(UTC), quality_facts=(("content_hash", "not-cached-anymore"),),
    )
    loop._process_result(_result(_packet("f0", payload=blank, offset_ms=0, sequence=0), evidence_candidates=(candidate,)))
    assert [item.high_resolution for item in loop.retained] == [False]


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
    "mockingbird.observation.session_timeline",  # Stage 6.8
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
# Stage 6.11B: an ordinary HTTP reconnect -- a fresh transport connection
# per batch, resetting the Node's own per-connection sequence counter --
# no longer raises out of `session.run()` at all: CameraNodeAnalysisSource/
# FrameDrivenObservationProvider recognize and bridge it internally (see
# docs/reconnect-continuity-contract.md). This removes the Stage 6.6-era
# "rebuild the source and restart the provider's live generation" recovery
# entirely -- there is nothing left to recover from on a benign reconnect.
# Scenario 19 ("connection reopen failure reports health honestly"): a
# `session.run()` failure that still occurs (a genuine unrecoverable
# transport/source error, not an ordinary reconnect) now stops the capture
# cleanly and honestly rather than attempting a rebuild that no longer
# applies.
# --------------------------------------------------------------------------


def test_run_reports_health_honestly_on_a_genuine_unrecoverable_transport_error(tmp_path: Path) -> None:
    fake_provider = SimpleNamespace(active_track_count=0)
    calls = {"count": 0}

    class AlwaysRaisingSession:
        provider = fake_provider

        async def run(self, *, maximum_frames: int):
            calls["count"] += 1
            raise CameraNodeClientError("analysis_stream_unavailable")

    loop = _CaptureLoop(session=AlwaysRaisingSession(), output_directory=tmp_path, bounds=CaptureBounds(), shadow_operating_point=0.5, review_floor=0.1, privacy_regions=())
    import asyncio
    result = asyncio.run(loop.run(started_wall=datetime.now(UTC), duration_seconds=30))
    assert result == STOP_TRANSPORT_ERROR
    assert calls["count"] == 1  # stopped immediately, never silently retried
    assert loop.generation_reset_count == 0


def test_run_does_not_rebuild_the_source_or_restart_the_provider_on_an_ordinary_reconnect_error(tmp_path: Path) -> None:
    """A stray ValueError from `session.run()` (whatever its message) is now
    always a genuine, honestly-reported stop -- never a signal to rebuild
    the source/restart the provider, since an ordinary benign reconnect no
    longer produces one at all (see the real reconnect-flow test below for
    that proof)."""
    from mockingbird.observation.camera_node_live import CameraNodeAnalysisSource

    restart_calls = []
    fake_provider = SimpleNamespace(
        active_track_count=0,
        restart_live_generation=lambda stream_id, reason: restart_calls.append((stream_id, reason)),
    )
    calls = {"count": 0}

    class AlwaysRaisingSession:
        def __init__(self) -> None:
            self.source = CameraNodeAnalysisSource("stream-1")
            self.provider = fake_provider

        async def run(self, *, maximum_frames: int):
            calls["count"] += 1
            raise ValueError("analysis_frame_sequence")

    session = AlwaysRaisingSession()
    loop = _CaptureLoop(session=session, output_directory=tmp_path, bounds=CaptureBounds(), shadow_operating_point=0.5, review_floor=0.1, privacy_regions=())
    original_source = session.source
    import asyncio
    result = asyncio.run(loop.run(started_wall=datetime.now(UTC), duration_seconds=30))
    assert result == STOP_TRANSPORT_ERROR
    assert calls["count"] == 1
    assert session.source is original_source  # never rebuilt
    assert restart_calls == []  # never restarted
    assert loop.generation_reset_count == 0


class FakeTransportMultiConnection:
    """Serves one pre-built list of envelopes per call to
    `iter_analysis_frames`, exactly mirroring the real Camera Node contract
    that one call opens one HTTP connection (see `CameraNodeHttpTransport.
    iter_analysis_frames`): `FakeTransport` alone cannot exercise a real
    reconnect end-to-end because it slices one long combined list, which
    would only split at a connection boundary by coincidence."""

    def __init__(self, connections: list[list]) -> None:
        self._connections = list(connections)
        self.closed = False

    def iter_analysis_frames(self, *, maximum_frames: int):
        if not self._connections:
            return iter(())
        batch = self._connections.pop(0)
        return iter(batch[:maximum_frames])

    def request_evidence_burst(self, request):
        return EvidenceBurstResult(request.request_id, "failed", failure_code="fixture_no_burst")

    def close(self) -> None:
        self.closed = True


def _detecting_envelope(node_session_id: str, sequence: int, *, generation: str = "gen-a", captured_offset_ms: int = 0) -> AnalysisFrameEnvelope:
    payload = _jpeg((10, 10, 10), box=(20, 20, 80, 80))
    digest = hashlib.sha256(payload).hexdigest()
    return AnalysisFrameEnvelope(
        stream_id="stream-fixture", node_session_id=node_session_id, sequence=sequence,
        frame_id=f"{node_session_id}:{sequence}:{digest[:8]}",
        captured_at=datetime(2026, 8, 6, 12, 0, 0, tzinfo=UTC) + timedelta(milliseconds=captured_offset_ms),
        source_monotonic_ns=None, width=320, height=240, content_type="image/jpeg",
        provider_generation=generation, payload=payload, content_hash=digest,
    )


def test_run_capture_end_to_end_reconnect_produces_a_native_session_timeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full `run_capture` CLI flow across two real benign reconnects (real
    `CameraNodeAnalysisSource`/`LiveCameraNodeShadowSession`/
    `FrameDrivenObservationProvider`, only the transport faked): Stage
    6.11B means all three connection segments -- not just the first and
    third -- now retain frames, since a fresh connection under the same
    provider_generation no longer forces the loop to rebuild the source
    and drop whatever the reconnecting batch was carrying (the removed
    Stage 6.6-era failure mode). Every retained frame ends up with a
    unique, monotonic `session_sequence`, both boundary frames are flagged
    `temporal_discontinuity`, and the manifest is classified
    `native_session_timeline` since every frame carries a real per-
    connection id and host receive time. `generation_reset_count` -- a
    genuine source-generation reset count, not a transport-reconnect count
    -- stays 0: provider_generation never changes across any of the three
    connections."""
    import mockingbird.observation.onnx_provider as onnx_provider_module
    import mockingbird.observation.temporal_capture_cli as cli_module

    # A single strong "animal" detection (class index 0) on every inference
    # call is enough to retain every supplied frame via
    # TRIGGER_ANIMAL_ABOVE_OPERATING_POINT.
    detecting_output = np.asarray([[[0.2, 0.2, 0.8, 0.8, 0.9, 0]]], dtype=np.float32)
    monkeypatch.setattr(onnx_provider_module, "OptionalOrtCudaRuntime", lambda: FakeRuntime(lambda: FakeSession([detecting_output])))

    config_dir = _bundle_dir(tmp_path)
    camera_node_config = _camera_node_config(tmp_path)

    connection_one = [_detecting_envelope("node-session-one", seq, captured_offset_ms=seq * 500) for seq in range(3)]
    connection_two = [_detecting_envelope("node-session-two", seq, captured_offset_ms=seq * 500) for seq in range(2)]
    connection_three = [_detecting_envelope("node-session-three", seq, captured_offset_ms=seq * 500) for seq in range(3)]
    fake_transport = FakeTransportMultiConnection([connection_one, connection_two, connection_three])
    monkeypatch.setattr(cli_module, "CameraNodeHttpTransport", lambda **kwargs: fake_transport)

    destination = tmp_path / "capture-out-reconnect"
    exit_code = run_capture([
        "--camera-node-config", str(camera_node_config), "--provider", "frame-driven-onnx-cuda",
        "--provider-config", str(config_dir / "frame-driven-config.json"), "--output", str(destination),
        "--duration", "5",
    ])
    assert exit_code == 0
    manifest = json.loads((destination / "capture-session-manifest.json").read_text())
    assert manifest["generation_reset_count"] == 0
    assert manifest["session_timeline_classification"] == "native_session_timeline"
    frames = manifest["frames"]
    # Bounded latest-frame coalescing under host backpressure (an existing,
    # deliberate Stage 5 behavior, unrelated to this fix) means not every
    # supplied frame is guaranteed retained, but at least the newest frame
    # of each connection always survives -- enough to prove all three
    # connection segments are represented and ordered correctly.
    assert len(frames) >= 3
    session_sequences = [item["session_sequence"] for item in frames]
    assert session_sequences == sorted(session_sequences)
    assert len(set(session_sequences)) == len(frames)
    segment_ids = {item["connection_segment_id"] for item in frames}
    assert segment_ids == {"node-session-one", "node-session-two", "node-session-three"}
    discontinuous = [item for item in frames if item["temporal_discontinuity"]]
    assert len(discontinuous) == 2
    assert {item["connection_segment_id"] for item in discontinuous} == {"node-session-two", "node-session-three"}
    assert sorted(item["connection_segment_ordinal"] for item in discontinuous) == [1, 2]


def test_run_capture_holds_its_frame_bound_across_multiple_reconnects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 25: `CaptureBounds.max_analysis_frames` still stops the
    bounded capture even though benign reconnects no longer force a
    (bound-check-resetting) source rebuild -- Stage 6.11B's continuity fix
    must never come at the cost of the capture's own hard ceilings."""
    import mockingbird.observation.onnx_provider as onnx_provider_module
    import mockingbird.observation.temporal_capture_cli as cli_module

    detecting_output = np.asarray([[[0.2, 0.2, 0.8, 0.8, 0.9, 0]]], dtype=np.float32)
    monkeypatch.setattr(onnx_provider_module, "OptionalOrtCudaRuntime", lambda: FakeRuntime(lambda: FakeSession([detecting_output])))

    config_dir = _bundle_dir(tmp_path)
    camera_node_config = _camera_node_config(tmp_path)

    connections = [
        [_detecting_envelope(f"node-session-{index}", seq, captured_offset_ms=seq * 500) for seq in range(3)]
        for index in range(5)
    ]
    fake_transport = FakeTransportMultiConnection(connections)
    monkeypatch.setattr(cli_module, "CameraNodeHttpTransport", lambda **kwargs: fake_transport)

    destination = tmp_path / "capture-out-bounded-reconnects"
    exit_code = run_capture([
        "--camera-node-config", str(camera_node_config), "--provider", "frame-driven-onnx-cuda",
        "--provider-config", str(config_dir / "frame-driven-config.json"), "--output", str(destination),
        "--duration", "5", "--max-analysis-frames", "4",
    ])
    assert exit_code == 0
    manifest = json.loads((destination / "capture-session-manifest.json").read_text())
    assert manifest["stop_condition"] == STOP_FRAME_LIMIT
    assert len(manifest["frames"]) <= 4
    assert manifest["generation_reset_count"] == 0


def test_run_capture_operator_marker_correlates_to_a_frame_across_a_reconnect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 24: an operator marker discovered on a later batch boundary
    still correlates back (by host receive time, unaffected by the
    per-connection sequence/offset reset) to a frame retained under an
    *earlier* connection segment -- the marker-rescue mechanism does not
    care whether the intervening batch boundary was a reconnect."""
    import mockingbird.observation.onnx_provider as onnx_provider_module
    import mockingbird.observation.temporal_capture_cli as cli_module
    from mockingbird.observation.temporal_capture import OperatorMarker
    from mockingbird.observation.temporal_capture_io import write_operator_marker

    # No detection at all -- every frame relies purely on marker rescue,
    # isolating this test from the animal-detection trigger path.
    blank_output = np.asarray([[[0.0, 0.0, 1.0, 1.0, 0.01, 0]]], dtype=np.float32)
    monkeypatch.setattr(onnx_provider_module, "OptionalOrtCudaRuntime", lambda: FakeRuntime(lambda: FakeSession([blank_output])))

    config_dir = _bundle_dir(tmp_path)
    camera_node_config = _camera_node_config(tmp_path)
    destination = tmp_path / "capture-out-marker-reconnect"

    connection_one = [_detecting_envelope("node-session-one", 0, captured_offset_ms=0)]
    connection_two = [_detecting_envelope("node-session-two", 0, captured_offset_ms=0)]

    class _MarkerWritingTransport(FakeTransportMultiConnection):
        """Writes the operator marker in between the two connections --
        mirroring `temporal-capture-mark` running as a separate process
        while the capture loop is between batches -- so it is only ever
        discoverable at the *second* connection's batch boundary, after
        the frame it refers to was already retained under the first."""

        def iter_analysis_frames(self, *, maximum_frames: int):
            if self._connections and self._connections[0] is connection_two:
                # The live session stamps each frame's `received_at` from
                # the real wall clock (`datetime.now(UTC)`, not a
                # controllable fake one), so the marker must reference that
                # same real clock to fall inside its own lookback window.
                write_operator_marker(
                    destination,
                    OperatorMarker("marker-1", "wildlife_visible_now", datetime.now(UTC).isoformat(), lookback_seconds=30),
                )
            return super().iter_analysis_frames(maximum_frames=maximum_frames)

    fake_transport = _MarkerWritingTransport([connection_one, connection_two])
    monkeypatch.setattr(cli_module, "CameraNodeHttpTransport", lambda **kwargs: fake_transport)

    exit_code = run_capture([
        "--camera-node-config", str(camera_node_config), "--provider", "frame-driven-onnx-cuda",
        "--provider-config", str(config_dir / "frame-driven-config.json"), "--output", str(destination),
        "--duration", "5",
    ])
    assert exit_code == 0
    manifest = json.loads((destination / "capture-session-manifest.json").read_text())
    marked = [item for item in manifest["frames"] if "marker-1" in item["operator_marker_ids"]]
    assert len(marked) == 1
    assert marked[0]["connection_segment_id"] == "node-session-one"


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


# --------------------------------------------------------------------------
# Stage 6.7 real daylight finding: `_refresh_markers()`'s rescue scan only
# ever rescans `recent_frames`, the trigger-less pool -- a frame that
# already qualified for retention through its own unrelated trigger (a real
# detection, `recurring_static_geometry`, a shadow-track event, ...) never
# enters that pool, so a marker discovered afterward can never correlate to
# it, even when the frame's own `received_at` plainly falls inside the
# marker's lookback window. On a quiet scene this is invisible (almost every
# frame is trigger-less and therefore rescue-eligible), but a real bounded
# daylight session against the paired Camera Node showed nearly every frame
# already carrying a `recurring_static_geometry`/`shadow_track_event`
# trigger of its own, so all four real operator markers fired during that
# session were discovered and logged (visible in the manifest's own
# `operator_markers` list) but left every retained frame's
# `operator_marker_ids` empty -- including frames independently confirmed by
# an `animal_above_operating_point` detection seconds before the operator's
# own report of the same sighting.
# --------------------------------------------------------------------------


def test_marker_discovered_after_an_already_retained_triggered_frame_still_correlates_to_it(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    loop = _loop(tmp_path, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    frame_received_at = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)

    # f0 retains itself immediately via a real animal detection -- unlike the
    # rescue-buffer tests above, it never enters the trigger-less pool.
    loop._process_result(_result(
        _packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=frame_received_at),
        detections=(_det((0.1, 0.1, 0.2, 0.2), 0.9),),
    ))
    assert [item.frame_id for item in loop.retained] == ["f0"]
    assert loop.retained[0].operator_marker_ids == ()
    assert all(entry[0].frame_id != "f0" for entry in loop.recent_frames)

    # The operator reports the same real sighting a few seconds later.
    marker_time = frame_received_at + timedelta(seconds=5)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "wildlife_visible_now", marker_time.isoformat(), lookback_seconds=20))
    loop._refresh_markers()

    assert [item.frame_id for item in loop.retained] == ["f0"]  # backfilled in place, never duplicated
    assert "marker-1" in loop.retained[0].operator_marker_ids
    assert TRIGGER_OPERATOR_MARKER in loop.retained[0].trigger_reasons
    # The frame's own original evidence is preserved, not overwritten.
    assert loop.retained[0].animal_detection_count == 1


def test_marker_backfill_onto_an_already_retained_frame_respects_the_lookback_window(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_capture import OperatorMarker

    loop = _loop(tmp_path, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    loop._process_result(_result(
        _packet("f0", payload=blank, offset_ms=0, sequence=0, received_at=base),
        detections=(_det((0.1, 0.1, 0.2, 0.2), 0.9),),
    ))

    # Marker refers to a moment 60 real seconds after f0 -- well outside
    # even a generous 20s lookback, so no backfill should occur.
    marker_time = base + timedelta(seconds=60)
    write_operator_marker(tmp_path, OperatorMarker("marker-1", "uncertain_possible_wildlife", marker_time.isoformat(), lookback_seconds=20))
    loop._refresh_markers()

    assert loop.retained[0].operator_marker_ids == ()


def test_marker_backfill_pool_never_exceeds_its_bound(tmp_path: Path) -> None:
    loop = _loop(tmp_path, adjacent_context_frame_count=3, max_periodic_negative_samples=0, pretrigger_frame_count=0)
    blank = _jpeg((30, 30, 30))
    base = datetime(2026, 8, 5, 21, 0, 0, tzinfo=UTC)
    for index in range(10):
        loop._process_result(_result(
            _packet(f"f{index}", payload=blank, offset_ms=index * 500, sequence=index, received_at=base + timedelta(seconds=index)),
            detections=(_det((0.1, 0.1, 0.2, 0.2), 0.9),),
        ))
    assert len(loop.recent_retained_identities) <= 3
    assert [frame_id for frame_id, _ in loop.recent_retained_identities] == ["f7", "f8", "f9"]
