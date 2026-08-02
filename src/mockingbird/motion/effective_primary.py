"""Bounded, deterministic selection of review evidence; never model inference."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


MAX_EVIDENCE_CANDIDATES = 4
MIN_CROP_DIMENSION = 96


@dataclass(frozen=True)
class EvidenceCandidate:
    media_asset_id: str
    role: str
    captured_at: datetime
    width: int | None = None
    height: int | None = None
    track_box: tuple[float, float, float, float] | None = None
    crop_box: tuple[float, float, float, float] | None = None
    alignment_status: str | None = None
    user_selected: bool = False
    user_refined: bool = False
    sharpness: float | None = None
    available: bool | None = None
    decodable: bool | None = None
    track_supported: bool | None = None
    lineage_valid: bool | None = None


@dataclass(frozen=True)
class EffectivePrimarySelection:
    media_asset_id: str | None
    reason: str
    temporally_supported: bool | None
    contained: bool | None
    edge_clipped: bool | None
    automatic: bool


@dataclass(frozen=True)
class _Assessment:
    candidate: EvidenceCandidate
    temporal: bool | None
    contained: bool | None
    clipped: bool | None
    useful: bool | None

    @property
    def rejected(self) -> bool:
        return any(
            value is False
            for value in (
                self.temporal,
                self.contained,
                None if self.clipped is None else not self.clipped,
                self.useful,
                self.candidate.lineage_valid
                if self.candidate.role == "activity_crop"
                else None,
            )
        )


def select_effective_primary(
    candidates: list[EvidenceCandidate],
    *,
    support_start: datetime | None = None,
    support_end: datetime | None = None,
    cadence_seconds: float = 1.5,
) -> EffectivePrimarySelection:
    """Select at most four retained candidates without changing them.

    Suitability is deliberately tri-state: ``True`` is supported, ``False`` is
    an affirmative rejection, and ``None`` is unavailable/uncertain metadata.
    A legacy crop must not lose solely because the old record lacks a complete
    temporal interval; a positively late or clipped crop still loses.
    """

    items = candidates[:MAX_EVIDENCE_CANDIDATES]
    for item in items:
        if item.user_selected:
            return _result(item, "user_selected_primary")
    for item in items:
        if item.user_refined:
            return _result(item, "user_refined_primary")

    assessed = [
        _assessment(item, support_start, support_end, cadence_seconds) for item in items
    ]
    for item in assessed:
        if (
            item.candidate.role != "activity_crop"
            or item.rejected
            or item.temporal is not True
        ):
            continue
        return _selection(item, "high_resolution_temporally_aligned")
    for item in assessed:
        if item.candidate.role == "tracked_best_frame" and not item.rejected:
            return _selection(item, "tracked_best_frame_preferred")
    for item in assessed:
        if item.candidate.role == "pretrigger" and not item.rejected:
            return _selection(item, "pretrigger_frame_preferred")

    # Preserve the one-primary presentation invariant only after no role reaches
    # automatic eligibility. An uncertain crop stays attached as secondary
    # evidence, but is not a confirmed useful primary for the admitted subject.
    fallback = next(
        (item for item in assessed if item.candidate.role == "tracked_best_frame"),
        None,
    )
    fallback = fallback or next(
        (item for item in assessed if item.candidate.role == "pretrigger"), None
    )
    fallback = fallback or (assessed[0] if assessed else None)
    if fallback:
        return _selection(fallback, "no_useful_primary_evidence")
    return EffectivePrimarySelection(None, "no_useful_primary_evidence", None, None, None, True)


def _result(item: EvidenceCandidate, reason: str) -> EffectivePrimarySelection:
    return EffectivePrimarySelection(item.media_asset_id, reason, None, None, None, True)


def _selection(item: _Assessment, reason: str) -> EffectivePrimarySelection:
    return EffectivePrimarySelection(
        item.candidate.media_asset_id,
        reason,
        item.temporal,
        item.contained,
        item.clipped,
        True,
    )


def _assessment(
    item: EvidenceCandidate,
    support_start: datetime | None,
    support_end: datetime | None,
    cadence_seconds: float,
) -> _Assessment:
    temporal = _temporal_support(item, support_start, support_end, cadence_seconds)
    contained, clipped = _crop_geometry(item)
    useful = _usable_media(item)
    return _Assessment(item, temporal, contained, clipped, useful)


def _temporal_support(
    item: EvidenceCandidate,
    start: datetime | None,
    end: datetime | None,
    cadence: float,
) -> bool | None:
    if item.role == "tracked_best_frame":
        # A retained tracked-best frame is associated with the admitted track;
        # callers can explicitly reject stale/cross-generation evidence.
        return False if item.track_supported is False else True
    if start is None or end is None:
        return None
    start = _utc(start)
    end = _utc(end)
    captured = _utc(item.captured_at)
    grace = timedelta(seconds=max(1.0, min(10.0, cadence * 3)))
    return start - grace <= captured <= end + grace


def _crop_geometry(item: EvidenceCandidate) -> tuple[bool | None, bool | None]:
    if item.role != "activity_crop":
        return None, None
    if item.track_box is None or item.crop_box is None:
        return None, None
    left, top, right, bottom = item.track_box
    crop_left, crop_top, crop_right, crop_bottom = item.crop_box
    contained = (
        crop_left <= left
        and crop_top <= top
        and right <= crop_right
        and bottom <= crop_bottom
    )
    # The retained padded crop boundary is authoritative. A near image edge is
    # not automatically clipping when that boundary still contains the track.
    return contained, not contained


def _usable_media(item: EvidenceCandidate) -> bool | None:
    if item.available is False or item.decodable is False:
        return False
    if item.width is not None and item.width < MIN_CROP_DIMENSION:
        return False
    if item.height is not None and item.height < MIN_CROP_DIMENSION:
        return False
    if item.sharpness is not None and item.sharpness <= 1.0:
        return False
    if item.width is None or item.height is None:
        return None
    return True


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
