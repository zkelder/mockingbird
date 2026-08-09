"""Windows launcher reliability: console-safe startup and instance identity.

Covers "Windows launcher defects" in
docs/camera-node-pairing-persistence-design.md:

- `Start MockingBird.vbs` runs the embedded runtime through `pythonw.exe`,
  which has no console at all -- an unguarded `print()` used to crash the
  process before it ever bound a port, invisibly.
- The packaged launcher must distinguish *this* installation's own
  already-running instance from an arbitrary other service or a
  MockingBird instance forwarded from a different environment (for
  example WSL) that merely answers a healthy `/health` on the same port.

These tests run entirely on this (non-Windows) development host: Windows-
only branches are exercised by monkeypatching `os.name` and injecting a
fake `ctypes.windll`, never by requiring an actual Windows process.
"""

from __future__ import annotations

from pathlib import Path
import sys

import httpx
import pytest

import mockingbird.api.main as api_main
from mockingbird.api.main import app
import mockingbird.runtime as runtime_module
import mockingbird.runtime_state as runtime_state
from mockingbird.runtime import APP_HOME_ENV_VAR, run
from mockingbird.web_app import WEB_DIST_ENV_VAR


def _create_frontend_build(dist_path: Path) -> None:
    (dist_path / "assets").mkdir(parents=True)
    (dist_path / "index.html").write_text(
        "<!doctype html><title>MockingBird</title>", encoding="utf-8"
    )


def _prepare_runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, port: int) -> str:
    """Common scaffolding for a `run()` call that must not actually bind a
    port, build a real frontend, or touch the real developer checkout."""

    monkeypatch.chdir(Path.cwd())
    dist_path = tmp_path / "dist"
    _create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))
    monkeypatch.setenv(APP_HOME_ENV_VAR, str(tmp_path / "home"))
    monkeypatch.setattr(api_main, "_repository", None)
    monkeypatch.setattr(runtime_module, "prepare_runtime_state", lambda _home: None)
    monkeypatch.setattr(runtime_module.uvicorn, "run", lambda *args, **kwargs: None)
    return runtime_module.local_base_url("127.0.0.1", port)


# ---------------------------------------------------------------------------
# Console-safety: pythonw.exe has no console; sys.std* are None there.
# ---------------------------------------------------------------------------


def test_ensure_console_streams_patches_missing_streams_without_crashing() -> None:
    real_stdin, real_stdout, real_stderr = sys.stdin, sys.stdout, sys.stderr
    try:
        sys.stdin = None
        sys.stdout = None
        sys.stderr = None
        has_console = runtime_module._ensure_console_streams()
        assert has_console is False
        assert sys.stdin is not None
        assert sys.stdout is not None
        assert sys.stderr is not None
        # The entire point: this must never raise `AttributeError` on a
        # `None` stream the way it silently did before this milestone.
        print("must not crash even though pythonw has no console")
    finally:
        sys.stdin, sys.stdout, sys.stderr = real_stdin, real_stdout, real_stderr


def test_ensure_console_streams_leaves_a_real_console_untouched() -> None:
    stdout_before, stderr_before, stdin_before = sys.stdout, sys.stderr, sys.stdin
    has_console = runtime_module._ensure_console_streams()
    assert has_console is True
    assert sys.stdout is stdout_before
    assert sys.stderr is stderr_before
    assert sys.stdin is stdin_before


def test_alert_failure_shows_a_native_dialog_only_when_windows_has_no_console(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import ctypes

    calls: list[tuple] = []

    class FakeUser32:
        @staticmethod
        def MessageBoxW(hwnd, text, caption, flags):  # noqa: N802 - matches Win32 name
            calls.append((text, caption, flags))
            return 1

    class FakeWindll:
        user32 = FakeUser32()

    monkeypatch.setattr(ctypes, "windll", FakeWindll(), raising=False)
    monkeypatch.setattr(runtime_module.os, "name", "nt")

    runtime_module._alert_failure("No console, Windows: must show a dialog.", has_console=False)
    assert len(calls) == 1
    assert calls[0][0] == "No console, Windows: must show a dialog."

    calls.clear()
    runtime_module._alert_failure("Has a console: no dialog needed.", has_console=True)
    assert calls == []


def test_alert_failure_never_shows_a_dialog_off_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    import ctypes

    calls: list[tuple] = []

    class FakeUser32:
        @staticmethod
        def MessageBoxW(hwnd, text, caption, flags):  # noqa: N802
            calls.append((text, caption, flags))
            return 1

    class FakeWindll:
        user32 = FakeUser32()

    monkeypatch.setattr(ctypes, "windll", FakeWindll(), raising=False)
    monkeypatch.setattr(runtime_module.os, "name", "posix")

    runtime_module._alert_failure("No console, not Windows: still no dialog.", has_console=False)
    assert calls == []


def test_alert_failure_dialog_mechanism_failure_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """The alert mechanism itself must never become a new way to fail."""

    import ctypes

    class ExplodingWindll:
        @property
        def user32(self):
            raise RuntimeError("no such DLL on this fake system")

    monkeypatch.setattr(ctypes, "windll", ExplodingWindll(), raising=False)
    monkeypatch.setattr(runtime_module.os, "name", "nt")

    runtime_module._alert_failure("Should not raise even if the dialog itself fails.", has_console=False)


# ---------------------------------------------------------------------------
# Instance identity: "is that healthy /health really THIS installation."
# ---------------------------------------------------------------------------


def test_resolve_instance_id_is_stable_and_directory_scoped(tmp_path: Path) -> None:
    home_a = tmp_path / "install-a"
    home_b = tmp_path / "install-b"

    first_read = runtime_state.resolve_instance_id(home_a)
    second_read = runtime_state.resolve_instance_id(home_a)
    other_install = runtime_state.resolve_instance_id(home_b)

    assert first_read == second_read  # stable across repeated launches
    assert first_read != other_install  # a different data directory is a different install
    assert (home_a / "instance_identity.json").is_file()


def test_resolve_instance_id_recovers_from_a_corrupt_identity_file(tmp_path: Path) -> None:
    home = tmp_path / "install"
    home.mkdir()
    (home / "instance_identity.json").write_text("not valid json {{{", encoding="utf-8")

    # Must not raise; a fresh identity is simply minted and persisted.
    instance_id = runtime_state.resolve_instance_id(home)
    assert instance_id
    assert runtime_state.resolve_instance_id(home) == instance_id


@pytest.mark.anyio
async def test_product_instance_endpoint_reports_none_without_a_real_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare development/test server never went through `prepare_runtime_
    state`, so it honestly reports "cannot confirm identity" rather than
    inventing one -- the conservative default a launcher must trust.

    `runtime_state._runtime_home` is a process-global by product design (one
    real launch is one process); explicitly cleared here so this assertion
    is independent of whatever other test in the same pytest process may
    have already exercised a real launch path and left it set.
    """

    monkeypatch.setattr(runtime_state, "_runtime_home", None)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/product/instance")
    assert response.status_code == 200
    assert response.json()["instance_id"] is None


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_remote_instance_id_reads_a_real_health_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, _limit: int | None = None) -> bytes:
            return b'{"instance_id": "abc123", "app_version": "0.1.0"}'

    monkeypatch.setattr(runtime_module, "urlopen", lambda *_a, **_kw: FakeResponse())
    assert runtime_module._remote_instance_id("http://127.0.0.1:8000") == "abc123"


def test_remote_instance_id_is_none_for_an_unreachable_or_older_instance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unreachable(*_args, **_kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(runtime_module, "urlopen", raise_unreachable)
    assert runtime_module._remote_instance_id("http://127.0.0.1:8000") is None


def test_real_same_instance_reuse_still_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Double-launching the exact same installation (the same data
    directory) must still safely reuse the already-running copy."""

    base_url = _prepare_runtime_env(tmp_path, monkeypatch, port=8201)
    monkeypatch.setattr(runtime_module, "healthy_mockingbird_at", lambda _url: True)
    own_home = (tmp_path / "home").resolve()
    shared_instance_id = runtime_state.resolve_instance_id(own_home)
    monkeypatch.setattr(runtime_module, "_remote_instance_id", lambda _url: shared_instance_id)
    opened: list[str] = []
    monkeypatch.setattr(runtime_module.webbrowser, "open", lambda url: opened.append(url))

    result = run(["--port", "8201"])

    assert result == 0
    assert opened == [base_url]


def test_wsl_forwarded_or_different_install_is_never_silently_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A healthy `/health` alone must never be treated as proof of "this
    installation" -- exactly the WSL-on-port-8000 collision this milestone
    fixes. Distinguished by identity, not by killing the other process."""

    _prepare_runtime_env(tmp_path, monkeypatch, port=8202)
    monkeypatch.setattr(runtime_module, "healthy_mockingbird_at", lambda _url: True)
    monkeypatch.setattr(runtime_module, "_remote_instance_id", lambda _url: "a-different-installation-id")
    opened: list[str] = []
    monkeypatch.setattr(runtime_module.webbrowser, "open", lambda url: opened.append(url))

    def _unreachable(*_args, **_kwargs):
        raise AssertionError("must not even ask about port availability once a conflict is already known")

    # `run()` never spawns a process or sends a signal to "clean up" a port
    # conflict either -- there is simply no such code path to exercise;
    # this asserts the one thing it *could* wrongly fall through to instead.
    monkeypatch.setattr(runtime_module, "port_is_available", _unreachable)

    result = run(["--port", "8202", "--no-browser"])

    assert result == 2
    assert opened == []  # never silently attach to the wrong installation


def test_unconfirmable_remote_identity_is_treated_as_a_conflict_not_a_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An older MockingBird without `/api/product/instance`, or a timeout,
    must resolve to "cannot confirm" -- never silently reused merely
    because `/health` responded."""

    _prepare_runtime_env(tmp_path, monkeypatch, port=8203)
    monkeypatch.setattr(runtime_module, "healthy_mockingbird_at", lambda _url: True)
    monkeypatch.setattr(runtime_module, "_remote_instance_id", lambda _url: None)
    opened: list[str] = []
    monkeypatch.setattr(runtime_module.webbrowser, "open", lambda url: opened.append(url))

    result = run(["--port", "8203", "--no-browser"])

    assert result == 2
    assert opened == []


def test_launcher_frontend_resolution_is_independent_of_the_launch_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bundle extracted to an arbitrary path, double-clicked with an
    unrelated shell working directory, must resolve identically -- see
    `resolve_frontend_dist`'s `__file__`-relative packaged-path check."""

    from mockingbird.web_app import resolve_frontend_dist

    monkeypatch.delenv(WEB_DIST_ENV_VAR, raising=False)
    unrelated_cwd = tmp_path / "some" / "unrelated" / "launch-directory"
    unrelated_cwd.mkdir(parents=True)

    monkeypatch.chdir(Path.cwd())
    from_repo_root = resolve_frontend_dist()
    monkeypatch.chdir(unrelated_cwd)
    from_unrelated_cwd = resolve_frontend_dist()

    assert from_repo_root == from_unrelated_cwd
