from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import replace

import pytest

from mockingbird.observation.contracts import (
    DetectionEvidenceSample,
    DetectionObservation,
    FramePacket,
    TrackUpdate,
)
from mockingbird.observation.temporal_capture import (
    RetainedFrameRecord,
    TemporalCaptureError,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
)
from mockingbird.observation.exact_frame_capture import (
    ExactFrameCaptureError,
    build_exact_analysis_frame,
)


def _frame() -> FramePacket:
    return FramePacket(
        stream_id="stream-1",
        media_asset_id="temporary:frame-1",
        captured_at=datetime(2026, 8, 11, tzinfo=UTC),
        frame_id="frame-1",
        source_offset_ms=1200,
        width=640,
        height=360,
        payload=b"exact-detector-input",
    )


def _detection() -> DetectionObservation:
    return DetectionObservation(
        detector_id="mdv5",
        label="animal",
        confidence=0.42,
        captured_at=datetime(2026, 8, 11, tzinfo=UTC),
        observation_id="observation-1",
        frame_id="frame-1",
        provider_id="frame-driven-onnx-cuda",
        model_key="mdv5-onnx",
        generation_id="generation-1",
        bounding_box=(0.1, 0.2, 0.3, 0.4),
        class_source_label="1",
        is_animal=True,
    )


def _track() -> TrackUpdate:
    return TrackUpdate(
        track_id="track-1",
        generation_id="generation-1",
        captured_at=datetime(2026, 8, 11, tzinfo=UTC),
        status="updated",
        lifecycle_state="confirmed",
        frame_id="frame-1",
        source_offset_ms=1200,
        broad_class="animal",
        bounding_box=(0.1, 0.2, 0.3, 0.4),
        detector_confirmation_count=2,
        confidence=0.42,
        support_state="strong_detector_supported",
        confidence_samples=(
            DetectionEvidenceSample(
                confidence=0.42,
                source_offset_ms=1200,
                frame_id="frame-1",
                observation_id="observation-1",
                is_strong=True,
                bounding_box=(0.1, 0.2, 0.3, 0.4),
            ),
        ),
        bounding_box_source_offset_ms=1200,
    )


def test_exact_frame_envelope_binds_bytes_outputs_provenance_and_lineage() -> None:
    envelope = build_exact_analysis_frame(
        _frame(),
        (_detection(),),
        (_track(),),
        model_fingerprint="model-fingerprint",
        provider_id="frame-driven-onnx-cuda",
        capture_score_threshold=0.02,
    ).to_semantic_dict()

    assert envelope["detector_input"]["sha256"] == (
        "e2071dd4f0c6df6f475d60668e9127967d6cfa2a87a555ec713d213746be2c83"
    )
    assert envelope["detector_input"]["relative_payload"] == "frames/frame-1.jpg"
    assert (
        envelope["raw_provider_detector_outputs"][0]["observation_id"]
        == "observation-1"
    )
    assert envelope["normalized_detections"][0]["normalized_xyxy"] == (
        0.1,
        0.2,
        0.3,
        0.4,
    )
    attribution = envelope["geometry_attributions"][0]["attribution"]
    assert attribution["geometry_source"] == "detector"
    assert attribution["same_frame"] is True
    assert envelope["counterfactual_lineage"]["track_generation_ids"] == (
        "generation-1",
    )
    assert envelope["model_provenance"]["capture_score_threshold"] == 0.02
    assert envelope["authority"] == "diagnostic_evidence_only"
    assert envelope["creates_truth"] is False
    assert envelope["creates_product_record"] is False


def test_exact_frame_capture_requires_actual_payload_and_dimensions() -> None:
    with pytest.raises(
        ExactFrameCaptureError, match="exact_detector_input_unavailable"
    ):
        build_exact_analysis_frame(
            FramePacket("stream", "temporary", None, frame_id="frame", payload=None),
            (),
            (),
            model_fingerprint="model",
            provider_id="provider",
            capture_score_threshold=0.02,
        )


def test_exact_frame_capture_is_bounded_and_reports_truncation() -> None:
    detections = tuple(_detection() for _ in range(51))
    updates = tuple(_track() for _ in range(65))
    envelope = build_exact_analysis_frame(
        _frame(),
        detections,
        updates,
        model_fingerprint="model",
        provider_id="provider",
        capture_score_threshold=0.02,
    )

    assert len(envelope.raw_provider_detector_outputs) == 50
    assert len(envelope.geometry_attributions) == 64
    assert envelope.detector_outputs_truncated is True
    assert envelope.track_updates_truncated is True


def test_temporal_capture_record_binds_exact_envelope_to_persisted_jpeg() -> None:
    envelope = build_exact_analysis_frame(
        _frame(),
        (_detection(),),
        (_track(),),
        model_fingerprint="model-fingerprint",
        provider_id="provider",
        capture_score_threshold=0.02,
    ).to_semantic_dict()
    record = RetainedFrameRecord(
        frame_id="frame-1",
        sequence=1,
        source_offset_ms=1200,
        provider_generation="provider-generation",
        content_hash=envelope["detector_input"]["sha256"],
        byte_size=envelope["detector_input"]["byte_size"],
        trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=1,
        animal_detection_count=1,
        max_animal_score=0.42,
        active_track_count=1,
        motion_proposal_count=0,
        exact_analysis=envelope,
    )
    assert record.exact_analysis == envelope

    with pytest.raises(TemporalCaptureError, match="invalid_exact_analysis_envelope"):
        replace(record, content_hash="0" * 64)


def test_exact_capture_cli_flag_is_explicit_and_default_off() -> None:
    from mockingbird.observation.temporal_capture_cli import _capture_parser

    required = [
        "--camera-node-config",
        "camera.json",
        "--provider",
        "frame-driven-onnx-cuda",
        "--provider-config",
        "provider.json",
        "--output",
        "capture",
        "--scene-id",
        "scene-01",
    ]
    assert _capture_parser().parse_args(required).retain_exact_analysis is False
    assert (
        _capture_parser()
        .parse_args([*required, "--retain-exact-analysis"])
        .retain_exact_analysis
        is True
    )
