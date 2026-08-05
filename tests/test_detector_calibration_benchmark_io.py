"""Safety and CLI-wiring tests for the detector-calibration benchmark's
filesystem I/O and command entry point. Uses fake ONNX Runtime sessions only
(mirrors tests/test_observation_onnx_cuda.py); no real model, camera, or
product database is touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mockingbird.observation.detector_benchmark import DetectorBenchmarkError
from mockingbird.observation.detector_benchmark_cli import run as detector_benchmark_run
from mockingbird.observation.detector_benchmark_io import (
    load_calibration_manifest,
    write_detector_benchmark_report,
)
from mockingbird.observation.onnx_provider import BUNDLE_SCHEMA_VERSION


def _bundle(tmp_path: Path, **updates: object) -> Path:
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"fake-onnx-model")
    payload: dict[str, object] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "model_key": "fixture-detector",
        "model_version": "1",
        "model_file": model.name,
        "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "model_format": "ONNX",
        "license": "fixture-only",
        "redistribution": "not-redistributable",
        "input_name": "images",
        "input_width": 4,
        "input_height": 4,
        "input_dtype": "float32",
        "input_scale": 0.00392156862745098,
        "channel_order": "NCHW",
        "color_format": "RGB",
        "letterbox_fill": [114, 114, 114],
        "normalization_mean": [0.0, 0.0, 0.0],
        "normalization_std": [1.0, 1.0, 1.0],
        "resize_mode": "letterbox",
        "output_names": ["detections"],
        "decoder_key": "xyxy-score-class-v1",
        "broad_classes": ["animal", "person", "vehicle"],
        "animal_classes": ["animal"],
        "taxonomy": "fixture broad classes",
        "provenance": "generated test contract",
        "provider_compatibility": ["onnx-cuda"],
        "limitations": ["test fixture"],
        "score_threshold": 0.1,
        "max_observations_per_frame": 10,
    }
    payload.update(updates)
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _cohort(tmp_path: Path) -> tuple[Path, Path]:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    positive = frames_dir / "positive.jpg"
    Image.new("RGB", (40, 20), color="white").save(positive)
    negative = frames_dir / "negative.jpg"
    Image.new("RGB", (40, 20), color="black").save(negative)

    manifest_payload = {
        "version": 1,
        "cohort_id": "fixture-cohort",
        "annotation_policy": "synthetic fixture cohort",
        "frames": [
            {
                "frame_id": "positive-1",
                "image": "positive.jpg",
                "width": 40,
                "height": 20,
                "animal_present": "yes",
                "boxes": [{"box": [0.25, 0.25, 0.75, 0.75], "broad_class": "animal"}],
                "scene_group": "fixture-scene",
            },
            {
                "frame_id": "negative-1",
                "image": "negative.jpg",
                "width": 40,
                "height": 20,
                "animal_present": "no",
                "scene_group": "fixture-scene",
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    return frames_dir, manifest_path


# --------------------------------------------------------------------------
# I/O safety
# --------------------------------------------------------------------------


def test_load_calibration_manifest_round_trips(tmp_path: Path) -> None:
    frames_dir, manifest_path = _cohort(tmp_path)

    manifest, root = load_calibration_manifest(frames_dir, manifest_path)

    assert len(manifest.frames) == 2
    assert root == frames_dir.resolve()
    positive = manifest.frame("positive-1")
    assert positive.animal_present == "yes"
    assert len(positive.boxes) == 1
    assert positive.content_hash is not None and len(positive.content_hash) == 64


def test_load_calibration_manifest_rejects_path_traversal(tmp_path: Path) -> None:
    frames_dir, manifest_path = _cohort(tmp_path)
    payload = json.loads(manifest_path.read_text())
    payload["frames"][0]["image"] = "../escape.jpg"
    manifest_path.write_text(json.dumps(payload))

    with pytest.raises(DetectorBenchmarkError, match="unsafe_frame_path"):
        load_calibration_manifest(frames_dir, manifest_path)


def test_load_calibration_manifest_rejects_absolute_image_path(tmp_path: Path) -> None:
    frames_dir, manifest_path = _cohort(tmp_path)
    payload = json.loads(manifest_path.read_text())
    payload["frames"][0]["image"] = str((frames_dir / "positive.jpg").resolve())
    manifest_path.write_text(json.dumps(payload))

    with pytest.raises(DetectorBenchmarkError, match="unsafe_frame_path"):
        load_calibration_manifest(frames_dir, manifest_path)


def test_load_calibration_manifest_rejects_hash_mismatch(tmp_path: Path) -> None:
    frames_dir, manifest_path = _cohort(tmp_path)
    payload = json.loads(manifest_path.read_text())
    payload["frames"][0]["content_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(payload))

    with pytest.raises(DetectorBenchmarkError, match="frame_hash_mismatch"):
        load_calibration_manifest(frames_dir, manifest_path)


def test_load_calibration_manifest_rejects_duplicate_frame_id(tmp_path: Path) -> None:
    frames_dir, manifest_path = _cohort(tmp_path)
    payload = json.loads(manifest_path.read_text())
    payload["frames"][1]["frame_id"] = payload["frames"][0]["frame_id"]
    manifest_path.write_text(json.dumps(payload))

    with pytest.raises(DetectorBenchmarkError, match="duplicate_frame_id"):
        load_calibration_manifest(frames_dir, manifest_path)


def test_write_report_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.txt").write_text("x")

    with pytest.raises(DetectorBenchmarkError, match="nonempty_output_directory"):
        write_detector_benchmark_report(output, {"semantic_fingerprint": "x"}, execution={})


def test_write_report_is_atomic_and_readable(tmp_path: Path) -> None:
    output = tmp_path / "output"
    semantic = {"schema_version": 1, "semantic_fingerprint": "abc"}

    path = write_detector_benchmark_report(output, semantic, execution={"duration_ms": 12})

    payload = json.loads(path.read_text())
    assert payload["semantic_fingerprint"] == "abc"
    assert payload["execution"] == {"duration_ms": 12}
    assert not list(output.glob(".*.tmp"))


# --------------------------------------------------------------------------
# CLI wiring (fake CUDA runtime only)
# --------------------------------------------------------------------------


class FakeSession:
    def __init__(self, outputs: object, providers: tuple[str, ...] = ("CUDAExecutionProvider",)) -> None:
        self.outputs = outputs
        self.providers = providers
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.closed = False

    def get_providers(self) -> list[str]:
        return list(self.providers)

    def run(self, outputs: list[str], inputs: dict[str, object]) -> object:
        self.calls.append((outputs, inputs))
        return self.outputs

    def execution_assignment(self) -> dict[str, object]:
        return {
            "classification": "cuda_only_verified",
            "cuda_executed_nodes": max(1, len(self.calls)),
            "cpu_executed_nodes": 0,
            "unknown_executed_nodes": 0,
        }

    def close(self) -> None:
        self.closed = True


class FakeRuntime:
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory
        self.sessions: list[FakeSession] = []

    def available_providers(self) -> tuple[str, ...]:
        return ("CUDAExecutionProvider",)

    def create_session(self, model_path: Path, *, input_name: str, output_names: tuple[str, ...]) -> FakeSession:
        session = self._session_factory()
        self.sessions.append(session)
        return session


def test_cli_end_to_end_with_fake_cuda_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _cohort(tmp_path)

    # One animal box overlapping the reviewed truth box, one non-animal box.
    # Both rows must land inside the letterbox content region (input y in
    # [1, 3) for a 40x20 source into a 4x4 input) or the real MDv5/generic
    # decoder correctly rejects them as pure-padding, zero-area boxes.
    output = np.asarray([[
        [1.0, 1.0, 3.0, 3.0, 0.8, 0],
        [3.0, 1.0, 4.0, 2.0, 0.9, 2],
    ]], dtype=np.float32)

    def runtime_factory() -> FakeRuntime:
        return FakeRuntime(lambda: FakeSession([output]))

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime_factory)

    payloads = []
    for name in ("run-a", "run-b"):
        destination = tmp_path / name
        exit_code = detector_benchmark_run([
            "--provider", "onnx-cuda",
            "--provider-config", str(bundle_path),
            "--frames", str(frames_dir),
            "--manifest", str(manifest_path),
            "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "detector-benchmark-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["creates_truth"] is False
    assert payloads[0]["shadow_only"] is True
    assert payloads[0]["overall_classification"] == "DETECTOR_CALIBRATION_INSUFFICIENT_DATA"
    assert payloads[0]["configured_threshold"] == 0.1
    assert 0.1 in payloads[0]["threshold_grid"]
    assert len(payloads[0]["recommendations"]) == 7
    assert str(bundle_path.parent.resolve()) not in json.dumps({k: v for k, v in payloads[0].items() if k != "execution"})
    assert "execution" in payloads[0]
    assert payloads[0]["execution"]["primary_execution_facts"]["cuda_execution_verification"]["classification"] == "cuda_only_verified"


def test_cli_rejects_missing_manifest_cleanly(tmp_path: Path) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    exit_code = detector_benchmark_run([
        "--provider", "onnx-cuda",
        "--provider-config", str(bundle_path),
        "--frames", str(frames_dir),
        "--manifest", str(tmp_path / "missing.json"),
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()
