"""Safe, filesystem-only I/O for the detector-calibration benchmark.

Mirrors `mockingbird.observation.replay_io`'s safety conventions (contained
paths, no symlinks, atomic report writes) for the separate reviewed
calibration-manifest schema. This module never imports the product
repository and never opens the product database.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.web_app import find_workspace_root
from mockingbird.observation.detector_benchmark import (
    MANIFEST_VERSION,
    CalibrationFrame,
    CalibrationManifest,
    DetectorBenchmarkError,
    ReviewedBox,
    StaticStructure,
)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_STRING_LENGTH = 2048
MAX_FRAMES = 5_000


def load_calibration_manifest(frames_directory: Path, manifest_path: Path) -> tuple[CalibrationManifest, Path]:
    """Load and validate the reviewed manifest; returns the manifest plus the
    resolved, symlink-free frames root every image path was checked against."""

    root = _safe_directory(frames_directory)
    document = _load_json(manifest_path)
    version = document.get("version", document.get("schema_version"))
    if version != MANIFEST_VERSION:
        raise DetectorBenchmarkError("unsupported_manifest_version")
    cohort_id = _require_string(document, "cohort_id")
    annotation_policy = _require_string(document, "annotation_policy")
    frame_documents = _require_list(document, "frames")
    if len(frame_documents) > MAX_FRAMES:
        raise DetectorBenchmarkError("frame_limit")

    frames: list[CalibrationFrame] = []
    seen_ids: set[str] = set()
    for item in frame_documents:
        if not isinstance(item, dict):
            raise DetectorBenchmarkError("invalid_frame_manifest")
        frame_id = _require_string(item, "frame_id")
        if frame_id in seen_ids:
            raise DetectorBenchmarkError("duplicate_frame_id")
        seen_ids.add(frame_id)
        relative = _require_string(item, "image")
        resolved = _safe_frame_path(root, relative)
        width, height = _verify_image(resolved)
        declared_width, declared_height = item.get("width"), item.get("height")
        if declared_width is not None and declared_width != width:
            raise DetectorBenchmarkError("frame_dimensions_mismatch")
        if declared_height is not None and declared_height != height:
            raise DetectorBenchmarkError("frame_dimensions_mismatch")
        content_hash = _file_hash(resolved)
        declared_hash = item.get("content_hash")
        if declared_hash is not None and declared_hash != content_hash:
            raise DetectorBenchmarkError("frame_hash_mismatch")
        frames.append(CalibrationFrame(
            frame_id=frame_id,
            image_path=relative,
            content_hash=content_hash,
            width=width,
            height=height,
            animal_present=_require_choice(item, "animal_present", {"yes", "no", "ambiguous"}),
            boxes=tuple(_reviewed_box(box) for box in _optional_list(item, "boxes")),
            scorable=_optional_bool(item, "scorable", default=True),
            occlusion=_optional_string(item, "occlusion"),
            blur=_optional_string(item, "blur"),
            clipped=_optional_nullable_bool(item, "clipped"),
            distance=_optional_string(item, "distance"),
            privacy_ignore_regions=tuple(_box(value) for value in _optional_list(item, "privacy_ignore_regions")),
            scene_group=_require_string(item, "scene_group"),
            sequence_id=_optional_string(item, "sequence_id"),
            sequence_order=_optional_int(item, "sequence_order"),
            source_offset_ms=_optional_int(item, "source_offset_ms"),
            provenance=_optional_string(item, "provenance") or "",
            reviewer_note=_optional_string(item, "reviewer_note") or "",
        ))

    structures_document = document.get("scene_static_structures", {})
    if not isinstance(structures_document, dict):
        raise DetectorBenchmarkError("invalid_scene_static_structures")
    structures = {
        scene: tuple(_static_structure(entry) for entry in entries)
        for scene, entries in structures_document.items()
    }

    manifest = CalibrationManifest(
        version=version, cohort_id=cohort_id, annotation_policy=annotation_policy,
        frames=tuple(frames), scene_static_structures=structures,
    )
    return manifest, root


def write_detector_benchmark_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    directory = _safe_output_directory(output_directory)
    output = directory / "detector-benchmark-report.json"
    payload = {**semantic, "execution": dict(sorted(execution.items()))}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".detector-benchmark-report.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(serialized)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, output)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
    return output


def _safe_directory(value: Path) -> Path:
    if value.is_symlink() or not value.is_dir():
        raise DetectorBenchmarkError("unsafe_frames_directory")
    return value.resolve(strict=True)


def _safe_frame_path(root: Path, relative: str) -> Path:
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or item.suffix.lower() not in _IMAGE_SUFFIXES:
        raise DetectorBenchmarkError("unsafe_frame_path")
    candidate = root / item
    if candidate.is_symlink() or not candidate.is_file():
        raise DetectorBenchmarkError("unsafe_frame_path")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise DetectorBenchmarkError("unsafe_frame_path")
    return resolved


def _safe_output_directory(value: Path) -> Path:
    directory = value.expanduser()
    workspace = find_workspace_root()
    parent = directory.parent.resolve(strict=True) if not directory.exists() else directory.resolve(strict=True).parent
    resolved = parent / directory.name
    if directory.is_symlink() or directory == Path(".") or directory.suffix:
        raise DetectorBenchmarkError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise DetectorBenchmarkError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise DetectorBenchmarkError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise DetectorBenchmarkError("unsafe_manifest_path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DetectorBenchmarkError("invalid_manifest_json") from error
    if not isinstance(value, dict):
        raise DetectorBenchmarkError("invalid_manifest_json")
    return value


def _verify_image(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            dimensions = image.size
            image.verify()
            return dimensions
    except Exception as error:
        raise DetectorBenchmarkError("undecodable_frame") from error


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _box(value: object) -> tuple[float, float, float, float]:
    if (
        not isinstance(value, list) or len(value) != 4
        or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
    ):
        raise DetectorBenchmarkError("invalid_box")
    return tuple(float(item) for item in value)  # type: ignore[return-value]


def _reviewed_box(value: object) -> ReviewedBox:
    if not isinstance(value, dict):
        raise DetectorBenchmarkError("invalid_reviewed_box")
    return ReviewedBox(box=_box(value.get("box")), broad_class=str(value.get("broad_class", "animal")))


def _static_structure(value: object) -> StaticStructure:
    if not isinstance(value, dict):
        raise DetectorBenchmarkError("invalid_static_structure")
    return StaticStructure(
        label=_require_string(value, "label"),
        box=_box(value.get("box")),
        note=_optional_string(value, "note"),
    )


def _require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result or len(result) > MAX_STRING_LENGTH:
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _require_choice(value: dict[str, Any], key: str, choices: set[str]) -> str:
    result = _require_string(value, key)
    if result not in choices:
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, str) or len(result) > MAX_STRING_LENGTH):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _optional_bool(value: dict[str, Any], key: str, *, default: bool) -> bool:
    result = value.get(key, default)
    if not isinstance(result, bool):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _optional_nullable_bool(value: dict[str, Any], key: str) -> bool | None:
    result = value.get(key)
    if result is not None and not isinstance(result, bool):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _optional_int(value: dict[str, Any], key: str) -> int | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, int) or isinstance(result, bool)):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _require_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key)
    if not isinstance(result, list):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result


def _optional_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key, [])
    if not isinstance(result, list):
        raise DetectorBenchmarkError(f"invalid_{key}")
    return result
