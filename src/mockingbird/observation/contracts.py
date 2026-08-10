"""Stable facts exchanged by Observation Engine providers.

These contracts deliberately describe evidence and operational state only. They
do not expose adapter payloads, persist product objects, or carry reviewed truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Literal, Protocol, Sequence


@dataclass(frozen=True)
class FramePacket:
    """A bounded path/reference or transient payload with provider-neutral identity.

    `frame_id` is this packet's own identity in whatever space produced it --
    for a deterministic replay input that is a replay-local, input-fingerprint
    -derived identity (see `replay.ReplayInput.packets()`), never an absolute
    path. `source_capture_frame_id`/`source_content_hash` are separate,
    optional, additive provenance: when this packet was produced by replaying
    reviewed Stage 6.6/6.8 temporal-review capture data, they carry the
    *original* retained Camera Node frame's stable identity/content hash --
    the identity a human reviewer's annotation actually refers to -- so a
    consumer can join back to reviewed truth without ever needing
    `frame_id`/`media_asset_id` to double as that identity. Both stay `None`
    for a generic replay input with no reviewed-capture provenance, or for a
    pre-Stage-6.14 caller; see docs/reviewed-replay-lineage-contract.md.
    """

    stream_id: str
    media_asset_id: str
    captured_at: datetime | None
    frame_id: str | None = None
    source_offset_ms: int | None = None
    width: int | None = None
    height: int | None = None
    source_path: str | None = None
    analysis_excluded_regions: tuple[tuple[float, float, float, float], ...] = ()
    payload: bytes | None = None
    frame_sequence: int | None = None
    node_session_id: str | None = None
    source_monotonic_ns: int | None = None
    received_at: datetime | None = None
    provider_generation: str | None = None
    timing_facts: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    source_capture_frame_id: str | None = None
    source_content_hash: str | None = None


@dataclass(frozen=True)
class DetectionObservation:
    """Untrusted, provider-neutral detector evidence; never reviewed truth.

    `source_capture_frame_id` is the same optional, additive reviewed-
    provenance fact described on `FramePacket` -- the original captured
    frame this detection's own `frame_id` was replayed from, when known.
    """

    detector_id: str
    label: str
    confidence: float | None
    captured_at: datetime
    observation_id: str | None = None
    frame_id: str | None = None
    provider_id: str | None = None
    model_key: str | None = None
    generation_id: str | None = None
    bounding_box: tuple[float, float, float, float] | None = None
    class_source_label: str | None = None
    is_animal: bool | None = None
    source_capture_frame_id: str | None = None


@dataclass(frozen=True)
class DetectionEvidenceSample:
    """One bounded, retained per-detection fact behind a track/proposal's
    aggregate confidence accounting (Detection Quality Accounting v1 -- see
    docs/detection-quality-accounting-contract.md). Evidence, never
    observational authority: nothing downstream may treat one sample as a
    species/animal-presence decision by itself.

    `observation_id` is `DetectionObservation.observation_id` -- the exact
    source detection this sample was taken from, so a diagnostic can trace
    an aggregate stat back to one real detector output, never a
    reconstructed guess. A sample list may be a bounded, representative
    subset of every detection a track ever matched (see
    `ConfidenceEvidenceSummary.sample_truncated`); it is never fabricated
    for a detection that did not happen.
    """

    confidence: float
    source_offset_ms: int | None
    frame_id: str | None
    observation_id: str | None
    is_strong: bool


@dataclass(frozen=True)
class ConfidenceEvidenceSummary:
    """Model-neutral detector-confidence/evidence accounting for one track
    generation or assembled Visit proposal (Detection Quality Accounting v1
    -- see docs/detection-quality-accounting-contract.md).

    This is evidence, never truth or observational authority: an admission
    gate may *read* it, but nothing may treat it as a species/animal-
    presence decision by itself, and no downstream code may silently
    convert it into a reviewed outcome (see "The truth boundary" in
    product-doctrine.md).

    Every count is exact and authoritative (never truncated) unless noted.
    `None`/empty fields mean "not known/not applicable," never a fabricated
    zero or a fabricated absence of evidence -- a summary rebuilt from a
    legacy record that predates this contract (or from a track that
    genuinely saw no detections) reports the honestly-unavailable fields as
    `None`/empty rather than a reconstructed guess; `sample_truncated`
    disambiguates "we hold no per-detection sample even though detections
    happened" from "there were genuinely zero detections."
    """

    detection_count: int
    max_confidence: float | None
    mean_confidence: float | None
    median_confidence: float | None
    # `None` specifically when `samples` holds zero entries despite
    # `detection_count > 0` -- i.e. a legacy/reconstructed record that never
    # carried per-detection samples at all. Reporting `0` in that case would
    # read as "provably no strong detections," which is not known; `None`
    # is the honest "unknown," matching every other unavailable-evidence
    # field on this dataclass. A real (possibly sample-capped, still
    # partially informative) integer whenever at least one sample exists.
    strong_detection_count: int | None
    weak_detection_count: int | None
    # `None` under the same "no retained samples despite detection_count >
    # 0" legacy condition as `strong_detection_count` above -- a legacy
    # `TrackUpdate`'s own `max_consecutive_detector_confirmed_frames`
    # defaults to `0` (that field's own backward-compatible dataclass
    # default), which would otherwise misreport "provably never two in a
    # row" for a generation this contract simply never measured.
    max_consecutive_detector_confirmed_frames: int | None
    samples: tuple[DetectionEvidenceSample, ...]
    broad_class: str | None
    first_detection_offset_ms: int | None
    last_detection_offset_ms: int | None
    # True whenever `samples` is known not to hold every one of
    # `detection_count`'s underlying detections -- either the bounded
    # per-track sample cap was reached, or (a legacy/reconstructed record)
    # no per-detection samples were ever recorded at all. `False` only when
    # `samples` is provably the complete set (including the trivial
    # `detection_count == 0` case).
    sample_truncated: bool = False

    def __post_init__(self) -> None:
        if self.detection_count < 0:
            raise ValueError("invalid_confidence_evidence_summary")
        if self.strong_detection_count is not None and self.strong_detection_count < 0:
            raise ValueError("invalid_confidence_evidence_summary")
        if self.weak_detection_count is not None and self.weak_detection_count < 0:
            raise ValueError("invalid_confidence_evidence_summary")
        if (
            self.strong_detection_count is not None
            and self.weak_detection_count is not None
            and self.strong_detection_count + self.weak_detection_count > self.detection_count
        ):
            raise ValueError("invalid_confidence_evidence_summary")
        if self.max_consecutive_detector_confirmed_frames is not None and self.max_consecutive_detector_confirmed_frames < 0:
            raise ValueError("invalid_confidence_evidence_summary")


EMPTY_CONFIDENCE_EVIDENCE = ConfidenceEvidenceSummary(
    detection_count=0,
    max_confidence=None,
    mean_confidence=None,
    median_confidence=None,
    strong_detection_count=0,
    weak_detection_count=0,
    max_consecutive_detector_confirmed_frames=0,
    samples=(),
    broad_class=None,
    first_detection_offset_ms=None,
    last_detection_offset_ms=None,
    sample_truncated=False,
)


def merge_confidence_evidence(
    summaries: Sequence[ConfidenceEvidenceSummary],
) -> ConfidenceEvidenceSummary:
    """Combine one or more tracklets'/generations' own `ConfidenceEvidenceSummary`
    into one summary for an assembled multi-tracklet Visit proposal.

    Pure aggregation only -- never re-derives a fact from raw detections
    (there are none available at this layer). `max_consecutive_detector_
    confirmed_frames` takes the max across constituents rather than summing:
    a real gap between two merged tracklets is not "more consecutive
    support," and the merged proposal's own two-tracklet-adjacency evidence
    is already captured separately (see `AssembledVisitProposal.
    assembly_decisions`), not invented here as a longer streak.
    """

    if not summaries:
        return EMPTY_CONFIDENCE_EVIDENCE
    if len(summaries) == 1:
        return summaries[0]
    detection_count = sum(item.detection_count for item in summaries)
    # A sum is only honest when every constituent's own count is actually
    # known -- silently treating one constituent's unknown (`None`) count
    # as zero would fabricate part of the total. If any constituent lacks
    # it, the merged total is `None` too (see the `strong_detection_count`
    # docstring above).
    strong_count = (
        sum(item.strong_detection_count for item in summaries)
        if all(item.strong_detection_count is not None for item in summaries)
        else None
    )
    weak_count = (
        sum(item.weak_detection_count for item in summaries)
        if all(item.weak_detection_count is not None for item in summaries)
        else None
    )
    max_confidences = [item.max_confidence for item in summaries if item.max_confidence is not None]
    all_samples = tuple(
        sample for item in summaries for sample in item.samples
    )
    ordered_samples = tuple(sorted(
        all_samples,
        key=lambda sample: (
            sample.source_offset_ms if sample.source_offset_ms is not None else 2**63,
            sample.frame_id or "",
            sample.observation_id or "",
        ),
    ))
    sample_confidences = [sample.confidence for sample in ordered_samples]
    first_offsets = [item.first_detection_offset_ms for item in summaries if item.first_detection_offset_ms is not None]
    last_offsets = [item.last_detection_offset_ms for item in summaries if item.last_detection_offset_ms is not None]
    broad_classes = {item.broad_class for item in summaries if item.broad_class is not None}
    return ConfidenceEvidenceSummary(
        detection_count=detection_count,
        max_confidence=max(max_confidences) if max_confidences else None,
        mean_confidence=(sum(sample_confidences) / len(sample_confidences)) if sample_confidences else None,
        median_confidence=median(sample_confidences) if sample_confidences else None,
        strong_detection_count=strong_count,
        weak_detection_count=weak_count,
        # Same "any unknown constituent makes the merged fact unknown"
        # reasoning as `strong_count`/`weak_count` above: a known max drawn
        # only from the known constituents could silently understate the
        # truth if the unknown one was actually higher.
        max_consecutive_detector_confirmed_frames=(
            max(item.max_consecutive_detector_confirmed_frames for item in summaries)
            if all(item.max_consecutive_detector_confirmed_frames is not None for item in summaries)
            else None
        ),
        samples=ordered_samples,
        # A merged proposal's constituent tracklets are only ever compatible
        # (same `broad_class`) by construction (see `classify_boundary`'s
        # `broad_class_mismatch` structural check) -- a mismatch here would
        # indicate a caller bug upstream, not a fact worth guessing at.
        broad_class=next(iter(broad_classes)) if len(broad_classes) == 1 else None,
        first_detection_offset_ms=min(first_offsets) if first_offsets else None,
        last_detection_offset_ms=max(last_offsets) if last_offsets else None,
        sample_truncated=any(item.sample_truncated for item in summaries) or len(ordered_samples) < detection_count,
    )


@dataclass(frozen=True)
class TrackUpdate:
    """Temporal-support evidence for a provider-neutral track generation.

    `supporting_source_capture_frame_ids` mirrors `supporting_frame_ids` in
    the same optional, additive reviewed-provenance space `FramePacket`
    describes: the original captured frame identities behind every replay
    frame this track generation has genuinely observed so far, deduplicated
    independently of `supporting_frame_ids` (present only for the frames
    that actually carried known source lineage).

    `weak_detector_support_count`/`support_state` are Stage 6.16's bounded
    evidence-hierarchy provenance (see
    docs/sustained-visit-continuity-contract.md): a spatially coherent
    detector observation below `strong_detection_threshold` but at or above
    `weak_detector_support_floor` increments `weak_detector_support_count`
    instead of `detector_confirmation_count` and never by itself confirms a
    tentative track. `support_state` names what kind of evidence most
    recently refreshed this update (`strong_detector_supported`,
    `weak_detector_supported`, `tracker_supported`) or reuses the existing
    `temporarily_lost` lifecycle vocabulary when nothing did -- the same
    "reuse existing vocabulary rather than add a new externally-visible
    state" convention Stage 6.11 established for reconnect bridging.
    """

    track_id: str
    generation_id: str
    captured_at: datetime
    status: Literal["started", "updated", "ended"]
    lifecycle_state: Literal[
        "tentative", "confirmed", "temporarily_lost", "ended", "rejected"
    ] = "tentative"
    frame_id: str | None = None
    source_offset_ms: int | None = None
    broad_class: str | None = None
    bounding_box: tuple[float, float, float, float] | None = None
    supporting_frame_ids: tuple[str, ...] = ()
    detector_confirmation_count: int = 0
    tracker_support_count: int = 0
    confidence: float | None = None
    detector_provenance: str | None = None
    tracker_provenance: str | None = None
    terminal_reason: str | None = None
    supporting_source_capture_frame_ids: tuple[str, ...] = ()
    weak_detector_support_count: int = 0
    support_state: Literal[
        "strong_detector_supported", "weak_detector_supported", "tracker_supported", "temporarily_lost",
    ] = "temporarily_lost"
    # Stage 6.19 (see docs/tracklet-visit-assembly-contract.md): two small,
    # additive, already-known-internally facts the tracker itself never
    # exposed, needed by the shadow `VisitEpisodeAssembler` to summarize a
    # *finalized* tracklet honestly without redesigning tracker association
    # or confirmation. Both default to their pre-Stage-6.19 implicit value,
    # so every existing positional/keyword `TrackUpdate(...)` call site (in
    # this module's own tests and every other provider) remains valid
    # unchanged. `detector_ran` mirrors `ProviderNeutralFrameTracker.observe`'s
    # own already-existing `detector_ran` parameter -- whether the detector
    # actually evaluated the frame this update was produced for, independent
    # of whether it matched *this* track -- so a consumer can finally tell a
    # genuine detector-negative frame (`support_state="temporarily_lost"` and
    # `detector_ran=True`) apart from an idle-cadence frame the detector
    # never inspected at all (`detector_ran=False`); see the assembly
    # contract's "skipped gaps are not negative evidence" rule. `ambiguous_
    # start` mirrors the track's own already-computed `_is_ambiguous_reentry`
    # result at the moment its generation began -- true when this generation
    # started plausibly-but-not-confidently continuing a recently-ended one
    # -- carried onto every update of the generation (not just the `started`
    # one) so a consumer inspecting only a generation's *terminal* update
    # still sees it.
    detector_ran: bool = False
    ambiguous_start: bool = False
    # Detection Quality Accounting v1 (see
    # docs/detection-quality-accounting-contract.md): a bounded, cumulative-
    # so-far list of this generation's own genuine matched-detection
    # confidence samples, mirroring how `supporting_frame_ids` is already
    # cumulative-so-far across a generation's updates. Defaulted so every
    # pre-existing positional/keyword `TrackUpdate(...)` call site (this
    # module's own tests, every provider, and every acceptance-tooling JSON
    # reconstruction such as `rescore_visit_truth.py`) remains valid
    # unchanged -- a reconstructed legacy `TrackUpdate` simply has no
    # samples, which is the honest "no fabricated confidence for legacy
    # records" outcome, not an error.
    confidence_samples: tuple[DetectionEvidenceSample, ...] = ()
    # Running max (this generation's lifetime so far) of consecutive frames
    # where the detector itself matched this track -- mirrors `detector_
    # confirmation_count` (a total) the same way `consecutive_negative_
    # detector_frames` mirrors it as a streak. Never itself a confirmation
    # bar; purely descriptive provenance for quality accounting / shadow
    # admission-policy evaluation (see `mockingbird.observation.
    # admission_policy`).
    max_consecutive_detector_confirmed_frames: int = 0


@dataclass(frozen=True)
class EvidenceCandidate:
    """A candidate media reference and its role, before durable product promotion.

    `source_capture_frame_id`/`source_content_hash` are the same optional,
    additive reviewed-provenance facts described on `FramePacket`: the
    original captured frame this candidate's own `frame_id`/`media_asset_id`
    were replayed from, when known. They never replace `frame_id` (which
    remains this candidate's own replay/source identity) -- they are the
    explicit bridge a truth-joining consumer (for example the evidence
    benchmark) uses instead of assuming `frame_id` doubles as reviewed truth's
    identity.
    """

    media_asset_id: str
    stream_id: str
    role: str
    captured_at: datetime | None
    frame_id: str | None = None
    source_offset_ms: int | None = None
    width: int | None = None
    height: int | None = None
    subject_geometry: tuple[float, float, float, float] | None = None
    track_generation_id: str | None = None
    detector_provenance: str | None = None
    tracker_provenance: str | None = None
    quality_facts: tuple[tuple[str, float | int | bool | str | None], ...] = ()
    temporary: bool = True
    shadow_only: bool = True
    source_capture_frame_id: str | None = None
    source_content_hash: str | None = None


@dataclass(frozen=True)
class VisitProposal:
    """An unpersisted proposal for existing Visit assembly to consider.

    `supporting_source_capture_frame_ids` mirrors `supporting_frame_ids` in
    the same optional, additive reviewed-provenance space `TrackUpdate`
    describes -- the original captured frame identities supporting this
    proposal, when known.
    """

    proposal_key: str
    source_id: str
    stream_id: str
    evidence_media_asset_ids: tuple[str, ...]
    reason: str
    start_offset_ms: int | None = None
    end_offset_ms: int | None = None
    zone_id: str | None = None
    shadow_only: bool = True
    idempotency_key: str | None = None
    broad_subject_class: str | None = None
    track_generation_id: str | None = None
    detector_provenance: str | None = None
    tracker_provenance: str | None = None
    supporting_frame_ids: tuple[str, ...] = ()
    terminal_reason: str | None = None
    provider_key: str | None = None
    provider_version: str | None = None
    supporting_source_capture_frame_ids: tuple[str, ...] = ()
    # Detection Quality Accounting v1: the aggregate detector-confidence/
    # evidence accounting behind this proposal's constituent track
    # generation(s) -- see `ConfidenceEvidenceSummary` and
    # docs/detection-quality-accounting-contract.md. `None` for a proposal
    # built before this field existed, or by a caller that never populated
    # it -- never a fabricated summary. This is evidence a quality-
    # accounting pass or a *shadow* admission-policy evaluator may read; the
    # production `candidate_visit_authority`/`candidate_quality_gate` gates
    # remain unchanged by this field's mere presence (see "Production
    # authority gate" in docs/detection-quality-accounting-contract.md).
    confidence_evidence: ConfidenceEvidenceSummary | None = None


@dataclass(frozen=True)
class ObservationResult:
    """One provider result containing evidence facts, never product truth."""

    provider_id: str
    source_id: str
    stream_id: str
    observed_at: datetime | None
    frame_packets: tuple[FramePacket, ...] = ()
    detection_observations: tuple[DetectionObservation, ...] = ()
    track_updates: tuple[TrackUpdate, ...] = ()
    evidence_candidates: tuple[EvidenceCandidate, ...] = ()
    visit_proposals: tuple[VisitProposal, ...] = ()
    creates_truth: bool = False


@dataclass(frozen=True)
class ObservationProviderCapabilities:
    """Honest capability declaration; unsupported facts remain false."""

    timer_driven: bool
    emits_frame_packets: bool
    emits_detection_observations: bool
    emits_track_updates: bool
    emits_evidence_candidates: bool
    emits_visit_proposals: bool
    deterministic_replay: bool = False
    frame_driven: bool = False
    cuda_detector: bool = False
    tracking: bool = False
    shadow_visit_proposals: bool = False
    production_proposal_authority: bool = False
    continuous_live_stream_input: bool = False
    camera_node_analysis_stream: bool = False
    rolling_live_encoded_buffer: bool = False
    high_resolution_burst: bool = False
    species_interpretation: bool = False


@dataclass(frozen=True)
class ObservationProviderHealth:
    """Bounded operational health that does not probe or start a provider."""

    state: Literal["idle", "running", "stopped", "degraded"]
    healthy: bool
    message: str
    observed_at: datetime | None = None


@dataclass(frozen=True)
class ObservationProviderDescriptor:
    provider_id: str
    display_name: str
    capabilities: ObservationProviderCapabilities
    health: ObservationProviderHealth


@dataclass(frozen=True)
class ObservationEngineStatus:
    active_provider_id: str
    provider: ObservationProviderDescriptor
    creates_truth: bool = False


class ObservationProvider(Protocol):
    """Small provider boundary for snapshot, replay, or accelerated implementations."""

    @property
    def provider_id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def capabilities(self) -> ObservationProviderCapabilities: ...

    async def health(self, *, stream_id: str | None = None) -> ObservationProviderHealth: ...

    async def describe(
        self,
        *,
        stream_id: str | None = None,
    ) -> ObservationProviderDescriptor: ...
