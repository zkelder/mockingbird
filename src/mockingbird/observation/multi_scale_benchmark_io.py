"""Safe, filesystem-only I/O for the Stage 6.4 multi-scale detector
benchmark and strategy comparison.

Reuses `detector_benchmark_io.load_calibration_manifest` unchanged -- a
multi-scale benchmark reads the identical reviewed `CalibrationManifest`
schema as the Stage 6.2 single-pass benchmark, including a materially
larger or small-subject-focused cohort authored in that same schema. This
module adds only atomic report writes for the two new report shapes
(per-strategy benchmark report, strategy comparison report). Never imports
the product repository and never opens the product database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.detector_benchmark_io import load_calibration_manifest
from mockingbird.observation.multi_scale_benchmark import MultiScaleBenchmarkError
from mockingbird.web_app import find_workspace_root

MULTI_SCALE_REPORT_FILENAME = "multi-scale-benchmark-report.json"
MULTI_SCALE_COMPARISON_FILENAME = "multi-scale-comparison-report.json"

__all__ = [
    "MULTI_SCALE_COMPARISON_FILENAME",
    "MULTI_SCALE_REPORT_FILENAME",
    "load_calibration_manifest",
    "load_multi_scale_benchmark_report",
    "write_multi_scale_benchmark_report",
    "write_multi_scale_comparison_report",
]


def load_multi_scale_benchmark_report(path: Path) -> dict[str, Any]:
    """Load one existing `multi-scale-benchmark-report.json`-shaped file.

    Path safety only (no symlink, must be a regular `.json` file); deferred
    structural validation happens in `multi_scale_benchmark.compare_strategy_reports`.
    Deliberately not confined to the repository workspace -- two-root
    reproducibility checks require reading reports from unrelated absolute
    paths."""

    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise MultiScaleBenchmarkError("unsafe_report_path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MultiScaleBenchmarkError("invalid_report_json") from error
    if not isinstance(value, dict):
        raise MultiScaleBenchmarkError("invalid_report_json")
    return value


def write_multi_scale_benchmark_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    return _write_report(output_directory, MULTI_SCALE_REPORT_FILENAME, semantic, execution=execution)


def write_multi_scale_comparison_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    return _write_report(output_directory, MULTI_SCALE_COMPARISON_FILENAME, semantic, execution=execution)


def _write_report(output_directory: Path, filename: str, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    """Atomic fsync-then-rename write, identical convention to
    `detector_benchmark_io.write_detector_benchmark_report`."""

    directory = _safe_output_directory(output_directory)
    output = directory / filename
    payload = {**semantic, "execution": dict(sorted(execution.items()))}
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=directory)
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
        raise MultiScaleBenchmarkError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise MultiScaleBenchmarkError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise MultiScaleBenchmarkError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)
