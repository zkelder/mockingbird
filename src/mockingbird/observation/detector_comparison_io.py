"""Safe, filesystem-only I/O for the Stage 6.3 detector-candidate comparison.

Mirrors `mockingbird.observation.detector_benchmark_io`'s safety conventions
(contained paths, no symlinks, atomic report writes) for loading one or more
already-produced `detector-benchmark-report.json` files and writing the
comparison report. This module never imports the product repository and
never opens the product database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.detector_comparison import DetectorComparisonError
from mockingbird.web_app import find_workspace_root

REPORT_FILENAME = "detector-comparison-report.json"


def load_detector_benchmark_report(path: Path) -> dict[str, Any]:
    """Load one existing `detector-benchmark-report.json`-shaped file.

    Path safety only (no symlink, must be a regular `.json` file); the
    report's own internal structure is validated lazily by
    `detector_comparison.compare_candidate` when the fields it actually
    needs are missing or malformed, the same division of responsibility
    `detector_benchmark_io.load_calibration_manifest` uses for the
    calibration manifest versus `detector_benchmark.CalibrationManifest`.
    Deliberately not confined to the repository workspace: two-root
    reproducibility checks require reading reports from unrelated absolute
    paths, exactly like `--frames`/`--manifest`/`--provider-config` already
    accept any local path the caller names.
    """

    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise DetectorComparisonError("unsafe_report_path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise DetectorComparisonError("invalid_report_json") from error
    if not isinstance(value, dict):
        raise DetectorComparisonError("invalid_report_json")
    return value


def write_detector_comparison_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    """Atomically write the one comparison report into a new or empty
    directory, using the identical fsync-then-rename convention as
    `detector_benchmark_io.write_detector_benchmark_report`."""

    directory = _safe_output_directory(output_directory)
    output = directory / REPORT_FILENAME
    payload = {**semantic, "execution": dict(sorted(execution.items()))}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".detector-comparison-report.", suffix=".tmp", dir=directory)
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
        raise DetectorComparisonError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise DetectorComparisonError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise DetectorComparisonError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)


__all__ = [
    "REPORT_FILENAME",
    "load_detector_benchmark_report",
    "write_detector_comparison_report",
]
