#!/usr/bin/env python3
"""Create local image demo detection evidence through the public MockingBird API."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import one local image, create demo DetectionProposal evidence, and print "
            "where to review it. No model runs and no reviewed truth is created."
        )
    )
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--file", required=True, help="Path to a local image file.")
    parser.add_argument("--stream-id", default=None)
    parser.add_argument("--zone-id", default=None)
    parser.add_argument("--label", default="bird")
    parser.add_argument("--species", default="unknown_bird")
    parser.add_argument("--subject-label", default="unknown_bird")
    parser.add_argument("--convert", action="store_true")
    return parser.parse_args()


def api_url(api_base: str, path: str) -> str:
    return f"{api_base.rstrip('/')}{path}"


def read_json_response(request: Request) -> Any:
    try:
        with urlopen(request, timeout=20) as response:
            content = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} {request.full_url}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach {request.full_url}: {error.reason}") from error

    if not content:
        return None
    return json.loads(content.decode("utf-8"))


def api_get(api_base: str, path: str) -> Any:
    return read_json_response(Request(api_url(api_base, path), method="GET"))


def api_post_json(api_base: str, path: str, payload: dict[str, Any]) -> Any:
    body = json.dumps(payload).encode("utf-8")
    return read_json_response(
        Request(
            api_url(api_base, path),
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
    )


def encode_multipart(
    fields: dict[str, str],
    file_path: Path,
    content_type: str,
) -> tuple[bytes, str]:
    boundary = f"mockingbird-smoke-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("utf-8"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )

    chunks.extend(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="file"; '
                f'filename="{file_path.name}"\r\n'
            ).encode("utf-8"),
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
            file_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    return b"".join(chunks), boundary


def api_post_multipart(
    api_base: str,
    path: str,
    fields: dict[str, str],
    file_path: Path,
) -> Any:
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    body, boundary = encode_multipart(fields, file_path, content_type)
    return read_json_response(
        Request(
            api_url(api_base, path),
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    )


def choose_stream(api_base: str, requested_stream_id: str | None) -> str:
    if requested_stream_id:
        return requested_stream_id

    streams = api_get(api_base, "/api/streams")
    if not streams:
        raise RuntimeError("No streams are available. Create or seed a Stream first.")
    return str(streams[0]["id"])


def choose_zone(api_base: str, stream_id: str, requested_zone_id: str | None) -> str | None:
    if requested_zone_id:
        return requested_zone_id

    zones = api_get(api_base, f"/api/streams/{quote(stream_id)}/zones")
    for zone in zones:
        if zone.get("is_active") and zone.get("zone_type") not in {"privacy", "ignore"}:
            return str(zone["id"])
    return None


def print_id(label: str, value: str | None) -> None:
    print(f"{label}: {value or 'n/a'}")


def result_id(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    return value.get("id") if isinstance(value, dict) else None


def main() -> int:
    args = parse_args()
    api_base = args.api_base.rstrip("/")
    file_path = Path(args.file).expanduser().resolve()

    if not file_path.is_file():
        print(f"Local image file was not found: {file_path}", file=sys.stderr)
        return 2

    try:
        health = api_get(api_base, "/health")
        stream_id = choose_stream(api_base, args.stream_id)
        zone_id = choose_zone(api_base, stream_id, args.zone_id)

        import_fields = {
            "stream_id": stream_id,
            "title": f"Local smoke import: {file_path.name}",
            "subject_label": args.subject_label,
            "species_guess": args.species,
            "notes": (
                "Local image smoke path. Imported through explicit developer command; "
                "no reviewed truth was created."
            ),
        }
        if zone_id:
            import_fields["zone_id"] = zone_id

        import_result = api_post_multipart(api_base, "/api/media/import", import_fields, file_path)
        media_asset = import_result["media_asset"]
        media_asset_id = media_asset["id"]

        demo_result = api_post_json(
            api_base,
            "/api/detection-runs/demo",
            {
                "media_asset_id": media_asset_id,
                "zone_id": zone_id,
                "label": args.label,
                "confidence": 0.72,
                "suggested_subject_label": args.subject_label,
                "suggested_species": args.species,
                "notes": (
                    "Local image smoke demo detector evidence only. No model inspected "
                    "the media and no reviewed truth was created."
                ),
            },
        )
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    detection_run = demo_result["detection_run"]
    proposals = demo_result["proposals"]
    first_proposal = proposals[0] if proposals else None

    print("MockingBird local image smoke path")
    print(f"API health: {health}")
    print_id("stream_id", stream_id)
    print_id("zone_id", zone_id)
    print_id("media_asset_id", media_asset_id)
    print_id("import_event_id", result_id(import_result, "event"))
    print_id("import_visit_id", result_id(import_result, "visit"))
    print_id("detection_run_id", detection_run["id"])
    print(f"detection_proposal_ids: {', '.join(proposal['id'] for proposal in proposals)}")
    print(f"review_queue_count: {demo_result['review_queue_count']}")

    if args.convert:
        if first_proposal is None:
            print("No proposal was created, so nothing was converted.", file=sys.stderr)
            return 1
        try:
            decision = api_post_json(
                api_base,
                f"/api/detection-proposals/{quote(first_proposal['id'])}/decision",
                {
                    "decision": "convert_to_event",
                    "event_title": f"Local smoke review: {file_path.name}",
                    "subject_label": args.subject_label,
                    "species_guess": args.species,
                    "notes": (
                        "Converted by local image smoke command. Event/Visit remain "
                        "unreviewed until explicit correction."
                    ),
                },
            )
        except RuntimeError as error:
            print(error, file=sys.stderr)
            return 1
        print_id("converted_event_id", result_id(decision, "event"))
        print_id("converted_visit_id", result_id(decision, "visit"))
        print("Converted proposal created reviewable Event/Visit context only.")

    print()
    print("API/UI hints:")
    print(f"- {api_base}/api/media/{quote(media_asset_id)}")
    print(f"- {api_base}/api/detection-runs/{quote(detection_run['id'])}/proposals")
    print(f"- {api_base}/api/detection-proposals")
    print(f"- {api_base}/api/review-queue")
    print()
    print("Safety boundary:")
    print("- Demo detection is synthetic DetectionProposal evidence.")
    print("- No model inspected the media.")
    print("- No ReviewLabel truth was created.")
    print("- No Event or Visit was marked reviewed.")
    print("- User correction remains required before exports, analytics, or classifier truth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
