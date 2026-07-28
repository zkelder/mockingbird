import asyncio
import base64
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import subprocess
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

from mockingbird.api import main as api_main
from mockingbird.api.main import (
    app,
    configure_repository,
    get_live_camera_session_manager,
    get_source_monitor_manager,
    get_stream_live_camera_session_mjpeg,
    get_stream_local_mjpeg_bridge,
    get_stream_rtsp_mjpeg_bridge,
    get_stream_windows_dshow_mjpeg_bridge,
)
from mockingbird.api.schemas import (
    DashboardStreamRuntimeStatus,
    LivePreviewLeaseRequest,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    ZoneActivitySensitivity,
    ZoneMonitoringPolicyUpdate,
)
from mockingbird.monitoring.source_monitor import SourceMonitorOptions
from mockingbird.playback import (
    live_frame_cache,
    local_camera_bridge,
    rtsp_bridge,
    windows_camera_bridge,
)
from mockingbird.playback.live_camera_session import (
    DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES,
    _LiveCameraSession,
    _LiveActivitySession,
)
from mockingbird.playback.live_preview_leases import LivePreviewLeaseManager
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.sampler.saved_media_frames import (
    SavedMediaFrame,
    SavedMediaFrameDecodeError,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
AUTO_LIVE_STREAM_ID = "stream-live-auto-regions"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    get_live_camera_session_manager().stop_all(reason="test_reset")
    live_frame_cache.clear_all_frames()
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    get_live_camera_session_manager().stop_all(reason="test_reset")
    live_frame_cache.clear_all_frames()
    configure_repository(None)


@pytest.fixture(autouse=True)
def linux_local_usb_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the Linux local-USB contract consistently on every test host."""

    local_camera_status = local_camera_bridge.local_camera_status

    def status_for_linux_host(
        *,
        device: str | None,
        camera_format: str | None = None,
        platform_name: str = "linux",
        ffmpeg_available: bool | None = None,
    ) -> str:
        return local_camera_status(
            device=device,
            camera_format=camera_format,
            platform_name=platform_name,
            ffmpeg_available=ffmpeg_available,
        )

    monkeypatch.setattr(
        local_camera_bridge,
        "local_camera_status",
        status_for_linux_host,
    )


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


class FakeStdout:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    def read(self, chunk_size: int) -> bytes:
        return self._chunks.pop(0) if self._chunks else b""


class FakeFfmpegProcess:
    def __init__(self, chunks: list[bytes]) -> None:
        self.stdout = FakeStdout(chunks)
        self.terminated = False
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.terminated = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return 0

    def kill(self) -> None:
        self.killed = True


def add_stream_without_zones(
    repository: ProductRepository,
    *,
    stream_id: str = AUTO_LIVE_STREAM_ID,
) -> str:
    with repository.session_factory() as session:
        with session.begin():
            if session.get(StreamModel, stream_id) is None:
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=SOURCE_ID,
                        name="Live automatic activity stream",
                        description="Synthetic live Stream without named Zones.",
                        is_live=True,
                    )
                )
    return stream_id


def add_stream_visit_history(repository: ProductRepository, tmp_path: Path) -> None:
    """Add isolated Visit history that exercises the Stream-scoped read surface."""

    captured_at = datetime(2099, 1, 1, 12, 0, tzinfo=UTC)
    visits = [
        (
            "event-history-needs-review",
            "visit-history-needs-review",
            captured_at + timedelta(minutes=1),
            "zone-history-feeder",
            "needs_review",
            None,
            "history-needs-review.jpg",
        ),
        (
            "event-history-confirmed",
            "visit-history-confirmed",
            captured_at + timedelta(minutes=2),
            "zone-history-feeder",
            "reviewed",
            "northern_cardinal",
            "history-confirmed.jpg",
        ),
        (
            "event-history-false-positive",
            "visit-history-false-positive",
            captured_at + timedelta(minutes=3),
            "zone-history-ground",
            "reviewed",
            "false_positive",
            "history-false-positive.jpg",
        ),
        (
            "event-history-blank",
            "visit-history-blank",
            captured_at + timedelta(minutes=4),
            "zone-history-ground",
            "reviewed",
            "blank",
            "history-blank.jpg",
        ),
    ]
    other_stream_id = add_stream_without_zones(repository, stream_id="stream-history-other")
    with repository.session_factory() as session:
        with session.begin():
            session.add_all(
                [
                    ZoneModel(
                        id="zone-history-feeder",
                        stream_id=STREAM_ID,
                        name="History feeder",
                        zone_type="feeder",
                        polygon_json="[]",
                        is_active=True,
                    ),
                    ZoneModel(
                        id="zone-history-ground",
                        stream_id=STREAM_ID,
                        name="History ground",
                        zone_type="ground",
                        polygon_json="[]",
                        is_active=True,
                    ),
                ]
            )
            for event_id, visit_id, started_at, zone_id, review_status, label, filename in visits:
                local_path = tmp_path / filename
                session.add(
                    MediaAssetModel(
                        id=f"media-{visit_id}",
                        source_id=SOURCE_ID,
                        stream_id=STREAM_ID,
                        filename=filename,
                        content_type="image/jpeg",
                        media_type="image",
                        local_path=str(local_path),
                        original_filename=filename,
                        file_size_bytes=16,
                        created_at=started_at,
                        notes="Visit history fixture",
                    )
                )
                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=STREAM_ID,
                        title=f"History {visit_id}",
                        event_type="history_fixture",
                        started_at=started_at,
                        ended_at=started_at + timedelta(seconds=45),
                        primary_zone_id=zone_id,
                        review_status=review_status,
                    )
                )
                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label="unknown_bird",
                        species_guess="northern_cardinal" if label is None else None,
                        confidence=None,
                        reviewed_label=label,
                        review_status=review_status,
                        representative_media_path=str(local_path),
                    )
                )
            session.add(
                EventModel(
                    id="event-history-other-stream",
                    stream_id=other_stream_id,
                    title="Other stream Visit",
                    event_type="history_fixture",
                    started_at=captured_at + timedelta(minutes=5),
                    ended_at=None,
                    primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id="visit-history-other-stream",
                    event_id="event-history-other-stream",
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )


async def test_stream_recent_visit_history_is_scoped_bounded_and_safe(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    add_stream_visit_history(isolated_repository, tmp_path)

    bounded = await client.get(f"/api/streams/{STREAM_ID}/visits", params={"limit": 3})
    assert bounded.status_code == 200
    recent_visits = bounded.json()
    assert [visit["id"] for visit in recent_visits] == [
        "visit-history-blank",
        "visit-history-false-positive",
        "visit-history-confirmed",
    ]
    assert all(visit["stream_id"] == STREAM_ID for visit in recent_visits)
    assert "visit-history-other-stream" not in {visit["id"] for visit in recent_visits}
    assert all(
        visit["primary_evidence"]["preview_url"].startswith("/api/media/")
        for visit in recent_visits
    )
    assert str(tmp_path) not in str(recent_visits)

    invalid_limit = await client.get(f"/api/streams/{STREAM_ID}/visits", params={"limit": 51})
    assert invalid_limit.status_code == 422

    needs_review = await client.get(
        f"/api/streams/{STREAM_ID}/visits",
        params={"review_status": "needs_review"},
    )
    assert needs_review.status_code == 200
    assert "visit-history-needs-review" in {visit["id"] for visit in needs_review.json()}
    assert all(visit["review_status"] == "needs_review" for visit in needs_review.json())

    suggestion = await client.post(
        "/api/species-suggestions/mock",
        json={"visit_id": "visit-history-needs-review", "suggested_label": "blue_jay"},
    )
    assert suggestion.status_code == 201
    with_suggestion = await client.get(
        f"/api/streams/{STREAM_ID}/visits",
        params={"review_status": "needs_review"},
    )
    history_suggestion = next(
        visit
        for visit in with_suggestion.json()
        if visit["id"] == "visit-history-needs-review"
    )
    assert history_suggestion["has_suggestion"] is True
    assert history_suggestion["suggested_label"] == "blue_jay"
    assert history_suggestion["reviewed_label"] is None
    assert history_suggestion["review_status"] == "needs_review"

    ground_zone = await client.get(
        f"/api/streams/{STREAM_ID}/visits",
        params={"zone_id": "zone-history-ground"},
    )
    assert ground_zone.status_code == 200
    assert [visit["id"] for visit in ground_zone.json()[:2]] == [
        "visit-history-blank",
        "visit-history-false-positive",
    ]
    assert all(visit["zone_type"] == "ground" for visit in ground_zone.json())

    reviewed = await client.get(
        f"/api/streams/{STREAM_ID}/visits",
        params={"review_status": "reviewed"},
    )
    assert reviewed.status_code == 200
    reviewed_by_id = {visit["id"]: visit for visit in reviewed.json()}
    assert reviewed_by_id["visit-history-confirmed"]["reviewed_label"] == "northern_cardinal"
    assert reviewed_by_id["visit-history-confirmed"]["review_outcome"] == "confirmed_bird"
    assert reviewed_by_id["visit-history-false-positive"]["review_outcome"] == "false_positive"
    assert reviewed_by_id["visit-history-blank"]["review_outcome"] == "blank"

    other_stream = await client.get("/api/streams/stream-history-other/visits")
    assert other_stream.status_code == 200
    assert [visit["id"] for visit in other_stream.json()] == ["visit-history-other-stream"]

    invalid_zone_scope = await client.get(
        "/api/streams/stream-history-other/visits",
        params={"zone_id": "zone-history-ground"},
    )
    assert invalid_zone_scope.status_code == 400

    detail = await client.get("/api/visits/visit-history-confirmed/detail")
    assert detail.status_code == 200
    evidence_frames = detail.json()["evidence_frames"]
    assert len(evidence_frames) == 1
    assert evidence_frames[0]["is_primary"] is True
    assert evidence_frames[0]["preview_url"] == "/api/media/media-visit-history-confirmed/file"
    assert str(tmp_path) not in str(detail.json())


def add_dashboard_today_visits(repository: ProductRepository, tmp_path: Path) -> str:
    """Create local-day truth and evidence cases for the operations Dashboard."""

    local_now = datetime.now().astimezone().replace(microsecond=0)
    records = [
        ("needs", "needs_review", None, True, 45),
        ("bird", "reviewed", "northern_mockingbird", True, 40),
        ("squirrel", "reviewed", "squirrel", True, 35),
        ("false", "reviewed", "false_positive", True, 30),
        ("blank", "reviewed", "blank", True, 25),
        ("unknown", "reviewed", "unknown_bird", False, 20),
    ]
    other_stream_id = add_stream_without_zones(repository, stream_id="stream-dashboard-other")
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                ZoneModel(
                    id="zone-dashboard-today",
                    stream_id=STREAM_ID,
                    name="Today feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
            for index, (kind, review_status, label, has_media, minutes_ago) in enumerate(records):
                started_at = local_now - timedelta(minutes=minutes_ago)
                visit_id = f"visit-dashboard-{kind}"
                local_path = tmp_path / f"dashboard-{kind}.jpg"
                if has_media:
                    session.add(
                        MediaAssetModel(
                            id=f"media-{visit_id}",
                            source_id=SOURCE_ID,
                            stream_id=STREAM_ID,
                            filename=f"dashboard-{kind}.jpg",
                            content_type="image/jpeg",
                            media_type="image",
                            local_path=str(local_path),
                            original_filename=f"dashboard-{kind}.jpg",
                            file_size_bytes=16,
                            created_at=started_at,
                            notes="Dashboard operations fixture",
                        )
                    )
                session.add(
                    EventModel(
                        id=f"event-dashboard-{kind}",
                        stream_id=STREAM_ID,
                        title=f"Dashboard {kind}",
                        event_type="dashboard_fixture",
                        started_at=started_at,
                        ended_at=started_at + timedelta(seconds=45),
                        primary_zone_id="zone-dashboard-today",
                        review_status=review_status,
                    )
                )
                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=f"event-dashboard-{kind}",
                        subject_label="unknown_bird",
                        species_guess="northern_mockingbird" if kind == "needs" else None,
                        confidence=None,
                        reviewed_label=label,
                        review_status=review_status,
                        representative_media_path=str(local_path) if has_media else None,
                    )
                )
            session.add(
                EventModel(
                    id="event-dashboard-other-needs",
                    stream_id=other_stream_id,
                    title="Other Stream Dashboard review",
                    event_type="dashboard_fixture",
                    started_at=local_now - timedelta(minutes=10),
                    ended_at=None,
                    primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id="visit-dashboard-other-needs",
                    event_id="event-dashboard-other-needs",
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                )
            )
    return local_now.isoformat()


async def test_dashboard_summary_uses_reviewed_truth_and_bounded_safe_visits(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    local_now = add_dashboard_today_visits(isolated_repository, tmp_path)
    suggestion = await client.post(
        "/api/species-suggestions/mock",
        json={"visit_id": "visit-dashboard-needs", "suggested_label": "blue_jay"},
    )
    assert suggestion.status_code == 201

    runtime = {
        STREAM_ID: DashboardStreamRuntimeStatus(
            monitoring_active=True,
            monitor_control="live_motion",
            can_stop_monitor=True,
            open_activity_session_count=2,
            ready_activity_session_count=1,
        )
    }
    summary = isolated_repository.dashboard_summary(
        runtime,
        now=datetime.fromisoformat(local_now),
    )

    expected_needs_review = sum(
        visit.review_status == ReviewStatus.needs_review
        for visit in isolated_repository.list_visits()
    )
    assert summary.headline.needs_review_visit_count == expected_needs_review
    assert summary.headline.monitored_stream_count == 1
    assert summary.headline.open_activity_session_count == 2
    assert summary.headline.reviewed_observation_count_today == 1
    assert {observation.label for observation in summary.today_observations} == {
        "northern_mockingbird"
    }
    assert "blue_jay" not in {observation.label for observation in summary.today_observations}
    assert "false_positive" not in {observation.label for observation in summary.today_observations}
    assert "blank" not in {observation.label for observation in summary.today_observations}
    assert {observation.label for observation in summary.reviewed_non_bird_activity} == {"squirrel"}

    streams_by_id = {stream.stream_id: stream for stream in summary.streams}
    assert streams_by_id[STREAM_ID].needs_review_visit_count >= 1
    assert streams_by_id["stream-dashboard-other"].needs_review_visit_count == 1
    assert streams_by_id[STREAM_ID].latest_visit is not None

    needs_by_id = {visit.id: visit for visit in summary.needs_review_visits}
    assert needs_by_id["visit-dashboard-needs"].has_suggestion is True
    assert needs_by_id["visit-dashboard-needs"].review_status == ReviewStatus.needs_review
    assert needs_by_id["visit-dashboard-other-needs"].stream_id == "stream-dashboard-other"
    assert any(visit.id == "visit-dashboard-unknown" and visit.primary_evidence is None for visit in summary.recent_activity)
    for visit in [*summary.needs_review_visits, *summary.recent_activity]:
        if visit.primary_evidence is not None:
            assert visit.primary_evidence.preview_url.startswith("/api/media/")
    assert str(tmp_path) not in summary.model_dump_json()
    assert len(summary.streams) <= 50
    assert len(summary.needs_review_visits) <= 12
    assert len(summary.today_observations) <= 12
    assert len(summary.recent_activity) <= 25
    assert [visit.activity_started_at for visit in summary.recent_activity] == sorted(
        (visit.activity_started_at for visit in summary.recent_activity),
        reverse=True,
    )

    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["headline"]["needs_review_visit_count"] == expected_needs_review
    assert payload["needs_review_visits"][0]["id"] == "visit-dashboard-other-needs"


async def test_dashboard_overview_exposes_only_safe_explicit_browser_preview_metadata(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="https://viewer:secret@camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    credentialed = await client.get("/api/dashboard/summary")
    assert credentialed.status_code == 200
    credentialed_stream = next(
        stream for stream in credentialed.json()["streams"] if stream["stream_id"] == STREAM_ID
    )
    assert credentialed_stream["live_preview"]["available"] is False
    assert "secret" not in credentialed.text
    assert "viewer" not in credentialed.text

    await configure_external_url_live_stream(
        client,
        live_stream_url="https://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )
    safe = await client.get("/api/dashboard/summary")
    assert safe.status_code == 200
    stream = next(stream for stream in safe.json()["streams"] if stream["stream_id"] == STREAM_ID)
    assert stream["live_preview"] == {
        "kind": "browser_direct",
        "available": True,
        "media_kind": "image",
        "preview_url": "https://camera.local/live.mjpg",
        "message": "Select Show live view to load this configured browser preview.",
    }
    assert stream["zone_overlays"]
    assert all(zone["stream_id"] == STREAM_ID for zone in stream["zone_overlays"])


async def test_overview_preview_lease_starts_only_an_explicit_view_and_preserves_monitoring(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCameraSessionManager:
        def __init__(self) -> None:
            self.snapshots: dict[str, SimpleNamespace] = {}
            self.started: list[object] = []
            self.stopped: list[tuple[str, str | None]] = []

        def status(self, stream_id: str) -> SimpleNamespace | None:
            return self.snapshots.get(stream_id)

        def start(self, configuration: object) -> SimpleNamespace:
            self.started.append(configuration)
            snapshot = SimpleNamespace(status="running", monitor_running=False)
            self.snapshots[STREAM_ID] = snapshot
            return snapshot

        def stop(self, stream_id: str, *, reason: str | None = None) -> SimpleNamespace | None:
            self.stopped.append((stream_id, reason))
            return self.snapshots.pop(stream_id, None)

        def stop_all(self, *, reason: str | None = None) -> None:
            self.snapshots.clear()

    fake_camera_manager = FakeCameraSessionManager()
    preview_manager = LivePreviewLeaseManager(lease_seconds=60)
    monkeypatch.setattr(api_main, "_live_camera_session_manager", fake_camera_manager)
    monkeypatch.setattr(api_main, "_live_preview_lease_manager", preview_manager)
    monkeypatch.setattr(
        api_main,
        "_overview_preview_configuration_or_409",
        lambda stream_id: SimpleNamespace(stream_id=stream_id),
    )
    before_policy = isolated_repository.get_stream_monitoring_policy(STREAM_ID)
    before_counts = (
        len(isolated_repository.list_events()),
        len(isolated_repository.list_visits()),
        len(isolated_repository.list_media_assets()),
    )
    owner = LivePreviewLeaseRequest(owner_id="overview-browser-owner")

    try:
        opened = await api_main.open_stream_live_preview(STREAM_ID, owner)
        repeated = await api_main.open_stream_live_preview(STREAM_ID, owner)
        closed = await api_main.close_stream_live_preview(STREAM_ID, owner)
    finally:
        preview_manager.shutdown()

    after_preview_policy = isolated_repository.get_stream_monitoring_policy(STREAM_ID)
    after_counts = (
        len(isolated_repository.list_events()),
        len(isolated_repository.list_visits()),
        len(isolated_repository.list_media_assets()),
    )
    assert opened.status == "live"
    assert opened.preview_url == f"/api/streams/{STREAM_ID}/live-session/mjpeg"
    assert repeated.status == "live"
    assert closed.released is True
    assert len(fake_camera_manager.started) == 1
    assert fake_camera_manager.stopped == [
        (STREAM_ID, "overview_preview_released")
    ]
    assert before_policy is not None and before_policy.mode == "off"
    assert after_preview_policy is not None and after_preview_policy.mode == "off"
    assert before_counts == after_counts

    # An armed Stream remains its durable monitor's responsibility even when
    # the overview no longer has a lease for the local camera session.
    isolated_repository.set_stream_monitoring_enabled(
        STREAM_ID,
        enabled=True,
        idempotency_key="overview-preview-preserve-armed-monitor",
    )
    fake_camera_manager.snapshots[STREAM_ID] = SimpleNamespace(
        status="running",
        monitor_running=False,
    )
    api_main._release_overview_started_session(STREAM_ID)
    armed_policy = isolated_repository.get_stream_monitoring_policy(STREAM_ID)
    assert armed_policy is not None and armed_policy.mode == "armed"
    assert fake_camera_manager.stopped == [
        (STREAM_ID, "overview_preview_released")
    ]


def test_dashboard_summary_exposes_durable_source_and_playback_classification(
    isolated_repository: ProductRepository,
) -> None:
    summary = isolated_repository.dashboard_summary(now=datetime.now().astimezone())

    demo_stream = next(item for item in summary.streams if item.source_id == SOURCE_ID)
    assert demo_stream.source_kind == SourceKind.demo
    assert demo_stream.playback_kind.value == "demo_panel"



def test_dashboard_summary_serializes_an_empty_stream_installation(
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-dashboard-empty",
                    name="Empty Dashboard Source",
                    kind=SourceKind.manual_upload.value,
                    status=SourceStatus.connected.value,
                    description="No Streams yet.",
                )
            )
    removed = isolated_repository.remove_sample_data(confirm=True)
    assert removed.removed is True

    summary = isolated_repository.dashboard_summary(now=datetime.now().astimezone())
    assert summary.headline.configured_stream_count == 0
    assert summary.headline.needs_review_visit_count == 0
    assert summary.streams == []
    assert summary.needs_review_visits == []
    assert summary.today_observations == []
    assert summary.recent_activity == []


def test_dashboard_summary_keeps_other_streams_when_one_readiness_check_fails(
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_stream_id = add_stream_without_zones(
        isolated_repository,
        stream_id="stream-dashboard-readiness-failure",
    )
    original_status = isolated_repository.get_stream_playback_status

    def status_with_one_failure(stream_id: str):
        if stream_id == other_stream_id:
            raise RuntimeError("fixture readiness failure")
        return original_status(stream_id)

    monkeypatch.setattr(isolated_repository, "get_stream_playback_status", status_with_one_failure)
    summary = isolated_repository.dashboard_summary(now=datetime.now().astimezone())
    streams_by_id = {stream.stream_id: stream for stream in summary.streams}

    assert streams_by_id[STREAM_ID].availability_status != "unavailable"
    assert streams_by_id[other_stream_id].availability_status == "unavailable"
    assert any("temporarily unavailable" in warning for warning in summary.warnings)


def test_live_frame_cache_returns_fresh_latest_frame() -> None:
    captured_at = datetime.now(UTC)
    frame_bytes = b"\xff\xd8live-frame\xff\xd9"

    frame = live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_bytes,
        captured_at=captured_at,
    )

    cached = live_frame_cache.get_latest_frame(
        STREAM_ID,
        now=captured_at + timedelta(seconds=1),
    )
    assert cached == frame
    assert cached is not None
    assert cached.frame_bytes == frame_bytes
    assert cached.age_ms(captured_at + timedelta(seconds=1)) == 1000


def test_live_frame_cache_ignores_stale_frame() -> None:
    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-frame\xff\xd9",
        captured_at=captured_at,
    )

    cached = live_frame_cache.get_latest_frame(
        STREAM_ID,
        max_age_seconds=5,
        now=captured_at + timedelta(seconds=6),
    )

    assert cached is None


def test_live_activity_evidence_selector_is_bounded_ordered_and_primary() -> None:
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    def values(index: int) -> dict[str, object]:
        captured_at = started_at + timedelta(seconds=index)
        return {
            "activity_detected": True,
            "best_frame_sequence": index,
            "best_frame_captured_at": captured_at,
            "best_frame_width": 640,
            "best_frame_height": 480,
            "best_score": float(index),
        }

    activity = _LiveActivitySession.from_detection(
        values(0),
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        region_key="zone:bounded-evidence",
        now=started_at,
        frame_bytes=b"frame-0",
        frame_content_type="image/jpeg",
    )
    for index in range(1, 36):
        activity.record_detection(
            values(index),
            now=started_at + timedelta(seconds=index),
            frame_bytes=f"frame-{index}".encode(),
            frame_content_type="image/jpeg",
        )

    frames = activity.evidence_frames(max_frames=99)

    assert 1 <= len(frames) <= DEFAULT_ACTIVITY_MAX_VISIT_EVIDENCE_FRAMES
    assert [frame.captured_at for frame in frames] == sorted(
        frame.captured_at for frame in frames
    )
    assert len({frame.frame_key for frame in frames}) == len(frames)
    assert sum(frame.is_primary for frame in frames) == 1
    assert next(frame for frame in frames if frame.is_primary).sequence == 35
    assert frames[0].sequence == 0
    assert frames[-1].sequence == 35


def blank_frame(*, width: int = 4, height: int = 4) -> list[list[int]]:
    return [[0 for _x in range(width)] for _y in range(height)]


def frame_with(
    points: list[tuple[int, int]],
    *,
    width: int = 4,
    height: int = 4,
) -> list[list[int]]:
    frame = blank_frame(width=width, height=height)
    for y, x in points:
        frame[y][x] = 255
    return frame


def test_live_frame_cache_returns_bounded_recent_frames() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    for index in range(live_frame_cache.DEFAULT_MAX_FRAMES + 3):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            f"\xff\xd8frame-{index}\xff\xd9".encode("latin1"),
            captured_at=captured_at + timedelta(seconds=index),
        )

    recent = live_frame_cache.get_recent_frames(
        STREAM_ID,
        max_age_seconds=120,
        now=captured_at + timedelta(seconds=30),
    )

    assert len(recent) == live_frame_cache.DEFAULT_MAX_FRAMES
    assert [frame.sequence for frame in recent] == list(range(4, 24))
    assert recent[-1].frame_bytes == b"\xff\xd8frame-22\xff\xd9"


def test_live_frame_cache_recent_frames_ignore_stale_frames() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-frame\xff\xd9",
        captured_at=captured_at,
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8fresh-frame\xff\xd9",
        captured_at=captured_at + timedelta(seconds=10),
    )

    recent = live_frame_cache.get_recent_frames(
        STREAM_ID,
        max_age_seconds=5,
        now=captured_at + timedelta(seconds=12),
    )

    assert [frame.frame_bytes for frame in recent] == [b"\xff\xd8fresh-frame\xff\xd9"]


def test_live_frame_cache_status_reports_recent_frame_diagnostics() -> None:
    captured_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-1\xff\xd9",
        captured_at=captured_at,
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-2\xff\xd9",
        captured_at=captured_at + timedelta(seconds=2),
    )
    newest = live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8frame-3\xff\xd9",
        captured_at=captured_at + timedelta(seconds=4),
    )

    status = live_frame_cache.get_cache_status(
        STREAM_ID,
        max_age_seconds=3,
        max_frames=3,
        now=captured_at + timedelta(seconds=5),
    )

    assert status.stream_id == STREAM_ID
    assert status.recent_frame_count == 2
    assert status.newest_frame_age_ms == 1000
    assert status.oldest_frame_age_ms == 5000
    assert status.newest_frame_sequence == newest.sequence
    assert status.buffer_capacity == 3
    assert status.fresh_enough is True
    assert status.last_frame_at == newest.captured_at


async def product_counts(client: httpx.AsyncClient) -> dict[str, int]:
    responses = {
        "events": await client.get("/api/events"),
        "visits": await client.get("/api/visits"),
        "media_assets": await client.get("/api/media"),
        "review_labels": await client.get("/api/review-labels"),
        "motion_evidence": await client.get("/api/motion/evidence"),
        "species_suggestions": await client.get("/api/species-suggestions"),
        "detection_proposals": await client.get("/api/detection-proposals"),
        "dataset_exports": await client.get("/api/dataset-exports"),
    }
    assert all(response.status_code == 200 for response in responses.values())

    return {
        "events": len(responses["events"].json()),
        "visits": len(responses["visits"].json()),
        "media_assets": len(responses["media_assets"].json()),
        "review_labels": len(responses["review_labels"].json()),
        "motion_evidence": len(responses["motion_evidence"].json()["motion_evidence"]),
        "species_suggestions": len(responses["species_suggestions"].json()["species_suggestions"]),
        "detection_proposals": len(responses["detection_proposals"].json()),
        "dataset_exports": len(responses["dataset_exports"].json()),
    }


async def dataset_coverage(client: httpx.AsyncClient) -> dict:
    response = await client.get("/api/dataset-coverage/summary")
    assert response.status_code == 200
    return response.json()


def assert_live_review_queue_item_quality(
    item: dict,
    *,
    created: dict,
    activity_session_id: str,
    detection_count: int,
    best_frame_sequence: int | None = None,
    expected_focus_crop_normalized: dict[str, float] | None = None,
    expected_focus_crop_pixels: dict[str, int] | None = None,
) -> None:
    assert item["target_type"] == "visit"
    assert item["target_id"] == created["visit_id"]
    assert item["visit_id"] == created["visit_id"]
    assert item["event_id"] == created["event_id"]
    assert item["source_id"] == SOURCE_ID
    assert item["source_name"] == "Backyard demo source"
    assert item["stream_id"] == STREAM_ID
    assert item["stream_name"] == "Backyard feeder stream"
    assert item["primary_zone_id"] == "zone-feeder"
    assert item["primary_zone_name"] == "Feeder"
    assert item["primary_zone_type"] == "feeder"
    assert item["zone_id"] == "zone-feeder"
    assert item["zone_name"] == "Feeder"
    assert item["zone_type"] == "feeder"
    assert item["best_media_asset_id"] == created["media_asset_id"]
    assert item["media_asset"]["id"] == created["media_asset_id"]
    assert item["activity_session_id"] == activity_session_id
    assert item["activity_started_at"] is not None
    assert item["activity_last_seen_at"] is not None
    assert item["detection_count"] == detection_count
    if best_frame_sequence is not None:
        assert item["best_frame_sequence"] == best_frame_sequence
    assert item["best_changed_ratio"] > 0
    assert item["best_changed_pixels"] > 0
    assert item["best_total_scored_pixels"] > 0
    assert item["effective_threshold_used"] is not None
    assert item["threshold_source"] is not None
    assert isinstance(item["fine_motion_applied"], bool)
    assert isinstance(item["image_quality_warnings"], list)
    assert item["focus_crop_available"] is True
    assert item["focus_crop_source"] == "activity"
    assert item["focus_crop_label"] == "Detected activity focus"
    assert item["focus_crop_box_normalized"] == pytest.approx(
        expected_focus_crop_normalized
        or {
            "x": 0.0,
            "y": 0.0,
            "width": 1.0,
            "height": 1.0,
        }
    )
    assert item["focus_crop_box_pixels"] == (
        expected_focus_crop_pixels
        or {
            "x": 0,
            "y": 0,
            "width": 4,
            "height": 4,
        }
    )
    assert "focus_crop_pixels_unavailable" not in item["focus_crop_warnings"]
    assert item["identification"]["focus_crop_available"] is True
    assert item["identification"]["focus_crop_box_normalized"] == item[
        "focus_crop_box_normalized"
    ]
    assert item["identification"]["focus_crop_box_pixels"] == item["focus_crop_box_pixels"]
    assert item["identification"]["creates_truth"] is False


def patch_live_motion_decoder(
    monkeypatch: pytest.MonkeyPatch,
    frames_by_bytes: dict[bytes, list[list[int]]],
) -> None:
    def fake_load_image_frame_plane_bytes(
        frame_bytes: bytes,
        *,
        content_type: str,
        max_dimension: int = 32,
    ) -> SavedMediaFrame:
        frame = frames_by_bytes[frame_bytes]
        return SavedMediaFrame(width=len(frame[0]), height=len(frame), frame=frame)

    monkeypatch.setattr(
        "mockingbird.api.main.load_image_frame_plane_bytes",
        fake_load_image_frame_plane_bytes,
    )
    monkeypatch.setattr(
        "mockingbird.api.main._source_luminance_plane",
        lambda frame_bytes: np.asarray(frames_by_bytes[frame_bytes], dtype=np.uint8),
    )


def patch_camera_processes_to_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> object:
        raise AssertionError("Live motion evaluation must not start a camera process")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.start_windows_dshow_mjpeg_process",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        fail_if_called,
    )


async def configure_external_url_live_stream(
    client: httpx.AsyncClient,
    *,
    live_stream_url: str,
    live_stream_type: str,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": live_stream_url,
                "live_stream_type": live_stream_type,
            },
        },
    )
    assert response.status_code == 200


async def configure_local_usb_camera(
    client: httpx.AsyncClient,
    *,
    device: str | None,
    camera_format: str = "v4l2",
    video_size: str | None = None,
    preview_video_size: str | None = None,
    capture_video_size: str | None = None,
    framerate: str | None = None,
    input_format: str | None = None,
    brightness: str | None = None,
    contrast: str | None = None,
    exposure: str | None = None,
    zoom_mode: str | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {
                "live_stream_type": "local_usb",
                "local_camera_device": device,
                "local_camera_format": camera_format,
                "video_size": video_size,
                "preview_video_size": preview_video_size,
                "capture_video_size": capture_video_size,
                "framerate": framerate,
                "input_format": input_format,
                "brightness": brightness,
                "contrast": contrast,
                "exposure": exposure,
                "zoom_mode": zoom_mode,
            },
        },
    )
    assert response.status_code == 200


async def configure_windows_dshow_camera(
    client: httpx.AsyncClient,
    *,
    camera_name: str | None,
    ffmpeg_binary_path: str | None = None,
    video_size: str | None = None,
    preview_video_size: str | None = None,
    capture_video_size: str | None = None,
    framerate: str | None = None,
    input_format: str | None = None,
) -> None:
    response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "local_usb",
            "config": {
                "live_stream_type": "windows_dshow",
                "windows_camera_name": camera_name,
                "ffmpeg_binary_path": ffmpeg_binary_path,
                "video_size": video_size,
                "preview_video_size": preview_video_size,
                "capture_video_size": capture_video_size,
                "framerate": framerate,
                "input_format": input_format,
            },
        },
    )
    assert response.status_code == 200


async def wait_for_live_session_frame_count(
    client: httpx.AsyncClient,
    stream_id: str,
    *,
    minimum: int,
) -> dict:
    last_status: dict | None = None
    for _index in range(40):
        response = await client.get(f"/api/streams/{stream_id}/live-session/status")
        assert response.status_code == 200
        last_status = response.json()
        if last_status["frame_count"] >= minimum:
            return last_status
        await asyncio.sleep(0.05)
    assert last_status is not None
    assert last_status["frame_count"] >= minimum
    return last_status


async def test_known_demo_stream_returns_playback_contract(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["stream_id"] == STREAM_ID
    assert playback["source_id"] == SOURCE_ID
    assert playback["status"] == "demo"
    assert playback["playback_kind"] == "demo_panel"
    assert playback["display_title"] == "Backyard feeder stream"
    assert "no real video playback" in playback["message"]
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "demo"
    assert playback["last_checked_at"] is None
    assert playback["preview_media_asset_id"] is None
    assert playback["preview_url"] is None


async def test_unknown_stream_playback_returns_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/streams/stream-missing/playback")

    assert response.status_code == 404
    assert response.json()["detail"] == "Stream 'stream-missing' was not found."


async def test_playback_contract_does_not_create_product_truth(client: httpx.AsyncClient) -> None:
    before = await product_counts(client)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    assert await product_counts(client) == before


async def test_playback_contract_does_not_claim_live_playback(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["supports_live_playback"] is False
    assert playback["playback_kind"] in {"demo_panel", "placeholder"}


async def test_live_motion_evaluation_waits_for_live_frames(client: httpx.AsyncClient) -> None:
    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "waiting_for_live_frames"
    assert result["session_status"] == "waiting_for_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["recent_frame_count"] == 0
    assert result["fresh_enough"] is False
    assert result["evaluated_at"]
    assert result["last_evaluation_message"] == result["message"]
    assert result["best_media_asset_id"] is None
    assert result["creates_truth"] is False
    assert result["creates_export"] is False


async def test_live_motion_evaluation_requires_camera_session_for_backend_camera_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "start_session_required"
    assert result["session_status"] == "waiting_for_session"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["camera_session_status"] == "stopped"
    assert result["camera_session_frame_count"] == 0
    assert result["message"] == "Start camera session before monitoring."
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert await product_counts(client) == before


async def test_live_motion_evaluation_requires_two_fresh_frames(client: httpx.AsyncClient) -> None:
    live_frame_cache.store_latest_frame(STREAM_ID, b"\xff\xd8only-frame\xff\xd9")

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "not_enough_frames"
    assert result["session_status"] == "waiting_for_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 1
    assert result["frames_considered"] == 1
    assert result["recent_frame_count"] == 1
    assert result["newest_frame_sequence"] == 1
    assert result["fresh_enough"] is False


async def test_live_motion_evaluation_reports_no_recent_frames_for_stale_cache(
    client: httpx.AsyncClient,
) -> None:
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"\xff\xd8stale-live-frame\xff\xd9",
        captured_at=datetime.now(UTC) - timedelta(seconds=30),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={"max_age_seconds": 5},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "no_recent_frames"
    assert result["session_status"] == "no_recent_frames"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 0
    assert result["frames_considered"] == 0
    assert result["recent_frame_count"] == 0
    assert result["newest_frame_age_ms"] is not None
    assert result["newest_frame_age_ms"] >= 30000
    assert result["last_frame_at"] is not None


async def test_live_motion_evaluation_reports_decode_failed(
    client: httpx.AsyncClient,
) -> None:
    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(STREAM_ID, b"not-an-image-1", captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        b"not-an-image-2",
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/live-motion/evaluate", json={})

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "decode_failed"
    assert result["session_status"] == "decode_failed"
    assert result["activity_detected"] is False
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["last_error"] == "Recent live frames could not be decoded for motion."
    assert result["last_evaluation_message"] == result["last_error"]


async def test_live_motion_evaluation_uses_cached_frames_and_saves_best_frame_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-motion-0\xff\xd9"
    frame_1 = b"\xff\xd8live-motion-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["evaluated_at"]
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["recent_frame_count"] == 2
    assert result["newest_frame_sequence"] == 2
    assert result["fresh_enough"] is True
    assert result["best_frame_sequence"] == 2
    assert result["best_media_asset_id"].startswith("media-asset-")
    assert result["can_create_review_activity"] is True
    assert result["review_activity_available"] is True
    assert result["review_activity_created"] is False
    assert result["created_evidence"] == []
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["strongest_zone_name"] == "Feeder"
    assert result["strongest_zone_type"] == "feeder"
    assert result["pixel_delta_threshold"] == 25.0
    assert result["min_changed_ratio"] == 0.1
    assert result["strongest_zone_min_changed_ratio"] == 0.05
    assert result["threshold_used"] == 0.05
    assert result["changed_pixels"] == 4
    assert result["total_pixels"] == 6
    assert result["mean_delta"] == 170.0
    assert result["frame_pair_sequences"] == [1, 2]
    assert result["feeder_threshold_applied"] is True
    assert result["focus_applied"] is False
    assert result["strongest_frame_start_sequence"] == 1
    assert result["strongest_frame_end_sequence"] == 2
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert result["session_status"] == "activity_detected"
    assert result["last_evaluation_message"] == result["message"]
    assert result["suppressed_zone_summaries"] == []

    media_response = await client.get(f"/api/media/{result['best_media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert media_asset["source_id"] == SOURCE_ID
    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == "image/jpeg"
    assert "Saved best live motion frame from active stream." in media_asset["notes"]
    assert "Creates no Events, Visits, ReviewLabels, exports, or truth." in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == frame_1

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_tracked_detector_creates_one_unverified_review_visit_without_truth(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A compact track qualifies in sub-second replay without the legacy duration gate."""

    def tracked_frame(left: int | None = None) -> list[list[int]]:
        pixels = [[0] * 640 for _ in range(360)]
        if left is not None:
            for row in range(170, 184):
                for column in range(left, left + 14):
                    pixels[row][column] = 255
        return pixels

    frames = [
        b"\xff\xd8tracked-0\xff\xd9",
        b"\xff\xd8tracked-1\xff\xd9",
        b"\xff\xd8tracked-2\xff\xd9",
        b"\xff\xd8tracked-3\xff\xd9",
    ]
    captured_at = datetime.now(UTC)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frames[0]: tracked_frame(),
            frames[1]: tracked_frame(),
            frames[2]: tracked_frame(250),
            frames[3]: tracked_frame(253),
        },
    )
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            frame,
            captured_at=captured_at + timedelta(milliseconds=index * 200),
        )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={"create_review_activity": True, "detector_preset": "high_sensitivity"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["analysis_frame_width"] == 640
    assert result["analysis_frame_height"] == 360
    assert result["motion_regions"]
    assert result["tracked_objects"]
    assert result["activity_triggers"]
    assert result["activity_triggers"][0]["verified"] is False
    assert result["event_id"]
    assert result["visit_id"]
    assert result["motion_evidence_id"]
    assert result["review_status"] == "needs_review"
    assert result["suggested_label"] is None
    assert result["suggestion_id"] is None
    assert result["creates_truth"] is False

    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["species_suggestions"] == before["species_suggestions"]


async def test_tracked_live_monitor_skips_one_malformed_frame_and_keeps_tracking(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def tracked_frame(left: int | None = None) -> list[list[int]]:
        pixels = [[0] * 640 for _ in range(360)]
        if left is not None:
            for row in range(170, 184):
                for column in range(left, left + 14):
                    pixels[row][column] = 255
        return pixels

    frames = [
        b"tracked-good-0",
        b"tracked-good-1",
        b"tracked-malformed",
        b"tracked-good-2",
        b"tracked-good-3",
    ]
    frame_planes = {
        frames[0]: tracked_frame(),
        frames[1]: tracked_frame(),
        frames[3]: tracked_frame(250),
        frames[4]: tracked_frame(253),
    }

    def decode(
        frame_bytes: bytes,
        *,
        content_type: str,
        max_dimension: int = 32,
    ) -> SavedMediaFrame:
        if frame_bytes == frames[2]:
            raise SavedMediaFrameDecodeError("synthetic malformed frame")
        frame = frame_planes[frame_bytes]
        return SavedMediaFrame(width=len(frame[0]), height=len(frame), frame=frame)

    monkeypatch.setattr("mockingbird.api.main.load_image_frame_plane_bytes", decode)
    captured_at = datetime.now(UTC)
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            frame,
            captured_at=captured_at + timedelta(milliseconds=index * 200),
        )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={"detector_preset": "high_sensitivity"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["frames_considered"] == 4
    assert result["dropped_frame_count"] >= 1
    assert result["activity_triggers"]
    assert "malformed live frames were skipped" in " ".join(result["warnings"])


async def test_live_motion_evaluation_uses_backend_session_frames_without_browser_request(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-motion-0\xff\xd9"
    frame_1 = b"\xff\xd8session-motion-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    session_status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    assert session_status["status"] == "running"

    def fail_if_started(*args: object, **kwargs: object) -> object:
        raise AssertionError("Live motion evaluation must not start another camera process")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_started,
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["session_status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["frames_available"] == 2
    assert result["frames_considered"] == 2
    assert result["camera_session_status"] == "running"
    assert result["camera_session_frame_count"] >= 2
    assert result["camera_session_latest_frame_age_ms"] >= 0
    assert result["camera_session_runtime_limit_seconds"] >= 1
    assert result["best_media_asset_id"] is None
    assert result["review_activity_created"] is False
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert await product_counts(client) == before


async def test_live_motion_evaluation_uses_strongest_recent_frame_pair(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frames = [
        b"\xff\xd8live-middle-pair-0\xff\xd9",
        b"\xff\xd8live-middle-pair-1\xff\xd9",
        b"\xff\xd8live-middle-pair-2\xff\xd9",
        b"\xff\xd8live-middle-pair-3\xff\xd9",
    ]
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frames[0]: blank_frame(),
            frames[1]: blank_frame(),
            frames[2]: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
            frames[3]: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            frame,
            captured_at=captured_at + timedelta(seconds=index),
        )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["frames_considered"] == 4
    assert len(result["frame_scores"]) == 3
    assert result["strongest_zone_id"] == "zone-feeder"
    assert result["strongest_frame_start_sequence"] == 2
    assert result["strongest_frame_end_sequence"] == 3
    assert result["best_frame_sequence"] == 3
    assert result["candidates"][0]["best_frame_index"] == 3
    assert result["best_media_asset_id"] is None
    assert result["review_activity_created"] is False
    assert result["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_decodes_live_frames_at_fine_motion_resolution(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-fine-resolution-0\xff\xd9"
    frame_1 = b"\xff\xd8live-fine-resolution-1\xff\xd9"
    captured_at = datetime.now(UTC)
    requested_max_dimensions: list[int] = []
    patch_camera_processes_to_fail(monkeypatch)

    def fake_load_image_frame_plane_bytes(
        frame_bytes: bytes,
        *,
        content_type: str,
        max_dimension: int = 32,
    ) -> SavedMediaFrame:
        requested_max_dimensions.append(max_dimension)
        assert frame_bytes in {frame_0, frame_1}
        return SavedMediaFrame(width=64, height=64, frame=blank_frame(width=64, height=64))

    monkeypatch.setattr(
        "mockingbird.api.main.load_image_frame_plane_bytes",
        fake_load_image_frame_plane_bytes,
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    assert requested_max_dimensions == [160, 160]


async def test_live_motion_bird_sized_feeder_mode_lowers_only_bird_zone_thresholds(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-small-feeder-0\xff\xd9"
    frame_1 = b"\xff\xd8live-small-feeder-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    standard_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "bird_sized_feeder_motion": False,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
        },
    )
    normal_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
        },
    )

    assert standard_response.status_code == 200
    standard = standard_response.json()
    assert standard["activity_detected"] is False
    assert standard["strongest_zone_name"] == "Feeder"
    assert standard["strongest_changed_ratio"] > 0
    assert standard["strongest_zone_min_changed_ratio"] == 0.012
    assert standard["requested_threshold"] == 0.012
    assert standard["effective_threshold_used"] == 0.012
    assert standard["threshold_source"] == "requested"
    assert standard["fine_motion_applied"] is False
    assert standard["bird_sized_feeder_motion"] is False
    assert standard["changed_pixels"] == 4
    assert standard["total_scored_pixels"] == 924

    assert normal_response.status_code == 200
    normal = normal_response.json()
    assert normal["activity_detected"] is False
    assert normal["strongest_zone_name"] == "Feeder"
    assert normal["strongest_changed_ratio"] > 0
    assert normal["strongest_zone_min_changed_ratio"] == 0.006
    assert normal["requested_threshold"] == 0.012
    assert normal["effective_threshold_used"] == 0.006
    assert normal["threshold_source"] == "bird_feeder_fine"
    assert normal["fine_motion_applied"] is True
    assert normal["bird_sized_feeder_motion"] is True
    assert normal["changed_pixels"] == 4
    assert normal["total_scored_pixels"] == 924
    assert normal["near_miss"] is True
    assert normal["margin_to_threshold"] < 0
    assert "No bird-sized activity yet" in normal["message"]
    assert "threshold 0.60%" in normal["message"]
    assert normal["strongest_frame_start_sequence"] is None
    assert normal["strongest_frame_end_sequence"] is None
    assert normal["best_media_asset_id"] is None

    high_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert high_response.status_code == 200
    high = high_response.json()
    assert high["activity_detected"] is True
    assert high["strongest_zone_name"] == "Feeder"
    assert high["strongest_zone_type"] == "feeder"
    assert high["strongest_zone_min_changed_ratio"] == pytest.approx(0.001)
    assert high["requested_threshold"] == 0.003
    assert high["effective_threshold_used"] == pytest.approx(0.001)
    assert high["threshold_used"] == pytest.approx(0.001)
    assert high["threshold_source"] == "bird_feeder_high_fine"
    assert high["fine_motion_applied"] is True
    assert high["bird_sized_feeder_motion"] is True
    assert high["changed_pixels"] == 4
    assert high["total_scored_pixels"] == 924
    assert high["near_miss"] is False
    assert high["margin_to_threshold"] > 0
    assert "Bird-sized motion detected" in high["message"]
    assert high["strongest_frame_start_sequence"] == 1
    assert high["strongest_frame_end_sequence"] == 2
    assert high["best_frame_sequence"] == 2
    assert high["best_media_asset_id"] is None
    assert high["review_activity_created"] is False
    assert high["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_does_not_broaden_small_yard_motion_thresholds(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-small-ground-0\xff\xd9"
    frame_1 = b"\xff\xd8live-small-ground-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(70, 20), (70, 21), (71, 20), (71, 21)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    normal_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
        },
    )
    high_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert normal_response.status_code == 200
    normal = normal_response.json()
    assert normal["activity_detected"] is False
    assert normal["strongest_zone_name"] == "Ground below feeder"
    assert normal["strongest_zone_type"] == "ground"
    assert normal["threshold_source"] == "requested"
    assert normal["fine_motion_applied"] is False
    assert normal["bird_sized_feeder_motion"] is True
    assert normal["effective_threshold_used"] == 0.012
    assert normal["changed_pixels"] == 4
    assert normal["total_scored_pixels"] == 2736

    assert high_response.status_code == 200
    high = high_response.json()
    assert high["activity_detected"] is False
    assert high["strongest_zone_name"] == "Ground below feeder"
    assert high["strongest_zone_type"] == "ground"
    assert high["threshold_source"] == "requested"
    assert high["fine_motion_applied"] is False
    assert high["bird_sized_feeder_motion"] is True
    assert high["effective_threshold_used"] == 0.003
    assert high["effective_threshold_used"] > 0.001
    assert await product_counts(client) == before


async def test_live_motion_focus_zone_limits_scoring_region(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-focus-zone-0\xff\xd9"
    frame_1 = b"\xff\xd8live-focus-zone-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(3, 1), (3, 2), (3, 3)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    unfocused_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )
    assert unfocused_response.status_code == 200
    unfocused = unfocused_response.json()
    assert unfocused["activity_detected"] is True
    assert unfocused["strongest_zone_id"] == "zone-ground"
    assert unfocused["focus_applied"] is False

    focused_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "focus_zone_id": "zone-feeder",
        },
    )
    assert focused_response.status_code == 200
    focused = focused_response.json()
    assert focused["activity_detected"] is False
    assert focused["focus_applied"] is True
    assert focused["focus_zone_id"] == "zone-feeder"
    assert focused["focus_zone_name"] == "Feeder"
    assert focused["strongest_zone_id"] == "zone-feeder"
    assert focused["threshold_used"] == 0.025
    assert focused["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_reports_simple_image_quality_warnings(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-overexposed-0\xff\xd9"
    frame_1 = b"\xff\xd8live-overexposed-1\xff\xd9"
    captured_at = datetime.now(UTC)
    overexposed_frame = [[250 for _x in range(8)] for _y in range(8)]
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: overexposed_frame,
            frame_1: overexposed_frame,
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert any("overexposed" in warning for warning in result["image_quality_warnings"])
    assert any("low contrast" in warning for warning in result["image_quality_warnings"])
    assert result["image_quality_warnings"][0] in result["warnings"]
    assert result["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_review_handoff_creates_needs_review_candidate(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-review-0\xff\xd9"
    frame_1 = b"\xff\xd8live-review-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)
    before_coverage = await dataset_coverage(client)
    before_queue = (await client.get("/api/review-queue")).json()

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "activity_detected"
    assert result["activity_detected"] is True
    assert result["session_status"] == "activity_detected"
    assert result["review_activity_created"] is True
    assert result["review_activity_reused"] is False
    assert result["review_activity_already_exists"] is False
    assert result["review_activity_available"] is False
    assert result["motion_evidence_id"].startswith("motion-evidence-")
    assert result["event_id"].startswith("event-motion-")
    assert result["visit_id"].startswith("visit-motion-")
    assert result["review_queue_item_id"] == f"review-queue-{result['visit_id']}"
    assert result["review_status"] == "needs_review"
    assert result["suggested_label"] == "unknown_bird"
    assert result["suggestion_id"].startswith("species-suggestion-")
    assert result["suggestion_confidence"] == 0.30
    assert "Low-confidence live motion suggestion from Feeder Zone context" in (
        result["suggestion_reason"]
    )
    assert result["suggestion_creates_truth"] is False
    assert result["creates_event"] is True
    assert result["creates_visit"] is True
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["strongest_zone_name"] == "Feeder"
    assert result["strongest_zone_type"] == "feeder"
    assert result["pixel_delta_threshold"] == 25.0
    assert result["min_changed_ratio"] == 0.1
    assert result["strongest_zone_min_changed_ratio"] == 0.05
    assert result["strongest_frame_start_sequence"] == 1
    assert result["strongest_frame_end_sequence"] == 2
    assert result["activity_summary"] == "Activity detected in Feeder."
    assert "Review activity created for Feeder" in result["message"]
    assert len(result["created_evidence"]) == 1
    evidence = result["created_evidence"][0]
    assert evidence["id"] == result["motion_evidence_id"]
    assert evidence["status"] == "promoted"
    assert evidence["zone_id"] == "zone-feeder"
    assert evidence["snapshot_media_asset_id"] == result["best_media_asset_id"]
    assert evidence["promoted_event_id"] == result["event_id"]
    assert evidence["promoted_visit_id"] == result["visit_id"]

    queue_response = await client.get("/api/review-queue")
    assert queue_response.status_code == 200
    queue = queue_response.json()
    assert len(queue) == len(before_queue) + 1
    queue_item = next(item for item in queue if item["id"] == result["review_queue_item_id"])
    assert queue_item["item_type"] == "visit"
    assert queue_item["stream_id"] == STREAM_ID
    assert queue_item["event_id"] == result["event_id"]
    assert queue_item["visit_id"] == result["visit_id"]
    assert queue_item["primary_zone_id"] == "zone-feeder"
    assert queue_item["primary_zone_name"] == "Feeder"
    assert queue_item["primary_zone_type"] == "feeder"
    assert queue_item["suggested_label"] == "unknown_bird"
    assert queue_item["suggestion_id"] == result["suggestion_id"]
    assert queue_item["suggestion_confidence"] == 0.30
    assert "Confirm or correct in Review Queue" in queue_item["suggestion_reason"]
    assert queue_item["suggestion_creates_truth"] is False
    assert queue_item["review_status"] == "needs_review"
    assert queue_item["media_asset"]["id"] == result["best_media_asset_id"]

    suggestions_response = await client.get(
        "/api/species-suggestions",
        params={"visit_id": result["visit_id"]},
    )
    assert suggestions_response.status_code == 200
    suggestions = suggestions_response.json()["species_suggestions"]
    assert len(suggestions) == 1
    suggestion = suggestions[0]
    assert suggestion["id"] == result["suggestion_id"]
    assert suggestion["suggested_label"] == "unknown_bird"
    assert suggestion["confidence"] == 0.30
    assert suggestion["status"] == "pending"
    assert suggestion["media_asset_id"] == result["best_media_asset_id"]
    assert suggestion["motion_evidence_id"] == result["motion_evidence_id"]

    event_detail_response = await client.get(f"/api/events/{result['event_id']}/detail")
    assert event_detail_response.status_code == 200
    event_detail = event_detail_response.json()
    assert event_detail["event"]["title"] == "Live motion activity in Feeder"
    assert event_detail["primary_zone"]["name"] == "Feeder"
    assert event_detail["primary_zone"]["zone_type"] == "feeder"

    visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert visit_detail_response.status_code == 200
    visit_detail = visit_detail_response.json()
    assert visit_detail["visit"]["subject_label"] == "unknown_bird"
    assert visit_detail["visit"]["confidence"] is None
    assert visit_detail["visit"]["reviewed_label"] is None
    assert visit_detail["visit"]["review_status"] == "needs_review"
    assert visit_detail["media_asset"]["id"] == result["best_media_asset_id"]

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["species_suggestions"] == before["species_suggestions"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]
    after_coverage = await dataset_coverage(client)
    assert after_coverage["reviewed_record_count"] == before_coverage["reviewed_record_count"]

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": result["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed live motion review candidate.",
        },
    )

    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_id"] == result["visit_id"]
    assert correction["visit"]["review_status"] == "reviewed"
    assert correction["visit"]["reviewed_label"] == "northern_cardinal"
    corrected_visit_detail_response = await client.get(f"/api/visits/{result['visit_id']}/detail")
    assert corrected_visit_detail_response.status_code == 200
    corrected_visit_detail = corrected_visit_detail_response.json()
    assert corrected_visit_detail["primary_zone"]["name"] == "Feeder"
    assert corrected_visit_detail["primary_zone"]["zone_type"] == "feeder"
    assert corrected_visit_detail["media_asset"]["id"] == result["best_media_asset_id"]
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after["review_labels"] + 1
    assert corrected_counts["species_suggestions"] == after["species_suggestions"]
    corrected_coverage = await dataset_coverage(client)
    assert (
        corrected_coverage["reviewed_record_count"]
        == before_coverage["reviewed_record_count"] + 1
    )
    corrected_queue = (await client.get("/api/review-queue")).json()
    assert all(item["id"] != result["review_queue_item_id"] for item in corrected_queue)


async def test_live_motion_auto_region_reaches_review_without_named_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    isolated_repository: ProductRepository,
) -> None:
    stream_id = add_stream_without_zones(isolated_repository)
    frame_0 = b"\xff\xd8live-auto-review-0\xff\xd9"
    frame_1 = b"\xff\xd8live-auto-review-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(y, x) for y in range(28, 32) for x in range(39, 43)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(stream_id, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        stream_id,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)
    before_coverage = await dataset_coverage(client)

    response = await client.post(
        f"/api/streams/{stream_id}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.0003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["uses_auto_regions"] is True
    assert result["can_create_review_activity"] is True
    assert result["review_activity_created"] is True
    assert result["suggested_label"] is None
    assert result["suggestion_id"] is None
    assert len(result["created_evidence"]) == 1
    evidence = result["created_evidence"][0]
    assert evidence["zone_id"] is None
    assert evidence["stream_id"] == stream_id
    assert evidence["status"] == "promoted"
    assert evidence["scoring_config"]["activity_region_kind"] == "auto_area"
    assert evidence["scoring_config"]["activity_region_id"]

    queue = (await client.get("/api/review-queue")).json()
    queue_item = next(item for item in queue if item["visit_id"] == result["visit_id"])
    assert queue_item["primary_zone_id"] is None
    assert queue_item["zone_id"] is None
    assert queue_item["focus_crop_source"] == "activity"
    assert queue_item["review_status"] == "needs_review"

    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]
    after_coverage = await dataset_coverage(client)
    assert after_coverage["reviewed_record_count"] == before_coverage["reviewed_record_count"]
    assert after_coverage["export_ready_count"] == before_coverage["export_ready_count"]
    zones_response = await client.get(f"/api/streams/{stream_id}/zones")
    assert zones_response.status_code == 200
    assert zones_response.json() == []



async def test_camera_node_motion_does_not_require_a_zone_or_available_detector(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A configured evidence profile may enrich a Visit, never gate its motion."""

    stream_id = add_stream_without_zones(isolated_repository, stream_id="stream-motion-first")
    frames = [
        b"\xff\xd8motion-first-0\xff\xd9",
        b"\xff\xd8motion-first-1\xff\xd9",
        b"\xff\xd8motion-first-2\xff\xd9",
        b"\xff\xd8motion-first-3\xff\xd9",
    ]
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frames[0]: blank_frame(width=100, height=100),
            frames[1]: blank_frame(width=100, height=100),
            frames[2]: frame_with(
                [(y, x) for y in range(30, 35) for x in range(62, 67)],
                width=100,
                height=100,
            ),
            frames[3]: frame_with(
                [(y, x) for y in range(30, 35) for x in range(65, 70)],
                width=100,
                height=100,
            ),
        },
    )
    # This is deliberately only a local configuration shape. No Camera Node
    # call is made; unavailable enrichment cannot suppress monitoring motion.
    monkeypatch.setattr(
        isolated_repository,
        "get_stream_live_playback_config",
        lambda _stream_id: SimpleNamespace(
            provider_key="camera_node",
            live_stream_type="camera_node",
            camera_node_monitoring_profile_id="monitoring-profile",
            camera_node_evidence_profile_id="evidence-profile",
        ),
    )
    monkeypatch.setattr(
        api_main,
        "_live_object_detector_result",
        lambda **_kwargs: (
            api_main.ObjectDetectorSnapshot(
                runtime_state="unavailable",
                model_configuration_state="not_configured",
                unavailable_reason="model_unavailable",
            ),
            {
                "zone_id": None,
                "source_width": None,
                "source_height": None,
                "input_width": None,
                "input_height": None,
            },
        ),
    )
    captured_at = datetime.now(UTC)
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            stream_id,
            frame,
            captured_at=captured_at + timedelta(milliseconds=index * 200),
        )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{stream_id}/live-motion/evaluate",
        json={"create_review_activity": True, "detector_preset": "high_sensitivity"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["object_detector_available"] is False
    assert result["object_detector_unavailable_reason"] == "model_unavailable"
    assert result["event_id"]
    assert result["visit_id"]
    assert result["motion_evidence_id"]
    assert result["strongest_zone_id"] is None
    assert result["creates_truth"] is False
    evidence = result["created_evidence"][0]
    assert evidence["zone_id"] is None
    assert evidence["scoring_config"]["activity_region_kind"] == "stream"
    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["review_labels"] == before["review_labels"]


async def test_whole_stream_motion_outside_feeder_creates_unzoned_visit(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normal Zone geometry is post-detection context, not the motion gate."""

    frames = [
        b"\xff\xd8outside-feeder-0\xff\xd9",
        b"\xff\xd8outside-feeder-1\xff\xd9",
        b"\xff\xd8outside-feeder-2\xff\xd9",
        b"\xff\xd8outside-feeder-3\xff\xd9",
    ]
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frames[0]: blank_frame(width=100, height=100),
            frames[1]: blank_frame(width=100, height=100),
            # Right of the partial feeder and above the ground Zone.
            frames[2]: frame_with(
                [(y, x) for y in range(16, 21) for x in range(78, 83)],
                width=100,
                height=100,
            ),
            frames[3]: frame_with(
                [(y, x) for y in range(16, 21) for x in range(81, 86)],
                width=100,
                height=100,
            ),
        },
    )
    captured_at = datetime.now(UTC)
    for index, frame in enumerate(frames):
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            frame,
            captured_at=captured_at + timedelta(milliseconds=index * 200),
        )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={"create_review_activity": True, "detector_preset": "high_sensitivity"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is True
    assert result["strongest_zone_id"] is None
    assert result["strongest_zone_name"] is None
    assert result["event_id"]
    assert result["visit_id"]
    assert result["creates_truth"] is False
    evidence = result["created_evidence"][0]
    assert evidence["zone_id"] is None
    assert evidence["scoring_config"]["activity_region_kind"] == "stream"
    after = await product_counts(client)
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["review_labels"] == before["review_labels"]

async def test_live_motion_review_handoff_suggests_unknown_animal_for_ground_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-ground-review-0\xff\xd9"
    frame_1 = b"\xff\xd8live-ground-review-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(3, 1), (3, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["review_activity_created"] is True
    assert result["strongest_zone_name"] == "Ground below feeder"
    assert result["strongest_zone_type"] == "ground"
    assert result["suggested_label"] == "unknown_animal"
    assert result["suggestion_confidence"] == 0.25
    assert result["suggestion_creates_truth"] is False

    queue = (await client.get("/api/review-queue")).json()
    queue_item = next(item for item in queue if item["id"] == result["review_queue_item_id"])
    assert queue_item["primary_zone_type"] == "ground"
    assert queue_item["suggested_label"] == "unknown_animal"
    assert queue_item["suggestion_id"] == result["suggestion_id"]
    assert queue_item["suggestion_confidence"] == 0.25
    assert queue_item["suggestion_creates_truth"] is False

    after = await product_counts(client)
    assert after["species_suggestions"] == before["species_suggestions"] + 1
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]


async def test_live_motion_reports_ignored_zone_without_review_activity(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-ignore-0\xff\xd9"
    frame_1 = b"\xff\xd8live-ignore-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(0, 0)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert result["status"] == "no_activity"
    assert result["review_activity_created"] is False
    assert result["review_activity_available"] is False
    assert result["best_media_asset_id"] is None
    assert result["motion_evidence_id"] is None
    assert result["event_id"] is None
    assert result["visit_id"] is None
    assert result["suggestion_id"] is None
    assert result["suggested_label"] is None
    assert result["suggestion_confidence"] is None
    assert result["suggestion_creates_truth"] is False
    assert result["creates_event"] is False
    assert result["creates_visit"] is False
    assert result["creates_truth"] is False
    assert result["creates_export"] is False
    assert result["activity_summary"] == "Motion ignored in Driveway edge ignore zone."
    assert result["message"] == "Motion ignored in Driveway edge ignore zone."
    assert len(result["suppressed_zone_summaries"]) == 1
    suppressed = result["suppressed_zone_summaries"][0]
    assert suppressed["zone_id"] == "zone-ignore-driveway-edge"
    assert suppressed["zone_name"] == "Driveway edge ignore zone"
    assert suppressed["zone_type"] == "ignore"
    assert suppressed["reason"] == "ignore_zone"
    assert await product_counts(client) == before


async def test_live_motion_suppresses_candidate_when_ignore_zone_is_strongest(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-ignore-strongest-0\xff\xd9"
    frame_1 = b"\xff\xd8live-ignore-strongest-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [
                    (30, 40),
                    (30, 41),
                    (31, 40),
                    (31, 41),
                    (20, 1),
                    (20, 2),
                    (20, 3),
                    (20, 4),
                    (20, 5),
                    (20, 6),
                    (20, 7),
                    (20, 8),
                    (20, 9),
                    (20, 10),
                ],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "bird_sized_feeder_motion": True,
            "min_changed_ratio": 0.001,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert result["review_activity_created"] is False
    assert result["motion_evidence_id"] is None
    assert result["event_id"] is None
    assert result["visit_id"] is None
    assert result["best_media_asset_id"] is None
    assert result["strongest_zone_id"] == "zone-ignore-driveway-edge"
    assert result["activity_summary"] == "Motion ignored in Driveway edge ignore zone."
    assert any(
        "review candidate suppressed" in warning for warning in result["warnings"]
    )
    assert result["creates_truth"] is False
    assert await product_counts(client) == before


async def test_live_motion_review_handoff_reuses_existing_review_candidate(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-review-duplicate-0\xff\xd9"
    frame_1 = b"\xff\xd8live-review-duplicate-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    after_first = await product_counts(client)
    queue_after_first = (await client.get("/api/review-queue")).json()

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["review_activity_created"] is False
    assert duplicate["review_activity_reused"] is True
    assert duplicate["review_activity_already_exists"] is True
    assert duplicate["session_status"] == "cooldown"
    assert duplicate["existing_review_activity_reference"] == first["motion_evidence_id"]
    assert duplicate["cooldown_remaining_seconds"] is not None
    assert duplicate["best_media_asset_id"] is None
    assert duplicate["motion_evidence_id"] == first["motion_evidence_id"]
    assert duplicate["event_id"] == first["event_id"]
    assert duplicate["visit_id"] == first["visit_id"]
    assert duplicate["review_queue_item_id"] == first["review_queue_item_id"]
    assert duplicate["suggestion_id"] == first["suggestion_id"]
    assert duplicate["suggested_label"] == first["suggested_label"]
    assert duplicate["suggestion_confidence"] == first["suggestion_confidence"]
    assert duplicate["suggestion_creates_truth"] is False

    after_duplicate = await product_counts(client)
    assert after_duplicate["motion_evidence"] == after_first["motion_evidence"]
    assert after_duplicate["media_assets"] == after_first["media_assets"]
    assert after_duplicate["events"] == after_first["events"]
    assert after_duplicate["visits"] == after_first["visits"]
    assert after_duplicate["species_suggestions"] == after_first["species_suggestions"]
    assert after_duplicate["review_labels"] == after_first["review_labels"]
    queue_after_duplicate = (await client.get("/api/review-queue")).json()
    assert queue_after_duplicate == queue_after_first


async def test_external_url_without_live_stream_reports_needs_stream_url(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {"url": "http://camera.local/still.jpg"},
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "needs_stream_url"
    assert playback["playback_kind"] == "external_url"
    assert playback["message"] == "No live stream URL configured."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"
    assert playback["live_stream_url_display"] is None


async def test_external_url_mjpeg_live_stream_reports_browser_ready_and_redacts_display(
    client: httpx.AsyncClient,
) -> None:
    live_url = "http://viewer:secret@camera.local/live.mjpg"
    await configure_external_url_live_stream(
        client,
        live_stream_url=live_url,
        live_stream_type="mjpeg",
    )

    configuration_response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")
    assert configuration_response.status_code == 200
    configuration = configuration_response.json()
    assert configuration["supports_live_playback"] is True
    assert configuration["safe_config_preview"]["live_stream_url"] == (
        "http://***:***@camera.local/live.mjpg"
    )
    assert "secret" not in str(configuration)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "mjpeg"
    assert playback["supports_live_playback"] is True
    assert playback["preview_url"] == live_url
    assert playback["live_stream_type"] == "mjpeg"
    assert playback["live_stream_url_display"] == "http://***:***@camera.local/live.mjpg"
    assert "secret" not in playback["live_stream_url_display"]


async def test_external_url_rtsp_live_stream_reports_bridge_required(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_rtsp_bridge_required"
    assert playback["playback_kind"] == "rtsp"
    assert playback["message"] == "RTSP bridge unavailable - ffmpeg not found."
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "rtsp"
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is False
    assert playback["rtsp_bridge_status"] == "ffmpeg_missing"


async def test_external_url_rtsp_live_stream_reports_bridge_available(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://viewer:secret@camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "rtsp"
    assert playback["supports_live_playback"] is True
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "rtsp"
    assert playback["live_stream_url_display"] == "rtsp://***:***@camera.local/live"
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is True
    assert playback["rtsp_bridge_status"] == "available"
    assert playback["bridged_mjpeg_url"] == f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg"
    assert "secret" not in playback["live_stream_url_display"]


async def test_external_url_rtsp_live_stream_rejects_invalid_rtsp_url(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/not-rtsp",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_rtsp_bridge_required"
    assert playback["supports_live_playback"] is False
    assert playback["rtsp_bridge_required"] is True
    assert playback["rtsp_bridge_available"] is False
    assert playback["rtsp_bridge_status"] == "unsupported_url"
    assert playback["bridged_mjpeg_url"] is None


async def test_rtsp_bridge_endpoint_rejects_non_rtsp_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "RTSP bridge requires RTSP stream type."


async def test_rtsp_bridge_endpoint_rejects_missing_live_stream_url(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={"provider_key": "external_url", "config": {"url": "http://camera.local/still.jpg"}},
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "Live stream URL is not configured."


async def test_rtsp_bridge_endpoint_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/rtsp-mjpeg")

    assert response.status_code == 503
    assert response.json()["detail"] == "RTSP bridge unavailable: ffmpeg not found."


async def test_rtsp_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8mock-jpeg\xff\xd9"
    fake_process = object()
    started_urls: list[str] = []

    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        lambda url: started_urls.append(url) or fake_process,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame]
        ),
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://viewer:secret@camera.local/live",
        live_stream_type="rtsp",
    )
    before = await product_counts(client)

    response = await get_stream_rtsp_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type.startswith("multipart/x-mixed-replace")
    assert response.background is None
    assert response.headers["content-type"].startswith("multipart/x-mixed-replace")
    assert started_urls == ["rtsp://viewer:secret@camera.local/live"]
    assert await product_counts(client) == before


async def test_playback_status_does_not_start_rtsp_bridge_process(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.rtsp_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fail_if_started(url: str):  # noqa: ANN202
        raise AssertionError("Playback status must not start ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.rtsp_bridge.start_rtsp_mjpeg_process",
        fail_if_started,
    )
    await configure_external_url_live_stream(
        client,
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


def test_rtsp_bridge_command_and_redaction_do_not_drop_credentials() -> None:
    url = "rtsp://viewer:secret@camera.local/live"

    command = rtsp_bridge.build_rtsp_mjpeg_command(url)

    assert command[:7] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
    ]
    assert url in command
    assert rtsp_bridge.redact_url(url) == "rtsp://***:***@camera.local/live"
    assert rtsp_bridge.validate_rtsp_url(url) is True
    assert rtsp_bridge.validate_rtsp_url("rtsps://camera.local/live") is True
    assert rtsp_bridge.validate_rtsp_url("http://camera.local/live") is False


def test_rtsp_bridge_multipart_generator_stops_process() -> None:
    fake_process = FakeFfmpegProcess([b"noise", b"\xff\xd8frame-one\xff\xd9tail"])

    chunks = list(rtsp_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 1
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_emits_two_frames_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8frame-one\xff\xd9middle\xff\xd8frame",
            b"-two\xff\xd9tail",
        ]
    )

    chunks = list(local_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 2
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"Content-Length: " in chunks[0]
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert chunks[0].endswith(b"\r\n")
    assert chunks[1].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-two\xff\xd9" in chunks[1]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_cleans_up_when_no_frames_arrive() -> None:
    fake_process = FakeFfmpegProcess([b"not-a-jpeg-frame"])

    chunks = list(local_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert chunks == []
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_local_camera_multipart_generator_updates_latest_frame_cache() -> None:
    fake_process = FakeFfmpegProcess([b"noise\xff\xd8local-live-frame\xff\xd9"])

    chunks = list(
        local_camera_bridge.iter_multipart_mjpeg(
            fake_process,
            on_frame=lambda frame: live_frame_cache.store_latest_frame(STREAM_ID, frame),
        )
    )

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert len(chunks) == 1
    assert cached is not None
    assert cached.frame_bytes == b"\xff\xd8local-live-frame\xff\xd9"


async def test_local_usb_playback_reports_not_configured_without_device(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(client, device=None)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "local_usb"
    assert playback["message"] == "Choose a local camera device such as /dev/video0."
    assert playback["supports_live_playback"] is False
    assert playback["live_stream_type"] == "local_usb"
    assert playback["local_camera_status"] == "device_missing"
    assert playback["local_camera_bridge_available"] is False
    assert playback["bridged_mjpeg_url"] is None


async def test_local_usb_playback_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unavailable"
    assert playback["playback_kind"] == "local_usb"
    assert playback["message"] == "Local camera bridge unavailable - ffmpeg not found."
    assert playback["local_camera_status"] == "ffmpeg_missing"
    assert playback["local_camera_bridge_available"] is False
    assert playback["local_camera_device_display"] == "/dev/video0"


async def test_local_usb_playback_rejects_invalid_device_path(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/tmp/not-a-camera")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "playback_error"
    assert playback["message"] == "Local camera device path must look like /dev/video0."
    assert playback["local_camera_status"] == "invalid_device"
    assert playback["supports_live_playback"] is False


async def test_local_usb_playback_reports_bridge_available(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "local_usb"
    assert playback["supports_live_playback"] is True
    assert playback["local_camera_status"] == "available"
    assert playback["local_camera_bridge_available"] is True
    assert playback["local_camera_device_display"] == "/dev/video0"
    assert playback["bridged_mjpeg_url"] == f"/api/streams/{STREAM_ID}/live/local-mjpeg"


async def test_local_camera_bridge_endpoint_rejects_non_local_usb_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Local camera bridge requires a local_usb Source provider."
    )


async def test_local_camera_bridge_endpoint_rejects_unsafe_device_path(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    await configure_local_usb_camera(client, device="/home/user/webcam")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == "Local camera device path must look like /dev/video0."


async def test_local_camera_bridge_endpoint_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: False,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/local-mjpeg")

    assert response.status_code == 503
    assert response.json()["detail"] == "Local camera bridge unavailable: ffmpeg not found."


async def test_local_camera_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = object()
    started_devices: list[str] = []

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: started_devices.append(device) or fake_process,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [b"--frame\r\nContent-Type: image/jpeg\r\n\r\njpeg"]
        ),
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    response = await get_stream_local_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert response.headers["content-type"] == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert started_devices == ["/dev/video0"]
    assert await product_counts(client) == before


async def test_live_camera_session_start_reuses_single_reader_and_reports_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_frame = b"\xff\xd8session-frame-one\xff\xd9"
    fake_process = FakeFfmpegProcess([b"noise" + session_frame])
    started_devices: list[str] = []
    started_kwargs: list[dict[str, object]] = []

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        started_devices.append(device)
        started_kwargs.append(dict(kwargs))
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        preview_video_size="1280x720",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
        brightness="driver-app",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")

    assert response.status_code == 200
    started = response.json()
    assert started["stream_id"] == STREAM_ID
    assert started["source_id"] == SOURCE_ID
    assert started["playback_kind"] == "local_usb"
    assert started["status"] == "running"
    assert started["persistent"] is False
    assert started["max_runtime_seconds"] >= 1
    assert started["camera_settings"]["input_format"] == "mjpeg"
    assert started["camera_settings"]["preview_video_size"] == "1280x720"
    assert started["camera_settings"]["capture_video_size"] == "1920x1080"
    assert started["camera_settings"]["brightness"] == "driver-app"
    assert started["message"] == (
        "Camera session is running. Live view, capture, and monitoring share these frames."
    )

    status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)
    assert status["status"] == "running"
    assert status["frame_count"] >= 1
    assert status["last_frame_at"] is not None
    assert status["latest_frame_age_ms"] >= 0
    assert status["clients_connected"] == 0
    assert status["persistent"] is False

    duplicate_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "running"
    assert duplicate["frame_count"] >= 1
    assert started_devices == ["/dev/video0"]
    assert started_kwargs[0]["input_format"] == "mjpeg"
    assert started_kwargs[0]["video_size"] == "1280x720"
    assert started_kwargs[0]["input_frame_rate"] == "15"

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")

    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["stop_reason"] == "user_stopped"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert await product_counts(client) == before


async def test_current_frame_endpoint_returns_cached_frame_with_safe_metadata_and_no_writes(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)
    encoded, frame_bytes = api_main.cv2.imencode(
        ".jpg",
        np.zeros((1440, 1920, 3), dtype=np.uint8),
    )
    assert encoded is True
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_bytes.tobytes(),
        captured_at=datetime.now(UTC),
    )
    monkeypatch.setattr(
        api_main,
        "_live_camera_session_manager",
        SimpleNamespace(status=lambda stream_id: SimpleNamespace(status="running")),
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live-session/current-frame")

    assert response.status_code == 200
    assert response.content.startswith(b"\xff\xd8")
    assert response.headers["cache-control"] == "no-store, max-age=0"
    assert response.headers["x-mockingbird-frame-sequence"] == "1"
    assert response.headers["x-mockingbird-frame-width"] == "1920"
    assert response.headers["x-mockingbird-frame-height"] == "1440"
    assert int(response.headers["x-mockingbird-frame-age-ms"]) >= 0
    assert await product_counts(client) == before


async def test_current_frame_endpoint_labels_stale_frames_without_starting_a_session(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await configure_local_usb_camera(client, device="/dev/video0")
    encoded, frame_bytes = api_main.cv2.imencode(
        ".jpg",
        np.zeros((4, 6, 3), dtype=np.uint8),
    )
    assert encoded is True
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_bytes.tobytes(),
        captured_at=datetime.now(UTC) - timedelta(seconds=12),
    )
    starts: list[str] = []
    monkeypatch.setattr(
        api_main,
        "_live_camera_session_manager",
        SimpleNamespace(
            status=lambda stream_id: SimpleNamespace(status="running"),
            start=lambda *_args, **_kwargs: starts.append("started"),
        ),
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live-session/current-frame")

    assert response.status_code == 200
    assert response.headers["x-mockingbird-frame-state"] == "stale"
    assert int(response.headers["x-mockingbird-frame-age-ms"]) >= 12_000
    assert starts == []




async def test_live_camera_session_mjpeg_uses_existing_session_without_new_reader(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_frame = b"\xff\xd8session-frame-one\xff\xd9"
    fake_process = FakeFfmpegProcess([session_frame])
    start_count = 0

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        nonlocal start_count
        start_count += 1
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)

    def fail_if_started(*args: object, **kwargs: object) -> object:
        raise AssertionError("Session MJPEG must not start another camera reader")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )

    response = await get_stream_live_camera_session_mjpeg(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={local_camera_bridge.MJPEG_BOUNDARY}"
    )
    stream = get_live_camera_session_manager().iter_mjpeg(STREAM_ID)
    chunk = next(stream)
    stream.close()
    assert b"Content-Type: image/jpeg" in chunk
    assert session_frame in chunk
    status = await wait_for_live_session_frame_count(client, STREAM_ID, minimum=1)
    assert status["status"] == "running"
    assert status["clients_connected"] == 0
    assert start_count == 1
    assert await product_counts(client) == before


async def test_backend_monitor_survives_hidden_live_view_until_camera_stop(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8monitor-no-activity-0\xff\xd9"
    frame_1 = b"\xff\xd8monitor-no-activity-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])
    start_count = 0

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        nonlocal start_count
        start_count += 1
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: blank_frame(),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is False
    assert monitor["status"] == "no_activity"

    stream = get_live_camera_session_manager().iter_mjpeg(STREAM_ID)
    chunk = next(stream)
    stream.close()
    assert frame_1 in chunk

    status_response = await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "running"
    assert status["clients_connected"] == 0
    assert status["monitor_running"] is True
    assert status["last_motion_result"]["status"] == "no_activity"

    stop_monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/stop"
    )
    assert stop_monitor_response.status_code == 200
    stopped_monitor = stop_monitor_response.json()
    assert stopped_monitor["status"] == "running"
    assert stopped_monitor["monitor_running"] is False
    assert fake_process.terminated is False

    restart_monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert restart_monitor_response.status_code == 200
    restarted_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert restarted_status["status"] == "running"
    assert restarted_status["monitor_running"] is True

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")

    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False
    assert stopped["stop_reason"] == "user_stopped"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert start_count == 1
    assert await product_counts(client) == before


async def test_live_motion_settings_do_not_start_camera_or_create_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_count = 0

    def fake_start(device: str, **kwargs: object) -> FakeFfmpegProcess:
        nonlocal start_count
        start_count += 1
        return FakeFfmpegProcess([])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fake_start,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/settings",
        json={
            "auto_create_review_candidates": True,
            "auto_review_quiet_seconds": 12,
            "auto_review_min_detections": 2,
        },
    )

    assert response.status_code == 200
    status = response.json()
    assert status["status"] == "stopped"
    assert status["monitor_running"] is False
    assert status["auto_create_review_candidates"] is False
    assert start_count == 0
    assert await product_counts(client) == before


async def test_live_motion_settings_update_running_monitor_without_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8settings-update-0\xff\xd9"
    frame_1 = b"\xff\xd8settings-update-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: blank_frame(),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    before = await product_counts(client)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "auto_create_review_candidates": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["auto_create_review_candidates"] is False

    settings_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/settings",
        json={
            "auto_create_review_candidates": True,
            "auto_review_quiet_seconds": 12,
            "auto_review_min_detections": 2,
        },
    )
    assert settings_response.status_code == 200
    settings = settings_response.json()
    assert settings["status"] == "running"
    assert settings["monitor_running"] is True
    assert settings["auto_create_review_candidates"] is True
    assert settings["auto_review_quiet_seconds"] == 12
    assert settings["auto_review_min_detections"] == 2
    assert await product_counts(client) == before

    status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert status["monitor_running"] is True
    assert status["auto_create_review_candidates"] is True
    assert status["auto_review_quiet_seconds"] == 12
    assert status["auto_review_min_detections"] == 2
    assert status["auto_review_created_count"] == 0
    assert await product_counts(client) == before


async def test_stored_live_activity_review_handoff_keeps_camera_running_and_truth_reviewed_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-review-activity-0\xff\xd9"
    frame_1 = b"\xff\xd8session-review-activity-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(),
            frame_1: frame_with([(1, 1), (1, 2), (2, 1), (2, 2)]),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    started = start_response.json()
    assert started["auto_create_review_candidates"] is False
    assert started["auto_review_created_count"] == 0
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    def fail_if_camera_reader_starts(*args: object, **kwargs: object) -> object:
        raise AssertionError("Monitoring/review handoff must reuse the live session frames")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_camera_reader_starts,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_camera_reader_starts,
    )

    before = await product_counts(client)
    before_queue = (await client.get("/api/review-queue")).json()
    before_labels = (await client.get("/api/review-labels")).json()

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["status"] == "activity_detected"
    assert monitor["activity_detected"] is True
    assert monitor["review_activity_available"] is True
    assert monitor["review_activity_created"] is False
    assert monitor["best_media_asset_id"] is None
    assert monitor["activity_session_id"].startswith("live-activity-")
    assert monitor["activity_detection_count"] == 1
    assert monitor["activity_best_frame_sequence"] == 2
    assert monitor["strongest_zone_name"] == "Feeder"
    assert monitor["creates_truth"] is False

    status_response = await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    assert status_response.status_code == 200
    status = status_response.json()
    assert status["status"] == "running"
    assert status["monitor_running"] is True
    assert status["current_activity_session_id"] == monitor["activity_session_id"]
    assert status["activity_detection_count"] == 1
    assert status["last_activity"]["best_media_asset_id"] is None
    assert status["last_activity"]["review_activity_created"] is False
    assert status["last_motion_result"]["review_activity_available"] is True

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "created"
    assert created["activity_detected"] is True
    assert created["review_activity_created"] is True
    assert created["review_activity_reused"] is False
    assert created["review_activity_already_exists"] is False
    assert created["activity_session_id"] == monitor["activity_session_id"]
    assert created["activity_detection_count"] == 1
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["event_id"].startswith("event-motion-")
    assert created["visit_id"].startswith("visit-motion-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["review_status"] == "needs_review"
    assert created["suggested_label"] == "unknown_bird"
    assert created["suggestion_id"].startswith("species-suggestion-")
    assert created["suggestion_confidence"] == 0.30
    assert created["creates_event"] is True
    assert created["creates_visit"] is True
    assert created["creates_truth"] is False
    assert created["creates_export"] is False

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert cached is not None
    assert cached.frame_bytes == frame_1
    post_create_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert post_create_status["status"] == "running"
    assert post_create_status["monitor_running"] is True
    assert post_create_status["frame_count"] >= 2
    assert post_create_status["last_activity"]["motion_evidence_id"] == created[
        "motion_evidence_id"
    ]
    assert post_create_status["last_motion_result"]["review_activity_created"] is True
    assert post_create_status["last_motion_result"]["review_queue_item_id"] == created[
        "review_queue_item_id"
    ]

    queue = (await client.get("/api/review-queue")).json()
    assert len(queue) == len(before_queue) + 1
    queue_item = next(item for item in queue if item["id"] == created["review_queue_item_id"])
    assert_live_review_queue_item_quality(
        queue_item,
        created=created,
        activity_session_id=monitor["activity_session_id"],
        detection_count=1,
        best_frame_sequence=2,
    )
    assert queue_item["suggested_label"] == "unknown_bird"

    after_create = await product_counts(client)
    assert after_create["media_assets"] == before["media_assets"] + 1
    assert after_create["motion_evidence"] == before["motion_evidence"] + 1
    assert after_create["events"] == before["events"] + 1
    assert after_create["visits"] == before["visits"] + 1
    assert after_create["species_suggestions"] == before["species_suggestions"] + 1
    assert after_create["review_labels"] == before["review_labels"]
    assert after_create["dataset_exports"] == before["dataset_exports"]
    labels_after_create = (await client.get("/api/review-labels")).json()
    assert labels_after_create == before_labels
    assert [
        label
        for label in labels_after_create
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ] == []

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "already_exists"
    assert duplicate["review_activity_created"] is False
    assert duplicate["review_activity_reused"] is True
    assert duplicate["review_activity_already_exists"] is True
    assert duplicate["motion_evidence_id"] == created["motion_evidence_id"]
    assert duplicate["event_id"] == created["event_id"]
    assert duplicate["visit_id"] == created["visit_id"]
    assert duplicate["review_queue_item_id"] == created["review_queue_item_id"]
    assert await product_counts(client) == after_create

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": created["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed stored live activity.",
        },
    )

    assert correction_response.status_code == 201
    correction = correction_response.json()
    assert correction["review_label"]["target_id"] == created["visit_id"]
    assert correction["visit"]["review_status"] == "reviewed"
    labels_after_correction = (await client.get("/api/review-labels")).json()
    bird_log_labels = [
        label
        for label in labels_after_correction
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ]
    assert len(bird_log_labels) == 1
    assert bird_log_labels[0]["label"] == "northern_cardinal"
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_create["review_labels"] + 1


async def test_stored_live_auto_activity_reaches_review_without_named_zone(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    isolated_repository: ProductRepository,
) -> None:
    stream_id = add_stream_without_zones(isolated_repository)
    frame_0 = b"\xff\xd8session-auto-area-0\xff\xd9"
    frame_1 = b"\xff\xd8session-auto-area-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(y, x) for y in range(28, 32) for x in range(39, 43)],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{stream_id}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, stream_id, minimum=2)
    before = await product_counts(client)

    monitor_response = await client.post(
        f"/api/streams/{stream_id}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.0003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is True
    assert monitor["review_activity_available"] is True
    assert monitor["review_activity_created"] is False
    assert monitor["activity_session_id"].startswith("live-activity-")

    create_response = await client.post(
        f"/api/streams/{stream_id}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "created"
    assert created["review_activity_created"] is True
    assert created["suggested_label"] is None
    assert created["suggestion_id"] is None

    evidence_response = await client.get(
        f"/api/motion/evidence/{created['motion_evidence_id']}"
    )
    assert evidence_response.status_code == 200
    evidence = evidence_response.json()
    assert evidence["zone_id"] is None
    assert evidence["stream_id"] == stream_id
    assert evidence["scoring_config"]["activity_region_kind"] == "auto_area"
    assert evidence["scoring_config"]["activity_region_id"]

    queue = (await client.get("/api/review-queue")).json()
    queue_item = next(item for item in queue if item["visit_id"] == created["visit_id"])
    assert queue_item["primary_zone_id"] is None
    assert queue_item["zone_id"] is None
    assert queue_item["focus_crop_source"] == "activity"
    assert queue_item["review_status"] == "needs_review"

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    assert after["motion_evidence"] == before["motion_evidence"] + 1
    assert after["events"] == before["events"] + 1
    assert after["visits"] == before["visits"] + 1
    assert after["species_suggestions"] == before["species_suggestions"]
    assert after["review_labels"] == before["review_labels"]
    assert after["dataset_exports"] == before["dataset_exports"]


async def test_unattended_monitoring_auto_creates_review_candidate_after_quiet_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8auto-review-activity-0\xff\xd9"
    frame_1 = b"\xff\xd8auto-review-activity-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    before = await product_counts(client)
    before_coverage = await dataset_coverage(client)
    before_analytics = (await client.get("/api/analytics/summary")).json()
    before_queue = (await client.get("/api/review-queue")).json()
    before_labels = (await client.get("/api/review-labels")).json()

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": True,
            "auto_create_review_candidates": True,
            "auto_review_quiet_seconds": 1,
            "auto_review_min_detections": 1,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 1.25,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is True
    assert monitor["auto_create_review_candidates"] is True
    assert monitor["auto_review_quiet_seconds"] == 1
    assert monitor["auto_review_min_detections"] == 1
    assert monitor["auto_review_created_count"] == 0
    assert monitor["review_activity_created"] is False
    assert monitor["review_queue_item_id"] is None
    assert monitor["activity_review_state"] == "waiting_for_quiet"
    assert monitor["activity_ready_for_review"] is False

    before_quiet_status = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert before_quiet_status["monitor_running"] is True
    assert before_quiet_status["auto_create_review_candidates"] is True
    assert before_quiet_status["auto_review_created_count"] == 0
    assert before_quiet_status["activity_review_activity_created"] is False
    assert before_quiet_status["activity_review_state"] == "waiting_for_quiet"
    assert (await client.get("/api/review-queue")).json() == before_queue
    assert await product_counts(client) == before

    await asyncio.sleep(4.5)

    auto_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert auto_status["status"] == "running"
    assert auto_status["monitor_running"] is True
    assert auto_status["auto_create_review_candidates"] is True
    assert auto_status["auto_review_created_count"] == 1
    assert auto_status["auto_review_last_error"] is None
    assert auto_status["last_auto_review_created_at"] is not None
    assert auto_status["activity_review_activity_created"] is True
    assert auto_status["activity_ready_for_review"] is True
    assert auto_status["activity_review_state"] == "review_candidate_created"
    assert auto_status["activity_motion_evidence_id"].startswith("motion-evidence-")
    assert auto_status["activity_event_id"].startswith("event-motion-")
    assert auto_status["activity_visit_id"].startswith("visit-motion-")
    assert (
        auto_status["activity_review_queue_item_id"]
        == f"review-queue-{auto_status['activity_visit_id']}"
    )
    assert (
        auto_status["last_auto_review_queue_item_id"]
        == auto_status["activity_review_queue_item_id"]
    )
    assert auto_status["last_motion_result"]["review_activity_created"] is True
    assert auto_status["last_motion_result"]["review_queue_item_id"] == auto_status[
        "activity_review_queue_item_id"
    ]
    assert auto_status["last_motion_result"]["best_media_asset_id"].startswith(
        "media-asset-"
    )

    queue = (await client.get("/api/review-queue")).json()
    assert len(queue) == len(before_queue) + 1
    queue_item = next(
        item for item in queue if item["id"] == auto_status["activity_review_queue_item_id"]
    )
    created = {
        "event_id": auto_status["activity_event_id"],
        "visit_id": auto_status["activity_visit_id"],
        "media_asset_id": auto_status["last_motion_result"]["best_media_asset_id"],
    }
    assert_live_review_queue_item_quality(
        queue_item,
        created=created,
        activity_session_id=monitor["activity_session_id"],
        detection_count=1,
        best_frame_sequence=2,
        expected_focus_crop_normalized={
            "x": 0.335,
            "y": 0.235,
            "width": 0.15,
            "height": 0.15,
        },
        expected_focus_crop_pixels={"x": 33, "y": 23, "width": 16, "height": 16},
    )
    assert queue_item["identification"]["creates_truth"] is False
    assert queue_item["identification"]["can_run"] is False
    assert queue_item["suggested_label"] == "unknown_bird"
    assert queue_item["suggestion_id"] is None

    after_auto = await product_counts(client)
    assert after_auto["media_assets"] == before["media_assets"] + 1
    assert after_auto["motion_evidence"] == before["motion_evidence"] + 1
    assert after_auto["events"] == before["events"] + 1
    assert after_auto["visits"] == before["visits"] + 1
    assert after_auto["species_suggestions"] == before["species_suggestions"]
    assert after_auto["review_labels"] == before["review_labels"]
    assert after_auto["detection_proposals"] == before["detection_proposals"]
    assert after_auto["dataset_exports"] == before["dataset_exports"]
    after_auto_coverage = await dataset_coverage(client)
    assert (
        after_auto_coverage["reviewed_record_count"]
        == before_coverage["reviewed_record_count"]
    )
    after_auto_analytics = (await client.get("/api/analytics/summary")).json()
    assert after_auto_analytics["species_counts"] == before_analytics["species_counts"]
    assert (await client.get("/api/review-labels")).json() == before_labels

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "already_exists"
    assert duplicate["review_activity_created"] is False
    assert duplicate["review_activity_reused"] is True
    assert duplicate["motion_evidence_id"] == auto_status["activity_motion_evidence_id"]
    assert duplicate["review_queue_item_id"] == auto_status["activity_review_queue_item_id"]
    assert await product_counts(client) == after_auto

    capture_response = await client.post(
        f"/api/streams/{STREAM_ID}/local-camera/capture-frame"
    )
    assert capture_response.status_code == 200
    capture = capture_response.json()
    assert capture["status"] == "saved"
    assert capture["capture_source"] == "live_camera_session"
    after_capture_status = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert after_capture_status["status"] == "running"
    assert after_capture_status["monitor_running"] is True

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": auto_status["activity_visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed unattended monitoring review candidate.",
        },
    )
    assert correction_response.status_code == 201
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_auto["review_labels"] + 1
    corrected_coverage = await dataset_coverage(client)
    assert (
        corrected_coverage["reviewed_record_count"]
        == before_coverage["reviewed_record_count"] + 1
    )
    corrected_analytics = (await client.get("/api/analytics/summary")).json()
    assert (
        corrected_analytics["species_counts"].get("northern_cardinal", 0)
        == before_analytics["species_counts"].get("northern_cardinal", 0) + 1
    )
    assert "northern_cardinal" in corrected_analytics["species_label_ids"]
    export_response = await client.post(
        "/api/dataset-exports",
        json={"name": "Reviewed unattended live activity", "reviewed_only": True},
    )
    assert export_response.status_code == 201
    export_manifest = export_response.json()["manifest"]
    assert any(
        record["visit_id"] == auto_status["activity_visit_id"]
        and record["label"] == "northern_cardinal"
        and record["reviewed"] is True
        for record in export_manifest["records"]
    )


async def test_unattended_monitoring_closes_each_quiet_zone_once(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A quiet Zone closes independently while another Zone remains active."""

    fake_process = FakeFfmpegProcess([])
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    started = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert started.status_code == 200

    manager = get_live_camera_session_manager()
    monitored = manager.start_monitor(
        STREAM_ID,
        lambda: {"activity_detected": False},
        interval_seconds=10,
        auto_create_review_candidates=True,
        auto_review_quiet_seconds=1,
        auto_review_min_detections=1,
    )
    assert monitored is not None
    before = await product_counts(client)
    now = datetime.now(UTC)

    def record_zone_activity(
        *,
        zone_id: str,
        zone_name: str,
        zone_type: str,
        seen_at: datetime,
        sequence: int,
        frame: bytes | None,
    ):
        return manager.record_activity_detection(
            STREAM_ID,
            {
                "region_key": f"zone:{zone_id}",
                "region_kind": "zone",
                "region_id": zone_id,
                "zone_id": zone_id,
                "zone_name": zone_name,
                "zone_type": zone_type,
                "monitoring_policy": {
                    "minimum_sustained_activity_seconds": (
                        2 if zone_type == "feeder" else 5
                    ),
                    "quiet_period_seconds": 20 if zone_type == "feeder" else 45,
                    "maximum_visit_duration_seconds": (
                        180 if zone_type == "feeder" else 360
                    ),
                    "maximum_evidence_frames": 4 if zone_type == "feeder" else 3,
                },
                "activity_detected": True,
                "last_seen_at": seen_at,
                "frames_evaluated_count": 1,
                "start_frame_sequence": sequence,
                "end_frame_sequence": sequence,
                "best_frame_sequence": sequence,
                "best_frame_captured_at": seen_at,
                "best_score": 0.8 if frame is not None else 0.7,
                "changed_ratio": 0.04,
                "changed_pixels": 40,
                "total_scored_pixels": 1000,
                "effective_threshold_used": 0.02,
                "threshold_source": "requested",
                "activity_left": 0.1,
                "activity_top": 0.2,
                "activity_right": 0.4,
                "activity_bottom": 0.5,
                "activity_changed_pixel_count": 40,
            },
            frame_bytes=frame,
            frame_content_type="image/jpeg",
            quiet_window_seconds=1,
        )

    initial_feeder = record_zone_activity(
        zone_id="zone-feeder",
        zone_name="Feeder",
        zone_type="feeder",
        seen_at=now - timedelta(seconds=60),
        sequence=9,
        frame=None,
    )
    feeder = record_zone_activity(
        zone_id="zone-feeder",
        zone_name="Feeder",
        zone_type="feeder",
        seen_at=now - timedelta(seconds=50),
        sequence=10,
        frame=b"\xff\xd8quiet-feeder\xff\xd9",
    )
    ground = record_zone_activity(
        zone_id="zone-ground",
        zone_name="Ground below feeder",
        zone_type="ground",
        seen_at=now - timedelta(seconds=2),
        sequence=11,
        frame=b"\xff\xd8active-ground\xff\xd9",
    )
    assert initial_feeder is not None
    assert feeder is not None
    assert feeder.activity_session_id == initial_feeder.activity_session_id
    assert ground is not None

    first_result = api_main._maybe_auto_create_live_review_candidate(STREAM_ID)
    assert first_result is not None
    assert first_result.review_activity_created is True
    assert first_result.activity_session_id == feeder.activity_session_id
    assert first_result.suggested_label is None
    first_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert first_status["open_activity_session_count"] == 1
    assert first_status["open_activity_zone_names"] == ["Ground below feeder"]
    assert first_status["ready_activity_session_count"] == 0
    assert first_status["latest_activity_review_queue_item_id"] == first_result.review_queue_item_id
    first_counts = await product_counts(client)
    assert first_counts["media_assets"] == before["media_assets"] + 1
    assert first_counts["motion_evidence"] == before["motion_evidence"] + 1
    assert first_counts["events"] == before["events"] + 1
    assert first_counts["visits"] == before["visits"] + 1
    assert first_counts["species_suggestions"] == before["species_suggestions"]
    assert api_main._maybe_auto_create_live_review_candidate(STREAM_ID) is None
    assert await product_counts(client) == first_counts

    # The still-open ground session gets its own eventual candidate, never a
    # duplicate of the completed feeder session.
    updated_ground = record_zone_activity(
        zone_id="zone-ground",
        zone_name="Ground below feeder",
        zone_type="ground",
        seen_at=now - timedelta(seconds=1),
        sequence=12,
        frame=b"\xff\xd8quiet-ground\xff\xd9",
    )
    assert updated_ground is not None
    assert updated_ground.activity_session_id == ground.activity_session_id

    class FutureDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            future = now + timedelta(seconds=50)
            return future if tz is not None else future.replace(tzinfo=None)

    monkeypatch.setattr(
        "mockingbird.playback.live_camera_session.datetime",
        FutureDatetime,
    )
    second_result = api_main._maybe_auto_create_live_review_candidate(STREAM_ID)
    assert second_result is not None
    assert second_result.review_activity_created is True
    assert second_result.activity_session_id == ground.activity_session_id
    assert second_result.review_queue_item_id != first_result.review_queue_item_id
    assert api_main._maybe_auto_create_live_review_candidate(STREAM_ID) is None
    second_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert second_status["open_activity_session_count"] == 0
    assert second_status["ready_activity_session_count"] == 0
    assert second_status["latest_activity_review_queue_item_id"] == second_result.review_queue_item_id
    final_counts = await product_counts(client)
    assert final_counts["media_assets"] == before["media_assets"] + 3
    assert final_counts["motion_evidence"] == before["motion_evidence"] + 2
    assert final_counts["events"] == before["events"] + 2
    assert final_counts["visits"] == before["visits"] + 2
    assert final_counts["species_suggestions"] == before["species_suggestions"]

    first_detail = (await client.get(f"/api/visits/{first_result.visit_id}/detail")).json()
    second_detail = (await client.get(f"/api/visits/{second_result.visit_id}/detail")).json()
    first_evidence_ids = {
        frame["media_asset_id"] for frame in first_detail["evidence_frames"]
    }
    second_evidence_ids = {
        frame["media_asset_id"] for frame in second_detail["evidence_frames"]
    }
    assert first_evidence_ids
    assert second_evidence_ids
    assert first_evidence_ids.isdisjoint(second_evidence_ids)


async def test_unattended_monitoring_respects_min_detection_gate(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8auto-review-min-0\xff\xd9"
    frame_1 = b"\xff\xd8auto-review-min-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    before = await product_counts(client)
    before_queue = (await client.get("/api/review-queue")).json()

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "auto_create_review_candidates": True,
            "auto_review_quiet_seconds": 1,
            "auto_review_min_detections": 2,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detection_count"] == 1
    assert monitor["review_activity_created"] is False

    await asyncio.sleep(1.1)
    status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert status["activity_ready_for_review"] is True
    assert status["activity_review_state"] == "ready_for_review"
    assert status["activity_review_activity_created"] is False
    assert status["auto_review_created_count"] == 0
    assert status["auto_review_last_error"] is None
    assert (await client.get("/api/review-queue")).json() == before_queue
    assert await product_counts(client) == before

    manual_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )
    assert manual_response.status_code == 200
    manual = manual_response.json()
    assert manual["review_activity_created"] is True
    assert manual["creates_truth"] is False
    after_manual = await product_counts(client)
    assert after_manual["motion_evidence"] == before["motion_evidence"] + 1
    assert after_manual["review_labels"] == before["review_labels"]


async def test_feeder_near_miss_starts_tentative_burst_before_confirmed_activity(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8near-miss-burst-0\xff\xd9"
    frame_1 = b"\xff\xd8near-miss-burst-1\xff\xd9"
    frame_2 = b"\xff\xd8near-miss-burst-2\xff\xd9"
    frame_3 = b"\xff\xd8near-miss-burst-3\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
            frame_2: blank_frame(width=100, height=100),
            frame_3: frame_with(
                [
                    (30, 40),
                    (30, 41),
                    (30, 42),
                    (31, 40),
                    (31, 41),
                    (31, 42),
                    (32, 40),
                    (32, 41),
                    (32, 42),
                ],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    before = await product_counts(client)

    near_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "auto_create_review_candidates": True,
            "auto_review_quiet_seconds": 30,
            "min_changed_ratio": 0.012,
            "pixel_delta_threshold": 18,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert near_response.status_code == 200
    near = near_response.json()
    assert near["activity_detected"] is False
    assert near["near_miss"] is True
    assert near["activity_session_id"].startswith("live-activity-")
    assert near["activity_detection_count"] == 0
    assert near["activity_near_miss_count"] == 1
    assert near["activity_candidate_frame_count"] == 1
    assert near["activity_saved_candidate_count"] == 0
    assert near["activity_review_state"] == "tentative_burst"
    assert near["activity_ready_for_review"] is False
    assert near["activity_manual_review_needed"] is False
    assert near["review_activity_available"] is False
    assert near["review_queue_item_id"] is None
    assert near["notification_event"] is None
    assert await product_counts(client) == before

    status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert status["current_activity_session_id"] == near["activity_session_id"]
    assert status["activity_review_state"] == "tentative_burst"
    assert status["activity_detection_count"] == 0
    assert status["activity_near_miss_count"] == 1
    assert status["auto_review_created_count"] == 0

    review_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["status"] == "unavailable"
    assert review["review_activity_created"] is False
    assert review["media_asset_id"] is None
    assert await product_counts(client) == before

    captured_at = datetime.fromisoformat(near["activity_last_seen_at"])
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_2,
        captured_at=captured_at + timedelta(seconds=1),
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_3,
        captured_at=captured_at + timedelta(seconds=2),
    )
    confirmed_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )
    assert confirmed_response.status_code == 200
    confirmed = confirmed_response.json()
    assert confirmed["activity_detected"] is True
    assert confirmed["activity_session_id"] == near["activity_session_id"]
    assert confirmed["activity_detection_count"] == 1
    assert confirmed["activity_near_miss_count"] == 1
    assert confirmed["activity_candidate_frame_count"] == 2
    assert confirmed["activity_saved_candidate_count"] == 0
    assert confirmed["notification_event"] == "activity_started"
    assert confirmed["best_media_asset_id"] is None
    assert await product_counts(client) == before


async def test_live_activity_burst_candidate_frames_are_bounded_and_notifications_do_not_spam(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    initial_0 = b"\xff\xd8bounded-burst-initial-0\xff\xd9"
    initial_1 = b"\xff\xd8bounded-burst-initial-1\xff\xd9"
    fake_process = FakeFfmpegProcess([initial_0, initial_1])
    frames_by_bytes = {
        initial_0: blank_frame(width=100, height=100),
        initial_1: frame_with(
            [(30, 40), (30, 41), (31, 40), (31, 41)],
            width=100,
            height=100,
        ),
    }

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )

    for index in range(35):
        blank = f"\xff\xd8bounded-burst-blank-{index}\xff\xd9".encode()
        motion = f"\xff\xd8bounded-burst-motion-{index}\xff\xd9".encode()
        frames_by_bytes[blank] = blank_frame(width=100, height=100)
        frames_by_bytes[motion] = frame_with(
            [
                (30, 40),
                (30, 41),
                (31, 40),
                (31, 41),
                (32, 40),
                (32, 41),
            ],
            width=100,
            height=100,
        )
    patch_live_motion_decoder(monkeypatch, frames_by_bytes)
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)
    before = await product_counts(client)

    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )
    assert first_response.status_code == 200
    first = first_response.json()
    assert first["notification_event"] == "activity_started"

    captured_at = datetime.fromisoformat(first["best_frame_captured_at"])
    last_result = first
    for index in range(35):
        blank = f"\xff\xd8bounded-burst-blank-{index}\xff\xd9".encode()
        motion = f"\xff\xd8bounded-burst-motion-{index}\xff\xd9".encode()
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            blank,
            captured_at=captured_at + timedelta(seconds=index * 0.1),
        )
        live_frame_cache.store_latest_frame(
            STREAM_ID,
            motion,
            captured_at=captured_at + timedelta(seconds=index * 0.1 + 0.05),
        )
        response = await client.post(
            f"/api/streams/{STREAM_ID}/live-motion/evaluate",
            json={
                "save_best_frame": True,
                "create_review_activity": False,
                "min_changed_ratio": 0.003,
                "pixel_delta_threshold": 10,
                "min_triggered_frames": 1,
            },
        )
        assert response.status_code == 200
        last_result = response.json()
        assert last_result["notification_event"] is None

    assert last_result["activity_session_id"] == first["activity_session_id"]
    assert 1 <= last_result["activity_detection_count"] <= 36
    assert 1 <= last_result["activity_candidate_frame_count"] <= 30
    assert last_result["activity_frames_evaluated_count"] > last_result[
        "activity_candidate_frame_count"
    ]
    assert last_result["activity_saved_candidate_count"] == 0
    assert last_result["best_media_asset_id"] is None
    assert await product_counts(client) == before


async def test_live_activity_session_groups_hits_and_promotes_one_best_frame(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-grouping-0\xff\xd9"
    frame_1 = b"\xff\xd8session-grouping-1\xff\xd9"
    frame_2 = b"\xff\xd8session-grouping-2\xff\xd9"
    frame_3 = b"\xff\xd8session-grouping-3\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
            frame_2: blank_frame(width=100, height=100),
            frame_3: frame_with(
                [
                    (30, 40),
                    (30, 41),
                    (30, 42),
                    (31, 40),
                    (31, 41),
                    (31, 42),
                    (32, 40),
                    (32, 41),
                    (32, 42),
                ],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    before = await product_counts(client)
    first_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert first_response.status_code == 200
    first = first_response.json()
    assert first["activity_detected"] is True
    assert first["activity_session_id"].startswith("live-activity-")
    assert first["activity_detection_count"] == 1
    assert first["activity_best_frame_sequence"] == 2
    assert first["best_media_asset_id"] is None
    assert await product_counts(client) == before

    captured_at = datetime.now(UTC)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_2,
        captured_at=captured_at + timedelta(seconds=1),
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_3,
        captured_at=captured_at + timedelta(seconds=2),
    )
    second_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
        },
    )

    assert second_response.status_code == 200
    second = second_response.json()
    assert second["activity_session_id"] == first["activity_session_id"]
    assert second["activity_detection_count"] == 2
    assert second["activity_best_frame_sequence"] == 4
    assert second["activity_best_score"] > first["activity_best_score"]
    assert second["best_media_asset_id"] is None
    assert await product_counts(client) == before

    status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert status["current_activity_session_id"] == first["activity_session_id"]
    assert status["activity_detection_count"] == 2
    assert status["activity_best_frame_sequence"] == 4
    assert status["activity_review_activity_created"] is False
    assert status["monitor_running"] is True

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["status"] == "created"
    assert created["activity_session_id"] == first["activity_session_id"]
    assert created["activity_detection_count"] == 2
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["creates_truth"] is False

    after_create = await product_counts(client)
    assert after_create["media_assets"] == before["media_assets"] + 2
    assert after_create["motion_evidence"] == before["motion_evidence"] + 1
    assert after_create["events"] == before["events"] + 1
    assert after_create["visits"] == before["visits"] + 1
    assert after_create["review_labels"] == before["review_labels"]
    assert after_create["dataset_exports"] == before["dataset_exports"]
    labels_after_create = (await client.get("/api/review-labels")).json()
    assert [
        label
        for label in labels_after_create
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ] == []

    queue = (await client.get("/api/review-queue")).json()
    assert queue[0]["id"] == created["review_queue_item_id"]
    queue_item = next(item for item in queue if item["id"] == created["review_queue_item_id"])
    assert_live_review_queue_item_quality(
        queue_item,
        created=created,
        activity_session_id=first["activity_session_id"],
        detection_count=2,
        best_frame_sequence=4,
        expected_focus_crop_normalized={
            "x": 0.34,
            "y": 0.24,
            "width": 0.15,
            "height": 0.15,
        },
        expected_focus_crop_pixels={"x": 34, "y": 24, "width": 15, "height": 15},
    )
    assert queue_item["suggested_label"] == "unknown_bird"
    assert queue_item["fine_motion_applied"] is True
    assert queue_item["threshold_source"] == "bird_feeder_high_fine"
    evidence_frames = queue_item["evidence_frames"]
    assert 1 < len(evidence_frames) <= 4
    assert [frame["captured_at"] for frame in evidence_frames] == sorted(
        frame["captured_at"] for frame in evidence_frames
    )
    assert [frame["media_asset_id"] for frame in evidence_frames] == list(
        dict.fromkeys(frame["media_asset_id"] for frame in evidence_frames)
    )
    assert sum(frame["is_primary"] for frame in evidence_frames) == 1
    assert next(frame for frame in evidence_frames if frame["is_primary"])[
        "media_asset_id"
    ] == created["media_asset_id"]
    assert all("local_path" not in frame for frame in evidence_frames)
    assert all(frame["preview_url"].startswith("/api/media/") for frame in evidence_frames)

    visit_detail = (await client.get(f"/api/visits/{created['visit_id']}/detail")).json()
    assert [frame["media_asset_id"] for frame in visit_detail["evidence_frames"]] == [
        frame["media_asset_id"] for frame in evidence_frames
    ]

    duplicate_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )
    assert duplicate_response.status_code == 200
    duplicate = duplicate_response.json()
    assert duplicate["status"] == "already_exists"
    assert duplicate["already_exists"] is True
    assert duplicate["activity_session_id"] == first["activity_session_id"]
    assert duplicate["motion_evidence_id"] == created["motion_evidence_id"]
    assert duplicate["review_queue_item_id"] == created["review_queue_item_id"]
    assert await product_counts(client) == after_create

    false_positive_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": created["visit_id"],
            "label": "false_positive",
            "notes": "Grouped live activity was not a bird visit.",
        },
    )

    assert false_positive_response.status_code == 201
    false_positive = false_positive_response.json()
    assert false_positive["review_label"]["label"] == "false_positive"
    assert false_positive["review_label"]["target_id"] == created["visit_id"]
    assert false_positive["visit"]["review_status"] == "reviewed"
    corrected_queue = (await client.get("/api/review-queue")).json()
    assert all(item["id"] != created["review_queue_item_id"] for item in corrected_queue)
    labels_after_false_positive = (await client.get("/api/review-labels")).json()
    assert [
        label["label"]
        for label in labels_after_false_positive
        if label["target_type"] == "visit" and label["target_id"] == created["visit_id"]
    ] == ["false_positive"]
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_create["review_labels"] + 1
    assert corrected_counts["dataset_exports"] == after_create["dataset_exports"]
    false_positive_analytics = (await client.get("/api/analytics/summary")).json()
    assert false_positive_analytics["species_counts"]["false_positive"] >= 1
    assert false_positive_analytics["label_categories"]["false_positive"] == "false_positive"
    assert "false_positive" not in false_positive_analytics["species_label_ids"]
    false_positive_export = await client.post(
        "/api/dataset-exports",
        json={"name": "Reviewed grouped activity outcomes", "reviewed_only": True},
    )
    assert false_positive_export.status_code == 201
    false_positive_record = next(
        record
        for record in false_positive_export.json()["manifest"]["records"]
        if record["visit_id"] == created["visit_id"]
    )
    assert false_positive_record["label"] == "false_positive"
    assert false_positive_record["is_species"] is False


async def test_small_feeder_activity_capture_and_review_handoff_keep_monitor_running(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8session-small-feeder-0\xff\xd9"
    frame_1 = b"\xff\xd8session-small-feeder-1\xff\xd9"
    fake_process = FakeFfmpegProcess([frame_0, frame_1])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)
    before_labels = (await client.get("/api/review-labels")).json()

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": True,
            "create_review_activity": False,
            "min_changed_ratio": 0.003,
            "pixel_delta_threshold": 10,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )

    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["activity_detected"] is True
    assert monitor["strongest_zone_name"] == "Feeder"
    assert monitor["fine_motion_applied"] is True
    assert monitor["threshold_source"] == "bird_feeder_high_fine"
    assert monitor["best_media_asset_id"] is None
    assert monitor["activity_session_id"].startswith("live-activity-")
    assert monitor["activity_detection_count"] == 1
    status_after_motion = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_motion["status"] == "running"
    assert status_after_motion["monitor_running"] is True
    assert status_after_motion["current_activity_session_id"] == monitor["activity_session_id"]
    assert status_after_motion["last_activity"]["best_media_asset_id"] is None

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture after small feeder activity must reuse session frames")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    capture_response = await client.post(
        f"/api/streams/{STREAM_ID}/local-camera/capture-frame"
    )

    assert capture_response.status_code == 200
    capture = capture_response.json()
    assert capture["status"] == "saved"
    assert capture["capture_source"] == "live_camera_session"
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["current_activity_session_id"] == monitor[
        "activity_session_id"
    ]
    assert status_after_capture["last_activity"]["best_media_asset_id"] is None

    create_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/review-activity"
    )

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["review_activity_created"] is True
    assert created["activity_session_id"] == monitor["activity_session_id"]
    assert created["media_asset_id"].startswith("media-asset-")
    assert created["motion_evidence_id"].startswith("motion-evidence-")
    assert created["event_id"].startswith("event-motion-")
    assert created["visit_id"].startswith("visit-motion-")
    assert created["review_queue_item_id"] == f"review-queue-{created['visit_id']}"
    assert created["creates_truth"] is False
    status_after_handoff = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_handoff["status"] == "running"
    assert status_after_handoff["monitor_running"] is True
    assert status_after_handoff["last_motion_result"]["review_activity_created"] is True

    labels_after_handoff = (await client.get("/api/review-labels")).json()
    assert labels_after_handoff == before_labels
    after_handoff = await product_counts(client)
    assert after_handoff["media_assets"] == before["media_assets"] + 2
    assert after_handoff["motion_evidence"] == before["motion_evidence"] + 1
    assert after_handoff["events"] == before["events"] + 1
    assert after_handoff["visits"] == before["visits"] + 1
    assert after_handoff["review_labels"] == before["review_labels"]
    assert after_handoff["dataset_exports"] == before["dataset_exports"]

    correction_response = await client.post(
        "/api/review-labels",
        json={
            "target_type": "visit",
            "target_id": created["visit_id"],
            "label": "northern_cardinal",
            "notes": "Confirmed small feeder activity.",
        },
    )
    assert correction_response.status_code == 201
    corrected_counts = await product_counts(client)
    assert corrected_counts["review_labels"] == after_handoff["review_labels"] + 1


async def test_playback_status_does_not_start_local_camera_bridge_process(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )

    def fail_if_started(device: str, **kwargs: object):  # noqa: ANN202
        raise AssertionError("Playback status must not start local camera ffmpeg")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        fail_if_started,
    )
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


def test_local_camera_command_uses_list_args_and_safe_device_validation() -> None:
    command = local_camera_bridge.build_local_camera_mjpeg_command("/dev/video0")

    assert command[:6] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
    ]
    assert "-i" in command
    assert "/dev/video0" in command
    assert "-input_format" not in command
    assert "-video_size" not in command
    assert "-framerate" not in command
    assert "shell=True" not in command
    assert local_camera_bridge.validate_local_camera_device("/dev/video0") is True
    assert local_camera_bridge.validate_local_camera_device("/dev/video12") is True
    assert local_camera_bridge.validate_local_camera_device("/tmp/video0") is False
    assert (
        local_camera_bridge.local_camera_status(
            device="/dev/video0",
            platform_name="darwin",
            ffmpeg_available=True,
        )
        == "unsupported_platform"
    )


def test_local_camera_command_allows_explicit_input_options() -> None:
    command = local_camera_bridge.build_local_camera_mjpeg_command(
        "/dev/video1",
        input_format="mjpeg",
        video_size="640x480",
        input_frame_rate=10,
    )

    assert command[command.index("-input_format") + 1] == "mjpeg"
    assert command[command.index("-video_size") + 1] == "640x480"
    assert command[command.index("-framerate") + 1] == "10"
    assert "/dev/video1" in command


async def test_windows_dshow_configuration_requires_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)

    response = await client.get(f"/api/sources/{SOURCE_ID}/provider-configuration")

    assert response.status_code == 200
    configuration = response.json()
    assert configuration["provider_key"] == "local_usb"
    assert configuration["missing_fields"] == ["windows_camera_name"]
    assert "Windows DirectShow camera name is required" in configuration["message"]
    assert "Use Detect cameras" in configuration["setup_hint"]


async def test_windows_dshow_playback_reports_missing_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "camera_name_missing"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["bridged_mjpeg_url"] is None
    assert "Use Detect cameras" in playback["setup_hint"]


async def test_windows_dshow_playback_reports_unsupported_host_without_windows_ffmpeg(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "unsupported_host",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_stream_type"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "unsupported_host"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["message"] == (
        "Windows DirectShow requires Windows ffmpeg.exe or running the API on Windows."
    )
    assert "/mnt/c/ffmpeg/bin/ffmpeg.exe" in playback["setup_hint"]


async def test_windows_dshow_playback_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "ffmpeg_missing",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unavailable"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is False
    assert playback["windows_camera_status"] == "ffmpeg_missing"
    assert playback["windows_camera_bridge_available"] is False
    assert playback["message"] == "Windows DirectShow bridge unavailable - ffmpeg not found."


async def test_windows_dshow_playback_reports_bridge_available_with_windows_ffmpeg_path(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "live_ready"
    assert playback["playback_kind"] == "windows_dshow"
    assert playback["supports_live_playback"] is True
    assert playback["windows_camera_status"] == "available"
    assert playback["windows_camera_bridge_available"] is True
    assert playback["windows_camera_name_display"] == "EMEET SmartCam S600"
    assert playback["windows_ffmpeg_binary_display"] == "/mnt/c/ffmpeg/bin/ffmpeg.exe"
    assert playback["bridged_mjpeg_url"] == (
        f"/api/streams/{STREAM_ID}/live/windows-dshow-mjpeg"
    )


async def test_windows_dshow_bridge_endpoint_rejects_non_windows_dshow_stream(
    client: httpx.AsyncClient,
) -> None:
    await configure_local_usb_camera(client, device="/dev/video0")

    response = await client.get(f"/api/streams/{STREAM_ID}/live/windows-dshow-mjpeg")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Windows DirectShow bridge requires windows_dshow playback type."
    )


async def test_windows_dshow_bridge_endpoint_streams_mocked_mjpeg_without_creating_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame_one = b"\xff\xd8windows-frame-one\xff\xd9"
    jpeg_frame_two = b"\xff\xd8windows-frame-two\xff\xd9"
    fake_process = object()
    started: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    def fake_start(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> object:
        started.append((camera_name, ffmpeg_binary_path, input_format, video_size, framerate))
        return fake_process

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.start_windows_dshow_mjpeg_process",
        fake_start,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.iter_multipart_mjpeg",
        lambda process, **kwargs: iter(
            [
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame_one,
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_frame_two,
            ]
        ),
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        video_size="640x480",
        preview_video_size="1280x720",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await get_stream_windows_dshow_mjpeg_bridge(STREAM_ID)

    assert response.status_code == 200
    assert response.media_type == (
        f"multipart/x-mixed-replace; boundary={windows_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert response.headers["content-type"] == (
        f"multipart/x-mixed-replace; boundary={windows_camera_bridge.MJPEG_BOUNDARY}"
    )
    assert started == [
        (
            "EMEET SmartCam S600",
            "/mnt/c/ffmpeg/bin/ffmpeg.exe",
            "mjpeg",
            "1280x720",
            "15",
        )
    ]
    assert await product_counts(client) == before


async def test_windows_dshow_capture_without_session_ignores_fresh_cache_and_uses_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-windows-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-windows-live-frame\xff\xd9"
    captured_args: list[str] = []

    def fake_capture(camera_name: str, **kwargs: object) -> bytes:
        captured_args.append(camera_name)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    live_frame_cache.store_latest_frame(STREAM_ID, live_frame)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(fallback_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == ["EMEET SmartCam S600"]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=windows_dshow" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_windows_dshow_capture_frame_ignores_stale_live_cache_and_falls_back(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_frame = b"\xff\xd8stale-windows-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-windows-frame\xff\xd9"
    captured_args: list[str] = []

    def fake_capture(camera_name: str, **kwargs: object) -> bytes:
        captured_args.append(camera_name)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        stale_frame,
        captured_at=datetime.now(UTC) - timedelta(seconds=30),
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert captured_args == ["EMEET SmartCam S600"]
    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    saved_path = Path(media_response.json()["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame


async def test_windows_dshow_capture_frame_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8captured-windows-frame\xff\xd9"
    captured_args: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    def fake_capture(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        framerate: str | None = None,
    ) -> bytes:
        captured_args.append((camera_name, ffmpeg_binary_path, input_format, video_size, framerate))
        return jpeg_frame

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        fake_capture,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        video_size="1280x720",
        capture_video_size="1920x1080",
        framerate="10",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["stream_id"] == STREAM_ID
    assert body["source_id"] == SOURCE_ID
    assert body["media_asset_id"].startswith("media-asset-")
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(jpeg_frame)
    assert body["file_name"].endswith(".jpg")
    assert body["relative_path"] == body["file_name"]
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == [
        (
            "EMEET SmartCam S600",
            "/mnt/c/ffmpeg/bin/ffmpeg.exe",
            "mjpeg",
            "1920x1080",
            "10",
        )
    ]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert media_asset["source_id"] == SOURCE_ID
    assert media_asset["stream_id"] == STREAM_ID
    assert media_asset["content_type"] == "image/jpeg"
    assert media_asset["media_type"] == "image"
    assert "Saved explicit local camera frame capture." in media_asset["notes"]
    assert "playback_type=windows_dshow" in media_asset["notes"]
    assert "Creates no Events, Visits, ReviewLabels, exports, or truth." in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == jpeg_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in (
        "events",
        "visits",
        "review_labels",
        "motion_evidence",
        "species_suggestions",
        "detection_proposals",
        "dataset_exports",
    ):
        assert after[key] == before[key]


async def test_local_usb_capture_without_session_ignores_fresh_cache_and_uses_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_frame = b"\xff\xd8cached-local-live-frame\xff\xd9"
    fallback_frame = b"\xff\xd8fallback-local-live-frame\xff\xd9"
    captured_args: list[str] = []

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.local_camera_status",
        lambda **kwargs: "available",
    )

    def fake_capture(device: str, **kwargs: object) -> bytes:
        captured_args.append(device)
        return fallback_frame

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fake_capture,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    live_frame_cache.store_latest_frame(STREAM_ID, live_frame)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(fallback_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == ["/dev/video0"]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=local_usb" in media_asset["notes"]
    saved_path = Path(media_asset["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == fallback_frame

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_local_usb_capture_frame_uses_running_session_frame_without_one_shot(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_session_frame = b"\xff\xd8session-capture-frame-0\xff\xd9"
    session_frame = b"\xff\xd8session-capture-frame-1\xff\xd9"
    fake_process = FakeFfmpegProcess([first_session_frame, session_frame])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    patch_live_motion_decoder(
        monkeypatch,
        {
            first_session_frame: blank_frame(),
            session_frame: blank_frame(),
        },
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    await wait_for_live_session_frame_count(client, STREAM_ID, minimum=2)

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    status_before_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_before_capture["status"] == "running"
    assert status_before_capture["monitor_running"] is True
    last_activity = {"best_media_asset_id": "media-asset-existing-activity"}
    get_live_camera_session_manager().update_last_activity(STREAM_ID, last_activity)

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture must use the running camera session frame")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == "Captured current frame; camera and monitoring are still running."
    assert body["capture_source"] == "live_camera_session"
    assert body["live_frame_age_ms"] >= 0
    assert body["bytes_written"] == len(session_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    saved_path = Path(media_response.json()["local_path"]).resolve()
    assert saved_path.is_relative_to(isolated_repository.media_root.resolve())
    assert saved_path.read_bytes() == session_frame

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert cached is not None
    assert cached.frame_bytes == session_frame
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["frame_count"] >= 2
    assert status_after_capture["last_activity"] == last_activity

    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False


async def test_local_usb_capture_with_running_session_without_fresh_frame_skips_one_shot(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = FakeFfmpegProcess([])

    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200

    monitor_response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/start",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
            "interval_seconds": 10,
        },
    )
    assert monitor_response.status_code == 200
    last_activity = {"best_media_asset_id": "media-asset-existing-stale-activity"}
    get_live_camera_session_manager().update_last_activity(STREAM_ID, last_activity)

    def fail_if_one_shot_capture_runs(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("Capture must not start one-shot ffmpeg during a running session")

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fail_if_one_shot_capture_runs,
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unavailable"
    assert body["message"] == "No fresh session frame available; camera session is still running."
    assert body["capture_source"] == "unavailable"
    assert body["media_asset_id"] is None
    assert body["bytes_written"] == 0
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert await product_counts(client) == before

    assert live_frame_cache.get_latest_frame(STREAM_ID) is None
    status_after_capture = (
        await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    ).json()
    assert status_after_capture["status"] == "running"
    assert status_after_capture["monitor_running"] is True
    assert status_after_capture["frame_count"] == 0
    assert status_after_capture["last_activity"] == last_activity

    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")
    assert stop_response.status_code == 200
    stopped = stop_response.json()
    assert stopped["status"] == "stopped"
    assert stopped["monitor_running"] is False


async def test_local_usb_capture_frame_creates_one_media_asset_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jpeg_frame = b"\xff\xd8captured-local-frame\xff\xd9"
    captured_args: list[tuple[str, str | None, str | None, str | None, str | None]] = []

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.local_camera_status",
        lambda **kwargs: "available",
    )

    def fake_capture(
        device: str,
        *,
        camera_format: str | None = None,
        input_format: str | None = None,
        video_size: str | None = None,
        input_frame_rate: str | None = None,
    ) -> bytes:
        captured_args.append((device, camera_format, input_format, video_size, input_frame_rate))
        return jpeg_frame

    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.capture_local_camera_frame",
        fake_capture,
    )
    await configure_local_usb_camera(
        client,
        device="/dev/video0",
        capture_video_size="1920x1080",
        framerate="15",
        input_format="mjpeg",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "saved"
    assert body["message"] == (
        "Saved one local camera frame directly because Live view was not streaming. "
        "It will not appear in Bird Log until you create/review activity."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["content_type"] == "image/jpeg"
    assert body["bytes_written"] == len(jpeg_frame)
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert body["creates_export"] is False
    assert captured_args == [("/dev/video0", "v4l2", "mjpeg", "1920x1080", "15")]

    media_response = await client.get(f"/api/media/{body['media_asset_id']}")
    assert media_response.status_code == 200
    media_asset = media_response.json()
    assert "playback_type=local_usb" in media_asset["notes"]
    after = await product_counts(client)
    assert after["media_assets"] == before["media_assets"] + 1
    for key in before:
        if key != "media_assets":
            assert after[key] == before[key]


async def test_local_camera_capture_reports_missing_windows_camera_name(
    client: httpx.AsyncClient,
) -> None:
    await configure_windows_dshow_camera(client, camera_name=None)
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "camera_not_configured"
    assert body["media_asset_id"] is None
    assert "Windows DirectShow camera name" in body["message"]
    assert await product_counts(client) == before


async def test_local_camera_capture_reports_ffmpeg_missing(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_status",
        lambda **kwargs: "ffmpeg_missing",
    )
    await configure_windows_dshow_camera(client, camera_name="EMEET SmartCam S600")
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ffmpeg_missing"
    assert body["bytes_written"] == 0
    assert await product_counts(client) == before


async def test_local_camera_capture_rejects_unsupported_stream_kind(
    client: httpx.AsyncClient,
) -> None:
    await configure_external_url_live_stream(
        client,
        live_stream_url="http://camera.local/live.mjpg",
        live_stream_type="mjpeg",
    )

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "unsupported"
    assert "local camera Source provider" in body["message"]


async def test_local_camera_capture_reports_no_frame_as_capture_failed(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.capture_windows_dshow_frame",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("no_frame_captured")),
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/local-camera/capture-frame")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "capture_failed"
    assert body["message"] == (
        "Camera is busy or did not return a frame. Close other camera apps, "
        "or open Live view until a frame appears and retry capture."
    )
    assert body["capture_source"] == "one_shot_ffmpeg"
    assert body["live_frame_age_ms"] is None
    assert body["bytes_written"] == 0
    assert await product_counts(client) == before


def test_windows_dshow_command_uses_list_args_and_safe_camera_name() -> None:
    command = windows_camera_bridge.build_windows_dshow_mjpeg_command(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        input_format="mjpeg",
        video_size="640x480",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
        "-input_format",
        "mjpeg",
        "-video_size",
        "640x480",
        "-framerate",
        "10",
        "-i",
        "video=EMEET SmartCam S600",
        "-an",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "-r",
        "5",
        "pipe:1",
    ]
    assert windows_camera_bridge.build_windows_dshow_list_devices_command() == [
        "ffmpeg",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    assert windows_camera_bridge.validate_windows_camera_name("EMEET SmartCam S600") is True
    assert windows_camera_bridge.validate_windows_camera_name("Camera\nName") is False
    assert windows_camera_bridge.validate_windows_camera_name("") is False


def _decode_camera_controls_launcher_script(command: list[str]) -> str:
    encoded_index = command.index("-EncodedCommand") + 1
    return base64.b64decode(command[encoded_index]).decode("utf-16-le")


def _camera_controls_launcher_payload(script: str) -> dict[str, str]:
    match = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", script)
    assert match is not None
    payload = json.loads(base64.b64decode(match.group(1)).decode("utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    assert all(isinstance(value, str) for value in payload.values())
    return payload


def test_windows_dshow_camera_controls_launch_interactively_without_waiting_for_dialog() -> None:
    camera_name = 'EMEET SmartCam S600 & Patio; $(calc.exe) "Bird"'
    ffmpeg_path = "C:\\Program Files & Tools\\FFmpeg\\bin\\ffmpeg.exe"
    powershell_path = (
        "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
    )
    existing_paths = {ffmpeg_path, powershell_path}
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = windows_camera_bridge.launch_windows_dshow_camera_controls(
        camera_name,
        ffmpeg_binary_path=ffmpeg_path,
        platform_name="win32",
        which=lambda name: powershell_path if name == "powershell.exe" else None,
        path_is_file=lambda path: str(path) in existing_paths,
        run_factory=fake_run,
    )

    assert result.returncode == 0
    assert len(calls) == 1
    launcher_command, launcher_options = calls[0]
    assert launcher_command == windows_camera_bridge.build_windows_dshow_camera_controls_launcher_command(
        camera_name,
        ffmpeg_binary_path=ffmpeg_path,
        platform_name="win32",
        which=lambda name: powershell_path if name == "powershell.exe" else None,
        path_is_file=lambda path: str(path) in existing_paths,
    )
    assert launcher_command[0] == powershell_path
    script = _decode_camera_controls_launcher_script(launcher_command)
    assert "Start-Process" in script
    assert "-WindowStyle Normal" in script
    assert "-PassThru" in script
    assert "-Wait" not in script
    assert "WaitForExit" not in script
    assert "-NoNewWindow" not in script
    assert "Hidden" not in script
    assert camera_name not in script
    assert ffmpeg_path not in script
    assert camera_name not in launcher_command
    assert ffmpeg_path not in launcher_command
    payload = _camera_controls_launcher_payload(script)
    expected_ffmpeg_command = windows_camera_bridge.build_windows_dshow_camera_controls_command(
        camera_name,
        ffmpeg_binary_path=ffmpeg_path,
    )
    assert ffmpeg_path in payload.values()
    assert subprocess.list2cmdline(expected_ffmpeg_command[1:]) in payload.values()
    assert launcher_options.get("shell") is not True
    assert launcher_options["timeout"] == 10.0
    assert "env" not in launcher_options
    assert launcher_options.get("creationflags", 0) != getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        -1,
    )


def test_windows_dshow_camera_controls_wsl_uses_windows_launcher_and_converts_path() -> None:
    camera_name = "Backyard Camera & Birdbath"
    wsl_ffmpeg_path = "/mnt/c/Program Files/FFmpeg/bin/ffmpeg.exe"
    windows_ffmpeg_path = "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe"
    powershell_path = (
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    existing_paths = {wsl_ffmpeg_path, powershell_path}
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    result = windows_camera_bridge.launch_windows_dshow_camera_controls(
        camera_name,
        ffmpeg_binary_path=wsl_ffmpeg_path,
        platform_name="linux",
        environment={"WSL_INTEROP": "/run/WSL/1_interop"},
        which=lambda name: powershell_path if name == "powershell.exe" else None,
        path_is_file=lambda path: str(path) in existing_paths,
        run_factory=fake_run,
    )

    assert result.returncode == 0
    launcher_command, launcher_options = calls[0]
    assert launcher_command[0] == powershell_path
    script = _decode_camera_controls_launcher_script(launcher_command)
    assert "Start-Process" in script
    assert "-WindowStyle Normal" in script
    assert "-Wait" not in script
    assert camera_name not in script
    assert wsl_ffmpeg_path not in script
    payload = _camera_controls_launcher_payload(script)
    expected_ffmpeg_command = windows_camera_bridge.build_windows_dshow_camera_controls_command(
        camera_name,
        ffmpeg_binary_path=windows_ffmpeg_path,
    )
    assert subprocess.list2cmdline(expected_ffmpeg_command[1:]) in payload.values()
    assert "env" not in launcher_options


@pytest.mark.parametrize(
    ("platform_name", "camera_name", "ffmpeg_path", "existing_paths", "powershell", "expected"),
    [
        (
            "win32",
            None,
            "C:\\ffmpeg\\bin\\ffmpeg.exe",
            {"C:\\ffmpeg\\bin\\ffmpeg.exe"},
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "camera_name_missing",
        ),
        (
            "win32",
            "EMEET SmartCam S600",
            "C:\\missing\\ffmpeg.exe",
            set(),
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "ffmpeg_missing",
        ),
        (
            "win32",
            "EMEET SmartCam S600",
            "relative\\ffmpeg.exe",
            {"relative\\ffmpeg.exe"},
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "controls_unavailable",
        ),
        (
            "win32",
            "EMEET SmartCam S600",
            "C:\\tools\\not-ffmpeg.exe",
            {"C:\\tools\\not-ffmpeg.exe"},
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "controls_unavailable",
        ),
        (
            "linux",
            "EMEET SmartCam S600",
            "/mnt/c/ffmpeg/bin/ffmpeg.exe",
            {"/mnt/c/ffmpeg/bin/ffmpeg.exe"},
            None,
            "controls_unavailable",
        ),
        (
            "darwin",
            "EMEET SmartCam S600",
            "/Applications/ffmpeg.exe",
            {"/Applications/ffmpeg.exe"},
            None,
            "unsupported_platform",
        ),
    ],
)
def test_windows_dshow_camera_controls_status_reports_setup_and_platform_failures(
    platform_name: str,
    camera_name: str | None,
    ffmpeg_path: str,
    existing_paths: set[str],
    powershell: str | None,
    expected: str,
) -> None:
    if powershell is not None:
        existing_paths.add(powershell)

    assert (
        windows_camera_bridge.windows_camera_controls_status(
            camera_name=camera_name,
            ffmpeg_binary_path=ffmpeg_path,
            platform_name=platform_name,
            environment=(
                {"WSL_INTEROP": "/run/WSL/1_interop"}
                if platform_name == "linux"
                else None
            ),
            which=lambda name: powershell if name == "powershell.exe" else None,
            path_is_file=lambda path: str(path) in existing_paths,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("platform_name", "ffmpeg_path", "resolved_ffmpeg", "powershell"),
    [
        (
            "win32",
            None,
            "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",
            "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
        ),
        (
            "linux",
            "/mnt/c/Program Files/FFmpeg/bin/ffmpeg.exe",
            "/mnt/c/Program Files/FFmpeg/bin/ffmpeg.exe",
            "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        ),
    ],
)
def test_windows_dshow_camera_controls_status_accepts_native_windows_and_wsl(
    platform_name: str,
    ffmpeg_path: str | None,
    resolved_ffmpeg: str,
    powershell: str,
) -> None:
    existing_paths = {resolved_ffmpeg, powershell}

    def resolve_binary(name: str) -> str | None:
        if name in {"ffmpeg", "ffmpeg.exe"}:
            return resolved_ffmpeg
        if name == "powershell.exe":
            return powershell
        return None

    assert (
        windows_camera_bridge.windows_camera_controls_status(
            camera_name="EMEET SmartCam S600",
            ffmpeg_binary_path=ffmpeg_path,
            platform_name=platform_name,
            environment=(
                {"WSL_INTEROP": "/run/WSL/1_interop"}
                if platform_name == "linux"
                else None
            ),
            which=resolve_binary,
            path_is_file=lambda path: str(path) in existing_paths,
        )
        == "available"
    )


def test_windows_dshow_camera_controls_reject_untrusted_host_executables() -> None:
    powershell_path = (
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    wsl_ffmpeg_path = "/mnt/c/ffmpeg/bin/ffmpeg.exe"
    lookalike_paths = {wsl_ffmpeg_path, powershell_path}

    assert (
        windows_camera_bridge.windows_camera_controls_status(
            camera_name="EMEET SmartCam S600",
            ffmpeg_binary_path=wsl_ffmpeg_path,
            platform_name="linux",
            environment={},
            which=lambda name: powershell_path if name == "powershell.exe" else None,
            path_is_file=lambda path: str(path) in lookalike_paths,
        )
        == "unsupported_platform"
    )

    for ffmpeg_path in (
        "\\\\server\\share\\ffmpeg.exe",
        "\\\\?\\C:\\tools\\ffmpeg.exe",
    ):
        assert (
            windows_camera_bridge.windows_camera_controls_status(
                camera_name="EMEET SmartCam S600",
                ffmpeg_binary_path=ffmpeg_path,
                platform_name="win32",
                environment={"SystemRoot": "C:\\Windows"},
                which=lambda name: (
                    "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"
                    if name == "powershell.exe"
                    else None
                ),
                path_is_file=lambda path: str(path) == ffmpeg_path,
            )
            == "controls_unavailable"
        )

    shadowed_powershell = "C:\\worktree\\powershell.exe"
    assert (
        windows_camera_bridge.windows_camera_controls_status(
            camera_name="EMEET SmartCam S600",
            ffmpeg_binary_path="C:\\tools\\ffmpeg.exe",
            platform_name="win32",
            environment={"SystemRoot": "C:\\Windows"},
            which=lambda name: shadowed_powershell if name == "powershell.exe" else None,
            path_is_file=lambda path: str(path)
            in {"C:\\tools\\ffmpeg.exe", shadowed_powershell},
        )
        == "controls_unavailable"
    )


def test_windows_camera_listing_parses_video_devices_without_shell() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr=(
                '[dshow @ 000001] "Backyard Camera" (video)\n'
                '[dshow @ 000001] "Microphone" (audio)\n'
                '[dshow @ 000001] "Backyard Camera" (video)'
            ),
        )

    devices = windows_camera_bridge.list_windows_dshow_video_devices(
        ffmpeg_binary_path="C:\\ffmpeg\\ffmpeg.exe",
        run_factory=fake_run,
    )

    assert devices == ["Backyard Camera"]
    assert calls[0][0] == [
        "C:\\ffmpeg\\ffmpeg.exe",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    assert calls[0][1].get("shell") is not True
    assert calls[0][1]["timeout"] == 10.0


async def test_windows_camera_discovery_returns_devices_without_creating_data(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mockingbird.api.main.sys.platform", "win32")
    monkeypatch.setattr(
        windows_camera_bridge,
        "is_windows_ffmpeg_available",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        windows_camera_bridge,
        "list_windows_dshow_video_devices",
        lambda *args, **kwargs: ["Backyard Camera", "Birdbath Camera"],
    )
    before = await product_counts(client)

    response = await client.get("/api/local-cameras/windows")

    assert response.status_code == 200
    assert response.json() == {
        "status": "available",
        "devices": ["Backyard Camera", "Birdbath Camera"],
        "message": "Found 2 cameras.",
        "creates_truth": False,
    }
    assert await product_counts(client) == before


async def test_live_motion_reports_clipped_highlights_despite_dark_scene_details(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame_0 = b"\xff\xd8live-clipped-0\xff\xd9"
    frame_1 = b"\xff\xd8live-clipped-1\xff\xd9"
    captured_at = datetime.now(UTC)
    # Mirrors a field frame where roughly half the image is clipped white while
    # usable-looking tree detail keeps the total contrast range high.
    clipped_frame = [[255 for _x in range(10)] for _y in range(4)] + [
        [180 for _x in range(10)] for _y in range(6)
    ]
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: clipped_frame,
            frame_1: clipped_frame,
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_changed_ratio": 0.1,
            "min_triggered_frames": 1,
        },
    )

    assert response.status_code == 200
    warnings = response.json()["image_quality_warnings"]
    assert any("overexposed with clipped highlights" in warning for warning in warnings)
    assert any("camera controls" in warning for warning in warnings)


async def test_windows_camera_discovery_explains_when_no_camera_is_connected(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("mockingbird.api.main.sys.platform", "win32")
    monkeypatch.setattr(
        windows_camera_bridge,
        "is_windows_ffmpeg_available",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        windows_camera_bridge,
        "list_windows_dshow_video_devices",
        lambda *args, **kwargs: [],
    )

    response = await client.get("/api/local-cameras/windows")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_devices"
    assert body["devices"] == []
    assert "Connect a camera" in body["message"]
    assert body["creates_truth"] is False


async def test_windows_camera_controls_launch_promptly_without_creating_or_registering_runtime(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launched: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_controls_status",
        lambda **kwargs: "available",
    )

    def fake_launch(
        camera_name: str,
        *,
        ffmpeg_binary_path: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        launched.append((camera_name, ffmpeg_binary_path))
        return subprocess.CompletedProcess(["powershell.exe"], 0, stdout="", stderr="")

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.launch_windows_dshow_camera_controls",
        fake_launch,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\ffmpeg\\bin\\ffmpeg.exe",
    )
    before = await product_counts(client)
    before_live = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    before_monitor = (await client.get(f"/api/streams/{STREAM_ID}/monitor/status")).json()
    before_policy = (await client.get(f"/api/streams/{STREAM_ID}/monitoring-policy")).json()
    before_runtime = (await client.get(f"/api/streams/{STREAM_ID}/runtime-status")).json()

    response = await client.post(f"/api/streams/{STREAM_ID}/camera-controls/open")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "launched"
    assert body["stream_id"] == STREAM_ID
    assert body["source_id"] == SOURCE_ID
    assert "launched" in body["message"].lower()
    assert "changed" not in body["message"].lower()
    assert "closed" not in body["message"].lower()
    assert body["creates_media"] is False
    assert body["creates_evidence"] is False
    assert body["creates_event"] is False
    assert body["creates_visit"] is False
    assert body["creates_truth"] is False
    assert launched == [("EMEET SmartCam S600", "C:\\ffmpeg\\bin\\ffmpeg.exe")]
    assert await product_counts(client) == before
    assert (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json() == before_live
    assert (await client.get(f"/api/streams/{STREAM_ID}/monitor/status")).json() == before_monitor
    assert (await client.get(f"/api/streams/{STREAM_ID}/monitoring-policy")).json() == before_policy
    assert (await client.get(f"/api/streams/{STREAM_ID}/runtime-status")).json() == before_runtime


async def test_windows_camera_controls_require_stopped_camera(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = FakeFfmpegProcess([])
    launch_calls = 0
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_controls_status",
        lambda **kwargs: "available",
    )

    def fail_if_launched(*args: object, **kwargs: object) -> object:
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("controls launcher must not run while the camera owns the device")

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.launch_windows_dshow_camera_controls",
        fail_if_launched,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.start_windows_dshow_mjpeg_process",
        lambda *args, **kwargs: fake_process,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\ffmpeg\\bin\\ffmpeg.exe",
    )
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/camera-controls/open")

    assert response.status_code == 200
    assert response.json()["status"] == "camera_running"
    assert "Stop the camera" in response.json()["message"]
    assert await product_counts(client) == before
    assert launch_calls == 0
    assert fake_process.terminated is False
    live_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert live_status["status"] in {"starting", "running"}
    stop_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/stop")
    assert stop_response.status_code == 200


async def test_windows_camera_controls_require_stopped_source_monitor_without_stopping_it(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch_calls = 0

    def fail_if_launched(*args: object, **kwargs: object) -> object:
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("controls launcher must not run while monitoring owns the source")

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.launch_windows_dshow_camera_controls",
        fail_if_launched,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\ffmpeg\\bin\\ffmpeg.exe",
    )
    monitor_manager = get_source_monitor_manager()
    started = await monitor_manager.start(
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        options=SourceMonitorOptions(),
        autostart=False,
    )
    assert started.status == "monitoring"
    before = await product_counts(client)
    before_policy = (await client.get(f"/api/streams/{STREAM_ID}/monitoring-policy")).json()

    response = await client.post(f"/api/streams/{STREAM_ID}/camera-controls/open")

    assert response.status_code == 200
    assert response.json()["status"] == "monitor_running"
    assert "Stop monitoring" in response.json()["message"]
    assert launch_calls == 0
    assert await product_counts(client) == before
    still_running = await monitor_manager.status(STREAM_ID)
    assert still_running is not None
    assert still_running.status == "monitoring"
    assert (await client.get(f"/api/streams/{STREAM_ID}/monitoring-policy")).json() == before_policy
    live_status = (await client.get(f"/api/streams/{STREAM_ID}/live-session/status")).json()
    assert live_status["status"] == "stopped"
    await monitor_manager.stop(STREAM_ID)


@pytest.mark.parametrize(
    ("bridge_status", "expected_status", "message_fragment"),
    [
        ("camera_name_missing", "camera_not_configured", "DirectShow camera name"),
        ("ffmpeg_missing", "ffmpeg_missing", "ffmpeg"),
        ("unsupported_platform", "unsupported_platform", "does not support"),
        ("controls_unavailable", "controls_unavailable", "this host"),
    ],
)
async def test_windows_camera_controls_report_honest_prelaunch_failures(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    bridge_status: str,
    expected_status: str,
    message_fragment: str,
) -> None:
    launch_calls = 0

    def fail_if_launched(*args: object, **kwargs: object) -> object:
        nonlocal launch_calls
        launch_calls += 1
        raise AssertionError("unavailable controls must not launch a process")

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_controls_status",
        lambda **kwargs: bridge_status,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.launch_windows_dshow_camera_controls",
        fail_if_launched,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name="EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\private camera tools\\ffmpeg.exe",
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/camera-controls/open")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected_status
    assert message_fragment.lower() in body["message"].lower()
    assert launch_calls == 0
    assert await product_counts(client) == before
    response_text = response.text.lower()
    assert "private camera tools" not in response_text
    assert "emeet smartcam" not in response_text
    assert "start-process" not in response_text


@pytest.mark.parametrize("failure_kind", ["nonzero", "os_error", "timeout"])
async def test_windows_camera_controls_sanitize_launcher_failure(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    failure_kind: str,
) -> None:
    private_path = "C:\\Users\\private-user\\Secret Camera Tools\\ffmpeg.exe"
    camera_name = "Private Patio Camera"
    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.windows_camera_controls_status",
        lambda **kwargs: "available",
    )

    def fail_launch(
        *_args: object,
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if failure_kind == "os_error":
            raise OSError(f"could not execute {private_path} for {camera_name}")
        if failure_kind == "timeout":
            raise subprocess.TimeoutExpired(
                ["powershell.exe", "-EncodedCommand", "private-command"],
                10,
            )
        return subprocess.CompletedProcess(
            ["powershell.exe", "-EncodedCommand", "private-command"],
            1,
            stdout="",
            stderr=f"failed {private_path} {camera_name}",
        )

    monkeypatch.setattr(
        "mockingbird.api.main.windows_camera_bridge.launch_windows_dshow_camera_controls",
        fail_launch,
    )
    await configure_windows_dshow_camera(
        client,
        camera_name=camera_name,
        ffmpeg_binary_path=private_path,
    )
    before = await product_counts(client)

    response = await client.post(f"/api/streams/{STREAM_ID}/camera-controls/open")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "launch_failed"
    assert "could not be launched" in body["message"].lower()
    assert await product_counts(client) == before
    response_text = response.text.lower()
    assert "private-user" not in response_text
    assert "secret camera tools" not in response_text
    assert camera_name.lower() not in response_text
    assert "private-command" not in response_text


def test_windows_dshow_frame_capture_command_uses_list_args() -> None:
    command = windows_camera_bridge.build_windows_dshow_frame_capture_command(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        input_format="mjpeg",
        video_size="1280x720",
        framerate="10",
    )

    assert command == [
        "/mnt/c/ffmpeg/bin/ffmpeg.exe",
        "-f",
        "dshow",
        "-input_format",
        "mjpeg",
        "-video_size",
        "1280x720",
        "-framerate",
        "10",
        "-i",
        "video=EMEET SmartCam S600",
        "-an",
        "-frames:v",
        "1",
        "-f",
        "image2pipe",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]


def test_windows_dshow_start_uses_popen_list_without_shell() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def fake_popen(command: list[str], **kwargs: object) -> FakeFfmpegProcess:
        calls.append((command, kwargs))
        return FakeFfmpegProcess([])

    process = windows_camera_bridge.start_windows_dshow_mjpeg_process(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="C:\\ffmpeg\\bin\\ffmpeg.exe",
        popen_factory=fake_popen,
    )

    assert isinstance(process, FakeFfmpegProcess)
    assert calls[0][0][0] == "C:\\ffmpeg\\bin\\ffmpeg.exe"
    assert calls[0][0][calls[0][0].index("-i") + 1] == "video=EMEET SmartCam S600"
    assert calls[0][1].get("shell") is not True


def test_local_camera_frame_capture_command_uses_list_args() -> None:
    command = local_camera_bridge.build_local_camera_frame_capture_command(
        "/dev/video0",
        video_size="640x480",
        input_frame_rate="10",
    )

    assert command[:6] == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
    ]
    assert command[command.index("-video_size") + 1] == "640x480"
    assert command[command.index("-framerate") + 1] == "10"
    assert command[command.index("-i") + 1] == "/dev/video0"
    assert command[command.index("-frames:v") + 1] == "1"
    assert "shell=True" not in command


def test_frame_capture_reader_returns_one_jpeg_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8captured-frame",
            b"\xff\xd9ignored\xff\xd8second-frame\xff\xd9",
        ]
    )

    frame = windows_camera_bridge.capture_windows_dshow_frame(
        "EMEET SmartCam S600",
        ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
        popen_factory=lambda *args, **kwargs: fake_process,
    )

    assert frame == b"\xff\xd8captured-frame\xff\xd9"
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_frame_capture_reader_reports_no_jpeg() -> None:
    fake_process = FakeFfmpegProcess([b"not-a-jpeg"])

    with pytest.raises(ValueError, match="no_frame_captured"):
        windows_camera_bridge.capture_windows_dshow_frame(
            "EMEET SmartCam S600",
            ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
            popen_factory=lambda *args, **kwargs: fake_process,
        )

    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_windows_dshow_status_is_wsl_aware() -> None:
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="linux",
            ffmpeg_binary_path=None,
            ffmpeg_available=True,
        )
        == "unsupported_host"
    )
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="win32",
            ffmpeg_binary_path="ffmpeg",
            ffmpeg_available=False,
        )
        == "ffmpeg_missing"
    )
    assert (
        windows_camera_bridge.windows_camera_status(
            camera_name="EMEET SmartCam S600",
            platform_name="linux",
            ffmpeg_binary_path="/mnt/c/ffmpeg/bin/ffmpeg.exe",
            ffmpeg_available=False,
        )
        == "available"
    )


def test_windows_dshow_multipart_generator_emits_two_frames_and_stops_process() -> None:
    fake_process = FakeFfmpegProcess(
        [
            b"noise\xff\xd8frame-one\xff\xd9middle\xff\xd8frame",
            b"-two\xff\xd9tail",
        ]
    )

    chunks = list(windows_camera_bridge.iter_multipart_mjpeg(fake_process))

    assert len(chunks) == 2
    assert chunks[0].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-one\xff\xd9" in chunks[0]
    assert chunks[1].startswith(b"--frame\r\nContent-Type: image/jpeg")
    assert b"\xff\xd8frame-two\xff\xd9" in chunks[1]
    assert fake_process.terminated is True
    assert fake_process.waited is True
    assert fake_process.killed is False


def test_windows_dshow_multipart_generator_updates_latest_frame_cache() -> None:
    fake_process = FakeFfmpegProcess([b"noise\xff\xd8windows-live-frame\xff\xd9"])

    chunks = list(
        windows_camera_bridge.iter_multipart_mjpeg(
            fake_process,
            on_frame=lambda frame: live_frame_cache.store_latest_frame(STREAM_ID, frame),
        )
    )

    cached = live_frame_cache.get_latest_frame(STREAM_ID)
    assert len(chunks) == 1
    assert cached is not None
    assert cached.frame_bytes == b"\xff\xd8windows-live-frame\xff\xd9"


async def test_live_camera_diagnostic_events_are_bounded_and_metadata_only(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = FakeFfmpegProcess([])
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)

    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200
    manager = get_live_camera_session_manager()
    for index in range(130):
        manager.record_motion_result(
            STREAM_ID,
            {
                "status": "activity_detected" if index % 2 else "no_activity",
                "session_status": "new_activity" if index % 2 else "no_activity",
                "camera_url": "rtsp://user:secret@example.invalid/live",
                "frame_bytes": b"private-frame",
                "model_output": {"raw": "private-output"},
            },
        )

    status_response = await client.get(f"/api/streams/{STREAM_ID}/live-session/status")
    assert status_response.status_code == 200
    assert "diagnostic_events" not in status_response.json()
    response = await client.get(f"/api/streams/{STREAM_ID}/live-session/diagnostics")
    assert response.status_code == 200
    body = response.json()
    events = body["diagnostic_events"]
    assert len(events) == 100
    assert body["diagnostic_events_truncated"] is True
    assert [event["sequence"] for event in events] == sorted(
        event["sequence"] for event in events
    )
    diagnostic_text = repr(events)
    assert "secret" not in diagnostic_text
    assert "private-frame" not in diagnostic_text
    assert "private-output" not in diagnostic_text
    assert all(event["creates_truth"] is False for event in events)
    assert await product_counts(client) == before


async def test_live_camera_diagnostics_record_product_transitions_without_truth(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_process = FakeFfmpegProcess([])
    monkeypatch.setattr(
        "mockingbird.playback.local_camera_bridge.is_ffmpeg_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "mockingbird.api.main.local_camera_bridge.start_local_camera_mjpeg_process",
        lambda device, **kwargs: fake_process,
    )
    await configure_local_usb_camera(client, device="/dev/video0")
    before = await product_counts(client)
    start_response = await client.post(f"/api/streams/{STREAM_ID}/live-session/start")
    assert start_response.status_code == 200

    manager = get_live_camera_session_manager()
    started_at = datetime.now(UTC)
    near_miss = manager.record_activity_detection(
        STREAM_ID,
        {
            "region_key": "zone:diagnostic-test",
            "region_kind": "zone",
            "region_id": "zone-diagnostic-test",
            "zone_id": "zone-diagnostic-test",
            "zone_type": "feeder",
            "last_seen_at": started_at,
            "activity_detected": False,
            "near_miss": True,
            "frames_evaluated_count": 2,
            "best_frame_sequence": 1,
            "best_frame_captured_at": started_at,
            "best_score": 0.01,
        },
        frame_bytes=b"\xff\xd8near-miss-frame\xff\xd9",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )
    assert near_miss is not None
    confirmed = manager.record_activity_detection(
        STREAM_ID,
        {
            "region_key": "zone:diagnostic-test",
            "region_kind": "zone",
            "region_id": "zone-diagnostic-test",
            "zone_id": "zone-diagnostic-test",
            "zone_type": "feeder",
            "last_seen_at": started_at + timedelta(seconds=1),
            "activity_detected": True,
            "near_miss": False,
            "frames_evaluated_count": 2,
            "best_frame_sequence": 2,
            "best_frame_captured_at": started_at + timedelta(seconds=1),
            "best_score": 0.02,
        },
        frame_bytes=b"\xff\xd8confirmed-frame\xff\xd9",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )
    assert confirmed is not None
    activity_session_id = confirmed.activity_session_id
    manager.mark_activity_ready_for_review(
        STREAM_ID,
        activity_session_id,
        quiet_seconds=1,
    )
    manager.mark_activity_media_asset(
        STREAM_ID,
        activity_session_id,
        "media-asset-diagnostic-test",
    )
    manager.mark_activity_review_created(
        STREAM_ID,
        activity_session_id,
        {
            "motion_evidence_id": "motion-evidence-diagnostic-test",
            "event_id": "event-diagnostic-test",
            "visit_id": "visit-diagnostic-test",
            "review_queue_item_id": "review-queue-diagnostic-test",
        },
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/live-session/diagnostics")
    assert response.status_code == 200
    events = response.json()["diagnostic_events"]
    event_types = [event["event_type"] for event in events]
    assert event_types == [
        "camera_started",
        "near_miss_started",
        "activity_confirmed",
        "activity_ready_for_review",
        "best_frame_saved",
        "review_candidate_created",
        "activity_retired",
    ]
    diagnostic_text = repr(events)
    assert "near-miss-frame" not in diagnostic_text
    assert "confirmed-frame" not in diagnostic_text
    assert "media-asset-diagnostic-test" not in diagnostic_text
    assert all(event["creates_truth"] is False for event in events)
    assert await product_counts(client) == before


async def test_external_url_unknown_live_stream_type_reports_unsupported(
    client: httpx.AsyncClient,
) -> None:
    update_response = await client.patch(
        f"/api/sources/{SOURCE_ID}/provider-configuration",
        json={
            "provider_key": "external_url",
            "config": {
                "url": "http://camera.local/still.jpg",
                "live_stream_url": "http://camera.local/custom-stream",
                "live_stream_type": "unknown",
            },
        },
    )
    assert update_response.status_code == 200

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "unsupported_stream_type"
    assert playback["playback_kind"] == "unknown"
    assert playback["supports_live_playback"] is False
    assert playback["preview_url"] is None
    assert playback["live_stream_type"] == "unknown"


async def test_not_configured_stream_returns_setup_hint(
    client: httpx.AsyncClient,
    isolated_repository: ProductRepository,
) -> None:
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-future-local",
                    name="Future local source",
                    kind=SourceKind.local_folder.value,
                    status=SourceStatus.needs_setup.value,
                    description="Product metadata for a future local source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-future-local",
                    source_id="source-future-local",
                    name="Future source stream",
                    description="Placeholder stream for future playback.",
                    is_live=False,
                )
            )

    response = await client.get("/api/streams/stream-future-local/playback")

    assert response.status_code == 200
    playback = response.json()
    assert playback["status"] == "not_configured"
    assert playback["playback_kind"] == "placeholder"
    assert playback["setup_hint"]
    assert playback["supports_zone_editing"] is True
    assert playback["supports_live_playback"] is False
    assert playback["adapter_key"] == "local_folder"


async def test_playback_route_does_not_require_adapter_runtime_status(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called():
        raise AssertionError("Playback status must not call detector adapter status")

    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_local_detector_status",
        fail_if_called,
    )
    monkeypatch.setattr(
        "mockingbird.repository.product_repository.get_megadetector_status",
        fail_if_called,
    )

    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200


async def test_playback_contract_creates_no_media_or_model_artifacts(
    client: httpx.AsyncClient,
    tmp_path: Path,
) -> None:
    response = await client.get(f"/api/streams/{STREAM_ID}/playback")

    assert response.status_code == 200
    artifact_extensions = {".onnx", ".pt", ".pth", ".weights", ".engine", ".ckpt"}
    assert [
        path
        for path in tmp_path.rglob("*")
        if path.is_file() and path.suffix.lower() in artifact_extensions
    ] == []


def test_windows_dshow_controls_wsl_accepts_native_windows_ffmpeg_path() -> None:
    windows_ffmpeg_path = "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe"
    wsl_ffmpeg_path = "/mnt/c/Program Files/FFmpeg/bin/ffmpeg.exe"
    powershell_path = (
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    existing_paths = {wsl_ffmpeg_path, powershell_path}

    command = windows_camera_bridge.build_windows_dshow_camera_controls_launcher_command(
        "EMEET SmartCam S600",
        ffmpeg_binary_path=windows_ffmpeg_path,
        platform_name="linux",
        environment={"WSL_INTEROP": "/run/WSL/1_interop"},
        which=lambda name: powershell_path if name == "powershell.exe" else None,
        path_is_file=lambda path: str(path) in existing_paths,
    )

    script = _decode_camera_controls_launcher_script(command)
    payload = _camera_controls_launcher_payload(script)
    assert windows_ffmpeg_path in payload.values()


def test_windows_dshow_invocation_maps_native_windows_path_inside_wsl() -> None:
    assert (
        windows_camera_bridge.windows_ffmpeg_invocation_binary(
            "C:\\Program Files\\FFmpeg\\bin\\ffmpeg.exe",
            platform_name="linux",
            environment={"WSL_DISTRO_NAME": "Ubuntu"},
        )
        == "/mnt/c/Program Files/FFmpeg/bin/ffmpeg.exe"
    )
def test_zone_monitoring_policy_defaults_persist_and_restore(
    isolated_repository: ProductRepository,
) -> None:
    feeder = isolated_repository.get_zone("zone-feeder")
    ground = isolated_repository.get_zone("zone-ground")
    ignored = isolated_repository.get_zone("zone-ignore-driveway-edge")

    assert feeder is not None and feeder.monitoring_policy is not None
    assert ground is not None and ground.monitoring_policy is not None
    assert ignored is not None and ignored.monitoring_policy is None
    assert feeder.monitoring_policy.activity_sensitivity == ZoneActivitySensitivity.high
    assert feeder.monitoring_policy.quiet_period_seconds == 20
    assert ground.monitoring_policy.quiet_period_seconds == 45
    assert feeder.monitoring_policy.uses_recommended_defaults is True

    updated = isolated_repository.update_zone_monitoring_policy(
        feeder.id,
        ZoneMonitoringPolicyUpdate(
            minimum_sustained_activity_seconds=7,
            maximum_evidence_frames=2,
        ),
    )
    assert updated is not None and updated.monitoring_policy is not None
    assert updated.monitoring_policy.minimum_sustained_activity_seconds == 7
    assert updated.monitoring_policy.maximum_evidence_frames == 2
    assert set(updated.monitoring_policy.customized_fields) == {
        "minimum_sustained_activity_seconds",
        "maximum_evidence_frames",
    }

    reloaded = ProductRepository(
        db_url=isolated_repository.db_url,
        media_root=isolated_repository.media_root,
    )
    try:
        persisted = reloaded.get_zone(feeder.id)
        assert persisted is not None and persisted.monitoring_policy is not None
        assert persisted.monitoring_policy.minimum_sustained_activity_seconds == 7
        assert persisted.monitoring_policy.maximum_evidence_frames == 2
    finally:
        reloaded.close()

    restored = isolated_repository.restore_zone_monitoring_policy_defaults(feeder.id)
    assert restored is not None and restored.monitoring_policy is not None
    assert restored.monitoring_policy.uses_recommended_defaults is True
    assert restored.monitoring_policy.minimum_sustained_activity_seconds == 2
    assert restored.monitoring_policy.maximum_evidence_frames == 4


async def test_zone_monitoring_policy_api_is_bounded_and_preserves_truth(
    client: httpx.AsyncClient,
) -> None:
    before = await product_counts(client)
    read_response = await client.get("/api/zones/zone-feeder/monitoring-policy")
    assert read_response.status_code == 200
    assert read_response.json()["uses_recommended_defaults"] is True

    unknown_setting = await client.put(
        "/api/zones/zone-feeder/monitoring-policy",
        json={"unexpected": True},
    )
    assert unknown_setting.status_code == 422
    out_of_range = await client.put(
        "/api/zones/zone-feeder/monitoring-policy",
        json={"maximum_evidence_frames": 5},
    )
    assert out_of_range.status_code == 422

    updated = await client.put(
        "/api/zones/zone-feeder/monitoring-policy",
        json={"monitoring_enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["monitoring_enabled"] is False
    assert updated.json()["uses_recommended_defaults"] is False

    restored = await client.post(
        "/api/zones/zone-feeder/monitoring-policy/restore-defaults"
    )
    assert restored.status_code == 200
    assert restored.json()["monitoring_enabled"] is True
    assert restored.json()["uses_recommended_defaults"] is True

    restricted = await client.put(
        "/api/zones/zone-ignore-driveway-edge/monitoring-policy",
        json={"monitoring_enabled": True},
    )
    assert restricted.status_code == 400
    assert "Privacy and Ignore" in restricted.json()["detail"]
    assert await product_counts(client) == before


def test_zone_policy_lifecycle_uses_per_zone_quiet_maximum_and_evidence_limits() -> None:
    started_at = datetime.now(UTC)

    def values(
        zone_id: str,
        seen_at: datetime,
        policy: dict[str, object],
    ) -> dict[str, object]:
        return {
            "region_key": f"zone:{zone_id}",
            "region_kind": "zone",
            "region_id": zone_id,
            "zone_id": zone_id,
            "zone_name": zone_id,
            "zone_type": "feeder",
            "activity_detected": True,
            "last_seen_at": seen_at,
            "best_frame_sequence": 1,
            "best_frame_captured_at": seen_at,
            "best_score": 0.9,
            "monitoring_policy": policy,
        }

    brief = _LiveActivitySession.from_detection(
        values(
            "brief",
            started_at,
            {
                "minimum_sustained_activity_seconds": 5,
                "quiet_period_seconds": 10,
                "maximum_visit_duration_seconds": 60,
                "maximum_evidence_frames": 1,
            },
        ),
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        region_key="zone:brief",
        now=started_at,
        frame_bytes=b"brief",
        frame_content_type="image/jpeg",
    )
    brief.mark_ready_for_review(quiet_seconds=4)
    assert brief.ready_for_review is True
    assert brief.review_state == "ready_for_review"

    session = _LiveCameraSession(
        config=SimpleNamespace(
            stream_id=STREAM_ID,
            source_id=SOURCE_ID,
            live_stream_type="rtsp",
        ),
        process=FakeFfmpegProcess([]),
        max_runtime_seconds=300,
    )
    short_quiet = session.record_activity_detection(
        values(
            "short-quiet",
            started_at - timedelta(seconds=10),
            {
                "minimum_sustained_activity_seconds": 0,
                "quiet_period_seconds": 5,
                "maximum_visit_duration_seconds": 60,
                "maximum_evidence_frames": 1,
            },
        ),
        frame_bytes=b"short-quiet",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )
    long_quiet = session.record_activity_detection(
        values(
            "long-quiet",
            started_at - timedelta(seconds=10),
            {
                "minimum_sustained_activity_seconds": 0,
                "quiet_period_seconds": 20,
                "maximum_visit_duration_seconds": 60,
                "maximum_evidence_frames": 4,
            },
        ),
        frame_bytes=b"long-quiet",
        frame_content_type="image/jpeg",
        quiet_window_seconds=30,
    )
    assert short_quiet is not None and long_quiet is not None
    ready = session.mark_quiet_activity_sessions_ready_for_review(quiet_seconds=30)
    assert {item.zone_id for item in ready} == {"short-quiet", "long-quiet"}

    maximum = session.record_activity_detection(
        values(
            "maximum",
            started_at,
            {
                "minimum_sustained_activity_seconds": 0,
                "quiet_period_seconds": 5,
                "maximum_visit_duration_seconds": 5,
                "maximum_evidence_frames": 1,
            },
        ),
        frame_bytes=b"maximum-first",
        frame_content_type="image/jpeg",
        quiet_window_seconds=5,
    )
    assert maximum is not None
    finalized = session.record_activity_detection(
        values(
            "maximum",
            started_at + timedelta(seconds=6),
            {
                "minimum_sustained_activity_seconds": 0,
                "quiet_period_seconds": 5,
                "maximum_visit_duration_seconds": 5,
                "maximum_evidence_frames": 1,
            },
        ),
        frame_bytes=b"maximum-second",
        frame_content_type="image/jpeg",
        quiet_window_seconds=5,
    )
    assert finalized is not None
    assert finalized.ready_for_review is True
    assert finalized.review_state == "maximum_duration"

    evidence_activity = _LiveActivitySession.from_detection(
        values(
            "evidence",
            started_at,
            {
                "minimum_sustained_activity_seconds": 0,
                "quiet_period_seconds": 5,
                "maximum_visit_duration_seconds": 60,
                "maximum_evidence_frames": 1,
            },
        ),
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        region_key="zone:evidence",
        now=started_at,
        frame_bytes=b"evidence-0",
        frame_content_type="image/jpeg",
    )
    for index in range(1, 5):
        evidence_activity.record_detection(
            values("evidence", started_at + timedelta(seconds=index), {}),
            now=started_at + timedelta(seconds=index),
            frame_bytes=f"evidence-{index}".encode(),
            frame_content_type="image/jpeg",
        )
    assert len(evidence_activity.evidence_frames(max_frames=1)) == 1


async def test_disabled_zone_does_not_qualify_live_activity(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disabled = await client.put(
        "/api/zones/zone-feeder/monitoring-policy",
        json={"monitoring_enabled": False},
    )
    assert disabled.status_code == 200
    frame_0 = b"\xff\xd8zone-policy-off-0\xff\xd9"
    frame_1 = b"\xff\xd8zone-policy-off-1\xff\xd9"
    captured_at = datetime.now(UTC)
    patch_camera_processes_to_fail(monkeypatch)
    patch_live_motion_decoder(
        monkeypatch,
        {
            frame_0: blank_frame(width=100, height=100),
            frame_1: frame_with(
                [(30, 40), (30, 41), (31, 40), (31, 41)],
                width=100,
                height=100,
            ),
        },
    )
    live_frame_cache.store_latest_frame(STREAM_ID, frame_0, captured_at=captured_at)
    live_frame_cache.store_latest_frame(
        STREAM_ID,
        frame_1,
        captured_at=captured_at + timedelta(seconds=1),
    )

    response = await client.post(
        f"/api/streams/{STREAM_ID}/live-motion/evaluate",
        json={
            "save_best_frame": False,
            "create_review_activity": False,
            "min_triggered_frames": 1,
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["activity_detected"] is False
    assert result["uses_auto_regions"] is False
    assert "Monitoring disabled for Zone: Feeder." in result["warnings"]
    assert result["creates_truth"] is False
