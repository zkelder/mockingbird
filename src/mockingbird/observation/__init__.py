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
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.registry import ObservationEngineRegistry
from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

__all__ = [
    "DetectionObservation",
    "EvidenceCandidate",
    "FramePacket",
    "ObservationEngineRegistry",
    "ObservationEngineStatus",
    "ObservationProviderCapabilities",
    "ObservationProviderDescriptor",
    "ObservationProviderHealth",
    "ObservationProvider",
    "ObservationResult",
    "OnnxCudaObservationProvider",
    "OnnxModelBundle",
    "SnapshotObservationProvider",
    "TrackUpdate",
    "VisitProposal",
]
