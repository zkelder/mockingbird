"""Mirrors tests/test_storage_retention_service.py's own established
pattern, applied to AttentionSyncService (see
docs/calm-attention-notifications-v1-report.md)."""

import threading

from mockingbird.monitoring.attention_sync_service import AttentionSyncService


def test_attention_sync_service_runs_only_the_app_owned_sync_callback() -> None:
    calls: list[str] = []
    service = AttentionSyncService(run_sync=lambda: calls.append("sync"), poll_interval_seconds=60)

    service.run_once()
    service.shutdown()

    assert calls == ["sync"]


def test_attention_sync_service_never_overlaps_sync_and_survives_failure() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def run_sync() -> None:
        calls.append("started")
        entered.set()
        release.wait(timeout=1)

    service = AttentionSyncService(run_sync=run_sync)
    first = threading.Thread(target=service.run_once)
    first.start()
    assert entered.wait(timeout=1)
    service.run_once()  # a second concurrent tick must be a no-op, not a second sync
    release.set()
    first.join(timeout=1)
    assert calls == ["started"]

    failures = 0

    def flaky_sync() -> None:
        nonlocal failures
        failures += 1
        if failures == 1:
            raise OSError("Place Story computation unavailable")

    failing_service = AttentionSyncService(run_sync=flaky_sync)
    failing_service.run_once()  # must not raise -- Phase 27: a sync failure never surfaces
    failing_service.run_once()

    assert failures == 2


def test_attention_sync_service_enforces_a_sixty_second_floor() -> None:
    """Unlike storage retention's 5s floor, attention sync must never be
    configured to run faster than once a minute -- Phase 38's "do not
    introduce high-frequency polling.\""""

    service = AttentionSyncService(run_sync=lambda: None, poll_interval_seconds=1)
    assert service._poll_interval_seconds == 60.0  # noqa: SLF001 - white-box floor check
