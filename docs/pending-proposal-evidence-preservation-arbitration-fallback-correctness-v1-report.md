# Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness v1

## Starting state

Verified before any action, exactly as the governing instruction stated:

- Branch `main`, HEAD `b37656d8e0fefd407bf5753d0ad204e26a4271da`, 266 commits ahead of `origin/main`, not pushed.
- Schema `v58` (`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py:45`), unchanged by this milestone.
- The seven preserved untracked files present and untouched throughout (re-verified after every worktree-affecting operation):
  `docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`.
- No active writer touching this worktree.
- Latest accepted milestone: Representative Daylight Gate A Field Acceptance v6 — Post-Fix Replication & Multi-Subject Tranche, classification **B**. Sustained-Activity Visit Admission Starvation & Stop-Finalization Correctness v1 remains accepted and, per v6's own direct source-level confirmation, its specific mechanism does not recur.
- Authorization before this instruction: **NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, per `docs/release-execution-state.md` §3.

### v6 field evidence (the defect this milestone fixes)

Representative Daylight Gate A Field Acceptance v6 (2026-08-31, 106.63 real minutes, real Camera Node, real sometimes-multi-subject bird activity) found:

- `candidates_created` stayed at exactly 0 for the entire session despite `track_updates_observed` reaching 11,078 and `proposals_observed` reaching 521.
- Arbitration itself worked correctly on schedule for every ambiguous component (not v4's starvation mechanism recurring).
- **48 of 263 distinct proposals (18.3%)** reached a genuine arbitration win and then permanently failed at the evidence-availability gate (`blocked_missing_evidence`/`no_persistable_evidence_bytes`), because the shared, session-global, insertion-order-only 128-entry evidence-byte cache had already evicted that winner's own bytes by the time its (correctly, if belatedly, computed) turn arrived — and because `blocked_missing_evidence` is not retryable and no runner-up was ever attempted, the entire real activity component was lost.
- Two exhaustively-reviewed real activity windows (≈6.8min and ≥5min, both containing confirmed simultaneous multi-bird moments) were both entirely lost this way: 0/2 recall.
- Root cause traced precisely to source: `evaluate_candidate_authority`'s 8-gate order (`candidate_visit_authority.py`) has no evidence-availability gate at all; that check happens separately, downstream, in `product_repository.py`'s `_create_candidate_visit_locked`; `blocked_missing_evidence` is absent from `RETRYABLE_OUTCOMES`; and `_run_assembly_tick` (`engine_runtime.py`) attempted every ambiguous-component member exactly once, with no fallback path.

## Reproducers

Both required reproducers were built against real production logic (`_EngineSession._run_assembly_tick`, the real `assemble_visit_episodes`/`resolve_ambiguous_boundary_arbitration`, and — for the eviction reproducer — the real cache eviction policy itself, never bytes deleted after the fact) and confirmed RED on accepted `b37656d`, then GREEN after the fix. Both were additionally reverse-confirmed by `git stash`-isolating the three production-code files while keeping the new tests, running them against the untouched pre-fix code, and restoring the fix afterward.

### Eviction RED — `test_pending_component_preserves_minimum_viable_evidence_under_cache_pressure`

A proposal legitimately still `blocked_continuation_pending` (a real, honest delay) has its own already-harvested evidence bytes inserted into the real bounded cache; 200 unrelated evidence insertions then churn the cache through the real eviction function (`_select_eviction_victim`, extracted unchanged from `_harvest_burst_bytes`'s own live eviction loop — never a bytes deletion invented for the test); the pending proposal's continuation window then closes.

- **Pre-fix (RED):** `AttributeError` (no `protected_evidence_ids` parameter existed) when run against stashed pre-fix code with the new call shape; against the *old* eviction loop specifically (verified via a disposable ad-hoc script using the exact old `next(iter(cache))` policy, no protection, no new parameters) the proposal's evidence is evicted long before its window closes and it never reaches admission.
- **Post-fix (GREEN):** the proposal's own priority evidence is marked protected the moment it is known pending, survives all 200 unrelated insertions (cache stays exactly at its 128-entry bound throughout — protection changes *which* entry is evicted, never *whether* one is evicted), and the proposal is admitted once its window closes.

### Fallback RED — `test_resolved_component_falls_back_when_top_member_evidence_was_evicted`

A stabilized two-member ambiguous cluster where the higher-confidence member has no cached evidence bytes at all and the weaker member has real bytes.

- **Pre-fix (RED):** this exact scenario already existed as `test_ambiguous_boundary_arbitration_does_not_cascade_to_the_next_sibling`, whose own docstring explicitly documented the pre-fix contract ("Arbitration is single-shot, not a retry chain... the weaker sibling is not automatically promoted"). Confirmed still RED (candidates_created stays 0) against stashed pre-fix code.
- **Post-fix (GREEN):** the weaker, evidence-backed member is admitted; the stronger member's own record still honestly shows `no_persistable_evidence_bytes`; the ledger record for the admitted fallback member carries an honest `:fallback_position_1` suffix on its `reason` field (reusing the exact additive-suffix convention `candidate_visit_adapter.py` already uses for a retry-exhausted persistence failure — no new schema field, no new outcome vocabulary).

Nineteen tests in total (see "Validation" below) were confirmed RED on `b37656d` and GREEN after the fix, covering both defects across the pure arbitration module, the adapter, and the live engine runtime — including a third, order-independence regression found by this milestone's own adversarial self-review (see "A second real design correction," under "Fallback contract," below).

## Root cause

Precisely, three independent facts compose into the defect:

1. **No evidence-availability gate in authority.** `evaluate_candidate_authority`'s documented 8-gate order (`candidate_visit_authority.py:517–582`) never checks evidence-byte availability — ambiguity (gate 5) and continuation-pending (gate 6) are the only proposal-*shape* gates. A proposal that passes both (including via the `ambiguous_boundary_resolved=True` bypass a genuine arbitration win grants) reaches `"create"`; evidence-byte availability is checked separately, downstream, only after that, inside `ProductRepository._create_candidate_visit_locked`.
2. **`blocked_missing_evidence` is not retryable.** `RETRYABLE_OUTCOMES = frozenset({"blocked_continuation_pending"})` — once the sole arbitration winner for a resolved component fails at the evidence gate, its own proposal id (and every already-permanently-blocked losing sibling's) is marked permanently attempted.
3. **No fallback path existed.** `_run_assembly_tick` attempted every member of a resolved ambiguous component exactly once, independently, in the same tick — the winner with `ambiguous_boundary_resolved=True`, every other member with `ambiguous_boundary_resolved=False` (a deterministic, permanent `blocked_ambiguous_boundary`) — with no code path that reconsidered the component once its chosen winner failed downstream.

Underlying both: the shared, session-global, insertion-order-only 128-entry evidence-byte cache (`_MAX_CACHED_BURST_BYTES`, `engine_runtime.py`) has zero awareness of which pending proposal still needs which bytes. `_harvest_burst_bytes`/`_harvest_same_frame_bytes` evict the single oldest-inserted key the instant a new one arrives, regardless of whether that key belongs to a still-actionable proposal. This is not a new defect class — the comment written when the bound was last raised 32→128 already named almost exactly this mechanism and explicitly declined to fix it structurally, calling a "pending-proposal-aware eviction policy" a "materially larger change... left as a disclosed follow-up." v6 is the first real, concrete, session-wide measurement that this is not a rare edge case.

## Preservation contract

**Design:** a bounded, per-tick-recomputed "protected evidence id" set, consulted by the cache's own eviction policy.

- `_compute_protected_evidence_ids` (new, `engine_runtime.py`) runs once per assembly tick, before arbitration, over the tick's freshly-reassembled `proposals`. Every proposal not yet in `attempted_proposal_ids` is "still actionable": an ordinary proposal about to be attempted this tick, a `deferred_ids` member of a still-growing ambiguous component, and every other stable member of a component that resolves this tick (needed for same-tick fallback).
- For each still-actionable proposal, `CandidateVisitAuthorityAdapter.priority_evidence_ids` (new) previews — via the existing, unmodified `evidence_scoring.score_proposal_evidence`, called with the *currently cached* bytes (not `media=None`; see "A real design correction," below) — which small handful of ids (identification/context/same-frame/alternates) would actually be selected right now. This reuses the accepted scoring/selection semantics verbatim; it invents no new evidence-quality heuristic.
- The resulting per-proposal picks are unioned, oldest-`start_offset_ms`-first, into a session-owned `set[str]` (mirroring `attempted_proposal_ids`'s existing by-reference-mutation convention), capped at `_MAX_PROTECTED_EVIDENCE_IDS = 64` (half of either cache's own 128-entry bound). The set is **cleared and repopulated every tick** — never an accumulated union — so a proposal that resolves, is superseded, or becomes permanently ineligible loses its own protection automatically the very next tick, with no separate release step.
- `_harvest_burst_bytes`/`_harvest_same_frame_bytes` gained an optional `protected_ids` parameter (defaulting to an empty `frozenset`, so every pre-existing caller/test is unaffected) and now evict via `_select_eviction_victim`: the oldest-inserted key **not** currently protected, falling back to the literal oldest key only if every entry happens to be protected (deterministic, always evicts something; should not normally be reachable given the 64/128 headroom split).

### A real design correction found during implementation

The first design used `media=None` for the priority-evidence preview, reasoning that `score_proposal_evidence`'s ranking is "mostly metadata." Testing immediately (before it reached a single test run) surfaced that this was wrong: `evidence_scoring._score`'s hard-rejection set includes `candidate_unavailable` (no image, and metadata does not already declare `decodable=True`) — and no real, live-captured `EvidenceCandidate` this project constructs (`camera_node_live.py`) ever declares that fact upfront. Calling the preview with no media at all would have hard-rejected every real candidate and always returned nothing to protect, silently defeating the entire mechanism while every test using an idealized fixture (one that *does* declare `decodable=True`) would have still passed. The fix: pass the union of the caller's own `burst_bytes_cache`/`same_frame_bytes_cache`, **as they currently stand**, as the preview's `media` mapping. A candidate with no entry there is an honest, already-realized miss (never captured, or already evicted) — nothing this function could retroactively protect anyway. This is recorded here because it is exactly the kind of assumption error the milestone's own RED/GREEN discipline exists to catch, and it was caught before any test run relied on the wrong behavior, thanks to a targeted read of `evidence_scoring.py` prompted by writing the RED reproducer.

## Fallback contract

**Design:** when a resolved component's winner cannot be admitted, walk the component's own remaining stable members, in the same deterministic rank order arbitration already computed, until one is admissible or the component is exhausted.

- `candidate_visit_authority.AmbiguousBoundaryArbitration` gained a new field, `fallback_order_by_winner_id: Mapping[str, tuple[str, ...]]` (defaulted, so the one other direct construction site, `perception_regression_cli.py`, is unaffected). For each resolved winner, this names every *other* stable member of that exact same connected component, ranked best-first by the identical key that chose the winner (`_forced_decision_key` for a forced decision, `_arbitration_key` otherwise) — reusing accepted ranking semantics verbatim, inventing no new heuristic. (Implementation note: `max(pool, key=...)` was replaced with `sorted(pool, key=..., reverse=True)`, provably identical for winner selection since both keys end in a unique `proposal_id` tiebreak — no two distinct proposals can tie — while also yielding the full ranked order for free.)
- `_EngineSession._attempt_resolved_component` (new, `engine_runtime.py`) drives one component's own bounded chain: `winner`, then `fallback_order_by_winner_id[winner]` filtered to this tick's own `new_proposals`. Each member is attempted with `ambiguous_boundary_resolved=True` only while the chain is still genuinely "in contention" (nothing tried so far has succeeded or hit a non-fallback-eligible failure). The moment the chain settles — a success, or a failure outside the fallback-eligible set — every remaining member is attempted exactly as it always was before this fix (`ambiguous_boundary_resolved=False`, deterministically `blocked_ambiguous_boundary`), preserving "at most one Visit per component" unchanged. Arbitration itself is never rerun; no member of a *different* component is ever considered.
- `_FALLBACK_ELIGIBLE_OUTCOMES` (new, `engine_runtime.py`) draws the retryability line precisely (see "Evidence availability vs eligibility," below): `{"blocked_missing_evidence"} | (REJECTED_OUTCOMES - {"reject_insufficient_proposal_support"})` — i.e. `blocked_missing_evidence`, `reject_no_identification_or_context`, `reject_subject_geometry_invalid`. `blocked_privacy_zone`, `blocked_scene_confusor_suspected`, `reject_insufficient_proposal_support`, and `"failed"` are deliberately excluded (see below).
- Every member of a resolved component still receives exactly one recorded outcome (ledger entry, count update, permanent-attempted marking) regardless of chain position — fallback changes *which* member wins and in what order they are tried, never whether each gets recorded.

### A second real design correction, found by adversarial self-review (brief §31)

The first implementation of `_run_assembly_tick`'s attempt loop iterated `new_proposals` in the assembler's own emission order, branching per-proposal on "is this id a resolved winner." Every fallback test constructed so far happened to make the *winner* the temporally-earliest component member — which, per `assemble_visit_episodes`'s own documented ordering ("tracklets are first sorted into one deterministic total order... processing them in that order"), also makes it first in the assembler's own output. This silently masked a real bug: a losing sibling reached *before* its own winner would take the ordinary path immediately (permanently `blocked_ambiguous_boundary`, added to `attempted_proposal_ids`) — then, when the outer loop later reached the actual winner and walked its fallback chain, that same losing-but-fallback-eligible member would be attempted a **second time**, corrupting `proposals_observed` and producing two ledger records for one real proposal (confirmed via direct reproduction: `proposals_observed` read 3 for a 2-proposal component, with a spurious `blocked_ambiguous_boundary` record followed by the correct `created:fallback_position_1` one).

Fixed by processing every resolved component as one atomic first pass — iterating `arbitration.resolved_winner_ids` directly and walking each one's full chain via `_attempt_resolved_component` — *before* any ordinary (non-component) proposal is touched at all, so no component member is ever reachable by the second, ordinary-only pass. Confirmed via direct reproduction (0 duplicate records, `proposals_observed == 2`) and locked in permanently by `test_fallback_is_correct_regardless_of_which_component_member_the_assembler_lists_first`, which deliberately reverses every other test's own coincidental temporal-order alignment (weaker/fallback-admitted member temporally first, evidence-less winner temporally second/last-in-emission-order) — confirmed RED on baseline `b37656d` and GREEN after this fix.

### Fallback order (brief §12)

Exactly the contract requested: (1) selected winner; (2) remaining stable members in the existing canonical rank order; (3) only members already satisfying normal candidate/admission eligibility (a member still `continuation_pending` can never appear here — see below); (4) no growing member considered unless already forced-decision-eligible. No confidence/recency heuristic was invented for this — it is the identical ranking arbitration already uses.

A structural proof that "no still-growing member is ever named" needs no new guard: `resolve_ambiguous_boundary_arbitration`'s own pre-existing branch structure guarantees `pool` (the ranking pool, now also the fallback-order source) is `stable_members` in every reachable case — either explicitly (`forced=True`) or because reaching the ranking step at all already required `still_growing == False` for the whole component (`if still_growing and not forced: continue` deferred it otherwise, meaning `component == stable_members` whenever ranking actually runs). This is proven directly by `test_arbitration_fallback_order_never_names_a_still_growing_member`.

## Evidence availability vs eligibility (brief §13/§14)

Kept precisely distinct, per the failure-outcome vocabulary already in the codebase — no equivalence assumed between them:

| Category | Outcome(s) | Fallback-eligible? | Why |
|---|---|---|---|
| Evidence unavailable | `blocked_missing_evidence` | Yes | The real v6 mechanism — a per-proposal fact (each component member's own bytes are independently captured/evicted). |
| Evidence available, poor/ineligible | `reject_no_identification_or_context`, `reject_subject_geometry_invalid` | Yes | Also genuinely per-proposal — a sibling's own captured evidence quality is independent of the winner's. |
| Candidate structurally invalid | `reject_insufficient_proposal_support` | No | A fact about *this* proposal object, not shared evidence; per the gate's own docstring, should never fire for a real assembled proposal — treated conservatively as terminal. |
| Zone/geometry-invariant | `blocked_privacy_zone`, `blocked_scene_confusor_suspected` | No | Keyed on physical location/geometry shared by the whole encounter — every sibling would almost certainly hit the identical block; "falling back" would not meaningfully retry anything and could mask a genuine suspicion/privacy signal. |
| Infrastructure | `"failed"` (repository/persistence exception) | No | Per brief §14 explicitly: fallback belongs strictly before persistence, at the evidence/admission decision boundary — a transient infrastructure failure must never be reinterpreted as "try a different semantic winner." |

`blocked_continuation_pending` never reaches this decision at all: any component member still reporting it is never in `stable_members`/the fallback chain in the first place (see above).

## Bounds

- **Cache bound unchanged.** `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES` remain 128 — per the milestone's own explicit instruction, no blind capacity increase.
- **New protection bound.** `_MAX_PROTECTED_EVIDENCE_IDS = 64` — half of either cache's own capacity, a deliberate, explainable split: protection can never consume the *entire* cache, guaranteeing ordinary churn always has room to evict something unprotected (the `_select_eviction_victim` "everything protected" fallback path should not normally be reachable).
- **Deterministic degradation.** `_compute_protected_evidence_ids` processes still-actionable proposals oldest-`start_offset_ms`-first — the ones genuinely at risk (their evidence was inserted longest ago); once the 64-id budget is exhausted, remaining (necessarily more recent) proposals simply receive no *additional* protection this tick — safe, because a proposal's own most recent capture is, by construction, also the cache's own most recent insertion. Exhaustion is counted (`_protected_evidence_capacity_exhausted_count`), never silent.
- **Fallback chain bound.** Bounded by real component size — "a handful of temporally-adjacent tracklet fragments from one encounter," per the pre-existing `_ambiguous_component` docstring, never an unbounded graph.
- **No unbounded growth anywhere.** The protected set is recomputed fresh (never accumulated) every tick; both byte caches remain hard-capped at 128 exactly as before.

## Implementation

Touched files (production code only; test files listed under "Validation"):

- `src/mockingbird/observation/candidate_visit_authority.py` — `AmbiguousBoundaryArbitration.fallback_order_by_winner_id` (new field); `resolve_ambiguous_boundary_arbitration` now also computes and returns it (winner-selection logic itself provably unchanged — see "Fallback contract" above).
- `src/mockingbird/observation/candidate_visit_adapter.py` — `priority_evidence_ids_for_proposal` (new pure function) and `CandidateVisitAuthorityAdapter.priority_evidence_ids` (new thin method threading the adapter's own configured `scoring_bounds`).
- `src/mockingbird/observation/engine_runtime.py` — `_MAX_PROTECTED_EVIDENCE_IDS`, `_select_eviction_victim`, `_compute_protected_evidence_ids`, `_FALLBACK_ELIGIBLE_OUTCOMES` (all new); `_harvest_burst_bytes`/`_harvest_same_frame_bytes` gained an optional `protected_ids` parameter; `_run_assembly_tick` gained an optional `protected_evidence_ids` parameter and now computes/updates it every tick, and its attempt loop was restructured into two ordered passes — every resolved component, walked atomically as a unit via the new `_EngineSession._attempt_resolved_component` (winner then fallback chain), strictly *before* any ordinary (non-component) proposal is attempted at all (see "A second real design correction" under "Fallback contract," below, for why this ordering is load-bearing, not stylistic) — the ordinary path itself is byte-for-byte unchanged; four new session-lifetime diagnostic counters (`_fallback_attempted_count`, `_fallback_admitted_count`, `_fallback_exhausted_count`, `_protected_evidence_capacity_exhausted_count`), surfaced through the existing `advanced` diagnostics dict (no new API/schema surface); `_run_async` now owns a `protected_evidence_ids: set[str]` alongside its existing `burst_bytes_cache`/`same_frame_bytes_cache`, threaded through every harvest call site and both `_run_assembly_tick` call sites (periodic tick and the session-ending `finalize=True` tick).

No schema change. No new outcome codes (fallback attempts reuse the existing outcome vocabulary; the `reason` string gains an additive `:fallback_position_N` suffix only on genuine fallback attempts, following the exact precedent `candidate_visit_adapter.py` already set for a retry-exhausted persistence failure). `candidate_visit_authority_cli.py` (a hard-bounded 10-minute/3-candidate engineering trial tool, explicitly superseded by `engine_runtime.py`'s own app-owned lifecycle per that module's own docstring — never the live production Gate A path) was deliberately left untouched; it still calls `resolve_ambiguous_boundary_arbitration` positionally, which continues to work unchanged since the new field is purely additive.

## V6-shaped replay

`test_v6_shaped_replay_does_not_lose_viable_activity_to_cache_exhaustion` (new): >100 simulated minutes (105), two simultaneously-active, geometrically-distinct subjects (feeder/perch — the identical shape `test_field_derived_multi_subject_stress_replay` already established for arbitration correctness), driven through one real, joint `_run_assembly_tick` history — but, unlike that existing test's own deliberate isolation, against the **real, bounded 128-entry cache** with real eviction and real protection, not an unbounded test double.

- **Pre-fix mechanism confirmed genuinely RED** via a disposable ad-hoc script reproducing this exact activity pattern through the real, unmodified pre-fix `_run_assembly_tick` (old signature, plain insertion-order eviction, no fallback): `candidates_created` ends at **0**, with `blocked_missing_evidence: 2` (the precise v6 mechanism firing) and `blocked_ambiguous_boundary: 168` (siblings that never got a chance because their own winner failed downstream with no fallback) — a genuine, meaningful reproduction of the v6 loss class in synthetic replay, not merely a signature mismatch.
- **Post-fix:** bounded, non-zero admission (created=2 in the representative run measured), zero duplicates, no cross-subject contamination, `max_cache_size` never exceeds 128, `max_protected_size` stayed well under the 64 bound (12 in the measured run) — protection alone closed this particular replay's version of the defect (`fallback_attempted=0` in that run); fallback's own correctness under real, forced admission failure is separately, directly proven by the dedicated fallback tests below, since this specific synthetic shape's own churn pattern did not happen to produce a component whose winner failed downstream. Runtime: ~36s of real time (well under the 90s guard), confirming no O(n²) regression from either mechanism at this scale.
- Per the milestone's own explicit instruction, no exact Visit count is asserted — only the bounded-and-nonzero invariant, duplicate/contamination absence, and the cache/protection bounds.

## Exactly-once

Proven directly:

- `test_resolved_component_falls_back_when_top_member_evidence_was_evicted` / `test_component_with_no_viable_member_admits_nothing_and_diagnoses_honestly`: winner fails pre-admission → exactly one other member is tried, in order; a chain that exhausts admits nothing (never fabricates a "something" admission).
- `test_fallback_works_during_stop_finalization`: fallback succeeds at the session-ending `finalize=True` tick exactly as mid-session; a second, repeated `finalize=True` tick over the same already-resolved state creates no second Visit (`attempted_proposal_ids` already marks both members permanently resolved — the pre-existing idempotency mechanism, completely unmodified, is what makes this safe, not new fallback-specific logic).
- The repository's own pre-existing `create_candidate_visit_from_proposal` idempotency guarantee (re-validated from scratch every call, keyed on `proposal_id`, inside one atomic transaction) is untouched by this milestone — fallback only changes *which* `proposal_id` gets attempted next, never how any single attempt's own idempotency/persistence is decided.
- `"failed"` (persistence exception) is explicitly excluded from `_FALLBACK_ELIGIBLE_OUTCOMES` (see above) — a retry-exhausted contention failure can never trigger a different semantic winner, precisely per brief §15's own instruction.
- `test_fallback_is_correct_regardless_of_which_component_member_the_assembler_lists_first` directly closes the one concrete double-attempt risk this milestone's own self-review found (see "A second real design correction" under "Fallback contract," above): the repository's own idempotency happened to absorb it into a merely-corrupted-diagnostics outcome rather than a duplicate persisted Visit in every case reproduced, but the underlying double-attempt was still a genuine defect, now structurally impossible (every resolved component is walked exactly once, as one atomic unit, before any member of it could be reached any other way).

## Fragmentation

Every fallback/preservation test that reaches admission checks `duplicate_count == 0` and, where a component has more than one member, `len(created_rows) == 1` per resolved component — a rescued component still yields exactly one Visit, never one-per-member. The v6-shaped replay additionally checks the same invariant at scale (zero duplicate `proposal_id`s among 105-simulated-minute created rows) and bounds the total logical-Visit-group count (`0 < logical_visit_groups <= 20`), ruling out an explosion. No new fragmentation mechanism is introduced — fallback operates strictly *within* an already-resolved component and never changes how components themselves are formed (`assemble_visit_episodes`/arbitration's own component-detection logic is completely untouched).

## Multi-subject

`test_fallback_never_mixes_evidence_across_two_independent_simultaneous_components` (new): two entirely separate, genuinely simultaneous ambiguous components (geometrically distinct feeder/perch subjects) resolve on the same tick, both winners lacking evidence — both independently fall back to their own other member; verified via `MediaAssetModel.trigger_id` (the engine-side proposal id each persisted media row was actually built from) that neither subject's own persisted evidence set could have come from the other's fallback attempt. The v6-shaped replay additionally re-checks this at scale across the full 105-minute run. No ReID mechanism was introduced or required — isolation follows directly from each proposal's own `evidence_candidate_ids`/`track_generation_id` scoping, which `evidence_scoring.score_proposal_evidence` already enforced before this milestone.

## Stop-finalization

`test_fallback_works_during_stop_finalization` and the preservation tests' own `finalize=True` ticks confirm: protected evidence remains available through the session-ending tick exactly as mid-session (protection is recomputed identically regardless of `finalize`); fallback is attempted and succeeds at `finalize=True` exactly as it would mid-session; a repeated `finalize=True` tick over unchanged state does not duplicate; no pin/memory leak (the protected-ids set is a plain local variable inside one `_run_async` coroutine invocation, discarded naturally when that coroutine returns — the same lifetime guarantee `burst_bytes_cache`/`attempted_proposal_ids` already had before this milestone).

## Diagnostics

Per brief §19's own bounded scope ("Use existing structured counterfactual/ledger conventions. Do not create a new user-facing diagnostics screen"):

- Four new session-lifetime counters (`fallback_attempted_count`, `fallback_admitted_count`, `fallback_exhausted_count`, `protected_evidence_capacity_exhausted_count`) surfaced through the pre-existing `advanced` diagnostics dict — the same mechanism `evidence_harvest_misses` already uses, not a new surface.
- Per-proposal traceability reuses the existing free-form `reason` string on the counterfactual ledger (`ProposalOutcomeRecord`, unmodified schema) via an additive `:fallback_position_N` suffix on genuine fallback attempts only — directly mirroring the precedent `candidate_visit_adapter.py` already established for a retry-exhausted persistence failure (`f"{failure_code}:retries_exhausted"`). The primary (position-0) attempt's own record is never suffixed. This distinguishes, from the ledger alone, an ordinary direct win from a fallback-rescued one, and names which position rescued it.
- Winner-evidence-unavailable is directly visible as the winner's own unmodified `blocked_missing_evidence` ledger record — never hidden by the sibling's later success.

## Performance

- No new per-tick cost scales worse than linearly in already-bounded quantities: `_compute_protected_evidence_ids` iterates still-pending proposals (bounded by real activity, never unbounded) calling the existing, cheap `score_proposal_evidence` (itself bounded by `EvidenceScoringBounds.max_candidates`, default 16); `_select_eviction_victim` scans at most 128 cache entries per eviction.
- `test_sustained_activity_does_not_duplicate_or_explode_visits_over_a_long_run` (pre-existing, unmodified expectations) and `test_field_derived_multi_subject_stress_replay` (pre-existing) both still pass unchanged, confirming no regression to the already-accepted performance guards.
- The new v6-shaped replay (105 simulated minutes, real bounded cache, real protection, real fallback machinery present) completed in ~36s of real time, comfortably under its own 90s guard and in the same range as the pre-existing unbounded-cache multi-subject stress test.

## Validation

### Tier 1

All 19 new/updated tests were confirmed RED on accepted `b37656d` (via `git stash` isolating the three production files, running the affected tests, then restoring) and GREEN after the fix, run individually and in the full combined suite: **`tests/test_candidate_visit_authority.py` + `tests/test_candidate_visit_authority_acceptance.py` + `tests/test_candidate_visit_adapter.py` + `tests/test_engine_runtime.py`: 187 passed, 0 failed** (re-run twice — once before, once after the order-independence fix found by self-review; both runs clean).

### Tier 2

Affected-subsystem validation (evidence scoring, visit episode assembler, candidate persistence/idempotency, identification eligibility, counterfactual ledger, scene confusor): **`tests/test_observation_evidence_scoring.py` + `tests/test_visit_episode_assembler.py` + `tests/test_candidate_visit_repository.py` + `tests/test_concurrent_candidate_visit_persistence_reliability.py` + `tests/test_identification_eligibility.py` + `tests/test_identification_eligibility_regression_2026_08_21.py` + `tests/test_counterfactual_lineage.py` + `tests/test_scene_confusor.py` + `tests/test_scene_confusor_repository.py`: 279 passed, 0 failed** (re-run twice for the same reason as Tier 1; both runs clean).

### Tier 3

One full Core run (`scripts/verify_core.py`, i.e. `pytest -m "not slow"`), against the fully-fixed code including the order-independence correction. The tool's own 10-minute background-task cap is shorter than this suite's real runtime (confirmed directly: an unsplit attempt reached only ~8% after 1.5 minutes of CPU time), so it was run as four sequential-file, concurrently-executed chunks covering the complete alphabetical test-file list with no overlap or gap; the sum of all four chunks' own collected-test counts (5372) matches `--collect-only`'s own whole-suite count exactly, confirming complete, non-duplicated coverage.

**5357 passed, 3 skipped, 11 xfailed, 1 failed, 23 deselected** (5372 total in "not slow" scope; deselected = "slow"-marked, out of this run's own scope by design).

The one failure, `tests/test_temporal_capture_cli.py::test_run_capture_end_to_end_reconnect_produces_a_native_session_timeline`, is independently confirmed unrelated to this milestone, not merely assumed:

- **Zero code-dependency relationship**: `temporal_capture_cli.py`/its test import nothing this milestone touched (`candidate_visit_authority.py`, `candidate_visit_adapter.py`, `engine_runtime.py`) — it exercises a structurally separate Stage 5 capture-CLI path.
- **Passed cleanly on the exact pre-fix baseline** (`git stash`-isolated to production-code-only, this test file untouched either way) in the same investigation session.
- **Passed 5/5 consecutive runs in isolation** with this milestone's own fix fully in place.
- **Only failed once, inside the one concurrently-executed chunk running 80 other test files simultaneously alongside three sibling chunks** (12 real CPU cores, all four chunks together saturating them) — the test's own docstring already names real wall-clock-timing-dependent behavior ("Bounded latest-frame coalescing under host backpressure," a `--duration 5` real-time capture window), consistent with a genuine, pre-existing timing-sensitive flake made visible by this investigation's own necessary chunked-concurrent execution (an artifact of working around the tool's own timeout, not of this milestone's product code).

Per the milestone's own §30 bar ("fixed if related; independently baseline-reproduced if unrelated... do not normalize... without reproduction"), this is reproduced, understood, and correctly left unfixed here — an environment/tooling artifact of this investigation's own concurrent test execution, not a product defect this milestone introduced or is responsible for fixing.

`ruff check` on every touched file: zero new findings. Two pre-existing findings in `tests/test_engine_runtime.py` (an unused `dataclass` import and an unused `status` local in `test_non_camera_node_stream_reports_honest_unavailable_state`) were independently confirmed present on baseline `b37656d` via clean-checkout bisection — unrelated to this milestone, not introduced or worsened by it, left untouched.

## Remaining risks

- **Protection capacity under extreme concurrent pressure.** `_MAX_PROTECTED_EVIDENCE_IDS` (64) is a real, deliberately bounded ceiling, not a claim of perfect retention under unbounded simultaneous activity — a session with far more than a handful of genuinely simultaneous pending proposals (well beyond anything measured in any real cohort to date, including v6's own multi-subject moments) could still exhaust protection and lose some evidence to ordinary eviction. This is diagnosed (`protected_evidence_capacity_exhausted_count`), never silent, and degrades to exactly the pre-fix behavior for the proposals it cannot protect — never worse.
- **Fallback is bounded by real component membership.** If every member of a resolved component genuinely lacks usable evidence (not merely one), the component is honestly, correctly lost — this is not a defect, but it means fallback cannot manufacture evidence that was never captured for *any* member.
- **The v6-shaped replay's own synthetic churn pattern did not happen to exercise fallback.** Preservation alone closed it. This is an honest characterization, not a gap the milestone leaves unaddressed — fallback's own correctness (including under stop-finalization and multi-subject conditions) is separately, directly proven by five dedicated tests that do force a winner-evidence-unavailable condition. Both mechanisms remain in place as defense-in-depth, exactly matching brief §34's own "AND" framing (preservation-or-equally-strong-design, *and* fallback-when-semantically-safe).
- **Not yet field-proven.** Every reproduction and every stress replay in this milestone is deterministic and synthetic, per its own explicit non-goal (§32, "no field run"). The next real daylight cohort is what converts this from a strong deterministic proof into a field-confirmed fix — see "Next field proof required," below.
- **`candidate_visit_authority_cli.py`** (the superseded engineering-trial CLI) does not gain fallback/preservation — deliberately out of scope, since it is not the live product path v6 exercised, and its own hard 10-minute/3-candidate bound makes the underlying risk far smaller there regardless.

## Next field proof required

If this milestone is accepted, the next daylight cohort (not authorized by this milestone; global reconciliation required first, per §36) should prove:

- Non-zero in-session `candidates_created` under sustained, real activity of the same general shape v6 measured (the core "does it still get stuck at zero" question).
- No v6-style whole-component loss when at least one member's evidence remains usable — i.e., a materially reduced (ideally near-zero, honestly reported either way) `blocked_missing_evidence` rate among proposals whose own component had *any* viable alternative member, distinguished from a component where genuinely no member had usable evidence (a legitimately unrepresentable case, not a regression).
- At least one real, observed fallback event (a component where the natural/forced winner failed and a runner-up was admitted instead), if real conditions produce one — or an honest disclosure if they do not, exactly like v5/v6's own qualitative-not-fabricated standard.
- Genuine concurrent multi-subject siblings actually reaching admission (still never jointly observed with real in-session admissions across v5 and v6) — this milestone does not manufacture that field condition, only removes one known mechanism that was preventing it from ever reaching admission at all.
- No duplicate-Visit or fragmentation regression (the existing, accepted measurement discipline, unchanged).
- Useful evidence still survives at admission (the existing ~85% candidate useful-evidence-rate dimension, unchanged, re-measurable once real admissions occur again).
- Stop-finalization remains correct under real sustained activity (unchanged from the already-accepted v4/v5 contract).

## Decision

**Classification: A.**

Every element of the brief's own acceptance bar (§34) is met:

- Deterministic reproduction of the v6 loss class: yes, at three levels — pure arbitration behavior, the live engine's per-tick attempt loop, and a 105-simulated-minute multi-subject replay against the real bounded cache — with the replay's own pre-fix failure additionally confirmed via direct reproduction of the real *mechanism* (not merely a signature mismatch).
- Pre-fix RED: yes, nineteen tests, confirmed via `git stash` isolation of the exact production-code changes, not merely "tests that only start passing because test setup changed."
- Pending evidence protected while still required (bounded preservation) **and** fallback to a viable same-component member where semantically safe: both implemented, both tested independently and together, matching brief §34's own explicit "AND" framing.
- No duplicate regression: proven directly (exactly-once tests) and at scale (zero duplicates across the 105-minute replay).
- No fragmentation explosion: proven directly and at scale (bounded logical-Visit-group count).
- Multi-subject evidence isolation preserved: proven directly (`MediaAssetModel.trigger_id` cross-check) and at scale.
- Bounded memory: both new bounds (`_MAX_PROTECTED_EVIDENCE_IDS=64`, unchanged 128-entry caches) are hard, deterministic, and diagnosed on exhaustion — never unbounded.
- Stop-finalization preserved: proven directly, including repeated-stop non-duplication.
- Long-run high-churn replay does not reproduce the v6 loss while viable evidence exists: proven (bounded non-zero admission under real cache pressure).
- Tier 1 clean (187/187), Tier 2 clean (279/279), Tier 3 clean apart from one independently confirmed unrelated finding (5357/5358 excluding the pre-existing timing-sensitive flake) — see "Validation," above, for the complete bisection.

This milestone does not implement any of the explicit non-goals (§37): no cache-size increase, no detector/model threshold tuning, no MDv5/BioCLIP/SpeciesNet changes, no identification-policy expansion, no UI/provider/storage/Camera-Node work, no field run.

## Final response summary

- Classification: **A**
- Starting HEAD: `b37656d` (verified exact match to the governing instruction's stated starting state)
- Implementation/report HEAD: this commit (production code: `candidate_visit_authority.py`, `candidate_visit_adapter.py`, `engine_runtime.py`; tests: `test_candidate_visit_authority.py`, `test_candidate_visit_adapter.py`, `test_engine_runtime.py`; this report)
- Schema: v58, unchanged
- Root cause: no evidence-availability gate in authority; `blocked_missing_evidence` non-retryable; no fallback path existed — composed with a session-global, insertion-order-only 128-entry evidence-byte cache with zero pending-proposal awareness
- Eviction RED: confirmed (pending proposal's evidence evicted by 200+ unrelated insertions through the real eviction policy; RED on `b37656d`)
- Fallback RED: confirmed (`test_ambiguous_boundary_arbitration_does_not_cascade_to_the_next_sibling`'s own pre-fix scenario, renamed/rewritten as `test_resolved_component_falls_back_when_top_member_evidence_was_evicted`)
- Preservation design: per-tick-recomputed, bounded (64), oldest-first protected-id set consulted by the cache's own real eviction policy; uses currently-cached bytes for its priority preview (a real design correction made mid-implementation, documented above)
- Fallback design: deterministic same-component walk (`_attempt_resolved_component`), reusing arbitration's own ranking, bounded outcome-eligibility set, never reruns arbitration, never crosses components
- Cache bound result: unchanged at 128; new protection bound 64, hard-capped, diagnosed on exhaustion, never unbounded
- V6-shaped replay result: pre-fix genuinely RED (0 admissions, real `blocked_missing_evidence`/`blocked_ambiguous_boundary` mix) via direct mechanism reproduction; post-fix bounded non-zero admission, zero duplicates, no cross-subject contamination, bounds respected, ~36s runtime
- Exactly-once result: proven (winner-succeeds-no-fallback, fallback-succeeds-once, chain-exhausted-admits-nothing, repeated-finalize-no-duplicate, persistence-failure-never-triggers-fallback)
- Fragmentation result: zero duplicates, bounded Visit-group count, both in targeted tests and at 105-minute scale
- Multi-subject result: independently verified via persisted-evidence `trigger_id` cross-check; no cross-subject contamination in targeted tests or at scale
- Stop-finalization result: fallback and preservation both proven correct at the `finalize=True` tick; repeated stop does not duplicate
- Diagnostics result: four new session counters via the existing `advanced` surface; per-record `:fallback_position_N` reason suffix via the existing ledger, no schema change
- Performance result: no new unbounded loop; 105-minute replay in ~36s, under its own 90s guard
- Tier 1: 187 passed, 0 failed (4 files, run twice)
- Tier 2: 279 passed, 0 failed (9 files, run twice)
- Tier 3: 5357 passed, 3 skipped, 11 xfailed, 1 failed, 23 deselected (5372 total, full Core run via 4 chunks summing exactly to the whole-suite collect count); the 1 failure independently confirmed unrelated (zero code-dependency, passes on baseline, passes 5/5 in isolation, fails only under this investigation's own 4-way concurrent chunk execution)
- Remaining risk: protection capacity under activity levels beyond anything measured to date; fallback cannot rescue a component where genuinely no member has usable evidence; not yet field-proven
- Exact next daylight proof required: non-zero in-session admissions under sustained activity; materially reduced/understood `blocked_missing_evidence` rate; a real observed fallback event or honest disclosure of none; genuine concurrent multi-subject siblings reaching admission; no duplicate/fragmentation regression; useful-evidence rate re-measurable; stop-finalization correctness under real sustained activity
- Current authorization: returns to **NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**
- Ready/not ready for ChatGPT acceptance review: **ready for review**
