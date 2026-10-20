"""Bounded app-owned scheduling for Calm Attention & Notifications v1.

See docs/calm-attention-notifications-v1-report.md. This mirrors
`mockingbird.storage.retention_service.LocalStorageRetentionService`
exactly -- the established shape for "run this bounded, idempotent
reconciliation on a periodic interval" in this codebase (there is no
generic scheduler/cron component; see that report's "Daily / Weekly
Digest" archaeology) -- applied to
`ProductRepository.sync_attention_signals` instead of storage cleanup.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import sqlite3
import threading

from sqlalchemy.exc import SQLAlchemyError

from mockingbird.diagnostics.error_taxonomy import resolve_error
from mockingbird.diagnostics.structured_log import log_error_event

#: Fifteen minutes. Place Story/digest facts do not change meaningfully
#: faster than this in practice (the underlying regularity/change windows
#: are themselves multi-day), and every alert this produces is keyed by a
#: stable, content-derived `deduplication_key` -- a missed or delayed tick
#: is always safe to catch up on the next one, never a duplicate or a lost
#: notification (Phase 26: delivery idempotency).
DEFAULT_ATTENTION_SYNC_POLL_INTERVAL_SECONDS = 900.0


@dataclass(frozen=True)
class AttentionSyncDiagnostics:
    """Attention Integrity & Health Reliability v1: bounded, in-process facts
    about attention reconciliation, so a health surface can tell "there are
    no alerts" apart from "alert reconciliation is failing." Every field is
    a timestamp, a counter, or a registered error code with its registered
    safe message -- never raw exception text (only `last_error_type`, the
    exception class name, is kept for support). Counters are process-
    lifetime and reset on restart, like the service itself."""

    running: bool
    poll_interval_seconds: float
    last_attempt_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None
    last_error_type: str | None
    consecutive_failure_count: int
    success_count: int
    failure_count: int


def _attention_sync_error_code(error: BaseException) -> str:
    if isinstance(error, (SQLAlchemyError, sqlite3.Error)):
        return "attention_sync_database_error"
    return "attention_sync_failed"


class AttentionSyncService:
    """Run no more than one fresh attention-sync pass at a time.

    The repository remains the policy authority. This small lifecycle
    wrapper never creates a second computation path, never blocks
    Observation Engine start/stop, and never lets a sync failure surface
    as a user-facing error -- a missed sync just means attention state is
    briefly behind, exactly as if the app had been closed (Phase 27: a
    delivery-side failure must never affect the underlying product event
    or Observation Engine health).
    """

    def __init__(
        self,
        *,
        run_sync: Callable[[], None],
        poll_interval_seconds: float = DEFAULT_ATTENTION_SYNC_POLL_INTERVAL_SECONDS,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._run_sync = run_sync
        self._poll_interval_seconds = max(60.0, poll_interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._clock = clock or (lambda: datetime.now(UTC))
        self._diagnostics_lock = threading.Lock()
        self._last_attempt_at: datetime | None = None
        self._last_success_at: datetime | None = None
        self._last_failure_at: datetime | None = None
        self._last_error_code: str | None = None
        self._last_error_type: str | None = None
        self._consecutive_failure_count = 0
        self._success_count = 0
        self._failure_count = 0

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="mockingbird-attention-sync",
                daemon=True,
            )
            self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def run_once(self) -> None:
        """Perform a single safe-off-aware pass for tests and the app loop."""

        if not self._run_lock.acquire(blocking=False):
            return
        try:
            with self._diagnostics_lock:
                self._last_attempt_at = self._clock()
            try:
                self._run_sync()
            except Exception as error:
                # Attention sync is optional local reconciliation. Its
                # failure must never stop healthy monitoring, review, or the
                # API process -- see the module docstring -- but it must not
                # be silent either: record it for the health surface.
                code = _attention_sync_error_code(error)
                with self._diagnostics_lock:
                    self._last_failure_at = self._clock()
                    self._last_error_code = code
                    self._last_error_type = type(error).__name__
                    self._consecutive_failure_count += 1
                    self._failure_count += 1
                    consecutive = self._consecutive_failure_count
                log_error_event(
                    "attention", "sync_failed", code=code, exception=error,
                    consecutive_failure_count=consecutive,
                )
                return
            with self._diagnostics_lock:
                self._last_success_at = self._clock()
                self._consecutive_failure_count = 0
                self._success_count += 1
        finally:
            self._run_lock.release()

    def diagnostics(self) -> AttentionSyncDiagnostics:
        """Side-effect free snapshot. The last error code/message are kept
        after a later success (with `consecutive_failure_count` back at 0)
        so support can still see what last went wrong."""

        with self._lock:
            running = self._thread is not None and self._thread.is_alive()
        with self._diagnostics_lock:
            return AttentionSyncDiagnostics(
                running=running,
                poll_interval_seconds=self._poll_interval_seconds,
                last_attempt_at=self._last_attempt_at,
                last_success_at=self._last_success_at,
                last_failure_at=self._last_failure_at,
                last_error_code=self._last_error_code,
                last_error_message=(
                    resolve_error(self._last_error_code).message if self._last_error_code else None
                ),
                last_error_type=self._last_error_type,
                consecutive_failure_count=self._consecutive_failure_count,
                success_count=self._success_count,
                failure_count=self._failure_count,
            )

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval_seconds):
            self.run_once()
