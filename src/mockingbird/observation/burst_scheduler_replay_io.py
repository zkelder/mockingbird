"""Safe, filesystem-only I/O for the Stage 6.9 historical burst-schedule
replay evaluator. Mirrors `detector_comparison_io`/`temporal_capture_io`'s
safety conventions (contained paths, no symlinks, atomic report writes).
This module never imports the product repository and never opens the
product database; it only ever reads an existing capture manifest/annotation
file and writes one new, separate report file -- it never modifies either
input.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.burst_scheduler_replay import BurstScheduleReplayError
from mockingbird.web_app import find_workspace_root

REPORT_FILENAME = "burst-schedule-replay-report.json"


def load_json_document(path: Path) -> dict[str, Any]:
    """Load one existing JSON object file (a capture-session-manifest.json
    or annotation.json). Path safety only; the caller's own pure function
    validates the fields it actually needs, the same division of
    responsibility every earlier benchmark IO module uses."""

    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise BurstScheduleReplayError("unsafe_document_path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BurstScheduleReplayError("invalid_document_json") from error
    if not isinstance(value, dict):
        raise BurstScheduleReplayError("invalid_document_json")
    return value


def write_replay_report(output_directory: Path, semantic: dict[str, Any]) -> Path:
    """Atomically write the one replay report into a new or empty directory."""

    directory = _safe_output_directory(output_directory)
    output = directory / REPORT_FILENAME
    serialized = json.dumps(semantic, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".burst-schedule-replay-report.", suffix=".tmp", dir=directory)
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


def _safe_output_directory(value: Path) -> Path:
    directory = value.expanduser()
    workspace = find_workspace_root()
    parent = directory.parent.resolve(strict=True) if not directory.exists() else directory.resolve(strict=True).parent
    resolved = parent / directory.name
    if directory.is_symlink() or directory == Path(".") or directory.suffix:
        raise BurstScheduleReplayError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise BurstScheduleReplayError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise BurstScheduleReplayError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)


__all__ = [
    "REPORT_FILENAME",
    "load_json_document",
    "write_replay_report",
]
