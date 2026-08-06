"""Safety and CLI-wiring tests for the Stage 6.5 adaptive motion-proposal
detector benchmark's filesystem I/O and command entry points. Uses fake ONNX
Runtime sessions only (mirrors tests/test_multi_scale_cli.py); no real
model, camera, or product database is touched.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from mockingbird.observation.motion_proposal_benchmark import MotionProposalBenchmarkError
from mockingbird.observation.motion_proposal_cli import run_benchmark, run_decision
from mockingbird.observation.motion_proposal_io import (
    load_motion_proposal_report,
    write_motion_proposal_benchmark_report,
    write_motion_proposal_decision_report,
)
from mockingbird.observation.motion_proposal_strategy import FULL_FRAME_PLUS_MOTION_PROPOSALS
from mockingbird.observation.multi_scale_cli import run_benchmark as run_multi_scale_benchmark
from mockingbird.observation.onnx_provider import BUNDLE_SCHEMA_VERSION


def _bundle(tmp_path: Path) -> Path:
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
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest


def _temporal_cohort(tmp_path: Path) -> tuple[Path, Path]:
    """A real two-frame ordered sequence (blank -> localized change) plus one
    unrelated singleton frame, mirroring a genuine reviewed temporal cohort."""

    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    width, height = 1600, 1200

    blank = Image.new("RGB", (width, height), color=(40, 40, 40))
    blank.save(frames_dir / "a.jpg", quality=95)
    changed = blank.copy()
    ImageDraw.Draw(changed).rectangle((700, 500, 780, 580), fill=(220, 220, 220))
    changed.save(frames_dir / "b.jpg", quality=95)
    singleton = Image.new("RGB", (width, height), color=(10, 10, 10))
    singleton.save(frames_dir / "c.jpg", quality=95)

    manifest_payload = {
        "version": 1, "cohort_id": "fixture-motion-proposal-cohort", "annotation_policy": "synthetic fixture cohort",
        "frames": [
            {
                "frame_id": "a", "image": "a.jpg", "width": width, "height": height,
                "animal_present": "no", "scene_group": "fixture-scene",
                "sequence_id": "seq-1", "sequence_order": 0, "source_offset_ms": 0,
            },
            {
                "frame_id": "b", "image": "b.jpg", "width": width, "height": height,
                "animal_present": "yes", "scene_group": "fixture-scene",
                "boxes": [{"box": [700 / width, 500 / height, 780 / width, 580 / height], "broad_class": "animal"}],
                "sequence_id": "seq-1", "sequence_order": 1, "source_offset_ms": 1000,
            },
            {
                "frame_id": "c", "image": "c.jpg", "width": width, "height": height,
                "animal_present": "no", "scene_group": "fixture-scene",
                "sequence_id": "seq-2", "sequence_order": 0, "source_offset_ms": 0,
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
    return np.asarray([[[0.0, 0.0, 1.0, 1.0, 0.01, 0]]], dtype=np.float32)


def _patch_fake_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime",
        lambda: FakeRuntime(lambda: FakeSession([_no_detections_output()])),
    )


# --------------------------------------------------------------------------
# I/O safety
# --------------------------------------------------------------------------


def test_load_motion_proposal_report_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real.json"
    real.write_text(json.dumps({"a": 1}), encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(real)

    with pytest.raises(MotionProposalBenchmarkError, match="unsafe_report_path"):
        load_motion_proposal_report(link)


def test_load_motion_proposal_report_rejects_malformed_json(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not valid", encoding="utf-8")

    with pytest.raises(MotionProposalBenchmarkError, match="invalid_report_json"):
        load_motion_proposal_report(path)


def test_write_reports_are_atomic_and_use_distinct_filenames(tmp_path: Path) -> None:
    benchmark_output = tmp_path / "benchmark-output"
    decision_output = tmp_path / "decision-output"

    benchmark_path = write_motion_proposal_benchmark_report(benchmark_output, {"semantic_fingerprint": "abc"}, execution={"total_inference_calls": 5})
    decision_path = write_motion_proposal_decision_report(decision_output, {"semantic_fingerprint": "def"}, execution={})

    assert benchmark_path.name == "motion-proposal-benchmark-report.json"
    assert decision_path.name == "motion-proposal-decision-report.json"
    assert not list(benchmark_output.glob(".*.tmp"))
    assert not list(decision_output.glob(".*.tmp"))


def test_benchmark_cli_rejects_missing_manifest_cleanly(tmp_path: Path) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()

    exit_code = run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(tmp_path / "missing.json"), "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_decision_cli_rejects_missing_report_cleanly(tmp_path: Path) -> None:
    exit_code = run_decision([
        "--full-frame-report", str(tmp_path / "missing.json"),
        "--uniform-tiles-report", str(tmp_path / "also-missing.json"),
        "--motion-proposal-report", str(tmp_path / "still-missing.json"),
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


# --------------------------------------------------------------------------
# CLI wiring (fake CUDA runtime only)
# --------------------------------------------------------------------------


def test_benchmark_cli_end_to_end_is_deterministic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)

    payloads = []
    for name in ("run-a", "run-b"):
        destination = tmp_path / name
        exit_code = run_benchmark([
            "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
            "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "motion-proposal-benchmark-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["strategy"]["strategy_key"] == "full_frame_plus_motion_proposals"
    assert payloads[0]["creates_truth"] is False
    assert payloads[0]["production_proposal_authority"] is False


def test_benchmark_cli_produces_more_windows_only_for_the_frame_with_real_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)

    destination = tmp_path / "out"
    exit_code = run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(destination),
    ])
    assert exit_code == 0
    payload = json.loads((destination / "motion-proposal-benchmark-report.json").read_text())

    # a: first frame in seq-1, no predecessor -> full_frame only.
    # b: real localized change vs a -> full_frame + exactly one proposal.
    # c: first frame in seq-2 (no predecessor) -> full_frame only.
    assert payload["execution"]["windows_per_frame"] == {"a": 1, "b": 2, "c": 1}
    assert payload["execution"]["total_inference_calls"] == 4
    assert payload["execution"]["max_windows_per_frame"] == 1 + FULL_FRAME_PLUS_MOTION_PROPOSALS.max_proposals_per_frame
    assert payload["proposal_behavior"]["frames_with_proposals"] == 1
    assert payload["proposal_behavior"]["rejection_reason_distribution"] == [["first_frame_no_predecessor", 2]]
    assert "proposal_generation_latency_ms" in payload["execution"]
    assert "detector_latency_ms" in payload["execution"]


def test_decision_cli_consumes_existing_multi_scale_reports_unmodified(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)

    full_frame_out, uniform_tiles_out, motion_proposal_out, decision_out = (
        tmp_path / "full-frame", tmp_path / "uniform-tiles", tmp_path / "motion-proposal", tmp_path / "decision",
    )
    assert run_multi_scale_benchmark([
        "--strategy", "full_frame", "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(full_frame_out),
    ]) == 0
    assert run_multi_scale_benchmark([
        "--strategy", "full_frame_plus_uniform_tiles", "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(uniform_tiles_out),
    ]) == 0
    assert run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(motion_proposal_out),
    ]) == 0

    exit_code = run_decision([
        "--full-frame-report", str(full_frame_out / "multi-scale-benchmark-report.json"),
        "--uniform-tiles-report", str(uniform_tiles_out / "multi-scale-benchmark-report.json"),
        "--motion-proposal-report", str(motion_proposal_out / "motion-proposal-benchmark-report.json"),
        "--output", str(decision_out),
    ])
    assert exit_code == 0
    payload = json.loads((decision_out / "motion-proposal-decision-report.json").read_text())
    assert payload["final_recommendation"] in {
        "retain_full_frame_inference", "continue_adaptive_strategy_offline", "expand_temporal_benchmark_truth",
        "adaptive_strategy_ready_for_bounded_live_shadow_trial", "adaptive_strategy_unsuitable", "insufficient_temporal_data",
    }
    assert payload["safe_for_production_authority"] is False


# --------------------------------------------------------------------------
# 24. Absolute paths remain non-semantic
# --------------------------------------------------------------------------


def test_absolute_paths_never_enter_the_semantic_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)

    destination = tmp_path / "out"
    assert run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(destination),
    ]) == 0
    payload = json.loads((destination / "motion-proposal-benchmark-report.json").read_text())
    semantic_only = {key: value for key, value in payload.items() if key != "execution"}

    assert str(tmp_path.resolve()) not in json.dumps(semantic_only)
    assert str(frames_dir.resolve()) not in json.dumps(semantic_only)
    # The absolute root is allowed to appear only in the excluded execution section.
    assert "execution" in payload


# --------------------------------------------------------------------------
# 26. No runtime configuration mutation
# --------------------------------------------------------------------------


def test_running_the_benchmark_does_not_mutate_the_shared_strategy_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import asdict
    before = asdict(FULL_FRAME_PLUS_MOTION_PROPOSALS)

    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)
    assert run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(tmp_path / "out"),
    ]) == 0

    after = asdict(FULL_FRAME_PLUS_MOTION_PROPOSALS)
    assert before == after


def test_score_threshold_override_does_not_mutate_the_shared_preset(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from dataclasses import asdict
    before = asdict(FULL_FRAME_PLUS_MOTION_PROPOSALS)

    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)
    assert run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(tmp_path / "out"),
        "--score-threshold", "0.42",
    ]) == 0

    assert asdict(FULL_FRAME_PLUS_MOTION_PROPOSALS) == before
    payload = json.loads((tmp_path / "out" / "motion-proposal-benchmark-report.json").read_text())
    assert payload["strategy"]["per_window_score_threshold"] == 0.42


# --------------------------------------------------------------------------
# 27. No product repository or truth-write dependency
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", [
    "mockingbird.observation.motion_proposal_strategy",
    "mockingbird.observation.motion_proposal_benchmark",
    "mockingbird.observation.motion_proposal_io",
    "mockingbird.observation.motion_proposal_cli",
])
def test_stage_6_5_modules_never_import_the_product_repository(module_name: str) -> None:
    import importlib
    module = importlib.import_module(module_name)
    source = Path(module.__file__).read_text(encoding="utf-8")
    forbidden = ("mockingbird.repository", "mockingbird.persistence", "sqlalchemy", "mockingbird.api.main")
    for token in forbidden:
        assert token not in source, f"{module_name} references {token}"


# --------------------------------------------------------------------------
# 29. Buffers remain bounded end-to-end
# --------------------------------------------------------------------------


def test_total_inference_calls_stay_bounded_by_max_proposals_per_frame(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle_path = _bundle(tmp_path)
    frames_dir, manifest_path = _temporal_cohort(tmp_path)
    _patch_fake_cuda(monkeypatch)

    destination = tmp_path / "out"
    assert run_benchmark([
        "--provider", "onnx-cuda", "--provider-config", str(bundle_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path), "--output", str(destination),
    ]) == 0
    payload = json.loads((destination / "motion-proposal-benchmark-report.json").read_text())

    max_per_frame = 1 + FULL_FRAME_PLUS_MOTION_PROPOSALS.max_proposals_per_frame
    assert all(count <= max_per_frame for count in payload["execution"]["windows_per_frame"].values())
    assert payload["execution"]["total_inference_calls"] <= max_per_frame * 3  # 3 frames in the fixture cohort
