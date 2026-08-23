from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.conftest import LegacyAuthenticatedSyncTestClient
from sqlalchemy import event, func, select

from mockingbird.analytics.zone_insights import (
    TimeInterval,
    interval_seconds,
    merge_intervals,
    subtract_intervals,
)
from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    ActivityLibrarySearchRequest,
    SpeciesSuggestionCreateRequest,
    ZoneInsightsRequest,
)
from mockingbird.repository.product_repository import ProductRepository, SpeciesSuggestionModel
from mockingbird.storage.models import (
    CameraHealthIncidentModel,
    CameraSourceModel,
    MonitoringExposureIntervalModel,
    EventModel,
    ReviewLabelModel,
    StreamModel,
    StreamRuntimeCheckpointModel,
    TaxonomyLabelModel,
    VisitModel,
    ZoneModel,
)


SOURCE_ID = "source-zone-insights"
STREAM_ID = "stream-zone-insights"
DISABLED_STREAM_ID = "stream-zone-insights-disabled"
FEEDER_ZONE_ID = "zone-zone-insights-feeder"
YARD_ZONE_ID = "zone-zone-insights-yard"
DISABLED_ZONE_ID = "zone-zone-insights-disabled"
RANGE_START = datetime(2026, 7, 1, 9, tzinfo=UTC)
RANGE_END = datetime(2026, 7, 1, 13, tzinfo=UTC)


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
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Zone insight camera",
                    kind="manual_upload",
                    status="connected",
                    description="Focused Zone Insights fixture.",
                )
            )
            session.add_all(
                [
                    StreamModel(
                        id=STREAM_ID,
                        source_id=SOURCE_ID,
                        name="Feeder stream",
                        description="Focused Zone Insights fixture.",
                        is_live=False,
                    ),
                    StreamModel(
                        id=DISABLED_STREAM_ID,
                        source_id=SOURCE_ID,
                        name="Disabled stream",
                        description="No healthy checkpoint fixture.",
                        is_live=False,
                    ),
                ]
            )
            session.add_all(
                [
                    ZoneModel(
                        id=FEEDER_ZONE_ID,
                        stream_id=STREAM_ID,
                        name="North feeder",
                        zone_type="feeder",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                    ZoneModel(
                        id=YARD_ZONE_ID,
                        stream_id=STREAM_ID,
                        name="North yard",
                        zone_type="yard",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                    ZoneModel(
                        id=DISABLED_ZONE_ID,
                        stream_id=DISABLED_STREAM_ID,
                        name="Disabled feeder",
                        zone_type="feeder",
                        polygon_json="[]",
                        is_active=True,
                        monitoring_policy_json=None,
                    ),
                ]
            )
            session.add(
                StreamRuntimeCheckpointModel(
                    stream_id=STREAM_ID,
                    observed_policy_revision=1,
                    actual_state="stopped",
                    app_instance_id=None,
                    runtime_generation_id=None,
                    last_start_attempt_at=RANGE_START,
                    last_healthy_frame_at=RANGE_END - timedelta(minutes=2),
                    last_evidence_persisted_at=None,
                    last_evidence_failure_at=None,
                    evidence_failure_code=None,
                    last_clean_stop_at=RANGE_END - timedelta(hours=1),
                    last_failure_at=None,
                    failure_code=None,
                    consecutive_failure_count=0,
                    next_retry_at=None,
                    last_stop_reason="manual_camera_stop",
                    start_count=1,
                    failure_count=0,
                    evidence_handoff_count=0,
                    safety_hold_active=False,
                    updated_at=RANGE_END,
                )
            )
            # Durable intervals already exclude unhealthy/recovering time.
            session.add(
                MonitoringExposureIntervalModel(
                    id="exposure-zone-insights",
                    stream_id=STREAM_ID,
                    source_id=SOURCE_ID,
                    runtime_generation_id="zone-insights-generation",
                    started_at=RANGE_START,
                    last_confirmed_fresh_at=RANGE_START + timedelta(hours=2),
                    ended_at=RANGE_START + timedelta(hours=2),
                    close_reason="provider_failure",
                    created_at=RANGE_START,
                    updated_at=RANGE_START + timedelta(hours=2),
                )
            )
            # Camera Health remains operational history; it no longer mutates durable exposure.
            session.add_all(
                [
                    CameraHealthIncidentModel(
                        id="incident-zone-insights-a",
                        stream_id=STREAM_ID,
                        category="camera_unavailable",
                        severity="warning",
                        started_at=RANGE_START + timedelta(minutes=30),
                        updated_at=RANGE_START + timedelta(hours=1, minutes=30),
                        resolved_at=RANGE_START + timedelta(hours=1, minutes=30),
                        reason_code="camera_unavailable",
                        condition_fingerprint="zone-insights-a",
                        next_retry_at=None,
                        occurrence_count=1,
                        alert_id=None,
                    ),
                    CameraHealthIncidentModel(
                        id="incident-zone-insights-b",
                        stream_id=STREAM_ID,
                        category="recovery_exhausted",
                        severity="warning",
                        started_at=RANGE_START + timedelta(hours=1),
                        updated_at=RANGE_START + timedelta(hours=1, minutes=15),
                        resolved_at=RANGE_START + timedelta(hours=1, minutes=15),
                        reason_code="camera_unavailable",
                        condition_fingerprint="zone-insights-b",
                        next_retry_at=None,
                        occurrence_count=1,
                        alert_id=None,
                    ),
                ]
            )
    return repository


def _add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    zone_id: str,
    started_at: datetime,
    reviewed_label: str | None = None,
    review_status: str = "needs_review",
    is_superseded: bool = False,
    duration_seconds: int = 20,
) -> None:
    event_id = f"event-{visit_id}"
    stream_id = DISABLED_STREAM_ID if zone_id == DISABLED_ZONE_ID else STREAM_ID
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Zone Insights {visit_id}",
                    event_type="manual_media_import",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=duration_seconds),
                    primary_zone_id=zone_id,
                    review_status=review_status,
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=reviewed_label,
                    review_status=review_status,
                    representative_media_path=None,
                    zone_id=zone_id,
                    is_superseded=is_superseded,
                )
            )


def _counts(repository: ProductRepository) -> dict[str, int]:
    with repository.session_factory() as session:
        return {
            "events": session.scalar(select(func.count(EventModel.id))) or 0,
            "visits": session.scalar(select(func.count(VisitModel.id))) or 0,
            "labels": session.scalar(select(func.count(ReviewLabelModel.id))) or 0,
            "suggestions": session.scalar(select(func.count(SpeciesSuggestionModel.id))) or 0,
        }


def test_interval_helpers_merge_overlaps_without_double_counting() -> None:
    first = TimeInterval(RANGE_START, RANGE_START + timedelta(hours=2))
    second = TimeInterval(RANGE_START + timedelta(hours=1), RANGE_START + timedelta(hours=3))
    blocked = TimeInterval(
        RANGE_START + timedelta(minutes=30),
        RANGE_START + timedelta(hours=1, minutes=30),
    )

    assert merge_intervals([first, second]) == [
        TimeInterval(RANGE_START, RANGE_START + timedelta(hours=3)),
    ]
    assert interval_seconds(subtract_intervals([first, second], [blocked])) == 2 * 60 * 60


def test_zone_insights_use_only_truth_and_return_auditable_denominator(
    repository: ProductRepository,
) -> None:
    _add_visit(repository, visit_id="confirmed-cardinal", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=5), reviewed_label="northern_cardinal", review_status="reviewed", duration_seconds=20)
    _add_visit(repository, visit_id="confirmed-blue-jay", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=10), reviewed_label="blue_jay", review_status="reviewed", duration_seconds=40)
    _add_visit(repository, visit_id="unresolved-suggestion", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=15))
    _add_visit(repository, visit_id="blank", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=20), reviewed_label="blank", review_status="reviewed")
    _add_visit(repository, visit_id="squirrel", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=25), reviewed_label="squirrel", review_status="reviewed")
    _add_visit(repository, visit_id="false-positive", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=30), reviewed_label="false_positive", review_status="reviewed")
    _add_visit(repository, visit_id="superseded-cardinal", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=35), reviewed_label="northern_cardinal", review_status="reviewed", is_superseded=True)
    _add_visit(repository, visit_id="yard-cardinal", zone_id=YARD_ZONE_ID, started_at=RANGE_START + timedelta(minutes=40), reviewed_label="northern_cardinal", review_status="reviewed")
    _add_visit(repository, visit_id="disabled-unresolved", zone_id=DISABLED_ZONE_ID, started_at=RANGE_START + timedelta(minutes=45))
    repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            event_id="event-unresolved-suggestion",
            visit_id="unresolved-suggestion",
            adapter_id="fixture",
            adapter_name="Fixture suggestion",
            suggested_label="blue_jay",
        )
    )
    before = _counts(repository)

    summary = repository.zone_insights(
        ZoneInsightsRequest(
            start_at=RANGE_START,
            end_at=RANGE_END,
            source_id=SOURCE_ID,
            zone_type="feeder",
        )
    )

    assert _counts(repository) == before
    assert summary.zone_count == 2
    feeder = next(zone for zone in summary.zones if zone.zone_id == FEEDER_ZONE_ID)
    assert feeder.metrics.healthy_monitored_hours == 2
    assert feeder.metrics.confirmed_bird_visit_count == 2
    assert feeder.metrics.confirmed_bird_visits_per_monitored_hour == 1
    assert feeder.metrics.total_confirmed_bird_dwell_seconds == 60
    assert feeder.metrics.median_confirmed_bird_duration_seconds == 30
    assert feeder.metrics.confirmed_species_richness == 2
    assert feeder.metrics.unresolved_visit_count == 1
    assert feeder.metrics.reviewed_blank_count == 1
    assert feeder.metrics.reviewed_non_bird_count == 1
    assert feeder.metrics.reviewed_false_positive_count == 1
    assert feeder.metrics.review_coverage_percentage == pytest.approx(83.33)
    assert feeder.metrics.reviewed_false_positive_percentage == 20
    assert feeder.metrics.evidence_success_percentage is None
    assert {item.label for item in feeder.species_composition} == {
        "northern_cardinal",
        "blue_jay",
    }
    assert feeder.metrics.data_quality_status == "sufficient"
    disabled = next(zone for zone in summary.zones if zone.zone_id == DISABLED_ZONE_ID)
    assert disabled.metrics.healthy_monitored_hours is None
    assert disabled.metrics.confirmed_bird_visits_per_monitored_hour is None
    assert disabled.metrics.data_quality_status == "unavailable_exposure"
    assert any("do not represent unique individuals" in warning for warning in summary.warnings)
    assert any("activity sessions" in warning for warning in summary.warnings)

    confirmed = repository.search_activity_library(
        ActivityLibrarySearchRequest(
            page_size=50,
            **feeder.confirmed_activity_drilldown.filters.model_dump(),
        )
    )
    blank = repository.search_activity_library(
        ActivityLibrarySearchRequest(
            page_size=50,
            **feeder.reviewed_blank_drilldown.filters.model_dump(),
        )
    )
    non_bird = repository.search_activity_library(
        ActivityLibrarySearchRequest(
            page_size=50,
            **feeder.reviewed_non_bird_drilldown.filters.model_dump(),
        )
    )
    # Everyday Discovery / Product Experience v2 (Phase K): the
    # `confirmed_wildlife` drilldown filter was bird-only before this
    # milestone (the same defect fixed for Activity Library's own search box
    # -- see docs/canonical-new-regular-species-contract.md and
    # `_activity_library_review_filter_matches`), so this Zone Insights
    # drilldown silently excluded the confirmed squirrel too. It is now
    # wildlife-inclusive, and genuinely, correctly overlaps with the
    # unrelated (unchanged) `non_bird` drilldown for a non-bird wildlife
    # taxon -- the two answer different questions ("is this confirmed
    # wildlife" vs. "is this specifically not a bird") that were only ever
    # mutually exclusive by the old bird-only bug's accident, not by design.
    assert {visit.id for visit in confirmed.visits} == {
        "confirmed-cardinal",
        "confirmed-blue-jay",
        "squirrel",
    }
    assert [visit.id for visit in blank.visits] == ["blank"]
    assert [visit.id for visit in non_bird.visits] == ["squirrel"]

    with repository.session_factory() as session:
        cardinal_taxonomy_id = session.scalar(
            select(TaxonomyLabelModel.id).where(TaxonomyLabelModel.label == "northern_cardinal")
        )
    assert cardinal_taxonomy_id is not None
    cardinal_only = repository.zone_insights(
        ZoneInsightsRequest(
            start_at=RANGE_START,
            end_at=RANGE_END,
            source_id=SOURCE_ID,
            zone_type="feeder",
            confirmed_taxonomy_id=cardinal_taxonomy_id,
        )
    )
    cardinal_feeder = next(zone for zone in cardinal_only.zones if zone.zone_id == FEEDER_ZONE_ID)
    assert cardinal_feeder.metrics.confirmed_bird_visit_count == 1
    assert [item.label for item in cardinal_feeder.species_composition] == ["northern_cardinal"]


def test_zone_insights_api_validates_range_and_is_read_only(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="api-cardinal", zone_id=FEEDER_ZONE_ID, started_at=RANGE_START + timedelta(minutes=5), reviewed_label="northern_cardinal", review_status="reviewed")
    before = _counts(repository)
    client = LegacyAuthenticatedSyncTestClient(app)

    valid = client.post(
        "/api/analytics/zone-insights",
        json={
            "start_at": RANGE_START.isoformat(),
            "end_at": RANGE_END.isoformat(),
            "source_id": SOURCE_ID,
        },
    )
    invalid = client.post(
        "/api/analytics/zone-insights",
        json={
            "start_at": "2025-01-01T00:00:00+00:00",
            "end_at": "2026-01-03T00:00:01+00:00",
        },
    )

    assert valid.status_code == 200
    assert valid.json()["applied_filters"]["source_id"] == SOURCE_ID
    assert invalid.status_code == 422
    assert _counts(repository) == before



def test_zone_insights_reports_durable_history_boundaries_and_insufficient_exposure(
    repository: ProductRepository,
) -> None:
    before = _counts(repository)
    partial = repository.zone_insights(
        ZoneInsightsRequest(
            start_at=RANGE_START - timedelta(hours=2),
            end_at=RANGE_END,
            stream_id=STREAM_ID,
        )
    )
    feeder = next(zone for zone in partial.zones if zone.zone_id == FEEDER_ZONE_ID)
    assert feeder.metrics.exposure_history_available_from == RANGE_START
    assert feeder.metrics.exposure_history_is_partial is True
    assert feeder.metrics.exposure_interval_count == 1
    assert feeder.metrics.healthy_monitored_hours == 2
    assert any(
        "Earlier time in this range is excluded from rate calculations."
        in warning
        for warning in partial.warnings
    )

    insufficient = repository.zone_insights(
        ZoneInsightsRequest(
            start_at=RANGE_START,
            end_at=RANGE_START + timedelta(hours=1),
            stream_id=STREAM_ID,
        )
    )
    limited_feeder = next(
        zone for zone in insufficient.zones if zone.zone_id == FEEDER_ZONE_ID
    )
    assert limited_feeder.metrics.healthy_monitored_hours == 1
    assert limited_feeder.metrics.confirmed_bird_visits_per_monitored_hour is None
    assert limited_feeder.metrics.data_quality_status == "limited_monitoring"
    assert _counts(repository) == before


def test_zone_insights_unions_overlapping_durable_intervals(
    repository: ProductRepository,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id="exposure-zone-insights-overlap",
                    stream_id=STREAM_ID,
                    source_id=SOURCE_ID,
                    runtime_generation_id="zone-insights-overlap",
                    started_at=RANGE_START + timedelta(hours=1),
                    last_confirmed_fresh_at=RANGE_START + timedelta(hours=3),
                    ended_at=RANGE_START + timedelta(hours=3),
                    close_reason="session_stopped",
                    created_at=RANGE_START + timedelta(hours=1),
                    updated_at=RANGE_START + timedelta(hours=3),
                )
            )

    summary = repository.zone_insights(
        ZoneInsightsRequest(
            start_at=RANGE_START,
            end_at=RANGE_END,
            stream_id=STREAM_ID,
        )
    )
    feeder = next(zone for zone in summary.zones if zone.zone_id == FEEDER_ZONE_ID)
    assert feeder.metrics.exposure_interval_count == 2
    assert feeder.metrics.healthy_monitored_hours == 3


def test_taxonomy_resolution_costs_exactly_one_query_regardless_of_visit_count(
    repository: ProductRepository,
) -> None:
    """Place Intelligence Backend Hardening v1: `zone_insights` used to cost
    *two* `taxonomy_labels` full-table-scan queries per reviewed Visit with
    a real species label -- one inside the canonical resolver's own
    `_visit_review_outcome`, and a second, independent one this method
    issued directly for its own `taxonomy` field -- so it scaled strictly
    worse than `place_activity_report`'s pre-hardening O(N) shape. Both are
    now served by one `_taxonomy_label_index` preload per call, reused for
    both lookups, so the total stays at exactly one query regardless of how
    many reviewed Visits are in range."""

    for index in range(30):
        _add_visit(
            repository,
            visit_id=f"taxonomy-query-{index}",
            zone_id=FEEDER_ZONE_ID,
            started_at=RANGE_START + timedelta(minutes=index),
            reviewed_label="northern_cardinal",
            review_status="reviewed",
        )

    def _generate(*, visit_count: int) -> int:
        statements: list[str] = []

        def _record(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
            if "taxonomy_labels" in statement:
                statements.append(statement)

        event.listen(repository.engine, "before_cursor_execute", _record)
        try:
            summary = repository.zone_insights(
                ZoneInsightsRequest(
                    start_at=RANGE_START,
                    end_at=RANGE_START + timedelta(minutes=visit_count),
                    source_id=SOURCE_ID,
                    zone_type="feeder",
                )
            )
        finally:
            event.remove(repository.engine, "before_cursor_execute", _record)
        feeder = next(zone for zone in summary.zones if zone.zone_id == FEEDER_ZONE_ID)
        assert feeder.metrics.confirmed_bird_visit_count == visit_count
        return len(statements)

    small = _generate(visit_count=5)
    large = _generate(visit_count=30)

    assert small == 1
    assert large == 1
