"""CLI wiring tests for `evidence-benchmark`/`evidence-comparison`
(Observation Engine v2 Stage 6.13). Runs the real command entry points
end-to-end against hand-built fixture files; no real camera, CUDA, or
product database is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from mockingbird.observation.evidence_benchmark_cli import run_benchmark, run_comparison


def _manifest_payload(*, useful: bool) -> dict:
    return {
        "manifest_version": 1,
        "manifest_id": "cli-fixture",
        "source_description": "cli-test",
        "candidates": [{
            "candidate_id": "c1", "session_id": "session-1", "role": "tracked_best",
            "track_generation_id": "track-1", "width": 320, "height": 240,
            "subject_geometry": [0.2, 0.2, 0.6, 0.7], "useful_identification": useful,
            "image_path": "frames/c1.jpg",
        }],
        "appearances": [],
    }


def _write_manifest(tmp_path: Path, name: str, *, useful: bool) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(_manifest_payload(useful=useful)), encoding="utf-8")
    return path


def _frames_directory(tmp_path: Path) -> Path:
    frames = tmp_path / "frames"
    frames.mkdir(exist_ok=True)
    if not (frames / "c1.jpg").exists():
        Image.new("RGB", (320, 240), "white").save(frames / "c1.jpg")
    return tmp_path


def test_benchmark_cli_runs_end_to_end_and_is_deterministic(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, "manifest.json", useful=True)
    root = _frames_directory(tmp_path)

    payloads = []
    for name in ("run-a", "run-b"):
        destination = tmp_path / name
        exit_code = run_benchmark([
            "--frames", str(root), "--manifest", str(manifest_path), "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "evidence-benchmark-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["creates_truth"] is False
    assert payloads[0]["shadow_only"] is True
    assert "execution" in payloads[0]
    assert str(tmp_path.resolve()) not in json.dumps(payloads[0]["semantic"])
    assert str(tmp_path.resolve()) in json.dumps(payloads[0]["execution"])


def test_benchmark_cli_rejects_manifest_and_review_together(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, "manifest.json", useful=True)
    root = _frames_directory(tmp_path)
    review = tmp_path / "review"
    review.mkdir()

    exit_code = run_benchmark([
        "--review", str(review), "--frames", str(root), "--manifest", str(manifest_path),
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_benchmark_cli_rejects_missing_manifest_cleanly(tmp_path: Path) -> None:
    exit_code = run_benchmark(["--output", str(tmp_path / "out")])
    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_benchmark_cli_rejects_a_symlinked_manifest(tmp_path: Path) -> None:
    manifest_path = _write_manifest(tmp_path, "manifest.json", useful=True)
    link = tmp_path / "link.json"
    link.symlink_to(manifest_path)

    exit_code = run_benchmark(["--manifest", str(link), "--output", str(tmp_path / "out")])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_comparison_cli_runs_end_to_end_and_is_deterministic(tmp_path: Path) -> None:
    root = _frames_directory(tmp_path)
    baseline_manifest = _write_manifest(tmp_path, "baseline-manifest.json", useful=False)
    candidate_manifest = _write_manifest(tmp_path, "candidate-manifest.json", useful=True)

    assert run_benchmark([
        "--frames", str(root), "--manifest", str(baseline_manifest), "--output", str(tmp_path / "baseline"),
    ]) == 0
    assert run_benchmark([
        "--frames", str(root), "--manifest", str(candidate_manifest), "--output", str(tmp_path / "candidate"),
    ]) == 0

    payloads = []
    for name in ("cmp-a", "cmp-b"):
        destination = tmp_path / name
        exit_code = run_comparison([
            "--baseline", str(tmp_path / "baseline" / "evidence-benchmark-report.json"),
            "--candidate", str(tmp_path / "candidate" / "evidence-benchmark-report.json"),
            "--output", str(destination),
        ])
        assert exit_code == 0
        payloads.append(json.loads((destination / "evidence-comparison-report.json").read_text()))

    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert "winner" not in payloads[0]
    entry = next(item for item in payloads[0]["metrics"] if item["metric"] == "useful_identification_rate")
    assert entry["classification"] == "candidate better"


def test_comparison_cli_rejects_missing_baseline_report_cleanly(tmp_path: Path) -> None:
    root = _frames_directory(tmp_path)
    candidate_manifest = _write_manifest(tmp_path, "candidate-manifest.json", useful=True)
    assert run_benchmark([
        "--frames", str(root), "--manifest", str(candidate_manifest), "--output", str(tmp_path / "candidate"),
    ]) == 0

    exit_code = run_comparison([
        "--baseline", str(tmp_path / "missing.json"),
        "--candidate", str(tmp_path / "candidate" / "evidence-benchmark-report.json"),
        "--output", str(tmp_path / "out"),
    ])

    assert exit_code != 0
    assert not (tmp_path / "out").exists()


def test_review_only_benchmark_cli_invocation(tmp_path: Path) -> None:
    """The --review convenience path derives both candidates and truth
    mechanically from a Stage 6.6/6.8 packet -- no --frames/--manifest and
    no hand-copying required."""
    from dataclasses import asdict
    from mockingbird.observation.temporal_annotation import AnnotationSet, BoxAnnotation, EvidenceUsefulness, FrameAnnotation, Provenance
    from mockingbird.observation.temporal_capture import (
        CAPTURE_MANIFEST_SCHEMA_VERSION, STOP_DURATION_ELAPSED, TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
        CaptureBounds, CaptureSessionConfig, CaptureSessionManifest, RetainedFrameRecord,
    )

    review = tmp_path / "review"
    review.mkdir()
    config = CaptureSessionConfig(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1",
        stream_id="s1", transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=1000, analysis_height=1000, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    record = RetainedFrameRecord(
        frame_id="frame-a", sequence=0, source_offset_ms=0, provider_generation="gen-1",
        content_hash="h" * 64, byte_size=1000, trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,),
        detector_observation_count=1, animal_detection_count=1, max_animal_score=0.5,
        active_track_count=1, motion_proposal_count=0, track_generation_ids=("track-1",),
        session_offset_ms=0, connection_segment_id="segment-1",
    )
    manifest = CaptureSessionManifest(
        config=config, session_id="session-1", node_session_id="node-session-1",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=1000, first_sequence=0, last_sequence=0,
        sequence_gap_count=0, dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0,
        generation_reset_count=0, provider_generations=("gen-1",), model_fingerprint="model-fp",
        tracker_proposal_config_fingerprint="cfg-fp", frames=(record,), operator_markers=(),
        stop_condition=STOP_DURATION_ELAPSED,
    )
    document = manifest.to_semantic_dict()
    document["semantic_fingerprint"] = manifest.fingerprint
    (review / "capture-session-manifest.json").write_text(json.dumps(document), encoding="utf-8")

    annotations = AnnotationSet(
        1, "session-1", manifest.fingerprint,
        (FrameAnnotation(
            "frame-a", whole_frame_truth="yes", boxes=(BoxAnnotation((0.1, 0.1, 0.3, 0.3)),),
            evidence_usefulness=EvidenceUsefulness(True, True, True, False),
            provenance=Provenance("alice", "2026-08-06T00:00:00+00:00", "session-1", "detector_crop"),
        ),),
    )
    annotation_document = {
        "schema_version": annotations.schema_version, "capture_session_id": annotations.capture_session_id,
        "capture_manifest_fingerprint": annotations.capture_manifest_fingerprint,
        "frames": [asdict(item) for item in annotations.frames], "appearances": [],
    }
    (review / "annotation.json").write_text(json.dumps(annotation_document), encoding="utf-8")
    (review / "frames").mkdir()
    Image.new("RGB", (320, 240), "white").save(review / "frames" / "frame-a.jpg")

    destination = tmp_path / "out"
    exit_code = run_benchmark(["--review", str(review), "--output", str(destination)])

    assert exit_code == 0
    payload = json.loads((destination / "evidence-benchmark-report.json").read_text())
    assert payload["metrics"]["episodes_evaluated"] == {"state": "evaluated", "value": 1}
    assert payload["metrics"]["useful_identification_rate"] == {"state": "evaluated", "value": 1.0}
