# Candidate-Visit authority contract

Status: Observation Engine v2 Stage 7 engineering-workflow contract. Composes
unchanged with
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
(Stage 6.19), [reviewed-visit-truth-contract.md](reviewed-visit-truth-contract.md)
(Stage 6.17), and [camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)
(Stage 5). This is the first stage in the Observation Engine v2 sequence that
may write a product-database record; every prior stage (1-6.19) remained
`shadow_only=true`/`creates_truth=false` with no product-repository import
anywhere in the pipeline.

## Problem

Stage 6.19 proved the shadow `VisitEpisodeAssembler` materially reduces
tracker fragmentation on real reviewed wildlife (a sustained ~5-minute visit
consolidates from dozens of raw confirmed generations into a handful of
assembled proposals) while introducing no new fresh-field incorrect merges.
Every one of those assembled `AssembledVisitProposal`s still only exists in
memory, inside whatever process ran the replay or live session -- nothing
about it is visible to a human reviewer. Authority must move exactly one
step: from "an in-memory shadow proposal" to "a bounded, explicitly
machine-marked, needs-review candidate Visit a reviewer can actually see and
correct through the existing Review Queue" -- never further. This stage does
not, and structurally cannot, create `ReviewLabel`, reviewed `Observation`,
confirmed species truth, Bird Log truth, export truth, or analytics truth.

## Authority state

`mockingbird.observation.candidate_visit_authority.ObservationAuthorityMode`
is an explicit two-value `str, Enum` -- deliberately not a boolean:

- `shadow` (default): identical to every prior stage. No candidate Visit can
  ever be created. Live/replay shadow observation, the assembler, and every
  existing production path are completely unaffected.
- `candidate_visit`: the only mode in which
  `ProductRepository.create_candidate_visit_from_proposal` may actually
  persist a Visit. Setting this mode does not itself do anything beyond
  recording the mode and a fresh activation boundary -- no proposal is
  automatically ingested.

Persisted as one durable singleton row
(`ObservationAuthoritySettingsModel`, `observation_authority_settings`
table, `singleton_id=1`) -- the exact same "one settings row, `singleton_id`
primary key" convention `StorageRetentionSettingsModel` already established.
The row is never seeded by a schema migration; `ProductRepository` creates
it lazily, defaulted to `shadow`, the first time authority state is read or
written. An installation that upgrades through Stage 7's migration (schema
version 28) and never touches this feature behaves exactly as if the table
did not exist: reads report shadow defaults from nothing on disk, and no
migration can ever set `mode='candidate_visit'`.

Future authority levels are explicitly out of scope for this stage.

## Session/Stream scope (Visit Authority Budget + Ambiguous-Boundary Recall
## Closure v1)

`ObservationAuthoritySettingsModel` is keyed by `stream_id` (primary key) --
one durable authority row per Stream, never a single global singleton. This
corrects a real, demonstrated 2026-08-19 field defect in the original
`singleton_id=1` design: a shared global row meant one Stream's Stop
silently reverted a *different*, still-running Stream's authority to
shadow, and the session/hourly candidate-budget count was a cross-Stream
total despite its own name. `get_observation_authority_state`/
`set_observation_authority_mode`/`create_candidate_visit_from_proposal`'s
own transactional re-check all resolve exactly one Stream's own row;
`_authority_state`'s session/hourly count queries filter
`ObservationCandidateVisitModel.stream_id` explicitly. A real Stream's own
per-Stream Start/Stop Observation control (see
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md))
is the product's real session unit; the durable authority state it governs
is now scoped to match, not a global implementation artifact left over from
when only a single-Stream CLI trial existed. Schema 35
(`_migrate_to_per_stream_observation_authority`) re-keys the table on
upgrade, safely: the row only ever holds lazily-created diagnostic/mode
state, never truth, and every Stream reverting to the safe `shadow` default
is the correct direction for any installation carrying a stale row forward.

## Activation boundary

`activation_boundary_at` is a deterministic activation/start fact: set fresh
(to the caller-supplied `now`) every time `mode` transitions
`shadow -> candidate_visit`, and cleared back to `None` on every
`candidate_visit -> shadow` transition (the kill switch). Re-affirming an
already-active mode does not reset it, *unless* the caller explicitly
asserts `fresh_session=True` (see "Fresh-session activation," below). A
proposal is only eligible to create a candidate when its own `observed_at`
(the wall-clock moment the adapter first evaluated it -- never recomputed,
never read from the proposal itself, which stays deliberately wall-clock-free
per the assembly contract) is at or after this boundary. This is what makes
turning authority on never retroactively promote historical shadow output:
"no backlog replay into authority when enabling the mode" is enforced
structurally, not by caller discipline alone.

### Fresh-session activation

Real, demonstrated 2026-08-19 field defect: a process that never reached
`stop()`'s kill switch (a crash, `kill -9`, or a mid-session redeploy --
exactly what a real Windows dev-deployment redeploy does) leaves a Stream's
own authority row stuck at `candidate_visit` with a stale, possibly-already-
exhausted `activation_boundary_at`. The *next* literal "Start observing" for
that Stream previously found `mode` already `candidate_visit` and, per the
re-affirmation rule above, never reset the boundary -- silently inheriting
whatever budget the "crashed" prior session had already consumed, in one
real case exhausted from a previous *day's* sessions.

`set_observation_authority_mode` accepts an explicit, caller-supplied
`fresh_session: bool = False`. When `True`, a transition *into*
`candidate_visit` always establishes a fresh `activation_boundary_at`, even
if the row's `mode` was already `candidate_visit` for that Stream. Only
`engine_runtime._EngineSession._run_async` -- the product's own Start path
-- ever passes `fresh_session=True`, exactly once per real "Start observing"
action: `ObservationEngineSessionManager.start()` only ever constructs a
brand-new `_EngineSession` when no session for that Stream is already
`is_active` in this process, so the *only* way this call can ever find
`mode` already `candidate_visit` for that Stream is a stale leftover from a
session that has actually ended (crashed) -- never a genuinely-still-running
session calling Start twice. This makes `fresh_session=True` unconditionally
safe at this one call site: it can never "steal" a still-active session's own
budget, because a still-active session's own `_EngineSession` object already
holds that Stream's only path to this call.

This can only ever move the boundary *forward* in real use (a well-behaved
caller's own `now` is monotonically non-decreasing), never backward -- it
cannot be used to admit an older historical proposal, preserving "no backlog
replay into authority" exactly. The CLI trial
(`candidate_visit_authority_cli.py --activate`) and every other caller omit
`fresh_session`, preserving the original re-affirmation-does-not-reset
behavior unchanged (a trial reactivated mid-run must not be able to sneak a
wider window in).

## Kill switch

There is no separate boolean layered on top of `ObservationAuthorityMode`.
The kill switch *is*
`set_observation_authority_mode(ObservationAuthorityMode.shadow)`. It is
immediate and requires no restart: every candidate-creation attempt re-reads
this row fresh from the database inside its own transaction, never a
cached in-process value, so a change made from any process sharing the
database (a second CLI invocation, a future admin action) takes effect on
the very next attempt anywhere, including inside an already-running trial
process (`test_candidate_visit_repository.py::test_kill_switch_blocks_new_
candidates` and the CLI's own `--activate`/no-`--activate` behavior both
exercise this). Disabling authority never touches an already-created
candidate Visit or its evidence; it remains exactly as reviewable as before
(see "Existing Visit protection").

### Stop-finalization ordering (Sustained-Activity Visit Admission Starvation & Stop-Finalization Correctness v1)

"No candidate can ever be created once a user has pressed Stop" (the kill
switch's own original framing) and "pending, already-force-decided work
must survive Stop" (see "Episode finality"/"Bounded component decision
horizon" in docs/tracklet-visit-assembly-contract.md) are only in tension
if the kill switch's own revert can run *before* the session's own
in-flight finalize tick reaches persistence. Before this fix, it could:
`engine_runtime._EngineSession.stop()` bounded its own `thread.join()` to a
fixed, generous timeout (originally 20s) purely for HTTP-response
responsiveness, but then reverted authority to shadow unconditionally the
instant the join call returned -- on a genuine timeout (the background
thread still alive, most likely to happen under exactly the sustained
-activity load "Bounded component decision horizon" describes, since a
busy session's own finalize tick has more work to do) exactly as much as on
a real completion. `create_candidate_visit_from_proposal` re-reads
authority mode fresh from the repository by design (see "Persistence
adapter boundary," below) -- so a finalize tick that reached it *after*
this premature external revert saw `shadow` and silently discarded an
already-force-decided, genuinely valid candidate as `blocked_shadow_mode`.
This was the real, previously-unresolved "why did stop not rescue the
pending work" question Representative Daylight Gate A Field Acceptance v4
disclosed but left open (that session's own real stop happened not to hit
the race, or hit a different failure entirely -- see that report's own
"open, disclosed, unresolved question").

Fixed by making the join's own outcome authoritative rather than advisory:
`stop()` now only performs its own external, defensive revert-and-`_state`
transition when the background thread has *actually* finished (`not
thread.is_alive()` after the join, or no thread at all -- the shape an
early pre-repository failure produces, the one case this external call
remains the *only* place authority ever reverts). If the join times out
against a thread that is still genuinely running, `stop()` does nothing
further: no premature revert, and `_state` stays `"stopping"` (an honest
signal, not a false claim of success) with `advanced["stop_finalization_
pending"] = True` for a status poll to see. The background thread's own
`_run_async` `finally` chain -- tracker teardown, then the forced-decision
finalize tick, then that same thread's own already-pre-existing revert
-to-shadow, all on one thread, in the correct order, using the SAME
repository connection throughout -- is unconditional (a daemon thread is
never killed by `stop()` returning) and therefore guarantees eventual
completion; `_run()`'s own outer `finally` normalizes `_state` back to
`"stopped"` and clears `stop_finalization_pending` once that thread
genuinely finishes, whether or not the original `stop()` call was still
around to see it. This satisfies the "force-finalization must complete
before the stop operation claims success, OR the stop response must
explicitly indicate pending finalization and guarantee eventual
completion" bar directly: the common case (finalize completes well within
the join's own bound, especially now that "Bounded component decision
horizon" keeps a live session's own backlog small) is still a fully
synchronous, resolved-before-response stop; the rare, slow-finalize case is
honestly disclosed rather than silently discarded. Repeated `stop()` calls
while finalization is still pending remain safe (`set_observation_
authority_mode` is idempotent; `create_candidate_visit_from_proposal`'s own
existing idempotency guarantee makes a second finalize attempt for an
already-decided proposal id a no-op).

## Persistence adapter boundary

```
VisitEpisodeAssembler -> AssembledVisitProposal
                       -> candidate_visit_authority (pure gate)
                       -> candidate_visit_adapter (the one impure seam)
                       -> ProductRepository.create_candidate_visit_from_proposal
```

`mockingbird.observation.candidate_visit_authority` is pure: no filesystem,
network, CUDA/ONNX Runtime/OpenCV, product-repository, or SQLAlchemy import
-- structurally enforced the same way every earlier Stage 6.x decision
module is (`test_candidate_visit_authority_module_has_no_product_repository_
import`). It never reads a wall clock or a database itself; `observed_at`,
authority mode, the activation boundary, and durable session/hourly counts
are all explicit caller-supplied facts (`AuthorityState`). Its own decision
function, `evaluate_candidate_authority`, accepts a small structural
`ProposalLineage` protocol (`proposal_id`,
`constituent_generation_ids`, `source_capture_frame_ids`,
`ambiguous_adjacent_proposal_ids`) rather than importing
`visit_episode_assembler.AssembledVisitProposal` directly -- letting the
product repository's own plain `CandidateVisitProposalFacts` satisfy the
identical protocol and reuse the exact same gate for its own transactional
re-check, with no import in either direction beyond what the pipeline above
already requires.

`mockingbird.observation.candidate_visit_adapter.CandidateVisitAuthorityAdapter`
is the one module in the whole Observation Engine v2 tree that imports both
the assembler's output type and `mockingbird.repository.product_repository`.
It scores already-retained evidence exactly the way Stage 6 already does
(`evidence_scoring.score_proposal_evidence`, completely unmodified), builds
the bounded evidence items it can actually back with real bytes, and calls
the repository. `visit_episode_assembler.py` itself has zero references to
this module, `candidate_visit_authority`, or `mockingbird.repository`
anywhere in its own source (unchanged from Stage 6.19; see
`test_visit_episode_assembler.py::test_no_product_repository_dependency`).

`ProductRepository.create_candidate_visit_from_proposal` is the actual,
concurrency-safe authority boundary: it re-validates mode, activation
boundary, rate budgets, lineage, and Privacy/Ignore Zone safety *inside* the
same transaction that performs the write (serialized by a dedicated
in-process `threading.Lock`, matching this class's own established
single-flight convention -- `_storage_retention_lock`/
`_review_identification_assistant_lock`). The adapter's own pre-check with
the shared pure gate is advisory only; a retried, replayed, reconnected, or
racing call always converges on exactly one Visit because the repository
method itself re-decides, never because the caller was careful.

## Candidate Visit semantics

One accepted `AssembledVisitProposal` may create at most one candidate
Visit, keyed by a durable idempotency ledger row
(`ObservationCandidateVisitModel`, `observation_candidate_visits` table)
whose primary key *is* `AssembledVisitProposal.proposal_id` -- already a
deterministic sha256 of the assembler version plus sorted constituent
generation ids (see
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)),
so it needs no second identity scheme to be stable across retry, process
restart, reconnect, replayed frames, and repeated finalization.

The persisted candidate reuses the existing product model unchanged --
`VisitModel`/`EventModel`, exactly the same tables every other Visit lives
in -- rather than inventing a parallel "CandidateVisit" domain object:

- `EventModel.event_type = "observation_engine_candidate"` (a new stable
  string value, the same convention `"motion_evidence"`/
  `"manual_media_import"`/`"folder_media_import"` already establish for
  event provenance).
- `VisitModel.review_status = "needs_review"` (the existing enum value
  every unreviewed Visit already uses) and `subject_label` set to the
  proposal's own `broad_class` (never a species guess).
- The ledger row (`ObservationCandidateVisitModel`) carries everything else
  Stage 7 must retain: `stream_id`, `zone_id`, `broad_class`,
  source-relative `start_offset_ms`/`end_offset_ms`, `assembler_version`,
  `authority_gate_version`, `constituent_generation_ids_json`,
  `constituent_track_ids_json`, `source_capture_frame_ids_json`,
  `supporting_frame_ids_json`, `evidence_candidate_ids_json`,
  `detector_provenance`/`tracker_provenance`/`provider_key`,
  `selected_identification_media_asset_id`/
  `selected_context_media_asset_id`, `persisted_media_asset_ids_json`,
  `limitation_facts_json`, and `ambiguous_adjacent_proposal_ids_json`.

### Lineage validity: two distinct frame-identity fields

A real bounded trial against the paired Camera Node (see "Real controlled
trial" below) disclosed a genuine gap in the first implementation: a
proposal assembled from a genuine *live* session never populates
`source_capture_frame_ids` at all -- that identity is Stage 6.14's
reviewed-source concept, populated only when a proposal traces back through
the temporal-review/replay pipeline (a human has already retained the
frame). Requiring it unconditionally would have made every real live
proposal structurally ineligible regardless of evidence quality. The
lineage-validity gate now accepts *either* `source_capture_frame_ids` (the
more specific, reviewed-source identity, preferred when present) *or*
`supporting_frame_ids` (the ordinary per-track frame identity every Stage
4+ tracker generation already carries, live or replay) -- refusing only a
proposal with no traceable frame identity at all. Both fields are retained
on the ledger row whenever present; neither is fabricated when absent.

Species identity is never persisted as truth: `VisitModel.species_guess`
and `reviewed_label` stay `None` on creation, always. If a future provider
attaches a species suggestion elsewhere, it remains suggestion evidence only
(`SpeciesSuggestion`), completely outside this stage's write path.

### Candidate identification

A Stage 7 candidate is distinguishable from every other Visit provenance
using existing fields alone, with no duplicate concept introduced:

- `review_status == "needs_review"` (shared with every other unreviewed
  Visit -- correct, since a candidate must use the exact same review
  surface).
- `EventModel.event_type == "observation_engine_candidate"` (unique to this
  stage, mirroring the existing per-provenance `event_type` convention).
- Presence of an `ObservationCandidateVisitModel` row keyed by the Visit's
  own id (`uq_observation_candidate_visit_visit`) -- the authoritative,
  queryable "this Visit was Stage-7-created" fact and full lineage record.

### Concurrent-sibling Event reuse (Multi-Subject Visit Assembly & Review v1, Phase 2)

`AssembledVisitProposal.concurrent_sibling_proposal_ids` (Phase 1, see
"Concurrent-sibling detection" in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md))
names every other proposal this one was classified `incompatible`/
`temporal_overlap` against -- genuinely simultaneous, distinct subjects
sharing one real encounter, never a continuation-timing question. Phase 2
(schema 36, 2026-08-20) is what gives that fact product consequence:
`_create_candidate_visit_locked` calls a new, small, side-effect-free
helper, `_event_id_for_concurrent_siblings`, immediately before minting an
`EventModel` -- a bounded `proposal_id IN (...)` lookup (defensively
re-filtered to the same `stream_id`, mirroring the Privacy/Ignore Zone
check just above it) against the existing ledger's own primary key. If any
listed sibling already has a persisted candidate, this candidate reuses
that sibling's own `event_id` instead of minting a new one; otherwise it
mints a new `EventModel` exactly as before this milestone. No new table, no
secondary index, no change to `VisitModel`'s own shape.

This is grouping, never a reason to admit: everything above this point in
`_create_candidate_visit_locked` -- authority mode, activation boundary,
lineage validity, the ambiguity/continuation-pending policies below, rate
budgets, evidence-quality admission, and scene-confusor suspicion -- already
ran unmodified, per-proposal, before this check is ever reached. One
sibling's own rejection (missing evidence, scene-confusor suspicion, a
budget exhausted) never blocks, delays, or degrades a different,
independently evidence-backed sibling; a sibling this proposal lists that
was never itself persisted (rejected, not yet attempted, or genuinely
absent) simply means this candidate mints its own new Event, identical to
the ordinary single-subject path. Order-independent by construction: for a
three-or-more-subject encounter, whichever sibling is persisted first is
found by whichever is persisted next, regardless of attempt order -- proven
directly for a real nuthatch-plus-two-finches encounter shape, attempted
out of order, in `tests/test_candidate_visit_adapter.py`.

The ledger row's own `concurrent_sibling_proposal_ids_json` (schema 36,
additive nullable column, mirroring `_migrate_to_observation_geometry_
lineage`'s exact pattern) retains this candidate's own sibling relationship
as diagnostic lineage -- never re-read to decide grouping for a *different*
candidate, which always looks the sibling up directly by `proposal_id`
instead. `None` for a ledger row that predates this concept; never a
fabricated relationship. The `"created"` outcome's own `reason` string
distinguishes `candidate_visit_created` (a new Event -- the unchanged,
ordinary single-subject string, byte-identical to every pre-Phase-2 Visit)
from `candidate_visit_created_shared_event` (a reused Event) -- the minimum
new observability this milestone needed, reusing the existing free-text
`reason` field rather than a new counter or table.

Species identity remains exactly as isolated per sibling as it already is
per any Visit: `VisitModel.species_guess`/`reviewed_label` stay `None` on
creation for every sibling, identically. Review/correction remains
per-Visit and per-sibling: reviewing one sibling Visit never implicitly
confirms, reviews, or touches another sibling's own `review_status` or
`ReviewLabel` history -- this was already true of every Visit under the
existing, completely unmodified `create_review_label` path, and sharing an
`event_id` changes nothing about it (see "Authority and limitations,"
below, and "Review Decision Provenance" in
[architecture.md](architecture.md)).

## Ambiguity policy

A proposal whose own `ambiguous_adjacent_proposal_ids` is non-empty -- the
assembler itself could not confidently resolve this proposal's boundary
against a temporally-adjacent one -- is conservatively **blocked**
(`blocked_ambiguous_boundary`), not persisted with a boundary that might
legitimately need to change. Locking in a possibly-wrong episode grouping as
a persisted candidate is a worse failure than not creating one yet: Stage 7
candidates are never automatically re-merged, re-split, or have their
historical timing rewritten once created (see "Existing Visit protection"),
so an ambiguous boundary is exactly the case where persisting now would
foreclose a better answer later. The shadow proposal itself remains fully
visible through existing shadow/replay diagnostics either way; this policy
only decides Stage 7's own persistence action.

**Ambiguous boundary arbitration (Admission Recall Investigation +
Conditional Fix v1):** a real ~94-minute accepted daily-use session found
the block above was, unlike the continuation-pending policy below, a
genuinely *permanent* verdict with no recovery path at all -- including for
a confirmed detection above `strong_detection_threshold` and for a
well-evidenced, cleanly-merged 14-generation episode that kept absorbing
continuation evidence without ever being reconsidered (see "Ambiguous
boundary arbitration" in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
for the full field evidence and mechanism). `evaluate_candidate_authority`
now accepts one additional, explicit, caller-supplied fact,
`ambiguous_boundary_resolved: bool = False`: when `True`, this proposal
skips the block above (falling through to every check below it,
unchanged). This gate never computes that fact itself -- it has no
visibility into sibling proposals -- so it may only ever be asserted by a
caller that already ran `candidate_visit_authority.resolve_ambiguous_
boundary_arbitration` over the full current tick's proposal set and
confirmed this exact proposal is both the single best-evidenced member of
its own ambiguous cluster *and* that every member of that cluster
(including this one) has itself stopped growing (`not continuation_
pending`). Every other member of a resolved cluster is still attempted
with the default `False` and still blocks here exactly as before: at most
one Visit is ever admitted per ambiguous cluster, so the original
duplicate-Visit protection this policy exists to provide is fully
preserved.

**Chain scope closed (Ambiguous-Boundary Transitive Fragmentation Closure
v1, 2026-08-20):** "ambiguous cluster" above now always means the full
bounded connected component of `ambiguous_adjacent_proposal_ids` links, not
only a proposal's own immediately-listed neighbors -- closing a real
defect where a sequential chain (A-B ambiguous, B-C ambiguous, A-C never
directly compared) could let both `A` and `C` independently win
arbitration against their shared neighbor `B`, admitting two Visits for
one connected, still-ambiguous encounter. See "Chain scope" in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
for the complete mechanism and prior history. Contained entirely within
`candidate_visit_authority.resolve_ambiguous_boundary_arbitration`; this
gate's own decision order and every other check are unchanged.

**Fallback contract (Pending-Proposal Evidence Preservation & Arbitration
Fallback Correctness v1):** Representative Daylight Gate A Field
Acceptance v6 found a real, concrete instance of a risk the "Evidence-cache
capacity" section below had already named but left unaddressed: a real
arbitration winner reached `ambiguous_boundary_resolved=True` correctly,
then permanently failed one gate later at evidence availability
(`blocked_missing_evidence`), with no code path ever reconsidering the
same resolved component -- 48/263 distinct proposals (18.3%) lost this way
in one real session. `resolve_ambiguous_boundary_arbitration` now also
returns `fallback_order_by_winner_id: Mapping[str, tuple[str, ...]]`: for
each winner, every *other* stable member of that exact same connected
component, ranked best-first by the identical key that chose the winner
(`_forced_decision_key` for a forced decision, `_arbitration_key`
otherwise -- never a new heuristic). This module still computes no new
policy and remains unaware of evidence bytes entirely; it only exposes the
order a caller may safely walk.

`engine_runtime._EngineSession._attempt_resolved_component` is that
caller: it attempts the winner, then -- only if the winner's own outcome
is genuinely about *this proposal's* evidence (`blocked_missing_evidence`,
`reject_no_identification_or_context`, `reject_subject_geometry_invalid`)
rather than a component-wide or infrastructure fact
(`blocked_privacy_zone`, `blocked_scene_confusor_suspected`,
`reject_insufficient_proposal_support`, a repository `"failed"`) -- the
next-ranked member, and so on, stopping at the first admissible member or
once the component is exhausted. Every member still attempted with the
default `ambiguous_boundary_resolved=False` once the chain settles blocks
exactly as before: at most one Visit is ever admitted per component,
unchanged. Every resolved component is walked as one atomic unit, in a
pass over `resolved_winner_ids` that completes *before* any ordinary,
non-component proposal is attempted at all -- `new_proposals`' own
emission order has no guaranteed relationship to arbitration rank, so
branching per-proposal on "is this a winner" while iterating that list
directly let a losing-but-fallback-eligible sibling reached first take the
ordinary path (and get marked permanently attempted) before its own
winner's chain ever ran, corrupting bookkeeping with a duplicate attempt
once the chain later reached it -- found by this milestone's own
adversarial self-review, fixed before it reached a committed test. See
this milestone's own report for the full RED/GREEN account, the exactly-
once/multi-subject/stop-finalization proofs, and the 105-simulated-minute
v6-shaped replay against the real bounded cache.

## Continuation-pending policy (Visit Continuity / Provisional Admission Fix v1)

A proposal whose own `continuation_pending` is `True` -- the assembler
itself cannot yet certify this proposal's own tail boundary as final,
because a same-encounter continuation tracklet could still be assembled
onto it later (see "Episode finality" in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md))
-- is conservatively **blocked** (`blocked_continuation_pending`), checked
immediately after the ambiguity policy above and for the identical reason:
persisting now would foreclose the assembler's own already-correct merge
decision, which real 2026-08-10 evidence proved matters (candidate-004 was
admitted, then a strict-superset continuation merged and was admitted
*again* 56 seconds later as candidate-005, for one real ~75-second
encounter). Unlike every other blocked outcome, this one is retryable
(`candidate_visit_authority.RETRYABLE_OUTCOMES`): the identical `proposal_
id` may honestly become eligible on a later attempt purely because more of
the stream has now been observed, with nothing else about the proposal
changed -- so a caller must not treat this outcome as a permanent fact the
way every other blocked outcome already is (see `engine_runtime.
_EngineSession._run_assembly_tick`'s own retry bookkeeping). This gate adds
no new tracker/assembler logic of its own; it only ever reads a fact the
assembler already computed, exactly like the ambiguity policy it sits next
to.

## Idempotency and concurrency

Proven at three layers (`tests/test_candidate_visit_repository.py`):
same-proposal replay, a simulated process restart (`ProductRepository`
re-opened against the identical on-disk database file), and eight
concurrent threads racing the identical request -- every case converges on
exactly one created candidate and the rest report `idempotent_repeat` with
the same `visit_id`. Session/hourly rate counts are computed live from the
ledger table on every attempt (`select count(...) where created_at >= ...`)
-- never an in-memory-only counter a restart could reset.

## Existing Visit protection

`create_candidate_visit_from_proposal` never touches an existing Visit row:
it only ever inserts a brand-new `VisitModel`/`EventModel`/
`ObservationCandidateVisitModel`/`MediaAssetModel` set, or (idempotent case)
reads one back unchanged. There is no merge-into-reviewed-Visit path, no
historical-timing-rewrite path, and no attach-new-machine-evidence-to-an-
existing-Visit path anywhere in this stage.
`test_candidate_visit_repository.py::test_candidate_creation_does_not_
mutate_an_unrelated_reviewed_visit` proves a pre-existing reviewed Visit's
full row (`review_status`, `reviewed_label`, `species_guess`, `confidence`)
is byte-identical before and after a Stage 7 create.

## Evidence persistence

Stage 7 persists only already-selected, already-bounded evidence -- never
the analysis stream. The adapter calls the unmodified Stage 6
`evidence_scoring.score_proposal_evidence` scorer, then builds a
`CandidateEvidenceItem` only for the identification/context/alternate picks
it actually has real bytes for; a pick with no retrievable bytes is
honestly skipped, never fabricated. The repository bounds the persisted set
to `max_evidence_items_per_candidate` (default 4) and
`max_evidence_bytes_per_candidate` (default 8 MB), and requires at least
one persistable item -- zero persistable evidence fails safely
(`blocked_missing_evidence`) rather than creating an evidence-less
candidate. Every persisted `MediaAssetModel` carries `trigger_id =
proposal_id` (an existing v24 provenance field, reused rather than
duplicated) and `derivation_source = "observation_engine_candidate"`, plus
`evidence_role` (`identification`/`context`/`alternate`, plus the
separately-slotted, non-competing `classifier_same_frame` -- see Same-Frame
Species Evidence v1) and `normalized_track_box_json` from the candidate's
own subject geometry when known.

**All-Alternate Subject Evidence Recall Correctness v1** (see docs/all-
alternate-subject-evidence-recall-correctness-v1-report.md): a proposal
whose identification/context picks both fail to survive to admission (real
bytes never harvested, or independently ineligible), but whose
`classifier_same_frame` item does, is no longer discarded outright
(`reject_no_identification_or_context`) purely because that role never
competes for identification/context. `evaluate_evidence_admission` treats
it as a narrowly-scoped last-resort `primary` in exactly that one case --
never displacing a real identification/context pick, and still subject to
the same geometry-validity/detector-corroboration checks unchanged.

For the real live trial, evidence is sourced only from the live session's
own bounded high-resolution burst cache
(`LiveCameraNodeShadowSession.temporary_burst_payload`, keyed by content
hash) -- the "already-captured real evidence burst" this stage's own
evidence-persistence policy names first. Ordinary tracked/pretrigger
analysis frames are not retained as recoverable bytes by the live session at
all (only used for inference, matching "do not persist the entire analysis
stream"), so a live trial's candidates are backed exclusively by real burst
frames; a proposal with no captured/retained burst fails safely rather than
persisting without real evidence. This is a deliberate, disclosed scope
choice for the first trial, not a defect -- broadening evidence sourcing to
ordinary tracked frames is future, separately-scoped work.

### Evidence-cache capacity (Visit Authority Budget + Ambiguous-Boundary
### Recall Closure v1)

`engine_runtime._EngineSession` harvests each burst-role/same-frame-role
candidate's real bytes out of the live session's own transient cache the
moment it is first observed (`_harvest_burst_bytes`/`_harvest_same_frame_
bytes`), into its own longer-lived `burst_bytes_cache`/`same_frame_bytes_
cache` -- because the underlying live-session cache is cleared on `session.
stop()`, and a proposal's own admission attempt can be legitimately delayed
well past capture time (`blocked_ambiguous_boundary` pending arbitration
stabilization, or `blocked_continuation_pending` for up to `ambiguous_gap_
ms`, 45s, per retry cycle -- see "Ambiguous boundary arbitration" in
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)).
Real, evidenced 2026-08-19 field defect: reconstructing both missed strong
encounters (~5.0min/34-generation/0.889-confidence and ~8.67min/40-
generation/0.846-confidence) against the real captured counterfactual ledger
found the proposal that actually escaped the ambiguity block in each cluster
(either never ambiguous, or an arbitration winner) still permanently failed
at evidence admission (`reject_no_identification_or_context`) -- not because
no evidence was ever captured, but because `_MAX_CACHED_BURST_BYTES`/
`_MAX_CACHED_SAME_FRAME_BYTES` (previously 8) is evicted purely by insertion
count, with no awareness of which pending proposal still needs which bytes;
unrelated activity elsewhere in a busy real stream cycled past it before the
delayed proposal's own attempt ever ran. Raised to 32 -- a capacity fix, not
an evidence-quality threshold change: every requirement `candidate_quality_
gate.evaluate_evidence_admission` enforces (a real, decodable, geometrically
-valid identification/context candidate) is completely unchanged; this only
keeps evidence already judged sufficient from vanishing before its own
legitimately-delayed admission attempt runs. Verified directly:
`test_delayed_proposal_still_finds_its_evidence_after_unrelated_cache_churn`
in `tests/test_engine_runtime.py` reproduces the exact real failure shape
with the old bound (RED) and stays fixed with the new one (GREEN). The
ambiguous-boundary arbitration mechanism itself needed no change -- real
evidence (proposals reaching the evidence-quality gate at all) proves it
already correctly narrows each cluster to one winner in both missed
encounters; the loss happened one stage downstream, at evidence retention.

**Superseded bound, current value:** a busier 2026-08-19 session
(End-to-End Bird Encounter Recall Closure v1) found this same mechanism's
32-entry bound still insufficient under real, busier load and raised it
again to **128** (same relative 4x jump; RED/GREEN-verified against that
session's own real generation/timing/confidence shape; zero regression
across every replayed cohort). The mechanism above (harvest-before-eviction)
is unchanged and still accurately described; only the specific bound is
current-as-of-32 in this section's own historical narration. See
[end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
§9 for the complete defect/fix account, and "Gate A" in
[roadmap.md](roadmap.md) for why this remains an open item: the raised
bound is RED/GREEN-verified but still needs one live field proof under real
busy-session load.

### Selection-priority and generation-scope fixes (Sustained-Activity Visit Admission Starvation & Stop-Finalization Correctness v1)

The 128-entry bound above was field-validated against delays on the order of
tens of seconds to a few minutes (natural `blocked_continuation_pending`/
`blocked_ambiguous_boundary` resolution). "Bounded component decision
horizon" (see [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md))
introduces a *forced* decision on the order of tens of *minutes* for a
sustained-activity component -- a materially longer delay this bound was
never exercised against. Investigated directly (per this section's own
governing brief: "if this materially contributes to starvation or poor
forced-finalization behavior, fix it narrowly"), rather than simply raised
again (a fourth capacity bump repeating this section's own established
"capacity fix, not a structural fix" caveat, without addressing why a
forced-decision winner's evidence keeps being unreachable regardless of the
bound's exact size):

- **Forced-decision winner selection now prefers recency over confidence**
  (`candidate_visit_authority._forced_decision_key`, used only for a forced
  decision -- an ordinary, naturally-stabilized component is unaffected,
  still ranked by confidence exactly as before). A forced decision exists
  specifically so a component does not defer forever; crowning a
  historically-best-scoring member whose own evidence has, by construction,
  had far longer to rotate out of the bounded cache than any naturally
  -resolving component ever would just moves the identical "zero Visits"
  symptom one gate later (`blocked_missing_evidence`, reproduced directly
  before this fix). The winner-selection pool also now excludes any member
  that is itself still `continuation_pending` -- such a member would fail
  `evaluate_candidate_authority`'s own step-6 gate regardless of the
  step-5 ambiguity bypass a forced decision grants, wasting an attempt.
- **`evidence_scoring.score_proposal_evidence` now prefers byte-available
  candidates under its own `max_candidates` (16) truncation**, before
  falling back to the original offset-first order. A long-lived,
  forced-decision proposal can carry far more retained evidence-candidate
  facts than that bound; the old, plain offset-first order always kept the
  *earliest* (therefore most likely already-evicted) ones, even when
  byte-backed evidence existed elsewhere in the same proposal. See
  [multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)
  "Bounds."
- **A multi-generation-merged proposal's `track_generation_id` is now
  `None`** (`visit_episode_assembler.project_to_visit_proposal`), not a
  fabricated single (first-constituent) value -- see
  [multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)
  "Boundary." This was the dominant mechanism in this milestone's own
  worst-case reproduction: real evidence is tagged with the *specific*
  constituent generation active at capture time, almost always not the
  proposal's own first one, so the scorer's `track_generation_id` guard
  silently excluded the great majority of a merged proposal's own real,
  byte-backed evidence regardless of the truncation-order fix above. A
  genuinely single-generation proposal (the common case) is unaffected.

Together, reproduced directly against the real, unmodified scorer and the
real, bounded 128-entry cache: a forced-decision winner with real evidence
for less than half its own constituent generations (115 of 240, in the
worst-case shape this milestone's own investigation constructed) now
correctly reaches `create` instead of `blocked_missing_evidence`. See this
milestone's own report for the full RED/GREEN account.

### Preservation contract (Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness v1)

Representative Daylight Gate A Field Acceptance v6 field-measured that the
128-entry bound above, raised twice already, is still a bound, not a
structural fix: `_harvest_burst_bytes`/`_harvest_same_frame_bytes` evict
the single oldest-inserted key the instant a new one arrives, with zero
awareness of whether that key belongs to a still-actionable pending
proposal. Rather than a fourth capacity bump (explicitly rejected --
representative field evidence does not support treating a numeric bound as
the intended contract), eviction is now pending-proposal-aware:

- `engine_runtime._compute_protected_evidence_ids`, called once per
  assembly tick, considers every proposal not yet in `attempted_proposal_
  ids` "still actionable" (an ordinary about-to-be-attempted proposal, a
  still-growing ambiguous component's own deferred member, or another
  stable member of a component resolving this same tick, needed for a
  same-tick fallback attempt -- see below). For each, `CandidateVisitAuthorityAdapter.
  priority_evidence_ids` previews -- via the unmodified `evidence_scoring.
  score_proposal_evidence`, using whatever bytes the caller's own caches
  *currently* hold, never `media=None` (real, live-captured evidence never
  declares `decodable=True` upfront, so a bytes-free preview would hard-
  reject every real candidate and protect nothing) -- which small handful
  of ids would actually be selected right now.
- The resulting ids are unioned, oldest-`start_offset_ms`-first (the
  proposals genuinely at risk; a proposal's own most recent capture is,
  by construction, also the cache's own most recent insertion, safe
  regardless of protection), into a bounded `set[str]`
  (`_MAX_PROTECTED_EVIDENCE_IDS = 64`, half of either cache's own
  capacity -- protection can never consume an entire cache) -- cleared and
  recomputed fresh every tick, never accumulated, so a resolved or
  superseded proposal loses its own protection automatically the very
  next tick.
- `_harvest_burst_bytes`/`_harvest_same_frame_bytes` now evict via
  `_select_eviction_victim`: the oldest-inserted key *not* currently
  protected (falling back to the literal oldest key only if every entry
  happens to be protected -- deterministic, always evicts something,
  should not normally be reachable given the 64/128 headroom). Capacity
  exhaustion (more still-actionable priority evidence than the 64-id
  budget allows) is counted, never silent.

Both mechanisms -- preservation here, and "Fallback contract" above --
were implemented together and are independently tested; the v6-shaped
105-simulated-minute replay (real bounded cache, real eviction, two
simultaneous subjects) confirms bounded, non-zero admission survives real
cache pressure. See this milestone's own report for the complete account,
including a design correction found before any test run relied on it
(the `media`-mapping requirement above) and one found by adversarial
self-review after initial tests passed (the fallback-ordering fix
described in "Fallback contract").

## Privacy / Ignore

Subjects inside a Privacy or Ignore Zone are already excluded upstream of
every Observation Engine v2 provider: the frame-driven tracker discards any
detection centered inside an excluded region before a track ever forms (see
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)),
so no evidence candidate -- and no `AssembledVisitProposal` -- should ever
legitimately carry a masked Zone. `create_candidate_visit_from_proposal`
still checks `ZoneModel.zone_type` explicitly before creating anything
(`blocked_privacy_zone`) as defense in depth, exactly mirroring the same
explicit check `_promote_motion_evidence_model`/
`create_motion_evidence_from_saved_media` already perform at this
persistence boundary.

## Failure behavior

A genuine repository/storage failure (never an ordinary policy rejection,
which returns a typed outcome instead) raises one sanitized `ValueError`
from inside the failed transaction, which rolls back completely -- no
partial Visit/Event/MediaAsset/ledger row can ever survive
(`test_persistence_failure_rolls_back_and_creates_no_partial_truth`). The
adapter catches it, records a bounded, sanitized failure diagnostic
(`ProductRepository.record_observation_authority_failure`, a
separate small transaction from the failed one), and returns an ordinary
`"failed"` outcome -- it never re-raises, so a live observation loop driving
the adapter continues to its next frame/proposal
(`test_repository_failure_is_caught_and_recorded_not_raised`).

## Limits

`AuthorityLimits` (`max_candidates_per_session`, `max_candidates_per_hour`,
`max_evidence_items_per_candidate`, `max_evidence_bytes_per_candidate`) are
explicit, bounded, and caller-configurable -- generous defaults (50/20/4/8MB)
for general operation, overridden to the trial-mandated 3-candidate session
bound by `candidate-authority-trial`'s own CLI. `create_candidate_visit_
from_proposal` never ingests a historical backlog: only proposals whose
`observed_at` is at or after the current activation boundary are eligible
at all, regardless of budget headroom. The safety bound itself is
unconditionally preserved by this contract's own Visit Authority Budget +
Ambiguous-Boundary Recall Closure v1 fix (above) -- it is scoped correctly
(per Stream, per genuinely-new session), never raised or removed: a
genuinely still-active session that exhausts its own real budget must, and
does, still block (`blocked_session_limit`) exactly as before.

## Diagnostics

`ProductRepository.get_observation_authority_state(stream_id=...)` is a
side-effect-free read (never creates the settings row) returning, for one
Stream: current mode, activation boundary, configured limits, live
session/hourly counts, and bounded lifetime counters
(`proposals_observed_count`, `candidates_attempted_count`,
`candidates_created_count`, `idempotent_repeat_count`, `suppressed_count`,
`failure_count`, `last_failure_code`/`last_failure_at`,
`last_candidate_visit_id`, `last_proposal_id`). No admin UI is added in this
stage.

### Health/diagnostic truth for budget exhaustion (Visit Authority Budget +
### Ambiguous-Boundary Recall Closure v1)

A legitimately exhausted in-session budget (`blocked_session_limit`, a real,
non-retryable outcome for the rest of the current activation window -- see
"Limits," below) must never be silently absorbed into an otherwise-healthy
status: a Stream can stay genuinely `observing`/`engine_available` while
unable to create any further Visit, and that fact must be surfaced
truthfully rather than presented as ordinary full productivity.
`_EngineSession` tracks `candidate_authority_exhausted: bool` (set the first
time this running session observes a `blocked_session_limit` outcome; sticky
for the rest of the session, matching the outcome's own permanent-for-this-
activation-window semantics -- a fresh Start always begins with it `False`
again) plus a plain-language `candidate_authority_message`. Both flow through
`ObservationEngineSessionStatus` -> `unified_status.ObservationPanelFacts` ->
the `ObservationSessionStatusResponse` wire contract unchanged in shape,
reaching `GET /api/streams/{id}/observation/status` and the Observation
panel's basic view (`ObservationControlPanel.tsx`) -- not buried in advanced
diagnostics alone, since this is exactly the kind of truthful health fact a
normal user needs without opening internal counters. Raw internal counters
(configured budget, consumed count, activation/session identity, exhaustion
timestamp/reason) remain in the existing `advanced` diagnostics object
(`activation_boundary_at`, `counts.suppressed_reasons` including
`blocked_session_limit`'s own count) -- reused, not duplicated, per "do not
expose internal counters as ordinary UI clutter."

## Real controlled trial

`python -m mockingbird candidate-authority-trial` (see module docstring in
`candidate_visit_authority_cli.py`) reuses Stage 5's
`CameraNodeAnalysisSource`/`CameraNodeHttpTransport`/
`LiveCameraNodeShadowSession` completely unchanged -- the same convention
`temporal_capture_cli.py` already established -- for a hard-bounded
duration (`--duration-seconds`, capped at 600) and a hard-bounded candidate
stop condition (`--max-candidates`, capped at 3). It periodically reruns
`build_tracklets`/`assemble_visit_episodes` over the live session's own
accumulated `TrackUpdate`s (the assembler itself remains a post-hoc pass
over finalized, confirmed generations, exactly as Stage 6.19 designed it --
this trial does not add a live incremental assembler) and, only with
`--activate`, attempts a real candidate through the real
`CandidateVisitAuthorityAdapter` against the real product database. Without
`--activate`, authority state is read but never changed, so the trial is a
safe, hardware-connectivity/mechanics-only dry run identical in effect to
ordinary shadow observation.

### Real trial results (2026-08-08, paired Raspberry Pi Camera Node)

A dry run (45s, no `--activate`) connected to the real Node, ran real ONNX
Runtime CUDA MegaDetector inference (RTX 4060 Ti), observed 2 real
assembled proposals, and correctly reported `blocked_shadow_mode` for both
-- zero product writes beyond the additive schema migration itself (44 to
46 tables; one lazily-created `observation_authority_settings` row,
`mode=shadow`). A first activated attempt (300s) surfaced the lineage gap
above: all 24 real assembled proposals were `blocked_invalid_lineage`. With
that fixed, a second activated attempt (300s, `--max-candidates 3`)
observed 14 real assembled proposals -- 6 `blocked_missing_evidence` (no
retrievable high-resolution burst), 6 `blocked_ambiguous_boundary` (the
assembler's own conservative policy), and **2 genuine candidate Visits
created** from real 4624x3472 burst evidence of a backyard feeder tree,
both `needs_review`, both with complete lineage, neither self-reviewed. A
full structural snapshot before/after found changes exactly attributable to
the two candidates (`+2` each to `visits`/`events`/`media_assets`/
`visit_evidence_links`/the ledger table, `+2` to `product_alerts` from the
existing, unrelated "Visit ready for review" alert mechanism every
needs-review Visit already triggers) and zero changes to `review_labels` or
any reviewed Visit. The kill switch (`ObservationAuthorityMode.shadow`) was
then exercised against the same real database: a new proposal attempt
immediately reported `blocked_shadow_mode`, both real candidates remained
present and `needs_review`, and a final snapshot confirmed zero further
change. See the Stage 7 final report for the complete acceptance matrix.

## Authority and limitations

This stage opens the product database -- the first Observation Engine v2
stage to do so -- but only ever through
`create_candidate_visit_from_proposal`'s own narrow, transactional,
idempotent write path, and only when `mode == candidate_visit`. It cannot
create a `ReviewLabel`, mark a Visit reviewed, write a confirmed species
guess, create a reviewed `Observation`, or touch Bird Log/analytics/export
truth by itself under any input -- every one of those remains reachable
only through the exact existing, completely unmodified
`ProductRepository.create_review_label` correction path
(`tests/test_candidate_visit_review_workflow.py`). It changes no detector,
tracker, reconnect, burst-scheduler, evidence-scoring, session-timeline, or
Privacy/Ignore-masking behavior, and grants no further authority level --
future authority levels beyond `candidate_visit` are explicitly out of
scope for this stage.
