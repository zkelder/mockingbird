"""Localization Attribution / Detection Geometry Lineage v1 (see
docs/localization-attribution-contract.md).

Direct, deterministic, hardware-free tests for the pure attribution-building
and attribution-classifying functions. Some scenarios deliberately reproduce
the *numeric shape* of real field evidence (the ~9.5s evidence-capture-vs-
last-detection gap independently measured for both visit-observation-
candidate-007 and -008 in
data/field-acceptance/2026-08-11-post-fix-field-validation/FINAL-REPORT.md)
without using any private media, real Visit id, or exact historical value as
a hard-coded assertion target -- see that report and
docs/localization-attribution-contract.md "Retrospective analysis" for the
full disclosed reasoning.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from mockingbird.observation.contracts import (
    ConfidenceEvidenceSummary,
    DetectionEvidenceSample,
    GeometryAttribution,
    TrackUpdate,
)
from mockingbird.observation.localization_attribution import (
    DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
    LocalizationAttributionResult,
    classify_localization_attribution,
    geometry_attribution_for_burst,
    geometry_attribution_for_update,
    geometry_attribution_from_json,
)


def _update(
    *,
    support_state: str,
    source_offset_ms: int,
    bounding_box_source_offset_ms: int | None,
    confidence: float | None = None,
    confidence_samples: tuple[DetectionEvidenceSample, ...] = (),
    frame_id: str | None = "frame-x",
) -> TrackUpdate:
    return TrackUpdate(
        track_id="track-1",
        generation_id="gen-1",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        status="updated",
        lifecycle_state="confirmed",
        frame_id=frame_id,
        source_offset_ms=source_offset_ms,
        broad_class="animal",
        bounding_box=(0.4, 0.4, 0.6, 0.6),
        confidence=confidence,
        support_state=support_state,
        bounding_box_source_offset_ms=bounding_box_source_offset_ms,
        confidence_samples=confidence_samples,
    )


def _summary(*, detection_count: int, last_detection_offset_ms: int | None) -> ConfidenceEvidenceSummary:
    return ConfidenceEvidenceSummary(
        detection_count=detection_count,
        max_confidence=0.5,
        mean_confidence=0.4,
        median_confidence=0.4,
        strong_detection_count=0,
        weak_detection_count=detection_count,
        max_consecutive_detector_confirmed_frames=1,
        samples=(),
        broad_class="animal",
        first_detection_offset_ms=0 if detection_count else None,
        last_detection_offset_ms=last_detection_offset_ms,
        sample_truncated=False,
    )


# --------------------------------------------------------------------------
# geometry_attribution_for_update / geometry_attribution_for_burst
# --------------------------------------------------------------------------


def test_same_frame_detector_hit_reports_zero_gap_and_the_matching_sample() -> None:
    sample = DetectionEvidenceSample(
        confidence=0.66, source_offset_ms=760_843, frame_id="frame-x",
        observation_id="obs-42", is_strong=False, bounding_box=(0.44, 0.59, 0.48, 0.62),
    )
    update = _update(
        support_state="weak_detector_supported", source_offset_ms=760_843,
        bounding_box_source_offset_ms=760_843, confidence=0.66, confidence_samples=(sample,),
    )
    attribution = geometry_attribution_for_update(update, same_frame=True)
    assert attribution.geometry_source == "detector"
    assert attribution.same_frame is True
    assert attribution.geometry_evidence_gap_ms == 0
    assert attribution.geometry_source_offset_ms == 760_843
    assert attribution.geometry_source_observation_id == "obs-42"
    assert attribution.geometry_source_confidence == 0.66


def test_tracker_supported_geometry_has_no_detector_provenance() -> None:
    update = _update(support_state="tracker_supported", source_offset_ms=5_000, bounding_box_source_offset_ms=5_000)
    attribution = geometry_attribution_for_update(update, same_frame=True)
    assert attribution.geometry_source == "tracker"
    assert attribution.geometry_source_observation_id is None
    assert attribution.geometry_source_confidence is None
    assert attribution.geometry_evidence_gap_ms == 0


def test_carried_forward_geometry_reports_the_stale_source_offset() -> None:
    update = _update(support_state="temporarily_lost", source_offset_ms=9_000, bounding_box_source_offset_ms=3_000)
    attribution = geometry_attribution_for_update(update, same_frame=True)
    assert attribution.geometry_source == "carried_forward"
    assert attribution.geometry_source_offset_ms == 3_000  # not this update's own 9_000


def test_derives_gap_from_offsets_when_not_same_frame_and_no_measured_gap_supplied() -> None:
    """The frame-driven provider's own `pretrigger` role shape: the evidence
    image's own offset and the geometry's own source offset are both known,
    but differ, and no independently-measured delta exists (unlike a Camera
    Node burst) -- the gap must be derived, not left `None`."""
    update = _update(support_state="strong_detector_supported", source_offset_ms=400, bounding_box_source_offset_ms=400)
    attribution = geometry_attribution_for_update(update, same_frame=False, evidence_source_offset_ms=200)
    assert attribution.same_frame is False
    assert attribution.geometry_evidence_gap_ms == 200


def test_gap_is_absolute_regardless_of_which_side_is_later() -> None:
    """A `pretrigger` image is *older* than the geometry it is stamped with
    (the opposite direction from a burst, which is *newer*) -- both are
    equally "not the same moment," so the magnitude must be unsigned."""
    update = _update(support_state="strong_detector_supported", source_offset_ms=1_000, bounding_box_source_offset_ms=1_000)
    earlier_image = geometry_attribution_for_update(update, same_frame=False, evidence_source_offset_ms=200)
    later_image = geometry_attribution_for_update(update, same_frame=False, evidence_source_offset_ms=1_800)
    assert earlier_image.geometry_evidence_gap_ms == 800
    assert later_image.geometry_evidence_gap_ms == 800


def test_gap_is_none_when_neither_measured_nor_derivable() -> None:
    update = _update(support_state="strong_detector_supported", source_offset_ms=1_000, bounding_box_source_offset_ms=None)
    attribution = geometry_attribution_for_update(update, same_frame=False, evidence_source_offset_ms=None)
    assert attribution.same_frame is False
    assert attribution.geometry_evidence_gap_ms is None


def test_burst_attribution_uses_the_transport_measured_gap_verbatim() -> None:
    """`geometry_attribution_for_burst` never reconstructs the gap from
    offsets -- it reuses the transport's own already-measured, real
    `request_to_capture_ms` exactly, and is always structurally
    `same_frame=False` (a burst is a genuinely separate capture event by
    construction, regardless of how small the measured gap turns out)."""
    update = _update(support_state="weak_detector_supported", source_offset_ms=1_290_768, bounding_box_source_offset_ms=1_290_768)
    attribution = geometry_attribution_for_burst(update, request_to_capture_ms=9_551)
    assert attribution.same_frame is False
    assert attribution.geometry_evidence_gap_ms == 9_551
    assert attribution.geometry_source == "detector"


def test_burst_attribution_with_unknown_capture_latency_is_still_honestly_unaligned() -> None:
    update = _update(support_state="strong_detector_supported", source_offset_ms=1_000, bounding_box_source_offset_ms=1_000)
    attribution = geometry_attribution_for_burst(update, request_to_capture_ms=None)
    assert attribution.same_frame is False
    assert attribution.geometry_evidence_gap_ms is None


# --------------------------------------------------------------------------
# geometry_attribution_from_json
# --------------------------------------------------------------------------


def test_geometry_attribution_json_round_trips() -> None:
    original = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=1000, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.5, same_frame=False, geometry_evidence_gap_ms=250,
    )
    payload = json.dumps(asdict(original))
    reconstructed = geometry_attribution_from_json(payload)
    assert reconstructed == original


@pytest.mark.parametrize("payload", [None, "", "not json", "[]", "42", '{"geometry_evidence_gap_ms": -1}'])
def test_geometry_attribution_json_never_fabricates_on_bad_input(payload: str | None) -> None:
    assert geometry_attribution_from_json(payload) is None


# --------------------------------------------------------------------------
# classify_localization_attribution
# --------------------------------------------------------------------------


def test_missing_lineage_is_insufficient_never_guessed() -> None:
    result = classify_localization_attribution(None)
    assert result.attribution == "insufficient_geometry_lineage"
    assert result.geometry_source is None


def test_empty_attribution_with_no_facts_is_insufficient() -> None:
    empty = GeometryAttribution(
        geometry_source=None, geometry_source_offset_ms=None, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=None, geometry_evidence_gap_ms=None,
    )
    result = classify_localization_attribution(empty)
    assert result.attribution == "insufficient_geometry_lineage"


def test_aligned_genuine_detector_hit_is_detector_off_target() -> None:
    attribution = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=760_843, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.66, same_frame=True, geometry_evidence_gap_ms=0,
    )
    result = classify_localization_attribution(attribution)
    assert result.attribution == "detector_off_target"
    assert result.geometry_evidence_gap_ms == 0


def test_aligned_tracker_supported_geometry_is_tracker_drift() -> None:
    attribution = GeometryAttribution(
        geometry_source="tracker", geometry_source_offset_ms=5_000, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=True, geometry_evidence_gap_ms=0,
    )
    result = classify_localization_attribution(attribution)
    assert result.attribution == "tracker_drift"


def test_carried_forward_with_confirmed_detection_history_is_hit_then_lost() -> None:
    attribution = GeometryAttribution(
        geometry_source="carried_forward", geometry_source_offset_ms=9_000, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=True, geometry_evidence_gap_ms=0,
    )
    confidence_evidence = _summary(detection_count=3, last_detection_offset_ms=5_000)
    result = classify_localization_attribution(attribution, confidence_evidence=confidence_evidence)
    assert result.attribution == "detector_hit_then_lost"


def test_carried_forward_without_confirmed_history_is_insufficient_not_guessed() -> None:
    attribution = GeometryAttribution(
        geometry_source="carried_forward", geometry_source_offset_ms=9_000, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=True, geometry_evidence_gap_ms=0,
    )
    assert classify_localization_attribution(attribution).attribution == "insufficient_geometry_lineage"
    zero_detections = _summary(detection_count=0, last_detection_offset_ms=None)
    assert classify_localization_attribution(
        attribution, confidence_evidence=zero_detections
    ).attribution == "insufficient_geometry_lineage"


def test_carried_forward_before_its_own_last_detection_offset_is_not_hit_then_lost() -> None:
    """Defensive: a stale box whose own source offset is *before* the last
    known detection (should not happen by tracker construction, but the
    classifier must not claim `detector_hit_then_lost` from a fact pattern
    that does not actually support it)."""
    attribution = GeometryAttribution(
        geometry_source="carried_forward", geometry_source_offset_ms=1_000, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=True, geometry_evidence_gap_ms=0,
    )
    confidence_evidence = _summary(detection_count=3, last_detection_offset_ms=5_000)
    result = classify_localization_attribution(attribution, confidence_evidence=confidence_evidence)
    assert result.attribution == "insufficient_geometry_lineage"


@pytest.mark.parametrize("gap_ms", [None, DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS + 1, 9_551])
def test_not_same_frame_beyond_threshold_or_unknown_is_misaligned(gap_ms: int | None) -> None:
    attribution = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=760_843, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.66, same_frame=False, geometry_evidence_gap_ms=gap_ms,
    )
    result = classify_localization_attribution(attribution)
    assert result.attribution == "evidence_geometry_misaligned"


def test_misalignment_threshold_is_inclusive_not_exclusive() -> None:
    """Exactly at the bound is still trusted; only strictly past it counts
    as misaligned -- a deliberate, documented boundary, not an accident of
    `>` vs `>=`."""
    at_bound = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=0, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.5, same_frame=False, geometry_evidence_gap_ms=DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
    )
    result = classify_localization_attribution(at_bound)
    assert result.attribution == "detector_off_target"
    assert result.geometry_evidence_gap_ms == DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS


def test_small_gap_below_threshold_falls_through_to_geometry_source() -> None:
    small_gap = GeometryAttribution(
        geometry_source="tracker", geometry_source_offset_ms=0, geometry_source_observation_id=None,
        geometry_source_confidence=None, same_frame=False, geometry_evidence_gap_ms=50,
    )
    result = classify_localization_attribution(small_gap)
    assert result.attribution == "tracker_drift"


def test_custom_misalignment_threshold_is_honored() -> None:
    attribution = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=0, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.5, same_frame=False, geometry_evidence_gap_ms=100,
    )
    assert classify_localization_attribution(attribution, misalignment_gap_threshold_ms=50).attribution == "evidence_geometry_misaligned"
    assert classify_localization_attribution(attribution, misalignment_gap_threshold_ms=200).attribution == "detector_off_target"


def test_negative_threshold_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid_misalignment_gap_threshold"):
        classify_localization_attribution(None, misalignment_gap_threshold_ms=-1)


def test_classification_is_deterministic() -> None:
    attribution = GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=760_843, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.66, same_frame=True, geometry_evidence_gap_ms=0,
    )
    first = classify_localization_attribution(attribution)
    second = classify_localization_attribution(attribution)
    assert first == second


def test_result_rejects_negative_gap() -> None:
    with pytest.raises(ValueError, match="invalid_localization_attribution_result"):
        LocalizationAttributionResult("tracker_drift", "reason", "tracker", -1)


# --------------------------------------------------------------------------
# Real-field-shaped scenarios (numeric shape only -- never a hard-coded
# private value; see module docstring and
# docs/localization-attribution-contract.md "Retrospective analysis")
# --------------------------------------------------------------------------


def test_burst_delay_shape_matching_the_2026_08_11_field_session_is_misaligned() -> None:
    """Reproduces the *shape* independently measured for both candidate-007
    and candidate-008 in the 2026-08-11 post-fix field session (evidence
    image captured roughly 9.5s after the tracklet's own last supporting
    detection sample -- see FINAL-REPORT.md section 9): with this
    contract's lineage in place, that gap alone is sufficient to flag the
    persisted geometry as unaligned with its own evidence image, regardless
    of how confident the originating detection was."""
    update = _update(
        support_state="weak_detector_supported", source_offset_ms=769_641, bounding_box_source_offset_ms=769_641,
        confidence=0.66,
    )
    attribution = geometry_attribution_for_burst(update, request_to_capture_ms=9_574)
    result = classify_localization_attribution(attribution)
    assert result.attribution == "evidence_geometry_misaligned"


def test_early_strong_hit_then_long_quiet_coast_before_capture_is_hit_then_lost() -> None:
    """A distinct, complementary shape from the misalignment case above: the
    evidence image itself *is* captured close to the geometry's own source
    moment (no burst-timing artifact), but that source moment is itself a
    stale, carried-forward box from well after the tracklet's own last
    genuine detector confirmation -- the detector demonstrably found the
    subject earlier in the encounter, then lost it before evidence was
    ever attached."""
    update = _update(support_state="temporarily_lost", source_offset_ms=30_000, bounding_box_source_offset_ms=28_000)
    confidence_evidence = _summary(detection_count=5, last_detection_offset_ms=20_000)
    attribution = geometry_attribution_for_burst(update, request_to_capture_ms=150)
    result = classify_localization_attribution(attribution, confidence_evidence=confidence_evidence)
    assert result.attribution == "detector_hit_then_lost"


# --------------------------------------------------------------------------
# Structural purity
# --------------------------------------------------------------------------


def test_localization_attribution_module_has_no_product_repository_import() -> None:
    """Structural guard, the same convention every Stage 6.x/7 decision
    module in this package follows (`visit_episode_assembler`,
    `candidate_visit_authority`, `candidate_quality_gate`, `admission_
    policy`): this module must stay pure -- no filesystem beyond its own
    source read here, network, product-repository, or SQLAlchemy import."""
    source = Path("src/mockingbird/observation/localization_attribution.py").read_text(encoding="utf-8")
    forbidden = (
        "mockingbird.repository", "mockingbird.storage", "mockingbird.api", "sqlalchemy",
        "import socket", "import requests", "from PIL", "import PIL", "onnxruntime", "numpy",
    )
    for token in forbidden:
        assert token not in source, f"unexpected impure dependency: {token}"
