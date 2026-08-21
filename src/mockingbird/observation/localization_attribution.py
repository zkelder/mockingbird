"""Localization Attribution / Detection Geometry Lineage v1 (see
docs/localization-attribution-contract.md).

Answers, for one persisted candidate's evidence box: which observation
supplied this geometry, was it a genuine detector hit or tracker-support
patch match or a stale carried-forward box, and does the evidence image it
is drawn on provably represent the same moment as that observation? This is
diagnostic accounting over already-emitted lineage facts, never
observational truth -- it never inspects pixel content, never decides
whether an animal is actually present, and never feeds back into evidence
selection, admission, or Visit assembly (see "The truth boundary" in
product-doctrine.md).

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- the same structural convention every other Stage 6.x/7
decision module in this package follows (`visit_episode_assembler`,
`candidate_visit_authority`, `candidate_quality_gate`, `admission_policy`).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Literal

from mockingbird.observation.contracts import (
    ConfidenceEvidenceSummary,
    DetectionEvidenceSample,
    GeometryAttribution,
    TrackUpdate,
)

LOCALIZATION_ATTRIBUTION_VERSION = "localization-attribution-v1"

# Reused, not invented: the same bound `TrackerConfiguration.maximum_
# unsupported_detector_ms`/`FrameDrivenSettings.maximum_unsupported_
# detector_ms` already use (5000ms default, both places) for "how long may a
# track go with no fresh detector confirmation before the tracker itself
# would call it lost." Applied here for an analogous purpose one layer up:
# how long may an evidence image's own capture moment drift from the
# geometry's own source moment before that geometry can no longer be trusted
# to represent what the image actually shows. See "Bounded misalignment
# threshold" in docs/localization-attribution-contract.md.
DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS = 5_000

LocalizationAttributionCode = Literal[
    "detector_off_target",
    "tracker_drift",
    "evidence_geometry_misaligned",
    "detector_hit_then_lost",
    "insufficient_geometry_lineage",
]


@dataclass(frozen=True)
class LocalizationAttributionResult:
    """One deterministic classification of why a persisted candidate's own
    evidence geometry may not represent a visible subject. Reason strings
    are stable, sanitized codes -- never raw exception text. Carries the raw
    facts it was decided from so a caller/report can explain the decision
    without recomputing it."""

    attribution: LocalizationAttributionCode
    reason: str
    geometry_source: Literal["detector", "tracker", "carried_forward"] | None
    geometry_evidence_gap_ms: int | None

    def __post_init__(self) -> None:
        if self.geometry_evidence_gap_ms is not None and self.geometry_evidence_gap_ms < 0:
            raise ValueError("invalid_localization_attribution_result")


def geometry_source_from_support_state(
    support_state: str | None,
) -> Literal["detector", "tracker", "carried_forward"] | None:
    """The tracker's own `TrackUpdate.support_state` already distinguishes
    exactly the three kinds this contract needs, by construction:
    `strong_detector_supported`/`weak_detector_supported` are set only
    inside `frame_tracker._observe_detection` (which also freshly sets
    `bounding_box`/`last_offset_ms` in the same call); `tracker_supported`
    only inside `_observe_tracker_support` (same guarantee); `temporarily_
    lost` is the one state where neither ran this frame, so `bounding_box`
    is simply whatever it was last genuinely set to -- see
    `contracts.TrackUpdate.bounding_box_source_offset_ms`. Reusing this
    existing, already-correct-by-construction fact is deliberate: a second,
    independently-derived offset-freshness check could only ever disagree
    with it if the tracker's own invariant were broken, which would be a
    tracker bug to fix there, not paper over here.

    Public (not module-private): `mockingbird.observation.counterfactual_
    lineage` reuses this exact mapping one layer earlier -- for a track
    generation's own last-known geometry, independent of whether that
    geometry ever became any persisted candidate's evidence box -- rather
    than duplicating the same three-way mapping a second time (Rejected /
    Suppressed Detection Attribution v1, see docs/rejected-detection
    -attribution-contract.md)."""
    if support_state in ("strong_detector_supported", "weak_detector_supported"):
        return "detector"
    if support_state == "tracker_supported":
        return "tracker"
    if support_state == "temporarily_lost":
        return "carried_forward"
    return None


def _matching_confidence_sample(update: TrackUpdate) -> DetectionEvidenceSample | None:
    """The confidence sample that corresponds to this update's own
    detector-sourced geometry, when one exists. `TrackUpdate.
    confidence_samples` is cumulative-so-far; the *last* one is the exact
    match precisely when this update's own geometry was itself freshly set
    by a genuine detection this frame -- `frame_tracker._observe_detection`
    appends the sample and sets `bounding_box`/`last_offset_ms` together,
    atomically, so the offsets can only agree when it really is the same
    observation. Never a guess: if the offsets do not agree (or there are no
    samples at all -- for example a legacy-reconstructed `TrackUpdate`),
    this honestly returns `None` rather than attributing the wrong sample."""
    if not update.confidence_samples:
        return None
    candidate = update.confidence_samples[-1]
    if (
        update.bounding_box_source_offset_ms is None
        or candidate.source_offset_ms != update.bounding_box_source_offset_ms
    ):
        return None
    return candidate


def geometry_attribution_for_update(
    update: TrackUpdate,
    *,
    same_frame: bool,
    evidence_source_offset_ms: int | None = None,
    measured_gap_ms: int | None = None,
    fov_alignment_proven: bool | None = None,
    geometry_transform_id: str | None = None,
    misalignment_gap_threshold_ms: int = DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
) -> GeometryAttribution:
    """Build the `GeometryAttribution` fact for one `EvidenceCandidate` whose
    `subject_geometry` is `update.bounding_box`.

    `same_frame` is a structural fact the caller already knows from its own
    construction -- never guessed here (see `GeometryAttribution.
    same_frame`). When `same_frame` is `False`, the gap is `measured_gap_ms`
    when the caller already has a real, independently-measured delta (for
    example a Camera Node evidence burst's own `request_to_capture_ms`,
    computed by the transport from two real timestamps -- see
    `geometry_attribution_for_burst`); otherwise it is derived from
    `evidence_source_offset_ms - update.bounding_box_source_offset_ms` when
    both are known, and left honestly `None` when neither is available.

    `fov_alignment_proven`/`geometry_transform_id` (Source-Resolution +
    Multi-Frame Species Evidence v1, additive) are only ever consulted when
    `same_frame` is `False` -- an exact same-frame capture is always
    `resolution_provenance="exact_same_frame"` regardless of any alignment
    fact, matching `GeometryAttribution`'s own cross-field invariant.
    """
    source = geometry_source_from_support_state(update.support_state)
    sample = _matching_confidence_sample(update) if source == "detector" else None
    if same_frame:
        gap_ms: int | None = 0
        resolution_provenance: (
            Literal["exact_same_frame", "synchronized", "near_time_capture", "fallback"]
        ) = "exact_same_frame"
    else:
        if measured_gap_ms is not None:
            gap_ms = measured_gap_ms
        elif evidence_source_offset_ms is not None and update.bounding_box_source_offset_ms is not None:
            gap_ms = abs(evidence_source_offset_ms - update.bounding_box_source_offset_ms)
        else:
            gap_ms = None
        resolution_provenance = resolution_provenance_for_burst(
            fov_alignment_proven=fov_alignment_proven,
            gap_ms=gap_ms,
            misalignment_gap_threshold_ms=misalignment_gap_threshold_ms,
        )
    return GeometryAttribution(
        geometry_source=source,
        geometry_source_offset_ms=update.bounding_box_source_offset_ms,
        geometry_source_observation_id=sample.observation_id if sample is not None else None,
        geometry_source_confidence=sample.confidence if sample is not None else None,
        same_frame=same_frame,
        geometry_evidence_gap_ms=gap_ms,
        fov_alignment_proven=fov_alignment_proven if not same_frame else None,
        geometry_transform_id=geometry_transform_id if not same_frame else None,
        resolution_provenance=resolution_provenance,
    )


# Source-Resolution + Multi-Frame Species Evidence v1: the same bounded gap
# already used to decide whether a burst's geometry is trustworthy *at all*
# (`DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS`, reused rather than a second
# invented number) also gates the stricter "synchronized" resolution-
# provenance tier -- a real, FOV-proven-aligned dual-stream capture is only
# ever called "synchronized" when its own measured gap is inside the exact
# same bound `classify_localization_attribution` already uses to decide the
# geometry is not misaligned; a proven-aligned capture with an excessive gap
# is `"near_time_capture"`, never a contradiction between the two facts.


def resolution_provenance_for_burst(
    *,
    fov_alignment_proven: bool | None,
    gap_ms: int | None,
    misalignment_gap_threshold_ms: int = DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
) -> Literal["synchronized", "near_time_capture", "fallback"]:
    """Classify a genuinely-separate (never `same_frame`) evidence capture's
    own place in the milestone's resolution-provenance vocabulary (see
    `GeometryAttribution.resolution_provenance` and "Resolution/provenance
    vocabulary" in docs/source-resolution-multi-frame-species-evidence
    -contract.md), from plain, already-computed facts only -- never imports
    `mockingbird.motion.high_resolution_evidence` itself (this module stays
    free of that module's OpenCV/NumPy dependency; a caller that already
    called `resolve_alignment` passes in only its boolean verdict).

    - `"synchronized"`: FOV alignment is proven (`fov_alignment_proven is
      True`) *and* the measured gap is known and within the bounded
      misalignment threshold -- a real, later capture, but from a
      continuously-configured dual-stream session showing the identical
      field of view, with a tightly bounded, honestly-measured delta.
    - `"near_time_capture"`: a real, bounded-gap capture that is not proven
      to share the same field of view (alignment unproven, or the provider
      never reports the fact at all) -- honestly retained as evidence, but
      never safe to crop a reused subject box against.
    - `"fallback"`: the gap is unknown or exceeds the bounded threshold --
      no defensible temporal *or* spatial correspondence claim.
    """
    if misalignment_gap_threshold_ms < 0:
        raise ValueError("invalid_misalignment_gap_threshold")
    if gap_ms is None or gap_ms > misalignment_gap_threshold_ms:
        return "fallback"
    if fov_alignment_proven is True:
        return "synchronized"
    return "near_time_capture"


def geometry_attribution_for_burst(
    update: TrackUpdate,
    *,
    request_to_capture_ms: int | None,
    fov_alignment_proven: bool | None = None,
    geometry_transform_id: str | None = None,
    misalignment_gap_threshold_ms: int = DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
) -> GeometryAttribution:
    """`GeometryAttribution` for a high-resolution Camera Node evidence
    burst (`camera_node_live.py`): a genuinely separate, later real capture
    event by construction, never the same frame as the triggering analysis
    update that supplied `subject_geometry` -- see `EvidenceBurstFrame.
    request_to_capture_ms` (`media_contracts.py`), which is already the
    exact, real, transport-measured delta and needs no offset-origin
    reconstruction.

    `fov_alignment_proven`/`geometry_transform_id` are the caller's already-
    computed `mockingbird.motion.high_resolution_evidence.resolve_alignment`
    facts for this Stream's monitoring/evidence capture-profile pair (`None`
    when alignment was never checked -- for example a provider that does not
    report capture-profile geometry at all). Used only to compute the
    honest `resolution_provenance` tier below; never to fabricate a mapped
    box here (a caller that wants an actually-transformed `subject_geometry`
    applies `NormalizedGeometryTransform.map_box` itself before building the
    `EvidenceCandidate`, using the exact transform this `geometry_transform_id`
    names)."""
    return geometry_attribution_for_update(
        update,
        same_frame=False,
        measured_gap_ms=request_to_capture_ms,
        fov_alignment_proven=fov_alignment_proven,
        geometry_transform_id=geometry_transform_id,
        misalignment_gap_threshold_ms=misalignment_gap_threshold_ms,
    )


def geometry_attribution_from_json(payload: str | None) -> GeometryAttribution | None:
    """Reconstruct a `GeometryAttribution` from its persisted
    `MediaAssetModel.geometry_attribution_json` form (or an equivalent
    already-decoded JSON string from any other caller). `None` for `None`,
    empty, or malformed input -- the honest "this evidence item predates
    this contract, or its producer never computed one" fact -- never a
    fabricated attribution. Mirrors the established `evaluation_governance`/
    `rescore_visit_truth.py` "reconstruct a frozen fact from already-recorded
    JSON, never guess a missing one" convention."""
    if not payload:
        return None
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return GeometryAttribution(
            geometry_source=data.get("geometry_source"),
            geometry_source_offset_ms=data.get("geometry_source_offset_ms"),
            geometry_source_observation_id=data.get("geometry_source_observation_id"),
            geometry_source_confidence=data.get("geometry_source_confidence"),
            same_frame=data.get("same_frame"),
            geometry_evidence_gap_ms=data.get("geometry_evidence_gap_ms"),
            # Source-Resolution + Multi-Frame Species Evidence v1: `.get(...)`
            # honestly returns `None` for any record persisted before these
            # fields existed -- never a guessed/backfilled value.
            fov_alignment_proven=data.get("fov_alignment_proven"),
            geometry_transform_id=data.get("geometry_transform_id"),
            resolution_provenance=data.get("resolution_provenance"),
        )
    except (ValueError, TypeError):
        return None


def classify_localization_attribution(
    attribution: GeometryAttribution | None,
    *,
    confidence_evidence: ConfidenceEvidenceSummary | None = None,
    misalignment_gap_threshold_ms: int = DEFAULT_MISALIGNMENT_GAP_THRESHOLD_MS,
) -> LocalizationAttributionResult:
    """Classify why a persisted candidate's own evidence geometry may not
    represent a visible subject, using only already-retained lineage facts
    -- never pixel content, never a species/animal-presence judgment (see
    "The truth boundary" in product-doctrine.md). Deterministic: identical
    inputs always produce an identical result.

    Decision order (most specific/decidable fact checked first; see
    "Attribution decision order" in docs/localization-attribution-contract.md):

    1. `insufficient_geometry_lineage` -- no lineage retained at all (a
       legacy record that predates this contract, or a caller that never
       computed one). Never guessed past this point.
    2. `evidence_geometry_misaligned` -- the evidence image is not provably
       the same moment as the geometry's own source observation, and the
       measured/derivable gap (when known) exceeds the bounded threshold, or
       the gap is unknown outright (an unproven alignment is never treated
       as proven). This is checked *before* asking what kind of observation
       supplied the geometry: if the image itself cannot be trusted to show
       the same moment, the kind of observation that produced the box is
       moot until that is resolved.
    3. `detector_hit_then_lost` -- the geometry is a stale, carried-forward
       box (no fresh observation established it), *and* this tracklet's own
       confidence evidence proves the detector had genuinely confirmed the
       subject earlier, before the geometry's own source moment.
    4. `tracker_drift` -- the geometry came from tracker-support (patch)
       matching, not a genuine detection, this exact moment.
    5. `detector_off_target` -- by elimination: the geometry is a genuine,
       temporally-aligned detector hit with no known intervening lineage
       artifact. If it still misses a visible subject, the raw detector
       output on that exact frame is the most defensible attribution
       available from lineage alone.
    6. `insufficient_geometry_lineage` -- defensive fallback (for example a
       carried-forward box with no confidence evidence to corroborate step 3
       against, or an unrecognized `geometry_source`).
    """
    if misalignment_gap_threshold_ms < 0:
        raise ValueError("invalid_misalignment_gap_threshold")

    if attribution is None or (
        attribution.geometry_source is None and attribution.geometry_source_offset_ms is None
    ):
        return LocalizationAttributionResult(
            "insufficient_geometry_lineage", "no_geometry_lineage_retained_for_this_record", None, None,
        )

    if attribution.same_frame is not True and (
        attribution.geometry_evidence_gap_ms is None
        or attribution.geometry_evidence_gap_ms > misalignment_gap_threshold_ms
    ):
        return LocalizationAttributionResult(
            "evidence_geometry_misaligned",
            "evidence_image_not_provably_aligned_with_geometry_source_moment",
            attribution.geometry_source,
            attribution.geometry_evidence_gap_ms,
        )

    if attribution.geometry_source == "carried_forward":
        if (
            confidence_evidence is not None
            and confidence_evidence.detection_count > 0
            and confidence_evidence.last_detection_offset_ms is not None
            and attribution.geometry_source_offset_ms is not None
            and attribution.geometry_source_offset_ms > confidence_evidence.last_detection_offset_ms
        ):
            return LocalizationAttributionResult(
                "detector_hit_then_lost",
                "detector_confirmed_earlier_then_geometry_coasted_past_last_detection",
                attribution.geometry_source,
                attribution.geometry_evidence_gap_ms,
            )
        return LocalizationAttributionResult(
            "insufficient_geometry_lineage",
            "carried_forward_geometry_without_confirmed_detection_history",
            attribution.geometry_source,
            attribution.geometry_evidence_gap_ms,
        )

    if attribution.geometry_source == "tracker":
        return LocalizationAttributionResult(
            "tracker_drift",
            "geometry_supplied_by_tracker_support_not_a_genuine_detection",
            attribution.geometry_source,
            attribution.geometry_evidence_gap_ms,
        )

    if attribution.geometry_source == "detector":
        return LocalizationAttributionResult(
            "detector_off_target",
            "temporally_aligned_genuine_detector_hit",
            attribution.geometry_source,
            attribution.geometry_evidence_gap_ms,
        )

    return LocalizationAttributionResult(
        "insufficient_geometry_lineage", "unrecognized_geometry_source", attribution.geometry_source,
        attribution.geometry_evidence_gap_ms,
    )
