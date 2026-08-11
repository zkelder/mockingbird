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
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker
from mockingbird.observation.reconnect_continuity import CONTINUE_ACROSS_TRANSPORT_RECONNECT, ReconnectBridgeConfig
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


async def test_result_detector_ran_matches_the_actual_inference_cadence() -> None:
    """Rejected / Suppressed Detection Attribution v1 (see
    docs/rejected-detection-attribution-contract.md): `ObservationResult.
    detector_ran` is the fact a live counterfactual ledger needs to tell an
    idle-cadence frame the detector never inspected apart from one it
    inspected and found nothing in -- must exactly match `detector.
    inferred`, never merely "some track update existed this frame" (which a
    quiet frame with zero active tracks would not produce either way)."""
    frames = _frames(7)
    detector = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.2, 0.2, 0.4, 0.4)),)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(), tracker_support=lambda frame, track: track.bounding_box)
    provider.load()
    results = await provider.replay_frames(frames)
    inferred_frame_ids = set(detector.inferred)
    per_frame_results = [result for result in results if result.frame_packets]
    assert len(per_frame_results) == len(frames)
    for result in per_frame_results:
        frame_id = result.frame_packets[0].frame_id
        assert result.detector_ran == (frame_id in inferred_frame_ids)
    # The synthetic end-of-replay finalization result (no `frame_packets` of
    # its own -- see `_finalize_tracking`) honestly reports no detector
    # evaluation for itself; it is not a per-frame result at all.
    for result in results:
        if not result.frame_packets:
            assert result.detector_ran is False


async def test_weak_detection_rejects_but_two_coherent_detections_confirm() -> None:
    frames = _frames(4, step_ms=1000)
    weak = FakeDetector({frames[0].frame_id or "": (_animal(frames[0], (0.1, 0.1, 0.2, 0.2), 0.3),)})
    weak_provider = FrameDrivenObservationProvider(detector=weak, settings=_settings(), tracker_support=lambda *_: None)
    weak_provider.load()
    weak_results = await weak_provider.replay_frames(frames)
    assert not [item for result in weak_results for item in result.visit_proposals]
    assert any(item.lifecycle_state == "rejected" and item.terminal_reason == "insufficient_support" for result in weak_results for item in result.track_updates)
    # Stage 6.16: both scores are >= `_settings()`'s `strong_detection_
    # threshold` (0.8) so this remains a genuine strong-confirmation pair --
    # a weak-scored pair can no longer confirm a tentative track by itself
    # (see the dedicated coverage in tests/test_frame_tracker.py), so this
    # test's original "spatial/temporal coherence, not just one isolated
    # hit, is what separates rejected from confirmed" intent now needs both
    # detections to also individually clear the strong bar.
    coherent = FakeDetector({
        frames[0].frame_id or "": (_animal(frames[0], (0.1, 0.1, 0.2, 0.2), 0.85),),
        frames[1].frame_id or "": (_animal(frames[1], (0.11, 0.1, 0.21, 0.2), 0.85),),
    })
    provider = FrameDrivenObservationProvider(detector=coherent, settings=_settings(), tracker_support=lambda *_: None)
    provider.load()
    results = await provider.replay_frames(frames)
    proposals = [item for result in results for item in result.visit_proposals]
    assert len(proposals) == 1
    assert proposals[0].shadow_only is True
    # Stage 6.16: this confirmed track's own widened confirmed-track gap
    # tolerance now comfortably bridges the two trailing undetected frames
    # (frame_id gaps of only 1000-2000ms, well inside the existing
    # `maximum_unsupported_detector_ms` default of 5000ms), so it survives
    # to the end of this short 4-frame replay instead of expiring early via
    # the ordinary tight `tracker_expiry_ms` -- `end_of_replay`, not
    # `tracker_lost`, is now the correct, expected terminal reason here.
    assert proposals[0].terminal_reason == "end_of_replay"


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


async def test_evidence_geometry_attribution_distinguishes_pretrigger_from_same_frame_roles() -> None:
    """Localization Attribution / Detection Geometry Lineage v1 (see
    docs/localization-attribution-contract.md): `pretrigger` evidence is the
    one role in this provider whose image comes from an *earlier* retained
    frame than the `TrackUpdate` supplying its box (`_seed_evidence` reads
    `prior[-1]`, an older frame, while `update` is the track's current,
    just-started state) -- its own `geometry_attribution` must honestly
    report `same_frame=False` and a nonzero, exactly-derivable gap. Every
    other role's `frame`/`update` pair is the same per-frame processing
    step, so its `geometry_attribution` must report `same_frame=True` and a
    `0` gap -- proven, not merely asserted, by tracing frame identity."""
    frames = _frames(12)
    detector = FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    evidence = {item.role: item for result in results for item in result.evidence_candidates}

    pretrigger = evidence["pretrigger"]
    assert pretrigger.frame_id == frames[1].frame_id  # the retained frame *before* the detection frame
    attribution = pretrigger.geometry_attribution
    assert attribution is not None
    assert attribution.same_frame is False
    assert attribution.geometry_evidence_gap_ms == abs(frames[1].source_offset_ms - frames[2].source_offset_ms)
    assert attribution.geometry_evidence_gap_ms == 200

    for role in ("detector_confirmed", "tracked_best"):
        candidate = evidence[role]
        assert candidate.frame_id == frames[2].frame_id
        aligned = candidate.geometry_attribution
        assert aligned is not None
        assert aligned.same_frame is True
        assert aligned.geometry_evidence_gap_ms == 0
        assert aligned.geometry_source == "detector"
        assert aligned.geometry_source_confidence == 0.9  # FakeDetector/_animal's own default score


# --------------------------------------------------------------------------
# Stage 6.14: reviewed-to-replay evidence identity lineage
# --------------------------------------------------------------------------


def _frames_with_source_lineage(count: int, *, step_ms: int = 200) -> tuple[FramePacket, ...]:
    """Every produced frame additionally carries reviewed source-lineage
    provenance -- mirroring what `replay.ReplayInput.packets()` now
    produces for a temporal-review-derived input -- distinct from each
    frame's own replay-local `frame_id`/`media_asset_id`."""
    from dataclasses import replace
    return tuple(
        replace(
            frame,
            source_capture_frame_id=f"reviewed-{index}",
            source_content_hash=f"hash-{index}",
        )
        for index, frame in enumerate(_frames(count, step_ms=step_ms))
    )


async def test_evidence_candidate_retains_source_frame_lineage() -> None:
    """(7) Every `EvidenceCandidate` a confirmed track generation retains
    carries its own frame's reviewed `source_capture_frame_id`/
    `source_content_hash` as explicit, additive provenance -- distinct from,
    and alongside, its own replay-local `frame_id`."""

    frames = _frames_with_source_lineage(12)
    detector = FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    evidence = [item for result in results for item in result.evidence_candidates]
    assert evidence
    for item in evidence:
        assert item.source_capture_frame_id is not None
        assert item.source_capture_frame_id != item.frame_id  # distinct identity spaces
        assert item.source_capture_frame_id.startswith("reviewed-")
        assert item.source_content_hash is not None


async def test_visit_proposal_retains_source_supporting_lineage() -> None:
    """(8) A confirmed `VisitProposal`'s `supporting_source_capture_frame_ids`
    mirrors its `supporting_frame_ids` in reviewed-source-lineage space --
    both cover the same supporting frames, one per identity space."""

    frames = _frames_with_source_lineage(12)
    detector = FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    (proposal,) = [item for result in results for item in result.visit_proposals]
    assert proposal.supporting_source_capture_frame_ids
    assert len(proposal.supporting_source_capture_frame_ids) == len(proposal.supporting_frame_ids)
    assert all(item.startswith("reviewed-") for item in proposal.supporting_source_capture_frame_ids)


async def test_generic_replay_frames_without_source_lineage_still_produce_evidence() -> None:
    """(4, 24) A generic replay input with no reviewed-capture provenance at
    all (the pre-Stage-6.14 shape, and every non-temporal-review replay
    input) still produces evidence/proposals exactly as before -- source
    lineage fields simply stay `None`/empty throughout, never required."""

    frames = _frames(12)
    assert all(frame.source_capture_frame_id is None for frame in frames)
    detector = FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0),
        tracker_support=lambda frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(frames)
    evidence = [item for result in results for item in result.evidence_candidates]
    (proposal,) = [item for result in results for item in result.visit_proposals]
    assert evidence and all(item.source_capture_frame_id is None for item in evidence)
    assert proposal.supporting_source_capture_frame_ids == ()


async def test_source_lineage_propagation_is_deterministic_across_repeated_replay() -> None:
    """(24) Repeated `replay_frames` calls over the same lineage-carrying
    input reproduce byte-identical `EvidenceCandidate`/`VisitProposal`
    source-lineage fields alongside their existing replay-local
    counterparts (test_evidence_ring_roles_... already proves the latter;
    this proves the former holds too)."""

    frames = _frames_with_source_lineage(12)

    def _run_detector() -> FakeDetector:
        return FakeDetector({frames[2].frame_id or "": (_animal(frames[2], (0.2, 0.2, 0.5, 0.5)),)})

    async def _run() -> tuple[object, ...]:
        provider = FrameDrivenObservationProvider(
            detector=_run_detector(), settings=_settings(evidence_ring_size=4, baseline_detector_fps=5.0),
            tracker_support=lambda frame, track: track.bounding_box,
        )
        provider.load()
        results = await provider.replay_frames(frames)
        return tuple(item for result in results for item in result.evidence_candidates)

    first, second = await _run(), await _run()
    assert first == second
    assert first[0].source_capture_frame_id is not None


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


# =============================================================================
# Stage 6.11B: the identical Stage 6.11 reconnect-continuity decision reused
# through the *live* entry point (`observe_live_frame`) instead of only
# replay. Before this stage `observe_live_frame` had no boundary handling at
# all: the live capture loop (`temporal_capture_cli._CaptureLoop`) instead
# fully rebuilt the transport source and restarted this provider's whole
# tracker generation on every ordinary HTTP reconnect (roughly every ten
# seconds on the real Node). This section mirrors the replay-proof tests
# above through `observe_live_frame` called one frame at a time -- the
# actual shape a live Camera Node session drives it. See
# docs/reconnect-continuity-contract.md.
# =============================================================================


async def _observe_live_sequence(
    provider: FrameDrivenObservationProvider, packets: tuple[FramePacket, ...], *, finalize: bool = False,
) -> list:
    """Drive `packets` one at a time through the live entry point, exactly
    the shape a real `LiveCameraNodeShadowSession` uses. `finalize=True`
    additionally stops the session afterward (mirroring a real session
    eventually stopping, and matching how `replay_frames` implicitly
    finalizes every still-active generation at replay end) -- a still-
    confirmed-but-not-yet-terminated track otherwise never emits its
    VisitProposal, since nothing has closed its episode yet."""
    provider.start_live(packets[0].stream_id)
    results = []
    for packet in packets:
        results.append(await provider.observe_live_frame(packet))
    if finalize:
        results.extend(provider.stop_live("live_shadow_stopped"))
    return results


async def test_live_reconnect_with_same_source_preserves_provider_instance_and_bridges_one_episode() -> None:
    """Scenarios 1/6: the primary Stage 6.11B fix-proof test, live
    equivalent of `test_replay_benign_reconnect_with_full_provenance_
    bridges_one_episode` -- one `FrameDrivenObservationProvider` instance,
    driven only through its live entry point across a benign reconnect,
    produces exactly one coherent tracker generation and one confirmed
    VisitProposal, not two."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("live-bridge", "stream", 100, 100, 5.0, (
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
    same_provider = provider  # the object under test is never replaced
    results = await _observe_live_sequence(provider, packets, finalize=True)
    assert provider is same_provider
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
    assert provider.last_reconnect_decision is not None
    assert provider.last_reconnect_decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT


async def test_live_multiple_reconnects_preserve_one_track() -> None:
    """Scenario 8: three separate live reconnect boundaries, each with a
    real post-reconnect detection, still produce exactly one coherent
    episode through the live entry point."""
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
    replay = ReplayInput("live-multi-bridge", "stream", 100, 100, 5.0, tuple(frames))
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await _observe_live_sequence(provider, packets, finalize=True)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 1
    assert len(proposals) == 1
    facts = provider.replay_semantic_facts()
    assert facts["reconnect_boundaries"] == 3
    assert facts["reconnect_bridges_continued"] == 3
    assert facts["reconnect_bridges_expired"] == 0


async def _live_bridge_packets_without_post_reconnect_detection(*, reconnect_gap_ms: int = 2_500) -> tuple[FramePacket, ...]:
    """h0: a real detection starts a tentative track (one confirmation is
    not enough with `minimum_detector_confirmations=2`). h1: an ordinary
    same-segment miss. h2: the reconnect boundary itself, deliberately with
    no detection -- isolates "did merely bridging add support" from "did a
    real post-reconnect detection add support"."""
    replay = ReplayInput("live-no-fake-support", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 200 + reconnect_gap_ms, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50, original_source_offset_ms=0,
        ),
    ))
    return replay.packets()


async def test_live_tentative_track_gets_no_fake_support_from_reconnect_survival() -> None:
    """Scenario 7: crossing a benign reconnect boundary by itself must not
    increment detector_confirmation_count/tracker_support_count or promote
    a tentative track -- only genuine post-reconnect evidence may."""
    box = (0.2, 0.2, 0.5, 0.5)
    packets = await _live_bridge_packets_without_post_reconnect_detection()
    detector = FakeDetector({packets[0].frame_id or "": (_animal(packets[0], box),)})
    provider = FrameDrivenObservationProvider(
        detector=detector,
        settings=_settings(baseline_detector_fps=5.0, minimum_detector_confirmations=2, maximum_missed_frames=5, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000),
    )
    provider.load()
    results = await _observe_live_sequence(provider, packets)
    updates = [item for result in results for item in result.track_updates]
    after_start = next(item for item in updates if item.status == "started")
    after_boundary = updates[-1]
    assert after_start.detector_confirmation_count == 1
    assert after_start.lifecycle_state == "tentative"
    # The boundary frame is well past the tracker's own ordinary
    # maximum_frame_gap_ms/tracker_expiry_ms (1000ms) -- only the bridge,
    # not ordinary tolerance, is what keeps this track alive here.
    assert after_boundary.lifecycle_state == "temporarily_lost"
    assert after_boundary.detector_confirmation_count == after_start.detector_confirmation_count
    assert after_boundary.tracker_support_count == after_start.tracker_support_count == 0
    assert not any(item.status == "ended" for item in updates)


async def test_live_track_without_post_reconnect_evidence_expires_bridge() -> None:
    """Scenario 9: when no genuine post-reconnect evidence ever arrives,
    the bridge's own bounded budget still closes it -- reconnect survival
    is bounded patience, not indefinite immunity. Two pre-reconnect
    detections confirm the track first (mirroring `test_frame_tracker.
    test_no_post_reconnect_support_eventually_expires_the_track`), so the
    raw `reconnect_bridge_expired` reason is visible rather than relabeled
    `insufficient_support` (which is what an unconfirmed track's expiry
    reports instead -- a separate, already-covered case)."""
    box = (0.2, 0.2, 0.5, 0.5)
    packets = list(await _live_bridge_packets_without_post_reconnect_detection())
    # Extend well past both the frame-count and duration bridge budgets
    # (defaults: 8 frames / 8000ms) with frames carrying no detection at all.
    for index in range(3, 14):
        packets.append(FramePacket(**{
            **packets[-1].__dict__,
            "frame_id": f"h{index}",
            "source_offset_ms": packets[-1].source_offset_ms + 300,
            "timing_facts": (),
        }))
    detector = FakeDetector({
        packets[0].frame_id or "": (_animal(packets[0], box),),
        packets[1].frame_id or "": (_animal(packets[1], box),),
    })
    provider = FrameDrivenObservationProvider(
        detector=detector,
        settings=_settings(baseline_detector_fps=5.0, minimum_detector_confirmations=2, maximum_missed_frames=5, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000),
    )
    provider.load()
    results = await _observe_live_sequence(provider, tuple(packets))
    updates = [item for result in results for item in result.track_updates]
    terminal = [item for item in updates if item.status == "ended"]
    assert len(terminal) == 1
    assert terminal[0].terminal_reason == "reconnect_bridge_expired"
    facts = provider.replay_semantic_facts()
    assert facts["reconnect_bridges_expired"] == 1
    assert facts["reconnect_bridges_continued"] == 0


async def test_live_spatially_incompatible_reentry_starts_a_new_generation() -> None:
    """Scenario 10: a post-reconnect detection at a wildly different
    position/size than the pending track's last known geometry must not be
    accepted as reacquisition -- it starts its own new generation while the
    original pending track's bridge keeps counting down independently."""
    original_box = (0.1, 0.1, 0.2, 0.2)
    incompatible_box = (0.7, 0.7, 0.95, 0.95)
    replay = ReplayInput("live-incompatible-reentry", "stream", 100, 100, 5.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 200, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 2_700, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50, original_source_offset_ms=0,
        ),
    ))
    packets = replay.packets()
    detector = FakeDetector({
        packets[0].frame_id or "": (_animal(packets[0], original_box),),
        packets[2].frame_id or "": (_animal(packets[2], incompatible_box),),
    })
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await _observe_live_sequence(provider, packets)
    updates = [item for result in results for item in result.track_updates]
    assert len({item.generation_id for item in updates}) == 2
    started = [item for item in updates if item.status == "started"]
    assert len(started) == 2
    # The original (still-pending) track was not reacquired by the
    # spatially incompatible detection.
    pending_generation = started[0].generation_id
    pending_updates = [item for item in updates if item.generation_id == pending_generation]
    assert not any(item.detector_confirmation_count > 1 for item in pending_updates)


_BASE_TIMING_FACTS = (("connection_segment_id", "conn-a"), ("camera_id", "camera-1"), ("analysis_profile_id", "profile-1"))
_BOUNDARY_TIMING_FACTS = (
    ("connection_segment_id", "conn-b"), ("camera_id", "camera-1"), ("analysis_profile_id", "profile-1"),
    ("temporal_discontinuity", True), ("temporal_uncertainty_ms", 50),
)

_LIVE_RESET_VARIANTS = [
    pytest.param(
        {"provider_generation": "gen-2"}, "resets_true_source_change", id="provider_generation_change",
    ),
    pytest.param(
        {"timing_facts": tuple(dict(_BOUNDARY_TIMING_FACTS, camera_id="camera-2").items())},
        "resets_true_source_change", id="camera_identity_change",
    ),
    pytest.param(
        {"width": 640, "height": 480, "timing_facts": _BOUNDARY_TIMING_FACTS},
        "resets_true_source_change", id="profile_dimension_change",
    ),
    pytest.param(
        {
            "source_offset_ms": 200 + 60_000,
            "timing_facts": tuple(dict(_BOUNDARY_TIMING_FACTS, temporal_uncertainty_ms=50).items()),
        },
        "resets_true_source_change", id="excessive_reconnect_gap",
    ),
    pytest.param(
        {"timing_facts": tuple(dict(_BOUNDARY_TIMING_FACTS, temporal_uncertainty_ms=5_000).items())},
        "resets_true_source_change", id="excessive_temporal_uncertainty",
    ),
    pytest.param(
        {"timing_facts": (("temporal_discontinuity", True), ("temporal_uncertainty_ms", 50))},
        "resets_insufficient_provenance", id="missing_connection_segment_identity",
    ),
    pytest.param(
        {"timing_facts": _BOUNDARY_TIMING_FACTS + (("shutdown_boundary", True),)},
        "resets_true_source_change", id="shutdown_start_boundary",
    ),
]


@pytest.mark.parametrize("overrides,expected_fact", _LIVE_RESET_VARIANTS)
async def test_live_true_source_reset_variants_still_terminate(overrides: dict, expected_fact: str) -> None:
    """Scenarios 11/12/14/15/16/17/18: every category of confidently
    evidenced source-generation discontinuity, and the insufficient-
    provenance safety net, still fully reset the live tracker -- proving
    this stage did not trade away true-reset safety for bridging. A true
    reset's own finalized "ended" update is not surfaced through
    `observe_live_frame` (pre-existing, unchanged `restart_live_generation`
    behavior -- see its own docstring), so this checks the reset actually
    happened through `replay_semantic_facts()`/`last_reconnect_decision`
    plus a fresh, distinct generation for whatever comes after, rather than
    a discarded terminal `TrackUpdate`."""
    box = (0.2, 0.2, 0.5, 0.5)
    start = datetime(2026, 8, 6, tzinfo=UTC)

    def _packet(frame_id: str, offset_ms: int, timing_facts, *, width: int = 100, height: int = 100, provider_generation: str = "gen-1") -> FramePacket:
        return FramePacket(
            "stream", f"live:{frame_id}", start + timedelta(milliseconds=offset_ms), frame_id, offset_ms,
            width, height, provider_generation=provider_generation, timing_facts=timing_facts,
        )

    h0 = _packet("h0", 0, _BASE_TIMING_FACTS)
    h1 = _packet("h1", 200, _BASE_TIMING_FACTS)
    boundary_kwargs: dict[str, object] = {"provider_generation": "gen-1"}
    boundary_kwargs.update({key: value for key, value in overrides.items() if key not in {"timing_facts", "source_offset_ms"}})
    boundary = _packet("h2", overrides.get("source_offset_ms", 2_700), overrides.get("timing_facts", _BOUNDARY_TIMING_FACTS), **boundary_kwargs)
    after_reset = _packet("h3", boundary.source_offset_ms + 200, (), provider_generation=boundary.provider_generation, width=boundary.width or 100, height=boundary.height or 100)
    packets = (h0, h1, boundary, after_reset)
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    results = await _observe_live_sequence(provider, packets)
    updates = [item for result in results for item in result.track_updates]
    # The pre-reset generation's own started/updated facts are still
    # visible; only its "ended" update at the exact reset frame is
    # discarded (pre-existing `restart_live_generation` behavior).
    assert len({item.generation_id for item in updates}) == 2
    started = [item for item in updates if item.status == "started"]
    assert len(started) == 2
    facts = provider.replay_semantic_facts()
    assert facts[expected_fact] == 1
    assert facts["reconnect_bridges_continued"] == 0
    assert provider.last_reconnect_decision is not None
    assert provider.last_reconnect_decision.decision != CONTINUE_ACROSS_TRANSPORT_RECONNECT


async def test_live_stream_change_remains_hard_rejected_not_silently_bridged() -> None:
    """Scenario 13 ("stream change resets"): `observe_live_frame`'s own
    pre-existing guard -- a live session is started for exactly one
    stream_id -- already made a stream_id mismatch a hard error before this
    stage; this proves Stage 6.11B's new bridging code path never weakens
    that into a soft, silently-bridged reset."""
    frames = _frames(2)
    detector = FakeDetector()
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings())
    provider.load()
    provider.start_live("stream")
    await provider.observe_live_frame(frames[0])
    other_stream_frame = FramePacket(**{**frames[1].__dict__, "stream_id": "a-different-stream"})
    with pytest.raises(ReplayValidationError, match="live_stream_not_started"):
        await provider.observe_live_frame(other_stream_frame)


async def test_live_reconnect_does_not_duplicate_evidence_candidates_or_visit_proposals() -> None:
    """Scenarios 20/21: bridging a reconnect must not duplicate evidence
    candidates or emit more than one VisitProposal for the one coherent
    episode that spans it."""
    box = (0.2, 0.2, 0.5, 0.5)
    replay = ReplayInput("live-no-duplicates", "stream", 100, 100, 5.0, (
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
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0, evidence_ring_size=4))
    provider.load()
    results = await _observe_live_sequence(provider, packets, finalize=True)
    proposals = [item for result in results for item in result.visit_proposals]
    evidence = [item for result in results for item in result.evidence_candidates]
    assert len(proposals) == 1
    assert len({item.proposal_key for item in proposals}) == 1
    assert proposals[0].idempotency_key == proposals[0].proposal_key
    # Every evidence candidate role is distinct: no frame is counted twice.
    assert len(evidence) == len({(item.role, item.frame_id) for item in evidence})


async def test_live_provider_generation_change_resets_scheduler_relevant_reset_signal() -> None:
    """Supports `LiveCameraNodeShadowSession`'s own outer reset side effects
    (burst-scheduler state, temporary payload cache): `live_reset_count`
    changes exactly once per true reset and never for a benign bridge, so a
    caller can distinguish the two with a cheap before/after comparison."""
    box = (0.2, 0.2, 0.5, 0.5)
    bridge_packets = (await _live_bridge_packets_without_post_reconnect_detection())[:3]
    detector = FakeDetector({bridge_packets[0].frame_id or "": (_animal(bridge_packets[0], box),)})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_settings(baseline_detector_fps=5.0))
    provider.load()
    provider.start_live("stream")
    before = provider.live_reset_count
    for packet in bridge_packets:
        await provider.observe_live_frame(packet)
    assert provider.live_reset_count == before  # a benign bridge never resets

    reset_frame = FramePacket(**{**bridge_packets[-1].__dict__, "frame_id": "reset-frame", "provider_generation": "gen-2"})
    await provider.observe_live_frame(reset_frame)
    assert provider.live_reset_count == before + 1


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


# =============================================================================
# Stage 6.16: sustained-visit continuity through detector-confidence dips
#
# Reproduces, then proves fixed, the real attempt-3 sustained-visit
# fragmentation: a genuinely continuous ~5-minute feeder-bird appearance
# fragmented into ~37 confirmed track generations (29 of them geometrically
# at the reviewed feeder perch -- see the characterization doc below) purely
# because detector confidence naturally dipped below strong_detection_
# threshold, and sometimes below the detector's own decode floor entirely,
# more often than the tracker's ordinary tight tracker_expiry_ms/
# maximum_frame_gap_ms bound tolerated -- independent of any reconnect (that
# mechanism is separately, already fixed; see the Stage 6.11 section above).
# Full real-data proof: data/field-acceptance/2026-08-07-stage6.16-
# sustained-visit-continuity/fragmentation-characterization.md (ignored,
# local). Parallel fixtures prove the fix does not create immortal tracks or
# unsafe merges. See docs/frame-driven-shadow-provider-contract.md.
# =============================================================================


def test_committed_stage616_scenario_catalog_exists() -> None:
    catalog = json.loads(Path("tests/fixtures/observation_stage616/scenarios.json").read_text(encoding="utf-8"))
    all_scenarios = [name for group in catalog["scenarios"].values() for name in group]
    assert len(all_scenarios) == len(set(all_scenarios)) >= 25


def _stage616_settings(**updates: object) -> FrameDrivenSettings:
    """Mirrors the real deployed frame-driven provider configuration
    (data/models/observation-onnx-cuda/frame-driven-provider-config.json),
    not arbitrary test-only numbers."""
    values: dict[str, object] = {
        "source_nominal_fps": 2.0,
        "baseline_detector_fps": 2.0,
        "candidate_detector_fps": 2.0,
        "strong_detection_threshold": 0.7,
        "minimum_detector_confirmations": 2,
        "minimum_tracker_support_frames": 1,
        "maximum_missed_frames": 3,
        "maximum_frame_gap_ms": 1500,
        "tracker_expiry_ms": 1200,
        "maximum_track_duration_ms": 120_000,
        "maximum_active_tracks": 8,
        "evidence_ring_size": 8,
        "pretrigger_frame_count": 2,
        "maximum_unsupported_detector_ms": 5000,
        "negative_detector_frames_to_end": 2,
        "weak_detector_support_floor": 0.05,
        "maximum_weak_support_span_ms": 15000,
    }
    values.update(updates)
    return FrameDrivenSettings(**values)


async def test_replay_sustained_visit_survives_confidence_dips_as_one_episode() -> None:
    """The primary Stage 6.16 fix-proof test. A ~37-second single-subject
    sequence modeled on the proven real attempt-3 mechanism (strong start;
    repeated below-threshold or entirely-missed dips of 2-2.5s -- past the
    tight tracker_expiry_ms/maximum_frame_gap_ms bound but each individually
    inside the existing maximum_unsupported_detector_ms budget -- strong
    reconfirmation, one tracker-only stretch, repeated several times; then a
    real departure) fragmented into 12 generations run against unmodified
    pre-Stage-6.16 HEAD (75eea1c) before this fix was implemented -- see
    fragmentation-characterization.md. It must now remain one coherent
    confirmed episode until the final departure."""
    box = (0.4, 0.4, 0.6, 0.6)
    # (offset_ms, score) -- score None means no detection this frame at all
    # (bridged only by the tracker-support resolver, or a true final gap).
    schedule: list[tuple[int, float | None]] = [
        (0, 0.8), (500, 0.82),
        (2600, 0.25), (5100, 0.3), (7600, 0.85), (10100, 0.2), (12300, None), (14700, 0.83),
        (17200, 0.3), (19600, 0.28), (22000, 0.86),
        (24500, 0.15), (26900, None), (29300, 0.22), (31700, 0.88),
        (34200, None), (36700, None),  # true departure: explicit negatives then silence
    ]
    frames = tuple(ReplayFrame(index, offset, f"h{index}") for index, (offset, _score) in enumerate(schedule))
    replay = ReplayInput("sustained-visit", "stream", 100, 100, 2.0, frames)
    packets = replay.packets()
    detections = {
        packet.frame_id or "": (_animal(packet, box, score),)
        for packet, (_offset, score) in zip(packets, schedule)
        if score is not None
    }
    detector = FakeDetector(detections)
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_stage616_settings(),
        tracker_support=lambda _frame, track: track.bounding_box,
    )
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]
    generations = {item.generation_id for item in updates}

    assert len(generations) <= 2  # was 12 before this stage's fix
    assert len(proposals) >= 1
    assert proposals[0].shadow_only is True
    assert provider.capabilities.production_proposal_authority is False
    facts = provider.replay_semantic_facts()
    assert facts["confidence_dip_bridges"] >= 5
    assert facts["weak_detector_support_frames"] >= 5
    assert facts["strong_detector_support_frames"] >= 2
    assert facts["tracks_confirmed"] == len(proposals)


async def test_replay_attempt2_like_static_clutter_scenario_gets_no_widened_tolerance() -> None:
    """Scenario 30 (hard-negative regression), precisely stated: a static
    false-positive geometry -- modeled on the real attempt-2 red-glass-
    feeder pattern, whose maximum score across an entire real session
    (0.417) never once reached the real deployed strong_detection_threshold
    (0.7) -- produces a weak detection repeatedly at a fixed location.
    Confirming from two spatially-coherent weak hits is pre-existing,
    unchanged behavior (attempt-2's own real session already produced 38
    such confirmed clutter proposals under pre-Stage-6.16 code; proposal
    *precision* on genuine clutter is an existing, separate, out-of-scope
    detector-precision question -- see the hard scope boundary). What this
    stage must guarantee: such clutter, having never shown a genuinely
    strong hit, gets only the bounded, one-time "provisional" widened-
    tolerance allowance (`maximum_weak_support_span_ms`) from its own
    start, never the permanent one a real strong hit grants -- proven here
    by a gap well past that bounded allowance still splitting it into a
    fresh generation."""
    box = (0.6, 0.3, 0.68, 0.4)  # small, fixed, feeder-ornament-shaped region
    schedule: list[tuple[int, float]] = [(0, 0.3), (600, 0.35), (9000, 0.3)]
    frames = tuple(ReplayFrame(index, offset, f"clutter-{index}") for index, (offset, _score) in enumerate(schedule))
    replay = ReplayInput("attempt2-like-clutter", "stream", 100, 100, 2.0, frames)
    packets = replay.packets()
    detections = {
        packet.frame_id or "": (_animal(packet, box, score),)
        for packet, (_offset, score) in zip(packets, schedule)
    }
    detector = FakeDetector(detections)
    provider = FrameDrivenObservationProvider(
        detector=detector, settings=_stage616_settings(maximum_weak_support_span_ms=3000),
    )
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]

    confirmed_generations = {item.generation_id for item in updates if item.lifecycle_state == "confirmed"}
    assert len(confirmed_generations) == 1  # two coherent weak hits confirm -- ordinary, unchanged bar
    generation = next(iter(confirmed_generations))
    # The 8400ms gap to the third hit is well past the bounded 3000ms
    # provisional allowance measured from this never-strong track's own
    # start -- it must not have bridged.
    third_hit = next(item for item in updates if item.frame_id == packets[2].frame_id and item.status != "ended")
    assert third_hit.generation_id != generation
    facts = provider.replay_semantic_facts()
    assert facts["strong_detector_support_frames"] == 0
    assert facts["weak_detector_support_frames"] > 0


async def test_replay_reconnect_bridging_remains_unchanged_with_weak_evidence() -> None:
    """Scenario 19: a benign transport reconnect still bridges cleanly
    (Stage 6.11, unmodified) when the post-reconnect evidence happens to be
    weak rather than strong -- the two mechanisms compose without either
    one changing the other's behavior."""
    box = (0.2, 0.2, 0.5, 0.5)
    # Offsets (unlike the Stage 6.11 fixtures above, which use a 5fps
    # candidate cadence) are spaced to clear this test's own 2fps
    # (500ms-interval) `_stage616_settings` cadence, so both pre-reconnect
    # frames are actually inferred and the track reaches `confirmed`.
    replay = ReplayInput("bridge-with-weak-evidence", "stream", 100, 100, 2.0, (
        ReplayFrame(0, 0, "h0", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(1, 600, "h1", provider_generation="gen-1", connection_segment_id="conn-a", connection_segment_ordinal=0),
        ReplayFrame(
            2, 3_100, "h2", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1,
            temporal_discontinuity=True, temporal_uncertainty_ms=50, original_source_offset_ms=0,
        ),
        ReplayFrame(3, 3_600, "h3", provider_generation="gen-1", connection_segment_id="conn-b", connection_segment_ordinal=1),
    ))
    packets = replay.packets()
    detector = FakeDetector({
        packets[0].frame_id or "": (_animal(packets[0], box, 0.85),),
        packets[1].frame_id or "": (_animal(packets[1], box, 0.85),),
        # Post-reconnect evidence is deliberately weak.
        packets[2].frame_id or "": (_animal(packets[2], box, 0.2),),
        packets[3].frame_id or "": (_animal(packets[3], box, 0.2),),
    })
    provider = FrameDrivenObservationProvider(detector=detector, settings=_stage616_settings())
    provider.load()
    results = await provider.replay_frames(packets)
    updates = [item for result in results for item in result.track_updates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len({item.generation_id for item in updates}) == 1
    assert len(proposals) == 1
    facts = provider.replay_semantic_facts()
    assert facts["reconnect_bridges_continued"] == 1
    assert facts["reconnect_bridges_expired"] == 0
    reacquired = next(item for item in updates if item.frame_id == packets[2].frame_id)
    assert reacquired.support_state == "weak_detector_supported"


async def test_replay_reconnect_itself_adds_no_weak_or_strong_support() -> None:
    """Scenario 20 (Stage 6.16 variant): surviving a reconnect boundary by
    itself changes neither `detector_confirmation_count` nor
    `weak_detector_support_count` -- only genuine post-reconnect evidence
    (tested above) does."""
    tracker = ProviderNeutralFrameTracker("stream", _stage616_settings().tracker_configuration())
    box = (0.2, 0.2, 0.5, 0.5)
    frames = _frames(2, step_ms=1000)
    tracker.observe(frames[0], (_animal(frames[0], box, 0.8),))
    tracker.observe(frames[1], (_animal(frames[1], box, 0.85),))
    before = next(iter(tracker._tracks.values()))
    detector_before = before.detector_confirmation_count
    weak_before = before.weak_detector_support_count

    tracker.note_reconnect_boundary(boundary_offset_ms=6000, captured_at=frames[1].captured_at)
    after = next(iter(tracker._tracks.values()))
    assert after.detector_confirmation_count == detector_before
    assert after.weak_detector_support_count == weak_before
    assert after.support_state == "temporarily_lost"


async def test_replay_evidence_remains_generation_isolated_with_weak_dips() -> None:
    """Scenario 22/23: even though a confirmed track's episode now spans a
    confidence dip instead of splitting there, evidence-candidate/burst-role
    bookkeeping remains correctly scoped to that one (now longer) generation
    -- it never leaks into whatever starts next."""
    box = (0.4, 0.4, 0.6, 0.6)
    schedule: list[tuple[int, float | None]] = [
        (0, 0.8), (500, 0.85), (3000, 0.2), (6000, 0.86),
    ]
    frames = tuple(ReplayFrame(index, offset, f"h{index}") for index, (offset, _score) in enumerate(schedule))
    replay = ReplayInput("evidence-isolated-weak", "stream", 100, 100, 2.0, frames)
    packets = replay.packets()
    detections = {
        packet.frame_id or "": (_animal(packet, box, score),)
        for packet, (_offset, score) in zip(packets, schedule)
        if score is not None
    }
    detector = FakeDetector(detections)
    provider = FrameDrivenObservationProvider(detector=detector, settings=_stage616_settings())
    provider.load()
    results = await provider.replay_frames(packets)
    evidence = [item for result in results for item in result.evidence_candidates]
    proposals = [item for result in results for item in result.visit_proposals]

    assert len(proposals) == 1
    generation = proposals[0].track_generation_id
    assert evidence  # the dip did not wipe out evidence bookkeeping
    assert all(item.track_generation_id == generation for item in evidence)


async def test_replay_sustained_visit_fingerprint_repeats() -> None:
    """Scenario 24/26: the sustained-visit-with-dips replay is fully
    deterministic and reproducible -- identical semantic fingerprint,
    track updates, and proposals across two independent runs."""
    box = (0.4, 0.4, 0.6, 0.6)
    schedule: list[tuple[int, float | None]] = [
        (0, 0.8), (500, 0.85), (3000, 0.2), (5800, None), (8200, 0.87),
    ]
    frames = tuple(ReplayFrame(index, offset, f"h{index}") for index, (offset, _score) in enumerate(schedule))
    replay = ReplayInput("sustained-visit-determinism", "stream", 100, 100, 2.0, frames)
    manifest = BenchmarkManifest(1, "sustained-visit-determinism", replay.fingerprint, (), ())

    def build_provider() -> FrameDrivenObservationProvider:
        packets = replay.packets()
        detections = {
            packet.frame_id or "": (_animal(packet, box, score),)
            for packet, (_offset, score) in zip(packets, schedule)
            if score is not None
        }
        instance = FrameDrivenObservationProvider(
            detector=FakeDetector(detections), settings=_stage616_settings(),
            tracker_support=lambda _frame, track: track.bounding_box,
        )
        instance.load()
        return instance

    first = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(
        replay, manifest, provider_key="frame-driven-onnx-cuda",
    )
    second = await ReplayRunner({"frame-driven-onnx-cuda": build_provider()}).run(
        replay, manifest, provider_key="frame-driven-onnx-cuda",
    )
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.track_updates == second.track_updates
    assert first.proposals == second.proposals
    assert first.metrics["confidence_dip_bridge_count"] == second.metrics["confidence_dip_bridge_count"]


async def test_snapshot_provider_capabilities_remain_unchanged_stage616() -> None:
    """Scenario 25."""
    from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

    assert SnapshotObservationProvider.capabilities.tracking is False
    assert SnapshotObservationProvider.capabilities.frame_driven is False
    assert SnapshotObservationProvider.capabilities.production_proposal_authority is False


async def test_replay_privacy_ignore_exclusion_still_applies_to_weak_detections() -> None:
    """Scenario 28: Privacy/Ignore exclusion still masks a detection inside
    an excluded region regardless of its confidence -- the bounded evidence
    hierarchy changes tracker-continuity handling only, never detection
    filtering, which still happens upstream of it in `_process_frame`."""
    excluded_region = (0.0, 0.0, 0.5, 0.5)
    box_inside = (0.1, 0.1, 0.2, 0.2)
    frames = (
        ReplayFrame(0, 0, "h0", analysis_excluded_regions=(excluded_region,)),
        ReplayFrame(1, 500, "h1", analysis_excluded_regions=(excluded_region,)),
    )
    replay = ReplayInput("privacy-weak", "stream", 100, 100, 2.0, frames)
    packets = replay.packets()
    detector = FakeDetector({packet.frame_id or "": (_animal(packet, box_inside, 0.2),) for packet in packets})
    provider = FrameDrivenObservationProvider(detector=detector, settings=_stage616_settings())
    provider.load()
    results = await provider.replay_frames(packets)
    detections = [item for result in results for item in result.detection_observations]
    proposals = [item for result in results for item in result.visit_proposals]
    assert detections == []
    assert proposals == []


def test_stage616_modules_have_no_product_repository_or_transport_dependency() -> None:
    """Scenario 26/27 (no product writes, no authority change): the same
    structural, source-grep boundary as every prior Stage 6.x pure module,
    re-verified after this stage's additions."""
    forbidden = (
        "mockingbird.db", "mockingbird.repositories", "mockingbird.api.main", "ReviewLabel",
        "MotionEvidence", "StreamMonitoringPolicy", "LiveCameraSession", "sqlalchemy",
    )
    for relative in ("frame_tracker.py", "frame_driven_provider.py", "replay.py", "contracts.py"):
        source = Path(f"src/mockingbird/observation/{relative}").read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), relative
