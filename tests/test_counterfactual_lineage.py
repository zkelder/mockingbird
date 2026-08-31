"""Rejected / Suppressed Detection Attribution v1 (see
docs/rejected-detection-attribution-contract.md): focused, hardware-free
unit tests for the bounded counterfactual ledger, its ROI/time-window
query, and its deterministic attribution classifier.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.contracts import (
    EMPTY_CONFIDENCE_EVIDENCE,
    DetectionObservation,
    FramePacket,
    ObservationResult,
    TrackUpdate,
)
from mockingbird.observation.counterfactual_lineage import (
    ADMISSION_REJECTED_OUTCOMES,
    CounterfactualLedger,
    CounterfactualRetentionConfig,
    RawDetectionRecord,
    TrackGenerationRecord,
    classify_rejection_attribution,
)
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal

STREAM_ID = "stream-backyard-feeder"
NOW = datetime(2026, 8, 11, 18, 0, 0, tzinfo=UTC)
BOX = (0.40, 0.40, 0.50, 0.50)
ROI = (0.35, 0.35, 0.55, 0.55)
OUTSIDE_ROI = (0.0, 0.0, 0.05, 0.05)


# --- structural purity (matches every other Stage 6.x/7 pure module) -------


def test_counterfactual_lineage_module_has_no_product_repository_import() -> None:
    source = Path("src/mockingbird/observation/counterfactual_lineage.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "onnxruntime", "cv2",
    )
    for token in forbidden:
        assert token not in source, f"counterfactual_lineage.py must not reference {token}"


# --- fixtures ----------------------------------------------------------------


def _frame(offset_ms: int, *, frame_id: str | None = None) -> FramePacket:
    frame_id = frame_id or f"frame-{offset_ms}"
    return FramePacket(
        stream_id=STREAM_ID,
        media_asset_id=f"shadow-frame:{frame_id}",
        captured_at=NOW + timedelta(milliseconds=offset_ms),
        frame_id=frame_id,
        source_offset_ms=offset_ms,
        node_session_id="node-session-a",
        provider_generation="generation-a",
    )


def _detection(
    offset_ms: int, *, box: tuple[float, float, float, float] = BOX, confidence: float = 0.8,
    label: str = "animal", is_animal: bool = True, frame_id: str | None = None,
) -> DetectionObservation:
    frame_id = frame_id or f"frame-{offset_ms}"
    return DetectionObservation(
        detector_id="onnx-cuda:mdv5", label=label, confidence=confidence,
        captured_at=NOW + timedelta(milliseconds=offset_ms), observation_id=f"obs-{offset_ms}",
        frame_id=frame_id, provider_id="onnx-cuda", bounding_box=box, is_animal=is_animal,
    )


def _result(
    offset_ms: int, *, detections: tuple[DetectionObservation, ...] = (),
    track_updates: tuple[TrackUpdate, ...] = (), detector_ran: bool = True,
) -> ObservationResult:
    return ObservationResult(
        provider_id="frame-driven-onnx-cuda", source_id="live_shadow", stream_id=STREAM_ID,
        observed_at=NOW + timedelta(milliseconds=offset_ms), frame_packets=(_frame(offset_ms),),
        detection_observations=detections, track_updates=track_updates, detector_ran=detector_ran,
    )


def _track_update(
    *, generation_id: str, track_id: str, offset_ms: int, status: str, lifecycle_state: str,
    box: tuple[float, float, float, float] = BOX, support_state: str = "strong_detector_supported",
    confidence: float = 0.8, terminal_reason: str | None = None, detector_confirmation_count: int = 1,
    bounding_box_source_offset_ms: int | None = None,
) -> TrackUpdate:
    return TrackUpdate(
        track_id=track_id, generation_id=generation_id, captured_at=NOW + timedelta(milliseconds=offset_ms),
        status=status, lifecycle_state=lifecycle_state, frame_id=f"frame-{offset_ms}", source_offset_ms=offset_ms,
        broad_class="animal", bounding_box=box, supporting_frame_ids=(f"frame-{offset_ms}",),
        detector_confirmation_count=detector_confirmation_count, confidence=confidence,
        support_state=support_state, detector_ran=True, terminal_reason=terminal_reason,
        bounding_box_source_offset_ms=bounding_box_source_offset_ms if bounding_box_source_offset_ms is not None else offset_ms,
    )


def _assembled_proposal(generation_id: str, proposal_id: str, *, start_ms: int = 1000, end_ms: int = 3000) -> AssembledVisitProposal:
    return AssembledVisitProposal(
        proposal_id=proposal_id, stream_id=STREAM_ID, broad_class="animal",
        start_offset_ms=start_ms, end_offset_ms=end_ms,
        constituent_generation_ids=(generation_id,), constituent_track_ids=(f"{generation_id}-track",),
        supporting_frame_ids=(), source_capture_frame_ids=(), evidence_candidate_ids=(),
        assembly_decisions=(),
    )


def _confirmed_generation_ledger(
    *, generation_id: str = "gen-confirmed", start_ms: int = 1000, end_ms: int = 3000, confidence: float = 0.6,
) -> CounterfactualLedger:
    """A ledger with exactly one confirmed, detector-anchored track
    generation whose geometry overlaps `ROI` -- the shared starting point
    for the admission-outcome tests below."""
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(start_ms, detections=(_detection(start_ms, confidence=confidence),)))
    started = _track_update(
        generation_id=generation_id, track_id=f"{generation_id}-track", offset_ms=start_ms,
        status="started", lifecycle_state="confirmed", support_state="weak_detector_supported",
    )
    ended = _track_update(
        generation_id=generation_id, track_id=f"{generation_id}-track", offset_ms=end_ms,
        status="ended", lifecycle_state="ended", support_state="weak_detector_supported",
        terminal_reason="maximum_unsupported_duration", detector_confirmation_count=2,
    )
    ledger.observe_result(_result(start_ms, track_updates=(started,)))
    ledger.observe_result(_result(end_ms, track_updates=(ended,)))
    return ledger


# --- 1. raw hit -> track -> suppressed proposal retains reconstructable lineage --


def test_detector_hit_then_suppressed_retains_full_lineage() -> None:
    ledger = _confirmed_generation_ledger(generation_id="gen-suppressed")
    proposal = _assembled_proposal("gen-suppressed", "proposal-suppressed")
    ledger.record_proposal_outcome(
        proposal, outcome="blocked_ambiguous_boundary",
        reason="proposal_boundary_ambiguous_with_adjacent_proposal", visit_id=None,
        decided_at=NOW, known_horizon_ms=3_500,
    )

    window = ledger.query(start_offset_ms=0, end_offset_ms=4_000, roi=ROI)
    result = classify_rejection_attribution(window)

    assert result.attribution == "detector_hit_then_suppressed"
    assert result.supporting_proposal_id == "proposal-suppressed"
    outcome_record = next(item for item in window.proposal_outcomes if item.proposal_id == "proposal-suppressed")
    assert outcome_record.reason == "proposal_boundary_ambiguous_with_adjacent_proposal"
    assert outcome_record.constituent_generation_ids == ("gen-suppressed",)
    assert outcome_record.admitted is False
    generation_record = next(item for item in window.track_generations if item.generation_id == "gen-suppressed")
    assert generation_record.confirmed is True
    assert generation_record.confidence_evidence.detection_count >= 1


# --- 2. detector hit -> tracker subsequently loses/coasts the subject ------


def test_detector_hit_then_tracker_lost_for_unconfirmed_generation() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=(_detection(1_000, confidence=0.3),)))
    started = _track_update(
        generation_id="gen-lost", track_id="track-lost", offset_ms=1_000,
        status="started", lifecycle_state="tentative", support_state="weak_detector_supported",
    )
    ended = _track_update(
        generation_id="gen-lost", track_id="track-lost", offset_ms=1_800,
        status="ended", lifecycle_state="rejected", support_state="temporarily_lost",
        terminal_reason="insufficient_support",
    )
    ledger.observe_result(_result(1_000, track_updates=(started,)))
    ledger.observe_result(_result(1_800, track_updates=(ended,)))

    window = ledger.query(start_offset_ms=0, end_offset_ms=2_000, roi=ROI)
    result = classify_rejection_attribution(window)

    assert result.attribution == "detector_hit_then_tracker_lost"
    assert result.supporting_generation_id == "gen-lost"
    generation_record = next(item for item in window.track_generations if item.generation_id == "gen-lost")
    assert generation_record.confirmed is False
    assert generation_record.terminal_reason == "insufficient_support"


# --- 3. detector hit -> authority/admission rejection retains exact reason -


def test_admission_rejected_retains_exact_quality_gate_reason() -> None:
    ledger = _confirmed_generation_ledger(generation_id="gen-rejected")
    proposal = _assembled_proposal("gen-rejected", "proposal-rejected")
    ledger.record_proposal_outcome(
        proposal, outcome="reject_subject_geometry_invalid",
        reason="selected_evidence_missing_subject_geometry", visit_id=None,
        decided_at=NOW, known_horizon_ms=3_500,
    )

    window = ledger.query(start_offset_ms=0, end_offset_ms=4_000, roi=ROI)
    result = classify_rejection_attribution(window)

    assert result.attribution == "admission_rejected"
    outcome_record = next(item for item in window.proposal_outcomes if item.proposal_id == "proposal-rejected")
    assert outcome_record.outcome == "reject_subject_geometry_invalid"
    assert outcome_record.reason == "selected_evidence_missing_subject_geometry"
    assert outcome_record.outcome in ADMISSION_REJECTED_OUTCOMES


# --- 4. high-confidence clutter false positive remains diagnostic, not truth --


def test_high_confidence_detection_is_retained_as_diagnostic_only() -> None:
    """Candidate-009's own real shape (0.935 confidence, strong, on pure
    clutter -- see data/field-acceptance/2026-08-11-localization-attribution
    -live-evidence/diagnosed-009.json): the ledger retains it as evidence,
    never as an Observation/Visit/ReviewLabel. This module has no product
    -repository import at all (see the structural test above), so nothing
    it does can reach the truth boundary; this test additionally proves the
    record itself carries no truth-shaped field (no `reviewed`, `species`,
    or similar) and remains queryable exactly like any other raw detection."""

    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(500, detections=(_detection(500, confidence=0.935, box=BOX),)))

    window = ledger.query(start_offset_ms=0, end_offset_ms=1_000, roi=ROI)
    assert len(window.raw_detections_in_roi) == 1
    record = window.raw_detections_in_roi[0]
    assert isinstance(record, RawDetectionRecord)
    assert record.confidence == 0.935
    assert not hasattr(record, "reviewed_label")
    assert not hasattr(record, "species_guess")
    # A record this module builds is diagnostic evidence; classifying a
    # window it belongs to never crosses into an admitted/reviewed outcome
    # by itself (no track/proposal exists here at all).
    result = classify_rejection_attribution(window)
    assert result.attribution == "insufficient_counterfactual_lineage"


# --- 5. ROI/time query can find an overlapping detection -------------------


def test_query_finds_raw_detection_overlapping_roi_and_window() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=(_detection(1_000, box=BOX),)))

    in_roi = ledger.query(start_offset_ms=500, end_offset_ms=1_500, roi=ROI)
    assert len(in_roi.raw_detections_in_roi) == 1
    assert in_roi.raw_detections_in_roi[0].source_offset_ms == 1_000

    outside_roi = ledger.query(start_offset_ms=500, end_offset_ms=1_500, roi=OUTSIDE_ROI)
    assert outside_roi.raw_detections_in_roi == ()
    # The time-window-only (ROI-independent) view is unaffected by the ROI.
    assert outside_roi.raw_detections == in_roi.raw_detections

    outside_window = ledger.query(start_offset_ms=2_000, end_offset_ms=3_000, roi=ROI)
    assert outside_window.raw_detections == ()


# --- 6. complete covered interval, no overlap -> honest detector_miss ------


def test_detector_miss_when_coverage_complete_and_no_overlap() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    for offset in range(0, 2_001, 500):
        ledger.observe_result(_result(offset, detections=()))

    window = ledger.query(start_offset_ms=200, end_offset_ms=1_800, roi=ROI)
    result = classify_rejection_attribution(window)

    assert result.attribution == "detector_miss"
    assert window.coverage.complete_for(200, 1_800) is True


# --- 7. incomplete/evicted interval -> insufficient, never a false miss ----


def test_incomplete_coverage_returns_insufficient_not_a_false_detector_miss() -> None:
    config = CounterfactualRetentionConfig(
        max_raw_detection_records=3, max_track_generation_records=10,
        max_proposal_outcome_records=10, max_age_ms=10_000_000,
    )
    ledger = CounterfactualLedger(stream_id=STREAM_ID, config=config)
    for offset in range(0, 501, 100):  # 6 heartbeats; capacity 3 evicts offsets 0/100/200
        ledger.observe_result(_result(offset, detections=()))

    window = ledger.query(start_offset_ms=0, end_offset_ms=500, roi=ROI)
    result = classify_rejection_attribution(window)

    assert result.attribution == "insufficient_counterfactual_lineage"
    assert result.reason == "queried_window_not_fully_covered_by_retained_raw_detection_lineage"
    assert window.coverage.complete_for(0, 500) is False
    # A window entirely inside the still-retained tail is honestly complete.
    assert window.coverage.complete_for(400, 500) is True


# --- 8. retention eviction is deterministic and bounded ---------------------


def test_retention_eviction_is_deterministic_and_bounded() -> None:
    config = CounterfactualRetentionConfig(
        max_raw_detection_records=4, max_track_generation_records=10,
        max_proposal_outcome_records=10, max_age_ms=10_000_000,
    )

    def _build_accounting():
        ledger = CounterfactualLedger(stream_id=STREAM_ID, config=config)
        for offset in range(0, 700, 100):  # 7 heartbeats, capacity 4
            ledger.observe_result(_result(offset, detections=()))
        return ledger.coverage().raw_detection_retention

    first, second = _build_accounting(), _build_accounting()
    assert first == second  # deterministic: identical input, identical accounting
    assert first.recorded_count == 7
    assert first.retained_count == 4
    assert first.evicted_count == 3
    assert first.oldest_retained_offset_ms == 300
    assert first.newest_retained_offset_ms == 600


def test_retention_config_rejects_invalid_bounds() -> None:
    with pytest.raises(ValueError):
        CounterfactualRetentionConfig(max_raw_detection_records=0)
    with pytest.raises(ValueError):
        CounterfactualRetentionConfig(max_age_ms=0)


def test_query_rejects_invalid_window_and_roi() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    with pytest.raises(ValueError):
        ledger.query(start_offset_ms=100, end_offset_ms=0)
    with pytest.raises(ValueError):
        ledger.query(start_offset_ms=0, end_offset_ms=100, roi=(0.9, 0.0, 0.1, 1.0))


# --- 9. rejected telemetry never creates a Visit or Review Decision --------


def test_ledger_and_records_expose_no_review_or_visit_creation_surface() -> None:
    """Structural proof, alongside the module-level import guard above: none
    of `CounterfactualLedger`'s own public methods can write truth -- it has
    no method whose name suggests a write, and its constructor accepts no
    repository/session handle at all."""
    import inspect

    from mockingbird.observation import counterfactual_lineage as module

    signature = inspect.signature(CounterfactualLedger.__init__)
    for parameter in signature.parameters.values():
        assert "repository" not in parameter.name and "session" not in parameter.name.lower() or parameter.name == "self"
    public_methods = {
        name for name, value in inspect.getmembers(CounterfactualLedger)
        if not name.startswith("_") and inspect.isfunction(value)
    }
    assert public_methods == {"observe_result", "record_proposal_outcome", "coverage", "query"}
    assert not hasattr(module, "create_visit")
    assert not hasattr(module, "create_review_label")


# --- attribution edge cases -------------------------------------------------


def test_tracker_drift_when_region_geometry_is_tracker_sourced() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=(_detection(1_000, confidence=0.795),)))
    started = _track_update(
        generation_id="gen-drift", track_id="track-drift", offset_ms=1_000,
        status="started", lifecycle_state="confirmed", support_state="strong_detector_supported",
    )
    ended = _track_update(
        generation_id="gen-drift", track_id="track-drift", offset_ms=9_000,
        status="ended", lifecycle_state="ended", support_state="tracker_supported",
        terminal_reason="maximum_unsupported_duration", bounding_box_source_offset_ms=1_000,
    )
    ledger.observe_result(_result(1_000, track_updates=(started,)))
    ledger.observe_result(_result(9_000, track_updates=(ended,)))

    window = ledger.query(start_offset_ms=0, end_offset_ms=10_000, roi=ROI)
    result = classify_rejection_attribution(window)
    assert result.attribution == "tracker_drift"
    assert result.supporting_generation_id == "gen-drift"


def test_visit_created_when_the_constituent_generation_was_actually_admitted() -> None:
    ledger = _confirmed_generation_ledger(generation_id="gen-admitted")
    proposal = _assembled_proposal("gen-admitted", "proposal-admitted")
    ledger.record_proposal_outcome(
        proposal, outcome="created", reason="candidate_visit_created", visit_id="visit-1",
        decided_at=NOW, known_horizon_ms=3_500,
    )

    window = ledger.query(start_offset_ms=0, end_offset_ms=4_000, roi=ROI)
    result = classify_rejection_attribution(window)
    assert result.attribution == "visit_created"
    outcome_record = next(item for item in window.proposal_outcomes if item.proposal_id == "proposal-admitted")
    assert outcome_record.admitted is True
    assert outcome_record.visit_id == "visit-1"


def test_raw_detection_without_corresponding_generation_is_insufficient_not_a_guess() -> None:
    """A non-animal-class raw hit (or one the tracker's own active-track cap
    excluded) never starts a track at all -- this ledger must never guess a
    causal link that was not actually observed."""
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=(_detection(1_000, label="person", is_animal=False),)))

    window = ledger.query(start_offset_ms=0, end_offset_ms=2_000, roi=ROI)
    result = classify_rejection_attribution(window)
    assert result.attribution == "insufficient_counterfactual_lineage"
    assert result.reason == "raw_detector_activity_present_but_no_corresponding_track_generation_retained"


def test_detector_ran_heartbeat_is_distinct_from_a_real_detection() -> None:
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=()))  # detector ran, found nothing
    ledger.observe_result(_result(2_000, detections=(_detection(2_000),)))

    window = ledger.query(start_offset_ms=0, end_offset_ms=3_000)
    heartbeat = next(item for item in window.raw_detections if item.source_offset_ms == 1_000)
    detection = next(item for item in window.raw_detections if item.source_offset_ms == 2_000)
    assert heartbeat.has_detection is False
    assert detection.has_detection is True


def test_detector_skipped_frame_records_nothing_at_all() -> None:
    """An idle-cadence frame the detector never evaluated (`detector_ran=
    False`) must not be recorded as a "detector ran and found nothing"
    heartbeat -- it is a genuinely different fact (see
    `RawDetectionRecord`'s own docstring)."""
    ledger = CounterfactualLedger(stream_id=STREAM_ID)
    ledger.observe_result(_result(1_000, detections=(), detector_ran=False))
    window = ledger.query(start_offset_ms=0, end_offset_ms=2_000)
    assert window.raw_detections == ()


# --- Gate A Measurement Closure v1: generation-level wall-clock capture ----


def test_track_generation_record_carries_its_own_start_and_end_capture_wall_clock() -> None:
    """`start_captured_at`/`end_captured_at` are read straight off the
    generation's own first/terminal `TrackUpdate.captured_at` -- already a
    required field on every `TrackUpdate`, never a new wall-clock read --
    so a consumer (`fragmentation_accounting.py`, `capture_to_visible_
    latency.py`) finally has a genuine capture-time anchor for a generation,
    not only its source-relative `start_offset_ms`/`end_offset_ms`."""
    start_ms, end_ms = 1_000, 3_000
    ledger = _confirmed_generation_ledger(generation_id="gen-timed", start_ms=start_ms, end_ms=end_ms)

    window = ledger.query(start_offset_ms=0, end_offset_ms=4_000, roi=ROI)
    generation = next(item for item in window.track_generations if item.generation_id == "gen-timed")

    assert generation.start_captured_at == NOW + timedelta(milliseconds=start_ms)
    assert generation.end_captured_at == NOW + timedelta(milliseconds=end_ms)
    # Internally consistent with the offset domain (same live session, same
    # continuous clock) -- exactly the invariant a real Node/Host clock
    # split could violate; see `capture_to_visible_latency.py`'s own
    # clock-domain safety tests for the cross-domain case this does *not*
    # cover.
    assert generation.end_captured_at > generation.start_captured_at
    wall_clock_span_ms = (generation.end_captured_at - generation.start_captured_at).total_seconds() * 1000
    assert wall_clock_span_ms == end_ms - start_ms


def test_track_generation_from_saved_snapshot_without_the_new_field_is_none_not_fabricated() -> None:
    """A ledger snapshot saved before this field existed has no
    `start_captured_at`/`end_captured_at` key at all -- must decode as
    `None`, never crash, never silently invent a value."""
    record = TrackGenerationRecord(
        generation_id="gen-pre-existing", stream_id=STREAM_ID, broad_class="animal", track_ids=("t1",),
        start_offset_ms=0, end_offset_ms=1_000, start_bounding_box=BOX, end_bounding_box=BOX,
        geometry_envelope=BOX, confirmed=True, terminal_reason=None, terminal_support_state=None,
        terminal_bounding_box_source_offset_ms=None, confidence_evidence=EMPTY_CONFIDENCE_EVIDENCE,
    )
    assert record.start_captured_at is None
    assert record.end_captured_at is None
