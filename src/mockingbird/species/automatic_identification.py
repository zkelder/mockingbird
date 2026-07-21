"""Bounded automatic identification assist for new review candidates."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import threading
from typing import Any, Protocol

from mockingbird.api.schemas import ReviewIdentificationRequest
from mockingbird.species.bioclip_adapter import BIOCLIP_ADAPTER_ID


class AutomaticIdentificationRepository(Protocol):
    def list_bioclip_identification_attempts(
        self,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def identify_review_queue_item(
        self,
        target_type: str,
        target_id: str,
        payload: ReviewIdentificationRequest | None = None,
    ) -> Any: ...


@dataclass(frozen=True)
class AutomaticIdentificationUpdate:
    status: str
    target_id: str
    attempt_id: str | None = None
    suggestion_id: str | None = None
    message: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "target_id": self.target_id,
            "attempt_id": self.attempt_id,
            "suggestion_id": self.suggestion_id,
            "message": self.message,
        }


UpdateCallback = Callable[[AutomaticIdentificationUpdate], None]


class AutomaticReviewIdentificationAssist:
    """Run at most one local automatic BioCLIP attempt at a time."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="mockingbird-auto-identify",
        )
        self._lock = threading.Lock()
        self._reserved_targets: set[str] = set()
        self._futures: dict[str, tuple[Future[None], UpdateCallback]] = {}
        self._stopping = False

    def schedule(
        self,
        repository: AutomaticIdentificationRepository,
        *,
        visit_id: str,
        on_update: UpdateCallback,
    ) -> bool:
        visit_id = visit_id.strip()
        if not visit_id:
            return False
        attempts = repository.list_bioclip_identification_attempts(
            target_type="visit", target_id=visit_id
        )
        if attempts:
            latest = attempts[-1]
            self._notify(
                on_update,
                AutomaticIdentificationUpdate(
                    status="skipped_existing",
                    target_id=visit_id,
                    attempt_id=_text(latest.get("id")),
                    suggestion_id=_text(latest.get("resulting_species_suggestion_id")),
                    message="Automatic identification skipped because an attempt already exists.",
                ),
            )
            return False
        with self._lock:
            if self._stopping or visit_id in self._reserved_targets:
                return False
            self._reserved_targets.add(visit_id)
        self._notify(
            on_update,
            AutomaticIdentificationUpdate(
                status="pending",
                target_id=visit_id,
                message="Automatic identification is waiting for the local BioCLIP runner.",
            ),
        )
        try:
            future = self._executor.submit(self._run, repository, visit_id, on_update)
        except RuntimeError:
            with self._lock:
                self._reserved_targets.discard(visit_id)
            self._notify(
                on_update,
                AutomaticIdentificationUpdate(
                    status="failed",
                    target_id=visit_id,
                    message="Automatic identification could not start during shutdown.",
                ),
            )
            return False
        with self._lock:
            self._futures[visit_id] = (future, on_update)
        future.add_done_callback(
            lambda completed, target_id=visit_id: self._finish(target_id, completed)
        )
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._stopping = True
            futures = list(self._futures.items())
        for target_id, (future, on_update) in futures:
            if future.cancel():
                self._notify(
                    on_update,
                    AutomaticIdentificationUpdate(
                        status="failed",
                        target_id=target_id,
                        message="Automatic identification was cancelled before shutdown.",
                    ),
                )
        # Running work is already bounded by BioCLIP's timeout and owns honest
        # attempt completion, so shutdown waits for that one call.
        self._executor.shutdown(wait=True, cancel_futures=True)

    def _run(
        self,
        repository: AutomaticIdentificationRepository,
        visit_id: str,
        on_update: UpdateCallback,
    ) -> None:
        self._notify(
            on_update,
            AutomaticIdentificationUpdate(
                status="running",
                target_id=visit_id,
                message="Automatic identification is running locally.",
            ),
        )
        try:
            repository.identify_review_queue_item(
                "visit",
                visit_id,
                ReviewIdentificationRequest(
                    adapter_id=BIOCLIP_ADAPTER_ID,
                    notes=(
                        "Automatic post-activity BioCLIP suggestion; evidence only. "
                        "Explicit correction remains the only review truth."
                    ),
                ),
            )
            attempts = repository.list_bioclip_identification_attempts(
                target_type="visit", target_id=visit_id
            )
        except Exception:
            self._notify(
                on_update,
                AutomaticIdentificationUpdate(
                    status="failed",
                    target_id=visit_id,
                    message="Automatic identification failed without affecting monitoring.",
                ),
            )
            return
        self._notify(
            on_update,
            _update_from_attempt(visit_id, attempts[-1])
            if attempts
            else AutomaticIdentificationUpdate(
                status="failed",
                target_id=visit_id,
                message="Automatic identification finished without durable attempt evidence.",
            ),
        )

    def _finish(self, target_id: str, _future: Future[None]) -> None:
        with self._lock:
            self._reserved_targets.discard(target_id)
            self._futures.pop(target_id, None)

    @staticmethod
    def _notify(
        callback: UpdateCallback, update: AutomaticIdentificationUpdate
    ) -> None:
        try:
            callback(update)
        except Exception:
            return


def _update_from_attempt(
    visit_id: str, attempt: dict[str, Any]
) -> AutomaticIdentificationUpdate:
    outcome = _text(attempt.get("outcome"))
    status = {
        "succeeded": "succeeded",
        "no_result": "no_result",
        "timed_out": "timed_out",
    }.get(outcome or "", "failed")
    message = {
        "succeeded": "Automatic identification added a pending suggestion for review.",
        "no_result": "Automatic identification completed without a suggestion.",
        "timed_out": "Automatic identification reached its bounded timeout.",
        "failed": "Automatic identification failed without affecting monitoring.",
    }[status]
    return AutomaticIdentificationUpdate(
        status=status,
        target_id=visit_id,
        attempt_id=_text(attempt.get("id")),
        suggestion_id=_text(attempt.get("resulting_species_suggestion_id")),
        message=message,
    )


def _text(value: Any) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None


__all__ = ["AutomaticIdentificationUpdate", "AutomaticReviewIdentificationAssist"]
