"""Safe, filesystem-only I/O for the Stage 6.13 evidence-quality benchmark.

Mirrors `replay_io`/`detector_comparison_io`/`burst_scheduler_replay_io`'s
established safety conventions (contained/symlink-free paths, atomic
fsync-then-rename report writes, a new-or-empty output directory). This
module never imports the product repository and never opens the product
database. It only ever reads already-existing local files (a reviewed
evidence manifest, an already-produced replay report, or an already-built
Stage 6.6/6.8 review packet) and writes one new, separate report file; it
never mutates a reviewed source-media file or an input review packet.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal
from mockingbird.observation.evidence_benchmark import (
    EvidenceBenchmarkError,
    ReviewedAppearance,
    ReviewedEvidenceCandidate,
    ReviewedEvidenceManifest,
    build_reviewed_evidence_manifest_from_temporal_review,
)
from mockingbird.observation.temporal_annotation import TemporalAnnotationError
from mockingbird.observation.temporal_capture import TemporalCaptureError
from mockingbird.observation.temporal_capture_io import load_capture_manifest
from mockingbird.observation.temporal_review_io import load_annotation_set
from mockingbird.web_app import find_workspace_root

BENCHMARK_REPORT_FILENAME = "evidence-benchmark-report.json"
COMPARISON_REPORT_FILENAME = "evidence-comparison-report.json"
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
MAX_STRING_LENGTH = 512


# --------------------------------------------------------------------------
# Reviewed evidence manifest (native schema)
# --------------------------------------------------------------------------


def load_reviewed_evidence_manifest(path: Path) -> ReviewedEvidenceManifest:
    """Load a native, additive-versioned reviewed-evidence-manifest JSON
    file. Deliberately not confined to the repository workspace: like every
    other benchmark's `--manifest`/`--frames`/`--provider-config`, this
    accepts any local path the caller names."""

    document = _load_json(path, error="unsafe_manifest_path", json_error="invalid_manifest_json")
    version = _require_int(document, "manifest_version", minimum=1)
    manifest_id = _require_string(document, "manifest_id")
    source_description = _optional_string(document, "source_description") or ""
    candidates = tuple(_candidate(item) for item in _require_list(document, "candidates"))
    appearances = tuple(_appearance(item) for item in _optional_list(document, "appearances"))
    return ReviewedEvidenceManifest(version, manifest_id, source_description, candidates, appearances)


def load_review_packet_manifest(review_directory: Path, *, source_description: str | None = None) -> ReviewedEvidenceManifest:
    """Mechanically derive a reviewed evidence manifest from an existing
    Stage 6.6/6.8 self-contained review directory (`capture-session-
    manifest.json` + `annotation.json`) -- the caller never hand-copies
    data that already exists in the reviewed packet. The review directory
    itself doubles as the reviewed-frame-root: every candidate's
    `image_path` is `frames/<frame_id>.jpg`, already present there."""

    try:
        session = load_capture_manifest(review_directory)
        annotations = load_annotation_set(review_directory)
    except (TemporalCaptureError, TemporalAnnotationError) as error:
        raise EvidenceBenchmarkError(f"invalid_review_packet:{error}") from error
    label = source_description or f"temporal-review:{review_directory.name}"
    return build_reviewed_evidence_manifest_from_temporal_review(session, annotations, source_description=label)


def _candidate(value: object) -> ReviewedEvidenceCandidate:
    if not isinstance(value, dict):
        raise EvidenceBenchmarkError("invalid_reviewed_candidate")
    geometry = _optional_box(value, "subject_geometry")
    return ReviewedEvidenceCandidate(
        candidate_id=_require_string(value, "candidate_id"),
        session_id=_require_string(value, "session_id"),
        role=_require_string(value, "role"),
        track_generation_id=_optional_string(value, "track_generation_id"),
        episode_id=_optional_string(value, "episode_id"),
        width=_optional_int(value, "width"),
        height=_optional_int(value, "height"),
        subject_geometry=geometry,
        source_offset_ms=_optional_int(value, "source_offset_ms"),
        captured_at_iso=_optional_string(value, "captured_at_iso"),
        high_resolution=_optional_bool(value, "high_resolution"),
        request_to_capture_ms=_optional_number(value, "request_to_capture_ms"),
        temporal_alignment=_optional_string(value, "temporal_alignment"),
        timing_uncertainty_ms=_optional_int(value, "timing_uncertainty_ms"),
        privacy_masked=_optional_nullable_bool(value, "privacy_masked"),
        decodable=_optional_nullable_bool(value, "decodable"),
        sharpness=_optional_string(value, "sharpness"),
        image_path=_optional_string(value, "image_path"),
        reviewed_subject_visible=_optional_string(value, "reviewed_subject_visible"),
        ambiguous=_optional_bool(value, "ambiguous"),
        useful_broad_confirmation=_optional_nullable_bool(value, "useful_broad_confirmation"),
        useful_identification=_optional_nullable_bool(value, "useful_identification"),
        useful_context=_optional_nullable_bool(value, "useful_context"),
        preferred_identification=_optional_nullable_bool(value, "preferred_identification"),
        preferred_context=_optional_nullable_bool(value, "preferred_context"),
        reviewed_blurred=_optional_nullable_bool(value, "reviewed_blurred"),
        reviewed_clipped=_optional_nullable_bool(value, "reviewed_clipped"),
        reviewed_occluded=_optional_nullable_bool(value, "reviewed_occluded"),
        reviewed_subject_contained=_optional_nullable_bool(value, "reviewed_subject_contained"),
        reviewer=_optional_string(value, "reviewer"),
        reviewed_at_iso=_optional_string(value, "reviewed_at_iso"),
        truth_source=_optional_string(value, "truth_source"),
        limitations=tuple(_optional_list(value, "limitations")),
    )


def _appearance(value: object) -> ReviewedAppearance:
    if not isinstance(value, dict):
        raise EvidenceBenchmarkError("invalid_reviewed_appearance")
    return ReviewedAppearance(
        _require_string(value, "appearance_id"), _require_string(value, "session_id"),
        _require_int(value, "start_offset_ms", minimum=0), _require_int(value, "end_offset_ms", minimum=0),
    )


# --------------------------------------------------------------------------
# Existing replay/evidence results (optional supplementary candidate source)
# --------------------------------------------------------------------------


def load_replay_report_document(path: Path) -> dict[str, Any]:
    """Load an already-produced `replay-report.json`. Path safety only; its
    own internal structure is validated lazily by the small readers below,
    the same division of responsibility every prior comparison/replay IO
    module uses."""

    return _load_json(path, error="unsafe_replay_report_path", json_error="invalid_replay_report_json")


def replay_candidates_and_proposals(document: dict[str, Any]) -> tuple[
    tuple[EvidenceCandidate, ...], tuple[VisitProposal, ...], str | None, dict[str, Any] | None,
]:
    """Reconstruct real `EvidenceCandidate`/`VisitProposal` dataclasses from
    an already-produced replay report's own `evidence_candidates`/
    `proposals` sections, so `evaluate_evidence_benchmark` can call the
    scorer on them exactly as it does for reviewed-manifest-derived
    episodes -- never a shortcut that reuses the report's own already-
    computed selections in place of calling the scorer."""

    candidates = tuple(
        _evidence_candidate_from_dict(item)
        for item in document.get("evidence_candidates", [])
        if isinstance(item, dict)
    )
    proposals = tuple(
        _visit_proposal_from_dict(item)
        for item in document.get("proposals", [])
        if isinstance(item, dict)
    )
    fingerprint = document.get("semantic_fingerprint")
    provider = document.get("provider")
    return (
        candidates, proposals,
        fingerprint if isinstance(fingerprint, str) else None,
        provider if isinstance(provider, dict) else None,
    )


def _evidence_candidate_from_dict(value: dict[str, Any]) -> EvidenceCandidate:
    geometry = value.get("subject_geometry")
    facts = value.get("quality_facts") or ()
    return EvidenceCandidate(
        media_asset_id=str(value.get("media_asset_id") or ""),
        stream_id=str(value.get("stream_id") or ""),
        role=str(value.get("role") or ""),
        captured_at=None,
        frame_id=value.get("frame_id"),
        source_offset_ms=value.get("source_offset_ms"),
        width=value.get("width"),
        height=value.get("height"),
        subject_geometry=tuple(geometry) if isinstance(geometry, list) and len(geometry) == 4 else None,
        track_generation_id=value.get("track_generation_id"),
        detector_provenance=value.get("detector_provenance"),
        tracker_provenance=value.get("tracker_provenance"),
        quality_facts=tuple(tuple(item) for item in facts if isinstance(item, (list, tuple)) and len(item) == 2),
        temporary=bool(value.get("temporary", True)),
        shadow_only=bool(value.get("shadow_only", True)),
    )


def _visit_proposal_from_dict(value: dict[str, Any]) -> VisitProposal:
    evidence_ids = value.get("evidence_media_asset_ids") or ()
    supporting_ids = value.get("supporting_frame_ids") or ()
    return VisitProposal(
        proposal_key=str(value.get("proposal_key") or ""),
        source_id=str(value.get("source_id") or ""),
        stream_id=str(value.get("stream_id") or ""),
        evidence_media_asset_ids=tuple(evidence_ids) if isinstance(evidence_ids, (list, tuple)) else (),
        reason=str(value.get("reason") or "replay_report_import"),
        start_offset_ms=value.get("start_offset_ms"),
        end_offset_ms=value.get("end_offset_ms"),
        zone_id=value.get("zone_id"),
        shadow_only=bool(value.get("shadow_only", True)),
        idempotency_key=value.get("idempotency_key"),
        broad_subject_class=value.get("broad_subject_class"),
        track_generation_id=value.get("track_generation_id"),
        detector_provenance=value.get("detector_provenance"),
        tracker_provenance=value.get("tracker_provenance"),
        supporting_frame_ids=tuple(supporting_ids) if isinstance(supporting_ids, (list, tuple)) else (),
        terminal_reason=value.get("terminal_reason"),
        provider_key=value.get("provider_key"),
        provider_version=value.get("provider_version"),
    )


# --------------------------------------------------------------------------
# Media resolution -- read-only; the reviewed source frame is never modified
# --------------------------------------------------------------------------


def resolve_media_mapping(frames_root: Path, manifest: ReviewedEvidenceManifest) -> dict[str, str]:
    """Resolve every candidate's declared `image_path` against the reviewed
    frame root, mirroring `replay_io._safe_frame_path`'s traversal/symlink
    protection. A path that fails *safety* (absolute, traversal, wrong
    suffix, symlink) is rejected outright; a path that is simply absent on
    disk is skipped -- candidate metadata alone remains sufficient for
    scoring, no camera or GPU (and no image) is required."""

    if frames_root.is_symlink() or not frames_root.is_dir():
        raise EvidenceBenchmarkError("unsafe_frames_directory")
    root = frames_root.resolve(strict=True)
    resolved: dict[str, str] = {}
    for item in manifest.candidates:
        if not item.image_path:
            continue
        relative = Path(item.image_path)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() not in _IMAGE_SUFFIXES:
            raise EvidenceBenchmarkError("unsafe_frame_path")
        candidate_path = root / relative
        if candidate_path.is_symlink() or not candidate_path.is_file():
            continue
        candidate_resolved = candidate_path.resolve(strict=True)
        if not candidate_resolved.is_relative_to(root):
            raise EvidenceBenchmarkError("unsafe_frame_path")
        resolved[item.candidate_id] = str(candidate_resolved)
    return resolved


# --------------------------------------------------------------------------
# Report writers -- atomic, new-or-empty output directory only.
# --------------------------------------------------------------------------


def write_evidence_benchmark_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    """`semantic` must already carry its own top-level `semantic_fingerprint`
    (e.g. `{**report.to_semantic_dict(), "semantic_fingerprint": report.semantic_fingerprint}`)
    -- this writer never computes or overwrites it, the same division of
    responsibility `detector_comparison_io.write_detector_comparison_report`
    uses."""
    return _write_report(output_directory, BENCHMARK_REPORT_FILENAME, semantic, execution=execution)


def write_evidence_comparison_report(output_directory: Path, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    """`semantic` is `compare_evidence_benchmark_reports`'s own return value,
    which already carries its own top-level `semantic_fingerprint`."""
    return _write_report(output_directory, COMPARISON_REPORT_FILENAME, semantic, execution=execution)


def _write_report(output_directory: Path, filename: str, semantic: dict[str, Any], *, execution: dict[str, Any]) -> Path:
    directory = _safe_output_directory(output_directory)
    output = directory / filename
    payload = {**semantic, "semantic": semantic, "execution": dict(sorted(execution.items()))}
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
        raise EvidenceBenchmarkError("unsafe_output_path")
    if workspace is not None:
        root = workspace.resolve()
        if resolved == root or (resolved.is_relative_to(root) and not resolved.is_relative_to(root / "data")):
            raise EvidenceBenchmarkError("unsafe_output_path")
    if directory.exists():
        if not directory.is_dir() or any(directory.iterdir()):
            raise EvidenceBenchmarkError("nonempty_output_directory")
    else:
        directory.mkdir(parents=False, exist_ok=False)
    return directory.resolve(strict=True)


# --------------------------------------------------------------------------
# Small JSON field helpers (mirrors replay_io.py's own private convention)
# --------------------------------------------------------------------------


def _load_json(path: Path, *, error: str, json_error: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".json":
        raise EvidenceBenchmarkError(error)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error_instance:
        raise EvidenceBenchmarkError(json_error) from error_instance
    if not isinstance(value, dict):
        raise EvidenceBenchmarkError(json_error)
    return value


def _require_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result or len(result) > MAX_STRING_LENGTH:
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _optional_string(value: dict[str, Any], key: str) -> str | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, str) or len(result) > MAX_STRING_LENGTH):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result or None


def _optional_bool(value: dict[str, Any], key: str) -> bool:
    result = value.get(key, False)
    if not isinstance(result, bool):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _optional_nullable_bool(value: dict[str, Any], key: str) -> bool | None:
    result = value.get(key)
    if result is not None and not isinstance(result, bool):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _require_int(value: dict[str, Any], key: str, *, minimum: int) -> int:
    result = value.get(key)
    if not isinstance(result, int) or isinstance(result, bool) or result < minimum:
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _optional_int(value: dict[str, Any], key: str) -> int | None:
    result = value.get(key)
    if result is not None and (not isinstance(result, int) or isinstance(result, bool)):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _optional_number(value: dict[str, Any], key: str) -> float | None:
    result = value.get(key)
    if result is None:
        return None
    if not isinstance(result, (int, float)) or isinstance(result, bool):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return float(result)


def _optional_box(value: dict[str, Any], key: str) -> tuple[float, float, float, float] | None:
    result = value.get(key)
    if result is None:
        return None
    if (
        not isinstance(result, list) or len(result) != 4
        or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in result)
    ):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return tuple(float(item) for item in result)  # type: ignore[return-value]


def _require_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key)
    if not isinstance(result, list):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


def _optional_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key, [])
    if not isinstance(result, list):
        raise EvidenceBenchmarkError(f"invalid_{key}")
    return result


__all__ = [
    "BENCHMARK_REPORT_FILENAME",
    "COMPARISON_REPORT_FILENAME",
    "load_replay_report_document",
    "load_review_packet_manifest",
    "load_reviewed_evidence_manifest",
    "replay_candidates_and_proposals",
    "resolve_media_mapping",
    "write_evidence_benchmark_report",
    "write_evidence_comparison_report",
]
