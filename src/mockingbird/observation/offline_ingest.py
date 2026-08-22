"""Offline / Recorded Observation Ingest v1 -- the acquisition-session
orchestrator that drives one already-imported recorded-video `MediaAsset`
through the exact same Observation Engine seam a live Camera Node session
uses. See docs/offline-recorded-media-observation-contract.md for the full
product contract; this module is the mechanism.

## What this module does NOT do

It does not implement detection, tracking, Visit assembly, evidence
scoring, multi-subject grouping, Privacy/Ignore enforcement, or admission
policy -- every one of those is the existing, completely unmodified
Observation Engine v2 stack (`FrameDrivenObservationProvider`,
`visit_episode_assembler`, `candidate_visit_authority`,
`candidate_visit_adapter`, `ProductRepository.create_candidate_visit_
from_proposal`). This module only:

1. decodes one recorded video into the same `FramePacket` shape a live
   session already produces (`recorded_video_source`);
2. runs those packets through the real detector/tracker via
   `FrameDrivenObservationProvider.replay_frames` -- the same method the
   existing Perception Replay Regression Harness already uses for offline
   frame sources, called exactly once per video (a provider `reset()`s and
   finalizes on every call, so calling it more than once per recording
   would fabricate an artificial mid-encounter break -- see "Why exactly
   one `replay_frames` call per video" below);
3. assembles the resulting tracklets and, in one deterministic pass, admits
   each proposal through the unmodified authority/evidence/scene-confusor
   gate, exactly like `admission_replay.evaluate_shadow_admission` already
   does for the isolated test-only regression harness -- except against
   the *real* product repository and the MediaAsset's own already-selected
   Stream, never an isolated database;
4. records bounded progress/diagnostics in `RecordedMediaAnalysisRunModel`.

## Why exactly one `replay_frames` call per video

`FrameDrivenObservationProvider.replay_frames` calls `self.reset()` at
entry and `self.finalize_replay()`/`drain_final_results()` at exit -- each
call is a self-contained reset-process-finalize cycle (see its own
implementation). Splitting one recording's frames across multiple calls
would reset tracker state between chunks and finalize (i.e. "the recording
ended here") at every artificial chunk boundary, fragmenting one
continuous encounter purely because of how *this module* happened to
batch its own frames -- exactly the "frame gaps caused by sampling/seek
behavior must not accidentally fragment one encounter" failure this
contract must avoid. `recorded_video_source.sample_recorded_video_frames`
therefore decodes with a bounded streaming ffmpeg pipe (never buffering
the raw source file), but the resulting bounded, already-downsampled,
JPEG-compressed frame sequence for one video is assembled into one ordered
tuple and fed to `replay_frames` exactly once -- identical to how
`replay.ReplayRunner`/`perception_regression.run_perception_regression`
already drive this same seam for every other offline frame source.

## Acquisition-session semantics and timestamp policy

Every proposal this run admits is attempted with authority activated
freshly for this one call (`fresh_session=True`, mirroring exactly what a
real "Start observing" action does for a live Stream -- see
`engine_runtime._EngineSession`), and reverted to `shadow` unconditionally
afterward -- an offline analysis run is its own bounded acquisition
session, never a standing "this Stream is now live" state change.

`observed_at` passed to the authority gate/persisted Event timestamps is
derived per-proposal from the *video's own* timeline, never real
processing wall-clock "now": `capture_start + proposal.start_offset_ms`
when this MediaAsset's own `captured_at` (EXIF/container `creation_time`,
already extracted at import time) is known, or the same Unix-epoch-anchor
convention `frame_driven_provider._with_fallback_captured_at` already uses
when it is not -- see "Frame-time semantics" in
docs/offline-recorded-media-observation-contract.md. Import time (the
real "now" this function actually runs) only ever appears on this run's
own `RecordedMediaAnalysisRunModel` diagnostic row, never on the resulting
Visit/Event -- this is what keeps "imported today" honestly distinct from
"observed today" (see "Today/history timestamp behavior" in the same
doc).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mockingbird.diagnostics.structured_log import log_error_event
from mockingbird.observation.candidate_visit_authority import (
    ObservationAuthorityMode,
    resolve_ambiguous_boundary_arbitration,
)
from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.contracts import EvidenceCandidate, ObservationResult, TrackUpdate
from mockingbird.observation.engine_runtime import (
    ProviderLoader,
    _engine_failure_message,
    _load_real_provider,
    _sanitized,
    resolve_provider_config_path,
)
from mockingbird.observation.recorded_video_source import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_SAMPLE_FPS,
    RecordedVideoDecodeError,
    frame_packets_from_recorded_video,
    sample_recorded_video_frames,
)
from mockingbird.observation.visit_episode_assembler import build_tracklets, assemble_visit_episodes
from mockingbird.repository.product_repository import ProductRepository

#: A distinct, stable `provider_key` for every candidate this pipeline ever
#: creates -- durable, diagnostic-only lineage (persisted on
#: `ObservationCandidateVisitModel.provider_key`, never product-facing
#: truth) that answers "was this candidate produced by a live Camera Node
#: session, the candidate-authority CLI trial, the perception-replay
#: regression harness, or offline recorded-media ingest?" without touching
#: `EventModel.event_type`/`title`, which stay the existing, unmodified
#: `"observation_engine_candidate"` string every Stage 7 candidate already
#: uses (see "Source association" / "Acquisition-session semantics" in
#: docs/offline-recorded-media-observation-contract.md for why this is
#: sufficient and reuses established precedent -- `admission_replay.py`'s
#: own `provider_key="perception-replay-regression-v1"` is the exact same
#: pattern).
OFFLINE_INGEST_PROVIDER_KEY = "recorded-media-offline-ingest-v1"

#: The current pipeline identity: bumped whenever the offline decode/
#: assembly/admission mechanism itself materially changes, so a caller
#: explicitly wanting fresh analysis under a newer pipeline build supplies
#: (or this module's own default advances to) a new value -- see
#: "Idempotency" in docs/offline-recorded-media-observation-contract.md.
DEFAULT_PIPELINE_VERSION = "offline-video-ingest-v1"

#: The activation-boundary/fallback-timestamp anchor for a recording whose
#: own capture start is unknown -- deliberately the Unix epoch, mirroring
#: `frame_driven_provider._with_fallback_captured_at`'s own established
#: "obviously not a real date, never a fabricated 'now'" convention.
EPOCH_ANCHOR = datetime(1970, 1, 1, tzinfo=UTC)

VIDEO_MEDIA_TYPE = "video"


class OfflineIngestError(ValueError):
    """Stable, bounded orchestration-failure code -- see "Error taxonomy" in
    docs/offline-recorded-media-observation-contract.md. Never a raw
    filesystem path or third-party exception message."""


@dataclass(frozen=True)
class OfflineIngestResult:
    """The bounded, complete outcome of one offline recorded-video analysis
    attempt -- everything an API route, CLI command, or test needs to
    report status without re-deriving it from the durable run row."""

    run_id: str
    status: str  # "completed" | "failed" | "already_processed" | "in_progress"
    media_asset_id: str
    stream_id: str
    pipeline_version: str
    sample_fps: float
    frames_considered: int = 0
    frames_analyzed: int = 0
    events_created: int = 0
    visits_created: int = 0
    visit_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    source_duration_seconds: float | None = None
    truncated: bool = False
    capture_time_known: bool = False
    error_code: str | None = None
    error_message: str | None = None
    outcome_counts: dict[str, int] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"


def _generation_ids_by_evidence(evidence: tuple[EvidenceCandidate, ...]) -> dict[str, tuple[str, ...]]:
    """Group already-produced evidence candidates by their own
    `track_generation_id` -- a small, purely mechanical grouping utility
    (not detection/tracking/assembly logic), mirroring `replay._evidence_
    media_asset_ids_by_generation`'s identical shape for the exact same
    purpose (`visit_episode_assembler.build_tracklets`'s optional
    `evidence_candidate_ids_by_generation` argument)."""

    by_generation: dict[str, list[str]] = {}
    for item in evidence:
        if item.track_generation_id is None:
            continue
        bucket = by_generation.setdefault(item.track_generation_id, [])
        if item.media_asset_id not in bucket:
            bucket.append(item.media_asset_id)
    return {key: tuple(value) for key, value in by_generation.items()}


async def run_offline_video_ingest(
    repository: ProductRepository,
    *,
    media_asset_id: str,
    sample_fps: float = DEFAULT_SAMPLE_FPS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    pipeline_version: str = DEFAULT_PIPELINE_VERSION,
    force_reprocess: bool = False,
    ffmpeg_binary: str = "ffmpeg",
    provider_loader: ProviderLoader = _load_real_provider,
    now: datetime | None = None,
) -> OfflineIngestResult:
    """Analyze one already-imported recorded-video `MediaAsset` through the
    ordinary Observation Engine seam, producing Visit/Event/Evidence rows
    the existing Review Queue can show exactly like a live candidate.

    `media_asset_id` must already exist (created by the existing folder-
    import path) with `media_type == "video"` -- this function never scans
    a folder, imports a file, or creates a MediaAsset itself. The Stream/
    Source this candidate attaches to is always the MediaAsset's own
    already-recorded `stream_id`, never a caller-supplied override and
    never a default "active" camera -- see "Source association" in
    docs/offline-recorded-media-observation-contract.md.

    Idempotent by default: a prior `completed` run for the exact same
    `(media_asset_id, pipeline_version)` short-circuits with
    `status="already_processed"` and creates no new candidates. Pass
    `force_reprocess=True` to run again anyway (still under the same
    `pipeline_version` -- every resulting proposal id is still content-
    addressed, so a genuinely identical decode converges on the existing
    idempotent-repeat outcome at the persistence boundary; only a decode-
    affecting change, such as `sample_fps`, or an explicit new
    `pipeline_version`, can actually produce different candidates).
    """

    resolved_now = now or datetime.now(UTC)
    media_asset = repository.get_media_asset(media_asset_id)
    if media_asset is None:
        raise OfflineIngestError("media_asset_not_found")
    if media_asset.media_type != VIDEO_MEDIA_TYPE:
        raise OfflineIngestError("media_asset_not_video")
    stream = repository.get_stream(media_asset.stream_id)
    if stream is None:
        raise OfflineIngestError("missing_stream")
    stream_id = stream.id

    existing = repository.find_recorded_media_analysis_run(
        media_asset_id=media_asset_id, pipeline_version=pipeline_version,
    )
    if existing is not None and existing.status in ("queued", "processing"):
        return OfflineIngestResult(
            run_id=existing.id, status="in_progress", media_asset_id=media_asset_id,
            stream_id=stream_id, pipeline_version=pipeline_version, sample_fps=existing.sample_fps,
        )
    if existing is not None and existing.status == "completed" and not force_reprocess:
        return OfflineIngestResult(
            run_id=existing.id, status="already_processed", media_asset_id=media_asset_id,
            stream_id=stream_id, pipeline_version=pipeline_version, sample_fps=existing.sample_fps,
            frames_considered=existing.frames_considered, frames_analyzed=existing.frames_analyzed,
            events_created=existing.events_created, visits_created=existing.visits_created,
            source_duration_seconds=existing.source_duration_seconds,
        )

    try:
        run = repository.create_recorded_media_analysis_run(
            media_asset_id=media_asset_id, stream_id=stream_id, pipeline_version=pipeline_version,
            sample_fps=sample_fps, now=resolved_now,
        )
    except ValueError as error:
        if str(error) != "analysis_already_in_progress":
            raise
        # A genuine race against a concurrent attempt for the exact same
        # (media_asset_id, pipeline_version) that started between this
        # call's own idempotency pre-check above and this insert -- the
        # bounded, single-process-adequate guard described in "Idempotency
        # and concurrency" in docs/offline-recorded-media-observation-
        # contract.md caught it here instead. Report the same honest
        # outcome the pre-check path already reports, rather than letting
        # a raw ValueError escape as an unhandled 500.
        return OfflineIngestResult(
            run_id="", status="in_progress", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, sample_fps=sample_fps,
        )

    capture_start = media_asset.captured_at
    try:
        analysis_excluded_regions = repository.stream_privacy_ignore_regions(stream_id)
        sampling = sample_recorded_video_frames(
            Path(media_asset.local_path), sample_fps=sample_fps, max_frames=max_frames,
            ffmpeg_binary=ffmpeg_binary,
        )
        packets = frame_packets_from_recorded_video(
            sampling, stream_id=stream_id, media_asset_id_prefix=media_asset_id,
            capture_start=capture_start, analysis_excluded_regions=analysis_excluded_regions,
        )
        payload_by_media_asset_id = {packet.media_asset_id: packet.payload for packet in packets}

        try:
            provider, detector = provider_loader(resolve_provider_config_path())
        except (ValueError, OSError, RuntimeError) as error:
            message, _category = _engine_failure_message(error)
            repository.complete_recorded_media_analysis_run(
                run.id, status="failed", frames_considered=sampling.frame_count, frames_analyzed=0,
                events_created=0, visits_created=0, error_code="engine_unavailable",
                error_message=message, now=datetime.now(UTC),
                source_duration_seconds=sampling.source_duration_seconds,
            )
            return OfflineIngestResult(
                run_id=run.id, status="failed", media_asset_id=media_asset_id, stream_id=stream_id,
                pipeline_version=pipeline_version, sample_fps=sample_fps,
                frames_considered=sampling.frame_count, source_duration_seconds=sampling.source_duration_seconds,
                truncated=sampling.truncated, capture_time_known=capture_start is not None,
                error_code="engine_unavailable", error_message=message,
            )

        boundary_anchor = capture_start if capture_start is not None else EPOCH_ANCHOR
        repository.set_observation_authority_mode(
            ObservationAuthorityMode.candidate_visit, stream_id=stream_id, fresh_session=True, now=EPOCH_ANCHOR,
        )
        try:
            # Authority must stay active for both the decode/track pass
            # *and* the admission loop below -- `attempt_candidate` is what
            # actually re-checks the authority mode, not `replay_frames`
            # itself. See "Kill switch" in docs/candidate-visit-authority-
            # contract.md: the revert below is this whole bounded
            # acquisition session's own kill switch, unconditional in the
            # `finally`, never a standing "this Stream is now live" change.
            results: tuple[ObservationResult, ...] = await provider.replay_frames(packets)

            frames_analyzed = sum(1 for result in results if result.detector_ran)
            all_track_updates: list[TrackUpdate] = []
            all_evidence_candidates: list[EvidenceCandidate] = []
            for result in results:
                all_track_updates.extend(result.track_updates)
                all_evidence_candidates.extend(result.evidence_candidates)

            tracklets = build_tracklets(
                tuple(all_track_updates), stream_id=stream_id,
                evidence_candidate_ids_by_generation=_generation_ids_by_evidence(tuple(all_evidence_candidates)),
            )
            # No `known_horizon_ms`: this recording is already, wholly
            # observed by construction (the entire file was decoded above),
            # so every resulting proposal honestly reports `continuation_
            # pending=False` -- the same default behavior every other
            # offline/already-complete caller (`replay.py`) already relies
            # on; see "Episode finality" in docs/tracklet-visit-assembly-
            # contract.md.
            assembly = assemble_visit_episodes(tracklets)

            ordered_proposals = tuple(
                sorted(assembly.proposals, key=lambda item: (item.start_offset_ms, item.proposal_id))
            )
            arbitration = resolve_ambiguous_boundary_arbitration(ordered_proposals)
            evidence_by_generation: dict[str, list[EvidenceCandidate]] = {}
            for candidate in all_evidence_candidates:
                if candidate.track_generation_id is not None:
                    evidence_by_generation.setdefault(candidate.track_generation_id, []).append(candidate)

            adapter = CandidateVisitAuthorityAdapter(
                repository, detector_provenance=getattr(detector, "provider_id", None),
                tracker_provenance=provider.provider_id, provider_key=OFFLINE_INGEST_PROVIDER_KEY,
            )
            visit_ids: list[str] = []
            event_ids: list[str] = []
            outcome_counts: dict[str, int] = {}
            for proposal in ordered_proposals:
                relevant_evidence = tuple(
                    candidate
                    for generation_id in proposal.constituent_generation_ids
                    for candidate in evidence_by_generation.get(generation_id, ())
                )
                observed_at = boundary_anchor + timedelta(milliseconds=proposal.start_offset_ms)
                attempt = adapter.attempt_candidate(
                    proposal, evidence_candidates=relevant_evidence, evidence_bytes=payload_by_media_asset_id,
                    observed_at=observed_at,
                    ambiguous_boundary_resolved=proposal.proposal_id in arbitration.resolved_winner_ids,
                )
                outcome_counts[attempt.outcome] = outcome_counts.get(attempt.outcome, 0) + 1
                if attempt.created and attempt.visit_id is not None and attempt.event_id is not None:
                    visit_ids.append(attempt.visit_id)
                    event_ids.append(attempt.event_id)
        finally:
            # The kill switch -- always revert, whether analysis succeeded,
            # failed, or raised.
            repository.set_observation_authority_mode(
                ObservationAuthorityMode.shadow, stream_id=stream_id, now=resolved_now,
            )

        distinct_event_ids = tuple(dict.fromkeys(event_ids))
        repository.complete_recorded_media_analysis_run(
            run.id, status="completed", frames_considered=sampling.frame_count,
            frames_analyzed=frames_analyzed, events_created=len(distinct_event_ids),
            visits_created=len(visit_ids), now=datetime.now(UTC),
            source_duration_seconds=sampling.source_duration_seconds,
        )
        return OfflineIngestResult(
            run_id=run.id, status="completed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, sample_fps=sample_fps, frames_considered=sampling.frame_count,
            frames_analyzed=frames_analyzed, events_created=len(distinct_event_ids),
            visits_created=len(visit_ids), visit_ids=tuple(visit_ids), event_ids=distinct_event_ids,
            source_duration_seconds=sampling.source_duration_seconds, truncated=sampling.truncated,
            capture_time_known=capture_start is not None, outcome_counts=outcome_counts,
        )
    except RecordedVideoDecodeError as error:
        code = _sanitized(error)
        # Pre-Freeze Operability Gap Closure v1 ("A2 frame-decode failures
        # -- recorded/offline media"): disclosed as absent in
        # docs/observability-error-taxonomy-contract.md. One bounded record
        # per failed run -- `run_offline_video_ingest` decodes a whole
        # recording in one bounded `sample_recorded_video_frames` call (see
        # its own module docstring), never a per-frame retry loop, so this
        # can fire at most once per analysis attempt; no suppression
        # mechanism is needed here. Reuses the existing, already-registered
        # `OFFLINE_INGEST` taxonomy codes (`media_file_invalid`/
        # `unsupported_codec`/`decode_failed`/`ffmpeg_unavailable`) rather
        # than inventing new ones.
        log_error_event(
            "offline_ingest",
            "recorded_media_decode_failed",
            code=code,
            exception=error,
            stream_id=stream_id,
            media_asset_id=media_asset_id,
            run_id=run.id,
        )
        repository.complete_recorded_media_analysis_run(
            run.id, status="failed", frames_considered=0, frames_analyzed=0, events_created=0,
            visits_created=0, error_code=code, error_message=_decode_error_message(code),
            now=datetime.now(UTC),
        )
        return OfflineIngestResult(
            run_id=run.id, status="failed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, sample_fps=sample_fps, error_code=code,
            error_message=_decode_error_message(code),
        )
    except Exception as error:  # pragma: no cover - defensive orchestration boundary
        # A genuine, unexpected failure -- never partial truth: nothing
        # above this point writes a Visit/Event outside the repository's
        # own already-transactional `create_candidate_visit_from_proposal`,
        # so an exception here can only ever leave already-completed
        # candidates persisted (each independently, its own transaction) and
        # this run row recorded `failed` -- never a torn write.
        code = "processing_failed"
        repository.complete_recorded_media_analysis_run(
            run.id, status="failed", frames_considered=0, frames_analyzed=0, events_created=0,
            visits_created=0, error_code=code, error_message=_sanitized(error), now=datetime.now(UTC),
        )
        return OfflineIngestResult(
            run_id=run.id, status="failed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, sample_fps=sample_fps, error_code=code,
            error_message="Recorded-media analysis failed unexpectedly.",
        )


def _decode_error_message(code: str) -> str:
    return {
        "media_file_invalid": "This recorded file could not be read as a video.",
        "unsupported_codec": "This video's codec is not supported for analysis.",
        "decode_failed": "This video could not be decoded.",
        "ffmpeg_unavailable": "Video decoding is unavailable on this installation.",
        "invalid_sample_fps": "The requested analysis sampling rate is invalid.",
        "invalid_max_frames": "The requested frame limit is invalid.",
    }.get(code, "This recorded video could not be analyzed.")


__all__ = [
    "DEFAULT_PIPELINE_VERSION",
    "EPOCH_ANCHOR",
    "OFFLINE_INGEST_PROVIDER_KEY",
    "OfflineIngestError",
    "OfflineIngestResult",
    "run_offline_video_ingest",
]
