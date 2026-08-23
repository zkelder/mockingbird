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
from tests.conftest import LegacyAuthenticatedSyncTestClient

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
def client(repository: ProductRepository) -> LegacyAuthenticatedSyncTestClient:
    return LegacyAuthenticatedSyncTestClient(app)


def _configure_camera_node(client: LegacyAuthenticatedSyncTestClient, stream_id: str = DEMO_STREAM_ID) -> None:
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
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
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
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
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
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
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


class _FakeTerminallyUnavailableEngineManager:
    """A Camera Node Stream whose bounded reconnect retries were exhausted
    (`AnalysisStreamRetryPolicy`) -- the exact terminal, unrecoverable shape
    v0.1 Release Hardening v1's aggregate-health finding is about."""

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="stopped",
            observing=False,
            message="Camera Node connection stopped: repeated failures.",
            camera_connected=False,
            camera_message="Camera Node connection stopped: repeated failures.",
            engine_available=True,
            engine_message="Ready",
            stopped_reason="camera_unavailable",
        )


class _FakeReconnectingEngineManager:
    """A Camera Node Stream mid-way through a *bounded, still-in-progress*
    reconnect. `AnalysisStreamRetryPolicy` deliberately keeps `state`
    "observing" throughout this window (never alarm on a benign,
    self-healing reconnect) -- the negative control distinguishing this
    from the genuinely terminal case above."""

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return ObservationEngineSessionStatus(
            stream_id=stream_id,
            state="observing",
            observing=True,
            message="Observing",
            camera_connected=False,
            camera_message="Reconnecting to the Camera Node... (attempt 2 of 6)",
            engine_available=True,
            engine_message="Ready",
        )


def test_dashboard_summary_flags_a_terminally_unavailable_camera_node_stream(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """v0.1 Release Hardening v1 -- 3a: the aggregate Dashboard/health
    summary must not report "Ready"/zero attention while a Camera Node
    Stream's canonical engine state is terminally unavailable. Before this
    fix, `_camera_health_summary_from_models` always evaluated a
    camera_node Stream through the legacy `StreamMonitoringPolicy` path
    (which a camera_node Stream, by design, can never `armed` through), so
    it always reported the OK-bucket `stopped` state regardless of engine
    truth -- structurally indistinguishable from a Stream the user simply
    never started observing."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeTerminallyUnavailableEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    stream_summary = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["camera_health"]["state"] == "camera_unavailable"
    assert "repeated failures" in stream_summary["camera_health"]["message"]

    health = client.get("/api/product/health").json()
    assert health["cameras"]["needs_attention_count"] == 1
    assert health["ready"] is False, (
        "a genuinely terminal Camera Node failure must raise attention, not report healthy"
    )


def test_dashboard_summary_does_not_alarm_during_a_bounded_reconnect(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negative control: a reconnect still inside its bounded retry budget
    is a deliberately quiet, self-healing state (see
    AnalysisStreamRetryPolicy) -- it must not raise aggregate attention,
    matching calm-observatory notification doctrine."""

    _configure_camera_node(client)
    monkeypatch.setattr(
        "mockingbird.api.main.get_observation_engine_session_manager",
        lambda: _FakeReconnectingEngineManager(),
    )

    dashboard = client.get("/api/dashboard/summary").json()
    stream_summary = next(s for s in dashboard["streams"] if s["stream_id"] == DEMO_STREAM_ID)
    assert stream_summary["camera_health"]["state"] != "camera_unavailable"

    health = client.get("/api/product/health").json()
    assert health["cameras"]["needs_attention_count"] == 0
    assert health["ready"] is True


def test_product_health_counts_an_observing_camera_node_stream(
    client: LegacyAuthenticatedSyncTestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same defect surfaced most visibly through `ProductHealthPanel`'s
    always-on "Observing X of Y cameras" Dashboard summary line.

    `configured_stream_count == 1` here is also v0.1 Release Hardening
    v1's own regression guard for a real edge case in the *denominator*
    fix (see `DashboardHeadline.real_stream_count`): `_configure_camera_node`
    repurposes the seeded demo Source's provider configuration in place
    (`kind` stays `SourceKind.demo` forever -- it never updates), so
    filtering the "real" count on stale `kind` alone would make this
    genuinely observing camera disappear from the denominator while it
    still counted in the numerator, producing a nonsensical observing-more-
    cameras-than-exist result (1 of 0)."""

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
