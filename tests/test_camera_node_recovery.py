"""24/7 Field Reliability Corrections v1: `CameraNodeRecoverySupervisor`
-- automatic Camera Node observation resume after a `camera_unavailable`
stop, without requiring a person to press Start observing again.

Most scenarios use lightweight, structurally-typed fakes (a fake session
manager, repository, and health probe) for fast, fully deterministic
control over backoff timing and stop-reason eligibility -- exactly the
"simulation/unit coverage first" this milestone calls for. One end-to-end
test exercises the real `ObservationEngineSessionManager` (with a fixture
provider/transport, mirroring `test_engine_runtime.py`'s own established
hardware-free convention) to prove the real integration, not just this
file's own fakes, actually wires together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.api.schemas import CameraSource, SourceKind, SourceStatus
from mockingbird.observation.camera_node_recovery import (
    CameraNodeRecoverySupervisor,
    DEFAULT_BACKOFF_SCHEDULE_SECONDS,
)
from mockingbird.observation.engine_runtime import ObservationEngineSessionStatus
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig
from mockingbird.source_providers.camera_node import CameraNodeClientError

STREAM_ID = "stream-backyard-feeder"
SOURCE_ID = "source-backyard-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)


def _config(**overrides: object) -> StreamLivePlaybackConfig:
    values: dict[str, object] = dict(
        stream_id=STREAM_ID, source_id=SOURCE_ID, provider_key="camera_node",
        live_stream_url=None, live_stream_type="camera_node",
        camera_node_base_address="http://192.168.1.50:8787", camera_node_credential="fixture-credential",
        camera_node_camera_id="cam-1", camera_node_id="node-1",
        camera_node_monitoring_profile_id="monitoring-profile", camera_node_evidence_profile_id="evidence-profile",
    )
    values.update(overrides)
    return StreamLivePlaybackConfig(**values)


@dataclass
class _FakeStream:
    id: str


@dataclass
class _FakeIntent:
    """Structural double for `StreamObservationIntent` -- only the two members
    the supervisor reads."""

    desired_state: str
    requested_at: datetime = NOW

    @property
    def observing_intended(self) -> bool:
        return self.desired_state == "observing"


class _FakeRepository:
    """Structural double for `ProductRepository`: only the methods
    `CameraNodeRecoverySupervisor` actually calls.

    `intents` is keyed by stream id and defaults to empty -- i.e. no durable
    observation intent has ever been expressed, which is exactly the state
    every pre-existing test in this file was written against and must keep
    behaving identically under (no Host-restart candidate can arise from an
    absent intent)."""

    def __init__(
        self,
        *,
        streams: list[_FakeStream],
        configs: dict[str, StreamLivePlaybackConfig],
        sources: dict[str, CameraSource],
        intents: dict[str, _FakeIntent] | None = None,
    ) -> None:
        self._streams = streams
        self._configs = configs
        self._sources = sources
        self.intents = dict(intents or {})
        self.close_count = 0

    def list_streams(self) -> list[_FakeStream]:
        return list(self._streams)

    def streams_intended_observing(self) -> tuple[str, ...]:
        return tuple(
            stream_id for stream_id, intent in self.intents.items() if intent.observing_intended
        )

    def get_stream_observation_intent(self, stream_id: str) -> _FakeIntent | None:
        return self.intents.get(stream_id)

    def get_stream_live_playback_config(self, stream_id: str) -> StreamLivePlaybackConfig | None:
        return self._configs.get(stream_id)

    def get_source(self, source_id: str) -> CameraSource | None:
        return self._sources.get(source_id)

    def stream_privacy_ignore_regions(self, stream_id: str) -> tuple[tuple[float, float, float, float], ...]:
        return ()

    def close(self) -> None:
        self.close_count += 1


def _repository_factory(repository: _FakeRepository):
    return lambda: repository


@dataclass
class _FakeSessionManager:
    """Structural double for `ObservationEngineSessionManager`: records
    every `.start()` call and lets a test script arbitrary `.status()`
    sequences without running any real background thread."""

    statuses: dict[str, ObservationEngineSessionStatus] = field(default_factory=dict)
    start_calls: list[tuple[str, StreamLivePlaybackConfig]] = field(default_factory=list)
    resume_result: str = "observing"  # or "camera_unavailable" to simulate an immediate re-failure

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        return self.statuses.get(stream_id)

    def start(
        self, stream_id: str, config: StreamLivePlaybackConfig, *, privacy_ignore_regions=(),
    ) -> ObservationEngineSessionStatus:
        self.start_calls.append((stream_id, config))
        if self.resume_result == "observing":
            status = _status(stream_id, state="observing")
        else:
            status = _status(
                stream_id, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW,
            )
        self.statuses[stream_id] = status
        return status


def _status(
    stream_id: str, *, state: str, stopped_reason: str | None = None, stopped_at: datetime | None = None,
) -> ObservationEngineSessionStatus:
    return ObservationEngineSessionStatus(
        stream_id=stream_id, state=state, observing=state == "observing",
        message="", camera_connected=state == "observing", camera_message="",
        engine_available=state == "observing", engine_message="",
        stopped_at=stopped_at, stopped_reason=stopped_reason,
    )


class _FakeHealthClient:
    def __init__(self, *, healthy: bool = False) -> None:
        self.healthy = healthy
        self.calls: list[str] = []

    def health(self, base_address: str) -> dict[str, object]:
        self.calls.append(base_address)
        if not self.healthy:
            raise CameraNodeClientError("node_unavailable")
        return {}


def _source(status: SourceStatus = SourceStatus.connected) -> CameraSource:
    return CameraSource(id=SOURCE_ID, name="Backyard feeder", kind=SourceKind.integration, status=status, description="")


def _supervisor(
    *,
    session_manager: _FakeSessionManager,
    repository: _FakeRepository,
    health_client: _FakeHealthClient,
    clock,
    backoff_schedule_seconds: tuple[float, ...] = (10.0, 20.0),
) -> CameraNodeRecoverySupervisor:
    return CameraNodeRecoverySupervisor(
        session_manager=session_manager,
        repository_factory=_repository_factory(repository),
        camera_node_client=health_client,
        backoff_schedule_seconds=backoff_schedule_seconds,
        clock=clock,
    )


def _clock(moment: list[datetime]):
    return lambda: moment[0]


# --------------------------------------------------------------------------
# unavailable -> reachable -> observation resumes
# --------------------------------------------------------------------------


def test_reconcile_resumes_once_the_node_becomes_reachable_again() -> None:
    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=False)
    moment = [NOW + timedelta(minutes=1)]
    supervisor = _supervisor(session_manager=manager, repository=repository, health_client=health, clock=_clock(moment))

    # Still unreachable: no resume attempted, no `.start()` call.
    supervisor.reconcile_once()
    assert manager.start_calls == []

    # Node comes back -- advance past the first backoff step so this pass
    # is actually due to probe again (backoff timing itself is covered
    # separately by `test_backoff_bounds_probe_rate_and_never_gives_up_
    # permanently`; this test is only about the unhealthy -> healthy
    # transition).
    health.healthy = True
    moment[0] = moment[0] + timedelta(seconds=10)
    supervisor.reconcile_once()
    assert manager.start_calls == [(STREAM_ID, repository.get_stream_live_playback_config(STREAM_ID))]
    assert manager.status(STREAM_ID).state == "observing"


def test_reconcile_leaves_a_reachable_but_still_observing_stream_untouched() -> None:
    """A Stream that never stopped (or stopped for a non-recoverable
    reason) must never be probed or restarted at all."""

    manager = _FakeSessionManager(statuses={STREAM_ID: _status(STREAM_ID, state="observing")})
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []
    assert health.calls == []


# --------------------------------------------------------------------------
# bounded backoff / repeated flap
# --------------------------------------------------------------------------


def test_backoff_bounds_probe_rate_and_never_gives_up_permanently() -> None:
    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=False)
    moment = [NOW]
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock(moment),
        backoff_schedule_seconds=(10.0, 20.0, 40.0),
    )

    # First pass: eligible immediately (first sighting of this stop).
    supervisor.reconcile_once()
    assert len(health.calls) == 1

    # A pass 1 second later must NOT probe again -- backoff still pending.
    moment[0] = moment[0] + timedelta(seconds=1)
    supervisor.reconcile_once()
    assert len(health.calls) == 1

    # Advance past the first backoff step (10s): probes again.
    moment[0] = moment[0] + timedelta(seconds=10)
    supervisor.reconcile_once()
    assert len(health.calls) == 2

    # Advance past the second step (20s): probes a third time.
    moment[0] = moment[0] + timedelta(seconds=20)
    supervisor.reconcile_once()
    assert len(health.calls) == 3

    # Far beyond the whole schedule: still tries -- capped at the last
    # step, never permanently gives up (a real outage duration is
    # unbounded; this supervisor holds no camera resource while waiting).
    moment[0] = moment[0] + timedelta(hours=5)
    supervisor.reconcile_once()
    assert len(health.calls) == 4
    assert manager.start_calls == []  # still never actually resumed -- Node never recovered in this test


def test_repeated_flap_never_duplicates_a_start_call_per_stop_event() -> None:
    """A Stream that flaps unavailable -> recovers -> unavailable again
    must be handled as two independent stop events, never as one
    unbounded retry loop and never with more than one `.start()` per
    genuine recovery."""

    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
        resume_result="camera_unavailable",  # simulate an immediate re-failure after resuming
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=True)
    moment = [NOW]
    supervisor = _supervisor(session_manager=manager, repository=repository, health_client=health, clock=_clock(moment))

    supervisor.reconcile_once()
    assert len(manager.start_calls) == 1
    # The resumed session immediately failed again with a *new* stopped_at
    # (`resume_result="camera_unavailable"` stamps `stopped_at=NOW`,
    # identical here only because the fake doesn't advance time on its
    # own) -- give it a distinct, later `stopped_at` to model a genuinely
    # new stop event, then confirm it is treated as fresh (immediately
    # eligible again, not still serving out the *first* stop's backoff).
    moment[0] = moment[0] + timedelta(seconds=5)
    manager.statuses[STREAM_ID] = _status(
        STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=moment[0],
    )
    supervisor.reconcile_once()
    assert len(manager.start_calls) == 2

    # Recovers for real this time.
    manager.resume_result = "observing"
    moment[0] = moment[0] + timedelta(seconds=5)
    manager.statuses[STREAM_ID] = _status(
        STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=moment[0],
    )
    supervisor.reconcile_once()
    assert len(manager.start_calls) == 3
    assert manager.status(STREAM_ID).state == "observing"

    # Now genuinely observing -- further reconciles must not touch it again.
    supervisor.reconcile_once()
    assert len(manager.start_calls) == 3


# --------------------------------------------------------------------------
# user-intentional stop is never auto-resumed
# --------------------------------------------------------------------------


@pytest.mark.parametrize("stopped_reason", ["user_stopped", "app_shutdown", "session_ended", None])
def test_non_recoverable_stop_reasons_are_never_auto_resumed(stopped_reason: str | None) -> None:
    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason=stopped_reason, stopped_at=NOW)},
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []
    assert health.calls == []


def test_a_users_stop_immediately_before_the_start_call_wins_the_race() -> None:
    """Narrow race: the health probe succeeds, but the user pressed Stop in
    the moment between eligibility and the actual `.start()` call. The
    final in-memory re-check (`_maybe_recover`'s own last step) must catch
    this and skip the resume -- "user-intentional stop remains stopped and
    is NOT auto-resumed" holds even under this timing."""

    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )

    class _StopsTheStreamOnProbe(_FakeHealthClient):
        def health(self, base_address: str) -> dict[str, object]:
            result = super().health(base_address)
            # Simulate a user's Stop landing exactly between the probe and
            # the recheck-before-start.
            manager.statuses[STREAM_ID] = _status(STREAM_ID, state="stopped", stopped_reason="user_stopped")
            return result

    health = _StopsTheStreamOnProbe(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []
    assert manager.status(STREAM_ID).stopped_reason == "user_stopped"


# --------------------------------------------------------------------------
# shutdown remains respected
# --------------------------------------------------------------------------


def test_shutdown_stops_the_background_loop_and_no_further_reconcile_runs() -> None:
    # No eligible candidates at all -- the background thread's own first,
    # immediate `reconcile_once()` (no initial wait) is a real no-op
    # regardless of exactly when `shutdown()` runs relative to it, so this
    # part of the test is not racing the thread it just started.
    manager = _FakeSessionManager()
    repository = _FakeRepository(streams=[], configs={}, sources={})
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.start()
    try:
        assert supervisor._thread is not None
    finally:
        supervisor.shutdown()
    assert supervisor._thread is None
    assert manager.start_calls == []

    # `reconcile_once` itself also respects a shutdown already in progress
    # (used by the background loop's own final iteration check) -- a
    # `_stop_event` set before a call is a clean no-op, even with an
    # otherwise-eligible, immediately-resumable candidate present.
    eligible_manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    eligible_repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()}, sources={SOURCE_ID: _source()},
    )
    stopped_supervisor = _supervisor(
        session_manager=eligible_manager, repository=eligible_repository,
        health_client=_FakeHealthClient(healthy=True), clock=_clock([NOW]),
    )
    stopped_supervisor._stop_event.set()
    stopped_supervisor.reconcile_once()
    assert eligible_manager.start_calls == []


def test_start_is_idempotent() -> None:
    manager = _FakeSessionManager()
    repository = _FakeRepository(streams=[], configs={}, sources={})
    health = _FakeHealthClient()
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.start()
    first_thread = supervisor._thread
    supervisor.start()
    assert supervisor._thread is first_thread
    supervisor.shutdown()


# --------------------------------------------------------------------------
# eligibility filtering
# --------------------------------------------------------------------------


def test_archived_source_is_never_auto_resumed() -> None:
    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: _config()},
        sources={SOURCE_ID: _source(SourceStatus.archived)},
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []


def test_non_camera_node_stream_is_ignored() -> None:
    manager = _FakeSessionManager(
        statuses={STREAM_ID: _status(STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW)},
    )
    non_camera_node_config = StreamLivePlaybackConfig(
        stream_id=STREAM_ID, source_id=SOURCE_ID, provider_key="local_usb",
        live_stream_url=None, live_stream_type="local_usb",
    )
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)], configs={STREAM_ID: non_camera_node_config}, sources={SOURCE_ID: _source()},
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []
    assert health.calls == []


def test_reconcile_closes_its_own_repository_each_pass() -> None:
    manager = _FakeSessionManager()
    repository = _FakeRepository(streams=[], configs={}, sources={})
    health = _FakeHealthClient()
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    supervisor.reconcile_once()
    assert repository.close_count == 2


def test_default_backoff_schedule_is_bounded_and_never_zero() -> None:
    assert all(value > 0 for value in DEFAULT_BACKOFF_SCHEDULE_SECONDS)
    assert list(DEFAULT_BACKOFF_SCHEDULE_SECONDS) == sorted(DEFAULT_BACKOFF_SCHEDULE_SECONDS)


def test_invalid_construction_is_rejected() -> None:
    manager = _FakeSessionManager()
    repository = _FakeRepository(streams=[], configs={}, sources={})
    health = _FakeHealthClient()
    with pytest.raises(ValueError):
        CameraNodeRecoverySupervisor(
            session_manager=manager, repository_factory=_repository_factory(repository),
            camera_node_client=health, poll_interval_seconds=0,
        )
    with pytest.raises(ValueError):
        CameraNodeRecoverySupervisor(
            session_manager=manager, repository_factory=_repository_factory(repository),
            camera_node_client=health, backoff_schedule_seconds=(),
        )


# --------------------------------------------------------------------------
# Real end-to-end integration: the real ObservationEngineSessionManager
# --------------------------------------------------------------------------


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


# Distinct from `STREAM_ID`/`SOURCE_ID` above -- `ProductRepository()`
# auto-seeds one default demo Stream/Source on fresh construction (see
# `test_camera_health.py`'s own comment on this), and it happens to use
# `STREAM_ID`/`SOURCE_ID`'s exact values; every fake-based test above never
# touches a real repository so this never mattered until now.
REAL_STREAM_ID = "stream-recovery-integration"
REAL_SOURCE_ID = "source-recovery-integration"


def _seed_real_camera_node_stream(repository: ProductRepository) -> None:
    import json

    from mockingbird.repository.product_repository import SourceProviderConfigurationModel
    from mockingbird.storage.models import CameraSourceModel, StreamModel

    with repository.session_factory() as session, session.begin():
        session.add(
            CameraSourceModel(
                id=REAL_SOURCE_ID, name="Backyard feeder", kind="integration", status="connected", description="",
            )
        )
        session.add(
            StreamModel(
                id=REAL_STREAM_ID, source_id=REAL_SOURCE_ID, name="Backyard feeder", description="", is_live=True,
            )
        )
        session.add(
            SourceProviderConfigurationModel(
                source_id=REAL_SOURCE_ID, provider_key="camera_node",
                config_json=json.dumps(
                    {
                        "node_base_address": "http://192.168.1.50:8787",
                        "node_credential": "fixture-credential",
                        "node_camera_id": "cam-1",
                        "node_id": "node-1",
                        "node_monitoring_profile_id": "monitoring-profile",
                        "node_evidence_profile_id": "evidence-profile",
                    }
                ),
                updated_at=NOW,
            )
        )


def test_real_repository_wiring_resolves_the_same_candidate_a_fake_would(
    repository: ProductRepository,
) -> None:
    """Every other test in this file proves the supervisor's own policy
    logic against structural fakes; this proves the *other* half -- that a
    genuinely seeded `ProductRepository` (real `list_streams`/`get_stream_
    live_playback_config`/`get_source`, the same calls `api/main.py`'s own
    Start-observing route makes) resolves into an eligible recovery
    candidate exactly like the fakes assume, closing the gap a
    fake-repository-only suite could otherwise hide (a field name drift
    between `StreamLivePlaybackConfig` and what the real repository
    actually populates, for example)."""

    _seed_real_camera_node_stream(repository)
    manager = _FakeSessionManager(
        statuses={
            REAL_STREAM_ID: _status(REAL_STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW),
        },
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = CameraNodeRecoverySupervisor(
        session_manager=manager, repository_factory=lambda: repository,
        camera_node_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert len(manager.start_calls) == 1
    resumed_stream_id, resumed_config = manager.start_calls[0]
    assert resumed_stream_id == REAL_STREAM_ID
    assert resumed_config.provider_key == "camera_node"
    assert resumed_config.camera_node_base_address == "http://192.168.1.50:8787"
    assert manager.status(REAL_STREAM_ID).state == "observing"


def test_real_repository_excludes_archived_source(repository: ProductRepository) -> None:
    _seed_real_camera_node_stream(repository)
    with repository.session_factory() as session, session.begin():
        from mockingbird.storage.models import CameraSourceModel

        source = session.get(CameraSourceModel, REAL_SOURCE_ID)
        source.status = "archived"

    manager = _FakeSessionManager(
        statuses={
            REAL_STREAM_ID: _status(REAL_STREAM_ID, state="stopped", stopped_reason="camera_unavailable", stopped_at=NOW),
        },
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = CameraNodeRecoverySupervisor(
        session_manager=manager, repository_factory=lambda: repository,
        camera_node_client=health, clock=_clock([NOW]),
    )
    supervisor.reconcile_once()
    assert manager.start_calls == []


# --------------------------------------------------------------------------
# Host-restart recovery (Native-Windows Field Reliability Corrections v1,
# Blocker 2)
#
# A restarted Host is modelled exactly as the product experiences it: a
# `_FakeSessionManager` with **no status at all** for the Stream, because the
# process that held the session object is gone. The durable intent is the only
# surviving statement of what should be happening -- which is the whole point
# of the fix, and why every test below varies the intent, not the status.
# --------------------------------------------------------------------------


def _restarted_host(
    *, intent: _FakeIntent | None, source_status: SourceStatus = SourceStatus.connected,
    config: StreamLivePlaybackConfig | None = None,
) -> tuple[_FakeSessionManager, _FakeRepository]:
    """A fresh process: the session manager knows nothing about any Stream."""

    manager = _FakeSessionManager(statuses={})
    repository = _FakeRepository(
        streams=[_FakeStream(STREAM_ID)],
        configs={STREAM_ID: config or _config()},
        sources={SOURCE_ID: _source(source_status)},
        intents={STREAM_ID: intent} if intent is not None else {},
    )
    return manager, repository


def test_host_restart_resumes_a_stream_whose_durable_intent_is_observing() -> None:
    """The reproduced field defect (Q-3), inverted into a passing assertion:
    with the Node reachable and no in-process session, a standing `observing`
    intent must resume observation with no user action at all."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == [(STREAM_ID, repository.get_stream_live_playback_config(STREAM_ID))]
    assert manager.status(STREAM_ID).state == "observing"


def test_host_restart_leaves_a_deliberately_stopped_stream_stopped() -> None:
    """The safety property that matters most: a person pressed Stop, so the
    Host coming back must NOT resurrect observation -- not even probe for it."""

    manager, repository = _restarted_host(intent=_FakeIntent("stopped"))
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []
    assert manager.status(STREAM_ID) is None


def test_host_restart_never_starts_a_stream_with_no_recorded_intent() -> None:
    """No blind "start every Camera Node on boot." A Stream nobody has ever
    asked to observe -- including every Stream on an installation upgraded to
    schema 61, which gets no intent row from the migration -- stays stopped."""

    manager, repository = _restarted_host(intent=None)
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []


def test_host_restart_with_an_unavailable_node_resumes_once_it_returns() -> None:
    """The Host starts while the Camera Node is still offline (pairing and
    credentials intact, transport simply unavailable). The existing bounded
    backoff must keep probing and resume the moment the Node answers -- no new
    scheduler, no manual intervention, and no giving up."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))
    health = _FakeHealthClient(healthy=False)
    moment = [NOW]
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock(moment),
        backoff_schedule_seconds=(10.0, 20.0),
    )

    supervisor.reconcile_once()
    assert manager.start_calls == []
    assert health.calls == ["http://192.168.1.50:8787"]

    # Still down, and still inside the first backoff step: not re-probed.
    moment[0] = moment[0] + timedelta(seconds=5)
    supervisor.reconcile_once()
    assert len(health.calls) == 1

    # First backoff step elapsed, still down: probed again, still no start.
    moment[0] = moment[0] + timedelta(seconds=5)
    supervisor.reconcile_once()
    assert len(health.calls) == 2
    assert manager.start_calls == []

    # The Node returns.
    health.healthy = True
    moment[0] = moment[0] + timedelta(seconds=20)
    supervisor.reconcile_once()
    assert manager.start_calls == [(STREAM_ID, repository.get_stream_live_playback_config(STREAM_ID))]


def test_host_restart_resume_is_attempted_once_per_intent_not_once_per_pass() -> None:
    """Idempotence across passes: once a resume has started a session, later
    reconcile passes see a live session and must not call `.start()` again --
    no duplicate session, no duplicate observation work."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))
    health = _FakeHealthClient(healthy=True)
    moment = [NOW]
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock(moment),
    )

    for _ in range(4):
        moment[0] = moment[0] + timedelta(minutes=5)
        supervisor.reconcile_once()

    assert len(manager.start_calls) == 1


def test_host_restart_resume_that_fails_again_keeps_backing_off() -> None:
    """A resumed session that immediately re-fails with `camera_unavailable`
    hands over to the *existing* eligibility class (a real stopped session
    object now exists), rather than the intent class retrying every pass."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))
    manager.resume_result = "camera_unavailable"
    health = _FakeHealthClient(healthy=True)
    moment = [NOW]
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock(moment),
        backoff_schedule_seconds=(10.0, 20.0),
    )

    supervisor.reconcile_once()
    assert len(manager.start_calls) == 1
    assert manager.status(STREAM_ID).stopped_reason == "camera_unavailable"

    # The next pass is the ordinary camera_unavailable path, which is due
    # immediately on a newly-seen `stopped_at` -- it must still be exactly one
    # start per stop event, never an unbounded loop.
    moment[0] = moment[0] + timedelta(seconds=1)
    supervisor.reconcile_once()
    assert len(manager.start_calls) == 2


def test_a_users_stop_during_the_health_probe_wins_over_a_host_restart_resume() -> None:
    """The intent is deliberately re-read immediately before `.start()`: a Stop
    that lands while the (potentially slow) health probe is in flight must win,
    exactly as the pre-existing `camera_unavailable` race guard does for a
    stale session object."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))

    class _StopDuringProbe(_FakeHealthClient):
        def health(self, base_address: str) -> dict[str, object]:
            repository.intents[STREAM_ID] = _FakeIntent("stopped")
            return super().health(base_address)

    health = _StopDuringProbe(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert health.calls == ["http://192.168.1.50:8787"]
    assert manager.start_calls == []


def test_a_manual_start_during_the_health_probe_is_not_raced_by_a_resume() -> None:
    """If something else started the Stream while the probe was in flight (a
    user pressing Start observing), the resume must stand down rather than
    start a second session for the same Stream."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))

    class _StartDuringProbe(_FakeHealthClient):
        def health(self, base_address: str) -> dict[str, object]:
            manager.statuses[STREAM_ID] = _status(STREAM_ID, state="observing")
            return super().health(base_address)

    health = _StartDuringProbe(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []


def test_host_restart_never_resumes_an_archived_sources_stream() -> None:
    manager, repository = _restarted_host(
        intent=_FakeIntent("observing"), source_status=SourceStatus.archived,
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []


def test_host_restart_never_resumes_a_stream_that_lost_its_pairing() -> None:
    """Credentials/pairing removed while the Host was down: there is no base
    address to probe, so this is a clean no-op rather than an exception."""

    manager, repository = _restarted_host(
        intent=_FakeIntent("observing"), config=_config(camera_node_base_address=None),
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []


def test_host_restart_never_resumes_a_non_camera_node_stream() -> None:
    """An intent row for a Stream that is no longer a Camera Node Stream (or
    never was) must not drag the legacy live-monitoring lane into this
    supervisor."""

    manager, repository = _restarted_host(
        intent=_FakeIntent("observing"),
        config=_config(
            live_stream_type="rtsp", provider_key="rtsp",
            live_stream_url="rtsp://camera.local/stream",
            camera_node_base_address=None, camera_node_credential=None,
            camera_node_camera_id=None, camera_node_id=None,
        ),
    )
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []


def test_shutdown_prevents_any_host_restart_resume() -> None:
    """`shutdown()` must quiesce the intent class exactly as it does the
    existing one -- an app tearing down never starts a new session."""

    manager, repository = _restarted_host(intent=_FakeIntent("observing"))
    health = _FakeHealthClient(healthy=True)
    supervisor = _supervisor(
        session_manager=manager, repository=repository, health_client=health, clock=_clock([NOW]),
    )

    supervisor.shutdown()
    supervisor.reconcile_once()

    assert manager.start_calls == []
    assert health.calls == []
