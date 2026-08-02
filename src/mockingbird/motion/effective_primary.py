"""Bounded, deterministic selection of review evidence; never model inference."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

MAX_EVIDENCE_CANDIDATES = 4
MIN_CROP_DIMENSION = 96
EDGE_MARGIN = 0.03

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

@dataclass(frozen=True)
class EffectivePrimarySelection:
    media_asset_id: str | None
    reason: str
    temporally_supported: bool | None
    contained: bool | None
    edge_clipped: bool | None
    automatic: bool

def select_effective_primary(candidates: list[EvidenceCandidate], *, support_start: datetime | None = None, support_end: datetime | None = None, cadence_seconds: float = 1.5) -> EffectivePrimarySelection:
    """Select at most four retained candidates without changing them.

    High-resolution coordinate lineage is deliberately separate from temporal
    support: a late aligned crop cannot displace a useful tracked frame.
    """
    items = candidates[:MAX_EVIDENCE_CANDIDATES]
    for item in items:
        if item.user_selected:
            return _result(item, "user_selected_primary", True)
    for item in items:
        if item.user_refined:
            return _result(item, "user_refined_primary", True)
    supported = [_assessment(item, support_start, support_end, cadence_seconds) for item in items]
    for item, temporal, contained, clipped, useful in supported:
        if item.role == "activity_crop" and temporal and contained and not clipped and useful:
            return EffectivePrimarySelection(item.media_asset_id, "high_resolution_temporally_aligned", True, True, False, True)
    for item, temporal, contained, clipped, useful in supported:
        if item.role == "tracked_best_frame" and useful:
            return EffectivePrimarySelection(item.media_asset_id, "tracked_best_frame_preferred", temporal, contained, clipped, True)
    for item, temporal, contained, clipped, useful in supported:
        if item.role == "pretrigger" and useful:
            return EffectivePrimarySelection(item.media_asset_id, "pretrigger_frame_preferred", temporal, contained, clipped, True)
    # Keep the stored one-primary invariant even when suitability is weak.
    fallback = next((row for row in supported if row[0].role == "tracked_best_frame"), None)
    fallback = fallback or next((row for row in supported if row[0].role == "pretrigger"), None)
    fallback = fallback or (supported[0] if supported else None)
    if fallback:
        item, temporal, contained, clipped, _useful = fallback
        return EffectivePrimarySelection(item.media_asset_id, "no_useful_primary_evidence", temporal, contained, clipped, True)
    return EffectivePrimarySelection(None, "no_useful_primary_evidence", None, None, None, True)

def _result(item: EvidenceCandidate, reason: str, automatic: bool) -> EffectivePrimarySelection:
    return EffectivePrimarySelection(item.media_asset_id, reason, None, None, None, automatic)

def _assessment(item: EvidenceCandidate, start: datetime | None, end: datetime | None, cadence: float) -> tuple[EvidenceCandidate, bool | None, bool | None, bool | None, bool]:
    temporal = None
    if start and end:
        start = _utc(start); end = _utc(end); captured = _utc(item.captured_at)
        grace = timedelta(seconds=max(1.0, min(10.0, cadence * 3)))
        temporal = start - grace <= captured <= end + grace
    contained = clipped = None
    if item.role == "activity_crop" and item.track_box and item.crop_box:
        l,t,r,b = item.track_box; cl,ct,cr,cb = item.crop_box
        contained = cl <= l and ct <= t and r <= cr and b <= cb
        clipped = not contained or min(l-cl, t-ct, cr-r, cb-b) < EDGE_MARGIN
    useful = bool((item.width or 0) >= MIN_CROP_DIMENSION and (item.height or 0) >= MIN_CROP_DIMENSION)
    if item.sharpness is not None and item.sharpness <= 1.0: useful = False
    return item, temporal, contained, clipped, useful

def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
