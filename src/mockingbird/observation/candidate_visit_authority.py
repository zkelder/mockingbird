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

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Literal, Mapping, Protocol, Sequence, runtime_checkable

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
    # Sustained-Activity Visit Admission Starvation & Stop-Finalization
    # Correctness v1 (see "Bounded component decision horizon" in
    # docs/tracklet-visit-assembly-contract.md): this proposal's own
    # earliest/latest constituent tracklet offsets -- `start_offset_ms` is
    # what `resolve_ambiguous_boundary_arbitration`'s own bounded-decision-
    # horizon check needs to measure how long a whole connected component
    # has been waiting for a decision; both are what `_forced_decision_key`
    # needs to prefer the most recently active member once a decision is
    # actually forced (see that function's own docstring for why recency,
    # not confidence, is the right ranking there). Never reconstructed
    # here (this stays a pure consumer, exactly like every other field on
    # this Protocol); `AssembledVisitProposal` already carries both
    # unchanged.
    start_offset_ms: int
    end_offset_ms: int


@dataclass(frozen=True)
class AmbiguousBoundaryArbitration:
    """One deterministic, per-tick resolution of every currently-ambiguous
    proposal's own boundary-arbitration status, evaluated over its full
    bounded *connected component* of ambiguous-adjacent relationships still
    present this tick (see "Ambiguous boundary arbitration" in
    docs/tracklet-visit-assembly-contract.md, and "Chain scope" there for
    the Ambiguous-Boundary Transitive Fragmentation Closure v1 history of
    this specific field).

    `resolved_winner_ids`: proposals whose own connected ambiguous
    component (itself, plus every proposal transitively reachable through
    `ambiguous_adjacent_proposal_ids` links still present this tick) has
    fully stabilized -- none of them still `continuation_pending` -- and
    which is the single best-evidenced member of that *whole* component. A
    caller should attempt these with `evaluate_candidate_authority(...,
    ambiguous_boundary_resolved=True)`; every other member of a stabilized
    component is attempted normally and correctly still blocks -- at most
    one winner per component, never per locally-listed pairwise set.

    `deferred_ids`: ambiguous proposals whose own connected component has
    *not* yet stabilized (itself or any proposal anywhere in the same
    component is still `continuation_pending`) -- a same-encounter
    continuation tracklet could still change the picture for any member of
    the component, exactly the reason `continuation_pending` itself exists.
    A caller should not attempt these at all this tick (never mark them
    permanently attempted), so they are naturally re-offered once more of
    the stream has been observed -- identical in spirit to how an ordinary
    `continuation_pending` proposal is already retried, without needing a
    new outcome code for this case.

    `fallback_order_by_winner_id`: Pending-Proposal Evidence Preservation &
    Arbitration Fallback Correctness v1 (see "Fallback contract" in
    docs/candidate-visit-authority-contract.md). For each id in
    `resolved_winner_ids`, the *other* stable members of that exact same
    connected component -- never a different component, never a still-
    growing member -- ranked best-first by the identical deterministic key
    that chose the winner itself (`_forced_decision_key` for a forced
    decision, `_arbitration_key` otherwise; see each key's own docstring).
    This is real field evidence's own answer to "what should authority try
    next if the chosen winner cannot actually produce an admissible
    Visit": Representative Daylight Gate A Field Acceptance v6 found a real
    arbitration winner permanently fail at the downstream evidence-
    availability gate, with no runner-up ever attempted, silently losing an
    entire real, confirmed activity component. This module still never
    knows *why* a winner might fail (it has no evidence-byte awareness at
    all, by design) -- it only ever exposes the deterministic order a
    caller (`engine_runtime._run_assembly_tick`) may safely walk if the
    winner cannot be admitted. A winner id absent here (or mapped to an
    empty tuple) has no other stable component member -- ordinary for a
    two-member pair once the loser is excluded, and always the case for a
    winner with an otherwise-empty `ambiguous_adjacent_proposal_ids`,
    though such a proposal is never a key in `resolved_winner_ids` at all.
    """

    resolved_winner_ids: frozenset[str]
    deferred_ids: frozenset[str]
    fallback_order_by_winner_id: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


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


def _forced_decision_key(proposal: ProposalArbitrationFacts) -> tuple[int, int, float, int, str]:
    """Ranking used only for a *forced* decision (see
    `resolve_ambiguous_boundary_arbitration`'s own docstring, "Bounded
    component decision horizon" in docs/tracklet-visit-assembly-contract.md,
    and the real defect this closes, disclosed in this milestone's own
    report): prefers the most recently active member, never the highest-
    confidence one.

    A forced decision exists specifically so a component does not defer
    forever. Picking a historically-best-scoring member whose own evidence
    has, by construction, had far longer to rotate out of the bounded
    evidence cache than any *naturally*-resolving component ever would (a
    forced decision only ever fires once a component's oldest member has
    been pending for `maximum_component_pending_ms` -- an order of
    magnitude longer than the delay the evidence cache's own capacity was
    field-validated against, see "Evidence-cache capacity" in
    docs/candidate-visit-authority-contract.md) accomplishes nothing: it
    just moves the identical "zero Visits" symptom one gate later
    (`blocked_missing_evidence` at the quality gate, instead of an
    unresolved arbitration) -- reproduced directly, deterministically,
    against the real bounded 128-entry cache before this second fix.

    Recency is the one proposal-level fact this pure module can reason
    about without any cache awareness of its own: the bounded evidence
    cache evicts in insertion (therefore capture-time) order, so the most
    recently active member is the one most likely to still have real,
    retrievable evidence. `end_offset_ms` first (a proposal's own most
    recent activity), `start_offset_ms` next (prefers a proposal active for
    longer, all else equal, as a secondary recency signal), then the
    unmodified `_arbitration_key` tuple as a final, deterministic tiebreak
    -- confidence still decides among equally-recent members, so a genuine
    tie never produces an ambiguous result. Never used for a *naturally*
    -resolved component (every pre-existing test/behavior for that case is
    completely unchanged -- see `resolve_ambiguous_boundary_arbitration`'s
    own call site)."""

    max_confidence, generation_count, proposal_id = _arbitration_key(proposal)
    return (proposal.end_offset_ms, proposal.start_offset_ms, max_confidence, generation_count, proposal_id)


def _ambiguous_component(seed_id: str, by_id: dict[str, ProposalArbitrationFacts]) -> list[str]:
    """Bounded, iterative (never recursive) traversal of every proposal id
    transitively reachable from `seed_id` by following only `ambiguous_
    adjacent_proposal_ids` links -- never a `concurrent_sibling_proposal_ids`
    link (this function, like `ProposalArbitrationFacts` itself, has no
    knowledge of that field at all) and never a proposal id absent from
    `by_id` (a sibling no longer present this tick is a dead end, identical
    in spirit to the pre-existing "missing sibling this tick is treated as
    no rival" rule -- see `test_arbitration_missing_sibling_this_tick_is_
    treated_as_no_rival`). `assemble_visit_episodes` always records an
    ambiguous link symmetrically (both directions at once), so this
    traversal reaches the identical component regardless of which member is
    used as the seed or what order its neighbors are visited in -- order-
    independence comes from that graph symmetry, not from sorting here.

    An explicit list-as-stack keeps this a plain, bounded loop: real
    component sizes are a handful of temporally-adjacent tracklet fragments
    from one encounter, never an unbounded graph, but an iterative form is
    used regardless so stack depth can never scale with recursion depth."""

    component = [seed_id]
    seen = {seed_id}
    stack = [seed_id]
    while stack:
        current = by_id[stack.pop()]
        for neighbor_id in current.ambiguous_adjacent_proposal_ids:
            if neighbor_id not in by_id or neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            component.append(neighbor_id)
            stack.append(neighbor_id)
    return component


def resolve_ambiguous_boundary_arbitration(
    proposals: Sequence[ProposalArbitrationFacts],
    *,
    known_horizon_ms: int | None = None,
    maximum_component_pending_ms: int | None = None,
) -> AmbiguousBoundaryArbitration:
    """Classify every currently-ambiguous proposal in one tick's full,
    freshly-assembled proposal set (see `visit_episode_assembler.
    assemble_visit_episodes`) into "safe to arbitrate now, and wins" or
    "not yet stable, defer."

    Pure and deterministic: a function only of the supplied proposals'
    own already-computed facts, never a wall clock, a database, or pixel
    content.

    Ambiguous-Boundary Transitive Fragmentation Closure v1: resolves the
    full bounded *connected component* reachable from each proposal via
    `ambiguous_adjacent_proposal_ids` links (see `_ambiguous_component`),
    not only its immediately-listed neighbors. This replaces the prior
    pairwise-only scope, which let a real defect through: given a temporal
    chain A-B ambiguous, B-C ambiguous (A and C never directly listing each
    other -- the real shape a temporal sequence produces, since the
    assembler only ever compares a tracklet against the tail of a still-open
    episode), the old pairwise ranking let `A` and `C` each independently
    beat their shared neighbor `B` in their own local comparison and both
    win arbitration -- two admitted Visits for one connected, still-
    ambiguous chain (see "Ambiguous boundary arbitration: chain scope" in
    docs/tracklet-visit-assembly-contract.md for the full prior account).
    At most one winner is now ever selected per connected component,
    preserving "at most one Visit per ambiguous cluster" as originally
    intended rather than only per locally-listed pair.

    A proposal with no `ambiguous_adjacent_proposal_ids` at all is untouched
    by this function (never appears in either returned set) -- arbitration
    only ever concerns proposals the assembler itself already flagged as
    boundary-ambiguous. Bounded to exactly the proposals supplied this call
    (one tick, one Stream's own session -- see "No cross-session/Stream
    propagation"): this function holds no state between calls, and a
    component can never include a proposal id absent from `proposals`.

    Sustained-Activity Visit Admission Starvation & Stop-Finalization
    Correctness v1 (see "Bounded component decision horizon" in
    docs/tracklet-visit-assembly-contract.md): `known_horizon_ms`/
    `maximum_component_pending_ms` are optional, purely-additive,
    source-offset-relative facts (never a wall-clock read, matching every
    other bound in this package) -- omitted (the default), a still-growing
    component defers *unconditionally*, exactly the pre-existing behavior
    every caller/test before this fix already relies on. Real field
    evidence (Representative Daylight Gate A Field Acceptance v4: ~112
    minutes of real, sustained, near-continuous multi-bird feeder activity
    producing zero admitted Visits for the entire session) proved this
    unconditional defer is unbounded in practice: each successive
    `maximum_episode_duration_ms`-capped episode fragment from one sustained
    activity source can become transitively ambiguous-linked to the next,
    and because a component's own currently-active tail is, by definition,
    still growing for as long as raw activity continues, the *entire*
    component -- including everything transitively linked to it, all the
    way back to the start of the session -- stays deferred for the whole
    remaining life of the session. Individual episodes are already
    correctly bounded (`maximum_episode_duration_ms` caps one episode's own
    span; `ambiguous_gap_ms` caps how long any one proposal's own tail may
    stay `continuation_pending` once it truly stops growing); the gap is
    structural, not a wrong value: nothing previously bounded how long the
    *connected component* as a whole may keep deferring while its own tail
    keeps being refreshed by new activity.

    When both are supplied, a component whose own oldest member (by
    `start_offset_ms`) has been waiting longer than `maximum_component_
    pending_ms` (measured against `known_horizon_ms`) is force-arbitrated
    even though some member is still `continuation_pending` -- the same
    `_arbitration_key` ranking still picks the single best-evidenced
    member; forcing *when* a component may be decided never changes *how*
    its winner is chosen. Every other member (including one that is itself
    still growing) is still attempted normally and still blocks, exactly
    preserving "at most one Visit per ambiguous cluster." A member cut off
    mid-growth by a forced decision is not lost: a tracklet that later
    continues merging onto its own tail produces a new, larger, never-
    before-attempted proposal id on a later tick, offered again through
    this same, unmodified path.
    """

    by_id = {proposal.proposal_id: proposal for proposal in proposals}
    winners: set[str] = set()
    deferred: set[str] = set()
    visited: set[str] = set()
    fallback_order: dict[str, tuple[str, ...]] = {}

    for proposal in proposals:
        if not proposal.ambiguous_adjacent_proposal_ids or proposal.proposal_id in visited:
            continue
        component_ids = _ambiguous_component(proposal.proposal_id, by_id)
        visited.update(component_ids)
        component = [by_id[member_id] for member_id in component_ids]
        still_growing = any(member.continuation_pending for member in component)
        stable_members = [member for member in component if not member.continuation_pending]
        forced = (
            still_growing
            and bool(stable_members)
            and _component_pending_horizon_exceeded(
                component,
                known_horizon_ms=known_horizon_ms,
                maximum_component_pending_ms=maximum_component_pending_ms,
            )
        )
        # `bool(stable_members)` above matters: a proposal that is itself
        # still `continuation_pending` fails `evaluate_candidate_authority`'s
        # own gate 6 unconditionally, regardless of the ambiguous-boundary
        # bypass a forced decision grants at gate 5 (see "Continuation
        # -pending policy" in docs/candidate-visit-authority-contract.md --
        # the two checks are independent). Forcing a decision while *every*
        # member is still individually growing would only ever crown a
        # winner that fails on its own merits one gate later -- wasting an
        # attempt, never producing a Visit. This is a narrow, self
        # -correcting transitional window (the horizon check is keyed on
        # the component's own *oldest* member's `start_offset_ms`, which can
        # cross the bound slightly before that same member's own `end_
        # offset_ms` naturally clears `ambiguous_gap_ms`): the very next
        # tick or two, once at least one member has genuinely gone quiet,
        # `forced` becomes true again automatically -- no new state, no
        # caller change needed.
        if still_growing and not forced:
            # Any member of the *whole* component still growing means the
            # component's own shape could still change -- a same-encounter
            # continuation tracklet could still merge into any member,
            # potentially re-linking or absorbing others -- so the entire
            # component defers, never only the growing member's immediate
            # neighbors. Never decide a permanent winner/loser from an
            # incomplete component, unless the bounded decision horizon
            # above has already been exceeded.
            deferred.update(component_ids)
            continue
        # `forced` ranks only among `stable_members` (never a still-growing
        # one, for the reason above) using `_forced_decision_key` (recency
        # -first -- see its own docstring for why); an ordinary, naturally
        # -stabilized component (`still_growing` already false for every
        # member, so `stable_members == component`) ranks the full
        # component with the unmodified confidence-first `_arbitration_key`
        # -- every pre-existing test/behavior for that common case is
        # completely unaffected by this fix.
        pool = stable_members if forced else component
        # `sorted(..., reverse=True)[0]` rather than a separate `max(...)`
        # call: both `_arbitration_key`/`_forced_decision_key` end in a
        # unique `proposal_id` tiebreak, so no two distinct proposals can
        # ever tie -- the ranked order below always agrees with `max()`'s
        # own "first maximal item" pick, while also giving the *rest* of
        # the ranking for free, which `max()` alone would discard.
        ranked = sorted(pool, key=_forced_decision_key if forced else _arbitration_key, reverse=True)
        best = ranked[0]
        winners.add(best.proposal_id)
        fallback_order[best.proposal_id] = tuple(member.proposal_id for member in ranked[1:])

    return AmbiguousBoundaryArbitration(
        resolved_winner_ids=frozenset(winners), deferred_ids=frozenset(deferred),
        fallback_order_by_winner_id=fallback_order,
    )


def _component_pending_horizon_exceeded(
    component: Sequence[ProposalArbitrationFacts],
    *,
    known_horizon_ms: int | None,
    maximum_component_pending_ms: int | None,
) -> bool:
    """Bounded-decision-horizon check backing `resolve_ambiguous_boundary_
    arbitration`'s own forced-decision policy (see that function's
    docstring for the full field-evidenced rationale): has this component's
    own oldest member been waiting for a decision longer than the caller's
    bound allows? `False` whenever either fact is omitted -- preserves the
    exact prior, unconditional-defer behavior for every pre-existing
    caller/test."""

    if known_horizon_ms is None or maximum_component_pending_ms is None:
        return False
    oldest_start_ms = min(member.start_offset_ms for member in component)
    return (known_horizon_ms - oldest_start_ms) > maximum_component_pending_ms


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
