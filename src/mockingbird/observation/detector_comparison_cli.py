"""Command entry point for the offline, shadow-only detector-candidate
comparison (Observation Engine v2 Stage 6.3).

python -m mockingbird detector-comparison \\
  --baseline-label mdv5 \\
  --baseline-report <ignored-baseline-detector-benchmark-report.json> \\
  --candidate spruce=<ignored-candidate-detector-benchmark-report.json> \\
  [--candidate other-label=<other-report.json> ...] \\
  --output <output-directory>

This command opens no product database, starts no camera/Camera Node/worker,
runs no model inference, and writes only the one deterministic report file
into the requested output directory. Every input is an already-produced
Stage 6.2 `detector-benchmark-report.json`. See
docs/detector-candidate-comparison-contract.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from mockingbird.observation.detector_comparison import (
    DetectorComparisonError,
    build_comparison_semantic_report,
)
from mockingbird.observation.detector_comparison_io import (
    load_detector_benchmark_report,
    write_detector_comparison_report,
)

_ERROR_EXIT_CODES = {
    "unsafe_report_path": 6,
    "invalid_report_json": 6,
    "unsafe_output_path": 6,
    "nonempty_output_directory": 7,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare one or more detector candidates against an MDv5 baseline, "
        "each already scored by the Stage 6.2 detector-calibration benchmark."
    )
    parser.add_argument("--baseline-label", required=True, help="Short label for the baseline model, e.g. 'mdv5'.")
    parser.add_argument("--baseline-report", required=True, type=Path, help="Existing baseline detector-benchmark-report.json.")
    parser.add_argument(
        "--candidate", required=True, action="append", metavar="LABEL=REPORT_PATH",
        help="One candidate as label=path to its detector-benchmark-report.json; repeatable.",
    )
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


def _parse_candidate_argument(raw: str) -> tuple[str, Path]:
    label, separator, path_text = raw.partition("=")
    if not separator or not label or not path_text:
        raise DetectorComparisonError("invalid_candidate_argument")
    return label, Path(path_text)


def _run(args: argparse.Namespace) -> int:
    baseline_report = load_detector_benchmark_report(args.baseline_report)

    candidate_reports: dict[str, dict[str, object]] = {}
    for raw in args.candidate:
        label, path = _parse_candidate_argument(raw)
        if label in candidate_reports:
            raise DetectorComparisonError("duplicate_candidate_label")
        candidate_reports[label] = load_detector_benchmark_report(path)

    semantic = build_comparison_semantic_report(
        baseline_label=args.baseline_label, baseline_report=baseline_report, candidate_reports=candidate_reports,
    )
    # `build_comparison_semantic_report` already returns its own
    # `execution` section (per-candidate runtime facts read from each input
    # report's own non-semantic section); nothing further to add here.
    execution = semantic.pop("execution")
    report_path = write_detector_comparison_report(args.output, semantic, execution=execution)
    print(f"Detector comparison report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    for label in semantic["candidate_labels"]:
        comparison = next(item for item in semantic["comparisons"] if item["candidate_label"] == label)
        verdict = comparison["verdict"]
        print(
            f"  {label}: precision={verdict['precision']} recall={verdict['recall']} "
            f"small_subject_recall={verdict['small_subject_recall']} licensing={verdict['licensing']} "
            f"-> {verdict['final_recommendation']}"
        )
    return 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _run(args)
    except DetectorComparisonError as error:
        print(f"Detector comparison rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def main() -> None:
    raise SystemExit(run())
