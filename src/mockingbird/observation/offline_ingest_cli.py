"""CLI entry point for `python -m mockingbird analyze-recorded-media`.

Mirrors the existing `python -m mockingbird <subcommand>` dispatch
convention in `__main__.py` (a lazy import + `run(argv)` returning an int
exit code, `asyncio.run(...)` bridging sync CLI to the async Observation
Engine seam -- the same bridge `candidate_visit_authority_cli.run_trial`
already uses) -- see "API/CLI/UI surface" in docs/offline-recorded-media-
observation-contract.md.

Operates on the real local product database by default (`ProductRepository()`
with no explicit `db_url`) -- this is ordinary local-tool usage, not a test;
see `mockingbird.storage.database`'s own pytest-only safety guard, which
this module never triggers because it is never imported under pytest.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from mockingbird.observation.offline_ingest import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_PIPELINE_VERSION,
    DEFAULT_SAMPLE_FPS,
    OfflineIngestError,
    OfflineIngestResult,
    run_offline_video_ingest,
)
from mockingbird.repository.product_repository import ProductRepository


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mockingbird analyze-recorded-media",
        description=(
            "Decode one already-imported recorded-video MediaAsset and run it "
            "through the ordinary Observation Engine seam, producing candidate "
            "Events/Visits/Evidence for review -- exactly like a live Camera "
            "Node session. Never imports media itself; the MediaAsset id must "
            "already exist (see the existing folder-import path)."
        ),
    )
    parser.add_argument("media_asset_id", help="The already-imported video MediaAsset id to analyze.")
    parser.add_argument(
        "--sample-fps", type=float, default=None,
        help=f"Deterministic analysis sampling rate in frames/second (default: {DEFAULT_SAMPLE_FPS}).",
    )
    parser.add_argument(
        "--max-frames", type=int, default=None,
        help=f"Bounded sampled-frame cap for this decode (default: {DEFAULT_MAX_FRAMES}).",
    )
    parser.add_argument(
        "--pipeline-version", default=None,
        help=f"Pipeline identity for idempotency/reprocessing (default: {DEFAULT_PIPELINE_VERSION}).",
    )
    parser.add_argument(
        "--force-reprocess", action="store_true",
        help="Analyze again even if already completed under this exact pipeline_version.",
    )
    parser.add_argument("--json", action="store_true", help="Print the result as machine-readable JSON.")
    return parser


def render_human(result: OfflineIngestResult) -> str:
    lines = [
        f"status: {result.status}",
        f"media_asset_id: {result.media_asset_id}",
        f"stream_id: {result.stream_id}",
        f"sample_fps: {result.sample_fps}",
        f"frames_considered: {result.frames_considered}",
        f"frames_analyzed: {result.frames_analyzed}",
        f"events_created: {result.events_created}",
        f"visits_created: {result.visits_created}",
    ]
    if result.source_duration_seconds is not None:
        lines.append(f"source_duration_seconds: {result.source_duration_seconds:.1f}")
    if result.truncated:
        lines.append("truncated: true (this recording exceeded the bounded frame cap)")
    lines.append(f"capture_time_known: {result.capture_time_known}")
    if result.error_code:
        lines.append(f"error: {result.error_code} -- {result.error_message}")
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    kwargs: dict[str, object] = {"force_reprocess": args.force_reprocess}
    if args.sample_fps is not None:
        kwargs["sample_fps"] = args.sample_fps
    if args.max_frames is not None:
        kwargs["max_frames"] = args.max_frames
    if args.pipeline_version is not None:
        kwargs["pipeline_version"] = args.pipeline_version

    repository = ProductRepository()
    try:
        result = asyncio.run(
            run_offline_video_ingest(repository, media_asset_id=args.media_asset_id, **kwargs)
        )
    except OfflineIngestError as error:
        print(f"error: {error}")
        return 1
    finally:
        repository.close()

    if args.json:
        print(json.dumps(
            {
                "run_id": result.run_id, "status": result.status, "media_asset_id": result.media_asset_id,
                "stream_id": result.stream_id, "pipeline_version": result.pipeline_version,
                "sample_fps": result.sample_fps, "frames_considered": result.frames_considered,
                "frames_analyzed": result.frames_analyzed, "events_created": result.events_created,
                "visits_created": result.visits_created, "visit_ids": list(result.visit_ids),
                "event_ids": list(result.event_ids), "source_duration_seconds": result.source_duration_seconds,
                "truncated": result.truncated, "capture_time_known": result.capture_time_known,
                "error_code": result.error_code, "error_message": result.error_message,
            },
            indent=2,
        ))
    else:
        print(render_human(result))
    return 0 if result.status in ("completed", "already_processed") else 1
