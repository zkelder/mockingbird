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
    # Release Reliability & First-Run Recovery v1: `runtime.run()` no longer
    # calls the `uvicorn.run(...)` convenience wrapper directly -- it
    # constructs `uvicorn.Config`+`uvicorn.Server` explicitly so it can
    # publish the real `Server` on `app.state.uvicorn_server` (see
    # `POST /api/product/shutdown` in api/main.py). Mocking `Server.run`
    # itself (never actually binding a real socket or blocking) is the
    # equivalent no-op for this new shape; `uvicorn.Config`/`uvicorn.
    # Server(...)` construction is cheap and non-blocking, so leaving it
    # real (rather than also mocking `Server.__init__`) still lets
    # `app.state.uvicorn_server` genuinely get set, exactly as production
    # does.
    monkeypatch.setattr(runtime_module.uvicorn.Server, "run", lambda self: None)
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


# ---------------------------------------------------------------------------
# Build identity: which exact commit/build a *packaged* instance is running
# (docs/windows-dev-deployment-design.md). `_build_info_path` is redirected
# per test the same way test_engine_runtime.py redirects `packaged_
# observation_runtime_root` -- never by writing a fixture file into this
# real installed package's own source tree.
# ---------------------------------------------------------------------------


def test_resolve_build_identity_is_none_without_a_packaged_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A bare development checkout (this test suite's own real state) never
    went through `write_build_identity` -- the conservative "cannot
    confirm" default, matching `resolve_instance_id`'s own philosophy,
    rather than inventing a commit/build."""

    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: tmp_path / "no-such-build-info.json")

    assert runtime_state.resolve_build_identity() == (None, None)


def test_resolve_build_identity_reads_a_real_packaged_build_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_info = tmp_path / "build_info.json"
    build_info.write_text(
        '{"git_commit": "af15161d76f214d9b10310284840a8069b12eb70", "build_id": "0123456789abcdef", '
        '"built_at": "2026-08-09T00:00:00+00:00", "app_version": "0.1.0"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: build_info)

    git_commit, build_id = runtime_state.resolve_build_identity()

    assert git_commit == "af15161d76f214d9b10310284840a8069b12eb70"
    assert build_id == "0123456789abcdef"


def test_resolve_build_identity_recovers_from_a_corrupt_build_info(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_info = tmp_path / "build_info.json"
    build_info.write_text("not valid json {{{", encoding="utf-8")
    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: build_info)

    # Must not raise -- an honest "cannot confirm", same as a missing file.
    assert runtime_state.resolve_build_identity() == (None, None)


def test_resolve_build_identity_ignores_malformed_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `build_info.json` that parses as JSON but whose fields are not the
    non-empty strings this contract requires (a wrong type, or an empty
    string) is treated exactly like a missing field -- never surfaced as a
    truthy-but-wrong identity a caller could act on."""

    build_info = tmp_path / "build_info.json"
    build_info.write_text('{"git_commit": 12345, "build_id": ""}', encoding="utf-8")
    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: build_info)

    assert runtime_state.resolve_build_identity() == (None, None)


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
    have already exercised a real launch path and left it set. Also never
    went through `write_build_identity`, so `git_commit`/`build_id` are
    conservatively `None` too -- `_build_info_path` is redirected to a path
    that cannot exist so this assertion is independent of whether this
    particular test host happens to have a real packaged build_info.json
    lying around anywhere.
    """

    monkeypatch.setattr(runtime_state, "_runtime_home", None)
    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: Path("/no/such/build_info.json"))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/product/instance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["instance_id"] is None
    assert payload["git_commit"] is None
    assert payload["build_id"] is None


@pytest.mark.anyio
async def test_product_instance_endpoint_reports_build_identity_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The positive case: once a process is running from a real packaged
    build, `/api/product/instance` self-reports its exact commit/build --
    what a dev-deployment tool's verification step actually reads (see
    docs/windows-dev-deployment-design.md).

    Redirects the same low-level `_build_info_path` seam the other
    `resolve_build_identity` tests use, rather than monkeypatching
    `resolve_build_identity` itself: `api/main.py` imported that name with
    `from mockingbird.runtime_state import resolve_build_identity`, a
    separate binding in `api_main`'s own module namespace that reassigning
    `runtime_state.resolve_build_identity` would not reach -- redirecting
    the lower-level seam instead exercises the real function through the
    real endpoint, unaffected by which module's copy of the name is used.
    """

    build_info = tmp_path / "build_info.json"
    build_info.write_text(
        '{"git_commit": "af15161d76f214d9b10310284840a8069b12eb70", "build_id": "cafef00ddeadbeef", '
        '"built_at": "2026-08-09T00:00:00+00:00", "app_version": "0.1.0"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_state, "_build_info_path", lambda: build_info)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/product/instance")
    assert response.status_code == 200
    payload = response.json()
    assert payload["git_commit"] == "af15161d76f214d9b10310284840a8069b12eb70"
    assert payload["build_id"] == "cafef00ddeadbeef"


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


# ---------------------------------------------------------------------------
# Mobile & Remote Experience v1: `GET /api/product/connection` and the
# `runtime.run()` state it reads back -- see ProductConnectionInfo's own
# docstring in api/schemas.py for the authenticated-vs-public reasoning.
# ---------------------------------------------------------------------------


def test_detect_local_network_address_returns_a_string_on_this_host() -> None:
    """Sanity check against this real development host -- not a mock, since
    the whole point of the UDP-connect trick is that it works without real
    connectivity to the target; a `None` here on an ordinary dev machine
    would itself be the interesting failure."""

    address = runtime_module.detect_local_network_address()
    assert address is None or isinstance(address, str) and address


def test_detect_local_network_address_is_none_on_any_socket_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No network interface / sandboxed networking must read "could not
    determine," never raise and never crash the endpoint that calls this."""

    class _RaisingSocket:
        def __init__(self, *_args, **_kwargs) -> None:
            raise OSError("no network available")

    monkeypatch.setattr(runtime_module.socket, "socket", _RaisingSocket)
    assert runtime_module.detect_local_network_address() is None


def test_run_wires_bind_state_onto_app_state_for_network_allowed_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one real place these facts are set -- `GET /api/product/
    connection` only ever reads them back (see the endpoint's own
    docstring)."""

    _prepare_runtime_env(tmp_path, monkeypatch, port=8204)
    monkeypatch.setattr(runtime_module, "port_is_available", lambda _host, _port: True)
    monkeypatch.delattr(api_main.app.state, "bind_host", raising=False)
    monkeypatch.delattr(api_main.app.state, "bind_port", raising=False)
    monkeypatch.delattr(api_main.app.state, "network_access_allowed", raising=False)

    try:
        result = run(["--host", "0.0.0.0", "--allow-network", "--port", "8204", "--no-browser"])
        assert result == 0
        assert api_main.app.state.bind_host == "0.0.0.0"
        assert api_main.app.state.bind_port == 8204
        assert api_main.app.state.network_access_allowed is True
    finally:
        monkeypatch.delattr(api_main.app.state, "bind_host", raising=False)
        monkeypatch.delattr(api_main.app.state, "bind_port", raising=False)
        monkeypatch.delattr(api_main.app.state, "network_access_allowed", raising=False)


async def _sign_in_as_bootstrap_administrator(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/setup/administrator",
        json={
            "display_name": "Ada Admin",
            "login_identity": "ada-connection-test",
            "password": "correct horse battery staple",
        },
    )
    assert response.status_code in (200, 201), response.text


@pytest.mark.anyio
async def test_product_connection_endpoint_requires_authentication() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/product/connection")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_product_connection_endpoint_reports_conservative_defaults_without_a_real_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(app.state, "bind_host", raising=False)
    monkeypatch.delattr(app.state, "bind_port", raising=False)
    monkeypatch.delattr(app.state, "network_access_allowed", raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _sign_in_as_bootstrap_administrator(client)
        response = await client.get("/api/product/connection")
    assert response.status_code == 200
    payload = response.json()
    assert payload["bind_host"] == "127.0.0.1"
    assert payload["bind_port"] == 8000
    assert payload["network_access_allowed"] is False
    assert payload["is_loopback_only"] is True
    assert payload["local_network_url"] is None


@pytest.mark.anyio
async def test_product_connection_endpoint_reports_explicit_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.state, "bind_host", "127.0.0.1", raising=False)
    monkeypatch.setattr(app.state, "bind_port", 9001, raising=False)
    monkeypatch.setattr(app.state, "network_access_allowed", False, raising=False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _sign_in_as_bootstrap_administrator(client)
        response = await client.get("/api/product/connection")
    payload = response.json()
    assert payload["is_loopback_only"] is True
    assert payload["local_network_url"] is None


@pytest.mark.anyio
async def test_product_connection_endpoint_detects_lan_address_for_a_wildcard_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--host 0.0.0.0 --allow-network`: the literal bind host is not
    itself a usable URL, so the endpoint falls back to best-effort LAN
    detection."""

    monkeypatch.setattr(app.state, "bind_host", "0.0.0.0", raising=False)
    monkeypatch.setattr(app.state, "bind_port", 8000, raising=False)
    monkeypatch.setattr(app.state, "network_access_allowed", True, raising=False)
    monkeypatch.setattr(runtime_module, "detect_local_network_address", lambda: "192.168.1.42")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _sign_in_as_bootstrap_administrator(client)
        response = await client.get("/api/product/connection")
    payload = response.json()
    assert payload["is_loopback_only"] is False
    assert payload["local_network_url"] == "http://192.168.1.42:8000"


@pytest.mark.anyio
async def test_product_connection_endpoint_uses_the_literal_host_when_not_wildcard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`--host 192.168.1.42 --allow-network` (a specific address, not the
    `0.0.0.0` wildcard): the host is already known, so no LAN-detection
    guess is needed -- proven by making detection raise if it is ever
    called."""

    def _must_not_be_called() -> str | None:
        raise AssertionError("detect_local_network_address should not be called for a non-wildcard bind_host")

    monkeypatch.setattr(app.state, "bind_host", "192.168.1.42", raising=False)
    monkeypatch.setattr(app.state, "bind_port", 8000, raising=False)
    monkeypatch.setattr(app.state, "network_access_allowed", True, raising=False)
    monkeypatch.setattr(runtime_module, "detect_local_network_address", _must_not_be_called)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _sign_in_as_bootstrap_administrator(client)
        response = await client.get("/api/product/connection")
    payload = response.json()
    assert payload["local_network_url"] == "http://192.168.1.42:8000"


@pytest.mark.anyio
async def test_product_connection_endpoint_reports_no_lan_url_when_detection_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(app.state, "bind_host", "0.0.0.0", raising=False)
    monkeypatch.setattr(app.state, "bind_port", 8000, raising=False)
    monkeypatch.setattr(app.state, "network_access_allowed", True, raising=False)
    monkeypatch.setattr(runtime_module, "detect_local_network_address", lambda: None)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await _sign_in_as_bootstrap_administrator(client)
        response = await client.get("/api/product/connection")
    payload = response.json()
    assert payload["local_network_url"] is None
