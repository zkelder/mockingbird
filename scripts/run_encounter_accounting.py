#!/usr/bin/env python3
"""Admission Recall Investigation + Conditional Fix v1: build an
encounter-level accounting report from an already-fetched counterfactual
ledger window (see docs/tracklet-visit-assembly-contract.md "Ambiguous
boundary arbitration" and docs/rejected-detection-attribution-contract.md).

This is a hardware-free, database-free, network-free analysis pass over an
already-saved JSON snapshot -- exactly the same "reconstruct from already
-recorded facts" methodology `run_detection_quality_accounting.py` already
established for the Stage 6.19 assembler, applied here to Rejected/
Suppressed Detection Attribution v1's own counterfactual ledger instead.
It never opens a live camera, the product database, or a network
connection, and it creates no Event, Visit, ReviewLabel, or reviewed truth.

Input: a JSON file with the exact shape
`GET /api/streams/{stream_id}/observation/counterfactual` returns (see
`CounterfactualWindowResponse` in `mockingbird.api.schemas`) -- an operator
fetches this once, from either a still-running or a stopped-but-not-yet
-restarted Observation Engine session, and saves it to disk; this script
never fetches it itself. A bounded window covering the whole session
(`start_offset_ms=0`, a generous `end_offset_ms`) reconstructs the fullest
available picture; the response's own `coverage` facts (also reported
below) disclose exactly how much of the session's raw-detection/track
-generation/proposal-outcome lineage is still retained versus evicted --
this script never claims completeness the source data does not have.

Output: `encounter-funnel-report.json` (schema: `encounter_accounting.
EncounterFunnelReport` plus the individual `EncounterCluster` list) under
`--output`, and a compact human-readable summary on stdout.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mockingbird.observation.clock_calibration import ClockCalibrationRecord  # noqa: E402
from mockingbird.observation.contracts import ConfidenceEvidenceSummary  # noqa: E402
from mockingbird.observation.counterfactual_lineage import (  # noqa: E402
    ProposalOutcomeRecord,
    TrackGenerationRecord,
)
from mockingbird.observation.encounter_accounting import (  # noqa: E402
    EncounterCluster,
    build_encounter_funnel_report,
    cluster_encounters,
)


def _cluster_to_dict(cluster: EncounterCluster) -> dict:
    """`dataclasses.asdict` only serializes actual dataclass fields, never
    `EncounterCluster`'s own computed properties (`plausibility`, `is_
    fragmented`, ...) -- a report consumer needs those too, so this adds
    them explicitly rather than silently omitting the derived facts a
    human reviewer actually wants to see."""
    payload = asdict(cluster)
    payload["duration_ms"] = cluster.duration_ms
    payload["has_confirmed_tracking"] = cluster.has_confirmed_tracking
    payload["has_viable_proposal"] = cluster.has_viable_proposal
    payload["has_visit"] = cluster.has_visit
    payload["is_fragmented"] = cluster.is_fragmented
    payload["has_multiple_proposals"] = cluster.has_multiple_proposals
    payload["plausibility"] = cluster.plausibility
    return payload


def _confidence_evidence_from_dict(data: dict | None) -> ConfidenceEvidenceSummary:
    """The API's `CounterfactualConfidenceSummaryResponse` is a small,
    bounded projection (`detection_count`/`max_confidence`/`strong_
    detection_count` only -- see `_counterfactual_confidence_response` in
    `mockingbird.api.main`), never the full `ConfidenceEvidenceSummary`.
    Every field this script does not receive is honestly reported unknown
    (`None`/empty), never fabricated."""
    if data is None:
        return ConfidenceEvidenceSummary(
            detection_count=0, max_confidence=None, mean_confidence=None, median_confidence=None,
            strong_detection_count=None, weak_detection_count=None,
            max_consecutive_detector_confirmed_frames=None, samples=(), broad_class=None,
            first_detection_offset_ms=None, last_detection_offset_ms=None, sample_truncated=True,
        )
    return ConfidenceEvidenceSummary(
        detection_count=data.get("detection_count", 0),
        max_confidence=data.get("max_confidence"),
        mean_confidence=None,
        median_confidence=None,
        strong_detection_count=data.get("strong_detection_count"),
        weak_detection_count=None,
        max_consecutive_detector_confirmed_frames=None,
        samples=(),
        broad_class=None,
        first_detection_offset_ms=None,
        last_detection_offset_ms=None,
        sample_truncated=True,
    )


def _optional_datetime(value: str | None) -> datetime | None:
    """`None` for a missing/absent key (a saved ledger snapshot from before
    Gate A Measurement Closure v1 added this field) -- never fabricated;
    never raises on a well-formed ISO-8601 string, matching every other
    tolerant-parse helper in this script."""
    return datetime.fromisoformat(value) if value else None


def _track_generation_from_dict(data: dict) -> TrackGenerationRecord:
    return TrackGenerationRecord(
        generation_id=data["generation_id"],
        stream_id=data.get("stream_id", "unknown-stream"),
        broad_class=data["broad_class"],
        track_ids=tuple(data.get("track_ids", ())),
        start_offset_ms=data["start_offset_ms"],
        end_offset_ms=data["end_offset_ms"],
        start_bounding_box=tuple(data["start_bounding_box"]),
        end_bounding_box=tuple(data["end_bounding_box"]),
        geometry_envelope=tuple(data["geometry_envelope"]),
        confirmed=data["confirmed"],
        terminal_reason=data.get("terminal_reason"),
        terminal_support_state=None,
        terminal_bounding_box_source_offset_ms=None,
        confidence_evidence=_confidence_evidence_from_dict(data.get("confidence_evidence")),
        start_captured_at=_optional_datetime(data.get("start_captured_at")),
        end_captured_at=_optional_datetime(data.get("end_captured_at")),
    )


def _proposal_outcome_from_dict(data: dict) -> ProposalOutcomeRecord:
    return ProposalOutcomeRecord(
        proposal_id=data["proposal_id"],
        stream_id=data.get("stream_id", "unknown-stream"),
        broad_class=data["broad_class"],
        zone_id=data.get("zone_id"),
        start_offset_ms=data["start_offset_ms"],
        end_offset_ms=data["end_offset_ms"],
        constituent_generation_ids=tuple(data.get("constituent_generation_ids", ())),
        constituent_track_ids=(),
        outcome=data["outcome"],
        reason=data.get("reason", ""),
        admitted=data["admitted"],
        visit_id=data.get("visit_id"),
        confidence_evidence=None,
        # Gate A Measurement Closure v1: pre-existing bug fix, exposed (not
        # introduced) by this milestone's own new latency accounting --
        # `cluster_encounters` never itself does datetime arithmetic on
        # `decided_at` (only `decided_at_offset_ms`, an int), so a bare
        # ISO-8601 *string* silently round-tripped as "close enough" for
        # every prior use of this parser. `capture_to_visible_latency.py`
        # is the first real consumer that subtracts `decided_at` from
        # another datetime, and a raw string there raises `TypeError`
        # rather than silently producing a wrong number -- still worth
        # fixing at the source rather than relying on that to always be
        # true downstream.
        decided_at=_optional_datetime(data.get("decided_at")),
        decided_at_offset_ms=data.get("end_offset_ms"),
    )


def _clock_calibration_from_dict(data: dict) -> ClockCalibrationRecord:
    """Camera Node -> Host Clock Normalization v1: parses one
    `CounterfactualClockCalibrationResponse`-shaped dict. `calibrated_at` is
    always present (unlike `start_captured_at`/`end_captured_at`, no saved
    snapshot ever predates this field's own *record type* -- it either has
    no `clock_calibrations` key at all, handled by the caller defaulting to
    `()`, or every entry it does have is well-formed)."""
    return ClockCalibrationRecord(
        stream_id=data.get("stream_id", "unknown-stream"),
        source_offset_ms=data["source_offset_ms"],
        calibrated_at=datetime.fromisoformat(data["calibrated_at"]),
        sample_count=data["sample_count"],
        state=data["state"],
        offset_ms=data.get("offset_ms"),
        uncertainty_ms=data.get("uncertainty_ms"),
        min_delta_ms=data.get("min_delta_ms"),
        max_delta_ms=data.get("max_delta_ms"),
        clock_jump_detected=data.get("clock_jump_detected", False),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input", type=Path, required=True,
        help="Path to a saved GET .../observation/counterfactual JSON response.",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/evaluations/encounter-accounting"),
        help="Directory to write encounter-funnel-report.json into (gitignored; created if missing).",
    )
    args = parser.parse_args(argv)

    window = json.loads(args.input.read_text(encoding="utf-8"))
    track_generations = [_track_generation_from_dict(item) for item in window.get("track_generations", ())]
    proposal_outcomes = [_proposal_outcome_from_dict(item) for item in window.get("proposal_outcomes", ())]

    clusters = cluster_encounters(track_generations, proposal_outcomes)
    report = build_encounter_funnel_report(clusters)

    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "encounter-funnel-report.json"
    report_path.write_text(
        json.dumps(
            {
                "source_input": str(args.input),
                "source_coverage": window.get("coverage"),
                "funnel": asdict(report),
                "clusters": [_cluster_to_dict(cluster) for cluster in clusters],
            },
            indent=2, sort_keys=True, default=str,
        ),
        encoding="utf-8",
    )

    print(f"Encounter clusters reconstructed: {report.total_encounter_clusters}")
    print(f"  with confirmed tracking:  {report.clusters_with_confirmed_tracking}  (tracking_recall={report.tracking_recall})")
    print(f"  with a viable proposal:   {report.clusters_with_viable_proposal}  (proposal_recall={report.proposal_recall})")
    print(f"  with an admitted Visit:   {report.clusters_with_visit}  (admission_recall={report.admission_recall})")
    print(f"Fragmented clusters (>1 track generation): {report.fragmented_cluster_count}")
    print(f"Clusters with >1 distinct proposal: {report.multi_proposal_cluster_count}")
    print(f"Clusters with >1 admitted Visit (duplicate signal): {report.duplicate_visit_cluster_count}")
    print(f"Plausibility tiers: {report.plausibility_counts}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
