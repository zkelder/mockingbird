from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha1, sha256
import json
from pathlib import Path
import shutil
import stat
from uuid import uuid4

import cv2
import numpy as np
import pytest

from mockingbird.motion.local_activity_diagnostic import (
    CROP_FILENAME,
    FULL_EVIDENCE_FILENAME,
    LOCAL_ACTIVITY_DIAGNOSTIC_DIR_ENV,
    MANIFEST_FILENAME,
    MAX_DIAGNOSTIC_JPEG_BYTES,
    MAX_DIAGNOSTIC_TOTAL_BYTES,
    QUALIFYING_MONITORING_FILENAME,
    LocalActivityDiagnosticExport,
    activity_diagnostic_export_from_capture,
    export_local_activity_diagnostic,
)
from mockingbird.repository.product_repository import ProductRepository


def _jpeg(color: tuple[int, int, int]) -> bytes:
    image = np.full((48, 64, 3), color, dtype=np.uint8)
    encoded, output = cv2.imencode(".jpg", image)
    assert encoded
    return output.tobytes()


@pytest.fixture
def output_directory() -> Path:
    directory = Path("/tmp") / f"mockingbird-local-diagnostic-{uuid4().hex}"
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture
def artifact() -> LocalActivityDiagnosticExport:
    monitoring = _jpeg((10, 20, 30))
    timestamp = datetime(2026, 7, 27, 18, 0, tzinfo=UTC)
    return LocalActivityDiagnosticExport(
        stream_id="stream-001",
        zone_id="zone-006",
        activity_session_id="live-activity-001",
        track_generation_id="zone-006:object-generation-test-00000001",
        qualifying_frame_identity=sha1(monitoring).hexdigest()[:20],
        detector_class="animal",
        detector_score=0.93,
        normalized_detector_box=(0.25, 0.30, 0.50, 0.60),
        normalized_padded_crop_box=(0.20, 0.25, 0.55, 0.65),
        monitoring_width=1920,
        monitoring_height=1440,
        full_width=4624,
        full_height=3472,
        crop_width=320,
        crop_height=420,
        alignment_group_id="camera-fov-001",
        capture_claimed_at=timestamp,
        capture_requested_at=timestamp,
        capture_completed_at=timestamp,
        qualifying_monitoring_jpeg=monitoring,
        full_evidence_jpeg=_jpeg((40, 50, 60)),
        crop_jpeg=_jpeg((70, 80, 90)),
    )


def _capture_claim(artifact: LocalActivityDiagnosticExport, *, status: str) -> dict[str, object]:
    return {
        "status": status,
        "stream_id": artifact.stream_id,
        "zone_id": artifact.zone_id,
        "activity_session_id": artifact.activity_session_id,
        "track_generation_id": artifact.track_generation_id,
        "qualifying_frame_identity": artifact.qualifying_frame_identity,
        "detector_class": artifact.detector_class,
        "detector_score": artifact.detector_score,
        "normalized_track_box": list(artifact.normalized_detector_box),
        "alignment_group_id": artifact.alignment_group_id,
        "claim_timestamp": artifact.capture_claimed_at,
        "request_timestamp": artifact.capture_requested_at,
        "completion_timestamp": artifact.capture_completed_at,
    }


def _captured_evidence(artifact: LocalActivityDiagnosticExport) -> dict[str, object]:
    return {
        "alignment_status": "aligned",
        "full_image": artifact.full_evidence_jpeg,
        "crop_image": artifact.crop_jpeg,
        "full_width": artifact.full_width,
        "full_height": artifact.full_height,
        "crop_width": artifact.crop_width,
        "crop_height": artifact.crop_height,
        "normalized_padded_crop_box": list(artifact.normalized_padded_crop_box),
    }


def test_export_writes_exact_in_memory_images_and_safe_manifest(
    artifact: LocalActivityDiagnosticExport,
    output_directory: Path,
) -> None:
    result = export_local_activity_diagnostic(
        artifact,
        output_directory=output_directory,
    )

    assert result.exported
    assert (output_directory / QUALIFYING_MONITORING_FILENAME).read_bytes() == (
        artifact.qualifying_monitoring_jpeg
    )
    assert (output_directory / FULL_EVIDENCE_FILENAME).read_bytes() == (
        artifact.full_evidence_jpeg
    )
    assert (output_directory / CROP_FILENAME).read_bytes() == artifact.crop_jpeg
    manifest = json.loads((output_directory / MANIFEST_FILENAME).read_text())
    assert manifest["qualifying_frame_identity"] == artifact.qualifying_frame_identity
    assert manifest["detector"] == {
        "class": "animal",
        "normalized_box": [0.25, 0.3, 0.5, 0.6],
        "score": 0.93,
    }
    assert manifest["image_sha256"] == {
        QUALIFYING_MONITORING_FILENAME: sha256(
            artifact.qualifying_monitoring_jpeg
        ).hexdigest(),
        FULL_EVIDENCE_FILENAME: sha256(artifact.full_evidence_jpeg).hexdigest(),
        CROP_FILENAME: sha256(artifact.crop_jpeg).hexdigest(),
    }
    assert stat.S_IMODE(output_directory.stat().st_mode) & 0o077 == 0
    assert all(
        stat.S_IMODE((output_directory / name).stat().st_mode) & 0o077 == 0
        for name in (
            QUALIFYING_MONITORING_FILENAME,
            FULL_EVIDENCE_FILENAME,
            CROP_FILENAME,
            MANIFEST_FILENAME,
        )
    )
    manifest_text = (output_directory / MANIFEST_FILENAME).read_text()
    assert "credential" not in manifest_text
    assert "bearer" not in manifest_text
    assert str(output_directory) not in manifest_text


def test_export_is_disabled_without_the_explicit_environment_opt_in(
    artifact: LocalActivityDiagnosticExport,
) -> None:
    result = export_local_activity_diagnostic(artifact, environment={})

    assert result.status == "disabled"


def test_capture_adapter_requires_current_successful_aligned_evidence(
    artifact: LocalActivityDiagnosticExport,
    output_directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(LOCAL_ACTIVITY_DIAGNOSTIC_DIR_ENV, str(output_directory))
    failed = activity_diagnostic_export_from_capture(
        capture_claim=_capture_claim(artifact, status="stale"),
        captured_evidence=_captured_evidence(artifact),
        qualifying_monitoring_jpeg=artifact.qualifying_monitoring_jpeg,
        qualifying_monitoring_width=artifact.monitoring_width,
        qualifying_monitoring_height=artifact.monitoring_height,
    )

    assert failed.status == "capture_not_succeeded"
    assert not output_directory.exists()

    unaligned = activity_diagnostic_export_from_capture(
        capture_claim=_capture_claim(artifact, status="succeeded"),
        captured_evidence={**_captured_evidence(artifact), "alignment_status": "full_only"},
        qualifying_monitoring_jpeg=artifact.qualifying_monitoring_jpeg,
        qualifying_monitoring_width=artifact.monitoring_width,
        qualifying_monitoring_height=artifact.monitoring_height,
    )

    assert unaligned.status == "capture_not_exportable"
    assert not output_directory.exists()


def test_export_bounds_and_frame_identity_fail_closed(
    artifact: LocalActivityDiagnosticExport,
    output_directory: Path,
) -> None:
    oversized_jpeg = b"\xff\xd8" + b"x" * MAX_DIAGNOSTIC_JPEG_BYTES + b"\xff\xd9"
    oversized = replace(artifact, full_evidence_jpeg=oversized_jpeg)

    assert (
        export_local_activity_diagnostic(oversized, output_directory=output_directory).status
        == "invalid_or_oversized_jpeg"
    )
    assert not output_directory.exists()

    excessive_jpeg = b"\xff\xd8" + b"x" * (MAX_DIAGNOSTIC_TOTAL_BYTES // 3) + b"\xff\xd9"
    excessive = replace(
        artifact,
        qualifying_monitoring_jpeg=excessive_jpeg,
        qualifying_frame_identity=sha1(excessive_jpeg).hexdigest()[:20],
        full_evidence_jpeg=excessive_jpeg,
        crop_jpeg=excessive_jpeg,
    )
    assert (
        export_local_activity_diagnostic(excessive, output_directory=output_directory).status
        == "total_size_exceeded"
    )
    assert not output_directory.exists()

    mismatched = replace(artifact, qualifying_frame_identity="not-the-frame")
    assert (
        export_local_activity_diagnostic(mismatched, output_directory=output_directory).status
        == "qualifying_frame_mismatch"
    )
    assert not output_directory.exists()


def test_later_generation_cannot_overwrite_or_inherit_manifest(
    artifact: LocalActivityDiagnosticExport,
    output_directory: Path,
) -> None:
    first = export_local_activity_diagnostic(artifact, output_directory=output_directory)
    manifest_before = (output_directory / MANIFEST_FILENAME).read_bytes()
    later = replace(
        artifact,
        track_generation_id="zone-006:object-generation-test-00000002",
    )

    second = export_local_activity_diagnostic(later, output_directory=output_directory)

    assert first.exported
    assert not second.exported
    assert (output_directory / MANIFEST_FILENAME).read_bytes() == manifest_before
    assert json.loads(manifest_before)["track_generation_id"] == artifact.track_generation_id


def test_export_never_creates_product_records(
    artifact: LocalActivityDiagnosticExport,
    output_directory: Path,
    tmp_path: Path,
) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    before = (
        len(repository.list_events()),
        len(repository.list_visits()),
        len(repository.list_media_assets()),
        len(repository.review_queue_items()),
        len(repository.list_review_labels()),
    )
    try:
        result = export_local_activity_diagnostic(
            artifact,
            output_directory=output_directory,
        )
        after = (
            len(repository.list_events()),
            len(repository.list_visits()),
            len(repository.list_media_assets()),
            len(repository.review_queue_items()),
            len(repository.list_review_labels()),
        )
    finally:
        repository.close()

    assert result.exported
    assert after == before
