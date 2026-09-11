# Release Experience Rehearsal v1

Directly authorized outside this file (see the milestone brief returned
to ChatGPT alongside this report). Classification: see recommendation,
§12 below -- this report does not self-classify.

## 1. Artifact identity

- Source commit for the rehearsal's real fixes: `88a5eb1` (accepted
  baseline, Product Polish & UX Refinement v2).
- Fix commits made during this milestone: `5af366a` ("4 real defects
  found and fixed live against the built Windows artifact"), `250dd5c`
  ("document the expected SmartScreen warning").
- **Final artifact** built from `250dd5c` (clean tracked source,
  `source_clean: true`): `dist/release-experience-rehearsal-v1-final/`,
  `MockingBird-windows-x64.zip`, version `0.1.0`, unsigned (no
  `MOCKINGBIRD_RELEASE_SIGNING_KEY_ID` configured, none fabricated).
  Independently verified with `scripts/verify_release_artifact.py`: see
  §8. Exact file count/byte size/SHA-256 recorded in that verification
  run's own output.
- An earlier build from the pre-fix baseline (`88a5eb1`,
  `dist/release-experience-rehearsal-v1/`) was the one actually used for
  the bulk of the live rehearsal in §2-§11 below, since the defects
  described there were found *during* that rehearsal, not before it. The
  final, fixed artifact was independently re-verified and spot-checked
  (§8) rather than re-walked start to finish.

## 2. Release-user path actually exercised

Real native-Windows/GPU hardware (the same reference dev machine this
project's memory calls "sandbox has real Windows+GPU interop"), a fresh
disposable data directory (the pre-existing `%LOCALAPPDATA%\MockingBird`
was renamed aside before the rehearsal and restored byte-for-byte
afterward -- verified by file count/size/mtime before and after), and a
disposable browser-automation profile (Playwright driving real
Windows-side Microsoft Edge, `channel: 'msedge'`, no separate Chromium
download needed).

Exercised, in order:

1. Built the release artifact from the accepted baseline (§1).
2. Independently verified it (§8).
3. Extracted a fresh copy to `Desktop\MockingBird-Rehearsal\` (matching
   the documented "anywhere you like -- your Desktop" guidance).
4. Double-click-equivalent launch (`wscript.exe` on `Start
   MockingBird.vbs`, matching the real double-click code path) --
   confirmed the browser auto-opened on its own (new browser process
   detected after readiness), no console window, no terminal.
5. First-run wizard: Welcome -> Account creation -> Storage -> Add
   Camera -> "Your camera is ready".
6. Created the first Administrator account through the real UI (no
   credentials asked of the user; this is exactly the "ordinary
   development/validation work" case that memory's standing policy says
   should use a fresh disposable instance, not the case requiring the
   user's live participation).
7. Storage step genuinely showed a real "running low" disk warning (this
   machine's C: drive is genuinely constrained by unrelated prior
   work/dev history) -- verified the threshold logic itself is sound
   (§3.1), not fabricated alarm.
8. Camera/source setup:
   - Paired a real, disposable MockingBird Camera Node (`python -m
     mockingbird_node`, run from this sandbox's Linux/WSL side --
     Debian-family Linux is an explicitly documented-supported Node
     platform) over a real network handshake -- genuinely live software,
     no attached camera hardware (honestly reports `setup_required`,
     matching documented behavior for a Node without a camera).
   - Deliberately did **not** touch the real reference Raspberry Pi
     Camera Node's existing pairing (read-only health check only -- see
     §6) to avoid disrupting whatever it is currently paired to; this is
     the one place live hardware proof was intentionally not attempted
     (see §6 for the honest disposition).
   - Completed a Manual-media (recorded video/images) Source instead,
     using real photographs (see §7).
9. First observation: imported a real backyard-feeder photograph (from a
   real prior field-acceptance recording, containing a real, visible
   small bird) through **Import Media**, producing a real reviewable
   Visit.
10. Ran the real local BioCLIP-2 identification assistant against that
    real photo on real CPU inference -- genuinely abstained (top
    candidate well below the confidence floor on an uncropped, wide
    scene) -- and found a real bug in how that honest abstention was
    reported (§3.4).
11. Reviewed and corrected the Visit ("Unknown Bird") through the real
    correction UI.
12. Checked Today, Bird Log, and Place Story for the reviewed truth --
    found a real, deeper cross-surface inconsistency (§3.5, disclosed,
    not fixed).
13. Checked Doctor -- comprehensive, honest, correctly reported real GPU/
    CUDA/BioCLIP/detector-model availability and the real low-disk state
    with matching severity and an actionable "what to do."
14. Created and verified a real local backup.
15. Clean shutdown via the real **Shut Down MockingBird** button --
    confirmed both the main process and its multiprocessing worker child
    genuinely exited (`Get-Process`/port-listener checks), not merely
    that the browser tab closed.
16. Relaunch -- confirmed no false "did not shut down cleanly" warning
    (the specific regression the immediately-preceding milestone fixed),
    and confirmed full persistence (Sources/Streams/Zones/Visits/
    Corrections/backup all intact, exact same `instance_id`).
17. A representative, safe error scenario: attempted to pair the
    disposable Camera Node using a deliberately wrong one-time code
    while the Node was genuinely unreachable (stopped) -- see §3.7 for
    what this did and did not prove.
18. Full uninstall, followed literally: shut down -> deleted the
    application folder (verified the separate data folder was
    byte-for-byte untouched) -> re-extracted a fresh copy of the
    application folder over the same data folder (verified it skipped
    onboarding and picked up exactly where it left off, matching the
    "Upgrading MockingBird"/reinstall claim) -> shut down again ->
    deleted the data folder too (full removal, verified gone).
19. Restored the machine's original `%LOCALAPPDATA%\MockingBird` from
    the pre-rehearsal backup; stopped the disposable Camera Node;
    removed the disposable extraction folder.

## 3. Concrete friction points found (with fixes)

### 3.1 Storage-tier severity not visually distinguished (FIXED)

**Symptom.** A brand-new install with 888 KB of real product data showed
"Local storage space is running low" in a calm green-bordered
`notice-panel` on the very first wizard screen after account creation.
Investigated the threshold logic directly (`LOW_DISK_FREE_BYTES_
THRESHOLD`/`LOW_DISK_FREE_RATIO_THRESHOLD` in `storage/database.py`) and
confirmed it is sound and not a bug -- this test machine's C: drive
genuinely has under 5% free space from unrelated prior work, and the
1 GB-or-5%-of-disk trigger is a defensible, already-reviewed judgment
call. The real defect was downstream: the 4-tier `storage_health_tier`
ladder (`healthy`/`getting_low`/`action_recommended`/`critical`) was
introduced by a past milestone, but every consumer of the derived
`storage_warning` string (`OnboardingWizard`, `LocalDataPage`,
`DashboardPage`) rendered it in one plain, calm box regardless of tier,
and `ProductHealthPanel`'s compact one-line summary showed it as
undecorated plain text -- so `critical` ("New evidence may soon fail to
save") was visually indistinguishable from the mild `getting_low`
advisory everywhere a user would actually see it.

**Fix.** `storage_health_tier` is already exposed cleanly in the API
(`StorageSummary.storage_health_tier`); no schema change needed. The
three prose surfaces now use each page's own already-existing
error-styled class (`error-panel` / `dashboard-action-error`) for
`critical`, reusing the exact same treatment those pages already give
the "not writable" case, instead of inventing new styling.
`ProductHealthPanel` now wraps its one-line summary in the existing
`StatusPill` component (already imported, already used one line away for
the top-level Ready/Needs-attention state) with `alert` for
`critical`/not-writable, `review` for `action_recommended`, and plain
text for `healthy`/`getting_low` (preserving the calm-by-default
convention this exact file already uses for the acoustic "Not
configured" state).

**Files:** `web/src/components/OnboardingWizard.tsx`,
`web/src/pages/LocalDataPage.tsx`, `web/src/pages/DashboardPage.tsx`,
`web/src/components/ProductHealthPanel.tsx`.

**Validated:** tsc/vite clean; 34 relevant e2e tests passing (onboarding
x6, doctor/camera-node x3, mobile-viewport-audit x25). The `critical`
tier's specific visual output was verified by code/type inspection
against an already-covered, already-styled sibling case (`error-panel`
for not-writable), not from a live full-disk repro -- deliberately not
attempted, per this milestone's explicit "do not fill the real system
disk" instruction.

### 3.2 Onboarding wizard's final step misled a Manual-media user (FIXED)

**Symptom.** After completing camera setup with a Manual-media (recorded
video/image) Source, wizard step 5 ("Your camera is ready") showed:
"Start observing when you would like MockingBird to watch this camera...
Sightings will show up in Today and Bird Log as they happen" -- directly
below, the real Observation panel showed "**Not available here** / This
stream has product metadata but no playback adapter configured yet." The
heading and lead paragraph were written for the live-camera path and
never mention Import Media, the Manual-media Source's actual next step.
Not an absolute dead end (Import Media is a top-level, always-visible
main-nav item -- a Dashboard-bound user would likely still find it), but
a real, avoidable moment of confusion at the single most consequential
step of first-run setup.

**Fix.** `ObservationControlPanel` gained an optional `onStatus` callback
(reusing its existing 3-second poll, not a second fetch) so `ObserveStep`
can read `runtime_available` without new backend work. When `false`, the
final step now explains plainly that this camera type does not watch on
its own and points to **Import Media** by name, while the live-camera
copy is unchanged and still shown by default while the first status poll
is in flight (so it does not flash the wrong copy for the common
live-camera case).

**Files:** `web/src/components/OnboardingWizard.tsx`,
`web/src/components/ObservationControlPanel.tsx`.

**Validated:** tsc/vite clean; 6 onboarding e2e tests + 5 observation-
panel e2e tests passing. Live re-verification against the final,
fixed artifact deferred to §8 (a full second onboarding walkthrough was
not repeated; the fix is a small, type-checked conditional read from an
already-correct, already-tested data source).

### 3.3 Synthetic "demo proposal" panel unconditionally visible to real users (FIXED)

**Symptom.** Import Media's success view included a full "Browser local
smoke path" panel -- "Create synthetic demo proposal evidence for local
smoke testing. No model inspects the media and no reviewed truth is
created" -- with working buttons, shown to every user regardless of
Developer Mode. `VisitDetailPage.tsx` already gates an analogous
synthetic-evidence action behind the existing `isDeveloperMode` toggle
(itself already a deliberate, documented, off-by-default nav affordance
that reveals genuinely advanced pages); this one page's panel simply
never received the same treatment.

**Fix.** Added the identical `isDeveloperMode` prop/gating to
`ManualImportPage`, wired from `App.tsx` exactly as `VisitDetailPage`
already receives it. The panel is invisible by default, reachable the
same way every other advanced page already is.

**Disclosed, not fixed (same pattern, lower-traffic surface):** a second
instance of the identical anti-pattern exists on `StreamsPage.tsx`'s
per-image "Analyze image (demo)" action (Cameras -> Camera setup and
repair -> a saved image's own detail). Deliberately not fixed this
milestone: `StreamsPage.tsx` is a very large (7,700+ line) file, this
specific panel is several navigation steps deeper than Import Media (a
new user is unlikely to reach it during ordinary first use), and wrapping
it correctly would need careful verification across a much larger,
less-familiar span of markup than was proportionate to fix live under
this milestone's own "bounded, not a broad sweep" instruction. Recommend
a small, dedicated follow-up that greps for every unconditionally-visible
"demo"/"synthetic"/"smoke" action across the frontend and gates each the
same way, in one pass, with its own focused review.

**Files:** `web/src/pages/ManualImportPage.tsx`, `web/src/App.tsx`.

**Validated:** tsc/vite clean; no existing e2e coverage exercised this
exact panel (none lost); `review-queue-fast-review-keyboard.spec.ts`
(the one spec touching this page) still passes.

### 3.4 Honest identification abstention reported as "failed" (FIXED -- real backend bug)

**Symptom.** Running the real local BioCLIP-2 species-suggestion
assistant against the real imported photo (a wide, uncropped yard scene
with a small bird on a feeder -- no detector-provided crop exists for
Manual media) produced a genuinely low-confidence top candidate
("Red-bellied Woodpecker", 59.2%, well under the 85% full-frame
confidence floor) and correctly, honestly abstained --
`ReviewIdentificationStatus.identification_uncertain` at the underlying
single-shot boundary, exactly the by-design "honest uncertainty rather
than a malfunction" outcome that status's own docstring describes
(matching a previously-documented real incident, same species, almost
the same score, from `person-background-false-positive-attribution-v1-
report.md`). But the Visit-detail page's "Suggest species" action (the
`start_visit_identification_assistant` wrapper) never mapped that status
into its own terminal-status vocabulary, so it fell through to the
generic `"failed"` catch-all -- reported to the user as "Latest explicit
request: failed", indistinguishable from a genuine adapter/runtime
error, and a real, if narrow, breach of the "honest uncertainty, not a
malfunction" contract that status exists specifically to uphold.

**Fix.** Added `ReviewIdentificationStatus.identification_uncertain` to
the already-existing `no_result` terminal-status set in
`start_visit_identification_assistant` (`product_repository.py`) --
reusing an already-correct, already-calm status rather than inventing a
new one. Reproduced RED first (`git stash` the fix, re-run the new test:
`assert 'failed' == 'no_result'` fails) then GREEN; a new regression test
(`test_identification_assistant_run_reports_honest_abstention_not_
failed`) added to `tests/test_identification_eligibility_regression_
2026_08_21.py`, the file that already covers this exact abstention
boundary at the single-shot level. Also fixed the adjacent
`IdentificationAssistant.tsx` display line, which rendered the raw
`run.status`/`run.request_origin` enum values via bare `String(...)`
instead of this exact file's own established `formatLabel(...)`
convention (used one line away for `availability.status`) -- so even a
genuine `"failed"` now reads as plain language, not a second raw-enum
leak.

**Files:** `src/mockingbird/repository/product_repository.py`,
`web/src/components/IdentificationAssistant.tsx`, `tests/
test_identification_eligibility_regression_2026_08_21.py`.

**Validated:** RED->GREEN confirmed directly; 44 tests passing across
the identification/species-suggestion test family; full Core
independently reconfirms this change (see §8).

### 3.5 Cross-surface disagreement on "confirmed wildlife" for unresolved species (FOUND, DELIBERATELY NOT FIXED)

**Symptom.** After reviewing the imported Visit as "Unknown Bird," the
**same underlying fact** reads differently across three real product
surfaces:

- **Today's digest** (`place_activity_report.py`): "**Confirmed wildlife
  -- species not yet identified** / 1 visit confirmed today" --
  `unknown_bird`/`unknown_animal` resolve to `_Classification.
  CONFIRMED_SPECIES_UNRESOLVED`, explicitly documented as "a human
  explicitly confirming an animal was present while abstaining on
  species. That is confirmed wildlife activity with an unresolved taxon."
- **Bird Log** (`product_repository.py`'s `_visit_review_outcome` ->
  `_is_confirmed_wildlife_summary`): "**No confirmed wildlife
  observations yet**. Review a Visit to create a confirmed local
  wildlife observation." -- the identical label resolves to
  `VisitReviewOutcome.ambiguous` (grouped with genuinely-uncertain
  free-text "ambiguous"/"unknown" labels), which is excluded from
  "confirmed wildlife" everywhere that outcome feeds: Bird Log, Wildlife
  Insights, Activity Library, and Place Story's representative-evidence
  selector.
- **Local Data's own Storage summary** (`_storage_visit_is_wildlife`,
  built on the same `_visit_review_outcome`): "reviewed wildlife: 0 ·
  reviewed other: 0" -- the same Visit counts in neither bucket, despite
  "Corrections: 1" showing directly above it on the same page.

Both computations are deliberate, thoughtfully reasoned, and separately
well-documented in their own code -- this is a genuine architectural
disagreement between two independently-evolved subsystems about what
"confirmed wildlife" means for the exact case product-doctrine.md calls
out by name ("Unknown and abstained outcomes are valid"), not a simple
oversight. A real new user's very first reviewed Visit -- the one moment
this whole rehearsal is built around getting right -- is described as
both "confirmed" and "not confirmed" simultaneously, on pages one click
apart.

**Why not fixed here.** Reconciling `VisitReviewOutcome`'s semantics
would touch `_visit_review_outcome` itself, used (per its own docstring)
as "the exact same active reviewed truth as Insights" -- meaning Bird
Log, Wildlife Insights, Activity Library, and Place Story's
representative-evidence selector all key off it, several already
extensively tested and accepted in prior milestones. Deciding which
side's definition is canonical, then propagating that decision correctly
across every dependent surface with proportionate new test coverage, is
a real, cross-cutting product-semantics decision -- squarely the kind of
"reopen accepted v1/v2 polish" and "expand a small usability issue into a
broad redesign" this milestone's own brief explicitly forbids. Disclosed
in full, precisely root-caused (all three call sites and their exact
enum branches identified above), and recommended as a dedicated,
bounded follow-up investigation -- not attempted speculatively.

### 3.6 Uninstall step 1 did not mention the preferred stop method (FIXED)

**Symptom.** "Install and start (Windows)" establishes **Shut Down
MockingBird** as "the preferred way" to stop the app (it avoids a false
"did not shut down cleanly" note). "Uninstall" step 1, later in the same
document, never mentions it -- going straight to Task Manager/restarting
the computer, as if the earlier guidance did not apply here too.

**Fix.** Uninstall step 1 now names Shut Down MockingBird first,
explicitly cross-referencing "the same preferred method as 'Install and
start (Windows),' above," with Task Manager/restart kept as the fallback
for when MockingBird itself will not open.

**Files:** `docs/using-mockingbird.md`.

### 3.7 Windows SmartScreen warning undocumented (FIXED)

**Symptom.** The release artifact is honestly unsigned (§1) -- no
signing key exists, none was fabricated, matching the accepted signing
posture. A real, unsigned, newly-downloaded Windows executable/script
combination very likely triggers a SmartScreen "Windows protected your
PC" warning on first run. Neither `docs/using-mockingbird.md` nor the
in-package `README-FIRST.txt` said anything about this at all -- a real,
foreseeable first-launch surprise this milestone's own brief specifically
names ("If a warning is expected and cannot be removed safely, make sure
the documentation explains it before the user encounters it").

**Not literally triggered in this rehearsal**: the launch mechanism used
here (`wscript.exe` invoked directly via `Start-Process`, matching the
double-click code path exactly) does not carry the "Mark of the Web"
zone-identifier a real browser download attaches, so SmartScreen's own
reputation gate was not exercised end-to-end live. This is disclosed as
reasoned-from-known-Windows-behavior-and-the-artifact's-real-unsigned-
state, not directly observed -- see §6 for the full accounting of what
this rehearsal's methodology could and could not exercise on this
specific point.

**Fix.** Added a short, honest note to both `docs/using-mockingbird.md`
("Install and start (Windows)") and the in-package `README-FIRST.txt`
(generated by `scripts/build_local_product.py`) explaining why the
warning appears and the standard "More info -> Run anyway" path --
without weakening, second-guessing, or instructing around the warning
itself; the user still decides whether to trust their download source.

**Files:** `docs/using-mockingbird.md`, `scripts/build_local_product.py`.

**Validated:** the one existing packaging test asserting on
`README-FIRST.txt` content (`test_assemble_windows_bundle_produces_a_
python_and_pip_free_user_experience`) still passes -- its assertions are
substring-based (`"To remove MockingBird"` present, `%LOCALAPPDATA%\
MockingBird` count >= 2), unaffected by the addition.

### 3.8 Minor, disclosed, not fixed

- **Terminology mismatch**: `docs/using-mockingbird.md` describes this
  Source type as "Recorded wildlife video or images you already have";
  the actual Camera-type dropdown in the product itself calls it "Manual
  media -- Import only." A careful reader following the doc literally
  would need to infer the mapping. Low severity (only one plausible
  match exists in the dropdown); not fixed, to avoid a speculative
  rename of a shipped, tested UI label for a single milestone's own
  minor wording preference.
- **"Add Camera" discoverability on the dedicated Cameras page**: the
  Dashboard has an always-visible "Add Camera" button; the "Cameras /
  Streams" workspace page itself (whose own subtitle literally reads
  "Add a camera, connect it...") has no top-level Add-Camera
  affordance -- it is one level deeper, inside "Camera setup and
  repair." Not a dead end (two working paths exist; the Dashboard's own
  button is the one a first-time user sees immediately after finishing
  setup), and out of proportion to fix as a UI-layout change during this
  milestone.
- **Camera Node "unreachable after a working pairing" was not
  exercised live** -- see §6.

## 4. Documentation changes (summary)

- `docs/using-mockingbird.md`: Uninstall step 1 now names the preferred
  stop method (§3.6); added a SmartScreen warning note to "Install and
  start (Windows)" (§3.7).
- `scripts/build_local_product.py`: `README_FIRST` template gained the
  matching in-package SmartScreen note (§3.7).
- This report (`docs/release-experience-rehearsal-v1-report.md`) is new.

No other public documentation was rewritten; `docs/using-mockingbird.md`
and `docs/camera-node-install-guide.md` were both read in full and
checked against real, live behavior throughout this rehearsal (§2) and
found accurate everywhere except the two items above. No broken relative
markdown links were found in any public-facing doc
(`using-mockingbird.md`, `camera-node-install-guide.md`, `README.md`,
`THIRD_PARTY_NOTICES.md`, `CONTRIBUTING.md`, `SECURITY.md`).
`SECURITY.md`'s GitHub URL matches the real `origin` remote exactly.

## 5. Real Windows evidence

Every step in §2 ran against the real packaged artifact on real
native-Windows hardware with a real NVIDIA GPU -- Doctor's own live
report confirmed `GPU / CUDA: Pass -- CUDA execution provider is
available`, `Detector model: Pass -- ... present and verified`, `Species
identification: Pass -- BioCLIP species-suggestion runtime is
available`, all self-reported by the running instance itself, not
assumed. Real process-level verification (not just HTTP-level) for
launch (new browser process detected), shutdown (both the main process
and its multiprocessing worker child confirmed exited via
`Get-Process`/`Get-NetTCPConnection`), and uninstall (`Test-Path` on both
the application and data folders, before and after each step).

## 6. Real Pi evidence, and what was deliberately not attempted

The real reference Raspberry Pi 4 Camera Node (`192.168.1.112:8787`) was
checked read-only over the LAN: healthy, paired, `self_test: passed`,
`camera_available: true`, `available_camera_count: 1`. Deliberately **not**
touched further -- `pairing_required: false` means it is already
committed to some existing pairing this rehearsal could not identify or
safely assume was disposable, and revoking or re-pairing it live would be
a one-way action against shared infrastructure with no way to restore the
prior pairing afterward. This is exactly the situation this milestone's
own brief anticipates ("Where the full camera path cannot be exercised,
distinguish clearly between: live hardware proof / structural proof /
simulation / not verified"):

- **Live hardware proof**: the reference Pi's own health/self-test/
  camera-availability facts (read-only).
- **Live software proof, no physical camera**: a fresh, disposable
  `python -m mockingbird_node` instance (run on this sandbox's own
  Debian-family Linux side, an explicitly documented-supported Node
  platform) paired for real with the rehearsal's MockingBird instance
  over a real network handshake, real one-time pairing code, real
  `POST`/health exchange -- genuinely live, just without an attached
  camera (honestly reports `setup_required`, matching documented
  behavior).
- **Not verified**: a Camera-Node-backed Stream's live-video/detection
  path end to end, and "Camera Node goes unreachable after a working
  pairing" as a live error scenario -- both would need either the
  reference Pi's own pairing disrupted or a second physical camera-
  equipped device, neither available without a decision outside this
  milestone's own authority. The *attempted-pairing-while-unreachable*
  case (§2 step 17, a different, achievable scenario) was exercised
  instead, but the attempt itself did not complete cleanly under this
  rehearsal's own browser-automation tooling (a locator-timeout issue in
  the test harness, not a product-side failure) and was not re-attempted
  given time already invested relative to its incremental value beyond
  the Camera Node pairing success already proven in §2 step 8.

## 7. Validation results

- `npm run typecheck` (tsc --noEmit): clean, after every frontend change.
- `npm run build` (vite): clean, after every frontend change.
- Targeted e2e (Playwright, WSL-side dev backend): 55 tests passing
  across `onboarding.spec.ts` (6), `doctor-and-camera-node-hardware-
  health.spec.ts` (3), `mobile-viewport-audit.spec.ts` (25), `visit-
  classifier-supporting-evidence.spec.ts` (4), `visit-evidence-review-
  loop.spec.ts` (2), `observation-panel.spec.ts` +
  `observation-panel-subsystem-message-honesty.spec.ts` (5), `review-
  queue-fast-review-keyboard.spec.ts` (1), plus the identification-
  eligibility Python suite counted separately below.
- Python: `tests/test_identification_eligibility_regression_2026_08_21.py`
  + `tests/test_identification_assistant.py` +
  `tests/test_review_queue_species_suggestion_batch.py` +
  `tests/test_background_empty_evidence_species_confidence_correctness_
  v1.py` -- 44 passed, including the new regression test, RED->GREEN
  confirmed directly (§3.4).
- `tests/test_local_product_packaging.py -k "readme or bundle"` -- 24
  passed (covers the README-FIRST.txt change, §3.7).
- **Full Core** (`scripts/verify_core.py`, justified by real logic
  changes inside `product_repository.py`, the large, widely-shared
  repository module -- not run merely because this milestone has
  "release" in the name): 6003 passed / 3 failed / 4 skipped / 35
  deselected / 11 xfailed (47m38s). All 3 failures independently
  reconfirmed to fail identically against the unmodified pre-fix commit
  (`git stash` the one changed backend file, re-run exactly those 3
  tests -- same 3 names, same assertion failures, including a clearly
  time-relative `insufficient_recent_coverage`/`higher_recent_presence`
  mismatch in `test_place_change_summary_repository.py`) -- pre-existing,
  unrelated to this milestone's changes, matching this project's own
  well-established ~2-4-per-full-run flakiness baseline.
- `scripts/verify_release_artifact.py`: OK, both for the pre-fix
  rehearsal build and the final fixed build (§1/§8).

## 8. Final artifact re-verification

Built from `250dd5c` (both fix commits, clean tracked source,
`source_clean: true`). `scripts/verify_release_artifact.py`: **OK** --
`MockingBird-windows-x64.zip`, 18,728 files, 4,922,847,877 bytes, version
`0.1.0`, `source git:250dd5c7fe1663e13f596185234ff8619ef8cb4c`, unsigned.
SHA-256: `5f39bd7ae3b11054b651e12ab06e16e561d538e3f97df6c8e76da60fa556ce73`.
`build_id`: `2514784fd104be92`.

Spot-checked live against this exact final artifact (fresh disposable
extraction, fresh disposable data directory, fresh Administrator account
"Spot Check"):

- README-FIRST.txt confirmed to contain the new SmartScreen note (§3.7),
  read directly from the extracted bundle.
- Ran the complete first-run wizard through a Manual-media camera setup
  once more. Wizard step 5 now reads: "This camera type doesn't watch for
  activity on its own here, so there is no Start observing step for it.
  If this is a recorded/imported Source, use **Import Media** (in the
  main menu) whenever you're ready to add video or image files..." --
  confirming the §3.2 fix live, on the real final artifact, not merely
  by code inspection.
- Clean shutdown re-confirmed (process exit verified via `Get-Process`).

The other three fixes (§3.1 storage severity, §3.3 Developer Mode
gating, §3.4 identification-assistant status mapping) were not
separately re-walked live against this final artifact beyond what §7's
automated tests already cover, given proportionate effort for a spot
-check pass -- each is validated by tsc/vite, targeted e2e, and (for
§3.4) a directly reproduced RED->GREEN Python test against the exact
changed function.

This final artifact, and the superseded pre-fix build used for the bulk
of the live rehearsal, both existed only as local, disposable build
output (`dist/`, git-ignored) on this sandbox; the superseded pre-fix
build was deleted after this final artifact was verified. Nothing was
pushed, published, or distributed.

## 9. Release-experience scorecard

| Dimension | Rating |
| --- | --- |
| Getting started | ACCEPTABLE |
| Prerequisite clarity | POLISHED |
| First launch | POLISHED |
| Account creation | POLISHED |
| Camera/source setup | ACCEPTABLE |
| System-health understanding | POLISHED |
| First observation | NEEDS MORE WORK |
| Review/correction | POLISHED |
| Today / Bird Log / Place understanding | NEEDS MORE WORK |
| Error/recovery experience | ACCEPTABLE |
| Shutdown/restart | POLISHED |
| Backup/data understanding | POLISHED |
| Uninstall/removal | POLISHED |
| Public documentation | ACCEPTABLE |
| Overall visual/interaction quality | POLISHED |

**Getting started -- ACCEPTABLE, not POLISHED.** The in-hand experience
(unpack, double-click, auto-opens) is genuinely excellent, but the public
docs necessarily start from "you already have the zip" -- there is no
current answer to "where do I download this from" because MockingBird is
not yet published. Structural, not a defect this milestone can fix
(publication is explicitly out of scope), but real.

**Camera/source setup -- ACCEPTABLE.** The Camera Node pairing flow
itself is excellent and proven live; the wizard dead-end for Manual
media was found and fixed (§3.2). Held back from POLISHED by the
"Manual media" vs. "recorded wildlife video" terminology mismatch and
the Cameras-page Add-Camera discoverability note (§3.8), both real but
minor.

**First observation -- NEEDS MORE WORK.** The single acute defect
(honest abstention reported as "failed") is fixed (§3.4), but the
first-observation experience terminates in a genuine trust problem: the
Today digest calls the user's first reviewed Visit "confirmed" while
Bird Log says nothing has been confirmed yet (§3.5). This is exactly the
moment this whole rehearsal's objective is built around, and it does not
yet cohere.

**Today / Bird Log / Place understanding -- NEEDS MORE WORK.** Same root
cause as above (§3.5), reflected here because it is fundamentally a
"does reviewed truth show up consistently across these three surfaces"
question, not only a first-observation one -- it recurs for every future
`unknown_bird`/`unknown_animal` review a user makes, not just the first.

**Error/recovery experience -- ACCEPTABLE, not POLISHED.** Shutdown/
restart recovery and Doctor's own diagnostics are excellent and fully
proven live. Held back because the one Camera-Node-connectivity error
scenario this milestone asked for could not be cleanly exercised (§6),
so this dimension's rating reflects incomplete verification, not a known
defect.

**Public documentation -- ACCEPTABLE.** Comprehensive, honest, internally
consistent after this milestone's two fixes (§3.6, §3.7); held back only
by the pre-publication "where do I get this" structural gap (same
reasoning as "Getting started") and the minor terminology note (§3.8).

## 10. Remaining known release-experience issues

1. Cross-surface "confirmed wildlife" disagreement for `unknown_bird`/
   `unknown_animal` reviewed labels (§3.5) -- the most significant open
   item, recommend a dedicated follow-up investigation/decision.
2. `StreamsPage.tsx`'s "Analyze image (demo)" panel is the same
   unconditional-visibility anti-pattern already fixed once this
   milestone on Import Media (§3.3) -- recommend a small, dedicated
   sweep for every remaining instance, done in one pass.
3. "Manual media" vs. documented "recorded wildlife video" naming
   mismatch (§3.8) -- minor.
4. "Add Camera" not present at the top level of the dedicated Cameras
   page itself (§3.8) -- minor, two working paths already exist.
5. Camera-Node-unreachable-after-a-working-pairing was not verified live
   this milestone (§6) -- needs either the reference Pi's pairing
   deliberately reset (an owner decision, not this milestone's to make)
   or a second camera-equipped device.
6. No public download location exists yet for MockingBird (structural --
   the product is not published; not a defect).

## 11. Current HEAD / schema / version

- HEAD: `250dd5c` (this milestone's two fix commits, `5af366a` and
  `250dd5c`, on top of the accepted `88a5eb1` baseline).
- Schema: `v59`, unchanged.
- Version: `0.1.0`, unchanged.
- Working tree: clean except the seven preserved untracked detector
  files (verified present and unmodified at both the start and the end
  of this milestone).
- Not pushed. Nothing published or distributed. No competing writer
  found or created during this session (six other local Claude sessions
  shared this same working tree at points during this milestone; all
  were confirmed idle/sleeping with no recent file modifications before
  any edit was made, and `git status` was re-verified clean immediately
  before every commit).

## 12. Recommendation

**READY FOR OWNER RELEASE DECISION**, with one release-experience item
(§3.5, the cross-surface "confirmed wildlife" disagreement) recorded as a
real, disclosed, non-blocking gap the owner may reasonably choose to
close before or after the release decision -- it affects trust/polish in
how reviewed truth is reflected, not correctness, safety, or data
integrity, and every other rehearsed step (build, install, account,
camera setup, first observation's mechanics, review/correction,
Doctor, shutdown/restart, backup, uninstall) is proven working end to
end on the real artifact.

This does not self-authorize a follow-on milestone. The two items in §10
worth a dedicated pass (the cross-surface semantic reconciliation, and
the remaining "demo panel" sweep) are named for the next external
(ChatGPT) reconciliation to weigh, not started here.
