"""Safe, filesystem-only I/O for the Stage 6.5 adaptive motion-proposal
detector benchmark and three-way decision.

Reuses `detector_benchmark_io.load_calibration_manifest` unchanged -- the
temporal cohort is authored in the identical reviewed `CalibrationManifest`
schema the Stage 6.2 single-pass benchmark already uses (`sequence_id`/
`sequence_order`/`source_offset_ms` are already first-class fields of that
schema; see docs/adaptive-motion-proposal-benchmark-contract.md). This module
adds only atomic report writes for the two new report shapes and the one
genuinely new decode step: turning an already-verified source image into a
small, fixed-size grayscale `FramePlane` for differencing. Never imports the
product repository and never opens the product database.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.detector_benchmark_io import load_calibration_manifest
from mockingbird.observation.motion_proposal_benchmark import MotionProposalBenchmarkError
from mockingbird.observation.motion_proposal_strategy import FramePlane
from mockingbird.web_app import find_workspace_root

MOTION_PROPOSAL_REPORT_FILENAME = "motion-proposal-benchmark-report.json"
MOTION_PROPOSAL_DECISION_FILENAME = "motion-proposal-decision-report.json"

__all__ = [
    "MOTION_PROPOSAL_DECISION_FILENAME",
    "MOTION_PROPOSAL_REPORT_FILENAME",
    "decode_frame_plane",
    "load_calibration_manifest",
    "load_motion_proposal_report",
    "write_motion_proposal_decision_report",
    "write_motion_proposal_benchmark_report",
]


def decode_frame_plane(image_path: Path, *, comparison_width: int, comparison_height: int) -> FramePlane:
    """Decode one already-verified local image into a small, fixed-size
    grayscale frame plane for pure differencing.

    Deliberately the only place in the Stage 6.5 code path that touches PIL
    for pixel decode, mirroring `multi_scale_cli._window_packets`/
    `detector_benchmark_io._verify_image` keeping PIL out of every pure
    module. Downsampling to one fixed size regardless of source resolution
    or aspect ratio is intentional: the produced plane is only ever compared
    against another plane decoded the same way, and every region computed
    from it is immediately normalized back to [0,1] source-relative
    coordinates, so the fixed comparison size never becomes a scene- or
    camera-specific coordinate."""

    try:
        from PIL import Image
        with Image.open(image_path) as source:
            source.load()
            grayscale = source.convert("L").resize(
                (comparison_width, comparison_height), Image.Resampling.BILINEAR,
            )
            pixels = list(grayscale.getdata())
    except Exception as error:
        raise MotionProposalBenchmarkError("undecodable_frame") from error
    return tuple(
        tuple(pixels[row * comparison_width:(row + 1) * comparison_width])
        for row in range(comparison_height)
    )


def load_motion_proposal_report(path: Path) -> dict[str, Any]:
    """Load one existing motion-proposal-shaped report file. Path safety
    only; deferred structural validation happens in the consuming function.
    Deliberately not confined to the repository workspace -- two-root
    reproducibility checks require reading reports from unrelated absolute
    paths, the same convention `multi_scale_benchmark_io` already uses."""

    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise MotionProposalBenchmarkError("unsafe_report_path")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MotionProposalBenchmarkError("invalid_report_json") from error
    if not isinstance(value, dict):
        raise MotionProposalBenchmarkError("invalid_report_json")
    return value


def write_motion_proposal_benchmark_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    return _write_report(output_directory, MOTION_PROPOSAL_REPORT_FILENAME, semantic, execution=execution)


def write_motion_proposal_decision_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    return _write_report(output_directory, MOTION_PROPOSAL_DECISION_FILENAME, semantic, execution=execution)


def _write_report(output_directory: Path, filename: str, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    """Atomic fsync-then-rename write, identical convention to
    `detector_benchmark_io`/`multi_scale_benchmark_io`."""

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
        raise MotionProposalBenchmarkError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise MotionProposalBenchmarkError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise MotionProposalBenchmarkError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)
