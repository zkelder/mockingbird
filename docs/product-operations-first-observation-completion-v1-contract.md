# Product Operations & First-Observation Completion v1 -- Implementation Contract

**Authorization:** direct milestone authorization from the external (ChatGPT)
global-roadmap reconciliation, superseding the previous broad "Hardware &
Recovery Acceptance" authorization and the unstarted "Storage Pressure &
Survival Completion" authorization. Not itself a roadmap-reconciliation
milestone -- implementation and product-integration work.

**Method:** four parallel read-only investigation agents (Doctor/diagnostics
API+UI; first-run wizard/source readiness; first-observation product loop;
storage-survival contract) plus direct reading of the governing docs and the
exact code patterns this milestone will reuse. Findings below are grounded in
file:line citations, cross-confirmed where two independent agents converged
on the same fact.

---

## 1. Verified baseline

- Repository: `/home/<user>/projects/mockingbird-active`, branch `main`.
- HEAD at start: `7b7e282` (matches the authorization's expected commit --
  "Reconcile release-execution-state.md: record Release Reliability &
  First-Run Recovery v1").
- Schema: `v59` (`CURRENT_DATABASE_SCHEMA_VERSION`,
  `src/mockingbird/storage/database.py:46`).
- Worktree: clean except the seven preserved untracked detector files
  (confirmed present, matches the exact expected list).
- No active competing writer: no `mockingbird`/`uvicorn`/`pytest` process
  running; zero files modified anywhere in the repository in the last 4
  hours; one other interactive peer session shares this working directory
  but shows zero filesystem activity, consistent with idle.
- Current authorization going in: `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`, explicitly superseded by this milestone's own
  governing directive.

---

## 2. Area 1 -- In-app diagnostics and recovery ("Doctor")

### What exists

- `src/mockingbird/diagnostics/doctor.py` (2589 lines): 16 checks
  (`DoctorCheckCode`), each returning `DoctorCheckResult{code, component,
  status: PASS|WARN|FAIL|SKIPPED, summary, detail, recoverability:
  blocking|degraded|informational|None, user_action, diagnostic_context,
  duration_ms}`, orchestrated into one `DoctorReport{overall_status:
  HEALTHY|DEGRADED|UNHEALTHY, ...}` by `run_doctor()`. Deterministic
  severity derivation; only Database/Storage can ever be `blocking`; every
  check fails independently and is individually bounded/timed-out. Full
  contract: `docs/mockingbird-doctor-operational-health-contract.md`.
- The engine is a real, mature, well-tested, privacy-safe read-only
  snapshot -- confirmed by direct reading, not merely cited.
- **Zero HTTP exposure today.** Confirmed by grep: the only production
  caller is `python -m mockingbird doctor`
  (`src/mockingbird/__main__.py:60-62`). No route in `src/mockingbird/api/`
  imports `doctor`/`run_doctor`/`DoctorReport`.
- **Zero frontend exposure today.** `grep -rln -i "doctor" web/src/` returns
  nothing -- not even a stub.
- Graceful shutdown (`POST /api/product/shutdown`, Administrator-tier,
  `main.py:11127-11174`) and its frontend control (`LocalDataPage.tsx`,
  "Shut Down MockingBird") are already fully built and wired -- nothing to
  build there; Doctor's own recovery-action UI should link to/reuse this,
  not duplicate it.
- The established auth pattern for a new operational route: a flat
  `ROUTE_POLICY` table in `src/mockingbird/api/auth.py` (no
  per-route `Depends()`), with `("POST", "/api/product/shutdown")`
  registered at `auth.py:647` inside the Administrator bucket alongside
  storage/retention/backup/recovery controls. `PolicyTier`:
  `public|authenticated|reviewer|administrator|device`; anything
  unregistered under `/api/*` defaults to `authenticated` (Viewer floor).

### What's genuinely missing

1. An authenticated `GET /api/product/doctor` route serializing
   `DoctorReport` -- does not exist in any form.
2. A frontend page rendering it with calm, per-check PASS/WARN/FAIL/
   SKIPPED presentation, actionable explanations, and safe recovery
   actions -- does not exist in any form.
3. Camera Node storage/hardware-quality visibility never reaches a human.
   Cross-confirmed independently by two separate investigation agents:
   `mockingbird_node/hardware_health.py` (shipped by the immediately-prior
   milestone) adds real `storage`/`hardware` fields to `/node/v1/health`
   and degrades the Node's own self-test, but **nothing on the Host ever
   polls this live** -- Doctor's own `_gather_camera_node`
   (`doctor.py:1061-1180`) is explicitly, by design, DB-only (never
   constructs a live client -- see the contract doc's "Known v1 scope
   limits," `mockingbird-doctor-operational-health-contract.md:313-316`),
   and grep confirms zero other Host-side consumer reads the `storage`/
   `hardware` keys. This is explicitly disclosed as open follow-up in
   `docs/release-reliability-first-run-recovery-v1-report.md` §4.4/§7 and
   `docs/roadmap.md`'s 2026-09-08 dated update to Gate E.

### Planned changes

- **New `GET /api/product/doctor`** (Administrator-tier, same bucket/
  rationale as `/api/product/shutdown`: an operational/diagnostic surface
  exposing local filesystem paths, schema/migration state, and Camera Node
  identity facts -- more than a Viewer needs day-to-day, and consistent
  with keeping the read surface at the same tier as the recovery actions it
  will link to). Thin wrapper: call `run_doctor()`, serialize the existing
  dataclasses to a new Pydantic response schema. No change to `doctor.py`
  itself beyond what's needed to serialize cleanly (the module is frozen
  contract; reuse, never duplicate, its logic/thresholds/vocabulary --
  `SKIPPED` stays `SKIPPED` in the wire shape; the milestone brief's
  "UNAVAILABLE" language is a UI-copy concern, not a backend rename).
- **New `web/src/pages/DoctorPage.tsx`**: overall-status banner, one row per
  check (component, status badge, summary always shown, detail/
  diagnostic_context behind a disclosure, `user_action` when present),
  calm colors (`StatusPill`, matching existing tone conventions), a
  Refresh action, and honest loading/error/unreachable states. Recovery
  actions are links to existing controls, never new mutations: Storage/
  Backup checks link to the Local Data page (already hosts cleanup/backup/
  restore); Camera Node checks link to Streams/Camera Configuration;
  Application check surfaces the existing "Shut Down MockingBird" action
  where relevant (e.g. a stuck/starting state). Reachable from
  `productNavItems` as `{ page: "doctor", label: "Doctor", minRole:
  "administrator" }`, mirroring the existing `"users"` admin-gated nav
  entry exactly (`App.tsx:117,676-678`); route `/doctor` added to
  `navigation.ts` alongside `users: "/users"`.
- **Camera Node hardware-health visibility**, bounded: a new live,
  on-demand, non-persisting endpoint mirroring the existing "Check the
  picture" precedent (`CameraSetupPage.tsx`'s bounded preview pattern) --
  **not** a schema migration, **not** a change to Doctor's own read-only
  invariant. `CameraNodeClient.health()` (`source_providers/camera_node.py
  :609-614`) already returns the raw `/node/v1/health` payload, which
  already includes `storage`/`hardware` (shipped last milestone) -- no
  Node-side change needed at all. New route resolves an already-paired
  Stream's `camera_node_base_address` the same way
  `start_stream_observation`/`node_compatibility.probe_node_compatibility`
  already do (`main.py:11743-11760`), calls `client.health()` in a bounded
  `asyncio.to_thread`, and returns the storage/hardware facts (or an honest
  "not a Camera Node stream" / "unreachable" result, never a crash).
  Administrator-tier, matching `/api/camera-nodes/pair/preview`'s existing
  precedent for a live-Node-touching read. Surfaced on the Camera
  Configuration page (where camera-specific health already lives) and
  linked from Doctor's `camera_node` check via `user_action` text -- Doctor
  itself stays exactly as documented, DB-only.

---

## 3. Area 2 -- First-run and source readiness

### What exists

- A real 5-step wizard (`OnboardingWizard.tsx`) that persists progress
  server-side and resumes correctly; step 4 embeds the real
  `CameraSetupPage`, step 5 embeds the real `ObservationControlPanel` --
  which already correctly separates Camera health from Observation/
  detector health (`ObservationControlPanel.tsx:256-270`), live-field
  -proven (`docs/authenticated-camera-node-golden-path-capture-preview-
  acceptance-v1-report.md:371-377`).
- Real, working per-provider connectivity confirmation ("Check camera
  settings" / "Check the picture") for every source type, deliberately
  scoped to connectivity/URL/pairing only -- detector/GPU readiness is
  correctly deferred to the Observe step, which already shows it honestly.
- Backend building blocks for a unified readiness view already exist and
  are richly shaped (`GET /api/streams/{id}/observation-status`, `GET
  /api/streams/{id}/camera-health`, `.../incidents`) but the latter two are
  defined in `client.ts` and **called by zero frontend components**.

### Concrete reproduced defects (in scope to fix)

1. **Cross-surface health contradiction.** `_camera_health_summary_from_
   models` (`product_repository.py:14537-14636`) is called from four call
   sites; only `dashboard_summary()` (`:19047-19058`) threads
   `engine_terminally_unavailable`/`engine_unavailable_message` (the
   accepted Lane C fix). `get_stream_camera_health()` (`:15258-15266` --
   backs `GET /api/streams/{id}/camera-health` **and** the Camera
   Configuration ("Edit camera setup") page) and `_yard_map_activity_
   summary()` (`:17810-17818` -- backs Yard & Camera Map) do not. Result:
   for a Camera Node stream with a connected camera but a failed detector/
   GPU/model, the Dashboard correctly shows "Camera unavailable" (alert,
   real failure text) while Camera Configuration and Yard Map, for the
   identical stream at the identical moment, show "Monitoring stopped"
   (calm tone) -- one click apart. This is exactly the class of honesty bug
   Lane C's own closure fixed elsewhere but missed at these two call sites.
   **Fix:** thread the same `engine_terminally_unavailable`/`engine_
   unavailable_message` facts into both remaining call sites, reusing the
   exact mechanism already proven at the third.
2. **Wrong-subsystem message in `ObservationControlPanel`.** The needs
   -attention detail box is hardcoded to `status.camera_message`
   regardless of which subsystem actually failed
   (`ObservationControlPanel.tsx:282-286`). For a connected camera with a
   failed engine, this shows the reassuring "Camera Node is paired and
   configured" instead of the real engine failure text -- an internally
   inconsistent panel. **Fix:** show `engine_message` when the camera is
   connected but the engine is not available, `camera_message` otherwise,
   mirroring the precedence already used for the panel's own top-line
   `status.message`.

### Planned changes

- Fix both defects above with focused backend/frontend changes + regression
  tests proving the previously-contradictory surfaces now agree.
- Camera Node hardware-health live-check endpoint (Area 1, shared).
- No wizard/setup-flow restructuring, no new health vocabulary, no
  redesign -- the existing architecture and the existing three status
  concepts (`CameraHealthState`, `ObservationSessionStatus`,
  `StreamPlaybackStatus`) are preserved; this closes the plumbing gap that
  makes them disagree, which is the substance of "coherent workflow" here.

---

## 4. Area 3 -- First-observation product loop

### What exists (independently verified, not merely re-cited)

An independent code-reading audit (not merely trusting Lane C's own closure
claim) traced Today's sparse-state CTAs, Review Queue's suggestion/
abstention presentation and both real correction-mutation paths, evidence
visibility (including the same-frame classifier-evidence panel), Bird Log's
confirmed-only inclusion rule, and the backend abstention contract
(`identification_eligibility.py`'s typed `AbstentionDecision`, verified
end-to-end to `ReviewIdentificationStatus.identification_uncertain` with an
honest message and no fabricated `SpeciesSuggestionModel` row). Five specific
claims from `docs/lane-c-sparse-state-honesty-first-hour-narrative-closure
-v1-report.md` were independently re-verified against current code and held.

**No reproducible defect was found.** Lane C's "materially delivered / no
known dev remains" status holds up under independent scrutiny.

### Planned changes

- No functional rework planned. A live smoke pass (existing Playwright e2e:
  dashboard/review-queue/bird-log/onboarding specs, plus real-hardware
  where available) is part of this milestone's validation, not new
  implementation -- if it surfaces a genuine defect, fix it; otherwise this
  area closes on verification evidence, per the milestone's own "if already
  complete, document the evidence" instruction.
- Two minor, non-blocking observations disclosed by the audit (suggestion
  -row provenance not visually distinguished from a coarse fallback label;
  two independent correction-save code paths) are noted but not treated as
  defects requiring a fix under this milestone's bounded scope.

---

## 5. Area 4 -- Storage survival, bounded completion

### What exists (independently verified)

A real, tested, four-tier disk-pressure ladder (`healthy` / `getting_low`
&lt;5GB or &lt;15% / `action_recommended` &lt;1GB or &lt;5% / `critical` &lt;200MB or
&lt;1%, `storage/database.py:1905-1955`), duplicated consistently on the Camera
Node. Under `critical`: media writes are uncaught at the write layer but
every actual write happens inside a transactional `session.begin()` block
that rolls back atomically on failure (no partial/corrupt commit); the one
retry policy in the candidate-persistence path (`_MAX_PERSISTENCE_ATTEMPTS =
3`) explicitly never retries a non-contention (e.g. disk-full-shaped)
failure -- proven by `test_non_contention_failure_is_not_retried`; the
opt-in transport spool has a real, tested disk-floor guard that evicts or
raises rather than silently exceeding a bound; the previously-disclosed
unbounded `storage_cleanup_history` gap is already fixed
(`_prune_storage_cleanup_history`); the host log file is genuinely bounded
(`RotatingFileHandler`, 5MB x 3). Human visibility of Host-side pressure
already reaches Doctor and the Dashboard. This is a real, independent
re-confirmation of Lane M's CLOSED status, not a re-assertion of the prior
claim.

### Genuinely missing piece

The same Camera Node storage/hardware-quality-visibility gap identified
independently in Area 1 -- found by *both* the Doctor-focused and the
storage-focused investigation agents as the one concrete, named,
still-open item connecting "Doctor" and "storage survival." Addressed once,
under Area 1, not duplicated.

### Planned changes

- Camera Node hardware-health live-check endpoint (Area 1; satisfies this
  area's "Camera Node health" visibility half too).
- **One new, real fault-injection test** proving the disk-full write path
  fails safely end-to-end (a literal `OSError`/`ENOSPC`-shaped exception
  injected at the real Host media-write function, asserting: the
  transaction rolls back with zero partial data, the failure is recorded
  as a typed `"failed"` outcome rather than crashing the observation loop,
  and it is not retried) -- closes the one real test-depth gap the
  independent audit found (existing coverage proves the *mechanism*
  generically; nothing today proves it specifically for a real disk-full
  shape). This is evidence-only: no production behavior changes, since the
  code path already fails closed by inspection and by the generic test.
- **Document, do not reimplement**, everything else: Lane M's retention/
  cleanup/backup/spool machinery is complete and independently
  re-verified; this milestone's closure report will cite that evidence
  directly rather than re-running Lane M's own acceptance.

### Explicitly not reopened

- **Orphan-media/no-DB-owner detection.** Confirmed still genuinely absent
  (only one full media-root walk exists anywhere,
  `storage/backup.py:669`, purely for backup archiving, zero DB
  cross-reference). Repeatedly, explicitly disclosed across three prior
  milestone reports and `release-execution-state.md` §6 Lane M as
  low-materiality and *deliberately not reopened* -- "a reasonable
  candidate for a future bounded 'sampled orphan sweep,' not a reason this
  lane remains open." Left exactly as is, per this milestone's own
  "reopen only for reproduced defects... or explicit authorization" scope
  boundary.
- **No Doctor signal for automatic-cleanup outcome.** Small, real, already
  disclosed (`storage-retention-disk-pressure-recovery-closure-v1-report.md
  :168`). Storage/Backup tiers already carry the primary actionable
  signal; this is a minor enrichment, not a survival gap. Left as a
  disclosed remaining limitation unless time remains after the above.
- **No deletion-policy or threshold change of any kind.** Every threshold
  above is reused verbatim, never re-derived or invented.

---

## 6. Area 5 -- Product polish and integration

Scoped strictly to what Areas 1-4 touch: honest loading/empty/error states
on the new Doctor page; consistent status presentation (reusing
`StatusPill`/existing tone helpers, never a new visual language); the two
Area 2 coherence fixes are themselves polish-as-correctness. No visual
redesign, no unrelated-feature work.

---

## 7. Explicit non-goals (reconfirmed from the governing brief)

Gate G / participant recruitment / distribution gates; remote LTE/solar/
native mobile/new ML models/ecological enrichment; a new observability
platform, frontend rewrite, or broad architecture refactor; reopening
accepted detection/tracking/identification policy; inventing storage
thresholds or deletion policy; pushing to remote.

---

## 8. Validation plan

- Tier 1: every new/changed test file, run fresh.
- Tier 2: affected-subsystem suites -- `test_doctor.py`, camera-health/
  observation-status/yard-map repository tests, `test_camera_node_
  hardware_health.py`-adjacent coverage, storage/candidate-persistence
  tests.
- `ruff check` on every changed file; frontend `tsc --noEmit && vite build`.
- New/adjacent Playwright e2e: a Doctor page spec; re-run of dashboard/
  review-queue/bird-log/onboarding/camera-controls specs as the live
  first-observation-loop demonstration.
- Tier 3 (full Core): warranted here -- this milestone touches shared
  repository health-summary code on three call sites and adds new API
  surface, which is exactly the cross-cutting-risk bar this project's own
  validation-tiers doctrine sets for a full run.
- Real hardware where available (labeled as such, not conflated with
  simulated/structural evidence): native-Windows Doctor page + shutdown
  re-confirmation; the real reference Camera Node for the new live
  hardware-health endpoint. No fault injection against real user data or
  real disks; no repeat of Lane R/Gate A field acceptance.

---

## 9. Files expected to change (best estimate, not exhaustive)

Backend: `diagnostics/doctor.py` (serialization surface only, if needed),
`api/main.py`, `api/auth.py`, `api/schemas.py`,
`repository/product_repository.py` (the two call sites), `source_providers/
camera_node.py` (if a thin wrapper helper is warranted).
Frontend: new `pages/DoctorPage.tsx`, `App.tsx`, `navigation.ts`,
`api/client.ts`, `api/types.ts`, `components/ObservationControlPanel.tsx`,
`pages/CameraConfigurationPage.tsx`.
Tests: new `test_product_doctor_api.py`-shaped file, targeted additions to
`test_doctor.py`, camera-health/yard-map/dashboard repository tests,
candidate-persistence fault-injection test, new Playwright spec.
Docs: this contract; `release-execution-state.md` reconciliation entries;
the closure report.

No detector/tracker/identification/schema-policy code changes anticipated.
A schema migration is **not** currently planned (the Camera Node
hardware-health design deliberately avoids one) -- if implementation
reveals one is genuinely required, this contract will be updated before
proceeding, per the milestone's own "lock the contract before implementing"
discipline.
