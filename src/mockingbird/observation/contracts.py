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
    """A retained frame reference; providers never need to expose frame bytes here."""

    stream_id: str
    media_asset_id: str
    captured_at: datetime | None


@dataclass(frozen=True)
class DetectionObservation:
    """Untrusted detector evidence emitted by a future inference-capable provider."""

    detector_id: str
    label: str
    confidence: float | None
    captured_at: datetime


@dataclass(frozen=True)
class TrackUpdate:
    """Temporal-support evidence for a provider-neutral track generation."""

    track_id: str
    generation_id: str
    captured_at: datetime
    status: Literal["started", "updated", "ended"]


@dataclass(frozen=True)
class EvidenceCandidate:
    """A candidate media reference and its role, before durable product promotion."""

    media_asset_id: str
    stream_id: str
    role: str
    captured_at: datetime | None


@dataclass(frozen=True)
class VisitProposal:
    """An unpersisted proposal for existing Visit assembly to consider."""

    proposal_key: str
    source_id: str
    stream_id: str
    evidence_media_asset_ids: tuple[str, ...]
    reason: str


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
