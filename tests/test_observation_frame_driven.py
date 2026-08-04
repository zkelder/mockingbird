from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import (
    FRAME_DRIVEN_PROVIDER_VERSION,
    FrameDrivenObservationProvider,
    FrameDrivenSettings,
)
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedAppearance,
    ExpectedVisit,
    ReplayFrame,
    ReplayInput,
    ReplayRunner,
    ReplayValidationError,
    compare_replay_reports,
    semantic_fingerprint,
)


pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeDetector:
    def __init__(self, detections: dict[str, tuple[DetectionObservation, ...]] | None = None) -> None:
        self.detections = detections or {}
        self.inferred: list[str] = []
        self.loaded = False
        self.finalized = 0

    def probe(self) -> dict[str, object]:
        return {
            "cuda_available": True,
            "model_bundle_compatible": True,
            "runtime_available": True,
            "session_loaded": self.loaded,
        }

    def load(self) -> None:
        self.loaded = True

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        assert self.loaded
        self.inferred.append(frame.frame_id or "")
        return self.detections.get(frame.frame_id or "", ())

    def finalize_replay(self) -> None:
        self.finalized += 1

    def close(self) -> None:
        self.loaded = False

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "fake", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {"inference_count": len(self.inferred)}


def _frames(count: int, *, step_ms: int = 200) -> tuple[FramePacket, ...]:
    start = datetime(2026, 8, 3, tzinfo=UTC)
    return tuple(
        FramePacket(
            "stream",
            f"replay:{index}",
            start + timedelta(milliseconds=index * step_ms),
            f"frame-{index}",
            index * step_ms,
            100,
            100,
        )
        for index in range(count)
    )


def _animal(frame: FramePacket, box: tuple[float, float, float, float], score: float = 0.9) -> DetectionObservation:
    return DetectionObservation(
        "fake:1",
        "animal",
        score,
        frame.captured_at or datetime(2026, 8, 3, tzinfo=UTC),
        f"detection:{frame.frame_id}:{box}",
        frame.frame_id,
        "fake",
        "fake",
        "fake-generation",
        box,
        "0",
        True,
    )


def _settings(**updates: object) -> FrameDrivenSettings:
    values: dict[str, object] = {
        "source_nominal_fps": 5.0,
        "baseline_detector_fps": 1.0,
        "candidate_detector_fps": 5.0,
        "strong_detection_threshold": 0.8,
        "minimum_detector_confirmations": 2,
        "minimum_tracker_support_frames": 1,
        "maximum_missed_frames": 2,
        "maximum_frame_gap_ms": 1000,
        "tracker_expiry_ms": 1000,
        "maximum_track_duration_ms": 10000,
        "maximum_active_tracks": 8,
        "evidence_ring_size": 5,
        "pretrigger_frame_count": 2,
    }
    values.update(updates)
    return FrameDrivenSettings(**values)


async def test_capabilities_and_health_are_side_effect_free_and_honest() -> None:
    detector = FakeDetector()
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings())
    health = await provider.health()
    assert provider.provider_id == "frame-driven-onnx-cuda"
    assert provider.capabilities.frame_driven is True
    assert provider.capabilities.tracking is True
    assert provider.capabilities.shadow_visit_proposals is True
    assert provider.capabilities.production_proposal_authority is False
    assert provider.capabilities.continuous_live_stream_input is True
    assert provider.capabilities.camera_node_analysis_stream is True
    assert provider.capabilities.high_resolution_burst is True
    assert health.healthy is True
    assert detector.loaded is False


async def test_live_lifecycle_processes_frames_and_clears_transient_state() -> None:
    frames = _frames(2)
    detector = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.2, 0.2, 0.4, 0.4)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(), tracker_support=lambda frame, track: track.bounding_box
    )
    provider.load()
    provider.start_live("stream")
    first = await provider.observe_live_frame(frames[0])
    second = await provider.observe_live_frame(frames[1])
    assert first.source_id == "live_shadow"
    assert second.source_id == "live_shadow"
    assert provider.active_track_count == 1
    final = provider.stop_live()
    assert final
    assert provider.active_track_count == 0
    with pytest.raises(ReplayValidationError, match="live_stream_not_started"):
        await provider.observe_live_frame(frames[1])


async def test_idle_schedule_accelerates_for_candidate_and_tracks_every_frame() -> None:
    frames = _frames(7)
    detector = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.2, 0.2, 0.4, 0.4)),)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(), tracker_support=lambda frame, track: track.bounding_box)
    provider.load()
    results = await provider.replay_frames(frames)
    assert detector.inferred[:3] == ["frame-0", "frame-1", "frame-2"]
    assert sum(len(result.frame_packets) for result in results) == len(frames)
    updates = [item for result in results for item in result.track_updates]
    assert {item.frame_id for item in updates} >= {frame.frame_id for frame in frames[:3]}
    assert any(item.lifecycle_state == "confirmed" for item in updates)


async def test_weak_detection_rejects_but_two_coherent_detections_confirm() -> None:
    frames = _frames(4, step_ms=1000)
    weak = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.1, 0.1, 0.2, 0.2), 0.3),)})
    weak_provider = FrameDrivenObservationProvider(detector=weak, settings=_settings(), tracker_support=lambda *_: None)
    weak_provider.load()
    weak_results = await weak_provider.replay_frames(frames)
    assert not [item for result in weak_results for item in result.visit_proposals]
    assert any(item.lifecycle_state == "rejected" and item.terminal_reason == "insufficient_support" for result in weak_results for item in result.track_updates)
    coherent = FakeDetector({
        frames[0].frame_id or "": (_animal(frames[0], (0.1, 0.1, 0.2, 0.2), 0.5),),
        frames[1].frame_id or "": (_animal(frames[1], (0.11, 0.1, 0.21, 0.2), 0.5),),
    })
    provider = FrameDrivenObservationProvider(detector=coherent, settings=_settings(), tracker_support=lambda *_: None)
    provider.load()
    results = await provider.replay_frames(frames)
    proposals = [item for result in results for item in result.visit_proposals]
    assert len(proposals) == 1
    assert proposals[0].shadow_only is True
    assert proposals[0].terminal_reason == "tracker_lost"


async def test_duplicate_frame_support_miss_tolerance_and_expiry_are_bounded() -> None:
    frames = list(_frames(6))
    frames[1] = FramePacket(**{**frames[1].__dict__, "frame_id": frames[0].frame_id})
    detector = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.2, 0.2, 0.4, 0.4)),)})
    supported = {"frame-2", "frame-4"}
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(maximum_missed_frames=1), tracker_support=lambda frame, track: track.bounding_box if frame.frame_id in supported else None)
    provider.load()
    results = await provider.replay_frames(tuple(frames))
    updates = [item for result in results for item in result.track_updates]
    assert max(item.tracker_support_count for item in updates) == 2
    assert any(item.lifecycle_state == "ended" and item.terminal_reason == "end_of_replay" for item in updates)


async def test_simultaneous_and_crossing_animals_keep_distinct_generations() -> None:
    frames = _frames(4)
    positions = (
        ((0.1, 0.2, 0.25, 0.4), (0.75, 0.2, 0.9, 0.4)),
        ((0.25, 0.2, 0.4, 0.4), (0.6, 0.2, 0.75, 0.4)),
        ((0.45, 0.2, 0.6, 0.4), (0.4, 0.2, 0.55, 0.4)),
        ((0.65, 0.2, 0.8, 0.4), (0.2, 0.2, 0.35, 0.4)),
    )
    detector = FakeDetector({frame.frame_id or "": tuple(_animal(frame, box) for box in positions[index]) for index, frame in enumerate(frames)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(), tracker_support=lambda *_: None)
    provider.load()
    results = await provider.replay_frames(frames)
    proposals = [item for result in results for item in result.visit_proposals]
    assert len(proposals) == 2
    assert len({item.track_generation_id for item in proposals}) == 2
    assert len({item.proposal_key for item in proposals}) == 2


async def test_evidence_ring_roles_bounds_proposal_idempotency_and_reset() -> None:
    frames = _frames(12)
    detector = FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0), tracker_support=lambda frame, track: track.bounding_box)
    provider.load()
    first = await provider.replay_frames(frames)
    first_evidence = [item for result in first for item in result.evidence_candidates]
    proposals = [item for result in first for item in result.visit_proposals]
    assert len(first_evidence) <= 4
    assert {item.role for item in first_evidence} >= {"pretrigger", "detector_confirmed", "tracked_best"}
    assert len(proposals) == 1
    assert proposals[0].idempotency_key == proposals[0].proposal_key
    provider.finalize_replay()
    assert provider.drain_final_results() == ()
    provider.reset()
    assert provider.active_track_count == 0


async def test_privacy_ignore_exclusion_filters_detection_before_tracking() -> None:
    frame = FramePacket(**{**_frames(1)[0].__dict__, "analysis_excluded_regions": ((0.0, 0.0, 0.5, 0.5),)})
    detector = FakeDetector({frame.frame_id or "": (_animal(frame, (0.1, 0.1, 0.2, 0.2)),)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings())
    provider.load()
    results = await provider.replay_frames((frame,))
    assert not [item for result in results for item in result.detection_observations]
    assert not [item for result in results for item in result.visit_proposals]


async def test_replay_fingerprint_and_report_comparison_are_deterministic() -> None:
    replay = ReplayInput("stage4", "stream", 100, 100, 5.0, tuple(ReplayFrame(index, index * 200, str(index)) for index in range(4)))
    legacy_fingerprint = semantic_fingerprint({
        "version": 1, "input_id": "stage4", "stream_id": "stream",
        "width": 100, "height": 100, "nominal_fps": 5.0,
        "frames": [
            {"index": index, "source_offset_ms": index * 200, "content_hash": str(index)}
            for index in range(4)
        ],
    })
    assert replay.fingerprint == legacy_fingerprint
    excluded = ReplayInput(
        "stage4", "stream", 100, 100, 5.0,
        (ReplayFrame(0, 0, "0", analysis_excluded_regions=((0.0, 0.0, 0.5, 0.5),)),),
    )
    assert excluded.fingerprint != legacy_fingerprint
    manifest = BenchmarkManifest(1, "stage4", replay.fingerprint, (ExpectedAppearance("bird", 0, 600),), (ExpectedVisit("visit", ("bird",), 0, 600),))

    def provider() -> FrameDrivenObservationProvider:
        packets = replay.packets()
        detector = FakeDetector({packets[0].frame_id or "": (_animal(packets[0], (0.2, 0.2, 0.4, 0.4)),)})
        instance = FrameDrivenObservationProvider(detector=detector, settings=_settings(), tracker_support=lambda frame, track: track.bounding_box)
        instance.load()
        return instance

    first_provider = provider()
    second_provider = provider()
    first = await ReplayRunner({first_provider.provider_id: first_provider}).run(replay, manifest, provider_key=first_provider.provider_id)
    second = await ReplayRunner({second_provider.provider_id: second_provider}).run(replay, manifest, provider_key=second_provider.provider_id)
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.track_updates == second.track_updates
    assert first.evidence_candidates == second.evidence_candidates
    assert first.metrics["proposals_with_evidence"] == {"value": 1, "state": "evaluated"}
    assert compare_replay_reports(first, second) == compare_replay_reports(first, second)


def test_committed_scenario_catalog_and_structural_no_write_boundary() -> None:
    catalog = json.loads(Path("tests/fixtures/observation_stage4/scenarios.json").read_text(encoding="utf-8"))
    assert len(catalog["scenarios"]) == 12
    source = Path("src/mockingbird/observation/frame_driven_provider.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession")
    assert not any(token in source for token in forbidden)
    assert FRAME_DRIVEN_PROVIDER_VERSION
