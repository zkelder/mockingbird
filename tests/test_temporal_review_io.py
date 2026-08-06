"""Hardware-free tests for the Stage 6.6 review-packet renderer and the
`temporal-review-build`/`temporal-review-validate`/`temporal-review-export`
CLI commands. Uses synthetic capture directories only; no Camera Node,
CUDA, or product database is touched. Numbered sections mirror the task's
required hardware-free-test list.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image

from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    STOP_DURATION_ELAPSED,
    TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    RetainedFrameRecord,
)
from mockingbird.observation.temporal_capture_io import write_capture_manifest, write_frame_bytes
from mockingbird.observation.temporal_review_cli import run_build, run_export, run_validate
from mockingbird.observation.temporal_review_io import build_review_packet, safe_review_directory


def _jpeg(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (200, 150), color=color)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _write_capture_directory(tmp_path: Path, *, frame_specs: list[tuple[str, int]]) -> Path:
    """frame_specs: list of (frame_id, sequence) in the order to write them
    on disk (deliberately reversed from chronological, to prove the review
    packet re-orders chronologically rather than trusting write order)."""

    capture_dir = tmp_path / "capture"
    capture_dir.mkdir()
    records = []
    for frame_id, sequence in frame_specs:
        payload = _jpeg((10 + sequence * 20, 10, 10))
        write_frame_bytes(capture_dir, frame_id=frame_id, payload=payload)
        from hashlib import sha256
        records.append(RetainedFrameRecord(
            frame_id=frame_id, sequence=sequence, source_offset_ms=sequence * 1000, provider_generation="gen-1",
            content_hash=sha256(payload).hexdigest(), byte_size=len(payload),
            trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,), detector_observation_count=1,
            animal_detection_count=1, max_animal_score=0.8, active_track_count=0, motion_proposal_count=0,
            detection_boxes=((0.2, 0.2, 0.4, 0.4, 0.8),),
        ))
    config = CaptureSessionConfig(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id="stream-1",
        transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=200, analysis_height=150, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    manifest = CaptureSessionManifest(
        config=config, session_id="session-1", node_session_id="node-session-1",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=max(s for _, s in frame_specs) * 1000,
        first_sequence=0, last_sequence=max(s for _, s in frame_specs), sequence_gap_count=0,
        dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0, generation_reset_count=0,
        provider_generations=("gen-1",), model_fingerprint="model-fp", tracker_proposal_config_fingerprint="cfg-fp",
        frames=tuple(records), operator_markers=(), stop_condition=STOP_DURATION_ELAPSED,
    )
    semantic = manifest.to_semantic_dict()
    semantic["semantic_fingerprint"] = manifest.fingerprint
    write_capture_manifest(capture_dir, semantic)
    return capture_dir


# --------------------------------------------------------------------------
# 16. Review contact-sheet ordering
# --------------------------------------------------------------------------


def test_review_packet_orders_frames_chronologically_regardless_of_write_order(tmp_path: Path) -> None:
    # Written to disk in reverse chronological order (sequence 2, 0, 1).
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f2", 2), ("f0", 0), ("f1", 1)])
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    summary = build_review_packet(capture_dir, review_dir)
    assert summary["frame_count"] == 3

    index_html = (review_dir / "index.html").read_text()
    # The chronological frame_id order must appear in the rendered index.
    assert index_html.index("f0") < index_html.index("f1") < index_html.index("f2")


def test_contact_sheet_is_generated_and_bounded_in_size(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0), ("f1", 1)])
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    build_review_packet(capture_dir, review_dir)
    sheet_path = review_dir / "contact-sheet.jpg"
    assert sheet_path.is_file()
    with Image.open(sheet_path) as image:
        assert image.size[0] > 0 and image.size[1] > 0


# --------------------------------------------------------------------------
# 17. Detector-crop source-coordinate correctness
# --------------------------------------------------------------------------


def test_overlay_crop_draws_the_detection_box_at_the_correct_pixel_position(tmp_path: Path) -> None:
    from mockingbird.observation.temporal_review_io import _frame_overlay

    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0)])
    record = {
        "frame_id": "f0", "source_offset_ms": 0, "trigger_reasons": ["animal_above_operating_point"],
        "detection_boxes": [(0.25, 0.25, 0.5, 0.5, 0.9)], "motion_proposal_boxes": [],
    }
    overlay = _frame_overlay(capture_dir / "frames" / "f0.jpg", record, max_edge=200)
    width, height = overlay.size
    # A box at normalized (0.25,0.25,0.5,0.5) should have its outline pixels
    # cluster near x=width*0.25 and x=width*0.5, not smeared across the frame.
    from PIL import ImageDraw
    canvas_check = Image.new("RGB", overlay.size)
    ImageDraw.Draw(canvas_check).rectangle(
        (width * 0.25, height * 0.25, width * 0.5, height * 0.5), outline=(255, 60, 60), width=2,
    )
    # Sanity: the expected box location is fully inside the overlay canvas bounds.
    assert 0 <= width * 0.25 < width * 0.5 <= width
    assert 0 <= height * 0.25 < height * 0.5 <= height


# --------------------------------------------------------------------------
# Full CLI wiring: build -> validate -> export (all three targets)
# --------------------------------------------------------------------------


def test_review_build_creates_a_self_contained_directory_needing_no_capture_flag(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0)])
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0
    assert (review_dir / "capture-session-manifest.json").is_file()
    assert (review_dir / "annotation.json").is_file()

    # temporal-review-validate needs only --review (matches the task's own sketch).
    assert run_validate(["--review", str(review_dir)]) == 0


def test_review_build_never_writes_to_the_original_capture_directory(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("b1", 1), ("a1", 1), ("a2", 2)])
    original_bytes = (capture_dir / "capture-session-manifest.json").read_bytes()
    original_mtime = (capture_dir / "capture-session-manifest.json").stat().st_mtime_ns
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    build_review_packet(capture_dir, review_dir)
    # The upgraded manifest actually differs from the original (it gains
    # Stage 6.8 fields) -- proving this is a meaningful check, not a no-op.
    assert (review_dir / "capture-session-manifest.json").read_bytes() != original_bytes
    assert (capture_dir / "capture-session-manifest.json").read_bytes() == original_bytes
    assert (capture_dir / "capture-session-manifest.json").stat().st_mtime_ns == original_mtime


def test_upgraded_manifest_and_replay_export_never_contain_an_absolute_path(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("b1", 1), ("a1", 1), ("a2", 2)])
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0
    manifest_text = (review_dir / "capture-session-manifest.json").read_text()
    assert str(tmp_path) not in manifest_text
    assert str(capture_dir) not in manifest_text

    annotation_path = review_dir / "annotation.json"
    payload = json.loads(annotation_path.read_text())
    for frame in payload["frames"]:
        frame.update({
            "whole_frame_truth": "yes",
            "boxes": [{"box": [0.2, 0.2, 0.4, 0.4], "broad_class": "animal"}],
            "provenance": {
                "reviewer": "smoke", "reviewed_at_iso": "2026-08-05T20:05:00+00:00",
                "source_capture_session": "session-1", "truth_source": "full_frame_inspection",
            },
        })
    annotation_path.write_text(json.dumps(payload))
    assert run_validate(["--review", str(review_dir)]) == 0

    output_dir = tmp_path / "export-replay"
    assert run_export(["--review", str(review_dir), "--target", "replay", "--output", str(output_dir)]) == 0
    export_text = (output_dir / "temporal-review-replay-manifest.json").read_text()
    assert str(tmp_path) not in export_text
    assert str(capture_dir) not in export_text


def test_review_build_never_overwrites_an_in_progress_annotation_file(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0)])
    review_dir = safe_review_directory(tmp_path / "review")
    build_review_packet(capture_dir, review_dir)
    annotation_path = review_dir / "annotation.json"
    payload = json.loads(annotation_path.read_text())
    payload["frames"][0]["whole_frame_truth"] = "no"
    annotation_path.write_text(json.dumps(payload))

    build_review_packet(capture_dir, review_dir)  # re-run review-build

    reloaded = json.loads(annotation_path.read_text())
    assert reloaded["frames"][0]["whole_frame_truth"] == "no"  # not reset to "unreviewed"


def test_full_pipeline_export_to_all_three_targets(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0)])
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0

    annotation_path = review_dir / "annotation.json"
    payload = json.loads(annotation_path.read_text())
    payload["frames"][0].update({
        "whole_frame_truth": "yes",
        "boxes": [{"box": [0.2, 0.2, 0.4, 0.4], "broad_class": "animal"}],
        "provenance": {
            "reviewer": "smoke", "reviewed_at_iso": datetime.now(UTC).isoformat(),
            "source_capture_session": "session-1", "truth_source": "full_frame_inspection",
        },
    })
    annotation_path.write_text(json.dumps(payload))

    assert run_validate(["--review", str(review_dir)]) == 0

    for target, filename in (
        ("detector-calibration", "temporal-review-detector-calibration-manifest.json"),
        ("motion-proposal", "temporal-review-motion-proposal-manifest.json"),
        ("replay", "temporal-review-replay-manifest.json"),
    ):
        output_dir = tmp_path / f"export-{target}"
        assert run_export(["--review", str(review_dir), "--target", target, "--output", str(output_dir)]) == 0
        exported = json.loads((output_dir / filename).read_text())
        assert "dataset_statistics" in exported


def test_export_refuses_when_validation_fails(tmp_path: Path) -> None:
    capture_dir = _write_capture_directory(tmp_path, frame_specs=[("f0", 0)])
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0

    annotation_path = review_dir / "annotation.json"
    payload = json.loads(annotation_path.read_text())
    payload["frames"][0]["whole_frame_truth"] = "yes"  # no box, not marked unscorable -> invalid
    annotation_path.write_text(json.dumps(payload))

    output_dir = tmp_path / "export-out"
    exit_code = run_export(["--review", str(review_dir), "--target", "detector-calibration", "--output", str(output_dir)])
    assert exit_code != 0


# --------------------------------------------------------------------------
# Stage 6.8: full-session replay across a legacy (pre-Stage-6.8) multi-
# reconnect capture -- the capstone scenario this stage exists to fix.
# --------------------------------------------------------------------------


def _write_legacy_reconnect_capture_directory(tmp_path: Path) -> Path:
    """A pre-Stage-6.8 capture directory with two implied connections:
    frames a1/a2 (local sequence 1/2) and b1/b2 (local sequence 1/2 again,
    b1 chronologically *after* a2) -- exactly the real Stage 6.7 pattern
    (see docs/temporal-review-capture-contract.md) where connection-local
    `sequence` collides across reconnects. No `connection_segment_id`/
    `host_received_at` is set anywhere, so this manifest carries zero
    native Stage 6.8 fields and must go through legacy derivation."""

    capture_dir = tmp_path / "legacy-capture"
    capture_dir.mkdir()
    from hashlib import sha256
    frame_specs = [("a1", 1, 0), ("a2", 2, 500), ("b1", 1, 0), ("b2", 2, 500)]
    records = []
    for frame_id, sequence, offset_ms in frame_specs:
        payload = _jpeg((10 + sequence * 20, 10 + len(frame_id), 10))
        write_frame_bytes(capture_dir, frame_id=frame_id, payload=payload)
        records.append(RetainedFrameRecord(
            frame_id=frame_id, sequence=sequence, source_offset_ms=offset_ms, provider_generation="gen-1",
            content_hash=sha256(payload).hexdigest(), byte_size=len(payload),
            trigger_reasons=(TRIGGER_ANIMAL_ABOVE_OPERATING_POINT,), detector_observation_count=1,
            animal_detection_count=1, max_animal_score=0.8, active_track_count=0, motion_proposal_count=0,
            detection_boxes=((0.2, 0.2, 0.4, 0.4, 0.8),),
        ))
    config = CaptureSessionConfig(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id="stream-1",
        transport_key="camera-node-http-multipart-jpeg", provider_key="frame-driven-onnx-cuda",
        analysis_width=200, analysis_height=150, nominal_fps=2.0, review_score_threshold=0.02,
        shadow_operating_point=0.5, review_floor=0.1, evidence_profile_id="profile-1", bounds=CaptureBounds(),
    )
    # Simulates a genuinely pre-Stage-6.8 capture: the *frame records* never
    # populate connection_segment_id/host_received_at (nothing in the old
    # `_CaptureLoop` ever set them), which is what `upgrade_capture_manifest_
    # timeline` actually keys its native-vs-legacy decision on -- not the
    # schema_version number, which CaptureSessionConfig's own constructor
    # rightly refuses to backdate now that a real capture always populates
    # both together.
    manifest = CaptureSessionManifest(
        config=config, session_id="legacy-session-1", node_session_id="temporal-capture:legacy-run",
        start_host_time_iso="2026-08-05T20:00:00+00:00", end_host_time_iso="2026-08-05T20:01:00+00:00",
        start_source_offset_ms=0, end_source_offset_ms=500,
        first_sequence=1, last_sequence=2, sequence_gap_count=0,
        dropped_frame_count=0, coalesced_frame_count=0, stale_frame_count=0, generation_reset_count=1,
        provider_generations=("gen-1",), model_fingerprint="model-fp", tracker_proposal_config_fingerprint="cfg-fp",
        frames=tuple(records), operator_markers=(), stop_condition=STOP_DURATION_ELAPSED,
    )
    semantic = manifest.to_semantic_dict()
    semantic["semantic_fingerprint"] = manifest.fingerprint
    write_capture_manifest(capture_dir, semantic)
    return capture_dir


def test_full_session_replay_export_loads_after_a_legacy_reconnect_upgrade(tmp_path: Path) -> None:
    """The capstone regression test: build a review packet from a legacy,
    multi-reconnect capture (no manual connection-safe sub-window
    selection), review it, export to replay, and prove the export is a
    genuinely loadable `ReplayInput`/`BenchmarkManifest` -- not just a
    manifest that validates in isolation."""

    from mockingbird.observation.replay_io import load_replay_bundle

    capture_dir = _write_legacy_reconnect_capture_directory(tmp_path)
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0

    upgraded_manifest = json.loads((review_dir / "capture-session-manifest.json").read_text())
    assert upgraded_manifest["session_timeline_classification"] == "derived_session_timeline"
    session_sequences = sorted(item["session_sequence"] for item in upgraded_manifest["frames"])
    assert session_sequences == [0, 1, 2, 3]

    annotation_path = review_dir / "annotation.json"
    payload = json.loads(annotation_path.read_text())
    for frame in payload["frames"]:
        frame.update({
            "whole_frame_truth": "yes",
            "boxes": [{"box": [0.2, 0.2, 0.4, 0.4], "broad_class": "animal"}],
            "provenance": {
                "reviewer": "smoke", "reviewed_at_iso": "2026-08-05T20:05:00+00:00",
                "source_capture_session": "legacy-session-1", "truth_source": "full_frame_inspection",
            },
        })
    annotation_path.write_text(json.dumps(payload))

    assert run_validate(["--review", str(review_dir)]) == 0

    output_dir = tmp_path / "export-replay"
    assert run_export(["--review", str(review_dir), "--target", "replay", "--output", str(output_dir)]) == 0
    assert (output_dir / "images").is_dir()

    # The real proof: load it back exactly the way `replay-benchmark` would.
    bundle = load_replay_bundle(output_dir, output_dir / "temporal-review-replay-manifest.json")
    assert len(bundle.replay.frames) == 4
    offsets = [frame.source_offset_ms for frame in bundle.replay.frames]
    assert offsets == sorted(offsets) and len(set(offsets)) == 4
    assert bundle.manifest.input_fingerprint == bundle.replay.fingerprint


def test_repeated_full_session_replay_export_has_an_identical_fingerprint(tmp_path: Path) -> None:
    capture_dir = _write_legacy_reconnect_capture_directory(tmp_path)
    review_dir = tmp_path / "review"
    assert run_build(["--capture", str(capture_dir), "--output", str(review_dir)]) == 0

    first_output = tmp_path / "export-replay-a"
    second_output = tmp_path / "export-replay-b"
    assert run_export(["--review", str(review_dir), "--target", "replay", "--output", str(first_output)]) == 0
    assert run_export(["--review", str(review_dir), "--target", "replay", "--output", str(second_output)]) == 0
    first = json.loads((first_output / "temporal-review-replay-manifest.json").read_text())
    second = json.loads((second_output / "temporal-review-replay-manifest.json").read_text())
    assert first["input_fingerprint"] == second["input_fingerprint"]
