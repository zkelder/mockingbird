# Lane C Sparse-State Honesty & First-Hour Narrative Closure v1

## Starting state

Verified before any change: branch `main`, HEAD `02f047f` (Reconcile
release-execution-state.md: accept Ongoing Monitoring Failure Diagnostics
for RTSP / Local USB / Windows DShow v1), schema `v58`
(`CURRENT_DATABASE_SCHEMA_VERSION`, `src/mockingbird/storage/database.py`),
latest accepted milestone Ongoing Monitoring Failure Diagnostics for RTSP /
Local USB / Windows DShow v1, Lane G `MATERIALLY CLOSED / VALIDATION
REMAINS` (`docs/release-execution-state.md` §6.G), Lane R/Gate A `NOT DONE
-- RELEASE-CRITICAL` (open, §6.R), current authorization `NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED` (§3), local `main` 253 commits
ahead of `origin/main` (not pushed). All matched.

The one discrepancy: §6.C ("Everyday Product / Discovery UX") still carried
its original nine-item `PARTIAL` remaining-work prose, not the "materially
delivered with two bounded DEV gaps" framing this milestone's own governing
brief supplied. Cross-checked rather than treated as a stop-and-report
mismatch: every one of the seven items the brief names as delivered has a
real, already-accepted milestone behind it (Best Moments/report-first
hierarchy and calm daily summary via the Gate C Daily Place Report and Calm
Daily Digest milestones; New/Regular presentation via Gate C Historical
Baseline Maturity and Historical Species-Status Correctness v1;
understandable suggestion explanations via Same-Frame Species Evidence and
Visit Classifier Evidence Visibility; mostly-invisible review via the
review-optional design and Whole-Product UI Closure's Review Queue fix) --
§6.C's own prose was simply never reconciled as each landed piecemeal under
Gate C naming rather than explicit "Lane C" naming. Reconciling that text
is this milestone's own closing step (see "Lane C final disposition,"
below), not a precondition for starting it.

Worktree safety: the seven preserved untracked files
(`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`) were present, untracked, and
confirmed untouched throughout (`git status` unchanged before/after; still
`??` at the end, never staged/edited/deleted). No active writer was found
modifying this worktree: `git status` was byte-identical across a 3-second
window, no `.git/index.lock`, and no file under the repository had an
mtime inside the preceding 10 minutes. The numerous `ccd-cli` processes
sharing this directory as `cwd` are this session's own remote-CLI process
tree, not independent concurrent editors -- `mockingbird-active` is the
one canonical checkout, distinct from the many other `mockingbird-*`
sibling directories used by other milestones/sessions.

## Lane C accepted baseline

Per the governing brief's own accepted read-only Lane C reconciliation
(§4): **delivered/accepted** -- Best Moments, calm daily summary, New /
Regular presentation, unknown/unresolved handling, understandable
suggestion explanations, mostly-invisible review, report-first hierarchy.
**Partial, bounded DEV remaining** -- (1) sparse/no-wildlife honesty under
primary detector/GPU/model failure; (2) coherent first-hour narrative in
onboarding. Neither of the seven delivered items was reopened, touched, or
re-litigated by this milestone.

## Detector-health RED

New `tests/test_dashboard_detector_health_honesty.py`, run against the
real, unmodified pre-fix code:

```
tests/test_dashboard_detector_health_honesty.py::test_dashboard_flags_detector_unavailable_while_camera_stays_healthy FAILED
tests/test_dashboard_detector_health_honesty.py::test_dashboard_healthy_detector_path_is_unaffected PASSED
tests/test_dashboard_detector_health_honesty.py::test_camera_transport_failure_message_stays_distinct_from_detector_failure_message PASSED
tests/test_dashboard_detector_health_honesty.py::test_acoustic_status_stays_independent_of_a_visual_detector_failure PASSED
```

The failure, exactly as predicted before writing the fix:

```
AssertionError: expected the real detector/GPU failure text, got: 'Camera Node is paired and configured.'
```

The scenario: a `camera_node`-provider Stream whose
`ObservationEngineSessionManager.status()` reports a real production shape
-- `state="error"`, `camera_connected=True` (the pairing guard already
passed), `camera_message="Camera Node is paired and configured."` (the
pre-existing, un-clearable success text set before the engine load is
attempted), `engine_available=False`, `engine_message=<the real GPU/model
failure text `_engine_failure_message` produces>`. This mirrors what a real
`_EngineSession._run_async` produces for a genuine `onnx_cuda_unavailable`/
missing-model-bundle failure (`engine_runtime.py`), faking only the
side-effect-free `ObservationEngineSessionManager.status()` read -- the
same technique `test_dashboard_observation_engine_truth.py` already
established, never starting a real session or touching CUDA/GPU hardware.

Only the message-precedence assertion failed. `camera_health.state ==
"camera_unavailable"`, `needs_attention_count == 1`, and `ready is False`
were **already correct pre-fix** -- confirmed directly by leaving those
assertions in the same RED test and observing they did not fail. The three
other scenarios (healthy detector, camera-transport failure staying
distinct, acoustic independence) all passed unmodified pre-fix, precisely
scoping the real defect to the message text alone, not the underlying
state detection.

## Root cause

Traced the exact precedence chain end to end by direct code reading, then
confirmed with the RED test above:

1. **Where is primary visual model availability already known?**
   `_EngineSession._engine_available`/`_engine_message`
   (`src/mockingbird/observation/engine_runtime.py`), set the moment
   `self._provider_loader(...)` (the real MDv5a ONNX/CUDA detector load)
   raises. Exposed unchanged via `ObservationEngineSessionStatus.
   engine_available`/`.engine_message`. `_EngineSession.snapshot()` already
   computes its own top-level `message` field with the *correct*
   precedence for the "error" state: `self._camera_message if not
   self._camera_connected else self._engine_message` -- explicitly
   documented as the "Camera health/status correction" contract
   (`engine_runtime.py:760-768`): "headline whichever subsystem is actually
   the blocking problem... never the other way around."
2. **Where is it lost?** `_dashboard_runtime_by_stream`
   (`src/mockingbird/api/main.py`), the function that bridges the engine
   manager's live session status into the Dashboard/`ProductHealth`
   aggregate. It re-derived a *second*, different precedence rule instead
   of reusing the one above: `engine_unavailable_message = engine_status.
   camera_message or engine_status.message`.
3. **Why does `camera_message` override the current failure message?**
   `camera_message` is set unconditionally, early -- "Camera Node is
   paired and configured." is written the moment the pairing guard passes,
   *before* the engine/detector load is even attempted -- and is never
   cleared if the engine subsequently fails while the camera stays
   connected (by design: a later transport failure still revises it
   correctly downward; an engine failure has no reason to touch a
   camera-subsystem fact). It is therefore always a truthy string, so
   `camera_message or message` always short-circuited to it, discarding
   `engine_status.message` (which had already resolved correctly) in favor
   of stale success text from an unrelated subsystem.
4. **Missing data, wrong precedence, or both?** Wrong precedence only. The
   real failure text (`engine_message`) was already present, already
   correct, and already reachable at this exact call site -- it was
   discarded, not absent.
5. **Does correcting precedence alone fully solve it?** Yes, confirmed by
   the GREEN run below: no other layer (the per-camera `CameraHealthState`
   assignment, the top-level `ready`/`needs_attention_count` computation,
   the frontend Dashboard rendering) needed a change.
6. **Is an additive `ProductHealth` field needed?** No. `CameraHealthState.
   camera_unavailable` (an existing enum member, already rendered with an
   "alert"-tone "Camera unavailable" badge by the frontend's own existing
   `cameraHealthTone`/`cameraHealthLabel`) plus a correct `message` string
   already express "detection is unavailable" completely and honestly
   through the existing contract. Adding a field would have duplicated an
   already-sufficient truth channel.

## Health contract

Confirmed against all four required outcomes, each with a passing
regression test:

- **Healthy camera + healthy detector:** unaffected
  (`test_dashboard_healthy_detector_path_is_unaffected`) -- `ready: true`,
  `needs_attention_count: 0`, message `"MockingBird is ready."`.
- **Healthy camera + unavailable primary detector:** `camera_health.state`
  is the existing `"camera_unavailable"` (alert-tone, non-OK-bucket), and
  its `message` now carries the real detector/GPU failure text -- never
  "paired and configured," "all healthy," or an ordinary quiet state
  (`test_dashboard_flags_detector_unavailable_while_camera_stays_healthy`).
- **Camera failure:** stays the actionable top-level problem, with its own
  specific transport-failure text, never the detector/GPU wording
  (`test_camera_transport_failure_message_stays_distinct_from_detector_
  failure_message`; the pre-existing `test_dashboard_observation_engine_
  truth.py::test_dashboard_summary_flags_a_terminally_unavailable_camera_
  node_stream` continues to pass unmodified).
- **Optional acoustic failure:** stays independent and optional
  (`test_acoustic_status_stays_independent_of_a_visual_detector_failure`;
  the five pre-existing `test_product_health.py` acoustic tests continue to
  pass unmodified) -- acoustic status is never derived from, or implied
  by, the primary visual detector's own state, and never a factor in
  `ready` (unchanged, pre-existing behavior).
- **BioCLIP vs. detector:** structurally confirmed distinct, not merely
  asserted -- `_EngineSession._schedule_automatic_identification` (the
  BioCLIP call site) wraps its entire body in `try/except Exception:
  return`, documented "must never break admission." It cannot reach
  `self._state`, `self._engine_available`, or `self._engine_message` under
  any failure; a BioCLIP outage can never be represented as a detector
  outage because the two code paths do not share write access to the same
  state.

## Implementation

One precedence fix, `src/mockingbird/api/main.py`
(`_dashboard_runtime_by_stream`): replaced
`engine_status.camera_message or engine_status.message` with
`engine_status.engine_message if engine_status.camera_connected else
engine_status.camera_message` -- reusing the exact same
camera-connected-wins-only-if-disconnected precedence
`_EngineSession.snapshot()` already defines and documents, rather than
inventing a second rule. Verified behaviorally identical to the old code
for both pre-existing trigger scenarios (not paired at all; bounded
reconnect exhausted, `camera_connected=False`) and correct for the one it
fixes (engine/detector failure while `camera_connected=True`). No new
field, no schema change, no new endpoint.

## Dashboard result

No frontend change was needed, confirmed by direct inspection before
concluding so (`docs/product-doctrine.md` "Capability-aware UX": prefer
the honest existing surface over scaffolding a new one). `DashboardPage.
tsx` already renders `camera.failure_reason ?? camera.message` verbatim
for the per-camera attention row, with no hardcoded frontend string and no
truncation. `cameraHealthLabel`/`cameraHealthTone`
(`web/src/utils.ts`) already map `camera_unavailable` to the label "Camera
unavailable" and the strongest available tone, `"alert"` -- so the badge
was already correctly alarming pre-fix; only the message sitting next to
it was self-contradictory ("Camera unavailable" next to "Camera Node is
paired and configured."). Fixing the backend text alone resolves the
contradiction end to end.

## Onboarding narrative result

`web/src/components/OnboardingWizard.tsx`, two paragraphs:

- **Welcome step:** "When something worth a look happens, it appears in
  your Review Queue for you to confirm" -> "Sightings show up right away
  in Today and Bird Log, often with a likely species guess -- MockingBird
  never claims an identification as certain until you confirm or correct
  it, whenever you'd like."
- **Observe step** (post-camera-setup): "Anything worth a look lands in
  Review Queue" -> "Sightings will show up in Today and Bird Log as they
  happen; open Review Queue any time you want to work through suggestions
  in one place."

Both now match `docs/product-doctrine.md`'s "Core flow" (Observe ->
Discover -> Understand -> Confirm -> Remember -> Improve, discovery
through Today/Bird Log/Visit detail) and "Measured, Inferred, and
Reviewed" (Inferred output must be useful immediately, never gated on
human confirmation first). Terminology reused, not invented: "Likely" /
"Not yet confirmed" already appear on `BirdLogPage.tsx`; "Confirmed" /
correction actions already appear on `VisitDetailPage.tsx`. Review Queue
is still named, still available, just no longer framed as the destination
sightings "land in" or "appear in" -- it remains a real, findable surface
for deliberate batch review. No screens added, no wizard-flow change, no
other paragraph touched.

## Validation

Tier 1 (this milestone's own new files):

```
tests/test_dashboard_detector_health_honesty.py .... (4 passed)
tests/test_onboarding_narrative_copy.py ... (3 passed)
```

Tier 2 (health/dashboard/camera/onboarding/setup-adjacent subsystem
sweep, 30 files -- everything in the repository that exercises
`dashboard_summary`, `/api/product/health`, `_camera_health_summary_from_
models`/camera health, or setup/onboarding state, plus this milestone's
own two new files): **594 passed, 11 xfailed, 0 failed** (261.5s). The 11
xfailed are pre-existing, unrelated to this change (established `xfail`
markers in the swept files, not new).

Frontend: `npm run typecheck` (`tsc --noEmit`) clean. The dedicated,
already-established onboarding e2e suite
(`npm run test:e2e:onboarding`, a real Chromium browser against a real
built frontend and a real fresh backend instance -- not a mock DOM) --
**6 passed, 0 failed**, including the extended "a fresh install creates
the first administrator..." test carrying this milestone's own new
Welcome-step copy assertions, proven against real rendered HTML, not only
the static-source-text backstop.

Tier 3 (full Core): not run. Per the brief's own guidance (§17), this
change is a single-branch precedence fix confined to one function
(`_dashboard_runtime_by_stream`) with zero DTO/schema change and zero
central runtime-health-plumbing restructuring; Tier 2's 30-file, 594-test
sweep already covers every real consumer of the touched function
(`dashboard_summary`, `/api/product/health`, and every camera-health/
setup-state-adjacent test in the repository) and returned clean, so there
is no blast-radius evidence calling for a full-Core run.

`ruff check` on every touched/new file: zero new findings. The 26
pre-existing findings in `src/mockingbird/api/main.py` (unrelated imports/
statement style, none within ~2,300 lines of the touched function) are
confirmed unrelated by direct `git stash push -u` bisection -- identical
count (26) and identical finding set before and after this change. The
two new test files are clean (`ruff check`: "All checks passed!").

No schema change (`CURRENT_DATABASE_SCHEMA_VERSION` unchanged at `v58`).

## Remaining Lane C gaps

None known. Both bounded DEV gaps the accepted reconciliation named are
closed: detector/GPU/model failure while the camera stays connected now
surfaces its own real failure text instead of stale "paired and
configured" success text (and continues to raise `needs_attention_count`/
`ready: false`, which was already correct); onboarding no longer frames
Review Queue as the normal destination for ordinary discovery.

Not claimed as complete by this milestone, and out of its scope: broader
onboarding polish beyond the two stale paragraphs; any Dashboard layout
change; Best Moments/New-Regular/suggestion-explanation/review-queue
logic (frozen, untouched); future taxonomy content; Gate A field
validation; Lane G real-hardware validation.

One precisely-scoped, adjacent, genuinely out-of-scope observation found
during self-review and deliberately not chased: `_EngineSession._run`'s
outermost `except Exception` (`engine_runtime.py:855`, marked
`pragma: no cover - defensive: never crash the app process`) sets only
`_camera_message` (to the raw exception text), never `_engine_message`.
If this genuinely unexpected, never-yet-reproduced catch-all ever fired
*after* the camera connected and the detector already loaded (so
`engine_message` still held its last, now-stale "Observation Engine is
running." text), this milestone's fix would surface that stale text
rather than the crash detail -- `_EngineSession.snapshot()`'s own
"headline whichever subsystem is actually blocking" precedence already
has this identical characteristic one layer up (unchanged by this
milestone), so this is not a regression this milestone introduces; it is
a pre-existing gap in a defensive backstop this milestone's fix
deliberately reuses rather than diverges from, per the governing brief's
own "if an existing shared helper already defines it, reuse it"
instruction. Disclosed, not fixed: `pragma: no cover`, never reproduced,
and the correct fix (if ever warranted) belongs in `_EngineSession._run`
itself, not in the Dashboard-layer precedence this milestone's scope
covers.

## Lane C final disposition

**MATERIALLY DELIVERED / NO KNOWN DEV REMAINS.** `docs/release-execution-
state.md` §6.C updated to cite: Best Moments, calm daily summary, New /
Regular presentation, unknown/unresolved handling, understandable
suggestion explanations, mostly-invisible review, and report-first
hierarchy as delivered by the already-accepted milestones behind each
(Gate C Daily Place Report, Gate C Calm Daily Digest, Gate C Historical
Baseline Maturity, Historical Species-Status Correctness v1, Same-Frame
Species Evidence, Visit Classifier Evidence Visibility, Whole-Product UI
Closure's review-optional fix); and this milestone for sparse/no-wildlife
detector-health honesty and first-hour onboarding narrative. This does not
claim future taxonomy content, broader onboarding redesign, or general UI
perfection is complete -- only that no concrete, previously-disclosed Lane
C development gap remains known.

## Decision

**A.** Both known Lane C DEV gaps closed with real, independently-verified
evidence: the detector-unavailable-while-camera-healthy message-honesty
defect was reproduced RED against the real, unmodified pre-fix code before
any change, root-caused to one specific line, fixed by reusing an
already-correct, already-documented precedence rule rather than inventing
a new one, and confirmed GREEN together with three adjacent regression
scenarios (healthy path, camera-failure distinctness, acoustic
independence) plus a structural (not merely asserted) BioCLIP/detector
separation check. The onboarding narrative fix is verified against real
rendered DOM through the repository's own established e2e suite, not only
a static-source backstop. Tier 1 and Tier 2 are fully clean (601 tests
total across the two, 0 failures), `ruff check`/`tsc --noEmit` clean, no
schema change, and the diff is confined to exactly the files this
milestone's scope names -- no unrelated Lane C work reopened.
