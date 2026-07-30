import asyncio
from pathlib import Path
from urllib.error import URLError

import httpx
from fastapi import HTTPException
import pytest

import mockingbird.api.main as api_main
from mockingbird.api.main import app
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.runtime import (
    APP_HOME_ENV_VAR,
    healthy_mockingbird_at,
    resolve_runtime_home,
    run,
)
from mockingbird.web_app import WEB_DIST_ENV_VAR, frontend_response


def request(path: str) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
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
