# Global Remaining Product-Development & Release-Queue Reconciliation v1

Documentation/governance reconciliation. Zero product, test, or schema code
touched. No field session run, no defect fixed, no model changed.

## Starting state

Verified directly against the repository, not assumed from the governing
brief's own conversation-side memory:

- **Branch:** `main`. **HEAD:** `b3dba92` (the reconciliation commit
  recording Representative Daylight True-Latency Tail Convergence v2).
  Exact match to the brief's expected `b3dba92`.
- **Schema:** `v58`, confirmed throughout `docs/release-execution-state.md`
  and unchanged since.
- **Latest accepted milestone:** Representative Daylight True-Latency Tail
  Convergence v2, classification **B** -- blocked at the hard daylight
  gate (21:26-21:29 EDT, night), zero new latency samples, zero deployment.
  Exact match to the brief's expected state.
- **Gate A:** `OPEN -- TRUE LATENCY TAIL EVIDENCE REMAINS`. **Lane R:**
  `OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS`. **Whole
  -scene recall:** `ACCEPTED KNOWN LIMITATION -- NO NUMERIC RECALL FLOOR
  YET`. **Current authorization:** `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`. All four exact matches to the brief's expected
  state.
- **Worktree safety:** the seven preserved untracked detector files
  (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) are present, untouched, and are the
  entire `git status --porcelain` output -- no active writer, nothing else
  dirty.

**No discrepancy between the conversation-side expected state and
repository evidence was found.** The repository is already exactly where
the governing brief said it would be.

## Why reconciliation was required

`docs/release-execution-state.md`'s own header has read, since before this
milestone, `## CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT`, with the
explicit warning that Representative Field Acceptance, External
Pre-Release Acceptance, and Final Release Hardening "must not become the
default next milestone while substantial product-roadmap capability
remains intentionally unfinished." In practice, roughly the last three
weeks of accepted work (2026-08-19 through 2026-09-05) concentrated almost
entirely on Lane R / Gate A field-acceptance correctness -- real value, but
narrow. No session had recently re-walked the complete A-S lane queue to
ask whether that phase label still matched reality, or whether the product
-roadmap capability it was protecting had, milestone by milestone, already
been substantially delivered elsewhere. This milestone performs exactly
that walk, reading `release-execution-state.md` (9,877 lines) and
`roadmap.md` (4,125 lines) in full, plus `product-doctrine.md`, rather than
sampling or trusting prior summaries -- including this session's own
persistent memory, which (see below) is demonstrably behind the repository
on several points.

## Owner MIT decision

The project owner has selected **MIT** as MockingBird's own source-code
license. This resolves the one item `docs/release-execution-state.md` Lane
P and `README.md`'s own "License" section have both explicitly named, since
Release Licensing, Distribution & Third-Party Legal Closure v1
(2026-08-30), as outside a bounded engineering milestone's authority: "a
business/legal decision... not resolved by this or any prior milestone."
That report's own decision packet recommended MIT first, named Apache-2.0
and a copyleft option and rejected both with reasons, and confirmed every
current dependency's license is compatible with either permissive option --
the owner's choice needed no new engineering analysis, only a decision.

**A. Owner decision: RESOLVED.** Recorded here as fact, not reopened.

**B. Mechanical follow-through: still required, verified empirically this
session (not assumed from the prior report's own "no LICENSE file exists"
claim):**

```
$ ls LICENSE*
ls: cannot access 'LICENSE*': No such file or directory
$ grep -i license pyproject.toml
(no output)
$ grep -i '"license"' web/package.json
(no output)
$ sed -n '462,467p' README.md
## License

MockingBird's own source-code license has not yet been finalized -- this is
an explicit, open owner decision, not an oversight (see
`docs/release-execution-state.md`, Lane P, for its current status). No
`LICENSE` file exists in this repository yet, and none should be assumed.
```

Three concrete artifacts still say "not yet finalized" or are simply
absent: no `LICENSE` file exists; `pyproject.toml`/`web/package.json`
carry no license metadata; `README.md`'s own "License" section explicitly
tells a reader the decision has not been made. All three would be false as
of this reconciliation if left unchanged.

**C. Lane P closure timing: the owner decision itself is closed now; Lane
P as a release-blocking item is not closed until the repository stops
saying it is undecided.** A person cloning this repository today, or a
future External Pre-Release Acceptance participant, would still read "not
yet finalized" in `README.md` and find no `LICENSE` file. Per this
milestone's own explicit instruction ("Do NOT perform the follow-through
in this reconciliation unless absolutely necessary to make the scheduler
truthful. Prefer recording it as a small explicit next action"), this
reconciliation does **not** create the `LICENSE` file, add packaging
metadata, or edit `README.md`'s License section. Lane P is reconciled
below to **"OWNER DECISION RESOLVED (MIT) -- MECHANICAL ADOPTION PENDING,"**
not to "CLOSED," and the exact three-artifact action is named as the
smallest sufficient next step (see "Ordered global sequence," below).

## Complete A-S lane matrix

Evidence for every entry below is direct: `release-execution-state.md` §6
(read in full this session) cross-checked against the specific accepted
milestone reports it names. "Bucket" uses this milestone's own four-way
scheme: **A** substantial product development before release, **B**
release-critical validation/readiness, **C** pre-release
decision/housekeeping, **D** after-release / later-evidence-driven /
frozen.

| Lane | Current status (repo) | Remaining work | Bucket | Stale? |
|---|---|---|---|---|
| **A** Acoustic/BirdNET | ACCEPTED -- RELEASE-READY OPTIONAL | soak, physical unplug, natural wild-bird evidence | D | **Yes** -- see below |
| **B** Remote/WAN | PARTIAL -- AFTER RELEASE UNLESS NEW CORE DEPENDENCY | LTE/remote deploy/bandwidth/solar | D | No |
| **C** Everyday Product/Discovery UX | MATERIALLY DELIVERED / NO KNOWN DEV REMAINS | none | -- | No |
| **D** Calm Notifications | MATERIALLY DELIVERED | Web Push, per-user read state, precise deep links, health-attention, sync diagnostics -- all explicitly enhancement | D | No |
| **E** Mobile/Remote UX | PARTIAL, MATERIALLY ADVANCED | progressive disclosure; live overlay-network acceptance | D/B(minor) | **Yes** -- see below |
| **F** Multi-Camera/Multi-Site | MATERIALLY ADVANCED; concurrent-write reliability **CLOSED** | notification grouping, Story attribution, filter consolidation, Feature linking (D); GPU-concurrency evidence + soak (B, needs real hardware); broad multi-site (D, separate decision) | D/B | No |
| **G** Camera/Source Experience | **CLOSED -- RELEASE-CRITICAL** (2026-09-03) | none release-blocking | -- | No (repo current; see memory note below) |
| **H** Site-Specific Learning | FROZEN | none unless new evidence | D | No |
| **I** Broader Wildlife Maturity | FROZEN STRUCTURALLY | mature mammal ID needs real field evidence | D | No |
| **J** Ecological/External Workflows | MATERIALLY ADVANCED | OAuth submit, media-byte inclusion, deep-link preselect, batch-filter depth -- all optional | D | No |
| **K** Ecosystem/Provider Integrations | **DECISION CLOSED** -- deferred pending evidence, not required for launch | none (decision-only lane) | C (resolved) | No |
| **L** Appliance/Update/Recovery | MATERIALLY CLOSED -- RELEASE-CRITICAL | 2 small disclosed rollback/systemd-template residuals (B, minor); broader UX (D) | B/D | No |
| **M** Storage/Retention UX | **CLOSED -- RELEASE-CRITICAL** | orphan-media sweep explicitly not reopened | D (deferred by design) | No |
| **N** Privacy/Contribution | **CLOSED -- RELEASE-CRITICAL** | none | -- | No |
| **O** Platform/Runtime | **CLOSED** | none (support truth is now explicit) | -- | No |
| **P** Release Licensing/Distribution | SUBSTANTIALLY CLOSED; **owner MIT decision now RESOLVED, mechanical adoption pending** | LICENSE file + packaging metadata + README correction (small, bounded); BirdNET commercial-adjacent legal review (no engineering action) | C | Updated by this milestone |
| **Q** Whole-Product UI/Accessibility/Performance | **CLOSED as integrated pass** | disclosed non-blocking test-hygiene/CSS items, deliberately bounded | D | No |
| **R** Complete Field Acceptance | **OPEN -- RELEASE-CRITICAL -- TRUE LATENCY TAIL EVIDENCE REMAINS** | one more representative-daylight latency tranche | B | No -- keep open, do not schedule (see below) |
| **S** Actual Final Release Hardening | LAST; not started | correctly downstream of R, P, and Gate G | -- | No |

### Lane detail and specific deltas requested by the governing brief

**Lane A.** §6.A's own remaining-bullet list still reads: "frontend
acoustic health/status; longer field soak; physical unplug/replug; natural
wild-bird acoustic field session." But Whole-Product UI / Accessibility /
Performance Closure v1 (2026-08-27, classification A) states explicitly:
"the scheduler's disclosed bounded acoustic health/status gap (Lane A)
closed with the smallest capability-aware addition the brief allowed --
composed entirely from already-existing facts, never a factor in `ready`."
**Stale entry, corrected below**: "frontend acoustic health/status" is
removed from Lane A's remaining list; the other three items are real and
unchanged.

**Lane E.** §6.E's own remaining-bullet list names four items. Two are
independently, unambiguously closed elsewhere in the same document:

1. *"a pre-existing `ReviewQueuePage` `product_category` gap (found,
   documented, not fixed)"* -- Whole-Product UI / Accessibility /
   Performance Closure v1's own P0 finding is the identical defect: "(1)
   manually- and folder-imported Visits... were silently excluded from
   Review Queue's default 'Animals' tab regardless of `subject_label` --
   the real, previously-unidentified root cause of one class of confusion
   this project had repeatedly, incorrectly attributed to
   `reviewed-product-loop.spec.ts` being an unrelated flake." Fixed, with a
   regression test, at classification A.
2. *"no login rate-limiting exists anywhere in this product"* -- Login
   Rate-Limiting & Authentication Abuse Resistance v1 (accepted
   classification A) closed exactly this gap: a new
   `mockingbird.security.login_rate_limiter.LoginRateLimiter`, a fixed
   1s/2s/5s/15s/30s/60s delay ladder, account- and source-keyed, live at
   `POST /api/auth/sign-in` today.

**Stale entries, corrected below.** The genuinely still-open Lane E items
are: progressive disclosure for the dense Visit/Stream/Settings pages
(real, cosmetic-density, not release-blocking); no live external-overlay
-network (Tailscale/WireGuard) acceptance was ever possible from this
sandbox (a real validation gap, structurally difficult to close without
external network access -- bucket B/minor, not blocking).

**Lane G.** Verified against the newest evidence, not against this
session's own persisted memory. §6.G already reads `CLOSED --
RELEASE-CRITICAL`, closed by Authenticated Camera Node Golden-Path Capture
& Preview Acceptance v1 (2026-09-03, classification A): real authenticated
Node images captured and decoded end to end, real Add Camera
pairing/preview/complete against a fresh disposable Host, real
Chromium/Playwright proof, credential safety verified. This document's own
text is **not** stale here. This session's own persistent memory
([[camera-source-release-hardware-validation-closure-v1-2026-09-02]]) is
the thing that was behind -- it reflects the immediately-prior 2026-09-02
milestone's "MATERIALLY CLOSED / VALIDATION REMAINS" state and has no
entry for the very next day's actual closure. Repository evidence, not
memory, governs, per this milestone's own instruction; Lane G is CLOSED.

**Lane K.** Verified: §6.K already reads `DECISION CLOSED -- DEDICATED
PROVIDER INTEGRATIONS DEFERRED PENDING EVIDENCE; NOT REQUIRED FOR LAUNCH`,
not the "OPEN DECISION" wording the brief specifically warned against
preserving if stale. Already current; no correction needed.

**Lane F.** Every sub-item the brief asked to be accounted for separately
is already tracked distinctly in the repository text, not blended: the
integrated multi-camera product pass (Multi-Camera Place Experience v2,
closed, classification B); the concurrent-write reliability fix
(Concurrent Candidate Visit Persistence Reliability v1, **CLOSED**,
classification A, its own dedicated "Reliability lane status" subsection);
notification grouping / Story attribution / filter consolidation / Feature
linking (each individually named on the standing "do NOT automatically
authorize by adjacency" list); GPU-concurrency real-hardware measurement
and multi-hour soak (both explicitly "needs real hardware this sandbox
lacks" -- a validation gap, not unbuilt product); the legacy 2-Stream
motion-pipeline cap (a pre-existing, disclosed limit on a deprecated path,
not the modern Camera Node path); broad multi-site (explicitly "a separate
product/architecture decision," not release scope). No lane text collapses
these together. No correction needed beyond the bucket assignment above.

## Stale scheduler entries corrected

1. **Lane A** (§6.A): removed "frontend acoustic health/status" from the
   remaining-work list -- closed by Whole-Product UI / Accessibility /
   Performance Closure v1 (2026-08-27).
2. **Lane E** (§6.E): removed the `ReviewQueuePage` `product_category` gap
   -- closed by the same milestone -- and "no login rate-limiting" -- closed
   by Login Rate-Limiting & Authentication Abuse Resistance v1.
3. **Lane P** (§6.P and §2's own License packet reference): recorded the
   owner's MIT decision as resolved, with the mechanical adoption gap
   named precisely and empirically (no `LICENSE` file, no packaging
   metadata, `README.md` still says "not yet finalized").
4. **`CURRENT PHASE`** header: `SUBSTANTIAL PRODUCT DEVELOPMENT` no longer
   matches the evidence across 19 lanes (see "Feature-freeze decision,"
   below) -- corrected.

No other stale lane text was found. Every other lane's own status line
already matched the newest accepted milestone that touches it.

## Remaining substantial product-development candidates

The scheduler and roadmap both name a real list of "substantial remaining
opportunities": year-over-year seasonality; environmental/weather context
composed into before/after and Story; multi-camera Place Feature linking;
ranked Feature comparison; Place Story period summaries; dedicated
taxon/Feature story surfaces; representative imagery on Story cards;
environmental historical backfill / wind / cloud associations; related
Place/Biodiversity work. Applying this milestone's own five-question test
to each:

| Opportunity | Improves core loop? | User perceives absence as unfinished? | Completes shipped concept or new lane? | Pre-freeze dependency/risk? | New correctness surface? | Verdict |
|---|---|---|---|---|---|---|
| Year-over-year seasonality | Marginally | No -- product has ~1 month of real history, not a year | Extends shipped concept | None -- blocked on elapsed time, not engineering | Low | **Cannot be meaningfully built now regardless of effort. D.** |
| Weather composed into before/after & Story | Marginally (enrichment) | Unlikely -- caveat, not a missing capability | Completes shipped concepts (weather + before/after + Story all exist) | None | Low, bounded | Real, bounded, named twice as "the single largest deferred piece" -- but optional |
| Multi-camera Place Feature linking | No (single-camera is the primary "Personal/Home" target per product-doctrine.md) | No | Extends a multi-camera-only edge | None | Low | D -- narrow-audience enrichment |
| Ranked Feature comparison view | Marginally | No | Extends shipped concept | None | Low | D -- enrichment |
| Place Story period summaries | Marginally | No | Extends shipped concept | **Deliberately deferred on a measured performance cost** | **Yes -- named performance risk** | D -- do not rush pre-freeze |
| Dedicated taxon/Feature story page | Marginally | No -- API already supports the filters; UI convenience only | Extends shipped concept | None | Low | D -- enrichment |
| Representative imagery on Story cards | Marginally | No | Extends shipped concept | None | Low | D -- enrichment |
| Environmental historical backfill / wind / cloud | Marginally | No | Extends shipped concept | None | Low | D -- enrichment |
| A consolidated "Explore" page (roadmap.md Layer 6) | No -- the underlying associations are already surfaced inline on Today/Bird Log/Place Report | No -- information architecture, not missing capability | New lane (never started) | None | Low | Considered and rejected -- navigation nicety, not a gap |

**Conclusion: fewer than 3 genuinely belong before release -- none do.**
Every named opportunity is either mechanically impossible right now
(seasonality, blocked on elapsed time), explicitly carries a named
performance risk that argues for *not* rushing it pre-freeze (Story period
summaries), or is enrichment on an already-shipped, already-functioning
concept that a first public user would experience as "less powerful," not
"unfinished." This milestone does not invent product-development work to
keep a development label populated. If the owner later wants a small,
independent, bounded enrichment pass, the environmental-context-on-before
/after composition is the single most substantiated candidate (named as
the largest deferred item in two separate accepted reports, small in
scope, independent of daylight and hardware) -- but it is explicitly not
required, and not recommended as this milestone's one next action (see
below).

## Release-critical validation/readiness

- **Lane R** (Gate A / Complete Field Acceptance): OPEN. Six of eight/nine
  tracked release dimensions are already `READY FOR RELEASE BUDGET`
  (false-Visit rate, fragmentation, duplicates, useful-evidence,
  evidence-survival, monitoring coverage). Recall is decided (`ACCEPTED
  KNOWN LIMITATION`). **True capture-to-visible latency's tail is the sole
  remaining blocker** -- four sized, RTT-normalized cohorts, maxima
  spanning 261.2-865.2 seconds, no fifth qualifying sample yet.
- **Lane L** residual: `rollback()` does not restore an already-changed
  systemd unit template; a narrower directory-swap crash-window gap. Both
  small, disclosed, worked around once in the field, not yet closed
  structurally.
- **Lane E** residual: no live external-overlay-network acceptance has
  ever been possible from this sandbox (needs a real external network this
  environment cannot provide).
- **Lane F** residual: real GPU/CUDA-driver-level concurrent-inference
  measurement and a multi-hour concurrent soak both need real hardware
  this sandbox lacks.
- **External Pre-Release Acceptance (Gate G) itself**: not started, not
  scoped -- see "External Pre-Release readiness criteria," below.

## Pre-release decisions/housekeeping

- **Lane P** LICENSE mechanical adoption (three artifacts: `LICENSE` file;
  `pyproject.toml`/`web/package.json` metadata; `README.md`'s License
  section) -- small, bounded, unblocked by the owner's MIT decision, not
  performed in this milestone by explicit instruction.
- **BirdNET commercial-adjacent legal posture** (§2 of
  `release-execution-state.md`) -- see "BirdNET legal posture," below. No
  engineering action; a genuine legal-review item.
- Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md`/
  `THIRD_PARTY_NOTICES.md` (all three confirmed present on disk this
  session) -- brand/trademark review, website/docs polish -- named in
  roadmap.md's "Public release readiness" as real but explicitly "not
  now."

## After-release queue

Unchanged from `release-execution-state.md` §8 and confirmed still
accurate: complete remote/intermittent-WAN/LTE field deployment;
solar/battery; custom CM4/CM5 hardware; research-grade remote-field
acceptance; broad multi-site; native mobile; advanced acoustic analytics;
mature automatic mammal species identification. Add, from this
reconciliation's own lane-by-lane pass: multi-camera Place Feature
linking, camera-filter UI consolidation, notification-level cross-camera
grouping, Place Story wildlife-event source attribution (Lane F); Web
Push, per-user read/dismiss state, precise per-taxon/Feature deep links,
detector/model-unavailable Observatory Health attention (Lane D); live
OAuth iNaturalist submission, media-byte inclusion, single-Visit deep-link
preselection (Lane J); the low-materiality orphan-media sweep (Lane M,
explicitly not reopened); Land Management/Agriculture (roadmap.md Layer
5, non-primary audience).

## Later/evidence-driven queue

Unchanged from `release-execution-state.md` §9: GenICam, GigE Vision,
USB3 Vision, radiometric thermal, specialized industrial cameras,
individual-animal recognition, population estimates, behavior prediction,
causal ecological modeling, large cloud-first infrastructure. Add:
year-over-year seasonality (blocked on elapsed real history, not
engineering); mature automatic mammal species identification (blocked on
real MockingBird-domain mammal field evidence, still genuinely zero
anywhere in this repository or environment, per the standing record).

## Feature-freeze decision

**C -- MockingBird is functionally at feature freeze already.** Evidence,
not the stale phase label, drives this:

- Every layer of roadmap.md's own "Remaining roadmap -- canonical
  sequence" (Layers 1-8) has substantial, accepted delivery: Layer 1
  (Local Identity) delivered in full; Layer 2 (Environmental Context) v1+v2
  delivered; Layer 3 (Habitat & Phenology) accepted/frozen; Layer 4
  (Biodiversity & Place Intelligence) delivered across four separate
  accepted milestones; Layer 5 (Land Management/Agriculture) correctly
  unstarted for a non-primary audience; Layer 6 (Ecosystem UX Closure)
  substantively delivered inline, with only a navigation-consolidation
  nicety ("Explore" as one page) left, considered and rejected above as
  non-essential; Layer 7 (Mobile/PWA + Calm Notifications) delivered;
  Layer 8 (Remaining product maturity) is cross-cutting/ongoing by design,
  not a discrete gap.
- Every lane A-S in `release-execution-state.md` is CLOSED, MATERIALLY
  CLOSED/ADVANCED/DELIVERED, FROZEN, or DECISION CLOSED, with the sole
  exception of Lane R (true-latency evidence, a validation gap, not a
  product gap) and Lane P's now-small mechanical remainder.
- The Product Opportunity Review above found zero opportunities that clear
  the bar for "substantial product development before release."

What remains is: evidence (Lane R, daylight-dependent), release
readiness/hardening (Lane L's two small residuals; Lane F's
hardware-dependent measurements; Lane E's overlay-network validation),
legal/housekeeping (Lane P mechanical adoption; BirdNET legal review),
disclosed non-blocking defects (Q's test-hygiene/CSS items), and the
eventual External Pre-Release Acceptance / Final Release Hardening
sequence. This is precisely the shape of "near/at feature freeze," not
"still in substantial product development."

## Field-acceptance loop breaker

**Lane R's true-latency tail convergence is WAITING FOR A GENUINE DAYLIGHT
WINDOW.** It is explicitly not scheduled by this milestone, is not the
default next task at night or under unsuitable conditions, and this
milestone does not open another Gate A investigation of any kind. When
daylight conditions are next naturally available, that tranche can resume
on its own authorization, without displacing the higher-value
determination this milestone already made: there is no higher-value
independent product-development milestone it would be displacing, because
none is currently justified (see "Feature-freeze decision," above).

## BirdNET legal posture

Facts kept intact, per this milestone's own instruction: `birdnetlib`
code is Apache-2.0; the BirdNET model weights are CC BY-NC-SA 4.0
(NonCommercial); official MockingBird packages do not redistribute the
weights (durably enforced by
`verify_no_nc_licensed_acoustic_model_redistribution`); external
acquisition of the weights remains optional; the core visual product
functions completely without BirdNET.

**Disposition: B and D together -- not A, not requiring a new C action.**

- **Not A.** It does not block all public launch: "Acoustics may ship as
  the now-accepted optional capability," and core visual MockingBird is
  fully functional without it.
- **B applies.** It blocks (or, more precisely, leaves genuinely
  unresolved) only commercial-adjacent use of the optional acoustic
  feature: "Whether an individual user's own private, non-commercial use
  of MockingBird+BirdNET... could ever be implicated merely because the
  surrounding open-source project also accepts donations or sells
  optional paid support remains genuinely unresolved."
- **C is already substantially satisfied, not newly required.** The
  disablement/disclosure this would call for is already shipped: BirdNET
  is off-by-default, externally/optionally acquired, and both
  `docs/using-mockingbird.md` and `THIRD_PARTY_NOTICES.md` already
  disclose the licensing boundary to an actual product user.
- **D applies for what remains.** "The existing acceptance record
  recommends legal review before any commercial-adjacent distribution
  decision actually touches the acoustic feature, and does not resolve the
  question itself" -- there is no engineering action available now; this
  is a standing legal-review item, to be picked up only if/when a
  commercial-adjacent distribution decision is actually contemplated.

## External Pre-Release readiness criteria

Not yet ready. Concretely blocked on:

1. **Lane R closes** -- the true-latency tail converges (or an explicit
   release-authority decision accepts the current evidence, mirroring how
   recall's own decision was already made).
2. **Lane P's mechanical LICENSE adoption lands** -- an external
   participant should not clone a repository that still says its own
   license "has not yet been finalized."
3. **A cohort plan is actually scoped** -- roadmap.md's own Gate G is
   honest that this is "Not started; no existing doctrine to reconcile":
   who participates, how many, what diversity of real setups, and how
   findings are triaged have never been defined.

Everything else release-critical (Lanes G, L, M, N, O, Q) is already
closed or materially closed with only small, disclosed, non-blocking
residuals -- these do **not** block starting Gate G scoping work in
parallel with #1 above, once #2 is done.

## Final Hardening readiness criteria

Not yet ready, and correctly sequenced strictly after External Pre-Release
Acceptance: "External Pre-Release Acceptance -> Final Release Hardening ->
the one public launch -- no separate beta release precedes it." Even
though this reconciliation finds the intended capability set is now
substantially stable (see "Feature-freeze decision," above) -- the
precondition Lane S's own text names for *starting* Final Hardening --
beginning it before Gate G actually runs would discard real external
findings Final Hardening is supposed to triage. Final Hardening's own
scope, once it starts, is unchanged from Lane S's existing text: defects,
reliability, performance, UX, compatibility, packaging, security,
documentation, installation, upgrade/recovery, field failures, Gate G
findings, release-artifact validation, dependency/license closure,
clean-install repetition, and internal release-candidate builds -- no
major new capability without explicit, concrete necessity.

## Ordered global sequence

```
NOW (no daylight/hardware dependency):
  1. Bounded LICENSE / packaging-metadata mechanical adoption (Lane P) --
     small housekeeping, not a product milestone. Advisory next action,
     not self-authorized by this reconciliation.
  2. (Parallel, human-only, no engineering action) BirdNET
     commercial-adjacent legal review, whenever the owner wants it --
     does not block anything else.
  3. (Optional, small, not required) Lane L's two disclosed rollback/
     systemd-template residuals; Lane E's dense-page progressive
     disclosure -- neither blocks Gate G scoping.

WHEN DAYLIGHT IS NATURALLY AVAILABLE (not scheduled by this milestone):
  - Lane R's one remaining true-latency tranche.

THEN (once Lane R closes and #1 above lands):
  - External (ChatGPT) acceptance review of this reconciliation and of
    Gate A's final closure.
  - Scope and begin External Pre-Release Acceptance (Gate G): define
    cohort size/diversity and a findings-intake process.

THEN:
  - Triage Gate G findings; begin Final Release Hardening.

THEN:
  - The one public launch.

AFTER RELEASE (explicitly deferred, not gating, unchanged from §8/§9):
  Remote/WAN + solar + custom-hardware field productization; broad
  multi-site; native mobile; mature automatic mammal ID; year-over-year
  seasonality; Land Management/Agriculture; every named enrichment item in
  "After-release queue," above; the Later/evidence-driven §9 list.
```

## Recommended next milestone

**No substantial product-development milestone is recommended.** The
Product Opportunity Review found none that clears the bar (see above),
and this reconciliation's overall decision is that MockingBird is
functionally at feature freeze. The one concrete, small, advisory-only
next action available right now, independent of daylight or hardware, is
the bounded **Lane P LICENSE / packaging-metadata mechanical adoption**
named above -- a housekeeping/legal-compliance action, not a product
capability milestone, and not self-authorized here. If the owner instead
wants one small, genuinely optional product enrichment at some point, the
environmental-context-on-before/after composition (named as the largest
deferred item in two separate accepted reports) is the most substantiated
candidate -- but it is explicitly not recommended as required, and this
milestone does not authorize it.

## Decision

**A**
