"""Pure field evaluation for already-stored BioCLIP suggestion evidence.

This module does not open product storage, load media, or invoke a model.  It
compares exact-target SpeciesSuggestion evidence with final ReviewLabel truth
supplied by a read-only boundary.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import hashlib
import json
import math
from statistics import median
from typing import Any, Mapping

from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_SCORE_KIND,
)

REPORT_SCHEMA_VERSION = 2
CROP_BREAKDOWN_KEYS = (
    "credible_megadetector_crop",
    "measured_activity_crop",
    "full_frame_fallback",
    "unknown_missing",
)
_NON_BIRD_CATEGORIES = {"mammal", "pet", "person", "vehicle", "object"}
_CANDIDATE_NON_BIRD_CATEGORIES = _NON_BIRD_CATEGORIES | {"false_positive"}
BIOCLIP_ATTEMPT_OUTCOMES = (
    "succeeded",
    "no_result",
    "timed_out",
    "failed",
    "unsupported",
    "cancelled",
)


@dataclass(frozen=True)
class StoredReviewLabel:
    """One persisted ReviewLabel correction."""

    id: str
    target_type: str
    target_id: str
    label: str
    created_at: datetime


@dataclass(frozen=True)
class StoredSpeciesSuggestion:
    """The stored fields needed to evaluate one SpeciesSuggestion."""

    id: str
    event_id: str | None
    visit_id: str | None
    adapter_id: str
    suggested_label: str
    suggested_scientific_name: str | None
    confidence: float | None
    rank: int
    alternatives: tuple[Mapping[str, Any], ...] | None
    evidence_region: Mapping[str, Any] | None
    status: str
    created_at: datetime


@dataclass(frozen=True)
class StoredBioClipAttempt:
    """The safe stored fields needed to evaluate one manual BioCLIP attempt."""

    id: str
    target_type: str
    target_id: str
    adapter_id: str
    resulting_species_suggestion_id: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    timeout_limit_ms: int
    timeout_exceeded: bool
    outcome: str | None
    crop_source: str | None
    candidate_manifest: tuple[Mapping[str, Any], ...] | None
    candidate_set_count: int | None
    candidate_set_sha256: str | None
    candidate_set_version: str | None
    candidate_manifest_complete: bool
    model_provenance: Mapping[str, Any] | None
    preprocessing: Mapping[str, Any] | None
    error_code: str | None
    error_stage: str | None


@dataclass(frozen=True)
class TaxonomyDescriptor:
    """Review taxonomy facts used without guessing label meaning."""

    label: str
    category: str
    is_species: bool


@dataclass(frozen=True)
class EvaluationConfig:
    """Field-evaluation guardrails."""

    minimum_examples: int = 30
    mistake_limit: int = 20

    def __post_init__(self) -> None:
        if self.minimum_examples < 1:
            raise ValueError("minimum_examples must be at least 1")
        if self.mistake_limit < 1:
            raise ValueError("mistake_limit must be at least 1")


@dataclass(frozen=True)
class BioClipFieldTruthReport:
    """Serializable field report with explicit metric availability."""

    schema_version: int
    generated_at: str
    database_identifier: str
    configuration: dict[str, Any]
    safety: dict[str, Any]
    score_semantics: dict[str, Any]
    small_sample: dict[str, Any]
    counts: dict[str, Any]
    metrics: dict[str, Any]
    attempt_metrics: dict[str, Any]
    reliability: dict[str, Any]
    exclusions: dict[str, Any]
    breakdowns: dict[str, Any]
    evaluated_examples: list[dict[str, Any]]
    mistake_examples: list[dict[str, Any]]
    temporal_diagnostics: dict[str, Any]
    unsupported_metrics: list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
        )


@dataclass(frozen=True)
class _RankedCandidate:
    rank: int
    label: str
    score: float
    scientific_name: str | None


@dataclass(frozen=True)
class _ValidatedSuggestion:
    suggestion: StoredSpeciesSuggestion
    ranking: tuple[_RankedCandidate, ...]
    top_three_available: bool
    stored_candidate_membership_available: bool
    crop_key: str
    provenance: dict[str, Any]
    candidate_prompt_variant_id: str
    model_weights_variant_id: str
    runtime_variant_id: str
    model_weights_runtime_combination_id: str


@dataclass(frozen=True)
class _CompleteCandidateManifest:
    """One defensively validated complete candidate-bank manifest."""

    labels: tuple[str, ...]
    entries: tuple[Mapping[str, Any], ...]
    count: int
    fingerprint: str
    version: str | None


def evaluate_bioclip_field_truth(
    review_labels: list[StoredReviewLabel] | tuple[StoredReviewLabel, ...],
    species_suggestions: (
        list[StoredSpeciesSuggestion] | tuple[StoredSpeciesSuggestion, ...]
    ),
    taxonomy: list[TaxonomyDescriptor] | tuple[TaxonomyDescriptor, ...],
    *,
    generated_at: datetime,
    database_identifier: str,
    config: EvaluationConfig | None = None,
    attempts: (list[StoredBioClipAttempt] | tuple[StoredBioClipAttempt, ...]) = (),
) -> BioClipFieldTruthReport:
    """Evaluate stored BioCLIP evidence against exact-target ReviewLabel truth."""

    evaluation_config = config or EvaluationConfig()
    final_truth, unsupported_truth_records = _latest_review_truth(review_labels)
    latest_suggestions, suggestion_audit = _latest_bioclip_suggestions(
        species_suggestions
    )
    taxonomy_by_label = {
        item.label.strip(): item for item in taxonomy if item.label.strip()
    }
    bioclip_attempts = tuple(
        attempt for attempt in attempts if attempt.adapter_id == BIOCLIP_ADAPTER_ID
    )
    attempts_by_suggestion_id = _successful_attempts_by_suggestion_id(bioclip_attempts)

    label_distribution = Counter(item.label.strip() for item in final_truth.values())
    crop_distribution = Counter({key: 0 for key in CROP_BREAKDOWN_KEYS})
    exclusion_counts: Counter[str] = Counter()
    exclusion_details: list[dict[str, Any]] = []
    evaluated_examples: list[dict[str, Any]] = []
    candidate_prompt_variants: dict[str, dict[str, Any]] = {}
    model_weights_variants: dict[str, dict[str, Any]] = {}
    runtime_variants: dict[str, dict[str, Any]] = {}
    combination_variants: dict[str, dict[str, Any]] = {}
    selected_statuses: Counter[str] = Counter()
    selected_suggestion_count = 0
    missing_crop_count = 0
    suggestion_created_after_review_count = 0

    for target_key in sorted(final_truth):
        truth = final_truth[target_key]
        suggestion = latest_suggestions.get(target_key)
        if suggestion is None:
            reasons = ["no_bioclip_suggestion"]
            exclusion_counts.update(reasons)
            exclusion_details.append(_exclusion_detail(target_key, reasons))
            continue

        selected_suggestion_count += 1
        selected_statuses[suggestion.status or "unknown_missing"] += 1
        if _crop_key(suggestion.evidence_region) == "unknown_missing":
            missing_crop_count += 1
        if _datetime_key(suggestion.created_at) > _datetime_key(truth.created_at):
            suggestion_created_after_review_count += 1

        validated, reasons = _validate_suggestion(suggestion)
        if reasons:
            exclusion_counts.update(reasons)
            exclusion_details.append(
                _exclusion_detail(
                    target_key,
                    reasons,
                    suggestion_id=suggestion.id,
                )
            )
            continue
        assert validated is not None

        crop_distribution[validated.crop_key] += 1
        _increment_variant(
            candidate_prompt_variants,
            validated.candidate_prompt_variant_id,
            _candidate_prompt_variant_fields(validated.provenance),
        )
        _increment_variant(
            model_weights_variants,
            validated.model_weights_variant_id,
            _model_weights_variant_fields(validated.provenance),
        )
        _increment_variant(
            runtime_variants,
            validated.runtime_variant_id,
            _runtime_variant_fields(validated.provenance),
        )
        _increment_variant(
            combination_variants,
            validated.model_weights_runtime_combination_id,
            {
                "model_weights_variant_id": validated.model_weights_variant_id,
                "runtime_variant_id": validated.runtime_variant_id,
            },
        )

        corrected_label = truth.label.strip()
        top = validated.ranking[0]
        corrected_rank = next(
            (
                candidate.rank
                for candidate in validated.ranking
                if candidate.label == corrected_label
            ),
            None,
        )
        not_present_among_stored_candidates = (
            corrected_rank is None
            if validated.stored_candidate_membership_available
            else None
        )
        top_three_correct = (
            corrected_rank is not None and corrected_rank <= 3
            if validated.top_three_available
            else None
        )
        candidate_fingerprint = _candidate_set_identifier(validated.provenance)
        linked_attempt = _linked_successful_attempt(
            attempts_by_suggestion_id,
            suggestion,
            target_key,
        )
        linked_manifest = (
            _validated_complete_candidate_manifest(linked_attempt)
            if linked_attempt is not None
            else None
        )
        full_candidate_corrected_rank = (
            _manifest_rank(linked_manifest, corrected_label)
            if linked_manifest is not None
            else None
        )
        full_candidate_contains_corrected_label = (
            _manifest_contains_label(linked_manifest, corrected_label)
            if linked_manifest is not None
            else None
        )
        example = {
            "target_type": target_key[0],
            "target_id": target_key[1],
            "review_label_id": truth.id,
            "suggestion_id": suggestion.id,
            "suggestion_status": suggestion.status,
            "corrected_label": corrected_label,
            "top_suggestion": top.label,
            "top_score": top.score,
            "top_1_correct": top.label == corrected_label,
            "top_3_available": validated.top_three_available,
            "top_3_correct": top_three_correct,
            "corrected_rank_in_stored_ranking": corrected_rank,
            "corrected_label_not_present_among_stored_candidates": (
                not_present_among_stored_candidates
            ),
            "stored_candidate_count": len(validated.ranking),
            "attempt_id": linked_attempt.id if linked_attempt is not None else None,
            "complete_candidate_manifest_available": linked_manifest is not None,
            "complete_candidate_count": (
                linked_manifest.count if linked_manifest is not None else None
            ),
            "corrected_rank_in_complete_candidate_bank": (
                full_candidate_corrected_rank
            ),
            "corrected_label_missing_from_complete_candidate_bank": (
                not full_candidate_contains_corrected_label
                if full_candidate_contains_corrected_label is not None
                else None
            ),
            "crop_source": validated.crop_key,
            "candidate_set_identifier": candidate_fingerprint,
            "candidate_prompt_variant_id": validated.candidate_prompt_variant_id,
            "model_weights_variant_id": validated.model_weights_variant_id,
            "runtime_variant_id": validated.runtime_variant_id,
            "score_kind": BIOCLIP_SCORE_KIND,
            "calibrated": False,
            "top_suggestion_is_species": _is_species_suggestion(
                top,
                taxonomy_by_label,
            ),
            "suggestion_created_after_final_review": (
                _datetime_key(suggestion.created_at) > _datetime_key(truth.created_at)
            ),
        }
        evaluated_examples.append(example)

    evaluated_examples.sort(key=lambda item: (item["target_type"], item["target_id"]))
    eligible_count = len(evaluated_examples)
    top_one_correct = sum(item["top_1_correct"] for item in evaluated_examples)
    top_three_examples = [
        item for item in evaluated_examples if item["top_3_available"]
    ]
    top_three_correct = sum(
        item["top_3_correct"] is True for item in top_three_examples
    )
    corrected_ranks = Counter(
        str(item["corrected_rank_in_stored_ranking"])
        for item in evaluated_examples
        if item["corrected_rank_in_stored_ranking"] is not None
    )
    not_present_among_stored_candidates_count = sum(
        item["corrected_label_not_present_among_stored_candidates"] is True
        for item in evaluated_examples
    )
    stored_candidate_membership_unavailable_count = sum(
        item["corrected_label_not_present_among_stored_candidates"] is None
        for item in evaluated_examples
    )
    stored_candidate_membership_evaluated_count = (
        eligible_count - stored_candidate_membership_unavailable_count
    )
    complete_membership_examples = [
        item
        for item in evaluated_examples
        if item["complete_candidate_manifest_available"]
    ]
    corrected_label_missing_from_complete_candidate_bank_count = sum(
        item["corrected_label_missing_from_complete_candidate_bank"] is True
        for item in complete_membership_examples
    )

    unknown_bird_examples = [
        item for item in evaluated_examples if item["corrected_label"] == "unknown_bird"
    ]
    false_positive_examples = [
        item
        for item in evaluated_examples
        if item["corrected_label"] == "false_positive"
    ]
    known_non_bird_examples = [
        item
        for item in evaluated_examples
        if _is_known_non_bird_truth(item["corrected_label"], taxonomy_by_label)
    ]

    all_mistakes = sorted(
        (
            _mistake_example(item)
            for item in evaluated_examples
            if not item["top_1_correct"]
        ),
        key=lambda item: (
            -item["uncalibrated_score"],
            item["candidate_set_identifier"],
            item["target_type"],
            item["target_id"],
            item["suggestion_id"],
        ),
    )
    mistake_examples = all_mistakes[: evaluation_config.mistake_limit]
    small_sample_warning = _small_sample_warning(
        eligible_count,
        evaluation_config.minimum_examples,
    )
    unreviewed_bioclip_targets = sorted(set(latest_suggestions).difference(final_truth))
    attempt_metrics = _build_attempt_metrics(
        bioclip_attempts,
        species_suggestions,
        final_truth,
        taxonomy_by_label,
    )

    return BioClipFieldTruthReport(
        schema_version=REPORT_SCHEMA_VERSION,
        generated_at=_as_utc(generated_at).isoformat().replace("+00:00", "Z"),
        database_identifier=database_identifier,
        configuration={
            "minimum_examples": evaluation_config.minimum_examples,
            "mistake_limit": evaluation_config.mistake_limit,
            "adapter_id": BIOCLIP_ADAPTER_ID,
            "truth_target_types": ["event", "visit"],
            "record_selection": (
                "latest ReviewLabel and latest BioCLIP suggestion by "
                "(created_at, id) for the exact same target"
            ),
            "attempt_scope": (
                "all supplied manual BioCLIP attempt evidence; attempts never "
                "select or replace the suggestion used for accuracy"
            ),
        },
        safety={
            "read_only_evaluation": True,
            "database_writes_performed": False,
            "inference_invoked": False,
            "review_labels_created_or_modified": False,
            "species_suggestions_created_or_modified": False,
            "product_or_operational_state_modified": False,
            "truth_source": "latest_exact_target_review_label_only",
        },
        score_semantics={
            "kind": BIOCLIP_SCORE_KIND,
            "calibrated": False,
            "is_probability": False,
            "meaning": (
                "Candidate-relative ranking magnitude within the stored candidate "
                "bank; correctness is reported separately."
            ),
        },
        small_sample={
            "eligible_examples": eligible_count,
            "minimum_examples": evaluation_config.minimum_examples,
            "threshold_met": eligible_count >= evaluation_config.minimum_examples,
            "descriptive_only": eligible_count < evaluation_config.minimum_examples,
            "warning": small_sample_warning,
        },
        counts={
            "reviewed_targets_inspected": len(final_truth),
            "bioclip_suggestions_inspected": suggestion_audit[
                "bioclip_suggestions_inspected"
            ],
            "bioclip_targets_inspected": len(latest_suggestions),
            "reviewed_targets_with_bioclip": selected_suggestion_count,
            "eligible_examples": eligible_count,
            "excluded_examples": len(exclusion_details),
            "unreviewed_bioclip_targets": len(unreviewed_bioclip_targets),
            "unscoped_bioclip_suggestions": suggestion_audit[
                "unscoped_bioclip_suggestions"
            ],
            "unsupported_review_label_records": unsupported_truth_records,
            "manual_bioclip_attempts_inspected": attempt_metrics["counts"][
                "total_manual_attempts"
            ],
        },
        metrics={
            "top_1": _accuracy_metric(
                top_one_correct,
                eligible_count,
                unavailable_reason="No eligible examples contain valid rank-1 evidence.",
            ),
            "top_3": _accuracy_metric(
                top_three_correct,
                len(top_three_examples),
                unavailable_reason=(
                    "No eligible examples contain complete, unique stored ranks 1-3."
                ),
                unavailable_count=eligible_count - len(top_three_examples),
            ),
            "corrected_label_ranks_in_stored_ranking": dict(
                sorted(corrected_ranks.items(), key=lambda item: int(item[0]))
            ),
            "corrected_label_not_present_among_stored_candidates": {
                "available": stored_candidate_membership_evaluated_count > 0,
                "count": (
                    not_present_among_stored_candidates_count
                    if stored_candidate_membership_evaluated_count > 0
                    else None
                ),
                "evaluated_count": stored_candidate_membership_evaluated_count,
                "unavailable_count": stored_candidate_membership_unavailable_count,
                "meaning": (
                    "Absent from every interpretable candidate actually stored for "
                    "the suggestion. This does not claim a complete top-K ranking or "
                    "absence from the full candidate bank."
                ),
            },
            "corrected_label_missing_from_candidate_set": {
                "available": bool(complete_membership_examples),
                "count": (
                    corrected_label_missing_from_complete_candidate_bank_count
                    if complete_membership_examples
                    else None
                ),
                "evaluated_count": len(complete_membership_examples),
                "unavailable_count": eligible_count - len(complete_membership_examples),
                "reason": (
                    None
                    if complete_membership_examples
                    else (
                        "No selected successful suggestion is linked to a valid "
                        "complete candidate-bank manifest. Historical suggestions "
                        "are not backfilled."
                    )
                ),
            },
            "unknown_bird_truth": _false_species_metric(unknown_bird_examples),
            "false_positive_truth": _false_species_metric(false_positive_examples),
            "known_non_bird_truth": _false_species_metric(known_non_bird_examples),
            "top_1_mistake_count": len(all_mistakes),
        },
        attempt_metrics=attempt_metrics,
        reliability={
            "runtime_ms": attempt_metrics["duration_ms"],
            "timeout_runs": {
                "available": True,
                "count": attempt_metrics["counts"]["outcomes"]["timed_out"],
                "coverage": "recorded_manual_attempts_only",
                "historical_coverage_incomplete": attempt_metrics[
                    "historical_coverage"
                ]["incomplete"],
            },
            "failed_runs": {
                "available": True,
                "count": attempt_metrics["counts"]["outcomes"]["failed"],
                "coverage": "recorded_manual_attempts_only",
                "historical_coverage_incomplete": attempt_metrics[
                    "historical_coverage"
                ]["incomplete"],
            },
            "no_result_runs": {
                "available": True,
                "count": attempt_metrics["counts"]["outcomes"]["no_result"],
                "coverage": "recorded_manual_attempts_only",
                "historical_coverage_incomplete": attempt_metrics[
                    "historical_coverage"
                ]["incomplete"],
            },
            "missing_provenance_count": exclusion_counts["missing_provenance"],
            "missing_crop_count": missing_crop_count,
            "selected_suggestion_status_distribution": dict(
                sorted(selected_statuses.items())
            ),
        },
        exclusions={
            "reason_counts": dict(sorted(exclusion_counts.items())),
            "reason_counts_may_overlap": True,
            "details": exclusion_details,
            "unreviewed_bioclip_target_details": [
                {"target_type": key[0], "target_id": key[1]}
                for key in unreviewed_bioclip_targets
            ],
        },
        breakdowns={
            "review_label_distribution": dict(sorted(label_distribution.items())),
            "crop_source_distribution": {
                key: crop_distribution[key] for key in CROP_BREAKDOWN_KEYS
            },
            "candidate_prompt_variants": _sorted_variants(candidate_prompt_variants),
            "model_weights_variants": _sorted_variants(model_weights_variants),
            "runtime_version_variants": _sorted_variants(runtime_variants),
            "model_weights_runtime_combinations": _sorted_variants(
                combination_variants
            ),
        },
        evaluated_examples=evaluated_examples,
        mistake_examples=mistake_examples,
        temporal_diagnostics={
            "suggestion_created_after_final_review_count": (
                suggestion_created_after_review_count
            ),
            "meaning": (
                "Diagnostic only. ReviewLabel and SpeciesSuggestion have no durable "
                "association ID; record selection remains exact-target and latest."
            ),
        },
        unsupported_metrics=[
            {
                "metric": "historical_manual_attempt_outcomes_and_duration",
                "smallest_future_provenance_addition": (
                    "Unavailable by design before durable attempt recording; "
                    "historical suggestions are not backfilled or rerun."
                ),
            },
        ],
    )


def render_terminal_report(report: BioClipFieldTruthReport) -> str:
    """Render a concise human-readable report without hiding unavailable data."""

    counts = report.counts
    metrics = report.metrics
    attempts = report.attempt_metrics
    reliability = report.reliability
    breakdowns = report.breakdowns
    lines = [
        "MockingBird BioCLIP field-truth evaluation",
        "",
        f"WARNING: {report.small_sample['warning']}",
        "",
        f"Database: {report.database_identifier}",
        f"Generated: {report.generated_at}",
        (
            "Safety: read-only stored-record evaluation; no inference, truth write, "
            "camera action, or monitoring action."
        ),
        "",
        "Cohort",
        f"- Reviewed targets inspected: {counts['reviewed_targets_inspected']}",
        f"- Reviewed targets with BioCLIP: {counts['reviewed_targets_with_bioclip']}",
        f"- Eligible examples: {counts['eligible_examples']}",
        f"- Excluded examples: {counts['excluded_examples']}",
        f"- Unreviewed BioCLIP targets: {counts['unreviewed_bioclip_targets']}",
        "",
        "Accuracy",
        (
            "- Scores are candidate-relative and uncalibrated; they are not "
            "probabilities."
        ),
        f"- Top-1: {_format_accuracy(metrics['top_1'])}",
        f"- Top-3: {_format_accuracy(metrics['top_3'])}",
        "- Corrected label not present among stored candidates: "
        + _format_stored_candidate_absence(
            metrics["corrected_label_not_present_among_stored_candidates"]
        ),
        "- Corrected label absent from complete candidate bank: "
        + _format_complete_candidate_absence(
            metrics["corrected_label_missing_from_candidate_set"]
        ),
        "- Species suggested on unknown_bird: "
        + _format_false_species_metric(metrics["unknown_bird_truth"]),
        "- Species suggested on false_positive: "
        + _format_false_species_metric(metrics["false_positive_truth"]),
        "- Species suggested on known non-bird truth: "
        + _format_false_species_metric(metrics["known_non_bird_truth"]),
        "",
        "Breakdowns",
        "- Review labels: "
        + _format_distribution(breakdowns["review_label_distribution"]),
        "- Crop sources: "
        + _format_distribution(breakdowns["crop_source_distribution"]),
        (
            "- Candidate/prompt variants: "
            f"{len(breakdowns['candidate_prompt_variants'])}"
        ),
        f"- Model/weights variants: {len(breakdowns['model_weights_variants'])}",
        f"- Runtime-version variants: {len(breakdowns['runtime_version_variants'])}",
        (
            "- Model/weights/runtime combinations: "
            f"{len(breakdowns['model_weights_runtime_combinations'])}"
        ),
        "",
        "Reliability and exclusions",
        (
            "- Recorded manual attempts: "
            f"{attempts['counts']['total_manual_attempts']} "
            f"({attempts['counts']['terminal_attempts']} terminal, "
            f"{attempts['counts']['incomplete_attempts']} incomplete)"
        ),
        "- Attempt outcomes: " + _format_distribution(attempts["counts"]["outcomes"]),
        "- Attempt success rate: "
        + _format_attempt_success_rate(attempts["success_rate"]),
        "- Runtime median/min/max: "
        + _format_duration_summary(reliability["runtime_ms"]),
        f"- Timeout count: {reliability['timeout_runs']['count']}",
        f"- Failed-run count: {reliability['failed_runs']['count']}",
        f"- No-result count: {reliability['no_result_runs']['count']}",
        (
            "- Historical suggestions without linked attempts: "
            f"{attempts['suggestions_without_linked_attempts']['count']}"
        ),
        (
            "- Complete candidate manifests: "
            f"{attempts['candidate_banks']['complete_manifest_attempts']}/"
            f"{attempts['counts']['total_manual_attempts']}"
        ),
        f"- Missing provenance: {reliability['missing_provenance_count']}",
        f"- Missing crop: {reliability['missing_crop_count']}",
        "- Exclusions: " + _format_distribution(report.exclusions["reason_counts"]),
        "",
        "Highest-scoring top-1 mistakes",
    ]
    if report.mistake_examples:
        for mistake in report.mistake_examples:
            lines.append(
                "- "
                f"{mistake['target_type']}:{mistake['target_id']} "
                f"truth={mistake['corrected_label']} "
                f"top={mistake['top_suggestion']} "
                f"score={mistake['uncalibrated_score']:.3f} "
                f"crop={mistake['crop_source']} "
                f"candidate={mistake['candidate_set_identifier']}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines)


def _latest_review_truth(
    review_labels: list[StoredReviewLabel] | tuple[StoredReviewLabel, ...],
) -> tuple[dict[tuple[str, str], StoredReviewLabel], int]:
    grouped: dict[tuple[str, str], list[StoredReviewLabel]] = defaultdict(list)
    unsupported = 0
    for label in review_labels:
        target_key = _review_target_key(label)
        if target_key is None or not label.label.strip():
            unsupported += 1
            continue
        grouped[target_key].append(label)
    return (
        {
            key: max(
                values, key=lambda value: (_datetime_key(value.created_at), value.id)
            )
            for key, values in grouped.items()
        },
        unsupported,
    )


def _latest_bioclip_suggestions(
    species_suggestions: (
        list[StoredSpeciesSuggestion] | tuple[StoredSpeciesSuggestion, ...]
    ),
) -> tuple[dict[tuple[str, str], StoredSpeciesSuggestion], dict[str, int]]:
    grouped: dict[tuple[str, str], list[StoredSpeciesSuggestion]] = defaultdict(list)
    inspected = 0
    unscoped = 0
    for suggestion in species_suggestions:
        if suggestion.adapter_id != BIOCLIP_ADAPTER_ID:
            continue
        inspected += 1
        target_key = _suggestion_target_key(suggestion)
        if target_key is None:
            unscoped += 1
            continue
        grouped[target_key].append(suggestion)
    return (
        {
            key: max(
                values, key=lambda value: (_datetime_key(value.created_at), value.id)
            )
            for key, values in grouped.items()
        },
        {
            "bioclip_suggestions_inspected": inspected,
            "unscoped_bioclip_suggestions": unscoped,
        },
    )


def _successful_attempts_by_suggestion_id(
    attempts: tuple[StoredBioClipAttempt, ...],
) -> dict[str, StoredBioClipAttempt]:
    grouped: dict[str, list[StoredBioClipAttempt]] = defaultdict(list)
    for attempt in attempts:
        suggestion_id = _optional_text(attempt.resulting_species_suggestion_id)
        if attempt.outcome == "succeeded" and suggestion_id is not None:
            grouped[suggestion_id].append(attempt)
    return {
        suggestion_id: max(
            values,
            key=lambda value: (
                _datetime_key(value.completed_at or value.started_at),
                value.id,
            ),
        )
        for suggestion_id, values in grouped.items()
    }


def _linked_successful_attempt(
    attempts_by_suggestion_id: Mapping[str, StoredBioClipAttempt],
    suggestion: StoredSpeciesSuggestion,
    target_key: tuple[str, str],
) -> StoredBioClipAttempt | None:
    attempt = attempts_by_suggestion_id.get(suggestion.id)
    if attempt is None or _attempt_target_key(attempt) != target_key:
        return None
    return attempt


def _build_attempt_metrics(
    attempts: tuple[StoredBioClipAttempt, ...],
    species_suggestions: (
        list[StoredSpeciesSuggestion] | tuple[StoredSpeciesSuggestion, ...]
    ),
    final_truth: Mapping[tuple[str, str], StoredReviewLabel],
    taxonomy_by_label: Mapping[str, TaxonomyDescriptor],
) -> dict[str, Any]:
    outcome_counts = Counter({outcome: 0 for outcome in BIOCLIP_ATTEMPT_OUTCOMES})
    terminal_attempts: list[StoredBioClipAttempt] = []
    incomplete_attempts: list[StoredBioClipAttempt] = []
    for attempt in attempts:
        if attempt.outcome in BIOCLIP_ATTEMPT_OUTCOMES:
            outcome_counts[attempt.outcome] += 1
            terminal_attempts.append(attempt)
        else:
            incomplete_attempts.append(attempt)

    valid_durations = [
        int(attempt.duration_ms)
        for attempt in terminal_attempts
        if _valid_duration_ms(attempt.duration_ms)
    ]
    duration_by_crop: dict[str, list[int]] = defaultdict(list)
    duration_by_variant: dict[str, list[int]] = defaultdict(list)
    crop_attempt_counts: Counter[str] = Counter()
    variant_attempt_counts: Counter[str] = Counter()
    for attempt in terminal_attempts:
        crop_key = _attempt_crop_key(attempt.crop_source)
        variant_id = _attempt_model_runtime_variant_id(attempt)
        crop_attempt_counts[crop_key] += 1
        variant_attempt_counts[variant_id] += 1
        if not _valid_duration_ms(attempt.duration_ms):
            continue
        duration = int(attempt.duration_ms)
        duration_by_crop[crop_key].append(duration)
        duration_by_variant[variant_id].append(duration)

    target_counts: Counter[tuple[str, str]] = Counter()
    invalid_target_count = 0
    for attempt in attempts:
        target_key = _attempt_target_key(attempt)
        if target_key is None:
            invalid_target_count += 1
        else:
            target_counts[target_key] += 1
    repeated_attempt_count = sum(max(0, count - 1) for count in target_counts.values())
    repeated_target_count = sum(count > 1 for count in target_counts.values())

    bioclip_suggestion_ids = {
        suggestion.id
        for suggestion in species_suggestions
        if suggestion.adapter_id == BIOCLIP_ADAPTER_ID
    }
    linked_suggestion_ids = {
        suggestion_id
        for attempt in attempts
        if attempt.outcome == "succeeded"
        for suggestion_id in [_optional_text(attempt.resulting_species_suggestion_id)]
        if suggestion_id is not None
    }
    suggestions_without_linked_attempts = bioclip_suggestion_ids - linked_suggestion_ids
    linked_attempts_without_stored_suggestion = (
        linked_suggestion_ids - bioclip_suggestion_ids
    )
    historical_coverage_incomplete = bool(suggestions_without_linked_attempts)

    complete_manifests: list[
        tuple[StoredBioClipAttempt, _CompleteCandidateManifest]
    ] = []
    invalid_complete_manifest_count = 0
    for attempt in attempts:
        manifest = _validated_complete_candidate_manifest(attempt)
        if manifest is not None:
            complete_manifests.append((attempt, manifest))
        elif attempt.candidate_manifest_complete:
            invalid_complete_manifest_count += 1

    size_distribution = Counter(
        str(manifest.count) for _, manifest in complete_manifests
    )
    fingerprint_counts = Counter(
        manifest.fingerprint for _, manifest in complete_manifests
    )
    candidate_version_counts = Counter(
        manifest.version or "unknown_missing" for _, manifest in complete_manifests
    )
    candidate_variant_counts = Counter(
        (
            manifest.fingerprint,
            manifest.version or "unknown_missing",
            manifest.count,
        )
        for _, manifest in complete_manifests
    )
    corrected_label_absent_details: list[dict[str, str]] = []
    reviewed_complete_manifest_count = 0
    unknown_bird_attempt_count = 0
    taxonomy_non_bird_attempt_count = 0
    taxonomy_non_bird_label_counts: Counter[str] = Counter()
    for attempt, manifest in complete_manifests:
        labels = set(manifest.labels)
        if "unknown_bird" in labels:
            unknown_bird_attempt_count += 1
        non_bird_labels = sorted(
            label
            for label in labels
            if _is_taxonomy_backed_non_bird_candidate(
                label,
                taxonomy_by_label,
            )
        )
        if non_bird_labels:
            taxonomy_non_bird_attempt_count += 1
            taxonomy_non_bird_label_counts.update(non_bird_labels)

        target_key = _attempt_target_key(attempt)
        if target_key is None or target_key not in final_truth:
            continue
        reviewed_complete_manifest_count += 1
        corrected_label = final_truth[target_key].label.strip()
        if corrected_label not in labels:
            corrected_label_absent_details.append(
                {
                    "attempt_id": attempt.id,
                    "target_type": target_key[0],
                    "target_id": target_key[1],
                }
            )

    successful_attempt_count = outcome_counts["succeeded"]
    top_three_supported_count = sum(
        attempt.outcome == "succeeded" and _manifest_supports_top_three(manifest)
        for attempt, manifest in complete_manifests
    )
    success_denominator = len(terminal_attempts)
    return {
        "scope": {
            "kind": "recorded_user_triggered_manual_bioclip_attempts",
            "accuracy_selection_uses_attempts": False,
            "truth_source": "latest_exact_target_review_label_only",
            "automatic_attempts_included": False,
        },
        "counts": {
            "total_manual_attempts": len(attempts),
            "terminal_attempts": len(terminal_attempts),
            "incomplete_attempts": len(incomplete_attempts),
            "outcomes": {
                outcome: outcome_counts[outcome] for outcome in BIOCLIP_ATTEMPT_OUTCOMES
            },
            "invalid_target_records": invalid_target_count,
        },
        "success_rate": {
            "available": success_denominator > 0,
            "successful_attempts": successful_attempt_count,
            "denominator": "terminal_recorded_attempts",
            "denominator_count": success_denominator,
            "rate": (
                successful_attempt_count / success_denominator
                if success_denominator
                else None
            ),
            "incomplete_attempts_excluded": len(incomplete_attempts),
        },
        "duration_ms": _duration_summary(
            valid_durations,
            unavailable_count=len(terminal_attempts) - len(valid_durations),
            historical_coverage_incomplete=historical_coverage_incomplete,
        ),
        "duration_by_crop_source": [
            {
                "crop_source": crop_source,
                "attempt_count": crop_attempt_counts[crop_source],
                **_duration_summary(
                    duration_by_crop.get(crop_source, []),
                    unavailable_count=(
                        crop_attempt_counts[crop_source]
                        - len(duration_by_crop.get(crop_source, []))
                    ),
                    historical_coverage_incomplete=historical_coverage_incomplete,
                ),
            }
            for crop_source in sorted(crop_attempt_counts)
        ],
        "duration_by_model_runtime_variant": [
            {
                "variant_id": variant_id,
                "attempt_count": variant_attempt_counts[variant_id],
                **_duration_summary(
                    duration_by_variant.get(variant_id, []),
                    unavailable_count=(
                        variant_attempt_counts[variant_id]
                        - len(duration_by_variant.get(variant_id, []))
                    ),
                    historical_coverage_incomplete=historical_coverage_incomplete,
                ),
            }
            for variant_id in sorted(variant_attempt_counts)
        ],
        "attempt_counts_by_target": [
            {
                "target_type": target_type,
                "target_id": target_id,
                "count": target_counts[(target_type, target_id)],
            }
            for target_type, target_id in sorted(target_counts)
        ],
        "repeated_attempts": {
            "attempts_beyond_first_per_target": repeated_attempt_count,
            "targets_with_multiple_attempts": repeated_target_count,
        },
        "attempts_without_suggestions": {
            "count": sum(
                _optional_text(attempt.resulting_species_suggestion_id) is None
                for attempt in attempts
            ),
            "successful_attempts_without_suggestion": sum(
                attempt.outcome == "succeeded"
                and _optional_text(attempt.resulting_species_suggestion_id) is None
                for attempt in attempts
            ),
            "linked_attempts_without_stored_suggestion": len(
                linked_attempts_without_stored_suggestion
            ),
        },
        "suggestions_without_linked_attempts": {
            "count": len(suggestions_without_linked_attempts),
            "meaning": (
                "Stored BioCLIP suggestions without a successful durable attempt "
                "link are historical or incomplete evidence."
            ),
        },
        "historical_coverage": {
            "complete": not historical_coverage_incomplete,
            "incomplete": historical_coverage_incomplete,
            "boundary": (
                "Attempt outcomes, durations, and complete candidate manifests are "
                "available only for manual BioCLIP invocations recorded after "
                "durable attempt provenance was introduced; no history is backfilled."
            ),
        },
        "candidate_banks": {
            "complete_manifest_attempts": len(complete_manifests),
            "incomplete_manifest_attempts": len(attempts) - len(complete_manifests),
            "invalid_complete_manifest_attempts": invalid_complete_manifest_count,
            "size_distribution": dict(
                sorted(size_distribution.items(), key=lambda item: int(item[0]))
            ),
            "fingerprints": [
                {
                    "sha256": fingerprint,
                    "attempt_count": fingerprint_counts[fingerprint],
                }
                for fingerprint in sorted(fingerprint_counts)
            ],
            "version_distribution": dict(sorted(candidate_version_counts.items())),
            "variants": [
                {
                    "sha256": fingerprint,
                    "version": version,
                    "candidate_count": candidate_count,
                    "attempt_count": candidate_variant_counts[
                        (fingerprint, version, candidate_count)
                    ],
                }
                for fingerprint, version, candidate_count in sorted(
                    candidate_variant_counts
                )
            ],
            "variant_count": len(candidate_variant_counts),
            "corrected_label_absent": {
                "available": reviewed_complete_manifest_count > 0,
                "count": (
                    len(corrected_label_absent_details)
                    if reviewed_complete_manifest_count
                    else None
                ),
                "evaluated_attempt_count": reviewed_complete_manifest_count,
                "details": corrected_label_absent_details,
            },
            "unknown_bird_presence": {
                "available": bool(complete_manifests),
                "attempt_count": unknown_bird_attempt_count,
                "evaluated_attempt_count": len(complete_manifests),
                "rate": (
                    unknown_bird_attempt_count / len(complete_manifests)
                    if complete_manifests
                    else None
                ),
            },
            "taxonomy_backed_non_bird_escape_presence": {
                "available": bool(complete_manifests),
                "attempt_count": taxonomy_non_bird_attempt_count,
                "evaluated_attempt_count": len(complete_manifests),
                "rate": (
                    taxonomy_non_bird_attempt_count / len(complete_manifests)
                    if complete_manifests
                    else None
                ),
                "label_distribution": dict(
                    sorted(taxonomy_non_bird_label_counts.items())
                ),
                "classification_source": "stored_review_taxonomy_category",
            },
            "top_3_support": {
                "available": successful_attempt_count > 0,
                "successful_attempt_count": successful_attempt_count,
                "supported_attempt_count": top_three_supported_count,
                "unsupported_attempt_count": (
                    successful_attempt_count - top_three_supported_count
                ),
                "fully_supported": (
                    top_three_supported_count == successful_attempt_count
                    if successful_attempt_count
                    else None
                ),
            },
        },
    }


def _duration_summary(
    durations: list[int],
    *,
    unavailable_count: int,
    historical_coverage_incomplete: bool,
) -> dict[str, Any]:
    return {
        "available": bool(durations),
        "sample_count": len(durations),
        "median": median(durations) if durations else None,
        "minimum": min(durations) if durations else None,
        "maximum": max(durations) if durations else None,
        "unavailable_count": unavailable_count,
        "coverage": "recorded_manual_attempts_only",
        "historical_coverage_incomplete": historical_coverage_incomplete,
        "reason": (
            None if durations else "No recorded terminal attempt has a valid duration."
        ),
    }


def _validated_complete_candidate_manifest(
    attempt: StoredBioClipAttempt,
) -> _CompleteCandidateManifest | None:
    manifest = attempt.candidate_manifest
    count = attempt.candidate_set_count
    fingerprint = attempt.candidate_set_sha256
    if (
        attempt.candidate_manifest_complete is not True
        or manifest is None
        or isinstance(count, bool)
        or not isinstance(count, int)
        or count < 1
        or len(manifest) != count
        or not _is_sha256(fingerprint)
    ):
        return None
    labels: list[str] = []
    raw_labels: list[str] = []
    for expected_position, entry in enumerate(manifest, start=1):
        label = _candidate_manifest_label(entry)
        raw_label = entry.get("raw_label") if isinstance(entry, Mapping) else None
        source_position = (
            entry.get("source_position") if isinstance(entry, Mapping) else None
        )
        if (
            label is None
            or not isinstance(raw_label, str)
            or not raw_label.strip()
            or raw_label != raw_label.strip()
            or isinstance(source_position, bool)
            or source_position != expected_position
        ):
            return None
        labels.append(label)
        raw_labels.append(raw_label)
    computed_fingerprint = hashlib.sha256(
        "\n".join(raw_labels).encode("utf-8")
    ).hexdigest()
    if computed_fingerprint != str(fingerprint).lower():
        return None
    return _CompleteCandidateManifest(
        labels=tuple(labels),
        entries=manifest,
        count=count,
        fingerprint=str(fingerprint).lower(),
        version=_safe_report_token(attempt.candidate_set_version),
    )


def _candidate_manifest_label(entry: Mapping[str, Any]) -> str | None:
    if not isinstance(entry, Mapping):
        return None
    for field in ("normalized_label", "label"):
        value = entry.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_report_token(value: Any) -> str | None:
    text = _optional_text(value)
    if (
        text is None
        or len(text) > 100
        or any(
            character
            not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-"
            for character in text
        )
    ):
        return None
    return text


def _manifest_contains_label(
    manifest: _CompleteCandidateManifest,
    label: str,
) -> bool:
    return label in manifest.labels


def _manifest_rank(
    manifest: _CompleteCandidateManifest,
    label: str,
) -> int | None:
    for entry in manifest.entries:
        if _candidate_manifest_label(entry) != label:
            continue
        rank = entry.get("global_rank", entry.get("rank"))
        if not isinstance(rank, bool) and isinstance(rank, int) and rank > 0:
            return rank
    return None


def _manifest_supports_top_three(
    manifest: _CompleteCandidateManifest,
) -> bool:
    valid_ranks: set[int] = set()
    for entry in manifest.entries:
        rank = entry.get("global_rank", entry.get("rank"))
        score = entry.get("score")
        if (
            not isinstance(rank, bool)
            and isinstance(rank, int)
            and rank > 0
            and _valid_score(score)
            and entry.get("score_kind") == BIOCLIP_SCORE_KIND
            and entry.get("calibrated") is False
        ):
            valid_ranks.add(rank)
    return {1, 2, 3}.issubset(valid_ranks)


def _attempt_model_runtime_variant_id(attempt: StoredBioClipAttempt) -> str:
    model = attempt.model_provenance
    preprocessing = attempt.preprocessing
    fields: dict[str, Any] = {}
    if isinstance(model, Mapping):
        for key in (
            "adapter_id",
            "adapter_contract_version",
            "model_name",
            "architecture_id",
            "device",
            "open_clip_version",
            "torch_version",
            "pillow_version",
            "numpy_version",
            "model_weights_sha256",
            "preprocessing_id",
            "preprocessing_sha256",
        ):
            value = model.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                fields[key] = value
    if isinstance(preprocessing, Mapping):
        for key in ("preprocessing_id", "preprocessing_sha256"):
            value = preprocessing.get(key)
            if isinstance(value, (str, int, float, bool)) or value is None:
                fields[f"preprocessing.{key}"] = value
    return (
        _variant_id("attempt-model-runtime", fields)
        if fields
        else "attempt-model-runtime-unknown-missing"
    )


def _attempt_crop_key(value: str | None) -> str:
    return {
        "megadetector": "credible_megadetector_crop",
        "credible_megadetector_crop": "credible_megadetector_crop",
        "activity": "measured_activity_crop",
        "measured_activity_crop": "measured_activity_crop",
        "full_frame": "full_frame_fallback",
        "full_frame_fallback": "full_frame_fallback",
    }.get(_optional_text(value), "unknown_missing")


def _attempt_target_key(
    attempt: StoredBioClipAttempt,
) -> tuple[str, str] | None:
    target_type = attempt.target_type.strip()
    target_id = attempt.target_id.strip()
    if target_type not in {"event", "visit"} or not target_id:
        return None
    return target_type, target_id


def _is_taxonomy_backed_non_bird_candidate(
    label: str,
    taxonomy_by_label: Mapping[str, TaxonomyDescriptor],
) -> bool:
    item = taxonomy_by_label.get(label)
    return item is not None and item.category in _CANDIDATE_NON_BIRD_CATEGORIES


def _valid_duration_ms(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, int) and value >= 0


def _review_target_key(label: StoredReviewLabel) -> tuple[str, str] | None:
    target_type = label.target_type.strip()
    target_id = label.target_id.strip()
    if target_type not in {"event", "visit"} or not target_id:
        return None
    return target_type, target_id


def _suggestion_target_key(
    suggestion: StoredSpeciesSuggestion,
) -> tuple[str, str] | None:
    if suggestion.visit_id is not None and suggestion.visit_id.strip():
        return "visit", suggestion.visit_id.strip()
    if suggestion.event_id is not None and suggestion.event_id.strip():
        return "event", suggestion.event_id.strip()
    return None


def _validate_suggestion(
    suggestion: StoredSpeciesSuggestion,
) -> tuple[_ValidatedSuggestion | None, list[str]]:
    reasons: list[str] = []
    top = _primary_candidate(suggestion)
    if top is None:
        reasons.append("missing_ranking")
    provenance = _validated_provenance(suggestion.evidence_region)
    if provenance is None:
        reasons.append("missing_provenance")
    if reasons:
        return None, reasons
    assert top is not None
    assert provenance is not None

    alternatives, alternatives_fully_valid = _validated_alternatives(
        suggestion.alternatives
    )
    rank_groups: dict[int, list[_RankedCandidate]] = defaultdict(list)
    for alternative in alternatives:
        rank_groups[alternative.rank].append(alternative)
    unique_alternatives = [
        values[0]
        for rank, values in sorted(rank_groups.items())
        if rank > 1 and len(values) == 1
    ]
    duplicates_present = any(len(values) != 1 for values in rank_groups.values())
    ranking = (top, *unique_alternatives)
    rank_values = {candidate.rank for candidate in ranking}
    candidate_fields = _candidate_prompt_variant_fields(provenance)
    model_fields = _model_weights_variant_fields(provenance)
    runtime_fields = _runtime_variant_fields(provenance)
    candidate_variant_id = _variant_id("candidate-prompt", candidate_fields)
    model_variant_id = _variant_id("model-weights", model_fields)
    runtime_variant_id = _variant_id("runtime", runtime_fields)
    return (
        _ValidatedSuggestion(
            suggestion=suggestion,
            ranking=ranking,
            top_three_available={1, 2, 3}.issubset(rank_values),
            stored_candidate_membership_available=(
                alternatives_fully_valid and not duplicates_present
            ),
            crop_key=_crop_key(suggestion.evidence_region),
            provenance=provenance,
            candidate_prompt_variant_id=candidate_variant_id,
            model_weights_variant_id=model_variant_id,
            runtime_variant_id=runtime_variant_id,
            model_weights_runtime_combination_id=_variant_id(
                "model-runtime",
                {
                    "model_weights_variant_id": model_variant_id,
                    "runtime_variant_id": runtime_variant_id,
                },
            ),
        ),
        [],
    )


def _primary_candidate(
    suggestion: StoredSpeciesSuggestion,
) -> _RankedCandidate | None:
    label = suggestion.suggested_label.strip()
    if suggestion.rank != 1 or not label or not _valid_score(suggestion.confidence):
        return None
    return _RankedCandidate(
        rank=1,
        label=label,
        score=float(suggestion.confidence),
        scientific_name=_optional_text(suggestion.suggested_scientific_name),
    )


def _validated_alternatives(
    alternatives: tuple[Mapping[str, Any], ...] | None,
) -> tuple[list[_RankedCandidate], bool]:
    if alternatives is None:
        return [], False
    candidates: list[_RankedCandidate] = []
    fully_valid = True
    for value in alternatives:
        candidate = _alternative_candidate(value)
        if candidate is None:
            fully_valid = False
        else:
            candidates.append(candidate)
    return candidates, fully_valid


def _alternative_candidate(value: Mapping[str, Any]) -> _RankedCandidate | None:
    rank = value.get("rank")
    label = value.get("suggested_label")
    score = value.get("score")
    scientific_name = value.get("scientific_name")
    if (
        isinstance(rank, bool)
        or not isinstance(rank, int)
        or rank <= 1
        or not isinstance(label, str)
        or not label.strip()
        or not _valid_score(score)
        or value.get("score_kind") != BIOCLIP_SCORE_KIND
        or value.get("calibrated") is not False
        or scientific_name is not None
        and not isinstance(scientific_name, str)
    ):
        return None
    return _RankedCandidate(
        rank=rank,
        label=label.strip(),
        score=float(score),
        scientific_name=_optional_text(scientific_name),
    )


def _validated_provenance(
    evidence_region: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(evidence_region, Mapping):
        return None
    provenance = evidence_region.get("model_provenance")
    if not isinstance(provenance, Mapping):
        return None
    text_fields = (
        "model_name",
        "device",
        "open_clip_version",
        "torch_version",
        "model_weights_name",
        "prompt_recipe_id",
    )
    digest_fields = (
        "labels_sha256",
        "embedding_cache_sha256",
        "model_config_sha256",
        "model_weights_sha256",
        "prompt_recipe_sha256",
    )
    label_count = provenance.get("label_count")
    if (
        provenance.get("adapter_id") != BIOCLIP_ADAPTER_ID
        or evidence_region.get("score_semantics") != BIOCLIP_SCORE_KIND
        or evidence_region.get("calibrated") is not False
        or provenance.get("score_kind") != BIOCLIP_SCORE_KIND
        or provenance.get("calibrated") is not False
        or isinstance(label_count, bool)
        or not isinstance(label_count, int)
        or label_count < 1
        or any(not _required_text(provenance.get(field)) for field in text_fields)
        or any(not _is_sha256(provenance.get(field)) for field in digest_fields)
    ):
        return None
    return {
        "adapter_id": BIOCLIP_ADAPTER_ID,
        **{field: str(provenance[field]).strip() for field in text_fields},
        **{field: str(provenance[field]).lower() for field in digest_fields},
        "label_count": label_count,
        "score_kind": BIOCLIP_SCORE_KIND,
        "calibrated": False,
    }


def _candidate_prompt_variant_fields(provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "label_count": provenance["label_count"],
        "labels_sha256": provenance["labels_sha256"],
        "embedding_cache_sha256": provenance["embedding_cache_sha256"],
        "prompt_recipe_id": provenance["prompt_recipe_id"],
        "prompt_recipe_sha256": provenance["prompt_recipe_sha256"],
    }


def _model_weights_variant_fields(provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "model_name": provenance["model_name"],
        "model_config_sha256": provenance["model_config_sha256"],
        "model_weights_name": provenance["model_weights_name"],
        "model_weights_sha256": provenance["model_weights_sha256"],
    }


def _runtime_variant_fields(provenance: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "device": provenance["device"],
        "open_clip_version": provenance["open_clip_version"],
        "torch_version": provenance["torch_version"],
    }


def _candidate_set_identifier(provenance: Mapping[str, Any]) -> str:
    return (
        f"labels-{str(provenance['labels_sha256'])[:12]}-n{provenance['label_count']}"
    )


def _crop_key(evidence_region: Mapping[str, Any] | None) -> str:
    if not isinstance(evidence_region, Mapping):
        return "unknown_missing"
    source = evidence_region.get("source")
    return {
        "megadetector": "credible_megadetector_crop",
        "activity": "measured_activity_crop",
        "full_frame": "full_frame_fallback",
    }.get(source, "unknown_missing")


def _is_species_suggestion(
    candidate: _RankedCandidate,
    taxonomy_by_label: Mapping[str, TaxonomyDescriptor],
) -> bool | None:
    taxonomy_item = taxonomy_by_label.get(candidate.label)
    if taxonomy_item is not None and taxonomy_item.is_species:
        return True
    if candidate.scientific_name:
        return True
    if taxonomy_item is not None:
        return False
    return None


def _is_known_non_bird_truth(
    label: str,
    taxonomy_by_label: Mapping[str, TaxonomyDescriptor],
) -> bool:
    item = taxonomy_by_label.get(label)
    return item is not None and item.category in _NON_BIRD_CATEGORIES


def _false_species_metric(examples: list[dict[str, Any]]) -> dict[str, Any]:
    species_suggested_count = sum(
        item["top_suggestion_is_species"] is True for item in examples
    )
    classified_count = sum(
        item["top_suggestion_is_species"] is not None for item in examples
    )
    unknown_classification_count = len(examples) - classified_count
    return {
        "available": classified_count > 0,
        "evaluated_count": len(examples),
        "classified_count": classified_count,
        "unknown_classification_count": unknown_classification_count,
        "species_suggested_count": species_suggested_count,
        "rate": (
            species_suggested_count / classified_count if classified_count else None
        ),
    }


def _accuracy_metric(
    correct: int,
    evaluated: int,
    *,
    unavailable_reason: str,
    unavailable_count: int = 0,
) -> dict[str, Any]:
    return {
        "available": evaluated > 0,
        "correct": correct if evaluated > 0 else None,
        "evaluated": evaluated,
        "rate": correct / evaluated if evaluated > 0 else None,
        "unavailable_count": unavailable_count,
        "reason": None if evaluated > 0 else unavailable_reason,
    }


def _mistake_example(example: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_type": example["target_type"],
        "target_id": example["target_id"],
        "suggestion_id": example["suggestion_id"],
        "corrected_label": example["corrected_label"],
        "top_suggestion": example["top_suggestion"],
        "uncalibrated_score": example["top_score"],
        "score_kind": BIOCLIP_SCORE_KIND,
        "crop_source": example["crop_source"],
        "candidate_set_identifier": example["candidate_set_identifier"],
        "corrected_rank_in_stored_ranking": example["corrected_rank_in_stored_ranking"],
    }


def _small_sample_warning(eligible: int, minimum: int) -> str:
    if eligible >= minimum:
        return (
            f"The minimum descriptive gate is met ({eligible} eligible examples; "
            f"minimum {minimum}), but this report alone does not select or validate "
            "a production model."
        )
    return (
        f"DESCRIPTIVE ONLY: {eligible} eligible reviewed example"
        f"{'' if eligible == 1 else 's'} is below the minimum of {minimum}; "
        "an accuracy claim or model selection is not justified."
    )


def _exclusion_detail(
    target_key: tuple[str, str],
    reasons: list[str],
    *,
    suggestion_id: str | None = None,
) -> dict[str, Any]:
    return {
        "target_type": target_key[0],
        "target_id": target_key[1],
        "suggestion_id": suggestion_id,
        "reasons": sorted(set(reasons)),
    }


def _increment_variant(
    store: dict[str, dict[str, Any]],
    variant_id: str,
    fields: dict[str, Any],
) -> None:
    if variant_id not in store:
        store[variant_id] = {"variant_id": variant_id, "count": 0, **fields}
    store[variant_id]["count"] += 1


def _sorted_variants(store: Mapping[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [store[key] for key in sorted(store)]


def _variant_id(prefix: str, fields: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(fields),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:16]}"


def _format_accuracy(metric: Mapping[str, Any]) -> str:
    if not metric["available"]:
        return f"unavailable ({metric['reason']})"
    suffix = (
        f"; {metric['unavailable_count']} unavailable"
        if metric["unavailable_count"]
        else ""
    )
    return (
        f"{metric['correct']}/{metric['evaluated']} "
        f"({metric['rate'] * 100:.1f}%){suffix}"
    )


def _format_stored_candidate_absence(metric: Mapping[str, Any]) -> str:
    if not metric["available"]:
        return (
            "unavailable "
            f"({metric['unavailable_count']} eligible ranking"
            f"{'' if metric['unavailable_count'] == 1 else 's'} could not be "
            "interpreted completely)"
        )
    suffix = (
        f"; {metric['unavailable_count']} unavailable"
        if metric["unavailable_count"]
        else ""
    )
    return f"{metric['count']}/{metric['evaluated_count']}{suffix}"


def _format_complete_candidate_absence(metric: Mapping[str, Any]) -> str:
    if not metric["available"]:
        return f"unavailable ({metric['reason']})"
    suffix = (
        f"; {metric['unavailable_count']} historical/incomplete"
        if metric["unavailable_count"]
        else ""
    )
    return f"{metric['count']}/{metric['evaluated_count']}{suffix}"


def _format_attempt_success_rate(metric: Mapping[str, Any]) -> str:
    if not metric["available"]:
        return "unavailable (no terminal recorded attempts)"
    return (
        f"{metric['successful_attempts']}/{metric['denominator_count']} "
        f"terminal recorded attempts ({metric['rate'] * 100:.1f}%)"
    )


def _format_duration_summary(metric: Mapping[str, Any]) -> str:
    if not metric["available"]:
        return f"unavailable ({metric['reason']})"
    return (
        f"{metric['median']}/{metric['minimum']}/{metric['maximum']} ms "
        f"across {metric['sample_count']} recorded attempts"
    )


def _format_false_species_metric(metric: Mapping[str, Any]) -> str:
    if metric["evaluated_count"] == 0:
        return "0 relevant examples"
    if not metric["available"]:
        return (
            f"unavailable (0/{metric['evaluated_count']} suggestions could be "
            "classified as species or non-species)"
        )
    suffix = (
        f"; {metric['unknown_classification_count']} unclassified"
        if metric["unknown_classification_count"]
        else ""
    )
    return (
        f"{metric['species_suggested_count']}/{metric['classified_count']} "
        f"classified suggestions across {metric['evaluated_count']} relevant "
        f"examples{suffix}"
    )


def _format_distribution(distribution: Mapping[str, int]) -> str:
    if not distribution:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in sorted(distribution.items()))


def _required_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _optional_text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _valid_score(value: Any) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
        and 0 <= float(value) <= 1
    )


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _datetime_key(value: datetime) -> datetime:
    return _as_utc(value)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
