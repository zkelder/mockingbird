from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation.onnx_provider import (
    DECODER_KEY,
    MDV5_DECODER_KEY,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
    _Transform,
    _decode,
    _percentile,
)
from mockingbird.observation.replay import ReplayValidationError


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _bundle(tmp_path: Path, **updates: object) -> OnnxModelBundle:
    values: dict[str, object] = {
        "schema_version": 1,
        "model_key": "md-v5a",
        "model_version": "0.1",
        "model_path": tmp_path / "model.onnx",
        "model_fingerprint": "a" * 64,
        "model_format": "ONNX",
        "license_name": "MIT",
        "redistribution": "local activation",
        "input_name": "images",
        "input_width": 100,
        "input_height": 100,
        "input_dtype": "float32",
        "input_scale": 1 / 255,
        "channel_order": "NCHW",
        "color_format": "RGB",
        "letterbox_fill": (114, 114, 114),
        "normalization_mean": (0.0, 0.0, 0.0),
        "normalization_std": (1.0, 1.0, 1.0),
        "resize_mode": "letterbox",
        "output_names": ("predictions",),
        "decoder_key": MDV5_DECODER_KEY,
        "broad_classes": ("animal", "person", "vehicle"),
        "animal_classes": ("animal",),
        "taxonomy": "MegaDetector v5 broad classes",
        "provenance": "synthetic raw tensor",
        "provider_compatibility": ("onnx-cuda",),
        "limitations": ("test fixture",),
        "score_threshold": 0.25,
        "max_observations_per_frame": 300,
        "nms_iou_threshold": 0.45,
        "nms_max_detections": 300,
        "max_decode_candidates": 102_000,
        "raw_output_shape": None,
    }
    values.update(updates)
    return OnnxModelBundle(**values)


def _frame(tmp_path: Path) -> FramePacket:
    path = tmp_path / "frame.png"
    Image.new("RGB", (200, 100), color="white").save(path)
    return FramePacket(
        "stream",
        "replay:0",
        datetime(2026, 8, 3, tzinfo=UTC),
        "frame-0",
        0,
        200,
        100,
        str(path),
    )


def _transform() -> _Transform:
    return _Transform(0.5, 0.5, 0, 25, 200, 100)


def _raw(*rows: list[float]) -> list[np.ndarray]:
    return [np.asarray([rows], dtype=np.float32)]


def test_md_v5_raw_confidence_mapping_nms_order_and_letterbox_reversal(tmp_path: Path) -> None:
    output = _raw(
        [50, 50, 80, 40, 0.9, 0.8, 0.1, 0.1],
        [50, 50, 78, 38, 0.8, 0.7, 0.1, 0.1],
        [20, 40, 10, 10, 0.9, 0.1, 0.9, 0.1],
        [80, 40, 10, 10, 0.9, 0.1, 0.1, 0.9],
    )

    first = _decode(output, _frame(tmp_path), _bundle(tmp_path), _transform())
    second = _decode(output, _frame(tmp_path), _bundle(tmp_path), _transform())

    assert [(item.label, item.confidence) for item in first] == [
        ("person", 0.809),
        ("vehicle", 0.809),
        ("animal", 0.719),
    ]
    assert first[0].bounding_box == (0.15, 0.2, 0.25, 0.4)
    assert first[2].bounding_box == (0.1, 0.1, 0.9, 0.9)
    assert [item.class_source_label for item in first] == ["1", "2", "0"]
    assert [item.observation_id for item in first] == [item.observation_id for item in second]
    assert len({item.observation_id for item in first}) == 3


def test_md_v5_raw_strict_score_filter_preserves_separate_boxes_and_clips(tmp_path: Path) -> None:
    output = _raw(
        [5, 25, 20, 30, 0.5, 0.5, 0.1, 0.1],
        [25, 25, 10, 10, 0.8, 0.8, 0.1, 0.1],
        [75, 25, 10, 10, 0.8, 0.8, 0.1, 0.1],
    )

    detections = _decode(output, _frame(tmp_path), _bundle(tmp_path), _transform())

    assert len(detections) == 2
    assert all(item.label == "animal" for item in detections)
    assert [item.bounding_box for item in detections] == [
        (0.2, 0.0, 0.3, 0.1),
        (0.7, 0.0, 0.8, 0.1),
    ]


@pytest.mark.parametrize(
    "output",
    [
        [np.zeros((2, 3, 8), dtype=np.float32)],
        [np.zeros((1, 4, 7), dtype=np.float32)],
        [np.asarray([[[1, 1, 1, 1, np.nan, 1, 0, 0]]], dtype=np.float32)],
        [np.asarray([[[1, 1, 1, 1, 1, np.inf, 0, 0]]], dtype=np.float32)],
    ],
)
def test_md_v5_raw_rejects_malformed_or_nonfinite_output(
    tmp_path: Path, output: list[np.ndarray]
) -> None:
    with pytest.raises(ReplayValidationError, match="malformed_detector_output"):
        _decode(output, _frame(tmp_path), _bundle(tmp_path), _transform())


def test_md_v5_raw_rejects_excess_candidates(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, max_decode_candidates=2, raw_output_shape=None)
    with pytest.raises(ReplayValidationError, match="detector_output_limit"):
        _decode(
            [np.zeros((1, 3, 8), dtype=np.float32)],
            _frame(tmp_path),
            bundle,
            _transform(),
        )


def test_existing_xyxy_decoder_remains_unchanged(tmp_path: Path) -> None:
    bundle = _bundle(
        tmp_path,
        decoder_key=DECODER_KEY,
        broad_classes=("bird",),
        animal_classes=("bird",),
        max_observations_per_frame=1,
        raw_output_shape=None,
    )
    detections = _decode(
        [np.asarray([[[10, 30, 90, 70, 0.8, 0]]], dtype=np.float32)],
        _frame(tmp_path),
        bundle,
        _transform(),
    )
    assert detections[0].label == "bird"
    assert detections[0].confidence == 0.8
    assert detections[0].bounding_box == (0.1, 0.1, 0.9, 0.9)


def test_md_v5_bundle_contract_validates_raw_shape_mapping_and_source_hash(tmp_path: Path) -> None:
    model = tmp_path / "md-v5.onnx"
    model.write_bytes(b"fixture")
    payload: dict[str, object] = {
        "schema_version": 1,
        "model_key": "md-v5a",
        "model_version": "0.1",
        "model_file": model.name,
        "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "source_model_fingerprint": "b" * 64,
        "model_format": "ONNX",
        "license": "MIT",
        "redistribution": "local activation",
        "input_name": "images",
        "input_width": 1280,
        "input_height": 1280,
        "input_dtype": "float32",
        "input_scale": 1 / 255,
        "channel_order": "NCHW",
        "color_format": "RGB",
        "letterbox_fill": [114, 114, 114],
        "normalization_mean": [0.0, 0.0, 0.0],
        "normalization_std": [1.0, 1.0, 1.0],
        "resize_mode": "letterbox",
        "output_names": ["predictions"],
        "decoder_key": MDV5_DECODER_KEY,
        "broad_classes": ["animal", "person", "vehicle"],
        "animal_classes": ["animal"],
        "taxonomy": "MegaDetector v5 broad classes",
        "provenance": "official MegaDetector v5a",
        "provider_compatibility": ["onnx-cuda"],
        "limitations": ["shadow-only"],
        "score_threshold": 0.1,
        "max_observations_per_frame": 300,
        "nms_iou_threshold": 0.45,
        "nms_max_detections": 300,
        "max_decode_candidates": 102_000,
        "raw_output_shape": [1, 102_000, 8],
    }
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    bundle = OnnxModelBundle.load(manifest)
    assert bundle.raw_output_shape == (1, 102_000, 8)
    assert bundle.source_model_fingerprint == "b" * 64

    for update in (
        {"broad_classes": ["person", "animal", "vehicle"]},
        {"animal_classes": ["animal", "person"]},
        {"raw_output_shape": [1, 102_000, 7]},
        {"raw_output_shape": [2, 102_000, 8]},
        {"raw_output_shape": [1, 0, 8]},
        {"max_decode_candidates": 100_000},
        {"source_model_fingerprint": None},
    ):
        manifest.write_text(json.dumps({**payload, **update}), encoding="utf-8")
        with pytest.raises(ReplayValidationError, match="invalid_model_bundle"):
            OnnxModelBundle.load(manifest)


def test_md_v5_raw_applies_detection_bound(tmp_path: Path) -> None:
    output = _raw(
        [10, 50, 4, 4, 0.9, 0.9, 0.1, 0.1],
        [30, 50, 4, 4, 0.8, 0.9, 0.1, 0.1],
        [50, 50, 4, 4, 0.7, 0.9, 0.1, 0.1],
    )
    detections = _decode(
        output,
        _frame(tmp_path),
        _bundle(tmp_path, nms_max_detections=2),
        _transform(),
    )
    assert len(detections) == 2
    assert [item.confidence for item in detections] == [0.809, 0.719]


def test_execution_percentiles_use_linear_interpolation() -> None:
    values = [10.0, 20.0]
    assert _percentile(values, 0.5) == 15.0
    assert _percentile(values, 0.9) == 19.0
    assert _percentile(values, 0.95) == 19.5


class FakeSession:
    def __init__(self, assignment: dict[str, object]) -> None:
        self.assignment = assignment

    def get_providers(self) -> list[str]:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    def run(self, _outputs: list[str], _inputs: dict[str, object]) -> list[np.ndarray]:
        return [np.zeros((1, 0, 8), dtype=np.float32)]

    def execution_assignment(self) -> dict[str, object]:
        return self.assignment

    def close(self) -> None:
        return None


class FakeRuntime:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def available_providers(self) -> tuple[str, ...]:
        return ("CUDAExecutionProvider", "CPUExecutionProvider")

    def runtime_version(self) -> str:
        return "fixture"

    def create_session(self, *_args: object, **_kwargs: object) -> FakeSession:
        return self.session


class NoAssignmentSession:
    def get_providers(self) -> list[str]:
        return ["CUDAExecutionProvider"]

    def run(self, _outputs: list[str], _inputs: dict[str, object]) -> list[np.ndarray]:
        return [np.zeros((1, 0, 8), dtype=np.float32)]


@pytest.mark.anyio
async def test_provider_rejects_missing_execution_assignment_evidence(tmp_path: Path) -> None:
    class Runtime:
        def available_providers(self) -> tuple[str, ...]:
            return ("CUDAExecutionProvider",)

        def runtime_version(self) -> str:
            return "fixture"

        def create_session(self, *_args: object, **_kwargs: object) -> NoAssignmentSession:
            return NoAssignmentSession()

    provider = OnnxCudaObservationProvider(runtime=Runtime(), bundle=_bundle(tmp_path))
    provider.load()
    with pytest.raises(ReplayValidationError, match="onnx_cuda_verification_insufficient"):
        await provider.replay_frames((_frame(tmp_path),))


@pytest.mark.anyio
async def test_registered_cpu_is_accepted_when_profile_proves_cuda_only(tmp_path: Path) -> None:
    assignment = {
        "classification": "cuda_only_verified",
        "cuda_executed_nodes": 7,
        "cpu_executed_nodes": 0,
        "unknown_executed_nodes": 0,
    }
    provider = OnnxCudaObservationProvider(
        runtime=FakeRuntime(FakeSession(assignment)), bundle=_bundle(tmp_path)
    )
    provider.load()
    await provider.replay_frames((_frame(tmp_path),))
    assert provider.execution_facts()["cuda_execution_verification"] == assignment


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("assignment", "error"),
    [
        (
            {
                "classification": "mixed_cuda_cpu_execution",
                "cuda_executed_nodes": 6,
                "cpu_executed_nodes": 1,
                "unknown_executed_nodes": 0,
            },
            "onnx_cuda_mixed_execution",
        ),
        (
            {
                "classification": "cuda_execution_verification_insufficient",
                "cuda_executed_nodes": 0,
                "cpu_executed_nodes": 0,
                "unknown_executed_nodes": 1,
            },
            "onnx_cuda_verification_insufficient",
        ),
    ],
)
async def test_cuda_execution_assignment_must_be_verified(
    tmp_path: Path, assignment: dict[str, object], error: str
) -> None:
    provider = OnnxCudaObservationProvider(
        runtime=FakeRuntime(FakeSession(assignment)), bundle=_bundle(tmp_path)
    )
    provider.load()
    with pytest.raises(ReplayValidationError, match=error):
        await provider.replay_frames((_frame(tmp_path),))
