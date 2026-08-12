from __future__ import annotations

from pathlib import Path

import pytest

from mockingbird.training.wildlife import (
    CorpusExample,
    EvaluationBox,
    ExperimentIdentity,
    HoldoutRecord,
    PixelBox,
    WildlifeTrainingError,
    assert_no_group_leakage,
    contamination_report,
    evaluate_detections,
    load_source_registry,
    require_materialization_source,
    source_pixel_size_bucket,
)


def _example(**changes: object) -> CorpusExample:
    values: dict[str, object] = {
        "example_id": "example-1",
        "source_id": "caltech-camera-traps-20200316",
        "source_version": "20200316",
        "source_identity": "cct:image-1",
        "parent_identity": "cct:sequence-1",
        "image": "train/example-1.jpg",
        "source_url": "https://example.invalid/example-1.jpg",
        "source_license": "CDLA-Permissive-2.0",
        "geography": "Southwestern United States",
        "width": 100,
        "height": 100,
        "split": "train",
        "site_id": "site-1",
        "camera_id": "camera-1",
        "sequence_id": "sequence-1",
        "captured_at": "2026-01-01T00:00:00Z",
        "truth_authority": "public_human_bbox",
        "boxes": (PixelBox(10, 10, 20, 20, "bird"),),
        "sha256": "a" * 64,
        "dhash64": "0000000000000000",
        "phash64": "0000000000000000",
        "negative_kind": None,
    }
    values.update(changes)
    return CorpusExample(**values)  # type: ignore[arg-type]


def test_registry_is_29_source_fail_closed_record() -> None:
    registry = load_source_registry()

    assert len(registry["sources"]) == 29
    assert len(registry["fingerprint"]) == 64
    assert (
        require_materialization_source(registry, "caltech-camera-traps-20200316")[
            "license"
        ]
        == "CDLA-Permissive-2.0"
    )
    assert (
        require_materialization_source(registry, "coco-2017-permissive-animal-subset")[
            "status"
        ]
        == "accepted_with_per_image_license_filter"
    )
    with pytest.raises(
        WildlifeTrainingError, match="source_not_materialization_eligible"
    ):
        require_materialization_source(registry, "nabirds-v1")


@pytest.mark.parametrize(
    ("width", "height", "expected"),
    [
        (31, 32, "very_small"),
        (32, 32, "small"),
        (95, 96, "small"),
        (96, 96, "medium"),
        (255, 256, "medium"),
        (256, 256, "large"),
    ],
)
def test_size_buckets_use_fixed_source_pixel_area(
    width: float, height: float, expected: str
) -> None:
    assert source_pixel_size_bucket(width, height) == expected


def test_box_normalization_rejects_out_of_source_geometry() -> None:
    assert PixelBox(10, 20, 30, 40, "bird").normalized_xyxy(100, 200) == (
        0.1,
        0.1,
        0.4,
        0.3,
    )
    with pytest.raises(WildlifeTrainingError, match="box_outside_source"):
        PixelBox(90, 0, 20, 10, "bird").normalized_xyxy(100, 100)


def test_agent_or_model_localization_cannot_be_training_truth() -> None:
    with pytest.raises(WildlifeTrainingError, match="non_human_training_authority"):
        _example(truth_authority="agent_diagnostic")
    with pytest.raises(
        WildlifeTrainingError, match="positive_example_requires_human_boxes"
    ):
        _example(boxes=(), truth_authority="public_human_bbox")


def test_negative_truth_requires_curated_empty_authority_and_composition() -> None:
    negative = _example(
        boxes=(),
        truth_authority="public_curated_empty",
        negative_kind="camera_trap_empty_scene",
    )
    assert negative.is_positive is False
    with pytest.raises(
        WildlifeTrainingError, match="negative_example_requires_composition"
    ):
        _example(boxes=(), truth_authority="public_curated_empty")


def test_strongest_sequence_group_cannot_cross_split() -> None:
    train = _example()
    valid = _example(
        example_id="example-2",
        source_identity="cct:image-2",
        split="valid",
    )
    with pytest.raises(WildlifeTrainingError, match="strongest_group_split_leakage"):
        assert_no_group_leakage((train, valid))


def test_contamination_checks_exact_identity_lineage_and_near_duplicate() -> None:
    example = _example()
    holdout = HoldoutRecord(
        frame_id="holdout-1",
        sha256="a" * 64,
        dhash64="0000000000000001",
        phash64="0000000000000001",
        source_identity="cct:image-1",
        parent_identity="cct:sequence-1",
        site_id="site-1",
        camera_id="camera-1",
        sequence_id="sequence-1",
    )

    report = contamination_report((example,), (holdout,))

    assert report["passed"] is False
    assert report["exact_sha256_matches"]
    assert report["source_or_parent_identity_matches"]
    assert report["site_camera_sequence_matches"]
    assert report["near_duplicate_matches"][0]["dhash_distance"] == 1
    assert report["near_duplicate_matches"][0]["phash_distance"] == 1


def test_dhash_collision_alone_does_not_fail_contamination() -> None:
    report = contamination_report(
        (_example(),),
        (
            HoldoutRecord(
                "holdout",
                "b" * 64,
                "0000000000000001",
                "ffffffffffffffff",
                "other",
                None,
                "other-site",
                "other-camera",
                "other-sequence",
            ),
        ),
    )
    assert report["passed"] is True


def test_unrelated_materialized_examples_pass_contamination() -> None:
    report = contamination_report(
        (_example(),),
        (
            HoldoutRecord(
                "holdout",
                "b" * 64,
                "ffffffffffffffff",
                "ffffffffffffffff",
                "other",
                None,
                "other-site",
                "other-camera",
                "other-sequence",
            ),
        ),
    )
    assert report["passed"] is True


def test_experiment_identity_binds_corpus_runtime_weights_and_effective_batch() -> None:
    experiment = ExperimentIdentity(
        experiment_id="rfdetr-stage1-proof",
        corpus_fingerprint="a" * 64,
        split_fingerprint="b" * 64,
        model_architecture="RF-DETR Small",
        model_upstream_id="rf-detr-small.pth",
        package_version="1.8.3",
        package_sha256="c" * 64,
        pretrained_sha256="d" * 64,
        resolution=640,
        batch_size=1,
        grad_accum_steps=8,
        optimizer="AdamW",
        learning_rate=0.0001,
        learning_rate_encoder=0.00015,
        scheduler="step",
        amp_dtype="float16",
        seed=260811,
        augmentation="RF-DETR CPU default; multi_scale disabled",
    )

    assert experiment.effective_batch_size == 8
    assert len(experiment.fingerprint) == 64


def test_evaluation_reports_localization_sizes_taxa_and_hard_negatives() -> None:
    truth = {
        "positive": (
            EvaluationBox((0.1, 0.1, 0.2, 0.2), taxon="bird", size_bucket="very_small"),
            EvaluationBox((0.6, 0.6, 0.9, 0.9), taxon="raccoon", size_bucket="large"),
        ),
        "negative": (),
    }
    predictions = {
        "positive": (
            EvaluationBox((0.1, 0.1, 0.2, 0.2), confidence=0.9),
            EvaluationBox((0.0, 0.7, 0.1, 0.8), confidence=0.4),
        ),
        "negative": (EvaluationBox((0.2, 0.2, 0.3, 0.3), confidence=0.6),),
    }

    metrics = evaluate_detections(truth, predictions)

    assert metrics["precision"] == pytest.approx(1 / 3)
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == pytest.approx(0.4)
    assert metrics["mean_localization_iou"] == 1.0
    assert metrics["false_detections_per_negative_frame"] == 1.0
    assert metrics["recall_by_size_bucket"] == {"large": 0.0, "very_small": 1.0}
    assert metrics["recall_by_taxon"] == {"bird": 1.0, "raccoon": 0.0}
    assert metrics["creates_product_truth"] is False


def test_evaluation_box_tolerates_float_boundary_noise_but_rejects_real_overflow() -> None:
    """A truth box built as `(pixel + pixel) / image_dimension` can land a few
    ULPs past an exact 0/1 boundary from float summation alone -- this is
    exactly what a real Stage-2 validation frame produced (a box touching an
    image's right edge normalized to `1.0000000000000018`). That must not
    fail closed the same way an actually out-of-bounds box should."""

    boundary_noise = 5e-15
    accepted = EvaluationBox(
        (-boundary_noise, 0.1, 1 + boundary_noise, 1 + boundary_noise)
    )
    assert accepted.box == (-boundary_noise, 0.1, 1 + boundary_noise, 1 + boundary_noise)

    for box in (
        (1.01, 0.1, 1.5, 0.5),  # right well past 1
        (0.1, -0.02, 0.5, 0.5),  # top well past 0
        (0.1, 0.1, 0.5, 1.5),  # bottom well past 1
        (-0.02, 0.1, 0.5, 0.5),  # left well past 0
    ):
        with pytest.raises(WildlifeTrainingError, match="evaluation_box_invalid"):
            EvaluationBox(box)


def test_registry_file_stays_next_to_module() -> None:
    assert (
        Path(__file__)
        .parents[1]
        .joinpath("src/mockingbird/training/wildlife_source_registry_v0_1.json")
        .is_file()
    )
