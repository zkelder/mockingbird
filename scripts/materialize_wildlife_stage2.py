#!/usr/bin/env python3
"""Plan and materialize the governed 8,000-example wildlife Stage-2 corpus.

Only reviewed public metadata and independently reviewed local truth are
eligible. The selector creates camera/site-grouped validation, oversamples
source-pixel small animals with train-only context crops, keeps curated empty
scenes, and exports one-class COCO data below the ignored data directory.
"""

from __future__ import annotations

import argparse
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from shutil import copyfileobj
import sys
import tempfile
import time
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from PIL import Image

from mockingbird.training.wildlife import (
    CorpusExample,
    PixelBox,
    WildlifeTrainingError,
    assert_no_group_leakage,
    build_stage2_corpus_manifest,
    contamination_report,
    context_crop_bounds,
    corpus_summary,
    dhash64,
    dhash_distance,
    load_stage2_source_registry,
    phash64,
    phash_distance,
    require_materialization_source,
    sha256_file,
    verify_frozen_benchmark,
)

SEED = 260812
TARGET_TOTAL = 8_000
BASE_POSITIVE_TOTAL = 5_000
CONTEXT_CROP_TOTAL = 1_000
NEGATIVE_TOTAL = 2_000

OREGON_BASE = "https://storage.googleapis.com/public-datasets-lila/oregon-critters"
CHANNEL_BASE = (
    "https://lilawildlife.blob.core.windows.net/lila-wildlife/"
    "channel-islands-camera-traps/images"
)
ENA_BASE = "https://lilawildlife.blob.core.windows.net/lila-wildlife/ena24/images"
NACTI_BASE = (
    "https://lilawildlife.blob.core.windows.net/lila-wildlife/nacti-unzipped"
)
CCT_BASE = (
    "https://lilawildlife.blob.core.windows.net/lila-wildlife/"
    "caltech-unzipped/cct_images"
)

SOURCE_ARTIFACTS = {
    "oregon_critters.json": "975600087fee22bc7f1596db5322c68ddae278df7f2b864c2eb208421cf03c18",
    "channel_islands_camera_traps.json": "355e69035ca56db95bedb7d9da8df92270f7ea85956d229b742a7e89977661ce",
    "ena24_public.json": "77a35cbf44716557105c205a2d274c234884bf7913bcb1c90d265671b0c836f2",
    "nacti_20230920_bboxes.json": "31771496398b69f8b7546eb5f27e4438dd42099a5f284304aee6651a5ca7909e",
    "caltech_bboxes_20200316.json": "9cc208db67b7dcf3fa403920c203a416527628f76a6b838371ab654478bf2ea3",
    "caltech_images_20210113.json": "0ed31a7371effe1938bdcc5817713ef35c21b868e9974be000fbb7886b95a34c",
    "CaltechCameraTrapsSplits_v0.json": "4deddfc58791124b37db375d45eeccb52d980b40cdd1dbac4881d0aae7ef34b4",
}

SOURCE_QUOTAS = {
    "oregon": {
        "train_positive": 1700, "valid_positive": 300,
        "train_negative": 700, "valid_negative": 0,
        "train_small": 380, "valid_small": 80,
    },
    "channel": {
        "train_positive": 1500, "valid_positive": 300,
        "train_negative": 500, "valid_negative": 200,
        "train_small": 900, "valid_small": 150,
    },
    "ena": {"train_positive": 600, "train_small": 100},
    "nacti": {"train_positive": 400, "train_small": 180},
    "cct": {
        "train_positive": 150, "valid_positive": 50,
        "train_negative": 532, "valid_negative": 50,
        "train_small": 40, "valid_small": 10,
    },
}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("data/training/wildlife-stage2")
    )
    parser.add_argument(
        "--stage1-root", type=Path, default=Path("data/training/wildlife-stage1")
    )
    parser.add_argument(
        "--local-review",
        type=Path,
        default=Path(
            "data/field-acceptance/"
            "2026-08-05-temporal-capture-mechanics-smoke/review-out"
        ),
    )
    parser.add_argument(
        "--holdout-manifest",
        type=Path,
        default=Path("data/evaluations/detector-promotion-v1/corpus-manifest.json"),
    )
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--plan-only", action="store_true")
    return parser.parse_args()


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError(
            f"source_annotation_unreadable:{path.name}"
        ) from error
    if not isinstance(payload, dict):
        raise WildlifeTrainingError(f"source_annotation_invalid:{path.name}")
    return payload


def _stable_order(
    values: Iterable[Any],
    *,
    seed: int,
    identity: Callable[[Any], str],
) -> list[Any]:
    return sorted(
        values,
        key=lambda item: sha256(f"{seed}:{identity(item)}".encode()).hexdigest(),
    )


def _encoded_url(base: str, path: str) -> str:
    return f"{base}/{quote(path, safe='/')}"


def _taxon_group(name: str) -> str:
    value = name.casefold()
    groups = (
        ("bird", ("bird", "jay", "owl", "grouse", "woodpecker", "thrush",
                  "junco", "robin", "quail", "crow", "chicken", "flicker",
                  "parulidae", "picidae", "poecile", "troglodytidae",
                  "strigidae", "catharus")),
        ("bat", ("bat",)),
        ("reptile_amphibian", ("reptile", "amphibian", "lizard")),
        ("invertebrate", ("invertebrate", "insect")),
        ("small_mammal", ("squirrel", "chipmunk", "rodent", "rabbit",
                          "cottontail", "lepor", "neotoma", "small mammal",
                          "mountain beaver", "woodchuck")),
        ("mesocarnivore", ("fox", "skunk", "raccoon", "opossum", "marten",
                           "mink", "weasel", "bobcat", "cat", "dog", "coyote")),
        ("ungulate", ("deer", "elk", "moose", "horse", "cow", "cattle",
                      "sheep", "boar")),
        ("large_carnivore", ("bear", "cougar", "mountain lion")),
    )
    for group, tokens in groups:
        if any(token in value for token in tokens):
            return group
    return "other_animal"


def _primary_taxon_group(boxes: Sequence[PixelBox]) -> str:
    order = {"very_small": 0, "small": 1, "medium": 2, "large": 3}
    primary = min(boxes, key=lambda box: (order[box.size_bucket], box.taxon))
    return _taxon_group(primary.taxon)


def _round_robin_grouped(
    candidates: Sequence[CorpusExample],
    *,
    total: int,
    seed: int,
    salt: str,
) -> list[CorpusExample]:
    grouped: dict[str, list[CorpusExample]] = defaultdict(list)
    for item in candidates:
        grouped[item.strongest_group].append(item)
    groups = _stable_order(grouped, seed=seed, identity=lambda value: f"{salt}:{value}")
    queues = {
        group: deque(_stable_order(
            grouped[group],
            seed=seed,
            identity=lambda item: f"{salt}:{item.example_id}",
        ))
        for group in groups
    }
    chosen: list[CorpusExample] = []
    while len(chosen) < total:
        progress = False
        for group in groups:
            if queues[group] and len(chosen) < total:
                chosen.append(queues[group].popleft())
                progress = True
        if not progress:
            raise WildlifeTrainingError(f"selection_quota_unavailable:{salt}:{total}")
    return chosen


def _balanced_positive_select(
    candidates: Sequence[CorpusExample],
    *,
    total: int,
    small_min: int,
    seed: int,
    salt: str,
) -> list[CorpusExample]:
    small = [
        item for item in candidates
        if item.size_bucket in ("very_small", "small")
    ]
    chosen = _round_robin_grouped(
        small, total=small_min, seed=seed, salt=f"{salt}:small"
    )
    identities = {item.example_id for item in chosen}
    remaining = [item for item in candidates if item.example_id not in identities]
    chosen.extend(_round_robin_grouped(
        remaining,
        total=total - len(chosen),
        seed=seed,
        salt=f"{salt}:fill",
    ))
    return chosen


def _choose_valid_groups(
    groups: Iterable[str], *, count: int, seed: int, salt: str
) -> set[str]:
    ordered = _stable_order(
        set(groups), seed=seed, identity=lambda value: f"{salt}:{value}"
    )
    if len(ordered) < count:
        raise WildlifeTrainingError(f"validation_groups_unavailable:{salt}")
    return set(ordered[:count])


def _source_example(
    *,
    source_key: str,
    source_id: str,
    source_version: str,
    image_id: str,
    source_url: str,
    license_name: str,
    geography: str,
    width: int,
    height: int,
    split: str,
    site_id: str | None,
    camera_id: str | None,
    sequence_id: str | None,
    captured_at: str | None,
    boxes: Sequence[PixelBox],
    negative_kind: str | None = None,
) -> CorpusExample:
    positive = bool(boxes)
    return CorpusExample(
        example_id=f"{source_key}:{image_id}",
        source_id=source_id,
        source_version=source_version,
        source_identity=f"{source_key}:image:{image_id}",
        parent_identity=(
            f"{source_key}:sequence:{sequence_id}" if sequence_id else None
        ),
        image=(
            f"dataset/{split}/{source_key}-"
            f"{sha256(image_id.encode()).hexdigest()[:20]}.jpg"
        ),
        source_url=source_url,
        source_license=license_name,
        geography=geography,
        width=int(width),
        height=int(height),
        split=split,  # type: ignore[arg-type]
        site_id=site_id,
        camera_id=camera_id,
        sequence_id=sequence_id,
        captured_at=captured_at,
        truth_authority=(
            "public_human_bbox" if positive else "public_curated_empty"
        ),
        boxes=tuple(boxes),
        negative_kind=negative_kind,
        taxon_group=_primary_taxon_group(boxes) if positive else None,
    )



def _validated_boxes(
    annotations: Sequence[dict[str, Any]],
    *,
    categories: dict[Any, str],
    excluded: set[str],
    width: int,
    height: int,
) -> tuple[PixelBox, ...] | None:
    """Return exact source boxes, excluding an image if any animal box is invalid."""

    boxes: list[PixelBox] = []
    try:
        for annotation in annotations:
            name = categories[annotation["category_id"]]
            if name.casefold() in excluded or not annotation.get("bbox"):
                continue
            box = PixelBox(*annotation["bbox"], name)
            box.normalized_xyxy(int(width), int(height))
            boxes.append(box)
    except (KeyError, TypeError, WildlifeTrainingError):
        return None
    return tuple(boxes)


def _oregon_group(image: dict[str, Any]) -> str:
    """Recover a conservative physical-site group when empty labels use *_NA."""

    location = str(image["location"])
    if location.endswith("_NA"):
        project = location.removesuffix("_NA")
        stem = Path(str(image["file_name"])).stem
        token = stem.split("_", 1)[0]
        if not token or token.casefold() in {"img", "image"}:
            raise WildlifeTrainingError("oregon_empty_camera_unrecoverable")
        location = f"{project}_{token}"
    return re.sub(r"-[BGT]$", "", location, flags=re.IGNORECASE)


def _select_oregon(root: Path, *, seed: int) -> list[CorpusExample]:
    payload = _load(root / "source/oregon-critters/oregon_critters.json")
    categories = {item["id"]: item["name"] for item in payload["categories"]}
    images = {item["id"]: item for item in payload["images"]}
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in payload["annotations"]:
        rows[annotation["image_id"]].append(annotation)
    valid_locations = _choose_valid_groups(
        (_oregon_group(item) for item in images.values()),
        count=240, seed=seed, salt="oregon",
    )
    pools = _empty_pools()
    for image_id, image in images.items():
        annotations = rows.get(image_id, [])
        names = {categories[item["category_id"]] for item in annotations}
        if "human" in names:
            continue
        location = _oregon_group(image)
        split = "valid" if location in valid_locations else "train"
        boxes = _validated_boxes(
            annotations,
            categories=categories,
            excluded={"empty", "human"},
            width=image["width"],
            height=image["height"],
        )
        if boxes is None:
            continue
        negative = not boxes and names == {"empty"}
        if not boxes and not negative:
            continue
        example = _source_example(
            source_key="oregon",
            source_id="oregon-critters-20260304",
            source_version="2026.03.04",
            image_id=str(image_id),
            source_url=_encoded_url(OREGON_BASE, image["file_name"]),
            license_name="CDLA-Permissive-2.0",
            geography="Western Oregon, United States",
            width=image["width"], height=image["height"], split=split,
            site_id=f"oregon-location-{location}",
            camera_id=f"oregon-location-{location}",
            sequence_id=None, captured_at=image.get("datetime"), boxes=boxes,
            negative_kind="camera_trap_empty_false_trigger" if negative else None,
        )
        pools[split]["positive" if boxes else "negative"].append(example)
    return _select_from_pools(pools, SOURCE_QUOTAS["oregon"], seed, "oregon")


def _empty_pools() -> dict[str, dict[str, list[CorpusExample]]]:
    return {
        "train": {"positive": [], "negative": []},
        "valid": {"positive": [], "negative": []},
    }


def _select_from_pools(
    pools: dict[str, dict[str, list[CorpusExample]]],
    quota: dict[str, int],
    seed: int,
    salt: str,
) -> list[CorpusExample]:
    selected: list[CorpusExample] = []
    for split in ("train", "valid"):
        selected.extend(_balanced_positive_select(
            pools[split]["positive"],
            total=quota[f"{split}_positive"],
            small_min=quota[f"{split}_small"],
            seed=seed, salt=f"{salt}:{split}:positive",
        ))
        selected.extend(_round_robin_grouped(
            pools[split]["negative"],
            total=quota[f"{split}_negative"],
            seed=seed, salt=f"{salt}:{split}:negative",
        ))
    return selected


def _select_channel(root: Path, *, seed: int) -> list[CorpusExample]:
    payload = _load(
        root / "source/channel-islands-camera-traps/channel_islands_camera_traps.json"
    )
    categories = {item["id"]: item["name"] for item in payload["categories"]}
    images = {item["id"]: item for item in payload["images"]}
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in payload["annotations"]:
        rows[annotation["image_id"]].append(annotation)
    valid_locations = _choose_valid_groups(
        (str(item["location"]) for item in images.values()),
        count=12, seed=seed, salt="channel",
    )
    pools = _empty_pools()
    for image_id, image in images.items():
        annotations = rows.get(image_id, [])
        names = {categories[item["category_id"]] for item in annotations}
        if "human" in names:
            continue
        location = str(image["location"])
        split = "valid" if location in valid_locations else "train"
        boxes = _validated_boxes(
            annotations,
            categories=categories,
            excluded={"empty", "human"},
            width=image["width"],
            height=image["height"],
        )
        if boxes is None:
            continue
        negative = not boxes and names == {"empty"}
        if not boxes and not negative:
            continue
        example = _source_example(
            source_key="channel",
            source_id="channel-islands-camera-traps-2020",
            source_version="2020 public non-human export",
            image_id=str(image_id),
            source_url=_encoded_url(CHANNEL_BASE, image["file_name"]),
            license_name="CDLA-Permissive-2.0",
            geography="California Channel Islands, United States",
            width=image["width"], height=image["height"], split=split,
            site_id=f"channel-location-{location}",
            camera_id=f"channel-location-{location}",
            sequence_id=f"channel-sequence-{image['seq_id']}",
            captured_at=None, boxes=boxes,
            negative_kind="camera_trap_empty_scene" if negative else None,
        )
        pools[split]["positive" if boxes else "negative"].append(example)
    return _select_from_pools(pools, SOURCE_QUOTAS["channel"], seed, "channel")


def _select_ena(root: Path, *, seed: int) -> list[CorpusExample]:
    payload = _load(root / "source/ena24/ena24_public.json")
    categories = {item["id"]: item["name"] for item in payload["categories"]}
    images = {item["id"]: item for item in payload["images"]}
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in payload["annotations"]:
        rows[annotation["image_id"]].append(annotation)
    candidates: list[CorpusExample] = []
    for image_id, image_annotations in rows.items():
        image = images[image_id]
        boxes = _validated_boxes(
            image_annotations,
            categories=categories,
            excluded={"vehicle"},
            width=image["width"],
            height=image["height"],
        )
        if boxes is None:
            continue
        if boxes:
            candidates.append(_source_example(
                source_key="ena24",
                source_id="ena24-detection-public-2016",
                source_version="2016 public non-human detection export",
                image_id=str(image_id),
                source_url=_encoded_url(ENA_BASE, image["file_name"]),
                license_name="CDLA-Permissive-2.0",
                geography="Eastern North America",
                width=image["width"], height=image["height"], split="train",
                site_id=None, camera_id=None, sequence_id=None,
                captured_at=None, boxes=boxes,
            ))
    quota = SOURCE_QUOTAS["ena"]
    return _balanced_positive_select(
        candidates, total=quota["train_positive"],
        small_min=quota["train_small"], seed=seed, salt="ena24:train",
    )


def _nacti_camera(study: str, image_id: str) -> str:
    return image_id.rsplit("_img", 1)[0] if study == "CPW" else image_id.split("_", 1)[0]


def _select_nacti(root: Path, *, seed: int) -> list[CorpusExample]:
    payload = _load(root / "source/nacti/nacti_20230920_bboxes.json")
    images = {item["id"]: item for item in payload["images"]}
    rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for annotation in payload["annotations"]:
        if annotation["category_id"] == 1 and annotation.get("bbox"):
            rows[annotation["image_id"]].append(annotation)
    candidates: list[CorpusExample] = []
    for uuid, image_annotations in rows.items():
        image = images[uuid]
        image_id, study = str(image["image_id"]), str(image["study"])
        boxes = _validated_boxes(
            image_annotations,
            categories={1: "animal (NACTI bbox subset)"},
            excluded=set(),
            width=image["width"],
            height=image["height"],
        )
        if boxes is None:
            continue
        candidates.append(_source_example(
            source_key="nacti",
            source_id="nacti-human-corrected-boxes-20230920",
            source_version="bbox export 2023-09-20 joined to metadata 1.14",
            image_id=image_id,
            source_url=_encoded_url(NACTI_BASE, image["file_name"]),
            license_name="CDLA-Permissive-1.0",
            geography="United States",
            width=image["width"], height=image["height"], split="train",
            site_id=f"nacti-study-{study}",
            camera_id=f"nacti-camera-{study}-{_nacti_camera(study, image_id)}",
            sequence_id=None, captured_at=None, boxes=boxes,
        ))
    quota = SOURCE_QUOTAS["nacti"]
    return _balanced_positive_select(
        candidates, total=quota["train_positive"],
        small_min=quota["train_small"], seed=seed, salt="nacti:train",
    )


def _select_cct(stage1_root: Path, *, seed: int) -> list[CorpusExample]:
    source = stage1_root / "source/caltech-camera-traps"
    bbox_payload = _load(source / "caltech_bboxes_20200316.json")
    label_payload = _load(source / "caltech_images_20210113.json")
    splits = _load(source / "CaltechCameraTrapsSplits_v0.json")["splits"]
    split_locations = {
        "train": set(str(value) for value in splits["train"]),
        "valid": set(str(value) for value in splits["val"]),
    }
    categories = {item["id"]: item["name"] for item in bbox_payload["categories"]}
    images = {item["id"]: item for item in bbox_payload["images"]}
    boxes: dict[str, list[PixelBox]] = defaultdict(list)
    for row in bbox_payload["annotations"]:
        name = categories[row["category_id"]]
        if name not in {"empty", "car"} and row.get("bbox"):
            boxes[row["image_id"]].append(PixelBox(*row["bbox"], name))
    label_categories = {item["id"]: item["name"] for item in label_payload["categories"]}
    labels: dict[str, list[str]] = defaultdict(list)
    for row in label_payload["annotations"]:
        labels[row["image_id"]].append(label_categories[row["category_id"]])
    pools = _empty_pools()
    for image_id, image in images.items():
        location = str(image["location"])
        if location not in split_locations["train"] | split_locations["valid"]:
            continue
        split = "train" if location in split_locations["train"] else "valid"
        if image_id in boxes:
            pools[split]["positive"].append(_source_example(
                source_key="cct",
                source_id="caltech-camera-traps-20200316",
                source_version="bounding boxes 20200316",
                image_id=str(image_id),
                source_url=_encoded_url(CCT_BASE, image["file_name"]),
                license_name="CDLA-Permissive-2.0",
                geography="Southwestern United States",
                width=image["width"], height=image["height"], split=split,
                site_id=f"cct-location-{location}",
                camera_id=f"cct-location-{location}",
                sequence_id=f"cct-sequence-{image['seq_id']}",
                captured_at=image.get("date_captured"), boxes=boxes[image_id],
            ))
    for image in label_payload["images"]:
        image_id, location = image["id"], str(image["location"])
        if labels.get(image_id) != ["empty"]:
            continue
        if location not in split_locations["train"] | split_locations["valid"]:
            continue
        split = "train" if location in split_locations["train"] else "valid"
        pools[split]["negative"].append(_source_example(
            source_key="cct",
            source_id="caltech-camera-traps-20200316",
            source_version="image labels 20210113",
            image_id=str(image_id),
            source_url=_encoded_url(CCT_BASE, image["file_name"]),
            license_name="CDLA-Permissive-2.0",
            geography="Southwestern United States",
            width=image["width"], height=image["height"], split=split,
            site_id=f"cct-location-{location}",
            camera_id=f"cct-location-{location}",
            sequence_id=f"cct-sequence-{image['seq_id']}",
            captured_at=image.get("date_captured"), boxes=(),
            negative_kind="camera_trap_empty_scene",
        ))
    return _select_from_pools(pools, SOURCE_QUOTAS["cct"], seed, "cct")


def _select_local_negatives(review_root: Path) -> list[CorpusExample]:
    annotation = _load(review_root / "annotation.json")
    session_id = annotation.get("capture_session_id")
    if not isinstance(session_id, str) or not session_id:
        raise WildlifeTrainingError("local_review_session_invalid")
    selected: list[CorpusExample] = []
    for frame in annotation.get("frames", []):
        provenance = frame.get("provenance") or {}
        if (
            frame.get("whole_frame_truth") != "no"
            or frame.get("boxes")
            or provenance.get("reviewer") != "zkelder"
            or provenance.get("truth_source") != "full_frame_inspection"
            or provenance.get("whole_frame_independently_confirmed") is not True
        ):
            continue
        frame_id = str(frame["frame_id"])
        paths = (
            review_root / "frames" / f"{frame_id}.jpg",
            review_root / "high-resolution" / f"{frame_id}.jpg",
        )
        image_path = next((path for path in paths if path.is_file()), None)
        if image_path is None:
            raise WildlifeTrainingError(f"local_review_frame_missing:{frame_id}")
        with Image.open(image_path) as opened:
            width, height = opened.size
        selected.append(CorpusExample(
            example_id=f"local-review:{frame_id}",
            source_id="mockingbird-local-human-corrections-20260812",
            source_version="reviewed local exports through 2026-08-12",
            source_identity=f"mockingbird-local:image:{frame_id}",
            parent_identity=f"mockingbird-local:session:{session_id}",
            image=f"dataset/train/local-{frame_id[:20]}.jpg",
            source_url=image_path.resolve().as_uri(),
            source_license="user-owned local data; no redistribution",
            geography="deployment-local North American backyard",
            width=width, height=height, split="train",
            site_id="mockingbird-local-site",
            camera_id="mockingbird-local-camera",
            sequence_id=f"mockingbird-local-session-{session_id}",
            captured_at=provenance.get("reviewed_at_iso"),
            truth_authority="human_reviewed_empty",
            boxes=(), negative_kind="local_static_clutter_night",
        ))
    if len(selected) != 18:
        raise WildlifeTrainingError(f"local_reviewed_negative_count_changed:{len(selected)}")
    return selected


def _context_crops(
    positives: Sequence[CorpusExample], *, seed: int
) -> list[CorpusExample]:
    candidates: list[CorpusExample] = []
    for source in positives:
        if source.split != "train" or source.size_bucket not in ("very_small", "small"):
            continue
        bounds, boxes = context_crop_bounds(
            image_width=source.width, image_height=source.height,
            boxes=source.boxes, context_scale=5.0, minimum_side=256,
        )
        left, top, right, bottom = bounds
        width, height = right - left, bottom - top
        if width >= source.width * 0.8 and height >= source.height * 0.8:
            continue
        crop_key = f"{left}-{top}-{right}-{bottom}"
        candidates.append(replace(
            source,
            example_id=f"{source.example_id}:context:{crop_key}",
            source_identity=f"{source.source_identity}:context:{crop_key}",
            parent_identity=source.source_identity,
            image=(
                "dataset/train/context-"
                f"{sha256((source.example_id + crop_key).encode()).hexdigest()[:20]}.jpg"
            ),
            width=width, height=height, boxes=boxes,
            augmentation_kind="context_crop",
        ))
    return _round_robin_grouped(
        candidates, total=CONTEXT_CROP_TOTAL, seed=seed, salt="stage2:context"
    )


def select_examples(
    *,
    output_root: Path,
    stage1_root: Path,
    local_review_root: Path,
    seed: int,
) -> list[CorpusExample]:
    examples: list[CorpusExample] = []
    examples.extend(_select_oregon(output_root, seed=seed))
    examples.extend(_select_channel(output_root, seed=seed))
    examples.extend(_select_ena(output_root, seed=seed))
    examples.extend(_select_nacti(output_root, seed=seed))
    examples.extend(_select_cct(stage1_root, seed=seed))
    examples.extend(_select_local_negatives(local_review_root))
    base_positives = [item for item in examples if item.is_positive]
    examples.extend(_context_crops(base_positives, seed=seed))
    if len(base_positives) != BASE_POSITIVE_TOTAL:
        raise WildlifeTrainingError(f"stage2_base_positive_count_invalid:{len(base_positives)}")
    if sum(not item.is_positive for item in examples) != NEGATIVE_TOTAL:
        raise WildlifeTrainingError("stage2_negative_count_invalid")
    if len(examples) != TARGET_TOTAL:
        raise WildlifeTrainingError(f"stage2_total_invalid:{len(examples)}")
    if len({item.example_id for item in examples}) != TARGET_TOTAL:
        raise WildlifeTrainingError("stage2_example_identity_collision")
    assert_no_group_leakage(examples)
    return sorted(examples, key=lambda item: item.example_id)


def _verify_sources(output_root: Path, stage1_root: Path) -> dict[str, str]:
    paths = {
        "oregon_critters.json": output_root / "source/oregon-critters/oregon_critters.json",
        "channel_islands_camera_traps.json": output_root / "source/channel-islands-camera-traps/channel_islands_camera_traps.json",
        "ena24_public.json": output_root / "source/ena24/ena24_public.json",
        "nacti_20230920_bboxes.json": output_root / "source/nacti/nacti_20230920_bboxes.json",
        "caltech_bboxes_20200316.json": stage1_root / "source/caltech-camera-traps/caltech_bboxes_20200316.json",
        "caltech_images_20210113.json": stage1_root / "source/caltech-camera-traps/caltech_images_20210113.json",
        "CaltechCameraTrapsSplits_v0.json": stage1_root / "source/caltech-camera-traps/CaltechCameraTrapsSplits_v0.json",
    }
    checksums: dict[str, str] = {}
    for name, path in paths.items():
        actual = sha256_file(path)
        if actual != SOURCE_ARTIFACTS[name]:
            raise WildlifeTrainingError(f"source_checksum_mismatch:{name}")
        checksums[name] = actual
    return checksums


def _copy_or_download(example: CorpusExample, destination: Path) -> None:
    parsed = urlparse(example.source_url)
    if parsed.scheme == "file":
        with Path(unquote(parsed.path)).open("rb") as source, destination.open("wb") as output:
            copyfileobj(source, output, length=1024 * 1024)
        return
    request = Request(
        example.source_url,
        headers={"User-Agent": "MockingBird-Wildlife-Stage2/0.2"},
    )
    with urlopen(request, timeout=60) as response, destination.open("wb") as output:
        copyfileobj(response, output, length=1024 * 1024)


def _materialize_full(example: CorpusExample, *, root: Path) -> CorpusExample:
    destination = root / example.image
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file():
        for attempt in range(5):
            temporary: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent, prefix=f".{destination.name}.",
                    suffix=".part", delete=False,
                ) as output:
                    temporary = Path(output.name)
                _copy_or_download(example, temporary)
                os.replace(temporary, destination)
                break
            except (HTTPError, URLError, TimeoutError, OSError) as error:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
                if attempt == 4:
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
        raise WildlifeTrainingError(f"image_decode_failed:{example.example_id}") from error
    if actual_size != (example.width, example.height):
        raise WildlifeTrainingError(
            f"image_dimensions_mismatch:{example.example_id}:{actual_size}"
        )
    return replace(
        example, sha256=sha256_file(destination),
        dhash64=dhash64(destination), phash64=phash64(destination),
    )


def _materialize_crop(
    example: CorpusExample, *, source: CorpusExample, root: Path
) -> CorpusExample:
    destination, source_path = root / example.image, root / source.image
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.is_file():
        source_box, crop_box = source.boxes[0], example.boxes[0]
        left = int(round(source_box.x - crop_box.x))
        top = int(round(source_box.y - crop_box.y))
        with Image.open(source_path) as opened:
            opened.convert("RGB").crop((
                left, top, left + example.width, top + example.height
            )).save(destination, format="JPEG", quality=95, subsampling=0)
    with Image.open(destination) as opened:
        if opened.size != (example.width, example.height):
            raise WildlifeTrainingError(f"context_crop_dimensions_mismatch:{example.example_id}")
    return replace(
        example, sha256=sha256_file(destination),
        dhash64=dhash64(destination), phash64=phash64(destination),
    )


def materialize(
    examples: Sequence[CorpusExample], *, root: Path, workers: int
) -> list[CorpusExample]:
    if workers < 1 or workers > 32:
        raise WildlifeTrainingError("download_worker_bound_invalid")
    full = [item for item in examples if item.augmentation_kind == "full_scene"]
    completed: list[CorpusExample] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_materialize_full, item, root=root): item.example_id
            for item in full
        }
        for index, future in enumerate(as_completed(futures), start=1):
            completed.append(future.result())
            if index % 250 == 0:
                print(f"materialized full scenes {index}/{len(full)}", flush=True)
    by_identity = {item.source_identity: item for item in completed}
    for item in examples:
        if item.augmentation_kind == "context_crop":
            if not item.parent_identity or item.parent_identity not in by_identity:
                raise WildlifeTrainingError(f"context_crop_parent_missing:{item.example_id}")
            completed.append(_materialize_crop(
                item, source=by_identity[item.parent_identity], root=root
            ))
    return sorted(completed, key=lambda item: item.example_id)


def _internal_split_report(examples: Sequence[CorpusExample]) -> dict[str, Any]:
    train = [item for item in examples if item.split == "train"]
    valid = [item for item in examples if item.split == "valid"]
    train_hashes = {item.sha256: item.example_id for item in train}
    exact = [
        {"train": train_hashes[item.sha256], "valid": item.example_id}
        for item in valid if item.sha256 in train_hashes
    ]
    near: list[dict[str, Any]] = []
    for validation in valid:
        assert validation.dhash64 and validation.phash64
        for training in train:
            assert training.dhash64 and training.phash64
            distance = dhash_distance(validation.dhash64, training.dhash64)
            frequency_distance = phash_distance(validation.phash64, training.phash64)
            if distance <= 2 and frequency_distance <= 4:
                near.append({
                    "train": training.example_id, "valid": validation.example_id,
                    "dhash_distance": distance,
                    "phash_distance": frequency_distance,
                })
    return {
        "exact_content_cross_split": exact,
        "near_duplicate_cross_split": near,
        "passed": not (exact or near),
        "near_duplicate_policy": "dhash64 <= 2 corroborated by phash64 <= 4",
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def _write_coco(examples: Sequence[CorpusExample], *, root: Path, split: str) -> None:
    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    annotation_id = 1
    rows = sorted(
        (item for item in examples if item.split == split),
        key=lambda item: item.example_id,
    )
    for image_id, example in enumerate(rows, start=1):
        images.append({
            "id": image_id, "file_name": Path(example.image).name,
            "width": example.width, "height": example.height,
            "mockingbird_example_id": example.example_id,
            "domain_role": example.domain_role,
            "augmentation_kind": example.augmentation_kind,
        })
        for box in example.boxes:
            annotations.append({
                "id": annotation_id, "image_id": image_id, "category_id": 1,
                "bbox": [box.x, box.y, box.width, box.height],
                "area": box.area, "iscrowd": 0, "source_taxon": box.taxon,
                "source_pixel_size_bucket": box.size_bucket,
                "truth_authority": example.truth_authority,
            })
            annotation_id += 1
    _write_json(root / "dataset" / split / "_annotations.coco.json", {
        "info": {
            "description": "MockingBird Stage-2 one-class wildlife detector corpus",
            "version": "0.2", "creates_product_truth": False,
        },
        "licenses": [],
        "categories": [{"id": 1, "name": "animal", "supercategory": "animal"}],
        "images": images, "annotations": annotations,
    })


def main() -> int:
    args = _args()
    repository_root = Path(__file__).resolve().parents[1]
    output_root = args.output.resolve()
    try:
        output_root.relative_to((repository_root / "data").resolve())
    except ValueError as error:
        raise SystemExit("Stage-2 output must remain below ignored repository data.") from error
    registry = load_stage2_source_registry()
    for source_id in (
        "oregon-critters-20260304",
        "channel-islands-camera-traps-2020",
        "ena24-detection-public-2016",
        "nacti-human-corrected-boxes-20230920",
        "caltech-camera-traps-20200316",
        "mockingbird-local-human-corrections-20260812",
    ):
        require_materialization_source(registry, source_id)
    checksums = _verify_sources(output_root, args.stage1_root.resolve())
    examples = select_examples(
        output_root=output_root,
        stage1_root=args.stage1_root.resolve(),
        local_review_root=args.local_review.resolve(),
        seed=args.seed,
    )
    plan = {
        "corpus_id": "north-american-backyard-wildlife-stage2-v0.2",
        "seed": args.seed, "summary": corpus_summary(examples),
        "source_artifact_checksums": checksums,
        "registry_fingerprint": registry["fingerprint"],
        "source_quotas": SOURCE_QUOTAS,
        "base_positive_images": BASE_POSITIVE_TOTAL,
        "context_crop_examples": CONTEXT_CROP_TOTAL,
        "negative_images": NEGATIVE_TOTAL,
        "transfer_only_images": 0,
        "coco_policy": (
            "excluded from canonical Stage-2; irrelevant global categories are "
            "therefore absent and no COCO ablation is required"
        ),
        "frozen_75_selection_use": "prohibited",
        "estimated_materialized_bytes": 8_000_000_000,
        "estimated_checkpoint_bytes": 5_000_000_000,
    }
    _write_json(output_root / "selection-plan.json", plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.plan_only:
        return 0
    holdout = verify_frozen_benchmark(
        args.holdout_manifest.resolve(), repository_root=repository_root
    )
    materialized = materialize(examples, root=output_root, workers=args.workers)
    contamination = contamination_report(materialized, holdout)
    internal = _internal_split_report(materialized)
    _write_json(output_root / "contamination-report.json", contamination)
    _write_json(output_root / "internal-split-contamination.json", internal)
    manifest = build_stage2_corpus_manifest(
        materialized,
        registry_fingerprint=registry["fingerprint"],
        contamination=contamination,
        internal_split_contamination=internal,
        selection_policy={
            "seed": args.seed, "target_total": TARGET_TOTAL,
            "base_positive_images": BASE_POSITIVE_TOTAL,
            "context_crop_examples": CONTEXT_CROP_TOTAL,
            "negative_images": NEGATIVE_TOTAL, "source_quotas": SOURCE_QUOTAS,
            "oregon_split": "own deterministic location-grouped split",
            "channel_split": "own deterministic camera-location-grouped split",
            "cct_split": "official location-grouped train/validation split",
            "ena_split": "train-only because camera lineage is absent",
            "nacti_split": "train-only because bbox sequence lineage is incomplete",
            "local_split": "train-only single reviewed session",
            "neighboring_sequence_random_split": False,
            "image_label_only_positives_included": 0,
            "agent_or_model_truth_included": 0,
            "transfer_only_images_included": 0,
        },
    )
    _write_coco(materialized, root=output_root, split="train")
    _write_coco(materialized, root=output_root, split="valid")
    _write_json(output_root / "stage2-manifest.json", manifest)
    print(json.dumps({
        "manifest": str(output_root / "stage2-manifest.json"),
        "semantic_fingerprint": manifest["semantic_fingerprint"],
        "split_fingerprint": manifest["split_fingerprint"],
        "summary": manifest["summary"],
        "contamination_passed": contamination["passed"],
        "internal_split_contamination_passed": internal["passed"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except WildlifeTrainingError as error:
        print(f"wildlife Stage-2 materialization failed: {error}", file=sys.stderr)
        raise SystemExit(2) from error
