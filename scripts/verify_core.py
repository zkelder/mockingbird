#!/usr/bin/env python3
"""Tier B -- Core milestone gate: the whole backend suite except `slow`.

Guarantees: every fast unit/pure-contract test (Tier A) plus every core
integration test (SQLite repository behavior, API route behavior,
Observation lifecycle, backup/restore, migrations, evidence persistence,
monitoring lifecycle) -- everything except the `slow`-marked minority
(real subprocess/process launches, real dependency installation, large
real-artifact hashing; see docs/test-suite-validation-tiers-contract.md).

Run this before calling a normal milestone/task complete, and for any
change touching more than one subsystem or any of the "preserve critical
contracts" areas in docs/test-suite-validation-tiers-contract.md, even if
the diff looks small.

Usage:
    python scripts/verify_core.py [extra pytest args]

Exit code is pytest's own exit code.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "not slow",
        *sys.argv[1:],
    ]
    print(f"[verify_core] {' '.join(command)}", file=sys.stderr)
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
