"""Gate C -- Meaningful Change Detection / Baseline Comparison v1:
repository/API integration coverage (see
docs/meaningful-change-detection-contract.md).

Complements `tests/test_place_change_summary.py`'s pure-domain coverage of
`mockingbird.analytics.place_change_summary` with the real integration path:
durable SQLite state, `ProductRepository.place_activity_report`/
`wildlife_journal_overview`/`wildlife_journal_history`, and their HTTP
routes. Confirmed truth is established through the real `create_review_
label`/`create_species_suggestion`/`revise_visit_review` write paths,
matching `tests/test_historical_baseline_repository.py`'s own established
convention -- never by hand-setting `VisitModel.reviewed_label`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.analytics.place_change_summary import (
    RECENT_WINDOW_USABLE_DAYS,
    REFERENCE_WINDOW_USABLE_DAYS,
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

SOURCE_ID = "source-place-change"
ARCHIVED_SOURCE_ID = "source-place-change-archived"
STREAM_A = "stream-place-change-a"
ARCHIVED_STREAM = "stream-place-change-archived"
ZONE_FEEDER = "zone-place-change-feeder"

# "Today" for these tests -- comfortably far from the schema's own seeded
# demo content so distinct-day counts stay exact.
PERIOD_START = datetime(2026, 8, 21, 0, tzinfo=UTC)
PERIOD_END = PERIOD_START + timedelta(days=1)

USABLE_HOURS = 2.0  # clears USABLE_DAY_MONITORED_SECONDS_THRESHOLD exactly


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
                        name="Place change camera",
                        kind="manual_upload",
                        status="connected",
                        description="Focused Gate C fixture.",
                    ),
                    CameraSourceModel(
                        id=ARCHIVED_SOURCE_ID,
                        name="Retired place change camera",
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
                        name="Yard stream",
                        description="Focused Gate C fixture.",
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
                    title=f"Gate C fixture {visit_id}",
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
    repository: ProductRepository, *, day: datetime, stream_id: str = STREAM_A, hours: float = USABLE_HOURS
) -> None:
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


def _add_full_valid_baseline(repository: ProductRepository, *, end_at: datetime = PERIOD_START) -> None:
    """21 consecutive usable days (7 recent + 14 reference), fresh and
    contiguous, ending at (and including) `end_at`'s own date -- the
    smallest fixture that clears Gate C's own `is_valid` gate."""

    for offset in range(RECENT_WINDOW_USABLE_DAYS + REFERENCE_WINDOW_USABLE_DAYS):
        _add_usable_day(repository, day=end_at - timedelta(days=offset))


def _report(repository: ProductRepository, *, start_at=PERIOD_START, end_at=PERIOD_END, local_timezone=None):
    return repository.place_activity_report(
        PlaceActivityReportRequest(start_at=start_at, end_at=end_at), local_timezone=local_timezone
    )


def _change_status_for(report, label: str):
    [taxon] = [taxon for taxon in report.taxa if taxon.label == label]
    return taxon.change_status


# 1. Real installation's current ~6-usable-day history stays insufficient ----


def test_current_real_approximately_six_usable_day_history_yields_insufficient_baseline(
    repository: ProductRepository,
) -> None:
    """Requirement 17: the same real-data shape historical-baseline-
    maturity-contract.md's own retained local dev database was measured
    against (~6 usable days) must never produce a strong change claim --
    only "still building a baseline," a mandatory regression."""

    for offset in range(1, 7):  # 6 usable days, one short of RECENT_WINDOW_USABLE_DAYS (7)
        _add_usable_day(repository, day=PERIOD_START - timedelta(days=offset))
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=8), zone_id=ZONE_FEEDER)
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)

    assert report.historical_baseline.maturity == "developing"  # 6 usable days: developing, not established
    assert report.change_windows.is_valid is False
    assert report.change_windows.invalid_reason == "insufficient_baseline"
    assert report.overall_change_status.status == "building_baseline"
    assert _change_status_for(report, "northern_cardinal").status == "insufficient_baseline"


# 2. Established baseline, clearly higher recent presence -------------------


def test_established_baseline_with_clearly_higher_recent_presence_reads_higher(
    repository: ProductRepository,
) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]  # 5 of the 7 recent days
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(9, 12)]  # 3 of the 14 reference days
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)

    assert report.change_windows.is_valid is True
    status = _change_status_for(report, "northern_cardinal")
    assert status.recent_presence_days == 5
    assert status.reference_presence_days == 3
    assert status.status == "higher_recent_presence"
    assert report.overall_change_status.status == "more_activity_recorded"


# 3. Established baseline, clearly lower recent presence --------------------


def test_established_baseline_with_clearly_lower_recent_presence_reads_lower(
    repository: ProductRepository,
) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=0)]  # 1 of 7 recent days
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(7, 17)]  # 10 of 14 reference days
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)

    status = _change_status_for(report, "northern_cardinal")
    assert status.status == "lower_recent_presence"
    assert report.overall_change_status.status == "less_activity_recorded"


# 4. Similar presence reads no_supported_change ------------------------------


def test_similar_recent_and_reference_presence_reads_no_supported_change(
    repository: ProductRepository,
) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(4)]  # 4 of 7 (57%)
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(7, 15)]  # 8 of 14 (57%)
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    assert _change_status_for(report, "northern_cardinal").status == "no_supported_change"


# 5. One busy recent day does not imply a persistent increase ---------------


def test_one_busy_recent_day_does_not_imply_a_persistent_increase(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    for i in range(25):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=PERIOD_START + timedelta(hours=1, minutes=i))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    status = _change_status_for(report, "northern_cardinal")
    assert status.recent_presence_days == 1
    assert status.status == "no_supported_change"


# 6. Recent period with insufficient (stale) monitoring ----------------------


def test_recent_period_with_insufficient_monitoring_reads_insufficient_recent_coverage(
    repository: ProductRepository,
) -> None:
    """Requirement 8: deep historical depth exists, but the whole 21-day
    fixture is anchored well before "today" -- monitoring has recently
    lapsed, a materially different, more honest state than "still building
    a baseline"."""

    _add_full_valid_baseline(repository, end_at=PERIOD_START - timedelta(days=60))
    _add_visit(repository, visit_id="cardinal-1", at=PERIOD_START + timedelta(hours=1))
    _confirm(repository, visit_id="cardinal-1", label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    assert report.change_windows.is_valid is False
    assert report.change_windows.invalid_reason == "insufficient_recent_coverage"
    assert _change_status_for(report, "northern_cardinal").status == "insufficient_recent_coverage"
    assert report.overall_change_status.status == "insufficient_recent_coverage"


# 7. Provisional suggestion never changes status ------------------------------


def test_provisional_suggestion_does_not_change_status(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]
    for i, day in enumerate(recent_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")
    # A provisional suggestion on every single reference-window day -- must
    # never contribute a reference presence day.
    for offset in range(7, 21):
        day = PERIOD_START - timedelta(days=offset)
        visit_id = f"suggested-{offset}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=9))
        _suggest(repository, visit_id=visit_id, stream_id=STREAM_A, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    status = _change_status_for(report, "northern_cardinal")
    assert status.reference_presence_days == 0
    assert status.status == "no_supported_change"


# 8. Reviewed correction changes derived comparison --------------------------


def test_reviewed_correction_changes_derived_comparison(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(9, 12)]
    visit_ids = []
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"mislabeled-{i}"
        visit_ids.append(visit_id)
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="house_finch")

    before = _report(repository, local_timezone=UTC)
    assert _change_status_for(before, "house_finch").status == "higher_recent_presence"
    assert [taxon for taxon in before.taxa if taxon.label == "northern_cardinal"] == []

    for visit_id in visit_ids:
        _revise(repository, visit_id=visit_id, label="northern_cardinal")

    after = _report(repository, local_timezone=UTC)
    # The superseded label no longer carries a phantom change result.
    assert [taxon for taxon in after.taxa if taxon.label == "house_finch"] == []
    assert _change_status_for(after, "northern_cardinal").status == "higher_recent_presence"


# 9. Unresolved wildlife counts toward overall but never a named taxon ------


def test_unresolved_wildlife_counts_toward_overall_but_never_a_named_taxon(
    repository: ProductRepository,
) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(9, 12)]
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"unknown-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="unknown_bird")

    report = _report(repository, local_timezone=UTC)
    assert report.taxa == []  # no named taxon entry at all
    assert report.overall_change_status.recent_presence_days == 5
    assert report.overall_change_status.status == "more_activity_recorded"


# 10. Multiple simultaneous subject Visits count one taxon presence day -----


def test_multiple_subject_visits_in_one_event_count_one_presence_day(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
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
                        id=f"sibling-{i}",
                        event_id=shared_event_id,
                        subject_label="unknown_bird",
                        species_guess=None,
                        confidence=None,
                        reviewed_label=None,
                        review_status="needs_review",
                        representative_media_path=None,
                        zone_id=ZONE_FEEDER,
                        is_superseded=False,
                    )
                    for i in range(3)
                ]
            )
    for i in range(3):
        _confirm(repository, visit_id=f"sibling-{i}", label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    assert _change_status_for(report, "northern_cardinal").recent_presence_days == 1


# 11. Archived-Stream confirmations are excluded -----------------------------


def test_archived_stream_confirmations_are_excluded(repository: ProductRepository) -> None:
    for offset in range(RECENT_WINDOW_USABLE_DAYS + REFERENCE_WINDOW_USABLE_DAYS):
        _add_usable_day(repository, day=PERIOD_START - timedelta(days=offset), stream_id=ARCHIVED_STREAM)
    _add_visit(
        repository,
        visit_id="on-archived-stream",
        at=PERIOD_START + timedelta(hours=1),
        stream_id=ARCHIVED_STREAM,
    )
    _confirm(repository, visit_id="on-archived-stream", label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    assert report.change_windows.is_valid is False  # the archived Stream's exposure history never counts
    assert report.taxa == []


# 12. Local midnight boundary correctness (real repository/timezone path) ---


def test_local_midnight_boundary_correct_through_the_repository(repository: ProductRepository) -> None:
    eastern = ZoneInfo("America/New_York")
    day_two_local = datetime(2026, 8, 21, tzinfo=eastern)
    _add_full_valid_baseline(repository, end_at=day_two_local.astimezone(UTC))

    # 23:45 local the evening before day_two, and 00:15 local just after --
    # both distinct local calendar days despite 30 minutes of wall time.
    just_before_midnight = datetime(2026, 8, 20, 23, 45, tzinfo=eastern).astimezone(UTC)
    just_after_midnight = datetime(2026, 8, 21, 0, 15, tzinfo=eastern).astimezone(UTC)
    _add_visit(repository, visit_id="cardinal-before", at=just_before_midnight)
    _confirm(repository, visit_id="cardinal-before", label="northern_cardinal")
    _add_visit(repository, visit_id="cardinal-after", at=just_after_midnight)
    _confirm(repository, visit_id="cardinal-after", label="northern_cardinal")

    report = _report(
        repository,
        start_at=day_two_local.astimezone(UTC),
        end_at=day_two_local.astimezone(UTC) + timedelta(days=1),
        local_timezone=eastern,
    )
    # Both confirmations land within the 7-day recent window (2026-08-20 and
    # 2026-08-21 are both among the most recent 7 usable days) as two
    # distinct local presence days.
    assert _change_status_for(report, "northern_cardinal").recent_presence_days == 2


# 13. Deterministic regardless of row insertion order ------------------------


def test_deterministic_regardless_of_row_insertion_order(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in (4, 0, 2, 1, 3)]  # non-chronological
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in (11, 9, 10)]
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    report = _report(repository, local_timezone=UTC)
    status = _change_status_for(report, "northern_cardinal")
    assert status.recent_presence_days == 5
    assert status.reference_presence_days == 3
    assert status.status == "higher_recent_presence"


# 14. Today and Bird Log agree on the same per-label change status ----------


def test_today_and_bird_log_present_the_same_change_status(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(9, 12)]
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    # Both surfaces must be anchored to the *same* "now" for a fair
    # comparison -- place_activity_report anchors to its own period_end_at
    # (PERIOD_END); Bird Log anchors to "now" by convention.
    bird_log_now = PERIOD_START + timedelta(hours=12)

    # Deliberately no `local_timezone` override here (unlike every other
    # test in this file): `wildlife_journal_overview`/`wildlife_journal_
    # history` have no such override (they always use the host's own
    # resolved zone via `now.astimezone()`, by design -- see docs/
    # historical-baseline-maturity-contract.md's "Timezone correctness"),
    # so Today must use that same host zone here for a fair, consistent
    # cross-surface comparison rather than being pinned to a different one.
    report = _report(repository)
    overview = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest(), now=bird_log_now)
    history = repository.wildlife_journal_history(
        "northern_cardinal", WildlifeJournalHistoryRequest(preset="all_time"), now=bird_log_now
    )

    today_status = _change_status_for(report, "northern_cardinal")
    [overview_entry] = [entry for entry in overview.labels if entry.label == "northern_cardinal"]

    assert today_status.status == "higher_recent_presence"
    assert overview_entry.change_status is not None
    assert overview_entry.change_status.status == today_status.status
    assert overview_entry.change_status.recent_presence_days == today_status.recent_presence_days
    assert history is not None
    assert history.change_status is not None
    assert history.change_status.status == today_status.status


# 15. API round trip exposes the new fields end to end -----------------------


def test_api_round_trip_exposes_change_detection_fields(repository: ProductRepository) -> None:
    _add_full_valid_baseline(repository)
    recent_days = [PERIOD_START - timedelta(days=offset) for offset in range(5)]
    reference_days = [PERIOD_START - timedelta(days=offset) for offset in range(9, 12)]
    for i, day in enumerate(recent_days + reference_days):
        visit_id = f"cardinal-{i}"
        _add_visit(repository, visit_id=visit_id, at=day + timedelta(hours=10))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal")

    client = LegacyAuthenticatedSyncTestClient(app)

    report_response = client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": PERIOD_START.isoformat(), "end_at": PERIOD_END.isoformat()},
    )
    assert report_response.status_code == 200
    body = report_response.json()
    assert body["change_windows"]["is_valid"] is True
    assert body["overall_change_status"]["status"] == "more_activity_recorded"
    [taxon] = body["taxa"]
    assert taxon["change_status"]["status"] == "higher_recent_presence"

    journal_response = client.get("/api/bird-log/journal")
    assert journal_response.status_code == 200
    journal_body = journal_response.json()
    [label_summary] = [entry for entry in journal_body["labels"] if entry["label"] == "northern_cardinal"]
    assert label_summary["change_status"]["status"] == "higher_recent_presence"

    label_history_response = client.get("/api/bird-log/journal/northern_cardinal")
    assert label_history_response.status_code == 200
    label_history_body = label_history_response.json()
    assert label_history_body["change_status"]["status"] == "higher_recent_presence"
