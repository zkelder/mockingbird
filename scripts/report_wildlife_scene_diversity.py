#!/usr/bin/env python3
"""Read-only Multi-Scene Backyard Domain Acquisition scene-diversity /
multi-scene-readiness report (task Section 6).

Cross-references, never mutates: the legacy feeder correction subset (if
built), any newly captured multi-scene manifests under
`--scene-manifest-root`, and any built-and-reviewed scene/session review
packets (`--scene-review SCENE_ID:REVIEW_DIR`, repeatable). Reports total/
training/holdout scenes, sessions per scene, exact retained frames, human-
reviewed positives/negatives, ambiguous frames, animal boxes, size buckets,
scene concentration, and whether the first practical multi-scene
acquisition target (docs/wildlife-detector-training-contract.md "Scene
diversity accounting" / task Section 5) has been met.

This script never opens the product database, starts a camera/worker, or
writes any file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from mockingbird.observation.temporal_annotation import AnnotationSet, TemporalAnnotationError
from mockingbird.observation.temporal_capture import TemporalCaptureError
from mockingbird.observation.temporal_review_io import load_annotation_set, load_capture_manifest
from mockingbird.training.wildlife_multiscene import (
    WildlifeMultiSceneError,
    annotation_counts_for_scene,
    feeder_subset_session_concentration,
    scan_scene_manifests,
    scene_diversity_report,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--feeder-subset", type=Path,
        default=Path("data/training/wildlife-feeder-subset/feeder-correction-subset-v1.json"),
    )
    parser.add_argument(
        "--feeder-review", type=Path, default=Path("data/training/wildlife-stage3/tranche-a-review"),
        help="Existing Stage-3 Tranche A review directory; cross-referenced for real reviewed "
             "counts restricted to the feeder subset's own frames.",
    )
    parser.add_argument("--scene-manifest-root", type=Path, default=Path("data/field-acceptance"))
    parser.add_argument(
        "--scene-review", action="append", default=[], metavar="SCENE_ID:REVIEW_DIR",
        help="Repeatable. A built-and-reviewed scene/session review packet "
             "(build_wildlife_scene_review_tranche.py + stage3-tranche-review-build) to "
             "cross-reference for real reviewed counts.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of the human summary.")
    return parser.parse_args()


def _frame_dimensions(manifest: dict) -> dict[str, tuple[int, int]]:
    return {
        str(item["frame_id"]): (int(item.get("original_width") or 0), int(item.get("original_height") or 0))
        for item in manifest.get("frames", [])
    }


def _feeder_annotation_counts(feeder_subset: dict, review_dir: Path) -> dict:
    if not review_dir.is_dir():
        return {}
    try:
        manifest = load_capture_manifest(review_dir)
        annotations = load_annotation_set(review_dir)
    except (TemporalCaptureError, TemporalAnnotationError):
        return {}
    subset_frame_ids = {row["frame_id"] for row in feeder_subset.get("frames", [])}
    # Restrict to the ~200 selected frames -- the review directory covers
    # the full 700-frame Tranche A, and counts here must describe the
    # smaller default-plan subset, not the whole superset.
    filtered = AnnotationSet(
        schema_version=annotations.schema_version, capture_session_id=annotations.capture_session_id,
        capture_manifest_fingerprint=annotations.capture_manifest_fingerprint,
        frames=tuple(item for item in annotations.frames if item.frame_id in subset_frame_ids),
    )
    return annotation_counts_for_scene(filtered, _frame_dimensions(manifest))


def _scene_annotation_counts(pairs: list[str]) -> dict[str, dict]:
    counts: dict[str, dict] = {}
    for pair in pairs:
        scene_id, separator, directory = pair.partition(":")
        if not separator:
            print(f"warning: ignoring malformed --scene-review value {pair!r} (expected SCENE_ID:DIR)", file=sys.stderr)
            continue
        review_dir = Path(directory)
        try:
            manifest = load_capture_manifest(review_dir)
            annotations = load_annotation_set(review_dir)
        except (TemporalCaptureError, TemporalAnnotationError) as error:
            print(f"warning: skipping unreadable scene review {pair}: {error}", file=sys.stderr)
            continue
        counts[scene_id] = annotation_counts_for_scene(annotations, _frame_dimensions(manifest))
    return counts


def _human_summary(report: dict) -> str:
    lines = [
        "Multi-scene diversity / readiness report",
        f"  total_scenes={report['total_scenes']} training_scenes={report['training_scenes']} "
        f"holdout_scenes={report['holdout_scenes']}",
    ]
    for scene_id, info in sorted(report["scenes"].items()):
        lines.append(
            f"    {scene_id}: purpose={info['purpose']} sessions={info['sessions']} frames={info['retained_frames']} "
            f"reviewed(+{info['reviewed_positive']}/-{info['reviewed_negative']}/?{info['ambiguous']}) "
            f"boxes={info['animal_boxes']} size_buckets={info['size_buckets']}"
        )
    if report["conflicting_purpose_scenes"]:
        lines.append(f"  CONFLICTING PURPOSE SCENES: {report['conflicting_purpose_scenes']}")
    concentration = report["concentration"]
    lines.append(
        f"  concentration: most={concentration['most_concentrated_scene']} "
        f"fraction={concentration['most_concentrated_fraction']:.2f} warning={concentration['warning']} "
        f"(visibility only, threshold={concentration['warning_fraction_threshold']})"
    )
    if "feeder_subset_concentration" in report:
        feeder_concentration = report["feeder_subset_concentration"]
        lines.append(
            f"  feeder subset session concentration: most={feeder_concentration['most_concentrated_session']} "
            f"fraction={feeder_concentration['most_concentrated_fraction']:.2f} of {feeder_concentration['total']} frames"
        )
    target = report["first_multiscene_target"]
    lines.append(f"  FIRST_MULTISCENE_TARGET_MET={target['met']}")
    if target["reasons"]:
        lines.append("  not yet met because:")
        lines.extend(f"    - {reason}" for reason in target["reasons"])
    return "\n".join(lines)


def main() -> int:
    args = _args()
    feeder_subset = None
    feeder_annotation_counts = None
    if args.feeder_subset.is_file():
        feeder_subset = json.loads(args.feeder_subset.read_text())
        feeder_annotation_counts = _feeder_annotation_counts(feeder_subset, args.feeder_review)

    manifest_paths = (
        sorted(args.scene_manifest_root.glob("**/capture-session-manifest.json"))
        if args.scene_manifest_root.is_dir() else []
    )
    scene_records = scan_scene_manifests(manifest_paths)
    scene_annotation_counts = _scene_annotation_counts(args.scene_review)

    report = scene_diversity_report(
        feeder_subset=feeder_subset, feeder_annotation_counts=feeder_annotation_counts,
        scene_records=scene_records, scene_annotation_counts=scene_annotation_counts,
    )
    if feeder_subset is not None:
        report["feeder_subset_concentration"] = feeder_subset_session_concentration(feeder_subset)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_summary(report))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeMultiSceneError as error:
        print(f"Scene diversity report failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
