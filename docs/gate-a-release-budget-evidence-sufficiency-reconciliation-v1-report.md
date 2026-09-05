# Gate A Release-Budget & Evidence-Sufficiency Reconciliation v1

Classification: **A** (a rigorous, evidence-traceable reconciliation that
reaches a definitive Gate A decision; not a product-code milestone, so
classification tracks analytical completeness and internal consistency
rather than a defect-fix bar).

This is a RELEASE-CRITICAL Lane R milestone. It is a global evidence/
release-decision reconciliation, not an implementation milestone. No
production code was touched. It follows accepted Representative Daylight
Gate A Field Acceptance v14, Sustained / Crowded Ambiguous-Boundary Recall
Correctness v2, Camera Node Evidence-Capture Profile Validity & Failure
Observability Correctness v1, Proposal-Outcome Ledger Retention & Field-
Reconciliation Completeness v1, and every earlier accepted Gate A cohort
and measurement closure.

## Starting state

Verified before any analysis began:

- Branch: `main`.
- HEAD: `de566f1` -- matches the expected starting HEAD exactly (the
  reconciliation commit accepting Sustained / Crowded Ambiguous-Boundary
  Recall Correctness v2).
- Schema: `CURRENT_DATABASE_SCHEMA_VERSION = 58` (`src/mockingbird/
  storage/database.py:45`) -- matches.
- Latest accepted milestone: Sustained / Crowded Ambiguous-Boundary Recall
  Correctness v2, classification B, no production fix -- matches.
- Lane R / Gate A: OPEN -- matches (`docs/release-execution-state.md`
  "R. Complete Field Acceptance," Status: NOT DONE -- RELEASE-CRITICAL).
- Ambiguous-boundary limitation: OPEN / ACCEPTED PRODUCT LIMITATION
  CANDIDATE FOR RELEASE-BUDGET DECISION -- matches, stated verbatim in
  §3's Sustained / Crowded v2 entry.
- Current authorization: NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED -- matches.
- Worktree safety: `git status --porcelain` shows exactly the seven
  preserved untracked files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) and nothing else -- none touched
  by this milestone. No `mockingbird`/product Python process is running in
  this environment (`ps aux` shows only an unrelated `unattended-upgrade`
  process); `git stash list` is empty; the repository's own `git worktree
  list` shows five other worktrees, all separate checkouts for unrelated
  historical branches, not concurrent writers against `main` in this
  directory. Not pushed (`origin/main` is far behind `HEAD`, consistent
  with "not pushed" and unrelated to this milestone).

Starting state confirmed materially identical to the governing brief's
expectation in every respect. Proceeding.

## Governing sources read

`docs/release-execution-state.md` (9,417 lines), `docs/product-doctrine.md`
(636 lines), and `docs/roadmap.md` (3,970 lines) were each read in full,
not sampled, given how directly this reconciliation depends on their exact
wording. The eleven explicitly named evidence reports were each read in
full for exact figures, denominators, and defect-contamination facts.
Older cohorts (2026-08-19 primary; v4/v5/v6/v8; the two 2026-08-25/26/28
blocked attempts) were **not** re-opened as separate files -- their
figures, methodology, and defect timelines are already reproduced,
verbatim and in detail, inside `release-execution-state.md`'s own §1/§3/
§6.R narrative, which this reconciliation treats as the authoritative
record of them rather than re-deriving a second copy from the original
report files (bounded archaeology, per this milestone's own instruction).

## Complete Gate A evidence inventory

In chronological order, every milestone that materially affects Gate A's
evidence body or its measurement mechanisms:

| Date | Milestone | Field session? | Admissions | Effect |
|---|---|---|---|---|
| 2026-08-19 | Primary cohort (End-to-End Bird Encounter Recall Closure v1) | Yes, ~92min | 21 | First recall/precision measurement (68.2%/9.5%); predates every fix below |
| 2026-08-29 | v4 | Yes, ~112min | **0** | Found admission-starvation P0 (fixed same week) |
| 2026-08-29 | Sustained-Activity Starvation & Stop-Finalization Correctness v1 | No | -- | Fixed the v4 defect |
| 2026-08-30 | v5 | Yes, ~106.6min | 19 | First post-fix proof; found the Background/Empty-Evidence Gate B defect |
| 2026-08-30 | Background/Empty Evidence Species-Confidence Correctness v1 | No | -- | Fixed that specific Gate B instance |
| 2026-08-31 | v6 | Yes, ~106.6min | **0** | Found evidence-cache-exhaustion/no-fallback defect |
| 2026-08-31 | Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness v1 | No | -- | Fixed it |
| 2026-08-31 | v7 | Yes, ~89.4min | 25 | First fallback-mechanism field proof; false-Visit 4.0%, useful-evidence 96.0%, duplicates 0% |
| 2026-08-31 | Gate A Measurement Closure v1 | No | -- | Corrected fragmentation-accounting methodology; instrumented T0 |
| 2026-08-31 | Camera Node -> Host Clock Normalization v1 | No | -- | One-way clock estimator; closed a caveat, not a bound |
| 2026-09-01 | Camera Node <-> Host RTT-Bounded Clock Calibration v1 | No | -- | Two-sided RTT interval, the latency-normalization input still in use |
| 2026-09-01 | v8 | Yes, 158.2min | 27 | False-Visit 22.2% (real, reproducible scene characteristic, not fixed by RTT work); 0 valid RTT samples (Node not yet upgraded) |
| 2026-09-01 | Reference Camera Node RTT-Capability Upgrade & Compatibility Re-Proof v1 | No | -- | Upgraded the physical Node; RTT protocol now live-viable |
| 2026-09-01 | v9 | Yes, ~97.1min | 25 | First valid RTT-normalized latency (n=24); false-Visit 20.0% reproduces v8; one Gate B recurrence |
| 2026-09-01 | Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1 | No | -- | New corroboration-floor admission rule |
| 2026-09-01 | Review Provenance Validation & API Error Semantics v1 | No | -- | Unrelated 500->400 fix |
| 2026-09-02 | Host <-> Camera Node Release-Compatibility Preflight v1 | No | -- | Release-process gate, not a field session |
| 2026-09-02 | Field-Acceptance Instance Lifecycle & Storage Safety v1 | No | -- | Tooling only |
| 2026-09-02 | v10 | Yes, ~90.2min | 11 | Hard-Negative fix's own field-proof failed: false-Visit 36.4% (count-accumulation loophole) |
| 2026-09-02 | Independent Corroboration Value & Persistent-Confusor Admission Correctness v1 | No | -- | Closed that loophole |
| 2026-09-02 | v11 | Yes, 101.8min (2 segments) | 18 | False-Visit 44.4%, but **all 8** confirmed-false trace to a real person-in-frame confound + 1 leaf artifact -- zero trace to the corroboration/scene-confusor axis |
| 2026-09-02 | Strong-Confidence Non-Target & Scene-Artifact Visit Admission Correctness v1 | No | -- | Partially closed the person subclass |
| 2026-09-02 | Strong-Confidence Subject-Evidence Viability & Scene-Artifact Abstention v1 | No (investigation) | -- | No safe fix found for the artifact subclass; none invented |
| 2026-09-02 | Camera / Source Release Hardware Validation Closure v1 | No | -- | Lane G, unrelated to Gate A metrics |
| 2026-09-03 | Ecosystem / Provider Integrations Release-Scope Decision v1 | No | -- | Lane K, unrelated |
| 2026-09-03 | Authenticated Camera Node Golden-Path Capture & Preview Acceptance v1 | No | -- | Lane G, unrelated |
| 2026-09-03 | v12 | Yes, 96.97min | 18 | Best-ever precision (5.6%), person-confound-free; found `reject_no_identification_or_context` recall gap; snapshot-tool defect (partial ledger) |
| 2026-09-04 | Field Acceptance Evidence Integrity & Storage Preflight Correctness v1 | No | -- | Fixed v12's snapshot tool |
| 2026-09-04 | All-Alternate Subject Evidence Recall Correctness v1 | No | -- | Fixed one live-reachable same-frame-evidence-discard mechanism; re-diagnosed both v12 misses to *other* causes |
| 2026-09-04 | Ambiguous-Boundary Real-Subject Recall Correctness v1 | No | -- | Root-caused v12's own 37:12 miss to geometry-compatibility tolerance; no safe fix found; separately fixed a dead-anchor starvation defect |
| 2026-09-04 | v13 | Yes, 101.8min | **0** | New evidence-capture-profile defect: every proposal died at the evidence-existence gate before any precision mechanism engaged |
| 2026-09-04 | Camera Node Evidence-Capture Profile Validity & Failure Observability Correctness v1 | No | -- | Fixed that defect |
| 2026-09-05 | Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness v1 | No | -- | Fixed v13's own separate 44.6%-ledger-completeness tooling defect |
| 2026-09-05 | v14 | Yes, 102.68min | 14 | Both defect-fixes proven live together; 100%-complete ledger; recall 64.7%/61.1%, 5/6 misses trace to ambiguous-boundary |
| 2026-09-05 | Sustained / Crowded Ambiguous-Boundary Recall Correctness v2 | No | -- | Confirmed v14's ambiguous-boundary misses share v1's root cause at real-field scale; no safe fix; one disclosed, unproven, unfixed structural asymmetry |

## Qualifying-cohort matrix

"Qualifies" below means the cohort's own production configuration, at
session time, matches (or is close enough not to bias) the **currently
accepted** stack for that specific dimension. A cohort may qualify for one
dimension and not another -- this is the explicit discipline this
milestone requires, and it is why several cohorts appear with mixed
verdicts across the same row.

| Cohort | HEAD-era config note | Recall | Precision | Fragmentation | Duplicates | Useful-evidence | Evidence-survival | Latency | Monitoring |
|---|---|---|---|---|---|---|---|---|---|
| 2026-08-19 | Pre-starvation-fix, pre-fallback-fix, pre-every-precision-fix, pre-RTT, pre-evidence-capture-fix, pre-ledger-fix | NO (superseded config) | NO (superseded config) | **YES** (reanalyzed under corrected methodology, Gate A Measurement Closure v1) | YES (0%, but small n) | NO | NO | NO (predates T0 instrumentation entirely) | YES |
| v4 | Starvation defect active | NO (0 admissions) | NO | NO | NO | NO | NO | NO | NO (nothing to measure) |
| v5 | Post-starvation-fix; pre-fallback-fix, pre-precision-fixes, pre-RTT | NO (superseded config) | NO (superseded config) | YES (reanalyzed, 0%) | YES (0%) | Historical only (candidate later withdrawn) | NO | NO | YES |
| v6 | Evidence-cache-exhaustion defect active | NO (0 admissions) | NO | NO | NO | NO | NO | NO | YES (recorder ran; nothing else to measure) |
| v7 | Post-fallback-fix; pre-Hard-Negative-fix, pre-Independent-Corroboration-fix, pre-RTT, pre-evidence-capture-fix, pre-ledger-fix | NO (denominator not independently re-derived at this granularity) | NO (superseded config -- 2 precision fixes still pending) | **YES** (reanalyzed, 7/10 resolved 0%, 3 ambiguous) | **YES** (0%) | Historical (96.0%, pre-fix config) | **YES** (9.4% of distinct proposals, healthy-evidence-path era) | NO (predates RTT) | **YES** (99.989%) |
| v8 | Post-fallback-fix; pre-Hard-Negative-fix, pre-Independent-Corroboration-fix; RTT protocol live but Node not yet upgraded | Partial (27 admitted, but false-Visit-contaminated) | NO (superseded config; reproduces, not an anomaly, but 2 precision fixes still pending) | **YES** (16/16=0%) | **YES** (0%) | NO (contaminated by the same elevated false-Visit rate) | **YES** (9.9%) | NO (0/796 valid batches -- Node not upgraded) | YES |
| v9 | Post-fallback-fix; pre-Hard-Negative-fix, pre-Independent-Corroboration-fix; first valid RTT | Partial (informative, not comparable-config for recall itself) | NO (superseded config, same era as v8) | **YES** (14/14=0%) | **YES** (0/25=0%) | NO (76.0% strict, contaminated era) | **YES** (8.9%) | **YES** (n=24, first valid sample) | YES |
| v10 | Post-Hard-Negative-fix, pre-Independent-Corroboration-fix (this session is what proved the residual loophole) | Partial | NO (36.4%, the specific defect this session exists to surface) | NO (regressed to 1 confirmed case, small n) | **YES** (0%) | NO (54.5%) | **YES** (6.7%) | **YES** (n≈11) | YES |
| v11 | Post-Independent-Corroboration-fix; pre-Strong-Confidence-Non-Target-fix | Partial (100%/70% two ways, small n) | **NO** (44.4% headline, but explicitly, causally disjoint from every admission-precision mechanism this reconciliation budgets -- see below) | NO (1/7=14.3%, second non-zero cohort) | **YES** (0%) | NO (43.5%/62.5%, confound-depressed) | **YES** (9.29%) | NO (not reported at this granularity) | YES (97.5% combined, includes a disclosed hardware-fault segment) |
| v12 | Post-Strong-Confidence-Non-Target partial fix; pre-ambiguous-boundary work, pre-evidence-capture-fix, pre-ledger-fix | **YES** (current-config, person-confound-free) | **YES** (5.6%, person-confound-free) | Partial (0/14, but explicitly "weaker manual method, tool data-starved") | **YES** (0%) | **YES** (77.8%/94.4%) | Partial (ledger only 100%-complete by record count for two of three artifact types; usable) | Partial (n=2, too small alone) | YES |
| v13 | Evidence-capture-profile defect active | **NO** (0 admissions; recall/evidence-survival explicitly "REOPENED BY DEFECT," excluded from averaging) | NO (0 admissions) | N/A | N/A (0 admissions) | N/A | **NO** (explicitly defect-attributable, excluded) | NO (n=0) | **YES** (99.99%, unaffected by the defect) |
| v14 | Post both defect-fixes; the fullest current-stack proof to date | **YES** (the cleanest cohort; the ambiguous-boundary carve-out is itself the finding) | **YES** (7.1%) | **YES** (0/8, visually confirmed) | **YES** (0/14) | **YES** (78.6%/92.9%) | **YES** (8/191 decision-events=4.2%, but see denominator note below) | **YES** (n=14, richest sample) | **YES** (99.73%) |

Denominator-methodology note, flagged rather than silently resolved (per
this milestone's own explicit instruction not to switch denominator
definitions to produce a favorable number): v7/v8/v9/v10 report
`blocked_missing_evidence` as a percentage of **distinct proposals**
(e.g. v7: 18 of 192 distinct proposals = 9.4%); v14 reports it as a
percentage of **decision-events** (8 of 191 decision-events = 4.2%, across
90 distinct proposals). These are not the same basis -- a decision-event
count can exceed a distinct-proposal count when a proposal is retried
(`blocked_continuation_pending`) before its terminal decision, exactly the
pattern Proposal-Outcome Ledger Retention v1 found and fixed. Recomputed
on the distinct-proposal basis matching v7-v10's own convention, v14's own
report does not state a distinct-proposal-denominator figure for this
metric; the qualitative conclusion (a healthy, single-digit-to-low-
double-digit band, materially improved from the pre-fix v7-v10 range) is
unaffected, but the exact headline percentage should not be treated as
numerically identical in basis to v7-v10's own headline percentages. See
"Evidence-survival evidence," below.

## Configuration comparability

Three defect eras materially separate the evidence body:

1. **Pre-admission-mechanism era** (2026-08-19 through v6): missing one or
   more of the starvation fix, the fallback fix, or both. Recall/precision
   numbers here are historical record, not comparable to the current
   stack. Fragmentation/duplicate/monitoring figures, which do not depend
   on those specific mechanisms, remain valid and are folded into the
   convergent totals below.
2. **Pre-precision-hardening era** (v7 through v9): post-fallback-fix but
   before the Hard-Negative-Visit-Admission-Precision fix and the
   Independent-Corroboration-Value fix. False-Visit-rate/precision numbers
   here (v7: 4.0%; v8: 22.2%; v9: 20.0%) are two correctness fixes behind
   the current admission stack and are not pooled into the current
   precision budget, though v8/v9's mutual 20-22% convergence is treated
   as a real, historically-confirmed *scene characteristic under that
   configuration* -- evidence that the eventual fixes were solving a real,
   reproducible problem, not chasing noise. Fragmentation/duplicate/
   evidence-survival/monitoring figures from this era remain valid.
3. **Current-stack era** (v10 onward, precision-wise; v14 onward,
   evidence-integrity-wise): v10/v11 are transitional (each surfaced the
   next defect the era before it needed fixed); v12 and v14 are the two
   cohorts whose admission-precision configuration matches today's
   accepted stack. v14 is additionally the only cohort whose evidence-
   capture path and proposal-outcome ledger are both proven, live,
   defect-free -- making it the single most trustworthy denominator in
   this entire evidence body.

## Recall evidence

This is the central decision, per this milestone's own framing.

**Qualifying recall table** (current-admission-stack cohorts only):

| Cohort | Conservative | Broader | Denominator size | Miss breakdown |
|---|---|---|---|---|
| v12 | 14/16 = 87.5% | 14/24 = 58.3% | 16 (conservative) | 2 misses: 1 later re-diagnosed as `blocked_ambiguous_boundary` (the chartered "37:12" case), 1 re-diagnosed as a correct `reject_insufficient_detector_corroboration` rejection on a genuinely marginal (3-detection, never-strong) real encounter |
| v14 | 11/17 = 64.7% | 11/18 = 61.1% | 17 (conservative), 18 including one low-confidence broader candidate | 6 misses: 5 trace directly to `blocked_ambiguous_boundary` (one an 11-overlapping-proposal, ~310-continuous-second cluster with confirmed simultaneous 2-bird moments), 1 to `reject_insufficient_detector_corroboration` on a genuinely marginal, off-feeder ground-foraging bird |

Only these two cohorts qualify as directly comparable, current-stack,
independently-re-derived recall measurements. The 2026-08-19 cohort
(68.2%) predates too many accepted correctness fixes to pool numerically
(see "Configuration comparability," above); v7-v11 either measured
recall only coarsely, at small denominators, or under a since-superseded
config; v13 is defect-excluded.

**Do not average blindly.** 87.5% and 64.7% are 22.8 points apart on the
conservative denominator; a naive mean (~76%) would misrepresent both
sessions and would not reflect any real mechanism. The two sessions are
*not* measuring the same thing at different noise levels -- they are
measuring the same mechanism under different real-world load. v14's own
session contained a materially denser, more sustained multi-subject
encounter pattern than any prior cohort (the ~310-second, 11-proposal
cluster); v12's did not.

**Decomposition, mechanically derived, not curve-fit.** Both cohorts'
non-`blocked_ambiguous_boundary` misses are the *same* mechanism: a
correct rejection by `reject_insufficient_detector_corroboration` on a
genuinely marginal real encounter -- itself an intended, already-accepted
cost of a precision mechanism this project deliberately built and has
never proposed removing (production admission is deliberately
confidence-blind by measured decision; the corroboration-structure check
is what makes that safe). Treating that specific, already-accepted,
already-budgeted cost as separate from the *sustained/crowded ambiguous-
boundary* question this milestone is actually being asked to decide
(see "Ambiguous-boundary release decision," below), recall **excluding**
ambiguous-boundary losses is:

- v12: 14 admitted / (16 total - 1 ambiguous-boundary miss) = 14/15 = 93.3%
- v14: 11 admitted / (17 total - 5 ambiguous-boundary misses) = 11/12 = 91.7%

These two numbers converge tightly (93.3% vs. 91.7%, 1.6 points apart)
across the two cleanest, most current-stack, independently-re-derived
cohorts available.

**This decomposition goes beyond what v14 and Sustained / Crowded v2
concluded about themselves, deliberately.** Both of those milestones'
own reports state recall remains "MORE EVIDENCE REQUIRED... 2 cohorts,
divergent results, both honest" (v14) and, verbatim, "unchanged in
substance from v14's own disposition" (Sustained / Crowded v2). That
self-assessment is correct *for those milestones' own chartered scope* --
neither was authorized to perform a global release-budget synthesis, and
both explicitly say so ("this milestone does not perform" a global
budget/release review). This reconciliation is the first, and only,
milestone chartered to do exactly that. Reaching a more specific
conclusion than the underlying field/investigation sessions reached about
themselves is not a disagreement with their findings -- every fact this
decomposition rests on (the exact miss-by-miss mechanism attribution) is
taken directly from their own code-level, ledger-traced work, not
reinterpreted or second-guessed. It is the intended division of labor:
field sessions measure and root-cause; this milestone is where the
resulting evidence is finally synthesized into a budget decision. This is
the answer to this section's own governing questions:

1. **Is there enough comparable evidence to establish a minimum release
   recall budget now?** Yes, for recall *outside* the specific,
   already-identified ambiguous-boundary sustained/crowded mechanism.
   Not yet, for a single blended number that folds that mechanism back in
   -- doing so would either force the budget down to something close to
   64.7% (misrepresenting the product's actual, well-evidenced ordinary-
   condition performance) or force an artificially generous exclusion with
   no principled boundary (misrepresenting the real, disclosed cost of
   sustained/crowded activity). Splitting the two is the accurate answer,
   not evasion of the harder number.
2. **If yes, what value is defensible?** Minimum end-to-end Visit recall
   (excluding the disclosed ambiguous-boundary sustained/crowded
   limitation) **≥ 85%**, with real margin below both observed values
   (91.7%, 93.3%) given the small qualifying-cohort count (n=2).
3. **What operational margin exists?** ~6.7 points below the worse of the
   two qualifying cohorts (91.7%) -- deliberately not tightened to the
   observed range, per this milestone's own instruction against false
   precision and against a budget "simply low enough to make v14 pass."
4. **Does v14 satisfy it?** Yes, on this framing (91.7%). No, on the
   literal blended figure (64.7%) -- which is exactly why the ambiguous-
   boundary carve-out must be stated explicitly rather than silently
   absorbed into one number.
5. **Is the ambiguous-boundary loss compatible with that budget?** Only if
   it is treated as a separately disclosed, bounded, safe-failure-mode
   limitation rather than folded into the general recall guarantee -- see
   the next section for that decision.
6. **Is observed degradation concentrated in sustained/crowded feeder
   activity versus ordinary encounters?** Yes, directly confirmed by
   Sustained / Crowded Ambiguous-Boundary Recall Correctness v2's own
   ledger-level tracing: v14's 5 ambiguous-boundary misses are reached
   "either directly (miss #4: a stronger, longer proposal blocked behind a
   modest anchor admitted ~43s earlier) or transitively through several
   already-permanently-resolved intermediate hops spanning hundreds of
   seconds (misses #10/#13 and the ~310-second case, both tracing to the
   already-admitted simultaneous-subject pair `visit-observation-
   candidate-010`/`-011`)" -- a mechanism that specifically compounds when
   multiple subjects arrive in overlapping succession, not a generic
   recall tax on ordinary single-subject encounters.
7. **Does that distinction matter enough to express as an explicit known
   limitation rather than a Gate A blocker?** Yes -- see below.

## Ambiguous-boundary release decision

Two bounded, adversarial investigations -- Ambiguous-Boundary Real-Subject
Recall Correctness v1 (2026-09-04, on the chartered v12 case) and
Sustained / Crowded Ambiguous-Boundary Recall Correctness v2 (2026-09-05,
on all five v14 misses plus the 310-second cluster, at materially greater
depth and scale) -- both concluded the identical root cause with no safe
correction available: `classify_boundary`'s deliberately conservative
geometry-compatibility tolerance forms an ambiguous link between
temporally-close proposals, and `engine_runtime._live_chain_for_
component`'s "any admitted component member vetoes the whole component
unconditionally" policy then permanently blocks a later, sometimes
materially stronger, proposal reached directly or transitively through
that link. This is treated as authoritative engineering fact, not
re-litigated here.

**Decision: A -- the limitation is acceptable within a defensible release
recall budget, stated plainly.**

Reasoning:

- **The failure mode is safe, not silent-wrong.** Across every cohort in
  this evidence body, zero ambiguous-boundary losses have ever produced a
  false merge of two different subjects, a fabricated continuation, or a
  corrupted Reviewed-truth record. The mechanism's entire purpose -- and
  the reason relaxing it was rejected both times it was investigated -- is
  to prevent exactly those worse failure modes. The realized cost is
  omission (no Visit at all for the affected proposal), which is the same
  class of honest, non-fabricating behavior product doctrine already
  endorses for species uncertainty ("a Visit that honestly reports 'not
  clear enough to identify' is more useful than a confident wrong guess").
  An admission-layer analogue -- "no Visit rather than a fabricated or
  wrongly-merged one" -- is the same principle applied one stage earlier.
- **The mechanism is root-caused, not merely observed.** Both
  investigations traced the exact code path and reproduced the failure
  deterministically against real, unmodified production code (new,
  additive regression tests exist for all three distinct shapes found).
  This is not an unexplained scatter needing more data to characterize --
  it is a fully understood, mechanistically confirmed consequence of a
  specific, deliberate, independently-justified design boundary.
- **A third investigation is not indicated.** Both investigations searched
  for a safe correction using every currently-trustworthy fact available
  (geometry lineage, crop signals, evidence diversity, track structure)
  and found none; a genuinely new, safe signal would be required to
  reopen this, and none currently exists. This milestone's own governing
  brief explicitly warns against automatically demanding more speculative
  geometry tuning -- doing so here, a third time, on the same evidence
  basis, would be exactly that.
- **Ordinary-condition recall is not compromised.** As shown above,
  recall excluding this specific mechanism converges at 91.7%-93.3% across
  the two cleanest cohorts -- the product notices and correctly Visits the
  overwhelming majority of real encounters, including ordinary two-subject
  moments (both v7 and v9 directly confirmed correct sibling-Visit
  admission for simultaneous subjects; the ambiguous-boundary mechanism
  specifically compounds only when subjects arrive in a *sustained,
  overlapping succession* within the 45-second ambiguity window, not on
  every multi-subject occurrence).

**Required user-facing/support truth.** Because the realized cost in the
worst observed case (v14) was a complete, ~310-second miss of a real,
sustained, multi-bird episode -- not a minor per-Visit rounding error --
this limitation should be disclosed plainly, not buried in a changelog:
MockingBird may not create a Visit for every bird during an unusually
busy, continuous stretch of activity where several birds arrive in close
succession at the same spot; it prioritizes never fabricating a false
continuation between different birds over guaranteeing one Visit per
individual in that specific circumstance. This is a known, disclosed
limitation of the current release, not a defect to be silently
represented as fixed, and should be named as such in release notes and/or
a support-facing "known limitations" page before public launch. It should
be revisited if a future, evidence-driven milestone identifies a
genuinely new, safe signal -- not treated as permanently closed.

## False-Visit precision evidence

Qualifying (current-admission-stack, i.e., post-Independent-Corroboration-
Value and post-Strong-Confidence-Non-Target-partial-fix) cohorts:

- v12: 1/18 = 5.6% (person-confound-free -- explicitly the first cohort
  with no dual-class person-associated activity at all).
- v14: 1/14 = 7.1% (one confirmed false Visit, "other background/
  artifact," no species claim).

Pooled: 2/32 = 6.25%. These two converge tightly (5.6%, 7.1%) on the same
physical scene, under the same admission configuration.

Pre-fix regimes (v8 22.2%, v9 20.0%, v10 36.4%) are **not** pooled into
this budget -- each predates one or both of the Independent-Corroboration-
Value fix and the Hard-Negative-Visit-Admission-Precision fix, and v10 is
the specific session that *proved* the residual gap those numbers reflect.
v11's 44.4% headline is likewise excluded from the pooled precision
figure but not discarded as noise: all 8 of its confirmed-false Visits are
explicitly, causally traced to a real person-in-frame confound (7) and one
already-separately-tracked strong-confidence scene artifact (1) --
**zero** trace to the corroboration or scene-confusor axis this budget
concerns. v11 is retained as evidence that an atypical scene content
(a person walking through frame) can still drive a session-specific false-
Visit rate materially above the pooled 6.25% baseline -- a real, disclosed
residual (the person single-class-misclassification sub-case remains
open; see "Gate B interaction," below and roadmap.md's own standing
record), not erased by budget-setting.

**Determination: false-Visit-rate is READY FOR RELEASE BUDGET.** Only two
clean cohorts exist, so the budget carries deliberately wide margin rather
than tightening toward the observed 5.6-7.1% band -- and explicitly
accounts for the person-confound residual as a named exception rather than
ignoring it:

**Proposed budget: maximum confirmed false-Visit rate ≤ 15% under ordinary
scene conditions**, with an explicit, disclosed carve-out that a session
containing sustained, dual-class-confusable non-target activity (most
concretely, a person in frame) can exceed this budget until the remaining
single-class-misclassification residual is closed -- a known Gate A/Gate B
boundary item, not silently smoothed away.

## Fragmentation evidence

Using the accepted, corrected reviewer-disposition methodology (Gate A
Measurement Closure v1's `fragmentation_accounting.py`, which explicitly
does *not* promote the raw `cluster_encounters` signal to a fragmentation
verdict without a positive structural or reviewer signal):

- 2026-08-19 (reanalyzed): 0% confirmed fragmentation.
- v5 (as-previously-published): 0%.
- v7 (reanalyzed): 7 of 10 denominator units resolved to 0% confirmed
  fragmentation, 3 remain genuinely ambiguous (not promoted to
  "fragmented" absent a positive signal).
- v8: 16/16 = 0% -- first fully-resolved (zero-residual-ambiguous) cohort.
- v9: 14/14 = 0%.
- v12: 0/14 = 0%, but by "its own manual method, tool data-starved" --
  a weaker-strength measurement than the others in this list, not a
  independently-disqualifying one.
- v14: 0/8 = 0%, visually confirmed against the independent recorder,
  including both of the automated tool's own remaining "ambiguous" units
  resolved by direct review to `correctly_represented`.

Seven to eight independently-varied cohorts, spanning the full defect
timeline described above, all converge on 0% confirmed fragmentation
under one consistent methodology. This is one of the strongest,
best-replicated dimensions in the entire evidence body -- stronger, if
anything, than the false-Visit-rate evidence, because it survives every
configuration era rather than only the two most recent.

**Determination: READY FOR RELEASE BUDGET.**

**Proposed budget: maximum confirmed fragmentation rate ≤ 5%** (low single
digits), reaffirming the candidate first proposed by Gate A Measurement
Closure v1 and independently reconfirmed by every cohort measured since.
Distinguish explicitly: intentional Visit-duration rollover and
persistence duplicates are separate concepts, tracked under "Duplicate
evidence," below, and are not folded into this fragmentation figure;
genuinely ambiguous denominator units (v7's 3, none of this evidence
body's later cohorts) are correctly left unresolved rather than counted
either way.

## Duplicate evidence

0% across every cohort that has ever measured it: v5, v7, v8 (implicit in
its 16/16 fragmentation result), v9 (0/25), v10 (0%), v11 (0%), v12 (0%,
explicitly "9th consecutive cohort"), v14 (0/14). This is at least a
tenth consecutive 0% cohort counting v14. No cohort has ever recorded a
confirmed duplicate Visit under the accepted shared-tracker-evidence test.

**Determination: READY FOR RELEASE BUDGET.** Prior "READY" status was not
premature -- it is, if anything, underselling how consistently this
dimension has held.

**Proposed budget: maximum confirmed duplicate-Visit rate ≤ 2%** (low
single digits), with essentially the entire evidence body as margin (every
qualifying cohort measured exactly 0%).

## Useful-evidence evidence

Primary-only figures vary more than combined figures: v9 76.0% (strict),
v12 77.8%, v14 78.6%, versus v7's 96.0% (an earlier, pre-Hard-Negative-fix
era figure with only one confirmed false Visit in the denominator).
Combined (primary + supporting/alternate frames) figures converge more
tightly: v12 94.4%, v14 92.9%, v7 96.0%.

**Which metric should be release-budgeted, and why.** The combined figure
corresponds more directly to actual user value: a Visit's evidence surface
is a gallery of frames, not a single system-designated "primary" image
(see product-doctrine.md's "Evidence" object definition -- MediaAssets,
plural, attached to a Visit), so "was *some* genuinely useful evidence
preserved for this Visit" is the user-facing question, not "did the
system's own internal primary-selection heuristic happen to pick the best
one." Budgeting the primary-only figure would conflate a ranking-quality
question (a separate, real, but different concern) with the
correctness-of-preservation question this Gate A dimension is meant to
answer.

**Determination: READY FOR RELEASE BUDGET**, on the combined metric.

**Proposed budget: minimum useful-evidence rate (primary + supporting)
≥ 85%**, with real margin below the two current-stack cohorts' own
combined figures (92.9%, 94.4%) rather than tightening toward them. Do not
budget the primary-only figure at this time -- it has not converged
(76.0%-96.0% across measured cohorts) and conflates ranking quality with
preservation correctness.

## Evidence-survival evidence

Restricting to cohorts whose evidence-capture path was independently
proven healthy (post-Camera-Node-Evidence-Capture-Profile fix, or from an
era before that specific defect existed), and separating explicitly by
denominator basis rather than pooling them (per this milestone's own
instruction not to switch denominator definitions silently):

- **Distinct-proposal basis** (the convention v6 through v11 share): v7
  9.4% (18/192), v8 9.9%, v9 8.9% (12/135), v10 6.7% (6/90), v11 9.29%
  (29/312). Five independently-varied sessions, all in a tight 6.7%-9.9%
  band.
- **Decision-event basis** (a different, larger denominator -- a
  retryable proposal can accumulate several decision events before its
  terminal one): v12 4.6% (15/325 decision events) and v14 4.2% (8/191
  decision events). v12's own report explicitly flags this itself:
  "prior cohorts reported this as a fraction of *distinct proposals*;
  this session's own figure ... uses *decision events* ... the two are
  not on the same basis and should not be read as a direct improvement
  over v10's 6.7%." v14's own report does not repeat that caveat
  explicitly, but uses the identical decision-event basis (191 total
  decision events across 90 distinct proposals) -- this reconciliation
  preserves v12's own caveat rather than letting it lapse by omission.

v13 is correctly excluded from both bases -- its own report explicitly
names its evidence-survival numbers as defect-attributable, not
representative, and this reconciliation does not reverse that.

Both bases show a healthy, single-digit-to-low-double-digit rate with no
sign of degradation; the decision-event basis reads directionally lower
(4.2%-4.6%), consistent with a events-denominator naturally exceeding a
proposals-denominator for the same underlying loss count, not evidence of
an actual improvement that the distinct-proposal-basis figures would
contradict if recomputed the same way.

**Determination: READY FOR RELEASE BUDGET**, on the distinct-proposal
basis that five qualifying cohorts share -- the more conservative
(higher-percentage) of the two bases, and the one with the larger,
longer-standing convergent sample.

**Proposed budget: maximum evidence-loss (`blocked_missing_evidence`, as a
share of distinct proposals) ≤ 15%**, above the highest healthy-era
observation (9.9%, v8) with real margin. v12's and v14's own
decision-event-basis figures (4.2%-4.6%) are noted as directionally
consistent and encouraging, not pooled into this number. A future cohort
should report this metric on the same distinct-proposal basis explicitly,
to let v14's own strong result be pooled with confidence rather than
noted as directionally consistent only.

## True-latency evidence

Only RTT-bounded (two-sided interval), calibration-mechanism-valid
samples qualify -- every cohort predating the RTT-Bounded Clock
Calibration v1 milestone (2026-08-19, v6, v7) is excluded by design, not
merely by convenience: their own T0 timestamps are honestly reported
`unavailable_capture_time`.

| Cohort | n | Median | p90 | p95 | Max |
|---|---|---|---|---|---|
| v9 | 24 | 111,811ms (~111.8s) | 173,944ms (~173.9s) | 200,408ms (~200.4s) | 307,373ms (~307.4s) |
| v10 | 11 | 103,900ms (~103.9s) | 183,300ms (~183.3s) | -- | -- |
| v12 | 2 | -- (too small to characterize) | -- | -- | -- |
| v13 | 0 | -- | -- | -- | -- |
| v14 | 14 | 82,920.6ms (~82.9s) | 235,454.9ms (~235.5s) | 253,408.4ms (~253.4s) | 261,211.4ms (~261.2s) |

Medians converge reasonably across the three usable-sized cohorts (v9,
v10, v14: ~83-112s), all consistent with the accepted root cause -- a
tight, deliberate tail latency from the Visit-Continuity/episode-boundary
quiet-period design, present regardless of encounter length: v9's own
additive decomposition measured this tail directly at median 54,656ms
(~54.7s, range 47.8-116.8s) across its 24 samples, and v10 independently
measured essentially the same thing (median tail latency 57.9s, "matching
v9's own tightly-clustered ~48-60s tail-latency finding for 10 of 11
Visits"); v14's own n=14 sample richly corroborates the same mechanism
without restating the decomposition separately. Tails of the full T0->T5
distribution (p90/max) vary more across sessions: v9's max (307.4s)
exceeds v14's (261.2s) by ~46s, and v14's own p90 (235.5s) materially
exceeds v9's (173.9s) -- a real spread across only three usable samples,
not yet a converged tail distribution, even though the underlying
*tail-latency component* specifically is itself tightly and repeatedly
confirmed. The full-distribution spread reflects variation in
*encounter-span* length and count, which the tail-latency component does
not.

**Product-doctrine framing, applied deliberately.** MockingBird's own
governing priority explicitly separates capture/correctness from
optional/enrichment latency, and product-doctrine frames this as a
discovery loop, not a live-surveillance guarantee: a user checking Today
or Bird Log minutes after an encounter is the expected usage pattern, not
a real-time feed. A hard tail-latency SLA is not something the product
claims or needs to claim.

**Determination: median is READY FOR RELEASE BUDGET; p90/maximum remain
MORE EVIDENCE REQUIRED, non-blocking.**

**Proposed budget: median capture-to-visible latency ≤ 180 seconds**, with
substantial margin above the highest qualifying median observed (~111.8s,
v9) -- deliberately not tightened toward v14's own best (lower) result.
No p90 or maximum budget is proposed at this time; three genuinely-sized
qualifying samples is not enough to set a tail-latency number without
inventing false precision, and doctrine does not require one for release.

## Monitoring evidence

Convergent and strong across essentially every cohort that reported it:
v4 99.78%, v5 ~99.99%, v6 ~99.4%, v7 99.989%, v9 97.95%, v10 99.99%, v11
97.5% (combined across two segments separated by a disclosed, user-
resolved ~71-minute CSI-cable hardware fault), v13 99.99% (tightest to
date before v14), v14 99.73% (max gap 5.80s, zero gaps >10s).

Two cohorts (v9 97.95%, v11 97.5%) sit below a naive 99% floor. Both have
an honest, disclosed, non-recurring explanation: v9's figure reflects the
independent recorder's own ~4.2-minute post-start arming lag inside a
~97-minute session (a measurement-tooling characteristic at session start,
not an ongoing capture gap); v11's figure reflects a real, external,
physically-resolved Camera Node hardware fault (already governed
separately under Gate D/E's field-recovery ladder, not a coverage-budget
violation in the steady-state sense this dimension is meant to capture).

**Determination: READY FOR RELEASE BUDGET**, reaffirming "READY FOR
BUDGET since v12" status.

**Proposed budget: minimum monitoring coverage ≥ 97%** in the steady
state, stated as a round number with real margin below every observed
value including the two disclosed exceptions -- rather than the tighter
~99% figure that would, taken literally, retroactively fail two already-
accepted, well-explained real cohorts. A future Camera Node hardware
fault remains separately governed by Gate D/E's field-recovery ladder,
not by this coverage budget.

## Gate B interaction

Gate A admission correctness and Gate B species-confidence correctness are
kept separate here, per this milestone's own explicit instruction.

**False Visits abstain honestly in the current-stack era.** v12: zero Gate
B recurrence. v14: the one confirmed false Visit received no species
claim at all -- zero Gate B recurrence. Both of the two cleanest,
current-configuration cohorts show clean abstention.

**One already-known, already-disclosed, rare residual remains, unaffected
by this reconciliation.** v9 (pre-fix era) recorded one Gate B recurrence:
a false Visit received a wrong confident species label, root-caused
precisely to the Background/Empty-Evidence fix's own already-disclosed
detector-sourced-evidence exclusion boundary, "not a regression." This is
the same standing, named limitation roadmap.md's own Gate B section
already tracks (a detector-sourced-but-still-wrong background crop can
still clear eligibility because the fix's own signal cannot distinguish a
genuinely contemporaneous detector hit on real background from one on a
real animal). It has not recurred in either of the two cleanest,
current-stack cohorts examined since (v12, v14). This reconciliation does
not attempt to close it -- it is Gate B's own standing item, release-
significant but separately tracked, not a new Gate A finding and not
merged into any Gate A budget above.

## Multi-subject / crowded-scene assessment

**2-subject handling is proven.** Genuine, independently-visually-confirmed
simultaneous two-bird moments have been correctly admitted as
independent, evidence-backed sibling Visits sharing one Event on at least
one occasion (v7); direct visual confirmation of 2 simultaneous birds
without full sibling-mechanism tracing exists in additional cohorts (v9,
v14). The concurrent-sibling Event-reuse mechanism itself is architecture
that predates this evidence body and is not reopened here.

**3+-simultaneous-subject activity has never been naturally observed**
across at least eight real field cohorts (v7 through v14) that explicitly
sought, rather than manufactured, exactly this condition. Per this
milestone's own instruction not to keep an item as a blocker "merely
because it has been historically listed if current release evidence no
longer justifies blocker status": eight consecutive real cohorts failing
to produce a 3+-subject moment, despite deliberately seeking one each
time, is itself evidence that this is a genuinely infrequent real-world
occurrence for backyard/feeder-scale wildlife activity at this reference
site -- not that the evidence-gathering has been inadequate.

**Determination: useful but non-blocking field-maturity evidence, not
required to pass Gate A.** The genuinely proven 2-subject mechanism
already satisfies the "hard release requirement" language in roadmap.md's
own "Multi-subject Visit correctness" section (ordinary feeder scenes with
multiple simultaneous birds must not collapse to zero/one/duplicate
Visits -- proven not to). A 3+-subject/NMS stress case remains a real,
disclosed, bounded unknown (does NMS suppress a third close bird? -- v7
disclosed exactly this concern once, never independently reproduced or
refuted since), appropriately classified as an after-release/evidence-
driven item: it should be captured opportunistically whenever a future
field session naturally observes it, not manufactured or demanded as a
precondition for the one public launch.

## Proposed release budgets

| Dimension | Status | Qualifying cohorts | Observed range | Proposed budget | Margin | Rationale |
|---|---|---|---|---|---|---|
| A. Recall (excluding disclosed ambiguous-boundary limitation) | READY | v12, v14 | 91.7%-93.3% | ≥ 85% | ~6.7pp below worst qualifying | Two independently-varied, current-stack, code-decomposed cohorts converge tightly once the separately-disclosed mechanism is isolated |
| A'. Ambiguous-boundary sustained/crowded recall limitation | ACCEPTED LIMITATION (see below), not a numeric budget | v12, v14; root-caused by two adversarial investigations | v14 worst case: 5/17 of a session's real encounters | N/A -- disclosed, not budgeted | N/A | Safe failure mode (omission, never fabrication); no safe fix found after two investigations; disclosure required |
| B. False-Visit rate | READY | v12, v14 | 5.6%-7.1% | ≤ 15% (ordinary scenes) | ~8pp above worst qualifying | Two convergent current-stack cohorts; wide margin for small n and for the disclosed person-confound exception |
| C. Fragmentation | READY | 2026-08-19 (reanalyzed), v5, v7 (reanalyzed), v8, v9, v12, v14 | 0% throughout | ≤ 5% | Effectively the entire margin between 0% and the budget | 7-8 independently-varied cohorts across every defect era converge |
| D. Duplicates | READY | v5, v7, v8, v9, v10, v11, v12, v14 | 0% throughout | ≤ 2% | Effectively the entire margin | ≥8 consecutive 0% cohorts, strongest dimension in the evidence body |
| E. Useful-evidence (combined) | READY | v7, v12, v14 | 92.9%-96.0% | ≥ 85% | ~8pp below worst qualifying | Combined metric matches actual user-facing gallery experience; primary-only not yet convergent, not budgeted |
| F. Evidence survival | READY | v7, v8, v9, v10, v11 (distinct-proposal basis); v12, v14 directionally consistent on a different (decision-event) basis | 6.7%-9.9% | ≤ 15% | ~5pp above worst qualifying | Healthy-evidence-path era only (v13 excluded); denominator harmonization flagged for the next cohort |
| G. True latency (median) | READY | v9, v10, v14 | ~82.9s-111.8s | ≤ 180s | ~68s above worst qualifying | Doctrine explicitly treats latency as non-surveillance-grade; median captures typical experience |
| G'. True latency (p90/max) | MORE EVIDENCE REQUIRED, non-blocking | v9, v14 (v10 partial, v12 too small) | p90 173.9s-235.5s; max 261.2s-307.4s | Not proposed | -- | Only 2-3 sized samples; real spread; not required by doctrine to gate release |
| H. Monitoring coverage | READY | v4 through v14, nearly every cohort | 97.5%-99.99%+ | ≥ 97% | Real margin below both disclosed exceptions | Two below-99% cohorts both honestly explained (tooling-lag, disclosed hardware fault); round, non-false-precision number |

## Cross-metric operating-point assessment

The current operating point -- ~93% ordinary-condition recall, ~94-96%
precision, 0% fragmentation, 0% duplicates, ~93-94% useful-evidence
(combined), ~90-96% evidence survival, a median latency of roughly 1.5-2
minutes with an intentionally long tail, and ≥97% monitoring coverage --
is not achieved by suppressing recall to buy precision, nor by flooding
false Visits to chase recall. The one significant recall cost (the
ambiguous-boundary sustained/crowded limitation) is concentrated in a
specific, well-understood mechanism rather than a diffuse tax on ordinary
operation, and its failure mode is abstention, never fabrication. The one
significant precision residual (person-in-frame single-class
misclassification) is likewise a named, bounded, disclosed exception
rather than a systemic weakness. Assessed as a whole, this is a coherent,
defensible operating point for a v1 release, not an artifact of
optimizing one dimension in isolation.

## Product-doctrine assessment

- **Nature-first, not surveillance-first:** the accepted median-latency
  framing and the ambiguous-boundary safe-abstention decision both
  explicitly apply this -- the product is not judged, and does not judge
  itself, by real-time-surveillance completeness standards.
- **Bird-first but wildlife-native:** unaffected by this reconciliation;
  no species/taxonomy claim is made or changed here.
- **Abstention-friendly:** directly reinforced -- the central release
  decision in this milestone (Option A on the ambiguous-boundary
  limitation) is itself an application of "an honest gap is better than a
  fabricated one" one architectural layer earlier than where that
  principle is usually applied (species identification).
- **Human-correctable:** unaffected; every Visit in this evidence body
  remains subject to ordinary review and correction.
- **Place-centered, local-first:** unaffected; no code change.
- **Not surveillance-first:** reaffirmed by the latency and recall
  framing above.

**Does the observed behavior still deliver Observe -> Discover ->
Understand -> Confirm -> Remember -> Improve credibly?** Yes. A user
returns to a mostly-complete, low-noise, low-duplicate, low-fragmentation
history with useful evidence on the great majority of Visits, discovers
it within a couple of minutes of an encounter in the typical case, and
can trust that what MockingBird did create is genuine, not a fabricated
merge or a corrupted continuation. The one disclosed limitation --
occasional complete loss of the single densest, most sustained multi-bird
episode in a session -- is a real cost to "Remember," honestly disclosed,
not hidden inside an aggregate number, and does not by itself undermine
the loop's credibility for ordinary and even most extraordinary use.

## Remaining Gate A dependency-by-dependency disposition

The canonical numbered list, as it stands after the last full restatement
(Field Acceptance Evidence Integrity & Storage Preflight Correctness v1,
narrowed since by All-Alternate Subject Evidence Recall Correctness v1,
v13, the two 2026-09-04/05 correctness fixes, v14, and Sustained/Crowded
v2). No item is dropped silently; every item below states its origin and
its current disposition explicitly.

1. **Never-strong single-generation confusor clearing
   `blocked_ambiguous_boundary` then reaching the quality gate repeatedly.**
   -- **NON-BLOCKING KNOWN LIMITATION.** The originally-motivating false-
   Visit regimes this item tracked (v10 36.4%, v11 44.4%) are each
   root-caused and fixed (Independent-Corroboration-Value fix,
   Strong-Confidence-Non-Target partial fix); the two cleanest cohorts
   measured since (v12 5.6%, v14 7.1%) show zero recurrence of this
   specific failure shape. A session deliberately targeting a never-strong
   recurring confusor has still never run, so formal closure is not
   claimed -- but two consecutive clean cohorts with no recurrence is
   itself informative, not merely absent evidence.
2. **A second person-confound-free false-Visit-rate cohort.** --
   **SUBSTANTIALLY ADVANCED, NOT FULLY CLOSED.** v12 and v14 together
   supply exactly two convergent, person-confound-free cohorts (5.6%,
   7.1%); this reconciliation accepts that as sufficient to set an initial,
   wide-margin budget (see "False-Visit precision evidence," above) rather
   than waiting for a third.
3. **Full-ledger-coverage fragmentation re-proof at full tool strength.**
   -- **MATERIALLY ADVANCED / EFFECTIVELY CLOSED.** v14 supplies a
   visually-confirmed 0/8 result, including direct resolution of the
   automated tool's own two remaining ambiguous units -- stronger evidence
   than v12's own weaker manual method, even though v14's own report
   notes its wording targeted a slightly different prior gap.
4. **A second independently-varied true-latency cohort.** -- **CLOSED**,
   by v14 (n=14, the richest sample of any cohort to date).
5. **A second live cohort producing genuinely crowded 3+-simultaneous-
   subject activity.** -- **AFTER RELEASE / EVIDENCE-DRIVEN, NON-
   BLOCKING.** See "Multi-subject / crowded-scene assessment," above.
6. **The bounded visual-review pass against v7's own two remaining
   genuinely-unreviewed ambiguous fragmentation units.** --
   **NON-BLOCKING KNOWN LIMITATION.** Superseded in practical value: v14's
   own fully-resolved, visually-confirmed 0/8 result is materially
   stronger evidence for the same underlying question than chasing v7's
   now nearly two-week-old partial residual would add.
7. **The ~13 untraced v7 `blocked_missing_evidence` records.** --
   **NON-BLOCKING KNOWN LIMITATION**, same reasoning as item 6 -- v14's
   fully-complete, 100%-reconciled ledger is a materially stronger,
   more current evidence source for this same question.
8. **Same-frame class-contradiction fix's field effect on person-
   associated false Visits.** -- **AFTER RELEASE / EVIDENCE-DRIVEN,
   NON-BLOCKING.** No genuine human presence has recurred in any cohort
   since the fix; this will be naturally exercised whenever it next
   occurs, not manufactured.
9. **Further strong-confidence scene-artifact recurrence.** --
   **AFTER RELEASE / EVIDENCE-DRIVEN, NON-BLOCKING.** Has not recurred in
   either of the two cleanest cohorts since (v12, v14) -- a negative
   result, consistent with, not contradicting, non-blocking status.
10. **No whole-frame human suppression of real birds with a person
    present.** -- **AFTER RELEASE / EVIDENCE-DRIVEN, NON-BLOCKING.**
    Untested by absence of the precondition (no person-plus-bird cohort
    since the fix), not by a negative result.
11. **Scene-confusor participation, including corroboration-rejected
    occurrence counts.** -- **CLOSED / NON-BLOCKING.** Directly, repeatedly
    measured (v11: 14 regions tracked, zero suspected, a real stationary
    bird's own Visit directly confirmed surviving the mechanism; v12: the
    first real-field category-D case, zero false-Visit cost; v14: zero
    scene-confusor participation, mechanism off by default for this
    Stream).
12. **A cohort with intact full-session raw-ledger coverage.** --
    **CLOSED**, by v14 (all three ledger artifacts 100% `COMPLETE`, the
    cleanest of any cohort to date).
13. **Whether `reject_no_identification_or_context`'s "vanish entirely,
    no Visit at all" behavior for brief-but-real encounters should be
    revisited.** -- **MATERIALLY CLOSED / NON-BLOCKING.** The one
    concretely identified, live-reachable mechanism behind it (a
    same-frame-only evidence set silently discarded) is fixed
    (All-Alternate Subject Evidence Recall Correctness v1); neither of
    the two original v12 misses that motivated this item actually traced
    to this code path once re-diagnosed with better tooling (both traced
    to ambiguous-boundary arbitration and detector-corroboration
    instead); v14, the cleanest post-fix cohort, records zero misses
    tracing to this code. The abstract question ("could this ever drop a
    real encounter in some other shape") is not proven impossible, but two
    consecutive clean cohorts show zero adverse evidence.
14. **Evidence-capture profile-staleness/silent-failure defect, plus
    proposal-outcome ledger-cadence completeness.** -- **CLOSED, both
    halves**, by the two 2026-09-04/05 correctness fixes and field-
    re-proved together, live, for the first time by v14.

**New item arising from this evidence body, not previously numbered:** the
ambiguous-boundary/geometry-compatibility-tolerance sustained/crowded
recall limitation. Disposed of above under "Ambiguous-boundary release
decision" as an **ACCEPTED PRODUCT LIMITATION**, not a numbered blocking
dependency -- consistent with how this reconciliation's own governing
brief frames the choice ("state the limitation plainly," not "add another
list item").

No item above is silently dropped: every one is accounted for with an
explicit disposition and reasoning.

## Gate A decision

**PASS.**

Every release-blocking Gate A dependency is either closed, bounded to a
non-blocking known limitation, reclassified as after-release/evidence-
driven with no current justification for blocker status, or -- for the
one dependency that cannot be closed by further engineering (the
ambiguous-boundary sustained/crowded recall limitation) -- resolved via an
explicit, evidence-grounded release-quality decision (Option A: accept,
disclose plainly) rather than left open indefinitely awaiting a fix two
independent investigations already found unsafe to build.

Explicit release budgets are accepted for seven of the eight primary
dimensions (recall, excluding the disclosed limitation; false-Visit rate;
fragmentation; duplicates; useful-evidence; evidence survival; monitoring
coverage), plus a partial budget (median only) for the eighth (true
latency), with its own tail statistics named as a genuine, non-blocking,
residual data gap rather than silently converted into a number the
evidence does not yet support.

**Lane R moves to CLOSED / PASSED for the Complete Field Acceptance
dependency this reconciliation was chartered to resolve.**

Residual limitations that remain, explicitly, not as blockers:

- The ambiguous-boundary sustained/crowded recall limitation itself
  (disclosed, required user-facing language recommended above).
- The person-in-frame single-class-misclassification precision residual
  (already known, already tracked, unaffected by this milestone).
- The detector-sourced-but-still-wrong background-crop Gate B residual
  (already known, already tracked, unaffected by this milestone).
- 3+-simultaneous-subject behavior, genuinely untested (after-release/
  evidence-driven).
- True-latency tail statistics (p90/maximum), genuinely under-sampled
  (non-blocking; doctrine does not require a tail SLA).
- The `blocked_missing_evidence` denominator-basis inconsistency between
  the v7-v10 (distinct-proposal) and v14 (decision-event) reporting
  conventions -- a measurement-hygiene item for the next cohort to
  harmonize, not a substantive gap.
- Items 6-10 above (v7 archaeology; person/artifact recurrence questions),
  each a genuine, disclosed, low-materiality gap, none blocking.

## Release-phase implications

Gate A passing does **not**, by itself, justify moving out of **CURRENT
PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT**. Inspecting the complete
release-critical and pre-release decision queue:

- **Lane G** (Camera / Source Experience): CLOSED -- RELEASE-CRITICAL.
- **Lane L** (Appliance / Update / Recovery): MATERIALLY CLOSED --
  RELEASE-CRITICAL (two small, disclosed, non-blocking residuals).
- **Lane M** (Storage / Retention): CLOSED -- RELEASE-CRITICAL.
- **Lane N** (Privacy / Local Only): CLOSED -- RELEASE-CRITICAL.
- **Lane O** (Platform / Runtime Portability): CLOSED.
- **Lane P** (Release Engineering / Distribution): SUBSTANTIALLY CLOSED,
  **one item deliberately still open** -- the source-code `LICENSE`
  owner decision (see below).
- **Lane Q** (Whole-Product UI/Accessibility/Performance): CLOSED.
- **Lane K** (Ecosystem/Provider Integrations): DECISION CLOSED, deferred,
  not required for launch.
- **Lane R** (Complete Field Acceptance / Gate A): now PASSED by this
  reconciliation.
- **§2** (BirdNET commercial-adjacent legal posture): still genuinely
  **unresolved** -- see below.
- **Gate G** (External Pre-Release Acceptance): not started; no scoping
  work has been done.
- **Lane S** (Actual Final Release Hardening): explicitly LAST, and not
  yet begun.

Two genuine release-critical/pre-release decisions remain open
independent of Gate A: the codebase `LICENSE` (a business/legal decision,
not resolvable by engineering) and the BirdNET commercial-adjacent
distribution question (needs actual legal review, not further
engineering). Gate A passing does not resolve either. Per this
milestone's own explicit instruction not to change phase merely because
Gate A passes if another genuine release-critical capability remains
open: **the phase label does not change**, and External Pre-Release
Acceptance is **not** self-authorized by this reconciliation. The natural
next pre-release step is resolving the two named decisions above and
scoping Gate G -- neither is authorized to begin by this milestone.

## Source-code license decision status

Unchanged, carried accurately from the accepted record: MIT was
recommended by Release Licensing, Distribution & Third-Party Legal
Closure v1's own complete decision packet (with two alternatives named and
reasoned through), but the decision itself remains an explicit **owner**
decision, not resolvable by any bounded engineering milestone including
this one. No `LICENSE` file exists and none is created by this
reconciliation. This status is unaffected by Gate A passing.

## BirdNET legal status

Unchanged, carried accurately: BirdNET's model weights are CC BY-NC-SA 4.0
(NonCommercial); MockingBird's official packaging never redistributes
them, durably enforced by a build-time guard
(`verify_no_nc_licensed_acoustic_model_redistribution`); acoustic
capability is optional and release-ready on that basis. Whether an
individual user's own private, non-commercial use could ever become
implicated merely because the surrounding open-source project also
accepts donations or sells optional paid support remains genuinely
**unresolved** -- the existing record recommends legal review before any
commercial-adjacent distribution decision touches this feature and does
not resolve the question itself. This reconciliation does not manufacture
legal certainty engineering cannot provide: the posture (optional,
non-redistributed) sufficiently bounds launch risk for a purely local,
non-commercial personal/home release, but a genuine commercial-adjacent
distribution decision (paid support, a crowdfunded/paid appliance, a
hosted paid service) should not proceed without the recommended legal
review actually happening first. This is a disclosure, not a resolution.

## Residual risks / known limitations

Consolidated from the sections above, for a single reference list:

1. Ambiguous-boundary sustained/crowded recall limitation (accepted,
   disclosed, primary finding of this reconciliation).
2. Person-in-frame single-class-misclassification precision residual
   (already known).
3. Detector-sourced-but-still-wrong background-crop Gate B residual
   (already known).
4. 3+-simultaneous-subject behavior untested (after-release/evidence-
   driven).
5. True-latency tail statistics (p90/max) under-sampled (non-blocking).
6. `blocked_missing_evidence` denominator-basis inconsistency across
   cohorts (measurement hygiene, not a substantive gap).
7. v7's own two unreviewed ambiguous fragmentation units and ~13 untraced
   `blocked_missing_evidence` records (superseded in practical value by
   v14's own materially stronger, fully-traced evidence).
8. Source-code `LICENSE` owner decision outstanding (pre-release, not
   Gate A).
9. BirdNET commercial-adjacent legal posture genuinely unresolved
   pending legal review (pre-release, not Gate A).
10. Gate G (External Pre-Release Acceptance) not yet scoped or started.

## Decision

**A**
