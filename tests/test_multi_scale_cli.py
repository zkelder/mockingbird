"""Safety and CLI-wiring tests for the Stage 6.4 multi-scale detector
benchmark's filesystem I/O and command entry points. Uses fake ONNX Runtime
sessions only (mirrors tests/test_detector_calibration_benchmark_io.py); no
real model, camera, or product database is touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from mockingbird.observation.multi_scale_benchmark import MultiScaleBenchmarkError
from mockingbird.observation.multi_scale_benchmark_io import (
    load_multi_scale_benchmark_report,
    write_multi_scale_benchmark_report,
    write_multi_scale_comparison_report,
)
from mockingbird.observation.multi_scale_cli import run_benchmark, run_comparison
from mockingbird.observation.onnx_provider import BUNDLE_SCHEMA_VERSION


def _bundle(tmp_path: Path, **updates: object) -> Path:
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"fake-onnx-model")
    payload: dict[str, object] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "model_key": "fixture-detector", "model_version": "1", "model_file": model.name,
        "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "model_format": "ONNX", "license": "fixture-only", "redistribution": "not-redistributable",
        "input_name": "images", "input_width": 4, "input_height": 4, "input_dtype": "float32",
        "input_scale": 0.00392156862745098, "channel_order": "NCHW", "color_format": "RGB",
        "letterbox_fill": [114, 114, 114], "normalization_mean": [0.0, 0.0, 0.0],
        "normalization_std": [1.0, 1.0, 1.0], "resize_mode": "letterbox",
        "output_names": ["detections"], "decoder_key": "xyxy-score-class-v1",
        "broad_classes": ["animal", "person", "vehicle"], "animal_classes": ["animal"],
        "taxonomy": "fixture broad classes", "provenance": "generated test contract",
        "provider_compatibility": ["onnx-cuda"], "limitations": ["test fixture"],
        "score_threshold": 0.1, "max_observations_per_frame": 10,
    }
    payload.update(updates)
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _cohort(tmp_path: Path) -> tuple[Path, Path]:
    """A cohort with one large (tiling-eligible) positive frame and one
    small (full-frame-only) negative frame."""

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    large = frames_dir / "large.jpg"
    Image.new("RGB", (1200, 1200), color="white").save(large)
    small = frames_dir / "small.jpg"
    Image.new("RGB", (200, 150), color="black").save(small)

    manifest_payload = {
        "version": 1, "cohort_id": "fixture-multi-scale-cohort", "annotation_policy": "synthetic fixture cohort",
        "frames": [
            {
                "frame_id": "large-1", "image": "large.jpg", "width": 1200, "height": 1200,
                "animal_present": "yes",
                "boxes": [{"box": [0.25, 0.25, 0.75, 0.75], "broad_class": "animal"}],
                "scene_group": "fixture-scene",
            },
            {
                "frame_id": "small-1", "image": "small.jpg", "width": 200, "height": 150,
                "animal_present": "no", "scene_group": "fixture-scene",
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    return frames_dir, manifest_path


class FakeSession:
    def __init__(self, outputs: object, providers: tuple[str, ...] = ("CUDAExecutionProvider",)) -> None:
        self.outputs = outputs
        self.providers = providers
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def get_providers(self) -> list[str]:
        return list(self.providers)

    def run(self, outputs: list[str], inputs: dict[str, object]) -> object:
        self.calls.append((outputs, inputs))
        return self.outputs

    def execution_assignment(self) -> dict[str, object]:
        return {
            "classification": "cuda_only_verified", "cuda_executed_nodes": max(1, len(self.calls)),
            "cpu_executed_nodes": 0, "unknown_executed_nodes": 0,
        }

    def close(self) -> None:
        pass


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


def _no_detections_output() -> np.ndarray:
    # An empty (all below-threshold) xyxy-score-class row set: one row that
    # never clears the 0.1 configured threshold.
    return np.asarray([[[0.0, 0.0, 1.0, 1.0, 0.01, 0]]], dtype=np.float32)


# --------------------------------------------------------------------------
# I/O safety
# --------------------------------------------------------------------------


def test_load_multi_scale_benchmark_report_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text(json.dumps({"a": 1}), encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    with pytest.raises(MultiScaleBenchmarkError, match="unsafe_report_path"):
        load_multi_scale_benchmark_report(link)


def test_load_multi_scale_benchmark_report_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid", encoding="utf-8")

    with pytest.raises(MultiScaleBenchmarkError, match="invalid_report_json"):
        load_multi_scale_benchmark_report(path)


def test_write_benchmark_report_rejects_nonempty_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "existing.txt").write_text("x")

    with pytest.raises(MultiScaleBenchmarkError, match="nonempty_output_directory"):
        write_multi_scale_benchmark_report(output, {"semantic_fingerprint": "x"}, execution={})


def test_write_reports_are_atomic_and_use_distinct_filenames(tmp_path: Path) -> None:
    benchmark_output = tmp_path / "benchmark-output"
    comparison_output = tmp_path / "comparison-output"

    benchmark_path = write_multi_scale_benchmark_report(benchmark_output, {"semantic_fingerprint": "abc"}, execution={"total_inference_calls": 5})
    comparison_path = write_multi_scale_comparison_report(comparison_output, {"semantic_fingerprint": "def"}, execution={})

    assert benchmark_path.name == "multi-scale-benchmark-report.json"
    assert comparison_path.name == "multi-scale-comparison-report.json"
    assert not list(benchmark_output.glob(".*.tmp"))
    assert not list(comparison_output.glob(".*.tmp"))


# --------------------------------------------------------------------------
# CLI wiring (fake CUDA runtime only)
# --------------------------------------------------------------------------


def test_full_frame_cli_end_to_end_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _cohort(tmp_path)

    def runtime_factory() -> FakeRuntime:
        return FakeRuntime(lambda: FakeSession([_no_detections_output()]))

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime_factory)

    payloads = []
    for name in ("run-a", "run-b"):
        destination = tmp_path / name
        exit_code = run_benchmark([
            "--strategy", "full_frame", "--provider", "onnx-cuda",
            "--provider-config", str(bundle_path), "--frames", str(frames_dir),
            "--manifest", str(manifest_path), "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "multi-scale-benchmark-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["strategy"]["strategy_key"] == "full_frame"
    assert payloads[0]["creates_truth"] is False
    assert "execution" in payloads[0]
    assert payloads[0]["execution"]["total_inference_calls"] == 2  # one window (full_frame) per frame, 2 frames
    assert str(bundle_path.parent.resolve()) not in json.dumps({k: v for k, v in payloads[0].items() if k != "execution"})


def test_tiled_cli_runs_more_than_one_window_on_the_large_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _cohort(tmp_path)

    def runtime_factory() -> FakeRuntime:
        return FakeRuntime(lambda: FakeSession([_no_detections_output()]))

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime_factory)

    destination = tmp_path / "tiled-out"
    exit_code = run_benchmark([
        "--strategy", "full_frame_plus_uniform_tiles", "--provider", "onnx-cuda",
        "--provider-config", str(bundle_path), "--frames", str(frames_dir),
        "--manifest", str(manifest_path), "--output", str(destination),
    ])

    assert exit_code == 0
    payload = json.loads((destination / "multi-scale-benchmark-report.json").read_text())
    # large-1 (1200x1200, above the 960 min) gets full_frame + tiles;
    # small-1 (200x150, below the min) degrades to full_frame only.
    assert payload["execution"]["windows_per_frame"]["large-1"] > 1
    assert payload["execution"]["windows_per_frame"]["small-1"] == 1
    assert payload["execution"]["total_inference_calls"] == (
        payload["execution"]["windows_per_frame"]["large-1"] + payload["execution"]["windows_per_frame"]["small-1"]
    )


def test_comparison_cli_end_to_end_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _cohort(tmp_path)

    def runtime_factory() -> FakeRuntime:
        return FakeRuntime(lambda: FakeSession([_no_detections_output()]))

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime_factory)

    full_frame_out = tmp_path / "full-frame-out"
    tiled_out = tmp_path / "tiled-out"
    assert run_benchmark([
        "--strategy", "full_frame", "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(full_frame_out),
    ]) == 0
    assert run_benchmark([
        "--strategy", "full_frame_plus_uniform_tiles", "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(tiled_out),
    ]) == 0

    comparison_payloads = []
    for name in ("cmp-a", "cmp-b"):
        destination = tmp_path / name
        exit_code = run_comparison([
            "--baseline-report", str(full_frame_out / "multi-scale-benchmark-report.json"),
            "--candidate-report", str(tiled_out / "multi-scale-benchmark-report.json"),
            "--output", str(destination),
        ])
        assert exit_code == 0
        comparison_payloads.append(json.loads((destination / "multi-scale-comparison-report.json").read_text()))

    assert comparison_payloads[0]["semantic_fingerprint"] == comparison_payloads[1]["semantic_fingerprint"]
    assert comparison_payloads[0]["baseline_strategy"] == "full_frame"
    assert comparison_payloads[0]["candidate_strategy"] == "full_frame_plus_uniform_tiles"
    assert comparison_payloads[0]["cohort_consistent"] is True


def test_cli_rejects_missing_manifest_cleanly(tmp_path: Path) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    exit_code = run_benchmark([
        "--strategy", "full_frame", "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_comparison_cli_rejects_missing_report_cleanly(tmp_path: Path) -> None:
    exit_code = run_comparison([
        "--baseline-report", str(tmp_path / "missing.json"),
        "--candidate-report", str(tmp_path / "also-missing.json"),
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()
