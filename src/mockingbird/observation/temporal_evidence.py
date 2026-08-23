"""Multimodal Observation & Soundscape v1, Phase C: a normalized temporal
evidence model used only for multimodal (visual/acoustic) association.

Both visual and acoustic evidence already carry real domain timestamps --
`EventModel.started_at`/`ended_at` (already absolute, already correctly
anchored by whichever pipeline created the row -- see
`create_acoustic_candidate_visit`'s own `observed_at` computation) and, for
the raw acoustic case, `MediaAssetModel.captured_at` plus a BirdNET
detection's own `window_start_ms`/`window_end_ms` offsets. This module never
invents a new clock and never reads analysis time, database insertion time,
or UI render time -- see docs/multimodal-observation-soundscape-v1-contract.md,
"Temporal model."

Deterministic and dependency-free: every function here is a pure transform
of already-persisted fields, matching this package's established
`scene_confusor.py`/`visit_episode_assembler.py` "pure decision module"
convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

#: The same honest "no real capture instant known" anchor `acoustic_ingest.
#: EPOCH_ANCHOR`/`offline_ingest.EPOCH_ANCHOR` already use. Duplicated, not
#: imported -- this module must stay usable without importing the acoustic
#: ingest pipeline (a pure, dependency-light module, reused by both the
#: acoustic and visual candidate-creation call sites).
EPOCH_ANCHOR = datetime(1970, 1, 1, tzinfo=UTC)

#: Where this interval's start/end instants actually came from.
ClockProvenance = Literal[
    "visual_event_range",
    "acoustic_event_range",
    "acoustic_window_media_captured_at",
    "acoustic_window_epoch_anchor_fallback",
]


@dataclass(frozen=True)
class EvidenceInterval:
    """One normalized ``[start, end]`` instant range for one piece of
    evidence, plus enough provenance to judge how much to trust it as a real
    wall-clock fact. ``start``/``end`` are always timezone-aware; ``end >=
    start`` always holds -- a degenerate zero-duration instant is valid and
    expected (a candidate Visit that never observed a second frame; a
    BirdNET window whose start/end offsets happened to collapse)."""

    start: datetime
    end: datetime
    source: str
    clock_provenance: ClockProvenance


def event_evidence_interval(
    *,
    started_at: datetime,
    ended_at: datetime | None,
    clock_provenance: ClockProvenance,
) -> EvidenceInterval:
    """Normalize an already-persisted ``EventModel``'s own range. Used
    identically for a visual candidate Event and an acoustic candidate
    Event -- both already store correctly-anchored absolute instants in
    `started_at`/`ended_at` (see `create_acoustic_candidate_visit`'s
    `observed_at`/`window_duration_ms` computation for the acoustic case),
    so this function does not need to know which modality produced them.

    `ended_at` is nullable on `EventModel` (some candidate Visits never
    observed a second frame); an unknown end honestly collapses to a
    zero-duration instant at `started_at` rather than guessing a duration.
    """

    end = ended_at if ended_at is not None and ended_at >= started_at else started_at
    return EvidenceInterval(
        start=started_at, end=end, source="event_started_ended", clock_provenance=clock_provenance,
    )


def acoustic_window_interval(
    *,
    media_captured_at: datetime | None,
    window_start_ms: int,
    window_end_ms: int,
) -> EvidenceInterval:
    """Normalize one raw BirdNET detection window into an absolute interval,
    duplicating -- deliberately, not importing, matching this package's
    established per-module convention -- the exact `boundary_anchor +
    offset` computation `acoustic_ingest.py` already uses to derive
    `observed_at`, so the two can never silently drift apart (see
    `tests/test_temporal_evidence.py`'s cross-check against a real
    `acoustic_ingest` computation).

    `media_captured_at is None` (the MediaAsset's own real capture instant
    was never established -- see `MediaAssetModel.captured_at`) is the one
    case that genuinely falls back to the shared epoch anchor; that
    fallback is reported honestly via `clock_provenance` rather than being
    indistinguishable from a real timestamp. This is the function Phase C
    calls "exact BirdNET detection start/end offset -> resulting absolute
    detection interval."
    """

    anchor = media_captured_at if media_captured_at is not None else EPOCH_ANCHOR
    duration_ms = max(0, window_end_ms - window_start_ms)
    start = anchor + timedelta(milliseconds=window_start_ms)
    end = start + timedelta(milliseconds=duration_ms)
    return EvidenceInterval(
        start=start,
        end=end,
        source="acoustic_window_offset",
        clock_provenance=(
            "acoustic_window_media_captured_at"
            if media_captured_at is not None
            else "acoustic_window_epoch_anchor_fallback"
        ),
    )


def interval_relationship_ms(a: EvidenceInterval, b: EvidenceInterval) -> tuple[int, int]:
    """Return ``(overlap_ms, gap_ms)``: exactly one is ever meaningfully
    nonzero. A positive `overlap_ms` means the two intervals genuinely
    intersect in time (by that many milliseconds); a positive `gap_ms`
    means the later interval starts that many milliseconds after the
    earlier one ends. Touching exactly (`a.end == b.start`) reports
    ``(0, 0)`` -- adjacent, neither overlapping nor separated -- which is
    intentional: it is the strictest possible non-negative gap, so every
    threshold comparison downstream (`gap_ms <= window_ms`) already treats
    it as the closest possible "not overlapping" case without a special
    case here."""

    latest_start = max(a.start, b.start)
    earliest_end = min(a.end, b.end)
    delta_ms = (earliest_end - latest_start).total_seconds() * 1000.0
    if delta_ms >= 0:
        return int(round(delta_ms)), 0
    return 0, int(round(-delta_ms))
