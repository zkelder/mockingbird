"""Source-Resolution + Multi-Frame Species Evidence v1 governed benchmark --
direct, deterministic, hardware-free tests for the pure comparison/report
module. No DB/filesystem/model access (see
tests/test_source_resolution_species_benchmark_io.py for the real-cohort
loader, which does touch a real sqlite fixture).
"""

from __future__ import annotations

import pytest

from mockingbird.observation.source_resolution_species_benchmark import (
    DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX,
    DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX,
    ResolutionArmMeasurement,
    ResolutionEvidencePair,
    build_source_resolution_benchmark_report,
    simulate_analysis_resolution_crop_dimensions,
    summarize_for_decision,
)
from mockingbird.species.identification_eligibility import MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX


def _pair(
    *,
    visit_id: str = "visit-1",
    media_asset_id: str = "media-1",
    reviewed_label: str | None = "house_finch",
    box: tuple[float, float, float, float] = (0.44, 0.42, 0.48, 0.44),
    native_width: int = 4624,
    native_height: int = 3472,
    crop_width: int = 279,
    crop_height: int = 99,
    siblings: int = 0,
) -> ResolutionEvidencePair:
    return ResolutionEvidencePair(
        visit_id=visit_id, media_asset_id=media_asset_id, reviewed_label=reviewed_label,
        subject_box_normalized=box, native_source_width=native_width, native_source_height=native_height,
        native_crop_width=crop_width, native_crop_height=crop_height, sibling_native_candidate_count=siblings,
    )


# ---------------------------------------------------------------------------
# simulate_analysis_resolution_crop_dimensions
# ---------------------------------------------------------------------------


def test_simulated_dimensions_are_exact_normalized_box_arithmetic() -> None:
    width, height = simulate_analysis_resolution_crop_dimensions(
        (0.25, 0.25, 0.75, 0.75), analysis_width_px=1920, analysis_height_px=1080,
    )
    assert width == round(0.5 * 1920)
    assert height == round(0.5 * 1080)


def test_simulated_dimensions_use_the_real_deployed_analysis_resolution_by_default() -> None:
    assert DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX == 1920
    assert DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX == 1080


def test_simulated_dimensions_never_zero_even_for_a_tiny_box() -> None:
    width, height = simulate_analysis_resolution_crop_dimensions((0.0, 0.0, 0.0001, 0.0001))
    assert width >= 1 and height >= 1


def test_simulated_dimensions_rejects_invalid_resolution() -> None:
    with pytest.raises(ValueError):
        simulate_analysis_resolution_crop_dimensions((0.1, 0.1, 0.2, 0.2), analysis_width_px=0)


# ---------------------------------------------------------------------------
# ResolutionEvidencePair validation
# ---------------------------------------------------------------------------


def test_pair_rejects_degenerate_box() -> None:
    with pytest.raises(ValueError):
        _pair(box=(0.5, 0.5, 0.5, 0.5))


def test_pair_rejects_out_of_range_box() -> None:
    with pytest.raises(ValueError):
        _pair(box=(-0.1, 0.1, 0.5, 0.5))


def test_pair_rejects_non_positive_dimensions() -> None:
    with pytest.raises(ValueError):
        _pair(native_width=0)
    with pytest.raises(ValueError):
        _pair(crop_height=0)


def test_pair_rejects_negative_sibling_count() -> None:
    with pytest.raises(ValueError):
        _pair(siblings=-1)


# ---------------------------------------------------------------------------
# ResolutionArmMeasurement
# ---------------------------------------------------------------------------


def test_arm_measurement_computes_area_and_eligibility() -> None:
    measurement = ResolutionArmMeasurement.from_dimensions(200, 150)
    assert measurement.area_px == 30_000
    assert measurement.eligible is True


def test_arm_measurement_below_floor_is_ineligible() -> None:
    measurement = ResolutionArmMeasurement.from_dimensions(
        MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX - 1, 200,
    )
    assert measurement.eligible is False


# ---------------------------------------------------------------------------
# build_source_resolution_benchmark_report
# ---------------------------------------------------------------------------


def test_empty_cohort_is_honestly_reported_never_an_error() -> None:
    report = build_source_resolution_benchmark_report((), real_data_source="test")
    assert report.cohort_size == 0
    assert report.analysis_equivalent_median_width_px is None
    assert report.native_median_width_px is None
    assert report.median_native_to_analysis_pixel_area_ratio is None
    assert "empty_cohort: no real paired native-resolution evidence was available." in report.limitations


def test_no_live_model_limitation_is_always_disclosed_by_default() -> None:
    report = build_source_resolution_benchmark_report((_pair(),), real_data_source="test")
    assert report.live_model_inference_available is False
    assert any("live_species_classifier_unavailable" in item for item in report.limitations)


def test_live_model_available_suppresses_that_specific_limitation() -> None:
    report = build_source_resolution_benchmark_report(
        (_pair(),), real_data_source="test", live_model_inference_available=True,
    )
    assert report.live_model_inference_available is True
    assert not any("live_species_classifier_unavailable" in item for item in report.limitations)


def test_real_small_far_bird_shape_crosses_eligibility_only_at_native_resolution() -> None:
    """Reproduces the exact numeric shape of a real row in this product's
    own database (visit-motion-024/media-asset-034): a small/far bird whose
    real native-resolution crop is well above the eligibility floor, but
    whose real subject box would fall below it at the real deployed
    analysis-stream resolution."""

    pair = _pair(box=(0.44475, 0.4222, 0.48015, 0.43885), crop_width=279, crop_height=99)
    report = build_source_resolution_benchmark_report((pair,), real_data_source="test")
    assert report.native_eligible_count == 1
    assert report.analysis_equivalent_ineligible_count == 1
    assert report.newly_eligible_count == 1
    assert report.newly_eligible_visit_ids == ("visit-1",)
    assert report.median_native_to_analysis_pixel_area_ratio > 1.0


def test_subject_already_eligible_at_analysis_resolution_is_not_newly_eligible() -> None:
    """A large, close subject gains detail at native resolution but does
    not need it to clear the eligibility floor -- never miscounted as
    'newly eligible.'"""

    pair = _pair(box=(0.1, 0.1, 0.9, 0.9), native_width=4624, native_height=3472, crop_width=3000, crop_height=2000)
    report = build_source_resolution_benchmark_report((pair,), real_data_source="test")
    assert report.analysis_equivalent_eligible_count == 1
    assert report.newly_eligible_count == 0


def test_sibling_candidates_populate_multi_frame_availability_buckets() -> None:
    pairs = (
        _pair(visit_id="visit-multi", media_asset_id="m1", siblings=1),
        _pair(visit_id="visit-multi", media_asset_id="m2", siblings=1),
        _pair(visit_id="visit-single", media_asset_id="m3", siblings=0),
    )
    report = build_source_resolution_benchmark_report(pairs, real_data_source="test")
    assert report.visits_with_multiple_native_candidates == 1
    assert report.visits_with_single_native_candidate == 1
    assert report.max_native_candidates_observed_for_one_visit == 2


def test_false_positive_pairs_are_tracked_separately() -> None:
    pairs = (
        _pair(visit_id="v1", reviewed_label="false_positive"),
        _pair(visit_id="v2", reviewed_label="house_finch"),
        _pair(visit_id="v3", reviewed_label=None),
    )
    report = build_source_resolution_benchmark_report(pairs, real_data_source="test")
    assert report.false_positive_pair_count == 1
    assert report.false_positive_native_eligible_count == 1


def test_report_is_deterministic_regardless_of_input_ordering() -> None:
    pairs_a = (
        _pair(visit_id="v1", media_asset_id="m1", box=(0.1, 0.1, 0.2, 0.2)),
        _pair(visit_id="v2", media_asset_id="m2", box=(0.3, 0.3, 0.6, 0.6)),
    )
    pairs_b = tuple(reversed(pairs_a))
    report_a = build_source_resolution_benchmark_report(pairs_a, real_data_source="test")
    report_b = build_source_resolution_benchmark_report(pairs_b, real_data_source="test")
    assert report_a.as_dict() == report_b.as_dict()


def test_report_round_trips_through_as_dict() -> None:
    report = build_source_resolution_benchmark_report((_pair(),), real_data_source="test")
    payload = report.as_dict()
    assert payload["cohort_size"] == 1
    assert payload["schema_version"] == report.schema_version


# ---------------------------------------------------------------------------
# summarize_for_decision
# ---------------------------------------------------------------------------


def test_summary_reports_no_data_for_empty_cohort() -> None:
    report = build_source_resolution_benchmark_report((), real_data_source="test")
    summary = summarize_for_decision(report)
    assert summary["does_native_resolution_add_real_pixel_detail"] == "no_data"
    assert summary["is_multi_frame_evidence_genuinely_available"] == "no_data"


def test_summary_reports_rarely_or_never_when_no_visit_has_multiple_candidates() -> None:
    report = build_source_resolution_benchmark_report((_pair(),), real_data_source="test")
    summary = summarize_for_decision(report)
    assert summary["is_multi_frame_evidence_genuinely_available"].startswith("rarely_or_never")


def test_summary_reports_yes_when_multiple_candidates_exist() -> None:
    pairs = (
        _pair(visit_id="v1", media_asset_id="m1", siblings=2),
        _pair(visit_id="v1", media_asset_id="m2", siblings=2),
        _pair(visit_id="v1", media_asset_id="m3", siblings=2),
    )
    report = build_source_resolution_benchmark_report(pairs, real_data_source="test")
    summary = summarize_for_decision(report)
    assert summary["is_multi_frame_evidence_genuinely_available"].startswith("yes")
