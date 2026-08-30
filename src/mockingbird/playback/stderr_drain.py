"""Bounded, continuous stderr draining for long-running ffmpeg-based
playback processes (RTSP / local USB / Windows DirectShow ongoing
monitoring).

Ongoing Monitoring Failure Diagnostics v1: the long-running MJPEG bridge
processes these three providers start (`rtsp_bridge.start_rtsp_mjpeg_
process`/`local_camera_bridge.start_local_camera_mjpeg_process`/`windows_
camera_bridge.start_windows_dshow_mjpeg_process`) previously discarded
stderr entirely (`stderr=subprocess.DEVNULL`) so a real failure cause was
never available once monitoring had already started -- only the bounded
one-shot setup-time probe (`rtsp_bridge.probe_rtsp_stream`) ever captured
it. Simply switching those processes to `stderr=subprocess.PIPE` without
continuously draining the pipe would risk the well-known pipe-buffer
deadlock (the child blocks writing to a full, unread pipe; nothing else
in this process ever unblocks it). `BoundedStderrDrain` is the fix: one
dedicated daemon thread per monitored process, reading stderr continuously
so the child can never block on it, retaining only a small, bounded,
credential-safe tail for classification -- never a general logging
subsystem, never persisted to disk, discarded the moment the owning
session ends.

Lifecycle contract: one drain instance is owned by exactly one monitored
process's lifecycle. Create it alongside the process, call `.start()`
once, and call `.stop()` once that process has already been terminated/
killed (mirrors `_stop_process`'s existing terminate-then-kill discipline
-- an EOF on the pipe is what lets this thread's blocking read return and
the thread exit; `.stop()` itself does not interrupt a blocking read, it
only bounds how long it waits for the thread to notice EOF on its own).
`.stop()` is idempotent and safe to call more than once.
"""

from __future__ import annotations

import threading
from typing import BinaryIO

from mockingbird.playback.rtsp_bridge import redact_credentials_in_text

#: Matches `_PROBE_MAX_STDERR_BYTES` (the bounded one-shot setup probe) so
#: ongoing monitoring never retains more raw diagnostic text than setup
#: validation already does.
DEFAULT_DRAIN_CHUNK_BYTES = 4096
DEFAULT_DRAIN_MAX_RETAINED_BYTES = 4096

_DRAIN_THREAD_NAME = "mockingbird-stderr-drain"


class BoundedStderrDrain:
    """Continuously drains one child process's stderr pipe on a dedicated
    daemon thread, retaining only a bounded, redacted tail of the most
    recent output.

    Never blocks the child: the drain thread's own blocking `read()` calls
    happen off the frame-decode path entirely, on a thread whose only job
    is to keep the pipe empty. Bounded memory: retained text is capped at
    `max_retained_bytes`, trimmed from the front (oldest first) on every
    chunk -- growth is never unbounded regardless of how long or how noisy
    the child's stderr is. Thread-safe: every read/write of the retained
    buffer is behind one lock.
    """

    def __init__(
        self,
        stderr: BinaryIO,
        *,
        chunk_size: int = DEFAULT_DRAIN_CHUNK_BYTES,
        max_retained_bytes: int = DEFAULT_DRAIN_MAX_RETAINED_BYTES,
    ) -> None:
        self._stderr = stderr
        self._chunk_size = chunk_size
        self._max_retained_bytes = max_retained_bytes
        self._lock = threading.Lock()
        self._buffer = bytearray()
        self._total_bytes_seen = 0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Idempotent: a second call while already running is a no-op."""

        if self._thread is not None:
            return
        thread = threading.Thread(target=self._run, name=_DRAIN_THREAD_NAME, daemon=True)
        self._thread = thread
        thread.start()

    def _run(self) -> None:
        while True:
            try:
                chunk = self._stderr.read(self._chunk_size)
            except (OSError, ValueError):
                # A closed/invalid pipe -- nothing more to drain, exactly
                # like a clean EOF below.
                return
            if not chunk:
                return  # EOF: the child's stderr pipe has closed.
            with self._lock:
                self._total_bytes_seen += len(chunk)
                self._buffer.extend(chunk)
                overflow = len(self._buffer) - self._max_retained_bytes
                if overflow > 0:
                    del self._buffer[:overflow]

    def latest_text(self) -> str | None:
        """Bounded, credential-redacted tail of the most recent stderr
        output, or `None` if nothing has been captured yet. Decoding and
        redaction both happen here, on the full retained tail, rather than
        per-chunk -- so a credentialed URL split across two read chunks is
        still caught (the redaction regex sees the whole retained string
        at once, never a partial fragment)."""

        with self._lock:
            raw = bytes(self._buffer)
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace").strip()
        if not text:
            return None
        return redact_credentials_in_text(text)

    @property
    def bytes_seen(self) -> int:
        """Total bytes ever read from the pipe (an unbounded counter, not
        retained content) -- advanced/diagnostic only, e.g. to confirm a
        drain thread genuinely kept up with a high-volume producer rather
        than having stalled."""

        with self._lock:
            return self._total_bytes_seen

    def stop(self, *, timeout: float = 2.0) -> None:
        """Bounded join; safe to call more than once. Callers must ensure
        the owning process has already been terminated/killed before
        calling this (see the module/class docstrings) -- otherwise the
        drain thread may still be blocked reading a still-open pipe and
        this call will simply return after `timeout` without the thread
        having stopped, matching `_stop_process`'s own bounded-wait
        precedent rather than hanging indefinitely."""

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)


__all__ = [
    "DEFAULT_DRAIN_CHUNK_BYTES",
    "DEFAULT_DRAIN_MAX_RETAINED_BYTES",
    "BoundedStderrDrain",
]
