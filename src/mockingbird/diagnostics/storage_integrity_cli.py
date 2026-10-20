"""CLI entry point for `python -m mockingbird storage-integrity`.

Follows the `python -m mockingbird <subcommand>` convention (lazy import +
`run(argv)` returning an exit code), like `doctor`. The default operation is
report-only; moving anything requires explicit `--quarantine ... --yes`.
Contract: docs/orphan-media-integrity-recovery-contract.md.

Exit codes: 0 clean (or an explicit action completed), 1 unowned media found,
2 the check could not finish (never conflated with clean), 3 an explicit action
did not fully succeed.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from mockingbird.diagnostics.doctor import resolve_doctor_environment
from mockingbird.storage.database import create_database_engine
from mockingbird.storage.orphan_media import (
    list_orphan_quarantine_batches,
    quarantine_orphans,
    restore_orphan_quarantine_batch,
    scan_orphan_media,
)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mockingbird storage-integrity",
        description=(
            "Check whether saved media in managed storage is linked to an observation. "
            "Report-only unless --quarantine or --restore is given with --yes."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument(
        "--quarantine", action="append", default=[], metavar="RELATIVE_PATH",
        help="Move this unowned file (path relative to the managed media folder, as reported) to the recovery folder. Repeatable; requires --yes.",
    )
    parser.add_argument("--restore", metavar="BATCH_ID", help="Move a recovery batch back to where its files were. Requires --yes.")
    parser.add_argument("--list-recovery", action="store_true", help="List recent recovery batches.")
    parser.add_argument("--yes", action="store_true", help="Confirm a move or restore.")
    return parser


def _emit(payload: dict, *, as_json: bool, lines: list[str]) -> None:
    print(json.dumps(payload, indent=2, default=str, sort_keys=True) if as_json else "\n".join(lines))


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)
    environment = resolve_doctor_environment()
    engine = create_database_engine(environment.db_url)
    try:
        if args.list_recovery:
            batches = list_orphan_quarantine_batches(environment.media_root)
            _emit(
                {"batches": [asdict(b) for b in batches]}, as_json=args.json,
                lines=[f"{b.batch_id}  moved={b.moved_count} restored={b.restored_count} failed={b.failed_count}" for b in batches]
                or ["No recovery batches."],
            )
            return 0
        if args.restore:
            if not args.yes:
                print("Restoring moves files; re-run with --yes to confirm.")
                return 3
            restored = restore_orphan_quarantine_batch(environment.media_root, args.restore)
            _emit(
                asdict(restored), as_json=args.json,
                lines=[f"Restore {restored.status}: {restored.restored_count} restored, {restored.conflict_count} conflicts, {restored.failed_count} failed."],
            )
            return 0 if restored.status == "completed" else 3
        if args.quarantine:
            if not args.yes:
                print("Moving files to the recovery folder requires --yes. Nothing was changed.")
                return 3
            result = quarantine_orphans(
                engine, environment.media_root, args.quarantine, relative_base=environment.runtime_home
            )
            _emit(
                asdict(result), as_json=args.json,
                lines=[
                    f"Quarantine {result.status}: {result.moved_count} moved, {result.skipped_count} skipped, {result.failed_count} failed."
                    + (f" Batch {result.batch_id}." if result.batch_id else "")
                    + (f" Refused: {result.refusal_code}." if result.refusal_code else "")
                ],
            )
            return 0 if result.status == "completed" else 3
        report = scan_orphan_media(engine, environment.media_root, relative_base=environment.runtime_home)
        payload = {
            "status": report.status, "complete": report.complete,
            "files_examined": report.files_examined, "owned_files": report.owned_files,
            "orphan_count": report.orphan_count, "orphan_bytes": report.orphan_bytes,
            "recently_written_count": report.recently_written_count,
            "unsafe_entry_count": report.unsafe_entry_count,
            "excluded_counts": report.excluded_counts, "incomplete_reasons": report.incomplete_reasons,
            "findings_truncated": report.findings_truncated,
            "findings": [
                {"relative_path": f.relative_path, "size_bytes": f.size_bytes, "kind": f.kind} for f in report.findings
            ],
        }
        lines = [f"Storage integrity: {report.status}", f"  files examined: {report.files_examined}, owned: {report.owned_files}"]
        if report.status == "incomplete":
            lines.append(f"  could not finish: {', '.join(report.incomplete_reasons)}")
        lines.extend(f"  {f.kind}: {f.relative_path} ({f.size_bytes} bytes)" for f in report.findings)
        _emit(payload, as_json=args.json, lines=lines)
        return {"clean": 0, "orphans_found": 1, "incomplete": 2}[report.status]
    finally:
        engine.dispose()
