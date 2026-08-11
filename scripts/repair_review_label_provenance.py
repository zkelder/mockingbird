#!/usr/bin/env python3
"""Review Decision Provenance / Truth Boundary v1, Part 8: a bounded
maintenance command that repairs the durable provenance of ReviewLabel rows
whose own `notes` already self-disclose non-human review origin (see
docs/review-decision-provenance-contract.md).

## What this does and does not do

This never guesses. It only acts on a ReviewLabel row whose own `notes`
field already contains one of this codebase's established non-human
disclosure markers (`mockingbird.review_provenance.
NON_HUMAN_DISCLOSURE_MARKERS` -- "agent", "claude", "language model", ...;
the same bounded, documented vocabulary `evaluation_governance.py` already
uses, not a content classifier). A matched row is reclassified to explicit
`agent_diagnostic` provenance with a named `reviewer_identity`; the product
repository then re-derives the resulting Visit/Event truth state from
scratch (see `ProductRepository.reclassify_review_label_provenance`), so a
row that turns out non-authoritative can no longer misrepresent its target
as "reviewed". It never deletes a ReviewLabel row, its `label`, or its
`notes` -- "Do not delete or pretend they never happened" applies to a
maintenance repair exactly as it does to a live product action. It never
touches a row that does not self-disclose non-human origin -- "Do not
rewrite unrelated historical ReviewLabels".

## Talking to the product

This talks to a *running* MockingBird instance over its real HTTP API
(`GET /api/review-labels`, `POST /api/review-labels/{id}/reclassify-
provenance`) rather than opening the SQLite file directly, so it never
races the live server's own connection/transaction handling and reuses
exactly the same validated repository logic a real product action would.
Point `--base-url` at any reachable instance (a local dev server, or a
paired Windows dev deployment reachable through whatever interop channel
the operator's environment provides -- this script has no Windows-specific
code of its own, matching the existing boundary that keeps sandbox/deploy-
specific interop mechanics out of general product tooling; see
docs/windows-dev-deployment-design.md).

## Usage

    python scripts/repair_review_label_provenance.py --base-url http://127.0.0.1:8000
        # dry run: reports matches, changes nothing

    python scripts/repair_review_label_provenance.py --base-url http://127.0.0.1:8000 --apply
        # applies the repair to every matched row

    python scripts/repair_review_label_provenance.py --apply --review-label-id review-label-001
        # restrict to specific, already-known id(s)

Always run without `--apply` first and inspect the report.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import sys
import urllib.error
import urllib.request

from mockingbird.review_provenance import discloses_non_human_review

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_REVIEWER_IDENTITY = "claude-agent-visual-inspection-2026-08-10"


class RepairCommandError(RuntimeError):
    """A bounded failure reason for this maintenance command."""


@dataclass(frozen=True)
class RepairResult:
    review_label_id: str
    target_type: str
    target_id: str
    label: str
    notes_excerpt: str
    previous_review_origin: str | None
    applied: bool
    new_review_origin: str | None = None
    error: str | None = None


def _http_json(method: str, url: str, *, payload: dict | None = None, timeout: float = 15.0) -> tuple[int, object]:
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


def find_candidates(base_url: str) -> list[dict]:
    """Read-only: every currently-effective ReviewLabel whose own notes
    self-disclose non-human review origin. Never mutates anything."""

    status, body = _http_json("GET", f"{base_url}/api/review-labels")
    if status != 200 or not isinstance(body, list):
        raise RepairCommandError(f"unexpected GET /api/review-labels response: {status} {body!r}")
    return [label for label in body if discloses_non_human_review(label.get("notes"))]


def repair_one(base_url: str, label: dict, *, reviewer_identity: str, apply: bool) -> RepairResult:
    notes = label.get("notes") or ""
    base = RepairResult(
        review_label_id=label["id"],
        target_type=label["target_type"],
        target_id=label["target_id"],
        label=label["label"],
        notes_excerpt=notes[:120],
        previous_review_origin=label.get("review_origin"),
        applied=False,
    )
    if not apply:
        return base

    status, body = _http_json(
        "POST",
        f"{base_url}/api/review-labels/{label['id']}/reclassify-provenance",
        payload={
            "review_origin": "agent_diagnostic",
            "reviewer_identity": reviewer_identity,
            "expected_current_review_origin": label.get("review_origin"),
        },
    )
    if status != 200:
        return RepairResult(**{**asdict(base), "error": f"{status} {body!r}"})
    new_origin = body.get("review_origin") if isinstance(body, dict) else None
    return RepairResult(**{**asdict(base), "applied": True, "new_review_origin": new_origin})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"default: {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--reviewer-identity",
        default=DEFAULT_REVIEWER_IDENTITY,
        help="Named identity recorded on every repaired row.",
    )
    parser.add_argument(
        "--review-label-id",
        action="append",
        default=None,
        help="Restrict to this id (repeatable). Default: every currently-effective row matching the disclosure scan.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write the repair. Without this flag, only a report is produced.",
    )
    args = parser.parse_args(argv)

    try:
        candidates = find_candidates(args.base_url)
    except RepairCommandError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.review_label_id:
        wanted = set(args.review_label_id)
        candidates = [label for label in candidates if label["id"] in wanted]

    results = [
        repair_one(args.base_url, label, reviewer_identity=args.reviewer_identity, apply=args.apply)
        for label in candidates
    ]

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "base_url": args.base_url,
        "apply": args.apply,
        "matched_count": len(results),
        "repaired_count": sum(1 for result in results if result.applied and result.error is None),
        "results": [asdict(result) for result in results],
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if any(result.error for result in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
