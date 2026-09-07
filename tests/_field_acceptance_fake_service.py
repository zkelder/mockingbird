"""Field Acceptance End-to-End Integration Proof v1: a real, disposable,
stdlib-only HTTP service that answers exactly the field-acceptance
endpoints the accepted tooling actually calls -- bearer-token-authenticated
Observation start/status/stop and raw-ledger counterfactual reads, plus the
two public product-identity routes `deploy_windows_dev.py`'s own real
process-liveness probe (`probe_port`) uses. This is never a mock of
`FieldAcceptanceClient`/`WindowsHost` themselves, and never a parallel
production API -- see docs/non-interactive-field-acceptance-authentication-
session-access-v1-contract.md for the real contract this mirrors, and
`FakeObservationState`'s own docstring for exactly which fields/shapes come
from direct reading of `field_acceptance_client.py`, `deploy_windows_dev.
probe_port`/`verified_owning_release`, `capture_to_visible_latency.
build_latency_samples`, and `field_acceptance_ledger_snapshot.
reconcile_ledger`.

Runs on a real socket in a background thread -- mirrors this suite's own
established precedent for a shared, non-test-prefixed real-HTTP/real
-process test helper (`tests/_transport_fault_injection.py`,
`tests/test_camera_node_real_process.py`) -- so the actual field-acceptance
CLIs can be driven over it through a real `subprocess`, not merely an
in-process monkeypatch of `urllib.request.urlopen`.

State progression is call-count/explicit-action-driven, never wall-clock
-dependent (the same determinism principle `test_field_acceptance_session_
driver.py`'s own `_FakeClock` already established), so a real, but fast,
subprocess/HTTP round trip stays fully deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import threading
import time
from typing import Any
import urllib.error
import urllib.request

_OBSERVATION_PATH_RE = re.compile(r"^/api/streams/([^/]+)/observation/([a-z-]+)$")


def free_port() -> int:
    """A real, currently-unused TCP port on 127.0.0.1 -- mirrors
    `tests/_transport_fault_injection.py`/`tests/test_camera_node_real_
    process.py`'s own identical helper."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class FakeObservationState:
    """One Stream's fake Observation lifecycle plus the small, realistic
    raw-ledger this integration proof needs -- deliberately not a full
    `CounterfactualLedger` reimplementation, only exactly the record shape
    `capture_to_visible_latency.build_latency_samples`/`field_acceptance_
    ledger_snapshot.reconcile_ledger` actually read.

    Three admitted candidates, chosen to cover the honest classification
    vocabulary this milestone's own governing directive names, never
    invented for its own sake:

    - ``proposal-1``: an ordinary admission with a real, valid capture
      anchor (``generation-1``, real ``start_captured_at``) -- resolves to
      ``state="measured"``.
    - ``proposal-2``: admitted, but its own constituent generation
      (``generation-2``) has no ``start_captured_at`` at all (a real,
      accepted "this predates capture" shape -- see
      `capture_to_visible_latency._resolve_t0`'s own docstring) -- resolves
      to ``state="unavailable_capture_time"``, never a crash.
    - ``proposal-3-rescued``: only appears once stop-finalization has
      genuinely settled (``phase == "stopped"``) -- the exact "candidate
      rescued during finalization" shape *Representative Daylight
      True-Latency Tail Convergence v3*'s own candidate-012 established
      (``decided_at`` after the stop request), reusing ``generation-1`` and
      an ambiguous-boundary-arbitration fallback ``reason`` suffix --
      resolves to ``state="measured"`` AND ``is_fallback=True``
      (``fallback_measured``), proving a rescued candidate is never
      silently mis-classified either.

    Every timestamp fact is computed exactly once (`__post_init__`, or the
    moment settlement genuinely occurs) and never re-derived on a later
    fetch -- a real product's ledger never re-decides a past decision's own
    timestamp on a later re-read, and `field_acceptance_ledger_snapshot`'s
    own dedup keys `proposal_outcomes` by ``(proposal_id, decided_at)`` (see
    `_proposal_outcome_identity`), so a timestamp that drifted per fetch
    would silently defeat deduplication instead of modeling a stable fact.
    """

    stream_id: str
    bearer_token: str
    instance_id: str
    git_commit: str
    build_id: str
    app_version: str = "0.0.0-fake"
    session_duration_ms: int = 60_000
    stopping_polls_to_settle: int = 2

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, init=False)
    status_poll_count: int = field(default=0, init=False)
    phase: str = field(default="not_started", init=False)  # not_started -> observing -> stopping -> stopped
    stop_poll_count: int = field(default=0, init=False)
    rescued_decided_at: "datetime | None" = field(default=None, init=False)
    request_log: list = field(default_factory=list, init=False)

    _gen1_start: datetime = field(init=False)
    _gen1_end: datetime = field(init=False)
    _outcome1_decided_at: datetime = field(init=False)
    _outcome2_decided_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._gen1_start = now - timedelta(seconds=45)
        self._gen1_end = self._gen1_start + timedelta(seconds=3)
        self._outcome1_decided_at = self._gen1_end + timedelta(seconds=1)
        self._outcome2_decided_at = now - timedelta(seconds=40)

    # --- Mutating actions (POST) -------------------------------------

    def start_observation(self) -> None:
        with self._lock:
            self.phase = "observing"
            self.status_poll_count = 0
            self.stop_poll_count = 0
            self.rescued_decided_at = None

    def stop_observation(self) -> None:
        with self._lock:
            self.phase = "stopping"
            self.stop_poll_count = 0

    # --- Reads (GET) ----------------------------------------------------

    def status(self) -> dict:
        """`ObservationSessionStatusResponse`-shaped: `state` genuinely
        transitions `observing -> stopping -> stopped` after
        `stopping_polls_to_settle` polls (models real stop-finalization
        pending -> settled, including the transient `"stopping"` state
        `wait_for_stop_settlement` must not mistake for settled), and
        `counts.candidates_created` progresses with every poll (models
        real candidate-count progression the session driver's own
        `sample_count_fn` reads)."""

        with self._lock:
            self.status_poll_count += 1
            if self.phase == "stopping":
                self.stop_poll_count += 1
                if self.stop_poll_count >= self.stopping_polls_to_settle:
                    self.phase = "stopped"
                    self.rescued_decided_at = datetime.now(timezone.utc)
            reported_state = "observing" if self.phase == "not_started" else self.phase
            return {
                "state": reported_state,
                "observing": self.phase == "observing",
                "counts": {"candidates_created": min(self.status_poll_count, 50)},
            }

    def counterfactual(self) -> dict:
        """`CounterfactualWindowResponse`-shaped -- see this class's own
        docstring for the three admitted candidates. Coverage is reported
        honestly (real `oldest`/`newest_retained_offset_ms` per artifact,
        never a "proven from session start" shortcut), so a genuine,
        structurally-unavoidable boundary gap (nothing before the first
        event, nothing after the last, up to `session_duration_ms`)
        reconciles `PARTIAL` -- the same honest shape *Representative
        Daylight True-Latency Tail Convergence v3*'s own real report
        recorded, never an invented defect."""

        with self._lock:
            track_generations = [
                {
                    "generation_id": "generation-1", "stream_id": self.stream_id, "broad_class": "animal",
                    "track_ids": ["track-1"], "start_offset_ms": 5_000, "end_offset_ms": 8_000,
                    "start_bounding_box": [0.40, 0.40, 0.55, 0.60], "end_bounding_box": [0.42, 0.41, 0.56, 0.61],
                    "geometry_envelope": [0.40, 0.40, 0.56, 0.61], "confirmed": True,
                    "terminal_reason": "episode_boundary_final",
                    "start_captured_at": iso(self._gen1_start), "end_captured_at": iso(self._gen1_end),
                },
                {
                    "generation_id": "generation-2", "stream_id": self.stream_id, "broad_class": "animal",
                    "track_ids": ["track-2"], "start_offset_ms": 15_000, "end_offset_ms": 17_000,
                    "start_bounding_box": [0.10, 0.10, 0.20, 0.20], "end_bounding_box": [0.11, 0.11, 0.21, 0.21],
                    "geometry_envelope": [0.10, 0.10, 0.21, 0.21], "confirmed": True,
                    "terminal_reason": "episode_boundary_final",
                    # Deliberately no start_captured_at/end_captured_at --
                    # see this class's own docstring for proposal-2.
                },
            ]
            proposal_outcomes = [
                {
                    "proposal_id": "proposal-1", "stream_id": self.stream_id, "broad_class": "animal",
                    "zone_id": None, "start_offset_ms": 5_000, "end_offset_ms": 8_000,
                    "constituent_generation_ids": ["generation-1"], "outcome": "visit_created", "reason": "admitted",
                    "admitted": True, "visit_id": "visit-outcome-1", "decided_at": iso(self._outcome1_decided_at),
                },
                {
                    "proposal_id": "proposal-2", "stream_id": self.stream_id, "broad_class": "animal",
                    "zone_id": None, "start_offset_ms": 15_000, "end_offset_ms": 17_000,
                    "constituent_generation_ids": ["generation-2"], "outcome": "visit_created", "reason": "admitted",
                    "admitted": True, "visit_id": "visit-outcome-2", "decided_at": iso(self._outcome2_decided_at),
                },
            ]
            if self.rescued_decided_at is not None:
                proposal_outcomes.append({
                    "proposal_id": "proposal-3-rescued", "stream_id": self.stream_id, "broad_class": "animal",
                    "zone_id": None, "start_offset_ms": 5_000, "end_offset_ms": 8_000,
                    "constituent_generation_ids": ["generation-1"], "outcome": "visit_created",
                    "reason": "admitted:fallback_position_2", "admitted": True, "visit_id": "visit-outcome-3",
                    "decided_at": iso(self.rescued_decided_at),
                })

            proposal_offsets = [value for item in proposal_outcomes for value in (item["start_offset_ms"], item["end_offset_ms"])]
            return {
                "stream_id": self.stream_id, "start_offset_ms": 0, "end_offset_ms": self.session_duration_ms,
                "roi": None,
                "raw_detections": [],
                "track_generations": track_generations,
                "proposal_outcomes": proposal_outcomes,
                "raw_detection_count_in_roi": 0, "track_generation_count_in_roi": len(track_generations),
                "coverage": {
                    "session_first_offset_ms": 0, "session_last_offset_ms": self.session_duration_ms,
                    "raw_detections": {
                        "recorded_count": 0, "oldest_retained_offset_ms": None, "newest_retained_offset_ms": None,
                    },
                    "track_generations": {
                        "recorded_count": len(track_generations),
                        "oldest_retained_offset_ms": min(item["start_offset_ms"] for item in track_generations),
                        "newest_retained_offset_ms": max(item["end_offset_ms"] for item in track_generations),
                    },
                    "proposal_outcomes": {
                        "recorded_count": len(proposal_outcomes),
                        "oldest_retained_offset_ms": min(proposal_offsets),
                        "newest_retained_offset_ms": max(proposal_offsets),
                    },
                },
                "attribution": "fake_field_acceptance_service",
                "attribution_reason": "Field Acceptance End-to-End Integration Proof v1 fixture -- not a live query.",
                "clock_calibrations": [], "clock_calibration_required": False, "rtt_clock_calibrations": [],
            }


def _make_handler(state: FakeObservationState) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
            pass

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            """Models "authenticated requests" (governing report §3): a
            missing/wrong bearer token is rejected exactly like the real
            product's own `resolve_field_acceptance_token` -- see
            docs/non-interactive-field-acceptance-authentication-session-
            access-v1-contract.md. `/health`/`/api/product/instance`/
            `/api/product/health` deliberately never check this, matching
            `deploy_windows_dev.probe_port`'s own real behavior (it never
            sends an Authorization header) and `field_acceptance_client.
            product_health`'s own docstring ("public, unauthenticated")."""

            return self.headers.get("Authorization") == f"Bearer {state.bearer_token}"

        def _consume_body(self) -> bytes:
            length = int(self.headers.get("Content-Length", 0) or 0)
            return self.rfile.read(length) if length else b""

        def do_GET(self) -> None:  # noqa: N802 - stdlib method name
            self._consume_body()
            path = self.path.partition("?")[0]
            if path == "/health":
                self._send_json(200, {"status": "ok"})
                return
            if path == "/api/product/instance":
                self._send_json(200, {
                    "instance_id": state.instance_id, "app_version": state.app_version,
                    "git_commit": state.git_commit, "build_id": state.build_id,
                })
                return
            if path == "/api/product/health":
                self._send_json(200, {"ready": True, "database_schema_version": 59})
                return

            match = _OBSERVATION_PATH_RE.match(path)
            if match and match.group(1) == state.stream_id:
                if not self._authorized():
                    self._send_json(401, {"detail": "Field-acceptance credential is missing, invalid, expired, or revoked."})
                    return
                action = match.group(2)
                if action == "status":
                    self._send_json(200, state.status())
                    return
                if action == "counterfactual":
                    self._send_json(200, state.counterfactual())
                    return
                if action == "scene-confusor-learning":
                    self._send_json(200, {"stream_id": state.stream_id, "reviewed_evidence_enabled": False})
                    return
            self._send_json(404, {"detail": f"no such route: GET {path}"})

        def do_POST(self) -> None:  # noqa: N802 - stdlib method name
            self._consume_body()
            path = self.path.partition("?")[0]
            match = _OBSERVATION_PATH_RE.match(path)
            if match and match.group(1) == state.stream_id:
                if not self._authorized():
                    self._send_json(401, {"detail": "Field-acceptance credential is missing, invalid, expired, or revoked."})
                    return
                action = match.group(2)
                if action == "start":
                    state.start_observation()
                    self._send_json(200, {"state": "observing"})
                    return
                if action == "stop":
                    state.stop_observation()
                    self._send_json(200, {"state": "stopping"})
                    return
            self._send_json(404, {"detail": f"no such route: POST {path}"})

    return _Handler


def _wait_until_serving(base_url: str, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: "Exception | None" = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/health", timeout=1.0) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (urllib.error.URLError, ConnectionError, OSError) as error:
            last_error = error
        time.sleep(0.05)
    raise RuntimeError(f"fake field-acceptance service never answered /health within {timeout_seconds}s: {last_error}")


class FakeFieldAcceptanceService:
    """A real `ThreadingHTTPServer` on a real socket, in a background
    daemon thread -- reachable by a real `subprocess` (WSL2 localhost
    -forwarding confirmed live in this sandbox, so a real Windows-native
    `powershell.exe`/`Invoke-WebRequest`/`Get-NetTCPConnection` call also
    reaches it -- see the governing report's own "Process-liveness proof"
    for the direct empirical confirmation this design relies on)."""

    def __init__(self, state: FakeObservationState, *, port: "int | None" = None) -> None:
        self.state = state
        self.port = port if port is not None else free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), _make_handler(state))
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def start(self) -> "FakeFieldAcceptanceService":
        self._thread.start()
        _wait_until_serving(self.base_url, timeout_seconds=10.0)
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=10.0)


def write_fake_dev_root(
    dev_root: Path, *, sha: str, full_commit: str, build_id: str, port: int, app_version: str = "0.0.0-fake",
) -> None:
    """The minimal, real `releases/deployments.json` + `releases/
    current.json` shape `field_acceptance_instance_lifecycle.py`'s own
    `_probe_running`/`init_instance` read directly from disk (see
    `deploy_windows_dev.ReleaseRecord.as_dict`/`CurrentPointer.as_dict`) --
    built by hand, deliberately never through a real multi-GB
    `deploy_windows_dev.py deploy`, per the governing directive's own "Do
    not deploy the real product" bound. `read_current`/`read_deployments`
    are plain `json.loads` file reads with no `windows_host` involvement,
    so this needs no Windows-host seam either."""

    releases_dir = dev_root / "releases"
    releases_dir.mkdir(parents=True, exist_ok=True)
    ledger_entry = {
        "sha": sha, "full_commit": full_commit, "build_id": build_id, "app_version": app_version,
        "runtime_hash": "fake-runtime-hash", "model_hash": "fake-model-hash",
        "deployed_at": iso(datetime.now(timezone.utc)), "junctioned_relative_paths": [],
        "bioclip_model_hash": "no-model-bundle-packaged",
    }
    (releases_dir / "deployments.json").write_text(json.dumps([ledger_entry]), encoding="utf-8")
    (releases_dir / "current.json").write_text(json.dumps({"sha": sha, "pid": None, "port": port}), encoding="utf-8")
