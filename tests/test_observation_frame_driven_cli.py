from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from mockingbird.observation.replay import ReplayFrame, ReplayInput
from mockingbird.observation.replay_cli import run as replay_run


class _Session:
    def __init__(self) -> None:
        self.calls = 0
        self.closed = False

    def get_providers(self) -> list[str]:
        return ["CUDAExecutionProvider"]

    def run(self, _outputs: list[str], _inputs: dict[str, object]) -> list[np.ndarray]:
        self.calls += 1
        return [np.asarray([[[20.0, 20.0, 40.0, 40.0, 0.9, 0.0]]], dtype=np.float32)]

    def execution_assignment(self) -> dict[str, object]:
        return {
            "classification": "cuda_only_verified",
            "cuda_executed_nodes": self.calls,
            "cpu_executed_nodes": 0,
            "unknown_executed_nodes": 0,
        }

    def close(self) -> None:
        self.closed = True


class _Runtime:
    def __init__(self, session: _Session) -> None:
        self.session = session

    def available_providers(self) -> tuple[str, ...]:
        return ("CUDAExecutionProvider",)

    def runtime_version(self) -> str:
        return "fixture"

    def create_session(self, *_args: object, **_kwargs: object) -> _Session:
        return self.session


def _files(tmp_path: Path) -> tuple[Path, Path, Path]:
    frames = tmp_path / "frames"
    frames.mkdir()
    hashes: list[str] = []
    for index in range(3):
        path = frames / f"frame-{index}.png"
        Image.new("RGB", (100, 100), color=(index * 20, 100, 30)).save(path)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
    replay = ReplayInput(
        "frame-driven-cli",
        "stream",
        100,
        100,
        1.0,
        tuple(ReplayFrame(index, index * 1000, value) for index, value in enumerate(hashes)),
    )
    manifest = tmp_path / "benchmark.json"
    manifest.write_text(json.dumps({
        "version": 1,
        "benchmark_id": "frame-driven-cli",
        "input_fingerprint": replay.fingerprint,
        "input_id": replay.input_id,
        "stream_id": replay.stream_id,
        "width": replay.width,
        "height": replay.height,
        "nominal_fps": replay.nominal_fps,
        "frames": [
            {"path": f"frame-{index}.png", "source_offset_ms": index * 1000, "content_hash": value}
            for index, value in enumerate(hashes)
        ],
        "appearances": [{"appearance_id": "bird", "start_offset_ms": 0, "end_offset_ms": 2000}],
        "visits": [{"visit_id": "bird-visit", "appearance_ids": ["bird"], "start_offset_ms": 0, "end_offset_ms": 2000}],
        "thresholds": {},
    }), encoding="utf-8")
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"fixture")
    bundle = tmp_path / "model-bundle.json"
    bundle.write_text(json.dumps({
        "schema_version": 1,
        "model_key": "fixture",
        "model_version": "1",
        "model_file": model.name,
        "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "model_format": "ONNX",
        "license": "fixture",
        "redistribution": "fixture",
        "input_name": "images",
        "input_width": 100,
        "input_height": 100,
        "input_dtype": "float32",
        "input_scale": 1 / 255,
        "channel_order": "NCHW",
        "color_format": "RGB",
        "letterbox_fill": [0, 0, 0],
        "normalization_mean": [0, 0, 0],
        "normalization_std": [1, 1, 1],
        "resize_mode": "stretch",
        "output_names": ["detections"],
        "decoder_key": "xyxy-score-class-v1",
        "broad_classes": ["animal"],
        "animal_classes": ["animal"],
        "taxonomy": "fixture",
        "provenance": "fixture",
        "provider_compatibility": ["onnx-cuda"],
        "limitations": ["fixture"],
    }), encoding="utf-8")
    configuration = tmp_path / "frame-driven.json"
    configuration.write_text(json.dumps({
        "schema_version": 1,
        "model_bundle": bundle.name,
        "settings": {
            "source_nominal_fps": 1.0,
            "baseline_detector_fps": 1.0,
            "candidate_detector_fps": 1.0,
            "minimum_detector_confirmations": 2,
        },
    }), encoding="utf-8")
    return frames, manifest, configuration


def test_frame_driven_cli_requires_config_and_writes_deterministic_shadow_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    frames, manifest, configuration = _files(tmp_path)
    assert replay_run([
        "--provider", "frame-driven-onnx-cuda",
        "--frames", str(frames),
        "--manifest", str(manifest),
        "--output", str(tmp_path / "missing"),
    ]) == 9

    sessions: list[_Session] = []

    def runtime() -> _Runtime:
        session = _Session()
        sessions.append(session)
        return _Runtime(session)

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime)
    payloads = []
    for name in ("first", "second"):
        output = tmp_path / name
        assert replay_run([
            "--provider", "frame-driven-onnx-cuda",
            "--provider-config", str(configuration),
            "--frames", str(frames),
            "--manifest", str(manifest),
            "--output", str(output),
        ]) == 0
        payloads.append(json.loads((output / "replay-report.json").read_text(encoding="utf-8")))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["provider"]["provider_id"] == "frame-driven-onnx-cuda"
    assert payloads[0]["provider"]["production_proposal_authority"] is False
    assert payloads[0]["metrics"]["frames_inferred"] == {"state": "evaluated", "value": 3}
    assert len(payloads[0]["track_updates"]) >= 3
    assert len(payloads[0]["proposals"]) == 1
    assert all(item["shadow_only"] for item in payloads[0]["proposals"])
    assert payloads[0]["evidence_candidates"]
    assert all(session.closed for session in sessions)
