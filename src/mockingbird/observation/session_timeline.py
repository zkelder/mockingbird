"""Provider-neutral, reconnect-safe session-timeline derivation.

Observation Engine v2 Stage 6.8. This module is pure: no filesystem,
network, CUDA/ONNX Runtime/OpenCV, or product-repository import anywhere in
its contract, mirroring every prior Stage's pure/io/cli split.

A real paired Camera Node HTTP connection resets its own per-connection
transport sequence number and this codebase's source-relative offset
bookkeeping on every reconnect, while the underlying camera/provider
identity (`provider_generation`) does not change. Reconnecting every few
seconds is the *normal* case on this transport, not a rare failure (see
docs/temporal-review-capture-contract.md). That leaves three concepts that
must stay distinct rather than collapse into one number:

- **source-local facts**: original capture timestamp, source-relative
  offset, transport sequence, provider generation -- exactly what one
  Camera Node connection supplied, never overwritten here.
- **connection segment**: one contiguous transport connection/generation,
  with its own deterministic identity, ordinal, frame range, and timing
  quality.
- **session timeline**: a deterministic, monotonic, engineering-only
  correlation coordinate used only inside one capture session -- explicitly
  *not* a camera monotonic timestamp -- derived from retained provenance so
  every retained frame gets one stable, comparable position regardless of
  how many reconnects happened in between.

See docs/session-timeline-contract.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

MAX_TIMELINE_FRAMES = 20_000

NATIVE_SESSION_TIMELINE = "native_session_timeline"
DERIVED_SESSION_TIMELINE = "derived_session_timeline"
INSUFFICIENT_TEMPORAL_PROVENANCE = "insufficient_temporal_provenance"

SESSION_TIMELINE_CLASSIFICATIONS: tuple[str, ...] = (
    NATIVE_SESSION_TIMELINE, DERIVED_SESSION_TIMELINE, INSUFFICIENT_TEMPORAL_PROVENANCE,
)

# A connection segment boundary crossed by a genuine, precisely-measured
# (native) host-clock gap still carries some uncertainty: the PC receive
# clock is not synchronized to the Node's capture clock (see
# camera-node-live-shadow-contract.md), so even a real measured delta is an
# estimate of true capture-time separation, not a proven one.
NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS = 0
NATIVE_RECONNECT_UNCERTAINTY_MS = 50
NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS = 250

# A pre-Stage-6.8 (legacy) capture manifest never recorded a host receive
# timestamp or a real per-connection identity, so a reconstructed segment
# boundary's true wall-clock gap is genuinely unknown -- it could be
# anywhere from milliseconds to tens of seconds on this transport. This
# constant documents that as an explicit, bounded "we do not know" value
# rather than inventing a plausible-looking duration; the assigned
# session_offset_ms step across the boundary is always the minimal 1ms
# needed for strict ordering, never a fabricated gap estimate.
LEGACY_RECONNECT_GAP_UNCERTAINTY_MS = 30_000

# A single-connection gap this long is past what "brief reconnect" framing
# can honestly cover, even when it is natively measured; flagged as an
# additional limitation rather than a rejection (the caller decides whether
# an appearance interval spanning it needs explicit reviewer uncertainty).
LONG_GAP_THRESHOLD_MS = 300_000
_MIN_FORWARD_STEP_MS = 1


class SessionTimelineError(ValueError):
    """A bounded session-timeline derivation failure code."""


@dataclass(frozen=True)
class SourceFrameFact:
    """Bounded per-frame input this module derives a timeline from.

    `connection_segment_hint`/`host_received_at_iso` are the *native*
    signals a Stage 6.8 capture records directly (the real transport
    connection identity and a host wall-clock receive time). Either may be
    `None` for a pre-Stage-6.8 manifest, which routes the whole session
    through the legacy reconstruction path instead of pretending to have
    native provenance it does not.
    """

    frame_id: str
    source_sequence: int
    source_offset_ms: int
    provider_generation: str
    connection_segment_hint: str | None = None
    host_received_at_iso: str | None = None
    source_capture_timestamp_iso: str | None = None

    def __post_init__(self) -> None:
        if not self.frame_id or self.source_sequence < 0 or self.source_offset_ms < 0 or not self.provider_generation:
            raise SessionTimelineError("invalid_source_frame_fact")


@dataclass(frozen=True)
class FrameTimelineFact:
    """The derived, session-wide coordinate for one retained frame. Never a
    replacement for source-local facts -- callers keep those unchanged and
    merge this alongside them."""

    frame_id: str
    connection_segment_id: str
    connection_segment_ordinal: int
    session_sequence: int
    session_offset_ms: int
    previous_frame_identity: str | None
    temporal_discontinuity: bool
    temporal_uncertainty_ms: int


@dataclass(frozen=True)
class ConnectionSegment:
    segment_id: str
    segment_ordinal: int
    first_frame_id: str
    last_frame_id: str
    frame_count: int
    source_sequence_range: tuple[int, int]
    source_offset_range_ms: tuple[int, int]
    host_received_at_range: tuple[str, str] | None
    timing_quality: str
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionTimeline:
    classification: str
    frames: tuple[FrameTimelineFact, ...]
    segments: tuple[ConnectionSegment, ...]
    limitations: tuple[str, ...]
    upgrade_provenance: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.classification not in SESSION_TIMELINE_CLASSIFICATIONS:
            raise SessionTimelineError("invalid_session_timeline_classification")

    def frame(self, frame_id: str) -> FrameTimelineFact | None:
        for item in self.frames:
            if item.frame_id == frame_id:
                return item
        return None


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise SessionTimelineError("invalid_host_received_at") from error
    if parsed.tzinfo is None:
        raise SessionTimelineError("invalid_host_received_at")
    return parsed


def derive_session_timeline(facts: tuple[SourceFrameFact, ...], *, session_id: str) -> SessionTimeline:
    """Derive a deterministic, monotonic session timeline from bounded
    per-frame facts, supplied in the order the caller asserts they were
    genuinely retained (true chronological/receipt order for a native
    capture; the manifest's own stored order for a legacy upgrade -- see
    `_derive_legacy` for why that is handled differently).

    Deterministic for repeated calls with the same input, independent of
    filesystem paths or process identity, and never recomputes a
    current-wall-clock value: every fact used here already came from the
    caller's stored records.
    """

    if not session_id:
        raise SessionTimelineError("invalid_session_identity")
    if len(facts) > MAX_TIMELINE_FRAMES:
        raise SessionTimelineError("session_timeline_frame_limit")
    if not facts:
        return SessionTimeline(NATIVE_SESSION_TIMELINE, (), (), ())
    frame_ids = [item.frame_id for item in facts]
    if len(frame_ids) != len(set(frame_ids)):
        raise SessionTimelineError("duplicate_frame_identity")

    if all(item.connection_segment_hint and item.host_received_at_iso for item in facts):
        return _derive_native(facts)
    return _derive_legacy(facts)


def _derive_native(facts: tuple[SourceFrameFact, ...]) -> SessionTimeline:
    """Native derivation: trust the caller's given order as true
    chronological receipt order (the "frame order observed by the
    authenticated analysis source"), and use each frame's own host receive
    timestamp only to measure the *step* to the next frame -- never as a
    resort key, so a genuine host-clock regression cannot silently reorder
    frames relative to their true arrival sequence."""

    parsed_times = [_parse_iso(item.host_received_at_iso) for item in facts]  # type: ignore[arg-type]
    timeline_frames: list[FrameTimelineFact] = []
    segment_ordinals: dict[str, int] = {}
    segment_members: dict[str, list[int]] = {}
    running_offset_ms = 0
    global_limitations: set[str] = {
        "node-to-host clock alignment is uncertain unless externally synchronized",
    }
    previous_id: str | None = None

    for index, fact in enumerate(facts):
        segment_id = fact.connection_segment_hint or ""
        if segment_id not in segment_ordinals:
            segment_ordinals[segment_id] = len(segment_ordinals)
            segment_members[segment_id] = []
        segment_members[segment_id].append(index)

        if index == 0:
            offset_ms = 0
            discontinuity = False
            uncertainty = NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS
        else:
            previous_segment = facts[index - 1].connection_segment_hint or ""
            discontinuity = segment_id != previous_segment
            delta_ms = (parsed_times[index] - parsed_times[index - 1]).total_seconds() * 1000.0
            regressed = delta_ms < 0
            if regressed:
                step = _MIN_FORWARD_STEP_MS
                global_limitations.add("host receive clock regression observed; assigned coordinate clamped forward")
            else:
                step = max(round(delta_ms), _MIN_FORWARD_STEP_MS)
            offset_ms = running_offset_ms + step
            if discontinuity:
                uncertainty = NATIVE_RECONNECT_UNCERTAINTY_MS
                if step >= LONG_GAP_THRESHOLD_MS:
                    global_limitations.add("a connection segment gap exceeded the bounded long-gap threshold")
            elif regressed:
                uncertainty = NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS
            else:
                uncertainty = NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS
        running_offset_ms = offset_ms

        timeline_frames.append(FrameTimelineFact(
            frame_id=fact.frame_id, connection_segment_id=segment_id,
            connection_segment_ordinal=segment_ordinals[segment_id], session_sequence=index,
            session_offset_ms=offset_ms, previous_frame_identity=previous_id,
            temporal_discontinuity=discontinuity, temporal_uncertainty_ms=uncertainty,
        ))
        previous_id = fact.frame_id

    segments = tuple(
        _build_segment(
            segment_id, ordinal, facts, parsed_times, segment_members[segment_id],
            timing_quality="measured_host_clock",
        )
        for segment_id, ordinal in sorted(segment_ordinals.items(), key=lambda item: item[1])
    )
    return SessionTimeline(NATIVE_SESSION_TIMELINE, tuple(timeline_frames), segments, tuple(sorted(global_limitations)))


def _build_segment(
    segment_id: str, ordinal: int, facts: tuple[SourceFrameFact, ...],
    parsed_times: list[datetime] | None, member_indices: list[int], *, timing_quality: str,
) -> ConnectionSegment:
    members = [facts[index] for index in member_indices]
    sequences = [item.source_sequence for item in members]
    offsets = [item.source_offset_ms for item in members]
    received_range = None
    if parsed_times is not None:
        received_range = (
            parsed_times[member_indices[0]].isoformat(),
            parsed_times[member_indices[-1]].isoformat(),
        )
    return ConnectionSegment(
        segment_id=segment_id, segment_ordinal=ordinal,
        first_frame_id=members[0].frame_id, last_frame_id=members[-1].frame_id,
        frame_count=len(members), source_sequence_range=(min(sequences), max(sequences)),
        source_offset_range_ms=(min(offsets), max(offsets)), host_received_at_range=received_range,
        timing_quality=timing_quality,
        limitations=() if timing_quality == "measured_host_clock" else (
            "segment membership and internal frame order are a deterministic best-effort "
            "reconstruction from source-local sequence numbers only; true wall-clock order "
            "among frames sharing this reconstructed segment is not independently confirmed",
        ),
    )


def _derive_legacy(facts: tuple[SourceFrameFact, ...]) -> SessionTimeline:
    """Legacy/backward-compatible derivation for a manifest that never
    recorded a native per-connection identity or host receive time.

    The manifest's own stored frame order groups frames by raw,
    connection-local `source_sequence` value (ascending), which is *not*
    chronological once more than one connection contributed frames -- every
    connection's own sequence numbering restarts near zero. This
    reconstructs plausible connection segments with a deterministic greedy
    bin-packing pass: process frames in the given (stored) order, and place
    each one into the first still-open segment whose last-assigned sequence
    is lower than this frame's own sequence (a fresh segment is opened only
    when no existing one qualifies). Within any one reconstructed segment
    this guarantees strictly increasing `source_sequence`, exactly the
    property a single real connection has; segment ordinal is assigned by
    creation order, which -- because ties at the same sequence value keep
    the stored array's own (chronologically stable-sorted) relative order --
    approximates true connection start order without claiming to prove it.
    The true duration of any reconstructed reconnect gap is unknown and is
    never fabricated; only ordering and discontinuity facts are asserted,
    at `LEGACY_RECONNECT_GAP_UNCERTAINTY_MS` bounded uncertainty.

    The bin-packing pass itself needs its input pre-sorted by ascending
    `source_sequence` (stable, so frames genuinely tied at the same sequence
    value -- different connections' same local position -- keep their given
    relative order): a real pre-Stage-6.8 manifest is already stored that
    way (its own `to_semantic_dict()` sorted by raw `sequence` before ever
    writing to disk), but nothing about *this* function should silently
    depend on that as an unstated precondition of its caller.
    """

    facts = tuple(sorted(facts, key=lambda item: item.source_sequence))
    open_segments: list[dict[str, object]] = []  # each: {"last_sequence": int, "members": [index,...]}
    for index, fact in enumerate(facts):
        target = next(
            (segment for segment in open_segments if segment["last_sequence"] < fact.source_sequence),  # type: ignore[operator]
            None,
        )
        if target is None:
            target = {"last_sequence": fact.source_sequence, "members": []}
            open_segments.append(target)
        target["last_sequence"] = fact.source_sequence
        target["members"].append(index)  # type: ignore[union-attr]

    timeline_frames: list[FrameTimelineFact] = []
    segments: list[ConnectionSegment] = []
    running_offset_ms = 0
    previous_id: str | None = None
    session_sequence = 0
    for ordinal, segment in enumerate(open_segments):
        member_indices: list[int] = segment["members"]  # type: ignore[assignment]
        segment_id = f"legacy-segment-{ordinal:04d}"
        local_previous_offset: int | None = None
        for member_index in member_indices:
            fact = facts[member_index]
            is_segment_start = local_previous_offset is None
            if session_sequence == 0:
                offset_ms = 0
                discontinuity = False
                uncertainty = NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS
            elif is_segment_start:
                offset_ms = running_offset_ms + _MIN_FORWARD_STEP_MS
                discontinuity = True
                uncertainty = LEGACY_RECONNECT_GAP_UNCERTAINTY_MS
            else:
                local_delta = fact.source_offset_ms - local_previous_offset  # type: ignore[operator]
                step = max(local_delta, _MIN_FORWARD_STEP_MS)
                offset_ms = running_offset_ms + step
                discontinuity = False
                uncertainty = NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS
            running_offset_ms = offset_ms
            local_previous_offset = fact.source_offset_ms

            timeline_frames.append(FrameTimelineFact(
                frame_id=fact.frame_id, connection_segment_id=segment_id, connection_segment_ordinal=ordinal,
                session_sequence=session_sequence, session_offset_ms=offset_ms, previous_frame_identity=previous_id,
                temporal_discontinuity=discontinuity, temporal_uncertainty_ms=uncertainty,
            ))
            previous_id = fact.frame_id
            session_sequence += 1
        segments.append(_build_segment(segment_id, ordinal, facts, None, member_indices, timing_quality="reconstructed_sequence_order"))

    upgrade_provenance = {
        "derivation_method": "legacy_sequence_reconstruction_v1",
        "reconstructed_segment_count": len(open_segments),
    }
    limitations = (
        "derived from a pre-Stage-6.8 capture manifest lacking native per-frame connection "
        "identity and host receive time; segment boundaries and ordering are a best-effort, "
        "deterministic reconstruction from source-local sequence numbers, not a proven "
        "recovery of true wall-clock order across connections",
    )
    return SessionTimeline(DERIVED_SESSION_TIMELINE, tuple(timeline_frames), tuple(segments), limitations, upgrade_provenance)


__all__ = [
    "DERIVED_SESSION_TIMELINE",
    "INSUFFICIENT_TEMPORAL_PROVENANCE",
    "LEGACY_RECONNECT_GAP_UNCERTAINTY_MS",
    "LONG_GAP_THRESHOLD_MS",
    "MAX_TIMELINE_FRAMES",
    "NATIVE_CLOCK_REGRESSION_UNCERTAINTY_MS",
    "NATIVE_RECONNECT_UNCERTAINTY_MS",
    "NATIVE_SESSION_TIMELINE",
    "NATIVE_WITHIN_SEGMENT_UNCERTAINTY_MS",
    "SESSION_TIMELINE_CLASSIFICATIONS",
    "ConnectionSegment",
    "FrameTimelineFact",
    "SessionTimeline",
    "SessionTimelineError",
    "SourceFrameFact",
    "derive_session_timeline",
]
