"""Perception Replay Regression Harness v1: `perception_regression_cli.py`
end-to-end, in-process (no subprocess) -- exactly like `replay_cli.py`'s own
`test_snapshot_cli_runs_offline_and_writes_a_new_report` convention.
Provider construction is monkeypatched to a fast, hardware-free fake
detector: this file proves the CLI's own argument parsing, fixture
resolution, windowing wiring, and safe file I/O, not provider selection
(already covered by `test_perception_regression.py` and `replay_cli.py`'s
own tests).
"""
from __future__ import annotations

import hashlib
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.observation import perception_regression_cli as cli
from mockingbird.observation.contracts import DetectionObservation, FramePacket
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenSettings


class _FakeDetector:
    def __init__(self, detections: dict[str, tuple[DetectionObservation, ...]]) -> None:
        self.detections = detections

    def probe(self) -> dict[str, object]:
        return {"cuda_available": True, "model_bundle_compatible": True}

    def load(self) -> None:
        pass

    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]:
        return self.detections.get(frame.frame_id or "", ())

    def finalize_replay(self) -> None:
        pass

    def close(self) -> None:
        pass

    def report_metadata(self) -> dict[str, object]:
        return {"model": {"key": "fake", "version": "1"}}

    def execution_facts(self) -> dict[str, object]:
        return {}


def _settings() -> FrameDrivenSettings:
    return FrameDrivenSettings(
        source_nominal_fps=2.0, baseline_detector_fps=2.0, candidate_detector_fps=2.0,
        strong_detection_threshold=0.8, minimum_detector_confirmations=2, minimum_tracker_support_frames=1,
        maximum_missed_frames=2, maximum_frame_gap_ms=1000, tracker_expiry_ms=1000,
        maximum_track_duration_ms=30_000, maximum_active_tracks=8,
        maximum_unsupported_detector_ms=5000, negative_detector_frames_to_end=100,
    )


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color=(50, 100, 70)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _write_frames_and_manifest(tmp_path: Path, *, count: int, step_ms: int = 500, stream_id: str = "replay:fixture-feeder") -> tuple[Path, Path]:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    payload = _jpeg_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    frame_entries = []
    for index in range(count):
        (frames_dir / f"frame-{index:03d}.jpg").write_bytes(payload)
        frame_entries.append({"path": f"frame-{index:03d}.jpg", "source_offset_ms": index * step_ms, "content_hash": digest})
    manifest_document = {
        "version": 1, "benchmark_id": "cli-fixture", "input_id": "cli-fixture-input", "stream_id": stream_id,
        "width": 320, "height": 240, "nominal_fps": 2.0, "frames": frame_entries,
        "appearances": [], "visits": [], "thresholds": {},
    }
    # input_fingerprint requires a real ReplayInput to compute -- build one directly.
    from mockingbird.observation.replay import ReplayFrame, ReplayInput
    replay = ReplayInput(
        "cli-fixture-input", stream_id, 320, 240, 2.0,
        tuple(ReplayFrame(i, i * step_ms, digest) for i in range(count)),
    )
    manifest_document["input_fingerprint"] = replay.fingerprint
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_document), encoding="utf-8")
    return frames_dir, manifest_path


@pytest.fixture(autouse=True)
def _fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_configured_provider(*, provider_key: str, provider_config_path):
        provider = FrameDrivenObservationProvider(detector=_FakeDetector({}), settings=_settings())
        return provider, ("fake provider for CLI testing",)

    monkeypatch.setattr(cli, "_configured_provider", _fake_configured_provider)


def test_run_with_explicit_frames_and_manifest_writes_a_report(tmp_path: Path) -> None:
    frames_dir, manifest_path = _write_frames_and_manifest(tmp_path, count=4)
    output = tmp_path / "out"
    exit_code = cli.run([
        "run", "--frames", str(frames_dir), "--manifest", str(manifest_path),
        "--stream-id", "replay:fixture-feeder", "--output", str(output),
    ])
    assert exit_code == 0
    payload = json.loads((output / "perception-regression-report.json").read_text(encoding="utf-8"))
    assert payload["harness_version"] == "perception-replay-regression-harness-v1"
    assert payload["admission"]["outcome_counts"] == {}
    assert "execution" in payload
    assert str(frames_dir) not in json.dumps(payload["provenance"])


def test_run_rejects_both_fixture_and_explicit_frames(tmp_path: Path) -> None:
    frames_dir, manifest_path = _write_frames_and_manifest(tmp_path, count=2)
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps({"version": 1, "fixtures": []}), encoding="utf-8")
    exit_code = cli.run([
        "run", "--fixture", "anything", "--registry", str(registry_path),
        "--frames", str(frames_dir), "--manifest", str(manifest_path),
        "--stream-id", "replay:fixture-feeder", "--output", str(tmp_path / "out"),
    ])
    assert exit_code == cli._EXIT_CODES["fixture_and_explicit_input_both_given"]


def test_run_by_fixture_name_resolves_from_registry(tmp_path: Path) -> None:
    frames_dir, manifest_path = _write_frames_and_manifest(tmp_path, count=4)
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps({
        "version": 1,
        "fixtures": [{
            "fixture_id": "known_valid_bird_visit",
            "description": "test fixture",
            "source_kind": "benchmark_manifest",
            "frames_path": str(frames_dir),
            "manifest_path": str(manifest_path),
            "provider_key": "frame-driven-onnx-cuda",
            "provider_config_path": None,
            "stream_id": "replay:fixture-feeder",
            "base_observed_at": "2026-08-19T17:27:10+00:00",
        }],
    }), encoding="utf-8")
    output = tmp_path / "out"
    exit_code = cli.run(["run", "--fixture", "known_valid_bird_visit", "--registry", str(registry_path), "--output", str(output)])
    assert exit_code == 0
    payload = json.loads((output / "perception-regression-report.json").read_text(encoding="utf-8"))
    assert payload["provenance"]["provider_key"] == "frame-driven-onnx-cuda"


def test_list_fixtures_prints_every_declared_fixture(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    registry_path = tmp_path / "fixtures.json"
    registry_path.write_text(json.dumps({
        "version": 1,
        "fixtures": [{
            "fixture_id": "z_fixture", "description": "second", "source_kind": "benchmark_manifest",
            "frames_path": "/does/not/matter", "manifest_path": "/does/not/matter",
            "provider_key": "frame-driven-onnx-cuda", "provider_config_path": None,
            "stream_id": "replay:z", "base_observed_at": None,
        }, {
            "fixture_id": "a_fixture", "description": "first", "source_kind": "acceptance_recording",
            "frames_path": "/does/not/matter", "manifest_path": None,
            "provider_key": "frame-driven-onnx-cuda", "provider_config_path": None,
            "stream_id": "replay:a", "base_observed_at": None,
        }],
    }), encoding="utf-8")
    exit_code = cli.run(["list-fixtures", "--registry", str(registry_path)])
    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.index("a_fixture") < out.index("z_fixture")  # sorted


def test_compare_writes_a_deterministic_diff(tmp_path: Path) -> None:
    frames_dir, manifest_path = _write_frames_and_manifest(tmp_path, count=4)
    baseline_out = tmp_path / "baseline"
    candidate_out = tmp_path / "candidate"
    for output in (baseline_out, candidate_out):
        exit_code = cli.run([
            "run", "--frames", str(frames_dir), "--manifest", str(manifest_path),
            "--stream-id", "replay:fixture-feeder", "--output", str(output),
        ])
        assert exit_code == 0

    diff_output = tmp_path / "diff.json"
    exit_code = cli.run([
        "compare",
        "--baseline", str(baseline_out / "perception-regression-report.json"),
        "--candidate", str(candidate_out / "perception-regression-report.json"),
        "--output", str(diff_output),
    ])
    assert exit_code == 0
    diff = json.loads(diff_output.read_text(encoding="utf-8"))
    assert diff["replay_comparison"]["metrics"]
    assert all(row["classification"] == "equivalent" for row in diff["admission_comparisons"])
