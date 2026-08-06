"""Command entry point for the Stage 6.9 historical burst-schedule replay.

python -m mockingbird burst-schedule-replay \\
  --manifest <existing-capture-session-manifest.json> \\
  [--annotation <existing-annotation.json>] \\
  [--session-id <label>] \\
  --output <new-or-empty-output-directory>

Opens no product database, starts no camera/Camera Node/worker, and performs
no live burst request. It replays already-captured Stage 6.6/6.8 manifest
facts (and, optionally, already-reviewed annotation truth) through a fresh
`BurstScheduler` and writes one deterministic report file. See
docs/burst-scheduler-contract.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from mockingbird.observation.burst_scheduler_replay import (
    BurstScheduleReplayError,
    replay_burst_schedule,
)
from mockingbird.observation.burst_scheduler_replay_io import (
    load_json_document,
    write_replay_report,
)

_ERROR_EXIT_CODES = {
    "unsafe_document_path": 6,
    "invalid_document_json": 6,
    "unsafe_output_path": 6,
    "nonempty_output_directory": 7,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Replay Stage 6.9 recurrence-aware burst-scheduler decisions against an "
        "already-captured Stage 6.6/6.8 capture-session manifest, optionally cross-referenced "
        "against reviewed annotation truth, without opening a network connection or the product "
        "database."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="Existing capture-session-manifest.json.")
    parser.add_argument("--annotation", type=Path, default=None, help="Existing reviewed annotation.json (optional).")
    parser.add_argument("--session-id", default=None, help="Replay session label; defaults to the manifest's own session_id.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


def _run(args: argparse.Namespace) -> int:
    manifest = load_json_document(args.manifest)
    annotation = load_json_document(args.annotation) if args.annotation is not None else None
    session_id = args.session_id or str(manifest.get("session_id") or "burst-schedule-replay")

    report = replay_burst_schedule(manifest, session_id=session_id, annotation=annotation)
    semantic = report.to_semantic_dict()
    semantic["semantic_fingerprint"] = report.fingerprint
    output_path = write_replay_report(args.output, semantic)

    print(f"Burst-schedule replay report written to {output_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    print(
        f"  current: {report.current_retained_frames} retained frames, "
        f"{report.current_high_resolution_frames} high-resolution, {report.current_track_generations} track generations"
    )
    print(
        f"  proposed: {report.proposed_issued_count} issued / {report.reconstructed_opportunity_count} opportunities "
        f"({report.static_recurrence_suppressions} suppressed as recurring static geometry)"
    )
    print(
        f"  high-resolution frame reduction: {report.high_resolution_frames_reduction} "
        f"(ratio={report.high_resolution_frames_reduction_ratio})"
    )
    if report.genuine_appearance_reviewed is not None:
        print(f"  genuine appearances reviewed/retained: {report.genuine_appearance_reviewed}/{report.genuine_appearance_retained}")
    if report.operator_marked_appearance_reviewed is not None:
        print(f"  operator-marked appearances reviewed/retained: {report.operator_marked_appearance_reviewed}/{report.operator_marked_appearance_retained}")
    if report.missed_useful_burst_risk:
        print(f"  missed-useful-burst risk frames: {list(report.missed_useful_burst_risk)}")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except BurstScheduleReplayError as error:
        print(f"Burst-schedule replay rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error).split(":", 1)[0], 2)


def main() -> None:
    raise SystemExit(run())
