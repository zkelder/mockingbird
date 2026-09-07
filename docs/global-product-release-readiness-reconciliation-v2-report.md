# Global Product & Release Readiness Reconciliation v2

Read-only global sequencing milestone. Zero product, test, or schema code
touched; no field session run, no deployment, no defect fixed, no model
changed, no push. The only artifacts this milestone produces are this
report and a factual-reconciliation correction to
`docs/release-execution-state.md` (see "Documentation-hygiene correction
made by this milestone," below).

**Classification legend used below** -- two different A/B/C/D schemes
appear in this repository's documents, and this report keeps them
explicitly separate to avoid the confusion a casual reader would hit:

- **This report's own required output categories** (per the governing
  brief, §2): **A** release-critical work, **B** pre-release decisions,
  **C** after-release product work, **D** later/evidence-driven/deferred
  work. Used in "Complete lane-status table" and the four work-bucket
  sections below.
- **This repository's own per-milestone acceptance rubric** (used at the
  end of every accepted milestone report, including
  [global-remaining-product-development-release-queue-reconciliation-v1-report.md](global-remaining-product-development-release-queue-reconciliation-v1-report.md)'s
  own closing `## Decision`): a single letter judging how cleanly *that
  milestone itself* closed (**A** = complete, bounded, no residual gap in
  its own scope; **B** = real accepted work with an inherent, disclosed
  limitation; ...). Used only in "Classification of this reconciliation
  milestone," at the very end, and when quoting a milestone's own stated
  classification in "Accepted delta," below.

---

## 1. Verified starting state

Verified directly against the repository this session, not assumed from
the governing brief's own text:

- **Branch:** `main`. **HEAD:** `5e36989` ("Place Feature Comparison &
  Habitat Outcomes v1: report correction", 2026-09-06 22:53:59 -0400).
  Exact match to the brief's expected HEAD, reconfirmed via
  `git rev-parse HEAD` immediately before this report was written.
- **Schema:** `CURRENT_DATABASE_SCHEMA_VERSION = 59`
  ([database.py:46](../src/mockingbird/storage/database.py)). Exact match
  to the brief's expected schema v59, independently cross-confirmed by
  every one of the five delta milestones' own schema statements (see
  §2, below).
- **Worktree:** clean except the seven preserved untracked detector files,
  which are present, untracked, and are the *entire* `git status
  --porcelain` output -- byte-for-byte identical to
  `release-execution-state.md` §13's own list
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`), confirmed both at the start and
  end of this milestone. `git diff --stat HEAD` is empty; `git stash list`
  is empty. **No active writer, nothing else dirty.**
- **Active writers:** none on `main`. No mockingbird/python/pytest/node
  process is running (`ps aux` shows only an unrelated Codex
  app-server and an unattended-upgrade daemon). Five other local git
  worktrees exist (`mockingbird-feature-replay`,
  `mockingbird-pending-feature-restore-v2`,
  `mockingbird-perception-replay-harness-v1`,
  `mockingbird-place-intelligence-reporting-v1`,
  `mockingbird-remote-transport-v1`), each on its own separate branch,
  each with a last commit between 2026-07-20 and 2026-08-22 -- stale,
  abandoned, unrelated to current work (one carries uncommitted local
  edits from 2026-07-20, orthogonal to `main`). 355 peer Claude sessions
  are visible to this session (predominantly offline "Remote Control"
  sessions recording this project's own historical milestones, plus
  several currently-interactive sessions); none shows evidence of writing
  to `main` during this reconciliation.
- **Not pushed:** `git status --porcelain=v2 --branch` reports
  `# branch.ab +365 -0` -- 365 commits ahead of `origin/main`, 0 behind.
  Matches expected.
- **Lane P:** `CLOSED -- RELEASE-CRITICAL LICENSING/DISTRIBUTION
  REQUIREMENTS COMPLETE`, confirmed directly against the working tree, not
  assumed from any report: `LICENSE` exists (MIT, added 2026-09-05, 1081
  bytes); `pyproject.toml` carries `license = "MIT"` /
  `license-files = ["LICENSE"]`; `web/package.json` carries
  `"license": "MIT"`; `README.md`'s License section
  ([README.md:462-472](../README.md)) states the resolved MIT position, no
  longer "not yet finalized." `SECURITY.md`, `CONTRIBUTING.md`, and
  `THIRD_PARTY_NOTICES.md` are all present on disk. Exact match to the
  brief's expected baseline.
- **Lane R:** `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
  REMAINS`, confirmed via `release-execution-state.md:7591-7593`, *Gate A
  True-Latency Tail Closure & Final Lane R Decision v1*, and
  *Representative Daylight True-Latency Tail Convergence v2* (the latest
  accepted document, which added zero new evidence -- see §5, below).
  Exact match to the brief's expected baseline.
- **Current authorization:** `NONE`. No document anywhere records a
  different value; every one of the six milestones accepted since the
  last global reconciliation explicitly returns current authorization to
  `NONE` at its own close.
- **Latest accepted milestone (going in):** Place Feature Comparison &
  Habitat Outcomes v1: report correction (`5e36989`). Exact match.

**No discrepancy between the brief's expected starting state and
repository evidence was found**, with one exception described next.

### Documentation-hygiene finding: `release-execution-state.md` §16 is stale

§16 ("Transition checkpoint") still records **`Accepted HEAD: 763fe22`**
(the Multi-Camera Place Experience v2 implementation commit, 2026-08-26)
as its top bookkeeping block, and states **`LICENSE: still genuinely
absent -- open business/legal decision, not resolved by this or any prior
milestone`** and **`Current authorized implementation milestone: NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`**
([release-execution-state.md:10253-10260](release-execution-state.md),
[:10726-10727](release-execution-state.md),
[:10676-10677](release-execution-state.md)). All three statements are
false as of this reconciliation: HEAD is `5e36989`, not `763fe22`; Lane P
is `CLOSED` with a real `LICENSE` file, contradicting §16's own "still
genuinely absent" line stated *in the same document* whose §6 Lane P entry
correctly says `CLOSED`; and the named reconciliation (v1) already ran on
2026-09-06. §16 was simply never updated after the 2026-08-26 checkpoint
that produced it, while roughly twenty further milestones were accepted
and §§5-6 and §14 (which *are* current, confirmed independently) kept
pace. This is a documentation-currency defect, not a product or release
gap -- it is corrected by this milestone (see "Documentation-hygiene
correction made by this milestone," below), consistent with this
reconciliation's authorization to correct "accepted HEAD/schema, corrected
lane/opportunity status, concrete blockers, and accepted validation
state."

---

## 2. Accepted delta since the last global reconciliation

**Baseline:** *Global Remaining Product-Development & Release-Queue
Reconciliation v1*
([report](global-remaining-product-development-release-queue-reconciliation-v1-report.md)
`9c4f8d5`, reconciliation `9eaa6e0`; HEAD at the time `b3dba92`; schema
v58). That milestone's own finding, read in full for this reconciliation:
feature freeze **functionally confirmed** by an evidence-based,
five-question test applied to every named remaining product opportunity,
against a full A-S lane walk; zero opportunities cleared the bar for
"substantial product development before release"; the one concrete,
advisory next action it named was Lane P's mechanical LICENSE adoption
(explicitly not self-authorized). Its own closing classification: **A**.

**Six milestones have been accepted on `main` since that baseline**, all
read in full for this reconciliation (five directly named by the governing
brief, plus the Lane P closure that immediately preceded them and is
already "priced into" the brief's own expected starting state):

| # | Milestone | Commits (impl / report) | Schema | Repo's own classification |
|---|---|---|---|---|
| 1 | MIT Source License Adoption & Lane P Mechanical Closure v1 | `bdfa35f` / `d3b9820` | v58 (unchanged) | A |
| 2 | Environmental Context x Place Story & Habitat Change Composition v1 | `1709bf3` / `c07171b` | v58 (unchanged) | A |
| 3 | Year-over-Year Seasonality & Long-Term Place Memory v1 | `a83b4e3` / `2771d4c` | v58 (unchanged) | **B** (see below) |
| 4 | Multi-Camera Place Feature Linking & Cross-View Habitat Context v1 | `3cce9e4` / `973cb5e` | v58 -> **v59** | A |
| 5 | Place Story Deep Dives & Representative Evidence v1 | `33d9f5f` / `594d65b` | v59 (unchanged) | A |
| 6 | Place Feature Comparison & Habitat Outcomes v1 (+ report correction) | `76c3b92` / `b788974` / `5e36989` | v59 (unchanged) | A |

Milestone #1 directly executed v1's own recommended next action. Milestones
#2-6 are the brief's five named deltas, all built as **bounded, explicitly
owner-authorized, one-time exceptions during the freeze** -- the phrase
"a deliberately-authorized, one-time, bounded reopening... not a
resumption of general product development" (or a close paraphrase)
appears in `roadmap.md` five separate times for this exact chain
(`roadmap.md:3678-3680,3712-3714,3764-3767,3818-3821,3878-3881`). Every
one of #2-6 explicitly self-certifies, in its own report, that it leaves
Lane R, Lane P, and BirdNET's legal posture completely untouched, and that
current authorization returns to `NONE` at its close. **None of the five
claims to advance release readiness; each was deliberately picking up an
item this project's own v1 reconciliation had already, explicitly,
classified `D -- enrichment`** in its "Remaining substantial
product-development candidates" table
([v1 report](global-remaining-product-development-release-queue-reconciliation-v1-report.md),
lines 252-262) -- i.e. this delta is *evidence that the freeze held*, not
evidence it was breached: the largest deferred items on v1's own list are
now also done, and what is left is thinner than what v1 already found
insufficient.

### What each delivered

1. **MIT Source License Adoption & Lane P Mechanical Closure v1** --
   created the real `LICENSE` file, PEP 639 SPDX metadata in
   `pyproject.toml`/`web/package.json`, and corrected `README.md`'s
   License section; proved MIT inclusion in built wheels/bundles. Lane P:
   `OWNER DECISION RESOLVED -- MECHANICAL ADOPTION PENDING` -> `CLOSED`.
2. **Environmental Context x Place Story & Habitat Change Composition
   v1** -- composed the already-accepted weather engine into Place
   Story/Feature before-after comparisons via one new pure module and one
   new repository method; every generated sentence drawn from five fixed,
   non-causal templates; `information_class` typed `Literal["inferred"]`
   so the type system itself forbids marking this "reviewed." Zero schema
   change.
3. **Year-over-Year Seasonality & Long-Term Place Memory v1** -- the
   product's first true year-over-year comparison (Place-level and
   species-level), reusing the existing materiality primitive unmodified;
   new `GET /api/place/year-over-year`; three genuine pre-shipping defects
   caught and fixed by this milestone's own tests. **Classified B, not A,
   by its own explicit reasoning**: "the one inherent, undeferrable
   limitation is that no real deployment can yet demonstrate a live
   `\"comparable\"` outcome, since this product does not yet have a full
   year of real accumulated field history anywhere -- every
   positive-outcome proof in this report is necessarily synthetic." A
   direct query against the real local dev DB returned an honest
   `status="insufficient_prior_history"`. Zero schema change.
4. **Multi-Camera Place Feature Linking & Cross-View Habitat Context
   v1** -- one new additive-and-backfilled table
   (`place_feature_observation_links`), letting a Place Feature link to
   more than one camera/Zone view; found and fixed three genuine
   pre-existing defects (archived-Source Feature-association going silent
   on camera archival; `delete_zone`'s reference guard never checking
   Feature-linked Zones; a real N+1 query). **Schema v58 -> v59.**
5. **Place Story Deep Dives & Representative Evidence v1** -- the
   product's first two dedicated "story of one thing" pages (Taxon Story,
   Feature Story -- the latter also the first dedicated Feature detail
   page, closing a gap two prior milestones had each separately
   recorded), composed entirely from already-accepted endpoints. Shares
   Milestone 3's honest limitation: "this product does not yet have a
   full multi-year real deployment anywhere" -- proof is synthetic.
6. **Place Feature Comparison & Habitat Outcomes v1** -- a ranked Feature
   comparison overview and a Habitat Change Outcomes view, implemented as
   exactly one new repository method plus one behavior-preserving
   extraction; explicitly, by name, closes the item v1's own review had
   classified `D -- enrichment` ("ranked Feature comparison view"). Its
   `report correction` (`5e36989`) fixed a self-caught arithmetic citation
   error in a test-count breakdown (one file's count corrected 18 -> 24 so
   the itemized list actually sums to the already-correct stated total of
   172) -- a narrow, non-substantive evidence-citation fix, not a
   functional or decision change.

### Cross-cutting findings across the delta (worth tracking, none release-blocking)

- **A recurring, never-fixed test flake** in the
  `test_place_biodiversity_summary_repository.py` /
  `test_place_change_summary_repository.py` family (a real-wall-clock
  -date-sensitive fixture issue) was independently re-hit and
  independently re-bisected as pre-existing/unrelated in the Core runs of
  milestones #3, #4, #5, and #6 -- four consecutive milestones. It has
  never blocked acceptance and is not release-blocking, but its
  persistence across four Core runs without a fix is small, accumulating,
  now-explicitly-tracked technical debt.
- **A disclosed-but-unfixed copy ambiguity**: `featureAssociationSentence`
  renders identical wording for `early_signal` and `comparable` maturity,
  contradicting `comparison_insight_event`'s own more careful qualifier.
  Named in Milestone #2, still unfixed and re-disclosed in Milestone #6.
- **Two milestones' positive outcomes are proven only synthetically**
  (#3 and #5): both are honest, both explicitly disclose this as
  "blocked on elapsed real history, not engineering," and neither treats
  it as a defect -- but a governance reviewer should know that neither
  milestone's core new capability has yet been observed to produce a real
  positive result against real accumulated field history anywhere.
- **Latest accepted Core validation run** (Milestone #6, the most recent):
  **5,897 passed / 4 failed / 3 skipped / 23 deselected / 11 xfailed, 276
  warnings** (45m18s). All four failures independently reconfirmed
  pre-existing/unrelated via `git stash push -u` bisection against the
  exact starting commit: three are the recurring flake family above; the
  fourth (`test_analysis_stream_disconnect_during_inflight_capture_releases_camera_lock`)
  is a newly-observed concurrent-load timing flake in unrelated Camera
  Node code, confirmed non-deterministic (passes cleanly in isolation).
  Schema v59 unchanged. This is healthy validation evidence.

---

## 3. Complete lane-status table

All nineteen lettered lanes of `release-execution-state.md` §6, verified
against direct repository evidence this session (via the four parallel
research passes described below) plus the delta in §2. "Bucket" is this
report's own A/B/C/D legend (release-critical / pre-release decision /
after-release / later-evidence-driven), assigned to each lane's
**remaining** work, not its closed status.

| Lane | Status | Remaining work | Bucket |
|---|---|---|---|
| **A** Acoustic/BirdNET | ACCEPTED -- RELEASE-READY OPTIONAL | longer field soak; physical unplug/replug; natural wild-bird field evidence | D |
| **B** Remote/Intermittent-WAN | PARTIAL -- AFTER RELEASE UNLESS NEW CORE DEPENDENCY | real LTE/remote-Pi/bandwidth/solar acceptance | C |
| **C** Everyday Product/Discovery UX | MATERIALLY DELIVERED / NO KNOWN DEV REMAINS | none | -- |
| **D** Calm Notifications | MATERIALLY DELIVERED | Web Push; per-user read state; precise deep links; model-unavailable attention; sync diagnostics | D |
| **E** Mobile/Remote UX | PARTIAL, MATERIALLY ADVANCED | dense-page progressive disclosure (D); live external-overlay-network acceptance -- structurally blocked, this sandbox has no external network (B) | D/B |
| **F** Multi-Camera/Multi-Site | MATERIALLY ADVANCED; concurrent-write reliability CLOSED; **Feature linking CLOSED 2026-09-06** | cross-camera notification grouping (D -- **not named anywhere in `roadmap.md` at all**, a genuine untracked-by-name gap, flagged here so it isn't lost); Story wildlife-source attribution (D); ~6 camera-filter UI controls to consolidate (D); GPU-concurrency measurement + multi-hour soak -- needs real hardware (B); broad multi-site -- separate product decision (C) | D/B/C |
| **G** Camera/Source Experience | **CLOSED -- RELEASE-CRITICAL** (2026-09-03) | none release-blocking | -- |
| **H** Site-Specific Learning | FROZEN | none unless new evidence | D |
| **I** Broader Wildlife Maturity | FROZEN STRUCTURALLY | mature mammal ID -- zero real MockingBird-domain mammal field evidence exists anywhere | D |
| **J** Ecological/External Workflows | MATERIALLY ADVANCED | live OAuth submit; media-byte inclusion; deep-link preselect; batch-filter depth | D |
| **K** Ecosystem/Provider Integrations | DECISION CLOSED -- deferred pending evidence, not required for launch | none (decision-only lane) | -- |
| **L** Appliance/Update/Recovery | MATERIALLY CLOSED -- RELEASE-CRITICAL | `rollback()` doesn't restore a changed systemd unit template; a narrower rollback crash-window gap -- both small, disclosed, worked around once live | **A** |
| **M** Storage/Retention UX | **CLOSED -- RELEASE-CRITICAL** | orphan-media sweep, deliberately not reopened | D |
| **N** Privacy/Contribution | **CLOSED -- RELEASE-CRITICAL** | none | -- |
| **O** Platform/Runtime Portability | **CLOSED** | none | -- |
| **P** Release Licensing/Distribution | **CLOSED -- RELEASE-CRITICAL** (confirmed §1, above) | BirdNET commercial-adjacent legal posture -- no engineering action available | B |
| **Q** Whole-Product UI/Accessibility/Performance | **CLOSED as integrated pass** | disclosed non-blocking test-hygiene/CSS/keyboard-on-zone-polygon items | D |
| **R** Complete Field Acceptance | **OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS** | one more genuine-daylight representative field tranche (see §6) | **A** |
| **S** Final Release Hardening (+ Gate G, External Pre-Release Acceptance, its own precondition) | LAST; not started, not scoped | correctly sequenced strictly after Lane R closes and Gate G runs | **A** |

---

## 4. Release readiness: the task's named lane subset (G, L, M, N, O, P, Q, R, S)

One line each, for direct traceability to the governing brief's §4 list
(full detail in the table above):

- **G** Camera/Source: CLOSED -- RELEASE-CRITICAL. No residual.
- **L** Appliance/Update/Recovery: MATERIALLY CLOSED -- RELEASE-CRITICAL.
  Two small disclosed rollback residuals remain, both previously worked
  around live in the field once, neither structurally closed.
- **M** Storage/Retention: CLOSED -- RELEASE-CRITICAL. No residual
  (orphan-media sweep deliberately not reopened, low materiality).
- **N** Local Only/Privacy: CLOSED -- RELEASE-CRITICAL. No residual.
- **O** Platform/Runtime support truth: CLOSED. No residual.
- **P** Licensing/Distribution: CLOSED -- RELEASE-CRITICAL (confirmed
  directly this session). BirdNET's commercial-adjacent legal posture is a
  standing, separate, non-blocking legal-review item.
- **Q** Accessibility/Performance: CLOSED as an integrated pass. Disclosed
  non-blocking residuals only.
- **R** Representative field acceptance / true latency: **OPEN --
  RELEASE-CRITICAL.** The sole remaining release-blocking item in this
  entire subset. See §6.
- **S** External Pre-Release Acceptance / Final Release Hardening: not
  started, not scoped. Correctly sequenced downstream of R (and, now that
  P is closed, no longer also blocked on P).

**One-public-launch doctrine, preserved, quoted exactly:**

> "External Pre-Release Acceptance -> Final Release Hardening -> the one
> public launch -- no separate beta release precedes it."
> ([release-execution-state.md:9640-9642](release-execution-state.md))

> "Gate G is private validation of the still-unreleased product before
> launch, not a separately released public beta -- do not describe it, or
> the release that follows it, as a beta externally."
> (`roadmap.md:2639-2641`)

**Neither downstream gate is started by this reconciliation.** External
Pre-Release Acceptance (Gate G) is "not yet ready... not started, not
scoped" per the prior reconciliation's own explicit finding
([v1 report](global-remaining-product-development-release-queue-reconciliation-v1-report.md),
"External Pre-Release readiness criteria"), concretely blocked on: (1)
Lane R closing (or an explicit release-authority decision to accept the
current evidence, mirroring how the recall dimension was already
resolved); (2) Lane P's mechanical LICENSE adoption -- **now done**,
resolved since Milestone #1 in §2; (3) a cohort plan actually being
scoped -- who participates, how many, what diversity of real setups, how
findings are triaged -- "never... defined," per `roadmap.md`'s own honest
Gate G text. With (2) now resolved, (1) and (3) are the two genuinely
remaining preconditions; (3) has no daylight or hardware dependency (see
§7, "Recommended next milestone"). Final Release Hardening (Lane S) is
correctly sequenced strictly after Gate G actually runs, not merely after
the capability set stabilizes -- starting it early would discard real
external findings Final Hardening exists to triage.

---

## 5. Remaining release-critical work (Bucket A)

- **Lane R -- true-latency tail.** The sole item standing directly between
  this product and starting the downstream release sequence. See §6 for
  full detail.
- **Lane L -- two small disclosed rollback/systemd-template residuals.**
  Both previously worked around live in the field once; neither
  structurally closed. Small, bounded, not currently scheduled.
- **Lane F -- GPU/CUDA-driver-level concurrent-inference measurement and a
  multi-hour concurrent soak.** Needs real hardware this sandbox lacks.
- **Lane E -- live external-overlay-network (Tailscale/WireGuard)
  acceptance.** Has never been possible from this sandbox; needs real
  external network access.
- **Gate G scoping and execution, then Lane S.** Correctly not started;
  see §4 for exact preconditions.

None of these is new. All were already tracked before this reconciliation;
this pass reconfirms none has silently resolved and none has grown.

## 6. Unresolved pre-release decisions (Bucket B)

- **BirdNET commercial-adjacent legal posture.** Standing legal-review
  item: "whether an individual user's own private, non-commercial use of
  MockingBird+BirdNET... could ever be implicated merely because the
  surrounding open-source project also accepts donations or sells
  optional paid support remains genuinely unresolved." No engineering
  action is available; does not block core public launch (acoustics ships
  as the already-accepted optional capability regardless of this
  question's resolution).
- **Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md`/
  `THIRD_PARTY_NOTICES.md`** (all three confirmed present) -- brand/
  trademark review, website/docs polish -- named "not now" in
  `roadmap.md`'s own "Public release readiness" text.
- **Gate G's cohort/findings-intake plan.** Genuinely undefined. Has zero
  daylight/hardware dependency, and its formerly-blocking precondition
  (Lane P) is now resolved -- it could be scoped in parallel with waiting
  for Lane R's daylight window. Recorded here as a real open decision, not
  self-authorized (see §7).

## 7. After-release opportunities (Bucket C)

Per `release-execution-state.md` §8, verbatim, unchanged and reconfirmed
still accurate: complete remote/intermittent-WAN/LTE field deployment;
solar/battery; custom CM4/CM5 hardware; research-grade remote-field
acceptance; broad multi-site; native mobile; advanced acoustic analytics;
mature automatic mammal species identification.

Plus, confirmed still open by this reconciliation's own delta-and-roadmap
walk (§2, §8 of this report; none promoted to release-critical):
multi-camera notification grouping (genuinely untracked by name anywhere
in `roadmap.md` until this report -- flagged for the scheduler); Place
Story wildlife-event source attribution; ~6-control camera-filter UI
consolidation; Web Push and the rest of Lane D's enhancement list;
live OAuth iNaturalist submission, media-byte inclusion, deep-link
preselection (Lane J); a Wildlife Insights integration decision (still
unresearched); GBIF direct publication (deferred, institutional); Land
Management/Agriculture (non-primary audience, `roadmap.md` Layer 5).

## 8. Later / evidence-driven work (Bucket D)

Per `release-execution-state.md` §9, verbatim, unchanged: GenICam, GigE
Vision, USB3 Vision, radiometric thermal, specialized industrial cameras,
individual-animal recognition, population estimates, behavior prediction,
causal ecological modeling, large cloud-first infrastructure.

Plus, evidence-gated (not engineering-gated) items reconfirmed by this
pass: **year-over-year seasonality's own real-outcome proof** -- the
capability shipped in §2 (#3), but a live "comparable" result needs a full
year of real accumulated field history nowhere in this product yet exists;
**mature automatic mammal species identification** -- zero real
MockingBird-domain mammal field evidence exists anywhere, per the standing
record; **Feature-specific year-over-year, week/named-seasonal-period
comparison, Place Story period summaries** (the last explicitly deferred
on a *named performance-cost risk*, not merely low priority -- do not
rush this one pre-freeze if it is ever picked up); **deeper ERA5/
Open-Meteo archive backfill and wind/cloud-cover statistical
associations**; **a dedicated Explore page** (considered and rejected as
navigation nicety, not a capability gap, by v1's own review; nothing in
this delta changes that).

---

## 9. Product capability-set-complete judgment

**Yes.** The intended first-public-release capability set is complete
enough to impose a durable feature freeze, and this reconciliation
reaffirms -- on independently re-gathered evidence, not by trusting the
prior finding -- that it already was.

This is a **re-confirmation**, not a fresh discovery: v1 already made this
finding via a rigorous five-question test against every named
opportunity. What this reconciliation adds is that the delta since v1
*strengthens* rather than weakens it: five of the largest items on v1's
own "deferred, D-bucket enrichment" list have now also been built, as
bounded, explicitly-authorized, one-time exceptions that never claimed to
be release-necessary and never reopened the freeze. What remains on the
enrichment list is thinner than what v1 already found insufficient to
justify pre-release work.

Independently re-walking every opportunity named in the governing brief's
§3 against current `roadmap.md` text (not against memory, not against v1's
own summary of itself):

| Opportunity | Verdict |
|---|---|
| Place Story period summaries | OPEN, explicit non-goal for now, deferred on a **named performance-cost risk** -- do not rush pre-freeze |
| Feature-specific YoY / additional seasonality modes | Place/species-wide YoY now **DONE** (§2 #3); Feature-specific YoY an explicit non-goal; week/named-period seasonality still open |
| Environmental archive/backfill & deeper associations | OPEN, confirmed still unbuilt as of the 2026-09-06 text (ERA5/Open-Meteo backfill, wind/cloud-cover associations) |
| Source-quality signals & diagnostics surfaces | Narrow admission-yield source-quality signal **already shipped** (Place/Yard Intelligence v2); a broader unified "diagnostics surface" is not named as such in `roadmap.md` -- closest relatives (Doctor API/UI, unified Explainability view, causal Visit tracing) are open but plausibly under-dated prose (see documentation-currency note, below) |
| Multi-camera notification grouping & source attribution | Source attribution **DONE** (Camera/Source + Multi-Camera Maturity v1); notification grouping is a **genuine gap `roadmap.md` never names** -- recorded in §7, above, so it is not silently lost again |
| Camera-filter consolidation | OPEN, confirmed still open as of the 2026-09-06 text |
| Mobile/remote refinements | Dense-page progressive disclosure open (D, minor); external-overlay-network acceptance structurally blocked by this sandbox (B, a validation gap, not an unbuilt capability) |
| Broader wildlife & provider work | Promotion-pipeline mechanism itself mature and repeatedly exercised (several accepted "retain baseline, promote nothing" decisions); broader non-avian/mammal expansion genuinely open but **evidence-gated**, not engineering-gated |
| Remaining research/conservation opportunities | eBird definitively closed/excluded (policy, not a gap); iNaturalist/Darwin Core/Camtrap DP delivered; GBIF deferred (institutional); media-byte export bundling and a Wildlife Insights decision genuinely open; broader dataset-contribution/learning-ecosystem lane explicitly "not started, gated behind mature evidence and dataset governance" |

**None clears the bar for pre-release necessity.** Every item is either
already delivered, mechanically impossible right now (blocked on elapsed
real history), carries a named risk arguing against rushing it pre-freeze,
or is enrichment on an already-shipped, already-functioning concept a
first public user would experience as "less powerful," not "unfinished."
This report does not select any of them merely because they are adjacent
to the just-completed delta.

**What genuinely remains before the one public launch is not missing
product capability.** It is: (1) Lane R's true-latency-tail field
evidence (a validation gap, not a product gap); (2) a handful of small,
individually-disclosed, mostly hardware- or sandbox-access-gated
validation residuals (Lanes L, F, E); (3) the standing BirdNET
legal-review question (no engineering action available, does not block
core launch); and (4) scoping and then running External Pre-Release
Acceptance and Final Release Hardening, correctly not yet started.

**Minor documentation-currency note** (not release-blocking, not chased
down further by this read-only pass): a full-file read of `roadmap.md`
surfaced that "Appliance/Storage/Privacy/Recovery v1" shipped real
capability "with no corresponding roadmap-prose update of its own" by
`roadmap.md`'s own admission (`roadmap.md:1086-1088`), that Habitat &
Phenology Foundation (Layer 3) carries no dated status update anywhere in
its own section despite being treated as an accepted foundation elsewhere,
and that a handful of Gate D/E storage-health/diagnostics passages may
predate capability that has since shipped. Worth a future bounded
housekeeping pass; does not change this judgment.

---

## 10. Lane R: current evidence and next field contract

**Current status: OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE
REMAINS.** Unchanged since *Gate A True-Latency Tail Closure & Final Lane
R Decision v1* (`b6b4727`), reconfirmed by *Representative Daylight
True-Latency Tail Convergence v2* (`a7f879f`, the latest accepted
document), which added **zero new evidence**.

Six of eight/nine tracked release dimensions are already `READY FOR
RELEASE BUDGET` (false-Visit rate, fragmentation, duplicates,
useful-evidence, evidence-survival, monitoring coverage). Recall's own
release-decision is resolved (`ACCEPTED KNOWN LIMITATION -- NO NUMERIC
RECALL FLOOR YET`, not reopened by this pass). **True capture-to-visible
latency's unconverged tail is the sole remaining blocker.**

### Standing evidence body (unchanged by this reconciliation)

Four sized, RTT-normalized cohorts:

| Cohort | Date | n | Median | p90 | Max | Status |
|---|---|---|---|---|---|---|
| v9 | 2026-09-01 | 24 | 111.8s | 173.9s | 307.4s | Intact, live-measured |
| v10 | 2026-09-01 | 11 | 103.9s | 183.3s | **742.3s** | Intact, live-measured |
| v11 | 2026-09-02 | 23 | 115.7s | 318.5s | **865.2s** | Supporting only -- offline reconstruction, never visually re-verified |
| v14 | 2026-09-05 | 14 | 82.9s | 235.5s | 261.2s | Intact, live-measured, richest sample to date |

Tail spans **261.2s-865.2s**, no convergence; medians reasonably stable
(~83-116s). A fifth attempt (the dusk-start *Final Lane R Decision v1*
session) produced n=1, independently judged "likely not a real animal,"
excluded. The most recent attempt (*Convergence v2*, night of 2026-09-05,
21:26-21:29 EDT local, roughly 1.5-1.7 hours past civil twilight end) was
blocked at a **hard pre-deployment daylight gate** -- zero deployment,
zero samples.

*(For completeness: an intermediate reconciliation,* Gate A Release-Budget
& Evidence-Sufficiency Reconciliation v1 *(`8c42f80`), was explicitly
**not accepted** -- it silently excluded ambiguous-boundary misses from
the recall denominator to manufacture an inflated recall figure, and its
own latency tail table omitted v10's already-accepted 742.3s maximum. It
was corrected by* Gate A Whole-Scene Budget & Remaining-Evidence
Correction v1 *(`bf7ee89`), which restored Lane R to `OPEN`. This history
does not change the current status; recorded here for provenance.)*

### Is a "v3" still the correct next field action?

**No report titled "Convergence v3" (or "Field Acceptance v15") exists
anywhere in this repository, and nothing has been attempted since the
failed night attempt on 2026-09-05.** The plan is unchanged, unsuperseded
by any later evidence, quoted exactly rather than paraphrased:

> "The smallest sufficient next step... **one more already-otherwise
> -motivated representative *daylight* session (not a latency-dedicated
> cohort) run for its own reasons would add a genuine 5th qualifying
> sample**; a session deliberately scheduled to start with at least ~75
> minutes of remaining daylight would avoid repeating this milestone's own
> dusk-timing gap."
> (*Gate A True-Latency Tail Closure & Final Lane R Decision v1*)

> "The next attempt at this exact milestone should simply be re-run during
> genuine daylight hours (per the reference site's own established
> pattern, roughly mid-morning through mid-afternoon EDT...) -- **no other
> precondition changed tonight**."
> (*Representative Daylight True-Latency Tail Convergence v2*)

Both converge on the same substantive precondition set; neither document
names the next attempt "v3." Functionally, "the next Lane R field
action" -- whatever it ends up being titled -- is still correct and
unsuperseded.

### Exact preconditions remaining

1. **Genuine daylight window** -- a *diurnal*, not seasonal, gate: start
   mid-morning through mid-afternoon EDT, or with >= ~75 minutes of
   remaining daylight if starting later. No document anywhere claims a
   seasonal block; early-September daylight hours are described as fully
   representative.
2. **Sample-size target**: >= 12 valid RTT-normalized latency samples;
   an ordinary 90-105 minute session length is recommended so the session
   is not sample-starved.
3. **Explicit authorization** -- currently `NONE`. Not granted by this
   reconciliation.
4. **Camera Node re-pairing** -- last left paired to an archived
   instance; needs the same non-destructive, multiply-precedented pairing
   reset, with separate explicit user authorization per this project's
   standing practice.
5. **Non-blocking**: an 18.5GB storage-reclaim opportunity across two
   archived, `SAFE_TO_RECLAIM`-flagged Windows dev-roots remains
   available and undone -- worth doing if margin is tight, not required.
6. **No code or mechanism preconditions remain.** RTT-bounded clock
   calibration, evidence-capture, and ledger-snapshot tooling are all
   separately closed and proven correct by prior accepted milestones.

### Latency budget

**Explicitly not set, and this report does not invent one**, per the
standing, repeatedly-reaffirmed position: "**MORE EVIDENCE REQUIRED** --
unchanged from the accepted pre-milestone state... no budget is adopted on
the strength of a single doubtful sample," and the standing instruction
this project already follows not to "ask what number lets everything
pass." A converged, multi-cohort (ideally 5+ sized samples)
characterization of the p90/max tail is the named bar for closing this
dimension -- not the stable median alone.

### Daylight availability, recorded as an opportunity, not an authorization

The Lane R block is purely a time-of-day scheduling matter, not a
multi-week seasonal one. If a genuine daylight window (mid-morning through
mid-afternoon EDT, or any comparable window with sufficient remaining
daylight) is next naturally available, that is recorded here as a
legitimate execution opportunity consistent with the preconditions above
-- **this report does not run a field session, does not deploy, and does
not authorize one.** Explicit authorization remains `NONE`.

---

## 11. Recommended next milestone

**Top recommendation (advisory only, not self-authorized): the next Lane
R representative-daylight field tranche**, once a genuine daylight window,
explicit authorization, and routine Camera Node re-pairing are all in
place. Rationale: it is the *only* item standing directly between this
product and starting the downstream release sequence (Gate G -> Lane S ->
the one public launch); it carries zero remaining engineering unknowns
(every mechanism precondition is already closed); and further delay does
not reduce its cost -- only real elapsed daylight time converts it into a
5th qualifying sample. Nothing else in the complete queue is
comparably release-critical: every other release-critical residual (Lanes
L, F, E) is individually small, already disclosed, and gated on hardware
or network access this sandbox cannot supply regardless of scheduling.

**Strongest alternative: scope Gate G's cohort and findings-intake plan,
in parallel.** This has zero daylight or hardware dependency, and its
formerly-blocking precondition (Lane P) is now resolved (§2, Milestone
#1) -- it does not need to wait for Lane R, and doing it now would shorten
the critical path once Lane R does close, exactly as v1's own "External
Pre-Release readiness criteria" already found ("these do not block
starting Gate G scoping work in parallel with #1 [Lane R], once #2 [Lane
P] is done"). This report records it as the strongest non-Lane-R option,
not as a competing "instead of" choice -- both are legitimate parallel
tracks; this reconciliation authorizes neither.

**Explicitly not recommended, and explicitly considered and rejected**:
continuing the just-completed Place-Intelligence enrichment streak (e.g.
environmental archive/backfill, multi-camera notification grouping,
camera-filter consolidation) merely because it is adjacent to the
five most recent milestones. Every item in that family remains correctly
bucketed C/D (§7-§8) -- real, and not without value, but not the next
priority, and picking one now would be selecting by adjacency rather than
by release criticality, which the governing brief specifically warns
against.

A recommendation is advisory until ChatGPT authorizes it. This report does
not fill the scheduler's authorization field with either option above.

---

## 12. Explicit non-goals

**Of this reconciliation milestone itself:** no product, test, or schema
code changes; no field session run; no deployment; no model changed; no
push; no next-milestone implementation; no change to current authorization
(remains `NONE`); no touching of the seven preserved untracked detector
files (reconfirmed present, untracked, unmodified, both before and after
this milestone's edits).

**Of the product roadmap right now:** no enrichment/product-development
milestone is promoted to release-required status (all named opportunities
in §9 reconfirmed non-blocking); no broad multi-site; no native mobile; no
remote/LTE/solar field productization; no mature automatic mammal ID; no
re-opening of BioCLIP 2.5 / species-classification promotion (frozen, no
re-promotion, per standing record); no starting Gate G execution (only
*scoping* is arguably unblocked, and even that is advisory here, not
self-authorized); no starting Final Release Hardening (Lane S); no
inventing a Lane R latency budget; no running or scheduling a Lane R field
session by this milestone.

---

## 13. Documentation-hygiene correction made by this milestone

Consistent with this milestone's authorization to reconcile "accepted
HEAD/schema, corrected lane/opportunity status, concrete blockers, and
accepted validation state" -- and following this document's own
established convention of *adding* a dated correction rather than
rewriting history in place (the same pattern already used within Lanes A,
E, and P) -- this reconciliation makes exactly two additive edits to
`docs/release-execution-state.md`:

1. A new dated correction paragraph appended to the end of the `##
   CURRENT PHASE` section (after v1's own 2026-09-06 correction), recording
   this reconciliation's HEAD/schema/delta/judgment and pointing to this
   report.
2. A short correction/pointer note inserted immediately after the `## 16.
   Transition checkpoint` heading, flagging that section's existing
   content as dated to the 2026-08-26 Multi-Camera Place Experience v2
   checkpoint and pointing readers to the new top-of-file correction (and
   this report) for current facts. The historical stacked entries below it
   are left untouched, exactly as this project's own convention treats
   superseded narrative elsewhere in the file.

**Current authorization remains `NONE`.** Neither edit changes it.

---

## 14. Classification of this reconciliation milestone

Using this repository's own per-milestone acceptance rubric (not this
report's A-D work-bucket legend, see the note at the top of this
document): **A** -- a complete, bounded governance reconciliation with no
residual gap in its own scope. Every verification claim above is grounded
in direct repository evidence gathered this session (four full-document
research passes plus direct file/git verification), not in this session's
own memory or in historical conversation reconstruction. No discrepancy
was found between the brief's expected starting state and the repository,
except the now-corrected §16 documentation-currency defect. The feature
-freeze finding is reaffirmed, strengthened by the accepted delta, and not
weakened by it. Lane R's status, evidence, and next-field-contract are
fully reconciled with no invented numbers. No downstream gate is started.
No authorization is granted.

## Decision

**A**
