"""Command entry point for the offline, shadow-only replay benchmark."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
import json
import sys

from mockingbird.monitoring.source_monitor import SourceMonitorManager
from mockingbird.observation.registry import ObservationEngineRegistry
from mockingbird.observation.replay import ReplayRunner, ReplayValidationError
from mockingbird.observation.replay_io import load_replay_bundle, write_replay_report
from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

LIMITATIONS = (
    "offline ordered-frame replay only",
    "snapshot compatibility provider emits evidence but no replay visit proposals",
    "no cameras, Camera Node, workers, models, durable product objects, or truth are started or written",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline shadow-only Observation Engine replay benchmark.")
    parser.add_argument("--provider", required=True, help="Registered Observation Engine provider id.")
    parser.add_argument("--frames", required=True, type=Path, help="Directory containing manifest-named JPEG/PNG frames.")
    parser.add_argument("--manifest", required=True, type=Path, help="Versioned replay benchmark JSON manifest.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


async def _unused_capture(*_args: object) -> object:
    raise AssertionError("Replay must not capture a camera frame.")


async def _unused_images(*_args: object) -> list[str]:
    raise AssertionError("Replay must not list managed media.")


async def _unused_motion(*_args: object) -> object:
    raise AssertionError("Replay must not run the snapshot motion path.")


async def _run(args: argparse.Namespace) -> int:
    bundle = load_replay_bundle(args.frames, args.manifest)
    provider = SnapshotObservationProvider(SourceMonitorManager(
        capture_snapshot=_unused_capture, list_saved_images=_unused_images, evaluate_saved_media=_unused_motion,
    ))
    registry = ObservationEngineRegistry([provider], active_provider_id=provider.provider_id)
    if args.provider != registry.active_provider_id:
        raise ReplayValidationError("unsupported_provider")
    descriptor = await registry.status(stream_id=bundle.replay.stream_id)
    report = await ReplayRunner({provider.provider_id: registry.active_provider}).run(
        bundle.replay, bundle.manifest, provider_key=args.provider, thresholds=bundle.thresholds,
    )
    provider_contract = asdict(descriptor.provider)
    provider_contract["version"] = "snapshot-compatibility-v1"
    report_path = write_replay_report(args.output, report, replay=bundle.replay, manifest=bundle.manifest,
        provider=provider_contract, limitations=LIMITATIONS, execution={"mode": "offline"})
    unsuccessful = any(item["state"] in {"fail", "unscorable"} for item in report.threshold_results)
    written_fingerprint = json.loads(report_path.read_text(encoding="utf-8"))["semantic_fingerprint"]
    print(f"Replay report written to {report_path}; semantic fingerprint {written_fingerprint}.")
    return 3 if unsuccessful else 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except ReplayValidationError as error:
        print(f"Replay benchmark rejected: {error}", file=sys.stderr)
        return {"unsupported_provider": 4, "provider_failure": 5, "unsafe_output_path": 6, "nonempty_output_directory": 7, "production_authority": 8}.get(str(error), 2)


def main() -> None:
    raise SystemExit(run())
