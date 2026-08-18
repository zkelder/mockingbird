"""Stage 7 pure candidate-Visit authority gate.

Status: Observation Engine v2 Stage 7 engineering-workflow contract (see
docs/candidate-visit-authority-contract.md). This module decides -- and
never itself performs -- whether one already-assembled, shadow-only
`AssembledVisitProposal` (Stage 6.19, `visit_episode_assembler.py`) may
become a bounded, needs-review candidate Visit.

Pure: no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository,
or SQLAlchemy import -- structurally enforced by
`test_candidate_visit_authority_module_has_no_product_repository_import` the
same way every other Stage 6.x decision module (`reconnect_continuity`,
`session_timeline`, `visit_episode_assembler`) already is. It never reads a
wall clock, a database, or a configuration file itself: every fact this
module needs (current authority mode, the recorded activation boundary,
already-durable session/hourly counts, whether a candidate already exists
for this exact proposal) is supplied explicitly by the caller, and
`observed_at` -- the wall-clock moment the *caller* is evaluating this
proposal -- is likewise an explicit parameter, never `datetime.now()` read
in here. This keeps the gate itself deterministic and independently testable
without a database, exactly like every sibling pure module in this package.

`mockingbird.observation.candidate_visit_adapter` is the one place that
reads live authority state from the product repository, decides
`observed_at`, and finally calls a product-repository write after this gate
returns `"create"`. This module has no knowledge of, and no import path to,
the product database -- see "Persistence adapter boundary" in the contract
doc.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal, Protocol, Sequence, runtime_checkable

AUTHORITY_GATE_VERSION = "candidate-visit-authority-v1"


@runtime_checkable
class ProposalLineage(Protocol):
    """The only shape this gate needs from a proposal -- deliberately a
    structural `Protocol`, not an import of
    `visit_episode_assembler.AssembledVisitProposal`. `AssembledVisitProposal`
    already satisfies this shape unchanged, so the adapter can pass one
    directly; the product repository's own persistence-side lineage record
    (which has no reason to import the observation engine's assembler
    module) can satisfy it too. This is what lets exactly one gate
    implementation be reused for both the adapter's pre-check and the
    repository's own transactional re-check without a cross-import in
    either direction beyond what "VisitEpisodeAssembler -> VisitProposal ->
    authority gate -> product repository" already requires."""

    proposal_id: str
    constituent_generation_ids: tuple[str, ...]
    source_capture_frame_ids: tuple[str, ...]
    supporting_frame_ids: tuple[str, ...]
    ambiguous_adjacent_proposal_ids: tuple[str, ...]
    # Visit Continuity / Provisional Admission Fix v1 (see
    # docs/tracklet-visit-assembly-contract.md "Episode finality"): a fact
    # the assembler already computed (never reconstructed here -- this gate
    # stays a pure consumer, exactly like it already is for `ambiguous_
    # adjacent_proposal_ids`) naming whether a same-encounter continuation
    # tracklet could still be assembled onto this proposal's own tail later.
    continuation_pending: bool


@runtime_checkable
class ProposalArbitrationFacts(Protocol):
    """The only shape `resolve_ambiguous_boundary_arbitration` needs --
    deliberately a separate, narrower structural `Protocol` from
    `ProposalLineage`: arbitration is a *caller-side*, cross-proposal policy
    decision (comparing one proposal against its own ambiguous siblings),
    never something the pure per-proposal authority gate itself computes.
    `AssembledVisitProposal` already satisfies this shape unchanged."""

    proposal_id: str
    ambiguous_adjacent_proposal_ids: tuple[str, ...]
    continuation_pending: bool
    constituent_generation_ids: tuple[str, ...]
    # Only `.max_confidence` is read; any object exposing that attribute
    # (for example `contracts.ConfidenceEvidenceSummary`) satisfies this.
    confidence_evidence: object


@dataclass(frozen=True)
class AmbiguousBoundaryArbitration:
    """One deterministic, per-tick resolution of every currently-ambiguous
    proposal's own boundary-arbitration status against its immediate
    ambiguous-adjacent sibling(s) still present this tick (see "Ambiguous
    boundary arbitration" in docs/tracklet-visit-assembly-contract.md).

    `resolved_winner_ids`: proposals whose own ambiguous cluster (itself,
    plus every one of its listed `ambiguous_adjacent_proposal_ids` that is
    still present this tick) has fully stabilized -- none of them still
    `continuation_pending` -- and which is the single best-evidenced member
    of that cluster. A caller should attempt these with `evaluate_candidate_
    authority(..., ambiguous_boundary_resolved=True)`; every other member of
    a stabilized cluster is attempted normally and correctly still blocks.

    `deferred_ids`: ambiguous proposals whose own cluster has *not* yet
    stabilized (itself or a live sibling is still `continuation_pending`) --
    a same-encounter continuation tracklet could still change the picture,
    exactly the reason `continuation_pending` itself exists. A caller should
    not attempt these at all this tick (never mark them permanently
    attempted), so they are naturally re-offered once more of the stream has
    been observed -- identical in spirit to how an ordinary `continuation_
    pending` proposal is already retried, without needing a new outcome code
    for this case.
    """

    resolved_winner_ids: frozenset[str]
    deferred_ids: frozenset[str]


def _arbitration_key(proposal: ProposalArbitrationFacts) -> tuple[float, int, str]:
    """Deterministic total order for arbitration: strongest detector
    confidence first, then the most constituent evidence (a longer,
    internally-merged tracklet chain), then `proposal_id` as a last-resort,
    arbitrary-but-reproducible tiebreak so a genuine float/count tie never
    makes arbitration ambiguous itself. `max_confidence` reuses exactly the
    same confidence fact Detection Quality Accounting v1 already threads
    from detection through to this layer -- never a new signal."""

    max_confidence = getattr(proposal.confidence_evidence, "max_confidence", None)
    return (max_confidence if max_confidence is not None else -1.0, len(proposal.constituent_generation_ids), proposal.proposal_id)


def resolve_ambiguous_boundary_arbitration(
    proposals: Sequence[ProposalArbitrationFacts],
) -> AmbiguousBoundaryArbitration:
    """Classify every currently-ambiguous proposal in one tick's full,
    freshly-assembled proposal set (see `visit_episode_assembler.
    assemble_visit_episodes`) into "safe to arbitrate now, and wins" or
    "not yet stable, defer."

    Pure and deterministic: a function only of the supplied proposals'
    own already-computed facts, never a wall clock, a database, or pixel
    content. Comparison is local to each proposal's own listed
    `ambiguous_adjacent_proposal_ids` (never a transitive closure across a
    longer chain) -- see "Ambiguous boundary arbitration: chain scope" in
    docs/tracklet-visit-assembly-contract.md for why this bounded, pairwise
    scope is a deliberate, disclosed choice rather than an oversight.

    A proposal with no `ambiguous_adjacent_proposal_ids` at all is untouched
    by this function (never appears in either returned set) -- arbitration
    only ever concerns proposals the assembler itself already flagged as
    boundary-ambiguous.
    """

    by_id = {proposal.proposal_id: proposal for proposal in proposals}
    winners: set[str] = set()
    deferred: set[str] = set()

    for proposal in proposals:
        if not proposal.ambiguous_adjacent_proposal_ids:
            continue
        live_siblings = [
            by_id[sibling_id]
            for sibling_id in proposal.ambiguous_adjacent_proposal_ids
            if sibling_id in by_id
        ]
        if proposal.continuation_pending or any(sibling.continuation_pending for sibling in live_siblings):
            # This proposal, or a sibling it is still ambiguous against, may
            # still grow (a same-encounter continuation tracklet has not yet
            # had its own chance to arrive and change the picture) -- defer,
            # exactly the reason `continuation_pending` exists one layer
            # below. Never decide a permanent winner/loser from an
            # incomplete cluster.
            deferred.add(proposal.proposal_id)
            continue
        cluster = [proposal, *live_siblings]
        best = max(cluster, key=_arbitration_key)
        if best.proposal_id == proposal.proposal_id:
            winners.add(proposal.proposal_id)

    return AmbiguousBoundaryArbitration(resolved_winner_ids=frozenset(winners), deferred_ids=frozenset(deferred))


class ObservationAuthorityMode(str, Enum):
    """Explicit authority state -- deliberately not a boolean (see
    "Authority states" in the contract doc). `shadow` is the only mode that
    may ever be a schema/migration default; only `candidate_visit` may
    persist a candidate Visit. There is no third value in this stage --
    future authority levels are explicitly out of scope."""

    shadow = "shadow"
    candidate_visit = "candidate_visit"


AuthorityOutcome = Literal[
    "create",
    "idempotent_repeat",
    "blocked_shadow_mode",
    "blocked_pre_activation",
    "blocked_invalid_lineage",
    "blocked_ambiguous_boundary",
    "blocked_continuation_pending",
    "blocked_session_limit",
    "blocked_hourly_limit",
]

# Outcomes that represent this proposal never having reached the durable
# ledger at all (as opposed to "create" or the idempotent-repeat fact) --
# the adapter uses this to decide whether to increment its bounded
# "candidates suppressed" diagnostic.
BLOCKED_OUTCOMES: frozenset[AuthorityOutcome] = frozenset(
    {
        "blocked_shadow_mode",
        "blocked_pre_activation",
        "blocked_invalid_lineage",
        "blocked_ambiguous_boundary",
        "blocked_continuation_pending",
        "blocked_session_limit",
        "blocked_hourly_limit",
    }
)

# `blocked_continuation_pending` is never a permanent fact about a given
# `proposal_id` the way every other blocked outcome effectively is (see
# "Continuation-pending policy" below): the identical proposal id, re
# -evaluated later with nothing else changed but more of the stream having
# been observed, can honestly reach a different outcome once its own
# episode boundary finalizes. A caller retrying a "new" proposal across
# repeated assembly passes (`engine_runtime.py`, `candidate_visit_authority
# _cli.py`) uses this to decide which proposal ids are safe to remember as
# permanently resolved versus which must be re-offered on a later pass.
RETRYABLE_OUTCOMES: frozenset[AuthorityOutcome] = frozenset({"blocked_continuation_pending"})


@dataclass(frozen=True)
class AuthorityLimits:
    """Explicit hard bounds for the controlled trial (see "Limits" in the
    contract doc). Every field is caller-configurable so a bounded real
    trial can set tighter values (for example 3 candidates / one session)
    than a long-running default without a second code path."""

    max_candidates_per_session: int = 50
    max_candidates_per_hour: int = 20
    max_evidence_items_per_candidate: int = 4
    max_evidence_bytes_per_candidate: int = 8_000_000

    def __post_init__(self) -> None:
        if not 1 <= self.max_candidates_per_session <= 10_000:
            raise ValueError("invalid_authority_limits")
        if not 1 <= self.max_candidates_per_hour <= 10_000:
            raise ValueError("invalid_authority_limits")
        if not 1 <= self.max_evidence_items_per_candidate <= 16:
            raise ValueError("invalid_authority_limits")
        if not 1024 <= self.max_evidence_bytes_per_candidate <= 64_000_000:
            raise ValueError("invalid_authority_limits")


@dataclass(frozen=True)
class AuthorityState:
    """Durable authority facts the adapter has already read from the product
    repository this call -- a snapshot, never a live handle. `activation_
    boundary_at` is the deterministic activation/start fact recorded the
    moment authority last transitioned from `shadow` to `candidate_visit`
    (see "Activation boundary" in the contract doc); `None` whenever `mode`
    is `shadow` or authority has never been activated. The two counters are
    durable counts the adapter computed from the persisted candidate ledger
    (never an in-memory-only counter that a restart could reset)."""

    mode: ObservationAuthorityMode
    activation_boundary_at: datetime | None
    candidates_created_in_session: int
    candidates_created_in_trailing_hour: int

    @staticmethod
    def default_mode() -> ObservationAuthorityMode:
        """The one and only default: existing installations/configurations
        must not silently gain authority, and no migration may enable it."""
        return ObservationAuthorityMode.shadow

    def __post_init__(self) -> None:
        if self.candidates_created_in_session < 0 or self.candidates_created_in_trailing_hour < 0:
            raise ValueError("invalid_authority_state")


@dataclass(frozen=True)
class AuthorityDecision:
    """One deterministic classification of whether `proposal_id` may create
    a candidate Visit right now. Reason strings are stable, sanitized codes
    -- never a raw exception message, absolute path, or credential."""

    proposal_id: str
    outcome: AuthorityOutcome
    reason: str

    @property
    def should_create(self) -> bool:
        return self.outcome == "create"


def evaluate_candidate_authority(
    proposal: ProposalLineage,
    *,
    observed_at: datetime,
    state: AuthorityState,
    limits: AuthorityLimits | None = None,
    already_exists: bool = False,
    ambiguous_boundary_resolved: bool = False,
) -> AuthorityDecision:
    """Classify one assembled proposal against current authority state.

    Order is deliberate and documented in docs/candidate-visit-authority-
    contract.md's "Authority gate decision order":

    1. Idempotent fact first: whether a candidate already exists for this
       exact `proposal.proposal_id` is a fact about the past, not a policy
       decision, and must be reported identically regardless of the
       *current* mode -- a candidate created while authority was active
       must still be reported idempotent even if authority is later
       disabled (see "Kill switch": "existing candidate Visits remain
       reviewable").
    2. Authority mode: the single most fundamental gate. `shadow` blocks
       every proposal unconditionally, independent of every other fact.
    3. Activation boundary: a proposal observed before the recorded
       activation fact can never create a candidate, even in
       `candidate_visit` mode -- this is what makes turning authority on
       never retroactively promote historical shadow output (see
       "Activation boundary" / "no backlog replay").
    4. Lineage validity: a structural safety check on the proposal itself,
       independent of authority policy. Requires at least one frame
       identity -- `source_capture_frame_ids` (the Stage 6.14 reviewed-
       source identity, populated only when the proposal was assembled
       from a reviewed temporal-review/replay pipeline) when available, or
       `supporting_frame_ids` (the ordinary per-track frame identity every
       Stage 4+ tracker generation already carries, live or replay). A
       genuine live Camera Node session has no reviewed-source identity to
       carry -- that concept only exists for frames a human has already
       retained through temporal-review capture -- so requiring it
       unconditionally would make every real live proposal structurally
       ineligible regardless of evidence quality; requiring *some* real
       frame lineage, preferring the more specific one when it exists,
       still refuses a proposal with no traceable frame identity at all.
    5. Ambiguity policy: a proposal whose own episode boundary the
       assembler could not confidently resolve
       (`ambiguous_adjacent_proposal_ids` non-empty) is conservatively
       blocked rather than persisted with a boundary that might need to
       change -- see "Ambiguity policy" in the contract doc for the full
       rationale -- *unless* the caller explicitly asserts
       `ambiguous_boundary_resolved=True`. This gate never computes that
       fact itself (it has no visibility into sibling proposals): a caller
       sets it only after `resolve_ambiguous_boundary_arbitration` has
       independently confirmed this exact proposal is both the single
       best-evidenced member of its own ambiguous cluster *and* that every
       member of that cluster has itself stopped growing (`not
       continuation_pending`, checked below, for both this proposal and
       every live sibling) -- see "Ambiguous boundary arbitration" in
       docs/tracklet-visit-assembly-contract.md. Every other member of a
       resolved cluster is still attempted with the default `False` and
       still blocks here, exactly as before: at most one Visit is ever
       admitted per ambiguous cluster, never more.
    6. Continuation-pending policy (Visit Continuity / Provisional
       Admission Fix v1): a proposal whose own tail boundary the assembler
       cannot yet certify as final (`continuation_pending`) is
       conservatively blocked for the same reason ambiguity is -- a
       same-encounter continuation tracklet may still be assembled onto it,
       changing its constituent set before it would ever be revisited
       otherwise (Stage 7 candidates are never re-merged after creation).
       Structurally identical to the ambiguity check above: a fact the
       assembler already computed, never reconstructed here. Unlike every
       other blocked outcome, this one is retryable (see
       `RETRYABLE_OUTCOMES`) -- the identical proposal id may honestly
       become eligible later purely because more of the stream has now been
       observed, with nothing else about the proposal changed.
    7. Session budget, then hourly budget: bounded, explicit, durable rate
       limits.
    8. Otherwise: create.
    """

    limits = limits or AuthorityLimits()
    if already_exists:
        return AuthorityDecision(proposal.proposal_id, "idempotent_repeat", "existing_candidate_visit_for_proposal")
    if state.mode != ObservationAuthorityMode.candidate_visit:
        return AuthorityDecision(proposal.proposal_id, "blocked_shadow_mode", "authority_mode_is_shadow")
    if state.activation_boundary_at is None or observed_at < state.activation_boundary_at:
        return AuthorityDecision(
            proposal.proposal_id, "blocked_pre_activation", "proposal_observed_before_activation_boundary",
        )
    has_frame_lineage = bool(proposal.source_capture_frame_ids) or bool(proposal.supporting_frame_ids)
    if not proposal.constituent_generation_ids or not has_frame_lineage:
        return AuthorityDecision(proposal.proposal_id, "blocked_invalid_lineage", "proposal_missing_required_lineage")
    if proposal.ambiguous_adjacent_proposal_ids and not ambiguous_boundary_resolved:
        return AuthorityDecision(
            proposal.proposal_id, "blocked_ambiguous_boundary", "proposal_boundary_ambiguous_with_adjacent_proposal",
        )
    if proposal.continuation_pending:
        return AuthorityDecision(
            proposal.proposal_id, "blocked_continuation_pending", "episode_boundary_not_yet_final",
        )
    if state.candidates_created_in_session >= limits.max_candidates_per_session:
        return AuthorityDecision(proposal.proposal_id, "blocked_session_limit", "session_candidate_budget_exhausted")
    if state.candidates_created_in_trailing_hour >= limits.max_candidates_per_hour:
        return AuthorityDecision(proposal.proposal_id, "blocked_hourly_limit", "hourly_candidate_budget_exhausted")
    reason = (
        "eligible_assembled_proposal_ambiguous_boundary_arbitration_winner"
        if proposal.ambiguous_adjacent_proposal_ids
        else "eligible_assembled_proposal"
    )
    return AuthorityDecision(proposal.proposal_id, "create", reason)
