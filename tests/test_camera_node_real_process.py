"""Real-OS-process smoke test for the Camera Node package.

Every other Camera Node test drives the FastAPI app in-process through
`httpx.ASGITransport` -- fast, but it never proves the package actually
boots as a genuine separate OS process reachable over a real TCP socket, the
exact shape `systemd` will run in production. This file closes that gap
(see "Real-process smoke test" in docs/camera-node-installer-design.md). It
complements, and does not replace, the existing in-process suite.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import time
import urllib.error
import urllib.request
import venv

import pytest

# Test Suite Runtime & Baseline Reliability v1: a real venv/pip install plus
# a real subprocess.Popen'd OS process over a real TCP socket -- Tier C
# (slow software integration), excluded from the Fast/Core gates. See
# docs/test-suite-validation-tiers-contract.md.
pytestmark = pytest.mark.slow

ROOT = Path(__file__).resolve().parents[1]
BUILD_ARTIFACT = runpy.run_path(ROOT / "scripts" / "build_camera_node_artifact.py")["build_camera_node_artifact"]

_START_TIMEOUT_SECONDS = 25.0
_STOP_TIMEOUT_SECONDS = 10.0


def _free_local_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _real_node_environment(tmp_path: Path) -> dict[str, str]:
    """A minimal, fully isolated environment: no inherited pairing state, no
    real camera provider, and nothing that could ever touch a real
    developer/operator's actual `~/.local/state` directory."""

    return {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "MOCKINGBIRD_NODE_BIND": "127.0.0.1",
        "MOCKINGBIRD_NODE_PROVIDERS": "synthetic",
        "MOCKINGBIRD_NODE_TESTING": "1",
        "MOCKINGBIRD_NODE_PAIRING_STATE_PATH": str(tmp_path / "pairing.json"),
    }


def _venv_python(tmp_path: Path, *, name: str = "node-real-process-env") -> Path:
    artifact = BUILD_ARTIFACT(tmp_path / "artifact", allow_dirty_source=True)
    environment_root = tmp_path / name
    venv.EnvBuilder(with_pip=True).create(environment_root)
    python = environment_root / "bin" / "python"
    # Unlike the packaging test's `--no-deps` install (which only proves the
    # wheel itself is slim), a real running server needs its actual runtime
    # requirements importable -- `pip`'s local wheel cache (already warm from
    # this same environment's own fastapi/uvicorn/pydantic, core dependencies
    # of the main `mockingbird` package) keeps this fast without requiring
    # fresh network access.
    install_result = subprocess.run(
        [python, "-m", "pip", "install", str(artifact.wheel), "-r", str(artifact.requirements)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0, install_result.stderr
    return python


def _wait_for_health(port: int, *, timeout_seconds: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/node/v1/health", timeout=2) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, ConnectionError, TimeoutError) as error:
            last_error = error
            time.sleep(0.25)
    raise AssertionError(f"Camera Node never answered /node/v1/health within {timeout_seconds}s: {last_error}")


def test_real_subprocess_serves_health_over_a_real_socket_and_shuts_down_cleanly(tmp_path) -> None:
    python = _venv_python(tmp_path)
    port = _free_local_port()
    environment = _real_node_environment(tmp_path)
    environment["MOCKINGBIRD_NODE_PORT"] = str(port)
    # info, not the conservative default, so the graceful-shutdown sequence
    # below is independently provable from real log output, not merely
    # inferred from a bounded exit.
    environment["MOCKINGBIRD_NODE_LOG_LEVEL"] = "info"

    process = subprocess.Popen(
        [python, "-m", "mockingbird_node"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        payload = _wait_for_health(port, timeout_seconds=_START_TIMEOUT_SECONDS)
        assert payload["status"] == "available"
        assert payload["api_version"] == "v1"
        assert payload["camera_count"] == 1  # the synthetic test camera
        assert payload["pairing_required"] is True

        # The real capabilities/pairing round trip also works over the real
        # socket, not only the health check. `urlopen` raises `HTTPError`
        # (a subclass it can still be inspected through) for a non-2xx
        # status rather than returning a response.
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/node/v1/cameras", timeout=2)
            raise AssertionError("expected 401 Unauthorized without a pairing credential")
        except urllib.error.HTTPError as error:
            assert error.code == 401  # unauthenticated -- pairing required
    finally:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=_STOP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=_STOP_TIMEOUT_SECONDS)
            raise AssertionError(
                f"Camera Node did not shut down within {_STOP_TIMEOUT_SECONDS}s of SIGTERM "
                f"(the exact behavior systemd's TimeoutStopSec relies on).\nstdout={stdout}\nstderr={stderr}"
            )

    # A genuinely *graceful* shutdown, empirically confirmed rather than
    # assumed: uvicorn runs its full ASGI shutdown sequence (which calls
    # this app's own `shutdown_provider` -> `provider.close()`) to
    # completion, well within the bounded window above, *before* it
    # deliberately re-raises the SIGTERM it caught -- documented, standard
    # daemon behavior (see uvicorn.Server.capture_signals) so a process
    # supervisor's own exit-status accounting stays correct. This is why the
    # exit code itself is signal-terminated (-15), never 0 -- asserting 0
    # here would be asserting the wrong thing about what "clean shutdown"
    # actually looks like at the OS level for a process that reacts to a
    # signal rather than exiting on its own initiative.
    assert process.returncode == -15, f"stdout={stdout}\nstderr={stderr}"
    assert "Shutting down" in stderr
    assert "Application shutdown complete" in stderr
    # The new deterministic, log-level-independent startup line (see
    # "Diagnostics implementation" in docs/camera-node-installer-design.md)
    # actually appears, and never leaks a credential/digest.
    assert "MockingBird Camera Node listening:" in stderr
    assert f"port={port}" in stderr
    assert "providers=synthetic" in stderr
    assert "pairing=not yet paired" in stderr
    assert "MockingBird Camera Node pairing code:" in stderr


def test_real_subprocess_reports_a_clean_config_error_and_exits_promptly(tmp_path) -> None:
    python = _venv_python(tmp_path)
    environment = _real_node_environment(tmp_path)
    environment["MOCKINGBIRD_NODE_PORT"] = str(_free_local_port())
    environment["MOCKINGBIRD_NODE_BIND"] = "not-a-real-bind-address"

    process = subprocess.Popen(
        [python, "-m", "mockingbird_node"],
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=_STOP_TIMEOUT_SECONDS)
        raise AssertionError(f"A config-load failure must exit promptly, never hang.\nstdout={stdout}\nstderr={stderr}")

    assert process.returncode == 1
    assert "Camera Node configuration error: mockingbird_node_bind_invalid" in stderr
    # A clean, single-line failure -- never a raw Python traceback dumped to
    # the journal for an entirely ordinary, anticipated misconfiguration.
    assert "Traceback" not in stderr
