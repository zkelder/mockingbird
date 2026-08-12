#!/usr/bin/env python3
"""Run the bounded RF-DETR Small Stage-1 CUDA checkpoint/resume proof."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import sys
from typing import Any

from mockingbird.training.wildlife import (
    ExperimentIdentity,
    WildlifeTrainingError,
    sha256_file,
)

CORPUS_FINGERPRINT = "df1edfe3df4b5287ddad3702312a8fb7f1aa273ae26827818bb42b56be773b8d"
SPLIT_FINGERPRINT = "5c0009f4c3c56366f3ab58e62c17f4aceda2b976bd9098d0a17622471954fcb8"
RFDETR_WHEEL_SHA256 = "345e55b897ce590464e64ae4750e60b668436cbc6bf58d87f438895a93c3e9a4"
PRETRAINED_SHA256 = "d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33"
RESOLUTION = 640
BATCH_SIZE = 1
GRAD_ACCUM_STEPS = 8
SEED = 260811


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("initial", "resume"))
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/training/wildlife-stage1"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/training/wildlife-stage1/experiments/rfdetr-small-stage1-proof"
        ),
    )
    parser.add_argument(
        "--pretrained",
        type=Path,
        default=Path("data/models/detector-promotion-v1/rf-detr-small.pth"),
    )
    parser.add_argument(
        "--wheel",
        type=Path,
        default=Path(
            "data/runtime/detector-promotion-v1/packages/rfdetr-1.8.3-py3-none-any.whl"
        ),
    )
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError(f"training_input_unreadable:{path.name}") from error
    if not isinstance(payload, dict):
        raise WildlifeTrainingError(f"training_input_invalid:{path.name}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
    )
    os.replace(temporary, path)


def _checkpoint_inventory(output: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(output.glob("*.ckpt")) + sorted(output.glob("*.pth"))
    ]


def main() -> int:
    args = _args()
    repository_root = Path(__file__).resolve().parents[1]
    corpus = args.corpus.resolve()
    output = args.output.resolve()
    pretrained = args.pretrained.resolve()
    wheel = args.wheel.resolve()
    for path in (corpus, output):
        try:
            path.relative_to((repository_root / "data").resolve())
        except ValueError as error:
            raise WildlifeTrainingError(
                "training_artifact_path_outside_ignored_data"
            ) from error

    manifest = _read_json(corpus / "stage1-manifest.json")
    if manifest.get("semantic_fingerprint") != CORPUS_FINGERPRINT:
        raise WildlifeTrainingError("stage1_corpus_fingerprint_mismatch")
    if manifest.get("split_fingerprint") != SPLIT_FINGERPRINT:
        raise WildlifeTrainingError("stage1_split_fingerprint_mismatch")
    if sha256_file(wheel) != RFDETR_WHEEL_SHA256:
        raise WildlifeTrainingError("rfdetr_wheel_checksum_mismatch")
    if sha256_file(pretrained) != PRETRAINED_SHA256:
        raise WildlifeTrainingError("rfdetr_pretrained_checksum_mismatch")

    import torch
    import rfdetr
    from rfdetr import RFDETRSmall

    if not torch.cuda.is_available():
        raise WildlifeTrainingError("cuda_unavailable")
    if torch.cuda.get_device_properties(0).total_memory < 7_000_000_000:
        raise WildlifeTrainingError("cuda_vram_below_stage1_gate")

    experiment = ExperimentIdentity(
        experiment_id="rfdetr-small-stage1-proof-v0.1",
        corpus_fingerprint=CORPUS_FINGERPRINT,
        split_fingerprint=SPLIT_FINGERPRINT,
        model_architecture="RF-DETR Small",
        model_upstream_id="rf-detr-small.pth",
        package_version="1.8.3",
        package_sha256=RFDETR_WHEEL_SHA256,
        pretrained_sha256=PRETRAINED_SHA256,
        resolution=RESOLUTION,
        batch_size=BATCH_SIZE,
        grad_accum_steps=GRAD_ACCUM_STEPS,
        optimizer="AdamW",
        learning_rate=0.0001,
        learning_rate_encoder=0.00015,
        scheduler="step (lr_drop=1)",
        amp_dtype="fp16",
        seed=SEED,
        augmentation="RF-DETR 1.8.3 CPU default; multi_scale disabled",
    )
    output.mkdir(parents=True, exist_ok=True)
    resume_checkpoint = output / "checkpoint_0.ckpt"
    if args.phase == "resume" and not resume_checkpoint.is_file():
        raise WildlifeTrainingError("resume_checkpoint_missing")
    if args.phase == "initial" and any(output.glob("*.ckpt")):
        raise WildlifeTrainingError("initial_phase_output_contains_checkpoint")

    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "cuda_device": torch.cuda.get_device_name(0),
        "cuda_total_memory_bytes": torch.cuda.get_device_properties(0).total_memory,
        "rfdetr_module": str(Path(rfdetr.__file__).resolve()),
    }
    plan = {
        "phase": args.phase,
        "intentional_stop_after_total_epochs": 1 if args.phase == "initial" else 2,
        "resume_checkpoint": str(resume_checkpoint) if args.phase == "resume" else None,
        "experiment": {
            **experiment.__dict__,
            "effective_batch_size": experiment.effective_batch_size,
            "fingerprint": experiment.fingerprint,
        },
        "environment": environment,
        "corpus_manifest": str(corpus / "stage1-manifest.json"),
        "output_dir": str(output),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(output / f"{args.phase}-plan.json", plan)
    print(json.dumps(plan, indent=2, sort_keys=True), flush=True)

    torch.set_float32_matmul_precision("high")
    model = RFDETRSmall(
        pretrain_weights=str(pretrained),
        resolution=RESOLUTION,
        gradient_checkpointing=True,
    )
    model.train(
        dataset_dir=str(corpus / "dataset"),
        output_dir=str(output),
        epochs=1 if args.phase == "initial" else 2,
        resume=str(resume_checkpoint) if args.phase == "resume" else None,
        resolution=RESOLUTION,
        batch_size=BATCH_SIZE,
        grad_accum_steps=GRAD_ACCUM_STEPS,
        lr=0.0001,
        lr_encoder=0.00015,
        lr_drop=1,
        lr_scheduler="step",
        warmup_epochs=0.0,
        weight_decay=0.0001,
        multi_scale=False,
        use_ema=True,
        amp_dtype="fp16",
        checkpoint_interval=1,
        eval_interval=1,
        num_workers=0,
        pin_memory=True,
        persistent_workers=False,
        prefetch_factor=None,
        seed=SEED,
        device="cuda",
        accelerator="gpu",
        devices=1,
        strategy="auto",
        progress_bar="tqdm",
        tensorboard=False,
        wandb=False,
        mlflow=False,
        clearml=False,
        save_dataset_grids=False,
        compute_val_loss=True,
        log_per_class_metrics=True,
        class_names=["animal"],
        notes={
            "experiment_fingerprint": experiment.fingerprint,
            "corpus_fingerprint": CORPUS_FINGERPRINT,
            "split_fingerprint": SPLIT_FINGERPRINT,
            "phase": args.phase,
            "creates_product_truth": False,
            "production_model_changed": False,
        },
    )
    result = {
        **plan,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "checkpoints": _checkpoint_inventory(output),
        "cuda_max_memory_allocated_bytes": torch.cuda.max_memory_allocated(0),
        "cuda_max_memory_reserved_bytes": torch.cuda.max_memory_reserved(0),
    }
    _write_json(output / f"{args.phase}-result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeTrainingError as error:
        print(f"RF-DETR Stage-1 proof failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
