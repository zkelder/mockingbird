"""Command entry points for the Stage 6.13 deterministic evidence-quality
benchmark and comparison.

python -m mockingbird evidence-benchmark \\
  --review <reviewed-temporal-review-directory> \\
  --output <new-or-empty-output-directory>

python -m mockingbird evidence-benchmark \\
  --frames <reviewed-frame-root> --manifest <reviewed-evidence-manifest.json> \\
  [--replay-report <existing-replay-report.json>] \\
  --output <new-or-empty-output-directory>

python -m mockingbird evidence-comparison \\
  --baseline <baseline-evidence-benchmark-report.json> \\
  --candidate <candidate-evidence-benchmark-report.json> \\
  --output <new-or-empty-output-directory>

Neither command opens the product database, starts a camera/Camera Node/
worker, or runs model inference; both read already-existing local files and
write one new, deterministic report file. See
docs/evidence-benchmark-contract.md.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
import time
from typing import Mapping

from mockingbird.observation.evidence_benchmark import (
    EvidenceBenchmarkError,
    compare_evidence_benchmark_reports,
    evaluate_evidence_benchmark,
)
from mockingbird.observation.evidence_benchmark_io import (
    load_replay_report_document,
    load_review_packet_manifest,
    load_reviewed_evidence_manifest,
    replay_candidates_and_proposals,
    resolve_media_mapping,
    write_evidence_benchmark_report,
    write_evidence_comparison_report,
)

_ERROR_EXIT_CODES = {
    "unsafe_manifest_path": 6, "invalid_manifest_json": 6, "unsafe_replay_report_path": 6,
    "invalid_replay_report_json": 6, "unsafe_frames_directory": 6, "unsafe_frame_path": 6,
    "unsafe_output_path": 6, "nonempty_output_directory": 7, "invalid_review_packet": 8,
    "review_is_exclusive_with_frames_and_manifest": 2, "manifest_required": 2,
}


def _exit_code(error: EvidenceBenchmarkError) -> int:
    return _ERROR_EXIT_CODES.get(str(error).split(":", 1)[0], 2)


# --------------------------------------------------------------------------
# evidence-benchmark
# --------------------------------------------------------------------------


def build_benchmark_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically evaluate reviewed evidence candidates by calling the existing "
        "Stage 6 evidence scorer -- never a second ranking algorithm. Consumes either an existing "
        "Stage 6.6/6.8 temporal-review directory (--review) or a native reviewed-evidence-manifest "
        "(--frames/--manifest), optionally supplemented by an already-produced replay report."
    )
    parser.add_argument("--review", type=Path, default=None, help="Existing self-contained Stage 6.6/6.8 review directory.")
    parser.add_argument("--frames", type=Path, default=None, help="Reviewed-frame-root directory for a native --manifest.")
    parser.add_argument("--manifest", type=Path, default=None, help="Native reviewed-evidence-manifest JSON.")
    parser.add_argument("--replay-report", type=Path, default=None, help="Optional already-produced replay-report.json.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


def _process_rss_bytes() -> int | None:
    try:
        import resource
    except ImportError:
        return None
    # POSIX ru_maxrss is kilobytes on Linux, bytes on macOS; this is a
    # non-semantic, best-effort figure only -- never part of the semantic
    # fingerprint -- so the small cross-platform imprecision is acceptable.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 if platform.system() == "Linux" else resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _measure_image_decode_latency_ms(media: Mapping[str, object] | None) -> float | None:
    if not media:
        return None
    from PIL import Image
    started = time.perf_counter()
    for value in media.values():
        try:
            with Image.open(value) as image:
                image.load()
        except Exception:
            continue
    return (time.perf_counter() - started) * 1000


def _run_benchmark(args: argparse.Namespace) -> int:
    if args.review is not None:
        if args.frames is not None or args.manifest is not None:
            raise EvidenceBenchmarkError("review_is_exclusive_with_frames_and_manifest")
        manifest = load_review_packet_manifest(args.review)
        frames_root = args.review
    else:
        if args.manifest is None:
            raise EvidenceBenchmarkError("manifest_required")
        manifest = load_reviewed_evidence_manifest(args.manifest)
        frames_root = args.frames

    media = resolve_media_mapping(frames_root, manifest) if frames_root is not None else None
    decode_latency_ms = _measure_image_decode_latency_ms(media)

    replay_candidates: tuple = ()
    replay_proposals: tuple = ()
    replay_fingerprint = None
    provider_identity = None
    if args.replay_report is not None:
        document = load_replay_report_document(args.replay_report)
        replay_candidates, replay_proposals, replay_fingerprint, provider_identity = replay_candidates_and_proposals(document)

    started = time.perf_counter()
    report = evaluate_evidence_benchmark(
        manifest, media=media, replay_candidates=replay_candidates, replay_proposals=replay_proposals,
        provider_identity=provider_identity, replay_report_fingerprint=replay_fingerprint,
    )
    duration_ms = (time.perf_counter() - started) * 1000

    # `to_semantic_dict()` deliberately never embeds its own fingerprint
    # (that would be self-referential); add it as a sibling key here, the
    # same division of responsibility `replay_io.write_replay_report` uses.
    semantic = {**report.to_semantic_dict(), "semantic_fingerprint": report.semantic_fingerprint}
    execution = {
        "output_path": str(Path(args.output).expanduser().resolve()),
        "wall_clock_duration_ms": round(duration_ms, 3),
        "image_decode_latency_ms": round(decode_latency_ms, 3) if decode_latency_ms is not None else None,
        "process_rss_bytes": _process_rss_bytes(),
        "environment": {"python_version": platform.python_version(), "platform": platform.platform()},
    }
    report_path = write_evidence_benchmark_report(args.output, semantic, execution=execution)

    metrics = semantic["metrics"]
    print(f"Evidence benchmark report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    print(f"  episodes evaluated: {metrics['episodes_evaluated']}")
    print(f"  useful identification rate: {metrics['useful_identification_rate']}")
    print(f"  useful context rate: {metrics['useful_context_rate']}")
    print(f"  no-useful-evidence episodes: {metrics['no_useful_evidence_count']}")
    if semantic["limitations"]:
        print(f"  limitations: {semantic['limitations']}")
    return 0


def run_benchmark(argv: list[str] | None = None) -> int:
    args = build_benchmark_parser().parse_args(argv)
    try:
        return _run_benchmark(args)
    except EvidenceBenchmarkError as error:
        print(f"Evidence benchmark rejected: {error}", file=sys.stderr)
        return _exit_code(error)


def main_benchmark() -> None:
    raise SystemExit(run_benchmark())


# --------------------------------------------------------------------------
# evidence-comparison
# --------------------------------------------------------------------------


def build_comparison_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deterministically compare two evidence-benchmark reports (baseline vs candidate "
        "provider/policy/cohort) metric-by-metric, without an aggregate winner score."
    )
    parser.add_argument("--baseline", required=True, type=Path, help="Existing baseline evidence-benchmark-report.json.")
    parser.add_argument("--candidate", required=True, type=Path, help="Existing candidate evidence-benchmark-report.json.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


def _run_comparison(args: argparse.Namespace) -> int:
    baseline = load_replay_report_document(args.baseline)
    candidate = load_replay_report_document(args.candidate)
    started = time.perf_counter()
    semantic = compare_evidence_benchmark_reports(baseline, candidate)
    duration_ms = (time.perf_counter() - started) * 1000
    execution = {
        "output_path": str(Path(args.output).expanduser().resolve()),
        "wall_clock_duration_ms": round(duration_ms, 3),
        "environment": {"python_version": platform.python_version(), "platform": platform.platform()},
    }
    report_path = write_evidence_comparison_report(args.output, semantic, execution=execution)
    print(f"Evidence comparison report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    classifications: dict[str, int] = {}
    for item in semantic["metrics"]:
        classifications[item["classification"]] = classifications.get(item["classification"], 0) + 1
    for classification, count in sorted(classifications.items()):
        print(f"  {classification}: {count}")
    return 0


def run_comparison(argv: list[str] | None = None) -> int:
    args = build_comparison_parser().parse_args(argv)
    try:
        return _run_comparison(args)
    except EvidenceBenchmarkError as error:
        print(f"Evidence comparison rejected: {error}", file=sys.stderr)
        return _exit_code(error)


def main_comparison() -> None:
    raise SystemExit(run_comparison())
