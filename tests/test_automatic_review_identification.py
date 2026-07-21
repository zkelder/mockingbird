from __future__ import annotations

from threading import Event

import pytest

from mockingbird.species.automatic_identification import (
    AutomaticIdentificationUpdate,
    AutomaticReviewIdentificationAssist,
)
from mockingbird.species.bioclip_adapter import BIOCLIP_ADAPTER_ID


class FakeRepository:
    def __init__(self, *, outcome: str = "succeeded", fail: bool = False) -> None:
        self.outcome = outcome
        self.fail = fail
        self.attempts: list[dict[str, object]] = []
        self.calls = []
        self.started = Event()
        self.release = Event()
        self.release.set()

    def list_bioclip_identification_attempts(self, *, target_type=None, target_id=None):
        return list(self.attempts)

    def identify_review_queue_item(self, target_type, target_id, payload=None):
        self.calls.append((target_type, target_id, payload))
        self.started.set()
        self.release.wait(timeout=2)
        if self.fail:
            raise RuntimeError("local runner failed")
        suggestion_id = "suggestion-1" if self.outcome == "succeeded" else None
        self.attempts.append(
            {
                "id": "attempt-1",
                "outcome": self.outcome,
                "resulting_species_suggestion_id": suggestion_id,
            }
        )


def collect_updates():
    updates: list[AutomaticIdentificationUpdate] = []
    terminal = Event()

    def callback(update: AutomaticIdentificationUpdate) -> None:
        updates.append(update)
        if update.status not in {"pending", "running"}:
            terminal.set()

    return updates, terminal, callback


def test_schedules_one_evidence_only_bioclip_attempt() -> None:
    repository = FakeRepository()
    assist = AutomaticReviewIdentificationAssist()
    updates, terminal, callback = collect_updates()

    assert assist.schedule(repository, visit_id="visit-1", on_update=callback) is True
    assert terminal.wait(timeout=2)
    assist.shutdown()

    assert [update.status for update in updates] == ["pending", "running", "succeeded"]
    assert len(repository.calls) == 1
    target_type, target_id, payload = repository.calls[0]
    assert (target_type, target_id) == ("visit", "visit-1")
    assert payload.adapter_id == BIOCLIP_ADAPTER_ID
    assert updates[-1].suggestion_id == "suggestion-1"


@pytest.mark.parametrize("outcome", ["succeeded", "failed", "timed_out", "no_result"])
def test_existing_attempt_of_any_outcome_is_never_retried(outcome: str) -> None:
    repository = FakeRepository()
    repository.attempts.append({"id": "existing", "outcome": outcome})
    assist = AutomaticReviewIdentificationAssist()
    updates, _terminal, callback = collect_updates()

    assert assist.schedule(repository, visit_id="visit-1", on_update=callback) is False
    assist.shutdown()

    assert repository.calls == []
    assert [update.status for update in updates] == ["skipped_existing"]


def test_runner_failure_is_terminal_and_does_not_retry() -> None:
    repository = FakeRepository(fail=True)
    assist = AutomaticReviewIdentificationAssist()
    updates, terminal, callback = collect_updates()

    assert assist.schedule(repository, visit_id="visit-1", on_update=callback) is True
    assert terminal.wait(timeout=2)
    assist.shutdown()

    assert len(repository.calls) == 1
    assert updates[-1].status == "failed"


def test_schedule_does_not_block_the_monitor_thread() -> None:
    repository = FakeRepository()
    repository.release.clear()
    assist = AutomaticReviewIdentificationAssist()
    updates, terminal, callback = collect_updates()

    assert assist.schedule(repository, visit_id="visit-1", on_update=callback) is True
    assert repository.started.wait(timeout=1)
    assert terminal.is_set() is False
    assert assist.schedule(repository, visit_id="visit-1", on_update=callback) is False

    repository.release.set()
    assert terminal.wait(timeout=2)
    assist.shutdown()
    assert len(repository.calls) == 1
