from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any

import pytest

from mockingbird.species import bioclip_adapter
from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_SCORE_KIND,
)
from mockingbird.species.bioclip_evaluation import (
    EvaluationConfig,
    StoredBioClipAttempt,
    StoredReviewLabel,
    StoredSpeciesSuggestion,
    TaxonomyDescriptor,
    evaluate_bioclip_field_truth,
    render_terminal_report,
)
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "evaluate_bioclip_field_truth.py"
)
SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "evaluate_bioclip_field_truth_script",
    SCRIPT_PATH,
)
assert SCRIPT_SPEC is not None
assert SCRIPT_SPEC.loader is not None
EVALUATION_SCRIPT = importlib.util.module_from_spec(SCRIPT_SPEC)
sys.modules[SCRIPT_SPEC.name] = EVALUATION_SCRIPT
SCRIPT_SPEC.loader.exec_module(EVALUATION_SCRIPT)

BASE_TIME = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64
HASH_C = "c" * 64
HASH_D = "d" * 64
HASH_E = "e" * 64


def valid_provenance() -> dict[str, Any]:
    return {
        "adapter_id": BIOCLIP_ADAPTER_ID,
        "adapter_name": "BioCLIP 2",
        "model_name": "BioCLIP 2 local",
        "device": "cpu",
        "open_clip_version": "3.3.0",
        "torch_version": "2.7.0",
        "label_count": 252,
        "labels_sha256": HASH_A,
        "embedding_cache_sha256": HASH_B,
        "model_config_sha256": HASH_C,
        "model_weights_sha256": HASH_D,
        "model_weights_name": "open_clip_model.safetensors",
        "prompt_recipe_id": "prompt-v1",
        "prompt_recipe_sha256": HASH_E,
        "score_kind": BIOCLIP_SCORE_KIND,
        "calibrated": False,
    }


def evidence_region(source: str | None = "megadetector") -> dict[str, Any]:
    value: dict[str, Any] = {
        "score_semantics": BIOCLIP_SCORE_KIND,
        "calibrated": False,
        "model_provenance": valid_provenance(),
    }
    if source is not None:
        value["source"] = source
    return value


def review_label(
    label: str,
    *,
    target_id: str = "visit-1",
    target_type: str = "visit",
    record_id: str = "review-1",
    minute: int = 10,
) -> StoredReviewLabel:
    return StoredReviewLabel(
        id=record_id,
        target_type=target_type,
        target_id=target_id,
        label=label,
        created_at=BASE_TIME + timedelta(minutes=minute),
    )


def alternative(
    rank: int,
    label: str,
    score: float,
    *,
    scientific_name: str | None = None,
) -> dict[str, Any]:
    return {
        "rank": rank,
        "label": label.replace("_", " "),
        "suggested_label": label,
        "common_name": label.replace("_", " "),
        "scientific_name": scientific_name,
        "score": score,
        "score_kind": BIOCLIP_SCORE_KIND,
        "calibrated": False,
    }


def suggestion(
    top_label: str,
    *,
    target_id: str = "visit-1",
    event_id: str = "event-1",
    record_id: str = "suggestion-1",
    minute: int = 5,
    top_score: float = 0.8,
    rank: int = 1,
    alternatives: tuple[dict[str, Any], ...] | None = None,
    source: str | None = "megadetector",
    region: dict[str, Any] | None = None,
    scientific_name: str | None = None,
    status: str = "pending",
    visit_target: bool = True,
) -> StoredSpeciesSuggestion:
    if alternatives is None:
        alternatives = (
            alternative(2, "blue_jay", 0.15, scientific_name="Cyanocitta cristata"),
            alternative(3, "song_sparrow", 0.05, scientific_name="Melospiza melodia"),
        )
    if scientific_name is None and top_label == "northern_cardinal":
        scientific_name = "Cardinalis cardinalis"
    return StoredSpeciesSuggestion(
        id=record_id,
        event_id=event_id,
        visit_id=target_id if visit_target else None,
        adapter_id=BIOCLIP_ADAPTER_ID,
        suggested_label=top_label,
        suggested_scientific_name=scientific_name,
        confidence=top_score,
        rank=rank,
        alternatives=alternatives,
        evidence_region=evidence_region(source) if region is None else region,
        status=status,
        created_at=BASE_TIME + timedelta(minutes=minute),
    )


def taxonomy() -> tuple[TaxonomyDescriptor, ...]:
    return (
        TaxonomyDescriptor("northern_cardinal", "bird", True),
        TaxonomyDescriptor("blue_jay", "bird", True),
        TaxonomyDescriptor("song_sparrow", "bird", True),
        TaxonomyDescriptor("unknown_bird", "unknown", False),
        TaxonomyDescriptor("false_positive", "false_positive", False),
        TaxonomyDescriptor("squirrel", "mammal", True),
        TaxonomyDescriptor("person", "person", False),
        TaxonomyDescriptor("vehicle", "vehicle", False),
    )


def candidate_manifest(
    labels: tuple[str, ...] = (
        "northern_cardinal",
        "blue_jay",
        "unknown_bird",
        "vehicle",
    ),
) -> tuple[dict[str, Any], ...]:
    scores = (0.7, 0.2, 0.08, 0.02)
    ranking = sorted(
        range(len(labels)),
        key=lambda index: (-scores[index], index),
    )
    ranks = {
        candidate_index: rank for rank, candidate_index in enumerate(ranking, start=1)
    }
    return tuple(
        {
            "source_position": index + 1,
            "raw_label": label.replace("_", " "),
            "prompt_input": label.replace("_", " "),
            "normalized_label": label,
            "common_name": label.replace("_", " "),
            "scientific_name": None,
            "rank": ranks[index],
            "score": scores[index],
            "score_kind": BIOCLIP_SCORE_KIND,
            "calibrated": False,
        }
        for index, label in enumerate(labels)
    )


def attempt(
    *,
    record_id: str = "attempt-1",
    target_id: str = "visit-1",
    target_type: str = "visit",
    suggestion_id: str | None = "suggestion-1",
    outcome: str | None = "succeeded",
    duration_ms: int | None = 1250,
    crop_source: str | None = "credible_megadetector_crop",
    manifest: tuple[dict[str, Any], ...] | None = None,
    manifest_complete: bool = True,
    minute: int = 4,
) -> StoredBioClipAttempt:
    values = candidate_manifest() if manifest is None else manifest
    manifest_sha256 = (
        hashlib.sha256(
            "\n".join(str(value["raw_label"]) for value in values).encode("utf-8")
        ).hexdigest()
        if values is not None
        else None
    )
    return StoredBioClipAttempt(
        id=record_id,
        target_type=target_type,
        target_id=target_id,
        adapter_id=BIOCLIP_ADAPTER_ID,
        resulting_species_suggestion_id=suggestion_id,
        started_at=BASE_TIME + timedelta(minutes=minute),
        completed_at=(
            BASE_TIME + timedelta(minutes=minute, seconds=2)
            if outcome is not None
            else None
        ),
        duration_ms=duration_ms,
        timeout_limit_ms=60_000,
        timeout_exceeded=outcome == "timed_out",
        outcome=outcome,
        crop_source=crop_source,
        candidate_manifest=values,
        candidate_set_count=len(values) if values is not None else None,
        candidate_set_sha256=manifest_sha256,
        candidate_set_version="ordered_trimmed_utf8_lf_sha256_v1",
        candidate_manifest_complete=manifest_complete,
        model_provenance={
            "adapter_id": BIOCLIP_ADAPTER_ID,
            "model_name": "BioCLIP 2 local",
            "architecture_id": "ViT-L-14",
            "device": "cpu",
            "open_clip_version": "3.3.0",
            "torch_version": "2.7.0",
            "model_weights_sha256": HASH_D,
        },
        preprocessing={
            "preprocessing_id": "open-clip-default",
            "preprocessing_sha256": HASH_E,
        },
        error_code=None if outcome == "succeeded" else f"bioclip_{outcome}",
        error_stage=None if outcome == "succeeded" else "model_execution",
    )


def field_report(
    labels: list[StoredReviewLabel],
    suggestions: list[StoredSpeciesSuggestion],
    *,
    minimum_examples: int = 30,
    attempts: list[StoredBioClipAttempt] | None = None,
):
    return evaluate_bioclip_field_truth(
        labels,
        suggestions,
        taxonomy(),
        generated_at=BASE_TIME,
        database_identifier="test.sqlite3#safe",
        config=EvaluationConfig(minimum_examples=minimum_examples),
        attempts=attempts or (),
    )


def test_top_1_correct() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
    )

    assert report.counts["eligible_examples"] == 1
    assert report.metrics["top_1"] == {
        "available": True,
        "correct": 1,
        "evaluated": 1,
        "rate": 1.0,
        "unavailable_count": 0,
        "reason": None,
    }
    assert report.evaluated_examples[0]["corrected_rank_in_stored_ranking"] == 1
    assert report.evaluated_examples[0]["top_score"] == pytest.approx(0.8)
    assert report.score_semantics["calibrated"] is False


def test_top_3_correct_when_top_1_is_wrong() -> None:
    ranked = (
        alternative(
            2,
            "northern_cardinal",
            0.3,
            scientific_name="Cardinalis cardinalis",
        ),
        alternative(3, "song_sparrow", 0.1, scientific_name="Melospiza melodia"),
    )
    report = field_report(
        [review_label("northern_cardinal")],
        [
            suggestion(
                "blue_jay", alternatives=ranked, scientific_name="Cyanocitta cristata"
            )
        ],
    )

    assert report.metrics["top_1"]["correct"] == 0
    assert report.metrics["top_3"]["correct"] == 1
    assert report.metrics["top_3"]["evaluated"] == 1
    assert report.evaluated_examples[0]["corrected_rank_in_stored_ranking"] == 2


def test_corrected_label_absent_from_stored_ranking_not_candidate_set() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [
            suggestion(
                "blue_jay",
                alternatives=(
                    alternative(
                        2,
                        "song_sparrow",
                        0.2,
                        scientific_name="Melospiza melodia",
                    ),
                ),
                scientific_name="Cyanocitta cristata",
            )
        ],
    )

    metric = report.metrics["corrected_label_not_present_among_stored_candidates"]
    assert metric["available"] is True
    assert metric["count"] == 1
    assert (
        report.evaluated_examples[0][
            "corrected_label_not_present_among_stored_candidates"
        ]
        is True
    )
    assert "does not claim a complete top-K" in metric["meaning"]
    assert (
        report.metrics["corrected_label_missing_from_candidate_set"]["available"]
        is False
    )


def test_unknown_bird_truth_counts_species_suggestion() -> None:
    report = field_report(
        [review_label("unknown_bird")],
        [suggestion("northern_cardinal")],
    )

    assert report.metrics["unknown_bird_truth"] == {
        "available": True,
        "evaluated_count": 1,
        "classified_count": 1,
        "unknown_classification_count": 0,
        "species_suggested_count": 1,
        "rate": 1.0,
    }


def test_unknown_species_shape_is_not_counted_as_confirmed_non_species() -> None:
    report = field_report(
        [review_label("unknown_bird")],
        [suggestion("mystery_candidate", scientific_name=None)],
    )

    assert report.evaluated_examples[0]["top_suggestion_is_species"] is None
    assert report.metrics["unknown_bird_truth"] == {
        "available": False,
        "evaluated_count": 1,
        "classified_count": 0,
        "unknown_classification_count": 1,
        "species_suggested_count": 0,
        "rate": None,
    }


def test_uninterpretable_stored_candidates_are_not_reported_absent() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [
            suggestion(
                "blue_jay",
                scientific_name="Cyanocitta cristata",
                alternatives=({"rank": 2},),
            )
        ],
    )

    metric = report.metrics["corrected_label_not_present_among_stored_candidates"]
    assert metric["available"] is False
    assert metric["count"] is None
    assert metric["unavailable_count"] == 1
    assert "not present among stored candidates: unavailable" in (
        render_terminal_report(report)
    )


def test_false_positive_truth_counts_species_suggestion() -> None:
    report = field_report(
        [review_label("false_positive")],
        [suggestion("northern_cardinal")],
    )

    assert report.metrics["false_positive_truth"]["evaluated_count"] == 1
    assert report.metrics["false_positive_truth"]["species_suggested_count"] == 1


def test_known_non_bird_truth_counts_species_suggestion() -> None:
    report = field_report(
        [review_label("squirrel")],
        [suggestion("northern_cardinal")],
    )

    assert report.metrics["known_non_bird_truth"]["evaluated_count"] == 1
    assert report.metrics["known_non_bird_truth"]["species_suggested_count"] == 1


def test_crop_source_breakdowns_include_unknown_missing() -> None:
    sources = ("megadetector", "activity", "full_frame", None)
    labels = [
        review_label(
            "northern_cardinal",
            target_id=f"visit-{index}",
            record_id=f"review-{index}",
        )
        for index in range(4)
    ]
    suggestions = [
        suggestion(
            "northern_cardinal",
            target_id=f"visit-{index}",
            event_id=f"event-{index}",
            record_id=f"suggestion-{index}",
            source=source,
        )
        for index, source in enumerate(sources)
    ]

    report = field_report(labels, suggestions)

    assert report.breakdowns["crop_source_distribution"] == {
        "credible_megadetector_crop": 1,
        "measured_activity_crop": 1,
        "full_frame_fallback": 1,
        "unknown_missing": 1,
    }
    assert report.reliability["missing_crop_count"] == 1


def test_history_only_report_keeps_attempt_metrics_explicitly_incomplete() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
    )

    assert report.attempt_metrics["counts"]["total_manual_attempts"] == 0
    assert report.attempt_metrics["suggestions_without_linked_attempts"]["count"] == 1
    assert report.attempt_metrics["historical_coverage"]["incomplete"] is True
    assert report.reliability["runtime_ms"]["available"] is False
    assert report.reliability["runtime_ms"]["sample_count"] == 0
    assert report.reliability["timeout_runs"]["count"] == 0
    assert report.reliability["timeout_runs"]["available"] is True
    assert report.reliability["failed_runs"]["count"] == 0
    assert report.reliability["failed_runs"]["available"] is True


def test_attempt_metrics_count_every_terminal_outcome_and_duration() -> None:
    attempts = [
        attempt(record_id="success", duration_ms=1000),
        attempt(
            record_id="no-result",
            outcome="no_result",
            suggestion_id=None,
            duration_ms=400,
        ),
        attempt(
            record_id="timeout",
            outcome="timed_out",
            suggestion_id=None,
            duration_ms=600,
        ),
        attempt(
            record_id="failure",
            outcome="failed",
            suggestion_id=None,
            duration_ms=500,
        ),
        attempt(
            record_id="unsupported",
            outcome="unsupported",
            suggestion_id=None,
            duration_ms=None,
        ),
        attempt(
            record_id="cancelled",
            outcome="cancelled",
            suggestion_id=None,
            duration_ms=50,
        ),
        attempt(
            record_id="incomplete",
            outcome=None,
            suggestion_id=None,
            duration_ms=None,
        ),
    ]

    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=attempts,
    )

    metrics = report.attempt_metrics
    assert metrics["counts"] == {
        "total_manual_attempts": 7,
        "terminal_attempts": 6,
        "incomplete_attempts": 1,
        "outcomes": {
            "succeeded": 1,
            "no_result": 1,
            "timed_out": 1,
            "failed": 1,
            "unsupported": 1,
            "cancelled": 1,
        },
        "invalid_target_records": 0,
    }
    assert metrics["success_rate"]["denominator"] == "terminal_recorded_attempts"
    assert metrics["success_rate"]["rate"] == pytest.approx(1 / 6)
    assert metrics["duration_ms"]["sample_count"] == 5
    assert metrics["duration_ms"]["median"] == 500
    assert metrics["duration_ms"]["minimum"] == 50
    assert metrics["duration_ms"]["maximum"] == 1000
    assert metrics["duration_ms"]["unavailable_count"] == 1
    assert metrics["repeated_attempts"] == {
        "attempts_beyond_first_per_target": 6,
        "targets_with_multiple_attempts": 1,
    }
    assert metrics["attempts_without_suggestions"]["count"] == 6
    assert report.metrics["top_1"]["correct"] == 1


def test_failed_attempt_does_not_displace_successful_suggestion_accuracy() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=[
            attempt(record_id="success", minute=4),
            attempt(
                record_id="later-failure",
                outcome="failed",
                suggestion_id=None,
                minute=20,
            ),
        ],
    )

    assert report.metrics["top_1"]["correct"] == 1
    assert report.metrics["top_3"]["correct"] == 1
    assert report.evaluated_examples[0]["attempt_id"] == "success"
    assert report.attempt_metrics["counts"]["outcomes"]["failed"] == 1


def test_complete_candidate_bank_metrics_use_attempt_link_and_taxonomy() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=[attempt()],
    )

    candidate_metrics = report.attempt_metrics["candidate_banks"]
    assert candidate_metrics["complete_manifest_attempts"] == 1
    assert candidate_metrics["size_distribution"] == {"4": 1}
    assert candidate_metrics["fingerprints"] == [
        {
            "sha256": attempt().candidate_set_sha256,
            "attempt_count": 1,
        }
    ]
    assert candidate_metrics["version_distribution"] == {
        "ordered_trimmed_utf8_lf_sha256_v1": 1
    }
    assert candidate_metrics["variants"] == [
        {
            "sha256": attempt().candidate_set_sha256,
            "version": "ordered_trimmed_utf8_lf_sha256_v1",
            "candidate_count": 4,
            "attempt_count": 1,
        }
    ]
    assert candidate_metrics["unknown_bird_presence"]["attempt_count"] == 1
    assert candidate_metrics["taxonomy_backed_non_bird_escape_presence"][
        "label_distribution"
    ] == {"vehicle": 1}
    assert candidate_metrics["corrected_label_absent"]["count"] == 0
    assert candidate_metrics["top_3_support"]["fully_supported"] is True
    assert report.metrics["corrected_label_missing_from_candidate_set"] == {
        "available": True,
        "count": 0,
        "evaluated_count": 1,
        "unavailable_count": 0,
        "reason": None,
    }


def test_complete_candidate_bank_detects_corrected_label_absence() -> None:
    manifest = candidate_manifest(
        ("blue_jay", "song_sparrow", "unknown_bird", "person")
    )
    report = field_report(
        [review_label("northern_cardinal")],
        [
            suggestion(
                "blue_jay",
                scientific_name="Cyanocitta cristata",
            )
        ],
        attempts=[attempt(manifest=manifest)],
    )

    metric = report.metrics["corrected_label_missing_from_candidate_set"]
    assert metric["available"] is True
    assert metric["count"] == 1
    assert (
        report.evaluated_examples[0][
            "corrected_label_missing_from_complete_candidate_bank"
        ]
        is True
    )
    attempt_metric = report.attempt_metrics["candidate_banks"]["corrected_label_absent"]
    assert attempt_metric["count"] == 1
    assert attempt_metric["details"] == [
        {
            "attempt_id": "attempt-1",
            "target_type": "visit",
            "target_id": "visit-1",
        }
    ]


def test_incomplete_manifest_remains_unavailable_without_reconstruction() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=[attempt(manifest_complete=False)],
    )

    candidate_metrics = report.attempt_metrics["candidate_banks"]
    assert candidate_metrics["complete_manifest_attempts"] == 0
    assert candidate_metrics["incomplete_manifest_attempts"] == 1
    assert (
        report.metrics["corrected_label_missing_from_candidate_set"]["available"]
        is False
    )
    assert (
        report.evaluated_examples[0]["complete_candidate_manifest_available"] is False
    )


def test_complete_manifest_flag_does_not_override_fingerprint_mismatch() -> None:
    invalid_attempt = replace(
        attempt(),
        candidate_set_sha256=HASH_A,
    )
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=[invalid_attempt],
    )

    candidate_metrics = report.attempt_metrics["candidate_banks"]
    assert candidate_metrics["complete_manifest_attempts"] == 0
    assert candidate_metrics["invalid_complete_manifest_attempts"] == 1
    assert (
        report.evaluated_examples[0]["complete_candidate_manifest_available"] is False
    )


def test_missing_primary_ranking_and_provenance_are_excluded() -> None:
    labels = [
        review_label("northern_cardinal", target_id="visit-rank"),
        review_label("northern_cardinal", target_id="visit-provenance"),
    ]
    missing_provenance_region = {
        "source": "activity",
        "score_semantics": BIOCLIP_SCORE_KIND,
        "calibrated": False,
    }
    suggestions = [
        suggestion(
            "northern_cardinal",
            target_id="visit-rank",
            record_id="suggestion-rank",
            rank=2,
        ),
        suggestion(
            "northern_cardinal",
            target_id="visit-provenance",
            record_id="suggestion-provenance",
            region=missing_provenance_region,
        ),
    ]

    report = field_report(labels, suggestions)

    assert report.counts["eligible_examples"] == 0
    assert report.counts["excluded_examples"] == 2
    assert report.exclusions["reason_counts"] == {
        "missing_provenance": 1,
        "missing_ranking": 1,
    }
    assert report.reliability["missing_provenance_count"] == 1


def test_latest_suggestion_for_exact_target_is_selected_without_rank_merging() -> None:
    labels = [
        review_label("northern_cardinal", target_id="visit-shared"),
        review_label(
            "northern_cardinal",
            target_id="event-parent",
            target_type="event",
            record_id="review-event",
        ),
    ]
    suggestions = [
        suggestion(
            "northern_cardinal",
            target_id="visit-shared",
            event_id="event-parent",
            record_id="suggestion-old",
            minute=3,
        ),
        suggestion(
            "blue_jay",
            target_id="visit-shared",
            event_id="event-parent",
            record_id="suggestion-new",
            minute=6,
            alternatives=(
                alternative(
                    2,
                    "northern_cardinal",
                    0.2,
                    scientific_name="Cardinalis cardinalis",
                ),
            ),
            scientific_name="Cyanocitta cristata",
        ),
    ]

    report = field_report(labels, suggestions)

    assert report.counts["eligible_examples"] == 1
    assert report.counts["excluded_examples"] == 1
    assert report.evaluated_examples[0]["target_id"] == "visit-shared"
    assert report.evaluated_examples[0]["suggestion_id"] == "suggestion-new"
    assert report.metrics["top_1"]["correct"] == 0
    assert report.exclusions["reason_counts"]["no_bioclip_suggestion"] == 1


def test_latest_review_label_wins_deterministically() -> None:
    labels = [
        review_label(
            "unknown_bird",
            record_id="review-old",
            minute=7,
        ),
        review_label(
            "northern_cardinal",
            record_id="review-new",
            minute=9,
        ),
    ]

    report = field_report(labels, [suggestion("northern_cardinal")])

    assert report.breakdowns["review_label_distribution"] == {"northern_cardinal": 1}
    assert report.evaluated_examples[0]["review_label_id"] == "review-new"
    assert report.metrics["top_1"]["correct"] == 1


def test_small_sample_warning_blocks_accuracy_or_selection_claim() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        minimum_examples=30,
    )

    assert report.small_sample["threshold_met"] is False
    assert report.small_sample["descriptive_only"] is True
    assert "DESCRIPTIVE ONLY" in report.small_sample["warning"]
    assert "model selection is not justified" in report.small_sample["warning"]


def test_report_json_serialization_is_safe_and_explicit() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("blue_jay", scientific_name="Cyanocitta cristata")],
    )

    payload = json.loads(report.to_json())

    assert payload["schema_version"] == 2
    assert payload["database_identifier"] == "test.sqlite3#safe"
    assert payload["safety"]["read_only_evaluation"] is True
    assert payload["safety"]["inference_invoked"] is False
    assert payload["score_semantics"]["is_probability"] is False
    assert payload["mistake_examples"][0]["uncalibrated_score"] == pytest.approx(0.8)
    assert "C:\\" not in report.to_json()


def test_attempt_report_does_not_emit_paths_urls_or_error_details() -> None:
    unsafe_attempt = replace(
        attempt(),
        model_provenance={
            "adapter_id": BIOCLIP_ADAPTER_ID,
            "model_name": r"C:\private\models\weights.bin",
            "device": "cpu",
            "provider_url": "rtsp://user:password@camera.local/stream",
        },
        error_code="safe_code",
        error_stage="inference",
    )

    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
        attempts=[unsafe_attempt],
    )
    serialized = report.to_json()

    assert "C:\\private" not in serialized
    assert "rtsp://" not in serialized
    assert "password" not in serialized
    assert "provider_url" not in serialized


def test_cli_json_run_preserves_database_and_operational_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database_path = _create_evaluation_database(tmp_path)
    output_path = tmp_path / "data" / "evaluations" / "field-truth.json"
    before_bytes = database_path.read_bytes()
    before_tables = _database_snapshot(database_path)
    monkeypatch.setattr(EVALUATION_SCRIPT, "PROJECT_ROOT", tmp_path)

    result = EVALUATION_SCRIPT.main(
        [
            "--database-url",
            "sqlite:///data/field.sqlite3",
            "--minimum-examples",
            "30",
            "--json-output",
            "data/evaluations/field-truth.json",
        ]
    )

    assert result == 0
    assert database_path.read_bytes() == before_bytes
    assert _database_snapshot(database_path) == before_tables
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["counts"]["eligible_examples"] == 1
    assert payload["counts"]["excluded_examples"] == 0
    assert payload["attempt_metrics"]["counts"]["total_manual_attempts"] == 1
    assert (
        payload["attempt_metrics"]["candidate_banks"]["complete_manifest_attempts"] == 1
    )
    assert payload["safety"]["product_or_operational_state_modified"] is False
    assert str(tmp_path) not in json.dumps(payload)
    terminal_output = capsys.readouterr().out
    assert "DESCRIPTIVE ONLY" in terminal_output
    assert "Top-1: 1/1" in terminal_output


def test_evaluation_never_calls_bioclip_inference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = _create_evaluation_database(tmp_path)
    monkeypatch.setattr(EVALUATION_SCRIPT, "PROJECT_ROOT", tmp_path)
    calls: list[str] = []

    def fail_if_called(*args: Any, **kwargs: Any) -> Any:
        calls.append("inference")
        raise AssertionError("Evaluation must not invoke BioCLIP.")

    monkeypatch.setattr(
        bioclip_adapter,
        "run_bioclip_on_image",
        fail_if_called,
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "run_bioclip_from_image_loader",
        fail_if_called,
    )

    report = EVALUATION_SCRIPT.build_report(
        database_path,
        minimum_examples=30,
        generated_at=BASE_TIME,
    )

    assert calls == []
    assert report.safety["inference_invoked"] is False


def test_read_only_evaluator_does_not_initialize_or_migrate_old_schema(
    tmp_path: Path,
) -> None:
    database_path = _create_evaluation_database(tmp_path)
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("DROP TABLE bioclip_identification_attempts")
        connection.execute(
            "UPDATE mockingbird_schema SET version = ? WHERE singleton_id = 1",
            (CURRENT_DATABASE_SCHEMA_VERSION - 1,),
        )
        connection.commit()
    finally:
        connection.close()
    before = _database_snapshot(database_path)

    with pytest.raises(
        EVALUATION_SCRIPT.EvaluationCommandError,
        match="will not migrate",
    ):
        EVALUATION_SCRIPT.load_evaluation_records(database_path)

    assert _database_snapshot(database_path) == before
    connection = sqlite3.connect(database_path)
    try:
        attempt_table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'bioclip_identification_attempts'
            """
        ).fetchone()
        version = connection.execute(
            "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
        ).fetchone()
    finally:
        connection.close()
    assert attempt_table is None
    assert version == (CURRENT_DATABASE_SCHEMA_VERSION - 1,)


def _create_evaluation_database(tmp_path: Path) -> Path:
    data_root = tmp_path / "data"
    data_root.mkdir()
    database_path = data_root / "field.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE mockingbird_schema (
                singleton_id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL
            );
            CREATE TABLE review_labels (
                id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                label TEXT NOT NULL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE species_suggestions (
                id TEXT PRIMARY KEY,
                source_id TEXT,
                stream_id TEXT,
                event_id TEXT,
                visit_id TEXT,
                media_asset_id TEXT,
                motion_evidence_id TEXT,
                adapter_id TEXT NOT NULL,
                adapter_name TEXT NOT NULL,
                suggested_label TEXT NOT NULL,
                suggested_common_name TEXT,
                suggested_scientific_name TEXT,
                confidence REAL,
                rank INTEGER NOT NULL,
                alternatives_json TEXT NOT NULL,
                evidence_region_json TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                notes TEXT
            );
            CREATE TABLE bioclip_identification_attempts (
                id TEXT PRIMARY KEY,
                target_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                event_id TEXT,
                visit_id TEXT,
                media_asset_id TEXT NOT NULL,
                source_id TEXT,
                stream_id TEXT,
                zone_id TEXT,
                motion_evidence_id TEXT,
                detection_proposal_id TEXT,
                resulting_species_suggestion_id TEXT,
                adapter_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_ms INTEGER,
                timeout_limit_ms INTEGER NOT NULL,
                timeout_exceeded INTEGER NOT NULL,
                outcome TEXT,
                crop_source TEXT,
                crop_provenance_json TEXT,
                model_provenance_json TEXT,
                preprocessing_json TEXT,
                candidate_manifest_json TEXT,
                candidate_set_count INTEGER,
                candidate_set_sha256 TEXT,
                candidate_set_version TEXT,
                candidate_manifest_complete INTEGER NOT NULL,
                error_code TEXT,
                error_stage TEXT,
                error_detail TEXT,
                provenance_schema_version INTEGER NOT NULL
            );
            CREATE TABLE taxonomy_labels (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                display_name TEXT NOT NULL,
                category TEXT NOT NULL,
                scientific_name TEXT,
                aliases_json TEXT NOT NULL,
                is_species INTEGER NOT NULL,
                is_reviewable INTEGER NOT NULL,
                sort_order INTEGER
            );
            CREATE TABLE events (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE visits (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE detection_runs (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE detection_proposals (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE dataset_exports (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE media_assets (id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE stream_monitoring_policies (
                stream_id TEXT PRIMARY KEY,
                state TEXT NOT NULL
            );
            CREATE TABLE stream_runtime_checkpoints (
                stream_id TEXT PRIMARY KEY,
                state TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO mockingbird_schema(singleton_id, version) VALUES (1, ?)",
            (CURRENT_DATABASE_SCHEMA_VERSION,),
        )
        connection.execute(
            """
            INSERT INTO review_labels(
                id, target_type, target_id, label, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "review-1",
                "visit",
                "visit-1",
                "northern_cardinal",
                None,
                (BASE_TIME + timedelta(minutes=10)).isoformat(),
            ),
        )
        stored_suggestion = suggestion("northern_cardinal")
        connection.execute(
            """
            INSERT INTO species_suggestions(
                id,
                event_id,
                visit_id,
                adapter_id,
                adapter_name,
                suggested_label,
                suggested_scientific_name,
                confidence,
                rank,
                alternatives_json,
                evidence_region_json,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stored_suggestion.id,
                stored_suggestion.event_id,
                stored_suggestion.visit_id,
                stored_suggestion.adapter_id,
                "BioCLIP 2",
                stored_suggestion.suggested_label,
                stored_suggestion.suggested_scientific_name,
                stored_suggestion.confidence,
                stored_suggestion.rank,
                json.dumps(list(stored_suggestion.alternatives or ())),
                json.dumps(stored_suggestion.evidence_region),
                stored_suggestion.status,
                stored_suggestion.created_at.isoformat(),
            ),
        )
        stored_attempt = attempt()
        connection.execute(
            """
            INSERT INTO bioclip_identification_attempts(
                id,
                target_type,
                target_id,
                event_id,
                visit_id,
                media_asset_id,
                resulting_species_suggestion_id,
                adapter_id,
                started_at,
                completed_at,
                duration_ms,
                timeout_limit_ms,
                timeout_exceeded,
                outcome,
                crop_source,
                model_provenance_json,
                preprocessing_json,
                candidate_manifest_json,
                candidate_set_count,
                candidate_set_sha256,
                candidate_set_version,
                candidate_manifest_complete,
                provenance_schema_version
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                stored_attempt.id,
                stored_attempt.target_type,
                stored_attempt.target_id,
                "event-1",
                stored_attempt.target_id,
                "media-1",
                stored_attempt.resulting_species_suggestion_id,
                stored_attempt.adapter_id,
                stored_attempt.started_at.isoformat(),
                (
                    stored_attempt.completed_at.isoformat()
                    if stored_attempt.completed_at is not None
                    else None
                ),
                stored_attempt.duration_ms,
                stored_attempt.timeout_limit_ms,
                stored_attempt.timeout_exceeded,
                stored_attempt.outcome,
                stored_attempt.crop_source,
                json.dumps(stored_attempt.model_provenance),
                json.dumps(stored_attempt.preprocessing),
                json.dumps(list(stored_attempt.candidate_manifest or ())),
                stored_attempt.candidate_set_count,
                stored_attempt.candidate_set_sha256,
                stored_attempt.candidate_set_version,
                stored_attempt.candidate_manifest_complete,
                1,
            ),
        )
        for index, item in enumerate(taxonomy()):
            connection.execute(
                """
                INSERT INTO taxonomy_labels(
                    id,
                    label,
                    display_name,
                    category,
                    scientific_name,
                    aliases_json,
                    is_species,
                    is_reviewable,
                    sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"taxonomy-{index}",
                    item.label,
                    item.label.replace("_", " "),
                    item.category,
                    None,
                    "[]",
                    item.is_species,
                    True,
                    index,
                ),
            )
        operational_tables = (
            "events",
            "visits",
            "detection_runs",
            "detection_proposals",
            "dataset_exports",
            "media_assets",
        )
        for table in operational_tables:
            connection.execute(
                f"INSERT INTO {table}(id, state) VALUES (?, ?)",
                (f"{table}-1", "unchanged"),
            )
        connection.execute(
            """
            INSERT INTO stream_monitoring_policies(stream_id, state)
            VALUES ('stream-1', 'off')
            """
        )
        connection.execute(
            """
            INSERT INTO stream_runtime_checkpoints(stream_id, state)
            VALUES ('stream-1', 'stopped')
            """
        )
        connection.commit()
    finally:
        connection.close()
    return database_path


def _database_snapshot(database_path: Path) -> dict[str, list[tuple[Any, ...]]]:
    connection = sqlite3.connect(database_path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            )
        ]
        return {
            table: list(connection.execute(f"SELECT * FROM {table} ORDER BY 1"))
            for table in tables
        }
    finally:
        connection.close()
