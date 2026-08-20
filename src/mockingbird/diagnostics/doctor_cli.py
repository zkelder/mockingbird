"""CLI entry point for `python -m mockingbird doctor`.

Mirrors the existing `python -m mockingbird <subcommand>` dispatch
convention in `__main__.py` (a lazy import + `run(argv)` returning an int
exit code) rather than inventing a new `argparse.add_subparsers()` pattern
-- see "CLI" in docs/mockingbird-doctor-operational-health-contract.md.
"""

from __future__ import annotations

import argparse

from mockingbird.diagnostics.doctor import (
    DoctorReport,
    DoctorStatus,
    doctor_exit_code,
    run_doctor,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mockingbird doctor",
        description="Check whether this MockingBird installation is healthy enough to observe wildlife.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the report as machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Per-check bounded timeout in seconds (default: 5s; 15s for the detector model check).",
    )
    return parser


def render_human(report: DoctorReport) -> str:
    """Calm, concise default rendering -- see the "CLI" worked example in
    docs/mockingbird-doctor-operational-health-contract.md."""

    lines = ["MockingBird Doctor", ""]
    for check in report.checks:
        lines.append(f"{check.status.value:<7} {check.component}")
        if check.status in (DoctorStatus.WARN, DoctorStatus.FAIL, DoctorStatus.SKIPPED):
            if check.summary:
                lines.append(f"      {check.summary}")
            if check.detail:
                lines.append(f"      {check.detail}")
            if check.user_action:
                lines.append(f"      Action: {check.user_action}")
    lines.append("")
    lines.append(f"Overall: {report.overall_status.value}")
    lines.append(f"Checked in {report.duration_ms:.0f}ms.")
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    run_kwargs = {}
    if args.timeout is not None:
        run_kwargs["timeout_seconds"] = args.timeout
    report = run_doctor(**run_kwargs)
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(render_human(report))
    return doctor_exit_code(report)
