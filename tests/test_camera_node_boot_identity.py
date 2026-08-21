"""Camera Node Boot Identity + Autonomous Recovery v1.

Covers: stable per-boot identity (`mockingbird_node.identity`), the bounded
startup self-test (`mockingbird_node.selftest`), the sd_notify/watchdog
heartbeat (`mockingbird_node.watchdog`), the additive `/node/v1/health`
fields, backward compatibility with an older Node's response shape, and the
host-side durable boot-identity/last-seen bookkeeping
(`ProductRepository._record_camera_node_boot_observation`). See
docs/camera-node-installer-design.md.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import os
import socket
import tempfile
import time
from pathlib import Path

import httpx
import pytest

from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel
from mockingbird_node.app import create_node_app
from mockingbird_node.config import CameraNodeConfig
from mockingbird_node import identity, selftest, watchdog


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# --------------------------------------------------------------------------
# identity.py -- stable boot identity, uptime, service version
# --------------------------------------------------------------------------


def test_read_boot_id_from_a_real_file(tmp_path: Path) -> None:
    path = tmp_path / "boot_id"
    path.write_text("e52fe936-ae14-4232-b761-d51c5a2ac3b2\n", encoding="ascii")
    assert identity.read_boot_id(path=path) == "e52fe936-ae14-4232-b761-d51c5a2ac3b2"


def test_read_boot_id_missing_file_returns_none_never_fabricated(tmp_path: Path) -> None:
    """Explicit milestone requirement: never derive `boot_id` from the PID
    or wall clock -- a missing kernel fact must degrade to `None`."""

    assert identity.read_boot_id(path=tmp_path / "does-not-exist") is None


def test_read_boot_id_rejects_malformed_content(tmp_path: Path) -> None:
    path = tmp_path / "boot_id"
    path.write_text("<not a boot id; way too long " + "x" * 100, encoding="ascii")
    assert identity.read_boot_id(path=path) is None


def test_read_os_uptime_seconds_parses_the_first_proc_uptime_field(tmp_path: Path) -> None:
    path = tmp_path / "uptime"
    path.write_text("118727.04 470882.71\n", encoding="ascii")
    assert identity.read_os_uptime_seconds(path=path) == pytest.approx(118727.04)


def test_read_os_uptime_seconds_missing_file_returns_none(tmp_path: Path) -> None:
    assert identity.read_os_uptime_seconds(path=tmp_path / "missing") is None


def test_service_clock_uses_only_a_monotonic_source() -> None:
    """Never wall-clock time -- an NTP correction or manual clock change
    must not move uptime backwards or forwards."""

    ticks = iter([100.0, 100.0, 142.5])
    clock = identity.ServiceClock(monotonic=lambda: next(ticks))
    assert clock.uptime_seconds() == pytest.approx(0.0)
    assert clock.uptime_seconds() == pytest.approx(42.5)


def test_resolve_service_version_never_raises_and_returns_a_string() -> None:
    # This test process never has the separate `mockingbird-camera-node`
    # wheel installed -- exactly the dev-checkout fallback path.
    version = identity.resolve_service_version()
    assert isinstance(version, str) and version
    from mockingbird_node import __version__

    assert version == __version__


# --------------------------------------------------------------------------
# selftest.py -- bounded, non-blocking startup self-test
# --------------------------------------------------------------------------


class _FakeCamera:
    def __init__(self, status: str) -> None:
        self.status = status


class _FakeProvider:
    def __init__(self, cameras: list, *, delay_seconds: float = 0.0, raises: bool = False) -> None:
        self._cameras = cameras
        self._delay_seconds = delay_seconds
        self._raises = raises

    def cameras(self) -> list:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if self._raises:
            raise RuntimeError("provider exploded")
        return self._cameras


def test_self_test_passes_with_an_available_camera(tmp_path: Path) -> None:
    result = selftest.run_startup_self_test(
        provider=_FakeProvider([_FakeCamera("available")]),
        pairing_state_path=tmp_path / "state" / "pairing.json",
    )
    assert result.status == "passed"
    assert result.providers_initialized is True
    assert result.camera_available is True
    assert result.pairing_state_writable is True
    assert result.reasons == ()


def test_self_test_degrades_never_fails_when_no_camera_is_available(tmp_path: Path) -> None:
    """Explicit milestone requirement: a camera being absent must never
    look like the Node itself is broken, and must never block startup."""

    result = selftest.run_startup_self_test(
        provider=_FakeProvider([_FakeCamera("unavailable")]),
        pairing_state_path=tmp_path / "state" / "pairing.json",
    )
    assert result.status == "degraded"
    assert result.camera_available is False
    assert "no_camera_available" in result.reasons


def test_self_test_degrades_when_provider_enumeration_hangs(tmp_path: Path) -> None:
    """Bounded: a truly wedged provider call must not hang the process
    before it ever binds its listening socket."""

    result = selftest.run_startup_self_test(
        provider=_FakeProvider([], delay_seconds=2.0),
        pairing_state_path=tmp_path / "state" / "pairing.json",
        timeout_seconds=0.2,
    )
    assert result.status == "degraded"
    assert result.providers_initialized is False
    assert "provider_enumeration_timed_out" in result.reasons


def test_self_test_degrades_when_provider_enumeration_raises(tmp_path: Path) -> None:
    result = selftest.run_startup_self_test(
        provider=_FakeProvider([], raises=True),
        pairing_state_path=tmp_path / "state" / "pairing.json",
    )
    assert result.status == "degraded"
    assert result.providers_initialized is False
    assert "provider_enumeration_failed" in result.reasons


def test_self_test_reports_unwritable_pairing_state_path() -> None:
    # A path whose parent cannot possibly be created (an existing regular
    # file standing where a directory is required).
    with tempfile.NamedTemporaryFile() as blocker:
        blocked_path = Path(blocker.name) / "state" / "pairing.json"
        result = selftest.run_startup_self_test(
            provider=_FakeProvider([_FakeCamera("available")]),
            pairing_state_path=blocked_path,
        )
    assert result.status == "degraded"
    assert result.pairing_state_writable is False
    assert "pairing_state_path_unwritable" in result.reasons


# --------------------------------------------------------------------------
# watchdog.py -- sd_notify protocol + bounded, meaningful heartbeat
# --------------------------------------------------------------------------


def test_sd_notify_is_a_safe_no_op_without_notify_socket() -> None:
    assert watchdog.sd_notify(b"READY=1\n", socket_path=None) is False


def test_sd_notify_sends_real_bytes_over_a_real_unix_datagram_socket(tmp_path: Path) -> None:
    socket_path = str(tmp_path / "notify.sock")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(socket_path)
    server.settimeout(2.0)
    try:
        assert watchdog.sd_notify(b"READY=1\n", socket_path=socket_path) is True
        data, _ = server.recvfrom(4096)
        assert data == b"READY=1\n"
    finally:
        server.close()


def test_watchdog_timeout_seconds_parses_watchdog_usec(monkeypatch) -> None:
    monkeypatch.setenv("WATCHDOG_USEC", "30000000")
    assert watchdog.watchdog_timeout_seconds() == pytest.approx(30.0)
    assert watchdog.watchdog_ping_interval_seconds() == pytest.approx(15.0)


def test_watchdog_timeout_seconds_absent_without_the_env_var(monkeypatch) -> None:
    monkeypatch.delenv("WATCHDOG_USEC", raising=False)
    assert watchdog.watchdog_timeout_seconds() is None
    assert watchdog.watchdog_ping_interval_seconds() is None


@pytest.mark.anyio
async def test_watchdog_loop_pings_only_after_a_real_probe_completes() -> None:
    progress = watchdog.WatchdogProgress(enabled=True, ping_interval_seconds=0.01)
    sent: list[bytes] = []
    ticks = iter([0.0, 0.01, 0.02, 0.03])

    async def fast_probe() -> str:
        return "ok"

    task = asyncio.create_task(
        watchdog.run_watchdog_loop(
            progress=progress,
            probe=fast_probe,
            probe_timeout_seconds=0.05,
            sleep=lambda _seconds: asyncio.sleep(0),  # deterministic, no real wall-clock wait
            notify=lambda message: sent.append(message) or True,
            monotonic=lambda: next(ticks, 0.03),
        )
    )
    for _ in range(20):
        await asyncio.sleep(0)
        if len(sent) >= 2:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sent[:2] == [b"WATCHDOG=1\n", b"WATCHDOG=1\n"]
    assert progress.last_probe_ok is True
    assert progress.consecutive_probe_failures == 0


@pytest.mark.anyio
async def test_watchdog_loop_withholds_the_ping_when_the_probe_hangs() -> None:
    """The watchdog signal must correspond to meaningful Camera Node
    progress -- never a bare timer. A probe that never completes within
    its own bound must never be pinged as if it had."""

    progress = watchdog.WatchdogProgress(enabled=True, ping_interval_seconds=0.01)
    sent: list[bytes] = []

    async def hanging_probe() -> None:
        await asyncio.sleep(10.0)

    task = asyncio.create_task(
        watchdog.run_watchdog_loop(
            progress=progress,
            probe=hanging_probe,
            probe_timeout_seconds=0.01,
            sleep=lambda _seconds: asyncio.sleep(0),
            notify=lambda message: sent.append(message) or True,
        )
    )
    # `asyncio.wait_for`'s own timeout is real event-loop time (the
    # injectable `sleep=`/`monotonic=` seams only control the *outer*
    # ping-interval wait, not `wait_for` itself) -- a real, bounded wait is
    # correct here, not a busy poll.
    for _ in range(20):
        await asyncio.sleep(0.02)
        if progress.consecutive_probe_failures >= 2:
            break
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert sent == []
    assert progress.last_probe_ok is False
    assert progress.consecutive_probe_failures >= 2


# --------------------------------------------------------------------------
# /node/v1/health -- additive fields, backward-compatible with old Nodes
# --------------------------------------------------------------------------


def _synthetic_config(**overrides: object) -> CameraNodeConfig:
    os.environ["MOCKINGBIRD_NODE_PROVIDERS"] = "synthetic"
    os.environ["MOCKINGBIRD_NODE_TESTING"] = "1"
    return CameraNodeConfig.from_environment()


@pytest.mark.anyio
async def test_health_endpoint_exposes_boot_identity_and_selftest_fields(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MOCKINGBIRD_NODE_PAIRING_STATE_PATH", str(tmp_path / "pairing.json"))
    config = _synthetic_config()
    app = create_node_app(config)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/node/v1/health")
    assert response.status_code == 200
    body = response.json()
    # Every pre-existing field is unchanged.
    assert body["node_id"].startswith("node-")
    assert body["status"] == "available"
    # Additive fields this milestone adds.
    assert "boot_id" in body  # str or None -- never absent from the shape
    assert isinstance(body["os_uptime_seconds"], (float, int, type(None)))
    assert isinstance(body["service_uptime_seconds"], (float, int))
    assert body["service_version"]
    assert body["self_test"]["status"] in {"passed", "degraded"}
    assert body["self_test"]["camera_available"] is True  # synthetic camera is always available
    assert body["watchdog"]["enabled"] is False  # no NOTIFY_SOCKET in this test process


@pytest.mark.anyio
async def test_analysis_stream_carries_boot_identity_headers(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MOCKINGBIRD_NODE_PAIRING_STATE_PATH", str(tmp_path / "pairing.json"))
    config = _synthetic_config()
    app = create_node_app(config)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pair_response = await client.post(
            "/node/v1/pair", json={"pairing_code": app.state.pairing_code}
        )
        credential = pair_response.json()["credential"]
        camera_id = pair_response.json()["cameras"][0]["camera_id"]
        async with client.stream(
            "GET",
            f"/node/v1/cameras/{camera_id}/analysis-stream",
            headers={"Authorization": f"Bearer {credential}", "X-MockingBird-Max-Frames": "1"},
        ) as stream_response:
            raw = b""
            async for chunk in stream_response.aiter_bytes():
                raw += chunk
    assert b"X-MockingBird-Node-Service-Version:" in raw
    if app.state.boot_id:  # this sandbox has a real boot_id; a CI host without /proc may not
        assert f"X-MockingBird-Node-Boot-Id: {app.state.boot_id}".encode() in raw


def test_old_node_health_response_shape_still_parses_via_the_host_client() -> None:
    """Backward compatibility: a real response captured from a Camera Node
    running *before* this milestone (no boot_id/uptime/self_test/watchdog
    fields at all) must not break the host's own parsing -- see
    `CameraNodeClient.health`, which returns the decoded dict as-is."""

    from mockingbird.source_providers.camera_node import _safe_json

    old_response = json.dumps(
        {
            "node_id": "node-76ec8e53ae586dd0",
            "display_name": "Pi Camera Node",
            "api_version": "v1",
            "status": "available",
            "camera_count": 8,
            "available_camera_count": 8,
            "pairing_required": False,
        }
    ).encode("utf-8")
    parsed = _safe_json(old_response)
    assert parsed["node_id"] == "node-76ec8e53ae586dd0"
    # New, additive fields are simply absent -- `.get(...)` on the host side
    # (never a required-field access) is how every caller must read them.
    assert parsed.get("boot_id") is None
    assert parsed.get("self_test") is None


# --------------------------------------------------------------------------
# Repository: durable last-seen / boot-identity bookkeeping
# --------------------------------------------------------------------------


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{tmp_path / 'boot-identity.sqlite3'}", media_root=tmp_path / "media")


def _seed_camera_node_stream(repository: ProductRepository, *, source_id: str, stream_id: str) -> None:
    with repository.session_factory() as session, session.begin():
        session.add(
            CameraSourceModel(
                id=source_id, name="Test Camera Node", kind="integration",
                status="connected", description="",
            )
        )
        session.add(
            StreamModel(
                id=stream_id, source_id=source_id, name="Test stream",
                description="", is_live=True,
            )
        )


def test_same_boot_id_across_two_observations_is_not_a_transition(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed_camera_node_stream(repository, source_id="source-1", stream_id="stream-1")
    first = datetime.now(UTC)
    outcome_one = repository.record_observation_exposure_frame(
        stream_id="stream-1", runtime_generation_id="gen-1",
        healthy_at=first, now=first, node_boot_id="boot-A", node_service_version="0.1.0",
    )
    second = first + timedelta(seconds=45)
    outcome_two = repository.record_observation_exposure_frame(
        stream_id="stream-1", runtime_generation_id="gen-1",
        healthy_at=second, now=second, node_boot_id="boot-A",
    )
    repository.close()

    assert outcome_one.recorded is True
    assert outcome_one.boot_transition_detected is False  # first-ever observation is not a "transition"
    assert outcome_two.boot_transition_detected is False


def test_new_boot_id_is_detected_as_a_transition(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed_camera_node_stream(repository, source_id="source-1", stream_id="stream-1")
    first = datetime.now(UTC)
    repository.record_observation_exposure_frame(
        stream_id="stream-1", runtime_generation_id="gen-1",
        healthy_at=first, now=first, node_boot_id="boot-A",
    )
    rebooted_at = first + timedelta(minutes=1)
    outcome = repository.record_observation_exposure_frame(
        stream_id="stream-1", runtime_generation_id="gen-2",
        healthy_at=rebooted_at, now=rebooted_at, node_boot_id="boot-B",
    )

    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, "source-1")
        history = json.loads(source.camera_node_recent_boot_transitions_json)
    repository.close()

    assert outcome.boot_transition_detected is True
    assert source is not None
    assert history[0]["boot_id"] == "boot-B"


def test_recent_boot_transition_history_is_bounded_at_five_entries(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _seed_camera_node_stream(repository, source_id="source-1", stream_id="stream-1")
    when = datetime.now(UTC)
    for index in range(8):
        when = when + timedelta(minutes=1)
        repository.record_observation_exposure_frame(
            stream_id="stream-1", runtime_generation_id=f"gen-{index}",
            healthy_at=when, now=when, node_boot_id=f"boot-{index}",
        )
    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, "source-1")
        history = json.loads(source.camera_node_recent_boot_transitions_json)
    repository.close()

    # Never an unbounded ledger (milestone instruction #10); newest first.
    assert len(history) == 5
    assert history[0]["boot_id"] == "boot-7"
    assert history[-1]["boot_id"] == "boot-3"


def test_last_seen_advances_even_without_a_boot_id(tmp_path: Path) -> None:
    """`camera_node_last_seen_at` is real evidence of contact regardless of
    whether the Node reported a boot id (an older Node, for example)."""

    repository = _repository(tmp_path)
    _seed_camera_node_stream(repository, source_id="source-1", stream_id="stream-1")
    when = datetime.now(UTC)
    repository.record_observation_exposure_frame(
        stream_id="stream-1", runtime_generation_id="gen-1", healthy_at=when, now=when,
    )
    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, "source-1")
        last_seen = source.camera_node_last_seen_at
        boot_id = source.camera_node_boot_id
    repository.close()

    assert last_seen is not None
    assert boot_id is None


def test_boot_observation_is_a_safe_no_op_for_an_unknown_stream(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    when = datetime.now(UTC)
    outcome = repository.record_observation_exposure_frame(
        stream_id="stream-does-not-exist", runtime_generation_id="gen-1",
        healthy_at=when, now=when, node_boot_id="boot-A",
    )
    repository.close()
    assert outcome.recorded is False
    assert outcome.boot_transition_detected is False
