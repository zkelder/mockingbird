"""Opt-in local export of one pending high-resolution activity artifact set.

This module is deliberately outside the product-media and API paths.  It is
for a local operator to inspect the exact in-memory bytes before an explicit
review handoff persists them.  The export target is supplied only through an
environment variable, must be a fresh direct child of ``/tmp``, and accepts at
most one complete artifact set.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1, sha256
import json
import math
import os
from pathlib import Path
import re
from typing import Any, Mapping


LOCAL_ACTIVITY_DIAGNOSTIC_DIR_ENV = "MOCKINGBIRD_LOCAL_ACTIVITY_DIAGNOSTIC_DIR"
MAX_DIAGNOSTIC_JPEG_BYTES = 16_000_000
MAX_DIAGNOSTIC_TOTAL_BYTES = 32_000_000
MAX_DIAGNOSTIC_MANIFEST_BYTES = 64_000

QUALIFYING_MONITORING_FILENAME = "qualifying-monitoring.jpg"
FULL_EVIDENCE_FILENAME = "high-resolution-evidence.jpg"
CROP_FILENAME = "high-resolution-crop.jpg"
MANIFEST_FILENAME = "manifest.json"

_SAFE_LINEAGE_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


@dataclass(frozen=True)
class LocalActivityDiagnosticExport:
    """The exact bytes and safe provenance for one successful track capture."""

    stream_id: str
    zone_id: str
    activity_session_id: str
    track_generation_id: str
    qualifying_frame_identity: str
    detector_class: str
    detector_score: float
    normalized_detector_box: tuple[float, float, float, float]
    normalized_padded_crop_box: tuple[float, float, float, float]
    monitoring_width: int
    monitoring_height: int
    full_width: int
    full_height: int
    crop_width: int
    crop_height: int
    alignment_group_id: str
    capture_claimed_at: datetime
    capture_requested_at: datetime
    capture_completed_at: datetime
    qualifying_monitoring_jpeg: bytes
    full_evidence_jpeg: bytes
    crop_jpeg: bytes


@dataclass(frozen=True)
class LocalActivityDiagnosticExportResult:
    status: str

    @property
    def exported(self) -> bool:
        return self.status == "exported"


def export_local_activity_diagnostic(
    artifact: LocalActivityDiagnosticExport,
    *,
    output_directory: Path | None = None,
    environment: Mapping[str, str] | None = None,
) -> LocalActivityDiagnosticExportResult:
    """Write one local inspection bundle only when explicitly enabled.

    The status is intentionally internal.  It is never added to a public API
    response, so a local path or image bytes cannot leak through status data.
    """

    selected_directory = output_directory
    if selected_directory is None:
        configured = (environment if environment is not None else os.environ).get(
            LOCAL_ACTIVITY_DIAGNOSTIC_DIR_ENV, ""
        ).strip()
        if not configured:
            return LocalActivityDiagnosticExportResult("disabled")
        selected_directory = Path(configured)

    validation_failure = _validation_failure(artifact)
    if validation_failure is not None:
        return LocalActivityDiagnosticExportResult(validation_failure)
    if not _is_fresh_tmp_directory(selected_directory):
        return LocalActivityDiagnosticExportResult("output_directory_rejected")

    manifest = _manifest(artifact)
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    ).encode("utf-8") + b"\n"
    if len(manifest_bytes) > MAX_DIAGNOSTIC_MANIFEST_BYTES:
        return LocalActivityDiagnosticExportResult("manifest_too_large")

    created = False
    try:
        os.mkdir(selected_directory, mode=0o700)
        created = True
        _write_restrictive_file(
            selected_directory / QUALIFYING_MONITORING_FILENAME,
            artifact.qualifying_monitoring_jpeg,
        )
        _write_restrictive_file(
            selected_directory / FULL_EVIDENCE_FILENAME,
            artifact.full_evidence_jpeg,
        )
        _write_restrictive_file(selected_directory / CROP_FILENAME, artifact.crop_jpeg)
        _write_restrictive_file(selected_directory / MANIFEST_FILENAME, manifest_bytes)
    except FileExistsError:
        return LocalActivityDiagnosticExportResult("already_exported")
    except OSError:
        if created:
            _remove_partial_export(selected_directory)
        return LocalActivityDiagnosticExportResult("export_failed")
    return LocalActivityDiagnosticExportResult("exported")


def activity_diagnostic_export_from_capture(
    *,
    capture_claim: Mapping[str, Any],
    captured_evidence: Mapping[str, Any],
    qualifying_monitoring_jpeg: bytes,
    qualifying_monitoring_width: int,
    qualifying_monitoring_height: int,
) -> LocalActivityDiagnosticExportResult:
    """Adapt an in-memory capture claim to the strictly safe export format."""

    if capture_claim.get("status") != "succeeded":
        return LocalActivityDiagnosticExportResult("capture_not_succeeded")
    if captured_evidence.get("alignment_status") != "aligned":
        return LocalActivityDiagnosticExportResult("capture_not_exportable")
    try:
        artifact = LocalActivityDiagnosticExport(
            stream_id=_required_token(capture_claim, "stream_id"),
            zone_id=_required_token(capture_claim, "zone_id"),
            activity_session_id=_required_token(capture_claim, "activity_session_id"),
            track_generation_id=_required_token(capture_claim, "track_generation_id"),
            qualifying_frame_identity=_required_token(
                capture_claim, "qualifying_frame_identity"
            ),
            detector_class=_required_token(capture_claim, "detector_class"),
            detector_score=_required_score(capture_claim.get("detector_score")),
            normalized_detector_box=_required_box(
                capture_claim.get("normalized_track_box")
            ),
            normalized_padded_crop_box=_required_box(
                captured_evidence.get("normalized_padded_crop_box")
            ),
            monitoring_width=_required_dimension(
                qualifying_monitoring_width, "monitoring_width"
            ),
            monitoring_height=_required_dimension(
                qualifying_monitoring_height, "monitoring_height"
            ),
            full_width=_required_dimension(captured_evidence.get("full_width"), "full_width"),
            full_height=_required_dimension(
                captured_evidence.get("full_height"), "full_height"
            ),
            crop_width=_required_dimension(captured_evidence.get("crop_width"), "crop_width"),
            crop_height=_required_dimension(
                captured_evidence.get("crop_height"), "crop_height"
            ),
            alignment_group_id=_required_token(capture_claim, "alignment_group_id"),
            capture_claimed_at=_required_datetime(capture_claim.get("claim_timestamp")),
            capture_requested_at=_required_datetime(
                capture_claim.get("request_timestamp")
            ),
            capture_completed_at=_required_datetime(
                capture_claim.get("completion_timestamp")
            ),
            qualifying_monitoring_jpeg=qualifying_monitoring_jpeg,
            full_evidence_jpeg=_required_jpeg(captured_evidence.get("full_image")),
            crop_jpeg=_required_jpeg(captured_evidence.get("crop_image")),
        )
    except (TypeError, ValueError):
        return LocalActivityDiagnosticExportResult("capture_not_exportable")
    return export_local_activity_diagnostic(artifact)


def _validation_failure(artifact: LocalActivityDiagnosticExport) -> str | None:
    if not all(
        _SAFE_LINEAGE_TOKEN.fullmatch(value)
        for value in (
            artifact.stream_id,
            artifact.zone_id,
            artifact.activity_session_id,
            artifact.track_generation_id,
            artifact.qualifying_frame_identity,
            artifact.detector_class,
            artifact.alignment_group_id,
        )
    ):
        return "unsafe_lineage"
    if not math.isfinite(artifact.detector_score) or not 0.0 <= artifact.detector_score <= 1.0:
        return "invalid_score"
    if not _valid_box(artifact.normalized_detector_box) or not _valid_box(
        artifact.normalized_padded_crop_box
    ):
        return "invalid_geometry"
    if not all(
        isinstance(value, int) and 1 <= value <= 20_000
        for value in (
            artifact.monitoring_width,
            artifact.monitoring_height,
            artifact.full_width,
            artifact.full_height,
            artifact.crop_width,
            artifact.crop_height,
        )
    ):
        return "invalid_dimensions"
    images = (
        artifact.qualifying_monitoring_jpeg,
        artifact.full_evidence_jpeg,
        artifact.crop_jpeg,
    )
    if any(not _is_bounded_jpeg(image) for image in images):
        return "invalid_or_oversized_jpeg"
    if sum(len(image) for image in images) > MAX_DIAGNOSTIC_TOTAL_BYTES:
        return "total_size_exceeded"
    if sha1(artifact.qualifying_monitoring_jpeg).hexdigest()[:20] != artifact.qualifying_frame_identity:
        return "qualifying_frame_mismatch"
    return None


def _manifest(artifact: LocalActivityDiagnosticExport) -> dict[str, object]:
    return {
        "activity_session_id": artifact.activity_session_id,
        "alignment_group_id": artifact.alignment_group_id,
        "capture_timestamps": {
            "claim": _isoformat(artifact.capture_claimed_at),
            "completion": _isoformat(artifact.capture_completed_at),
            "request": _isoformat(artifact.capture_requested_at),
        },
        "crop_dimensions": [artifact.crop_width, artifact.crop_height],
        "detector": {
            "class": artifact.detector_class,
            "normalized_box": list(artifact.normalized_detector_box),
            "score": artifact.detector_score,
        },
        "full_image_dimensions": [artifact.full_width, artifact.full_height],
        "image_sha256": {
            CROP_FILENAME: sha256(artifact.crop_jpeg).hexdigest(),
            FULL_EVIDENCE_FILENAME: sha256(artifact.full_evidence_jpeg).hexdigest(),
            QUALIFYING_MONITORING_FILENAME: sha256(
                artifact.qualifying_monitoring_jpeg
            ).hexdigest(),
        },
        "monitoring_dimensions": [
            artifact.monitoring_width,
            artifact.monitoring_height,
        ],
        "normalized_padded_crop_box": list(artifact.normalized_padded_crop_box),
        "qualifying_frame_identity": artifact.qualifying_frame_identity,
        "stream_id": artifact.stream_id,
        "track_generation_id": artifact.track_generation_id,
        "zone_id": artifact.zone_id,
    }


def _is_fresh_tmp_directory(output_directory: Path) -> bool:
    try:
        target = output_directory.resolve(strict=False)
        temporary_root = Path("/tmp").resolve(strict=True)
    except OSError:
        return False
    return target.parent == temporary_root and not target.exists() and not target.is_symlink()


def _write_restrictive_file(path: Path, contents: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _remove_partial_export(output_directory: Path) -> None:
    for filename in (
        QUALIFYING_MONITORING_FILENAME,
        FULL_EVIDENCE_FILENAME,
        CROP_FILENAME,
        MANIFEST_FILENAME,
    ):
        try:
            (output_directory / filename).unlink()
        except FileNotFoundError:
            continue
        except OSError:
            return
    try:
        output_directory.rmdir()
    except OSError:
        pass


def _required_token(values: Mapping[str, Any], key: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not _SAFE_LINEAGE_TOKEN.fullmatch(value):
        raise ValueError(key)
    return value


def _required_score(value: object) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("detector_score")
    score = float(value)
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("detector_score")
    return score


def _required_box(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError("box")
    try:
        box = tuple(float(item) for item in value)
    except (TypeError, ValueError) as error:
        raise ValueError("box") from error
    if not _valid_box(box):
        raise ValueError("box")
    return box


def _required_dimension(value: object, key: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 20_000:
        raise ValueError(key)
    return value


def _required_datetime(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError("timestamp")
    return value


def _required_jpeg(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise ValueError("jpeg")
    return value


def _is_bounded_jpeg(value: bytes) -> bool:
    return (
        bool(value)
        and len(value) <= MAX_DIAGNOSTIC_JPEG_BYTES
        and value.startswith(b"\xff\xd8")
        and value.endswith(b"\xff\xd9")
    )


def _valid_box(box: tuple[float, float, float, float]) -> bool:
    left, top, right, bottom = box
    return (
        all(math.isfinite(value) for value in box)
        and 0.0 <= left < right <= 1.0
        and 0.0 <= top < bottom <= 1.0
    )


def _isoformat(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
