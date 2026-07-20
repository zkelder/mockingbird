import threading

from mockingbird.storage.retention_service import LocalStorageRetentionService


def test_retention_service_runs_only_the_app_owned_maintenance_callback() -> None:
    calls: list[str] = []
    service = LocalStorageRetentionService(
        run_maintenance=lambda: calls.append("maintenance"),
        poll_interval_seconds=5,
    )

    service.run_once()
    service.shutdown()

    assert calls == ["maintenance"]


def test_retention_service_never_overlaps_maintenance_and_survives_failure() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls: list[str] = []

    def run_maintenance() -> None:
        calls.append("started")
        entered.set()
        release.wait(timeout=1)

    service = LocalStorageRetentionService(run_maintenance=run_maintenance)
    first = threading.Thread(target=service.run_once)
    first.start()
    assert entered.wait(timeout=1)
    service.run_once()
    release.set()
    first.join(timeout=1)
    assert calls == ["started"]

    failures = 0

    def flaky_maintenance() -> None:
        nonlocal failures
        failures += 1
        if failures == 1:
            raise OSError("local media unavailable")

    failing_service = LocalStorageRetentionService(run_maintenance=flaky_maintenance)
    failing_service.run_once()
    failing_service.run_once()

    assert failures == 2
