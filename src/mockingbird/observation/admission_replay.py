"""Perception Replay Regression Harness v1: shadow admission bridge.

`replay.py`'s Stage 2 benchmark and its Stage 6.19 `assemble_visit_episode_
report` extension both stop at an *assembled* `AssembledVisitProposal` --
deliberately: neither module imports the product repository (see their own
module docstrings and `test_visit_episode_assembler.py::test_no_product_
repository_dependency`). This module is the next, additive layer: it drives
an already-assembled proposal through the *real*, completely unmodified
Stage 7 authority/quality/scene-confusor gates
(`candidate_visit_authority.evaluate_candidate_authority`,
`candidate_quality_gate.evaluate_evidence_admission`,
`scene_confusor.evaluate_scene_confusor_suspicion` -- all three called,
unmodified, from inside `ProductRepository._create_candidate_visit_locked`)
and the real `CandidateVisitAuthorityAdapter.attempt_candidate` -- whose own
docstring already names "a replay/offline harness" as a legitimate caller,
alongside a live session driver and a test.

Reuse, not reimplementation: every admission decision here is made by the
exact production code path a live Camera Node session uses. Nothing in this
module reimplements authority, quality-gate, or scene-confusor logic.

Isolation, structural not conventional: this module only ever constructs a
`ProductRepository` against a caller-supplied, explicitly isolated
`db_url`/`media_root` (see `IsolatedAdmissionRepository`) -- it has no
default-database code path at all, so there is no fallback for a caller to
accidentally hit. `mockingbird.storage.database.database_url_from_env`'s own
fail-closed guard (`docs/test-repository-isolation-contract.md`) is a second,
independent layer of protection if a caller ever did pass `db_url=None`
outside a pytest process, but this module never does so itself.

A replay-derived admission run necessarily starts with a clean, empty
history: no prior scene-confusor region history, no prior candidate-Visit
ledger for this synthetic stream. `scene_confusor.evaluate_scene_confusor_
suspicion` therefore honestly returns `not_suspected` for every replay run
today (there is no cross-run history to accumulate) -- this is not a
harness limitation to fix, it is what a fresh, isolated regression run is
supposed to mean; see docs/perception-replay-regression-harness-contract.md
"Scope boundaries."
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Mapping, Sequence
import tempfile

from mockingbird.observation.candidate_visit_authority import (
    AmbiguousBoundaryArbitration,
    ObservationAuthorityMode,
    resolve_ambiguous_boundary_arbitration,
)
from mockingbird.observation.candidate_visit_adapter import CandidateAttemptResult, CandidateVisitAuthorityAdapter
from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import CameraSourceModel, StreamModel

ADMISSION_REPLAY_VERSION = "admission-replay-v1"

#: A replay run must always use an explicitly isolated stream identity, never
#: one that could collide with (or be mistaken for) a real product Stream.
#: Every synthetic stream id this module mints or accepts must carry this
#: prefix; `IsolatedAdmissionRepository` refuses to activate authority for
#: any stream id that does not.
REPLAY_STREAM_ID_PREFIX = "replay:"


class AdmissionReplayError(ValueError):
    """A bounded admission-replay configuration or safety-guard failure."""


@dataclass(frozen=True)
class ProposalAdmissionOutcome:
    """One proposal's real admission verdict from this replay run, plus the
    bounded evidence facts needed to explain it without re-deriving them."""

    proposal_id: str
    stream_id: str
    outcome: str
    reason: str
    visit_id: str | None
    event_id: str | None
    observed_at: datetime
    ambiguous_boundary_resolved: bool
    evidence_candidate_count: int
    evidence_bytes_available_count: int

    @property
    def created(self) -> bool:
        return self.outcome == "created"


@dataclass(frozen=True)
class AdmissionReplayReport:
    """The full-funnel admission-shadow result for one replay run's already-
    assembled proposals, in deterministic (proposal_id-sorted) order."""

    stream_id: str
    outcomes: tuple[ProposalAdmissionOutcome, ...]
    arbitration: AmbiguousBoundaryArbitration
    outcome_counts: Mapping[str, int]

    @property
    def created_count(self) -> int:
        return self.outcome_counts.get("created", 0)


def require_replay_stream_id(stream_id: str) -> None:
    """Fail closed rather than silently admit against an ambiguous identity:
    every stream id this module ever activates authority for, or attempts a
    candidate against, must be visibly a replay identity. A caller wanting a
    fuller-persistence replay against real Stream history should do so
    explicitly and outside this module, never by this module quietly
    accepting a real `stream_id`."""

    if not stream_id.startswith(REPLAY_STREAM_ID_PREFIX):
        raise AdmissionReplayError("stream_id_not_replay_namespaced")


@contextmanager
def IsolatedAdmissionRepository(
    *,
    directory: Path | None = None,
    stream_id: str,
    activation_boundary_at: datetime,
    max_candidates_per_session: int | None = None,
    max_candidates_per_hour: int | None = None,
) -> Iterator[ProductRepository]:
    """Yield a freshly created `ProductRepository` backed by an isolated,
    disposable SQLite database and media root -- the exact `db_url=f"sqlite:
    ///{...}"` construction convention `tests/conftest.py` and ~90 test
    files already use, applied here at script/CLI scope instead of test
    scope. Never resolves a default database path; `directory` is always
    either caller-supplied or a fresh `tempfile.mkdtemp` this function owns
    and removes on exit.

    Also creates one explicit, synthetic `CameraSourceModel`/`StreamModel`
    row pair for `stream_id` -- `_create_candidate_visit_locked` looks the
    Stream up by id (for its own privacy-zone check) and rejects
    `missing_stream` otherwise; a fresh isolated database has no demo-seeded
    Stream a real `stream_id` could coincidentally match. `zone_id` is left
    unset on every replayed proposal (no Zone row exists in this isolated
    database either), which is honestly outside this harness's v1 scope --
    see "Scope boundaries" in docs/perception-replay-regression-harness-
    contract.md.

    Activates candidate-Visit authority for `stream_id` with `fresh_session=
    True` (mirroring exactly what a real Start-observing action does --
    `engine_runtime._EngineSession`'s own Start path, see `candidate-visit-
    authority-contract.md` "Fresh-session activation") so replayed proposals
    can actually reach a `create` verdict instead of trivially blocking on
    `blocked_shadow_mode`. `require_replay_stream_id` is enforced before
    anything is created."""

    require_replay_stream_id(stream_id)
    owns_directory = directory is None
    resolved = Path(directory) if directory is not None else Path(tempfile.mkdtemp(prefix="mockingbird-replay-admission-"))
    repository = ProductRepository(
        db_url=f"sqlite:///{resolved / 'replay-admission.sqlite3'}",
        media_root=resolved / "media",
    )
    try:
        source_id = f"source:{stream_id}"
        with repository.session_factory() as session:
            with session.begin():
                session.add(CameraSourceModel(
                    id=source_id, name=f"Perception replay synthetic source ({stream_id})",
                    kind="replay", status="connected",
                    description="Synthetic Source created only for an isolated perception-replay admission run.",
                ))
                session.add(StreamModel(
                    id=stream_id, source_id=source_id,
                    name=f"Perception replay synthetic stream ({stream_id})",
                    description="Synthetic Stream created only for an isolated perception-replay admission run.",
                    is_live=False,
                ))
        repository.set_observation_authority_mode(
            ObservationAuthorityMode.candidate_visit,
            stream_id=stream_id,
            fresh_session=True,
            now=activation_boundary_at,
            **{
                key: value
                for key, value in (
                    ("max_candidates_per_session", max_candidates_per_session),
                    ("max_candidates_per_hour", max_candidates_per_hour),
                )
                if value is not None
            },
        )
        yield repository
    finally:
        repository.close()
        if owns_directory:
            import shutil

            shutil.rmtree(resolved, ignore_errors=True)


def _evidence_candidates_by_generation(
    evidence: Sequence[EvidenceCandidate],
) -> dict[str, list[EvidenceCandidate]]:
    by_generation: dict[str, list[EvidenceCandidate]] = {}
    for candidate in evidence:
        if candidate.track_generation_id is None:
            continue
        by_generation.setdefault(candidate.track_generation_id, []).append(candidate)
    return by_generation


def evaluate_shadow_admission(
    proposals: Sequence[AssembledVisitProposal],
    *,
    repository: ProductRepository,
    stream_id: str,
    evidence_candidates: Sequence[EvidenceCandidate],
    evidence_bytes: Mapping[str, bytes],
    base_observed_at: datetime,
) -> AdmissionReplayReport:
    """Drive every already-assembled proposal through the real Stage 7
    admission path, in deterministic order, using logical time: each
    proposal's `observed_at` is `base_observed_at` shifted by its own
    `start_offset_ms` -- the recorded replay-relative timestamp, never a
    real sleep and never wall-clock `datetime.now()`. This is the harness's
    logical-time mode; there is no other mode.

    `resolve_ambiguous_boundary_arbitration` runs once over the *entire*
    supplied batch first (mirroring `engine_runtime._run_assembly_tick`'s
    own "recompute over everything accumulated so far" discipline), and its
    winners are the only proposals attempted with `ambiguous_boundary_
    resolved=True` -- every other member of an ambiguous cluster is still
    attempted normally and still correctly blocks, exactly as production
    requires (see "Ambiguous boundary arbitration" in
    docs/tracklet-visit-assembly-contract.md).

    Deferred proposals (see `AmbiguousBoundaryArbitration.deferred_ids`) are
    still attempted this pass -- a single bounded replay run has no later
    "tick" to revisit them on, unlike a live session -- so they correctly
    surface as `blocked_ambiguous_boundary` or `blocked_continuation_
    pending`, an honest, disclosed replay-specific limitation (a bounded
    replay window cannot always see whether more stream would have
    resolved an ambiguous or continuation-pending tail), not a fabricated
    verdict.
    """

    require_replay_stream_id(stream_id)
    ordered = tuple(sorted(proposals, key=lambda item: (item.start_offset_ms, item.proposal_id)))
    arbitration = resolve_ambiguous_boundary_arbitration(ordered)
    evidence_by_generation = _evidence_candidates_by_generation(evidence_candidates)
    adapter = CandidateVisitAuthorityAdapter(repository, provider_key="perception-replay-regression-v1")

    outcomes: list[ProposalAdmissionOutcome] = []
    counts: dict[str, int] = {}
    for proposal in ordered:
        relevant_evidence = tuple(
            candidate
            for generation_id in proposal.constituent_generation_ids
            for candidate in evidence_by_generation.get(generation_id, ())
        )
        available_bytes = sum(1 for candidate in relevant_evidence if evidence_bytes.get(candidate.media_asset_id))
        observed_at = base_observed_at + timedelta(milliseconds=proposal.start_offset_ms)
        boundary_resolved = proposal.proposal_id in arbitration.resolved_winner_ids
        result: CandidateAttemptResult = adapter.attempt_candidate(
            proposal,
            evidence_candidates=relevant_evidence,
            evidence_bytes=evidence_bytes,
            observed_at=observed_at,
            ambiguous_boundary_resolved=boundary_resolved,
        )
        outcomes.append(
            ProposalAdmissionOutcome(
                proposal_id=result.proposal_id,
                stream_id=stream_id,
                outcome=result.outcome,
                reason=result.reason,
                visit_id=result.visit_id,
                event_id=result.event_id,
                observed_at=observed_at,
                ambiguous_boundary_resolved=boundary_resolved,
                evidence_candidate_count=len(relevant_evidence),
                evidence_bytes_available_count=available_bytes,
            )
        )
        counts[result.outcome] = counts.get(result.outcome, 0) + 1

    return AdmissionReplayReport(
        stream_id=stream_id,
        outcomes=tuple(outcomes),
        arbitration=arbitration,
        outcome_counts=dict(sorted(counts.items())),
    )


def admission_report_to_json(report: AdmissionReplayReport) -> dict[str, object]:
    """Deterministic, JSON-safe projection -- datetimes as ISO-8601, frozensets
    as sorted tuples, no absolute path or host fact (those belong only in the
    caller's own non-semantic execution/provenance section)."""

    return {
        "stream_id": report.stream_id,
        "outcome_counts": dict(report.outcome_counts),
        "arbitration": {
            "resolved_winner_ids": sorted(report.arbitration.resolved_winner_ids),
            "deferred_ids": sorted(report.arbitration.deferred_ids),
        },
        "outcomes": [
            {**asdict(item), "observed_at": item.observed_at.isoformat()}
            for item in sorted(report.outcomes, key=lambda item: item.proposal_id)
        ],
    }
