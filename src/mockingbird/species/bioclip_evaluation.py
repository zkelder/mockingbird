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
from typing import Any, Mapping

from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_SCORE_KIND,
)

REPORT_SCHEMA_VERSION = 1
CROP_BREAKDOWN_KEYS = (
    "credible_megadetector_crop",
    "measured_activity_crop",
    "full_frame_fallback",
    "unknown_missing",
)
_NON_BIRD_CATEGORIES = {"mammal", "pet", "person", "vehicle", "object"}


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
    unreviewed_bioclip_targets = sorted(
        set(latest_suggestions).difference(final_truth)
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
                "available": False,
                "count": None,
                "reason": (
                    "Historical suggestions store a candidate-bank fingerprint and "
                    "top-K ranking, not complete candidate-label membership."
                ),
            },
            "unknown_bird_truth": _false_species_metric(unknown_bird_examples),
            "false_positive_truth": _false_species_metric(false_positive_examples),
            "known_non_bird_truth": _false_species_metric(known_non_bird_examples),
            "top_1_mistake_count": len(all_mistakes),
        },
        reliability={
            "runtime_ms": {
                "available": False,
                "sample_count": None,
                "median": None,
                "minimum": None,
                "maximum": None,
                "reason": "Successful suggestions do not persist inference duration.",
            },
            "timeout_runs": {
                "available": False,
                "count": None,
                "reason": "Timeout attempts do not persist a durable run record.",
            },
            "failed_runs": {
                "available": False,
                "count": None,
                "reason": "Failed attempts do not persist a durable run record.",
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
            "candidate_prompt_variants": _sorted_variants(
                candidate_prompt_variants
            ),
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
                "metric": "complete_candidate_set_membership",
                "smallest_future_provenance_addition": (
                    "Persist immutable normalized candidate membership keyed by "
                    "labels_sha256."
                ),
            },
            {
                "metric": "successful_inference_runtime",
                "smallest_future_provenance_addition": (
                    "Persist bounded run_duration_ms with successful suggestion "
                    "provenance."
                ),
            },
            {
                "metric": "timeout_and_failed_run_counts",
                "smallest_future_provenance_addition": (
                    "Persist append-only evidence-only attempt outcomes; never write "
                    "review truth from them."
                ),
            },
        ],
    )


def render_terminal_report(report: BioClipFieldTruthReport) -> str:
    """Render a concise human-readable report without hiding unavailable data."""

    counts = report.counts
    metrics = report.metrics
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
        "- Corrected label absent from full candidate set: unavailable",
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
        "- Runtime median/min/max: unavailable (not persisted)",
        "- Timeout count: unavailable (attempts are not persisted)",
        "- Failed-run count: unavailable (attempts are not persisted)",
        f"- Missing provenance: {reliability['missing_provenance_count']}",
        f"- Missing crop: {reliability['missing_crop_count']}",
        "- Exclusions: "
        + _format_distribution(report.exclusions["reason_counts"]),
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
            key: max(values, key=lambda value: (_datetime_key(value.created_at), value.id))
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
            key: max(values, key=lambda value: (_datetime_key(value.created_at), value.id))
            for key, values in grouped.items()
        },
        {
            "bioclip_suggestions_inspected": inspected,
            "unscoped_bioclip_suggestions": unscoped,
        },
    )


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
    if (
        suggestion.rank != 1
        or not label
        or not _valid_score(suggestion.confidence)
    ):
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
        f"labels-{str(provenance['labels_sha256'])[:12]}"
        f"-n{provenance['label_count']}"
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
            species_suggested_count / classified_count
            if classified_count
            else None
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
        "corrected_rank_in_stored_ranking": example[
            "corrected_rank_in_stored_ranking"
        ],
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
