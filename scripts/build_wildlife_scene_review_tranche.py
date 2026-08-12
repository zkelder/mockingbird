#!/usr/bin/env python3
"""Build a scene- or session-scoped review tranche from real multi-scene
capture manifests (Multi-Scene Backyard Domain Acquisition + Holdout v2 v1,
task Section 7).

Scans every `capture-session-manifest.json` under `--scene-manifest-root`
for frames carrying an explicit `scene_id` (see `temporal-capture
--scene-id`), filters to one scene and/or one session, and writes a
tranche-shaped JSON ready for the *existing* browser localization reviewer
-- not a second review system:

    .venv/bin/python -m mockingbird stage3-tranche-review-build \\
      --tranche <this script's --output> --output <review-directory>

This script never opens the product database, starts a camera/worker, or
creates human truth.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from mockingbird.training.wildlife_multiscene import (
    WildlifeMultiSceneError,
    build_scene_review_tranche,
    scan_scene_manifests,
)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scene-manifest-root", type=Path, default=Path("data/field-acceptance"),
        help="Root directory to recursively search for capture-session-manifest.json files.",
    )
    parser.add_argument("--scene-id", default=None, help="Restrict to this physical scene.")
    parser.add_argument("--session-id", default=None, help="Restrict to this capture session.")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    args = _args()
    if not args.scene_manifest_root.is_dir():
        raise WildlifeMultiSceneError("scene_manifest_root_missing")
    manifest_paths = sorted(args.scene_manifest_root.glob("**/capture-session-manifest.json"))
    records = scan_scene_manifests(manifest_paths)
    payload = build_scene_review_tranche(records, scene_id=args.scene_id, session_id=args.session_id)
    _write_json(args.output, payload)
    print(json.dumps({
        "output": str(args.output),
        "tranche_id": payload["tranche_id"],
        "scene_id": payload["scene_id"],
        "session_id": payload["session_id"],
        "frame_count": payload["frame_count"],
        "semantic_fingerprint": payload["semantic_fingerprint"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeMultiSceneError as error:
        print(f"Scene review tranche build failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
