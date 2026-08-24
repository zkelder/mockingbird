"""Environmental Context Foundation v1 (see docs/environmental-context-
foundation-v1-contract.md), including its "Solar Temporal-Semantics
Acceptance Closure" correction.

Covers: the local solar/daylight provider (sunrise/sunset/day-night
depending only on Place coordinates and a UTC instant -- never on any
timezone concept, real or approximate -- across western and eastern
longitudes, both hemispheres, and both solstice seasons; the bracketing
[sunrise, sunset) window search across UTC-calendar-date boundaries;
coarse-rounding accuracy; and polar-night handling); the
environmental-context settings singleton (coarse rounding, clearing, audit
trail, both-or-neither validation); the provider-neutral observation table
(bounded provenance, idempotent daily caching); Visit/Place association
(the canonical `activity_started_at` field, exact sunrise/sunset boundary
instants, a direct proof that varying the season alone cannot change a
UTC-instant classification, absence-safe throughout, and direct proof that
environmental-context reads never mutate reviewed wildlife truth); the
real HTTP surface; and backup/restore survival.
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
    candidate_dates_for_window,
    classify_daylight_state,
    compute_daily_solar_facts,
    find_daylight_window,
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


def test_compute_daily_solar_facts_matches_known_reference_for_nyc() -> None:
    # Real-world reference: NYC summer solstice sunrise/sunset are
    # approximately 05:25/20:30 EDT (UTC-4). Tolerance is generous (a few
    # minutes) since this checks "roughly right against an independent
    # real-world reference," not bit-exactness against a second computation.
    #
    # `facts.sunset_at` here is the *raw single-date* sunset -- the one
    # that falls within UTC calendar day 2026-06-21 itself, which for this
    # longitude is the tail of the *previous* local evening (2026-06-20
    # 20:30 EDT), not "today's" 2026-06-21 20:30 EDT sunset a naive reader
    # might expect (that one carries UTC date 2026-06-22; see
    # `test_compute_daily_solar_facts_for_date_is_the_utc_calendar_date_
    # not_a_civil_date`, above). This is exactly why Visit/Place context
    # never uses one date's raw pair directly -- see `find_daylight_
    # window`, exercised separately below.
    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    local_sunrise = facts.sunrise_at - timedelta(hours=4)
    local_sunset = facts.sunset_at - timedelta(hours=4)
    assert abs((local_sunrise - datetime(2026, 6, 21, 5, 25, tzinfo=UTC)).total_seconds()) < 300
    assert abs((local_sunset - datetime(2026, 6, 20, 20, 30, tzinfo=UTC)).total_seconds()) < 300

    # The Visit-relevant sunset (via the bracket search) is the real,
    # intuitively-expected one: 2026-06-21 20:30 EDT.
    afternoon = datetime(2026, 6, 21, 20, 0, tzinfo=UTC)
    _, real_sunset_at = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, afternoon)
    assert abs((real_sunset_at - timedelta(hours=4) - datetime(2026, 6, 21, 20, 30, tzinfo=UTC)).total_seconds()) < 300


def test_compute_daily_solar_facts_for_date_is_the_utc_calendar_date_not_a_civil_date() -> None:
    """`compute_daily_solar_facts(..., for_date=D)` means exactly "the
    sunrise/sunset that fall within UTC calendar day D" -- confirmed here
    directly rather than assumed. For a longitude west of Greenwich (NYC),
    that UTC-day sunset genuinely carries the *same* UTC date as the
    sunrise, at an earlier time-of-day -- this is not a bug, and not a
    mislabeling; it is what "the sunset associated with UTC day D" means
    for this longitude (the sunset instant that happens to fall inside D's
    own 00:00-24:00 UTC window is the tail of the previous local evening).

    This directly replaces this suite's earlier ("Environmental Context
    Foundation v1", before this closure) claim that `astral` "mislabels" a
    date here -- that claim was based solely on calling astral with
    `tzinfo=UTC` and expecting a *civil*-calendar-date answer; astral's own
    contract is that `date` is interpreted in whatever `tzinfo` is given,
    so a UTC answer to a UTC question is correct by construction, not a
    defect. See docs/environmental-context-foundation-v1-contract.md
    "Solar temporal semantics" for the full record.
    """

    facts = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    assert facts.for_date == date(2026, 6, 21)
    assert facts.sunrise_at.date() == date(2026, 6, 21)
    assert facts.sunset_at.date() == date(2026, 6, 21)  # same UTC date as for_date, by construction
    assert facts.sunset_at < facts.sunrise_at  # earlier time-of-day; see docstring above


def test_compute_daily_solar_facts_ordering_within_one_date_depends_on_longitude() -> None:
    """Whether `sunset_at` falls before or after `sunrise_at` *within the
    same `for_date`* depends only on how far local solar noon is offset
    from UTC noon by longitude -- not on hemisphere, not on season. A
    longitude far enough from Greenwich in *either* direction can put
    local noon early or late in the UTC day, inverting the naive
    same-date ordering; near Greenwich, it holds normally. None of this
    is a defect: see `find_daylight_window`, which never relies on one
    date's own pair being self-ordered."""

    close_to_greenwich = compute_daily_solar_facts(51.5, -0.1, date(2026, 3, 20))  # London
    assert close_to_greenwich.sunset_at > close_to_greenwich.sunrise_at

    far_east = compute_daily_solar_facts(35.68, 139.7, date(2026, 3, 20))  # Tokyo
    assert far_east.sunset_at < far_east.sunrise_at

    far_west = compute_daily_solar_facts(40.7, -74.0, date(2026, 6, 21))  # NYC, solstice
    assert far_west.sunset_at < far_west.sunrise_at


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
    sunrise_at = datetime(2026, 6, 21, 9, 25, tzinfo=UTC)
    sunset_at = datetime(2026, 6, 22, 0, 30, tzinfo=UTC)
    noon = sunrise_at + (sunset_at - sunrise_at) / 2
    well_before_dawn = sunrise_at - timedelta(hours=2)
    assert classify_daylight_state(noon, sunrise_at, sunset_at) == "day"
    assert classify_daylight_state(well_before_dawn, sunrise_at, sunset_at) == "night"


def test_classify_daylight_state_rejects_naive_datetime() -> None:
    sunrise_at = datetime(2026, 6, 21, 9, 25, tzinfo=UTC)
    sunset_at = datetime(2026, 6, 22, 0, 30, tzinfo=UTC)
    with pytest.raises(ValueError):
        classify_daylight_state(datetime(2026, 6, 21, 12, 0), sunrise_at, sunset_at)


def test_classify_daylight_state_exact_boundary_instants() -> None:
    """The boundary itself belongs to the following state on both ends:
    `[sunrise_at, sunset_at)` -- the instant of sunrise is already "day,"
    the instant of sunset is already "night," matching how `find_daylight_
    window` constructs this pair (a sunrise is never later than the
    instant it was found relative to; see that function's own docstring)."""

    sunrise_at = datetime(2026, 6, 21, 9, 25, tzinfo=UTC)
    sunset_at = datetime(2026, 6, 22, 0, 30, tzinfo=UTC)
    assert classify_daylight_state(sunrise_at - timedelta(seconds=1), sunrise_at, sunset_at) == "night"
    assert classify_daylight_state(sunrise_at, sunrise_at, sunset_at) == "day"
    assert classify_daylight_state(sunset_at - timedelta(seconds=1), sunrise_at, sunset_at) == "day"
    assert classify_daylight_state(sunset_at, sunrise_at, sunset_at) == "night"


def _daylight_window(latitude: float, longitude: float, instant: datetime) -> tuple[datetime, datetime]:
    """Test-only helper mirroring `ProductRepository._get_daylight_window_
    in_session`'s pure-function core, without a database: compute the
    three candidate dates, fetch each directly (no caching needed for a
    test), and hand them to `find_daylight_window`."""

    candidates = []
    for candidate_date in candidate_dates_for_window(instant):
        try:
            candidates.append(compute_daily_solar_facts(latitude, longitude, candidate_date))
        except SolarContextUnavailableError:
            continue
    window = find_daylight_window(candidates, instant)
    assert window is not None
    return window


def test_find_daylight_window_western_longitude_sunset_crosses_utc_midnight() -> None:
    """NYC (west of Greenwich): a Visit at real local mid-afternoon (UTC
    instant), classified using only coordinates + that UTC instant, must
    resolve a self-consistent window whose sunset genuinely follows its
    sunrise in absolute time, even though the two fall on different UTC
    calendar dates."""

    instant = datetime(2026, 6, 21, 20, 0, tzinfo=UTC)  # 16:00 EDT, mid-afternoon
    sunrise_at, sunset_at = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, instant)
    assert sunrise_at < sunset_at
    assert sunrise_at <= instant < sunset_at
    assert sunrise_at.date() == date(2026, 6, 21)
    assert sunset_at.date() == date(2026, 6, 22)  # correctly the following UTC date
    assert classify_daylight_state(instant, sunrise_at, sunset_at) == "day"


def test_find_daylight_window_eastern_longitude_date_boundary_counterpart() -> None:
    """Tokyo (east of Greenwich): the same property, on the hemisphere
    where the UTC-date-boundary crossing runs the other direction."""

    instant = datetime(2026, 6, 21, 3, 0, tzinfo=UTC)  # 12:00 JST, local noon
    sunrise_at, sunset_at = _daylight_window(35.68, 139.7, instant)
    assert sunrise_at < sunset_at
    assert sunrise_at <= instant < sunset_at
    assert classify_daylight_state(instant, sunrise_at, sunset_at) == "day"
    # This window's own sunrise/sunset genuinely fall on two different UTC
    # calendar dates -- confirms this used the cross-date bracket for
    # real, not merely a same-date pair that happened to work out.
    assert sunrise_at.date() == date(2026, 6, 20)
    assert sunset_at.date() == date(2026, 6, 21)


def test_find_daylight_window_visit_just_before_and_after_sunrise() -> None:
    reference = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    just_before = reference.sunrise_at - timedelta(minutes=1)
    just_after = reference.sunrise_at + timedelta(minutes=1)
    sunrise_before, sunset_before = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, just_before)
    sunrise_after, sunset_after = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, just_after)
    assert classify_daylight_state(just_before, sunrise_before, sunset_before) == "night"
    assert classify_daylight_state(just_after, sunrise_after, sunset_after) == "day"


def test_find_daylight_window_visit_just_before_and_after_sunset() -> None:
    reference = compute_daily_solar_facts(NYC_LATITUDE, NYC_LONGITUDE, date(2026, 6, 21))
    # This UTC-day's own sunset (see the "for_date is the UTC calendar
    # date" test above) is the *real* upcoming sunset relative to a
    # mid-day instant one day later in local terms -- use the window
    # finder itself (not the raw per-date fact) to get the one genuinely
    # relevant to a concrete Visit instant, matching how the repository
    # always does this.
    afternoon = datetime(2026, 6, 21, 20, 0, tzinfo=UTC)
    _, sunset_at = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, afternoon)
    just_before = sunset_at - timedelta(minutes=1)
    just_after = sunset_at + timedelta(minutes=1)
    sunrise_before, sunset_before = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, just_before)
    sunrise_after, sunset_after = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, just_after)
    assert classify_daylight_state(just_before, sunrise_before, sunset_before) == "day"
    assert classify_daylight_state(just_after, sunrise_after, sunset_after) == "night"


def test_daylight_classification_unaffected_by_season_with_no_civil_timezone_stored() -> None:
    """Direct proof of requirement: DST season must not alter UTC-instant
    solar classification merely because no civil timezone is stored.
    Nothing in this module ever reads a season, a DST flag, or any
    timezone -- classification is a pure function of coordinates and a
    UTC instant. Pick a January (EST-season, if a civil zone existed) and
    a July (EDT-season) instant that are each unambiguously mid-morning
    daylight in NYC, and confirm both classify correctly with the exact
    same code path -- there is no DST-aware branch to regress."""

    winter_midmorning = datetime(2026, 1, 15, 15, 0, tzinfo=UTC)  # ~10am EST equivalent
    summer_midmorning = datetime(2026, 7, 15, 15, 0, tzinfo=UTC)  # ~11am EDT equivalent
    for instant in (winter_midmorning, summer_midmorning):
        sunrise_at, sunset_at = _daylight_window(NYC_LATITUDE, NYC_LONGITUDE, instant)
        assert classify_daylight_state(instant, sunrise_at, sunset_at) == "day"


@pytest.mark.parametrize(
    ("latitude", "longitude", "label"),
    [
        (40.7, -74.0, "NYC (west, northern summer)"),
        (35.68, 139.7, "Tokyo (east, northern summer)"),
        (-33.9, 151.2, "Sydney (east, southern winter)"),
        (51.5, -0.1, "London (near Greenwich)"),
    ],
)
def test_find_daylight_window_hourly_sweep_is_self_consistent(
    latitude: float, longitude: float, label: str
) -> None:
    """Property-style sweep (not just hand-picked instants): for 72
    consecutive hourly UTC instants, the window found is always self-
    consistent (`sunrise_at <= instant < sunset_at` or the instant is
    correctly "night"), and exactly two day/night transitions occur per
    ~24h -- proving the bracket search has no hidden longitude-specific
    failure mode across these hemispheres."""

    instant = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)
    previous_state = None
    transitions = 0
    for _ in range(72):
        sunrise_at, sunset_at = _daylight_window(latitude, longitude, instant)
        assert sunrise_at <= instant
        assert sunrise_at < sunset_at
        state = classify_daylight_state(instant, sunrise_at, sunset_at)
        if previous_state is not None and state != previous_state:
            transitions += 1
        previous_state = state
        instant += timedelta(hours=1)
    assert transitions == 6, f"{label}: expected 6 transitions in 72h, got {transitions}"


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
    assert today.information_class == "inferred"
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
        # Bounded, not unbounded: one sunrise + one sunset row for each of
        # the 3 UTC calendar dates `_get_daylight_window_in_session`
        # brackets "now" with (see `candidate_dates_for_window`) -- 6
        # rows total, cached once and reused by the second call above,
        # never growing further on repeated calls for the same "now".
        assert len(rows) == 6
        assert len({row.for_date for row in rows}) == 3  # exactly 3 distinct bracketing dates
        assert {row.metric for row in rows} == {"sunrise", "sunset"}
        for row in rows:
            assert row.information_class == "inferred"
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
    assert noon_context.information_class == "inferred"  # canonical doctrine tier, not "derived"
    assert noon_context.evaluated_at == datetime(2026, 6, 21, 16, 0, tzinfo=UTC)

    # ~2am EDT (06:00 UTC the following day) is unambiguously nighttime --
    # exercised through the real repository path (not the pure functions
    # tested above) to confirm `_get_daylight_window_in_session`'s cross-
    # date bracketing works end to end, including its own caching.
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
        # 6, not 2: one "today" lookup caches all 3 bracketing UTC dates
        # (see `test_daily_solar_context_is_cached_not_recomputed`, above).
        assert len(rows) == 6
