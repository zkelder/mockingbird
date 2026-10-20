# Owner-Only Release Polish & Acceptance v1 -- closure report

**Date:** 2026-09-29. **Classification: A** -- every scoped item is closed
with red-then-green tests, Core is green, and a fresh private candidate
was built, independently verified and accepted on native Windows. There
is one bounded, disclosed scope extension (§3).

**Candidate source:** `215069b3f95e54fee8c660d53013e665dd67877c`. It is
frozen as the candidate, and the record commit that follows changes only
documentation. Version `0.1.0`, schema `v61`. Nothing was pushed, tagged,
signed, published, uploaded or sent. Nobody was recruited or contacted.

## 1. Starting state and sequencing record

- **Starting state:** `main` at `c02ffd5`, as expected. The only untracked
  files were the seven protected detector files and `uv.lock`, and they
  are byte-identical at the end (`63f9e5ba`, `81cdff04`, `ade97d9d`,
  `a24aa6e2`, `e85a2315`, `548f0706`, `abad318b`; `uv.lock` `f36f26ba`).
- **Commit `130742a` (first, documentation only):** records the owner's
  decision additively in
  [release-execution-state.md](release-execution-state.md) (CURRENT PHASE,
  §3 and §6.S) and in [roadmap.md](roadmap.md) Gate G:
  - Gate G is **waived, not passed**.
  - The owner is the sole pre-release tester until public release.
  - The sequence is now *owner-only pre-release acceptance -> Final
    Release Hardening -> the one public launch*.
  - The lost independent setup, hardware and user-diversity evidence is
    disclosed.
  - The historical Gate G plan, participant package and reports are
    unchanged.

## 2. Corrections (each test was red before the fix)

| Item | Reproduced | Fix | Tests |
|---|---|---|---|
| **O-1** capture time unknown | Real recording without `creation_time` -> Visits at `1970-01-01T00:00:09Z`; the old frontend rendered "Dec 31, 7:00 PM" in America/New_York (browser spec red on the unmodified build). | Additive `capture_time_known` flag, decided **only by recorded provenance**: the candidate ledger's `provider_key` maps to `recorded_video` (or the Event is an acoustic candidate), **and** the source recording's own `MediaAssetModel.captured_at` is `None`. The date's age is never used, so a recording that genuinely states a 1970 time stays known. A `< 1971` prefilter only avoids queries. The flag is exposed on Visit/Event detail, Review Queue items, `StreamVisitSummary` (Today, Activity Library) and Bird Log label rows, representatives and gallery. The frontend's `formatCaptureDateTime` shows "Capture time unknown". Raw timestamps, ordering, evidence and truth are unchanged. No schema change. | `test_offline_ingest.py` (+5), `test_acoustic_ingest.py` (+2), e2e `unknown-capture-time-offline-evidence.spec.ts` |
| **O-1 (found while investigating)** research export | Offline evidence frames persist `1970 + offset` as their own `captured_at` (the frame-driven provider's epoch fallback), so the research export's `capture_timestamp_known` predicate ("evidence `captured_at` present") certified the placeholder as `recorded`. Reproduced red. | The same provenance fact is now also required. The record is still exported, with the existing `capture_timestamp_uncertain` recommendation. | `test_research_export_does_not_claim_a_recorded_capture_time_for_the_placeholder` |
| **O-2** offline evidence wording | An offline Visit said "No detections are attached to this manual media visit" (browser spec red). | `noDetectionRecordsMessage` distinguishes: offline analysis of an imported recording, live observation, sound analysis, manual/folder import. The offline case reads: "Found by offline analysis of an imported recording. No separate detection records are stored for this visit; review its saved evidence frames instead." `VisitDetail.acquisition_type` reuses the research mapping. No Detection rows or evidence are invented. | e2e spec (3 tests incl. a manual-import control) |
| **README-FIRST** | Four-step onboarding, Task-Manager-only stop, "Nothing is uploaded anywhere", no FFmpeg/BirdNET statement. | Rewritten: the five steps Welcome -> Account -> Storage -> Add a camera -> Start observing; Local Data -> *Shut down MockingBird* -> *Confirm shut down* as the normal stop, and Task Manager/restart only for a forced stop; "Your data stays on this computer" with the opt-in network features named (own cameras/Camera Node on the LAN, weather off until turned on, iNaturalist lookups, a web address you enter, phone access off by default); FFmpeg and BirdNET weights not included; uninstall and data retention kept accurate. | `test_local_product_packaging.py` +5, tied to `WIZARD_STEP_ORDER` and the `LocalDataPage.tsx` button labels; the ZIP's README equals the constant |
| **Midnight fixture** | `TZ` forced to local 00:20: `test_today_dashboard_shows_only_corrected_truth` failed (`pf-corrected` dropped out of Today). | The fixture anchors Visits at the previous local day's noon and queries Today with an explicit `local_date`, the way the browser already does. Production Today semantics are unchanged. | New `test_today_dashboard_corrected_truth_holds_just_after_local_midnight` (forces 00:20 via a synthetic `TZ`); file green at 00:01/00:05/00:20/00:59/23:59 and in UTC, New York, Auckland, Kiritimati, Pago Pago and Kolkata |

## 3. Deviations from scope (disclosed)

- **Sibling midnight test:** `test_acoustic_visit_appears_in_todays_confirmed_bird_count`
  in the same file had the identical defect and failed at local 00:05. It
  got the same one-helper fix. It is test-only and in the same fixture
  family.
- **Research export predicate** (§2): extended O-1 to the one export
  surface where the placeholder was asserted as a *recorded* time. This is
  a one-conjunct change using the same fact.
- **`docs/offline-recorded-media-observation-contract.md`:** added a
  "Capture-time presentation" section. It corrects the contract's
  implication that persisted offline evidence has `captured_at = None`.
- **Acoustic imported audio** with no capture time uses the same
  presentation, since it has the same epoch anchor and the same defect.

## 4. Validation

- **Focused:** every new test was red first. Affected backend suites (28
  files: offline/acoustic ingest, research/Camtrap/Darwin Core export,
  Today/dashboard, Review Queue (6 files), Wildlife Journal, Activity
  Library, multimodal, candidate review, packaging, release verifier,
  deploy): **576 passed, 0 failed**.
- **Frontend:** `tsc --noEmit` clean; `vite build` clean.
- **Browser (Playwright, 13 specs, 82 tests):** 80 passed, 2 failed. Both
  failures are pre-existing and not attributable:
  - `reviewed-product-loop.spec.ts` is the long-documented gap.
  - `review-queue-reviewed-tab.spec.ts` fails identically on the
    untouched `c02ffd5` source (all tracked `src`/`web/src` changes
    stashed and the frontend rebuilt).
  - The new spec was red on the old build and is 3/3 green.
- **Lint:** `ruff` reports 83 findings on the changed Python files before
  and 83 after -- the identical set, so nothing new.
- **Core (`scripts/verify_core.py`, at `215069b`):** **6249 passed, 0
  failed**, 4 skipped, 35 deselected, 11 xfailed (58m01s). This is the
  first local Core run with zero failures since the midnight fixture was
  first recorded.
- **Full gate:** not run. The only packaging change is the README text
  constant plus its tests. The built artifact was verified directly
  instead (§5).

## 5. Candidate artifacts (private, ignored `dist/`)

- **Windows Host** (`dist/owner-only-release-polish-v1-215069b/`):
  - `MockingBird-windows-x64.zip` SHA-256
    **`d1050b99d3eee93e0096e5ea5b6a3e982224860a4f904afa8a3892172f01bb9d`**.
  - `build_id 85b92328bb185cba`, `source_clean: true`, 19,284 files /
    4,923,721,175 bytes, embedded Python 3.12.7, unsigned.
- **Verification of the Host artifact:**
  - `SHA256SUMS` all OK.
  - `verify_release_artifact.py` -> `OK ... source git:215069b…, unsigned`.
  - Runtime, GPU and BioCLIP requirements, both model bundles, the native
    CUDA runtime and signing are **identical** to `2272126`. The SBOM has
    59 components, identical.
  - 212/212 packaged `mockingbird/*.py` files are byte-identical to
    `215069b`.
  - `README-FIRST.txt` equals `README_FIRST`.
  - No `ffmpeg.exe`/`ffprobe.exe` and no BirdNET model. `LICENSE` and
    `THIRD_PARTY_NOTICES.md` are present.
  - The only content delta against `2272126` is `README-FIRST.txt`,
    `api/main.py`, `api/schemas.py`, `repository/product_repository.py`,
    build metadata, and the rebuilt frontend bundle.
- **Camera Node** (`dist/owner-only-release-polish-v1-215069b-camera-node/`):
  - The wheel SHA-256 is
    `38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904`,
    **byte-identical** to the accepted wheel.
  - The manifest records `source_state git:215069b…`.
  - 15/15 modules and `install_camera_node.py` are byte-identical to
    `215069b`.
  - `SHA256SUMS` is OK.
  - **No Pi or hardware acceptance was performed or is claimed.**

## 6. Native-Windows acceptance (exact artifact, disposable home)

**Setup:**

- The ZIP was copied from Windows over the UNC path (a WSL 9p write
  failed with `ENOMEM` and was retried from the Windows side).
- Native `Get-FileHash` = `D1050B99…`, which matches.
- Native `tar.exe` extraction took 58 s and produced 19,284 files /
  4,923,721,175 bytes, exactly the manifest.
- Install at `D:\MBOP\install`, home at `D:\MBOP\home-a`, port 8151,
  launched with the shipped `Start MockingBird.vbs`.
- The six persistent developer `MOCKINGBIRD_*` variables were removed at
  process scope only.
- The real Edge browser ran headless with the America/New_York time zone.
- Port 8000 and the real `%LOCALAPPDATA%\MockingBird` were untouched (last
  write 2026-08-09, before and after).

**Results:**

- **Build identity:** `GET /api/product/instance` -> `git_commit
  215069b…`, `build_id 85b92328bb185cba`, matching the manifest.
- **First run:**
  - All five onboarding steps completed in the UI ("Setup step 2 of 5"
    is the Account step).
  - Doctor **HEALTHY** with no non-PASS checks.
- **Recorded-media import without capture metadata:**
  - The real 64 s reference-Pi field recording (ffprobe: no
    `creation_time`) was imported through Import Media.
  - `analyze-recorded`: 128 frames considered, 64 analysed, 2 Events / 2
    Visits, `capture_time_known: false`, `creates_truth: false`, 58.4 s.
  - The raw times are preserved (`1970-01-01T00:00:09Z` and `…:52Z`).
- **Presentation across surfaces:**
  - Review Queue, Visit Detail (both Visits), Event Detail, Activity
    Library and Today all show **"Capture time unknown"**.
  - **Zero "Dec 31" / "7:00 PM"** occurrences anywhere.
  - The manual-import control Visit keeps its real date and "manual media"
    wording.
- **Evidence wording:** Visit Detail shows "Found by offline analysis of
  an imported recording…". There is no "manual media visit" on either
  offline Visit. `detections: 0`, and there are 3-4 real evidence frames.
- **Truth:**
  - Both offline Visits were corrected to *Unknown Bird* with
    `review_origin: human`, `is_authoritative: true`, attributed to the
    signed-in administrator.
  - Bird Log then showed `confirmed_species_unresolved_visit_count: 2`.
  - An earlier driver call of mine omitted `review_origin`. The product
    correctly stored it as non-authoritative and displays it as
    "Unattributed origin (not reviewed truth)". It is shown in the
    evidence, not hidden.
- **Shutdown and restart:**
  - Local Data -> *Shut down MockingBird* -> *Confirm shut down*, twice
    via the UI: "Application shutdown complete", no remaining process,
    port free.
  - Each relaunch reported `previous_shutdown_clean: true` with all data
    intact.
  - A third stop through the same endpoint exited in 0.52 s.
- **Doctor after the instance stopped:** CLI `doctor --json` returned
  **HEALTHY**, exit 0.
- **Doctor while the instance is running:** CLI Doctor reports a DEGRADED
  "did not shut down cleanly" WARN. This is the previously disclosed Doctor
  Application-check limitation (running marker), not new, and was not
  changed here.
- **Browser errors:** 0 in both sessions.
- **Evidence:** 34 files (screenshots, JSONL, driver and scripts) in
  ignored `dist/owner-only-release-polish-v1-215069b-evidence/`.

## 7. Remaining limitations

- **Gate G is waived, not passed:**
  - There is no independent setup, hardware or user-diversity evidence.
  - Owner testing covers the owner's configuration only.
  - MockingBird must never be described as externally validated.
- **No live camera or Observation start/resume** was exercised on this
  exact build (no live camera attached; Pi not used). No new Camera Node
  or Pi evidence exists.
- **Surfaces not changed:** these still format raw times, but they either
  never receive an offline Visit or are aggregate labels:
  - the standalone Media library's `MediaAssetPreview` (the file's own
    `created_at` without Visit context)
  - Place Report / Insights / Taxon and Feature Story timestamps
  - Bird Log `place_context.observed_at`
- **Pre-existing, unchanged:**
  - `review-queue-reviewed-tab.spec.ts` and `reviewed-product-loop.spec.ts`
    failures.
  - The Doctor running-instance Application WARN.
- **Artifact status:** the build is unsigned, and no signing key exists or
  was created.

## 8. Classification and outcome

**A.** Candidate `215069b` is corrected and accepted on native Windows
within the scope above. The next step is the owner's own pre-release
testing and, when the owner chooses, Final Release Hardening or the
release decision. **Authorization returns to NONE.**
