"""MegaDetector-family adapter wrapper.

This module records MegaDetector runtime state without importing heavy model
dependencies. Detector outputs remain proposal evidence below product truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module, util
import os
from pathlib import Path
from types import ModuleType

MEGADETECTOR_ADAPTER_ID = "megadetector"
MEGADETECTOR_RUNTIME_EXTRA = "detector-megadetector"
MEGADETECTOR_RUNTIME_PACKAGE = "PytorchWildlife"
MEGADETECTOR_MODEL_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH"
MEGADETECTOR_LABELS_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_LABELS_PATH"
MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV = "MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD"
MEGADETECTOR_SETUP_HINT = (
    f"Install optional {MEGADETECTOR_RUNTIME_EXTRA} runtime only when needed. "
    f"Set {MEGADETECTOR_MODEL_PATH_ENV} to a local MegaDetector-family model file. "
    f"Optionally set {MEGADETECTOR_LABELS_PATH_ENV} to local labels. "
    "No model files are bundled or downloaded automatically. "
    "MegaDetector outputs animal/person/vehicle proposal evidence only."
)

SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MEGADETECTOR_SUPPORTED_LABELS = ["animal", "person", "vehicle", "unknown_animal"]


class MegaDetectorError(RuntimeError):
    pass


class MegaDetectorConfigurationError(MegaDetectorError):
    pass


class MegaDetectorModelFileError(MegaDetectorConfigurationError):
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
class MegaDetectorRuntimeStatus:
    available: bool
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
                "model file before running the adapter. The optional "
                f"{MEGADETECTOR_RUNTIME_EXTRA} runtime is not required for app startup."
            ),
        )

    if not model_path.exists() or not model_path.is_file():
        return MegaDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail=(
                "Configured MegaDetector model file was not found. No model files "
                "are bundled or downloaded automatically."
            ),
        )

    runtime_status = get_megadetector_runtime_status()
    if not runtime_status.available:
        return MegaDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail=runtime_status.detail,
        )

    return MegaDetectorStatus(
        status="available",
        configured=True,
        runtime_available=True,
        model_path=str(model_path),
        labels_path=str(labels_path) if labels_path else None,
        detail=(
            "Optional MegaDetector runtime dependency is importable and the local "
            "model path exists. Runs create proposal evidence only."
        ),
    )


def get_megadetector_runtime_status() -> MegaDetectorRuntimeStatus:
    try:
        runtime_spec = util.find_spec(MEGADETECTOR_RUNTIME_PACKAGE)
    except (ImportError, AttributeError, ValueError):
        return MegaDetectorRuntimeStatus(
            available=False,
            detail=(
                "Optional MegaDetector runtime dependency could not be inspected. "
                f"Install the {MEGADETECTOR_RUNTIME_EXTRA} extra only when needed."
            ),
        )

    if runtime_spec is None:
        return MegaDetectorRuntimeStatus(
            available=False,
            detail=(
                "Optional MegaDetector runtime dependency is not installed. "
                f"Install the {MEGADETECTOR_RUNTIME_EXTRA} extra only when ready "
                "to run local MegaDetector proposal evidence."
            ),
        )

    return MegaDetectorRuntimeStatus(
        available=True,
        detail="Optional MegaDetector runtime dependency is importable.",
    )


def run_megadetector_on_image(
    *,
    local_path: str,
    content_type: str,
    zone_context: str | None = None,
) -> list[MegaDetectorProposal]:
    if content_type not in SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES:
        raise MegaDetectorUnsupportedMediaError("unsupported_media_type")

    status = get_megadetector_status()
    if not status.configured:
        raise MegaDetectorConfigurationError(status.detail)
    if status.model_path is not None and not Path(status.model_path).is_file():
        raise MegaDetectorModelFileError(status.detail)
    if status.status != "available" or not status.runtime_available:
        raise MegaDetectorRuntimeUnavailableError(status.detail)

    image_path = Path(local_path)
    if not image_path.exists() or not image_path.is_file():
        raise MegaDetectorUnsupportedMediaError("missing_media_file")

    if status.model_path is None:
        raise MegaDetectorConfigurationError(status.detail)

    return _execute_megadetector_runtime(
        media_local_path=str(image_path),
        model_path=status.model_path,
        labels_path=status.labels_path,
        confidence_threshold=_confidence_threshold(),
        zone_context=zone_context,
    )


def _load_megadetector_runtime() -> ModuleType:
    try:
        return import_module(MEGADETECTOR_RUNTIME_PACKAGE)
    except ImportError as error:
        raise MegaDetectorRuntimeUnavailableError(
            "Optional MegaDetector runtime dependency is not installed. "
            f"Install the {MEGADETECTOR_RUNTIME_EXTRA} extra only when ready."
        ) from error


def _execute_megadetector_runtime(
    *,
    media_local_path: str,
    model_path: str,
    labels_path: str | None,
    confidence_threshold: float | None,
    zone_context: str | None,
) -> list[MegaDetectorProposal]:
    _load_megadetector_runtime()
    raise MegaDetectorRuntimeUnavailableError(
        "MegaDetector runtime dependency boundary is available, but production "
        "inference is not implemented in this phase."
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


def _confidence_threshold() -> float | None:
    value = os.environ.get(MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV)
    if value is None or not value.strip():
        return None

    try:
        threshold = float(value)
    except ValueError as error:
        raise MegaDetectorConfigurationError(
            f"{MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV} must be a number between 0 and 1."
        ) from error

    if threshold < 0 or threshold > 1:
        raise MegaDetectorConfigurationError(
            f"{MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV} must be between 0 and 1."
        )
    return threshold
