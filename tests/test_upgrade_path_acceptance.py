"""Upgrade-path acceptance: an existing, previously-current-schema
installation upgrades in place and remains usable through the real HTTP API
(First-Hour Onboarding + Whole-Product Observability Closure v1, "A10").

Confirmed by this milestone's own investigation: an unusually rich set of
per-schema-version migration tests already exists in test_persistence.py
(19+, spanning v1 through v41->v42) -- but every one of them asserts at the
repository-object level, never through the FastAPI HTTP layer a real
upgraded installation's frontend actually talks to. This extends the exact
same rewind convention (`test_schema_41_upgrades_to_current_with_research_
collections`'s "drop the newest table, roll the recorded version back")
one step further: through `/api/dashboard/summary` and `/api/analytics/
place-activity-report` post-migration.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine


def test_a_v41_installation_upgrades_in_place_and_today_works_over_http(tmp_path: Path) -> None:
    """existing v41-ish retained installation -> current application ->
    migrations -> existing Sources/Visits/reviews still readable -> Today
    works -- all driven through the real HTTP API, not the repository
    object directly."""

    db_path = tmp_path / "mockingbird.sqlite3"
    media_root = tmp_path / "media"

    # 1. A representative "existing installation": build a real, fully-
    # current, demo-seeded database (the same seed_if_empty() a real first
    # launch produces), note what it already has, then roll it back to the
    # previously-current schema -- the exact rewind
    # test_schema_41_upgrades_to_current_with_research_collections already
    # established as this repository's own convention for this table.
    bootstrap = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    existing_source_count = len(bootstrap.list_sources())
    existing_visit_count = len(bootstrap.list_visits())
    assert existing_source_count >= 1  # the demo seed always provides at least one
    bootstrap.close()

    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE research_collections")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 41 WHERE singleton_id = 1")
        # A genuinely *established* installation completed onboarding long
        # ago -- unlike a database that is merely freshly created and then
        # has its own schema number rewound (which schema 29's own seeding
        # already stamped completed=False, since it was never actually
        # used). Without this, the scenario under test would silently
        # collapse into "brand new database," not "existing retained
        # installation" -- exactly the distinction A10 asks this test to
        # cover, caught by this test's own first real run.
        connection.exec_driver_sql("UPDATE app_setup_state SET completed = 1 WHERE singleton_id = 1")
    engine.dispose()

    # 2. "current application": a fresh ProductRepository against that same
    # file runs the real migration-on-startup path (no manual migration
    # step -- see runtime.run_preflight -> get_repository()).
    upgraded = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    assert upgraded.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION

    async def scenario() -> None:
        configure_repository(upgraded)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            # 3. Existing Sources/Visits still readable -- through the real
            # API, not a direct repository call.
            sources = await client.get("/api/sources")
            assert sources.status_code == 200
            assert len(sources.json()) == existing_source_count

            visits = await client.get("/api/visits")
            assert visits.status_code == 200
            assert len(visits.json()) == existing_visit_count

            # 4. An established installation never re-shows onboarding --
            # the schema-29 migration seeds `completed=True` for exactly
            # this case (see local-product-packaging-design.md).
            setup_state = await client.get("/api/setup/state")
            assert setup_state.status_code == 200
            assert setup_state.json()["completed"] is True

            # 5. Today works: both report surfaces render without error for
            # the now-upgraded, pre-existing installation.
            dashboard = await client.get("/api/dashboard/summary")
            assert dashboard.status_code == 200

            now = datetime.now(UTC)
            report = await client.post(
                "/api/analytics/place-activity-report",
                json={"start_at": (now - timedelta(days=1)).isoformat(), "end_at": now.isoformat()},
            )
            assert report.status_code == 200

            doctor_health = await client.get("/api/product/health")
            assert doctor_health.status_code == 200
            assert doctor_health.json()["database_schema_version"] == CURRENT_DATABASE_SCHEMA_VERSION

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        upgraded.close()
