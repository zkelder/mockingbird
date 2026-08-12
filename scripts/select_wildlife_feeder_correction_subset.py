#!/usr/bin/env python3
"""Select the deterministic ~200-frame feeder correction subset (Multi-Scene
Backyard Domain Acquisition + Holdout v2 v1, task Section 1) from the
existing 700-frame Stage-3 Tranche A.

Prioritization only -- creates no human truth. Every selected row keeps its
inherited `review_status: "unreviewed"`/`training_eligible: False` from the
source tranche unchanged. See
docs/wildlife-detector-training-contract.md "Feeder correction subset v1".
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from mockingbird.training.wildlife_multiscene import (
    WildlifeMultiSceneError,
    feeder_subset_session_concentration,
    load_tranche_a,
    select_feeder_correction_subset,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tranche", type=Path, default=Path("data/training/wildlife-stage3/tranche-a.json"),
        help="Existing Stage-3 Tranche A manifest (scripts/build_wildlife_stage3_correction_tranche.py output).",
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/training/wildlife-feeder-subset/feeder-correction-subset-v1.json"),
    )
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    args = _args()
    tranche_payload = load_tranche_a(args.tranche)
    payload = select_feeder_correction_subset(tranche_payload)
    _write_json(args.output, payload)
    concentration = feeder_subset_session_concentration(payload)
    print(json.dumps({
        "output": str(args.output),
        "selected_count": payload["selected_count"],
        "targets": payload["targets"],
        "lanes": {lane: {"target": result["target"], **result["dedup"]} for lane, result in payload["lanes"].items()},
        "distinct_capture_sessions": payload["distinct_capture_sessions"],
        "session_concentration": concentration,
        "semantic_fingerprint": payload["semantic_fingerprint"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeMultiSceneError as error:
        print(f"Feeder correction subset selection failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
