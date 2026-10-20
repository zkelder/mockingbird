"""Attention Integrity & Health Reliability v1: turn *existing* model/runtime
health facts into a sustained, deduplicated, self-resolving Observatory
Health attention condition.

This module computes no new health fact. Its inputs are exactly what already
exists elsewhere:

* MockingBird Doctor's own interpreted Detector model, GPU / CUDA and
  Species identification checks (`mockingbird.diagnostics.doctor.
  model_runtime_health_checks`), which already decide when a *configured*
  production model/runtime is unavailable (for example, a Camera Node is
  configured but no valid detector bundle is installed, or BioCLIP is
  configured but its runtime is unavailable). A check that is not
  configured, passes, was skipped, or could not finish is never read as
  "unavailable" here -- only a completed WARN/FAIL interpretation is.
* The Observation Engine's own in-memory Start failure classification
  (`engine_runtime._engine_failure_message`'s `missing_model_or_runtime`/
  `unsupported_gpu` categories), for a Stream that actually tried to observe.

Each condition is a *diagnostic inference about the Host*, never evidence
about wildlife and never Reviewed truth: it only ever becomes an attention
item, which a person can read, dismiss, or act on.

"Sustained" means the same kind of problem was observed on at least two
separate evaluations at least `sustain_seconds` apart; one clean evaluation
(every input gathered, that kind absent) resolves it. First-seen state is
in-process only: after a restart a condition must be re-observed before it
alerts again, which errs toward calm rather than toward a stale alarm.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import threading

#: Two attention-sync ticks (15 minutes apart by default) always satisfy
#: this; it exists so a caller evaluating more often still cannot alert on
#: a problem that was only seen for a moment (for example, a model file
#: caught mid-reinstall).
DEFAULT_MODEL_RUNTIME_SUSTAIN_SECONDS = 120.0


class ModelRuntimeHealthKind(str, Enum):
    """One Observatory Health alert per kind, so two different problems
    (say, a missing detector bundle *and* an unavailable BioCLIP runtime)
    never hide each other, while the same problem reported by both Doctor
    and a failed Observation Engine Start stays one alert."""

    detector_model = "detector_model"
    gpu_runtime = "gpu_runtime"
    species_model = "species_model"


@dataclass(frozen=True)
class ModelRuntimeHealthFact:
    """One observed "configured production model/runtime is unavailable"
    fact. `code` is a short stable code (Doctor check code or engine error
    code); `message` is already user-safe text taken from the fact's own
    source. `stream_id` is set only when a real Stream's Observation Engine
    failed to start, which lets the alert open that Stream's recovery
    surface instead of Doctor."""

    kind: ModelRuntimeHealthKind
    code: str
    message: str
    stream_id: str | None = None


@dataclass(frozen=True)
class ModelRuntimeHealthCondition:
    kind: ModelRuntimeHealthKind
    code: str
    message: str
    stream_id: str | None
    first_observed_at: datetime


@dataclass(frozen=True)
class ModelRuntimeHealthEvaluation:
    """`sustained` are the conditions to alert on now; `cleared` are the
    kinds this complete evaluation positively observed healthy and whose
    alert (if any) must resolve. A kind in neither set is pending: seen
    once, not yet sustained, and neither alerted nor resolved."""

    sustained: tuple[ModelRuntimeHealthCondition, ...]
    cleared: frozenset[ModelRuntimeHealthKind]


def _preferred_fact(facts: list[ModelRuntimeHealthFact]) -> ModelRuntimeHealthFact:
    # A real Stream that could not start is the more actionable, more
    # specific fact; among those, a stable order keeps the fingerprint
    # stable across ticks instead of flapping between Streams.
    stream_facts = sorted((fact for fact in facts if fact.stream_id), key=lambda fact: (fact.stream_id or "", fact.code))
    if stream_facts:
        return stream_facts[0]
    return sorted(facts, key=lambda fact: fact.code)[0]


class ModelRuntimeHealthMonitor:
    """Bounded per-kind first-seen bookkeeping; thread-safe because the
    attention sync thread is the only writer but a test or a future caller
    may evaluate concurrently."""

    def __init__(self, *, sustain_seconds: float = DEFAULT_MODEL_RUNTIME_SUSTAIN_SECONDS) -> None:
        self._sustain = timedelta(seconds=max(0.0, sustain_seconds))
        self._first_seen: dict[ModelRuntimeHealthKind, datetime] = {}
        self._observation_count: dict[ModelRuntimeHealthKind, int] = {}
        self._lock = threading.Lock()

    def evaluate(self, facts: Iterable[ModelRuntimeHealthFact], *, now: datetime) -> ModelRuntimeHealthEvaluation:
        by_kind: dict[ModelRuntimeHealthKind, list[ModelRuntimeHealthFact]] = {}
        for fact in facts:
            by_kind.setdefault(fact.kind, []).append(fact)
        sustained: list[ModelRuntimeHealthCondition] = []
        cleared: set[ModelRuntimeHealthKind] = set()
        with self._lock:
            for kind in ModelRuntimeHealthKind:
                kind_facts = by_kind.get(kind)
                if not kind_facts:
                    self._first_seen.pop(kind, None)
                    self._observation_count.pop(kind, None)
                    cleared.add(kind)
                    continue
                first_seen = self._first_seen.setdefault(kind, now)
                count = self._observation_count.get(kind, 0) + 1
                self._observation_count[kind] = count
                if count < 2 or now - first_seen < self._sustain:
                    continue
                fact = _preferred_fact(kind_facts)
                sustained.append(
                    ModelRuntimeHealthCondition(
                        kind=kind,
                        code=fact.code,
                        message=fact.message,
                        stream_id=fact.stream_id,
                        first_observed_at=first_seen,
                    )
                )
        return ModelRuntimeHealthEvaluation(sustained=tuple(sustained), cleared=frozenset(cleared))


#: Observation Engine Start-failure categories (already produced by
#: `engine_runtime._engine_failure_message`, unchanged) -> the one alert
#: kind each belongs to.
ENGINE_FAILURE_CATEGORY_KIND: dict[str, ModelRuntimeHealthKind] = {
    "missing_model_or_runtime": ModelRuntimeHealthKind.detector_model,
    "unsupported_gpu": ModelRuntimeHealthKind.gpu_runtime,
}
