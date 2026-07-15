"""Optional local MegaDetector adapter.

The core app never imports the heavy runtime at startup and never downloads a
model. An explicit Review Queue action can run one local MDv5 image and records
the result as proposal evidence below user-reviewed product truth.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module, util
import math
import os
from pathlib import Path
from types import ModuleType
from typing import Any

MEGADETECTOR_ADAPTER_ID = "megadetector"
MEGADETECTOR_RUNTIME_EXTRA = "detector-megadetector"
MEGADETECTOR_RUNTIME_PACKAGE = "megadetector"
MEGADETECTOR_MODEL_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_MODEL_PATH"
MEGADETECTOR_LABELS_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_LABELS_PATH"
MEGADETECTOR_CONFIDENCE_THRESHOLD_ENV = "MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD"
MEGADETECTOR_RUNTIME_CACHE_PATH_ENV = "MOCKINGBIRD_MEGADETECTOR_RUNTIME_CACHE_PATH"
MEGADETECTOR_DEFAULT_RUNTIME_CACHE_PATH = "data/runtime/megadetector"
MEGADETECTOR_DEFAULT_CONFIDENCE_THRESHOLD = 0.1
MEGADETECTOR_MAX_PROPOSALS = 20
MEGADETECTOR_SETUP_HINT = (
    f"Install optional {MEGADETECTOR_RUNTIME_EXTRA} support only when needed. "
    f"Set {MEGADETECTOR_MODEL_PATH_ENV} to an existing local MDv5 .pt model file. "
    "No model files are bundled or downloaded automatically. "
    "MegaDetector outputs animal/person/vehicle proposal evidence only."
)

SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MEGADETECTOR_SUPPORTED_LABELS = ["animal", "person", "vehicle", "unknown_animal"]
MEGADETECTOR_CATEGORY_LABELS = {
    "1": "animal",
    "2": "person",
    "3": "vehicle",
}


class MegaDetectorError(RuntimeError):
    pass


class MegaDetectorConfigurationError(MegaDetectorError):
    pass


class MegaDetectorModelFileError(MegaDetectorConfigurationError):
    pass


class MegaDetectorModelFormatError(MegaDetectorConfigurationError):
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

    if model_path.suffix.lower() != ".pt":
        return MegaDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail=(
                "The first local MegaDetector runtime supports an explicit MDv5 "
                ".pt model file only. Model aliases and automatic downloads are not "
                "accepted."
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
    focus_box: MegaDetectorBox | None = None,
) -> list[MegaDetectorProposal]:
    if content_type not in SUPPORTED_MEGADETECTOR_IMAGE_CONTENT_TYPES:
        raise MegaDetectorUnsupportedMediaError("unsupported_media_type")

    status = get_megadetector_status()
    if not status.configured:
        raise MegaDetectorConfigurationError(status.detail)
    if status.model_path is not None and not Path(status.model_path).is_file():
        raise MegaDetectorModelFileError(status.detail)
    if status.model_path is not None and Path(status.model_path).suffix.lower() != ".pt":
        raise MegaDetectorModelFormatError(status.detail)
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
        focus_box=focus_box,
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
    focus_box: MegaDetectorBox | None = None,
) -> list[MegaDetectorProposal]:
    _prepare_megadetector_runtime_environment()
    _load_megadetector_runtime()
    try:
        resolved_model_path = Path(model_path).resolve(strict=True)
    except OSError as error:
        raise MegaDetectorModelFileError(
            "Configured MegaDetector model file was not found."
        ) from error
    if resolved_model_path.suffix.lower() != ".pt":
        raise MegaDetectorModelFormatError(
            "MegaDetector requires an explicit local MDv5 .pt model file."
        )

    # MegaDetector's animal/person/vehicle category map is fixed for this
    # adapter. Labels and zone context stay in the product-level run contract,
    # but neither changes raw model inference.
    del labels_path, zone_context
    threshold = (
        MEGADETECTOR_DEFAULT_CONFIDENCE_THRESHOLD
        if confidence_threshold is None
        else confidence_threshold
    )

    try:
        run_detector = import_module("megadetector.detection.run_detector")
        visualization_utils = import_module(
            "megadetector.visualization.visualization_utils"
        )
        detector = run_detector.load_detector(
            str(resolved_model_path),
            force_model_download=False,
        )
        image = visualization_utils.load_image(media_local_path)
        inference_image, applied_focus_box = _focused_image(image, focus_box)
        output = detector.generate_detections_one_image(
            inference_image,
            image_id=media_local_path,
            detection_threshold=threshold,
        )
    except MegaDetectorError:
        raise
    except Exception as error:  # pragma: no cover - depends on the optional runtime.
        raise MegaDetectorOutputError("megadetector_failed") from error

    proposals = _parse_megadetector_output(output, threshold=threshold)
    return _remap_focused_proposals(proposals, applied_focus_box)


def _prepare_megadetector_runtime_environment() -> Path:
    """Keep optional runtime caches local and disable package auto-install hooks."""

    configured_path = os.environ.get(
        MEGADETECTOR_RUNTIME_CACHE_PATH_ENV,
        MEGADETECTOR_DEFAULT_RUNTIME_CACHE_PATH,
    )
    cache_root = Path(configured_path).expanduser().resolve()
    yolo_cache = cache_root / "yolov5"
    matplotlib_cache = cache_root / "matplotlib"
    try:
        yolo_cache.mkdir(parents=True, exist_ok=True)
        matplotlib_cache.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise MegaDetectorRuntimeUnavailableError(
            "MegaDetector could not prepare its local runtime cache."
        ) from error

    os.environ.setdefault("YOLOV5_CONFIG_DIR", str(yolo_cache))
    os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
    os.environ.setdefault("YOLOv5_AUTOINSTALL", "False")
    return cache_root


def _focused_image(
    image: Any,
    focus_box: MegaDetectorBox | None,
) -> tuple[Any, MegaDetectorBox | None]:
    if focus_box is None:
        return image, None
    if not _valid_box(focus_box):
        raise MegaDetectorOutputError("unsupported_detector_output")

    size = getattr(image, "size", None)
    if (
        not isinstance(size, Sequence)
        or isinstance(size, (str, bytes))
        or len(size) != 2
    ):
        raise MegaDetectorOutputError("unsupported_detector_output")
    try:
        image_width = int(size[0])
        image_height = int(size[1])
    except (TypeError, ValueError) as error:
        raise MegaDetectorOutputError("unsupported_detector_output") from error
    if image_width < 1 or image_height < 1 or not hasattr(image, "crop"):
        raise MegaDetectorOutputError("unsupported_detector_output")

    left = max(0, min(image_width - 1, math.floor(focus_box.x * image_width)))
    top = max(0, min(image_height - 1, math.floor(focus_box.y * image_height)))
    right = max(
        left + 1,
        min(image_width, math.ceil((focus_box.x + focus_box.width) * image_width)),
    )
    bottom = max(
        top + 1,
        min(image_height, math.ceil((focus_box.y + focus_box.height) * image_height)),
    )
    applied_box = MegaDetectorBox(
        x=left / image_width,
        y=top / image_height,
        width=(right - left) / image_width,
        height=(bottom - top) / image_height,
    )
    return image.crop((left, top, right, bottom)), applied_box


def _remap_focused_proposals(
    proposals: list[MegaDetectorProposal],
    focus_box: MegaDetectorBox | None,
) -> list[MegaDetectorProposal]:
    if focus_box is None:
        return proposals

    remapped: list[MegaDetectorProposal] = []
    for proposal in proposals:
        if proposal.bbox is None:
            remapped.append(proposal)
            continue
        remapped.append(
            MegaDetectorProposal(
                label=proposal.label,
                confidence=proposal.confidence,
                bbox=MegaDetectorBox(
                    x=focus_box.x + proposal.bbox.x * focus_box.width,
                    y=focus_box.y + proposal.bbox.y * focus_box.height,
                    width=proposal.bbox.width * focus_box.width,
                    height=proposal.bbox.height * focus_box.height,
                ),
            )
        )
    return remapped


def _valid_box(box: MegaDetectorBox) -> bool:
    return (
        all(
            math.isfinite(value) and 0 <= value <= 1
            for value in (box.x, box.y, box.width, box.height)
        )
        and box.width > 0
        and box.height > 0
        and box.x + box.width <= 1.000001
        and box.y + box.height <= 1.000001
    )


def _parse_megadetector_output(
    output: Any,
    *,
    threshold: float,
) -> list[MegaDetectorProposal]:
    if not isinstance(output, Mapping):
        raise MegaDetectorOutputError("unsupported_detector_output")
    if output.get("failure"):
        raise MegaDetectorOutputError("megadetector_failed")

    detections = output.get("detections")
    if detections is None:
        return []
    if not isinstance(detections, Sequence) or isinstance(detections, (str, bytes)):
        raise MegaDetectorOutputError("unsupported_detector_output")

    proposals: list[MegaDetectorProposal] = []
    for detection in detections:
        proposal = _proposal_from_detection(detection, threshold=threshold)
        if proposal is not None:
            proposals.append(proposal)

    return sorted(
        proposals,
        key=lambda proposal: proposal.confidence,
        reverse=True,
    )[:MEGADETECTOR_MAX_PROPOSALS]


def _proposal_from_detection(
    detection: Any,
    *,
    threshold: float,
) -> MegaDetectorProposal | None:
    if not isinstance(detection, Mapping):
        raise MegaDetectorOutputError("unsupported_detector_output")

    label = MEGADETECTOR_CATEGORY_LABELS.get(str(detection.get("category")))
    if label is None:
        # Unknown runtime categories are ignored instead of being mislabeled as
        # animals and polluting the user's review queue.
        return None

    confidence = _bounded_number(detection.get("conf"))
    if confidence is None:
        raise MegaDetectorOutputError("unsupported_detector_output")
    if confidence < threshold:
        return None

    bbox_value = detection.get("bbox")
    bbox = None if bbox_value is None else _normalized_box(bbox_value)
    return MegaDetectorProposal(label=label, confidence=confidence, bbox=bbox)


def _normalized_box(value: Any) -> MegaDetectorBox:
    if (
        not isinstance(value, Sequence)
        or isinstance(value, (str, bytes))
        or len(value) != 4
    ):
        raise MegaDetectorOutputError("unsupported_detector_output")

    numbers = [_bounded_number(item) for item in value]
    if any(number is None for number in numbers):
        raise MegaDetectorOutputError("unsupported_detector_output")
    x, y, width, height = (float(number) for number in numbers)
    if width <= 0 or height <= 0 or x + width > 1.000001 or y + height > 1.000001:
        raise MegaDetectorOutputError("unsupported_detector_output")
    return MegaDetectorBox(x=x, y=y, width=width, height=height)


def _bounded_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number < 0 or number > 1:
        return None
    return number


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
