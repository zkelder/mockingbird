#!/usr/bin/env python3
"""Field Acceptance Tooling Correctness & Preflight Closure v1: an
independent, bounded pre-Observation readiness gate for the acceptance
recorder (`mockingbird.observation.acceptance_recorder.
BoundedFrameSampleRecorder`) -- see docs/field-acceptance-tooling-
correctness-preflight-closure-v1-report.md.

## Why this exists

Representative Daylight True-Latency Tail Convergence v3's own Defect #3:
an operator enabled the recorder (`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_
DIR` was set, non-empty) and the deploy step reported nothing wrong -- but
the value silently mistranslated to a garbage relative path (see
`deploy_windows_dev.py`'s own `launch_release` fix for the *cause* this
tool guards the *consequence* of -- Defect #2/#3's shared root: an
untranslated/mistranslated Windows path, silently accepted), and the
recorder never wrote a single usable frame all session. No independent
visual-evidence frames were available to resolve that session's own
disputed samples -- discovered only after the fact, in the field report,
never before Observation.

"A process exists" is not sufficient proof a recorder is actually working
-- see governing brief §4. This tool proves the *stronger* claim a real
field procedure needs before it commits to a full session: the target
directory exists and is writable, real frame files are actually being
written (not merely a directory sitting empty), their timestamps/sizes
genuinely advance over a bounded observation window, and the writes
correspond to the intended Stream (never a differently-spelled sibling
directory from a stale prior session). If none of that can be confirmed
within a bounded timeout, this fails closed -- the calling field procedure
is expected to STOP BEFORE (committing further to) OBSERVATION rather than
run an entire session blind on an unverified assumption, exactly the
mistake this milestone closes.

## What this checks (and does not)

Reads `<recording_root>/<stream_id>/<session-timestamp>/` -- the exact
directory shape `engine_runtime._EngineSession` computes
(`acceptance_recording_root / stream_id / started_at.strftime(
"%Y%m%dT%H%M%SZ")`) -- purely from the filesystem side (this project's own
`sandbox-has-windows-gpu-interop` convention: a WSL-visible `/mnt/c/...`
recording root is directly readable from here with no extra translation,
matching the same value an operator already set in
`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`). Re-resolves the newest
correctly-named session directory on *every* poll (never latches onto a
stale one from a prior session and stops looking). Never inspects the
recorder's own in-process `AcceptanceRecorderStatus` (not exposed by any
API -- see that dataclass's own docstring, "surfaced in the final field
report, never in ordinary product status/health") and never talks to the
product HTTP API at all for the file-evidence check itself; an optional
injectable `process_alive_fn` is the only way this tool ever learns
whether the deployed process is even still running (`None` -- unknown,
checked only when a caller wires one in -- never assumed either way).

This is not a general filesystem-watch utility -- bounded to exactly the
one directory shape/naming convention `acceptance_recorder.py` itself
already established, and to exactly the pass/fail readiness question a
field procedure needs answered once, right after triggering Observation
start, before committing to the rest of the session.

## Usage

    # Immediately after triggering `POST .../observation/start` -- give
    # the recorder a bounded window to prove it is genuinely writing,
    # before committing to the rest of the session. --dev-root is optional
    # and additionally confirms the deployed process is actually still
    # running (governing brief §4's "recorder process is alive") before
    # waiting for frame evidence:
    python scripts/field_acceptance_recorder_readiness.py \\
        --recording-root /mnt/c/Users/<you>/AppData/Local/<DevRoot>/acceptance-recording \\
        --stream-id <id> --dev-root /mnt/c/Users/<you>/AppData/Local/<DevRoot> --timeout-seconds 90

Exit code 0 only when readiness is confirmed; 1 otherwise -- the governing
field procedure must treat a non-zero exit as STOP BEFORE OBSERVATION
(governing brief §4), never merely a warning.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent

_lifecycle_module: dict[str, object] | None = None


def _lifecycle() -> dict[str, object]:
    """Reuses `field_acceptance_instance_lifecycle.py`'s own already
    -established `_probe_running`/`real_windows_host` primitives for the
    CLI's optional `--dev-root` process-liveness wiring below -- never a
    second, independently-drifting "is the deployed process alive" check.
    Loaded via `runpy.run_path`, matching this whole tooling family's
    established sibling-script-reuse convention (`_dwd()`/`_fac()` in the
    other field-acceptance scripts)."""

    global _lifecycle_module
    if _lifecycle_module is None:
        _lifecycle_module = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_instance_lifecycle.py"))
    return _lifecycle_module

# Matches `datetime.strftime("%Y%m%dT%H%M%SZ")` exactly -- the one naming
# convention `engine_runtime._EngineSession` actually uses for a recorder
# session directory. Deliberately narrow (never "any subdirectory") so a
# stray, differently-named directory under the same Stream never gets
# mistaken for real recorder evidence.
_SESSION_DIR_RE = re.compile(r"^\d{8}T\d{6}Z$")


@dataclass(frozen=True)
class RecorderSnapshot:
    """One poll's own observed facts about `session_dir` -- deliberately
    small and directly comparable across polls (see `_has_advanced`)."""

    manifest_line_count: int
    newest_frame_filename: str | None
    newest_frame_size_bytes: int | None
    newest_frame_mtime: float | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecorderReadinessResult:
    ready: bool
    reason: str
    stream_id: str
    recording_root: str
    session_dir: str | None
    session_dir_writable: bool | None
    elapsed_seconds: float
    poll_count: int
    process_alive: bool | None
    first_snapshot: RecorderSnapshot | None
    last_snapshot: RecorderSnapshot | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready, "reason": self.reason, "stream_id": self.stream_id,
            "recording_root": self.recording_root, "session_dir": self.session_dir,
            "session_dir_writable": self.session_dir_writable, "elapsed_seconds": self.elapsed_seconds,
            "poll_count": self.poll_count, "process_alive": self.process_alive,
            "first_snapshot": self.first_snapshot.as_dict() if self.first_snapshot else None,
            "last_snapshot": self.last_snapshot.as_dict() if self.last_snapshot else None,
        }


def _find_session_dir(recording_root: Path, stream_id: str) -> Path | None:
    """The most recently *named* session directory (`%Y%m%dT%H%M%SZ`
    timestamps sort lexicographically in start order, matching
    `engine_runtime._EngineSession`'s own naming) under `<recording_root>/
    <stream_id>/` -- `None` if that directory does not exist yet, or
    contains no correctly-named subdirectory (never guesses at a
    differently-named one; see `_SESSION_DIR_RE`). Called fresh on every
    poll (see `check_recorder_readiness`) so a session directory that
    appears *after* polling has already begun is still found."""

    stream_dir = recording_root / stream_id
    if not stream_dir.is_dir():
        return None
    try:
        candidates = sorted(
            (entry for entry in stream_dir.iterdir() if entry.is_dir() and _SESSION_DIR_RE.match(entry.name)),
            key=lambda entry: entry.name,
        )
    except OSError:
        return None
    return candidates[-1] if candidates else None


def _snapshot(session_dir: Path) -> RecorderSnapshot:
    """Reads exactly the two artifact classes `BoundedFrameSampleRecorder`
    itself writes (`manifest.jsonl`, `frame-*.jpg`) -- never parses frame
    bytes/manifest JSON content, only counts/stats them; this is a
    liveness/advancement proof, not a content-correctness audit."""

    manifest_path = session_dir / "manifest.jsonl"
    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest_line_count = sum(1 for _ in handle)
    except OSError:
        manifest_line_count = 0

    newest_name: str | None = None
    newest_mtime: float | None = None
    newest_size: int | None = None
    try:
        frame_files = [
            entry for entry in session_dir.iterdir()
            if entry.name.startswith("frame-") and entry.name.endswith(".jpg")
        ]
    except OSError:
        frame_files = []
    for entry in frame_files:
        try:
            stat = entry.stat()
        except OSError:
            continue
        if newest_mtime is None or stat.st_mtime > newest_mtime:
            newest_mtime, newest_name, newest_size = stat.st_mtime, entry.name, stat.st_size

    return RecorderSnapshot(
        manifest_line_count=manifest_line_count, newest_frame_filename=newest_name,
        newest_frame_size_bytes=newest_size, newest_frame_mtime=newest_mtime,
    )


def _has_advanced(first: RecorderSnapshot, latest: RecorderSnapshot) -> bool:
    """Real advancement -- never merely 'a directory exists' or 'exactly
    one static file sits there unchanged.' True the moment *either* the
    manifest has grown (more frames considered/saved) *or* a genuinely
    newer frame file has appeared (a distinct filename, or the identical
    name with a later mtime -- covers the case of exactly one sample
    interval elapsed between polls, still only one file on disk but a real
    new write landed on it -- `BoundedFrameSampleRecorder` never rewrites
    an existing frame file in place, but a test double reasonably might)."""

    if latest.manifest_line_count > first.manifest_line_count:
        return True
    if latest.newest_frame_filename is None:
        return False
    if latest.newest_frame_filename != first.newest_frame_filename:
        return True
    return (
        first.newest_frame_mtime is not None
        and latest.newest_frame_mtime is not None
        and latest.newest_frame_mtime > first.newest_frame_mtime
    )


def check_recorder_readiness(
    *,
    recording_root: Path,
    stream_id: str,
    timeout_seconds: float = 90.0,
    poll_interval_seconds: float = 5.0,
    process_alive_fn: "Callable[[], bool] | None" = None,
    monotonic_fn: "Callable[[], float] | None" = None,
    sleep_fn: "Callable[[float], None] | None" = None,
) -> RecorderReadinessResult:
    """Governing brief §4 'Independent recorder hard gate': polls, bounded
    by `timeout_seconds`, until real, advancing frame evidence is observed
    under `<recording_root>/<stream_id>/<session-timestamp>/` -- never
    merely that the directory exists. A process-liveness failure (when
    `process_alive_fn` is given) fails immediately, before any polling --
    no point waiting out a full timeout for evidence from a process that
    is not there. `monotonic_fn`/`sleep_fn` default to real `time.
    monotonic`/`time.sleep`, late-bound fresh on every call (never
    captured at module-load/def time -- matches `field_acceptance_ledger_
    snapshot.run_periodic_collection`'s own established `sleep_fn`/
    `stdout`/`stderr` discipline) so a test's own fake clock always
    actually takes effect."""

    if monotonic_fn is None:
        monotonic_fn = time.monotonic
    if sleep_fn is None:
        sleep_fn = time.sleep

    recording_root = Path(recording_root)
    start = monotonic_fn()

    if process_alive_fn is not None and not process_alive_fn():
        return RecorderReadinessResult(
            ready=False,
            reason=(
                "recorder_process_not_alive -- the deployed process is not running; no point waiting for "
                "frame evidence from a process that is not there."
            ),
            stream_id=stream_id, recording_root=str(recording_root), session_dir=None,
            session_dir_writable=None, elapsed_seconds=0.0, poll_count=0, process_alive=False,
            first_snapshot=None, last_snapshot=None,
        )
    process_alive = True if process_alive_fn is not None else None

    poll_count = 0
    session_dir: Path | None = None
    first_snapshot: RecorderSnapshot | None = None
    last_snapshot: RecorderSnapshot | None = None

    while True:
        poll_count += 1
        found = _find_session_dir(recording_root, stream_id)
        if found is not None and found != session_dir:
            # A fresh (or first-ever) session directory -- start tracking
            # advancement from here, never from a stale prior session's own
            # already-static files (governing brief §4's "recording
            # corresponds to the intended camera/session").
            session_dir = found
            first_snapshot = None
        elapsed = monotonic_fn() - start

        if session_dir is not None:
            snapshot = _snapshot(session_dir)
            if first_snapshot is None:
                first_snapshot = snapshot
                last_snapshot = snapshot
            else:
                last_snapshot = snapshot
                if _has_advanced(first_snapshot, snapshot):
                    return RecorderReadinessResult(
                        ready=True,
                        reason=(
                            f"Confirmed advancing frame evidence under {session_dir} after {poll_count} "
                            f"poll(s) ({elapsed:.1f}s)."
                        ),
                        stream_id=stream_id, recording_root=str(recording_root), session_dir=str(session_dir),
                        session_dir_writable=_is_writable(session_dir), elapsed_seconds=elapsed,
                        poll_count=poll_count, process_alive=process_alive,
                        first_snapshot=first_snapshot, last_snapshot=last_snapshot,
                    )

        if elapsed >= timeout_seconds:
            return RecorderReadinessResult(
                ready=False, reason=_timeout_reason(recording_root, stream_id, session_dir, last_snapshot, timeout_seconds),
                stream_id=stream_id, recording_root=str(recording_root),
                session_dir=str(session_dir) if session_dir else None,
                session_dir_writable=_is_writable(session_dir) if session_dir else None,
                elapsed_seconds=elapsed, poll_count=poll_count, process_alive=process_alive,
                first_snapshot=first_snapshot, last_snapshot=last_snapshot,
            )

        sleep_fn(poll_interval_seconds)


def _is_writable(session_dir: Path) -> bool:
    return os.access(session_dir, os.W_OK)


def _timeout_reason(
    recording_root: Path, stream_id: str, session_dir: Path | None,
    last_snapshot: RecorderSnapshot | None, timeout_seconds: float,
) -> str:
    if session_dir is None:
        return (
            f"recorder_session_directory_not_found -- no {stream_id}/<session-timestamp> directory ever "
            f"appeared under {recording_root} within {timeout_seconds}s. The recorder may not be enabled, "
            "may be writing to a different path (see MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR / "
            "deploy_windows_dev.py's own Windows-path translation), or may be targeting a different Stream."
        )
    if last_snapshot is not None and last_snapshot.newest_frame_filename is None:
        return f"no_frames_written -- {session_dir} exists but zero frame files appeared within {timeout_seconds}s."
    return (
        f"frames_not_advancing -- {session_dir} exists with frame evidence present, but neither the "
        f"manifest nor the newest frame file advanced within {timeout_seconds}s -- writes appear stalled."
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _process_alive_fn_for_dev_root(dev_root: Path) -> Callable[[], bool]:
    """Wires a real 'is the deployed process still running' check into
    `check_recorder_readiness`'s own optional `process_alive_fn` seam,
    reusing `field_acceptance_instance_lifecycle.py`'s own already
    -established `_probe_running`/`real_windows_host` (which itself reuses
    `deploy_windows_dev.py`'s own port/process-table primitives) -- never a
    second, independently-drifting liveness check. `dev_root` is resolved
    through that same module's own canonical `_resolve_dev_root` (Field
    Acceptance Tooling Correctness & Preflight Closure v1) so this CLI
    accepts the identical WSL-visible/Windows-style input convention every
    other field-acceptance tool now does."""

    lifecycle = _lifecycle()
    dwd = lifecycle["_dwd"]()  # type: ignore[operator]
    windows_host = dwd["real_windows_host"]()  # type: ignore[operator]
    resolved = lifecycle["_resolve_dev_root"](dev_root)  # type: ignore[operator]

    def _check() -> bool:
        process_running, _owning_release, _port = lifecycle["_probe_running"](  # type: ignore[operator]
            dev_root=resolved, windows_host=windows_host, dwd=dwd,
        )
        return bool(process_running)

    return _check


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--recording-root", type=Path, required=True,
        help="WSL-visible recording root -- the same value given to MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR.",
    )
    parser.add_argument("--stream-id", required=True)
    parser.add_argument(
        "--dev-root", type=Path, default=None,
        help="Optional -- when given, also confirms the deployed process is actually still running "
        "(field_acceptance_instance_lifecycle.py's own process probe) before waiting for frame evidence.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    process_alive_fn = _process_alive_fn_for_dev_root(args.dev_root) if args.dev_root is not None else None
    result = check_recorder_readiness(
        recording_root=args.recording_root, stream_id=args.stream_id,
        timeout_seconds=args.timeout_seconds, poll_interval_seconds=args.poll_interval_seconds,
        process_alive_fn=process_alive_fn,
    )
    if args.as_json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str))
    else:
        for key, value in result.as_dict().items():
            print(f"{key}: {value}")
        if not result.ready:
            print("\nSTOP BEFORE OBSERVATION -- recorder readiness could not be confirmed.", file=sys.stderr)
    return 0 if result.ready else 1


if __name__ == "__main__":
    sys.exit(main())
