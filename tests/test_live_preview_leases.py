from datetime import UTC, datetime, timedelta

from mockingbird.playback.live_preview_leases import LivePreviewLeaseManager


def test_preview_leases_are_idempotent_and_release_only_after_last_owner() -> None:
    manager = LivePreviewLeaseManager(
        max_previews_per_owner=4,
        max_backend_preview_streams=2,
        lease_seconds=60,
    )
    try:
        first = manager.acquire(
            owner_id="browser-owner-one",
            stream_id="stream-one",
            backend_session_active=False,
        )
        repeated = manager.acquire(
            owner_id="browser-owner-one",
            stream_id="stream-one",
            backend_session_active=True,
        )
        second_owner = manager.acquire(
            owner_id="browser-owner-two",
            stream_id="stream-one",
            backend_session_active=True,
        )

        assert first.status == "live"
        assert first.should_start_session is True
        assert repeated.status == "live"
        assert repeated.should_start_session is False
        assert second_owner.status == "live"

        first_release = manager.release(
            owner_id="browser-owner-one",
            stream_id="stream-one",
        )
        last_release = manager.release(
            owner_id="browser-owner-two",
            stream_id="stream-one",
        )
        assert first_release.released is True
        assert first_release.should_stop_session is False
        assert last_release.released is True
        assert last_release.should_stop_session is True
    finally:
        manager.shutdown()


def test_preview_leases_enforce_local_capacity_and_expire_safely() -> None:
    now = datetime(2026, 7, 21, tzinfo=UTC)
    expired_streams: list[str] = []
    manager = LivePreviewLeaseManager(
        clock=lambda: now,
        max_previews_per_owner=4,
        max_backend_preview_streams=2,
        lease_seconds=60,
        on_expired_stream=expired_streams.append,
    )
    try:
        assert manager.acquire(
            owner_id="browser-owner",
            stream_id="stream-one",
            backend_session_active=False,
        ).status == "live"
        assert manager.acquire(
            owner_id="browser-owner",
            stream_id="stream-two",
            backend_session_active=False,
        ).status == "live"
        limited = manager.acquire(
            owner_id="browser-owner",
            stream_id="stream-three",
            backend_session_active=False,
        )
        assert limited.status == "limit_reached"
        assert limited.effective_limit == 2

        now += timedelta(seconds=61)
        # A subsequent explicit request prunes departed-browser leases without
        # changing monitoring intent or creating any product records.
        refreshed = manager.acquire(
            owner_id="browser-owner",
            stream_id="stream-three",
            backend_session_active=False,
        )
        assert refreshed.status == "live"
        assert set(expired_streams) == {"stream-one", "stream-two"}
    finally:
        manager.shutdown()
