"""Perception Replay Regression Harness v1: safe filesystem I/O.

Mirrors `replay_io.py`'s own safety conventions (no symlinks, no traversal,
atomic writes, no absolute path ever entering a semantic/committed payload)
for two additive capabilities `replay_io.py` does not provide:

1. Building a `ReplayBundle` directly from a real `acceptance_recorder.py`
   recording directory (a `manifest.jsonl` + `frame-*.jpg` files) -- no
   hand-authored truth manifest required, since a raw field recording has
   none. Every Visit/appearance-truth-dependent metric this produces is
   honestly `not_evaluated`/`insufficient_truth`; see `replay.BenchmarkManifest`
   for exactly which metrics that affects.
2. A small, explicit regression-fixture registry (JSON, one entry per named
   fixture) so a real field defect can be replayed by name instead of by
   re-typing its frames/manifest/provider/stream-id/window every time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json

from mockingbird.observation.replay import BenchmarkManifest, ReplayFrame, ReplayInput, ReplayValidationError
from mockingbird.observation.replay_io import ReplayBundle

MAX_STRING_LENGTH = 512
#: `description` is genuinely explanatory prose (which real defect a fixture
#: regression-tracks, where its adjudicated denominator lives) rather than an
#: identifier/path -- a materially larger, still-bounded cap, not unbounded.
MAX_DESCRIPTION_LENGTH = 4_000
MAX_RECORDING_FRAMES = 20_000
ACCEPTANCE_RECORDING_MANIFEST_FILENAME = "manifest.jsonl"


def _safe_directory(value: Path) -> Path:
    if value.is_symlink() or not value.is_dir():
        raise ReplayValidationError("unsafe_recording_directory")
    return value.resolve(strict=True)


def load_acceptance_recording(
    directory: Path,
    *,
    stream_id: str,
    input_id: str,
    window_start_ms: int | None = None,
    window_end_ms: int | None = None,
) -> ReplayBundle:
    """Build a `ReplayBundle` (empty-truth `BenchmarkManifest`) directly from
    one real `acceptance_recorder.BoundedFrameSampleRecorder` output
    directory -- the exact `manifest.jsonl` + `frame-{seq:06d}-offset
    {ms:09d}ms.jpg` shape `acceptance_recorder.py` writes (see
    docs/independent-encounter-denominator-design.md).

    `window_start_ms`/`window_end_ms` (both inclusive, both optional) bound
    which recorded frames are included, evaluated against each frame's own
    real `source_offset_ms` -- a session-relative offset from this
    recording's own first saved frame, never a wall-clock cut. Frame
    `index`/`source_offset_ms` are re-based to start at 0 for the *selected*
    window (required by `ReplayInput.__post_init__`'s own strictly-
    increasing-from-a-stable-origin contract) while each frame's genuine
    absolute `captured_at_iso` is preserved unchanged -- so the harness's
    logical-time admission mapping can prefer real recorded wall-clock time
    over a synthetic anchor. Never sleeps, never reads a wall clock itself.

    Directory safety mirrors `replay_io._safe_directory`/`_safe_frame_path`
    exactly: no symlinks, no path escaping `directory`, one required
    `manifest.jsonl`.
    """

    root = _safe_directory(directory)
    manifest_path = root / ACCEPTANCE_RECORDING_MANIFEST_FILENAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ReplayValidationError("unsafe_recording_manifest_path")

    records: list[dict[str, Any]] = []
    with manifest_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ReplayValidationError("invalid_recording_manifest_line") from error
            if not isinstance(record, dict):
                raise ReplayValidationError("invalid_recording_manifest_line")
            records.append(record)
    if not records:
        raise ReplayValidationError("empty_recording")
    if len(records) > MAX_RECORDING_FRAMES:
        raise ReplayValidationError("recording_frame_limit")

    records.sort(key=lambda item: _require_int(item, "sequence"))
    origin_offset_ms = _require_int(records[0], "source_offset_ms")

    selected: list[tuple[int, dict[str, Any]]] = []
    for record in records:
        raw_offset = _require_int(record, "source_offset_ms")
        rebased_offset = raw_offset - origin_offset_ms
        if window_start_ms is not None and rebased_offset < window_start_ms:
            continue
        if window_end_ms is not None and rebased_offset > window_end_ms:
            continue
        selected.append((rebased_offset, record))
    if not selected:
        raise ReplayValidationError("empty_window_selection")
    if window_start_ms is not None:
        # Re-base again so the *selected* window itself starts at offset 0 --
        # required by `ReplayInput`'s strictly-increasing-from-a-stable-
        # origin contract when a caller replays a bounded window in
        # isolation rather than the whole recording.
        window_origin_ms = selected[0][0]
        selected = [(offset - window_origin_ms, record) for offset, record in selected]

    frames: list[ReplayFrame] = []
    for index, (offset_ms, record) in enumerate(selected):
        filename = _require_string(record, "filename")
        candidate = _safe_recording_frame_path(root, filename)
        content_hash = _require_string(record, "content_hash")
        captured_at_iso = record.get("captured_at")
        frames.append(ReplayFrame(
            index, offset_ms, content_hash, str(candidate),
            captured_at_iso=captured_at_iso if isinstance(captured_at_iso, str) else None,
            source_sequence=_optional_int(record, "sequence"),
        ))

    first_frame = selected[0][1]
    width, height = _probe_dimensions(root / _require_string(first_frame, "filename"))
    replay = ReplayInput(input_id, stream_id, width, height, _acceptance_recorder_nominal_fps(), tuple(frames))
    manifest = BenchmarkManifest(1, f"{input_id}:empty-truth", replay.fingerprint, (), ())
    return ReplayBundle(replay, manifest, {})


def _acceptance_recorder_nominal_fps() -> float:
    """`acceptance_recorder.py` samples on a wall-clock interval, not a fixed
    frame rate, and this loader never assumes the configured default; the
    `ReplayInput.nominal_fps` field only gates `frame-driven-onnx-cuda`'s own
    `--provider-config`-declared `source_nominal_fps` check
    (`replay_cli.py`), which a caller replaying real acceptance-recorder
    frames through that provider must pass its *own* matching value for --
    this constant is deliberately generic/permissive (never `0`, satisfying
    `ReplayInput.__post_init__`) rather than a specific claimed cadence."""

    return 1.0


def _probe_dimensions(path: Path) -> tuple[int, int]:
    try:
        from PIL import Image
        with Image.open(path) as image:
            return image.size
    except Exception as error:
        raise ReplayValidationError("undecodable_recording_frame") from error


def _safe_recording_frame_path(root: Path, relative: str) -> Path:
    item = Path(relative)
    if item.is_absolute() or ".." in item.parts or item.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise ReplayValidationError("unsafe_recording_frame_path")
    candidate = root / item
    if candidate.is_symlink() or not candidate.is_file():
        raise ReplayValidationError("unsafe_recording_frame_path")
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ReplayValidationError("unsafe_recording_frame_path")
    return resolved


@dataclass(frozen=True)
class RegressionFixture:
    """One named, reproducible replay input -- a pointer, never a copy, at
    real or synthetic frames plus the configuration needed to replay them
    identically every time. `denominator_reference` optionally names a local
    path to an independently-adjudicated encounter table (never required;
    never itself evidence of wildlife truth -- see
    docs/independent-encounter-denominator-design.md)."""

    fixture_id: str
    description: str
    source_kind: str  # "benchmark_manifest" | "acceptance_recording"
    frames_path: str
    manifest_path: str | None
    provider_key: str
    provider_config_path: str | None
    stream_id: str
    base_observed_at: datetime | None
    window_start_ms: int | None = None
    window_end_ms: int | None = None
    denominator_reference: str | None = None
    structural_expectation: str | None = None


def load_fixture_registry(path: Path) -> dict[str, RegressionFixture]:
    """Parse a small, versioned JSON registry of named fixtures. Refuses a
    symlinked/non-file path exactly like every other manifest this package
    loads; refuses a duplicate `fixture_id`."""

    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise ReplayValidationError("unsafe_fixture_registry_path")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ReplayValidationError("invalid_fixture_registry_json") from error
    if not isinstance(document, dict) or document.get("version") != 1:
        raise ReplayValidationError("unsupported_fixture_registry_version")
    entries = document.get("fixtures")
    if not isinstance(entries, list):
        raise ReplayValidationError("invalid_fixture_registry_json")

    fixtures: dict[str, RegressionFixture] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReplayValidationError("invalid_fixture_entry")
        fixture_id = _require_string(entry, "fixture_id")
        if fixture_id in fixtures:
            raise ReplayValidationError("duplicate_fixture_id")
        base_observed_at_raw = entry.get("base_observed_at")
        base_observed_at = None
        if base_observed_at_raw is not None:
            if not isinstance(base_observed_at_raw, str):
                raise ReplayValidationError("invalid_base_observed_at")
            try:
                base_observed_at = datetime.fromisoformat(base_observed_at_raw)
            except ValueError as error:
                raise ReplayValidationError("invalid_base_observed_at") from error
            if base_observed_at.tzinfo is None:
                base_observed_at = base_observed_at.replace(tzinfo=UTC)
        description = entry.get("description")
        if not isinstance(description, str) or not description or len(description) > MAX_DESCRIPTION_LENGTH:
            raise ReplayValidationError("invalid_description")
        fixtures[fixture_id] = RegressionFixture(
            fixture_id=fixture_id,
            description=description,
            source_kind=_require_string(entry, "source_kind"),
            frames_path=_require_string(entry, "frames_path"),
            manifest_path=_optional_string(entry, "manifest_path"),
            provider_key=_require_string(entry, "provider_key"),
            provider_config_path=_optional_string(entry, "provider_config_path"),
            stream_id=_require_string(entry, "stream_id"),
            base_observed_at=base_observed_at,
            window_start_ms=_optional_int(entry, "window_start_ms"),
            window_end_ms=_optional_int(entry, "window_end_ms"),
            denominator_reference=_optional_string(entry, "denominator_reference"),
            structural_expectation=_optional_string(entry, "structural_expectation"),
        )
        if fixtures[fixture_id].source_kind not in {"benchmark_manifest", "acceptance_recording"}:
            raise ReplayValidationError("unsupported_fixture_source_kind")
    return fixtures


def _require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result or len(result) > MAX_STRING_LENGTH:
        raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, str) or len(result) > MAX_STRING_LENGTH):
        raise ReplayValidationError(f"invalid_{key}")
    return result


def _require_int(value: dict[str, Any], key: str) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool):
        raise ReplayValidationError(f"invalid_{key}")
    return result


def _optional_int(value: dict[str, Any], key: str) -> int | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, int) or isinstance(result, bool)):
        raise ReplayValidationError(f"invalid_{key}")
    return result
