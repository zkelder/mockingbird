"""Bounded acoustic-clip analysis orchestrator -- Acoustic / BirdNET
Observation Foundation v1. See docs/acoustic-birdnet-observation-
foundation-v1-contract.md for the full policy; this module is the
mechanics tying `mockingbird.species.birdnet_adapter` (inference) to
`mockingbird.repository.product_repository` (persistence).

## Why this is not `offline_ingest.py` with audio swapped in

`offline_ingest.py` reuses the *existing* Observation Engine seam
(`FrameDrivenObservationProvider.replay_frames` -> tracker -> assembler ->
`CandidateVisitAuthorityAdapter.attempt_candidate`) because recorded video
genuinely needs everything that seam provides: spatial detection, temporal
tracking across frames, multi-subject disambiguation. BirdNET provides none
of the inputs that seam requires (no bounding box, no frame-to-frame
subject identity) and needs none of what it solves (there is no moving
subject to track across an audio clip) -- forcing acoustic detections
through it would mean fabricating geometry that was never observed, exactly
the "pretending there was visual evidence" trap this milestone's own
architecture question warns against.

This module is instead a small, independently-written mirror of
`offline_ingest.py`'s *orchestration shape* (idempotency pre-check ->
bounded decode -> bounded analysis -> bounded admission loop -> durable run
bookkeeping), calling into `ProductRepository.create_acoustic_candidate_
visit` -- the audio-native sibling of `create_candidate_visit_from_
proposal` -- rather than into the visual admission stack. Nothing here
duplicates detection, tracking, or Visit-assembly logic; there is none to
duplicate on this path.

## Same-clip species merge

BirdNET reports one detection per fixed ~3s analysis window. Multiple
consecutive/overlapping windows of the *same* species within one bounded
clip are merged into one candidate Visit (`window_start_ms`/`window_end_ms`
spanning the earliest start to the latest end, `confidence` the peak across
the merged windows) -- never one Visit per raw window, which would
fragment one continuous vocalization into a spam of near-duplicate Review
Queue items exactly the way this product's own Visit Continuity work
(2026-08-17) already fixed for the visual path. Two *different* species
detected in the same clip correctly become two independent candidate
Visits (each its own Event -- no artificial Event-sharing for simultaneous
distinct species is attempted here; see "Known bounded gaps").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import tempfile

from mockingbird.diagnostics.structured_log import log_error_event
from mockingbird.observation.audio_capture import (
    AudioDecodeError,
    decode_audio_to_canonical_wav,
)
from mockingbird.repository.product_repository import (
    AcousticDetectionFacts,
    ProductRepository,
)
from mockingbird.source_providers import media_provenance
from mockingbird.species.birdnet_adapter import (
    BirdNetAdapterConfig,
    BirdNetConfigurationError,
    BirdNetDetection,
    run_birdnet_on_clip,
)

#: Identifies which BirdNET model/config produced a run -- the audio analog
#: of `offline_ingest.DEFAULT_PIPELINE_VERSION`. Bump only on a genuine
#: model/config change that should invalidate prior idempotency, never for
#: an unrelated code change.
DEFAULT_PIPELINE_VERSION = "birdnet-analyzer-global-6k-v2.4-v1"

AUDIO_MEDIA_TYPE = "audio"

#: Same honest "not a real timestamp" anchor `offline_ingest.EPOCH_ANCHOR`
#: uses, deliberately reused rather than a second anchor -- see "Timestamp
#: representation" in docs/acoustic-birdnet-observation-foundation-v1-
#: contract.md: reusing the identical anchor is what lets a future
#: audiovisual-fusion milestone join a video frame and an audio window on
#: one timeline without a translation layer.
EPOCH_ANCHOR = datetime(1970, 1, 1, tzinfo=UTC)


class AcousticIngestError(ValueError):
    """Stable, bounded orchestration-failure code -- mirrors
    `offline_ingest.OfflineIngestError`'s identical convention."""


@dataclass(frozen=True)
class AcousticIngestResult:
    """The bounded, complete outcome of one acoustic analysis attempt."""

    run_id: str
    status: str  # "completed" | "failed" | "already_processed" | "in_progress"
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    min_confidence: float
    windows_analyzed: int = 0
    detections_above_threshold: int = 0
    species_suggestions_created: int = 0
    events_created: int = 0
    visits_created: int = 0
    visit_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    source_duration_seconds: float | None = None
    capture_time_known: bool = False
    error_code: str | None = None
    error_message: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"


def _merge_same_species_detections(
    detections: tuple[BirdNetDetection, ...],
) -> list[BirdNetDetection]:
    """Merge consecutive/overlapping same-species raw BirdNET windows into
    one detection per species per clip -- see the module docstring's
    "Same-clip species merge". Deterministic: species groups are emitted in
    first-seen order."""

    grouped: dict[str, list[BirdNetDetection]] = {}
    order: list[str] = []
    for detection in detections:
        if detection.common_name not in grouped:
            grouped[detection.common_name] = []
            order.append(detection.common_name)
        grouped[detection.common_name].append(detection)

    merged: list[BirdNetDetection] = []
    for common_name in order:
        group = grouped[common_name]
        merged.append(
            BirdNetDetection(
                common_name=common_name,
                scientific_name=group[0].scientific_name,
                confidence=max(item.confidence for item in group),
                start_ms=min(item.start_ms for item in group),
                end_ms=max(item.end_ms for item in group),
            )
        )
    return merged


def _error_message(code: str) -> str:
    return {
        "media_file_invalid": "This recorded file could not be read as audio.",
        "unsupported_codec": "This audio's codec is not supported for analysis.",
        "decode_failed": "This audio could not be decoded.",
        "ffmpeg_unavailable": "Audio decoding is unavailable on this installation.",
        "birdnet_runtime_unavailable": (
            "The optional BirdNET acoustic adapter is not installed on this installation."
        ),
        "birdnet_model_load_failed": "The BirdNET model could not be loaded.",
        "birdnet_analysis_failed": "BirdNET analysis failed unexpectedly.",
    }.get(code, "This recorded audio could not be analyzed.")


def run_acoustic_analysis(
    repository: ProductRepository,
    *,
    media_asset_id: str,
    min_confidence: float | None = None,
    pipeline_version: str = DEFAULT_PIPELINE_VERSION,
    force_reprocess: bool = False,
    latitude: float | None = None,
    longitude: float | None = None,
    ffmpeg_binary: str = "ffmpeg",
    now: datetime | None = None,
    analyzer: Any | None = None,
    recording: Any | None = None,
) -> AcousticIngestResult:
    """Analyze one already-imported recorded-audio `MediaAsset`, producing
    ordinary needs-review candidate Visits exactly like a live Camera Node
    session -- see the module docstring for why this is an independent,
    bounded admission path rather than a reuse of the visual candidate
    -Visit machinery.

    `media_asset_id` must already exist (created by the existing manual-
    upload or folder-import path, now audio-content-type-aware) with
    `media_type == "audio"` -- this function never imports a file itself.
    The Stream/Source this candidate attaches to is always the MediaAsset's
    own already-recorded `stream_id`, mirroring `run_offline_video_ingest`'s
    identical "explicit operator-selected association" discipline.

    Idempotent by default: a prior `completed` run for the exact same
    `(media_asset_id, pipeline_version)` short-circuits with
    `status="already_processed"`. `analyzer`/`recording` are test-injection
    seams (see `birdnet_adapter.run_birdnet_on_clip`'s identical
    parameters) -- both omitted, the real, lazily-loaded BirdNET model is
    used. Passing `recording` avoids any dependency on the real
    `birdnetlib` package being installed at all.
    """

    resolved_now = now or datetime.now(UTC)
    media_asset = repository.get_media_asset(media_asset_id)
    if media_asset is None:
        raise AcousticIngestError("media_asset_not_found")
    if media_asset.media_type != AUDIO_MEDIA_TYPE:
        raise AcousticIngestError("media_asset_not_audio")
    stream = repository.get_stream(media_asset.stream_id)
    if stream is None:
        raise AcousticIngestError("missing_stream")
    stream_id = stream.id

    try:
        config = BirdNetAdapterConfig(
            min_confidence=(
                min_confidence if min_confidence is not None
                else BirdNetAdapterConfig().min_confidence
            ),
            latitude=latitude,
            longitude=longitude,
        )
    except BirdNetConfigurationError as error:
        raise AcousticIngestError(str(error)) from error

    existing = repository.find_acoustic_analysis_run(
        media_asset_id=media_asset_id, pipeline_version=pipeline_version,
    )
    if existing is not None and existing.status in ("queued", "processing"):
        return AcousticIngestResult(
            run_id=existing.id, status="in_progress", media_asset_id=media_asset_id,
            stream_id=stream_id, pipeline_version=pipeline_version,
            min_confidence=config.min_confidence,
        )
    if existing is not None and existing.status == "completed" and not force_reprocess:
        return AcousticIngestResult(
            run_id=existing.id, status="already_processed", media_asset_id=media_asset_id,
            stream_id=stream_id, pipeline_version=pipeline_version,
            min_confidence=config.min_confidence,
            windows_analyzed=existing.windows_analyzed,
            detections_above_threshold=existing.detections_above_threshold,
            species_suggestions_created=existing.species_suggestions_created,
            events_created=existing.events_created, visits_created=existing.visits_created,
            source_duration_seconds=existing.source_duration_seconds,
        )

    try:
        run = repository.create_acoustic_analysis_run(
            media_asset_id=media_asset_id, stream_id=stream_id, pipeline_version=pipeline_version,
            min_confidence=config.min_confidence, now=resolved_now,
        )
    except ValueError as error:
        if str(error) != "analysis_already_in_progress":
            raise
        return AcousticIngestResult(
            run_id="", status="in_progress", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, min_confidence=config.min_confidence,
        )

    capture_start = media_asset.captured_at
    boundary_anchor = capture_start if capture_start is not None else EPOCH_ANCHOR

    try:
        with tempfile.TemporaryDirectory(prefix="mockingbird-acoustic-ingest-") as tmp_dir:
            canonical_path = Path(tmp_dir) / "canonical.wav"
            transcode = decode_audio_to_canonical_wav(
                Path(media_asset.local_path), canonical_path, ffmpeg_binary=ffmpeg_binary,
            )
            source_sha256 = media_provenance.compute_content_sha256(Path(media_asset.local_path))

            analysis = run_birdnet_on_clip(
                canonical_path, config=config, source_content_sha256=source_sha256,
                analyzer=analyzer, recording=recording,
            )

        merged_detections = _merge_same_species_detections(analysis.detections)
        visit_ids: list[str] = []
        event_ids: list[str] = []
        species_suggestions_created = 0
        for detection in merged_detections:
            observed_at = boundary_anchor + timedelta(milliseconds=detection.start_ms)
            outcome = repository.create_acoustic_candidate_visit(
                stream_id=stream_id,
                media_asset_id=media_asset_id,
                detection=AcousticDetectionFacts(
                    common_name=detection.common_name,
                    scientific_name=detection.scientific_name,
                    confidence=detection.confidence,
                    window_start_ms=detection.start_ms,
                    window_end_ms=detection.end_ms,
                ),
                model_provenance=analysis.provenance.as_dict(),
                observed_at=observed_at,
                adapter_id=analysis.provenance.adapter_id,
                adapter_name=analysis.provenance.model_name,
            )
            if outcome.outcome == "created":
                species_suggestions_created += 1
                if outcome.visit_id is not None:
                    visit_ids.append(outcome.visit_id)
                if outcome.event_id is not None:
                    event_ids.append(outcome.event_id)

        distinct_event_ids = tuple(dict.fromkeys(event_ids))
        repository.complete_acoustic_analysis_run(
            run.id, status="completed", windows_analyzed=analysis.windows_analyzed,
            detections_above_threshold=len(analysis.detections),
            species_suggestions_created=species_suggestions_created,
            events_created=len(distinct_event_ids), visits_created=len(visit_ids),
            now=datetime.now(UTC), source_duration_seconds=transcode.duration_seconds,
        )
        return AcousticIngestResult(
            run_id=run.id, status="completed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, min_confidence=config.min_confidence,
            windows_analyzed=analysis.windows_analyzed,
            detections_above_threshold=len(analysis.detections),
            species_suggestions_created=species_suggestions_created,
            events_created=len(distinct_event_ids), visits_created=len(visit_ids),
            visit_ids=tuple(visit_ids), event_ids=distinct_event_ids,
            source_duration_seconds=transcode.duration_seconds,
            capture_time_known=capture_start is not None,
        )
    except (AudioDecodeError, BirdNetConfigurationError) as error:
        code = str(error)
        log_error_event(
            "acoustic_ingest", "acoustic_analysis_failed", code=code, exception=error,
            stream_id=stream_id, media_asset_id=media_asset_id, run_id=run.id,
        )
        repository.complete_acoustic_analysis_run(
            run.id, status="failed", windows_analyzed=0, detections_above_threshold=0,
            species_suggestions_created=0, events_created=0, visits_created=0,
            error_code=code, error_message=_error_message(code), now=datetime.now(UTC),
        )
        return AcousticIngestResult(
            run_id=run.id, status="failed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, min_confidence=config.min_confidence,
            error_code=code, error_message=_error_message(code),
        )
    except Exception as error:  # pragma: no cover - defensive orchestration boundary
        # Never partial truth: nothing above this point writes a Visit/
        # Event/SpeciesSuggestion outside `create_acoustic_candidate_
        # visit`'s own transaction, so an exception here can only leave
        # already-completed candidates persisted and this run row failed --
        # never a torn write. Mirrors `run_offline_video_ingest`'s identical
        # defensive boundary.
        code = "processing_failed"
        log_error_event(
            "acoustic_ingest", "acoustic_analysis_failed", code=code, exception=error,
            stream_id=stream_id, media_asset_id=media_asset_id, run_id=run.id,
        )
        repository.complete_acoustic_analysis_run(
            run.id, status="failed", windows_analyzed=0, detections_above_threshold=0,
            species_suggestions_created=0, events_created=0, visits_created=0,
            error_code=code, error_message="Acoustic analysis failed unexpectedly.",
            now=datetime.now(UTC),
        )
        return AcousticIngestResult(
            run_id=run.id, status="failed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, min_confidence=config.min_confidence,
            error_code=code, error_message="Acoustic analysis failed unexpectedly.",
        )


__all__ = [
    "AUDIO_MEDIA_TYPE",
    "DEFAULT_PIPELINE_VERSION",
    "EPOCH_ANCHOR",
    "AcousticIngestError",
    "AcousticIngestResult",
    "run_acoustic_analysis",
]
