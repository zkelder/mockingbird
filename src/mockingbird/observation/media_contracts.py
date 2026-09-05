"""Provider-neutral bounded media contracts for live shadow observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


Availability = Literal["available", "unavailable", "degraded"]
TimingConfidence = Literal["supported", "uncertain", "unavailable"]


@dataclass(frozen=True)
class AnalysisStreamCapability:
    transport_key: str
    stream_mode: str
    content_type: str
    width: int
    height: int
    nominal_fps: float
    maximum_fps: float
    sequence_supported: bool
    capture_timestamp_supported: bool
    monotonic_timestamp_supported: bool
    timestamp_precision: str
    hardware_encoding_available: bool
    simultaneous_evidence_capture: str
    availability: Availability
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.transport_key
            or self.stream_mode not in {"continuous", "bounded_continuous"}
            or self.content_type not in {"image/jpeg", "image/png"}
            or not 1 <= self.width <= 16_000
            or not 1 <= self.height <= 12_000
            or self.nominal_fps <= 0
            or self.maximum_fps < self.nominal_fps
            or len(self.limitations) > 12
        ):
            raise ValueError("invalid_analysis_stream_capability")


@dataclass(frozen=True)
class AnalysisFrameEnvelope:
    stream_id: str
    node_session_id: str
    sequence: int
    frame_id: str
    captured_at: datetime
    source_monotonic_ns: int | None
    width: int
    height: int
    content_type: str
    provider_generation: str
    payload: bytes
    content_hash: str
    timing_facts: tuple[tuple[str, str | int | float | bool | None], ...] = ()
    # Boot Identity + Autonomous Recovery v1: optional, read from the same
    # per-part analysis-stream headers a Node already sends (see
    # `mockingbird_node.app.analysis_parts`). `None` for an older Node that
    # predates this field -- never required, never fabricated. Lets a
    # currently-observing session learn the Node's boot identity from
    # frames it already pulls, with no extra request. See "Boot identity"
    # in docs/camera-node-installer-design.md.
    node_boot_id: str | None = None
    node_service_version: str | None = None

    def __post_init__(self) -> None:
        if not self.stream_id or not self.node_session_id or not self.frame_id:
            raise ValueError("analysis_frame_identity")
        if self.sequence < 0 or not self.provider_generation:
            raise ValueError("analysis_frame_sequence")
        if self.captured_at.tzinfo is None:
            raise ValueError("analysis_frame_timestamp")
        if self.source_monotonic_ns is not None and self.source_monotonic_ns < 0:
            raise ValueError("analysis_frame_timestamp")
        if not 1 <= self.width <= 16_000 or not 1 <= self.height <= 12_000:
            raise ValueError("analysis_frame_dimensions")
        if self.content_type not in {"image/jpeg", "image/png"}:
            raise ValueError("analysis_frame_content")
        if not self.payload:
            raise ValueError("analysis_frame_content")
        if len(self.content_hash) != 64:
            raise ValueError("analysis_frame_hash")


@dataclass(frozen=True)
class EvidenceBurstCapability:
    availability: Availability
    available_profiles: tuple[str, ...]
    maximum_frames_per_burst: int
    minimum_interval_ms: int
    expected_latency_ms: tuple[int, int] | None
    analysis_continues: str
    exposure_may_change: bool
    focus_may_change: bool
    source_provenance_supported: bool
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not 1 <= self.maximum_frames_per_burst <= 8
            or self.minimum_interval_ms < 0
            or len(self.available_profiles) > 12
            or len(self.limitations) > 12
        ):
            raise ValueError("invalid_evidence_burst_capability")
        if self.expected_latency_ms is not None and (
            self.expected_latency_ms[0] < 0
            or self.expected_latency_ms[1] < self.expected_latency_ms[0]
        ):
            raise ValueError("invalid_evidence_burst_capability")


@dataclass(frozen=True)
class EvidenceBurstRequest:
    request_id: str
    stream_id: str
    node_session_id: str
    track_generation_id: str
    trigger_frame_id: str
    trigger_captured_at: datetime
    requested_frame_count: int
    requested_profile_id: str
    cadence_ms: int
    subject_geometry: tuple[float, float, float, float] | None
    zone_id: str | None
    deadline_at: datetime
    shadow_only: bool = True

    def __post_init__(self) -> None:
        if not all((self.request_id, self.stream_id, self.node_session_id, self.track_generation_id, self.trigger_frame_id, self.requested_profile_id)):
            raise ValueError("invalid_evidence_burst_request")
        if self.requested_frame_count != 1 or self.cadence_ms < 0 or not self.shadow_only:
            raise ValueError("invalid_evidence_burst_request")
        if self.trigger_captured_at.tzinfo is None or self.deadline_at.tzinfo is None:
            raise ValueError("invalid_evidence_burst_request")
        if self.deadline_at < self.trigger_captured_at:
            raise ValueError("invalid_evidence_burst_request")
        if self.subject_geometry is not None and not _valid_box(self.subject_geometry):
            raise ValueError("invalid_evidence_burst_request")


@dataclass(frozen=True)
class EvidenceBurstFrame:
    sequence: int
    captured_at: datetime
    width: int
    height: int
    content_type: str
    content_hash: str
    payload: bytes
    parent_frame_id: str
    provider_generation: str
    request_to_capture_ms: int | None
    temporal_alignment: TimingConfidence


@dataclass(frozen=True)
class EvidenceBurstResult:
    request_id: str
    status: Literal["captured", "failed", "stale"]
    frames: tuple[EvidenceBurstFrame, ...] = ()
    failure_code: str | None = None
    temporary: bool = True
    shadow_only: bool = True
    # Camera Node Evidence-Capture Profile Validity & Failure Observability
    # Correctness v1 (see docs/camera-node-evidence-capture-profile-validity
    # -failure-observability-correctness-v1-report.md). `failure_class` is a
    # bounded, safe transport-level sub-classification (never raw host/port/
    # exception text) of a `failure_code` such as `evidence_burst_unavailable`
    # -- mirrors `CameraNodeClientError.failure_class`'s own established
    # additive-diagnostic-only pattern; never used for control flow.
    # `reconciled_profile_id` is set only when a stale, no-longer-advertised
    # `evidence_profile_id` was deterministically reconciled to a live
    # replacement during this exact call (see `CameraNodeHttpTransport.
    # request_evidence_burst`); a caller (`LiveCameraNodeShadowSession`)
    # uses it to keep its own copy of the profile id in sync, regardless of
    # whether the retried attempt itself then succeeded.
    failure_class: str | None = None
    reconciled_profile_id: str | None = None

    def __post_init__(self) -> None:
        if not self.request_id or len(self.frames) > 8 or not self.temporary or not self.shadow_only:
            raise ValueError("invalid_evidence_burst_result")
        if self.status == "captured" and not self.frames:
            raise ValueError("invalid_evidence_burst_result")
        if self.status != "captured" and self.frames:
            raise ValueError("invalid_evidence_burst_result")
        if self.failure_code is not None and (
            len(self.failure_code) > 80
            or not self.failure_code.replace("_", "").isalnum()
        ):
            raise ValueError("invalid_evidence_burst_result")
        if self.failure_class is not None and (
            len(self.failure_class) > 40
            or not self.failure_class.replace("_", "").isalnum()
        ):
            raise ValueError("invalid_evidence_burst_result")
        if self.reconciled_profile_id is not None and (
            not self.reconciled_profile_id
            or len(self.reconciled_profile_id) > 120
            or "/" in self.reconciled_profile_id
        ):
            raise ValueError("invalid_evidence_burst_result")


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(0.0 <= value <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )
