"""First-run onboarding detection and persistence.

Covers the MockingBird Installable Local Product v1 milestone's core new
backend behavior: a genuinely new database must show onboarding once, and an
existing (migrating) database must never show it, regardless of restart. See
docs/local-product-packaging-design.md.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest

from mockingbird.api import main as api_main
from mockingbird.api.main import app
from mockingbird.api.schemas import SetupStateUpdate
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import create_database_engine, CURRENT_DATABASE_SCHEMA_VERSION


def _repository(tmp_path: Path, *, name: str = "mockingbird.sqlite3") -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / name}",
        media_root=tmp_path / "media",
    )


def _request(path: str, *, method: str = "GET", json_body: dict | None = None) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, json=json_body)

    return asyncio.run(send())


def test_fresh_database_seeds_incomplete_onboarding(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    state = repository.get_setup_state()

    assert state.completed is False
    assert state.current_step == "welcome"
    assert state.last_created_stream_id is None


def test_existing_database_migrating_to_current_schema_never_shows_onboarding(
    tmp_path: Path,
) -> None:
    # Build a database the way a real pre-existing installation looks: full
    # product data, then rewind it to look like it predates the
    # `app_setup_state` concept entirely (schema version 1, table absent) --
    # exactly what a real installation from before this milestone has.
    repository = _repository(tmp_path)
    before = repository.local_data_status()
    assert before.source_count > 0  # the seeded demo graph, standing in for real user data
    repository.close()

    engine = create_database_engine(repository.db_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE app_setup_state")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 1 WHERE singleton_id = 1")
    engine.dispose()

    migrated = _repository(tmp_path)
    try:
        state = migrated.get_setup_state()
        after = migrated.local_data_status()

        assert state.completed is True
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert after.source_count == before.source_count
        assert after.stream_count == before.stream_count
        assert after.zone_count == before.zone_count
        assert after.review_label_count == before.review_label_count
    finally:
        migrated.close()


def test_migration_guards_a_row_left_behind_by_a_partial_upgrade(tmp_path: Path) -> None:
    """Regression test: a downgrade-replay database that *kept* the table
    (for example one built from an already-current copy, the way this
    repository's own backup-recovery test fixtures work) must not crash the
    migration with a duplicate-row error, and must not silently overwrite
    whatever the existing row already said.
    """

    repository = _repository(tmp_path)
    repository.update_setup_state(
        SetupStateUpdate(current_step="camera", completed=False, last_created_stream_id=None)
    )
    repository.close()

    engine = create_database_engine(repository.db_url)
    with engine.begin() as connection:
        # Only rewind the version -- app_setup_state (and its in-progress row)
        # stays, unlike the test above.
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 1 WHERE singleton_id = 1")
    engine.dispose()

    migrated = _repository(tmp_path)
    try:
        state = migrated.get_setup_state()
        assert state.current_step == "camera"
        assert state.completed is False
    finally:
        migrated.close()


def test_setup_state_persists_across_a_simulated_restart(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.update_setup_state(
        SetupStateUpdate(current_step="observe", completed=False, last_created_stream_id="stream-real-camera")
    )
    repository.close()

    reopened = _repository(tmp_path)
    try:
        state = reopened.get_setup_state()
        assert state.current_step == "observe"
        assert state.completed is False
        assert state.last_created_stream_id == "stream-real-camera"
    finally:
        reopened.close()


def test_update_setup_state_never_clears_stream_id_when_omitted(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.update_setup_state(
        SetupStateUpdate(current_step="camera", completed=False, last_created_stream_id="stream-abc")
    )

    repository.update_setup_state(SetupStateUpdate(current_step="observe", completed=False))

    assert repository.get_setup_state().last_created_stream_id == "stream-abc"


@pytest.fixture
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProductRepository:
    repository = _repository(tmp_path)
    monkeypatch.setattr(api_main, "_repository", repository)
    return repository


def test_api_setup_state_contract(isolated_repository: ProductRepository) -> None:
    get_response = _request("/api/setup/state")
    assert get_response.status_code == 200
    assert get_response.json()["completed"] is False

    put_response = _request(
        "/api/setup/state",
        method="PUT",
        json_body={"current_step": "storage", "completed": False},
    )
    assert put_response.status_code == 200
    assert put_response.json()["current_step"] == "storage"

    confirm_response = _request("/api/setup/state")
    assert confirm_response.json()["current_step"] == "storage"


def test_api_setup_state_rejects_unknown_fields(isolated_repository: ProductRepository) -> None:
    response = _request(
        "/api/setup/state",
        method="PUT",
        json_body={"current_step": "storage", "completed": False, "unexpected_field": "x"},
    )

    assert response.status_code == 422
