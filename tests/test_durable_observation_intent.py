"""Native-Windows Field Reliability Corrections v1, Blocker 2 -- the durable
observation-intent contract (`stream_observation_intents`, schema 61).

Reproduced field defect this closes: after a graceful native-Windows Host
restart, with the Camera Node healthy and reachable throughout, a
previously-observing Stream came back `state=stopped` and stayed stopped until
a person pressed Start observing again
(docs/field-validation-closure-v1-report.md Q-3).

`CameraNodeRecoverySupervisor`'s own use of this intent is covered in
`tests/test_camera_node_recovery.py`. This file covers the persistence layer
and the product actions that write it, plus the migration -- i.e. that the
*intent itself* is durable, correct, and never fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import app, configure_repository
from mockingbird.api.demo_data import STREAM_ID as DEMO_STREAM_ID
from mockingbird.repository.product_repository import (
    OBSERVATION_INTENT_OBSERVING,
    OBSERVATION_INTENT_STOPPED,
    ProductRepository,
)
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    _SCHEMA_MIGRATIONS,
    database_schema_version_is_compatible,
)

EARLIER = datetime(2026, 9, 25, 10, 0, tzinfo=UTC)
LATER = EARLIER + timedelta(hours=3)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    try:
        yield repository
    finally:
        repository.close()


# --------------------------------------------------------------------------
# Schema / migration
# --------------------------------------------------------------------------


def test_schema_61_registers_the_intent_migration_and_stays_reachable() -> None:
    assert CURRENT_DATABASE_SCHEMA_VERSION == 62
    assert 61 in _SCHEMA_MIGRATIONS
    # Every earlier recorded schema must still be able to reach 61.
    assert database_schema_version_is_compatible(1)
    assert database_schema_version_is_compatible(60)


def test_a_fresh_install_has_the_intent_table(repository: ProductRepository) -> None:
    with repository.engine.connect() as connection:
        tables = set(
            connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).scalars()
        )
    assert "stream_observation_intents" in tables


def test_upgrading_from_schema_60_creates_the_table_and_no_intent_rows(tmp_path: Path) -> None:
    """The upgrade must be purely additive, and must leave **zero** intent
    rows: an installation upgraded while nothing was observing must not
    spontaneously start observing on every paired Camera Node, and one
    upgraded while something *was* observing gets no auto-resume either
    (honest, and identical to the pre-milestone behaviour). Intent is only
    ever created by a real product action afterwards."""

    database_path = tmp_path / "upgraded.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        stream_ids = [stream.id for stream in repository.list_streams()]
        assert stream_ids, "the seeded install must have at least one Stream to prove this"
        with repository.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE IF EXISTS stream_observation_intents")
            connection.exec_driver_sql(
                "UPDATE mockingbird_schema SET version = 60 WHERE singleton_id = 1"
            )
    finally:
        repository.close()

    reopened = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        assert reopened.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        with reopened.engine.connect() as connection:
            assert "stream_observation_intents" in set(
                connection.execute(text("SELECT name FROM sqlite_master WHERE type = 'table'")).scalars()
            )
            assert connection.execute(
                text("SELECT count(*) FROM stream_observation_intents")
            ).scalar_one() == 0
        # Every pre-existing Stream survived, and none of them gained an intent.
        assert [stream.id for stream in reopened.list_streams()] == stream_ids
        for stream_id in stream_ids:
            assert reopened.get_stream_observation_intent(stream_id) is None
        assert reopened.streams_intended_observing() == ()
    finally:
        reopened.close()


def test_the_migration_is_idempotent(tmp_path: Path) -> None:
    """Re-running it against a database that already has the table (the
    fresh-install case, where `create_all` got there first) must be a no-op,
    never an error that blocks an upgrade."""

    database_path = tmp_path / "rerun.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        stream_id = repository.list_streams()[0].id
        repository.record_stream_observation_intent(
            stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started",
        )
        with repository.engine.begin() as connection:
            # Rewind the version only -- leave the table and its row in place.
            connection.exec_driver_sql(
                "UPDATE mockingbird_schema SET version = 60 WHERE singleton_id = 1"
            )
    finally:
        repository.close()

    reopened = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        assert reopened.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        # The pre-existing intent row was not dropped or rewritten.
        intent = reopened.get_stream_observation_intent(stream_id)
        assert intent is not None and intent.desired_state == OBSERVATION_INTENT_OBSERVING
    finally:
        reopened.close()


# --------------------------------------------------------------------------
# Persistence semantics
# --------------------------------------------------------------------------


def test_absent_intent_is_none_and_never_reads_as_observing(repository: ProductRepository) -> None:
    stream_id = repository.list_streams()[0].id

    assert repository.get_stream_observation_intent(stream_id) is None
    assert repository.streams_intended_observing() == ()


def test_recording_observing_intent_is_readable_and_listed(repository: ProductRepository) -> None:
    stream_id = repository.list_streams()[0].id

    recorded = repository.record_stream_observation_intent(
        stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started", now=EARLIER,
    )

    assert recorded is not None
    assert recorded.desired_state == OBSERVATION_INTENT_OBSERVING
    assert recorded.observing_intended is True
    assert recorded.requested_reason == "user_started"
    assert recorded.requested_at == EARLIER
    assert repository.get_stream_observation_intent(stream_id) == recorded
    assert repository.streams_intended_observing() == (stream_id,)


def test_stopping_clears_the_intent_without_deleting_the_row(repository: ProductRepository) -> None:
    """A deliberate Stop is recorded as an explicit `stopped` state, not by
    deleting the row: "a person stopped this" and "nobody ever asked" are
    different facts and must stay distinguishable."""

    stream_id = repository.list_streams()[0].id
    repository.record_stream_observation_intent(
        stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started", now=EARLIER,
    )

    stopped = repository.record_stream_observation_intent(
        stream_id, desired_state=OBSERVATION_INTENT_STOPPED, reason="user_stopped", now=LATER,
    )

    assert stopped is not None
    assert stopped.desired_state == OBSERVATION_INTENT_STOPPED
    assert stopped.observing_intended is False
    assert stopped.requested_reason == "user_stopped"
    assert stopped.requested_at == LATER  # the state genuinely changed
    assert repository.get_stream_observation_intent(stream_id) is not None
    assert repository.streams_intended_observing() == ()


def test_requested_at_only_advances_when_the_state_actually_changes(
    repository: ProductRepository,
) -> None:
    """Pressing Start observing again on an already-intended-observing Stream
    must not look like a fresh intent -- `CameraNodeRecoverySupervisor` keys
    its backoff bookkeeping off `requested_at`, so a re-write on every action
    would reset backoff and defeat it."""

    stream_id = repository.list_streams()[0].id
    repository.record_stream_observation_intent(
        stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started", now=EARLIER,
    )

    again = repository.record_stream_observation_intent(
        stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="automatic_resume", now=LATER,
    )

    assert again is not None
    assert again.requested_at == EARLIER  # unchanged
    assert again.updated_at == LATER  # every write is still visible
    assert again.requested_reason == "automatic_resume"


def test_one_stream_can_never_hold_two_intents(repository: ProductRepository) -> None:
    """`stream_id` is the primary key, so a duplicate durable intent is not
    representable at all -- not merely avoided by the writers."""

    stream_id = repository.list_streams()[0].id
    for index in range(5):
        repository.record_stream_observation_intent(
            stream_id,
            desired_state=OBSERVATION_INTENT_OBSERVING if index % 2 == 0 else OBSERVATION_INTENT_STOPPED,
            reason="user_started",
        )

    with repository.engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM stream_observation_intents WHERE stream_id = :sid"),
            {"sid": stream_id},
        ).scalar_one() == 1


def test_an_unknown_stream_records_nothing_rather_than_raising(
    repository: ProductRepository,
) -> None:
    assert (
        repository.record_stream_observation_intent(
            "stream-does-not-exist", desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started",
        )
        is None
    )
    assert repository.streams_intended_observing() == ()


def test_an_invalid_desired_state_is_refused(repository: ProductRepository) -> None:
    stream_id = repository.list_streams()[0].id

    with pytest.raises(ValueError, match="observation_intent_desired_state_invalid"):
        repository.record_stream_observation_intent(
            stream_id, desired_state="paused", reason="user_started",
        )
    assert repository.get_stream_observation_intent(stream_id) is None


def test_intent_survives_reopening_the_database(tmp_path: Path) -> None:
    """The property the whole fix rests on: the intent is durable across a
    process boundary. This is the unit-level stand-in for a Host restart --
    nothing in memory carries over, only the database file."""

    database_path = tmp_path / "durable.sqlite3"
    first = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        stream_id = first.list_streams()[0].id
        first.record_stream_observation_intent(
            stream_id, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started", now=EARLIER,
        )
    finally:
        first.close()

    second = ProductRepository(db_url=f"sqlite:///{database_path}", media_root=tmp_path / "media")
    try:
        intent = second.get_stream_observation_intent(stream_id)
        assert intent is not None
        assert intent.observing_intended is True
        assert intent.requested_at == EARLIER
        assert second.streams_intended_observing() == (stream_id,)
    finally:
        second.close()


def test_streams_intended_observing_lists_only_observing_streams(
    repository: ProductRepository,
) -> None:
    """Two Streams, opposite intents. The second Stream row is inserted
    directly because the seeded install has exactly one and this assertion is
    about the *query*, not about Stream creation -- an intent row's only
    requirement of a Stream is that its `streams` row exists."""

    observing = repository.list_streams()[0].id
    stopped = "stream-second-camera"
    with repository.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO streams (id, source_id, name, description, is_live) "
                "SELECT :new_id, source_id, 'Second camera', '', is_live "
                "FROM streams WHERE id = :existing_id"
            ),
            {"new_id": stopped, "existing_id": observing},
        )
    repository.record_stream_observation_intent(
        observing, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started",
    )
    repository.record_stream_observation_intent(
        stopped, desired_state=OBSERVATION_INTENT_STOPPED, reason="user_stopped",
    )

    assert repository.streams_intended_observing() == (observing,)


# --------------------------------------------------------------------------
# Product actions that write it
# --------------------------------------------------------------------------


@pytest.fixture
def api_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'api.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def client(api_repository: ProductRepository) -> LegacyAuthenticatedSyncTestClient:
    return LegacyAuthenticatedSyncTestClient(app)


def _route_demo_stream_to_the_camera_node_lane(client: LegacyAuthenticatedSyncTestClient) -> None:
    """A real `camera_node` Source, so lane resolution routes Start/Stop
    observing to the Observation Engine (the same helper shape
    `tests/test_observation_session_api.py` uses). Pairing is deliberately not
    completed -- that is irrelevant to whether *intent* is recorded, and keeps
    this test hardware-free."""

    response = client.patch(
        "/api/sources/source-backyard-demo/provider-configuration",
        json={"provider_key": "camera_node", "config": {}},
    )
    assert response.status_code == 200


def test_start_observing_records_durable_observing_intent(
    client: LegacyAuthenticatedSyncTestClient, api_repository: ProductRepository,
) -> None:
    _route_demo_stream_to_the_camera_node_lane(client)
    assert api_repository.get_stream_observation_intent(DEMO_STREAM_ID) is None

    assert client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start").status_code == 200

    intent = api_repository.get_stream_observation_intent(DEMO_STREAM_ID)
    assert intent is not None
    assert intent.desired_state == OBSERVATION_INTENT_OBSERVING
    assert intent.requested_reason == "user_started"
    assert api_repository.streams_intended_observing() == (DEMO_STREAM_ID,)


def test_stop_observing_records_durable_stopped_intent(
    client: LegacyAuthenticatedSyncTestClient, api_repository: ProductRepository,
) -> None:
    _route_demo_stream_to_the_camera_node_lane(client)
    assert client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start").status_code == 200

    assert client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/stop").status_code == 200

    intent = api_repository.get_stream_observation_intent(DEMO_STREAM_ID)
    assert intent is not None
    assert intent.desired_state == OBSERVATION_INTENT_STOPPED
    assert intent.requested_reason == "user_stopped"
    assert api_repository.streams_intended_observing() == ()


def test_stop_observing_clears_intent_even_with_no_session_in_this_process(
    client: LegacyAuthenticatedSyncTestClient, api_repository: ProductRepository,
) -> None:
    """The post-restart Stop: this process never held a session, so the engine's
    own `stop()` returns `None` and the durable intent is the only thing left to
    clear. Pressing Stop must still make the Stream stay stopped forever."""

    _route_demo_stream_to_the_camera_node_lane(client)
    api_repository.record_stream_observation_intent(
        DEMO_STREAM_ID, desired_state=OBSERVATION_INTENT_OBSERVING, reason="user_started",
    )

    assert client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/stop").status_code == 200

    intent = api_repository.get_stream_observation_intent(DEMO_STREAM_ID)
    assert intent is not None and intent.desired_state == OBSERVATION_INTENT_STOPPED


def test_start_observing_on_a_stream_with_no_runtime_records_no_intent(
    client: LegacyAuthenticatedSyncTestClient, api_repository: ProductRepository,
) -> None:
    """The seeded Stream has no provider configured, so Start observing reports
    an honest "no integrated runtime" and returns before the Camera Node lane.
    It must leave no intent behind for a later process to act on."""

    assert client.post(f"/api/streams/{DEMO_STREAM_ID}/observation/start").status_code == 200

    assert api_repository.get_stream_observation_intent(DEMO_STREAM_ID) is None
    assert api_repository.streams_intended_observing() == ()


def test_archiving_a_source_clears_its_streams_observing_intent(
    client: LegacyAuthenticatedSyncTestClient, api_repository: ProductRepository,
) -> None:
    """Archiving already "explicitly cancels future restart" for the legacy
    lane. The Camera Node lane needs the same, so un-archiving later can never
    silently resume observation nobody asked for."""

    # A real, non-demo camera: the seeded sample Source deliberately cannot be
    # archived at all (`demo_source_immutable`, 400).
    created = client.post("/api/sources", json={"name": "Side feeder camera"})
    assert created.status_code == 201
    source_id = created.json()["source"]["id"]
    stream_id = created.json()["stream"]["id"]
    assert (
        client.patch(
            f"/api/sources/{source_id}/provider-configuration",
            json={"provider_key": "camera_node", "config": {}},
        ).status_code
        == 200
    )
    assert client.post(f"/api/streams/{stream_id}/observation/start").status_code == 200
    assert api_repository.streams_intended_observing() == (stream_id,)

    response = client.patch(f"/api/sources/{source_id}", json={"archived": True})
    assert response.status_code == 200

    intent = api_repository.get_stream_observation_intent(stream_id)
    assert intent is not None
    assert intent.desired_state == OBSERVATION_INTENT_STOPPED
    assert intent.requested_reason == "source_archived"
    assert api_repository.streams_intended_observing() == ()
