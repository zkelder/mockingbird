# Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness v1

Bounded RELEASE-CRITICAL Gate A evidence-integrity milestone, directly
authorized outside `docs/release-execution-state.md`, following Camera Node
Evidence-Capture Profile Validity & Failure Observability Correctness v1
and Representative Daylight Gate A Field Acceptance v13 -- Intact-Ledger
Re-Proof & Budget Convergence. Governing question: why did a session with
350 real proposal-decision events yield only 156 recoverable
`proposal_outcome` records (44.6%) under the accepted periodic-checkpoint
process, and is field collection now capable of preserving/reconciling
proposal-decision history at release-budget quality under realistic
high-churn conditions?

## Starting state

Verified against `docs/release-execution-state.md`, `docs/product-doctrine.md`,
and `docs/roadmap.md` before any action, exactly as the governing brief
described:

- Branch `main`, git HEAD `cdede93f9ca391ef396e48425cd84c81b7eb5fae` --
  matched exactly (`git rev-parse HEAD`).
- Schema v58, unchanged.
- Latest accepted milestone: Camera Node Evidence-Capture Profile Validity
  & Failure Observability Correctness v1, classification **A** -- matched
  (§3 top entry).
- Lane R / Gate A: **OPEN** -- matched.
- Evidence-capture profile validity/failure observability: **CLOSED /
  READY FOR REPRESENTATIVE FIELD RE-PROOF** -- matched.
- Recall and evidence survival: **REOPENED / WAITING FOR FIELD RE-PROOF**
  -- matched.
- Proposal-outcome ledger completeness/cadence: **OPEN as a separate Gate
  A evidence-integrity dependency** (v13's own disclosed 44.6%
  completeness, explicitly not touched or widened by the evidence-capture
  milestone) -- matched.
- Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED` -- matched; this milestone's own governing brief is the
  external reconciliation that authorizes this specific session.
- Not pushed -- confirmed (`git log origin/main..HEAD`, +335 ahead).
- Production stack confirmed unchanged in doctrine: MDv5a ONNX, threshold
  0.1, BioCLIP-2, current Identification Eligibility/Abstention, schema
  v58.

No discrepancy found -- state matches the brief's expectation exactly, so
no STOP condition applies.

## Worktree safety

No active writer found in this worktree (no `.git/index.lock`, no other
process). All 7 preserved untracked detector files reconfirmed present,
byte-for-byte untouched throughout this milestone (verified again at
report time):
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`. Not pushed.

## V13 loss reconstruction

Reconstructed from two independent sources: the accepted v13 report's own
"Ledger integrity" section, and (more precisely) the real, locally-preserved
v13 evidence archive
(`data/field-acceptance/2026-09-04-gate-a-v13-intact-ledger-budget-convergence/`
-- gitignored, machine-local, not committed, exactly like every other real
field-acceptance archive in this project) -- its 21 real
`raw-periodic-snapshots/checkpoint-NNNN.json` files plus the real final
corrective fetch (`merged-ledger/counterfactual-final.json`) were read and
analyzed directly, not merely trusted from the prior report's own prose.

**Basis, confirmed exactly:**

- Total decision-event count: **350** (`coverage.proposal_outcomes.
  recorded_count`, identical across the 21st periodic checkpoint and the
  separate final corrective fetch -- and identical to the live session's
  own `proposals_observed` counter, per the v13 report).
- Recovered `proposal_outcome` count under the accepted (pre-fix)
  reconciliation: **156**.
- Snapshot cadence: 300 real seconds (5 minutes), 21 checkpoints, plus one
  final corrective fetch taken live, seconds before the stop call.
- Retention/window limits (production defaults, unchanged,
  `CounterfactualRetentionConfig`): `max_proposal_outcome_records=1_000`
  (count), `max_age_ms=3_600_000` (60 minutes, rolling, relative to the
  most-recently-appended record's own offset).
- Per-checkpoint query bounds: every checkpoint queries the maximally
  broad, fixed window `start_offset_ms=0, end_offset_ms=86_400_000`
  (24h) -- a deliberate no-op filter, confirmed by direct code read of
  `CounterfactualLedger.query()`: with these bounds the window filter
  `item.start_offset_ms <= end_offset_ms and item.end_offset_ms >=
  start_offset_ms` is true for every retained record, so **every
  checkpoint returns everything currently retained, unconditionally** --
  there is no separate query-side windowing to lose anything to.
- Earliest/latest recovered offset (as reported, by the pre-fix tool):
  117,398ms / 5,980,520ms.
- **Direct archival re-analysis (this milestone, not merely re-quoting the
  prior report): the union of all 21 real checkpoint payloads' own raw
  `proposal_outcomes` lists, deduplicated by the full `(proposal_id,
  decided_at)` pair, recovers exactly 350 distinct events -- an exact
  match to `recorded_count`.** Zero raw decision events are unrecoverable
  from the real archived checkpoint files. Of those 350, exactly **156
  distinct `proposal_id`s** exist; 92 were decided exactly once, and 64
  were re-decided multiple times (31 five times, 15 four times, 7 three
  times, 11 twice) -- 92+11+7+15+31=156 proposals; 92+22+21+60+155=350
  events, both matching exactly.

**Which intervals are missing, and why -- determined precisely, not
assumed:**

- **Already evicted before checkpoint?** No. Cross-checked directly: every
  one of the 350 raw events appears in at least one of the 21 real
  checkpoint payloads (the 5-minute cadence comfortably outruns the
  60-minute rolling retention window -- roughly 12x margin -- so nothing
  is ever created and evicted between two consecutive checkpoints).
- **Omitted by query bounds?** No. The `[0, 86_400_000]` window is a
  deliberate no-op; confirmed by code read, not inference.
- **Overwritten/deduplicated?** No at the ledger-writer level (append-only,
  confirmed -- see "Ledger writer semantics," below). **Yes, this is the
  actual mechanism**, at the field-acceptance *reconciliation* layer:
  `field_acceptance_ledger_snapshot.py`'s own `_accumulate_artifact`
  deduplicated `proposal_outcomes` by `proposal_id` alone (`_IDENTITY_FN
  ["proposal_outcomes"] = _id_identity("proposal_id")`), collapsing every
  one of the 64 multiply-decided proposals' own 2-5 real, distinct
  decision events down to whichever one happened to be processed *last*
  across the 21 checkpoints, in checkpoint-file-iteration order (an
  accident of iteration order, not decision recency, though the two
  happened to coincide for v13's own real data -- see "Ledger writer
  semantics" for why that is not guaranteed).
- **Lost through pagination?** No such mechanism exists anywhere in this
  path (confirmed by direct code read of the API endpoint -- no page
  size, no cursor, no result cap beyond the ledger's own retention).
- **Collapsed by identity semantics?** **Yes -- this is the primary,
  confirmed mechanism.** `proposal_id` alone is the wrong identity for
  this one artifact type (see next section).
- **Absent from the ledger writer?** No (see "Ledger writer semantics" --
  every attempt is recorded, confirmed by direct code read and by
  `recorded_count` exactly matching the live session's own `proposals_
  observed` counter).
- **Lost during reconciliation?** **Yes -- confirmed the actual mechanism**,
  specifically the identity-collapse above, plus a second, closely-related
  reconciliation defect independently discovered during this milestone's
  own real-runtime smoke proof and confirmed against the same real v13
  archive: the interval/gap check's `[0, session_last_offset_ms]`
  windowing convention assumed every artifact type has activity spanning
  close to the full session (true for `raw_detections`/`track_
  generations`, which fire on nearly every tick) -- not true for
  `proposal_outcomes`, which is naturally silent before the first
  candidate encounter and after the last one. Even after fixing the
  identity collapse alone, v13's own real archive still reconciled to
  `PARTIAL` (zero missing records, `completeness_fraction=1.0`, but two
  "uncovered offset window(s)" -- `(0, 134581)` before the first real
  decision and `(6012950, 6081819)` after the last) purely from this
  second, distinct artifact of the same reconciliation layer. See
  "Reconciliation semantics" and "Implementation" for the full account of
  both.

**Root-cause note, made explicit up front:** the governing brief's own
§10 warns "do not assume cadence alone is the root cause," and it is not.
Cadence, retention capacity, the ledger writer, and the query layer are
all independently confirmed innocent below.

## Required proposal-outcome evidence

Determined before implementing anything (governing brief §11), by direct
code read of every existing consumer of `proposal_outcomes` -- never
guessed:

- **Every decided attempt, not only terminal ones, is genuinely useful
  evidence** -- but for a *different* reason than "Gate A metrics need
  them directly." Every currently-defined Gate A metric that consumes
  `proposal_outcomes` (recall, false-Visit rate, evidence-survival,
  fragmentation, via `encounter_accounting.cluster_encounters`) operates
  on each proposal's own **latest-by-`decided_at_offset_ms`** decision --
  confirmed by direct code read of `cluster_encounters`'s own `latest_
  outcome_by_proposal_id` reduction (`src/mockingbird/observation/
  encounter_accounting.py:242-256`), which is *already*, independently,
  precedented, established, and specifically documented as reducing a
  `proposal_outcomes` sequence that "can legitimately hold several records
  for one proposal id, and only the *last-decided* one is that proposal's
  own actual final fate." No currently-defined Gate A metric needs the
  full intermediate history to compute a number.
- **The intermediate `blocked_continuation_pending` history is real,
  disclosed diagnostic value, not required by any current metric, but not
  "high-volume noise" either** -- it is the exact fact this codebase's own
  Visit Continuity / Provisional Admission Fix v1 work already cares about
  (how long, and how many times, did a proposal's own tail boundary stay
  unresolved) and the exact class of detail `record_proposal_outcome`'s
  own docstring says was previously "discarded completely on every attempt
  but the last" before the counterfactual ledger existed at all. Discarding
  it a second time, one layer later, in the field-acceptance tool, would
  quietly re-introduce the same loss this project already fixed once.
- **Locked requirement:** field reconstruction needs, at minimum, the
  latest-known (terminal-or-still-pending) decision for every distinct
  proposal this session ever produced -- this is what every currently
  -defined Gate A metric actually consumes. It should *also* preserve the
  full intermediate decision-event history where the ledger itself already
  retains it, because (a) doing so is nearly free once the identity
  mismatch is fixed, (b) it is exactly the shape the accepted downstream
  consumer (`cluster_encounters`) was already built to receive and reduce
  itself, and (c) it directly answers a real, disclosed diagnostic
  question (how much continuation-pending churn a session produced) that
  this project has cared about before. This milestone delivers the
  stronger of the two (full history preserved) as the natural, no-extra
  -cost consequence of fixing the identity mismatch correctly -- not a
  separate design decision requiring its own tradeoff.
- **Not required, and correctly still absent:** individual raw-detection
  -level or track-generation-level intermediate state beyond what
  `raw_detections`/`track_generations` (unmodified, untouched by this
  milestone) already retain; nothing about this milestone changes what
  those two artifacts preserve.

## Ledger writer semantics

Traced directly in `src/mockingbird/observation/counterfactual_lineage.py`
and its one call site, `src/mockingbird/observation/engine_runtime.py`
(`_run_assembly_tick`'s `_record_and_count`) -- never inferred from
symptoms:

1. **Is every decision attempt written?** Yes. `record_proposal_outcome`
   is called exactly once per `adapter.attempt_candidate(...)` result,
   for every proposal attempted every tick, regardless of outcome
   (including a genuine `created`) -- confirmed by the module's own
   docstring and by direct trace of every call site.
2. **Are only terminal decisions written?** No -- every attempt is
   written, terminal or not (see next point).
3. **Can one proposal emit multiple outcomes?** **Yes, confirmed the
   central fact of this investigation.** `blocked_continuation_pending`
   is the one outcome in `candidate_visit_authority.RETRYABLE_OUTCOMES`
   (`frozenset({"blocked_continuation_pending"})`); a proposal blocked
   only for that reason is deliberately never added to `attempted_
   proposal_ids`, so it is re-offered (and re-decided, and re-recorded)
   on every subsequent ~10-second assembly tick until either its boundary
   finalizes into a terminal decision or the session itself ends
   (`finalize=True`, which forces a final decision for every still-pending
   proposal). Every other outcome (`created`, `idempotent_repeat`, or any
   `blocked_*`/`reject_*` code) is a permanently resolved fact for that
   exact proposal id and is never re-attempted.
4. **Is retention bounded by count, age, or both?** Both, independently
   -- `_BoundedOffsetLedger` evicts on `len(records) > max_count` and,
   separately, on `newest_offset - oldest_offset > max_age_ms`, oldest
   -first (FIFO) on each dimension.
5. **What is the bound?** `max_proposal_outcome_records=1_000`;
   `max_age_ms=3_600_000` (60 minutes) -- both production defaults,
   unmodified by this milestone.
6. **Is eviction FIFO/by timestamp/by key?** FIFO by *append order*,
   which the ledger's own age check assumes is non-decreasing in offset
   (`decided_at_offset_ms`, i.e. the tick's own `known_horizon_ms`, which
   only ever advances across ticks in real production use -- confirmed:
   `_run_async` computes `latest_known_offset_ms = max(...)` and passes it
   straight through every tick). **Confirmed-safe assumption, not
   exploitable in real production use** -- but a genuinely undocumented
   invariant before this milestone: this investigation's own test
   authoring discovered directly (a fixture bug caught during test
   writing, not a production defect) that appending records *out* of
   non-decreasing offset order corrupts `LedgerEvictionAccounting.oldest_
   retained_offset_ms`/`newest_retained_offset_ms` (they become
   mislabeled front/back-of-deque values, not true min/max). Documented
   here as a confirmed, currently-safe, but load-bearing assumption for
   any future caller of `record_proposal_outcome` -- not fixed, since
   production code never violates it and fixing it is unrelated to this
   milestone's own scope (no product-decision code was touched).
7. **Does high proposal churn disproportionately evict outcomes?** Not in
   any real cohort measured to date (see "Capacity/churn analysis") --
   churn evicts oldest-first exactly as designed; the *field-tooling*
   reconciliation defect this milestone fixes, not the ledger's own
   eviction mechanics, is what turned that ordinary, bounded, correctly
   -working eviction into an apparent 44.6% "loss."
8. **Does the writer deduplicate or replace prior events?** No --
   confirmed append-only; `_BoundedOffsetLedger.append` never mutates or
   removes an existing record except via its own FIFO eviction.
9. **Are reason updates mutable or append-only?** Append-only. A later
   tick's re-decision for the same proposal id is a brand-new,
   independent `ProposalOutcomeRecord`, never an in-place mutation of an
   earlier one.
10. **Are intermediate arbitration outcomes expected to survive?** Yes,
    for as long as retention allows -- and, per "Required proposal-outcome
    evidence" above, they are real, useful evidence, not noise to discard.

**Locked definition of "proposal_outcome completeness":** the fraction of
real decision *events* (not distinct proposals) ever appended to the
ledger that a reconciliation can recover, compared honestly against the
ledger's own authoritative `recorded_count`.

## Retention semantics

Confirmed unchanged and, per "Capacity/churn analysis" below, structurally
adequate for every real churn rate measured to date:

- Bound: 1,000 records **and** 60 minutes, whichever binds first
  (independently, per dimension).
- For v13's real 350-event/101.8-minute session, **neither bound was ever
  close to binding relative to the checkpoint cadence**: the count bound
  (1,000) was never reached at all (peak observed total 350); the age
  bound (60 minutes) did evict older records from the *live* in-memory
  ledger well before session end (as designed -- this is a rolling
  window, not a permanent store), but every one of those records had
  already been captured by an earlier periodic checkpoint, comfortably
  inside the 12x margin the 5-minute cadence provides against the
  60-minute window.
- This milestone does **not** change either bound, and does not need to
  -- see "Capacity/churn analysis."

## Query semantics

Traced directly in `GET /api/streams/{stream_id}/observation/counterfactual`
(`src/mockingbird/api/main.py`) and `CounterfactualLedger.query()`:

- Offset boundaries are inclusive on both ends (`start_offset_ms <=
  end_offset_ms >= start_offset_ms` overlap semantics); `start_offset_ms`/
  `end_offset_ms` are both required, `ge=0`, with `end_offset_ms <
  start_offset_ms` rejected with a `400` -- confirmed unchanged since the
  prior (Field Acceptance Evidence Integrity & Storage Preflight
  Correctness v1) milestone's own fix of the `None`-omission defect.
- **No max result limit, no pagination, of any kind exists anywhere in
  this path** -- confirmed by direct code read of both the API handler and
  the pure `CounterfactualLedger.query()` method: every retained record
  overlapping the requested window is returned, full stop.
- Sorting: records are returned in the ledger's own internal (append/FIFO)
  order; the field-acceptance tool does not rely on this order for
  correctness (its own dedup step is order-independent by construction,
  proven by `test_reconcile_ledger_deduplicates_overlapping_snapshots_
  deterministically`).
- Duplicate handling: none needed at the query layer -- a query never
  returns the same underlying record object twice within one response.
- **A query can never silently truncate results** -- confirmed; the only
  way fewer records come back than were ever created is genuine eviction,
  which is separately, honestly reported via `coverage.<type>.evicted_
  count`/`recorded_count`/`retained_count` on every response.
- Count metadata **does** expose truncation/eviction: `retained_count`,
  `evicted_count`, `recorded_count`, `oldest_retained_offset_ms`,
  `newest_retained_offset_ms` are present on every response, and were
  already correctly populated before this milestone (this part of the
  contract needed no fix).

**Conclusion: the query layer is fully exonerated.** The field-acceptance
tool's own deliberately maximal `[0, 86_400_000]` window means "successful
HTTP response silently returning only the first N records" (the specific
risk the governing brief's §8 warns about) cannot occur in this system --
there is no N to truncate to.

## Reconciliation semantics

Traced end to end in `scripts/field_acceptance_ledger_snapshot.py`
(`_accumulate_artifact`, `reconcile_ledger`, `build_merged_counterfactual_
window`) -- the actual site of both real defects this milestone fixes:

- **Unique event identity, before this fix:** `generation_id` for
  `track_generations` (correct -- recorded exactly once per generation, at
  its own `ended` transition, confirmed by direct code trace of
  `_observe_track_update_locked`); the full natural fact-tuple for
  `raw_detections` (correct -- one independent fact per analyzed frame,
  no id field exists to reuse); **`proposal_id` alone for `proposal_
  outcomes` (wrong)** -- this artifact type is the *only* one of the three
  where a single natural entity id can legitimately correspond to several
  independent, individually-meaningful ledger records over a session's
  life (see "Ledger writer semantics," point 3).
- **Whether multiple legitimate decisions for one proposal can
  collapse:** yes, confirmed -- this was the entire mechanism behind
  v13's 44.6%. The dict-keyed-by-identity merge (`unique[identity_fn
  (record)] = record`) silently keeps only the *last-processed* record
  for a given key; with `proposal_id` alone as the key, all but one of a
  multiply-decided proposal's own real, distinct decision events were
  discarded on every merge, in *checkpoint-processing order* -- which
  happens to coincide with *decision recency* only because checkpoints
  are, in fact, processed in chronological order and a proposal's own
  records accumulate monotonically within the live ledger (see "Ledger
  writer semantics," point 6) -- an accident of this system's own
  correct chronological-processing convention, not a property the old
  identity choice itself guaranteed or even referenced.
- **Whether timestamp equality can collapse distinct events:** no --
  `decided_at` is a fresh `datetime.now(UTC)` call per `record_proposal_
  outcome` invocation (see `engine_runtime._run_assembly_tick.
  _attempt`), effectively unique per decision attempt in practice; the
  fixed `(proposal_id, decided_at)` identity is exactly as precise a
  natural key as `_raw_detection_identity`'s own "full fact tuple"
  convention already established for the sibling artifact type.
- **Whether reason transitions survive:** before this fix, no (the
  intermediate `blocked_continuation_pending` reason for a since
  -resolved proposal was discarded whenever a later record for the same
  `proposal_id` existed anywhere in the payload set). After this fix,
  yes -- every reason transition for every proposal survives into both
  the reconciliation count and the merged output.
- **How overlap is reconciled:** order-independent set/dict union across
  every payload -- unaffected by this fix, still deterministic (re
  -confirmed: `test_reconcile_ledger_deduplicates_overlapping_snapshots_
  deterministically` still passes unmodified).
- **How gaps are detected -- the second, independently-discovered
  defect:** `_gaps_in` checks whether the union of each payload's own
  reported `[oldest_retained_offset_ms, newest_retained_offset_ms]`
  interval covers `[0, session_last_offset_ms]`. This implicitly assumes
  every artifact type has activity (and therefore a real retained
  interval) spanning close to the *entire* session -- true for
  `raw_detections`/`track_generations` (the detector runs, and is
  recorded, on essentially every analyzed frame, `detector_ran`
  heartbeats included) but structurally never true for `proposal_
  outcomes`, which has zero activity before the first viable candidate
  encounter and zero activity after the last one, *by the nature of what
  it records*, regardless of how well or continuously the field tool
  itself checkpointed. **Discovered during this milestone's own real
  -runtime smoke proof** (see below), then independently confirmed
  against the real v13 archive: even after fixing the identity collapse
  alone, v13's own real data still reconciled to `PARTIAL` for `proposal_
  outcomes` -- `recovered_unique_count=350`, exactly matching `final_
  recorded_count=350` (proving, by the count check alone, that nothing
  was actually lost), yet `gaps_ms=[(0, 134581), (6012950, 6081819)]`
  still forced the overall verdict to `PARTIAL`. This is a real, distinct,
  independently-discovered reconciliation defect, not merely a restatement
  of the identity-collapse defect -- fixed in the same milestone because
  it lives in the same function, affects the same artifact, and was
  necessary for an honest v13-shaped RED->GREEN proof.
- **Locked, precise fix (implemented, not just decided):** a payload
  proves interval coverage `[0, its own `session_last_offset_ms`]` for
  `proposal_outcomes` (regardless of its own retained-offset window)
  under exactly two conditions: (a) its own `recorded_count == 0`
  (definitively nothing yet, as of this payload's own fetch -- always
  trustworthy alone); or (b) its own `recorded_count == final_recorded_
  count` (the session-wide max) **and** this exact value is independently
  corroborated by at least one *other*, separately-fetched payload also
  reporting it -- guarding, deliberately, against a single, lone
  corrective fetch trivially "confirming" its own count as final with no
  independent evidence at all (the historical Representative Daylight
  Gate A Field Acceptance v12 shape this tool's own prior milestone
  already had to protect against: one uncorroborated corrective fetch,
  used to infer a large historical total no other observation ever
  touched). See "Implementation" for the exact code and "Bounded-eviction
  proof" for the test proving this refinement does not mask a genuine
  gap.

## First irreversible loss

**None occurred.** This is the central, precise finding of this
investigation: every one of v13's real 350 `proposal_outcome` decision
events is, and always was, fully recoverable from the real, already
-archived periodic-checkpoint files this session actually produced --
independently re-verified by this milestone via direct union-and-dedup of
the real archive using the correct `(proposal_id, decided_at)` identity,
which recovers exactly 350/350. No record was ever evicted from the live
ledger before some checkpoint had already captured it (the 5-minute
cadence provides roughly 12x margin against the 60-minute retention
window, and the count cap, at 1,000 against a 350-event session, was
never remotely close to binding). **The 44.6% figure describes a defect
entirely inside the field-acceptance reconciliation tool, not any loss of
evidence that ever actually occurred.** No retention/query/writer fix was
required or made; only the reconciliation tool's own identity and
gap-coverage logic needed correction.

## Root-cause classification

**E -- reconciliation identity collapses legitimate events** -- the
single, precise, confirmed root cause of the 44.6% figure, with one
closely-related second manifestation in the same reconciliation layer
(the gap-coverage artifact-uniformity assumption, above) that would have
prevented an honest `COMPLETE` verdict even after the identity fix alone,
discovered and fixed in the same milestone for the same reason.

Explicitly ruled out, each independently and directly:

- **A (retention count too small):** No -- 1,000 configured vs. 350 real
  peak total; never binding.
- **B (retention age shorter than checkpoint interval):** No -- 60
  minutes vs. a 5-minute cadence; ~12x margin, and empirically the union
  of checkpoints recovers 100% of everything ever created.
- **C (query result cap/pagination truncation):** No such mechanism
  exists anywhere in this path -- confirmed by direct code read, not
  inference.
- **D (checkpoint bounds leave gaps):** No -- the checkpoint *cadence*
  itself left no real hole; every event that was ever created was
  captured by some checkpoint.
- **F (writer fails to record required decisions):** No -- `recorded_
  count` (350) exactly matches the live session's own `proposals_
  observed` counter; every attempt is written, confirmed by direct trace.
- **G (multiple interacting causes):** Considered, but rejected as the
  primary classification -- both real defects found live entirely inside
  one function (`_accumulate_artifact`) and are two symptoms of the same
  underlying category of mistake (treating `proposal_outcomes`, uniquely
  among the three ledger artifacts, as if its own natural per-record
  identity/activity-pattern matched the other two), not independent,
  unrelated causes.
- **H (field tooling cadence inconsistent with an otherwise-correct
  bounded retention contract):** No -- the cadence (5 minutes) was never
  the problem; it already left generous, quantified margin (see
  "Capacity/churn analysis").
- **I (v13 evidence insufficient, deterministic reproduction establishes
  same failure class):** Not needed -- v13's own real archived evidence
  was sufficient on its own (re-analyzed directly, byte-for-byte), and a
  deterministic synthetic reproduction was *additionally* built for
  permanent regression coverage, not because the real evidence was
  lacking.
- **J (no defect / metric basis was wrong):** Close in spirit but not the
  most precise label -- there *is* a real, fixable code defect (the wrong
  identity function, and the wrong gap-coverage assumption), not merely a
  human mis-description of an otherwise-correct number.

## Capacity/churn analysis

Using real historical rates, not an invented target:

| Cohort | Duration | Total `proposal_outcome` decision events | Average rate |
|---|---|---|---|
| v12 | 96.97 min | 325 | ~3.35/min |
| v13 | 101.8 min | 350 | ~3.44/min |

No runaway growth trend across the two most recent comparable real
cohorts. Peak churn, computed directly from v13's own real archived
per-checkpoint `recorded_count` progression (21 real checkpoints, 300s
apart): the largest single-interval jump was **37 new decision events in
one 5-minute interval** (checkpoints 8→9, `recorded_count` 112→149) --
about 2.15x the session's own average rate.

- **Current count capacity vs. observed peak:** 1,000 configured vs. 350
  real session total -- **2.9x margin** for the whole session; vs. the
  single worst real 5-minute interval (37) -- **27x margin** per interval;
  even a *sustained* peak-rate session (37 events/interval for all ~20
  intervals) would total ~740, still under the 1,000 cap with margin to
  spare.
- **Current age capacity vs. checkpoint cadence:** 60 minutes vs. a
  5-minute cadence -- **12x margin**, independent of event volume.
- **Time-to-eviction at observed peak:** irrelevant to loss risk at this
  milestone's fixed cadence -- even the single busiest real 5-minute
  window (37 events) is fully captured well within one checkpoint
  interval, long before the 60-minute age window could ever evict it.

**Conclusion: no capacity increase is warranted by real field evidence.**
The existing 1,000-record / 60-minute bounds, combined with the existing
5-minute checkpoint-cadence convention, already provide generous,
quantified margin against every real churn rate measured to date across
two independent, comparable cohorts. Per the governing brief's §13/§14,
no capacity change is made; the fix is entirely at layer 1 of the
preferred design order (correct the reconciliation defect), never layer 4
(increase bounded retention).

## Locked retention/extraction contract

Locked, and now proven (not merely asserted):

> For every checkpoint interval within the supported retention window,
> the field collector can retrieve every required proposal decision
> event, and the reconciler can prove it precisely (a correct, unit
> -matched completeness fraction plus an honest, artifact-aware gap
> account) -- or it can prove exactly which interval was genuinely
> evicted/uncollected and mark that interval `PARTIAL`, never silently.

Required properties, all satisfied by the implementation below:

- **Bounded memory/storage:** unchanged -- `CounterfactualRetentionConfig`
  defaults untouched; no unbounded ledger introduced or proposed.
- **Deterministic:** unchanged and re-verified -- every merge/union step
  remains order-independent (`test_reconcile_ledger_deduplicates_
  overlapping_snapshots_deterministically` still passes; the new gap
  -coverage refinement is itself order-independent, since it only inspects
  each payload's own reported facts, never their relative processing
  order).
- **Measurable eviction:** unchanged -- `retained_count`/`evicted_count`/
  `recorded_count`/`oldest_retained_offset_ms`/`newest_retained_offset_ms`
  were already correct at the ledger layer; the reconciliation layer now
  additionally reports `recovered_distinct_entity_count` (informational)
  for artifacts, like `proposal_outcomes`, whose own identity is a
  decision event rather than a stable entity.
- **No silent truncation:** the completeness fraction can no longer
  silently compare mismatched units (deduplicated entity count vs. raw
  event count); the gap check can no longer silently flag a proven-zero
  or proven-complete window as an unexplained gap.
- **Sufficient margin for realistic field churn:** proven in "Capacity/
  churn analysis" above, from real evidence, not invented.
- **Compatible with 90-105 minute sessions using periodic extraction:**
  proven directly against v13's own real 101.8-minute archive (below).

## Implementation

Entirely confined to one field-acceptance evidence-integrity tool and its
own test file -- **zero production runtime files touched, zero schema
change, zero admission/perception/truth-semantics code touched.** The
ledger writer itself (`counterfactual_lineage.py`) lives inside production
runtime code (`src/mockingbird/observation/`), but this milestone did not
need to change it at all -- the defect, and therefore the fix, is entirely
downstream, in the offline field-acceptance tooling that reads the
ledger's own already-correct API responses. (Per the governing brief's own
allowance: "changing retention/bookkeeping may be allowed only if it does
not change decision semantics" -- moot here, since nothing in the ledger
writer or retention/bookkeeping code was touched at all.)

`scripts/field_acceptance_ledger_snapshot.py`:

1. **New `_proposal_outcome_identity(record) -> (proposal_id, decided_at)`**,
   replacing `_id_identity("proposal_id")` in `_IDENTITY_FN["proposal_
   outcomes"]`. `raw_detections`/`track_generations` identities are
   unchanged.
2. **New `_ENTITY_FIELD` mapping** (`None` for `raw_detections`/`track_
   generations`; `"proposal_id"` for `proposal_outcomes`) and a new,
   purely additive `ArtifactReconciliation.recovered_distinct_entity_
   count: int | None = None` field, computed in `reconcile_ledger` and
   surfaced in the human-readable `reason` string (e.g. "350/350 unique
   records recovered (156 distinct proposal_ids), zero gaps") --
   informational only, never part of `completeness_fraction`.
3. **Gap-coverage refinement in `_accumulate_artifact`** (shared,
   unmodified in this respect, by both `reconcile_ledger` and `build_
   merged_counterfactual_window` -- per that helper's own established
   "the two can never silently diverge" design intent): a payload
   contributes proven `[0, its own session_last_offset_ms]` coverage when
   its own `recorded_count == 0`, or when `recorded_count == final_
   recorded_count` **and** at least one other, independently-fetched
   payload agrees -- see "Reconciliation semantics" for the full
   reasoning and the v12-shape guard this corroboration requirement
   preserves.
4. **`build_merged_counterfactual_window` needed no separate code
   change** -- it already shares `_accumulate_artifact` with `reconcile_
   ledger` by design, so fixing the identity function there automatically
   fixes the merged-output artifact too: the merged `proposal_outcomes`
   array now correctly contains every distinct decision event (350 for
   v13), not just one per proposal (156) -- exactly the full-history shape
   `encounter_accounting.cluster_encounters` was already built, and
   already tested, to receive and correctly reduce itself (see "Required
   proposal-outcome evidence").
5. **New, bounded, non-fatal cadence-safety-margin warning** in `collect`:
   documents the known (not API-exposed) production `max_age_ms=60min`
   assumption and warns (never fails) if `--interval-seconds` leaves less
   than 4x margin against it -- addressing the governing brief's §14 item
   3 ("align checkpoint cadence... to authoritative retention bounds")
   without inventing a live-introspection API call or touching production
   code to expose the constant.
6. **Docstring/comment updates** throughout, documenting the fixed
   contract, the real v13 numbers this fix resolves, and the confirmed
   -safe FIFO-append-order assumption discovered during test authoring
   (see "Ledger writer semantics," point 6).

No watermark/cursor mechanism was added (governing brief §15): the
existing "query everything currently retained, every checkpoint" approach
is now provably correct (100% recovery, real v13 data) and simpler; a
watermark would add complexity with no evidenced need, and the API
exposes no stable incremental cursor to build one on top of without
inventing new server-side state.

## Eviction/truncation observability

Already adequate at the ledger layer before this milestone (`retained_
count`/`evicted_count`/`recorded_count`/`oldest_retained_offset_ms`/
`newest_retained_offset_ms`, exposed on every `/observation/status`
`advanced` payload and every `/observation/counterfactual` response) --
confirmed unmodified. This milestone adds, at the reconciliation layer
only, `recovered_distinct_entity_count` (see "Implementation," point 2)
so a report author is never again confused about whether a number like
"156" describes distinct proposals or raw decision events. No pagination
or query truncation exists anywhere in this path to make observable
(confirmed by direct code read -- see "Query semantics"); nothing further
was needed there.

## V13-shaped RED->GREEN

**Against the real v13 archive** (not merely a synthetic analogue --
`git stash`-bisected against this milestone's own real, uncommitted fix):

| | `proposal_outcomes` | `raw_detections` | `track_generations` |
|---|---|---|---|
| **RED** (pre-fix, real v13 data) | `PARTIAL`, 44.57% (156/350) | `PARTIAL`, 100% (35,518/35,518), gap `(6081263, 6081819)` | `PARTIAL`, 100% (434/434), gaps `(0, 28883)`, `(6081263, 6081819)` |
| **GREEN** (post-fix, real v13 data) | **`COMPLETE`, 100% (350/350, 156 distinct proposals), zero gaps** | `PARTIAL`, 100% (35,518/35,518), gap `(6081263, 6081819)` -- **byte-identical to RED** | `PARTIAL`, 100% (434/434), gaps `(0, 28883)`, `(6081263, 6081819)` -- **byte-identical to RED** |

The RED run's own `0.44571428571428573` completeness fraction reproduces
v13's historically-reported 44.6% figure exactly. `raw_detections`/`track_
generations` are byte-for-byte identical before and after -- direct proof
of zero regression on the two artifacts this milestone must not touch
(their own residual `PARTIAL` status is the same, already-accepted,
harmless trivial-tail-window characteristic the v13 report itself
disclosed and accepted; unrelated to, and untouched by, this fix).

**Permanent, committed synthetic reproduction** (`tests/test_field_
acceptance_ledger_snapshot.py::test_reconcile_ledger_v13_shaped_high_
churn_session_is_fully_complete`): drives the **real** `Counterfactual
Ledger` (production retention config, unmodified) through a deterministic,
v13-shaped session -- 156 distinct proposals, 350 total decision events,
using v13's own real per-proposal decision-count histogram (92x1, 11x2,
7x3, 15x4, 31x5), spread across the real 6,081,819ms session span, with a
real, interleaved 300-second periodic-checkpoint cadence (21 checkpoints)
-- reconciles to `COMPLETE`, 350/350, 156 distinct proposals, zero gaps.
A companion permanent test (`..._pre_fix_identity_reproduces_44_percent_
shape`) drives the identical fixture through the *old* `proposal_id`-only
identity function and confirms it reproduces the same failure class
(collapses to 156, `PARTIAL`, completeness `< 0.5`) -- a standing guard
against ever silently reintroducing this defect.

## Burst-churn proof

`test_reconcile_ledger_burst_churn_no_accidental_event_collapse`: 200
single-shot decisions inside one ~10-second window (a fallback-chain
-shaped burst, matching v13's own real "one chain tried at least 27
ranked positions" shape, scaled up) plus one proposal that legitimately
churns `blocked_continuation_pending` across three separate, overlapping
300-second checkpoint intervals before finally resolving -- 204/204
recovered (200 single-decision proposals + 4 events for the one churning
proposal), 201 distinct entities, `COMPLETE`, zero gaps. Proves no
accidental identity-driven collapse under load, using the real ledger and
the fixed identity, and (via five identical, fully-overlapping checkpoint
payloads) that "overlapping checkpoints reconcile deterministically"
(governing brief §18) continues to hold.

## Bounded-eviction proof

`test_reconcile_ledger_deliberately_exceeded_retention_is_honest_partial_
never_complete`: a deliberately adversarial, real `CounterfactualRetentionConfig`
(`max_age_ms=100_000`, 100 seconds) paired with a much coarser 300-second
checkpoint interval -- the opposite of this milestone's own locked-safe
default, where the interval is a small fraction of the retention window.
Result: genuine, real loss (`recovered_unique_count < final_recorded_
count`), `status == PARTIAL`, a real non-empty `gaps_ms`, `overall_status
== PARTIAL` -- proving the identity and gap-coverage fixes do not
accidentally mask a genuine retention/cadence shortfall. Memory/storage
stays bounded throughout (the real, unmodified `_BoundedOffsetLedger`);
only the test's own deliberately adversarial config/cadence pairing is
new.

## Zero-activity proof

The prior accepted zero-activity fix (`test_reconcile_ledger_zero_
activity_artifact_is_complete_not_partial`, from Field Acceptance Evidence
Integrity & Storage Preflight Correctness v1) is untouched and still
passes unmodified -- its own code path (`final_recorded_count == 0`) is
not on any branch this milestone changed. Two new, additional tests
extend this guarantee precisely into the new code: `test_reconcile_
ledger_zero_activity_proposal_outcomes_reports_zero_distinct_entities`
(a genuinely empty `proposal_outcomes` artifact reports `recovered_
distinct_entity_count == 0`, not `None` or a crash) and `test_reconcile_
ledger_zero_activity_still_complete_alongside_real_v13_shaped_activity`
(a session where `proposal_outcomes` is genuinely, honestly busy but
`track_generations`/`raw_detections` are genuinely empty still reports
those two as `COMPLETE`, never dragged to `PARTIAL` merely because a
sibling artifact is large).

## Other-artifact regression proof

Proven two ways, not merely asserted: (1) the real v13-shaped `git stash`
RED/GREEN comparison above shows `raw_detections`/`track_generations`
byte-identical before and after this fix, against real data; (2) the full
existing test suite for `raw_detections`/`track_generations` reconciliation
(every pre-existing test in `test_field_acceptance_ledger_snapshot.py`
that does not concern `proposal_outcomes`) passes unmodified. Scene
-confusor snapshots, RTT snapshots, and monitoring counters are fetched
and handled by entirely separate, untouched code paths (`AUXILIARY_
ARTIFACTS`, `_fetch_artifact`'s generic success/failure handling) --
confirmed unmodified by this diff and re-confirmed passing via the full
existing `take_checkpoint`/`run_periodic_collection` test coverage,
unchanged.

## Real runtime smoke proof

A full, real, end-to-end proof -- not a full representative cohort, and no
wildlife-performance claim is made:

- Real `mockingbird.api.main.app` served over a real TCP socket
  (`tests._transport_fault_injection.RunningApp`, this project's own
  established real-uvicorn-in-a-thread test harness).
- A real, isolated SQLite `ProductRepository` (fresh db/media root), a
  real `camera_node`-provider Source/Stream created through the same
  repository API real product code uses, a real bootstrapped
  Administrator and a real field-acceptance bearer credential.
- A real `ObservationEngineSessionManager`/`_EngineSession` -- production
  retention config, the real, unmodified `CounterfactualLedger`, the real,
  unmodified `_run_assembly_tick`/admission code -- with only the
  detector and Camera Node transport substituted for this project's own
  established, already-accepted hardware-free fixtures (`_ConfirmingDetector`/
  a `_NoBurstTransport`-shaped fake, copied structurally from `tests/
  test_engine_runtime.py`'s own precedented "real production pipeline,
  fake hardware only" convention -- the identical pattern that milestone's
  own `test_end_to_end_creates_one_candidate_and_activates_authority`
  already uses). `engine_runtime._ASSEMBLY_TICK_SECONDS` was temporarily
  shortened (a module-global constant, restored in `finally`) purely so a
  short local run produces several real ticks quickly -- never a change to
  what happens *within* one tick.
- The real `scripts/field_acceptance_ledger_snapshot.py` CLI, run as an
  actual subprocess (`collect` twice, `reconcile` once) against the real
  running server, exactly as a real field session would.

**Result:** the real session produced 2 real, distinct proposal-decision
events (`blocked_continuation_pending`, then `blocked_missing_evidence`
for a second, larger proposal once the track's own boundary finalized at
session end) across 2 real distinct proposals, alongside 180 real
`raw_detections` and 2 real `track_generations`. Six periodic checkpoints
(every 2s) plus two post-stop corrective checkpoints (deliberately two,
not one -- to satisfy this milestone's own new, independently
-corroborated trailing-gap rule, exactly as a real field session's own
last periodic checkpoint plus one corrective fetch normally would) were
taken via the real CLI over real HTTP. `reconcile` (real CLI, real JSON
output) reported: every checkpoint status explicit and `COMPLETE`;
`proposal_outcomes` present and correctly typed (`blocked_continuation_
pending`, `blocked_missing_evidence`); cumulative counts fully coherent
(`recorded_count == retained_count == 2`, `evicted_count == 0`);
`overall_status: COMPLETE`; exit code `0`. No silent truncation anywhere
in the real request/response/CLI/file round trip -- confirming the
hand-rolled test-fixture mirror of the wire format used in the synthetic
Tier-1 tests matches the real, live API response shape exactly.

## V13 historical evidence status

**Unchanged, as required.** V13's own accepted `proposal_outcomes`
completeness remains **44.6%**, exactly as accepted in its own report.
This milestone fixes future collection/reconciliation only; it does not,
and must not, retroactively upgrade v13's own historical record --
confirmed no edit was made to `representative-daylight-gate-a-field
-acceptance-v13-report.md` or to v13's own accepted numbers anywhere in
`docs/release-execution-state.md`.

## Validation

**Tier 1** (focused RED->GREEN): `tests/test_field_acceptance_ledger_
snapshot.py` -- **34/34 passed** (24 pre-existing, unmodified and still
green; 10 new, covering: retryable-decision event-vs-entity counting,
genuinely-missing-event honesty, entity-count `None`/`0` correctness for
all three artifact types, merged-output full-history preservation, the
real-ledger v13-shaped high-churn reproduction plus its pre-fix-identity
regression guard, burst churn, deliberate bounded-eviction, and zero
-activity alongside real busy activity). Plus the real-data `git stash`
RED->GREEN comparison against v13's own archived checkpoints, above.

**Tier 2** (affected counterfactual/ledger/client/field-acceptance/
accounting suites): `tests/test_field_acceptance_ledger_snapshot.py
tests/test_field_acceptance_client.py tests/test_field_acceptance_
authentication.py tests/test_field_acceptance_instance_lifecycle.py
tests/test_counterfactual_lineage.py tests/test_encounter_accounting.py
tests/test_fragmentation_accounting.py tests/test_run_gate_a_measurement_
accounting.py` -- **172/172 passed**. Additionally, `tests/test_engine_
runtime.py` (the full Observation Engine session-manager suite this
milestone's own real-runtime smoke proof built on, though it touches zero
lines of that file) -- **118/118 passed**.

**Tier 3 (Core): not run.** Decision, per the governing brief's own
instruction to explain: zero production runtime files were touched by
this milestone (the entire diff is `scripts/field_acceptance_ledger_
snapshot.py` plus its own test file) -- no admission, perception,
tracking, candidate-authority, quality-gate, assembly, evidence, species,
or truth-semantics code changed at all. Tier 1 (34 tests) plus Tier 2 (290
tests across every directly-affected consumption path) already fully
cover the complete blast radius of this change. Running the full Core
suite would add real time/cost with no plausible additional signal, given
the diff's own confirmed, narrow scope.

**Lint:** `ruff check scripts/field_acceptance_ledger_snapshot.py tests/
test_field_acceptance_ledger_snapshot.py` -- clean, zero findings.

## V14 readiness

**YES.** Per the governing brief's own bar:

- Evidence-capture fix already accepted (Camera Node Evidence-Capture
  Profile Validity & Failure Observability Correctness v1) -- unchanged
  by this milestone.
- Proposal-outcome ledger preservation contract now proven: real v13
  archive reconciles `COMPLETE` after this fix; a permanent synthetic
  regression fixture, built from v13's own real event-count histogram,
  proves the same mechanism deterministically and repeatably.
- Realistic high-churn case proven: both the real v13 archive (350
  events/101.8min) and a dedicated burst-churn fixture (200+ events in a
  ~10-second window, overlapping checkpoints, legitimate re-decision
  churn) reconcile correctly.
- Bounded eviction honest: a deliberately adversarial retention/cadence
  pairing still produces an honest, accurately-diagnosed `PARTIAL`, never
  a silently masked one.
- Real smoke reconciliation successful: a genuine, real, end-to-end run
  (real server, real session, real ledger, real HTTP, real CLI) reconciled
  `COMPLETE` with fully coherent counts.
- No known evidence-integrity defect remains capable of silently
  invalidating another representative cohort's own `proposal_outcomes`
  evidence -- both real defects this investigation found (identity
  collapse; gap-coverage artifact-uniformity assumption) are fixed and
  proven; no other defect was found in the writer, retention, or query
  layers (all independently exonerated above).

## Remaining Gate A dependencies

Unchanged in substance by this milestone (this milestone does not close
Gate A, does not authorize a next milestone, and does not touch any of
the following): the pre-existing 13-item Gate A dependency list (as
narrowed through prior accepted milestones -- never-strong single
-generation confusor clearing; a second person-confound-free cohort;
full-ledger-coverage automated fragmentation re-proof; a second
independently-varied true-latency cohort; a 3+-simultaneous-subject
cohort; v7's two remaining ambiguous fragmentation units; the ~13
untraced v7 `blocked_missing_evidence` records; same-frame class
-contradiction field effect on person-associated false Visits; further
strong-confidence scene-artifact recurrence; no whole-frame human
suppression of real birds; scene-confusor participation incl.
corroboration-rejected counts; intact full-session ledger coverage;
`reject_no_identification_or_context` "vanish entirely" behavior), plus
item (14)'s own recall/evidence-survival field-re-proof half (still
`REOPENED / WAITING FOR FIELD RE-PROOF`).

**Newly closed by this milestone:** the separate proposal-outcome
ledger-cadence/completeness dependency (v13's own disclosed 44.6% gap) --
now `CLOSED / READY FOR REPRESENTATIVE FIELD RE-PROOF`.

The next representative field cohort must still gather: complete/intact
ledger evidence (now genuinely achievable, per this milestone); an
independent denominator; recall; false-Visit rate; fragmentation;
duplicates; useful evidence; evidence survival; true RTT-normalized
latency; monitoring coverage; `classifier_same_frame` field
participation; dead-anchor field participation; ambiguous-boundary
evidence; precision-mechanism participation; Gate B check. No numeric
release budget is invented or advanced by this milestone.

## Decision

**A**

Every acceptance-bar item is met: v13's 44.6% result is precisely
explained (a reconciliation-layer identity mismatch, not a retention/
query/writer defect); the first irreversible loss is identified as
**none** (100% of v13's real decision events were always recoverable);
required evidence semantics were made explicit before implementation;
root cause classified (E); the contract was locked (and, where a second
defect was found mid-validation via the real-runtime smoke proof, fixed
in the same pass rather than deferred, exactly as the governing brief's
own "do not solve a query bug by allocating a giant cache" / "correct the
reconciliation defect first" preference intends); the solution is
bounded (zero unbounded ledger, zero capacity increase, zero production
runtime code touched); high-churn v13-shaped RED->GREEN is proven against
both real archived data and a permanent synthetic fixture; burst churn is
proven; duplicate/identity correctness is proven; deliberate eviction
produces an honest, explicit `PARTIAL`; zero-activity remains `COMPLETE`;
prior artifacts (`raw_detections`/`track_generations`) do not regress
(byte-identical against real data); a real end-to-end smoke reconciliation
succeeds; Tier 1 (34/34) and Tier 2 (290/290) are green; lint is clean; no
admission/perception/truth semantics were changed; v13 remains
historically 44.6%, unchanged; and the evidence pipeline is demonstrably
ready for the next representative Gate A cohort.
