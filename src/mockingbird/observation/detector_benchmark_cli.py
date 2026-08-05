"""Command entry point for the offline, shadow-only detector-calibration
precision/recall benchmark (Observation Engine v2 Stage 6.2).

python -m mockingbird detector-benchmark \\
  --provider onnx-cuda \\
  --provider-config <ignored-provider-config.json> \\
  --frames <ignored-frame-directory> \\
  --manifest <ignored-reviewed-manifest.json> \\
  --output <output-directory>

This command opens no product database, starts no camera/Camera Node/worker,
and writes only the one deterministic report file into the requested output
directory. See docs/detector-calibration-benchmark-contract.md.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from pathlib import Path
import subprocess
from time import perf_counter
from typing import Any
import sys

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation.detector_benchmark import (
    DetectorBenchmarkError,
    anchor_score_threshold,
    build_semantic_report,
    classify_recommendations,
    classify_sample_sufficiency,
    cluster_static_false_positives,
    compare_preprocessing,
    effective_threshold_grid,
    simulate_temporal_policies,
    sweep_thresholds,
)
from mockingbird.observation.detector_benchmark_io import (
    load_calibration_manifest,
    write_detector_benchmark_report,
)
from mockingbird.observation.onnx_provider import (
    PROVIDER_VERSION as ONNX_CUDA_PROVIDER_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.replay import ReplayValidationError

LIMITATIONS = (
    "offline reviewed-cohort detector precision/recall calibration only",
    "no camera, Camera Node, live monitoring, worker, or product database is started or opened",
    "diagnostic evidence only: no threshold, Ignore-region, or tracker mutation",
    "no production Visit-proposal authority; shadow-only",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the offline, shadow-only detector precision/recall calibration benchmark."
    )
    parser.add_argument("--provider", required=True, choices=("onnx-cuda",), help="Registered detector provider id.")
    parser.add_argument("--provider-config", required=True, type=Path, help="Existing ONNX model-bundle JSON.")
    parser.add_argument("--frames", required=True, type=Path, help="Directory containing manifest-named JPEG/PNG frames.")
    parser.add_argument("--manifest", required=True, type=Path, help="Versioned reviewed calibration manifest JSON.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    parser.add_argument(
        "--thresholds", type=str, default=None,
        help="Optional comma-separated bounded score-threshold grid override; defaults to a fixed general grid.",
    )
    return parser


def _frame_packet(frame: Any, root: Path) -> FramePacket:
    return FramePacket(
        stream_id="detector-calibration",
        media_asset_id=f"calibration:{frame.frame_id}",
        captured_at=None,
        frame_id=frame.frame_id,
        source_offset_ms=frame.source_offset_ms or 0,
        width=frame.width,
        height=frame.height,
        source_path=str(root / frame.image_path),
    )


def _gpu_memory_used_mib() -> float | None:
    """Best-effort, side-effect-free `nvidia-smi` read; a resource fact only
    (never semantic). Returns None rather than raising when unavailable."""

    try:
        output = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        return float(output.stdout.strip().splitlines()[0])
    except Exception:
        return None


async def _detect(bundle: OnnxModelBundle, frames: tuple[FramePacket, ...]) -> tuple[dict[str, tuple[Any, ...]], OnnxCudaObservationProvider]:
    provider = OnnxCudaObservationProvider(bundle=bundle)
    provider.load()
    results = await provider.replay_frames(frames)
    detections_by_frame = {
        packet.frame_id: result.detection_observations
        for packet, result in zip(frames, results)
    }
    return detections_by_frame, provider


async def _run(args: argparse.Namespace) -> int:
    manifest, root = load_calibration_manifest(args.frames, args.manifest)
    bundle = OnnxModelBundle.load(args.provider_config)
    configured_threshold = bundle.score_threshold

    if args.thresholds:
        try:
            requested = tuple(float(item) for item in args.thresholds.split(","))
        except ValueError as error:
            raise DetectorBenchmarkError("invalid_thresholds_argument") from error
    else:
        from mockingbird.observation.detector_benchmark import DEFAULT_THRESHOLD_GRID
        requested = DEFAULT_THRESHOLD_GRID
    thresholds = effective_threshold_grid(configured_threshold, requested)
    anchor = anchor_score_threshold(thresholds)

    frame_packets = tuple(_frame_packet(frame, root) for frame in sorted(manifest.frames, key=lambda item: item.frame_id))

    anchor_bundle = replace(bundle, score_threshold=anchor)
    gpu_memory_before_mib = _gpu_memory_used_mib()
    started = perf_counter()
    detections_by_frame, provider = await _detect(anchor_bundle, frame_packets)
    primary_duration_ms = round((perf_counter() - started) * 1000, 3)
    gpu_memory_after_mib = _gpu_memory_used_mib()
    primary_execution_facts = provider.execution_facts()
    provider.close()

    sweep = sweep_thresholds(manifest, detections_by_frame, thresholds, configured_threshold=configured_threshold)
    static_report = cluster_static_false_positives(manifest, detections_by_frame, threshold=configured_threshold)
    temporal_results = simulate_temporal_policies(manifest, detections_by_frame, threshold=configured_threshold)

    alternative_mode = "stretch" if bundle.resize_mode == "letterbox" else "letterbox"
    preprocessing_unsupported_reason = None
    alternative_row = None
    alternative_execution_facts: dict[str, object] = {}
    alternative_duration_ms = 0.0
    try:
        alternative_bundle = replace(anchor_bundle, resize_mode=alternative_mode)
    except Exception as error:  # pragma: no cover - defensive; resize_mode is always the fixed choice set
        alternative_bundle = None
        preprocessing_unsupported_reason = f"could not construct an alternative bundle: {error}"
    if alternative_bundle is not None:
        started = perf_counter()
        alternative_detections, alternative_provider = await _detect(alternative_bundle, frame_packets)
        alternative_duration_ms = round((perf_counter() - started) * 1000, 3)
        alternative_execution_facts = alternative_provider.execution_facts()
        alternative_provider.close()
        alternative_sweep = sweep_thresholds(
            manifest, alternative_detections, (configured_threshold,), configured_threshold=configured_threshold,
        )
        alternative_row = alternative_sweep[0]

    configured_row = next(row for row in sweep if row.is_configured_threshold)
    preprocessing = compare_preprocessing(
        configured_row, alternative_row,
        primary_resize_mode=bundle.resize_mode, alternative_resize_mode=alternative_mode,
        unsupported_reason=preprocessing_unsupported_reason,
    )

    sufficiency = classify_sample_sufficiency(manifest)
    recommendations = classify_recommendations(
        sweep=sweep, static_report=static_report, temporal_results=temporal_results,
        preprocessing=preprocessing, sufficiency=sufficiency,
    )

    provider_semantic = {
        "provider_key": "onnx-cuda",
        "provider_version": ONNX_CUDA_PROVIDER_VERSION,
        "model": {
            "key": bundle.model_key, "version": bundle.model_version,
            "fingerprint": bundle.model_fingerprint, "bundle_fingerprint": bundle.fingerprint,
            "source_model_fingerprint": bundle.source_model_fingerprint,
            "model_format": bundle.model_format,
            "decoder": bundle.decoder_key, "broad_classes": list(bundle.broad_classes),
            "animal_classes": list(bundle.animal_classes),
            "input_width": bundle.input_width, "input_height": bundle.input_height,
            "primary_resize_mode": bundle.resize_mode,
            "license": bundle.license_name,
            "redistribution": bundle.redistribution,
            "taxonomy": bundle.taxonomy,
            "provenance": bundle.provenance,
            "bundle_limitations": list(bundle.limitations),
        },
        "anchor_score_threshold": anchor,
        "limitations": list(LIMITATIONS),
        "shadow_mode": True,
    }

    semantic = build_semantic_report(
        manifest=manifest, configured_threshold=configured_threshold, thresholds=thresholds,
        sweep=sweep, static_report=static_report, temporal_results=temporal_results,
        preprocessing=preprocessing, sufficiency=sufficiency, recommendations=recommendations,
        provider=provider_semantic,
    )
    execution = {
        "mode": "offline",
        "primary_pass_duration_ms": primary_duration_ms,
        "alternative_preprocessing_pass_duration_ms": alternative_duration_ms,
        "primary_execution_facts": primary_execution_facts,
        "alternative_preprocessing_execution_facts": alternative_execution_facts,
        "model_size_bytes": bundle.model_path.stat().st_size,
        "gpu_memory_before_mib": gpu_memory_before_mib,
        "gpu_memory_after_mib": gpu_memory_after_mib,
        "gpu_memory_delta_mib": (
            gpu_memory_after_mib - gpu_memory_before_mib
            if gpu_memory_before_mib is not None and gpu_memory_after_mib is not None else None
        ),
    }
    report_path = write_detector_benchmark_report(args.output, semantic, execution=execution)
    print(f"Detector benchmark report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    return 0


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except (DetectorBenchmarkError, ReplayValidationError) as error:
        print(f"Detector benchmark rejected: {error}", file=sys.stderr)
        return {
            "unsafe_output_path": 6,
            "nonempty_output_directory": 7,
            "onnx_cuda_unavailable": 10,
            "onnx_cuda_no_fallback": 10,
            "onnx_cuda_session_load_failed": 11,
            "onnx_cuda_inference_failed": 12,
            "onnx_cuda_mixed_execution": 13,
            "onnx_cuda_verification_insufficient": 14,
        }.get(str(error), 2)


def main() -> None:
    raise SystemExit(run())
