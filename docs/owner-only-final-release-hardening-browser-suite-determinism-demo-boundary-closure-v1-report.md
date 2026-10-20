# Owner-Only Final Release Hardening -- Browser Suite Determinism & Demo-Boundary Closure v1 -- Report

**Date:** 2026-09-29. **Start:** `main` at record HEAD `9e0e113`. The
candidate source was `215069b`, `0.1.0`, schema `v61`. **Authorized by:**
ChatGPT global sequencing, after Reviewed-Truth Browser Closure v1 was
accepted at classification B. **Classification: A.**

**Commits** (local, not pushed):

| Commit | Content |
|---|---|
| `3f51e60` | Authorization record (docs only) |
| `ccb6131` | Reviewed history excludes demo labels (product fix and tests) |
| `02443ea` | Deterministic browser specs (test-only). **New candidate source.** |
| this report's commit | Closure record |

**Summary:**

- The complete default browser suite is **196/196** green.
- The Reviewed-history demo leak is closed, and both the browser and the
  packaged app show it.
- Packaged inputs changed, so a new private Windows candidate was built
  from `02443ea` and accepted on native Windows.
- Candidate `215069b` is **superseded**.

## 1. Task packet

- **Roadmap phase:** Final Release Hardening, owner-only (feature freeze;
  §6.S). Gate G stays **waived, not passed**. The owner is the sole
  pre-release tester.
- **Product flow improved:** Confirm -> Remember, and Discover ->
  Understand.
  - The Review Queue's reviewed history shows only the owner's own Review
    Decisions.
  - An insight alert lands on the right Place Story.
  - The browser gate that protects both is deterministic.
- **Why next:** the seven disclosed default-suite failures and the
  disclosed "Reviewed history" leak from Reviewed-Truth Browser Closure v1.
- **Files allowed:**
  - `web/e2e/*.spec.ts`;
  - the smallest production seam the leak required: the
    `GET /api/review-labels` read, `ProductRepository.list_review_labels`,
    the frontend API client and `ReviewQueuePage`;
  - one backend test file;
  - docs.
- **Non-goals:** as authorized. No features, O-1/O-2 reopening, weakened
  demo exclusion, detector/threshold/identification policy, Pi or Camera
  Node hardware, Gate G, signing, publishing or pushing.
- **Validation tier:**
  - The complete browser suite plus the three separate configurations.
  - Focused backend tests.
  - Full Core, because backend production code changed.
  - A rebuilt artifact with native-Windows acceptance, because packaged
    inputs changed.

## 2. Baseline (red, before any change)

`npm run test:e2e` at `3f51e60` (source identical to `9e0e113`): **187
passed / 7 failed** of 194. These are the same 7 that were disclosed.

| # | Spec / test | Failure at baseline |
|---|---|---|
| 1-2 | `broader-wildlife-maturity-review` x2 | `article.queue-card` first: element not found |
| 3 | `notification-preferences` "insight alert opens Place Story scoped to wildlife" | `kind` params: expected the 5 wildlife kinds, got `[]` |
| 4 | `review-queue-bulk-correct-stale-write` | `article.queue-card`: expected 1, received 0 |
| 5 | `review-queue-count-demo-exclusion` | `article.queue-card`: expected 1, received 19 |
| 6 | `review-queue-fast-review-keyboard` | "Filtered queue complete" heading not found |
| 7 | `today-report` quiet empty state | "Best moments" heading: expected 0, received 1 |

## 3. Root cause and fix per failure

**1-2, 4. Demo-Stream fixtures.**

- **Root cause:** all three imported onto `stream-backyard-feeder`. By
  contract, `_visible_review_queue_items` drops demo-Source items from
  every tab, including "Sample and older activity". So there was never
  anything to review.
- **Fix:** each spec now owns a real Source (`POST /api/sources`).
  - Bulk-correct also creates two real Zones for its concurrent Zone move.
  - Each spec scopes the queue to its own data and asserts the truth it
    saved: `reviewed_label` `unknown_animal` / `false_positive`, and the
    stale write stays `needs_review` with the Zone move authoritative.
- **Hidden drift found once the fixture reached the product:**
  - Bulk-correct's stale-write sentence changed from `--` to an em dash in
    `f2a8f83` (UI/UX & First-Run Adoption v1). The expected text was
    updated to the product's current copy; the assertion is otherwise
    unchanged.
  - Fast Review renders its "Saved <label>." confirmation, with Undo, only
    on the **next** item's panel. After the last filtered item it switches
    to "Filtered queue complete", which does not repeat it. With one
    Visit, the confirmation was visible only while the post-save refresh
    ran. This reproduced red under a busy prefix run. The spec now owns
    two Visits, so the confirmation is shown deterministically on the
    second. (Product finding F-1, §8.)

**5, 6. Shared-instance accumulation.**

- **Count spec:** it now scopes the queue to its own Visit. The response's
  `review_queue_count` is a global number by design, so the spec reads the
  real outstanding count from `/api/review-queue/summary` (sum of
  `needs_review_by_stream`, the same demo-excluded visible set) just before
  the correction. It asserts exactly N-1, with a non-digit boundary so
  "10" never matches "0". A fresh instance still asserts "0 items".
- **Fast-review-keyboard spec:** Fast Review walks the whole filtered
  queue, so it now filters to its own Visit (`Start Fast Review (1)`)
  before the keyboard-only journey.

**7. Today empty state.**

- **Root cause:** the spec mocked the report but passed the real Dashboard
  `today` lists through, and other specs' today-dated Visits filled
  "Best moments".
- **Fix:** `mockDashboardHeadline` accepts `todayOverrides`. The empty-day
  test supplies empty `best_moments`, `new_today` and `recent_regulars`,
  matching the spec's own stated synthetic-fixture design.

**3. Notification deep link: stale test assumption, not a product defect.**

- **Diagnosis:** `openAlertAction` has two deliberate `open_place_story`
  paths.
  - Calm Attention & Notifications v1 (Lane D) scoped a category-only
    insight to its Place Story group.
  - Place Story Deep Dives & Representative Evidence v1 (`33d9f5f`) then
    routed an action carrying a precise `taxon_label` to that taxon's own
    Story. This closed Lane D's own listed follow-up, "precise per-taxon
    deep links (today scoped to a category group)".
  - The fixture carried `taxon_label: "northern_cardinal"`, so the product
    correctly took the newer route and requested
    `/api/place/story?taxon=…`.
- **Verification:** both paths were checked in a real browser, and later
  in the packaged app (§6).
- **Fix:** one test per path.
  - Category-only -> `/place-story` with the 5 wildlife kinds and no taxon.
  - Taxon -> `/place-story/taxon/northern_cardinal` with `taxon=` and no
    kinds. This path previously had no browser coverage.

**Latent races found while proving determinism (all test-only):**

- **A. `notification-preferences` live delivery.**
  - **Symptom:** "A new sustained health alert delivers…" failed 1 in 8
    during the first shared-instance stress run.
  - **Root cause:** the mock switched on "the second
    `/api/alerts/unread` request". On Today, `TodayAttentionSummary` makes
    that request too, and the app shell always mounts **two**
    `AlertsControl` pollers (mobile header and sidebar). Mount order
    decided which component consumed "poll 1".
  - **Hidden consequence:** the three "never delivers" tests could read
    `__deliveredNotifications` before the poll they judge had run, so they
    could pass vacuously.
  - **Fix:** every request is served `[]` until the test has seen each
    poller's first poll arrive (the count of mounted `.alerts-control`),
    then explicitly releases the alert. Each test then waits for the Alerts
    badge on every poller; `AlertsInbox.refresh` sets it in the same step
    that makes the delivery decision.
  - The delivery test asserts one distinct notification tag (the alert's
    own id) and one delivery per poller. (Product finding F-2, §8.)
  - **Mutation check:** forcing `shouldDeliverForegroundNotification` to
    return `true` turns exactly the three "never delivers" tests red.
- **B. `dataset-export-download`.**
  - **Symptom:** red in the first full run after the fixes. The page opens
    with the seeded export's manifest preloaded, so "Download manifest
    JSON" is live before the spec's own export exists. With more reviewed
    data on the instance (the corrected specs now really save truth),
    generation took long enough for the click to download the seeded
    manifest.
  - **Fix:** wait for "Reviewed local dataset manifest generated in
    memory.", which the page sets in the same update as the new manifest.
    Reproduced red in the alphabetical prefix run, then green 32/32.
- **C. Demo controls under repurposing.**
  - **Root cause:** camera-controls, observation-panel, doctor,
    live-preview and dashboard specs deliberately repurpose
    `source-backyard-demo` into a real camera. By contract
    (`_real_source_condition`) its seeded activity is then real history.
    In the full run, 16 demo-Stream Visits and the squirrel label
    correctly counted as real, which broke the new demo controls.
  - **Fix:** each demo control first returns the seeded Source to its
    `demo` provider through the ordinary
    `PATCH /api/sources/{id}/provider-configuration`. It owns the state it
    asserts on, and nothing depends on execution order.

## 4. Reviewed-history demo leak (product fix, `ccb6131`)

- **Reproduced:**
  - **Browser:** the new spec was red on the unfixed build. Its own entry
    was visible (the positive control passed first), and
    `Record: event-squirrel-ground-001` was listed.
  - **Native:** on the packaged `215069b` (§6), after the sample
    walkthrough was restored, Reviewed history read "**2 reviewed**" and
    listed the squirrel as "Correction truth".
- **Root cause:** `CorrectionAuditPanel` read the raw, demo-inclusive
  `GET /api/review-labels`.
- **Fix:**
  - `GET /api/review-labels` gains an additive, opt-in
    `real_sources_only`. `ProductRepository.list_review_labels` filters
    through the existing `_real_stream_ids` seam: Visit targets via their
    Event's Stream, and Event targets directly.
  - The default stays demo-inclusive, for raw/audit access and the many
    existing callers.
  - `ReviewQueuePage` opts in. This also removes demo labels from its
    recent-label helper.
  - Classifier Readiness (an Advanced diagnostic) and the per-Stream
    timeline keep the raw read.
- **Unchanged:**
  - truth resolution (`_effective_review_label_models`) and the
    Reviewed-truth boundary;
  - seed records (not deleted or rewritten);
  - schema.
  - A repurposed demo Source's labels count as real, for parity with
    every other demo-exclusion site.
- **Tests:**
  - **Backend:** 4 tests in `tests/test_demo_source_exclusion.py`. Two were
    red before the fix: the demo event and demo-Visit human labels leaking,
    and a non-empty fresh-install read. The raw default and
    repurposed-source parity are pinned.
  - **Browser:** `review-queue-reviewed-history-demo-exclusion.spec.ts`.
    - Positive control: a real Source's human correction is listed as
      "Correction truth: Northern Cardinal".
    - Negative control: the seed label is absent, after first proving it
      is present in the raw read (not vacuous).

## 5. Validation

**Browser** (`web/dist` rebuilt each time; `run-playwright.mjs` gives each
invocation a fresh isolated instance):

| Run | Result |
|---|---|
| Baseline complete suite | 187 passed / 7 failed (§2) |
| Each affected spec alone, fresh instance (final versions) | all green: history 1, count 1, bulk 1, broader 2, dataset-export 1, fast-review-keyboard 1, notification 12, today-report 19 |
| Shared-instance stress 1: 240-Visit seed (30 real Visits x 8, a third reviewed; page size 25) + all affected specs, `--repeat-each=8` | 303 / 304; the 1 failure was race A, since fixed |
| `notification-preferences`, `--repeat-each=20`, one instance | **240 / 240** |
| Shared-instance stress 2 (final specs): 150-Visit seed + `observation-panel` (repurposes the demo Source) + every changed spec, `--repeat-each=5` | **210 / 210** |
| **Complete default suite (final)** | **196 / 196**, no skip, quarantine or retry (`retries: 0`) |
| Onboarding / bounded Review Queue / bounded media configs | 6/6, 4/4, 2/2 |

- **196 = 194 + 2:** the new Reviewed-history spec, plus the notification
  insight test split into its two paths.
- The throwaway stress-seed spec was never committed and was deleted after
  each run.

**Frontend and backend:**

- `tsc --noEmit` clean; `vite build` clean.
- `ruff`: 0 new findings (the changed files' existing counts are identical
  at HEAD and after).
- Focused backend tests: `test_demo_source_exclusion`, `test_api`,
  `test_persistence`, `test_review_queue*` -> **224 passed**.
- **Full Core** (`scripts/verify_core.py` on committed `02443ea`):
  
  - **Run 1:** 6252 passed, **1 failed**, 4 skipped, 35 deselected, 11
    xfailed (42:07). The failure was
    `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success`:
    `_run_until`'s 3.0 s wall-clock deadline expired on a machine shared
    with an unrelated workload. This is the load-induced flake of record
    (CI & Core Validation Closure v1). It imports only
    `mockingbird_node.transport_*`, which is byte-identical to `9e0e113`.
    It passed 5/5 alone, and its file went 7/7, then 2 failed / 5 passed,
    then 7/7 on re-runs. The timing sensitivity reproduces intermittently
    and is unchanged by this milestone. Run 1 is not claimed green.
  - **Run 2** (same committed tree): **6253 passed, 0 failed**, 4
    skipped, 35 deselected, 11 xfailed (40:39).

## 6. Artifact (packaged inputs changed -> new candidate)

**Host ZIP** (`dist/browser-suite-determinism-v1-02443ea/`, private,
ignored, unsigned):

- `MockingBird-windows-x64.zip` SHA-256
  **`785f3f37d206cf5de1078c1ef6ad193f23b8152c406c82d3111b8fb7e0b7b462`**.
- `build_id 5200ec77a7221902`, `source_clean: true`, source
  `git:02443ea71529f5dae50ca2eb731db3a73c5038ab`. 19,284 files /
  4,923,723,141 bytes.
- Built with `scripts/build_local_product.py`, no skip flags.

**Verification:**

- `SHA256SUMS` all OK.
- `verify_release_artifact.py` -> `OK … source git:02443ea…, unsigned`.
- All 212 packaged `mockingbird/*.py` files are byte-identical to
  `02443ea`.
- SBOM: 59 components, identical to `215069b`.
- Manifest differences from `215069b`: only build identity, byte total,
  SBOM hash, `source_state` and the ZIP hash.
- Tree differences from `215069b`: only `api/main.py`,
  `repository/product_repository.py`, `build_info.json`, the rebuilt
  frontend bundle (`web_dist/`, including its source fingerprint), and
  wheel `RECORD`/`direct_url.json`.

**Camera Node:** `git diff 215069b..02443ea` touches nothing under
`src/mockingbird_node` or its build/installer scripts. The accepted wheel
`38dfac47…` stays valid. No Node rebuild, and no Pi or hardware
acceptance is performed or claimed.

**Native-Windows acceptance** (exact ZIP, disposable home):

**Setup:**

- Copied from the Windows side over UNC (26 s). Native `Get-FileHash` =
  `785F3F37…`, which matches.
- `tar.exe` extraction took 70 s and produced 19,284 files /
  4,923,723,141 bytes, exactly the manifest.
- Install `D:\MBBS\install`, home `D:\MBBS\home`, port 8152, launched with
  the shipped `Start MockingBird.vbs`.
- The six developer `MOCKINGBIRD_*` variables were removed at process
  scope only.
- Real Edge, headless, America/New_York.
- Port 8000 was free and untouched. `%LOCALAPPDATA%\MockingBird` was
  untouched (last write 2026-08-09, before and after).

**Results:**

- **Identity:** `GET /api/product/instance` -> `git_commit 02443ea…`,
  `build_id 5200ec77a7221902`.
- **First run:**
  - Onboarding completed through the UI (manual-media camera).
  - The wizard removes the sample walkthrough once a real camera exists,
    so the fresh home had no demo Source and Reviewed history was absent.
  - A reference-Pi still was imported through **Import Media**, then
    corrected to *Northern Cardinal* through **Review Queue -> Fast
    review -> Save & Next**.
  - The result is `review_origin: human`, `is_authoritative: true`.
- **Reviewed history, positive:** "Reviewed history · 1 reviewed", the
  owner's Visit, "Northern Cardinal".
- **Reviewed history, negative (restart phase):**
  - **Local Data -> Reset demo data -> Confirm reset** restored the sample
    walkthrough beside the real camera. The raw read now contains
    `review-label-squirrel-001`.
  - Reviewed history still read "**1 reviewed**", with no squirrel and no
    `event-squirrel-ground-001`.
  - The same driver on the packaged `215069b` read "**2 reviewed**",
    listing the squirrel: native red/green.
- **Deep links:** the packaged frontend routed as follows.
  - A taxon-bearing insight -> `/place-story/taxon/northern_cardinal`
    (`taxon=northern_cardinal`).
  - A category-only insight -> `/place-story` with the 5 wildlife kinds.
  - The alerts were answered at the browser boundary, because a fresh
    install has no Place Story insight history.
- **Launch, shutdown, restart:**
  - Three in-app shutdowns (Local Data -> Shut down MockingBird -> Confirm
    shut down): each left "Application shutdown complete", 0 remaining
    processes and the port free.
  - The relaunch reported `previous_shutdown_clean: true` with the
    correction intact.
  - CLI `doctor --json` on the stopped home: **HEALTHY**, exit 0, both
    times.
- **Browser errors:** **0 uncaught page errors, 0 HTTP 5xx.** Console
  resource messages, all accounted for:
  - `401 GET /api/auth/session` while signed out before the account exists
    (expected);
  - `404 GET /api/camera-nodes/pending-setup` during onboarding (the
    endpoint's designed "nothing to resume" answer);
  - `404 POST /api/alerts/<synthetic id>/read` from the simulated alerts
    (a method artifact).
  - The two product ones occur identically on `215069b`. Signed-in
    navigation of Today, Review Queue, Import, Alerts, Place Story, taxon
    Story and Local Data produced no 4xx/5xx at all.
- **Evidence:** screenshots, JSONL, drivers, scripts and every browser log
  are in ignored `dist/browser-suite-determinism-v1-02443ea-evidence/`.

## 7. Boundaries kept

- No weakened assertion, skip, quarantine or retry.
- No execution-order dependence: every scoped spec owns its data, and
  demo controls own the demo state.
- Demo exclusion is only strengthened.
- Seed records, truth resolution and schema (`v61`) are unchanged.
- No detector, threshold or identification-policy change.
- No Pi, Camera Node or Gate G work.
- Nothing signed, published, uploaded, tagged or pushed.
- The seven protected untracked files and `uv.lock` are untouched. Only
  explicit paths were staged.
- Accepted O-1/O-2 work was not reopened.

## 8. Remaining limitations and findings (disclosed, not fixed)

- **F-1: Fast Review drops Undo at queue end.** After the last filtered
  item is saved, "Filtered queue complete" does not show the "Saved
  <label>." / **Undo last correction** block. The correction stays
  reachable and editable from Visit Detail. This is a small UX gap and is
  outside this brief.
- **F-2: two always-mounted alert pollers.** The app shell mounts one
  `AlertsControl` in the mobile header and one in the sidebar, so unread
  and preference reads run twice a minute, and a new immediate alert calls
  `new Notification` once per poller. Both use `tag: alert.id`, which the
  Notification API coalesces into the one notification a person sees. The
  cost is efficiency, not a user-visible defect.
- **Console resource 404/401** during first run, as in §6. These are
  pre-existing and designed.
- The **deep links** were proven natively with simulated alerts only. No
  real Place Story insight alert exists on a fresh install.
- **Gate G is waived, not passed.** There is no independent setup,
  hardware or user-diversity evidence, and MockingBird must never be
  described as externally validated. The build is unsigned.

## 9. Classification

**A.**

- All seven failures are root-caused and closed without weakening,
  together with three latent races that determinism testing exposed.
- The complete default suite is 196/196, repeatable under stress, and all
  three separate configurations pass.
- The demo-boundary leak is closed at the product seam, with positive and
  negative controls in the browser and on the packaged app.
- Full Core is green on the rerun, and run 1's single failure is the
  unrelated load-induced flake of record.
- The new candidate `02443ea` / `785f3f37…` is verified and accepted on
  native Windows.

**Authorization returns to NONE.**
