#!/usr/bin/env python3
"""Read-only Stage-3 Tranche A readiness/accounting report.

Cross-references the Tranche A selection manifest against the reviewer's
own `annotation.json` (never mutating either) and reports exactly what the
task requires: total tranche size, reviewed/remaining, positives/negatives/
ambiguous, boxes, train-/validation-candidate reviewed counts, size/
difficulty distribution, distinct encounter/session counts, and
contamination status -- plus a derived (not merely total-count) readiness
recommendation. Never declares Stage-3 trainable from total review count
alone: readiness requires each lane, and each split side, to independently
clear its own usable-reviewed bar, on top of the existing general dataset-
sufficiency floor `temporal_annotation.classify_export_sufficiency` already
enforces for every other reviewed-temporal-data export in this codebase.

This script never opens the product database, starts a camera/worker, or
writes any file.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

from mockingbird.observation.temporal_annotation import (
    AnnotationSet,
    TemporalAnnotationError,
    classify_export_sufficiency,
)
from mockingbird.observation.temporal_capture import TemporalCaptureError
from mockingbird.observation.temporal_review_io import load_annotation_set, load_capture_manifest
from mockingbird.training.wildlife_stage3_tranche import (
    LOCAL_TRAIN_CANDIDATE,
    LOCAL_VALIDATION_CANDIDATE,
)

# Derived from tranche composition, not a bare review-count floor (task
# requirement): each lane, and each split side, must independently clear
# this fraction of its own real target before Stage-3 is called ready. 0.8
# applied to the 325/275/100 lane targets lands at ~560 usable examples --
# consistent with, but derived independently of, the task's own suggested
# "around 500-600" default.
MIN_USABLE_FRACTION_PER_LANE = 0.8
MIN_USABLE_FRACTION_PER_SPLIT_SIDE = 0.8


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tranche", type=Path, default=Path("data/training/wildlife-stage3/tranche-a.json"))
    parser.add_argument("--review", type=Path, default=Path("data/training/wildlife-stage3/tranche-a-review"))
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of the human summary.")
    return parser.parse_args()


def _frame_annotation(annotations: AnnotationSet, frame_id: str):
    return annotations.frame(frame_id)


def build_readiness_report(tranche_payload: dict[str, Any], annotations: AnnotationSet) -> dict[str, Any]:
    frames = tranche_payload["frames"]
    total = len(frames)

    unreviewed = positive_usable = negative_usable = ambiguous = yes_but_unscorable = 0
    boxes = 0
    difficulty_tag_counts: Counter[str] = Counter()
    box_distance_counts: Counter[str] = Counter()
    by_lane: dict[str, dict[str, int]] = {}
    by_split: dict[str, dict[str, int]] = {}
    reviewed_sessions: set[str] = set()
    all_sessions: set[str] = set()

    for row in frames:
        lane = row["stage3_target_lane"]
        split = row.get("split_candidate", "unknown")
        all_sessions.add(row["capture_session_id"])
        lane_counts = by_lane.setdefault(lane, {"target": 0, "usable_reviewed": 0, "reviewed": 0})
        split_counts = by_split.setdefault(split, {"usable_reviewed": 0, "reviewed": 0})

        annotation = _frame_annotation(annotations, row["frame_id"])
        if annotation is None or not annotation.is_reviewed:
            unreviewed += 1
            continue

        lane_counts["reviewed"] += 1
        split_counts["reviewed"] += 1
        reviewed_sessions.add(row["capture_session_id"])
        difficulty_tag_counts.update(getattr(annotation, "difficulty_tags", ()) or ())

        if annotation.whole_frame_truth == "ambiguous":
            ambiguous += 1
            continue
        if annotation.whole_frame_truth == "yes" and annotation.yes_but_unscorable:
            yes_but_unscorable += 1
            continue
        if not annotation.is_scorable:
            continue  # defensive: any other non-scorable reviewed state, never silently counted as usable

        if annotation.whole_frame_truth == "yes":
            positive_usable += 1
            boxes += len(annotation.boxes)
            for box in annotation.boxes:
                if box.distance:
                    box_distance_counts[box.distance] += 1
        elif annotation.whole_frame_truth == "no":
            negative_usable += 1
        lane_counts["usable_reviewed"] += 1
        split_counts["usable_reviewed"] += 1

    for lane, target in tranche_payload["lane_targets"].items():
        by_lane.setdefault(lane, {"target": 0, "usable_reviewed": 0, "reviewed": 0})["target"] = target

    usable_total = positive_usable + negative_usable
    lane_bar_status = {
        lane: {
            "target": counts["target"],
            "usable_reviewed": counts["usable_reviewed"],
            "reviewed": counts["reviewed"],
            "minimum_required": round(counts["target"] * MIN_USABLE_FRACTION_PER_LANE),
            "meets_bar": counts["usable_reviewed"] >= round(counts["target"] * MIN_USABLE_FRACTION_PER_LANE),
        }
        for lane, counts in by_lane.items()
    }
    split_targets = {
        LOCAL_TRAIN_CANDIDATE: tranche_payload["split"].get("train_frame_count", 0),
        LOCAL_VALIDATION_CANDIDATE: tranche_payload["split"].get("validation_frame_count", 0),
    }
    split_bar_status = {
        split: {
            "target": split_targets.get(split, 0),
            "usable_reviewed": by_split.get(split, {}).get("usable_reviewed", 0),
            "reviewed": by_split.get(split, {}).get("reviewed", 0),
            "minimum_required": round(split_targets.get(split, 0) * MIN_USABLE_FRACTION_PER_SPLIT_SIDE),
            "meets_bar": by_split.get(split, {}).get("usable_reviewed", 0)
            >= round(split_targets.get(split, 0) * MIN_USABLE_FRACTION_PER_SPLIT_SIDE),
        }
        for split in (LOCAL_TRAIN_CANDIDATE, LOCAL_VALIDATION_CANDIDATE)
    }

    generic_sufficiency = classify_export_sufficiency(
        positive_usable, negative_usable,
        scene_groups=len(reviewed_sessions), sequences=len(reviewed_sessions),
    )
    reasons: list[str] = list(generic_sufficiency["reasons"])
    for lane, status in lane_bar_status.items():
        if not status["meets_bar"]:
            reasons.append(
                f"lane {lane}: {status['usable_reviewed']} usable-reviewed < "
                f"{status['minimum_required']} required ({int(MIN_USABLE_FRACTION_PER_LANE * 100)}% of target {status['target']})"
            )
    for split, status in split_bar_status.items():
        if not status["meets_bar"]:
            reasons.append(
                f"split {split}: {status['usable_reviewed']} usable-reviewed < "
                f"{status['minimum_required']} required ({int(MIN_USABLE_FRACTION_PER_SPLIT_SIDE * 100)}% of target {status['target']})"
            )
    contamination_passed = bool(tranche_payload.get("contamination", {}).get("passed"))
    if not contamination_passed:
        reasons.append("contamination check on the selected tranche did not pass")

    return {
        "tranche_id": tranche_payload.get("tranche_id"),
        "total_tranche_size": total,
        "reviewed": total - unreviewed,
        "remaining": unreviewed,
        "positives_usable": positive_usable,
        "negatives_usable": negative_usable,
        "ambiguous": ambiguous,
        "yes_but_unscorable": yes_but_unscorable,
        "usable_total": usable_total,
        "boxes": boxes,
        "by_lane": lane_bar_status,
        "by_split_candidate": split_bar_status,
        "difficulty_tag_distribution": dict(sorted(difficulty_tag_counts.items())),
        "box_distance_distribution": dict(sorted(box_distance_counts.items())),
        "distinct_sessions_in_tranche": len(all_sessions),
        "distinct_sessions_with_a_reviewed_frame": len(reviewed_sessions),
        "generic_dataset_sufficiency": generic_sufficiency,
        "contamination_passed": contamination_passed,
        "stage3_training_ready": not reasons,
        "not_ready_reasons": reasons,
    }


def _human_summary(report: dict[str, Any]) -> str:
    lines = [
        f"Stage-3 Tranche A readiness -- {report['tranche_id']}",
        f"  total={report['total_tranche_size']} reviewed={report['reviewed']} remaining={report['remaining']}",
        f"  usable positives={report['positives_usable']} usable negatives={report['negatives_usable']} "
        f"ambiguous={report['ambiguous']} yes_but_unscorable={report['yes_but_unscorable']} boxes={report['boxes']}",
        f"  distinct sessions: {report['distinct_sessions_with_a_reviewed_frame']} reviewed of "
        f"{report['distinct_sessions_in_tranche']} in tranche",
        f"  contamination_passed={report['contamination_passed']}",
        "  by lane:",
    ]
    for lane, status in sorted(report["by_lane"].items()):
        lines.append(
            f"    {lane}: usable_reviewed={status['usable_reviewed']}/{status['target']} "
            f"(need >= {status['minimum_required']}) meets_bar={status['meets_bar']}"
        )
    lines.append("  by split candidate:")
    for split, status in sorted(report["by_split_candidate"].items()):
        lines.append(
            f"    {split}: usable_reviewed={status['usable_reviewed']}/{status['target']} "
            f"(need >= {status['minimum_required']}) meets_bar={status['meets_bar']}"
        )
    if report["difficulty_tag_distribution"]:
        lines.append(f"  difficulty tags: {report['difficulty_tag_distribution']}")
    if report["box_distance_distribution"]:
        lines.append(f"  box distance: {report['box_distance_distribution']}")
    lines.append(f"  STAGE3_TRAINING_READY={report['stage3_training_ready']}")
    if report["not_ready_reasons"]:
        lines.append("  not ready because:")
        lines.extend(f"    - {reason}" for reason in report["not_ready_reasons"])
    return "\n".join(lines)


def main() -> int:
    args = _args()
    try:
        tranche_payload = json.loads(args.tranche.read_text(encoding="utf-8"))
        manifest = load_capture_manifest(args.review)
        annotations = load_annotation_set(args.review)
    except (OSError, json.JSONDecodeError) as error:
        print(f"Stage-3 readiness report failed: unreadable input ({error})")
        return 2
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        print(f"Stage-3 readiness report failed: {error}")
        return 2
    if manifest.get("source_tranche_fingerprint") != tranche_payload.get("semantic_fingerprint"):
        print(
            "Stage-3 readiness report failed: the review directory's own manifest was not built from "
            "this exact tranche file (fingerprint mismatch)."
        )
        return 3

    report = build_readiness_report(tranche_payload, annotations)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(_human_summary(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
