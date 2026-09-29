import asyncio
from pathlib import Path
from urllib.error import URLError

import httpx
from fastapi import HTTPException
import pytest

import mockingbird.api.main as api_main
from mockingbird.api.main import app
import mockingbird.runtime as runtime_module
import mockingbird.runtime_state as runtime_state
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.runtime import (
    APP_HOME_ENV_VAR,
    RuntimePreflight,
    _print_preflight,
    healthy_mockingbird_at,
    resolve_runtime_home,
    run,
)
from mockingbird.web_app import WEB_DIST_ENV_VAR, frontend_response
from tests.conftest import LegacyAuthenticatedTestClient


def request(path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(send())


def create_frontend_build(dist_path: Path) -> None:
    (dist_path / "assets").mkdir(parents=True)
    (dist_path / "index.html").write_text(
        "<!doctype html><title>MockingBird product shell</title>",
        encoding="utf-8",
    )
    (dist_path / "assets" / "app.js").write_text(
        "window.mockingBirdReady = true;",
        encoding="utf-8",
    )


def test_single_app_serves_frontend_and_api_from_same_origin(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))

    root_response = request("/")
    health_response = request("/health")

    assert root_response.status_code == 200
    assert "MockingBird product shell" in root_response.text
    assert root_response.headers["cache-control"] == "no-cache"
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}


def test_direct_product_route_restores_frontend_shell(tmp_path: Path, monkeypatch) -> None:
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))

    response = request("/visits/visit-bird-feeder-001")

    assert response.status_code == 200
    assert "MockingBird product shell" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_built_assets_are_cached_but_missing_files_are_not_masked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))

    asset_response = request("/assets/app.js")
    missing_response = request("/assets/missing.js")
    missing_api_response = request("/api/not-a-real-endpoint")

    assert asset_response.status_code == 200
    assert asset_response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert missing_response.status_code == 404
    assert missing_api_response.status_code == 404
    assert missing_api_response.headers["content-type"].startswith("application/json")


def test_missing_frontend_build_has_recoverable_startup_message(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(tmp_path / "missing-dist"))

    response = request("/")

    assert response.status_code == 503
    assert "interface is not ready yet" in response.text
    assert response.headers["cache-control"] == "no-store"


def test_frontend_response_rejects_parent_path_traversal(tmp_path: Path, monkeypatch) -> None:
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))

    with pytest.raises(HTTPException) as caught:
        frontend_response("../secret.txt")

    assert caught.value.status_code == 404


def test_runtime_home_override_is_stable_outside_workspace(tmp_path: Path, monkeypatch) -> None:
    configured_home = tmp_path / "MockingBird Home"
    monkeypatch.setenv(APP_HOME_ENV_VAR, str(configured_home))

    assert resolve_runtime_home(workspace_root=None) == configured_home.resolve()


def test_resolve_runtime_home_default_is_independent_of_the_application_directory(
    tmp_path: Path, monkeypatch
) -> None:
    """External Acceptance Entry Readiness & Uninstall Closure v1.

    The packaged product has no installer/registry/service -- "uninstall"
    is deleting the unpacked application folder, optionally followed by
    deleting the separate user-data folder. That is only a safe,
    well-defined two-level procedure (delete the app; optionally also
    delete the data) if the data location is genuinely independent of
    wherever the application happens to be unpacked. This regression test
    locks that invariant in at the unit level, on this test runner's own
    OS default branch (`XDG_DATA_HOME`/`~/.local/share/mockingbird`): with
    no `MOCKINGBIRD_HOME` override and `workspace_root=None` (the packaged
    artifact has no `pyproject.toml`/`web` sibling for `find_workspace_root`
    to find, unlike a development checkout), the resolved runtime home
    never depends on the application directory or current working
    directory. `pathlib.Path` dispatches on the real `os.name` at
    construction time, so the equivalent `nt`/`%LOCALAPPDATA%` branch
    cannot be faithfully exercised this way on a POSIX test runner
    (`Path(...)` raises `NotImplementedError: cannot instantiate
    'WindowsPath' on your system` the moment `os.name` is monkeypatched) --
    that exact Windows-specific instance of this same contract (identical
    code shape, just `LOCALAPPDATA` instead of `XDG_DATA_HOME`, see
    `resolve_runtime_home`) is proven instead by real native-Windows
    evidence in
    docs/external-acceptance-entry-readiness-uninstall-closure-v1-report.md,
    not simulated here.
    """

    monkeypatch.delenv(APP_HOME_ENV_VAR, raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    fake_home = tmp_path / "home" / "someone"
    fake_home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    application_directory_a = fake_home / "Desktop" / "MockingBird-linux-x64"
    application_directory_b = fake_home / "Downloads" / "MockingBird-linux-x64 (2)"
    expected_runtime_home = fake_home / ".local" / "share" / "mockingbird"

    assert resolve_runtime_home(workspace_root=None) == expected_runtime_home
    # Unpacking (or re-unpacking, e.g. after upgrading or reinstalling) the
    # application anywhere at all resolves to the exact same data location --
    # never a path derived from the application directory itself.
    for application_directory in (application_directory_a, application_directory_b):
        application_directory.mkdir(parents=True)
        monkeypatch.chdir(application_directory)
        assert resolve_runtime_home(workspace_root=None) == expected_runtime_home


def test_print_preflight_reports_an_ordinary_already_current_launch_unchanged(capsys) -> None:
    """Release Engineering Foundation v1 must not change the message an
    ordinary, non-upgrading launch has always printed."""

    _print_preflight(
        RuntimePreflight(
            runtime_home=Path("/tmp/runtime-home"),
            frontend_dist=Path("/tmp/runtime-home/frontend"),
            database_schema_version=53,
            database_integrity_check="ok",
        )
    )

    assert capsys.readouterr().out == "MockingBird is ready: data format 53, integrity ok.\n"


def test_print_preflight_honestly_reports_a_migration_that_just_ran(capsys) -> None:
    """`--check`/a real launch performs the migration as a real side effect
    (see docs/release-engineering-foundation-v1-report.md's "not a dry
    run" finding); the console message is the one console-visible place
    this fact can be confirmed, alongside the automatic safety backup id."""

    _print_preflight(
        RuntimePreflight(
            runtime_home=Path("/tmp/runtime-home"),
            frontend_dist=Path("/tmp/runtime-home/frontend"),
            database_schema_version=53,
            database_integrity_check="ok",
            database_migrated_from_version=52,
            database_pre_migration_backup_id="deadbeefcafef00d",
        )
    )

    assert capsys.readouterr().out == (
        "MockingBird is ready: data format upgraded 52 -> 53 "
        "(safety backup deadbeefcafef00d), integrity ok.\n"
    )


def test_runtime_refuses_network_binding_without_explicit_permission(capsys) -> None:
    result = run(["--host", "0.0.0.0", "--no-browser"])

    assert result == 2
    assert "stays on this device" in capsys.readouterr().out


def test_runtime_rejects_invalid_port_before_startup(capsys) -> None:
    result = run(["--port", "70000", "--no-browser"])

    assert result == 2
    assert "between 1 and 65535" in capsys.readouterr().out


def test_existing_instance_requires_health_and_product_shell(monkeypatch) -> None:
    class FakeResponse:
        def __init__(
            self,
            body: str,
            *,
            content_type: str = "application/json",
            status: int = 200,
        ) -> None:
            self.body = body.encode("utf-8")
            self.headers = {"Content-Type": content_type}
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, limit: int | None = None) -> bytes:
            return self.body if limit is None else self.body[:limit]

    responses = iter(
        [
            FakeResponse('{"status":"ok"}'),
            FakeResponse(
                "<!doctype html><title>MockingBird</title>",
                content_type="text/html; charset=utf-8",
            ),
        ]
    )
    monkeypatch.setattr("mockingbird.runtime.urlopen", lambda *_args, **_kwargs: next(responses))

    assert healthy_mockingbird_at("http://127.0.0.1:8000") is True


def test_plain_api_health_is_not_reused_as_complete_app(monkeypatch) -> None:
    class HealthOnlyResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def read(self, _limit: int | None = None) -> bytes:
            return b'{"status":"ok"}'

    calls = 0

    def health_without_shell(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return HealthOnlyResponse()
        raise URLError("no product shell")

    monkeypatch.setattr("mockingbird.runtime.urlopen", health_without_shell)

    assert healthy_mockingbird_at("http://127.0.0.1:8000") is False


def test_app_shutdown_stops_process_owned_runtime_activity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class SourceMonitorStub:
        cancelled = False

        def cancel_all(self) -> None:
            self.cancelled = True

    class CameraSessionStub:
        stopped_reason: str | None = None

        def stop_all(self, *, reason: str) -> None:
            self.stopped_reason = reason

    source_monitor = SourceMonitorStub()
    camera_session = CameraSessionStub()
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    monkeypatch.setattr(api_main, "_repository", repository)
    monkeypatch.setattr(api_main, "_source_monitor_manager", source_monitor)
    monkeypatch.setattr(api_main, "_live_camera_session_manager", camera_session)

    async def exercise_lifespan() -> None:
        async with api_main._app_lifespan(app):
            assert source_monitor.cancelled is False
            assert camera_session.stopped_reason is None

    asyncio.run(exercise_lifespan())

    assert source_monitor.cancelled is True
    assert camera_session.stopped_reason == "api_shutdown"


def test_app_shutdown_records_a_clean_shutdown_marker(tmp_path: Path, monkeypatch) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}")
    monkeypatch.setattr(api_main, "_repository", repository)
    marked = []
    monkeypatch.setattr(api_main, "mark_clean_shutdown", lambda: marked.append(True))

    async def exercise_lifespan() -> None:
        async with api_main._app_lifespan(app):
            assert marked == []  # not marked clean until shutdown actually completes

    asyncio.run(exercise_lifespan())

    assert marked == [True]


def test_repository_reconfiguration_stops_the_live_detector_generation(monkeypatch) -> None:
    class DetectorStub:
        stopped = False

        def shutdown(self) -> None:
            self.stopped = True

    detector = DetectorStub()
    monkeypatch.setattr(api_main, "_live_object_detector_manager", detector)

    api_main._stop_runtime_activity(reason="repository_reconfigured")

    assert detector.stopped is True
    assert api_main._live_object_detector_manager is None


# MockingBird Installable Local Product v1: previous-crash detection and a
# fixed log location (docs/local-product-packaging-design.md).


def test_prepare_runtime_state_detects_an_unclean_previous_run(tmp_path: Path) -> None:
    first_run = runtime_state.prepare_runtime_state(tmp_path)
    assert first_run is None  # never ran against this data directory before

    runtime_state.mark_clean_shutdown()
    second_run = runtime_state.prepare_runtime_state(tmp_path)
    assert second_run is True

    # No `mark_clean_shutdown()` before the next start -- for example a crash
    # or a forced kill.
    third_run = runtime_state.prepare_runtime_state(tmp_path)
    assert third_run is False
    assert runtime_state.previous_shutdown_was_clean() is False


def test_mark_clean_shutdown_is_a_safe_no_op_before_any_run_is_prepared(monkeypatch) -> None:
    monkeypatch.setattr(runtime_state, "_runtime_home", None)

    runtime_state.mark_clean_shutdown()  # must not raise


def test_configure_file_logging_creates_a_fixed_discoverable_log_file(tmp_path: Path) -> None:
    import logging

    log_path = runtime_state.configure_file_logging(tmp_path)

    assert log_path == tmp_path / "logs" / "mockingbird.log"
    logging.getLogger("mockingbird.test_logger").info("fidelity marker line")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "fidelity marker line" in log_path.read_text(encoding="utf-8")
    assert runtime_state.current_log_path() == log_path


def test_check_mode_never_touches_the_crash_marker_or_log_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """`--check` must stay side-effect-light: repeatedly validating startup
    must never make the *next real launch* think the previous one crashed.
    """

    # `run_preflight()` (exercised for real below) changes the process
    # working directory by product design; restore it so this test cannot
    # leak a changed cwd into later tests that assume the repository root.
    monkeypatch.chdir(Path.cwd())
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))
    monkeypatch.setenv(APP_HOME_ENV_VAR, str(tmp_path / "home"))
    # A real (not monkeypatched) `run_preflight()` call constructs a real
    # repository through the process-wide `get_repository()` singleton;
    # resetting it here, through monkeypatch, both starts this test from a
    # clean slate and automatically restores whatever was there afterward.
    monkeypatch.setattr(api_main, "_repository", None)

    prepare_calls = []
    monkeypatch.setattr(
        runtime_module,
        "prepare_runtime_state",
        lambda runtime_home: prepare_calls.append(runtime_home),
    )
    log_calls = []
    monkeypatch.setattr(
        runtime_module,
        "configure_file_logging",
        lambda runtime_home: log_calls.append(runtime_home),
    )

    result = run(["--check", "--skip-frontend-build"])

    assert result == 0
    assert prepare_calls == []
    assert log_calls == []


def test_real_launch_prepares_the_crash_marker_and_logging_before_serving(
    tmp_path: Path,
    monkeypatch,
) -> None:
    # The real (unmocked) `run_preflight()` this test exercises below changes
    # the process working directory to the runtime home, by product design
    # (see runtime.py) -- restore it so this test cannot leak a changed cwd
    # into later tests that assume the repository root (`monkeypatch.chdir`
    # restores whatever cwd was current the moment this line runs).
    monkeypatch.chdir(Path.cwd())
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))
    runtime_home = tmp_path / "home"
    monkeypatch.setenv(APP_HOME_ENV_VAR, str(runtime_home))
    monkeypatch.setattr(api_main, "_repository", None)

    prepare_calls = []
    monkeypatch.setattr(
        runtime_module,
        "prepare_runtime_state",
        lambda home: prepare_calls.append(home),
    )
    log_calls = []
    monkeypatch.setattr(
        runtime_module,
        "configure_file_logging",
        lambda home: log_calls.append(home),
    )
    # Never actually bind a port or block forever in a test.
    monkeypatch.setattr(runtime_module, "port_is_available", lambda _host, _port: True)
    # `runtime.run()` builds the real `uvicorn.Server` and then serves it
    # through `serve_until_stopped` (see runtime.py) -- mock only that step.
    monkeypatch.setattr(runtime_module, "serve_until_stopped", lambda _server: None)

    result = run(["--no-browser", "--port", "8199", "--skip-frontend-build"])

    assert result == 0
    assert prepare_calls == [runtime_home.resolve()]
    assert log_calls == [runtime_home.resolve()]


# ---------------------------------------------------------------------------
# Native-Windows Runtime Shutdown & Listener Resilience Correction v1.
#
# F-1 and F-2 were found on native Windows against the bundled CPython's
# Proactor event loop, which this Linux suite cannot run. These tests pin the
# two runtime decisions that close them at the closest controllable
# boundary: the uvicorn server loop is always a selector loop (F-2 and F-1's
# trigger), and graceful shutdown is bounded even if a connection's
# server-side bookkeeping leaks, which is exactly what the Proactor bug did
# (F-1). The real native-Windows socket/process proof is
# scripts/native_windows_runtime_resilience_acceptance.py.
# ---------------------------------------------------------------------------


def _free_loopback_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class _LeakedTransport:
    """Stand-in for a transport whose close never reached `Server._detach`."""

    def close(self) -> None:
        pass

    def abort(self) -> None:
        pass


def _leak_one_server_connection(server: asyncio.AbstractServer) -> None:
    """Reproduce F-1's exact state: the bundled CPython's Proactor
    `_call_connection_lost` raised `WinError 10054` before `server._detach()`,
    leaving `asyncio.Server`'s active-connection count one too high forever,
    so `Server.wait_closed()` (awaited unbounded by uvicorn's own shutdown)
    never returns."""

    try:
        server._attach()  # CPython 3.11/3.12
    except TypeError:
        server._attach(_LeakedTransport())  # CPython 3.13+


def _start_real_server(app, port: int, monkeypatch):
    """Start a real server through the real launch path's own seams, forced
    onto the native-Windows branch (selector loop via `asyncio.Runner`)."""

    import threading
    import time

    monkeypatch.setattr(runtime_module, "_SERVE_ON_SELECTOR_LOOP", True)
    server = runtime_module.build_uvicorn_server(app, host="127.0.0.1", port=port, log_config=None)
    thread = threading.Thread(target=runtime_module.serve_until_stopped, args=(server,), daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert thread.is_alive() and time.monotonic() < deadline, "test server never started"
        time.sleep(0.02)
    return server, thread


def test_graceful_shutdown_is_bounded_when_a_connection_never_detaches(monkeypatch) -> None:
    """F-1: a leaked server connection must not stop the existing lifespan
    teardown (which ends in `mark_clean_shutdown()`) from running, and the
    serve call must return within the configured bound."""

    import time
    from contextlib import asynccontextmanager

    from fastapi import FastAPI

    assert isinstance(runtime_module.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS, (int, float))
    assert 0 < runtime_module.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS <= 30
    # Shrink only the wait for this test; the production value is asserted
    # through the built Config just below.
    monkeypatch.setattr(runtime_module, "GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS", 1)

    teardown_events: list[str] = []

    @asynccontextmanager
    async def lifespan(_app):
        yield
        teardown_events.append("lifespan_teardown_completed")

    server, thread = _start_real_server(FastAPI(lifespan=lifespan), _free_loopback_port(), monkeypatch)
    assert server.config.timeout_graceful_shutdown == 1
    listening = server.servers[0]
    asyncio.run_coroutine_threadsafe(
        asyncio.sleep(0, result=_leak_one_server_connection(listening)), listening.get_loop()
    ).result(timeout=5)

    stop_requested = time.monotonic()
    server.should_exit = True
    thread.join(timeout=10)

    assert not thread.is_alive(), "graceful shutdown hung on a leaked connection (F-1)"
    assert teardown_events == ["lifespan_teardown_completed"]
    assert time.monotonic() - stop_requested < 5


def test_serve_on_selector_loop_only_on_windows() -> None:
    assert runtime_module._SERVE_ON_SELECTOR_LOOP is (runtime_module.sys.platform == "win32")


def test_built_server_carries_the_bounded_graceful_shutdown_timeout() -> None:
    server = runtime_module.build_uvicorn_server(app, host="127.0.0.1", port=8199, log_config=None)
    assert (
        server.config.timeout_graceful_shutdown
        == runtime_module.GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS
    )


def test_real_launch_serves_on_a_selector_loop_whatever_the_platform_default(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """F-2 (and F-1's trigger): uvicorn's own platform default on Windows is
    the Proactor loop, whose accept loop closes the listening socket on
    `WinError 64` and whose connection-lost path skips `Server._detach()` on
    `WinError 10054`. The real launch path must choose the selector loop
    itself on Windows, never inherit uvicorn's platform default. Windows and
    its default are simulated here (the flag plus a marker loop factory),
    since this suite runs on Linux."""

    monkeypatch.chdir(Path.cwd())
    dist_path = tmp_path / "dist"
    create_frontend_build(dist_path)
    monkeypatch.setenv(WEB_DIST_ENV_VAR, str(dist_path))
    monkeypatch.setenv(APP_HOME_ENV_VAR, str(tmp_path / "home"))
    monkeypatch.setattr(api_main, "_repository", None)
    monkeypatch.setattr(runtime_module, "prepare_runtime_state", lambda _home: None)
    monkeypatch.setattr(runtime_module, "configure_file_logging", lambda _home: None)
    monkeypatch.setattr(runtime_module, "port_is_available", lambda _host, _port: True)
    monkeypatch.setattr(runtime_module, "_SERVE_ON_SELECTOR_LOOP", True)

    class PlatformDefaultLoop(asyncio.SelectorEventLoop):
        """Stands in for Windows' Proactor default."""

    monkeypatch.setattr(
        runtime_module.uvicorn.Config, "get_loop_factory", lambda _self: PlatformDefaultLoop
    )
    served_on: list[asyncio.AbstractEventLoop] = []

    async def fake_serve(self, sockets=None) -> None:
        served_on.append(asyncio.get_running_loop())

    monkeypatch.setattr(runtime_module.uvicorn.Server, "serve", fake_serve)

    assert run(["--no-browser", "--port", "8199", "--skip-frontend-build"]) == 0

    assert len(served_on) == 1
    assert isinstance(served_on[0], asyncio.SelectorEventLoop)
    assert not isinstance(served_on[0], PlatformDefaultLoop)


def test_abortive_connection_burst_leaves_the_listener_serving(monkeypatch) -> None:
    """The exact F-2 reproducer shape (back-to-back `Connection: close`
    requests, each aborted with RST via `SO_LINGER 0`) against a real server
    started the way the real launch path starts it. On Linux this is a
    regression guard for the selector-loop listener; the native-Windows proof
    is the acceptance script."""

    import socket
    import struct
    import time

    from fastapi import FastAPI

    probe_app = FastAPI()

    @probe_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    port = _free_loopback_port()
    server, thread = _start_real_server(probe_app, port, monkeypatch)
    try:
        for _burst in range(3):
            for _ in range(30):
                client = socket.create_connection(("127.0.0.1", port))
                client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                client.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                client.close()
            time.sleep(0.2)
            with socket.create_connection(("127.0.0.1", port), timeout=3) as check:
                check.sendall(b"GET /health HTTP/1.1\r\nHost: 127.0.0.1\r\nConnection: close\r\n\r\n")
                assert check.recv(20).startswith(b"HTTP/1.1 200")
    finally:
        server.should_exit = True
        thread.join(timeout=15)
    assert not thread.is_alive()
