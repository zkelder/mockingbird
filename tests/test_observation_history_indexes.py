"""Performance / Scale / Stability Closure v1 -- schema 60 indexes.

MockingBird's core observation tables carried no secondary index at all
before this milestone -- only SQLite's own implicit primary-key indexes.
Every lookup by a foreign key was therefore a full table scan: invisible
on a fresh install, and quadratic on a real one. Measured at an ordinary
established-install size (2,813 Visits / 11,244 media assets / 90 days /
two cameras), adding exactly these indexes took `GET
/api/dataset-quality/summary` from 14.6s to 6.2s, `GET /api/review-queue`
from 9.6s to 6.4s and `GET /api/dashboard/summary` from 4.9s to 3.0s.

These tests assert the two properties that actually matter: a fresh
install and an upgraded install end up with the same indexes, and SQLite
really does use them for the query shapes they were chosen against. A
wall-clock assertion would be environment-dependent; a query plan is not.
"""

from __future__ import annotations

from sqlalchemy import text

from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    _OBSERVATION_HISTORY_INDEXES,
    _SCHEMA_MIGRATIONS,
    database_schema_version_is_compatible,
)
from mockingbird.repository.product_repository import ProductRepository


EXPECTED_INDEX_NAMES = {name for name, _definition in _OBSERVATION_HISTORY_INDEXES}


def _index_names(repository: ProductRepository) -> set[str]:
    with repository.engine.connect() as connection:
        rows = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type = 'index' AND name IS NOT NULL")
        ).scalars()
        return set(rows)


def test_schema_version_is_sixty_and_the_migration_is_registered() -> None:
    assert CURRENT_DATABASE_SCHEMA_VERSION == 60
    assert 60 in _SCHEMA_MIGRATIONS
    # Every earlier version must still be able to reach the current one.
    assert database_schema_version_is_compatible(1)
    assert database_schema_version_is_compatible(59)


def test_a_fresh_install_has_every_index(tmp_path) -> None:
    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'fresh.sqlite3'}")
    try:
        assert repository.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        missing = EXPECTED_INDEX_NAMES - _index_names(repository)
        assert not missing, f"fresh install is missing {sorted(missing)}"
    finally:
        repository.close()


def test_an_upgraded_install_ends_up_identical_to_a_fresh_one(tmp_path) -> None:
    """A schema-59 database must migrate to exactly the same index set."""

    upgraded_path = tmp_path / "upgraded.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{upgraded_path}")
    try:
        # Rewind to 59 and drop the indexes this migration is responsible
        # for, so the reopen below performs the real migration rather than
        # finding its work already done.
        with repository.engine.begin() as connection:
            for name in EXPECTED_INDEX_NAMES:
                connection.exec_driver_sql(f"DROP INDEX IF EXISTS {name}")
            connection.exec_driver_sql(
                "UPDATE mockingbird_schema SET version = 59 WHERE singleton_id = 1"
            )
    finally:
        repository.close()

    reopened = ProductRepository(db_url=f"sqlite:///{upgraded_path}")
    fresh = ProductRepository(db_url=f"sqlite:///{tmp_path / 'compare.sqlite3'}")
    try:
        assert reopened.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        assert EXPECTED_INDEX_NAMES <= _index_names(reopened)
        # Not merely "has the new ones" -- the whole index set must match.
        assert _index_names(reopened) == _index_names(fresh)
    finally:
        reopened.close()
        fresh.close()


def test_the_migration_is_a_no_op_when_the_indexes_already_exist(tmp_path) -> None:
    """Re-running it must not error -- a fresh 60 database already has them."""

    path = tmp_path / "rerun.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{path}")
    try:
        before = _index_names(repository)
        with repository.engine.begin() as connection:
            _SCHEMA_MIGRATIONS[60](connection)
            _SCHEMA_MIGRATIONS[60](connection)
        assert _index_names(repository) == before
    finally:
        repository.close()


def test_sqlite_actually_uses_each_index(tmp_path) -> None:
    """Every index must be chosen by the query shape it was added for."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'plans.sqlite3'}")
    queries = {
        "ix_review_labels_target": (
            "SELECT * FROM review_labels WHERE target_type = 'visit' AND target_id = 'v1'"
        ),
        "ix_visits_event": "SELECT * FROM visits WHERE event_id = 'e1'",
        "ix_visits_review_status": (
            "SELECT * FROM visits WHERE review_status = 'needs_review' AND is_superseded = 0"
        ),
        "ix_events_stream_started": (
            "SELECT * FROM events WHERE stream_id = 's1' AND started_at > '2026-01-01'"
        ),
        "ix_events_review_status": "SELECT * FROM events WHERE review_status = 'needs_review'",
        "ix_detections_event": "SELECT * FROM detections WHERE event_id = 'e1'",
        "ix_species_suggestions_visit_status": (
            "SELECT * FROM species_suggestions WHERE visit_id = 'v1' AND status = 'pending'"
        ),
        "ix_motion_evidence_visit": (
            "SELECT * FROM motion_evidence WHERE promoted_visit_id = 'v1'"
        ),
        "ix_motion_evidence_event": (
            "SELECT * FROM motion_evidence WHERE promoted_event_id = 'e1'"
        ),
        "ix_media_assets_local_path": "SELECT * FROM media_assets WHERE local_path = 'a/b.jpg'",
        "ix_media_assets_stream": "SELECT * FROM media_assets WHERE stream_id = 's1'",
        "ix_detection_proposals_run": "SELECT * FROM detection_proposals WHERE run_id = 'r1'",
        "ix_detection_proposals_visit": "SELECT * FROM detection_proposals WHERE visit_id = 'v1'",
        "ix_detection_runs_media": "SELECT * FROM detection_runs WHERE media_asset_id = 'm1'",
    }
    assert set(queries) == EXPECTED_INDEX_NAMES, "index set and plan coverage drifted apart"
    try:
        with repository.engine.connect() as connection:
            for index_name, query in queries.items():
                plan = " ".join(
                    str(row[-1])
                    for row in connection.exec_driver_sql("EXPLAIN QUERY PLAN " + query)
                )
                assert index_name in plan, f"{index_name} unused; plan was: {plan}"
    finally:
        repository.close()


def test_indexes_do_not_change_what_queries_return(tmp_path) -> None:
    """An index changes the plan, never a row -- prove it on real data."""

    from datetime import UTC, datetime

    from mockingbird.api.schemas import ReviewStatus
    from mockingbird.storage.models import EventModel, StreamModel, VisitModel, CameraSourceModel

    path = tmp_path / "rows.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{path}")
    now = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)
    try:
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    CameraSourceModel(
                        id="src-ix", name="Index", kind="integration",
                        status="connected", description="Index fixture.",
                    )
                )
                session.add(
                    StreamModel(
                        id="stream-ix", source_id="src-ix", name="Index",
                        description="Index fixture.", is_live=True,
                    )
                )
                for index in range(30):
                    session.add(
                        EventModel(
                            id=f"e-{index}", stream_id="stream-ix", title=f"E{index}",
                            event_type="wildlife_visit", started_at=now, ended_at=now,
                            primary_zone_id=None,
                            review_status=ReviewStatus.needs_review.value,
                        )
                    )
                    session.add(
                        VisitModel(
                            id=f"v-{index}", event_id=f"e-{index}", subject_label="bird",
                            species_guess=None, confidence=None, reviewed_label=None,
                            review_status=ReviewStatus.needs_review.value,
                            representative_media_path=None, zone_id=None, is_superseded=False,
                        )
                    )
        with_indexes = [visit.id for visit in repository.list_visits()]

        with repository.engine.begin() as connection:
            for name in EXPECTED_INDEX_NAMES:
                connection.exec_driver_sql(f"DROP INDEX IF EXISTS {name}")
        without_indexes = [visit.id for visit in repository.list_visits()]

        assert with_indexes == without_indexes
        assert len(with_indexes) >= 30
    finally:
        repository.close()
