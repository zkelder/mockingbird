"""Focused before/after measurement for the Review Queue's own requests.

Review Queue Scale Closure v1.

`benchmark_release_performance.py` measures the whole product and is the
right tool for "did anything regress". It is also slow at a large library,
precisely because the unbounded Review Queue shapes it measures take tens
of seconds each -- which is the thing this milestone is about. This script
measures only the requests the Review Queue and the app shell actually
make, so a before/after pair at two workload profiles is affordable.

It reuses that script's own server, client and SQL-counting machinery
rather than reimplementing them, so the numbers are produced exactly the
same way: a real packaged-shape server process over real HTTP for latency
and bytes, and an in-process ASGI transport with an engine hook for
statement counts (a structural measurement whose timing is deliberately
not reported).

Operations whose route does not exist in the tree being measured -- which
is the normal case when pointing this at the pre-milestone baseline --
record their 404 and are reported as absent, not silently skipped.

Usage:

    python scripts/benchmark_review_queue_scale.py --root /tmp/mb-perf-b \\
        --label before --json before.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import runpy
import statistics
import sys
import time

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:  # pragma: no cover - import plumbing
    sys.path.insert(0, str(_ROOT / "src"))

_RELEASE_BENCHMARK = runpy.run_path(
    str(Path(__file__).resolve().parent / "benchmark_release_performance.py")
)
Operation = _RELEASE_BENCHMARK["Operation"]
count_sql_statements = _RELEASE_BENCHMARK["count_sql_statements"]
environment_report = _RELEASE_BENCHMARK["environment_report"]
_Server = _RELEASE_BENCHMARK["_Server"]
_free_port = _RELEASE_BENCHMARK["_free_port"]
_Client = _RELEASE_BENCHMARK["_Client"]


def review_queue_operations() -> list[Operation]:
    """Exactly what the Review Queue and the app shell request, before and after.

    The two `before` shapes are listed first because they are what the
    product used to do on mount: the app shell's unbounded queue on every
    page load, and the page's own unbounded queue *including reviewed
    history* on mount and after every saved correction.
    """

    return [
        Operation(
            "shell_unbounded",
            "App shell, before (unbounded queue)",
            "GET",
            "/api/review-queue",
        ),
        Operation(
            "page_unbounded",
            "Review Queue mount, before (unbounded + history)",
            "GET",
            "/api/review-queue?include_reviewed=true",
        ),
        Operation(
            "shell_summary",
            "App shell, after (counts only)",
            "GET",
            "/api/review-queue/summary",
        ),
        Operation(
            "page_first",
            "Review Queue mount, after (first page)",
            "GET",
            "/api/review-queue/page?tab=animals&status=unreviewed&page_size=25",
        ),
        Operation(
            "page_next",
            "Review Queue, after (next page)",
            "GET",
            "/api/review-queue/page?tab=animals&status=unreviewed&page_size=25&page=1",
        ),
        Operation(
            "page_reviewed",
            "Review Queue, after (Reviewed tab, first page)",
            "GET",
            "/api/review-queue/page?tab=reviewed&page_size=25",
        ),
        Operation(
            "page_unchecked",
            "Review Queue, after (Unchecked tab, first page)",
            "GET",
            "/api/review-queue/page?tab=unchecked&status=unreviewed&page_size=25",
        ),
        Operation(
            "page_search",
            "Review Queue, after (search)",
            "GET",
            "/api/review-queue/page?tab=animals&status=unreviewed&page_size=25&search=cardinal",
        ),
        Operation(
            "fast_navigate",
            "Fast Review, next unresolved Visit",
            "POST",
            "/api/review-queue/fast/navigate",
            body={
                # One target is enough to exercise the decision: the cost
                # this milestone changed is classifying the backlog, which
                # the endpoint does regardless of how many targets it is
                # given.
                "ordered_targets": [{"target_type": "visit", "target_id": "unknown"}],
                "current_target": None,
                "direction": "next",
            },
        ),
    ]


def measure(root: Path, *, repeat: int) -> list[dict[str, object]]:
    operations = review_queue_operations()
    server = _Server(root, _free_port())
    server.start()
    results: list[dict[str, object]] = []
    try:
        client = _Client(server.base_url)
        client.sign_in()
        for operation in operations:
            # One warm-up, as the release benchmark does: the first request
            # to any route pays FastAPI's response-model construction once.
            status, payload = client.request(
                operation.method, operation.path, operation.body
            )
            samples: list[float] = []
            for _ in range(repeat):
                started = time.perf_counter()
                status, payload = client.request(
                    operation.method, operation.path, operation.body
                )
                samples.append((time.perf_counter() - started) * 1000.0)
            parsed: object = None
            try:
                parsed = json.loads(payload)
            except (ValueError, UnicodeDecodeError):
                parsed = None
            item_count: int | None = None
            if isinstance(parsed, list):
                item_count = len(parsed)
            elif isinstance(parsed, dict) and isinstance(parsed.get("items"), list):
                item_count = len(parsed["items"])
            results.append(
                {
                    "key": operation.key,
                    "label": operation.label,
                    "path": operation.path,
                    "status": status,
                    "present": status != 404,
                    "median_ms": round(statistics.median(samples), 1) if samples else None,
                    "min_ms": round(min(samples), 1) if samples else None,
                    "max_ms": round(max(samples), 1) if samples else None,
                    "response_bytes": len(payload),
                    "item_count": item_count,
                }
            )
    finally:
        server.stop()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--label", default="")
    parser.add_argument("--json", type=Path, default=None)
    parser.add_argument("--skip-sql-counts", action="store_true")
    args = parser.parse_args(argv)

    results = measure(args.root, repeat=args.repeat)
    if not args.skip_sql_counts:
        counts = count_sql_statements(args.root, review_queue_operations())
        for entry in results:
            entry["sql_statements"] = counts.get(str(entry["key"]))

    report = {
        "label": args.label,
        "environment": environment_report(),
        "root": str(args.root),
        "repeat": args.repeat,
        "operations": results,
    }
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"{'operation':<48} {'status':>6} {'median':>10} {'bytes':>12} {'items':>7} {'stmts':>7}")
    for entry in results:
        median = f"{entry['median_ms']:.1f} ms" if entry["median_ms"] is not None else "-"
        statements = entry.get("sql_statements")
        print(
            f"{str(entry['label']):<48} "
            f"{entry['status']:>6} "
            f"{median:>10} "
            f"{entry['response_bytes']:>12,} "
            f"{entry['item_count'] if entry['item_count'] is not None else '-':>7} "
            f"{statements if statements is not None else '-':>7}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
