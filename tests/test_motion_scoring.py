import pytest

from mockingbird.motion import (
    MotionFrameScore,
    MotionScore,
    MotionZone,
    extract_motion_candidates,
    score_frame_motion,
    score_zone_motion,
)


def zeros(width: int, height: int) -> list[list[int]]:
    return [[0 for _ in range(width)] for _ in range(height)]


def frame_score(frame_index: int, *scores: MotionScore) -> MotionFrameScore:
    triggered_zone_ids = [score.zone_id for score in scores if score.triggered]
    strongest_score = max(scores, key=lambda score: score.changed_ratio, default=None)
    return MotionFrameScore(
        frame_index=frame_index,
        scores=list(scores),
        triggered_zone_ids=triggered_zone_ids,
        strongest_zone_id=strongest_score.zone_id if strongest_score else None,
        strongest_changed_ratio=strongest_score.changed_ratio if strongest_score else 0.0,
    )


def motion_score(zone_id: str, ratio: float, *, triggered: bool = True) -> MotionScore:
    return MotionScore(
        zone_id=zone_id,
        changed_pixels=int(ratio * 100),
        total_pixels=100,
        changed_ratio=ratio,
        mean_delta=ratio * 255,
        triggered=triggered,
    )


def test_no_motion_returns_zero_changed_pixels_and_no_trigger() -> None:
    zone = MotionZone("feeder", 0.0, 0.0, 1.0, 1.0)

    score = score_zone_motion(zeros(3, 3), zeros(3, 3), zone)

    assert score.changed_pixels == 0
    assert score.total_pixels == 9
    assert score.changed_ratio == 0.0
    assert score.mean_delta == 0.0
    assert score.triggered is False


def test_motion_inside_zone_triggers_that_zone() -> None:
    previous_frame = zeros(4, 4)
    current_frame = zeros(4, 4)
    current_frame[1][1] = 255
    zone = MotionZone("feeder", 0.0, 0.0, 0.5, 0.5)

    score = score_zone_motion(previous_frame, current_frame, zone, min_changed_ratio=0.25)

    assert score.changed_pixels == 1
    assert score.total_pixels == 4
    assert score.changed_ratio == 0.25
    assert score.triggered is True


def test_motion_outside_zone_does_not_trigger_that_zone() -> None:
    previous_frame = zeros(4, 4)
    current_frame = zeros(4, 4)
    current_frame[0][0] = 255
    zone = MotionZone("driveway", 0.5, 0.5, 1.0, 1.0)

    score = score_zone_motion(previous_frame, current_frame, zone)

    assert score.changed_pixels == 0
    assert score.triggered is False


def test_multiple_zones_are_scored_independently() -> None:
    previous_frame = zeros(4, 4)
    current_frame = zeros(4, 4)
    current_frame[0][0] = 255
    current_frame[3][3] = 255
    zones = [
        MotionZone("feeder", 0.0, 0.0, 0.5, 0.5),
        MotionZone("ground", 0.5, 0.5, 1.0, 1.0),
    ]

    frame = score_frame_motion(previous_frame, current_frame, zones, frame_index=7)

    assert frame.frame_index == 7
    assert frame.triggered_zone_ids == ["feeder", "ground"]
    assert {score.zone_id: score.changed_pixels for score in frame.scores} == {
        "feeder": 1,
        "ground": 1,
    }


def test_strongest_zone_is_selected_by_changed_ratio() -> None:
    previous_frame = zeros(4, 4)
    current_frame = zeros(4, 4)
    current_frame[0][0] = 255
    for y in range(2):
        for x in range(2, 4):
            current_frame[y][x] = 255
    zones = [
        MotionZone("feeder", 0.0, 0.0, 0.5, 0.5),
        MotionZone("birdbath", 0.5, 0.0, 1.0, 0.5),
    ]

    frame = score_frame_motion(previous_frame, current_frame, zones, frame_index=1)

    assert frame.strongest_zone_id == "birdbath"
    assert frame.strongest_changed_ratio == 1.0


def test_pixel_delta_threshold_filters_tiny_changes() -> None:
    previous_frame = zeros(2, 2)
    current_frame = [[24, 0], [0, 0]]
    zone = MotionZone("feeder", 0.0, 0.0, 1.0, 1.0)

    score = score_zone_motion(previous_frame, current_frame, zone, pixel_delta_threshold=25.0)

    assert score.changed_pixels == 0
    assert score.mean_delta == 6.0
    assert score.triggered is False


def test_min_changed_ratio_filters_tiny_changed_areas() -> None:
    previous_frame = zeros(5, 5)
    current_frame = zeros(5, 5)
    current_frame[2][2] = 255
    zone = MotionZone("yard", 0.0, 0.0, 1.0, 1.0)

    score = score_zone_motion(previous_frame, current_frame, zone, min_changed_ratio=0.1)

    assert score.changed_pixels == 1
    assert score.changed_ratio == pytest.approx(0.04)
    assert score.triggered is False


def test_edge_zone_maps_to_at_least_one_pixel() -> None:
    previous_frame = zeros(3, 3)
    current_frame = zeros(3, 3)
    current_frame[2][2] = 255
    zone = MotionZone("edge", 0.99, 0.99, 1.0, 1.0)

    score = score_zone_motion(previous_frame, current_frame, zone, min_changed_ratio=1.0)

    assert score.total_pixels == 1
    assert score.changed_pixels == 1
    assert score.triggered is True


def test_invalid_frame_dimensions_raise_value_error() -> None:
    zone = MotionZone("feeder", 0.0, 0.0, 1.0, 1.0)

    with pytest.raises(ValueError, match="dimensions"):
        score_zone_motion([[0, 0]], [[0, 0], [0, 0]], zone)

    with pytest.raises(ValueError, match="rectangular"):
        score_zone_motion([[0], [0, 0]], [[0], [0, 0]], zone)


def test_invalid_pixel_values_raise_value_error() -> None:
    zone = MotionZone("feeder", 0.0, 0.0, 1.0, 1.0)

    with pytest.raises(ValueError, match="numeric"):
        score_zone_motion([[0]], [["bright"]], zone)


def test_invalid_zone_bounds_raise_value_error() -> None:
    with pytest.raises(ValueError, match="left < right"):
        score_zone_motion(
            zeros(2, 2),
            zeros(2, 2),
            MotionZone("bad", 0.5, 0.0, 0.5, 1.0),
        )

    with pytest.raises(ValueError, match="normalized"):
        score_zone_motion(
            zeros(2, 2),
            zeros(2, 2),
            MotionZone("bad", -0.1, 0.0, 1.0, 1.0),
        )


def test_debounce_requires_enough_triggered_frames() -> None:
    frame_scores = [frame_score(0, motion_score("feeder", 0.5))]

    candidates = extract_motion_candidates(frame_scores, min_triggered_frames=2)

    assert candidates == []


def test_max_gap_frames_bridges_a_short_gap() -> None:
    frame_scores = [
        frame_score(0, motion_score("feeder", 0.4)),
        frame_score(1, motion_score("feeder", 0.0, triggered=False)),
        frame_score(2, motion_score("feeder", 0.6)),
    ]

    candidates = extract_motion_candidates(
        frame_scores,
        min_triggered_frames=2,
        max_gap_frames=1,
    )

    assert len(candidates) == 1
    assert candidates[0].zone_id == "feeder"
    assert candidates[0].start_frame_index == 0
    assert candidates[0].end_frame_index == 2
    assert candidates[0].triggered_frame_count == 2


def test_best_frame_index_picks_strongest_frame_in_candidate() -> None:
    frame_scores = [
        frame_score(0, motion_score("feeder", 0.4)),
        frame_score(1, motion_score("feeder", 0.9)),
        frame_score(2, motion_score("feeder", 0.7)),
    ]

    candidates = extract_motion_candidates(frame_scores, min_triggered_frames=2)

    assert len(candidates) == 1
    assert candidates[0].best_frame_index == 1
    assert candidates[0].peak_changed_ratio == 0.9
