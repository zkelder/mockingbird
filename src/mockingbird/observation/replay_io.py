"""Safe, filesystem-only I/O for ordered-frame replay benchmarks."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.web_app import find_workspace_root
from mockingbird.observation.replay import (
    FRAME_IDENTITY_VERSION, MATCHER_VERSION, REPORT_SCHEMA_VERSION,
    BenchmarkManifest, ExpectedAppearance, ExpectedDetection, ExpectedEvidence, ExpectedVisit, ReplayFrame,
    ReplayInput, ReplayReport, ReplayValidationError, semantic_fingerprint,
)

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_STRING_LENGTH = 512


@dataclass(frozen=True)
class ReplayBundle:
    replay: ReplayInput
    manifest: BenchmarkManifest
    thresholds: dict[str, float]


def load_replay_bundle(frames_directory: Path, manifest_path: Path) -> ReplayBundle:
    root = _safe_directory(frames_directory)
    document = _load_json(manifest_path)
    version = _require_int(document, "version", minimum=1)
    width = _require_int(document, "width", minimum=1)
    height = _require_int(document, "height", minimum=1)
    frame_documents = _require_list(document, "frames")
    frames: list[ReplayFrame] = []
    seen_paths: set[str] = set()
    for index, item in enumerate(frame_documents):
        if not isinstance(item, dict):
            raise ReplayValidationError("invalid_frame_manifest")
        relative = _require_string(item, "path")
        if relative in seen_paths:
            raise ReplayValidationError("duplicate_frame_id")
        seen_paths.add(relative)
        candidate = _safe_frame_path(root, relative)
        if _verify_image(candidate) != (width, height):
            raise ReplayValidationError("frame_dimensions_mismatch")
        content_hash = _file_hash(candidate)
        declared_hash = item.get("content_hash")
        if declared_hash is not None and declared_hash != content_hash:
            raise ReplayValidationError("frame_hash_mismatch")
        frames.append(ReplayFrame(
            index,
            _require_int(item, "source_offset_ms", minimum=0),
            content_hash,
            str(candidate),
            _excluded_regions(item.get("analysis_excluded_regions", [])),
        ))
    replay = ReplayInput(_require_string(document, "input_id"), _require_string(document, "stream_id"),
                         width, height, _require_number(document, "nominal_fps", minimum=0.000001), tuple(frames))
    manifest = BenchmarkManifest(
        version, _require_string(document, "benchmark_id"), _require_string(document, "input_fingerprint"),
        tuple(_appearance(item) for item in _require_list(document, "appearances")),
        tuple(_visit(item) for item in _require_list(document, "visits")),
        tuple(_detection(item) for item in _optional_list(document, "detections")),
        tuple(_evidence(item) for item in _optional_list(document, "evidence")),
    )
    manifest.validate(replay)
    return ReplayBundle(replay, manifest, _thresholds(document.get("thresholds", {})))


def write_replay_report(output_directory: Path, report: ReplayReport, *, replay: ReplayInput,
                        manifest: BenchmarkManifest, provider: dict[str, Any],
                        limitations: tuple[str, ...], execution: dict[str, Any]) -> Path:
    directory = _safe_output_directory(output_directory)
    output = directory / "replay-report.json"
    semantic = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "benchmark": {"id": manifest.benchmark_id, "manifest_version": manifest.version,
                      "manifest_fingerprint": manifest.fingerprint},
        "replay": {"input_fingerprint": replay.fingerprint, "frame_identity_version": FRAME_IDENTITY_VERSION,
                   "settings": {"stream_id": replay.stream_id, "width": replay.width, "height": replay.height,
                                "nominal_fps": replay.nominal_fps, "frame_count": len(replay.frames)}},
        "matcher_version": MATCHER_VERSION,
        "provider": provider,
        "limitations": sorted(limitations),
        "expected_visits": [asdict(item) for item in sorted(manifest.visits, key=lambda item: item.visit_id)],
        "expected_detections": [
            asdict(item) for item in sorted(manifest.detections, key=lambda item: (item.frame_index, item.annotation_id))
        ],
        "expected_evidence": [asdict(item) for item in sorted(manifest.evidence, key=lambda item: item.candidate_id)],
        "detections": [asdict(item) for item in report.detections],
        "track_updates": [asdict(item) for item in report.track_updates],
        "evidence_candidates": [asdict(item) for item in report.evidence_candidates],
        "evidence_selections": [asdict(item) for item in report.evidence_selections],
        "evidence_fingerprint": report.evidence_fingerprint,
        "pipeline_facts": dict(sorted((report.pipeline_facts or {}).items())),
        "proposals": [asdict(item) for item in sorted(report.proposals, key=lambda item: item.proposal_key)],
        "matches": [asdict(item) for item in report.matches],
        "metrics": report.metrics,
        "threshold_results": list(report.threshold_results),
        "errors": list(report.errors),
        "creates_truth": report.creates_truth,
    }
    payload = {**semantic, "semantic": semantic, "semantic_fingerprint": semantic_fingerprint(semantic),
               "execution": dict(sorted(execution.items()))}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".replay-report.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(serialized); temporary.flush(); os.fsync(temporary.fileno())
        os.replace(temporary_name, output)
    finally:
        try: os.unlink(temporary_name)
        except FileNotFoundError: pass
    return output


def _safe_directory(value: Path) -> Path:
    if value.is_symlink() or not value.is_dir():
        raise ReplayValidationError("unsafe_frames_directory")
    return value.resolve(strict=True)


def _safe_frame_path(root: Path, relative: str) -> Path:
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or item.suffix.lower() not in _IMAGE_SUFFIXES:
        raise ReplayValidationError("unsafe_frame_path")
    candidate = root / item
    if candidate.is_symlink() or not candidate.is_file():
        raise ReplayValidationError("unsafe_frame_path")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ReplayValidationError("unsafe_frame_path")
    return resolved


def _safe_output_directory(value: Path) -> Path:
    directory = value.expanduser()
    workspace = find_workspace_root()
    parent = directory.parent.resolve(strict=True) if not directory.exists() else directory.resolve(strict=True).parent
    resolved = parent / directory.name
    if directory.is_symlink() or directory == Path(".") or directory.suffix:
        raise ReplayValidationError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise ReplayValidationError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise ReplayValidationError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)


def _load_json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise ReplayValidationError("unsafe_manifest_path")
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayValidationError("invalid_manifest_json") from error
    if not isinstance(value, dict): raise ReplayValidationError("invalid_manifest_json")
    return value


def _verify_image(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            dimensions = image.size; image.verify(); return dimensions
    except Exception as error: raise ReplayValidationError("undecodable_frame") from error


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024): digest.update(block)
    return digest.hexdigest()


def _appearance(value: object) -> ExpectedAppearance:
    if not isinstance(value, dict): raise ReplayValidationError("invalid_appearance")
    return ExpectedAppearance(_require_string(value, "appearance_id"), _require_int(value, "start_offset_ms", minimum=0),
                              _require_int(value, "end_offset_ms", minimum=0), _optional_string(value, "outcome"), _optional_bool(value, "ambiguous"))


def _visit(value: object) -> ExpectedVisit:
    if not isinstance(value, dict): raise ReplayValidationError("invalid_visit")
    ids = _require_list(value, "appearance_ids")
    if not all(isinstance(item, str) and item for item in ids): raise ReplayValidationError("invalid_visit_membership")
    return ExpectedVisit(_require_string(value, "visit_id"), tuple(ids), _require_int(value, "start_offset_ms", minimum=0),
                         _require_int(value, "end_offset_ms", minimum=0), _optional_string(value, "outcome"),
                         _optional_string(value, "zone_id"), _optional_bool(value, "ambiguous"))


def _detection(value: object) -> ExpectedDetection:
    if not isinstance(value, dict):
        raise ReplayValidationError("invalid_detection_annotation")
    box = value.get("bounding_box")
    if (
        not isinstance(box, list) or len(box) != 4
        or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in box)
    ):
        raise ReplayValidationError("invalid_detection_annotation")
    return ExpectedDetection(
        _require_string(value, "annotation_id"),
        _require_int(value, "frame_index", minimum=0),
        _require_string(value, "broad_class"),
        tuple(float(item) for item in box),
    )


def _evidence(value: object) -> ExpectedEvidence:
    if not isinstance(value, dict):
        raise ReplayValidationError("invalid_evidence_annotation")
    geometry_value = value.get("subject_geometry")
    geometry = None
    if geometry_value is not None:
        if (
            not isinstance(geometry_value, list) or len(geometry_value) != 4
            or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in geometry_value)
        ):
            raise ReplayValidationError("invalid_evidence_annotation")
        geometry = tuple(float(item) for item in geometry_value)
    return ExpectedEvidence(
        _require_string(value, "candidate_id"),
        _optional_nullable_bool(value, "subject_visible"),
        geometry,
        _optional_nullable_bool(value, "useful_animal_confirmation"),
        _optional_nullable_bool(value, "useful_identification"),
        _optional_nullable_bool(value, "useful_context"),
        _optional_nullable_bool(value, "preferred_context"),
        _optional_bool(value, "ambiguous"),
        _optional_nullable_bool(value, "obstruction"),
        _optional_nullable_bool(value, "motion_blur"),
        _optional_nullable_bool(value, "clipping"),
        _optional_nullable_bool(value, "subject_absent"),
    )


def _excluded_regions(value: object) -> tuple[tuple[float, float, float, float], ...]:
    if not isinstance(value, list) or len(value) > 32:
        raise ReplayValidationError("invalid_analysis_excluded_regions")
    regions: list[tuple[float, float, float, float]] = []
    for box in value:
        if (
            not isinstance(box, list)
            or len(box) != 4
            or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in box)
        ):
            raise ReplayValidationError("invalid_analysis_excluded_regions")
        normalized = tuple(float(item) for item in box)
        if not all(0.0 <= item <= 1.0 for item in normalized) or normalized[0] >= normalized[2] or normalized[1] >= normalized[3]:
            raise ReplayValidationError("invalid_analysis_excluded_regions")
        regions.append(normalized)
    return tuple(regions)


def _thresholds(value: object) -> dict[str, float]:
    if not isinstance(value, dict): raise ReplayValidationError("invalid_thresholds")
    result: dict[str, float] = {}
    for name, target in value.items():
        if not isinstance(name, str) or not name or not isinstance(target, (int, float)) or isinstance(target, bool):
            raise ReplayValidationError("invalid_thresholds")
        result[name] = float(target)
    return dict(sorted(result.items()))


def _require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result or len(result) > MAX_STRING_LENGTH: raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, str) or len(result) > MAX_STRING_LENGTH): raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_bool(value: dict[str, Any], key: str) -> bool:
    result = value.get(key, False)
    if not isinstance(result, bool): raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_nullable_bool(value: dict[str, Any], key: str) -> bool | None:
    result = value.get(key)
    if result is not None and not isinstance(result, bool):
        raise ReplayValidationError(f"invalid_{key}")
    return result


def _require_int(value: dict[str, Any], key: str, *, minimum: int) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool) or result < minimum: raise ReplayValidationError(f"invalid_{key}")
    return result


def _require_number(value: dict[str, Any], key: str, *, minimum: float) -> float:
    result = value.get(key)
    if not isinstance(result, (int, float)) or isinstance(result, bool) or result < minimum: raise ReplayValidationError(f"invalid_{key}")
    return float(result)


def _require_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key)
    if not isinstance(result, list): raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key, [])
    if not isinstance(result, list): raise ReplayValidationError(f"invalid_{key}")
    return result
