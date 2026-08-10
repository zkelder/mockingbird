#!/usr/bin/env python3
"""Detection Quality Accounting v1: run the SHADOW admission-policy sweep
against real, already-reviewed historical field data (see
docs/detection-quality-accounting-contract.md).

This reuses the exact same hardware-free "replay already-recorded real-CUDA
detection/tracker facts" methodology `data/field-acceptance/
2026-08-07-stage6.17-reviewed-visit-truth/rescore_visit_truth.py` already
established: no live camera, no CUDA/ONNX Runtime session, and no product
database are opened here. It differs from that script only in what it does
with the reconstructed facts -- instead of re-scoring the *old*, per-
generation Stage 6.17 matcher, it runs the *current* Stage 6.19 tracklet/
episode assembler (`visit_episode_assembler.build_tracklets`/
`assemble_visit_episodes`, now carrying `ConfidenceEvidenceSummary`) and then
the unchanged reviewed-Visit-truth matcher (`replay._match`), producing a
governed evaluation manifest (`evaluation_governance.EvaluationManifest`)
plus a SHADOW admission-policy comparison report
(`admission_policy.evaluate_policy_sweep`).

Reviewed truth eligibility is real, not asserted: every "reviewed_true_
positive"/"reviewed_false_positive" example here comes from one of the four
already-reviewed historical field sessions (attempt-2, attempt-3, session-03,
session-04) that a human reviewer's own `temporal-review-replay-manifest.json`
`visits`/`appearances` already ground -- never from an agent's own visual
inspection. The three 2026-08-10 false-candidate examples are registered
separately as `diagnostic_only`, exactly as the milestone that added this
script requires; they carry no recoverable per-detection confidence (the
confidence-lineage contract this script depends on postdates when they were
captured, and their packaged-product database is not part of this checkout --
see the final report), so they can only be reported qualitatively, never
scored by a confidence-based policy.

Writes two files into `--output`: `evaluation-manifest.json` and
`admission-policy-report.json`. Never opens the product database and creates
no Events, Visits, ReviewLabels, or reviewed truth.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mockingbird.observation.admission_policy import (  # noqa: E402
    LabeledProposal,
    default_policy_sweep,
    evaluate_policy_sweep,
)
from mockingbird.observation.contracts import TrackUpdate  # noqa: E402
from mockingbird.observation.evaluation_governance import EvaluationExample, EvaluationManifest  # noqa: E402
from mockingbird.observation.replay import BenchmarkManifest, _match  # noqa: E402
from mockingbird.observation.replay_io import load_replay_bundle  # noqa: E402
from mockingbird.observation.visit_episode_assembler import (  # noqa: E402
    assemble_visit_episodes,
    build_tracklets,
    project_to_visit_proposal,
)

# The four already-reviewed historical field sessions with a real
# `temporal-review-replay-manifest.json` (reviewed Visit/appearance truth)
# and a real-CUDA-verified, current (Stage 6.16+) recorded `replay-report.json`
# committed to this checkout's local (gitignored) `data/field-acceptance/`
# tree -- see docs/reviewed-replay-lineage-contract.md "Real offline
# acceptance" for how this exact corpus was produced and independently
# verified against real hardware.
_STAGE_6_17 = REPO_ROOT / "data/field-acceptance/2026-08-07-stage6.17-reviewed-visit-truth"
_STAGE_6_16 = REPO_ROOT / "data/field-acceptance/2026-08-07-stage6.16-sustained-visit-continuity"
SESSIONS: tuple[tuple[str, Path, Path], ...] = (
    ("attempt-2", _STAGE_6_17 / "attempt-2-export-replay", _STAGE_6_16 / "attempt-2-after/replay-report.json"),
    ("attempt-3", _STAGE_6_17 / "attempt-3-export-replay", _STAGE_6_16 / "attempt-3-after/replay-report.json"),
    ("session-03", _STAGE_6_17 / "session-03-export-replay", _STAGE_6_16 / "session-03-after/replay-report.json"),
    ("session-04", _STAGE_6_17 / "session-04-export-replay", _STAGE_6_16 / "session-04-after/replay-report.json"),
)

# The three 2026-08-10 Aug 10 false candidates (see
# docs/detection-quality-accounting-contract.md and the "observation-engine-
# false-positive-admission-2026-08-10" memory record this script's own
# governance manifest formalizes). Diagnostic only -- never reviewed truth;
# an agent's own visual inspection is not a human Review Decision.
DIAGNOSTIC_EXAMPLES: tuple[EvaluationExample, ...] = (
    EvaluationExample(
        example_id="visit-observation-candidate-001",
        status="diagnostic_only",
        source="agent-visual-inspection-2026-08-10",
        description="box on bare tree-trunk bark between two branches; no bird",
        provenance_ref="visit-episode:e6f2e2b554cc492ad1490058",
    ),
    EvaluationExample(
        example_id="visit-observation-candidate-002",
        status="diagnostic_only",
        source="agent-visual-inspection-2026-08-10",
        description="box on empty grass near a small lawn object; no bird",
        provenance_ref="visit-episode:5b076efb77afec4cd3483734",
    ),
    EvaluationExample(
        example_id="visit-observation-candidate-003",
        status="diagnostic_only",
        source="agent-visual-inspection-2026-08-10",
        description="box directly on the red plastic hummingbird feeder itself; no bird",
        provenance_ref="visit-episode:d11e3ee8fde30530c44d194e",
    ),
)


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _box(value: object) -> tuple[float, float, float, float] | None:
    return tuple(value) if value else None  # type: ignore[return-value]


def _track_update(d: dict) -> TrackUpdate:
    # Deliberately reconstructs only the pre-Detection-Quality-Accounting
    # fields these recorded reports actually have; `confidence_samples`/
    # `max_consecutive_detector_confirmed_frames` are left at their
    # backward-compatible dataclass defaults (`()`/`0`) -- `build_tracklets`
    # honestly reports the resulting strong/weak/consecutive facts as
    # unknown (`None`), never fabricated, for exactly this reason (see
    # docs/detection-quality-accounting-contract.md).
    return TrackUpdate(
        d["track_id"], d["generation_id"], _dt(d["captured_at"]), d["status"],
        d.get("lifecycle_state", "tentative"), d.get("frame_id"), d.get("source_offset_ms"),
        d.get("broad_class"), _box(d.get("bounding_box")), tuple(d.get("supporting_frame_ids") or ()),
        d.get("detector_confirmation_count", 0), d.get("tracker_support_count", 0), d.get("confidence"),
        d.get("detector_provenance"), d.get("tracker_provenance"), d.get("terminal_reason"),
        tuple(d.get("supporting_source_capture_frame_ids") or ()), d.get("weak_detector_support_count", 0),
        d.get("support_state", "temporarily_lost"),
    )


def _reviewed_examples_and_labels(
    name: str, export_directory: Path, recorded_report_path: Path,
) -> tuple[tuple[EvaluationExample, ...], tuple[LabeledProposal, ...]]:
    bundle = load_replay_bundle(export_directory, export_directory / "temporal-review-replay-manifest.json")
    manifest: BenchmarkManifest = bundle.manifest
    recorded = json.loads(recorded_report_path.read_text(encoding="utf-8"))
    track_updates = tuple(_track_update(item) for item in recorded["track_updates"])

    tracklets = build_tracklets(track_updates, stream_id=bundle.replay.stream_id)
    assembly = assemble_visit_episodes(tracklets)
    projected = tuple(project_to_visit_proposal(item) for item in assembly.proposals)
    matches = _match(manifest.visits, projected)

    statuses_by_proposal: dict[str, set[str]] = {}
    for match in matches:
        if match.proposal_key is not None:
            statuses_by_proposal.setdefault(match.proposal_key, set()).add(match.status)

    examples: list[EvaluationExample] = []
    labels: list[LabeledProposal] = []
    for proposal in assembly.proposals:
        statuses = statuses_by_proposal.get(proposal.proposal_id, set())
        if "incorrectly_merged" in statuses:
            truth_status = "reviewed_ambiguous"
            outcome = "incorrectly_merged"
        elif statuses & {"matched", "duplicate", "fragmented"}:
            truth_status = "reviewed_true_positive"
            outcome = "matched_reviewed_visit"
        elif "false" in statuses:
            truth_status = "reviewed_false_positive"
            outcome = "no_corresponding_reviewed_visit"
        else:
            # Should not happen for a real assembled proposal against a
            # manifest covering its whole session; recorded honestly rather
            # than silently dropped if it ever does.
            truth_status = "unreviewed"
            outcome = "no_match_status_recorded"
        examples.append(
            EvaluationExample(
                example_id=f"{name}:{proposal.proposal_id}",
                status="reviewed_truth" if truth_status != "unreviewed" else "auto_generated_unreviewed",
                source=f"stage6.17-reviewed-visit-truth:{name}",
                description=f"{outcome} ({proposal.broad_class}, {proposal.start_offset_ms}-{proposal.end_offset_ms}ms)",
                provenance_ref=proposal.proposal_id,
                reviewed_by=(
                    "temporal-review capture + Stage 6.17 reviewed-Visit-truth manifest"
                    if truth_status != "unreviewed"
                    else None
                ),
                reviewed_at_iso=None,
            )
        )
        labels.append(
            LabeledProposal(
                proposal_id=f"{name}:{proposal.proposal_id}",
                truth_status=truth_status,  # type: ignore[arg-type]
                confidence_evidence=proposal.confidence_evidence,
            )
        )
    return tuple(examples), tuple(labels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    all_examples: list[EvaluationExample] = list(DIAGNOSTIC_EXAMPLES)
    all_labels: list[LabeledProposal] = [
        LabeledProposal(example.example_id, "diagnostic_only", None) for example in DIAGNOSTIC_EXAMPLES
    ]
    session_summaries: dict[str, dict[str, int]] = {}
    for name, export_directory, recorded_report_path in SESSIONS:
        if not recorded_report_path.is_file():
            print(f"skip {name}: recorded report not found at {recorded_report_path}")
            continue
        examples, labels = _reviewed_examples_and_labels(name, export_directory, recorded_report_path)
        all_examples.extend(examples)
        all_labels.extend(labels)
        session_summaries[name] = {
            "reviewed_true_positive": sum(1 for item in labels if item.truth_status == "reviewed_true_positive"),
            "reviewed_false_positive": sum(1 for item in labels if item.truth_status == "reviewed_false_positive"),
            "reviewed_ambiguous": sum(1 for item in labels if item.truth_status == "reviewed_ambiguous"),
        }

    manifest = EvaluationManifest(schema_version=1, examples=tuple(all_examples))
    policy_report = evaluate_policy_sweep(default_policy_sweep(), tuple(all_labels))

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "evaluation-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": manifest.schema_version,
                "generated_at": datetime.now(UTC).isoformat(),
                "counts_by_status": manifest.counts_by_status,
                "session_summaries": session_summaries,
                "examples": [asdict(item) for item in manifest.examples],
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    (args.output / "admission-policy-report.json").write_text(
        json.dumps({"generated_at": datetime.now(UTC).isoformat(), **policy_report}, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    print(f"reviewed examples: {manifest.counts_by_status}")
    print(f"wrote {args.output / 'evaluation-manifest.json'}")
    print(f"wrote {args.output / 'admission-policy-report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
