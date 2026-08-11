"""Provider-neutral deterministic tracking for ordered analysis frames.

The tracker owns only bounded transient geometry and temporal-support facts.  It
has no model, camera, repository, media, or product-write dependency.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from math import hypot
from typing import Literal, NamedTuple, Protocol

from mockingbird.observation.contracts import (
    DetectionEvidenceSample, DetectionObservation, FramePacket, TrackUpdate,
)
from mockingbird.observation.reconnect_continuity import ReconnectBridgeConfig


TRACKER_VERSION = "spatial-frame-tracker-v1"
# Detection Quality Accounting v1 (see
# docs/detection-quality-accounting-contract.md): bounded cap on how many
# per-detection confidence samples one track generation retains. Derived,
# not an arbitrary magic number: `FrameDrivenSettings`'s own default
# `maximum_track_duration_ms` (30000) times its own default `candidate_
# detector_fps` (4.0) is ~120 -- the theoretical maximum genuine matched
# detections one generation could ever accumulate under today's real
# deployment configuration -- rounded up. A differently-configured tracker
# (a longer `maximum_track_duration_ms`, a test fixture, or a future
# candidate detector's own settings) can still exceed this cap; when it
# does, `ConfidenceEvidenceSummary.sample_truncated` honestly reports it
# rather than growing the retained list without bound.
MAX_TRACK_CONFIDENCE_SAMPLES = 128


@dataclass(frozen=True)
class TrackerConfiguration:
    strong_detection_threshold: float
    minimum_detector_confirmations: int
    minimum_tracker_support_frames: int
    maximum_missed_frames: int
    maximum_frame_gap_ms: int
    tracker_expiry_ms: int
    maximum_track_duration_ms: int
    maximum_active_tracks: int
    minimum_iou: float = 0.05
    maximum_centroid_distance: float = 0.22
    ambiguity_margin: float = 0.01
    # Stage 6.16 considered, then rejected, raising this Stage 4 default
    # (5000ms) to bridge more of the real attempt-3 confidence-dip gaps
    # (observed up to ~10.4s -- see fragmentation-characterization.md): the
    # existing test_ghost_tracker_support_does_not_absorb_a_later_distinct_
    # appearance regression (a previously-fixed reviewed-replay incorrect-
    # merge pattern, a loose/background-echoing tracker-support resolver
    # sustaining a track on pure tracker-support alone) proved a materially
    # larger value measurably weakens exactly the incorrect-merge/ghost-
    # track protection this stage must not trade away. Left unchanged;
    # fragmentation improvement instead comes from `_gap_bound`'s widened
    # per-frame tolerance and the weak-evidence continuity refresh, which do
    # not touch this ceiling's own protective role. See the final report for
    # the measured before/after effect of leaving this bound as-is.
    maximum_unsupported_detector_ms: int = 5000
    negative_detector_frames_to_end: int = 2
    ambiguous_reentry_window_ms: int = 1500
    # Stage 6.16 bounded evidence hierarchy (see
    # docs/sustained-visit-continuity-contract.md and `_widening_eligible`
    # for the full contract). `weak_detector_support_floor` reuses this
    # product's existing calibrated `review_floor` concept/default
    # (`temporal_capture_cli`'s `--review-floor`, already 0.05 in every real
    # deployment config) rather than inventing a scene-specific number: a
    # matched, spatially coherent detection at or above this floor and
    # below `strong_detection_threshold` is genuine but
    # `weak_detector_support`. `maximum_weak_support_span_ms` bounds how
    # long a confirmed track that has *never* shown a genuinely strong hit
    # may draw on the widened confirmed-track gap tolerance before
    # permanently falling back to the ordinary tight bound; default is a
    # small, explicitly-derived multiple (3x) of the existing
    # `maximum_unsupported_detector_ms` default (5000ms) -- not a new,
    # unrelated magic number.
    weak_detector_support_floor: float = 0.05
    maximum_weak_support_span_ms: int = 15000

    def __post_init__(self) -> None:
        if not 0.0 <= self.strong_detection_threshold <= 1.0:
            raise ValueError("invalid_strong_detection_threshold")
        if self.minimum_detector_confirmations < 1 or self.minimum_tracker_support_frames < 1:
            raise ValueError("invalid_confirmation_policy")
        if min(
            self.maximum_missed_frames,
            self.maximum_frame_gap_ms,
            self.tracker_expiry_ms,
            self.maximum_track_duration_ms,
            self.maximum_active_tracks,
            self.maximum_unsupported_detector_ms,
            self.negative_detector_frames_to_end,
            self.ambiguous_reentry_window_ms,
            self.maximum_weak_support_span_ms,
        ) < 1:
            raise ValueError("invalid_tracker_bound")
        if not 0.0 <= self.weak_detector_support_floor <= self.strong_detection_threshold:
            raise ValueError("invalid_weak_detector_support_floor")


@dataclass(frozen=True)
class TrackView:
    track_id: str
    generation_id: str
    lifecycle_state: Literal["tentative", "confirmed", "temporarily_lost"]
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    first_offset_ms: int
    last_offset_ms: int
    detector_confirmation_count: int
    tracker_support_count: int
    confidence: float | None
    supporting_frame_ids: tuple[str, ...]
    # Stage 6.14: the reviewed-source-lineage counterpart of
    # `supporting_frame_ids` -- see docs/reviewed-replay-lineage-contract.md.
    # Defaulted so every pre-existing positional `TrackView(...)` call site
    # (this module's own `.view()`, `frame_driven_provider._view_from_update`)
    # remains valid unchanged.
    supporting_source_frame_ids: tuple[str, ...] = ()
    # Stage 6.16: bounded evidence-hierarchy provenance, defaulted for the
    # same backward-compatibility reason as the field above.
    weak_detector_support_count: int = 0
    support_state: Literal[
        "strong_detector_supported", "weak_detector_supported", "tracker_supported", "temporarily_lost",
    ] = "temporarily_lost"
    # Stage 6.19: mirrors `_Track.ambiguous_start` below -- see
    # docs/tracklet-visit-assembly-contract.md. Defaulted for the same
    # backward-compatibility reason as the two fields above.
    ambiguous_start: bool = False
    # Detection Quality Accounting v1: mirrors `_Track.confidence_samples`/
    # `max_consecutive_detector_confirmed_frames` below -- see
    # docs/detection-quality-accounting-contract.md. Defaulted for the same
    # backward-compatibility reason as the fields above.
    confidence_samples: tuple[DetectionEvidenceSample, ...] = ()
    max_consecutive_detector_confirmed_frames: int = 0
    # Localization Attribution / Detection Geometry Lineage v1: mirrors
    # `_Track.last_offset_ms` -- see docs/localization-attribution-contract.md
    # and the identical field on `contracts.TrackUpdate`. Defaulted for the
    # same backward-compatibility reason as the fields above; `None` for a
    # `TrackView` reconstructed from something other than a live `_Track`
    # (for example `frame_driven_provider._view_from_update`, which has no
    # way to recover this fact from an already-emitted `TrackUpdate` alone).
    bounding_box_source_offset_ms: int | None = None


class TrackerSupportResolver(Protocol):
    def __call__(
        self,
        frame: FramePacket,
        track: TrackView,
    ) -> tuple[float, float, float, float] | None: ...


@dataclass(frozen=True)
class TerminalTrack:
    view: TrackView
    terminal_reason: str
    confirmed: bool


class _RecentEnding(NamedTuple):
    """A small bounded record of one just-ended generation, kept only to detect
    and honestly report an ambiguous reentry.  It never revives a generation."""

    generation_id: str
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    ended_offset_ms: int
    confident_split: bool


@dataclass(frozen=True)
class TrackerStep:
    updates: tuple[TrackUpdate, ...] = ()
    terminals: tuple[TerminalTrack, ...] = ()
    ambiguous_associations: int = 0
    ambiguous_reentries: int = 0
    # Stage 6.11: internal-only reconnect-bridge outcome counters (not part
    # of the external `TrackUpdate`/`VisitProposal` product contracts --
    # `frame_driven_provider` folds these into its own semantic-fact
    # counters, matching how `ambiguous_associations`/`ambiguous_reentries`
    # already flow through).
    reconnect_bridges_continued: int = 0
    reconnect_bridges_expired: int = 0
    reconnect_ambiguous_associations: int = 0
    # Stage 6.16: count of frames this step where a confirmed track's
    # widened confirmed-track gap tolerance (see `_gap_bound`) was the
    # reason it was not terminated -- i.e. the ordinary tight bound would
    # already have ended it. Internal-only, mirrors the reconnect counters
    # above (`frame_driven_provider` folds it into its own facts).
    confidence_dip_bridges: int = 0


@dataclass
class _Track:
    track_id: str
    generation_id: str
    broad_class: str
    bounding_box: tuple[float, float, float, float]
    first_captured_at: datetime
    last_captured_at: datetime
    first_offset_ms: int
    last_offset_ms: int
    detector_confirmation_count: int
    tracker_support_count: int
    confidence: float | None
    detector_provenance: str | None
    last_detector_offset_ms: int
    lifecycle_state: Literal["tentative", "confirmed", "temporarily_lost"] = "tentative"
    confirmed: bool = False
    missed_frames: int = 0
    consecutive_negative_detector_frames: int = 0
    velocity: tuple[float, float] = (0.0, 0.0)
    supporting_frame_ids: list[str] = field(default_factory=list)
    seen_frame_ids: set[str] = field(default_factory=set)
    # Stage 6.14: independently deduplicated reviewed-source-lineage
    # counterpart of `supporting_frame_ids`/`seen_frame_ids` above -- present
    # only for the supporting frames that actually carried known source
    # lineage (see `FramePacket.source_capture_frame_id`).
    supporting_source_frame_ids: list[str] = field(default_factory=list)
    seen_source_frame_ids: set[str] = field(default_factory=set)
    # Stage 6.11 bounded reconnect-bridge state (see
    # docs/reconnect-continuity-contract.md). `reconnect_pending` marks a
    # track as temporarily lost specifically pending bounded reacquisition
    # across a recognized benign transport reconnect -- distinct from an
    # ordinary detector miss, which uses `missed_frames`/`tracker_expiry_ms`
    # instead. Never persisted, never exposed on `TrackView`/`TrackUpdate`;
    # purely transient tracker-internal bookkeeping released the moment the
    # track reacquires or the bridge window closes.
    reconnect_pending: bool = False
    reconnect_bridge_deadline_offset_ms: int | None = None
    reconnect_bridge_frames_remaining: int | None = None
    # Stage 6.16 bounded evidence hierarchy (see
    # docs/sustained-visit-continuity-contract.md). `weak_detector_support_
    # count` mirrors `detector_confirmation_count`/`tracker_support_count`.
    # `last_strong_detector_offset_ms` is `None` until the first genuinely
    # strong detector hit and only ever advances on another strong hit --
    # weak/tracker-only refreshes never touch it -- so it is exactly the
    # anchor `_gap_bound` needs to bound how long a confirmed track may keep
    # drawing on the widened tolerance. `support_state` names what kind of
    # evidence most recently refreshed this track; never persisted, never
    # itself gating confirmation -- purely descriptive provenance.
    weak_detector_support_count: int = 0
    last_strong_detector_offset_ms: int | None = None
    support_state: Literal[
        "strong_detector_supported", "weak_detector_supported", "tracker_supported", "temporarily_lost",
    ] = "temporarily_lost"
    # Stage 6.19: fixed at `_start()` time from the same `_is_ambiguous_
    # reentry` check already computed there (see docs/tracklet-visit-
    # assembly-contract.md); never changes for the rest of this generation's
    # life, so every update simply carries the value the generation was born
    # with -- a consumer inspecting only a terminal update still sees it.
    ambiguous_start: bool = False
    # Detection Quality Accounting v1 (see
    # docs/detection-quality-accounting-contract.md). `confidence_samples`
    # is bounded by `MAX_TRACK_CONFIDENCE_SAMPLES`; `consecutive_detector_
    # confirmed_frames` is transient (reset by any non-detector-matched
    # frame) mirroring `consecutive_negative_detector_frames`'s own shape,
    # and `max_consecutive_detector_confirmed_frames` is the running max of
    # it for this generation's life, exposed on `TrackView`/`TrackUpdate`.
    confidence_samples: list[DetectionEvidenceSample] = field(default_factory=list)
    consecutive_detector_confirmed_frames: int = 0
    max_consecutive_detector_confirmed_frames: int = 0

    def view(self) -> TrackView:
        return TrackView(
            self.track_id,
            self.generation_id,
            self.lifecycle_state,
            self.broad_class,
            self.bounding_box,
            self.first_offset_ms,
            self.last_offset_ms,
            self.detector_confirmation_count,
            self.tracker_support_count,
            self.confidence,
            tuple(self.supporting_frame_ids),
            tuple(self.supporting_source_frame_ids),
            self.weak_detector_support_count,
            self.support_state,
            self.ambiguous_start,
            tuple(self.confidence_samples),
            self.max_consecutive_detector_confirmed_frames,
            self.last_offset_ms,
        )


class ProviderNeutralFrameTracker:
    """A deterministic one-to-one spatial tracker behind provider-neutral facts."""

    def __init__(
        self,
        stream_id: str,
        configuration: TrackerConfiguration,
        *,
        support_resolver: TrackerSupportResolver | None = None,
        reconnect_bridge_config: ReconnectBridgeConfig | None = None,
    ) -> None:
        self.stream_id = stream_id
        self.configuration = configuration
        self._support_resolver = support_resolver or (lambda _frame, _track: None)
        self._reconnect_bridge_config = reconnect_bridge_config or ReconnectBridgeConfig()
        self._tracks: dict[str, _Track] = {}
        self._next_track = 1
        self._seen_frames: set[str] = set()
        self._last_frame_offset_ms: int | None = None
        self._recent_endings: deque[_RecentEnding] = deque(maxlen=8)

    @property
    def active_count(self) -> int:
        return len(self._tracks)

    def reset(self) -> TrackerStep:
        step = self.finalize("provider_reset")
        self._tracks.clear()
        self._seen_frames.clear()
        self._last_frame_offset_ms = None
        self._recent_endings.clear()
        return step

    @property
    def reconnect_pending_count(self) -> int:
        """Bounded, read-only count of tracks currently awaiting bounded
        reacquisition across a benign reconnect (Stage 6.11). Never grows
        without bound: capped by `active_count`, and every pending track is
        released (reacquired or expired) within its own bounded budget."""
        return sum(1 for track in self._tracks.values() if track.reconnect_pending)

    def note_reconnect_boundary(
        self, *, boundary_offset_ms: int, captured_at: datetime,
    ) -> TrackerStep:
        """Mark every currently active track temporarily lost, pending
        bounded reacquisition, at a recognized benign transport-reconnect
        boundary (Stage 6.11's `continue_across_transport_reconnect`
        decision -- see docs/reconnect-continuity-contract.md).

        Does not terminate anything and does not add detector/tracker
        support by itself -- reconnect survival alone must never create
        fake evidence. Each track's bounded reacquisition window is
        enforced lazily by `observe()`/`_assign()` on subsequent frames,
        exactly like every other tracker bound in this module (checked on
        the next `observe()` call, never by a background timer).
        """
        config = self._reconnect_bridge_config
        boundary_frame = FramePacket(self.stream_id, "", captured_at, None, boundary_offset_ms)
        updates: list[TrackUpdate] = []
        for track in self._tracks.values():
            track.reconnect_pending = True
            track.reconnect_bridge_deadline_offset_ms = boundary_offset_ms + config.maximum_reconnect_bridge_duration_ms
            track.reconnect_bridge_frames_remaining = config.maximum_reconnect_bridge_frames
            track.lifecycle_state = "temporarily_lost"
            track.support_state = "temporarily_lost"
            # A reconnect boundary interrupts the connection itself -- a
            # "consecutive detector-confirmed frames" streak must not claim
            # continuity across it (see docs/detection-quality-accounting-
            # contract.md).
            track.consecutive_detector_confirmed_frames = 0
            # Stage 6.19: a reconnect boundary is a synthetic bookkeeping
            # marker, not a real per-frame detector evaluation -- honestly
            # `detector_ran=False` here, exactly like `finalize()`'s own
            # synthetic terminal frame below.
            updates.append(self._update(track, captured_at, boundary_frame, "updated", detector_ran=False))
        return TrackerStep(tuple(updates))

    def observe(
        self,
        frame: FramePacket,
        detections: tuple[DetectionObservation, ...],
        *,
        detector_ran: bool = False,
    ) -> TrackerStep:
        """Advance the episode boundary by one analysis frame.

        ``detector_ran`` distinguishes an explicit animal-negative detector pass
        (the detector executed and found nothing usable for a track) from an
        idle-cadence frame the detector never inspected.  Only the former counts
        toward ``negative_detector_frames_to_end``; tracker-support alone (for
        example a bounded local patch match) can bridge a brief loss but can
        never by itself keep an episode "genuinely supported" indefinitely --
        ``maximum_unsupported_detector_ms`` bounds that regardless of cadence.
        """
        frame_id = frame.frame_id
        offset = frame.source_offset_ms
        captured_at = frame.captured_at
        if frame_id is None or offset is None or captured_at is None:
            raise ValueError("frame_tracking_metadata_required")
        if frame_id in self._seen_frames:
            return TrackerStep()
        if self._last_frame_offset_ms is not None and offset <= self._last_frame_offset_ms:
            raise ValueError("non_monotonic_tracking_frame")
        self._seen_frames.add(frame_id)
        self._last_frame_offset_ms = offset

        updates: list[TrackUpdate] = []
        terminals: list[TerminalTrack] = []
        confidence_dip_bridges = 0
        for track in tuple(self._tracks.values()):
            if offset - track.first_offset_ms >= self.configuration.maximum_track_duration_ms:
                terminals.append(self._terminate(track, "maximum_duration", captured_at, frame))
            elif track.reconnect_pending:
                # A benign-reconnect bridge is in progress for this track:
                # its own bounded budget (checked below, once reacquisition
                # is actually attempted this frame) governs expiry instead
                # of the ordinary negative/unsupported/gap bounds, which a
                # real reconnect gap routinely exceeds by design. The
                # absolute `maximum_track_duration_ms` cap above still
                # applies unconditionally -- a chain of reconnects can never
                # keep a track alive past its own maximum episode length.
                continue
            elif track.consecutive_negative_detector_frames >= self.configuration.negative_detector_frames_to_end:
                terminals.append(self._terminate(track, "negative_interval_reentry", captured_at, frame))
            elif offset - track.last_detector_offset_ms > self.configuration.maximum_unsupported_detector_ms:
                terminals.append(self._terminate(track, "maximum_unsupported_duration", captured_at, frame))
            else:
                # Stage 6.16: an already-confirmed track recently anchored by
                # a genuinely strong detector hit gets the wider of its
                # ordinary tight gap tolerance and the existing
                # `maximum_unsupported_detector_ms` budget -- a bounded
                # detector-confidence dip or brief tracker-only stretch is
                # not mistaken for departure. See `_gap_bound` and
                # docs/sustained-visit-continuity-contract.md.
                tight_bound = self.configuration.maximum_frame_gap_ms
                gap = offset - track.last_offset_ms
                if gap > self._gap_bound(track, offset, tight_bound):
                    terminals.append(self._terminate(track, "tracker_lost", captured_at, frame))
                elif gap > tight_bound:
                    confidence_dip_bridges += 1

        animals = tuple(
            item
            for item in detections
            if item.is_animal is True
            and item.bounding_box is not None
            and item.frame_id == frame_id
            # Stage 6.16: the tracker's own explicit floor. In today's real
            # deployment this is a no-op safety margin (the ONNX decoder's
            # own `score_threshold` already sits above it), but the tracker
            # must not silently associate literal sub-floor noise to a
            # track regardless of what a future/differently-configured
            # provider's own decode floor happens to be.
            and (item.confidence or 0.0) >= self.configuration.weak_detector_support_floor
        )
        assignments, ambiguous, reconnect_ambiguous = self._assign(animals)
        matched_tracks = {track_id for track_id, _ in assignments}
        matched_detections = {index for _, index in assignments}

        reconnect_bridges_continued = 0
        for track_id, index in assignments:
            track = self._tracks[track_id]
            detection = animals[index]
            if track.reconnect_pending:
                reconnect_bridges_continued += 1
            self._observe_detection(track, detection, frame)
            updates.append(self._update(track, captured_at, frame, "updated", detector_ran=detector_ran))

        reconnect_bridges_expired = 0
        for track in tuple(self._tracks.values()):
            if track.track_id in matched_tracks:
                continue
            supported_box = self._support_resolver(frame, track.view())
            if supported_box is not None and _valid_box(supported_box):
                if track.reconnect_pending:
                    reconnect_bridges_continued += 1
                track.consecutive_negative_detector_frames = 0
                self._observe_tracker_support(track, supported_box, frame)
                updates.append(self._update(track, captured_at, frame, "updated", detector_ran=detector_ran))
                continue
            if track.reconnect_pending:
                # Bounded reconnect-bridge patience: decrement the frame
                # budget and check the session-relative deadline. Neither
                # `missed_frames` nor `consecutive_negative_detector_frames`
                # is touched here -- the gap itself must not accumulate as
                # either detector-negative or ordinary-miss evidence; only
                # real post-reconnect evidence (handled above) clears
                # `reconnect_pending` (see `_observe_detection`/
                # `_observe_tracker_support`).
                assert track.reconnect_bridge_frames_remaining is not None
                assert track.reconnect_bridge_deadline_offset_ms is not None
                # No detection matched this track this frame -- a
                # "consecutive detector-confirmed frames" streak cannot
                # continue through a reconnect gap either (see
                # docs/detection-quality-accounting-contract.md).
                track.consecutive_detector_confirmed_frames = 0
                track.reconnect_bridge_frames_remaining -= 1
                expired = (
                    track.reconnect_bridge_frames_remaining <= 0
                    or offset > track.reconnect_bridge_deadline_offset_ms
                )
                if expired:
                    reconnect_bridges_expired += 1
                    terminals.append(self._terminate(track, "reconnect_bridge_expired", captured_at, frame))
                else:
                    updates.append(self._update(track, captured_at, frame, "updated", detector_ran=detector_ran))
                continue
            if detector_ran:
                track.consecutive_negative_detector_frames += 1
            track.missed_frames += 1
            track.lifecycle_state = "temporarily_lost"
            track.support_state = "temporarily_lost"
            # No detection matched this track this frame -- see the
            # reconnect-branch comment above for why this streak resets here
            # too, regardless of whether the detector ran at all.
            track.consecutive_detector_confirmed_frames = 0
            # Stage 6.16: the same widened tolerance as the pre-check loop
            # above, applied to the ordinary miss-count/expiry bound. A
            # widening-eligible confirmed track relies on the time-based
            # bound alone -- a coarse or jittery real analysis cadence
            # naturally produces more "missed" frames without that meaning
            # the subject actually left.
            tight_bound = self.configuration.tracker_expiry_ms
            gap = offset - track.last_offset_ms
            widened = self._widening_eligible(track, offset)
            missed_exceeded = track.missed_frames > self.configuration.maximum_missed_frames
            bound = max(tight_bound, self.configuration.maximum_unsupported_detector_ms) if widened else tight_bound
            if gap > bound or (missed_exceeded and not widened):
                terminals.append(self._terminate(track, "tracker_lost", captured_at, frame))
            else:
                if widened and (gap > tight_bound or missed_exceeded):
                    confidence_dip_bridges += 1
                # Stage 6.19: this is the one honest source of a genuine
                # detector-negative-vs-skipped-frame distinction (see
                # docs/tracklet-visit-assembly-contract.md) -- `detector_ran`
                # here is this exact frame's own already-known value, carried
                # onto the emitted update rather than discarded.
                updates.append(self._update(track, captured_at, frame, "updated", detector_ran=detector_ran))

        ambiguous_reentries = 0
        for index, detection in enumerate(animals):
            if index in matched_detections:
                continue
            if len(self._tracks) >= self.configuration.maximum_active_tracks:
                continue
            track, reentry_ambiguous = self._start(detection, frame)
            if reentry_ambiguous:
                ambiguous_reentries += 1
            updates.append(self._update(track, captured_at, frame, "started", detector_ran=detector_ran))

        updates.extend(
            self._terminal_update(item, captured_at, frame, detector_ran=detector_ran) for item in terminals
        )
        return TrackerStep(
            tuple(updates), tuple(terminals), ambiguous, ambiguous_reentries,
            reconnect_bridges_continued, reconnect_bridges_expired, reconnect_ambiguous,
            confidence_dip_bridges,
        )

    def finalize(self, reason: str = "end_of_replay") -> TrackerStep:
        updates: list[TrackUpdate] = []
        terminals: list[TerminalTrack] = []
        for track in sorted(self._tracks.values(), key=lambda item: item.generation_id):
            terminal_reason = reason
            captured_at = track.last_captured_at
            frame = FramePacket(
                self.stream_id,
                "",
                captured_at,
                track.supporting_frame_ids[-1] if track.supporting_frame_ids else None,
                track.last_offset_ms,
            )
            terminal = self._terminate(track, terminal_reason, captured_at, frame)
            terminals.append(terminal)
            # Stage 6.19: synthetic end-of-replay/reset frame, not a real
            # per-frame detector evaluation -- honestly `detector_ran=False`.
            updates.append(self._terminal_update(terminal, captured_at, frame, detector_ran=False))
        return TrackerStep(tuple(updates), tuple(terminals))

    def _start(self, detection: DetectionObservation, frame: FramePacket) -> tuple[_Track, bool]:
        assert detection.bounding_box is not None and frame.source_offset_ms is not None and frame.captured_at is not None
        counter = self._next_track
        self._next_track += 1
        seed = (
            f"{self.stream_id}|{frame.frame_id}|{frame.source_offset_ms}|"
            f"{detection.label}|{detection.bounding_box}|{counter}"
        )
        generation = f"{self.stream_id}:frame-track:{sha256(seed.encode()).hexdigest()[:20]}"
        ambiguous = self._is_ambiguous_reentry(detection, frame)
        # Stage 6.16: the very first observation a generation is seeded from
        # is classified strong/weak exactly like any later one in
        # `_observe_detection` -- `detector_confirmation_count` still starts
        # at 1 unconditionally (unchanged pre-existing behavior; see the
        # long comment in `_observe_detection` for why), while
        # `weak_detector_support_count`/`last_strong_detector_offset_ms`/
        # `support_state` record which kind this first one was.
        strong = (detection.confidence or 0.0) >= self.configuration.strong_detection_threshold
        track = _Track(
            f"frame-track-{counter:04d}",
            generation,
            detection.label,
            detection.bounding_box,
            frame.captured_at,
            frame.captured_at,
            frame.source_offset_ms,
            frame.source_offset_ms,
            1,
            0,
            detection.confidence,
            detection.detector_id,
            frame.source_offset_ms,
            supporting_frame_ids=[frame.frame_id or ""],
            seen_frame_ids={frame.frame_id or ""},
            supporting_source_frame_ids=[frame.source_capture_frame_id] if frame.source_capture_frame_id else [],
            seen_source_frame_ids={frame.source_capture_frame_id} if frame.source_capture_frame_id else set(),
            weak_detector_support_count=0 if strong else 1,
            last_strong_detector_offset_ms=frame.source_offset_ms if strong else None,
            support_state="strong_detector_supported" if strong else "weak_detector_supported",
            ambiguous_start=ambiguous,
            confidence_samples=[_evidence_sample(detection, frame, is_strong=strong)],
            consecutive_detector_confirmed_frames=1,
            max_consecutive_detector_confirmed_frames=1,
        )
        self._tracks[track.track_id] = track
        return track, ambiguous

    def _is_ambiguous_reentry(self, detection: DetectionObservation, frame: FramePacket) -> bool:
        """Report -- never revive -- a start that could plausibly be the same
        subject as a recently, but not confidently, ended generation."""
        assert detection.bounding_box is not None and frame.source_offset_ms is not None
        for ending in self._recent_endings:
            if ending.confident_split or ending.broad_class != detection.label:
                continue
            if frame.source_offset_ms - ending.ended_offset_ms > self.configuration.ambiguous_reentry_window_ms:
                continue
            distance = hypot(*(
                left - right for left, right in zip(_center(ending.bounding_box), _center(detection.bounding_box))
            ))
            if (
                _iou(ending.bounding_box, detection.bounding_box) >= self.configuration.minimum_iou
                or distance <= self.configuration.maximum_centroid_distance
            ):
                return True
        return False

    def _clear_reconnect_pending(self, track: _Track) -> None:
        """Real post-reconnect evidence just matched this track -- release
        its bounded bridge budget. Only called from `_observe_detection`/
        `_observe_tracker_support`, i.e. only when genuine detector or
        tracker-support evidence was found; reconnect survival alone never
        reaches here."""
        track.reconnect_pending = False
        track.reconnect_bridge_deadline_offset_ms = None
        track.reconnect_bridge_frames_remaining = None

    def _widening_eligible(self, track: _Track, offset: int) -> bool:
        """Stage 6.16: whether `track` currently qualifies for the widened
        confirmed-track gap tolerance (`_gap_bound`) -- already confirmed
        (the existing, unchanged `minimum_detector_confirmations` repeated-
        evidence bar, not a strength bar, already filters out one-off
        noise). Two tiers, both bounded:

        - "Graduated": the track has shown at least one genuinely strong
          detector hit at any point in its life (`last_strong_detector_
          offset_ms is not None`). Real attempt-3 evidence shows a
          genuinely continuous real subject's own detector confidence can
          swing for minutes with only rare peaks above
          `strong_detection_threshold` (see fragmentation-
          characterization.md) -- once *any* such peak has occurred,
          treating the subject as no longer "just noise" is justified
          without re-requiring recency, so a graduated track keeps the
          widened tolerance for the rest of its life (still bounded by
          `maximum_unsupported_detector_ms`/`maximum_track_duration_ms`
          below and unconditionally by the absolute duration cap).
        - "Provisional": the track has *never* shown a strong hit. It still
          gets the widened tolerance, but only for a bounded, one-time,
          non-renewable window from its own start
          (`maximum_weak_support_span_ms`) -- long enough to bridge a real
          subject's early confidence dips before it has had a chance to
          register a strong hit, short enough that a persistent weak-only
          artifact (which can confirm from repeated coherent evidence
          exactly like a real subject can -- see
          test_persistent_weak_static_artifact_confirms_but_never_gets_
          widened_tolerance) cannot ride an indefinite string of weak/
          tracker-only refreshes: once the window elapses with no strong
          proof ever appearing, it permanently falls back to the ordinary
          tight bound, exactly like every track before this stage."""
        if not track.confirmed:
            return False
        if track.last_strong_detector_offset_ms is not None:
            return True
        return offset - track.first_offset_ms <= self.configuration.maximum_weak_support_span_ms

    def _gap_bound(self, track: _Track, offset: int, tight_bound: int) -> int:
        """Bounded per-frame miss/gap tolerance (Stage 6.16). A widening-
        eligible confirmed track (see `_widening_eligible`) gets the wider
        of its ordinary tight bound and the already-existing, already-
        configured `maximum_unsupported_detector_ms` budget -- reusing that
        bound rather than inventing a new one, so "how long may a confirmed
        subject go with no fresh strong proof" stays one coherent, already-
        bounded number regardless of which specific check is asking. Every
        other track keeps the tight bound unchanged. See
        docs/sustained-visit-continuity-contract.md."""
        if self._widening_eligible(track, offset):
            return max(tight_bound, self.configuration.maximum_unsupported_detector_ms)
        return tight_bound

    def _observe_detection(
        self,
        track: _Track,
        detection: DetectionObservation,
        frame: FramePacket,
    ) -> None:
        assert detection.bounding_box is not None and frame.source_offset_ms is not None and frame.captured_at is not None
        self._clear_reconnect_pending(track)
        old_center = _center(track.bounding_box)
        new_center = _center(detection.bounding_box)
        track.velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
        track.bounding_box = detection.bounding_box
        track.last_captured_at = frame.captured_at
        track.last_offset_ms = frame.source_offset_ms
        track.last_detector_offset_ms = frame.source_offset_ms
        track.missed_frames = 0
        track.consecutive_negative_detector_frames = 0
        track.confidence = max(track.confidence or 0.0, detection.confidence or 0.0)
        # Stage 6.16: `detector_confirmation_count` keeps its exact pre-
        # existing meaning and behavior -- it counts every genuine matched
        # detector observation, unconditionally, exactly as before this
        # stage. This is deliberate, not an oversight: real attempt-3
        # evidence proved a genuinely continuous subject's *confirming*
        # pair of observations is routinely both individually below
        # `strong_detection_threshold` (a real bird's own natural
        # confidence swings, e.g. 0.37 then 0.45 while still clearly the
        # same coherent, repeated, spatially-matched subject) -- gating
        # `minimum_detector_confirmations` itself on strength would have
        # made *initial* confirmation harder, not just continuity more
        # forgiving, directly hurting the appearance recall this stage
        # exists to improve. `minimum_detector_confirmations` was always a
        # *repeated, spatially-coherent evidence* bar, never a strength
        # bar; only a single, isolated observation with nothing
        # corroborating it (weak or strong) fails that bar, unchanged.
        #
        # What *is* new: `weak_detector_support_count` is a separate,
        # purely additive breakdown of how many of those matched
        # observations were specifically weak (provenance/reporting only,
        # gates nothing), and only a genuinely strong hit advances
        # `last_strong_detector_offset_ms` -- the sole anchor `_gap_bound`'s
        # widened confirmed-track tolerance depends on (see
        # `_widening_eligible`). A track confirmed entirely from weak
        # evidence never becomes eligible for that widened tolerance: it
        # still terminates on the same ordinary tight bound as before this
        # stage. See docs/sustained-visit-continuity-contract.md.
        track.detector_confirmation_count += 1
        strong = (detection.confidence or 0.0) >= self.configuration.strong_detection_threshold
        if strong:
            track.last_strong_detector_offset_ms = frame.source_offset_ms
            track.support_state = "strong_detector_supported"
        else:
            track.weak_detector_support_count += 1
            track.support_state = "weak_detector_supported"
        # Detection Quality Accounting v1 (see
        # docs/detection-quality-accounting-contract.md): a genuine matched
        # detector observation, strong or weak -- record it as a bounded
        # sample and extend this generation's own consecutive-confirmation
        # streak. Bounded by `MAX_TRACK_CONFIDENCE_SAMPLES`; once reached,
        # later samples are honestly dropped rather than grown without
        # bound (`ConfidenceEvidenceSummary.sample_truncated` reports this).
        if len(track.confidence_samples) < MAX_TRACK_CONFIDENCE_SAMPLES:
            track.confidence_samples.append(_evidence_sample(detection, frame, is_strong=strong))
        track.consecutive_detector_confirmed_frames += 1
        track.max_consecutive_detector_confirmed_frames = max(
            track.max_consecutive_detector_confirmed_frames, track.consecutive_detector_confirmed_frames,
        )
        self._remember(track, frame)
        self._confirm(track)

    def _observe_tracker_support(
        self,
        track: _Track,
        box: tuple[float, float, float, float],
        frame: FramePacket,
    ) -> None:
        assert frame.source_offset_ms is not None and frame.captured_at is not None
        self._clear_reconnect_pending(track)
        old_center = _center(track.bounding_box)
        new_center = _center(box)
        track.velocity = (new_center[0] - old_center[0], new_center[1] - old_center[1])
        track.bounding_box = box
        track.last_captured_at = frame.captured_at
        track.last_offset_ms = frame.source_offset_ms
        track.missed_frames = 0
        track.tracker_support_count += 1
        track.support_state = "tracker_supported"
        # The detector did not itself confirm this track this frame -- see
        # the docs/detection-quality-accounting-contract.md streak rule.
        track.consecutive_detector_confirmed_frames = 0
        self._remember(track, frame)
        self._confirm(track)

    def _remember(self, track: _Track, frame: FramePacket) -> None:
        frame_id = frame.frame_id
        if frame_id and frame_id not in track.seen_frame_ids:
            track.seen_frame_ids.add(frame_id)
            track.supporting_frame_ids.append(frame_id)
        source_id = frame.source_capture_frame_id
        if source_id and source_id not in track.seen_source_frame_ids:
            track.seen_source_frame_ids.add(source_id)
            track.supporting_source_frame_ids.append(source_id)

    def _confirm(self, track: _Track) -> None:
        strong = (track.confidence or 0.0) >= self.configuration.strong_detection_threshold
        if (
            track.detector_confirmation_count >= self.configuration.minimum_detector_confirmations
            or (
                strong
                and track.tracker_support_count >= self.configuration.minimum_tracker_support_frames
            )
        ):
            track.confirmed = True
            track.lifecycle_state = "confirmed"
        elif track.lifecycle_state == "temporarily_lost":
            track.lifecycle_state = "confirmed" if track.confirmed else "tentative"

    def _assign(
        self,
        detections: tuple[DetectionObservation, ...],
    ) -> tuple[list[tuple[str, int]], int, int]:
        candidates: list[tuple[float, str, int]] = []
        by_detection: dict[int, list[tuple[float, str]]] = {}
        pending_track_ids = {track.track_id for track in self._tracks.values() if track.reconnect_pending}
        for track in self._tracks.values():
            # A pending track's `velocity` reflects motion from *before* the
            # reconnect gap; extrapolating it forward across an unknown,
            # possibly multi-second gap is not well-founded (see
            # docs/reconnect-continuity-contract.md), so reacquisition
            # compares against the track's last *known* geometry directly
            # rather than a velocity-shifted prediction.
            predicted = track.bounding_box if track.reconnect_pending else _shift(track.bounding_box, track.velocity)
            for index, detection in enumerate(detections):
                if detection.label != track.broad_class or detection.bounding_box is None:
                    continue
                overlap = _iou(predicted, detection.bounding_box)
                distance = hypot(*(
                    left - right for left, right in zip(_center(predicted), _center(detection.bounding_box))
                ))
                if overlap < self.configuration.minimum_iou and distance > self.configuration.maximum_centroid_distance:
                    continue
                if track.reconnect_pending and not self._reconnect_reacquisition_compatible(track, detection.bounding_box):
                    continue
                score = overlap - distance
                candidates.append((-score, track.track_id, index))
                by_detection.setdefault(index, []).append((score, track.track_id))
        ambiguous_indices = {
            index
            for index, values in by_detection.items()
            if len(values) > 1
            and sorted(values, reverse=True)[0][0] - sorted(values, reverse=True)[1][0]
            <= self.configuration.ambiguity_margin
        }
        # `ambiguity_policy="reject"` (the only implemented policy, see
        # `ReconnectBridgeConfig`): an ambiguous detection touching at least
        # one reconnect-pending track is reported separately so a reviewer
        # can distinguish ordinary tracking ambiguity from reconnect-related
        # ambiguity, but the outcome is identical either way -- neither
        # candidate track is assigned from that detection below.
        reconnect_ambiguous = sum(
            1
            for index in ambiguous_indices
            if any(track_id in pending_track_ids for _, track_id in by_detection.get(index, []))
        )
        assigned_tracks: set[str] = set()
        assigned_detections: set[int] = set()
        assignments: list[tuple[str, int]] = []
        for _negative_score, track_id, index in sorted(candidates):
            if index in ambiguous_indices or track_id in assigned_tracks or index in assigned_detections:
                continue
            assigned_tracks.add(track_id)
            assigned_detections.add(index)
            assignments.append((track_id, index))
        return assignments, len(ambiguous_indices), reconnect_ambiguous

    def _reconnect_reacquisition_compatible(
        self, track: _Track, candidate_box: tuple[float, float, float, float],
    ) -> bool:
        """Bounded geometry-displacement/size-change gate applied only to a
        reconnect-pending track's own reacquisition candidates, on top of
        the ordinary IoU/centroid association test above. A spatially or
        dimensionally incompatible reentry must start a new generation
        instead of silently bridging (see docs/reconnect-continuity-contract.md,
        `ReconnectBridgeConfig.maximum_reconnect_geometry_displacement`/
        `maximum_reconnect_size_change_ratio`)."""
        config = self._reconnect_bridge_config
        distance = hypot(*(
            left - right for left, right in zip(_center(track.bounding_box), _center(candidate_box))
        ))
        if distance > config.maximum_reconnect_geometry_displacement:
            return False
        previous_area = max(
            1e-9, (track.bounding_box[2] - track.bounding_box[0]) * (track.bounding_box[3] - track.bounding_box[1])
        )
        candidate_area = (candidate_box[2] - candidate_box[0]) * (candidate_box[3] - candidate_box[1])
        size_change_ratio = abs(candidate_area - previous_area) / previous_area
        return size_change_ratio <= config.maximum_reconnect_size_change_ratio

    def _terminate(
        self,
        track: _Track,
        reason: str,
        captured_at: datetime,
        frame: FramePacket,
    ) -> TerminalTrack:
        self._tracks.pop(track.track_id, None)
        confirmed = track.confirmed
        uncertain_reasons = {
            "tracker_lost", "end_of_replay", "maximum_unsupported_duration", "negative_interval_reentry",
            # A bounded reconnect-bridge window closing without reacquisition
            # (Stage 6.11) is the same "bounded tolerance ran out" shape as
            # `tracker_lost`, not positive evidence of discontinuity -- an
            # unconfirmed track relabels to `insufficient_support` exactly
            # like the others, and (see `confident_split` below) a later
            # plausible reentry can still be honestly reported as ambiguous
            # rather than treated as confidently a different subject.
            "reconnect_bridge_expired",
        }
        terminal_reason = reason if confirmed or reason not in uncertain_reasons else "insufficient_support"
        confident_split = reason in {"maximum_unsupported_duration", "negative_interval_reentry"}
        self._recent_endings.append(_RecentEnding(
            track.generation_id, track.broad_class, track.bounding_box, track.last_offset_ms, confident_split,
        ))
        return TerminalTrack(track.view(), terminal_reason, confirmed)

    def _update(
        self,
        track: _Track,
        captured_at: datetime,
        frame: FramePacket,
        status: Literal["started", "updated"],
        *,
        detector_ran: bool,
    ) -> TrackUpdate:
        return TrackUpdate(
            track.track_id,
            track.generation_id,
            captured_at,
            status,
            track.lifecycle_state,
            frame.frame_id,
            frame.source_offset_ms,
            track.broad_class,
            track.bounding_box,
            tuple(track.supporting_frame_ids),
            track.detector_confirmation_count,
            track.tracker_support_count,
            track.confidence,
            track.detector_provenance,
            TRACKER_VERSION,
            supporting_source_capture_frame_ids=tuple(track.supporting_source_frame_ids),
            weak_detector_support_count=track.weak_detector_support_count,
            support_state=track.support_state,
            detector_ran=detector_ran,
            ambiguous_start=track.ambiguous_start,
            confidence_samples=tuple(track.confidence_samples),
            max_consecutive_detector_confirmed_frames=track.max_consecutive_detector_confirmed_frames,
            bounding_box_source_offset_ms=track.last_offset_ms,
        )

    def _terminal_update(
        self,
        terminal: TerminalTrack,
        captured_at: datetime,
        frame: FramePacket,
        *,
        detector_ran: bool,
    ) -> TrackUpdate:
        view = terminal.view
        return TrackUpdate(
            view.track_id,
            view.generation_id,
            captured_at,
            "ended",
            "ended" if terminal.confirmed else "rejected",
            frame.frame_id,
            frame.source_offset_ms,
            view.broad_class,
            view.bounding_box,
            view.supporting_frame_ids,
            view.detector_confirmation_count,
            view.tracker_support_count,
            view.confidence,
            None,
            TRACKER_VERSION,
            terminal.terminal_reason,
            supporting_source_capture_frame_ids=view.supporting_source_frame_ids,
            weak_detector_support_count=view.weak_detector_support_count,
            support_state=view.support_state,
            detector_ran=detector_ran,
            ambiguous_start=view.ambiguous_start,
            confidence_samples=view.confidence_samples,
            max_consecutive_detector_confirmed_frames=view.max_consecutive_detector_confirmed_frames,
            bounding_box_source_offset_ms=view.bounding_box_source_offset_ms,
        )


def _evidence_sample(
    detection: DetectionObservation, frame: FramePacket, *, is_strong: bool,
) -> DetectionEvidenceSample:
    """One bounded Detection Quality Accounting v1 sample from a genuine
    matched detector observation (see
    docs/detection-quality-accounting-contract.md). `confidence` follows
    this module's own established `detection.confidence or 0.0` convention
    for treating an absent score as zero (matching the `animals` filter in
    `observe()` and every other confidence read in this file).

    `bounding_box` (Localization Attribution / Detection Geometry Lineage v1
    -- see docs/localization-attribution-contract.md) is the exact raw
    source-coordinate box this genuine detection reported -- already in
    scope here, simply not previously retained."""
    return DetectionEvidenceSample(
        confidence=detection.confidence if detection.confidence is not None else 0.0,
        source_offset_ms=frame.source_offset_ms,
        frame_id=frame.frame_id,
        observation_id=detection.observation_id,
        is_strong=is_strong,
        bounding_box=detection.bounding_box,
    )


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _shift(
    box: tuple[float, float, float, float],
    velocity: tuple[float, float],
) -> tuple[float, float, float, float]:
    return tuple(
        max(0.0, min(1.0, value + velocity[index % 2]))
        for index, value in enumerate(box)
    )


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(0.0 <= value <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )


def _iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    x0, y0 = max(left[0], right[0]), max(left[1], right[1])
    x1, y1 = min(left[2], right[2]), min(left[3], right[3])
    intersection = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    left_area = (left[2] - left[0]) * (left[3] - left[1])
    right_area = (right[2] - right[0]) * (right[3] - right[1])
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
