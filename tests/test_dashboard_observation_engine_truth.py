"""v0.1 Product Flow Gap Pass v1: Dashboard/product-health "is MockingBird
monitoring?" truthfulness for a paired Camera Node Stream.

`_dashboard_runtime_by_stream` (api/main.py) previously consulted only the
legacy `LiveCameraSessionManager`/`SourceMonitorManager` -- never the
accepted `ObservationEngineSessionManager`. Architecture.md's "Live camera
ownership" documents that the legacy live session is *deliberately* paused
for the entire time Observation Engine owns a Camera Node Stream's camera
(`pause_for_observation`), so `monitoring_active` was structurally always
`False` for a genuinely, successfully observing Camera Node Stream. This
made `GET /api/dashboard/summary`'s `headline.monitored_stream_count` and
`GET /api/product/health`'s `observation.monitored_stream_count` undercount
real observation, and drove `TodayReportPanel`'s empty-state copy to the
"Monitoring hasn't started yet" branch even while Observation was actively,
healthily running -- directly contradicting Stream Detail's own Observation
panel (and the Dashboard's own `LiveCameraOverview` tile, already fixed for
a related gap -- see docs, "Dashboard ownership fix + Camera Node outage").

These tests drive the real `dashboard_summary`/`product_health` read paths
through the real API with a real `camera_node`-configured Stream, faking
only the side-effect-free `ObservationEngineSessionManager.status()` read
(mirroring `mockingbird.observation.unified_status.resolve_observation_
runtime`'s own lane resolution) -- never starting a real session.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.demo_data import STREAM_ID as DEMO_STREAM_ID
from mockingbird.observation.engine_runtime import ObservationEngineSessionStatus
from mockingbird.repository.product_repository import ProductRepository


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def client(repository: ProductRepository) -> TestClient:
    return TestClient(app)


def _configure_camera_node(client: TestClient, stream_id: str = DEMO_STREAM_ID) -> None:
    """Make the demo Stream's Source a `camera_node` provider (pairing
    status is irrelevant to this fix -- only `provider_key` is read)."""

    response = client.patch(
        "/api/sources/source-backyard-demo/provider-configuration",
        json={"provider_key": "camera_node", "config": {}},
    )
    assert response.status_code == 200


class _FakeObservingEngineManager:
    """A minimal stand-in for `ObservationEngineSessionManager` reporting one
    Stream as genuinely observing. `.status()` is the same side-effect-free
    read `ObservationControlPanel`/the unified status route already use."""

    def __init__(self, observing_stream_id: str) -> None:
        self._observing_stream_id = observing_stream_id

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        if stream_id != self._observing_stream_id:
            return None
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="observing",
            observing=True,
            message="Observing",
            camera_connected=True,
            camera_message="Healthy",
            engine_available=True,
            engine_message="Ready",
        )


class _FakeIdleEngineManager:
    """A Camera Node Stream that is paired but not currently observing."""

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="stopped",
            observing=False,
            message="Not observing",
            camera_connected=True,
            camera_message="Healthy",
            engine_available=True,
            engine_message="Ready",
        )


def test_dashboard_summary_reports_an_observing_camera_node_stream_as_monitored(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeObservingEngineManager(DEMO_STREAM_ID),
    )

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["headline"]["monitored_stream_count"] == 1
    stream_summary = next(s for s in body["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["monitoring_active"] is True
    assert stream_summary["monitor_control"] == "observation_engine"


def test_dashboard_summary_does_not_falsely_report_an_idle_camera_node_stream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: a paired-but-not-observing Camera Node must not
    suddenly read as monitored just because the engine manager exists."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeIdleEngineManager(),
    )

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["headline"]["monitored_stream_count"] == 0
    stream_summary = next(s for s in body["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["monitoring_active"] is False


def test_dashboard_summary_ignores_engine_status_for_a_non_camera_node_stream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Stream that never configured `camera_node` must not consult the
    engine manager's status at all, even if it would (incorrectly) report
    observing for that id -- the lane check must gate the read itself."""

    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeObservingEngineManager(DEMO_STREAM_ID),
    )

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["headline"]["monitored_stream_count"] == 0
    stream_summary = next(s for s in body["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["monitoring_active"] is False


def test_product_health_counts_an_observing_camera_node_stream(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same defect surfaced most visibly through `ProductHealthPanel`'s
    always-on "Observing X of Y cameras" Dashboard summary line."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeObservingEngineManager(DEMO_STREAM_ID),
    )

    response = client.get("/api/product/health")
    assert response.status_code == 200
    body = response.json()

    assert body["observation"]["monitored_stream_count"] == 1
    assert body["observation"]["configured_stream_count"] == 1
