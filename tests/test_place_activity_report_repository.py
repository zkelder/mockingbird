"""Place Intelligence Repository/API Integration v1 (see
docs/place-activity-report-contract.md and
mockingbird.repository.product_repository.ProductRepository.
place_activity_report).

These tests exercise the real integration path -- durable SQLite state,
`ProductRepository.place_activity_report`, and the `/api/analytics/
place-activity-report` HTTP route -- as a complement to
`tests/test_place_activity_report.py`'s pure-domain coverage of
`mockingbird.analytics.place_activity_report` itself. Confirmed truth is
established through the real `create_review_label`/`create_species_
suggestion` write paths wherever the scenario is about truth precedence,
not by hand-setting `VisitModel.reviewed_label`, so these tests prove the
full write -> read pipeline agrees with the pure module's own contract.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    PlaceActivityReportRequest,
    ReviewCorrectionCreate,
    SpeciesSuggestionCreateRequest,
)
from mockingbird.repository.product_repository import ProductRepository, SpeciesSuggestionModel
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

SOURCE_ID = "source-place-report"
ARCHIVED_SOURCE_ID = "source-place-report-archived"
STREAM_A = "stream-place-report-a"
STREAM_B = "stream-place-report-b"
ARCHIVED_STREAM = "stream-place-report-archived"
ZONE_FEEDER = "zone-place-report-feeder"
ZONE_YARD_A = "zone-place-report-yard-a"
ZONE_YARD_B = "zone-place-report-yard-b"
ARCHIVED_ZONE = "zone-place-report-archived"

PERIOD_START = datetime(2026, 7, 1, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    with repository.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            assert demo is not None
            demo.status = "archived"
            session.add_all(
                [
                    CameraSourceModel(
                        id=SOURCE_ID,
                        name="Place report camera",
                        kind="manual_upload",
                        status="connected",
                        description="Focused Place Activity Report fixture.",
                    ),
                    CameraSourceModel(
                        id=ARCHIVED_SOURCE_ID,
                        name="Retired place report camera",
                        kind="manual_upload",
                        status="archived",
                        description="Excluded-from-Place fixture source.",
                    ),
                ]
            )
            session.add_all(
                [
                    StreamModel(
                        id=STREAM_A,
                        source_id=SOURCE_ID,
                        name="Yard stream A",
                        description="Focused Place Activity Report fixture.",
                        is_live=False,
                    ),
                    StreamModel(
                        id=STREAM_B,
                        source_id=SOURCE_ID,
                        name="Yard stream B",
                        description="Focused Place Activity Report fixture.",
                        is_live=False,
                    ),
                    StreamModel(
                        id=ARCHIVED_STREAM,
                        source_id=ARCHIVED_SOURCE_ID,
                        name="Retired stream",
                        description="Excluded-from-Place fixture stream.",
                        is_live=False,
                    ),
                ]
            )
            session.add_all(
                [
                    ZoneModel(
                        id=ZONE_FEEDER,
                        stream_id=STREAM_A,
                        name="Feeder",
                        zone_type="feeder",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                    # Same display name, two different Streams/zone_ids --
                    # required scenario #9.
                    ZoneModel(
                        id=ZONE_YARD_A,
                        stream_id=STREAM_A,
                        name="Yard",
                        zone_type="yard",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                    ZoneModel(
                        id=ZONE_YARD_B,
                        stream_id=STREAM_B,
                        name="Yard",
                        zone_type="yard",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                    ZoneModel(
                        id=ARCHIVED_ZONE,
                        stream_id=ARCHIVED_STREAM,
                        name="Retired yard",
                        zone_type="yard",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                ]
            )
    return repository


def _add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    at: datetime,
    stream_id: str = STREAM_A,
    zone_id: str | None = None,
    duration_seconds: int = 20,
) -> None:
    """Create one bare needs_review Visit -- the real creation state.
    Confirmed/provisional truth is layered on afterward through the real
    `create_review_label`/`create_species_suggestion` write paths, never by
    hand-setting `VisitModel.reviewed_label` -- see the module docstring."""

    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Place report fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=at,
                    ended_at=at + timedelta(seconds=duration_seconds),
                    primary_zone_id=zone_id,
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
                    zone_id=zone_id,
                    is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=visit_id,
            label=label,
            review_origin="human",
        )
    )


def _suggest(
    repository: ProductRepository,
    *,
    visit_id: str,
    stream_id: str,
    label: str,
) -> None:
    repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            source_id=SOURCE_ID,
            stream_id=stream_id,
            event_id=f"event-{visit_id}",
            visit_id=visit_id,
            adapter_id="fixture",
            adapter_name="Fixture suggester",
            suggested_label=label,
        )
    )


def _add_exposure(
    repository: ProductRepository,
    *,
    interval_id: str,
    stream_id: str,
    started_at: datetime,
    ended_at: datetime,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id,
                    stream_id=stream_id,
                    source_id=SOURCE_ID,
                    runtime_generation_id=f"generation-{interval_id}",
                    started_at=started_at,
                    last_confirmed_fresh_at=ended_at,
                    ended_at=ended_at,
                    close_reason="provider_failure",
                    created_at=started_at,
                    updated_at=ended_at,
                )
            )


def _counts(repository: ProductRepository) -> dict[str, int]:
    with repository.session_factory() as session:
        return {
            "events": session.scalar(select(func.count(EventModel.id))) or 0,
            "visits": session.scalar(select(func.count(VisitModel.id))) or 0,
            "labels": session.scalar(select(func.count(ReviewLabelModel.id))) or 0,
            "suggestions": session.scalar(select(func.count(SpeciesSuggestionModel.id))) or 0,
            "exposure_intervals": session.scalar(
                select(func.count(MonitoringExposureIntervalModel.id))
            )
            or 0,
        }


def _report(
    repository: ProductRepository,
    *,
    start_at=PERIOD_START,
    end_at=PERIOD_END,
    now=None,
    local_timezone=None,
):
    return repository.place_activity_report(
        PlaceActivityReportRequest(start_at=start_at, end_at=end_at),
        now=now,
        local_timezone=local_timezone,
    )


# 1. Empty period -------------------------------------------------------------


def test_empty_period_returns_honest_empty_report(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="outside-period", at=PERIOD_START - timedelta(days=5))

    report = _report(repository)

    assert report.total_visit_count == 0
    assert report.wildlife_visit_count == 0
    assert report.taxa == []
    assert report.activity_by_zone == []
    assert report.busiest_zone is None
    assert len(report.activity_by_hour) == 24
    assert all(entry.wildlife_visit_count == 0 for entry in report.activity_by_hour)
    # An empty report is not an error, and coverage is an honest "not yet
    # computable" fact, not a fabricated number -- no exposure history exists.
    assert report.coverage.monitored_seconds is None
    assert report.coverage.coverage_ratio is None


# 2. Confirmed wildlife Visit ---------------------------------------------------


def test_confirmed_wildlife_visit_via_real_review_write_path(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="confirmed-cardinal", at=PERIOD_START + timedelta(hours=8), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="confirmed-cardinal", label="northern_cardinal")

    report = _report(repository)

    assert report.confirmed_wildlife_visit_count == 1
    assert report.provisional_wildlife_visit_count == 0
    assert report.wildlife_visit_count == 1
    [taxon] = report.taxa
    assert taxon.label == "northern_cardinal"
    assert taxon.category == "bird"
    assert taxon.is_species is True
    assert taxon.confirmed_visit_count == 1
    assert taxon.provisional_visit_count == 0


# 3. Provisional-only wildlife Visit ---------------------------------------------


def test_provisional_only_wildlife_visit_usable_absent_truth(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="suggested-finch", at=PERIOD_START + timedelta(hours=9), zone_id=ZONE_FEEDER)
    _suggest(repository, visit_id="suggested-finch", stream_id=STREAM_A, label="house_finch")

    report = _report(repository)

    assert report.confirmed_wildlife_visit_count == 0
    assert report.provisional_wildlife_visit_count == 1
    assert report.wildlife_visit_count == 1
    [taxon] = report.taxa
    assert taxon.label == "house_finch"
    assert taxon.confirmed_visit_count == 0
    assert taxon.provisional_visit_count == 1


# 4. Confirmed review overrides a provisional suggestion -------------------------


def test_confirmed_review_overrides_provisional_suggestion_outright(
    repository: ProductRepository,
) -> None:
    """The trickiest precedence case: a Visit carries both a (now-stale)
    automatic suggestion and a later human correction that disagrees with
    it, exactly like a real reviewed-after-BioCLIP Visit. Confirmed truth
    must win outright -- never blended -- matching
    docs/review-decision-provenance-contract.md exactly."""

    _add_visit(repository, visit_id="overridden", at=PERIOD_START + timedelta(hours=10), zone_id=ZONE_FEEDER)
    _suggest(repository, visit_id="overridden", stream_id=STREAM_A, label="house_finch")
    _confirm(repository, visit_id="overridden", label="northern_cardinal")

    report = _report(repository)

    assert report.confirmed_wildlife_visit_count == 1
    assert report.provisional_wildlife_visit_count == 0
    assert [taxon.label for taxon in report.taxa] == ["northern_cardinal"]


# 5. Unresolved Visit -----------------------------------------------------------


def test_unresolved_visit_with_no_truth_or_suggestion(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="unresolved", at=PERIOD_START + timedelta(hours=11), zone_id=ZONE_FEEDER)

    report = _report(repository)

    assert report.unresolved_visit_count == 1
    assert report.wildlife_visit_count == 0
    assert report.taxa == []


# 6. Confirmed animal with unresolved species ------------------------------------


def test_confirmed_animal_with_unresolved_species_counts_without_fabricating_a_taxon(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="confirmed-unknown", at=PERIOD_START + timedelta(hours=12), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="confirmed-unknown", label="unknown_animal")

    report = _report(repository)

    assert report.confirmed_wildlife_visit_count == 1
    assert report.confirmed_species_unresolved_visit_count == 1
    assert report.wildlife_visit_count == 1
    assert report.taxa == []


# 7. Non-wildlife Visit -----------------------------------------------------------


def test_non_wildlife_visit_is_excluded_from_wildlife_counts(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="confirmed-person", at=PERIOD_START + timedelta(hours=13), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="confirmed-person", label="person")

    report = _report(repository)

    assert report.non_wildlife_visit_count == 1
    assert report.wildlife_visit_count == 0
    assert report.total_visit_count == 1


# 8. Multiple taxa ------------------------------------------------------------


def test_multiple_taxa_are_each_represented(repository: ProductRepository) -> None:
    for index, visit_id in enumerate(["cardinal-a", "cardinal-b"]):
        _add_visit(repository, visit_id=visit_id, at=PERIOD_START + timedelta(hours=1 + index), zone_id=ZONE_FEEDER)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    _add_visit(repository, visit_id="finch-a", at=PERIOD_START + timedelta(hours=3), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="finch-a", label="house_finch")

    report = _report(repository)

    assert report.distinct_taxa_count == 2
    assert [taxon.label for taxon in report.taxa] == ["northern_cardinal", "house_finch"]
    cardinal = report.taxa[0]
    assert cardinal.confirmed_visit_count == 2


# 9. Same Zone name, distinct Zone ids -------------------------------------------


def test_same_zone_name_on_different_streams_is_never_merged(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="yard-a-cardinal", at=PERIOD_START + timedelta(hours=1), stream_id=STREAM_A, zone_id=ZONE_YARD_A)
    _confirm(repository, visit_id="yard-a-cardinal", label="northern_cardinal")
    _add_visit(repository, visit_id="yard-b-finch", at=PERIOD_START + timedelta(hours=2), stream_id=STREAM_B, zone_id=ZONE_YARD_B)
    _confirm(repository, visit_id="yard-b-finch", label="house_finch")

    report = _report(repository)

    yard_entries = [entry for entry in report.activity_by_zone if entry.zone_name == "Yard"]
    assert len(yard_entries) == 2
    assert {entry.zone_id for entry in yard_entries} == {ZONE_YARD_A, ZONE_YARD_B}


# 10. Local-time hourly bucketing -------------------------------------------------


def test_activity_by_hour_uses_resolved_local_time_not_utc(
    repository: ProductRepository,
) -> None:
    # 2026-07-01T23:30:00Z is 2026-07-01T19:30:00-04:00 (EDT) -- hour 19
    # locally, not hour 23.
    at = PERIOD_START + timedelta(hours=23, minutes=30)
    _add_visit(repository, visit_id="late-cardinal", at=at, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="late-cardinal", label="northern_cardinal")

    report = _report(repository, now=datetime(2026, 7, 15, 12, tzinfo=UTC))

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[19] == 1
    assert by_hour[23] == 0


# 11. Monitoring interval clipping to report bounds -------------------------------


def test_monitoring_interval_is_clipped_to_report_bounds(
    repository: ProductRepository,
) -> None:
    _add_exposure(
        repository,
        interval_id="exposure-overflowing",
        stream_id=STREAM_A,
        started_at=PERIOD_START - timedelta(hours=6),
        ended_at=PERIOD_END + timedelta(hours=6),
    )
    _add_exposure(
        repository,
        interval_id="exposure-b",
        stream_id=STREAM_B,
        started_at=PERIOD_START - timedelta(hours=6),
        ended_at=PERIOD_END + timedelta(hours=6),
    )

    report = _report(repository)

    assert report.coverage.monitored_seconds == pytest.approx(
        (PERIOD_END - PERIOD_START).total_seconds()
    )
    assert report.coverage.coverage_ratio == pytest.approx(1.0)
    assert report.coverage.gaps == []


# 12. Coverage gaps -----------------------------------------------------------------


def test_coverage_gaps_are_reported(repository: ProductRepository) -> None:
    monitored_end = PERIOD_START + timedelta(hours=10)
    _add_exposure(
        repository,
        interval_id="exposure-partial-a",
        stream_id=STREAM_A,
        started_at=PERIOD_START,
        ended_at=monitored_end,
    )
    _add_exposure(
        repository,
        interval_id="exposure-partial-b",
        stream_id=STREAM_B,
        started_at=PERIOD_START,
        ended_at=monitored_end,
    )

    report = _report(repository)

    assert report.coverage.monitored_seconds == pytest.approx(10 * 3600)
    assert report.coverage.coverage_ratio == pytest.approx(10 / 24)
    assert len(report.coverage.gaps) == 1
    assert report.coverage.gaps[0].start_at == monitored_end
    assert report.coverage.gaps[0].end_at == PERIOD_END


# 13. Partial coverage history ------------------------------------------------------


def test_coverage_marks_history_partial_when_period_predates_it(
    repository: ProductRepository,
) -> None:
    history_start = PERIOD_START + timedelta(hours=3)
    _add_exposure(
        repository,
        interval_id="exposure-late-start-a",
        stream_id=STREAM_A,
        started_at=history_start,
        ended_at=PERIOD_END,
    )
    _add_exposure(
        repository,
        interval_id="exposure-late-start-b",
        stream_id=STREAM_B,
        started_at=history_start,
        ended_at=PERIOD_END,
    )

    report = _report(repository)

    assert report.coverage.history_is_partial is True
    assert report.coverage.history_available_from == history_start
    assert report.coverage.monitored_seconds == pytest.approx(
        (PERIOD_END - history_start).total_seconds()
    )


def test_coverage_reflects_established_streams_when_one_stream_has_no_history(
    repository: ProductRepository,
) -> None:
    """Coverage-policy audit (Place Intelligence Backend Hardening v1):
    Stream A has full, trustworthy durable exposure history for the whole
    period; Stream B (a newly-added, not-yet-reporting camera) has none at
    all. The Place-wide figure is a *union* -- "was this Place being
    watched by any camera" -- and Stream B contributes nothing to that
    union either way, so it must not retroactively blank out Stream A's
    real, trustworthy coverage. This replaces the previous all-or-nothing
    policy this same scenario used to test (see git history for
    `test_coverage_withheld_when_any_in_scope_stream_lacks_history`); the
    fully-withheld case is still covered separately below when *no* Stream
    has any history at all."""

    _add_exposure(
        repository,
        interval_id="exposure-only-a",
        stream_id=STREAM_A,
        started_at=PERIOD_START,
        ended_at=PERIOD_END,
    )

    report = _report(repository)

    assert report.coverage.monitored_seconds == pytest.approx(
        (PERIOD_END - PERIOD_START).total_seconds()
    )
    assert report.coverage.coverage_ratio == pytest.approx(1.0)
    assert report.coverage.history_available_from == PERIOD_START
    # Never silently hidden: the caveat is disclosed as an honest warning,
    # not folded into a fabricated number or a full withdrawal.
    assert any(
        "Stream" in warning and "no durable monitoring exposure" in warning
        for warning in report.warnings
    )


def test_coverage_fully_withheld_only_when_no_in_scope_stream_has_any_history(
    repository: ProductRepository,
) -> None:
    """The genuinely honest "not yet computable" case is preserved: when
    *no* in-scope Stream has ever recorded durable exposure history (both
    Stream A and Stream B here), the figure is withheld entirely rather
    than reporting a fabricated zero or full coverage."""

    report = _report(repository)

    assert report.coverage.monitored_seconds is None
    assert report.coverage.coverage_ratio is None
    assert report.coverage.history_available_from is None
    assert report.maturity == "no_data"
    assert any(
        "No durable monitoring exposure has been recorded for any Stream yet"
        in warning
        for warning in report.warnings
    )


def test_coverage_survives_a_new_stream_added_midway_through_a_long_period(
    repository: ProductRepository,
) -> None:
    """The concrete scenario the coverage-policy audit was about: a Place
    with a full year of trustworthy history on Stream A must not have that
    entire year become "coverage unavailable" the moment a second camera
    (Stream B) is added late in the period and has not reported any
    durable exposure yet."""

    year_start = datetime(2025, 1, 1, tzinfo=UTC)
    year_end = year_start + timedelta(days=365)
    _add_exposure(
        repository,
        interval_id="exposure-full-year-a",
        stream_id=STREAM_A,
        started_at=year_start,
        ended_at=year_end,
    )
    # Stream B was added on day 300 but has not yet recorded a single
    # healthy frame -- no MonitoringExposureIntervalModel row at all.

    report = _report(repository, start_at=year_start, end_at=year_end)

    assert report.coverage.monitored_seconds == pytest.approx(
        (year_end - year_start).total_seconds()
    )
    assert report.coverage.coverage_ratio == pytest.approx(1.0)
    assert report.coverage.history_is_partial is False


# 14. Report period excludes out-of-window Visits -----------------------------------


def test_report_period_excludes_out_of_window_visits(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="before", at=PERIOD_START - timedelta(minutes=1), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="before", label="northern_cardinal")
    _add_visit(repository, visit_id="at-start", at=PERIOD_START, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="at-start", label="northern_cardinal")
    _add_visit(repository, visit_id="at-end", at=PERIOD_END, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="at-end", label="northern_cardinal")
    _add_visit(repository, visit_id="after", at=PERIOD_END + timedelta(minutes=1), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="after", label="northern_cardinal")

    report = _report(repository)

    # Half-open period [start, end): start included, end excluded.
    assert report.total_visit_count == 1
    assert report.first_activity_at == PERIOD_START
    assert report.last_activity_at == PERIOD_START


# 15. Read-only behavior --------------------------------------------------------------


def test_report_generation_is_read_only(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="confirmed-cardinal", at=PERIOD_START + timedelta(hours=1), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="confirmed-cardinal", label="northern_cardinal")
    _add_visit(repository, visit_id="suggested-finch", at=PERIOD_START + timedelta(hours=2), zone_id=ZONE_FEEDER)
    _suggest(repository, visit_id="suggested-finch", stream_id=STREAM_A, label="house_finch")
    _add_exposure(repository, interval_id="exposure-readonly-a", stream_id=STREAM_A, started_at=PERIOD_START, ended_at=PERIOD_END)
    _add_exposure(repository, interval_id="exposure-readonly-b", stream_id=STREAM_B, started_at=PERIOD_START, ended_at=PERIOD_END)
    before = _counts(repository)

    _report(repository)
    _report(repository)  # calling it twice must be equally inert

    client = TestClient(app)
    response = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat(), "end_at": PERIOD_END.isoformat()},
    )
    assert response.status_code == 200

    assert _counts(repository) == before


# 16. API serialization contract -------------------------------------------------------


def test_api_serialization_contract_exposes_only_documented_fields(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="confirmed-cardinal", at=PERIOD_START + timedelta(hours=1), stream_id=STREAM_A, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="confirmed-cardinal", label="northern_cardinal")
    _add_exposure(repository, interval_id="exposure-api-a", stream_id=STREAM_A, started_at=PERIOD_START, ended_at=PERIOD_END)
    _add_exposure(repository, interval_id="exposure-api-b", stream_id=STREAM_B, started_at=PERIOD_START, ended_at=PERIOD_END)

    client = TestClient(app)
    response = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat(), "end_at": PERIOD_END.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()

    assert set(body.keys()) == {
        "period_start_at",
        "period_end_at",
        "timezone_name",
        "generated_at",
        "total_visit_count",
        "confirmed_wildlife_visit_count",
        "provisional_wildlife_visit_count",
        "unresolved_visit_count",
        "non_wildlife_visit_count",
        "excluded_visit_count",
        "confirmed_species_unresolved_visit_count",
        "wildlife_visit_count",
        "distinct_taxa_count",
        "distinct_species_count",
        "taxa",
        "first_activity_at",
        "last_activity_at",
        "activity_by_zone",
        "busiest_zone",
        "activity_by_hour",
        "coverage",
        "maturity",
        "historical_baseline",
        "change_windows",
        "overall_change_status",
        "warnings",
    }
    assert body["total_visit_count"] == 1
    # A full day of durable exposure on both Streams is well past the
    # sparse-coverage threshold -- see compute_report_maturity.
    assert body["maturity"] == "usable"
    [taxon] = body["taxa"]
    assert set(taxon.keys()) == {
        "label",
        "display_name",
        "category",
        "is_species",
        "confirmed_visit_count",
        "provisional_visit_count",
        "total_visit_count",
        "first_activity_at",
        "last_activity_at",
        "historical_status",
        "change_status",
    }
    assert taxon["label"] == "northern_cardinal"
    assert taxon["category"] == "bird"
    # A single confirmation with no accumulated monitoring history at all
    # (this fixture never seeds MonitoringExposureIntervalModel rows before
    # PERIOD_START) is honestly its own all-time-first record, under an
    # insufficient baseline -- see Historical Baseline Maturity + New/
    # Regular Species v1, docs/historical-baseline-maturity-contract.md.
    assert set(taxon["historical_status"].keys()) == {
        "first_confirmed_at",
        "last_confirmed_at",
        "distinct_confirmed_days",
        "distinct_confirmed_usable_days",
        "total_confirmed_count",
        "status",
    }
    assert taxon["historical_status"]["status"] == "first_record"
    # Gate C -- Meaningful Change Detection / Baseline Comparison v1 (see
    # docs/meaningful-change-detection-contract.md): the identical zero-
    # accumulated-history fixture that makes historical_status "first_
    # record" above also makes any change comparison honestly unsupported.
    assert set(taxon["change_status"].keys()) == {
        "recent_presence_days",
        "recent_usable_day_count",
        "reference_presence_days",
        "reference_usable_day_count",
        "status",
    }
    assert taxon["change_status"]["status"] == "insufficient_baseline"
    assert set(body["change_windows"].keys()) == {
        "policy_version",
        "recent_window_start_at",
        "recent_window_end_at",
        "reference_window_start_at",
        "reference_window_end_at",
        "is_valid",
        "invalid_reason",
    }
    assert body["change_windows"]["is_valid"] is False
    assert body["change_windows"]["invalid_reason"] == "insufficient_baseline"
    assert set(body["overall_change_status"].keys()) == {
        "recent_presence_days",
        "recent_usable_day_count",
        "reference_presence_days",
        "reference_usable_day_count",
        "status",
    }
    assert body["overall_change_status"]["status"] == "building_baseline"
    assert len(body["activity_by_hour"]) == 24
    assert set(body["coverage"].keys()) == {
        "period_seconds",
        "monitored_seconds",
        "coverage_ratio",
        "history_available_from",
        "history_is_partial",
        "gaps",
        "gaps_truncated",
    }
    assert body["coverage"]["coverage_ratio"] == pytest.approx(1.0)
    assert set(body["historical_baseline"].keys()) == {
        "window_start_at",
        "window_end_at",
        "usable_day_count",
        "total_monitored_seconds",
        "maturity",
        "distinct_taxa_count",
        "earliest_authoritative_record_at",
        "latest_authoritative_record_at",
    }
    assert body["historical_baseline"]["maturity"] == "insufficient"
    # No raw internal ORM identifiers (visit_id, event_id, zone/stream
    # ORM ids on the taxon, SQLAlchemy state) ever leak into the response.
    assert "visit_id" not in taxon
    assert "_sa_instance_state" not in body


# 17. Invalid reporting-window inputs -------------------------------------------------


def test_invalid_reporting_window_inputs_are_rejected(repository: ProductRepository) -> None:
    client = TestClient(app)

    end_before_start = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_END.isoformat(), "end_at": PERIOD_START.isoformat()},
    )
    assert end_before_start.status_code == 422

    too_long = client.post(
        "/api/analytics/place-activity-report",
        json={
            "start_at": "2020-01-01T00:00:00+00:00",
            "end_at": "2026-01-03T00:00:01+00:00",
        },
    )
    assert too_long.status_code == 422

    missing_end = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat()},
    )
    assert missing_end.status_code == 422

    unknown_field = client.post(
        "/api/analytics/place-activity-report",
        json={
            "start_at": PERIOD_START.isoformat(),
            "end_at": PERIOD_END.isoformat(),
            "zone_id": "unexpected",
        },
    )
    assert unknown_field.status_code == 422

    valid = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat(), "end_at": PERIOD_END.isoformat()},
    )
    assert valid.status_code == 200


# 18. DST-boundary behavior -----------------------------------------------------------


def test_local_offset_resolves_correctly_for_the_generation_moment(tmp_path: Path) -> None:
    """`timezone_name` (a display label, e.g. "EST"/"EDT") reflects the
    resolved local zone's abbreviation *at the report's generation moment*
    -- proven here with a January (EST) and a July (EDT) `now`, both
    correctly distinct. This is a narrower property than hour-bucketing
    correctness: see tests/test_place_activity_report.py's "DST-correct
    local-time bucketing" section and the `local_timezone=` cases below in
    this file for proof that each *Visit* (not just the display label) is
    now converted using the actual IANA zone rules applicable at its own
    timestamp -- the real fix for the limitation this test used to
    document here, before `ProductRepository.place_activity_report`
    resolved a real `zoneinfo.ZoneInfo` (via
    `mockingbird.time_utils.resolve_host_local_timezone`) instead of one
    fixed offset snapshotted from the generation moment and reused for the
    whole requested period."""

    winter_now = datetime(2026, 1, 15, 17, 0, tzinfo=UTC)  # noon EST
    summer_now = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)  # noon EDT
    assert winter_now.astimezone(ZoneInfo("America/New_York")).tzname() == "EST"
    assert summer_now.astimezone(ZoneInfo("America/New_York")).tzname() == "EDT"

    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    try:
        # A fixed UTC instant that falls at 19:30 local under EDT and 12:30
        # local under EST, so the same Visit's hour bucket must move with
        # the resolved offset.
        moment = datetime(2026, 3, 1, 0, 30, tzinfo=UTC)
        winter_report = repository.place_activity_report(
            PlaceActivityReportRequest(start_at=moment - timedelta(hours=1), end_at=moment + timedelta(hours=1)),
            now=winter_now,
        )
        summer_report = repository.place_activity_report(
            PlaceActivityReportRequest(start_at=moment - timedelta(hours=1), end_at=moment + timedelta(hours=1)),
            now=summer_now,
        )
    finally:
        repository.close()

    assert winter_report.timezone_name == "EST"
    assert summer_report.timezone_name == "EDT"


# 2026 US spring-forward: 01:59:59 EST -> 03:00:00 EDT at 07:00:00Z.
# 2026 US fall-back: 01:59:59 EDT -> 01:00:00 EST at 06:00:00Z, so local
# 01:00-01:59 occurs twice.
_SPRING_FORWARD = datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
_FALL_BACK = datetime(2026, 11, 1, 6, 0, tzinfo=UTC)


def test_repository_report_buckets_spring_forward_transition_correctly(
    repository: ProductRepository,
) -> None:
    """End-to-end proof through the real write path and real SQLite storage
    (not just the pure module `test_place_activity_report.py` already
    covers) that the repository's DST fix is real: a Visit just before the
    2026 US spring-forward jump and one just after must each land in the
    local hour that genuinely applied to its own timestamp. Uses the
    `local_timezone=` test-only override so this is fully deterministic
    regardless of the host machine's own configured zone."""

    before = _SPRING_FORWARD - timedelta(minutes=30)  # 01:30 EST
    after = _SPRING_FORWARD + timedelta(minutes=30)  # 03:30 EDT
    _add_visit(repository, visit_id="before-spring-forward", at=before, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="before-spring-forward", label="northern_cardinal")
    _add_visit(repository, visit_id="after-spring-forward", at=after, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="after-spring-forward", label="house_finch")

    report = _report(
        repository,
        start_at=_SPRING_FORWARD - timedelta(hours=2),
        end_at=_SPRING_FORWARD + timedelta(hours=2),
        local_timezone=ZoneInfo("America/New_York"),
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[1] == 1
    assert by_hour[3] == 1
    assert by_hour[2] == 0  # the local hour that never happened that day


def test_repository_report_maps_fall_back_instants_to_the_repeated_local_hour(
    repository: ProductRepository,
) -> None:
    """The defining fall-back case end-to-end: two distinct real Visits,
    one before and one after the actual transition instant, both correctly
    land in local hour 1 -- the hour the local calendar repeats -- rather
    than one of them being misplaced by a full hour."""

    first_1am = _FALL_BACK - timedelta(minutes=30)  # 01:30 EDT (first occurrence)
    second_1am = _FALL_BACK + timedelta(minutes=30)  # 01:30 EST (second occurrence)
    _add_visit(repository, visit_id="first-1am", at=first_1am, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="first-1am", label="northern_cardinal")
    _add_visit(repository, visit_id="second-1am", at=second_1am, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="second-1am", label="house_finch")

    report = _report(
        repository,
        start_at=_FALL_BACK - timedelta(hours=2),
        end_at=_FALL_BACK + timedelta(hours=2),
        local_timezone=ZoneInfo("America/New_York"),
    )

    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[1] == 2
    assert report.total_visit_count == 2


def test_repository_report_period_spanning_a_transition(repository: ProductRepository) -> None:
    """A realistic "this week" report whose own requested boundaries
    straddle a real DST transition -- not just a Visit timestamp inside an
    unrelated period."""

    period_start = _SPRING_FORWARD - timedelta(days=1)
    period_end = _SPRING_FORWARD + timedelta(days=1)
    day_before = _SPRING_FORWARD - timedelta(hours=20)  # 2026-03-07T11:00:00Z = 06:00 EST
    just_after = _SPRING_FORWARD + timedelta(minutes=30)  # 2026-03-08T07:30:00Z = 03:30 EDT
    _add_visit(repository, visit_id="day-before", at=day_before, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="day-before", label="northern_cardinal")
    _add_visit(repository, visit_id="just-after", at=just_after, zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="just-after", label="house_finch")

    report = _report(
        repository,
        start_at=period_start,
        end_at=period_end,
        local_timezone=ZoneInfo("America/New_York"),
    )

    assert report.total_visit_count == 2
    by_hour = {entry.hour: entry.wildlife_visit_count for entry in report.activity_by_hour}
    assert by_hour[6] == 1
    assert by_hour[3] == 1


def test_production_default_resolves_a_real_zone_without_an_explicit_override(
    repository: ProductRepository,
) -> None:
    """Without the test-only `local_timezone=` override, production
    resolution (`resolve_host_local_timezone`) must still run and produce a
    usable, non-crashing report -- proving the default path is wired, not
    only the explicitly-overridden test path above."""

    _add_visit(repository, visit_id="default-zone", at=PERIOD_START + timedelta(hours=8), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="default-zone", label="northern_cardinal")

    report = _report(repository)

    assert report.confirmed_wildlife_visit_count == 1
    assert sum(entry.wildlife_visit_count for entry in report.activity_by_hour) == 1


# Performance: taxonomy resolution must not scale one query per Visit -----------------


def _count_taxonomy_queries(repository: ProductRepository, fn) -> int:
    statements: list[str] = []

    def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if "taxonomy_labels" in statement:
            statements.append(statement)

    event.listen(repository.engine, "before_cursor_execute", _record)
    try:
        fn()
    finally:
        event.remove(repository.engine, "before_cursor_execute", _record)
    return len(statements)


def test_taxonomy_resolution_costs_exactly_one_query_regardless_of_visit_count(
    repository: ProductRepository,
) -> None:
    """Hardening v1 regression coverage: before this milestone,
    `_stream_visit_summary_from_models`'s own `_visit_review_outcome` cost
    one additional `taxonomy_labels` full-table-scan query *per reviewed
    Visit with a real species label* (through `_taxonomy_label_model_for_
    input`'s unbatched per-call scan), on top of this report's own
    `_taxonomy_label_index` preload for `confirmed_taxon`/
    `provisional_taxon` -- an O(N) shape that a first version of this test
    only proved didn't get *worse* (see git history for the prior
    `test_taxonomy_resolution_adds_no_second_per_visit_query`), not that it
    was fixed. It is now fixed: `_stream_visit_summary_from_models` accepts
    the same preloaded `taxonomy_index` this method already builds and
    forwards it down to `_visit_review_outcome`/`_taxonomy_label_model_for_
    input`, so the *entire* report's taxonomy resolution -- both its own
    and the canonical resolver's internal one -- costs exactly one query
    total, whether the report covers 3 Visits or 8."""

    for index in range(8):
        visit_id = f"batch-{index}"
        _add_visit(repository, visit_id=visit_id, at=PERIOD_START + timedelta(hours=index), zone_id=ZONE_FEEDER)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    def _generate(*, visit_count: int) -> int:
        def _call() -> None:
            report = repository.place_activity_report(
                PlaceActivityReportRequest(
                    start_at=PERIOD_START,
                    end_at=PERIOD_START + timedelta(hours=visit_count),
                )
            )
            assert report.confirmed_wildlife_visit_count == visit_count

        return _count_taxonomy_queries(repository, _call)

    small = _generate(visit_count=3)
    large = _generate(visit_count=8)

    assert small == 1
    assert large == 1


# Long-period performance sanity check ------------------------------------
#
# Not microbenchmarking (per this milestone's own instruction): the goal is
# to catch an obvious query explosion or pathological pure-computation
# behavior at day/week/month/year scale, not to chase a tight latency
# budget. Visits are inserted directly, already reviewed, rather than
# through the real `create_review_label` write path this file otherwise
# prefers (see the module docstring) -- that write path's own performance
# (alert sync, milestone checks, etc.) is a different, unrelated concern
# from report *generation*, and conflating the two would measure the wrong
# thing; tests/test_zone_insights.py's own `_add_visit` helper already
# takes the same direct-construction shortcut for the identical reason.


def _add_reviewed_visits(
    repository: ProductRepository,
    *,
    count: int,
    start_at: datetime,
    id_prefix: str,
) -> None:
    labels = ("northern_cardinal", "house_finch", "blue_jay", "squirrel")
    with repository.session_factory() as session:
        with session.begin():
            for index in range(count):
                at = start_at + timedelta(hours=index * 6)  # spread across the year
                event_id = f"{id_prefix}-event-{index}"
                visit_id = f"{id_prefix}-visit-{index}"
                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=STREAM_A,
                        title=f"Benchmark visit {index}",
                        event_type="manual_media_import",
                        started_at=at,
                        ended_at=at + timedelta(seconds=20),
                        primary_zone_id=ZONE_FEEDER,
                        review_status="reviewed",
                    )
                )
                session.add(
                    VisitModel(
                        id=visit_id,
                        event_id=event_id,
                        subject_label="unknown_bird",
                        species_guess=None,
                        confidence=None,
                        reviewed_label=labels[index % len(labels)],
                        review_status="reviewed",
                        representative_media_path=None,
                        zone_id=ZONE_FEEDER,
                        is_superseded=False,
                    )
                )


def test_report_generation_query_shape_stays_bounded_at_a_materially_larger_cohort(
    repository: ProductRepository,
) -> None:
    """A year-scale Place with a materially larger reviewed-Visit cohort
    (150 Visits vs. a 25-Visit baseline, 6x) must not show query-count
    growth worse than linear, and must still generate in a bounded,
    reasonable time. This is the milestone's "long-period performance
    sanity check," not a tight latency budget -- the wall-clock assertion
    is deliberately generous so it does not become a flaky CI trip-wire."""

    year_start = datetime(2025, 1, 1, tzinfo=UTC)
    small_count = 25
    large_count = 150
    _add_reviewed_visits(repository, count=large_count, start_at=year_start, id_prefix="bench")

    def _generate(*, visit_count: int) -> tuple[int, float]:
        # The first `visit_count` Visits are 6h apart, so this end bound
        # selects exactly that many without needing a second, separate
        # data set -- matching the existing "reuse one larger fixture,
        # vary the requested period" pattern already proven above.
        end_at = year_start + timedelta(hours=visit_count * 6)
        statements: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            statements.append(statement)

        event.listen(repository.engine, "before_cursor_execute", _record)
        started = perf_counter()
        try:
            report = repository.place_activity_report(
                PlaceActivityReportRequest(start_at=year_start, end_at=end_at)
            )
        finally:
            event.remove(repository.engine, "before_cursor_execute", _record)
        elapsed = perf_counter() - started
        assert report.total_visit_count == visit_count
        return len(statements), elapsed

    small_queries, _small_elapsed = _generate(visit_count=small_count)
    large_queries, large_elapsed = _generate(visit_count=large_count)

    small_per_visit = small_queries / small_count
    large_per_visit = large_queries / large_count
    # Linear, not superlinear: the per-Visit query cost at 6x the cohort
    # size must not meaningfully exceed the per-Visit cost at the smaller
    # size (a generous 25% tolerance absorbs the small fixed/per-call
    # overhead that dominates at the tiny end, without hiding a real
    # O(N^2) shape, which would show a large multiple here, not a small
    # one).
    assert large_per_visit <= small_per_visit * 1.25, (
        f"query count grew faster than linearly: {small_per_visit=:.2f} "
        f"at n={small_count}, {large_per_visit=:.2f} at n={large_count}"
    )
    # Generous wall-clock ceiling for a full year, 150-Visit report against
    # real SQLite on developer/CI hardware -- a sanity trip-wire against a
    # gross pathological regression, not a performance target.
    assert large_elapsed < 5.0, f"report generation took {large_elapsed:.2f}s for {large_count} Visits"


# 19. Today Coverage Truth v1: Observation Engine writer integration ---------------
#
# `record_observation_exposure_frame`/`close_observation_exposure`
# (`ProductRepository`) are the camera_node-canonical writers of
# `MonitoringExposureIntervalModel` -- the exact same durable ledger every
# coverage test above already reads through `_add_exposure`'s raw-row
# seeding. These tests drive the *real* writers instead of hand-seeding
# rows, proving the full Observation Engine write -> Place Activity Report
# coverage read pipeline end to end. See docs/todays-coverage-truth
# -contract.md.


def _observe(
    repository: ProductRepository, *, stream_id: str, generation: str, healthy_at: datetime,
) -> None:
    repository.record_observation_exposure_frame(
        stream_id=stream_id, runtime_generation_id=generation, healthy_at=healthy_at, now=healthy_at,
    )


def _stop_observing(
    repository: ProductRepository, *, stream_id: str, now: datetime, reason: str = "session_stopped",
) -> None:
    repository.close_observation_exposure(stream_id=stream_id, close_reason=reason, now=now)


def test_sixty_minutes_of_observation_yields_about_sixty_minutes_of_coverage(
    repository: ProductRepository,
) -> None:
    """Milestone acceptance: 60 minutes of real Observation Engine activity
    produces ~60 minutes of reported coverage -- proven against a genuinely
    partial report window (90 minutes elapsed, only 60 observed), so this
    also proves the ratio is computed against the elapsed window, not a
    full nominal day."""

    window_start = PERIOD_START
    window_end = PERIOD_START + timedelta(minutes=90)
    _observe(repository, stream_id=STREAM_A, generation="gen-1", healthy_at=window_start)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-1",
        healthy_at=window_start + timedelta(minutes=60),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=window_start + timedelta(minutes=60, seconds=1))

    report = _report(repository, start_at=window_start, end_at=window_end)

    assert report.coverage.monitored_seconds == pytest.approx(60 * 60)
    assert report.coverage.coverage_ratio == pytest.approx(60 / 90)
    assert len(report.coverage.gaps) == 1
    assert report.coverage.gaps[0].start_at == window_start + timedelta(minutes=60)
    assert report.coverage.gaps[0].end_at == window_end
    # 60 real monitored minutes is above zero but still below the 2-hour
    # maturity threshold -- real, honest coverage, just not yet enough to
    # call the report "usable."
    assert report.maturity == "sparse"


def test_maturity_reaches_usable_once_real_coverage_crosses_two_hours(
    repository: ProductRepository,
) -> None:
    """Repository-level proof (not just the pure-module unit test) that
    crossing the same 2-hour threshold through a real recorded Observation
    Engine session flips maturity from "sparse" to "usable"."""

    window_start = PERIOD_START
    window_end = PERIOD_START + timedelta(hours=3)
    _observe(repository, stream_id=STREAM_A, generation="gen-1", healthy_at=window_start)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-1",
        healthy_at=window_start + timedelta(hours=2),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=window_start + timedelta(hours=2, seconds=1))

    report = _report(repository, start_at=window_start, end_at=window_end)

    assert report.coverage.monitored_seconds == pytest.approx(2 * 3600)
    assert report.maturity == "usable"


def test_stop_closes_the_interval_and_later_time_is_not_counted_as_coverage(
    repository: ProductRepository,
) -> None:
    _observe(repository, stream_id=STREAM_A, generation="gen-1", healthy_at=PERIOD_START)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-1",
        healthy_at=PERIOD_START + timedelta(hours=2),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=PERIOD_START + timedelta(hours=2, minutes=1))

    # A window extending well past the Stop -- coverage must not keep
    # growing after Stop closed the interval.
    report = _report(repository, start_at=PERIOD_START, end_at=PERIOD_START + timedelta(hours=10))

    assert report.coverage.monitored_seconds == pytest.approx(2 * 3600)
    assert len(report.coverage.gaps) == 1
    assert report.coverage.gaps[0].start_at == PERIOD_START + timedelta(hours=2)


def test_two_streams_with_partial_overlap_union_correctly(
    repository: ProductRepository,
) -> None:
    """Stream A observes hour 0-3, Stream B observes hour 2-5 -- the
    Place-level figure must be the *union* (hour 0-5, 5 hours), never the
    naive sum (3+3=6 hours, which would silently exceed what actually
    happened and could push a report over 100%)."""

    _observe(repository, stream_id=STREAM_A, generation="gen-a", healthy_at=PERIOD_START)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-a",
        healthy_at=PERIOD_START + timedelta(hours=3),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=PERIOD_START + timedelta(hours=3, minutes=1))

    _observe(
        repository, stream_id=STREAM_B, generation="gen-b",
        healthy_at=PERIOD_START + timedelta(hours=2),
    )
    _observe(
        repository, stream_id=STREAM_B, generation="gen-b",
        healthy_at=PERIOD_START + timedelta(hours=5),
    )
    _stop_observing(repository, stream_id=STREAM_B, now=PERIOD_START + timedelta(hours=5, minutes=1))

    report = _report(repository)

    assert report.coverage.monitored_seconds == pytest.approx(5 * 3600)
    assert report.coverage.coverage_ratio == pytest.approx(5 / 24)


def test_idle_configured_stream_contributes_zero_to_place_coverage(
    repository: ProductRepository,
) -> None:
    """Stream B is fully configured (a real Stream row in this Place) but
    Observation Engine was never started for it -- it must simply be
    excluded from the union, never dragging the figure down toward zero nor
    counted as if it had coverage."""

    _observe(repository, stream_id=STREAM_A, generation="gen-a", healthy_at=PERIOD_START)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-a",
        healthy_at=PERIOD_START + timedelta(hours=4),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=PERIOD_START + timedelta(hours=4, minutes=1))
    # Stream B: configured, never observed -- no exposure rows at all.

    report = _report(repository)

    assert report.coverage.monitored_seconds == pytest.approx(4 * 3600)
    assert report.coverage.coverage_ratio == pytest.approx(4 / 24)
    assert any(
        "Stream" in warning and "no durable monitoring exposure" in warning
        for warning in report.warnings
    )


def test_stream_with_prior_history_but_no_activity_in_window_reports_a_true_zero(
    repository: ProductRepository,
) -> None:
    """The exact real field defect this milestone fixes (commit b8c6766):
    a Stream has real Observation Engine exposure history from an *earlier*
    day, but the queried report window has zero overlap with it. Unlike the
    structural "no history at all" case (`test_coverage_fully_withheld_
    only_when_no_in_scope_stream_has_any_history` above), this must report
    a real, honest `coverage_ratio == 0.0` -- not `None` -- because durable
    history genuinely exists for this Stream, it just does not cover this
    window."""

    earlier_day = PERIOD_START - timedelta(days=3)
    _observe(repository, stream_id=STREAM_A, generation="gen-a", healthy_at=earlier_day)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-a",
        healthy_at=earlier_day + timedelta(hours=1),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=earlier_day + timedelta(hours=1, minutes=1))

    report = _report(repository)  # today's window, 3 days later than the recorded history

    assert report.coverage.monitored_seconds == pytest.approx(0.0)
    assert report.coverage.coverage_ratio == pytest.approx(0.0)
    assert report.coverage.history_available_from == earlier_day
    assert len(report.coverage.gaps) == 1


def test_observation_engine_coverage_present_without_any_legacy_supervisor_state(
    repository: ProductRepository,
) -> None:
    """Full-report-level proof, complementing tests/test_engine_runtime
    .py's own session-lifecycle-level version: real, correct Place Activity
    Report coverage requires zero legacy `StreamRuntimeCheckpointModel`/
    armed `StreamMonitoringPolicyModel` state at any point."""

    assert repository.list_enabled_monitoring_candidates(limit=10) == []

    _observe(repository, stream_id=STREAM_A, generation="gen-a", healthy_at=PERIOD_START)
    _observe(
        repository, stream_id=STREAM_A, generation="gen-a",
        healthy_at=PERIOD_START + timedelta(hours=1),
    )
    _stop_observing(repository, stream_id=STREAM_A, now=PERIOD_START + timedelta(hours=1, minutes=1))

    report = _report(repository)

    assert report.coverage.coverage_ratio == pytest.approx(1 / 24)
    assert repository.list_enabled_monitoring_candidates(limit=10) == []
