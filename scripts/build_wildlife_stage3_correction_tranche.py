#!/usr/bin/env python3
"""Build Stage-3 local domain-correction Tranche A: ~700 deterministically
prioritized, deduplicated, split-assigned frames selected from the existing,
already-governed 2,000-frame local-correction queue.

This is prioritization only -- see mockingbird.training.wildlife_stage3_tranche
module docstring and docs/wildlife-detector-training-contract.md. Every
selected row remains unreviewed and training-ineligible until a named human
completes full-frame review through the Stage-3 tranche reviewer
(`stage3-tranche-review-build`).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from mockingbird.training.wildlife import canonical_fingerprint, verify_frozen_benchmark
from mockingbird.training.wildlife_stage3_tranche import (
    LANE_TARGETS,
    SEED,
    SOURCE_QUEUE_ID,
    TRANCHE_ID,
    WildlifeStage3TrancheError,
    assert_no_split_leakage,
    assign_local_split,
    check_frozen_contamination,
    distinct_scenes,
    frozen_contamination_content_hashes,
    holdout_v2_content_hashes,
    load_queue,
    select_tranche,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queue", type=Path,
        default=Path("data/training/wildlife-stage2/local-correction-queue.json"),
        help="Existing deterministic 2,000-frame local-correction queue.",
    )
    parser.add_argument(
        "--holdout-manifest", type=Path,
        default=Path("data/evaluations/detector-promotion-v1/corpus-manifest.json"),
        help="Frozen 75-image checksum-pinned benchmark manifest (never for training).",
    )
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/training/wildlife-stage3/tranche-a.json"),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    return parser.parse_args()


def build_tranche(*, queue_path: Path, holdout_manifest_path: Path, repository_root: Path, seed: int) -> dict:
    queue_payload = load_queue(queue_path)
    manifest_paths = {Path(row["capture_manifest"]) for row in queue_payload["frames"]}
    holdout_v2_hashes = frozenset(holdout_v2_content_hashes(manifest_paths))

    # Computed once (real, checksum-verified, 75 frames) and reused for both
    # the pre-selection exclusion scan and the final post-selection proof
    # below -- `verify_frozen_benchmark` itself hashes every frozen image,
    # so calling it twice would be pure waste.
    holdout = verify_frozen_benchmark(holdout_manifest_path.resolve(), repository_root=repository_root.resolve())

    # Excluded *before* selection, not only checked after: the frozen
    # 75-image benchmark shares this corpus's own physical camera/scene, so
    # a real (not merely hash-coincidental) near-duplicate rate is expected
    # -- see the module docstring on `frozen_contamination_content_hashes`.
    # Scanning the full pre-selection queue means a contaminated row's lane
    # slot is naturally backfilled by the next-best real candidate.
    frozen_contamination_hashes, contamination_prescan = frozen_contamination_content_hashes(
        queue_payload["frames"], holdout=holdout,
    )

    selection = select_tranche(
        queue_payload, holdout_v2_hashes=holdout_v2_hashes,
        frozen_contamination_hashes=frozenset(frozen_contamination_hashes), lane_targets=LANE_TARGETS,
    )
    selected_rows = selection["frames"]

    split_summary = assign_local_split(selected_rows, seed=seed)
    assert_no_split_leakage(selected_rows)

    # Final, honest proof step over the already-cleaned selection -- must
    # pass given the pre-scan above; a failure here would mean the pre-scan
    # and this verification disagree, which is itself a bug worth crashing
    # loudly on rather than shipping silently.
    contamination = check_frozen_contamination(
        selected_rows, holdout=holdout,
    )
    if not contamination["passed"]:
        raise WildlifeStage3TrancheError("stage3_tranche_contamination_detected")

    scenes = distinct_scenes(selected_rows)

    payload = {
        "schema_version": 1,
        "tranche_id": TRANCHE_ID,
        "source_queue_id": SOURCE_QUEUE_ID,
        "source_queue_fingerprint": queue_payload["semantic_fingerprint"],
        "seed": seed,
        "lane_targets": LANE_TARGETS,
        "priority_tier_order_note": (
            "task steps 1+2 (known detector miss / off-target localization failure) are merged into "
            "known_detector_miss_or_localization_failure; task steps 6+7 (branches/vegetation / shadows/pavement) "
            "are merged into vegetation_or_shadow_confusor -- see the module docstring for why."
        ),
        "candidate_count_before_selection": len(queue_payload["frames"]),
        "excluded_holdout_v2_hashes": selection["excluded_holdout_v2_hashes"],
        "excluded_frozen_contamination_hashes": selection["excluded_frozen_contamination_hashes"],
        "frozen_contamination_prescan": contamination_prescan,
        "lanes": selection["lanes"],
        "selected_count": len(selected_rows),
        "distinct_capture_sessions": scenes["distinct_capture_sessions"],
        "frames_per_session": scenes["frames_per_session"],
        "split": split_summary,
        "contamination": contamination,
        "truth_policy": (
            "prioritization only; every row remains unreviewed and training-ineligible until named human "
            "full-frame review completes through the Stage-3 tranche reviewer"
        ),
        "creates_product_truth": False,
        "frames": selected_rows,
    }
    payload["semantic_fingerprint"] = canonical_fingerprint(payload)
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    args = _args()
    payload = build_tranche(
        queue_path=args.queue.resolve(), holdout_manifest_path=args.holdout_manifest,
        repository_root=args.repository_root, seed=args.seed,
    )
    _write_json(args.output.resolve(), payload)
    print(json.dumps({
        "output": str(args.output),
        "candidate_count_before_selection": payload["candidate_count_before_selection"],
        "excluded_holdout_v2_hashes": payload["excluded_holdout_v2_hashes"],
        "excluded_frozen_contamination_hashes": payload["excluded_frozen_contamination_hashes"],
        "selected_count": payload["selected_count"],
        "lanes": {
            lane: {"target": result["target"], **result["dedup"]}
            for lane, result in payload["lanes"].items()
        },
        "distinct_capture_sessions": payload["distinct_capture_sessions"],
        "split": payload["split"],
        "contamination_passed": payload["contamination"]["passed"],
        "semantic_fingerprint": payload["semantic_fingerprint"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeStage3TrancheError as error:
        print(f"Stage-3 tranche build failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
