"""Calm Attention & Notifications v1: ProductRepository.sync_attention_signals,
per-user notification preferences, and the AlertCategory/AttentionCategory/
AttentionUrgency presentation mapping. Mirrors tests/test_place_story_
repository.py's fixture/seeding pattern (source/stream/zone + `_cover_days` +
`_add_visit` + `_confirm`) -- see that file for the established precedent
this one follows, and docs/calm-attention-notifications-v1-report.md for the
full design.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from mockingbird.api.main import configure_repository
from mockingbird.api.schemas import (
    AlertActionType,
    AlertCategory,
    AlertSeverity,
    AttentionCategory,
    AttentionUrgency,
    CurrentUser,
    LabelCategory,
    PlaceActivityReportDigest,
    PlaceActivityReportDigestCoverage,
    PlaceActivityReportDigestOtherActivity,
    PlaceActivityReportDigestSpeciesHighlight,
    ReviewCorrectionCreate,
    UserNotificationPreferencesUpdate,
    UserRole,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MonitoringExposureIntervalModel,
    ProductAlertModel,
    StreamModel,
    UserModel,
    VisitModel,
    ZoneModel,
)

SOURCE_ID = "attention-fixture-source"
STREAM_ID = "attention-fixture-stream"
ZONE_ID = "attention-fixture-zone"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID, name="Attention fixture camera", kind="manual_upload",
                    status="connected", description="Calm Attention fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID, source_id=SOURCE_ID, name="Attention fixture stream",
                    description="Calm Attention fixture.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID, stream_id=STREAM_ID, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
    yield repository
    configure_repository(None)
    repository.close()


def _cover_days(repository: ProductRepository, *, start: date, days: int) -> None:
    with repository.session_factory() as session:
        with session.begin():
            for offset in range(days):
                day = start + timedelta(days=offset)
                started_at = datetime(day.year, day.month, day.day, tzinfo=UTC)
                ended_at = started_at + timedelta(hours=23)
                session.add(
                    MonitoringExposureIntervalModel(
                        id=f"exposure-{day.isoformat()}", stream_id=STREAM_ID, source_id=SOURCE_ID,
                        runtime_generation_id=f"generation-{day.isoformat()}", started_at=started_at,
                        last_confirmed_fresh_at=ended_at, ended_at=ended_at, close_reason="provider_failure",
                        created_at=started_at, updated_at=ended_at,
                    )
                )


def _add_visit(repository: ProductRepository, *, visit_id: str, at: datetime) -> None:
    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id, stream_id=STREAM_ID, title=f"Attention fixture {visit_id}",
                    event_type="manual_media_import", started_at=at, ended_at=at + timedelta(seconds=20),
                    primary_zone_id=ZONE_ID, review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id, event_id=event_id, subject_label="unknown_bird", species_guess=None,
                    confidence=None, reviewed_label=None, review_status="needs_review",
                    representative_media_path=None, zone_id=ZONE_ID, is_superseded=False,
                )
            )


def _confirm(repository: ProductRepository, *, visit_id: str, label: str = "northern_cardinal") -> None:
    repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human")
    )


def _alerts(repository: ProductRepository, category: str) -> list[ProductAlertModel]:
    from sqlalchemy import select

    with repository.session_factory() as session:
        return session.scalars(
            select(ProductAlertModel)
            .where(ProductAlertModel.category == category, ProductAlertModel.resolved_at.is_(None))
            .order_by(ProductAlertModel.created_at)
        ).all()


def _make_user(repository: ProductRepository, *, user_id: str, role: UserRole) -> CurrentUser:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                UserModel(
                    id=user_id, display_name=user_id, login_identity=user_id.lower(),
                    password_hash="scrypt$n=1,r=1,p=1$00$00", role=role.value, enabled=True,
                    created_at=now, updated_at=now, password_updated_at=now,
                )
            )
    return CurrentUser(id=user_id, display_name=user_id, login_identity=user_id.lower(), role=role, enabled=True)


# ---------------------------------------------------------------------------
# Pure mapping functions -- no database needed.
# ---------------------------------------------------------------------------


def test_attention_category_mapping_covers_every_alert_category() -> None:
    for category in AlertCategory:
        result = ProductRepository._attention_category_for(category)
        assert isinstance(result, AttentionCategory)
    assert ProductRepository._attention_category_for(AlertCategory.review) == AttentionCategory.needs_help
    assert ProductRepository._attention_category_for(AlertCategory.monitoring) == AttentionCategory.observatory_health
    assert ProductRepository._attention_category_for(AlertCategory.storage) == AttentionCategory.observatory_health
    assert ProductRepository._attention_category_for(AlertCategory.journal) == AttentionCategory.discovery
    assert ProductRepository._attention_category_for(AlertCategory.insight) == AttentionCategory.insight


def test_attention_urgency_review_is_always_in_app_only() -> None:
    for severity in AlertSeverity:
        assert (
            ProductRepository._attention_urgency_for(AlertCategory.review, severity)
            == AttentionUrgency.in_app_only
        )


def test_attention_urgency_wildlife_content_never_immediate() -> None:
    """Phase 9: "Do NOT use raw classifier confidence as importance... Do
    NOT notify for every ordinary Visit" -- Discovery/Insight content is
    never `immediate`, regardless of severity."""

    for category in (AlertCategory.journal, AlertCategory.insight):
        for severity in AlertSeverity:
            assert ProductRepository._attention_urgency_for(category, severity) == AttentionUrgency.digest


def test_attention_urgency_health_is_immediate_only_at_high_severity() -> None:
    for category in (AlertCategory.monitoring, AlertCategory.storage):
        assert ProductRepository._attention_urgency_for(category, AlertSeverity.high) == AttentionUrgency.immediate
        assert (
            ProductRepository._attention_urgency_for(category, AlertSeverity.warning)
            == AttentionUrgency.in_app_only
        )


def _highlight(display_name: str, *, note: str | None = None) -> PlaceActivityReportDigestSpeciesHighlight:
    now = datetime(2025, 6, 1, tzinfo=UTC)
    return PlaceActivityReportDigestSpeciesHighlight(
        label=display_name.lower().replace(" ", "_"), display_name=display_name, category=LabelCategory.bird,
        is_species=True, confirmed_visit_count=1, provisional_visit_count=0,
        first_activity_at=now, last_activity_at=now, reason="confirmed_activity",
        historical_note=note, change_note=None, pattern_note=None,
    )


def _digest(
    *, highlights: list[PlaceActivityReportDigestSpeciesHighlight], unresolved: int = 0,
    place_change_note: str | None = None,
) -> PlaceActivityReportDigest:
    now = datetime(2025, 6, 1, tzinfo=UTC)
    return PlaceActivityReportDigest(
        coverage=PlaceActivityReportDigestCoverage(state="confirmed_wildlife", maturity="usable", message="Fallback."),
        primary_highlights=highlights, other_species=[],
        other_activity=PlaceActivityReportDigestOtherActivity(provisional_visit_count=0, unresolved_visit_count=unresolved),
        place_change_note=place_change_note, first_activity_at=now, last_activity_at=now,
        confirmed_wildlife_visit_count=len(highlights),
    )


def test_compose_digest_message_joins_one_two_and_three_plus_highlights() -> None:
    one = ProductRepository._compose_digest_message(_digest(highlights=[_highlight("Northern Cardinal")]))
    assert one == "Northern Cardinal recorded."

    two = ProductRepository._compose_digest_message(
        _digest(highlights=[_highlight("Northern Cardinal"), _highlight("Blue Jay")])
    )
    assert two == "Northern Cardinal and Blue Jay recorded."

    three = ProductRepository._compose_digest_message(
        _digest(highlights=[_highlight("Northern Cardinal"), _highlight("Blue Jay"), _highlight("Tufted Titmouse")])
    )
    assert three == "Northern Cardinal, Blue Jay, and Tufted Titmouse recorded."


def test_compose_digest_message_includes_lead_note_and_needs_help_clause() -> None:
    message = ProductRepository._compose_digest_message(
        _digest(
            highlights=[_highlight("Eastern Bluebird", note="New to your reviewed history")],
            unresolved=3, place_change_note="Confirmed wildlife activity has been higher recently.",
        )
    )
    assert message == (
        "Eastern Bluebird recorded. New to your reviewed history "
        "Confirmed wildlife activity has been higher recently. 3 observations could use your help."
    )


def test_compose_digest_message_uses_singular_grammar_for_one_unresolved_observation() -> None:
    message = ProductRepository._compose_digest_message(_digest(highlights=[_highlight("Northern Cardinal")], unresolved=1))
    assert message.endswith("1 observation could use your help.")


def test_compose_digest_message_falls_back_to_coverage_message_with_no_highlights() -> None:
    message = ProductRepository._compose_digest_message(_digest(highlights=[]))
    assert message == "Fallback."


# ---------------------------------------------------------------------------
# Place Story -> attention sync.
# ---------------------------------------------------------------------------


def test_first_seen_is_not_duplicated_as_a_second_discovery_alert(new_york_host_timezone, repository: ProductRepository) -> None:
    """Phase 6 semantic deduplication: `_sync_journal_milestone_alert`
    (fired inline at review-commit time) already owns "first confirmed
    local observation." `sync_attention_signals` must not create a
    second, independently-worded Discovery alert for the same fact."""

    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    _add_visit(repository, visit_id="v1", at=datetime(2025, 3, 3, 10, tzinfo=UTC))
    _confirm(repository, visit_id="v1")

    journal_before = _alerts(repository, "journal")
    assert len(journal_before) == 1

    repository.sync_attention_signals(now=datetime(2025, 3, 5, tzinfo=UTC))

    journal_after = _alerts(repository, "journal")
    assert len(journal_after) == 1, "a second first-seen-flavored alert appeared"
    assert journal_after[0].deduplication_key == "journal:first-label:northern_cardinal"
    assert not any(a.deduplication_key.startswith("place-story:first-seen:") for a in journal_after)


def test_becoming_regular_produces_one_insight_alert(new_york_host_timezone, repository: ProductRepository) -> None:
    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=40)
    for offset in range(10):
        visit_id = f"v{offset}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 3, 1, tzinfo=UTC) + timedelta(days=offset, hours=10))
        _confirm(repository, visit_id=visit_id)

    repository.sync_attention_signals(now=datetime(2025, 3, 12, tzinfo=UTC))

    insight_alerts = _alerts(repository, "insight")
    regularity_alerts = [a for a in insight_alerts if a.deduplication_key.startswith("place-story:regularity:")]
    assert regularity_alerts, "expected at least one regularity-transition attention item"
    for alert in regularity_alerts:
        assert alert.action_type == AlertActionType.open_place_story.value

    # Idempotency (Phase 26): re-running with the same `now` must not
    # create a second version of the same condition, and must not disturb
    # already-read state.
    # Attention Integrity & Health Reliability v1: read state is per-user.
    reader = _make_user(repository, user_id="regularity-reader", role=UserRole.administrator)
    assert repository.mark_product_alert_read(regularity_alerts[0].id, user_id=reader.id)

    repository.sync_attention_signals(now=datetime(2025, 3, 12, tzinfo=UTC))
    with repository.session_factory() as session:
        from sqlalchemy import select

        replayed = session.scalars(
            select(ProductAlertModel).where(ProductAlertModel.deduplication_key == regularity_alerts[0].deduplication_key)
        ).all()
        assert len(replayed) == 1, "re-running the sync created a second version of an unchanged condition"
    listed = repository.list_product_alerts(viewer=reader, page_size=50).items
    replayed_view = next(item for item in listed if item.id == regularity_alerts[0].id)
    assert replayed_view.status == "read", "re-running the sync silently reset read state"


def test_stale_place_story_alert_is_resolved_on_next_sync(new_york_host_timezone, repository: ProductRepository) -> None:
    """Phase 32 correction safety: an attention item whose underlying
    Place Story fact no longer recomputes (e.g. a correction changed the
    confirmed taxon) is resolved on the next periodic sync, not left
    presenting stale truth forever."""

    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    now = datetime(2025, 3, 5, tzinfo=UTC)
    with repository.session_factory() as session:
        with session.begin():
            repository._refresh_product_alert(
                session, category=AlertCategory.insight, severity=AlertSeverity.info,
                title="Stale fact", message="No longer true.",
                deduplication_key="place-story:regularity:nonexistent_taxon:regular:2025-03-01",
                condition_fingerprint="place_story_event",
                action_type=AlertActionType.open_place_story, action_parameters={}, now=now,
            )

    repository.sync_attention_signals(now=now)

    with repository.session_factory() as session:
        from sqlalchemy import select

        stale = session.scalars(
            select(ProductAlertModel).where(
                ProductAlertModel.deduplication_key == "place-story:regularity:nonexistent_taxon:regular:2025-03-01"
            )
        ).one()
        assert stale.resolved_at is not None


def test_fifth_species_diversity_milestone_still_fires(new_york_host_timezone, repository: ProductRepository) -> None:
    """Proves the ordinal-1 exclusion above is narrow, not a blanket
    suppression of diversity milestones: the 5th distinct species is
    genuinely new information beyond that species' own routine "first
    confirmed" fact, and must still produce a Discovery alert."""

    start = date(2025, 3, 1)
    _cover_days(repository, start=start, days=10)
    labels = ["northern_cardinal", "blue_jay", "tufted_titmouse", "carolina_wren", "american_robin"]
    for index, label in enumerate(labels):
        visit_id = f"v{index}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 3, 1, tzinfo=UTC) + timedelta(days=index, hours=10))
        _confirm(repository, visit_id=visit_id, label=label)

    repository.sync_attention_signals(now=datetime(2025, 3, 6, tzinfo=UTC))

    journal_alerts = _alerts(repository, "journal")
    milestone_alerts = [a for a in journal_alerts if a.deduplication_key == "place-story:diversity-milestone:5"]
    assert len(milestone_alerts) == 1
    first_species_milestones = [a for a in journal_alerts if "diversity-milestone:1" in a.deduplication_key]
    assert first_species_milestones == [], "the redundant 1st-species milestone must stay excluded"


# ---------------------------------------------------------------------------
# Daily digest -> attention sync.
# ---------------------------------------------------------------------------


def test_daily_digest_suppressed_with_no_confirmed_activity(repository: ProductRepository) -> None:
    """Phase 14: never send a routine "0 birds detected today" notification."""

    now = datetime(2025, 6, 1, 12, tzinfo=UTC)
    repository.sync_attention_signals(now=now)
    assert _alerts(repository, "insight") == []


def test_daily_digest_created_with_confirmed_activity(repository: ProductRepository) -> None:
    start = date(2025, 6, 1)
    _cover_days(repository, start=start, days=3)
    _add_visit(repository, visit_id="v1", at=datetime(2025, 6, 1, 9, tzinfo=UTC))
    _confirm(repository, visit_id="v1")

    now = datetime(2025, 6, 1, 20, tzinfo=UTC)
    repository.sync_attention_signals(now=now)

    daily = [a for a in _alerts(repository, "insight") if a.deduplication_key == "digest:daily:2025-06-01"]
    assert len(daily) == 1
    assert "cardinal" in daily[0].message.lower() or "Cardinal" in daily[0].message
    assert daily[0].action_type == AlertActionType.open_place_report.value


# ---------------------------------------------------------------------------
# Per-user preferences and role-based visibility.
# ---------------------------------------------------------------------------


def test_notification_preferences_default_conservatively(repository: ProductRepository) -> None:
    preferences = repository.get_notification_preferences("user-1")
    assert preferences.browser_notifications_enabled is False
    assert preferences.quiet_hours_enabled is False
    assert preferences.discovery_enabled is True
    assert preferences.insight_enabled is True
    assert preferences.needs_help_enabled is True
    assert preferences.observatory_health_enabled is True


def test_notification_preferences_update_persists(repository: ProductRepository) -> None:
    repository.update_notification_preferences(
        "user-1", UserNotificationPreferencesUpdate(insight_enabled=False, browser_notifications_enabled=True)
    )
    reloaded = repository.get_notification_preferences("user-1")
    assert reloaded.insight_enabled is False
    assert reloaded.browser_notifications_enabled is True
    # Untouched fields keep their prior/default value.
    assert reloaded.discovery_enabled is True


def test_viewer_never_sees_needs_help_category(repository: ProductRepository) -> None:
    _add_visit(repository, visit_id="v1", at=datetime(2025, 3, 3, 10, tzinfo=UTC))
    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, "v1")
            repository._sync_review_alert(session, visit, datetime.now(UTC))

    viewer = _make_user(repository, user_id="viewer-1", role=UserRole.viewer)
    reviewer = _make_user(repository, user_id="reviewer-1", role=UserRole.reviewer)

    viewer_unread = repository.product_alert_unread(viewer=viewer)
    reviewer_unread = repository.product_alert_unread(viewer=reviewer)

    assert not any(a.category == AlertCategory.review for a in viewer_unread.recent)
    assert any(a.category == AlertCategory.review for a in reviewer_unread.recent)

    viewer_list = repository.list_product_alerts(category=AlertCategory.review, viewer=viewer)
    assert viewer_list.items == []
    reviewer_list = repository.list_product_alerts(category=AlertCategory.review, viewer=reviewer)
    assert len(reviewer_list.items) == 1


# ---------------------------------------------------------------------------
# Phase 36 product-shaped scenario: a realistic week, exercised end-to-end
# through the real sync entry point. Scoped honestly: the wildlife/digest/
# Needs-Help behavior below is exercised for real through this milestone's
# own new code; Wednesday's "brief disconnect, no interruption" and
# Friday's "sustained outage, one message" camera-health claims are NOT
# re-simulated here (that would mean fabricating Camera Node hardware
# state this test has no real stake in) -- they are already covered by
# the pre-existing, unmodified `_sync_camera_health_incident`/
# `CameraHealthIncidentModel` test suite this milestone reused rather than
# rebuilt (see the milestone report's "Observatory health"). This test's
# job is to prove the wildlife/digest/review side of the week stays calm.
# ---------------------------------------------------------------------------


def test_product_shaped_quiet_week_stays_calm(repository: ProductRepository) -> None:
    start = date(2025, 7, 7)  # a Monday
    # Coverage must extend well before Monday too: (1) the weekly digest's
    # own `place_change_summary` windows need a valid 14-usable-day
    # *reference* window ending before the 7-day *recent* window even
    # begins, and (2) the regular-establishing history below must finish
    # its own "becoming regular" transition *before* `sync_attention_
    # signals`'s own 30-day trailing Place Story lookback reaches back
    # from Monday, or that real, one-time transition would legitimately
    # (and correctly) still appear as this week's news -- both fixture-
    # completeness lessons, not product gaps.
    _cover_days(repository, start=start - timedelta(days=120), days=180)
    # Long-established regulars, active *every single day* for 90 days
    # straight before this week -- comfortably regular (and long past
    # their own one-time "becoming regular" transition) with no gap that
    # could itself read as a later "returned after absence," so their
    # ordinary daily activity this week must not produce any Insight alert.
    for offset in range(-90, 0):
        for label in ("northern_cardinal", "carolina_chickadee"):
            visit_id = f"regular-{label}-{offset}"
            _add_visit(repository, visit_id=visit_id, at=datetime(2025, 7, 7, tzinfo=UTC) + timedelta(days=offset, hours=9))
            _confirm(repository, visit_id=visit_id, label=label)

    def sync_end_of(day: date) -> None:
        repository.sync_attention_signals(now=datetime(day.year, day.month, day.day, 21, tzinfo=UTC))

    # Monday: ordinary regular activity only.
    _add_visit(repository, visit_id="mon-1", at=datetime(2025, 7, 7, 9, tzinfo=UTC))
    _confirm(repository, visit_id="mon-1", label="northern_cardinal")
    _add_visit(repository, visit_id="mon-2", at=datetime(2025, 7, 7, 10, tzinfo=UTC))
    _confirm(repository, visit_id="mon-2", label="carolina_chickadee")
    sync_end_of(date(2025, 7, 7))

    monday_insight = [a for a in _alerts(repository, "insight") if a.deduplication_key.startswith("place-story:")]
    assert monday_insight == [], "ordinary regular-species activity produced a spurious Insight alert"

    # Tuesday: first-ever bluebird, reviewed -- the one real Discovery
    # moment this week.
    _add_visit(repository, visit_id="tue-1", at=datetime(2025, 7, 8, 9, tzinfo=UTC))
    _confirm(repository, visit_id="tue-1", label="eastern_bluebird")
    sync_end_of(date(2025, 7, 8))

    bluebird_discovery = [a for a in _alerts(repository, "journal") if "bluebird" in a.deduplication_key]
    assert len(bluebird_discovery) == 1
    assert ProductRepository._attention_urgency_for(AlertCategory.journal, AlertSeverity.info) == AttentionUrgency.digest

    # Thursday: three Needs Help items -- must stay in-app-only, never a
    # live interruption, and must never multiply into three separate
    # "urgent" alerts.
    for index in range(3):
        visit_id = f"thu-needs-help-{index}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 7, 10, 9 + index, tzinfo=UTC))
    with repository.session_factory() as session:
        with session.begin():
            for index in range(3):
                visit = session.get(VisitModel, f"thu-needs-help-{index}")
                repository._sync_review_alert(session, visit, datetime.now(UTC))
    sync_end_of(date(2025, 7, 10))

    review_alerts = _alerts(repository, "review")
    assert len(review_alerts) == 3
    assert all(
        ProductRepository._attention_urgency_for(AlertCategory.review, AlertSeverity.warning)
        == AttentionUrgency.in_app_only
        for _ in review_alerts
    )
    thursday_digest = next(a for a in _alerts(repository, "insight") if a.deduplication_key == "digest:daily:2025-07-10")
    assert "could use your help" in thursday_digest.message

    # Saturday: a busy but ordinary morning for the already-regular species
    # -- higher count, same taxa, no genuinely unusual-for-Place signal.
    for index in range(6):
        visit_id = f"sat-{index}"
        _add_visit(repository, visit_id=visit_id, at=datetime(2025, 7, 12, 8 + index, tzinfo=UTC))
        _confirm(repository, visit_id=visit_id, label="northern_cardinal" if index % 2 else "carolina_chickadee")
    sync_end_of(date(2025, 7, 12))
    saturday_diversity = [a for a in _alerts(repository, "journal") if "diversity-milestone" in a.deduplication_key]
    assert saturday_diversity == [], "a busy-but-ordinary Saturday must not read as a biodiversity milestone"

    # Sunday: the weekly recap -- exactly one, idempotent.
    sync_end_of(date(2025, 7, 13))
    weekly = [a for a in _alerts(repository, "insight") if a.deduplication_key.startswith("digest:weekly:")]
    assert len(weekly) == 1

    # Whole-week accounting: never "dozens of messages" -- see the
    # milestone's own PRODUCT VALUE TEST. Count every distinct attention
    # item this entire week produced, across every category.
    with repository.session_factory() as session:
        total_active = session.scalar(
            select(func.count(ProductAlertModel.id)).where(ProductAlertModel.resolved_at.is_(None))
        )
        rows = session.scalars(select(ProductAlertModel).where(ProductAlertModel.resolved_at.is_(None))).all()
        immediate = [
            row for row in rows
            if ProductRepository._attention_urgency_for(AlertCategory(row.category), AlertSeverity(row.severity))
            == AttentionUrgency.immediate
        ]
    # 1 first-bluebird Discovery + 3 individual per-Visit review items
    # (in-app-only, not live interruptions) + up to 7 daily digests + 1
    # weekly digest -- comfortably bounded, nowhere near "dozens."
    assert total_active <= 14, f"expected a calm, bounded week; got {total_active} active attention items"
    # And zero of them were ever `immediate` urgency -- nothing in this
    # entirely wildlife/review week should have interrupted anyone live.
    assert immediate == [], "a purely wildlife/review week must never produce a live interruption"


def test_disabling_a_category_hides_it_for_that_user_only(repository: ProductRepository) -> None:
    start = date(2025, 6, 1)
    _cover_days(repository, start=start, days=3)
    _add_visit(repository, visit_id="v1", at=datetime(2025, 6, 1, 9, tzinfo=UTC))
    _confirm(repository, visit_id="v1")
    repository.sync_attention_signals(now=datetime(2025, 6, 1, 20, tzinfo=UTC))
    assert _alerts(repository, "insight"), "fixture must actually produce an insight alert"

    admin_a = _make_user(repository, user_id="admin-a", role=UserRole.administrator)
    admin_b = _make_user(repository, user_id="admin-b", role=UserRole.administrator)
    repository.update_notification_preferences("admin-a", UserNotificationPreferencesUpdate(insight_enabled=False))

    a_unread = repository.product_alert_unread(viewer=admin_a)
    b_unread = repository.product_alert_unread(viewer=admin_b)
    assert not any(a.attention_category == AttentionCategory.insight for a in a_unread.recent)
    assert any(a.attention_category == AttentionCategory.insight for a in b_unread.recent)
