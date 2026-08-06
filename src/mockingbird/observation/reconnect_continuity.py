"""Provider-neutral reconnect-safe tracker-continuity decision (Stage 6.11).

Distinguishes benign Camera Node transport reconnection -- where a bounded
active tracker generation may safely bridge the gap -- from genuine
source/provider discontinuity, where tracker state must reset. See
docs/reconnect-continuity-contract.md.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, camera-provider, or
product-repository import anywhere in this module, mirroring every other
Stage 6.x decision module (`burst_scheduler`, `session_timeline`). Every
input is a bounded, already-supplied fact; nothing here reads a clock,
recomputes a current timestamp, or uses species/class identity.

## Three separate concepts (see the module docstring in `frame_tracker.py`
## and docs/reconnect-continuity-contract.md for the full architectural rule)

- A **transport connection segment** is one HTTP analysis-stream connection.
  It may reset transport sequence, connection-local source offset, and
  request/session identifier -- none of that alone proves the camera
  changed, the observation source changed, or a track must end.
- An **observation source generation** is a durable identity for the logical
  analysis source. It changes only when evidence indicates continuity is
  unsafe (Stream/Camera Node/camera identity change, incompatible analysis
  profile, explicit provider reset, or excessive/uncertain discontinuity).
- A **track generation** (owned by `frame_tracker.ProviderNeutralFrameTracker`)
  is one coherent subject episode that may span more than one benign
  transport connection segment when continuity remains supported.
"""

from __future__ import annotations

from dataclasses import dataclass

from mockingbird.observation.contracts import FramePacket


# --- the four-way bounded continuity decision -------------------------------

CONTINUE_ACROSS_TRANSPORT_RECONNECT = "continue_across_transport_reconnect"
TEMPORARILY_LOST_ACROSS_RECONNECT = "temporarily_lost_across_reconnect"
RESET_SOURCE_GENERATION = "reset_source_generation"
REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE = "reject_continuity_insufficient_provenance"

# `TEMPORARILY_LOST_ACROSS_RECONNECT` is not returned by the boundary
# classifier below -- it is the bounded *per-track* status a tracker applies
# to each currently active track once `CONTINUE_ACROSS_TRANSPORT_RECONNECT`
# is granted (see `frame_tracker.ProviderNeutralFrameTracker.
# note_reconnect_boundary`), reusing the existing `lifecycle_state=
# "temporarily_lost"` vocabulary rather than adding a new externally-visible
# lifecycle value. It is listed here because it is part of the same stable,
# provider-neutral decision vocabulary this module owns.
RECONNECT_CONTINUITY_DECISIONS = (
    CONTINUE_ACROSS_TRANSPORT_RECONNECT,
    TEMPORARILY_LOST_ACROSS_RECONNECT,
    RESET_SOURCE_GENERATION,
    REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE,
)

# --- stable reason codes explaining *why* a decision was reached -----------

REASON_BENIGN_TRANSPORT_RECONNECT = "benign_transport_reconnect"
REASON_STREAM_CHANGED = "stream_changed"
REASON_PROVIDER_GENERATION_CHANGED = "provider_generation_changed"
REASON_CAMERA_IDENTITY_CHANGED = "camera_identity_changed"
REASON_CAMERA_NODE_IDENTITY_CHANGED = "camera_node_identity_changed"
REASON_ANALYSIS_PROFILE_INCOMPATIBLE = "analysis_profile_incompatible"
REASON_EXPLICIT_DISCONTINUITY = "explicit_discontinuity_reason"
REASON_SHUTDOWN_START_BOUNDARY = "shutdown_start_boundary"
REASON_EXCESSIVE_RECONNECT_GAP = "excessive_reconnect_gap"
REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY = "excessive_temporal_uncertainty"
REASON_MISSING_CONNECTION_SEGMENT_IDENTITY = "missing_connection_segment_identity"
REASON_MISSING_SOURCE_GAP_PROVENANCE = "missing_source_gap_provenance"
REASON_MISSING_TEMPORAL_UNCERTAINTY_PROVENANCE = "missing_temporal_uncertainty_provenance"
REASON_MISSING_PROVIDER_GENERATION_PROVENANCE = "missing_provider_generation_provenance"
REASON_CONNECTION_SEGMENT_NOT_ADVANCED = "connection_segment_not_advanced"
REASON_NON_MONOTONIC_SOURCE_GAP = "non_monotonic_source_gap"


@dataclass(frozen=True)
class ReconnectBridgeConfig:
    """Bounded, general-purpose policy for bridging one active tracker
    generation across a benign Camera Node transport reconnect.

    These are general defaults, not values tuned only until any one
    session's replay passes -- see docs/reconnect-continuity-contract.md for
    the real-session gap measurements (940-6868ms across session-03/04) this
    was sanity-checked against.
    """

    #: A reconnect whose measured source/session-relative gap exceeds this
    #: is no longer treated as an ordinary transport hiccup, regardless of
    #: how much other provenance looks benign.
    maximum_reconnect_gap_ms: int = 15_000
    #: A known `temporal_uncertainty_ms` above this bound is treated as an
    #: excessive/uncertain discontinuity (a `reset_source_generation`
    #: trigger), not a benign reconnect.
    maximum_temporal_uncertainty_ms: int = 2_000
    #: Bounded session-relative-time patience budget for post-reconnect
    #: reacquisition once a bridge begins, independent of and typically
    #: larger than the tracker's own ordinary `tracker_expiry_ms`/
    #: `maximum_frame_gap_ms` (which a real reconnect gap routinely
    #: exceeds by design -- that is exactly the case this bridge exists to
    #: cover).
    maximum_reconnect_bridge_duration_ms: int = 8_000
    #: Bounded count of analysis frames processed while a track remains
    #: reconnect-pending, independent of the duration budget above.
    maximum_reconnect_bridge_frames: int = 8
    #: Maximum normalized centroid displacement between a pending track's
    #: last known geometry and a candidate post-reconnect detection for
    #: reacquisition to be considered compatible. Deliberately tighter than
    #: the tracker's own ordinary `maximum_centroid_distance` (0.22 default):
    #: position uncertainty across an unknown-duration reconnect gap
    #: warrants more caution than ordinary frame-to-frame association, to
    #: avoid trading fragmentation for incorrect merges.
    maximum_reconnect_geometry_displacement: float = 0.18
    #: Maximum fractional box-area change (|new - old| / old) tolerated for
    #: the same reacquisition compatibility test.
    maximum_reconnect_size_change_ratio: float = 0.5
    #: Bounded count of genuine post-reconnect detector/tracker-support
    #: matches required to consider a track reacquired. Reconnect survival
    #: itself never counts toward this -- only real post-reconnect evidence.
    minimum_post_reconnect_support: int = 1
    #: The only implemented ambiguity policy: an ambiguous post-reconnect
    #: association (more than one active subject plausibly compatible with
    #: one incoming detection) is rejected rather than guessed -- neither
    #: candidate is silently bridged from that detection.
    ambiguity_policy: str = "reject"

    def __post_init__(self) -> None:
        if (
            not 1 <= self.maximum_reconnect_gap_ms <= 300_000
            or not 0 <= self.maximum_temporal_uncertainty_ms <= 60_000
            or not 1 <= self.maximum_reconnect_bridge_duration_ms <= 300_000
            or not 1 <= self.maximum_reconnect_bridge_frames <= 200
            or not 0.0 < self.maximum_reconnect_geometry_displacement <= 1.0
            or not 0.0 < self.maximum_reconnect_size_change_ratio <= 5.0
            or self.minimum_post_reconnect_support < 1
            or self.ambiguity_policy != "reject"
        ):
            raise ValueError("invalid_reconnect_bridge_config")


@dataclass(frozen=True)
class ReconnectContinuityDecision:
    """One bounded, provider-neutral continuity decision for a single
    recognized discontinuity boundary between two consecutive analysis
    frames."""

    decision: str
    reason: str
    source_gap_ms: int | None = None
    temporal_uncertainty_ms: int | None = None
    previous_connection_segment_id: str | None = None
    current_connection_segment_id: str | None = None

    def __post_init__(self) -> None:
        if self.decision not in RECONNECT_CONTINUITY_DECISIONS:
            raise ValueError("invalid_reconnect_continuity_decision")


def is_reconnect_boundary_signal(previous: FramePacket, current: FramePacket) -> bool:
    """Whether any positive discontinuity signal is present between two
    consecutive analysis frames -- the same two native Stage 6.8 signals
    the frame-driven replay host already checked: a real `provider_generation`
    change, or an explicit `temporal_discontinuity` timing fact (set on every
    reconnect boundary by `session_timeline.derive_session_timeline`; see
    docs/session-timeline-contract.md). Returns `False` whenever neither
    fact is present, which is every replay input built before Stage 6.8 --
    this never changes behavior for one.

    This is only the *outer* gate ("was anything unusual signaled at all").
    `classify_frame_reconnect_boundary` below makes the actual bridge-or-
    reset decision once this returns `True`.
    """

    if (
        previous.provider_generation is not None
        and current.provider_generation is not None
        and previous.provider_generation != current.provider_generation
    ):
        return True
    return bool(dict(current.timing_facts).get("temporal_discontinuity"))


def classify_frame_reconnect_boundary(
    previous: FramePacket,
    current: FramePacket,
    config: ReconnectBridgeConfig,
) -> ReconnectContinuityDecision:
    """Classify one recognized discontinuity boundary as a benign transport
    reconnect a bounded tracker bridge may survive, a confidently evidenced
    source-generation reset, or an insufficient-provenance safety reset.

    Only call this once `is_reconnect_boundary_signal(previous, current)` is
    `True` -- a caller that never sees a discontinuity signal at all should
    never reach this classifier, preserving pre-Stage-6.11 behavior exactly
    for every input that carries none of this provenance.

    Deliberately never reads species/class identity. Every input is a
    bounded fact already carried by the two supplied `FramePacket`s
    (`stream_id`, `provider_generation`, `width`/`height`, and additive
    `timing_facts` keys: `connection_segment_id`, `temporal_uncertainty_ms`,
    and the optional forward-compatible `camera_id`/`camera_node_id`/
    `analysis_profile_id`/`explicit_discontinuity_reason`/
    `shutdown_boundary` keys a future live producer may set).
    """

    current_facts = dict(current.timing_facts)
    previous_facts = dict(previous.timing_facts)
    gap_ms = None
    if previous.source_offset_ms is not None and current.source_offset_ms is not None:
        gap_ms = current.source_offset_ms - previous.source_offset_ms
    uncertainty_ms = _bounded_int(current_facts.get("temporal_uncertainty_ms"))
    previous_segment = _clean_str(previous_facts.get("connection_segment_id"))
    current_segment = _clean_str(current_facts.get("connection_segment_id"))

    def _decision(decision: str, reason: str) -> ReconnectContinuityDecision:
        return ReconnectContinuityDecision(
            decision,
            reason,
            source_gap_ms=gap_ms,
            temporal_uncertainty_ms=uncertainty_ms,
            previous_connection_segment_id=previous_segment,
            current_connection_segment_id=current_segment,
        )

    # --- confidently evidenced source-generation resets ---------------------
    # Each of these is a positive, already-known fact proving the logical
    # analysis source changed (or an explicit boundary was declared) --
    # never merely inferred from an absence of data.
    if previous.stream_id != current.stream_id:
        return _decision(RESET_SOURCE_GENERATION, REASON_STREAM_CHANGED)
    if (
        previous.provider_generation is not None
        and current.provider_generation is not None
        and previous.provider_generation != current.provider_generation
    ):
        return _decision(RESET_SOURCE_GENERATION, REASON_PROVIDER_GENERATION_CHANGED)
    for key, reason in (
        ("camera_id", REASON_CAMERA_IDENTITY_CHANGED),
        ("camera_node_id", REASON_CAMERA_NODE_IDENTITY_CHANGED),
        ("analysis_profile_id", REASON_ANALYSIS_PROFILE_INCOMPATIBLE),
    ):
        previous_value, current_value = _clean_str(previous_facts.get(key)), _clean_str(current_facts.get(key))
        if previous_value is not None and current_value is not None and previous_value != current_value:
            return _decision(RESET_SOURCE_GENERATION, reason)
    if (
        previous.width is not None and current.width is not None and previous.width != current.width
    ) or (
        previous.height is not None and current.height is not None and previous.height != current.height
    ):
        return _decision(RESET_SOURCE_GENERATION, REASON_ANALYSIS_PROFILE_INCOMPATIBLE)
    explicit_reason = _clean_str(current_facts.get("explicit_discontinuity_reason"))
    if explicit_reason is not None:
        return _decision(RESET_SOURCE_GENERATION, REASON_EXPLICIT_DISCONTINUITY)
    if bool(current_facts.get("shutdown_boundary")):
        return _decision(RESET_SOURCE_GENERATION, REASON_SHUTDOWN_START_BOUNDARY)

    # --- insufficient provenance to safely bridge ---------------------------
    # A discontinuity signal fired, but the minimum facts this stage needs
    # to *prove* it was an ordinary transport reconnect are missing. This is
    # the safe default for legacy/partial data -- never silently promoted
    # to a bridge just because nothing positively contradicted it.
    if previous_segment is None or current_segment is None:
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_MISSING_CONNECTION_SEGMENT_IDENTITY)
    if gap_ms is None:
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_MISSING_SOURCE_GAP_PROVENANCE)
    if uncertainty_ms is None:
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_MISSING_TEMPORAL_UNCERTAINTY_PROVENANCE)
    if previous.provider_generation is None or current.provider_generation is None:
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_MISSING_PROVIDER_GENERATION_PROVENANCE)
    if previous_segment == current_segment:
        # A discontinuity fired without the connection segment actually
        # advancing -- session-timeline provenance disagrees with itself;
        # do not guess which one is right.
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_CONNECTION_SEGMENT_NOT_ADVANCED)
    if gap_ms < 0:
        return _decision(REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE, REASON_NON_MONOTONIC_SOURCE_GAP)

    # --- known, confident, excessive-gap/uncertainty resets -----------------
    if gap_ms > config.maximum_reconnect_gap_ms:
        return _decision(RESET_SOURCE_GENERATION, REASON_EXCESSIVE_RECONNECT_GAP)
    if uncertainty_ms > config.maximum_temporal_uncertainty_ms:
        return _decision(RESET_SOURCE_GENERATION, REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY)

    return _decision(CONTINUE_ACROSS_TRANSPORT_RECONNECT, REASON_BENIGN_TRANSPORT_RECONNECT)


def _clean_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _bounded_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


__all__ = [
    "CONTINUE_ACROSS_TRANSPORT_RECONNECT",
    "REASON_ANALYSIS_PROFILE_INCOMPATIBLE",
    "REASON_BENIGN_TRANSPORT_RECONNECT",
    "REASON_CAMERA_IDENTITY_CHANGED",
    "REASON_CAMERA_NODE_IDENTITY_CHANGED",
    "REASON_CONNECTION_SEGMENT_NOT_ADVANCED",
    "REASON_EXCESSIVE_RECONNECT_GAP",
    "REASON_EXCESSIVE_TEMPORAL_UNCERTAINTY",
    "REASON_EXPLICIT_DISCONTINUITY",
    "REASON_MISSING_CONNECTION_SEGMENT_IDENTITY",
    "REASON_MISSING_PROVIDER_GENERATION_PROVENANCE",
    "REASON_MISSING_SOURCE_GAP_PROVENANCE",
    "REASON_MISSING_TEMPORAL_UNCERTAINTY_PROVENANCE",
    "REASON_NON_MONOTONIC_SOURCE_GAP",
    "REASON_SHUTDOWN_START_BOUNDARY",
    "REASON_STREAM_CHANGED",
    "RECONNECT_CONTINUITY_DECISIONS",
    "REJECT_CONTINUITY_INSUFFICIENT_PROVENANCE",
    "RESET_SOURCE_GENERATION",
    "TEMPORARILY_LOST_ACROSS_RECONNECT",
    "ReconnectBridgeConfig",
    "ReconnectContinuityDecision",
    "classify_frame_reconnect_boundary",
    "is_reconnect_boundary_signal",
]
