"""Acquisition-effort accounting for research/conservation reporting (see
"Effort accounting -- critical" in the governing milestone brief and
docs/research-conservation-export-contract.md "Effort accounting").

Distinguishes LIVE MONITORING EFFORT -- continuous-observation coverage,
already durably tracked by `MonitoringExposureIntervalModel` and reused here
via `mockingbird.analytics.place_activity_report.CoverageSummary` (never
re-derived; see that module's own `compute_coverage_summary`) -- from
OFFLINE / RECORDED ACQUISITION EFFORT: bounded, per-file capture
opportunities that must never imply continuous-site monitoring.

This module deliberately adds no new persisted ledger. Every input fact it
aggregates already exists durably: `RecordedMediaAnalysisRunModel` (schema
41, one row per completed offline analysis attempt) for recorded video, and
plain `MediaAssetModel.captured_at`/`stream_id` for a still image imported
through the existing folder-import path. See docs/offline-recorded-media-
observation-contract.md "Coverage / effort," which named a cross-run
aggregate as the one deferred piece this module now closes -- without
changing what either source already measures.

## Effort shapes (never blended into one "coverage" number)

- Recorded video: analyzed duration is known only when the source file's own
  duration was known (`RecordedMediaAnalysisRunModel.source_duration_
  seconds`); an unknown-duration clip is counted, honestly, as its own
  bucket rather than a fabricated zero.
- Still image: one capture opportunity, never an implied duration.
- Camera-trap batch: this module never infers deployment uptime from gaps
  between imported files -- it reports discrete counts only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class RecordedVideoAcquisitionFact:
    """One distinct recorded-video MediaAsset's most recent *completed*
    offline analysis attempt. Callers must dedupe to at most one fact per
    `media_asset_id` (its latest completed `RecordedMediaAnalysisRunModel`
    row) before calling `compute_offline_acquisition_effort` -- this module
    trusts that and does not dedupe itself, so a caller that passes every
    historical reprocessing attempt would silently inflate the count."""

    media_asset_id: str
    stream_id: str
    source_duration_seconds: float | None
    frames_analyzed: int
    completed_at: datetime


@dataclass(frozen=True)
class StillImageAcquisitionFact:
    """One offline-imported still image: one capture opportunity, no implied
    duration (see the module docstring's "Still image" rule)."""

    media_asset_id: str
    stream_id: str
    captured_at: datetime | None


@dataclass(frozen=True)
class OfflineAcquisitionEffort:
    """Bounded, honest offline/recorded acquisition-effort summary for a
    reporting period. Never a duration/coverage claim -- see module
    docstring. `recorded_video_analyzed_seconds` sums only the videos whose
    duration was actually known; `recorded_video_unknown_duration_count`
    discloses the rest rather than silently omitting them."""

    recorded_video_count: int
    recorded_video_analyzed_seconds: float
    recorded_video_unknown_duration_count: int
    still_image_count: int
    distinct_streams: int

    @property
    def has_any_offline_acquisition(self) -> bool:
        return self.recorded_video_count > 0 or self.still_image_count > 0


def compute_offline_acquisition_effort(
    *,
    recorded_videos: Iterable[RecordedVideoAcquisitionFact] = (),
    still_images: Iterable[StillImageAcquisitionFact] = (),
) -> OfflineAcquisitionEffort:
    """Aggregate already-resolved offline-acquisition facts into one bounded
    summary. Pure: never queries anything, never infers a duration or
    deployment span that was not already directly known."""

    videos = list(recorded_videos)
    stills = list(still_images)
    known_durations = [
        video.source_duration_seconds
        for video in videos
        if video.source_duration_seconds is not None
    ]
    streams = {video.stream_id for video in videos} | {image.stream_id for image in stills}

    return OfflineAcquisitionEffort(
        recorded_video_count=len(videos),
        recorded_video_analyzed_seconds=sum(known_durations),
        recorded_video_unknown_duration_count=len(videos) - len(known_durations),
        still_image_count=len(stills),
        distinct_streams=len(streams),
    )
