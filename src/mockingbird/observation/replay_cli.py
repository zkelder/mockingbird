"""Command entry point for offline, shadow-only Observation Engine replay."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any
import json
import sys

from mockingbird.monitoring.source_monitor import SourceMonitorManager
from mockingbird.observation.onnx_provider import (
    PROVIDER_VERSION as ONNX_CUDA_PROVIDER_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.registry import ObservationEngineRegistry
from mockingbird.observation.replay import ReplayRunner, ReplayValidationError
from mockingbird.observation.replay_io import load_replay_bundle, write_replay_report
from mockingbird.observation.snapshot_provider import SnapshotObservationProvider

SNAPSHOT_LIMITATIONS = (
    "offline ordered-frame replay only",
    "snapshot compatibility provider emits evidence but no replay visit proposals",
    "no cameras, Camera Node, workers, models, durable product objects, or truth are started or written",
)
ONNX_CUDA_LIMITATIONS = (
    "offline ordered-frame replay detection inference only",
    "no tracking or Visit proposal authority",
    "CUDAExecutionProvider is mandatory; CPU fallback is prohibited",
    "no cameras, Camera Node, workers, durable product objects, or truth are started or written",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an offline shadow-only Observation Engine replay benchmark.")
    parser.add_argument("--provider", required=True, help="Registered Observation Engine provider id.")
    parser.add_argument("--frames", required=True, type=Path, help="Directory containing manifest-named JPEG/PNG frames.")
    parser.add_argument("--manifest", required=True, type=Path, help="Versioned replay benchmark JSON manifest.")
    parser.add_argument("--provider-config", type=Path, help="Explicit provider configuration, required by onnx-cuda.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


async def _unused_capture(*_args: object) -> object:
    raise AssertionError("Replay must not capture a camera frame.")


async def _unused_images(*_args: object) -> list[str]:
    raise AssertionError("Replay must not list managed media.")


async def _unused_motion(*_args: object) -> object:
    raise AssertionError("Replay must not run the snapshot motion path.")


def _configured_provider(args: argparse.Namespace) -> tuple[Any, tuple[str, ...]]:
    if args.provider == "snapshot":
        if args.provider_config is not None:
            raise ReplayValidationError("unexpected_provider_configuration")
        return SnapshotObservationProvider(SourceMonitorManager(
            capture_snapshot=_unused_capture,
            list_saved_images=_unused_images,
            evaluate_saved_media=_unused_motion,
        )), SNAPSHOT_LIMITATIONS
    if args.provider == "onnx-cuda":
        if args.provider_config is None:
            raise ReplayValidationError("provider_configuration_required")
        bundle = OnnxModelBundle.load(args.provider_config)
        return OnnxCudaObservationProvider(bundle=bundle), ONNX_CUDA_LIMITATIONS
    raise ReplayValidationError("unsupported_provider")


async def _run(args: argparse.Namespace) -> int:
    bundle = load_replay_bundle(args.frames, args.manifest)
    provider, limitations = _configured_provider(args)
    close = getattr(provider, "close", None)
    try:
        if isinstance(provider, OnnxCudaObservationProvider):
            provider.load()
        registry = ObservationEngineRegistry([provider], active_provider_id=provider.provider_id)
        descriptor = await registry.status(stream_id=bundle.replay.stream_id)
        started = perf_counter()
        report = await ReplayRunner({provider.provider_id: registry.active_provider}).run(
            bundle.replay, bundle.manifest, provider_key=args.provider, thresholds=bundle.thresholds,
        )
        duration_ms = round((perf_counter() - started) * 1000, 3)
        provider_contract = asdict(descriptor.provider)
        execution: dict[str, object] = {"mode": "offline", "total_execution_duration_ms": duration_ms}
        if isinstance(provider, OnnxCudaObservationProvider):
            metadata = provider.report_metadata()
            provider_contract.update({
                "provider_key": metadata["provider_key"],
                "version": ONNX_CUDA_PROVIDER_VERSION,
                "model_bundle_configured": metadata["model_bundle_configured"],
                "model_bundle_compatible": metadata["model_bundle_compatible"],
                "model": metadata["model"],
                "limitations": metadata["limitations"],
                "shadow_mode": True,
            })
            execution.update({
                "runtime_available": metadata["runtime_available"],
                "runtime_version": metadata["runtime_version"],
                "cuda_available": metadata["cuda_available"],
                "available_execution_providers": metadata["available_execution_providers"],
                "selected_execution_providers": metadata["selected_execution_providers"],
                "device_type": metadata["device_type"],
                "accelerator": metadata["accelerator"],
                **provider.execution_facts(),
            })
        else:
            provider_contract["version"] = "snapshot-compatibility-v1"
        report_path = write_replay_report(
            args.output, report, replay=bundle.replay, manifest=bundle.manifest,
            provider=provider_contract, limitations=limitations,
            execution=execution,
        )
    finally:
        if callable(close):
            close()
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
        return {
            "unsupported_provider": 4,
            "provider_failure": 5,
            "unsafe_output_path": 6,
            "nonempty_output_directory": 7,
            "production_authority": 8,
            "provider_configuration_required": 9,
            "unexpected_provider_configuration": 9,
            "onnx_cuda_unavailable": 10,
            "onnx_cuda_no_fallback": 10,
            "onnx_cuda_session_load_failed": 11,
            "onnx_cuda_inference_failed": 12,
            "onnx_cuda_mixed_execution": 13,
            "onnx_cuda_verification_insufficient": 14,
        }.get(str(error), 2)


def main() -> None:
    raise SystemExit(run())
