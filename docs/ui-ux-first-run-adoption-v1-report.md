# UI/UX & First-Run Adoption v1 -- closure report

Comprehensive pre-release product-experience milestone. Two stages: a
complete, evidence-backed experience audit of the running product (Stage
A), then implementation of every P0/P1 defect it found plus bounded P2
polish (Stage B).

Governing context read first, in order:
[release-execution-state.md](release-execution-state.md),
[product-doctrine.md](product-doctrine.md), [roadmap.md](roadmap.md), and
the four most recent accepted hardening reports
([pre-release-trust-correctness-correction-v1-report.md](pre-release-trust-correctness-correction-v1-report.md),
[native-windows-packaging-acceptance-v1-report.md](native-windows-packaging-acceptance-v1-report.md),
[review-queue-count-truth-consistency-v1-report.md](review-queue-count-truth-consistency-v1-report.md),
[analytics-local-data-truth-consistency-v1-report.md](analytics-local-data-truth-consistency-v1-report.md)).

## A. Starting baseline

Verified directly before any edit: branch `main`; HEAD `456277f`; schema
`v59`; version `0.1.0`; working tree clean except the seven preserved
untracked detector files (§13) and `uv.lock`, all confirmed present and
byte-identical (SHA-256 recorded at session start and re-verified before
every commit). Latest accepted milestone: Analytics & Local Data Truth
Consistency v1.

## B. Writer safety / collision status

No repository locking mechanism exists; §13's single-writer rule is
enforced by inspection. Three independent checks before the first write:
every peer MockingBird session reported `idle` or `offline`; every
recent working-tree mtime predated the accepted HEAD commit (12:46,
checked at 13:18); the tree itself was clean. This session then recorded
an explicit claim in an untracked `.git/MOCKINGBIRD_ACTIVE_WRITER` marker
(inside `.git/`, so never part of the working tree and never committed)
naming the milestone, session, start time and baseline HEAD, and
re-verified before each commit boundary that every changed file was its
own. **No collision occurred.** Two long-lived shell wait-loops belonging
to an older session's scratchpad were observed polling `pgrep`; they are
not writers and touched nothing.

## C. Routes / screens audited

All 28 user-reachable routes plus the 5-step first-run wizard, against
two real running instances (a genuinely fresh install and a populated
one), at 1366px, 820px and 390px, with console/HTTP error capture,
horizontal-overflow measurement and structural accessibility facts per
route: `/`, `/cameras`, `/cameras/setup`, `/cameras/:id/edit`, `/import`,
`/folder-import`, `/review`, `/bird-log`, `/activity`, `/analytics`,
`/place-report`, `/place-report/compare`, `/place-story`,
`/ecological-destinations`, `/local-data`, `/users`, `/doctor`,
`/yard-map`, `/exports`, `/retention`, `/evidence`, `/proposals`,
`/analyzers`, `/species-suggestions`, `/classifier-readiness`,
`/classifier-manifest`, `/alerts`, `/collections`, `/worker-status`,
`/streams/:id`, `/events/:id`, `/visits/:id`.

## D. First-run journey, before and after

**Before.** Welcome named no concept (Host, Camera Node and Place were
undefined; hardware requirements unstated; nothing said what is optional
or what happens if you do nothing). The account step asked for a "Login
identity" on "this Host". The camera step stacked three headings, offered
"MockingBird Camera Node" as the default with a pairing code said to be
"shown on the Node's own console", listed seven unavailable providers as
disabled "-- unavailable" entries, rendered raw inline label+control
pairs ("Camera type[select]"), showed a raw `feeder` enum, and told the
user to start observing from a "Stream page / Observation panel" that the
next wizard step actually embeds. A user without camera hardware had no
signposted path. Skipping setup landed on a Today page whose first real
wildlife content was below three optional Place prompts and a status
panel -- and which claimed "Kinds of wildlife known here: 1" from seeded
demo data.

**After.** Welcome defines Host, Camera Node and Place in three lines,
states what hardware is needed (including "no camera at all -- import
photos or video"), says what stays off until asked for, and says what
happens if setup is skipped. The account step asks for a "Username" on
"this computer". The camera step shows one heading, a "What you'll need"
panel with an "Import photos instead" escape hatch, styled stacked form
controls, only available providers, "Feeder" rather than `feeder`, plain
pairing instructions pointing at the Camera Node install guide, and
honest "finishing never starts watching by itself" copy that matches the
next step. Today leads with real wildlife, states what to expect while
waiting, and no longer reports demo data as this Place's history.

## E. P0 / P1 / P2 / P3 inventory

Built from four parallel read-only audits (onboarding/time-to-value/
Camera Node; wildlife discovery/review/imagery; analytics/settings/
optional features; navigation/terminology/visual/responsive/accessibility/
errors), each evidence-backed against rendered output and source, then
de-duplicated. Labels apply only inside this milestone.

### P0 -- release blockers (4, all fixed)

1. **Demo data presented as real Place history, and exported as research
   truth.** A fresh install reported "Kinds of wildlife known here: 1"
   on Today and Place Report, named the seeded demo squirrel as Place
   Story's first recorded species, listed demo Visits in Activity
   Library, and -- most seriously -- treated that fabricated Visit as an
   eligible record in Darwin Core, Camtrap DP, iNaturalist eligibility
   and reviewed dataset exports.
2. **Import dead end.** On a fresh install the only Stream belongs to the
   demo Source, so Import Media defaulted to it; media imported there is
   (correctly) hidden by every review and history surface, making the
   no-camera path silently useless.
3. **Review Queue dead end.** The queue always opened on "Animals"; a
   user whose only waiting item sat under another group saw "No review
   items match these filters", and the offered "Reset filters" never
   changed the group. Today simultaneously said "All caught up".
4. **Add Camera assumes hardware and developer knowledge** (see D).

### P1 -- must fix before v0.1 (16, all fixed)

Welcome/account concept gaps; wizard heading stack and contradictory
"start watching" copy; Add Camera absent from the Cameras page header;
no statement of what to expect after starting to observe; Import page
jargon; Add Camera clipped at phone width; Today burying wildlife under
setup prompts, plus a review-backlog line contradicted by the Review
Queue and demo-inclusive camera counts; flat 13-item nav labelled
"Product loop", a "Current context -> Stream Detail" entry present before
any camera was opened, no `aria-current`, no skip link, and a hidden
mobile drawer that stayed in the tab order; Visit detail showing a model
guess and a confirmed identification identically, a correction box
silently prefilled with the model's guess, two unexplained confidence
numbers, a run-together header line, and the correction form below
notes/collections/tags; Review Queue header and control jargon
("Dataset-grade truth", "Product Mode", "Legacy activity", "reviewed
target"); Insights contradicting itself (range-scoped panels above
all-time totals) and mixing dataset-readiness material into the nature
page; Local Data asserting imported media "is not analyzed ... in this
phase" (false) and offering a "Not enabled" remote-access row with no way
to act; Doctor reporting "Everything MockingBird needs to observe
wildlife is working" on an install with nothing set up; the Alerts
popover not closing on Escape or outside click; backend-down and
failed-load states leaking "[object Object]", raw "Internal Server
Error", "Failed to fetch" and an empty "API base:"; an unlabelled role
`<select>` on Users.

### P2 -- bounded polish (fixed)

Literal `--` in user-facing copy across 25 components/pages and two
backend messages; Place Report printing an exclusive period end as an
inclusive date; 1.31:1 brand-mark contrast; `aria-pressed` on review
filter tabs; no `prefers-reduced-motion` handling; Change password
stranding focus and ignoring Escape; disabled buttons showing
`cursor: wait`; Bird Log copy ("Order labels by", "1 Stream / 1 Zone",
bird-only framing of a wildlife log); raw `feeder` and "Feeder (Feeder)";
`true`/`false` and raw retention enums; `/worker-status` reachable
without Developer Mode; Users table clipped at phone width;
`.text-action` visually identical to `.secondary-action`; Local Data
opening with database telemetry; taxonomy quick picks inserting internal
ids; Activity Library filter jargon.

### P3 -- recorded, not done

CSS token consolidation (310 distinct hex values, 2 `var()` uses) and
`evidence-badge-*`/`status-*` de-duplication; Yard Map promotion to
primary navigation; a confirm-new-password field; placeholder aspect
ratio reserved for missing evidence images; Fast Review's "C" shortcut
semantics (it saves a generic `bird` label and discards the species
suggestion, which reviewers may read as "confirm the suggestion"; its
keyboard contract is locked by an accepted e2e spec, so this milestone
recorded it rather than re-binding or relabelling it); a live Camera Node offline/reconnect UX
pass (needs real hardware); `"..."`/`"…"` consistency in loading strings.

## F. Navigation / information architecture

Primary navigation regrouped under plain headings that follow the product
loop without renaming any route or data model: Today; **Observe**
(Cameras, Import Media); **Wildlife** (Review Queue, Bird Log, Activity
Library); **Your place** (Place Story, Place Report, Insights, Ecological
Destinations); **Settings & help** (Local Data, Users, Doctor, Developer
Mode). The former "Current context" block became "Recently opened" and
lists only what the user actually opened (it previously showed "Stream
Detail" on a fresh install, resolved from a fallback to the first -- demo
-- Stream), naming the camera directly. Added a skip link and
`aria-current="page"`; `/worker-status` is now Developer-Mode gated.

## G. Terminology

Classified every product term against the four required classes. Acted
on: "Cameras / Streams" unified to **Cameras** (h1, nav, buttons and the
Model Adapters link); "Login identity" -> **Username** (4 UI sites, 6
spec assertions); "Legacy activity" -> "Sample and older activity";
"Order labels by" -> "Sort by"; "Stream"/"All Streams" -> "Camera"/"All
cameras" in import and library pickers; "N Stream / N Zone" -> "Seen on N
cameras / N areas"; "Product Mode" -> "What needs a look";
"Dataset-grade truth" -> "Confirm what visited"; zone editing "Available
nearby" -> "Can be drawn for this camera". Host/Camera Node/Place are
kept as canonical terms and now explained in plain language at first
contact rather than renamed. Internal vocabulary (Source, Event,
Detection Proposal, Model Adapter, Candidate pack) stays in developer
surfaces.

## H. Dashboard (Today)

Recent wildlife activity moved above the optional Place prompts and the
status panel; the three Place-detail prompts are grouped under one
labelled, explicitly optional "About your place" section; hero actions
reduced and ordered by what the install actually needs (Add Camera when
no real camera exists, otherwise Cameras); "Local app connected" ->
"Running on this device"; the review line no longer claims "All caught
up" when older visits are waiting; camera counts use the demo-excluded
`real_stream_count`, so a fresh install says "MockingBird is ready to
watch this place" instead of "Start observing on your camera".

## I. Observation / wildlife discovery

Visit detail now distinguishes Measured, Inferred and Reviewed at a
glance: a model guess renders as "Likely X" with a "MockingBird's guess"
badge, a confirmed identification as the name with "You confirmed this";
the detector's number is labelled "How sure the detector was it saw an
animal"; the header context line has real spacing and no longer repeats a
zone's type when it matches its name. Bird Log is framed as confirmed
wildlife (not birds only) with plain facts. Activity Library filters and
description are in ordinary language.

## J. Review / correction

The queue opens on the first group that actually has work (until the user
picks a group), "Reset filters" restores that choice, and the two
distinct empty states are honest: "All caught up" versus "Nothing waiting
in this group -- N waiting in Unchecked" with a button that goes there.
The header states the truth contract plainly ("What you confirm becomes
your trusted record ... later model runs can suggest, but never overwrite
it"). On Visit detail the correction form follows the evidence and the
optional identification assistant instead of sitting below notes,
collections and tags, and a prefilled box says it came from MockingBird's
own guess and can be changed or cleared.

## K. Analytics / Local Data / Yard Map

No accepted truth contract changed. Insights labels its all-time totals
as all-time (removing the apparent self-contradiction with its
range-scoped panels), renames metric cards into ordinary language, and
collapses dataset/model-readiness material under "Dataset readiness (for
exports and model work)". Local Data now opens with connection/privacy,
storage and backup, with the eleven raw count cards and database facts
moved into a collapsed "What's stored here, in detail" that discloses
they include the sample camera.

## L. Camera Node experience

"What you'll need" names a Camera Node as "a small networked camera
device -- a Raspberry Pi with a camera is the reference design",
alongside IP/ONVIF/RTSP cameras, USB webcams and the no-camera import
path; Raspberry Pi is never presented as the product. Pairing copy says
where the code actually comes from and points at the install guide.
Unavailable future providers are no longer listed as broken options.

## M. Settings / account / privacy

Remote access is no longer a dead end: the "Not enabled" row now states
exactly how to enable network access on Windows and Linux/macOS, keeping
the existing sign-in and plain-HTTP warnings. Dangerous actions (reset
demo data, shut down, restore) keep their confirm-then-act pattern and
remain at the bottom, now clearly separated from everyday settings by the
collapsed technical block. Change password takes focus when opened,
closes on Escape and returns focus to its trigger.

## N. Empty, loading and error states

Fresh-install states for Today, Review Queue, Bird Log, Activity Library,
Insights, Local Data, Yard Map, Exports, Collections, Alerts, Place Story
and Place Report were each inspected against the four questions (what is
this, why is it empty, is something wrong, what next). Rewritten where
they failed: Review Queue's "Nothing to review yet" (previously pointing
at Dataset Exports), Today's "No visits yet", Import's "First, choose
where imported media goes" with one-click setup. Loading panels carry
`role="status"`. Error copy tells the user what to do; validation and
network failures no longer surface raw internals.

## O. Visual system

Consolidated fixes rather than a redesign: a legible brand mark (contrast
was 1.31:1), a genuine third button tier, `cursor: not-allowed` for
disabled controls, stacked/styled form controls for the setup steps via
one reusable `source-setup-form` class, spacing for the visit context
line, and a `min-width: 0` fix for the grid/flex chain that let one wide
control stretch a whole page past a phone viewport. No design-system
rewrite; P3 records the token consolidation that remains.

## P. Wildlife imagery

Evidence and thumbnail presentation were judged with media deliberately
absent (the seeded demo Visits carry no files), so the finding is about
placeholder treatment, not image size: placeholders read honestly
("Evidence unavailable", "No saved thumbnail"). Reserving the viewer's
aspect ratio for missing media is recorded as P3. Real-image sizing on
Visit detail and the evidence gallery was left as accepted work from
Working App v1 and Same-Frame Species Evidence v1.

## Q. Responsive behaviour

Every audited route now measures zero horizontally overflowing elements
at 390px and 820px (the Add Camera page previously rendered 401px wide
inside a 390px viewport and clipped its own right edge). The Users table
keeps its intentional horizontal scroll and now says so at narrow widths.
Review filter tabs meet a 44px target on phones. Native mobile remains
out of scope.

## R. Accessibility

Fixed: skip link to `<main>`; `aria-current="page"` on primary and mobile
navigation; the closed mobile drawer no longer keeps ~15 buttons in the
tab order; Escape and outside-click close the Alerts popover; Change
password focus management; `aria-pressed` on review filter tabs and
taxonomy quick picks; an accessible name for the Users role select;
`prefers-reduced-motion` honoured globally; `role="status"` on loading
panels. Contrast was measured, not assumed: the brand mark was the one
real failure and is fixed; sidebar secondary text (7.99:1), meta text
(4.99:1), status pills (5.4-7.8:1) and text actions (5.91:1) already
passed. Certification-level conformance was not attempted.

## S. Copy / trust

Developer vocabulary, robotic phrasing and overconfident wording were
rewritten across the product, and two false statements were corrected
(Local Data's "not analyzed or transcoded in this phase"; Doctor's
"Everything MockingBird needs to observe wildlife is working" on an
unconfigured install). Backend-provided user-facing strings were included
where they were the source of the problem ("No durable monitoring
exposure has been recorded ... so coverage is withheld" -> "No camera has
spent time observing yet ..."; the biodiversity warning; Doctor's
"1 configured Stream(s)"). No marketing language was added; Local Only
claims were kept precise and verified against what the code actually
does.

## T. First-run acceptance result

Walked on a genuinely fresh instance (own database and media root,
administrator created through the real wizard), as a user with no camera
hardware. All twelve required abilities pass:

1. **Launch** -- first run opens the guided wizard, not a blank console.
2. **Understand what it is** -- "What MockingBird does" states the purpose
   in two sentences, above three local-first promises.
3. **Understand Local Only** -- "Your video and data stay on this device",
   "Nothing is uploaded or shared automatically", with the optional extras
   (sound, weather, phone access) named as off until enabled.
4. **Understand Host / Camera Node / Place** -- defined in the welcome
   step; Camera Node names Raspberry Pi as the reference design, not the
   product.
5. **Connect or add a source** -- Add Camera lists only available camera
   types and offers "Import photos instead"; Import Media sets up a real
   import source in one click.
6. **Recognise it is working** -- the observe step says what to expect
   ("a visit usually appears in Today within a few minutes ... a quiet
   hour is normal, not a failure").
7. **Reach wildlife observations** -- the imported visit appeared in
   Today's Recent activity and in the Review Queue.
8. **Tell inference from reviewed truth** -- the unreviewed visit read
   "Likely Northern Cardinal / MockingBird's guess"; the correction panel
   says the prefill is MockingBird's own guess and can be changed.
9. **Confirm or correct** -- "Confirm species" saved; the queue went to
   zero.
10. **Find it again** -- the confirmation appears in Bird Log and Insights.
11. **Understand important errors** -- backend-down, failed load and
    validation errors now say what happened and what to do.
12. **Know where to look for help** -- Doctor is in Settings & help and is
    honest about what is not yet set up.

## U. Observe -> Discover -> Understand -> Confirm -> Remember -> Improve

Each transition was exercised in one continuous scripted session against
the fresh instance (screenshots and captured page text retained in the
session scratchpad, not committed):

- **Observe.** `/import` showed "First, choose where imported media goes";
  one click created a real `manual_media` source; a photo imported and
  returned "Imported. A new visit is waiting for you to confirm what it
  shows."
- **Discover.** Today listed the new visit under Recent activity and
  offered "1 item worth reviewing".
- **Understand.** The Review Queue showed the waiting item with evidence
  and honest evidence-class wording; Visit detail distinguished guess from
  confirmation.
- **Confirm.** "Confirm species" saved a correction; `GET
  /api/review-queue` then returned zero items.
- **Remember.** Bird Log listed Northern Cardinal as confirmed wildlife.
- **Improve.** Insights counted it among confirmed species, and Today
  moved to "All caught up -- nothing waiting on you". The biodiversity
  card correctly still says no camera has spent time observing yet (an
  import carries no monitoring exposure) rather than inventing a baseline.

## V. Tier 1 validation

`tests/test_demo_source_exclusion.py`: 7 new tests (36 total, all
passing), each proving one surface on a genuinely fresh, demo-seeded
database -- biodiversity summary, Place Story, Place Activity Report,
Activity Library, reviewed dataset export, research/ecological export
scope -- plus a positive control proving a repurposed (real) Source's
history still counts. Proven RED against the unmodified baseline: 6 of
the 7 failed before the fix and pass after; the positive control passes
both ways, which is what makes it a control.

## W. Tier 2 validation

Affected backend subsystems: 51 test files run together (place
report/story/biodiversity/change/year-over-year/historical baseline,
research and ecological export, Darwin Core, Camtrap DP, dataset export,
activity library, Bird Log, dashboard, taxonomy, zone insights, API and
persistence). One sweep found 33 failures in 5 files; every one was a
fixture using the seeded demo Source as convenient plumbing for
research/ecological/activity-library scope, corrected with the
established `tests/conftest.py::de_demo_seeded_source` mechanism (no
assertion weakened). Those 5 files then passed 55/55. Doctor: 121 passed.
Place biodiversity: 43 passed. `tsc --noEmit`: clean throughout.
`ruff check src/mockingbird/repository/product_repository.py`: 55
findings, byte-identical to its established baseline.

## X. e2e / browser validation

The audit itself was browser-driven: 28 routes at three widths on two
real instances, plus targeted flows. Suites:

- **Onboarding suite** (own fresh instance): 6/6 passed.
- **Shared suite:** 181 passed / 10 failed on the first complete run. To
  classify those rigorously rather than assume, the accepted baseline
  (`456277f`) was cloned, built and run through the identical suite: it
  fails **9** of the same specs (all order/accumulation-sensitive against
  the suite's one shared instance -- e.g. a spec expecting exactly 1 queue
  card receives 19 after earlier specs have seeded their own). The single
  difference was `analytics-local-data-truth-consistency.spec.ts`, which
  pinned a metric label this milestone renamed; the label is now
  consistent across Insights and Local Data, the spec was updated, and it
  passes. **Net attributable e2e regressions: zero.**
- **Keyboard/accessibility checks** (scripted, real browser): skip link is
  the first tab stop and moves focus to `<main>`; navigation order is
  sensible with no invisible stops; review filter tabs are operable by
  keyboard and expose `aria-pressed`; Change password takes focus and
  Escape returns focus to its trigger; the Alerts popover closes on Escape
  and restores focus; Visit detail reaches "Confirm species" from the
  correction field in 8 tab stops.
- **Overflow measurement:** every audited route reports zero horizontally
  overflowing elements at 390px and 820px.

## Z-1. Disclosed process defect: three protected files were staged

**What happened.** This milestone's first implementation commit
(`3f6a49c`) was created with `git add -A src tests`, which swept in three
of the seven preserved untracked detector files that §13 of
[release-execution-state.md](release-execution-state.md) requires to stay
untouched and unstaged:

- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

**What was not affected.** Their *content* was never modified: the
SHA-256 of all seven files, recorded at session start, was re-verified
after every commit and matches byte for byte (independent copies were
also taken and compared). The other four preserved files were never
staged. Nothing was pushed.

**Why it is not repaired here.** Both available remedies -- rewriting the
unpushed local history to exclude those paths, and `git rm --cached` to
return them to untracked state with identical content on disk -- are
classified as destructive git operations and were refused by this
session's environment. Repairing this therefore needs an explicit
decision by the owner rather than a silent workaround. Until then the
three files are *tracked* in local history from `3f6a49c` onward, with
unchanged content.

**Recommended repair** (owner's choice, nothing pushed):
`git rm --cached` those three paths and commit, which restores them to
untracked immediately; or, for a clean history, rewrite `f050c88..HEAD`
excluding those paths.

**Process lesson, recorded so it does not recur:** in this repository
`git add -A <dir>` is unsafe -- the preserved files live inside `src/`
and `tests/`. Stage explicit paths, or `git add -u` for tracked files
only.

## AA. Remaining concrete v0.1 blockers

Nothing found in this milestone is left unfixed as a release blocker. Two
items carried forward from earlier milestones remain open and belong to
their own lanes, unchanged by this work:

1. A live, fresh **Camera Node pairing proof** against the shared
   reference Pi (Native-Windows & Packaging Acceptance v1's one incomplete
   real-hardware proof; Lane G / Lane R).
2. The **Doctor media-integrity relative-path** behaviour recorded in
   earlier audit notes, outside this milestone's scope.

Plus this milestone's own disclosed process defect (§Z-1): three
preserved untracked detector files are tracked in local history from
`3f6a49c`, content unchanged, awaiting the owner's decision on the
repair, because both repairs are destructive git operations this session
was not permitted to perform.

P3 items recorded in §E are deliberately deferred, not blockers.

## AB. Advisory next step (advisory only)

A performance/scale/stability pass is the natural next milestone: this
milestone deliberately avoided optimisation work, and its own audit noted
no performance regressions but did not measure large-history behaviour.
Sequencing authority remains external; this milestone does not authorise
itself or any successor.

## Y. Tier 3 -- full Core

Run twice, because the first run earned a second.

**First run: 12 failed / 6117 passed / 4 skipped / 11 xfailed (45m15s).**
Four matched the established pre-existing set
(`test_doctor_camera_node_transport`'s own pair,
`test_environmental_context`,
`test_place_change_summary_repository`). The other eight were real
fallout from this milestone's demo-exclusion work, in files the Tier 2
sweep never reached: `test_api` (Local Data's note copy),
`test_visit_tags`, `test_visit_collections`, `test_visit_organization`,
`test_high_resolution_evidence`, `test_local_only_privacy`,
`test_megadetector_adapter`, `test_review_decision_provenance` -- every
one of them using the seeded demo Source/Visit as convenient plumbing for
Activity Library search, dataset export, or research/ecological scope.
This is exactly the case Tier 3 exists for. All eight were corrected with
the same established `de_demo_seeded_source` mechanism (no assertion
weakened), and `test_api`'s assertion was pointed at the corrected Local
Data copy -- which also exposed, and fixed, a literal `--` this milestone
had itself introduced into that backend string.

**Second, confirming run: 5 failed / 6124 passed / 4 skipped / 11
xfailed (42m29s).** Four are the identical established pre-existing set.
The fifth,
`test_camera_node_transport_acceptance.py::test_scenario_1_ordinary_
disconnect_reconnect`, is a timing-sensitive acceptance test (it binds a
free port, starts a worker, and waits on 5-second deadlines); it passes
standalone in this tree **and** in the baseline clone, touches no
demo/export path, and failed only because browser suites were running
concurrently with Core against this machine -- a scheduling error on this
session's part, against this repository's own "do not run e2e and Core
concurrently" guidance, not a product regression.

**Zero Core failures attributable to this milestone's product changes.**

## Z. Final state

- **Branch/HEAD:** `main`, this report's own commit (implementation
  commits `3f6a49c`, `f2a8f83`, `d145a20`, `fc0ff49`, `7048ede`,
  `2c26d66`, `05146c7`, after the baseline reconciliation `f050c88`).
- **Schema:** `v59`, unchanged. **Version:** `0.1.0`, unchanged.
- **Working tree:** clean apart from the preserved untracked files and
  `uv.lock`; all eight protected files byte-identical to their
  session-start SHA-256, re-verified at close -- but see §Z-1: three of
  them are tracked in local history and await the owner's repair
  decision.
- **Push status:** **not pushed.**
- **Out of scope and untouched:** detector/model selection, MDv5a
  threshold, BioCLIP, SpeciesNet, BirdNET decisions, new wildlife
  capability, native mobile, multi-site, LTE/solar, custom hardware,
  storage/database architecture, broad performance work, Gate G.
