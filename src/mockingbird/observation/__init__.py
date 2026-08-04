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
from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    CameraNodeHttpTransport,
    LiveCameraNodeShadowSession,
    LiveShadowStatus,
)
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    AnalysisStreamCapability,
    EvidenceBurstCapability,
    EvidenceBurstRequest,
    EvidenceBurstResult,
)
from mockingbird.observation.registry import ObservationEngineRegistry
from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

__all__ = [
    "AnalysisFrameEnvelope",
    "AnalysisStreamCapability",
    "CameraNodeAnalysisSource",
    "CameraNodeHttpTransport",
    "DetectionObservation",
    "EvidenceBurstCapability",
    "EvidenceBurstRequest",
    "EvidenceBurstResult",
    "EvidenceCandidate",
    "FrameDrivenObservationProvider",
    "FrameDrivenProviderConfiguration",
    "FrameDrivenSettings",
    "FramePacket",
    "ObservationEngineRegistry",
    "LiveCameraNodeShadowSession",
    "LiveShadowStatus",
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
