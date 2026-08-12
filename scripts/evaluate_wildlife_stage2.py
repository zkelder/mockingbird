#!/usr/bin/env python3
"""Compare governed Stage-2 RF-DETR with Stage 1 and unchanged MDv5."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import UTC, datetime
from io import BytesIO
import json
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image

from mockingbird.observation.onnx_provider import MAX_INPUT_PIXELS
from mockingbird.training.wildlife import EvaluationBox, evaluate_detections, sha256_file
import evaluate_wildlife_stage1 as stage1_eval
from run_detector_candidate_benchmark import Mdv5Adapter

THRESHOLDS = stage1_eval.THRESHOLDS
STAGE2_FINGERPRINT = "2261e716a398185ccb9def87d6555726da35c74c801169b8ac97483dce179af5"
STAGE2_SPLIT_FINGERPRINT = "18513c4e5f07f8c9d4e7eadfbbaf75d9745cbb4f593126b37aabe5add1adba92"
STAGE1_CHECKPOINT_SHA256 = "b14581ebb0eed43675a229acec304a71fbc0b50ff8640d26acd95ee7f1564d1a"
_ONNX_PROVIDER_SUPPORTED_FORMATS = frozenset({"JPEG", "PNG"})
_DOWNSCALE_SAFETY_MARGIN = 0.999  # headroom against rounding landing back at the cap


def _onnx_provider_compatible_bytes(path: Path) -> bytes:
    """Normalize a benchmark-corpus frame to what `onnx_provider._preprocess`
    (production code, left untouched) actually accepts, without changing
    what any model in this comparison sees relative to the others.

    Two real Stage-2 corpus conditions trip its checks, both because a
    third-party source's own camera differs from what a real MockingBird
    Camera Node produces, never because of anything about the model or
    detector under test:

    - MPO, the multi-picture-JPEG container some Oregon Critters
      trail-camera frames use. PIL opens and decodes it exactly like the
      RF-DETR side of this comparison already does
      (`Image.open(path).convert("RGB")`, both defaulting to the first
      embedded frame) -- only `_preprocess`'s format allowlist rejects it.
    - A handful of Oregon Critters frames (5280x3960, ~20.9MP) that exceed
      `MAX_INPUT_PIXELS` (16,777,216 px): a real, intentional production
      guard against unbounded decode/inference cost, not a bug -- resized
      down (whole scene, aspect ratio preserved) rather than the limit
      relaxed.
    """

    raw = path.read_bytes()
    with Image.open(BytesIO(raw)) as opened:
        width, height = opened.size
        if opened.format in _ONNX_PROVIDER_SUPPORTED_FORMATS and width * height <= MAX_INPUT_PIXELS:
            return raw
        image = opened.convert("RGB")
    if width * height > MAX_INPUT_PIXELS:
        scale = (MAX_INPUT_PIXELS / (width * height)) ** 0.5 * _DOWNSCALE_SAFETY_MARGIN
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus", type=Path, default=Path("data/training/wildlife-stage2")
    )
    parser.add_argument(
        "--stage2-checkpoint",
        type=Path,
        default=Path(
            "data/training/wildlife-stage2/experiments/"
            "rfdetr-small-stage2-v0.2/checkpoint_best_ema.pth"
        ),
    )
    parser.add_argument(
        "--stage1-checkpoint",
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
        default=Path(
            "data/evaluations/detector-promotion-v1/diagnostic-manifest.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training/wildlife-stage2/evaluation-report.json"),
    )
    return parser.parse_args()


def _training_evidence(checkpoint: Path) -> dict[str, Any]:
    output = checkpoint.parent
    result = stage1_eval._read(output / "resume-result.json")
    inventory = {item["name"]: item for item in result["checkpoints"]}
    checkpoint_sha = sha256_file(checkpoint)
    if inventory.get(checkpoint.name, {}).get("sha256") != checkpoint_sha:
        raise ValueError("stage2_checkpoint_inventory_mismatch")
    rows = list(csv.DictReader((output / "metrics.csv").open(newline="")))
    epochs = sorted({int(row["epoch"]) for row in rows if row.get("epoch")})
    if len(epochs) < 10:
        raise ValueError(f"stage2_minimum_epochs_not_met:{len(epochs)}")
    validation_rows = [
        row
        for row in rows
        if row.get("val/ema_mAP_50_95") not in (None, "")
    ]
    return {
        "epochs_observed": epochs,
        "epochs_completed": len(epochs),
        "experiment": result["experiment"],
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_bytes": checkpoint.stat().st_size,
        "metrics_csv_sha256": sha256_file(output / "metrics.csv"),
        "validation_curve": [
            {
                "epoch": int(row["epoch"]),
                "ema_map_50_95": float(row["val/ema_mAP_50_95"]),
                "ema_map_50": float(row["val/ema_mAP_50"]),
                "map_50_95": float(row["val/mAP_50_95"]),
                "precision": float(row["val/precision"]),
                "recall": float(row["val/recall"]),
            }
            for row in validation_rows
        ],
        "resume_proof": {
            "initial_result": str(output / "initial-result.json"),
            "resume_result": str(output / "resume-result.json"),
            "resumed_from": result["resume_checkpoint"],
        },
    }


def _validation(
    corpus: Path,
) -> tuple[
    dict[str, list[EvaluationBox]],
    list[tuple[str, Path]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    manifest = stage1_eval._read(corpus / "stage2-manifest.json")
    if manifest.get("semantic_fingerprint") != STAGE2_FINGERPRINT:
        raise ValueError("stage2_fingerprint_mismatch")
    if manifest.get("split_fingerprint") != STAGE2_SPLIT_FINGERPRINT:
        raise ValueError("stage2_split_fingerprint_mismatch")
    examples = {item["example_id"]: item for item in manifest["examples"]}
    coco = stage1_eval._read(corpus / "dataset/valid/_annotations.coco.json")
    images = {item["id"]: item for item in coco["images"]}
    truth: dict[str, list[EvaluationBox]] = {
        item["mockingbird_example_id"]: [] for item in images.values()
    }
    for annotation in coco["annotations"]:
        image = images[annotation["image_id"]]
        frame_id = image["mockingbird_example_id"]
        x, y, width, height = (float(value) for value in annotation["bbox"])
        truth[frame_id].append(
            EvaluationBox(
                (
                    x / image["width"],
                    y / image["height"],
                    (x + width) / image["width"],
                    (y + height) / image["height"],
                ),
                taxon=annotation["source_taxon"],
                size_bucket=annotation["source_pixel_size_bucket"],
            )
        )
    cases = [
        (
            item["mockingbird_example_id"],
            corpus / "dataset/valid" / item["file_name"],
        )
        for item in images.values()
    ]
    ids = {frame_id for frame_id, _ in cases}
    frame_metadata = {
        frame_id: {
            "source_id": examples[frame_id]["source_id"],
            "site_id": examples[frame_id]["site_id"] or "unknown",
            "taxon_group": examples[frame_id]["taxon_group"] or "negative",
            "negative_kind": examples[frame_id]["negative_kind"] or "positive",
        }
        for frame_id in ids
    }
    metadata = {
        "images": len(ids),
        "positive_images": sum(bool(truth[item]) for item in ids),
        "negative_images": sum(not truth[item] for item in ids),
        "truth_boxes": sum(len(truth[item]) for item in ids),
    }
    return truth, cases, frame_metadata, metadata


def _hard_negative_cases(
    corpus: Path,
) -> tuple[list[tuple[str, Path]], dict[str, dict[str, Any]]]:
    manifest = stage1_eval._read(corpus / "stage2-manifest.json")
    rows = [
        item
        for item in manifest["examples"]
        if not item["is_positive"] and item["augmentation_kind"] == "full_scene"
    ]
    return (
        [(item["example_id"], corpus / item["image"]) for item in rows],
        {
            item["example_id"]: {
                "negative_kind": item["negative_kind"],
                "split": item["split"],
                "source_id": item["source_id"],
            }
            for item in rows
        },
    )


def _grouped_metrics(
    truth: Mapping[str, Sequence[EvaluationBox]],
    predictions: Mapping[str, Sequence[EvaluationBox]],
    metadata: Mapping[str, Mapping[str, Any]],
    field: str,
    *,
    minimum_truth: int = 0,
    minimum_frames: int = 1,
) -> dict[str, Any]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for frame_id in truth:
        grouped[str(metadata[frame_id][field])].append(frame_id)
    result = {}
    for value, frame_ids in sorted(grouped.items()):
        denominator = sum(len(truth[frame_id]) for frame_id in frame_ids)
        if denominator < minimum_truth or len(frame_ids) < minimum_frames:
            continue
        result[value] = {
            "frames": len(frame_ids),
            "truth_boxes": denominator,
            "metrics": evaluate_detections(
                {frame_id: truth[frame_id] for frame_id in frame_ids}, predictions
            ),
        }
    return result


def _negative_metrics(
    predictions: Mapping[str, Sequence[EvaluationBox]],
    metadata: Mapping[str, Mapping[str, Any]],
    field: str,
) -> dict[str, Any]:
    truth = {frame_id: [] for frame_id in metadata}
    return _grouped_metrics(truth, predictions, metadata, field)


def _mdv5_predictions_timed(
    adapter: Mdv5Adapter, cases: Iterable[tuple[str, Path]]
) -> tuple[dict[str, list[EvaluationBox]], list[float]]:
    results: dict[str, list[EvaluationBox]] = {}
    timings = []
    for frame_id, path in cases:
        rows, timing = adapter.infer(_onnx_provider_compatible_bytes(path))
        timings.append(float(timing["total_ms"]))
        results[frame_id] = [
            EvaluationBox(tuple(item["box"]), confidence=float(item["confidence"]))
            for item in rows
            if item["broad_class"] == "animal"
        ]
    return results, timings


def _run_rfdetr(
    checkpoint: Path,
    resolution: int,
    validation_cases: Sequence[tuple[str, Path]],
    frozen_cases: Sequence[tuple[str, Path]],
    diagnostic_cases: Sequence[tuple[str, Path]],
    hard_negative_cases: Sequence[tuple[str, Path]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    import torch
    from rfdetr import RFDETRSmall

    torch.cuda.empty_cache()
    # No explicit device index here: `reset_peak_memory_stats(0)` raises
    # "Invalid device argument" on this torch build (2.13.0+cu130) when
    # called before CUDA has done any real allocation in the process --
    # exactly the state at this point, since the model has not been built
    # yet. The no-arg form resolves through `current_device()`, which lazily
    # initializes CUDA as a side effect and so works pre-warm; it is
    # equivalent to device 0 here regardless, since this codebase is
    # single-GPU only.
    torch.cuda.reset_peak_memory_stats()
    model = RFDETRSmall(
        pretrain_weights=str(checkpoint.resolve()),
        resolution=resolution,
        device="cuda",
    )
    validation, validation_timing = stage1_eval._rfdetr_predictions(
        model, validation_cases
    )
    frozen, frozen_timing = stage1_eval._rfdetr_predictions(model, frozen_cases)
    diagnostic, diagnostic_timing = stage1_eval._rfdetr_predictions(
        model, diagnostic_cases
    )
    hard_negatives, hard_negative_timing = stage1_eval._rfdetr_predictions(
        model, hard_negative_cases
    )
    runtime = {
        "validation_median_ms": median(validation_timing.values()),
        "validation_fps": 1000.0 / median(validation_timing.values()),
        "frozen_median_ms": median(frozen_timing.values()),
        "diagnostic_median_ms": median(diagnostic_timing.values()),
        "hard_negative_median_ms": median(hard_negative_timing.values()),
        "peak_vram_allocated_bytes": torch.cuda.max_memory_allocated(0),
        "peak_vram_reserved_bytes": torch.cuda.max_memory_reserved(0),
        "model_bytes": checkpoint.stat().st_size,
    }
    del model
    torch.cuda.empty_cache()
    return {
        "validation": validation,
        "frozen": frozen,
        "diagnostic": diagnostic,
        "hard_negatives": hard_negatives,
    }, runtime


def _model_validation_report(
    truth: Mapping[str, Sequence[EvaluationBox]],
    predictions: Mapping[str, Sequence[EvaluationBox]],
    metadata: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "overall": evaluate_detections(truth, predictions),
        "by_source": _grouped_metrics(truth, predictions, metadata, "source_id"),
        "by_taxonomic_group": _grouped_metrics(
            truth, predictions, metadata, "taxon_group", minimum_truth=10
        ),
        "by_site_with_support": _grouped_metrics(
            truth,
            predictions,
            metadata,
            "site_id",
            minimum_truth=5,
            minimum_frames=5,
        ),
        "negative_strata": _grouped_metrics(
            truth, predictions, metadata, "negative_kind", minimum_frames=5
        ),
    }


def _decision(
    stage2_validation: Mapping[str, Any],
    stage1_validation: Mapping[str, Any],
    mdv5_validation: Mapping[str, Any],
    stage2_frozen: Mapping[str, Any],
    stage1_frozen: Mapping[str, Any],
    mdv5_frozen: Mapping[str, Any],
) -> str:
    stage2_small = min(
        stage2_validation["recall_by_size_bucket"].get("small", 0.0),
        stage2_validation["recall_by_size_bucket"].get("very_small", 0.0),
    )
    mdv5_small = min(
        mdv5_validation["recall_by_size_bucket"].get("small", 0.0),
        mdv5_validation["recall_by_size_bucket"].get("very_small", 0.0),
    )
    hard_negative_advantage = (
        stage2_validation["false_detections_per_negative_frame"]
        <= mdv5_validation["false_detections_per_negative_frame"]
    )
    if (
        stage2_frozen["recall"] >= mdv5_frozen["recall"]
        and stage2_frozen["f1"] > mdv5_frozen["f1"]
        and stage2_validation["f1"] > mdv5_validation["f1"]
        and stage2_small >= mdv5_small
        and hard_negative_advantage
    ):
        return "SHADOW_VALIDATION_READY"
    if (
        stage2_frozen["recall"] >= stage1_frozen["recall"] + 0.10
        and stage2_frozen["f1"] >= stage1_frozen["f1"] + 0.05
        and stage2_validation["f1"] >= stage1_validation["f1"]
    ):
        return "DOMAIN_TRAINING_PROMISING"
    return "PIPELINE_PROVEN_MODEL_WEAK"


def main() -> int:
    args = _args()
    if sha256_file(args.stage1_checkpoint) != STAGE1_CHECKPOINT_SHA256:
        raise ValueError("stage1_checkpoint_identity_mismatch")
    training = _training_evidence(args.stage2_checkpoint)
    truth, validation_cases, metadata, validation_metadata = _validation(args.corpus)
    hard_negative_cases, hard_negative_metadata = _hard_negative_cases(args.corpus)
    frozen_manifest = stage1_eval._read(args.frozen_manifest)
    frozen_truth, frozen_cases, distances = stage1_eval._frozen_truth(frozen_manifest)
    diagnostic_manifest = stage1_eval._read(args.diagnostic_manifest)
    diagnostic_cases = [
        (frame["frame_id"], Path(frame["image"]))
        for frame in diagnostic_manifest["frames"]
    ]

    stage2_raw, stage2_runtime = _run_rfdetr(
        args.stage2_checkpoint,
        768,
        validation_cases,
        frozen_cases,
        diagnostic_cases,
        hard_negative_cases,
    )
    stage2_sweep = [
        {
            "threshold": threshold,
            "metrics": evaluate_detections(
                truth, stage1_eval._thresholded(stage2_raw["validation"], threshold)
            ),
        }
        for threshold in THRESHOLDS
    ]
    selected = max(
        stage2_sweep,
        key=lambda row: (
            row["metrics"]["f1"],
            row["metrics"]["precision"],
            row["threshold"],
        ),
    )
    stage2_threshold = float(selected["threshold"])
    stage2 = {
        key: stage1_eval._thresholded(value, stage2_threshold)
        for key, value in stage2_raw.items()
    }

    stage1_raw, stage1_runtime = _run_rfdetr(
        args.stage1_checkpoint,
        640,
        validation_cases,
        frozen_cases,
        diagnostic_cases,
        hard_negative_cases,
    )
    stage1 = {
        key: stage1_eval._thresholded(value, 0.5)
        for key, value in stage1_raw.items()
    }

    mdv5_config = stage1_eval._read(
        Path("data/evaluations/detector-promotion-v1/mdv5-native-config.json")
    )
    if mdv5_config.get("score_threshold") != 0.1:
        raise ValueError("production_mdv5_threshold_changed")
    mdv5 = Mdv5Adapter(mdv5_config)
    mdv5.load()
    try:
        mdv5_validation, mdv5_validation_timing = _mdv5_predictions_timed(
            mdv5, validation_cases
        )
        mdv5_diagnostic, mdv5_diagnostic_timing = _mdv5_predictions_timed(
            mdv5, diagnostic_cases
        )
        mdv5_hard_negatives, mdv5_hard_negative_timing = _mdv5_predictions_timed(
            mdv5, hard_negative_cases
        )
    finally:
        mdv5.close()
    mdv5_frozen = stage1_eval._preserved_mdv5_frozen()

    stage2_validation_metrics = evaluate_detections(truth, stage2["validation"])
    stage1_validation_metrics = evaluate_detections(truth, stage1["validation"])
    mdv5_validation_metrics = evaluate_detections(truth, mdv5_validation)
    stage2_frozen_metrics = evaluate_detections(frozen_truth, stage2["frozen"])
    stage1_frozen_metrics = evaluate_detections(frozen_truth, stage1["frozen"])
    mdv5_frozen_metrics = evaluate_detections(frozen_truth, mdv5_frozen)
    decision = _decision(
        stage2_validation_metrics,
        stage1_validation_metrics,
        mdv5_validation_metrics,
        stage2_frozen_metrics,
        stage1_frozen_metrics,
        mdv5_frozen_metrics,
    )

    report = {
        "schema_version": 1,
        "report_version": "wildlife-stage2-evaluation-v0.2",
        "completed_at": datetime.now(UTC).isoformat(),
        "selection_authority": "Stage-2 anti-leakage validation only",
        "frozen_benchmark_use": "final evaluation only; never selection or tuning",
        "models": {
            "stage2_rfdetr_small": {
                "checkpoint": str(args.stage2_checkpoint),
                "checkpoint_sha256": training["checkpoint_sha256"],
                "resolution": 768,
                "selected_threshold": stage2_threshold,
                "threshold_selection_basis": "maximum F1 on Stage-2 validation only",
            },
            "stage1_rfdetr_small": {
                "checkpoint": str(args.stage1_checkpoint),
                "checkpoint_sha256": STAGE1_CHECKPOINT_SHA256,
                "resolution": 640,
                "fixed_threshold": 0.5,
            },
            "production_mdv5": {
                "weights_sha256": "b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc",
                "fixed_threshold": 0.1,
                "production_changed": False,
            },
        },
        "training_evidence": training,
        "stage2_validation": {
            "metadata": validation_metadata,
            "stage2_threshold_sweep": stage2_sweep,
            "stage2_rfdetr_small": _model_validation_report(
                truth, stage2["validation"], metadata
            ),
            "stage1_rfdetr_small_fixed_0_5": _model_validation_report(
                truth, stage1["validation"], metadata
            ),
            "production_mdv5_unchanged_0_1": _model_validation_report(
                truth, mdv5_validation, metadata
            ),
        },
        "frozen_mockingbird_75": {
            "manifest_fingerprint": stage1_eval.FROZEN_FINGERPRINT,
            "scorable_frames": len(frozen_truth),
            "stage2_rfdetr_small": stage2_frozen_metrics,
            "stage1_rfdetr_small_fixed_0_5": stage1_frozen_metrics,
            "production_mdv5_unchanged_0_1": mdv5_frozen_metrics,
            "stage2_distance_breakdown": stage1_eval._distance_metrics(
                frozen_truth, stage2["frozen"], distances
            ),
        },
        "latest_diagnostic_birds": {
            "denominator_policy": "diagnostic_only; excluded from population metrics",
            "stage2_rfdetr_small": stage1_eval._diagnostic_summary(
                diagnostic_manifest, stage2["diagnostic"]
            ),
            "stage1_rfdetr_small_fixed_0_5": stage1_eval._diagnostic_summary(
                diagnostic_manifest, stage1["diagnostic"]
            ),
            "production_mdv5_unchanged_0_1": stage1_eval._diagnostic_summary(
                diagnostic_manifest, mdv5_diagnostic
            ),
        },
        "hard_negative_strata": {
            "scope": (
                "all 2,000 governed empty frames; split is explicit because training "
                "negatives are diagnostic, not unbiased validation"
            ),
            "stage2_rfdetr_small": {
                "by_kind": _negative_metrics(
                    stage2["hard_negatives"], hard_negative_metadata, "negative_kind"
                ),
                "by_split": _negative_metrics(
                    stage2["hard_negatives"], hard_negative_metadata, "split"
                ),
            },
            "stage1_rfdetr_small_fixed_0_5": {
                "by_kind": _negative_metrics(
                    stage1["hard_negatives"], hard_negative_metadata, "negative_kind"
                ),
                "by_split": _negative_metrics(
                    stage1["hard_negatives"], hard_negative_metadata, "split"
                ),
            },
            "production_mdv5_unchanged_0_1": {
                "by_kind": _negative_metrics(
                    mdv5_hard_negatives, hard_negative_metadata, "negative_kind"
                ),
                "by_split": _negative_metrics(
                    mdv5_hard_negatives, hard_negative_metadata, "split"
                ),
            },
        },
        "runtime": {
            "cuda_device": "NVIDIA GeForce RTX 4060 Ti",
            "stage2_rfdetr_small": stage2_runtime,
            "stage1_rfdetr_small": stage1_runtime,
            "production_mdv5": {
                "validation_median_ms": median(mdv5_validation_timing),
                "validation_fps": 1000.0 / median(mdv5_validation_timing),
                "diagnostic_median_ms": median(mdv5_diagnostic_timing),
                "hard_negative_median_ms": median(mdv5_hard_negative_timing),
            },
        },
        "decision": decision,
        "decision_policy": {
            "shadow_validation_ready": (
                "beat MDv5 F1/recall on frozen, validation F1, supported small "
                "buckets, and validation hard-negative rate"
            ),
            "domain_training_promising": (
                "frozen recall +0.10 and F1 +0.05 over Stage 1 without lower "
                "Stage-2-validation F1"
            ),
        },
        "creates_product_truth": False,
        "changes_production_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
