"""Provider-neutral, evidence-only Observation Engine contracts."""

from mockingbird.observation.contracts import (
    DetectionObservation,
    EvidenceCandidate,
    FramePacket,
    ObservationEngineStatus,
    ObservationProviderCapabilities,
    ObservationProviderDescriptor,
    ObservationProviderHealth,
    ObservationProvider,
    ObservationResult,
    TrackUpdate,
    VisitProposal,
)
from mockingbird.observation.frame_driven_provider import (
    FrameDrivenObservationProvider,
    FrameDrivenProviderConfiguration,
    FrameDrivenSettings,
)
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker, TrackerConfiguration
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.registry import ObservationEngineRegistry
from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

__all__ = [
    "DetectionObservation",
    "EvidenceCandidate",
    "FrameDrivenObservationProvider",
    "FrameDrivenProviderConfiguration",
    "FrameDrivenSettings",
    "FramePacket",
    "ObservationEngineRegistry",
    "ObservationEngineStatus",
    "ObservationProviderCapabilities",
    "ObservationProviderDescriptor",
    "ObservationProviderHealth",
    "ObservationProvider",
    "ObservationResult",
    "OnnxCudaObservationProvider",
    "ProviderNeutralFrameTracker",
    "OnnxModelBundle",
    "SnapshotObservationProvider",
    "TrackUpdate",
    "TrackerConfiguration",
    "VisitProposal",
]
