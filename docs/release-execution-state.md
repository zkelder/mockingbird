# MockingBird Release Execution State

This file controls execution sequencing, not product doctrine.
[product-doctrine.md](product-doctrine.md) defines what MockingBird is.
[roadmap.md](roadmap.md) preserves the full roadmap. This file records
current accepted state, remaining lanes, release classification, and what
work is presently authorized.

Claude's "next natural milestone" suggestions are advisory only. They do
not authorize future work.

## CURRENT PHASE: FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING

**Corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1** (see
[global-remaining-product-development-release-queue-reconciliation-v1-report.md](global-remaining-product-development-release-queue-reconciliation-v1-report.md)).
The prior `SUBSTANTIAL PRODUCT DEVELOPMENT` label is stale: a full
lane-by-lane walk of §6, below, against direct repository evidence (not
recent session-scoped focus, and not this session's own persisted memory,
which was found behind the repository on at least one point) found every
layer of `roadmap.md`'s "Remaining roadmap -- canonical sequence" has
substantial accepted delivery, and a five-question test applied to every
named remaining product opportunity (year-over-year seasonality,
weather-on-before/after composition, multi-camera Feature linking, ranked
Feature comparison, Place Story period summaries, dedicated taxon/Feature
pages, representative Story imagery, environmental historical backfill)
found none clears the bar for substantial product development before
release. What genuinely remains is release-critical validation (Lane R's
true-latency tail, daylight-dependent), release readiness/hardening
residuals (Lanes L/E/F), a small resolved-but-not-yet-mechanically-adopted
licensing housekeeping item (Lane P -- the owner has selected MIT), the
still-open BirdNET commercial-adjacent legal question (no engineering
action available), and disclosed non-blocking defects. Representative
Field Acceptance, External Pre-Release Acceptance, and Final Release
Hardening (Lanes R/S, below) remain the correct downstream sequence,
gated on Lane R's own daylight-dependent evidence and Lane P's mechanical
adoption -- **not** on unfinished product capability. This correction does
**not** authorize Lane R's next tranche, External Pre-Release Acceptance,
Final Release Hardening, or any product-development milestone -- see §6,
"Global remaining execution queue," for the complete lane-by-lane
picture this phase label now reflects.

**Reconfirmed 2026-09-07 by Global Product & Release Readiness
Reconciliation v2** (see
[global-product-release-readiness-reconciliation-v2-report.md](global-product-release-readiness-reconciliation-v2-report.md)).
Read-only global sequencing pass, HEAD `5e36989`, schema `v59`. Six
milestones accepted since v1 (MIT Source License Adoption & Lane P
Mechanical Closure v1, then five Place-Intelligence-family enrichment
milestones through Place Feature Comparison & Habitat Outcomes v1) were
independently re-verified against direct repository evidence, not
assumed: Lane P is now genuinely `CLOSED` (real `LICENSE` file,
`pyproject.toml`/`web/package.json` metadata, corrected `README.md`, all
confirmed on disk); Lane R remains exactly `OPEN -- RELEASE-CRITICAL --
TRUE LATENCY TAIL EVIDENCE REMAINS`, untouched by any of the six
milestones, with zero new field evidence since *Representative Daylight
True-Latency Tail Convergence v2* (blocked at a hard pre-deployment
daylight gate, 2026-09-05 night); every one of the five enrichment
milestones deliberately picked up an item this file's own v1 correction
had already classified `D -- enrichment`, which is evidence the freeze
held, not evidence it was breached. The feature-freeze finding above is
**reaffirmed, not weakened**. This correction also found and fixes §16
("Transition checkpoint," below), which recorded a stale `763fe22` HEAD
from the 2026-08-26 Multi-Camera Place Experience v2 checkpoint,
including a now-false "LICENSE still genuinely absent" line -- corrected
in place, see §16. This correction does **not** authorize Lane R's next
tranche, does **not** invent a latency budget, does **not** start
External Pre-Release Acceptance or Final Release Hardening, and does
**not** change current authorization from `NONE`.

**Corrected 2026-09-07 by Representative Daylight True-Latency Tail
Convergence v3** (see
[representative-daylight-true-latency-tail-convergence-v3-report.md](representative-daylight-true-latency-tail-convergence-v3-report.md)),
directly authorized outside this file as exactly one bounded Lane R field
session. HEAD `f222217` (one commit ahead of the `e031291` starting
baseline: a genuine, reproduced, packaging-only `numpy` version-drift
defect blocked deployment outright and was fixed with the same minimal
pin-shape already used for `idna`/`click` in `WINDOWS_RUNTIME_REQUIREMENTS`,
validated by its own 12 directly-relevant tests, before any field
deployment -- zero detector/classifier/threshold/tracker/admission/Visit
-assembly/schema/production-configuration change). Schema unchanged
(`v59`). A genuine daylight session ran end-to-end (08:45:55-14:03:50 EDT,
76 minutes, at the 75-minute maximum) and produced 10 admitted candidates
/ 9 procedurally valid RTT-normalized latency samples -- short of the
≥12-sample target. Median converges more tightly than ever across five
cohorts now (82.9-115.7s, this session's own 112.2s landing almost exactly
on v9's 111.8s); the maximum (482.4s) falls inside the already-established
261.2-742.3s intact-cohort range; but this session's own p90 (385.1s) is a
new high outside every prior cohort's own 173.9-318.5s p90 band, leaving
the tail's upper-percentile region less resolved, not more. **Lane R
remains exactly `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS`** (see §6.R, below, for the complete updated record). This
correction does **not** authorize Lane R's next tranche, does **not**
invent a latency budget, does **not** start External Pre-Release
Acceptance or Final Release Hardening, and does **not** change current
authorization from `NONE`.

**Corrected 2026-09-07 by Field Acceptance Tooling Correctness & Preflight
Closure v1** (see
[field-acceptance-tooling-correctness-preflight-closure-v1-report.md](field-acceptance-tooling-correctness-preflight-closure-v1-report.md)),
directly authorized outside this file as a bounded, tooling-correctness
-only milestone -- no field session, no deployment, no hardware touched.
HEAD unchanged (`4e46952`); schema unchanged (`v59`). Closes five concrete
procedural gaps *Representative Daylight True-Latency Tail Convergence
v3* exposed: (A) a `--dev-root` path-resolution inconsistency across
`field_acceptance_instance_lifecycle.py`'s own subcommands, fixed by
routing every one of them through the same already-accepted
`deploy_windows_dev.resolve_dev_root_path` `preflight` already used; (B) a
Windows-style `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` value silently
mistranslating to a garbage path with no error (v3's own Defect #3), fixed
in `deploy_windows_dev.py`, plus a new, independently-testable
pre-Observation recorder-readiness gate
(`scripts/field_acceptance_recorder_readiness.py`) the next field
procedure must run and honor (`STOP BEFORE OBSERVATION` on failure); (C) a
hard, monotonic-clock-enforced 45-minute-minimum/75-minute-maximum/
≥12-sample-target session-stop contract, previously only ever driven by
operator judgment, now a tested, bounded polling loop
(`scripts/field_acceptance_session_driver.py`); (D) an enforced
Observation-stop -> finalization-settled -> final-raw-ledger-snapshot
ordering (same new driver script), previously vigilance-dependent (v3's
own report narrates the operator personally catching and correcting this
by hand); (E) a documentation/reporting clarification of the already
-correct `fallback_measured` terminology (admission-arbitration fallback,
never a timestamp fallback) -- zero logic change. 42 new deterministic
tests across 6 files; 404 total directly-affected tests passing, zero
regressions (including the real, `pip`-install-backed packaging suite).
**Lane R's own substantive status is unchanged and this milestone does
not touch it** -- see §6.R, below, for the tooling-readiness delta this
record adds. This correction does **not** declare Gate A passed, does
**not** close Lane R, does **not** authorize another field session, and
does **not** change current authorization from `NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED`.

**Corrected 2026-09-07 by Field Acceptance End-to-End Integration Proof v1**
(see
[field-acceptance-end-to-end-integration-proof-v1-report.md](field-acceptance-end-to-end-integration-proof-v1-report.md)),
directly authorized outside this file as a bounded, integration-and
-correctness-only milestone -- no field session, no deployment, no hardware
touched. HEAD unchanged (`2e7e8e0` at start); schema unchanged (`v59`).
Closes all three integration limitations the tooling-correctness milestone
immediately above named as out of its own bounded scope, using one real,
disposable, stdlib-only fake HTTP service reachable by a real subprocess:
the actual `field_acceptance_session_driver.py run` CLI entry point (target
-reached, hard-maximum, settlement-timeout, both credential-failure
shapes); the `field_acceptance_recorder_readiness.py --dev-root`
process-liveness branch against a genuinely running disposable process,
through the real, unmodified `deploy_windows_dev.real_windows_host()`; and
the complete field-tooling sequence (lifecycle init -> recorder readiness
-> authenticated Observation start -> monotonic session driver at the real,
unmodified 45/75-minute/12-sample defaults -> stop -> finalization settled
-> final raw-ledger snapshot -> bounded collector shutdown -> reconciliation
-> latency accounting -> cleanup), run as one bounded simulated scenario.
**No integration defect was found or reproduced in production code** -- all
three limitations closed cleanly on the first genuine end-to-end attempt;
the only fixes were to this milestone's own new test code. 12 new tests,
333 total directly-affected tests passing, zero regressions; `ruff check`
clean; no production code changed anywhere. This closure does **not**
declare Gate A passed, does **not** close Lane R (unchanged: `OPEN --
RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`), and does **not**
authorize the next Representative Field Acceptance tranche, External
Pre-Release Acceptance, or Final Release Hardening. **Authorization remains
NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.**

**Corrected 2026-09-07 by Representative Daylight True-Latency Tail
Convergence v4** (see
[representative-daylight-true-latency-tail-convergence-v4-report.md](representative-daylight-true-latency-tail-convergence-v4-report.md)),
directly authorized outside this file as exactly one bounded Lane R field
session. Starting state verified exactly as expected: HEAD `fcf236f`,
schema `v59`, Lane R `OPEN` and untouched, worktree safe, all seven
preserved untracked detector files present and unmodified throughout;
authorization at start `NONE`. Classification **B**. A genuine 75-minute
daylight session ran end-to-end (17:03:26-18:19:58 EDT) on the accepted,
unchanged production stack (MDv5a/ONNX/CUDA, `score_threshold: 0.1`),
using -- for the first time in a real field session -- the fully-hardened
tooling chain the two milestones immediately above closed and proved:
the recorder-readiness gate confirmed genuine advancing frames before the
session was allowed to continue, and the monotonic session driver enforced
the exact 45/75-minute/12-sample contract and the correct stop ->
settle -> snapshot ordering automatically (no operator vigilance required,
unlike every prior real cohort through v3). Produced 11 admitted
candidates / **11 procedurally valid** RTT-normalized latency samples (zero
invalid of any kind, the first Lane R cohort with none) -- one short of the
≥12-sample target, for a second consecutive session. Ledger reconciliation
was fully `COMPLETE` for the first time in this milestone family's own
history (zero gaps in `raw_detections`/`track_generations`/
`proposal_outcomes`, not merely zero *known* missing records), and the
independent acceptance recorder ran cleanly the entire session (1,335
frames, zero gaps exceeding 10 seconds) -- directly closing, in a real
field session for the first time, the exact recorder-verification gap v3's
own Defect #3 exposed. Median: 94.5s, reinforcing convergence across five
intact cohorts now (82.9-115.7s span, unchanged bounds). p90: 258.7s, back
inside the pre-v3 173.9-235.5s-adjacent band, easing but not resolving v3's
own divergence finding (five cohorts' p90 values still span 173.9-385.1s,
more than 2.2x). Max: 429.4s, inside the already-established
261.2-742.3s range for a second consecutive cohort. The sole >300-second
sample (429.4s) was fully traced to the same already-accepted
Visit-Continuity/ambiguous-boundary-arbitration mechanism, this time
corroborated by both the raw ledger (a 69-generation, 32-proposal contested
component) and, for the first time alongside an intact live cohort, real
independent-recorder frames showing genuine activity at the scene's own
feeder. One substantive finding disclosed rather than smoothed over: one
admitted candidate (candidate-005) is, on direct visual review of the
recorder's own frames, more likely a person and an accompanying small pet
passing through frame than a wild bird -- the same already-documented
person/domestic-pet confound class *Hard-Negative Visit Admission Precision
& Species-Escalation Correctness v1* and *Representative Daylight Gate A
Field Acceptance v9* already characterized, not a new mechanism; its own
latency measurement is retained unmodified in every statistic, per this
project's own abstention-over-fabrication discipline. One new, minor,
disclosed-not-fixed tooling gap found: `field_acceptance_instance_
lifecycle.py mark-archived --evidence-archive` does not resolve a
Windows-style path the same way `--dev-root` now does (the Tooling
Correctness milestone's own fix covers only `--dev-root`) -- a WSL-style
path workaround succeeded immediately, evidence was archived successfully,
not fixed here per this milestone's own bounded field-evidence scope. No
correctness defect was found or reproduced anywhere in the product; zero
production code changed. **Gate A decision: unchanged -- OPEN, TRUE LATENCY
TAIL EVIDENCE REMAINS.** No numeric budget is proposed or adopted -- the
median is now more strongly supported than ever, but the ≥12-sample target
was still not met and the p90 tail, while less divergent than v3 left it,
has not yet converged to a single defensible band. This closure does
**not** authorize another field tranche, External Pre-Release Acceptance,
Final Release Hardening, or any other next development milestone.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, returned here exactly as this milestone's own governing
directive required.

**Corrected 2026-09-07 by Lane R Accumulated Latency Evidence &
Release-Budget Decision v1** (see
[lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md](lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md)),
a bounded, read-only evidence-and-decision milestone, directly authorized
outside this file -- no field session, no deployment, no product/schema
change. HEAD unchanged (`0a776c8`); schema unchanged (`v59`). Pooled all
five intact, live-measured true-latency cohorts to date (v9, v10, v14,
Representative Daylight True-Latency Tail Convergence v3, and v4 -- 69
raw samples across six independent calendar days) and independently
recomputed every statistic directly from raw per-sample data rather than
prose summaries, reproducing every prior published figure exactly except
one: **v10's own report states p90 183.3s; every standard percentile
convention applied to v10's own 11 published per-sample values yields
201.5s instead** -- a disclosed, non-material field-acceptance-report
accounting slip (183.3s is candidate-005's own individual value, not the
90th percentile), never a product defect, and unrepeated in any prior
document's own conclusions since it changes no previously-stated band. A
bootstrap-resampling analysis (a transparent, standard method, not
invented to force a result) found that the per-cohort p90 scatter
repeatedly cited since the 2026-09-05 correction as "non-convergence"
(173.9-385.1s across cohorts) is fully consistent with ordinary
small-sample estimation noise around a single stable underlying
distribution at these sample sizes (9-24) -- every individual cohort's
own observed p90 falls inside its own bootstrap 90% interval computed
from the pooled set. The median remains tightly convergent (pooled
103.9s, bootstrap 90% CI 80.3-114.8s); the pooled p90 itself retains
real, quantified uncertainty (90% CI 198.6-331.8s), not erased by this
finding. Every >300-second sample across every cohort (five in the
primary pooled set, plus v11's reconstructed maximum) was re-confirmed to
trace to the same already-accepted Visit-Continuity/ambiguous-boundary
mechanism -- no new or pathological cause was found; no new perception
investigation was launched. Both explicit v4 acceptance qualifications
were resolved: the 75-minute Observation duration is accurate to the
session driver's own internal accounting (75.000 minutes, 31ms over); a
further ~64-93 seconds of wall-clock footprint is ordinary
stop-dispatch/settlement/snapshot overhead, correctly excluded from the
reported duration; recorder readiness was proven before Observation start
for v4 specifically, for the first time mechanically rather than by
operator attestation. **Classification A -- a specific, narrow,
recommended budget structure (typical latency numeric; upper-tail
qualitative; ceiling architectural, not statistically-fit) is proposed
for external release-authority acceptance, exactly as the recall decision
required.** This report does **not** itself close Lane R or declare Gate
A passed -- it recommends a decision for the next global reconciliation
to accept, correct, or reject, per its own governing directive's explicit
instruction not to self-authorize the recommended next action.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged.

**Corrected 2026-09-07 by Lane R Release-Budget Adjudication & Gate A
Decision v1** (see
[lane-r-release-budget-adjudication-gate-a-decision-v1-report.md](lane-r-release-budget-adjudication-gate-a-decision-v1-report.md)),
a bounded, read-only release-decision milestone, directly authorized
outside this file -- no field session, no deployment, no product/schema
change. HEAD unchanged (`ab48255`); schema unchanged (`v59`).
Independently verified every decisive fact the immediately-prior
milestone's own accumulated-evidence report relied on -- cohort
membership/exclusion rules, the v10 p90 correction (independently
recomputed from v10's own published per-sample table: 201.5s, confirmed by
all five standard percentile conventions), the `target_sample_count: int =
12` per-session stopping heuristic's exact origin in
`scripts/field_acceptance_session_driver.py` (confirmed by direct source
inspection, not a statistical minimum or release-gate requirement), the
bootstrap uncertainty method, every `>300`-second causal classification,
and -- read directly from the rejected report's own primary text, not
only the correction's characterization of it -- the exact two defects
that invalidated the 2026-09-05 Gate A "PASS" (a recall budget stated
verbatim as "excluding the disclosed limitation," and a latency tail table
whose own published max range, "261.2s-307.4s," omits v10's own
already-accepted 742.3-second maximum). No decisive calculation was found
wrong. **This milestone's own accepted budget repeats neither defect**:
recall is not re-touched (already separately closed 2026-09-06, preserved
unchanged), and the adopted latency budget discloses both 742.3s and the
reconstructed 865.2s prominently rather than omitting either. Classification
**A -- GATE A PASS, LANE R CLOSED.** Accepted budget: typical latency
~80-115s (numeric, pooled median 103.9s, bootstrap 90% CI
[80.3s, 114.8s]); upper-tail behavior qualitative, not a tight SLA
(observed per-cohort p90 174-385s; pooled bootstrap p90 90% CI
[198.6s, 331.8s]); a 20-minute (1,200s) architectural decision-horizon
ceiling reference, not a statistically-fit maximum; sustained/crowded
-activity latency disclosed together with the already-accepted recall
limitation as one product characteristic. All eight Gate A dimensions plus
multi-subject correctness now carry an accepted disposition -- see §6.R,
below, for the complete dimension-by-dimension record. This closure does
**not** start External Pre-Release Acceptance or Final Release Hardening
-- both remain separately gated and unauthorized by this milestone -- and
does **not** update `roadmap.md`'s own still-stale Gate A prose, which
this milestone's own governing directive scoped out of its documentation
delta (disclosed explicitly, not silently left inconsistent); reconciling
it is next global-roadmap-reconciliation work. **Authorization remains
NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.

**Corrected 2026-09-07 by Release-Gate Reconciliation & External
Acceptance Preparation v1** (see
[release-gate-reconciliation-external-acceptance-preparation-v1-report.md](release-gate-reconciliation-external-acceptance-preparation-v1-report.md)),
a bounded, read-only release-readiness/governance reconciliation
milestone, directly authorized outside this file -- no field session, no
deployment, no product/schema/tooling code change, no push. HEAD
unchanged (`aeff038`); schema unchanged (`v59`). Verified the expected
baseline exactly: HEAD, schema v59, Lane R `CLOSED`, Lane P `CLOSED`,
current authorization `NONE`, worktree clean except the seven preserved
untracked detector files (reconfirmed present and unmodified), no active
writer. Reconciled `roadmap.md`'s own Gate A / "Numeric release budgets"
prose to the accepted 2026-09-07 Gate A PASS / Lane R CLOSED decision --
explicitly scoped out of *Lane R Release-Budget Adjudication & Gate A
Decision v1*'s own documentation delta and disclosed there as a known gap
(see §6.R, above) -- by appending dated corrections that preserve, not
rewrite, the historical OPEN / rejected-PASS narrative already in
`roadmap.md`, exactly as this file's own convention already treats
superseded narrative. Performed a complete remaining-execution-queue
classification across all nineteen lettered lanes, re-derived from
*Global Product & Release Readiness Reconciliation v2*'s own complete
lane-status table plus the accepted delta since it: **zero new
release-critical dependency found**; Lane R's own closure is the only
material change to that table since v2 (recall, and the six
already-`READY` Gate A dimensions, are unchanged); every remaining
release-critical residual (Lanes L, F, E) is small, already disclosed,
and gated on hardware or external-network access this sandbox cannot
supply, unchanged since v2. Prepared -- without starting -- the concrete
Gate G (External Pre-Release Acceptance) plan named as the last of Gate
G's three entry preconditions in v2's own predecessor report: see
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md).
**This closure does not mark External Pre-Release Acceptance as executed
or passed, does not mark Final Release Hardening as started, and does
not authorize either.** `CURRENT PHASE` remains exactly `FEATURE FREEZE
-- EVIDENCE, RELEASE READINESS & HOUSEKEEPING`. **Authorization remains
NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next
external (ChatGPT) acceptance review to act on.

**Corrected 2026-09-08 by External Acceptance Entry Readiness &
Uninstall Closure v1** (see
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md)),
a bounded release-readiness milestone, directly authorized outside this
file, resolving the two concrete Gate G entry dependencies the
immediately-prior milestone named. HEAD `871c7ba` -> `6cebe0a`; schema
unchanged (`v59`); no product/schema code changed (one packaging-text
constant plus one new regression test); no field session; no deployment
beyond disposable, fully-cleaned-up test instances; no participant
contacted; no push. Verified the expected baseline exactly (HEAD, schema,
Lane R `CLOSED`, Lane P `CLOSED`, Gate G prepared/not started, current
authorization `NONE`, worktree clean except the seven preserved untracked
detector files, no active writer). **Closed the uninstall gap**: bounded
archaeology confirmed it was exactly the documentation-only gap the prior
two milestones believed but had not verified -- the packaged product has
no installer/registry/service footprint, so the application folder and
the local data folder (`%LOCALAPPDATA%\MockingBird`) are already two
separate, independently removable things by construction
(`mockingbird.runtime.resolve_runtime_home`); no new uninstall mechanism
was built or needed. Documented a two-level procedure in
`using-mockingbird.md` (delete the application folder -- safe, preserves
data; separately, explicitly delete the local data folder -- destructive,
permanent); fixed one genuine, small documentation-accuracy defect found
in the in-box `README-FIRST.txt` (the only uninstall documentation an
unpacked end user actually has); added a new dated "Uninstall contract"
phase to `appliance-storage-privacy-recovery-v1-contract.md`; added one
new regression test. **Proved every claim on real native-Windows
hardware**, not merely documented: stopping first is a real, OS-enforced
requirement (`Access to the path 'cv2.pyd' is denied` -- a genuine loaded
-module file lock, not assumed); a failed delete-while-running attempt
does not damage the running installation; deleting the application
folder alone leaves data intact; unpacking a fresh copy at a *different*
path reconnects automatically to the exact same preserved data
(`instance_id` byte-identical before and after); the explicit destructive
step removes both completely. **A real near-miss was caught and
disclosed, not smoothed over**: a bash `$env:` quoting bug in an early
verification check produced a false "absent" reading for the real
`%LOCALAPPDATA%\MockingBird`, which holds genuine leftover data from
prior milestones' own real native-Windows acceptance sessions
(8/9-9/1/2026, the same class of archived-Windows-dev-root evidence
§6.R's own disclosed 18.5GB+ housekeeping item already names -- confirmed
here to also include the production-path variant, not only
`MockingBirdDev`). Caught and corrected before any write or delete
occurred; every subsequent destructive real-hardware operation ran only
against a disposable path via `MOCKINGBIRD_HOME` override (mirroring
`deploy_windows_dev.py`'s own established isolation convention); both
real folders reconfirmed byte-identical -- same files, sizes, timestamps
-- after every step and at final cleanup. Zero operator data was ever at
risk. **Also closed**: `docs/local-mvp-readiness-checklist.md` marked
superseded, dated, historical body preserved unedited (this milestone's
own explicit authorization, resolving consolidated owner-decision #8).
**Prepared, without approving**, a private Gate G cohort/consent/
findings-intake contract (3-5 participants; direct trusted contacts or
relevant communities, no public announcement; explicit written consent;
a private-repository/existing issue mechanism for findings) as a new
addendum to `external-pre-release-acceptance-gate-g-plan-v1.md` --
**nothing in it is approved by this milestone**; no participant
recruited or contacted; no account or private-repository access created.
106 Tier 1 + 388 Tier 2 tests passing, zero regressions; `ruff` clean on
every changed file; full Core deliberately not run (narrow, additive,
documentation-shaped footprint -- see the report's §6 "Tier 3 decision").
**Does not** mark External Pre-Release Acceptance executed or passed,
**does not** mark Final Release Hardening started, **does not** authorize
either, and **does not** reopen Gate A -- see §6.S, below. **Authorization
remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the
next external (ChatGPT) acceptance review to act on.

**Corrected 2026-09-08 by External Pre-Release Acceptance -- Private
Cohort v1** (see
[external-pre-release-acceptance-private-cohort-v1-report.md](external-pre-release-acceptance-private-cohort-v1-report.md)),
a bounded Gate G setup milestone, directly authorized outside this file.
HEAD unchanged (`2fe2729`) until this milestone's own reconciliation
commit; schema unchanged (`v59`); no product/schema/tooling code changed;
no participant contacted; no build distributed externally; no push.
Verified the expected baseline exactly (HEAD, schema, Gate A `PASS`/Lane R
`CLOSED`, Lane P `CLOSED`, Gate G prepared/not started, authorization
`NONE`, worktree clean except the seven preserved untracked files, no
active writer) and directly confirmed zero production code has changed
since the immediately-prior milestone's own real-hardware uninstall proof
(`git diff --stat 6cebe0a..2fe2729` touches only this file). **Built and
independently verified a real, current internal acceptance candidate**
-- not merely cited historical evidence: a full, unskipped
`build_local_product.py` run at HEAD `2fe2729` (`git_commit`
`2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d`, `source_clean: true`) produced
`MockingBird-windows-x64.zip` (18,727 files, 4,922,804,306 bytes); every
MDv5a/BioCLIP-2 asset SHA-256 matched the accepted constants; the
independent `verify_release_artifact.py` passed cleanly; launched on real
native-Windows hardware (Windows 10 Pro `10.0.19045`, RTX 4060 Ti),
`GET /api/product/instance` self-reported the identical `git_commit`/
`build_id` as the build's own manifest; a bounded Local Only TCP
-connection spot-check found no non-loopback connection; restarting
against the same data home after a forceful stop proved recovery
(byte-identical database before/after). **One real, reproducible, non
-release-blocking Doctor defect was found and disclosed, not fixed**: a
fresh instance's Storage check reports `FAIL`/`BLOCKING` from the moment
the server has started even once -- before a participant reaches the
first-run wizard's own Storage step, not after -- because the intended
"not started yet" `PASS` branch is gated on database-file existence, not
wizard completion; root-caused to `_interpret_storage`
(`src/mockingbird/diagnostics/doctor.py`), classified Sev-2, smallest
correction proposed, not implemented (bounded scope). A secondary,
non-blocking observation: neither of the product's own two documented stop
methods produced a shutdown Doctor considers clean -- disclosed, not
escalated, zero data risk. **Prepared all nine required participant
materials** (invitation, written consent, install/first-run/correction
-evidence-trust/backup-recovery-uninstall guides, known limitations,
findings template, withdrawal/data-handling) in a new companion document,
grounded only in already-governed facts, promising no guaranteed species
identification, numeric latency SLA, cloud dependency, or surveillance
capability -- see
[external-pre-release-acceptance-private-cohort-v1-participant-materials.md](external-pre-release-acceptance-private-cohort-v1-participant-materials.md).
**No participant was contacted, recruited, or named; no account or
findings channel was created; no build was distributed.** 507 tests
passing fresh this session, zero regressions; `ruff` clean; full Core
deliberately not run (zero product/schema/tooling code changed). This
milestone **stops at the owner approval checkpoint** its own governing
directive requires (see the report's §5) rather than proceeding to Gate G
execution. **Does not** mark External Pre-Release Acceptance executed or
passed, **does not** mark Final Release Hardening started, **does not**
authorize either, and **does not** reopen Gate A -- see §6.S, below.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, pending the owner approval checkpoint named above before any
external action.

**2026-09-08 update (Release Reliability & First-Run Recovery v1):**
authorized directly by the external (ChatGPT) global-roadmap reconciliation
following its review of the read-only reconciliation at HEAD `d58569f`. See
[release-reliability-first-run-recovery-v1-report.md](release-reliability-first-run-recovery-v1-report.md).
Closed three small, disclosed, non-blocking gaps: the Storage-check false
-`FAIL` disclosed immediately above (root-caused and fixed -- `_interpret
_storage` now also honestly checks whether any real Source has ever been
configured, not raw database-file existence alone); a real graceful-stop
mechanism (new `POST /api/product/shutdown`, Administrator-tier, flips the
real `uvicorn.Server.should_exit` `runtime.py` now publishes on
`app.state`, driving the identical existing teardown a terminal's Ctrl+C
already triggers -- neither prior stop method was changed); and Gate E's
two named Camera Node visibility gaps (storage/media-health,
undervoltage/throttling/temperature), closed for their visibility half via
new `mockingbird_node/hardware_health.py`, degrading `run_startup_self_
test` when critical. **Two real, previously-unknown regressions were
found and fixed by this milestone's own validation, not shipped**: a
test-suite hang (`runtime.py`'s new `Server` construction silently bypassed
two tests' `uvicorn.run` mocks, fixed by mocking `Server.run` instead) and
a Camera Node packaging omission (`hardware_health.py` missing from
`NODE_FILES`, the identical class of gap this manifest has now caught a
third time). All verified on real hardware, not simulated: items 1-2 proven
end to end on real native-Windows hardware (a real process actually exited
after the new shutdown call; the real marker read clean immediately after;
Doctor's Storage check read `PASS` on a genuinely fresh instance); item 3's
parsing verified directly against the real reference Camera Node before
and after being written. Fast gate 1801/1801 passed; Core gate 5969
passed/4 failed/4 skipped/35 deselected/11 xfailed, all four failures
independently confirmed the same long-documented, pre-existing,
environment-sensitive flakes recorded in §14, in files this milestone never
touched. No product/schema/detector/identification-policy change; schema
unchanged (`v59`); no push. **Does not** reopen Gate A, start Gate G, or
start Final Release Hardening, and **does not** self-authorize a
subsequent milestone. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned for the next external
(ChatGPT) acceptance review.

**2026-09-09 update (Product Operations & First-Observation Completion
v1):** authorized directly by the external (ChatGPT) global-roadmap
reconciliation following its acceptance of Release Reliability &
First-Run Recovery v1 at `7b7e282`, schema v59 -- superseding the previous
broad "Hardware & Recovery Acceptance" authorization and the unstarted
"Storage Pressure & Survival Completion" authorization. The sole
authorized implementation milestone; not itself a reconciliation. See
[product-operations-first-observation-completion-v1-report.md](product-operations-first-observation-completion-v1-report.md)
and its own
[contract](product-operations-first-observation-completion-v1-contract.md).
Four parallel investigation agents plus direct governing-doc reading found
three of five scoped areas already substantially complete: the
first-observation product loop (independently re-verified, zero
reproduced defects); storage survival's core mechanics (disk-pressure
ladder, transactional rollback, bounded retention/spool/cleanup-history/
logs -- independently re-confirming Lane M's `CLOSED` status against
direct code evidence, not re-trusting the prior claim). The real, concrete
gaps closed: **Doctor had zero API/UI exposure** (a mature, well-tested,
CLI-only engine) -- new `GET /api/product/doctor` (Administrator-tier,
thin passthrough around the existing, unmodified `run_doctor()`) and a new
`DoctorPage.tsx` (PASS/WARN/FAIL/SKIPPED presentation, calm recovery
-action links to existing Local Data/Cameras surfaces), reachable from
primary nav (Administrator-gated). **Two independent audits converged
unprompted on the identical gap**: Camera Node storage/hardware-quality
facts (shipped by the immediately-prior milestone) never reached a human
anywhere -- closed by a bounded, live, on-demand, non-persisting `GET
/api/streams/{id}/camera-node-hardware-health` (mirrors the existing
"Check the picture" pattern; no schema migration, no change to Doctor's
own read-only/DB-only design invariant), surfaced on the Camera
Configuration page and verified against the real reference Camera Node
(real network I/O; an honest `storage`/`hardware` -> `None` degrade
confirmed for the reference Pi's own currently-installed build, which
predates those fields). **A genuine, reproduced cross-surface honesty
defect, fixed**: three of four surfaces reading
`_camera_health_summary_from_models` disagreed about a
camera-connected-but-detector-failed Camera Node Stream -- the Dashboard
correctly alarmed while Camera Configuration and Yard Map showed a stale
calm "stopped" state for the identical Stream at the identical moment, one
click apart; closed by threading the same `ObservationEngineSessionManager`
bridge `dashboard_summary` alone had into the other two call sites via a
new, single-fetch, behavior-preserving-at-the-original-call-site helper.
`ObservationControlPanel`'s own needs-attention detail box was separately
found hardcoded to the wrong subsystem's message and fixed. Both fixes
were proven RED (failing against the unmodified baseline, via `git stash`
bisection) before GREEN. **One real fault-injection test added**: a
literal `OSError(errno.ENOSPC, ...)` injected at the real Host media-write
function, proving atomic rollback/typed-failure/no-retry through the real,
unmodified persistence path -- closes a branch previously marked
`# pragma: no cover - defensive repository boundary` in production code,
genuinely new coverage. **One real, previously-unknown defect was found
and fixed by this milestone's own Core-gate validation, not shipped**: the
new fault-injection test's own absolute-zero-Visit-count assertion was
wrong (`ProductRepository.__init__` unconditionally seeds two demo Visits
into any fresh database, confirmed by direct root-cause investigation) --
a bug in the new test itself, never in production code; fixed by comparing
before/after counts, re-verified non-vacuous by direct scratch proof.
**Real hardware verification performed, not simulated**: native-Windows
(a genuinely fresh, disposable dev-root, exact commit `5a4858b` confirmed
both by the deploy tool and independently by `/api/product/instance`) --
Doctor's 16 checks returned correctly (`DEGRADED` from one honest
`Application: WARN`, `Storage: PASS` on a fresh unconfigured instance);
the hardware-health endpoint correctly degraded for a non-Camera-Node
Stream; the graceful-shutdown endpoint's real process exit re-confirmed.
The real reference Camera Node's own `/node/v1/health` was queried live
over the LAN. All disposable artifacts cleaned up; the persistent shared
Windows dev deployment and the reference Pi left exactly as found.
Backend Tier 1/2: 337 passed, 0 failed. Full existing + 9 new Playwright
e2e: 184 passed / 2 failed, both independently confirmed pre-existing via
`git stash` bisection against the unmodified baseline --
`reviewed-product-loop.spec.ts` (already long-documented) and a
newly-noticed `notification-preferences.spec.ts` gap (Calm Attention/
Notifications' Place Story deep-link scoping, Lane D territory),
disclosed here for the first time, not fixed, out of this milestone's
bounded scope. `ruff check` zero new findings (confirmed by bisection);
`tsc`/`vite build` clean. Core gate: a first attempt (started 23:56 EDT,
crossing local midnight mid-run) found 6 failures -- 5 individually
confirmed identical against the unmodified baseline or an already
-documented flaky-test file via direct bisection/root-cause tracing, the
6th this milestone's own new-test bug above; a second attempt (same
calendar day) found 5 failures with the bug still present; the accepted,
final attempt, with the test fix applied: **5985 passed / 1 failed
(confirmed pre-existing) / 4 skipped / 35 deselected / 11 xfailed -- zero
failures attributable to this milestone's changes across all three
attempts.** No detector/tracker/identification-policy change; no schema
change (`v59` unchanged); no deletion policy invented or changed; no push.
Implementation commit `5a4858b`. **Does not** reopen Gate A, start Gate G,
or start Final Release Hardening, and **does not** self-authorize a
subsequent milestone. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned for the next external
(ChatGPT) acceptance review.

**2026-09-10 update (Final Release Hardening & Launch Readiness v1):**
authorized directly by the external (ChatGPT) global-roadmap reconciliation
following its acceptance of Product Operations & First-Observation
Completion v1 at classification A, schema v59 -- this project's own last
engineering/hardening pass before the one public release, per this file's
own Lane S framing ("Actual Final Release Hardening," see §6.S, below).
Classification **A**. See
[final-release-hardening-launch-readiness-v1-report.md](final-release-hardening-launch-readiness-v1-report.md)
and
[final-release-hardening-launch-readiness-v1-defect-triage.md](final-release-hardening-launch-readiness-v1-defect-triage.md).
Implementation commit `b3889f8`; schema unchanged (`v59`); no product/
schema/detector/identification-policy code changed anywhere in this
milestone. Verified the expected baseline exactly (HEAD `fa83eec`, schema
v59, Gate A `PASS`/Lane R `CLOSED`, Lane P `CLOSED`, Gate G prepared/not
started, worktree clean except the seven preserved untracked detector
files, no active competing writer -- one other interactive session was
found not marked offline and confirmed idle directly with the user before
proceeding). **Versioning:** bumped the never-revisited "0.1.0"
dev-scaffolding version to "1.0.0" across the existing single-source-of
-truth contract (`pyproject.toml`, both packages' `__init__.py`,
`web/package.json`/lock) -- confirmed independent of the Host<->Camera Node
wire-protocol gate; grepped for stale post-bump literals and fixed one real
hit (`SECURITY.md`'s "pre-1.0" framing, which the bump would otherwise have
made false). **Supply-chain hardening:** new unconditional CycloneDX 1.5
SBOM generation (`generate_release_sbom`, stdlib-only, real installed
-package metadata) and new opt-in GPG release signing
(`sign_release_artifact`, honest unsigned default, no real key exists or
was fabricated -- the complete owner-facing key-generation/publication
procedure is documented, not executed); `verify_release_artifact.py`
generalized to check every `SHA256SUMS` entry, not only the historical zip/
manifest pair. **Documentation:** a dedicated investigation found and fixed
seven real public-documentation gaps (a stale first-run-steps list missing
the Account step; two brand-new, undocumented controls -- the Doctor UI
page and the graceful shutdown control, the latter now the documented
preferred stop method; a dead BirdNET-setup cross-reference; a Camera Node
install guide mislabeled "normal-user" while requiring a repository
checkout; a leaked personal WSL-path/status paragraph in `README.md`,
deleted; a broken `SECURITY.md` policy citation, replaced with three
concrete disclosures). **Defect triage:** a dedicated investigation
compiled 42 previously-disclosed, not-yet-fixed items across every accepted
milestone since 2026-08-24; **zero release blockers**, zero FIX NOW items
taken (every remaining item is an already-disclosed deliberate trade-off,
genuinely out-of-scope, or an environment-sensitive flake); two items
independently reconfirmed already fixed by the immediately-prior two
milestones (Doctor Storage false-`FAIL`; no-clean-shutdown gap), and one
stale memory note ("no login rate-limiting") found already closed by an
earlier accepted milestone. **One item was refined, not fixed, by this
milestone's own real-hardware validation**: Doctor's `Application` check's
"did not shut down cleanly" `WARN` -- already disclosed twice by name as
"an inherent property of running Doctor concurrently with a live
instance" -- was reproduced live on the real built artifact and traced to
its precise mechanism (`runtime.prepare_runtime_state` computes the prior
run's verdict once at boot for a console line, then discards it, so
Doctor's own later read-only re-check of the marker necessarily sees only
`"starting"` for the entire lifetime of any running instance, not a brief
window); a real fix touches the boot sequence, Doctor, and the API surface
together and needs new tests, more than a cheap one-line change, so it
remains a well-scoped, precisely-documented candidate for a small future
follow-up rather than fixed here. **Validation:** 107 packaging/verify
-artifact tests plus a 621-test adjacent sweep, 0 failed; frontend
`tsc`/`vite build` clean; full Core (Tier 3, run once): 5995 passed / 4
failed / 4 skipped / 35 deselected / 11 xfailed, 45m29s, all 4 failures
independently reconfirmed via `git stash` bisection as the identical,
long-documented pre-existing flakes in §14, zero attributable to this
milestone; a full-repo `ruff check .` (never wired into any gate) surfaces
163 pre-existing findings, independently confirmed 100% pre-existing via
the same bisection technique, 0 introduced. **Real hardware, not
simulated:** built both the Host artifact (`MockingBird-windows-x64.zip`,
18,728 files, GPU+BioCLIP runtime included, all required CUDA/cuDNN DLLs
verified present, both model bundles hash-verified) and the Camera Node
artifact from the identical clean commit; independently verified via
`verify_release_artifact.py`; exercised the complete real path (install ->
first run -> Account -> Doctor -> health -> graceful shutdown -> restart ->
data-persistence recovery) on real native-Windows hardware (Windows 10
Pro, RTX 4060 Ti) against the built artifact itself, with three-way
identity confirmation (`build_info.json`/`manifest.json`/the running
instance's own `GET /api/product/instance` all agreeing); confirmed the
real reference Camera Node's wire-protocol/checksum compatibility with the
new artifact via a genuine, non-destructive `--preflight` check (no
upgrade performed, the device's live pairing untouched). No push; nothing
publicly distributed. **Release-readiness verdict: READY FOR OWNER RELEASE
DECISION** (see the report's §9 for the complete owner-only-steps list --
principally: generate/hold a real signing key if signing is desired, and
the actual decision to publish). **Does not** call the product publicly
released, **does not** distribute it, **does not** push, **does not**
self-authorize a subsequent milestone. **Authorization remains NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned for the next
external (ChatGPT) acceptance review and the owner's own release decision.

**2026-09-12 update (Final Candidate Build & Freeze v1 -- ChatGPT accepts
Manual Import Evidence Integrity v1 as classification A):** builds and
freezes the final v0.1.0 release candidate from the current accepted
state; also catches up this file's own stacked log, which had fallen six
real, already-accepted commits behind `main` since the entry directly
above. See §3, below, for the complete delta (Final Release Candidate
Corrections v1, Product Polish & UX Refinement v1/v2, Release Experience
Rehearsal v1, Reviewed Wildlife Semantic Consistency v1, Manual Import
Evidence Integrity v1, and this milestone's own final-artifact build/
verify/smoke record) -- not duplicated here to avoid drift between two
copies of the same facts. HEAD `ee2af65`, schema `v59` unchanged, version
`0.1.0` (not `1.0.0` -- see the version-restoration note in §3's own new
entry). **Authorization remains NONE.**

**2026-09-21 update (Pre-Release Trust & Correctness Correction v1
authorized):** catches up this file's own stacked log a second time --
`2468b91`/`0135801` ("24/7 Field Reliability Corrections v1", 2026-09-16)
were real, accepted, merged commits this file never once mentioned before
now. A definitive read-only baseline audit the same day found three fresh,
high-severity, previously-undisclosed defects (fabricated demo history
shown as real on a fresh install; a broader-than-assumed Doctor media-
integrity false-positive; the shipped Windows launcher silently dropping
`--host`/`--allow-network`) plus six smaller confirmed gaps. The external
(ChatGPT) global release sequencing authorized a bounded defect-correction
milestone closing all of them -- see §3, below, for the complete delta and
the milestone's own eventual closure entry once implemented and validated.
**Authorization: Pre-Release Trust & Correctness Correction v1** (no longer
`NONE`).

**2026-09-21 update (Pre-Release Trust & Correctness Correction v1
accepted; Native-Windows & Packaging Acceptance v1 authorized):** the
external (ChatGPT) global release sequencing accepted Pre-Release Trust &
Correctness Correction v1's own closure entry (§3, below) -- all nine
confirmed 2026-09-21 baseline-audit defects closed, none deferred, Core/e2e
checkpoints clean of any new regression. Accepted HEAD
`f62bb90c786158627394ad62d4d40acbc86007e1`. Directly authorizes the next
milestone: **Native-Windows & Packaging Acceptance v1** -- a
clean-machine/user-acceptance exercise proving the actual generated
MockingBird v0.1 Windows distribution and its documented end-user workflow
work end to end (build reproducibility from clean source; clean
native-Windows install; first launch/Local Only default; runtime
asset/model acquisition; first real Camera Node operation; remote-access
opt-in; diagnostics/failure recovery; backup/restore; update/migration;
uninstall/removal; release-artifact self-consistency) -- explicitly not a
WSL, developer-checkout, source-tree, or hand-prepared-environment claim.
See §3, below, for this milestone's own record once implemented and
validated. **Authorization: Native-Windows & Packaging Acceptance v1** (no
longer Pre-Release Trust & Correctness Correction v1).

**2026-09-22 update (Analytics & Local Data Truth Consistency v1
accepted; UI/UX & First-Run Adoption v1 authorized):** the external
(ChatGPT) global release sequencing accepted Analytics & Local Data Truth
Consistency v1's own closure entry (§3, below). Accepted HEAD
`456277f633df0a1e51821bd00ad8260c42c40244` ("Reconcile release-execution-
state.md and publish the Analytics & Local Data Truth Consistency v1
report"). Directly authorizes the next milestone: **UI/UX & First-Run
Adoption v1** -- the comprehensive pre-release product-experience
milestone (Stage A: a finite, evidence-backed UI/UX defect inventory from
the running product; Stage B: fix every P0/P1 and bounded P2 item it
finds). See §3, below, for this milestone's own record once implemented
and validated. **Authorization: UI/UX & First-Run Adoption v1** (no longer
NONE).

**2026-09-22 update (UI/UX & First-Run Adoption v1 accepted; Performance /
Scale / Stability Closure v1 authorized):** the external (ChatGPT) global
release sequencing accepted UI/UX & First-Run Adoption v1's own closure
entry (§3, below) -- 4 P0 and 16 P1 product-experience defects closed,
Core run twice with zero failures attributable to the milestone's own
changes, and its disclosed protected-file incident non-destructively
remediated (`2549b32`, contents unchanged, no commit rewritten). Accepted
HEAD `3133c64b6a9c49273f5cc57a807240630cab5b7a` ("docs: record the
protected-file remediation in the UI/UX v1 closure report"). Directly
authorizes the next milestone: **Performance / Scale / Stability Closure
v1** -- establishing that v0.1 stays responsive, bounded and recoverable
under realistic first-release workloads (Stage A: credible v0.1 load
profiles plus measured startup, UI/API responsiveness, the flagged
unbounded `GET /api/visits` surface, memory, CPU/GPU, storage growth,
database scale, queue/backpressure, long-run stability, restart/recovery,
optional BirdNET, and native Windows -- producing an evidence-backed
P0/P1/P2/P3 inventory; Stage B: fix every P0/P1 and bounded P2). Release
fitness, not maximum scale: no storage-architecture redesign, no
distributed/cloud infrastructure, no model re-selection, no frontend
rewrite, no Gate G, no push. See §3, below, for this milestone's own
record once implemented and validated. **Authorization: Performance /
Scale / Stability Closure v1** (no longer UI/UX & First-Run Adoption v1).

**Update, 2026-09-23/24, by Review Queue Scale Closure v1:** Performance /
Scale / Stability Closure v1 is implemented but left one release-blocking
P0 open (`GET /api/review-queue` unbounded), so it is **not yet globally
accepted**. **Review Queue Scale Closure v1** was authorized externally as
a bounded continuation to close exactly that P0, and is now implemented
and validated -- see §3. It changes data access, not product meaning: the
tabs, filters, reviewed history, correction flows, counts, demo-source
exclusion and Measured/Inferred/Reviewed boundaries are the accepted ones.
Schema unchanged at `v60`. **Not pushed.** Whether Performance / Scale /
Stability Closure v1 can now be accepted, and whether Field Validation
Closure is next, is the external sequencing decision -- this milestone
authorizes nothing.

## 1. Current accepted state

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`

**Staleness correction, 2026-09-22, by Performance / Scale / Stability
Closure v1:** the note immediately below is superseded. **Current facts,
verified directly this session:** Accepted HEAD
`3133c64b6a9c49273f5cc57a807240630cab5b7a` ("docs: record the
protected-file remediation in the UI/UX v1 closure report"); schema `v59`
unchanged (`CURRENT_DATABASE_SCHEMA_VERSION = 59` in
`src/mockingbird/storage/database.py`, read directly); version `0.1.0`;
latest accepted milestone **UI/UX & First-Run Adoption v1**; current
authorized implementation milestone **Performance / Scale / Stability
Closure v1**. Working tree confirmed clean except the seven preserved
untracked detector files (§13, below) and `uv.lock`, all eight present,
untracked and SHA-256-hashed at session start for re-verification at every
commit boundary. **The UI/UX & First-Run Adoption v1 protected-file
incident (three of the seven briefly tracked from `3f6a49c`) is
remediated** -- commit `2549b32` restored all seven to untracked state
index-only, contents never altered, and `3133c64` recorded the remedy in
that milestone's own closure report; §13's rule stands unchanged and
un-weakened. Writer safety: peer-session and working-tree-mtime checks
performed at session start, and this session recorded its own
single-writer claim in an untracked `.git/MOCKINGBIRD_ACTIVE_WRITER`
marker (inside `.git/`, so never part of the working tree), re-checked
before each commit boundary. This note does not re-derive or rewrite the
notes/history below.

**Staleness correction, 2026-09-22, by UI/UX & First-Run Adoption v1:**
the note immediately below is further superseded. **Current facts,
verified directly:** Accepted HEAD
`456277f633df0a1e51821bd00ad8260c42c40244`; schema `v59` unchanged;
version `0.1.0`; latest accepted milestone **Analytics & Local Data Truth
Consistency v1**; current authorized implementation milestone **UI/UX &
First-Run Adoption v1**. Working tree confirmed clean except the seven
preserved untracked detector files (§13, below) and `uv.lock`, present and
untouched (re-hashed at session start). Writer safety: every peer
MockingBird session found idle/offline and every recent working-tree
mtime predates the accepted HEAD commit; this session recorded its own
single-writer claim in an untracked `.git/MOCKINGBIRD_ACTIVE_WRITER`
marker (inside `.git/`, so never part of the working tree) and re-checks
peers before each commit boundary. This note does not re-derive or
rewrite the note/history below.

**Staleness correction, 2026-09-22, by Analytics & Local Data Truth
Consistency v1:** the note immediately below, and the stacked "Accepted
HEAD" log beneath it, are both further superseded -- accepted HEAD has
moved once since (`6740f71` "Analytics & Local Data Truth Consistency v1:
exclude demo-source activity from Analytics, Local Data, Dataset
Coverage/Quality, and Yard Map"; see `## CURRENT PHASE`, above, and §3,
below, for the complete delta -- this reconciliation's own commit, which
records and publishes this milestone's closure, follows immediately
after). **Current facts, verified directly:** Accepted HEAD
`993d3ef094a5f9f0d7ba2941b25476f1172b9c8b` (unchanged from the note
below -- the acceptance-of-the-immediately-prior-milestone step this
reconciliation itself performs, per §3, has not yet been confirmed by any
*later* milestone, matching this file's own established convention);
schema `v59` unchanged; version `0.1.0`; implementation commit `6740f71`
executes and fully validates **Analytics & Local Data Truth Consistency
v1** (excludes the seeded demo Source's own activity from `Analytics
Summary`/`LocalDataStatus`/`DatasetCoverageSummary`/`DatasetQualitySummary`/
`YardMapActivitySummary` -- see §3); current authorized implementation
milestone `NONE`, pending external (ChatGPT) acceptance of this closure.
Working tree confirmed clean except the seven preserved untracked
detector files (§13, below) and `uv.lock` (pre-existing untracked, not
one of the seven, not touched), present and untouched. **Not a clean
single-writer session throughout -- disclosed here rather than only in
the milestone's own report:** a second Claude session sharing this exact
milestone and working tree was active for part of this reconciliation's
own Tier 3 window; see the closure report's own §R for the complete,
unredacted account. No commit, push, or destructive operation occurred
from either session before this reconciliation's own commits. This note
does not re-derive or rewrite the note/history below, which remains an
accurate historical record through its own last-updated point.

**Staleness correction, 2026-09-22, by Review Queue Count Truth
Consistency v1:** the 2026-09-21 note immediately below, and the stacked
"Accepted HEAD" log beneath it, are both further superseded -- accepted
HEAD has moved once since (`3feab6c` "Reconcile release-execution-
state.md and publish the Native-Windows & Packaging Acceptance v1
report"; see `## CURRENT PHASE`, above, and §3, below, for the complete
delta). **Current facts, verified directly:** Accepted HEAD
`3feab6c3e5bacf6ee45fb7f8067c5049d2813565`; schema `v59` unchanged;
version `0.1.0`; latest accepted milestone Native-Windows & Packaging
Acceptance v1 (two real native-Windows/GPU defects found and fixed --
see §3); current authorized implementation milestone **Review Queue
Count Truth Consistency v1**. Working tree confirmed clean except the
seven preserved untracked detector files (§13, below), present and
untouched; no active writer session found sharing this working tree
(verified directly via this session's own peer-session inventory). This
note does not re-derive or rewrite the note/history below, which remains
an accurate historical record through its own last-updated point.

**Staleness correction, 2026-09-21, by Native-Windows & Packaging
Acceptance v1:** the 2026-09-12 note immediately below, and the stacked
"Accepted HEAD" log beneath it, are both further superseded -- accepted
HEAD has moved twice since (`0135801` "24/7 Field Reliability Corrections
v1", then `f62bb90` "Pre-Release Trust & Correctness Correction v1"; see
`## CURRENT PHASE`, above, and §3, below, for the complete delta). **Current
facts, verified directly:** Accepted HEAD
`f62bb90c786158627394ad62d4d40acbc86007e1`; schema `v59` unchanged; version
`0.1.0`; latest accepted milestone Pre-Release Trust & Correctness
Correction v1 (all nine 2026-09-21 baseline-audit defects closed -- UI-01,
DI-1, PKG-1, PKG-2, FLOW-3, FLOW-5, FLOW-10, DI-2, SEC-2); current
authorized implementation milestone **Native-Windows & Packaging
Acceptance v1**. Working tree confirmed clean except the seven preserved
untracked detector files (§13, below), present and untouched; no active
writer session found sharing this working tree (verified directly via this
session's own peer-session inventory). This note does not re-derive or
rewrite the note/history below, which remains an accurate historical record
through its own last-updated point.

**Staleness correction, 2026-09-12, by Final Candidate Build & Freeze v1:**
the stacked "Accepted HEAD" log immediately below is dated to the Place
Story Deep Dives & Representative Evidence v1 checkpoint (`33d9f5f`) and
was not kept current through the many milestones accepted since -- treat
it as historical narrative, not current state (the same situation §16,
below, already names and corrects for an earlier checkpoint). **Current
facts, verified directly:** Accepted HEAD `ee2af65`
(`ee2af6512d983693def5633cf7fa0b29ab86453c`); schema `v59` unchanged;
version `0.1.0`; latest accepted milestone Manual Import Evidence
Integrity v1; current authorized implementation milestone `NONE`. See
`## CURRENT PHASE`, above, and §3, below, for the complete current picture
and the full delta since `33d9f5f`, including this milestone's own final
release-candidate build/verify/smoke record. This note does not re-derive
or rewrite the stacked history below, which remains an accurate historical
record through its own last-updated point.

- **Accepted HEAD:** `33d9f5f` -- the implementation commit for
  Place Story Deep Dives & Representative Evidence v1 (see
  [place-story-deep-dives-representative-evidence-v1-report.md](place-story-deep-dives-representative-evidence-v1-report.md)
  for the complete record). A deliberately-authorized, one-time, bounded
  product-development reopening -- not a resumption of general product
  development -- directly authorized outside this file, closing two named
  "D -- enrichment" opportunities the immediately-prior Global Remaining
  Product-Development & Release-Queue Reconciliation v1 report had itself
  examined and classified as not required before release: "a dedicated
  taxon/Feature story page" and "representative imagery on Story cards."
  Classification **A**. Schema unchanged (`v59` -> `v59`, no migration):
  archaeology found `GET /api/bird-log/journal/{label}` (Bird Log's own
  existing per-species drill-down) and `GET /api/place/features/{id}/detail`
  (the existing Feature-detail bundle) already carried nearly everything a
  deep-dive header needed, and Place Story's own `taxon=`/`feature_id=`
  filters had worked end-to-end, unused by any page, since Place Story &
  Seasonal Timeline v1 shipped. Two new pages, `TaxonStoryPage.tsx`
  (`/place-story/taxon/:label`) and `FeatureStoryPage.tsx`
  (`/place-story/feature/:id` -- also this product's first dedicated,
  URL-addressable Feature detail page, closing the identically-named gap
  Place Features & Habitat Change v2 and Multi-Camera Place Feature Linking
  v1 had each separately disclosed), compose these already-accepted
  primitives via three (Taxon) or two (Feature) independent fetches each,
  rendered through one shared, extracted card component (`PlaceStoryEntryCard.tsx`,
  behavior-preserving relative to `PlaceStoryPage.tsx`'s own former private
  renderer -- the existing `place-story.spec.ts` suite passes unmodified).
  The one genuinely new backend capability is an additive `taxon` parameter
  on `GET /api/place/year-over-year`, reusing `compute_species_year_over_
  year_comparisons`'s already-computed, previously-discarded full per-taxon
  result (proven to add zero extra queries); the other is `PlaceFeatureDetail
  .representative_evidence`, a new additive field built on the canonical
  Gate C selector (`select_representative_evidence`) completely unmodified
  -- only the Feature-scoped, multi-camera-aware, cross-camera-deduplicated
  candidate-gathering path is new (`_feature_representative_evidence`,
  sharing a newly-extracted, behavior-preserving query core, `_feature_
  scoped_visit_rows`, with the pre-existing Feature yield/before-after
  computation). Every abstention path required (no observation links, no
  confirmed wildlife Visit in scope, a Visit outside the Feature's own
  scope, a missing media file, an archived linked camera) is proven directly
  with a dedicated regression test, not merely designed. Two real,
  previously-nonexistent-until-this-milestone defects were found by this
  milestone's own query-count measurement discipline and fixed before
  shipping: an N+1-shaped inefficiency in the first representative-evidence
  implementation (built a full Visit summary for every historical row
  before bounding to the most-recent 20 confirmed candidates, instead of
  after -- fixed by scanning most-recent-first with an early exit,
  behaviorally identical final selection, proven by a dedicated query-count
  test at 25 vs. 50 of a Feature's own confirmed Visits); and a redundant
  taxonomy-table re-scan in the first `taxon=` year-over-year implementation
  (fixed by reusing the caller's already-fetched `taxonomy_index`, proven
  by a dedicated zero-extra-queries test). Deep links wired at every
  location the governing brief named: Place Story's own entry actions (a
  new "{name}'s story" action, additive alongside the existing Bird Log
  link; a Feature-linked entry's action becomes "{name} story", replacing
  its former "View in Place Report" fallback for that one case only), Bird
  Log's per-species header (a new "See {name}'s story" link),
  `PlaceFeaturesCard`'s calm-view feature tags (now clickable, optional
  prop, backward compatible), `PlaceActivityReportPage`'s inline Feature
  expand (a new "View {name} story" action), the Year-over-Year card
  (`onOpenTaxonStory` as the primary per-species action, its existing Bird
  Log link kept as a second explicit action), and Calm Attention's
  `open_place_story` action (now routing precisely to a taxon's/Feature's
  own Story when the underlying attention signal already names one --
  `taxon_label`/`feature_id` were already flowing to the frontend, unused
  until now -- falling back to the pre-existing category-group scoping only
  when neither is present; not a Web Push/attention-persistence/per-user-
  read-state reopening). A real, comprehensive product-shaped scenario (two
  taxa, one two-camera Feature, two years of history, a deleted evidence
  file, a real cross-camera duplicate encounter, camera rename/archive, a
  Reviewed correction, all under an enforced Local Only guarantee) proves
  the whole chain coheres end to end: a Taxon Story that never leaks a
  different taxon's events; a Feature Story with exactly one change entry
  despite two linked cameras and zero per-Visit wildlife entries; a real
  year-over-year material increase narrated for one taxon specifically;
  representative evidence that skips a deleted file honestly and survives
  camera rename/archival; and a Reviewed correction removing the winning
  representative-evidence Visit from eligibility on the very next read, no
  invalidation step. 19 new focused backend tests (11 in `test_place_
  feature.py`: 8 representative-evidence correctness/abstention + 1 HTTP
  round trip + 2 performance, bringing that file from 86 to 97 tests; 8 in
  `test_year_over_year_comparison_repository.py`: 5 taxon-comparison + 2
  HTTP round trip + 1 performance, bringing that file from 25 to 33 tests)
  plus the one product-shaped scenario, all passing; directly-affected re-run (`test_place_story.py`,
  `test_place_story_repository.py`, `test_year_over_year_comparison.py`,
  `test_year_over_year_product_shaped_scenario.py`, `test_multi_camera_
  place_feature_linking_scenario.py`) 221 passed / 0 failed; `ruff check`
  zero new findings, proven by a message-level diff against a `git stash
  push -u`-isolated clean baseline; `tsc --noEmit`/`vite build` clean (109
  modules, both new pages correctly code-split); 17 new Playwright e2e
  tests (both pages: direct route, reload, invalid id, sparse state,
  representative image + alt text, deep-link click-through, phone width,
  keyboard focus-management) all passing; 78 directly-adjacent existing
  e2e specs (`place-story`, `place-features`, `year-over-year`, `bird-log-
  historical-status`, `mobile-viewport-audit`, `today-report`) re-run and
  passing, zero regressions from the `PlaceStoryEntryCard` extraction or
  the new optional props/response fields. Full Core (`scripts/verify_
  core.py`) 5875 passed / 1 failed / 3 skipped / 23 deselected
  (slow-marked) / 11 xfailed (42m57s) -- the one failure
  (`test_place_change_summary_repository.py::test_api_round_trip_exposes_
  change_detection_fields`) independently re-confirmed pre-existing and
  unrelated via a fresh `git stash push -u` bisection against this exact
  starting commit (byte-identical failure), the same already-documented
  flakiness class Multi-Camera Place Feature Linking v1's own Core run
  also hit on this identical commit. Starting state verified exactly as expected:
  HEAD `973cb5e`, schema `v59`, Lane P `CLOSED`, Lane R `OPEN -- RELEASE-
  CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS` (untouched), authorization
  `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`. Worktree safe:
  no active writer, all seven preserved untracked detector files present
  and unchanged. **This closure does not reopen any other lane, does not
  authorize a second product-development milestone, and does not change
  Lane R or Lane P.** `CURRENT PHASE` returns unchanged to `FEATURE FREEZE
  -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING`. **Authorization remains
  NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next
  external (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-Place-Story-Deep-Dives-Representative-Evidence-v1):** `3cce9e4` -- the implementation commit for
  Multi-Camera Place Feature Linking & Cross-View Habitat Context v1 (see
  Multi-Camera Place Feature Linking & Cross-View Habitat Context v1 (see
  [multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md](multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md)
  for the complete record). A deliberately-authorized, one-time, bounded
  product-development reopening -- not a resumption of general product
  development -- directly authorized outside this file, closing the
  "multi-camera Feature linking" gap Place Features & Habitat Change v2's
  own Phase 28 named and Multi-Camera Place Experience v2 investigated and
  deferred: a Place Feature can now be linked to zero, one, or many
  camera/Zone observation views ("these cameras are different views of the
  same thing"), not just one. Classification **A**. Schema `v58` -> `v59`:
  one new additive-and-backfilled table, `place_feature_observation_links`
  (own id, required `source_id` -- deliberately matching
  `PlaceFeatureModel.source_id`'s own existing FK target rather than the
  governing brief's own literal `stream_id` candidate naming, so an
  existing Feature's association migrates with zero translation --
  optional `zone_id`, the identical information_class/provenance/
  actor_user_id provenance quartet `PlaceFeatureModel` already carries, and
  two partial unique indexes correctly preventing a duplicate view despite
  the nullable `zone_id`, which a plain `UniqueConstraint` cannot do in
  SQLite). `PlaceFeatureModel.source_id`/`zone_id` become a
  repository-maintained compatibility mirror (populated only when a
  Feature has exactly one link, honestly `NULL`/`NULL` for zero or many),
  not the source of truth; every migrated single-link Feature reads back
  byte-identical to its pre-migration self, proven directly by a real
  v58-simulated database backfill test. Two new endpoints
  (`POST`/`DELETE .../observation-links`) add or remove a view
  incrementally; the legacy `PlaceFeatureUpdate.source_id`/`zone_id`
  fields are preserved, explicitly redefined as a documented
  full-replacement compatibility operation, never a silent one.
  Cross-view analytics reuse two already-accepted primitives completely
  unmodified -- `_associated_visit_ids_to_exclude_from_counting` (one real
  encounter recorded by two linked cameras counts once, proven directly
  with a real cross-camera-confirmed pair) and `_place_activity_coverage_
  summary` (coverage is a real elapsed-time union across linked views,
  never a sum, proven with real overlapping-interval numbers) -- never a
  second duplicate-counting or coverage engine. Place Story required zero
  changes: Feature change events were already Feature-centered, not
  camera-centered. Two real, pre-existing defects found and fixed along
  the way, beyond what this milestone strictly required: a bare-Source
  Feature association went silently quiet the instant its one camera was
  archived, unlike an otherwise-identical Zone-linked association (both
  now correctly stay reachable, matching "archiving preserves history"
  doctrine); and `delete_zone`'s reference guard had no check at all for a
  Zone referenced only by a Place Feature link, a real dangling-reference
  risk. A real, measured, avoidable N+1-shaped re-fetch of a Feature's own
  link rows once per change event (found by this milestone's own
  query-count measurement discipline, not assumed) was fixed by threading
  one up-front link fetch through the whole detail-bundle computation,
  confirmed safe by an identical passing-test re-run before and after.
  36 new backend tests (`test_place_feature.py`: 50 -> 86) plus one
  comprehensive product-shaped scenario test (two linked cameras,
  cross-camera dedup, independent-encounter preservation, coverage union,
  camera rename/archive safety, Reviewed-correction propagation, all under
  an enforced Local Only guarantee) plus one new schema-migration test;
  462 passed / 0 failed across the full directly-adjacent-subsystem sweep
  plus the complete `test_persistence.py` migration suite, re-run against
  the truly final code; full Core (`scripts/verify_core.py`) 5,854 passed /
  1 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
  (57m23s) -- the one failure independently re-confirmed pre-existing and
  unrelated via a fresh `git stash push -u` bisection against this
  milestone's own exact starting commit (a new sighting of the same
  already-documented "fixed test date drifting against real wall-clock
  time" flakiness class this codebase's own validation baselines already
  record for a sibling test file); `ruff check` zero new findings, proven
  by a message-level diff against a `git stash`-isolated clean baseline,
  twice; `tsc --noEmit`/`vite build` clean; 12/12 new/updated Playwright
  e2e tests passing (7 pre-existing + 5 new) plus 68/68 directly-adjacent
  existing e2e specs re-run and passing. Starting state verified exactly
  as expected: HEAD `2771d4c`, schema `v58`, Lane P `CLOSED`, Lane R
  `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`
  (untouched), authorization `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`. Worktree safe: no active writer, all seven
  preserved untracked detector files present and unchanged. **This
  closure does not reopen any other lane, does not authorize a second
  product-development milestone, and does not change Lane R or Lane P.**
  `CURRENT PHASE` returns unchanged to `FEATURE FREEZE -- EVIDENCE,
  RELEASE READINESS & HOUSEKEEPING`. **Authorization remains NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external
  (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-Multi-Camera-Place-Feature-Linking-Cross-View-Habitat-Context-v1):** `a83b4e3` -- the implementation commit for
  Year-over-Year Seasonality & Long-Term Place Memory v1 (see
  [year-over-year-seasonality-long-term-place-memory-v1-report.md](year-over-year-seasonality-long-term-place-memory-v1-report.md)
  for the complete record). A deliberately-authorized, one-time, bounded
  product-development reopening -- not a resumption of general product
  development -- directly authorized outside this file, building
  MockingBird's first true year-over-year Place comparison ("how does this
  season compare with the same time last year") and closing the gap
  `seasonal_pattern.py`'s own docstring, the Place / Yard Intelligence v2
  report, and the immediately-prior Global Remaining Product-Development &
  Release-Queue Reconciliation v1 report all independently named as the
  honest ceiling of every existing seasonality primitive (a single
  trailing 366-day window that resets, never accumulates across years).
  Classification **B**. Zero schema change (`v58` unchanged); one new pure
  analytics module (`mockingbird.analytics.year_over_year_comparison`)
  composed entirely over the already-accepted `conditional_association`
  primitive (comparable-period boundaries shift by whole calendar years,
  never a fixed 365/366-day timedelta, with a documented deterministic
  Feb-29 rule; coverage/effort normalization reuses the existing
  presence-day-rate convention `place_change_summary`/`seasonal_pattern`/
  `habitat_association` already established, proven directly immune to a
  raw-monitored-hours skew); species-level comparison covers normalized
  activity difference and first-observed-timing difference ("first
  observed here", never "arrived"), ranked by evidence strength and
  bounded to 5, never raw percent change. One pre-existing repository
  helper (`_historical_usable_dates`) extracted, not behaviorally changed,
  into a window-parameterized sibling -- all 6 of its own pre-existing
  call sites' full test coverage passes unmodified. New
  `GET /api/place/year-over-year`; a new `YearOverYearCard` on both
  Dashboard and the Place Report page; a new Place Story `year_over_year`
  event kind, gated to compute only when a Story request's own range
  includes "now" (measured isolated marginal cost: -4.9ms, noise-level).
  Multi-camera duplicate safety, archived-Stream reachability, and
  Reviewed-correction propagation proven directly (repository tests plus a
  real product-shaped 2-camera/2-year end-to-end scenario that also proves
  Local Only by patching `socket.socket.connect` to raise for its entire
  duration); a real measured performance proof (~18ms per call against a
  synthetic 3-year/1,644-Visit history, query count unchanged after
  seeding three additional unrelated years). 64 new backend tests plus 18
  new tests across the two Place Story test files, all passing; a broader
  Tier 2.5 sweep across every directly-affected subsystem at 677 passed /
  1 failed (the one failure independently re-confirmed pre-existing and
  unrelated via a fresh `git stash push -u` bisection against this
  milestone's own exact starting commit -- `test_place_change_summary_
  repository.py::test_api_round_trip_exposes_change_detection_fields`,
  already documented in prior sessions' memory); `ruff check` zero new
  findings, proven by a message-level diff against a `git stash`-isolated
  clean baseline; `tsc --noEmit`/`vite build` clean; 7/7 new e2e tests plus
  23/23 directly-adjacent existing e2e specs re-run and passing. Three real
  defects found and fixed during this milestone's own development, never
  shipped: a `has_any_monitoring_history` scoping gap (conflated "history
  exists ever" with "history reaches back to this period's own end",
  caught by this milestone's own `test_no_prior_year_history_at_all`); a
  Pydantic Literal type mismatch on the new association status (`Place
  YearOverYearAssociation` needed the full `insufficient_data`-inclusive
  range, not `PlaceFeatureAssociation`'s narrower one); and a missed
  schema-level mirror for the new Story event kind (added to the pure
  analytics module's own `PlaceStoryEventKind` but initially missed in
  `schemas.py`'s mirrored copy, then also missed on the frontend's own
  `PlaceStoryPage.tsx` group/label maps) -- each caught immediately by a
  real `pydantic_core.ValidationError` or TypeScript compile error in the
  very first end-to-end integration test/build, none shipped. No live
  production proof of a `"comparable"` (material-difference) outcome
  exists yet -- checked directly against this
  repository's own real, unmodified local development database, which
  honestly reports `insufficient_prior_history` today, since no real
  installation has a full year of accumulated field history anywhere yet;
  this is the identical, unavoidable "blocked on elapsed real history, not
  engineering" constraint the immediately-prior reconciliation already
  named, not a defect of this milestone's own engineering. Starting state
  verified exactly as expected: HEAD `c07171b`, schema `v58`, Lane P
  `CLOSED`, Lane R `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
  REMAINS` (untouched), authorization `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`. Worktree safe: no active writer, all seven
  preserved untracked detector files present and unchanged. **This closure
  does not reopen any other lane, does not authorize a second product-
  development milestone, and does not change Lane R or Lane P.**
  `CURRENT PHASE` returns unchanged to `FEATURE FREEZE -- EVIDENCE, RELEASE
  READINESS & HOUSEKEEPING`. **Authorization remains NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external
  (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-Year-over-Year-Seasonality-Long-Term-Place-Memory-v1):** `1709bf3` -- the implementation commit for
  Environmental Context x Place Story & Habitat Change Composition v1 (see
  §3, below, and
  [environmental-context-place-story-habitat-change-composition-v1-report.md](environmental-context-place-story-habitat-change-composition-v1-report.md)
  for the complete record). A deliberately-authorized, one-time, bounded
  product-development reopening -- not a resumption of general product
  development -- directly authorized outside this file, closing the
  explicitly-named "compose environmental-context/weather caveats onto a
  before/after result" gap both Place Features & Habitat Change v2 and
  Place Story & Seasonal Timeline v1 recorded as deferred. Classification
  **A**. Zero schema change (`v58` unchanged); one new pure analytics
  module, one additive API field, one frontend line, zero new database
  columns/tables. Starting state verified exactly as expected: HEAD
  `d3b9820`, schema `v58`, Lane P `CLOSED`, Lane R `OPEN -- RELEASE-CRITICAL
  -- TRUE LATENCY TAIL EVIDENCE REMAINS` (untouched), authorization `NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`. Worktree safe: no active
  writer, all seven preserved untracked detector files present and
  unchanged. See §3, below, for the complete implementation record. **This
  closure does not reopen any other lane, does not authorize a second
  product-development milestone, and does not change Lane R or Lane P.**
  `CURRENT PHASE` returns unchanged to `FEATURE FREEZE -- EVIDENCE, RELEASE
  READINESS & HOUSEKEEPING`. **Authorization remains NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external
  (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-Environmental-Context-x-Place-Story-Habitat-Change-Composition-v1):** `bdfa35f` -- the implementation commit for MIT Source
  License Adoption & Lane P Mechanical Closure v1 (see §3, below, and
  [mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md](mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md)
  for the complete record). Bounded feature-freeze housekeeping milestone,
  directly authorized outside this file, performing exactly the mechanical
  follow-through the immediately-prior reconciliation named and
  deliberately did not perform. Classification **A**. Zero product/schema/
  Core code changed; confined to a new root `LICENSE` file, `pyproject.
  toml`/`web/package.json` license metadata, one new packaging function
  (`package_license` in `scripts/build_local_product.py`, mirroring
  `package_third_party_notices` exactly) and its dedicated tests, `README.
  md`'s "License" section, `THIRD_PARTY_NOTICES.md`'s own two self-
  referential sentences about MockingBird's own license status (no third-
  party fact touched), and one small `roadmap.md` Gate F staleness
  correction. Verified starting state exactly as expected: HEAD `9eaa6e0`,
  schema `v58`, worktree safe (all seven preserved untracked detector files
  present and untouched). **Owner's MIT decision (already recorded resolved
  by the immediately-prior reconciliation) is now mechanically adopted**: a
  real `LICENSE` file exists (standard MIT text; copyright `MockingBird
  contributors` -- the narrowest formulation this repository's own text
  already established, `THIRD_PARTY_NOTICES.md`'s pre-existing "MockingBird
  is written by its own contributors," used because a single individual git
  identity is not by itself a defensible legal copyright-holder string and
  no company/organization name exists anywhere in the repository);
  `pyproject.toml` carries modern PEP 639 SPDX metadata (`license = "MIT"`,
  `license-files = ["LICENSE"]`), which required raising the `hatchling`
  build-system floor from `>=1.24` to `>=1.27` -- empirically verified
  against a real version matrix that 1.24-1.25 reject `license-files` as an
  array outright, 1.26 accepts it but silently omits the modern `License-
  Expression`/`License-File` metadata fields, and 1.27 is the first version
  confirmed to emit both correctly (Metadata-Version 2.4); `web/package.
  json` gained a matching `"license": "MIT"` for consistency. Distribution
  inclusion proven, not assumed: a real `pip wheel .` build of this exact
  repository (the identical command `build_wheel()` runs) produced a real
  `mockingbird-0.1.0-py3-none-any.whl` whose `METADATA` carries `License-
  Expression: MIT`/`License-File: LICENSE` and whose `mockingbird-0.1.0.
  dist-info/licenses/LICENSE` is byte-identical to the repository's own
  file; the official Windows bundle additionally gained an explicit
  `package_license` step copying `LICENSE` to the bundle root, visible
  alongside `THIRD_PARTY_NOTICES.md`, since the wheel's own automatic
  `dist-info/licenses/` copy lands buried in `python/site-packages/` where
  an end user unpacking the release folder would not find it.
  `README.md`'s "License" section no longer says the decision "has not yet
  been finalized"; it states MIT plainly, points to `LICENSE`, and
  continues to point to `THIRD_PARTY_NOTICES.md` for third-party terms
  without implying they are all MIT. `THIRD_PARTY_NOTICES.md`'s own two
  self-referential sentences were corrected to match; every third-party
  fact in that file (MDv5a/BioCLIP-2 provenance, ffmpeg non-bundling,
  BirdNET/birdnetlib NC-model exclusion, both build-time guards) is byte-
  for-byte unchanged, re-confirmed directly. 7 new tests plus 2 new
  assertions in the canonical `tests/test_local_product_packaging.py` (81
  passed, 4 pre-existing slow-marked tests correctly deselected, 0 failed);
  `ruff check` clean on every changed Python file; `tests/test_version_
  provenance.py` (4 passed) as an adjacent sanity check. Tier 2/3: not run
  -- every changed file is packaging/documentation-only with zero importers
  anywhere in `src/mockingbird/`, the identical reasoning already applied
  to every prior packaging-tooling-only milestone. **Lane P: CLOSED --
  RELEASE-CRITICAL LICENSING/DISTRIBUTION REQUIREMENTS COMPLETE** (see
  §6.P, below) -- the BirdNET commercial-adjacent legal posture (§2, above)
  remains a separate, standing legal-review item, not reopened or newly
  blocking here, and does not keep this lane's own mechanical
  license/distribution scope open. This closure does **not** authorize
  External Pre-Release Acceptance, Final Release Hardening, the next Lane R
  daylight tranche, or any product-development milestone. **Authorization
  remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
  returned here exactly as this milestone's own governing brief required,
  for the next external (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-MIT-Source-License-Adoption-Lane-P-Mechanical-Closure-v1):** `9c4f8d5` -- the report commit for Global Remaining
  Product-Development & Release-Queue Reconciliation v1 (see §3, below,
  and
  [global-remaining-product-development-release-queue-reconciliation-v1-report.md](global-remaining-product-development-release-queue-reconciliation-v1-report.md)
  for the complete record). Documentation/governance reconciliation,
  directly authorized outside this file as the standing response to this
  file's own long-running `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED` gate. Classification **A**. Zero product/test/schema code
  changed. Read `release-execution-state.md`, `product-doctrine.md`, and
  `roadmap.md` in full (not sampled) and walked every lane A-S against
  direct repository evidence rather than recent session-scoped focus on
  Lane R alone. Verified the conversation-side expected starting state
  (branch, HEAD `b3dba92`, schema v58, Gate A/Lane R/recall/authorization)
  an exact match to the repository, and worktree safety (the seven
  preserved untracked detector files) unchanged. Found and corrects three
  stale lane entries: Lane A's remaining-work list still named a
  "frontend acoustic health/status" gap that Whole-Product UI /
  Accessibility / Performance Closure v1 (2026-08-27) had already closed
  by name; Lane E's remaining-work list still named a `ReviewQueuePage`
  `product_category` gap and a login-rate-limiting gap that Whole-Product
  UI / Accessibility / Performance Closure v1 and Login Rate-Limiting &
  Authentication Abuse Resistance v1 had each already, separately closed.
  Confirmed Lane G's `CLOSED -- RELEASE-CRITICAL` status (2026-09-03) is
  itself already current and not stale -- the thing that was behind was
  this session's own persisted memory, one milestone short; repository
  evidence, not memory, governs. Records the owner's new, explicit MIT
  source-code-license decision (Lane P) as **resolved**, distinct from
  the still-pending mechanical adoption: empirically verified this
  session that no `LICENSE` file exists, `pyproject.toml`/
  `web/package.json` carry no license metadata, and `README.md`'s own
  "License" section still says the decision "has not yet been finalized"
  -- named as a small, bounded next action, deliberately not performed in
  this reconciliation itself, per its own governing brief's explicit
  instruction not to perform the follow-through unless necessary to make
  the scheduler truthful (it is not -- Lane P's own text below already
  states the decision is resolved and the adoption is pending). Applied a
  five-question product-opportunity test (core-loop value; would a first
  public user perceive its absence as unfinished; completes a shipped
  concept vs. starts a new lane; pre-freeze dependency/risk; new
  correctness surface) to every remaining opportunity `roadmap.md` and
  this file's own §6 name -- year-over-year seasonality (mechanically
  blocked on elapsed real history, not engineering), weather-on-before/
  after composition, multi-camera Place Feature linking, ranked Feature
  comparison, Place Story period summaries (explicitly deferred on a
  measured performance cost -- a real pre-freeze risk argument, not a
  reason to rush it), dedicated taxon/Feature story pages, representative
  Story-card imagery, environmental historical backfill, and a
  consolidated "Explore" page (`roadmap.md` Layer 6, considered and
  rejected as a navigation nicety over already-surfaced capability, not a
  missing one) -- and found **none clears the bar for substantial product
  development before release**; fewer than three genuinely qualify, and
  this reconciliation does not invent work to keep a development label
  populated. **Feature-freeze decision: C -- MockingBird is functionally
  at feature freeze already** (see `CURRENT PHASE`, above, corrected
  accordingly): every layer of `roadmap.md`'s own "Remaining roadmap --
  canonical sequence" (Layers 1-8) shows substantial accepted delivery,
  and every lane A-S here is closed, materially closed/advanced/
  delivered, frozen, or decision-closed except Lane R (a validation gap,
  daylight-dependent, explicitly **not** scheduled by this reconciliation
  -- no new Gate A investigation opened) and Lane P's now-small mechanical
  remainder. BirdNET's own commercial-adjacent legal posture (§2, below)
  is reconciled to **B+D**: blocks only commercial-adjacent use of the
  optional acoustic feature, not all public launch, and has no available
  engineering action -- a standing legal-review item. External
  Pre-Release Acceptance and Final Release Hardening readiness criteria
  are stated (see the linked report); neither is authorized. **No
  substantial product-development milestone is recommended** -- the one
  small, independent, advisory-only next action named is Lane P's own
  bounded mechanical LICENSE/packaging-metadata adoption, not a product
  capability milestone, not self-authorized here. This closure does
  **not** authorize External Pre-Release Acceptance, Final Release
  Hardening, the next Lane R daylight tranche, another Gate A
  investigation, or any product-development milestone -- see §3, below,
  for the complete reconciliation entry. **Authorization remains NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external
  (ChatGPT) acceptance review to act on.
- **Prior accepted HEAD (pre-Global-Remaining-Product-Development-Release-Queue-Reconciliation-v1):** `a7f879f` -- the report commit for Representative
  Daylight True-Latency Tail Convergence v2 (see §3, above, and
  [representative-daylight-true-latency-tail-convergence-v2-report.md](representative-daylight-true-latency-tail-convergence-v2-report.md)
  for the complete record). Bounded RELEASE-CRITICAL Lane R evidence
  milestone, directly authorized outside this file, whose sole purpose was
  one additional intact, genuinely daylight, current-stack RTT-normalized
  T0->T5 latency distribution large enough to evaluate tail convergence.
  Classification **B**. Zero production code changed; zero new latency
  samples; zero deployment. The governing brief's own hard daylight gate
  (its §4) failed before any field tranche could be attempted: local
  wall-clock time was 21:26-21:29 EDT on 2026-09-05, cross-checked via two
  independent clocks (the sandbox and the native Windows host via
  `powershell.exe`, the identical method v10 and v14 both used as their
  own daylight proof) -- roughly 1.5-1.7 hours past civil twilight end,
  unambiguous night. Per the brief's own explicit instruction for this
  case, no fresh instance was deployed, no Camera Node pairing or RTT
  preflight was attempted, and no Observation was opened -- only bounded,
  read-only readiness checks (reference Camera Node confirmed reachable
  on the LAN via ping and an open TCP 8787; no pairing/deployment
  attempted). The existing qualifying latency body was re-confirmed
  exactly from source and is unchanged: three intact, live-measured
  cohorts (v9 n=24, 111.8/173.9/307.4s; v10 n=11, 103.9/183.3/742.3s; v14
  n=14, 82.9/235.5/261.2s) plus one supporting/reconstructed cohort (v11
  n=23, 115.7/318.5/865.2s, not equivalent to an intact cohort) -- no
  fifth qualifying sample added, tail still spanning 261.2-865.2s with no
  convergence. **Gate A decision: OPEN -- TRUE LATENCY TAIL EVIDENCE
  REMAINS**, unchanged. Lane R remains `OPEN -- RELEASE-CRITICAL -- TRUE
  LATENCY TAIL EVIDENCE REMAINS` (see §6.R, below), unchanged. No
  correctness defect found; nothing patched; nothing deployed. This
  closure does **not** authorize another field tranche, External
  Pre-Release Acceptance, Final Release Hardening, or any other next
  development milestone -- see §3 for the complete reconciliation entry.
  `roadmap.md` intentionally left unchanged (no latency budget or Gate
  A/Lane R final state was accepted this milestone, per its own §27).
- **Prior accepted HEAD (pre-Representative-Daylight-True-Latency-Tail-Convergence-v2):** `b6b4727` -- the report commit for Gate A
  True-Latency Tail Closure & Final Lane R Decision v1 (see §3, above, and
  [gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md](gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md)
  for the complete record). Bounded RELEASE-CRITICAL Lane R
  field-measurement and final-decision milestone, directly authorized
  outside this file. Documentation/reconciliation only, zero production
  code changed (one factual crowded-activity limitation sentence added to
  `using-mockingbird.md`'s "Review" section). Classification **B**.
  Reconciles the global recall release-authority decision (supplied by
  ChatGPT) into the scheduler for the first time -- whole-scene recall is
  now **ACCEPTED KNOWN LIMITATION, no numeric floor** -- and runs the
  smallest sufficient live latency-tail proof the immediately-prior
  correction called for: a fresh disposable instance at that milestone's
  own accepted HEAD (`bf7ee89`), a valid 5/5-sample RTT-bounded Camera
  Node calibration, and 100%/100%/100% ledger reconciliation, but the
  live tranche itself produced only n=1 valid latency sample (of a
  required ≥12) before an honest, disclosed stop -- the session started
  at dusk, and scene-wide raw-detection activity (both animal- and
  vehicle-class) is shown, quantified from the session's own ledger, to
  have collapsed together from minute ~15 as real darkness set in,
  confirmed in real time. The one sample obtained is further judged,
  independently, likely not a real animal on direct visual review (an
  unmoving shape at one exact feeder-perch position across 2+ minutes of
  independent-recorder frames, consistent with a static feeder component
  marginally misclassified under difficult low light) -- disclosed, not
  counted toward tail convergence. **Gate A decision: OPEN -- TRUE
  LATENCY TAIL EVIDENCE REMAINS** (narrowed from "OPEN -- RELEASE
  DECISION REQUIRED": recall's own decision is now made; latency's tail
  convergence is the sole remaining blocker). Lane R narrows to `OPEN --
  RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS` (see §6.R,
  below). No correctness defect found; nothing patched live. This
  closure does **not** authorize External Pre-Release Acceptance, Final
  Release Hardening, another field cohort, or any other next development
  milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-Gate-A-True-Latency-Tail-Closure-Final-Lane
  -R-Decision-v1):** `e57c911` -- the report commit for Authenticated
  Camera Node Golden-Path Capture & Preview Acceptance v1 (see §3, below,
  and
  [authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md](authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md)
  for the complete record). Lane G hardware-validation milestone
  (directly authorized outside this file), release-critical,
  validation-focused with one bounded two-part Camera Node fix. Traced
  the reference Camera Node's orphaned pairing credential (unresolved by
  the immediately-prior milestone) to an archived, dormant Representative
  Daylight field-acceptance instance (`MockingBirdFieldAcceptanceV11`) by
  SHA-256 digest comparison and safely revoked it through the real,
  unmodified `CameraNodeClient.revoke()` production path -- the first
  session on record to recover a dormant credential via the authenticated
  path rather than a manual `pairing.json` edit. Deployed the previously
  -accepted `V4L2CameraProvider` diagnostic-truth fix (`ca98fc6`, never
  live-deployed in its own milestone) to the real reference Pi via the
  existing installer, which immediately exposed a second, real,
  previously-unknown gap in the same diagnostic: `isOpened()` alone is
  insufficient ground truth for "capture capable" -- this Pi's
  `bcm2835-isp` internal ISP pipeline-stage nodes can accept a V4L2
  `open()` while never delivering a frame. Fixed (a bounded read-check,
  same file/pattern as the first fix) together with the timing
  consequence that fix's own real-hardware enumeration cost exposed in
  self-test's fixed timeout, before any further validation proceeded
  (implementation commit `4c1be35`, RED->GREEN, 361 passed / 0 failed
  across the full Camera Node subsystem, 0 new `ruff` findings, Tier 3
  correctly not run -- identical bounded-blast-radius reasoning to the
  prior fix). Real authenticated Node images captured and decoded
  end to end (1920x1080, a real backyard scene, three independent
  captures via two request shapes); real Add Camera pairing/preview/
  complete proven via a genuinely fresh disposable Host instance; real
  Chromium/Playwright proof against the real built frontend (full pass,
  real screenshots); preview non-persistence verified directly against
  the database (zero Visits/Events created); bounded interruption/
  recovery exercised against the configured Stream; credential safety
  verified against the real secret value, not merely field names; strict
  `field_acceptance` compatibility passed with a real 5/5-sample RTT
  calibration batch. One disclosed, non-blocking finding: a real,
  self-resolving post-pairing background-warm-proof timing race
  (self-resolves in ~5-10s with honest failure messaging throughout;
  judged correctly non-release-critical, not fixed as a product change).
  Classification **A**. **Lane G status, updated (see §6, below):**
  `MATERIALLY CLOSED / VALIDATION REMAINS` -> `CLOSED -- RELEASE
  -CRITICAL`. Final Node state: healthy, upgraded, genuinely unpaired
  (every test credential this milestone itself minted, including two
  self-inflicted orphans from its own iterative testing, was cleanly
  revoked before finishing) -- deliberately not left as another mystery
  credential for the next session to untangle. One disposable Windows
  instance (`MockingBirdCameraGoldenPathV1`, built/verified but not
  ultimately needed for the proof) left `SAFE_TO_RECLAIM`
  (~2.5GB), not destroyed. This closure does **not** authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-Authenticated-Camera-Node-Golden-Path-
  Capture-&-Preview-Acceptance-v1):** `8a3ad4f` -- the report commit for
  Ecosystem / Provider Integrations Release-Scope Decision v1 (see §3,
  below, and
  [ecosystem-provider-integrations-release-scope-decision-v1-report.md](ecosystem-provider-integrations-release-scope-decision-v1-report.md)
  for the complete record). Pre-release product-scope decision for Lane K
  -- documentation/reconciliation only, zero production code changed, no
  adapter or plugin framework implemented. Decision: no dedicated
  Frigate, Blue Iris, Scrypted, or Home Assistant adapter (or generic
  NVR/plugin framework) is required for the one public launch; launch
  acquisition posture remains native Camera Node (golden path) +
  standards-based acquisition (ONVIF, RTSP/RTSPS, local USB/platform
  camera, offline/recorded ingest, camera-trap ingest) -- traced directly
  from real existing code and design docs, all already substantial
  accepted work (see "Camera / Acquisition Foundations," §5, below). Each
  of the four candidates individually assessed against product value,
  capability gap, existing standards coverage, surveillance/NVR
  product-identity pressure, and new credential/network surface; all four
  DEFERRED -- NOT REQUIRED FOR LAUNCH, not "never." Concrete,
  evidence-based reopening criteria recorded (repeated otherwise-
  unsolvable connection failures, a provider exposing evidence-quality
  facts standards can't, measured installation-burden reduction, repeated
  organizational dependency, measured reliability gain); popularity,
  API-availability, competitor-parity, and plugin-framework desire are
  explicitly insufficient alone. Architecture contract locked for any
  future adapter: must terminate into the existing Source/Stream/Visit/
  Evidence/Review Decision/Observation spine, never parallel Visit or
  Reviewed truth, never a second camera database, never cloud-required
  operation, never a surveillance-specific mode, never separate
  per-provider analytics truth. Classification **A**. **Lane K status,
  updated:** `OPEN DECISION` -> `DECISION CLOSED -- DEDICATED PROVIDER
  INTEGRATIONS DEFERRED PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH` (see §6
  Lane K, below). Removes zero launch blockers -- Lane K was already
  categorized decision-only (§6 category B), never release-critical. This
  closure does **not** authorize a provider implementation, Lane R,
  External Pre-Release Acceptance, or Final Release Hardening, and does
  **not** select a next development milestone -- see §3 for the complete
  reconciliation entry.
- **Prior accepted HEAD (pre-Ecosystem-Provider-Integrations-Release-
  Scope-Decision-v1):** `e79420e` -- the report commit for Camera / Source
  Release Hardware Validation Closure v1 (see §3, below, and
  [camera-source-release-hardware-validation-closure-v1-report.md](camera-source-release-hardware-validation-closure-v1-report.md)
  for the complete record). Lane G hardware-validation milestone
  (release-critical, validation-only -- no new providers, no
  wildlife-denominator field cohort). Scheduler headline reconciliation:
  verified this document's own "Accepted HEAD" convention (naming the
  report commit, never the reconciliation commit that records it) is
  established and consistent, not stale; no bookkeeping correction made.
  Proves, live, against the real reference Camera Node (Pi,
  `node-76ec8e53ae586dd0`): health, both compatibility-preflight profiles
  (including a real 5/5-valid bounded RTT clock-calibration batch), an
  honest pairing-conflict rejection, and a clean bounded
  service-restart-recovery cycle (`node_id`/`boot_id`/pairing all
  correctly preserved) -- the first session on record to reach this depth
  against a genuinely reachable reference Node rather than finding it
  unreachable. Reproduces and fixes Representative Daylight Gate A Field
  Acceptance v11's own disclosed diagnostic-truth defect
  (`/node/v1/health`'s `self_test.camera_available` could report success
  while the specifically-configured camera was actually unavailable):
  root-caused, live, to `V4L2CameraProvider.cameras()` unconditionally
  marking every enumerated `/dev/videoN` device "available" from path
  existence alone, so this Node's own internal ISP/codec/HEVC-decoder
  pipeline device nodes (confirmed, live, never real cameras -- none
  opens via this Node's own installed OpenCV) masked the real camera's
  correctly-reported absence inside self-test's aggregate check. Fixed in
  `mockingbird_node.providers` (a bounded, per-path-cached, real-
  openability probe reusing `snapshot()`'s own existing ground truth,
  never a second signal); self-test's own separate, disclosed,
  deliberately-not-fixed once-at-startup/cached-forever staleness
  characteristic is not load-bearing for any safety decision today (the
  Host compatibility preflight never reads `self_test.camera_available`).
  Not deployed to the live reference Pi -- proven instead via tests
  grounded in this Node's own real, live-captured device topology, to
  avoid mutating a shared reference device for a validation-only
  milestone. RED->GREEN via 4 tests (2 new V4L2-provider-level, 1 new
  end-to-end composite+self-test integration reproducer, 1 existing test
  updated for the new legitimate per-candidate probe); 731 passed, 0
  failed across the full affected Camera Node/compatibility/RTSP/USB/
  DirectShow/credential-redaction/preview-contract subsystem sweep (11
  pre-existing xfails, unrelated); 0 new `ruff` findings (verified against
  unmodified `HEAD` for both changed files). Tier 3 (full Core)
  deliberately not run: `mockingbird_node` has zero import-time coupling
  into the Host's `mockingbird` package, an already-documented
  architectural invariant (`src/mockingbird/api/camera_node_transport.py`)
  confirmed directly this session, so the blast radius is provably bounded
  to Tier 2. No RTSP/local-USB/ONVIF hardware was reachable tonight
  (confirmed live -- a port-554 probe and an empty `/dev/video*`/`lsusb`,
  not assumed); a known Windows USB webcam (`EMEET SmartCam S600`) is
  registered but not currently connected -- a real live DirectShow
  enumeration-honesty proof only (zero video devices, correctly parsed by
  the real product function against this exact captured output), no live
  capture. Classification **B**: real, verified progress and one genuine
  defect fixed with clean regression coverage, but the milestone's own
  core named gap -- live authenticated video capture/preview proof for
  any real camera, including the reachable Camera Node itself -- remains
  open for every path tonight, for disclosed hardware/credential-
  availability reasons, not a code defect; not force-closed to A. **Lane
  G status, updated:** stays MATERIALLY CLOSED / VALIDATION REMAINS --
  RELEASE-CRITICAL (see §6 Lane G, below) -- narrower and better
  evidenced than before, not closed. This closure does **not** authorize
  the next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3 for the complete
  reconciliation entry.
- **Prior accepted HEAD (pre-Camera-Source-Release-Hardware-Validation-
  Closure-v1):** `d1f4f18` -- the report commit for Strong-Confidence
  Subject-Evidence Viability & Scene-Artifact Abstention v1 (see §3, below,
  and
  [strong-confidence-subject-evidence-viability-scene-artifact-abstention-v1-report.md](strong-confidence-subject-evidence-viability-scene-artifact-abstention-v1-report.md)
  for the complete record). Investigation-only, zero production code
  changed. Reconstructs Representative Daylight Gate A Field Acceptance
  v11's own Visit 018 (a leaf/branch cluster at the recurring "Location A"
  geometry that cleared `strong_detection_threshold` six times in one
  occurrence) faithfully, reusing the immediately-prior milestone's own
  already-field-grounded reproducer unmodified, and investigates every
  avenue the governing brief names (detector geometry lineage, crop
  containment/occupancy/consistency/stability, evidence
  diversity/temporal spacing, independent detector reacquisition,
  track-generation structure, evidence scoring, scene-confusor state) for
  a safe, non-ML, non-confidence-magnitude, non-motion, non-spatial-
  blacklist fact that separates a strong scene artifact from a strong
  real (including stationary and brief) bird. Classification **B**. **No
  safe separator was found; per the brief's own explicit instruction, none
  was invented.** Two new findings, both proven directly against real
  production code paths in a new, additive test file
  (`tests/test_strong_confidence_subject_evidence_viability_v1.py`, 2/2
  passing), not merely asserted from reading source: (1) the exact
  artifact shape and the accepted "strong real bird" positive control are
  structurally identical at every fact `candidate_quality_gate`/
  `scene_confusor` can read -- one track generation, `strong_detection_
  count > 0` -- so no count/generation threshold, for any constant,
  separates them without also catching the real bird; (2) the accepted
  geometry-lineage signal (Localization Attribution / Detection Geometry
  Lineage v1, `geometry_source`) -- the specific candidate generalization
  the governing brief's own §11 asked this milestone to investigate --
  does **not** separate them either: both classify identically as
  `geometry_source="detector"` / `detector_off_target`, because the
  artifact's own detector agreement is completely genuine and
  contemporaneous, six times over, not stale/tracker-extrapolated (the
  different, narrower defect class that signal already, correctly,
  closes for Background/Empty Evidence Species-Confidence Correctness
  v1). `scene_confusor.py` and `candidate_quality_gate.py` remain
  completely unmodified -- both of scene-confusor's own confidence
  escapes (steps 5/6) are reconfirmed, directly, still unconditional on
  region history by original design and simultaneously required for the
  real, field-proven feeder-pole stationary-real-bird control; weakening
  either without a new, independent, safe fact (none found) would risk
  that control. Zero MDv5/NMS/BioCLIP/eligibility threshold changed; zero
  new coordinate literal in production code; no whole-frame human veto;
  no spatial blacklist; no motion requirement; schema unchanged (`v58`).
  Directly-relevant existing regression suite re-run unchanged (107
  passed, 0 failed); 0 new `ruff` findings. Tier 3 (full Core)
  deliberately not run, per the brief's own explicit instruction not to
  run it for ceremony when a milestone concludes investigation-only with
  no production change. This does **not** close the field-observed
  Visit-018 defect -- it proves, with new evidence, that closing it
  safely needs either a genuinely new evidence-quality/content signal
  (explicitly out of scope for a Gate-A correctness milestone) or real
  field data this sandbox cannot responsibly produce. This closure does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, External Pre-Release Acceptance, or Final Release Hardening,
  and does **not** select a next development milestone -- see §3 for the
  complete reconciliation entry.
- **Prior accepted HEAD (pre-Strong-Confidence-Subject-Evidence-
  Viability-Scene-Artifact-Abstention-v1):** `1465103` -- the report
  commit for Strong-Confidence Non-Target & Scene-Artifact Visit
  Admission Correctness v1 (see
  [strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md](strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md)
  for the complete record). Reopened by Representative Daylight Gate A
  Field Acceptance v11's own field evidence: 8/18 confirmed-false Visits
  (44.4%), all admitted via the strong-detection bypass -- 7 a real
  person-in-frame confound (matching the already-accepted, out-of-scope
  Person-Background-False-Positive residual class), 1 (Visit 018) a
  strong-confidence leaf/branch scene artifact at the recurring "Location
  A" foliage geometry. Classification **B**. Both subclasses
  deterministically reproduced against the real, unmodified production
  admission path (tracker -> assembler -> authority -> quality-gate ->
  repository), not a synthetic fixture. **Person subclass, partially
  closed:** a new, bounded, same-frame class-contradiction check in
  `frame_tracker.observe()` now excludes an `animal`-class detection from
  ever corroborating a wildlife track when it substantially (IoU >= 0.3,
  reusing `scene_confusor.GEOMETRY_IOU_THRESHOLD`'s own already-field-
  justified bar) coincides, same frame, with an explicitly non-animal
  (`person`/`vehicle`) detection -- grounded in a real architectural fact
  confirmed at the code level (MDv5's own per-candidate-argmax-then-per-
  class-NMS decode can legitimately emit two different-class boxes for
  one real, torn-between-classes object). Deterministic RED->GREEN proof
  via `git stash`: the identical reproducer sequence was `created`
  pre-fix, `reject_insufficient_detector_corroboration` post-fix. The
  pure single-class-misclassification sub-case (no co-occurring
  contradiction anywhere) remains exactly the already-accepted 2026-08-20
  Person-Background-False-Positive residual -- unchanged, not reopened.
  **Artifact subclass, genuinely improved but not closed for the field-
  observed shape:** `product_repository._create_candidate_visit_locked`
  now also records scene-confusor region history (bookkeeping only,
  never changing the returned outcome) for a proposal rejected via
  `reject_insufficient_detector_corroboration`, not only an admitted one
  -- closing a real, confirmed defect where a recurring, always-weak
  hard-negative location (this codebase's own "Location A") left zero
  trace in `scene_confusor_regions` no matter how many times it
  recurred, because `_touch_scene_confusor_region` was reachable only
  once quality-gate already said `admit`. Directly reproduced and fixed
  for a never-strong recurring confusor that eventually clears the
  count-based corroboration axis (pre-fix `created`, post-fix `blocked_
  scene_confusor_suspected`, confirmed via `git stash`). **Directly
  proven, numerically, not to close v11's own headline Visit 018 shape:**
  a genuinely strong (>=0.70) occurrence still escapes scene-confusor
  suspicion regardless of accumulated history, because `evaluate_scene_
  confusor_suspicion`'s own steps 5 ("materially stronger than this
  region's own history") and 6 ("independently strong, unconditionally")
  are both, by original design, checked without reference to occurrence
  history once triggered -- and both are load-bearing for the real,
  field-proven feeder-pole stationary-real-bird positive control, so this
  milestone leaves `scene_confusor.py` itself completely unmodified
  rather than risk that control on an unverified assumption. Zero MDv5/
  NMS/BioCLIP/eligibility threshold changed; zero coordinate literal read
  by either fix; schema unchanged (`v58`). Every required positive
  control preserved (strong/weak/stationary real bird, bird+person
  spatially separate, multi-subject isolation, all prior hard-negative/
  corroboration/scene-confusor mechanisms). Tier 1 (new 11-test
  reproducer suite) 11/11; Tier 2 (28 directly-affected-subsystem files)
  705 passed / 0 failed; Tier 3 (one full Core run) 5610 passed / 2
  failed (both independently reconfirmed pre-existing and unrelated via
  fresh `git stash` isolation against this session's own starting HEAD --
  the same already-repeatedly-documented `test_place_biodiversity_
  summary_repository.py` pair named in §14) / 3 skipped / 23 deselected /
  11 xfailed; zero new `ruff` findings (git-stash-isolated baseline
  comparison). This closure does **not** authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-Strong-Confidence-Non-Target-Scene-Artifact-
  Visit-Admission-Correctness-v1):** `547209d` -- the report commit for
  Representative Daylight Gate A Field Acceptance v11 (Independent-
  Corroboration & Scene-Confusor Re-Proof; see §3/§6.R, below, and
  [representative-daylight-gate-a-field-acceptance-v11-report.md](representative-daylight-gate-a-field-acceptance-v11-report.md)
  for the complete record). No production code changed by this milestone
  (a real, representative-daylight, real-hardware field session, 101.8
  combined real observing minutes across two segments separated by a
  genuine ~71-minute Camera Node CSI-ribbon-cable hardware fault -- fully
  disclosed, user-resolved mid-session, isolated from the Host, which
  stayed healthy throughout including through the outage). Classification
  **B**. 100% lossless raw-ledger recovery verified on both segments
  against live cumulative counters. Directly queried (not inferred)
  `scene_confusor_regions` after the session -- answering the prior
  milestone's own disclosed evidence-trail gap definitively: 14 regions
  tracked, `occurrence_count` up to 5, `suspected_count = 0` throughout --
  every region that crossed the suspicion threshold held genuinely
  strong-confidence detections and was correctly, by design, never
  suspected (including a real, stationary, repeatedly-visited house-finch
  feeder location, spanning both segments -- direct field proof a real
  bird's own Visit at a spatially-stable location survives the mechanism);
  the session's one genuinely weak persistent-confusor chain (42
  generations, 883 detections, ~20 minutes, same coordinates the fix's own
  reproducer used) was intercepted almost every time by a different,
  pre-existing mechanism (`blocked_ambiguous_boundary`) before it could
  ever reach scene-confusor, so the two accepted mechanisms did not get a
  documented chance to compose in the field this session. Zero confirmed-
  false Visits trace to the corroboration axis (its 2 field rejections
  were both correct), but one admission (a 14-generation chain reaching
  the session's own dominant persistent-confusor coordinates) is a direct,
  hand-verified field reproduction of the fix's own explicitly-disclosed
  residual boundary (multiple non-dominant generations, none individually
  concentrated: `remainder=68 > remaining_floor=27` for `N=14`) --
  classified ambiguous, not confirmed-false, since its own evidence image
  does not clearly resolve a subject either way. Primary false-Visit rate
  8/18 confirmed (excluding 5 ambiguous) = 44.4%, numerically worse than
  v10's 36.4% but causally disjoint from it: all 8 confirmed-false Visits
  trace to a real landscaping worker in-frame (7, the already-accepted,
  out-of-scope person-background-false-positive residual class) plus one
  strong-confidence leaf artifact (1) -- none caused by a corroboration-
  axis or scene-confusor failure. Useful-evidence 43.5% raw / 62.5%
  excluding the same confound. Recall 100% (7/7 conservative denominator)
  / 70% (7/10 less-conservative, honestly disclosed both ways).
  Fragmentation 1/7 = 14.3% (a second consecutive non-zero cohort after
  v10 reopened it). Duplicates 0% (an 8th-9th convergent cohort).
  `blocked_missing_evidence` 9.29% (in-band, v7-v10 convergent range). Two
  genuine simultaneous-bird sightings directly, independently visually
  confirmed. Zero confident species labels on any confirmed-false Visit
  (Gate B clean). Two disclosed tooling defects (an acceptance-recorder
  directory-path encoding bug; fragile `--dev-root` absolute-Windows-path
  handling this milestone's own operator hit and self-corrected, with no
  lasting effect -- `git status` confirmed clean throughout and at
  report time), one disclosed real Camera Node hardware fault (root-
  caused to a CSI cable, user-resolved), and one open, unconfirmed
  observation (a 71-proposal `blocked_continuation_pending` backlog at
  segment-2 end, plausibly superseded intermediate state, not yet
  confirmed either way). This closure does **not** authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-Representative-Daylight-Gate-A-Field-
  Acceptance-v11):** `3c75674` -- the report commit for Independent
  Corroboration Value & Persistent-Confusor Admission Correctness v1 (see
  [independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md](independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md)
  for the complete record), sitting directly on top of `eeb1e57` (this
  milestone's own implementation commit -- one new, additive
  `max_single_generation_detection_count` fact on `contracts.
  ConfidenceEvidenceSummary` (max, not sum, across constituents, mirroring
  `max_consecutive_detector_confirmed_frames`'s own established pattern),
  and one new pure helper in `candidate_quality_gate.py`,
  `_concentrated_in_single_generation`, recursively re-applying the
  *existing* `_BARE_DETECTOR_CONFIRMATIONS_PER_GENERATION`/`_QUALIFYING_
  DETECTIONS_MARGIN` constants to "the chain minus its own single largest
  member" -- zero new numeric constants introduced anywhere), which sits
  on top of `89b87f1` (the reconciliation commit accepting Representative
  Daylight Gate A Field Acceptance v10). Classification **A**. Reopened
  the accepted Hard-Negative Visit Admission Precision & Species-
  Escalation Correctness v1 fix because v10 produced real field evidence
  satisfying the accepted-work-freeze exception: that fix correctly
  rejected 3/3 classic bare-minimum single-generation hard negatives, but
  the same recurring tube-feeder-area confusor defeated its count-based
  corroboration axis 4 separate times (36.4% confirmed-false-Visit rate)
  by accumulating many individually-insufficient detections within one
  already-confirmed generation's own extended natural persistence, never
  by chaining bare-minimum restarts (the shape the prior fix already
  closed). Mathematically proved -- not merely observed -- that no
  function of raw detection-count magnitude, for any constant, could
  separate the disclosed v10 false range (9-33) from the disclosed real
  range (13-18, v10's own weak/distant-bird control), since they overlap;
  ruled out per-generation caps, detection-rate/density, geometry
  variance, and confidence-shape heuristics on the same evidentiary
  grounds, each explicitly forbidden or mathematically shown ineffective
  before landing on the recursive-floor design actually shipped.
  Investigation also found, and empirically verified via a real
  sequential-admission reproducer (not modified, not duplicated, not
  re-tuned), that the already-live `scene_confusor` mechanism
  (unconditional since schema 34) independently blocks a 4th
  same-geometry, single-generation recurrence of a never-strong signature
  within one session -- closing, together with this milestone's own new
  within-proposal check, both the concentrated-corroboration shape and
  the repeat-occurrence shape v10's persistent confusor exhibited, with a
  single-generation proposal's first-through-third occurrence at a new
  location remaining the same honestly disclosed, now mathematically
  irreducible residual the prior milestone already named. Every accepted
  positive control retained (v10's own weak/distant real bird, including
  at the confusor's own former location; a dedicated stationary/
  motionless real-bird control; brief and intermittent real-bird
  controls; both accepted v8/v9 hard negatives, one proven to reach the
  byte-identical pre-existing rejection path; multi-subject isolation;
  species-escalation and Reviewed-truth safety). Zero new numeric
  constants; zero coordinate literals read by the fix (proven in both
  directions by adversarial tests); production MDv5a `score_threshold`
  confirmed unchanged at `0.1`; schema unchanged (`v58` -- the new fact
  travels inside the existing `confidence_evidence_json` text blob, no
  migration). Tier 1 (new 18-test replay suite) 18/18; Tier 2 (24
  affected-subsystem files, including scene-confusor's own 65 tests) 725
  passed / 2 pre-existing unrelated skips / 0 failures; Tier 3 (one full
  Core run) 5600 passed / 1 failed / 3 skipped / 23 deselected / 11
  xfailed -- the 1 failure (`test_transport_worker.py`, unrelated Camera
  Node transport/retry code, zero call-graph relationship to any file
  this milestone touched) independently confirmed a non-reproducible,
  load-induced async-timing flake via 8 consecutive clean isolated
  re-runs (3 on the clean starting HEAD, 5 with this milestone's changes
  restored), not the same previously-documented recurring pair and
  verified from scratch rather than assumed; zero new `ruff` findings on
  every touched production file (`git stash`-isolated baseline
  comparison). Honestly disclosed, not hidden: two independently-
  substantial generations neither individually dominant are not flagged
  by this check (a deliberate, bounded, documented design choice, not an
  oversight), and the real v10 session's own report never confirms
  whether scene-confusor state was actually consulted for its own 4
  admitted false Visits -- both named as concrete inputs to the next,
  separately-authorized daylight tranche, not resolved here (no field
  session was run by this milestone). Does **not** authorize the next
  Representative Field Acceptance session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-Independent-Corroboration-Value-Persistent-
  Confusor-Admission-Correctness-v1):** `e6d662f` -- the report commit for
  Representative Daylight Gate A Field Acceptance v10 (Admission-Precision
  Re-Proof & Gate A Closure Tranche; see §3/§6.R, below, and
  [representative-daylight-gate-a-field-acceptance-v10-report.md](representative-daylight-gate-a-field-acceptance-v10-report.md)
  for the complete record). No production code changed by this milestone
  (a real ~90.2-minute live field-acceptance session against the real
  reference Camera Node, plus rigorous post-hoc offline accounting using a
  newly-disclosed periodic-counterfactual-snapshot method) --
  `e6d662f` sits directly on top of `b7e9724` (the reconciliation commit
  accepting Field-Acceptance Instance Lifecycle & Storage Safety v1).
  Classification **A** (the session itself, not the hypothesis under
  test -- see below). Primary finding: the Hard-Negative Visit Admission
  Precision fix's own field-proof criterion did **not** hold -- confirmed
  false-Visit rate 4/11 = 36.4%, worse than both v8 (22.2%) and v9
  (20.0%), root-caused precisely to one recurring background confusor
  (tube-feeder area) defeating the new rule's count-based corroboration
  axis, exactly the residual risk that fix's own report had already
  disclosed as untested at this scale. The rule correctly rejected 3/3
  classic bare-minimum single-generation hard-negative chains, including
  an exact re-confirmation of v8's own foliage-cluster location.
  Weak-real-bird recall preserved; Gate B's own species-escalation
  failure class (false Visit -> confident wrong species) did **not**
  recur. Fragmentation regressed to one confirmed case (breaking the
  prior 0% streak); duplicates remain 0%; `blocked_missing_evidence`
  improved to 6.7% (best of all cohorts); RTT-normalized latency stable,
  closely matching v9. Field-acceptance instance lifecycle tooling
  exercised end to end for the first time in a real session
  (`init` -> `completed` -> `archived`, evidence-archive attached,
  `SAFE_TO_RECLAIM`, deliberately not destroyed). Does **not** authorize
  the next Representative Field Acceptance session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- see §3 for the complete reconciliation entry.
- **Prior accepted HEAD (pre-v10):**
  `1000c8d` -- the report commit for Field-Acceptance
  Instance Lifecycle & Storage Safety v1 (see §3/§6.R, below, and
  [field-acceptance-instance-lifecycle-storage-safety-v1-report.md](field-acceptance-instance-lifecycle-storage-safety-v1-report.md)
  for the complete record), sitting directly on top of `91a8ebb` (this
  milestone's own implementation commit -- a new durable, self-verifying
  sidecar manifest (`field_acceptance_manifest.json`) tracking
  `active -> completed -> archived` for a disposable field-acceptance
  Windows dev-root, with `SAFE_TO_RECLAIM` computed fresh at assess/
  cleanup time rather than stored; a new standalone `scripts/field_
  acceptance_instance_lifecycle.py` (`init`/`status`/`assess`/`complete`/
  `mark-archived`/`cleanup`/`preflight`), reusing `deploy_windows_dev.py`'s
  own process/port-safety primitives via the identical `runpy.run_path`
  sibling-script convention that file already uses for `build_local_
  product.py`; two additive changes to `deploy_windows_dev.py` itself
  (a `--stop` flag exposing the already-existing `stop_verified_
  deployment` standalone; `check_storage_headroom`, a pre-build fail
  -closed storage-preflight guard mirroring already-accepted disk
  -pressure/recorder-ceiling thresholds as literals); cleanup dry-run by
  default, explicit `--destroy` required, redundantly re-verified
  immediately before its one destructive call, which delegates to
  `deploy_windows_dev.py`'s own already-hardened `WindowsHost.remove_tree`
  -- zero schema change, zero `src/mockingbird/` files touched), which
  sits on top of `664bfbe` (the reconciliation commit accepting Host <->
  Camera Node Release-Compatibility Preflight v1).
- **Prior accepted HEAD (pre-Field-Acceptance-Instance-Lifecycle-Storage-Safety-v1):**
  `b39b414` -- the report commit for Host <-> Camera
  Node Release-Compatibility Preflight v1 (see §3/§6.R,
  below, and
  [host-camera-node-release-compatibility-preflight-v1-report.md](host-camera-node-release-compatibility-preflight-v1-report.md)
  for the complete record), sitting directly on top of `2e84227` (this
  milestone's own implementation commit -- new `mockingbird.observation.
  node_compatibility` (pure `classify_node_compatibility` decision table
  + live `probe_node_compatibility` orchestration, reusing `CameraNode
  Client`/`clock_calibration.estimate_rtt_clock_calibration` unchanged);
  one new conditional gate in `api/main.py:start_stream_observation`,
  active only when `request.state.field_acceptance_principal is not None`
  and the Stream is already fully paired, failing closed via one new pure
  `unified_status.camera_node_incompatible_facts` builder before
  `.start(...)` is ever called; one new informational `diagnostic_
  context` key on Doctor's existing `camera_node` check; a new standalone
  `scripts/check_camera_node_compatibility.py` CLI; 25 new tests across
  `test_node_compatibility.py`/`test_node_compatibility_api.py`/`test_
  doctor.py` -- zero schema change, zero wire-protocol change), which
  sits on top of `da1d05e` (the reconciliation commit accepting Review
  Provenance Validation & API Error Semantics v1).
- **Prior accepted HEAD (pre-Host-Camera-Node-Release-Compatibility-Preflight-v1):**
  `6809933` -- the report commit for Review Provenance
  Validation & API Error Semantics v1 (see §3/§6.R,
  below, and
  [review-provenance-validation-api-error-semantics-v1-report.md](review-provenance-validation-api-error-semantics-v1-report.md)
  for the complete record), sitting directly on top of `00ff750` (this
  milestone's own implementation commit -- one new `except ReviewProvenanceError`
  clause in `create_review_label`, `mockingbird/api/main.py`, mapping the
  v9-disclosed `agent_diagnostic` review-provenance `500` to a clean `400`
  via `str(error)`, mirrored from the identical, already-established
  convention its sibling endpoint `reclassify_review_label_provenance`
  already used for this exact exception type; 7 new API-level tests in
  `tests/test_api.py` against the real endpoint; zero change to
  `review_provenance.py`, zero schema/model/provenance-policy change),
  which sits on top of `e18e0e8` (the reconciliation commit accepting
  Hard-Negative Visit Admission Precision & Species-Escalation
  Correctness v1).
- **Prior accepted HEAD (pre-Review-Provenance-Validation-API-Error-Semantics-v1):**
  `9cb14c7` -- the report commit for Hard-Negative Visit
  Admission Precision & Species-Escalation Correctness v1 (see §3/§6.R,
  below, and
  [hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md](hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md)
  for the complete record), sitting directly on top of `95f0340` (this
  milestone's own implementation commit -- one new admission-time check,
  `candidate_quality_gate.reject_insufficient_detector_corroboration`,
  reusing already-computed `contracts.ConfidenceEvidenceSummary` detector
  -corroboration facts never previously read at this boundary; a small,
  duck-typed deserialization helper in `product_repository.py`; a new
  Tier 1 replay test file driving every hard-negative/positive-control
  case through real, unmodified production code -- zero change to
  `frame_tracker.py`/`visit_episode_assembler.py`/`evidence_scoring.py`/
  `scene_confusor.py`/`counterfactual_lineage.py`/the MDv5 detector path;
  production MDv5a `score_threshold` unchanged at `0.1`; zero schema
  change), which sits on top of `58c0634` (the reconciliation commit
  accepting Representative Daylight Gate A Field Acceptance v9).
- **Prior accepted HEAD (pre-Hard-Negative-Visit-Admission-Precision-
  Species-Escalation-Correctness-v1):** `8b5185b` -- the report commit for
  Representative Daylight Gate A Field Acceptance v9 (True-Latency &
  Precision Reconciliation Tranche; see §3/§6.R, below, and
  [representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
  for the complete record). No production code changed by this milestone
  (a live field-acceptance session plus post-hoc offline accounting) --
  `8b5185b` sits directly on top of `17ce108` (the reconciliation commit
  accepting Reference Camera Node RTT-Capability Upgrade & Compatibility
  Re-Proof v1).
- **Prior accepted HEAD (pre-v9):** `1a36b06` -- the report commit for Reference Camera
  Node RTT-Capability Upgrade & Compatibility Re-Proof v1 (see §3/§6.R,
  below, and
  [reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
  for the complete record). No production code changed by this milestone
  (it upgraded and re-verified real Camera Node hardware, not the
  repository) -- `1a36b06` sits directly on top of `1a39479` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v8). Self-correction: this file's own §1 headline bullet was
  not refreshed when v8 was reconciled at `1a39479` (only §3/§6.R were
  updated at the time) -- `1a39479`/`eb75bd6` (v8's own reconciliation/
  report commits) were real, correctly-accepted intermediate states that
  this bullet simply never advanced past; see §3's own chronological
  entries, which are and remain the authoritative record.
- **Prior accepted HEAD (pre-Reference-Camera-Node-RTT-Capability-Upgrade
  -Compatibility-Re-Proof-v1):** `ea38d21` -- the report commit for Camera
  Node <-> Host RTT-Bounded Clock Calibration v1 (see §3/§6.R, below, and
  [camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
  for the complete record), sitting directly on top of `bc6d5ee` (this
  milestone's own implementation commit -- a new `RttRoundTrip`/
  `RttClockCalibrationRecord`/`estimate_rtt_clock_calibration` section in
  `clock_calibration.py` (the accepted one-way estimator entirely
  unchanged alongside it, now scoped to relative drift/jump monitoring
  only), two additive `/node/v1/health` response fields (`mockingbird_
  node/app.py`), a new `CameraNodeClient.sample_clock_round_trip` method,
  an additive `rtt_clock_calibrations` ledger/API/CLI projection, a
  deliberately renamed-not-retyped `rtt_calibrations` parameter and new
  interval fields (`*_min_ms`/`*_max_ms`) on `capture_to_visible_
  latency.py`, a new bounded RTT-recalibration trigger/concurrent-batch on
  `engine_runtime.py`, one Doctor diagnostic-string update, and one
  contract-doc correction -- zero Camera Node/wire-protocol breaking
  change, zero schema/database change, zero Visit-grouping/admission/
  model change), which sits on top of `d25134b` (the reconciliation
  commit accepting Camera Node -> Host Clock Normalization for True
  Capture-to-Visible Latency v1).
- **Prior accepted HEAD (pre-Camera-Node-Host-RTT-Bounded-Clock
  -Calibration-v1):** `1766ad6` -- the report commit for Camera Node ->
  Host Clock Normalization for True Capture-to-Visible Latency v1 (see
  §3/§6.R, below, and
  [camera-node-host-clock-normalization-latency-v1-report.md](camera-node-host-clock-normalization-latency-v1-report.md)
  for the complete record), sitting directly on top of `1e1a78b` (this
  milestone's own implementation commit -- new `clock_calibration.py` plus
  its test file, additive `CounterfactualLedger`/`CounterfactualWindowResult`
  calibration fields on `counterfactual_lineage.py`, an additive
  `clock_calibration_required`/`invalid_clock_mapping` extension to
  `capture_to_visible_latency.py` defaulted to exactly pre-milestone
  behavior, a small additive buffer/tick hook on `engine_runtime.py`,
  additive API-schema/route projection, additive calibration parsing in
  both `run_gate_a_measurement_accounting.py`/`run_encounter_accounting.py`,
  one Doctor diagnostic-string update, and one contract-doc update -- zero
  Camera Node/wire-protocol change, zero schema/database change, zero
  Visit-grouping/admission/model change), which sits on top of `3eeb8ed`
  (the reconciliation commit accepting Gate A Measurement Closure v1).
- **Prior accepted HEAD (pre-Camera-Node-Host-Clock-Normalization-v1):**
  `86955ab` -- the report commit for Gate A Measurement Closure v1 (see
  [gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
  for the complete record), sitting directly on top of `211a368` (this
  milestone's own implementation commit -- new `fragmentation_accounting.py`/
  `capture_to_visible_latency.py`/`scripts/run_gate_a_measurement_accounting.py`
  plus their test files, an additive `TrackGenerationRecord.start_captured_at`/
  `end_captured_at` field pair on `counterfactual_lineage.py` and its API
  -schema/route projection, one pre-existing `run_encounter_accounting.py`
  bug fix, and two new regression tests on already-accepted files
  `engine_runtime.py`/`candidate_visit_repository.py` -- zero Visit-grouping/
  admission/model/schema change), which sits on top of `a5cf039` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v7).
- **Prior accepted HEAD (pre-Gate-A-Measurement-Closure-v1):** `5351e08` --
  the report commit for Representative Daylight Gate A Field Acceptance v7
  (see [representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
  for the complete record), sitting directly on top of `d192a0b` (this
  milestone's own deploy-tooling-fix commit -- `scripts/deploy_windows_dev.py`/
  its own test file only, zero product/perception/admission/Visit/evidence/
  classification code, the same bounded shape as v6's own deploy-tooling
  fix), which sits on top of `5b1c540` (the reconciliation commit accepting
  Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness
  v1).
- **Prior accepted HEAD (pre-v7):** `42d6075` -- the report commit for Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1 (see its own
  "Latest accepted milestone" entry, below, and
  [pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
  for the complete record), sitting directly on top of `1b8dd47` (this
  milestone's own implementation commit -- production code
  `candidate_visit_authority.py`/`candidate_visit_adapter.py`/
  `engine_runtime.py`, their test files, and `docs/candidate-visit-
  authority-contract.md`), which sits on top of `b37656d` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v6 at Classification B).
- **Prior accepted HEAD (pre-Pending-Proposal Evidence Preservation &
  Arbitration Fallback Correctness v1):** `b35b2d4` -- the deploy-tooling-fix commit for
  Representative Daylight Gate A Field Acceptance v6 (see its own "Latest
  accepted milestone" entry, below, and
  [representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
  for the complete record), sitting on top of `26edddf` (the implementation
  commit for Background / Empty Evidence Species-Confidence Correctness v1,
  unchanged, not itself re-run, by this milestone). This milestone's own
  report commit (`40e4f5e`) sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention -- the deploy-tooling fix itself (bounded to `scripts/deploy_
  windows_dev.py`/its own test file, zero product/perception/admission/
  Visit/evidence/classification code) is the only code this milestone
  actually changed; see "Latest accepted milestone," below, for why a
  Classification B field session still cites a real code-bearing HEAD.
- **Prior accepted HEAD (pre-v6):** `26edddf` -- the implementation commit for Background /
  Empty Evidence Species-Confidence Correctness v1 (see its own "Prior
  accepted milestone" entry, below, and
  [background-empty-evidence-species-confidence-correctness-v1-report.md](background-empty-evidence-species-confidence-correctness-v1-report.md)
  for the complete record), sitting on top of `428fcb3` (the reconciliation
  commit that authorized Representative Daylight Gate A Field Acceptance v6
  as the next Lane R milestone).
- **Prior accepted HEAD (pre-Background/Empty Evidence Species-Confidence
  Correctness v1):** `65f5ec2` -- Representative Daylight Gate A Field
  Acceptance v5's own report commit (`e203489`) plus one same-day,
  self-caught follow-up commit adding a section its own governing
  template required but the first draft omitted (`65f5ec2`; no field
  evidence changed, only the report's own completeness), sitting on top
  of `eeb5f98` (the reconciliation commit accepting Lane C Sparse-State
  Honesty & First-Hour Narrative Closure v1), for the identical reason
  v4's own report commit was cited standalone below: a real, live
  ~106.6-minute field session that changed zero production code (see its
  own "Prior accepted milestone" entry, below, and
  [representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
  for the complete record).
- **Prior accepted HEAD (pre-v5):** `cb2a561` -- the implementation commit for Ongoing
  Monitoring Failure Diagnostics for RTSP / Local USB / Windows DShow v1
  (its own separate report commit, `7dd5146`, sits directly on top and is
  not cited here as a second, separate code-bearing HEAD, matching this
  field's established convention). `6a448e3` (the implementation commit
  for Login Rate-Limiting & Authentication Abuse Resistance v1; its own
  separate report commit, `54b90fa`, sits directly on top, likewise not
  cited separately). `83b15a5` (the implementation commit for Historical
  Species-Status ("New" vs. "Seen Before") Correctness v1; its own separate
  report commit, `b619546`, sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention). `e3c293f` (the implementation commit for
  Release Licensing, Distribution & Third-Party Legal Closure v1; its own
  separate report commit, `d1a2955`, sits directly on top and is not
  cited here as a second, separate code-bearing HEAD, matching this
  field's established convention). `893eed5` (the implementation commit
  for Platform / Runtime Portability & Support Truth Closure v1; its own
  separate report commit, `d5f4a32`, sits directly on top, likewise not
  cited separately). `6f7bbb6` (the implementation commit
  for Sustained-Activity Visit Admission Starvation & Stop-Finalization
  Correctness v1; its own separate report commit, `0638759`, sits
  directly on top, likewise not cited separately).
  `81dec47` (the implementation commit for Local
  Only / Privacy Closure v1; its own separate documentation-only report
  commit, `64f0a4d`, sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention). Native-Windows Packaged Local-Only Acceptance & Privacy
  Closure v1's own report commit (`c8016b9`) also sits on top, likewise
  not cited as a separate code-bearing HEAD -- that milestone found zero
  reproduced defects and changed zero production code, so it added only
  its own report file. Representative Daylight Gate A Field Acceptance
  v4's own report commit (`270b6ba`) sits on top next, for the identical
  reason: a real, live ~112-minute field session that changed zero
  production code (the real defect it found is disclosed, not fixed --
  see its own "Prior accepted milestone" entry, below).
  `9c52c7f` (Retention Correctness & Bounded Cleanup
  Closure v1's own implementation commit), `fe54ac9` (Storage / Retention /
  Disk-Pressure & Recovery Closure v1's own implementation commit),
  `1656f1a` (Non-Interactive Field Acceptance Authentication & Session
  Access v1's own implementation commit), `18a0025` (Whole-Product UI /
  Accessibility / Performance Closure v1's own implementation commit),
  One-Release Roadmap & Scheduler Reconciliation v1's own commit
  (documentation-only, `4312b18`), and Camera Node Upgrade &
  Compatibility Recovery v1's own three implementation commits sit
  underneath it in history; the intervening reconciliation commits for
  those closures (`7f98e43`, `8572308`, `4581424`, `4aeb658`, `e01e691`,
  `c03d0b1`, `80e1bb3`) are likewise not cited as separate code-bearing
  HEADs for the identical reason.
- **Schema:** `v58` -- unchanged by Representative Daylight Gate A Field
  Acceptance v7 (a live field-acceptance session plus one bounded deploy-
  tooling fix; zero product/perception/admission/Visit/evidence/
  classification code touched, zero schema-bearing code touched). Also
  unchanged by Pending-Proposal Evidence Preservation & Arbitration Fallback
  Correctness v1 (bounded, pending-proposal-aware preservation and
  deterministic same-component fallback added entirely within existing
  in-memory session state; no new/changed table). Also unchanged by
  Representative Daylight Gate A Field Acceptance v6. Also unchanged by
  Background / Empty Evidence Species-
  Confidence Correctness v1 (reads the already-existing, already-migrated
  `MediaAssetModel.geometry_attribution_json` column, schema 33; adds one
  new optional function parameter and one new pure-decision-function
  reason code, no new table/column/migration). Also unchanged by
  Representative Daylight Gate A Field
  Acceptance v5 (a live field-acceptance session; zero production code
  touched). Also unchanged by this milestone (Lane C Sparse-State
  Honesty & First-Hour Narrative Closure v1 is a single-branch precedence
  fix in `_dashboard_runtime_by_stream` -- api/main.py -- plus two
  frontend copy paragraphs; no DTO field, table, or column was added).
  Also unchanged by Ongoing Monitoring
  Failure Diagnostics for RTSP / Local USB / Windows DShow v1 (adds one new
  file, a new in-memory session field, and bounded application-code-only
  edits across the playback/repository/API layers; every new failure code
  is stored in the pre-existing, already-unbounded-length `StreamRuntime
  CheckpointModel.failure_code` `String` column, so no new table/column/
  migration was needed). Also unchanged by Login Rate-Limiting &
  Authentication Abuse Resistance v1 (adds one new file plus bounded edits
  to `authenticate_user`/`sign_in`; throttle state is deliberately
  in-memory only, never persisted, so it needed no new table/column/
  migration). Also unchanged by Historical Species-
  Status ("New" vs. "Seen Before") Correctness v1 (touches one test file
  only; zero production code). Also unchanged by Release Licensing,
  Distribution & Third-Party Legal Closure v1 touches only packaging
  tooling and documentation -- `scripts/build_local_product.py`, a new
  `THIRD_PARTY_NOTICES.md`, and two doc files -- no model/migration
  change). Platform / Runtime Portability & Support Truth Closure v1 (an
  evidence/documentation closure plus two narrow capability-message fixes
  in `mockingbird.diagnostics.doctor`) had likewise left schema unchanged.
  Sustained-
  Activity Visit Admission Starvation & Stop-Finalization Correctness v1
  (see its own "Prior accepted milestone" entry, below) had likewise left
  schema unchanged. Representative Daylight Gate A Field Acceptance v6 also
  left schema unchanged -- its own deploy-tooling fix touches only
  `scripts/deploy_windows_dev.py`/its test file, no model/migration.
  Pending-Proposal Evidence Preservation & Arbitration Fallback
  Correctness v1 also leaves schema unchanged -- a new arbitration field
  (`AmbiguousBoundaryArbitration.fallback_order_by_winner_id`), two new
  adapter functions, and bounded in-memory engine-runtime state
  (`_MAX_PROTECTED_EVIDENCE_IDS`, four new session-lifetime counters
  surfaced through the existing `advanced` diagnostics dict); no new
  table/column/migration.
- **Latest accepted milestone:** Pending-Proposal Evidence Preservation &
  Arbitration Fallback Correctness v1 -- see
  [pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the exact defect
  Representative Daylight Gate A Field Acceptance v6 measured (see its own
  entry, below): a real arbitration winner permanently failing at the
  downstream evidence-availability gate (the bounded, insertion-order-only
  128-entry evidence-byte cache) with no fallback to a runner-up, losing
  48/263 distinct proposals (18.3%) in that real session. Root cause:
  `evaluate_candidate_authority` has no evidence-availability gate at all;
  `blocked_missing_evidence` is not retryable; `_run_assembly_tick`
  attempted every ambiguous-component member exactly once with no code
  path reconsidering a component once its chosen winner failed downstream.
  Two mechanisms, both implemented and independently tested, per this
  milestone's own governing brief's explicit requirement for both:
  **preservation** (`engine_runtime._compute_protected_evidence_ids`, a
  bounded (`_MAX_PROTECTED_EVIDENCE_IDS=64`), per-tick-recomputed set of
  still-actionable proposals' priority evidence, consulted by the shared
  cache's own real eviction policy so it prefers evicting something
  unprotected first) and **fallback**
  (`candidate_visit_authority.AmbiguousBoundaryArbitration.fallback_
  order_by_winner_id` plus `_EngineSession._attempt_resolved_component`,
  which walks a resolved component's winner then its own remaining stable
  members, in the identical rank order arbitration already computed,
  stopping at the first admissible member or once the component's members
  are exhausted -- never rerunning arbitration, never crossing components).
  The unchanged 128-entry cache bound itself was deliberately *not* raised
  again, per the milestone's own explicit instruction. Two real design
  corrections were found and fixed during this milestone's own
  implementation and adversarial self-review (both fully documented in the
  report and in `docs/candidate-visit-authority-contract.md`): the
  priority-evidence preview must use currently-cached bytes, not `media=
  None` (real, live-captured evidence never declares `decodable=True`
  upfront, so a bytes-free preview would hard-reject every real candidate
  and protect nothing); and every resolved component must be walked as one
  atomic unit before any ordinary proposal is attempted at all, since
  `new_proposals`' own emission order has no guaranteed relationship to
  arbitration rank (a losing sibling reached first was being double-
  attempted once its own winner's chain later reached it, corrupting
  `proposals_observed`/the ledger -- found before it reached a committed
  test, fixed, and locked in by a dedicated permanent regression test).
  19 new/updated tests, all confirmed RED on accepted `b37656d` (via
  `git stash` isolating the three production files) and GREEN after the
  fix, including a 105-simulated-minute v6-shaped replay against the real
  bounded cache (two simultaneous subjects, real eviction, real
  protection) whose own pre-fix failure was independently confirmed
  genuinely RED via direct reproduction of the real mechanism (zero
  admissions, real `blocked_missing_evidence`/`blocked_ambiguous_boundary`
  mix), and dedicated exactly-once, fragmentation, multi-subject-isolation,
  and stop-finalization proofs. Tier 1 187/187, Tier 2 279/279, Tier 3 (one
  full Core run, `pytest -m "not slow"`, 5372 tests) 5357 passed, 3
  skipped, 11 xfailed, 1 failed -- the one failure
  (`test_temporal_capture_cli.py::test_run_capture_end_to_end_reconnect_
  produces_a_native_session_timeline`) independently confirmed unrelated
  (zero code-dependency relationship to any file this milestone touched;
  passes on the exact pre-fix baseline; passes 5/5 consecutive runs in
  isolation with the fix in place; only failed once, inside this
  investigation's own necessary four-way concurrent chunked Core
  execution -- an artifact of working around this environment's own
  10-minute background-task cap on a single `pytest -m "not slow"`
  invocation, not a product defect). No schema change. This closure does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, External Pre-Release Acceptance, or Final Release Hardening,
  and does **not** select a next development milestone -- authorization
  returns to the bold statement in §3, below, unchanged by this closure.
  This is nighttime/implementation correctness work only, per this
  milestone's own explicit non-goal: no field session was run. See §6.R,
  below, for the updated "Remaining Gate A dependency" this closure leaves,
  and this milestone's own report, "Next field proof required," for
  exactly what the next daylight cohort must prove.

- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v6 -- Post-Fix Replication & Multi-Subject Tranche -- see
  [representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
  for the complete record. Classification **B**. A real, live
  106.63-minute Observation session against the real reference Camera
  Node, on the accepted, unmodified build, directly confirmed the
  *specific* Sustained-Activity Visit Admission Starvation mechanism v4
  found (arbitration deferring a whole connected component forever) does
  **not** recur -- arbitration reached a decision for every ambiguous
  component on schedule throughout. But `candidates_created` ended the
  session at **zero** despite substantial, independently-confirmed,
  sometimes-simultaneous real wildlife activity (two exhaustively-reviewed
  real activity segments, each directly confirmed via full-resolution
  independent-recorder frames and containing genuine multi-bird moments,
  0/2 represented by any admitted Visit) -- the same practical symptom v4
  produced, now root-caused to a *different*, precisely source-traced
  mechanism: the sole arbitration winner for a real, resolved component can
  fail at the downstream evidence-availability gate (the bounded 128-entry
  evidence-byte cache, evicted purely by insertion order with no awareness
  of which pending proposal still needs which bytes), and because that
  outcome is not retryable and no fallback to a runner-up exists, the
  component's real activity is permanently lost. This is a concrete,
  real-field instance of an already-disclosed residual risk -- named,
  explicitly not fixed, when the evidence-cache bound was last raised
  32->128 ("a pending-proposal-aware eviction policy... is a materially
  larger change... left as a disclosed follow-up, not undertaken here") --
  not a new defect class, but a materially sharper session-wide measurement
  of its real consequence (48/263 distinct proposals, 18.3%, spread across
  the full session, versus v5's own 2.8%) than existed before, and shown
  for the first time to also reach the *ordinary* (non-forced) arbitration
  path, not only the recency-forced path the original disclosure discussed.
  Stop-finalization behaved correctly (the honest `stopping`/`stopped`
  cycle was observed live, rescuing 0 -- consistent with root cause, not a
  regression, since nothing cleanly resolvable remained pending at stop).
  Zero `blocked_shadow_mode`, zero persistence contention, zero
  ERROR/CRITICAL/WARNING lines in the full structured session log.
  Background/empty-evidence eligibility and species assistance were not
  exercisable this session (zero admitted Visits ever reached either
  layer) -- disclosed as honest measurement gaps, not fabricated proof.
  Real, directly-confirmed simultaneous multi-subject activity occurred
  (not manufactured) but, exactly like v5's own session for a different
  reason, never reached an admitted Visit, so multi-subject Visit-grouping
  correctness remains completely unexercised end-to-end across two
  consecutive post-fix cohorts now. Two bounded, tested, own-session
  deploy-tooling defects were found and fixed along the way (a
  `UnicodeDecodeError` crash in `_run_powershell`'s non-UTF-8 output
  handling that was masking a real, unrelated failure, RED->GREEN proven
  with a new regression test; a separate, disclosed-not-fixed `--dev-root`
  WSL-path usability gap) -- zero product/perception/admission/Visit/
  evidence/classification code touched. Per the milestone's own explicit
  §14 failure conditions and §35 acceptance bar, this is deliberately
  **not** rounded up to Classification A on the strength of the
  investigation's own rigor alone: `candidates_created` remaining at zero
  for a prolonged real sustained-activity session is one of this
  milestone's own five explicit failure conditions, and "post-fix admission
  behavior replicates"/"in-session admissions occur" are both explicit
  Classification A requirements that did not hold this session. This
  closure does **not** authorize the next Representative Field Acceptance /
  Gate A session, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone --
  authorization returns to the bold statement in §3, below, unchanged by
  this closure. This reopens, rather than closes, a specific Gate A
  correctness question -- see §6.R, below, for the complete "Remaining Gate
  A dependency" account.

- **Prior accepted milestone:** Background / Empty Evidence Species-
  Confidence Correctness v1 -- see
  [background-empty-evidence-species-confidence-correctness-v1-report.md](background-empty-evidence-species-confidence-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the exact v5-
  disclosed Gate B defect class below: a weak, single-detection,
  `terminal_reason: maximum_unsupported_duration` localization's crop --
  real bytes, ordinary size, subject-focused tier -- received a confident
  ("Brown Thrasher," 89.9% score, 0.857 margin) wrong BioCLIP species
  label, clearing even the strictest existing abstention floor (proving no
  score/margin/tier change could ever catch it). Root cause: `evaluate_
  identification_eligibility` had no signal independent of BioCLIP's own
  output to ask whether a crop's box corresponds to a real, contemporaneous
  detector observation. Fix reads the already-persisted (schema 33)
  `MediaAssetModel.geometry_attribution_json`; a crop backed by tracker-only
  extrapolation or a stale carried-forward box, at the two crop tiers with
  no other same-moment-correspondence guarantee, is now ineligible --
  proven RED->GREEN against the real production `identify_review_queue_
  item` path, real-cohort validated (11/40 real background Visits newly
  abstain, 0/7 mandatory real positive controls regress). Several
  alternative signals (detection count, bbox size/coverage, padding ratio)
  were tested against real data and rejected as non-discriminating before
  this fix was chosen. Tier 1 82/82, Tier 2 456/456, Tier 3 clean apart from
  2 independently-verified pre-existing, unrelated failures. Honestly
  bounded, not oversold: a detector-sourced-but-still-wrong background
  crop (a genuine, contemporaneous, but recurring/confident false read)
  remains an open, disclosed Gate B residual -- not solved by this
  milestone, unchanged from before it. No schema change. No BioCLIP/
  detector/admission/Visit-assembly change. Does not authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does not select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure.

- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v5 -- see
  [representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
  for the complete record. Classification **A**. A real, live
  ~106.6-minute Observation session against the real reference Camera
  Node -- the identical Stream/scene that exposed Representative
  Daylight Gate A Field Acceptance v4's own admission-starvation defect
  -- on freshly-deployed accepted HEAD (`eeb5f98`, schema v58 unchanged).
  Directly, conclusively confirms the accepted Sustained-Activity Visit
  Admission Starvation & Stop-Finalization Correctness v1 fix works
  end-to-end under real sustained genuine wildlife activity:
  `candidates_created` reached its first real admission ~25 seconds into
  the session (v4 stayed at exactly 0 for its entire ~112-minute
  session) and climbed steadily throughout (19 real Visits admitted by
  session end, not only at stop); the new honest `stop_finalization_
  pending` status was observed live for the first time in a real field
  session, correctly appearing then clearing while the finalize tick
  genuinely rescued 2 more pending candidates (17 -> 19); zero
  `blocked_shadow_mode`, zero persistence-contention, zero duplicate
  Visits across the whole session -- no recurrence of any of the three
  defects that milestone fixed. One real defect found and precisely
  root-caused, not fixed (per the governing brief's own bar): a single
  false-positive admission (a weak, single-detection, `terminal_reason:
  maximum_unsupported_duration` localization) received a confident
  ("Brown Thrasher," 89.9%) but wrong BioCLIP species label on a crop
  direct pixel-region inspection against its own real bounding box
  confirms is empty background -- a fresh, concretely-reproduced
  instance of the already-known Gate B "background evidence -> confident
  label" regression class `roadmap.md` already names as open work, not a
  new starvation-family defect and not release-blocking for this
  milestone's own scope. Gate A/Lane R remains open (see §6.R, below);
  this closure does not authorize the next Representative Field
  Acceptance session, External Pre-Release Acceptance, or Final Release
  Hardening, and does not select a next development milestone --
  authorization returns to the bold statement in §3, below, unchanged by
  this closure.

- **Prior accepted milestone:** Lane C Sparse-State Honesty & First-Hour
  Narrative Closure v1 -- see
  [lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md)
  for the complete record. Classification **A**. Closes both bounded DEV
  gaps the accepted read-only Lane C reconciliation left open (§6.C,
  below): sparse/no-wildlife honesty under primary detector/GPU/model
  failure, and a coherent first-hour onboarding narrative. Root-caused the
  first gap to one specific line: `_dashboard_runtime_by_stream`
  (api/main.py) computed a Camera Node Stream's Dashboard/`ProductHealth`
  failure text as `engine_status.camera_message or engine_status.message`.
  `camera_message` ("Camera Node is paired and configured.") is set
  unconditionally, early -- before the Observation Engine's own detector/
  GPU/model load is even attempted -- and is never cleared once the camera
  connects, so it stayed truthy and the `or` always picked it, discarding
  the real, already-correctly-resolved failure text
  (`engine_status.message`) whenever the *engine* (not the camera) was
  what actually failed while the camera stayed perfectly reachable --
  self-contradicting an already-correct "Camera unavailable"/alert-tone
  badge with reassuring "paired and configured" wording next to it.
  Reproduced RED against the real, unmodified pre-fix code first (a fake,
  side-effect-free `ObservationEngineSessionManager.status()` read mirroring
  a real `_EngineSession` GPU-failure shape, the same technique
  `test_dashboard_observation_engine_truth.py` already established): only
  the message-precedence assertion failed -- `camera_health.state`,
  `needs_attention_count`, and `ready` were already correct pre-fix,
  precisely scoping the real defect to message text alone. Fixed by
  reusing, not re-deriving, the exact camera-connected-wins-only-if-
  disconnected precedence `_EngineSession.snapshot`'s own "headline
  whichever subsystem is actually blocking" contract already defines
  (`engine_message if engine_status.camera_connected else camera_message`)
  -- no additive `ProductHealthStatus`/`CameraHealthSummary` field needed;
  the existing `CameraHealthState.camera_unavailable` state (already
  alert-toned in the frontend) plus a correct message fully express the
  truth. Zero frontend change needed: `DashboardPage.tsx` already renders
  `camera.failure_reason ?? camera.message` verbatim. Confirmed
  independently: a healthy detector stays unaffected; a genuine camera/
  transport failure keeps its own distinct message, never the detector/GPU
  wording; acoustic (BirdNET) status stays independent, never implied by
  or implying the visual detector's own state; BioCLIP failures are
  structurally incapable of reaching this code path at all
  (`_schedule_automatic_identification` wraps its entire body in
  `try/except Exception: return`, "must never break admission" -- it
  cannot touch `_engine_available`/`_engine_message` under any failure).
  The onboarding gap: `web/src/components/OnboardingWizard.tsx` had two
  stale paragraphs (Welcome step, post-camera-setup Observe step) telling
  first-time users a sighting "appears in"/"lands in" Review Queue,
  predating the shipped review-optional design
  (`docs/product-doctrine.md` "Core flow": Observe -> Discover -> Understand
  -> Confirm -> Remember -> Improve, discovery through Today/Bird Log/Visit
  detail; "Measured, Inferred, and Reviewed": Inferred output must be
  useful immediately, never gated on confirmation first). Rewritten to
  name Today/Bird Log as where sightings actually show up, reusing already-
  established terminology ("Likely"/"Not yet confirmed" from
  `BirdLogPage.tsx`) rather than inventing new vocabulary; Review Queue
  remains named and available for deliberate batch review, just no longer
  framed as the normal destination. No screens added, no wizard-flow
  change. 7 new tests: `tests/test_dashboard_detector_health_honesty.py`
  (4, backend) and `tests/test_onboarding_narrative_copy.py` (3, a
  lightweight static-source-text regression -- not a new frontend
  unit-test framework -- covering the Observe-step paragraph the
  established e2e suite cannot reach without disproportionate new
  camera-pairing scaffolding); the existing
  `web/e2e/onboarding.spec.ts` gained two assertions on the Welcome-step
  paragraph, verified against a real rendered browser DOM
  (`npm run test:e2e:onboarding`: 6/6 passing). Tier 1: 7/7 passing. Tier
  2 (30 files, the established health/dashboard/camera/onboarding/setup-
  adjacent subsystem sweep): 594 passed, 11 xfailed (pre-existing), 0
  failed. Tier 3 (full Core) deliberately not run -- a single-branch
  precedence fix confined to one function, zero DTO/schema change, and
  Tier 2's own 594-test sweep already covers every real consumer of the
  touched function. `ruff check`: zero new findings on
  `src/mockingbird/api/main.py` (26 pre-existing findings confirmed
  unrelated via direct `git stash push -u` bisection -- identical count
  and finding set, none within ~2,300 lines of the touched function); the
  two new test files clean. `tsc --noEmit` clean. No schema change (see
  "Schema," above). `docs/release-execution-state.md` §6.C now reconciled
  to **MATERIALLY DELIVERED / NO KNOWN DEV REMAINS** (see below). This
  closure does **not** authorize the next Representative Field Acceptance
  / Gate A session, Lane G validation, provider integrations, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- authorization returns to **NONE
  -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED** (§3, below),
  unchanged by this closure.
- **Prior accepted milestone:** Ongoing Monitoring Failure Diagnostics
  for RTSP / Local USB / Windows DShow v1 -- see
  [ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md)
  for the complete record. Classification **A**. Closes Lane G's
  remaining disclosed gap (`camera-source-experience-v1-report.md`'s own
  section 7): once a non-Camera-Node Stream (RTSP, local USB, Windows
  DirectShow) is armed and running, a concrete failure cause
  (authentication, network, codec, decode) collapsed to one generic
  ongoing-monitoring message, even though setup-time validation already
  distinguished these causes. Confirmed the starting-state premise before
  starting (branch `main`, accepted HEAD `b1c78dc`, schema v58, the seven
  preserved untracked files present and untouched, no active worktree
  writer) -- matched exactly. Root-caused to two independent chokepoints,
  both confirmed by direct code reading before any fix: the long-running
  playback processes these three providers start used
  `stderr=subprocess.DEVNULL` unconditionally (no evidence was ever
  captured to classify with in the first place -- unlike the bounded
  one-shot setup-time probe, which already opted into capturing it), and
  even a correctly classified code would have been discarded by two
  separate hardcoded Camera-Node-only allowlists (`api.main._managed_
  camera_status`; `ProductRepository.mark_monitoring_backoff_with_
  failure_code`) before ever reaching a user. Reproduced against the
  real, unmodified pre-fix code via a direct `git stash` bisection: a
  real `"401 Unauthorized"` ffmpeg stderr line was silently discarded,
  collapsing to `"Camera process ended before the session was stopped."`
  regardless of cause. Fixed with a new, bounded, continuous
  `BoundedStderrDrain` (`playback/stderr_drain.py`) -- one dedicated
  daemon thread per monitored process, never blocking the child (unlike a
  naive switch to `stderr=PIPE` alone), retaining only a small
  (4096-byte), credential-redacted tail, owned by exactly one session's
  lifecycle and stopped from every exit path. Classification reuses the
  canonical vocabulary rather than building a second one: RTSP's
  setup-time `_classify_probe_failure` is now public
  (`classify_rtsp_failure_text`) and called unmodified by both setup
  validation and ongoing monitoring, proven identical by a dedicated
  setup/ongoing-agreement regression test; local USB and Windows
  DirectShow gained new, deliberately narrow classifiers backed only by
  real, reproducible evidence -- real ffmpeg 6.1.1 V4L2 stderr text
  gathered against this project's own Linux dev sandbox (device-missing,
  permission-denied) and real ffmpeg.exe 8.1.2 DirectShow stderr text
  gathered live against the project's own reference Windows dev host
  (device-unavailable -- the one category that host's zero attached video
  devices could actually produce) -- with an honest, provider-scoped
  generic fallback for every other cause, never a fabricated one. A live,
  real, end-to-end proof beyond unit tests (zero mocking anywhere in the
  call chain): a genuine `LiveCameraSessionManager` session against a
  real, disposable, instantly-refused local port correctly classified
  `camera_setup_rtsp_unreachable`. No retry/backoff timing logic was
  touched (`monitoring/durable_supervisor.py` has zero diff); recovery
  already clears stale failure state unconditionally via the pre-existing,
  unmodified `mark_monitoring_running`, re-verified correct for the new
  codes with a real-repository integration test. 26 new tests
  (`tests/test_ongoing_monitoring_failure_diagnostics.py`), each
  independently confirmed RED (via a real `ModuleNotFoundError` before
  implementation, or via the `git stash` bisection above) and GREEN
  after -- covering RTSP classification, setup/ongoing consistency,
  local_usb/windows_dshow evidence-backed-only classification, a
  dedicated Camera-Node-unaffected regression, credential redaction, a
  real ~4MB-stderr subprocess stress proof (no deadlock, bounded memory,
  drain keeps up), repeated-cycle thread-leak and concurrent-throughput
  proofs, multi-Stream isolation, and failure-code plumbing through
  `ManagedCameraStatus`/`StreamRuntimeStatusResponse`/`CameraHealthSummary`.
  Two pre-existing `test_stream_playback_contract.py` tests had
  fixed-signature test doubles that broke on the new `capture_stderr`
  keyword parameter this milestone adds to the three bridge modules'
  process-starting functions -- fixed (test-only signature widening, not
  a product defect). Tier 1: 26/26 passing. Tier 2 (20 files, the
  established camera/source/monitoring/health subsystem suite plus this
  milestone's own new file): 503 passed, 11 xfailed, 0 failed. Tier 3
  (`scripts/verify_core.py`, one full run): 5310 passed, 3 skipped, 23
  deselected, 11 xfailed, 0 failed -- no bisection needed. `ruff check`:
  0 new findings on every touched/new file, each individually confirmed
  via clean-baseline `git stash` bisection. No schema change (see
  "Schema," above). Local USB/Windows DirectShow hardware acceptance
  (device-busy, permission-on-real-hardware, unsupported-format) and a
  real RTSP camera's own live auth/codec failure remain genuinely
  untested -- honest, disclosed, not claimed; see the report's own
  "Remaining risks." Lane G moves from `PARTIAL, MATERIALLY CLOSED` to
  **MATERIALLY CLOSED / VALIDATION REMAINS** (see §6, below). This
  closure does **not** authorize the next Representative Field
  Acceptance / Gate A session, Lane C work, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure.
- **Prior accepted milestone:** Login Rate-Limiting & Authentication
  Abuse Resistance v1 -- see
  [login-rate-limiting-authentication-abuse-resistance-v1-report.md](login-rate-limiting-authentication-abuse-resistance-v1-report.md)
  for the complete record. Classification **A**. A RELEASE-SECURITY
  milestone, directly authorized outside this file, closing a real,
  previously-disclosed pre-existing gap: `POST /api/auth/sign-in` had
  generic, enumeration-safe failure behavior (unknown user/wrong password/
  disabled user all already returned the identical outcome) but no attempt
  counting, no delay, and no throttling of any kind -- first found by
  Mobile & Remote Experience v1's own security review, re-disclosed by
  several milestones since (most recently Non-Interactive Field Acceptance
  Authentication & Session Access v1). Root-caused against all ten of the
  governing brief's own diagnostic questions before any fix, confirming the
  gap was real and precisely bounded to one endpoint/one repository method.
  New `mockingbird.security.login_rate_limiter.LoginRateLimiter`: a small,
  dependency-free, thread-safe, in-process helper (not a general-purpose
  rate-limiting framework) with two independently-keyed, jointly-evaluated
  dimensions -- account (`login_identity`, real or not, so a nonexistent
  username throttles identically to a real one) and source (the direct TCP
  peer address, never a forwarded header, since this deployment establishes
  no trusted-proxy boundary for one) -- so neither a username spray (one
  source, many accounts) nor a distributed spray (many sources, one
  account) goes unbounded. The first 3 failures add no delay (typo
  tolerance, matching every pre-existing test that already made up to three
  wrong sign-in attempts); every failure after that walks a short, fixed,
  hand-picked ladder (1s/2s/5s/15s/30s/60s) that plateaus at 60 seconds
  forever -- no permanent lockout anywhere, proven directly by driving well
  past the ladder's own length and by a real multi-source distributed-spray
  test confirming ordinary time advancement always restores access. Both
  dimensions are hard-capped at 10,000 live entries with O(1)-amortized
  least-recently-touched eviction/pruning (an `OrderedDict`-backed design)
  -- an earlier plain-`dict`-plus-`min()`-scan version was found, by this
  milestone's own bounded-state tests, to cost several real seconds at
  10,000 simulated attempts, and was fixed before being accepted, closing
  a self-inflicted CPU-cost gap the governing brief's own "high-rate
  attacker must not cause unlimited memory growth" bar reasonably extends
  to cover. **Persistence: in-memory only, deliberately** -- weighed
  explicitly against the brief's own in-memory/persistent/hybrid framework;
  a local-first appliance does not need enterprise-grade persistent
  lockout state, and persisting it would itself become a new, worse
  denial-of-service surface (a throttle row outliving the very restart an
  owner would use to recover). Restart (or a local backup restore's own
  process-wide `ProductRepository` singleton swap -- an already-established
  precedent for resetting this exact class of in-memory session-adjacent
  state) clears all throttle state, which doubles as the owner's whole
  recovery lever if ever throttled themselves -- no new account-recovery
  mechanism was built or is needed. Monotonic clock throughout (never
  wall-clock, immune to NTP/DST/manual-clock changes), constructor-
  injected for fully deterministic tests -- zero real sleeps anywhere in
  either new test file. The outward HTTP contract is unchanged: the
  identical generic `401` for unknown user, wrong password, disabled user,
  and now, additionally, a currently-throttled account/source (even with
  the genuinely correct password) -- verified by a direct response-
  equality regression test comparing all three cases' real status code,
  JSON body, and cookie absence. Three new bounded audit events
  (`auth.login_failed`/`auth.login_throttled`/`auth.login_succeeded_
  after_failures`) reuse the existing `AuditLogEntryModel` mechanism with
  zero schema change, verified to never carry a password or token in their
  metadata; a throttled-while-already-throttled attempt writes no
  additional audit row at all, since it never reaches the database (bounded
  by construction, not a separate suppression rule). No session is ever
  created on a failed or throttled attempt, verified directly against real
  session-table row counts. 31 new tests: `tests/test_login_rate_
  limiter.py` (21, pure unit, fake clock, no DB/HTTP) and `tests/test_
  login_rate_limiting.py` (10, full product integration through real
  `POST /api/auth/sign-in` calls, including genuinely simulated distinct
  source addresses via `httpx.ASGITransport`'s own `client` parameter);
  `tests/test_local_identity_multi_user.py`'s 36 pre-existing tests pass
  unmodified, direct proof of zero behavior change to bootstrap, session
  lifecycle, authorization, review attribution, or backup/restore identity
  semantics. Tier 1 (67 tests across those three files): zero failures.
  Tier 2 (376 tests across 26 files -- every directly auth/security-adjacent
  file plus a deliberately broad, diverse cross-subsystem sample of the
  ~108 pre-existing files whose fixtures depend on the shared lazy
  bootstrap-then-sign-in test client succeeding): zero failures. Tier 3
  deliberately not run -- the change is confined to one repository method,
  one endpoint, and one new, zero-existing-importers file; session
  resolution, authorization tiers, and every other endpoint are untouched
  (confirmed by direct diff inspection), and Tier 2's own 376-test result
  is itself broad empirical confirmation of that narrow blast radius, not
  only a scoping argument. `ruff check`: zero new findings on every new/
  touched file; `product_repository.py`'s 57 pre-existing findings
  confirmed unrelated via a direct `git stash push -u`/`pop` bisection
  (identical count and finding set before and after, zero findings in the
  line ranges this milestone actually touched). No schema change (see
  "Schema," above). `docs/local-identity-multi-user-contract.md` gained a
  new "Login rate limiting / abuse resistance" section plus a "Known
  bounded gaps" entry documenting the disclosed reverse-proxy-source-
  collapse and success-clears-shared-source trade-offs. This closure does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, Lane G monitoring diagnostics, Lane C work, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- authorization returns to the bold
  statement in §3, below, unchanged by this closure.
- **Prior accepted milestone:** Historical Species-Status ("New" vs.
  "Seen Before") Correctness v1 -- see
  [historical-species-status-new-seen-before-correctness-v1-report.md](historical-species-status-new-seen-before-correctness-v1-report.md)
  for the complete record. Classification **A**. A release-correctness
  milestone closing `tests/test_place_biodiversity_summary_repository.py::
  test_api_route_returns_the_summary` and `::test_human_correction_
  updates_place_biodiversity_intelligence_correctly` -- both independently
  reproduced RED against the real, unmodified pre-fix code, matching the
  identical `'seen_before' == 'new'`/empty-`new_taxa` symptom this file's
  own §14 had already independently re-confirmed as pre-existing across at
  least nine consecutive prior full-Core checkpoints, never before given
  its own dedicated root-cause investigation. Root cause: a **test-fixture
  defect, not a product-code defect** -- the test file hardcoded `NOW` to a
  fixed past instant (2026-08-24) used both as fixture data and, in two
  assertions, exercised through the real HTTP routes for `place_
  biodiversity_summary`/`wildlife_journal_history`, both of which are
  deliberately, doctrine-documented "live view" endpoints (confirmed
  independently in three governing docs, including their own contract)
  with no way to inject a test clock -- always anchoring "today" to the
  real wall clock. Once real time moved six days past 2026-08-24, those two
  HTTP-only assertions correctly, per the live-view contract, started
  reading `"seen_before"` instead of `"new"`. The shared canonical
  computation (`compute_species_historical_statuses`/`ProductRepository.
  _historical_place_baseline_and_species_statuses`) was never defective --
  confirmed both by every `now=`-pinned assertion in the same test already
  passing, and against the endpoints' own governing contract docs
  (`docs/biodiversity-place-intelligence-v1-contract.md`, `docs/canonical-
  new-regular-species-contract.md`). Fix: one test file, zero production
  code -- `NOW` now tracks the real wall clock at collection time (pinned
  to noon UTC to avoid local-midnight edge cases) instead of a fixed date,
  plus two new tests closing this endpoint pair's own "subsequent
  occurrence reads seen_before" and "correction to a previously-seen
  species reads seen_before" coverage gaps (both semantic cases already
  proven elsewhere in the shared computation's own test suite, just not
  yet through this specific endpoint pair). Self-inclusion, future-Visit
  non-retroactivity, Reviewed-truth precedence, stale-inference exclusion,
  archived-Stream/Place isolation, and unresolved-label exclusion were each
  independently re-verified (structurally and/or by an existing or new
  passing test) during root-causing, per the governing brief's own
  adversarial-review requirement; one adjacent, unreproduced, out-of-scope
  observation about `place_story`'s own (separate, untouched) consumption
  of the same unbounded all-time aggregate was disclosed rather than
  chased. Tier 1 (23 tests, the implicated file) and Tier 2 (498 tests
  across every consumer of the shared historical-status path -- canonical
  new/regular consistency, Bird Log journal, place activity report, change
  summary, place story/features, regularity/seasonal/temporal patterns,
  dashboard Today, environmental context, ecological interoperability), run
  together: zero failures. Tier 3 (one full Core run, run bare with no
  `slow`-marker deselection): **5277 passed, 0 failed**, 3 skipped, 11
  xfailed -- the first zero-failure full Core checkpoint in at least nine
  consecutive prior attempts, definitively retiring the `test_place_
  biodiversity_summary_repository.py` pair from this section's own
  recurring "pre-existing" accounting (§14, below). `ruff check` clean on
  the one touched file. This closure does **not** authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure. `roadmap.md` was not edited -- this
  milestone is a bounded test-correctness fix, not a roadmap-scope change.
  Lane C's own remaining "New / Regular presentation" item (§6, below) is a
  distinct, still-open UX-presentation gap, not touched or closed by this
  purely computational-truth/test-correctness fix; no evidence surfaced
  that Lane C itself needs a separate reconciliation pass beyond what §6
  already records.
- **Prior accepted milestone:** Release Licensing, Distribution &
  Third-Party Legal Closure v1 -- see
  [release-licensing-distribution-third-party-legal-closure-v1-report.md](release-licensing-distribution-third-party-legal-closure-v1-report.md)
  for the complete record. Classification **B**. A pre-release-decision/
  release-blocking governance milestone (Lane P plus the still-open
  BirdNET commercial-adjacent posture in §2, below) -- confirmed via the
  hard sequencing guard as the highest-priority independent milestone
  available while Gate A's own daylight rerun (Lane R) stays externally
  blocked. Resolved, with durable machine enforcement rather than prose
  alone, both engineering-resolvable items Lane P had left deliberately
  open: **FFmpeg** was traced to every real invocation site
  (`mockingbird.playback.rtsp_bridge`/`local_camera_bridge`/
  `windows_camera_bridge`, all `shutil.which("ffmpeg")`-based) and every
  packaging/build script (zero references anywhere) -- MockingBird never
  bundles, downloads, or vendors an ffmpeg binary in any official package;
  it is a pure external system dependency, already honestly documented in
  `docs/using-mockingbird.md`. A new build-time guard,
  `verify_no_bundled_ffmpeg_binary`, mirrors the pre-existing
  `verify_no_nc_licensed_acoustic_model_redistribution`'s role for BirdNET
  so this posture can never silently reverse; 8 new tests, one of them a
  real integration proof through the unmodified `assemble_windows_bundle`
  call path, not only the guard function in isolation. **Third-party
  notices**: a new `THIRD_PARTY_NOTICES.md` (correct MIT license text and
  copyright provenance for both production-redistributed models -- MDv5a,
  copyright Microsoft Corporation per MegaDetector's own repository;
  BioCLIP-2, per its official model card -- a bounded direct-dependency
  license table verified against each package's own installed metadata
  rather than assumed, and an explicit "deliberately not bundled" account
  of ffmpeg and BirdNET/birdnetlib) now ships inside every official
  Windows bundle via a new `package_third_party_notices` step, which fails
  the build outright if its own source file is ever missing -- previously,
  the redistributed MDv5a/BioCLIP-2 model files carried zero accompanying
  license text at all, unlike every ordinary pip dependency, whose own
  license already travels automatically inside its `dist-info/`. Found and
  fixed one real, previously-undisclosed documentation gap: `docs/using-
  mockingbird.md`, the canonical user-facing guide, never mentioned the
  already-shipped, already-accepted BirdNET/acoustic feature at all --
  added a short, honest "Bird-sound identification (optional)" section
  (optional, separately obtained, differently licensed, never framed as a
  defect). Added a factual "License" section to `README.md` (no
  `LICENSE` file exists; none implied; a pointer to `THIRD_PARTY_NOTICES.md`).
  The MockingBird source-code license itself was deliberately **not**
  self-selected -- the roadmap's own evidence (`docs/roadmap.md` Gate F;
  this file's own prior Lane P text) already states this requires an
  explicit owner decision, not a bounded engineering milestone's authority
  -- the report instead delivers a complete decision packet (MIT
  recommended; Apache-2.0 and a copyleft option named and rejected with
  reasons; every current dependency's license confirmed compatible with
  either permissive option; one exact one-sentence question for the
  owner). Also named, honestly, as neither resolved nor newly blocking:
  the NVIDIA CUDA/cuDNN redistributable packages bundled with GPU builds
  use the same well-established EULA-based pattern official PyTorch/
  TensorFlow GPU wheels already use, but this milestone did not
  independently re-fetch NVIDIA's current EULA text against exactly what
  these pinned packages ship (an engineering interpretation, not a
  repository fact, disclosed as such rather than asserted with false
  certainty); and BirdNET's genuinely ambiguous commercial-adjacent
  private-use question (§2, below) remains exactly as unresolved as
  before, now simply more visibly disclosed to an actual product user
  rather than only an internal contract doc. `tests/test_local_product_
  packaging.py`: 74 passed, 0 failed (4 pre-existing `slow`-marked GPU/
  BioCLIP-dependency-closure tests correctly not re-run -- unrelated to
  this change, unmodified). `ruff check`: clean (zero findings, not merely
  zero new findings) on both changed Python files. No schema change; no
  product/perception/API/frontend code touched -- confined to
  `scripts/build_local_product.py`, its own dedicated test file, one new
  root notices file, and two documentation files. Lane P is now
  reconciled (§6, below) to **one** remaining deliberately-open item
  (down from two) -- the owner's source-code-license decision -- which
  remains a real release blocker for the public launch itself, honestly
  not closed by this milestone. This closure does **not** authorize the
  next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Platform / Runtime Portability & Support
  Truth Closure v1 -- see
  [platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md)
  for the complete record. Classification **A**. A bounded, release-critical
  evidence/documentation closure (Lane O) establishing MockingBird's
  truthful release support matrix across Host operating systems and
  inference runtimes -- not a portability expansion campaign; no new
  platform support was added. Reused rather than re-verified the extensive
  already-accepted native-Windows evidence (Native-Windows Packaged
  Local-Only Acceptance & Privacy Closure v1, Release Engineering
  Foundation v1) to confirm Windows 10/11 x64 as **Validated**: the only
  Host with a packaged, dependency-bundled, no-Python-required end-user
  distributable, with real CUDA execution-provider selection, real
  BioCLIP-2 inference, and a real 18-schema-version organic migration all
  proven at the production code path. Established, for the first time as
  one explicit, coherent, tested story, that MockingBird's accepted
  detector provider (`onnx-cuda`, backing the production `frame-driven-
  onnx-cuda` path) structurally forbids CPU execution by deliberate,
  regression-tested design (`session.disable_cpu_ep_fallback`, a
  CUDA-only provider list, `onnx_cuda_unavailable`/`onnx_cuda_no_fallback`
  raised rather than silently degrading) -- live wildlife detection
  requires a working NVIDIA CUDA GPU with zero fallback -- while both
  optional assistance models (BioCLIP-2 species suggestions, BirdNET
  acoustic identification) are CPU-only by the identical deliberate
  design, already validated, and never block Visit creation when
  unavailable. Classified Linux **structurally supported** at the
  source/dev level (continuously CI-validated on real, non-WSL
  `ubuntu-latest` for the full Core suite, frontend build, and the
  Windows-packaging pipeline's own structural smoke test; a genuine,
  first-class Linux-only feature already exists, the V4L2 local-USB-camera
  bridge) but explicitly **not** promoted to "validated release Host" --
  no packaged end-user Linux distribution exists and no dedicated native-
  Linux hardware acceptance has ever been performed, correcting a prior
  report's own looser use of "Validated" for the identical underlying
  fact. Classified macOS **unverified** overall, with one path
  (microphone capture) already **unsupported** and honestly disclosed
  (fixed in a prior accepted milestone, confirmed still in effect), and
  Apple Silicon acceleration **deferred**, extending rather than
  re-deriving `docs/species-classification-reevaluation-promotion-v2-report.md`'s
  own already-correct "no hardware, not assumed to work" precedent. AMD
  GPU acceleration confirmed **unsupported** -- zero ROCm/DirectML code
  anywhere in the stack. The Camera Node's reference-hardware-vs-hardware-
  agnostic-protocol distinction was verified against real provider code,
  not merely asserted: Raspberry Pi 4/Raspberry Pi OS is the real,
  repeatedly-validated reference device, while a genuine, independent
  `V4L2CameraProvider` (generic Linux/USB via OpenCV) sits behind the same
  `CameraNodeProvider` protocol alongside the Pi-specific backend, each
  degrading gracefully if its own runtime is absent -- no non-Pi hardware
  has ever been release-tested, and none was added this milestone. Found
  two real, reproduced, narrow capability-overclaim defects in `python -m
  mockingbird doctor` (its `SPECIES_IDENTIFICATION` and `GPU_CUDA` checks'
  own PASS branches each silently omitted an honest scope caveat the
  underlying probe already had available, understating how much a PASS
  there actually proves) and fixed both with the minimal truthful
  correction rather than a heavier, costlier re-architecture of either
  check -- each independently reproduced RED via `git stash` against the
  real pre-fix code and confirmed GREEN after, with a new dedicated
  regression test. Two further gaps (the Camera Node's
  `pairing_state_path` retaining a `Path.home()` fallback masked only by
  installer convention; `GET /api/observation-engine/status`'s name
  mismatching the legacy provider it actually wires to, confirmed to have
  zero frontend consumption) were found and precisely disclosed,
  deliberately not fixed, since neither is reproduced against any real or
  currently-shipping path. Published the canonical, plain-language,
  user-facing support matrix in a new "Platform & hardware support"
  section of `docs/using-mockingbird.md`, cross-checked line-by-line
  against the implementation evidence above. `tests/test_doctor.py` (107
  passed) and the directly adjacent `tests/test_doctor_cli.py` (8 passed)
  confirmed via direct grep to be the complete blast radius of the two
  changed functions; `ruff check` clean; full Core correctly not run,
  per the governing brief's own "primarily evidence/documentation"
  validation guidance for a Tier-1/focused change. No schema change. Lane
  O is now reconciled to **closed** (§6, below), resolving its own
  "RELEASE DECISION REQUIRED" status by making support truth explicit
  rather than by claiming any unsupported hardware is supported. This
  closure does **not** authorize the next Representative Field Acceptance
  / Gate A session, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone -- see
  §3, below.
- **Prior accepted milestone:** Sustained-Activity Visit Admission
  Starvation & Stop-Finalization Correctness v1 -- see
  [sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the real P0
  Representative Daylight Gate A Field Acceptance v4 found and disclosed
  (see the "Prior accepted milestone" entry immediately below): ~112 real
  minutes of sustained, near-continuous multi-bird feeder activity
  producing zero admitted Visits for the entire live session, and a real
  Observation stop that did not visibly rescue anything either. Both
  questions are independently root-caused, deterministically reproduced
  RED against the real, unmodified pre-fix code at the real production
  call site, and fixed: (1) nothing previously bounded how long a whole
  connected *ambiguous component* could keep deferring while its own
  currently-active tail kept being refreshed by sustained real activity,
  even though each individual episode was already correctly bounded --
  fixed with a bounded decision horizon that reuses the existing,
  already-calibrated 20-minute episode-span bound verbatim (never a new
  magic number, never the 45-second gap value itself, per the governing
  brief's own explicit instruction not to treat that value as the bug);
  (2) `_EngineSession.stop()`'s own external kill-switch revert ran
  unconditionally the instant its bounded thread-join returned, racing
  the background thread's own correctly-ordered teardown and silently
  discarding an already-force-decided candidate as `blocked_shadow_mode`
  -- fixed by making the join's own actual outcome (finished vs.
  genuinely still running) authoritative, with an honest
  `stop_finalization_pending` status signal for the rare case a caller's
  own bounded patience is exceeded. Investigating the evidence-cache
  bound's own possible contribution (per this milestone's own governing
  brief, not generic cache tuning) found and fixed two further real,
  narrow, pre-existing defects that would otherwise have kept producing
  the identical "zero Visits" symptom one gate later
  (`blocked_missing_evidence`) even after the primary fix: an
  evidence-candidate truncation order that always kept the *earliest*
  (most likely already-evicted) candidates over byte-available later
  ones, and a merged proposal's evidence silently scoped to only its
  *first* constituent generation. Neither the evidence-cache bound's own
  size nor the 45-second gap value were changed by either fix. A
  105-simulated-minute, two-simultaneous-subject stress replay (brief's
  own §18/§10 field-derived stress replay) confirms bounded, non-starved,
  non-duplicated, non-cross-subject-contaminated admission end-to-end,
  with the first admission landing within 25 simulated minutes -- a
  live-session fix, not merely a session-end rescue. 22 new tests, each
  independently confirmed RED against the pre-fix code and GREEN after.
  Tier 2 (the brief's own named subsystem list, 22 files): 505 passed, 0
  failed. Tier 3 (full Core): 5238 passed, 3 failed -- all 3
  independently confirmed unrelated, not merely assumed: the two
  `test_place_biodiversity_summary_repository.py` failures reproduce
  byte-identically on a direct `git stash` pre-milestone-baseline
  bisection; the one `test_transport_worker.py` failure is a genuine,
  pre-existing, timing-sensitive flake, proven directly (three
  consecutive full-file runs of the identical current code produced
  three different outcomes; zero import relationship to any file this
  milestone changed; a direct baseline bisection also passed cleanly) --
  3 skipped, 23 deselected, 11 xfailed, zero regressions attributable to
  this milestone. `ruff check`: zero new findings (clean-baseline
  bisection). No schema change. This closure does **not** itself close
  Lane R/Gate A (no live field session ran, per this milestone's own
  explicit non-goal), and does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v4 -- see
  [representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
  for the complete record. Classification **A**. A real, live ~112-minute
  Observation session against the real reference Camera Node, deployed to
  a genuinely fresh, disposable instance (never the operator's long-lived
  `MockingBirdDev` identity) -- the first real live daylight session run
  under the new Field Acceptance Operator credential mechanism, closing
  the loop that milestone's own report left open. Two real infrastructure
  conflicts were found and resolved live, both with the user's explicit,
  specific approval rather than assumed: the reference Camera Node's
  pairing is single-slot/disk-persisted, so reaching it from a genuinely
  fresh instance required resetting it via the already-documented,
  supported recovery flow (`docs/camera-node-install-guide.md`'s "An
  already-paired Node"), leaving the operator's own `MockingBirdDev`
  instance needing a one-time re-pair before its own next use; and the
  packaged launcher's fixed `127.0.0.1:8000` binding required stopping
  the operator's own instance (confirmed idle first: not monitoring,
  human idle 1+ day; fully reversible). The independent acceptance
  recorder ran the whole session (99.78% coverage); a first-pass blind
  15-second contact-sheet review wrongly concluded zero animal activity,
  self-caught and corrected by cross-referencing the merged (evicted-
  entry-recovered) counterfactual ledger's longest-duration confirmed
  tracks against full-resolution frames at those exact offsets -- real,
  repeated, multi-bird feeder activity (593 confirmed MDv5 animal-class
  tracks, 96.6% at one feeder location, near-continuous for effectively
  the entire session) plus a separate ground-mammal sighting, directly
  visually confirmed, not inferred. Despite this genuine, sustained
  activity, `candidates_created` stayed at exactly 0 for the whole
  session -- a real, previously-undocumented P0 admission-arbitration gap
  was found and precisely root-caused by direct code reading
  (`visit_episode_assembler.py`/`candidate_visit_authority.py`):
  `continuation_pending`/`blocked_ambiguous_boundary` resolution depends
  on a 45-second gap in that specific chain's own activity that
  near-continuous multi-subject activity structurally never produces
  while a session stays live, with session-end finalize as the only
  design-intended escape -- whose real effectiveness is itself now a
  disclosed open question, since this session's own real stop did not
  visibly admit anything either. Zero product code changed: per the
  governing brief's own explicit bar, a trustworthy fix needs
  component-aware forced-decision semantics (not a naive per-proposal
  timeout, which risks reopening the already-fixed transitive-ambiguous-
  component premature-split defect), a threshold calibrated against real
  field evidence, and likely a further look at the already-disclosed
  128-entry evidence-cache bound -- comparable in scope to a full
  milestone, not a bounded change. A second, real, live-checked product
  finding shares the identical root cause: `GET /api/dashboard/summary`
  showed zero signal of any kind after ~112 minutes of real activity --
  the exact "must never look like MockingBird saw nothing" failure mode
  `roadmap.md` already names as unacceptable. Persistence-contention log
  grep: zero occurrences (single Stream, log otherwise completely clean).
  Species assistance: N/A, moot downstream of the admission failure (zero
  Visits ever existed to run BioCLIP against). No release budgets
  proposed -- three real cohorts now span 0% to 68.2% end-to-end Visit
  recall; per the report's own reasoning, that range does not converge
  into a budget until the newly-found defect is fixed and re-measured.
  Does **not** authorize External Pre-Release Acceptance or Final Release
  Hardening, and does **not** select a next development milestone -- see
  §3, below.
- **Prior accepted milestone:** Native-Windows Packaged Local-Only
  Acceptance & Privacy Closure v1 -- see
  [native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md)
  for the complete record. Classification **A**. Closes both material gaps
  Local Only / Privacy Closure v1's own "Remaining risks" left open:
  actual native-Windows packaged runtime, and assets-present MDv5a/
  BioCLIP-2 operation under internet denial. Built and deployed the
  accepted native-Windows packaging path (`scripts/deploy_windows_dev.py`
  over `scripts/build_local_product.py`'s real release logic) to a fresh,
  disposable `--dev-root` -- never the operator's long-lived
  `MockingBirdDev` identity -- with **no skip flags**, so the release
  genuinely carries the full GPU/CUDA and BioCLIP dependency closures plus
  both packaged model bundles. Internet denial used a real, disposable,
  user-mode HTTP(S) egress-filtering proxy (no Administrator token is
  available in this interop session, confirmed directly, so a kernel
  firewall rule was not available -- the same class of environment-
  appropriate substitution the prior milestone made in the other
  direction for WSL): every optional-provider `CONNECT`/request the
  MockingBird process attempted was classified by real destination IP and
  either relayed (loopback/LAN) or refused before any real connection,
  independently corroborated by a live, zero-external-connections
  `Get-NetTCPConnection` snapshot and by the same mechanism separately
  catching a real headless Edge browser's own unrelated background
  telemetry. LAN preservation was proven live, not just configured: a
  proxied request to the project's real reference Camera Node returned a
  real `200` health payload. MDv5a and BioCLIP-2 were both proven
  initializing and running real local inference at the exact production
  code path (not a status flag) -- SHA-256 fingerprints matching this
  project's own accepted provenance record, real CUDA execution-provider
  selection for MDv5a, a real forward pass for BioCLIP-2 -- both before
  and after network denial, with the proxy log showing **zero** entries
  from either run (no download, no HF/network fallback attempted). Caught
  and worked around, before accepting it as evidence, a real environment-
  contamination finding: persistent User-level environment variables left
  over from earlier, unrelated dev sessions on this same Windows machine
  were silently redirecting BioCLIP resolution to a `\\wsl.localhost\...`
  path rather than the packaged bundle -- cleared per-process (never
  touching the persistent value) for every launch this milestone made,
  disclosed plainly as a methodology fact about this specific reused dev
  machine, not a product defect. A real browser render (headless Edge,
  offline, routed through the same proxy) showed the packaged frontend
  rendering correctly -- proper typography, layout, and product copy, zero
  external dependency. All 16 named core workflows were exercised live
  against real seeded product-shaped data, including a real local backup
  (created, verified, confirmed on disk) and a real review correction
  (submitted, immediately reflected). Both live optional-provider drills
  (weather, iNaturalist) degraded gracefully under real forced
  unreachability, with no retry storm and `ready: true` throughout. The
  camera-credential-at-rest question Local Only / Privacy Closure v1 left
  open was resolved by direct code/doc investigation to a documented
  non-defect: credentials are stored plaintext, exactly as the existing
  `docs/local-identity-multi-user-contract.md` already discloses, and no
  contract anywhere promises otherwise. Zero reproduced Local Only/privacy
  defects were found, so zero production code changed;
  `tests/test_local_only_privacy.py` was re-run clean (8/8) as the
  validation evidence, per the governing brief's own explicit guidance not
  to run a full Core gate for a zero-code-change acceptance milestone.
  Worktree safety reconfirmed throughout (the seven preserved untracked
  detector files byte-identical at start and end). Lane N is now
  genuinely, fully reconciled to **closed** (§6, below) -- both proofs the
  prior closure's own classification B explicitly named as missing are
  now real. This closure does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Local Only / Privacy Closure v1 -- see
  [local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)
  for the complete record. Classification **B**. A bounded, release
  -critical privacy/product-correctness milestone (Lane N) proving
  MockingBird's core product works Local Only, with no cloud account,
  contribution pathway, remote service, analytics dependency, external
  telemetry requirement, or provider credential required for ordinary
  use. Two independent bounded static-inventory passes (backend:
  `src/mockingbird/`, `src/mockingbird_node/`, all of `scripts/`,
  `pyproject.toml`/`uv.lock`; frontend: `web/src/` plus the real
  *compiled* `web/dist/assets/*.js` output) found: local production
  inference (MDv5a ONNX, BioCLIP-2, BirdNET) loads exclusively from local
  paths, with `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`/
  `HF_DATASETS_OFFLINE` defense-in-depth already present on the BioCLIP
  path; zero telemetry/analytics/crash-reporting dependency anywhere in
  the packaged dependency closure; zero mandatory external frontend
  runtime asset (only 3 harmless external-origin strings exist in the
  entire shipped JS bundle, none a fetch target); weather (Open-Meteo,
  off by default) and iNaturalist taxonomy lookup (gated by feature use,
  not a settings flag -- named explicitly since a search for only a
  persistent "enabled" flag would undercount it) are the only two live
  explicit-optional-provider call sites reachable from ordinary runtime,
  both already well-hardened (bounded timeouts, typed failure exceptions
  always caught, never poison a cache, never raise); no Derived Data
  Contribution/media-upload pathway is implemented in the codebase at
  all yet (every real "contribution" code hit is an unrelated internal
  scene-confusor-region bookkeeping concept), so contribution privacy is
  presently a non-question rather than a verified opt-in flow, stated
  plainly rather than overclaimed. A real runtime acceptance then ran a
  fresh disposable instance entirely inside a genuine, OS-level,
  unprivileged network namespace (`unshare --net --map-root-user`, real
  loopback confirmed working via an actual "connection refused" on an
  unbound port, every other interface absent -- not a firewall rule that
  could have a gap) -- proving 22 core authenticated API routes plus the
  frontend document and a hashed asset all return `200` with zero
  outbound connection possible; Observation start/stop against the
  seeded demo Stream degrades honestly rather than crashing; a real
  local backup creation succeeds and lands on local disk; and, with
  weather and iNaturalist taxonomy lookup both deliberately enabled and
  forced unreachable, every affected response still degrades gracefully
  (bounded latency across 5 rapid repeats, no retry-storm growth,
  `/api/product/health` stays `ready: true` throughout). A fresh, live,
  separate LAN-reachability check (outside the denied namespace,
  immediately afterward) confirmed the same sandbox that just proved
  zero internet dependency can still reach the project's real reference
  Camera Node over LAN -- direct evidence for the offline-vs-LAN-local
  distinction, not only an assertion of it. Zero reproduced Local Only/
  privacy defects were found, so zero production code changed; 8 new
  tests (`tests/test_local_only_privacy.py`) convert the live proof into
  a fast, hermetic, dependency-injected regression (never a real
  socket), self-verified via call-count assertions on the injected fake
  requesters that caught and fixed one test targeting the wrong endpoint
  before it was counted as passing evidence. Tier 2 (18 files across
  auth/environment-provider/ecological-interoperability/export/dashboard/
  model-adapter areas): 374 passed, 1 skipped, 0 failed. Tier 3 (full
  Core) not run -- this milestone changed zero production code, matching
  this codebase's own established precedent for non-cross-cutting
  changes. `ruff check`: clean on the one new file. Classification **B**,
  not A: every functional acceptance-bar dimension is satisfied with
  real, live evidence, but this session's own runtime acceptance ran the
  Linux/WSL dev checkout rather than the packaged native-Windows
  artifact end users receive, and exercised the model-assets-absent path
  rather than assets-present -- both named explicitly as the one
  material runtime-acceptance dimension left unverified fresh by this
  session, per the governing brief's own B criterion, not because any
  defect was found or is suspected. Lane N is now reconciled to
  **closed** (§6, below) -- see §3, below, for the full accounting. Does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, External Pre-Release Acceptance, or Final Release Hardening,
  and does **not** select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Retention Correctness & Bounded Cleanup
  Closure v1 -- see
  [retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md)
  for the complete record. Classification **A**. A small, bounded,
  release-critical follow-up (Lane M) closing exactly the three
  reproduced retention defects Storage / Retention / Disk-Pressure &
  Recovery Closure v1's own "Remaining risks" disclosed and deliberately
  left unfixed under its own bounded time budget: (1) imported/folder-
  imported media (`create_media_import`/`import_folder_media`, via
  `_create_media_product_records`, which never materializes a
  `VisitEvidenceLink`) was protected forever unconditionally by
  `_storage_retention_evaluation`'s `legacy_representative_evidence`
  bucket, directly contradicting `docs/appliance-storage-privacy-
  recovery-v1-contract.md:159-163`'s own "same active/superseded/
  reviewed rules as any other Visit-linked evidence -- no separate
  contract" claim -- fixed to become eligible once every referencing
  Visit is superseded, on the identical `superseded_evidence_age_days`
  clock `superseded_only_evidence` already uses for linked evidence,
  while remaining protected forever while any referencing Visit stays
  active regardless of review state, exactly matching a linked primary
  frame's own existing protection (reviewed, corrected, unreviewed, and
  folder-imported Visits all explicitly tested; the underlying import
  code creates exactly one asset per import, so the brief's own "cannot
  distinguish original from derived evidence" stop-condition did not
  apply -- there is nothing to distinguish); (2) a `"staging"`
  (interrupted) cleanup batch could only ever be restored, never purged,
  because `purge_storage_cleanup_batch`'s own purge query only ever
  considered items already durably `"quarantined"`, a state an
  interrupted item can structurally never reach on its own -- fixed with
  a new `_resolve_staging_batch_for_purge`, invoked only for a
  `"staging"` batch before the existing, unmodified purge logic runs,
  reusing (never duplicating) the exact reconciliation
  `execute_storage_cleanup` already performs at the end of a clean run
  (refactored into two shared helpers so there is exactly one
  implementation of this transition, not two); a batch that never
  actually moved anything resolves to the real `"failed"` outcome rather
  than a misleading `"purged"`, and one still genuinely ambiguous even
  after a real reconciliation attempt correctly stays rejected rather
  than reporting a false terminal state; (3) `storage_cleanup_history`'s
  own `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` constant never actually bounded
  the underlying `storage_cleanup_batches` table -- only a read-page size
  and an unrelated automatic-purge chunk size -- fixed with a new
  `_prune_storage_cleanup_history`, called at the tail of every write
  path that can newly produce an eligible row (execute/restore/purge),
  pruning the oldest rows beyond the newest 30 among batches in a
  terminal, disk-safe state (purged/restored/failed) only -- a batch
  still holding live `.recovery/<batch_id>/` files is never pruned
  regardless of age, proven directly by a dedicated test seeding a
  400-day-old still-quarantined batch alongside 35 newer purged ones and
  confirming the old-but-live one survives. Reviewed truth verified
  unaffected across all five required cases; DB/media coherence verified
  in both directions (no new dangling reference beyond the same already-
  accepted "row kept forever as audit trail, file gone, every read path
  already handles a clean 404" contract every other purge category
  already relies on; no new orphan file possible, since none of the
  three fixes adds a file-write path -- the pre-existing, already-
  disclosed structural no-DB-owner orphan-media gap is unaffected and was
  not reopened, per the governing brief). No schema change (see
  "Schema," above). 17 new tests (`tests/test_storage_retention.py`,
  39/39 passing), each independently confirmed RED against the pre-fix
  code -- via `git stash` of the production file while it was still
  uncommitted, and later via a direct pre-fix-blob swap once committed --
  and GREEN after. Tier 2 (23 files across storage/retention/imports/
  backup/doctor/visit-curation/review-queue): 329 passed, 0 failed. Tier
  3 (full Core): 5213 passed, 3 failed, 3 skipped, 23 deselected, 11
  xfailed -- all 3 failures independently confirmed unrelated, not merely
  assumed from precedent: a Camera Node picamera2-restoration test
  passing cleanly both in isolation and as its own full file (a
  full-suite-only flake); the identical, independently-reconfirmed
  pre-existing `test_place_biodiversity_summary_repository.py` pair
  (a bird-species historical-status classification defect with zero
  code-path relationship to this milestone's own changes), confirmed
  unrelated by directly swapping the pre-fix (`8572308`) blob back in and
  reproducing the identical failure, then restoring a byte-exact match to
  `HEAD` -- zero regressions attributable to this milestone (Tier 3's own
  long-running process had already imported the module a few minutes
  before a small, purely cosmetic, zero-behavior dead-parameter cleanup
  landed in the implementation commit; that specific increment was
  independently re-verified via a full Tier 1 + partial Tier 2 re-run
  against the exact final code instead of a second full 39-minute Tier 3
  pass for a provably zero-risk difference -- see the milestone report's
  own "Precise sequencing note" for the complete accounting). `ruff
  check`: zero new findings, confirmed by direct clean-baseline
  bisection against this file's own 57 pre-existing, unrelated findings.
  Lane M is now reconciled to **closed** (§6, below) -- see §3, below,
  for the full accounting. Does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Storage / Retention / Disk-Pressure &
  Recovery Closure v1 -- see
  [storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
  for the complete record. Classification **B**. A bounded, release-critical
  storage/reliability milestone (Lane M) that also determined the cause and
  product significance of the Windows Host free-space decline this file's
  own 2026-08-28 Lane R entry (below) first surfaced (`43.07GB -> 18.8GB`,
  2026-08-20 -> 2026-08-28) but left open. Real, directly-measured disk
  accounting (native `powershell.exe` interop against the real Windows dev
  host, not estimated) found the single largest consumer anywhere in the
  investigation: `%LOCALAPPDATA%\MockingBirdDev\runtime\` (the dev-only
  `deploy_windows_dev.py` tool's runtime/model/BioCLIP-model cache) held
  38.5GB across 21 never-pruned entries, including 6.25GB of definite
  orphaned `.staging-*`/`.stale-*` leftovers from interrupted cache
  populations -- a real, previously-disclosed-and-deliberately-deferred gap
  (`docs/windows-dev-deployment-design.md`'s own "Left for follow-up"
  section had judged this "unlikely to matter in practice," a judgment
  real measurement falsifies). Combined with the field-acceptance
  recorder's own real output directory (11.5GB, genuine evidentiary
  artifacts from the project's own real 2026-08-19/08-20/08-21 daylight/
  dusk sessions, not waste), directly-dated entries created inside the
  exact 2026-08-20 -> 2026-08-28 decline window account for roughly 72%
  of the observed 24.27GB decline -- **disposition B: MockingBird
  development/test-artifact accumulation, root-caused, product
  unaffected**. Neither growth path exists in, or is reachable by, a real
  end-user installation: `%LOCALAPPDATA%\MockingBird` (the real production
  runtime home) measures 1.1MB on this same machine, and the real product's
  own upgrade mechanism (Release Engineering Foundation v1) is a
  structurally different, single-version, database-level-pre-migration-
  backup-only design with no multi-version content-addressed cache at all.
  Fixed: a new `gc_cache_command`/`--gc-cache` flag in
  `scripts/deploy_windows_dev.py` implementing exactly the bounded shape
  the design doc's own deferred-follow-up section had already named
  (referenced-hash walk over every currently-on-disk retained release, plus
  an unconditional orphaned-`.staging-*`/`.stale-*` sweep) -- 11 new tests,
  `tests/test_deploy_windows_dev.py`: 123 passed; `ruff check` clean on
  both changed files. Applied live against the real Windows dev host,
  completing cleanly (exit code 0): `%LOCALAPPDATA%\MockingBirdDev` fell
  from 55.7GB to 26.1GB and real `C:` free space rose from ~20-23GB to
  ~51-52GB (96% -> 90% full) in one real, verified pass -- 17 stale release
  directories and 16 unreferenced/orphaned cache entries actually removed
  (`releases/` correctly settling at exactly the 5 protected/kept:
  `a56081a`, `248853a`, `f609c89`, `db8588c`, `80e1bb3`), independently
  cross-confirmed by the matching rise in real `C:` free space (see the
  milestone report for the complete numbers). Separately, deep archaeology
  of the already-accepted storage-
  retention/backup/Doctor product contract (`docs/appliance-storage-
  privacy-recovery-v1-contract.md`, accepted 2026-08-23) -- re-verified,
  not rebuilt, via 349 real, independently re-run passing tests across the
  whole storage/retention/backup/doctor/deploy-tooling family -- found and
  precisely disclosed (not fixed, each safe-direction/non-release-blocking,
  none warranting a rushed change to the highest-stakes retention-
  eligibility code under this milestone's own time bound) one real
  documentation-vs-code mismatch (imported/folder-imported media is
  over-retained forever, contrary to the accepted contract's own explicit
  "same rules as any other Visit-linked evidence" claim -- empirically
  reproduced, zero pre-existing test coverage for this exact path) plus
  three smaller gaps (a `"staging"`-state cleanup batch can only ever be
  restored, never purged; `storage_cleanup_history`'s own
  `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` constant does not actually bound the
  underlying table, only a read-page/chunk size; no orphan-media,
  file-with-no-DB-owner, detection exists anywhere in the product, a
  structural gap distinct from, and confirmed still bounded/low-materiality
  for, the already-accepted Concurrent Candidate Visit Persistence
  Reliability v1 milestone's own disclosed orphan possibility, not
  reopened). No schema change; Tier 3 (full Core) not run, matching this
  codebase's own established precedent for changes confined entirely to
  `scripts/` deployment tooling with zero importers in `src/mockingbird/`
  (Camera Node Upgrade & Compatibility Recovery v1 made the identical call
  for the identical reason). Does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Non-Interactive Field Acceptance
  Authentication & Session Access v1 -- see
  [non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
  for the complete record. Classification **A**. A bounded, release-critical
  security/correctness dependency milestone -- not a product capability --
  closing the recurring field-acceptance authentication blocker three
  consecutive prior attempts hit (2026-08-25, 2026-08-26, 2026-08-28; see
  Lane R, §6, below) without an authentication bypass, without the
  operator's personal credentials, and without weakening production
  security. Adds one new, narrow, parallel, bearer-token-authenticated
  identity -- "Field Acceptance Operator" -- mirroring this codebase's own
  existing Camera Node device-identity-separation precedent rather than
  extending the linear Viewer/Reviewer/Administrator role ladder (the
  required permission shape -- broad Viewer-level reads plus exactly two
  otherwise-Administrator-tier mutations, Observation start/stop, and
  nothing else Administrator-tier -- is not a contiguous prefix of that
  ladder, so no single role-rank placement could express it correctly).
  Checked by the exact same central `install_authorization` gate every
  other request already passes through -- no parallel/insecure auth stack,
  no localhost/header bypass, no anonymous fallback, proven by a dedicated
  negative-test regression suite. Schema `v57 -> v58`: one new additive
  table, `field_acceptance_credentials` (hash-only token storage,
  mandatory bounded expiry -- no permanent-credential path exists in v1 at
  all -- explicit deterministic revocation, auditable creation/revocation/
  use). Provisioning is a bounded new admin CLI
  (`scripts/manage_field_acceptance_credential.py`, Administrator-only,
  never accepts a password as a CLI argument) mirroring the existing
  `repair_review_label_provenance.py` real-HTTP-instance precedent; the
  acceptance tooling itself gained a small stdlib-only client
  (`scripts/field_acceptance_client.py`) reading
  `MOCKINGBIRD_ACCEPTANCE_TOKEN` and failing clearly (never anonymously)
  on every required negative case. Real acceptance proof: provisioned and
  exercised this exact mechanism live against a real running instance of
  this milestone's own implementation commit (native Windows, real SQLite,
  real FastAPI/uvicorn process, `--skip-gpu-runtime --skip-bioclip-runtime`
  since this proof needed the auth/API layer, not detection quality) --
  the identical three endpoints that blocked the three prior field-
  acceptance attempts (`GET /api/streams`, `GET /api/visits`, `POST
  .../observation/start`) all still correctly `401` with no credential,
  then all succeed with the new credential, including a real Observation
  start/stop cycle against the auto-seeded demo Stream, with the
  credential correctly denied (`403`) on unrelated Administrator actions
  and its use distinguishable from a human Administrator's in the audit
  trail; revocation was proven immediate (the identical token fails on its
  very next use). Deployed to an isolated, disposable dev-root -- **not**
  the operator's real `MockingBirdDev` deployment, confirmed untouched
  throughout -- with a disposable bootstrapped Administrator, no live
  operator credentials used anywhere in this milestone's own work,
  matching this file's own standing decision (see the 2026-08-25 Lane R
  entry, below) against asking the operator for real credentials or live
  participation. Environment left in a secure, known, empty state after
  proof (credential revoked, disposable instance and process fully
  removed). Tier 1/2: 20 new tests
  (`tests/test_field_acceptance_authentication.py`) plus 219 across the
  eight pre-existing files this milestone's schema-literal bump touched,
  all passing. Tier 3 (full Core): 5187 passed / 2 failed -- the 2
  failures both the identical, independently-reconfirmed pre-existing
  `test_place_biodiversity_summary_repository.py` pair (a bird-species
  historical-status classification defect with zero code-path relationship
  to this milestone's own changes), confirmed unrelated by a direct
  `git checkout` bisection against this milestone's own true starting HEAD
  (`c03d0b1`), not merely inferred from precedent -- zero regressions
  attributable to this milestone. `ruff check`: zero new findings,
  confirmed by a direct clean-baseline bisection. e2e not run (zero
  `web/src/` changes; the existing suite's cookie-session `storageState`
  bootstrap is untouched and does not intersect this milestone's
  bearer-token mechanism). Concrete residual risk, both disclosed in full
  in the milestone's own report: no login rate-limiting exists anywhere in
  this product (a pre-existing, disclosed gap from Mobile & Remote
  Experience v1, untouched, out of this milestone's scope) -- a
  field-acceptance bearer token is a static secret for its bounded
  lifetime, mitigated by mandatory expiry/hash-only storage/explicit
  revocation but not by any brute-force protection on the token-lookup
  path itself; and the real acceptance proof ran against a disposable
  instance, not the operator's specific long-running real `MockingBirdDev`
  deployment (deliberately, per standing policy), so that specific
  instance still needs its own one-time `create` provisioning step before
  its first non-interactive use -- not a gap in the mechanism, the
  intended minimal human step. This closure does **not** authorize Lane R, the
  next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Whole-Product UI / Accessibility /
  Performance Closure v1 -- see
  [whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
  for the complete record. Classification **A**. Closes Lane Q as an
  integrated pass. A bounded, live browser/keyboard investigation across a
  seeded, product-shaped 371-Visit QA instance (own isolated database, own
  bootstrapped disposable Administrator -- no live credentials used) found
  and fixed one P0 and three P1 defects, each with a RED/GREEN-verified
  regression test and a live before/after confirmation, not merely code
  inspection: (1) manually- and folder-imported Visits (the default,
  promoted camera-less acquisition path) were silently excluded from
  Review Queue's default "Animals" tab regardless of subject_label --
  the real, previously-unidentified root cause of one class of confusion
  this project had repeatedly, incorrectly attributed to
  `reviewed-product-loop.spec.ts` being an unrelated flake across at
  least three prior milestones; (2)-(3) two real keyboard focus-management
  defects in Fast Review (activation, and last-item-in-view completion)
  left focus stranded on `document.body`, found via live keyboard-driven
  browser testing, both fixed with the same "focus the new region's own
  heading" pattern the mobile nav drawer already used correctly; (4) the
  scheduler's disclosed bounded acoustic health/status gap (Lane A) closed
  with the smallest capability-aware addition the brief allowed --
  composed entirely from already-existing facts, never a factor in
  `ready`. Investigated and confirmed NOT regressions: two very-tall-
  looking pages (Stream Detail, Analytics) that turned out to still be
  correctly bounded exactly as the 2026-08-18 "v0.1 Product Flow Gap Pass
  v1" fix intended. Root-caused (not fixed, disclosed) `reviewed-product-
  loop.spec.ts`'s real mechanism for the first time: `ReviewQueuePage.
  tsx`'s `const productMode = true;`, a pre-existing (`1772c36`,
  2026-07-28, predating this milestone by a month), un-toggleable
  constant, makes the legacy markup that spec targets permanently
  unreachable -- test-suite staleness, not a live product defect; fixing
  the spec itself needs a real rewrite against the current flow, left as a
  precisely-scoped, not-yet-started follow-up. Zero horizontal overflow
  found across 40 real combinations (4 required widths x 10 pages);
  measured, not assumed, performance at an 89-item backlog sits at or
  below BioCLIP Status / Review Queue Performance v1's own accepted
  87-item precedent, no regression found or introduced. Full e2e (136
  specs, 8 new): 135 passed / 1 failed -- the one failure the precisely-
  diagnosed pre-existing gap above, independently reproduced identically
  on the unmodified 128-spec baseline (127 passed / 1 failed, byte-
  identical single assertion). Full Core run clean (see §14). `ruff
  check`: zero new findings, confirmed by a direct clean-baseline
  bisection given `product_repository.py`'s 42,600+ line scale. Schema
  unchanged (v57 -> v57). Remaining, disclosed, not blocking: Zone-polygon
  *drawing* (not selection) has no keyboard equivalent (optional/advanced
  feature, pre-existing); a materially larger dead-CSS footprint around
  `.bird-log-entry` than previously documented; a narrow raw-exception-
  text edge case on non-`ApiError` failures. This closure does **not**
  authorize Lane R, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone.
- **Prior accepted milestone:** One-Release Roadmap & Scheduler
  Reconciliation v1 -- documentation/state-governance only, touching zero
  product/test/schema code. See
  [one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
  for the complete record. Classification **A**. Reconciled this file and
  `roadmap.md` to one coherent release doctrine: MockingBird has one
  public release -- no public "v0.1" product stage, no beta product
  release, no separate before-v1.0 roadmap phase. External Pre-Release
  Acceptance (roadmap.md's Gate G, renamed here from its prior "External
  Beta Acceptance") and internal release-candidate builds remain allowed
  as pre-launch validation/engineering mechanics, never a separate product
  stage; this file's own Lane S ("Actual Final Release Hardening") is
  rewritten onto that same readiness-triggered, not version-number
  -triggered, sequencing (External Pre-Release Acceptance -> Final Release
  Hardening -> the one public launch). Renamed this file's own §7
  ("First-public-v0.1 doctrine" -> "One-release doctrine") and §8
  ("Post-v0.1 / before-v1.0 queue" -> "After-release queue"); replaced
  "v0.1 CRITICAL"/"v0.1 blocker"/"v0.1 scope"/"v0.1 requirement" language
  throughout both files with "release-critical"/"release
  blocker"/"release scope"/"release requirement," matching wording
  `roadmap.md` had already adopted for its own "Release gates"/
  "After-release lanes"/"Release non-blockers" headings at an earlier,
  partial reconciliation (`326207b`); fixed several cross-references that
  earlier rename had left dangling ("v0.1 release gates" -> "Release
  gates," "v0.1 non-blockers" -> "Release non-blockers," "Post-v0.1
  lanes" -> "After-release lanes," and a "(see "v0.1 feature freeze,"
  below)" pointer redirected to the section that actually carries that
  content today). Added a short "Four release-shape categories" index to
  §6, above, mapping the existing lettered lanes onto release-critical/
  pre-release-decision/after-release/later-evidence-driven categories
  without removing, renaming, or promoting any of them. `product-
  doctrine.md` was read in full and left unedited -- it already frames the
  release as the real product launch and creates no beta/v0.1 product
  stage. Every dated historical milestone bullet, proper-noun milestone
  title (for example "v0.1 Product Flow Gap Pass v1," "v0.1 Observational
  Quality Closure v1," "v0.1 Acquisition/Ingest Interoperability Closure
  v1"), and historical decision label (the 2026-08-22 "v0.1 feature
  freeze now active" decision, and the reasoning tied to it) was left
  verbatim, since it records what was actually named and decided at the
  time, not current doctrine. No lane, gate, or roadmap capability was
  added, removed, or promoted; no code, test, or schema changed.
- **Prior accepted milestone:** Camera Node Upgrade & Compatibility
  Recovery v1 -- see
  [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).
  Classification **A**. Closes Lane L's one remaining named gap: a Camera
  Node **upgrade** workflow, distinct from the already-accepted install/
  reboot/reprovision/replacement hardening -- see Lane L, §6, below.
  Investigation found the existing installer already had real update/
  rollback *mechanics* (build_id-keyed idempotency, one retained prior
  version); what was missing was a real upgrade *contract*: artifact
  -checksum verification before any mutation (the artifact builder already
  produced `SHA256SUMS`/per-file hashes but nothing ever checked them),
  staged build-and-verify before the live install is touched at all
  (`venv.staging`, `import mockingbird_node.app` as the activation gate),
  automatic recovery when a newly-activated build fails post-update
  verification, and a bounded Node-local wire-protocol compatibility
  classification (`current`/`compatible_older`/`incompatible`/`unknown`,
  styled after the existing `provider_compatibility` convention) -- the
  Host's own real wire-protocol gate (exact-match only, no graduated tier)
  was investigated and deliberately left unchanged, a pre-existing
  accepted decision. Found and fixed, before any real-hardware attempt, a
  real reproduced defect in the already-accepted artifact builder:
  `NODE_FILES` had silently drifted behind `app.py`'s own imports (Remote /
  Intermittent-WAN Transport Foundation v1 added six transport modules
  without updating the packaged file list) -- every fresh install and
  upgrade produced by the accepted builder was completely broken
  (`ModuleNotFoundError` at startup), confirmed by direct reproduction;
  fixed, plus a new fast static import-closure test closing the whole
  class of drift, not just this instance. A 5-angle adversarial
  self-review before real-hardware acceptance found and fixed 8 further
  correctness issues in this milestone's own new code (most notably: the
  original activation-recovery design, keyed only on whether a staging
  directory still existed, missed a real crash window a manifest-first,
  build-id-reconciliation redesign closes completely; and a plain,
  successful, directly-requested `--rollback` was originally misreported
  as a failed upgrade). Real acceptance against the project's actual
  reference Pi -- which had never been upgraded since 2026-08-18, predating
  three later accepted Camera Node milestones entirely -- found and fixed
  two further real defects live: a universal, upgrade-blocking crash
  (`transport_spool_dir` defaulting through a `Path.home()`-derived path
  that is always broken under the already-accepted `ProtectHome=true`
  hardening, regardless of whether transport was ever configured -- would
  have broken *every* Camera Node upgrading past the transport milestone
  through the accepted installer, not just this device), and two
  automatic-recovery gaps (`systemctl restart` failing outright did not
  trigger automatic rollback; a preceding crash loop's exhausted
  `StartLimitBurst` blocked an unrelated later restart) -- both found live,
  both fixed the same session with dedicated regression tests, not merely
  disclosed. The device was then successfully, fully upgraded end to end
  (node identity, pairing credential hash, and camera availability all
  confirmed byte-identical/unchanged before and after; new boot-identity/
  self-test/watchdog capabilities live on real hardware for the first
  time), with a real idempotent re-run confirmed afterward. One honest
  reservation against an unqualified top classification: `rollback()`
  restores code but not an already-changed systemd unit template, a real
  gap this session's own recovery encountered and worked around manually
  (a temporary drop-in) rather than closed structurally -- disclosed, not
  hidden. Tier 1 (114 tests across `test_install_camera_node.py`/
  `test_camera_node_packaging.py`/`test_camera_node_config_transport.py`/
  `test_camera_node_real_process.py`, all passing), Tier 2 (the full
  `camera_node`/`doctor` test family, 493 passed / 0 failed fast-tier plus
  17 passed / 0 failed slow-tier), `ruff check` clean. Tier 3 not run --
  every changed line sits in `scripts/` deployment tooling or the
  deliberately main-app-isolated `mockingbird_node` package (confirmed by
  direct `grep`: zero importers of either in `src/mockingbird/`); real
  hardware acceptance is stronger evidence for this milestone's actual
  scope than an unrelated 5000+ test Core run. No schema change; no
  product/perception/database/API code touched.
- **Prior accepted milestone:** Representative Multi-Camera Field
  Acceptance & Release-Budget Evidence v1 -- see
  [representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
  Classification **B** -- no live field session ran (session start, 20:26
  EDT 2026-08-26, was after sunset -- the same "darkness produces an
  unusable bird denominator" scenario this project has already hit twice
  before, 2026-08-19/2026-08-20; this milestone's own governing brief
  names exactly this as the case to not manufacture a field result under).
  Executed the brief's own "no representative conditions" path instead:
  re-verified every precondition a live daylight session needs (Camera
  Node network reachability, GPU/detector idle and available, disk
  headroom, the exact acceptance-recorder env-var settings/structured-log
  path, the exact command/API sequence, minimum run duration), and --
  while proving "the current deployed build contains accepted HEAD" --
  found and fixed one real, previously-hidden defect: a fresh, full-
  fidelity Windows dev build of the then-current accepted HEAD
  (`db8588c`) failed outright with a genuine `LocalProductBuildError`
  (site-packages ended up with two different `click` versions, 8.4.2 and
  8.5.0, installed by two independent dependency-install tiers -- the
  identical mechanism, and identical one-line-pin fix shape, as this same
  file's own already-documented `idna` pin). Validated RED->GREEN against
  an existing test that already covered this exact shape but had never
  been run against today's live PyPI state
  (`test_real_windows_bioclip_dependency_closure_installs_offline_with_no_duplicates`);
  full `test_local_product_packaging.py` (66 fast + 4 slow) passing;
  `ruff check` clean; Tier 3 not run (change isolated to Windows packaging
  tooling, zero import relationship to the Core suite). Re-deployed after
  the fix and independently re-verified via direct HTTP (`GET
  /api/product/instance`/`/api/product/health`: `git_commit` exact match,
  schema `57`, `ready: true`) that the deployed artifact carries the fix
  (`click-8.4.2.dist-info` the only `click` entry anywhere in it), then
  stopped it cleanly, leaving `db8588c` a retained, ledger-verified
  release ready for instant relaunch. Also learned, via the
  unauthenticated health endpoint only (no credentials used, matching the
  standing decision below): only one real Stream (the reference Camera
  Node) is currently configured in this dev instance -- a second real,
  already-supported Windows-USB-webcam Source (hardware-validated for the
  prior Acoustic milestone) is not yet wired up, and should be added as a
  genuine second Stream before the next live session, so this project's
  still-open "does the concurrent-persistence fix hold under genuine
  multi-camera load" question can actually be tested with two real
  cameras. No product/perception/admission/Visit/evidence/classification
  code touched; no schema change; Gate A evidence body unchanged (zero new
  field-cohort minutes gathered) -- no release budgets proposed. See Lane
  R, §6, below, for the Gate A/field-acceptance-specific record.
- **Prior accepted milestone:** Concurrent Candidate Visit Persistence
  Reliability v1 -- see
  [concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
  Classification **A** -- a bounded correctness milestone, not a further
  Multi-Camera product pass, closing the real, disclosed occasional
  lost-candidate-Visit concurrent-write reliability gap Multi-Camera Place
  Experience v2 found, root-caused, and deliberately left unfixed (its own
  bounded transient-retry attempt did not reliably close the gap and was
  reverted). Root cause confirmed directly (a real captured
  `sqlalchemy.exc.OperationalError: database is locked` stack trace under
  real concurrent multi-Stream SQLite writes) and reproduced
  deterministically on demand (a real second SQLite connection holding a
  real write lock, independent of host load) -- not merely inferred.
  `create_candidate_visit_from_proposal` was already idempotent
  (`proposal_id`-keyed) and fully transactional (a failed attempt rolls
  back completely, already proven by a pre-existing test), which made a
  bounded, classified retry provably safe. Fixed by (1) classifying the
  one demonstrated SQLite lock/busy shape as a new, narrow, retryable code
  distinct from every other repository failure, and (2) a bounded
  (3-attempt), short jittered-backoff retry at the *caller* boundary
  (`candidate_visit_adapter.attempt_candidate`) -- deliberately not inside
  the repository method again, which is what the reverted attempt already
  tried. No schema change; no change to Reviewed truth, concurrent-sibling
  Event reuse, or ambiguous-boundary arbitration. 4 new tests (1
  deterministic real-SQLite-lock end-to-end test, 3 fast mock-based
  tests), each independently confirmed RED against the pre-fix code and
  GREEN after. Tier 1/2: 231 passed, 0 failed. Tier 3 (full Core gate):
  5109 passed, 3 failed -- 2 already-disclosed pre-existing
  (`test_place_biodiversity_summary_repository.py`) and 1
  (`test_transport_worker.py`) confirmed unrelated by import-graph proof
  (a separate Camera Node-side package, zero code path to either changed
  file) plus a clean 5/5 re-run in isolation -- zero regressions
  attributable to this milestone. See the report for full detail,
  including honestly-disclosed remaining risk (an orphaned-media-file edge
  case on a failed-then-retried attempt, pre-existing and not introduced
  by this fix; the write transaction still does more work than strictly
  minimal while holding SQLite's lock, a real but separately-scoped future
  opportunity; WAL mode/a higher `busy_timeout` were not empirically
  tested, deliberately, given this exact codebase's own documented prior
  negative result from changing the shared engine's transaction
  configuration).
- **Prior accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views (see
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)).
  Classification **B** -- an integrated multi-camera product pass on top
  of the already-accepted Camera/Source + Multi-Camera Maturity v1
  foundation (cross-camera association engine, Area vocabulary, provider
  compatibility -- that milestone's own report had gone missing from this
  file's own bookkeeping, corrected here). A real correctness defect found
  and fixed with principled nuance across two rounds of correction (Tier 1
  test evidence, then a full Tier 3 Core run) rather than a blanket
  overcorrection: an archived camera's history was unreachable from every
  discovery surface; the fix preserves every already-tested current-
  active-observatory default exactly (Bird Log overview, Wildlife
  Insights, Biodiversity, Place Activity Report/Today) while making that
  real history reachable by explicit camera selection, with Place Story
  and research/conservation export unconditionally inclusive where no
  existing test disagreed. Today now surfaces its own already-computed
  per-camera activity/evidence-source facts for the first time; Bird Log's
  camera filter now reaches its overview list; Zone Insights' Place-wide
  aggregate coverage was a naive camera-hours sum, now a real elapsed-time
  union matching Today's own semantics; Dashboard distinguishes "some
  cameras need attention" from "every armed camera needs attention"; a
  real, measured concurrency proof (genuine concurrent threads, 2-camera
  and 4-camera-asymmetric topologies) found zero cross-Stream contamination
  and no starvation, and separately found, root-caused, and honestly
  disclosed (not shipped -- an attempted fix did not reliably help) a real
  occasional lost-candidate-Visit reliability gap under real concurrent
  write contention; a comprehensive, real, executable 3-camera product-
  shaped scenario proves the whole chain -- identity, coverage, overlap
  dedup, health, correction propagation -- coheres end to end. See the
  report for full detail and honestly-disclosed remaining gaps.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology (see
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
  Classification **B** -- a real, working, submission-ready iNaturalist
  workflow (eligibility preview with per-record reasons, explicit never-
  inferred location/media consent, batch prepare, a destination-shaped CSV
  confirmed directly against iNaturalist's own open-source bulk-import
  code, fingerprint-based staleness detection, and a self-reported
  external-result close-the-loop step -- proven end to end by a real,
  executable 12-Visit product-shaped scenario test) plus a bounded,
  additive Darwin Core Occurrence-core export (`basisOfRecord=
  "MachineObservation"`, GBIF's own recommended camera-trap value); eBird
  and direct GBIF publication both honestly, evidence-backed deferred
  rather than built -- eBird's own current "Rules and Best Practices"
  (checked 2026-08-25) explicitly excludes feeder/trail-camera data
  ("eBird is designed to collect in-person observations of living wild
  birds"), and GBIF direct publication requires organizational
  Participant-Node endorsement, not a backyard-user workflow. No live,
  authenticated destination submission exists anywhere in this milestone
  (Phase 26: no unsafe credential-storage workaround invented) -- a user
  uploads the generated file themselves. Two real security findings made
  and fixed during the milestone's own work: a CSV-injection gap in the
  one shared CSV writer behind every export in this codebase (generic
  research export, Camtrap DP, Darwin Core, and the new ecological CSV
  alike), and a `javascript:`-scheme external-URL gap on the self-reported
  result field. See the report for the full official-source destination
  research (URLs, quotes, access dates) and real, honestly-recorded
  remaining gaps (no live OAuth submit, no media-byte inclusion, no
  single-Visit deep-link pre-selection).
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters (see
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
  Classification **B** -- a real canonical attention-selection layer
  (`ProductRepository.sync_attention_signals`) composed entirely over
  already-accepted facts (`place_story`, `daily_digest`/its weekly reuse,
  the existing `ProductAlertModel` review/monitoring/storage/journal alert
  system), never a second computation path; genuine semantic-dedup work
  (two real double-notification anti-patterns found and fixed by tests, not
  merely by review -- first-seen vs. the 1st-species diversity milestone, and
  the underlying "first confirmed" fact computed two different ways in two
  different subsystems); reused, not reinvented, health/storage debounce;
  new per-user notification preferences (the product's first per-user
  settings row) with quiet hours evaluated in the viewer's own browser-local
  time (deliberately avoiding a server/Place timezone that does not exist);
  foreground-only browser-notification delivery (Phase 22 Decision B --
  Web Push explicitly evaluated and deferred, no cloud/push infrastructure
  added); a real, executable Monday-through-Sunday product-shaped quiet-week
  test proving the whole week stays calm (<=14 total attention items, zero
  ever `immediate` urgency). See the report for real, honestly-recorded
  remaining gaps (Web Push, detector/model-unavailable health attention,
  global not-per-user read/dismiss state, coarse Place Story deep-link
  scoping).
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk (see
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
  Classification **B** -- strong mobile experience and a clear secure
  remote posture with bounded external-network/PWA gaps. A verified
  navigation fix (a ~20-item sidebar that previously stacked in full above
  every page's own content below 980px is now a compact top bar + off-
  canvas drawer + 4-item bottom nav, proven overflow-free across 10 real
  automated phone-width screenshots); a from-scratch bounded PWA shell
  (manifest, icons, a service worker that only ever caches Vite's own
  immutable hashed assets, never navigation/API/data); LAN access made
  genuinely discoverable (`GET /api/product/connection` + a new Settings
  card); a private-overlay-network (Tailscale-compatible) remote-access
  posture investigated against real architecture and documented, with
  direct public-internet exposure and a cloud relay explicitly not built;
  new CORS regression coverage where none existed. Also closed, ahead of
  the broader mobile work, a bounded pre-existing correctness defect in
  the accepted Place Intelligence primitive `place_change_summary.py`
  (see "Bounded return-after-absence correction," below). Schema
  unchanged. See the report for real, honestly-recorded remaining gaps
  (Visit/Stream/Settings page density, a pre-existing Review Queue
  `product_category` data gap, no login rate-limiting, no live external-
  overlay-network validation possible in this sandbox).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place (see
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
  Classification **B** -- major useful capability, bounded history/story
  gaps (period summaries not built, pending a measured performance cost;
  environmental-context/weather caveats not yet composed onto a
  before/after insight; no dedicated taxon/Feature story page; no
  representative imagery on Story cards -- see the report's "Remaining
  major PRODUCT opportunities"). Schema unchanged (v55 -> v55): a pure
  derived read-model (`mockingbird.analytics.place_story.PlaceStoryEvent`)
  composed entirely from already-authoritative facts, no new table.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding (see
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
  Classification **B** -- major useful capability, bounded feature/data-
  model maturity gaps (environmental-context/weather caveats not yet
  composed onto a before/after result; a Feature can only link to one
  camera/Zone; no representative evidence or ranked comparison view yet --
  see the report's "Remaining major PRODUCT opportunities"). Two new
  additive tables (schema 54 -> 55): `PlaceFeatureModel` and
  `PlaceFeatureChangeEventModel` -- the first discrete before/after
  change-event model in this codebase, closing a gap two prior milestones
  both explicitly recorded as their own honest ceiling.
- **Push state:** Local accepted state. Do not push without explicit
  authorization.
- **Production detector:** MDv5a ONNX
- **Production threshold:** `0.1`
- **Production visual species-identification system:** BioCLIP-2 +
  Identification Eligibility / Abstention

**BioCLIP 2.5.** Explicitly rejected for release promotion. Reason: it
improved positive bird identification but showed unacceptable
confident-wrong/non-abstaining behavior on real hard negatives.

**SpeciesNet.** Not production bird identification. It remains an
unpromoted broader-wildlife lead based on external-domain mammal evidence,
pending genuine MockingBird-field evidence.

## 2. Current acoustic release state

**Acoustic / BirdNET: ACCEPTED -- RELEASE-READY OPTIONAL.** The milestone
is complete and frozen unless concrete evidence exposes a defect.

Established facts:

- substantial acoustic/runtime/multimodal functionality exists;
- `birdnetlib` code is Apache-2.0;
- the BirdNET model weights used by MockingBird are CC BY-NC-SA 4.0 /
  NonCommercial;
- official MockingBird packaging must not redistribute those BirdNET model
  weights;
- a build-time guard (`verify_no_nc_licensed_acoustic_model_redistribution`
  in `scripts/build_local_product.py`) now enforces that packaging
  boundary;
- BirdNET/model acquisition remains external and optional (the
  `classifier-birdnet` pip extra -- a dependency declaration, not a
  redistribution);
- core visual MockingBird remains functional without BirdNET;
- real Windows USB microphone capture has been validated;
- real BirdNET inference over captured audio has been validated;
- concurrent visual + audio capture has been validated;
- device failure/reconnect behavior has been exercised;
- Today/Bird Log multimodal count/row contradiction was fixed;
- macOS unsupported mic behavior now fails honestly;
- the documented BirdNET confidence environment setting now actually
  works;
- an unbounded acoustic in-memory segment list was bounded.

Remaining bounded gaps -- classified as bounded product/field gaps, **not**
reasons to reopen the acoustic architecture:

- no true physical mid-session microphone unplug acceptance;
- no multi-hour acoustic soak;
- no natural wild-bird acoustic field session from the accepted test
  hardware;
- no audio equivalent of visual Privacy Zone redaction/exclusion beyond
  the currently documented privacy boundary.

**Corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1:** "no product-facing frontend acoustic
health/status surface yet" (formerly the first item above) is removed --
closed by Whole-Product UI / Accessibility / Performance Closure v1
(2026-08-27), same fact and same correction as Lane A, §6.A, below.

Acoustics are optional in the public release because of
licensing/distribution posture, not because the core implementation is
considered merely experimental.

**Licensing posture.** Commercial use of the BirdNET model weights is
**not** legally approved. Deliberately bundling/redistributing the model
into a commercially-directed distribution (paid support, a
crowdfunded/paid appliance, a hosted paid service) is not allowed under CC
BY-NC-SA 4.0 -- the clear case that license exists to restrict. Whether an
individual user's own private, non-commercial use of MockingBird+BirdNET
(the model is never redistributed by MockingBird itself) could ever be
implicated merely because the surrounding open-source project also accepts
donations or sells optional paid support remains genuinely **unresolved**;
the existing acceptance record recommends legal review before any
commercial-adjacent distribution decision actually touches the acoustic
feature, and does not resolve the question itself. This caveat is
preserved here, not relaxed. Release Licensing, Distribution & Third-Party
Legal Closure v1 (see §1/§3, above) re-verified the enforcement mechanism
behind this posture still works (`verify_no_nc_licensed_acoustic_model_
redistribution`, unchanged) and, for the first time, surfaced this
boundary to an actual product user (`docs/using-mockingbird.md`'s new
"Bird-sound identification (optional)" section; `THIRD_PARTY_NOTICES.md`)
-- it did not resolve the unresolved question above, which remains
exactly as open as stated.

## 3. Current authorized milestone

**Recorded, 2026-09-25, by Today Truth Regression Repair v1.**

**Accepted delta.** *Native-Windows Field Reliability Corrections v1* is
**accepted at `83a0e86`, schema `v61`** -- validation state carried forward
unchanged from its own record below and in
[native-windows-field-reliability-corrections-v1-report.md](native-windows-field-reliability-corrections-v1-report.md).
*Field Validation Closure v1* **remains unaccepted**, because the Today truth
regression that milestone's closure pass newly identified (§3's
"newly identified release-blocker CANDIDATE," below) was judged a **v0.1
blocker**. `Q-2`, `Q-4` and the stale `camera_connected` field keep their
existing disposition: **nonblocking, deferred, not fixed.**

**Authorized.** *Today Truth Regression Repair v1* -- one bounded
correctness milestone during the feature freeze, and **the only authorized
milestone**. Its product purpose is to preserve Discover -> Confirm ->
Remember: confirming wildlife must not make that wildlife disappear from
Today's relevant summaries and highlights. See
[today-truth-regression-repair-v1-contract.md](today-truth-regression-repair-v1-contract.md)
and
[today-truth-regression-repair-v1-report.md](today-truth-regression-repair-v1-report.md).

**Status: IMPLEMENTED, pending acceptance.** Committed locally, not pushed.
Schema **v61, unchanged**; version `0.1.0`, unchanged. One production file
changed: `src/mockingbird/repository/product_repository.py`.

- **Root cause.** `_preloaded_motion_evidence_for_review_queue_item`
  returned an *authoritative* `None` -- not its `_PRELOAD_MISS` sentinel --
  for any Visit/Event absent from Review Queue Scale Closure v1's bulk
  preload. A target with no MotionEvidence and a target never fetched are
  both simply absent from the map; the code read the second as the first.
  Because `_read_only_build_cache` is shared by nested builds, and
  `dashboard_summary` runs the queue build and *then* Today inside one
  cache, Today's reviewed/confirmed Visits -- not queue members -- were
  told they had no evidence, and `detector_qualified_animal_visit_count`
  collapsed toward `0`.
- **Blast radius, swept rather than assumed.** Three lookups consult that
  cache. Today's two day loops were wrong; the queue's own **visit-less
  Event lane** was also wrong (a second, previously unreported in-queue
  manifestation, found by the trace, not by the failing tests); the Visit
  loop was correct only by predicate coincidence; the pending-suggestion
  preload was latent; `media_asset_by_local_path` was never exposed. The
  four identification/BioCLIP paths open no build cache and always queried.
- **Repair.** Each preload now carries the exact id set it fetched, and
  `covers()` is the only thing that authorises a cached answer; a lookup
  whose Visit *or* Event side is uncovered falls through. Media filtering,
  union deduplication, newest-first `(created_at, id)` ordering including
  ties, nested-cache lifetime and cleanup, queue membership/order/
  classification are all preserved. **The accepted optimization is not
  disabled or reverted** -- it is made correct and then extended, so Today
  and the visit-less Event lane declare their own bounded row sets and get
  one bulk read instead of one round trip per row.
- **Evidence.** All seven recorded regression tests fail at `83a0e86` and
  pass after; 14 new focused tests (six of which also fail at the
  unrepaired baseline) assert every lookup case **twice** -- cached and
  uncached -- and require the two answers to agree. Product flow, identical
  isolated data: confirming four animal Visits took Today's count 4 -> 1 ->
  **0** with "Best moments" **empty** before, and holds it at **4** with
  each species in "New today" exactly once after. The canonical Today
  report (`place_activity_report`) was correct on both sides -- a separate
  computation path, which is why its correctness was never evidence that
  the Dashboard Today panel was fine.
- **Query performance, identical data.** Review-queue statement counts are
  `+1` flat (68 -> 69 at both 25 and 205 Visits; 300 -> 301 with 60
  visit-less Events); `dashboard_summary` is `+2` flat regardless of the
  day's size (437 -> 439 at 10 confirmed Visits, 2,547 -> 2,549 at 100),
  while the counts go from a wrong `5` to a correct `15` and `105`.
  Established scale guarantees are retained and structurally locked down.
- **Core gate, on the committed code:** `6 failed, 6225 passed, 4 skipped,
  35 deselected, 11 xfailed` (0:45:53). **All seven recorded regression
  failures are gone**, and **zero failures are attributable to this
  milestone**: all six remaining reproduce in isolation and fail
  *identically* at the pre-repair baseline with only the one tracked
  production file reverted, and all six are members of the established
  recorded six-set. The prior accepted checkpoint was `11 failed, 6205
  passed`. Also clean: frontend type-check and production build,
  `python -m mockingbird --check`, a hardware-free product smoke over HTTP
  on a disposable instance, and zero new `ruff` findings.
- **No schema, public API, review-authority, model, camera-status,
  recovery or production-configuration change.** No hardware session,
  packaging rebuild or Full gate was required by this cache-only scope.
- **Disclosed:** at least two *other* Claude sessions were active in this
  working tree during the milestone -- one briefed on the same defect
  (it detected the uncommitted work, stopped before editing, stood down,
  and contributed a review finding now committed as `19ae391`), and a
  third running a wide `pytest` sweep against the uncommitted tree whose
  results are **not** a `83a0e86` baseline. See the report's §J.

**This entry authorizes no further milestone.** *Field Validation Closure
v1* remains unaccepted; the remaining release queue in §6 is unchanged.

---

**Recorded, 2026-09-25, by Native-Windows Field Reliability Corrections v1.**

*Field Validation Closure v1* **executed at `8a45d1a` but is NOT accepted** --
it is awaiting exactly two field corrections. Its report is valid evidence of
what the `d5dd1d9` build did and is preserved unchanged; two of the four
defects it disclosed (`Q-1` native-Windows local time falling back to a fixed
UTC offset, and `Q-3` observation not resuming after a Host restart) were
judged v0.1-critical and had to be fixed before that acceptance decision could
be made.

*Native-Windows Field Reliability Corrections v1* was **authorized** as that
bounded correction milestone -- fix exactly those two blockers and their direct
dependencies, nothing else, with mandatory repeat validation on the same real
native-Windows Host + real Camera Node topology. See
[native-windows-field-reliability-corrections-v1-contract.md](native-windows-field-reliability-corrections-v1-contract.md)
and
[native-windows-field-reliability-corrections-v1-report.md](native-windows-field-reliability-corrections-v1-report.md).

**Concrete correction evidence, implemented at HEAD `15691d9`, schema
`v60 -> v61`:**

- **Blocker 1 (Q-1) CLOSED.** Two independent faults, both required: no
  Windows -> IANA zone-name derivation existed anywhere in the product (so the
  resolver always reached its fixed-offset fallback), and `tzdata` was not
  packaged either (both `astral` and `tzlocal` declare it conditionally for
  Windows, but `install_windows_runtime_dependencies` resolves environment
  markers against the Linux build host while only wheel *tags* honor
  `--platform win_amd64`). `tzlocal`'s CLDR `windowsZones` mapping is now
  resolution step 3 -- after `TZ` and `/etc/localtime`, so no Linux/macOS
  resolution changes -- and `tzdata` is packaged explicitly. Proven in the
  deployed packaged runtime on the real Host: `TimeZoneKeyName "Eastern
  Standard Time" -> America/New_York`; `2026-12-15 16:00Z -> 11:00 EST-0500`
  (was `12:00 "Eastern Daylight Time-0400"`); `2026-07-15 16:00Z -> 12:00
  EDT-0400`; both DST transitions correct on both sides; Doctor's Clock check
  now reports `America/New_York` live. No stored timestamp rewritten, API UTC
  fields unchanged, Local Only preserved, no external timezone service.
- **Blocker 2 (Q-3) CLOSED.** The resume mechanism was never missing --
  `CameraNodeRecoverySupervisor` reads an *in-memory* session status, which a
  Host restart destroys; what was missing was a durable record of whether
  observation *should* be active. New `stream_observation_intents` table
  (schema `v61`, one additive table, one row per Stream), written at the
  product action and deliberately never at a runtime teardown -- which makes a
  clean restart and an abrupt kill one mechanism rather than two. Proven on the
  real topology with **no manual action**: graceful restart resumed in ~12 s
  with fresh frames and zero duplicate Stream/Source/session/Reviewed state; a
  deliberately stopped observation **stayed stopped** across a restart (20
  polls / ~6 min, Node never probed); a Host started while the Node was
  unavailable resumed ~29 s after the Node returned; an **abrupt
  `Stop-Process -Force`** also resumed automatically. `PRAGMA quick_check` ok,
  0 duplicate Visit ids, Reviewed truth unchanged, no media loss.

**This entry does not claim global acceptance of Field Validation Closure v1**
-- that decision is the owner's/ChatGPT's, and the addendum in
[field-validation-closure-v1-report.md](field-validation-closure-v1-report.md)
exists so it can be made. `Q-2` (stale Camera Node startup self-test) and `Q-4`
(camera-re-initialisation false-Visit burst) remain **open and deliberately
unfixed**; neither was a dependency of either correction, and neither is a
v0.1 blocker. This entry **authorizes no further milestone**: *Documentation /
Diagnostics / Release Engineering Closure* remains unauthorized until Field
Validation Closure v1 is accepted.

### Acceptance-closure record (2026-09-25)

The correction milestone's remaining acceptance work is complete.

| | |
| --- | --- |
| Correction implementation HEAD | `15691d9` |
| Field-evidence HEAD | `2cdb39b` |
| Schema | **v61** (`v60 -> v61`, one additive table); version `0.1.0` unchanged |
| **Final Core result** | **`11 failed, 6205 passed, 4 skipped, 35 deselected, 11 xfailed` (0:41:00) -- ZERO failures attributable to this milestone** |
| Core attribution method | all eleven reproduce deterministically in isolation, and all eleven fail **identically at the pre-correction baseline `8a45d1a`**. Four are the established recorded pre-existing set; seven were bisected to `3d78f8a` (Review Queue Scale Closure v1, 2026-09-23) -- `73dbcd4` PASS -> `3d78f8a` FAIL, direct parent, so the attribution is exact |
| Real-hardware evidence | real Windows 10 Pro Host + real Raspberry Pi 4 Camera Node (`node-76ec8e53ae586dd0`, real `ov64a40` CSI camera); build confirmed via the product's own `GET /api/product/instance`; four Host restarts; v60 -> v61 migration of a real 169-Visit / 343-asset field database with all counts intact and **0 intent rows** |
| Protected files | all seven re-verified byte-identical to their hashes of record and still untracked; `uv.lock` untouched. Working tree carries those eight untracked files and nothing else |
| Push | **not pushed.** No tag, no publish, no remote operation |

**Disposition of the stale `camera_connected` field: nonblocking deferred
field-quality issue, NOT fixed.** Traced producer to consumer. It *is*
user-facing -- `ObservationControlPanel` renders "Camera Healthy" from it on
Stream detail and in the onboarding wizard -- so branch A's "not user-facing"
premise is **not** claimed. But it is a bounded **300 s** heartbeat freshness
window (`CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS`), past which the same
projection reports `camera_connected: false` / "Camera Node offline -- last seen
N minute(s) ago", with existing passing regression tests on **both** sides; the
field observation fell inside that window (~186 s). No recovery, resume,
admission or control-flow path reads the field -- only display. Changing it would
reverse an accepted product decision encoded in a currently-passing test, which
is a product change rather than a narrow repair, and so outside this milestone's
authorization. Live-probe/recovery behaviour and Node self-test behaviour were
untouched. Full reasoning: corrections report §O.

**Durable observation-intent contract, migration safety and field integrity** are
recorded clause by clause, each against a named passing test or a field
observation, in the corrections report's "Closure confirmations" section.

**Remaining Q-2 / Q-4: both open, both deliberately unfixed, and NEITHER is
release-blocking.** Q-2 (stale Camera Node startup self-test) is invisible in the
product -- the Host never reads it -- and pessimistic in direction. Q-4
(false-Visit burst during camera re-initialisation) is within accepted, disclosed
product behaviour, human review being the product's answer to false Visits.

**One newly identified release-blocker CANDIDATE, belonging to a prior
milestone.** While classifying the Core run, `dashboard_summary`'s Today counts
were found to collapse toward `0` for reviewed/confirmed Visits: a review-queue
bulk preload sharing the same read cache answers Today's motion-evidence lookups
with an authoritative `None` for Visits the queue never covered
(`_preloaded_motion_evidence_for_review_queue_item` returns `None` instead of its
`_PRELOAD_MISS` sentinel; `_read_only_build_cache` has nested builds share the
outermost cache). Introduced by `3d78f8a`, present at `8a45d1a`, therefore
present in the build Field Validation Closure v1 validated -- its §U verdict of
"no remaining v0.1 field blockers" was reached without knowledge of it. This is a
user-facing truth regression on the landing page. **Not fixed** -- outside this
milestone's authorized scope. Its blast radius beyond `dashboard_summary` was
deliberately not swept and is **not** claimed to be confined to Today. Whether it
blocks v0.1 is the owner's decision.

**Field Validation Closure v1 still awaits ChatGPT acceptance.** Nothing in this
entry marks it globally accepted.

**Accepted, 2026-09-25, by Field Validation Closure v1's own baseline
reconciliation.** Performance / Scale / Stability Closure v1 (the
`IMPLEMENTED, pending external acceptance` entry below) and the
subsequent Review Queue Scale Closure v1 and Remaining Performance P1
Closure v1 are now **accepted**: accepted HEAD `d5dd1d9`, schema `v60`.
Validation state carried forward unchanged from each milestone's own
record (below, and in
[performance-scale-stability-closure-v1-report.md](performance-scale-stability-closure-v1-report.md),
[review-queue-scale-closure-v1-report.md](review-queue-scale-closure-v1-report.md)
and the Remaining Performance P1 Closure v1 commit series
`1919017`..`d5dd1d9`). **No remaining P0 or P1 performance blocker**:
the Review Queue unbounded-retrieval P0 that Performance / Scale /
Stability Closure v1 disclosed is closed by Review Queue Scale Closure
v1, and P1-7/P1-8 are closed by Remaining Performance P1 Closure v1.
**Performance P2 items remain deferred**, unchanged and still
unauthorized. **Current authorized milestone = Field Validation Closure
v1** -- real-hardware field validation (native-Windows Host, real
reference Camera Node, real camera, real network, accepted production ML
pipeline), report-first, closing the remaining real-world field-evidence
gaps rather than reopening accepted work. This entry records only that
accepted delta; it rewrites no unrelated scheduler history and
authorizes no milestone beyond Field Validation Closure v1 itself.

**Accepted, 2026-09-22, by Performance / Scale / Stability Closure v1's
own baseline reconciliation.** UI/UX & First-Run Adoption v1 (the entry
below) is now accepted: accepted HEAD
`3133c64b6a9c49273f5cc57a807240630cab5b7a`. Validation state carried
forward unchanged from that milestone's own record, below and in
[ui-ux-first-run-adoption-v1-report.md](ui-ux-first-run-adoption-v1-report.md):
Tier 1 `tests/test_demo_source_exclusion.py` 7 new tests (36 total),
6 of 7 proven RED against the unmodified baseline; Tier 2 51 backend test
files, 33 fixture failures in 5 files all corrected with the established
`de_demo_seeded_source` mechanism (no assertion weakened), then 55/55;
Tier 3 (full Core) run twice -- first run 12 failed / 6117 passed, eight
of them genuine demo-exclusion fallout in files Tier 2 never reached, all
corrected; second, confirming run **5 failed / 6124 passed / 4 skipped /
11 xfailed (42m29s)**, four the established pre-existing set
(`test_doctor_camera_node_transport.py`'s own pair,
`test_environmental_context.py::test_temperature_band_established_once_
enough_days_are_cached`,
`test_place_change_summary_repository.py::test_api_round_trip_exposes_
change_detection_fields`) and the fifth
(`test_camera_node_transport_acceptance.py::test_scenario_1_ordinary_
disconnect_reconnect`) a concurrency-scheduling artifact of running
browser suites against this machine at the same time as Core, passing
standalone in both the working tree and a baseline clone. Schema
unchanged (`v59`). **The protected-file incident that milestone disclosed
in its own §Z-1 is remediated, not merely recorded:** commit `2549b32`
restored all seven preserved files to untracked state index-only, with
every file's contents byte-identical throughout and no milestone commit
rewritten; `3133c64` published that remedy in the closure report. §13's
"never edited, deleted, renamed, staged, incorporated, or cleaned up"
rule is unchanged and un-weakened by the incident. **Carried forward, not
falsely closed:** (a) Native-Windows & Packaging Acceptance v1's live
fresh Camera Node pairing proof against the shared reference Pi (Lane G /
Lane R field-validation item, unchanged, now carried across three
consecutive milestones); (b) the Doctor media-integrity relative-path
behaviour recorded in earlier audit notes, outside that milestone's scope
and outside this one's. Verified starting baseline exactly as expected:
branch `main`; HEAD `3133c64`; schema `v59`; working tree clean except the
seven preserved untracked detector files and `uv.lock`.

**Review Queue Scale Closure v1 -- IMPLEMENTED, pending external
acceptance.** A bounded continuation authorized to close the one
release-blocking P0 that Performance / Scale / Stability Closure v1 left
open (its §R P0-4 and §Z): `GET /api/review-queue` is unbounded. See
[review-queue-scale-closure-v1-report.md](review-queue-scale-closure-v1-report.md)
for the complete record. **Schema `v60`, unchanged** -- no table, no
column, no migration; entirely a read-path change plus two new read
endpoints.

That milestone had said plainly why it could not bound the response alone:
`ReviewQueuePage.tsx` computed every tab count, triage count,
source/stream facet, "showing N of M" disclosure and bulk-selection
eligibility client-side over the whole download, so a windowed response
presenting those numbers as totals would have been a truth regression, not
a performance fix. This milestone moved those predicates to the server
*without changing what they decide*:
`src/mockingbird/repository/review_queue_filters.py` is a pure,
session-free port with one function per named TypeScript original, and the
client-side copies were deleted rather than left to drift.

**Measured, before (a `git worktree` of the accepted baseline `73dbcd4`)
and after, on the same machine, at both required profiles:**

| | Before | After |
|---|---|---|
| Review Queue mount, Profile B (2,811 Visits) | 12.3 s / **20.4 MB** / 2,811 items / 28,227 statements | 1.6 s / **194 KB** / 25 items / 305 |
| Review Queue mount, Profile C (burst/backlog, 2,058-item backlog) | 12.0 s / **24.1 MB** / 3,322 items / 23,400 | 2.0 s / **195 KB** / 25 items / 312 |
| App-shell review counts, Profile C | 7.6 s / **14.9 MB** / 20,671 | 1.4 s / **238 bytes** / 105 |
| Fast Review "next unresolved Visit", Profile C | 9.0 s / 20,671 | 0.9 s / **77** |

Profile C reproduces the P0's own published figures exactly -- 2,058
items, 14,921,425 bytes, 20,671 statements against "2,060 items, 14.9 MB,
20,673" -- confirming the same workload. Latency conclusions are drawn
from within-run comparisons (before-shape and after-shape measured in the
same process, same minute, same database), because this machine is shared
with an unrelated bursty workload.

**Two real defects the work surfaced and fixed**, both of which only a
running browser could have caught: the primary single-item correction path
(every card's Confirm / Correct / False positive) stopped refreshing once
the app shell no longer carried the queue, leaving tab counts stale; and
two in-flight queue requests could let a slow earlier response reinstate a
stale view.

**Validation.** Tier 1: 28 new tests in
`tests/test_review_queue_page_scale.py`, including the §12 structural
regression tests -- ten times the reviewed history at an identical backlog
must not move the response by more than 64 bytes, and ten times the
*backlog* may only move the documented 200-target Fast Review snapshot.
Tier 2: 279 passed, with 6 `test_dashboard_today.py` failures reproduced
identically at the baseline. Browser: 4 new tests on their own isolated
instance (`playwright.review-queue.config.ts`, the same isolation
`onboarding.spec.ts` already has); the shared suite was **9 failed / 182
passed at this HEAD against 10 failed / 181 passed at the baseline** -- a
strict subset, **zero browser failures attributable to this milestone**.
Tier 3 full Core, run twice: **12 failed / 6,173 passed / 4 skipped / 11
xfailed** both times (46:47 and 45:58), every failure classified -- four
from the established pre-existing set, seven reproduced identically at the
baseline (the six `test_dashboard_today.py` date-sensitive tests plus
`test_canonical_new_regular_species_consistency.py`, same family), and one
Camera Node transport full-run timing flake. The two runs differ by exactly
one swap inside that transport family:
`test_transport_worker.py::test_retryable_failure_...` failed in run 1 and
passed in run 2, while
`test_camera_node_transport_acceptance.py::test_scenario_8_...` did the
reverse. Both pass standalone, neither file references the review queue at
all, `test_camera_node_transport_acceptance.py` is already a documented
member of this repository's load-sensitive flake family (UI/UX & First-Run
Adoption v1 classified `test_scenario_1_...` identically), and run 2's
failure is provably a harness race rather than a product fault: it asserted
`item.state in {"pending", "failed_retryable"}` and read `'transmitting'`
having sampled the spool mid-attempt, on an item already carrying the
correct `last_error='transport_protocol_unsupported'`. **Zero Core failures
attributable to this milestone, in both runs.** `ruff` byte-identical to baseline on every changed product
file; `tsc --noEmit` and `npm run build` clean.

**Remaining Performance / Scale / Stability blockers:** P0-4 is closed.
P1-7 (`GET /api/media`, 11.9 MB at Profile B), P1-8
(`/api/detection-proposals`, `/api/detection-runs`,
`/api/species-suggestions`), P2-1 (Bird Log journal), P2-2 (dataset
coverage/quality) and P2-3 (`dashboard_summary`'s unrendered fields) are
open and untouched. One new **P2-4, not release-blocking**: the bounded
page's own classification pass is still O(total history) in *Python* (a
handful of statements, but one `ReviewQueueItem` constructed per queue
member), which is what keeps it at roughly a second rather than tens of
milliseconds.

Working tree clean apart from the seven preserved untracked detector files
(verified untracked and byte-identical to their session-start SHA-256 at
every commit boundary; explicit staging paths throughout) and `uv.lock`.
Verified starting baseline exactly as expected: branch `main`; HEAD
`73dbcd4`; schema `v60`. **Not pushed.**

**Performance / Scale / Stability Closure v1 -- IMPLEMENTED, pending
external acceptance.** See
[performance-scale-stability-closure-v1-report.md](performance-scale-stability-closure-v1-report.md)
for the complete record. **Schema `v59` -> `v60`** (fourteen additive
indexes; no table, column or value changed; a fresh install and an
upgraded install converge on an identical index set, asserted as a test;
the real 2,813-Visit database migrated in 2.8s including its
pre-migration safety backup). Stage A measured four credible v0.1
workloads (69 / 2,813 / 3,322-with-burst / 11,206 Visits, each sized from
this repository's own accepted field evidence) on two real environments
(Linux/WSL and **native Windows**, using a real packaged MockingBird
Windows runtime against native NTFS storage).

**The three findings that mattered:**

1. **Backups -- and therefore upgrades -- failed after about two months
   of ordinary use.** A backup manifest carries one ~154-byte entry per
   media file and `MAX_MANIFEST_BYTES` was 1 MiB, so it was exceeded at
   roughly 6,800 files. `create_backup` verifies the archive it has just
   written, so this was not "an old backup cannot be read" -- *no backup
   could be made at all* -- and because the pre-migration safety backup
   is a hard gate on migrating, the same install could no longer be
   upgraded. Reproduced end to end. Pre-existing and independent of
   everything else here; the schema bump is simply how it surfaced.
2. **The core observation tables had no secondary index at all**, so
   every foreign-key lookup was a full table scan. Fourteen indexes
   added, each chosen from a real query plan and each pinned by a test
   asserting SQLite picks it.
3. **The landing page and review loop degraded with total accumulated
   history rather than with work outstanding.** Fixed by pushing the
   review-status predicate into SQL, a read-only build cache, bulk
   preloads, and letting the Dashboard and the eleven `review_queue_count`
   fields ask for classification without per-item review-card hydration.

Measured at the established-install workload, before -> after:
`GET /api/dashboard/summary` 18.02s -> 2.29s (38,796 -> 5,189 SQL
statements); `GET /api/review-queue` 17.15s -> 5.07s (38,970 -> 11,027);
Activity Library 7.09s -> 173ms; `GET /api/events` 2.79s -> 19ms (2,820
-> 3 statements). Also: `GET /api/visits` -- the endpoint the pre-release
audit specifically flagged -- confirmed unbounded, confirmed to have **no
frontend consumer**, and bounded with `limit`/`offset`.

Measured non-findings, each with evidence rather than assumption: **no
per-request memory leak** (4,427 identical requests against a fixed
library moved RSS 5.6 MB/hour; flat file descriptors and threads);
**queues are genuinely bounded** (4 ingest frames, 100 acoustic segments
per Stream, 500 global, all shedding oldest-first to a diagnosable
state); **restart is safe** (three restarts under load, two of them
`SIGKILL`, zero duplicated or orphaned observations, zero stranded queue
work); **logs are hard-capped** at 20 MB; **optional BirdNET's disabled
path is lightweight** (0.48ms, no heavy import).

**One P0 is reduced but explicitly NOT closed, and this file records it
as open:** `GET /api/review-queue` remains unbounded. At Profile C -- an
ordinary three-month library with one burst week and an owner behind on
review -- it returns 14.9 MB in 74.4s; at Profile D, 36.1 MB in 95.8s;
and `ReviewQueuePage` requests it with `include_reviewed=true` on mount
and after every saved correction. Closing it needs server-side pagination
**plus** server-computed per-tab and per-filter counts **plus** a matching
change to that page, which computes all of them client-side over the full
list -- a coordinated frontend change that materially alters the
just-accepted UI/UX & First-Run Adoption v1 milestone's most complex page.
That is the owner's call to authorize, not this milestone's to take
against an explicit "do not rewrite the frontend / do not reopen the
accepted UI/UX milestone" instruction. The same reasoning applies to
`GET /api/media` (11.9 MB at Profile B, six page consumers) and the three
detection/suggestion list endpoints. **This is the natural next
milestone's subject, and saying so here is advisory only.**

Tier 1: 30 new tests across four files
(`test_review_queue_scale.py`, `test_bounded_list_endpoints.py`,
`test_observation_history_indexes.py`, `test_backup_manifest_scale.py`),
with RED-against-baseline proof wherever the change permitted it. Tier 2:
145 + 126 + 34 passed across review-queue, dashboard, identification,
review-provenance, persistence/migration, backup/restore/upgrade,
dataset, journal and export subsystems. Tier 3 (full Core) run twice: the
first run (11 failed / 6,111 passed) found **a real defect this milestone
had introduced** -- migration 60 aborted an upgrade from an old schema
because migrations run before `create_all` and a table did not exist yet
-- fixed in `700de44`; the second, confirming run was **6 failed / 6,116
passed / 4 skipped / 35 deselected / 11 xfailed (43m07s)**, all six the
established pre-existing set. **Zero Core failures attributable to this
milestone's changes.** `ruff` byte-identical to baseline on every changed
product file. Working tree clean apart from the seven preserved untracked
detector files (verified untracked and byte-identical at every commit
boundary; explicit staging paths throughout) and `uv.lock`. **Not
pushed.**

**Performance / Scale / Stability Closure v1** -- directly authorized
outside this file by the external (ChatGPT) global release sequencing,
following acceptance of UI/UX & First-Run Adoption v1, above. Establishes
that MockingBird v0.1 remains responsive, bounded and recoverable under
realistic first-release workloads -- release fitness, not theoretical
maximum scale. Stage A: define a finite set of credible v0.1 load profiles
(fresh install, established home install, busy period, large early-adopter
library) and measure startup, UI/API responsiveness, the specifically
flagged unbounded `GET /api/visits` surface, memory, CPU/GPU, disk/media/
database growth, database/query scale, queue/backpressure behaviour,
long-run stability, restart/recovery under load, optional-BirdNET impact,
and native-Windows-specific behaviour -- producing an evidence-backed
P0/P1/P2/P3 inventory. Stage B: fix every P0 and P1, and bounded P2 items
only where clearly worthwhile. Explicitly out of scope: storage-
architecture redesign, distributed/cloud/multi-site infrastructure,
detector/model selection, thresholds, a new task-queue platform absent a
demonstrated blocker, frontend rewrite, reopening the accepted UI/UX
milestone, Gate G, push. See
[performance-scale-stability-closure-v1-report.md](performance-scale-stability-closure-v1-report.md)
for the complete record once implemented and validated.

**Accepted, 2026-09-22, by UI/UX & First-Run Adoption v1's own
baseline reconciliation.** Analytics & Local Data Truth Consistency v1
(the entry immediately below) is now accepted: accepted HEAD
`456277f633df0a1e51821bd00ad8260c42c40244`. Validation state carried
forward unchanged from that milestone's own record, below: Tier 1 11 new
tests (`tests/test_demo_source_exclusion.py`, 29 total) RED-then-GREEN;
Tier 2 419 passed twice; Tier 3 (full Core) confirming run 4 failed /
6083 passed / 4 skipped / 35 deselected / 11 xfailed, all 4 the
established pre-existing set; targeted e2e and `tsc --noEmit` clean;
schema unchanged (`v59`). **Carried forward, not falsely closed:** (a)
Native-Windows & Packaging Acceptance v1's live fresh Camera Node pairing
proof against the shared reference Pi (Lane G/Lane R field-validation
item, unchanged); (b) that milestone's own explicitly-disclosed
out-of-scope gap -- Place Biodiversity/Change/Habitat summaries were
never checked for the same demo-source leak -- which this milestone's own
Stage A audit, below, reproduces directly on a fresh install and records
in its own entry. Verified starting baseline exactly as expected: branch
`main`; HEAD `456277f`; schema `v59`; working tree clean except the seven
preserved untracked detector files and `uv.lock`.

**UI/UX & First-Run Adoption v1** -- directly authorized outside this
file by the external (ChatGPT) global release sequencing, following
acceptance of Analytics & Local Data Truth Consistency v1, above. The
comprehensive pre-release product-experience milestone: Stage A, a
finite, evidence-backed UI/UX defect inventory built from the running
product (fresh and populated instances, desktop and narrow widths), not
source review alone; Stage B, fix every P0/P1 item and bounded, low-risk
P2 items. Explicitly out of scope: detector/model selection, MDv5a
threshold, BioCLIP, SpeciesNet, BirdNET redesign, new wildlife
capability, native mobile, multi-site, LTE/solar, custom hardware,
storage/database architecture, broad performance work, Gate G, push. See
[ui-ux-first-run-adoption-v1-report.md](ui-ux-first-run-adoption-v1-report.md)
for the complete record once implemented and validated.

**Accepted, 2026-09-22, by Analytics & Local Data Truth Consistency v1's
own baseline reconciliation.** Review Queue Count Truth Consistency v1
(the entry immediately below) is now accepted: accepted HEAD
`993d3ef094a5f9f0d7ba2941b25476f1172b9c8b` ("Add Review Queue Count Truth
Consistency v1 closure report, link from release-execution-state.md").
Validation state carried forward unchanged from that milestone's own
record, below: the canonical `_visible_review_queue_items`/`_visible_
review_queue_count` fix, reused at all eleven `review_queue_count` call
sites; Tier 3 (full Core), run once against the fix: 6069 passed, 7
failed (6 pre-existing, 1 newly-observed full-suite-only intermittent
flake, reconfirmed clean via a second full run); schema unchanged (`v59`).
That milestone's own two disclosed-but-deliberately-out-of-scope sibling
count families -- `AnalyticsSummary.needs_review_count` and `YardMap
ActivitySummary.needs_review_count`, both demo-inclusive throughout, along
with every field family sharing their own producer functions -- are
exactly what this reconciliation's own milestone, below, closes; not
carried forward as still-open. **Not falsely closed:** Native-Windows &
Packaging Acceptance v1's own one incomplete real-hardware proof -- a
live, fresh Camera Node pairing proof against the shared reference Pi,
blocked by that session's own auto-mode guardrail against remote writes
to shared infrastructure, not a product defect -- remains genuinely open
and is carried forward here unchanged, once again, as a still-open
field-validation item; it belongs with Lane G/Lane R's own existing
Camera Node hardware-validation record (§6.G, §6.R) for whichever future
session next has authorization to perform a live pairing-reset against
that shared device. Verified starting baseline for this reconciliation
exactly as expected: branch `main`; HEAD `993d3ef`; schema `v59`; working
tree clean except the seven preserved untracked detector files, confirmed
present and untouched, plus `uv.lock` (pre-existing untracked, not one of
the seven, not touched). **Disclosed departure from this file's own §13
"never allow multiple Claude writer sessions in the same working tree"
rule:** a second Claude Desktop session (`Analytics & Local Data Truth
Consistency`, no "v1") sharing this exact milestone and working tree was
found active partway through this reconciliation's own Tier 3 work, after
an initial peer-session check had found every session idle. Not
prevented, only detected after the fact and then handled: both sessions'
edits were independently verified (not merely accepted) before being
relied on, and both sessions coordinated live via cross-session messaging
for the remainder of the work, including one near-collision (both
independently started a full Core run within the same minute; caught
within about a minute via direct process inspection and resolved by
stopping this session's own redundant run). HEAD never moved during any
of this; no commit, push, or destructive operation occurred from either
session before this reconciliation's own commits. Full account in the
closure report's own §R.

**Analytics & Local Data Truth Consistency v1** -- directly authorized
outside this file by the external (ChatGPT) global release sequencing,
following acceptance of Review Queue Count Truth Consistency v1, above.
A narrow release-correctness milestone, not a UI redesign: excludes the
seeded demo Source's own activity from `AnalyticsSummary`, `LocalData
Status` (via its existing reuse of `AnalyticsSummary`), `DatasetCoverage
Summary`, `DatasetQualitySummary`, and `YardMapActivitySummary` --
exactly the field families Review Queue Count Truth Consistency v1's own
report disclosed and deliberately left out of its own bounded scope.
Starting baseline verified exactly as expected before any edit: branch
`main`; HEAD `993d3ef`; schema `v59` unchanged; working tree clean except
the seven preserved untracked detector files (§13, below) and `uv.lock`,
confirmed present and untouched.

**2026-09-22 update (Analytics & Local Data Truth Consistency v1
executed):** see
[analytics-local-data-truth-consistency-v1-report.md](analytics-local-data-truth-consistency-v1-report.md)
for the complete record, summarized here. One shared seam,
`_real_stream_ids(session)`, reuses the canonical `_real_source_
condition()` the Review Queue family already established; `_analytics_
summary`, `_dataset_coverage_summary`, `_dataset_quality_summary`, and
`_yard_map_activity_summary`/`yard_map` (new `is_real_source` parameter)
all now filter through it -- one seam for every Python-side aggregation
this defect family touches, not ad hoc `provider_key != "demo"` checks
per call site. `LocalDataStatus`'s own raw storage-inventory fields
(`source_count`, `stream_count`, `zone_count`, `media_asset_count`,
`detection_run_count`, `detection_proposal_count`, `motion_evidence_
count`, `review_label_count`, `dataset_export_count`) are deliberately
left demo-inclusive -- local-storage diagnostics ("local source records"/
"local import references"), not ecosystem-history truth, already honestly
disclosed via `seed_data_present`, matching the same Category-C
determination this file's own history already applied to `AdapterEvaluation
Summary.unreviewed_count`. `target_species_count` (taxonomy list size, not
activity-derived) and Yard Map's own monitoring/health fields are
likewise unaffected either way, correctly. Incidental fix, disclosed
rather than folded in silently: `_dataset_quality_summary` referenced
`event_ids_with_any_visits` without ever defining it (unlike its two
siblings), crashing `GET /api/dataset-quality/summary` on any genuinely
eventless real Event -- fixed to match the sibling functions' own
established shape.

**Validation.** Tier 1: 11 new tests in `tests/test_demo_source_
exclusion.py` (29 total, all passing) -- RED against the unmodified
baseline (8 of 11 failed) and GREEN after the fix, via `git stash`
bisection. Tier 2: 30 directly-adjacent test files, 419 passed twice;
9 files needed fixture-level corrections where they used the seeded demo
Source as convenient plumbing rather than testing demo-exclusion itself
(`test_api.py`, `test_persistence.py`, `test_dataset_coverage.py`,
`test_dataset_quality.py`, `test_model_readiness.py`, `test_yard_map.py`
in the original sweep; `test_taxonomy.py`/`test_source_provider_smoke_
flows.py` found only by Tier 3, below) -- each reviewed individually, no
assertion weakened, only repurposed via the established `de_demo_seeded_
source` mechanism or corrected to the newly-correct expected value.
`ruff check`: `product_repository.py`'s established 56-finding baseline
is now 55 (the incidental `F821` fix); every other changed file clean or
byte-identical to its own pre-existing baseline.

**Tier 3 (full Core).** First run: 6079 passed, 8 failed -- 4 matched the
established pre-existing set (`test_doctor_camera_node_transport.py` x2,
`test_environmental_context.py`, `test_place_change_summary_repository.py`;
`test_place_biodiversity_summary_repository.py`'s own pair did not
reproduce, consistent with its long-documented flakiness), 4 were new
(`test_source_provider_smoke_flows.py`/`test_taxonomy.py`, two files never
reached by Tier 2's own sweep -- exactly the case Tier 3 exists for),
root-caused and fixed as fixture-level corrections identical in kind to
the nine above, independently re-verified (including a direct full-
traceback reproduction proving the one `KeyError` is a test assertion
artifact, not a server-side defect) rather than accepted on report alone.
Second, confirming run from the fully-fixed tree: **4 failed, 6083
passed, 4 skipped, 35 deselected, 11 xfailed (42m38s)** -- the identical
established pre-existing set, independently re-confirmed via `git stash`
bisection against unmodified HEAD. **Zero Core failures attributable to
this milestone.**

**Targeted e2e.** `web/e2e/analytics-local-data-truth-consistency.spec.ts`
proves a real correction moves `/analytics` and `/local-data`'s real,
rendered counts by exactly the genuine amount and surfaces the corrected
species, both pages, through the real UI -- deliberately delta-based
rather than a hard "reads zero" (this suite's own shared-instance
constraint, disclosed in the spec's own header). The demo-only-install
"reads exactly zero" contract itself is Tier 1's own claim, proven there
with true fixture isolation. Found and fixed three pre-existing
Playwright strict-mode violations in the untracked spec file itself (not
application code) before it would pass at all -- full account, including
why the fixed spec legitimately passes both before and after this
milestone's own backend fix (proof of its own real, but narrower, scope;
not a failed RED proof), in the closure report's own §O. `tsc --noEmit`:
clean.

No schema change (`v59`, unchanged); no detector/classifier/threshold/
tracker/admission/Visit-assembly/truth-mutation change anywhere in this
milestone. Working tree confirmed clean except the seven preserved
untracked detector files and `uv.lock`, byte-identical (re-hashed) at this
session's own start and close. Implementation commit `6740f71`; this
reconciliation's own commit follows. Not pushed.

**Does not** redesign Analytics, Local Data, Dataset Coverage/Quality, or
Yard Map; change any model/detector/threshold; touch Place Biodiversity/
Change/Habitat summaries (bounded scope, per the governing brief -- an
analogous gap there is genuinely unknown, not assumed clean); or begin
the next global phase (UI/UX & First-Run Adoption v1) -- all explicitly
out of scope and untouched. **Does not** push. **Does not** self-authorize
a subsequent milestone. **Authorization remains this milestone's own**
pending the owner/external (ChatGPT) acceptance review of this closure.

**2026-09-22 update (UI/UX & First-Run Adoption v1 executed):** see
[ui-ux-first-run-adoption-v1-report.md](ui-ux-first-run-adoption-v1-report.md)
for the complete record, summarized here. Stage A audited all 28
user-reachable routes plus the five-step first-run wizard against two
real running instances (a genuinely fresh install and a populated one) at
1366/820/390px, with console/HTTP error capture, per-element overflow
measurement and structural accessibility facts -- not source review
alone. It produced a finite inventory of 4 P0, 16 P1, ~16 P2 and a
recorded P3 set. Stage B fixed every P0 and P1 and the bounded P2 items.

**P0-1 is a truth defect this file's own prior milestone explicitly left
unexamined** (Analytics & Local Data Truth Consistency v1 disclosed that
Place Biodiversity/Change/Habitat were out of its bounded scope): on a
fresh install the seeded demo Visit was presented as this Place's real
history ("Kinds of wildlife known here: 1" on Today and Place Report,
Place Story's "1st species recorded"), listed in Activity Library, and --
most seriously -- exported as an *eligible research record* by Darwin
Core, Camtrap DP, iNaturalist eligibility and reviewed dataset exports
(`_research_scope_stream_ids` returned `None`, meaning "every Stream").
Closed at one shared seam,
`_historical_place_baseline_and_species_statuses` (all six Place-history
callers), plus each sibling scope, reusing the established
`_real_stream_ids`/`_real_source_condition()` contract rather than ad hoc
per-call-site checks. The other three P0s were first-run dead ends:
Import Media defaulting to the demo Stream (media filed there is hidden
by every review/history surface), the Review Queue offering only a
non-working recovery when its default group was empty while work waited
elsewhere, and an Add Camera step that assumed Camera Node hardware and
repository knowledge.

**Validation.** Tier 1: 7 new tests in `tests/test_demo_source_
exclusion.py` (36 total), RED-then-GREEN via `git stash` bisection (6 of
7 failed against the unmodified baseline), including a positive control
proving a repurposed real Source still counts. Tier 2: 51 backend test
files; one sweep found 33 failures in 5 files, every one a fixture using
the seeded demo Source as convenient plumbing, corrected via the
established `de_demo_seeded_source` mechanism with no assertion weakened
(then 55/55). `tsc --noEmit` clean; `ruff` unchanged at its established
55-finding baseline for `product_repository.py`.

**Tier 3 (full Core).** First run 12 failed / 6117 passed
(45m15s): 4 the established pre-existing set, 8 genuine fallout in files
Tier 2 never reached -- all eight using the seeded demo Source/Visit as
plumbing for Activity Library search, dataset export or research scope,
each corrected via the same `de_demo_seeded_source` mechanism. Second,
confirming run: **5 failed / 6124 passed / 4 skipped / 11 xfailed
(42m29s)** -- the identical 4 pre-existing failures plus one
timing-sensitive Camera Node transport acceptance test that passes
standalone in this tree and in a baseline clone, and failed only because
browser suites were running concurrently against this machine. Zero Core
failures attributable to this milestone's product changes.

**e2e.** Onboarding suite 6/6. Shared suite: 181 passed / 10 failed,
classified rigorously rather than assumed -- the accepted baseline
(`456277f`) was cloned, built and run through the identical suite and
fails **9** of the same specs (order/accumulation artifacts against the
suite's one shared instance). The single difference was one spec pinning
a metric label this milestone renamed; label made consistent across
Insights and Local Data, spec updated, now passing. Net attributable e2e
regressions: zero. Scripted keyboard checks (skip link, focus order,
Escape/focus return on the Alerts popover and Change password, review
tabs) all pass; every audited route measures zero horizontally
overflowing elements at 390px and 820px.

No schema change (`v59`). No detector/classifier/threshold/tracker/
admission/Visit-assembly change. No accepted truth contract changed --
the demo-exclusion work extends the existing contract to the surfaces it
had not yet reached.

**Disclosed process defect, not repaired:** this milestone's first
implementation commit used `git add -A src tests` and thereby staged
three of the seven preserved untracked detector files
(`small_bird_benchmark.py`, `wildlife.py.orig`,
`test_small_bird_benchmark.py`). Their content was never modified
(SHA-256 verified at session start and after every commit, byte
identical) and nothing was pushed, but they are tracked in local history
from `3f6a49c` onward. Both repairs -- `git rm --cached`, or rewriting
the unpushed range -- are destructive git operations this session was
refused permission to perform, so the repair is left to the owner. See
§Z-1 of the closure report.

**Does not** push, change any model/detector/threshold, redesign
Analytics/Local Data/Yard Map truth, build mobile/multi-site, perform
broad performance work, execute Gate G, or self-authorize a successor.
**Authorization remains this milestone's own** pending the owner/external
(ChatGPT) acceptance review of this closure.

**Native-Windows & Packaging Acceptance v1 [reference retained below for
its own still-open Camera Node pairing item, accepted above]** -- directly
authorized outside this file by the external (ChatGPT) global release
sequencing, following acceptance of Pre-Release Trust & Correctness
Correction v1 (HEAD
`3feab6c3e5bacf6ee45fb7f8067c5049d2813565` ("Reconcile release-execution-
state.md and publish the Native-Windows & Packaging Acceptance v1
report"), the documentation-reconciliation commit immediately following
that milestone's own `9f98955` fix commit -- no code changed between
them. Validation state carried forward unchanged from that milestone's
own record, below: two real defects found and fixed on real native-
Windows/GPU hardware (a backup restore-plan file-lock bug; a demo-Source
Review Queue/Dashboard leak), Tier 3 second run 6061 passed / 7 failed
(all 7 independently re-confirmed pre-existing/environmental via `git
stash` bisection, zero attributable to that milestone), schema unchanged
(`v59`). **Not falsely closed:** that milestone's own one incomplete
real-hardware proof -- a live, fresh Camera Node pairing proof against
the shared reference Pi, blocked by that session's own auto-mode
guardrail against remote writes to shared infrastructure, not a product
defect -- remains genuinely open and is carried forward here as a
still-open field-validation item, not marked done. It belongs with Lane
G/Lane R's own existing Camera Node hardware-validation record (§6.G,
§6.R) for whichever future session next has authorization to perform a
live pairing-reset against that shared device; this reconciliation does
not attempt it and does not reopen either lane's own `CLOSED` status on
this basis, since both lanes' own closures were already earned on
different, already-proven grounds (Lane G: Authenticated Camera Node
Golden-Path Capture & Preview Acceptance v1's own fresh pairing proof;
Lane R: the accepted true-latency budget). Verified starting baseline for
this reconciliation exactly as expected: branch `main`; HEAD
`3feab6c3e5bacf6ee45fb7f8067c5049d2813565`; schema `v59`; working tree
clean except the seven preserved untracked detector files, confirmed
present and untouched; of 199 peer sessions, every MockingBird-named
session idle or offline, the sole "busy" peer session belonging to an
unrelated project.

**Review Queue Count Truth Consistency v1** -- directly authorized
outside this file by the external (ChatGPT) global release sequencing,
following acceptance of Native-Windows & Packaging Acceptance v1, above.
A narrow release-correctness milestone, not a UI redesign: that
milestone's own N.2 fix excluded the seeded demo Source's activity from
`GET /api/review-queue`/`dashboard_summary`, but disclosed roughly a
dozen sibling `review_queue_count` response fields (Manual Import,
Folder Import, Model Adapters, Detection Proposals, and the core
review/correction flow itself) still computing an unfiltered
`len(_review_queue_items(...))`, surfaced to users as "N needs review"
pills/toasts. Starting baseline verified exactly as expected before any
edit: branch `main`; HEAD `3feab6c3e5bacf6ee45fb7f8067c5049d2813565`;
schema `v59` unchanged; working tree clean except the seven preserved
untracked detector files (§13, below), confirmed present and untouched;
no active writer session found sharing this working tree (this session's
own peer-session inventory, identical finding to the acceptance note
above). This entry is updated in place once this milestone is
implemented and validated, matching this file's own established
convention.

**2026-09-22 update (Review Queue Count Truth Consistency v1 executed):**
see
[review-queue-count-truth-consistency-v1-report.md](review-queue-count-truth-consistency-v1-report.md)
for the complete record, summarized here. A bounded repository search
for every `review_queue_count` producer
(`grep` across `src/`, cross-checked against every call site of
`self._review_queue_items(session)`) found exactly eleven --
`run_model_adapter`, `_run_local_image_detector_adapter`,
`_run_megadetector_adapter`, `create_demo_detection_run`,
`decide_detection_proposal`, `create_media_import`,
`import_folder_media`, `_create_review_label_result_in_session`,
`_review_correction_result_for_model`, `_visit_review_reopen_response`,
`_fast_review_undo_response` -- confirming, not merely assuming, the
prior milestone's own "roughly a dozen" estimate. **Canonical fix:** two
new `ProductRepository` methods immediately after `_review_queue_items`
itself -- `_visible_review_queue_items` (filters `is_demo_source`) and
`_visible_review_queue_count` (its length) -- reused at all eleven sites
and at `dashboard_summary`'s own pre-existing inline filter (removing
that duplicate), while `_review_queue_items`/`review_queue_items()`
itself is untouched, preserving the internal unfiltered contract
`test_review_queue_product_mode.py` depends on. `GET /api/review-queue`'s
own existing one-line filter in `api/main.py` was deliberately left as
is (a different architectural layer, already correct, already tested;
consolidating it was considered and declined to keep this milestone's
blast radius bounded).

Two closely-related but larger families were found during this search
and deliberately **not** fixed, disclosed here rather than silently
left: `YardMapActivitySummary.needs_review_count`
(`YardMapPage.tsx`'s own per-camera "N needs review" button) is a raw
per-stream SQL count with no `is_demo_source` awareness at all; and
`AnalyticsSummary.needs_review_count` (`_analytics_summary`, embedded
--but, checked directly, never actually read by the frontend-- in four
of the eleven fixed response objects, and separately live via `GET
/api/analytics/summary` feeding `AnalyticsPage.tsx`,
`SpeciesCoverageCard.tsx`, and transitively `LocalDataStatus`/
`DatasetCoverageSummary`/`DatasetQualitySummary` on `LocalDataPage.tsx`
and their panels) is demo-inclusive throughout, alongside its own
sibling `event_count`/`visit_count`/`species_counts` fields that would
need the identical treatment to stay internally consistent if
`needs_review_count` alone were changed. Both are real, user-visible
instances of the same defect family, but neither is "immediately
related" to `review_queue_count` in the bounded sense this milestone's
own governing brief scoped (different computation, different response
shapes, a materially larger blast radius across Analytics/Local
Data/Dataset Coverage/Dataset Quality this milestone's own brief did not
authorize) -- see this milestone's own report for the complete record
and why a dedicated follow-up, not an opportunistic extension here, is
the correct next step. `AdapterEvaluationSummary.unreviewed_count`
(`ModelAdaptersPage.tsx`'s adapter-evaluation stats grid) was also
found and is correctly left alone: a QA/evaluation metric about
adapter-proposal outcome history, not a "go review this" call to
action.

Schema unchanged (`v59`); no detector/classifier/threshold/tracker/
admission/Visit-assembly/truth-mutation change anywhere in this
milestone -- confirmed both by design (the fix only ever changes which
already-computed items are counted) and by full Tier 3 evidence, below.
Working tree confirmed clean except the seven preserved untracked
detector files, byte-identical (re-hashed) at this milestone's own start
and close.

**Validation.** Tier 1: 8 new focused tests added to the existing
`tests/test_demo_source_exclusion.py` (18 total in that file, all
passing), covering a demo-only queue (count 0), real activity alongside
demo (count 1, then 2), a repurposed seeded demo Source (counts once
repurposed, mirroring the already-established `_real_source_condition`
contract), the core `POST /api/review-labels` correction response, Fast
Review's undo response, Manual Import, Folder Import, and one combined
test exercising Model Adapters/the Manual-Import-adjacent "demo
proposal" action/Detection Proposals together against one shared real
Visit (table-driven rather than three near-duplicate fixtures). The
core-correction-flow test was independently proven RED against the
unmodified `3feab6c` baseline (`assert 1 == 0`, the seeded demo Visit
counted as outstanding real work) and GREEN after the fix, via `git
stash` bisection. Tier 2: 275 passed / 0 failed across 20
directly-adjacent files (review queue, dashboard demo exclusion, fast
review, media/folder import, model adapter, detection interface,
review identification, visit curation, and the broad `test_api.py`),
explicitly including the demo-source contract tests from the prior two
milestones. `ruff check` on both changed source files: `product_
repository.py`'s own established 56-finding baseline confirmed
byte-identical before/after via `git stash` bisection;
`test_demo_source_exclusion.py`: 0 findings.

**Tier 3 (full Core), run once against the fix: 6069 passed, 7 failed,
4 skipped, 35 deselected, 11 xfailed (43m35s).** Six failures are
byte-identical to the already-established pre-existing set (`test_
doctor_camera_node_transport.py` x2, `test_environmental_context.py`,
both `test_place_biodiversity_summary_repository.py` cases, `test_
place_change_summary_repository.py`) recorded across multiple prior
milestones. The seventh, `test_everyday_discovery_ux_closure.py::test_
today_dashboard_shows_only_corrected_truth`, was not previously on
record -- rather than assume flakiness, this milestone ran full Tier 3 a
**second time**, from a `git stash`-isolated unmodified `3feab6c`
baseline: **6062 passed, 6 failed, 4 skipped, 35 deselected, 11 xfailed
(41m9s)** -- the identical six pre-existing failures, and the seventh
test did not fail on this run either. This test's own file was last
touched two commits before this milestone's own starting baseline,
untouched by this milestone; it passed cleanly both in isolation (1/1)
and at its own file's level (19/19) on the fixed tree. **Zero Core
failures attributable to this milestone** -- the seventh is a genuine,
newly-observed, full-suite-only intermittent flake in an unrelated
subsystem (consistent with this repository's own already-documented
class of load/timing-sensitive full-suite flakiness), not a regression,
proven by a full second baseline run rather than asserted.

**Targeted e2e.** One new spec, `review-queue-count-demo-exclusion.
spec.ts`: a dedicated real (non-demo) Source/Stream via `POST
/api/sources` (the seeded demo Stream is always `legacy_activity` by
design and would never exercise this fix, per `review-queue-fast-
review-keyboard.spec.ts`'s own established reasoning), one real import,
one real "False positive" correction through the actual rendered UI,
asserting the real toast text reads "0 items still need review." --
independently proven RED (announced "1", the seeded demo Visit's own
count) against the unmodified baseline and GREEN after the fix, both at
the real-browser level, via the identical `git stash` bisection
discipline used for Tier 1. `review-queue-fast-review-keyboard.spec.ts`
re-run standalone: passed, no regression. Two other existing specs
(`reviewed-product-loop.spec.ts`, `review-queue-bulk-correct-stale-
write.spec.ts`) were found already failing when run standalone against
this exact starting baseline -- independently confirmed via the same
bisection to fail byte-identically with or without this milestone's own
fix (a stale UI-element expectation in each, unrelated to
`review_queue_count`), disclosed here as pre-existing e2e drift this
milestone did not cause and does not fix. `tsc --noEmit` on the web
project: clean.

Second commit pending, code+tests only (matching this file's own
established convention of keeping the doc-reconciliation commit
separate). Not pushed.

**Does not** redesign the Review Queue, Dashboard, or imports; change
any model/detector/threshold; implement pagination/performance work;
alter Local Only/Host-Place terminology; or begin the next global phase
(UI/UX & First-Run Adoption v1) -- all explicitly out of scope and
untouched. **Does not** push. **Does not** self-authorize a subsequent
milestone. **Authorization remains this milestone's own** pending the
owner/external (ChatGPT) acceptance review of this closure.

**Native-Windows & Packaging Acceptance v1** -- directly authorized outside
this file by the external (ChatGPT) global release sequencing, following
acceptance of Pre-Release Trust & Correctness Correction v1 (HEAD
`f62bb90c786158627394ad62d4d40acbc86007e1`, all nine confirmed 2026-09-21
baseline-audit defects closed -- see that milestone's own entry immediately
below for the complete closure record this authorization accepts). A
clean-machine/user-acceptance exercise: prove the actual generated
MockingBird v0.1 Windows distribution and its documented end-user workflow
work end to end -- build reproducibility from clean source, clean
native-Windows install, first launch/Local Only default, runtime
asset/model acquisition, first real Camera Node operation, remote-access
opt-in, diagnostics/failure recovery, backup/restore, update/migration,
uninstall/removal, and release-artifact self-consistency -- not a WSL,
developer-checkout, source-tree, or hand-prepared-environment claim.
Starting baseline verified exactly as expected before any edit: branch
`main`; HEAD `f62bb90`; schema `v59` unchanged; working tree clean except
the seven preserved untracked detector files (§13, below), confirmed
present and untouched; no active writer session found sharing this working
tree (this session's own peer-session inventory: every other
MockingBird-named session idle or offline; the only "busy" peer session
anywhere belongs to an unrelated project). This entry is updated in place
once this milestone is implemented and validated, matching this file's own
established convention.

**2026-09-22 update (Native-Windows & Packaging Acceptance v1 executed):**
built the actual release artifact twice from clean source
(`python scripts/build_local_product.py <dir>`, no skip flags -- full
GPU/CUDA + BioCLIP runtime both times) -- once from `f62bb90` for Phases
1-8's own baseline, once more from this milestone's own fix commit
`039ce7d` for Phases 9-11 and final re-verification. Both independently
verified with `scripts/verify_release_artifact.py` (**OK** both times) and
a full zip-listing audit (zero protected-file hits, zero BirdNET
model-weight hits, only the licensed adapter code). Installed and driven
through the real, documented end-user path on real native-Windows/GPU
hardware (Windows 10 Pro, RTX 4060 Ti) throughout -- unpack, double-click
`Start MockingBird.vbs`, guided setup, Add Camera, Start observing,
Review, backup/restore, remote-access opt-in, upgrade, uninstall -- per
the complete record in
[native-windows-packaging-acceptance-v1-report.md](native-windows-packaging-acceptance-v1-report.md).

Two real defects found via this live testing, both fixed, both
independently re-verified live on the rebuilt artifact:

- **Backup restore-plan failed on native Windows (release-relevant).**
  `storage/backup.py`'s `create_restore_plan` -- the required first step of
  every documented restore -- used `with sqlite3.connect(...) as
  connection:`, which only commits/rolls back on exit and never closes the
  connection (a well-known stdlib gotcha); its own `finally` block's
  `temporary_database.unlink()` then hit a genuine
  `PermissionError: [WinError 32]` every time on real Windows (invisible
  on POSIX, which is why Linux/WSL testing never caught it). This made the
  entire documented restore flow unusable on native Windows for every
  backup. Fixed with an explicit `connection.close()`, matching the
  already-correct pattern `_validate_database_file` already uses two
  functions above in the same file; the identical fix was applied to
  `_rebind_staged_database`'s sibling occurrence for consistency (not
  independently reproduced failing, fixed proactively). Live-reconfirmed
  end to end on the rebuilt artifact: real backup -> restore-plan (200)
  -> confirmed restore (200) -> post-restore sign-in succeeded.
- **Demo Source leaked into the real Review Queue and Dashboard counts.**
  The seeded demo Source's fabricated Visit appeared as a genuine Review
  Queue item and inflated `needs_review_visit_count`/
  `actionable_animal_visit_count`/`legacy_activity_count` on a brand-new
  install with zero real cameras -- the same defect family Pre-Release
  Trust & Correctness Correction v1's own UI-01 fix closed for Dashboard
  "Recent activity"/Bird Log, at two different call sites (the Review
  Queue API endpoint and `dashboard_summary`'s own derivation) that fix
  did not cover, plus a third, independent sibling gap in the raw
  `needs_review_visit_count`/`needs_review_counts` COUNT queries. Fixed by
  filtering on the already-computed `is_demo_source` flag at the actual
  product-facing boundaries (mirroring the established
  `_dashboard_today_summary` precedent), and by extending the sibling
  `needs_rows` query's own `_real_source_condition()` join to its two raw
  COUNT siblings. `_review_queue_items` itself deliberately still returns
  every item, flagged -- an existing test depends on that contract for
  internal callers, confirmed by reproducing why an initial, wrong-layer
  fix attempt broke it before landing the correct one. Live-reconfirmed on
  the rebuilt artifact against the *same* pre-existing data that showed
  the leak before the fix, and independently corroborated a second way via
  a real old-build-to-new-build upgrade test on that identical data.

No schema change (`v59`, unchanged); no detector/classifier/threshold/
tracker/admission/Visit-assembly change; working tree confirmed clean
except the seven preserved untracked detector files both before and after
implementation. First commit, `039ce7d`, not pushed.

**Validation.** Tier 1: 6 new regression tests (4 demo-source-exclusion
extending the existing `test_demo_source_exclusion.py`; 2 backup, using a
close-tracking wrapper around `sqlite3.connect` since `sqlite3.Connection`
is an immutable C-extension type), each RED->GREEN via `git stash`
bisection against the unmodified `f62bb90` baseline. Tier 2: full sweep of
12 directly-adjacent test files (119 tests: the backup suite plus 8
dashboard/review-queue files) green; `ruff check` zero new findings on
every changed source file (`storage/backup.py` clean; `api/main.py`/
`repository/product_repository.py`'s own pre-existing large-file finding
counts confirmed byte-identical before/after via bisection, matching this
file's own established convention for those two files).

**Tier 3 (full Core), first run, against `039ce7d`: 41 failures.** Not
hidden -- a real regression event, disclosed as required. Triage: 6
matched already-established pre-existing/environmental failures; the
remaining ~35 were newly broken by this milestone's own `is_demo_source`
filtering becoming load-bearing for the first time (see N.2, above),
which exposed a second, more subtle pre-existing bug in the same
function: `_review_queue_product_context` computed `is_demo_source` as
`kind == demo OR provider_key == "demo"`, an OR that could never stop
being true once a Source's `kind` was `"demo"` -- contradicting
`_real_source_condition()`'s own established precedent (a real
provider row wins when present; `kind` decides only as the fallback when
none exists), which is exactly why a repurposed demo Source (this
milestone's own `de_demo_seeded_source` test helper, and several
pre-existing e2e specs, both legitimately do this) could never actually
stop reading as demo. Corrected to match that precedent exactly; the
~35 affected tests were reviewed individually (not mechanically forced
green) and found to all be legitimate fixture-plumbing conversions, with
one dedicated new regression test added for the specific inconsistency
(`test_a_repurposed_demo_source_no_longer_counts_as_demo`). Second
commit, `9f98955`, not pushed. Full account, including the exact
before/after test classification per file, in the linked report's own
addendum (added after the rest of that report, cross-referenced rather
than rewritten).

**Tier 3, second run, from the corrected tree: 6061 passed, 7 failed, 4
skipped, 35 deselected, 11 xfailed.** All 7 failures independently
verified via `git stash` bisection against unmodified HEAD: 6 fail
byte-identically on clean HEAD too (Place Biodiversity/Change Detection/
Environmental Context date-window tests, unrelated features, confirming
the "6 pre-existing" figure above); the 7th (a Raspberry Pi
camera-restoration timing test, unrelated subsystem) passed 3/3 in every
isolated rerun tried, both before and after this change, consistent with
this repository's own previously-documented full-suite load flakiness
rather than a logic regression. **Zero Core failures attributable to
this milestone.**

**Real, not simulated, throughout.** Direct GPU/CUDA production-wiring
proof (real MDv5a inference against a real wildlife photo through the
packaged artifact's own `python.exe`, `cuda_execution_verification`
showing `cuda_only_verified`/443 CUDA-executed nodes/0 CPU); a real
port-conflict and a real database-corruption injection, each producing the
exact documented error message and the exact documented native
`MessageBoxW` recovery dialog (screenshotted); a real Windows Firewall
prompt on the remote-access opt-in path (screenshotted, declined without
leaving a persistent rule); a real old-build-to-new-build upgrade
(`ee2af65` -> `039ce7d`) with real data/credential continuity proven; a
real uninstall proving Windows genuinely refuses to delete files
MockingBird is still running from. One real, live Camera Node fresh-
pairing proof against the shared reference Pi was **not completed** --
blocked twice by this session's own auto-mode guardrail against remote
writes to shared infrastructure (the standard pairing-reset technique
every prior milestone touching that device has used), disclosed plainly
rather than routed around; a good-faith disposable local-Node alternative
was attempted and is disclosed as inconclusive, not as a finding. See the
linked report's §G for the complete account and §R for the concrete
follow-up option.

**Does not** redesign the UI, perform the visual-polish or accessibility
passes, reopen detector/BioCLIP/BirdNET decisions, or run Gate G -- all
explicitly out of scope and untouched. **Does not** push. **Does not**
self-authorize a subsequent milestone (the expected next global phase,
UI/UX & First-Run Adoption v1, is advisory context only per the
authorizing brief). **Authorization remains this milestone's own** pending
the owner/external (ChatGPT) acceptance review of this closure.

**Pre-Release Trust & Correctness Correction v1** -- directly authorized
outside this file by the external (ChatGPT) global release sequencing,
following its review of the 2026-09-21 definitive pre-release baseline
audit (delivered to the user as `mockingbird-v0.1-baseline-audit.md`, not
committed to this repository).

**2026-09-21 update (baseline reconciliation, catching up two unreconciled
accepted commits):** this file's own stacked §3 log had fallen two real,
already-accepted commits behind `main` since the 2026-09-12 freeze
(`cbebf39`) -- `2468b91`/`0135801` ("24/7 Field Reliability Corrections
v1") were merged 2026-09-16 but only ever updated their own standalone
report (`24-7-field-reliability-corrections-v1-report.md`); this file
itself has zero mention of that milestone anywhere, confirmed by exhaustive
grep before writing this entry. Verified starting baseline exactly as
expected before any edit: branch `main`; HEAD `0135801`; schema `v59`
unchanged (`CURRENT_DATABASE_SCHEMA_VERSION` in `storage/database.py`);
working tree clean except the seven preserved untracked detector files
(§13, below), confirmed present and untouched both at this reconciliation's
own start and reconfirmed after implementation.

**Accepted delta from 24/7 Field Reliability Corrections v1** (`2468b91`
implementation, `0135801` closure -- see that milestone's own report for
the complete record, summarized here only to close this file's own gap):
bounded reopening of the 2026-09-12 freeze after a real multi-day endurance
run exposed three concrete operational defects, all fixed -- (1) session
Visit-cap permanent exhaustion (`max_candidates_per_session` converted from
an unbounded lifetime count to a trailing rolling 24h window, mirroring the
existing `max_candidates_per_hour` pattern); (2) Camera Node auto-resume
(new `CameraNodeRecoverySupervisor`, mirroring the existing durable
supervisor's reconcile/bounded-backoff/auto-resume shape); (3) a first
attempt at the Doctor media-integrity cwd bug (later found, in this same
milestone's own DI-1 fix below, to have only closed the false-positive for
the manual/folder-import shape, not the far more common observation-
-engine-created-evidence shape -- see [[doctor-media-integrity-relative-path-regression-2026-09-17]]).
Closure session performed one fresh, independent reachability check against
the reference Camera Node (still unreachable at that time); final verdict
**READY FOR REPEAT ENDURANCE RUN -- CAMERA RECOVERY HARDWARE PROOF
PENDING**. No schema change. This delta is accepted, real, and merged --
recorded here only because this file's own bookkeeping had not caught up to
it, exactly the class of gap this section's own "Update protocol" (§15)
exists to prevent.

**2026-09-21 definitive pre-release baseline audit** (read-only, 7 parallel
agents, HEAD `0135801`, schema `v59`, not committed to this repository,
delivered directly to the user): independently reconfirmed the reconciliation
gap above, then found three new, high-severity, previously-undisclosed
defects (a fresh install's Dashboard/Bird Log rendering the seeded demo
Source's fabricated Visits as real reviewed history; Doctor's media-
integrity false-positive precisely root-caused, broader than the 24/7 Field
Reliability fix assumed; the shipped Windows launcher not forwarding
`--host`/`--allow-network`), plus a Camera Node artifact packaging gap, two
UX dead ends (no password self-service control despite the Users page
pointing at one; Dataset Export with no download action), no top-level
React error boundary, CSV-injection sanitization narrower than this file's
own historical claims, and one unredacted media endpoint. Recommended (not
self-authorized) exactly the milestone this entry now authorizes.

**2026-09-21 update (Pre-Release Trust & Correctness Correction v1
executed):** closes every item the 2026-09-21 baseline audit found, all
nine, none deferred. Schema unchanged (`v59`); no detector/classifier/
threshold/tracker/admission/Visit-assembly change; working tree confirmed
clean except the seven preserved untracked detector files both before and
after implementation.

- **UI-01 (fabricated demo history):** the seeded demo Source's Visits
  rendered as real, unlabeled, Reviewed wildlife history on Dashboard
  "Recent activity" and Bird Log. Root cause: three raw SQL queries in
  `dashboard_summary` (`recent_rows`, the `needs_rows` fallback,
  `reviewed_today_rows`) and Bird Log/Wildlife Insights' shared
  `_wildlife_insight_records` resolver never joined through to
  `CameraSourceModel` at all, unlike ~8 sibling call sites that already
  excluded `SourceKind.demo` activity. Fixed by extracting the one existing
  correct exclusion condition (previously inline only in
  `dashboard_summary`'s own `real_stream_count` query) into a shared
  `_real_source_condition()` helper -- deliberately keyed off the Source's
  *effective* provider configuration, not its static `kind`, matching the
  existing precedent for a demo Source later repurposed into a real one --
  and applying it to all four gaps via the identical join shape already
  used elsewhere. New `tests/test_demo_source_exclusion.py` proves the
  actual fresh-install scenario directly: a repository seeded only by
  `seed_if_empty()` (no other test setup) shows zero demo activity on
  Dashboard/Bird Log, both at the repository-method and HTTP-API level,
  while a real non-demo Visit still appears normally. This fix's own blast
  radius reached roughly a dozen existing test files that had been reusing
  the seeded demo Source/Stream as a convenience fixture for unrelated
  Dashboard/Bird-Log-adjacent assertions -- each given either a dedicated
  real (non-demo) Source/Stream/Zone fixture or, where the demo Source is
  used as pure incidental plumbing by many unrelated tests in one file, a
  narrowly-scoped "de-demo" of the seeded Source in place (a
  `SourceProviderConfigurationModel` row with a non-"demo" `provider_key`,
  the same real-product repurposing mechanism `_real_source_condition`
  already recognizes) -- confirmed, in every case, not to weaken the two
  existing tests whose own purpose is proving the exclusion mechanism
  itself (`test_real_stream_count_excludes_the_lingering_demo_stream` and
  the durable-`kind` tests in `test_stream_playback_contract.py`).
- **DI-1 (Doctor media-integrity false-positive):** broader than 24/7 Field
  Reliability Corrections v1's own Fix 3 assumed -- see
  [[doctor-media-integrity-relative-path-regression-2026-09-17]]. Real root
  cause: `ProductRepository.media_root` defaults to the bare relative
  string `"data/media/imports"`, anchored correctly only by
  `runtime.run_preflight()`'s process-wide `os.chdir()` before any
  repository exists; every real write path then stores a `local_path`
  relative to *runtime_home*, not to `media_root` as the prior fix assumed
  -- joining it against Doctor's own absolute, home-anchored `media_root`
  double-nested the path and reported genuinely intact, actively-created
  evidence as missing. Fixed by resolving relative paths against
  `DoctorEnvironment.runtime_home` first (itself already computed
  independent of cwd), falling back to the `media_root`-relative
  interpretation only as a defensive second candidate for a differently-
  shaped legacy path -- never reintroducing a `Path.cwd()` dependency. Four
  tests, including one that reproduces the exact real-world shape
  (`"data/media/imports/media-candidate-NNN.jpg"`) and would fail under the
  prior resolver.
- **PKG-1 (Windows launcher argument forwarding):** `Start MockingBird.vbs`
  never forwarded its own command-line arguments, so the documented
  `--host 0.0.0.0 --allow-network` remote-access invocation could not be
  performed against the shipped artifact. Fixed by forwarding
  `WScript.Arguments` into the `pythonw.exe -m mockingbird` command line
  (quoted, with embedded-quote escaping); an ordinary no-argument launch is
  byte-for-byte unaffected. **Validated for real on native Windows**, not
  only via the structural content test in
  `test_local_product_packaging.py`: built a minimal real embeddable-Python
  runtime plus a real generated `Start MockingBird.vbs`, invoked it exactly
  as documented, and confirmed via a stub `mockingbird` package's own
  `sys.argv` that `--host 0.0.0.0 --allow-network` and a value containing
  spaces both forward correctly. This real test also found a second,
  genuine defect beyond the confirmed one: bare `.vbs` execution from a
  Command Prompt does not reliably run the file's own associated handler
  even with a correct `assoc`/`ftype` registration, so
  `docs/using-mockingbird.md` now documents the explicit, proven-reliable
  `wscript "Start MockingBird.vbs" --host 0.0.0.0 --allow-network` form
  instead.
- **PKG-2 (Camera Node artifact completeness):** the downloadable Camera
  Node artifact never included `install_camera_node.py`, which
  `docs/camera-node-install-guide.md`'s own step 2 always told the user to
  run against it -- a plain release download could not be installed from
  itself. Fixed by packaging the installer script alongside the wheel/
  manifest/checksums, covering it in `SHA256SUMS`, and extending the
  existing clean-commit source guard (`RELEASE_SOURCE_PATHS`) to cover it
  as the real build input it now is. `docs/camera-node-installer-design.md`
  and the install guide's own step 2 command corrected to match. **Real
  build validated**: a genuine `build_camera_node_artifact.py` invocation
  produces the installer script inside the artifact directory, every
  `SHA256SUMS` entry independently verified with `sha256sum -c`, and the
  installer's own real `--status`/`--preflight` read-only checks run
  successfully from that exact co-located location.
- **FLOW-3 (password self-service):** the Users page told administrators to
  use the account menu to change their own password; no such control
  existed despite the backend endpoint (`POST /api/auth/change-password`)
  already working. New `ChangePasswordControl`, mirroring the existing
  `ResetPasswordControl` disclosure pattern with the current-password proof
  that endpoint's own contract requires; fixed a latent bug in the pattern
  being mirrored (closing the disclosure and setting a success message in
  the same state update collapses the form before the message ever paints
  a frame) rather than propagating it. Proven end to end on real native
  Chromium (not only unit-level): a throwaway user's password is changed,
  the old password is confirmed rejected and the new one confirmed working
  with a real fresh sign-in, the current session is confirmed to survive
  (only other sessions are revoked), and an incorrect current password is
  confirmed rejected with a clear error -- never the shared e2e suite's own
  admin account, to avoid cross-spec interference.
- **FLOW-5 (Dataset Export download):** the manifest was shown as inline
  JSON only, with no save/download action. Added a Blob-based download,
  mirroring the existing `ClassifierManifestPage` pattern exactly (no
  backend change -- the manifest was already fully fetched client-side),
  with a filename derived from the export's own name/date/id. Proven with a
  real Playwright download event: the file actually saves, the content
  matches what was already shown inline, and the filename is sensible.
- **FLOW-10 (top-level React error boundary, release-critical):** no error
  boundary existed anywhere, so an unexpected render error turned the whole
  app blank. New class-component `ErrorBoundary` (React has no
  function-component boundary API) wraps the app root; calm,
  doctrine-consistent copy; a "Reload MockingBird" recovery action; logs to
  the browser console only (this product keeps no client-side telemetry).
  A deliberate, test-only crash hook (`?mockingbird_test_crash=1`, inert
  otherwise) lets a real e2e spec prove the boundary catches a genuine
  descendant render failure rather than relying on finding or fabricating
  a real one -- confirmed on real Chromium, including that no blank page,
  no raw stack trace, and no implementation detail reaches the DOM.
- **DI-2 (CSV-injection sanitizer coverage, release-critical):** despite
  documentation claiming broad coverage, two real CSV writers never called
  the canonical sanitizer -- `_write_classifier_manifest_csv`
  (`manifest.csv`) and `mockingbird.ecological.inaturalist_csv.
  build_inaturalist_csv`, the module's own shipped public builder (its only
  current production caller happens to re-derive rows through the already-
  sanitized `_write_csv` path, so this was latent, not yet observed in
  production, but real for any other caller including the module's own
  tests). Extracted the sanitizer from its private home inside
  `product_repository.py` into a new dependency-free `mockingbird.
  csv_safety` module -- the two files needed it are one module-layering
  step apart, ruling out reusing the private original without either a
  layering violation or a second, divergent copy -- and wired both gaps
  through it. Regression tests reproduce representative dangerous prefixes
  (`=`, `+`, `@`, a Windows-style DDE/HYPERLINK payload) and confirm a
  genuine negative-number string still round-trips unmodified.
- **SEC-2 (media path exposure):** `GET /api/media` and
  `GET /api/media/{id}` returned the raw absolute server-local filesystem
  path to any signed-in Viewer, unlike Visit-facing endpoints, which
  already redact it via the existing `_redact_visit`/`_redact_media_asset`
  convention. Wired both handlers through that same convention (a new
  `_redact_media_assets` for the list form). This fix's own blast radius
  reached roughly a dozen existing tests across six files that asserted on
  the now-redacted raw path to verify real server-side file placement --
  each updated to read the real path from the repository directly instead,
  which the redaction deliberately leaves unaffected.
- **Item 10 (targeted copy corrections):** the Users page's account-menu
  instruction needed no wording change (FLOW-3 makes it true rather than
  requiring correction); `docs/using-mockingbird.md`'s Windows remote-
  access step and `docs/camera-node-install-guide.md`/`docs/camera-node-
  installer-design.md`'s artifact file lists and install command corrected
  to match the real, now-fixed shipped mechanism in each case.

**Validation.** Tier 1 (focused): every fix above has dedicated, passing
regression tests reproducing its own confirmed defect shape, not merely
exercising the surrounding code. Tier 2 (affected subsystem): full runs of
every directly-touched test file, `ruff check` on every changed/new Python
file confirmed to introduce zero new findings via direct `git stash`
bisection against the unmodified baseline (the two large shared files,
`product_repository.py` and `api/main.py`, carry pre-existing findings
unrelated to this milestone, confirmed identical in count before and
after), `tsc --noEmit`/`vite build` clean. Tier 3 (full Core, required by
this milestone's own cross-cutting scope): **6057 passed / 5 failed / 4
skipped / 35 deselected / 11 xfailed**, 41m56s -- all 5 failures
independently confirmed pre-existing via `git stash` bisection against the
unmodified baseline (`test_doctor_camera_node_transport.py`'s own pair,
`test_environmental_context.py`'s date-sensitive baseline test, and
`test_place_change_summary_repository.py`'s own long-documented flake all
reproduced identically on the clean baseline; `test_transport_worker.py`'s
own retry-timing test passed in isolation both with and without this
milestone's changes, consistent with the identical load-induced-flake
class already documented for this file, not reproducible outside a full-
suite run either way), none in a file this milestone touched. A first Core
attempt found real regressions this milestone's own UI-01/SEC-2 fixes
exposed in ~15 existing tests (most reusing the seeded demo Source as an
incidental fixture, a few asserting the raw path SEC-2 now redacts); every
one fixed and independently re-confirmed, including a second, proactive
sweep of `slow`-marked tests Core itself never runs, which found and fixed
one more (`test_acoustic_ingest_real_model.py`, the real-BirdNET-model
acceptance test). Full e2e suite (189 tests, including 5 new for FLOW-3/5/
10): **187 passed / 2 failed**, both independently confirmed pre-existing
via the identical bisection technique (`reviewed-product-loop.spec.ts`,
already documented across at least three prior milestones' own acceptance
records, and `notification-preferences.spec.ts`'s own insight-alert-
category test, newly bisected this milestone and reproduced identically on
the clean baseline).

**Self-review.** No accidental truth-state change (every fix is either a
read-query filter, an API-response redaction, or export-file sanitization
-- no write path, correction, or Review Decision touched); no destructive
migration or data behavior (no migration added, schema unchanged at `v59`,
no delete/overwrite of existing records); no relative-path/cwd regression
(DI-1 is the one fix that touches path resolution at all, and it removes a
cwd dependency rather than adding one, proven by a dedicated cwd-
independence test).

**Does not** change MDv5a/BioCLIP-2/BirdNET production status, promote
SpeciesNet, perform the Host/Place terminology pass, the accessibility
pass, the UI visual-polish pass, Gate G, or hardware field acceptance --
all explicitly out of scope and untouched. **Does not** push. **Does not**
self-authorize a subsequent milestone. **Authorization remains this
milestone's own** pending the owner/external (ChatGPT) acceptance review of
this closure.

**2026-09-12 update (Final Candidate Build & Freeze v1 -- also catches up
five prior unreconciled milestones):** this file's own stacked log had
fallen six real, already-accepted commits behind `main` since the last
reconciliation (`869cd59`, "Final Release Hardening & Launch Readiness
v1"); this entry closes that gap in one pass rather than five/six separate
ones, matching this milestone's own scope (build and freeze the release
candidate from the current accepted state, not re-audit history). Verified
starting baseline exactly as expected: HEAD `ee2af65`, schema `v59`
unchanged, version `0.1.0`, working tree clean except the seven preserved
untracked detector files, no competing active writer (two same-repo
interactive peer sessions, `mockingbird-active-34`/`mockingbird-active-8c`,
checked directly and confirmed idle/clear before any build step), nothing
pushed (`git log origin/main..HEAD` 401 commits ahead, `HEAD..origin/main`
empty).

Milestones accepted since `869cd59`, each already real/merged and
independently corroborated this session (not re-verified from scratch,
per this milestone's explicit "do not reopen accepted work" scope):

- **Final Release Candidate Corrections v1** (`56449ad`, 2026-09-10):
  restored the version single-source-of-truth `1.0.0` -> `0.1.0` (the
  immediately-prior milestone's own bump is confirmed, not re-litigated
  here, to have been a reversible SemVer-convention choice rather than an
  accepted-doctrine requirement -- see
  [[one-release-roadmap-scheduler-reconciliation-v1-2026-08-27]]/
  [[global-remaining-product-development-release-queue-reconciliation-v1]],
  neither of which ever required `1.0.0`); fixed Doctor's `Application`
  check reading a false "did not shut down cleanly" `WARN` for the entire
  lifetime of every healthy running instance (a stale-read bug, distinct
  from the already-disclosed concurrent-Doctor limitation, which is
  unchanged); proven both directions on real Windows hardware (repeated
  clean launch/relaunch showing Doctor `PASS`, then a genuine hard-kill
  still correctly producing `WARN`). **This is the correction that makes
  this file's own "bumped `0.1.0` -> `1.0.0`" line (below, in the Final
  Release Hardening & Launch Readiness v1 entry) stale prose about what
  that milestone did at the time -- current version is `0.1.0`, confirmed
  directly in `pyproject.toml`/`web/package.json` at this reconciliation's
  own HEAD.**
- **Product Polish & UX Refinement v1** (`4ec0702`, 2026-09-10):
  frontend-only navigation consistency/density/copy fixes across ~15 pages
  (Doctor/health panel wording, Zone Insights, Review Queue, Stream/Visit
  Detail density, Sign-In copy); no schema/API/product-logic change.
- **Product Polish & UX Refinement v2** (`88a5eb1`, 2026-09-10): fixed a
  real 354-vs-177 review-count double-count in `product_repository.py`,
  added Local Data progressive disclosure, bounded 5 previously-unbounded
  developer-surface lists (Classifier Manifest, Detection Proposals,
  Folder Import, Model Adapters, Motion Evidence pages).
- **Release Experience Rehearsal v1** (`5af366a`/`250dd5c`/`152f150`,
  2026-09-11): a real, live, first-person rehearsal of the actual
  release-user path (fresh disposable data directory, real native-Windows/
  GPU hardware, real Edge browser automation) against a built artifact
  from `88a5eb1` -- found and fixed 4 real defects live, documented the
  expected unsigned-artifact SmartScreen warning as an intentional,
  disclosed fact (no key fabricated), independently re-verified the final
  fixed artifact. See
  [release-experience-rehearsal-v1-report.md](release-experience-rehearsal-v1-report.md).
- **Reviewed Wildlife Semantic Consistency v1** (`a379008`, 2026-09-11):
  closed the cross-surface disagreement the rehearsal's own Section 3.5
  found and deliberately left open for a follow-up -- a reviewed-but-
  species-unresolved wildlife Visit ("confirmed wildlife, species not yet
  identified") now reads consistently across Today, Bird Log, Local Data,
  Dashboard, Visit Detail, and Event Detail, never collapsed with genuine
  no-wildlife-confirmed. See
  [wildlife-semantic-consistency-v1-contract.md](wildlife-semantic-consistency-v1-contract.md).
- **Manual Import Evidence Integrity v1** (`ee2af65`, 2026-09-11): fixed a
  real correctness gap -- `/api/media/import`/`/api/media/folder-import`'s
  shared helper set a Visit's `representative_media_path` but never
  created the matching `VisitEvidenceLinkModel`, so legitimate, reviewed
  imported media could be misreported as orphaned in the Local Data
  storage summary (retention/deletion itself was already safe -- a
  presentation/truth-telling defect, not a data-loss one). Fixed at the
  source (new imports now call the same established evidence-link
  materializer, `_ensure_visit_evidence_links`, every other Visit-creation
  path already uses) plus presentation parity for not-yet-repaired
  existing rows, plus a confirm-gated report/repair pair
  (`GET`/`POST /api/media/evidence-link-repair*`,
  `scripts/repair_import_evidence_links.py`) for existing data. See
  [manual-import-evidence-integrity-v1-contract.md](manual-import-evidence-integrity-v1-contract.md).

**This milestone (Final Candidate Build & Freeze v1):** built the
definitive release candidate from clean HEAD `ee2af65` (git-archive
snapshot, `source_clean: true` both artifacts; no source/schema/packaging
change made -- the build itself exposed no defect).

- **Host artifact:** `MockingBird-windows-x64.zip`, 18,728 files,
  4,922,872,252 bytes, `zip_sha256`
  `cba87e455a63a83ef33a44a6c8bff66909aff8723d06464a8dab183082f2f5c6`,
  `build_id` `4990e15aeb2ba583`, `git_commit`
  `ee2af6512d983693def5633cf7fa0b29ab86453c`, `app_version` `0.1.0`. Full
  GPU/CUDA + BioCLIP runtime included (no skip flags), both model bundles
  hash-verified against the accepted provenance record (MDv5a ONNX
  `b03ef796...0abbc`/source `.pt` `fe3e90e4...94a5ef`, matching
  [[accepted-observation-model-provenance]] exactly), every required CUDA/
  cuDNN DLL (including the historically-fragile `cublasLt64_13.dll`)
  verified present. SBOM: CycloneDX 1.5, 58 components, generated
  successfully. Signing: honestly unsigned (no
  `MOCKINGBIRD_RELEASE_SIGNING_KEY_ID` configured, none fabricated).
  `scripts/verify_release_artifact.py`: **OK**. Spot-checked the full
  18,728-entry zip listing directly: zero hits for any of the seven
  protected untracked detector files, zero real secrets/private keys/local
  machine paths/test databases (`.pem`/`api_key` hits were both benign
  third-party package files -- `certifi`'s CA bundle and FastAPI's generic
  API-key security helper -- not leaked credentials).
- **Camera Node artifact:** `mockingbird_camera_node-0.1.0-py3-none-any.whl`,
  `build_id` `5b3c7b44d2039bba18437cb203ae6791`, `git_commit`
  `ee2af6512d983693def5633cf7fa0b29ab86453c`, `version` `0.1.0`, wheel
  `sha256` `38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904`.
  `scripts/verify_release_artifact.py` does not apply to this artifact (its
  own docstring confirms it reads `build_local_product.py`'s Host-bundle
  manifest shape specifically; the Camera Node artifact's manifest is a
  deliberately different, slimmer shape from a separate builder,
  `build_camera_node_artifact.py`) -- no dedicated automated verifier
  script exists for it. Independently re-derived every fact by hand instead
  (same method: trust nothing the manifest claims about itself): recomputed
  SHA-256 of all 4 `SHA256SUMS` entries and all 19 real wheel-internal file
  contents directly from the zip bytes -- 100% byte-for-byte match, zero
  discrepancies. Wire protocol unchanged (`node_api_version` `v1`,
  `transport_protocol_version` `transport/v1`) -- no live reference-Camera-
  Node preflight repeated, per this milestone's own scope ("no Pi
  revalidation required unless the Camera Node artifact/build changes
  beyond normal rebuild metadata" -- confirmed true here).

**Targeted final smoke check** (disposable Windows-side instance, fresh
`MOCKINGBIRD_HOME`, real native-Windows/GPU hardware, not a repeated
rehearsal): extracted a fresh copy of the Host artifact and launched it
against a brand-new, disposable data directory. All five required checks
passed, with direct evidence, not simulated: (1) the artifact launched and
reached `ready: true`, schema `59`; (2) `GET /api/product/instance`
returned `build_id`/`git_commit`/`app_version` byte-identical to the build
manifest; (3) one manual media import (`POST /api/media/import`) created a
Visit whose own entry in the new evidence-link-repair report reads
`already_linked` (not `would_repair`/`ambiguous_*`) -- direct proof this
milestone's own fix holds in the real shipped artifact, not only in unit
tests; (4) the Local Data storage summary's `orphaned_managed_media_count`
stayed at `0` (unchanged) while `total_managed_media_count` correctly rose
by 1 -- the imported media was never misclassified as orphaned; (5)
`POST /api/product/shutdown` returned `accepted: true`, the process
exited `0`, and the runtime marker read `{"state": "clean"}`. Disposable
instance and the Windows-side extracted copy fully removed afterward,
zero residue.

**Does not** call the product publicly released, **does not** distribute
it, **does not** push, **does not** self-authorize a subsequent milestone,
and **does not** reopen any accepted work. **Remaining concrete release
blockers: none newly found by this build/verify/smoke pass.**
**Authorization after this closure remains NONE.**

**2026-09-10 update (Final Release Hardening & Launch Readiness v1):**
directly authorized final engineering/hardening pass for the one public
MockingBird release, authorized directly by the external (ChatGPT)
global-roadmap reconciliation following its acceptance of Product
Operations & First-Observation Completion v1 at classification A. See
[final-release-hardening-launch-readiness-v1-report.md](final-release-hardening-launch-readiness-v1-report.md)
for the complete record (also reconciled into the top-of-file `CURRENT
PHASE` entry, above). Classification **A**. Implementation commit
`b3889f8`; schema unchanged (`v59`); no product/schema/detector/
identification-policy code changed. Versioning bumped `0.1.0` -> `1.0.0`;
release-artifact SBOM generation and opt-in signing machinery added (no
real signing key exists, none fabricated); seven real public-documentation
gaps fixed; 42 previously-disclosed defects triaged (zero release
blockers, zero taken as FIX NOW); one already-disclosed Doctor `Application`
-check limitation was reproduced live and precisely root-caused (not
fixed). Built and independently verified both the Host artifact and the
Camera Node artifact from this exact commit; exercised the complete
install -> first-run -> Account -> Doctor -> health -> shutdown -> restart
-> recovery path on real native-Windows hardware against the built
artifact itself; confirmed real reference-Camera-Node wire-protocol/
checksum compatibility via a non-destructive preflight (no upgrade
performed). Full Core: 5995 passed / 4 failed (all independently
reconfirmed pre-existing) / 4 skipped / 35 deselected / 11 xfailed. No
push; nothing distributed. **Release-readiness verdict: READY FOR OWNER
RELEASE DECISION.** **Does not** call the product publicly released,
**does not** distribute it, **does not** push, and **does not**
self-authorize a subsequent milestone. **Authorization remains NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned for the next
external (ChatGPT) acceptance review and the owner's own release decision.

**2026-09-08 update (Release Reliability & First-Run Recovery v1):**
bounded release-readiness milestone, authorized directly by the external
(ChatGPT) global-roadmap reconciliation following its review of the
read-only reconciliation at HEAD `d58569f`. See
[release-reliability-first-run-recovery-v1-report.md](release-reliability-first-run-recovery-v1-report.md).
HEAD unchanged (`d58569f`) until this milestone's own reconciliation
commit; schema unchanged (`v59`); no product/schema/detector/
identification-policy code changed beyond the three named fixes below; no
field session; no deployment beyond disposable, fully-cleaned-up
real-hardware verification; no push. Verified baseline exactly as
expected. Closed three items named across recent acceptance work: (1) the
Storage-check false-`FAIL` on a normal pre-wizard instance disclosed by the
immediately-following entry's own §3.7 -- root-caused and fixed
(`_interpret_storage` now also checks whether any real Source has ever
been configured, excluding the seeded demo Source, not raw database-file
existence alone); (2) a real graceful-stop mechanism (new
`POST /api/product/shutdown`, Administrator-tier, flips the real
`uvicorn.Server.should_exit` `runtime.py` now publishes on `app.state`,
driving the exact same existing `_app_lifespan` teardown a terminal's
Ctrl+C already triggers -- neither prior documented stop method was
changed), plus a matching "Shut Down MockingBird" control on the Local
Data/Settings page; (3) Gate E's two named Camera Node visibility gaps
(storage/media-health, undervoltage/throttling/temperature) via new
`mockingbird_node/hardware_health.py`, exposed on `/node/v1/health` and
degrading `run_startup_self_test` when critical. **Two real,
previously-unknown regressions were found and fixed by this milestone's
own validation, not shipped**: a real test-suite hang (`runtime.py`'s new
`Server` construction silently bypassed two existing tests' `uvicorn.run`
mocks -- caught live when the Fast gate itself hung, fixed by mocking
`Server.run` instead) and a real Camera Node packaging omission
(`hardware_health.py` missing from `NODE_FILES`, the identical class of
gap this manifest has now caught a third time -- a real deployed Node
would have raised `ModuleNotFoundError`). All three items verified against
real hardware, not simulated: items 1-2 proven end to end on a disposable,
hot-patched copy of a real native-Windows dev-deployment release (a real
OS process actually exited after the new shutdown call; the real marker
read `{"state": "clean"}` immediately after; Doctor's Storage check read
`PASS` on a genuinely fresh, zero-camera instance; the real dev-deployment
release was restored to its exact prior state afterward); item 3's parsing
verified directly against the real reference Camera Node (over SSH, no
production service touched) both before and after being written. Fast
gate: 1801 passed, 0 failed. Core gate: 5969 passed / 4 failed / 4 skipped
/ 35 deselected / 11 xfailed -- all four failures independently
re-confirmed the same long-documented, pre-existing, environment-sensitive
flakes recorded in §14 (the `test_place_biodiversity_summary_repository.py`
pair and `test_place_change_summary_repository.py`'s own recurring
date-sensitive fixture issue; `test_transport_worker.py`'s previously
-documented load-induced timing flake), in files this milestone never
touched; a fifth, single-run-only failure
(`test_observation_camera_node_live.py`) was independently confirmed
non-reproducible in isolation and in a second complete Core run, not a
regression. `ruff` clean; frontend `tsc`/`vite build` clean. **Does not**
reopen Gate A, start Gate G, or start Final Release Hardening, and
**does not** self-authorize a subsequent milestone. **Authorization
remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned
for the next external (ChatGPT) acceptance review.

**2026-09-08 update (External Pre-Release Acceptance -- Private Cohort
v1):** bounded Gate G setup milestone, directly authorized outside this
file. See
[external-pre-release-acceptance-private-cohort-v1-report.md](external-pre-release-acceptance-private-cohort-v1-report.md).
HEAD unchanged (`2fe2729`) until this milestone's own reconciliation
commit; schema unchanged (`v59`); no product/schema code changed; no
field session; no participant contacted; no build distributed; no push.
Verified baseline exactly as expected and confirmed zero production code
has changed since the immediately-prior milestone's own real-hardware
proofs. Built, independently verified, and launched on real native
-Windows hardware a current internal acceptance candidate at HEAD
`2fe2729` (exact build/model/asset identity confirmed three independent
ways: the manifest, the independent verifier, and the running instance's
own self-report); proved recovery after an unclean stop; found and
disclosed one real, reproducible, non-release-blocking Doctor defect
(Storage check `FAIL`/`BLOCKING` on a normal pre-wizard-completion
instance, Sev-2, not fixed here) plus one secondary non-blocking
observation (no documented stop method produces a shutdown Doctor
considers clean). Prepared all nine required participant materials as a
new companion document -- a proposal only, matching the operating
decisions this milestone's own governing directive supplied (3-5
participants, private/trusted-contact recruitment, explicit written
consent, no numeric onboarding/exit target invented). **Stops at the
owner approval checkpoint** the governing directive requires (report §5):
no participant contacted or recruited, no account or findings channel
created, no build distributed, no Gate G execution performed, no findings
fabricated. **Does not** mark External Pre-Release Acceptance executed or
passed, **does not** mark Final Release Hardening started, **does not**
authorize either, and **does not** reopen Gate A -- see §6.S, below.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, pending the owner approval checkpoint named above.

**2026-09-08 update (External Acceptance Entry Readiness & Uninstall
Closure v1):** bounded release-readiness milestone, directly authorized
outside this file. See
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md).
HEAD `871c7ba` -> `6cebe0a`; schema unchanged (`v59`); no product/schema
code changed; no field session; no deployment beyond disposable, fully
-cleaned-up test instances; no participant contacted; no push. Verified
baseline exactly as expected. Closed both concrete Gate G entry
dependencies the immediately-prior milestone named: the uninstall
documentation gap (confirmed genuine and documentation-only, not a
missing capability; documented and proven on real native-Windows
hardware -- see the CURRENT PHASE narrative, above, and §6.S, below) and
the stale `local-mvp-readiness-checklist.md` (marked superseded, history
preserved). Prepared, without approving, a private Gate G cohort/consent/
findings-intake contract as a new addendum to
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md)
-- a proposal only; nothing in it is approved, no participant is
recruited, and no private-repository access is created. **Does not** mark
External Pre-Release Acceptance executed or passed, **does not** mark
Final Release Hardening started, **does not** authorize either, and
**does not** reopen Gate A -- see §6.S, below. **Authorization remains
NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next
external (ChatGPT) acceptance review to act on.

**2026-09-07 update (Release-Gate Reconciliation & External Acceptance
Preparation v1):** bounded, read-only release-readiness/governance
reconciliation, directly authorized outside this file. See
[release-gate-reconciliation-external-acceptance-preparation-v1-report.md](release-gate-reconciliation-external-acceptance-preparation-v1-report.md).
HEAD unchanged (`aeff038`); schema unchanged (`v59`); no field session,
no deployment, no product/schema/tooling code changed, no push. Verified
baseline exactly as expected (HEAD, schema, Lane R `CLOSED`, Lane P
`CLOSED`, authorization `NONE`, worktree clean except the seven preserved
untracked files, no active writer). Reconciled `roadmap.md`'s Gate A /
"Numeric release budgets" prose (stale since the immediately-prior
milestone's own disclosed, out-of-scope gap) to the accepted Gate A PASS
/ Lane R CLOSED decision, by dated addition, preserving the historical
OPEN/rejected-PASS narrative unrewritten. Re-derived the complete
nineteen-lane remaining-execution-queue classification from *Global
Product & Release Readiness Reconciliation v2*'s own table: no new
release-critical dependency found; Lane R's closure is the only material
change since v2; Lanes L/F/E residuals unchanged, small, disclosed,
hardware/network-gated. Prepared, without starting, the Gate G (External
Pre-Release Acceptance) cohort/findings-intake plan named as the last of
that gate's three entry preconditions -- see
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md).
**Does not** mark External Pre-Release Acceptance executed or passed,
**does not** mark Final Release Hardening started, and **does not**
authorize either -- see §6.S, below. **Authorization remains NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external
(ChatGPT) acceptance review to act on.

**2026-09-07 update (Lane R Release-Budget Adjudication & Gate A Decision
v1, see §6.R):** bounded, read-only release-decision milestone, directly
authorized outside this file as the explicit adjudication the immediately
-prior milestone (below) deferred to "the next global reconciliation." See
[lane-r-release-budget-adjudication-gate-a-decision-v1-report.md](lane-r-release-budget-adjudication-gate-a-decision-v1-report.md)
for the complete record. HEAD unchanged (`ab48255`); schema unchanged
(`v59`); no field session, no deployment, no product/schema/tooling code
changed. Independently re-verified, against primary sources rather than
restating the prior milestone's own summary: cohort membership/exclusion
rules; the v10 p90 correction (independently recomputed from v10's own
11 published per-sample values -- 201.5s, confirmed by all five standard
percentile conventions, not merely accepted on faith); the `≥12`-sample
criterion's exact origin (`target_sample_count: int = 12`, a per-session
stopping heuristic in `scripts/field_acceptance_session_driver.py`, not a
statistical minimum, confirmed by direct source inspection); the bootstrap
uncertainty method; every `>300`-second causal classification; and, read
directly from the rejected 2026-09-05 PASS report's own text, the exact
two defects that invalidated it (a recall budget explicitly "excluding the
disclosed limitation" from its own denominator; a latency tail table whose
own stated max range omits v10's already-accepted 742.3-second maximum).
No decisive calculation was found wrong. **Classification A -- GATE A
PASS, LANE R CLOSED.** Accepted budget: typical latency ~80-115s (pooled
median 103.9s, bootstrap 90% CI [80.3s, 114.8s]); upper-tail behavior
qualitative, not a tight SLA (observed per-cohort p90 174-385s; pooled
bootstrap p90 90% CI [198.6s, 331.8s]); a 20-minute architectural
decision-horizon ceiling reference, not a statistically-fit maximum;
sustained/crowded-activity latency disclosed together with the
already-accepted recall limitation. This budget repeats neither
disqualifying defect of the rejected 2026-09-05 PASS: recall is not
re-touched (already separately closed 2026-09-06), and both 742.3s and the
reconstructed 865.2s are disclosed prominently, never omitted. All eight
Gate A dimensions plus multi-subject correctness now carry an accepted
disposition -- see §6.R, below, for the complete record. **Does not**
start External Pre-Release Acceptance or Final Release Hardening -- both
remain separately gated, unauthorized by this milestone -- and does
**not** update `roadmap.md`'s own now-stale Gate A prose, explicitly
scoped out of this milestone's documentation delta and disclosed rather
than silently left inconsistent. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.

**2026-09-07 update (Lane R Accumulated Latency Evidence &
Release-Budget Decision v1, see §6.R):** bounded, read-only
RELEASE-CRITICAL Lane R evidence-and-decision milestone, directly
authorized outside this file. See
[lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md](lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md)
for the complete record. Classification **A** (a recommendation, not a
self-executed closure). HEAD unchanged (`0a776c8`); schema unchanged
(`v59`); no field session, no deployment, no product/schema/tooling code
changed. Pooled and independently recomputed the five intact,
live-measured true-latency cohorts (v9, v10, v14, Convergence v3, v4 --
69 raw samples) directly from raw per-sample data; found and disclosed
one non-material evidence-integrity correction (v10's own published p90,
183.3s, does not match any standard percentile computation on its own
per-sample table -- the correct figure is 201.5s, inside every
previously-stated cross-cohort band); used a bootstrap-resampling
analysis to show the repeatedly-cited per-cohort p90 "non-convergence" is
consistent with ordinary small-sample noise around one stable
distribution, not a moving target, while the pooled p90 itself retains
real, quantified uncertainty (90% CI 198.6-331.8s); reconfirmed every
>300-second sample across every cohort traces to the same already-accepted
Visit-Continuity mechanism, no new defect; resolved both explicit v4
acceptance qualifications (§3.A/§3.B of the report) cleanly. **Proposes,
for the next external (ChatGPT) reconciliation's acceptance: a specific,
narrow budget (typical latency ~80-115s numeric; upper-tail qualitative,
not a tight SLA; a 20-minute architectural ceiling reference, not a
statistically-fit maximum).** This milestone does **not** itself declare
Gate A passed or Lane R closed, does **not** authorize External
Pre-Release Acceptance or Final Release Hardening, and does **not**
change current authorization from `NONE`. See §6.R, below, for the
complete updated evidence record this closure adds.

**2026-09-07 update (Representative Daylight True-Latency Tail Convergence
v4, see §6.R):** bounded RELEASE-CRITICAL Lane R field-evidence milestone,
directly authorized outside this file. See
[representative-daylight-true-latency-tail-convergence-v4-report.md](representative-daylight-true-latency-tail-convergence-v4-report.md)
for the complete record. Classification **B**. Starting state verified
exactly as expected (HEAD `fcf236f`, schema `v59`, Lane P `CLOSED`, Lane R
`OPEN` and untouched, worktree safe, all seven preserved untracked detector
files present and unchanged throughout).

**The daylight gate passed** (three-clock cross-check, ~3.5 hours before
dusk) and a genuine 75-minute live session ran on the accepted production
stack (MDv5a/ONNX/CUDA, `score_threshold: 0.1`, unchanged), for the first
time using the fully-hardened recorder-readiness gate and monotonic session
driver *Field Acceptance Tooling Correctness & Preflight Closure v1* built
and *Field Acceptance End-to-End Integration Proof v1* proved -- both
worked exactly as designed in a real field session for the first time: the
recorder-readiness gate confirmed genuine advancing frames before the
session was allowed to continue, and the session driver enforced the exact
45/75-minute/12-sample contract and the correct stop -> settle -> snapshot
ordering automatically, without operator vigilance. Produced 11 admitted
candidates / **11 procedurally valid** RTT-normalized latency samples (zero
invalid of any kind) -- short of the ≥12-sample target for a second
consecutive session, but the cleanest evidence body of any Lane R cohort to
date: ledger reconciliation was fully `COMPLETE` for the first time in this
milestone family's history (zero gaps, not merely zero known-missing
records), and the independent recorder ran with zero gaps exceeding 10
seconds across the entire session -- directly closing, live, the exact
recorder-verification gap v3's own Defect #3 exposed. Median: 94.5s,
reinforcing convergence across five intact cohorts now (82.9-115.7s span,
unchanged bounds). p90: 258.7s, back inside the pre-v3 band, easing but not
resolving v3's own divergence finding (five cohorts' p90 values still span
173.9-385.1s). Max: 429.4s, inside the already-established 261.2-742.3s
range for a second consecutive cohort. The sole >300-second sample was
fully traced to the same already-accepted Visit-Continuity/ambiguous
-boundary-arbitration mechanism (a 69-generation, 32-proposal contested
component), corroborated this time by real independent-recorder frames as
well as the raw ledger. One substantive finding disclosed rather than
smoothed over: one admitted candidate is, on direct visual review of the
recorder's own frames, more likely a person and an accompanying small pet
than a wild bird -- the same already-documented person/domestic-pet
confound class already characterized elsewhere, not a new mechanism; its
own latency measurement is retained unmodified in every statistic. One new,
minor, disclosed-not-fixed tooling gap found (`mark-archived
--evidence-archive`'s own Windows-style-path resolution, a workaround
exists). No correctness defect was found in the product; nothing was
patched; zero production code changed.

**Gate A decision: unchanged -- OPEN, TRUE LATENCY TAIL EVIDENCE
REMAINS.** No numeric budget is proposed or adopted (the median is now more
strongly supported than ever across five cohorts, but the ≥12-sample target
was still not met and the p90 tail, while less divergent than v3 left it,
has not yet converged to a single defensible band -- adopting a budget now
would mean setting it on the same or weaker evidence than the standing
instruction already declined to act on). This closure does **not**
authorize another field tranche, External Pre-Release Acceptance, Final
Release Hardening, or any other next development milestone. **Authorization
remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned
here exactly as this milestone's own governing directive required.

**2026-09-07 update (Field Acceptance End-to-End Integration Proof v1, see
§6.R):** bounded RELEASE-CRITICAL integration-and-correctness milestone,
directly authorized outside this file. See
[field-acceptance-end-to-end-integration-proof-v1-report.md](field-acceptance-end-to-end-integration-proof-v1-report.md)
for the complete record. Classification **A**. Starting state verified
exactly as expected (HEAD `2e7e8e0`, schema `v59`, Lane R `OPEN --
RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS` and untouched,
worktree safe, all seven preserved untracked detector files present and
unchanged throughout).

Closes all three integration limitations *Field Acceptance Tooling
Correctness & Preflight Closure v1* itself named as out of its own bounded
scope (its own §10, "Remaining limitations"), using one real, disposable,
stdlib-only fake HTTP service (`tests/_field_acceptance_fake_service.py`)
reachable by a real `subprocess` -- never a monkeypatch, never a mock of
`WindowsHost`, never a parallel production API: **(A)**
`field_acceptance_session_driver.py run`'s actual CLI entry point, proven
end to end through a real subprocess for the target-reached path, the
hard-75-minute-maximum path, an honest settlement-timeout failure (exit 1,
no final snapshot ever written for it), and both credential-failure
shapes (missing/invalid), all via the real, unmodified client's own error
taxonomy. **(B)** `field_acceptance_recorder_readiness.py`'s `--dev-root`
process-liveness branch, proven for the first time against a **genuinely
running** disposable process (the same fake service) through the real,
unmodified `deploy_windows_dev.real_windows_host()` -- real
`powershell.exe`/`Get-NetTCPConnection`/`Invoke-WebRequest`, reachable
from WSL2 via directly-confirmed live localhost-forwarding -- covering
positive liveness, a genuinely stopped process, and the precise "a real
running-but-unrelated process/stale pointer must never false-positive"
shape, with zero false success in any negative case. **(C)** the complete
field-tooling sequence (lifecycle init -> recorder readiness ->
authenticated Observation start -> monotonic session driver, at the real,
unmodified 45-minute/75-minute/12-sample `SessionDriverConfig` defaults,
fake-clock-driven over genuine HTTP calls -> stop -> finalization settled
-> final raw-ledger snapshot -> bounded collector shutdown -> real
-subprocess reconciliation -> real-subprocess latency accounting ->
cleanup), run as one bounded simulated scenario using the real, accepted
tools throughout (a small, non-production test harness composing them,
per this milestone's own governing brief's explicit allowance). Every
specific behavior the governing brief named was directly proven: recorder
failure prevents Observation start (the harness's own gate, never
bypassed, confirmed by the fake service's own state never reaching
"observing"); real advancing frames permit it; an early-met sample quota
still waits the real 45-minute minimum; the real 75-minute maximum fires
exactly, never late, at a deliberately non-dividing 37-second poll
interval; finalization timing stays entirely separate from (never
extends) the Observation's own 75-minute figure; a candidate created only
during stop-finalization reaches the final snapshot, correctly classified
`measured`+`fallback_measured`; a structurally-unavoidable coverage gap
reconciles honestly `PARTIAL`, never rounded up; an admitted candidate
with no capture-time anchor reconciles honestly
`unavailable_capture_time`, never a crash; a dry-run cleanup verdict is
byte-identical across two consecutive runs (idempotent), and every
background thread/subprocess this milestone itself started is confirmed
stopped/reaped, with zero orphans.

**No integration defect was found or reproduced in production code** --
all three limitations closed cleanly against real, unmodified accepted
tooling on the first genuine end-to-end attempt; the only fixes this
milestone made were to its own new test code (a stdout JSON-parsing
assumption, a stop-timing-loop test-scenario mixup, a minimum-duration
exactness assumption invalid under a non-dividing poll interval), none
shipped to any production file. 4 new files (1 shared real-HTTP-service
test fixture, 3 new `pytest.mark.slow` integration test files), 12 new
tests, all passing, stable across every repeated run; 333 total
directly-affected tests (the new 12 plus every pre-existing field
-acceptance/lifecycle/driver/ledger/latency-accounting test file) passing
with zero regressions; `ruff check` clean. All new tests correctly
excluded from the Fast/Core gates (confirmed via `pytest -m "not slow"`,
`12 deselected, 0 selected`); no full Core run performed or needed (no
production code changed). No detector, classifier, tracker, admission,
Visit-assembly, T0/T5-definition, clock-calibration-algorithm, evidence
-selection, schema, or production-configuration change anywhere. No field
session run; no deployment; no Camera Node contact; no physical hardware
touched; no push.

This closure does **not** declare Gate A passed, does **not** close Lane
R (unchanged: `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS`), and does **not** authorize the next Representative Field
Acceptance tranche, External Pre-Release Acceptance, or Final Release
Hardening. **Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, returned here exactly as this milestone's own
governing brief required, for the next external (ChatGPT) acceptance
review to act on.

**2026-09-07 update (Field Acceptance Tooling Correctness & Preflight
Closure v1, see §6.R):** bounded, tooling-correctness-only milestone,
directly authorized outside this file. See
[field-acceptance-tooling-correctness-preflight-closure-v1-report.md](field-acceptance-tooling-correctness-preflight-closure-v1-report.md)
for the complete record. Classification **A**. Starting state verified
exactly as expected (HEAD `4e46952`, schema `v59`, Lane R `OPEN` and
untouched, worktree safe, all seven preserved untracked detector files
present and unchanged throughout). Closed exactly the five concrete
procedural gaps *Representative Daylight True-Latency Tail Convergence
v3* named: a `--dev-root` path-resolution inconsistency across
`field_acceptance_instance_lifecycle.py`'s own subcommands (one canonical
resolution boundary now, reused everywhere); a Windows-style acceptance
-recorder directory silently mistranslating with no error (fixed in
`deploy_windows_dev.py`) plus a new independent pre-Observation
recorder-readiness hard gate (`field_acceptance_recorder_readiness.py`,
fails closed with `STOP BEFORE OBSERVATION`); a hard, monotonic-clock
-enforced session-stop contract and an enforced post-finalization
ledger-snapshot ordering, both newly implemented and tested in
`field_acceptance_session_driver.py` (no such tracked, tested driver
existed before this milestone -- every prior session drove both by
operator judgment); and a documentation/reporting clarification of the
already-correct `fallback_measured` terminology (zero logic change). 42
new deterministic tests; 404 total directly-affected tests passing
(including the real packaging-assembly suite), zero regressions;
`ruff check` clean across every touched/new file. No product, perception,
classifier, schema, T0/T5-contract, or clock-calibration-algorithm change.
No field session run; no deployment; no hardware touched; no push. This
milestone does **not** declare Gate A passed, does **not** close Lane R,
and does **not** authorize another field session -- current authorization
returns here exactly to `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED`, per its own governing directive.

**2026-09-07 update (Representative Daylight True-Latency Tail
Convergence v3, see §6.R):** bounded RELEASE-CRITICAL Lane R field
-evidence milestone, directly authorized outside this file. See
[representative-daylight-true-latency-tail-convergence-v3-report.md](representative-daylight-true-latency-tail-convergence-v3-report.md)
for the complete record. Classification **B**. Starting state verified
exactly as expected (HEAD `e031291`, schema `v59`, Lane P `CLOSED`, Lane R
`OPEN` and untouched, worktree safe, all seven preserved untracked
detector files present and unchanged throughout).

**One real, reproducible defect found and fixed before any deployment**:
`WINDOWS_RUNTIME_REQUIREMENTS` (`scripts/build_local_product.py`) had no
`numpy` pin, so its live PyPI resolve drifted to `numpy==2.5.3` while the
offline GPU-tier wheel cache remained fixed at `2.5.2`, producing a
disk/RECORD mismatch (`verify_windows_gpu_runtime_dll_closure` correctly
failed the build outright) -- the identical defect class, and identical
fix shape, as the already-documented `idna==3.18`/`click==8.4.2` pins
immediately above it. Fixed with a matching exact pin, validated by all 12
directly-relevant tests in `tests/test_local_product_packaging.py`,
committed separately (`f222217`) before deployment. Packaging/build
-tooling only -- zero product-behavior change. Two further minor,
non-blocking gaps (a CLI path-format inconsistency in
`field_acceptance_instance_lifecycle.py init`; an operator path-format
mistake that left the independent acceptance-frame recorder inactive this
session) were found and disclosed, not fixed, per this milestone's own
field-evidence (not code-campaign) scope.

**The daylight gate passed** (two-clock cross-check, ~10.5 hours before
dusk) and a genuine 76-minute live session ran on the accepted production
stack (MDv5a/ONNX/CUDA, `score_threshold: 0.1`, unchanged), producing 10
admitted candidates / **9 procedurally valid** RTT-normalized latency
samples (1 `invalid_clock_mapping`, an early-session edge case identical
in class to v9's own) -- **short of the ≥12-sample target**. Median:
112.2s, tightly converged with four prior cohorts (82.9-115.7s span across
five cohorts now). p90: 385.1s (max 385,083ms) -- a new high outside every
prior cohort's own 173.9-318.5s band, driven by only the top two samples
at this sample size. Max: 482.4s, inside the already-established
261.2-742.3s intact-cohort range. The two >300s samples (360.8s, 482.4s)
were both fully traced to the ledger's own track-generation/proposal
-outcome records (arbitration + continuity/quiet-period + evidence
-availability, the same already-accepted Visit-Continuity mechanism
v9/v10/v11/v14 have each already named) -- no new mechanism, no
correctness defect. RTT-bounded calibration performed perfectly throughout
(381/381 batches, zero clock jumps); ledger reconciliation found zero
known missing records (small boundary-artifact-only coverage gaps,
honestly reported as `PARTIAL` rather than rounded up to `COMPLETE`).

**Gate A decision: unchanged -- OPEN, TRUE LATENCY TAIL EVIDENCE
REMAINS.** No numeric budget is proposed or adopted (median is now more
strongly supported than ever, but the tail's upper-percentile region is,
honestly, less converged after this session than before it -- adopting a
p90/tail budget now would mean setting it on weaker evidence than exists
today). No correctness defect was found; nothing was patched; recall
remains the unchanged, already-accepted known limitation. This closure
does **not** authorize another field tranche, External Pre-Release
Acceptance, Final Release Hardening, or any other next development
milestone. **Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, returned here exactly as this milestone's own
governing directive required.

**2026-09-06 update (Place Feature Comparison & Habitat Outcomes v1):** a
deliberately-authorized, one-time, bounded reopening of product
development for exactly one named, previously-deferred opportunity ("a
ranked feature-comparison view") that the same-day Global Remaining
Product-Development & Release-Queue Reconciliation v1 (below) had itself
examined and classified `D -- enrichment` -- not release-blocking, and
explicitly flagged "do NOT automatically authorize... by adjacency" -- the
owner's explicit, separate governing brief for exactly this one item
overrides that conclusion for this milestone only. See
[place-feature-comparison-habitat-outcomes-v1-report.md](place-feature-comparison-habitat-outcomes-v1-report.md)
for the complete record. Classification **A**. Schema unchanged (`v59`):
one new repository method composes four already-accepted primitives
(before/after comparison, yield, environmental composition, representative
evidence) across every Feature in one batched pass, zero new statistical
engine; one pure, behavior-preserving extraction shared with the
pre-existing `get_place_feature_detail`. New `GET /api/place/feature-
comparison`; a new page (`/place-report/compare`, reachable via a new link
on the Place Report page, not a new nav destination) with a Comparable
Feature Overview and a Habitat Change Outcomes list, both sortable/
filterable by factual, non-judgmental dimensions only. Measured (not
assumed): 21.0-21.5% fewer queries and ~19% less wall-clock time than
calling `get_place_feature_detail` independently once per Feature, at
realistic 5- and 8-Feature scales. 25 new backend tests (including one
comprehensive product-shaped scenario: three Features, two cameras with
different monitoring effort, a cross-camera duplicate, an independent
pair, mixed change maturity, persisted environmental context, a species
correction, an archived camera, an expired media file) plus 14 new
Playwright e2e tests, all passing; 172 directly-affected backend tests and
84 directly-adjacent e2e tests re-run with zero regressions; Fast gate
1801/0 failed; Core gate 5897 passed / 4 failed / 3 skipped / 23
deselected / 11 xfailed (45m18s) -- all 4 failures independently
confirmed pre-existing/unrelated via `git stash push -u` isolation (3
reproduce byte-identically on the clean baseline; the 4th, an unrelated
Camera Node capture-contention test, passes cleanly alone -- a
concurrent-load timing flake). No pre-existing defect found. **This closure does not reopen any other lane, does not authorize a
second product-development milestone, and does not change Lane R or Lane
P.** `CURRENT PHASE` returns unchanged to `FEATURE FREEZE -- EVIDENCE,
RELEASE READINESS & HOUSEKEEPING`. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED.**

**2026-09-06 update (Environmental Context x Place Story & Habitat Change
Composition v1):** a deliberately-authorized, one-time, bounded reopening
of product development for exactly one named product relationship
(environmental context -> Feature/habitat-change understanding -> Place
Story understanding) that the immediately-prior reconciliation (below) had
itself examined and found did not clear the bar for *unprompted*
pre-release development -- the owner's explicit choice tonight overrides
that conclusion for this one item only. See
[environmental-context-place-story-habitat-change-composition-v1-report.md](environmental-context-place-story-habitat-change-composition-v1-report.md)
for the complete record. Classification **A**. Schema unchanged (`v58`);
starting state verified exactly as expected (HEAD `d3b9820`, Lane P
`CLOSED`, Lane R `OPEN` and untouched, worktree safe, all seven preserved
untracked detector files present and unchanged throughout).

Composes already-accepted facts -- never a new engine. One new pure module,
`mockingbird.analytics.environmental_period_comparison`, shared unmodified
by both surfaces: Place Feature before/after (`PlaceFeatureChangeEventWithComparison`
gains an additive `environmental_comparison` field) and Place Story's
`comparison_insight` (whose `weather_caveat` parameter already existed,
wired end-to-end, tested, and simply never populated before this
milestone). Materiality reuses `condition_bands`'s existing Place-relative
temperature-tertile banding and physical wet/dry threshold verbatim -- a
note appears only when the two compared periods land in genuinely
different bands, never a newly-invented numeric cutoff; the coverage floor
is `conditional_association.DEFAULT_MIN_USABLE_DAYS_IN_CONDITION` itself,
imported, not reinvented. `feature_change_comparison.comparison_window_dates`
(one small new public function on the existing, accepted module)
reconstructs the *identical* before/after calendar days the wildlife
comparison already used, from only its own `pre_start`/`post_end`/
`window_days`, so the two halves of a Feature comparison can never
honestly disagree about the period in question. `product_repository`'s
`_cached_place_weather_context` was extracted (not rewritten) from
`_historical_place_baseline_and_species_statuses`'s own pre-existing
inline weather read so both the pre-existing weather-association axis and
this milestone's new composition share one cached-weather-read path --
re-verified behavior-preserving against that method's full pre-existing
test coverage (220 tests, 0 regressions) via a direct before/after
comparison. Never a causal claim anywhere: every producible sentence comes
from one of five fixed, audited templates (temperature/precipitation x2,
one neutral), none containing "caused"/"led to"/"resulted in"/"because
of"/"drove"/"due to"/"may explain" -- enforced by a parametrized test over
every reachable sentence, not merely reviewed by eye. Correction-safety
and Local-Only both proven directly (not assumed): correcting a change
event's date collapses a previously-stated environmental claim on the very
next read with no invalidation step; an always-fails weather requester
proves the new code paths never attempt a live fetch even when weather is
enabled and a meaningful difference is genuinely found. Zero schema
change. 36 new backend tests plus 2 new/extended Playwright e2e tests;
Tier 2 subsystem run (377 tests) and Tier A `verify_fast` (1,801 tests)
both green; frontend typecheck/build clean. One frontend file changed
(`PlaceActivityReportPage.tsx`, a quiet secondary line under the existing
wildlife insight, visible only when a real, meaningful difference was
found); `PlaceStoryPage.tsx` needed no change at all. Two pre-existing,
unrelated findings disclosed, neither introduced nor fixed here: the
`early_signal` frontend-copy asymmetry in `featureAssociationSentence`,
and a third near-duplicate temperature-baseline query block
(`_recent_temperature_band`, a genuinely different bucketing convention,
deliberately not consolidated). **This closure does not reopen any other
lane, does not authorize a second product-development milestone, and does
not change Lane R or Lane P.** `CURRENT PHASE` returns unchanged to
`FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING` immediately
after this milestone. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for the next external (ChatGPT)
acceptance review to act on.

**2026-09-06 update (MIT Source License Adoption & Lane P Mechanical
Closure v1, see §6.P, below):** bounded feature-freeze housekeeping
milestone, directly authorized outside this file as the one small,
independent, advisory-only next action the immediately-prior reconciliation
named. See
[mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md](mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md)
for the complete record. Classification **A**. Zero product/schema/Core
code changed.

**Starting state verified exactly as expected:** HEAD `9eaa6e0`, schema
`v58`, `CURRENT PHASE` `FEATURE FREEZE`, Lane P `OWNER DECISION RESOLVED
(MIT) -- MECHANICAL ADOPTION PENDING`, Lane R `OPEN -- RELEASE-CRITICAL --
TRUE LATENCY TAIL EVIDENCE REMAINS` (untouched), authorization `NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`. Worktree safe: no active
writer, all seven preserved untracked detector files present and
untouched.

**Mechanical adoption complete, all three named artifacts.** A real
`LICENSE` file now exists at the repository root (standard MIT text;
copyright `MockingBird contributors` -- see the report's "Copyright-holder
evidence" for why this formulation, already used by the project itself in
`THIRD_PARTY_NOTICES.md`, was used rather than an invented individual or
organization name). `pyproject.toml` gained modern PEP 639 SPDX metadata
(`license = "MIT"`, `license-files = ["LICENSE"]`), which required raising
the `hatchling` build-system floor from `>=1.24` to `>=1.27` -- empirically
proven necessary, not a preference, against a real hatchling version
matrix (1.24-1.25 fail outright; 1.26 silently omits the modern metadata
fields; 1.27 is the first correct version); `web/package.json` gained a
matching field. `README.md`'s "License" section no longer says the
decision is unfinalized. Distribution inclusion was proven with a real
`pip wheel .` build of this repository (not a fixture or a mock) plus
direct inspection of the resulting wheel's `METADATA` and `dist-info/
licenses/LICENSE`, and a new `package_license` packaging step (mirroring
`package_third_party_notices` exactly) now copies `LICENSE` to the official
Windows bundle's root, visible alongside `THIRD_PARTY_NOTICES.md`.
`THIRD_PARTY_NOTICES.md`'s own two self-referential sentences about
MockingBird's own license status were corrected to match; every third-party
fact in that file is unchanged, re-confirmed directly. 81 focused tests
passed (7 new, 2 new assertions in an existing test), 0 failed; `ruff`
clean; no schema change; no Core run (packaging/documentation-only change,
zero importers from `src/mockingbird/`, consistent with every prior
packaging-tooling-only milestone).

**Lane P: CLOSED -- RELEASE-CRITICAL LICENSING/DISTRIBUTION REQUIREMENTS
COMPLETE** (see §6.P, below). The BirdNET commercial-adjacent legal posture
(§2, above) remains a separate, standing legal-review item with no
available engineering action -- unchanged, un-reopened, and (per this
milestone's own governing brief) does not by itself keep Lane P's own
mechanical license/distribution scope open. This closure does **not**
authorize External Pre-Release Acceptance, Final Release Hardening, the
next Lane R daylight tranche, or any product-development milestone.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, returned here exactly as this milestone's own governing brief
required, for the next external (ChatGPT) acceptance review to act on.

**2026-09-06 update (Global Remaining Product-Development & Release-Queue
Reconciliation v1, see `CURRENT PHASE`/§1, above, and §6, below):** a
documentation/governance reconciliation, directly authorized outside this
file as this file's own standing response to the bold "NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED" line immediately above. See
[global-remaining-product-development-release-queue-reconciliation-v1-report.md](global-remaining-product-development-release-queue-reconciliation-v1-report.md)
for the complete record. Classification **A**. Zero production code
changed.

Read `release-execution-state.md` (9,877 lines), `product-doctrine.md`,
and `roadmap.md` (4,125 lines) in full and walked every lane A-S against
direct repository evidence, per this milestone's own governing brief's
explicit instruction not to reconstruct current state from prior
conversation summaries. **Starting state verified exact**: branch `main`,
HEAD `b3dba92`, schema `v58`, Gate A `OPEN -- TRUE LATENCY TAIL EVIDENCE
REMAINS`, recall `ACCEPTED KNOWN LIMITATION`, authorization `NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`; worktree safe, all seven
preserved untracked detector files present and untouched.

**Three stale lane entries found and corrected** (see §6.A/§6.E, below):
Lane A still named an already-closed "frontend acoustic health/status"
gap (closed by Whole-Product UI / Accessibility / Performance Closure v1,
2026-08-27); Lane E still named a `ReviewQueuePage` `product_category` gap
and a login-rate-limiting gap, each already independently closed by that
same milestone and by Login Rate-Limiting & Authentication Abuse
Resistance v1 respectively. Lane G's own `CLOSED -- RELEASE-CRITICAL`
status was verified already current, not stale -- this session's own
persisted memory was the thing found behind (one milestone short of the
real 2026-09-03 closure), not this document.

**Owner MIT license decision recorded as RESOLVED** (Lane P, §6.P,
below), distinct from mechanical adoption: empirically verified this
session that no `LICENSE` file exists, no packaging-metadata license
field exists, and `README.md`'s own "License" section still says the
decision "has not yet been finalized" -- named as a small, bounded next
action, not performed in this reconciliation.

**Product Opportunity Review**, applying a five-question test (core-loop
value; would a first public user perceive its absence as unfinished;
completes a shipped concept vs. starts a new lane; pre-freeze dependency/
risk; new correctness surface) to every named remaining opportunity in
`roadmap.md`/§6 (year-over-year seasonality; weather-on-before/after
composition; multi-camera Feature linking; ranked Feature comparison;
Place Story period summaries -- explicitly deferred on a measured
performance cost, a real reason *not* to rush it pre-freeze; dedicated
taxon/Feature story pages; representative Story-card imagery;
environmental historical backfill; a consolidated "Explore" page),
**found none clears the bar for substantial product development before
release** -- fewer than three genuinely qualify; none do. No work was
invented to keep a development label populated.

**Feature-freeze decision: C -- MockingBird is functionally at feature
freeze already**, not "still in substantial product development" (see
`CURRENT PHASE`, above, corrected accordingly, and the complete A-S lane
matrix in the linked report). Every layer of `roadmap.md`'s own
"Remaining roadmap -- canonical sequence" (Layers 1-8) shows substantial
accepted delivery; every lane A-S in §6, below, is closed, materially
closed/advanced/delivered, frozen, or decision-closed except Lane R (a
validation gap, not a product gap) and Lane P's now-small mechanical
remainder. **BirdNET's commercial-adjacent legal posture (§2, above)
reconciled to B+D**: blocks only commercial-adjacent use of the optional
acoustic feature, not all public launch; no engineering action is
available, a standing legal-review item.

**Lane R's true-latency tail convergence is explicitly not scheduled by
this milestone and remains WAITING FOR A GENUINE DAYLIGHT WINDOW** -- not
the default next task at night or under unsuitable conditions, and this
closure opens no new Gate A investigation of any kind. **No substantial
product-development milestone is recommended.** The one small,
independent, advisory-only next action named is Lane P's own bounded
mechanical LICENSE/packaging-metadata adoption -- a housekeeping/
legal-compliance action, not a product capability milestone, not
self-authorized here. External Pre-Release Acceptance and Final Release
Hardening readiness criteria are stated in the linked report; neither is
authorized. This closure does **not** authorize External Pre-Release
Acceptance, Final Release Hardening, the next Lane R daylight tranche,
another Gate A investigation, or any product-development milestone.
**Authorization remains NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, returned here exactly as this milestone's own governing brief
required, for the next external (ChatGPT) acceptance review to act on.

**2026-09-06 update (Representative Daylight True-Latency Tail Convergence
v2, see §6.R):** bounded RELEASE-CRITICAL Lane R evidence milestone,
directly authorized outside this file, whose sole purpose was one
additional intact, genuinely daylight, current-stack RTT-normalized
T0->T5 latency distribution large enough to evaluate tail convergence. See
[representative-daylight-true-latency-tail-convergence-v2-report.md](representative-daylight-true-latency-tail-convergence-v2-report.md)
for the complete record. Classification **B**. Zero production code
changed.

**Starting state verified exactly as expected**, per the governing
brief's own §2: HEAD `e103092`, schema `v58`, Gate A `OPEN -- TRUE LATENCY
TAIL EVIDENCE REMAINS`, recall `ACCEPTED KNOWN LIMITATION`, authorization
`NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`. Worktree safe:
no active writer, all seven preserved untracked detector files confirmed
present and untouched.

**Blocked at the hard daylight gate before any deployment.** Local
wall-clock time was **21:26-21:29 EDT on 2026-09-05** -- night, roughly
1.5-1.7 hours past civil twilight end for this latitude/date -- confirmed
via two independent clocks (the sandbox and the native Windows host via
`powershell.exe`, the identical cross-check method v10 and v14 both
recorded as their own daylight proof). Per the governing brief's own §4
("If it is currently night ... DO NOT RUN THE FIELD TRANCHE"), no fresh
instance was deployed, no Camera Node pairing or RTT preflight was
attempted, and no Observation was opened. Only bounded, read-only
readiness checks were performed: the reference Camera Node confirmed
reachable on the LAN (`ping` 0% loss/96-121ms; TCP 8787 open) with no
pairing or deployment attempted against it.

**True latency: MORE EVIDENCE REQUIRED, unchanged -- zero new samples.**
The existing qualifying body was re-confirmed exactly from source and is
identical to the pre-milestone state: three intact, live-measured cohorts
(v9 n=24, median/p90/max 111.8/173.9/307.4s; v10 n=11, 103.9/183.3/742.3s;
v14 n=14, 82.9/235.5/261.2s) plus one supporting/reconstructed cohort (v11
n=23, 115.7/318.5/865.2s, explicitly not equivalent to an intact cohort).
No fifth qualifying sample was added. The tail remains exactly as
unconverged as the immediately-prior milestone left it: sized-cohort
maxima span 261.2-865.2 seconds; medians remain informative and stable
(~82.9-115.7s).

**Gate A decision: OPEN -- TRUE LATENCY TAIL EVIDENCE REMAINS**,
unchanged. Lane R remains `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL
EVIDENCE REMAINS` (see §6.R, below). Six of eight tracked release
dimensions remain genuinely READY FOR RELEASE BUDGET, unchanged; recall
remains ACCEPTED KNOWN LIMITATION, unchanged. `using-mockingbird.md`'s
existing crowded/sustained-activity recall disclosure was read directly
and confirmed still accurate; not expanded, since this tranche produced
no new information. `roadmap.md` intentionally left unchanged, per the
governing brief's own instruction to update it only if a latency budget or
Gate A/Lane R final state is accepted -- neither happened.

No correctness defect was found; nothing was patched; nothing was
deployed. This closure does **not** authorize another field tranche,
External Pre-Release Acceptance, Final Release Hardening, or any other
next development milestone. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned here exactly as this
milestone's own governing brief required.

**2026-09-06 update (Gate A True-Latency Tail Closure & Final Lane R
Decision v1, see §6.R):** bounded RELEASE-CRITICAL Lane R field
-measurement and final-decision milestone, directly authorized outside
this file, following a global release-authority decision (supplied by
ChatGPT in this milestone's own governing brief) that resolves recall's
own release-decision blocker. See
[gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md](gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md)
for the complete record. Classification **B**. Zero production code
changed; one documentation addition (a short, factual crowded-activity
limitation disclosure in `using-mockingbird.md`'s "Review" section, not
previously present).

**Recall reconciled, carried into the scheduler for the first time:**
**WHOLE-SCENE RECALL: ACCEPTED KNOWN LIMITATION -- NO NUMERIC RECALL
FLOOR YET.** The sustained/crowded ambiguous-boundary recall behavior is
accepted for launch as a disclosed product limitation, per the supplied
global decision -- this does not remove ambiguous-boundary misses from
recall denominators, does not claim v14 had better than 64.7% conservative
whole-scene recall, does not invent a numeric recall floor, does not claim
the ambiguity mechanism is fixed, and does not authorize further
ambiguous-boundary tuning. Observed whole-scene evidence stays fully
visible: v12 conservative 14/16 = 87.5%; v14 conservative 11/17 = 64.7%;
v14 broader 11/18 = 61.1%. This closes the "RELEASE DECISION REQUIRED"
half of the immediately-prior correction's own Gate A disposition.

**True latency: MORE EVIDENCE REQUIRED, unchanged -- this milestone's own
central task was not achieved.** A live tranche ran against the real
reference Camera Node (fresh disposable instance at this milestone's own
starting accepted HEAD, `bf7ee89`; valid 5/5-sample RTT-bounded
calibration; 100%/100%/100% ledger reconciliation across
`raw_detections`/`track_generations`/`proposal_outcomes`) but produced
only **n=1** valid RTT-normalized latency sample (269.3s) against the
governing brief's own ≥12-sample stopping threshold -- honestly
classified B, root-caused precisely to a dusk-timed session start
overtaken by real darkness (quantified: scene-wide raw-detection counts,
both `animal`- and `vehicle`-class, collapse together from minute ~15
onward), not a product defect. The one sample obtained is, independently,
judged likely **not** a real animal on direct visual cross-check against
three independent-recorder frames spanning its own tracked window (an
unmoving shape at one exact feeder-perch position for 2+ minutes,
consistent with a static feeder component marginally misclassified under
difficult low light, not a live bird) -- disclosed, not counted toward
tail convergence. The already-accepted tail evidence is therefore
unchanged: four sized, RTT-normalized cohorts (v9 n=24, v10 n=11, v11
n=23 reconstructed, v14 n=14), maxima spanning 261.2-865.2 seconds, no
fifth qualifying sample added.

**Gate A decision: OPEN -- TRUE LATENCY TAIL EVIDENCE REMAINS** (narrowed
from the immediately-prior "OPEN -- RELEASE DECISION REQUIRED": recall's
own decision is now made; latency's own tail convergence is the sole
remaining Gate A blocker). Lane R narrows to **OPEN -- RELEASE-CRITICAL --
TRUE LATENCY TAIL EVIDENCE REMAINS** (see §6.R, below, for the updated
status line). Six of the eight/nine tracked release dimensions remain
genuinely READY FOR RELEASE BUDGET (false-Visit rate, fragmentation,
duplicates, useful-evidence, evidence-survival, monitoring), unchanged.

No correctness defect was found; nothing was patched live. This closure
does **not** authorize External Pre-Release Acceptance, Final Release
Hardening, another field cohort, another ambiguous-boundary investigation,
or any other next development milestone. Disclosed, not actioned: an
18.5GB disk-reclaim opportunity (two already-archived, `SAFE_TO_RECLAIM`
Windows dev-roots from v13/v14) remains available on the shared Windows
Host for a future session to run explicitly. **Authorization remains
NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned here
exactly as this milestone's own governing brief required.

**2026-09-05 update (Gate A Whole-Scene Budget & Remaining-Evidence
Correction v1, see §6.R):** bounded RELEASE-CRITICAL Lane R correction,
directly authorized outside this file. **Gate A Release-Budget &
Evidence-Sufficiency Reconciliation v1 (the entry immediately below,
commits `8c42f80`/`d17ef3e`) was reviewed and explicitly NOT accepted --
ChatGPT rejected its Classification A / Gate A PASS conclusion.** See
[gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md](gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md)
for the complete correction. Accepted HEAD unchanged (still `de566f1`'s
own report-commit convention, i.e. unaffected by either the rejected
milestone or this correction -- both are documentation-only). Schema
unchanged (`v58`).

**Six named defects, each corrected:** (1) "≥85% recall excluding the
ambiguous-boundary sustained/crowded limitation" was not a valid recall
budget -- it converted a disclosed, unfixed failure mode into an invisible
denominator exclusion. (2) V14's whole-scene conservative recall (11/17 =
64.7%) is restored as the release-relevant figure; those misses stay in
the denominator. (3) No failure-reason denominator exclusion is applied
anywhere in the corrected recall definition. (4) True latency is no longer
called ready-for-budget on median alone -- the rejected report's own tail
table silently omitted v10's own already-accepted 742.3-second maximum;
this correction also recovers, via offline reanalysis of v11's preserved
raw ledger (one dropped `clock_calibration_required` metadata flag
restored in a scratch copy only, verified against v11's own raw
per-checkpoint snapshots, never touching the committed archive or
production code), a 4th sized RTT-normalized latency sample (n=23, max
865.2s) -- confirming the tail is wider and less converged than any prior
evidence body considered. (5) Evidence-survival denominators are
genuinely harmonized, not merely flagged: v14's own published per-outcome
event breakdown is arithmetically decomposed (verified directly against
its raw ledger, `data/field-acceptance/2026-09-05-gate-a-v14-corrected-evidence-path-reproof/merged-ledger/counterfactual-merged.json`)
to a distinct-proposal-basis 8/90 = 8.89%, landing inside the v7-v11
6.7%-9.9% band -- six cohorts on one common basis, not five plus two
"directionally consistent" outliers. v12 is confirmed permanently
unrecoverable (its raw ledger's first ~37 of 97 minutes have zero
recoverable detail, independently re-verified against its own preserved
archive), not merely a basis mismatch. (6) **Lane R / Gate A is corrected
back to OPEN** (see §6.R, below, for the updated status line -- the
`CLOSED / PASSED` status the rejected reconciliation wrote is preserved,
not deleted, immediately above the correction, as the record of what was
wrongly claimed).

**Corrected disposition:** six of eight release dimensions (false-Visit
rate on ordinary scenes ≤15%, fragmentation ≤5%, duplicates ≤2%,
useful-evidence ≥85% combined, evidence-survival ≤15% distinct-proposal
basis, monitoring coverage ≥97%) are honestly READY FOR RELEASE BUDGET --
two of them (evidence-survival, and the false-Visit stratification) on
*stronger* footing than the rejected report established. Recall is
**RELEASE DECISION REQUIRED**: the engineering side is finished (two
independent adversarial investigations already exhausted every
currently-trustworthy signal and found no safe correction), and what
remains -- whether a whole-scene recall floor that can fall to 64.7%
during unusually busy real activity is acceptable for a v1 launch -- is an
explicit product-risk-tolerance judgment for the release authority, not an
evidence gap. True latency is **MORE EVIDENCE REQUIRED** (median
informative across four cohorts, ~83-116s; tail unconverged, four sized
maxima spanning 261.2-865.2s). **Gate A decision: OPEN -- RELEASE DECISION
REQUIRED**, with true-latency's tail distribution as a second, independent
open item that would still need to close even after the recall decision is
made.

**Smallest sufficient remaining Gate A proof, per dimension** (this
milestone's own central task, per its governing brief's explicit
instruction not to default to scheduling another 90-105-minute field
cohort): evidence-survival harmonization is **CLOSED by this correction**
via offline reanalysis of an already-preserved cohort (v14's own raw
ledger) -- no field time was needed. Latency-tail is **partially advanced
the same way** (the newly-recovered v11 sample), with the residual gap
sized to "one more ordinary-length representative session, whenever one
next runs for its own reasons" rather than a dedicated cohort -- every
other offline-reanalysis avenue for this specific gap is exhausted (v7/v8
predate valid RTT calibration; v12's own raw ledger has the same permanent
~37-minute gap that blocks its evidence-survival harmonization; v13 had
zero admissions). Recall's smallest sufficient step is an **explicit
owner/release-authority decision** on the already-sufficient (if
divergent) evidence above -- not more field data; if the release authority
instead wants a tighter numeric floor first, 2-3 more
already-otherwise-motivated representative sessions (not a
recall-dedicated cohort) would characterize how often high-density,
lower-recall sessions occur. **This closure does not authorize a field
cohort, another ambiguous-boundary investigation, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.** Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **CURRENT PHASE:
SUBSTANTIAL PRODUCT DEVELOPMENT does not change.**

**2026-09-05 update (Gate A Release-Budget & Evidence-Sufficiency
Reconciliation v1, see §6.R):** the global evidence/release-decision
reconciliation this file's own standing "NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED" authorization has been waiting for since Gate A
Measurement Closure v1 first proposed candidate budgets in 2026-08-31. See
[gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md](gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md)
for the complete evidence inventory, qualifying-cohort matrix, and
reasoning. Classification **A**. Zero production code changed; documents
only. Accepted HEAD unchanged (`de566f1`, the reconciliation commit
accepting Sustained / Crowded Ambiguous-Boundary Recall Correctness v2);
schema unchanged (`v58`).

Synthesized the complete Gate A evidence body -- fourteen real field
cohorts (2026-08-19 primary through v14), every intervening correctness
fix, and both ambiguous-boundary investigations -- into explicit,
evidence-traceable release budgets, none tuned to a specific cohort's own
result: minimum end-to-end Visit recall (excluding the ambiguous-boundary
limitation, below) ≥85%; maximum confirmed false-Visit rate ≤15%
(ordinary scenes); maximum confirmed fragmentation rate ≤5%; maximum
confirmed duplicate-Visit rate ≤2%; minimum useful-evidence rate (primary
+ supporting) ≥85%; maximum evidence-loss (`blocked_missing_evidence`, of
distinct proposals) ≤15%; median capture-to-visible latency ≤180 seconds
(no p90/maximum budget -- insufficient sized samples, and doctrine does
not require a tail-latency SLA); minimum monitoring coverage ≥97% steady
state. See `roadmap.md`'s own "Numeric release budgets" for the complete,
now-current accounting (this file's own copy above is not restated a
second time here).

**Central decision: the `blocked_ambiguous_boundary`/geometry-
compatibility-tolerance sustained/crowded recall limitation -- OPEN /
ACCEPTED PRODUCT LIMITATION CANDIDATE FOR RELEASE-BUDGET DECISION per the
immediately-prior two milestones -- is resolved as an accepted, disclosed
product limitation, not a release blocker.** Both Ambiguous-Boundary
Real-Subject Recall Correctness v1 and Sustained / Crowded Ambiguous-
Boundary Recall Correctness v2 are treated as authoritative engineering
fact (no safe correction exists using any currently-trustworthy signal);
this milestone makes the release-quality judgment those two investigations
were not chartered to make. The realized cost is always safe omission
(no Visit created), never a false merge, fabricated continuation, or
corrupted Reviewed-truth record -- the same abstention-over-fabrication
principle product doctrine already applies to species uncertainty, one
architectural layer earlier. Recall excluding this specific,
mechanistically-traced mechanism converges tightly across the two
cleanest current-stack cohorts (v12 93.3%, v14 91.7%), which is the basis
for the accepted recall budget above; the blended, undifferentiated
figures (v12 87.5%/58.3%, v14 64.7%/61.1%) remain the honest, reported
field results and are not hidden. Required user-facing/support
disclosure: MockingBird may not create a Visit for every bird during an
unusually busy, continuous stretch of activity where several birds arrive
in close succession at the same spot; it prioritizes never fabricating a
false continuation over guaranteeing one Visit per individual in that
specific circumstance -- to be named plainly in release notes/support
documentation before public launch, not silently represented as fully
solved.

Every remaining numbered Gate A dependency item (the 13-item list plus
item 14) is given an explicit disposition in the linked report -- none
silently dropped. Most are downgraded from "blocking" to **NON-BLOCKING
KNOWN LIMITATION** or **AFTER RELEASE / EVIDENCE-DRIVEN** based on
current evidence (per this milestone's own explicit authority not to keep
an item blocking merely because it was historically listed): items (4),
(12), (14) are **CLOSED**; items (1), (3), (11), (13) are **materially
advanced / non-blocking**; items (2) is **substantially advanced, not
fully closed** (two, not three, convergent person-confound-free precision
cohorts); items (5), (6), (7), (8), (9), (10) are **non-blocking known
limitations or after-release/evidence-driven**, none currently justifying
blocker status. Gate B interaction kept separate throughout: false Visits
abstain honestly in both current-stack cohorts (v12, v14); the one
already-known, already-tracked detector-sourced-background-crop residual
is unaffected and not resolved here. The 3+-simultaneous-subject/NMS
question is classified after-release/evidence-driven, non-blocking --
eight real cohorts (v7-v14) have each sought, not manufactured, this
condition and none has naturally produced it, which this milestone treats
as evidence of genuine real-world infrequency, not inadequate testing.

**Gate A decision: PASS.** Lane R moves to **CLOSED / PASSED** (see §6.R,
below, for the updated status line). This does **not** trigger a release-
phase transition: the source-code `LICENSE` owner decision and the
BirdNET commercial-adjacent legal posture both remain genuinely open,
pre-release, non-Gate-A decisions this milestone does not resolve and
cannot resolve by engineering means, and Gate G (External Pre-Release
Acceptance) has not been scoped or started. **CURRENT PHASE: SUBSTANTIAL
PRODUCT DEVELOPMENT does not change.** This closure does **not**
authorize External Pre-Release Acceptance, Final Release Hardening,
another field cohort, another ambiguity-mechanism fix, or any other next
development milestone. **Authorization remains NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, returned here exactly as this
milestone's own governing brief required, for the next external
(ChatGPT) acceptance review to act on.

**2026-09-05 update (Sustained / Crowded Ambiguous-Boundary Recall
Correctness v2, see §6.R):** bounded RELEASE-CRITICAL Gate A correctness
milestone, directly authorized outside this file, reopening the accepted,
frozen Ambiguous-Boundary Real-Subject Recall Correctness v1 investigation
because Representative Daylight Gate A Field Acceptance v14 (immediately
above) supplied new, materially richer real-field evidence about the
identical mechanism. See
[sustained-crowded-ambiguous-boundary-recall-correctness-v2-report.md](sustained-crowded-ambiguous-boundary-recall-correctness-v2-report.md)
for the complete record. Classification **B** -- zero production code
changed. Reconstructed all five v14 `blocked_ambiguous_boundary` recall
misses plus the ~310-second sustained/crowded case directly from the
preserved real-session ledger (22,260 `raw_detections`, 218 `track_
generations`, 191 `proposal_outcomes`) and confirmed, with materially
greater depth than the isolated v12 case allowed, that the dominant
mechanism is the *same* one v1 already found and declined to fix:
`classify_boundary`'s own out-of-scope geometry-compatibility tolerance
forms an ambiguous link, and `engine_runtime._live_chain_for_component`'s
deliberate, adversarially-tested "any admitted component member vetoes
the whole component unconditionally" policy then permanently blocks a
later, sometimes materially stronger, proposal -- reached either directly
(miss #4: a stronger, longer proposal blocked behind a modest anchor
admitted ~43s earlier) or transitively through several already
-permanently-resolved intermediate hops spanning hundreds of seconds
(misses #10/#13 and the ~310-second case, both tracing to the already
-admitted simultaneous-subject pair `visit-observation-candidate-010`/
`-011`). Miss #7 is a different, same-tick transitive-bridging shape with
no stale-admission complication, structurally identical in kind to the
original chartered v12 case. **One genuine, new, principled structural
fact was found and disclosed, not fixed**: the codebase already bounds how
long a still-growing ambiguous component may defer (`maximum_episode_
duration_ms`, 20 minutes, "Bounded component decision horizon") but places
no symmetric bound on how long an already-resolved member's veto reach may
persist (`engine_runtime._live_chain_for_component` takes no time/horizon
parameter at all -- confirmed directly against its own signature).
Reusing that same 20-minute constant for this different purpose would
**not** have changed any of v14's own five misses' recorded outcomes (the
real veto fired at only ~12 minutes elapsed, already under that bound),
and is not proven live-reachable in this project's own field data --
per this project's own established discipline (fix what is proven live
-reachable; do not overturn an adversarially-tested safety decision
without a new fact that resolves the question it protects), **no
production code was changed**. Three new, additive tests in `tests/
test_engine_runtime.py` reproduce the three distinct shapes (miss #4,
miss #7, the ~310s multi-hop chain) directly against the real, unmodified
`_EngineSession._run_assembly_tick`/`resolve_ambiguous_boundary_
arbitration`/`_live_chain_for_component` call path -- all pass on first
execution against the real, unmodified production code, confirming the
root-cause analysis by direct code execution, not only documentation
reading. Tier 1 (`test_engine_runtime.py`): 121 passed, 0 failed. Tier 2
(24 directly-relevant subsystem files): 461 passed, 0 failed -- an
identical count to v1's own Tier 2 run on the same file list, confirming
zero regression from this milestone's additive-only tests. Tier 3 not
run (zero production code changed). `ruff check`: 2 findings, both
confirmed pre-existing via `git stash` isolation, zero new findings. No
schema change (`v58`, unchanged). **This closure does not authorize
another admission change, another field cohort, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.** Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **The ambiguous
-boundary sustained/crowded recall limitation remains OPEN / ACCEPTED
PRODUCT LIMITATION CANDIDATE FOR RELEASE-BUDGET DECISION** -- not silently
converted into acceptance of v14's own 64.7% recall figure, which would
require an explicit global budget/release review this milestone does not
perform.

**2026-09-05 update (Representative Daylight Gate A Field Acceptance v14 --
Corrected Evidence-Path Re-Proof & Budget Convergence, see §6.R):**
RELEASE-CRITICAL Gate A field-evidence milestone, directly authorized
outside this file, following Representative Daylight Gate A Field
Acceptance v13, Camera Node Evidence-Capture Profile Validity & Failure
Observability Correctness v1, Proposal-Outcome Ledger Retention & Field
-Reconciliation Completeness v1, All-Alternate Subject Evidence Recall
Correctness v1, and Ambiguous-Boundary Real-Subject Recall Correctness v1.
See
[representative-daylight-gate-a-field-acceptance-v14-report.md](representative-daylight-gate-a-field-acceptance-v14-report.md)
for the complete record. Classification **A**. Zero production code
touched; Accepted HEAD unchanged (still the report commit for Proposal
-Outcome Ledger Retention & Field-Reconciliation Completeness v1,
`2301335`, per this file's own established "name the report commit, never
the reconciliation commit" convention).

**Session**: a fresh disposable native-Windows instance
(`MockingBirdFieldAcceptanceV14`), full accepted production stack (MDv5a
ONNX, threshold 0.1, BioCLIP-2, onnx-cuda/CUDA), 102.68 real minutes of
representative daylight monitoring against the real reference Camera Node
(a routine pairing-code refresh only -- the Node was already unpaired at
session start, so no destructive pairing-state removal was needed),
independent acceptance recorder enabled throughout (5,182 frames, 4.10GB,
99.73% coverage by this milestone's own reporting method, zero gaps >10s),
and the accepted `field_acceptance_ledger_snapshot.py` collect/reconcile
tool run detached for the full session (22 checkpoints).
**Both of the two defects this milestone was chartered to re-prove are
confirmed fixed, live, together, for the first time**: evidence-capture
profile recovery (204/204 evidence-burst requests captured, 0 failures, 1
correct self-healing reconciliation matching the root-caused mechanism
exactly) and proposal-outcome ledger completeness (`raw_detections`
22,260/22,260, `track_generations` 218/218, `proposal_outcomes` 191/191
decision-events across 90 distinct proposals -- **all three artifacts
100% `COMPLETE`, zero gaps, the cleanest ledger-completeness result of any
cohort to date**). **Headline finding #1**: 14 Visits admitted, a direct,
complete reversal of v13's zero-Visit defect-driven pathology.
**Headline finding #2, equally important**: rigorous visual cross-check
against the independent recorder (12 full-session contact sheets plus
full-resolution inspection of every admitted-Visit window, every
ledger-derived "silent" ambiguous-boundary/missing-evidence/detector
-corroboration window, and supplementary spot-checks) established a
17-encounter-period conservative denominator and **conservative recall of
only 11/17 = 64.7%** (lower than v12's 87.5%) -- **5 of the 6 confirmed
misses trace directly to `blocked_ambiguous_boundary`**, several spanning
tens to hundreds of continuous seconds of visually-unambiguous real bird
presence (one 11-overlapping-proposal cluster alone spans ~310 continuous
seconds with confirmed simultaneous 2-bird moments), the 6th to
`reject_insufficient_detector_corroboration` on a genuinely marginal,
off-feeder ground-foraging bird. This directly and substantially answers
the "does the geometry-compatibility-tolerance question recur" candidate
fact Ambiguous-Boundary Real-Subject Recall Correctness v1 left open:
**yes, materially, under real sustained/crowded activity** -- not merely
the one chartered v12 ~37:12 case (which remains **OPEN / NO SAFE
CORRECTION ESTABLISHED**, untouched, not tuned this session). One
confirmed false Visit (1/14 = 7.1%, "other background/artifact", no
species claim, zero Gate B recurrence); fragmentation 0/8 = 0.0%
(visually confirmed, not merely inferred); duplicates 0/14 = 0%; useful
evidence 78.6%/92.9% (closely matching v12's own 77.8%/94.4%); one
`dead_anchor_promoted` occurrence, evaluated on its merits for the first
time (visually confirmed real, sustained bird presence, correctly
promoted); one confirmed naturally-occurring simultaneous-subject pair,
now visually verified (two real birds in one frame), not merely
ledger-inferred; zero `classifier_same_frame`, zero scene-confusor
participation (off by default); **true latency n=14, 100% measured, by
far the richest sample of any cohort** (median 82,920.6ms, p95
253,408.4ms, max 261,211.4ms), against RTT-bounded calibration of 528
batches (527 calibrated, 99.8%). Monitoring coverage 99.73%, zero Node
disconnects, `boot_id` unchanged throughout. One isolated field-tooling
defect (this session's own uncommitted scratch orchestration -- a stray
PowerShell CRLF and an untranslated WSL path) was found and fixed within
~90 seconds, before any real session time was affected; no product
runtime file touched. Tier 1-3 correctly not run (zero production code
changed); schema unchanged (`v58`). **Gate A dependency effect**: item
(14) (evidence-capture + proposal-outcome ledger) now **fully CLOSED,
both halves**; the intact-full-session-ledger-coverage item (12) **CLOSED**;
a second independently-varied true-latency cohort item (4) **CLOSED**; the
second person-confound-free false-Visit-rate cohort item (2) **substantially
advanced, not fully closed**; the `blocked_ambiguous_boundary`/geometry
-compatibility-tolerance question moves from "candidate fact for the next
cohort" to **this cohort's own best-evidenced, most consequential open
item** -- more urgent than the pre-existing items (1), (3), (5)-(11), (13),
which remain otherwise unchanged in substance. **This closure does not
authorize a defect fix, v15, External Pre-Release Acceptance, or Final
Release Hardening, and does not select a next development milestone.**
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Classification A does not mean Gate A passes --
and it does not here: Gate A remains OPEN**, now with its most important
remaining dependency more precisely characterized than at any prior
cohort.

**2026-09-05 update (Proposal-Outcome Ledger Retention & Field
-Reconciliation Completeness v1, see §6.R):** bounded RELEASE-CRITICAL
Gate A evidence-integrity milestone, directly authorized outside this
file, following Camera Node Evidence-Capture Profile Validity & Failure
Observability Correctness v1 and Representative Daylight Gate A Field
Acceptance v13 (below). See
[proposal-outcome-ledger-retention-field-reconciliation-completeness-v1-report.md](proposal-outcome-ledger-retention-field-reconciliation-completeness-v1-report.md)
for the complete record. Classification **A**. Root-caused v13's own
disclosed 44.6% `proposal_outcome` completeness (the separate ledger
-cadence dependency v13 left open, distinct from and narrower than the
evidence-capture defect the milestone immediately below fixed): **not a
retention, query, or ledger-writer defect** -- all three independently
exonerated by direct code trace and by re-analysis of v13's own real,
locally-preserved archived checkpoint files (gitignored, not committed;
never retroactively edited) -- **entirely a field-acceptance
reconciliation defect** in `scripts/field_acceptance_ledger_snapshot.py`.
`proposal_outcomes` is an append-only decision-*event* log, not a
per-proposal state table: a retryable `blocked_continuation_pending`
proposal legitimately accumulates several independent decision events
across assembly ticks (confirmed: 64 of v13's real 156 distinct
proposals were re-decided 2-5 times each, together accounting for all
350 of that session's real decision events). The reconciler deduplicated
`proposal_outcomes` by `proposal_id` alone -- correct for `track_
generations`/`raw_detections`, wrong for this one artifact type --
silently collapsing 194 of 350 real, legitimate decision events down to
one each; direct re-analysis of v13's own real archive confirms **zero
data was ever actually lost** (the union of all 21 real periodic
checkpoints recovers exactly 350/350 real events with zero gaps). A
second, closely-related reconciliation defect in the same function was
independently discovered via this milestone's own real-runtime smoke
proof: the interval/gap check assumed every artifact type has activity
spanning close to the full session (true for `raw_detections`/`track_
generations`; never true for `proposal_outcomes`, which is naturally
silent before the first candidate encounter and after the last one) --
even after fixing the identity collapse alone, v13's own real archive
still falsely reconciled `PARTIAL` for this reason alone. **Fix, entirely
confined to field-acceptance tooling -- zero production runtime files
touched, zero schema change, zero admission/perception/truth-semantics
code changed:** (1) new `(proposal_id, decided_at)` reconciliation
identity, replacing `proposal_id` alone, shared automatically by both
`reconcile_ledger`'s completeness accounting and `build_merged_
counterfactual_window`'s merged output (which now correctly preserves
full per-proposal decision history -- exactly the shape `encounter_
accounting.cluster_encounters` was already built, and already tested, to
receive and reduce itself via its own established `_decision_offset`
-latest-wins rule); (2) a new, purely informational `recovered_distinct_
entity_count` field, never conflated into the completeness ratio; (3) a
gap-coverage refinement recognizing a payload's own `recorded_count == 0`
or (independently corroborated by a second payload) `recorded_count ==
final_recorded_count` as proof of interval coverage from session start,
guarding against a lone corrective fetch trivially "confirming" itself
(the historical Representative Daylight Gate A Field Acceptance v12
shape); (4) a new, non-fatal checkpoint-cadence safety-margin warning.
Capacity/churn analysis (v12: 325 events/96.97min; v13: 350/101.8min;
real peak 37 events/5-minute interval) shows the existing 1,000-record/
60-minute retention bounds already carry 2.9x-27x margin against every
real churn rate measured to date -- **no capacity increase was made or
warranted**. Validated via real-data `git stash` RED->GREEN bisection
against v13's own archive (proposal_outcomes: 44.57% `PARTIAL` ->
100%/`COMPLETE`; `raw_detections`/`track_generations` confirmed
byte-identical before and after -- zero regression, their own residual
`PARTIAL` status being the same, already-accepted, harmless trivial-tail
-window characteristic v13's own report already disclosed), a permanent
synthetic regression fixture built from v13's own real per-proposal
decision-count histogram, a dedicated burst-churn proof, a deliberate
bounded-eviction proof (a genuinely adversarial retention/cadence pairing
still produces an honest `PARTIAL`, never silently masked), and a real,
full end-to-end runtime smoke proof (a real server, a real Observation
Engine session with the real, unmodified `CounterfactualLedger` and
production retention config -- only the detector/Camera-Node transport
substituted for this project's own established hardware-free test
fixtures -- real HTTP, the real CLI run as a real subprocess) reconciling
`COMPLETE` with fully coherent counts. Tier 1: 34/34 (10 new). Tier 2:
290/290 across every directly-affected field-acceptance/counterfactual
-ledger/encounter-accounting/engine-runtime consumption path. Tier 3
(Core) correctly not run -- zero production runtime files touched.
`ruff check` clean. V13 remains historically **44.6%**, unchanged --
this milestone fixes future collection/reconciliation only. **This
closure does not authorize a representative field cohort, v14, External
Pre-Release Acceptance, or Final Release Hardening, and does not select a
next development milestone.** Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Gate A dependency
effect:** the separate proposal-outcome ledger-cadence/completeness
dependency (v13's own disclosed 44.6% gap) moves to **CLOSED / READY FOR
REPRESENTATIVE FIELD RE-PROOF**; the pre-existing 13-item Gate A
dependency list (unchanged in substance) and item (14)'s own recall/
evidence-survival field-re-proof half (**still REOPENED / WAITING FOR
FIELD RE-PROOF**) remain exactly as the milestone below left them.

**2026-09-04 update (Camera Node Evidence-Capture Profile Validity &
Failure Observability Correctness v1, see §6.R):** bounded RELEASE
-CRITICAL correctness milestone, directly authorized outside this file,
following Representative Daylight Gate A Field Acceptance v13 (below).
See
[camera-node-evidence-capture-profile-validity-failure-observability-correctness-v1-report.md](camera-node-evidence-capture-profile-validity-failure-observability-correctness-v1-report.md)
for the complete record. Classification **A**. Fixes v13's own disclosed,
release-critical evidence-capture defect (dependency item (14), below):
root-caused live, on the real reference Camera Node, to
`PiCamera2Provider`'s async warm-proof promotion silently retiring a
`reconfiguration_required` evidence profile id in favor of a differently
-named `warm_concurrent` one carrying an identical capture contract
(~4.2 real seconds after pairing/Node start, live-timed) --
`CameraNodeHttpTransport.request_evidence_burst` never re-validated the
persisted id against the Node's live advertised set, and collapsed every
distinct burst failure into one identical, unlogged generic code even
though the Node already reports the exact cause via `X-MockingBird-Node
-Error`. The competing timeout hypothesis (the other v13 candidate
trigger) was independently measured live and found **not supported**
(real cold `reconfiguration_required` captures: 5.66s-7.87s against a
~12s Host budget) -- the timeout was not changed. Fix:
`request_evidence_burst` now classifies failures via the Node's own
already-available header (a real, bounded taxonomy: stale/no-longer
-advertised profile, camera-busy, warm-up-timeout, session-failure, plus
a `failure_class` sub-classification for raw transport exceptions) and,
only on the specific stale-profile code, performs exactly one
deterministic live reconciliation (matching on stable semantic facts --
camera identity, "evidence" purpose, `capture_class == "warm_concurrent"`
-- failing closed on any ambiguity) plus one bounded retry -- never a
blind/generic retry loop, structurally unable to duplicate evidence.
`LiveShadowStatus`'s own burst/reconciliation counters -- confirmed
computed but never once read by `engine_runtime.py` before this
milestone -- now reach the existing `observation/status` `advanced`
payload with zero schema change. Schema `v58`, unchanged. Live-proven on
the real reference Camera Node (a user-authorized, non-destructive
pairing reset): the cold->warm promotion reproduced and timed; the pre
-fix generic failure reproduced against real hardware; post-fix, the
identical stale-id condition self-heals and captures real bytes both
through the full unmodified `ObservationEngineSessionManager`/
`_EngineSession` production pipeline (a real `EvidenceCandidate`
constructed with real Pi bytes -- the exact code path v13 proved
unreachable, now proven reachable) and directly at the transport layer
(three sequential real bursts, all succeeded); a non-recoverable failure
(wrong credential) stayed conservative and correctly classified. Nine
new tests, genuine RED proven by `git stash` bisection against the pre
-fix code, GREEN after the fix (53/53 in the affected file); one real
regression found and fixed during the same RED->GREEN pass (a test
fixture gap the new diagnostics read exposed, closed with this file's
own established "diagnostics must never break observation" discipline).
Tier 2: 686 passed / 11 xfailed across 24 Camera Node/Observation Engine
test files, one unrelated, isolation-confirmed pre-existing flake in a
disjoint transport-spool/worker test file. Tier 3 (Core) correctly not
run -- narrow, well-isolated diff, already fully covered by Tier 2. No
admission/species/truth semantics changed (confirmed against the full
freeze list: MDv5, threshold, NMS, tracker, candidate authority,
ambiguous-boundary arbitration, dead-anchor promotion, candidate quality
gate, `classifier_same_frame`, corroboration, scene-confusor, evidence
quality/ranking, Visit grouping, BioCLIP, Identification Eligibility, and
Reviewed truth are all untouched). **This closure does not authorize a
representative field cohort, v14, External Pre-Release Acceptance, or
Final Release Hardening, and does not select a next development
milestone.** Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Gate A dependency effect:**
evidence-capture profile validity/failure observability -- item (14)'s
own defect-fix half -- moves to **CLOSED / READY FOR REPRESENTATIVE
FIELD RE-PROOF**; recall and evidence-survival remain **REOPENED /
WAITING FOR FIELD RE-PROOF**, item (14)'s own remaining half -- only a
representative field cohort with this fix in place can re-measure them.
The pre-existing 13-item Gate A dependency list (unchanged in substance)
and the separate proposal-outcome ledger-cadence dependency (v13's own
disclosed 44.6% completeness, not touched or widened by this milestone)
remain exactly as v13 left them.

**2026-09-04 update (Representative Daylight Gate A Field Acceptance v13
-- Intact-Ledger Re-Proof & Budget Convergence, see §6.R):** RELEASE
-CRITICAL Gate A field-evidence milestone, directly authorized outside
this file, following Representative Daylight Gate A Field Acceptance v12,
Field Acceptance Evidence Integrity & Storage Preflight Correctness v1,
All-Alternate Subject Evidence Recall Correctness v1, and Ambiguous
-Boundary Real-Subject Recall Correctness v1. See
[representative-daylight-gate-a-field-acceptance-v13-report.md](representative-daylight-gate-a-field-acceptance-v13-report.md)
for the complete record. Classification **B** (one explicit, named,
mechanical reason: this milestone's own acceptance bar required true
latency to be sampled materially better than v12's own n=2 -- this
session measured n=0, fewer, despite the strongest RTT-calibration
-infrastructure evidence of any cohort to date, 523 batches, 99.04%
calibrated; the `proposal_outcomes` ledger artifact also reconciled to
only 44.6% decision-event completeness, a real, precisely-disclosed
gap). Zero production code touched; Accepted HEAD unchanged (still the
report commit for Ambiguous-Boundary Real-Subject Recall Correctness v1,
`eb02d51` per this file's own established "name the report commit, never
the reconciliation commit" convention -- **the top-of-§1 "Accepted HEAD"
bullet itself was found stale at `e57c911` during this milestone's own
starting-state verification, three code-changing milestones behind
(`3600e98`/storage-preflight fix, `e672c87`/all-alternate fix,
`14322b3`/dead-anchor fix, each its own report commit `146c085`/
`f819cf6`/`eb02d51` never propagated into that bullet) -- flagged here
for a future reconciliation pass to catch up properly; not corrected by
this milestone itself, which is a field-evidence session, not the
right occasion for a multi-milestone historical §1 rewrite**). Schema
v58, unchanged.

**Session**: a fresh disposable native-Windows instance
(`MockingBirdFieldAcceptanceV13`), full accepted production stack
(MDv5a ONNX, threshold 0.1, BioCLIP-2, onnx-cuda/CUDA), 101.8 real
minutes of representative daylight monitoring against the real reference
Camera Node (a new picamera2 pairing, after a user-authorized,
twice-precedented, non-destructive Node-side pairing reset), independent
acceptance recorder enabled throughout (5,013 frames, 4.48GB, zero gaps
over 5s), and the accepted `field_acceptance_ledger_snapshot.py`
collect/reconcile tool run detached for the full session (21 checkpoints,
zero ad hoc script). **Headline finding: zero Visits were admitted
against a genuinely, substantially active real session** (48
independently-reconstructed encounter clusters via the accepted
`encounter_accounting.py`, 19 conservatively confirmed real via
plausibility classification and direct visual cross-check against the
independent recorder -- including a visually-confirmed 30-second,
16-strong-detection real bird at the feeder). **Root-caused, not merely
observed**: a genuine, previously-undiscovered defect in the Observation
Engine's own automatic evidence-capture path
(`CameraNodeHttpTransport.request_evidence_burst`,
`camera_node_live.py`) -- the Host persists a Camera-Node evidence
`profile_id` at camera-setup time and never re-validates it against the
Node's live advertised profile set; every burst failure (a stale-profile
`409`, a timeout, a connection reset) collapses into one identical,
**entirely unlogged** generic failure code, with no `EvidenceCandidate`
ever created and no file ever written, so every proposal this session
died at the evidence-existence gate (`no_persistable_evidence_bytes`)
before any of the accepted precision mechanisms (ambiguous-boundary
blocking specifically, detector-corroboration, scene-confusor, same-frame
class-conflict) ever had a chance to engage -- confirmed via full code
tracing, with two concrete, code-grounded candidate triggers identified
(async Node-side profile renaming via warm-proof promotion; reconfiguration
latency at or beyond the Host's own fixed timeout under real concurrent
monitoring-stream contention). Not fixed during the cohort, per this
file's own §8/standing discipline -- core admission/evidence-path code,
explicitly off-limits during field collection. Both accepted precision
fixes were honestly field-accounted despite the shared root cause:
`classifier_same_frame` fallback, **zero occurrences**;
`dead_anchor_promoted`, **exactly one occurrence** (a 3-generation
component), itself defeated by the same evidence-capture defect before
its own merits could be evaluated. Duplicate-rate and monitoring-coverage
release-budget readiness (both `READY FOR BUDGET` since v12) are
**reaffirmed and, for monitoring coverage, strengthened** (99.99% span
coverage, max gap 3.68s -- the tightest of any cohort). Recall and
evidence-survival, by contrast, are **REOPENED BY DEFECT** -- this
session's own numbers are correctly excluded from budget-convergence
averaging for those two metrics, since they are defect-attributable, not
representative. This closure does **not** authorize a defect fix, v14,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
**Remaining Gate A dependency, in priority order, restating the prior
13-item list (unchanged in substance, see the Ambiguous-Boundary
Real-Subject Recall Correctness v1 entry below) plus one new, more urgent
item**: **(14) [NEW, RELEASE-CRITICAL] fix the Observation Engine's
automatic evidence-capture profile-staleness/silent-failure defect
identified above, then field-re-prove recall against a representative
cohort with the fix in place** -- more urgent than items (1)-(13), since
no future field cohort's own recall/evidence-survival measurement can be
trusted at face value until this is closed.

**2026-09-04 update (Ambiguous-Boundary Real-Subject Recall Correctness
v1, see §6.R):** bounded RELEASE-CRITICAL Gate A product-correctness
milestone, directly authorized outside this file, following All-Alternate
Subject Evidence Recall Correctness v1's own disclosed-not-fixed finding
that the v12 ~37:12 real bird was permanently blocked by candidate
-authority ambiguous-boundary arbitration. See
[ambiguous-boundary-real-subject-recall-correctness-v1-report.md](ambiguous-boundary-real-subject-recall-correctness-v1-report.md)
for the complete record. Classification **B**. **The chartered ~37:12
case (`visit-episode:06c209aec98c56ebcc7d9d47`) was reconstructed with
high fidelity -- including one decisive, code-grounded fact established
for the first time: the real 187ms gap between its own `blocked_
ambiguous_boundary` decision and its winning sibling's (`visit
-observation-candidate-017`) `created` decision is two orders of magnitude
below the proven 10-second minimum spacing between separate assembly
ticks (`engine_runtime._ASSEMBLY_TICK_SECONDS = 10.0`), proving both were
decided together, ordinarily, in one single tick -- the existing,
unmodified fallback-chain mechanism working exactly as designed, not a
dispatch defect. Its own true root cause is confirmed to be the *already
-disclosed*, explicitly out-of-scope geometry-compatibility-tolerance
finding that milestone raised (`classify_boundary`'s 0.6-normalized
-centroid-distance cap): no safe, in-scope fix exists using only currently
-trustworthy facts (Classification I, per that taxonomy, subsumed under
this milestone's own overall B). No fix was attempted or claimed for this
specific case -- it remains exactly as open as before this milestone,
neither better nor worse.** **The same investigation independently
surfaced, and safely fixed, a genuinely separate, real, in-scope defect in
the identical mechanism**, confirmed live-reachable in this exact same
real v12 session (that session's own very next `blocked_ambiguous_
boundary` loss, ~11 seconds later, on a genuinely separate later tick):
`engine_runtime._run_assembly_tick`'s winner-loop assumed an ambiguous
component's own arbitration-selected winner is always attemptable this
tick; because arbitration is recomputed fresh every tick from the
assembler's *entire* tracklet history, a component's own top-ranked member
can itself already be permanently resolved on a *strictly earlier* tick,
silently starving every later, brand-new arrival within its reach --
including when that stale member was never itself admitted at all (zero
Visits ever produced). Fixed narrowly, entirely inside `engine_runtime.py`
(`_live_chain_for_component`, a new pure helper, plus a same-shaped
`admitted_proposal_ids` session-local record mirroring `attempted
_proposal_ids`): no change to `candidate_visit_authority.resolve_
ambiguous_boundary_arbitration`'s own ranking, no new time-based staleness
constant, no threshold of any kind -- "at most one Visit per ambiguous
cluster" is checked, and preserved, unconditionally before any promotion
is ever attempted (proven directly by a dedicated adversarial regression
test: a later arrival with dramatically higher confidence than an
already-admitted anchor still correctly blocks). No schema change (v58,
unchanged); no candidate-authority ranking, geometry, threshold, detector,
tracker, BioCLIP, or Identification Eligibility/Abstention change. Real
-hardware smoke judged unnecessary and not run (reachability verified;
reasoning matches the immediately-prior milestone's own judgment for an
analogously narrow, non-timing-sensitive diff -- see the report's own
"Real-hardware smoke"). Tier 1 (6 new tests, `tests/test_engine_runtime.py`
118/118) and Tier 2 (461/461 across every directly-affected observation/
admission/precision/dashboard/multi-camera subsystem, 579/579 combined
with Tier 1) both clean. Tier 3 (full Core): 5679 passed / **1 failed** /
3 skipped / 23 deselected (`slow`-marked) / 11 xfailed, 236 warnings
(1991.73s/33m11s) -- the 1 failure
(`tests/test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields`, a genuinely new, previously
-uncatalogued-by-name instance, not the already-documented `test_place_
biodiversity_summary_repository.py` pair) independently re-confirmed
pre-existing and unrelated via `git stash` bisection to the clean
starting HEAD, byte-identical failure, zero of this milestone's changes
applied -- see §14, below, and the report's own "Tier 3 decision" for the
complete account. **Gate A effect:** the v12 ~37:12 ambiguous-boundary recall defect remains
**OPEN, unchanged** (root-caused, not fixed, not worsened); the separately
-discovered dead-anchor-promotion defect is **CLOSED / READY FOR FIELD
RE-PROOF**. Gate A's own pre-existing 13-item dependency list (items
(1)-(13), as narrowed by the two immediately-prior milestones) is
**unchanged** -- neither closed nor reopened by this milestone; the
dead-anchor-promotion mechanism's own real-world field frequency and
precision-safety under sustained real activity are added as a candidate
fact for the next representative cohort to independently confirm, not as
a new numbered item. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, a fix for the v12
~37:12 case's own still-open geometry-tolerance question, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone. Authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.

**2026-09-04 update (All-Alternate Subject Evidence Recall Correctness v1,
see §6.R):** bounded RELEASE-CRITICAL Gate A product-correctness milestone,
directly authorized outside this file, following Representative Daylight
Gate A Field Acceptance v12's own two confirmed-real-bird `reject_no_
identification_or_context` misses. See
[all-alternate-subject-evidence-recall-correctness-v1-report.md](all-alternate-subject-evidence-recall-correctness-v1-report.md)
for the complete record. Classification **A**. **Material correction to
v12's own diagnosis, established by direct ledger-to-code cross-reference
against the recovered raw ledger**: neither of v12's two named misses
(37:12, 57:07) actually terminates at `reject_no_identification_or_
context` -- the 37:12 bird was permanently blocked by candidate-authority
ambiguous-boundary arbitration (never reached the evidence-quality gate at
all); the 57:07 bird passed the identification/context check and was
correctly rejected by the separate, already-hardened detector-
corroboration gate on a genuinely marginal (3-detection, never-strong)
real encounter. **The milestone's own chartered failure pattern was
nonetheless proven real and fixed**, by complete case-exhaustion over
`evidence_scoring.score_proposal_evidence`'s own logic (not sampling): a
proposal whose *only* surviving, byte-backed evidence is its own
`classifier_same_frame` snapshot (Same-Frame Species Evidence v1's
diagnostic/classifier-input asset, deliberately excluded from
identification/context ranking so it can never outrank a real burst) was
being discarded outright because that exclusion from ranking was misread,
one gate downstream, as "no viable evidence" -- despite the same-frame
asset being a real, tracker/detector-confirmed, geometry-proven subject
capture. Directly confirms and resolves a suspicion Harvested Evidence
Issuance / Missing-Evidence Closure v1 (2026-08-20) explicitly raised and
left unpursued ("the same accidental 'other evidence happens to survive'
shape may be part of why the real field session's own ... cases ... were
never conclusively ruled out as related"). Fixed narrowly:
`candidate_quality_gate.evaluate_evidence_admission` gains one last-resort
fallback to a `classifier_same_frame` item, only when neither
`identification` nor `context` exists, subject to the same geometry-
validity/detector-corroboration checks unchanged (never a bypass);
`product_repository.py`'s two presentation-layer same-frame exclusions
each gain a matching conditional carve-out so a same-frame-only admitted
Visit actually shows its one photo rather than an empty gallery.
`alternate` deliberately given no equivalent fallback (proven live
-unreachable alone in the current scorer). No schema change (v58,
unchanged); no detector/tracker/BioCLIP/threshold change; no candidate
-authority or ambiguous-boundary change. RED->GREEN confirmed via `git
stash` at both the pure-gate and real-repository-transaction levels, using
this exact session's own real detection signatures for both the positive
control (a real 8-detection/0.479-confidence encounter) and the negative/
precision control (the session's own real persistent red-flag confusor's
weakest signature, 1 detection/0.121 confidence). Tier 1 (8 new tests) and
Tier 2 (518 tests across every directly-affected observation/admission/
evidence subsystem, including every required historical false-positive
-control regression suite) both clean. Tier 3 (full Core): 5672 passed / 2
failed / 3 skipped / 23 deselected / 11 xfailed -- the 2 failures
(`test_place_biodiversity_summary_repository.py`'s own extensively
pre-documented, real-wall-clock-dependent pair -- see §14) independently
re-confirmed pre-existing and unrelated via `git stash` bisection to the
clean starting HEAD, byte-identical failure, zero of this milestone's
changes applied. **One genuinely new, real, precisely-root-caused finding
disclosed, not fixed** (explicitly out of this milestone's own scope, per
its own brief's "do not touch candidate authority/ambiguity threshold"):
the 37:12 bird's own real cause -- ambiguous-boundary arbitration's
geometry-compatibility tolerance, capped at a large 0.6 normalized
centroid distance for any gap >= ~9.6 seconds, may not meaningfully
discriminate between a real, spatially-distinct subject and an unrelated
persistent confusor/prior encounter within the same 45-second ambiguity
window. **Gate A dependency item (13), narrowed**: the specific same-frame
-only evidence-exclusion defect this item's own "all-or-nothing vanish"
concern was partly about is now closed/fixed and proven; the item's own
broader question (does this terminal reason ever discard a real encounter,
in any other shape) is answered as completely as the current architecture
allows by this milestone's own case-exhaustion proof, but full field
re-confirmation still awaits the next representative cohort (item 12,
unchanged). This closure does **not** authorize the next Representative
Field Acceptance / Gate A session, a fix for the newly-disclosed
ambiguous-boundary finding, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged.

**2026-09-04 update (Field Acceptance Evidence Integrity & Storage
Preflight Correctness v1, see §6.R):** bounded RELEASE-CRITICAL
acceptance-tooling correctness milestone, directly authorized outside
this file, following Representative Daylight Gate A Field Acceptance
v12's own two disclosed field-tooling defects. See
[field-acceptance-evidence-integrity-storage-preflight-correctness-v1-report.md](field-acceptance-evidence-integrity-storage-preflight-correctness-v1-report.md)
for the complete record. Classification **A**. **Snapshot-evidence
defect (v12's own `end_offset_ms=None` silently dropped, breaking raw
-ledger capture for all 12 periodic snapshots) fixed and proven**:
`FieldAcceptanceClient.observation_counterfactual` now fails locally,
before any HTTP request, on a missing required bound
(`FieldAcceptanceInvalidParameterError`); a new, committed periodic
-snapshot + reconciliation tool
(`scripts/field_acceptance_ledger_snapshot.py`) replaces the ad hoc,
uncommitted script every real cohort since v9 wrote from scratch --
each checkpoint carries explicit per-artifact success/failure (a failed
required raw-ledger fetch is never silently `complete`), and end-of-run
reconciliation deterministically reports `COMPLETE` or `PARTIAL` with
the exact missing count/offset-window, never inferred from a clean
session end. **Storage-preflight defect (a malformed Windows-style
`--dev-root` under WSL/POSIX silently measuring the WSL virtual disk
instead of the real Windows drive) fixed and proven** -- at both the
secondary `field_acceptance_instance_lifecycle.py preflight` tool v12
directly hit *and* the primary `deploy_windows_dev.py` deploy entry
point every real field session actually runs first (an identical,
independently-discovered instance of the same defect, only found via
this milestone's own self-review, not named in v12's own report): a
Windows-drive-letter/UNC path is translated via the real, already
-accepted `wslpath -u` primitive or refused outright, never silently
CWD-anchored; `StoragePreflightReport` now exposes requested/resolved
/probed-path provenance plus filesystem device identity. **Real proof,
not merely reasoned about**: a real WSL-to-Windows storage proof against
the reference development Windows host (independently-queried free
-space figures agree within normal measurement drift; the previously
-dangerous Windows-drive-string form now measures the identical real
device id as the direct-mounted-path form; a genuinely unmounted drive
letter fails closed) and a real snapshot smoke proof (a fresh disposable
instance, the real reference Camera Node re-paired to it after a
confirmed-safe, precedented, user-approved local pairing-state reset; a
real ~4.4-minute GPU-backed Observation session, 5 real periodic
checkpoints plus one final corrective fetch, reconciled -- correctly
distinguishing a genuine zero, `track_generations`/`proposal_outcomes`
both `COMPLETE`, from one real, exact, sub-second interval-coverage gap
named to the millisecond in `raw_detections` despite a perfect 220/220
record-count match, proving the tool never rubber-stamps completeness
from a count match alone). Two critical defects in this milestone's own
first implementation pass (a `main()` CLI path that silently defeated
the storage fix; a reconciler that misreported a genuinely healthy
zero-activity artifact type as `PARTIAL`) were caught and fixed by
multi-agent self-review before any real proof was attempted -- see the
report's own "Self-review findings and fixes." Tier 1 (33/33 + 185/185)
and Tier 2 (321/321) green; lint clean; zero `src/mockingbird/**` diff,
zero schema change (`v58`, unchanged), zero wildlife/product admission
behavior changed anywhere in this milestone -- confirmed directly,
including that `candidate_quality_gate.py`'s
`reject_no_identification_or_context` (the separate, preserved v12
product finding) remains byte-for-byte untouched. **v12's own historical
evidence-preservation gap is not retroactively upgraded** -- its raw
ledger remains honestly partial, exactly as disclosed; this milestone
repairs future collection, it does not manufacture v12's own missing
data. **Gate A dependency list, narrowed precisely**: the *tooling
-broken* rationale for item (12) (a cohort with intact full-session
ledger coverage, needed specifically because v12's own snapshot tooling
could not be trusted) is closed -- the tool is now fixed and proven. The
underlying, independent requirement is **not** removed: Gate A still
needs an actual representative cohort whose raw ledger this now-fixed
tooling genuinely captures completely end to end; fixing the tool does
not retroactively create that evidence. Item (13)
(`reject_no_identification_or_context`'s all-or-nothing behavior for
brief-but-real encounters) is preserved verbatim, untouched, still open
-- this milestone's own governing brief explicitly scoped it out. This
closure does **not** authorize the all-alternate-evidence product fix,
another Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone. Authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.

**2026-09-03 update (Representative Daylight Gate A Field Acceptance v12
-- Precision, Recall & Budget-Convergence Tranche, see §1/§6.R):** the
next real-field Lane R / Gate A cohort, directly authorized outside this
file as the milestone following global reconciliation. See
[representative-daylight-gate-a-field-acceptance-v12-report.md](representative-daylight-gate-a-field-acceptance-v12-report.md)
for the complete record. Classification **A**. 96.97-minute real daylight
session against the accepted configuration (HEAD `fa9c8f0` unchanged,
schema v58, MDv5a `score_threshold 0.1`, real RTT-bounded calibration
`calibrated`, real Node build `4c1be35`). **Best-ever single-session
precision**: 1/18 = 5.6% confirmed false Visits (v8 22.2%, v9 20.0%, v10
36.4%, v11 44.4%) -- and, for the first time, **person-confound-free**
(no dual-class person-associated activity occurred at all), directly
answering dependency item #2's own requirement for an unconfounded
cohort. Recall 14/16 = 87.5% conservative (14/24 = 58.3% broader lower
bound), fragmentation 0/14 = 0% (own manual method, tool data-starved --
see below), duplicates 0% (9th consecutive cohort), useful evidence
77.8% raw / 94.4% including alternate frames, zero Gate B recurrence,
zero natural Node disconnect. **Two genuinely new findings, both
precisely root-caused, neither fixed during the cohort (§8/§32):** (1) a
brand-new persistent non-animal confusor -- a small red property/utility
marking flag -- directly confirmed by pixel inspection, driving ~70% of
this session's track-generation volume yet producing zero registered
scene-confusor rows (the first real-field example of category D, "never
eligible to reach scene-confusor," since its tracks terminate at the
tracking layer itself); it produced zero false Visits. (2) A real,
visually-confirmed recall gap: `reject_no_identification_or_context`
(`candidate_quality_gate.py`) discards a proposal outright -- no Visit
at all, not even an abstained one -- whenever no captured evidence item
ever reaches role `identification`/`context`; two brief, clearly-visible
real birds were independently confirmed by full-resolution frame
inspection to have received no Visit this way. **Disclosed field-tooling
defect (this session's own snapshot script, not product code):** the
10-minute periodic-ledger-snapshot loop's `end_offset_ms=None` was
silently dropped against a server-required parameter, breaking raw
ledger capture for all 12 snapshots; a single post-stop corrective fetch
recovered a partial tail (52.95%/39.40%/53.85% completeness by record
type, zero coverage for the session's own first ~37-46 minutes) --
quantified precisely, not inferred, per the governing brief's own
instruction. Visit-level detail and evidence (100% of 18 Visits / 36
images) and the independent acceptance-recorder (4,833 frames, zero
gaps over 10s) are unaffected. Budget-readiness: duplicate rate and
monitoring coverage now **READY FOR BUDGET** (duplicates: 9 consecutive
0% cohorts; coverage: 5 cohorts in the 97.5-99.99%+ band); every other
Gate A metric remains **MORE EVIDENCE REQUIRED**, named precisely in the
report's own budget-convergence section. **Gate A status: unchanged,
`NOT DONE -- RELEASE-CRITICAL`** -- per this milestone's own governing
brief, Classification A here reflects excellent, valid field evidence,
not Gate A closure. The pre-existing 11-item dependency list is
carried forward (items #2, #3, #11 meaningfully advanced but not
closed; items #1, #4-10 unmet or only trivially satisfied), **extended
by two new items**: (12) a cohort with intact full-session ledger
coverage, to properly cross-validate this session's own partially-
unverifiable figures; (13) whether `reject_no_identification_or_
context`'s all-or-nothing behavior for brief-but-real encounters should
be revisited. Field instance archived (`SAFE_TO_RECLAIM`, ~8.8GB, not
destroyed by default); real defects/discoveries preserved as evidence
under `data/field-acceptance/2026-09-03-gate-a-v12-precision-recall-
budget-convergence/`. Zero production code changed; no Tier 3 run (§33).
Does **not** authorize the next Gate A cohort, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. This file's own bold "NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED" statement, directly above, is
unchanged.

**2026-09-03 update (Authenticated Camera Node Golden-Path Capture &
Preview Acceptance v1, see §1):** Lane G hardware-validation milestone
(directly authorized outside this file), release-critical -- proves the
one concrete gap Camera / Source Release Hardware Validation Closure v1
left open: authenticated Camera Node capture/preview end to end on the
accepted build. See
[authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md](authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md)
for the complete record. Classification **A**. **Pairing-state mystery
resolved:** the Node's orphaned credential (unknown to every prior
session) traced to an archived, dormant `MockingBirdFieldAcceptanceV11`
by SHA-256 digest comparison and safely revoked through the real
authenticated `CameraNodeClient.revoke()` path. **Accepted-build
deployment:** `ca98fc6`'s `V4L2CameraProvider` fix, never live-deployed in
its own milestone, deployed to the reference Pi -- which immediately
exposed a second, real diagnostic-truth gap in the same class
(`isOpened()` alone insufficient; a `bcm2835-isp` pipeline-stage node can
accept `open()` while never delivering a frame). Fixed together with the
timing consequence its own real-hardware cost exposed in self-test's
fixed timeout (implementation `4c1be35`, RED->GREEN, Tier 1+2 clean, Tier
3 correctly not run). **Golden-path proof:** real authenticated Node
images captured and decoded (1920x1080, real scene, three independent
captures); real Add Camera pairing/preview/complete via a genuinely fresh
disposable Host instance; real Chromium/Playwright proof against the real
built frontend (full pass, screenshots); preview non-persistence verified
directly against the database; bounded interruption/recovery exercised
against the configured Stream; credential safety verified against the
real secret value; strict `field_acceptance` compatibility passed with a
real RTT calibration. One disclosed, non-blocking finding (a
self-resolving post-pairing timing race) -- not fixed, correctly judged
non-release-critical. **Lane G status, updated (see §6, below):**
`MATERIALLY CLOSED / VALIDATION REMAINS` -> `CLOSED -- RELEASE-CRITICAL`.
Final Node state: healthy, upgraded, genuinely unpaired. Does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. This file's own bold "NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED" statement, directly
above, is unchanged.

**2026-09-03 update (Ecosystem / Provider Integrations Release-Scope
Decision v1, see §1):** pre-release product-scope decision for Lane K,
directly authorized outside this file as global product-roadmap
reconciliation -- documentation/reconciliation only, zero production code
changed. See
[ecosystem-provider-integrations-release-scope-decision-v1-report.md](ecosystem-provider-integrations-release-scope-decision-v1-report.md)
for the complete record. Classification **A**. Confirms MockingBird
already has reasonable non-proprietary launch acquisition options across
every category traced (Camera Node, ONVIF, RTSP/RTSPS, local USB/platform
camera, offline/recorded ingest, camera-trap ingest, plus a
general-purpose vendor-neutral webhook ingress any of the four candidate
ecosystems could already use without a dedicated adapter) and closes Lane
K's `OPEN DECISION` to `DECISION CLOSED -- DEDICATED PROVIDER
INTEGRATIONS DEFERRED PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH` (§6,
below) with concrete reopening criteria and a locked architecture
contract for any future adapter (must terminate into the existing
Source/Stream/Visit/Evidence/Review Decision/Observation spine; no
parallel truth, no second camera database, no cloud-required operation,
no surveillance-specific mode, no separate analytics truth). Removes zero
launch blockers: Lane K was already category B (pre-release decision),
never release-critical, so no release-shape recategorization was needed,
mirroring how Lane O and Lane P's own resolutions were each closed in
place. Does **not** authorize a provider implementation, Lane R, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone. This file's own bold "NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED" statement, directly
above, is unchanged.

**2026-09-02 update (Camera / Source Release Hardware Validation Closure
v1, see §1):** Lane G hardware-validation milestone (directly authorized
outside this file), release-critical, validation-only -- no new provider
integrations, no wildlife-denominator field cohort. See
[camera-source-release-hardware-validation-closure-v1-report.md](camera-source-release-hardware-validation-closure-v1-report.md)
for the complete record. Classification **B**. **Scheduler headline
reconciliation:** determined the brief's suspected staleness (§1's
"Accepted HEAD" naming the report commit rather than the reconciliation
commit that records it) is this document's own established, consistent
convention across at least two full verified cycles, not a defect --
verified, not corrected. **Camera Node golden path:** real, live evidence
against the reachable reference Pi (`node-76ec8e53ae586dd0`) -- health,
both compatibility-preflight profiles (`ordinary_monitoring` and
`field_acceptance`, the latter including a real 5/5-valid bounded RTT
clock-calibration batch), an honest `409 pairing_code_used` rejection on a
live pairing-conflict probe, and a clean bounded
`systemctl restart`/recovery cycle (`node_id`/`boot_id`/pairing on-disk
state all correctly preserved across the restart) -- the first session on
record to reach this depth against a genuinely reachable reference Node.
Live authenticated preview/snapshot was **not** exercised: the only
locally-known pairing credential is stale/revoked, the Node's pairing
model is single-credential, and this milestone deliberately did not force
a fresh pairing against a shared reference device merely to obtain one.
**v11 diagnostic-truth defect:** reproduced deterministically, live,
against this exact Node's own real device topology, and fixed --
`V4L2CameraProvider.cameras()` was unconditionally marking every
enumerated `/dev/videoN` device "available" from path existence alone, so
this Pi's own internal ISP/codec/HEVC-decoder pipeline device nodes (none
of which open via this Node's own installed OpenCV, confirmed live) could
keep self-test's aggregate `camera_available` true even when the real
camera, correctly reported absent by `picamera2`, was actually gone --
exactly v11's own recorded field shape. Fixed in `mockingbird_node.
providers` (bounded, per-path-cached, reuses `snapshot()`'s own existing
openability ground truth); not deployed to the live reference Pi, proven
instead via tests grounded in its own real device topology. Self-test's
separate, disclosed, deliberately-not-fixed once-at-startup/cached-
forever staleness characteristic remains -- not load-bearing for any
safety decision today (the Host compatibility preflight never reads
`self_test.camera_available`). RED->GREEN via 4 tests; 731 passed, 0
failed across the full affected subsystem sweep (11 pre-existing xfails,
unrelated); 0 new `ruff` findings; Tier 3 (full Core) deliberately not
run -- `mockingbird_node` has zero import-time coupling into the Host's
`mockingbird` package (an already-documented architectural invariant,
directly confirmed this session), so the blast radius is provably bounded
to Tier 2. **RTSP/local-USB/ONVIF:** confirmed unavailable tonight (live
port-554 probe, empty `/dev/video*`/`lsusb`), not fabricated -- unchanged
from every prior camera-source milestone's own disclosed gap. **Windows
DirectShow:** a known USB webcam (`EMEET SmartCam S600`) is registered on
the reference Windows host but not currently connected; real live
DirectShow enumeration returned zero video devices, correctly parsed as
empty by the real product function against this exact captured output --
enumeration-honesty proof only, no live capture. **Multi-source
coexistence:** not exercisable -- only one source (Camera Node) was
genuinely live tonight. **Lane G status, updated (see §6, below):** stays
MATERIALLY CLOSED / VALIDATION REMAINS -- RELEASE-CRITICAL. Real,
meaningful progress (the Camera Node golden path's health/compatibility/
recovery layer is now proven for the first time, and one real,
previously-only-anecdotally-known diagnostic defect is fixed with full
regression coverage), but Lane G's own specifically-named remaining gap --
proving live authenticated video decode/preview end-to-end for any real
camera -- is **still open** for every path, including the one path that
was genuinely reachable tonight, for disclosed credential/hardware-
availability reasons rather than a rediscovered code defect. **Concrete
remaining release-critical dependency:** obtain or mint a usable pairing
credential for the reference Camera Node and prove live authenticated
video capture/preview against it end to end; RTSP/local-USB/Windows-
DShow/ONVIF live hardware acceptance remains a hardware-availability gap,
not a release-blocking defect, exactly as open as every prior session
already left it. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone.

**2026-09-02 update (Strong-Confidence Subject-Evidence Viability &
Scene-Artifact Abstention v1, see §1):** a direct, investigation-only
follow-up to the immediately-prior milestone's own disclosed residual --
the exact v11 Visit-018 strong-confidence leaf/branch scene-artifact shape
at "Location A," proven, numerically, not closed by that milestone's own
scene-confusor bookkeeping fix. See
[strong-confidence-subject-evidence-viability-scene-artifact-abstention-v1-report.md](strong-confidence-subject-evidence-viability-scene-artifact-abstention-v1-report.md)
for the complete record. Classification **B**. **Investigated every
avenue the governing brief named -- detector geometry lineage, crop
containment/occupancy/consistency/stability, evidence diversity/temporal
spacing, independent detector reacquisition, track-generation structure,
evidence scoring, scene-confusor state -- and found no safe, non-ML,
non-confidence-magnitude, non-motion, non-spatial-blacklist fact that
separates a strong scene artifact from a strong real (including
stationary and brief) bird. Per the brief's own explicit instruction, no
rule was invented to force a result: zero production code changed.**
Two new findings, both proven directly against real production code
paths (`ProviderNeutralFrameTracker`, `build_tracklets`/`assemble_visit_
episodes`, `localization_attribution.geometry_attribution_for_update`/
`classify_localization_attribution`) in a new, additive test file
(`tests/test_strong_confidence_subject_evidence_viability_v1.py`, 2/2
passing), not asserted from reading source alone: **(1) structural-shape
identity** -- the exact artifact shape (one track generation,
`strong_detection_count=6`) and the accepted "strong real bird" positive
control (one track generation, `strong_detection_count=3`) are
structurally identical at every fact `candidate_quality_gate`/
`scene_confusor` can read; the real bird's own detection count is
*lower* than the artifact's, so no count/generation threshold, for any
constant, separates them without also catching the real bird first --
this is a disguised confidence/count retune, which the brief explicitly
forbids. **(2) geometry-grounding non-separation** -- directly answers
the brief's own §11 (whether Background / Empty Evidence Species-
Confidence Correctness v1's own "credible contemporaneous detector
grounding" fact, `geometry_source`, generalizes to Visit admission):
both the artifact and the real-bird control classify identically as
`geometry_source="detector"` / `classify_localization_attribution(...)
.attribution == "detector_off_target"`, because the artifact's own six
detections are completely genuine, contemporaneous MDv5 agreement, not
stale/tracker-extrapolated geometry -- the different, narrower defect
class that signal already, correctly, closes elsewhere. `localization_
attribution.classify_localization_attribution`'s own docstring already
names this exact limit verbatim ("the raw detector output on that exact
frame is the most defensible attribution available from lineage alone").
Also investigated and explicitly rejected as unsafe, not merely
unexamined: intra-generation box/geometry variance (a disguised
motion/stillness requirement, forbidden by the brief); encounter
duration/detection temporal density (would risk the mandatory brief-
real-bird positive control); evidence-candidate diversity (the brief's
own text preemptively names this insufficient by itself, since a real
stationary bird legitimately produces the same shape); evidence
photographic quality (re-confirmed, not re-derived, from the immediately-
prior milestone's own real-crop trace -- none of `evidence_scoring.py`'s
components are content/semantic signals). `scene_confusor.py` and
`candidate_quality_gate.py` remain completely unmodified: both of
scene-confusor's own confidence escapes (steps 5/6, `stronger_confidence_
than_region_history`/`independently_strong_detection`) are reconfirmed
directly, by reading the current source in full, to be unconditional on
region history by original design and simultaneously required for the
real, field-proven feeder-pole stationary-real-bird control (`occurrence_
count=4`, `max_confidence_observed=0.827`, escaping via step 6 every
time, spanning both v11 field segments) -- weakening either without a
new, independent, safe fact (none found this milestone) would risk that
control directly. Zero MDv5/NMS/BioCLIP/eligibility threshold changed;
zero new coordinate literal in production code; no whole-frame human
veto; no spatial blacklist; no motion requirement; no BioCLIP validity
gate; schema unchanged (`v58`). Directly-relevant existing regression
suite re-run unchanged (`tests/test_strong_confidence_non_target_scene_
artifact_v1.py`, `tests/test_independent_corroboration_value_persistent_
confusor_v1.py`, `tests/test_hard_negative_visit_admission_precision_v1.
py`, `tests/test_localization_attribution.py`, `tests/test_observation_
evidence_scoring.py`, plus the new file: 107 passed, 0 failed); 0 new
`ruff` findings. Tier 3 (full Core) deliberately not run, matching the
brief's own explicit instruction not to run it for ceremony when a
milestone concludes investigation-only with no production change --
documented, not omitted. **Strong-confidence-artifact defect state,
updated:** still open, unchanged in observable product behavior (Visit
018's own exact shape still admits), but now backed by two new,
code-proven negative results narrowing what a future closure attempt
would need (a genuinely new evidence-quality/content signal, or real
field data this sandbox cannot responsibly produce) rather than an
unexamined residual. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A
dependency:** unchanged and unmet by this milestone (no field session
was run, per this milestone's own explicit instruction, and no
production admission behavior changed) -- the v11 entry's own priority
list and the immediately-prior milestone's own extension items (8-11,
below) remain exactly as they were; this milestone adds no new field-proof
item beyond what its own "Next field proof" section (in the linked
report) already names as separately out of scope. **Separately reproduced
diagnostic/tooling defects (v11, carried forward, not this milestone's
scope):** Camera Node `/node/v1/health` self-test can report
`camera_available: true` while the specifically-configured camera remains
physically undetected (real, disclosed, not release-blocking -- the
actual safety-relevant compatibility-preflight gate already catches it
correctly); acceptance-recorder directory-path encoding defect for an
absolute Windows `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` (data-intact,
tooling-only). Neither investigated or fixed this milestone; no
dependency found between either and this milestone's own subject-
evidence-viability investigation.

**2026-09-02 update (Strong-Confidence Non-Target & Scene-Artifact Visit
Admission Correctness v1, see §1):** reopened by Representative Daylight
Gate A Field Acceptance v11's own real field evidence -- 8/18
confirmed-false Visits (44.4%), all admitted via the strong-detection
bypass (`candidate_quality_gate._insufficient_detector_corroboration`'s
own `strong_detection_count > 0` escape), a mechanism no prior milestone
had directly examined -- at classification **B**. See
[strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md](strong-confidence-non-target-scene-artifact-visit-admission-correctness-v1-report.md)
for the complete record. Two genuinely distinct false subclasses (7 a
real person-in-frame confound, 1 the "Location A" strong-confidence
leaf/branch scene artifact) were separated and deterministically
reproduced against the real, unmodified production admission path.
**Person subclass:** traced to a real, architecturally-confirmed MDv5
decode fact (per-candidate-argmax-before-NMS, then per-class NMS -- a
single real object can legitimately decode as two different-class boxes
on one frame) -- `frame_tracker.observe()` now excludes an animal-class
detection from ever corroborating a wildlife track when it substantially
(IoU >= 0.3, reusing `scene_confusor.GEOMETRY_IOU_THRESHOLD`'s own bar)
coincides, same frame, with an explicitly non-animal (`person`/
`vehicle`) detection -- partially closed: the co-occurring-contradiction
shape is now measurably prevented (`git stash`-verified RED->GREEN); the
pure single-class-misclassification shape (no co-occurring contradiction
anywhere) remains exactly the already-accepted 2026-08-20
Person-Background-False-Positive residual, unchanged. **Artifact
subclass:** found and fixed a real, confirmed defect in `product_
repository._create_candidate_visit_locked` -- `_touch_scene_confusor_
region` was reachable only once the quality gate already said `admit`,
so a recurring, always-weak hard-negative location (Location A) left
zero scene-confusor history no matter how many times it recurred within
a session, and the one time it finally cleared `strong_detection_
threshold` outright it was evaluated against a blank history. Now fixed
(bookkeeping runs for a `reject_insufficient_detector_corroboration`
outcome too, never changing that outcome itself) and directly proven,
via `git stash`, to newly catch a recurring never-strong confusor that
eventually clears the corroboration *count* axis. **Directly proven,
numerically, not to close v11's own headline Visit 018 shape itself:**
`evaluate_scene_confusor_suspicion`'s own steps 5 (materially-stronger-
than-history) and 6 (independently-strong, unconditional) are both
checked without reference to occurrence history once triggered, by
original design, and both are load-bearing for the real, field-proven
feeder-pole stationary-real-bird control -- so `scene_confusor.py` itself
is left completely unmodified rather than risk that control on an
unverified assumption; this residual is reported honestly, not
concealed. Zero MDv5/NMS/BioCLIP/eligibility threshold changed; zero
coordinate literal read by either fix; no whole-frame human veto; no
spatial blacklist; schema unchanged (`v58`). Every required positive
control preserved (strong/weak/stationary real bird, bird+person
spatially separate, multi-subject isolation, all prior hard-negative/
corroboration/scene-confusor mechanisms, Reviewed truth, species
non-escalation). **Validation:** Tier 1 (new 11-test reproducer suite,
`tests/test_strong_confidence_non_target_scene_artifact_v1.py`) 11/11;
Tier 2 (28 directly-affected-subsystem files) 705 passed / 0 failed;
Tier 3 (one full Core run) 5610 passed / 2 failed / 3 skipped / 23
deselected / 11 xfailed (1928.46s) -- the 2 failures independently
reconfirmed pre-existing and unrelated via fresh `git stash` isolation
against this session's own starting HEAD (the same already-repeatedly-
documented `test_place_biodiversity_summary_repository.py` pair named in
§14, most recently also independently reconfirmed by the Hard-Negative
Visit Admission Precision & Species-Escalation Correctness v1 checkpoint
touching the same two production files); zero new `ruff` findings on
either touched production file (`git stash`-isolated baseline
comparison, identical finding count/codes before and after). This
closure does **not** authorize the next Representative Field Acceptance
/ Gate A session, External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Strong-confidence precision-defect state:**
person subclass partially closed (co-occurring-contradiction sub-case);
pure single-class-misclassification sub-case remains the already-
accepted 2026-08-20 residual. Artifact subclass genuinely improved
(scene-confusor historical bookkeeping now complete) but the field-
observed Visit-018 shape itself remains open, with a precise, numeric,
evidence-based account of why closing it further needs either new
evidence-quality signals (Gate-B/new-ML territory, out of scope) or real
field data this sandbox cannot safely produce. **Remaining Gate A
dependency:** the v11 entry's own 7-item priority list, below, is
unchanged and unmet by this milestone (no field session was run, per
this milestone's own explicit instruction) -- extended, not replaced, by
this milestone's own next-field-proof items: (8) whether the same-frame
class-contradiction fix materially reduces person-associated false
Visits in a cohort with a real, extended human presence; (9) whether any
further strong-confidence scene-artifact false Visit recurs, and if so,
whether it shows the same "weak-history-then-sudden-strong" shape this
milestone could not close; (10) no whole-frame human suppression of real
birds in a session with a person present; (11) scene-confusor
participation, now also measuring corroboration-rejected occurrence
counts directly (newly possible with this milestone's own fix).

**2026-09-02 update (Representative Daylight Gate A Field Acceptance v11
-- Independent-Corroboration & Scene-Confusor Re-Proof, see §1/§6.R):**
ran the field session the Independent Corroboration Value v1 closure's own
item (1), below, required, at classification **B**. See
[representative-daylight-gate-a-field-acceptance-v11-report.md](representative-daylight-gate-a-field-acceptance-v11-report.md)
for the complete record. No production code changed; schema unchanged
(`v58`). A real 101.8-minute combined field session across two segments,
separated by a genuine, fully-disclosed, user-resolved ~71-minute Camera
Node CSI-cable hardware fault -- isolated from the Host, which stayed
healthy throughout.
**Independent-corroboration field-proof state:** the corroboration axis
was evaluated 3 times with a final outcome -- 2 correct field rejections
(Location A and the "ornament" recurrence, both classic single-generation
shapes) and 1 admission (a 14-generation proposal reaching the session's
own dominant persistent-confusor coordinates) that is a direct, hand-
verified field reproduction of the fix's own disclosed non-dominant-
multi-generation residual (`remainder=68 > remaining_floor=27` for
`N=14`) -- classified ambiguous (not confirmed-false) since its own
evidence does not clearly resolve a subject. Zero confirmed-false Visits
trace to the corroboration axis this session. **Scene-confusor field-
proof state, now directly measured, closing the prior milestone's own
disclosed evidence-trail gap:** a direct `scene_confusor_regions` table
read (not inferred) found 14 regions tracked, `occurrence_count` up to 5,
**`suspected_count = 0` for every region** -- every region crossing the
suspicion threshold held genuinely strong-confidence detections and was
correctly, by design, never suspected (one such region is the real,
stationary, repeatedly-visited feeder location itself, spanning both
segments -- direct field proof a real bird survives the mechanism); the
session's own genuinely weak, ~20-minute, 42-generation persistent-
confusor chain was intercepted almost every time by a different,
pre-existing mechanism (`blocked_ambiguous_boundary`) before it could
reach scene-confusor at all, so **the two accepted mechanisms did not get
a documented chance to compose in the field this session.** **Gate A
metric maturity:** primary false-Visit rate 8/18 confirmed = 44.4%,
numerically worse than v10's 36.4% but shown causally disjoint from it
(all 8 confirmed-false Visits trace to a real landscaping worker in-frame
-- the already-accepted, out-of-scope person-background-false-positive
class -- plus one strong-confidence leaf artifact; none caused by a
corroboration-axis or scene-confusor failure); useful-evidence 43.5% raw
/ 62.5% excluding the same confound (still below the v5/v7 94-96% band);
recall 100% (7/7 conservative) / 70% (7/10 less-conservative, both
disclosed); fragmentation 1/7 = 14.3% (a second consecutive non-zero
cohort, still not reconverged toward the prior 0% streak);
duplicates 0% (an 8th-9th convergent cohort, still READY);
`blocked_missing_evidence` 9.29% (in-band, v7-v10 convergent range,
still effectively mature as a measurement); monitoring coverage 97.5%
combined (still READY-band). Two genuine simultaneous-bird sightings
directly, independently visually confirmed (short of 3+). Zero confident
species labels on any confirmed-false Visit (Gate B clean). **Two
disclosed tooling defects** (an acceptance-recorder directory-path
encoding bug -- data itself intact, 4,373 independent frames captured
correctly regardless; and fragile `--dev-root` absolute-Windows-path
handling this same milestone's own operator hit and immediately
self-corrected, confirmed zero lasting effect), **one disclosed real
Camera Node hardware fault** (root-caused to a CSI ribbon-cable I2C
failure, user-resolved by physical reseat, fully isolated from the
product), and **one open, unconfirmed observation** (a 71-proposal
`blocked_continuation_pending` backlog at segment-2 end, plausibly
superseded intermediate state from the session's own dominant
ambiguous-boundary chain, not yet confirmed either way). This closure
does **not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening,
and does **not** select a next development milestone. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged. **Remaining Gate A dependency, in priority order, superseding
the priority order in the entry immediately below (item (1) there --
the concrete field-proof the Independent Corroboration Value v1 closure
required -- is now answered by this session, though inconclusively: see
above; replaced below by the concrete new blocker this session's own
finding requires):** (1) a next, separately-authorized Representative
Daylight Gate A cohort must specifically seek a session where a
never-strong, single-generation-shaped persistent confusor clears
`blocked_ambiguous_boundary` and reaches the quality gate as a genuinely
single-generation, repeatedly-admitted case -- the one direct field re-
test of the corroboration-axis fix this milestone was designed for and
did not obtain this session (this session's own dominant persistent
confusor was almost entirely intercepted upstream instead); the same
cohort should also re-measure whether A and B ever compose in the field
now that non-participation has a documented structural cause; (2) the
false-Visit-rate and useful-evidence-rate budgets need at least one
cohort not dominated by an unrelated person-in-frame confound, to avoid
the causal-decomposition burden this session's own report had to carry;
(3) fragmentation, re-measured a third time (v10: 1/5; v11: 1/7; still
not reconverged toward the prior 0% streak); (4) a second,
independently-varied true-latency cohort (unchanged); (5) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged -- v11's own best result remains 2 simultaneous subjects,
achieved twice, directly confirmed); (6) the bounded visual-review pass
against v7's own two remaining genuinely-unreviewed ambiguous
fragmentation units (unchanged); (7) the ~13 untraced
`blocked_missing_evidence` records, v7's own (unchanged).

**2026-09-02 update (Independent Corroboration Value & Persistent-Confusor
Admission Correctness v1, see §1/§6.R):** reopened the accepted Hard-
Negative Visit Admission Precision & Species-Escalation Correctness v1
fix because Representative Daylight Gate A Field Acceptance v10 (below)
produced real field evidence satisfying the accepted-work-freeze
exception, at classification **A** -- see
[independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md](independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md)
for the complete record. v10 found the prior rule correctly rejected 3/3
classic bare-minimum single-generation hard negatives, but the same
recurring tube-feeder-area confusor defeated its count-based
corroboration axis 4 separate times (36.4% confirmed-false-Visit rate) by
accumulating many individually-insufficient detections within one
already-confirmed generation's own extended natural persistence, never by
chaining bare-minimum restarts. **Root cause, mathematically proved, not
merely observed:** the prior floor (`2 * constituent_generation_count +
1`) implicitly assumed every constituent generation contributes only ~2
detections (the bare confirmation minimum); it never bounded how many
*more* a single generation may go on to accumulate once confirmed. The
disclosed v10 false range (9-33 detections) and real range (13-18, v10's
own weak/distant-bird control) overlap directly, so no function of raw
`detection_count` magnitude, for any constant, can separate them --
proven algebraically for a per-generation cap combined with the existing
linear floor (either a complete no-op for any cap `>2`, or a rule that
also rejects every real single-generation positive control for a cap
`<=3`) -- and a time-density/detection-rate signal, geometry variance,
and confidence-shape heuristics were each independently ruled out on the
same or stronger grounds (the last three each explicitly forbidden by
this milestone's own governing brief). **Fix:** one new, additive
`max_single_generation_detection_count` fact (`contracts.
ConfidenceEvidenceSummary`, max-not-sum across constituents) lets
`candidate_quality_gate._concentrated_in_single_generation` recursively
re-apply the *existing*, already field-justified `_BARE_DETECTOR_
CONFIRMATIONS_PER_GENERATION`/`_QUALIFYING_DETECTIONS_MARGIN` constants to
"the chain minus its own single largest member": a multi-generation
proposal's count-axis credit is now insufficient when discounting its
most-dominant generation leaves the rest at or below their own
identically-scaled floor. Zero new numeric constants anywhere.
Single-generation proposals (`N == 1`) are provably, byte-identically
unaffected -- nothing to recurse against -- so v10's own real weak-bird
control (admitted "purely via count-based corroboration") and every
existing accepted positive control are unchanged. **New finding, not
previously documented:** the already-live, unconditional (since schema
34) `scene_confusor` mechanism sits in the same admission function as a
completely independent, already-field-validated third check; empirically
verified, via a real sequential-admission reproducer (not modified, not
duplicated, not re-tuned), to independently block a 4th same-geometry,
single-generation recurrence of a never-strong signature within one
session -- closing, together with this milestone's own new check, both
the concentrated-corroboration shape (new) and the repeat-occurrence
shape (already-existing, now verified rather than assumed) v10's
persistent confusor exhibited. A single-generation proposal's own
first-through-third occurrence at a *new* location remains the same
disclosed residual the prior milestone already named, now proven
mathematically irreducible for this signal class rather than merely
observed -- honestly disclosed, not hidden, along with the real v10
session's own report never confirming whether scene-confusor state was
actually consulted for its own 4 admissions, and a two-independently-
substantial-generations edge case this check does not flag (a deliberate,
documented, bounded design choice). Production MDv5a `score_threshold`
confirmed unchanged at `0.1`; zero coordinate literals read by the fix,
proven in both directions by adversarial tests (no spatial blacklist);
schema unchanged (`v58` -- the new fact travels inside the existing
`confidence_evidence_json` text blob). **Validation:** Tier 1 (new
18-test replay suite) 18/18; Tier 2 (24 affected-subsystem files,
including scene-confusor's own 65 tests) 725 passed / 2 pre-existing
unrelated skips / 0 failures; Tier 3 (one full Core run) 5600 passed / 1
failed / 3 skipped / 23 deselected / 11 xfailed -- the 1 failure
(`test_transport_worker.py`, unrelated Camera Node transport/retry code)
independently confirmed a non-reproducible, load-induced async-timing
flake via 8 consecutive clean isolated re-runs (3 on the clean starting
HEAD, 5 with this milestone's changes restored) -- a *new* finding, not
the same previously-documented `test_place_biodiversity_summary_
repository.py` pair, verified from scratch rather than pattern-matched;
zero new `ruff` findings on every touched production file. Species-
escalation, Reviewed-truth, multi-subject-isolation, and sustained/
fallback/stop-finalization correctness all directly re-tested and
preserved (the last by construction -- zero lines changed in `frame_
tracker.py`/`candidate_visit_authority.py` -- and by both full,
unmodified suites passing unchanged). This closure does **not** authorize
the next Representative Field Acceptance / Gate A session (no field
session was run by this milestone, per its own explicit instruction),
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. Authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
**Remaining Gate A dependency, in priority order, superseding the
priority order in the v10 entry immediately below (item (1) there --
the count-accumulation admission-rule gap -- is now closed by this
milestone, with two narrow, honestly disclosed residuals named above,
and replaced below by the concrete field-proof this closure itself
requires):** (1) a next, separately-authorized Representative Daylight
Gate A cohort must field-prove this closure -- the known persistent
tube-feeder confusor no longer admits; false-Visit rate materially below
the v8/v9/v10 ~20-36% regime; useful-evidence rate materially recovers
toward v5/v7's own 94-96% range; v10's own weak small/distant-bird shape
still admits; a genuinely stationary real bird's own Visit survives in
the field, not only in a constructed reproducer; and whether scene-
confusor state was actually consulted for any repeat occurrence this
milestone's own reproducer shows it should catch, closing this
milestone's own disclosed evidence-trail gap; (2) a second,
independently-varied true-latency cohort (unchanged); (3) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(5) the ~13 untraced `blocked_missing_evidence` records, v7's own
(unchanged); (6) fragmentation, re-measured after v10's own 1/5 result
(unchanged, out of this milestone's own explicit scope).

**2026-09-02 update (Representative Daylight Gate A Field Acceptance v10
-- Admission-Precision Re-Proof & Gate A Closure Tranche, see §1/§6.R):**
ran the field session the Hard-Negative Visit Admission Precision fix's
own closure required, at classification **A** -- see
[representative-daylight-gate-a-field-acceptance-v10-report.md](representative-daylight-gate-a-field-acceptance-v10-report.md)
for the complete record. A real ~90.2-minute Observation session
(2026-09-02, 07:39:59-09:11:12 EDT) against the same real reference
Camera Node, on a fresh disposable instance
(`MockingBirdFieldAcceptanceV10`) whose accepted-HEAD identity was
directly confirmed (`git_commit` exact match, schema v58). Both required
preflight gates confirmed compatible/calibrated before Observation start.
**Primary finding: the fix's own stated field-proof criterion did not
hold.** Direct visual + raw-detection-trajectory review of all 11
admitted Visits (100%, not sampled) found **4 confirmed false/background
admissions (36.4%)** -- worse than both v8 (22.2%) and v9 (20.0%), not
materially reduced toward v5/v7's 4-5.3% range. This is not a diffuse
regression: the rule correctly rejected 3/3 classic bare-minimum
single-generation hard-negative chains this session (including an exact
re-confirmation, by bounding-box coordinates and direct visual
inspection, of v8's own foliage-cluster "Location A"), but the *same*
recurring background confusor (a location at/near the tube feeder)
defeated the rule's count-based corroboration axis 4 separate times by
accumulating enough individually-insufficient low-confidence detections
within one continuation window to clear `2 * constituent_generation_count
+ 1` without ever reaching a strong detection -- precisely the residual
risk the fix's own report disclosed as untested at this scale ("a
hypothetical real bird at the exact same corroboration floor... is not
distinguishable by corroboration structure alone"), now concretely
reproduced with real field data (15 further `blocked_ambiguous_boundary`
occurrences of the same confusor location, spanning nearly the entire
session, corroborate that this is a near-continuous background signal,
not an intermittent one). **Weak-real-bird recall preserved** (a genuine
small/distant bird, matching `northern_mockingbird`, admitted three times
via count-based corroboration, never rejected). One genuine recall miss
was found and traced (a real bird at the same feeder, ~5.8 minutes after
an admitted Visit, resolved `blocked_ambiguous_boundary`) -- confirmed
**not** attributable to the new rule, which the pre-existing arbitration
mechanism, unrelated to `reject_insufficient_detector_corroboration`,
alone produced. **Gate B's own species-escalation failure class (false
Visit -> confident wrong species) did not recur**: none of the 4
confirmed-false admissions received a species guess (Identification
Eligibility/Abstention correctly abstained on all of them). Useful-
evidence rate fell to 54.5% (below v9's already-withdrawn 76.0%).
Fragmentation regressed to one confirmed real case (two overlapping-
window admitted Visits at one location, tracker-interrupted rather than
merged) -- breaking the prior 6th/7th-cohort 0% convergence streak on a
single-cohort, small-denominator basis. Duplicates remain 0% (7th
convergent cohort). `blocked_missing_evidence` improved further to 6.7%
distinct-proposal rate -- better than v7 (9.4%), v8 (9.9%), and v9
(8.9%), a further convergent, healthy result. RTT calibration: 445
in-session batches (merged from periodic snapshots -- see below), 98.9%
`calibrated`, 0 clock jumps. True latency: median T0->T5 103.9s / p90
183.3s, closely matching v9 (111.8s / 173.9s), with one disclosed,
root-caused outlier (candidate-010's own finalization delayed ~11.4
minutes by a temporally-close subsequent real encounter at the same
location awaiting its own arbitration -- the accepted Visit-Continuity
quiet-period mechanism, not a new defect). Monitoring coverage 99.99%
(4,296 frames, further convergent). No multi-subject wildlife evidence
this session (today's activity was sparser than v5-v9's own cohorts, 11
admissions vs. 19-27) -- target not met, unrelated to this milestone's
own scope. Stop-finalization and the `AnalysisStreamRetryPolicy`
(2 reconnect recoveries, both clean) both worked correctly a second time
on a different Stream/session. **New methodological finding, disclosed
for future sessions:** the counterfactual ledger's own 60-minute
age-eviction bound (`CounterfactualRetentionConfig.max_age_ms`) is
shorter than this milestone's own 75-100 minute target session length --
a single end-of-session read would have silently lost ~46% of the
session's own raw-detection/proposal-outcome history to eviction;
recovered instead via periodic full-window snapshots every 12 minutes,
merged post-hoc, achieving 100% recovery of the raw-detection and
track-generation ledgers. **Field-acceptance instance lifecycle tooling
exercised end to end for the first time in a real session**
(`init` -> `completed` -> `archived`, evidence-archive attached,
`SAFE_TO_RECLAIM`, deliberately not destroyed, per the milestone's own
"do not manually improvise cleanup" instruction). One disclosed
operational action, user-authorized: the reference Camera Node's single
pairing-credential slot was held by the now-dormant v9 instance;
freeing it for v10 required an SSH-mediated pairing-state reset,
correctly declined once by the auto-mode permission classifier as a
consequential remote-infrastructure action, then explicitly authorized
by the user before proceeding (backed up first; `boot_id` continuity
confirmed a credential-state reset only, never a physical device
change). Tier 1-3 correctly not run (zero production code changed, per
this milestone's own explicit validation rule); zero schema change
(v58, unchanged). This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Concrete new
blocker, replacing item (1) in the list below:** the count-accumulation
loophole in `reject_insufficient_detector_corroboration` traced above --
a future admission-precision milestone needs to bound corroboration
credit by genuine detection value/variance (not raw repeated-detection
count alone) so a physically static confusor cannot out-accumulate a
floor scaled only by generation count; this is now a precisely-scoped
DEV contract candidate, not an open-ended re-investigation. **Remaining
Gate A dependency, in priority order, superseding the priority order in
the Hard-Negative entry below (item (1) there is now answered -- field-
proof ran and did not confirm the fix; superseded by the concrete new
blocker just above):** (1) the count-accumulation admission-rule gap
just named; (2) a second, independently-varied true-latency cohort
(unchanged -- Gate A's own standing rule requires cross-session
convergence); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged, still not met by v10); (4)
the bounded visual-review pass against v7's own two remaining genuinely-
unreviewed ambiguous fragmentation units (unchanged); (5) the ~13
untraced `blocked_missing_evidence` records, v7's own (unchanged); (6)
the three real, disk-space-consuming legacy field-acceptance dev-roots
now disclosed as structurally invisible to the new lifecycle-manifest
tool's own `preflight` reclaimability accounting (new, bounded,
tooling-only, not release-critical).

**2026-09-02 update (Field-Acceptance Instance Lifecycle & Storage Safety
v1, see §1/§6.R):** closes the accumulation root cause v8's own report
first diagnosed and v9's own session re-encountered and manually worked
around -- "every prior field-acceptance disposable instance was left
running/retained indefinitely after acceptance, none ever cleaned up" --
at classification **A**. See
[field-acceptance-instance-lifecycle-storage-safety-v1-report.md](field-acceptance-instance-lifecycle-storage-safety-v1-report.md)
for the complete record; see §6.R's own chronological entry for the full
account (root cause, the new manifest/lifecycle/reclaimability contract,
cleanup safety, cache scope, and the real native-Windows proof, including
one genuine performance defect found and fixed by that proof -- a
multi-minute wrong-target refusal against the real, ~29GB, many-release
`MockingBirdDev` root, fixed to 0.104 seconds, safety never at risk).
Purely release/deployment tooling: no wildlife cohort, no Camera Node
activity, zero `src/mockingbird/` files changed, zero schema change
(`v58`, unchanged), and general product retention/disk-pressure behavior
(Storage / Retention / Disk-Pressure & Recovery Closure v1 / Retention
Correctness & Bounded Cleanup Closure v1, §6.M, already accepted and
frozen) was **not reopened**. New: a durable, self-verifying sidecar
manifest (`field_acceptance_manifest.json`) tracking `active -> completed
-> archived`, a new standalone `scripts/field_acceptance_instance_
lifecycle.py` (`init`/`status`/`assess`/`complete`/`mark-archived`/
`cleanup`/`preflight`), and two additive changes to `scripts/deploy_
windows_dev.py` (a `--stop` flag exposing the already-existing, already
-safe `stop_verified_deployment` standalone; a pre-build storage
-preflight guard mirroring already-accepted disk-pressure/recorder
-ceiling thresholds). Cleanup is dry-run by default, explicit `--destroy`
required, redundantly re-verified immediately before its one delegated
-not-reimplemented destructive call. Tier 1 170/170, Tier 2 147/147, 0
regressions across both; Tier 3 correctly not run (no product code
touched); zero `ruff` findings. This closure does **not** authorize the
next Representative Field Acceptance / Gate A session (Representative
Daylight Gate A Field Acceptance v10 -- Admission-Precision Re-Proof &
Gate A Closure Tranche remains the exact next daylight dependency,
unchanged and not self-authorized here), External Pre-Release Acceptance,
or Final Release Hardening, and does **not** select a next development
milestone. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A dependency,
unchanged from the list immediately below -- this milestone is orthogonal
to Gate A's own field-evidence dependency chain and neither adds to nor
closes any item on it:** (1) the next Representative Daylight Gate A
cohort must field-prove the Hard-Negative Visit Admission Precision fix
(unchanged); (2) a second, independently-varied true-latency cohort
(unchanged); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (4) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (5) the ~13 untraced `blocked_
missing_evidence` records, v7's own (unchanged).

**2026-09-02 update (Host <-> Camera Node Release-Compatibility Preflight
v1, see §1/§6.R):** closes the release-process gap the Reference Camera
Node RTT-Capability Upgrade & Compatibility Re-Proof v1 entry (below)
disclosed but explicitly left unfixed -- "no automated mechanism
currently exists that checks 'is the installed Camera Node build
compatible with/current relative to the accepted repo HEAD' before a
Gate A/field-acceptance session begins" -- at classification **A**. See
[host-camera-node-release-compatibility-preflight-v1-report.md](host-camera-node-release-compatibility-preflight-v1-report.md)
for the complete record. This is a release-process/correctness closure,
not a field session: no wildlife cohort was run, no detector/model/
hard-negative/RTT-protocol code was touched, and Gate A's own evidence
body and remaining dependency (below) are unchanged by this milestone.
New `mockingbird.observation.node_compatibility`: a pure decision table
plus live orchestration reusing the existing, unmodified `CameraNode
Client`/`clock_calibration.estimate_rtt_clock_calibration` functions --
never a second calibration implementation. Compatibility is capability
-based, never exact git-commit equality (the Camera Node has never
exposed a live `git_commit`; `service_version`/`app_version` are both
pinned at `"0.1.0"` on Host and Node today, so a `version_skew_detected`
field is reported purely as informational diagnostics and never gates
compatibility). Two bounded profiles (`ordinary_monitoring`: only the
health protocol must answer; `field_acceptance`: additionally requires
the expected camera live-confirmed available, RTT timestamp fields
present, and a real bounded RTT-bounded calibration batch to actually
reach `state == "calibrated"`); six actionable states (`compatible`,
`incompatible_missing_capability`, `incompatible_protocol`,
`calibration_failed`, `node_unreachable`, `camera_unavailable`) -- never
a generic "Camera Node unhealthy" bucket. No wire-protocol change --
every fact needed (`api_version`/`service_version`/`node_receive_time`/
`node_time`) was already on the wire; an old Node's health response
parses exactly as before. Wired into the one and only call site
(`grep`-confirmed: `get_observation_engine_session_manager().start(`
appears exactly once in `src/`) -- only a field-acceptance credential's
own session start is held to the stricter profile, and only once the
Stream is already fully paired; an ordinary signed-in user's Start
observing is structurally unaffected (the new code path, and its network
calls, never execute outside that condition). On incompatibility, fails
closed before the Observation Engine session, acceptance-recorder
allocation, or any GPU/model resource commitment -- confirmed end to end,
including a same-session follow-up status check proving `observing`
stayed `False`. Zero mutation of Node state anywhere (every call is a
pre-existing, already-accepted, read-only GET). Doctor gains one new
informational context key on its existing `camera_node` check's PASS
branch, pointing at a new standalone script
(`scripts/check_camera_node_compatibility.py`) for a live verdict --
mirrors the `clock` check's own established "not measurable from a
standalone Doctor check" precedent rather than adding a live probe to
Doctor itself. Exercised live against the real, already-upgraded
reference Camera Node (`192.168.1.112:8787`) from two independent
network paths -- this sandbox and a real native-Windows Host (the actual
Gate A Host platform) -- both profiles `compatible` on both paths, each
with a real 5/5 valid RTT-bounded calibration batch (22.65ms RTT from
this sandbox, 24.0ms from native Windows). One incidental, pre-existing,
unrelated finding disclosed on the Windows dev instance (a stale database
schema predating `camera_node_last_seen_at`, schema 37, causing Doctor's
`camera_node` check to raise rather than gracefully degrade) -- confirmed
unrelated to this milestone (`storage/models.py` untouched) and already
covered by passing Linux-side tests against a correctly-migrated schema;
left disclosed for a future Doctor/migration-robustness milestone, not
fixed here. No schema change. Tier 1 (25/25, non-flaky across 5
consecutive runs) and Tier 2 (582/582 across `CameraNodeClient`, RTT
calibration, engine runtime, Doctor, field-acceptance auth, the
installer, and the full `test_api.py`/`test_observation_camera_node_
live.py` surface, plus a clean full-app import/boot smoke test) both
clean; Tier 3 correctly not run, per this milestone's own explicit §29
carve-out for enforcement limited to acceptance/Doctor surfaces, matching
this diff precisely (confirmed by direct code reading: the new `api/
main.py` behavior is conditionally gated and reachable only for an
already-paired Stream; `unified_status.py` gained one new additive
function; `doctor.py` gained one new informational context key inside an
existing branch). Zero new `ruff` findings (`git stash`-isolated baseline
comparison; `api/main.py`'s own 26 pre-existing, unrelated findings
unchanged before/after). This closure does **not** authorize the next
Representative Field Acceptance / Gate A session (Representative Daylight
Gate A Field Acceptance v10 -- Admission-Precision Re-Proof & Gate A
Closure Tranche remains the exact next daylight dependency, unchanged and
not self-authorized here), External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, unchanged from the
list immediately below -- this milestone is orthogonal to Gate A's own
field-evidence dependency chain and neither adds to nor closes any item
on it:** (1) the next Representative Daylight Gate A cohort must
field-prove the Hard-Negative Visit Admission Precision fix (unchanged --
see the Hard-Negative entry below for the complete field-proof criteria);
(2) a second, independently-varied true-latency cohort (unchanged); (3) a
second live cohort producing genuinely crowded 3+-simultaneous-subject
activity (unchanged); (4) the bounded visual-review pass against v7's own
two remaining genuinely-unreviewed ambiguous fragmentation units
(unchanged); (5) the ~13 untraced `blocked_missing_evidence` records,
v7's own (unchanged).

**2026-09-01 update (Review Provenance Validation & API Error Semantics
v1, see §1/§6.R):** closes item (6) immediately below -- the
`agent_diagnostic` review-provenance `500` v9's own field session
disclosed and worked around -- at classification **A**. See
[review-provenance-validation-api-error-semantics-v1-report.md](review-provenance-validation-api-error-semantics-v1-report.md)
for the complete record. Reproduced through the real `POST
/api/review-labels` endpoint (not the domain function directly), captured
pre-fix: `review_origin="agent_diagnostic"` with no `reviewer_identity`
correctly raises `ReviewProvenanceError` in `product_repository.py`, but
`create_review_label` (`api/main.py`) caught only
`ReviewRevisionConflictError`, so this well-formed validation error
reached the client as an unhandled `500`. Root cause traced to one
missing `except` clause -- `create_review_label`'s own closest sibling,
`reclassify_review_label_provenance`, already carries the identical
mapping for this identical exception type (`except ReviewProvenanceError
as error: raise HTTPException(status_code=400, detail=str(error)) from
error`); the fix adds exactly that one clause, mirrored, not invented. A
scope check traced every one of the four endpoints reaching
`review_provenance.validate_review_origin`: `create_review_label` was the
only one still exhibiting an unhandled `500` (the other three --
`revise_visit_review`, `create_fast_review_correction`,
`bulk_correct_review_queue_items` -- already avoid it via their own
pre-existing generic `except ValueError` fallback, with a less-specific
message than `str(error)`, disclosed in the report as a minor,
out-of-scope inconsistency, not fixed here). Provenance policy
unweakened: `review_provenance.py` untouched, `agent_diagnostic`/
`imported_curated` still strictly require `reviewer_identity`, no
default, no anonymous-reviewer fallback. Directly confirmed, not assumed:
the rejected request persists nothing (checked via the Visit's own
unfiltered `correction_history`, since `GET /api/review-labels` resolves
only the current *authoritative* row per target and would hide a leaked
non-authoritative row regardless); a failed request cannot overwrite
*existing* Reviewed truth on the same Visit; no misleading
`review.corrected` audit entry is created on failure; a genuinely
unrelated unexpected exception (a monkeypatched `RuntimeError`) still
surfaces unmasked, proving the new clause did not widen into a generic
catch-all. 8 lines changed in one function in `api/main.py`; zero
schema/model/provenance-policy change. Tier 1 (`tests/test_api.py` in
full, 7 new tests) 61/61; Tier 2 (11 directly-traced
review/correction/auth/audit files) 206/206, 0 regressions; Tier 3
correctly not run (one `except` clause, one endpoint, nothing
shared/cross-cutting touched -- the decision criterion this milestone
itself set, satisfied against the actual diff); zero new `ruff` findings
(baseline-isolated via `git stash`). This closure does **not** authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone. Authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Remaining
Gate A dependency, in priority order, superseding the priority order in
the Hard-Negative entry immediately below (item (6) there -- the
`agent_diagnostic` review-provenance defect -- is now CLOSED by this
milestone and dropped from this list):** (1) the next Representative
Daylight Gate A cohort must field-prove the Hard-Negative Visit Admission
Precision fix (unchanged -- see the Hard-Negative entry immediately below
for the complete field-proof criteria); (2) a second, independently
-varied true-latency cohort (unchanged); (3) a second live cohort
producing genuinely crowded 3+-simultaneous-subject activity (unchanged);
(4) the bounded visual-review pass against v7's own two remaining
genuinely-unreviewed ambiguous fragmentation units (unchanged); (5) the
~13 untraced `blocked_missing_evidence` records, v7's own (unchanged).

**2026-09-01 update (Hard-Negative Visit Admission Precision &
Species-Escalation Correctness v1, see §1/§6.R):** closed the reproducible
precision defect v9 field-confirmed, at classification **A** -- see
[hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md](hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md)
for the complete record. Traced the first irreversible product decision
explicitly, not assumed: neither tracker confirmation (deliberate,
recall-preserving infrastructure -- "a repeated, spatially-coherent
evidence bar, never a strength bar," left untouched) nor candidate
authority (mode/lineage/rate-limits only, by design, never evidence
-quality) -- `candidate_quality_gate.evaluate_evidence_admission`, the
existing boundary already composing "already-measured facts into one
conservative reviewable-enough decision," immediately before evidence
bytes are written and a Visit/Event becomes real. Root cause: the
admission pipeline already computed rich per-detection confidence
accounting (`contracts.ConfidenceEvidenceSummary`, Detection Quality
Accounting v1) but no admission-adjacent gate had ever read it; v8's own
already-recorded finding (confirmed-real Visits 006/016 "not
distinguishable from the false cluster by confidence alone") and
Detection Quality Accounting v1's own 70-Visit confidence-threshold sweep
(conclusively rejected, "Production authority gate" in
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md))
together rule out a confidence-*magnitude* fix; what was unused was the
corroboration-*structure* half of the same already-computed evidence.
**New admission rule** (`reject_insufficient_detector_corroboration`,
added last, after every pre-existing check): rejects only when a proposal
never reached a strong detection AND its genuine detector corroboration
never exceeds a scaled floor (`2 * constituent_generation_count + 1` --
closes the "chain more bare-minimum restarts together" loophole a flat
floor would leave open, directly reproducing and correctly rejecting
v9's own `visit-observation-candidate-027` 9-generation chained shape)
AND it never showed two consecutive genuine detections anywhere
(structurally ungameable -- `merge_confidence_evidence` already takes the
max, never the sum, of that exact field). Either axis clearing its own
floor admits; any unknown fact never causes a reject. Not a confidence
threshold, not a scene-coordinate blacklist (proven via an explicit
adversarial test at an arbitrary non-field bounding box), and does not
touch the production MDv5a `0.1` `score_threshold`. **Reproduced from
real field evidence, not a labeled-background fake unit test:**
`visit-observation-candidate-026`'s own real, traced signature (3 raw
detections, confidence 0.109-0.111, the feeder-cap sun-glint location --
the one confirmed-false v9 Visit that received a confident wrong species
label) and the recurring foliage-cluster location are each reproduced by
driving real `DetectionObservation`/`FramePacket` sequences through the
real, unmodified `ProviderNeutralFrameTracker`/`build_tracklets`/
`assemble_visit_episodes`/`CandidateVisitAuthorityAdapter`/
`ProductRepository` path, and both are now correctly rejected. Six
distinct genuine-weak-bird positive controls (small/distant, brief
landing, low-confidence-but-real, partially occluded, intermittently
corroborated, sustained multi-generation with one real consecutive
segment) continue to admit through the identical real path; a normal
strong Visit, multi-subject isolation (no cross-subject corroboration),
and the accepted sustained-activity/fallback/stop-finalization behavior
are all unaffected (by construction -- zero lines changed in
`frame_tracker.py`/`visit_episode_assembler.py` -- and directly tested).
**Species-escalation result (Option A, directly confirmed against a real
repository, not inferred):** rejecting the false Visit at admission
structurally eliminates the issue -- no `VisitModel`/`ObservationCandidateVisitModel`
row is ever created for a rejected proposal, and every production species
-inference entry point requires one to resolve at all; `identification_
eligibility.py` was not reopened. Reviewed truth preserved and directly
tested. `blocked_missing_evidence` and the disclosed `POST
/api/review-labels` `agent_diagnostic` 500 both confirmed untouched, as
instructed. Rate-limit interaction confirmed clean: a rejected hard
negative never increments `candidates_created_in_session`/`_trailing_
hour` (only `outcome=="created"` does), so it cannot consume the same
capacity an admitted Visit does. **Validation:** Tier 1 (new replay suite)
16/16; Tier 2 (every directly/indirectly affected subsystem) 733 tests, 0
regressions; Tier 3 (one full Core run) 5504 passed / 2 failed / 3 skipped
/ 23 deselected / 11 xfailed -- the 2 failures independently confirmed
pre-existing and unrelated via `git stash`-isolated baseline reproduction
on the exact starting HEAD (the same already-repeatedly-documented
`test_place_biodiversity_summary_repository.py` pair named in §14,
below); zero new `ruff` findings (same baseline-isolated confirmation).
One honestly disclosed residual, not hidden: a hypothetical real bird at
the exact same corroboration floor as the traced false cluster is not
distinguishable by corroboration structure alone (the same
structurally-irreducible limit v8's own report already showed for
confidence magnitude), and this fix has not yet been field-validated at
the scale "Production authority gate"'s own six conditions would require
for a fully-settled confidence-threshold-class policy -- both disclosed,
neither self-authorized to close via a new field cohort here, per this
milestone's own explicit instruction. This closure does **not** authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone. Authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Remaining
Gate A dependency, in priority order, superseding the priority order in
the v9 entry immediately below:** (1) the next Representative Daylight
Gate A cohort must field-prove this precision fix -- false-Visit rate
materially below the v8/v9 ~20-22.2% regime, useful-evidence rate
recovered, genuine low-confidence recall preserved, no recurrence of
either known hard-negative cluster as an *admitted* Visit, Gate B
hard-negative species-escalation absent -- not self-authorized by this
closure; (2) a second, independently-varied true-latency cohort
(unchanged -- Gate A's own standing rule requires cross-session
convergence); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (4) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (5) the ~13 untraced
`blocked_missing_evidence` records, v7's own (unchanged, confirmed not
the same root cause as this milestone's own fix); (6) the disclosed
`agent_diagnostic` review-provenance error-handling defect (unchanged,
bounded, a precise next DEV contract already named).

**2026-09-01 update (Representative Daylight Gate A Field Acceptance v9 --
True-Latency & Precision Reconciliation Tranche, see §1/§6.R):** ran the
field session the RTT re-proof's own closure made possible, at
classification **A** -- see
[representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
for the complete record. A real ~97.1-minute Observation session (T_start
20:34:04.727Z, `stopped_at` 22:11:53.796Z) against the same real reference
Camera Node, with the acceptance recorder confirmed writing real frames to
the correct per-session path within ~4.2 minutes (97.95% temporal-span
coverage, 2,353 files, 2.02GB of a 4.3GB sized budget -- no truncation).
**Item (1) (the first real, validly RTT-normalized T0->T5 latency field
distribution) is now closed:** 447 of 460 in-session RTT-bounded batches
`calibrated` (0 `inconsistent_samples`, 0 clock jumps), producing 24 of 25
admitted Visits with a real measured latency sample (median 111,811ms,
p90 173,944ms, max 307,373ms). Root-caused, not merely reported: an
additive decomposition (beyond the accepted `capture_to_visible_
latency.py` contract, using only already-published fields) shows a tight,
consistent ~48-60s "tail latency" (last capture to decision) across
almost every sample regardless of encounter length, matching the accepted
Visit-Continuity/episode-boundary quiet-period design exactly (multiple
individual proposals' own full `blocked_continuation_pending`/`episode_
boundary_not_yet_final` revision histories directly confirm it) -- this is
the deliberate, now-quantified cost of avoiding Visit fragmentation, not a
pipeline inefficiency. **Item (2) (reconciling the diverged false-Visit-
rate/useful-evidence-rate evidence body) now has a determinate answer:**
direct multi-frame pixel-region inspection (the v5/v7/v8-established
method) of every Visit with zero "strong" detections found **5 of 25
(20.0%) confirmed false** -- closely replicating v8's own 22.2%, and
materially diverging from v5 (5.3%)/v7 (4.0%). **v8's elevated rate
reproduces: it is a real, reproducible characteristic of this scene under
current conditions, not a v8-specific cohort anomaly.** Two distinct
recurring hard-negative spatial locations were found and traced in full
(detector box, confidence, frame content, track lifetime, proposal path,
evidence, species eligibility): one a near-exact recurrence of v8's own
already-reported location (a hanging leaf cluster over the road); one new
this session (a sun-glint on the tube feeder's own glossy cap). The
false-Visit-rate/useful-evidence-rate candidate budgets remain correctly
withdrawn (v9 reinforces, not reverses, v8's own withdrawal -- v9's own
strict useful-evidence rate, 76.0%, sits below the previously-proposed
~85% candidate). A real, previously-unknown Gate B residual instance was
also field-confirmed for the first time since Background/Empty Evidence
Species-Confidence Correctness v1 was accepted: 1 of the 5 confirmed-false
Visits received a wrong confident species label, root-caused precisely to
the fix's own already-disclosed exclusion (genuinely detector-sourced,
not tracker-extrapolated, evidence) -- not a regression, but the first
live instance of an already-known gap. Fragmentation reached a
sixth/seventh convergent real cohort at 0% (14/14 `correctly_represented`,
using the accepted reviewer-disposition method, not raw clustering);
duplicates a fourth convergent cohort at 0% (0/25, zero shared tracker
evidence); `blocked_missing_evidence` a third independently-varied
post-fix confirmation (8.9%, 12/135, closely clustered with v7's 9.4% and
v8's 9.9%). The rolling `max_candidates_per_hour` limit activated for the
second time in any cohort (6 real blocks, all high-confidence, self-
cleared correctly). Direct visual confirmation of 2 simultaneous birds at
the feeder was obtained (the best 2-subject evidence to date), but the
detection-stage mechanism (independently detected-then-NMS-suppressed, or
never separately detected) could not be traced this session
(`raw_detections` did not merge losslessly, a disclosed, known gap
matching v8's own). Zero persistence contention; zero ERROR/CRITICAL/
WARNING/Traceback lines across the full structured log. One real,
reproducible product defect was found via live product usage during this
session's own review-recording step, disclosed and worked around, not
fixed (out of this milestone's own scope): `POST /api/review-labels` with
`review_origin=agent_diagnostic` and no `reviewer_identity` correctly
raises `ReviewProvenanceError`, but `create_review_label` only catches
`ReviewRevisionConflictError` explicitly, so this well-formed validation
error propagates as an unhandled `500` instead of a clean `400` --
a precise, bounded next DEV contract is named in the report's own
"Defects" section. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Per this milestone's own explicit instruction,
Gate A is **not** self-closed by this report: the false-Visit-rate
divergence reproducing, rather than resolving, is judged a complete,
determinate answer to this milestone's own second primary objective, but
still leaves a release-blocking open item, and true latency has exactly
one real cohort (Gate A's own standing rule requires cross-session
convergence before any number is proposed). Authorization remains **NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. See
§6.R, below, for the complete, updated "Remaining Gate A dependency"
account.

**2026-09-01 update (Reference Camera Node RTT-Capability Upgrade &
Compatibility Re-Proof v1, see §1/§6.R):** closes the Camera Node upgrade
dependency the v8 reconciliation immediately below named as Gate A's own
sharpest remaining item. See
[reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
for the complete record. Classification **A**. The real reference Camera
Node (`node-76ec8e53ae586dd0`, Pi 4, `192.168.1.112`) was upgraded, using
the accepted `scripts/install_camera_node.py` mechanism end to end (build
against accepted HEAD `1a39479` -> preflight -> install), from
`git_commit baf9fdb` (71 commits behind, built 2026-08-27, predating the
RTT protocol) to `git_commit 1a39479` itself -- confirmed via the fresh
`manifest.json`, `install_camera_node.py --status`, and direct inspection
of the deployed wheel. Zero unexpected config/data loss (`node.env`
byte-preserved per the installer's own report; pairing survived the
upgrade itself intact -- `node_id`/`pairing_required` unchanged
before/after); rollback to the prior build remains available and was not
exercised (no new defect appeared). Pre-upgrade RED confirmed live
(`GET /node/v1/health` lacked `node_receive_time`/`node_time`);
post-upgrade GREEN confirmed live (both fields present, valid UTC,
`node_receive_time <= node_time`, advancing across independent requests
over the following ~10 minutes -- proven live, not cached). Ran the real,
unmodified production RTT functions (`CameraNodeClient.sample_clock_
round_trip`, `estimate_rtt_clock_calibration`) directly against the
upgraded Node: **6 of 6 real calibration batches (30 round trips, ~3.35
real minutes) reached `state="calibrated"`**, zero `insufficient_samples`,
zero `inconsistent_samples`, all 6 batch intervals mutually consistent
(raw RTT 102-393ms, all well under the 1000ms ceiling). This is the first
real, valid RTT-bounded calibration evidence to exist since the protocol
was accepted -- v8's own 796-batch, 0-valid session is now understood to
be an infrastructure gap already closed, not a mechanism defect (the
mechanism itself was already independently proven correct-under-failure by
v8; this milestone proves it correct-under-success). A real camera smoke
test (a fresh, disposable, CPU-only local Host instance -- no Windows/GPU
needed for this, since the live-preview path used is independent of the
GPU-only Observation Engine detector) drove a real pairing, a real camera
-setup completion, and three real 1920x1080 live frames through the actual
Host API, with advancing frame sequence numbers and capture timestamps,
visually confirmed as real footage of the reference yard. This session
deliberately displaced the stale pairing v8's own session had left in
place (with real-time user approval, after the environment's own safety
layer correctly declined to let this proceed silently) -- documented
explicitly as a choice this session made for its own verification
purposes, distinct from and subsequent to confirming the upgrade itself
preserved pairing cleanly. Doctor ran clean for every check within this
milestone's scope; confirmed no dedicated "old Node version" warning
exists anywhere in Doctor to have newly cleared (there was never one).
Also newly, independently root-caused (not merely re-cited): **no
automated mechanism anywhere in the release process currently checks
Camera-Node-build-vs-Host-build compatibility before a Gate A/field
-acceptance session begins** -- `install_camera_node.py --preflight` only
ever runs on-demand, before an operator-chosen upgrade, never as a
precondition of starting an Observation session. Disclosed, not fixed
(explicit non-goal: no fleet-management feature built here) -- a future,
separately-scoped release-engineering milestone should weigh a lightweight
preflight/Doctor check for this. No production code was changed; no tests
were invented (real-hardware validation is this milestone's own
validation, per its own explicit instruction). Authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged;
this closure does **not** authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone.
**Remaining Gate A dependency, in priority order, superseding the priority
order in the v8 entry immediately below:** (1) the first real, *validly
RTT-normalized* T0->T5 capture-to-visible latency field distribution --
the Node, Host, and calibration mechanism are now all proven ready; only a
live field session's own real samples are missing; (2) reconciling the
now-diverged false-Visit-rate/useful-evidence-rate evidence body (v5/v7
vs. v8) -- unchanged, not attempted here (non-goal: no detector/model
tuning); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (4) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (5) the ~13 untraced
`blocked_missing_evidence` records, v7's own (unchanged); (6) the
already-known Gate B admission-precision residual (unchanged).

**2026-09-01 update (Representative Daylight Gate A Field Acceptance v8 --
True-Latency & Crowding Closure Tranche, see §1/§6.R):** ran the first field
session against post-RTT-calibration accepted HEAD, at classification **B**
-- see
[representative-daylight-gate-a-field-acceptance-v8-report.md](representative-daylight-gate-a-field-acceptance-v8-report.md)
for the complete record. Deployed a genuinely fresh, disposable instance
(not the operator's own identity; reused V7's already-populated runtime/
model/BioCLIP caches by renaming its directory and wiping only `userdata/`,
per two user-approved storage-headroom decisions -- see the report's own
"Defects" -- rather than paying a fresh ~8GB cache-population cost against
this milestone's own severely constrained storage headroom, itself now
root-caused for the first time: every prior field-acceptance disposable
instance was left running/retained indefinitely after acceptance, none
ever cleaned up). A real, live 158.2-minute Observation session followed
against the real reference Camera Node (the identical physical camera
every prior Gate A cohort used) -- materially longer than the 60-120
minute target, disclosed as such, not concealed. `candidates_created`
reached **27** by session end (a new high across every Gate A cohort to
date, exceeding v7's own 25), all in-session, none rescued at stop (an
honest `stop_finalization_pending` observed live then correctly resolved
with nothing further rescuable). Fragmentation accounting reached, for the
first time in any cohort, **zero residual ambiguous denominator units**
(16 of 16 `correctly_represented`, 0 fragmented/duplicate/missed/merged --
the fourth/fifth convergent real cohort at 0% confirmed fragmentation).
Fallback mechanics were exercised more deeply than any prior cohort (8
attempted, 7 admitted, 1 honestly exhausted, one chain reaching fallback
position 3 -- the deepest yet observed), and `blocked_missing_evidence`
(9.9%, 21/212 distinct proposals, using the same denominator convention v6/
v7 established) closely replicates v7's own post-fix level at nearly 2x the
sample size, a real second independently-varied confirmation the
Preservation/Fallback fix holds at scale. `observation_candidate_visit_
persistence_contention`: zero. Stop-finalization: honest, clean.

**Primary purpose not achieved, for a real, precisely root-caused reason,
not a measurement-contract defect: zero valid RTT-bounded calibration
samples were obtained (0 of 796 attempted batches; 796 `insufficient_
samples`), so zero valid true T0 -> T5 latency samples exist (27 of 27
admitted Visits honestly report `invalid_clock_mapping`).** Root-caused
three independent ways, not merely disclosed: the reference Camera Node's
live `GET /node/v1/health` response lacks the two additive fields
(`node_receive_time`/`node_time`) the accepted RTT-Bounded Clock
Calibration v1 milestone added; `grep` of the Node's own installed code
confirms the string does not exist anywhere on it; and its own install
manifest records `git_commit baf9fdb` (built 2026-08-27), independently
confirmed via `git merge-base --is-ancestor` to be **69 commits behind**
current HEAD and to predate the commit (`bc6d5ee`) that introduced the
field the calibration protocol depends on -- the reference Camera Node has
not been redeployed since the "Camera Node Upgrade & Compatibility
Recovery v1" milestone (2026-08-26), across five field-relevant milestones
accepted since. Not fixed live, deliberately: doing so mid-session would
have required restarting/redeploying the Node's own service, risking
exactly the "do not force a reconnect" action this milestone's own
governing brief explicitly prohibited, and would have contaminated
already-collected measurements. The accepted one-way (relative)
drift/jump monitor, unaffected by the missing fields, returned a complete,
clean, fully valid record throughout (796 of 796 `calibrated`, offset
stable within an 85-244ms band across the full session, zero clock
jumps) -- real, positive evidence the underlying Node-Host clock
relationship was stable and well-behaved, but this cannot substitute for
the two-sided bound the milestone needed, by the accepted design's own
explicit reasoning. **RTT calibration mechanism itself further validated
as correct and honest under exactly this failure mode** (graceful
degradation, never a crash, at every layer, across a genuinely large real
sample) -- the measurement contract is proven working; the physical
prerequisite it depends on is not yet met.

A further real, well-evidenced, and materially reopening finding: **direct
pixel-region inspection** (cropping each low-confidence, no-species
admitted Visit's own exact recorded bounding box out of its nearest
acceptance-recorder frame, matching the v5 report's own established
method) found **6 of 27 admitted Visits (22.2%) to be false or
likely-false** -- empty grass/background, not animals, 5 of them directly
pixel-confirmed and clustered at one specific recurring low-confidence
screen location (most plausibly one hanging leaf cluster or branch tip).
This directly and materially exceeds v5 (5.3%) and v7 (4.0%), the two
cohorts whose own convergence previously supported a candidate false-Visit
budget -- that candidate is **withdrawn pending more evidence**, not
reaffirmed, and the useful-evidence-rate candidate (directly downstream of
the same root cause) is withdrawn alongside it. Root cause is real, not
noise: production admission stays deliberately confidence-blind by
measured decision (`roadmap.md` "Numeric release budgets" -- confidence
gating was swept against real reviewed data and explicitly not adopted),
so a scene with a recurring weak-signal location pays a real, now-quantified
cost under that design. Gate B's own abstention behavior held cleanly
throughout despite this -- **zero confidently-wrong species labels on any
false Visit** -- the accepted Background/Empty Evidence Species-Confidence
Correctness v1 fix continues to hold under the largest real test it has
yet received. This same rigorous pixel-level check also **reversed the
session's own initial working hypothesis**: the cleanest-looking
concurrent-multi-subject signature found this session (Visits 010/011 --
identical start offset to the millisecond, shared `event_id`, clearly
disjoint bounding-box positions) turned out, on direct pixel inspection,
to be two independent false detections, not two birds -- disclosed
explicitly as a methodological finding (structural/temporal concurrency
signals alone are not sufficient proof of genuine crowding) rather than
quietly corrected. A second candidate pair (Visits 021/022, materially
higher confidence, same shared-Event structural signal) remains the
session's best 2-subject evidence but falls outside the acceptance
recorder's own coverage window (which itself stopped at ~99.4 of the
session's 158.2 minutes, cleanly, on reaching its own configured 4GB byte
bound -- a disclosed, self-inflicted, non-product coverage shortfall, not
a product regression; product-side Observation Engine continuity was
~100%, zero reconnects logged, zero errors in the live session itself) and
so could not be additionally visually confirmed. No 3+-subject moment was
observed. Recall: the one exhaustive-denominator window reviewed (0-5.0
minutes, all 23 track generations individually reviewed, not sampled)
found 3 of 3 genuine encounters represented (100%), with one further
confirmed-but-honestly-rejected track disclosed as ambiguous rather than
folded into either side of the ratio.

Two further concrete, bounded, same-session findings, both disclosed, not
release-blocking: an operator (not product) recorder-configuration mistake
(`MAX_BYTES` exceeding `AcceptanceRecorderConfig`'s own hard 5GB ceiling)
caused one real `500` on the first `observation/start` attempt, root-caused
immediately from the structured log's own traceback and fixed by
relaunching the already-built release with a corrected value -- zero
product code touched, and the storage-decline root cause named above,
mitigated for this session via two user-approved decisions (reusing V7's
caches; deleting its now-redundant 3.2GB recorder set after archiving its
small, critical raw ledger data first, closing part of the "v7's own raw
evidence never archived" gap Gate A Measurement Closure v1 had disclosed)
but left at only ~3.5GB free post-session, needing attention before any
near-term next session. All raw session artifacts (merged lossless
ledger, Visits export, reviewer-dispositions used to fully resolve
fragmentation, accounting reports, and the decisive pixel-crop images) are
archived to
`data/field-acceptance/2026-09-01-gate-a-v8-true-latency-crowding-tranche/`.
No production code was changed by this milestone; Core was not run per its
own explicit instruction for a no-code-change field session (identity,
schema, and product-visible results were independently validated live
instead -- see the report's own "Identity"/validation account). This
closure does **not** authorize the next Representative Field Acceptance /
Gate A session, External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. Per this milestone's own explicit instruction, Gate
A is **not** self-closed by this report -- closure requires external
(ChatGPT) review; see §6.R, below, for the complete, updated "Remaining
Gate A dependency" account, now led by the Camera Node upgrade
dependency and the reopened false-Visit-rate/useful-evidence-rate
evidence body.

**2026-09-01 update (Camera Node <-> Host RTT-Bounded Clock Calibration
v1, see §1/§6.R):** closes the absolute Node<->Host offset/error-bound gap
the accepted Camera Node -> Host Clock Normalization v1's own report
disclosed but did not solve -- that milestone's own one-way estimator
(`received_at_host - captured_at_node`) is, by construction, only ever a
one-sided upper bound on the true offset (`true_offset_ms <=
min(deltas)`), never a defensible two-sided error bound, however tight its
own observed jitter spread looks. See
[camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
for the complete record. Classification **A**. Reuses the existing `GET
/node/v1/health` request/response operation (two additive response
fields, `node_receive_time`/`node_time`) rather than inventing a dedicated
time-sync protocol, per this milestone's own explicit instruction -- a
real correction, disclosed rather than silently fixed, to the accepted
prior milestone's own "no request/response exchange exists" framing
(correct for the one-way analysis-stream push specifically, incorrectly
generalized to the whole Camera Node protocol). A rigorously-derived
two-sided offset interval (`[offset_min_ms, offset_max_ms]`, never a
symmetric-delay NTP formula) replaces the one-way estimator as the sole
input `capture_to_visible_latency.py` normalizes T0 through; the one-way
estimator itself is not discarded (its per-frame ~10-second cadence
continues, unchanged, as the *relative* drift/jump monitor that decides
when a live session spends the cost of a fresh RTT-bounded batch -- one of
four recalibration triggers: session start, a 5-minute bounded periodic
cadence, detected reconnect, or a one-way-detected jump). Every latency
sample now carries the full interval (`latency_min_ms`/`latency_max_ms`),
never only a collapsed point estimate; re-proved directly against
fallback, stop-finalization, and multi-subject-sibling scenarios, each now
asserting the interval, not only the point estimate. A real regression (a
sequential 5-attempt calibration batch against an unreachable Node
blocking a live session's own frame-processing tick for up to ~10 seconds)
was found via a genuinely failing pre-existing end-to-end test and fixed
(concurrent batch attempts; the first calibration moved off the session
-start critical path entirely, triggered instead at the first ordinary
tick). Zero Camera Node/wire-protocol breaking changes -- an old Node's
`/node/v1/health` response simply lacks the two new keys, degrading
honestly to `insufficient_samples`, never a crash. Schema unchanged
(`v58`) -- nothing here is persisted to SQLAlchemy. Tier 1 (404 passed) +
Tier 2 (670 passed, combined in one invocation) + Tier 3 (full Core gate,
run because this milestone -- unlike the accepted prior one -- adds
genuinely new runtime network I/O to the live engine loop, not merely
passive computation over already-flowing data): 5487 passed, 3 failed (all
3 independently confirmed pre-existing/unrelated by fresh baseline
bisection -- the same recurring `test_place_biodiversity_summary_
repository.py` pair this file's own history has already reconfirmed across
multiple prior milestones, plus one real-clock/local-day-boundary-sensitive
test in `test_stream_playback_contract.py` whose own 27m38s run happened
to straddle the actual local-midnight rollover into 2026-09-01), 3
skipped, 23 deselected, 11 xfailed. Zero new ruff findings (verified via
direct line-content diff against a stashed baseline, not merely a count
match). **Absolute Node<->Host clock-calibration state moves from OPEN to
CLOSED**: a defensible bounded interval now exists, with honest
degradation for poor-quality/high-RTT/mutually-inconsistent samples, and
epoch-based clock-jump invalidation extended to the new anchor type.
**True capture-to-visible latency remains MORE FIELD EVIDENCE REQUIRED,
unchanged in kind but now for a materially stronger reason a second
time**: the measurement mechanism itself is now both closed AND correct/
defensible, not merely closed; every historical cohort (2026-08-19, v6,
v7) still predates `rtt_clock_calibrations` entirely and cannot be
retroactively fixed. A next field session run against post-this-milestone
accepted HEAD would be the first able to produce a real, validly
RTT-normalized T0 -> T5 distribution. Does not reopen fragmentation
accounting, does not tune models/detectors, does not run a field cohort.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged; this closure does not authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone. **Remaining Gate A dependency, unchanged in
priority order and in every item's own substance -- only item (1)'s own
bar is now sharper a second time:** (1) real, *validly RTT-normalized*
capture-to-visible latency field samples -- the measurement mechanism is
now both closed and defensible; the samples themselves still do not
exist; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (3) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (4) the ~13 untraced
`blocked_missing_evidence` records (unchanged); (5) the already-known Gate
B admission-precision residual (unchanged). See §6.R, below, for the
complete, updated account.

**2026-08-31 update (Camera Node -> Host Clock Normalization for True
Capture-to-Visible Latency v1, see §1/§6.R):** closes the clock-domain
precondition Gate A Measurement Closure v1's own T0 -> `decided_at` figure
was silently resting on -- not a new field session (none run here), but
proof that the ~39-second discrepancy that figure's own caveat cited was
never evidence of a real Camera-Node-vs-Host wall-clock offset, and a
real, bounded, tested calibration/normalization mechanism for when one
actually needs measuring. Classification **A**; see §6.R, below, for the
complete account (root-cause re-measurement, calibration/uncertainty/
drift/clock-jump design, fallback/stop-finalization/multi-subject proof,
551 Tier 1 + Tier 2 tests, zero new ruff findings). Schema unchanged
(`v58`). Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; does not authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.

**2026-08-31 update (Gate A Measurement Closure v1 -- Fragmentation
Accounting & True User-Visible Latency Instrumentation, see §1/§6.R):**
directly closes the two measurement gaps the prior reconciliation's own
"Remaining Gate A dependency" named as items 1 and 3 -- see
[gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
for the complete record. Classification **A**. A new, explicit,
human-correctable fragmentation-disposition layer
(`fragmentation_accounting.py`) reproduces (RED) and corrects (GREEN) the
real methodology problem v7 disclosed: `cluster_encounters`'s own raw
`duplicate_visit_cluster_count` signal misreads sustained-activity
mega-clusters as fragmentation/duplication defects when every admitted
Visit inside them is a genuinely separate real encounter -- the corrected
accounting never promotes that raw signal to a disposition on its own,
staying honestly `ambiguous` absent a shared-evidence (`duplicate`) or
shared-Event-concurrent-sibling (`correctly_represented`) structural
signal or an explicit, non-empty-note-bearing reviewer override. Reran
this corrected accounting against every cohort with recoverable raw
ledger evidence -- the 2026-08-19 primary full-funnel cohort (from its own
already-tracked `data/field-acceptance/` evidence) and v6/v7 (whose own
raw counterfactual-ledger snapshots were never archived there, a disclosed
tooling-hygiene gap; recovered from the original field sessions' own
still-present local scratchpad directories, verified lossless against
each accepted report's own published counts, and archived under
`data/field-acceptance/2026-08-31-gate-a-{v6,v7}-measurement-closure-
reanalysis/` for future reproducibility). All three reanalyzable/reported
cohorts (2026-08-19, v5, v7) now converge on **0% confirmed
fragmentation** under one consistent methodology, most residual ambiguity
resolved via each cohort's own already-existing independent review (the
2026-08-19 cohort's own `independent-encounter-table.md`; v7's own
already-accepted "Multi-subject" section) rather than fresh guessing --
**fragmentation moves to READY FOR FORMAL BUDGET REVIEW**, candidate
~0%/low single digits. Separately, a full T0 (source capture) -> T5
(query-visible) production timeline was traced directly in code: T2/T3/T4/
T5 already collapse into one existing Host-domain value
(`ProposalOutcomeRecord.decided_at`) in this codebase's current
synchronous design, and T4/T5 equivalence is now *proven*, not assumed, by
a new repository-level read-after-write test; the one genuine missing
piece, T0, is now instrumented via one small, additive
`TrackGenerationRecord.start_captured_at`/`end_captured_at` field pair
(values already in scope on every `TrackUpdate`, never a new wall-clock
read), propagated through to the counterfactual-ledger API response so
future field-acceptance tooling actually receives it. Fallback timestamp
correctness (a genuine risk after the accepted v6/v7 fallback work) was
independently proven at two layers -- the new latency module and a new
persistence-boundary test on `engine_runtime.py` -- and a real ~39-second
offset-vs-wall-clock drift was found in v7's own preserved data, directly
justifying the module's explicit clock-domain-caveat design. **Capture-to
-visible latency remains MEASUREMENT CONTRACT CLOSED / MORE FIELD EVIDENCE
REQUIRED**: every historical cohort checked (2026-08-19, v6, v7) predates
the new field and honestly reports every sample `unavailable_capture_time`
-- confirmed directly, never inferred around. Schema unchanged (`v58`,
every change additive or a brand-new zero-existing-caller pure module).
Tier 1 (218) + Tier 2 (222) = 440 tests passed, 0 failed; zero new ruff
findings (verified against a stashed baseline); Tier 3 explicitly not run,
decision documented in the report (additive/narrow production-code
footprint, not warranted "solely because this is called Gate A," per this
milestone's own explicit instruction). One pre-existing, latent bug fixed
(`run_encounter_accounting.py`'s own `decided_at` was never parsed into a
`datetime` -- harmless until this milestone's own new consumer needed real
arithmetic on it), confined to an offline analysis script, never the live
admission/persistence path. Does not tune models, does not change Visit
grouping semantics, does not run a field cohort. Neither budget is
accepted here -- both are proposed for external review only. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged; this closure does not authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does not select a next development milestone. See
§6.R, below, for the complete, updated "Remaining Gate A dependency"
account.

**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche** is, as of this Post-v5 Global
Product-Roadmap Reconciliation & Gate A Next-Step Authorization milestone
(2026-08-30), the next RELEASE-CRITICAL milestone -- directly authorized
outside this file, as a bounded Lane R field-validation session, exactly
the same standing this file has already recorded for v4 and v5 each in
turn without ever changing this section's own bold statement above (see
[roadmap.md](roadmap.md) "Gate A," 2026-08-30 update, and "Numeric release
budgets" for the complete reconciled evidence state this authorization
rests on). **Not yet run.** Purpose: exactly the "Remaining Gate A
dependency" Representative Daylight Gate A Field Acceptance v5's own
report named -- a second post-fix daylight cohort, for replication and
closure evidence, not product tuning. Prefer a cohort that exercises
genuinely simultaneous multi-subject activity (the one dimension v5 could
not exercise at all: real simultaneous presence was confirmed in-scene,
but no two Visits shared an Event as concurrent siblings), because that
remains materially under-evidenced; a sparser single-subject replication
is also useful and an acceptable substitute if multi-subject conditions
do not naturally occur. Contract:

- no product/perception/admission/Visit/evidence/classification tuning
  while measuring -- the accepted build is measured unchanged, exactly as
  v4/v5 measured it;
- representative real daylight conditions required, directly checked (a
  dedicated pre-flight scene check, matching v5's own method) before
  committing to a long session -- if conditions are not representative,
  stop rather than contaminate the evidence body; no requirement to force
  unsuitable conditions merely to complete the cohort;
- genuinely simultaneous multi-subject admission/arbitration is a
  priority evidence target, sought, not artificially manufactured;
- sustained-activity admission behavior and stop-finalization behavior
  remain under observation -- confirm no regression, not merely re-prove
  the fix once more;
- duplicate-Visit and fragmentation checks remain required, matching
  every prior cohort's own accounting;
- an independently retained denominator/evidence accounting (the
  established acceptance-recorder + counterfactual-ledger method) is
  required, matching v4/v5's own methodology;
- honest abstention remains acceptable -- no requirement to produce a
  specific species count or a specific outcome;
- this milestone measures; it does not fix. Per this project's own
  established field-acceptance bar, any defect found (including a further
  instance of the already-disclosed Gate B background-evidence/
  confident-label liability, below) is root-caused and disclosed, not
  necessarily fixed in the same milestone.

This reconciliation does **not** authorize External Pre-Release
Acceptance or Final Release Hardening -- current evidence does not yet
support either. It does not itself run the field session, and does not
select any other next development milestone. Gate A/Lane R remains open
(§6.R, below). Two budget dimensions -- minimum monitoring coverage
(~99%) and minimum useful-evidence rate (~85%) -- are reconciled to
**READY FOR FORMAL BUDGET REVIEW** (candidate values proposed across all
four real cohorts to date, not yet formally accepted release budgets --
see [roadmap.md](roadmap.md) "Numeric release budgets"); recall,
false-Visit rate, fragmentation rate, and capture-to-visible latency
remain evidence-accumulated only, with no candidate value yet proposed.
No numeric recall budget or claim is introduced by this reconciliation --
v5's own qualitative "no missed genuine encounter found via targeted, not
exhaustive, review" conclusion is preserved exactly as reported, not
converted into a recall percentage. The known Gate B liability carried
forward unresolved: weak/spurious detections can still yield background
evidence that BioCLIP labels with a confident (wrong) species name,
reproduced fresh by v5 (a "Brown Thrasher," 89.9%, on confirmed empty
lawn/background) -- a known, already-`roadmap.md`-named regression class,
not a new v5 blocker, not release-blocking for Gate A directly, and
explicitly not to be fixed opportunistically inside v6.

**2026-08-30 update (Background / Empty Evidence Species-Confidence
Correctness v1, see §1, above):** the specific v5 instance of this
liability named directly above is now fixed -- a new geometry-
corroboration eligibility check (reading already-persisted Localization
Attribution / Detection Geometry Lineage v1 facts, schema unchanged)
withholds an automatic species claim on a crop whose own box does not
correspond to a real, contemporaneous detector observation, proven
RED->GREEN against the real production path and real-cohort validated.
Honestly bounded, not a full close: a detector-sourced-but-still-wrong
background crop (a genuinely confident, contemporaneous, but recurring or
otherwise misleading detector hit) remains an open, disclosed Gate B
residual, unchanged by this fix -- see the milestone's own report and
`roadmap.md` Gate B for the complete accounting. This closure does not
alter the Gate A v6 contract above in any way -- v6 remains authorized,
not yet run, exactly as already stated -- and does not itself authorize
Gate A v6 execution, External Pre-Release Acceptance, or Final Release
Hardening. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged.

**2026-08-31 update (Representative Daylight Gate A Field Acceptance v6 --
Post-Fix Replication & Multi-Subject Tranche, see §1/§6.R):** v6 has now
run, at classification **B**, not A. A real, live 106.63-minute
Observation session against the real reference Camera Node directly
confirmed the *specific* Sustained-Activity starvation mechanism v4 found
does not recur -- arbitration reached a decision for every ambiguous
component on schedule throughout -- but `candidates_created` ended the
session at zero anyway, despite two independently-confirmed, real,
sometimes-simultaneous-multi-subject activity segments, root-caused to a
different, precisely source-traced mechanism: an arbitration winner can
still fail at the downstream evidence-availability gate (the bounded
128-entry evidence-byte cache), with no retry/fallback to a runner-up, so
the component's real activity is permanently lost. This is a concrete
field measurement of a risk already named (not fixed) when that cache
bound was last raised, not a new defect class -- but a materially sharper
one than existed before (48/263 distinct proposals, 18.3%, this session,
versus v5's own 2.8%). See the milestone's own report for the complete
account, including two bounded, tested, own-session deploy-tooling fixes
(zero product/perception code touched) and the full honest-gap accounting
for the dimensions zero admissions made unexercisable this session
(background/empty-evidence eligibility, species assistance, useful-
evidence rate, false-Visit rate, fragmentation). This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. Authorization remains **NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. No budget
dimension moves to READY FOR FORMAL BUDGET REVIEW this update, and no
existing candidate (monitoring coverage, useful-evidence rate) is
withdrawn -- this session neither confirms nor refutes either, having
produced zero admitted Visits to measure a useful-evidence rate over, and
having measured monitoring coverage (~99.4%) consistent with the existing
candidate. Gate A/Lane R remains open, and this update reopens rather than
narrows the "Remaining Gate A dependency" picture -- see §6.R, below, for
the complete account, now led by the evidence-cache-exhaustion/no-fallback
mechanism this session concretely measured.

**2026-08-31 update (Pending-Proposal Evidence Preservation & Arbitration
Fallback Correctness v1, see §1/§6.R):** the evidence-cache-exhaustion/
no-fallback mechanism v6 concretely measured immediately above is now
fixed, at classification **A** -- see
[pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
for the complete record. Bounded, pending-proposal-aware preservation
(protects a bounded, per-tick-recomputed set of still-actionable
proposals' priority evidence from the shared cache's own eviction) and
deterministic same-component fallback (walks a resolved component's
winner then its own remaining stable members, in arbitration's own
existing rank order, if the winner cannot actually be admitted) were both
implemented and independently tested, per this milestone's own governing
brief's explicit requirement for both mechanisms. The unchanged 128-entry
cache bound was deliberately *not* raised a fourth time. Two real design
corrections were found and fixed during implementation and this
milestone's own adversarial self-review -- see the report's own
"Preservation contract"/"Fallback contract" sections for the complete
account, including one (an iteration-order-dependent double-attempt bug)
found only by self-review, after tests were already passing, and locked
in by a dedicated permanent regression test before this milestone
concluded. Deterministically reproduced against real production logic
(both required RED reproducers, plus a 105-simulated-minute v6-shaped
replay against the real bounded cache, all confirmed genuinely RED on
accepted `b37656d` and GREEN after the fix). Tier 1 187/187, Tier 2
279/279, Tier 3 (one full Core run) 5357/5372 passed (3 skipped, 11
xfailed), 1 failed and independently confirmed unrelated (a pre-existing
timing-sensitive flake in `test_temporal_capture_cli.py`, made visible
only by this investigation's own necessary four-way concurrent chunked
Core execution -- zero code-dependency relationship to any file this
milestone touched, passes on baseline, passes 5/5 in isolation with the
fix in place). No schema change. This is nighttime/implementation
correctness work only, per this milestone's own explicit non-goal -- no
field session was run, and this closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. Gate A/Lane R
remains open -- see §6.R, below, for the updated "Remaining Gate A
dependency" account and this milestone's own report, "Next field proof
required," for exactly what the next daylight cohort must prove (chiefly:
non-zero in-session admissions under sustained activity that this fix's
own deterministic proof cannot itself provide -- field confirmation
remains outstanding).

**2026-08-31 update (Representative Daylight Gate A Field Acceptance v7 --
Evidence-Preservation / Arbitration-Fallback Re-Proof, see §1/§6.R):** the
field confirmation the pending-proposal fix's own report named as
outstanding immediately above is now provided, at classification **A** --
see
[representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
for the complete record. A real, live 89.4-minute Observation session
against the real reference Camera Node (the identical physical camera
v4/v5/v6 used) directly confirms the fix under genuine field conditions:
`candidates_created` reached 25 in-session (first admission ~6.6 minutes in,
growth throughout, not concentrated at stop) -- reversing v6's own zero and
exceeding v5's own 19. Six real, natural fallback attempts occurred (five
admitted, one honestly exhausted), three fully reconstructed end to end
(component members, canonical ranking, why the winner failed, fallback
position, admitted evidence, species outcome); zero instances of the
unacceptable "component silently discarded while a viable member exists"
outcome were found anywhere directly traced. `blocked_missing_evidence`
materially reduced (18.3% -> 9.4%, roughly halved). Genuine concurrent
multi-subject admission was directly visually confirmed for the first time
across any Gate A cohort (two independent sibling-Event pairs, one requiring
the fallback mechanism simultaneously) -- the other dimension the prior
reconciliation's own "Remaining Gate A dependency" named as still open. One
bounded, tested, own-commit deploy-tooling defect was found and fixed along
the way (a WSL/Windows path-conversion bug that left the independent
acceptance recorder silently unarmed for a discarded ~2m26s preliminary
session, before the formal session this report measures) -- zero product/
perception/admission/Visit/evidence/classification code touched. All 25
admitted Visits individually reviewed against real recorder frames: 96.0%
useful-evidence rate, one confirmed real false Visit (empty background,
correctly given no species label), zero genuine duplicate Visits (zero
shared tracker evidence across all 25 admissions -- the strongest test
applied to date). Honestly disclosed, not blocking: a concrete field
instance of the already-named, not-yet-benchmarked crowded-feeder/NMS gap (a
third simultaneous bird the detector never separately perceived); ~13
`blocked_missing_evidence` records outside this session's own two
exhaustive-denominator windows remain individually untraced; fragmentation-
rate and true user-visible latency remain evidence-accumulated only. Two
further budget dimensions move to **READY FOR FORMAL BUDGET REVIEW**
(maximum false-Visit rate, candidate ~5-10%; maximum duplicate-Visit rate,
candidate ~0%/low single digits), alongside the two already-proposed
dimensions this session's own measurements strengthen (monitoring coverage,
useful-evidence rate) -- see "Numeric release budgets" in
[roadmap.md](roadmap.md) for the still-current reconciled accounting, not
itself updated by this milestone per its own governing brief's explicit
scope (release-execution-state.md only). This closure does **not** authorize
External Pre-Release Acceptance or Final Release Hardening, and does **not**
select a next development milestone -- authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. Per the
milestone's own explicit instruction, Gate A is **not** self-closed by this
report -- closure requires external (ChatGPT) review of the accumulated
evidence; see §6.R, below, for the complete, updated "Remaining Gate A
dependency" account.

Representative Daylight Gate A Field Acceptance v5 (directly authorized
outside this file, as the next RELEASE-CRITICAL field-validation session
for the accepted, frozen Sustained-Activity Visit Admission Starvation &
Stop-Finalization Correctness v1 fix) is now accepted at classification
**A** -- see §1, above, §6.R, below, and
[representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
for the full record. This closure does not change this section's own
bottom-line authorization, which remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED** exactly as it did before it -- this milestone
was not self-authorizing, and does not authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening. Gate A/Lane R remains open; the field session
this milestone ran real-world-confirms the accepted fix works end-to-end
under sustained genuine activity (see §6.R for the complete evidence) but
does not itself declare Gate A passed, propose an accepted numeric
release budget, or select a next development milestone.

Lane C Sparse-State Honesty & First-Hour Narrative Closure v1 (directly
authorized outside this file, as a bounded, HIGH-RELEASE-VALUE
product-correctness milestone closing the two remaining bounded DEV gaps
an accepted read-only Lane C reconciliation had left open) is now accepted
at classification **A** -- see §1, above, Lane C/§6, below, and
[lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md)
for the full record. This closure does not change this section's own
bottom-line authorization, which remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED** exactly as it did before Ongoing Monitoring
Failure Diagnostics for RTSP / Local USB / Windows DShow v1 below --
neither milestone was self-authorizing, and neither authorizes the next
Representative Field Acceptance / Gate A session, Lane G validation,
provider integrations, External Pre-Release Acceptance, or Final Release
Hardening.

Ongoing Monitoring Failure Diagnostics for RTSP / Local USB / Windows
DShow v1 (directly authorized outside this file, as a RELEASE-CRITICAL
milestone closing Lane G's own remaining, previously-disclosed
ongoing-monitoring generic-collapse gap) is now accepted at
classification **A** -- see §1, above, Lane G/§6, below, and
[ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `b1c78dc`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly, as did Lane G's own stated `PARTIAL, MATERIALLY CLOSED`
status and the exact gap description. Root-caused against every one of
the governing brief's own ten stderr/process-lifecycle diagnostic
questions before any fix. A bounded, continuous `BoundedStderrDrain`
(new, `playback/stderr_drain.py`) replaces the previously-unconditional
`stderr=subprocess.DEVNULL` on the three non-Camera-Node providers' own
long-running monitored processes, proven safe against a real
~4MB-stderr-flood subprocess (no deadlock, bounded memory, no blocked
frame delivery) and against ten repeated start/stop cycles (no thread
leak). RTSP ongoing classification reuses the exact, unmodified,
already-accepted setup-time vocabulary (`classify_rtsp_failure_text`,
renamed public from `_classify_probe_failure`); local USB/Windows
DirectShow gained new classifiers strictly bounded to real, reproducible
evidence gathered this milestone (real ffmpeg 6.1.1 V4L2 stderr against
this project's own Linux dev sandbox; real ffmpeg.exe 8.1.2 DirectShow
stderr gathered live against the project's own reference Windows dev
host), with an honest generic fallback everywhere real evidence ran out
-- no false precision invented for either provider, per the brief's own
explicit bar. Two independent hardcoded Camera-Node-only allowlists
(`_managed_camera_status`; `mark_monitoring_backoff_with_failure_code`)
that discarded any other provider's classified code were widened, not
duplicated; Camera Node's own separate mechanism is completely untouched.
Recovery-clears-stale-failure was re-verified correct for the new codes
against a real repository, with zero change to the pre-existing,
provider-agnostic clearing mechanism itself or to any retry/backoff
timing. 26 new tests, Tier 1 26/26, Tier 2 (20 files) 503 passed/11
xfailed/0 failed, Tier 3 (one full `scripts/verify_core.py` run) 5310
passed/3 skipped/23 deselected/11 xfailed/**0 failed** -- no bisection
needed. `ruff check`: zero new findings on every touched/new file,
confirmed via clean-baseline bisection. No schema change. Local USB/
Windows DirectShow hardware acceptance (device-busy, permission-on-real-
hardware, unsupported-format) and a real RTSP camera's own live auth/
codec failure remain genuinely untested -- honestly disclosed, not
claimed. Lane G moves to **MATERIALLY CLOSED / VALIDATION REMAINS** (§6,
below). This closure does **not** authorize the next Representative Field
Acceptance / Gate A session, Lane C work, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- authorization returns to the bold statement
immediately above, unchanged by this closure.

Login Rate-Limiting & Authentication Abuse Resistance v1 (directly
authorized outside this file, as a RELEASE-SECURITY milestone closing the
human-login rate-limiting gap the full remaining-roadmap reconciliation
pass itself had verified was still open) is now accepted at classification
**A** -- see §1, above, and
[login-rate-limiting-authentication-abuse-resistance-v1-report.md](login-rate-limiting-authentication-abuse-resistance-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `a846655`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly. `POST /api/auth/sign-in` previously had generic,
enumeration-safe failure behavior but no attempt counting, no delay, and no
throttling at all; pairing already had its own rate limiting
(`mockingbird_node.app`'s `_MAX_PAIR_ATTEMPTS`), human login did not. Fixed
with a small, dependency-free `LoginRateLimiter` (account- and source-keyed,
jointly evaluated, a short fixed delay ladder that plateaus at 60 seconds
forever -- no permanent lockout), deliberately in-memory only (resets on
restart/backup-restore, matching this codebase's own established precedent
for that boundary; a local-first appliance does not need persistent
lockout state, and persisting it would become its own DoS surface). The
outward HTTP contract is unchanged -- the identical generic `401` for
unknown user, wrong password, disabled user, and now throttled account/
source alike, proven by a direct response-equality regression test. No
session is ever created on a failed or throttled attempt; three new
bounded audit events reuse the existing audit-log mechanism with zero
schema change and no secret ever in their metadata. 31 new tests, plus
36 pre-existing identity tests re-confirmed passing unmodified. Tier 1 (67
tests): zero failures. Tier 2 (376 tests across 26 files spanning every
directly auth-adjacent file plus a broad, diverse cross-subsystem sample):
zero failures. Tier 3 deliberately not run -- the change is confined to
one repository method, one endpoint, and one new file with zero existing
importers, and Tier 2's own breadth is itself empirical confirmation of
that narrow blast radius. `ruff check`: zero new findings (the 57
pre-existing `product_repository.py` findings confirmed unrelated via a
direct clean-baseline bisection). No schema change. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, Lane G monitoring diagnostics, Lane C work, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- authorization returns to the bold statement
immediately above, unchanged by this closure.

Historical Species-Status ("New" vs. "Seen Before") Correctness v1
(directly authorized outside this file, as a release-critical correctness
milestone closing two reproduced, multiply-recurring `tests/test_place_
biodiversity_summary_repository.py` failures the global reconciliation pass
itself surfaced -- reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, and
[historical-species-status-new-seen-before-correctness-v1-report.md](historical-species-status-new-seen-before-correctness-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `98f1138`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly. Root-caused before fixing, per the governing brief's own
ten diagnostic questions: both failures trace to one test-fixture defect
(a hardcoded past `NOW` constant colliding with two intentionally
real-wall-clock-anchored "live view" HTTP routes -- `place_biodiversity_
summary`/`wildlife_journal_history`, neither of which accepts a way to
inject a test clock, by design), never to the shared canonical
`compute_species_historical_statuses`/`_historical_place_baseline_and_
species_statuses` computation itself, which was independently re-verified
correct against its own governing contracts and against every `now=`
-pinned assertion in the same test file, all already passing. Fixed with
the smallest correct change: one test file, zero production code, zero
schema change. Both reproduced failures independently proven RED pre-fix
and GREEN after; every required semantic case (first occurrence, subsequent
occurrence, correction to a new species, correction to a previously-seen
species, current-Visit self-exclusion, future-Visit non-retroactivity,
archived-Stream/Place isolation, unresolved-label exclusion, cross-endpoint
agreement) independently proven, two of them by new tests this milestone
added. Tier 1/2 (498 tests across every consumer of the shared
historical-status path): zero failures. Tier 3 (one full Core run): 5277
passed, **zero failed** -- the first zero-failure full Core checkpoint in
at least nine consecutive prior attempts (see §14, below). This closure
does **not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not edited
-- this milestone is a bounded test-correctness fix, not a roadmap-scope
change. No evidence surfaced that Lane C itself requires a separate
reconciliation pass beyond what §6 already records; its own remaining "New
/ Regular presentation" item is a distinct UX-presentation gap, untouched
by this purely computational-truth/test-correctness fix.

Release Licensing, Distribution & Third-Party Legal Closure v1 (directly
authorized outside this file, as a pre-release-decision/release-blocking
governance milestone -- Lane P plus the still-open BirdNET
commercial-adjacent posture in §2, above -- the highest-priority
independent milestone available while Gate A's own daylight-conditions
rerun (Lane R) stays separately blocked, confirmed via this milestone's
own hard sequencing guard before starting) is now accepted at
classification **B** -- see §1, above, Lane P/§2, and
[release-licensing-distribution-third-party-legal-closure-v1-report.md](release-licensing-distribution-third-party-legal-closure-v1-report.md)
for the full record. Resolved both engineering-resolvable items Lane P
had left open (FFmpeg's distribution posture -- never bundled, now a
durably-enforced guard, `verify_no_bundled_ffmpeg_binary` -- and a new
`THIRD_PARTY_NOTICES.md` shipping correct MIT license text for the two
production-redistributed models, MDv5a and BioCLIP-2, that previously
carried none), re-verified the pre-existing BirdNET-weight-exclusion
enforcement still works unchanged, found and fixed one real documentation
gap (the canonical user guide never mentioned the shipped, accepted
BirdNET/acoustic feature at all), and produced a complete owner decision
packet for the one item that genuinely cannot be resolved by engineering
means alone: MockingBird's own source-code license (MIT recommended, no
other engineering ambiguity blocking it). Classification **B**, not A,
because that one owner decision remains outstanding and remains a real
release blocker for the public launch itself -- see this milestone's own
report for the complete reasoning against self-selecting it. This closure
does **not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone -- see the bold
statement immediately above, unchanged by this closure.

Platform / Runtime Portability & Support Truth Closure v1 (directly
authorized outside this file, as a bounded, release-critical evidence/
documentation closure of Lane O -- the highest-priority independent
task available while Gate A's own daylight-conditions rerun stays
separately blocked) is now accepted at classification **A** -- see §1,
above, Lane O, §6, below, and
[platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md)
for the full record. Confirmed the sequencing premise before starting:
Lane O read as `PARTIAL -- RELEASE DECISION REQUIRED` and release-critical,
Lane R correctly still gated on daylight field conditions and unrelated,
and no higher-priority independent release-critical dependency blocked
Lane O -- the premise held, so the milestone proceeded rather than
stopping. Built a truthful, explicit support matrix across Host OS
(Windows validated; Linux structurally supported at the source/dev level,
no packaged release; macOS unverified, one path already honestly
unsupported), inference runtime (CPU: the accepted detector forbids it by
deliberate, tested design, zero fallback; NVIDIA CUDA validated on
Windows; Apple Silicon deferred; AMD unsupported), and Camera Node
(Raspberry Pi 4 validated reference hardware; genuinely hardware-agnostic
provider protocol; no non-Pi hardware release-tested) -- entirely by
reusing already-accepted evidence plus bounded, targeted code/doc
archaeology, with zero new platform support added, per the milestone's own
explicit non-goals. Found and fixed two narrow, reproduced capability-
overclaim defects in `python -m mockingbird doctor` (its
`SPECIES_IDENTIFICATION` and `GPU_CUDA` checks each silently omitted an
honest scope caveat their own underlying probes already had available),
each independently proven RED via `git stash` against the real pre-fix
code and GREEN after, with a new dedicated regression test;
`tests/test_doctor.py` (107 passed) and `tests/test_doctor_cli.py` (8
passed) confirmed via direct grep to be the complete blast radius; `ruff
check` clean; full Core correctly not run for this primarily evidence/
documentation closure, per the governing brief's own validation guidance.
Two further gaps were found and precisely disclosed rather than fixed,
since neither is reproduced against any real or currently-shipping path
(a Camera Node `Path.home()` fallback masked by installer convention; a
dead-code API-endpoint naming mismatch with zero frontend consumption).
Published the canonical, plain-language user-facing support matrix as a
new "Platform & hardware support" section in `docs/using-mockingbird.md`.
No schema change. Lane O is now reconciled to **closed** (§6, below) --
resolved by making support truth explicit, not by claiming any
unsupported hardware is supported. This closure does **not** authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone -- see the bold statement immediately
above, unchanged by this closure.

Sustained-Activity Visit Admission Starvation & Stop-Finalization
Correctness v1 (directly authorized outside this file, as a
release-critical correctness milestone closing exactly the defect class
Representative Daylight Gate A Field Acceptance v4 found and disclosed,
below) is now accepted at classification **A** -- see §1, above, Lane R,
§6, below, and
[sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
for the full record. Both the continuous-activity starvation and the
stop-finalization questions the prior milestone left open are
independently root-caused, deterministically reproduced RED against the
real, unmodified pre-fix code, and fixed -- plus two further real,
narrow, evidence-cache-adjacent defects this milestone's own required
investigation found and closed along the way (see the report's own
"Root cause" section for the complete four-part account). This closure
does **not** authorize External Pre-Release Acceptance or Final Release
Hardening, and does **not** select a next development milestone -- see
the bold statement immediately above, unchanged by this closure.
`roadmap.md` was not edited: this milestone is a bounded correctness fix
confined to the Observation Engine admission/evidence-scoring stack, not
a roadmap-scope change, and per its own governing brief only
`release-execution-state.md` is updated on acceptance (accepted HEAD;
schema unchanged; latest accepted milestone; Gate A defect state;
validation state; exact daylight rerun requirement) -- the already
-closed Lanes M/N/Q are untouched. This closure does **not** itself close
Lane R/Gate A (no live field session ran, per this milestone's own
explicit non-goal) and does **not** authorize the next daylight session
by itself -- that remains its own separate authorization decision, per
the bold statement above.

Representative Daylight Gate A Field Acceptance v4 (directly authorized
outside this file, as a release-critical field-evidence milestone) is
now accepted at classification **A** -- see §1, above, Lane R, §6,
below, and
[representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
for the full record. This closure does **not** authorize External
Pre-Release Acceptance or Final Release Hardening, and does **not**
select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not
edited: this milestone is a bounded field-measurement session, not a
roadmap-scope change, and per its own governing brief only
`release-execution-state.md` is updated on acceptance (accepted HEAD;
schema; latest accepted milestone; Lane R/Gate A evidence state;
candidate-budget state; exact remaining dependency) -- the already-
closed Lanes M/N/Q are untouched. The real, previously-undocumented P0
this session found and precisely root-caused (sustained near-continuous
multi-subject activity can produce zero admitted Visits for an entire
live session -- see §1, above, and the report itself for the full
mechanism) is a genuine addition to Gate A's remaining-work picture, not
a milestone-invalidating problem with this session's own execution.

Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1
(directly authorized outside this file, as a bounded release-critical
acceptance milestone closing the two specific gaps Local Only / Privacy
Closure v1's own classification B left open, reconciled here at its own
closure) is now accepted at classification **A** -- see §1, above, Lane N,
§6, above, and
[native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md)
for the full record. Confirmed the starting-state discrepancy before
proceeding: this file's own text (post the prior milestone's own
reconciliation) already said Lane N "closed," while the governing brief
for this milestone stated -- correctly, per ChatGPT's actual acceptance
review of that same prior report -- that two material proofs remained
(native-Windows packaged runtime; assets-present MDv5a/BioCLIP-2 operation
under internet denial). Treated the brief's framing as authoritative,
proceeded to actually close both gaps with real evidence rather than
treating the discrepancy as a stop-and-report contradiction, per the
brief's own explicit resolution of it. Both gaps are now closed for real:
a fresh, disposable, no-skip-flags native-Windows packaged deployment
(never the operator's long-lived dev identity); a real, disposable,
process-level internet-denial mechanism (the only kind available without
an Administrator token in this environment, independently corroborated by
live OS-level connection accounting and by the same mechanism catching a
real browser's own unrelated background traffic); both production models
proven initializing and running real local inference at the exact
production code path, both before and after denial, with independently-
confirmed zero network activity; a real offline browser render; all 16
named core workflows exercised live, including a real backup and a real
review correction; both live optional-provider drills degrading
gracefully with no retry storm; and the camera-credential-at-rest question
resolved to a documented non-defect. Zero reproduced Local Only/privacy
defects were found across either milestone -- this milestone changed zero
production code, adding only its own report. This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not
edited -- this milestone is a bounded acceptance/correctness closure
confined to native-Windows/privacy verification, not a roadmap-scope
change.

Local Only / Privacy Closure v1 (directly authorized outside this file,
as a bounded release-critical privacy/product-correctness milestone,
reconciled here at its own closure) is now accepted at classification
**B** -- see §1, above, Lane N, §6, below, and
[local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)
for the full record. Confirmed the sequencing premise before starting
(Lane N still open/release-critical/independent; no higher-priority
independent release-critical dependency blocks it; Lane R/Gate A still
correctly gated on representative daylight conditions, unrelated). Proved
the Local Only contract with real evidence rather than code inspection
alone: a genuine OS-level, unprivileged network namespace
(`unshare --net --map-root-user`) hosting a fresh disposable instance
with no internet route at all (loopback confirmed working via a real
"connection refused," not merely "everything fails the same way") --
22 core authenticated API routes, the frontend document, a hashed asset,
Observation start/stop against the seeded demo Stream, a real local
backup, and two deliberate optional-provider-failure drills (weather,
iNaturalist taxonomy lookup, both explicitly enabled and forced
unreachable) all completed correctly with zero outbound connection
required, zero retry storm, zero mislabeled health. A fresh, separate,
live LAN-reachability check immediately afterward confirmed the same
sandbox that just proved zero internet dependency can still reach the
project's real reference Camera Node over LAN, directly evidencing
(rather than only asserting) the offline-vs-LAN-local distinction the
governing brief required. Zero reproduced Local Only/privacy defects
were found -- this milestone changed zero production code; its own new
test file (`tests/test_local_only_privacy.py`, 8 tests, self-verified via
call-count assertions on injected fake requesters) converts the live
proof into a standing, hermetic regression, including a trip-wire against
any future undisclosed telemetry/analytics dependency ever being
declared. Classification **B**, not A, because this session's own
runtime acceptance ran the Linux/WSL dev checkout rather than the
packaged native-Windows artifact end users receive, and exercised the
model-assets-absent path rather than assets-present -- both named
explicitly in the report's own "Remaining risks," not because any defect
was found or is suspected. Lane N is now reconciled to **closed** (§6,
below): the contract is proven and every reproduced-defect requirement is
vacuously satisfied by real runtime acceptance (not static inspection
alone), matching the governing brief's own stated precondition for
closing it on that basis. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- see the bold statement immediately above,
unchanged by this closure. `roadmap.md` was not edited -- this milestone
is a bounded acceptance/correctness closure confined to privacy/network
-dependency verification, not a roadmap-scope change.

Retention Correctness & Bounded Cleanup Closure v1 (directly authorized
outside this file, as a small, bounded, release-critical follow-up to
Storage / Retention / Disk-Pressure & Recovery Closure v1, reconciled
here at its own closure) is now accepted at classification **A** -- see
§1, above, Lane M, §6, below, and
[retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md)
for the full record. Closes all three reproduced retention defects
Storage / Retention / Disk-Pressure & Recovery Closure v1 disclosed and
deliberately left unfixed under its own bounded time budget (imported/
folder-imported media over-retention against its own documented
contract; a `"staging"`-batch purge-path gap; a cosmetically-misnamed,
actually-unbounded `storage_cleanup_history` constant) -- see §1, above,
for the complete accounting of each fix, its RED/GREEN proof, and full
Tier 1/2/3 validation (zero regressions attributable to this milestone,
directly confirmed rather than assumed). Lane M is now reconciled to
**closed** (§6, below): the retention contract this file's own prior
entry called "materially closed, not fully closed" pending exactly these
three fixes is no longer ambiguous -- each of the five governing
questions the imported-media contract raised (which imported media is
retainable indefinitely vs. eligible under ordinary retention; whether
Reviewed truth implies indefinite evidence preservation or only product
truth preservation; whether user-imported originals are distinguished
from derived evidence in the data model; whether the current behavior was
explicitly contradicted by existing docs/tests) was answered directly
from code, traced and cited precisely, not inferred or guessed, and each
fix was proven RED before GREEN against a dedicated, deterministic
reproducer before being applied. The one remaining, already-disclosed,
structural storage gap -- no code anywhere scans the media directory and
cross-references it against the DB, so a file with no DB owner is
permanently invisible to every existing integrity/retention check -- is
real, bounded, low-materiality (per the prior closure's own
investigation), unaffected by this milestone, and was deliberately not
reopened, per this milestone's own governing brief; it remains a
reasonable candidate for a future bounded "sampled orphan sweep," not a
reason to withhold closing Lane M over these three specific, now-closed
defects. This closure does **not** authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone -- see the bold statement immediately above, unchanged by this
closure. `roadmap.md` was not edited -- this milestone is a bounded
correctness closure confined to retention/import cleanup code, not a
roadmap-scope change.

Storage / Retention / Disk-Pressure & Recovery Closure v1 (directly
authorized outside this file, as a bounded release-critical storage/
reliability milestone, reconciled here at its own closure) is now accepted
at classification **B** -- see §1, above, Lane M, §6, below, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
for the full record. Determines, with real directly-measured evidence, the
cause of the Windows Host free-space decline this file's own 2026-08-28
Lane R entry (below) first surfaced and left open: **disposition B**
(MockingBird development/test-artifact accumulation -- `deploy_windows_
dev.py`'s own never-garbage-collected runtime/model cache, 38.5GB, the
single largest consumer found anywhere in the investigation, plus the
field-acceptance recorder's own real output directory, 11.5GB -- together
accounting for roughly 72% of the exact dated decline window; neither path
is reachable by a real end-user installation). The dominant contributor is
fixed (`--gc-cache`, applied live against the real Windows dev host). This
closure classifies **B**, not A, because the remaining ~28% of the exact
decline window was not individually attributed to a single further cause
(disclosed honestly rather than forced to round), and because three real,
precisely-disclosed, safe-direction product-side retention findings
(imported-media over-retention against its own documented contract; a
`"staging"`-batch purge-path gap; a cosmetically-misnamed, slowly-
unbounded `storage_cleanup_history` constant) were deliberately left
disclosed rather than fixed under this milestone's own bounded time
budget, each requiring either new test coverage this milestone did not
build or a change to the highest-stakes retention-eligibility code this
milestone judged not warranted without it. This closure does **not**
itself authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone. `roadmap.md` was not
edited -- this milestone is a bounded investigation/dependency-tooling fix,
not a roadmap-scope change.

Non-Interactive Field Acceptance Authentication & Session Access v1
(directly authorized outside this file, as a bounded release-critical
security/correctness dependency milestone -- not a product capability,
reconciled here at its own closure) is now accepted at classification
**A** -- see §1, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record. Closes the recurring field-acceptance authentication
blocker Lane R's own three most recent attempts (2026-08-25, 2026-08-26,
2026-08-28, all recorded below) hit, without an authentication bypass,
without the operator's personal credentials, and without weakening
production security -- see §1, above, for the complete accounting
(mechanism, schema change, real live proof against a disposable isolated
instance, full Tier 1/2/3 validation). This closure does **not** itself
authorize the next Representative Field Acceptance / Gate A session --
that session is still gated on the same global product-roadmap
reconciliation this file's own governing phase label protects (see
"CURRENT PHASE," above) -- and does **not** authorize External Pre-Release
Acceptance or Final Release Hardening. The next daylight Gate A session,
whenever separately authorized, needs exactly one new step before it
starts: an Administrator (the operator) runs, once, against the real
instance, `python scripts/manage_field_acceptance_credential.py create`,
then exports the printed token as `MOCKINGBIRD_ACCEPTANCE_TOKEN` -- no
further auth archaeology should be needed for that session. `roadmap.md`
was not edited -- this milestone is a bounded dependency fix, not a
roadmap-scope change.

Representative Daylight Field Acceptance & Gate A Evidence v2 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **B** -- see §6 Lane R, below, and
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md)
for the full record. Accepted HEAD is unchanged (`80e1bb3`) -- this
milestone touched zero product/perception/admission/Visit/evidence/
classification/schema code; it only ran and cleanly stopped a fresh
Windows dev deployment of the already-accepted build for verification.
This does **not** close Lane R/Gate A: no live field session ran. Unlike
the two immediately-preceding attempts, every environmental and
infrastructure precondition (daylight, reference Camera Node health, GPU/
detector health, storage headroom, acceptance-recorder readiness) was
independently re-confirmed healthy this time -- the sole remaining
blocker, isolated more precisely than either prior attempt could isolate
it, is the identical authentication precondition first found 2026-08-25
(real sign-in required on every session-relevant endpoint, empirically
re-confirmed today via `401` on `GET /api/streams`/`GET /api/visits`
against the freshly redeployed accepted HEAD; no credentials exist;
standing user policy against asking again or routing around it via a
disposable instance for this class of milestone). Gate A's evidence body
is unchanged -- still exactly the two real 2026-08-19/2026-08-20 daylight
cohorts, for the third consecutive milestone attempt. No release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

Whole-Product UI / Accessibility / Performance Closure v1 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **A** -- see §1, above, Lane Q, §6, below, and
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the full record. This closes Lane Q as an integrated pass -- the
whole-product responsive/accessibility/performance/multi-camera/error-
recovery/acoustic-status evaluation this file's own Lane Q text had been
waiting on since it was first named. It does **not** authorize Lane R,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. Do NOT automatically
authorize, by adjacency to this closure: a `reviewed-product-loop.spec.ts`
rewrite (real, disclosed, precisely diagnosed as test-suite-only
staleness this milestone -- not a live product defect, not urgent); a
keyboard-driven Zone-polygon-drawing editor (real, disclosed, pre-
existing, optional/advanced-feature scope); the larger-than-previously-
documented dead-CSS cleanup or the narrow raw-exception-text hardening
(both real, disclosed P2 items, neither automatically the next milestone
by adjacency).

One-Release Roadmap & Scheduler Reconciliation v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- a documentation/state-governance milestone,
touching zero product/test/schema code. It reconciles this file and
`roadmap.md` to one coherent release doctrine: MockingBird has one public
release; there is no public "v0.1" product stage, no beta product
release, and no separate before-v1.0 roadmap phase; External Pre-Release
Acceptance (roadmap.md's Gate G, renamed from "External Beta Acceptance")
and internal release-candidate builds remain allowed as pre-launch
validation/engineering mechanics, never a separate product stage; Final
Release Hardening (Lane S, above) is readiness-triggered, not
version-number-triggered. See §1, above, and
[one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
for the complete accounting, including confirmation that no lane, gate, or
roadmap capability was added, removed, or promoted by this pass, and every
dated historical milestone title/decision label that happened to use
"v0.1"/"beta" vocabulary at the time was left verbatim. This closure does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone --
see the bold statement immediately above, unchanged by this closure.

Camera Node Upgrade & Compatibility Recovery v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, Lane L, §6, below, and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md)
for the full record, including two real defects found and fixed live
during real reference-Pi acceptance (a universal transport-path crash
under the already-accepted `ProtectHome=true` hardening, and two
automatic-recovery gaps) and one honestly-disclosed remaining reservation
(`rollback()` does not restore an already-changed systemd unit template).
This closes Lane L's one specifically-named remaining gap; it does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** reopen any other part of the
already-accepted Camera Node install/reboot/reprovision/replacement
work.

Representative Multi-Camera Field Acceptance & Release-Budget Evidence v1
(directly authorized outside this file, reconciled here at its own
closure) is now accepted at classification **B** -- see §1, above, and
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md)
for the full record. This does **not** close Lane R/Gate A -- no live
field session ran (environmental conditions, not a product defect; see
Lane R, §6) -- and does **not** authorize a next milestone by itself; it
found and fixed one narrow, unrelated release-engineering defect (a
Windows dependency-pin gap) while re-verifying execution-readiness for
the next daylight session.

Concurrent Candidate Visit Persistence Reliability v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md)
for the full record. This closes the one specific, bounded item named
below (the lost-candidate-Visit concurrent-write reliability gap); it does
**not** reopen or advance any other part of Multi-Camera Place Experience
v2's own remaining scope.

Multi-Camera Place Experience v2 (directly authorized outside this file,
reconciled here at its own closure -- see §16) remains accepted at
classification **B** -- see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
and §1/§6 Lane F, above/below, for the full record. Do NOT automatically
authorize, by adjacency to this closure: notification-level (Calm
Attention) cross-camera grouping; Place Story wildlife-event source
attribution; camera-filter UI consolidation; multi-camera Place Feature
linking; or broad multi-site -- each individually real and recorded in the
report's "Remaining major PRODUCT opportunities," none automatically the
next milestone by adjacency. (The one item this same list previously named
-- "a dedicated follow-on investigation into the real, disclosed occasional
lost-candidate-Visit concurrent-write reliability gap" -- is no longer an
open item: Concurrent Candidate Visit Persistence Reliability v1, above,
is exactly that dedicated investigation, and it reached a proven, validated
fix, not merely an investigation.)

Ecological Interoperability & Submission Workflows v1 (directly authorized
outside this file, reconciled here at its own closure -- see §16) is now
accepted at classification **B** (a real, working, submission-ready
iNaturalist workflow proven end to end by an executable 12-Visit
product-shaped scenario, plus a bounded additive Darwin Core export; eBird
and direct GBIF publication both honestly, evidence-backed deferred rather
than built -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
Calm Attention & Notifications v1 (directly authorized outside this file,
reconciled here at its own closure -- see §16) is now accepted at
classification **B** (a real canonical attention-selection layer composed
entirely over already-accepted facts, genuine semantic-dedup fixes found by
tests, reused health/storage debounce, new per-user preferences and quiet
hours, foreground-only browser notifications with Web Push deliberately
evaluated and deferred, and a real executable product-shaped quiet-week
proof -- see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
Mobile & Remote Experience v1 remains accepted at classification **B**
(strong mobile experience and a clear secure remote posture with bounded
external-network/PWA gaps -- see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
That milestone also closed, as its own bounded Phase 0, the
`place_change_summary.py`/`_presence_status` threshold gap the Place
Story & Seasonal Timeline v1 report (below) had recommended as future
work -- that item is now resolved, not still outstanding.
Place Story & Seasonal Timeline v1 remains accepted at classification
**B** (major useful capability, bounded history/story gaps -- see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
Place Features & Habitat Change v2 remains accepted at classification
**B** (major useful capability, bounded feature/data-model maturity
gaps -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
Environmental Context v2 remains accepted at classification **B** (major
useful capability, bounded provider/statistical/UI limitations -- see
[environmental-context-v2-report.md](environmental-context-v2-report.md)).
Place / Yard Intelligence v2 remains accepted at classification **B**
(major useful capability, bounded maturity gaps -- see
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)).
Camera / Source Experience & First-Hour Setup Closure v1 remains accepted
and closed at classification **C** (usable, bounded further closure
remains -- see Lane G, §6). No new implementation milestone is currently
authorized. The next milestone will be selected only after the governing
external process verifies this execution state against the complete
remaining release queue, the remaining Calm Attention & Notifications
opportunities (Web Push for a genuinely closed-browser interruption,
deliberately deferred; detector/model-unavailable Observatory Health
attention; per-user, not global, read/dismiss state; precise per-taxon/
per-Feature Place Story deep links; a live attention-sync diagnostics
surface -- see that report's "Remaining major PRODUCT opportunities"), the
remaining Mobile & Remote Experience product
opportunities (progressive disclosure for the dense Visit/Stream/Settings
pages; a genuine pre-existing `ReviewQueuePage` `product_category`/
"animals"-tab gap, found and documented, not fixed; no login rate-
limiting, a real pre-existing gap whose relevance this milestone's own
expanded network reachability directly heightens; no live external-
overlay-network (Tailscale/WireGuard) validation was possible from this
sandbox -- see the Mobile & Remote Experience v1 report's "Remaining
major PRODUCT opportunities"), the remaining Place Story product
opportunities (period summaries -- deferred on a measured performance
cost, not simply unattempted -- environmental-context/weather caveats on a
before/after insight, formerly listed here, closed 2026-09-06 by
Environmental Context x Place Story & Habitat Change Composition v1; a
dedicated taxon/Feature story page and representative imagery on Story
cards, formerly listed here, closed 2026-09-06 by Place Story Deep Dives &
Representative Evidence v1, see §1), the remaining Place Features & Habitat
Change product opportunities (a ranked feature-comparison view -- see the
Place Features & Habitat Change v2 report; composing environmental-
context/weather caveats onto a before/after result, formerly listed here,
closed the same day by the identical milestone; multi-camera Feature
linking, formerly listed here, closed 2026-09-06 by Multi-Camera Place
Feature Linking & Cross-View Habitat Context v1, see §1; representative
evidence in Feature detail, formerly listed here, closed 2026-09-06 by
Place Story Deep Dives & Representative Evidence v1, see §1), the
remaining Place/Yard
Intelligence product opportunities (seasonality maturation against real
history, a `source_quality_signals` UI surface -- the habitat before/
after change-event data model itself is now closed by that milestone),
**and** the remaining Environmental Context product opportunities
(deeper historical backfill via Open-Meteo's archive/ERA5 endpoint, wind/
cloud-cover statistical associations, a dedicated diagnostics/Explore-page
surface for weather -- see the Environmental Context v2 report). Do not
choose the next milestone by adjacency to this one.

Do NOT automatically authorize:

- a managed/fleet Camera Node updater, unattended/automatic upgrade
  scheduling, remote-triggered updates, artifact signing/PKI beyond
  checksums, or a graduated ("compatible older") wire-protocol tier beyond
  the Host's own existing exact-match gate, merely by adjacency to Camera
  Node Upgrade & Compatibility Recovery v1's closure -- each explicitly
  out of that milestone's own scope, none automatically the next milestone;
- a standalone follow-on campaign to close the two items Camera Node
  Upgrade & Compatibility Recovery v1 left honestly disclosed (`rollback()`
  not restoring an already-changed systemd unit template; its own
  directory swap's narrower residual crash-window gap) -- both real and
  recorded, neither automatically the next milestone by adjacency unless a
  concrete recurrence is found;
- live, authenticated iNaturalist OAuth submission, or any eBird workflow
  of any kind, merely to close Ecological Interoperability & Submission
  Workflows v1's own deliberately-deferred external-authorization boundary
  -- see that report for the full evidence (eBird's own current policy
  conflict; no secure server-side credential-storage pattern exists yet)
  this decision rests on;
- direct GBIF publication as a standalone follow-on -- see that report's
  destination research for why this remains institutional, not a
  backyard-user workflow;
- ecological-submission media-byte inclusion, or a single-Visit deep-link
  pre-selection on the Ecological Destinations page, as a standalone
  follow-on campaign -- each individually real and recorded, neither
  automatically the next milestone by adjacency;
- Remote Field Productization;
- standalone Web Push (VAPID/subscription persistence, a genuine outbound
  call to a third-party push service) merely to close Calm Attention &
  Notifications v1's own deliberately-deferred Phase 22 Decision B gap --
  see that report for the full local-first/privacy reasoning this decision
  rests on;
- a Review Queue product_category/"animals"-tab fix or per-user read/
  dismiss state as a standalone follow-on campaign -- each individually
  real and recorded in the Calm Attention & Notifications v1 report, none
  automatically the next milestone by adjacency (precise per-taxon/Feature
  Place Story deep links, formerly listed here, closed 2026-09-06 by Place
  Story Deep Dives & Representative Evidence v1 -- see §1);
- further Mobile/PWA/remote-access work as a standalone follow-on
  campaign -- specifically: progressive disclosure for the dense Visit/
  Stream/Settings pages, the `ReviewQueuePage` `product_category`/
  "animals"-tab fix, login rate-limiting, or a live external-overlay-
  network acceptance pass -- each individually real and recorded, none
  automatically the next milestone by adjacency;
- Local Species/Taxon Prior;
- another classifier benchmark;
- Provider Integrations;
- a second weather provider or user-facing provider choice;
- Open-Meteo archive/ERA5 deep historical backfill;
- a Feature/Zone multi-camera join table;
- Place Story period summaries as a standalone follow-on campaign
  (weather-caveat composition and dedicated taxon/Feature story pages,
  formerly listed here, are closed -- see §1);
- a ranked Feature-comparison view, a Feature-specific year-over-year
  comparison, or a general "see all" ranked species-change drill-down on
  the Year-over-Year card, as standalone follow-on campaigns -- each
  individually real and recorded in the Place Story Deep Dives &
  Representative Evidence v1 report, none automatically the next milestone
  by adjacency;
- Land Management / Agriculture as a separate campaign;
- notification-level (Calm Attention) cross-camera health grouping, Place
  Story wildlife-event source attribution, or camera-filter UI
  consolidation as standalone follow-on campaigns -- each individually
  real and recorded in the Multi-Camera Place Experience v2 report, none
  automatically the next milestone by adjacency. (The lost-candidate-Visit
  concurrent-write reliability gap that report also found, root-caused,
  and deliberately did not fix is **no longer on this list** -- Concurrent
  Candidate Visit Persistence Reliability v1, see §1, closed it at
  classification A.);
- broad multi-site, merely because single-Place multi-camera work just
  closed;
- final Release Hardening.

## 4. Product/release guardrails

MockingBird is:

- local-first;
- hardware-agnostic;
- nature-first rather than surveillance-first;
- bird-first but wildlife-native;
- evidence-backed;
- Place-centered;
- cloud-optional;
- human-correctable;
- abstention-friendly.

Canonical epistemic classes: **Measured**, **Inferred**, **Reviewed**.

Human correction is authoritative. Model inference cannot silently become
reviewed truth.

Raspberry Pi is reference Camera Node hardware, not product identity.
Native Windows remains the first end-user Host acceptance target.
WSL/Linux development success does not equal native-Windows product
acceptance.

Privacy Zones currently mean trigger-level exclusion, not guaranteed pixel
redaction of all retained frames unless future code explicitly implements
that.

User data is not the primary monetization strategy. Core functionality
must remain complete under Local Only privacy.

## 5. Frozen / substantially accepted lanes

Summarized without milestone archaeology; see `roadmap.md` and the linked
accepted-milestone docs for detail if a future task genuinely needs it.

**Observation / Reviewed Truth.** Accepted foundations include Visit →
Evidence → Review → Observation; review/correction/revision; actor
attribution; evidence lineage; Today/history truth.

**Perception / Admission.** Accepted: MDv5a production detector;
small/far-bird work; ambiguous-boundary/admission fixes; per-Stream Visit
authority; evidence-cache correction; scene-confusor suppression;
perception replay; multi-subject Visit foundations.

**Site-Specific Learning.** Accepted and frozen. Reviewed-negative
scene-confusor adaptation accumulates/evaluates reviewed evidence, is
production-disabled by default, and requires explicit per-Stream
enablement for production effect. Do not automatically build Local Taxon
Prior or calibration on top of this.

**Species Classification.** Accepted and frozen: BioCLIP-2 stays
production; BioCLIP 2.5 rejected; SpeciesNet not promoted.

**Broader Wildlife.** Accepted structurally. Non-bird review/history/
product semantics work. Automatic mammal species identification remains
limited.

**Identity / Multi-User.** Accepted: Viewer / Reviewer / Administrator;
server-side sessions; authorization; actor attribution; audit; review
concurrency; backup/restore.

**Environmental Context.** Accepted; extended, not frozen -- Environmental
Context v2 (2026-08-25) added the first general weather provider
(Open-Meteo) on top of the accepted solar/daylight foundation: eight
provider-neutral metrics, always `information_class="inferred"`; a
second, independent `weather_enabled` opt-in (schema v53 -> v54) gating
every outbound network call separately from the existing coordinate
setting; bounded lazy caching; Place-relative temperature and wet/dry
precipitation associations composed onto the existing `conditional_
association` primitive alongside `habitat_associations`. See
[environmental-context-v2-report.md](environmental-context-v2-report.md).
Substantial product-roadmap opportunity remains (deeper historical
backfill via the archive/ERA5 endpoint, wind/cloud-cover statistical
associations, a dedicated diagnostics/Explore-page surface); do not treat
this lane as closed.

**Habitat & Phenology.** Accepted/frozen.

**Biodiversity & Place Intelligence.** Accepted; extended, not frozen --
Place / Yard Intelligence v2 (2026-08-25) added regularity narrative,
seasonal pattern, temporal pattern, per-Source activity/quality, and a
weekly digest on top of the already-accepted foundation. Place Features &
Habitat Change v2 (2026-08-25, same day) closed that milestone's own
recorded "habitat before/after change-event data model" gap: a durable
Place Feature entity, a Reviewed change-event timeline, and a before/after
comparison engine built on pure reuse of the existing `conditional_
association` primitive -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md).
Place Story & Seasonal Timeline v1 (2026-08-25, same day) composes all of
the above -- plus Reviewed phenology observations and Reviewed Feature
change events -- into one Place-wide, dated, filterable, correction-safe
timeline (`GET /api/place/story`), no new schema; see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
for the full record, including a genuine previously-undiscovered gap
found in `place_change_summary.py`'s own already-accepted threshold logic
(worked around locally, not patched at its source -- see that report's
"Truth / provenance"). Environmental Context x Place Story & Habitat
Change Composition v1 (2026-09-06) closed the "environmental-context/
weather caveats not yet composed onto a before/after result or a Story
insight" gap named here -- see
[environmental-context-place-story-habitat-change-composition-v1-report.md](environmental-context-place-story-habitat-change-composition-v1-report.md).
Year-over-Year Seasonality & Long-Term Place Memory v1 (2026-09-06) closed
the "year-over-year seasonality" gap named here -- see
[year-over-year-seasonality-long-term-place-memory-v1-report.md](year-over-year-seasonality-long-term-place-memory-v1-report.md):
a new pure module composes onto the already-accepted `conditional_
association` primitive to compare one Place-local calendar month against
the same month one year earlier (Place-level activity and per-species
activity/first-observed-timing), zero schema change, plus a new Dashboard/
Place Report card and a new Place Story event kind. No live production
proof of a `"comparable"` outcome exists yet -- this product does not have
a full year of real accumulated field history anywhere yet, an
unavoidable data-availability constraint, not an engineering gap.
Multi-Camera Place Feature Linking & Cross-View Habitat Context v1
(2026-09-06) closed the "multi-camera Feature linking" gap named here (a
Place Feature can now be linked to zero, one, or many camera/Zone
observation views) -- see
[multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md](multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md).
Place Story Deep Dives & Representative Evidence v1 (2026-09-06) closed
the "a dedicated taxon/Feature story page" and "representative imagery"
gaps named here -- see
[place-story-deep-dives-representative-evidence-v1-report.md](place-story-deep-dives-representative-evidence-v1-report.md):
two new pages (`/place-story/taxon/:label`, `/place-story/feature/:id` --
also this product's first dedicated Feature detail page) compose already-
accepted primitives (Bird Log's own per-species bundle, the existing
Feature-detail bundle, Place Story's own already-working `taxon=`/
`feature_id=` filters) via one shared, extracted Story-card component;
representative evidence reuses the canonical Gate C selector unmodified,
extended to a Feature's own linked camera views via a new, multi-camera-
aware, cross-camera-deduplicated candidate-gathering path. Place Feature
Comparison & Habitat Outcomes v1 (2026-09-06) closed the "a ranked
feature-comparison view" opportunity named here (a deliberately-authorized,
bounded reopening of this specific, previously `D -- enrichment`-classified
backlog item, not a resumption of general product development) -- see
[place-feature-comparison-habitat-outcomes-v1-report.md](place-feature-comparison-habitat-outcomes-v1-report.md):
one new repository method composes four already-accepted primitives
(before/after comparison, yield, environmental composition, representative
evidence) across every Feature in one batched pass, zero new statistical
engine, measured 21.0-21.5% fewer queries than calling `get_place_feature_
detail` independently once per Feature.
Substantial product-roadmap opportunity still remains (Place Story period
summaries; a year/month picker over the year-over-year card; week-level or
named-seasonal-period comparison; batching `StreamVisitSummary`
construction across many Visits, the larger remaining share of the
comparison overview's own measured query cost -- see that report's and
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)'s
and
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)'s
respective "Remaining major PRODUCT opportunities"); do not treat this
lane as closed.

**Camera / Acquisition Foundations.** Substantial accepted work: native
Camera Node path; ONVIF; RTSP/RTSPS; offline/recorded ingest; camera-trap
ingest; provider-neutral Source/Stream architecture. First-hour product
experience materially closed (Add Camera preview, credential honesty) --
see Lane G.

**Diagnostics / Storage / Recovery Foundations.** Substantial accepted
work: health/diagnostics; Doctor/support concepts; storage health;
retention; backup/restore; recovery. Final integrated product acceptance
remains open (see Lane R, below). **2026-09-09 update (Product Operations
& First-Observation Completion v1):** Doctor's own CLI-only limitation is
closed -- a real authenticated `GET /api/product/doctor` and a new
`DoctorPage.tsx` now expose it, unmodified underneath, with calm recovery
-action links to existing controls. Camera Node storage/hardware-quality
visibility (shipped Node-side by the immediately-prior milestone but
unreachable by any human) is also closed, via a bounded live check rather
than Doctor itself. See the top-of-file dated entry and
[product-operations-first-observation-completion-v1-report.md](product-operations-first-observation-completion-v1-report.md)
for the full record. Whole-product integrated acceptance (Lane R) is
unaffected by this note and remains its own separate, already-closed
status.

**Research / Conservation.** Substantial accepted work: conservation
reporting; effort/coverage; research-safe eligibility/export; Camtrap DP;
Darwin Core Occurrence-core export (2026-08-25, additive to Camtrap DP, not
redundant with it -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md));
contributor/research provenance.

## 6. Global remaining execution queue

This is the most important section. Lanes are not removed merely because
they are not next.

**Four release-shape categories.** Every lane below already sorts into one
of four categories; renaming the release model (§7, above) does not change
which lanes are release-critical, deferred, or later -- it only fixes the
words used to describe them:

- **A. Release-critical** -- must be complete/credible before the one
  public launch. Lanes marked **RELEASE-CRITICAL** below carry this:
  representative field correctness/whole-product acceptance (Lane R),
  camera/source golden path (Lane G), storage/retention/recovery (Lane M),
  Local Only/privacy (Lane N), platform/runtime support truth (Lane O),
  release/distribution closure (Lane P), accessibility/performance (Lane
  Q), appliance/update/recovery (Lane L) -- plus, as the internal gates
  above become credible, External Pre-Release Acceptance and Final
  Release Hardening themselves (Lane S, below; roadmap.md Gates F-G).
- **B. Pre-release decisions** -- decisions required before launch, not
  necessarily implementation milestones: the codebase `LICENSE` --
  **RESOLVED**: the owner selected MIT and mechanical adoption (a real
  `LICENSE` file, package metadata, README truth, distribution inclusion)
  is now complete, per MIT Source License Adoption & Lane P Mechanical
  Closure v1 (Lane P now **CLOSED** -- see Lane P, below; full ffmpeg
  distribution licensing, the item this line previously named alongside
  it, is fully resolved); the still-open BirdNET
  commercial-adjacent legal posture (§2, above -- blocks only
  commercial-adjacent use of the optional acoustic feature, per the
  2026-09-06 reconciliation below, not all public launch); platform-support
  declarations (Lane O, resolved -- see Lane O, below); Ecosystem/Provider
  Integrations scope (Lane K, resolved -- see Lane K, below); any other
  genuine unresolved release decision as it surfaces.
- **C. After release** -- real product development explicitly not
  required for launch, kept so it is not lost: complete remote/
  intermittent-WAN/LTE, solar/battery, custom CM4/CM5 (Lane B, and §8,
  below); research-grade remote-field acceptance; broad multi-site (Lane
  F's own explicitly-deferred remainder); native mobile (Lane E's own
  explicitly-out-of-scope remainder); advanced acoustic analytics (Lane
  A's own remaining bounded follow-up); mature automatic mammal species
  identification (Lane I).
- **D. Later / evidence-driven** -- the long-range, demand-driven queue in
  §9, below: GenICam, GigE Vision, USB3 Vision, radiometric thermal,
  specialized industrial cameras, individual-animal recognition,
  population estimates, behavior prediction, causal ecological modeling,
  large cloud/fleet infrastructure.

This is a navigational grouping over the existing lettered lanes (A-S), not
a new or renumbered lane system: no lane is removed, renamed, or promoted
between categories by this grouping, and each lane's own status text below
remains authoritative over this summary.

### A. Acoustic / BirdNET Productization

**Status:** ACCEPTED -- RELEASE-READY OPTIONAL.

**Corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1:** the "frontend acoustic health/status"
item this section previously listed as remaining was already closed by
Whole-Product UI / Accessibility / Performance Closure v1 (2026-08-27):
"the scheduler's disclosed bounded acoustic health/status gap (Lane A)
closed with the smallest capability-aware addition the brief allowed --
composed entirely from already-existing facts, never a factor in
`ready`." Removed from the remaining list below; the other three items
are unaffected.

Remaining bounded follow-up only: longer field soak; physical
unplug/replug; natural wild-bird field evidence. Do not schedule another
acoustic architecture milestone automatically.

### B. Remote / Intermittent-WAN Field Productization

**Status:** PARTIAL -- AFTER RELEASE UNLESS A NEW CORE DEPENDENCY
APPEARS.

Existing foundation includes substantial spool; store-and-forward;
transport; retry; Host consume-to-evidence behavior; diagnostics.

Remaining: real LTE/carrier acceptance; real remote Pi deployment;
bandwidth behavior; resume granularity; extended outages; unattended
recovery; remote operator experience; solar/battery/power reality.

Remote LTE/solar/custom CM4/CM5 field deployment is **not** a release
blocker.

### C. Everyday Product / Discovery UX

**Status:** MATERIALLY DELIVERED / NO KNOWN DEV REMAINS. Lane C Sparse-
State Honesty & First-Hour Narrative Closure v1 (2026-08-30) closed the
two remaining bounded DEV gaps a prior accepted read-only Lane C
reconciliation had left open; see
[lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md).
Classification **A**.

Delivered, across the already-accepted milestones behind each (this
section's own prose had never been reconciled as each landed piecemeal
under Gate C naming rather than explicit "Lane C" naming -- corrected
here, not re-implemented): Best Moments and report-first hierarchy (Gate C
Daily Place Report v1, Gate C Representative Species Evidence v1); calm
daily summary (Gate C Calm Daily Digest v1); New / Regular presentation
(Gate C Historical Baseline Maturity v1, Historical Species-Status
Correctness v1); unknown/unresolved handling (Gate C Per-Species Zone +
Time Pattern Intelligence v1 and the broader review-optional/unresolved-
label design); understandable suggestion explanations (Same-Frame Species
Evidence v1, Visit Same-Frame Classifier Evidence Visibility v1);
mostly-invisible review (the shipped review-optional design; Whole-Product
UI / Accessibility / Performance Closure v1's Review Queue fix). Delivered
by this milestone: sparse/no-wildlife honesty under primary detector/GPU/
model failure (a Camera Node Stream's Dashboard/`ProductHealth` failure
text no longer lets a stale "paired and configured" success message mask
a real detector/GPU/model failure); a coherent first-hour narrative in
onboarding (`OnboardingWizard.tsx` no longer frames Review Queue as the
normal destination for ordinary discovery -- Today/Bird Log are, matching
the shipped review-optional design).

Not claimed complete by this closure: future taxonomy content, a Dashboard
layout change, or general UI perfection. Do not turn this lane into a
giant redesign; do not reopen any of the delivered items above without a
directly reproduced, same-root-cause dependency.

### D. Calm Notifications

**Status:** MATERIALLY DELIVERED -- Calm Attention & Notifications v1
(2026-08-25) closed this lane's decision; see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md).
Classification **B**.

Delivered: one canonical attention-selection layer over already-accepted
facts (Place Story, the daily/weekly digest, the existing review/monitoring/
storage/journal alert system); a small user-centered taxonomy (Discovery/
Insight/Needs Help/Observatory Health) and explicit urgency (immediate/
digest/in-app-only), never raw internal severity/error vocabulary; genuine
semantic deduplication (two real double-notification anti-patterns found
and fixed by tests); reused, not reinvented, health/storage debounce; a
daily/weekly digest notification reusing the existing digest computation
unmodified, suppressed when there is genuinely nothing meaningful; per-user
notification preferences (four category toggles + quiet hours, evaluated in
the viewer's own browser-local time); foreground-only browser-notification
delivery (Web Push explicitly evaluated and deferred -- Decision B, no
cloud push infrastructure added, matching this lane's own standing
instruction); an extended Attention Center and a calm "N things worth
noticing" line on Today; a real, executable product-shaped quiet-week test
proving the whole week stays calm. Schema 55 -> 56 (one additive per-user
preferences table).

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": Web Push for a genuinely closed-browser
interruption; detector/model-unavailable Observatory Health attention;
per-user (not global) read/dismiss state; precise per-taxon/Feature Place
Story deep links (today scoped to a category group); a live attention-sync
diagnostics surface.

### E. Mobile / Remote UX

**Status:** PARTIAL, MATERIALLY ADVANCED -- Mobile & Remote Experience v1
(2026-08-25) closed the core decision this lane was waiting on; see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md).
Classification **B**.

Delivered: a verified (10 real automated phone-width screenshots, zero
overflow) responsive navigation fix -- top bar + off-canvas drawer +
4-item bottom nav, replacing a sidebar that previously stacked in full
above every page below 980px; a bounded, safety-reasoned installable PWA
shell (manifest, icons, a service worker that only ever caches Vite's own
immutable hashed assets, never navigation/API/data -- no offline data
claim made anywhere); LAN access made discoverable (`GET /api/product/
connection` + a Settings card, with a corrected, no-longer-stale
`--allow-network` help string); a private-overlay-network
(Tailscale-compatible) posture chosen and documented as the supported
away-from-home path, with direct public-internet exposure and a cloud
relay explicitly, plainly documented as unsupported/not-built; new CORS
regression coverage. Native mobile remains explicitly out of scope,
unchanged.

**Corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1:** two of the four items this section
previously listed as remaining were already independently closed
elsewhere in this document. The `ReviewQueuePage` `product_category` gap
is the identical defect Whole-Product UI / Accessibility / Performance
Closure v1 (2026-08-27) fixed as its own P0 finding: "manually- and
folder-imported Visits... were silently excluded from Review Queue's
default 'Animals' tab regardless of `subject_label` -- the real,
previously-unidentified root cause of one class of confusion this project
had repeatedly, incorrectly attributed to `reviewed-product-loop.spec.ts`
being an unrelated flake." The login-rate-limiting gap was closed by
Login Rate-Limiting & Authentication Abuse Resistance v1 (accepted
classification A): a new `LoginRateLimiter`, account- and source-keyed,
live at `POST /api/auth/sign-in` today. Both removed from the remaining
list below.

Remaining, not closed by this pass (see the report's "Remaining major
PRODUCT opportunities" for the full record): progressive disclosure for
the dense Visit/Stream/Settings pages; no live external-overlay-network
(Tailscale/WireGuard) acceptance was possible from this sandbox --
validated structurally only. Do not equate this closure with a finished,
fully-polished mobile product, and do not automatically authorize a
follow-on Mobile/PWA campaign by adjacency -- see §3.

### F. Multi-Camera / Multi-Site

**Status:** MATERIALLY ADVANCED -- Multi-Camera Place Experience v2
(2026-08-26) closed this lane's integrated-acceptance decision; see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md).
Classification **B**.

Camera/Source + Multi-Camera Maturity v1 (2026-08-23) had already built the
real foundation this lane's own text below was actually waiting on
(cross-camera duplicate-encounter association, Area vocabulary, provider
compatibility, health coherence) -- that milestone's own report was
missing (only a `-contract.md` existed, no `-report.md`), which is why
this lane's status had not been updated to reflect it; corrected here.
Delivered this milestone: a real, previously-hidden defect found and fixed
with principled nuance (an archived camera's history was unreachable from
every discovery surface, contradicting this codebase's own documented
archive-only-preserves-history doctrine; the fix deliberately preserves
already-tested current-active-only *defaults* on Bird Log/Wildlife
Insights/Biodiversity while making that real history reachable by explicit
camera filter and by period-scoped reports); Today surfacing its own
already-computed per-camera activity/evidence-source facts for the first
time; a Bird Log camera filter reaching the overview list, not only the
per-species drilldown; a real coverage-union fix for Zone Insights'
Place-wide aggregate (was a naive per-camera-hours sum); Dashboard
distinguishing "some cameras need attention" from "every armed camera
needs attention"; a real, measured (2-camera and 4-camera-asymmetric,
genuinely concurrent real-thread) admission/assembly-layer concurrency
proof with zero cross-Stream contamination and no starvation found; a
comprehensive, real, executable product-shaped scenario proving the whole
chain -- identity, coverage, overlap dedup, health, correction propagation
-- coheres end to end. Schema unchanged (v57 -> v57): every fix is a query-
scope correction or an additive field on an already-derived response
object.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": notification-level (Calm Attention) cross-camera
grouping beyond the Dashboard status-view fix; Place Story wildlife-event
source attribution (the field exists, populating it needs restructuring a
shared SQL-aggregation layer, not a field-threading exercise); consolidating
at least 6 independently-implemented camera-filter UI controls into one
canonical component; multi-camera Place Feature linking, formerly listed
here, closed 2026-09-06 by Multi-Camera Place Feature Linking & Cross-View
Habitat Context v1, see the status note directly below; real GPU/CUDA-
driver-level concurrent-inference measurement (needs real hardware this
sandbox lacks); a multi-hour concurrent soak beyond the single-pass
measured proof; the pre-existing, disclosed 2-Stream cap on the separate
legacy motion pipeline (RTSP/USB/local providers, not the modern
Observation Engine's own Camera Node path).

**Reliability lane status (Concurrent Candidate Visit Persistence
Reliability v1, same-day follow-on):** this lane's one item touching the
critical Visit write path -- occasional silent loss of an admitted
candidate under real concurrent multi-Stream SQLite writes -- is now
**CLOSED** at classification **A**; see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
Every other item in the "Remaining, not closed by this pass" list directly
above is unaffected and still open.

**Feature-linking item status (Multi-Camera Place Feature Linking &
Cross-View Habitat Context v1, 2026-09-06):** this lane's own "multi-camera
Place Feature linking" item, named in the "Remaining, not closed by this
pass" list above and repeated in Place Features & Habitat Change v2's own
Phase-28 record, is now **CLOSED** at classification **A**;
see §1, above, and
[multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md](multi-camera-place-feature-linking-cross-view-habitat-context-v1-report.md).
A Place Feature can now hold zero, one, or many camera/Zone observation
links; cross-view analytics reuse the accepted cross-camera duplicate-
encounter exclusion and elapsed-time coverage-union primitives unmodified
(one real encounter recorded by two linked cameras counts once; coverage is
a real union, never a sum). Every other item in the "Remaining, not closed
by this pass" list directly above is unaffected and still open.

True multi-site remains a separate product/architecture decision. Do not
silently make it release scope, and do not self-authorize it by adjacency
to this lane's closure.

### G. Camera / Source Experience

**Status:** CLOSED -- RELEASE-CRITICAL. Authenticated Camera Node
Golden-Path Capture & Preview Acceptance v1 (2026-09-03, classification
**A**) closed this lane's own last-named remaining gap -- see the end of
this section for the full closure record.
Camera / Source Experience & First-Hour Setup Closure v1 (2026-08-25)
fixed two real P0 first-hour gaps and two P1s; see
[camera-source-experience-v1-report.md](camera-source-experience-v1-report.md)
for the full archaeology, gap table, and evidence. Ongoing Monitoring
Failure Diagnostics for RTSP / Local USB / Windows DShow v1 (2026-08-30)
then closed that milestone's own disclosed remaining implementation gap;
see
[ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md).
Release classification: **C** (usable; the remaining gap is real hardware
validation, not implementation).

Closed by Camera / Source Experience & First-Hour Setup Closure v1:
manual RTSP setup's separate "Auth username"/"Auth password" fields were
collected but silently discarded on every write and never reached a real
connection attempt -- now stored for real and merged into the effective
connection URL everywhere it's actually used. Only Camera Node had a
real "Check the picture" setup preview -- now RTSP/ONVIF/local/
Windows-USB have the same bounded, non-persisting preview capability, and
`CameraSetupValidationResponse.preview_available` is computed honestly
instead of hardcoded `False`. A healthy camera's own detail page had no
persistent way back to reconfigure it; a dead, unreachable duplicate
Add-Camera form was removed.

Closed by Ongoing Monitoring Failure Diagnostics for RTSP / Local USB /
Windows DShow v1: the ongoing-monitoring failure-code collapse named
below is fixed -- a new bounded, continuous `BoundedStderrDrain` replaces
the previously-unconditional `stderr=subprocess.DEVNULL` on RTSP/local
USB/Windows DirectShow's own long-running monitored processes (proven
safe: no pipe deadlock, bounded memory, no thread leak, no blocked frame
delivery); RTSP ongoing monitoring now reuses the exact, unmodified
setup-time classification vocabulary; local USB/Windows DirectShow gained
new classifiers strictly bounded to real evidence gathered this
milestone, with an honest generic fallback wherever that evidence ran
out; two independent hardcoded Camera-Node-only allowlists that had been
discarding any other provider's classified code were widened. Camera Node
itself was out of scope and is untouched.

Remaining, not closed by either pass: real local USB/Windows DirectShow
hardware acceptance (device-busy, permission-on-real-hardware,
unsupported-format were not evidence-backed on the hardware available
this session -- honestly generic behavior for those causes by design, not
a known defect) and a real RTSP camera's own live auth/codec failure
(only a real, live, disposable-endpoint *unreachable*-failure proof was
practical this session, through the completely real, unmodified product
code path). No real, reachable camera/RTSP/ONVIF/local-USB hardware or
Camera Node was available to prove actual video decode/preview
end-to-end in either session (native-Windows evidence proves the real
subprocess/HTTP/taxonomy/credential-merge mechanics genuinely work
against a real unreachable host, not that a specific real camera's
picture renders). Full integrated multi-camera/whole-product acceptance
remains Lane R.

Camera / Source Release Hardware Validation Closure v1 (2026-09-02,
classification **B**; see
[camera-source-release-hardware-validation-closure-v1-report.md](camera-source-release-hardware-validation-closure-v1-report.md))
changed which specific gap remains, but not the overall status. For the
first time on record, the reference Camera Node was genuinely reachable
this session: real, live proof of health, both compatibility-preflight
profiles (including a real bounded RTT clock-calibration batch), an
honest pairing-conflict rejection, and a clean bounded service-restart
recovery cycle. It also reproduced and fixed, live against this exact
Node's real device topology, a diagnostic-truth defect Representative
Daylight Gate A Field Acceptance v11 had disclosed but left open:
`/node/v1/health`'s `self_test.camera_available` could report success
purely because a co-enabled `v4l2` provider counted the Node's own
internal ISP/codec/HEVC-decoder pipeline device nodes as cameras, masking
the real camera's correctly-reported absence (`mockingbird_node.
providers.V4L2CameraProvider`, not deployed to the live reference Pi --
proven via tests grounded in its own real topology instead). Still not
closed: live authenticated video capture/preview proof, for *any* real
camera including the now-proven-reachable Camera Node itself -- this
session had no usable pairing credential for it (the Node's pairing model
is single-credential; the only locally-known one is stale/revoked, and
forcing a fresh pairing against this shared reference device was
deliberately avoided) -- and RTSP/local-USB/ONVIF hardware remained
unreachable, with a known Windows DirectShow webcam registered but not
connected (real, live, enumeration-honesty proof only; no live capture).
Concrete remaining item: obtain or mint a usable Camera Node pairing
credential and prove live video capture/preview end to end.

**Authenticated Camera Node Golden-Path Capture & Preview Acceptance v1**
(2026-09-03, classification **A**; see
[authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md](authenticated-camera-node-golden-path-capture-preview-acceptance-v1-report.md))
closed the concrete remaining item named above. Traced the reference
Node's orphaned credential (unresolved by the immediately-prior session)
to an archived, dormant `MockingBirdFieldAcceptanceV11` by SHA-256 digest
comparison and safely revoked it through the real, unmodified
`CameraNodeClient.revoke()` path. Deployed the previously-accepted
`V4L2CameraProvider` fix (`ca98fc6`, never live-deployed in its own
milestone) to the reference Pi, which immediately exposed a second, real
diagnostic-truth gap in the same class (`isOpened()` alone insufficient --
a `bcm2835-isp` internal ISP pipeline-stage node can accept a V4L2
`open()` while never delivering a frame); fixed together with the timing
consequence its own real-hardware cost exposed in self-test's fixed
timeout (`4c1be35`, RED->GREEN, Tier 1+2 clean). Real authenticated Node
images captured and decoded end to end (1920x1080, a real backyard scene,
three independent captures via two request shapes); real Add Camera
pairing/preview/complete proven via a genuinely fresh disposable Host
instance; real Chromium/Playwright proof against the real built frontend
(full pass, real screenshots); preview non-persistence verified directly
against the database (zero Visits/Events created); bounded interruption/
recovery exercised against the configured Stream; credential safety
verified against the real secret value; strict `field_acceptance`
compatibility passed with a real 5/5-sample RTT calibration batch. One
disclosed, non-blocking finding: a real, self-resolving post-pairing
background-warm-proof timing race (self-resolves in ~5-10s with honest
failure messaging throughout the whole time; judged correctly non
-release-critical, not fixed as a product change). RTSP/local-USB/ONVIF/
Windows-DirectShow hardware remains unavailable in this environment,
exactly as every prior session already, honestly, disclosed -- per that
milestone's own governing brief, this does not block Lane G closure; those
paths' declared support labels remain honest and unchanged. Final Node
state: healthy, upgraded, genuinely unpaired (every test credential this
milestone itself minted was cleanly revoked before finishing). **Lane G
status, updated:** `MATERIALLY CLOSED / VALIDATION REMAINS` -> `CLOSED --
RELEASE-CRITICAL`.

### H. Site-Specific Learning

**Status:** FROZEN.

No adjacent learning expansion automatically authorized.

### I. Broader Wildlife Maturity

**Status:** FROZEN STRUCTURALLY.

Real mammal field evidence remains limited. Do not create another model
campaign solely to fill the matrix.

### J. Ecological / External Workflows

**Status:** MATERIALLY ADVANCED -- Ecological Interoperability & Submission
Workflows v1 (2026-08-25) closed this lane's decision; see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md).
Classification **B**.

Delivered: a real, working, submission-ready iNaturalist workflow
(eligibility preview with per-record reasons, explicit never-inferred
location/media consent, batch prepare, a destination-shaped CSV confirmed
directly against iNaturalist's own open-source bulk-import code,
fingerprint-based staleness detection, a self-reported external-result
close-the-loop step); a bounded, additive Darwin Core Occurrence-core
export; the destination-decision research itself (eBird's own current
policy explicitly excludes feeder/trail-camera data -- not offered, and
the product UI says why persistently, not merely in a hover tooltip; GBIF
direct publication requires organizational endorsement -- correctly
deferred as institutional); two real security findings made and fixed
(CSV injection in the shared CSV writer behind every export in this
codebase, retroactively hardening the pre-existing generic/Camtrap DP
paths too; a `javascript:`-scheme external-URL gap). Schema 56 -> 57 (two
additive tables). No live, authenticated destination submission exists
anywhere -- Phase 26 of that milestone's own brief: no unsafe
credential-storage workaround invented for a capability that does not yet
exist.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": live OAuth iNaturalist submission; media-byte
inclusion; a single-Visit deep-link pre-selection on the Ecological
Destinations page; broader batch-filter UI depth (stream/source/collection
scoping, already supported server-side via the reused
`ResearchExportFilters`, not yet exposed in the frontend).

### K. Ecosystem / Provider Integrations

**Status:** DECISION CLOSED -- DEDICATED PROVIDER INTEGRATIONS DEFERRED
PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH. Ecosystem / Provider
Integrations Release-Scope Decision v1 (2026-09-03) closed this lane's
decision; see
[ecosystem-provider-integrations-release-scope-decision-v1-report.md](ecosystem-provider-integrations-release-scope-decision-v1-report.md).
Classification **A**.

Candidates assessed individually: Frigate; Blue Iris; Scrypted; Home
Assistant. None supplies a camera-acquisition capability MockingBird
fundamentally lacks -- ONVIF, RTSP/RTSPS, local USB/platform camera,
offline/recorded ingest, and camera-trap ingest already cover the core
camera path (see "Camera / Acquisition Foundations," §5, above), and a
generic, vendor-neutral webhook ingress already lets any of the four feed
evidence-only events in today without a dedicated adapter. Each carries
real surveillance/NVR product-identity pressure and a new credential/
network surface. Native Camera Node + standards-based acquisition remain
the golden/general launch path. Deferred, not implemented, not "never" --
see the report's "Reopening criteria" for the concrete, evidence-based bar
(repeated otherwise-unsolvable connection failures, a provider exposing
evidence-quality facts standards can't, measured installation-burden
reduction, repeated organizational dependency, measured reliability gain;
popularity/API-availability/competitor-parity/plugin-framework desire are
explicitly insufficient alone) and "Architecture contract for future
adapters" for the locked terminating-into-existing-truth-architecture
requirement any later adapter must meet.

### L. Appliance / Update / Recovery

**Status:** MATERIALLY CLOSED -- RELEASE-CRITICAL. Host side closed by
Release Engineering Foundation v1 (2026-08-25); Camera Node **upgrade**
workflow -- the one specifically-named remaining item -- closed by Camera
Node Upgrade & Compatibility Recovery v1 (2026-08-26), classification
**A**. See [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

Closed for the **Host**: an automatic, verified pre-migration safety
backup now runs before any in-place schema upgrade; a genuine post-
migration health check gates readiness; the upgrade fact is honestly
surfaced (console + Dashboard); restoring that automatic backup is the
documented rollback path; interrupted-upgrade behavior (backup failure,
mid-migration failure, post-migration integrity failure) all fail closed
and are regression-tested; real native-Windows evidence includes an
organically-occurring 18-schema-version migration on real pre-existing
data. Host↔Camera Node **wire-protocol** version compatibility
(`api_version`, `transport_protocol_version`) confirmed already
hard-gated; the Node's own `service_version` remains display-only by
deliberate choice (see the milestone report).

Closed for the **Camera Node**: `scripts/install_camera_node.py` (the
existing installer, extended rather than replaced) now runs a real
preflight (artifact well-formed, `SHA256SUMS` checksums, disk space, a
Node-local wire-protocol compatibility comparison against the currently
-installed build) before any mutation; stages and verifies a candidate
(`import mockingbird_node.app` inside its own fresh venv) before the live
install is touched at all; activates manifest-first/venv-second so any
interruption resolves to one of three well-defined, automatically
-reconciled states; automatically restores the prior known-good build if
the newly-activated one fails post-update health verification (never on a
first-ever install); and never silently accepts an unexpected `node_id`
change. Real acceptance against the project's actual reference Pi (never
upgraded since 2026-08-18, predating three later accepted Camera Node
milestones) found and fixed, live, a universal upgrade-blocking defect
(a transport-configuration path defaulting through `Path.home()`, always
broken under the already-accepted `ProtectHome=true` hardening regardless
of whether transport was ever configured -- would have broken every
Camera Node upgrading past Remote/Intermittent-WAN Transport Foundation
v1 through the accepted installer) and two automatic-recovery gaps
(`systemctl restart` failing outright not triggering rollback; a prior
crash loop's exhausted `StartLimitBurst` blocking an unrelated later
restart) -- all three fixed the same session with regression tests, not
merely disclosed. The device was fully upgraded end to end with node
identity/pairing/camera availability all confirmed unchanged.

Remaining, disclosed, not closed by this pass: `rollback()` restores code
but not an already-changed systemd unit template (a real gap this
milestone's own real acceptance encountered and worked around manually,
not closed structurally); `rollback()`'s own directory swap has a
narrower residual crash-window gap than the forward-upgrade path's
reconciliation closes; reinstall/replacement beyond what reprovisioning
already covers and broader operator-facing update/recovery UX remain
Camera Node install/reboot/reprovision's own already-accepted scope,
unaffected by this milestone. See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

**2026-09-08 note:** Host **uninstall** (never part of this lane's own
original scope, which covered install/update/recovery only) is now
separately documented and proven -- see the new "Uninstall contract
(Phase P)" in
[appliance-storage-privacy-recovery-v1-contract.md](appliance-storage-privacy-recovery-v1-contract.md)
and
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md).
This lane's own two disclosed residuals (`rollback()`'s systemd-template
and directory-swap gaps, immediately above) are untouched and unaffected.

### M. Storage / Retention UX

**Status:** CLOSED -- RELEASE-CRITICAL. Integrated acceptance performed
by Storage / Retention / Disk-Pressure & Recovery Closure v1 (2026-08-28,
classification **B**), then closed by Retention Correctness & Bounded
Cleanup Closure v1 (2026-08-28, classification **A**) -- see §1/§3,
above, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)/
[retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md).
Disk-pressure detection (a real, tested, graduated healthy/getting_low/
action_recommended/critical ladder), long-running storage growth (real,
directly-measured accounting on both the WSL dev host and the real Windows
deployment), cleanup/retention (now 366+ real tests across the two
closures, independently re-run, covering eligibility/idempotency/
interruption-safety/transactional ordering/bounded history), DB/media
consistency (traced precisely in both directions), and backup visibility
(Doctor-surfaced staleness/unreadable-count/interrupted-restore, all real
and tested) were each verified integrated, not merely inspected in
isolation. NAS/external-storage support remains an explicit product
decision, not an automatic blocker, and was not built. The three real,
precisely-disclosed, safe-direction gaps the first closure found and
deliberately left unfixed (imported-media over-retention against its own
documented contract; a `"staging"`-batch purge-path gap; a cosmetically-
misnamed, actually-unbounded `storage_cleanup_history` constant) are now
fixed and tested by the second, closing this lane. One real,
already-disclosed, structural gap remains, deliberately not reopened by
either closure: no orphan-media/no-DB-owner detection anywhere in the
product (no code scans the media directory and cross-references it
against the DB) -- real, bounded, and low-materiality per the first
closure's own investigation, not release-blocking, a reasonable candidate
for a future bounded "sampled orphan sweep," not a reason this lane
remains open.

### N. Privacy / Contribution

**Status:** CLOSED -- RELEASE-CRITICAL. Local Only / Privacy Closure v1
first closed this lane's Local Only requirement at classification **B**
(see
[local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)),
proving core product functionality works with zero internet route
available via a real, live, OS-level network-denial runtime acceptance --
but that acceptance ran the Linux/WSL dev checkout rather than the
packaged native-Windows artifact, and exercised the model-assets-absent
path rather than assets-present, both named explicitly as the reason it
was not classification A. Native-Windows Packaged Local-Only Acceptance &
Privacy Closure v1 (see §1/§3, above, and
[native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md))
closed both of those specific gaps at classification **A**: a real
disposable native-Windows packaged deployment (full GPU/BioCLIP dependency
closure, no skip flags), a real (non-kernel, environment-appropriate)
internet-denial mechanism with independent OS-level corroboration, and
both production models (MDv5a, BioCLIP-2) proven initializing and running
real local inference at the exact production code path both before and
after denial, with zero outbound network activity. The camera-credential-
at-rest question this lane's prior closure left open is now resolved to a
documented non-defect (plaintext at rest, no contract promises
otherwise -- see that report's own "Camera credential storage" section).
Zero reproduced Local Only/privacy defects across either milestone.

**Local Only.** Operational/default requirement. Confirmed met -- see
above.

**Derived Data Contribution.** Doctrine exists; confirmed **not yet
operationally implemented** -- Local Only / Privacy Closure v1 traced
every "contribution" occurrence in `src/mockingbird/` and found none is a
cloud-upload pathway (every real hit is an unrelated internal
scene-confusor-region bookkeeping concept). Do not assume operational
implementation or cloud backend exists. Never silently include:
image/video/audio; thumbnails/crops; raw frames; embeddings/reconstructable
media-derived features; local filesystem paths; free-text notes;
faces/people/vehicle imagery; precise property/home coordinates. The
moment this capability is actually built, it needs its own dedicated
privacy verification -- this lane's closure does not cover a capability
that does not yet exist.

**Media contribution.** Separate future consent capability. Contribution
must never become required for core operation.

### O. Platform / Runtime Portability

**Status:** CLOSED -- Platform / Runtime Portability & Support Truth
Closure v1 (2026-08-30) closed this lane at classification **A**; see
[platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md).

The canonical vocabulary is now: **Validated** (real release acceptance
on the real platform/runtime); **Structurally supported** (the stack
intentionally supports it, no unguarded defect known, hardware acceptance
incomplete); **Degraded / fallback** (an explicit, honestly-reported
limitation, never silent); **Unverified** (no current claim, genuinely
untested); **Unsupported** (known not to work, or excluded, and says so);
**Deferred** (potential future support, not part of this release). This
reuses this lane's own five terms verbatim plus folds in "Degraded /
fallback," which already existed as a real status value in the product's
own health model before this closure.

**Host:** native Windows -- **Validated** (the only Host with a packaged,
no-Python-required end-user distributable; real CUDA/BioCLIP/migration
evidence at the production code path, entirely reused from already-
accepted milestones). Linux -- **Structurally supported** at the source/
dev level only (continuously CI-validated on real `ubuntu-latest` for the
full Core suite, frontend build, and the Windows-packaging pipeline's own
structural smoke test; a genuine first-class Linux-only feature, the V4L2
local-USB-camera bridge, already exists) -- explicitly **not** "validated
release Host": no packaged end-user Linux distribution exists, and no
dedicated native-Linux hardware acceptance has ever been performed. macOS
-- **Unverified** overall; microphone capture specifically **Unsupported**
and already honestly disclosed (fixed in a prior accepted milestone).

**Runtime:** CPU -- the accepted detector (`onnx-cuda`, backing the
production `frame-driven-onnx-cuda` path) is **Unsupported** on CPU by
deliberate, regression-tested design (`session.disable_cpu_ep_fallback`,
CUDA-only provider list, `onnx_cuda_unavailable`/`onnx_cuda_no_fallback`
raised rather than silently degrading) -- there is no fallback, and this
is a tested guardrail, not a gap. Species (BioCLIP-2) and acoustic
(BirdNET) assistance are **Validated**, CPU-only by the identical
deliberate design, and never block Visit creation when unavailable.
NVIDIA CUDA -- **Validated** on native Windows (the strongest currently-
evidenced accelerated path); **structurally supported, hardware-
unverified** on native Linux specifically (identical code, zero OS
branch in the CUDA path itself, never separately proven on real Linux
hardware). Apple Silicon -- **Deferred** (zero active MPS selection code
in the accepted production path; no hardware available; extends
`docs/species-classification-reevaluation-promotion-v2-report.md`'s own
precedent rather than re-deriving it). AMD -- **Unsupported** (zero
ROCm/DirectML code anywhere in the stack).

**Camera Node:** Raspberry Pi 4 / Raspberry Pi OS remains the real,
repeatedly-validated reference hardware. The Camera Node's own software is
genuinely hardware-agnostic by protocol, verified against real code, not
merely asserted: a `CameraNodeProvider` abstraction backs both the
Pi-specific `PiCamera2Provider` and a real, independent
`V4L2CameraProvider` (generic Linux/USB via OpenCV), each degrading
gracefully (`setup_required`, never a crash) if its own runtime is
absent. No non-Pi hardware has ever been release-tested, and the matrix
does not claim otherwise.

Two narrow, reproduced capability-overclaim defects were found and fixed
in `python -m mockingbird doctor` (see §1/§3, above, for the full
account); two further gaps were found and precisely disclosed, not fixed,
since neither is reproduced against any real or currently-shipping path.
No new platform support was added; do not schedule a macOS port, an
Apple Silicon model-conversion campaign, or ROCm/DirectML implementation
as a consequence of this closure -- none is a release blocker, and none
was authorized.

### P. Release Engineering Foundation / Distribution

**Status:** CLOSED -- RELEASE-CRITICAL LICENSING/DISTRIBUTION REQUIREMENTS
COMPLETE. The owner's MIT decision is resolved and mechanical adoption is
now also complete -- a real `LICENSE` file, correct package metadata, and
README truth all exist and are proven to reach every official deliverable
this repository produces (see the 2026-09-06 MIT Source License Adoption &
Lane P Mechanical Closure v1 correction below). Release Engineering
Foundation v1 (2026-08-25) closed:
upgrade procedure (see Lane L); a real, currently-live dependency-closure
defect found and fixed via genuine native-Windows deployment (`astral`
missing from the packaged bundle -- would have broken *every* launch,
clean-install included) plus a regression test against the whole class of
drift; version single-source-of-truth; artifact provenance/checksum
parity with the Camera Node build script (`source_clean`); an independent
post-build artifact verifier (`scripts/verify_release_artifact.py`); this
repository's first CI automation (`.github/workflows/ci.yml` -- Core
gate, frontend build, a real structural packaging-smoke build);
`SECURITY.md`; release-artifact smoke testing; Host ↔ Camera Node
compatibility (investigated and confirmed adequate, not a gap). See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
for the complete record, including real native-Windows acceptance
evidence (Decision A).

Release Licensing, Distribution & Third-Party Legal Closure v1
(2026-08-30, see §1/§3, above) closed the second item this section
previously named: **full ffmpeg bundling**. Traced to every real
invocation site and every packaging/build script -- MockingBird never
bundles, downloads, or vendors an ffmpeg binary in any official package;
it is a pure external system dependency (`shutil.which("ffmpeg")`),
already honestly documented, and the recommended Camera Node golden path
needs no ffmpeg at all. A new build-time guard,
`verify_no_bundled_ffmpeg_binary`, now makes this posture durable rather
than merely accidental, mirroring the pre-existing BirdNET-weight-
exclusion guard's own role. The same milestone also added
`THIRD_PARTY_NOTICES.md` -- shipped inside every official Windows bundle,
correcting a real gap where the redistributed MDv5a/BioCLIP-2 model files
carried zero accompanying license/notice text (unlike an ordinary pip
dependency, whose own license already travels automatically).

**Corrected 2026-09-06 by Global Remaining Product-Development &
Release-Queue Reconciliation v1:** the owner has now explicitly selected
**MIT** for MockingBird's own source-code license -- the exact
owner-facing question Release Licensing, Distribution & Third-Party
Legal Closure v1's own decision packet posed. **The owner decision itself
is RESOLVED**, not reopened; do not re-litigate MIT vs. Apache-2.0. This
does **not** by itself close Lane P: verified empirically this session
that no `LICENSE` file exists anywhere in the repository, neither
`pyproject.toml` nor `web/package.json` carries any license metadata, and
`README.md`'s own "License" section still tells a reader the decision
"has not yet been finalized" -- all three would be false as of this
reconciliation if left unchanged. **Lane P moves to `OWNER DECISION
RESOLVED (MIT) -- MECHANICAL ADOPTION PENDING`**, not to closed. The
bounded next action (deliberately not performed in this reconciliation,
per its own governing brief's explicit instruction not to perform
follow-through unless necessary to make the scheduler truthful): add a
real `LICENSE` file with correct MIT text/copyright; add SPDX license
metadata to `pyproject.toml` (and, for consistency, `web/package.json`);
and correct `README.md`'s "License" section to state the resolved
decision instead of "not yet finalized." The still-unresolved BirdNET
commercial-adjacent-distribution question (§2, above) is a separate,
standing legal-review item with no available engineering action --
reconciled to **B+D** (blocks only commercial-adjacent use of the
optional acoustic feature, not all public launch) in the linked report's
"BirdNET legal posture" section, not resolved or newly blocking here.

**Corrected 2026-09-06 by MIT Source License Adoption & Lane P Mechanical
Closure v1** (see
[mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md](mit-source-license-adoption-lane-p-mechanical-closure-v1-report.md)):
performed exactly the bounded mechanical next action named above, all
three artifacts. A real `LICENSE` file now exists at the repository root
(standard MIT text; copyright `MockingBird contributors` -- the narrowest
formulation this repository's own text already established, used because a
single individual git identity is not by itself a defensible legal
copyright-holder string and no company/organization name exists anywhere
in the repository). `pyproject.toml` carries modern PEP 639 SPDX metadata
(`license = "MIT"`, `license-files = ["LICENSE"]`); this required raising
the `hatchling` build-system floor from `>=1.24` to `>=1.27`, empirically
proven necessary (not a preference) against a real version matrix: 1.24-
1.25 reject `license-files` as an array outright, 1.26 accepts it but
silently omits the modern `License-Expression`/`License-File` metadata
fields, and 1.27 is the first version confirmed to emit both correctly.
`web/package.json` gained a matching field. `README.md`'s "License"
section no longer says the decision is unfinalized. Distribution inclusion
was proven, not assumed: a real `pip wheel .` build of this repository
produced a real wheel whose `METADATA` carries `License-Expression: MIT`/
`License-File: LICENSE` and whose `dist-info/licenses/LICENSE` is byte-
identical to the repository's own file; a new `package_license` packaging
step (mirroring `package_third_party_notices` exactly) additionally copies
`LICENSE` to the official Windows bundle's visible root, alongside
`THIRD_PARTY_NOTICES.md`. `THIRD_PARTY_NOTICES.md`'s own two self-
referential sentences about MockingBird's own license status were
corrected to match; every third-party fact in that file is unchanged,
re-confirmed directly. **Lane P moves to `CLOSED -- RELEASE-CRITICAL
LICENSING/DISTRIBUTION REQUIREMENTS COMPLETE`.** The BirdNET commercial-
adjacent legal posture remains exactly as reconciled above (**B+D**,
separate and unaffected) -- per this milestone's own governing brief, it
does not by itself keep Lane P's own mechanical scope open.

Deliberately still open, not silently dropped, and unaffected by the
above: public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md`/
`THIRD_PARTY_NOTICES.md` (README/site polish, brand/trademark review)
remains open per "Public release readiness" in [roadmap.md](roadmap.md),
not release-critical blocking.

Release Engineering Foundation may occur before all product development is
finished. Release Engineering Foundation is not the same as final Release
Hardening.

### Q. Whole-Product UI / Accessibility / Performance

**Status:** CLOSED AS AN INTEGRATED PASS -- Whole-Product UI /
Accessibility / Performance Closure v1 (2026-08-27) closed this lane; see
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md).
Classification **A**.

Validated live against a seeded, product-shaped 371-Visit QA instance and
real code inspection: responsive behavior (zero horizontal overflow, 4
required widths x 10 pages); touch (existing tap-target/mobile-drawer
conventions intact); keyboard/focus (sidebar nav, mobile drawer already
correct; two real Fast Review focus-management defects found and fixed);
accessibility semantics (spot-checked, sound); large real-data performance
(measured, at or below established precedent, no regression); several
cameras (3 active mixed-health + 1 archived Stream, coherent); large
review queues (89-item backlog, correctly bounded); error/recovery UX
(camera-vs-observation-runtime distinction already correct); visual
consistency (StatusPill never color-only). Closed the bounded acoustic
health/status gap (Lane A) with the smallest capability-aware addition
the brief allowed. Found and fixed one P0 (Review Queue default-tab
misclassification of imported Visits) along the way -- the real,
previously-unidentified root cause of one class of confusion this project
had repeatedly misattributed to `reviewed-product-loop.spec.ts` being an
unrelated flake. That spec itself remains red, now precisely diagnosed as
test-suite staleness (a hardcoded `productMode = true` makes the legacy
markup it targets permanently unreachable), not a live product defect --
disclosed, not fixed, a real but separately-scoped follow-up. Also
disclosed, not fixed: Zone-polygon drawing (not selection) has no
keyboard equivalent (optional/advanced feature); a larger-than-previously
-documented dead-CSS footprint; a narrow raw-exception-text edge case.
See the report for the complete finding-by-finding record.

### R. Complete Field Acceptance

**Status:** CLOSED, per Lane R Release-Budget Adjudication & Gate A
Decision v1 (2026-09-07, see §3, above, and
[lane-r-release-budget-adjudication-gate-a-decision-v1-report.md](lane-r-release-budget-adjudication-gate-a-decision-v1-report.md)).
Closed from `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS`, the status recorded by Gate A True-Latency Tail Closure & Final
Lane R Decision v1 (2026-09-06) and reconfirmed unchanged by every session
narrated immediately below through Lane R Accumulated Latency Evidence &
Release-Budget Decision v1 (2026-09-07). That accumulated-evidence
milestone pooled all five intact, live-measured true-latency cohorts
(v9, v10, v14, Convergence v3, v4 -- 69 raw samples, six independent
calendar days), independently recomputed every statistic from raw data,
found and disclosed one non-material correction (v10's own published p90,
183.3s, corrected to 201.5s), and used a bootstrap-resampling analysis to
show the per-cohort p90 scatter long cited as "non-convergence" is
statistically consistent with ordinary small-sample noise around one
stable distribution -- then proposed, but explicitly declined to
self-adopt, a specific three-part budget for external acceptance. This
adjudication milestone independently re-verified every decisive fact in
that proposal against primary sources (including, read directly rather
than merely characterized, the rejected 2026-09-05 PASS's own two
disqualifying defects -- a recall denominator that excluded a known
failure mode, and a latency tail table that omitted v10's own 742.3-second
maximum) and found no decisive calculation wrong. **Accepted budget:**
typical latency ~80-115s (numeric, pooled median 103.9s, bootstrap 90% CI
[80.3s, 114.8s]); upper-tail behavior disclosed qualitatively, not as a
tight SLA (observed per-cohort p90 174-385s; pooled bootstrap p90 90% CI
[198.6s, 331.8s]); a 20-minute (1,200s) architectural decision-horizon
ceiling reference, not a statistically-fit maximum (every observed maximum
to date, 742.3s live-measured / 865.2s reconstructed-only, sits at
62-72% of it); sustained/crowded-activity latency disclosed together with
the already-accepted recall limitation as one product characteristic.
**Whole-scene recall stands exactly as the 2026-09-06 decision left it**
(v12 87.5%, v14 64.7% conservative / 61.1% broader, accepted known
limitation, no numeric floor) -- not re-litigated by this closure. **All
eight Gate A dimensions plus multi-subject Visit correctness now carry an
accepted disposition** -- six numeric budgets (false-Visit rate ≤15%,
fragmentation ≤5%, duplicates ≤2%, useful-evidence ≥85%, evidence-loss
≤15%, monitoring ≥97%, all unchanged from the 2026-09-05 correction below),
recall's accepted known-limitation status, true latency's budget above,
and multi-subject correctness (closed 2026-08-19/20, Phase 1/2/4). No
correctness defect was found anywhere in this evidence body. **This
closure does not start External Pre-Release Acceptance or Final Release
Hardening** -- both remain the correct next lanes in sequence but neither
is authorized by this milestone -- and does **not** update `roadmap.md`'s
own Gate A/"Numeric release budgets" prose, which still reads `OPEN`/"no
budget adopted" as of its own 2026-09-06 entries and is now stale relative
to this decision; reconciling that prose is explicitly out of this bounded
milestone's own scope and is disclosed here, not silently left
inconsistent. Disclosed, not actioned: an 18.5GB+ disk-reclaim opportunity
(archived, `SAFE_TO_RECLAIM` Windows dev-roots from v13/v14/Convergence v3)
remains available for a future session.

**Reconfirmed, no change (2026-09-06, Representative Daylight
True-Latency Tail Convergence v2):** an attempt to obtain the next
qualifying latency tranche was directly authorized and run, but stopped
before any deployment at the governing brief's own hard daylight gate
(local wall-clock 21:26-21:29 EDT on 2026-09-05, confirmed night via two
independent clocks) -- Classification B, WAITING FOR REPRESENTATIVE
DAYLIGHT. Zero new samples; the existing tail evidence above is unchanged.
See
[representative-daylight-true-latency-tail-convergence-v2-report.md](representative-daylight-true-latency-tail-convergence-v2-report.md).
The status line above stands exactly as written.

**Updated, additional evidence, no qualitative change (2026-09-07,
Representative Daylight True-Latency Tail Convergence v3):** the next
attempt at exactly this field action was directly authorized and this
time reached a full live session -- daylight gate passed (two-clock
cross-check, ~10.5 hours before dusk), one real packaging defect (a
`numpy` version-pin drift in `WINDOWS_RUNTIME_REQUIREMENTS`, identical
class to the already-fixed `idna`/`click` pins) found and fixed before
deployment (`f222217`), 76-minute session on the unchanged accepted
production stack. Result: 10 admitted candidates, **9 procedurally valid**
RTT-normalized samples -- short of the ≥12-sample target (median 112.2s,
tightly converging across five cohorts now at 82.9-115.7s; p90 385.1s, a
new high outside every prior cohort's own 173.9-318.5s band; max 482.4s,
inside the already-established 261.2-742.3s range). Both >300s samples
were fully traced to the ledger's own arbitration/continuity records -- no
new mechanism, no correctness defect. See
[representative-daylight-true-latency-tail-convergence-v3-report.md](representative-daylight-true-latency-tail-convergence-v3-report.md)
for the complete record, including the full per-sample table, causal
classification, and the honest observation that this session's own p90
finding leaves the tail's upper-percentile region *less* converged than
before it, even though the median and the outright maximum are both
reassuring. **The status line above stands exactly as written -- Lane R
remains OPEN, TRUE LATENCY TAIL EVIDENCE REMAINS.** No latency budget is
proposed or adopted. Disclosed, not actioned: the SAFE_TO_RECLAIM
disk-reclaim opportunity has grown to three archived dev-roots (~24.3GB,
now including this milestone's own archived instance).

**Tooling-readiness delta (2026-09-07, Field Acceptance Tooling
Correctness & Preflight Closure v1) -- substantive status unchanged, this
record is additive only.** See
[field-acceptance-tooling-correctness-preflight-closure-v1-report.md](field-acceptance-tooling-correctness-preflight-closure-v1-report.md).
Closed, with deterministic tests, exactly the five concrete procedural
gaps the v3 session above exposed: the `--dev-root` path-format
inconsistency that produced v3's own Defect #2 workaround; the
Windows-style acceptance-recorder-directory mistranslation that produced
v3's own Defect #3 (no independent recorder frames all session), now
additionally guarded by a new, independent, bounded pre-Observation
readiness gate (`scripts/field_acceptance_recorder_readiness.py`) the
*next* field procedure must run and honor before committing to a full
session (`STOP BEFORE OBSERVATION` on failure, never merely a warning);
no tracked, tested session-stop-timing driver existed anywhere in this
repository before this milestone (every real cohort through v3 drove the
45-minute-minimum/75-minute-maximum/≥12-sample-target contract, and the
post-stop-finalization ledger-snapshot ordering, by operator judgment
alone) -- both are now enforced, tested code
(`scripts/field_acceptance_session_driver.py`). **Concrete remaining
blockers for the next Lane R field tranche, none removed by this
milestone: the ≥12-sample threshold itself (v3 reached 9); the tail's
upper-percentile (p90) region, which v3's own session left less converged
than before it, not more.** No new field evidence; no latency budget
proposed; Lane R's own status line above is unmodified by this entry.

**Integration-readiness delta (2026-09-07, Field Acceptance End-to-End
Integration Proof v1) -- substantive status unchanged, this record is
additive only.** See
[field-acceptance-end-to-end-integration-proof-v1-report.md](field-acceptance-end-to-end-integration-proof-v1-report.md).
Closed, with 12 new real-subprocess/real-fake-service tests, all three
integration limitations the tooling-correctness milestone above named as
out of its own scope: the actual `field_acceptance_session_driver.py run`
CLI entry point; the recorder-readiness `--dev-root` process-liveness
branch against a genuinely running process; and the complete field-tooling
sequence end to end as one bounded simulated scenario. No integration
defect found or reproduced in production code. No new field evidence; no
latency budget proposed; Lane R's own status line above is unmodified by
this entry.

**Updated, additional evidence, narrows both named blockers without
closing either (2026-09-07, Representative Daylight True-Latency Tail
Convergence v4):** the next attempt at this exact field action was
directly authorized and ran the first real field session using the
fully-hardened recorder-readiness gate and monotonic session driver the two
entries immediately above built and proved -- both worked exactly as
designed. Daylight gate passed (three-clock cross-check, ~3.5 hours before
dusk); 75-minute session on the unchanged accepted production stack.
Result: 11 admitted candidates, **11 procedurally valid** RTT-normalized
samples (zero invalid) -- short of the ≥12-sample target for a second
consecutive session (median 94.5s, reinforcing convergence across five
intact cohorts at 82.9-115.7s; p90 258.7s, back inside the pre-v3 band,
easing but not resolving v3's own divergence finding; max 429.4s, inside
the already-established 261.2-742.3s range for a second consecutive
cohort). Ledger reconciliation was fully `COMPLETE` for the first time in
this milestone family's own history, and the independent recorder ran with
zero gaps exceeding 10 seconds all session -- directly closing, live, the
exact recorder-verification gap v3's own Defect #3 exposed. The sole
>300-second sample was fully traced to the same already-accepted
arbitration/sustained-activity mechanism, corroborated by real
independent-recorder frames for the first time alongside an intact live
cohort. One admitted candidate is, on direct visual review, more likely a
disclosed person/domestic-pet confound than a wild bird (already
-characterized class, not new; its latency measurement is retained
unmodified). See
[representative-daylight-true-latency-tail-convergence-v4-report.md](representative-daylight-true-latency-tail-convergence-v4-report.md)
for the complete record, including the full per-sample table and causal
classification. **The status line above stands exactly as written -- Lane
R remains OPEN, TRUE LATENCY TAIL EVIDENCE REMAINS.** No latency budget is
proposed or adopted. **Concrete remaining blockers for the next Lane R
field tranche, both narrower than before, neither closed: the ≥12-sample
threshold itself (v3 reached 9, this session reached 11); the tail's
upper-percentile (p90) region, which this session's own 258.7s eases back
toward the pre-v3 band without yet forming, across all five intact
cohorts, a single convergent band the way the medians already have.** One
new, minor, disclosed-not-fixed tooling gap found:
`field_acceptance_instance_lifecycle.py mark-archived --evidence-archive`
does not resolve a Windows-style path the way `--dev-root` now does (a
WSL-style path workaround succeeded immediately).

**Prior status (immediately preceding, 2026-09-05):** OPEN --
RELEASE-CRITICAL -- RELEASE DECISION REQUIRED, per
Gate A Whole-Scene Budget & Remaining-Evidence Correction v1 (2026-09-05,
see §3, above, and
[gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md](gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md)),
correcting the `CLOSED / PASSED` claim immediately below, which was
**not accepted**. Six of eight release dimensions (false-Visit rate on
ordinary scenes, fragmentation, duplicates, useful-evidence,
evidence-survival, monitoring coverage) are genuinely READY FOR RELEASE
BUDGET -- see `roadmap.md`'s "Numeric release budgets" for the corrected
figures. Whole-scene end-to-end recall (no failure-reason denominator
exclusion; v14's own conservative 11/17 = 64.7% stays in the denominator)
is **RELEASE DECISION REQUIRED**: the ambiguous-boundary sustained/crowded
mechanism producing v14's low end is fully root-caused and confirmed
unfixable with any currently-trustworthy signal by two independent
adversarial investigations, so what remains is an explicit
product-risk-tolerance judgment for the release authority, not an
engineering gap. True capture-to-visible latency is **MORE EVIDENCE
REQUIRED** (median converges across four cohorts; the tail does not --
observed maxima span 261.2-865.2 seconds, including v10's own
already-accepted 742.3-second maximum and a newly-recovered v11 maximum of
865.2 seconds this correction's own offline reanalysis surfaced). The
chronological field-acceptance history immediately below (2026-08-19
through Sustained / Crowded Ambiguous-Boundary Recall Correctness v2) is
preserved, unchanged, as the complete evidentiary record both the rejected
reconciliation and this correction rest on.

**Superseded status (2026-09-05, Gate A Release-Budget & Evidence
-Sufficiency Reconciliation v1's own claim -- NOT ACCEPTED, preserved here
verbatim as the record of what was proposed and rejected, not as current
status):** CLOSED / PASSED -- RELEASE-CRITICAL, per Gate A Release-Budget
& Evidence-Sufficiency Reconciliation v1 (2026-09-05, see §3, above, and
[gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md](gate-a-release-budget-evidence-sufficiency-reconciliation-v1-report.md)).
Explicit numeric release budgets accepted across recall (with the
ambiguous-boundary sustained/crowded mechanism carved out as an accepted,
disclosed limitation rather than folded into the number), false-Visit
rate, fragmentation, duplicates, useful-evidence, evidence-survival,
median latency, and monitoring coverage -- see `roadmap.md`'s "Numeric
release budgets" for the accepted figures. Residual, explicitly
non-blocking limitations remain (named in full in the linked report's own
"Residual risks / known limitations"); none is a Gate A blocker. The
chronological field-acceptance history immediately below (2026-08-19
through Sustained / Crowded Ambiguous-Boundary Recall Correctness v2) is
preserved as the complete evidentiary record this closure rests on, not
superseded or deleted.

**Prior status (before the above; this is the accurate pre-2026-09-05
status):** NOT DONE -- RELEASE-CRITICAL.

Component acceptance is not whole-product acceptance. Final integrated
release configuration should exercise: several cameras; visual inference;
audio if included; review; Today/history; long unattended operation;
disconnect/reconnect; Host reboot; Camera Node reboot; storage pressure;
model unavailable; backup/restore; upgrade; clean installation; actual
user operation. Remote LTE field acceptance remains separately scoped when
Remote Field is not part of release scope.

**Representative Field Acceptance & Release-Budget Closure v1 (2026-08-25)
attempted, returned Gate C -- OPEN, insufficient representative evidence.**
Not a product defect: the attempt was stopped before any Observation
session started because the native-Windows dev instance now enforces real
sign-in on every endpoint the session needed (streams, observation start/
stop, Visits, counterfactual ledger -- the pytest auth bypass was removed
as part of the accepted Local Identity / Multi-User work, 2026-08-23),
no credentials exist anywhere in this repository, and the user explicitly
declined to share real admin credentials, create a temporary account, or
participate live right now. Nothing about the frozen perception/admission/
Visit/evidence/classification stack was exercised or judged. Real,
positive, non-live evidence preserved from this attempt: the reference
Camera Node (`192.168.1.112:8787`) is reachable at the network level; the
native-Windows Host dev deployment is healthy at the accepted commit
(schema v53); the full accepted acceptance-tooling chain (recorder,
motion-screen/contact-sheet review, independent encounter table,
counterfactual ledger, `run_encounter_accounting.py`) is confirmed present
and ready to reuse. See
[representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md)
for the full record, including the standing decision for future sessions:
do not ask the user again for real credentials or live participation
unless a future milestone specifically requires human acceptance and they
explicitly agree first; ordinary auth-requiring development/validation
work should instead use a fresh, isolated dev instance with a disposable
bootstrapped local Administrator account.

**Representative Multi-Camera Field Acceptance & Release-Budget Evidence
v1 (2026-08-26) attempted, also returned no new live-field evidence --
classification B, an acceptable outcome per this milestone's own governing
brief, and a materially different shape from the 2026-08-25 attempt
above.** Not blocked by authentication this time: the session start
(20:26 EDT) was after sunset, the same "darkness produces an unusable bird
denominator" scenario 2026-08-19/2026-08-20 already demonstrated twice: a
post-sunset session produces a clean, real, but useless zero-track-
generation result, not evidence about daytime bird activity. No
Observation session was opened. Executed the "no representative
conditions" path instead and used the time to make the next daylight
session concretely more ready, not merely re-documented: found and fixed
one real, previously-hidden Windows build defect (a `click` dependency-
pin gap identical in mechanism to this codebase's own already-documented
`idna` pin) that would otherwise have cost the next session its own
debugging time; produced a fresh, independently-HTTP-verified, ledger-
retained deployable artifact of accepted HEAD ready for instant relaunch;
confirmed GPU/detector/storage/Camera-Node health; confirmed, via the
unauthenticated health endpoint only, that only one real Stream is
currently configured in the dev instance and that a second real, already-
supported Source (a Windows-native USB webcam, already hardware-validated
for the Acoustic milestone) should be wired up before the next session so
the still-open "does the concurrent-persistence fix hold under genuine
multi-camera load" question can actually be tested with two real cameras;
and documented the exact command/API sequence, acceptance-recorder
settings, and structured-log location (`.../userdata/logs/mockingbird.
log`) that session needs. See
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
Gate A's evidence body is unchanged by this session (still exactly the
two real 2026-08-19/2026-08-20 daylight cohorts) -- no release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

**Representative Daylight Field Acceptance & Gate A Evidence v2
(2026-08-28) attempted, also returned no new live-field evidence --
classification B.** For the first time in three consecutive attempts,
every environmental/infrastructure precondition was simultaneously
satisfied: session start ~15:20 EDT (mid-afternoon, hours before sunset --
unlike the 2026-08-26 attempt), reference Camera Node healthy and
reachable (`GET /node/v1/health`: `status: "available"`, self-test
passed, watchdog healthy, zero consecutive probe failures), GPU idle and
available (RTX 4060 Ti, zero MockingBird compute process at check time),
storage adequate, acceptance-recorder confirmed present and structurally
isolated from product truth. The sole remaining blocker, isolated more
precisely than either prior attempt could isolate it, is the identical
authentication precondition from the 2026-08-25 attempt above,
re-confirmed today against a freshly rebuilt and redeployed current
accepted HEAD (`80e1bb3`): `GET /api/streams` and `GET /api/visits` both
returned `401`, with no credentials attempted. Per the standing decision
above, no credentials were requested, no fresh disposable instance was
substituted for the real one, and production authentication was not
touched. The fresh deploy itself hit one cold-start false-negative (the
tool's own bounded 90-second verification window gave up before BioCLIP/
CUDA cold start finished) -- manually confirmed healthy and identity-exact
(`git_commit` exact match, schema 57, `ready: true`) via direct HTTP and a
follow-up `--status` check, matching an already-documented recurring
pattern, not a new defect; then stopped cleanly, leaving `80e1bb3`
retained and ledger-verified. Confirmed, again via the unauthenticated
health endpoint only, that the second real Source (the EMEET SmartCam
S600 USB webcam identified 2026-08-26) remains unwired -- adding it needs
the same authenticated path. Investigated one hypothesis for the
continuing `C:` free-space decline (43.07GB on 2026-08-20 -> 18.8GB today)
-- retained Windows dev-release accumulation -- and ruled it out (25
retained releases total only ~700-750MB; each release is ~29MB, not a
multi-GB per-release duplication); the actual cause remains open. Gate
A's evidence body is unchanged -- still exactly the two real
2026-08-19/2026-08-20 daylight cohorts, now for the third consecutive
attempt, two of the three blocked by the identical authentication
precondition. No release budgets proposed. See
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md).

**Non-Interactive Field Acceptance Authentication & Session Access v1
(2026-08-28) closed the authentication half of the recurring blocker
above, at classification A -- see §1/§3, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record.** A narrow, non-interactive, bearer-token "Field
Acceptance Operator" credential (schema v58) now lets bounded
field-acceptance tooling authenticate without an operator's personal
password, proven live against a real running instance of the exact
mechanism (the identical three previously-blocking endpoints -- `GET
/api/streams`, `GET /api/visits`, `POST .../observation/start` -- all
still correctly `401` unauthenticated, then all succeed with the new
credential, including a real Observation start/stop cycle). This closes
the *authentication* precondition specifically -- it does **not** by
itself close Lane R/Gate A, does **not** run the field session, and does
**not** authorize the next attempt; Gate A's evidence body is unchanged --
still exactly the two real 2026-08-19/2026-08-20 daylight cohorts. The
next daylight session still needs its own separate authorization plus
representative daylight/weather/health conditions (unrelated to
authentication, and not something this milestone could control), but no
longer needs to ask the operator for credentials or route around the
blocker -- see this milestone's own report for the exact one-time
provisioning command.

**Representative Daylight Gate A Field Acceptance v4 (2026-08-29) ran
the first real live daylight session under the new credential, at
classification A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
for the full record.** Deployed to a genuinely fresh, disposable instance
(never the operator's `MockingBirdDev` identity), resolving a real
conflict the credential-closure milestone did not anticipate: the
reference Camera Node's pairing is single-slot/disk-persisted, so a
truly fresh instance cannot reach it without a reset -- done via the
already-documented, supported recovery flow, with the user's explicit,
specific approval (not assumed), leaving the operator's own
`MockingBirdDev` instance needing a one-time re-pair before its own next
use. A real ~112-minute Observation session followed against the real
Stream, with the independent acceptance recorder running throughout
(99.78% coverage) and real, sustained, near-continuous multi-bird feeder
activity directly visually confirmed (full-resolution frames, not
inferred) for effectively the entire session. `candidates_created`
stayed at exactly 0 the whole time -- a real, previously-undocumented P0
admission-arbitration gap (sustained near-continuous activity structurally
starves the `continuation_pending`/`blocked_ambiguous_boundary`
resolution mechanism, whose only design-intended escape, session-end
finalize, did not visibly rescue this session's own real stop either --
left as a precise, disclosed open question) was found and precisely
root-caused by direct code reading, not fixed -- a trustworthy fix is
comparable in scope to a full milestone, not a bounded change, per the
governing brief's own explicit bar. Gate A's evidence body now has a
**third** real cohort, structurally different from the first two
(sustained multi-subject activity at a busy feeder, vs. the sparser
single-subject encounters 2026-08-19/2026-08-20 each captured) -- three
real cohorts now span 0% to 68.2% end-to-end Visit recall. No release
budgets proposed; the report's own reasoning is explicit that this range
does not converge into a budget until the newly-found defect is fixed
and re-measured. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone.

**Sustained-Activity Visit Admission Starvation & Stop-Finalization
Correctness v1 (2026-08-29) fixes the P0 the field session immediately
above found, at classification A -- see §1/§3, above, and
[sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
for the full record.** Root cause confirmed structural, not a
wrong-value bug: individual episodes were already correctly bounded, but
nothing bounded how long a whole connected *ambiguous component* could
keep deferring while its own currently-active tail kept being refreshed
by sustained real activity -- deterministically reproduced (26 simulated
minutes of continuous activity, zero admissions, exactly the field
symptom) against the real, unmodified pre-fix code before being fixed
with a bounded decision horizon reusing the existing, already-calibrated
20-minute episode-span bound (never a new magic number, never the 45s
gap value itself). The field report's own separate, disclosed-open
"did stop rescue anything" question is independently root-caused (a
real external/background-thread revert-to-shadow race, deterministically
reproduced and fixed) and confirmed **not** the same mechanism as the
starvation defect. Investigating the evidence-cache bound's own possible
contribution (per this milestone's own governing brief) found and fixed
two further real, narrow, pre-existing defects that would otherwise have
kept producing the identical "zero Visits" symptom one gate later
(`blocked_missing_evidence`) even after the primary fix -- neither the
128-entry bound's own size nor the 45-second gap value were changed. A
105-simulated-minute, two-simultaneous-subject stress replay confirms
bounded, non-starved, non-duplicated, non-contaminated admission
end-to-end. Tier 2: 505 passed, 0 failed (22 files, the brief's own
named subsystem list). Tier 3 (full Core): 5238 passed, 3 failed (all 3
independently confirmed pre-existing/unrelated, not merely assumed --
see the report for the direct bisection/repeated-run evidence), 3
skipped, 23 deselected, 11 xfailed. No schema change. This closure does
**not** itself close Lane R/Gate A -- no live field session ran, per
this milestone's own explicit non-goal (§20: "do not launch a real
wildlife Observation tonight... a real daylight field rerun belongs
AFTER this implementation milestone is accepted") -- and does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. The next daylight session
against a busy, real feeder Stream is what Gate A still needs: proof
that `candidates_created` is no longer stuck at 0 under real sustained
activity, that admission happens well before session end (not only at
stop), that a real stop against genuinely pending work resolves
honestly, and that multi-subject correctness holds through to real
admitted Visits under real conditions -- the one dimension the
motivating field session could not exercise at all, since nothing there
ever reached admission. See the milestone's own report, "Field-rerun
requirement," for the complete, precise list.

**Representative Daylight Gate A Field Acceptance v5 (2026-08-30) ran the
first real daylight session against the corrected build, closing every
item that milestone's own "Field-rerun requirement" named, at
classification A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
for the full record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node
via the identical documented recovery flow v4 used, with the user's
explicit approval. A real ~106.6-minute Observation session followed
against the same real Stream/scene v4's own busy-feeder session used,
with the independent acceptance recorder running throughout (~99.99%
temporal-span coverage, ~5,147 frames). `candidates_created` reached its
first real admission ~25 seconds into the session and climbed steadily
throughout -- 19 real Visits admitted by session end, not merely at
stop, directly confirming the accepted fix under real sustained genuine
activity. Stopped deliberately into a moment with substantial genuinely
pending work; the new `stop_finalization_pending` status was observed
live for the first time in a real field session, correctly appearing
then clearing while the finalize tick genuinely rescued 2 more pending
candidates (17 -> 19) -- directly answering v4's own left-open "did stop
rescue anything" question. Zero `blocked_shadow_mode`, zero persistence-
contention, zero duplicate Visits across the whole session -- no
recurrence of any of the three defects that milestone fixed. Multi-
subject correctness remains only partially advanced: real simultaneous
multi-bird presence was directly confirmed in-scene, but no two Visits
this session shared a single Event as genuinely concurrent siblings, so
that specific mechanism was not exercised end-to-end either. One real
defect was found and precisely root-caused, not fixed, per the governing
brief's own bar: a single false-positive admission (a weak, single-
detection, `terminal_reason: maximum_unsupported_duration` localization)
received a confident ("Brown Thrasher," 89.9%) but wrong BioCLIP species
label on a crop that direct pixel-region inspection against its own real
bounding box confirms is empty background -- a fresh, concretely-
reproduced instance of the already-known Gate B "background evidence ->
confident label" regression class `roadmap.md` already names as open
work (see Gate B, [roadmap.md](roadmap.md)), not a new starvation-family
defect and not release-blocking for this milestone's own scope. Gate A's
evidence body now includes a fourth real cohort, and the first
post-fix one: three prior cohorts spanned 0% to 68.2% end-to-end Visit
recall; this session found no missed genuine encounter via targeted
(not exhaustive) independent review, qualitatively far closer to
complete than either prior busy-feeder or sparse-encounter cohort. Two
candidate release budgets are proposed for review, from convergent
evidence across all four real cohorts, not self-accepted: minimum
monitoring coverage ~99% (all four cohorts measured 99.6%-99.99%) and
minimum useful-evidence rate ~85% (two independent measurements, 88.2%
and 94.7%, with no contrary evidence). Recall/false-Visit-rate/
fragmentation-rate budgets are explicitly *not* proposed -- this
session's own figures are the first post-fix measurement of each, not
yet a second, independently-varied confirmation. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening,
and does **not** select a next development milestone. Remaining Gate A
dependency, in priority order: (1) a second post-fix daylight session
exercising conditions v5 did not (genuinely simultaneous multi-subject
admission, and/or a sparser single-subject scene re-run post-fix) to
convert this session's own single strong data point into the broader
body of field evidence Gate A budgets require; (2) only then, propose
numeric release budgets for recall/false-Visit-rate/fragmentation-rate
with real cross-session convergent support. The one disclosed defect
this session found remains open Gate B work, not blocking Gate A
directly.

**Post-v5 Global Product-Roadmap Reconciliation & Gate A Next-Step
Authorization (2026-08-30).** Documentation/governance-only -- reconciles
this file and `roadmap.md` to agree on the v5 result above and names the
exact next Lane R milestone: see §3, above, for the full authorized
contract (**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche**, not yet run). Two budget
dimensions -- minimum monitoring coverage (~99%) and minimum
useful-evidence rate (~85%) -- move to **READY FOR FORMAL BUDGET REVIEW**
(candidate values proposed across all four real cohorts to date, not yet
formally accepted release budgets); recall, false-Visit rate,
fragmentation rate, and capture-to-visible latency remain
evidence-accumulated only, with no candidate value proposed -- see
`roadmap.md` "Numeric release budgets" for the complete reconciled
accounting. No numeric recall budget is introduced by this reconciliation;
v5's own qualitative "no missed genuine encounter found via targeted, not
exhaustive, review" conclusion is preserved exactly as reported, not
converted into a recall percentage. Gate A/Lane R remains open. This
reconciliation does not authorize External Pre-Release Acceptance or
Final Release Hardening, and does not itself run the next field session.

**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche (2026-08-31) ran the second real
daylight session against the corrected build, at classification **B**,
not A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
for the full record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node
via the identical documented recovery flow v4/v5 used, with the user's
explicit approval. A real 106.63-minute Observation session followed
against the same real Stream/scene, a genuinely different daylight window
(09:19:59-11:06:37 EDT, mid-morning) than v4's or v5's own, with the
independent acceptance recorder running throughout (~99.4% temporal-span
coverage, 5,214 frames). Two exhaustively-reviewed real activity windows
(directly confirmed via full-resolution independent-recorder frames, not
inferred, each containing genuine simultaneous multi-bird moments -- 2
birds at 25.79min, 2-3 birds in an active flurry at 90.50min) together
produced **zero** admitted Visits: `candidates_created` stayed at exactly
0 for the entire session, despite `track_updates_observed` reaching
11,078 and `proposals_observed` reaching 521. Directly root-caused by
reading the real arbitration source (`candidate_visit_authority.py`,
`engine_runtime.py`) against the real, fully-reconstructed counterfactual
ledger (521 records, cross-verified lossless): this is **not** a
recurrence of v4's own starvation mechanism -- `resolve_ambiguous_
boundary_arbitration` reached a decision for every real ambiguous
component on schedule throughout (164 proposals correctly, permanently
`blocked_ambiguous_boundary` as non-winning cluster members; the intended
"at most one Visit per cluster" behavior working exactly as designed). The
actual loss mechanism is one gate later: 48 of 263 distinct proposals
(18.3%, spread across the *entire* session, not one isolated cluster)
reached a genuine arbitration win and then permanently failed at the
evidence-availability gate (`blocked_missing_evidence`/`no_persistable_
evidence_bytes`), because the shared, session-global, insertion-order-only
128-entry evidence-byte cache had already evicted that specific winner's
own bytes by the time its own (correctly, if belatedly, computed)
arbitration turn arrived -- and because that outcome is not in
`RETRYABLE_OUTCOMES`, no code path ever re-attempts the same resolved
component with its own second-best member. This is not a new defect
class: `engine_runtime.py`'s own `_MAX_CACHED_BURST_BYTES` history
comment already named almost exactly this mechanism when the bound was
last raised 32->128 and explicitly declined to fix it structurally ("a
pending-proposal-aware eviction policy... is a materially larger
change... left as a disclosed follow-up, not undertaken here"); v5's own
report separately named the same residual in the abstract. v6 is the
first real, concrete, session-wide *measurement* that this is not a rare
edge case (18.3% of distinct proposals this session, versus v5's own
2.8%), and the first evidence that it also reaches the *ordinary*
(non-forced, confidence-ranked) arbitration path, not only the
recency-forced path the original disclosure discussed. Stop-finalization
itself behaved correctly (the honest `stopping`/`stopped` cycle with
`stop_finalization_pending` was observed live exactly as the accepted
contract specifies, rescuing 0 -- consistent with, not a regression of,
the root cause: nothing cleanly resolvable remained pending at stop,
since every real activity window's own fate had already been permanently
decided earlier in the session). Zero `blocked_shadow_mode`, zero
persistence contention, zero ERROR/CRITICAL/WARNING lines across the full
164-line structured session log. Background/empty-evidence eligibility
and species assistance were not exercisable this session at all (zero
admitted Visits ever reached either layer) -- disclosed as honest
measurement gaps, not fabricated proof; the accepted `26edddf` fix's own
two files are confirmed byte-for-byte unmodified this session. Real,
directly-confirmed simultaneous multi-subject activity occurred (not
manufactured) but never reached an admitted Visit either, so multi-subject
Visit-grouping correctness remains completely unexercised end-to-end
across two consecutive post-fix cohorts now, for two different reasons (v5:
nothing happened to be concurrent among what *was* admitted; v6: nothing
was admitted at all). Two bounded, tested, own-session deploy-tooling
defects were found and fixed along the way (a real `UnicodeDecodeError`
crash in `_run_powershell`'s non-UTF-8 PowerShell-output handling that was
masking a real, unrelated failure, proven RED->GREEN with a new hermetic
regression test; a separate, disclosed-not-fixed `--dev-root` WSL-path
usability gap that caused the underlying masked failure) -- zero product/
perception/admission/Visit/evidence/classification code touched; full
`tests/test_deploy_windows_dev.py` 124/124 passed, `ruff` clean. Per the
milestone's own explicit §14 failure conditions ("prolonged real sustained
activity + `candidates_created` remains zero" is explicitly met) and its
own §35 acceptance bar ("post-fix admission behavior replicates"/
"in-session admissions occur" are both explicit Classification A
requirements that did not hold), this report deliberately does not round
up to Classification A on the strength of the investigation's own rigor
alone -- see the report's own "Decision" section for the complete
reasoning. This closure does **not** authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone. **Remaining Gate A dependency, in priority order, superseding
the priority order the prior reconciliation above named:** (1) fix and
then field-re-prove the evidence-cache-exhaustion/no-runner-up-fallback
mechanism this session concretely measured -- now the single most
consequential open Gate A correctness question; (2) a daylight session
that actually achieves real in-session admissions *and* genuine concurrent
multi-subject siblings, still never jointly observed; (3) background/
empty-evidence eligibility remains field-unproven a second time (not
urgent -- the fix's own dedicated milestone already validated it
thoroughly via reproducer plus real-cohort benchmark; still open as live
confirmation); (4) the four still-immature numeric budgets (recall,
false-Visit rate, fragmentation/duplicate rate, capture-to-visible
latency) remain resting on v5's own single post-fix data point --
unchanged, not converged, by this session's own zero-admission result.
No numeric budget is withdrawn or newly proposed by this reconciliation --
monitoring coverage (~99.4% this session) remains consistent with its
existing ~99% candidate; useful-evidence rate is neither confirmed nor
refuted (no admitted Visits to measure it over) and its existing ~85%
candidate is unchanged.

**Pending-Proposal Evidence Preservation & Arbitration Fallback
Correctness v1 (2026-08-31) closes dependency (1) immediately above, at
classification A -- see §1/§3, above, and
[pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
for the complete record.** The evidence-cache-exhaustion/no-runner-up-
fallback mechanism v6 concretely measured is fixed: bounded, pending-
proposal-aware preservation and deterministic same-component fallback,
both implemented and independently tested, deterministically reproduced
(both required RED reproducers plus a 105-simulated-minute v6-shaped
replay against the real bounded cache, all RED on `b37656d`/GREEN after
the fix). This is a deterministic, implementation-level closure only --
per this milestone's own explicit non-goal, no field session ran, so
dependency (1)'s own second half ("...then field-re-prove") remains
genuinely outstanding, now promoted to the single most important
remaining item below. **Remaining Gate A dependency, in priority order,
superseding the priority order immediately above:** (1) a daylight
session that actually achieves non-zero in-session `candidates_created`
under sustained real activity -- the field proof this fix's own
deterministic reproduction cannot itself provide, and the core open
question three consecutive real cohorts (v4, v5's own partial success,
v6) have now circled around for three different underlying reasons; (2)
that same session, or a later one, jointly observing real in-session
admissions *and* genuine concurrent multi-subject siblings, still never
jointly observed across any real cohort to date; (3) background/
empty-evidence eligibility remains field-unproven a second time (not
urgent -- unchanged from the prior reconciliation's own reasoning); (4)
the four still-immature numeric budgets (recall, false-Visit rate,
fragmentation/duplicate rate, capture-to-visible latency) remain resting
on v5's own single post-fix data point, unchanged by this closure (a pure
implementation-correctness milestone with no field session provides no
new data point for any of the four). No numeric budget is withdrawn or
newly proposed by this reconciliation. Gate A/Lane R remains open. This
closure does **not** authorize the next Representative Field Acceptance /
Gate A session, External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone --
authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged, per §3, above.

**Representative Daylight Gate A Field Acceptance v7 -- Evidence-Preservation
/ Arbitration-Fallback Re-Proof (2026-08-31) ran the field session the
pending-proposal fix's own report named as outstanding, at classification
**A** -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
for the complete record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node via
the identical documented recovery flow v4/v5/v6 each used, with the user's
explicit approval. A real ~89.4-minute Observation session followed against
the same real Stream/scene, with the independent acceptance recorder running
throughout (99.989% temporal-span coverage, 3,848 frames) after a real
deploy-tooling defect (found and fixed in its own commit, zero product code
touched) that had left it silently unarmed for a discarded ~2m26s preliminary
session. `candidates_created` reached its first real admission ~6.6 minutes
into the session and climbed steadily throughout to **25** by session end
(24 in-session, 1 rescued by stop-finalization) -- directly reversing v6's
own zero and exceeding v5's own 19. Six real, natural fallback attempts
occurred (five admitted, one honestly exhausted), three fully reconstructed
end to end against the real counterfactual ledger (merged losslessly across
11 periodic snapshots to survive the ledger's own 60-minute eviction window
over an 89-minute session): in each of the two successes, the highest-
confidence component member failed at the evidence-availability gate exactly
as v6 diagnosed, and the runtime's own next-ranked member was admitted
within tens of milliseconds, in the same tick; in the one exhaustion, both
members of a two-member component carried extremely weak evidence
(confirmed, on direct visual review, to be genuine noise, not a real
missed animal), and the mechanism correctly gave up rather than fabricate an
admission. **Zero instances of the unacceptable "component silently
discarded while a viable member exists" outcome were found anywhere directly
traced.** `blocked_missing_evidence` fell from v6's own 18.3% to **9.4%** (18
of 192 distinct proposals), roughly halved. Genuine concurrent multi-subject
admission was directly visually confirmed for the first time across any Gate
A cohort -- two independent sibling-Event pairs, each with disjoint
underlying tracker evidence, one pair's own admission additionally requiring
the fallback mechanism at the same time (the first observed interaction
between the two previously-separately-proved mechanisms) -- closing the
other half of the "Remaining Gate A dependency" the prior reconciliation
named. A real, first-ever exercise of the pre-existing
`max_candidates_per_hour: 20` rolling budget occurred (no prior cohort ever
produced enough real admissions to reach it) and was confirmed to
self-clear correctly, not stick. All 25 admitted Visits were individually
reviewed against real, native-resolution recorder frames (not a sample):
96.0% useful-evidence rate (24/25), and one real, confirmed false Visit
(empty background, correctly receiving no automatic species label under the
already-accepted geometry-corroboration fix -- the false *admission* itself,
not a false *label*, is the still-open, unaffected-by-this-milestone Gate B/
admission-precision residual `roadmap.md` already names). Zero genuine
duplicate Visits across all 25 admissions, verified by the strongest test
applied to any cohort to date (zero tracker evidence shared between any two
admitted Visits). Two exhaustive-denominator windows (6.5 minutes and 70
seconds, deliberately this session's own hardest moments -- both fallback
events, the exhaustion, and the multi-subject admission, not a favorable
sample) found 3 of 3 real encounters represented by a useful admitted Visit.
Zero persistence contention, zero `blocked_shadow_mode`, zero ERROR/
CRITICAL/WARNING lines across the full session log. Honestly disclosed, not
treated as a regression: a concrete field instance of the already-named,
not-yet-benchmarked crowded-feeder/NMS gap (a third real, simultaneous bird,
directly visually confirmed, that the detector itself never separately
perceived -- most plausibly NMS suppression at close range, per `roadmap.md`
Gate A's own already-recorded open dimension). This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. **Two further numeric budget
dimensions move to READY FOR FORMAL BUDGET REVIEW** (maximum false-Visit
rate, candidate ~5-10%, from two convergent post-fix measurements: v5's 5.3%
and this session's own 4.0%; maximum duplicate-Visit rate, candidate ~0%/low
single digits, from two convergent zero measurements), alongside the two
already-proposed dimensions this session's own measurements strengthen
(monitoring coverage ~99%, now a 5th convergent cohort at 99.989%;
useful-evidence rate ~85%, now a 3rd convergent post-fix cohort at 96.0%) --
`roadmap.md` "Numeric release budgets" itself is not updated by this
reconciliation, per this milestone's own explicit scope. Minimum end-to-end
Visit recall and maximum fragmentation rate remain evidence-accumulated
only -- this session's own 3/3 exhaustive-window recall and its own
zero-shared-evidence duplicate/fragmentation test are real, positive,
convergent-direction data points, but methodologically distinct from v5's
own full-session-review recall figure and its own `cluster_encounters`-based
fragmentation figure respectively, so neither is yet a second directly
comparable number. Maximum capture-to-visible-Visit latency remains
unmeasured by any cohort to date. **Remaining Gate A dependency, in priority
order, superseding the priority order immediately above:** (1) a
directly-comparable second fragmentation-rate measurement (an offline pass
over this session's own already-preserved merged ledger, not a new field
session, could close this); (2) a second live cohort producing a genuinely
crowded, 3+-simultaneous-subject moment, to stress-test whether the
disclosed crowded-feeder/NMS gap recurs, worsens, or is scene-specific; (3)
true user-visible (capture-to-browser) latency instrumentation (a frontend-
side addition, not a field-session-only fix); (4) the ~13
`blocked_missing_evidence` records outside this session's own two
exhaustive windows remain individually untraced to their own component/
rescue context (also closeable via an offline pass over the already-
preserved merged ledger); (5) the already-known, unaffected-by-this-
milestone Gate B/admission-precision residual (a background/empty crop can
still become a real, if unlabeled, false Visit) remains open exactly as
`roadmap.md` already frames it. **Per this milestone's own explicit
instruction, Gate A is not self-closed by this session -- closure requires
external (ChatGPT) review of the accumulated evidence across all real
cohorts to date.** Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged.

**Gate A Measurement Closure v1 -- Fragmentation Accounting & True
User-Visible Latency Instrumentation (2026-08-31)** directly closes
dependency items (1) and (3) named immediately above -- see §1/§3, above,
and
[gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
for the complete record. Classification **A**. A dedicated offline pass
reapplying corrected, human-reviewable fragmentation accounting
(`fragmentation_accounting.py`, new) against v7's own already-preserved
merged ledger -- recovered from the original field session's own local
scratchpad directory and archived under `data/field-acceptance/2026-08-31-
gate-a-v7-measurement-closure-reanalysis/` for future reproducibility,
exactly as item (1) itself proposed -- resolves 7 of v7's own 10
denominator units (5 auto-confident, plus the two directly-visually
-confirmed multi-subject sibling pairs already named above, applied here
as sourced reviewer overrides) with **zero confirmed fragmentation**,
leaving 3 genuinely ambiguous (one of them the same sustained mega-cluster
this reconciliation's own "duplicate_visit_cluster_count: 5 and
fragmented_cluster_count: 17 (of 27 total encounter clusters)" raw-signal
caveat, above, already named as a methodology problem, not a defect). The
2026-08-19 primary cohort and v5 (as-previously-published) independently
show the identical zero-confirmed-fragmentation result under the same now
-consistent methodology -- three convergent cohorts move fragmentation to
**READY FOR FORMAL BUDGET REVIEW**, candidate ~0%/low single digits.
Item (3) (true user-visible latency instrumentation) is now fully defined
and implemented (T0 -> `decided_at`, T2-T5's own collapse into one
existing Host-domain value proven, not assumed, by a new repository-level
test; fallback-timestamp correctness independently proven at two layers,
including a new `engine_runtime.py` persistence-boundary test) -- but
**remains MEASUREMENT CONTRACT CLOSED / MORE FIELD EVIDENCE REQUIRED**:
v7's own preserved ledger predates the new field entirely, so every one of
its 25 admitted proposals' latency samples honestly reports
`unavailable_capture_time` when run through the new tooling, confirmed
directly rather than inferred -- the same true of the 2026-08-19 and v6
cohorts. A next field session run against post-this-milestone accepted
HEAD would be the first to produce real measured samples. Item (2) (a
second live cohort producing genuinely crowded 3+-simultaneous-subject
activity, to stress-test the disclosed crowded-feeder/NMS gap) and item
(5) (the already-known Gate B admission-precision residual) remain open,
unaffected by this milestone's own explicit scope; item (4) (~13 untraced
`blocked_missing_evidence` records) remains open, not attempted here.
Per this milestone's own explicit instruction, neither budget is accepted,
and Gate A is not self-closed by this closure -- closure requires external
(ChatGPT) review of the accumulated evidence, exactly as before. Schema
unchanged (`v58`). Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; this closure does not authorize the
next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening. **Remaining Gate A
dependency, in priority order, superseding the priority order immediately
above:** (1) real capture-to-visible latency field samples -- the single
item this milestone's own new instrumentation cannot retroactively
supply; any ordinary daylight session run against accepted HEAD after this
milestone closes it; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged from above); (3) a bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (`visit-observation-candidate-015/-016/-
017` and `-027/-028`) -- recorder frames already archived, not attempted
here as out of this milestone's own measurement-contract scope; (4) the
~13 untraced `blocked_missing_evidence` records (unchanged from above);
(5) the already-known Gate B admission-precision residual (unchanged from
above).

**Camera Node -> Host Clock Normalization for True Capture-to-Visible
Latency v1 (2026-08-31)** does not supply item (1) above (that still
requires an actual field session, not run here) -- it instead closes a
precondition item (1)'s own eventual fulfillment was silently resting on:
Gate A Measurement Closure v1's own T0 -> `decided_at` figure subtracted a
Camera Node-domain timestamp from a Host-domain one, disclosed via a fixed
caveat string but never proven safe, and a real ~39-second discrepancy
found in v7's own data was cited as justification for that caveat without
ever being root-caused. See
[camera-node-host-clock-normalization-latency-v1-report.md](camera-node-host-clock-normalization-latency-v1-report.md)
for the complete record. Classification **A**. Directly re-measured the
~39s figure against v7's own preserved raw ledger (recovered by Gate A
Measurement Closure v1, still present) and proved it was never evidence of
a Node-Host clock offset at all -- both operands of that original
comparison (`source_offset_ms`, `captured_at`) are Node-domain-labeled
fields on the same record, so nothing Host-side ever entered it; the real
Node-Host offset (`node_to_host_clock_offset_ms`, computed per frame in
`camera_node_live.py` since before this milestone) has never been durably
captured by any prior cohort, a fact now closed rather than merely
disclosed. New pure module `clock_calibration.py` supplies a bounded,
session-scoped one-way-delay calibration (point estimate: minimum observed
delta; uncertainty: observed spread -- no round trip exists in the current
push-only analysis-stream protocol, so none is invented) with drift
observation and clock-jump detection/invalidation (a disclosed 5-second
threshold, tested in both directions, never interpolated or extrapolated
across a detected jump). `capture_to_visible_latency.py`'s `LatencyState`
gains a fourth, structurally distinct value, `invalid_clock_mapping` -- a
required mapping that does not exist now honestly rejects the sample
rather than silently subtracting across an unproven clock boundary --
gated behind a new `clock_calibration_required` parameter defaulting to
`False` (exactly pre-milestone behavior, proven unaffected: all 11 of Gate
A Measurement Closure v1's own existing tests pass byte-for-byte
unchanged) and set `True` only for a real Camera Node session
(`provider_key == "camera_node"`; an RTSP/local/USB source structurally
never has this problem and is untouched). Fallback/stop-finalization/
multi-subject correctness independently re-proven under normalization,
including one deliberately discriminating fallback test (a clock jump
placed between the winner's and the admitted fallback member's own
calibration epochs, which would fail under a cross-proposal contamination
bug). Zero Camera Node/wire-protocol changes -- every input already
existed on both sides before this milestone; every schema/response change
is additive and defaulted. Schema unchanged (`v58`) -- nothing here is
persisted to SQLAlchemy. Tier 1 (285) + Tier 2 (266) = 551 tests passed, 0
failed, run together in one invocation; zero new ruff findings (one
pre-existing finding incidentally fixed). Does not reopen fragmentation
accounting, does not tune models/detectors, does not run a field cohort.
**Capture-to-visible latency remains MORE FIELD EVIDENCE REQUIRED,
unchanged in kind but now for a materially stronger reason: the
measurement mechanism itself is closed and correct, not merely defined.**
Every historical cohort (2026-08-19, v6, v7) still predates `clock_
calibration.py` entirely and is not, and cannot be, retroactively fixed
(stated explicitly, not inferred around) -- a next field session run
against post-this-milestone accepted HEAD would be the first able to
produce a real, validly-normalized T0 -> T5 distribution. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged; this closure does not authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does not select a next development milestone.
**Remaining Gate A dependency, unchanged in priority order and in every
item's own substance -- only item (1)'s own bar is now sharper:** (1) real,
*validly clock-normalized* capture-to-visible latency field samples (not
merely "field samples" -- the measurement mechanism they would need is now
closed; the samples themselves still do not exist); (2) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (3) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(4) the ~13 untraced `blocked_missing_evidence` records (unchanged); (5)
the already-known Gate B admission-precision residual (unchanged).

**Camera Node <-> Host RTT-Bounded Clock Calibration v1 (2026-09-01)**
does not itself run a field session -- it closes the absolute Node-Host
offset/error-bound measurement gap the immediately-preceding milestone's
own report named as still open: that milestone's own one-way estimator
(`offset_ms = min(deltas)`) is, by construction, only ever a one-sided
upper bound on the true offset, never a defensible two-sided error bound.
See
[camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
for the complete record. Classification **A**. Reuses the existing `GET
/node/v1/health` request/response operation (two additive response
fields, `node_receive_time`/`node_time`) rather than a new time-sync
protocol -- correcting, in place, the immediately-preceding milestone's
own "no request/response exchange exists" framing (correct for the
one-way analysis-stream push specifically, incorrectly generalized to the
whole Camera Node protocol; `docs/camera-node-live-shadow-contract.md` is
corrected the same way). A rigorously-derived two-sided offset interval
(`[offset_min_ms, offset_max_ms]`, from the honest inequalities "request
left before the Node's own receive timestamp" / "response arrived after
the Node's own send timestamp," never a symmetric-delay NTP formula) is
now the sole input `capture_to_visible_latency.py` normalizes T0 through;
the accepted one-way estimator is not discarded -- it continues, unchanged,
as the *relative* drift/jump monitor that decides when a live session
spends the cost of a fresh RTT-bounded batch, one of four recalibration
triggers (session start; a disclosed 5-minute bounded periodic cadence;
detected reconnect; a one-way-detected jump). Every latency sample now
carries the full interval (`latency_min_ms`/`latency_max_ms`), never only
a collapsed point estimate -- re-proved directly against fallback,
stop-finalization, and multi-subject-sibling scenarios, each now asserting
the interval itself, not only the point estimate, and the min/max
inversion (earliest possible t0 yields the *largest* possible latency)
verified at two independent layers. A real regression -- a sequential
5-attempt calibration batch against an unreachable Node blocking a live
session's own frame-processing tick for up to ~10 seconds -- was found via
a genuinely failing pre-existing end-to-end test during this milestone's
own work and fixed (concurrent batch attempts; the first calibration
triggered at the first ordinary tick rather than gating session start).
Zero Camera Node/wire-protocol breaking changes -- an old Node's response
simply lacks the two new keys, degrading honestly to `insufficient_
samples` at every layer, never a crash. Schema unchanged (`v58`). Tier 1
(404) + Tier 2 (670, combined) + Tier 3 (full Core gate, run because this
milestone -- unlike the immediately-preceding one -- adds genuinely new
runtime network I/O to the live engine loop): 5487 passed, 3 failed (all 3
independently confirmed pre-existing/unrelated by fresh baseline
bisection -- the recurring `test_place_biodiversity_summary_repository.py`
pair, plus one real-clock/local-day-boundary test whose own run happened
to straddle the actual midnight rollover into 2026-09-01), 3 skipped, 23
deselected, 11 xfailed; zero new ruff findings. **Absolute Node<->Host
clock-calibration state moves from OPEN to CLOSED.** **Capture-to-visible
latency remains MORE FIELD EVIDENCE REQUIRED, unchanged in kind but now
for a materially stronger reason a second time**: the measurement
mechanism is now both closed and correct/defensible, not merely closed;
every historical cohort (2026-08-19, v6, v7) still predates `rtt_clock_
calibrations` entirely and cannot be retroactively fixed. Does not reopen
fragmentation accounting, does not tune models/detectors, does not run a
field cohort. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; this closure does not authorize the
next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does not select a
next development milestone. **Remaining Gate A dependency, unchanged in
priority order and in every item's own substance -- only item (1)'s own
bar is now sharper a second time:** (1) real, *validly RTT-normalized*
capture-to-visible latency field samples -- the measurement mechanism is
now both closed and defensible; the samples themselves still do not
exist; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (3) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (4) the ~13 untraced
`blocked_missing_evidence` records (unchanged); (5) the already-known Gate
B admission-precision residual (unchanged).

**Reference Camera Node RTT-Capability Upgrade & Compatibility Re-Proof v1
(2026-09-01)** closes the Camera Node upgrade dependency the v8 entry
immediately below named as Gate A's own sharpest remaining item -- see
[reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
for the complete record. Classification **A**. The real reference Camera
Node was upgraded end to end via the accepted `scripts/install_camera_
node.py` mechanism (build against accepted HEAD `1a39479` -> preflight ->
install) from `git_commit baf9fdb` (71 commits behind, predating the RTT
protocol) to `git_commit 1a39479` itself, with zero unexpected config/data
loss and pairing preserved intact through the upgrade itself. Pre-upgrade
RED and post-upgrade GREEN both confirmed live against the real device
(`node_receive_time`/`node_time` absent, then present/valid/advancing).
Running the real, unmodified production RTT functions directly against
the upgraded Node produced **6 of 6 valid calibration batches (30 round
trips, ~3.35 real minutes)** -- the first real, valid RTT-bounded
calibration evidence to exist since the protocol was accepted; v8's own
796-batch, 0-valid session is now understood as an infrastructure gap,
already closed, not a mechanism defect. A real camera smoke test (fresh
disposable CPU-only Host instance, no Windows/GPU needed) drove a real
pairing, camera-setup completion, and three real advancing 1920x1080 live
frames through the actual Host API, visually confirmed as real reference
-yard footage -- this deliberately, transparently, and with real-time user
approval displaced the stale pairing v8's own session had left in place,
after the environment's own safety layer correctly declined to let that
proceed without asking. Doctor ran clean for this milestone's scope; no
dedicated "old Node version" warning exists anywhere in Doctor to have
newly cleared (there was never one). Newly, independently root-caused: no
automated mechanism anywhere in the release process checks Camera-Node
-build-vs-Host-build compatibility before a Gate A session begins --
disclosed, not fixed (explicit non-goal: no fleet-management feature).
No production code changed; no tests invented (real-hardware validation is
this milestone's own validation). Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged; does not authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does not select a
next development milestone. **Remaining Gate A dependency, in priority
order, superseding the priority order in the v8 entry immediately below:**
(1) the first real, *validly RTT-normalized* T0->T5 capture-to-visible
latency field distribution -- the Node, Host, and calibration mechanism
are now all proven ready; only a live field session's own real samples
are missing; (2) reconciling the now-diverged false-Visit-rate/
useful-evidence-rate evidence body (v5/v7 vs. v8) (unchanged); (3) a
second live cohort producing genuinely crowded 3+-simultaneous-subject
activity (unchanged); (4) the bounded visual-review pass against v7's own
two remaining genuinely-unreviewed ambiguous fragmentation units
(unchanged); (5) the ~13 untraced `blocked_missing_evidence` records, v7's
own (unchanged); (6) the already-known Gate B admission-precision residual
(unchanged).

**Representative Daylight Gate A Field Acceptance v8 -- True-Latency &
Crowding Closure Tranche (2026-09-01) ran the first field session against
post-RTT-calibration accepted HEAD, at classification **B** -- see §1/§3,
above, and
[representative-daylight-gate-a-field-acceptance-v8-report.md](representative-daylight-gate-a-field-acceptance-v8-report.md)
for the complete record.** A real, live 158.2-minute Observation session
(longer than the 60-120 minute target, disclosed) against the same real
reference Camera Node produced the highest `candidates_created` of any
cohort to date (27, all in-session), the first-ever fully-resolved
(zero-residual-ambiguous) fragmentation accounting (16/16
`correctly_represented`, a fourth/fifth convergent 0% cohort), the
deepest fallback chain yet observed (position 3 of 3), and
`blocked_missing_evidence` (9.9%, 21/212) closely replicating v7's own
9.4% at nearly double the distinct-proposal volume -- a real second,
independently-varied confirmation the Preservation/Fallback fix holds at
scale. Zero persistence contention; honest, clean stop-finalization.
**Item (1) above remains not closed, for a real, precisely root-caused
reason:** zero of 796 attempted RTT-bounded calibration batches produced
a valid sample (all `insufficient_samples`) because the reference Camera
Node's own installed software (`git_commit baf9fdb`, built 2026-08-27,
confirmed 69 commits behind current HEAD via `git merge-base
--is-ancestor`, and confirmed via direct `grep` to contain neither of the
two response fields the RTT protocol depends on) has not been redeployed
since the "Camera Node Upgrade & Compatibility Recovery v1" milestone
(2026-08-26) -- across five field-relevant milestones accepted since, none
of which touched the physical Node. Not fixed live: doing so mid-session
would have forced a reconnect (explicitly prohibited by this milestone's
own governing brief) and risked contaminating already-collected
measurements. The unaffected one-way drift/jump monitor returned a
complete, fully valid record (796/796 `calibrated`, stable 85-244ms
offset, zero jumps) -- real positive evidence of a stable underlying clock
relationship, not a substitute for the missing two-sided bound. Item (2)
(3+-subject crowding) remains unmet; a second candidate 2-subject pair
(Visits 021/022) was found but not visually confirmable (outside the
session's own recorder coverage window). **A new, materially reopening
finding, from direct pixel-region inspection of every low-confidence
admitted Visit's own recorded bounding box (matching the v5 report's own
established method):** 6 of 27 admitted Visits (22.2%) are false or
likely-false (empty background, clustered at one recurring weak-signal
screen location) -- materially exceeding v5 (5.3%) and v7 (4.0%), whose
own convergence previously supported a candidate false-Visit budget. That
candidate, and the directly-downstream useful-evidence-rate candidate, are
**withdrawn pending more evidence**, not reaffirmed, per this session's own
report ("Budget maturity"/"Candidate budgets") -- `roadmap.md` itself is not
edited by this reconciliation, per this milestone's own explicit scope
(release-execution-state.md only); a future reconciliation should confirm
whether `roadmap.md`'s own "Numeric release budgets" text already reflects
v7's own candidate proposals or still needs updating before this
withdrawal is reflected there too. Gate B's
own abstention behavior held cleanly throughout (zero confidently-wrong
species labels on any false Visit). The same rigorous check also reversed
this session's own initial working hypothesis that Visits 010/011
constituted directly-confirmed 2-subject crowding -- both are, in fact,
false detections sharing the same structural/temporal signature genuine
concurrent siblings would show, a disclosed methodological finding in its
own right. One real, previously-undiagnosed root cause was found for the
storage decline `roadmap.md`/this file had disclosed but not explained
since 2026-08-28: every prior field-acceptance disposable instance was
left running/retained indefinitely after acceptance, none ever cleaned up
-- mitigated for this session via two user-approved decisions (documented
in the report's own "Defects"), left at ~3.5GB free post-session, needing
attention before any near-term next session. No production code was
changed; Core was not run (no-code-change field session, per this
milestone's own explicit instruction) -- identity/schema/product-visible
results were independently validated live instead. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone. Per this milestone's
own explicit instruction, Gate A is **not** self-closed by this report.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, in priority order,
superseding the priority order immediately above:** (1) a Camera Node
software upgrade (via the already-accepted, already-validated upgrade
procedure) followed by a field session, to obtain the first real valid
RTT-bounded calibration samples and true T0->T5 latency distribution --
now the single most consequential, precisely-scoped remaining Gate A
dependency, a materially narrower ask than "more field evidence required"
was before this milestone; (2) reconciling the now-diverged
false-Visit-rate/useful-evidence-rate evidence body (v5/v7 vs. v8) before
either budget can be responsibly proposed -- likely via one or more
further cohorts, not by discarding v8's own result; (3) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged --
out of this milestone's own scope, not attempted here); (5) the ~13
untraced `blocked_missing_evidence` records, v7's own (unchanged -- v7's
raw evidence, recovered and archived this session for the first time, at
`data/field-acceptance/2026-08-31-gate-a-v7-raw-recorder-and-ledger-preservation/`,
remains available for that separate, still-open task); (6) the
already-known Gate B admission-precision residual (unchanged).

**Representative Daylight Gate A Field Acceptance v9 -- True-Latency &
Precision Reconciliation Tranche (2026-09-01) ran the field session item
(1) above named as the single most consequential remaining dependency, at
classification **A** -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
for the complete record.** A real ~97.1-minute Observation session against
the same real reference Camera Node, with the independent acceptance
recorder confirmed armed and writing real frames within ~4.2 minutes
(97.95% coverage, 2,353 files). **Item (1) closed:** 447/460 in-session
RTT-bounded batches `calibrated` (0 inconsistent, 0 jumps), 24/25 admitted
Visits produced a real measured T0->T5 latency sample (median 111,811ms,
p90 173,944ms, max 307,373ms) -- the first real, defensible latency
distribution in Gate A's history, root-caused via an additive tail-latency
decomposition to the accepted Visit-Continuity/episode-boundary quiet
-period design (a tight ~48-60s tail regardless of encounter length,
directly confirmed on individual proposals' own `blocked_continuation_
pending` revision histories), not pipeline inefficiency. **Item (2)
(reconciling the diverged false-Visit-rate/useful-evidence-rate evidence
body) now has a determinate answer:** direct multi-frame pixel-region
inspection found 5/25 (20.0%) confirmed false, closely replicating v8's
22.2% and materially diverging from v5 (5.3%)/v7 (4.0%) -- **v8's
elevated rate reproduces, a real, reproducible scene characteristic, not
a cohort anomaly.** Two distinct recurring hard-negative locations traced
in full (one a near-exact recurrence of v8's own reported location; one
new -- a feeder-cap sun-glint); the false-Visit-rate/useful-evidence-rate
candidates remain correctly withdrawn (v9's own 76.0% strict useful-
evidence rate sits below the ~85% figure v8 had already withdrawn). A
real Gate B residual instance field-confirmed for the first time since
its own governing fix was accepted (1/5 false Visits received a wrong
confident species label, root-caused to the fix's own already-disclosed
detector-sourced-evidence exclusion, not a regression). Fragmentation
reached a sixth/seventh convergent real cohort at 0% (14/14, accepted
reviewer-disposition method); duplicates a fourth convergent cohort at 0%
(0/25); `blocked_missing_evidence` a third independently-varied post-fix
confirmation (8.9%, 12/135, closely clustered with v7/v8). The rolling
hourly candidate limit activated for the second time in any cohort (6
real blocks, all high-confidence, self-cleared correctly). Direct visual
confirmation of 2 simultaneous birds at the feeder obtained (the best
2-subject evidence to date), but the detection-stage mechanism could not
be traced this session (`raw_detections` did not merge losslessly, a
disclosed gap matching v8's own). Zero persistence contention; zero
ERROR/CRITICAL/WARNING/Traceback lines in the full structured log. One
real, reproducible product defect found via live product usage (not
fixed, out of scope, a precise bounded next DEV contract named in the
report): `POST /api/review-labels` with `review_origin=agent_diagnostic`
and no `reviewer_identity` correctly raises `ReviewProvenanceError`, but
`create_review_label` only catches `ReviewRevisionConflictError`
explicitly, so this well-formed validation error propagates as an
unhandled `500` instead of a clean `400`. No production code was changed
by this milestone. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Per this milestone's own explicit instruction,
Gate A is **not** self-closed by this report -- the false-Visit-rate
divergence reproducing (rather than resolving) is judged a complete,
determinate answer to this milestone's own second primary objective, but
still leaves a release-blocking open item, and true latency has exactly
one real cohort. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A dependency, in
priority order, superseding the priority order immediately above:** (1)
resolve the false-Visit-rate/useful-evidence-rate divergence itself --
now sharpened to a well-evidenced, specific candidate explanation (scene-
specific recurring hard-negative locations; the already-accepted, per-
Stream `scene_confusor_regions` mechanism exists but is currently off by
default for this Stream) rather than an unexplained scatter, but not yet
confirmed as the actual explanation nor addressed -- the single most
consequential remaining Gate A dependency; (2) a second, independently-
varied true-latency cohort (Gate A's own standing rule requires cross-
session convergence before any number is proposed; ideally at a
materially different time of day/season, to test whether the ~48-60s
tail-latency constant and the encounter-duration-dominated distribution
shape both hold); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged -- still not observed in any
cohort to date); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(5) the ~13 untraced `blocked_missing_evidence` records, v7's own
(unchanged); (6) the newly-field-confirmed Gate B detector-sourced-
evidence residual (sharpened from a theoretical gap to one concrete field
instance -- still open, not fixed this milestone); (7) the disclosed
`agent_diagnostic` review-provenance error-handling defect (bounded,
unrelated to any measurement above, a precise next DEV contract already
named).

**Hard-Negative Visit Admission Precision & Species-Escalation
Correctness v1 (2026-09-01) closed item (1) immediately above --
resolving the false-Visit-rate divergence with a generalized correctness
fix, at classification **A** -- see §1/§3, above, and
[hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md](hard-negative-visit-admission-precision-species-escalation-correctness-v1-report.md)
for the complete record.** First irreversible product decision traced
explicitly: `candidate_quality_gate.evaluate_evidence_admission`, not
tracker confirmation (deliberate, recall-preserving) or candidate
authority (mode/lineage/rate-limits only, by design). New admission rule
(`reject_insufficient_detector_corroboration`): rejects only when a
proposal never reached a strong detection AND genuine detector
corroboration never exceeds a scaled floor (`2 * constituent_generation_
count + 1`, closing the chained-restart gaming loophole
`visit-observation-candidate-027`'s own 9-generation shape would
otherwise exploit) AND it never showed two consecutive genuine detections
anywhere (structurally ungameable). Not a confidence threshold (Detection
Quality Accounting v1's own 70-Visit sweep already ruled that out), not a
scene-coordinate blacklist (proven via an explicit adversarial test at an
arbitrary bounding box), production MDv5a `0.1` `score_threshold`
untouched. `visit-observation-candidate-026`'s own real signature (the
one confirmed-false v9 Visit with a confident wrong species label) and
the recurring foliage-cluster location are each reproduced through the
real, unmodified detector-observation-to-repository path and now
correctly rejected; six genuine-weak-bird positive controls, a normal
strong Visit, multi-subject isolation, and the accepted sustained
-activity/fallback/stop-finalization behavior all continue to admit/
function unaffected. Species-escalation Option A confirmed directly: a
rejected proposal creates no `VisitModel`/`ObservationCandidateVisitModel`
row, so species inference structurally cannot reach it;
`identification_eligibility.py` not reopened. Reviewed truth preserved;
`blocked_missing_evidence` and the disclosed `agent_diagnostic` 500 both
confirmed untouched; rate-limit accounting confirmed clean (a rejection
never increments the counters the hourly/session budget actually reads).
Tier 1 16/16; Tier 2 733 tests/0 regressions; Tier 3 one full Core run,
5504 passed / 2 failed (independently baseline-confirmed pre-existing and
unrelated -- the same `test_place_biodiversity_summary_repository.py`
pair §14 already names) / 3 skipped / 23 deselected / 11 xfailed; zero
new `ruff` findings. One honestly disclosed residual: a hypothetical real
bird at the exact same corroboration floor as the traced false cluster is
not distinguishable by corroboration structure alone (the same
structurally-irreducible limit v8's own report already showed for
confidence magnitude), and this fix is not yet field-validated at the
scale "Production authority gate"'s own six conditions
([detection-quality-accounting-contract.md](detection-quality-accounting-contract.md))
would require for a fully-settled policy -- expected, not self-authorized
to close here. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Per this milestone's own explicit instruction,
Gate A is **not** self-closed by this report: the fix is validated by
deterministic real-production-code replay, not yet by a live cohort.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, in priority order,
superseding the priority order in the v9 entry immediately above:** (1)
the next Representative Daylight Gate A cohort must field-prove this
precision fix (see this milestone's own report, "Next field proof," for
the complete list: false-Visit rate materially below the v8/v9 ~20-22.2%
regime, useful-evidence rate recovered, genuine low-confidence recall
preserved, no recurrence of either known hard-negative cluster as an
*admitted* Visit, Gate B hard-negative species-escalation absent) -- not
self-authorized by this closure; (2) a second, independently-varied
true-latency cohort (unchanged); (3) a second live cohort producing
genuinely crowded 3+-simultaneous-subject activity (unchanged); (4) the
bounded visual-review pass against v7's own two remaining genuinely
-unreviewed ambiguous fragmentation units (unchanged); (5) the ~13
untraced `blocked_missing_evidence` records, v7's own (unchanged,
confirmed this milestone not the same root cause); (6) the disclosed
`agent_diagnostic` review-provenance error-handling defect (unchanged,
bounded, a precise next DEV contract already named).

**Review Provenance Validation & API Error Semantics v1 (2026-09-01)
closed item (6) immediately above -- the `agent_diagnostic`
review-provenance `500`, at classification **A** -- see §1/§3, above, and
[review-provenance-validation-api-error-semantics-v1-report.md](review-provenance-validation-api-error-semantics-v1-report.md)
for the complete record.** Reproduced through the real `POST
/api/review-labels` endpoint, captured pre-fix: `review_origin=
"agent_diagnostic"` with no `reviewer_identity` correctly raises
`ReviewProvenanceError`, but `create_review_label` caught only
`ReviewRevisionConflictError`, so it reached the client as an unhandled
`500`. Fixed with one `except ReviewProvenanceError as error: raise
HTTPException(status_code=400, detail=str(error)) from error` clause,
mirrored from the identical, already-established convention its sibling
endpoint `reclassify_review_label_provenance` already used for this exact
exception type -- repository precedent, not intuition. A scope check
traced all four endpoints reaching `review_provenance.validate_review_
origin`: `create_review_label` was the only one still unhandled (the
other three already avoid a `500` via their own pre-existing generic
`except ValueError` fallback, with a less-specific message, disclosed as
a minor out-of-scope inconsistency). `review_provenance.py` untouched --
`agent_diagnostic`/`imported_curated` still strictly require `reviewer_
identity`. Directly confirmed: nothing persists on a rejected request
(via the Visit's own unfiltered `correction_history`, since `GET
/api/review-labels` resolves only the current *authoritative* row per
target and would hide a leaked non-authoritative row regardless);
existing Reviewed truth on the same Visit cannot be overwritten by a
subsequent failed request; no misleading `review.corrected` audit entry
on failure; a monkeypatched, genuinely unrelated `RuntimeError` still
surfaces unmasked. 8 lines changed in one function, zero schema/model
/provenance-policy change. Tier 1 (`tests/test_api.py`, 7 new tests)
61/61; Tier 2 (11 directly-traced files) 206/206, 0 regressions; Tier 3
correctly not run (not cross-cutting); zero new `ruff` findings. Does
**not** authorize Gate A v10, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, superseding the
list immediately above (item (6) there is now CLOSED and dropped):** (1)
the next Representative Daylight Gate A cohort must field-prove the
Hard-Negative Visit Admission Precision fix (unchanged -- see the entry
above for the complete field-proof criteria); (2) a second,
independently-varied true-latency cohort (unchanged); (3) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(5) the ~13 untraced `blocked_missing_evidence` records, v7's own
(unchanged).

**Host <-> Camera Node Release-Compatibility Preflight v1 (2026-09-02)
closes the release-process gap the Reference Camera Node RTT-Capability
Upgrade & Compatibility Re-Proof v1 entry above disclosed -- "no
automated mechanism currently exists that checks 'is the installed
Camera Node build compatible with/current relative to the accepted repo
HEAD' before a Gate A/field-acceptance session begins" -- at
classification **A**. See
[host-camera-node-release-compatibility-preflight-v1-report.md](host-camera-node-release-compatibility-preflight-v1-report.md)
for the complete record.** New `mockingbird.observation.node_
compatibility`: a pure decision table (`classify_node_compatibility`)
plus live orchestration (`probe_node_compatibility`) reusing the
existing, unmodified `CameraNodeClient`/`clock_calibration.estimate_rtt_
clock_calibration` functions -- never a second calibration
implementation. Compatibility is capability-based, never exact
git-commit equality: the Camera Node has never exposed a live `git_
commit` (only a static package `service_version`, currently `"0.1.0"` on
both Host and Node, this codebase's own established never-bump
practice), so a `version_skew_detected` field is reported purely as
informational diagnostics and never gates compatibility -- the one place
a real version mismatch is already meaningfully comparable, `api_
version`, is already hard-gated to exact-match at pairing time. Two
bounded profiles (`ordinary_monitoring`: only requires the health
protocol to answer; `field_acceptance`: additionally requires the
expected camera live-confirmed available, the RTT timestamp fields
present, and a real bounded RTT-bounded calibration batch to actually
reach `state == "calibrated"`); six actionable states (`compatible`,
`incompatible_missing_capability`, `incompatible_protocol`,
`calibration_failed`, `node_unreachable`, `camera_unavailable`) -- never
a generic "Camera Node unhealthy" bucket. No wire-protocol change --
every fact this contract needs (`api_version`/`service_version`/`node_
receive_time`/`node_time`) was already present on the wire; an old
Node's health response continues to parse exactly as before.

Wired into the one and only call site (`grep`-confirmed:
`get_observation_engine_session_manager().start(` appears exactly once
in `src/`, in `api/main.py`'s `start_stream_observation` -- no bypass
path exists): only a field-acceptance credential's own session start
(`request.state.field_acceptance_principal`, already resolved
unconditionally on every request by `auth.install_authorization`) is
held to the stricter `field_acceptance` profile, and only once the Stream
is already fully paired (mirrors `unified_status._camera_node_paired`'s
own four-field check exactly, so an unpaired Stream is left to its
existing "not paired yet" message unchanged) -- an ordinary signed-in
user's Start observing is never newly blocked, confirmed both
structurally (the new code path is wrapped in that same `if`, so its
network calls never execute for an ordinary session) and behaviorally
(real HTTP through the real pairing/setup/observation-start path: an
Administrator's own Start observing against the identical v8-shape old-
Node response is never blocked). On incompatibility, fails closed -- via
one new pure `unified_status.camera_node_incompatible_facts` builder --
before the Observation Engine session, acceptance-recorder allocation, or
any GPU/model resource commitment, confirmed end to end (a field-
acceptance credential's own `POST .../observation/start` against the
exact real v8 health shape returns an honest `needs_attention` status and
a same-session follow-up `GET .../observation/status` confirms
`observing` stayed `False`). Zero mutation of any kind: every call this
milestone's own code makes (`health`, `cameras`, `sample_clock_round_
trip`) is a pre-existing, already-accepted, read-only GET -- nothing
SSHes into the Node, installs software, resets pairing, or upgrades
anything automatically; upgrade remains the existing, separate,
operator-initiated `scripts/install_camera_node.py` action.

Doctor (`diagnostics/doctor.py`) gains one new informational `diagnostic_
context` key on the existing `camera_node` check's terminal PASS branch
(only when a camera_node Source is configured), pointing at a new
standalone script (`scripts/check_camera_node_compatibility.py`, which
formalizes what every prior field-acceptance report has so far done by
hand -- "5 real calibration batches run directly against the Node via
the exact unmodified production functions") for a live verdict -- mirrors
the `clock` check's own already-established "not measurable from a
standalone Doctor check: see ... instead" precedent rather than adding a
live network probe, which would violate Doctor's own documented
read-only, no-`ProductRepository`-construction design invariant. No new
check, no existing check's status/recoverability changed.

Exercised live against the real, already-upgraded reference Camera Node
(`192.168.1.112:8787`, confirmed LAN-reachable) from two independent
network paths: this sandbox (WSL2) and, more representatively, a real
native-Windows Host (the actual Gate A Host platform) via the existing,
accepted `scripts/deploy_windows_dev.py`, with the deployed instance's
`git_commit` independently verified over real HTTP rather than trusting
the deploy helper's own report. Both `ordinary_monitoring` and `field_
acceptance` profiles return `compatible` on both paths, each with a real
5/5 valid RTT-bounded calibration batch (22.65ms RTT from this sandbox,
24.0ms from native Windows) -- the first real RTT evidence collected by
this milestone's own new tool, consistent with (and independent
confirmation of) the Reference Camera Node RTT-Capability Upgrade &
Compatibility Re-Proof v1's own real-hardware proof. `--camera-id`/
`--credential` were deliberately not exercised against the real device
(would require a fresh, state-changing re-pair, out of this milestone's
own non-goals); the identical camera-availability code path is already
fully exercised, both directions, by fake-transport unit tests and
real-HTTP pairing-flow API tests. One incidental, pre-existing, unrelated
finding disclosed on the Windows dev instance: its persistent database
schema predates `camera_node_last_seen_at` (schema 37), so Doctor's
`camera_node` check raised rather than gracefully degrading -- confirmed
unrelated to this milestone (`storage/models.py` untouched here) and
already covered by two passing Linux-side unit tests against a
correctly-migrated schema; left disclosed for a future, separately-scoped
Doctor/migration-robustness milestone, not fixed here.

No schema change. Tier 1 (25 new tests across `test_node_compatibility.py`/
`test_node_compatibility_api.py`/`test_doctor.py`) 25/25, confirmed
non-flaky across 5 consecutive runs; Tier 2 (every directly-affected
subsystem -- `CameraNodeClient`, RTT calibration, engine runtime, Doctor,
field-acceptance auth, the installer, and the full `test_api.py`/`test_
observation_camera_node_live.py` surface) 582/582, 0 regressions, plus a
clean full-app import/boot smoke test (335 FastAPI routes); Tier 3
correctly not run, per this milestone's own explicit §29 carve-out for
enforcement limited to acceptance/Doctor surfaces, matching this diff
precisely (confirmed, not merely asserted: the new `api/main.py` behavior
is conditionally gated and only reachable for an already-paired Stream;
`unified_status.py` gained one new additive function; `doctor.py` gained
one new informational context key inside an existing branch). Zero new
`ruff` findings (`git stash`-isolated baseline comparison; `api/main.py`'s
own 26 pre-existing, unrelated findings unchanged before/after). This
closure does **not** authorize the next Representative Field Acceptance /
Gate A session (Representative Daylight Gate A Field Acceptance v10 --
Admission-Precision Re-Proof & Gate A Closure Tranche remains the exact
next daylight dependency, unchanged and not self-authorized here),
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. Authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
**Remaining Gate A dependency, unchanged from the entry immediately
above -- this milestone is a release-process closure orthogonal to Gate
A's own field-evidence dependency chain, and neither adds to nor closes
any item on it:** (1) the next Representative Daylight Gate A cohort must
field-prove the Hard-Negative Visit Admission Precision fix; (2) a
second, independently-varied true-latency cohort; (3) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity; (4)
the bounded visual-review pass against v7's own two remaining genuinely-
unreviewed ambiguous fragmentation units; (5) the ~13 untraced `blocked_
missing_evidence` records, v7's own.

**Field-Acceptance Instance Lifecycle & Storage Safety v1 (2026-09-02)
closes the accumulation root cause v8's own report first diagnosed and
v9's own session re-encountered and manually worked around --
"every prior field-acceptance disposable instance was left running/
retained indefinitely after acceptance, none ever cleaned up" -- at
classification **A**. See
[field-acceptance-instance-lifecycle-storage-safety-v1-report.md](field-acceptance-instance-lifecycle-storage-safety-v1-report.md)
for the complete record.** A release-process/tooling closure, not a field
session: no wildlife cohort was run, no Camera Node activity occurred,
and Gate A's own evidence body and remaining dependency (below) are
unchanged. Root-caused precisely, by direct code reading, not assumed:
`scripts/deploy_windows_dev.py` had a safe, ownership-verified stop
primitive (`stop_verified_deployment`) but no standalone CLI path to
invoke it without also deploying/rolling back something else; no concept
of "disposable" existed anywhere in the codebase (the only Host-side
instance-identity concept, `mockingbird.runtime_state.resolve_instance_
id`, carries no purpose/lifecycle field at all); and `--cleanup`/`--keep`/
`--gc-cache` (Storage / Retention / Disk-Pressure & Recovery Closure v1,
already accepted and frozen, **not reopened here**) each operate on one
`--dev-root` at a time, with nothing anywhere reasoning about *multiple*
separate disposable instances.

New, additive-only: a durable, self-verifying sidecar manifest
(`field_acceptance_manifest.json`, sitting beside `deploy_windows_dev.py`'s
own `deployments.json`/`current.json`, never a schema or product-code
change) recording `active -> completed -> archived`, with `SAFE_TO_
RECLAIM` deliberately computed fresh at assess/cleanup time rather than
stored (so a manually-relaunched process after archiving is still caught).
A new standalone script, `scripts/field_acceptance_instance_lifecycle.py`
(`init`/`status`/`assess`/`complete`/`mark-archived`/`cleanup`/
`preflight`), reusing `deploy_windows_dev.py`'s own process/port-safety
primitives via the identical `runpy.run_path` sibling-script convention
that file already uses for `build_local_product.py` -- never a second
implementation. `deploy_windows_dev.py` itself gained exactly two additive
things: a `--stop` flag (exposes the existing `stop_verified_deployment`
standalone, previously only reachable as a side effect of `deploy()`/
`rollback()`) and `check_storage_headroom`, a pre-build fail-closed
storage-preflight guard (mirrors the product's own already-accepted disk
-pressure thresholds and the acceptance recorder's own hard 5GB ceiling as
literals, never invented numbers), placed at the same "fail fast before
any build work" point as the pre-existing `_validate_host_port`.
Cleanup is dry-run by default; `--destroy` is required explicitly, and
`execute_cleanup` redundantly re-verifies path safety/identity/not
-running immediately before its one destructive call, which delegates to
`deploy_windows_dev.py`'s own already-hardened `WindowsHost.remove_tree`
-- never a second recursive-delete implementation. Shared runtime/model/
BioCLIP-model caches are confirmed structurally per-dev-root (never
shared across separate `--dev-root` instances, matching V8's own report's
direct confirmation), so a full-instance reclaim never touches another
instance's cache; the pre-existing `--gc-cache`/`--cleanup --keep` remain
the correct, un-duplicated path for trimming one *persistent* dev-root's
own release history.

Real native-Windows proof, end to end, against the actual reference dev
host (genuinely storage-constrained at proof time, 26.8GB free of ~499GB):
a fresh, purpose-created disposable instance
(`MockingBirdLifecycleProofV1`) was identified, measured, gracefully
stopped, archived against minimal synthetic evidence, dry-run assessed,
and destructively cleaned up -- with the operator's own persistent
`MockingBirdDev` (29.2GB) and every other historical instance
(`MockingBirdFieldAcceptanceV9`, `MockingBirdFirstHourAcceptance`)
confirmed byte-for-byte untouched throughout, ~2.43GB of real disk space
genuinely reclaimed, and `MockingBirdDev` fully restored afterward
(verified identical `instance_id`/`git_commit`/`build_id` to before). This
same real proof found and fixed one genuine defect no small-fixture unit
test could have surfaced: a wrong-target refusal against the real,
~29GB, many-release `MockingBirdDev` initially took over two minutes
(an unconditional full byte-count walk ran before the identity check that
was always going to refuse regardless -- safety never at risk, only
performance) -- fixed by reordering, reverified at 0.104 seconds, and
regression-tested. Tier 1 170/170 (37 new tests in a new `test_field_
acceptance_instance_lifecycle.py`, 8 new in `test_deploy_windows_dev.py`
alongside its 125 pre-existing, 0 regressions); Tier 2 147/147 across
every directly-relevant surface (`test_acceptance_recorder.py`, `test_
field_acceptance_authentication.py`, the three `test_storage_retention_*`
files, `test_storage_status_disk.py`, `test_node_compatibility*.py`,
`test_observation_session_api.py`/`test_observation_unified_api.py`), 0
regressions; Tier 3 correctly not run (zero `src/mockingbird/` files
changed, confirmed via `git diff --stat`); zero `ruff` findings (absolute,
not merely relative to baseline). No schema change (`v58`, unchanged).
This closure does **not** authorize the next Representative Field
Acceptance / Gate A session (Representative Daylight Gate A Field
Acceptance v10 -- Admission-Precision Re-Proof & Gate A Closure Tranche
remains the exact next daylight dependency, unchanged and not
self-authorized here), External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, unchanged from the
entry immediately above -- this milestone is a release-process/tooling
closure orthogonal to Gate A's own field-evidence dependency chain, and
neither adds to nor closes any item on it:** (1) the next Representative
Daylight Gate A cohort must field-prove the Hard-Negative Visit Admission
Precision fix; (2) a second, independently-varied true-latency cohort;
(3) a second live cohort producing genuinely crowded 3+-simultaneous
-subject activity; (4) the bounded visual-review pass against v7's own
two remaining genuinely-unreviewed ambiguous fragmentation units; (5) the
~13 untraced `blocked_missing_evidence` records, v7's own. **New,
disclosed release-operational fact this milestone adds, not a Gate A
dependency:** disposable field-acceptance instances now have an explicit
lifecycle -- a future field session should `init` its disposable
`--dev-root` immediately after deploying, and `complete`/`mark-archived`/
`cleanup` it once the session's own report is written, so the same
accumulation this milestone closed does not silently recur.

**Representative Daylight Gate A Field Acceptance v10 -- Admission-
Precision Re-Proof & Gate A Closure Tranche (2026-09-02) ran the field
session item (1) above required, at classification A.** See
[representative-daylight-gate-a-field-acceptance-v10-report.md](representative-daylight-gate-a-field-acceptance-v10-report.md)
for the complete record; see §1/§3, above, for the full reconciled
summary. First real session to use the newly-accepted field-acceptance
instance lifecycle end to end (`init` immediately after deploying,
`complete`/`mark-archived` once the report was written, evidence-archive
attached, `SAFE_TO_RECLAIM`, deliberately not destroyed) -- exactly the
"future field session should" guidance the entry immediately above this
one asked for, now itself the worked example. **Primary result: the
Hard-Negative Visit Admission Precision fix's own field-proof criterion
did not hold** -- confirmed false-Visit rate 4/11 = 36.4%, worse than v8
(22.2%) and v9 (20.0%). Precisely root-caused, not diffuse: the new rule
correctly rejected 3/3 classic single-generation hard-negative chains
(one an exact re-confirmation of v8's own foliage-cluster location by
coordinates and direct visual inspection), but the same recurring
tube-feeder-area confusor defeated the rule's count-based corroboration
axis 4 times by accumulating enough individually-insufficient low
-confidence detections within one continuation window -- the exact
residual risk that fix's own report had already disclosed as untested at
this scale, now concretely reproduced (further corroborated by 15
`blocked_ambiguous_boundary` occurrences of the same location spanning
nearly the whole session). Weak-real-bird recall preserved (a genuine
small/distant bird admitted three times via count-based corroboration,
never rejected); the one genuine recall miss found traces to the
pre-existing `blocked_ambiguous_boundary` mechanism, not the new rule.
Gate B's own species-escalation failure class (false Visit -> confident
wrong species) did not recur on any of the 4 confirmed-false admissions.
Useful-evidence rate fell to 54.5%; fragmentation regressed to one real
confirmed case (breaking the prior 0% streak, small-denominator basis);
duplicates remain 0% (7th convergent cohort); `blocked_missing_evidence`
improved to 6.7% (best of all cohorts, further convergent); RTT
calibration 445 batches merged from periodic snapshots, 98.9%
`calibrated`, 0 clock jumps; true latency median T0->T5 103.9s / p90
183.3s, closely matching v9 (111.8s / 173.9s) with one disclosed,
root-caused outlier; monitoring coverage 99.99%; stop-finalization and
the connectivity retry policy both worked correctly a second time. No
multi-subject wildlife evidence this session (sparser activity day than
v5-v9, 11 admissions vs. 19-27) -- target not met, disclosed, not a
defect. **New methodological finding for future sessions:** the
counterfactual ledger's own 60-minute age-eviction bound is shorter than
this milestone's own 75-100 minute target session length; a single
end-of-session read would have silently lost ~46% of the session's own
history to eviction, worked around via periodic full-window snapshots
every 12 minutes merged post-hoc (100% recovery of the raw-detection and
track-generation ledgers) -- recommended as standing acceptance
methodology for any session expected to run past ~50 minutes. One
disclosed, user-authorized operational action: the reference Camera
Node's single pairing-credential slot, held by the now-dormant v9
instance, required an SSH-mediated reset to free for v10 -- correctly
declined once by the auto-mode permission classifier as a consequential
remote-infrastructure action, then explicitly authorized by the user
(backed up first, `boot_id` continuity confirmed a credential-state
reset only). Tier 1-3 correctly not run (zero production code changed);
zero schema change (`v58`, unchanged). This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. Authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
**Remaining Gate A dependency, in priority order, superseding the
priority order in the entry above (item (1) there is now answered --
field-proof ran and did not confirm the fix; superseded by the concrete
new blocker immediately below):** (1) the count-accumulation loophole in
`reject_insufficient_detector_corroboration` this session traced and
precisely scoped -- bound corroboration credit by genuine detection
value/variance, not raw repeated-detection count alone, so a physically
static confusor cannot out-accumulate a floor scaled only by generation
count; (2) a second, independently-varied true-latency cohort
(unchanged); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged, still not met); (4) the
bounded visual-review pass against v7's own two remaining genuinely
-unreviewed ambiguous fragmentation units (unchanged); (5) the ~13
untraced `blocked_missing_evidence` records, v7's own (unchanged); (6)
the three real, disk-space-consuming legacy field-acceptance dev-roots
(`MockingBirdFieldAcceptanceV9` 6.8GB, `MockingBirdFirstHourAcceptance`
2.4GB, `MockingBirdDev`) now disclosed as structurally invisible to the
new lifecycle-manifest tool's own `preflight` reclaimability accounting,
since none was ever `init`-ed under it (new, bounded, tooling-only, not
release-critical).

**Field Acceptance Evidence Integrity & Storage Preflight Correctness v1
(2026-09-04) fixed and proved the field-tooling defects v12 disclosed --
does not itself close Lane R/Gate A, does not run a field session, and
does not authorize the next attempt.** **Remaining Gate A dependency, in
priority order, restating v12's own 13-item list with item (12) now
narrowed (unchanged otherwise):** (1) never-strong single-generation
confusor clearing `blocked_ambiguous_boundary` then reaching the quality
gate repeatedly -- unmet; (2) a second person-confound-free cohort, to
confirm v12's own 5.6% false-Visit rate is representative -- unmet; (3)
a full-ledger-coverage re-proof of fragmentation at full automated-tool
strength (v12's own 0/14 used a weaker manual method, data-starved) --
unmet; (4) a second independently-varied true-latency cohort -- unmet;
(5) a 3+-simultaneous-subject cohort -- unmet; (6) v7's two remaining
ambiguous fragmentation units -- not investigated; (7) the ~13 untraced
v7 `blocked_missing_evidence` records -- not investigated; (8) same
-frame class-contradiction fix's field effect on person-associated false
Visits -- unmet, no genuine human presence has recurred since; (9)
further strong-confidence scene-artifact recurrence -- has not recurred
(a negative result, not a closure); (10) no whole-frame human
suppression of real birds with a person present -- still only trivially
satisfied; (11) scene-confusor participation incl.
corroboration-rejected occurrence counts -- directly measured through
v12, including the first real-field category-D case; **(12) [NARROWED
by Field Acceptance Evidence Integrity & Storage Preflight Correctness
v1] a cohort with intact full-session raw-ledger coverage** -- v12's own
tooling defect that risked this outcome is fixed and proven (real
WSL-independent periodic-snapshot + deterministic reconciliation
tooling); this item no longer exists "because the snapshot tool might
silently break again," but the standing evidence requirement is
unchanged: Gate A still needs at least one representative cohort whose
raw ledger this tool actually captures completely end to end, and
fixing the tool does not retroactively create that evidence; (13)
resolve whether `reject_no_identification_or_context`'s "vanish
entirely, no Visit at all" behavior for brief-but-real encounters should
be revisited -- untouched, preserved verbatim, still open (explicitly
out of this milestone's own scope).

**All-Alternate Subject Evidence Recall Correctness v1 (2026-09-04) root
-caused and fixed one live-reachable mechanism behind item (13) -- a
proposal whose only surviving evidence is a `classifier_same_frame`
snapshot no longer vanishes -- but did not close item (13) itself: neither
of v12's own two named `reject_no_identification_or_context` misses (37:12,
57:07) was actually caused by this mechanism (precise ledger reconstruction
found different, disclosed, out-of-scope causes for each -- candidate
-authority ambiguous-boundary arbitration; detector corroboration), and a
genuinely new, real, precisely-root-caused finding (whether ambiguous
-boundary arbitration's own geometry-compatibility tolerance meaningfully
discriminates real subjects from persistent confusors within its 45-second
window) was disclosed, not fixed, staying explicitly out of that
milestone's own scope. Does not itself close Lane R/Gate A, does not run a
field session, and does not authorize the next attempt or a fix for the
newly-disclosed ambiguous-boundary finding.** **Remaining Gate A
dependency, in priority order, restating v12's own 13-item list with items
(12) and (13) now narrowed (unchanged otherwise):** (1)-(11) unchanged,
see immediately above; (12) unchanged, see immediately above; **(13)
[NARROWED by All-Alternate Subject Evidence Recall Correctness v1]
resolve whether `reject_no_identification_or_context`'s "vanish entirely,
no Visit at all" behavior for brief-but-real encounters should be
revisited** -- the one specific, proven, live-reachable mechanism behind
it (a same-frame-only evidence set silently discarded) is fixed; the
standing question is not retired: neither v12 real miss this item's own
prior wording was motivated by is actually explained by that mechanism,
so full field re-confirmation that brief-but-real encounters are no
longer silently lost still awaits the next representative cohort (item
12) run against this now-fixed code, and a new, separate, disclosed
-not-fixed ambiguous-boundary/geometry-tolerance finding (see
[all-alternate-subject-evidence-recall-correctness-v1-report.md](all-alternate-subject-evidence-recall-correctness-v1-report.md)
"Remaining residuals") is a candidate for a future, separately-authorized
milestone, not added as a 14th list item here since it was never part of
v12's own original list.

**Ambiguous-Boundary Real-Subject Recall Correctness v1 (2026-09-04)
directly pursued the candidate the entry immediately above named -- does
not close Lane R/Gate A, does not run a field session, and does not
authorize the next attempt.** Reconstructed the chartered v12 ~37:12 case
(`06c209ae...`) with high fidelity and established, for the first time, a
decisive fact settling how it was actually lost: the real 187ms gap
between its own `blocked_ambiguous_boundary` decision and its winning
sibling's `created` decision is two orders of magnitude below the proven
10-second minimum spacing between separate assembly ticks
(`_ASSEMBLY_TICK_SECONDS=10.0`), proving both were decided together,
ordinarily, in the existing fallback-chain mechanism -- not a dispatch
defect. Its own root cause is confirmed to be exactly the already
-disclosed geometry-compatibility-tolerance question the entry above
raised; no safe, in-scope fix exists, and none was attempted
(Classification I, per this milestone's own taxonomy). **The v12 ~37:12
recall defect therefore stays exactly as open as before this milestone.**
Separately, the same investigation found and safely fixed a genuinely
different, real, in-scope defect in the identical mechanism, confirmed
live-reachable in this exact real session (its own next `blocked_
ambiguous_boundary` loss, ~11 seconds later, a genuinely separate tick):
an ambiguous component's own arbitration-selected winner can itself
already be permanently resolved on a strictly earlier tick, silently
starving every later arrival within its reach even when that stale member
was never admitted at all. Fixed entirely inside `engine_runtime.py`
(`_live_chain_for_component` plus a same-shaped `admitted_proposal_ids`
record), reusing only already-existing structural facts -- no new
threshold, no time-based staleness constant, no change to arbitration's
own ranking. Tier 1 (6 new tests) and Tier 2 (461 tests across every
directly-affected subsystem, 579 combined) both clean; Tier 3 (full Core):
5679 passed / 1 failed (independently re-confirmed pre-existing and
unrelated via `git stash` bisection -- a new, previously-uncatalogued
-by-name Place-Intelligence-change-summary test, unconnected to this
milestone's own Observation-Engine-only diff). Classification **B**.
**Remaining Gate A
dependency, unchanged from the entry immediately above in every respect
-- this milestone neither closes nor reopens any of the 13 items:** (1)
-(13) as already narrowed. **New, disclosed candidate fact for the next
representative cohort (not a 14th list item):** does the dead-anchor
-promotion fix measurably change recall or precision under real, sustained
activity, and does the already-disclosed geometry-compatibility-tolerance
question (still the v12 ~37:12 case's own real, unresolved cause) recur.

**Representative Daylight Gate A Field Acceptance v13 -- Intact-Ledger
Re-Proof & Budget Convergence (2026-09-04) directly answered the
candidate fact immediately above, using the accepted committed snapshot
tooling for the first time end to end -- does not close Lane R/Gate A,
does not authorize the next attempt.** Classification **B** (see §3 for
the full record and the one explicit named reason). 101.8 real minutes
against a fresh disposable instance and the real reference Camera Node
(fresh picamera2 pairing after a user-authorized Node-side reset),
independent acceptance recorder enabled throughout (5,013 frames,
4.48GB, zero gaps over 5s), accepted `field_acceptance_ledger_snapshot.py`
run detached for the full session (21 checkpoints; `raw_detections`/
`track_generations` reconciled 100% complete by record count,
`proposal_outcomes` decision-event coverage 44.6% -- a real, disclosed,
newly-identified residual limitation: this artifact's own retention can
outpace a 5-minute snapshot cadence under high proposal-churn sessions,
distinct from and narrower than v12's own now-fixed tooling defect).
**Headline finding, dual-sourced (manual visual review of the fully
independent acceptance recorder, plus the accepted automated
`encounter_accounting.py`/`run_gate_a_measurement_accounting.py`
reconstruction, 48 encounter clusters, 19 conservatively confirmed
real): zero Visits were admitted against a genuinely, substantially
active real feeder session** -- the worst recall result of any cohort to
date, and, unlike v4's own pre-fix admission-arbitration starvation, not
attributable to the accepted Sustained-Activity fix's own mechanism at
all (that fix's own counters behaved correctly throughout: candidate
authority never exhausted, fallback chains attempted and exhausted
normally). **Root-caused precisely via full code tracing to a genuine,
previously-undiscovered, release-critical defect in the Observation
Engine's own automatic evidence-capture path**
(`CameraNodeHttpTransport.request_evidence_burst`, `src/mockingbird/
observation/camera_node_live.py:551-621`): the Host persists a Camera
-Node evidence `profile_id` at camera-setup time and never re-validates
it against the Node's live advertised profile set; every burst failure of
any kind (a stale-profile `409 profile_not_advertised`, a `503`, a raw
timeout, a connection reset) collapses into one identical, generic
failure code with **zero logging anywhere in the file**, no
`EvidenceCandidate` of any role is ever created, and no file is ever
written -- so every proposal this session was rejected `blocked_missing_
evidence`/`no_persistable_evidence_bytes` at the evidence-*existence*
gate, before any of the accepted precision mechanisms (ambiguous-boundary
blocking, detector-corroboration, scene-confusor, same-frame
class-conflict) could ever engage. Two concrete, code-grounded candidate
triggers identified (the Node's own async warm-proof promotion silently
renaming/retiring the exact profile_id this Stream's config still names;
and/or the still-`reconfiguration_required` capture path's own worst-case
~12+-second latency sitting at or beyond the Host's own fixed ~12-second
timeout under real concurrent monitoring-stream lock contention) --
determining which one (or both) actually fired requires live Node
inspection this milestone's own bounded field-collection scope did not
extend to. Independently ruled out: the already-fixed 2026-08-20
harvest-cache timing race (this session's own `evidence_harvest_misses`
stayed 0 throughout, which that defect's own closure contract states
proves nothing was ever successfully captured in the first place, not a
recurrence of a captured-then-lost race). Both accepted precision fixes
honestly field-accounted despite the shared root cause:
`classifier_same_frame` fallback **zero occurrences**; `dead_anchor_
promoted` **exactly one occurrence** (a 3-generation component), itself
defeated by the identical evidence-capture defect before its own merits
could be evaluated -- fallback counters (`fallback_attempted_count`/
`fallback_exhausted_count`, both 16, `fallback_admitted_count` 0)
internally coherent throughout. Zero `blocked_ambiguous_boundary` outcomes
and zero `reject_insufficient_detector_corroboration` outcomes occurred
all session -- a materially different shape from every prior cohort,
since arbitration successfully selected and attempted real chain members
(one chain alone tried at least 27 ranked positions) rather than being
blocked at arbitration itself; the shared evidence-capture defect
defeated every attempt regardless of rank, so the v12 ~37:12
geometry-compatibility-tolerance question could not recur in a form this
session could evaluate. Zero scene-confusor regions were ever registered
(first cohort in this project's history with a completely empty table) --
root-caused precisely: the scene-confusor touch point fires only `on
admit` and `on reject_insufficient_detector_corroboration`, neither of
which ever occurred. RTT-bounded clock calibration reached the largest,
cleanest sample of any cohort to date (523 batches, 518 calibrated
(99.04%), 0 clock jumps, `offset_ms` range `[-55.772, 110.616]`) --
substantially strengthening dependency item #4's own infrastructure half
even though 0 admitted-Visit latency samples resulted (worse, not better,
than v12's own n=2 -- the one named reason this milestone classifies B
rather than A). Independent-recorder monitoring coverage was the tightest
of any cohort to date (99.99% span, max gap 3.68s, zero Node disconnects,
`boot_id` unchanged throughout). Duplicate-rate and monitoring-coverage
release-budget readiness (`READY FOR BUDGET` since v12) are **reaffirmed,
and for monitoring coverage further strengthened** by this session; every
other metric's own prior "MORE EVIDENCE REQUIRED" status is unchanged,
except recall and evidence-survival/`blocked_missing_evidence`, both
newly **REOPENED BY DEFECT** -- this session's own 0%/88.5% numbers are
correctly excluded from budget-convergence averaging for those two
metrics specifically, as defect-attributable rather than representative.
Not fixed during the cohort, per this file's own standing discipline --
core admission/evidence-path code, explicitly off-limits during field
collection. Tier 1-3 correctly not run (zero production code changed);
schema unchanged (`v58`). This closure does **not** authorize a defect
fix, v14, External Pre-Release Acceptance, or Final Release Hardening,
and does **not** select a next development milestone. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged. **Remaining Gate A dependency, in priority order, restating
the prior 13-item list (unchanged in substance) plus one new, more
urgent item:** (1)-(13) as already narrowed by prior entries above --
none closed or reopened in substance by v13, except (11) (scene-confusor
participation) directly measured again (zero regions) and (12) (intact
ledger coverage) materially advanced (two of three artifacts fully
complete by record count, the third's own residual limitation newly
named precisely). **(14) [NEW, RELEASE-CRITICAL] fix the Observation
Engine's automatic evidence-capture profile-staleness/silent-failure
defect identified above, then field-re-prove recall against a
representative cohort with the fix in place** -- more urgent than items
(1)-(13): no future field cohort's own recall/evidence-survival
measurement can be trusted at face value until this is closed.

**Camera Node Evidence-Capture Profile Validity & Failure Observability
Correctness v1 (2026-09-04) directly answers item (14) immediately
above's own defect-fix half -- does not close Lane R/Gate A, does not
authorize the next representative field attempt.** Classification **A**
(see §3 for the full record). Independent, bounded, non-field-cohort
correctness milestone: reproduced v13's own defect live, on the real
reference Camera Node, rather than relying on the historical (now
unrecoverable -- that Node process has long since cycled) v13 session
alone. **First irreversible error, confirmed**: `CameraNodeHttpTransport.
request_evidence_burst` (`src/mockingbird/observation/camera_node_
live.py`) received the Node's own `409` + `X-MockingBird-Node-Error:
profile_not_advertised` and discarded the header, returning the same
generic `evidence_burst_unavailable` code used for every other failure
class, with zero logging -- confirmed unchanged from v13's own account.
**Root cause, proven live (classification B, not merely inferred)**:
`PiCamera2Provider`'s background `_schedule_warm_proof`/`_prove_warm_
profiles` (`src/mockingbird_node/providers.py`) retires a cold
`reconfiguration_required` evidence profile id and replaces it with a
differently-named `warm_concurrent` id (identical width/height/purposes/
`geometry_group`) -- live-measured at ~4.18 real seconds after a fresh
pairing on the reference Pi, confirmed to stay retired (never
re-advertised) for the rest of that Node process's life. **The competing
timeout hypothesis was independently, separately measured live and
found not supported**: real cold `reconfiguration_required` captures
(forcing a full reset -> reinit -> capture -> monitoring-restore cycle)
took 5.66s-7.87s against the Host's own ~12s budget (2s connect + 10s
response) -- real headroom in every measured case, on the real
hardware; the timeout was not changed, and no fix was invented for an
unproven cause. **Fix, at the causal layer only**: `request_evidence_
burst` now parses the Node's own `X-MockingBird-Node-Error` header (the
identical alias table `source_providers.camera_node.CameraNodeClient.
capture`/`.snapshot` already use for the sibling `/capture` endpoint,
duplicated locally rather than cross-imported, matching this file's own
existing precedent) into a real, bounded failure taxonomy, and -- only
on the Node's own explicit "not advertised" signal -- performs exactly
one live reconciliation (`_reconcile_evidence_profile`, reusing the
already-bounded-timeout `CameraNodeClient.cameras()` already used
elsewhere in this exact runtime) matched on stable semantic facts alone
(camera identity, "evidence" purpose, preferring `capture_class ==
"warm_concurrent"`), failing closed on any ambiguity/zero-match/
unreachable-Node condition, followed by exactly one bounded retry --
never a loop, never triggered by any other failure class (auth,
camera-busy, session-failure, raw transport exception all keep their
own distinct, now-observable codes). `LiveShadowStatus`'s pre-existing
`burst_requests`/`burst_captures`/`burst_failures`/`stale_bursts`
counters -- confirmed by direct code search to have been computed all
along but never once read by `engine_runtime.py`, and therefore
structurally invisible to `observation/status`'s own `advanced` payload
in production -- now reach that same already-untyped, schema-free dict
once per batch, alongside new reconciliation-count/last-failure
diagnostics. Schema `v58`, unchanged. **Real Camera Node re-proof, twice
over**: (a) the full, unmodified `ObservationEngineSessionManager`/
`_EngineSession`/`LiveCameraNodeShadowSession` production pipeline,
against the real Pi, with only the detector substituted for this
project's own established deterministic test fixture (MDv5/threshold/
tracker completely uninvolved, matching this milestone's own freeze
list) -- configured with the exact stale cold profile id, self-healed
within 13 real seconds, `evidence_burst_captures=1`/`evidence_burst_
failures=0`/`evidence_profile_reconciliation_count=1` via the real
`advanced` status API, a real `EvidenceCandidate` constructed with real
Pi bytes (the exact code path v13 proved structurally unreachable all
session, now proven reachable); no Visit was admitted in this bounded
~24-second smoke, correctly not required, and consistent with every
`EvidenceCandidate`'s own `temporary=True`/`shadow_only=True` design
(durable persistence is gated on Visit admission through the
deliberately untouched downstream precision gates, independently
reconfirmed unaffected by the full Tier 2 run). (b) three sequential
real burst requests directly at the transport layer, all succeeded
(the first self-healing in 0.450s, the next two using the corrected id
directly in ~0.29-0.31s each) -- proving the fix is sticky for the life
of the transport, not a one-shot fluke. A non-recoverable failure (a
deliberately wrong credential against the real Node) stayed
conservative: correctly classified `authentication_rejected`, zero
frames, no reconciliation attempted, no crash. Nine new tests (a real
`create_node_app` over a real socket via the established `RunningApp`
harness, real pairing, real HTTP), genuine RED proven by `git stash`
bisection against the pre-fix code (9/9 failed for the right reasons),
GREEN after the fix (53/53 in the affected file); one real regression
was found and fixed during the same RED->GREEN pass -- the new
`engine_runtime.py` diagnostics read initially broke an unrelated
`test_engine_runtime.py` fixture whose minimal fake provider didn't
implement `replay_semantic_facts()`/`active_track_count` (a latent gap
`session.status()` had simply never been called against before this
milestone), closed with this file's own established "diagnostics must
never break observation"/`report_metadata` discipline, re-run clean.
Tier 2: 686 passed / 11 xfailed across the full Camera Node/Observation
Engine/live-camera-session/multi-camera-concurrent-runtime/unified
-observation-status subsystem (24 files), zero failures attributable to
this change; one unrelated, real-thread/real-socket, isolation-confirmed
pre-existing flake (`test_camera_node_transport_acceptance.py`, a
disjoint Remote/Intermittent-WAN transport-spool/worker test file
sharing zero code with this diff, two different background-worker
retry-timing races across three full-batch runs, clean 8/8 and 4/4 in
isolation). Tier 3 (Core) correctly not run -- identical bounded-blast
-radius reasoning to prior comparably-scoped Camera Node milestones; the
diff touches only the evidence-capture transport, two additive
dataclass fields, and one additive best-effort diagnostics read, all
fully covered by Tier 2. `ruff check` clean (one pre-existing, out-of
-scope unused import elsewhere in the touched test file, confirmed via
`git diff` to predate this milestone). No admission/species/truth
semantics changed -- MDv5, threshold, NMS, tracker, candidate authority,
ambiguous-boundary arbitration, dead-anchor promotion, candidate quality
gate, `classifier_same_frame`, detector/independent corroboration,
scene-confusor, evidence quality/ranking, Visit grouping, BioCLIP,
Identification Eligibility, and Reviewed truth are all confirmed
untouched. Disclosed, not fixed (out of this milestone's bounded Host
-side scope): the Node's own earliest "camera missing/not available"
checks still carry no `X-MockingBird-Node-Error` header at the wire
level (would require touching and redeploying the separate
`mockingbird_camera_node` package); `engine_runtime._default_capture_
profile_alignment`'s own live-profile lookup (feeding `fov_alignment_
proven`/geometry lineage, deliberately frozen territory) still silently
degrades to `not_checked` rather than self-healing when the persisted
evidence profile is stale at session start -- evidence capture itself is
unaffected, proven live above. This closure does **not** authorize a
representative field cohort, v14, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A dependency,
updated:** the pre-existing 13-item list (unchanged in substance) plus
item (14), now split -- its defect-fix half **CLOSED / READY FOR
REPRESENTATIVE FIELD RE-PROOF**, its recall/evidence-survival
field-re-proof half **still REOPENED / WAITING FOR FIELD RE-PROOF**, and
the separate proposal-outcome ledger-cadence dependency (v13's own
disclosed 44.6% completeness) untouched and unwidened by this milestone.
The next representative field cohort must still gather: complete/intact
ledger evidence; independent denominator; recall; false-Visit rate;
fragmentation; duplicates; useful evidence; evidence survival; true
RTT-normalized latency; monitoring coverage; `classifier_same_frame`
field participation; dead-anchor field participation; ambiguous-boundary
evidence; precision-mechanism participation; Gate B check. No numeric
release budget is invented or advanced by this milestone.

**Proposal-Outcome Ledger Retention & Field-Reconciliation Completeness
v1 (2026-09-05) directly answers the separate proposal-outcome ledger
-cadence dependency v13 left open above -- does not close Lane R/Gate A,
does not authorize the next representative field attempt.** Classification
**A** (see §3 for the full record). Root-caused v13's own disclosed 44.6%
`proposal_outcome` completeness precisely: not a retention/query/writer
defect (all three independently exonerated), entirely a `scripts/field_
acceptance_ledger_snapshot.py` reconciliation defect -- `proposal_id`
-only deduplication silently collapsing a retryable proposal's own several
real, legitimate `blocked_continuation_pending`/terminal decision events
(64 of v13's real 156 distinct proposals, together accounting for all 350
real decision events) down to one each, plus a second, related
gap-coverage defect misreading `proposal_outcomes`' own naturally sparse
activity pattern as an interval gap. Direct re-analysis of v13's own real,
locally-preserved archive (gitignored, never retroactively edited) proves
**zero data was ever actually lost**: the union of all 21 real periodic
checkpoints recovers exactly 350/350 real decision events with zero gaps.
Fixed entirely inside the field-acceptance tool -- zero production
runtime files touched, zero schema change, zero admission/perception/
truth-semantics code changed: a `(proposal_id, decided_at)` reconciliation
identity (shared by `reconcile_ledger` and `build_merged_counterfactual_
window`), a new informational `recovered_distinct_entity_count` field, a
gap-coverage refinement (a payload's own proven-zero or, when
independently corroborated, proven-final `recorded_count` closes interval
ambiguity from session start -- guarding against the historical v12
"lone corrective fetch" shape), and a non-fatal cadence-safety-margin
warning. Capacity/churn analysis (v12 325 events/96.97min, v13
350/101.8min, real peak 37 events/5-min interval) shows the existing
1,000-record/60-minute retention bounds already carry 2.9x-27x margin
against every real churn rate measured to date -- no capacity increase
made or warranted. Validated via real-data `git stash` RED->GREEN
bisection against v13's own archive (proposal_outcomes 44.57% `PARTIAL`
-> 100%/`COMPLETE`; `raw_detections`/`track_generations` confirmed
byte-identical before/after -- zero regression), a permanent synthetic
regression fixture built from v13's own real decision-count histogram, a
burst-churn proof, a deliberate bounded-eviction proof (a genuinely
adversarial config still produces an honest, unmasked `PARTIAL`), and a
real, full end-to-end runtime smoke proof (real server, real Observation
Engine session with the real, unmodified `CounterfactualLedger` and
production retention config, hardware-free detector/transport fixtures,
real HTTP, the real CLI as a real subprocess) reconciling `COMPLETE` with
fully coherent counts. Tier 1: 34/34 (10 new). Tier 2: 290/290. Tier 3
correctly not run (zero production runtime diff). `ruff check` clean.
**V13 remains historically 44.6%, unchanged** -- this milestone fixes
future collection/reconciliation only. Does **not** authorize a
representative field cohort, v14, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A dependency,
updated:** the pre-existing 13-item list (unchanged in substance) plus
item (14) (unchanged from the milestone above: its defect-fix half
**CLOSED / READY FOR REPRESENTATIVE FIELD RE-PROOF**, its recall/
evidence-survival field-re-proof half **still REOPENED / WAITING FOR
FIELD RE-PROOF**) remain exactly as before -- and the separate
proposal-outcome ledger-cadence/completeness dependency this entry
answers now moves to **CLOSED / READY FOR REPRESENTATIVE FIELD
RE-PROOF**. The next representative field cohort may now simultaneously
field-re-prove: evidence-capture profile recovery; recall; evidence
survival; complete/intact `proposal_outcome` ledger coverage;
`classifier_same_frame` fallback; dead-anchor promotion; precision;
fragmentation; true latency; monitoring; Gate B. No numeric release
budget is invented or advanced by this milestone.

**Representative Daylight Gate A Field Acceptance v14 -- Corrected
Evidence-Path Re-Proof & Budget Convergence (2026-09-05) directly answers
the representative field cohort the two entries immediately above both
called for -- does not close Lane R/Gate A.** Classification **A** (see
§3 for the full record). 102.68 real minutes against a fresh disposable
instance and the real reference Camera Node (a routine pairing-code
refresh only -- the Node was already unpaired at session start),
independent acceptance recorder enabled throughout (5,182 frames, 4.10GB,
99.73% coverage, zero gaps >10s), accepted `field_acceptance_ledger_
snapshot.py` run detached for the full session (22 checkpoints).
**Both defect-fixes proved clean, live, together, for the first time**:
evidence-capture (204/204 bursts captured, 0 failures, 1 correct
self-heal) and proposal-outcome ledger completeness (`raw_detections`
22,260/22,260, `track_generations` 218/218, `proposal_outcomes` 191/191
across 90 distinct proposals -- **all three artifacts 100% `COMPLETE`,
zero gaps**, the cleanest of any cohort). 14 Visits admitted -- a
complete reversal of v13's zero-Visit pathology. **Rigorous independent
-recorder-first visual review** (12 full-session contact sheets; full
-resolution inspection of all 14 admitted-Visit windows, all 11 "silent"
`blocked_ambiguous_boundary` windows, all 8 `blocked_missing_evidence`
windows, all 4 `reject_insufficient_detector_corroboration` windows, plus
6 supplementary spot-checks) established a 17-encounter-period
conservative denominator (18 including one low-confidence broader
candidate) and **conservative recall of only 11/17 = 64.7%** (lower than
v12's 87.5%) -- **5 of 6 confirmed misses trace directly to
`blocked_ambiguous_boundary`** (one 11-overlapping-proposal cluster alone
spans ~310 continuous visually-confirmed seconds, including simultaneous
2-bird moments, with zero admission), the 6th to `reject_insufficient_
detector_corroboration` on a real, marginal, off-feeder ground-foraging
bird. Zero misses trace to `blocked_missing_evidence`, detector/tracker
failure, or the evidence-quality gate. **This directly and substantially
answers Ambiguous-Boundary Real-Subject Recall Correctness v1's own
disclosed "does the geometry-compatibility-tolerance question recur"
candidate fact: yes, materially, under real sustained/crowded activity**
-- distinct from, but sharing the identical root mechanism as, the
still-untouched, still-open v12 ~37:12 case. One confirmed false Visit
(1/14 = 7.1%, "other background/artifact," no species claim, zero Gate B
recurrence); both automated-tool "ambiguous" fragmentation units resolved
by visual review to correctly-represented, not fragmentation (0/8 = 0.0%,
now visually confirmed rather than merely inferred); duplicates 0/14 =
0%; useful evidence 78.6%/92.9% (closely matching v12's 77.8%/94.4%); one
`dead_anchor_promoted` occurrence evaluated on its merits for the first
time (visually confirmed real, sustained bird presence correctly
promoted, though only the final 58.6s of a ~316-second real bout); one
naturally-occurring simultaneous-subject pair, now visually confirmed
(two real birds in one frame, not merely ledger-inferred); zero
`classifier_same_frame`; zero scene-confusor participation (off by
default). **True latency: n=14, 100% measured, by far the richest sample
of any cohort** (v12 n=2, v13 n=0) -- median 82,920.6ms, p90 235,454.9ms,
p95 253,408.4ms, max 261,211.4ms -- against RTT-bounded calibration of
528 batches (527 calibrated, 99.8%, 0 clock jumps), directly corroborating
the previously-flagged Visit-Continuity-design tail-latency root cause
(v9) with the richest real evidence to date. Monitoring coverage 99.73%
(max gap 5.80s, zero gaps >10s), zero Node disconnects, `boot_id`
unchanged throughout, zero error/restart entries in the Node's own service
journal across the exact session window. One isolated field-tooling
defect (this session's own uncommitted scratch orchestration -- a stray
PowerShell CRLF in an extracted bearer token, and an untranslated WSL path
passed to a Windows-native process argument) found and fixed within ~90
seconds, before any real session time was affected -- no product runtime
file touched. Tier 1-3 correctly not run (zero production code changed);
schema unchanged (`v58`). `ruff check` not applicable (no Python source
changed). **Does not authorize a defect fix, v15, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.** Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. **Gate A dependency,
updated**: item (14) (evidence-capture + proposal-outcome ledger) now
**fully CLOSED, both halves**; item (12) (intact full-session ledger
coverage) **CLOSED**; item (4) (a second independently-varied true-latency
cohort) **CLOSED**; item (2) (second person-confound-free false-Visit-rate
cohort) **substantially advanced, not fully closed** (two mutually
-consistent cohorts, 5.6% and 7.1%, still short of a 3-cohort convergence
bar); the `blocked_ambiguous_boundary`/geometry-compatibility-tolerance
question moves from "candidate fact for the next cohort" to **this
cohort's own best-evidenced, most consequential open item** -- ahead of
the pre-existing items (1), (3), (5)-(11), (13), which remain otherwise
unchanged in substance (item (3)'s own fragmentation-tool-strength target
is materially advanced by this session's real, visually-confirmed 0/8
result, though its precise historical wording targeted a different prior
gap; item (5)'s 3+-simultaneous-subject bar remains unmet at 2). **Gate A
remains OPEN** -- Classification A does not mean Gate A passes, and does
not here: recall (64.7%) is a credible measurement of a real, substantial,
already-disclosed, deliberately-untouched-this-session limitation, not a
release-ready number.

**Sustained / Crowded Ambiguous-Boundary Recall Correctness v2 (2026-09-05)
directly answers whether v14's own richer evidence exposes a safe fix for
the `blocked_ambiguous_boundary`/geometry-compatibility-tolerance
limitation immediately above -- does not close Lane R/Gate A.**
Classification **B** (see §3 for the full record). Reconstructed all five
v14 ambiguous-boundary misses plus the ~310-second sustained/crowded case
from the preserved real-session ledger and confirmed, at materially
greater depth than the isolated v12 case allowed, that the dominant cause
is the *same* mechanism v1 already investigated and declined to fix
(`classify_boundary`'s out-of-scope geometry tolerance forming an
ambiguous link; `engine_runtime._live_chain_for_component`'s deliberate
"any admitted component member vetoes the whole component unconditionally"
policy then permanently blocking a later proposal, directly for miss #4
or transitively across several already-resolved hops for misses #10/#13
and the ~310s case, all tracing to the already-admitted `visit-
observation-candidate-010`/`-011` pair). Miss #7 shares the chartered v12
case's own same-tick transitive-bridging shape, with no stale-admission
complication. One new, disclosed-not-fixed structural asymmetry was
found (an already-resolved member's veto reach has no time bound, unlike
the existing 20-minute-bounded "still growing" deferral) -- proven, by
direct calculation, not to change any of v14's own five misses' recorded
outcomes, and not proven live-reachable in this project's own field data,
so left unfixed per this project's own established discipline. Zero
production code changed; three new, additive tests in `tests/
test_engine_runtime.py` reproduce all three distinct shapes directly
against the real, unmodified dispatch path, all passing. Tier 1 (121
passed) and Tier 2 (461 passed, identical count to v1's own run) both
fully green; Tier 3 not run (zero production diff). **The `blocked_
ambiguous_boundary`/geometry-compatibility-tolerance recall limitation
remains OPEN / ACCEPTED PRODUCT LIMITATION CANDIDATE FOR RELEASE-BUDGET
DECISION** -- the prior v1 conclusion (no safe correction without touching
geometry) is reconfirmed, not contradicted, at real-field scale; this is
**not** silently converted into acceptance of v14's own 64.7% recall
figure, which would require an explicit global budget/release review this
milestone does not perform. Gate A's remaining dependency list (items
(1), (3), (5)-(11), (13) from v14's own accounting) is unchanged in
substance. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**; does not authorize another admission change,
another field cohort, External Pre-Release Acceptance, or Final Release
Hardening.

**Updated, evidence reconstructed and a specific budget recommended, not
adopted (2026-09-07, Lane R Accumulated Latency Evidence &
Release-Budget Decision v1)** -- see
[lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md](lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md).
Read-only; no field session, no deployment. Pooled the five intact,
live-measured true-latency cohorts to date (v9 n=24, v10 n=11, v14 n=14,
Convergence v3 n=9, Convergence v4 n=11 -- 69 raw samples, six
independent calendar days) and independently recomputed every statistic
directly from raw per-sample JSON/tables rather than trusting prior
summaries: pooled median 103.9s (bootstrap 90% CI 80.3-114.8s), p90
259.2s (bootstrap 90% CI 198.6-331.8s), max 742.3s (v10; v11's own
reconstructed 865.2s remains disclosed as supporting-only, not
independently re-verified). **Found and disclosed one non-material
evidence-integrity correction**: v10's own report states p90 183.3s; every
standard percentile method applied to v10's own 11 published per-sample
values instead yields 201.5s (183.3s is candidate-005's own individual
value, not the 90th percentile) -- carried forward unverified through
five subsequent documents, including this section's own prior entries and
`roadmap.md`'s "Numeric release budgets"; the correction changes no prior
conclusion (201.5s still falls inside every previously-stated band).
**A bootstrap-resampling analysis found that the per-cohort p90 scatter
this section's own prior entries repeatedly cited as "non-convergence"
(173.9-385.1s) is statistically consistent with ordinary small-sample
estimation noise at these cohort sizes (9-24), not evidence of a moving
target** -- every individual cohort's own observed p90 falls inside its
own bootstrap 90% interval drawn from the pooled set; the median, by
contrast, is genuinely tightly convergent. Every >300-second sample
across every cohort was reconfirmed to trace to the same already-accepted
Visit-Continuity/ambiguous-boundary mechanism (no new perception
investigation launched; no new defect found). Both explicit v4 acceptance
qualifications from the entry above were resolved cleanly: the 75-minute
duration is accurate to the driver's own internal accounting; recorder
readiness was proven before Observation start for v4 specifically.
**Proposes a specific, narrow budget for external release-authority
acceptance**: typical latency ~80-115s (numeric); upper-tail behavior
disclosed qualitatively, not as a tight SLA; a 20-minute architectural
decision-horizon ceiling reference, not a statistically-fit maximum;
sustained/crowded-activity latency and recall disclosed together as one
product characteristic. **This milestone does not itself adopt this
budget, close Lane R, or declare Gate A passed -- it is a recommendation
for the next global reconciliation to accept, correct, or reject, exactly
as the recall decision above required.** The status line at the top of
this section stands exactly as written -- Lane R remains OPEN, TRUE
LATENCY TAIL EVIDENCE REMAINS. No field cohort, External Pre-Release
Acceptance, or Final Release Hardening is authorized by this closure.

**Closed 2026-09-07 (Lane R Release-Budget Adjudication & Gate A Decision
v1)** -- see
[lane-r-release-budget-adjudication-gate-a-decision-v1-report.md](lane-r-release-budget-adjudication-gate-a-decision-v1-report.md)
and the rewritten status line at the top of this section. This is the
"next global reconciliation" the entry immediately above deferred to.
Read-only; no field session, no deployment, no product/schema/tooling
code changed. Independently re-verified every decisive fact the entry
above relied on directly against primary sources -- the v10 p90
correction (recomputed from v10's own 11 published per-sample values via
five standard percentile conventions, confirming 201.5s exactly), the
`≥12`-sample criterion's exact origin in
`scripts/field_acceptance_session_driver.py` (`target_sample_count: int =
12`, a per-session stopping heuristic, confirmed by direct source
inspection, not a statistical minimum), the bootstrap uncertainty method,
every `>300`-second causal classification, and -- read directly from its
own primary text, not only the correction's characterization -- the
rejected 2026-09-05 PASS's exact two disqualifying defects (a recall
budget stated verbatim as "excluding the disclosed limitation"; a latency
tail table whose own stated max range, "261.2s-307.4s," omits v10's
already-accepted 742.3-second maximum). No decisive calculation was found
wrong. **Accepted the proposed budget exactly as recommended, repeating
neither disqualifying defect**: recall is not re-touched (already
separately closed 2026-09-06); both 742.3s and the reconstructed 865.2s
are disclosed prominently in the adopted ceiling reasoning, never omitted.
**Gate A: PASS. Lane R: CLOSED.** All eight Gate A dimensions plus
multi-subject Visit correctness now carry an accepted disposition -- see
the rewritten status line above for the complete accepted budget and
`roadmap.md`'s own now-stale-and-disclosed Gate A prose. Does **not**
start External Pre-Release Acceptance or Final Release Hardening -- both
remain separately gated and unauthorized by this milestone. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged.

### S. Actual Final Release Hardening

**Status:** LAST.

Final Release Hardening begins once the intended release capability set
stabilizes -- a readiness judgment, not a version-number boundary (see
"Release readiness vs. continued capability work" in
[roadmap.md](roadmap.md)). Release-critical correctness always outranks
optional capability; capability development may continue up to that point
whenever it materially improves the product without endangering a
release-critical dependency. Once Final Release Hardening begins, no
major capability is added without explicit authorization based on
concrete necessity, and focus narrows to: defects; reliability;
performance; UX; compatibility; packaging; security; documentation;
installation; upgrade/recovery; field failures; External Pre-Release
Acceptance findings; release-artifact validation; dependency/license
closure; clean-install repetition; internal release-candidate builds (an
engineering mechanic, not a separate product stage). External Pre-Release
Acceptance -> Final Release Hardening -> the one public launch -- no
separate beta release precedes it.

**2026-09-07 update (Gate G plan prepared, not started):** *Release-Gate
Reconciliation & External Acceptance Preparation v1* reconciles
`roadmap.md`'s Gate A prose to this lane's own already-accepted `CLOSED`
status (§6.R, above) and prepares -- without starting -- the concrete
Gate G (External Pre-Release Acceptance) plan this lane's own
precondition names: see
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md)
and
[release-gate-reconciliation-external-acceptance-preparation-v1-report.md](release-gate-reconciliation-external-acceptance-preparation-v1-report.md).
Gate G itself remains **not started**: no participant recruited, no
cohort fixed, no finding collected. This lane's own status remains
**LAST**; current authorization to begin Gate G execution or this lane
remains `NONE`.

**2026-09-08 update (entry-readiness dependencies closed, Gate G still
not started):** *External Acceptance Entry Readiness & Uninstall Closure
v1* closed the two concrete entry dependencies this section's own
2026-09-07 update left open: the uninstall procedure is now confirmed,
documented, and proven on real native-Windows hardware (see the CURRENT
PHASE narrative, above, and
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md)),
and a private Gate G cohort/consent/findings-intake contract is now
proposed (not approved) in
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md).
**Gate G remains not started**: no participant recruited, no cohort
fixed, no finding collected, no owner approval granted for any proposed
value. This lane's own status remains **LAST**; current authorization to
begin Gate G execution or this lane remains `NONE`.

**2026-09-08 update (internal candidate built and verified; Gate G still
not started):** *External Pre-Release Acceptance -- Private Cohort v1*
(see
[external-pre-release-acceptance-private-cohort-v1-report.md](external-pre-release-acceptance-private-cohort-v1-report.md))
built a real, current internal acceptance candidate from the accepted
baseline (HEAD `2fe2729`) and independently verified it three ways (build
manifest, independent `verify_release_artifact.py`, and the running
instance's own `GET /api/product/instance` self-report on real
native-Windows hardware) -- the concrete "internal release-candidate
builds" mechanic this lane's own framing paragraph, above, already
anticipates. Proved recovery after an unclean stop; found and disclosed
one real, non-release-blocking Doctor defect (Sev-2, Storage check false
`FAIL` on a normal pre-wizard-completion instance) and one secondary
non-blocking observation (no documented stop method yields a shutdown
Doctor considers clean) -- neither touches any Gate A dimension. Prepared
all nine Gate G participant materials this gate's own plan calls for, as
a proposal only. **Gate G itself remains not started**: no participant
recruited, no cohort fixed, no finding collected from an actual
participant, no build distributed, no owner approval granted for any
proposed value -- this milestone's own report presents a complete owner
approval checkpoint (its §5) rather than proceeding past it. This lane's
own status remains **LAST**; current authorization to begin Gate G
execution or this lane remains `NONE`.

**2026-09-10 update (Final Release Hardening & Launch Readiness v1
executed):** this lane's own framing paragraph, above, is now substantially
enacted -- see
[final-release-hardening-launch-readiness-v1-report.md](final-release-hardening-launch-readiness-v1-report.md).
Versioning given an intentional public identity (`0.1.0` -> `1.0.0`);
release-artifact SBOM/signing machinery added (unconditional SBOM, opt-in
signing -- no real key exists, none fabricated, the owner-facing key
procedure is documented); seven real public-documentation gaps closed;
known-defect triage completed across 42 items (zero release blockers, zero
FIX NOW); the real Host and Camera Node artifacts built from a clean commit
and independently verified; the complete install/first-run/health/
shutdown/restart/recovery path exercised on real native-Windows hardware
against the *built artifact itself*; the real reference Camera Node's
wire-protocol/checksum compatibility confirmed via a non-destructive
preflight (no upgrade performed, live pairing untouched). One real,
already-twice-disclosed Doctor `Application`-check limitation was
reproduced live and precisely root-caused (not fixed -- a real fix touches
the boot sequence/Doctor/API surface together and needs new tests). **Gate
G remains not started** -- this milestone did not recruit a participant,
fix a cohort, or distribute a build, matching its own governing brief's
explicit "do not start a private cohort" instruction. This lane's own
status remains **LAST**; current authorization to begin Gate G execution
remains `NONE`. **Release-readiness verdict: READY FOR OWNER RELEASE
DECISION** -- the owner-only steps remaining (a real signing key if
desired; the standing BirdNET commercial-adjacent legal question; the
publish/announce decision itself) are named explicitly in the report's §9
and are not, and cannot be, resolved by this or any engineering milestone.

## 7. One-release doctrine

MockingBird's public release target is a trustworthy single-site/home
observatory with:

- dependable visual observation;
- strong Visit/evidence quality;
- reviewed Observation truth;
- Today/history usefulness;
- native Camera Node golden path;
- ONVIF + RTSP/RTSPS;
- offline/recorded/camera-trap ingest;
- professional/research acquisition metadata;
- conservation reporting;
- effort/coverage;
- research-safe export;
- Camtrap DP;
- bounded contributor/research capability;
- Local Only privacy;
- installation/onboarding/recovery;
- diagnostics;
- storage;
- backup;
- versioning;
- security;
- OSS/release presentation;
- clean-install acceptance;
- integrated field acceptance.

Acoustics may ship as the now-accepted optional capability. Remote
LTE/solar/custom field hardware are not release blockers.

## 8. After-release queue

Explicitly keep:

- complete remote/intermittent-WAN/LTE field deployment;
- solar/battery;
- custom CM4/CM5 hardware;
- research-grade remote-field acceptance;
- broad multi-site;
- native mobile;
- advanced acoustic analytics;
- mature automatic mammal species identification.

Unless new evidence creates a dependency, do not promote these into
release scope.

## 9. Later / demand-driven queue

Examples:

- GenICam;
- GigE Vision;
- USB3 Vision;
- radiometric thermal;
- specialized industrial cameras;
- individual-animal recognition;
- population estimates;
- behavior prediction;
- causal ecological modeling;
- large cloud-first infrastructure.

## 10. Observability cross-cutting requirements

Keep visible as release requirements:

- structured error taxonomy;
- stable machine-readable codes;
- user-safe messages/actions;
- component attribution;
- recoverability;
- correlation/session identifiers where applicable;
- structured bounded logs;
- health transitions;
- reconnect/drop/failure counters;
- Visit/model/storage/coverage counters;
- support bundles;
- no uncontrolled raw/high-cardinality media telemetry.

Normal users get actionable diagnostics. Advanced support gets raw
details.

## 11. API / schema / version compatibility

Preserve:

- externally consumed schema/version discipline;
- additive compatibility where feasible;
- migration safety;
- Host ↔ Camera Node compatibility;
- upgrade/recovery semantics;
- explicit capability/version reporting.

Do not casually make breaking changes merely because all local tests can
be updated together.

## 12. Security / release questions

Keep visible:

- network exposure;
- HTTPS/TLS posture;
- secure remote-access decision;
- secret/credential storage;
- dependency/model supply chain;
- checksum/update verification;
- support-bundle disclosure;
- public SECURITY policy.

Do not claim encrypted camera/RTSP/ONVIF credentials at rest unless
current code proves it.

## 13. Development operating rules

**Bounded archaeology.** Start with governing docs and directly affected
code. Expand only when evidence reveals dependencies.

**Separate investigation and implementation.** When uncertainty is real:
(1) diagnose; (2) lock the contract; (3) implement.

**Validation tiers.** Tier 1: focused tests. Tier 2: affected subsystem
validation. Tier 3: full Core only when cross-cutting production risk
warrants it.

**Audit budget.** Default: one implementation/self-review; one acceptance
review. Additional audits require a concrete unresolved risk.

**Concurrent writers.** Never allow multiple Claude writer sessions in the
same working tree. Separate worktrees are required for parallel
implementation. Read-only agents are fine.

**Git.** Do not push without explicit user authorization. Protect the
seven preserved files (see below).

### Preserved untracked detector files

These seven known superseded/untracked detector files must remain
untouched -- not edited, deleted, renamed, staged, incorporated, or
cleaned up -- by any task working in this repository:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

They duplicate the accepted `multi_scale_strategy.py`/
`multi_scale_benchmark.py` work and were left uncommitted on purpose
rather than cleaned up; re-verify their presence untouched at the start of
each session that touches this repository.

## 14. Validation baselines

**Latest accepted Core checkpoint (Pre-Release Trust & Correctness
Correction v1):** 6057 passed / **5 failed** / 4 skipped / 35 deselected
(`slow`-marked) / 11 xfailed, 41m56s -- run twice this milestone (a first
attempt found 19 failures, 15 real regressions this milestone's own UI-01/
SEC-2 fixes exposed in existing tests plus 4 already-matching this
checkpoint's own pre-existing set; every real regression fixed and this
second, accepted attempt run clean of them). All 5 remaining failures
independently re-confirmed via direct `git stash` bisection against the
unmodified baseline this same session (not merely cited):
`test_doctor_camera_node_transport.py`'s own pair and
`test_environmental_context.py::test_temperature_band_established_once_
enough_days_are_cached` reproduced the identical failure standalone against
the stashed baseline; `test_place_change_summary_repository.py::test_api_
round_trip_exposes_change_detection_fields` is this section's own long-
documented recurring date-sensitive fixture flake (see below), also
reproduced standalone; `test_transport_worker.py::test_retryable_failure_
returns_item_to_failed_retryable_and_eventually_succeeds` passed standalone
against the stashed baseline and passed again with this milestone's changes
present, consistent with this same file's own already-documented load-
induced-timing-flake class (a different specific test in the identical
file, `test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_
on_next_success`, is the one previously recorded here) rather than
reproducible in isolation either way. No schema change (`v59`, unchanged).
Full existing e2e suite (189 tests, 5 new this milestone): 187 passed / 2
failed, both independently re-confirmed pre-existing via the identical
bisection technique -- `reviewed-product-loop.spec.ts` (already documented
below across multiple prior milestones) and `notification-preferences.
spec.ts::clicking an insight alert opens Place Story already scoped to
wildlife` (newly bisected this milestone, reproduced identically on the
unmodified baseline). See
[pre-release-trust-correctness-correction-v1-report.md](pre-release-trust-correctness-correction-v1-report.md)
for the complete record.

**External Pre-Release Acceptance -- Private Cohort v1 did not run a full
Core checkpoint** -- disclosed explicitly here so this is never mistaken
for one. Zero product/schema/tooling code changed (its only artifacts are
two new documentation files, a build-owned `dist/` output already
excluded from version control, and this file); a Core run would not
exercise anything beyond what the immediately-prior, already-fully-Core
-clean milestone already covered, and would not exercise the real
native-Windows build/launch/recovery/Doctor evidence that actually bears
on this milestone's own claims. It ran Tier 1 (every directly relevant
test file, fresh this session, not merely cited: `test_single_app_
runtime.py` 21 passed, `test_local_product_packaging.py` 85 passed,
`test_version_provenance.py` + `test_verify_release_artifact.py` 17
passed) + Tier 2 (`test_deploy_windows_dev.py`, `test_install_camera_
node.py`, `test_camera_node_packaging.py`, `test_local_backup_
recovery.py`, `test_cross_install_backup_restore.py`, `test_clean_
install_acceptance.py`, `test_upgrade_path_acceptance.py`, `test_
doctor.py`: 384 passed) -- **507 passed, 0 failed**, zero new `ruff`
findings on every file this milestone's own verification touched. Its own
real native-Windows evidence (build identity confirmed three independent
ways, recovery after an unclean stop, the disclosed Sev-2 Doctor finding)
is the validation that actually bears on its claims -- see
[external-pre-release-acceptance-private-cohort-v1-report.md](external-pre-release-acceptance-private-cohort-v1-report.md)
§3 and §9. The "Latest accepted Core checkpoint" below remains the most
recent actual full-suite number.

**External Acceptance Entry Readiness & Uninstall Closure v1 did not run
a full Core checkpoint** -- disclosed explicitly here so this is never
mistaken for one, matching this section's own established convention
(see "Gate A Measurement Closure v1," below). Per its own documented
Tier 3 decision (one packaging-text constant plus one new test; zero
application/schema/API/frontend logic changed -- not warranted for a
footprint this narrow, and a Core run would not have exercised the real
Windows file-lock/native-hardware behavior that actually mattered for
this milestone's own claims), it ran Tier 1 (every directly touched/new
test file in full: `test_single_app_runtime.py` 21 passed,
`test_local_product_packaging.py` 85 passed) + Tier 2 (every immediately
affected packaging/lifecycle subsystem: 388 passed across
`test_deploy_windows_dev.py`, `test_install_camera_node.py`,
`test_camera_node_packaging.py`, `test_local_backup_recovery.py`,
`test_cross_install_backup_restore.py`, `test_clean_install_
acceptance.py`, `test_upgrade_path_acceptance.py`, `test_version_
provenance.py`, `test_doctor.py`) -- **494 passed, 0 failed**, zero new
`ruff` findings on every changed file. Its own real-hardware evidence
(native-Windows file-lock behavior, disposable-instance data
persistence/reconnection) is the validation that actually bears on its
claims -- see
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md)
§4 and §6. The "Latest accepted Core checkpoint" below remains the most
recent actual full-suite number.

> **Pointer added 2026-09-25 (Native-Windows Field Reliability Corrections v1
> acceptance-closure).** The checkpoint ledger below is historical and stops at
> schema `v59`. It is **not** the current Core result. The most recent full Core
> run is the one recorded in §3's acceptance-closure record: `11 failed, 6205
> passed, 4 skipped, 35 deselected, 11 xfailed` at schema **v61**, with zero
> failures attributable to that milestone. Reconciling this ledger (and the rest
> of this file, un-reconciled since 2026-09-12) belongs to *Documentation /
> Diagnostics / Release Engineering Closure*, which is **not yet authorized**.

**Latest accepted Core checkpoint (Final Release Hardening & Launch
Readiness v1):** 5995 passed / **4 failed** / 4 skipped / 35 deselected
(`slow`-marked) / 11 xfailed, 2729s (45m29s) -- run once (this milestone
changed no product/schema/detector code; packaging/versioning/documentation
changes are cross-cutting enough to still warrant Tier 3, per its own
governing brief). All 4 failures independently re-confirmed via direct
`git stash` bisection against the unmodified baseline this same session
(not merely cited): `test_place_biodiversity_summary_repository.py`'s own
pair and `test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields` reproduced the identical assertion
failure standalone against the stashed baseline; `test_transport_worker.py
::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_
next_success` passed standalone against the same stashed baseline,
matching its own already-documented load-induced/non-reproducible-in
-isolation nature. No schema change (v59, unchanged). Also newly measured
and disclosed this checkpoint: a full-repo `ruff check .` (never wired
into Fast/Core/Full/CI) surfaces 163 findings, independently confirmed
100% pre-existing via the identical bisection technique -- every prior
"ruff clean" claim in this file's own history was necessarily scoped to
the files each milestone touched, never a full-repo sweep. See
[final-release-hardening-launch-readiness-v1-report.md](final-release-hardening-launch-readiness-v1-report.md)
§7 for the complete record.

**Prior accepted Core checkpoint (Product Operations &
First-Observation Completion v1):** 5985 passed / **1 failed** / 4
skipped / 35 deselected (`slow`-marked) / 11 xfailed, 43m51s -- the
accepted, final of three attempts this milestone ran (see the top-of-file
dated entry for the full three-attempt record: a first attempt found 6
failures crossing local midnight mid-run, 5 individually bisected/
root-caused to the unmodified baseline or an already-documented flaky
-test file, the 6th this milestone's own new fault-injection test's own
bug, found and fixed by this very validation, never in production code; a
second attempt, same calendar day, found 5 with the bug still present;
this accepted final attempt has the fix applied). The one remaining
failure, `test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields`, is the identical pre-existing,
long-documented flake named in the immediately-prior checkpoint below,
independently re-confirmed via direct `git stash` bisection against the
unmodified baseline this same session (not merely cited) --
`test_place_biodiversity_summary_repository.py`'s own pair, flaky by
nature rather than deterministic, did not reproduce this particular run.
No schema change (v59, unchanged). See
[product-operations-first-observation-completion-v1-report.md](product-operations-first-observation-completion-v1-report.md)
§7 for the complete record.

**Prior accepted Core checkpoint (Release Reliability & First-Run
Recovery v1):** 5969 passed / **4 failed** / 4 skipped / 35 deselected
(`slow`-marked) / 11 xfailed, run twice this milestone (a first attempt
independently confirmed the `test_camera_node_packaging.py` failure below
was real and reproducible before the fix; a second complete run, 2321.59s
/ 38m41s, is the accepted figure here). All 4 failures independently
re-confirmed the identical pre-existing, long-documented,
real-wall-clock-date/load-timing-sensitive flakes this section has now
recorded across ten-plus prior milestone checkpoints, in files this
milestone never touched: the `test_place_biodiversity_summary_
repository.py` pair, `test_place_change_summary_repository.py::test_api_
round_trip_exposes_change_detection_fields` (this section's own
recurring `'insufficient_recent_coverage' == 'higher_recent_presence'`
pair), and `test_transport_worker.py::test_sticky_diagnostic_set_on_
protocol_incompatibility_and_cleared_on_next_success` (a previously
-documented load-induced timing flake, Calm Attention & Notifications
v1/Mobile & Remote Experience v1 checkpoints). A fifth, single-run-only
failure (`test_observation_camera_node_live.py`, a file this milestone
did not itself edit, though it does exercise Camera Node code this
milestone's own changes touch adjacent parts of) was independently
confirmed non-reproducible in isolation (53/53 passed) and in the second
complete run (53/53 passed again) -- a genuine, non-reproducible,
load-dependent flake, not a regression. Two real, previously-unknown
defects were found and fixed before this figure was accepted, not left in
it: a test-suite hang (two tests' `uvicorn.run` mocks silently bypassed by
this milestone's own `runtime.py` change, fixed by mocking `Server.run`
instead) and a Camera Node packaging omission
(`test_camera_node_packaging.py::test_node_files_cover_the_real_internal_
import_closure` caught `hardware_health.py` missing from `NODE_FILES`,
fixed) -- see
[release-reliability-first-run-recovery-v1-report.md](release-reliability-first-run-recovery-v1-report.md)
for the complete record of both. No schema change (v59, unchanged). This
sandbox measured markedly slower than its own documented ~9-minute Core
baseline both times this milestone ran it (system load average 4.5+
observed directly, no memory pressure) -- disclosed as environmental, not
a product regression.

**Prior accepted Core checkpoint (Place Feature Comparison & Habitat
Outcomes v1):** 5897 passed / **4 failed** / 3 skipped / 23 deselected
(`slow`-marked) / 11 xfailed, 276 warnings -- `scripts/verify_core.py`'s
own `pytest -m "not slow"` convention, run once as one bare background
pass (2718.89s / 45m18s). All 4 failures independently confirmed
pre-existing/unrelated this session, not merely assumed:
`test_place_biodiversity_summary_repository.py::test_api_route_returns_
the_summary`, `::test_human_correction_updates_place_biodiversity_
intelligence_correctly`, and `test_place_change_summary_repository.py::
test_api_round_trip_exposes_change_detection_fields` (the identical
`AssertionError: assert 'insufficient_recent_coverage' ==
'higher_recent_presence'` this section's own prior checkpoint already
named) all reproduce byte-identically against this exact starting commit
via `git stash push -u` isolation; `test_camera_node_capture_
contention.py::test_analysis_stream_disconnect_during_inflight_capture_
releases_camera_lock` (unrelated Camera Node code, untouched by this
milestone) passes cleanly in isolation -- a concurrent-load timing flake,
not a deterministic one. No schema change (v59, unchanged).

**Prior accepted Core checkpoint (Ambiguous-Boundary Real-Subject Recall
Correctness v1):** 5679 passed / **1 failed** / 3 skipped / 23 deselected
(`slow`-marked) / 11 xfailed, 236 warnings -- `scripts/verify_core.py`'s
own `pytest -m "not slow"` convention, run once as one bare foreground
pass (1991.73s / 33m11s). **A genuinely different failure from every prior
checkpoint's own documented pair, not a recurrence of it:**
`tests/test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields`
(`AssertionError: assert 'insufficient_recent_coverage' ==
'higher_recent_presence'`) -- a different file, a different assertion,
and a different symptom string from `test_place_biodiversity_summary_
repository.py`'s own long-documented pair (which did *not* fail this
checkpoint; see the immediately-following "Prior" entry for its own
account). Independently re-confirmed pre-existing and unrelated this
session, not merely assumed: this milestone's own four changed files
(`engine_runtime.py`, `test_engine_runtime.py`, both contract/state docs)
were `git stash`-isolated back to the exact starting HEAD (`40c2560`),
and the identical test re-run on that clean baseline fails identically,
byte-for-byte. This milestone touches zero Place Intelligence/
change-summary/journal/biodiversity code -- `engine_runtime.py`'s own
diff has no import-path relationship to `PlaceChangeSummaryRepository`/
`build_place_activity_report` at all. The failing fixture compares a
fixed historical test date (`PERIOD_START = 2026-08-21`) against some
real-clock-relative "how recent is recent" computation -- consistent with
the same general class of real-wall-clock-date-dependent Place
Intelligence test fragility this section's own prior entries already
extensively document for the *other* pair (see "Prior accepted Core
checkpoint," below, and "Historical Species-Status..." further down), not
independently traced to its own internal mechanism by this milestone
(out of this milestone's own scope). Zero new `ruff` findings on any of
the four changed files (identical `git stash`-isolated comparison). No
schema change (v58, unchanged). See this milestone's own report's "Tier 3
decision" section for the complete account.

**Prior accepted Core checkpoint (All-Alternate Subject Evidence Recall
Correctness v1):** 5672 passed / **2 failed** / 3 skipped / 23 deselected
(`slow`-marked) / 11 xfailed, 236 warnings -- `scripts/verify_core.py`'s
own `pytest -m "not slow"` convention, run once as one bare foreground
pass (2613.39s / ~43m33s). The 2 failures
(`tests/test_place_biodiversity_summary_repository.py::test_api_route_
returns_the_summary`, `::test_human_correction_updates_place_
biodiversity_intelligence_correctly`) are independently confirmed
pre-existing and unrelated, not merely assumed: all seven files this
milestone touched (`candidate_quality_gate.py`, `product_repository.py`,
two contract docs, `VisitEvidenceSequence.tsx`, two test files) were `git
stash`-isolated back to the exact starting HEAD (`b4a2a660`), and the
identical two tests re-run in isolation fail identically on that clean
baseline, with the exact same assertion mismatch
(`AssertionError: assert 'seen_before' == 'new'`) -- Place Intelligence
biodiversity-taxonomy-history logic, zero code-dependency relationship to
Visit admission/evidence/quality-gate code this milestone touched. This is
the same already-repeatedly-documented pair this section's own prior
entries name recurring across numerous earlier Core checkpoints (see the
immediately-following entry and "Historical Species-Status..." below for
the fullest prior account). Zero new `ruff` findings on any touched
production file (same `git stash`-isolated baseline-vs-changed comparison:
57 pre-existing findings in `product_repository.py`, identical count/
content before and after; `candidate_quality_gate.py` and both new/touched
test files clean). No schema change. See this milestone's own report's
"Tier 3 decision" section for the complete account.

**Prior accepted Core checkpoint (Hard-Negative Visit Admission
Precision & Species-Escalation Correctness v1):** 5504 passed / **2
failed** / 3 skipped / 23 deselected (`slow`-marked) / 11 xfailed -- 5543
collected, `scripts/verify_core.py`'s own `pytest -m "not slow"`
convention, run once as one bare foreground pass (1868.59s / ~31m08s), the
first full-suite run in this section run as a single unbroken process
rather than concurrently-chunked files. The 2 failures
(`tests/test_place_biodiversity_summary_repository.py::test_api_route_
returns_the_summary`, `::test_human_correction_updates_place_
biodiversity_intelligence_correctly`) are independently confirmed
pre-existing and unrelated, not merely assumed: both files this milestone
touched (`candidate_quality_gate.py`, `product_repository.py`) were `git
stash`-isolated back to the exact starting HEAD (`58c0634`), and the
identical two tests re-run in isolation fail identically on that clean
baseline, with the exact same assertion mismatches
(`new_taxa`/`historical_status` -- Place Intelligence biodiversity
-taxonomy-history logic, zero code-dependency relationship to Visit
admission/evidence/quality-gate code this milestone touched). This is the
same already-repeatedly-documented pair this section's own prior entries
name recurring across numerous earlier Core checkpoints (see "Historical
Species-Status..." entry, below, for the fullest prior account of this
exact pair). Zero new `ruff` findings on either touched production file
(same `git stash`-isolated baseline-vs-changed comparison: 57 pre-existing
findings in `product_repository.py`, identical count/content before and
after; `candidate_quality_gate.py` and the new test file both clean). No
schema change. See this milestone's own report's "Validation" section for
the complete account.

**Prior accepted Core checkpoint (Pending-Proposal Evidence Preservation
& Arbitration Fallback Correctness v1):** 5357 passed / 1 failed / 3
skipped / 11 xfailed / 23 deselected (slow-marked) -- 5372 collected via
`scripts/verify_core.py`'s own `pytest -m "not slow"` convention, **not**
a bare run (unlike the immediately-prior checkpoint below, noted
honestly: this run is not a strict superset of that one -- it deliberately
excludes the 23 `slow`-marked tests `verify_core.py` itself always
excludes). Run as four sequential-file, concurrently-executed chunks
covering the complete alphabetical test-file list with no overlap or gap
(this environment's own background-task tooling caps a single foreground
run below this suite's real ~19-minute runtime; the four chunks' own
collected-test counts sum to exactly 5372, confirming complete,
non-duplicated coverage). The one failure
(`test_temporal_capture_cli.py::test_run_capture_end_to_end_reconnect_
produces_a_native_session_timeline`) is independently confirmed unrelated,
not merely assumed: zero code-dependency relationship to any file this
milestone touched; passes cleanly on the exact pre-fix baseline (`git
stash`-isolated); passes 5/5 consecutive runs in isolation with the fix in
place; only failed once, inside the one chunk running 80 other test files
concurrently alongside three sibling chunks (12 real CPU cores, all four
chunks together saturating them) -- a genuine, pre-existing, real-wall-
clock-timing-sensitive test (its own docstring already names "Bounded
latest-frame coalescing under host backpressure," a `--duration 5`
real-time capture window) made visible only by this investigation's own
necessary concurrent chunked execution, not a product defect. See this
milestone's own "Latest accepted milestone" entry in §1, above, and its
full report's own "Validation" section for the complete account. Zero new
`ruff` findings on any touched file (2 pre-existing, unrelated findings in
`tests/test_engine_runtime.py` independently confirmed present on baseline
`b37656d` via clean-checkout bisection, left untouched). No schema change.

**Gate A Measurement Closure v1 did not run a full Core checkpoint** --
disclosed explicitly here so this is never mistaken for one. Per its own
documented Tier 3 decision (additive/narrow production-code footprint;
not warranted "solely because this is called Gate A," per its own explicit
governing instruction), it ran Tier 1 (every directly touched/new file,
including two brand-new pure modules and their own test files) + Tier 2
(every immediately affected subsystem -- candidate authority, evidence/
fallback, persistence, repository reads, API visibility, acceptance
recorder, time utilities): **440 passed, 0 failed, across 18 test files**,
zero new `ruff` findings (verified against a stashed baseline covering the
exact same file set). See its own report's "Validation"/"Tier 3" sections
for the complete file list and reasoning. The "Latest accepted Core
checkpoint" above remains the most recent actual full-suite number.

**Prior accepted Core checkpoint (Historical Species-Status ("New" vs.
"Seen Before") Correctness v1):** 5277 passed / **0 failed** / 3 skipped /
11 xfailed (37m09s -- run bare, `python3 -m pytest -q`, with no `slow`
-marker deselection, so a strict superset of every prior checkpoint cited
below). This is the first zero-failure full Core checkpoint recorded
anywhere in this section: every checkpoint immediately below, back through
"Camera / Source Experience & First-Hour Setup Closure v1," reported
exactly the same 2 failures, the `test_place_biodiversity_summary_
repository.py` pair (`test_api_route_returns_the_summary`, `test_human_
correction_updates_place_biodiversity_intelligence_correctly`), each time
independently re-confirmed pre-existing and each time correctly judged
unrelated to that session's own changes -- this milestone is the first to
have actually root-caused and fixed that pair, rather than re-bisecting
past it again. Root cause and fix: see this milestone's own "Latest
accepted milestone" entry in §1, above, and its full report. Zero other
regressions; the 231 warnings are pre-existing, unrelated stdlib/
SQLAlchemy/FastAPI deprecation notices, not new findings.

**Prior accepted Core checkpoint (Whole-Product UI / Accessibility /
Performance Closure v1):** 5166 passed / 2 failed / 3 skipped / 23
deselected (slow-marked) / 11 xfailed (26m50s), run standalone after an
earlier concurrent-with-e2e attempt produced real, directly observed
SQLite lock contention (not re-used as evidence -- see the milestone
report's "A note on validation methodology"). Both failures are the
identical, already-documented pre-existing `test_place_biodiversity_
summary_repository.py` pair (`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`),
independently re-confirmed as pre-existing across now at least nine
consecutive prior milestone checkpoints below -- not re-bisected again
this session given zero code this milestone touched has any relationship
to biodiversity-summary computation. No schema change, so no guard-rail
assertions needed touching. 7 new backend tests across two files (2 in
`tests/test_review_queue_product_mode.py`, 5 in `tests/test_product_
health.py`), each independently RED-confirmed against the pre-fix code
via `git stash` and GREEN after; `ruff check` confirmed zero new findings
via a direct clean-baseline bisection per touched file (83 pre-existing
findings total, unchanged before/after: `main.py` 26/26,
`product_repository.py` 57/57); `tsc --noEmit`/`vite build` clean. Full
e2e suite (136 specs, 8 new -- 2 new spec files plus 6 added to the
existing viewport matrix): 135 passed / 1 failed, the one failure the
same pre-existing, now precisely-diagnosed `reviewed-product-loop.spec.ts`
gap immediately below in this same list, independently reproduced
identically on the unmodified 128-spec baseline (127 passed / 1 failed,
byte-identical single assertion) -- confirming no regression from this
milestone's own product/test changes. See
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the complete record, including a real, live-verified P0 fix (Review
Queue default-tab misclassification of imported Visits), three P1 fixes
(two Fast Review keyboard focus-management defects, the acoustic health/
status gap), and two investigated-and-confirmed-not-regressions
(Stream Detail/Analytics list bounding, both intact).

**Prior accepted Core checkpoint (Multi-Camera Place Experience v2):**
5106 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (26m48s). Both failures are the identical, already-documented
pre-existing `test_place_biodiversity_summary_repository.py` pair
(`'seen_before' == 'new'` assertion mismatch) below, re-confirmed this
session. A first full Core run this session (5103 passed / 5 failed)
surfaced 3 genuinely new failures beyond that pre-existing pair, all
traced to the same root cause -- this milestone's own first attempt at
its archived-camera-history fix had made `place_activity_report`'s
*unfiltered default* archived-inclusive too, contradicting a real,
pre-existing, deliberately-authored test from the already-accepted
"Gate C -- Meaningful Change Detection / Baseline Comparison v1" milestone
(`test_place_change_summary_repository.py::test_archived_stream_
confirmations_are_excluded` and `test_historical_baseline_repository.py`'s
own identically-named test) that this session's own narrower Tier 1
re-runs had not included in scope. Corrected precisely (the unfiltered
default stays archived-exclusive, matching Bird Log/Wildlife Insights/
Biodiversity's identical default; an explicit `source_ids` selection still
reaches archived history) and reconfirmed clean by this second, full run
-- see [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)'s
"Validation" for the complete record. No schema-version guard-rail
regression (schema unchanged, so no guard-rail assertions needed
touching). 87+ new/modified tests across the directly touched files plus
two new dedicated test files (`test_multi_camera_concurrent_runtime.py`,
`test_multi_camera_place_experience_scenario.py`), all passing; `ruff
check` confirmed zero new findings via a direct clean-baseline bisection
(`git stash push -u`/pop, content-normalized comparison) both before and
after the correction above; `tsc --noEmit`/`vite build` clean; targeted
e2e (`today-report.spec.ts` 19/19, `place-activity-report.spec.ts` 3/3,
`bird-log-historical-status.spec.ts` 9/9) passing; full existing e2e suite
(128 tests) re-run at 127 passed / 1 failed, that one failure the
identical, already-independently-documented pre-existing
`reviewed-product-loop.spec.ts` gap recorded across at least three prior
milestones' own acceptance records, including `mobile-viewport-audit.
spec.ts`'s own full clean re-run (zero horizontal-overflow findings)
across exactly the surfaces this milestone modified.

**Prior accepted Core checkpoint (Ecological Interoperability & Submission
Workflows v1):** 5095 passed / 2 failed / 3 skipped / 23 deselected
(slow-marked) / 11 xfailed (27m29s). Both failures are the identical
`test_place_biodiversity_summary_repository.py` pair (`'seen_before' ==
'new'` assertion mismatch) independently re-confirmed as pre-existing
across at least eight consecutive prior milestone checkpoints below --
re-run in isolation this session and reproduced byte-identically (same two
test names, same exact assertion values), confirming the established
precedent rather than a full `git stash` bisection for code sharing zero
files or logic with this milestone. No schema-version guard-rail
regression: all 14 hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 56`
assertions across 7 files were found and bumped to `57` (the identical
class of drift every prior schema bump has tripped -- see the milestone
report). 98 new tests across eight new test files plus targeted additions
to three existing ones, all passing; `ruff check` confirmed zero new
findings via a direct line-level diff against a clean baseline (stronger
than a bisection -- every pre-existing finding reproduces byte-identically
at its new, shifted line number; an over-broad `ruff --fix` run was caught
removing ~19 unrelated pre-existing unused imports and precisely reverted
first); `tsc --noEmit`/`vite build` clean; new `ecological-destinations.
spec.ts` 5/5 passing; full existing e2e suite (127 tests) re-run with only
the one already-known pre-existing failure (`reviewed-product-loop.
spec.ts`, unrelated to this milestone, recorded across at least three
prior milestones).

**Prior accepted Core checkpoint (Calm Attention & Notifications v1):** 4991
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m02s). All 3 failures independently re-bisected this session: the two
`test_place_biodiversity_summary_repository.py` failures (identical
`'seen_before' == 'new'` mismatch, see immediately below) reproduce
byte-identically against a fresh `git stash push -u` clean-baseline run with
zero of this milestone's changes applied. The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success` -- the identical test name
already recorded as a load-induced flake in the Mobile & Remote Experience v1
checkpoint below -- passed cleanly both in isolation and as part of its own
file (7/7) when re-run directly on this milestone's own code immediately
after the full Core run, confirming the flake again rather than assuming the
precedent still held. No schema-version guard-rail regression: all 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 55` assertions across 7 files
were found and bumped to `56` (the identical class of drift every prior
schema bump has tripped -- see the milestone report). 22 new tests across two
new files (`tests/test_calm_attention.py`, `tests/test_attention_sync_
service.py`) plus one new schema-migration regression test in `tests/
test_persistence.py`, all passing; `ruff check` clean (0 new findings,
bisected file-by-file against a clean baseline); `tsc --noEmit`/`vite build`
clean; 11/11 new `notification-preferences.spec.ts` e2e tests passing
(4 of which install a fake `Notification` global and a fake clock to prove
the live-notification decision logic end to end, not only that Settings
persists a toggle); full existing e2e suite (118 tests) re-run with only the
one already-known pre-existing failure (`reviewed-product-loop.spec.ts`,
independently reproduced and unrelated to this milestone).

**Prior accepted Core checkpoint (Mobile & Remote Experience v1):** 4976
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(24m02s -- measurably longer than the historical ~9min baseline; this
sandbox was independently confirmed under real, unrelated concurrent CPU
load throughout this session via `uptime`/`ps`, not a Core-gate
regression). Two failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean pre-milestone baseline (byte-identical
failure, same `'seen_before' == 'new'` assertion mismatch, with zero of
this milestone's changes applied). The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success`, has zero code relationship
to this milestone (Camera Node transport/protocol diagnostics), passed
7/7 cleanly on immediate isolated re-run, and matches an already-
documented precedent for exactly this file under exactly this condition
(the Environmental Context v2 checkpoint below recorded a different test
in this same file failing only under confirmed heavy concurrent load,
clean in isolation) -- the identical evidentiary shape, not bisected via
`git stash` a second time given that precedent and the isolation proof
already in hand. No schema change, so no guard-rail
assertions needed touching. 138 tests pass across the six directly
touched/added test files (20 genuinely new -- 2 for the Phase 0 RED/GREEN
proof, 5 for the new timing-guard parameters, 9 for the new
`/api/product/connection` endpoint, 4 for CORS -- plus 2 pre-existing
tests corrected to match the fixed behavior, their own actual claims
unaffected); `ruff check` clean
(0 new findings; the 57 pre-existing findings elsewhere in
`product_repository.py` confirmed unrelated via `git stash` bisection);
`tsc --noEmit`/`vite build` clean. Frontend e2e: new
`mobile-viewport-audit.spec.ts` 19/19 passing (10 core surfaces at
phone-viewport emulation, real seeded/imported data, zero horizontal-
overflow findings, plus a 360px/390px/768px matrix on the two densest
surfaces per Phase 25); full existing suite (112 tests, no filter) re-run
in full -- 111 passed, 1 failed, and that one failure
(`reviewed-product-loop.spec.ts`) is an independently-
reproduced, genuinely pre-existing defect (unmodified spec, run alone,
fails identically -- a `ReviewQueuePage` `product_category`/"animals"-tab
data gap, unrelated to this milestone's own changes) -- zero regressions
from the navigation/CSS changes across every other spec, including two
pre-existing mobile-specific tests.

**Prior accepted Core checkpoint (Place Story & Seasonal Timeline v1):**
4958 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (22m29s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean `950d5c2` baseline (byte-identical failure,
same `'seen_before' == 'new'` assertion mismatch, with zero of this
milestone's changes applied; `git worktree` gives invalid baselines in
this actively-shared worktree, so `git stash push -u`/`pop` was used
instead, then dropped after a diff-against-stash confirmed zero content
loss). No schema change, so no guard-rail assertions needed touching. 32
new tests (24 pure `tests/test_place_story.py` + 8 repository/HTTP
`tests/test_place_story_repository.py`); `tsc --noEmit`/`vite build`
clean; 44/44 targeted e2e passed (6 new `place-story.spec.ts` + 38
directly-adjacent re-run clean).

**Prior accepted Core checkpoint (Place Features & Habitat Change v2):**
4926 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (23m27s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash` bisection
against the clean `b0bd312` baseline (byte-identical failures with zero
of this milestone's changes applied). 50 new tests in
`tests/test_place_feature.py`
(pure window-selection/maturity logic, repository CRUD, dual-write
reconciliation, real seeded before/after scenarios, real HTTP surface),
plus a new `test_persistence.py` schema-55 migration test and 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 54` guard-rail assertions
across 8 unrelated files bumped to `55` (the same class of drift the
prior two schema bumps also tripped -- see the milestone report). 30
directly-adjacent existing tests re-run clean
(`test_habitat_phenology.py`/`test_habitat_association.py`/
`test_place_activity_report.py`/
`test_place_activity_report_repository.py`/`test_source_activity.py`
actually total 174; the 30 figure is the re-run e2e count, see below).
Frontend `tsc --noEmit` and `vite build` clean; a new 7-test Playwright
spec (`e2e/place-features.spec.ts`) plus 30 directly-adjacent existing
e2e tests (`today-report`/`place-activity-report`/`biodiversity-summary`)
re-run clean.

**Prior accepted Core checkpoint (Environmental Context v2):** 4874
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(26m13s). Two of the three failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below.
The third (`test_transport_worker.py::test_retryable_failure_returns_
item_to_failed_retryable_and_eventually_succeeds`) is unrelated to this
milestone (a different subsystem entirely, no shared code), reproduced
only under confirmed heavy concurrent system load, and passed cleanly
both in isolation and as part of its own file when re-run -- a transient,
load-induced flake, not a regression; see the milestone report's "Tests /
validation" for the full isolation evidence. 85 new tests across three new
pure modules plus repository/schema extensions (zero bugs found in the
three new pure modules themselves; three real bugs found and fixed in the
new repository-layer integration code during this milestone's own
test-writing); 42/42 targeted Playwright e2e tests passed. A first full
run also surfaced 10 additional failures, root-caused immediately to 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 53` guard-rail assertions
across 7 files unrelated to this milestone that its own correct v53->v54
schema bump was always going to trip -- fixed by updating all 14 to `54`
(not a defect in this milestone's own migration; see the report).

**Prior accepted Core checkpoint (Place / Yard Intelligence v2):** 4791
passed / 2 failed / 2 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m23s). The 2 failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
re-confirmed via a fresh `git stash` bisection against the clean `731ee30`
baseline this same session. 173 new pure-module tests added (all passing,
zero bugs found in the modules under test); 46/46 targeted Playwright e2e
tests passed after fixing one real regression found live (a pre-existing
mock fixture predating a new additive response field -- see the milestone
report).

**Prior accepted Core checkpoint (Camera / Source Experience &
First-Hour Setup Closure v1):** 4648 passed / 2 failed / 2 skipped / 11
xfailed. The 2 failures
(`test_place_biodiversity_summary_repository.py`, an unrelated
historical-status timing case) reproduced identically against the clean
`74c192a` baseline via `git stash` bisection -- confirmed pre-existing
flakiness, not a regression.

**Prior accepted Core checkpoint (Release Engineering Foundation v1):**
4633 passed / 0 failed / 0 errors. (A first full run showed 2 teardown
errors in an unrelated file; root-caused via clean-baseline bisection to
a pytest fixture-teardown-ordering interaction this milestone's own
`tests/conftest.py` change triggered, fixed at the source -- see the
milestone report's "Validation commands/results.")

**Prior accepted Core checkpoint (Acoustic milestone):** 4608 passed / 0
failed.

**Prior accepted Full checkpoint:** 4629 passed / 2 failed. Both failures
were in unrelated Camera Node real-subprocess tests and reproduced
identically on the clean baseline.

These counts are historical accepted checkpoints, not immutable future
expected totals.

## 15. Update protocol

At each accepted milestone closure, update only the delta:

- accepted HEAD;
- schema if changed;
- latest accepted milestone;
- affected lane status;
- newly discovered blocker;
- current validation checkpoint if applicable;
- field acceptance state;
- current authorized milestone only when explicitly authorized after
  global reconciliation.

Never copy a Claude "next natural milestone" suggestion directly into the
authorization field.

## 16. Transition checkpoint

**Staleness correction, 2026-09-07, by Global Product & Release
Readiness Reconciliation v2** (see
[global-product-release-readiness-reconciliation-v2-report.md](global-product-release-readiness-reconciliation-v2-report.md)):
everything below in this section is dated to the 2026-08-26 Multi-Camera
Place Experience v2 checkpoint and was never updated through the
roughly twenty milestones accepted since -- treat it as historical
narrative, not current state. **Current facts, verified directly
2026-09-07:** Accepted HEAD `5e36989` ("Place Feature Comparison &
Habitat Outcomes v1: report correction"); schema `v59` (v58 -> v59 via
Multi-Camera Place Feature Linking & Cross-View Habitat Context v1's
`place_feature_observation_links` table); Lane P `CLOSED` -- a real
`LICENSE` file (MIT) exists, contradicting this section's own "LICENSE:
still genuinely absent" line below; Lane R unchanged at `OPEN --
RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`; current
authorized implementation milestone remains `NONE` (the "GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED" qualifier below is itself
stale -- that reconciliation, and a second one, have both since run; see
`## CURRENT PHASE`, above, and the v2 report for the complete current
picture). See §§1, 4-6, and 14, above, for the sections of this document
that were kept current through each intervening milestone's own
reconciliation commit. The stacked history below is preserved unedited,
consistent with this document's own convention of correcting forward
rather than rewriting accepted history in place.

- **Accepted HEAD:** `763fe22` (Multi-Camera Place Experience v2
  implementation commit)
- **Schema:** v57 -> v57, unchanged. Every fix is a query-scope correction
  or an additive field on an already-derived, never-persisted response
  object -- no new/changed table.
- **Latest accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views
- **Multi-Camera Place Experience v2 classification:** B -- an integrated
  multi-camera product pass on the already-accepted Camera/Source +
  Multi-Camera Maturity v1 foundation (cross-camera association engine,
  Area vocabulary, provider compatibility, health WAN-vs-camera
  disambiguation -- that milestone's own report had gone missing from this
  file's own bookkeeping despite being a real, merged, accepted ancestor
  of this HEAD; corrected here, see Lane F, above). See
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
  for the full record: a real correctness defect (an archived camera's
  history was unreachable from every discovery surface, contradicting this
  codebase's own documented archive-only-preserves-history doctrine) found
  and fixed with principled nuance across two rounds of correction --
  Tier 1 test evidence first corrected an initial blanket overcorrection,
  then this milestone's own full Tier 3 Core run caught a second, more
  subtle one (`place_activity_report`'s unfiltered default had also become
  archived-inclusive, contradicting a real pre-existing test from the
  already-accepted "Gate C -- Meaningful Change Detection / Baseline
  Comparison v1" milestone -- see §14); the fix that shipped preserves
  every already-tested current-active-observatory default exactly (Bird
  Log overview, Wildlife Insights, Biodiversity, Place Activity
  Report/Today) while making that real history reachable by explicit
  camera/`source_ids` selection, with Place Story and research/
  conservation export unconditionally inclusive where no existing test
  disagreed; Today now surfaces its own already-computed per-camera
  activity/evidence-source facts for the first time (a compact "By camera"
  section and per-highlight camera attribution, both gated to 2+ cameras
  so Today stays a report, never a camera-monitoring dashboard); Bird
  Log's camera filter now reaches its overview list, not only the
  per-species drilldown; Zone Insights' Place-wide aggregate coverage was
  a naive per-camera-hours sum, now a real elapsed-time interval union
  matching Today's own already-correct semantics (proven with real
  before/after numbers: 2 hours + 2 hours overlapping by 1 hour now
  correctly reports 3, not 4); Dashboard distinguishes "some cameras need
  attention" from "every armed camera needs attention," computed from
  already-returned facts; `CameraConfigurationPage.tsx`'s own locally-
  drifted 3-tone health-tone/generic-label presentation now reuses the
  canonical `cameraHealthTone`/`cameraHealthLabel` every other health
  surface already converged on; a real, measured (not merely claimed)
  concurrency proof -- genuine concurrent `threading.Thread`s, one per
  Stream, each with its own `ProductRepository`/connection against one
  shared SQLite file, matching production's actual architecture -- found
  zero cross-Stream contamination and no starvation across 2-camera and
  4-camera-asymmetric topologies, and separately found, root-caused, and
  honestly disclosed (an attempted bounded transient-retry fix did not
  reliably close the gap and was deliberately reverted rather than shipped
  unproven on Stage 7's own live admission/persistence boundary) a real,
  reproducible occasional lost-candidate-Visit reliability gap under real
  concurrent write contention; a comprehensive, real, executable 3-camera
  product-shaped scenario (Front Feeder/Back Yard/Bird Bath, a real
  cross-camera "associated" pair, an archival, a rename, a reviewed
  correction) proves the whole chain -- identity, coverage, overlap dedup,
  health, correction propagation -- coheres end to end with zero mocking
  of product logic. Full Core 5106 passed / 2 failed (both the identical,
  independently-reconfirmed pre-existing `test_place_biodiversity_summary_
  repository.py` pair -- see §14) / 3 skipped / 23 deselected / 11 xfailed
  (26m48s); `ruff check`/`tsc --noEmit`/`vite build` clean; full existing
  e2e suite (128 tests) at 127 passed / 1 failed (the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap). Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": the occasional
  lost-candidate-Visit concurrent-write reliability gap (the single most
  concrete, actionable follow-on item); notification-level (Calm
  Attention) cross-camera grouping beyond the Dashboard status-view fix;
  Place Story wildlife-event source attribution; camera-filter UI
  consolidation (6+ independently-implemented controls); multi-camera
  Place Feature linking; real GPU/CUDA-driver-level concurrent-inference
  measurement (needs real hardware this sandbox lacks); a multi-hour
  concurrent soak; the pre-existing, disclosed 2-Stream cap on the
  separate legacy motion pipeline (RTSP/USB/local providers, not the
  modern Observation Engine's own Camera Node path).
- **Prior accepted HEAD:** `3c60d79` (Ecological
  Interoperability & Submission Workflows v1 implementation commit --
  filled in at reconciliation)
- **Schema:** v56 -> v57. Two new additive tables:
  `ecological_taxonomy_mappings` (a bounded, reusable "MockingBird label ->
  destination taxon" resolution cache, one row per `(destination, label)`)
  and `ecological_submission_records` (a durable per-Visit
  external-submission-preparation record, one mutable row per `(visit_id,
  destination)` until a self-reported external result freezes it). No
  existing table's shape changed.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology
- **Ecological Interoperability & Submission Workflows v1 classification:**
  B -- a real, working, submission-ready iNaturalist workflow composed
  entirely over the already-accepted research-eligibility gate and
  `ResearchObservation` shape (`mockingbird.ecological.destination_
  eligibility`/`adapters` never re-derive either), never a second truth
  system. See
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)
  for the full record: eligibility preview with per-record, never-bare
  status and reasons; a credential-free iNaturalist taxonomy mapping cache
  (`GET /v1/taxa`, confirmed public/no-auth against the official swagger
  spec) whose exact-name-match logic was directly corrected against a real
  live API call during this milestone's own testing (a plain "Northern
  Cardinal" query returns several candidates, not one -- requiring an exact
  match among them, not a bare single-result rule); explicit, never-
  inferred-from-the-weather-coordinate location/media consent (directly
  tested); a batch prepare/export pipeline producing the exact positional
  8-column CSV iNaturalist's own open-source bulk importer expects
  (confirmed directly against `lib/bulk_observation_file.rb`); deterministic
  content fingerprinting closing idempotency and correction-after-
  preparation staleness (a real precedence bug -- a stale-and-currently-
  ineligible record reported the less useful reason first -- found and
  fixed by this milestone's own test-writing); a self-reported external-
  result close-the-loop step, never a live automated submit; a bounded,
  additive Darwin Core Occurrence-core exporter
  (`basisOfRecord="MachineObservation"`, GBIF's own recommended camera-trap
  value, confirmed via its official camera-trap guide); eBird correctly,
  evidence-backed **not offered** (its own current "Rules and Best
  Practices," checked 2026-08-25, explicitly excludes feeder/trail-camera
  data -- a real policy conflict, not a time constraint, and the product UI
  now shows this reason persistently rather than behind a disabled
  button's hover-only tooltip, a real gap this milestone's own e2e testing
  found and fixed); direct GBIF publication correctly deferred as
  institutional (organizational Participant-Node endorsement required, not
  a backyard-user workflow); two real security findings made and fixed
  (CSV injection in the one shared `_write_csv` helper behind every export
  in this codebase, retroactively hardening the pre-existing generic
  research/Camtrap DP export paths too -- and a real regression in an
  early version of that exact fix, which corrupted legitimate negative
  coordinates, caught by this milestone's own test before shipping; a
  `javascript:`-scheme external-URL rejection on the self-reported result
  field); a real, executable 12-Visit product-shaped scenario test proving
  the whole workflow end to end with zero user interaction and zero
  provisional/superseded truth ever reaching a prepared record. 107+ new
  tests across nine new test files plus targeted additions to three
  existing ones, all passing; `ruff check` confirmed zero new findings via
  a direct line-level diff against a clean baseline (not merely a
  bisection) -- an over-broad `ruff --fix` run was caught removing ~19
  unrelated pre-existing unused imports and precisely reverted before that
  confirmation; `tsc --noEmit`/`vite build` clean; new
  `ecological-destinations.spec.ts` 4/4 passing; full existing e2e suite
  re-run at 126 passed / 1 failed, that one failure the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap recorded across at least three prior milestones' own
  acceptance records. Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": live OAuth iNaturalist
  submission; media-byte inclusion; a single-Visit deep-link pre-selection
  on the Ecological Destinations page; broader batch-filter UI depth.
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Prior accepted HEAD:** `c22bf94` (Calm Attention &
  Notifications v1 implementation commit -- filled in at reconciliation)
- **Schema:** v55 -> v56. One new additive table, `user_notification_
  preferences` (per-user delivery preferences). No existing table's shape
  changed; `ProductAlertModel.category`/`.action_type` are plain `String`
  columns with no database-level enum/check constraint, so the new
  `"insight"` category and the two new `open_place_story`/`open_place_report`
  action types needed no migration of their own.
- **Latest accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Calm Attention & Notifications v1 classification:** B -- a real canonical
  attention-selection layer (`ProductRepository.sync_attention_signals`)
  composed entirely over already-accepted facts (Place Story's already-
  deduplicated event stream, the existing daily/weekly digest, the existing
  review/monitoring/storage/journal `ProductAlert` system), never a second
  computation path. See
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)
  for the full record: a small user-centered taxonomy (Discovery/Insight/
  Needs Help/Observatory Health) and explicit urgency (immediate/digest/
  in-app-only) computed as a pure presentation-layer mapping, never stored
  and never a raw internal severity/error vocabulary leaking into copy;
  genuine semantic-deduplication work that found and fixed two real
  double-notification anti-patterns by *writing tests*, not merely by
  design review (`first_seen` excluded from the new sync because `_sync_
  journal_milestone_alert` already owns that fact; the 1st-species
  diversity milestone excluded too, since it is always dated at that same
  taxon's own first-ever confirmation); reused, not reinvented, health/
  storage debounce (`_sync_camera_health_incident`'s own already-debounced
  named-duration/consecutive-failure thresholds, untouched); a daily/weekly
  digest notification reusing `daily_digest.compute_daily_digest` unmodified
  via the exact same `place_activity_report` entry point Today/the Place
  Report already call, suppressed when there is genuinely nothing meaningful
  and never suppressed for an ordinary day of confirmed regular activity;
  Needs Help reclassified to `in_app_only` urgency and grouped into the
  digest's own "N observations could use your help" sentence instead of a
  second per-item interruption; new per-user notification preferences (this
  product's first per-user settings row -- four category toggles + quiet
  hours) with quiet hours deliberately evaluated in the viewer's own
  browser-local time rather than inventing a server/Place timezone that does
  not exist; a fixed role rule hiding Needs Help attention from Viewers
  server-side, not merely in the UI; foreground-only browser-notification
  delivery (Phase 22 Decision B, Web Push explicitly evaluated against real
  architecture facts and deferred -- no VAPID/subscription persistence, no
  outbound push-service call, no cloud infrastructure added, matching this
  lane's own standing "do not add cloud push infrastructure" instruction);
  a real, executable Monday-through-Sunday product-shaped quiet-week test
  proving the whole week stays calm (<=14 total attention items, zero ever
  reaching `immediate` urgency); a real controlled-checkbox revert bug found
  and fixed in the new Notifications settings UI by a failing Playwright
  assertion; 4 new e2e tests that install a fake `Notification` global and a
  fake clock to prove the live-notification decision logic end to end, not
  only that Settings persists a toggle. 22 new backend tests (`tests/
  test_calm_attention.py` + `tests/test_attention_sync_service.py`) plus one
  new schema-migration regression test, all passing; Core 4991 passed / 3
  failed (all 3 independently re-bisected this session -- 2 byte-identical
  pre-existing via fresh `git stash push -u`, 1 a load-induced flake
  reconfirmed clean in isolation and matching an identical documented
  precedent -- see §14) / 3 skipped / 11 xfailed; `ruff check`/`tsc --noEmit`/
  `vite build` clean; 11/11 new e2e tests passed; full existing e2e suite
  (118 tests) re-run with only the one already-known pre-existing failure
  (`reviewed-product-loop.spec.ts`, unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's "Remaining
  major PRODUCT opportunities": Web Push for a genuinely closed-browser
  interruption (deliberately deferred, not merely unattempted); detector/
  model-unavailable Observatory Health attention; per-user (not global)
  read/dismiss state; precise per-taxon/Feature Place Story deep links
  (today scoped to a category group); a live attention-sync diagnostics
  surface beyond the current structured log line.
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk
- **Mobile & Remote Experience v1 classification:** B -- strong mobile
  experience and a clear secure remote posture with bounded external-
  network/PWA gaps. See
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)
  for the full record: a verified responsive-navigation fix (top bar +
  off-canvas drawer + 4-item bottom nav, replacing a sidebar that
  previously stacked in full above every page below 980px, proven across
  10 real automated phone-width screenshots with zero horizontal-overflow
  findings); a bounded, from-scratch installable PWA shell (manifest,
  icons generated from the product's own existing brand mark, a service
  worker that caches only Vite's own immutable content-hashed assets and
  never navigation/API/data -- no offline data claim anywhere); LAN access
  made genuinely discoverable (`GET /api/product/connection`, a Settings
  "Connection & Remote Access" card, a corrected `--allow-network` help
  string that had gone stale since real authentication shipped); a
  private-overlay-network (Tailscale-compatible) remote-access posture
  investigated against real architecture and documented as the supported
  away-from-home path, with direct public-internet exposure and a cloud
  relay explicitly, plainly documented as unsupported/not-built; 4 new
  CORS regression tests closing a real, previously-zero coverage gap. Also
  closed, as its own bounded Phase 0 ahead of the broader mobile work: a
  genuine pre-existing defect in `place_change_summary._presence_status`
  that made the accepted `regularity_narrative` "returned after absence"
  wording structurally unreachable through Today/Bird Log's direct
  composition -- fixed at the source (not merely worked around a second
  time), including a second, deeper defect the naive fix alone would have
  introduced (a young-taxon false positive), closed by sharing one timing
  guard between Today/Bird Log and Place Story instead of duplicating it.
  138 tests pass across the six directly touched/added test files (20
  genuinely new, 2 pre-existing corrected -- see §14), Core 4976 passed /
  3 failed (2 pre-existing and re-confirmed via fresh `git stash push -u`
  bisection, 1 a load-induced flake in an unrelated file matching an
  already-documented precedent, isolation-confirmed clean -- see §14) /
  3 skipped / 11 xfailed; frontend `tsc`/`vite build` clean;
  19/19 new mobile-viewport e2e tests passed (10 core surfaces +
  360px/390px/768px matrix); full existing e2e suite
  (112 tests) re-run with only the one already-
  known pre-existing failure (`reviewed-product-loop.spec.ts`, a
  `ReviewQueuePage` `product_category` gap, independently reproduced and
  unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's
  "Remaining major PRODUCT opportunities": Visit/Stream/Settings page
  density (long but not broken), the `ReviewQueuePage` `product_category`
  gap itself (found, documented, not fixed), no login rate-limiting
  (pre-existing, real, more relevant now that reachability increased), and
  no live external-overlay-network acceptance was possible from this
  sandbox (validated structurally only).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place
- **Place Story & Seasonal Timeline v1 classification:** B -- major
  useful capability, bounded history/story gaps. New `GET /api/place/
  story` composes a small, deliberately bounded event taxonomy --
  wildlife (`first_seen`/`return`/`regularity_change`/
  `noteworthy_activity`/`diversity_milestone`), place
  (`feature_change`/`phenology`), context (`comparison_insight`) --
  entirely from already-accepted primitives (`historical_baseline`,
  `place_change_summary`, `regularity_narrative`,
  `PlaceFeatureChangeEventModel`, `PlacePhenologyObservationModel`,
  `feature_change_comparison`); regularity/activity-change detection
  re-applies those unmodified functions at every usable-date checkpoint
  so a transition is announced once, not once per recomputation. Found
  and worked around without modifying the frozen module: `place_change_
  summary._presence_status` has made the existing `"returned_after_
  absence"` wording unreachable in production on Today/Bird Log since
  Place / Yard Intelligence v2 shipped -- `place_story._effective_
  regularity_state` applies a narrow local supplemental check using that
  module's own already-correct fields; a dedicated fix to `place_change_
  summary.py` itself is recorded as future work, not applied here. New
  `PlaceStoryPage.tsx`: a calm, newest-first, month-grouped timeline with
  Period/Category filters and evidence drill-down. 24 pure-module tests
  (including regression tests for the gap above and a second, separately
  found and fixed checkpoint-seeding bug), 8 repository/HTTP integration
  tests against real seeded data (including three independent
  correction-safety proofs), all passing; Core 4958 passed / 2 failed
  (both pre-existing, re-confirmed via fresh `git stash push -u`
  bisection -- see §14) / 3 skipped / 11 xfailed; 44/44 targeted e2e
  passed (6 new + 38 directly-adjacent re-run). See
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
  for the full record, including recorded future opportunities (period
  summaries -- deferred on a measured performance cost, the single
  largest deferred piece --, environmental-context/weather caveats on a
  Story insight, a dedicated taxon/Feature story page, representative
  imagery on Story cards, and the `place_change_summary.py` fix itself)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding
- **Place Features & Habitat Change v2 classification:** B -- major
  useful capability, bounded feature/data-model maturity gaps. A durable
  `PlaceFeatureModel` (feeder/water/nest_box/vegetation_patch/structure/
  habitat_area/other, optionally camera/Zone-linked) and a Reviewed
  `PlaceFeatureChangeEventModel` timeline (added/removed/moved/modified/
  replenished/food_changed/vegetation_changed/other), a deliberate
  dual-write (not event-sourced) relationship between the two -- the
  first discrete before/after change-event model in this codebase,
  closing a gap `habitat_association.py`'s own docstring and the Place /
  Yard Intelligence v2 report both explicitly recorded as their own
  honest ceiling. A new before/after comparison module composes onto
  `conditional_association.compute_conditional_association` completely
  unmodified (proven byte-identical output to calling that primitive
  directly), adding only a bounded 7/14/30-day symmetric window
  escalation and a four-state maturity vocabulary (too_soon/insufficient_
  coverage/early_signal/comparable); a per-Feature yield module mirrors
  `source_activity.py` one level finer. Both new tables are PATCH-
  corrected in place because every derived comparison is computed fresh
  at read time, never cached -- proven, not just asserted, by a direct
  test that a correction changes the very next read. New Dashboard card
  and Place Report section, both mirroring existing Habitat & Phenology
  UI patterns exactly. 50 new backend tests, 7 new Playwright e2e tests,
  all passing; Core 4926 passed / 2 failed (both pre-existing, re-
  confirmed via fresh `git stash` bisection -- see §14) / 3 skipped / 11
  xfailed; 37/37 targeted e2e passed (7 new + 30 directly-adjacent
  re-run). See
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)
  for the full record, including recorded future opportunities
  (environmental-context/weather caveats on a before/after result --
  the single largest deliberately-deferred piece --, multi-camera
  Feature linking, representative evidence in Feature detail, a ranked
  feature-comparison view, deeper Today/`daily_digest` integration)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Environmental Context v2 -- Weather,
  Climate & Place Conditions
- **Environmental Context v2 classification:** B -- major useful
  capability, bounded provider/statistical/UI limitations. First general
  weather provider (Open-Meteo -- free, non-commercial, no API key,
  global coverage, CC BY 4.0 attributed) composed onto the existing
  `conditional_association` primitive alongside `habitat_associations`;
  two independent privacy opt-ins (coordinates for solar, a separate
  `weather_enabled` for any outbound network call); a bounded 92-day
  historical window (exceeds this product's entire real history today);
  six honest degraded-mode states, zero crashes, zero blocking of core
  product function. 85 new tests; Core 4874 passed / 3 failed (2
  pre-existing, 1 confirmed transient load-induced flake in an unrelated
  subsystem) / 3 skipped / 11 xfailed; 42/42 targeted e2e passed. See
  [environmental-context-v2-report.md](environmental-context-v2-report.md)
  for the full record, including the Open-Meteo terms/license research
  and recorded future opportunities (deeper historical backfill via the
  archive/ERA5 endpoint, wind/cloud-cover statistical associations, a
  dedicated diagnostics/Explore-page surface) deliberately not built by
  adjacency.
- **Camera / Source Experience release classification:** C -- usable,
  bounded further closure remains (ongoing-monitoring failure-code
  collapse; no real reachable camera/RTSP/ONVIF/local-USB/Camera-Node
  hardware exercised this session). See
  [camera-source-experience-v1-report.md](camera-source-experience-v1-report.md).
- **Native-Windows acceptance (this milestone):** none -- Ecological
  Interoperability & Submission Workflows v1 was validated via targeted
  and full Core Python tests, new Playwright e2e, `tsc`/`vite build`, and
  `ruff` on the Linux/WSL dev stack, plus a real live call to iNaturalist's
  own public taxonomy API during development (not a Windows-specific
  proof, but real external-network evidence). Every new module is plain
  Python/TypeScript with no OS-specific branch (the one external HTTP call
  uses the same stdlib `urllib.request` convention the existing weather
  provider already validated cross-platform), so it is not expected to
  behave differently on native Windows, but that remains an expectation,
  not fresh Windows evidence. The most recent real native-Windows
  acceptance remains further below (Place / Yard Intelligence v2),
  unaffected by this milestone's additive-only schema change.
- **Native-Windows acceptance (Calm Attention & Notifications v1):** none --
  validated via targeted Python tests (including a real 28-minute Core
  run), new Playwright e2e (including 4 real-browser `Notification`/
  fake-clock tests), `tsc`/`vite build`, and `ruff` on the Linux/WSL dev
  stack; every new module is plain Python/TypeScript with no OS-specific
  branch, so it is not expected to behave differently on native Windows,
  but that remains an expectation, not fresh Windows evidence.
- **Native-Windows acceptance (Place Story & Seasonal Timeline v1):** none
  -- Place Story &
  Seasonal Timeline v1 was validated via targeted Playwright e2e against
  the real running app (Linux/WSL dev stack) and full Core; it is a pure
  read-model over already-cross-platform data with no platform-specific
  code and is not expected to behave differently on native Windows, but
  that is an expectation, not fresh Windows evidence. The most recent
  real native-Windows acceptance remains the one below (Place / Yard
  Intelligence v2), unaffected by this milestone's schema-unchanged,
  additive-only change.
- **Native-Windows acceptance (Place Features & Habitat Change v2):**
  none -- validated the same way (targeted Playwright e2e + full Core on
  Linux/WSL), for the identical reason (no platform-specific code).
- **Native-Windows acceptance (Place / Yard Intelligence v2):** real
  deployment of the exact commit (confirmed via `/api/product/instance`),
  plus a second, genuinely fresh isolated instance exercised end-to-end
  (real administrator creation, real sign-in, real ffmpeg 8.1.2 subprocess
  against an intentionally unreachable RTSP host, honest
  `preview_available`, correct credential masking, no leak) -- not a
  full physical-camera acceptance; see that report's Section 6/9.
- **Prior Native-Windows acceptance (Release Engineering Foundation v1):**
  Decision A -- real deployment, a real packaging defect found and fixed,
  a real organic 18-schema-version migration with verified automatic
  backup, confirmed via real HTTP. See
  [release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md).
- **Weather provider decision:** Open-Meteo (`api.open-meteo.com`), free/
  non-commercial/no-API-key, CC BY 4.0 attributed, bounded to its own
  confirmed 92-day recent-history window. Off by default
  (`weather_enabled=False`); a second, independent opt-in from the
  existing coarse-coordinate setting. See the Environmental Context v2
  report's "Provider decision" for the full terms/license research and
  the preserved, unresolved commercial-adjacent-use caveat (mirroring the
  standing BirdNET caveat in §2, above).
- **Acoustic release posture:** Release-ready optional
- **Production detector:** MDv5a ONNX @ 0.1
- **Production visual species system:** BioCLIP-2 + Eligibility/Abstention
- **Current authorized implementation milestone:** NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED
- **State:** Milestone-closure checkpoint
- **Final release hardening:** not authorized
- **Remote LTE/solar:** not a release blocker
- **Ecological Interoperability:** delivered this milestone (classification
  B) -- see Lane J, §6; live OAuth iNaturalist submission, any eBird
  workflow, direct GBIF publication, media-byte inclusion, and a
  single-Visit deep-link pre-selection are not automatically authorized
  (see §3)
- **Ecological destination decisions:** eBird -- not offered (own current
  policy excludes feeder/trail-camera data); iNaturalist -- submission-ready
  CSV workflow delivered, live OAuth submit deliberately not built; Darwin
  Core -- built, additive to Camtrap DP; GBIF -- deferred, institutional
- **Darwin Core export:** delivered this milestone, additive to the
  already-accepted Camtrap DP export (not a replacement) -- see Lane
  "Research / Conservation," §5
- **Calm Notifications:** delivered this milestone (classification B) -- see
  Lane D, §6; a further Web Push/per-user-read-state/precise-deep-link
  campaign is not automatically authorized (see §3)
- **Calm attention capability:** B -- one canonical attention-selection
  layer over already-accepted facts, genuine semantic-dedup fixes found by
  tests, reused health/storage debounce, per-user preferences and quiet
  hours, foreground-only browser notifications with Web Push deliberately
  deferred, a real product-shaped quiet-week proof
- **Notification delivery decision:** foreground-only page-level
  `Notification` calls while the tab is open or backgrounded (Phase 22
  Decision B); no Web Push, no VAPID/subscription persistence, no outbound
  push-service call, no MockingBird-operated cloud notification backend --
  see the milestone report's "PWA / browser notification decision" for the
  full evaluation of all three options against real codebase facts
- **Mobile/PWA:** delivered this milestone (classification B) -- see Lane
  E, §6; a further Mobile/PWA/remote-access campaign is not automatically
  authorized (see §3)
- **Mobile experience capability:** B -- responsive navigation verified
  overflow-free across 10 real phone-width screenshots; dense secondary
  pages (Visit/Stream/Settings) remain long but not broken
- **Remote-access support posture:** private overlay network
  (Tailscale-compatible) is the documented, supported away-from-home
  path; direct public-internet exposure and a MockingBird-operated cloud
  relay are explicitly unsupported/not-built; LAN access via
  `--allow-network` is now discoverable in-product
- **Security implications (this milestone):** 4 new CORS regression
  tests closing a previously-zero coverage gap; new
  `GET /api/product/connection` deliberately kept authenticated (not
  public); media/evidence routes re-confirmed authenticated by policy-
  table inspection; no login rate-limiting exists (real, pre-existing,
  found and documented, not fixed -- see the milestone report)
- **Local Species Prior:** not authorized
- **Another classifier campaign:** not authorized
- **LICENSE:** still genuinely absent -- open business/legal decision, not
  resolved by this or any prior milestone (see Lane P, above)
- **Representative Field Acceptance (attempted 2026-08-25):** Gate C --
  OPEN, insufficient representative evidence; deferred by explicit user
  decision before any live session started (real-authentication/consent
  boundary, not a product defect). See Lane R and
  [representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md).
  Untracked root `uv.lock` investigated and removed per that milestone's
  own Decision A; working tree returned to exactly the seven preserved
  files then, and confirmed still exactly those seven, untouched, at this
  milestone's own start and close. An untracked `uv.lock` recurred mid-
  session during Place Features & Habitat Change v2 (an ordinary,
  never-gitignored side effect of `uv run` tool invocations in this
  actively-shared worktree, not a milestone artifact) -- removed again,
  same reasoning. It recurred a third time mid-session during Place Story
  & Seasonal Timeline v1, for the identical reason (a `git stash push -u`
  bisection re-created it) -- removed again; the working tree was
  confirmed to hold exactly the seven preserved files, untouched, at this
  milestone's own start and close, alongside this milestone's own
  committed additions. Mobile & Remote Experience v1 used `git stash
  push -u`/`pop` for its own Core-gate bisection (see §14) and confirmed,
  both before and after, that the working tree held exactly the seven
  preserved files, byte-identical to milestone start, alongside this
  milestone's own committed additions. Ecological Interoperability &
  Submission Workflows v1 confirmed the same at its own start (before any
  edit) and again at close: exactly the seven preserved files, untouched,
  alongside this milestone's own committed additions -- two peer sessions
  sharing this same working directory were confirmed idle (no file writes
  in 11+ and 105+ minutes respectively) before any write began.
  Multi-Camera Place Experience v2 confirmed the identical seven preserved
  files, untouched, at its own start, throughout (re-verified after two
  `git stash push -u`/`pop` ruff-bisection round-trips), and again at
  close alongside this milestone's own committed additions; two peer
  sessions sharing this same working directory (`mockingbird-active-65`,
  `mockingbird-active-c6`) were confirmed idle/read-only both before any
  write began and again immediately before the implementation commit
  (`git log`'s own unmoved HEAD across the full session, `763fe22`'s
  parent still `21fbc42`, was independent, objective confirmation neither
  peer had committed anything in the interim).
- **Push:** explicit authorization required
