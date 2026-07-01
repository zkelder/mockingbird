"""MegaDetector-family adapter wrapper.

This module records MegaDetector runtime state without importing heavy model
dependencies. Detector outputs remain proposal evidence below product truth.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

MEGADETECTOR_ADAPTER_ID = "megadetector"
MEGADETECTOR_MODEL_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH"
MEGADETECTOR_LABELS_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_LABELS_PATH"
MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV = "MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD"
MEGADETECTOR_SETUP_HINT = (
    f"Set {MEGADETECTOR_MODEL_PATH_ENV} to a local MegaDetector-family model file. "
    f"Optionally set {MEGADETECTOR_LABELS_PATH_ENV} to local labels. "
    "MegaDetector outputs animal/person/vehicle proposal evidence only."
)

SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MEGADETECTOR_SUPPORTED_LABELS = ["animal", "person", "vehicle", "unknown_animal"]


class MegaDetectorError(RuntimeError):
    pass


class MegaDetectorConfigurationError(MegaDetectorError):
    pass


class MegaDetectorRuntimeUnavailableError(MegaDetectorError):
    pass


class MegaDetectorUnsupportedMediaError(MegaDetectorError):
    pass


class MegaDetectorOutputError(MegaDetectorError):
    pass


@dataclass(frozen=True)
class MegaDetectorStatus:
    status: str
    configured: bool
    runtime_available: bool
    model_path: str | None
    labels_path: str | None
    detail: str


@dataclass(frozen=True)
class MegaDetectorBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class MegaDetectorProposal:
    label: str
    confidence: float
    bbox: MegaDetectorBox | None = None


def get_megadetector_status() -> MegaDetectorStatus:
    model_path = _env_path(MEGADETECTOR_MODEL_PATH_ENV)
    labels_path = _env_path(MEGADETECTOR_LABELS_PATH_ENV)
    if model_path is None:
        return MegaDetectorStatus(
            status="not_configured",
            configured=False,
            runtime_available=False,
            model_path=None,
            labels_path=str(labels_path) if labels_path else None,
            detail=(
                f"Set {MEGADETECTOR_MODEL_PATH_ENV} to a local MegaDetector-family "
                "model file before running the adapter."
            ),
        )

    if not model_path.exists() or not model_path.is_file():
        return MegaDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail="Configured MegaDetector model file was not found.",
        )

    return MegaDetectorStatus(
        status="unavailable",
        configured=True,
        runtime_available=False,
        model_path=str(model_path),
        labels_path=str(labels_path) if labels_path else None,
        detail=(
            "MegaDetector runtime integration is not installed in this wrapper phase. "
            "No heavy model dependency has been added."
        ),
    )


def run_megadetector_on_image(
    *,
    local_path: str,
    content_type: str,
) -> list[MegaDetectorProposal]:
    if content_type not in SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES:
        raise MegaDetectorUnsupportedMediaError("unsupported_media_type")

    status = get_megadetector_status()
    if not status.configured:
        raise MegaDetectorConfigurationError(status.detail)
    if status.status != "available" or not status.runtime_available:
        raise MegaDetectorRuntimeUnavailableError(status.detail)

    image_path = Path(local_path)
    if not image_path.exists() or not image_path.is_file():
        raise MegaDetectorUnsupportedMediaError("missing_media_file")

    raise MegaDetectorRuntimeUnavailableError(
        "MegaDetector runtime integration is unavailable in this wrapper phase."
    )


def normalize_megadetector_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_")
    normalized = "_".join(part for part in normalized.split() if part)
    if normalized == "animal":
        return "unknown_animal"
    if normalized in {"person", "vehicle", "unknown_animal"}:
        return normalized
    return "unknown_animal"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()
