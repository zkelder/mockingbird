from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.error import URLError

import pytest


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_mvp_smoke.py"
SPEC = importlib.util.spec_from_file_location("check_mvp_smoke", SCRIPT_PATH)
assert SPEC is not None
check_mvp_smoke = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_mvp_smoke)


def test_summarize_payloads_reports_mvp_readiness_counts() -> None:
    summary = check_mvp_smoke.summarize_payloads(
        {
            "health": {"status": "ok"},
            "streams": [{"id": "stream-backyard-feeder"}],
            "zones": [{"id": "zone-feeder"}],
            "review_queue": [{"id": "review-queue-visit"}],
            "detection_proposals": [{"id": "proposal-1"}, {"id": "proposal-2"}],
            "dataset_exports": [{"id": "dataset-export-1"}],
            "analytics": {
                "event_count": 3,
                "visit_count": 2,
                "needs_review_count": 1,
            },
            "classifier_readiness": {
                "reviewed_examples": 4,
                "export_ready_examples": 2,
            },
        }
    )

    assert summary["api_healthy"] is True
    assert summary["stream_count"] == 1
    assert summary["zone_count"] == 1
    assert summary["review_queue_count"] == 1
    assert summary["detection_proposal_count"] == 2
    assert summary["dataset_export_count"] == 1
    assert summary["analytics_event_count"] == 3
    assert summary["analytics_visit_count"] == 2
    assert summary["analytics_needs_review_count"] == 1
    assert summary["classifier_reviewed_examples"] == 4
    assert summary["classifier_export_ready_examples"] == 2
    assert check_mvp_smoke.hard_failures(summary) == []
    report = check_mvp_smoke.render_report(summary)
    assert "hard_failures: none" in report
    assert "This check is read-only." in report


def test_hard_failures_require_streams_and_zones() -> None:
    summary = check_mvp_smoke.summarize_payloads(
        {
            "health": {"status": "ok"},
            "streams": [],
            "zones": [],
            "review_queue": [],
            "detection_proposals": [],
            "dataset_exports": [],
            "analytics": {},
            "classifier_readiness": {},
        }
    )

    failures = check_mvp_smoke.hard_failures(summary)

    assert "No streams are available. Seed or restore demo data first." in failures
    assert "No zones are available. Seed or restore demo data first." in failures
    assert "hard_failures:" in check_mvp_smoke.render_report(summary)


def test_collect_payloads_reports_unreachable_api_as_hard_failure() -> None:
    def unreachable(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise URLError("connection refused")

    with pytest.raises(check_mvp_smoke.SmokeCheckError, match="Could not reach"):
        check_mvp_smoke.collect_payloads("http://127.0.0.1:8000", opener=unreachable)
