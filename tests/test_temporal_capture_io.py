"""Hardware-free tests for Stage 6.6 temporal-capture filesystem I/O safety:
output-directory bounds, marker read/write, and connection-config loading.
No Camera Node, CUDA, or product database is touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mockingbird.observation.temporal_capture import OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, OperatorMarker, TemporalCaptureError
from mockingbird.observation.temporal_capture_io import (
    load_camera_node_connection_config,
    read_operator_markers,
    safe_capture_output_directory,
    write_capture_manifest,
    write_frame_bytes,
    write_operator_marker,
)


# --------------------------------------------------------------------------
# 2. Output-directory safety
# --------------------------------------------------------------------------


def test_safe_output_directory_rejects_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(TemporalCaptureError, match="unsafe_output_path"):
        safe_capture_output_directory(link)


def test_safe_output_directory_rejects_nonempty_directory(tmp_path: Path) -> None:
    directory = tmp_path / "out"
    directory.mkdir()
    (directory / "existing.txt").write_text("x")
    with pytest.raises(TemporalCaptureError, match="nonempty_output_directory"):
        safe_capture_output_directory(directory)


def test_safe_output_directory_allows_existing_when_requested(tmp_path: Path) -> None:
    directory = tmp_path / "out"
    directory.mkdir()
    (directory / "existing.txt").write_text("x")
    resolved = safe_capture_output_directory(directory, allow_existing=True)
    assert resolved == directory.resolve()


def test_safe_output_directory_creates_a_new_directory(tmp_path: Path) -> None:
    directory = tmp_path / "brand-new"
    resolved = safe_capture_output_directory(directory)
    assert resolved.is_dir()


def test_write_frame_bytes_rejects_unsafe_frame_identity(tmp_path: Path) -> None:
    with pytest.raises(TemporalCaptureError, match="unsafe_frame_identity"):
        write_frame_bytes(tmp_path, frame_id="../escape", payload=b"data")


def test_write_frame_bytes_writes_into_the_expected_subdirectory(tmp_path: Path) -> None:
    path = write_frame_bytes(tmp_path, frame_id="frame-1", payload=b"\xff\xd8fakejpeg\xff\xd9")
    assert path == tmp_path / "frames" / "frame-1.jpg"
    assert path.read_bytes() == b"\xff\xd8fakejpeg\xff\xd9"


def test_write_frame_bytes_high_resolution_uses_its_own_subdirectory(tmp_path: Path) -> None:
    path = write_frame_bytes(tmp_path, frame_id="frame-1", payload=b"data", high_resolution=True)
    assert path == tmp_path / "high-resolution" / "frame-1.jpg"


def test_capture_manifest_write_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    write_capture_manifest(tmp_path, {"semantic_fingerprint": "abc"})
    assert not list(tmp_path.glob(".*.tmp"))
    assert (tmp_path / "capture-session-manifest.json").is_file()


def test_camera_node_connection_config_requires_every_field(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"base_address": "http://127.0.0.1:8787", "credential": "x"}))
    with pytest.raises(TemporalCaptureError):
        load_camera_node_connection_config(path)


def test_camera_node_connection_config_redacted_hides_the_credential(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    payload = {
        "base_address": "http://127.0.0.1:8787", "credential": "super-secret-token",
        "camera_id": "camera-0", "stream_id": "stream-1", "evidence_profile_id": "profile-1",
    }
    path.write_text(json.dumps(payload))
    config = load_camera_node_connection_config(path)
    redacted = config.redacted()
    assert redacted["credential"] == "<redacted>"
    assert "super-secret-token" not in json.dumps(redacted)


# --------------------------------------------------------------------------
# Operator marker read/write
# --------------------------------------------------------------------------


def test_operator_marker_round_trips_through_disk(tmp_path: Path) -> None:
    marker = OperatorMarker("marker-1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:00+00:00", note="a bird!")
    write_operator_marker(tmp_path, marker)
    markers = read_operator_markers(tmp_path)
    assert markers == (marker,)


def test_duplicate_marker_identity_is_rejected(tmp_path: Path) -> None:
    marker = OperatorMarker("marker-1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:00+00:00")
    write_operator_marker(tmp_path, marker)
    with pytest.raises(TemporalCaptureError, match="duplicate_marker_identity"):
        write_operator_marker(tmp_path, marker)


def test_read_operator_markers_returns_empty_when_no_markers_directory_exists(tmp_path: Path) -> None:
    assert read_operator_markers(tmp_path) == ()


def test_read_operator_markers_skips_a_corrupt_marker_file(tmp_path: Path) -> None:
    markers_dir = tmp_path / "markers"
    markers_dir.mkdir()
    (markers_dir / "broken.json").write_text("{not valid json")
    good = OperatorMarker("marker-1", OPERATOR_MARKER_WILDLIFE_VISIBLE_NOW, "2026-08-05T20:00:00+00:00")
    write_operator_marker(tmp_path, good)
    assert read_operator_markers(tmp_path) == (good,)
