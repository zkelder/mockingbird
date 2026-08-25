"""Bounded, restart-safe, quality-governed acoustic analysis runtime --
Acoustic Runtime & Quality v1. See docs/acoustic-runtime-quality-v1-
contract.md for the full policy.

Turns the accepted, explicit/manual acoustic path (`mockingbird.observation.
acoustic_ingest`, `mockingbird.species.birdnet_adapter`) into a continuously
-running pipeline, without changing either of those modules' own public
contracts for the existing manual `/analyze-audio` route:

    bounded audio segment source
    -> durable analysis work (queue admission, ProductRepository)
    -> BirdNET inference (acoustic_ingest.execute_queued_acoustic_analysis)
    -> quality/abstention policy (BirdNET's own confidence floor + always-
       needs_review admission -- unchanged, see docs)
    -> candidate Observation/evidence (create_acoustic_candidate_visit /
       extend_acoustic_candidate_visit)
    -> retry/recovery (ProductRepository's bounded backoff ledger)
    -> bounded retention (run_working_audio_retention_sweep)

## Why this is a new small module, not a new generic scheduler

Every existing "background loop" in this codebase (`DurableMonitoringSupervisor`,
`LocalStorageRetentionService`, `_EngineSession`) is a thin `threading.Thread`
wrapping a synchronous, individually-callable reconcile method, backed by a
durable-state Protocol/model with bounded retry/backoff columns. This module
reuses that exact shape rather than inventing a parallel task-scheduling
framework: `AcousticRuntimeService` is closest in spirit to
`LocalStorageRetentionService` (a queue-drain loop over many short-lived
items, not a small fixed set of long-lived Streams the way
`DurableMonitoringSupervisor` models cameras), while the durable state it
reconciles against (`AcousticAnalysisRunModel`) reuses `StreamRuntimeCheckpointModel`'s
established `consecutive_failure_count`/`next_retry_at` column shape, just at
per-item instead of per-Stream granularity. See
`mockingbird.repository.product_repository`'s "Acoustic Runtime & Quality v1"
section for the durable primitives this module calls.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
import threading
from typing import Any, Protocol
import uuid

from mockingbird.diagnostics.structured_log import log_error_event, log_event
from mockingbird.observation import acoustic_ingest
from mockingbird.observation.audio_capture import CapturedSegment, MicrophoneSessionManager
from mockingbird.repository.product_repository import (
    AcousticAnalysisRun,
    AcousticCandidateVisitOutcome,
    AcousticDetectionFacts,
    AcousticQueueDiagnostics,
    AcousticRetentionSweepResult,
    ProductRepository,
)
from mockingbird.source_providers import media_provenance
from mockingbird.species.birdnet_adapter import BirdNetDetection, get_birdnet_status
from mockingbird.time_utils import utc_now

# ---------------------------------------------------------------------------
# Bounded resource limits (Phase D). Every constant below is a deliberate,
# disclosed default -- see each one's own docstring for the capacity
# calculation or structural fact backing it, never an arbitrary number.
# ---------------------------------------------------------------------------

#: Per-Stream intake cap on in-flight (`queued`+`processing`) segments,
#: checked BEFORE a raw segment is ever imported as a MediaAsset -- the
#: primary backpressure layer (a segment over this cap is deleted
#: unimported, counted, never silently accumulated). Bounded-capacity
#: justification: BirdNET analyzes roughly 23x faster than real time on CPU
#: (a real 35s field recording in ~1.5s, see docs/acoustic-birdnet-
#: observation-foundation-v1-contract.md "BirdNET runtime decision"). At the
#: default `DEFAULT_SEGMENT_SECONDS=15` live-capture segment length, one
#: segment arrives every 15s and takes well under 1s to analyze -- under
#: sustained realistic single-Stream load the queue never approaches this
#: bound; it only matters if analysis is genuinely wedged/unavailable for an
#: extended period. At capacity, this bounds unanalyzed backlog to at most
#: `DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_STREAM * 15s` ~= 25 minutes of audio
#: per Stream -- see `test_acoustic_runtime_backpressure.py` for the
#: calculation proven as a test, not just asserted in a comment.
DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_STREAM = 100

#: Global cap on `queued` (not yet claimed) rows across every Stream -- the
#: coarser, second backpressure layer (`ProductRepository.
#: enforce_acoustic_queue_capacity`), guarding against many Streams each
#: individually under their own per-Stream cap but collectively large.
DEFAULT_MAX_GLOBAL_QUEUED = 500

#: How long a non-evidence (never produced a candidate) audio MediaAsset is
#: kept before the working-audio retention sweep deletes it (Phase E) --
#: long enough for an operator to notice/diagnose a failure pattern, short
#: enough that continuous unattended capture does not become an indefinite
#: audio recorder. Deliberately NOT gated behind the general
#: `automatic_cleanup_enabled` setting -- see `run_working_audio_retention_
#: sweep`'s own docstring for why.
DEFAULT_WORKING_AUDIO_TTL = timedelta(hours=48)

#: How often the retention sweep actually runs -- it is bounded/cheap but
#: still a table scan; no value in running it every tick when the TTL it
#: enforces is measured in hours.
DEFAULT_RETENTION_INTERVAL = timedelta(minutes=15)

#: In-process defensive staleness threshold: a `processing` row claimed by
#: *this* running process but stuck far longer than any real BirdNET
#: analysis should ever take (a wedged, not crashed, worker) is reclaimed.
#: Distinct from the unconditional startup reclaim (`stale_after=
#: timedelta(0)`), which handles the crash/restart case.
DEFAULT_STALE_CLAIM_THRESHOLD = timedelta(minutes=10)

#: Phase I consolidation gap: BirdNET's own fixed ~3s analysis window
#: (verified directly against the real bundled model -- see
#: `birdnet_adapter`'s module docstring), reused as a deterministic,
#: structurally-justified threshold rather than a value tuned from a small
#: corpus. Two same-species detections whose windows are no more than one
#: BirdNET window apart are treated as the same continuous vocal event.
ACOUSTIC_CONSOLIDATION_GAP = timedelta(seconds=3)

#: Default poll cadence for the background thread. Bounded and short enough
#: that a freshly queued segment is picked up promptly; the loop is a plain
#: `Event.wait`-based sleep (interruptible, mirrors `LocalStorageRetentionService`),
#: never a busy loop.
DEFAULT_POLL_INTERVAL_SECONDS = 2.0

DEFAULT_PIPELINE_VERSION = acoustic_ingest.DEFAULT_PIPELINE_VERSION


# ---------------------------------------------------------------------------
# Bounded, timestamped segment source (Phase B: "explicit Source identity" +
# "deterministic test provider").
# ---------------------------------------------------------------------------


class SegmentSource(Protocol):
    """A bounded, timestamped source of finalized audio segments. Every
    `CapturedSegment.path` this yields is considered owned by the caller
    once returned -- `AcousticRuntimeService` deletes it after copying it
    into the managed media root (or after dropping it for capacity), so an
    implementation must never hand back a path it needs to keep (see
    `FixtureSegmentSource`, which copies a shared fixture file into a
    disposable per-segment location before returning it, precisely to
    satisfy this contract without risking a real, committed test fixture)."""

    def active_stream_ids(self) -> list[str]:
        """Every Stream identity this source currently has activity for.
        `MicrophoneSegmentSource` reflects real running capture sessions;
        `FixtureSegmentSource` reflects its own fixed scripted plan."""
        ...  # noqa: D102 - Protocol

    def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
        """Every segment that has newly finalized/arrived for this Stream
        since the last call. Never blocks; never returns a segment already
        returned before."""
        ...  # noqa: D102 - Protocol


class MicrophoneSegmentSource:
    """Adapts the real, already-accepted `MicrophoneSessionManager` to the
    `SegmentSource` protocol -- production use, real hardware capture."""

    def __init__(self, session_manager: MicrophoneSessionManager) -> None:
        self._session_manager = session_manager

    def active_stream_ids(self) -> list[str]:
        return self._session_manager.running_stream_ids()

    def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
        return self._session_manager.poll_new_finalized_segments_with_timing(stream_id)


@dataclass(frozen=True)
class FixtureSegmentPlan:
    """One scripted segment a `FixtureSegmentSource` will eventually
    deliver: an existing, real, bounded audio fixture file, presented as if
    it were a real capture segment starting at `started_at` on
    `stream_id`."""

    stream_id: str
    fixture_path: Path
    started_at: datetime
    duration: timedelta


class FixtureSegmentSource:
    """Deterministic, hardware-free stand-in for a microphone (Phase B/K).
    Behaves like microphone-produced segments without any real capture,
    real waiting, or real elapsed time: `advance_to(now)` is the only thing
    that makes new segments "arrive" (whichever scripted segments have
    `started_at <= now` and were not already delivered), driven explicitly
    by a test/acceptance harness rather than a real clock.

    Every delivered segment still points at a real, on-disk (fixture) audio
    file -- BirdNET runs for real against real bytes when the caller does
    not inject a fake `recording`; only the *arrival timing* is simulated.
    Each fixture is copied into `working_directory` before being handed out
    (never the original committed fixture path), satisfying `SegmentSource`'s
    "the caller may delete what it returns" contract without ever touching
    a real, git-tracked corpus file."""

    def __init__(
        self, plan: Iterable[FixtureSegmentPlan], *, working_directory: Path,
    ) -> None:
        self._plan = sorted(plan, key=lambda item: item.started_at)
        self._working_directory = working_directory
        self._working_directory.mkdir(parents=True, exist_ok=True)
        self._delivered_indices: set[int] = set()
        self._now: datetime | None = None

    def advance_to(self, now: datetime) -> None:
        self._now = now

    def active_stream_ids(self) -> list[str]:
        return sorted({item.stream_id for item in self._plan})

    def poll_new_segments(self, stream_id: str) -> list[CapturedSegment]:
        if self._now is None:
            return []
        due: list[CapturedSegment] = []
        for index, item in enumerate(self._plan):
            if item.stream_id != stream_id or index in self._delivered_indices:
                continue
            if item.started_at > self._now:
                continue
            self._delivered_indices.add(index)
            disposable_path = self._working_directory / f"segment-{index:08d}-{item.fixture_path.name}"
            disposable_path.write_bytes(item.fixture_path.read_bytes())
            due.append(
                CapturedSegment(
                    path=disposable_path,
                    sequence_index=index,
                    started_at=item.started_at,
                    ended_at=item.started_at + item.duration,
                )
            )
        return due

    @property
    def pending_count(self) -> int:
        """How many scripted segments have not yet become due -- lets an
        acceptance driver know when it is safe to stop advancing time."""

        return len(self._plan) - len(self._delivered_indices)


# ---------------------------------------------------------------------------
# Diagnostics (Phase J). Counters are process-local/in-memory (reset on
# restart, exactly like `_EngineSession._evidence_harvest_misses`) --
# anything durable (queue depth, oldest pending age, recent failures) comes
# straight from `ProductRepository.acoustic_analysis_queue_diagnostics`
# instead, never duplicated here.
# ---------------------------------------------------------------------------


@dataclass
class AcousticRuntimeCounters:
    """Bounded, process-local diagnostic counters -- never raw audio, never
    high-cardinality (no per-segment identifiers), just bounded totals."""

    segments_received: int = 0
    segments_imported: int = 0
    segments_dropped_capacity: int = 0
    segments_dropped_unreadable: int = 0
    segments_already_in_flight: int = 0
    analyses_completed: int = 0
    analyses_with_detections: int = 0
    analyses_requeued: int = 0
    analyses_failed_terminal: int = 0
    candidates_created: int = 0
    candidates_extended: int = 0
    stale_claims_reclaimed: int = 0
    queue_capacity_evicted: int = 0
    retention_deleted: int = 0
    retention_failures: int = 0


@dataclass(frozen=True)
class AcousticRuntimeStatus:
    """One bounded, JSON-friendly snapshot combining in-memory counters with
    durable queue diagnostics -- what Doctor and any future status route
    expose. See Phase J's own bounded-information list."""

    counters: AcousticRuntimeCounters
    queue: AcousticQueueDiagnostics
    birdnet_runtime_available: bool
    active_stream_count: int


# ---------------------------------------------------------------------------
# The reconcile loop itself.
# ---------------------------------------------------------------------------


class AcousticRuntimeService:
    """Bounded reconcile loop: ingest -> enforce capacity -> reclaim stale
    work -> process one queued item -> (periodically) retention.

    Every step below is a plain, synchronous, individually-callable method
    with no internal sleeping -- `_run`'s background thread is a thin
    wrapper around `tick()`; tests and Phase K's simulated acceptance call
    these same methods directly with an injected clock/segment source/
    analyzer/recording, mirroring `DurableMonitoringSupervisor.
    reconcile_once`'s established "the loop and lifecycle tests both call
    this" convention exactly."""

    def __init__(
        self,
        *,
        repository: ProductRepository,
        segment_source: SegmentSource,
        pipeline_version: str = DEFAULT_PIPELINE_VERSION,
        min_confidence: float | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        max_in_flight_per_stream: int = DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_STREAM,
        max_global_queued: int = DEFAULT_MAX_GLOBAL_QUEUED,
        working_audio_ttl: timedelta = DEFAULT_WORKING_AUDIO_TTL,
        retention_interval: timedelta = DEFAULT_RETENTION_INTERVAL,
        stale_claim_threshold: timedelta = DEFAULT_STALE_CLAIM_THRESHOLD,
        consolidation_gap: timedelta = ACOUSTIC_CONSOLIDATION_GAP,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        clock: Callable[[], datetime] = utc_now,
        analyzer: Any | None = None,
        recording: Any | None = None,
        ffmpeg_binary: str = "ffmpeg",
    ) -> None:
        self._repository = repository
        self._segment_source = segment_source
        self._pipeline_version = pipeline_version
        self._min_confidence = min_confidence
        self._latitude = latitude
        self._longitude = longitude
        self._max_in_flight_per_stream = max_in_flight_per_stream
        self._max_global_queued = max_global_queued
        self._working_audio_ttl = working_audio_ttl
        self._retention_interval = retention_interval
        self._stale_claim_threshold = stale_claim_threshold
        self._consolidation_gap = consolidation_gap
        self._poll_interval_seconds = max(0.5, poll_interval_seconds)
        self._clock = clock
        self._analyzer = analyzer
        self._recording = recording
        self._ffmpeg_binary = ffmpeg_binary

        self._worker_id = uuid.uuid4().hex
        self._counters = AcousticRuntimeCounters()
        self._counters_lock = threading.Lock()
        self._reconcile_lock = threading.RLock()
        #: Single-flight guard for `tick()` itself -- mirrors
        #: `LocalStorageRetentionService._run_lock`'s identical
        #: `acquire(blocking=False)` shape (found missing via review): a
        #: caller invoking `tick()` (or a sub-step) directly while the
        #: background thread is also mid-tick could otherwise let two
        #: ingest passes interleave (the per-Stream intake cap is
        #: check-then-act, and `MicrophoneCaptureSession._known_segments`
        #: is a bare `set` mutated without its own lock).
        self._tick_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False
        self._last_retention_at: datetime | None = None

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        """Start the background loop. Idempotent (a second call while
        already running is a no-op, mirroring `DurableMonitoringSupervisor.
        start`'s identical guard). The very first `start()` for this process
        also performs the unconditional restart-recovery reclaim (Phase C)
        before the loop begins -- a fresh process cannot have legitimately
        claimed any row still `processing` in the database, so every such
        row is a crash leftover, mirroring `prepare_for_supervision`'s
        identical "any nonterminal state is a crash leftover" reasoning."""

        with self._reconcile_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            if not self._started:
                self.reclaim_stale_work(stale_after=timedelta(0))
                self._started = True
            self._thread = threading.Thread(
                target=self._run, name="mockingbird-acoustic-runtime", daemon=True,
            )
            self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._reconcile_lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval_seconds):
            try:
                self.tick()
            except Exception as error:  # noqa: BLE001 - a bad tick must never kill the loop
                # Mirrors `LocalStorageRetentionService.run_once`'s identical
                # "maintenance failure must never interrupt the rest of the
                # app" discipline -- logged, not silently swallowed.
                log_error_event(
                    "acoustic_runtime", "acoustic_runtime_tick_failed",
                    code="acoustic_runtime_tick_failed", exception=error,
                )
                continue

    # -- one full bounded pass ----------------------------------------------

    def tick(self, *, now: datetime | None = None) -> bool:
        """One full bounded reconcile pass. Safe to call directly (tests,
        Phase K acceptance simulation) or from the background loop.

        Single-flight (`_tick_lock.acquire(blocking=False)`): a call that
        arrives while another `tick()` is already running returns `False`
        immediately without doing anything, rather than letting two passes
        interleave -- mirrors `LocalStorageRetentionService.run_once`'s
        identical guard. Returns `True` if this call actually ran."""

        if not self._tick_lock.acquire(blocking=False):
            return False
        try:
            current = now or self._clock()
            self.ingest_available_segments(now=current)
            self.enforce_queue_capacity(now=current)
            self.reclaim_stale_work(stale_after=self._stale_claim_threshold, now=current)
            self.process_next_queued(now=current)
            self.run_retention(now=current)
            return True
        finally:
            self._tick_lock.release()

    # -- ingest ---------------------------------------------------------------

    def ingest_available_segments(self, *, now: datetime | None = None) -> int:
        """Drain every active Stream's segment source, importing each new
        segment as a MediaAsset and enqueueing it for analysis, subject to
        the per-Stream intake cap. Returns the count successfully
        imported+enqueued.

        Each segment is isolated in its own try/except (found via review):
        `poll_new_segments` marks every segment it returns as delivered
        (never returned again), so one segment raising mid-loop -- a full
        disk, a permissions error, any unexpected exception in `_ingest_
        one_segment` -- must not silently discard every sibling segment
        already polled behind it in the same call, nor skip the rest of
        this tick's own later steps (capacity enforcement, stale-work
        reclaim, analysis, retention) by propagating out of this method
        entirely."""

        current = now or self._clock()
        imported = 0
        for stream_id in self._segment_source.active_stream_ids():
            for segment in self._segment_source.poll_new_segments(stream_id):
                try:
                    if self._ingest_one_segment(stream_id, segment, now=current):
                        imported += 1
                except Exception as error:  # noqa: BLE001 - one bad segment must not lose its siblings
                    log_error_event(
                        "acoustic_runtime", "acoustic_segment_ingest_failed",
                        code="acoustic_segment_ingest_failed", exception=error,
                        stream_id=stream_id,
                    )
        return imported

    def _ingest_one_segment(self, stream_id: str, segment: CapturedSegment, *, now: datetime) -> bool:
        self._bump("segments_received")
        in_flight = self._repository.count_in_flight_acoustic_analysis(stream_id)
        if in_flight >= self._max_in_flight_per_stream:
            self._bump("segments_dropped_capacity")
            self._delete_raw_segment_file(segment)
            log_event(
                "acoustic_runtime", "acoustic_segment_dropped_capacity",
                stream_id=stream_id, in_flight=in_flight,
                max_in_flight=self._max_in_flight_per_stream,
            )
            return False

        probe = media_provenance.probe_audio_metadata(segment.path)
        try:
            file_size_bytes = segment.path.stat().st_size
        except OSError:
            file_size_bytes = 0
        if probe is None or file_size_bytes <= 0:
            self._bump("segments_dropped_unreadable")
            self._delete_raw_segment_file(segment)
            log_error_event(
                "acoustic_runtime", "acoustic_segment_unreadable",
                code="acoustic_segment_probe_failed", stream_id=stream_id,
            )
            return False

        media_asset = self._repository.create_audio_segment_media_asset(
            stream_id=stream_id,
            source_path=segment.path,
            original_filename=segment.path.name,
            captured_at=segment.started_at,
            sample_rate_hz=probe.sample_rate_hz,
            channel_count=probe.channel_count,
            file_size_bytes=file_size_bytes,
            now=now,
        )
        # The managed media root now holds its own copy -- the raw capture
        # file is redundant and, for a real microphone, must not accumulate
        # forever outside the MediaAsset system (see the module docstring's
        # "why this is a new small module" for the gap this closes).
        self._delete_raw_segment_file(segment)
        self._bump("segments_imported")

        _, outcome = self._repository.enqueue_acoustic_analysis(
            media_asset_id=media_asset.id, stream_id=stream_id,
            pipeline_version=self._pipeline_version,
            min_confidence=self._resolved_min_confidence(), now=now,
        )
        if outcome == "already_in_flight":  # pragma: no cover - benign race, not normally reachable
            self._bump("segments_already_in_flight")
        return True

    def _resolved_min_confidence(self) -> float:
        # Acoustic Productization, Licensing & Field Acceptance v1: honor
        # MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE via `resolve_birdnet_config`
        # when this service was constructed with no explicit override --
        # previously fell back to the hardcoded dataclass default, making
        # the documented env var dead code for the automatic runtime.
        from mockingbird.species.birdnet_adapter import resolve_birdnet_config

        return (
            self._min_confidence if self._min_confidence is not None
            else resolve_birdnet_config().min_confidence
        )

    def _delete_raw_segment_file(self, segment: CapturedSegment) -> None:
        try:
            segment.path.unlink(missing_ok=True)
        except OSError as error:  # pragma: no cover - best-effort only
            log_error_event(
                "acoustic_runtime", "acoustic_raw_segment_cleanup_failed",
                code="acoustic_raw_segment_cleanup_failed", exception=error,
            )

    # -- backpressure ---------------------------------------------------------

    def enforce_queue_capacity(self, *, now: datetime | None = None) -> list[str]:
        current = now or self._clock()
        evicted = self._repository.enforce_acoustic_queue_capacity(
            max_queued=self._max_global_queued, now=current,
        )
        if evicted:
            self._bump_by("queue_capacity_evicted", len(evicted))
            log_event(
                "acoustic_runtime", "acoustic_queue_capacity_evicted",
                evicted_count=len(evicted),
            )
        return evicted

    # -- restart/stall recovery -------------------------------------------

    def reclaim_stale_work(self, *, stale_after: timedelta, now: datetime | None = None) -> int:
        current = now or self._clock()
        count = self._repository.reclaim_stale_acoustic_analysis_work(
            now=current, stale_after=stale_after,
        )
        if count:
            self._bump_by("stale_claims_reclaimed", count)
            log_event("acoustic_runtime", "acoustic_stale_work_reclaimed", count=count)
        return count

    # -- analysis ---------------------------------------------------------

    def process_next_queued(self, *, now: datetime | None = None) -> acoustic_ingest.AcousticIngestResult | None:
        """Claim and fully process at most one queued segment this tick --
        bounded per-tick work. Returns the `AcousticIngestResult`, or `None`
        if nothing was queued/eligible right now (a legitimate, common
        outcome, never an error)."""

        current = now or self._clock()
        run = self._repository.claim_next_queued_acoustic_analysis(
            now=current, claimed_by=self._worker_id,
        )
        if run is None:
            return None
        result = acoustic_ingest.execute_queued_acoustic_analysis(
            self._repository, run=run, latitude=self._latitude, longitude=self._longitude,
            ffmpeg_binary=self._ffmpeg_binary, now=current, analyzer=self._analyzer,
            recording=self._recording,
            admit_detection=self._consolidating_admit(run.stream_id, run.media_asset_id),
        )
        if result.status == "completed":
            self._bump("analyses_completed")
            if result.detections_above_threshold > 0:
                self._bump("analyses_with_detections")
        elif result.status == "requeued":
            self._bump("analyses_requeued")
        elif result.status == "failed":
            self._bump("analyses_failed_terminal")
        return result

    def _consolidating_admit(self, stream_id: str, media_asset_id: str) -> acoustic_ingest.AdmitDetection:
        """Phase I: cross-segment consolidation. Tries to extend an existing
        still-`needs_review` acoustic candidate for the same `(stream_id,
        species)` whose window ended within `ACOUSTIC_CONSOLIDATION_GAP` of
        this detection's start; falls back to an ordinary new candidate if
        nothing matched, or if the matched Visit turned out to no longer be
        extendable (reviewed/superseded since the lookup)."""

        def _admit(
            detection: BirdNetDetection, observed_at: datetime,
            model_provenance: dict[str, Any], adapter_id: str, adapter_name: str,
        ) -> AcousticCandidateVisitOutcome:
            facts = AcousticDetectionFacts(
                common_name=detection.common_name,
                scientific_name=detection.scientific_name,
                confidence=detection.confidence,
                window_start_ms=detection.start_ms,
                window_end_ms=detection.end_ms,
            )
            species_guess = self._repository.resolve_acoustic_species_guess(detection.common_name)
            match = self._repository.find_extendable_acoustic_candidate(
                stream_id=stream_id, species_guess=species_guess,
                detection_start_at=observed_at, gap=self._consolidation_gap,
            )
            if match is not None:
                visit_id, event_id = match
                extend_outcome = self._repository.extend_acoustic_candidate_visit(
                    visit_id=visit_id, event_id=event_id, stream_id=stream_id,
                    media_asset_id=media_asset_id, detection=facts,
                    model_provenance=model_provenance, observed_at=observed_at,
                    adapter_id=adapter_id, adapter_name=adapter_name,
                )
                if extend_outcome.outcome != "not_extendable":
                    if extend_outcome.outcome == "extended":
                        self._bump("candidates_extended")
                    return extend_outcome
                # Fell out of eligibility (reviewed/superseded) between the
                # lookup above and this call -- fall back to a fresh
                # candidate rather than losing the detection.

            create_outcome = self._repository.create_acoustic_candidate_visit(
                stream_id=stream_id, media_asset_id=media_asset_id, detection=facts,
                model_provenance=model_provenance, observed_at=observed_at,
                adapter_id=adapter_id, adapter_name=adapter_name,
            )
            if create_outcome.outcome == "created":
                self._bump("candidates_created")
            return create_outcome

        return _admit

    # -- retention ----------------------------------------------------------

    def run_retention(self, *, now: datetime | None = None, force: bool = False) -> AcousticRetentionSweepResult | None:
        """Cadence-gated (Phase D/E): the sweep itself is bounded/cheap, but
        the TTL it enforces is measured in hours, so it does not need to run
        every tick. `force=True` (tests, Phase K acceptance) bypasses the
        cadence gate."""

        current = now or self._clock()
        if not force and self._last_retention_at is not None:
            if current - self._last_retention_at < self._retention_interval:
                return None
        self._last_retention_at = current
        older_than = current - self._working_audio_ttl
        result = self._repository.run_working_audio_retention_sweep(older_than=older_than)
        if result.deleted_count:
            self._bump_by("retention_deleted", result.deleted_count)
        if result.failed_count:
            self._bump_by("retention_failures", result.failed_count)
        return result

    # -- diagnostics (Phase J) -----------------------------------------------

    def status(self, *, now: datetime | None = None) -> AcousticRuntimeStatus:
        current = now or self._clock()
        queue = self._repository.acoustic_analysis_queue_diagnostics(current)
        with self._counters_lock:
            counters = replace(self._counters)
        return AcousticRuntimeStatus(
            counters=counters,
            queue=queue,
            birdnet_runtime_available=get_birdnet_status().runtime_available,
            active_stream_count=len(self._segment_source.active_stream_ids()),
        )

    def _bump(self, field_name: str) -> None:
        self._bump_by(field_name, 1)

    def _bump_by(self, field_name: str, amount: int) -> None:
        with self._counters_lock:
            setattr(self._counters, field_name, getattr(self._counters, field_name) + amount)


__all__ = [
    "ACOUSTIC_CONSOLIDATION_GAP",
    "DEFAULT_MAX_GLOBAL_QUEUED",
    "DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_STREAM",
    "DEFAULT_PIPELINE_VERSION",
    "DEFAULT_POLL_INTERVAL_SECONDS",
    "DEFAULT_RETENTION_INTERVAL",
    "DEFAULT_STALE_CLAIM_THRESHOLD",
    "DEFAULT_WORKING_AUDIO_TTL",
    "AcousticRuntimeCounters",
    "AcousticRuntimeService",
    "AcousticRuntimeStatus",
    "FixtureSegmentPlan",
    "FixtureSegmentSource",
    "MicrophoneSegmentSource",
    "SegmentSource",
]
