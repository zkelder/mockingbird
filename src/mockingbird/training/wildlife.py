"""Governed, filesystem-only wildlife detector training contracts.

This module is deliberately independent of the product repository and runtime.
Public annotations and later human localization review may become training
truth; model or agent suggestions never do.  Generated corpora, checkpoints,
and reports remain below ignored ``data/`` paths.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Literal, Mapping, Sequence
import numpy as np

from PIL import Image

REGISTRY_FILENAME = "wildlife_source_registry_v0_1.json"
REGISTRY_ID = "north-american-backyard-wildlife-sources-v0.1"
STAGE2_REGISTRY_FILENAME = "wildlife_source_registry_v0_2.json"
STAGE2_REGISTRY_ID = "north-american-backyard-wildlife-sources-v0.2"
STAGE1_CORPUS_ID = "north-american-backyard-wildlife-stage1-v0.1"
STAGE2_CORPUS_ID = "north-american-backyard-wildlife-stage2-v0.2"
FROZEN_BENCHMARK_SEMANTIC_FINGERPRINT = (
    "24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec"
)
FROZEN_BENCHMARK_FILE_SHA256 = (
    "45b46c7c57a9cfe028682f4d5d3d629e5c255222d5dcfde9735786b6731bad78"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

SizeBucket = Literal["very_small", "small", "medium", "large"]
TruthAuthority = Literal[
    "public_human_bbox",
    "public_curated_empty",
    "human_localization",
    "human_reviewed_empty",
]
Split = Literal["train", "valid"]
DomainRole = Literal["target_domain", "transfer_only"]
AugmentationKind = Literal["full_scene", "context_crop"]
_SIZE_ORDER: dict[SizeBucket, int] = {
    "very_small": 0,
    "small": 1,
    "medium": 2,
    "large": 3,
}
_ELIGIBLE_SOURCE_STATUSES = {
    "accepted",
    "accepted_with_per_image_license_filter",
}
_ELIGIBLE_AUTHORITIES = {
    "public_human_bbox",
    "public_curated_empty",
    "human_localization",
    "human_reviewed_empty",
}


class WildlifeTrainingError(ValueError):
    """A fail-closed corpus, provenance, or experiment validation error."""


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def canonical_fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return sha256(encoded).hexdigest()


def _registry_path() -> Path:
    return Path(__file__).with_name(REGISTRY_FILENAME)


def load_source_registry(path: Path | None = None) -> dict[str, Any]:
    try:
        payload = json.loads((path or _registry_path()).read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError("source_registry_unreadable") from error
    if payload.get("schema_version") != 1 or payload.get("registry_id") != REGISTRY_ID:
        raise WildlifeTrainingError("source_registry_identity_invalid")
    sources = payload.get("sources")
    if not isinstance(sources, list) or len(sources) != 29:
        raise WildlifeTrainingError("source_registry_requires_29_sources")
    required = {
        "source_id",
        "version",
        "status",
        "canonical_url",
        "license",
        "geography",
        "annotation_type",
        "site_camera_metadata",
        "taxonomic_distribution",
        "negative_availability",
        "download_mechanism",
        "known_biases",
    }
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not required.issubset(source):
            raise WildlifeTrainingError("source_registry_entry_incomplete")
        source_id = source["source_id"]
        if (
            not isinstance(source_id, str)
            or not source_id.strip()
            or source_id in identities
        ):
            raise WildlifeTrainingError("source_registry_identity_invalid")
        identities.add(source_id)
        status = source["status"]
        if status not in _ELIGIBLE_SOURCE_STATUSES and not source.get("block_reason"):
            raise WildlifeTrainingError("blocked_source_requires_reason")
        if status in _ELIGIBLE_SOURCE_STATUSES and any(
            token in str(source["license"]).lower()
            for token in ("unverified", "unclear", "requires review")
        ):
            raise WildlifeTrainingError("accepted_source_license_unclear")
    payload["fingerprint"] = canonical_fingerprint(
        {key: value for key, value in payload.items() if key != "fingerprint"}
    )
    return payload


def load_stage2_source_registry(path: Path | None = None) -> dict[str, Any]:
    """Load the separately versioned Stage-2 source decisions fail-closed."""

    registry_path = path or Path(__file__).with_name(STAGE2_REGISTRY_FILENAME)
    try:
        payload = json.loads(registry_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError("stage2_source_registry_unreadable") from error
    if (
        payload.get("schema_version") != 2
        or payload.get("registry_id") != STAGE2_REGISTRY_ID
    ):
        raise WildlifeTrainingError("stage2_source_registry_identity_invalid")
    sources = payload.get("sources")
    if not isinstance(sources, list) or len(sources) < 8:
        raise WildlifeTrainingError("stage2_source_registry_incomplete")
    required = {
        "source_id",
        "version",
        "status",
        "domain_role",
        "canonical_url",
        "license",
        "geography",
        "annotation_type",
        "site_camera_metadata",
        "taxonomic_distribution",
        "negative_availability",
        "download_mechanism",
        "known_biases",
        "decision_evidence",
    }
    identities: set[str] = set()
    for source in sources:
        if not isinstance(source, dict) or not required.issubset(source):
            raise WildlifeTrainingError("stage2_source_registry_entry_incomplete")
        source_id = source["source_id"]
        if not isinstance(source_id, str) or not source_id or source_id in identities:
            raise WildlifeTrainingError("stage2_source_registry_identity_invalid")
        identities.add(source_id)
        if source["domain_role"] not in ("target_domain", "transfer_only"):
            raise WildlifeTrainingError("stage2_source_domain_role_invalid")
        if source["status"] in _ELIGIBLE_SOURCE_STATUSES:
            if source["domain_role"] == "transfer_only" and not (
                0 < source.get("max_sampling_weight", 0) <= 0.25
            ):
                raise WildlifeTrainingError("transfer_only_registry_weight_invalid")
        elif not source.get("block_reason"):
            raise WildlifeTrainingError("stage2_blocked_source_requires_reason")
    payload["fingerprint"] = canonical_fingerprint(
        {key: value for key, value in payload.items() if key != "fingerprint"}
    )
    return payload


def require_materialization_source(
    registry: Mapping[str, Any], source_id: str
) -> Mapping[str, Any]:
    for source in registry.get("sources", []):
        if source.get("source_id") == source_id:
            if source.get("status") not in _ELIGIBLE_SOURCE_STATUSES:
                raise WildlifeTrainingError("source_not_materialization_eligible")
            return source
    raise WildlifeTrainingError("source_not_registered")


@dataclass(frozen=True)
class PixelBox:
    """One source-pixel ``xywh`` animal box with preserved taxonomy."""

    x: float
    y: float
    width: float
    height: float
    taxon: str

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if (
            not all(
                isinstance(value, (int, float)) and math.isfinite(value)
                for value in values
            )
            or self.x < 0
            or self.y < 0
            or self.width <= 0
            or self.height <= 0
            or not self.taxon.strip()
        ):
            raise WildlifeTrainingError("invalid_pixel_box")

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def size_bucket(self) -> SizeBucket:
        return source_pixel_size_bucket(self.width, self.height)

    def normalized_xyxy(
        self, source_width: int, source_height: int
    ) -> tuple[float, float, float, float]:
        if source_width <= 0 or source_height <= 0:
            raise WildlifeTrainingError("invalid_source_dimensions")
        right = self.x + self.width
        bottom = self.y + self.height
        if right > source_width + 1e-6 or bottom > source_height + 1e-6:
            raise WildlifeTrainingError("box_outside_source")
        return (
            self.x / source_width,
            self.y / source_height,
            min(float(source_width), right) / source_width,
            min(float(source_height), bottom) / source_height,
        )


def source_pixel_size_bucket(width: float, height: float) -> SizeBucket:
    """COCO-area buckets measured in decoded source pixels, never model pixels."""

    if width <= 0 or height <= 0 or not math.isfinite(width * height):
        raise WildlifeTrainingError("invalid_box_size")
    area = width * height
    if area < 32**2:
        return "very_small"
    if area < 96**2:
        return "small"
    if area < 256**2:
        return "medium"
    return "large"


def primary_size_bucket(boxes: Sequence[PixelBox]) -> SizeBucket | None:
    if not boxes:
        return None
    return min((box.size_bucket for box in boxes), key=_SIZE_ORDER.__getitem__)


@dataclass(frozen=True)
class CorpusExample:
    example_id: str
    source_id: str
    source_version: str
    source_identity: str
    parent_identity: str | None
    image: str
    source_url: str
    source_license: str
    geography: str
    width: int
    height: int
    split: Split
    site_id: str | None
    camera_id: str | None
    sequence_id: str | None
    captured_at: str | None
    truth_authority: TruthAuthority
    boxes: tuple[PixelBox, ...]
    sha256: str | None = None
    dhash64: str | None = None
    phash64: str | None = None
    negative_kind: str | None = None
    domain_role: DomainRole = "target_domain"
    sampling_weight: float = 1.0
    taxon_group: str | None = None
    augmentation_kind: AugmentationKind = "full_scene"

    def __post_init__(self) -> None:
        text = (
            self.example_id,
            self.source_id,
            self.source_version,
            self.source_identity,
            self.image,
            self.source_url,
            self.source_license,
            self.geography,
        )
        if any(not value.strip() for value in text):
            raise WildlifeTrainingError("corpus_example_identity_incomplete")
        if self.width <= 0 or self.height <= 0:
            raise WildlifeTrainingError("invalid_source_dimensions")
        if self.truth_authority not in _ELIGIBLE_AUTHORITIES:
            raise WildlifeTrainingError("non_human_training_authority")
        negative_authorities = {"public_curated_empty", "human_reviewed_empty"}
        if self.boxes and self.truth_authority in negative_authorities:
            raise WildlifeTrainingError("negative_example_has_boxes")
        if not self.boxes and self.truth_authority not in negative_authorities:
            raise WildlifeTrainingError("positive_example_requires_human_boxes")
        if not self.boxes and not self.negative_kind:
            raise WildlifeTrainingError("negative_example_requires_composition")
        if self.domain_role not in ("target_domain", "transfer_only"):
            raise WildlifeTrainingError("domain_role_invalid")
        if not math.isfinite(self.sampling_weight) or not 0 < self.sampling_weight <= 1:
            raise WildlifeTrainingError("sampling_weight_invalid")
        if self.domain_role == "transfer_only":
            if self.sampling_weight > 0.25:
                raise WildlifeTrainingError("transfer_only_weight_exceeds_cap")
            if self.split == "valid":
                raise WildlifeTrainingError("transfer_only_validation_prohibited")
        if self.augmentation_kind not in ("full_scene", "context_crop"):
            raise WildlifeTrainingError("augmentation_kind_invalid")
        if self.augmentation_kind == "context_crop" and self.split != "train":
            raise WildlifeTrainingError("context_crop_validation_prohibited")
        for box in self.boxes:
            box.normalized_xyxy(self.width, self.height)
        if self.sha256 is not None and not _SHA256.fullmatch(self.sha256):
            raise WildlifeTrainingError("invalid_content_sha256")
        if self.dhash64 is not None and not re.fullmatch(r"[0-9a-f]{16}", self.dhash64):
            raise WildlifeTrainingError("invalid_dhash64")
        if self.phash64 is not None and not re.fullmatch(r"[0-9a-f]{16}", self.phash64):
            raise WildlifeTrainingError("invalid_phash64")

    @property
    def is_positive(self) -> bool:
        return bool(self.boxes)

    @property
    def size_bucket(self) -> SizeBucket | None:
        return primary_size_bucket(self.boxes)

    @property
    def strongest_group(self) -> str:
        lineage = (
            self.sequence_id or self.camera_id or self.site_id or self.source_identity
        )
        return f"{self.source_id}:{lineage}"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["boxes"] = [
            {
                **asdict(box),
                "size_bucket": box.size_bucket,
                "normalized_xyxy": box.normalized_xyxy(self.width, self.height),
            }
            for box in self.boxes
        ]
        payload["is_positive"] = self.is_positive
        payload["primary_size_bucket"] = self.size_bucket
        payload["strongest_group"] = self.strongest_group
        return payload


def context_crop_bounds(
    *,
    image_width: int,
    image_height: int,
    boxes: Sequence[PixelBox],
    context_scale: float = 5.0,
    minimum_side: int = 256,
) -> tuple[tuple[int, int, int, int], tuple[PixelBox, ...]]:
    """Return a square context crop and source-pixel boxes rebased into it.

    The crop is deterministic, includes every supplied box, and never fabricates
    localization. Callers should pass all human boxes that intersect the crop.
    """

    if image_width <= 0 or image_height <= 0 or not boxes:
        raise WildlifeTrainingError("context_crop_input_invalid")
    if not math.isfinite(context_scale) or context_scale < 1 or minimum_side <= 0:
        raise WildlifeTrainingError("context_crop_policy_invalid")
    for box in boxes:
        box.normalized_xyxy(image_width, image_height)
    left = min(box.x for box in boxes)
    top = min(box.y for box in boxes)
    right = max(box.x + box.width for box in boxes)
    bottom = max(box.y + box.height for box in boxes)
    center_x = (left + right) / 2
    center_y = (top + bottom) / 2
    side = min(
        max(image_width, image_height),
        max(
            float(minimum_side),
            (right - left) * context_scale,
            (bottom - top) * context_scale,
        ),
    )
    crop_width = min(image_width, int(round(side)))
    crop_height = min(image_height, int(round(side)))
    crop_left = min(
        max(0, int(round(center_x - crop_width / 2))),
        image_width - crop_width,
    )
    crop_top = min(
        max(0, int(round(center_y - crop_height / 2))),
        image_height - crop_height,
    )
    crop_right = crop_left + crop_width
    crop_bottom = crop_top + crop_height
    rebased = tuple(
        PixelBox(
            box.x - crop_left,
            box.y - crop_top,
            box.width,
            box.height,
            box.taxon,
        )
        for box in boxes
        if box.x >= crop_left
        and box.y >= crop_top
        and box.x + box.width <= crop_right + 1e-6
        and box.y + box.height <= crop_bottom + 1e-6
    )
    if len(rebased) != len(boxes):
        raise WildlifeTrainingError("context_crop_dropped_box")
    return (crop_left, crop_top, crop_right, crop_bottom), rebased


def assert_no_group_leakage(examples: Iterable[CorpusExample]) -> None:
    assignments: dict[str, Split] = {}
    identities: set[str] = set()
    for example in examples:
        if example.source_identity in identities:
            raise WildlifeTrainingError("duplicate_source_identity")
        identities.add(example.source_identity)
        existing = assignments.setdefault(example.strongest_group, example.split)
        if existing != example.split:
            raise WildlifeTrainingError("strongest_group_split_leakage")


def dhash64(path: Path) -> str:
    """Return a deterministic 64-bit difference hash for practical near-dup checks."""

    try:
        with Image.open(path) as opened:
            pixels = list(
                opened.convert("L").resize((9, 8), Image.Resampling.BILINEAR).getdata()
            )
    except (OSError, ValueError) as error:
        raise WildlifeTrainingError("image_unreadable") from error
    value = 0
    for row in range(8):
        for column in range(8):
            value = (value << 1) | int(
                pixels[row * 9 + column] > pixels[row * 9 + column + 1]
            )
    return f"{value:016x}"


def dhash_distance(first: str, second: str) -> int:
    if not re.fullmatch(r"[0-9a-f]{16}", first) or not re.fullmatch(
        r"[0-9a-f]{16}", second
    ):
        raise WildlifeTrainingError("invalid_dhash64")
    return (int(first, 16) ^ int(second, 16)).bit_count()


def phash64(path: Path) -> str:
    """Return a 64-bit DCT perceptual hash to corroborate coarse dHash hits."""

    try:
        with Image.open(path) as opened:
            pixels = np.asarray(
                opened.convert("L").resize((32, 32), Image.Resampling.LANCZOS),
                dtype=np.float32,
            )
    except (OSError, ValueError) as error:
        raise WildlifeTrainingError("image_unreadable") from error
    positions = np.arange(32, dtype=np.float32)
    frequencies = positions[:, None]
    transform = np.cos(np.pi * (2 * positions + 1) * frequencies / 64.0)
    coefficients = transform @ pixels @ transform.T
    low_frequency = coefficients[:8, :8].reshape(-1)
    median = float(np.median(low_frequency[1:]))
    value = 0
    for coefficient in low_frequency:
        value = (value << 1) | int(coefficient > median)
    return f"{value:016x}"


def phash_distance(first: str, second: str) -> int:
    if not re.fullmatch(r"[0-9a-f]{16}", first) or not re.fullmatch(
        r"[0-9a-f]{16}", second
    ):
        raise WildlifeTrainingError("invalid_phash64")
    return (int(first, 16) ^ int(second, 16)).bit_count()


@dataclass(frozen=True)
class HoldoutRecord:
    frame_id: str
    sha256: str
    dhash64: str
    phash64: str
    source_identity: str
    parent_identity: str | None
    site_id: str | None
    camera_id: str | None
    sequence_id: str | None


def verify_frozen_benchmark(
    manifest_path: Path, *, repository_root: Path
) -> tuple[HoldoutRecord, ...]:
    if sha256_file(manifest_path) != FROZEN_BENCHMARK_FILE_SHA256:
        raise WildlifeTrainingError("frozen_benchmark_manifest_checksum_mismatch")
    try:
        payload = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise WildlifeTrainingError("frozen_benchmark_manifest_unreadable") from error
    if (
        payload.get("semantic_fingerprint") != FROZEN_BENCHMARK_SEMANTIC_FINGERPRINT
        or payload.get("training_use") != "prohibited; evaluation/holdout only"
    ):
        raise WildlifeTrainingError("frozen_benchmark_identity_mismatch")
    frames = payload.get("frames")
    if not isinstance(frames, list) or len(frames) != 75:
        raise WildlifeTrainingError("frozen_benchmark_frame_count_mismatch")
    records: list[HoldoutRecord] = []
    for frame in frames:
        image_path = (repository_root / frame["image"]).resolve()
        try:
            image_path.relative_to(repository_root.resolve())
        except ValueError as error:
            raise WildlifeTrainingError("frozen_benchmark_path_escape") from error
        content_hash = sha256_file(image_path)
        if content_hash != frame["content_hash"]:
            raise WildlifeTrainingError("frozen_benchmark_image_checksum_mismatch")
        with Image.open(image_path) as opened:
            if opened.size != (frame["width"], frame["height"]):
                raise WildlifeTrainingError(
                    "frozen_benchmark_image_dimensions_mismatch"
                )
        provenance = str(frame.get("provenance", ""))
        scene_group = str(frame.get("scene_group", "unknown"))
        records.append(
            HoldoutRecord(
                frame_id=frame["frame_id"],
                sha256=content_hash,
                dhash64=dhash64(image_path),
                source_identity=f"mockingbird-frozen:{frame['frame_id']}",
                parent_identity=frame.get("parent_identity"),
                phash64=phash64(image_path),
                site_id="mockingbird-local-site",
                camera_id=scene_group,
                sequence_id=canonical_fingerprint(provenance)[:16]
                if provenance
                else None,
            )
        )
    return tuple(records)


def contamination_report(
    examples: Sequence[CorpusExample],
    holdout: Sequence[HoldoutRecord],
    *,
    near_duplicate_distance: int = 4,
    perceptual_hash_distance: int = 6,
) -> dict[str, Any]:
    if near_duplicate_distance < 0 or near_duplicate_distance > 64:
        raise WildlifeTrainingError("invalid_near_duplicate_distance")
    if perceptual_hash_distance < 0 or perceptual_hash_distance > 64:
        raise WildlifeTrainingError("invalid_perceptual_hash_distance")
    exact: list[dict[str, str]] = []
    identity: list[dict[str, str]] = []
    lineage: list[dict[str, str]] = []
    near: list[dict[str, Any]] = []
    holdout_hashes = {row.sha256: row for row in holdout}
    holdout_sources = {row.source_identity: row for row in holdout}
    holdout_parents = {
        row.parent_identity: row for row in holdout if row.parent_identity
    }
    holdout_groups = {
        (row.site_id, row.camera_id, row.sequence_id): row
        for row in holdout
        if row.site_id or row.camera_id or row.sequence_id
    }
    for example in examples:
        if not example.sha256 or not example.dhash64 or not example.phash64:
            raise WildlifeTrainingError(
                "contamination_check_requires_materialized_hashes"
            )
        if match := holdout_hashes.get(example.sha256):
            exact.append(
                {"example_id": example.example_id, "holdout_frame_id": match.frame_id}
            )
        if match := holdout_sources.get(example.source_identity):
            identity.append(
                {"example_id": example.example_id, "holdout_frame_id": match.frame_id}
            )
        if example.parent_identity and (
            match := holdout_parents.get(example.parent_identity)
        ):
            identity.append(
                {"example_id": example.example_id, "holdout_frame_id": match.frame_id}
            )
        group = (example.site_id, example.camera_id, example.sequence_id)
        if any(group) and (match := holdout_groups.get(group)):
            lineage.append(
                {"example_id": example.example_id, "holdout_frame_id": match.frame_id}
            )
        for row in holdout:
            distance = dhash_distance(example.dhash64, row.dhash64)
            frequency_distance = phash_distance(example.phash64, row.phash64)
            if (
                distance <= near_duplicate_distance
                and frequency_distance <= perceptual_hash_distance
            ):
                near.append(
                    {
                        "example_id": example.example_id,
                        "holdout_frame_id": row.frame_id,
                        "dhash_distance": distance,
                        "phash_distance": frequency_distance,
                    }
                )
    result = {
        "frozen_benchmark_semantic_fingerprint": FROZEN_BENCHMARK_SEMANTIC_FINGERPRINT,
        "checked_examples": len(examples),
        "checked_holdout_frames": len(holdout),
        "near_duplicate_distance": near_duplicate_distance,
        "exact_sha256_matches": exact,
        "source_or_parent_identity_matches": identity,
        "site_camera_sequence_matches": lineage,
        "perceptual_hash_distance": perceptual_hash_distance,
        "near_duplicate_matches": near,
        "passed": not (exact or identity or lineage or near),
    }
    return result


def corpus_summary(examples: Sequence[CorpusExample]) -> dict[str, Any]:
    assert_no_group_leakage(examples)
    positives = [example for example in examples if example.is_positive]
    negatives = [example for example in examples if not example.is_positive]
    by_split = Counter(example.split for example in examples)
    sites = Counter(
        f"{example.source_id}:{example.site_id or example.camera_id or 'unknown'}"
        for example in examples
    )
    taxon = Counter(box.taxon for example in positives for box in example.boxes)
    sizes = Counter(example.size_bucket for example in positives)
    negative_kinds = Counter(example.negative_kind for example in negatives)
    domain_roles = Counter(example.domain_role for example in examples)
    augmentation_kinds = Counter(example.augmentation_kind for example in examples)
    taxon_groups = Counter(
        example.taxon_group for example in positives if example.taxon_group
    )
    validation_groups = {
        example.strongest_group for example in examples if example.split == "valid"
    }
    small_positives = sum(
        example.size_bucket in ("very_small", "small") for example in positives
    )
    return {
        "images": len(examples),
        "positive_images": len(positives),
        "negative_images": len(negatives),
        "boxes": sum(len(example.boxes) for example in positives),
        "by_split": dict(sorted(by_split.items())),
        "by_source_site": dict(sorted(sites.items())),
        "taxonomic_distribution": dict(sorted(taxon.items())),
        "primary_size_distribution": {key: sizes.get(key, 0) for key in _SIZE_ORDER},
        "negative_composition": dict(sorted(negative_kinds.items())),
        "strongest_group_count": len({example.strongest_group for example in examples}),
        "validation_group_count": len(validation_groups),
        "by_domain_role": dict(sorted(domain_roles.items())),
        "effective_sampling_mass_by_domain_role": dict(
            sorted(
                {
                    role: round(
                        sum(
                            example.sampling_weight
                            for example in examples
                            if example.domain_role == role
                        ),
                        6,
                    )
                    for role in domain_roles
                }.items()
            )
        ),
        "augmentation_distribution": dict(sorted(augmentation_kinds.items())),
        "taxonomic_group_distribution": dict(sorted(taxon_groups.items())),
        "small_positive_fraction": (
            small_positives / len(positives) if positives else 0.0
        ),
    }


def build_corpus_manifest(
    examples: Sequence[CorpusExample],
    *,
    registry_fingerprint: str,
    contamination: Mapping[str, Any],
    selection_policy: Mapping[str, Any],
) -> dict[str, Any]:
    if len(examples) != 1200:
        raise WildlifeTrainingError("stage1_requires_1200_images")
    summary = corpus_summary(examples)
    if summary["positive_images"] != 800 or summary["negative_images"] != 400:
        raise WildlifeTrainingError("stage1_class_balance_invalid")
    sizes = summary["primary_size_distribution"]
    if sizes["very_small"] < 200 or sizes["small"] < 250:
        raise WildlifeTrainingError("stage1_small_object_quota_unmet")


@dataclass(frozen=True)
class Stage2CorpusRequirements:
    total_min: int = 5_000
    total_max: int = 15_000
    min_positive_images: int = 3_500
    min_negative_images: int = 1_000
    min_small_positive_fraction: float = 0.30
    min_target_domain_fraction: float = 0.90
    min_distinct_groups: int = 100
    min_validation_groups: int = 30
    min_hard_negative_images: int = 1_000

    def __post_init__(self) -> None:
        counts = (
            self.total_min,
            self.total_max,
            self.min_positive_images,
            self.min_negative_images,
            self.min_distinct_groups,
            self.min_validation_groups,
            self.min_hard_negative_images,
        )
        if any(value < 0 for value in counts) or self.total_min > self.total_max:
            raise WildlifeTrainingError("stage2_requirements_invalid")
        if not 0 <= self.min_small_positive_fraction <= 1 or not (
            0 <= self.min_target_domain_fraction <= 1
        ):
            raise WildlifeTrainingError("stage2_requirements_invalid")


def build_stage2_corpus_manifest(
    examples: Sequence[CorpusExample],
    *,
    registry_fingerprint: str,
    contamination: Mapping[str, Any],
    internal_split_contamination: Mapping[str, Any],
    selection_policy: Mapping[str, Any],
    requirements: Stage2CorpusRequirements = Stage2CorpusRequirements(),
) -> dict[str, Any]:
    """Build the governed Stage-2 manifest after all quota/leakage gates pass."""

    if not _SHA256.fullmatch(registry_fingerprint):
        raise WildlifeTrainingError("stage2_registry_fingerprint_invalid")
    summary = corpus_summary(examples)
    if not requirements.total_min <= summary["images"] <= requirements.total_max:
        raise WildlifeTrainingError("stage2_corpus_size_invalid")
    if summary["positive_images"] < requirements.min_positive_images:
        raise WildlifeTrainingError("stage2_positive_quota_unmet")
    if summary["negative_images"] < requirements.min_negative_images:
        raise WildlifeTrainingError("stage2_negative_quota_unmet")
    if summary["small_positive_fraction"] < requirements.min_small_positive_fraction:
        raise WildlifeTrainingError("stage2_small_object_quota_unmet")
    target_count = summary["by_domain_role"].get("target_domain", 0)
    if target_count / summary["images"] < requirements.min_target_domain_fraction:
        raise WildlifeTrainingError("stage2_target_domain_fraction_unmet")
    if summary["strongest_group_count"] < requirements.min_distinct_groups:
        raise WildlifeTrainingError("stage2_source_site_diversity_unmet")
    if summary["validation_group_count"] < requirements.min_validation_groups:
        raise WildlifeTrainingError("stage2_validation_group_diversity_unmet")
    hard_negative_count = sum(
        not example.is_positive and bool(example.negative_kind) for example in examples
    )
    if hard_negative_count < requirements.min_hard_negative_images:
        raise WildlifeTrainingError("stage2_hard_negative_quota_unmet")
    if any(example.is_positive and not example.taxon_group for example in examples):
        raise WildlifeTrainingError("stage2_positive_taxon_group_missing")
    if not contamination.get("passed"):
        raise WildlifeTrainingError("frozen_benchmark_contamination")
    if not internal_split_contamination.get("passed"):
        raise WildlifeTrainingError("internal_train_validation_contamination")
    rows = [
        example.to_dict()
        for example in sorted(examples, key=lambda item: item.example_id)
    ]
    semantic: dict[str, Any] = {
        "schema_version": 2,
        "corpus_id": STAGE2_CORPUS_ID,
        "detector_ontology": ["animal"],
        "taxonomy_policy": (
            "preserve source taxon and governed taxon group as metadata; "
            "train one detector class"
        ),
        "domain_policy": (
            "target-domain examples are canonical; transfer-only examples are "
            "train-only, capped at 0.25 sampling weight, and require ablation"
        ),
        "size_policy": (
            "source-pixel box area: very_small <32^2; small <96^2; "
            "medium <256^2; large otherwise"
        ),
        "registry_fingerprint": registry_fingerprint,
        "selection_policy": dict(selection_policy),
        "requirements": asdict(requirements),
        "examples": rows,
        "summary": summary,
        "hard_negative_images": hard_negative_count,
        "contamination": dict(contamination),
        "internal_split_contamination": dict(internal_split_contamination),
        "creates_product_truth": False,
    }
    semantic["semantic_fingerprint"] = canonical_fingerprint(semantic)
    semantic["split_fingerprint"] = canonical_fingerprint(
        [
            {
                "example_id": row["example_id"],
                "split": row["split"],
                "strongest_group": row["strongest_group"],
                "sha256": row["sha256"],
                "domain_role": row["domain_role"],
                "sampling_weight": row["sampling_weight"],
                "augmentation_kind": row["augmentation_kind"],
            }
            for row in rows
        ]
    )
    return semantic
    if summary["strongest_group_count"] < 8:
        raise WildlifeTrainingError("stage1_source_site_diversity_unmet")
    if not contamination.get("passed"):
        raise WildlifeTrainingError("frozen_benchmark_contamination")
    rows = [
        example.to_dict()
        for example in sorted(examples, key=lambda item: item.example_id)
    ]
    semantic = {
        "schema_version": 1,
        "corpus_id": STAGE1_CORPUS_ID,
        "detector_ontology": ["animal"],
        "taxonomy_policy": "preserve source taxon as metadata; train one detector class",
        "size_policy": "source-pixel box area: very_small <32^2; small <96^2; medium <256^2; large otherwise",
        "registry_fingerprint": registry_fingerprint,
        "selection_policy": dict(selection_policy),
        "examples": rows,
        "summary": summary,
        "contamination": dict(contamination),
        "creates_product_truth": False,
    }
    semantic["semantic_fingerprint"] = canonical_fingerprint(semantic)
    split_projection = [
        {
            "example_id": row["example_id"],
            "split": row["split"],
            "strongest_group": row["strongest_group"],
            "sha256": row["sha256"],
        }
        for row in rows
    ]
    semantic["split_fingerprint"] = canonical_fingerprint(split_projection)
    return semantic


@dataclass(frozen=True)
class ExperimentIdentity:
    experiment_id: str
    corpus_fingerprint: str
    split_fingerprint: str
    model_architecture: str
    model_upstream_id: str
    package_version: str
    package_sha256: str
    pretrained_sha256: str
    resolution: int
    batch_size: int
    grad_accum_steps: int
    optimizer: str
    learning_rate: float
    learning_rate_encoder: float
    scheduler: str
    amp_dtype: str
    seed: int
    augmentation: str

    def __post_init__(self) -> None:
        hashes = (
            self.corpus_fingerprint,
            self.split_fingerprint,
            self.package_sha256,
            self.pretrained_sha256,
        )
        if any(not _SHA256.fullmatch(value) for value in hashes):
            raise WildlifeTrainingError("experiment_hash_invalid")
        if self.resolution <= 0 or self.resolution % 32:
            raise WildlifeTrainingError("experiment_resolution_invalid")
        if self.batch_size <= 0 or self.grad_accum_steps <= 0:
            raise WildlifeTrainingError("experiment_batch_invalid")
        if self.learning_rate <= 0 or self.learning_rate_encoder <= 0:
            raise WildlifeTrainingError("experiment_learning_rate_invalid")

    @property
    def effective_batch_size(self) -> int:
        return self.batch_size * self.grad_accum_steps

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(asdict(self))


@dataclass(frozen=True)
class EvaluationBox:
    box: tuple[float, float, float, float]
    confidence: float | None = None
    taxon: str | None = None
    size_bucket: SizeBucket | None = None

    def __post_init__(self) -> None:
        left, top, right, bottom = self.box
        # Truth boxes normalized as (pixel + pixel) / image_dimension can land
        # a few ULPs past an exact 0/1 boundary purely from float summation
        # (e.g. a box touching the image's right edge); tolerate that with the
        # same 1e-6 slack `PixelBox.normalized_xyxy`/`context_crop_bounds`
        # already use for the identical source-pixel boundary case, without
        # weakening the check against an actually out-of-bounds box.
        tolerance = 1e-6
        if (
            not all(math.isfinite(value) for value in self.box)
            or left < -tolerance
            or top < -tolerance
            or right > 1 + tolerance
            or bottom > 1 + tolerance
            or right <= left
            or bottom <= top
        ):
            raise WildlifeTrainingError("evaluation_box_invalid")


def intersection_over_union(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right, bottom = min(first[2], second[2]), min(first[3], second[3])
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else intersection / union


def _match(
    truth: Sequence[EvaluationBox],
    predictions: Sequence[EvaluationBox],
    iou_threshold: float,
) -> tuple[int, int, int, list[float], set[int]]:
    ordered = sorted(
        enumerate(predictions),
        key=lambda item: -(item[1].confidence or 0.0),
    )
    unmatched = set(range(len(truth)))
    matched_ious: list[float] = []
    matched_truth: set[int] = set()
    false_positives = 0
    for _, prediction in ordered:
        candidates = [
            (intersection_over_union(prediction.box, truth[index].box), index)
            for index in unmatched
        ]
        best_iou, best_index = max(candidates, default=(0.0, -1))
        if best_index >= 0 and best_iou >= iou_threshold:
            unmatched.remove(best_index)
            matched_truth.add(best_index)
            matched_ious.append(best_iou)
        else:
            false_positives += 1
    return (
        len(matched_truth),
        false_positives,
        len(unmatched),
        matched_ious,
        matched_truth,
    )


def evaluate_detections(
    truth_by_frame: Mapping[str, Sequence[EvaluationBox]],
    predictions_by_frame: Mapping[str, Sequence[EvaluationBox]],
    *,
    match_iou: float = 0.5,
) -> dict[str, Any]:
    if not 0 < match_iou <= 1:
        raise WildlifeTrainingError("evaluation_iou_invalid")
    tp = fp = fn = 0
    matched_ious: list[float] = []
    negative_frames = false_on_negative = 0
    recall_numerators: Counter[str] = Counter()
    recall_denominators: Counter[str] = Counter()
    taxon_numerators: Counter[str] = Counter()
    taxon_denominators: Counter[str] = Counter()
    threshold_hits = {0.25: 0, 0.5: 0, 0.75: 0}
    total_truth = 0
    for frame_id in sorted(truth_by_frame):
        truth = list(truth_by_frame[frame_id])
        predictions = list(predictions_by_frame.get(frame_id, ()))
        if not truth:
            negative_frames += 1
            false_on_negative += len(predictions)
        frame_tp, frame_fp, frame_fn, ious, matched = _match(
            truth, predictions, match_iou
        )
        tp += frame_tp
        fp += frame_fp
        fn += frame_fn
        matched_ious.extend(ious)
        total_truth += len(truth)
        for index, item in enumerate(truth):
            bucket = item.size_bucket or "unknown"
            taxon = item.taxon or "unknown"
            recall_denominators[bucket] += 1
            taxon_denominators[taxon] += 1
            if index in matched:
                recall_numerators[bucket] += 1
                taxon_numerators[taxon] += 1
            best = max(
                (
                    intersection_over_union(item.box, prediction.box)
                    for prediction in predictions
                ),
                default=0.0,
            )
            for threshold in threshold_hits:
                threshold_hits[threshold] += int(best >= threshold)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0,
        "mean_localization_iou": (
            sum(matched_ious) / len(matched_ious) if matched_ious else 0.0
        ),
        "recall_at_iou": {
            f"{threshold:.2f}": (hits / total_truth if total_truth else 0.0)
            for threshold, hits in threshold_hits.items()
        },
        "false_detections_per_negative_frame": (
            false_on_negative / negative_frames if negative_frames else 0.0
        ),
        "recall_by_size_bucket": {
            bucket: recall_numerators[bucket] / denominator
            for bucket, denominator in sorted(recall_denominators.items())
        },
        "recall_by_taxon": {
            taxon: taxon_numerators[taxon] / denominator
            for taxon, denominator in sorted(taxon_denominators.items())
        },
        "creates_product_truth": False,
    }
