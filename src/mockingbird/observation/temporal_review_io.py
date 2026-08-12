"""Safe filesystem I/O and PIL rendering for the Stage 6.6 review packet.

This is the one module in the Stage 6.6 pipeline allowed to touch PIL for
pixel rendering, mirroring how `multi_scale_cli`/`data/field-acceptance/.../
build_overlays.py` keep box-drawing out of every pure module. It never opens
the product database and never imports the product repository.
"""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from mockingbird.observation.temporal_annotation import (
    AnnotationSet,
    TemporalAnnotationError,
    annotation_skeleton,
)
from mockingbird.observation.temporal_capture_io import (
    FRAMES_DIRECTORY_NAME,
    HIGH_RESOLUTION_DIRECTORY_NAME,
    load_capture_manifest,
    safe_capture_output_directory,
)

ANNOTATION_FILENAME = "annotation.json"
CONTACT_SHEET_FILENAME = "contact-sheet.jpg"
INDEX_FILENAME = "index.html"
CROPS_DIRECTORY_NAME = "crops"

__all__ = [
    "ANNOTATION_FILENAME",
    "CONTACT_SHEET_FILENAME",
    "CROPS_DIRECTORY_NAME",
    "INDEX_FILENAME",
    "build_review_packet",
    "load_annotation_set",
    "load_capture_manifest",
    "safe_review_directory",
    "write_annotation_set",
    "write_export_manifest",
]


def safe_review_directory(value: Path, *, allow_existing: bool = False) -> Path:
    return safe_capture_output_directory(value, allow_existing=allow_existing)


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


def write_annotation_set(review_directory: Path, annotations: AnnotationSet) -> Path:
    destination = review_directory / ANNOTATION_FILENAME
    payload = {
        "schema_version": annotations.schema_version,
        "capture_session_id": annotations.capture_session_id,
        "capture_manifest_fingerprint": annotations.capture_manifest_fingerprint,
        "frames": [asdict(item) for item in annotations.frames],
        "appearances": [asdict(item) for item in annotations.appearances],
    }
    _atomic_write_bytes(destination, json.dumps(payload, indent=2, sort_keys=True).encode())
    return destination


def load_annotation_set(review_directory: Path) -> AnnotationSet:
    from mockingbird.observation.temporal_annotation import (
        AppearanceInterval,
        BoxAnnotation,
        EvidenceUsefulness,
        FrameAnnotation,
        Provenance,
    )

    path = review_directory / ANNOTATION_FILENAME
    if path.is_symlink() or not path.is_file():
        raise TemporalAnnotationError("missing_annotation_file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TemporalAnnotationError("invalid_annotation_file") from error
    if not isinstance(payload, dict):
        raise TemporalAnnotationError("invalid_annotation_file")

    def _box(value: dict[str, Any]) -> BoxAnnotation:
        return BoxAnnotation(
            box=tuple(value["box"]), broad_class=value.get("broad_class", "animal"),
            partially_visible=value.get("partially_visible", False), occluded=value.get("occluded", False),
            edge_clipped=value.get("edge_clipped", False), blurred=value.get("blurred", False),
            distance=value.get("distance"), box_confidence=value.get("box_confidence", "confident"),
            review_limitation=value.get("review_limitation"),
        )

    def _provenance(value: dict[str, Any] | None) -> Provenance | None:
        if value is None:
            return None
        return Provenance(
            reviewer=value["reviewer"], reviewed_at_iso=value["reviewed_at_iso"],
            source_capture_session=value["source_capture_session"], truth_source=value["truth_source"],
            product_review_label=value.get("product_review_label"),
            whole_frame_independently_confirmed=value.get("whole_frame_independently_confirmed", False),
        )

    def _usefulness(value: dict[str, Any] | None) -> EvidenceUsefulness | None:
        if value is None:
            return None
        return EvidenceUsefulness(**value)

    frames = tuple(
        FrameAnnotation(
            frame_id=item["frame_id"], whole_frame_truth=item.get("whole_frame_truth", "unreviewed"),
            yes_but_unscorable=item.get("yes_but_unscorable", False),
            boxes=tuple(_box(box) for box in item.get("boxes", [])),
            evidence_usefulness=_usefulness(item.get("evidence_usefulness")),
            provenance=_provenance(item.get("provenance")),
            privacy_ignore_override=item.get("privacy_ignore_override", False),
            reviewer_note=item.get("reviewer_note", ""),
        )
        for item in payload.get("frames", [])
    )
    appearances = tuple(
        AppearanceInterval(
            appearance_id=item["appearance_id"], start_frame_id=item["start_frame_id"], end_frame_id=item["end_frame_id"],
            instantaneous=item.get("instantaneous", False), entry_uncertain=item.get("entry_uncertain", False),
            exit_uncertain=item.get("exit_uncertain", False), continuity_ambiguous=item.get("continuity_ambiguous", False),
            # Stage 6.17: optional, absent on any pre-Stage-6.17 annotation.json.
            zone_id=item.get("zone_id"),
        )
        for item in payload.get("appearances", [])
    )
    return AnnotationSet(
        schema_version=payload.get("schema_version", 1), capture_session_id=payload["capture_session_id"],
        capture_manifest_fingerprint=payload["capture_manifest_fingerprint"], frames=frames, appearances=appearances,
    )


def write_export_manifest(output_directory: Path, semantic: dict[str, Any], *, filename: str) -> Path:
    directory = safe_capture_output_directory(output_directory)
    destination = directory / filename
    serialized = json.dumps(semantic, sort_keys=True, separators=(",", ":"), default=str).encode() + b"\n"
    _atomic_write_bytes(destination, serialized)
    return destination


def copy_replay_export_images(review_directory: Path, output_directory: Path, replay_payload: dict[str, Any]) -> int:
    """Copy every source frame a `build_replay_export` payload's `frames[].path`
    references (always `images/<frame_id>.jpg`, always sourced from the
    self-contained review directory's own `frames/` -- high-resolution
    frames are already excluded from replay, so `high-resolution/` is never
    read here) so the exported directory `replay-benchmark --frames` can
    actually load, not just a manifest that references paths nothing wrote.
    Returns the number of files copied."""

    import shutil

    directory = safe_capture_output_directory(output_directory, allow_existing=True)
    images_directory = directory / "images"
    images_directory.mkdir(parents=True, exist_ok=True)
    copied = 0
    for record in replay_payload.get("frames", []):
        relative = str(record.get("path", ""))
        if not relative.startswith("images/") or "/" in relative[len("images/"):]:
            raise TemporalAnnotationError("invalid_replay_export_frame_path")
        frame_file_name = relative[len("images/"):]
        source_path = review_directory / FRAMES_DIRECTORY_NAME / frame_file_name
        if source_path.is_symlink() or not source_path.is_file():
            raise TemporalAnnotationError("missing_replay_export_source_frame")
        shutil.copyfile(source_path, images_directory / frame_file_name)
        copied += 1
    return copied


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def _load_font(size: int):
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _draw_boxes(image, boxes: list[tuple[tuple[float, float, float, float], tuple[int, int, int], str]]) -> None:
    from PIL import ImageDraw
    width, height = image.size
    draw = ImageDraw.Draw(image)
    font = _load_font(14)
    for (left, top, right, bottom), color, label in boxes:
        pixel_box = (left * width, top * height, right * width, bottom * height)
        draw.rectangle(pixel_box, outline=color, width=2)
        if label:
            draw.text((pixel_box[0] + 2, max(0, pixel_box[1] - 14)), label, fill=color, font=font)


def _frame_overlay(source_path: Path, record: dict[str, Any], *, max_edge: int = 900):
    from PIL import Image
    with Image.open(source_path) as source:
        image = source.convert("RGB")
    width, height = image.size
    scale = min(1.0, max_edge / max(width, height))
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    canvas = image.resize(target, Image.Resampling.BILINEAR)
    boxes: list[tuple[tuple[float, float, float, float], tuple[int, int, int], str]] = []
    for item in record.get("detection_boxes", []):
        left, top, right, bottom, score = item
        boxes.append(((left, top, right, bottom), (255, 60, 60), f"det {score:.2f}"))
    for item in record.get("motion_proposal_boxes", []):
        left, top, right, bottom = item
        boxes.append(((left, top, right, bottom), (60, 160, 255), "proposal"))
    _draw_boxes(canvas, boxes)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    font = _load_font(15)
    title = f"{record['frame_id']} t={record['source_offset_ms']}ms {','.join(record['trigger_reasons'])}"
    draw.rectangle((0, 0, target[0], 18), fill=(0, 0, 0))
    draw.text((3, 2), title[:140], fill=(255, 255, 255), font=font)
    return canvas


def _contact_sheet(thumbnails: list, *, columns: int = 6, cell: int = 180):
    from PIL import Image
    if not thumbnails:
        return Image.new("RGB", (cell, cell), color=(20, 20, 20))
    rows = (len(thumbnails) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell, rows * cell), color=(15, 15, 15))
    for index, thumbnail in enumerate(thumbnails):
        thumb = thumbnail.copy()
        thumb.thumbnail((cell - 6, cell - 6))
        x, y = (index % columns) * cell + 3, (index // columns) * cell + 3
        sheet.paste(thumb, (x, y))
    return sheet


def build_review_packet(capture_directory: Path, review_directory: Path) -> dict[str, Any]:
    """Deterministic, bounded review packet: one overlay crop per retained
    frame, one chronological contact sheet, an HTML index, and a fresh
    `annotation.json` skeleton (never overwritten if one already exists, so
    re-running review-build never discards in-progress human review). The
    review directory is made fully self-contained -- the capture manifest
    and every original source frame are copied in -- so
    `temporal-review-validate`/`temporal-review-export` need only `--review`,
    matching the task's own command sketch, and content-hash validation
    keeps working even if the original capture directory is later removed.

    Stage 6.8: the manifest copied in is not always byte-identical to the
    original. `upgrade_capture_manifest_timeline` derives the reconnect-safe
    session timeline (a no-op pass-through for an already-native Stage 6.8
    capture; a deterministic reconstruction for an older one) and *that*
    upgraded manifest -- never the original capture directory's own file --
    is what gets written into the review directory, ordered, and validated/
    exported against from here on. `capture-out/capture-session-manifest.json`
    itself is only ever read, never opened for writing."""

    from mockingbird.observation.temporal_capture import upgrade_capture_manifest_timeline
    from mockingbird.observation.temporal_capture_io import write_capture_manifest
    import shutil

    manifest = upgrade_capture_manifest_timeline(load_capture_manifest(capture_directory))
    write_capture_manifest(review_directory, manifest)

    # Reconnect-safe session order, not the raw per-connection `sequence`:
    # that value resets on every reconnect, so sorting by it alone
    # interleaves unrelated connections' frames instead of true session
    # order (see docs/session-timeline-contract.md).
    frames = sorted(manifest.get("frames", []), key=lambda item: item["session_sequence"])
    crops_directory = review_directory / CROPS_DIRECTORY_NAME
    crops_directory.mkdir(parents=True, exist_ok=True)

    thumbnails = []
    crop_paths: list[str] = []
    for record in frames:
        subdirectory = HIGH_RESOLUTION_DIRECTORY_NAME if record.get("high_resolution") else FRAMES_DIRECTORY_NAME
        source_path = capture_directory / subdirectory / f"{record['frame_id']}.jpg"
        if not source_path.is_file():
            continue
        destination_subdirectory = review_directory / subdirectory
        destination_subdirectory.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_subdirectory / source_path.name)
        overlay = _frame_overlay(source_path, record)
        crop_name = f"{record['frame_id']}.jpg"
        overlay.save(crops_directory / crop_name, quality=88)
        crop_paths.append(crop_name)
        thumbnails.append(overlay)

    sheet = _contact_sheet(thumbnails)
    sheet.save(review_directory / CONTACT_SHEET_FILENAME, quality=85)

    frame_ids = tuple(item["frame_id"] for item in frames)
    annotation_path = review_directory / ANNOTATION_FILENAME
    if not annotation_path.is_file():
        skeleton = annotation_skeleton(
            frame_ids, capture_session_id=str(manifest.get("session_id")),
            capture_manifest_fingerprint=str(manifest.get("semantic_fingerprint")),
        )
        write_annotation_set(review_directory, skeleton)

    annotation_payload = json.loads(annotation_path.read_text(encoding="utf-8"))
    from mockingbird.observation.temporal_review_ui import render_review_ui

    html = render_review_ui(manifest, frames, crop_paths, annotation_payload)
    _atomic_write_bytes(review_directory / INDEX_FILENAME, html.encode("utf-8"))

    return {
        "session_id": manifest.get("session_id"), "frame_count": len(frames),
        "crop_count": len(crop_paths), "contact_sheet": CONTACT_SHEET_FILENAME,
        "index": INDEX_FILENAME, "annotation_skeleton": ANNOTATION_FILENAME,
    }


def _render_index(manifest: dict[str, Any], frames: list[dict[str, Any]], crop_paths: list[str]) -> str:
    rows = []
    for record, crop_name in zip(frames, crop_paths):
        rows.append(
            "<section class='frame'>"
            f"<h3>{record['frame_id']}</h3>"
            f"<img src='{CROPS_DIRECTORY_NAME}/{crop_name}' loading='lazy'/>"
            f"<p>offset={record['source_offset_ms']}ms seq={record['sequence']} "
            f"generation={record['provider_generation']} triggers={', '.join(record['trigger_reasons'])}</p>"
            f"<p>detector_observations={record['detector_observation_count']} "
            f"max_score={record['max_animal_score']} motion_proposals={record['motion_proposal_count']} "
            f"active_tracks={record['active_track_count']} privacy_interaction={record['privacy_ignore_interaction']}</p>"
            "</section>"
        )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>Temporal review: {manifest.get('session_id')}</title>"
        "<style>body{font-family:sans-serif;background:#111;color:#eee;}"
        ".frame{border-bottom:1px solid #333;padding:8px 0;} img{max-width:900px;}</style>"
        "</head><body>"
        f"<h1>Temporal review packet: {manifest.get('session_id')}</h1>"
        f"<p>stop_condition={manifest.get('stop_condition')} frames={len(frames)}</p>"
        f"<img src='{CONTACT_SHEET_FILENAME}' style='max-width:100%'/>"
        "<p>Edit annotation.json to record whole-frame truth, reviewed boxes, appearance "
        "intervals, evidence usefulness, and provenance for each frame below, then run "
        "<code>temporal-review-validate</code>.</p>"
        + "".join(rows) +
        "</body></html>"
    )
