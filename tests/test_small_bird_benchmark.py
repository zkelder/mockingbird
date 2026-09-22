from mockingbird.detectors.megadetector_adapter import MegaDetectorBox, MegaDetectorProposal
import numpy as np

from mockingbird.detectors.small_bird_benchmark import (
    NormalizedBox,
    OVERLAPPING_ZONE_TILES,
    aspect_preserving_zone_jpeg,
    deduplicate_tiled_proposals,
    evaluation_metrics,
    run_strategy,
    track_sequence_metrics,
    tiled_coordinate_boxes,
)


def test_tiled_boxes_cover_zone_edges_and_remain_bounded() -> None:
    zone = NormalizedBox(0.2, 0.25, 0.8, 0.75)

    tiles = tiled_coordinate_boxes(zone, columns=2, rows=2, overlap=0.2)

    assert len(tiles) == 4
    assert tiles[0].left == zone.left
    assert tiles[0].top == zone.top
    assert tiles[-1].right == zone.right
    assert tiles[-1].bottom == zone.bottom


def test_tiled_deduplication_is_deterministic_and_retains_one_subject() -> None:
    duplicate = MegaDetectorBox(x=0.4, y=0.4, width=0.12, height=0.12)
    proposals = [
        MegaDetectorProposal(label="animal", confidence=0.8, bbox=duplicate),
        MegaDetectorProposal(label="animal", confidence=0.9, bbox=duplicate),
    ]

    merged = deduplicate_tiled_proposals(proposals, iou_threshold=0.5)

    assert merged == [MegaDetectorProposal(label="animal", confidence=0.9, bbox=duplicate)]


def test_metrics_measure_containment_small_subjects_and_no_truth_writes() -> None:
    metrics = evaluation_metrics(
        frames=[
            {
                "id": "small-bird",
                "bird_visible": "yes",
                "in_target_zone": True,
                "full_bird_visible": True,
                "manual_bird_box": [0.4, 0.4, 0.45, 0.46],
                "width": 1920,
                "height": 1440,
            },
            {
                "id": "empty",
                "bird_visible": "no",
                "in_target_zone": True,
                "width": 1920,
                "height": 1440,
            },
        ],
        predictions={
            "small-bird": [
                MegaDetectorProposal(
                    label="animal",
                    confidence=0.7,
                    bbox=MegaDetectorBox(x=0.39, y=0.39, width=0.08, height=0.09),
                )
            ],
            "empty": [],
        },
        latencies_ms={"small-bird": 800, "empty": 750},
    )

    assert metrics["visible_bird_frame_recall"] == 1.0
    assert metrics["false_positive_frames"] == 0
    assert metrics["full_body_containment"] == 1.0
    assert metrics["small_bird"]["recall"] == 1.0
    assert metrics["safety"]["product_writes"] is False



def test_small_bird_denominator_and_containment_include_a_missed_full_body() -> None:
    metrics = evaluation_metrics(
        frames=[
            {
                "id": "missed-small-bird",
                "bird_visible": "yes",
                "in_target_zone": True,
                "full_bird_visible": True,
                "manual_bird_box": [0.4, 0.4, 0.45, 0.46],
                "width": 1920,
                "height": 1440,
            }
        ],
        predictions={"missed-small-bird": []},
        latencies_ms={"missed-small-bird": 700},
    )

    assert metrics["visible_bird_frame_recall"] == 0.0
    assert metrics["full_body_containment"] == 0.0
    assert metrics["small_bird"] == {
        "definition": "manual bird longest side <= 96 source pixels",
        "positive_frames": 1,
        "hits": 0,
        "recall": 0.0,
    }



def test_higher_resolution_zone_input_preserves_aspect_ratio() -> None:
    image = np.zeros((100, 200, 3), dtype=np.uint8)

    image_bytes, size = aspect_preserving_zone_jpeg(
        image,
        NormalizedBox(0.25, 0.25, 0.75, 0.75),
        target_long_edge=300,
    )

    assert image_bytes.startswith(b"\xff\xd8")
    assert size == (300, 150)


def test_tiled_strategy_uses_four_bounded_tiles_and_merges_duplicate_subjects() -> None:
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    calls: list[MegaDetectorBox] = []

    def runner(_image: bytes, coordinate_box: MegaDetectorBox) -> list[MegaDetectorProposal]:
        calls.append(coordinate_box)
        return [
            MegaDetectorProposal(
                label="animal",
                confidence=0.7,
                bbox=MegaDetectorBox(x=0.45, y=0.45, width=0.1, height=0.1),
            )
        ]

    proposals, input_sizes = run_strategy(
        image,
        zone=NormalizedBox(0.2, 0.2, 0.8, 0.8),
        strategy=OVERLAPPING_ZONE_TILES,
        runner=runner,
    )

    assert len(calls) == 4
    assert all(0.0 < box.width <= 1.0 and 0.0 < box.height <= 1.0 for box in calls)
    assert all(max(size) == 1280 for size in input_sizes)
    assert len(proposals) == 1


def test_ordered_short_occlusion_keeps_one_offline_subject_track() -> None:
    proposals = {
        "bird-1": [MegaDetectorProposal("animal", 0.8, MegaDetectorBox(0.4, 0.4, 0.1, 0.1))],
        "bird-2": [],
        "bird-3": [MegaDetectorProposal("animal", 0.8, MegaDetectorBox(0.42, 0.4, 0.1, 0.1))],
    }
    metrics = track_sequence_metrics(
        frames=[
            {"id": "bird-1", "sequence_id": "bird", "sequence_order": 1},
            {"id": "bird-2", "sequence_id": "bird", "sequence_order": 2},
            {"id": "bird-3", "sequence_id": "bird", "sequence_order": 3},
        ],
        predictions=proposals,
    )

    assert metrics["sequence_count"] == 1
    assert metrics["results"] == [
        {
            "sequence_id": "bird",
            "frame_count": 3,
            "track_count": 1,
            "coherent_single_subject": True,
            "max_track_hits": 2,
        }
    ]
