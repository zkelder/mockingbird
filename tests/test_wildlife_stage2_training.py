from __future__ import annotations

from dataclasses import replace

import pytest

from mockingbird.training.wildlife import (
    CorpusExample,
    PixelBox,
    Stage2CorpusRequirements,
    WildlifeTrainingError,
    build_stage2_corpus_manifest,
    context_crop_bounds,
    load_stage2_source_registry,
)


def _example(index: int, **changes: object) -> CorpusExample:
    values: dict[str, object] = {
        "example_id": f"example-{index}",
        "source_id": "oregon-critters-20260304",
        "source_version": "2026.03.04",
        "source_identity": f"oregon:image-{index}",
        "parent_identity": f"oregon:sequence-{index}",
        "image": f"train/example-{index}.jpg",
        "source_url": f"https://example.invalid/example-{index}.jpg",
        "source_license": "CDLA-Permissive-2.0",
        "geography": "Western Oregon, United States",
        "width": 640,
        "height": 480,
        "split": "train",
        "site_id": f"site-{index}",
        "camera_id": f"camera-{index}",
        "sequence_id": f"sequence-{index}",
        "captured_at": "2026-01-01T00:00:00Z",
        "truth_authority": "public_human_bbox",
        "boxes": (PixelBox(20, 20, 31, 31, "bird"),),
        "sha256": f"{index:064x}",
        "dhash64": f"{index:016x}",
        "phash64": f"{index + 20:016x}",
        "negative_kind": None,
        "domain_role": "target_domain",
        "sampling_weight": 1.0,
        "taxon_group": "bird",
        "augmentation_kind": "full_scene",
    }
    values.update(changes)
    return CorpusExample(**values)  # type: ignore[arg-type]


def _requirements() -> Stage2CorpusRequirements:
    return Stage2CorpusRequirements(
        total_min=4,
        total_max=8,
        min_positive_images=2,
        min_negative_images=2,
        min_small_positive_fraction=0.5,
        min_target_domain_fraction=0.75,
        min_distinct_groups=4,
        min_validation_groups=2,
        min_hard_negative_images=2,
    )


def test_stage2_registry_records_accept_reject_and_ablation_decisions() -> None:
    registry = load_stage2_source_registry()
    by_id = {item["source_id"]: item for item in registry["sources"]}

    assert by_id["oregon-critters-20260304"]["status"] == "accepted"
    assert by_id["channel-islands-camera-traps-2020"]["status"] == "accepted"
    assert by_id["ena24-detection-public-2016"]["status"] == "accepted"
    assert by_id["nacti-human-corrected-boxes-20230920"]["status"] == "accepted"
    assert by_id["missouri-camera-traps-1.21"]["status"] == "rejected"
    assert by_id["coco-2017-target-animal-transfer"]["domain_role"] == "transfer_only"
    assert by_id["coco-2017-target-animal-transfer"]["max_sampling_weight"] == 0.25


def test_human_reviewed_empty_is_training_truth_but_agent_diagnostic_is_not() -> None:
    reviewed = _example(
        1,
        boxes=(),
        truth_authority="human_reviewed_empty",
        negative_kind="local_static_clutter",
        taxon_group=None,
    )
    assert reviewed.is_positive is False

    with pytest.raises(WildlifeTrainingError, match="non_human_training_authority"):
        replace(reviewed, truth_authority="agent_diagnostic")  # type: ignore[arg-type]


def test_transfer_only_examples_are_train_only_and_weight_capped() -> None:
    transfer = _example(
        1,
        source_id="coco-2017-target-animal-transfer",
        domain_role="transfer_only",
        sampling_weight=0.25,
    )
    assert transfer.sampling_weight == 0.25

    with pytest.raises(WildlifeTrainingError, match="transfer_only_weight_exceeds_cap"):
        replace(transfer, sampling_weight=0.251)
    with pytest.raises(WildlifeTrainingError, match="transfer_only_validation_prohibited"):
        replace(transfer, split="valid")


def test_context_crop_preserves_context_and_rebases_boxes() -> None:
    bounds, boxes = context_crop_bounds(
        image_width=1000,
        image_height=800,
        boxes=(PixelBox(460, 360, 40, 30, "bird"),),
        context_scale=5.0,
        minimum_side=200,
    )

    assert bounds == (380, 275, 580, 475)
    assert boxes == (PixelBox(80, 85, 40, 30, "bird"),)


def test_stage2_manifest_binds_domain_mix_small_quota_and_grouped_validation() -> None:
    examples = (
        _example(1),
        _example(2, split="valid", image="valid/example-2.jpg"),
        _example(
            3,
            boxes=(),
            truth_authority="public_curated_empty",
            negative_kind="camera_trap_empty_scene",
            taxon_group=None,
        ),
        _example(
            4,
            split="valid",
            image="valid/example-4.jpg",
            boxes=(),
            truth_authority="public_curated_empty",
            negative_kind="camera_trap_empty_scene",
            taxon_group=None,
        ),
    )

    manifest = build_stage2_corpus_manifest(
        examples,
        registry_fingerprint="a" * 64,
        contamination={"passed": True},
        internal_split_contamination={"passed": True},
        selection_policy={"seed": 260812},
        requirements=_requirements(),
    )

    assert manifest["corpus_id"] == "north-american-backyard-wildlife-stage2-v0.2"
    assert manifest["summary"]["by_domain_role"] == {"target_domain": 4}
    assert manifest["summary"]["validation_group_count"] == 2
    assert manifest["summary"]["small_positive_fraction"] == 1.0
    assert len(manifest["semantic_fingerprint"]) == 64


def test_stage2_manifest_fails_closed_on_weak_domain_or_leakage() -> None:
    examples = [
        _example(1),
        _example(2, split="valid", image="valid/example-2.jpg"),
        _example(
            3,
            boxes=(),
            truth_authority="public_curated_empty",
            negative_kind="camera_trap_empty_scene",
            taxon_group=None,
        ),
        _example(
            4,
            split="valid",
            image="valid/example-4.jpg",
            boxes=(),
            truth_authority="public_curated_empty",
            negative_kind="camera_trap_empty_scene",
            taxon_group=None,
        ),
    ]
    with pytest.raises(WildlifeTrainingError, match="internal_train_validation_contamination"):
        build_stage2_corpus_manifest(
            examples,
            registry_fingerprint="a" * 64,
            contamination={"passed": True},
            internal_split_contamination={"passed": False},
            selection_policy={},
            requirements=_requirements(),
        )

    weak_domain = [
        replace(item, domain_role="transfer_only", sampling_weight=0.25, split="train")
        for item in examples
    ]
    with pytest.raises(WildlifeTrainingError, match="stage2_target_domain_fraction_unmet"):
        build_stage2_corpus_manifest(
            weak_domain,
            registry_fingerprint="a" * 64,
            contamination={"passed": True},
            internal_split_contamination={"passed": True},
            selection_policy={},
            requirements=_requirements(),
        )
