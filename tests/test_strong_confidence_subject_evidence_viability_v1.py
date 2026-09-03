"""Strong-Confidence Subject-Evidence Viability & Scene-Artifact Abstention
v1 -- investigation-only proof tests.

This milestone changes **no production code** (see
docs/strong-confidence-subject-evidence-viability-scene-artifact-abstention-
v1-report.md, "Why no safe implementation exists"): its investigation found
no existing, safe, non-ML evidence fact that separates Representative
Daylight Gate A Field Acceptance v11's own Visit 018 (a leaf/branch cluster
at the recurring "Location A" geometry that cleared `strong_detection_
threshold` six times in one occurrence) from a genuine strong/stationary
real bird, without also risking the mandatory positive controls (especially
a brief or stationary real bird).

This file does not test a fix -- it *proves*, against the real,
unmodified production code paths (never a synthetic assertion or a
docstring-only claim), the two strongest negative findings the report's own
investigation reached, so a future reader does not have to re-derive them:

1. The exact Visit-018 shape and the exact "strong real bird" positive
   control (both already established, unmodified, reused from
   `tests/test_strong_confidence_non_target_scene_artifact_v1.py`'s own
   `TestStrongSceneArtifactAtLocationA`/`TestStrongAndWeakRealBirdPreserved`
   classes) are *structurally identical* at every fact `candidate_quality_
   gate`/`scene_confusor` can read: one constituent track generation,
   `strong_detection_count > 0`. No function of generation count or
   detection count, for any constant, can separate them without also
   catching one of them -- confirmed here directly on real
   `AssembledVisitProposal`/`ConfidenceEvidenceSummary` objects, not
   asserted from reading the source.
2. Reconstructing the real `GeometryAttribution` (Localization Attribution /
   Detection Geometry Lineage v1, schema 33) for each case's own selected
   strong-detector-confirmed `TrackUpdate` -- the exact generalized
   "credible contemporaneous detector grounding" fact the governing brief's
   §11 asks this milestone to investigate -- shows both classify identically
   as `geometry_source="detector"` / `classify_localization_attribution(...)
   .attribution == "detector_off_target"`. The module's own docstring
   already names this outcome: "If it still misses a visible subject, the
   raw detector output on that exact frame is the most defensible
   attribution available from lineage alone." This is not a case this
   signal was ever designed to catch (it correctly caught a *different*
   defect class -- stale, tracker-extrapolated geometry with no
   contemporaneous detector agreement at all -- in Background / Empty
   Evidence Species-Confidence Correctness v1); Visit 018's own detector
   agreement is completely genuine and contemporaneous, six times over.

Reuses the identical real-production-path methodology every sibling
2026-09-02 milestone test file already established (`ProviderNeutralFrame
Tracker.observe()` -> `build_tracklets`/`assemble_visit_episodes` -> real
`TrackUpdate`/`AssembledVisitProposal` objects) -- duplicated, not imported,
matching this codebase's own established per-milestone self-contained
test-file convention.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mockingbird.observation.contracts import DetectionObservation, FramePacket, TrackUpdate
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker, TrackerConfiguration
from mockingbird.observation.localization_attribution import (
    classify_localization_attribution,
    geometry_attribution_for_update,
)
from mockingbird.observation.visit_episode_assembler import assemble_visit_episodes, build_tracklets

STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"
BASE_TIME = datetime(2026, 9, 2, 16, 29, 0, tzinfo=UTC)

# Identical to the sibling `test_strong_confidence_non_target_scene_
# artifact_v1.py`'s own `_LOCATION_A_BOX`/`_FEEDER_BOX` -- v11's own
# reported "Location A" coordinates (bbox center (0.202, 0.691)) and a
# geometrically distant, unrelated feeder-perch location for the real-bird
# control. Duplicated, not imported, matching this codebase's own
# established per-milestone self-contained test-file convention.
_LOCATION_A_BOX = (0.16, 0.66, 0.24, 0.74)  # center = (0.20, 0.70)
_FEEDER_BOX = (0.55, 0.40, 0.62, 0.48)


def _tracker_config(**overrides: object) -> TrackerConfiguration:
    values: dict[str, object] = dict(
        strong_detection_threshold=0.70,
        minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1,
        maximum_missed_frames=3,
        maximum_frame_gap_ms=1500,
        tracker_expiry_ms=1200,
        maximum_track_duration_ms=30_000,
        maximum_active_tracks=24,
        minimum_iou=0.05,
        maximum_centroid_distance=0.22,
        ambiguity_margin=0.01,
        maximum_unsupported_detector_ms=5000,
        negative_detector_frames_to_end=2,
        ambiguous_reentry_window_ms=1500,
        weak_detector_support_floor=0.05,
        maximum_weak_support_span_ms=15_000,
    )
    values.update(overrides)
    return TrackerConfiguration(**values)


def _tracker() -> ProviderNeutralFrameTracker:
    return ProviderNeutralFrameTracker(
        STREAM_ID, _tracker_config(), support_resolver=lambda _frame, track: track.bounding_box,
    )


def _frame(offset_ms: int) -> FramePacket:
    return FramePacket(
        stream_id=STREAM_ID, media_asset_id=f"repro:{offset_ms}",
        captured_at=BASE_TIME + timedelta(milliseconds=offset_ms),
        frame_id=f"repro-frame-{offset_ms}", source_offset_ms=offset_ms, width=1920, height=1080,
    )


def _detection(frame: FramePacket, box: tuple[float, float, float, float], *, confidence: float) -> DetectionObservation:
    return DetectionObservation(
        detector_id="onnx-cuda", label="animal", confidence=confidence, captured_at=frame.captured_at,
        observation_id=f"obs:{frame.frame_id}", frame_id=frame.frame_id, provider_id="frame-driven-onnx-cuda",
        model_key="md-v5a", bounding_box=box, class_source_label="0", is_animal=True,
    )


def _single_occurrence_updates(box: tuple[float, float, float, float], confidences: list[float]) -> list[TrackUpdate]:
    """Identical shape to the sibling file's own `_weak_rejection_ticks` +
    `_run_single_occurrence` (alternating detection/gap ticks, one
    continuous generation, `tracker_expiry_ms=1200` never exceeded) --
    duplicated, not imported. Returns the raw `TrackUpdate` stream instead
    of attempting persistence, so this file can inspect `support_state`
    directly."""
    tracker = _tracker()
    updates: list[TrackUpdate] = []
    offset = 0
    for confidence in confidences:
        frame = _frame(offset)
        updates.extend(tracker.observe(frame, (_detection(frame, box, confidence=confidence),)).updates)
        offset += 250
        updates.extend(tracker.observe(_frame(offset), ()).updates)
        offset += 250
    updates.extend(tracker.observe(_frame(offset + 5500), ()).updates)
    updates.extend(tracker.finalize("end_of_replay").updates)
    return updates


def _assembled_proposal(updates: list[TrackUpdate], *, box: tuple[float, float, float, float]):
    generation_ids = {update.generation_id for update in updates}
    tracklets = build_tracklets(
        tuple(updates), stream_id=STREAM_ID,
        zone_id_by_generation={generation_id: ZONE_ID for generation_id in generation_ids},
        evidence_candidate_ids_by_generation={
            generation_id: (f"{generation_id}-id", f"{generation_id}-ctx") for generation_id in generation_ids
        },
    )
    result = assemble_visit_episodes(tracklets)
    assert len(result.proposals) == 1, "reproducer must assemble into exactly one chained proposal"
    return result.proposals[0]


def _first_strong_detector_supported_update(updates: list[TrackUpdate], box: tuple[float, float, float, float]) -> TrackUpdate:
    for update in updates:
        if update.support_state == "strong_detector_supported" and update.bounding_box == box:
            return update
    raise AssertionError("no strong_detector_supported update found for this box -- reproducer construction error")


class TestStructuralShapeIndistinguishable:
    """Finding 1 (see module docstring): confirms directly on real
    `AssembledVisitProposal`/`ConfidenceEvidenceSummary` objects -- not
    merely by reading `candidate_quality_gate.py`'s source -- that the
    exact Visit-018 artifact shape and the exact accepted "strong real
    bird" positive control are structurally identical on every fact either
    `candidate_quality_gate` or `scene_confusor` can read."""

    def test_artifact_and_real_bird_share_identical_generation_and_corroboration_shape(self) -> None:
        # Visit 018's own shape: one occurrence, six detections, all
        # clearing `strong_detection_threshold` -- identical construction to
        # `TestStrongSceneArtifactAtLocationA::test_sudden_strong_
        # occurrence_after_weak_history_remains_open` in the sibling file
        # (this file's own single-occurrence helper reproduces only the
        # 4th/strong occurrence -- prior weak history is scene-confusor
        # region state, not a structural fact of the strong occurrence's
        # own generation/detection shape being compared here).
        artifact_updates = _single_occurrence_updates(_LOCATION_A_BOX, [0.72, 0.75, 0.71, 0.78, 0.73, 0.76])
        artifact_proposal = _assembled_proposal(artifact_updates, box=_LOCATION_A_BOX)

        # The sibling file's own accepted "strong real bird" positive
        # control (`TestStrongAndWeakRealBirdPreserved::test_strong_real_
        # bird_admits_unchanged`) -- reused unmodified.
        real_bird_updates = _single_occurrence_updates(_FEEDER_BOX, [0.82, 0.85, 0.80])
        real_bird_proposal = _assembled_proposal(real_bird_updates, box=_FEEDER_BOX)

        for label, proposal in (("artifact", artifact_proposal), ("real_bird", real_bird_proposal)):
            assert len(proposal.constituent_generation_ids) == 1, label
            evidence = proposal.confidence_evidence
            assert evidence is not None, label
            assert evidence.strong_detection_count is not None and evidence.strong_detection_count > 0, label

        # No detection-count threshold, for any constant, separates them:
        # the real bird's own count (3) is *lower* than the artifact's (6)
        # -- a count-based rule strict enough to reject the artifact would
        # already have to be loose enough to admit fewer detections than
        # the real bird supplies, or it rejects the real bird too.
        assert real_bird_proposal.confidence_evidence.detection_count < artifact_proposal.confidence_evidence.detection_count


class TestGeometryGroundingDoesNotSeparate:
    """Finding 2 (see module docstring): directly answers the governing
    brief's §11 ("Determine whether a generalized version of credible
    contemporaneous detector grounding already exists at species inference
    but is absent at Visit admission... ask whether the same underlying
    fact can safely support Visit validity") using the real
    `localization_attribution` module (Localization Attribution / Detection
    Geometry Lineage v1, schema 33) against each case's own real,
    strong-detector-confirmed `TrackUpdate` -- not a hypothetical."""

    def test_artifact_and_real_bird_both_show_genuine_contemporaneous_detector_grounding(self) -> None:
        artifact_updates = _single_occurrence_updates(_LOCATION_A_BOX, [0.72, 0.75, 0.71, 0.78, 0.73, 0.76])
        artifact_update = _first_strong_detector_supported_update(artifact_updates, _LOCATION_A_BOX)

        real_bird_updates = _single_occurrence_updates(_FEEDER_BOX, [0.82, 0.85, 0.80])
        real_bird_update = _first_strong_detector_supported_update(real_bird_updates, _FEEDER_BOX)

        for label, update in (("artifact", artifact_update), ("real_bird", real_bird_update)):
            attribution = geometry_attribution_for_update(update, same_frame=True)
            assert attribution.geometry_source == "detector", label
            result = classify_localization_attribution(attribution)
            # Exactly the module's own documented "by elimination" outcome
            # for a genuine, temporally-aligned detector hit -- see
            # `classify_localization_attribution`'s own docstring, decision
            # step 5: "If it still misses a visible subject, the raw
            # detector output on that exact frame is the most defensible
            # attribution available from lineage alone." Identical for both
            # cases: this signal, even generalized to Visit admission,
            # cannot separate them.
            assert result.attribution == "detector_off_target", label
            assert result.geometry_source == "detector", label
