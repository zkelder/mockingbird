from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    StoredReviewLabel,
    StoredSpeciesSuggestion,
    TaxonomyDescriptor,
    evaluate_bioclip_field_truth,
    render_terminal_report,
)
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "evaluate_bioclip_field_truth.py"
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


def field_report(
    labels: list[StoredReviewLabel],
    suggestions: list[StoredSpeciesSuggestion],
    *,
    minimum_examples: int = 30,
):
    return evaluate_bioclip_field_truth(
        labels,
        suggestions,
        taxonomy(),
        generated_at=BASE_TIME,
        database_identifier="test.sqlite3#safe",
        config=EvaluationConfig(minimum_examples=minimum_examples),
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
        [suggestion("blue_jay", alternatives=ranked, scientific_name="Cyanocitta cristata")],
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

    metric = report.metrics[
        "corrected_label_not_present_among_stored_candidates"
    ]
    assert metric["available"] is True
    assert metric["count"] == 1
    assert report.evaluated_examples[0][
        "corrected_label_not_present_among_stored_candidates"
    ] is True
    assert "does not claim a complete top-K" in metric["meaning"]
    assert report.metrics["corrected_label_missing_from_candidate_set"][
        "available"
    ] is False


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

    metric = report.metrics[
        "corrected_label_not_present_among_stored_candidates"
    ]
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


def test_unstored_runtime_timeout_and_failure_metrics_are_unavailable() -> None:
    report = field_report(
        [review_label("northern_cardinal")],
        [suggestion("northern_cardinal")],
    )

    assert report.reliability["runtime_ms"] == {
        "available": False,
        "sample_count": None,
        "median": None,
        "minimum": None,
        "maximum": None,
        "reason": "Successful suggestions do not persist inference duration.",
    }
    assert report.reliability["timeout_runs"]["count"] is None
    assert report.reliability["timeout_runs"]["available"] is False
    assert report.reliability["failed_runs"]["count"] is None
    assert report.reliability["failed_runs"]["available"] is False


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

    assert report.breakdowns["review_label_distribution"] == {
        "northern_cardinal": 1
    }
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

    assert payload["schema_version"] == 1
    assert payload["database_identifier"] == "test.sqlite3#safe"
    assert payload["safety"]["read_only_evaluation"] is True
    assert payload["safety"]["inference_invoked"] is False
    assert payload["score_semantics"]["is_probability"] is False
    assert payload["mistake_examples"][0]["uncalibrated_score"] == pytest.approx(0.8)
    assert "C:\\" not in report.to_json()


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
