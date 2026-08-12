"""Command entry points for the Stage 6.6 review-packet build, annotation
validation, and benchmark export, plus the Stage-3 correction-tranche
reviewer.

python -m mockingbird temporal-review-build --capture <capture-directory> --output <review-directory>
python -m mockingbird temporal-review-validate --review <review-directory>
python -m mockingbird temporal-review-export --review <review-directory> \\
  --target detector-calibration|motion-proposal|replay --output <output-directory>
python -m mockingbird stage3-tranche-review-build --tranche <tranche.json> --output <review-directory>

None of these commands opens the product database, starts a camera/worker,
or creates a product record. See docs/temporal-review-capture-contract.md and
docs/wildlife-detector-training-contract.md.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import sys

from mockingbird.observation.temporal_annotation import (
    TemporalAnnotationError,
    build_detector_calibration_export,
    build_motion_proposal_export,
    build_replay_export,
    compute_dataset_statistics,
    validate_annotations,
)
from mockingbird.observation.temporal_capture import TemporalCaptureError
from mockingbird.observation.temporal_capture_io import FRAMES_DIRECTORY_NAME, HIGH_RESOLUTION_DIRECTORY_NAME
from mockingbird.observation.temporal_review_io import (
    build_review_packet,
    build_stage3_tranche_review_packet,
    copy_replay_export_images,
    load_annotation_set,
    load_capture_manifest,
    safe_review_directory,
    write_export_manifest,
)

EXPORT_TARGETS = ("detector-calibration", "motion-proposal", "replay")
_ERROR_EXIT_CODES = {
    "unsafe_output_path": 6, "nonempty_output_directory": 7, "missing_capture_manifest": 8,
    "invalid_capture_manifest": 8, "missing_annotation_file": 9, "invalid_annotation_file": 9,
    "stage3_tranche_source_image_integrity_mismatch": 12,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a bounded, deterministic review packet from a capture directory.")
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _stage3_build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a self-contained Stage-3 correction-tranche review packet.")
    parser.add_argument("--tranche", required=True, type=Path, help="Tranche JSON from build_wildlife_stage3_correction_tranche.py.")
    parser.add_argument("--output", required=True, type=Path)
    return parser


def _validate_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate a reviewer-edited annotation.json against its capture manifest.")
    parser.add_argument("--review", required=True, type=Path, help="Self-contained review directory produced by temporal-review-build.")
    return parser


def _export_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export a validated review packet into an existing benchmark manifest shape.")
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--target", required=True, choices=EXPORT_TARGETS)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--scene-group", default=None, help="Defaults to the capture session's own stream_id.")
    return parser


def run_build(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        output_directory = safe_review_directory(args.output)
        summary = build_review_packet(args.capture, output_directory)
        print(f"Review packet written to {output_directory}: {summary['frame_count']} frames, {summary['crop_count']} crops.")
        print(f"Edit {output_directory / 'annotation.json'} then run temporal-review-validate.")
        return 0
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        print(f"Review-build rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def run_stage3_review_build(argv: list[str] | None = None) -> int:
    args = _stage3_build_parser().parse_args(argv)
    try:
        output_directory = safe_review_directory(args.output, allow_existing=True)
        summary = build_stage3_tranche_review_packet(args.tranche, output_directory)
        print(
            f"Stage-3 tranche review packet written to {output_directory}: "
            f"{summary['frame_count']} frames, {summary['crop_count']} crops."
        )
        print(f"Open {output_directory / 'index.html'} in a browser to review, or run temporal-review-validate.")
        return 0
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        print(f"Stage-3 review-build rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def _content_hash_lookup(capture_directory: Path):
    def _lookup(frame_id: str) -> str | None:
        for subdirectory in (FRAMES_DIRECTORY_NAME, HIGH_RESOLUTION_DIRECTORY_NAME):
            path = capture_directory / subdirectory / f"{frame_id}.jpg"
            if path.is_file() and not path.is_symlink():
                return sha256(path.read_bytes()).hexdigest()
        return None
    return _lookup


def run_validate(argv: list[str] | None = None) -> int:
    args = _validate_parser().parse_args(argv)
    try:
        manifest = load_capture_manifest(args.review)
        annotations = load_annotation_set(args.review)
        report = validate_annotations(manifest, annotations, actual_content_hash=_content_hash_lookup(args.review))
        for issue in report.issues:
            print(f"[{issue.severity.upper()}] {issue.code} frame={issue.frame_id}: {issue.detail}")
        print(
            f"scorable={report.scorable_frame_count} reviewed={report.reviewed_frame_count} "
            f"ambiguous={report.ambiguous_frame_count} unreviewed={report.unreviewed_frame_count} "
            f"rejects={report.reject_count}"
        )
        print("VALIDATION OK" if report.ok else "VALIDATION FAILED")
        return 0 if report.ok else 1
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        print(f"Review-validate rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def run_export(argv: list[str] | None = None) -> int:
    args = _export_parser().parse_args(argv)
    try:
        manifest = load_capture_manifest(args.review)
        annotations = load_annotation_set(args.review)
        report = validate_annotations(manifest, annotations, actual_content_hash=_content_hash_lookup(args.review))
        if not report.ok:
            print("Export refused: annotation set fails validation. Run temporal-review-validate for details.", file=sys.stderr)
            return 3
        scene_group = args.scene_group or str(manifest.get("config", {}).get("stream_id"))
        if args.target == "detector-calibration":
            payload = build_detector_calibration_export(manifest, annotations, scene_group=scene_group)
            filename = "temporal-review-detector-calibration-manifest.json"
        elif args.target == "motion-proposal":
            payload = build_motion_proposal_export(manifest, annotations, scene_group=scene_group)
            filename = "temporal-review-motion-proposal-manifest.json"
        else:
            payload = build_replay_export(manifest, annotations)
            filename = "temporal-review-replay-manifest.json"
        statistics = compute_dataset_statistics((manifest,), (annotations,))
        payload_with_stats = {**payload, "dataset_statistics": statistics.to_dict()}
        path = write_export_manifest(args.output, payload_with_stats, filename=filename)
        print(f"Export written to {path}.")
        print(f"benchmark_sufficiency[{args.target.replace('-', '_')}]={statistics.benchmark_sufficiency.get(args.target.replace('-', '_'), statistics.benchmark_sufficiency)}")
        if args.target == "replay":
            # The manifest alone is not a runnable replay input: copy every
            # source frame it references so `replay-benchmark --frames
            # <output>` actually loads without a separate manual step.
            copied = copy_replay_export_images(args.review, args.output, payload)
            print(f"Copied {copied} replay source frame(s) to {args.output / 'images'}.")
        return 0
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        print(f"Review-export rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def main_build() -> None:
    raise SystemExit(run_build())


def main_stage3_review_build() -> None:
    raise SystemExit(run_stage3_review_build())


def main_validate() -> None:
    raise SystemExit(run_validate())


def main_export() -> None:
    raise SystemExit(run_export())
