#!/usr/bin/env python3
"""CLI for the Source-Resolution + Multi-Frame Species Evidence v1 governed
benchmark (see docs/source-resolution-multi-frame-species-evidence-contract.md
and src/mockingbird/observation/source_resolution_species_benchmark.py).

Loads a real cohort of paired native-resolution/derived-crop evidence from
an existing product database (always via a safe, disposable copy -- never
opens the real database file directly, see `copy_database_for_read_only_
analysis`), builds the deterministic comparison report, and writes it as
JSON plus a short plain-language summary.

Usage:
    python scripts/benchmark_source_resolution_species_evidence.py \\
        --database data/mockingbird.sqlite3 \\
        --media-root . \\
        --output data/benchmarks/source-resolution-species-evidence

No live species classifier is invoked -- this benchmark deliberately
reports only model-independent geometry/eligibility/candidate-availability
facts when a real model is unavailable (the normal case for a development
sandbox with no packaged BioCLIP weights); see the module docstring's
"Honesty boundary".
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mockingbird.observation.source_resolution_species_benchmark import (
    build_source_resolution_benchmark_report,
    summarize_for_decision,
)
from mockingbird.observation.source_resolution_species_benchmark_io import (
    copy_database_for_read_only_analysis,
    load_resolution_evidence_pairs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="Path to a real product sqlite database.")
    parser.add_argument("--media-root", type=Path, default=Path("."), help="Repo root media paths are relative to.")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for the JSON report.")
    parser.add_argument("--max-pairs", type=int, default=None, help="Optional bound on cohort size.")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="mockingbird-source-resolution-benchmark-") as workspace:
        copy_path = copy_database_for_read_only_analysis(args.database, workspace=Path(workspace))
        pairs, load_summary = load_resolution_evidence_pairs(
            copy_path, media_root=args.media_root, max_pairs=args.max_pairs,
        )

    report = build_source_resolution_benchmark_report(
        pairs,
        real_data_source=f"{args.database} (real product database, read-only copy)",
        live_model_inference_available=False,
    )
    summary = summarize_for_decision(report)

    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "source-resolution-species-benchmark-report.json"
    report_path.write_text(
        json.dumps(
            {
                "load_summary": {
                    "total_candidate_rows": load_summary.total_candidate_rows,
                    "usable_pairs": load_summary.usable_pairs,
                    "skipped_missing_dimensions": load_summary.skipped_missing_dimensions,
                    "skipped_missing_box": load_summary.skipped_missing_box,
                    "skipped_missing_parent": load_summary.skipped_missing_parent,
                },
                "report": report.as_dict(),
                "summary": summary,
            },
            indent=2, sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"Wrote report to {report_path}")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
