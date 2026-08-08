"""Stable facts exchanged by Observation Engine providers.

These contracts deliberately describe evidence and operational state only. They
do not expose adapter payloads, persist product objects, or carry reviewed truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


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
