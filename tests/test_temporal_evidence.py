"""Multimodal Observation & Soundscape v1, Phase C: deterministic interval
normalization. Every test here is a pure function call -- no repository, no
database, no fixture media."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from mockingbird.observation import acoustic_ingest
from mockingbird.observation.temporal_evidence import (
    EPOCH_ANCHOR,
    acoustic_window_interval,
    event_evidence_interval,
    interval_relationship_ms,
)


def test_epoch_anchor_matches_acoustic_ingest_exactly() -> None:
    """A silent drift between the two "no real capture instant known"
    anchors would make an epoch-anchor-fallback acoustic Visit and its own
    association-engine interval disagree about the same clip's timing --
    this pins them together so any future edit to either constant fails
    loudly here first."""

    assert EPOCH_ANCHOR == acoustic_ingest.EPOCH_ANCHOR


def test_event_evidence_interval_uses_started_and_ended_at() -> None:
    started = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    ended = started + timedelta(seconds=12)
    interval = event_evidence_interval(started_at=started, ended_at=ended, clock_provenance="visual_event_range")
    assert interval.start == started
    assert interval.end == ended
    assert interval.clock_provenance == "visual_event_range"


def test_event_evidence_interval_null_ended_at_collapses_to_started_at() -> None:
    started = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    interval = event_evidence_interval(started_at=started, ended_at=None, clock_provenance="acoustic_event_range")
    assert interval.start == started
    assert interval.end == started


def test_event_evidence_interval_rejects_ended_before_started_by_collapsing() -> None:
    """A corrupt/impossible `ended_at < started_at` row (should never exist,
    but this is a pure normalization function -- never trust the caller)
    honestly collapses to a zero-duration instant rather than reporting a
    negative-duration interval that would break every downstream overlap
    computation."""

    started = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    interval = event_evidence_interval(
        started_at=started, ended_at=started - timedelta(seconds=5), clock_provenance="visual_event_range",
    )
    assert interval.end == started


def test_acoustic_window_interval_matches_acoustic_ingest_observed_at_formula() -> None:
    """Cross-checks this module's own absolute-interval computation against
    the exact formula `acoustic_ingest.py` independently applies to derive
    `observed_at` for a real candidate Visit, proving the two cannot
    silently diverge (see the module docstring)."""

    captured_at = datetime(2026, 8, 22, 9, 30, 0, tzinfo=UTC)
    window_start_ms, window_end_ms = 4_000, 7_000

    interval = acoustic_window_interval(
        media_captured_at=captured_at, window_start_ms=window_start_ms, window_end_ms=window_end_ms,
    )

    expected_start = captured_at + timedelta(milliseconds=window_start_ms)
    expected_end = expected_start + timedelta(milliseconds=window_end_ms - window_start_ms)
    assert interval.start == expected_start
    assert interval.end == expected_end
    assert interval.clock_provenance == "acoustic_window_media_captured_at"


def test_acoustic_window_interval_falls_back_to_epoch_anchor_honestly() -> None:
    interval = acoustic_window_interval(media_captured_at=None, window_start_ms=0, window_end_ms=3_000)
    assert interval.start == EPOCH_ANCHOR
    assert interval.clock_provenance == "acoustic_window_epoch_anchor_fallback"


def test_interval_relationship_reports_overlap_not_gap() -> None:
    base = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    a = event_evidence_interval(started_at=base, ended_at=base + timedelta(seconds=10), clock_provenance="visual_event_range")
    b = event_evidence_interval(
        started_at=base + timedelta(seconds=5), ended_at=base + timedelta(seconds=15), clock_provenance="acoustic_event_range",
    )
    overlap_ms, gap_ms = interval_relationship_ms(a, b)
    assert overlap_ms == 5_000
    assert gap_ms == 0


def test_interval_relationship_reports_gap_not_overlap() -> None:
    base = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    a = event_evidence_interval(started_at=base, ended_at=base + timedelta(seconds=2), clock_provenance="visual_event_range")
    b = event_evidence_interval(
        started_at=base + timedelta(seconds=10), ended_at=base + timedelta(seconds=12), clock_provenance="acoustic_event_range",
    )
    overlap_ms, gap_ms = interval_relationship_ms(a, b)
    assert overlap_ms == 0
    assert gap_ms == 8_000


def test_interval_relationship_is_order_independent() -> None:
    base = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    a = event_evidence_interval(started_at=base, ended_at=base + timedelta(seconds=2), clock_provenance="visual_event_range")
    b = event_evidence_interval(
        started_at=base + timedelta(seconds=10), ended_at=base + timedelta(seconds=12), clock_provenance="acoustic_event_range",
    )
    assert interval_relationship_ms(a, b) == interval_relationship_ms(b, a)


def test_interval_relationship_touching_exactly_is_zero_and_zero() -> None:
    base = datetime(2026, 8, 22, 10, 0, 0, tzinfo=UTC)
    a = event_evidence_interval(started_at=base, ended_at=base + timedelta(seconds=5), clock_provenance="visual_event_range")
    b = event_evidence_interval(
        started_at=base + timedelta(seconds=5), ended_at=base + timedelta(seconds=8), clock_provenance="acoustic_event_range",
    )
    assert interval_relationship_ms(a, b) == (0, 0)
