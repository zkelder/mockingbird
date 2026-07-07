"""Local image detector adapter shell.

This module keeps detector runtime concerns below the product model. Detector
outputs are proposal evidence only; repository review/correction logic decides
what becomes dataset truth.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
import os
from pathlib import Path
from typing import Any

LOCAL_IMAGE_DETECTOR_ID = "local_image_detector"
MODEL_PATH_ENV = "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH"
LABELS_PATH_ENV = "MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH"
CONFIDENCE_THRESHOLD_ENV = "MOCKINGBIRD_LOCAL_DETECTOR_CONFIDENCE_THRESHOLD"
LOCAL_DETECTOR_SETUP_HINT = (
    f"Set {MODEL_PATH_ENV} to a local model file. "
    f"Optionally set {LABELS_PATH_ENV} to a newline-delimited labels file. "
    "No model files are bundled or downloaded automatically. "
    "Detector outputs stay as proposal evidence until user review."
)

SUPPORTED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


class LocalDetectorError(RuntimeError):
    pass


class LocalDetectorConfigurationError(LocalDetectorError):
    pass


class LocalDetectorRuntimeUnavailableError(LocalDetectorError):
    pass


class LocalDetectorUnsupportedMediaError(LocalDetectorError):
    pass


class LocalDetectorOutputError(LocalDetectorError):
    pass


@dataclass(frozen=True)
class LocalDetectorStatus:
    status: str
    configured: bool
    runtime_available: bool
    model_path: str | None
    labels_path: str | None
    detail: str


@dataclass(frozen=True)
class LocalDetectorBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class LocalDetectorProposal:
    label: str
    confidence: float
    bbox: LocalDetectorBox | None = None


def get_local_detector_status() -> LocalDetectorStatus:
    model_path = _env_path(MODEL_PATH_ENV)
    labels_path = _env_path(LABELS_PATH_ENV)
    if model_path is None:
        return LocalDetectorStatus(
            status="not_configured",
            configured=False,
            runtime_available=False,
            model_path=None,
            labels_path=str(labels_path) if labels_path else None,
            detail=(
                f"Set {MODEL_PATH_ENV} to a local image detector model file before "
                "running the local detector adapter."
            ),
        )

    if not model_path.exists() or not model_path.is_file():
        return LocalDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail="Configured local detector model file was not found.",
        )

    missing = _missing_runtime_modules()
    if missing:
        return LocalDetectorStatus(
            status="unavailable",
            configured=True,
            runtime_available=False,
            model_path=str(model_path),
            labels_path=str(labels_path) if labels_path else None,
            detail=(
                "Local detector runtime is missing optional dependencies: "
                f"{', '.join(missing)}."
            ),
        )

    return LocalDetectorStatus(
        status="available",
        configured=True,
        runtime_available=True,
        model_path=str(model_path),
        labels_path=str(labels_path) if labels_path else None,
        detail=(
            "Local image detector is configured. Outputs remain proposal evidence "
            "until reviewed and corrected."
        ),
    )


def run_local_image_detector(
    *,
    local_path: str,
    content_type: str,
    model_path: str | None = None,
    labels_path: str | None = None,
) -> list[LocalDetectorProposal]:
    if content_type not in SUPPORTED_IMAGE_CONTENT_TYPES:
        raise LocalDetectorUnsupportedMediaError("unsupported_media_type")

    status = get_local_detector_status()
    if not status.configured:
        raise LocalDetectorConfigurationError(status.detail)
    if status.status != "available" or not status.runtime_available:
        raise LocalDetectorRuntimeUnavailableError(status.detail)

    resolved_model_path = Path(model_path or status.model_path or "")
    resolved_labels_path = Path(labels_path or status.labels_path or "") if labels_path or status.labels_path else None
    image_path = Path(local_path)
    if not image_path.exists() or not image_path.is_file():
        raise LocalDetectorUnsupportedMediaError("missing_media_file")

    return _run_onnx_image_detector(
        image_path=image_path,
        model_path=resolved_model_path,
        labels_path=resolved_labels_path,
    )


def _run_onnx_image_detector(
    *,
    image_path: Path,
    model_path: Path,
    labels_path: Path | None,
) -> list[LocalDetectorProposal]:
    try:
        import numpy as np
        import onnxruntime as ort
        from PIL import Image
    except ImportError as error:
        raise LocalDetectorRuntimeUnavailableError(
            "Local detector runtime requires optional Pillow, numpy, and onnxruntime packages."
        ) from error

    labels = _load_labels(labels_path)
    threshold = _confidence_threshold()

    try:
        session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        input_meta = session.get_inputs()[0]
        input_name = input_meta.name
        input_shape = list(input_meta.shape)
        image_size = _input_image_size(input_shape)
        with Image.open(image_path) as image:
            width, height = image.size
            prepared = image.convert("RGB").resize((image_size, image_size))
        array = np.asarray(prepared, dtype=np.float32) / 255.0
        array = np.transpose(array, (2, 0, 1))[None, :, :, :]
        outputs = session.run(None, {input_name: array})
    except LocalDetectorError:
        raise
    except Exception as error:  # pragma: no cover - depends on user-provided local model.
        raise LocalDetectorOutputError("local_detector_failed") from error

    return _parse_detector_outputs(outputs, labels=labels, threshold=threshold, image_width=width, image_height=height)


def _parse_detector_outputs(
    outputs: list[Any],
    *,
    labels: list[str],
    threshold: float,
    image_width: int,
    image_height: int,
) -> list[LocalDetectorProposal]:
    try:
        import numpy as np
    except ImportError as error:
        raise LocalDetectorRuntimeUnavailableError(
            "Local detector runtime requires optional numpy package."
        ) from error

    if not outputs:
        return []

    output = np.asarray(outputs[0])
    output = np.squeeze(output)
    if output.ndim != 2:
        raise LocalDetectorOutputError("unsupported_detector_output")
    if output.shape[0] < output.shape[1] and output.shape[0] in {5, 6, 7, 84, 85}:
        output = output.T
    if output.shape[1] < 6:
        raise LocalDetectorOutputError("unsupported_detector_output")

    proposals: list[LocalDetectorProposal] = []
    for row in output:
        label_index, confidence = _row_label_and_confidence(row)
        if confidence < threshold:
            continue
        label = labels[label_index] if 0 <= label_index < len(labels) else "unknown_animal"
        box = _row_to_box(row, image_width=image_width, image_height=image_height)
        proposals.append(
            LocalDetectorProposal(
                label=_normalize_detector_label(label),
                confidence=max(0.0, min(1.0, float(confidence))),
                bbox=box,
            )
        )

    return sorted(proposals, key=lambda proposal: proposal.confidence, reverse=True)[:20]


def _row_label_and_confidence(row: Any) -> tuple[int, float]:
    values = list(row)
    if len(values) > 6:
        class_scores = values[5:]
        best_index = max(range(len(class_scores)), key=lambda index: float(class_scores[index]))
        objectness = float(values[4])
        score = float(class_scores[best_index])
        return best_index, objectness * score if 0 <= objectness <= 1 else score
    return int(float(values[5])), float(values[4])


def _row_to_box(row: Any, *, image_width: int, image_height: int) -> LocalDetectorBox | None:
    x1, y1, x2_or_width, y2_or_height = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
    if max(abs(x1), abs(y1), abs(x2_or_width), abs(y2_or_height)) <= 1.5:
        x = max(0.0, min(1.0, x1))
        y = max(0.0, min(1.0, y1))
        width = max(0.001, min(1.0 - x, x2_or_width if x2_or_width <= 1 else 1.0))
        height = max(0.001, min(1.0 - y, y2_or_height if y2_or_height <= 1 else 1.0))
        return LocalDetectorBox(x=x, y=y, width=width, height=height)

    x = max(0.0, min(1.0, x1 / max(image_width, 1)))
    y = max(0.0, min(1.0, y1 / max(image_height, 1)))
    if x2_or_width > x1 and y2_or_height > y1:
        width = (x2_or_width - x1) / max(image_width, 1)
        height = (y2_or_height - y1) / max(image_height, 1)
    else:
        width = x2_or_width / max(image_width, 1)
        height = y2_or_height / max(image_height, 1)
    return LocalDetectorBox(
        x=x,
        y=y,
        width=max(0.001, min(1.0 - x, width)),
        height=max(0.001, min(1.0 - y, height)),
    )


def _missing_runtime_modules() -> list[str]:
    missing: list[str] = []
    for module_name in ("PIL", "numpy", "onnxruntime"):
        if importlib.util.find_spec(module_name) is None:
            missing.append(module_name)
    return missing


def _input_image_size(input_shape: list[Any]) -> int:
    for value in reversed(input_shape):
        if isinstance(value, int) and value > 0:
            return int(value)
    return 640


def _load_labels(labels_path: Path | None) -> list[str]:
    if labels_path is None or not labels_path.exists() or not labels_path.is_file():
        return ["unknown_animal"]
    labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines()]
    return [_normalize_detector_label(label) for label in labels if label.strip()] or ["unknown_animal"]


def _confidence_threshold() -> float:
    raw_value = os.environ.get(CONFIDENCE_THRESHOLD_ENV, "0.5")
    try:
        return max(0.0, min(1.0, float(raw_value)))
    except ValueError:
        return 0.5


def _normalize_detector_label(label: str) -> str:
    normalized = label.strip().lower().replace("-", "_")
    normalized = "_".join(part for part in normalized.split() if part)
    return normalized or "unknown_animal"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return None
    return Path(value).expanduser()
