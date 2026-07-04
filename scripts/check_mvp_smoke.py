#!/usr/bin/env python3
"""Read-only MVP smoke check for a running MockingBird API."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JsonPayload = dict[str, Any] | list[Any] | str | int | float | bool | None
OpenUrl = Callable[..., Any]

READINESS_ENDPOINTS: tuple[tuple[str, str, bool], ...] = (
    ("health", "/health", True),
    ("streams", "/api/streams", True),
    ("zones", "/api/zones", True),
    ("review_queue", "/api/review-queue", False),
    ("detection_proposals", "/api/detection-proposals", False),
    ("dataset_exports", "/api/dataset-exports", False),
    ("analytics", "/api/analytics/summary", False),
    ("classifier_readiness", "/api/classifier-readiness", False),
)


class SmokeCheckError(RuntimeError):
    """A hard readiness failure for the local MVP smoke check."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Check a running MockingBird API for read-only MVP demo readiness. "
            "This creates no media, proposals, corrections, exports, or truth."
        )
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def api_url(api_base: str, path: str) -> str:
    return f"{api_base.rstrip('/')}{path}"


def read_json_response(api_base: str, path: str, opener: OpenUrl = urlopen) -> JsonPayload:
    request = Request(api_url(api_base, path), method="GET")
    try:
        with opener(request, timeout=10) as response:
            content = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SmokeCheckError(f"HTTP {error.code} {request.full_url}: {detail}") from error
    except URLError as error:
        raise SmokeCheckError(f"Could not reach {request.full_url}: {error.reason}") from error

    if not content:
        return None
    return json.loads(content.decode("utf-8"))


def collect_payloads(api_base: str, opener: OpenUrl = urlopen) -> dict[str, JsonPayload]:
    payloads: dict[str, JsonPayload] = {}
    optional_errors: dict[str, str] = {}

    for key, path, required in READINESS_ENDPOINTS:
        try:
            payloads[key] = read_json_response(api_base, path, opener)
        except SmokeCheckError as error:
            if required:
                raise
            optional_errors[key] = str(error)

    if optional_errors:
        payloads["_optional_errors"] = optional_errors
    return payloads


def list_count(payload: JsonPayload) -> int:
    return len(payload) if isinstance(payload, list) else 0


def int_field(payload: JsonPayload, key: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get(key)
    return value if isinstance(value, int) else None


def summarize_payloads(payloads: dict[str, JsonPayload]) -> dict[str, Any]:
    health = payloads.get("health")
    analytics = payloads.get("analytics")
    classifier = payloads.get("classifier_readiness")
    summary = {
        "api_healthy": isinstance(health, dict) and health.get("status") == "ok",
        "stream_count": list_count(payloads.get("streams")),
        "zone_count": list_count(payloads.get("zones")),
        "review_queue_count": list_count(payloads.get("review_queue")),
        "detection_proposal_count": list_count(payloads.get("detection_proposals")),
        "dataset_export_count": list_count(payloads.get("dataset_exports")),
        "analytics_event_count": int_field(analytics, "event_count"),
        "analytics_visit_count": int_field(analytics, "visit_count"),
        "analytics_needs_review_count": int_field(analytics, "needs_review_count"),
        "classifier_reviewed_examples": int_field(classifier, "reviewed_examples"),
        "classifier_export_ready_examples": int_field(classifier, "export_ready_examples"),
        "optional_errors": payloads.get("_optional_errors", {}),
    }
    return summary


def hard_failures(summary: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if not summary["api_healthy"]:
        failures.append("/health did not report status=ok.")
    if summary["stream_count"] <= 0:
        failures.append("No streams are available. Seed or restore demo data first.")
    if summary["zone_count"] <= 0:
        failures.append("No zones are available. Seed or restore demo data first.")
    return failures


def render_report(summary: dict[str, Any], *, verbose: bool = False) -> str:
    lines = [
        "MockingBird MVP smoke readiness",
        f"api_healthy: {summary['api_healthy']}",
        f"stream_count: {summary['stream_count']}",
        f"zone_count: {summary['zone_count']}",
        f"review_queue_count: {summary['review_queue_count']}",
        f"detection_proposal_count: {summary['detection_proposal_count']}",
        f"dataset_export_count: {summary['dataset_export_count']}",
    ]

    if summary["analytics_event_count"] is not None:
        lines.extend(
            [
                f"analytics_event_count: {summary['analytics_event_count']}",
                f"analytics_visit_count: {summary['analytics_visit_count']}",
                f"analytics_needs_review_count: {summary['analytics_needs_review_count']}",
            ]
        )

    if summary["classifier_reviewed_examples"] is not None:
        lines.extend(
            [
                f"classifier_reviewed_examples: {summary['classifier_reviewed_examples']}",
                (
                    "classifier_export_ready_examples: "
                    f"{summary['classifier_export_ready_examples']}"
                ),
            ]
        )

    optional_errors = summary["optional_errors"]
    if verbose and optional_errors:
        lines.append("optional_endpoint_errors:")
        for key, error in sorted(optional_errors.items()):
            lines.append(f"- {key}: {error}")

    failures = hard_failures(summary)
    if failures:
        lines.append("hard_failures:")
        lines.extend(f"- {failure}" for failure in failures)
    else:
        lines.append("hard_failures: none")

    lines.extend(
        [
            "truth_boundary:",
            "- This check is read-only.",
            "- Demo proposals are evidence, not truth.",
            "- ReviewLabel truth still requires explicit correction.",
            "- Dataset exports still require explicit creation.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    try:
        payloads = collect_payloads(args.api_base)
    except SmokeCheckError as error:
        print(error, file=sys.stderr)
        return 1

    summary = summarize_payloads(payloads)
    print(render_report(summary, verbose=args.verbose))
    return 1 if hard_failures(summary) else 0


if __name__ == "__main__":
    raise SystemExit(main())
