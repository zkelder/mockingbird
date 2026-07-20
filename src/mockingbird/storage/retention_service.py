"""Bounded app-owned scheduling for optional local storage retention."""

from __future__ import annotations

from collections.abc import Callable
import threading


class LocalStorageRetentionService:
    """Run no more than one fresh local retention pass at a time.

    The repository remains the policy authority. This small lifecycle wrapper never
    constructs cameras, reuses browser previews, or lets cleanup failures interrupt
    Stream monitoring.
    """

    def __init__(
        self,
        *,
        run_maintenance: Callable[[], None],
        poll_interval_seconds: float = 60.0,
    ) -> None:
        self._run_maintenance = run_maintenance
        self._poll_interval_seconds = max(5.0, poll_interval_seconds)
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
                name="mockingbird-storage-retention",
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
            self._run_maintenance()
        except Exception:
            # Cleanup is optional local maintenance. Its failure must not stop
            # healthy monitoring, playback, or the API process.
            return
        finally:
            self._run_lock.release()

    def _run(self) -> None:
        while not self._stop_event.wait(self._poll_interval_seconds):
            self.run_once()
