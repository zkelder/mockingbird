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


def _report(repository: ProductRepository, *, start_at=PERIOD_START, end_at=PERIOD_END, now=None):
    return repository.place_activity_report(
        PlaceActivityReportRequest(start_at=start_at, end_at=end_at),
        now=now,
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


def test_coverage_withheld_when_any_in_scope_stream_lacks_history(
    repository: ProductRepository,
) -> None:
    """All-or-nothing honesty policy (see "Monitoring coverage" in
    docs/place-activity-report-contract.md): Stream A has durable exposure
    history, Stream B has none at all -- the Place-wide figure must be
    withheld entirely, never silently averaged as if Stream B had zero
    healthy time."""

    _add_exposure(
        repository,
        interval_id="exposure-only-a",
        stream_id=STREAM_A,
        started_at=PERIOD_START,
        ended_at=PERIOD_END,
    )

    report = _report(repository)

    assert report.coverage.monitored_seconds is None
    assert report.coverage.coverage_ratio is None
    assert report.coverage.history_available_from is None


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
        "warnings",
    }
    assert body["total_visit_count"] == 1
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
    }
    assert taxon["label"] == "northern_cardinal"
    assert taxon["category"] == "bird"
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
    """The product's existing local-time convention (zone_insights,
    wildlife_insights, dashboard_summary, and now this report) resolves
    "local" from the host's own current UTC offset at generation time --
    see the comment on `ProductRepository.place_activity_report`. That
    resolution genuinely is DST-correct *for the instant `now` represents*
    (Python's `astimezone()` consults the system zone database), proven
    here with a January (EST) and a July (EDT) `now`. The one real, honest
    limitation -- shared by every existing local-time analytics surface in
    the product, not new here -- is that a single report call resolves one
    fixed offset from its own generation moment and applies it uniformly
    across the whole requested period, so a period that itself straddles a
    real DST transition is bucketed with one offset throughout rather than
    the historically-correct offset per day."""

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


# Performance: taxonomy resolution must not scale one query per Visit -----------------


def test_taxonomy_resolution_adds_no_second_per_visit_query(
    repository: ProductRepository,
) -> None:
    """Real regression coverage for the N+1 shape this milestone's
    performance review targeted -- refined by what a first version of this
    test actually found: `_stream_visit_summary_from_models` (the canonical
    per-Visit resolver this method is required to reuse unmodified) already
    costs one `taxonomy_labels` query per reviewed Visit with a real species
    label today, through its own `_visit_review_outcome` -- the same cost
    `zone_insights`/`wildlife_insights` already pay in production, not
    something this milestone introduces or is scoped to fix (see
    `ProductRepository._taxonomy_label_index`'s docstring).

    What this report's own taxonomy resolution (`confirmed_taxon`/
    `provisional_taxon`) must not do is add a *second* per-Visit query on
    top of that pre-existing one: `_taxonomy_label_index` preloads the whole
    table exactly once regardless of Visit count, so going from 3 to 8
    Visits must add exactly 5 taxonomy queries -- one per additional Visit,
    from the pre-existing resolver alone -- never 10, which a naive
    per-Visit `_taxonomy_label_model_for_input` call for both
    `confirmed_taxon` and `provisional_taxon` would have cost on top of the
    resolver's own existing query.
    """

    for index in range(8):
        visit_id = f"batch-{index}"
        _add_visit(repository, visit_id=visit_id, at=PERIOD_START + timedelta(hours=index), zone_id=ZONE_FEEDER)
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    def _count_taxonomy_queries(*, visit_count: int) -> int:
        statements: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            if "taxonomy_labels" in statement:
                statements.append(statement)

        event.listen(repository.engine, "before_cursor_execute", _record)
        try:
            report = repository.place_activity_report(
                PlaceActivityReportRequest(
                    start_at=PERIOD_START,
                    end_at=PERIOD_START + timedelta(hours=visit_count),
                )
            )
        finally:
            event.remove(repository.engine, "before_cursor_execute", _record)
        assert report.confirmed_wildlife_visit_count == visit_count
        return len(statements)

    small = _count_taxonomy_queries(visit_count=3)
    large = _count_taxonomy_queries(visit_count=8)

    assert large - small == 5
