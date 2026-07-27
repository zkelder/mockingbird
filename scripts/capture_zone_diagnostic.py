"""Capture bounded local Zone crops for offline detector comparison.

This development utility reads an existing local live-session MJPEG endpoint
and uses the production Privacy/Ignore-masked Zone crop helper.  It persists
only the masked Zone crops, compact contact sheets, and non-secret metadata;
it never stores a full frame, records audio, opens a camera, or creates product
records.  Detector inference and bird annotation are deliberately separate
offline steps.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
import signal
from time import monotonic, sleep
from typing import Any
from urllib.request import urlopen

import cv2
import numpy as np

from mockingbird.api.main import _object_detector_zone_crop
from mockingbird.api.schemas import Zone


MAX_DURATION_SECONDS = 30 * 60
MAX_FILES = 1_800
MAX_BYTES = 250 * 1024 * 1024
CAPTURE_INTERVAL_SECONDS = 1.0
CONTACT_SHEET_GROUP_SIZE = 50
CONTACT_SHEET_COLUMNS = 10
CONTACT_SHEET_THUMBNAIL_SIZE = (160, 90)
MANIFEST_FLUSH_INTERVAL = 10
MAX_CONSECUTIVE_CONNECT_FAILURES = 10


def _json(url: str) -> Any:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - local caller URL only.
        return json.loads(response.read().decode("utf-8"))


def _read_mjpeg_frame(response: Any) -> bytes | None:
    while True:
        boundary = response.readline()
        if not boundary:
            return None
        if boundary.startswith(b"--frame"):
            break
    content_length: int | None = None
    while True:
        header = response.readline()
        if not header:
            return None
        if header in {b"\r\n", b"\n"}:
            break
        name, _, value = header.decode("ascii", errors="ignore").partition(":")
        if name.lower() == "content-length":
            try:
                content_length = int(value.strip())
            except ValueError:
                return None
    if content_length is None or content_length < 1 or content_length > 8 * 1024 * 1024:
        return None
    payload = response.read(content_length)
    response.readline()
    return payload if len(payload) == content_length else None


def _contact_sheet_jpeg(images: list[np.ndarray]) -> bytes | None:
    if not images:
        return None
    thumbnail_width, thumbnail_height = CONTACT_SHEET_THUMBNAIL_SIZE
    rows = (len(images) + CONTACT_SHEET_COLUMNS - 1) // CONTACT_SHEET_COLUMNS
    sheet = np.zeros(
        (rows * thumbnail_height, CONTACT_SHEET_COLUMNS * thumbnail_width, 3),
        dtype=np.uint8,
    )
    for index, image in enumerate(images):
        thumbnail = cv2.resize(
            image,
            (thumbnail_width, thumbnail_height),
            interpolation=cv2.INTER_AREA,
        )
        row, column = divmod(index, CONTACT_SHEET_COLUMNS)
        top, left = row * thumbnail_height, column * thumbnail_width
        sheet[top : top + thumbnail_height, left : left + thumbnail_width] = thumbnail
    encoded, data = cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return data.tobytes() if encoded else None


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--stream-id", required=True)
    parser.add_argument("--zone-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--duration-seconds", type=int, default=MAX_DURATION_SECONDS)
    parser.add_argument("--max-files", type=int, default=MAX_FILES)
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    return parser


def _capture_manifest(
    *,
    stream_id: str,
    zone_id: str,
    started_at: str,
    duration_seconds: float,
    records: list[dict[str, Any]],
    crop_bytes: int,
    contact_sheet_bytes: int,
    duplicate_frame_count: int,
    frozen_frame_count: int,
    reconnect_count: int,
    connection_error_count: int,
    contact_sheets: list[str],
    status: str,
    stop_reason: str | None,
) -> dict[str, Any]:
    return {
        "status": status,
        "stop_reason": stop_reason,
        "stream_id": stream_id,
        "zone_id": zone_id,
        "started_at": started_at,
        "duration_seconds": round(duration_seconds, 3),
        "capture_interval_seconds": CAPTURE_INTERVAL_SECONDS,
        "crop_count": len(records),
        "crop_bytes": crop_bytes,
        "contact_sheet_bytes": contact_sheet_bytes,
        "total_bytes": crop_bytes + contact_sheet_bytes,
        "duplicate_frame_count": duplicate_frame_count,
        "frozen_frame_count": frozen_frame_count,
        "reconnect_count": reconnect_count,
        "connection_error_count": connection_error_count,
        "contact_sheets": contact_sheets,
        "records": records,
    }


def _final_capture_status(stop_reason: str | None) -> str:
    """Classify a bounded collection's outcome without misreporting a failure."""

    if stop_reason == "interrupted":
        return "interrupted"
    if stop_reason and stop_reason.startswith("capture_error_"):
        return "failed"
    return "completed"


def main() -> int:
    args = _parser().parse_args()
    if not 1 <= args.duration_seconds <= MAX_DURATION_SECONDS:
        raise SystemExit(f"duration must be between 1 and {MAX_DURATION_SECONDS} seconds")
    if not 1 <= args.max_files <= MAX_FILES or not 1 <= args.max_bytes <= MAX_BYTES:
        raise SystemExit("file and byte limits exceed the bounded diagnostic policy")

    api_base = args.api_base.rstrip("/")
    zones = [
        Zone.model_validate(raw)
        for raw in _json(f"{api_base}/api/streams/{args.stream_id}/zones")
    ]
    zone = next((item for item in zones if item.id == args.zone_id), None)
    if zone is None or not zone.is_active or zone.zone_type.value in {"privacy", "ignore"}:
        raise SystemExit("requested Zone is not an active ordinary Zone")
    blocked = [
        item
        for item in zones
        if item.is_active and item.zone_type.value in {"privacy", "ignore"}
    ]
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit("output directory must be empty to preserve an immutable diagnostic")
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.json"
    records_path = output_dir / "records.jsonl"
    started_monotonic = monotonic()
    started_at = datetime.now(UTC).isoformat()
    next_capture_at = started_monotonic
    records: list[dict[str, Any]] = []
    pending_contact_images: list[np.ndarray] = []
    contact_sheets: list[str] = []
    crop_bytes = 0
    contact_sheet_bytes = 0
    duplicate_frame_count = 0
    frozen_frame_count = 0
    reconnect_count = 0
    connection_error_count = 0
    consecutive_connect_failures = 0
    last_frame_identity: str | None = None
    last_crop_identity: str | None = None
    stop_reason: str | None = None
    response: Any | None = None
    previous_signal_handlers: dict[int, Any] = {}

    def stop_capture(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    def flush_manifest(status: str, reason: str | None) -> None:
        _write_json(
            manifest_path,
            _capture_manifest(
                stream_id=args.stream_id,
                zone_id=zone.id,
                started_at=started_at,
                duration_seconds=monotonic() - started_monotonic,
                records=records,
                crop_bytes=crop_bytes,
                contact_sheet_bytes=contact_sheet_bytes,
                duplicate_frame_count=duplicate_frame_count,
                frozen_frame_count=frozen_frame_count,
                reconnect_count=reconnect_count,
                connection_error_count=connection_error_count,
                contact_sheets=contact_sheets,
                status=status,
                stop_reason=reason,
            ),
        )

    def flush_contact_sheet() -> None:
        nonlocal contact_sheet_bytes
        if not pending_contact_images:
            return
        data = _contact_sheet_jpeg(pending_contact_images)
        pending_contact_images.clear()
        if data is None or crop_bytes + contact_sheet_bytes + len(data) > args.max_bytes:
            return
        filename = f"contact-sheet-{len(contact_sheets) + 1:03d}.jpg"
        (output_dir / filename).write_bytes(data)
        contact_sheet_bytes += len(data)
        contact_sheets.append(filename)

    for shutdown_signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        previous_signal_handlers[shutdown_signal] = signal.signal(shutdown_signal, stop_capture)
    flush_manifest("capturing", None)
    try:
        while monotonic() - started_monotonic < args.duration_seconds:
            if len(records) >= args.max_files:
                stop_reason = "maximum_crop_count"
                break
            if crop_bytes + contact_sheet_bytes >= args.max_bytes:
                stop_reason = "maximum_bytes"
                break
            if response is None:
                try:
                    response = urlopen(  # noqa: S310 - local caller URL only.
                        f"{api_base}/api/streams/{args.stream_id}/live-session/mjpeg",
                        timeout=10,
                    )
                except OSError:
                    # A persistent monitor can briefly recycle its read-only
                    # preview endpoint. Retry a bounded number of times rather
                    # than claiming a completed collection with a short gap.
                    reconnect_count += 1
                    connection_error_count += 1
                    consecutive_connect_failures += 1
                    if consecutive_connect_failures >= MAX_CONSECUTIVE_CONNECT_FAILURES:
                        stop_reason = "capture_error_reconnect_unavailable"
                        break
                    sleep(1.0)
                    continue
                consecutive_connect_failures = 0
            frame = _read_mjpeg_frame(response)
            if frame is None:
                response.close()
                response = None
                reconnect_count += 1
                sleep(0.1)
                continue
            now = monotonic()
            if now < next_capture_at:
                continue
            next_capture_at = max(next_capture_at + CAPTURE_INTERVAL_SECONDS, now)
            frame_identity = sha1(frame).hexdigest()[:20]
            if frame_identity == last_frame_identity:
                duplicate_frame_count += 1
                continue
            crop = _object_detector_zone_crop(frame, zone=zone, blocked_zones=blocked)
            if crop is None:
                continue
            image, coordinate_box, source_width, source_height, input_width, input_height = crop
            crop_identity = sha1(image).hexdigest()[:20]
            if crop_identity == last_crop_identity:
                frozen_frame_count += 1
                last_frame_identity = frame_identity
                continue
            if crop_bytes + contact_sheet_bytes + len(image) > args.max_bytes:
                stop_reason = "maximum_bytes"
                break
            filename = f"zone-crop-{len(records) + 1:04d}.jpg"
            (output_dir / filename).write_bytes(image)
            decoded = cv2.imdecode(np.frombuffer(image, dtype=np.uint8), cv2.IMREAD_COLOR)
            if decoded is not None:
                pending_contact_images.append(decoded)
            crop_bytes += len(image)
            record = {
                "captured_at": datetime.now(UTC).isoformat(),
                "file": filename,
                "frame_identity": frame_identity,
                "crop_identity": crop_identity,
                "zone_id": zone.id,
                "zone_source_dimensions": [source_width, source_height],
                "detector_input_dimensions": [input_width, input_height],
                "full_frame_normalized_zone_box": list(coordinate_box),
                "visible_bird": "uncertain",
            }
            with records_path.open("a", encoding="utf-8") as records_file:
                records_file.write(json.dumps(record, separators=(",", ":")) + "\n")
            records.append(record)
            last_frame_identity = frame_identity
            last_crop_identity = crop_identity
            if len(pending_contact_images) >= CONTACT_SHEET_GROUP_SIZE:
                flush_contact_sheet()
            if len(records) % MANIFEST_FLUSH_INTERVAL == 0:
                flush_manifest("capturing", None)
    except KeyboardInterrupt:
        stop_reason = "interrupted"
    except Exception as error:
        # Retain only a coarse failure kind: the full source URL and any runtime
        # response details do not belong in an on-disk diagnostic manifest.
        stop_reason = f"capture_error_{type(error).__name__}"
    finally:
        if response is not None:
            response.close()
        flush_contact_sheet()
        final_status = _final_capture_status(stop_reason)
        flush_manifest(final_status, stop_reason or "duration_elapsed")
        for shutdown_signal, handler in previous_signal_handlers.items():
            signal.signal(shutdown_signal, handler)

    manifest = _capture_manifest(
        stream_id=args.stream_id,
        zone_id=zone.id,
        started_at=started_at,
        duration_seconds=monotonic() - started_monotonic,
        records=records,
        crop_bytes=crop_bytes,
        contact_sheet_bytes=contact_sheet_bytes,
        duplicate_frame_count=duplicate_frame_count,
        frozen_frame_count=frozen_frame_count,
        reconnect_count=reconnect_count,
        connection_error_count=connection_error_count,
        contact_sheets=contact_sheets,
        status=_final_capture_status(stop_reason),
        stop_reason=stop_reason or "duration_elapsed",
    )
    print(
        json.dumps(
            {
                key: manifest[key]
                for key in ("status", "stop_reason", "duration_seconds", "crop_count", "total_bytes")
            }
        )
    )
    if stop_reason == "interrupted":
        return 130
    return 1 if _final_capture_status(stop_reason) == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
