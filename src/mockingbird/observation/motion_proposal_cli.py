"""Command entry points for the offline, shadow-only adaptive motion-proposal
detector benchmark and three-way strategy decision (Observation Engine v2
Stage 6.5).

python -m mockingbird motion-proposal-benchmark \\
  --provider onnx-cuda \\
  --provider-config <ignored-provider-config.json> \\
  --frames <ignored-reviewed-temporal-cohort-frame-directory> \\
  --manifest <ignored-reviewed-temporal-cohort-manifest.json> \\
  --output <output-directory>

python -m mockingbird motion-proposal-decision \\
  --full-frame-report <full_frame multi-scale-benchmark-report.json> \\
  --uniform-tiles-report <full_frame_plus_uniform_tiles multi-scale-benchmark-report.json> \\
  --motion-proposal-report <motion-proposal-benchmark-report.json> \\
  --output <output-directory>

Neither command opens a product database, starts a camera/Camera Node/worker,
or writes anything besides the one deterministic report file into the
requested output directory. See
docs/adaptive-motion-proposal-benchmark-contract.md.
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
from mockingbird.observation.detector_benchmark import CalibrationFrame, CalibrationManifest, DetectorBenchmarkError
from mockingbird.observation.motion_proposal_benchmark import (
    MotionProposalBenchmarkError,
    build_adaptive_decision_report,
    build_motion_proposal_semantic_report,
    merge_frame_proposal_windows,
)
from mockingbird.observation.motion_proposal_io import (
    load_calibration_manifest,
    load_motion_proposal_report,
    write_motion_proposal_benchmark_report,
    write_motion_proposal_decision_report,
    decode_frame_plane,
)
from mockingbird.observation.motion_proposal_strategy import (
    FULL_FRAME_PLUS_MOTION_PROPOSALS,
    FrameIdentity,
    MotionProposalStrategyConfig,
    ProposalGenerationResult,
    generate_proposals,
)
from mockingbird.observation.multi_scale_strategy import StrategyWindow
from mockingbird.observation.onnx_provider import (
    PROVIDER_VERSION as ONNX_CUDA_PROVIDER_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.replay import ReplayValidationError

LIMITATIONS = (
    "offline reviewed-temporal-cohort adaptive motion-proposal detector benchmark only",
    "no camera, Camera Node, live monitoring, worker, or product database is started or opened",
    "diagnostic evidence only: no threshold, Ignore-region, tracker, or default-provider mutation",
    "no production Visit-proposal authority; shadow-only",
)

_ERROR_EXIT_CODES = {
    "unsafe_output_path": 6,
    "nonempty_output_directory": 7,
    "unsafe_report_path": 6,
    "invalid_report_json": 6,
    "undecodable_frame": 8,
    "onnx_cuda_unavailable": 10,
    "onnx_cuda_no_fallback": 10,
    "onnx_cuda_session_load_failed": 11,
    "onnx_cuda_inference_failed": 12,
    "onnx_cuda_mixed_execution": 13,
    "onnx_cuda_verification_insufficient": 14,
}


def _benchmark_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the offline, shadow-only adaptive motion-proposal detector benchmark."
    )
    parser.add_argument("--provider", required=True, choices=("onnx-cuda",), help="Registered detector provider id.")
    parser.add_argument("--provider-config", required=True, type=Path, help="Existing ONNX model-bundle JSON.")
    parser.add_argument("--frames", required=True, type=Path, help="Directory containing manifest-named JPEG/PNG frames.")
    parser.add_argument("--manifest", required=True, type=Path, help="Versioned reviewed temporal calibration manifest JSON.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    parser.add_argument(
        "--score-threshold", type=float, default=None,
        help="Optional explicit per-window score threshold override; defaults to the strategy's own preset value.",
    )
    return parser


def _decision_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare full_frame, full_frame_plus_uniform_tiles, and full_frame_plus_motion_proposals reports.")
    parser.add_argument("--full-frame-report", required=True, type=Path, help="Existing full_frame multi-scale-benchmark-report.json.")
    parser.add_argument("--uniform-tiles-report", required=True, type=Path, help="Existing full_frame_plus_uniform_tiles multi-scale-benchmark-report.json.")
    parser.add_argument("--motion-proposal-report", required=True, type=Path, help="Existing motion-proposal-benchmark-report.json.")
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


# --------------------------------------------------------------------------
# Sequence grouping and predecessor lookup (manifest-driven; mirrors
# `detector_benchmark._sequence_groups`'s own ordering convention so the
# reused temporal-policy simulation and this benchmark's own predecessor
# selection agree on what "in order" means for the same manifest).
# --------------------------------------------------------------------------


def _ordered_sequences(manifest: CalibrationManifest) -> dict[str, tuple[CalibrationFrame, ...]]:
    groups: dict[str, list[CalibrationFrame]] = {}
    for frame in manifest.frames:
        key = frame.sequence_id if frame.sequence_id is not None else f"__singleton__:{frame.frame_id}"
        groups.setdefault(key, []).append(frame)
    return {
        key: tuple(sorted(
            frames,
            key=lambda item: (
                item.sequence_order if item.sequence_order is not None else 0,
                item.source_offset_ms if item.source_offset_ms is not None else 0,
                item.frame_id,
            ),
        ))
        for key, frames in sorted(groups.items())
    }


def _predecessors_by_frame_id(manifest: CalibrationManifest) -> dict[str, CalibrationFrame | None]:
    """Every real (non-singleton) sequence's frame maps to the immediately
    preceding frame in that same sequence; a singleton or first-in-sequence
    frame maps to `None`."""

    result: dict[str, CalibrationFrame | None] = {}
    for key, ordered in _ordered_sequences(manifest).items():
        is_real_sequence = not key.startswith("__singleton__:")
        previous: CalibrationFrame | None = None
        for frame in ordered:
            result[frame.frame_id] = previous if is_real_sequence else None
            previous = frame
    return result


def _frame_identity(frame: CalibrationFrame) -> FrameIdentity:
    return FrameIdentity(
        frame_id=frame.frame_id, sequence_id=frame.sequence_id,
        source_offset_ms=frame.source_offset_ms, content_hash=frame.content_hash,
    )


# --------------------------------------------------------------------------
# Window/packet construction
# --------------------------------------------------------------------------


def _crop_to_jpeg(image: Any, box: tuple[float, float, float, float]) -> bytes:
    width, height = image.size
    left, top, right, bottom = box
    pixel_box = (
        max(0, min(width - 1, round(left * width))), max(0, min(height - 1, round(top * height))),
        max(1, min(width, round(right * width))), max(1, min(height, round(bottom * height))),
    )
    crop = image.crop(pixel_box)
    buffer = BytesIO()
    crop.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _proposal_packet(frame: CalibrationFrame, window: StrategyWindow, decoded_image: Any) -> FramePacket:
    from mockingbird.observation.multi_scale_strategy import remap_regions_to_window
    media_asset_id = f"motion-proposal:{frame.frame_id}:{window.window_id}"
    return FramePacket(
        stream_id="motion-proposal-benchmark", media_asset_id=media_asset_id, captured_at=None,
        frame_id=frame.frame_id, source_offset_ms=frame.source_offset_ms or 0,
        width=None, height=None, payload=_crop_to_jpeg(decoded_image, window.source_box),
        analysis_excluded_regions=remap_regions_to_window(window, frame.privacy_ignore_regions),
    )


def _full_frame_packet(frame: CalibrationFrame, root: Path) -> FramePacket:
    return FramePacket(
        stream_id="motion-proposal-benchmark", media_asset_id=f"motion-proposal:{frame.frame_id}:full_frame",
        captured_at=None, frame_id=frame.frame_id, source_offset_ms=frame.source_offset_ms or 0,
        width=frame.width, height=frame.height, source_path=str(root / frame.image_path),
        analysis_excluded_regions=frame.privacy_ignore_regions,
    )


async def _run_benchmark(args: argparse.Namespace) -> int:
    manifest, root = load_calibration_manifest(args.frames, args.manifest)
    bundle = OnnxModelBundle.load(args.provider_config)
    strategy: MotionProposalStrategyConfig = FULL_FRAME_PLUS_MOTION_PROPOSALS
    if args.score_threshold is not None:
        strategy = replace(strategy, per_window_score_threshold=args.score_threshold)
    threshold = strategy.per_window_score_threshold

    ordered_frames = sorted(manifest.frames, key=lambda item: item.frame_id)
    predecessors = _predecessors_by_frame_id(manifest)

    # -- proposal generation (pure; measured separately from detector latency) --
    proposal_started = perf_counter()
    frame_plane_cache: dict[str, object] = {}

    def _plane(frame_id: str) -> object:
        if frame_id not in frame_plane_cache:
            image_path = root / manifest.frame(frame_id).image_path
            frame_plane_cache[frame_id] = decode_frame_plane(
                image_path, comparison_width=strategy.comparison_width, comparison_height=strategy.comparison_height,
            )
        return frame_plane_cache[frame_id]

    proposal_results: dict[str, ProposalGenerationResult] = {}
    for frame in ordered_frames:
        predecessor_frame = predecessors.get(frame.frame_id)
        predecessor_plane = current_plane = None
        if predecessor_frame is not None:
            predecessor_plane = _plane(predecessor_frame.frame_id)
            current_plane = _plane(frame.frame_id)
        proposal_results[frame.frame_id] = generate_proposals(
            strategy,
            current=_frame_identity(frame),
            predecessor=_frame_identity(predecessor_frame) if predecessor_frame is not None else None,
            predecessor_plane=predecessor_plane, current_plane=current_plane,
            excluded_regions=frame.privacy_ignore_regions,
        )
    proposal_generation_latency_ms = round((perf_counter() - proposal_started) * 1000, 3)

    # -- window/packet construction --
    windows_by_frame: dict[str, tuple[StrategyWindow, ...]] = {}
    keys: list[tuple[str, str]] = []
    packets: list[FramePacket] = []
    for frame in ordered_frames:
        result = proposal_results[frame.frame_id]
        full_frame_window = StrategyWindow("full_frame", "full_frame", (0.0, 0.0, 1.0, 1.0))
        frame_windows = (full_frame_window, *(proposal.window for proposal in result.proposals))
        windows_by_frame[frame.frame_id] = frame_windows

        decoded_image = None
        if result.proposals:
            from PIL import Image
            source = Image.open(root / frame.image_path)
            try:
                source.load()
                decoded_image = source.convert("RGB")
            finally:
                source.close()

        for window in frame_windows:
            keys.append((frame.frame_id, window.window_id))
            packets.append(
                _full_frame_packet(frame, root) if window.window_kind == "full_frame"
                else _proposal_packet(frame, window, decoded_image)
            )

    scored_bundle = replace(bundle, score_threshold=threshold)
    provider = OnnxCudaObservationProvider(bundle=scored_bundle)
    provider.load()
    gpu_memory_before_mib = _gpu_memory_used_mib()
    before_rss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    detector_started = perf_counter()
    results = await provider.replay_frames(tuple(packets))
    detector_latency_ms = round((perf_counter() - detector_started) * 1000, 3)
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
        full_frame_window = frame_windows[0]
        kept, suppressed = merge_frame_proposal_windows(
            frame.frame_id, proposal_results[frame.frame_id], full_frame_window,
            local_detections_by_frame[frame.frame_id],
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
    max_windows_per_frame = 1 + strategy.max_proposals_per_frame
    semantic = build_motion_proposal_semantic_report(
        manifest=manifest, strategy=strategy, kept_by_frame=kept_by_frame,
        suppressed_by_frame=suppressed_by_frame, proposal_results=proposal_results,
        provider=provider_semantic,
    )
    total_latency_ms = round(proposal_generation_latency_ms + detector_latency_ms, 3)
    execution = {
        "mode": "offline",
        "total_inference_calls": len(packets),
        "windows_per_frame": dict(sorted(windows_per_frame.items())),
        "max_windows_per_frame": max_windows_per_frame,
        "proposal_generation_latency_ms": proposal_generation_latency_ms,
        "detector_latency_ms": detector_latency_ms,
        "total_frame_processing_latency_ms": total_latency_ms,
        "execution_facts": execution_facts,
        "process_peak_rss_kib_before": before_rss_kib,
        "process_peak_rss_kib_after": after_rss_kib,
        "gpu_memory_before_mib": gpu_memory_before_mib,
        "gpu_memory_after_mib": gpu_memory_after_mib,
    }
    report_path = write_motion_proposal_benchmark_report(args.output, semantic, execution=execution)
    print(f"Motion-proposal benchmark report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
    return 0


def run_benchmark(argv: list[str] | None = None) -> int:
    args = _benchmark_parser().parse_args(argv)
    try:
        return asyncio.run(_run_benchmark(args))
    except (DetectorBenchmarkError, MotionProposalBenchmarkError, ReplayValidationError) as error:
        print(f"Motion-proposal benchmark rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def run_decision(argv: list[str] | None = None) -> int:
    args = _decision_parser().parse_args(argv)
    try:
        full_frame_report = load_motion_proposal_report(args.full_frame_report)
        uniform_tiles_report = load_motion_proposal_report(args.uniform_tiles_report)
        motion_proposal_report = load_motion_proposal_report(args.motion_proposal_report)
        semantic = build_adaptive_decision_report(full_frame_report, uniform_tiles_report, motion_proposal_report)
        execution = semantic.pop("execution")
        report_path = write_motion_proposal_decision_report(args.output, semantic, execution=execution)
        print(f"Motion-proposal decision report written to {report_path}; semantic fingerprint {semantic['semantic_fingerprint']}.")
        print(f"  final_recommendation={semantic['final_recommendation']}")
        return 0
    except MotionProposalBenchmarkError as error:
        print(f"Motion-proposal decision rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def main_benchmark() -> None:
    raise SystemExit(run_benchmark())


def main_decision() -> None:
    raise SystemExit(run_decision())
