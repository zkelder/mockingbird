"""Source-Resolution + Multi-Frame Species Evidence v1: governed benchmark
comparing the current analysis-resolution/single-frame species-evidence
path (A) against a genuinely higher native/source-resolution single-best
frame (B) and a native multi-frame candidate policy (C).

This module is pure: no filesystem I/O, no network, no CUDA/ONNX Runtime/
OpenCV, no product-repository or product-database import (see
`source_resolution_species_benchmark_io.py` for loading a real cohort from
an existing product database, mirroring the established `evidence_
benchmark.py` / `evidence_benchmark_io.py` split).

Honesty boundary (see "Resolution-aware benchmark integrity" in
docs/source-resolution-multi-frame-species-evidence-contract.md): this
benchmark never compares an analysis crop against an upscaled copy of that
same crop and calls it native-resolution evidence. Where genuine paired
native/analysis-resolution imagery is unavailable, a caller must construct
the "analysis-resolution equivalent" arm by *downscaling* real native pixels
to a real, deployed analysis-stream resolution *before* cropping the same
real, already-measured subject box -- simulating what a genuinely lower-
resolution capture of the identical real scene would have recorded (less
information than the real native capture, never invented detail). This
module itself only ever operates on already-computed pixel-dimension facts;
it never encodes/decodes/resizes an image.

If a live species classifier is unavailable in the environment this
benchmark runs in, it does not fabricate accuracy/precision numbers: it
honestly measures the model-independent facts this milestone's product
requirement actually turns on -- genuine subject pixel dimensions, whether
each arm clears the existing resolution-eligibility floor
(`identification_eligibility.MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX`), and
real multi-frame candidate availability -- and reports `live_model_
inference_available=False` plus an explicit `limitations` entry rather than
silently omitting the question.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from statistics import median
from typing import Literal

from mockingbird.species.identification_eligibility import (
    MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX,
    evaluate_identification_eligibility,
)

SOURCE_RESOLUTION_BENCHMARK_REPORT_SCHEMA_VERSION = 1
SOURCE_RESOLUTION_BENCHMARK_VERSION = "source-resolution-species-benchmark-v1"

# The real, deployed analysis-stream ceiling (`scripts/install_camera_node.py`
# / `scripts/build_camera_node_artifact.py`, and `mockingbird_node.config.
# CameraNodeConfig` defaults) -- never a guessed number. See "Actual
# analysis resolution" in the milestone final report for the exact citation.
DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX = 1920
DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX = 1080


@dataclass(frozen=True)
class ResolutionEvidencePair:
    """One real, already-persisted native-resolution subject crop and the
    real geometry facts needed to honestly simulate its analysis-resolution
    equivalent -- the minimal input this module needs. Built by the IO layer
    from real Visit/MediaAsset rows; never fabricated here.

    `subject_box_normalized` and `native_source_width`/`height` are real,
    already-measured facts (the crop's own recorded subject box, and its
    real native parent image's real dimensions). `native_crop_width`/
    `height` are the crop's own real, already-persisted pixel dimensions --
    never recomputed here, so a caller's real crop and this module's
    simulated analysis-equivalent size are always compared on the same
    normalized-box basis.
    """

    visit_id: str
    media_asset_id: str
    reviewed_label: str | None
    subject_box_normalized: tuple[float, float, float, float]
    native_source_width: int
    native_source_height: int
    native_crop_width: int
    native_crop_height: int
    # How many *other* genuinely distinct native-resolution candidate crops
    # this same Visit has (0 for a single-encounter Visit) -- the real
    # multi-frame candidate availability fact, never an invented count.
    sibling_native_candidate_count: int

    def __post_init__(self) -> None:
        left, top, right, bottom = self.subject_box_normalized
        if not (0.0 <= left < right <= 1.0 and 0.0 <= top < bottom <= 1.0):
            raise ValueError("invalid_resolution_evidence_pair_box")
        if self.native_source_width < 1 or self.native_source_height < 1:
            raise ValueError("invalid_resolution_evidence_pair_dimensions")
        if self.native_crop_width < 1 or self.native_crop_height < 1:
            raise ValueError("invalid_resolution_evidence_pair_dimensions")
        if self.sibling_native_candidate_count < 0:
            raise ValueError("invalid_resolution_evidence_pair_sibling_count")


def simulate_analysis_resolution_crop_dimensions(
    subject_box_normalized: tuple[float, float, float, float],
    *,
    analysis_width_px: int = DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX,
    analysis_height_px: int = DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX,
) -> tuple[int, int]:
    """The honest, pure geometry this benchmark uses for its "A" arm: what
    pixel dimensions would this *exact same real subject box* have if it
    had been captured (and cropped, with no padding, matching how the
    real native crop's own bounds were derived) directly at a genuinely
    lower analysis-stream resolution -- never derived by resizing/
    upscaling an existing image. A normalized box is resolution-independent
    by construction (`x_norm = x_pixel / width`), so this is exact
    arithmetic, not an approximation."""

    if analysis_width_px < 1 or analysis_height_px < 1:
        raise ValueError("invalid_analysis_resolution")
    left, top, right, bottom = subject_box_normalized
    width_px = max(1, round((right - left) * analysis_width_px))
    height_px = max(1, round((bottom - top) * analysis_height_px))
    return width_px, height_px


@dataclass(frozen=True)
class ResolutionArmMeasurement:
    """One arm's (A/B) measured, honest facts for one real pair -- pixel
    dimensions plus whether that size clears the existing, already-accepted
    resolution-eligibility floor. Never a species prediction."""

    width_px: int
    height_px: int
    area_px: int
    eligible: bool

    @staticmethod
    def from_dimensions(width_px: int, height_px: int) -> "ResolutionArmMeasurement":
        decision = evaluate_identification_eligibility(
            classifier_input_width=width_px, classifier_input_height=height_px,
        )
        return ResolutionArmMeasurement(
            width_px=width_px, height_px=height_px,
            area_px=width_px * height_px, eligible=decision.eligible,
        )


@dataclass(frozen=True)
class SourceResolutionBenchmarkReport:
    schema_version: int
    benchmark_version: str
    cohort_size: int
    real_data_source: str
    analysis_resolution_width_px: int
    analysis_resolution_height_px: int
    live_model_inference_available: bool
    # Arm A: analysis-resolution equivalent (real box, simulated resolution)
    analysis_equivalent_median_width_px: float | None
    analysis_equivalent_median_height_px: float | None
    analysis_equivalent_eligible_count: int
    analysis_equivalent_ineligible_count: int
    # Arm B: real, already-persisted native-resolution single-best crop
    native_median_width_px: float | None
    native_median_height_px: float | None
    native_eligible_count: int
    native_ineligible_count: int
    # Comparative signal
    median_native_to_analysis_pixel_area_ratio: float | None
    newly_eligible_count: int
    newly_eligible_visit_ids: tuple[str, ...]
    # Arm C: real multi-frame candidate availability (governs whether a
    # multi-frame *policy* is even reachable for this cohort, independent
    # of whether it was scored by a live model)
    visits_with_multiple_native_candidates: int
    visits_with_single_native_candidate: int
    max_native_candidates_observed_for_one_visit: int
    # False-positive-specific: does more real detail exist even for
    # evidence a human reviewer confirmed is not a species-identifiable
    # subject -- a real, ground-truthed check on whether "more resolution"
    # risks manufacturing false confidence, not just correct confidence.
    false_positive_pair_count: int
    false_positive_native_eligible_count: int
    limitations: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def build_source_resolution_benchmark_report(
    pairs: tuple[ResolutionEvidencePair, ...],
    *,
    real_data_source: str,
    live_model_inference_available: bool = False,
    analysis_width_px: int = DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX,
    analysis_height_px: int = DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX,
    extra_limitations: tuple[str, ...] = (),
) -> SourceResolutionBenchmarkReport:
    """Build the deterministic comparison report from an already-loaded real
    cohort. Empty `pairs` is honestly reported (all counts zero, every
    median `None`), never an error -- "no real paired evidence available"
    is itself a valid, reportable outcome (see "Resolution-aware benchmark
    integrity")."""

    limitations: list[str] = list(extra_limitations)
    if not live_model_inference_available:
        limitations.append(
            "live_species_classifier_unavailable: species top-1 correctness, "
            "named-suggestion precision, cross-arm disagreement rate, and "
            "false-confident-suggestion rate could not be measured in this "
            "environment; only model-independent geometry/eligibility facts "
            "are reported."
        )
    if not pairs:
        limitations.append("empty_cohort: no real paired native-resolution evidence was available.")

    analysis_widths: list[float] = []
    analysis_heights: list[float] = []
    native_widths: list[float] = []
    native_heights: list[float] = []
    area_ratios: list[float] = []
    analysis_eligible = analysis_ineligible = 0
    native_eligible = native_ineligible = 0
    newly_eligible_ids: list[str] = []
    multi_candidate_visits: set[str] = set()
    single_candidate_visits: set[str] = set()
    max_siblings = 0
    false_positive_pairs = 0
    false_positive_native_eligible = 0

    for pair in pairs:
        analysis_width, analysis_height = simulate_analysis_resolution_crop_dimensions(
            pair.subject_box_normalized,
            analysis_width_px=analysis_width_px, analysis_height_px=analysis_height_px,
        )
        arm_a = ResolutionArmMeasurement.from_dimensions(analysis_width, analysis_height)
        arm_b = ResolutionArmMeasurement.from_dimensions(pair.native_crop_width, pair.native_crop_height)

        analysis_widths.append(arm_a.width_px)
        analysis_heights.append(arm_a.height_px)
        native_widths.append(arm_b.width_px)
        native_heights.append(arm_b.height_px)
        if arm_a.area_px > 0:
            area_ratios.append(arm_b.area_px / arm_a.area_px)

        analysis_eligible += int(arm_a.eligible)
        analysis_ineligible += int(not arm_a.eligible)
        native_eligible += int(arm_b.eligible)
        native_ineligible += int(not arm_b.eligible)
        if arm_b.eligible and not arm_a.eligible:
            newly_eligible_ids.append(pair.visit_id)

        if pair.sibling_native_candidate_count > 0:
            multi_candidate_visits.add(pair.visit_id)
        else:
            single_candidate_visits.add(pair.visit_id)
        max_siblings = max(max_siblings, pair.sibling_native_candidate_count + 1)

        if pair.reviewed_label == "false_positive":
            false_positive_pairs += 1
            false_positive_native_eligible += int(arm_b.eligible)

    # A Visit contributing more than one pair is, by construction, in
    # `multi_candidate_visits` for every one of its own pairs -- de-duplicate
    # against `single_candidate_visits` so a Visit is never double-counted
    # across both buckets.
    single_candidate_visits -= multi_candidate_visits

    return SourceResolutionBenchmarkReport(
        schema_version=SOURCE_RESOLUTION_BENCHMARK_REPORT_SCHEMA_VERSION,
        benchmark_version=SOURCE_RESOLUTION_BENCHMARK_VERSION,
        cohort_size=len(pairs),
        real_data_source=real_data_source,
        analysis_resolution_width_px=analysis_width_px,
        analysis_resolution_height_px=analysis_height_px,
        live_model_inference_available=live_model_inference_available,
        analysis_equivalent_median_width_px=_median(analysis_widths),
        analysis_equivalent_median_height_px=_median(analysis_heights),
        analysis_equivalent_eligible_count=analysis_eligible,
        analysis_equivalent_ineligible_count=analysis_ineligible,
        native_median_width_px=_median(native_widths),
        native_median_height_px=_median(native_heights),
        native_eligible_count=native_eligible,
        native_ineligible_count=native_ineligible,
        median_native_to_analysis_pixel_area_ratio=_median(area_ratios),
        newly_eligible_count=len(newly_eligible_ids),
        newly_eligible_visit_ids=tuple(sorted(set(newly_eligible_ids))),
        visits_with_multiple_native_candidates=len(multi_candidate_visits),
        visits_with_single_native_candidate=len(single_candidate_visits),
        max_native_candidates_observed_for_one_visit=max_siblings,
        false_positive_pair_count=false_positive_pairs,
        false_positive_native_eligible_count=false_positive_native_eligible,
        limitations=tuple(limitations),
    )


CohortQuestion = Literal[
    "does_native_resolution_add_real_pixel_detail",
    "does_native_resolution_change_eligibility",
    "is_multi_frame_evidence_genuinely_available",
]


def summarize_for_decision(report: SourceResolutionBenchmarkReport) -> dict[str, str]:
    """A small, honest, deterministic plain-language summary of what this
    report's own numbers actually support -- never a species-accuracy claim
    this report cannot back. Used by the CLI/final report, not by product
    code."""

    summary: dict[str, str] = {}
    if report.cohort_size == 0:
        summary["does_native_resolution_add_real_pixel_detail"] = "no_data"
        summary["does_native_resolution_change_eligibility"] = "no_data"
        summary["is_multi_frame_evidence_genuinely_available"] = "no_data"
        return summary

    if report.median_native_to_analysis_pixel_area_ratio is not None:
        ratio = report.median_native_to_analysis_pixel_area_ratio
        summary["does_native_resolution_add_real_pixel_detail"] = (
            f"yes: median native/analysis-equivalent subject pixel area ratio is {ratio:.1f}x "
            f"across {report.cohort_size} real paired crops"
        )
    else:
        summary["does_native_resolution_add_real_pixel_detail"] = "insufficient_data"

    if report.newly_eligible_count > 0:
        summary["does_native_resolution_change_eligibility"] = (
            f"yes: {report.newly_eligible_count}/{report.cohort_size} real subjects cross the "
            f"{MINIMUM_CLASSIFIER_INPUT_DIMENSION_PX}px eligibility floor only at native resolution "
            "(too small to attempt at the analysis-resolution equivalent)"
        )
    elif report.analysis_equivalent_ineligible_count == 0:
        summary["does_native_resolution_change_eligibility"] = (
            "no_measurable_difference: every real subject in this cohort already clears the "
            "eligibility floor at the analysis-resolution equivalent"
        )
    else:
        summary["does_native_resolution_change_eligibility"] = "no_measurable_difference"

    total_visits = report.visits_with_multiple_native_candidates + report.visits_with_single_native_candidate
    if report.visits_with_multiple_native_candidates > 0:
        summary["is_multi_frame_evidence_genuinely_available"] = (
            f"yes: {report.visits_with_multiple_native_candidates}/{total_visits} real Visits in "
            f"this cohort have more than one genuinely distinct native-resolution candidate frame "
            f"(up to {report.max_native_candidates_observed_for_one_visit} observed)"
        )
    else:
        summary["is_multi_frame_evidence_genuinely_available"] = (
            f"rarely_or_never: 0/{total_visits} real Visits in this cohort had more than one "
            "distinct native-resolution candidate frame"
        )
    return summary


__all__ = [
    "DEFAULT_ANALYSIS_RESOLUTION_HEIGHT_PX",
    "DEFAULT_ANALYSIS_RESOLUTION_WIDTH_PX",
    "ResolutionArmMeasurement",
    "ResolutionEvidencePair",
    "SOURCE_RESOLUTION_BENCHMARK_REPORT_SCHEMA_VERSION",
    "SOURCE_RESOLUTION_BENCHMARK_VERSION",
    "SourceResolutionBenchmarkReport",
    "build_source_resolution_benchmark_report",
    "simulate_analysis_resolution_crop_dimensions",
    "summarize_for_decision",
]
