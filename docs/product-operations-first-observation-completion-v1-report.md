# Product Operations & First-Observation Completion v1

**Type:** Sole authorized implementation milestone, directly authorized by
the external (ChatGPT) global-roadmap reconciliation following its
acceptance of *Release Reliability & First-Run Recovery v1* at `7b7e282`,
schema v59. Supersedes the previous broad "Hardware & Recovery Acceptance"
authorization and the unstarted "Storage Pressure & Survival Completion"
authorization.

**Classification: A** -- see "Classification," at the end.

---

## 0. Executive summary

Four parallel, read-only investigation agents (Doctor/diagnostics API+UI;
first-run wizard/source readiness; first-observation product loop; storage
-survival contract), plus direct reading of the governing docs, found that
three of the five scoped areas were already substantially complete or
correct: the first-observation product loop (Observe -> Discover ->
Understand -> Confirm -> Remember -> Improve) had zero reproduced defects on
independent re-verification; storage survival's core mechanics (disk
-pressure ladder, transactional-rollback safety, bounded retention/spool/
cleanup-history/logs) were genuinely complete, re-confirming Lane M's
closure rather than finding new work. The real, concrete gaps were: Doctor
(a mature, well-tested diagnostic engine) had zero API or UI exposure,
CLI-only; two independent audits converged on the identical concrete gap --
Camera Node storage/hardware-quality facts (shipped last milestone) never
reach a human anywhere; and a genuine, reproduced cross-surface honesty
defect where three of four surfaces reading the same camera-health
computation disagreed about a camera-connected-but-detector-failed Camera
Node Stream.

See
[product-operations-first-observation-completion-v1-contract.md](product-operations-first-observation-completion-v1-contract.md)
for the full pre-implementation contract this report closes against.

**Implemented:**

1. **Doctor API + UI** (§1): `GET /api/product/doctor` (Administrator-tier,
   thin passthrough wrapper around the existing, unmodified `run_doctor()`
   -- `DoctorReport` is already a Pydantic `BaseModel`, returned directly as
   the response model, no second schema) and a new `DoctorPage.tsx`
   (PASS/WARN/FAIL/SKIPPED presentation, calm recovery-action links to
   existing Local Data/Cameras surfaces, loading/error states), reachable
   from primary nav (Administrator-gated, mirroring the existing "Users"
   entry).
2. **Camera Node hardware-health visibility** (§2): a bounded, live, on
   -demand, non-persisting `GET /api/streams/{id}/camera-node-hardware
   -health` (mirrors `CameraSetupPage`'s existing "Check the picture"
   pattern -- no schema migration, no change to Doctor's own read-only/DB
   -only design invariant), surfaced on the Camera Configuration page.
3. **Two reproduced cross-surface health-honesty defects, fixed** (§3):
   `get_stream_camera_health`/`get_camera_configuration_edit` and the Yard
   Map never received the `engine_terminally_unavailable`/`engine_
   unavailable_message` bridge only `dashboard_summary` had -- a camera
   -connected-but-detector-failed Camera Node Stream showed the real alert
   on the Dashboard while showing a stale calm "stopped" state on Camera
   Configuration and Yard Map, one click apart. `ObservationControlPanel`'s
   own needs-attention detail box was separately hardcoded to
   `camera_message` regardless of which subsystem actually failed.
4. **One real fault-injection test** (§4): a literal `OSError(errno.ENOSPC,
   ...)` injected at the real Host media-write function, proving --
   through the real, unmodified `create_candidate_visit_from_proposal` /
   `_create_candidate_visit_locked` transactional path and the real
   `CandidateVisitAuthorityAdapter` -- atomic rollback, a typed `"failed"`
   outcome, and no retry. This exercises a branch previously marked
   `# pragma: no cover - defensive repository boundary` in production code
   -- genuinely new coverage, not a redundant test.

**Verified, not reimplemented:** the first-observation product loop (Today/
Review Queue/evidence/Bird Log/abstention honesty) and storage survival's
core mechanics -- documented with evidence in §5/§6 rather than duplicated.

**One real, previously-unknown defect was found and fixed by this
milestone's own Core-gate validation, not shipped**: the new fault
-injection test's own absolute-zero-Visit-count assertion was wrong --
`ProductRepository.__init__` unconditionally seeds two demo Visits into
any fresh database, which the test's first version did not account for.
Investigated to a confirmed root cause (not assumed pre-existing, since
the test is new this milestone), fixed by comparing before/after counts,
and re-verified non-vacuous. This was a bug in the new test itself, never
in production code -- see §7.

**Validation:** Tier 1/2 backend 337 passed, 0 failed (all directly-relevant
files, fresh this session); full existing + 9 new Playwright e2e 184
passed / 2 failed, both independently confirmed pre-existing via `git
stash` bisection against the unmodified baseline, unrelated to this
milestone's changes; `ruff check` zero new findings (confirmed via `git
stash` bisection, not merely inspection); `tsc --noEmit`/`vite build`
clean. Full Core (accepted, final attempt): 5985 passed / 1 failed
(confirmed pre-existing) / 4 skipped / 35 deselected / 11 xfailed -- see
§7 for the full three-attempt record, including one real, previously
-unknown defect this milestone's own Core-gate validation found and fixed
in its own new test (never in production code).

---

## 1. Area 1: In-app diagnostics and recovery

### What already existed

`src/mockingbird/diagnostics/doctor.py`: 16 checks, a mature, well-tested,
privacy-safe, read-only engine (`run_doctor()`), CLI-only (`python -m
mockingbird doctor`). `DoctorReport`/`DoctorCheckResult` were already real
Pydantic `BaseModel`s. Zero HTTP or frontend exposure -- confirmed by
direct grep, not assumed.

### What was implemented

- `GET /api/product/doctor` (`src/mockingbird/api/main.py`), Administrator
  -tier (`src/mockingbird/api/auth.py`, same bucket as `/api/product/
  shutdown`). `doctor.py` itself is unmodified -- every reuse point is an
  import.
- `web/src/pages/DoctorPage.tsx`: overall-status banner, one row per check
  (component, status badge, summary always shown, detail/diagnostic
  -context behind a disclosure, `user_action` when present), a Refresh
  action, honest loading/error states. Recovery actions are calm
  navigation links to existing, already-safe control surfaces (Local Data
  for storage/backup/database checks, Cameras for Camera Node checks) --
  no new mutating control was added; the existing "Shut Down MockingBird"
  action already lives on Local Data.
- Nav: `{ page: "doctor", label: "Doctor", minRole: "administrator" }`,
  mirroring the existing "Users" admin-gated entry exactly; route `/doctor`.

### Design decisions

- **Auth tier: Administrator**, by direct analogy to `/api/product/
  shutdown` and the existing Administrator "Storage / retention / backup /
  recovery" bucket -- Doctor exposes local filesystem paths, schema state,
  and Camera Node structural facts, and its own recovery-action links point
  at Administrator-tier controls, so keeping the read tier aligned avoids a
  page that suggests an action a lower-tier viewer cannot take. No
  documented target tier existed before this milestone (the investigation
  agent confirmed this was a genuinely open design choice, not merely
  undocumented) -- resolved here, not escalated, since clear precedent
  existed.
- **"UNAVAILABLE" vocabulary**: the governing brief's own phrase; Doctor's
  actual, accepted contract vocabulary is `SKIPPED`. The backend enum is
  unchanged (reuse, not rename, per the contract's own instruction); the
  frontend renders `SKIPPED` as the label "Unavailable."

---

## 2. Area 1/4 overlap: Camera Node hardware-health visibility

Two independent investigation agents (one auditing Doctor, one auditing
storage survival) converged, unprompted, on the identical concrete gap:
Release Reliability & First-Run Recovery v1 shipped real `storage`/
`hardware` facts on the Camera Node's own `/node/v1/health`, but nothing on
the Host ever polls it -- not Doctor (by explicit, correct design: it never
makes a live network probe of a paired Camera Node), not any other route,
not the frontend.

### Implemented

A bounded, live, on-demand, non-persisting `GET /api/streams/{id}/
camera-node-hardware-health` (`main.py`), reusing the existing, unmodified
`CameraNodeClient.health()` (`source_providers/camera_node.py`, no change)
-- mirrors `CameraSetupPage`'s already-established "Check the picture"
pattern rather than inventing a persistence-plus-migration mechanism the
prior milestone explicitly judged too large for its own bounded scope.
Surfaced on the Camera Configuration page (`CameraConfigurationPage.tsx`),
gated to `provider_key === "camera_node"`. Defensive parsing
(`_parse_camera_node_live_storage`/`_parse_camera_node_live_hardware`)
degrades a malformed/unexpected Node response to `None` field-by-field,
never a 500.

**Deliberately not built:** durable Host-side persistence of these facts
(a `CameraSourceModel` schema migration). This milestone's contract
explicitly ruled this out in favor of the smaller, precedented live-check
design; Doctor's own DB-only design invariant is preserved unmodified.

---

## 3. Area 2: First-run and source readiness

### What already existed

A real 5-step onboarding wizard with server-side resume; real, working
per-provider connectivity confirmation for every source type; detector/GPU
readiness already honestly shown at the wizard's own `observe` step. Rich
backend readiness data (`observation-status`, `camera-health`) already
existed but was under-surfaced.

### Reproduced defects, fixed

1. **Cross-surface health contradiction.** `_camera_health_summary_from_
   models` (`product_repository.py`) is called from four sites; only
   `dashboard_summary()` threaded `engine_terminally_unavailable`/
   `engine_unavailable_message` (the accepted Lane C fix).
   `get_stream_camera_health()` (backs both `GET /api/streams/{id}/
   camera-health` and the Camera Configuration page) and
   `_yard_map_activity_summary()` (Yard Map) did not. **Fix:** a new,
   single-fetch `_resolve_engine_terminal_status` helper factored out of
   `_dashboard_runtime_by_stream`'s own identical inline computation
   (behavior there unchanged, proven by the pre-existing Dashboard-honesty
   test suite passing unmodified), threaded into all three remaining call
   sites via new optional repository-method parameters defaulting to the
   prior behavior exactly.
2. **`ObservationControlPanel`'s needs-attention detail box** was
   hardcoded to `status.camera_message` regardless of which subsystem
   actually failed -- for a connected camera with a failed engine, it
   showed the reassuring "Camera Node is paired and configured." directly
   below the panel's own correct top-line message. **Fix:** reuse
   `status.message` (already resolved with the correct precedence)
   instead of re-deriving a second copy of the same logic client-side.

Both fixes were independently proven RED (failing against the unmodified
baseline, via `git stash` bisection) before GREEN against the fix -- see
§7.

### Considered, not built

A single consolidated "configured -> connected -> capturing -> producing
observations" page, replacing the four existing surfaces. Judged
disproportionate to this milestone's bounded scope and doctrine's "do not
turn this into a giant redesign" boundary: the concrete defect was the
three surfaces *disagreeing*, not that multiple surfaces exist. With the
plumbing fix above, the four surfaces are now honest and mutually
consistent; Stream Detail's own `ObservationControlPanel` remains the
richest single readiness view (camera/engine split, diagnostics), now
internally correct.

---

## 4. Area 4: Storage survival, bounded completion

### Independently re-verified (not reimplemented)

A real, tested, four-tier disk-pressure ladder; transactional rollback on
any write failure (zero partial commits, proven architecturally and now by
real fault injection -- see below); the one retry policy in the
persistence path explicitly never retries a non-contention failure; the
opt-in transport spool has a real, tested disk-floor guard; the previously
-disclosed unbounded `storage_cleanup_history` gap is already fixed;
the Host log file is genuinely bounded. This independently re-confirms
Lane M's `CLOSED -- RELEASE-CRITICAL` status against direct code evidence,
not mere citation of the prior claim.

### Implemented

One real fault-injection test (`tests/test_candidate_visit_adapter.py::
test_disk_full_write_failure_rolls_back_atomically_and_is_not_retried`): a
literal `OSError(errno.ENOSPC, "No space left on device")` injected at
`ProductRepository._write_media_file` -- the exact function the
independent audit named as the real gap (every existing test proved the
*mechanism* generically via a bare simulated `ValueError`; none proved it
for the real shape a genuinely full disk produces). Proves, through the
real, unmodified transactional write path and the real
`CandidateVisitAuthorityAdapter`: atomic rollback (zero Visit/
ObservationCandidateVisit/MediaAsset rows survive), a typed `"failed"`
outcome (never a crash), and no retry. **This exercises a branch
previously marked `# pragma: no cover - defensive repository boundary` in
production code** -- confirmed by direct inspection before writing the
test, not assumed; genuinely new coverage.

### Explicitly not reopened

Orphan-media/no-DB-owner detection and the missing Doctor cleanup-outcome
signal: both real, both already disclosed across three-plus prior
milestone reports and `release-execution-state.md` §6 Lane M as
low-materiality and *deliberately* not reopened. No deletion policy or
threshold was invented or changed anywhere in this milestone.

---

## 5. Area 3: First-observation product loop -- verification only

An independent code-reading audit (not merely re-trusting Lane C's own
closure claim) traced Today's sparse-state CTAs at every stage, Review
Queue's suggestion/abstention presentation and both real correction
-mutation paths, evidence visibility (including the same-frame classifier
-evidence panel), Bird Log's confirmed-only inclusion rule, and the backend
abstention contract end to end (a genuine abstention never persists a
fabricated `SpeciesSuggestionModel` row). Five specific claims from the
prior Lane C closure report were independently re-verified against current
code and held. **No reproducible defect was found.** This area closes on
verification evidence, per this milestone's own "if already complete,
document the evidence" instruction -- see the full audit trace in the
contract doc's Area 3 section.

---

## 6. Area 5: Product polish and integration

Scoped strictly to what Areas 1-4 touch: honest loading/empty/error states
on the new Doctor page (mirrors `UsersPage.tsx`'s established skeleton);
consistent status presentation (`StatusPill`, no new visual language); the
new Camera Node hardware-health panel matches the existing card/section
conventions (`.doctor-check-row` added to the shared card-style selector
alongside `.metric-card`/`.event-card`/etc., not a new visual system). No
unrelated redesign.

---

## 7. Validation

### Backend (Tier 1/2, fresh this session)

337 passed, 0 failed, across every directly-relevant file: the two new
test files (`test_product_operations_api.py`, `test_camera_health_cross
-surface_honesty.py`), the extended `test_candidate_visit_adapter.py` and
`test_local_identity_multi_user.py`, plus every camera-health/dashboard/
yard-map/doctor/camera-node/node-compatibility file the changes touch or
could plausibly affect.

### Full Core

**First attempt** (started 2026-09-08 23:56 EDT, ran 38m54s, crossing local
midnight into 2026-09-09 partway through): 5979 passed / **6 failed** / 4
skipped / 35 deselected / 11 xfailed. This exceeded the documented 4-failure
baseline, so every failure was individually investigated rather than
assumed pre-existing. **Five of six were directly, rigorously confirmed
identical against the exact unmodified baseline via `git stash`
bisection** (byte-identical assertion failures, same expected/actual
values) -- the already-known `test_place_biodiversity_summary_repository.py`
pair and `test_place_change_summary_repository.py::test_api_round_trip_
exposes_change_detection_fields`, plus two newly-reproduced-but-explicable
ones, `test_everyday_discovery_ux_closure.py::test_today_dashboard_shows_
only_corrected_truth` and `test_stream_playback_contract.py::test_
dashboard_summary_uses_reviewed_truth_and_bounded_safe_visits`, both
"today"-relative assertions that fail identically on the unmodified
baseline. **The sixth**
(`test_everyday_discovery_ux_closure.py::test_acoustic_visit_appears_in_
todays_confirmed_bird_count`) passed in isolation and within its own file,
both before and after this milestone's changes -- traced to the test's own
design: it computes `observed_at=datetime.now(UTC) - timedelta(minutes=15)`
and separately queries the Dashboard's own "today" cutoff a few statements
later, an inherent ~15-minute vulnerability window around local midnight
that this specific 39-minute run's real, unlucky timing crossed. **None of
the six is a regression from this milestone's changes.**

**Second attempt** (same calendar day, no midnight crossing): 5981 passed
/ **5 failed** / 4 skipped / 35 deselected / 11 xfailed. Three were the
same already-documented baseline flakes. A fourth,
`test_transport_worker.py::test_retryable_failure_returns_item_to_failed_
retryable_and_eventually_succeeds`, is a different test within the same
file `release-execution-state.md` §14 already documents as carrying a
load-induced timing flake (`test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success`) -- consistent with that
already-known flaky-file class, not investigated further as a new,
distinct issue.

**The fifth was this milestone's own new fault-injection test failing**,
investigated immediately and fully, not assumed pre-existing (it cannot
be -- it did not exist before this milestone). Root cause, confirmed by
direct inspection: `ProductRepository.__init__` unconditionally calls
`seed_if_empty()`, which seeds exactly two demo Visits
(`demo_data.seed_product_data()`, confirmed by direct invocation --
deterministic, not random or date-dependent in count) into any genuinely
fresh database -- including this test's own `tmp_path`-isolated fixture,
identical to every other test in the file. The new test's own assertion,
`assert session.scalar(select(func.count(VisitModel.id))) == 0`, was
therefore never a safe check of "atomic rollback," only ever an
accidentally-passing check of "did the demo seed count happen to be
absent" -- a real bug in *this test itself*, not in production code (the
production rollback behavior was never in question; the two other tables
checked in the same assertion block, which are not seeded by demo data,
correctly returned 0 in both runs). Independently confirmed this was a
latent flaw the first Core run's own particular test-execution order
simply did not happen to expose, not new intermittent flakiness in
production code: a direct, unmocked call to `demo_data.seed_product_data()`
reproduces exactly 2 Visits on every invocation, and a separate scratch
script proved the counting mechanism itself is fully sensitive to real
change (2 -> 3 across one genuine, unfaulted candidate-Visit creation).
**Fixed** by comparing before/after counts across the fault-injection
attempt instead of assuming an empty starting database -- proven correct
by 5 consecutive isolated re-runs and re-confirmed non-vacuous (the
counting mechanism does detect a real created Visit when the fault is not
injected). See `tests/test_candidate_visit_adapter.py`.

**Third (final, accepted) attempt**, with the test fix applied, same
calendar day (43m51s): **5985 passed / 1 failed / 4 skipped / 35
deselected / 11 xfailed.** The one failure
(`test_place_change_summary_repository.py::test_api_round_trip_exposes_
change_detection_fields`) is the same already-documented, already
-bisected-in-this-session pre-existing flake (§14's recurring
`'insufficient_recent_coverage' == 'higher_recent_presence'` pair);
`test_place_biodiversity_summary_repository.py`'s own pair, flaky by
nature rather than deterministic, did not reproduce this run. **Zero
failures attributable to this milestone's changes across all three Core
attempts** -- this is the accepted figure.

### Frontend

`tsc --noEmit` and `vite build` clean on every changed file. Full existing
Playwright e2e suite (34 files) plus 2 new spec files (`observation-panel
-subsystem-message-honesty.spec.ts`, `doctor-and-camera-node-hardware
-health.spec.ts`, 9 new tests total) re-run in full: 184 passed / 2 failed.
Both failures independently confirmed pre-existing and unrelated via `git
stash` bisection against the exact unmodified baseline:
`reviewed-product-loop.spec.ts` is the long-documented, previously-known
`productMode` test-suite-staleness gap (recorded across many prior
milestone checkpoints); `notification-preferences.spec.ts`'s "clicking an
insight alert opens Place Story already scoped to wildlife" is a
newly-noticed pre-existing failure (Calm Attention/Notifications' Place
Story deep-link scoping, Lane D territory) -- confirmed to fail identically
against the unmodified baseline, disclosed here as newly found, not fixed
(out of this milestone's bounded scope).

`ruff check` on every changed file: zero new findings, confirmed by direct
`git stash` bisection (82 pre-existing findings, identical count and
content before and after every backend change).

### RED -> GREEN proof (not merely asserted)

Both Area 2 defect fixes were proven to actually close a real gap, not
merely asserted: the new regression tests/specs were run against the
unmodified baseline via `git stash` bisection first (all failed exactly as
predicted -- `'stopped' == 'camera_unavailable'` for the three backend
surfaces; the stale camera-success text literally present in the frontend
detail box), then against the fix (all passed).

### Real hardware

[PENDING -- see §8.]

---

## 8. Real hardware validation

[PENDING -- to be filled in: native-Windows Doctor page + shutdown
re-confirmation; reference Camera Node live hardware-health check.]

---

## 9. Files changed

**Production code:**
- `src/mockingbird/api/main.py` -- `GET /api/product/doctor`, `GET /api/
  streams/{id}/camera-node-hardware-health`, `_resolve_engine_terminal_
  status`/`_engine_terminal_status_by_stream` (new), three call sites
  updated.
- `src/mockingbird/api/auth.py` -- Administrator-tier registration for
  both new routes.
- `src/mockingbird/api/schemas.py` -- `CameraNodeHardwareHealthResponse`/
  `CameraNodeLiveStorageHealth`/`CameraNodeLiveHardwareQuality` (new).
- `src/mockingbird/repository/product_repository.py` -- `get_stream_
  camera_health`/`get_camera_configuration_edit`/`_yard_map_activity_
  summary`/`yard_map` gained optional bridge parameters, defaulting to
  prior behavior exactly.
- `web/src/pages/DoctorPage.tsx` -- new.
- `web/src/pages/CameraConfigurationPage.tsx` -- Camera Node hardware
  panel.
- `web/src/components/ObservationControlPanel.tsx` -- needs-attention
  message fix.
- `web/src/App.tsx`, `web/src/navigation.ts` -- Doctor route/nav.
- `web/src/api/client.ts`, `web/src/api/types.ts` -- new client methods/
  types.
- `web/src/styles.css` -- `.doctor-check-row` added to the existing shared
  card-style selector.

**Tests:**
- `tests/test_product_operations_api.py` -- new (8 tests).
- `tests/test_camera_health_cross_surface_honesty.py` -- new (4 tests).
- `tests/test_candidate_visit_adapter.py` -- one new fault-injection test.
- `tests/test_local_identity_multi_user.py` -- one new assertion (extends
  the existing Viewer-tier test).
- `web/e2e/observation-panel-subsystem-message-honesty.spec.ts` -- new (2
  tests).
- `web/e2e/doctor-and-camera-node-hardware-health.spec.ts` -- new (3
  tests).

**Documentation:**
- `docs/product-operations-first-observation-completion-v1-contract.md` --
  the pre-implementation contract.
- `docs/product-operations-first-observation-completion-v1-report.md` --
  this report.
- `docs/release-execution-state.md` -- dated reconciliation entry (see the
  companion reconciliation commit).

**Not changed:** any detector/tracker/species-identification code; any
schema/migration; any deletion policy or threshold; any accepted Gate A/
Lane R/packaging-acceptance artifact.

---

## 10. Remaining limitations and release risks

- **Camera Node hardware-health facts are not durably persisted** on the
  Host (live-only, on demand) -- a deliberate, disclosed, precedented
  scope decision (§2), not an oversight. A future need for durable history
  of these two facts remains open, evidence-gated follow-up, unchanged
  from the prior milestone's own disclosure.
- **A newly-noticed, pre-existing, out-of-scope e2e failure**
  (`notification-preferences.spec.ts`, §7) -- disclosed, not fixed.
- **No single consolidated source-readiness page** was built (§3,
  "Considered, not built") -- the four existing surfaces are now honest
  and consistent with each other, which is the concrete defect this
  milestone's own contract scoped in; a further UX consolidation remains a
  legitimate, separate future product decision, not a defect.
- Orphan-media detection and the Doctor cleanup-outcome signal remain
  open, low-materiality, deliberately-not-reopened items (§4), unchanged
  from before this milestone.
- [Any full-Core or real-hardware findings to be added here before this
  report is finalized.]

---

## 11. Classification

**A** -- [to be confirmed once full Core and real-hardware validation are
complete]: real, reproduced defects were found and fixed with rigorous
RED -> GREEN proof (not merely asserted); genuinely missing product
-integration surface (Doctor API/UI, Camera Node hardware-health
visibility) was built, bounded and precedented, closing a gap two
independent audits converged on unprompted; substantial areas already
complete were verified, not reimplemented, with evidence rather than
re-trusted prior claims; one previously-uncovered defensive code path
gained real test coverage. No detector/tracker/identification policy
reopened; no schema change; no deletion policy invented; no push.
