"""24/7 Field Reliability Corrections v1: automatic Camera Node observation
resume after a `camera_unavailable` stop.

Field evidence: the reference Camera Node suffered a real network-level
outage. `engine_runtime._EngineSession`'s own bounded `AnalysisStreamRetryPolicy`
correctly retried, then correctly gave up and ended the session with
`stopped_reason="camera_unavailable"` -- exactly its documented, intended
behavior for a genuinely persistent interruption. The Host stayed healthy
throughout, but observation never resumed on its own once the Node came
back, because nothing in the product ever called `ObservationEngineSession
Manager.start()` again. Requiring a person to notice and click "Start
observing" again is incompatible with an unattended 24/7 deployment.

This module is the missing supervision layer *above* one `_EngineSession`'s
own lifecycle -- it never touches `AnalysisStreamRetryPolicy` or anything
inside a still-running session. It notices a session that has already
ended with `stopped_reason == "camera_unavailable"` (the whole
`_EngineSession` object is gone; camera ownership already released),
periodically re-probes that Node's own unauthenticated `/node/v1/health`,
and once it responds, calls `ObservationEngineSessionManager.start()` again
-- exactly as if a user had pressed Start observing, reusing a fresh,
repository-sourced `StreamLivePlaybackConfig` so a source reconfigured
while the Node was down is picked up automatically, never a rebuild.

Recovery eligibility is deliberately an allow-list of the one stop reason
this module ever acts on (`_RECOVERABLE_STOPPED_REASONS`), not a deny-list:
`user_stopped` (a person pressed Stop), `app_shutdown` (the whole product is
tearing down), and any other/future `stopped_reason` this module has never
seen are all safely excluded by default, never auto-resumed.

Native-Windows Field Reliability Corrections v1 -- Host-restart recovery.
A second eligibility class was added above, because the first one is
structurally blind to it: `session_manager.status()` reads the manager's own
**in-memory** `_sessions` dict, so a Camera Node outage (which leaves that
object behind, stopped, with `stopped_reason="camera_unavailable"`) is
visible to this module, while a **Host** restart -- which destroys the whole
process -- makes `status()` return `None` for every Stream and therefore
matches nothing at all. Real field evidence: with the Node healthy and
reachable throughout a graceful Host restart, the previously-observing Stream
came back `state=stopped` and stayed stopped until a person pressed Start
observing again (docs/field-validation-closure-v1-report.md Q-3) -- fatal for
an unattended 24/7 deployment on a platform that reboots itself for updates.

The fix is deliberately *not* a new mechanism: the resume path here already
worked. What was missing was a durable answer to "is this Stream supposed to
be observing?", now `ProductRepository.record_stream_observation_intent` /
`streams_intended_observing` (schema 61). This module reads that intent and
resumes a Stream with **no in-process session at all** whose intent is
`observing`, then falls through to the identical probe/backoff/start path
below. Because the record is durable rather than a clean-shutdown callback,
an abrupt process or OS kill recovers through the very same route -- and an
observation a person deliberately stopped has intent `stopped`, so it stays
stopped across any number of restarts. An absent intent row is never read as
`observing`: this must never become "start every Camera Node on boot." See
docs/native-windows-field-reliability-corrections-v1-contract.md.

Mirrors `monitoring.durable_supervisor.DurableMonitoringSupervisor`'s
proven bounded-backoff/reconcile-loop shape (repository-sourced desired
state, a `reconcile_once` pass that is unit-testable independent of the
background thread, `wake()`/`shutdown()`) without touching that class, its
`StreamMonitoringPolicy`-shaped store protocol, or the legacy
`live_monitoring` lane at all: see docs/runtime-map.md -- the legacy lane
and the Camera Node engine lane are structurally different runtimes, and
forcing them through one shared abstraction would be a materially larger,
riskier change than this milestone's own "smallest coherent fix" charge
allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import threading
from typing import Callable, Protocol

from mockingbird.api.schemas import SourceStatus
from mockingbird.diagnostics.structured_log import log_event
from mockingbird.observation.engine_runtime import ObservationEngineSessionManager, ObservationEngineSessionStatus
from mockingbird.observation.unified_status import RUNTIME_KIND_CAMERA_NODE, resolve_observation_runtime
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig
from mockingbird.source_providers.camera_node import CameraNodeClientError
from mockingbird.time_utils import utc_now

logger = logging.getLogger(__name__)

# The one stop reason this supervisor ever acts on -- see module docstring
# "Recovery eligibility." A `frozenset` (not a single string compared
# directly) so a future, genuinely-equivalent reason can be added without
# restructuring every comparison site.
_RECOVERABLE_STOPPED_REASONS = frozenset({"camera_unavailable"})

DEFAULT_POLL_INTERVAL_SECONDS = 30.0
# Bounded, capped-and-repeating backoff: a real outage duration is unknown
# in advance (the reference Node in this milestone's own field evidence
# never returned for the rest of a multi-day run) -- unlike `AnalysisStream
# RetryPolicy` (which bounds retries *while a session still holds camera
# ownership* and correctly gives up after a bounded budget), this
# supervisor acts only after that ownership has already been fully
# released, so there is no resource cost to retrying indefinitely. Capping
# at the last value (rather than ever stopping) keeps "repeated disconnect
# /reconnect cycles must remain bounded" satisfied as a bounded *rate*,
# never a bounded *count* that would silently stop trying to recover.
DEFAULT_BACKOFF_SCHEDULE_SECONDS: tuple[float, ...] = (30.0, 60.0, 120.0, 300.0, 600.0)


@dataclass
class _RecoveryBookkeeping:
    consecutive_attempts: int = 0
    next_attempt_at: datetime | None = None
    last_seen_stopped_at: datetime | None = None


@dataclass(frozen=True)
class _RecoveryCandidate:
    stream_id: str
    config: StreamLivePlaybackConfig
    # `None` for a Host-restart candidate: this process has no session object
    # for the Stream at all, which is precisely what identifies it. Backoff
    # bookkeeping keys off `stopped_at`, so such a candidate carries the
    # durable intent's own `requested_at` as its stable stop identity instead
    # (see `_maybe_recover`).
    session_status: ObservationEngineSessionStatus | None
    stop_identity: datetime | None


class _HealthProbe(Protocol):
    def health(self, base_address: str) -> dict[str, object]: ...


class CameraNodeRecoverySupervisor:
    """Background, bounded reconciliation loop that periodically re-probes a
    Camera Node's own health and calls `ObservationEngineSessionManager
    .start()` again once it responds, with no user action -- for a Camera Node
    Stream in either of two states (see `_eligible_candidates`):

    - its most recent in-process Observation Engine session ended with
      `stopped_reason == "camera_unavailable"` (the camera went away while the
      Host kept running), or
    - this process has **no** session for it at all while its durable
      observation intent is `observing` (the Host itself restarted, cleanly or
      abruptly, while the user's standing intent was to observe).

    Together these restore both "MockingBird resumes watching once its camera
    comes back" and "MockingBird resumes watching after its own Host reboots."

    Each background session already opens its own dedicated
    `ProductRepository` (see `ObservationEngineSessionManager`'s own
    docstring); this supervisor does the same via `repository_factory`,
    opening and closing a fresh repository each reconcile pass rather than
    holding one open for the lifetime of the process.
    """

    def __init__(
        self,
        *,
        session_manager: ObservationEngineSessionManager,
        repository_factory: Callable[[], ProductRepository],
        camera_node_client: _HealthProbe,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        backoff_schedule_seconds: tuple[float, ...] = DEFAULT_BACKOFF_SCHEDULE_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds_must_be_positive")
        if not backoff_schedule_seconds or any(value < 0 for value in backoff_schedule_seconds):
            raise ValueError("invalid_backoff_schedule")
        self._session_manager = session_manager
        self._repository_factory = repository_factory
        self._camera_node_client = camera_node_client
        self._poll_interval_seconds = poll_interval_seconds
        self._backoff_schedule_seconds = backoff_schedule_seconds
        self._clock = clock or utc_now
        self._lock = threading.RLock()
        self._bookkeeping: dict[str, _RecoveryBookkeeping] = {}
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start exactly one background loop. Idempotent: calling this
        again while already running is a safe no-op, mirroring
        `DurableMonitoringSupervisor.start()`."""

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run, name="mockingbird-camera-node-recovery", daemon=True,
            )
            self._thread.start()

    def wake(self) -> None:
        """Request a prompt reconciliation pass sooner than the next poll."""

        self._wake_event.set()

    def shutdown(self) -> None:
        """Quiesce the background loop. Never calls into the session
        manager itself -- a caller tearing down the app already stops every
        session directly (`ObservationEngineSessionManager.stop_all`); this
        only ensures no further *auto-resume* attempt can start once
        shutdown has begun, matching "shutdown remains respected."""

        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=3)
        with self._lock:
            self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.reconcile_once()
            except Exception:  # pragma: no cover - defensive: never crash the app process
                logger.exception("camera_node_recovery_reconcile_failed")
            self._wake_event.wait(timeout=self._poll_interval_seconds)
            self._wake_event.clear()

    def reconcile_once(self, *, now: datetime | None = None) -> None:
        """One deterministic pass: used by the background loop and directly
        by tests. Side effects (a health probe, an `ObservationEngineSession
        Manager.start()` call) only ever happen for a Stream currently
        eligible -- see `_eligible_candidates`."""

        if self._stop_event.is_set():
            return
        current_time = now or self._clock()
        repository = self._repository_factory()
        try:
            candidates = self._eligible_candidates(repository)
        finally:
            repository.close()

        current_ids = {candidate.stream_id for candidate in candidates}
        with self._lock:
            for stream_id in set(self._bookkeeping) - current_ids:
                # No longer a `camera_unavailable`-stopped Camera Node
                # Stream this pass (manually restarted, stopped, deleted,
                # or reconfigured away from Camera Node) -- never keep
                # stale backoff state for it.
                self._bookkeeping.pop(stream_id, None)

        for candidate in candidates:
            try:
                self._maybe_recover(candidate, now=current_time)
            except Exception:  # pragma: no cover - defensive: one Stream's failure must not stop the pass
                logger.exception("camera_node_recovery_attempt_failed", extra={"stream_id": candidate.stream_id})

    def _eligible_candidates(self, repository: ProductRepository) -> list[_RecoveryCandidate]:
        """Two eligibility classes, checked per Stream in this order:

        1. **In-process `camera_unavailable` stop** -- the original class. A
           session object exists, it ended, and its `stopped_reason` is on the
           allow-list. This is a Camera Node outage inside a still-running
           Host.
        2. **No in-process session at all, with durable intent `observing`** --
           Host-restart recovery (Native-Windows Field Reliability Corrections
           v1). `status() is None` is exactly what a fresh process sees for a
           Stream that was observing before it restarted, and the durable
           intent is the only thing that can say whether it *should* still be.

        A Stream whose session object exists but stopped for any other reason
        -- `user_stopped`, `app_shutdown`, a hard `error` -- matches neither
        class and is never resumed, unchanged from before. Class 2
        deliberately requires the intent to be *present and* `observing`: an
        absent row means nobody ever asked this Stream to observe.
        """

        intended_observing = frozenset(repository.streams_intended_observing())
        candidates: list[_RecoveryCandidate] = []
        for stream in repository.list_streams():
            status = self._session_manager.status(stream.id)
            stop_identity: datetime | None
            if status is None:
                if stream.id not in intended_observing:
                    continue
                intent = repository.get_stream_observation_intent(stream.id)
                if intent is None or not intent.observing_intended:
                    # Raced away between the set query and this read (a Stop
                    # landing mid-pass). Never resume on a stale snapshot.
                    continue
                # Stable per-intent identity for backoff bookkeeping, in
                # place of a `stopped_at` this class has no session to read.
                # It changes only when the user's intent itself changes, so
                # repeated failed resume attempts keep backing off instead of
                # resetting every pass.
                stop_identity = intent.requested_at
            elif (
                status.state != "stopped"
                or status.stopped_reason not in _RECOVERABLE_STOPPED_REASONS
            ):
                continue
            else:
                stop_identity = status.stopped_at
            config = repository.get_stream_live_playback_config(stream.id)
            if config is None or resolve_observation_runtime(config) != RUNTIME_KIND_CAMERA_NODE:
                continue
            if not config.camera_node_base_address:
                # Nothing to probe -- an incompletely-paired Stream can
                # never have reached `camera_unavailable` in the first
                # place (`_run_async`'s own pairing guard reports a
                # different, non-recoverable `error` state instead), but
                # this stays a safe, explicit no-op rather than an
                # assumption. It is also the right answer for a
                # Host-restart candidate whose pairing was removed while
                # the Host was down.
                continue
            source = repository.get_source(config.source_id)
            if source is None or source.status == SourceStatus.archived:
                continue
            candidates.append(
                _RecoveryCandidate(
                    stream_id=stream.id,
                    config=config,
                    session_status=status,
                    stop_identity=stop_identity,
                )
            )
        return candidates

    def _maybe_recover(self, candidate: _RecoveryCandidate, *, now: datetime) -> None:
        with self._lock:
            bookkeeping = self._bookkeeping.setdefault(candidate.stream_id, _RecoveryBookkeeping())
            stopped_at = candidate.stop_identity
            if bookkeeping.last_seen_stopped_at != stopped_at:
                # A new stop event since we last looked (either the very
                # first sighting, or a resumed session that failed again) --
                # reset backoff progression. Never on every pass: that would
                # defeat backoff entirely.
                bookkeeping.last_seen_stopped_at = stopped_at
                bookkeeping.consecutive_attempts = 0
                bookkeeping.next_attempt_at = now
            if bookkeeping.next_attempt_at is None or now < bookkeeping.next_attempt_at:
                return

        healthy = self._probe_health(candidate.config)
        if not healthy:
            with self._lock:
                index = min(bookkeeping.consecutive_attempts, len(self._backoff_schedule_seconds) - 1)
                bookkeeping.consecutive_attempts += 1
                bookkeeping.next_attempt_at = now + timedelta(seconds=self._backoff_schedule_seconds[index])
            return

        # Final, cheap, in-memory re-check immediately before starting:
        # narrows the window in which a user's own just-issued Stop (which
        # only ever no-ops against the stale, already-stopped session
        # object until this call replaces it) could otherwise be raced by
        # this recovery attempt. "user-intentional stop remains stopped and
        # is NOT auto-resumed" holds regardless of probe latency.
        latest_status = self._session_manager.status(candidate.stream_id)
        if candidate.session_status is None:
            # Host-restart class: eligibility was "no session object exists."
            # If one now does, something else (a user pressing Start, or an
            # earlier resume in this same process) already started it, so this
            # attempt must stand down rather than race it. The durable intent
            # is re-read too, so a Stop issued during the probe wins.
            if latest_status is not None:
                with self._lock:
                    self._bookkeeping.pop(candidate.stream_id, None)
                return
            repository = self._repository_factory()
            try:
                intent = repository.get_stream_observation_intent(candidate.stream_id)
            finally:
                repository.close()
            if intent is None or not intent.observing_intended:
                with self._lock:
                    self._bookkeeping.pop(candidate.stream_id, None)
                return
        elif (
            latest_status is None
            or latest_status.state != "stopped"
            or latest_status.stopped_reason not in _RECOVERABLE_STOPPED_REASONS
        ):
            with self._lock:
                self._bookkeeping.pop(candidate.stream_id, None)
            return

        repository = self._repository_factory()
        try:
            regions = repository.stream_privacy_ignore_regions(candidate.stream_id)
            fresh_config = repository.get_stream_live_playback_config(candidate.stream_id) or candidate.config
        finally:
            repository.close()
        log_event(
            "observation_engine",
            "camera_node_auto_resume_attempt",
            stream_id=candidate.stream_id,
            # Which of the two eligibility classes fired, so a field operator
            # reading the log can tell "the camera came back" apart from "the
            # Host restarted and we restored the user's standing intent."
            recovery_class=(
                "host_restart_intent" if candidate.session_status is None else "camera_unavailable"
            ),
        )
        self._session_manager.start(candidate.stream_id, fresh_config, privacy_ignore_regions=regions)
        with self._lock:
            # Whichever way the resumed session goes -- keeps observing, or
            # ends in `camera_unavailable` again -- is judged on the *next*
            # reconcile pass, which will see its own fresh `stopped_at`/
            # `stopped_reason` (or no longer see this stream at all, if it
            # is now observing). Bookkeeping for *this* stop event is done.
            self._bookkeeping.pop(candidate.stream_id, None)

    def _probe_health(self, config: StreamLivePlaybackConfig) -> bool:
        try:
            self._camera_node_client.health(config.camera_node_base_address)
        except CameraNodeClientError:
            return False
        return True
