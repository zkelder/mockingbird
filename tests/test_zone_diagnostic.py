from __future__ import annotations

import importlib.util
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np


def _utility_module():
    path = Path("scripts/capture_zone_diagnostic.py")
    spec = importlib.util.spec_from_file_location("capture_zone_diagnostic", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_diagnostic_bounds_match_the_real_zone_capture_policy() -> None:
    utility = _utility_module()

    assert utility.MAX_DURATION_SECONDS == 30 * 60
    assert utility.MAX_FILES == 1_800
    assert utility.MAX_BYTES == 250 * 1024 * 1024
    assert utility.CAPTURE_INTERVAL_SECONDS == 1.0


def test_mjpeg_reader_extracts_only_the_bounded_jpeg_payload() -> None:
    utility = _utility_module()
    payload = b"jpeg-zone-crop"
    response = BytesIO(
        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 14\r\n\r\n"
        + payload
        + b"\r\n"
    )

    assert utility._read_mjpeg_frame(response) == payload


def test_contact_sheet_is_compact_and_contains_only_derived_crop_pixels() -> None:
    utility = _utility_module()
    images = [
        np.full((540, 960, 3), fill_value=value, dtype=np.uint8)
        for value in (30, 200)
    ]

    encoded = utility._contact_sheet_jpeg(images)
    assert encoded is not None
    decoded = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)

    assert decoded is not None
    assert decoded.shape == (90, 1600, 3)
    assert int(decoded[45, 80].mean()) < 50
    assert int(decoded[45, 240].mean()) > 180


def test_manifest_records_bounded_capture_and_duplicate_telemetry() -> None:
    utility = _utility_module()

    manifest = utility._capture_manifest(
        stream_id="stream-local",
        zone_id="zone-local",
        started_at="2026-07-26T00:00:00+00:00",
        duration_seconds=3.2,
        records=[{"file": "zone-crop-0001.jpg", "frame_identity": "frame-identity"}],
        crop_bytes=100,
        contact_sheet_bytes=25,
        duplicate_frame_count=2,
        frozen_frame_count=1,
        reconnect_count=3,
        connection_error_count=1,
        contact_sheets=["contact-sheet-001.jpg"],
        status="completed",
        stop_reason="duration_elapsed",
    )

    assert manifest["crop_count"] == 1
    assert manifest["total_bytes"] == 125
    assert manifest["duplicate_frame_count"] == 2
    assert manifest["frozen_frame_count"] == 1
    assert manifest["connection_error_count"] == 1
    assert manifest["records"][0]["frame_identity"] == "frame-identity"


def test_capture_status_preserves_interruption_and_failure_outcomes() -> None:
    utility = _utility_module()

    assert utility._final_capture_status(None) == "completed"
    assert utility._final_capture_status("maximum_crop_count") == "completed"
    assert utility._final_capture_status("interrupted") == "interrupted"
    assert utility._final_capture_status("capture_error_TimeoutError") == "failed"
