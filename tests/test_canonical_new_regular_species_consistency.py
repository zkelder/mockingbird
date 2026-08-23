"""Canonical New/Regular Species v1 (Everyday Discovery / Product Experience
v2; see docs/canonical-new-regular-species-contract.md): cross-surface
consistency regression coverage.

Before this milestone, Today's dashboard (`ProductRepository.
_dashboard_today_summary`) and Bird Log (`wildlife_journal_overview`/
`wildlife_journal_history`) each computed "new"/"regular" species status with
their own independent logic -- bird-only vs. wildlife-inclusive, raw
calendar-day counting vs. genuinely-monitored ("usable") day counting, a
14-day window vs. a 366-day window -- and could (and, per the milestone's own
archaeology, did) disagree about the same species on the same day. Both
surfaces now consume the exact same `mockingbird.analytics.historical_
baseline.compute_species_historical_statuses` facts via `ProductRepository.
_historical_place_baseline_and_species_statuses`. This file proves that
consumption end to end through the public repository methods each real page
calls -- `dashboard_summary` (Today) and `wildlife_journal_overview` (Bird
Log) -- rather than re-testing the shared pure function in isolation (already
covered by `tests/test_historical_baseline.py`).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import json

from mockingbird.api.schemas import WildlifeJournalOverviewRequest
from mockingbird.repository.product_repository import MotionEvidenceModel, ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

LOCAL_TIMEZONE = ZoneInfo("America/New_York")
SELECTED_DAY = date(2026, 7, 29)
LOCAL_NOW = datetime(2026, 7, 29, 12, tzinfo=LOCAL_TIMEZONE)
SOURCE_ID = "source-canonical-consistency"
STREAM_ID = "stream-canonical-consistency"
ZONE_ID = "zone-canonical-consistency"


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
                    name="Consistency camera",
                    kind="integration",
                    status="connected",
                    description="Canonical New/Regular cross-surface fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Consistency stream",
                    description="Canonical New/Regular cross-surface fixture.",
                    is_live=True,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID,
                    stream_id=STREAM_ID,
                    name="Feeder",
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
    reviewed_label: str,
) -> None:
    event_id = f"event-{visit_id}"
    media_id = f"media-{visit_id}"
    media_path = repository.media_root / f"{visit_id}.jpg"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename=f"{visit_id}.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(media_path),
                    original_filename=f"{visit_id}.jpg",
                    file_size_bytes=64,
                    created_at=observed_at,
                    captured_at=observed_at,
                    notes="Canonical New/Regular cross-surface fixture.",
                )
            )
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Consistency {visit_id}",
                    event_type="durable_monitoring_visit",
                    started_at=observed_at,
                    ended_at=observed_at + timedelta(seconds=20),
                    primary_zone_id=ZONE_ID,
                    review_status="reviewed",
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
                    review_status="reviewed",
                    representative_media_path=str(media_path),
                    zone_id=ZONE_ID,
                    is_superseded=False,
                )
            )
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
            # `_dashboard_today_summary`'s `qualified`/`confirmed_species`
            # (the source of `new_today`, unlike `recent_regulars`'s separate
            # `species_history` query) additionally requires a resolvable
            # detector-class context via `_review_queue_product_context`,
            # which reads this row -- see `test_dashboard_today.py`'s
            # identical fixture shape.
            session.add(
                MotionEvidenceModel(
                    id=f"evidence-{visit_id}",
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    zone_id=ZONE_ID,
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
                                        "class": "animal",
                                        "score": 0.8,
                                    }
                                }
                            )
                        }
                    ),
                    snapshot_media_asset_id=media_id,
                    status="promoted",
                    promoted_event_id=event_id,
                    promoted_visit_id=visit_id,
                    created_at=observed_at,
                    notes=None,
                )
            )


def _add_usable_day(repository: ProductRepository, *, day: datetime) -> None:
    """One durable monitoring interval clearing the 2-hour usable-day bar,
    stored as UTC (see `_utc`) regardless of `day`'s own zone."""

    start_at = _utc(day)
    end_at = _utc(day + timedelta(hours=3))
    interval_id = f"exposure-{STREAM_ID}-{day.date().isoformat()}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MonitoringExposureIntervalModel(
                    id=interval_id,
                    stream_id=STREAM_ID,
                    source_id=SOURCE_ID,
                    runtime_generation_id=f"generation-{interval_id}",
                    started_at=start_at,
                    last_confirmed_fresh_at=end_at,
                    ended_at=end_at,
                    close_reason="provider_failure",
                    created_at=start_at,
                    updated_at=end_at,
                )
            )


def test_today_and_bird_log_agree_on_regular_species(repository: ProductRepository) -> None:
    """A species confirmed on 3 genuinely-monitored days (20, 10, and 3 days
    ago -- the last one recent enough for Today's own 14-day "recent
    regulars" candidate window) must read "regular" identically on Today's
    dashboard and on Bird Log's live overview."""

    for days_ago in (20, 10, 3):
        day = LOCAL_NOW - timedelta(days=days_ago)
        _add_visit(
            repository,
            visit_id=f"cardinal-{days_ago}",
            observed_at=_utc(day),
            reviewed_label="northern_cardinal",
        )
        _add_usable_day(
            repository,
            day=datetime.combine(day.date(), datetime.min.time(), LOCAL_TIMEZONE),
        )

    dashboard = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    journal = repository.wildlife_journal_overview(
        WildlifeJournalOverviewRequest(), now=LOCAL_NOW + timedelta(hours=1)
    )

    dashboard_regular = {
        species.label: species.historical_status for species in dashboard.today.recent_regulars
    }
    journal_regular = {label.label: label for label in journal.labels}

    assert dashboard_regular.get("northern_cardinal") == "regular"
    assert journal_regular["northern_cardinal"].historical_status == "regular"
    assert journal_regular["northern_cardinal"].is_regular is True
    assert journal_regular["northern_cardinal"].distinct_confirmed_usable_days == 3


def test_today_and_bird_log_agree_on_new_species(repository: ProductRepository) -> None:
    """A taxon's first-ever confirmed record, made today, must read "new" (or
    the baseline-appropriate "first_record") identically on Today's dashboard
    and on Bird Log's live overview -- never "new" on one and silently absent
    or "seen_before" on the other."""

    _add_visit(
        repository,
        visit_id="wren-debut",
        observed_at=_utc(LOCAL_NOW),
        reviewed_label="carolina_wren",
    )

    dashboard = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    journal = repository.wildlife_journal_overview(
        WildlifeJournalOverviewRequest(), now=LOCAL_NOW + timedelta(hours=1)
    )

    dashboard_status = {
        species.label: species.historical_status for species in dashboard.today.new_today
    }
    journal_status = {label.label: label.historical_status for label in journal.labels}

    assert dashboard_status.get("carolina_wren") in ("new", "first_record")
    assert journal_status.get("carolina_wren") == dashboard_status.get("carolina_wren")


def test_today_and_bird_log_agree_a_species_is_not_yet_regular(
    repository: ProductRepository,
) -> None:
    """The negative case: 3 distinct calendar-day confirmations with zero
    recorded monitoring exposure must NOT read "regular" on either surface --
    this is the exact coverage-blind disagreement scenario the milestone's
    archaeology found (raw calendar-day counting vs. genuinely-monitored-day
    counting)."""

    for offset in (0, 1, 2):
        day = LOCAL_NOW - timedelta(days=offset)
        _add_visit(
            repository,
            visit_id=f"jay-{offset}",
            observed_at=_utc(day),
            reviewed_label="blue_jay",
        )

    dashboard = repository.dashboard_summary(now=LOCAL_NOW, local_date=SELECTED_DAY)
    journal = repository.wildlife_journal_overview(
        WildlifeJournalOverviewRequest(), now=LOCAL_NOW + timedelta(hours=1)
    )

    assert "blue_jay" not in {species.label for species in dashboard.today.recent_regulars}
    journal_entry = next(label for label in journal.labels if label.label == "blue_jay")
    assert journal_entry.is_regular is False
    assert journal_entry.historical_status != "regular"
