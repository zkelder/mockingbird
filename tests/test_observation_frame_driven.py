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
from mockingbird.observation.reconnect_continuity import ReconnectBridgeConfig
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


def _frames_with_discontinuity_at(
    count: int, boundary_index: int, *, generation_change: bool, step_ms: int = 200,
) -> tuple[FramePacket, ...]:
    """`count` frames at a constant nominal cadence, with a Stage 6.8
    reconnect-safe discontinuity signal on the frame at `boundary_index`:
    either a real `provider_generation` change (the pre-existing signal) or
    a *bare* `temporal_discontinuity` timing fact with the same
    provider_generation and no other Stage 6.11 bridge provenance
    (`connection_segment_id`/`temporal_uncertainty_ms`) -- deliberately
    insufficient to safely bridge, so it still resets (see
    `test_replay_benign_reconnect_with_full_provenance_bridges_one_episode`
    for the fully-provenanced case that now bridges instead)."""

    base = _frames(count, step_ms=step_ms)
    frames = []
    for index, frame in enumerate(base):
        overrides: dict[str, object] = {"provider_generation": "gen-a"}
        if index >= boundary_index:
            overrides["provider_generation"] = "gen-b" if generation_change else "gen-a"
        if index == boundary_index and not generation_change:
            overrides["timing_facts"] = (("temporal_discontinuity", True),)
        frames.append(FramePacket(**{**frame.__dict__, **overrides}))
    return tuple(frames)


@pytest.mark.parametrize(
    "generation_change,expected_reason",
    [(True, "provider_reset"), (False, "insufficient_reconnect_provenance")],
    ids=["provider_generation_changed", "temporal_discontinuity_without_bridge_provenance"],
)
async def test_replay_discontinuity_ends_the_track_instead_of_silently_continuing_it(
    generation_change: bool, expected_reason: str,
) -> None:
    frames = _frames_with_discontinuity_at(10, 5, generation_change=generation_change)
    detector = FakeDetector({
        frames[1].frame_id or "": (_animal(frames[1], (0.2, 0.2, 0.4, 0.4)),),
        frames[6].frame_id or "": (_animal(frames[6], (0.2, 0.2, 0.4, 0.4)),),
    })
    # Coherent tracker-support alone would otherwise carry a track across
    # the whole replay (see test_evidence_ring_roles_bounds_proposal_
    # idempotency_and_reset for the same fake resolver's normal behavior).
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(baseline_detector_fps=5.0), tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    # The discontinuity produced a real second generation, not one track
    # spanning the whole replay -- true whether the reset was a confidently
    # evidenced generation change or a safety reset for missing bridge
    # provenance (Stage 6.11 distinguishes *why*, not just *whether*, it
    # reset; see docs/reconnect-continuity-contract.md).
    assert len({item.generation_id for item in updates}) == 2
    assert len(proposals) == 2
    assert len({item.track_generation_id for item in proposals}) == 2
    reset_terminations = [item for item in updates if item.status == "ended" and item.terminal_reason == expected_reason]
    assert len(reset_terminations) == 1


async def test_replay_without_any_discontinuity_signal_keeps_one_continuous_track() -> None:
    """Backward compatibility: a replay input that never sets
    `provider_generation`/`temporal_discontinuity` (every pre-Stage-6.8
    replay input) is completely unaffected by this addition."""

    frames = _frames(10)
    detector = FakeDetector({frames[1].frame_id or "": (_animal(frames[1], (0.2, 0.2, 0.4, 0.4)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(baseline_detector_fps=5.0), tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]
    assert len({item.generation_id for item in updates}) == 1
    assert len(proposals) == 1
    assert not any(item.terminal_reason == "provider_reset" for item in updates)


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


async def test_two_separate_bird_visits_create_two_shadow_proposals_with_isolated_evidence() -> None:
    """Catalog scenario "two_separate_bird_visits": animal A is confirmed, leaves
    for a meaningful gap, and animal B arrives later in the same broad class and
    a similar position.  The episode boundary must close A's episode and start a
    distinct generation for B rather than continuing one merged episode."""
    frames = _frames(10, step_ms=1000)
    box = (0.2, 0.2, 0.5, 0.5)
    detector = FakeDetector({
        frames[0].frame_id or "": (_animal(frames[0], box),),
        frames[1].frame_id or "": (_animal(frames[1], box),),
        frames[8].frame_id or "": (_animal(frames[8], box),),
        frames[9].frame_id or "": (_animal(frames[9], box),),
    })
    provider = FrameDrivenObservationProvider(
        detector=detector,
        settings=_settings(
            source_nominal_fps=1.0, baseline_detector_fps=1.0, candidate_detector_fps=1.0,
            maximum_unsupported_detector_ms=3000, maximum_frame_gap_ms=6000, tracker_expiry_ms=6000,
        ),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    proposals = [item for result in results for item in result.visit_proposals]
    assert len(proposals) == 2
    assert len({item.track_generation_id for item in proposals}) == 2
    first_ids = set(proposals[0].evidence_media_asset_ids)
    second_ids = set(proposals[1].evidence_media_asset_ids)
    assert first_ids and second_ids
    assert not (first_ids & second_ids)


async def test_boundary_metrics_report_the_confident_split_and_reason_distribution() -> None:
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("input", "stream", 100, 100, 1.0, tuple(
        ReplayFrame(index, index * 1000, str(index)) for index in range(10)
    ))
    packets = replay.packets()
    detector = FakeDetector({
        packets[index].frame_id or "": (_animal(packets[index], box),) for index in (0, 1, 8, 9)
    })
    provider = FrameDrivenObservationProvider(
        detector=detector,
        settings=_settings(
            source_nominal_fps=1.0, baseline_detector_fps=1.0, candidate_detector_fps=1.0,
            maximum_unsupported_detector_ms=3000, maximum_frame_gap_ms=6000, tracker_expiry_ms=6000,
        ),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    manifest = BenchmarkManifest(1, "boundary", replay.fingerprint, (), ())
    report = await ReplayRunner({provider.provider_id: provider}).run(replay, manifest, provider_key=provider.provider_id)
    assert report.metrics["episode_confirmed_split_count"] == {"state": "evaluated", "value": 1}
    assert report.metrics["boundary_reason_distribution"] == {
        "state": "evaluated",
        "value": {"end_of_replay": 1, "maximum_unsupported_duration": 1},
    }
    assert report.metrics["episode_ambiguous_reentry_count"] == {"state": "evaluated", "value": 0}
    assert report.metrics["tracks_confirmed"] == {"state": "evaluated", "value": 2}


async def test_replay_and_evidence_ordering_remain_deterministic_across_an_episode_split() -> None:
    frames = _frames(10, step_ms=1000)
    box = (0.2, 0.2, 0.5, 0.5)

    def build_provider() -> FrameDrivenObservationProvider:
        detector = FakeDetector({
            f"frame-{index}": (_animal(frames[index], box),) for index in (0, 1, 8, 9)
        })
        instance = FrameDrivenObservationProvider(
            detector=detector,
            settings=_settings(
                source_nominal_fps=1.0, baseline_detector_fps=1.0, candidate_detector_fps=1.0,
                maximum_unsupported_detector_ms=3000, maximum_frame_gap_ms=6000, tracker_expiry_ms=6000,
            ),
            tracker_support=lambda frame, track: track.bounding_box,
        )
        instance.load()
        return instance

    first_provider = build_provider()
    second_provider = build_provider()
    first_results = await first_provider.replay_frames(frames)
    second_results = await second_provider.replay_frames(frames)
    first_proposals = tuple(sorted(
        (item for result in first_results for item in result.visit_proposals), key=lambda item: item.proposal_key,
    ))
    second_proposals = tuple(sorted(
        (item for result in second_results for item in result.visit_proposals), key=lambda item: item.proposal_key,
    ))
    assert first_proposals == second_proposals
    assert len(first_proposals) == 2
    first_updates = tuple(item for result in first_results for item in result.track_updates)
    second_updates = tuple(item for result in second_results for item in result.track_updates)
    assert first_updates == second_updates


def test_committed_scenario_catalog_and_structural_no_write_boundary() -> None:
    catalog = json.loads(Path("tests/fixtures/observation_stage4/scenarios.json").read_text(encoding="utf-8"))
    assert len(catalog["scenarios"]) == 12
    source = Path("src/mockingbird/observation/frame_driven_provider.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession")
    assert not any(token in source for token in forbidden)
    assert FRAME_DRIVEN_PROVIDER_VERSION


# =============================================================================
# Stage 6.11: reconnect-safe tracker continuity
#
# Reproduces, then proves fixed, the real Stage 6.10 session-03/04 failure:
# a genuinely continuous animal appearance was previously cut into a
# separate tracker generation -- and a separate confirmed VisitProposal --
# at every benign HTTP reconnect boundary purely because the connection
# reset, even though provider_generation never changed (67 proposals for 2
# reviewed appearances in session-03; 27 for 3 in session-04;
# appearance_recall/proposal_precision measured 0.0 in both). Parallel
# fixtures for genuine source discontinuity prove those still terminate.
# See docs/reconnect-continuity-contract.md.
# =============================================================================


def test_committed_stage611_scenario_catalog_exists() -> None:
    catalog = json.loads(Path("tests/fixtures/observation_stage611/scenarios.json").read_text(encoding="utf-8"))
    all_scenarios = [name for group in catalog["scenarios"].values() for name in group]
    assert len(all_scenarios) == len(set(all_scenarios)) >= 20


async def test_replay_benign_reconnect_with_full_provenance_bridges_one_episode() -> None:
    """The primary Stage 6.11 fix-proof test: the exact 'Benign reconnect'
    fixture shape the task specifies -- same Stream, same provider
    generation, same analysis profile, connection-local offsets reset
    (`original_source_offset_ms`), a new connection segment, session-
    relative `source_offset_ms` staying monotonic, a short bounded gap
    (2500ms -- comfortably inside the real 940-6868ms session-03/04 range,
    and well past the tracker's own ordinary maximum_frame_gap_ms/
    tracker_expiry_ms, proving the *bridge* -- not just tolerance -- is
    what carries it), and one coherent animal detected before and after.
    Before this stage this produced two generations and two proposals
    (reason: "provider_reset"); it must now produce exactly one."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("bridge", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50, original_source_offset_ms=0,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 1
    assert len(proposals) == 1
    assert not any(item.terminal_reason in {"provider_reset", "insufficient_reconnect_provenance"} for item in updates)
    assert proposals[0].shadow_only is True
    assert provider.capabilities.production_proposal_authority is False
    facts = provider.replay_semantic_facts()
    assert facts["reconnect_boundaries"] == 1
    assert facts["reconnect_bridges_attempted"] == 1
    assert facts["reconnect_bridges_continued"] == 1
    assert facts["reconnect_bridges_expired"] == 0
    assert facts["resets_true_source_change"] == 0
    assert facts["resets_insufficient_provenance"] == 0


async def test_replay_multiple_benign_reconnects_preserve_one_episode() -> None:
    """Scenario 16: three separate reconnect boundaries, each with a real
    post-reconnect detection, still produce exactly one coherent episode."""
    box = (0.2, 0.2, 0.5, 0.5)
    frames = []
    offsets = [0, 200, 2_700, 2_900, 5_400, 5_600, 8_100, 8_300]
    for index, offset in enumerate(offsets):
        segment_ordinal = index // 2
        overrides: dict[str, object] = {
            "provider_generation": "gen-1",
            "connection_segment_id": f"conn-{segment_ordinal}",
            "connection_segment_ordinal": segment_ordinal,
        }
        if index % 2 == 0 and index > 0:
            overrides["temporal_discontinuity"] = True
            overrides["temporal_uncertainty_ms"] = 50
            overrides["original_source_offset_ms"] = 0
        frames.append(ReplayFrame(index, offset, f"h{index}", **overrides))
    replay = ReplayInput("multi-bridge", "stream", 100, 100, 5.0, tuple(frames))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 1
    assert len(proposals) == 1
    facts = provider.replay_semantic_facts()
    assert facts["reconnect_boundaries"] == 3
    assert facts["reconnect_bridges_continued"] == 3
    assert facts["reconnect_bridges_expired"] == 0


@pytest.mark.parametrize(
    "build_frames,expected_reason",
    [
        (
            lambda box: (
                ReplayInput("reset-generation", "stream", 100, 100, 5.0, (
                    ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
                    ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
                    ReplayFrame(
                        2, 2_700, "h2", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1,
                        temporal_discontinuity=True, temporal_uncertainty_ms=50,
                    ),
                    ReplayFrame(3, 2_900, "h3", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1),
                )).packets()
            ),
            "provider_reset",
        ),
        (
            lambda box: (
                ReplayInput("reset-gap", "stream", 100, 100, 5.0, (
                    ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
                    ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
                    ReplayFrame(
                        2, 200 + 60_000, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
                        temporal_discontinuity=True, temporal_uncertainty_ms=50,
                    ),
                    ReplayFrame(3, 200 + 60_200, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
                )).packets()
            ),
            "provider_reset",
        ),
    ],
    ids=["provider_generation_change", "excessive_reconnect_gap"],
)
async def test_replay_true_source_reset_variants_still_terminate(build_frames, expected_reason: str) -> None:
    """Parallel 'true source reset' fixtures: even with an otherwise-benign
    connection-segment transition, a genuine provider-generation change or
    an excessive reconnect gap must still terminate the episode -- proving
    this stage did not trade fragmentation-avoidance for unsafe merging."""
    box = (0.2, 0.2, 0.5, 0.5)
    packets = build_frames(box)
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 2
    assert len(proposals) == 2
    reset_terminations = [item for item in updates if item.status == "ended" and item.terminal_reason == expected_reason]
    assert len(reset_terminations) == 1
    facts = provider.replay_semantic_facts()
    assert facts["resets_true_source_change"] == 1
    assert facts["reconnect_bridges_continued"] == 0


async def test_replay_incompatible_dimensions_still_resets() -> None:
    """Scenario 9: an analysis dimension change at the reconnect boundary
    is confident evidence of an incompatible profile, not a benign
    reconnect -- even though provider_generation itself is unchanged."""
    frames = _frames(4, step_ms=200)
    detector = FakeDetector({
        frames[0].frame_id or "": (_animal(frames[0], (0.2, 0.2, 0.4, 0.4)),),
        frames[3].frame_id or "": (_animal(frames[3], (0.2, 0.2, 0.4, 0.4)),),
    })
    overridden = []
    for index, frame in enumerate(frames):
        overrides: dict[str, object] = {"provider_generation": "gen-1"}
        if index >= 2:
            overrides["width"], overrides["height"] = 640, 480
        if index == 2:
            overrides["timing_facts"] = (
                ("connection_segment_id", "conn-b"), ("temporal_discontinuity", True), ("temporal_uncertainty_ms", 50),
            )
        else:
            overrides["timing_facts"] = (("connection_segment_id", "conn-a"),)
        overridden.append(FramePacket(**{**frame.__dict__, **overrides}))
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(tuple(overridden))
    updates = [item for result in results for item in result.track_updates]
    reset_terminations = [item for item in updates if item.status == "ended" and item.terminal_reason == "provider_reset"]
    assert len(reset_terminations) == 1
    assert len({item.generation_id for item in updates}) == 2


async def test_replay_bird_leaves_before_reconnect_different_bird_after_does_not_merge() -> None:
    """Incorrect-merge protection: the first animal is gone (no detection)
    on the last frame before reconnect, and a spatially distinct animal
    appears after -- must be two generations, never one merged episode."""
    left_box, right_box = (0.05, 0.05, 0.2, 0.2), (0.75, 0.75, 0.9, 0.9)
    replay = ReplayInput("leaves-then-different", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(2, 400, "h2", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            3, 2_900, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(4, 3_100, "h4", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({
        packets[0].frame_id or "": (_animal(packets[0], left_box),),
        packets[1].frame_id or "": (_animal(packets[1], left_box),),
        # packets[2]: the original bird already left -- no detection.
        packets[3].frame_id or "": (_animal(packets[3], right_box),),
        packets[4].frame_id or "": (_animal(packets[4], right_box),),
    })
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 2
    assert len(proposals) == 2
    assert len({item.track_generation_id for item in proposals}) == 2


async def test_replay_two_birds_opposite_sides_of_reconnect_survive_independently() -> None:
    """Incorrect-merge protection: two simultaneous, spatially distinct
    subjects both bridge the same reconnect independently -- neither
    absorbs the other's evidence."""
    left_box, right_box = (0.05, 0.05, 0.2, 0.2), (0.75, 0.75, 0.9, 0.9)
    replay = ReplayInput("two-birds-bridge", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({
        packet.frame_id or "": (_animal(packet, left_box), _animal(packet, right_box)) for packet in packets
    })
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 2
    assert len(proposals) == 2
    assert proposals[0].track_generation_id != proposals[1].track_generation_id
    # Both subjects share the same underlying frames (this fixture is
    # deliberately simultaneous), so `evidence_media_asset_ids` -- a
    # frame-level identity -- legitimately overlaps; per-candidate
    # `subject_geometry`/`track_generation_id` is the actual isolation
    # guarantee, and it must stay correct for each subject independently.
    evidence = [item for result in results for item in result.evidence_candidates]
    left_geometry = {item.subject_geometry for item in evidence if item.track_generation_id == proposals[0].track_generation_id}
    right_geometry = {item.subject_geometry for item in evidence if item.track_generation_id == proposals[1].track_generation_id}
    assert left_geometry and right_geometry
    assert left_geometry.isdisjoint(right_geometry)


async def test_replay_long_reconnect_gap_terminates_tracks() -> None:
    """Incorrect-merge protection: a reconnect gap beyond the configured
    bound is not bridged even with an otherwise-benign, fully-provenanced
    boundary -- it terminates like any other confidently evidenced reset."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("long-gap", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 200 + 120_000, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 200 + 120_200, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(baseline_detector_fps=5.0),
        reconnect_bridge_config=ReconnectBridgeConfig(maximum_reconnect_gap_ms=15_000),
    )
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    assert len({item.generation_id for item in updates}) == 2
    facts = provider.replay_semantic_facts()
    assert facts["resets_true_source_change"] == 1


async def test_replay_evidence_and_proposals_remain_generation_isolated_across_a_reset() -> None:
    """Scenario 24: evidence-candidate/proposal lineage never crosses a
    reconnect-driven reset boundary."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("evidence-isolated", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    proposals = [item for result in results for item in result.visit_proposals]
    assert len(proposals) == 2
    first_ids = set(proposals[0].evidence_media_asset_ids)
    second_ids = set(proposals[1].evidence_media_asset_ids)
    assert first_ids and second_ids
    assert not (first_ids & second_ids)
    assert proposals[0].track_generation_id != proposals[1].track_generation_id


async def test_replay_bridging_is_deterministic_and_reproducible() -> None:
    """Scenario 26: replaying the identical benign-reconnect input twice
    produces byte-identical track updates, proposals, and semantic
    fingerprint."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("bridge-determinism", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    manifest = BenchmarkManifest(1, "bridge-determinism", replay.fingerprint, (), ())

    def build_provider() -> FrameDrivenObservationProvider:
        packets = replay.packets()
        detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
        instance = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
        instance.load()
        return instance

    first = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(replay, manifest, provider_key="frame-driven-onnx-cuda")
    second = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(replay, manifest, provider_key="frame-driven-onnx-cuda")
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.track_updates == second.track_updates
    assert first.proposals == second.proposals
    assert first.metrics["reconnect_bridges_continued"] == {"state": "evaluated", "value": 1}


async def test_replay_true_reset_is_deterministic_and_reproducible() -> None:
    """Scenario 27: the same determinism guarantee for the reset path."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("reset-determinism", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-2", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    manifest = BenchmarkManifest(1, "reset-determinism", replay.fingerprint, (), ())

    def build_provider() -> FrameDrivenObservationProvider:
        packets = replay.packets()
        detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
        instance = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
        instance.load()
        return instance

    first = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(replay, manifest, provider_key="frame-driven-onnx-cuda")
    second = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(replay, manifest, provider_key="frame-driven-onnx-cuda")
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.metrics["reconnect_resets_true_source_change"] == {"state": "evaluated", "value": 1}


async def test_replay_connection_segment_provenance_visible_after_bridge() -> None:
    """Scenario 35: a successful bridge does not hide the underlying
    connection-segment boundary -- it remains visible as provenance, and
    the reconnect metrics honestly report the track/proposal as spanning
    more than one transport segment."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("segment-provenance", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50,
        ),
        ReplayFrame(3, 2_900, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    manifest = BenchmarkManifest(1, "segment-provenance", replay.fingerprint, (), ())
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    report = await ReplayRunner({provider.provider_id: provider}).run(replay, manifest, provider_key=provider.provider_id)
    assert report.metrics["tracks_spanning_multiple_connection_segments"] == {"state": "evaluated", "value": 1}
    assert report.metrics["proposals_spanning_multiple_connection_segments"] == {"state": "evaluated", "value": 1}
    assert report.metrics["reconnect_fragmentation_avoided"] == {"state": "evaluated", "value": 1}
    assert report.metrics["reconnect_related_incorrect_merge_count"] == {"state": "evaluated", "value": 0}
    # The two underlying connection segments are still directly readable
    # from each supporting frame's own provenance -- never rewritten as if
    # no reconnect happened.
    segment_ids = {dict(frame.timing_facts).get("connection_segment_id") for frame in packets}
    assert segment_ids == {"conn-a", "conn-b"}


async def test_replay_privacy_ignore_exclusion_unaffected_by_reconnect_bridging() -> None:
    """Scenario 31: Privacy/Ignore exclusion still masks a detection inside
    an excluded region on a post-reconnect frame exactly as before -- the
    bridge changes tracker-continuity handling only, never detection
    filtering."""
    excluded_region = (0.0, 0.0, 0.5, 0.5)
    box_inside = (0.1, 0.1, 0.2, 0.2)
    replay = ReplayInput("privacy-bridge", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0,
                    analysis_excluded_regions=(excluded_region,)),
        ReplayFrame(
            1, 2_500, "h1", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50, analysis_excluded_regions=(excluded_region,),
        ),
    ))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box_inside),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await provider.replay_frames(packets)
    detections = [item for result in results for item in result.detection_observations]
    proposals = [item for result in results for item in result.visit_proposals]
    assert detections == []
    assert proposals == []


async def test_snapshot_provider_capabilities_remain_unchanged() -> None:
    """Scenario 28: this stage touches no code path shared with
    `SnapshotObservationProvider` -- its capability contract stays exactly
    as declared before Stage 6.11."""
    from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

    assert SnapshotObservationProvider.capabilities.tracking is False
    assert SnapshotObservationProvider.capabilities.frame_driven is False
    assert SnapshotObservationProvider.capabilities.production_proposal_authority is False


def test_stage611_modules_have_no_product_repository_or_transport_dependency() -> None:
    """Scenario 29/30: no durable product write and no production
    authority is reachable from any Stage 6.11 module -- a structural,
    source-grep boundary matching every prior Stage 6.x pure module."""
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "mockingbird.api.main", "ReviewLabel",
        "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession", "sqlalchemy",
    )
    for relative in ("reconnect_continuity.py", "frame_tracker.py", "frame_driven_provider.py"):
        source = Path(f"src/mockingbird/observation/{relative}").read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), relative
