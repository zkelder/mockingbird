"""Habitat & Phenology Foundation v1 (see docs/habitat-phenology-
foundation-v1-contract.md).

Covers: the pure temporal-status logic (`mockingbird.habitat.phenology`
-- interval containment, current/recent/past classification, and the
exact "no end date means a single-date observation, never 'ongoing
indefinitely'" boundary that keeps an April observation from silently
reading as current in August); the durable Place habitat-fact repository
surface (add/list/update/remove, note-clearing, absence-safety, Place-wide
scoping); the dated phenology-observation repository surface (same shape,
plus the interval-validity guard and the explicit `clear_observed_end_date`
convention); the compact current/recent "habitat context" bundle; a direct
proof this domain never touches wildlife review truth; the real HTTP
surface (auth-required mutations, 404s, 422s); and backup/restore/restart
survival.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from mockingbird.api.main import app, configure_repository, get_repository
from mockingbird.api.schemas import (
    CurrentUser,
    PlaceHabitatFactCreate,
    PlaceHabitatFactUpdate,
    PlacePhenologyObservationCreate,
    PlacePhenologyObservationUpdate,
    UserRole,
)
from mockingbird.habitat.phenology import (
    DEFAULT_RECENT_WINDOW_DAYS,
    classify_phenology_status,
    phenology_interval_covers,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import EventModel, PlaceHabitatFactModel, VisitModel
from tests.conftest import LegacyAuthenticatedSyncTestClient

STREAM_ID = "stream-backyard-feeder"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin",
        display_name="Test Admin",
        login_identity="test-admin",
        role=UserRole.administrator,
        enabled=True,
    )


def _add_visit(repository: ProductRepository, *, visit_id: str, at: datetime) -> None:
    """Mirrors `tests/test_environmental_context.py`'s identical fixture
    helper -- a minimal Visit/Event pair, deterministic, no evidence."""

    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Habitat/phenology fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=at,
                    ended_at=at + timedelta(seconds=20),
                    primary_zone_id=None,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id=None,
                    is_superseded=False,
                )
            )


# --- Pure temporal-status logic ------------------------------------------------


def test_phenology_interval_covers_single_date_observation_only_covers_that_day() -> None:
    start = date(2026, 4, 10)
    assert phenology_interval_covers(start, None, date(2026, 4, 10)) is True
    assert phenology_interval_covers(start, None, date(2026, 4, 11)) is False
    assert phenology_interval_covers(start, None, date(2026, 4, 9)) is False


def test_phenology_interval_covers_real_interval() -> None:
    start, end = date(2026, 4, 1), date(2026, 4, 20)
    assert phenology_interval_covers(start, end, date(2026, 4, 1)) is True
    assert phenology_interval_covers(start, end, date(2026, 4, 20)) is True
    assert phenology_interval_covers(start, end, date(2026, 4, 10)) is True
    assert phenology_interval_covers(start, end, date(2026, 3, 31)) is False
    assert phenology_interval_covers(start, end, date(2026, 4, 21)) is False


def test_classify_phenology_status_current_when_today_is_within_interval() -> None:
    result = classify_phenology_status(
        date(2026, 8, 20), date(2026, 8, 30), today=date(2026, 8, 24)
    )
    assert result.status == "current"


def test_classify_phenology_status_april_observation_is_not_current_in_august() -> None:
    """The exact motivating scenario named in the governing brief: 'do not
    pretend an observation from April is still current in August unless
    its interval explicitly covers August.' A single-date April entry with
    no end date must not silently still read as current months later."""

    result = classify_phenology_status(date(2026, 4, 10), None, today=date(2026, 8, 24))
    assert result.status == "past"


def test_classify_phenology_status_april_observation_with_explicit_august_interval_is_current() -> None:
    result = classify_phenology_status(
        date(2026, 4, 10), date(2026, 9, 1), today=date(2026, 8, 24)
    )
    assert result.status == "current"


def test_classify_phenology_status_recently_concluded_within_window_is_recent() -> None:
    today = date(2026, 8, 24)
    concluded = today - timedelta(days=DEFAULT_RECENT_WINDOW_DAYS - 1)
    result = classify_phenology_status(concluded - timedelta(days=5), concluded, today=today)
    assert result.status == "recent"


def test_classify_phenology_status_concluded_beyond_window_is_past() -> None:
    today = date(2026, 8, 24)
    concluded = today - timedelta(days=DEFAULT_RECENT_WINDOW_DAYS + 1)
    result = classify_phenology_status(concluded - timedelta(days=5), concluded, today=today)
    assert result.status == "past"


def test_classify_phenology_status_exact_recent_window_boundary_is_recent() -> None:
    today = date(2026, 8, 24)
    concluded = today - timedelta(days=DEFAULT_RECENT_WINDOW_DAYS)
    result = classify_phenology_status(concluded, concluded, today=today)
    assert result.status == "recent"


def test_classify_phenology_status_future_dated_interval_is_past_not_current() -> None:
    result = classify_phenology_status(
        date(2026, 9, 1), date(2026, 9, 10), today=date(2026, 8, 24)
    )
    assert result.status == "past"


def test_classify_phenology_status_rejects_negative_recent_window() -> None:
    with pytest.raises(ValueError):
        classify_phenology_status(
            date(2026, 8, 1), None, today=date(2026, 8, 24), recent_window_days=-1
        )


# --- Habitat fact repository surface -------------------------------------------


def test_add_and_list_habitat_facts(repository: ProductRepository) -> None:
    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="feature", label="Bird feeders", note="Sunflower seed"),
        acting_user=_acting_user(),
    )
    facts = repository.list_place_habitat_facts()
    assert {f.label for f in facts} == {"Woodland edge", "Bird feeders"}
    feeders = next(f for f in facts if f.label == "Bird feeders")
    assert feeders.note == "Sunflower seed"
    assert feeders.information_class == "reviewed"
    assert feeders.provenance == "user_manual_entry"


def test_habitat_facts_absence_is_an_empty_list_never_a_fabricated_claim(
    repository: ProductRepository,
) -> None:
    """The governing brief's own invariant: 'absence of a fact must not
    imply false.' There is no 'confirmed absent' row -- just nothing."""

    assert repository.list_place_habitat_facts() == []


def test_update_habitat_fact_note_and_clear_it(repository: ProductRepository) -> None:
    fact = repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="vegetation", label="Conifers"), acting_user=_acting_user()
    )
    updated = repository.update_place_habitat_fact(
        fact.id, PlaceHabitatFactUpdate(note="Two large spruces"), acting_user=_acting_user()
    )
    assert updated is not None
    assert updated.note == "Two large spruces"
    assert updated.updated_at >= fact.updated_at

    cleared = repository.update_place_habitat_fact(
        fact.id, PlaceHabitatFactUpdate(note=""), acting_user=_acting_user()
    )
    assert cleared is not None
    assert cleared.note is None


def test_update_habitat_fact_omitted_fields_leave_them_unchanged(
    repository: ProductRepository,
) -> None:
    fact = repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Suburban yard", note="Front and back"),
        acting_user=_acting_user(),
    )
    updated = repository.update_place_habitat_fact(
        fact.id, PlaceHabitatFactUpdate(category="feature"), acting_user=_acting_user()
    )
    assert updated is not None
    assert updated.category == "feature"
    assert updated.label == "Suburban yard"  # unchanged
    assert updated.note == "Front and back"  # unchanged


def test_update_missing_habitat_fact_returns_none(repository: ProductRepository) -> None:
    assert (
        repository.update_place_habitat_fact(
            "does-not-exist", PlaceHabitatFactUpdate(label="x"), acting_user=_acting_user()
        )
        is None
    )


def test_remove_habitat_fact(repository: ProductRepository) -> None:
    fact = repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="feature", label="Nest boxes"), acting_user=_acting_user()
    )
    assert repository.remove_place_habitat_fact(fact.id, acting_user=_acting_user()) is True
    assert repository.list_place_habitat_facts() == []
    assert repository.remove_place_habitat_fact(fact.id, acting_user=_acting_user()) is False


def test_add_habitat_fact_records_audit_event(repository: ProductRepository) -> None:
    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    events = repository.list_audit_log(limit=10)
    assert any(event.action == "place_habitat.fact_added" for event in events)


def test_habitat_facts_are_place_wide_only_in_v1(repository: ProductRepository) -> None:
    """Confirms the documented v1 invariant directly against the schema:
    every row this milestone ever writes has `source_id IS NULL`."""

    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    with repository.session_factory() as session:
        rows = session.scalars(select(PlaceHabitatFactModel)).all()
        assert len(rows) == 1
        assert rows[0].source_id is None


# --- Phenology observation repository surface -----------------------------------


def test_add_and_list_phenology_observations_newest_first(repository: ProductRepository) -> None:
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Redbud", phenomenon="flowering", observed_start_date=date(2026, 4, 1)
        ),
        acting_user=_acting_user(),
    )
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea", phenomenon="flowering", observed_start_date=date(2026, 5, 1)
        ),
        acting_user=_acting_user(),
    )
    observations = repository.list_place_phenology_observations()
    assert [o.subject_label for o in observations] == ["Azalea", "Redbud"]


def test_phenology_observations_absence_is_an_empty_list(repository: ProductRepository) -> None:
    assert repository.list_place_phenology_observations() == []


def test_create_phenology_observation_rejects_end_before_start(
    repository: ProductRepository,
) -> None:
    with pytest.raises(ValueError):
        repository.add_place_phenology_observation(
            PlacePhenologyObservationCreate(
                subject_label="Azalea",
                phenomenon="flowering",
                observed_start_date=date(2026, 8, 20),
                observed_end_date=date(2026, 8, 1),
            ),
            acting_user=_acting_user(),
        )


def test_update_phenology_observation_extends_end_date(repository: ProductRepository) -> None:
    today = datetime.now(UTC).date()
    observation = repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Sunflower feeder",
            phenomenon="feeder/resource availability",
            observed_start_date=today - timedelta(days=10),
        ),
        acting_user=_acting_user(),
    )
    assert observation.status == "recent"  # single-date, 10 days ago

    updated = repository.update_place_phenology_observation(
        observation.id,
        PlacePhenologyObservationUpdate(observed_end_date=today),
        acting_user=_acting_user(),
    )
    assert updated is not None
    assert updated.status == "current"


def test_update_phenology_observation_clear_end_date_returns_to_single_date(
    repository: ProductRepository,
) -> None:
    today = datetime.now(UTC).date()
    observation = repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea",
            phenomenon="flowering",
            observed_start_date=today - timedelta(days=2),
            observed_end_date=today + timedelta(days=2),
        ),
        acting_user=_acting_user(),
    )
    updated = repository.update_place_phenology_observation(
        observation.id,
        PlacePhenologyObservationUpdate(clear_observed_end_date=True),
        acting_user=_acting_user(),
    )
    assert updated is not None
    assert updated.observed_end_date is None


def test_update_phenology_observation_rejects_resulting_end_before_start(
    repository: ProductRepository,
) -> None:
    observation = repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea",
            phenomenon="flowering",
            observed_start_date=date(2026, 8, 1),
            observed_end_date=date(2026, 8, 20),
        ),
        acting_user=_acting_user(),
    )
    with pytest.raises(ValueError):
        repository.update_place_phenology_observation(
            observation.id,
            PlacePhenologyObservationUpdate(observed_start_date=date(2026, 8, 25)),
            acting_user=_acting_user(),
        )


def test_update_missing_phenology_observation_returns_none(repository: ProductRepository) -> None:
    assert (
        repository.update_place_phenology_observation(
            "does-not-exist", PlacePhenologyObservationUpdate(note="x"), acting_user=_acting_user()
        )
        is None
    )


def test_remove_phenology_observation(repository: ProductRepository) -> None:
    observation = repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea", phenomenon="flowering", observed_start_date=date(2026, 8, 1)
        ),
        acting_user=_acting_user(),
    )
    assert (
        repository.remove_place_phenology_observation(observation.id, acting_user=_acting_user())
        is True
    )
    assert repository.list_place_phenology_observations() == []
    assert (
        repository.remove_place_phenology_observation(observation.id, acting_user=_acting_user())
        is False
    )


# --- Compact current/recent context bundle --------------------------------------


def test_get_place_habitat_context_bundles_current_and_recent_only(
    repository: ProductRepository,
) -> None:
    today = datetime.now(UTC).date()
    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea",
            phenomenon="flowering",
            observed_start_date=today - timedelta(days=1),
            observed_end_date=today + timedelta(days=5),
        ),
        acting_user=_acting_user(),
    )
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Redbud", phenomenon="flowering", observed_start_date=today - timedelta(days=8)
        ),
        acting_user=_acting_user(),
    )
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Old Bloom",
            phenomenon="flowering",
            observed_start_date=today - timedelta(days=200),
        ),
        acting_user=_acting_user(),
    )

    context = repository.get_place_habitat_context()
    assert [f.label for f in context.habitat_facts] == ["Woodland edge"]
    assert [o.subject_label for o in context.current_phenology] == ["Azalea"]
    assert [o.subject_label for o in context.recent_phenology] == ["Redbud"]
    # "Old Bloom" (200 days ago) must never appear in either -- proves
    # historical entries stay historical rather than leaking into a
    # "current/recent" surface indefinitely.
    all_ids = {o.subject_label for o in context.current_phenology + context.recent_phenology}
    assert "Old Bloom" not in all_ids


def test_get_place_habitat_context_empty_is_a_calm_sparse_state(
    repository: ProductRepository,
) -> None:
    context = repository.get_place_habitat_context()
    assert context.habitat_facts == []
    assert context.current_phenology == []
    assert context.recent_phenology == []


# --- Truth-boundary and persistence proofs --------------------------------------


def test_habitat_phenology_never_touches_review_truth(repository: ProductRepository) -> None:
    """Direct proof of the governing brief's own doctrine: habitat/phenology
    context must never silently become reviewed wildlife truth."""

    _add_visit(repository, visit_id="truth-visit", at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC))
    before = repository.get_visit("truth-visit")
    assert before is not None

    repository.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="setting", label="Woodland edge"), acting_user=_acting_user()
    )
    repository.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea", phenomenon="flowering", observed_start_date=date(2026, 6, 21)
        ),
        acting_user=_acting_user(),
    )

    after = repository.get_visit("truth-visit")
    assert after is not None
    assert before.review_status == after.review_status
    assert after.reviewed_label is None


def test_habitat_facts_survive_repository_restart(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}"
    first = ProductRepository(db_url=db_url, media_root=tmp_path / "media")
    configure_repository(first)
    first.add_place_habitat_fact(
        PlaceHabitatFactCreate(category="feature", label="Water feature"), acting_user=_acting_user()
    )
    first.add_place_phenology_observation(
        PlacePhenologyObservationCreate(
            subject_label="Azalea", phenomenon="flowering", observed_start_date=date(2026, 8, 1)
        ),
        acting_user=_acting_user(),
    )
    first.close()
    configure_repository(None)

    reopened = ProductRepository(db_url=db_url, media_root=tmp_path / "media")
    try:
        facts = reopened.list_place_habitat_facts()
        observations = reopened.list_place_phenology_observations()
        assert [f.label for f in facts] == ["Water feature"]
        assert [o.subject_label for o in observations] == ["Azalea"]
    finally:
        reopened.close()


# --- HTTP surface ----------------------------------------------------------------


def test_habitat_fact_mutations_require_authentication(repository: ProductRepository) -> None:
    plain_client = TestClient(app)
    response = plain_client.post(
        "/api/place/habitat", json={"category": "setting", "label": "Woodland edge"}
    )
    assert response.status_code == 401


def test_habitat_fact_crud_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)

    created = client.post(
        "/api/place/habitat", json={"category": "vegetation", "label": "Conifers"}
    )
    assert created.status_code == 201, created.text
    fact_id = created.json()["id"]

    listed = client.get("/api/place/habitat")
    assert listed.status_code == 200
    assert [f["label"] for f in listed.json()] == ["Conifers"]

    updated = client.patch(f"/api/place/habitat/{fact_id}", json={"note": "Two large spruces"})
    assert updated.status_code == 200
    assert updated.json()["note"] == "Two large spruces"

    deleted = client.delete(f"/api/place/habitat/{fact_id}")
    assert deleted.status_code == 204
    assert client.get("/api/place/habitat").json() == []


def test_habitat_fact_invalid_category_is_422_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.post("/api/place/habitat", json={"category": "not-a-category", "label": "x"})
    assert response.status_code == 422


def test_update_missing_habitat_fact_is_404_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.patch("/api/place/habitat/does-not-exist", json={"note": "x"})
    assert response.status_code == 404


def test_delete_missing_habitat_fact_is_404_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.delete("/api/place/habitat/does-not-exist")
    assert response.status_code == 404


def test_phenology_observation_crud_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)

    created = client.post(
        "/api/place/phenology",
        json={
            "subject_label": "Azalea",
            "phenomenon": "flowering",
            "observed_start_date": "2026-08-20",
            "observed_end_date": "2026-08-30",
        },
    )
    assert created.status_code == 201, created.text
    observation_id = created.json()["id"]
    assert created.json()["status"] in ("current", "recent", "past")

    listed = client.get("/api/place/phenology")
    assert listed.status_code == 200
    assert [o["subject_label"] for o in listed.json()] == ["Azalea"]

    updated = client.patch(
        f"/api/place/phenology/{observation_id}", json={"note": "Heavy bloom this year"}
    )
    assert updated.status_code == 200
    assert updated.json()["note"] == "Heavy bloom this year"

    deleted = client.delete(f"/api/place/phenology/{observation_id}")
    assert deleted.status_code == 204
    assert client.get("/api/place/phenology").json() == []


def test_phenology_observation_invalid_interval_is_422_over_http(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.post(
        "/api/place/phenology",
        json={
            "subject_label": "Azalea",
            "phenomenon": "flowering",
            "observed_start_date": "2026-08-20",
            "observed_end_date": "2026-08-01",
        },
    )
    assert response.status_code == 422


def test_phenology_observation_conflicting_end_date_update_is_422_over_http(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    created = client.post(
        "/api/place/phenology",
        json={
            "subject_label": "Azalea",
            "phenomenon": "flowering",
            "observed_start_date": "2026-08-20",
        },
    )
    observation_id = created.json()["id"]
    response = client.patch(
        f"/api/place/phenology/{observation_id}",
        json={"observed_end_date": "2026-08-25", "clear_observed_end_date": True},
    )
    assert response.status_code == 422


def test_get_place_habitat_context_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    client.post("/api/place/habitat", json={"category": "setting", "label": "Woodland edge"})
    today = datetime.now(UTC).date().isoformat()
    client.post(
        "/api/place/phenology",
        json={"subject_label": "Azalea", "phenomenon": "flowering", "observed_start_date": today},
    )

    response = client.get("/api/place/habitat-context")
    assert response.status_code == 200
    body = response.json()
    assert [f["label"] for f in body["habitat_facts"]] == ["Woodland edge"]
    assert [o["subject_label"] for o in body["current_phenology"]] == ["Azalea"]
    assert body["recent_phenology"] == []


def test_habitat_context_reads_also_require_authentication(
    repository: ProductRepository,
) -> None:
    """Unlike `/api/settings/installation` (a narrow, documented exception
    letting a signed-out sign-in screen show an installation name -- see
    `mockingbird.api.auth._ALWAYS_PUBLIC_PATHS`), habitat/phenology data has
    no such pre-login requirement and is not on that allowlist: every route
    in this domain, reads included, requires a signed-in session, matching
    the rest of this product's ordinary data."""

    plain_client = TestClient(app)
    response = plain_client.get("/api/place/habitat-context")
    assert response.status_code == 401
    assert TestClient(app).get("/api/place/habitat").status_code == 401
    assert TestClient(app).get("/api/place/phenology").status_code == 401


def test_backup_restore_preserves_habitat_and_phenology(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    client.post("/api/place/habitat", json={"category": "feature", "label": "Water feature"})
    client.post(
        "/api/place/phenology",
        json={"subject_label": "Azalea", "phenomenon": "flowering", "observed_start_date": "2026-08-01"},
    )

    backup_response = client.post("/api/settings/backups")
    assert backup_response.status_code == 201, backup_response.text
    backup_id = backup_response.json()["backup"]["id"]

    restore_response = client.post(
        f"/api/settings/backups/{backup_id}/restore", json={"confirm": True}
    )
    assert restore_response.status_code == 200, restore_response.text

    restored_repository = get_repository()
    facts = restored_repository.list_place_habitat_facts()
    observations = restored_repository.list_place_phenology_observations()
    assert [f.label for f in facts] == ["Water feature"]
    assert [o.subject_label for o in observations] == ["Azalea"]
