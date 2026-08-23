#!/usr/bin/env python3
"""Run the bounded Acoustic Runtime & Quality v1 benchmark corpus against
the real BirdNET adapter and print/save a report. Never opens or writes the
product database -- read-only against `tests/fixtures/acoustic/`.

    python scripts/evaluate_acoustic_quality.py
    python scripts/evaluate_acoustic_quality.py --json report.json
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from mockingbird.observation.acoustic_quality_benchmark import (  # noqa: E402
    evaluate_acoustic_quality,
    render_terminal_report,
)

DEFAULT_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "acoustic"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixtures-dir", type=Path, default=DEFAULT_FIXTURES_DIR,
        help="Directory containing the acoustic benchmark .wav fixtures (default: tests/fixtures/acoustic).",
    )
    parser.add_argument(
        "--min-confidence", type=float, default=None,
        help="Production confidence floor to score against (default: BirdNetAdapterConfig's own default).",
    )
    parser.add_argument(
        "--json", type=Path, default=None, help="Optional path to also write the full report as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    report = evaluate_acoustic_quality(
        args.fixtures_dir, production_min_confidence=args.min_confidence,
    )
    print(render_terminal_report(report))
    if args.json is not None:
        import json

        args.json.write_text(json.dumps(report.as_dict(), indent=2, default=str), encoding="utf-8")
        print(f"\nFull report written to {args.json}")
    if report.error_count == report.corpus_size:
        print(
            "\nNo clips were evaluable (missing fixtures and/or BirdNET runtime unavailable). "
            "See tests/fixtures/acoustic/PROVENANCE.md to regenerate fixtures locally.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
