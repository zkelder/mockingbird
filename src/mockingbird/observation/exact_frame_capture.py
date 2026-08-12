"""Bounded exact-analysis-frame diagnostic envelope.

This module records facts already present at the frame-driven provider
boundary. It does not rerun detection, infer truth, or create a product
record. The caller remains responsible for persisting the exact payload
bytes and enforcing the temporal-capture resource bounds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Any, Sequence

from mockingbird.observation.contracts import (
    DetectionObservation,
    FramePacket,
    TrackUpdate,
)
from mockingbird.observation.counterfactual_lineage import (
    COUNTERFACTUAL_LINEAGE_VERSION,
)
from mockingbird.observation.localization_attribution import (
    LOCALIZATION_ATTRIBUTION_VERSION,
    geometry_attribution_for_update,
)

EXACT_FRAME_CAPTURE_VERSION = "exact-analysis-frame-capture-v1"
MAX_EXACT_DETECTOR_OUTPUTS = 50
MAX_EXACT_TRACK_UPDATES = 64


class ExactFrameCaptureError(ValueError):
    """A fail-closed exact-frame envelope validation error."""


@dataclass(frozen=True)
class ExactModelProvenance:
    model_fingerprint: str
    provider_id: str
    capture_score_threshold: float

    def __post_init__(self) -> None:
        if (
            not self.model_fingerprint
            or not self.provider_id
            or not 0.0 <= self.capture_score_threshold <= 1.0
        ):
            raise ExactFrameCaptureError("invalid_exact_model_provenance")


@dataclass(frozen=True)
class ExactAnalysisFrame:
    """One local, non-authoritative frame plus its already-emitted lineage."""

    frame_id: str
    detector_input_sha256: str
    detector_input_byte_size: int
    detector_input_width: int
    detector_input_height: int
    model_provenance: ExactModelProvenance
    raw_provider_detector_outputs: tuple[dict[str, Any], ...]
    normalized_detections: tuple[dict[str, Any], ...]
    geometry_attributions: tuple[dict[str, Any], ...]
    counterfactual_lineage: dict[str, Any]
    detector_outputs_truncated: bool = False
    track_updates_truncated: bool = False

    def __post_init__(self) -> None:
        if (
            not self.frame_id
            or len(self.detector_input_sha256) != 64
            or self.detector_input_byte_size < 1
            or self.detector_input_width < 1
            or self.detector_input_height < 1
            or len(self.raw_provider_detector_outputs) > MAX_EXACT_DETECTOR_OUTPUTS
            or len(self.geometry_attributions) > MAX_EXACT_TRACK_UPDATES
        ):
            raise ExactFrameCaptureError("invalid_exact_analysis_frame")

    def to_semantic_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "capture_version": EXACT_FRAME_CAPTURE_VERSION,
            "frame_id": self.frame_id,
            "detector_input": {
                "relative_payload": f"frames/{self.frame_id}.jpg",
                "sha256": self.detector_input_sha256,
                "byte_size": self.detector_input_byte_size,
                "width": self.detector_input_width,
                "height": self.detector_input_height,
            },
            "model_provenance": asdict(self.model_provenance),
            "raw_provider_detector_outputs": list(self.raw_provider_detector_outputs),
            "normalized_detections": list(self.normalized_detections),
            "geometry_attributions": list(self.geometry_attributions),
            "counterfactual_lineage": self.counterfactual_lineage,
            "detector_outputs_truncated": self.detector_outputs_truncated,
            "track_updates_truncated": self.track_updates_truncated,
            "creates_truth": False,
            "creates_product_record": False,
            "authority": "diagnostic_evidence_only",
            "limitation": (
                "raw_provider_detector_outputs are provider-neutral outputs retained at the "
                "explicit review capture threshold, not pre-threshold model logits"
            ),
        }


def build_exact_analysis_frame(
    frame: FramePacket,
    observations: Sequence[DetectionObservation],
    track_updates: Sequence[TrackUpdate],
    *,
    model_fingerprint: str,
    provider_id: str,
    capture_score_threshold: float,
) -> ExactAnalysisFrame:
    """Build a bounded envelope without interpreting any detector evidence."""

    if (
        frame.frame_id is None
        or frame.payload is None
        or frame.width is None
        or frame.height is None
    ):
        raise ExactFrameCaptureError("exact_detector_input_unavailable")
    retained_observations = tuple(observations[:MAX_EXACT_DETECTOR_OUTPUTS])
    retained_updates = tuple(track_updates[:MAX_EXACT_TRACK_UPDATES])
    raw_outputs = tuple(
        {
            "observation_id": item.observation_id,
            "detector_id": item.detector_id,
            "provider_id": item.provider_id,
            "model_key": item.model_key,
            "generation_id": item.generation_id,
            "frame_id": item.frame_id,
            "source_capture_frame_id": item.source_capture_frame_id,
            "captured_at": item.captured_at.isoformat(),
            "label": item.label,
            "class_source_label": item.class_source_label,
            "confidence": item.confidence,
            "is_animal": item.is_animal,
            "bounding_box": item.bounding_box,
        }
        for item in retained_observations
    )
    normalized = tuple(
        {
            "observation_id": item.observation_id,
            "label": item.label,
            "confidence": item.confidence,
            "is_animal": item.is_animal,
            "normalized_xyxy": item.bounding_box,
        }
        for item in retained_observations
        if item.bounding_box is not None
    )
    geometry = tuple(
        {
            "track_id": update.track_id,
            "generation_id": update.generation_id,
            "frame_id": update.frame_id,
            "bounding_box": update.bounding_box,
            "attribution": asdict(
                geometry_attribution_for_update(
                    update,
                    same_frame=(update.frame_id == frame.frame_id),
                    evidence_source_offset_ms=frame.source_offset_ms,
                )
            ),
        }
        for update in retained_updates
        if update.bounding_box is not None
    )
    observation_ids = tuple(
        dict.fromkeys(
            item.observation_id
            for item in retained_observations
            if item.observation_id is not None
        )
    )
    generation_ids = tuple(
        dict.fromkeys(update.generation_id for update in retained_updates)
    )
    return ExactAnalysisFrame(
        frame_id=frame.frame_id,
        detector_input_sha256=sha256(frame.payload).hexdigest(),
        detector_input_byte_size=len(frame.payload),
        detector_input_width=frame.width,
        detector_input_height=frame.height,
        model_provenance=ExactModelProvenance(
            model_fingerprint=model_fingerprint,
            provider_id=provider_id,
            capture_score_threshold=capture_score_threshold,
        ),
        raw_provider_detector_outputs=raw_outputs,
        normalized_detections=normalized,
        geometry_attributions=geometry,
        counterfactual_lineage={
            "version": COUNTERFACTUAL_LINEAGE_VERSION,
            "localization_attribution_version": LOCALIZATION_ATTRIBUTION_VERSION,
            "source_frame_id": frame.frame_id,
            "observation_ids": observation_ids,
            "track_generation_ids": generation_ids,
            "proposal_outcome_ids": (),
            "coverage": "frame_and_emitted_track_updates_only",
        },
        detector_outputs_truncated=len(observations) > len(retained_observations),
        track_updates_truncated=len(track_updates) > len(retained_updates),
    )


__all__ = [
    "EXACT_FRAME_CAPTURE_VERSION",
    "MAX_EXACT_DETECTOR_OUTPUTS",
    "MAX_EXACT_TRACK_UPDATES",
    "ExactAnalysisFrame",
    "ExactFrameCaptureError",
    "ExactModelProvenance",
    "build_exact_analysis_frame",
]
