"""Historical Baseline Maturity + New/Regular Species v1: repository/API
integration coverage (see docs/historical-baseline-maturity-contract.md).

Complements `tests/test_historical_baseline.py`'s pure-domain coverage of
`mockingbird.analytics.historical_baseline` with the real integration path:
durable SQLite state, `ProductRepository.place_activity_report`/
`wildlife_journal_overview`/`wildlife_journal_history`, and their HTTP
routes. Confirmed truth is established through the real `create_review_
label`/`create_species_suggestion`/`revise_visit_review` write paths
wherever the scenario is about truth precedence, matching `tests/
test_place_activity_report_repository.py`'s own established convention --
never by hand-setting `VisitModel.reviewed_label`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from mockingbird.analytics.historical_baseline import (
    MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR,
    MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE,
    USABLE_DAY_MONITORED_SECONDS_THRESHOLD,
)
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    PlaceActivityReportRequest,
    ReviewCorrectionCreate,
    SpeciesSuggestionCreateRequest,
    VisitReviewRevisionCreate,
    WildlifeJournalHistoryRequest,
    WildlifeJournalOverviewRequest,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

SOURCE_ID = "source-historical-baseline"
ARCHIVED_SOURCE_ID = "source-historical-baseline-archived"
STREAM_A = "stream-historical-baseline-a"
STREAM_B = "stream-historical-baseline-b"
ARCHIVED_STREAM = "stream-historical-baseline-archived"
ZONE_FEEDER = "zone-historical-baseline-feeder"

# "Today" for these tests -- comfortably far from the schema's own seeded
# demo content so distinct-day counts stay exact.
PERIOD_START = datetime(2026, 8, 21, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)

USABLE_HOURS = USABLE_DAY_MONITORED_SECONDS_THRESHOLD / 3600.0


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
                        name="Historical baseline camera",
                        kind="manual_upload",
                        status="connected",
                        description="Focused historical-baseline fixture.",
                    ),
                    CameraSourceModel(
                        id=ARCHIVED_SOURCE_ID,
                        name="Retired historical baseline camera",
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
                        description="Focused historical-baseline fixture.",
                        is_live=False,
                    ),
                    StreamModel(
                        id=STREAM_B,
                        source_id=SOURCE_ID,
                        name="Yard stream B",
                        description="Focused historical-baseline fixture.",
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
            session.add(
                ZoneModel(
                    id=ZONE_FEEDER,
                    stream_id=STREAM_A,
                    name="Feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                    monitoring_policy_json=None,
                )
            )
    return repository


def _add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    at: datetime,
    stream_id: str = STREAM_A,
    zone_id: str | None = None,
) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Historical baseline fixture {visit_id}",
                    event_type="manual_media_import",
                    started_at=at,
                    ended_at=at + timedelta(seconds=20),
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
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _revise(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    """A real, later human correction of an already-reviewed Visit -- the
    concrete real-world shape of requirement #4 ("corrected review updates
    authoritative history")."""

    with repository.session_factory() as session:
        token = repository._review_state_token(session, "visit", visit_id)
    repository.revise_visit_review(
        visit_id,
        VisitReviewRevisionCreate(
            label=label,
            expected_state_token=token,
            idempotency_key=f"revise-{visit_id}-{label}",
            review_origin="human",
        ),
    )


def _suggest(repository: ProductRepository, *, visit_id: str, stream_id: str, label: str) -> None:
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


def _add_usable_day(
    repository: ProductRepository,
    *,
    day: datetime,
    stream_id: str = STREAM_A,
    hours: float = USABLE_HOURS,
) -> None:
    """One durable monitoring interval clearing the usable-day bar,
    starting at `day`'s own midnight."""

    interval_id = f"exposure-{stream_id}-{day.date().isoformat()}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id,
                    stream_id=stream_id,
                    source_id=SOURCE_ID,
                    runtime_generation_id=f"generation-{interval_id}",
                    started_at=day,
                    last_confirmed_fresh_at=day + timedelta(hours=hours),
                    ended_at=day + timedelta(hours=hours),
                    close_reason="provider_failure",
                    created_at=day,
                    updated_at=day + timedelta(hours=hours),
                )
            )


def _report(repository: ProductRepository, *, start_at=PERIOD_START, end_at=PERIOD_END, local_timezone=None):
    return repository.place_activity_report(
        PlaceActivityReportRequest(start_at=start_at, end_at=end_at),
        local_timezone=local_timezone,
    )


def _historical_status_for(report, label: str):
    [taxon] = [taxon for taxon in report.taxa if taxon.label == label]
    return taxon.historical_status


# 1. First reviewed species record, immature baseline ------------------------


def test_first_confirmed_species_with_no_prior_history_reads_first_record(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=8), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    report = _report(repository)

    assert report.historical_baseline.maturity == "insufficient"
    status = _historical_status_for(report, "northern_cardinal")
    assert status is not None
    assert status.status == "first_record"
    assert status.total_confirmed_count == 1


# 2. First reviewed species record, established baseline ---------------------


def test_first_confirmed_species_with_established_baseline_reads_new(
    repository: ProductRepository,
) -> None:
    for offset in range(1, 1 + MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE):
        _add_usable_day(repository, day=PERIOD_START - timedelta(days=offset))
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=8), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    report = _report(repository)

    assert report.historical_baseline.maturity == "established"
    assert report.historical_baseline.usable_day_count == MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE
    status = _historical_status_for(report, "northern_cardinal")
    assert status.status == "new"


# 3. Provisional suggestion never creates a historical first record ----------


def test_provisional_suggestion_never_creates_historical_first_record(
    repository: ProductRepository,
) -> None:
    earlier_suggested_only = PERIOD_START - timedelta(days=20)
    later_confirmed = PERIOD_START + timedelta(hours=1)

    _add_visit(repository, visit_id="suggested-only", at=earlier_suggested_only)
    _suggest(repository, visit_id="suggested-only", stream_id=STREAM_A, label="northern_cardinal")

    _add_visit(repository, visit_id="confirmed", at=later_confirmed)
    _confirm(repository, visit_id="confirmed", label="northern_cardinal")

    report = _report(repository)

    status = _historical_status_for(report, "northern_cardinal")
    assert status.first_confirmed_at == later_confirmed
    assert status.total_confirmed_count == 1
    assert status.status == "first_record"  # today's confirmation IS the real first record


# 4. Corrected review updates authoritative history ---------------------------


def test_corrected_review_updates_authoritative_history(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="mislabeled", at=PERIOD_START + timedelta(hours=2))
    _confirm(repository, visit_id="mislabeled", label="house_finch")
    _revise(repository, visit_id="mislabeled", label="northern_cardinal")

    report = _report(repository)

    assert _historical_status_for(report, "northern_cardinal") is not None
    assert _historical_status_for(report, "northern_cardinal").total_confirmed_count == 1
    # The superseded original label must not retain a phantom historical
    # record for a correction that was never real.
    house_finch_entries = [taxon for taxon in report.taxa if taxon.label == "house_finch"]
    assert house_finch_entries == []


# 5. Many Visits in one day does not automatically become regular ------------


def test_many_visits_in_one_day_does_not_become_regular(repository: ProductRepository) -> None:
    _add_usable_day(repository, day=PERIOD_START)
    for i in range(20):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=PERIOD_START + timedelta(hours=1, minutes=i))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository)

    status = _historical_status_for(report, "northern_cardinal")
    assert status.total_confirmed_count == 20
    assert status.distinct_confirmed_usable_days == 1
    assert status.status != "regular"


# 6. Multiple usable days makes a species regular -----------------------------


def test_species_seen_across_usable_days_becomes_regular(repository: ProductRepository) -> None:
    days = [PERIOD_START - timedelta(days=offset) for offset in (10, 5, 1)]
    for i, day in enumerate(days):
        _add_usable_day(repository, day=day)
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=1))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    # A taxon's `historical_status` only appears on `report.taxa` when it
    # also has activity *within today's own period* -- exactly the
    # milestone's own "6 confirmed visits today, Regular here" shape, where
    # the regular badge rides alongside today's real Visit count, not a
    # standing roster of every historically-regular species regardless of
    # whether it showed up today (that is Bird Log's job -- see requirement
    # 14's cross-surface test).
    _add_visit(repository, visit_id="cardinal-today", at=PERIOD_START + timedelta(hours=8))
    _confirm(repository, visit_id="cardinal-today", label="northern_cardinal")

    report = _report(repository)

    status = _historical_status_for(report, "northern_cardinal")
    assert status.distinct_confirmed_usable_days == MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR
    assert status.status == "regular"


# 7. Low-coverage days do not mature the baseline or make a species regular --


def test_low_coverage_days_do_not_count_toward_regularity(repository: ProductRepository) -> None:
    days = [PERIOD_START - timedelta(days=offset) for offset in (10, 5, 1)]
    # Only the first day gets real, usable (>= 2h) monitoring; the other
    # two get a real but far-too-short interval (3 minutes).
    _add_usable_day(repository, day=days[0])
    for day in days[1:]:
        _add_usable_day(repository, day=day, hours=3 / 60)

    for i, day in enumerate(days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=1))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-today", at=PERIOD_START + timedelta(hours=8))
    _confirm(repository, visit_id="cardinal-today", label="northern_cardinal")

    report = _report(repository)

    status = _historical_status_for(report, "northern_cardinal")
    assert status.distinct_confirmed_days == 4  # the 3 fixture days plus today
    # Only days[0] ever got a real, usable (>= 2h) interval -- today itself
    # has no exposure interval seeded at all, matching requirement 8.
    assert status.distinct_confirmed_usable_days == 1
    assert status.status != "regular"
    assert report.historical_baseline.usable_day_count == 1
    assert report.historical_baseline.maturity == "insufficient"


# 8. Zero-monitoring days do not count as usable days -------------------------


def test_zero_monitoring_day_does_not_count_as_usable(repository: ProductRepository) -> None:
    # No MonitoringExposureIntervalModel row is ever created for today --
    # a sighting can happen (and be confirmed) with zero durable monitoring
    # history, and that must not silently count as a usable day.
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    report = _report(repository)

    assert report.historical_baseline.usable_day_count == 0
    assert _historical_status_for(report, "northern_cardinal").distinct_confirmed_usable_days == 0


# 9. Unresolved wildlife does not create named history -------------------------


def test_unresolved_wildlife_creates_no_named_history(repository: ProductRepository) -> None:
    _add_usable_day(repository, day=PERIOD_START)
    _add_visit(repository, visit_id="unknown-1", at=PERIOD_START + timedelta(hours=1))
    _confirm(repository, visit_id="unknown-1", label="unknown_bird")

    report = _report(repository)

    # A confirmed-but-unresolved wildlife Visit is real, counted activity --
    # just never a named taxon's historical record.
    assert report.confirmed_species_unresolved_visit_count == 1
    assert report.historical_baseline.distinct_taxa_count == 0
    assert report.taxa == []


# 10. Multiple subject Visits in one Event count independently ----------------


def test_multiple_subject_visits_in_one_event_count_independently(
    repository: ProductRepository,
) -> None:
    """Multi-Subject Visit Assembly: two sibling Visits under one Event
    (simultaneous distinct subjects) must each contribute their own taxon's
    history independently -- never collapsed into one occurrence."""

    _add_usable_day(repository, day=PERIOD_START)
    simultaneous = PERIOD_START + timedelta(hours=9)
    shared_event_id = "shared-multi-subject-event"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=shared_event_id,
                    stream_id=STREAM_A,
                    title="Multi-subject fixture",
                    event_type="manual_media_import",
                    started_at=simultaneous,
                    ended_at=simultaneous + timedelta(seconds=20),
                    primary_zone_id=ZONE_FEEDER,
                    review_status="needs_review",
                )
            )
            session.add_all(
                [
                    VisitModel(
                        id="sibling-cardinal",
                        event_id=shared_event_id,
                        subject_label="unknown_bird",
                        species_guess=None,
                        confidence=None,
                        reviewed_label=None,
                        review_status="needs_review",
                        representative_media_path=None,
                        zone_id=ZONE_FEEDER,
                        is_superseded=False,
                    ),
                    VisitModel(
                        id="sibling-finch",
                        event_id=shared_event_id,
                        subject_label="unknown_bird",
                        species_guess=None,
                        confidence=None,
                        reviewed_label=None,
                        review_status="needs_review",
                        representative_media_path=None,
                        zone_id=ZONE_FEEDER,
                        is_superseded=False,
                    ),
                ]
            )
    _confirm(repository, visit_id="sibling-cardinal", label="northern_cardinal")
    _confirm(repository, visit_id="sibling-finch", label="house_finch")

    report = _report(repository)

    assert _historical_status_for(report, "northern_cardinal").total_confirmed_count == 1
    assert _historical_status_for(report, "house_finch").total_confirmed_count == 1


# 11. Local midnight boundary correctness (real repository/timezone path) ----


def test_local_midnight_boundary_correct_through_the_repository(
    repository: ProductRepository,
) -> None:
    eastern = ZoneInfo("America/New_York")
    day_one_local = datetime(2026, 8, 19, tzinfo=eastern)
    day_two_local = datetime(2026, 8, 20, tzinfo=eastern)
    _add_usable_day(repository, day=day_one_local.astimezone(UTC))
    _add_usable_day(repository, day=day_two_local.astimezone(UTC))

    # 23:45 local on day one, 00:15 local on day two -- both real, distinct
    # local calendar days despite being 30 minutes apart in wall time.
    just_before_midnight = datetime(2026, 8, 19, 23, 45, tzinfo=eastern).astimezone(UTC)
    just_after_midnight = datetime(2026, 8, 20, 0, 15, tzinfo=eastern).astimezone(UTC)
    _add_visit(repository, visit_id="cardinal-before", at=just_before_midnight)
    _confirm(repository, visit_id="cardinal-before", label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-after", at=just_after_midnight)
    _confirm(repository, visit_id="cardinal-after", label="northern_cardinal")

    # The report period is exactly local day two (Eastern midnight to
    # midnight) -- it contains "cardinal-after" (00:15 local) so the taxon
    # actually appears on today's report, matching real Today-report usage,
    # while "cardinal-before" (23:45 local the *prior* day) still
    # contributes to the accumulated distinct-day history via the bounded
    # window without itself falling in today's period.
    report = _report(
        repository,
        start_at=day_two_local.astimezone(UTC),
        end_at=day_two_local.astimezone(UTC) + timedelta(days=1),
        local_timezone=eastern,
    )

    status = _historical_status_for(report, "northern_cardinal")
    assert status.distinct_confirmed_days == 2


# 12. Deterministic regardless of database row insertion order ---------------


def test_deterministic_regardless_of_row_insertion_order(repository: ProductRepository) -> None:
    days = [PERIOD_START - timedelta(days=offset) for offset in (1, 5, 10)]  # non-chronological
    for day in days:
        _add_usable_day(repository, day=day)
    # Insert Visits deliberately out of chronological order.
    for i, day in enumerate([days[2], days[0], days[1]]):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=1))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-today", at=PERIOD_START + timedelta(hours=8))
    _confirm(repository, visit_id="cardinal-today", label="northern_cardinal")

    report = _report(repository)

    status = _historical_status_for(report, "northern_cardinal")
    assert status.distinct_confirmed_usable_days == MIN_DISTINCT_USABLE_DAYS_FOR_REGULAR
    assert status.status == "regular"


# 13. Reviewed truth supersedes provisional state on the same Visit ----------


def test_reviewed_truth_supersedes_provisional_on_same_visit(repository: ProductRepository) -> None:
    at = PERIOD_START + timedelta(hours=3)
    _add_visit(repository, visit_id="v1", at=at)
    _suggest(repository, visit_id="v1", stream_id=STREAM_A, label="house_finch")
    _confirm(repository, visit_id="v1", label="northern_cardinal")

    report = _report(repository)

    assert _historical_status_for(report, "northern_cardinal").total_confirmed_count == 1
    assert [taxon for taxon in report.taxa if taxon.label == "house_finch"] == []


# 14. Today's concise status matches the deeper Bird Log computation ---------


def test_today_status_matches_bird_log_regularity(repository: ProductRepository) -> None:
    days = [PERIOD_START - timedelta(days=offset) for offset in (10, 5, 1)]
    for i, day in enumerate(days):
        _add_usable_day(repository, day=day)
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=1))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-today", at=PERIOD_START + timedelta(hours=8))
    _confirm(repository, visit_id="cardinal-today", label="northern_cardinal")

    # Both surfaces must be anchored to the *same* "now" for a fair
    # comparison -- place_activity_report anchors to its own period_end_at
    # (PERIOD_END); Bird Log anchors to "now" by convention (see
    # `wildlife_journal_overview`'s own docstring/comment), so this test
    # supplies the identical instant explicitly rather than relying on the
    # real wall clock happening to agree with PERIOD_END.
    bird_log_now = PERIOD_START + timedelta(hours=12)

    report = _report(repository)
    overview = repository.wildlife_journal_overview(
        WildlifeJournalOverviewRequest(), now=bird_log_now
    )
    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(preset="all_time"), now=bird_log_now
    )

    today_status = _historical_status_for(report, "northern_cardinal")
    [overview_entry] = [entry for entry in overview.labels if entry.label == "northern_cardinal"]

    assert today_status.status == "regular"
    assert overview_entry.is_regular is True
    assert overview_entry.distinct_confirmed_usable_days == today_status.distinct_confirmed_usable_days
    assert history is not None
    assert history.is_regular is True
    assert history.distinct_confirmed_usable_days == today_status.distinct_confirmed_usable_days
    assert history.baseline_maturity == overview.baseline_maturity


# 15. Archived-Stream history is excluded, matching place_activity_report's --
#     own existing non-archived-Streams scoping (a deliberate, documented
#     choice -- see docs/historical-baseline-maturity-contract.md).


def test_archived_stream_confirmations_are_excluded_from_historical_facts(
    repository: ProductRepository,
) -> None:
    _add_usable_day(repository, day=PERIOD_START, stream_id=ARCHIVED_STREAM)
    _add_visit(repository, visit_id="on-archived-stream", at=PERIOD_START + timedelta(hours=1), stream_id=ARCHIVED_STREAM)
    _confirm(repository, visit_id="on-archived-stream", label="northern_cardinal")

    report = _report(repository)

    assert report.historical_baseline.distinct_taxa_count == 0
    assert report.historical_baseline.usable_day_count == 0
    assert report.taxa == []


# 16. API round trip exposes the new fields end to end ------------------------


def test_api_round_trip_exposes_historical_baseline_and_bird_log_regularity(
    repository: ProductRepository,
) -> None:
    for offset in range(1, 1 + MIN_USABLE_DAYS_FOR_ESTABLISHED_BASELINE):
        _add_usable_day(repository, day=PERIOD_START - timedelta(days=offset))
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=8))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    client = TestClient(app)

    report_response = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat(), "end_at": PERIOD_END.isoformat()},
    )
    assert report_response.status_code == 200
    body = report_response.json()
    assert body["historical_baseline"]["maturity"] == "established"
    [taxon] = body["taxa"]
    assert taxon["historical_status"]["status"] == "new"

    journal_response = client.get("/api/bird-log/journal")
    assert journal_response.status_code == 200
    journal_body = journal_response.json()
    assert journal_body["baseline_maturity"] == "established"
    [label_summary] = [
        entry for entry in journal_body["labels"] if entry["label"] == "northern_cardinal"
    ]
    assert "distinct_confirmed_usable_days" in label_summary
    assert "is_regular" in label_summary

    label_history_response = client.get("/api/bird-log/journal/northern_cardinal")
    assert label_history_response.status_code == 200
    label_history_body = label_history_response.json()
    assert label_history_body["baseline_maturity"] == "established"
    assert "distinct_confirmed_usable_days" in label_history_body
    assert "is_regular" in label_history_body
