# One-Release Roadmap & Scheduler Reconciliation v1

Documentation/state-governance milestone. No product, test, or schema code
changed.

## Starting state

- **Branch:** `main`
- **HEAD:** `cff0277` (Reconcile release-execution-state.md: accept Camera
  Node Upgrade & Compatibility Recovery v1)
- **Schema:** `v57`
- **Latest accepted milestone:** Camera Node Upgrade & Compatibility
  Recovery v1, classification **A**; Lane L's Camera Node upgrade gap
  closed.
- **Current authorized milestone (before this instruction):** NONE --
  GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.
- **Worktree:** no other active writer; index/lock files clean; the seven
  preserved untracked detector files present, byte-timestamp-unchanged,
  and untouched by this milestone.
- **Not pushed** (`main` is 214 commits ahead of `origin/main`).

## Problem

`docs/release-execution-state.md` and `docs/roadmap.md` still encoded a
multi-stage, version-numbered release model left over from an earlier
"v0.1 then v1" framing -- `v0.1 CRITICAL` status labels, `post-v0.1 /
before-v1.0` and `first-public-v0.1` section headings, a `v0.1` capability
freeze, and, most substantively, a `roadmap.md` passage that explicitly
permitted the one public release itself to be **described externally as a
beta** ("that is a distribution/expectation-setting label, not reduced
ambition"). That passage, plus a `Gate G -- External Beta Acceptance`
heading, directly contradicted the actual release doctrine: MockingBird
has one public release, not a beta product stage preceding a later "real"
release. A second, smaller problem: an earlier partial reconciliation
(`326207b`, 2026-08-10) had already renamed several `roadmap.md` headings
away from `v0.1` language (`Release gates`, `After-release lanes`,
`Release non-blockers`), but later prose additions cross-referenced those
sections by their old, now-nonexistent names -- three dangling
cross-references (`"v0.1 release gates"`, `"v0.1 non-blockers"`,
`"Post-v0.1 lanes"`) and one to a section (`"v0.1 feature freeze"`) that
had since been merged away entirely.

## Contract

MockingBird is developed toward **one public release**. There is no public
"v0.1" product stage, no beta release product, no separate before-v1.0
roadmap phase, and no deliberately diminished first launch. The first
public availability is the real product launch: polished, trustworthy,
recoverable, understandable, secure, credible, production-minded.

A small external cohort may validate the unreleased product beforehand
(**External Pre-Release Acceptance**) -- private, pre-launch validation,
not a separately released beta product. Internal release-candidate builds
remain allowed as an engineering mechanic during **Final Release
Hardening**, not a separate product stage. Sequencing is unmistakable:
External Pre-Release Acceptance -> Final Release Hardening -> the one
public launch. Final Release Hardening is triggered by capability
stabilizing (a readiness judgment), not by a version-number boundary.

## Changes

**`docs/roadmap.md`** (8 edits, +6 net lines):

- `Gate G -- External Beta Acceptance` -> `Gate G -- External Pre-Release
  Acceptance`; `Beta findings outrank speculative architecture work.` ->
  `Findings outrank speculative architecture work.`
- Replaced the passage permitting the release to be "described externally
  as a beta" with: Gate G is private pre-launch validation, never a
  separately released public beta; its findings feed Final Release
  Hardening (cross-referencing `release-execution-state.md`'s Lane S);
  sequencing is stated explicitly (External Pre-Release Acceptance ->
  Final Release Hardening -> the one public launch); "Release is release"
  is preserved verbatim since `## Public release readiness` quotes it by
  name.
- `a beta/RC acceptance cohort` -> `an external pre-release acceptance
  cohort` in the "Public release readiness" checklist.
- Dropped "first" from four "the first public release" mentions (it
  implies later staged releases) in "Release scope discipline," "Release
  readiness vs. continued capability work," "Public release readiness,"
  and "Remaining product maturity."
- Fixed three cross-references left dangling by the 2026-08-10 heading
  rename: `"v0.1 release gates"` -> `"Release gates"`; `"v0.1
  non-blockers"` -> `"Release non-blockers"`; `"Post-v0.1 lanes"` ->
  `"After-release lanes"`.
- Redirected one dangling pointer, `(see "v0.1 feature freeze," below)`,
  to `"Release readiness vs. continued capability work"` -- the section
  that actually carries that content today (the heading it pointed to no
  longer exists; the historical decision label itself, `v0.1 feature
  freeze now active`, is untouched).

**`docs/release-execution-state.md`** (terminology: 20 edits; structure: 3
additions):

- `External Beta` -> `External Pre-Release Acceptance` (banner); `beta` ->
  `External Pre-Release Acceptance` wherever it named the same gate.
- `v0.1 CRITICAL` -> `RELEASE-CRITICAL` across Lanes G, L, M, N, P, Q, R
  (7 lane-status lines) and one prose instance; `HIGH v0.1 VALUE` -> `HIGH
  RELEASE VALUE` (Lane C); `POST-v0.1 / BEFORE-v1.0` -> `AFTER RELEASE`
  (Lane B).
- `v0.1 scope` / `v0.1 requirement` / `v0.1 blocker(s)` / `first-public-
  v0.1 blocker` / `v0.1-CRITICAL blocking` -> `release scope` / `release
  requirement` / `release blocker(s)` / `release-critical blocking`
  (8 instances across Lanes B, F, L(closing text), P, R, S, §§7-8, §16).
- `remaining-v0.1 queue` -> `remaining release queue` (§3).
- `## 7. First-public-v0.1 doctrine` -> `## 7. One-release doctrine`; `The
  first public release target` -> `MockingBird's public release target`.
- `## 8. Post-v0.1 / before-v1.0 queue` -> `## 8. After-release queue`.
- Lane S (`Actual Final Release Hardening`) rewritten in full: "Only after
  intended v0.1 capability scope stabilizes. Then freeze major features
  ... beta; release candidate; public OSS release" became a
  readiness-triggered sequence naming release-critical-outranks-optional-
  capability, the External Pre-Release Acceptance -> Final Release
  Hardening -> public launch order, and internal release-candidate builds
  as "an engineering mechanic, not a separate product stage" -- implements
  the roadmap instruction's §12/§14 feature-freeze and ordering doctrine
  directly, cross-referencing `roadmap.md`'s already-correct "Release
  readiness vs. continued capability work."
- Added a "Four release-shape categories" navigational index at the top of
  §6 mapping the existing lettered lanes (A-S) onto Release-critical /
  Pre-release decisions / After release / Later-evidence-driven, per this
  milestone's brief §8 -- explicitly a summary over the existing lanes,
  not a new or renumbered lane system.
- §1 and §3 bookkeeping updated to accept this milestone (see "Git /
  scheduler closure," below).

**`docs/product-doctrine.md`**: read in full, zero stale-term hits found.
Left unedited -- it already frames the release as the real product launch,
creates no beta/v0.1 product stage, and only cross-references `roadmap.md`
generically for "the current release gates." No genuine contradiction to
fix.

## Preserved history

Left verbatim, as historical record rather than current doctrine:

- Proper-noun milestone titles containing `v0.1`: **v0.1 Product Flow Gap
  Pass v1**, **v0.1 Observational Quality Closure v1**, **v0.1
  Acquisition/Ingest Interoperability Closure v1** (`roadmap.md`), and
  their filename (`v01-product-flow-gap-pass-v1-findings.md`) and prose
  reference to **v0.1 Release Hardening v1** -- real milestones named that
  way at the time; renaming or unlinking them would falsify the record.
- The 2026-08-22 dated narrative bullet describing Detection & Species
  Model Benchmark / Promotion v1 as "the deliberately-last pre-v0.1
  capability milestone" and its **Decision: D -- ... v0.1 feature freeze
  now active** label -- a real decision made and named that way at the
  time. Only its dangling cross-reference was fixed (see Changes, above);
  the decision label itself is untouched.
- The 2026-08-22 "2026-08-22 partial closure" bullet under Species
  Classification Re-evaluation / Promotion v2, explaining a scheduling
  choice "since v0.1 feature freeze made this the last opportunity" --
  historical reasoning, left untouched (no dangling reference attached).
- `roadmap.md`'s own already-existing "This reconciliation formally
  retires the version-named feature freeze..." paragraph (from the
  2026-08-10 `326207b` reconciliation) -- already-correct current prose,
  not touched.
- Two other repository docs (`detection-species-model-benchmark-
  promotion-v1-report.md`, `multimodal-observation-soundscape-v1-
  contract.md`) still contain `v0.1`/`feature freeze` language. Both are
  historical milestone reports/contracts, not one of the three governing
  documents named in this milestone's brief; left untouched per the
  brief's bounded-search instruction.

## Roadmap preservation

No lane, gate, or roadmap capability was removed, added, or promoted.
Confirmed directly: `release-execution-state.md`'s Lane A-S list is
unchanged in count, order, and lettering (verified by heading diff); every
lane named in the governing brief's Release-critical/Pre-release-
decisions/After-release/Later-evidence-driven lists (§8) already existed
in the scheduler before this pass and is only re-indexed, never relocated,
by the new §6 summary. `roadmap.md`'s "After-release lanes," "Release
non-blockers," and "Remaining roadmap -- canonical sequence" sections are
untouched in content (only the two dangling cross-references into them
were fixed). No deferred item (remote/LTE, solar/battery, custom CM4/CM5,
broad multi-site, native mobile, advanced acoustic analytics, mature
mammal ID, GenICam/GigE/USB3 Vision, individual-animal recognition,
population estimates, behavior prediction, causal ecological modeling,
large cloud/fleet infrastructure) was promoted into release scope merely
because its version-numbered bucket name changed.

## Remaining terminology hits

Post-edit `grep -inE 'v0\.1|beta|\bRC\b|release candidate|first public
release|pre-v0\.1|post-v0\.1|before-v1\.0|feature freeze|public
launch|external acceptance'` against both files:

| File | Hits | Category |
|---|---|---|
| `roadmap.md` | 8 | Historical (proper-noun titles/filenames/dated decision narration) -- preserved verbatim |
| `roadmap.md` | 1 | Already-correct current prose ("formally retires the version-named feature freeze") -- no change needed |
| `roadmap.md` | 3 | This milestone's own new Gate G doctrine text (correctly stating what is *not* a beta) |
| `release-execution-state.md` | 21 | This milestone's own new/rewritten doctrine text (§1, §3, §6 additions; rewritten Lane S) -- all describing the corrected doctrine, none stale |

Every remaining hit was individually read in context (not pattern-matched
blind) before classification; none is genuine governing language still
needing correction.

## Validation

- `grep -inE` sweep above, before and after editing, both files: went from
  27 (`release-execution-state.md`) / 24 (`roadmap.md`) stale/mixed hits
  to 0 unclassified hits.
- Manual context read of all 51 original hits (see the two docs' own
  earlier grep passes in-session) before writing any edit.
- `git diff --check`: clean, no whitespace errors.
- Heading-structure diff (`grep -n '^#'` before/after): `release-
  execution-state.md` sections `## 1`-`## 16` and lanes `### A`-`### S`
  intact, same count, same order; `roadmap.md`'s 59 headings intact, same
  count, same order (only in-place text renames, e.g. `Gate G`).
- No markdown anchor-style links (`](#...)`) exist in either file, so
  heading-text renames (`§7`, `§8`, `Gate G`) cannot break an internal
  link; confirmed by grep before renaming.
- No Core run: documentation-only change, per this milestone's own
  non-goals.

## Decision

**A.** The governing release doctrine is coherently reconciled across
`docs/release-execution-state.md` and `docs/roadmap.md` with no scope
loss, no history falsified, and no next milestone selected.

## Git / scheduler closure

- Accepted HEAD becomes this reconciliation's own commit (documentation-
  only; the last code-bearing commit remains `be84074`, cited unchanged in
  `release-execution-state.md` §1 -- see that file for why a
  self-referential hash is not written there).
- Schema remains `v57`.
- Latest accepted milestone: **One-Release Roadmap & Scheduler
  Reconciliation v1**, classification **A**.
- Current authorized milestone: unchanged -- **NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED**. This milestone satisfies the
  reconciliation that phrase called for; it does not itself authorize any
  next implementation milestone.
- Single commit (no manufactured two-commit pattern), following this
  repository's own precedent for pure documentation/governance passes
  (e.g. `326207b`, `c5278cb`).
- Not pushed.
