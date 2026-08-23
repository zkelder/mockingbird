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

## Non-avian soundscape class filtering (Acoustic Runtime & Quality v1,
## Phase H -- benchmark-discovered)

BirdNET-Analyzer's bundled `BirdNET_GLOBAL_6K_V2.4` label set is not
exclusively bird species: confirmed by direct inspection of the real,
installed labels file (`birdnetlib/models/analyzer/BirdNET_GLOBAL_6K_V2.4_
Labels.txt`), it also includes 13 explicit non-avian "soundscape" classes
(`Dog`, `Engine`, `Environmental`, `Fireworks`, `Gryllus assimilis` and
`Miogryllus saussurei` -- both crickets, `Gun`, `Human non-vocal`, `Human
vocal`, `Human whistle`, `Noise`, `Power tools`, `Siren`) -- each stored
with its scientific name identical to its common name, BirdNET's own
convention for "not a species." Before this milestone's benchmark work
(Phase G/H) surfaced it with a real, clearly-licensed confusor recording (a
real lawnmower clip scored `Engine` at 0.607 confidence -- above the
*default* 0.5 floor), nothing in this module or `create_acoustic_candidate_
visit` filtered these out: a loud mechanical/human/animal sound could
create a fabricated needs-review "bird" candidate Visit labeled with a
nonsense species name. `NON_AVIAN_SOUNDSCAPE_LABELS` (below) is the fix:
these 13 labels are excluded before same-clip merge/admission -- an honest
abstention (no candidate created), never surfaced as if a bird had been
heard. `windows_analyzed`/`detections_above_threshold` on the run row still
honestly report BirdNET's *raw*, unfiltered output (a real, diagnostically
useful fact -- "BirdNET fired N times" -- distinct from "N candidates were
created"), so this filtering is never silently invisible in operational
history.

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

from collections.abc import Callable
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
    AcousticAnalysisRun,
    AcousticCandidateVisitOutcome,
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
    status: str  # "completed" | "failed" | "already_processed" | "in_progress" | "requeued"
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


#: BirdNET-Analyzer `BirdNET_GLOBAL_6K_V2.4`'s own non-avian "soundscape"
#: classes -- confirmed by direct inspection of the real, installed labels
#: file (`birdnetlib/models/analyzer/BirdNET_GLOBAL_6K_V2.4_Labels.txt`),
#: where each of these 13 entries stores its scientific name identical to
#: its common name (BirdNET's own convention for "not a species"), not
#: guessed from external documentation. See the module docstring's
#: "Non-avian soundscape class filtering" for why this exists and how it
#: was found. Exact strings, case-sensitive -- matched against `BirdNetDetection
#: .common_name` before same-clip merge/admission.
NON_AVIAN_SOUNDSCAPE_LABELS = frozenset(
    {
        "Dog",
        "Engine",
        "Environmental",
        "Fireworks",
        "Gryllus assimilis",
        "Gun",
        "Human non-vocal",
        "Human vocal",
        "Human whistle",
        "Miogryllus saussurei",
        "Noise",
        "Power tools",
        "Siren",
    }
)


def _is_non_avian_soundscape_class(detection: BirdNetDetection) -> bool:
    """Two independent signals, either sufficient on its own (found via
    review -- the first is the more robust one and should be trusted as
    the primary check):

    - `scientific_name == common_name` -- BirdNET's own general convention
      for "not a species" (see the module docstring), verified directly
      against the real installed label file to match exactly these same
      13 entries. Model-version-independent: a future BirdNET release that
      adds, renames, or relabels non-avian classes is still caught
      correctly without touching this code, unlike a hardcoded string
      list, which would silently stop matching.
    - `common_name in NON_AVIAN_SOUNDSCAPE_LABELS` -- the explicit,
      disclosed list, kept as defense-in-depth in case some future
      non-avian class does not follow the `scientific_name == common_name`
      convention."""

    return (
        detection.scientific_name == detection.common_name
        or detection.common_name in NON_AVIAN_SOUNDSCAPE_LABELS
    )


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


@dataclass(frozen=True)
class _AcousticAnalysisExecution:
    """The bounded outcome of one decode -> BirdNET -> admit pass, before
    either caller (`run_acoustic_analysis`'s own manual-path completion, or
    `execute_queued_acoustic_analysis`'s bounded-retry completion) decides
    how to finalize the run row. Factored out so the two callers can never
    silently diverge on the decode/analyze/merge/admit mechanics themselves
    -- only on what happens after."""

    windows_analyzed: int
    detections_above_threshold: int
    species_suggestions_created: int
    #: Every Visit/Event this run touched, created or merely extended --
    #: for traceability (e.g. "which Visits does this run's evidence now
    #: appear on").
    visit_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    #: Strict subset of the above: only the ones genuinely created by THIS
    #: run (`outcome.outcome == "created"`), never one Phase I cross-segment
    #: consolidation extended. Found via review: an earlier version counted
    #: `"extended"` outcomes as creations too, so a bird calling across N
    #: consecutive segments would durably record `visits_created=1`/
    #: `events_created=1` on N different run rows for the same one Visit --
    #: `AcousticIngestResult.visits_created`/`.events_created` are the
    #: honest counts, derived from these, never from `visit_ids`/`event_ids`.
    newly_created_visit_ids: tuple[str, ...]
    newly_created_event_ids: tuple[str, ...]
    source_duration_seconds: float | None


#: What the shared execution helper calls once per merged detection to turn
#: it into a durable candidate -- `model_provenance`/`adapter_id`/
#: `adapter_name` are passed at call time (only known once `run_birdnet_
#: on_clip` has actually returned, inside `_execute_acoustic_analysis`
#: itself), never pre-baked into the callback's own construction.
#: `run_acoustic_analysis` (manual path) always passes a callback that
#: calls `repository.create_acoustic_candidate_visit` unconditionally. The
#: automatic runtime (`mockingbird.observation.acoustic_runtime`) instead
#: passes a callback that first tries `extend_acoustic_candidate_visit` for
#: cross-segment consolidation (Phase I) and falls back to `create_
#: acoustic_candidate_visit` only if nothing was extendable -- kept out of
#: this module entirely, since consolidation needs cross-call state
#: (`acoustic_ingest.run_acoustic_analysis`/`execute_queued_acoustic_
#: analysis` are each a single, independent, stateless call).
AdmitDetection = Callable[
    [BirdNetDetection, datetime, "dict[str, Any]", str, str], AcousticCandidateVisitOutcome,
]


def _default_admit_detection(
    repository: ProductRepository, *, stream_id: str, media_asset_id: str,
) -> AdmitDetection:
    """The manual path's unconditional-create policy -- byte-identical to
    `run_acoustic_analysis`'s original inline loop body, just wrapped as a
    callback so `_execute_acoustic_analysis` can be shared."""

    def _admit(
        detection: BirdNetDetection, observed_at: datetime,
        model_provenance: dict[str, Any], adapter_id: str, adapter_name: str,
    ) -> AcousticCandidateVisitOutcome:
        return repository.create_acoustic_candidate_visit(
            stream_id=stream_id,
            media_asset_id=media_asset_id,
            detection=AcousticDetectionFacts(
                common_name=detection.common_name,
                scientific_name=detection.scientific_name,
                confidence=detection.confidence,
                window_start_ms=detection.start_ms,
                window_end_ms=detection.end_ms,
            ),
            model_provenance=model_provenance,
            observed_at=observed_at,
            adapter_id=adapter_id,
            adapter_name=adapter_name,
        )

    return _admit


def _execute_acoustic_analysis(
    repository: ProductRepository,
    *,
    stream_id: str,
    media_asset_id: str,
    media_asset_local_path: str,
    boundary_anchor: datetime,
    config: BirdNetAdapterConfig,
    ffmpeg_binary: str,
    analyzer: Any | None,
    recording: Any | None,
    admit_detection: AdmitDetection,
) -> _AcousticAnalysisExecution:
    """Decode -> BirdNET -> same-clip merge -> admit one bounded clip. Raises
    `AudioDecodeError`/`BirdNetConfigurationError` for an expected, bounded
    failure code, or any other `Exception` for a genuinely unexpected one --
    both callers catch and finalize the run row themselves; this helper
    never touches `AcousticAnalysisRunModel` at all."""

    with tempfile.TemporaryDirectory(prefix="mockingbird-acoustic-ingest-") as tmp_dir:
        canonical_path = Path(tmp_dir) / "canonical.wav"
        transcode = decode_audio_to_canonical_wav(
            Path(media_asset_local_path), canonical_path, ffmpeg_binary=ffmpeg_binary,
        )
        source_sha256 = media_provenance.compute_content_sha256(Path(media_asset_local_path))

        analysis = run_birdnet_on_clip(
            canonical_path, config=config, source_content_sha256=source_sha256,
            analyzer=analyzer, recording=recording,
        )

    # Phase H (benchmark-discovered, see the module docstring's "Non-avian
    # soundscape class filtering"): exclude BirdNET's own non-bird
    # soundscape classes *before* merge/admission -- an honest abstention,
    # never a fabricated "bird" candidate for a dog bark, siren, human
    # voice, or engine noise. `analysis.detections` (unfiltered) is still
    # what `detections_above_threshold`/`windows_analyzed` report below --
    # this filtering only affects candidate-creation eligibility.
    avian_detections = tuple(
        detection for detection in analysis.detections
        if not _is_non_avian_soundscape_class(detection)
    )
    merged_detections = _merge_same_species_detections(avian_detections)
    visit_ids: list[str] = []
    event_ids: list[str] = []
    species_suggestions_created = 0
    newly_created_visit_ids: list[str] = []
    newly_created_event_ids: list[str] = []
    provenance_dict = analysis.provenance.as_dict()
    for detection in merged_detections:
        observed_at = boundary_anchor + timedelta(milliseconds=detection.start_ms)
        outcome = admit_detection(
            detection, observed_at, provenance_dict,
            analysis.provenance.adapter_id, analysis.provenance.model_name,
        )
        if outcome.outcome in ("created", "extended"):
            species_suggestions_created += 1
            if outcome.visit_id is not None:
                visit_ids.append(outcome.visit_id)
            if outcome.event_id is not None:
                event_ids.append(outcome.event_id)
            if outcome.outcome == "created":
                if outcome.visit_id is not None:
                    newly_created_visit_ids.append(outcome.visit_id)
                if outcome.event_id is not None:
                    newly_created_event_ids.append(outcome.event_id)

    return _AcousticAnalysisExecution(
        windows_analyzed=analysis.windows_analyzed,
        detections_above_threshold=len(analysis.detections),
        species_suggestions_created=species_suggestions_created,
        visit_ids=tuple(visit_ids),
        event_ids=tuple(dict.fromkeys(event_ids)),
        newly_created_visit_ids=tuple(newly_created_visit_ids),
        newly_created_event_ids=tuple(dict.fromkeys(newly_created_event_ids)),
        source_duration_seconds=transcode.duration_seconds,
    )


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
        execution = _execute_acoustic_analysis(
            repository,
            stream_id=stream_id,
            media_asset_id=media_asset_id,
            media_asset_local_path=media_asset.local_path,
            boundary_anchor=boundary_anchor,
            config=config,
            ffmpeg_binary=ffmpeg_binary,
            analyzer=analyzer,
            recording=recording,
            admit_detection=_default_admit_detection(
                repository, stream_id=stream_id, media_asset_id=media_asset_id,
            ),
        )
        repository.complete_acoustic_analysis_run(
            run.id, status="completed", windows_analyzed=execution.windows_analyzed,
            detections_above_threshold=execution.detections_above_threshold,
            species_suggestions_created=execution.species_suggestions_created,
            events_created=len(execution.newly_created_event_ids),
            visits_created=len(execution.newly_created_visit_ids),
            now=datetime.now(UTC), source_duration_seconds=execution.source_duration_seconds,
        )
        return AcousticIngestResult(
            run_id=run.id, status="completed", media_asset_id=media_asset_id, stream_id=stream_id,
            pipeline_version=pipeline_version, min_confidence=config.min_confidence,
            windows_analyzed=execution.windows_analyzed,
            detections_above_threshold=execution.detections_above_threshold,
            species_suggestions_created=execution.species_suggestions_created,
            events_created=len(execution.newly_created_event_ids),
            visits_created=len(execution.newly_created_visit_ids),
            visit_ids=execution.visit_ids, event_ids=execution.event_ids,
            source_duration_seconds=execution.source_duration_seconds,
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


def execute_queued_acoustic_analysis(
    repository: ProductRepository,
    *,
    run: AcousticAnalysisRun,
    latitude: float | None = None,
    longitude: float | None = None,
    ffmpeg_binary: str = "ffmpeg",
    now: datetime | None = None,
    analyzer: Any | None = None,
    recording: Any | None = None,
    admit_detection: AdmitDetection | None = None,
) -> AcousticIngestResult:
    """Acoustic Runtime & Quality v1: run BirdNET analysis for one segment
    the automatic reconcile loop has *already* claimed (`run.status ==
    "processing"`, `run.claimed_by` set by `ProductRepository.claim_next_
    queued_acoustic_analysis`) -- the automatic-pipeline sibling of
    `run_acoustic_analysis`, sharing its exact decode/BirdNET/merge/admit
    mechanics (`_execute_acoustic_analysis`) but never creating a run row
    itself (the caller already did, at enqueue time) and never treating a
    failure as unconditionally terminal.

    On success: identical `complete_acoustic_analysis_run` completion to
    the manual path. On an expected (`AudioDecodeError`/
    `BirdNetConfigurationError`) or unexpected failure: `repository.retry_
    or_fail_acoustic_analysis_run` decides bounded requeue-with-backoff vs.
    terminal `failed` -- reflected in the returned `AcousticIngestResult.
    status` as `"requeued"` or `"failed"` respectively, so the caller's
    diagnostics/logging can tell the two apart.

    `admit_detection` defaults to the same unconditional-create policy
    `run_acoustic_analysis` uses; the runtime service passes its own
    consolidation-aware callback instead (see `AdmitDetection`'s
    docstring)."""

    resolved_now = now or datetime.now(UTC)
    media_asset = repository.get_media_asset(run.media_asset_id)
    if media_asset is None:  # pragma: no cover - defensive, the claimed row always references a real asset
        raise AcousticIngestError("media_asset_not_found")

    config = BirdNetAdapterConfig(
        min_confidence=run.min_confidence, latitude=latitude, longitude=longitude,
    )
    capture_start = media_asset.captured_at
    boundary_anchor = capture_start if capture_start is not None else EPOCH_ANCHOR
    admit = admit_detection or _default_admit_detection(
        repository, stream_id=run.stream_id, media_asset_id=run.media_asset_id,
    )

    try:
        execution = _execute_acoustic_analysis(
            repository,
            stream_id=run.stream_id,
            media_asset_id=run.media_asset_id,
            media_asset_local_path=media_asset.local_path,
            boundary_anchor=boundary_anchor,
            config=config,
            ffmpeg_binary=ffmpeg_binary,
            analyzer=analyzer,
            recording=recording,
            admit_detection=admit,
        )
        repository.complete_acoustic_analysis_run(
            run.id, status="completed", windows_analyzed=execution.windows_analyzed,
            detections_above_threshold=execution.detections_above_threshold,
            species_suggestions_created=execution.species_suggestions_created,
            events_created=len(execution.newly_created_event_ids),
            visits_created=len(execution.newly_created_visit_ids),
            now=resolved_now, source_duration_seconds=execution.source_duration_seconds,
        )
        return AcousticIngestResult(
            run_id=run.id, status="completed", media_asset_id=run.media_asset_id,
            stream_id=run.stream_id, pipeline_version=run.pipeline_version,
            min_confidence=config.min_confidence,
            windows_analyzed=execution.windows_analyzed,
            detections_above_threshold=execution.detections_above_threshold,
            species_suggestions_created=execution.species_suggestions_created,
            events_created=len(execution.newly_created_event_ids),
            visits_created=len(execution.newly_created_visit_ids),
            visit_ids=execution.visit_ids, event_ids=execution.event_ids,
            source_duration_seconds=execution.source_duration_seconds,
            capture_time_known=capture_start is not None,
        )
    except (AudioDecodeError, BirdNetConfigurationError) as error:
        code = str(error)
        return _retry_or_fail(repository, run, code=code, now=resolved_now)
    except Exception as error:  # pragma: no cover - defensive orchestration boundary
        # Same "never partial truth" reasoning as `run_acoustic_analysis`'s
        # identical defensive boundary -- an exception here can only leave
        # already-completed candidates persisted and this run row requeued
        # or failed, never a torn write.
        log_error_event(
            "acoustic_ingest", "acoustic_analysis_failed", code="processing_failed",
            exception=error, stream_id=run.stream_id, media_asset_id=run.media_asset_id,
            run_id=run.id,
        )
        return _retry_or_fail(repository, run, code="processing_failed", now=resolved_now)


def _retry_or_fail(
    repository: ProductRepository, run: AcousticAnalysisRun, *, code: str, now: datetime,
) -> AcousticIngestResult:
    log_error_event(
        "acoustic_ingest", "acoustic_analysis_failed", code=code,
        stream_id=run.stream_id, media_asset_id=run.media_asset_id, run_id=run.id,
    )
    outcome = repository.retry_or_fail_acoustic_analysis_run(
        run.id, error_code=code, error_message=_error_message(code), now=now,
    )
    return AcousticIngestResult(
        run_id=run.id, status=outcome, media_asset_id=run.media_asset_id,
        stream_id=run.stream_id, pipeline_version=run.pipeline_version,
        min_confidence=run.min_confidence, error_code=code, error_message=_error_message(code),
    )


__all__ = [
    "AUDIO_MEDIA_TYPE",
    "DEFAULT_PIPELINE_VERSION",
    "EPOCH_ANCHOR",
    "NON_AVIAN_SOUNDSCAPE_LABELS",
    "AcousticIngestError",
    "AcousticIngestResult",
    "AdmitDetection",
    "execute_queued_acoustic_analysis",
    "run_acoustic_analysis",
]
