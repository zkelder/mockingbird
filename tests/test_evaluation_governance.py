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


# =============================================================================
# Visit Continuity / Provisional Admission Fix v1, Part 7 audit: an agent's
# own visual-inspection disclosure (the real, established convention this
# codebase already uses -- see `DIAGNOSTIC_EXAMPLES` in
# scripts/run_detection_quality_accounting.py and the real `ReviewLabel.
# notes` text the 2026-08-10 fresh cohort wrote) must never be able to
# masquerade as `reviewed_truth` even if a future manifest script
# carelessly copies it into `reviewed_by`/`source`. Defense in depth only --
# see the module docstring's own note that this is not the only safeguard.
# =============================================================================


def test_reviewed_truth_rejects_agent_disclosed_reviewer_text() -> None:
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        EvaluationExample(
            example_id="visit-observation-candidate-004",
            status="reviewed_truth",
            source="fresh-cohort-2026-08-10",
            description="ambiguous: real bird present, box off-target",
            reviewed_by="Claude (agent visual inspection, not independently human-confirmed)",
        )


def test_reviewed_truth_rejects_the_real_disclosure_text_the_fresh_cohort_actually_wrote() -> None:
    """The exact prose the 2026-08-10 fresh cohort recorded in the real
    product's `ReviewLabel.notes` (see FINAL-REPORT.md Sec 6) must be
    caught if it were ever copied into a manifest's `reviewed_by` field."""
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        EvaluationExample(
            example_id="visit-observation-candidate-005",
            status="reviewed_truth",
            source="fresh-cohort-2026-08-10",
            description="ambiguous: real bird present, box off-target, track fragmentation",
            reviewed_by="[AGENT VISUAL REVIEW - not independently human-confirmed] full reasoning follows...",
        )


def test_reviewed_truth_rejects_agent_disclosed_source_even_with_innocuous_reviewer_text() -> None:
    """The established convention already puts the disclosure in `source`
    (`DIAGNOSTIC_EXAMPLES`'s own `"agent-visual-inspection-2026-08-10"`) --
    the check must cover that field too, not only `reviewed_by`."""
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        EvaluationExample(
            example_id="visit-observation-candidate-006",
            status="reviewed_truth",
            source="agent-visual-inspection-2026-08-10",
            description="feeder hardware false positive",
            reviewed_by="reviewer",
        )


def test_reviewed_truth_marker_check_is_case_insensitive() -> None:
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        EvaluationExample(
            example_id="x", status="reviewed_truth", source="s", description="d",
            reviewed_by="Reviewed by an AGENT visual pass",
        )


def test_reviewed_truth_accepts_genuinely_human_reviewer_text() -> None:
    """Sanity: the real, already-accepted Stage 6.17 reviewer-identity
    convention must not be caught by this defense-in-depth check."""
    example = EvaluationExample(
        example_id="session-04-visit-12",
        status="reviewed_truth",
        source="stage6.17-reviewed-visit-truth:session-04",
        description="reviewed real Visit",
        reviewed_by="temporal-review capture + Stage 6.17 reviewed-Visit-truth manifest",
    )
    assert example.training_eligible is True


def test_diagnostic_only_may_freely_disclose_agent_review() -> None:
    """The marker check only ever applies to a `reviewed_truth` claim --
    `diagnostic_only` (the correct status for an agent's own visual
    inspection) is exactly where this disclosure belongs and must never be
    rejected."""
    example = EvaluationExample(
        example_id="visit-observation-candidate-004",
        status="diagnostic_only",
        source="agent-visual-inspection-2026-08-10",
        description="ambiguous: real bird present, box off-target",
        reviewed_by="Claude (agent visual inspection, not independently human-confirmed)",
    )
    assert example.training_eligible is False
    assert example.evaluation_metric_eligible is False


def test_load_evaluation_manifest_rejects_agent_disclosed_reviewer_claiming_reviewed_truth(
    tmp_path: Path,
) -> None:
    payload = {
        "schema_version": 1,
        "examples": [
            {
                "example_id": "x", "status": "reviewed_truth", "source": "s", "description": "d",
                "reviewed_by": "agent visual review",
            },
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(EvaluationGovernanceError, match="reviewed_truth_requires_human_reviewer"):
        load_evaluation_manifest(path)
