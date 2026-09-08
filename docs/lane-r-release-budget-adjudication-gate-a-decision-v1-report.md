# Lane R Release-Budget Adjudication & Gate A Decision v1

**Type:** Bounded, read-only release-decision milestone (adjudication of existing evidence, not a new field session or research campaign). No product, schema, or tooling code changed. No field session run. No deployment. No push.

**Classification: A — GATE A PASS, LANE R CLOSED.** This milestone renders the decision the immediately-prior milestone (*Lane R Accumulated Latency Evidence & Release-Budget Decision v1*) explicitly deferred to "the next global reconciliation." This is that reconciliation.

---

## 0. Executive summary

This milestone adjudicates — independently verifies, does not merely restate — the candidate release budget proposed by *Lane R Accumulated Latency Evidence & Release-Budget Decision v1* (2026-09-07). Every decisive claim named by the governing directive was checked against primary sources: cohort membership and sample counts, the v10 percentile correction, the `≥12-sample` criterion's actual origin in code, the pooled/bootstrap statistics, every `>300s` causal classification, and — independently, from the rejected report's own text, not merely from the correction's characterization of it — the exact two defects that invalidated the 2026-09-05 Gate A "PASS." No decisive calculation was found wrong; the one disclosed correction (v10's p90: 183.3s → 201.5s) is independently reproduced here and confirmed non-material.

The proposed three-part latency budget (typical latency numeric; upper tail qualitative, not a tight SLA; a 20-minute architectural ceiling reference, not a statistically-fit maximum) satisfies every element the governing directive itself named as sufficient, and — critically — repeats neither disqualifying defect of the rejected 2026-09-05 PASS: it does not exclude any failure mode from a denominator, and it discloses every known outlier (742.3s, 865.2s) prominently rather than omitting the worst of them from its own tail characterization.

With this budget accepted, all eight Gate A release dimensions plus the multi-subject-correctness requirement now carry an accepted disposition — either a numeric budget or an explicit, disclosed known-limitation-without-a-fabricated-floor. No correctness defect was found anywhere in this evidence body. **Decision: A. GATE A PASS — LANE R CLOSED.** This does not start External Pre-Release Acceptance or Final Release Hardening; those remain separately gated, unauthorized by this milestone.

---

## 1. Verified baseline

Verified directly at the start of this milestone, matching the directive's own "expected accepted baseline" exactly:

- **HEAD:** `ab48255` (`Reconcile release-execution-state.md: record Lane R Accumulated Latency Evidence & Release-Budget Decision v1`).
- **Branch:** `main`. **Upstream:** `+379 -0` vs `origin/main` — not pushed (377 at the start of the prior milestone, +2 for its own two commits — no drift, no unexpected push/pull).
- **Schema:** `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`, independently grepped) — matches.
- **Lane R:** `OPEN — RELEASE-CRITICAL — TRUE LATENCY TAIL EVIDENCE REMAINS`, per the top-of-file `CURRENT PHASE` narrative's own most-recently-appended paragraph.
- **Current authorization at start:** `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED` — matches.
- **Active writers:** none (`ps aux` found no `mockingbird`/`uvicorn`/`camera_node`/`deploy_windows_dev` process).
- **The seven preserved untracked detector files:** present and unmodified (`git status --porcelain` reconfirmed at the start of this milestone; identical set as every predecessor milestone).

No materially different state was found than the directive's own expected baseline; proceeding without reconciliation was correct.

---

## 2. Governing sources read, and evidence adjudicated

Read in the exact order specified: `docs/release-execution-state.md` (top-of-file `CURRENT PHASE` narrative in full, §1 header, and the exact `Gate A`/`Lane R` cross-reference chain within it), `docs/product-doctrine.md` (in full), `docs/roadmap.md` (`Governing priority before release`, `Current status`, `Release readiness vs. continued capability work`, `Gate A` in full, `Gate B` heading, `Gate G`, and `Numeric release budgets` in full). Then, in full: `docs/lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md` — the accepted evidence reconstruction this milestone adjudicates.

Additionally read, per the directive's explicit instruction to read "the rejected prior PASS/reversal record": `docs/gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md` (the rejected 2026-09-05 PASS, its own recall and latency sections read directly) and `docs/gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md` (the same-evening correction that rejected it).

This milestone deliberately did **not** re-open `docs/release-execution-state.md` §3/§6.R's full historical narrative beyond what the top-of-file `CURRENT PHASE` paragraphs already reproduce (the two are the same content, per this document's own "append in three places" convention, confirmed via `git show --stat` on the commit that added them) — re-reading the same facts a second time would be exactly the "broad archaeology campaign" the governing directive says not to repeat. Raw per-sample JSON for v9/v14/Convergence v3 was not independently re-opened either, since the accumulated-evidence milestone already read it directly and reproduced every published statistic exactly (verified by this milestone's own independent recomputation of the one figure in dispute — v10's p90 — using only the already-published per-sample table, without needing the raw JSON files at all; see §3 below).

---

## 3. Independent verification of decisive facts

Each item the governing directive named as requiring independent verification (not mere restatement) was checked directly against primary sources:

| Decisive fact | Independent verification performed | Result |
|---|---|---|
| Cohort membership/sample counts, inclusion/exclusion rules | Cross-checked the §2.1 cohort table's exclusion reasoning (v6/v7/v8/2026-08-19 pre-instrumentation or infra gap; v12 n=2 too small + lost ledger; v13 n=0; dusk session n=1 non-biological; v11 reconstructed-only) against the stated reasons in each case | Reasoning sound and consistently applied; no cohort silently dropped or added |
| v10 percentile correction | Recomputed directly from v10's own 11 published per-sample values (76.5, 85.2, 183.3, 103.9, 79.4, 114.8, 201.5, 742.3, 69.3, 74.7, 138.7) using `numpy`, all five percentile conventions (`linear`/`lower`/`higher`/`nearest`/`midpoint`) | **All five independently yield 201.5s.** 183.3s is confirmed to be candidate-005's own raw value, not the 90th percentile — the correction is verified correct, not merely plausible |
| Retained 742.3s maximum | Confirmed present, unmodified, in the pooled max (§4.2 of the adjudicated report) and in this milestone's own dimension table (§6, below) | Retained, not softened |
| The `≥12-valid-sample` criterion's origin | Independently grepped `scripts/field_acceptance_session_driver.py`: `target_sample_count: int = 12` (line 124); `decide_stop` (line 163) permits early stop only if `elapsed_seconds >= minimum_duration_seconds AND sample_count >= target_sample_count` — the 75-minute maximum fires regardless of sample count | Confirmed: a per-session stopping heuristic, not a statistical minimum or release-gate requirement, exactly as claimed |
| v3/v4 protocol qualifications | Read §3.A/§3.B of the adjudicated report directly (75.000-minute internal driver accounting vs. 76.55-minute total wall-clock footprint, ~93s explained as stop-dispatch/settlement/snapshot overhead; recorder-readiness proven mechanically for v4 specifically) | Reasoning is sound and appropriately bounded; the report's own disclosed limitation (Convergence v4's raw ledger JSON is Windows-host-only, never independently cross-checked against raw JSON by any milestone) is preserved here, not resolved by assertion |
| Pooled vs. per-cohort statistics; uncertainty-method limitations | Reviewed the bootstrap method (20,000 resamples, per-cohort-sized) in §5.2: each cohort's own observed p90 falls inside its own bootstrap 90% interval computed from the pooled set. This is the textbook-correct way to ask "is this scatter more than sampling noise," standard and transparent, not invented to force a result | Method sound; the pooled p90's own honest residual uncertainty (90% CI [198.6s, 331.8s], ~133s wide) is disclosed, not erased, by the finding |
| All known `>300s` causal classifications | Reviewed §6 of the adjudicated report: five in the primary pool (v9 307.4s, v10 742.3s, Convergence v3 360.8s/482.4s, Convergence v4 429.4s) plus v11's reconstructed 865.2s, all traced to the same already-accepted Visit-Continuity/ambiguous-boundary mechanism | No new or pathological cause; consistent with the already-accepted design trade-off — no new perception investigation warranted |
| The prior PASS reversal's denominator and recall issues | Read directly from the rejected report's own text (not only the correction's characterization of it) | **Independently confirmed, see §4 below** |

No decisive calculation was found wrong. The only correction in the evidence body (v10's p90) is confirmed correct by this milestone's own independent recomputation, and is non-material (201.5s still falls inside every previously-stated cross-cohort band, changing no prior conclusion).

---

## 4. Historical PASS-reversal safeguards, independently reconfirmed

The 2026-09-05 attempt to declare Gate A `PASS` / Lane R `CLOSED` was rejected the same evening. This milestone read the rejected report's own primary text directly (not only the correction's summary of it) and confirms both disqualifying defects independently:

1. **Recall denominator manipulation.** The rejected report's own "Gate A decision" section states verbatim: *"Explicit release budgets are accepted for seven of the eight primary dimensions (recall, **excluding the disclosed limitation**; false-Visit rate; fragmentation; duplicates; useful-evidence; evidence survival; monitoring coverage)..."* — confirming, in the rejected document's own words, that its accepted recall figure excluded the `blocked_ambiguous_boundary` sustained/crowded failure mode from the denominator used to declare readiness. This is a disqualifying error: end-to-end recall must never exclude a real miss by internal failure reason.
2. **Omitted latency maximum.** The rejected report's own cross-dimension summary table states the true-latency (p90/max) row as *"p90 173.9s-235.5s; max 261.2s-307.4s"* — a range that **omits v10's own already-accepted, already-disclosed 742.3-second maximum**, disclosed elsewhere in the very same document's cohort table. Presenting a tail characterization that silently excludes the worst known sample is exactly the kind of denominator/selection error the recall defect above also commits, just applied to the latency dimension.

**This milestone's own accepted budget (§7 of the adjudicated report, ratified in §6 below) commits neither error.** Recall is not re-touched here at all — it was already, separately, correctly closed by an explicit 2026-09-06 external release-authority decision, preserved unchanged (§6, below). The latency budget adopted here explicitly includes both 742.3s and the reconstructed 865.2s in its own tail disclosure and ceiling reasoning (§5, below) — the worst-known sample is the central input to the "no hard maximum, architectural reference only" framing, not an inconvenient fact left out of a table.

---

## 5. Release-budget decision — true capture-to-visible latency

Distinguishing exactly the categories the governing directive named:

| Category | What the evidence supports | What this milestone does **not** do with it |
|---|---|---|
| Observed typical latency | Pooled median 103.9s across 69 samples/5 cohorts/6 days; bootstrap 90% CI [80.3s, 114.8s] | Not treated as a guarantee — stated as a typical/operational expectation |
| Operational release expectation | "Roughly 80–115 seconds" for a typical Visit to become visible | This is the number adopted below, exactly this narrowly |
| Statistical percentile guarantee | Pooled p90 point estimate 259.2s, bootstrap 90% CI [198.6s, 331.8s] — a real, ~133s-wide residual uncertainty | **Not adopted as a numeric SLA.** The directive explicitly forbids treating the 80–115s range as universal or fitting a tight percentile guarantee this evidence does not support, and this milestone does not |
| Hard maximum | No statistically-fit maximum is defensible from n=69 (heavy-tailed distribution, biased/high-variance sample-maximum estimator) | **Not invented.** No numeric hard maximum is adopted |
| Architectural reference | The existing 20-minute (1,200s) component-decision-horizon design bound, already part of the accepted architecture, not fit to this data | Cited only as a reference — **not** presented as a measured maximum or user-facing SLA, exactly as the directive requires |
| Documented known limitation | Sustained/crowded activity produces both the recall omission cost and the longest latency tails, via the identical already-accepted mechanism | Disclosed as one coherent product characteristic, not two separate footnotes |

**Accepted budget, adopted by this milestone:**

1. **Typical latency (numeric):** a MockingBird Visit typically becomes visible in **roughly 80–115 seconds** after the triggering activity is captured (pooled median 103.9s; bootstrap 90% CI [80.3s, 114.8s]; six independent real sessions across six calendar days, unchanged accepted production stack, each independently landing inside this same band).
2. **Upper-tail behavior (qualitative, not an SLA):** roughly 1 in 10 Visits takes materially longer — observed per-cohort p90 values range 174–385 seconds (pooled bootstrap p90 point estimate 259.2s, 90% CI [198.6s, 331.8s]). Disclosed to users qualitatively, never as a committed number: *"Most Visits appear within about two minutes. Occasionally — especially during busy or sustained activity — it may take several minutes longer."*
3. **Ceiling (architectural, not statistically-fit):** no numeric maximum/SLA is adopted. The existing 20-minute (1,200s) decision-horizon design bound is the honest ceiling reference; every observed maximum to date (742.3s live-measured, 865.2s reconstructed-only) sits at 62–72% of it, never beyond it.
4. **Sustained/crowded-activity behavior:** disclosed jointly with the already-accepted recall limitation, as one product characteristic: *"during unusually busy, continuous activity, MockingBird may occasionally miss creating a separate Visit for a later arrival, or take noticeably longer to finalize one, rather than risk incorrectly merging two different animals."*
5. **Known limitations retained, not smoothed over:** the `≥12`-per-session target has not been individually re-met since v14 (2026-09-05) — Convergence v3 (n=9) and v4 (n=11) both fell short as individual sessions, though the pooled six-day, 69-sample base is far larger than that per-session figure in any aggregate sense (§3, above; independently confirmed as a stopping heuristic, not a sufficiency threshold); v11 (n=23) is supporting/reconstructed evidence only, not independently re-verified against footage, and is excluded from the primary pooled statistics; v10's own report's p90 is corrected from 183.3s to 201.5s (non-material); every cohort before Convergence v4 used manual, operator-judged session-stop timing rather than the now-hardened automated driver; Convergence v4's own raw ledger JSON was never mirrored into this repository and so was never independently cross-checked against raw JSON by any milestone, including this one.

**Why this is sufficient, per the governing directive's own five-part test:** a measured typical-latency expectation (✓, item 1); an explicitly variable upper tail (✓, item 2); documented sustained/crowded-activity behavior (✓, item 4); no unsupported hard maximum (✓, item 3 — the 20-minute figure is never called a maximum or SLA); honest user-facing disclosure (✓, the quoted language above). No further field session is required to accept this specific, narrow structure — the bootstrap analysis (§3, above) directly answers the standing objection that per-cohort p90 disagreement means the tail hasn't converged, and a further "sustained/crowded density" session (named in the adjudicated report's own §9) would only sharpen a *tighter numeric* p90/max figure, which this budget deliberately does not attempt to adopt in the first place.

---

## 6. Complete Gate A dimension-by-dimension verdict

Every Gate A dimension, not only latency, reviewed against its currently accepted status in `roadmap.md`'s "Numeric release budgets" and this milestone's own latency adjudication above. Nothing below is reopened without a reproduced defect or genuine new field evidence; nothing is silently excluded.

| Dimension | Status | Accepted budget / disposition | Evidence base |
|---|---|---|---|
| End-to-end whole-scene Visit recall | **ACCEPTED KNOWN LIMITATION — no numeric floor** (unchanged, preserved as-is) | v12 87.5%, v14 64.7% conservative / 61.1% broader — the honest observed range, disclosed to users, not averaged or floored | 2026-09-06 explicit external release-authority decision; not re-litigated here |
| Ambiguous-boundary sustained/crowded recall mechanism | Root-caused, safe (omission-only), no further engineering fix currently justified | Cost stays inside the recall figures above, never removed from them; revisit only on a genuinely new safe signal | Two adversarial investigations (Ambiguous-Boundary Real-Subject Recall Correctness v1; Sustained/Crowded v2), both exhausted |
| Maximum confirmed false-Visit rate | READY | **≤ 15%** (pooled 6.25%; v12 5.6%, v14 7.1%) — person-in-frame regime separately, honestly unmeasured (n=0) under the current stack, non-blocking | v12, v14 (person-confound-free) |
| Maximum confirmed fragmentation rate | READY | **≤ 5%** (measured 0% across seven independently-varied cohorts) | 2026-08-19, v5, v7, v8, v9, v12, v14 |
| Maximum confirmed duplicate-Visit rate | READY | **≤ 2%** (measured 0% across at least eight cohorts) | v5 through v14 |
| Minimum useful-evidence rate (combined) | READY | **≥ 85%** (converges 92.9%–96.0%) | v7, v12, v14 |
| Maximum evidence-loss (`blocked_missing_evidence`) | READY | **≤ 15%** (converges 6.7%–9.9% across six harmonized cohorts; v12 excluded — permanently lost first ~37 of 97 minutes of its own raw ledger) | v7, v8, v9, v10, v11, v14 |
| Minimum monitoring coverage | READY | **≥ 97%** (97.5%–99.99%+; two sub-99% outliers each independently explained, not an ongoing defect) | Nearly every cohort |
| **True capture-to-visible latency** | **NEWLY CLOSED BY THIS MILESTONE** | Typical ~80–115s (numeric); upper tail qualitative, not an SLA; 20-minute architectural ceiling reference, not a fitted maximum — see §5, above | 69 samples, 5 intact cohorts, 6 independent calendar days |
| Multi-subject Visit correctness | **CLOSED** (Phase 1/2/4, 2026-08-19/20) | Event-reuse persistence for genuinely simultaneous subjects; transitive ambiguous-cluster arbitration for sequential fragmentation | Proven through the real, unmodified assembler end-to-end |

**Every dimension now carries an accepted disposition.** No dimension is silently excluded, no recall or latency sample is dropped from any figure above, and no dimension is reopened without the reproduced defect or new field evidence the governing directive requires — the only change this milestone makes is closing the one dimension (true latency) that the immediately-prior milestone left as an explicit recommendation, using evidence already gathered, not new field data.

---

## 7. Final decision

### A. GATE A PASS — LANE R CLOSED

All current Gate A criteria are satisfied under the defensible, deliberately narrow accepted release budget stated in §5 and ratified across all dimensions in §6. No correctness defect blocks this decision (§3, §4). This decision does not repeat either disqualifying defect of the rejected 2026-09-05 PASS (§4).

**Accepted release budget, in full (true latency, the dimension this milestone closes):**
- Typical: ~80–115 seconds (median-based, numeric).
- Upper tail: qualitative disclosure only (~1 in 10 Visits materially longer, 174–385s observed per-cohort p90 range; pooled bootstrap p90 90% CI [198.6s, 331.8s]) — never a numeric SLA.
- Ceiling: 20-minute (1,200s) architectural decision-horizon reference — never a measured maximum.
- Sustained/crowded-activity behavior: one disclosed product characteristic, shared with the recall limitation.

**Known limitations, explicitly not waived, carried into the release record:**
- Whole-scene recall may fall to 64.7% (conservative) during unusually busy, sustained/crowded activity — an accepted product characteristic, not a defect, with no numeric floor.
- The person-in-frame false-Visit regime is genuinely unmeasured (n=0) under the current admission stack.
- The `≥12`-valid-sample per-session target has not been individually re-met since 2026-09-05 (v14); the pooled six-day, 69-sample evidence base is the basis for this decision, not any single session's own count.
- v11's latency contribution (n=23) is supporting/reconstructed evidence only.
- Convergence v4's raw ledger was never independently cross-checked against raw JSON by any milestone.

**Remaining downstream release gates (unauthorized by this milestone — see §8):** Gate G (External Pre-Release Acceptance), then Lane S (Final Release Hardening), then the one public launch.

---

## 8. Release sequencing

Per the accepted one-release doctrine (`roadmap.md` Gate G; `release-execution-state.md` §7), Lane R closure is distinct from public release. The sequence remains:

**External Pre-Release Acceptance → Final Release Hardening → one public launch.**

**This milestone does not start either downstream gate.** Gate G is not begun, planned, or scheduled here; Lane S remains explicitly "LAST — awaits R," and R's own closure by this milestone does not itself constitute authorization to proceed — a fresh, explicit authorization step is required, consistent with every prior lane closure in this project's history (closing a lane has never, on its own, auto-started the next one).

---

## 9. Documentation delta

**Updated:** `docs/release-execution-state.md` — the top-of-file `CURRENT PHASE` narrative, §3 ("Current authorized milestone"), and §6.R ("Complete Field Acceptance," including its authoritative top-of-section status line, which is rewritten from `OPEN — RELEASE-CRITICAL — TRUE LATENCY TAIL EVIDENCE REMAINS` to `CLOSED`) each received one additive, dated entry recording this decision, per this file's own established convention (confirmed by inspecting exactly how the immediately-prior milestone's own reconciliation commit was structured). No other lane, no roadmap sequencing, and no phase label changed; `CURRENT PHASE` remains exactly `FEATURE FREEZE — EVIDENCE, RELEASE READINESS & HOUSEKEEPING`, and current authorization remains exactly `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`, per this milestone's own governing directive.

**Deliberately not updated:** `docs/roadmap.md`. Its "Gate A" and "Numeric release budgets" sections still read `OPEN — TRUE LATENCY TAIL EVIDENCE REMAINS` and "no budget adopted" respectively, as of their own 2026-09-06 entries — now stale relative to this decision. The governing directive for this milestone scopes the documentation update to `docs/release-execution-state.md` only ("do not change unrelated lanes or roadmap sequencing"); reconciling `roadmap.md`'s own prose to match is exactly the kind of global-roadmap-reconciliation action this project's own established convention (e.g., *Global Remaining Product-Development & Release-Queue Reconciliation v1*, *Global Product & Release Readiness Reconciliation v2*) performs as its own dedicated step, not something this bounded adjudication milestone should reach into unilaterally. This gap is disclosed here explicitly, not left for silent discovery.

**No product, schema, or tooling code changed. No field deployment. No full Core run. No push.** All seven preserved untracked detector files reconfirmed present and unmodified at the close of this milestone.

---

## 10. Classification

**A** — a decisive, accepted change to release-governance state (Gate A PASS, Lane R CLOSED), independently adjudicated from existing evidence per this milestone's own explicit charter to render that decision, not merely to recommend one for further review.

---

*Prepared as a bounded, read-only release-decision milestone. No product, schema, or tooling code was changed. No field session was run. No deployment occurred. No push was made.*
