#!/usr/bin/env python3
"""Fine-tune RF-DETR Small on governed wildlife Stage-2 with resume proof."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
from typing import Any

from mockingbird.training.wildlife import (
    ExperimentIdentity,
    WildlifeTrainingError,
    sha256_file,
)

RFDETR_WHEEL_SHA256 = "345e55b897ce590464e64ae4750e60b668436cbc6bf58d87f438895a93c3e9a4"
STAGE1_BEST_TOTAL_SHA256 = (
    "b14581ebb0eed43675a229acec304a71fbc0b50ff8640d26acd95ee7f1564d1a"
)
RESOLUTION = 768
BATCH_SIZE = 1
GRAD_ACCUM_STEPS = 8
MAX_EPOCHS = 14
EARLY_STOPPING_SKIP_EPOCHS = 9
EARLY_STOPPING_PATIENCE = 3
SEED = 260812
AUGMENTATION = {
    "RandomBrightnessContrast": {
        "brightness_limit": 0.12,
        "contrast_limit": 0.12,
        "p": 0.35,
    },
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("preflight", "initial", "resume"))
    parser.add_argument(
        "--finalize-recovered-initial",
        action="store_true",
        help="verify and inventory a recovered epoch-0 optimizer checkpoint",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("data/training/wildlife-stage2"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/training/wildlife-stage2/experiments/rfdetr-small-stage2-v0.2"
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
        "--wheel",
        type=Path,
        default=Path(
            "data/runtime/detector-promotion-v1/packages/"
            "rfdetr-1.8.3-py3-none-any.whl"
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


def _stage_checkpoint_tempdir(output: Path) -> Path:
    """Force every ``tempfile``-based staging write onto ``output``'s filesystem.

    ``pytorch_lightning``'s ``_atomic_save`` writes each checkpoint through an
    ``fsspec`` local-filesystem transaction. Inside that transaction,
    ``fsspec.implementations.local.LocalFileOpener._open`` stages the write
    with a bare ``tempfile.mkstemp()`` -- no ``dir=`` argument -- so the
    staging file lands wherever ``tempfile.gettempdir()`` resolves,
    independent of the checkpoint's destination directory. The commit step
    then does ``shutil.move(staged, destination)``: same-filesystem, that is
    a cheap atomic ``os.rename``; cross-filesystem (for example a Windows
    drive mounted into WSL2 at ``/mnt/c`` versus the native ext4 root), it
    falls back to a real copy-then-delete of the whole checkpoint, which can
    fail partway under host memory/IO pressure on a ~500 MB file. This is
    exactly what produced the epoch-0 ``checkpoint_0.ckpt`` recovery.

    Staging inside ``output`` itself -- rather than merely "the same
    top-level filesystem" -- guarantees the same device for every checkpoint
    write this process makes, so the eventual rename can never need a copy.
    Setting ``tempfile.tempdir`` directly (not just the environment
    variables) makes this authoritative even if something already resolved
    and cached the previous default before this call.
    """

    staging = output / ".checkpoint-staging"
    staging.mkdir(parents=True, exist_ok=True)
    if os.stat(staging).st_dev != os.stat(output).st_dev:
        # Structurally unreachable for a plain child directory; fail closed
        # rather than silently accept a staging location that could still
        # require a cross-filesystem copy.
        raise WildlifeTrainingError("checkpoint_staging_dir_not_same_filesystem")
    location = str(staging)
    os.environ["TMPDIR"] = location
    os.environ["TEMP"] = location
    os.environ["TMP"] = location
    tempfile.tempdir = location
    return staging


def main() -> int:
    args = _args()
    repository_root = Path(__file__).resolve().parents[1]
    corpus = args.corpus.resolve()
    output = args.output.resolve()
    stage1_checkpoint = args.stage1_checkpoint.resolve()
    wheel = args.wheel.resolve()
    for path in (corpus, output):
        try:
            path.relative_to((repository_root / "data").resolve())
        except ValueError as error:
            raise WildlifeTrainingError(
                "training_artifact_path_outside_ignored_data"
            ) from error
    manifest = _read_json(corpus / "stage2-manifest.json")
    corpus_fingerprint = str(manifest.get("semantic_fingerprint", ""))
    split_fingerprint = str(manifest.get("split_fingerprint", ""))
    if len(corpus_fingerprint) != 64 or len(split_fingerprint) != 64:
        raise WildlifeTrainingError("stage2_manifest_fingerprint_invalid")
    if manifest.get("corpus_id") != "north-american-backyard-wildlife-stage2-v0.2":
        raise WildlifeTrainingError("stage2_manifest_identity_invalid")
    if manifest.get("summary", {}).get("images") != 8_000:
        raise WildlifeTrainingError("stage2_manifest_image_count_invalid")
    if sha256_file(wheel) != RFDETR_WHEEL_SHA256:
        raise WildlifeTrainingError("rfdetr_wheel_checksum_mismatch")
    if sha256_file(stage1_checkpoint) != STAGE1_BEST_TOTAL_SHA256:
        raise WildlifeTrainingError("stage1_checkpoint_checksum_mismatch")

    checkpoint_staging_dir = _stage_checkpoint_tempdir(output)

    import torch
    import rfdetr

    cuda_available = torch.cuda.is_available()
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "torch": torch.__version__,
        "torch_cuda": torch.version.cuda,
        "cuda_available": cuda_available,
        "cuda_device": torch.cuda.get_device_name(0) if cuda_available else None,
        "cuda_total_memory_bytes": (
            torch.cuda.get_device_properties(0).total_memory
            if cuda_available
            else None
        ),
        "rfdetr_version": version("rfdetr"),
        "rfdetr_module": str(Path(rfdetr.__file__).resolve()),
    }
    experiment = ExperimentIdentity(
        experiment_id="rfdetr-small-stage2-v0.2",
        corpus_fingerprint=corpus_fingerprint,
        split_fingerprint=split_fingerprint,
        model_architecture="RF-DETR Small",
        model_upstream_id=(
            "MockingBird Stage-1 best-total initialized from rf-detr-small.pth"
        ),
        package_version="1.8.3",
        package_sha256=RFDETR_WHEEL_SHA256,
        pretrained_sha256=STAGE1_BEST_TOTAL_SHA256,
        resolution=RESOLUTION,
        batch_size=BATCH_SIZE,
        grad_accum_steps=GRAD_ACCUM_STEPS,
        optimizer="AdamW",
        learning_rate=0.00005,
        learning_rate_encoder=0.000075,
        scheduler="step (lr_drop=11)",
        amp_dtype="fp16",
        seed=SEED,
        augmentation=(
            "1,000 governed source-pixel context crops plus fixed 768px input; "
            "bounded brightness/contrast; multi-scale disabled"
        ),
    )
    output.mkdir(parents=True, exist_ok=True)
    resume_checkpoint = output / "checkpoint_0.ckpt"
    total_epochs = 0 if args.phase == "preflight" else (
        1 if args.phase == "initial" else MAX_EPOCHS
    )
    plan = {
        "phase": args.phase,
        "target_total_epochs": total_epochs,
        "minimum_stage2_epochs": 10,
        "resume_checkpoint": (
            str(resume_checkpoint) if args.phase == "resume" else None
        ),
        "initialization": {
            "stage1_checkpoint": str(stage1_checkpoint),
            "sha256": STAGE1_BEST_TOTAL_SHA256,
            "stage1_decision": "PIPELINE_PROVEN_MODEL_WEAK",
        },
        "small_object_strategy": {
            "resolution": RESOLUTION,
            "source_pixel_context_crop_examples": 1_000,
            "validation_context_crops": 0,
            "multi_scale": False,
            "augmentation": AUGMENTATION,
        },
        "early_stopping": {
            "enabled": True,
            "skip_best_epochs": EARLY_STOPPING_SKIP_EPOCHS,
            "patience": EARLY_STOPPING_PATIENCE,
            "min_delta": 0.001,
            "monitor": "EMA validation mAP 50:95",
            "minimum_epochs_before_stop": 10,
        },
        "experiment": {
            **experiment.__dict__,
            "effective_batch_size": experiment.effective_batch_size,
            "fingerprint": experiment.fingerprint,
        },
        "environment": environment,
        "corpus_manifest": str(corpus / "stage2-manifest.json"),
        "output_dir": str(output),
        "checkpoint_staging_dir": str(checkpoint_staging_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "creates_product_truth": False,
        "production_model_changed": False,
    }
    if args.finalize_recovered_initial:
        if args.phase != "initial":
            raise WildlifeTrainingError("checkpoint_recovery_phase_invalid")
        original_plan = _read_json(output / "initial-plan.json")
        if (
            original_plan.get("experiment", {}).get("fingerprint")
            != experiment.fingerprint
        ):
            raise WildlifeTrainingError("checkpoint_recovery_experiment_mismatch")
        if not resume_checkpoint.is_file():
            raise WildlifeTrainingError("checkpoint_recovery_file_missing")
        checkpoint = torch.load(
            resume_checkpoint,
            map_location="cpu",
            weights_only=False,
            mmap=True,
        )
        if (
            checkpoint.get("epoch") != 0
            or int(checkpoint.get("global_step", 0)) <= 0
            or len(checkpoint.get("optimizer_states", ())) != 1
            or len(checkpoint.get("lr_schedulers", ())) != 1
        ):
            raise WildlifeTrainingError("checkpoint_recovery_state_invalid")
        result = {
            **original_plan,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "completion_status": "recovered_after_cross_filesystem_atomic_commit_failure",
            "recovery_validation": {
                "epoch": checkpoint["epoch"],
                "global_step": checkpoint["global_step"],
                "optimizer_states": len(checkpoint["optimizer_states"]),
                "lr_schedulers": len(checkpoint["lr_schedulers"]),
            },
            "checkpoints": _checkpoint_inventory(output),
            "metrics_csv_sha256": sha256_file(output / "metrics.csv"),
        }
        _write_json(output / "initial-result.json", result)
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        return 0
    _write_json(output / f"{args.phase}-plan.json", plan)
    print(json.dumps(plan, indent=2, sort_keys=True), flush=True)
    if args.phase == "preflight":
        return 0 if cuda_available else 3
    if not cuda_available:
        raise WildlifeTrainingError("cuda_unavailable")
    if torch.cuda.get_device_properties(0).total_memory < 7_000_000_000:
        raise WildlifeTrainingError("cuda_vram_below_stage2_gate")
    if args.phase == "resume" and not resume_checkpoint.is_file():
        raise WildlifeTrainingError("resume_checkpoint_missing")
    if args.phase == "initial" and any(output.glob("*.ckpt")):
        raise WildlifeTrainingError("initial_phase_output_contains_checkpoint")

    from rfdetr import RFDETRSmall

    torch.set_float32_matmul_precision("high")
    model = RFDETRSmall(
        pretrain_weights=str(stage1_checkpoint),
        resolution=RESOLUTION,
        gradient_checkpointing=True,
    )
    model.train(
        dataset_dir=str(corpus / "dataset"),
        output_dir=str(output),
        epochs=total_epochs,
        resume=str(resume_checkpoint) if args.phase == "resume" else None,
        resolution=RESOLUTION,
        batch_size=BATCH_SIZE,
        grad_accum_steps=GRAD_ACCUM_STEPS,
        lr=0.00005,
        lr_encoder=0.000075,
        lr_drop=11,
        lr_scheduler="step",
        warmup_epochs=0.5,
        weight_decay=0.0001,
        multi_scale=False,
        use_ema=True,
        amp_dtype="fp16",
        checkpoint_interval=1,
        eval_interval=1,
        early_stopping=True,
        early_stopping_patience=EARLY_STOPPING_PATIENCE,
        early_stopping_min_delta=0.001,
        early_stopping_use_ema=True,
        skip_best_epochs=EARLY_STOPPING_SKIP_EPOCHS,
        aug_config=AUGMENTATION,
        augmentation_backend="cpu",
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
            "corpus_fingerprint": corpus_fingerprint,
            "split_fingerprint": split_fingerprint,
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
        print(f"RF-DETR Stage-2 fine-tuning failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
