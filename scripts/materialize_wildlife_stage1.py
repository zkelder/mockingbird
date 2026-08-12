#!/usr/bin/env python3
"""Materialize the governed 1,200-image wildlife detector Stage-1 corpus.

The command consumes only previously downloaded official annotation files,
selects deterministic human-boxed positives and curated camera-trap negatives,
downloads the selected images, verifies the frozen MockingBird holdout, and
exports one-class COCO train/validation folders.  It never opens product data
storage or treats detector/agent output as truth.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

from mockingbird.training.wildlife import (
    CorpusExample,
    PixelBox,
    WildlifeTrainingError,
    assert_no_group_leakage,
    build_corpus_manifest,
    contamination_report,
    dhash64,
    dhash_distance,
    load_source_registry,
    require_materialization_source,
    phash64,
    phash_distance,
    sha256_file,
    verify_frozen_benchmark,
)

SEED = 260811
COCO_ALLOWED_LICENSE_IDS = {4, 7, 8}
COCO_ANIMAL_CLASSES = {
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
}
COCO_SELECTION_CLASSES = {"bird", "cat", "dog", "bear"}
CCT_NON_ANIMALS = {"empty", "car"}
CCT_BASE_URL = (
    "https://lilawildlife.blob.core.windows.net/lila-wildlife/"
    "caltech-unzipped/cct_images"
)
COCO_BASE_URL = "http://images.cocodataset.org"
SOURCE_ARTIFACTS = {
    "caltech_bboxes_20200316.json": "9cc208db67b7dcf3fa403920c203a416527628f76a6b838371ab654478bf2ea3",
    "caltech_images_20210113.json": "0ed31a7371effe1938bdcc5817713ef35c21b868e9974be000fbb7886b95a34c",
    "CaltechCameraTrapsSplits_v0.json": "4deddfc58791124b37db375d45eeccb52d980b40cdd1dbac4881d0aae7ef34b4",
    "annotations_trainval2017.zip": "113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268",
    "instances_train2017.json": "610fce4944abdeb15354cc765333805529359d12d88f2f711393ca586901d01d",
    "instances_val2017.json": "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f",
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/training/wildlife-stage1"),
    )
    parser.add_argument(
        "--holdout-manifest",
        type=Path,
        default=Path("data/evaluations/detector-promotion-v1/corpus-manifest.json"),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args()


def _stable_order(values: Iterable[Any], *, seed: int, identity: Any) -> list[Any]:
    return sorted(
        values,
        key=lambda item: sha256(f"{seed}:{identity(item)}".encode()).hexdigest(),
    )


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError(
            f"source_annotation_unreadable:{path.name}"
        ) from error
    if not isinstance(value, dict):
        raise WildlifeTrainingError(f"source_annotation_invalid:{path.name}")
    return value


def _verify_sources(root: Path) -> dict[str, str]:
    cct = root / "source/caltech-camera-traps"
    coco = root / "source/coco-2017"
    paths = {
        "caltech_bboxes_20200316.json": cct / "caltech_bboxes_20200316.json",
        "caltech_images_20210113.json": cct / "caltech_images_20210113.json",
        "CaltechCameraTrapsSplits_v0.json": cct / "CaltechCameraTrapsSplits_v0.json",
        "annotations_trainval2017.zip": coco / "annotations_trainval2017.zip",
        "instances_train2017.json": coco / "annotations/instances_train2017.json",
        "instances_val2017.json": coco / "annotations/instances_val2017.json",
    }
    checksums: dict[str, str] = {}
    for name, path in paths.items():
        actual = sha256_file(path)
        if actual != SOURCE_ARTIFACTS[name]:
            raise WildlifeTrainingError(f"source_artifact_checksum_mismatch:{name}")
        checksums[name] = actual
    return checksums


def _select_coco(
    source_root: Path,
    *,
    seed: int,
) -> list[CorpusExample]:
    selected: list[CorpusExample] = []
    quotas = {
        "train": {"very_small": 192, "small": 240},
        "valid": {"very_small": 8, "small": 10},
    }
    for source_split, split in (("train", "train"), ("val", "valid")):
        payload = _load(
            source_root / "annotations" / f"instances_{source_split}2017.json"
        )
        categories = {item["id"]: item["name"] for item in payload["categories"]}
        licenses = {item["id"]: item["name"] for item in payload["licenses"]}
        images = {item["id"]: item for item in payload["images"]}
        annotations: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for annotation in payload["annotations"]:
            name = categories[annotation["category_id"]]
            if name in COCO_ANIMAL_CLASSES and not annotation.get("iscrowd", 0):
                annotations[annotation["image_id"]].append(annotation)

        candidates: dict[str, list[tuple[dict[str, Any], tuple[PixelBox, ...]]]] = (
            defaultdict(list)
        )
        for image_id, rows in annotations.items():
            image = images[image_id]
            if image["license"] not in COCO_ALLOWED_LICENSE_IDS:
                continue
            boxes = tuple(
                PixelBox(*row["bbox"], categories[row["category_id"]]) for row in rows
            )
            if not any(box.taxon in COCO_SELECTION_CLASSES for box in boxes):
                continue
            bucket = min(
                (box.size_bucket for box in boxes),
                key={"very_small": 0, "small": 1, "medium": 2, "large": 3}.__getitem__,
            )
            if bucket in {"very_small", "small"}:
                candidates[bucket].append((image, boxes))

        for bucket, count in quotas[split].items():
            ordered = _stable_order(
                candidates[bucket],
                seed=seed,
                identity=lambda pair: f"coco:{source_split}:{pair[0]['id']}:{bucket}",
            )
            if len(ordered) < count:
                raise WildlifeTrainingError(f"coco_{split}_{bucket}_quota_unavailable")
            for image, boxes in ordered[:count]:
                file_name = f"coco-{source_split}2017-{image['id']:012d}.jpg"
                selected.append(
                    CorpusExample(
                        example_id=f"coco-2017:{source_split}:{image['id']}",
                        source_id="coco-2017-permissive-animal-subset",
                        source_version=f"2017 {source_split} instances",
                        source_identity=f"coco-2017:{source_split}:{image['id']}",
                        parent_identity=None,
                        image=f"dataset/{split}/{file_name}",
                        source_url=f"{COCO_BASE_URL}/{source_split}2017/{image['file_name']}",
                        source_license=(
                            f"COCO annotations CC-BY-4.0; image: {licenses[image['license']]}"
                        ),
                        geography="unknown/mixed; not treated as North American provenance",
                        width=int(image["width"]),
                        height=int(image["height"]),
                        split=split,
                        site_id=None,
                        camera_id=None,
                        sequence_id=None,
                        captured_at=None,
                        truth_authority="public_human_bbox",
                        boxes=boxes,
                    )
                )
    return selected


def _round_robin_select(
    by_camera: dict[str, list[Any]],
    *,
    total: int,
    seed: int,
    identity: Any,
) -> list[Any]:
    cameras = _stable_order(by_camera, seed=seed, identity=lambda item: item)
    queues = {
        camera: deque(_stable_order(by_camera[camera], seed=seed, identity=identity))
        for camera in cameras
    }
    chosen: list[Any] = []
    while len(chosen) < total:
        progress = False
        for camera in cameras:
            if queues[camera] and len(chosen) < total:
                chosen.append(queues[camera].popleft())
                progress = True
        if not progress:
            raise WildlifeTrainingError("cct_camera_quota_unavailable")
    return chosen


def _select_cct(
    source_root: Path,
    *,
    seed: int,
) -> list[CorpusExample]:
    bbox_payload = _load(source_root / "caltech_bboxes_20200316.json")
    label_payload = _load(source_root / "caltech_images_20210113.json")
    splits = _load(source_root / "CaltechCameraTrapsSplits_v0.json")["splits"]
    split_locations = {
        "train": set(str(item) for item in splits["train"]),
        "valid": set(str(item) for item in splits["val"]),
    }
    bbox_categories = {item["id"]: item["name"] for item in bbox_payload["categories"]}
    bbox_images = {item["id"]: item for item in bbox_payload["images"]}
    boxes_by_image: dict[str, list[PixelBox]] = defaultdict(list)
    annotation_ids: dict[str, list[str]] = defaultdict(list)
    for annotation in bbox_payload["annotations"]:
        taxon = bbox_categories[annotation["category_id"]]
        if taxon in CCT_NON_ANIMALS or not annotation.get("bbox"):
            continue
        boxes_by_image[annotation["image_id"]].append(
            PixelBox(*annotation["bbox"], taxon)
        )
        annotation_ids[annotation["image_id"]].append(str(annotation["id"]))

    label_categories = {
        item["id"]: item["name"] for item in label_payload["categories"]
    }
    labels_by_image: dict[str, list[str]] = defaultdict(list)
    for annotation in label_payload["annotations"]:
        labels_by_image[annotation["image_id"]].append(
            label_categories[annotation["category_id"]]
        )

    positives_by_split_camera: dict[
        str, dict[str, list[tuple[dict[str, Any], tuple[PixelBox, ...]]]]
    ] = {
        "train": defaultdict(list),
        "valid": defaultdict(list),
    }
    for image_id, boxes in boxes_by_image.items():
        image = bbox_images[image_id]
        camera = str(image["location"])
        if camera not in split_locations["train"] | split_locations["valid"]:
            continue
        split = "train" if camera in split_locations["train"] else "valid"
        positives_by_split_camera[split][camera].append((image, tuple(boxes)))

    negatives_by_split_camera: dict[str, dict[str, list[dict[str, Any]]]] = {
        "train": defaultdict(list),
        "valid": defaultdict(list),
    }
    for image in label_payload["images"]:
        labels = labels_by_image[image["id"]]
        if not labels or any(label != "empty" for label in labels):
            continue
        camera = str(image["location"])
        if camera not in split_locations["train"] | split_locations["valid"]:
            continue
        split = "train" if camera in split_locations["train"] else "valid"
        negatives_by_split_camera[split][camera].append(image)

    selected: list[CorpusExample] = []
    quotas = {
        "train": {"positive": 280, "negative": 320, "cameras": 10},
        "valid": {"positive": 70, "negative": 80, "cameras": 4},
    }
    for split, quota in quotas.items():
        eligible_cameras = [
            camera
            for camera in positives_by_split_camera[split]
            if len(positives_by_split_camera[split][camera]) >= 20
            and len(negatives_by_split_camera[split][camera]) >= 20
        ]
        ordered_cameras = _stable_order(
            eligible_cameras,
            seed=seed,
            identity=lambda camera: f"cct:{split}:{camera}",
        )
        cameras = ordered_cameras[: quota["cameras"]]
        if len(cameras) != quota["cameras"]:
            raise WildlifeTrainingError(f"cct_{split}_camera_diversity_unavailable")

        positives = _round_robin_select(
            {camera: positives_by_split_camera[split][camera] for camera in cameras},
            total=quota["positive"],
            seed=seed,
            identity=lambda pair: pair[0]["id"],
        )
        negatives = _round_robin_select(
            {camera: negatives_by_split_camera[split][camera] for camera in cameras},
            total=quota["negative"],
            seed=seed,
            identity=lambda image: image["id"],
        )
        for image, boxes in positives:
            file_name = f"cct-{image['id']}.jpg"
            selected.append(
                CorpusExample(
                    example_id=f"cct:{image['id']}",
                    source_id="caltech-camera-traps-20200316",
                    source_version="bounding boxes 20200316",
                    source_identity=f"cct:image:{image['id']}",
                    parent_identity=f"cct:sequence:{image['seq_id']}",
                    image=f"dataset/{split}/{file_name}",
                    source_url=f"{CCT_BASE_URL}/{image['file_name']}",
                    source_license="CDLA-Permissive-2.0",
                    geography="Southwestern United States",
                    width=int(image["width"]),
                    height=int(image["height"]),
                    split=split,
                    site_id=f"cct-location-{image['location']}",
                    camera_id=f"cct-location-{image['location']}",
                    sequence_id=f"cct-sequence-{image['seq_id']}",
                    captured_at=image.get("date_captured"),
                    truth_authority="public_human_bbox",
                    boxes=boxes,
                )
            )
        for image in negatives:
            file_name = f"cct-{image['id']}.jpg"
            selected.append(
                CorpusExample(
                    example_id=f"cct:{image['id']}",
                    source_id="caltech-camera-traps-20200316",
                    source_version="image labels 20210113",
                    source_identity=f"cct:image:{image['id']}",
                    parent_identity=f"cct:sequence:{image['seq_id']}",
                    image=f"dataset/{split}/{file_name}",
                    source_url=f"{CCT_BASE_URL}/{image['file_name']}",
                    source_license="CDLA-Permissive-2.0",
                    geography="Southwestern United States",
                    width=int(image["width"]),
                    height=int(image["height"]),
                    split=split,
                    site_id=f"cct-location-{image['location']}",
                    camera_id=f"cct-location-{image['location']}",
                    sequence_id=f"cct-sequence-{image['seq_id']}",
                    captured_at=image.get("date_captured"),
                    truth_authority="public_curated_empty",
                    boxes=(),
                    negative_kind="camera_trap_empty_scene",
                )
            )
    return selected


def select_examples(root: Path, *, seed: int) -> list[CorpusExample]:
    examples = _select_coco(root / "source/coco-2017", seed=seed)
    examples.extend(_select_cct(root / "source/caltech-camera-traps", seed=seed))
    if len(examples) != 1200 or len({item.example_id for item in examples}) != 1200:
        raise WildlifeTrainingError("stage1_selection_identity_invalid")
    assert_no_group_leakage(examples)
    return examples


def _download_one(example: CorpusExample, *, root: Path) -> CorpusExample:
    destination = root / example.image
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file():
        request = Request(
            example.source_url,
            headers={"User-Agent": "MockingBird-Wildlife-Stage1/0.1"},
        )
        for attempt in range(4):
            temporary: Path | None = None
            try:
                with urlopen(request, timeout=45) as response:
                    with tempfile.NamedTemporaryFile(
                        dir=destination.parent,
                        prefix=f".{destination.name}.",
                        suffix=".part",
                        delete=False,
                    ) as output:
                        temporary = Path(output.name)
                        shutil.copyfileobj(response, output, length=1024 * 1024)
                os.replace(temporary, destination)
                break
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                if attempt == 3:
                    raise WildlifeTrainingError(
                        f"image_download_failed:{example.example_id}:{type(error).__name__}"
                    ) from error
                time.sleep(0.5 * (2**attempt))
    try:
        with Image.open(destination) as opened:
            opened.verify()
        with Image.open(destination) as opened:
            actual_size = opened.size
    except (OSError, ValueError) as error:
        raise WildlifeTrainingError(
            f"image_decode_failed:{example.example_id}"
        ) from error
    if actual_size != (example.width, example.height):
        raise WildlifeTrainingError(
            f"image_dimensions_mismatch:{example.example_id}:{actual_size}"
        )
    return replace(
        example,
        sha256=sha256_file(destination),
        dhash64=dhash64(destination),
        phash64=phash64(destination),
    )


def materialize(
    examples: Sequence[CorpusExample],
    *,
    root: Path,
    workers: int,
) -> list[CorpusExample]:
    if workers < 1 or workers > 32:
        raise WildlifeTrainingError("download_worker_bound_invalid")
    completed: list[CorpusExample] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {
            pool.submit(_download_one, example, root=root): example.example_id
            for example in examples
        }
        for index, future in enumerate(as_completed(pending), start=1):
            completed.append(future.result())
            if index % 100 == 0:
                print(f"materialized {index}/{len(examples)}", flush=True)
    return sorted(completed, key=lambda item: item.example_id)


def _internal_split_report(examples: Sequence[CorpusExample]) -> dict[str, Any]:
    train = [item for item in examples if item.split == "train"]
    valid = [item for item in examples if item.split == "valid"]
    train_hashes = {item.sha256: item.example_id for item in train}
    exact = [
        {"train": train_hashes[item.sha256], "valid": item.example_id}
        for item in valid
        if item.sha256 in train_hashes
    ]
    near: list[dict[str, Any]] = []
    for validation in valid:
        assert validation.dhash64 is not None
        assert validation.phash64 is not None
        for training in train:
            assert training.dhash64 is not None
            assert training.phash64 is not None
            distance = dhash_distance(validation.dhash64, training.dhash64)
            frequency_distance = phash_distance(
                validation.phash64,
                training.phash64,
            )
            if distance <= 2 and frequency_distance <= 4:
                near.append(
                    {
                        "train": training.example_id,
                        "valid": validation.example_id,
                        "dhash_distance": distance,
                        "phash_distance": frequency_distance,
                    }
                )
    return {
        "exact_content_cross_split": exact,
        "near_duplicate_cross_split": near,
        "passed": not (exact or near),
        "near_duplicate_policy": "dhash64 <= 2 and phash64 <= 4",
    }


def _write_coco(examples: Sequence[CorpusExample], *, root: Path, split: str) -> None:
    rows = [item for item in examples if item.split == split]
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    annotation_id = 1
    for image_id, example in enumerate(
        sorted(rows, key=lambda item: item.example_id), start=1
    ):
        images.append(
            {
                "id": image_id,
                "file_name": Path(example.image).name,
                "width": example.width,
                "height": example.height,
                "mockingbird_example_id": example.example_id,
            }
        )
        for box in example.boxes:
            annotations.append(
                {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": 1,
                    "bbox": [box.x, box.y, box.width, box.height],
                    "area": box.area,
                    "iscrowd": 0,
                    "source_taxon": box.taxon,
                    "source_pixel_size_bucket": box.size_bucket,
                    "truth_authority": example.truth_authority,
                }
            )
            annotation_id += 1
    payload = {
        "info": {
            "description": "MockingBird Stage-1 one-class animal detector corpus",
            "version": "0.1",
            "creates_product_truth": False,
        },
        "licenses": [],
        "categories": [{"id": 1, "name": "animal", "supercategory": "animal"}],
        "images": images,
        "annotations": annotations,
    }
    destination = root / "dataset" / split / "_annotations.coco.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, destination)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def main() -> int:
    args = _args()
    repository_root = Path(__file__).resolve().parents[1]
    root = args.output.resolve()
    try:
        root.relative_to((repository_root / "data").resolve())
    except ValueError as error:
        raise SystemExit(
            "Stage-1 output must remain under the ignored repository data directory."
        ) from error
    registry = load_source_registry()
    require_materialization_source(registry, "caltech-camera-traps-20200316")
    require_materialization_source(registry, "coco-2017-permissive-animal-subset")
    source_checksums = _verify_sources(root)
    holdout = verify_frozen_benchmark(
        args.holdout_manifest.resolve(),
        repository_root=repository_root,
    )
    examples = select_examples(root, seed=args.seed)
    plan = {
        "corpus_id": "north-american-backyard-wildlife-stage1-v0.1",
        "seed": args.seed,
        "images": len(examples),
        "positives": sum(item.is_positive for item in examples),
        "negatives": sum(not item.is_positive for item in examples),
        "by_split": dict(Counter(item.split for item in examples)),
        "primary_size_distribution": dict(
            Counter(item.size_bucket for item in examples if item.is_positive)
        ),
        "source_artifact_checksums": source_checksums,
        "registry_fingerprint": registry["fingerprint"],
        "frozen_holdout_fingerprint": (
            "24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec"
        ),
        "estimated_materialized_image_bytes": 400_000_000,
        "estimated_training_checkpoint_bytes": 4_000_000_000,
    }
    _write_json(root / "selection-plan.json", plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.plan_only:
        return 0

    materialized = materialize(examples, root=root, workers=args.workers)
    contamination = contamination_report(materialized, holdout)
    internal = _internal_split_report(materialized)
    _write_json(root / "internal-split-contamination.json", internal)
    if not internal["passed"]:
        raise WildlifeTrainingError("internal_train_validation_contamination")
    selection_policy = {
        "seed": args.seed,
        "coco_positive_images": 450,
        "cct_positive_images": 350,
        "cct_curated_empty_images": 400,
        "cct_camera_group_split": "official Caltech train/validation camera split",
        "coco_split": "official COCO train2017/val2017 split; no site lineage available",
        "neighboring_camera_frames_random_split": False,
        "image_label_only_positives_included": 0,
        "agent_or_model_truth_included": 0,
    }
    manifest = build_corpus_manifest(
        materialized,
        registry_fingerprint=registry["fingerprint"],
        contamination=contamination,
        selection_policy=selection_policy,
    )
    _write_coco(materialized, root=root, split="train")
    _write_coco(materialized, root=root, split="valid")
    _write_json(root / "stage1-manifest.json", manifest)
    _write_json(root / "contamination-report.json", contamination)
    print(
        json.dumps(
            {
                "manifest": str(root / "stage1-manifest.json"),
                "semantic_fingerprint": manifest["semantic_fingerprint"],
                "split_fingerprint": manifest["split_fingerprint"],
                "summary": manifest["summary"],
                "contamination_passed": contamination["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeTrainingError as error:
        print(f"wildlife Stage-1 materialization failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
