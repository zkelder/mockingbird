"""Detection Quality Accounting v1 reviewed-truth / evaluation-set
governance (see docs/detection-quality-accounting-contract.md)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mockingbird.observation.evaluation_governance import (
    EvaluationExample,
    EvaluationGovernanceError,
    EvaluationManifest,
    load_evaluation_manifest,
    require_evaluation_metric_eligible,
)


def test_reviewed_truth_requires_a_named_reviewer() -> None:
    """The one rule this module exists to enforce: nothing may claim
    `reviewed_truth` without saying who/what reviewed it -- an agent's own
    visual inspection is honestly `diagnostic_only`, never this."""
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_reviewer_identity"):
        EvaluationExample(
            example_id="visit-1", status="reviewed_truth", source="test", description="test example",
        )


def test_diagnostic_only_does_not_require_a_reviewer() -> None:
    example = EvaluationExample(
        example_id="visit-observation-candidate-001",
        status="diagnostic_only",
        source="agent-visual-inspection-2026-08-10",
        description="box on bare tree bark; no bird",
    )
    assert example.training_eligible is False
    assert example.evaluation_metric_eligible is False


def test_reviewed_truth_example_is_training_and_metric_eligible() -> None:
    example = EvaluationExample(
        example_id="session-04-visit-12", status="reviewed_truth", source="stage6.17-reviewed-visit-truth",
        description="reviewed real Visit", reviewed_by="human-reviewer-session-04",
    )
    assert example.training_eligible is True
    assert example.evaluation_metric_eligible is True


def test_manifest_rejects_duplicate_example_ids() -> None:
    example = EvaluationExample(
        example_id="dup", status="diagnostic_only", source="test", description="test",
    )
    with pytest.raises(EvaluationGovernanceError, match="duplicate_evaluation_example_id"):
        EvaluationManifest(schema_version=1, examples=(example, example))


def test_require_evaluation_metric_eligible_drops_diagnostic_and_unreviewed() -> None:
    reviewed = EvaluationExample(
        example_id="r1", status="reviewed_truth", source="test", description="reviewed", reviewed_by="human",
    )
    diagnostic = EvaluationExample(example_id="d1", status="diagnostic_only", source="test", description="diagnostic")
    unreviewed = EvaluationExample(example_id="u1", status="auto_generated_unreviewed", source="test", description="raw")

    eligible = require_evaluation_metric_eligible((reviewed, diagnostic, unreviewed))

    assert eligible == (reviewed,)


def test_manifest_counts_by_status() -> None:
    manifest = EvaluationManifest(
        schema_version=1,
        examples=(
            EvaluationExample(example_id="r1", status="reviewed_truth", source="s", description="d", reviewed_by="human"),
            EvaluationExample(example_id="r2", status="reviewed_truth", source="s", description="d", reviewed_by="human"),
            EvaluationExample(example_id="d1", status="diagnostic_only", source="s", description="d"),
        ),
    )
    assert manifest.counts_by_status == {"reviewed_truth": 2, "diagnostic_only": 1, "auto_generated_unreviewed": 0}
    assert len(manifest.reviewed_truth) == 2
    assert len(manifest.diagnostic_only) == 1


def test_load_evaluation_manifest_round_trips(tmp_path: Path) -> None:
    payload = {
        "schema_version": 1,
        "examples": [
            {
                "example_id": "visit-observation-candidate-001",
                "status": "diagnostic_only",
                "source": "agent-visual-inspection-2026-08-10",
                "description": "box on bare tree bark; no bird",
                "provenance_ref": "visit-episode:e6f2e2b554cc492ad1490058",
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = load_evaluation_manifest(manifest_path)

    assert manifest.schema_version == 1
    assert len(manifest.examples) == 1
    assert manifest.examples[0].status == "diagnostic_only"
    assert manifest.examples[0].provenance_ref == "visit-episode:e6f2e2b554cc492ad1490058"


def test_load_evaluation_manifest_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EvaluationGovernanceError, match="invalid_evaluation_manifest_path"):
        load_evaluation_manifest(tmp_path / "missing.json")


def test_load_evaluation_manifest_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(EvaluationGovernanceError, match="invalid_evaluation_manifest_json"):
        load_evaluation_manifest(path)


def test_load_evaluation_manifest_rejects_example_missing_reviewer_when_claiming_reviewed_truth(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": 1,
        "examples": [
            {"example_id": "x", "status": "reviewed_truth", "source": "s", "description": "d"},
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_reviewer_identity"):
        load_evaluation_manifest(path)
