"""Activity session recommendations for saved-snapshot motion checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha1
import re
from typing import Literal

ActivitySessionStatus = Literal[
    "new_activity",
    "ongoing_activity",
    "cooldown_suppressed",
    "no_activity",
]

DEFAULT_QUIET_PERIOD_SECONDS = 30
DEFAULT_COOLDOWN_SECONDS = 30
DEFAULT_MAX_SNAPSHOTS_PER_SESSION = 3


@dataclass(frozen=True)
class ActivitySessionSettings:
    quiet_period_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    max_snapshots_per_session: int = DEFAULT_MAX_SNAPSHOTS_PER_SESSION


@dataclass(frozen=True)
class ExistingActivityReference:
    activity_id: str
    source_id: str | None
    stream_id: str | None
    region_kind: str
    region_id: str
    created_at: datetime
    snapshot_media_asset_id: str | None
    status: str


@dataclass(frozen=True)
class ActivitySessionRecommendation:
    session_key: str | None
    session_status: ActivitySessionStatus
    should_create_review_activity: bool
    message: str
    existing_activity_reference: str | None = None
    best_snapshot_media_asset_id: str | None = None
    best_snapshot_reason: str | None = None
    quiet_period_seconds: int = DEFAULT_QUIET_PERIOD_SECONDS
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    max_snapshots_per_session: int = DEFAULT_MAX_SNAPSHOTS_PER_SESSION
    debug: dict[str, str | int | float | bool | None] = field(default_factory=dict)


def recommend_activity_session(
    *,
    source_id: str | None,
    stream_id: str,
    region_kind: str,
    region_id: str | None,
    activity_at: datetime | None,
    activity_detected: bool,
    review_activity_available: bool,
    best_snapshot_media_asset_id: str | None,
    existing_activities: list[ExistingActivityReference],
    settings: ActivitySessionSettings | None = None,
) -> ActivitySessionRecommendation:
    """Recommend whether a motion result should become another review activity."""

    active_settings = settings or ActivitySessionSettings()
    timestamp = _coerce_datetime(activity_at) or datetime.now(timezone.utc)
    session_key = (
        activity_session_key(
            source_id=source_id,
            stream_id=stream_id,
            region_kind=region_kind,
            region_id=region_id,
            activity_at=timestamp,
            settings=active_settings,
        )
        if region_id
        else None
    )
    debug = _debug_details(
        source_id=source_id,
        stream_id=stream_id,
        region_kind=region_kind,
        region_id=region_id,
        activity_at=timestamp,
        settings=active_settings,
    )

    if not activity_detected or not region_id:
        return ActivitySessionRecommendation(
            session_key=session_key,
            session_status="no_activity",
            should_create_review_activity=False,
            message="No activity detected.",
            best_snapshot_media_asset_id=best_snapshot_media_asset_id,
            quiet_period_seconds=active_settings.quiet_period_seconds,
            cooldown_seconds=active_settings.cooldown_seconds,
            max_snapshots_per_session=active_settings.max_snapshots_per_session,
            debug=debug,
        )

    matching_existing = [
        activity
        for activity in existing_activities
        if activity.status != "ignored"
        and activity.stream_id == stream_id
        and activity.region_kind == region_kind
        and activity.region_id == region_id
    ]
    newest_existing = max(
        matching_existing,
        key=lambda activity: _coerce_datetime(activity.created_at) or datetime.min,
        default=None,
    )

    if newest_existing and best_snapshot_media_asset_id:
        duplicate_snapshot = next(
            (
                activity
                for activity in matching_existing
                if activity.snapshot_media_asset_id == best_snapshot_media_asset_id
            ),
            None,
        )
        if duplicate_snapshot:
            return _duplicate_recommendation(
                session_key=session_key,
                status="ongoing_activity",
                message="Ongoing activity already has a review item.",
                existing_activity=duplicate_snapshot,
                best_snapshot_media_asset_id=best_snapshot_media_asset_id,
                best_snapshot_reason="strongest motion score",
                settings=active_settings,
                debug=debug,
            )

    if newest_existing:
        newest_created_at = _coerce_datetime(newest_existing.created_at) or timestamp
        age_seconds = max(0.0, (timestamp - newest_created_at).total_seconds())
        if age_seconds <= active_settings.quiet_period_seconds:
            return _duplicate_recommendation(
                session_key=session_key,
                status="ongoing_activity",
                message="Ongoing activity already has a review item.",
                existing_activity=newest_existing,
                best_snapshot_media_asset_id=best_snapshot_media_asset_id,
                best_snapshot_reason="strongest motion score",
                settings=active_settings,
                debug={**debug, "existing_activity_age_seconds": round(age_seconds, 3)},
            )
        if age_seconds <= (
            active_settings.quiet_period_seconds + active_settings.cooldown_seconds
        ):
            return _duplicate_recommendation(
                session_key=session_key,
                status="cooldown_suppressed",
                message="Cooldown active for this activity area.",
                existing_activity=newest_existing,
                best_snapshot_media_asset_id=best_snapshot_media_asset_id,
                best_snapshot_reason="strongest motion score",
                settings=active_settings,
                debug={**debug, "existing_activity_age_seconds": round(age_seconds, 3)},
            )

    should_create = review_activity_available
    message = (
        "New activity is ready for review."
        if should_create
        else "Activity was detected, but review evidence is not available."
    )
    return ActivitySessionRecommendation(
        session_key=session_key,
        session_status="new_activity",
        should_create_review_activity=should_create,
        message=message,
        best_snapshot_media_asset_id=best_snapshot_media_asset_id,
        best_snapshot_reason="strongest motion score" if best_snapshot_media_asset_id else None,
        quiet_period_seconds=active_settings.quiet_period_seconds,
        cooldown_seconds=active_settings.cooldown_seconds,
        max_snapshots_per_session=active_settings.max_snapshots_per_session,
        debug=debug,
    )


def activity_session_key(
    *,
    source_id: str | None,
    stream_id: str,
    region_kind: str,
    region_id: str | None,
    activity_at: datetime,
    settings: ActivitySessionSettings,
) -> str:
    timestamp = _coerce_datetime(activity_at) or datetime.now(timezone.utc)
    quiet_period = max(1, settings.quiet_period_seconds)
    time_bucket = int(timestamp.timestamp()) // quiet_period
    raw_key = "|".join(
        [
            source_id or "source-unknown",
            stream_id,
            _slug(region_kind),
            _slug(region_id or "area-unknown"),
            str(time_bucket),
        ]
    )
    return f"activity-session-{sha1(raw_key.encode('utf-8')).hexdigest()[:16]}"


def _duplicate_recommendation(
    *,
    session_key: str | None,
    status: ActivitySessionStatus,
    message: str,
    existing_activity: ExistingActivityReference,
    best_snapshot_media_asset_id: str | None,
    best_snapshot_reason: str | None,
    settings: ActivitySessionSettings,
    debug: dict[str, str | int | float | bool | None],
) -> ActivitySessionRecommendation:
    return ActivitySessionRecommendation(
        session_key=session_key,
        session_status=status,
        should_create_review_activity=False,
        message=message,
        existing_activity_reference=existing_activity.activity_id,
        best_snapshot_media_asset_id=best_snapshot_media_asset_id,
        best_snapshot_reason=best_snapshot_reason,
        quiet_period_seconds=settings.quiet_period_seconds,
        cooldown_seconds=settings.cooldown_seconds,
        max_snapshots_per_session=settings.max_snapshots_per_session,
        debug=debug,
    )


def _debug_details(
    *,
    source_id: str | None,
    stream_id: str,
    region_kind: str,
    region_id: str | None,
    activity_at: datetime,
    settings: ActivitySessionSettings,
) -> dict[str, str | int | float | bool | None]:
    quiet_period = max(1, settings.quiet_period_seconds)
    return {
        "source_id": source_id,
        "stream_id": stream_id,
        "region_kind": region_kind,
        "region_id": region_id,
        "time_bucket": int(activity_at.timestamp()) // quiet_period,
    }


def _coerce_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
