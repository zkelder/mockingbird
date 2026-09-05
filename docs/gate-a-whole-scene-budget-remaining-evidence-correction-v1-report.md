# Gate A Whole-Scene Budget & Remaining-Evidence Correction v1

Classification: **A** (a rigorous, evidence-traceable correction that
identifies and fixes a specific, named methodological defect in a prior
reconciliation, re-derives every affected figure from primary sources,
performs two genuine new offline-evidence contributions, and reaches an
honest, evidence-grounded Gate A disposition; not a product-code milestone,
so classification tracks correctness and completeness of the correction
rather than a defect-fix bar).

This is a bounded RELEASE-CRITICAL Lane R evidence/governance correction.
It follows accepted Sustained / Crowded Ambiguous-Boundary Recall
Correctness v2 (`de566f1`) and directly supersedes the analytical
conclusions — but not the underlying factual record — of the **unaccepted**
Gate A Release-Budget & Evidence-Sufficiency Reconciliation v1
(`8c42f80`/`d17ef3e`), which ChatGPT explicitly rejected.

## Starting repository state vs accepted state

Verified directly before any correction began:

- **Physical git HEAD:** `d17ef3e` (`Reconcile release-execution-state.md:
  accept Gate A Release-Budget & Evidence-Sufficiency Reconciliation v1
  (classification A)`).
- **Accepted baseline (last milestone ChatGPT actually accepted):**
  `de566f1` (`Reconcile release-execution-state.md: accept Sustained /
  Crowded Ambiguous-Boundary Recall Correctness v2 (classification B)`).
- **Schema:** `v58`, unchanged by either the rejected work or this
  correction.
- **Exact files changed by the two unaccepted commits** (verified via
  `git show --stat`): `8c42f80` added exactly one new file,
  `docs/gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md`
  (981 insertions, no other file touched). `d17ef3e` changed exactly two
  files, `docs/release-execution-state.md` (108 lines) and `docs/roadmap.md`
  (128 lines), both additive/edit-in-place documentation changes. No
  production code, test, or schema file was touched by either commit.
- **Worktree safety:** `git status --porcelain` shows exactly the seven
  explicitly-preserved untracked files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) and nothing else. No active writer
  (`ps aux` shows no MockingBird/product process; no `.git/index.lock`).
  Not pushed (`main` is 344 commits ahead of `origin/main`, unrelated to
  this milestone).

Since the two unaccepted commits touch only the expected documentation
files, and the worktree contains no unrelated changes, this correction
proceeds as a **forward** delta on top of the physical repository state
(`d17ef3e`), per the governing brief's explicit instruction not to reset,
rebase, or rewrite those commits. They remain in history as the record of
what was proposed and rejected.

## Why the prior reconciliation was rejected

ChatGPT's rejection named six specific defects in
`gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md`
and its reconciliation commit. Each is addressed in this report:

1. **"≥85% end-to-end recall excluding the ambiguous-boundary
   sustained/crowded limitation" is not a valid end-to-end recall budget.**
   The rejected report computed `recall excluding ambiguous-boundary
   misses` (v12: 14/15=93.3%; v14: 11/12=91.7%) and then budgeted *that*
   number as "minimum end-to-end Visit recall," explicitly labeling the
   exclusion parenthetically rather than as a headline caveat. This
   converts a known, disclosed, unfixed failure mode into an invisible
   denominator adjustment — the opposite of "disclosed, not budgeted" the
   same document claims for the identical limitation one paragraph away.
   Corrected below: no failure-reason denominator exclusion is applied to
   the release recall figure anywhere in this report.
2. **V14's representative whole-scene result remains conservative
   recall = 11/17 = 64.7%**, and those misses stay in the denominator
   used for any release-recall claim, even though engineering cannot
   safely correct the mechanism producing them. This report treats 64.7%
   (and the broader 61.1%) as *the* v14 recall figures, full stop — not a
   "blended" or "literal" figure to be explained away.
3. **A disclosed, accepted product limitation may not be removed from the
   denominator used to claim whole-product recall.** The rejected report
   itself already understood this in the abstract (it separately states
   the ambiguous-boundary limitation "is disclosed... not silently
   absorbed into the blended recall figures") — but then did exactly that
   by budgeting the excluding-figure as the headline number. This report
   keeps the limitation's cost *inside* the recall figure and addresses
   its acceptability as a separate, explicit release-judgment question
   (see "Ambiguous-boundary product limitation," below).
4. **True latency is not fully closed merely by accepting a median budget
   while leaving p90/max unbounded.** The rejected report's own internal
   analysis (its "G'" row) correctly flagged p90/max as "MORE EVIDENCE
   REQUIRED, non-blocking" — but its "Proposed release budgets" table and
   its Gate A decision text then counted latency among the "explicit
   release budgets... accepted for seven of the eight primary dimensions,"
   folding the unresolved tail into a footnote rather than into the
   decision. Worse: its own tail table (`v9`/`v10`/`v14`) silently
   **omitted v10's own already-accepted, already-disclosed 742.3-second
   maximum** (`representative-daylight-gate-a-field-acceptance-v10-report.md`
   "True latency": "candidate-010's tail latency is 681.3s (~11.4
   minutes)... Full T0→T5... 742.3s"), reporting only v10's median/p90 and
   leaving max as `--`. Corrected below, with a materially wider tail range
   than the rejected report ever considered.
5. **Evidence-survival figures mixed proposal-basis and decision-event
   -basis denominators.** The rejected report acknowledged this
   explicitly but then still used the decision-event-basis figures
   (v12 4.6%, v14 4.2%) as "directionally consistent" support for a budget
   derived only from the five proposal-basis cohorts (v7-v11), rather than
   actually harmonizing them. This report performs the harmonization (see
   "Evidence-survival denominator harmonization," below) rather than
   flagging and setting aside the inconsistency again.
6. **Lane R / Gate A remains OPEN.** The rejected reconciliation commit
   moved Lane R to `CLOSED / PASSED` and roadmap.md's Gate A section to
   "Gate A **PASSED**." Both are corrected back, with the full history of
   what was wrongly claimed preserved (not deleted) alongside the
   correction — see "Roadmap / scheduler correction," implemented in this
   milestone's second commit.

Item 7 from the governing brief (identify the smallest exact remaining
requirement, not another 90-105-minute cohort) is addressed in "Smallest
sufficient remaining Gate A proof," below.

## Preserved valid analysis from the rejected work

Not everything in the rejected report is wrong, and discarding correct
analysis merely because it sits in an unaccepted document would be its own
kind of dishonesty. The following are independently re-verified against
primary sources in this correction and **retained**:

- **The complete Gate A evidence inventory** (the chronological table of
  every milestone from 2026-08-19 through Sustained/Crowded v2 and its
  effect on Gate A's evidence body) — re-verified against
  `release-execution-state.md` §3 and the individual cohort reports; no
  factual correction needed.
- **The three-era configuration-comparability framing** (pre-admission
  -mechanism era through v6; pre-precision-hardening era v7-v9;
  current-stack era v10 onward for precision, v14 onward for evidence
  -integrity) — correct and reused directly.
- **The false-Visit, fragmentation, duplicate, useful-evidence, and
  monitoring-coverage analyses and proposed budgets** — none of the six
  named rejection reasons implicates these four dimensions' own
  methodology or arithmetic. Re-verified independently against the
  underlying cohort reports in this correction (see their own sections,
  below) and found sound. Their proposed budgets are carried forward
  essentially unchanged, with §9's requested false-Visit stratification
  made more explicit.
- **The multi-subject/crowded-scene assessment** (2-subject handling
  proven; 3+-subject activity never naturally observed across 8 cohorts
  that sought it, treated as after-release/evidence-driven, non-blocking)
  — sound reasoning, retained.
- **The qualifying-cohort matrix's per-dimension verdicts** for every
  column *except* the recall/ambiguous-boundary treatment — retained,
  cross-checked directly against each named cohort's own report during
  this correction.
- **The product-doctrine assessment's framing** of the ambiguous-boundary
  mechanism as a safe (omission, never fabrication) failure mode, and the
  observation that this mirrors the abstention-over-fabrication principle
  product doctrine already applies to species uncertainty — this
  reasoning is correct and is retained for the *engineering* question ("is
  this mechanism safe, and is a further fix currently justified") while
  being kept sharply separate from the *release* question the rejected
  report answered wrongly.

What is **not** retained: the recall decomposition/exclusion arithmetic
and its resulting ≥85% budget; the claim that latency is ready for a
budget; the "directionally consistent, not pooled" treatment of
evidence-survival; the overall "Gate A PASS" / "Lane R CLOSED" conclusion.

## Correct whole-scene recall definition

Frozen, per the governing brief, as:

> end-to-end Visit recall = confirmed representative real encounter
> periods represented by ≥1 coherent Visit / all confirmed representative
> real encounter periods

No exclusion is made by internal failure reason. A miss caused by
`blocked_ambiguous_boundary`, `reject_insufficient_detector_corroboration`,
`blocked_missing_evidence`, a tracker failure, or any other product-stage
mechanism counts identically in the denominator. Internal cause is
retained for diagnosis (see "Ambiguous-boundary product limitation,"
below) but never removes a miss from the release-recall calculation.

## Qualifying recall evidence

Rebuilt from the original representative denominators in each cohort's own
report, classified per the brief's four categories:

| Cohort | Conservative recall | Broader recall | Denominator methodology | Classification | Why |
|---|---|---|---|---|---|
| 2026-08-19 (primary, `end-to-end-bird-encounter-recall-closure-v1`) | 15/22 = 68.2% | — | Full-session independent review (pre-dates today's tooling) | **NON-COMPARABLE** | Predates the admission-starvation fix, the fallback-chain fix, both precision fixes (Hard-Negative, Independent-Corroboration), RTT-bounded calibration, the evidence-capture-profile fix, and the ledger-completeness fix. Reported here as historical context only, never pooled. |
| v4 (2026-08-29) | 0/N (0 admissions) | — | N/A | **DEFECT-INVALIDATED** | Active admission-starvation P0; the session that discovered the defect, not a recall measurement. |
| v5 (2026-08-30) | No percentage (qualitative "no missed encounter found" only) | — | Targeted, non-exhaustive review, own report's explicit caveat | **NON-COMPARABLE** | Post-starvation-fix but pre-fallback-fix, pre-both-precision-fixes, pre-RTT; own report explicitly declines to state a recall percentage. |
| v6 (2026-08-31 AM) | 0/N (0 admissions) | — | N/A | **DEFECT-INVALIDATED** | Active evidence-cache-exhaustion defect. |
| v7 (2026-08-31 PM) | 3/3 = 100% (exhaustive, but only 2 targeted windows, ~8.6% of session span) | — | Two hand-picked "hardest-moment" windows, not full-session | **PARTIALLY QUALIFYING** | Own report: "Do not read a single recall percentage across cohorts as directly comparable"; pre-both-precision-fixes; small n, favorable-by-selection windows. |
| v8 (2026-09-01) | Not independently re-derived | — | N/A | **NON-COMPARABLE** | Pre-both-precision-fixes era; 27 admissions but false-Visit rate 22.2% makes admission-based recall inference unreliable; no independent whole-scene review performed. |
| v9 (2026-09-01) | Two independent-denominator windows, not a whole-session percentage | — | Two prospective windows (dense + sparse), not full-session | **PARTIALLY QUALIFYING** | Pre-both-precision-fixes era; genuinely useful evidence (no encounter missed in either window) but explicitly not a comparable percentage. |
| v10 (2026-09-02) | 4/5 = 80% | — | Two targeted windows + complete review of every ledger proposal, not full-session contact-sheet sweep | **PARTIALLY QUALIFYING** | Pre-Independent-Corroboration-Value-fix era (the fix this exact miss's mechanism motivated); own report: "should be read with the same conservative caveat v9's own report used." |
| v11 (2026-09-02) | 7/7 = 100% | 7/10 = 70% | Full raw-ledger review across both segments, deliberately conservative miss-crediting | **PARTIALLY QUALIFYING** | Pre-Strong-Confidence-Non-Target-fix era; genuine person-in-frame confound present (irrelevant to recall itself, but marks this cohort as pre-current-stack); own report explicitly declines to treat the 70% figure as more than "plausible." |
| v12 (2026-09-03) | **14/16 = 87.5%** | **14/24 = 58.3%** | Full-session denominator; snapshot-tool defect left the raw ledger only 39-54% complete for the *evidence-survival* metric, but Visit-level detail (the recall-relevant data) was 100% complete | **QUALIFYING** | Current admission-precision stack (post-Independent-Corroboration-Value fix); independently re-derived, full-session denominator. Known limitation: fragmentation used a weaker, tool-data-starved manual method (does not affect recall). |
| v13 (2026-09-04) | 0/N (0 admissions) | — | N/A | **DEFECT-INVALIDATED** | Active evidence-capture-profile defect; every proposal died before any precision/recall mechanism could engage. |
| v14 (2026-09-05) | **11/17 = 64.7%** | **11/18 = 61.1%** | Full-session denominator built from the independent recorder first, then cross-checked against every ledger-derived candidate window (87 distinct frames across 27 windows); 100%-complete ledger (all three artifacts) | **QUALIFYING** | Current admission-precision **and** evidence-integrity stack (post both 2026-09-04/05 correctness fixes) — the single most trustworthy denominator in the entire evidence body. |

**Only v12 and v14 qualify** as directly comparable, current-stack,
independently-re-derived, full-session recall measurements. They diverge
sharply: 87.5% vs. 64.7% conservative (22.8 points), 58.3% vs. 61.1%
broader (roughly converged, by coincidence of v12's own broader
denominator being unusually large relative to its conservative one).

**Miss-by-miss breakdown, no exclusion applied:**

- v12 (2 misses of 16 conservative): 1 traces to `blocked_ambiguous_boundary`
  (the chartered "~37:12" case, root-caused by Ambiguous-Boundary
  Real-Subject Recall Correctness v1); 1 traces to
  `reject_insufficient_detector_corroboration` on a genuinely marginal
  (3-detection, never-strong) real encounter — a correct-by-design
  rejection of an already-accepted, already-budgeted precision mechanism,
  not a defect.
- v14 (6 misses of 17 conservative): 5 trace to `blocked_ambiguous_boundary`
  (one an 11-overlapping-proposal, ~310-continuous-second cluster with
  confirmed simultaneous 2-bird moments); 1 traces to
  `reject_insufficient_detector_corroboration` on a genuinely marginal,
  off-feeder ground-foraging bird — the same already-accepted mechanism as
  v12's second miss.

**Do not manufacture convergence.** These two numbers are not the same
measurement with sampling noise; they are the same architecture measured
under materially different real-world activity density. v14's own session
produced a much denser, more sustained multi-subject encounter pattern
(the ~310-second cluster) than v12's did. The divergence is itself the
finding, not a defect in either measurement.

## Ambiguous-boundary product limitation

The accepted engineering conclusion is unchanged and is **not** relitigated
here: two independent, adversarial investigations (Ambiguous-Boundary
Real-Subject Recall Correctness v1, on the chartered v12 case; Sustained /
Crowded Ambiguous-Boundary Recall Correctness v2, on all five v14 misses
plus the 310-second cluster, at materially greater depth) both concluded
the identical root cause — `classify_boundary`'s geometry-compatibility
tolerance forms an ambiguous link between temporally-close proposals, and
`engine_runtime._live_chain_for_component`'s "any admitted component
member vetoes the whole component unconditionally" policy then permanently
blocks a later, sometimes materially stronger, proposal — with **no safe
correction available using any currently-trustworthy signal.** One
genuinely new structural fact was found and disclosed, not fixed: the
codebase bounds how long a still-growing component may *defer* a decision
(`maximum_episode_duration_ms` / `_MAXIMUM_COMPONENT_PENDING_MS`, 20
minutes) but places no symmetric bound on how long an already-resolved
member's *veto reach* may persist — reusing that bound for this different
purpose is a candidate fix a future milestone could pursue if a real
session ever shows the asymmetry actually firing (none has yet).

The failure mode is safe: across every cohort in this evidence body, zero
ambiguous-boundary losses have ever produced a false merge, a fabricated
continuation, or a corrupted Reviewed-truth record. The realized cost is
always omission — no Visit at all for the affected proposal.

This report keeps two questions explicitly separate, per the governing
brief:

**A. Is another engineering fix currently justified?** **No.** Both
investigations searched for a safe correction using every
currently-trustworthy fact available (geometry lineage, crop signals,
evidence diversity, track structure) and found none. A third investigation
on the same evidence basis is not indicated; sustained-crowded v2's own
"Residual risk" section is explicit that a future attempt would need "a
future milestone with concrete evidence of this specific asymmetry
actually firing in a real session" — a new fact, not more analysis of the
same fact.

**B. Is the product-level recall impact acceptable for launch?** This is a
release decision, and it is **not** answered by deleting the misses from
the denominator. It is answered using whole-scene recall as computed
above: a real MockingBird session under sustained/crowded activity can
show conservative recall as low as 64.7%, concentrated specifically in
that activity regime (5 of v14's 6 misses; 1 of v12's 2). See "Gate A
decision," below, for how this report resolves question B.

## False-Visit evidence

Re-evaluated without excluding person-associated activity, since
product-doctrine scopes person detection in generally (people are real
non-target activity a wildlife camera will see; MockingBird is not
scoped to ignore them, and no product decision excludes them from the
false-Visit accounting).

| Cohort | Rate | Regime |
|---|---|---|
| 2026-08-19 | 2/21 = 9.5% | Pre-fix historical |
| v7 | 1/25 = 4.0% | Pre-both-precision-fixes |
| v8 | 6/27 = 22.2% | Pre-both-precision-fixes |
| v9 | 5/25 = 20.0% | Pre-both-precision-fixes; 1 Gate B recurrence |
| v10 | 4/11 = 36.4% | Post-Hard-Negative-fix, pre-Independent-Corroboration-fix (the session that proved this exact residual) |
| v11 | 8/18 = 44.4% | Post-Independent-Corroboration-fix, pre-Strong-Confidence-Non-Target-fix; **all 8 confirmed-false Visits trace to a real person-in-frame confound (7) or an already-tracked scene artifact (1) — zero trace to the corroboration/scene-confusor axis** |
| **v12** | **1/18 = 5.6%** | **Current stack, person-confound-free** |
| **v14** | **1/14 = 7.1%** | **Current stack, person-confound-free** ("other background/artifact," no species claim) |

**Two regimes must be stated separately, not pooled into one number:**

- **Ordinary, non-person background/artifact false-Visit rate (current
  stack): READY FOR RELEASE BUDGET.** v12 and v14 converge tightly (5.6%,
  7.1%; pooled 6.25%) — two independent, current-stack, person-confound-
  free cohorts on the same physical scene. **Proposed budget: ≤15%**,
  ~8pp above the worse qualifying cohort.
- **Person-associated false-Visit rate under the current stack: genuinely
  unmeasured — n=0.** v11's 44.4% (7/8 person-caused) is the only
  concrete evidence that person-in-frame activity can drive false-Visit
  rate materially above the ordinary-scene band, but v11 predates the
  Strong-Confidence-Non-Target partial fix that specifically targeted this
  subclass. No cohort with both (a) the current admission stack and (b)
  a real person-in-frame confound has run since. Forcing one pooled number
  across these two regimes would either be too strict for ordinary use or
  too permissive for a person-present session — per the governing brief's
  own instruction, **no single overall false-Visit budget is adopted**;
  the ordinary-scene budget above stands on its own, and the
  person-associated regime remains an explicit, disclosed,
  **non-blocking known limitation** (already tracked under Gate B as the
  single-class-misclassification residual) rather than folded into either
  number.

Gate B interaction, unaffected by this correction: both v12 and v14 show
zero Gate B recurrence (the one confirmed false Visit in each received no
species claim, or none at all). The one already-known, pre-fix-era Gate B
recurrence (v9) remains a standing, separately-tracked residual, not
reopened here.

## Fragmentation evidence

Using the accepted, corrected reviewer-disposition methodology
(`gate-a-measurement-closure-fragmentation-latency-v1-report.md`'s
`fragmentation_accounting.py`, which never promotes an unresolved
`cluster_encounters` signal to "fragmented" without a positive structural
or reviewer signal) — independently re-verified against that report's own
"Existing-cohort reanalysis" table and each named cohort's own report:

- 2026-08-19 (reanalyzed): 7 of 8 denominator units resolved, 0%
  fragmented, 1 reviewer-confirmed genuinely ambiguous.
- v5: 0% (own full manual review).
- v7 (reanalyzed): 7 of 10 denominator units resolved, 0% fragmented, 3
  genuinely ambiguous (not promoted absent a positive signal).
- v8: 16/16 = 0%, first fully-resolved cohort.
- v9: 14/14 = 0%.
- v12: 0/14 = 0%, but by its own weaker manual method (tool data-starved
  by the same evidence-preservation gap that affected its
  evidence-survival denominator) — a real, disclosed measurement-strength
  caveat, not a contrary result.
- v14: 0/8 = 0%, visually confirmed against the independent recorder,
  including direct resolution of the automated tool's own two remaining
  "ambiguous" units.

Seven independently-varied cohorts across every configuration era converge
on 0% confirmed fragmentation under one consistent methodology — none of
this dimension's evidence is implicated by the six rejection findings.

**Determination: READY FOR RELEASE BUDGET. Proposed budget: maximum
confirmed fragmentation rate ≤5%**, unchanged from the rejected report
(this figure was not one of the corrected findings). Persistence-duration
rollover and duplicate Visits remain a separate concept (see "Duplicate
evidence," below), not folded into this figure.

## Duplicate evidence

0% across every cohort that has measured it: v5, v7, v8 (implicit in its
16/16 fragmentation result), v9 (0/25), v10 (0%), v11 (0%), v12 (0%,
explicitly its own "9th consecutive cohort"), v14 (0/14). At least eight
independently-varied cohorts, spanning every configuration era, have each
measured exactly 0% confirmed duplicates under the accepted
shared-tracker-evidence test.

**Determination: READY FOR RELEASE BUDGET. Proposed budget: maximum
confirmed duplicate-Visit rate ≤2%**, unchanged from the rejected report
— essentially the entire evidence body sits at the budget's margin.

## Useful-evidence denominator

Frozen as the **combined** metric (primary + supporting/alternate frames),
matching the rejected report's own choice, which this correction verifies
is sound and not implicated by the six rejection findings.

**Justification, made explicit per the governing brief's instruction that
a chosen combined metric must be something a user can actually reach.**
`product-doctrine.md`'s own "Evidence" object definition is plural
("MediaAssets... attached to a Visit"), and MockingBird's Visit Evidence
Gallery (see `[[working-app-v1-visit-evidence-gallery]]`) presents the full
set of a Visit's evidence images to a reviewing user, not only one
system-designated "primary" frame. A Visit whose primary frame is weakly
framed but whose gallery contains a clearly-visible alternate frame is
genuinely useful to a user reviewing that Visit — the combined figure
measures exactly this, while the primary-only figure measures a
ranking-quality question (did the system's own heuristic pick the single
best frame), a real but different concern this dimension is not meant to
answer.

Figures (combined): v7 96.0% (pre-fix era), v12 94.4%, v14 92.9%. Two
current-stack cohorts converge tightly (92.9%, 94.4%). Primary-only figures
remain more volatile (v9 76.0%, v12 77.8%, v14 78.6%, v7 96.0%) and are
correctly **not** budgeted, consistent with the rejected report.

**Determination: READY FOR RELEASE BUDGET. Proposed budget: minimum
useful-evidence rate (primary + supporting) ≥85%**, unchanged from the
rejected report — real margin below both current-stack cohorts' own
figures.

## Evidence-survival denominator harmonization

This is a primary corrective task, and — unlike the rejected report, which
flagged the inconsistency and then used the mismatched figures anyway as
"directionally consistent" support — this correction actually performs the
harmonization the brief calls for, using the authoritative repository
semantics (`proposal_outcomes` is an append-only decision-*event* log;
`blocked_continuation_pending` is the only non-terminal/retryable outcome;
every distinct proposal has at most one terminal decision).

**Denominator inventory:**

- **Distinct-proposal basis** (v7-v11's own convention): v7 9.4% (18/192),
  v8 9.9%, v9 8.9% (12/135), v10 6.7% (6/90), v11 9.29% (29/312). Five
  independently-varied sessions, tight 6.7%-9.9% band.
- **Decision-event basis** (v12, v14's own as-published figures): v12 4.6%
  (15/325), v14 4.2% (8/191). A structurally different, larger denominator
  — a retried proposal contributes multiple events before its terminal
  outcome, so an event-basis percentage reads directionally lower for the
  same underlying loss count, not because survival actually improved.

**Offline harmonization performed** (no production code changed; the
existing, unmodified `capture_to_visible_latency.py`/
`run_gate_a_measurement_accounting.py` machinery was not needed for this
part — this was a direct arithmetic decomposition of the raw, preserved
ledger, verified by script against
`data/field-acceptance/2026-09-05-gate-a-v14-corrected-evidence-path-reproof/merged-ledger/counterfactual-merged.json`):

v14's own report already discloses the full decision-event-outcome
breakdown (`blocked_continuation_pending` 110, `blocked_ambiguous_boundary`
55, `blocked_missing_evidence` 8, `reject_insufficient_detector_corroboration`
4, `created` 14 = 191 total, across 90 distinct proposals). Grouping the raw
ledger's 191 `proposal_outcomes` records by `proposal_id` and taking each
proposal's chronologically last outcome as its terminal state (independently
confirmed: **zero** of the 90 distinct proposals has more than one
non-`blocked_continuation_pending` outcome, validating that
`blocked_continuation_pending` is indeed the only retryable/non-terminal
state) yields exactly:

| terminal outcome | distinct proposals |
|---|---|
| `blocked_ambiguous_boundary` | 55 |
| `created` | 14 |
| `blocked_missing_evidence` | **8** |
| `reject_insufficient_detector_corroboration` | 4 |
| `blocked_continuation_pending` (still pending at session stop) | 9 |
| **total** | **90** |

**v14 harmonized, distinct-proposal-basis evidence-survival: 8/90 = 8.89%**
— falling almost exactly in the middle of the v7-v11 band (6.7%-9.9%).
This is a genuinely new, apples-to-apples number, not a "directionally
consistent" hand-wave: **six** independently-varied cohorts now converge
on one common basis at 6.7%-9.9%.

**v12 cannot be safely harmonized**, and this correction does not attempt
to force it. Direct inspection of v12's own preserved raw archive
(`data/field-acceptance/2026-09-03-gate-a-v12-precision-recall-budget-convergence/merged-ledger/live_post_stop_counterfactual.json`)
confirms the recovered window covers only proposals starting at session
offset ≥ 2,192,478ms (~36.5 of 97 minutes) — the first ~37 minutes have
**zero** recoverable detail, a permanent loss v12's own report already
disclosed. The recovered tail alone contains 63 distinct proposals with 10
terminal `blocked_missing_evidence` outcomes (15.87% on that
window-restricted sub-population) — a real number, but not a valid
full-session estimate: v12's own report attributes this window's
unusually high activity to "the flag confusor firing dozens of short
episodes," so extrapolating a partial-window rate to the full session
would not be honest. **v12 is correctly excluded from the harmonized
distinct-proposal-basis budget population**, for a different, more
precise reason than the rejected report gave (not merely "different
basis" — genuinely unrecoverable).

**Determination: READY FOR RELEASE BUDGET, more strongly evidenced than
the rejected report's own claim.** Six harmonized cohorts (v7, v8, v9,
v10, v11, v14), one common distinct-proposal basis, 6.7%-9.9% band.
**Proposed budget: maximum evidence-loss (`blocked_missing_evidence`, as a
share of distinct proposals) ≤15%**, unchanged numerically from the
rejected report but now resting on genuinely harmonized, not merely
"directionally consistent," evidence. v12's own decision-event-basis
figure (4.6%) is noted as informative but not pooled, and is not
recoverable onto the common basis; a future cohort should not repeat v12's
own ~37-46-minute ledger-preservation gap (already fixed by Field
Acceptance Evidence Integrity & Storage Preflight Correctness v1 and
proven closed by v14's own 100%-complete ledger).

## Latency distribution / tail evidence

Only RTT-bounded (two-sided-interval), calibration-mechanism-valid samples
qualify — every cohort predating Camera Node ↔ Host RTT-Bounded Clock
Calibration v1 (2026-08-19, v6, v7, v8) is excluded by design.

**Qualifying full T0→T5 distributions, re-verified directly against each
cohort's own report (and, for v11, newly recovered — see below):**

| Cohort | n | Median | p90 | p95 | Max |
|---|---|---|---|---|---|
| v9 | 24 | 111,811ms (111.8s) | 173,944ms (173.9s) | 200,408ms (200.4s) | 307,373ms (307.4s) |
| v10 | 11 | 103,900ms (103.9s) | 183,300ms (183.3s) | ~471,900ms (~471.9s, computed by this correction from v10's own published per-Visit table; not separately stated in v10's report) | **742,300ms (742.3s / 12.37min)** |
| v12 | 2 | — (too small) | — | — | — |
| v13 | 0 | — | — | — | — |
| v14 | 14 | 82,920.6ms (82.9s) | 235,454.9ms (235.5s) | 253,408.4ms (253.4s) | 261,211.4ms (261.2s) |
| **v11 (newly recovered, this correction)** | **23** | **115,699ms (115.7s)** | **318,469ms (318.5s)** | **524,369ms (524.4s)** | **865,199ms (865.2s / 14.42min)** |

**The rejected report's own tail table omitted v10's own already-disclosed
742.3-second maximum**, reporting `--` for both v10's p95 and max. That
figure was not missing evidence — it was published, with full root-cause
analysis, in v10's own accepted report ("candidate-010's tail latency is
681.3s... Full T0→T5... 742.3s... Root cause, traced not assumed: [a
subsequent, temporally-close encounter at the same location] extending one
Visit's own decision horizon while nearby, potentially-related activity is
still being arbitrated, not a new defect"). Any tail-evidence review that
does not surface this number is incomplete on its own terms.

**New evidence recovered by this correction, via offline reanalysis of a
preserved cohort (governing brief §17, option A) — no field session, no
production code change:** v11's own report declined to compute true
latency ("bounded archaeology... preserved in the merged ledger for a
future pass"). Its raw, merged-ledger archive
(`data/field-acceptance/2026-09-02-gate-a-v11-independent-corroboration-scene-confusor-reproof/merged-ledger/merged_segment{1,2}.json`)
is still present and contains 23 admitted proposals with real RTT
calibration coverage (160 and 315 batches respectively). Running it through
the existing, unmodified `run_gate_a_measurement_accounting.py` initially
produced implausible figures (`clock_calibration_state: not_required` for
every sample, i.e. **uncorrected** raw timestamps) because v11's own ad hoc
merge script (predating today's standardized `field_acceptance_ledger_snapshot.py`)
dropped the `clock_calibration_required` flag when combining periodic
snapshots — independently confirmed by inspecting v11's raw, unmerged
per-checkpoint snapshots, which correctly carry `clock_calibration_required:
true`. Restoring that one verified boolean into a **scratch working copy**
of the merged files (the committed archive under `data/field-acceptance/`
was never modified) and re-running the same unmodified tool produces a
valid, fully RTT-normalized (`clock_calibration_state: "normalized"` for
all 23 samples) distribution: **n=23, median 115.7s, p90 318.5s, p95
524.4s, max 865.2s.** This is disclosed as new analysis performed by this
correction, not as part of v11's own original accepted findings, and has
not been independently visually re-verified against footage the way v11's
own live findings were.

**What this means for the tail:** across four sized, RTT-normalized
samples, medians converge reasonably (82.9s-115.7s), but **maxima span a
more-than-3x range (261.2s to 865.2s) with no visible convergence.**
865.2s (v11, this correction) and 742.3s (v10, already accepted) are both
individually root-caused to the same mechanism v9 first named — the
Visit-Continuity/episode-boundary quiet-period design extending a
proposal's own decision horizon while a nearby, potentially-related
encounter is still being arbitrated — and both sit at 60-72% of the
architecture's own documented ceiling for a *different but related*
mechanism, `maximum_episode_duration_ms` (1,200,000ms / 20 minutes,
"Bounded component decision horizon," per
`sustained-crowded-ambiguous-boundary-recall-correctness-v2-report.md`).
This is informative context (no currently-known mechanism can push a
single proposal's resolution past that 20-minute ceiling), but it is not
itself a statistically-supported p90/max figure — it describes a plausible
worst-case ceiling, not an observed frequency.

**Determination: median is well-evidenced; the dimension as a whole is
not.** Per the governing brief's explicit instruction ("do not call
latency CLOSED based only on median"), **"G. true latency" is classified
as one metric, MORE EVIDENCE REQUIRED**, not split into a closed median
row and a footnoted tail row the way the rejected report did. The missing
fact is precise: a converged, multi-cohort (ideally 5+ sized samples)
characterization of the p90/max tail large enough to distinguish "742-865s
outliers are a rare, architecturally-bounded edge case" from "a
non-trivial fraction of real sessions will show a multi-minute outlier."
No p90 or maximum budget is proposed. The median observation (roughly
83-116s across four cohorts) remains a genuine, useful descriptive fact,
reportable as such, but not a substitute for a decision on the dimension
as a whole.

## Monitoring evidence

Unaffected by the six rejection findings; re-verified and unchanged.
Convergent and strong across essentially every cohort that reported it: v4
99.78%, v5 ~99.99%, v6 ~99.4%, v7 99.989%, v9 97.95%, v10 99.99%, v11
97.5% (a disclosed, physically-resolved Camera Node hardware fault), v13
99.99%, v14 99.73%. The two cohorts below a naive 99% floor (v9, v11) are
each honestly explained by a non-recurring cause, not an ongoing coverage
defect.

**Determination: READY FOR RELEASE BUDGET. Proposed budget: minimum
monitoring coverage ≥97%** in the steady state, unchanged from the
rejected report.

## Corrected eight-metric table

| # | Metric | Disposition | Budget / missing fact |
|---|---|---|---|
| A | Recall | **RELEASE DECISION REQUIRED** | Only 2 qualifying cohorts, both current-stack, diverge 64.7%-87.5% (conservative) for a fully root-caused, safe (omission-only), currently-unfixable-with-existing-signals mechanism. No further engineering investigation is indicated (two independent adversarial investigations already exhausted currently-trustworthy signals). Whether a whole-scene recall floor that can fall to ~65% during unusually busy activity is acceptable for a v1 launch is an explicit product-risk-tolerance decision, not an evidence gap engineering can close. |
| B | False-Visit rate | **READY FOR RELEASE BUDGET** (ordinary scenes); person-associated regime **NON-BLOCKING KNOWN LIMITATION** | ≤15% under ordinary (non-person) scene conditions, from v12 (5.6%) + v14 (7.1%). Person-in-frame false-Visit rate under the current stack is unmeasured (n=0 post-fix cohorts) — disclosed, not budgeted, not blocking (already a tracked Gate B residual). |
| C | Fragmentation | **READY FOR RELEASE BUDGET** | ≤5%. Seven independently-varied cohorts, all eras, converge on 0% confirmed. |
| D | Duplicates | **READY FOR RELEASE BUDGET** | ≤2%. Eight+ cohorts, all eras, converge on 0% confirmed. |
| E | Useful evidence (combined) | **READY FOR RELEASE BUDGET** | ≥85%. Two current-stack cohorts (92.9%, 94.4%) converge; primary-only correctly not budgeted (76.0%-96.0%, unconverged). |
| F | Evidence survival | **READY FOR RELEASE BUDGET** | ≤15% (`blocked_missing_evidence`, distinct-proposal basis). Six cohorts (v7, v8, v9, v10, v11, and v14 as harmonized by this correction) converge 6.7%-9.9%. v12 explicitly excluded (permanently unrecoverable first ~37 minutes, not merely a basis mismatch). |
| G | True latency | **MORE EVIDENCE REQUIRED** | Median well-evidenced (~83-116s across 4 cohorts) but not separately budgeted, per the governing brief's instruction not to call the dimension closed on median alone. Missing fact: a converged, multi-cohort characterization of the p90/max tail — four sized samples span 261.2s-865.2s at the maximum with no convergence (v10's own already-accepted 742.3s and this correction's newly-recovered v11 865.2s both materially exceed every figure the rejected report considered). |
| H | Monitoring coverage | **READY FOR RELEASE BUDGET** | ≥97% steady state. Nine cohorts converge 97.5%-99.99%+; both sub-99% cases honestly explained, non-recurring. |

Six of eight dimensions are honestly ready for a release budget (two of
them — evidence-survival and, arguably, false-Visit stratification — on
*stronger* footing than the rejected report established, via this
correction's own harmonization work). The two that are not (recall,
latency) are exactly the two the six named rejection findings concern.

## Smallest sufficient remaining Gate A proof

Per the governing brief's explicit instruction not to default to another
90-105-minute cohort, each remaining gap is matched to the smallest
sufficient closing action:

- **Evidence-survival harmonization (finding #5): CLOSED by this
  correction**, via offline reanalysis of a preserved cohort (option A) —
  no further action needed. v14's own already-collected raw ledger
  supplied everything required; no live session was necessary.
- **Latency tail (part of finding #4): PARTIALLY ADVANCED by this
  correction**, also via option A — recovering a real, valid, materially
  informative 4th sized sample (v11, n=23) from data that already existed,
  at zero field-time cost. The *remaining* gap is genuinely a sample-size
  problem (four cohorts, three of them single sessions, spanning a >3x
  max range) that this specific offline-reanalysis avenue has now been
  exhausted for (v7/v8 predate valid RTT calibration entirely; v12's own
  raw ledger has the same permanent ~37-minute gap that blocks its
  evidence-survival harmonization; v13 had zero admissions). Closing this
  properly needs **new** T0→T5 samples — but not necessarily a full
  marathon session: full T0→T5 samples accrue continuously throughout any
  live Observation session with real activity, so **a single additional
  representative daylight session of ordinary length (matching this
  project's own existing 90-105-minute convention, since a materially
  shorter session risks too few admitted Visits to add a meaningfully
  sized tail sample) run for its own, already-authorized purposes would
  suffice to add a 5th data point** — this does not require a
  latency-dedicated cohort to be separately scheduled. Until such a
  session runs (for whatever reason it is next authorized), this
  dimension should be reported as **median: informative; tail: open**,
  never as closed.
- **Recall (findings #1-#3): the smallest sufficient action is an explicit
  owner/release-authority decision (option E), not more field evidence.**
  The engineering side of this question is genuinely finished — two
  independent, adversarial investigations already exhausted every
  currently-trustworthy signal, and a third attempt on the same evidence
  basis is not indicated by anything in this evidence body. What remains
  is whether the observed, honestly-reported range (61.1%-87.5% broader
  recall; 64.7%-87.5% conservative, both driven by real activity density
  during sessions, not measurement noise) is an acceptable v1 launch
  characteristic, disclosed plainly to users as MockingBird's product
  doctrine already requires for comparable uncertainty (the same
  abstention-over-fabrication principle already applied to species
  identification, one layer earlier). **If the release authority instead
  wants a tighter numeric floor before deciding** (e.g., to know whether
  64.7%-level sessions are common or rare), the smallest sufficient
  further step is **not** a dedicated new field cohort either — it is 2-3
  more **already-otherwise-motivated** representative daylight sessions
  (whatever their own primary purpose), each independently reviewed for
  whole-scene recall using the same methodology v12/v14 already
  established, so that the *frequency* of high-density sessions among
  ordinary real-world use can be characterized rather than assumed from
  n=2. This is explicitly **not** a recommendation to schedule such a
  session — it names what a future session would need to measure *if and
  when one runs for other reasons*, consistent with the governing brief's
  instruction not to self-authorize a field cohort here.
- **Person-associated false-Visit regime: no action recommended.** This is
  an existing, already-disclosed, non-blocking known limitation (tracked
  under Gate B), unaffected by this correction, and does not need a
  dedicated session — it will be naturally re-exercised whenever a future
  session (run for any reason) happens to include a person in frame.

No combination of the above requires scheduling a new field cohort. The
two genuinely-open items (recall, latency-tail) are each smaller than "run
v15": one is an owner decision on already-sufficient (if divergent)
evidence, and the other is a data point that the project's ordinary
field-acceptance cadence will supply on its own the next time any
representative session runs for any purpose.

## Gate A decision

**OPEN — RELEASE DECISION REQUIRED.**

Recall — the single highest-priority Gate A dimension per
`product-doctrine.md`'s own "Governing priority before release" ("Trustworthy
detection, encounter reconstruction, Visit correctness... must be highly
reliable before release") — cannot be marked passed, budgeted, or closed
without an explicit release-authority judgment on whether a whole-scene
recall floor that can fall to 64.7% during unusually busy real activity is
an acceptable v1 characteristic. That decision has not been made by any
accepted milestone to date (Sustained/Crowded v2 explicitly declined to
make it, calling it "an explicit global budget/release review, which this
milestone does not perform and does not authorize"; the rejected
reconciliation attempted to make it by deleting the inconvenient
denominator, which is not a valid way to make it).

**A second, independent blocker also remains and would still need to close
even after the recall decision is made:** true latency's tail distribution
(p90/max) has not converged across the four sized samples now available,
and this correction's own new evidence (v11's recovered 865.2s maximum,
alongside v10's own already-accepted 742.3s) makes the tail wider and less
converged than any prior evidence body considered, not more settled.

Do not read "OPEN — RELEASE DECISION REQUIRED" as "almost passed": six of
eight metrics are genuinely ready for a release budget, several on
stronger evidence than before this correction, but Gate A's own governing
priority makes recall dispositive, and recall is not one of the six.

## Release-phase effect

None. This correction does not change **CURRENT PHASE: SUBSTANTIAL PRODUCT
DEVELOPMENT**. It does not authorize External Pre-Release Acceptance,
Final Release Hardening, another field cohort, or another
ambiguous-boundary investigation. It corrects Gate A's own status back to
OPEN and narrows what remains open; it does not itself close any lane.

## License status

Unchanged, carried forward accurately: MIT was recommended by Release
Licensing, Distribution & Third-Party Legal Closure v1's own decision
packet, but the decision remains an explicit **owner** decision, not
resolvable by any engineering milestone including this one. No `LICENSE`
file exists and none is created here. This status is independent of Gate
A and is not used, in either direction, as a reason to delay or accelerate
the Gate A decision above.

## BirdNET legal status

Unchanged, carried forward accurately: BirdNET's model weights are CC
BY-NC-SA 4.0 (NonCommercial); MockingBird's packaging never redistributes
them, durably enforced by a build-time guard; acoustic capability is
optional and release-ready on that basis. Whether an individual user's own
private, non-commercial use could ever become implicated merely because
the surrounding open-source project also accepts donations or sells
optional paid support remains genuinely unresolved pending legal review.
This is a disclosure carried forward, not a new finding, and is likewise
independent of the Gate A decision above.

## Residual risks

1. Ambiguous-boundary sustained/crowded recall limitation — root-caused,
   safe (omission-only), no further engineering fix currently justified;
   its release-acceptability is the open Gate A recall decision above.
2. True-latency tail (p90/max) genuinely unconverged, now known to be
   wider (up to ~865s observed) than any prior evidence body considered.
3. Person-in-frame false-Visit rate under the current admission stack is
   unmeasured (n=0); non-blocking, already tracked under Gate B.
4. Detector-sourced-but-still-wrong background-crop Gate B residual —
   already known, already tracked, unaffected by this correction.
5. 3+-simultaneous-subject behavior genuinely untested across 8 cohorts
   that sought it — after-release/evidence-driven, non-blocking.
6. `maximum_episode_duration_ms`'s veto-reach asymmetry (disclosed by
   Sustained/Crowded v2, not fixed, not proven live-reachable) — candidate
   fact for a future milestone only if new evidence of it firing appears.
7. v11's newly-recovered latency figures (this correction) have not been
   independently visually re-verified against footage the way v11's own
   original, accepted findings were — treat as a real, methodologically
   sound but not fully re-audited data point.
8. Source-code `LICENSE` owner decision outstanding (pre-release, not Gate
   A).
9. BirdNET commercial-adjacent legal posture genuinely unresolved pending
   legal review (pre-release, not Gate A).
10. Gate G (External Pre-Release Acceptance) not yet scoped or started.

## Decision

**A**
