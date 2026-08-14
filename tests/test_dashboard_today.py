from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from mockingbird.repository.product_repository import (
    MotionEvidenceModel,
    ProductRepository,
    SpeciesSuggestionModel,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)


LOCAL_TIMEZONE = ZoneInfo("America/New_York")
SELECTED_DAY = date(2026, 7, 29)
LOCAL_NOW = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
SOURCE_ID = "source-dashboard-today"
STREAM_ID = "stream-dashboard-today"
ZONE_ID = "zone-dashboard-today"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    with repository.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            assert demo is not None
            demo.status = "archived"
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Today camera",
                    kind="integration",
                    status="connected",
                    description="Focused Today summary fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Today stream",
                    description="Focused Today summary fixture.",
                    is_live=True,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID,
                    stream_id=STREAM_ID,
                    name="North feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
    return repository


def _utc(local_value: datetime) -> datetime:
    return local_value.astimezone(UTC)


def _add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    observed_at: datetime,
    reviewed_label: str | None = None,
    detector_class: str = "animal",
    with_media: bool = True,
    is_superseded: bool = False,
    event_type: str = "durable_monitoring_visit",
    source_id: str = SOURCE_ID,
    stream_id: str = STREAM_ID,
    zone_id: str | None = ZONE_ID,
) -> None:
    event_id = f"event-{visit_id}"
    review_status = "reviewed" if reviewed_label is not None else "needs_review"
    media_id = f"media-{visit_id}"
    media_path = repository.media_root / f"{visit_id}.jpg"
    with repository.session_factory() as session:
        with session.begin():
            if with_media:
                session.add(
                    MediaAssetModel(
                        id=media_id,
                        source_id=source_id,
                        stream_id=stream_id,
                        filename=f"{visit_id}.jpg",
                        content_type="image/jpeg",
                        media_type="image",
                        local_path=str(media_path),
                        original_filename=f"{visit_id}.jpg",
                        file_size_bytes=64,
                        created_at=observed_at,
                        captured_at=observed_at,
                        notes="Today summary evidence fixture.",
                    )
                )
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Today {visit_id}",
                    event_type=event_type,
                    started_at=observed_at,
                    ended_at=observed_at + timedelta(seconds=20),
                    primary_zone_id=zone_id,
                    review_status=review_status,
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_animal",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=reviewed_label,
                    review_status=review_status,
                    representative_media_path=str(media_path) if with_media else None,
                    zone_id=zone_id,
                    is_superseded=is_superseded,
                )
            )
            if reviewed_label is not None:
                session.add(
                    ReviewLabelModel(
                        id=f"review-label-{visit_id}",
                        target_type="visit",
                        target_id=visit_id,
                        label=reviewed_label,
                        notes=None,
                        created_at=observed_at + timedelta(minutes=1),
                    )
                )
            session.add(
                MotionEvidenceModel(
                    id=f"evidence-{visit_id}",
                    source_id=source_id,
                    stream_id=stream_id,
                    zone_id=zone_id,
                    start_frame_index=None,
                    end_frame_index=None,
                    best_frame_index=None,
                    start_time=None,
                    end_time=None,
                    best_frame_time=None,
                    peak_changed_ratio=0.1,
                    triggered_frame_count=1,
                    scoring_config_json=json.dumps(
                        {
                            "detector_evidence": json.dumps(
                                {
                                    "current_track": {
                                        "track_generation_id": f"track-{visit_id}",
                                        "class": detector_class,
                                        "score": 0.8,
                                    }
                                }
                            )
                        }
                    ),
                    snapshot_media_asset_id=media_id if with_media else None,
                    status="promoted",
                    promoted_event_id=event_id,
                    promoted_visit_id=visit_id,
                    created_at=observed_at,
                    notes=None,
                )
            )


def _durable_counts(repository: ProductRepository) -> tuple[int, int, int, int, int]:
    with repository.session_factory() as session:
        return (
            session.scalar(select(func.count(EventModel.id))) or 0,
            session.scalar(select(func.count(VisitModel.id))) or 0,
            session.scalar(select(func.count(ReviewLabelModel.id))) or 0,
            session.scalar(select(func.count(MotionEvidenceModel.id))) or 0,
            session.scalar(select(func.count(SpeciesSuggestionModel.id))) or 0,
        )


def test_today_summary_uses_selected_local_day_and_current_reviewed_truth(
    repository: ProductRepository,
) -> None:
    local_start = datetime(2026, 7, 29, 0, tzinfo=LOCAL_TIMEZONE)
    _add_visit(
        repository,
        visit_id="before-day",
        observed_at=_utc(local_start - timedelta(microseconds=1)),
    )
    _add_visit(repository, visit_id="at-start", observed_at=_utc(local_start))
    _add_visit(
        repository,
        visit_id="before-end",
        observed_at=_utc(local_start + timedelta(days=1) - timedelta(microseconds=1)),
    )
    _add_visit(
        repository,
        visit_id="at-next-start",
        observed_at=_utc(local_start + timedelta(days=1)),
    )
    _add_visit(
        repository,
        visit_id="generic-bird",
        observed_at=_utc(local_start + timedelta(hours=8)),
        reviewed_label="bird",
    )
    _add_visit(
        repository,
        visit_id="cardinal-earlier",
        observed_at=_utc(local_start - timedelta(days=4, hours=-9)),
        reviewed_label="northern_cardinal",
    )
    _add_visit(
        repository,
        visit_id="cardinal-today",
        observed_at=_utc(local_start + timedelta(hours=9)),
        reviewed_label="northern_cardinal",
    )
    _add_visit(
        repository,
        visit_id="blue-jay-today",
        observed_at=_utc(local_start + timedelta(hours=10)),
        reviewed_label="blue_jay",
    )

    before = _durable_counts(repository)
    summary = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)

    assert _durable_counts(repository) == before
    assert summary.local_day == SELECTED_DAY.isoformat()
    assert summary.today.detector_qualified_animal_visit_count == 6
    assert summary.today.unresolved_animal_visit_count == 2
    assert summary.today.confirmed_bird_visit_count == 3
    assert summary.today.confirmed_species_count == 2
    assert [species.label for species in summary.today.new_today] == ["blue_jay"]
    assert "northern_cardinal" not in {
        species.label for species in summary.today.new_today
    }
    assert {bucket.hour: bucket.animal_visit_count for bucket in summary.today.activity_by_hour}[
        0
    ] == 1
    assert {bucket.hour: bucket.animal_visit_count for bucket in summary.today.activity_by_hour}[
        23
    ] == 1


def test_today_summary_regulars_use_distinct_days_and_exclude_non_nature_records(
    repository: ProductRepository,
) -> None:
    noon = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
    for offset in (0, 1, 2):
        _add_visit(
            repository,
            visit_id=f"cardinal-day-{offset}",
            observed_at=_utc(noon - timedelta(days=offset)),
            reviewed_label="northern_cardinal",
        )
    for index in range(3):
        _add_visit(
            repository,
            visit_id=f"blue-jay-repeat-{index}",
            observed_at=_utc(noon + timedelta(minutes=index)),
            reviewed_label="blue_jay",
        )
    _add_visit(
        repository,
        visit_id="suggestion-only",
        observed_at=_utc(noon + timedelta(hours=1)),
    )
    repository.create_species_suggestion(
        __import__("mockingbird.api.schemas", fromlist=["SpeciesSuggestionCreateRequest"])
        .SpeciesSuggestionCreateRequest(
            source_id=SOURCE_ID,
            stream_id=STREAM_ID,
            event_id="event-suggestion-only",
            visit_id="suggestion-only",
            adapter_id="fixture",
            adapter_name="Fixture suggestion",
            suggested_label="house_finch",
        )
    )
    for label in ("person", "vehicle", "blank", "false_positive"):
        _add_visit(
            repository,
            visit_id=f"excluded-{label}",
            observed_at=_utc(noon + timedelta(hours=2)),
            reviewed_label=label,
        )
    _add_visit(
        repository,
        visit_id="superseded-cardinal",
        observed_at=_utc(noon + timedelta(hours=3)),
        reviewed_label="northern_cardinal",
        is_superseded=True,
    )
    _add_visit(
        repository,
        visit_id="test-cardinal",
        observed_at=_utc(noon + timedelta(hours=3)),
        reviewed_label="northern_cardinal",
        event_type="test_fixture",
    )

    summary = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)

    assert [
        (species.label, species.distinct_days_seen)
        for species in summary.today.recent_regulars
    ] == [("northern_cardinal", 3)]
    assert summary.today.confirmed_species_count == 2
    assert summary.today.detector_qualified_animal_visit_count == 7
    assert "house_finch" not in {
        species.label
        for species in [*summary.today.new_today, *summary.today.recent_regulars]
    }
    excluded_ids = {
        "excluded-person",
        "excluded-vehicle",
        "excluded-blank",
        "excluded-false_positive",
        "superseded-cardinal",
        "test-cardinal",
    }
    assert excluded_ids.isdisjoint(
        {moment.id for moment in summary.today.best_moments}
    )


def test_today_summary_bounds_moments_and_help_with_honest_deterministic_media(
    repository: ProductRepository,
) -> None:
    noon = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
    for index in range(9):
        _add_visit(
            repository,
            visit_id=f"unresolved-{index:02d}",
            observed_at=_utc(noon + timedelta(minutes=index)),
            with_media=index != 8,
        )

    first = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    second = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)

    assert len(first.today.best_moments) == 6
    assert len(first.today.needs_help) == 3
    assert [visit.id for visit in first.today.needs_help] == [
        "unresolved-08",
        "unresolved-07",
        "unresolved-06",
    ]
    assert first.today.needs_help[0].primary_evidence is None
    assert [visit.id for visit in first.today.best_moments] == [
        visit.id for visit in second.today.best_moments
    ]
    assert [visit.id for visit in first.today.needs_help] == [
        visit.id for visit in second.today.needs_help
    ]


# --- Automatic Species Suggestion v1: `likely_today` provisional grouping --


def _add_species_suggestion(
    repository: ProductRepository,
    *,
    visit_id: str,
    event_id: str,
    label: str,
) -> None:
    from mockingbird.api.schemas import SpeciesSuggestionCreateRequest

    repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            stream_id=STREAM_ID,
            event_id=event_id,
            visit_id=visit_id,
            adapter_id="fixture_bioclip",
            adapter_name="Fixture BioCLIP",
            suggested_label=label,
        )
    )


def _confirm_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    label: str,
    at: datetime,
) -> None:
    """Simulate what the real correction endpoint does: set the Visit's own
    reviewed fields and append an authoritative ReviewLabel row."""

    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.reviewed_label = label
            visit.review_status = "reviewed"
            session.add(
                ReviewLabelModel(
                    id=f"review-label-confirm-{visit_id}",
                    target_type="visit",
                    target_id=visit_id,
                    label=label,
                    notes=None,
                    created_at=at,
                )
            )


def test_today_summary_likely_today_groups_unreviewed_suggested_species(
    repository: ProductRepository,
) -> None:
    noon = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
    _add_visit(repository, visit_id="likely-house-finch", observed_at=_utc(noon))
    _add_species_suggestion(
        repository,
        visit_id="likely-house-finch",
        event_id="event-likely-house-finch",
        label="house_finch",
    )

    summary = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)

    assert [species.label for species in summary.today.likely_today] == ["house_finch"]
    likely = summary.today.likely_today[0]
    assert likely.is_confirmed is False
    assert likely.latest_visit.id == "likely-house-finch"
    # A provisional suggestion is useful in Today, but it is never counted
    # as, or mixed into, confirmed reviewed truth.
    assert "house_finch" not in {species.label for species in summary.today.new_today}
    assert "house_finch" not in {species.label for species in summary.today.recent_regulars}
    assert summary.today.confirmed_species_count == 0


def test_today_summary_likely_today_excludes_reviewed_and_non_species_suggestions(
    repository: ProductRepository,
) -> None:
    noon = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
    # Confirmed truth always wins and is never duplicated into likely_today,
    # even when a stale suggestion also exists for the same Visit.
    _add_visit(
        repository,
        visit_id="confirmed-cardinal",
        observed_at=_utc(noon),
        reviewed_label="northern_cardinal",
    )
    _add_species_suggestion(
        repository,
        visit_id="confirmed-cardinal",
        event_id="event-confirmed-cardinal",
        label="house_finch",
    )
    # "Not Animal" removes provisional wildlife interpretation even though a
    # species suggestion exists for the same Visit.
    _add_visit(
        repository,
        visit_id="false-positive-with-guess",
        observed_at=_utc(noon),
        reviewed_label="false_positive",
    )
    _add_species_suggestion(
        repository,
        visit_id="false-positive-with-guess",
        event_id="event-false-positive-with-guess",
        label="house_finch",
    )
    # A generic (non-species) suggested label must never create a fake
    # species tile.
    _add_visit(repository, visit_id="generic-bird-guess", observed_at=_utc(noon))
    _add_species_suggestion(
        repository,
        visit_id="generic-bird-guess",
        event_id="event-generic-bird-guess",
        label="bird",
    )

    summary = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)

    assert summary.today.likely_today == []


def test_today_summary_moves_from_likely_to_confirmed_without_duplication(
    repository: ProductRepository,
) -> None:
    """Model suggests House Finch; human later confirms Northern Cardinal.
    The same Visit must resolve to exactly one species entry -- the human
    correction -- never both, and never the stale suggestion."""

    noon = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
    _add_visit(repository, visit_id="finch-then-confirmed", observed_at=_utc(noon))
    _add_species_suggestion(
        repository,
        visit_id="finch-then-confirmed",
        event_id="event-finch-then-confirmed",
        label="house_finch",
    )

    before = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    assert [species.label for species in before.today.likely_today] == ["house_finch"]
    assert before.today.new_today == []

    _confirm_visit(
        repository,
        visit_id="finch-then-confirmed",
        label="northern_cardinal",
        at=_utc(noon) + timedelta(minutes=5),
    )

    after = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    assert after.today.likely_today == []
    assert [species.label for species in after.today.new_today] == ["northern_cardinal"]
    all_entries_for_visit = [
        species.label
        for species in [
            *after.today.new_today,
            *after.today.recent_regulars,
            *after.today.likely_today,
        ]
        if species.latest_visit.id == "finch-then-confirmed"
    ]
    assert all_entries_for_visit == ["northern_cardinal"]
