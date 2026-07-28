"""Pure, bounded calculations for auditable Zone Insights.

The durable monitor stores only the latest runtime generation and a bounded
Camera Health incident history.  These helpers deliberately turn that limited
history into a conservative exposure interval instead of inventing all-day
uptime from an armed Stream policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable


@dataclass(frozen=True, order=True)
class TimeInterval:
    """A half-open UTC time interval used only for read-side aggregation."""

    start_at: datetime
    end_at: datetime

    def clipped(self, start_at: datetime, end_at: datetime) -> "TimeInterval | None":
        start = max(self.start_at, start_at)
        end = min(self.end_at, end_at)
        return TimeInterval(start, end) if end > start else None


def merge_intervals(intervals: Iterable[TimeInterval]) -> list[TimeInterval]:
    """Merge overlaps so retries or overlapping incidents never double-count time."""

    ordered = sorted(interval for interval in intervals if interval.end_at > interval.start_at)
    merged: list[TimeInterval] = []
    for interval in ordered:
        if not merged or interval.start_at > merged[-1].end_at:
            merged.append(interval)
            continue
        previous = merged[-1]
        merged[-1] = TimeInterval(previous.start_at, max(previous.end_at, interval.end_at))
    return merged


def subtract_intervals(
    available: Iterable[TimeInterval],
    unavailable: Iterable[TimeInterval],
) -> list[TimeInterval]:
    """Remove known failed/recovering windows from bounded runtime availability."""

    remaining = merge_intervals(available)
    for blocked in merge_intervals(unavailable):
        next_remaining: list[TimeInterval] = []
        for interval in remaining:
            if blocked.end_at <= interval.start_at or blocked.start_at >= interval.end_at:
                next_remaining.append(interval)
                continue
            if blocked.start_at > interval.start_at:
                next_remaining.append(TimeInterval(interval.start_at, blocked.start_at))
            if blocked.end_at < interval.end_at:
                next_remaining.append(TimeInterval(blocked.end_at, interval.end_at))
        remaining = next_remaining
    return remaining


def interval_seconds(intervals: Iterable[TimeInterval]) -> float:
    return sum((interval.end_at - interval.start_at).total_seconds() for interval in intervals)


def bounded_healthy_runtime_interval(
    *,
    range_start_at: datetime,
    range_end_at: datetime,
    actual_state: str,
    last_start_attempt_at: datetime | None,
    last_healthy_frame_at: datetime | None,
    last_clean_stop_at: datetime | None,
    last_failure_at: datetime | None,
    freshness_limit: timedelta,
) -> TimeInterval | None:
    """Return only the latest generation supported by durable runtime facts.

    An armed policy alone is not exposure.  A generation must have started and
    later produced a healthy frame.  Its tail is capped by the established frame
    freshness limit and by any saved stop/failure boundary.  Earlier generations
    are intentionally unavailable because checkpoint history is bounded.
    """

    if actual_state not in {"running", "stopped", "interrupted", "backoff", "blocked"}:
        return None
    if last_start_attempt_at is None or last_healthy_frame_at is None:
        return None
    end_candidates = [range_end_at, last_healthy_frame_at + freshness_limit]
    if last_clean_stop_at is not None and last_clean_stop_at > last_start_attempt_at:
        end_candidates.append(last_clean_stop_at)
    if last_failure_at is not None and last_failure_at > last_start_attempt_at:
        end_candidates.append(last_failure_at)
    interval = TimeInterval(
        max(range_start_at, last_start_attempt_at),
        min(end_candidates),
    )
    return interval if interval.end_at > interval.start_at else None


def median_duration_seconds(values: Iterable[float]) -> float | None:
    durations = sorted(value for value in values if value >= 0)
    return float(median(durations)) if durations else None


def quality_status(
    *,
    healthy_monitored_seconds: float | None,
    reviewed_visit_count: int,
    active_visit_count: int,
    confirmed_bird_visit_count: int,
) -> tuple[str, list[str]]:
    """Return bounded user-facing confidence language without ranking thin data."""

    if healthy_monitored_seconds is None:
        return (
            "unavailable_exposure",
            [
                "Healthy monitored time is unavailable: durable history retains only the latest bounded runtime generation.",
            ],
        )
    warnings: list[str] = []
    if healthy_monitored_seconds < 2 * 60 * 60:
        warnings.append("Limited monitoring: fewer than 2 healthy monitored hours are supported.")
        return "limited_monitoring", warnings
    coverage = (reviewed_visit_count / active_visit_count * 100) if active_visit_count else None
    if reviewed_visit_count < 5 or (coverage is not None and coverage < 50):
        if reviewed_visit_count < 5:
            warnings.append("Limited review coverage: fewer than 5 Visits have been reviewed.")
        if coverage is not None and coverage < 50:
            warnings.append("Limited review coverage: fewer than 50% of captured Visits have been reviewed.")
        return "limited_review_coverage", warnings
    if confirmed_bird_visit_count == 0:
        return "no_confirmed_activity", ["No confirmed bird Visits in this selected range."]
    return "sufficient", warnings
