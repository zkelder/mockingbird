from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from PIL import Image
from mockingbird.observation.replay import ReplayFrame, ReplayInput, ReplayReport, ReplayValidationError
from mockingbird.observation.replay_cli import run as replay_run
from mockingbird.observation.replay_io import load_replay_bundle, write_replay_report



def _bundle_files(tmp_path: Path) -> tuple[Path, Path]:
    frames = tmp_path / "frames"
    frames.mkdir()
    for name in ("first.png", "second.png"):
        Image.new("RGB", (1, 1), color="white").save(frames / name)
    hashes = [hashlib.sha256((frames / name).read_bytes()).hexdigest() for name in ("first.png", "second.png")]
    replay = ReplayInput(
        "fixture-input", "fixture-stream", 1, 1, 1.0,
        (ReplayFrame(0, 0, hashes[0]), ReplayFrame(1, 1000, hashes[1])),
    )
    payload = {
        "version": 1, "benchmark_id": "fixture", "input_fingerprint": replay.fingerprint,
        "input_id": "fixture-input", "stream_id": "fixture-stream", "width": 1, "height": 1,
        "nominal_fps": 1.0,
        "frames": [
            {"path": "first.png", "source_offset_ms": 0, "content_hash": hashes[0]},
            {"path": "second.png", "source_offset_ms": 1000, "content_hash": hashes[1]},
        ],
        "appearances": [], "visits": [], "thresholds": {},
    }
    manifest = tmp_path / "benchmark.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return frames, manifest


def test_loader_validates_regular_images_and_constructs_stable_input(tmp_path: Path) -> None:
    frames, manifest = _bundle_files(tmp_path)
    bundle = load_replay_bundle(frames, manifest)
    assert [frame.source_offset_ms for frame in bundle.replay.frames] == [0, 1000]
    assert bundle.manifest.input_fingerprint == bundle.replay.fingerprint
    assert bundle.thresholds == {}
    assert all(frame.source_path and frame.source_path.endswith(".png") for frame in bundle.replay.frames)


def test_loader_accepts_bounded_frame_detection_annotations(tmp_path: Path) -> None:
    frames, manifest = _bundle_files(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["detections"] = [{
        "annotation_id": "bird-1",
        "frame_index": 0,
        "broad_class": "bird",
        "bounding_box": [0.1, 0.2, 0.8, 0.9],
    }]
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    bundle = load_replay_bundle(frames, manifest)
    assert bundle.manifest.detections[0].broad_class == "bird"
    assert bundle.manifest.detections[0].bounding_box == (0.1, 0.2, 0.8, 0.9)


def test_loader_rejects_parent_path_before_reading_a_frame(tmp_path: Path) -> None:
    frames, manifest = _bundle_files(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["frames"][0]["path"] = "../outside.png"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ReplayValidationError, match="unsafe_frame_path"):
        load_replay_bundle(frames, manifest)


def test_report_is_atomic_immutable_and_contains_no_source_path(tmp_path: Path) -> None:
    frames, manifest_path = _bundle_files(tmp_path)
    bundle = load_replay_bundle(frames, manifest_path)
    output = tmp_path / "report"
    report = ReplayReport((), (), (), {}, "semantic")
    report_path = write_replay_report(output, report, replay=bundle.replay, manifest=bundle.manifest,
        provider={"provider_id": "snapshot"}, limitations=("offline",), execution={})
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 3
    assert str(frames.resolve()) not in json.dumps(payload["semantic"])
    with pytest.raises(ReplayValidationError, match="nonempty_output_directory"):
        write_replay_report(output, report, replay=bundle.replay, manifest=bundle.manifest,
            provider={}, limitations=(), execution={})


def test_snapshot_cli_runs_offline_and_writes_a_new_report(tmp_path: Path) -> None:
    frames, manifest = _bundle_files(tmp_path)
    output = tmp_path / "result"
    assert replay_run(["--provider", "snapshot", "--frames", str(frames), "--manifest", str(manifest), "--output", str(output)]) == 0
    payload = json.loads((output / "replay-report.json").read_text(encoding="utf-8"))
    assert payload["creates_truth"] is False
    assert payload["provider"]["provider_id"] == "snapshot"
