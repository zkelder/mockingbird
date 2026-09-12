#!/usr/bin/env python3
"""Manual Import Evidence Integrity v1: a bounded maintenance command that
repairs the missing `VisitEvidenceLink` on a Visit created by a manual or
folder media import (`/api/media/import`, `/api/media/folder-import`)
before that fix -- see docs/manual-import-evidence-integrity-v1-contract.md.

## What this does and does not do

This never guesses. It only creates a `VisitEvidenceLink` for a Visit whose
`representative_media_path` resolves, unambiguously, to exactly one known
media asset that the established evidence materializer
(`ProductRepository._ensure_visit_evidence_links` -- the same one
`curate_visit_evidence`, `create_refined_visit_crop`,
`promote_visit_crop_history`, and `split_visit` already rely on) can turn
into real evidence. A Visit whose path matches zero or more than one asset,
whose Event no longer exists, or for which that materializer still finds
nothing derivable, is reported and left untouched -- never silently
assigned. It never deletes anything, never rewrites `representative_media_
path` or any reviewed truth, and a Visit that already has a
VisitEvidenceLink (from a prior run of this repair, or because it no
longer needs one) is reported `already_linked` and left alone.

## Talking to the product

This talks to a *running* MockingBird instance over its real HTTP API
(`GET /api/media/evidence-link-repair-report`,
`POST /api/media/evidence-link-repair`) rather than opening the SQLite file
directly, so it never races the live server's own connection/transaction
handling and reuses exactly the same validated repository logic a real
product action would -- the same design this repo's other maintenance
command, scripts/repair_review_label_provenance.py, already established.
Point `--base-url` at any reachable instance.

## Usage

    python scripts/repair_import_evidence_links.py --base-url http://127.0.0.1:8000
        # dry run: reports every candidate and what would happen, changes nothing

    python scripts/repair_import_evidence_links.py --base-url http://127.0.0.1:8000 --apply
        # applies the repair to every unambiguous candidate

Always run without `--apply` first and inspect the report. Any entry whose
`outcome` starts with `ambiguous_` is never touched by `--apply` either --
it stays visible for manual review.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class RepairCommandError(RuntimeError):
    """A bounded failure reason for this maintenance command."""


def _http_json(method: str, url: str, *, payload: dict | None = None, timeout: float = 30.0) -> tuple[int, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return response.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = body
        return error.code, parsed
    except urllib.error.URLError as error:
        raise RepairCommandError(f"could not reach {url}: {error}") from error


def fetch_report(base_url: str) -> dict:
    """Read-only: the current repair report. Never mutates anything."""

    status, body = _http_json("GET", f"{base_url}/api/media/evidence-link-repair-report")
    if status != 200 or not isinstance(body, dict):
        raise RepairCommandError(f"unexpected GET .../evidence-link-repair-report response: {status} {body!r}")
    return body


def apply_repair(base_url: str) -> dict:
    status, body = _http_json(
        "POST",
        f"{base_url}/api/media/evidence-link-repair",
        payload={"confirm": True},
    )
    if status != 200 or not isinstance(body, dict):
        raise RepairCommandError(f"unexpected POST .../evidence-link-repair response: {status} {body!r}")
    return body


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"default: {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually create the missing links. Without this flag, only a report is produced.",
    )
    args = parser.parse_args(argv)

    try:
        report = apply_repair(args.base_url) if args.apply else fetch_report(args.base_url)
    except RepairCommandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    print(json.dumps({"base_url": args.base_url, **report}, indent=2, sort_keys=True))

    ambiguous = [entry for entry in report.get("entries", []) if str(entry.get("outcome", "")).startswith("ambiguous_")]
    if ambiguous:
        print(
            f"note: {len(ambiguous)} Visit(s) left for manual review (ambiguous_* outcome) -- see entries above.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
