"""Environmental Context Foundation v1 (see docs/environmental-context-
foundation-v1-contract.md).

Covers: the local solar/daylight provider (sunrise/sunset/day-night,
longitude-aware calendar-date resolution -- including a regression test for
a real `astral` date-labeling bug found and worked around during
implementation -- coarse-rounding accuracy, and polar-night handling); the
environmental-context settings singleton (coarse rounding, clearing, audit
trail, both-or-neither validation); the provider-neutral observation table
(bounded provenance, idempotent daily caching); Visit/Place association
(the canonical `activity_started_at` field, near-midnight correctness,
absence-safe throughout, and direct proof that environmental-context reads
never mutate reviewed wildlife truth); the real HTTP surface; and
backup/restore survival.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from starlette.testclient import TestClient

from mockingbird.api.main import app, configure_repository, get_repository
from mockingbird.api.schemas import CurrentUser, EnvironmentalContextSettingsUpdate, UserRole
from mockingbird.environment.solar_context import (
    SolarContextUnavailableError,
    approximate_local_date,
    classify_daylight_state,
    compute_daily_solar_facts,
    get_solar_context_status,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    EnvironmentalContextRecordModel,
    EnvironmentalContextSettingsModel,
    EventModel,
    VisitModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient

NYC_LATITUDE = 40.7
NYC_LONGITUDE = -74.0
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


def _add_visit(
    repository: ProductRepository, *, visit_id: str, at: datetime, stream_id: str = STREAM_ID
) -> None:
    """A minimal Visit/Event pair with no evidence frames or motion
    evidence, so `_stream_visit_summary_from_models` falls back to
    `event.started_at` as `activity_started_at` -- a deterministic,
    controlled instant for these tests, mirroring
    `tests/test_historical_baseline_repository.py`'s own `_add_visit`
    fixture helper."""

    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Environmental context fixture {visit_id}",
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


# --- Solar provider: pure function tests ------------------------------------


def test_get_solar_context_status_reflects_configuration() -> None:
    assert get_solar_context_status(None, None).status == "not_configured"
    assert get_solar_context_status(None, -74.0).status == "not_configured"
    assert get_solar_context_status(40.7, -74.0).status == "available"


def test_compute_daily_solar_facts_orders_sunset_after_sunrise_across_hemispheres() -> None:
    for latitude, longitude in ((40.7, -74.0), (35.68, 139.7), (-33.9, 151.2), (51.5, -0.1)):
        facts = compute_daily_solar_facts(latitude, longitude, date(2026, 3, 20))
        assert facts.sunset_at > facts.sunrise_at


def test_compute_daily_solar_facts_matches_known_reference_for_nyc() -> None:
    # Real-world reference: NYC summer solstice sunrise/sunset are
    # approximately 05:25/20:30 EDT (UTC-4). Tolerance is generous (a few
    # minutes) since this checks "roughly right against an independent
    # real-world reference," not bit-exactness against a second computation.
    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    local_sunrise = facts.sunrise_at - timedelta(hours=4)
    local_sunset = facts.sunset_at - timedelta(hours=4)
    assert abs((local_sunrise - datetime(2026, 6, 21, 5, 25, tzinfo=UTC)).total_seconds()) < 300
    assert abs((local_sunset - datetime(2026, 6, 21, 20, 30, tzinfo=UTC)).total_seconds()) < 300


def test_compute_daily_solar_facts_date_boundary_is_longitude_aware_not_utc_naive() -> None:
    """Regression test for a real bug found during implementation:
    `astral.sun.sun` mislabels an event's calendar date by a full day when
    given `tzinfo=UTC` for a longitude far from Greenwich (confirmed
    directly: NYC's `date=2026-06-21` sunset came back dated `2026-06-21
    00:30 UTC`, a full day before the correct `2026-06-22 00:30 UTC`, cross-
    checked against the real `America/New_York` zone). `compute_daily_
    solar_facts` anchors to an approximate local offset instead of raw UTC
    specifically to avoid this."""

    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    assert facts.sunrise_at.date() == date(2026, 6, 21)
    assert facts.sunset_at.date() == date(2026, 6, 22)  # correctly crosses UTC midnight


def test_compute_daily_solar_facts_raises_typed_error_for_polar_night() -> None:
    with pytest.raises(SolarContextUnavailableError):
        compute_daily_solar_facts(78.0, 15.0, date(2026, 12, 21))


def test_coarse_rounding_changes_sunrise_by_well_under_a_minute() -> None:
    """Numeric justification for the ~11 km rounding decision in
    docs/environmental-context-foundation-v1-contract.md "Place
    coordinates...": the resulting sunrise error must stay far below the
    nearest-minute precision this feature ever presents."""

    precise = compute_daily_solar_facts(40.7128, -74.0060, date(2026, 3, 20))
    coarse = compute_daily_solar_facts(round(40.7128, 1), round(-74.0060, 1), date(2026, 3, 20))
    assert abs((precise.sunrise_at - coarse.sunrise_at).total_seconds()) < 60


def test_classify_daylight_state_day_and_night() -> None:
    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    noon = facts.sunrise_at + (facts.sunset_at - facts.sunrise_at) / 2
    well_before_dawn = facts.sunrise_at - timedelta(hours=2)
    assert classify_daylight_state(noon, facts.sunrise_at, facts.sunset_at) == "day"
    assert classify_daylight_state(well_before_dawn, facts.sunrise_at, facts.sunset_at) == "night"


def test_classify_daylight_state_rejects_naive_datetime() -> None:
    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    with pytest.raises(ValueError):
        classify_daylight_state(datetime(2026, 6, 21, 12, 0), facts.sunrise_at, facts.sunset_at)


def test_approximate_local_date_resolves_near_midnight_correctly() -> None:
    two_am_local = datetime(2026, 6, 21, 6, 0, tzinfo=UTC)  # ~2am EDT, still "last night" locally
    assert approximate_local_date(two_am_local, NYC_LONGITUDE) == date(2026, 6, 21)
    eleven_pm_local = datetime(2026, 6, 22, 3, 0, tzinfo=UTC)  # ~11pm EDT, already "tomorrow" in UTC
    assert approximate_local_date(eleven_pm_local, NYC_LONGITUDE) == date(2026, 6, 21)


# --- Repository: settings ----------------------------------------------------


def test_environmental_context_settings_default_absent(repository: ProductRepository) -> None:
    settings = repository.get_environmental_context_settings()
    assert settings.configured is False
    assert settings.coarse_latitude is None
    assert settings.coarse_longitude is None


def test_update_environmental_context_settings_rounds_to_coarse_precision(
    repository: ProductRepository,
) -> None:
    updated = repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7128, longitude=-74.0060),
        acting_user=_acting_user(),
    )
    assert updated.coarse_latitude == 40.7
    assert updated.coarse_longitude == -74.0
    assert updated.configured is True

    with repository.session_factory() as session:
        model = session.get(EnvironmentalContextSettingsModel, 1)
        assert model.coarse_latitude == 40.7
        assert model.coarse_longitude == -74.0


def test_update_environmental_context_settings_records_audit_event(
    repository: ProductRepository,
) -> None:
    before = len(repository.list_audit_log(limit=200))
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0),
        acting_user=_acting_user(),
    )
    audit = repository.list_audit_log(limit=200)
    assert len(audit) == before + 1
    assert audit[0].action == "settings.environmental_context_updated"


def test_clearing_environmental_context_settings_returns_to_not_configured(
    repository: ProductRepository,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0),
        acting_user=_acting_user(),
    )
    cleared = repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=None, longitude=None),
        acting_user=_acting_user(),
    )
    assert cleared.configured is False
    assert cleared.coarse_latitude is None
    assert cleared.coarse_longitude is None


def test_partial_coordinate_update_is_rejected() -> None:
    with pytest.raises(ValueError):
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=None)


# --- Repository: daily solar context / caching -------------------------------


def test_place_environmental_context_today_unavailable_without_location(
    repository: ProductRepository,
) -> None:
    today = repository.get_place_environmental_context_today()
    assert today.available is False
    assert today.reason == "not_configured"
    assert today.sunrise_at is None
    assert today.sunset_at is None


def test_place_environmental_context_today_available_once_configured(
    repository: ProductRepository,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0),
        acting_user=_acting_user(),
    )
    today = repository.get_place_environmental_context_today()
    assert today.available is True
    assert today.reason == "computed"
    assert today.sunset_at > today.sunrise_at
    assert today.daylight_state in ("day", "night")
    assert today.information_class == "derived"
    assert today.provider_key == "solar_local"
    assert today.basis_latitude == 40.7
    assert today.basis_longitude == -74.0


def test_daily_solar_context_is_cached_not_recomputed(repository: ProductRepository) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.7, longitude=-74.0),
        acting_user=_acting_user(),
    )
    first = repository.get_place_environmental_context_today()
    second = repository.get_place_environmental_context_today()
    assert first.sunrise_at == second.sunrise_at
    assert first.sunset_at == second.sunset_at

    with repository.session_factory() as session:
        rows = session.scalars(select(EnvironmentalContextRecordModel)).all()
        assert len(rows) == 2  # exactly one sunrise + one sunset row, never duplicated
        assert {row.metric for row in rows} == {"sunrise", "sunset"}
        for row in rows:
            assert row.information_class == "derived"
            assert row.provider_key == "solar_local"
            assert row.source_id is None  # Place-wide, not Source-scoped
            assert row.provenance_schema_version == 1
            assert row.provenance_json is not None
            provenance = json.loads(row.provenance_json)
            assert set(provenance.keys()) == {"algorithm", "algorithm_version"}  # bounded, fixed shape


def test_daily_solar_context_polar_night_is_unavailable_not_a_crash(
    repository: ProductRepository,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=78.0, longitude=15.0),
        acting_user=_acting_user(),
    )
    _add_visit(repository, visit_id="polar-visit", at=datetime(2026, 12, 21, 12, 0, tzinfo=UTC))
    context = repository.get_visit_environmental_context("polar-visit")
    assert context is not None
    assert context.available is False
    assert context.reason == "unavailable_for_date"


# --- Repository: Visit association ------------------------------------------


def test_visit_environmental_context_missing_visit_returns_none(
    repository: ProductRepository,
) -> None:
    assert repository.get_visit_environmental_context("does-not-exist") is None


def test_visit_environmental_context_unavailable_without_location(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="v1", at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC))
    context = repository.get_visit_environmental_context("v1")
    assert context is not None
    assert context.available is False
    assert context.reason == "not_configured"
    assert context.evaluated_at == datetime(2026, 6, 21, 16, 0, tzinfo=UTC)


def test_visit_environmental_context_uses_activity_started_at_and_classifies_correctly(
    repository: ProductRepository,
) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=NYC_LATITUDE, longitude=NYC_LONGITUDE),
        acting_user=_acting_user(),
    )
    # Noon EDT (16:00 UTC) on the summer solstice is unambiguously daytime.
    _add_visit(repository, visit_id="noon-visit", at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC))
    noon_context = repository.get_visit_environmental_context("noon-visit")
    assert noon_context is not None
    assert noon_context.available is True
    assert noon_context.daylight_state == "day"
    assert noon_context.evaluated_at == datetime(2026, 6, 21, 16, 0, tzinfo=UTC)

    # ~2am EDT (06:00 UTC the following day) is unambiguously nighttime, and
    # falls on the UTC-adjacent calendar date from its own local date -- the
    # exact boundary case `approximate_local_date` exists to get right.
    _add_visit(repository, visit_id="night-visit", at=datetime(2026, 6, 22, 6, 0, tzinfo=UTC))
    night_context = repository.get_visit_environmental_context("night-visit")
    assert night_context is not None
    assert night_context.available is True
    assert night_context.daylight_state == "night"


def test_environmental_context_never_touches_review_truth(repository: ProductRepository) -> None:
    """Direct proof of the milestone's own acceptance criterion:
    'environmental data cannot masquerade as reviewed wildlife truth.'"""

    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=NYC_LATITUDE, longitude=NYC_LONGITUDE),
        acting_user=_acting_user(),
    )
    _add_visit(repository, visit_id="truth-visit", at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC))
    before = repository.get_visit("truth-visit")
    assert before is not None
    repository.get_visit_environmental_context("truth-visit")  # writes environmental_context_records
    after = repository.get_visit("truth-visit")
    assert after is not None
    assert before.review_status == after.review_status
    assert after.reviewed_label is None


# --- HTTP surface -------------------------------------------------------------


def test_environmental_context_settings_put_requires_authentication(
    repository: ProductRepository,
) -> None:
    # A fresh repository with no administrator bootstrapped yet -- a plain,
    # cookie-less client must be rejected server-side, mirroring
    # `test_unauthenticated_request_is_rejected_server_side` in
    # tests/test_local_identity_multi_user.py.
    plain_client = TestClient(app)
    response = plain_client.put(
        "/api/settings/environmental-context", json={"latitude": 40.7, "longitude": -74.0}
    )
    assert response.status_code == 401


def test_get_environmental_context_settings_over_http_when_unset(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/settings/environmental-context")
    assert response.status_code == 200
    assert response.json()["configured"] is False


def test_put_environmental_context_settings_over_http_rounds_and_persists(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.put(
        "/api/settings/environmental-context",
        json={"latitude": 40.7128, "longitude": -74.0060},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["coarse_latitude"] == 40.7
    assert body["coarse_longitude"] == -74.0
    assert body["configured"] is True

    again = client.get("/api/settings/environmental-context")
    assert again.json()["coarse_latitude"] == 40.7


def test_put_environmental_context_settings_rejects_partial_coordinate_over_http(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.put("/api/settings/environmental-context", json={"latitude": 40.7})
    assert response.status_code == 422


def test_get_place_environmental_context_today_over_http(repository: ProductRepository) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    client.put("/api/settings/environmental-context", json={"latitude": 40.7, "longitude": -74.0})
    response = client.get("/api/place/environmental-context/today")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["daylight_state"] in ("day", "night")


def test_get_visit_environmental_context_over_http(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="http-visit", at=datetime(2026, 6, 21, 16, 0, tzinfo=UTC))
    client = LegacyAuthenticatedSyncTestClient(app)
    client.put("/api/settings/environmental-context", json={"latitude": 40.7, "longitude": -74.0})
    response = client.get("/api/visits/http-visit/environmental-context")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["daylight_state"] == "day"
    assert body["visit_id"] == "http-visit"


def test_get_visit_environmental_context_missing_visit_is_404(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    response = client.get("/api/visits/does-not-exist/environmental-context")
    assert response.status_code == 404


def test_backup_restore_preserves_environmental_context_settings_and_records(
    repository: ProductRepository,
) -> None:
    client = LegacyAuthenticatedSyncTestClient(app)
    client.put("/api/settings/environmental-context", json={"latitude": 40.7, "longitude": -74.0})
    client.get("/api/place/environmental-context/today")  # populate one cached sunrise/sunset pair

    backup_response = client.post("/api/settings/backups")
    assert backup_response.status_code == 201, backup_response.text
    backup_id = backup_response.json()["backup"]["id"]

    restore_response = client.post(
        f"/api/settings/backups/{backup_id}/restore", json={"confirm": True}
    )
    assert restore_response.status_code == 200, restore_response.text

    # `restore_local_backup` swaps the process-wide repository singleton --
    # re-fetch it to inspect the now-active, restored database directly
    # (same pattern as `test_backup_restore_preserves_users_roles_and_audit_
    # history` in tests/test_local_identity_multi_user.py).
    restored_repository = get_repository()
    restored_settings = restored_repository.get_environmental_context_settings()
    assert restored_settings.configured is True
    assert restored_settings.coarse_latitude == 40.7
    assert restored_settings.coarse_longitude == -74.0
    with restored_repository.session_factory() as session:
        rows = session.scalars(select(EnvironmentalContextRecordModel)).all()
        assert len(rows) == 2
