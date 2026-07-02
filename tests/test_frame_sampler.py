from pathlib import Path

import pytest

from mockingbird.api.schemas import MotionEvidenceStatus
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.sampler import (
    SamplerConfig,
    SamplerContext,
    SamplerZone,
    create_motion_evidence_from_sampler_result,
    evaluate_sampled_frame_sequence,
)

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
GROUND_ZONE_ID = "zone-ground"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")


def zeros(width: int = 4, height: int = 4) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def frame_with(pixels: list[tuple[int, int]]) -> list[list[int]]:
    frame = zeros()
    for y, x in pixels:
        frame[y][x] = 255
    return frame


def feeder_zone() -> SamplerZone:
    return SamplerZone(
        zone_id=FEEDER_ZONE_ID,
        left=0.0,
        top=0.0,
        right=0.5,
        bottom=0.5,
    )


def ground_zone() -> SamplerZone:
    return SamplerZone(
        zone_id=GROUND_ZONE_ID,
        left=0.5,
        top=0.5,
        right=1.0,
        bottom=1.0,
    )


def motion_frames() -> list[list[list[int]]]:
    return [
        zeros(),
        frame_with([(0, 0)]),
        frame_with([(0, 0), (0, 1), (1, 0), (1, 1)]),
    ]


def motion_config(
    *,
    pixel_delta_threshold: float = 25.0,
    min_changed_ratio: float = 0.25,
    min_triggered_frames: int = 2,
    max_gap_frames: int = 1,
    frame_index_start: int = 0,
    create_motion_evidence: bool = False,
) -> SamplerConfig:
    return SamplerConfig(
        pixel_delta_threshold=pixel_delta_threshold,
        min_changed_ratio=min_changed_ratio,
        min_triggered_frames=min_triggered_frames,
        max_gap_frames=max_gap_frames,
        frame_index_start=frame_index_start,
        create_motion_evidence=create_motion_evidence,
    )


def truth_counts(repository: ProductRepository) -> dict[str, int]:
    coverage = repository.dataset_coverage_summary()
    return {
        "events": len(repository.list_events()),
        "visits": len(repository.list_visits()),
        "review_labels": len(repository.list_review_labels()),
        "exports": len(repository.list_dataset_exports()),
        "export_ready_count": coverage.export_ready_count,
        "reviewed_record_count": coverage.reviewed_record_count,
    }


def test_sampler_returns_no_candidates_for_still_supplied_frames() -> None:
    result = evaluate_sampled_frame_sequence(
        [zeros(), zeros(), zeros()],
        [feeder_zone()],
        motion_config(),
    )

    assert [score.frame_index for score in result.frame_scores] == [1, 2]
    assert result.candidates == []
    assert result.created_evidence == []
    assert result.warnings == []
    assert all(score.triggered_zone_ids == [] for score in result.frame_scores)


def test_sampler_returns_candidate_with_best_frame_from_supplied_planes() -> None:
    result = evaluate_sampled_frame_sequence(
        motion_frames(),
        [feeder_zone()],
        motion_config(frame_index_start=10),
    )

    assert result.candidates[0].zone_id == FEEDER_ZONE_ID
    assert result.candidates[0].start_frame_index == 11
    assert result.candidates[0].end_frame_index == 12
    assert result.candidates[0].best_frame_index == 12
    assert result.candidates[0].peak_changed_ratio == 0.75
    assert result.candidates[0].triggered_frame_count == 2


def test_sampler_keeps_zone_candidates_independent() -> None:
    frames = [
        zeros(),
        frame_with([(0, 0), (3, 3)]),
        frame_with(
            [
                (0, 0),
                (0, 1),
                (1, 0),
                (1, 1),
                (2, 2),
                (2, 3),
                (3, 2),
                (3, 3),
            ]
        ),
    ]

    result = evaluate_sampled_frame_sequence(
        frames,
        [feeder_zone(), ground_zone()],
        motion_config(),
    )

    assert [candidate.zone_id for candidate in result.candidates] == [
        FEEDER_ZONE_ID,
        GROUND_ZONE_ID,
    ]


def test_sampler_thresholds_filter_candidate_noise() -> None:
    result = evaluate_sampled_frame_sequence(
        motion_frames(),
        [feeder_zone()],
        motion_config(min_changed_ratio=0.8),
    )

    assert result.candidates == []


def test_sampler_rejects_short_sequences() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        evaluate_sampled_frame_sequence([zeros()], [feeder_zone()], motion_config())


def test_sampler_rejects_empty_zones() -> None:
    with pytest.raises(ValueError, match="at least 1 zone"):
        evaluate_sampled_frame_sequence([zeros(), zeros()], [], motion_config())


def test_sampler_rejects_mismatched_frame_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        evaluate_sampled_frame_sequence(
            [[[0, 0]], [[0, 0], [0, 0]]],
            [feeder_zone()],
            motion_config(),
        )


def test_sampler_does_not_create_evidence_when_disabled(
    repository: ProductRepository,
) -> None:
    result = evaluate_sampled_frame_sequence(
        motion_frames(),
        [feeder_zone()],
        motion_config(create_motion_evidence=False),
    )

    before_count = len(repository.list_motion_evidence())
    created = create_motion_evidence_from_sampler_result(
        repository,
        result,
        SamplerContext(source_id=SOURCE_ID, stream_id=STREAM_ID),
        motion_config(create_motion_evidence=False),
    )

    assert created == []
    assert len(repository.list_motion_evidence()) == before_count


def test_sampler_creates_pending_motion_evidence_without_truth(
    repository: ProductRepository,
) -> None:
    result = evaluate_sampled_frame_sequence(
        motion_frames(),
        [feeder_zone()],
        motion_config(create_motion_evidence=True),
    )
    before_truth = truth_counts(repository)
    before_evidence_count = len(repository.list_motion_evidence())

    created = create_motion_evidence_from_sampler_result(
        repository,
        result,
        SamplerContext(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            notes="Sampler-created feeder motion evidence.",
        ),
        motion_config(create_motion_evidence=True),
    )

    assert len(created) == 1
    evidence = created[0]
    assert evidence.status == MotionEvidenceStatus.pending
    assert evidence.source_id == SOURCE_ID
    assert evidence.stream_id == STREAM_ID
    assert evidence.zone_id == FEEDER_ZONE_ID
    assert evidence.start_frame_index == 1
    assert evidence.end_frame_index == 2
    assert evidence.best_frame_index == 2
    assert evidence.peak_changed_ratio == 0.75
    assert evidence.triggered_frame_count == 2
    assert evidence.scoring_config == {
        "source": "sampler",
        "pixel_delta_threshold": 25.0,
        "min_changed_ratio": 0.25,
        "min_triggered_frames": 2,
        "max_gap_frames": 1,
        "frame_index_start": 0,
    }
    assert evidence.snapshot_media_asset_id is None
    assert len(repository.list_motion_evidence()) == before_evidence_count + 1
    assert truth_counts(repository) == before_truth
