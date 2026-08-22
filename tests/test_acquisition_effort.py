"""Pure-module tests for `mockingbird.research.acquisition_effort` (see
docs/research-conservation-export-contract.md "Effort accounting").
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.research.acquisition_effort import (
    RecordedVideoAcquisitionFact,
    StillImageAcquisitionFact,
    compute_offline_acquisition_effort,
)

_NOW = datetime(2026, 8, 22, tzinfo=UTC)


def test_no_offline_acquisition_reports_honest_zeros():
    effort = compute_offline_acquisition_effort()
    assert effort.recorded_video_count == 0
    assert effort.still_image_count == 0
    assert effort.has_any_offline_acquisition is False


def test_recorded_video_with_known_duration_is_summed():
    effort = compute_offline_acquisition_effort(
        recorded_videos=[
            RecordedVideoAcquisitionFact("media-1", "stream-1", 120.0, 240, _NOW),
            RecordedVideoAcquisitionFact("media-2", "stream-1", 60.0, 120, _NOW),
        ],
    )
    assert effort.recorded_video_count == 2
    assert effort.recorded_video_analyzed_seconds == 180.0
    assert effort.recorded_video_unknown_duration_count == 0
    assert effort.has_any_offline_acquisition is True


def test_recorded_video_with_unknown_duration_is_disclosed_not_fabricated_as_zero():
    effort = compute_offline_acquisition_effort(
        recorded_videos=[
            RecordedVideoAcquisitionFact("media-1", "stream-1", None, 10, _NOW),
            RecordedVideoAcquisitionFact("media-2", "stream-1", 30.0, 60, _NOW),
        ],
    )
    assert effort.recorded_video_count == 2
    # Only the known-duration video contributes to the analyzed-seconds sum.
    assert effort.recorded_video_analyzed_seconds == 30.0
    assert effort.recorded_video_unknown_duration_count == 1


def test_still_image_never_implies_a_duration():
    effort = compute_offline_acquisition_effort(
        still_images=[
            StillImageAcquisitionFact("media-3", "stream-2", _NOW),
            StillImageAcquisitionFact("media-4", "stream-2", None),
        ],
    )
    assert effort.still_image_count == 2
    assert effort.recorded_video_count == 0
    assert effort.recorded_video_analyzed_seconds == 0.0


def test_distinct_streams_counts_unique_streams_across_both_kinds():
    effort = compute_offline_acquisition_effort(
        recorded_videos=[RecordedVideoAcquisitionFact("media-1", "stream-1", 10.0, 5, _NOW)],
        still_images=[
            StillImageAcquisitionFact("media-2", "stream-1", _NOW),
            StillImageAcquisitionFact("media-3", "stream-2", _NOW),
        ],
    )
    assert effort.distinct_streams == 2


def test_effort_never_implies_deployment_uptime_from_file_gaps():
    # Two stills captured weeks apart must never be interpreted as a span of
    # deployment coverage between them -- only two discrete opportunities.
    far_apart = [
        StillImageAcquisitionFact("media-1", "stream-1", datetime(2026, 1, 1, tzinfo=UTC)),
        StillImageAcquisitionFact("media-2", "stream-1", datetime(2026, 6, 1, tzinfo=UTC)),
    ]
    effort = compute_offline_acquisition_effort(still_images=far_apart)
    assert effort.still_image_count == 2
    # No duration/span field exists on OfflineAcquisitionEffort for stills at
    # all -- the dataclass has no such attribute to assert against, which is
    # itself the guarantee: there is no field this could pollute.
    assert not hasattr(effort, "still_image_span_seconds")
