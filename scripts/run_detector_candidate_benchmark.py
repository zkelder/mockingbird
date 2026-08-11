#!/usr/bin/env python3
"""Run one detector candidate against one preserved-image manifest.

This is a benchmark adapter, not a production provider.  It keeps third-party
runtimes behind one source-pixel contract, applies the accepted MockingBird
full-frame or uniform-tile input strategy, and writes normalized detections and
non-semantic timing/resource facts.  It never opens the product database or
changes Observation Engine authority.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import platform
import sys
import time
import types
from typing import Any, Protocol

from PIL import Image

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation.detector_promotion import NormalizedCandidateDetection, intersection_over_union
from mockingbird.observation.multi_scale_strategy import (
    FULL_FRAME,
    FULL_FRAME_PLUS_UNIFORM_TILES,
    SCORE_DECIMALS,
    StrategyWindow,
    map_window_box_to_source,
    windows_for_frame,
)
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle

SCHEMA_VERSION = 1
RUNNER_VERSION = "detector-candidate-runner-v2"
STRATEGIES = {
    FULL_FRAME.strategy_key: FULL_FRAME,
    FULL_FRAME_PLUS_UNIFORM_TILES.strategy_key: FULL_FRAME_PLUS_UNIFORM_TILES,
}
ANIMAL_LABELS = {"animal", "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
VEHICLE_LABELS = {"vehicle", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"}


class Adapter(Protocol):
    def load(self) -> None: ...
    def infer(self, payload: bytes) -> tuple[list[dict[str, Any]], dict[str, float | None]]: ...
    def close(self) -> None: ...


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _gpu_facts() -> dict[str, Any]:
    try:
        import torch
        return {
            "cuda_available": torch.cuda.is_available(),
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "allocated_mib": torch.cuda.memory_allocated() / 1048576 if torch.cuda.is_available() else None,
            "reserved_mib": torch.cuda.memory_reserved() / 1048576 if torch.cuda.is_available() else None,
            "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1048576 if torch.cuda.is_available() else None,
        }
    except Exception as error:
        return {"cuda_available": False, "probe_error": type(error).__name__}


def _sync_cuda() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.synchronize()
    except Exception:
        return


def _broad_class(label: str) -> str:
    normalized = label.strip().lower()
    if normalized in ANIMAL_LABELS:
        return "animal"
    if normalized == "person":
        return "person"
    if normalized in VEHICLE_LABELS:
        return "vehicle"
    return "other"


class Mdv5Adapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.bundle = OnnxModelBundle.load(Path(config["model_bundle"]))
        self.provider = OnnxCudaObservationProvider(bundle=self.bundle)
        self.ordinal = 0

    def load(self) -> None:
        self.provider.load()

    def infer(self, payload: bytes) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
        self.ordinal += 1
        packet = FramePacket(
            stream_id="detector-promotion-benchmark", media_asset_id=f"window-{self.ordinal}",
            captured_at=None, frame_id=f"window-{self.ordinal}", payload=payload,
        )
        started = time.perf_counter()
        detections = asyncio.run(self.provider.infer_frame(packet))
        total_ms = (time.perf_counter() - started) * 1000
        inference_ms = self.provider._latencies_ms[-1]  # benchmark timing; production API intentionally exposes aggregates
        rows = [
            {
                "native_label": item.class_source_label or item.label,
                "broad_class": "animal" if item.is_animal else _broad_class(item.label),
                "confidence": item.confidence,
                "box": item.bounding_box,
            }
            for item in detections if item.bounding_box is not None and item.confidence is not None
        ]
        return rows, {
            "preprocessing_ms": None, "inference_ms": inference_ms,
            "postprocessing_ms": None, "total_ms": total_ms,
            "combined_preprocessing_postprocessing_ms": max(0.0, total_ms - inference_ms),
        }

    def close(self) -> None:
        self.provider.finalize_replay()
        self.provider.close()


def _namespace_package(name: str, path: Path) -> None:
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


class Mdv6ApacheAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model: Any = None

    def load(self) -> None:
        root = Path(self.config["pytorchwildlife_root"]).resolve() / "PytorchWildlife"
        for name, relative in (
            ("PytorchWildlife", ""), ("PytorchWildlife.models", "models"),
            ("PytorchWildlife.models.detection", "models/detection"),
            ("PytorchWildlife.models.detection.rtdetr_apache", "models/detection/rtdetr_apache"),
            ("PytorchWildlife.data", "data"),
        ):
            _namespace_package(name, root / relative)
        # These two imports are used only by convenience result/download paths.
        # The benchmark passes local verified weights and reads tensors directly.
        sys.modules.setdefault("supervision", types.ModuleType("supervision"))
        wget = types.ModuleType("wget")
        wget.download = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("unexpected_weight_download"))  # type: ignore[attr-defined]
        sys.modules.setdefault("wget", wget)

        base = __import__(
            "PytorchWildlife.models.detection.rtdetr_apache.rtdetr_apache_base",
            fromlist=["RTDETRApacheBase"],
        )
        official_yaml_config = base.YAMLConfig

        def offline_yaml_config(path: str, **kwargs: Any) -> Any:
            # The complete MDV6 checkpoint supplies every backbone weight.  The
            # upstream config's `pretrained: true` causes an unnecessary network
            # initialization that is overwritten immediately afterward.
            return official_yaml_config(path, PResNet={"pretrained": False}, **kwargs)

        base.YAMLConfig = offline_yaml_config
        module = __import__(
            "PytorchWildlife.models.detection.rtdetr_apache.megadetectorv6_apache",
            fromlist=["MegaDetectorV6Apache"],
        )
        self.model = module.MegaDetectorV6Apache(
            weights=self.config["weights"], device=self.config.get("device", "cuda"),
            version=self.config["model_version"],
        )
        self.model.model.eval()

    def infer(self, payload: bytes) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
        import torch
        opened = time.perf_counter()
        with Image.open(BytesIO(payload)) as source:
            image = source.convert("RGB")
        width, height = image.size
        tensor = self.model.transform(image)[None].to(self.model.device)
        original_size = torch.tensor([width, height])[None].to(self.model.device)
        _sync_cuda()
        preprocessing_ms = (time.perf_counter() - opened) * 1000

        started = time.perf_counter()
        with torch.inference_mode():
            outputs = self.model.model.model(tensor)
        _sync_cuda()
        inference_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        with torch.inference_mode():
            labels, boxes, scores = self.model.model.postprocessor(outputs, original_size)
        _sync_cuda()
        postprocessing_ms = (time.perf_counter() - started) * 1000
        rows = []
        for label, box, score in zip(labels[0], boxes[0], scores[0]):
            confidence = float(score.item())
            if confidence < float(self.config["score_threshold"]):
                continue
            label_name = self.model.CLASS_NAMES[int(label.item())]
            raw_box = [float(value) for value in box.detach().cpu().tolist()]
            # Official postprocessing can extend a fraction of a pixel beyond
            # the source. Clamping is explicit and recorded in provenance.
            clamped = (
                max(0.0, min(float(width), raw_box[0])), max(0.0, min(float(height), raw_box[1])),
                max(0.0, min(float(width), raw_box[2])), max(0.0, min(float(height), raw_box[3])),
            )
            if clamped[2] <= clamped[0] or clamped[3] <= clamped[1]:
                continue
            rows.append({
                "native_label": label_name, "broad_class": _broad_class(label_name),
                "confidence": confidence,
                "box": (clamped[0] / width, clamped[1] / height, clamped[2] / width, clamped[3] / height),
            })
        total_ms = preprocessing_ms + inference_ms + postprocessing_ms
        return rows, {
            "preprocessing_ms": preprocessing_ms, "inference_ms": inference_ms,
            "postprocessing_ms": postprocessing_ms, "total_ms": total_ms,
            "combined_preprocessing_postprocessing_ms": preprocessing_ms + postprocessing_ms,
        }

    def close(self) -> None:
        self.model = None
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            return


class RfDetrAdapter:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model: Any = None

    def load(self) -> None:
        from rfdetr import RFDETRSmall
        self.model = RFDETRSmall(
            pretrain_weights=str(Path(self.config["weights"]).resolve()),
            device=self.config.get("device", "cuda"),
        )

    def infer(self, payload: bytes) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
        with Image.open(BytesIO(payload)) as source:
            image = source.convert("RGB")
        started = time.perf_counter()
        detections = self.model.predict(
            image, threshold=float(self.config["score_threshold"]), include_source_image=False,
        )
        _sync_cuda()
        total_ms = (time.perf_counter() - started) * 1000
        class_names = detections.data.get("class_name")
        rows = []
        for index, (box, confidence) in enumerate(zip(detections.xyxy, detections.confidence)):
            label = str(class_names[index]) if class_names is not None else str(int(detections.class_id[index]))
            rows.append({
                "native_label": label, "broad_class": _broad_class(label),
                "confidence": float(confidence), "pixel_box": tuple(float(value) for value in box),
            })
        width, height = image.size
        for row in rows:
            left, top, right, bottom = row.pop("pixel_box")
            row["box"] = (
                max(0.0, left) / width, max(0.0, top) / height,
                min(float(width), right) / width, min(float(height), bottom) / height,
            )
        return rows, {
            "preprocessing_ms": None, "inference_ms": None, "postprocessing_ms": None,
            "total_ms": total_ms, "combined_preprocessing_postprocessing_ms": None,
        }

    def close(self) -> None:
        self.model = None


def _adapter(config: dict[str, Any]) -> Adapter:
    adapter_type = config.get("adapter")
    if adapter_type == "mdv5-onnx-cuda":
        return Mdv5Adapter(config)
    if adapter_type == "mdv6-apache-pytorch":
        return Mdv6ApacheAdapter(config)
    if adapter_type == "rfdetr-pytorch":
        return RfDetrAdapter(config)
    raise ValueError("unsupported_candidate_adapter")


def _tile_payload(source: Image.Image, window: StrategyWindow) -> bytes:
    width, height = source.size
    left, top, right, bottom = window.source_box
    box = (
        max(0, min(width - 1, round(left * width))), max(0, min(height - 1, round(top * height))),
        max(1, min(width, round(right * width))), max(1, min(height, round(bottom * height))),
    )
    buffer = BytesIO()
    source.crop(box).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _merge(rows: list[dict[str, Any]], *, iou_threshold: float, maximum: int) -> tuple[list[dict[str, Any]], int]:
    ordered = sorted(
        rows,
        key=lambda row: (-round(float(row["confidence"]), SCORE_DECIMALS), str(row["broad_class"]), tuple(row["source_box"]), str(row["window_id"])),
    )
    kept: list[dict[str, Any]] = []
    suppressed = 0
    for row in ordered:
        duplicate = any(
            row["broad_class"] == existing["broad_class"]
            and intersection_over_union(tuple(row["source_box"]), tuple(existing["source_box"])) >= iou_threshold
            for existing in kept
        )
        if duplicate:
            suppressed += 1
        elif len(kept) < maximum:
            kept.append(row)
    return kept, suppressed


def _run_frame(
    adapter: Adapter, frame: dict[str, Any], strategy: Any, config: dict[str, Any],
) -> dict[str, Any]:
    path = Path(frame["image"])
    payload = path.read_bytes()
    if _sha256(path) != frame["content_hash"]:
        raise ValueError(f"frame_hash_mismatch:{frame['frame_id']}")
    with Image.open(BytesIO(payload)) as opened:
        opened.load()
        source = opened.convert("RGB")
    width, height = source.size
    if [width, height] != [frame["width"], frame["height"]]:
        raise ValueError(f"frame_dimensions_mismatch:{frame['frame_id']}")
    windows = windows_for_frame(strategy, source_width=width, source_height=height)
    all_rows: list[dict[str, Any]] = []
    timings: list[dict[str, float | None]] = []
    for window in windows:
        window_payload = payload if window.window_kind == "full_frame" else _tile_payload(source, window)
        rows, timing = adapter.infer(window_payload)
        timings.append(timing)
        for row in rows:
            source_box = map_window_box_to_source(window, tuple(row["box"]))
            normalized = NormalizedCandidateDetection(
                frame_id=frame["frame_id"], broad_class=row["broad_class"],
                confidence=float(row["confidence"]), source_box=source_box,
                native_label=row["native_label"], model_key=config["model_key"],
                model_version=config["model_version"], strategy_key=strategy.strategy_key,
                backend=config["backend"],
            )
            all_rows.append({
                **asdict(normalized), "window_id": window.window_id,
                "window_kind": window.window_kind,
            })
    kept, suppressed = _merge(
        all_rows, iou_threshold=strategy.cross_window_iou_threshold,
        maximum=strategy.max_final_detections,
    )
    return {
        "frame_id": frame["frame_id"], "content_hash": frame["content_hash"],
        "source_width": width, "source_height": height, "window_count": len(windows),
        "detections": kept, "cross_window_suppressed_count": suppressed,
        "timing": {
            "window_timings_ms": timings,
            "total_ms": sum(float(item["total_ms"] or 0) for item in timings),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-config", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.candidate_config.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    weights_path = Path(config.get("weights", config.get("model_bundle", "")))
    expected = config.get("weights_sha256")
    if expected and _sha256(weights_path) != expected:
        raise ValueError("candidate_weights_checksum_mismatch")
    strategy = STRATEGIES[args.strategy]
    adapter = _adapter(config)
    before = _gpu_facts()
    started = time.perf_counter()
    adapter.load()
    _sync_cuda()
    startup_ms = (time.perf_counter() - started) * 1000
    loaded = _gpu_facts()
    results = []
    frame_timings: dict[str, dict[str, object]] = {}
    try:
        for frame in sorted(manifest["frames"], key=lambda item: item["frame_id"]):
            result = _run_frame(adapter, frame, strategy, config)
            frame_timings[result["frame_id"]] = result.pop("timing")
            results.append(result)
    finally:
        peak = _gpu_facts()
        adapter.close()
    semantic = {
        "schema_version": SCHEMA_VERSION, "runner_version": RUNNER_VERSION,
        "candidate": config, "strategy": asdict(strategy),
        "corpus_id": manifest["corpus_id"], "corpus_fingerprint": manifest["semantic_fingerprint"],
        "frames": results, "creates_truth": False, "changes_production_authority": False,
    }
    fingerprint = sha256(json.dumps(semantic, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output = {
        **semantic, "semantic_fingerprint": fingerprint,
        "execution": {
            "python": platform.python_version(), "platform": platform.platform(),
            "startup_ms": startup_ms, "gpu_before": before, "gpu_loaded": loaded,
            "gpu_peak": peak, "model_size_bytes": weights_path.stat().st_size,
            "frame_timings_ms": frame_timings,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(args.output, fingerprint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
