#!/usr/bin/env python3
"""Tier C -- Full software/release regression: the complete backend suite.

Guarantees: everything Tier B (Core) does, plus every `slow`-marked test --
real subprocess/process launches, real dependency installation into a real
site-packages, and large real-artifact hashing (see
docs/test-suite-validation-tiers-contract.md). This is a superset of plain
`pytest` with no marker filter; it exists so the tier's own meaning has a
name, not because the selection differs from an unfiltered run.

A `slow` test whose real prerequisite artifact (a local wheel cache, a
local model bundle) is absent on the current machine still `skip`s rather
than fails, exactly as before this milestone -- this tier never requires
real hardware, only whatever local caches happen to be present.

Reserve this for release-hardening completion, RC acceptance, cross-cutting
changes, or any change to packaging/dependency-closure/model-bundle code
(scripts/build_local_product.py, scripts/build_camera_node_artifact.py).
It is allowed to take substantially longer than Fast/Core -- that is by
design, not a defect to fix.

Usage:
    python scripts/verify_full.py [extra pytest args]

Exit code is pytest's own exit code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [sys.executable, "-m", "pytest", *sys.argv[1:]]
    print(f"[verify_full] {' '.join(command)}", file=sys.stderr)
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
