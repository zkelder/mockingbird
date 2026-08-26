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
import threading

#: Fifteen minutes. Place Story/digest facts do not change meaningfully
#: faster than this in practice (the underlying regularity/change windows
#: are themselves multi-day), and every alert this produces is keyed by a
#: stable, content-derived `deduplication_key` -- a missed or delayed tick
#: is always safe to catch up on the next one, never a duplicate or a lost
#: notification (Phase 26: delivery idempotency).
DEFAULT_ATTENTION_SYNC_POLL_INTERVAL_SECONDS = 900.0


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
    ) -> None:
        self._run_sync = run_sync
        self._poll_interval_seconds = max(60.0, poll_interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()

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
            self._run_sync()
        except Exception:
            # Attention sync is optional local reconciliation. Its failure
            # must never stop healthy monitoring, review, or the API
            # process -- see the module docstring.
            return
        finally:
            self._run_lock.release()

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval_seconds):
            self.run_once()
