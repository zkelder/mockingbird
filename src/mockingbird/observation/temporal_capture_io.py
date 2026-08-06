"""Safe, filesystem-only I/O for the Stage 6.6 temporal-capture pipeline.

Mirrors `detector_benchmark_io`/`multi_scale_benchmark_io`/`motion_proposal_io`'s
safety conventions (contained paths, no symlinks, atomic writes). This module
never imports the product repository and never opens the product database.
The only network-adjacent value it handles is the Camera Node connection
config, and that config is deliberately never echoed into a semantic
manifest -- see `CameraNodeConnectionConfig.redacted`.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.temporal_capture import OperatorMarker, TemporalCaptureError
from mockingbird.web_app import find_workspace_root

CAPTURE_MANIFEST_FILENAME = "capture-session-manifest.json"
MARKERS_DIRECTORY_NAME = "markers"
FRAMES_DIRECTORY_NAME = "frames"
HIGH_RESOLUTION_DIRECTORY_NAME = "high-resolution"

__all__ = [
    "CAPTURE_MANIFEST_FILENAME",
    "FRAMES_DIRECTORY_NAME",
    "HIGH_RESOLUTION_DIRECTORY_NAME",
    "MARKERS_DIRECTORY_NAME",
    "CameraNodeConnectionConfig",
    "load_camera_node_connection_config",
    "load_capture_manifest",
    "read_operator_markers",
    "safe_capture_output_directory",
    "write_capture_manifest",
    "write_frame_bytes",
    "write_operator_marker",
]


@dataclass(frozen=True)
class CameraNodeConnectionConfig:
    """The `--camera-node-config` file shape. Kept entirely separate from
    every semantic manifest type in `temporal_capture.py` -- nothing here is
    ever passed to `CaptureSessionConfig`/`CaptureSessionManifest`."""

    base_address: str
    credential: str
    camera_id: str
    stream_id: str
    evidence_profile_id: str

    def redacted(self) -> dict[str, str]:
        """Safe for logs/printing: host is kept (operators need it to debug
        connectivity), credential is not."""

        return {
            "base_address": self.base_address, "camera_id": self.camera_id,
            "stream_id": self.stream_id, "evidence_profile_id": self.evidence_profile_id,
            "credential": "<redacted>",
        }


def load_camera_node_connection_config(path: Path) -> CameraNodeConnectionConfig:
    if path.is_symlink() or not path.is_file():
        raise TemporalCaptureError("invalid_camera_node_config")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TemporalCaptureError("invalid_camera_node_config") from error
    required = ("base_address", "credential", "camera_id", "stream_id", "evidence_profile_id")
    if not isinstance(payload, dict) or any(not isinstance(payload.get(key), str) or not payload[key] for key in required):
        raise TemporalCaptureError("invalid_camera_node_config")
    return CameraNodeConnectionConfig(*(payload[key] for key in required))


def _safe_directory_path(value: Path) -> Path:
    directory = value.expanduser()
    workspace = find_workspace_root()
    parent = directory.parent.resolve(strict=True) if not directory.exists() else directory.resolve(strict=True).parent
    resolved = parent / directory.name
    if directory.is_symlink() or directory == Path(".") or directory.suffix:
        raise TemporalCaptureError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise TemporalCaptureError("unsafe_output_path")
    return resolved


def safe_capture_output_directory(value: Path, *, allow_existing: bool = False) -> Path:
    """Identical bound to every existing benchmark's `_safe_output_directory`
    (new-or-empty, symlink-free, contained under `data/` when inside the
    repository workspace) -- `allow_existing=True` lets review/export
    commands re-open a capture directory a previous command already wrote
    into, still refusing a symlink or an out-of-bounds path."""

    directory = value.expanduser()
    resolved = _safe_directory_path(directory)
    if directory.exists():
        if not directory.is_dir():
            raise TemporalCaptureError("unsafe_output_path")
        if not allow_existing and any(directory.iterdir()):
            raise TemporalCaptureError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return resolved


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass


def write_frame_bytes(capture_directory: Path, *, frame_id: str, payload: bytes, high_resolution: bool = False) -> Path:
    subdirectory = capture_directory / (HIGH_RESOLUTION_DIRECTORY_NAME if high_resolution else FRAMES_DIRECTORY_NAME)
    subdirectory.mkdir(parents=True, exist_ok=True)
    if "/" in frame_id or ".." in frame_id or not frame_id:
        raise TemporalCaptureError("unsafe_frame_identity")
    destination = subdirectory / f"{frame_id}.jpg"
    _atomic_write_bytes(destination, payload)
    return destination


def write_capture_manifest(capture_directory: Path, semantic: dict[str, Any]) -> Path:
    destination = capture_directory / CAPTURE_MANIFEST_FILENAME
    serialized = json.dumps(semantic, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    _atomic_write_bytes(destination, serialized)
    return destination


def load_capture_manifest(capture_directory: Path) -> dict[str, Any]:
    path = capture_directory / CAPTURE_MANIFEST_FILENAME
    if path.is_symlink() or not path.is_file():
        raise TemporalCaptureError("missing_capture_manifest")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TemporalCaptureError("invalid_capture_manifest") from error
    if not isinstance(value, dict):
        raise TemporalCaptureError("invalid_capture_manifest")
    return value


def write_operator_marker(capture_directory: Path, marker: OperatorMarker) -> Path:
    """Append one timestamped marker file -- the "simple engineering-only
    way to mark" the task packet asks for. A separate `temporal-capture-mark`
    process (or the same process reacting to a key press) writes this while
    `temporal-capture` is running; the capture loop polls the directory."""

    directory = capture_directory / MARKERS_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{marker.marker_id}.json"
    if destination.exists():
        raise TemporalCaptureError("duplicate_marker_identity")
    from dataclasses import asdict
    _atomic_write_bytes(destination, json.dumps(asdict(marker), sort_keys=True).encode())
    return destination


def read_operator_markers(capture_directory: Path) -> tuple[OperatorMarker, ...]:
    directory = capture_directory / MARKERS_DIRECTORY_NAME
    if not directory.is_dir():
        return ()
    markers: list[OperatorMarker] = []
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            markers.append(OperatorMarker(**payload))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, TemporalCaptureError):
            continue
    return tuple(markers)
