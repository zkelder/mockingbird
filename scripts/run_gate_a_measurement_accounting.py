#!/usr/bin/env python3
"""Gate A Measurement Closure v1: one reproducible command that reruns
encounter accounting (`encounter_accounting.py`, unmodified), the new
fragmentation-review accounting (`fragmentation_accounting.py`), and the new
capture-to-visible latency accounting (`capture_to_visible_latency.py`)
against one already-saved counterfactual ledger snapshot -- see
docs/gate-a-measurement-closure-fragmentation-latency-v1-report.md "Tooling
UX".

This is a hardware-free, database-free, network-free analysis pass over an
already-saved JSON snapshot, exactly the same methodology
`run_encounter_accounting.py` already established (reused here, not
duplicated -- this script imports that script's own dict-parsing helpers
rather than re-deriving them, matching the sibling-script-import convention
`scripts/evaluate_wildlife_stage1.py`/`evaluate_wildlife_stage2.py` already
use for `run_detector_candidate_benchmark.py`). It never opens a live
camera, the product database, or a network connection, and it creates no
Event, Visit, ReviewLabel, or reviewed truth.

Input: a JSON file with the exact shape `GET /api/streams/{stream_id}/
observation/counterfactual` returns -- an operator fetches this once (for a
session long enough to exceed the ledger's own 60-minute retention window,
merge several periodic snapshots first, exactly as
representative-daylight-gate-a-field-acceptance-v7-report.md "Independent
denominator" describes) and saves it to disk; this script never fetches it
itself.

Two more inputs are optional and purely additive:

- `--visits`: a `GET /api/visits`-shaped export (`[{"id": ..., "event_id":
  ...}, ...]`), used only for the confident concurrent-siblings auto
  -classification in `fragmentation_accounting.py` -- omitted, every
  multi-Visit candidate cluster with no shared tracker evidence is honestly
  `ambiguous` rather than guessed.
- `--dispositions`: reviewer overrides
  (`[{"denominator_unit_id": ..., "disposition": ..., "reviewer_note": ...,
  "subject_count": null, "evidence_pointer": null}, ...]`) -- the *only*
  way an `ambiguous` unit (or a wrong auto-classification) becomes
  `fragmented`/`correctly_represented`/`duplicate`/`merged`/`missed` with
  `denominator_confidence="reviewed"`. A first run with no `--dispositions`
  is exactly how a reviewer discovers which `denominator_unit_id`s need a
  decision (`needs_review_unit_ids` in the fragmentation report).

Output, under `--output` (default `data/evaluations/gate-a-measurement-
accounting`, gitignored):

- `encounter-funnel-report.json` -- `encounter_accounting.
  EncounterFunnelReport`, unmodified (the same schema
  `run_encounter_accounting.py` alone already produces).
- `fragmentation-accounting-report.json` -- `fragmentation_accounting.
  FragmentationAccountingReport` plus every `DenominatorUnit` (fragmentation
  review candidates and duplicate candidates alike -- filter by
  `disposition`).
- `latency-report.json` -- `capture_to_visible_latency.LatencySummary` plus
  every `LatencySample` (capture-to-visible latency samples, fallback
  attempts flagged). Camera Node -> Host Clock Normalization v1
  (additive): when `--input`'s own `clock_calibration_required` is `true`
  (a real Camera Node session), every sample's raw T0 is normalized through
  its own governing `clock_calibrations` entry before latency is computed
  -- `state="invalid_clock_mapping"` (distinct from `unavailable_capture_
  time`) whenever no trustworthy calibration covers it. A snapshot with no
  `clock_calibrations` key at all (saved before this milestone) is handled
  the same honest way, never a crash.

Plus a compact human-readable summary on stdout.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_encounter_accounting import (  # noqa: E402
    _clock_calibration_from_dict,
    _proposal_outcome_from_dict,
    _track_generation_from_dict,
)

from mockingbird.observation.capture_to_visible_latency import (  # noqa: E402
    build_latency_samples,
    build_latency_summary,
)
from mockingbird.observation.encounter_accounting import (  # noqa: E402
    build_encounter_funnel_report,
    cluster_encounters,
)
from mockingbird.observation.fragmentation_accounting import (  # noqa: E402
    ReviewerDisposition,
    apply_reviewer_dispositions,
    build_denominator_units,
    build_fragmentation_accounting_report,
)


def _load_visit_event_ids(path: Path | None) -> dict[str, str] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["id"]: item["event_id"] for item in data if item.get("event_id")}


def _load_reviewer_dispositions(path: Path | None) -> list[ReviewerDisposition]:
    if path is None:
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        ReviewerDisposition(
            denominator_unit_id=item["denominator_unit_id"],
            disposition=item["disposition"],
            reviewer_note=item["reviewer_note"],
            subject_count=item.get("subject_count"),
            evidence_pointer=item.get("evidence_pointer"),
        )
        for item in data
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to a saved GET .../observation/counterfactual JSON response.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/evaluations/gate-a-measurement-accounting"),
        help="Directory to write the three reports into (gitignored; created if missing).",
    )
    parser.add_argument(
        "--visits", type=Path, default=None,
        help="Optional GET /api/visits export, for the concurrent-siblings auto-classification.",
    )
    parser.add_argument(
        "--dispositions", type=Path, default=None, help="Optional reviewer-disposition overrides JSON.",
    )
    args = parser.parse_args(argv)

    window = json.loads(args.input.read_text(encoding="utf-8"))
    track_generations = [_track_generation_from_dict(item) for item in window.get("track_generations", ())]
    proposal_outcomes = [_proposal_outcome_from_dict(item) for item in window.get("proposal_outcomes", ())]
    # Camera Node -> Host Clock Normalization v1 (additive): absent for
    # every ledger snapshot saved before this milestone -- `()`/`False` are
    # the same honest "not a Camera Node session, or predates this field"
    # defaults `capture_to_visible_latency.build_latency_samples` itself
    # already uses.
    clock_calibrations = [_clock_calibration_from_dict(item) for item in window.get("clock_calibrations", ())]
    clock_calibration_required = window.get("clock_calibration_required", False)

    clusters = cluster_encounters(track_generations, proposal_outcomes)
    encounter_report = build_encounter_funnel_report(clusters)

    visit_event_ids = _load_visit_event_ids(args.visits)
    units = build_denominator_units(clusters, proposal_outcomes, visit_event_ids=visit_event_ids)
    overrides = _load_reviewer_dispositions(args.dispositions)
    if overrides:
        units = apply_reviewer_dispositions(units, overrides)
    fragmentation_report = build_fragmentation_accounting_report(units)

    latency_samples = build_latency_samples(
        proposal_outcomes, track_generations,
        clock_calibrations=clock_calibrations, clock_calibration_required=clock_calibration_required,
    )
    latency_summary = build_latency_summary(latency_samples)

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "encounter-funnel-report.json").write_text(
        json.dumps(
            {"source_input": str(args.input), "funnel": asdict(encounter_report)},
            indent=2, sort_keys=True, default=str,
        ),
        encoding="utf-8",
    )
    (args.output / "fragmentation-accounting-report.json").write_text(
        json.dumps(
            {
                "source_input": str(args.input),
                "report": asdict(fragmentation_report),
                "denominator_units": [asdict(unit) for unit in units],
            },
            indent=2, sort_keys=True, default=str,
        ),
        encoding="utf-8",
    )
    (args.output / "latency-report.json").write_text(
        json.dumps(
            {
                "source_input": str(args.input),
                "summary": asdict(latency_summary),
                "samples": [asdict(sample) for sample in latency_samples],
            },
            indent=2, sort_keys=True, default=str,
        ),
        encoding="utf-8",
    )

    print(f"Encounter clusters reconstructed: {encounter_report.total_encounter_clusters}")
    print(f"  with an admitted Visit: {encounter_report.clusters_with_visit}")
    print(
        f"  raw duplicate_visit_cluster_count={encounter_report.duplicate_visit_cluster_count}, "
        f"fragmented_cluster_count={encounter_report.fragmented_cluster_count} "
        "(track-generation-count diagnostics -- see fragmentation-accounting-report.json for the "
        "corrected, human-reviewable fragmentation disposition)"
    )
    print(
        f"Fragmentation accounting: {fragmentation_report.total_units} denominator units -- "
        f"correctly_represented={fragmentation_report.correctly_represented_count}, "
        f"fragmented={fragmentation_report.fragmented_count}, "
        f"duplicate={fragmentation_report.duplicate_count}, "
        f"missed={fragmentation_report.missed_count}, merged={fragmentation_report.merged_count}, "
        f"ambiguous={fragmentation_report.ambiguous_count} "
        f"(needs_review_unit_ids: {len(fragmentation_report.needs_review_unit_ids)})"
    )
    print(f"  fragmentation_rate={fragmentation_report.fragmentation_rate}")
    print(
        f"Clock calibration: required={clock_calibration_required}, "
        f"{len(clock_calibrations)} attempts recorded "
        f"({sum(1 for item in clock_calibrations if item.state == 'calibrated')} calibrated, "
        f"{sum(1 for item in clock_calibrations if item.clock_jump_detected)} clock jump(s) detected)"
    )
    print(
        f"Latency: {latency_summary.sample_count} admitted samples -- "
        f"measured={latency_summary.measured_count}, "
        f"unavailable_capture_time={latency_summary.unavailable_capture_time_count}, "
        f"invalid_negative={latency_summary.invalid_negative_count}, "
        f"implausible={latency_summary.implausible_count}, "
        f"invalid_clock_mapping={latency_summary.invalid_clock_mapping_count}, "
        f"fallback_measured={latency_summary.fallback_measured_count}"
    )
    print(
        f"  median_ms={latency_summary.median_ms}, p90_ms={latency_summary.p90_ms}, "
        f"p95_ms={latency_summary.p95_ms}, max_ms={latency_summary.max_ms}, mean_ms={latency_summary.mean_ms}"
    )
    print(f"Wrote {args.output}/{{encounter-funnel-report,fragmentation-accounting-report,latency-report}}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
