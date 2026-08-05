"""Command entry points for the offline, shadow-only multi-scale detector
benchmark and strategy comparison (Observation Engine v2 Stage 6.4).

python -m mockingbird multi-scale-benchmark \\
  --strategy {full_frame,full_frame_plus_uniform_tiles} \\
  --provider onnx-cuda \\
  --provider-config <ignored-provider-config.json> \\
  --frames <ignored-frame-directory> \\
  --manifest <ignored-reviewed-manifest.json> \\
  --output <output-directory>

python -m mockingbird multi-scale-comparison \\
  --baseline-report <full_frame report.json> \\
  --candidate-report <full_frame_plus_uniform_tiles report.json> \\
  --output <output-directory>

Neither command opens a product database, starts a camera/Camera Node/worker,
or writes anything besides the one deterministic report file into the
requested output directory. See docs/multi-scale-detector-benchmark-contract.md.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
from io import BytesIO
from pathlib import Path
import resource
import subprocess
from time import perf_counter
from typing import Any
import sys

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation.detector_benchmark import DetectorBenchmarkError
from mockingbird.observation.multi_scale_benchmark import (
    MultiScaleBenchmarkError,
    build_multi_scale_semantic_report,
    compare_strategy_reports,
    merge_frame_windows,
)
from mockingbird.observation.multi_scale_benchmark_io import (
    load_calibration_manifest,
    load_multi_scale_benchmark_report,
    write_multi_scale_benchmark_report,
    write_multi_scale_comparison_report,
)
from mockingbird.observation.multi_scale_strategy import (
    STRATEGIES,
    StrategyWindow,
    remap_regions_to_window,
    windows_for_frame,
)
from mockingbird.observation.onnx_provider import (
    PROVIDER_VERSION as ONNX_CUDA_PROVIDER_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.replay import ReplayValidationError

LIMITATIONS = (
    "offline reviewed-cohort multi-scale detector benchmark only",
    "no camera, Camera Node, live monitoring, worker, or product database is started or opened",
    "diagnostic evidence only: no threshold, Ignore-region, tracker, or default-provider mutation",
    "no production Visit-proposal authority; shadow-only",
)
_STRATEGIES_BY_KEY = {strategy.strategy_key: strategy for strategy in STRATEGIES}

_ERROR_EXIT_CODES = {
    "unsafe_output_path": 6,
    "nonempty_output_directory": 7,
    "unsafe_report_path": 6,
    "invalid_report_json": 6,
    "onnx_cuda_unavailable": 10,
    "onnx_cuda_no_fallback": 10,
    "onnx_cuda_session_load_failed": 11,
    "onnx_cuda_inference_failed": 12,
    "onnx_cuda_mixed_execution": 13,
    "onnx_cuda_verification_insufficient": 14,
}


def _benchmark_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the offline, shadow-only multi-scale detector benchmark for one strategy."
    )
    parser.add_argument("--strategy", required=True, choices=sorted(_STRATEGIES_BY_KEY), help="Registered multi-scale strategy key.")
    parser.add_argument("--provider", required=True, choices=("onnx-cuda",), help="Registered detector provider id.")
    parser.add_argument("--provider-config", required=True, type=Path, help="Existing ONNX model-bundle JSON.")
    parser.add_argument("--frames", required=True, type=Path, help="Directory containing manifest-named JPEG/PNG frames.")
    parser.add_argument("--manifest", required=True, type=Path, help="Versioned reviewed calibration manifest JSON.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    parser.add_argument(
        "--score-threshold", type=float, default=None,
        help="Optional explicit per-window score threshold override; defaults to the strategy's own preset value.",
    )
    return parser


def _comparison_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare two already-produced multi-scale-benchmark-report.json files.")
    parser.add_argument("--baseline-report", required=True, type=Path, help="Existing full_frame multi-scale-benchmark-report.json.")
    parser.add_argument("--candidate-report", required=True, type=Path, help="Existing candidate-strategy multi-scale-benchmark-report.json.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    return parser


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


def _crop_to_jpeg(image: Any, window: StrategyWindow) -> bytes:
    width, height = image.size
    left, top, right, bottom = window.source_box
    box = (
        max(0, min(width - 1, round(left * width))), max(0, min(height - 1, round(top * height))),
        max(1, min(width, round(right * width))), max(1, min(height, round(bottom * height))),
    )
    crop = image.crop(box)
    buffer = BytesIO()
    crop.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _window_packets(frame: Any, windows: tuple[StrategyWindow, ...], root: Path) -> dict[str, FramePacket]:
    """One `FramePacket` per window. The `full_frame` window reuses the
    original file path unchanged (byte-identical to the Stage 6.2 single-
    pass benchmark, no re-encoding); each `tile` window is cropped once from
    a single shared decode of the source image and re-encoded as its own
    JPEG payload, with Privacy/Ignore regions remapped into that window's
    own local space before being handed to the provider."""

    packets: dict[str, FramePacket] = {}
    tiles = [window for window in windows if window.window_kind == "tile"]
    decoded_image = None
    if tiles:
        from PIL import Image
        source = Image.open(root / frame.image_path)
        try:
            source.load()
            decoded_image = source.convert("RGB")
        finally:
            source.close()
    for window in windows:
        media_asset_id = f"multi-scale:{frame.frame_id}:{window.window_id}"
        if window.window_kind == "full_frame":
            packets[window.window_id] = FramePacket(
                stream_id="multi-scale-benchmark", media_asset_id=media_asset_id, captured_at=None,
                frame_id=frame.frame_id, source_offset_ms=frame.source_offset_ms or 0,
                width=frame.width, height=frame.height, source_path=str(root / frame.image_path),
                analysis_excluded_regions=frame.privacy_ignore_regions,
            )
        else:
            assert decoded_image is not None
            packets[window.window_id] = FramePacket(
                stream_id="multi-scale-benchmark", media_asset_id=media_asset_id, captured_at=None,
                frame_id=frame.frame_id, source_offset_ms=frame.source_offset_ms or 0,
                width=None, height=None, payload=_crop_to_jpeg(decoded_image, window),
                analysis_excluded_regions=remap_regions_to_window(window, frame.privacy_ignore_regions),
            )
    return packets


async def _run_benchmark(args: argparse.Namespace) -> int:
    manifest, root = load_calibration_manifest(args.frames, args.manifest)
    bundle = OnnxModelBundle.load(args.provider_config)
    strategy = _STRATEGIES_BY_KEY[args.strategy]
    if args.score_threshold is not None:
        strategy = replace(strategy, per_window_score_threshold=args.score_threshold)
    threshold = strategy.per_window_score_threshold

    ordered_frames = sorted(manifest.frames, key=lambda item: item.frame_id)
    windows_by_frame: dict[str, tuple[StrategyWindow, ...]] = {
        frame.frame_id: windows_for_frame(strategy, source_width=frame.width, source_height=frame.height)
        for frame in ordered_frames
    }

    keys: list[tuple[str, str]] = []
    packets: list[FramePacket] = []
    for frame in ordered_frames:
        frame_windows = windows_by_frame[frame.frame_id]
        window_packets = _window_packets(frame, frame_windows, root)
        for window in frame_windows:
            keys.append((frame.frame_id, window.window_id))
            packets.append(window_packets[window.window_id])

    scored_bundle = replace(bundle, score_threshold=threshold)
    provider = OnnxCudaObservationProvider(bundle=scored_bundle)
    provider.load()
    gpu_memory_before_mib = _gpu_memory_used_mib()
    before_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    started = perf_counter()
    results = await provider.replay_frames(tuple(packets))
    duration_ms = round((perf_counter() - started) * 1000, 3)
    after_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    gpu_memory_after_mib = _gpu_memory_used_mib()
    execution_facts = provider.execution_facts()
    provider.close()

    local_detections_by_frame: dict[str, dict[str, Any]] = {frame.frame_id: {} for frame in ordered_frames}
    for (frame_id, window_id), result in zip(keys, results):
        local_detections_by_frame[frame_id][window_id] = result.detection_observations

    kept_by_frame = {}
    suppressed_by_frame = {}
    windows_per_frame: dict[str, int] = {}
    for frame in ordered_frames:
        frame_windows = windows_by_frame[frame.frame_id]
        windows_per_frame[frame.frame_id] = len(frame_windows)
        kept, suppressed = merge_frame_windows(
            frame_windows, local_detections_by_frame[frame.frame_id],
            cross_window_iou_threshold=strategy.cross_window_iou_threshold,
            max_final_detections=strategy.max_final_detections,
        )
        kept_by_frame[frame.frame_id] = kept
        suppressed_by_frame[frame.frame_id] = suppressed

    provider_semantic = {
        "provider_key": "onnx-cuda", "provider_version": ONNX_CUDA_PROVIDER_VERSION,
        "model": {
            "key": bundle.model_key, "version": bundle.model_version,
            "fingerprint": bundle.model_fingerprint, "bundle_fingerprint": bundle.fingerprint,
            "source_model_fingerprint": bundle.source_model_fingerprint, "model_format": bundle.model_format,
            "decoder": bundle.decoder_key, "broad_classes": list(bundle.broad_classes),
            "animal_classes": list(bundle.animal_classes), "input_width": bundle.input_width,
            "input_height": bundle.input_height, "primary_resize_mode": bundle.resize_mode,
            "license": bundle.license_name, "redistribution": bundle.redistribution,
            "taxonomy": bundle.taxonomy, "provenance": bundle.provenance,
            "bundle_limitations": list(bundle.limitations),
        },
        "limitations": list(LIMITATIONS), "shadow_mode": True,
    }
    semantic = build_multi_scale_semantic_report(
        manifest=manifest, strategy=strategy, kept_by_frame=kept_by_frame,
        suppressed_by_frame=suppressed_by_frame, provider=provider_semantic,
    )
    execution = {
        "mode": "offline",
        "total_inference_calls": len(packets),
        "windows_per_frame": dict(sorted(windows_per_frame.items())),
        "max_windows_per_frame": strategy.max_windows_per_frame,
        "pass_duration_ms": duration_ms,
        "execution_facts": execution_facts,
        "process_peak_rss_kib_before": before_rss_kib,
        "process_peak_rss_kib_after": after_rss_kib,
        "gpu_memory_before_mib": gpu_memory_before_mib,
        "gpu_memory_after_mib": gpu_memory_after_mib,
    }
    report_path = write_multi_scale_benchmark_report(args.output, semantic, execution=execution)
    print(f"Multi-scale benchmark report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    return 0


def run_benchmark(argv: list[str] | None = None) -> int:
    args = _benchmark_parser().parse_args(argv)
    try:
        return asyncio.run(_run_benchmark(args))
    except (DetectorBenchmarkError, MultiScaleBenchmarkError, ReplayValidationError) as error:
        print(f"Multi-scale benchmark rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def run_comparison(argv: list[str] | None = None) -> int:
    args = _comparison_parser().parse_args(argv)
    try:
        baseline_report = load_multi_scale_benchmark_report(args.baseline_report)
        candidate_report = load_multi_scale_benchmark_report(args.candidate_report)
        semantic = compare_strategy_reports(baseline_report, candidate_report)
        execution = semantic.pop("execution")
        report_path = write_multi_scale_comparison_report(args.output, semantic, execution=execution)
        print(f"Multi-scale comparison report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
        print(
            f"  {semantic['baseline_strategy']} -> {semantic['candidate_strategy']}: "
            f"recall={semantic['recall']} precision={semantic['precision']} "
            f"small_subject_recall={semantic['small_subject_recall']} -> {semantic['final_recommendation']}"
        )
        return 0
    except MultiScaleBenchmarkError as error:
        print(f"Multi-scale comparison rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def main_benchmark() -> None:
    raise SystemExit(run_benchmark())


def main_comparison() -> None:
    raise SystemExit(run_comparison())
