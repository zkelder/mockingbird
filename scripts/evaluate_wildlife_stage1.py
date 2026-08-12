#!/usr/bin/env python3
"""Evaluate the trained Stage-1 wildlife detector without touching production."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image

from mockingbird.training.wildlife import (
    EvaluationBox,
    evaluate_detections,
    intersection_over_union,
    sha256_file,
    source_pixel_size_bucket,
)
from run_detector_candidate_benchmark import Mdv5Adapter

THRESHOLDS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.3, 0.5, 0.7)
STAGE1_FINGERPRINT = "df1edfe3df4b5287ddad3702312a8fb7f1aa273ae26827818bb42b56be773b8d"
FROZEN_FINGERPRINT = "24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec"


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"invalid_json_object:{path.name}")
    return payload


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/training/wildlife-stage1"),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path(
            "data/training/wildlife-stage1/experiments/"
            "rfdetr-small-stage1-proof/checkpoint_best_total.pth"
        ),
    )
    parser.add_argument(
        "--frozen-manifest",
        type=Path,
        default=Path("data/evaluations/detector-promotion-v1/corpus-manifest.json"),
    )
    parser.add_argument(
        "--diagnostic-manifest",
        type=Path,
        default=Path("data/evaluations/detector-promotion-v1/diagnostic-manifest.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training/wildlife-stage1/evaluation-report.json"),
    )
    return parser.parse_args()


def _clamped_box(
    box: Sequence[float], width: int, height: int
) -> tuple[float, float, float, float] | None:
    left, top, right, bottom = (float(value) for value in box)
    normalized = (
        max(0.0, min(1.0, left / width)),
        max(0.0, min(1.0, top / height)),
        max(0.0, min(1.0, right / width)),
        max(0.0, min(1.0, bottom / height)),
    )
    return (
        normalized
        if normalized[2] > normalized[0] and normalized[3] > normalized[1]
        else None
    )


def _rfdetr_predictions(
    model: Any,
    cases: Iterable[tuple[str, Path]],
    *,
    threshold: float = min(THRESHOLDS),
) -> tuple[dict[str, list[EvaluationBox]], dict[str, float]]:
    results: dict[str, list[EvaluationBox]] = {}
    timings: dict[str, float] = {}
    for frame_id, path in cases:
        with Image.open(path) as source:
            image = source.convert("RGB")
        width, height = image.size
        started = time.perf_counter()
        detections = model.predict(
            image, threshold=threshold, include_source_image=False
        )
        timings[frame_id] = (time.perf_counter() - started) * 1000
        rows: list[EvaluationBox] = []
        for box, confidence in zip(detections.xyxy, detections.confidence):
            normalized = _clamped_box(box, width, height)
            if normalized is not None:
                rows.append(EvaluationBox(normalized, confidence=float(confidence)))
        results[frame_id] = rows
    return results, timings


def _mdv5_predictions(
    adapter: Mdv5Adapter,
    cases: Iterable[tuple[str, Path]],
) -> dict[str, list[EvaluationBox]]:
    results: dict[str, list[EvaluationBox]] = {}
    for frame_id, path in cases:
        rows, _ = adapter.infer(path.read_bytes())
        results[frame_id] = [
            EvaluationBox(tuple(item["box"]), confidence=float(item["confidence"]))
            for item in rows
            if item["broad_class"] == "animal"
        ]
    return results


def _thresholded(
    predictions: Mapping[str, Sequence[EvaluationBox]],
    threshold: float,
) -> dict[str, list[EvaluationBox]]:
    return {
        frame_id: [item for item in rows if (item.confidence or 0.0) >= threshold]
        for frame_id, rows in predictions.items()
    }


def _stage_validation(
    corpus: Path,
) -> tuple[dict[str, list[EvaluationBox]], list[tuple[str, Path]], dict[str, Any]]:
    manifest = _read(corpus / "stage1-manifest.json")
    if manifest.get("semantic_fingerprint") != STAGE1_FINGERPRINT:
        raise ValueError("stage1_fingerprint_mismatch")
    examples = {item["example_id"]: item for item in manifest["examples"]}
    coco = _read(corpus / "dataset" / "valid" / "_annotations.coco.json")
    images = {item["id"]: item for item in coco["images"]}
    truth: dict[str, list[EvaluationBox]] = {
        item["mockingbird_example_id"]: [] for item in images.values()
    }
    for item in coco["annotations"]:
        image = images[item["image_id"]]
        frame_id = image["mockingbird_example_id"]
        x, y, width, height = (float(value) for value in item["bbox"])
        truth[frame_id].append(
            EvaluationBox(
                (
                    x / image["width"],
                    y / image["height"],
                    (x + width) / image["width"],
                    (y + height) / image["height"],
                ),
                taxon=item["source_taxon"],
                size_bucket=item["source_pixel_size_bucket"],
            )
        )
    cases = [
        (
            item["mockingbird_example_id"],
            corpus / "dataset" / "valid" / item["file_name"],
        )
        for item in images.values()
    ]
    validation_ids = {frame_id for frame_id, _ in cases}
    metadata = {
        "images": len(cases),
        "positive_images": sum(bool(truth[item]) for item in validation_ids),
        "negative_images": sum(not truth[item] for item in validation_ids),
        "source_distribution": dict(
            sorted(
                _count(examples[item]["source_id"] for item in validation_ids).items()
            )
        ),
    }
    return truth, cases, metadata


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for value in values:
        counts[value] += 1
    return counts


def _frozen_truth(
    manifest: dict[str, Any],
) -> tuple[dict[str, list[EvaluationBox]], list[tuple[str, Path]], dict[str, str]]:
    if manifest.get("semantic_fingerprint") != FROZEN_FINGERPRINT:
        raise ValueError("frozen_fingerprint_mismatch")
    truth: dict[str, list[EvaluationBox]] = {}
    cases: list[tuple[str, Path]] = []
    distances: dict[str, str] = {}
    for frame in manifest["frames"]:
        if frame.get("truth_status") != "reviewed_truth":
            continue
        boxes = frame.get("bird_boxes") or []
        if frame.get("animal_present") not in ("yes", "no"):
            continue
        if frame.get("animal_present") == "yes" and not boxes:
            continue
        frame_id = frame["frame_id"]
        truth[frame_id] = [
            EvaluationBox(
                tuple(box),
                taxon="bird",
                size_bucket=source_pixel_size_bucket(
                    (box[2] - box[0]) * frame["width"],
                    (box[3] - box[1]) * frame["height"],
                ),
            )
            for box in boxes
        ]
        cases.append((frame_id, Path(frame["image"])))
        if frame.get("distance"):
            distances[frame_id] = frame["distance"]
    return truth, cases, distances


def _preserved_mdv5_frozen() -> dict[str, list[EvaluationBox]]:
    run = _read(
        Path("data/evaluations/detector-promotion-v1/runs/mdv5-native-full-frame.json")
    )
    if (
        run["candidate"]["weights_sha256"]
        != ("b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc")
        or run["candidate"]["score_threshold"] != 0.1
    ):
        raise ValueError("production_mdv5_preserved_run_identity_mismatch")
    return {
        frame["frame_id"]: [
            EvaluationBox(
                tuple(item["source_box"]), confidence=float(item["confidence"])
            )
            for item in frame["detections"]
            if item["broad_class"] == "animal"
        ]
        for frame in run["frames"]
    }


def _distance_metrics(
    truth: Mapping[str, Sequence[EvaluationBox]],
    predictions: Mapping[str, Sequence[EvaluationBox]],
    distances: Mapping[str, str],
) -> dict[str, Any]:
    return {
        distance: evaluate_detections(
            {key: truth[key] for key, value in distances.items() if value == distance},
            predictions,
        )
        for distance in sorted(set(distances.values()))
    }


def _diagnostic_summary(
    manifest: dict[str, Any],
    predictions: Mapping[str, Sequence[EvaluationBox]],
) -> list[dict[str, Any]]:
    rows = []
    for frame in manifest["frames"]:
        roi = tuple(frame["bird_roi"])
        candidates = list(predictions.get(frame["frame_id"], ()))
        overlaps = [intersection_over_union(roi, item.box) for item in candidates]
        matched = [
            item.confidence
            for item, overlap in zip(candidates, overlaps)
            if overlap >= 0.5
        ]
        rows.append(
            {
                "frame_id": frame["frame_id"],
                "truth_status": "diagnostic_only",
                "detected_actual_bird": bool(matched),
                "best_bird_confidence": max(matched, default=None),
                "best_iou_with_agent_roi": max(overlaps, default=0.0),
                "animal_detection_count": len(candidates),
                "creates_population_metric": False,
            }
        )
    return rows


def main() -> int:
    args = _args()
    resume = _read(args.checkpoint.parent / "resume-result.json")
    checkpoint_sha = sha256_file(args.checkpoint)
    inventory = {item["name"]: item["sha256"] for item in resume["checkpoints"]}
    if inventory.get(args.checkpoint.name) != checkpoint_sha:
        raise ValueError("checkpoint_inventory_mismatch")

    stage_truth, stage_cases, stage_metadata = _stage_validation(args.corpus)
    frozen_manifest = _read(args.frozen_manifest)
    frozen_truth, frozen_cases, distances = _frozen_truth(frozen_manifest)
    diagnostic_manifest = _read(args.diagnostic_manifest)
    diagnostic_cases = [
        (frame["frame_id"], Path(frame["image"]))
        for frame in diagnostic_manifest["frames"]
    ]

    from rfdetr import RFDETRSmall
    import torch

    model = RFDETRSmall(
        pretrain_weights=str(args.checkpoint.resolve()),
        resolution=640,
        device="cuda",
    )
    stage_rf, stage_timing = _rfdetr_predictions(model, stage_cases)
    sweep = [
        {
            "threshold": threshold,
            "metrics": evaluate_detections(
                stage_truth, _thresholded(stage_rf, threshold)
            ),
        }
        for threshold in THRESHOLDS
    ]
    selected = max(
        sweep,
        key=lambda row: (
            row["metrics"]["f1"],
            row["metrics"]["precision"],
            row["threshold"],
        ),
    )
    selected_threshold = selected["threshold"]
    frozen_rf_raw, frozen_timing = _rfdetr_predictions(model, frozen_cases)
    diagnostic_rf_raw, _ = _rfdetr_predictions(model, diagnostic_cases)
    frozen_rf = _thresholded(frozen_rf_raw, selected_threshold)
    diagnostic_rf = _thresholded(diagnostic_rf_raw, selected_threshold)
    del model
    torch.cuda.empty_cache()

    mdv5_config = _read(
        Path("data/evaluations/detector-promotion-v1/mdv5-native-config.json")
    )
    mdv5 = Mdv5Adapter(mdv5_config)
    mdv5.load()
    try:
        stage_mdv5 = _mdv5_predictions(mdv5, stage_cases)
        diagnostic_mdv5 = _mdv5_predictions(mdv5, diagnostic_cases)
    finally:
        mdv5.close()
    frozen_mdv5 = _preserved_mdv5_frozen()

    report = {
        "schema_version": 1,
        "report_version": "wildlife-stage1-evaluation-v0.1",
        "completed_at": datetime.now(UTC).isoformat(),
        "model": {
            "architecture": "RF-DETR Small",
            "checkpoint": args.checkpoint.name,
            "checkpoint_sha256": checkpoint_sha,
            "resolution": 640,
            "selected_threshold": selected_threshold,
            "threshold_selection_basis": "maximum F1 on Stage-1 validation only",
        },
        "stage1_validation": {
            "metadata": stage_metadata,
            "threshold_sweep": sweep,
            "rfdetr_selected": selected["metrics"],
            "production_mdv5_unchanged_0_1": evaluate_detections(
                stage_truth, stage_mdv5
            ),
        },
        "frozen_mockingbird_75": {
            "manifest_fingerprint": FROZEN_FINGERPRINT,
            "scorable_frames": len(frozen_truth),
            "rfdetr": evaluate_detections(frozen_truth, frozen_rf),
            "production_mdv5_unchanged_0_1": evaluate_detections(
                frozen_truth, frozen_mdv5
            ),
            "rfdetr_distance_breakdown": _distance_metrics(
                frozen_truth, frozen_rf, distances
            ),
            "production_mdv5_distance_breakdown": _distance_metrics(
                frozen_truth,
                frozen_mdv5,
                distances,
            ),
        },
        "latest_diagnostic_birds": {
            "denominator_policy": "diagnostic_only; excluded from population metrics",
            "rfdetr": _diagnostic_summary(diagnostic_manifest, diagnostic_rf),
            "production_mdv5_unchanged_0_1": _diagnostic_summary(
                diagnostic_manifest,
                diagnostic_mdv5,
            ),
        },
        "runtime": {
            "cuda_device": torch.cuda.get_device_name(0),
            "stage1_rfdetr_median_ms": sorted(stage_timing.values())[
                len(stage_timing) // 2
            ],
            "frozen_rfdetr_median_ms": sorted(frozen_timing.values())[
                len(frozen_timing) // 2
            ],
        },
        "creates_product_truth": False,
        "changes_production_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
