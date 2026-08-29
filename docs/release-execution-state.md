# MockingBird Release Execution State

This file controls execution sequencing, not product doctrine.
[product-doctrine.md](product-doctrine.md) defines what MockingBird is.
[roadmap.md](roadmap.md) preserves the full roadmap. This file records
current accepted state, remaining lanes, release classification, and what
work is presently authorized.

Claude's "next natural milestone" suggestions are advisory only. They do
not authorize future work.

## CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT

MockingBird is still in substantial product development. Representative
Field Acceptance, External Pre-Release Acceptance, and Final Release
Hardening (Lanes R/S, below) are downstream gates and must **not** become
the default next
milestone while substantial product-roadmap capability remains
intentionally unfinished -- see §6, "Global remaining execution queue,"
for the complete remaining-capability picture this phase label is
protecting.

## 1. Current accepted state

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`
- **Accepted HEAD:** `fe54ac9` -- the implementation commit for
  Storage / Retention / Disk-Pressure & Recovery Closure v1 (its own
  separate documentation-only report commit sits directly on top and is
  not cited here as a second, separate code-bearing HEAD, matching this
  field's established convention). `1656f1a` (Non-Interactive Field
  Acceptance Authentication & Session Access v1's own implementation
  commit), `18a0025` (Whole-Product UI / Accessibility / Performance
  Closure v1's own implementation commit), One-Release Roadmap & Scheduler
  Reconciliation v1's own commit (documentation-only, `4312b18`), and
  Camera Node Upgrade & Compatibility Recovery v1's own three
  implementation commits sit underneath it in history; the intervening
  reconciliation commits for those closures (`e01e691`, `c03d0b1`,
  `80e1bb3`) are likewise not cited as separate code-bearing HEADs for the
  identical reason.
- **Schema:** `v58` -- unchanged by this milestone. Every fix Storage /
  Retention / Disk-Pressure & Recovery Closure v1 made lives entirely in
  `scripts/deploy_windows_dev.py` (dev-deployment tooling) and its own test
  file -- confirmed by direct grep that nothing under `src/mockingbird/`
  imports it; no product, persistence, or schema code was touched.
- **Latest accepted milestone:** Storage / Retention / Disk-Pressure &
  Recovery Closure v1 -- see
  [storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
  for the complete record. Classification **B**. A bounded, release-critical
  storage/reliability milestone (Lane M) that also determined the cause and
  product significance of the Windows Host free-space decline this file's
  own 2026-08-28 Lane R entry (below) first surfaced (`43.07GB -> 18.8GB`,
  2026-08-20 -> 2026-08-28) but left open. Real, directly-measured disk
  accounting (native `powershell.exe` interop against the real Windows dev
  host, not estimated) found the single largest consumer anywhere in the
  investigation: `%LOCALAPPDATA%\MockingBirdDev\runtime\` (the dev-only
  `deploy_windows_dev.py` tool's runtime/model/BioCLIP-model cache) held
  38.5GB across 21 never-pruned entries, including 6.25GB of definite
  orphaned `.staging-*`/`.stale-*` leftovers from interrupted cache
  populations -- a real, previously-disclosed-and-deliberately-deferred gap
  (`docs/windows-dev-deployment-design.md`'s own "Left for follow-up"
  section had judged this "unlikely to matter in practice," a judgment
  real measurement falsifies). Combined with the field-acceptance
  recorder's own real output directory (11.5GB, genuine evidentiary
  artifacts from the project's own real 2026-08-19/08-20/08-21 daylight/
  dusk sessions, not waste), directly-dated entries created inside the
  exact 2026-08-20 -> 2026-08-28 decline window account for roughly 72%
  of the observed 24.27GB decline -- **disposition B: MockingBird
  development/test-artifact accumulation, root-caused, product
  unaffected**. Neither growth path exists in, or is reachable by, a real
  end-user installation: `%LOCALAPPDATA%\MockingBird` (the real production
  runtime home) measures 1.1MB on this same machine, and the real product's
  own upgrade mechanism (Release Engineering Foundation v1) is a
  structurally different, single-version, database-level-pre-migration-
  backup-only design with no multi-version content-addressed cache at all.
  Fixed: a new `gc_cache_command`/`--gc-cache` flag in
  `scripts/deploy_windows_dev.py` implementing exactly the bounded shape
  the design doc's own deferred-follow-up section had already named
  (referenced-hash walk over every currently-on-disk retained release, plus
  an unconditional orphaned-`.staging-*`/`.stale-*` sweep) -- 11 new tests,
  `tests/test_deploy_windows_dev.py`: 123 passed; `ruff check` clean on
  both changed files. Applied live against the real Windows dev host to
  reclaim real disk space (see the milestone report for exact before/after
  figures). Separately, deep archaeology of the already-accepted storage-
  retention/backup/Doctor product contract (`docs/appliance-storage-
  privacy-recovery-v1-contract.md`, accepted 2026-08-23) -- re-verified,
  not rebuilt, via 349 real, independently re-run passing tests across the
  whole storage/retention/backup/doctor/deploy-tooling family -- found and
  precisely disclosed (not fixed, each safe-direction/non-release-blocking,
  none warranting a rushed change to the highest-stakes retention-
  eligibility code under this milestone's own time bound) one real
  documentation-vs-code mismatch (imported/folder-imported media is
  over-retained forever, contrary to the accepted contract's own explicit
  "same rules as any other Visit-linked evidence" claim -- empirically
  reproduced, zero pre-existing test coverage for this exact path) plus
  three smaller gaps (a `"staging"`-state cleanup batch can only ever be
  restored, never purged; `storage_cleanup_history`'s own
  `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` constant does not actually bound the
  underlying table, only a read-page/chunk size; no orphan-media,
  file-with-no-DB-owner, detection exists anywhere in the product, a
  structural gap distinct from, and confirmed still bounded/low-materiality
  for, the already-accepted Concurrent Candidate Visit Persistence
  Reliability v1 milestone's own disclosed orphan possibility, not
  reopened). No schema change; Tier 3 (full Core) not run, matching this
  codebase's own established precedent for changes confined entirely to
  `scripts/` deployment tooling with zero importers in `src/mockingbird/`
  (Camera Node Upgrade & Compatibility Recovery v1 made the identical call
  for the identical reason). Does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Non-Interactive Field Acceptance
  Authentication & Session Access v1 -- see
  [non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
  for the complete record. Classification **A**. A bounded, release-critical
  security/correctness dependency milestone -- not a product capability --
  closing the recurring field-acceptance authentication blocker three
  consecutive prior attempts hit (2026-08-25, 2026-08-26, 2026-08-28; see
  Lane R, §6, below) without an authentication bypass, without the
  operator's personal credentials, and without weakening production
  security. Adds one new, narrow, parallel, bearer-token-authenticated
  identity -- "Field Acceptance Operator" -- mirroring this codebase's own
  existing Camera Node device-identity-separation precedent rather than
  extending the linear Viewer/Reviewer/Administrator role ladder (the
  required permission shape -- broad Viewer-level reads plus exactly two
  otherwise-Administrator-tier mutations, Observation start/stop, and
  nothing else Administrator-tier -- is not a contiguous prefix of that
  ladder, so no single role-rank placement could express it correctly).
  Checked by the exact same central `install_authorization` gate every
  other request already passes through -- no parallel/insecure auth stack,
  no localhost/header bypass, no anonymous fallback, proven by a dedicated
  negative-test regression suite. Schema `v57 -> v58`: one new additive
  table, `field_acceptance_credentials` (hash-only token storage,
  mandatory bounded expiry -- no permanent-credential path exists in v1 at
  all -- explicit deterministic revocation, auditable creation/revocation/
  use). Provisioning is a bounded new admin CLI
  (`scripts/manage_field_acceptance_credential.py`, Administrator-only,
  never accepts a password as a CLI argument) mirroring the existing
  `repair_review_label_provenance.py` real-HTTP-instance precedent; the
  acceptance tooling itself gained a small stdlib-only client
  (`scripts/field_acceptance_client.py`) reading
  `MOCKINGBIRD_ACCEPTANCE_TOKEN` and failing clearly (never anonymously)
  on every required negative case. Real acceptance proof: provisioned and
  exercised this exact mechanism live against a real running instance of
  this milestone's own implementation commit (native Windows, real SQLite,
  real FastAPI/uvicorn process, `--skip-gpu-runtime --skip-bioclip-runtime`
  since this proof needed the auth/API layer, not detection quality) --
  the identical three endpoints that blocked the three prior field-
  acceptance attempts (`GET /api/streams`, `GET /api/visits`, `POST
  .../observation/start`) all still correctly `401` with no credential,
  then all succeed with the new credential, including a real Observation
  start/stop cycle against the auto-seeded demo Stream, with the
  credential correctly denied (`403`) on unrelated Administrator actions
  and its use distinguishable from a human Administrator's in the audit
  trail; revocation was proven immediate (the identical token fails on its
  very next use). Deployed to an isolated, disposable dev-root -- **not**
  the operator's real `MockingBirdDev` deployment, confirmed untouched
  throughout -- with a disposable bootstrapped Administrator, no live
  operator credentials used anywhere in this milestone's own work,
  matching this file's own standing decision (see the 2026-08-25 Lane R
  entry, below) against asking the operator for real credentials or live
  participation. Environment left in a secure, known, empty state after
  proof (credential revoked, disposable instance and process fully
  removed). Tier 1/2: 20 new tests
  (`tests/test_field_acceptance_authentication.py`) plus 219 across the
  eight pre-existing files this milestone's schema-literal bump touched,
  all passing. Tier 3 (full Core): 5187 passed / 2 failed -- the 2
  failures both the identical, independently-reconfirmed pre-existing
  `test_place_biodiversity_summary_repository.py` pair (a bird-species
  historical-status classification defect with zero code-path relationship
  to this milestone's own changes), confirmed unrelated by a direct
  `git checkout` bisection against this milestone's own true starting HEAD
  (`c03d0b1`), not merely inferred from precedent -- zero regressions
  attributable to this milestone. `ruff check`: zero new findings,
  confirmed by a direct clean-baseline bisection. e2e not run (zero
  `web/src/` changes; the existing suite's cookie-session `storageState`
  bootstrap is untouched and does not intersect this milestone's
  bearer-token mechanism). Concrete residual risk, both disclosed in full
  in the milestone's own report: no login rate-limiting exists anywhere in
  this product (a pre-existing, disclosed gap from Mobile & Remote
  Experience v1, untouched, out of this milestone's scope) -- a
  field-acceptance bearer token is a static secret for its bounded
  lifetime, mitigated by mandatory expiry/hash-only storage/explicit
  revocation but not by any brute-force protection on the token-lookup
  path itself; and the real acceptance proof ran against a disposable
  instance, not the operator's specific long-running real `MockingBirdDev`
  deployment (deliberately, per standing policy), so that specific
  instance still needs its own one-time `create` provisioning step before
  its first non-interactive use -- not a gap in the mechanism, the
  intended minimal human step. This closure does **not** authorize Lane R, the
  next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Whole-Product UI / Accessibility /
  Performance Closure v1 -- see
  [whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
  for the complete record. Classification **A**. Closes Lane Q as an
  integrated pass. A bounded, live browser/keyboard investigation across a
  seeded, product-shaped 371-Visit QA instance (own isolated database, own
  bootstrapped disposable Administrator -- no live credentials used) found
  and fixed one P0 and three P1 defects, each with a RED/GREEN-verified
  regression test and a live before/after confirmation, not merely code
  inspection: (1) manually- and folder-imported Visits (the default,
  promoted camera-less acquisition path) were silently excluded from
  Review Queue's default "Animals" tab regardless of subject_label --
  the real, previously-unidentified root cause of one class of confusion
  this project had repeatedly, incorrectly attributed to
  `reviewed-product-loop.spec.ts` being an unrelated flake across at
  least three prior milestones; (2)-(3) two real keyboard focus-management
  defects in Fast Review (activation, and last-item-in-view completion)
  left focus stranded on `document.body`, found via live keyboard-driven
  browser testing, both fixed with the same "focus the new region's own
  heading" pattern the mobile nav drawer already used correctly; (4) the
  scheduler's disclosed bounded acoustic health/status gap (Lane A) closed
  with the smallest capability-aware addition the brief allowed --
  composed entirely from already-existing facts, never a factor in
  `ready`. Investigated and confirmed NOT regressions: two very-tall-
  looking pages (Stream Detail, Analytics) that turned out to still be
  correctly bounded exactly as the 2026-08-18 "v0.1 Product Flow Gap Pass
  v1" fix intended. Root-caused (not fixed, disclosed) `reviewed-product-
  loop.spec.ts`'s real mechanism for the first time: `ReviewQueuePage.
  tsx`'s `const productMode = true;`, a pre-existing (`1772c36`,
  2026-07-28, predating this milestone by a month), un-toggleable
  constant, makes the legacy markup that spec targets permanently
  unreachable -- test-suite staleness, not a live product defect; fixing
  the spec itself needs a real rewrite against the current flow, left as a
  precisely-scoped, not-yet-started follow-up. Zero horizontal overflow
  found across 40 real combinations (4 required widths x 10 pages);
  measured, not assumed, performance at an 89-item backlog sits at or
  below BioCLIP Status / Review Queue Performance v1's own accepted
  87-item precedent, no regression found or introduced. Full e2e (136
  specs, 8 new): 135 passed / 1 failed -- the one failure the precisely-
  diagnosed pre-existing gap above, independently reproduced identically
  on the unmodified 128-spec baseline (127 passed / 1 failed, byte-
  identical single assertion). Full Core run clean (see §14). `ruff
  check`: zero new findings, confirmed by a direct clean-baseline
  bisection given `product_repository.py`'s 42,600+ line scale. Schema
  unchanged (v57 -> v57). Remaining, disclosed, not blocking: Zone-polygon
  *drawing* (not selection) has no keyboard equivalent (optional/advanced
  feature, pre-existing); a materially larger dead-CSS footprint around
  `.bird-log-entry` than previously documented; a narrow raw-exception-
  text edge case on non-`ApiError` failures. This closure does **not**
  authorize Lane R, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone.
- **Prior accepted milestone:** One-Release Roadmap & Scheduler
  Reconciliation v1 -- documentation/state-governance only, touching zero
  product/test/schema code. See
  [one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
  for the complete record. Classification **A**. Reconciled this file and
  `roadmap.md` to one coherent release doctrine: MockingBird has one
  public release -- no public "v0.1" product stage, no beta product
  release, no separate before-v1.0 roadmap phase. External Pre-Release
  Acceptance (roadmap.md's Gate G, renamed here from its prior "External
  Beta Acceptance") and internal release-candidate builds remain allowed
  as pre-launch validation/engineering mechanics, never a separate product
  stage; this file's own Lane S ("Actual Final Release Hardening") is
  rewritten onto that same readiness-triggered, not version-number
  -triggered, sequencing (External Pre-Release Acceptance -> Final Release
  Hardening -> the one public launch). Renamed this file's own §7
  ("First-public-v0.1 doctrine" -> "One-release doctrine") and §8
  ("Post-v0.1 / before-v1.0 queue" -> "After-release queue"); replaced
  "v0.1 CRITICAL"/"v0.1 blocker"/"v0.1 scope"/"v0.1 requirement" language
  throughout both files with "release-critical"/"release
  blocker"/"release scope"/"release requirement," matching wording
  `roadmap.md` had already adopted for its own "Release gates"/
  "After-release lanes"/"Release non-blockers" headings at an earlier,
  partial reconciliation (`326207b`); fixed several cross-references that
  earlier rename had left dangling ("v0.1 release gates" -> "Release
  gates," "v0.1 non-blockers" -> "Release non-blockers," "Post-v0.1
  lanes" -> "After-release lanes," and a "(see "v0.1 feature freeze,"
  below)" pointer redirected to the section that actually carries that
  content today). Added a short "Four release-shape categories" index to
  §6, above, mapping the existing lettered lanes onto release-critical/
  pre-release-decision/after-release/later-evidence-driven categories
  without removing, renaming, or promoting any of them. `product-
  doctrine.md` was read in full and left unedited -- it already frames the
  release as the real product launch and creates no beta/v0.1 product
  stage. Every dated historical milestone bullet, proper-noun milestone
  title (for example "v0.1 Product Flow Gap Pass v1," "v0.1 Observational
  Quality Closure v1," "v0.1 Acquisition/Ingest Interoperability Closure
  v1"), and historical decision label (the 2026-08-22 "v0.1 feature
  freeze now active" decision, and the reasoning tied to it) was left
  verbatim, since it records what was actually named and decided at the
  time, not current doctrine. No lane, gate, or roadmap capability was
  added, removed, or promoted; no code, test, or schema changed.
- **Prior accepted milestone:** Camera Node Upgrade & Compatibility
  Recovery v1 -- see
  [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).
  Classification **A**. Closes Lane L's one remaining named gap: a Camera
  Node **upgrade** workflow, distinct from the already-accepted install/
  reboot/reprovision/replacement hardening -- see Lane L, §6, below.
  Investigation found the existing installer already had real update/
  rollback *mechanics* (build_id-keyed idempotency, one retained prior
  version); what was missing was a real upgrade *contract*: artifact
  -checksum verification before any mutation (the artifact builder already
  produced `SHA256SUMS`/per-file hashes but nothing ever checked them),
  staged build-and-verify before the live install is touched at all
  (`venv.staging`, `import mockingbird_node.app` as the activation gate),
  automatic recovery when a newly-activated build fails post-update
  verification, and a bounded Node-local wire-protocol compatibility
  classification (`current`/`compatible_older`/`incompatible`/`unknown`,
  styled after the existing `provider_compatibility` convention) -- the
  Host's own real wire-protocol gate (exact-match only, no graduated tier)
  was investigated and deliberately left unchanged, a pre-existing
  accepted decision. Found and fixed, before any real-hardware attempt, a
  real reproduced defect in the already-accepted artifact builder:
  `NODE_FILES` had silently drifted behind `app.py`'s own imports (Remote /
  Intermittent-WAN Transport Foundation v1 added six transport modules
  without updating the packaged file list) -- every fresh install and
  upgrade produced by the accepted builder was completely broken
  (`ModuleNotFoundError` at startup), confirmed by direct reproduction;
  fixed, plus a new fast static import-closure test closing the whole
  class of drift, not just this instance. A 5-angle adversarial
  self-review before real-hardware acceptance found and fixed 8 further
  correctness issues in this milestone's own new code (most notably: the
  original activation-recovery design, keyed only on whether a staging
  directory still existed, missed a real crash window a manifest-first,
  build-id-reconciliation redesign closes completely; and a plain,
  successful, directly-requested `--rollback` was originally misreported
  as a failed upgrade). Real acceptance against the project's actual
  reference Pi -- which had never been upgraded since 2026-08-18, predating
  three later accepted Camera Node milestones entirely -- found and fixed
  two further real defects live: a universal, upgrade-blocking crash
  (`transport_spool_dir` defaulting through a `Path.home()`-derived path
  that is always broken under the already-accepted `ProtectHome=true`
  hardening, regardless of whether transport was ever configured -- would
  have broken *every* Camera Node upgrading past the transport milestone
  through the accepted installer, not just this device), and two
  automatic-recovery gaps (`systemctl restart` failing outright did not
  trigger automatic rollback; a preceding crash loop's exhausted
  `StartLimitBurst` blocked an unrelated later restart) -- both found live,
  both fixed the same session with dedicated regression tests, not merely
  disclosed. The device was then successfully, fully upgraded end to end
  (node identity, pairing credential hash, and camera availability all
  confirmed byte-identical/unchanged before and after; new boot-identity/
  self-test/watchdog capabilities live on real hardware for the first
  time), with a real idempotent re-run confirmed afterward. One honest
  reservation against an unqualified top classification: `rollback()`
  restores code but not an already-changed systemd unit template, a real
  gap this session's own recovery encountered and worked around manually
  (a temporary drop-in) rather than closed structurally -- disclosed, not
  hidden. Tier 1 (114 tests across `test_install_camera_node.py`/
  `test_camera_node_packaging.py`/`test_camera_node_config_transport.py`/
  `test_camera_node_real_process.py`, all passing), Tier 2 (the full
  `camera_node`/`doctor` test family, 493 passed / 0 failed fast-tier plus
  17 passed / 0 failed slow-tier), `ruff check` clean. Tier 3 not run --
  every changed line sits in `scripts/` deployment tooling or the
  deliberately main-app-isolated `mockingbird_node` package (confirmed by
  direct `grep`: zero importers of either in `src/mockingbird/`); real
  hardware acceptance is stronger evidence for this milestone's actual
  scope than an unrelated 5000+ test Core run. No schema change; no
  product/perception/database/API code touched.
- **Prior accepted milestone:** Representative Multi-Camera Field
  Acceptance & Release-Budget Evidence v1 -- see
  [representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
  Classification **B** -- no live field session ran (session start, 20:26
  EDT 2026-08-26, was after sunset -- the same "darkness produces an
  unusable bird denominator" scenario this project has already hit twice
  before, 2026-08-19/2026-08-20; this milestone's own governing brief
  names exactly this as the case to not manufacture a field result under).
  Executed the brief's own "no representative conditions" path instead:
  re-verified every precondition a live daylight session needs (Camera
  Node network reachability, GPU/detector idle and available, disk
  headroom, the exact acceptance-recorder env-var settings/structured-log
  path, the exact command/API sequence, minimum run duration), and --
  while proving "the current deployed build contains accepted HEAD" --
  found and fixed one real, previously-hidden defect: a fresh, full-
  fidelity Windows dev build of the then-current accepted HEAD
  (`db8588c`) failed outright with a genuine `LocalProductBuildError`
  (site-packages ended up with two different `click` versions, 8.4.2 and
  8.5.0, installed by two independent dependency-install tiers -- the
  identical mechanism, and identical one-line-pin fix shape, as this same
  file's own already-documented `idna` pin). Validated RED->GREEN against
  an existing test that already covered this exact shape but had never
  been run against today's live PyPI state
  (`test_real_windows_bioclip_dependency_closure_installs_offline_with_no_duplicates`);
  full `test_local_product_packaging.py` (66 fast + 4 slow) passing;
  `ruff check` clean; Tier 3 not run (change isolated to Windows packaging
  tooling, zero import relationship to the Core suite). Re-deployed after
  the fix and independently re-verified via direct HTTP (`GET
  /api/product/instance`/`/api/product/health`: `git_commit` exact match,
  schema `57`, `ready: true`) that the deployed artifact carries the fix
  (`click-8.4.2.dist-info` the only `click` entry anywhere in it), then
  stopped it cleanly, leaving `db8588c` a retained, ledger-verified
  release ready for instant relaunch. Also learned, via the
  unauthenticated health endpoint only (no credentials used, matching the
  standing decision below): only one real Stream (the reference Camera
  Node) is currently configured in this dev instance -- a second real,
  already-supported Windows-USB-webcam Source (hardware-validated for the
  prior Acoustic milestone) is not yet wired up, and should be added as a
  genuine second Stream before the next live session, so this project's
  still-open "does the concurrent-persistence fix hold under genuine
  multi-camera load" question can actually be tested with two real
  cameras. No product/perception/admission/Visit/evidence/classification
  code touched; no schema change; Gate A evidence body unchanged (zero new
  field-cohort minutes gathered) -- no release budgets proposed. See Lane
  R, §6, below, for the Gate A/field-acceptance-specific record.
- **Prior accepted milestone:** Concurrent Candidate Visit Persistence
  Reliability v1 -- see
  [concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
  Classification **A** -- a bounded correctness milestone, not a further
  Multi-Camera product pass, closing the real, disclosed occasional
  lost-candidate-Visit concurrent-write reliability gap Multi-Camera Place
  Experience v2 found, root-caused, and deliberately left unfixed (its own
  bounded transient-retry attempt did not reliably close the gap and was
  reverted). Root cause confirmed directly (a real captured
  `sqlalchemy.exc.OperationalError: database is locked` stack trace under
  real concurrent multi-Stream SQLite writes) and reproduced
  deterministically on demand (a real second SQLite connection holding a
  real write lock, independent of host load) -- not merely inferred.
  `create_candidate_visit_from_proposal` was already idempotent
  (`proposal_id`-keyed) and fully transactional (a failed attempt rolls
  back completely, already proven by a pre-existing test), which made a
  bounded, classified retry provably safe. Fixed by (1) classifying the
  one demonstrated SQLite lock/busy shape as a new, narrow, retryable code
  distinct from every other repository failure, and (2) a bounded
  (3-attempt), short jittered-backoff retry at the *caller* boundary
  (`candidate_visit_adapter.attempt_candidate`) -- deliberately not inside
  the repository method again, which is what the reverted attempt already
  tried. No schema change; no change to Reviewed truth, concurrent-sibling
  Event reuse, or ambiguous-boundary arbitration. 4 new tests (1
  deterministic real-SQLite-lock end-to-end test, 3 fast mock-based
  tests), each independently confirmed RED against the pre-fix code and
  GREEN after. Tier 1/2: 231 passed, 0 failed. Tier 3 (full Core gate):
  5109 passed, 3 failed -- 2 already-disclosed pre-existing
  (`test_place_biodiversity_summary_repository.py`) and 1
  (`test_transport_worker.py`) confirmed unrelated by import-graph proof
  (a separate Camera Node-side package, zero code path to either changed
  file) plus a clean 5/5 re-run in isolation -- zero regressions
  attributable to this milestone. See the report for full detail,
  including honestly-disclosed remaining risk (an orphaned-media-file edge
  case on a failed-then-retried attempt, pre-existing and not introduced
  by this fix; the write transaction still does more work than strictly
  minimal while holding SQLite's lock, a real but separately-scoped future
  opportunity; WAL mode/a higher `busy_timeout` were not empirically
  tested, deliberately, given this exact codebase's own documented prior
  negative result from changing the shared engine's transaction
  configuration).
- **Prior accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views (see
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)).
  Classification **B** -- an integrated multi-camera product pass on top
  of the already-accepted Camera/Source + Multi-Camera Maturity v1
  foundation (cross-camera association engine, Area vocabulary, provider
  compatibility -- that milestone's own report had gone missing from this
  file's own bookkeeping, corrected here). A real correctness defect found
  and fixed with principled nuance across two rounds of correction (Tier 1
  test evidence, then a full Tier 3 Core run) rather than a blanket
  overcorrection: an archived camera's history was unreachable from every
  discovery surface; the fix preserves every already-tested current-
  active-observatory default exactly (Bird Log overview, Wildlife
  Insights, Biodiversity, Place Activity Report/Today) while making that
  real history reachable by explicit camera selection, with Place Story
  and research/conservation export unconditionally inclusive where no
  existing test disagreed. Today now surfaces its own already-computed
  per-camera activity/evidence-source facts for the first time; Bird Log's
  camera filter now reaches its overview list; Zone Insights' Place-wide
  aggregate coverage was a naive camera-hours sum, now a real elapsed-time
  union matching Today's own semantics; Dashboard distinguishes "some
  cameras need attention" from "every armed camera needs attention"; a
  real, measured concurrency proof (genuine concurrent threads, 2-camera
  and 4-camera-asymmetric topologies) found zero cross-Stream contamination
  and no starvation, and separately found, root-caused, and honestly
  disclosed (not shipped -- an attempted fix did not reliably help) a real
  occasional lost-candidate-Visit reliability gap under real concurrent
  write contention; a comprehensive, real, executable 3-camera product-
  shaped scenario proves the whole chain -- identity, coverage, overlap
  dedup, health, correction propagation -- coheres end to end. See the
  report for full detail and honestly-disclosed remaining gaps.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology (see
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
  Classification **B** -- a real, working, submission-ready iNaturalist
  workflow (eligibility preview with per-record reasons, explicit never-
  inferred location/media consent, batch prepare, a destination-shaped CSV
  confirmed directly against iNaturalist's own open-source bulk-import
  code, fingerprint-based staleness detection, and a self-reported
  external-result close-the-loop step -- proven end to end by a real,
  executable 12-Visit product-shaped scenario test) plus a bounded,
  additive Darwin Core Occurrence-core export (`basisOfRecord=
  "MachineObservation"`, GBIF's own recommended camera-trap value); eBird
  and direct GBIF publication both honestly, evidence-backed deferred
  rather than built -- eBird's own current "Rules and Best Practices"
  (checked 2026-08-25) explicitly excludes feeder/trail-camera data
  ("eBird is designed to collect in-person observations of living wild
  birds"), and GBIF direct publication requires organizational
  Participant-Node endorsement, not a backyard-user workflow. No live,
  authenticated destination submission exists anywhere in this milestone
  (Phase 26: no unsafe credential-storage workaround invented) -- a user
  uploads the generated file themselves. Two real security findings made
  and fixed during the milestone's own work: a CSV-injection gap in the
  one shared CSV writer behind every export in this codebase (generic
  research export, Camtrap DP, Darwin Core, and the new ecological CSV
  alike), and a `javascript:`-scheme external-URL gap on the self-reported
  result field. See the report for the full official-source destination
  research (URLs, quotes, access dates) and real, honestly-recorded
  remaining gaps (no live OAuth submit, no media-byte inclusion, no
  single-Visit deep-link pre-selection).
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters (see
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
  Classification **B** -- a real canonical attention-selection layer
  (`ProductRepository.sync_attention_signals`) composed entirely over
  already-accepted facts (`place_story`, `daily_digest`/its weekly reuse,
  the existing `ProductAlertModel` review/monitoring/storage/journal alert
  system), never a second computation path; genuine semantic-dedup work
  (two real double-notification anti-patterns found and fixed by tests, not
  merely by review -- first-seen vs. the 1st-species diversity milestone, and
  the underlying "first confirmed" fact computed two different ways in two
  different subsystems); reused, not reinvented, health/storage debounce;
  new per-user notification preferences (the product's first per-user
  settings row) with quiet hours evaluated in the viewer's own browser-local
  time (deliberately avoiding a server/Place timezone that does not exist);
  foreground-only browser-notification delivery (Phase 22 Decision B --
  Web Push explicitly evaluated and deferred, no cloud/push infrastructure
  added); a real, executable Monday-through-Sunday product-shaped quiet-week
  test proving the whole week stays calm (<=14 total attention items, zero
  ever `immediate` urgency). See the report for real, honestly-recorded
  remaining gaps (Web Push, detector/model-unavailable health attention,
  global not-per-user read/dismiss state, coarse Place Story deep-link
  scoping).
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk (see
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
  Classification **B** -- strong mobile experience and a clear secure
  remote posture with bounded external-network/PWA gaps. A verified
  navigation fix (a ~20-item sidebar that previously stacked in full above
  every page's own content below 980px is now a compact top bar + off-
  canvas drawer + 4-item bottom nav, proven overflow-free across 10 real
  automated phone-width screenshots); a from-scratch bounded PWA shell
  (manifest, icons, a service worker that only ever caches Vite's own
  immutable hashed assets, never navigation/API/data); LAN access made
  genuinely discoverable (`GET /api/product/connection` + a new Settings
  card); a private-overlay-network (Tailscale-compatible) remote-access
  posture investigated against real architecture and documented, with
  direct public-internet exposure and a cloud relay explicitly not built;
  new CORS regression coverage where none existed. Also closed, ahead of
  the broader mobile work, a bounded pre-existing correctness defect in
  the accepted Place Intelligence primitive `place_change_summary.py`
  (see "Bounded return-after-absence correction," below). Schema
  unchanged. See the report for real, honestly-recorded remaining gaps
  (Visit/Stream/Settings page density, a pre-existing Review Queue
  `product_category` data gap, no login rate-limiting, no live external-
  overlay-network validation possible in this sandbox).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place (see
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
  Classification **B** -- major useful capability, bounded history/story
  gaps (period summaries not built, pending a measured performance cost;
  environmental-context/weather caveats not yet composed onto a
  before/after insight; no dedicated taxon/Feature story page; no
  representative imagery on Story cards -- see the report's "Remaining
  major PRODUCT opportunities"). Schema unchanged (v55 -> v55): a pure
  derived read-model (`mockingbird.analytics.place_story.PlaceStoryEvent`)
  composed entirely from already-authoritative facts, no new table.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding (see
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
  Classification **B** -- major useful capability, bounded feature/data-
  model maturity gaps (environmental-context/weather caveats not yet
  composed onto a before/after result; a Feature can only link to one
  camera/Zone; no representative evidence or ranked comparison view yet --
  see the report's "Remaining major PRODUCT opportunities"). Two new
  additive tables (schema 54 -> 55): `PlaceFeatureModel` and
  `PlaceFeatureChangeEventModel` -- the first discrete before/after
  change-event model in this codebase, closing a gap two prior milestones
  both explicitly recorded as their own honest ceiling.
- **Push state:** Local accepted state. Do not push without explicit
  authorization.
- **Production detector:** MDv5a ONNX
- **Production threshold:** `0.1`
- **Production visual species-identification system:** BioCLIP-2 +
  Identification Eligibility / Abstention

**BioCLIP 2.5.** Explicitly rejected for release promotion. Reason: it
improved positive bird identification but showed unacceptable
confident-wrong/non-abstaining behavior on real hard negatives.

**SpeciesNet.** Not production bird identification. It remains an
unpromoted broader-wildlife lead based on external-domain mammal evidence,
pending genuine MockingBird-field evidence.

## 2. Current acoustic release state

**Acoustic / BirdNET: ACCEPTED -- RELEASE-READY OPTIONAL.** The milestone
is complete and frozen unless concrete evidence exposes a defect.

Established facts:

- substantial acoustic/runtime/multimodal functionality exists;
- `birdnetlib` code is Apache-2.0;
- the BirdNET model weights used by MockingBird are CC BY-NC-SA 4.0 /
  NonCommercial;
- official MockingBird packaging must not redistribute those BirdNET model
  weights;
- a build-time guard (`verify_no_nc_licensed_acoustic_model_redistribution`
  in `scripts/build_local_product.py`) now enforces that packaging
  boundary;
- BirdNET/model acquisition remains external and optional (the
  `classifier-birdnet` pip extra -- a dependency declaration, not a
  redistribution);
- core visual MockingBird remains functional without BirdNET;
- real Windows USB microphone capture has been validated;
- real BirdNET inference over captured audio has been validated;
- concurrent visual + audio capture has been validated;
- device failure/reconnect behavior has been exercised;
- Today/Bird Log multimodal count/row contradiction was fixed;
- macOS unsupported mic behavior now fails honestly;
- the documented BirdNET confidence environment setting now actually
  works;
- an unbounded acoustic in-memory segment list was bounded.

Remaining bounded gaps -- classified as bounded product/field gaps, **not**
reasons to reopen the acoustic architecture:

- no product-facing frontend acoustic health/status surface yet;
- no true physical mid-session microphone unplug acceptance;
- no multi-hour acoustic soak;
- no natural wild-bird acoustic field session from the accepted test
  hardware;
- no audio equivalent of visual Privacy Zone redaction/exclusion beyond
  the currently documented privacy boundary.

Acoustics are optional in the public release because of
licensing/distribution posture, not because the core implementation is
considered merely experimental.

**Licensing posture.** Commercial use of the BirdNET model weights is
**not** legally approved. Deliberately bundling/redistributing the model
into a commercially-directed distribution (paid support, a
crowdfunded/paid appliance, a hosted paid service) is not allowed under CC
BY-NC-SA 4.0 -- the clear case that license exists to restrict. Whether an
individual user's own private, non-commercial use of MockingBird+BirdNET
(the model is never redistributed by MockingBird itself) could ever be
implicated merely because the surrounding open-source project also accepts
donations or sells optional paid support remains genuinely **unresolved**;
the existing acceptance record recommends legal review before any
commercial-adjacent distribution decision actually touches the acoustic
feature, and does not resolve the question itself. This caveat is
preserved here, not relaxed.

## 3. Current authorized milestone

**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.**

Storage / Retention / Disk-Pressure & Recovery Closure v1 (directly
authorized outside this file, as a bounded release-critical storage/
reliability milestone, reconciled here at its own closure) is now accepted
at classification **B** -- see §1, above, Lane M, §6, below, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
for the full record. Determines, with real directly-measured evidence, the
cause of the Windows Host free-space decline this file's own 2026-08-28
Lane R entry (below) first surfaced and left open: **disposition B**
(MockingBird development/test-artifact accumulation -- `deploy_windows_
dev.py`'s own never-garbage-collected runtime/model cache, 38.5GB, the
single largest consumer found anywhere in the investigation, plus the
field-acceptance recorder's own real output directory, 11.5GB -- together
accounting for roughly 72% of the exact dated decline window; neither path
is reachable by a real end-user installation). The dominant contributor is
fixed (`--gc-cache`, applied live against the real Windows dev host). This
closure classifies **B**, not A, because the remaining ~28% of the exact
decline window was not individually attributed to a single further cause
(disclosed honestly rather than forced to round), and because three real,
precisely-disclosed, safe-direction product-side retention findings
(imported-media over-retention against its own documented contract; a
`"staging"`-batch purge-path gap; a cosmetically-misnamed, slowly-
unbounded `storage_cleanup_history` constant) were deliberately left
disclosed rather than fixed under this milestone's own bounded time
budget, each requiring either new test coverage this milestone did not
build or a change to the highest-stakes retention-eligibility code this
milestone judged not warranted without it. This closure does **not**
itself authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone. `roadmap.md` was not
edited -- this milestone is a bounded investigation/dependency-tooling fix,
not a roadmap-scope change.

Non-Interactive Field Acceptance Authentication & Session Access v1
(directly authorized outside this file, as a bounded release-critical
security/correctness dependency milestone -- not a product capability,
reconciled here at its own closure) is now accepted at classification
**A** -- see §1, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record. Closes the recurring field-acceptance authentication
blocker Lane R's own three most recent attempts (2026-08-25, 2026-08-26,
2026-08-28, all recorded below) hit, without an authentication bypass,
without the operator's personal credentials, and without weakening
production security -- see §1, above, for the complete accounting
(mechanism, schema change, real live proof against a disposable isolated
instance, full Tier 1/2/3 validation). This closure does **not** itself
authorize the next Representative Field Acceptance / Gate A session --
that session is still gated on the same global product-roadmap
reconciliation this file's own governing phase label protects (see
"CURRENT PHASE," above) -- and does **not** authorize External Pre-Release
Acceptance or Final Release Hardening. The next daylight Gate A session,
whenever separately authorized, needs exactly one new step before it
starts: an Administrator (the operator) runs, once, against the real
instance, `python scripts/manage_field_acceptance_credential.py create`,
then exports the printed token as `MOCKINGBIRD_ACCEPTANCE_TOKEN` -- no
further auth archaeology should be needed for that session. `roadmap.md`
was not edited -- this milestone is a bounded dependency fix, not a
roadmap-scope change.

Representative Daylight Field Acceptance & Gate A Evidence v2 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **B** -- see §6 Lane R, below, and
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md)
for the full record. Accepted HEAD is unchanged (`80e1bb3`) -- this
milestone touched zero product/perception/admission/Visit/evidence/
classification/schema code; it only ran and cleanly stopped a fresh
Windows dev deployment of the already-accepted build for verification.
This does **not** close Lane R/Gate A: no live field session ran. Unlike
the two immediately-preceding attempts, every environmental and
infrastructure precondition (daylight, reference Camera Node health, GPU/
detector health, storage headroom, acceptance-recorder readiness) was
independently re-confirmed healthy this time -- the sole remaining
blocker, isolated more precisely than either prior attempt could isolate
it, is the identical authentication precondition first found 2026-08-25
(real sign-in required on every session-relevant endpoint, empirically
re-confirmed today via `401` on `GET /api/streams`/`GET /api/visits`
against the freshly redeployed accepted HEAD; no credentials exist;
standing user policy against asking again or routing around it via a
disposable instance for this class of milestone). Gate A's evidence body
is unchanged -- still exactly the two real 2026-08-19/2026-08-20 daylight
cohorts, for the third consecutive milestone attempt. No release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

Whole-Product UI / Accessibility / Performance Closure v1 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **A** -- see §1, above, Lane Q, §6, below, and
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the full record. This closes Lane Q as an integrated pass -- the
whole-product responsive/accessibility/performance/multi-camera/error-
recovery/acoustic-status evaluation this file's own Lane Q text had been
waiting on since it was first named. It does **not** authorize Lane R,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. Do NOT automatically
authorize, by adjacency to this closure: a `reviewed-product-loop.spec.ts`
rewrite (real, disclosed, precisely diagnosed as test-suite-only
staleness this milestone -- not a live product defect, not urgent); a
keyboard-driven Zone-polygon-drawing editor (real, disclosed, pre-
existing, optional/advanced-feature scope); the larger-than-previously-
documented dead-CSS cleanup or the narrow raw-exception-text hardening
(both real, disclosed P2 items, neither automatically the next milestone
by adjacency).

One-Release Roadmap & Scheduler Reconciliation v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- a documentation/state-governance milestone,
touching zero product/test/schema code. It reconciles this file and
`roadmap.md` to one coherent release doctrine: MockingBird has one public
release; there is no public "v0.1" product stage, no beta product
release, and no separate before-v1.0 roadmap phase; External Pre-Release
Acceptance (roadmap.md's Gate G, renamed from "External Beta Acceptance")
and internal release-candidate builds remain allowed as pre-launch
validation/engineering mechanics, never a separate product stage; Final
Release Hardening (Lane S, above) is readiness-triggered, not
version-number-triggered. See §1, above, and
[one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
for the complete accounting, including confirmation that no lane, gate, or
roadmap capability was added, removed, or promoted by this pass, and every
dated historical milestone title/decision label that happened to use
"v0.1"/"beta" vocabulary at the time was left verbatim. This closure does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone --
see the bold statement immediately above, unchanged by this closure.

Camera Node Upgrade & Compatibility Recovery v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, Lane L, §6, below, and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md)
for the full record, including two real defects found and fixed live
during real reference-Pi acceptance (a universal transport-path crash
under the already-accepted `ProtectHome=true` hardening, and two
automatic-recovery gaps) and one honestly-disclosed remaining reservation
(`rollback()` does not restore an already-changed systemd unit template).
This closes Lane L's one specifically-named remaining gap; it does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** reopen any other part of the
already-accepted Camera Node install/reboot/reprovision/replacement
work.

Representative Multi-Camera Field Acceptance & Release-Budget Evidence v1
(directly authorized outside this file, reconciled here at its own
closure) is now accepted at classification **B** -- see §1, above, and
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md)
for the full record. This does **not** close Lane R/Gate A -- no live
field session ran (environmental conditions, not a product defect; see
Lane R, §6) -- and does **not** authorize a next milestone by itself; it
found and fixed one narrow, unrelated release-engineering defect (a
Windows dependency-pin gap) while re-verifying execution-readiness for
the next daylight session.

Concurrent Candidate Visit Persistence Reliability v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md)
for the full record. This closes the one specific, bounded item named
below (the lost-candidate-Visit concurrent-write reliability gap); it does
**not** reopen or advance any other part of Multi-Camera Place Experience
v2's own remaining scope.

Multi-Camera Place Experience v2 (directly authorized outside this file,
reconciled here at its own closure -- see §16) remains accepted at
classification **B** -- see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
and §1/§6 Lane F, above/below, for the full record. Do NOT automatically
authorize, by adjacency to this closure: notification-level (Calm
Attention) cross-camera grouping; Place Story wildlife-event source
attribution; camera-filter UI consolidation; multi-camera Place Feature
linking; or broad multi-site -- each individually real and recorded in the
report's "Remaining major PRODUCT opportunities," none automatically the
next milestone by adjacency. (The one item this same list previously named
-- "a dedicated follow-on investigation into the real, disclosed occasional
lost-candidate-Visit concurrent-write reliability gap" -- is no longer an
open item: Concurrent Candidate Visit Persistence Reliability v1, above,
is exactly that dedicated investigation, and it reached a proven, validated
fix, not merely an investigation.)

Ecological Interoperability & Submission Workflows v1 (directly authorized
outside this file, reconciled here at its own closure -- see §16) is now
accepted at classification **B** (a real, working, submission-ready
iNaturalist workflow proven end to end by an executable 12-Visit
product-shaped scenario, plus a bounded additive Darwin Core export; eBird
and direct GBIF publication both honestly, evidence-backed deferred rather
than built -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
Calm Attention & Notifications v1 (directly authorized outside this file,
reconciled here at its own closure -- see §16) is now accepted at
classification **B** (a real canonical attention-selection layer composed
entirely over already-accepted facts, genuine semantic-dedup fixes found by
tests, reused health/storage debounce, new per-user preferences and quiet
hours, foreground-only browser notifications with Web Push deliberately
evaluated and deferred, and a real executable product-shaped quiet-week
proof -- see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
Mobile & Remote Experience v1 remains accepted at classification **B**
(strong mobile experience and a clear secure remote posture with bounded
external-network/PWA gaps -- see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
That milestone also closed, as its own bounded Phase 0, the
`place_change_summary.py`/`_presence_status` threshold gap the Place
Story & Seasonal Timeline v1 report (below) had recommended as future
work -- that item is now resolved, not still outstanding.
Place Story & Seasonal Timeline v1 remains accepted at classification
**B** (major useful capability, bounded history/story gaps -- see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
Place Features & Habitat Change v2 remains accepted at classification
**B** (major useful capability, bounded feature/data-model maturity
gaps -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
Environmental Context v2 remains accepted at classification **B** (major
useful capability, bounded provider/statistical/UI limitations -- see
[environmental-context-v2-report.md](environmental-context-v2-report.md)).
Place / Yard Intelligence v2 remains accepted at classification **B**
(major useful capability, bounded maturity gaps -- see
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)).
Camera / Source Experience & First-Hour Setup Closure v1 remains accepted
and closed at classification **C** (usable, bounded further closure
remains -- see Lane G, §6). No new implementation milestone is currently
authorized. The next milestone will be selected only after the governing
external process verifies this execution state against the complete
remaining release queue, the remaining Calm Attention & Notifications
opportunities (Web Push for a genuinely closed-browser interruption,
deliberately deferred; detector/model-unavailable Observatory Health
attention; per-user, not global, read/dismiss state; precise per-taxon/
per-Feature Place Story deep links; a live attention-sync diagnostics
surface -- see that report's "Remaining major PRODUCT opportunities"), the
remaining Mobile & Remote Experience product
opportunities (progressive disclosure for the dense Visit/Stream/Settings
pages; a genuine pre-existing `ReviewQueuePage` `product_category`/
"animals"-tab gap, found and documented, not fixed; no login rate-
limiting, a real pre-existing gap whose relevance this milestone's own
expanded network reachability directly heightens; no live external-
overlay-network (Tailscale/WireGuard) validation was possible from this
sandbox -- see the Mobile & Remote Experience v1 report's "Remaining
major PRODUCT opportunities"), the remaining Place Story product
opportunities (period summaries -- deferred on a measured performance
cost, not simply unattempted; environmental-context/weather caveats on a
before/after insight; a dedicated taxon/Feature story page; representative
imagery on Story cards), the remaining Place Features & Habitat Change
product opportunities (composing environmental-context/weather caveats
onto a before/after result, multi-camera Feature linking, representative
evidence in Feature detail, a ranked feature-comparison view -- see the
Place Features & Habitat Change v2 report), the remaining Place/Yard
Intelligence product opportunities (seasonality maturation against real
history, a `source_quality_signals` UI surface -- the habitat before/
after change-event data model itself is now closed by that milestone),
**and** the remaining Environmental Context product opportunities
(deeper historical backfill via Open-Meteo's archive/ERA5 endpoint, wind/
cloud-cover statistical associations, a dedicated diagnostics/Explore-page
surface for weather -- see the Environmental Context v2 report). Do not
choose the next milestone by adjacency to this one.

Do NOT automatically authorize:

- a managed/fleet Camera Node updater, unattended/automatic upgrade
  scheduling, remote-triggered updates, artifact signing/PKI beyond
  checksums, or a graduated ("compatible older") wire-protocol tier beyond
  the Host's own existing exact-match gate, merely by adjacency to Camera
  Node Upgrade & Compatibility Recovery v1's closure -- each explicitly
  out of that milestone's own scope, none automatically the next milestone;
- a standalone follow-on campaign to close the two items Camera Node
  Upgrade & Compatibility Recovery v1 left honestly disclosed (`rollback()`
  not restoring an already-changed systemd unit template; its own
  directory swap's narrower residual crash-window gap) -- both real and
  recorded, neither automatically the next milestone by adjacency unless a
  concrete recurrence is found;
- live, authenticated iNaturalist OAuth submission, or any eBird workflow
  of any kind, merely to close Ecological Interoperability & Submission
  Workflows v1's own deliberately-deferred external-authorization boundary
  -- see that report for the full evidence (eBird's own current policy
  conflict; no secure server-side credential-storage pattern exists yet)
  this decision rests on;
- direct GBIF publication as a standalone follow-on -- see that report's
  destination research for why this remains institutional, not a
  backyard-user workflow;
- ecological-submission media-byte inclusion, or a single-Visit deep-link
  pre-selection on the Ecological Destinations page, as a standalone
  follow-on campaign -- each individually real and recorded, neither
  automatically the next milestone by adjacency;
- Remote Field Productization;
- standalone Web Push (VAPID/subscription persistence, a genuine outbound
  call to a third-party push service) merely to close Calm Attention &
  Notifications v1's own deliberately-deferred Phase 22 Decision B gap --
  see that report for the full local-first/privacy reasoning this decision
  rests on;
- a Review Queue product_category/"animals"-tab fix, per-user read/dismiss
  state, or precise per-taxon/Feature Place Story deep links as a
  standalone follow-on campaign -- each individually real and recorded in
  the Calm Attention & Notifications v1 report, none automatically the
  next milestone by adjacency;
- further Mobile/PWA/remote-access work as a standalone follow-on
  campaign -- specifically: progressive disclosure for the dense Visit/
  Stream/Settings pages, the `ReviewQueuePage` `product_category`/
  "animals"-tab fix, login rate-limiting, or a live external-overlay-
  network acceptance pass -- each individually real and recorded, none
  automatically the next milestone by adjacency;
- Local Species/Taxon Prior;
- another classifier benchmark;
- Provider Integrations;
- a second weather provider or user-facing provider choice;
- Open-Meteo archive/ERA5 deep historical backfill;
- a Feature/Zone multi-camera join table;
- Place Story period summaries, weather-caveat composition, or dedicated
  taxon/Feature story pages, as a standalone follow-on campaign;
- Land Management / Agriculture as a separate campaign;
- notification-level (Calm Attention) cross-camera health grouping, Place
  Story wildlife-event source attribution, or camera-filter UI
  consolidation as standalone follow-on campaigns -- each individually
  real and recorded in the Multi-Camera Place Experience v2 report, none
  automatically the next milestone by adjacency. (The lost-candidate-Visit
  concurrent-write reliability gap that report also found, root-caused,
  and deliberately did not fix is **no longer on this list** -- Concurrent
  Candidate Visit Persistence Reliability v1, see §1, closed it at
  classification A.);
- broad multi-site, merely because single-Place multi-camera work just
  closed;
- final Release Hardening.

## 4. Product/release guardrails

MockingBird is:

- local-first;
- hardware-agnostic;
- nature-first rather than surveillance-first;
- bird-first but wildlife-native;
- evidence-backed;
- Place-centered;
- cloud-optional;
- human-correctable;
- abstention-friendly.

Canonical epistemic classes: **Measured**, **Inferred**, **Reviewed**.

Human correction is authoritative. Model inference cannot silently become
reviewed truth.

Raspberry Pi is reference Camera Node hardware, not product identity.
Native Windows remains the first end-user Host acceptance target.
WSL/Linux development success does not equal native-Windows product
acceptance.

Privacy Zones currently mean trigger-level exclusion, not guaranteed pixel
redaction of all retained frames unless future code explicitly implements
that.

User data is not the primary monetization strategy. Core functionality
must remain complete under Local Only privacy.

## 5. Frozen / substantially accepted lanes

Summarized without milestone archaeology; see `roadmap.md` and the linked
accepted-milestone docs for detail if a future task genuinely needs it.

**Observation / Reviewed Truth.** Accepted foundations include Visit →
Evidence → Review → Observation; review/correction/revision; actor
attribution; evidence lineage; Today/history truth.

**Perception / Admission.** Accepted: MDv5a production detector;
small/far-bird work; ambiguous-boundary/admission fixes; per-Stream Visit
authority; evidence-cache correction; scene-confusor suppression;
perception replay; multi-subject Visit foundations.

**Site-Specific Learning.** Accepted and frozen. Reviewed-negative
scene-confusor adaptation accumulates/evaluates reviewed evidence, is
production-disabled by default, and requires explicit per-Stream
enablement for production effect. Do not automatically build Local Taxon
Prior or calibration on top of this.

**Species Classification.** Accepted and frozen: BioCLIP-2 stays
production; BioCLIP 2.5 rejected; SpeciesNet not promoted.

**Broader Wildlife.** Accepted structurally. Non-bird review/history/
product semantics work. Automatic mammal species identification remains
limited.

**Identity / Multi-User.** Accepted: Viewer / Reviewer / Administrator;
server-side sessions; authorization; actor attribution; audit; review
concurrency; backup/restore.

**Environmental Context.** Accepted; extended, not frozen -- Environmental
Context v2 (2026-08-25) added the first general weather provider
(Open-Meteo) on top of the accepted solar/daylight foundation: eight
provider-neutral metrics, always `information_class="inferred"`; a
second, independent `weather_enabled` opt-in (schema v53 -> v54) gating
every outbound network call separately from the existing coordinate
setting; bounded lazy caching; Place-relative temperature and wet/dry
precipitation associations composed onto the existing `conditional_
association` primitive alongside `habitat_associations`. See
[environmental-context-v2-report.md](environmental-context-v2-report.md).
Substantial product-roadmap opportunity remains (deeper historical
backfill via the archive/ERA5 endpoint, wind/cloud-cover statistical
associations, a dedicated diagnostics/Explore-page surface); do not treat
this lane as closed.

**Habitat & Phenology.** Accepted/frozen.

**Biodiversity & Place Intelligence.** Accepted; extended, not frozen --
Place / Yard Intelligence v2 (2026-08-25) added regularity narrative,
seasonal pattern, temporal pattern, per-Source activity/quality, and a
weekly digest on top of the already-accepted foundation. Place Features &
Habitat Change v2 (2026-08-25, same day) closed that milestone's own
recorded "habitat before/after change-event data model" gap: a durable
Place Feature entity, a Reviewed change-event timeline, and a before/after
comparison engine built on pure reuse of the existing `conditional_
association` primitive -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md).
Place Story & Seasonal Timeline v1 (2026-08-25, same day) composes all of
the above -- plus Reviewed phenology observations and Reviewed Feature
change events -- into one Place-wide, dated, filterable, correction-safe
timeline (`GET /api/place/story`), no new schema; see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
for the full record, including a genuine previously-undiscovered gap
found in `place_change_summary.py`'s own already-accepted threshold logic
(worked around locally, not patched at its source -- see that report's
"Truth / provenance"). Substantial product-roadmap opportunity still
remains (year-over-year seasonality; environmental-context/weather
caveats not yet composed onto a before/after result or a Story insight;
multi-camera Feature linking; a ranked feature-comparison view; Place
Story period summaries; a dedicated taxon/Feature story page;
representative imagery on Story cards -- see that report's and
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)'s
and
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)'s
respective "Remaining major PRODUCT opportunities"); do not treat this
lane as closed.

**Camera / Acquisition Foundations.** Substantial accepted work: native
Camera Node path; ONVIF; RTSP/RTSPS; offline/recorded ingest; camera-trap
ingest; provider-neutral Source/Stream architecture. First-hour product
experience materially closed (Add Camera preview, credential honesty) --
see Lane G.

**Diagnostics / Storage / Recovery Foundations.** Substantial accepted
work: health/diagnostics; Doctor/support concepts; storage health;
retention; backup/restore; recovery. Final integrated product acceptance
remains open (see Lane R, below).

**Research / Conservation.** Substantial accepted work: conservation
reporting; effort/coverage; research-safe eligibility/export; Camtrap DP;
Darwin Core Occurrence-core export (2026-08-25, additive to Camtrap DP, not
redundant with it -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md));
contributor/research provenance.

## 6. Global remaining execution queue

This is the most important section. Lanes are not removed merely because
they are not next.

**Four release-shape categories.** Every lane below already sorts into one
of four categories; renaming the release model (§7, above) does not change
which lanes are release-critical, deferred, or later -- it only fixes the
words used to describe them:

- **A. Release-critical** -- must be complete/credible before the one
  public launch. Lanes marked **RELEASE-CRITICAL** below carry this:
  representative field correctness/whole-product acceptance (Lane R),
  camera/source golden path (Lane G), storage/retention/recovery (Lane M),
  Local Only/privacy (Lane N), platform/runtime support truth (Lane O),
  release/distribution closure (Lane P), accessibility/performance (Lane
  Q), appliance/update/recovery (Lane L) -- plus, as the internal gates
  above become credible, External Pre-Release Acceptance and Final
  Release Hardening themselves (Lane S, below; roadmap.md Gates F-G).
- **B. Pre-release decisions** -- decisions required before launch, not
  necessarily implementation milestones: the codebase `LICENSE` and full
  ffmpeg distribution licensing (Lane P); the still-open BirdNET
  commercial-adjacent legal posture (§2, above); platform-support
  declarations (Lane O, "RELEASE DECISION REQUIRED"); Ecosystem/Provider
  Integrations scope (Lane K, "OPEN DECISION"); any other genuine
  unresolved release decision as it surfaces.
- **C. After release** -- real product development explicitly not
  required for launch, kept so it is not lost: complete remote/
  intermittent-WAN/LTE, solar/battery, custom CM4/CM5 (Lane B, and §8,
  below); research-grade remote-field acceptance; broad multi-site (Lane
  F's own explicitly-deferred remainder); native mobile (Lane E's own
  explicitly-out-of-scope remainder); advanced acoustic analytics (Lane
  A's own remaining bounded follow-up); mature automatic mammal species
  identification (Lane I).
- **D. Later / evidence-driven** -- the long-range, demand-driven queue in
  §9, below: GenICam, GigE Vision, USB3 Vision, radiometric thermal,
  specialized industrial cameras, individual-animal recognition,
  population estimates, behavior prediction, causal ecological modeling,
  large cloud/fleet infrastructure.

This is a navigational grouping over the existing lettered lanes (A-S), not
a new or renumbered lane system: no lane is removed, renamed, or promoted
between categories by this grouping, and each lane's own status text below
remains authoritative over this summary.

### A. Acoustic / BirdNET Productization

**Status:** ACCEPTED -- RELEASE-READY OPTIONAL.

Remaining bounded follow-up only: frontend acoustic health/status; longer
field soak; physical unplug/replug; natural wild-bird field evidence. Do
not schedule another acoustic architecture milestone automatically.

### B. Remote / Intermittent-WAN Field Productization

**Status:** PARTIAL -- AFTER RELEASE UNLESS A NEW CORE DEPENDENCY
APPEARS.

Existing foundation includes substantial spool; store-and-forward;
transport; retry; Host consume-to-evidence behavior; diagnostics.

Remaining: real LTE/carrier acceptance; real remote Pi deployment;
bandwidth behavior; resume granularity; extended outages; unattended
recovery; remote operator experience; solar/battery/power reality.

Remote LTE/solar/custom CM4/CM5 field deployment is **not** a release
blocker.

### C. Everyday Product / Discovery UX

**Status:** PARTIAL -- HIGH RELEASE VALUE.

Remaining: Best Moments; calm daily summary; New / Regular presentation;
unknown/unresolved handling; sparse/no-wildlife states; understandable
suggestion explanations; mostly-invisible review; coherent first-hour
product experience; report-first hierarchy.

Do not turn this into a giant redesign.

### D. Calm Notifications

**Status:** MATERIALLY DELIVERED -- Calm Attention & Notifications v1
(2026-08-25) closed this lane's decision; see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md).
Classification **B**.

Delivered: one canonical attention-selection layer over already-accepted
facts (Place Story, the daily/weekly digest, the existing review/monitoring/
storage/journal alert system); a small user-centered taxonomy (Discovery/
Insight/Needs Help/Observatory Health) and explicit urgency (immediate/
digest/in-app-only), never raw internal severity/error vocabulary; genuine
semantic deduplication (two real double-notification anti-patterns found
and fixed by tests); reused, not reinvented, health/storage debounce; a
daily/weekly digest notification reusing the existing digest computation
unmodified, suppressed when there is genuinely nothing meaningful; per-user
notification preferences (four category toggles + quiet hours, evaluated in
the viewer's own browser-local time); foreground-only browser-notification
delivery (Web Push explicitly evaluated and deferred -- Decision B, no
cloud push infrastructure added, matching this lane's own standing
instruction); an extended Attention Center and a calm "N things worth
noticing" line on Today; a real, executable product-shaped quiet-week test
proving the whole week stays calm. Schema 55 -> 56 (one additive per-user
preferences table).

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": Web Push for a genuinely closed-browser
interruption; detector/model-unavailable Observatory Health attention;
per-user (not global) read/dismiss state; precise per-taxon/Feature Place
Story deep links (today scoped to a category group); a live attention-sync
diagnostics surface.

### E. Mobile / Remote UX

**Status:** PARTIAL, MATERIALLY ADVANCED -- Mobile & Remote Experience v1
(2026-08-25) closed the core decision this lane was waiting on; see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md).
Classification **B**.

Delivered: a verified (10 real automated phone-width screenshots, zero
overflow) responsive navigation fix -- top bar + off-canvas drawer +
4-item bottom nav, replacing a sidebar that previously stacked in full
above every page below 980px; a bounded, safety-reasoned installable PWA
shell (manifest, icons, a service worker that only ever caches Vite's own
immutable hashed assets, never navigation/API/data -- no offline data
claim made anywhere); LAN access made discoverable (`GET /api/product/
connection` + a Settings card, with a corrected, no-longer-stale
`--allow-network` help string); a private-overlay-network
(Tailscale-compatible) posture chosen and documented as the supported
away-from-home path, with direct public-internet exposure and a cloud
relay explicitly, plainly documented as unsupported/not-built; new CORS
regression coverage. Native mobile remains explicitly out of scope,
unchanged.

Remaining, not closed by this pass (see the report's "Remaining major
PRODUCT opportunities" for the full record): progressive disclosure for
the dense Visit/Stream/Settings pages; a pre-existing `ReviewQueuePage`
`product_category` gap (found, documented, not fixed -- independently
reproduced against an unmodified existing e2e spec); no login rate-
limiting (pre-existing, real, and directly more relevant now that this
lane increased network reachability); no live external-overlay-network
(Tailscale/WireGuard) acceptance was possible from this sandbox --
validated structurally only. Do not equate this closure with a finished,
fully-polished mobile product, and do not automatically authorize a
follow-on Mobile/PWA campaign by adjacency -- see §3.

### F. Multi-Camera / Multi-Site

**Status:** MATERIALLY ADVANCED -- Multi-Camera Place Experience v2
(2026-08-26) closed this lane's integrated-acceptance decision; see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md).
Classification **B**.

Camera/Source + Multi-Camera Maturity v1 (2026-08-23) had already built the
real foundation this lane's own text below was actually waiting on
(cross-camera duplicate-encounter association, Area vocabulary, provider
compatibility, health coherence) -- that milestone's own report was
missing (only a `-contract.md` existed, no `-report.md`), which is why
this lane's status had not been updated to reflect it; corrected here.
Delivered this milestone: a real, previously-hidden defect found and fixed
with principled nuance (an archived camera's history was unreachable from
every discovery surface, contradicting this codebase's own documented
archive-only-preserves-history doctrine; the fix deliberately preserves
already-tested current-active-only *defaults* on Bird Log/Wildlife
Insights/Biodiversity while making that real history reachable by explicit
camera filter and by period-scoped reports); Today surfacing its own
already-computed per-camera activity/evidence-source facts for the first
time; a Bird Log camera filter reaching the overview list, not only the
per-species drilldown; a real coverage-union fix for Zone Insights'
Place-wide aggregate (was a naive per-camera-hours sum); Dashboard
distinguishing "some cameras need attention" from "every armed camera
needs attention"; a real, measured (2-camera and 4-camera-asymmetric,
genuinely concurrent real-thread) admission/assembly-layer concurrency
proof with zero cross-Stream contamination and no starvation found; a
comprehensive, real, executable product-shaped scenario proving the whole
chain -- identity, coverage, overlap dedup, health, correction propagation
-- coheres end to end. Schema unchanged (v57 -> v57): every fix is a query-
scope correction or an additive field on an already-derived response
object.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": notification-level (Calm Attention) cross-camera
grouping beyond the Dashboard status-view fix; Place Story wildlife-event
source attribution (the field exists, populating it needs restructuring a
shared SQL-aggregation layer, not a field-threading exercise); consolidating
at least 6 independently-implemented camera-filter UI controls into one
canonical component; multi-camera Place Feature linking; real GPU/CUDA-
driver-level concurrent-inference measurement (needs real hardware this
sandbox lacks); a multi-hour concurrent soak beyond the single-pass
measured proof; the pre-existing, disclosed 2-Stream cap on the separate
legacy motion pipeline (RTSP/USB/local providers, not the modern
Observation Engine's own Camera Node path).

**Reliability lane status (Concurrent Candidate Visit Persistence
Reliability v1, same-day follow-on):** this lane's one item touching the
critical Visit write path -- occasional silent loss of an admitted
candidate under real concurrent multi-Stream SQLite writes -- is now
**CLOSED** at classification **A**; see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
Every other item in the "Remaining, not closed by this pass" list directly
above is unaffected and still open.

True multi-site remains a separate product/architecture decision. Do not
silently make it release scope, and do not self-authorize it by adjacency
to this lane's closure.

### G. Camera / Source Experience

**Status:** PARTIAL, MATERIALLY CLOSED -- RELEASE-CRITICAL. Camera /
Source Experience & First-Hour Setup Closure v1 (2026-08-25) fixed two
real P0
first-hour gaps and two P1s; see
[camera-source-experience-v1-report.md](camera-source-experience-v1-report.md)
for the full archaeology, gap table, and evidence. Release
classification: **C** (usable, bounded further closure remains).

Closed by this milestone: manual RTSP setup's separate "Auth username"/
"Auth password" fields were collected but silently discarded on every
write and never reached a real connection attempt -- now stored for real
and merged into the effective connection URL everywhere it's actually
used. Only Camera Node had a real "Check the picture" setup preview --
now RTSP/ONVIF/local/Windows-USB have the same bounded, non-persisting
preview capability, and `CameraSetupValidationResponse.preview_available`
is computed honestly instead of hardcoded `False`. A healthy camera's own
detail page had no persistent way back to reconfigure it; a dead,
unreachable duplicate Add-Camera form was removed.

Remaining, not closed by this pass: ongoing-monitoring failure-code
collapse for non-Camera-Node providers (once a Stream is armed and
running, a dead RTSP/local/Windows process's specific cause -- auth/
network/codec/decode -- is discarded in favor of a generic code; setup-
time validation is unaffected and stays fully distinguishing). No real,
reachable camera/RTSP/ONVIF/local-USB hardware or Camera Node was
available to prove actual video decode/preview end-to-end this session
(native-Windows evidence proves the real subprocess/HTTP/taxonomy/
credential-merge mechanics genuinely work against a real unreachable
host, not that a specific real camera's picture renders). Full
integrated multi-camera/whole-product acceptance remains Lane R.

### H. Site-Specific Learning

**Status:** FROZEN.

No adjacent learning expansion automatically authorized.

### I. Broader Wildlife Maturity

**Status:** FROZEN STRUCTURALLY.

Real mammal field evidence remains limited. Do not create another model
campaign solely to fill the matrix.

### J. Ecological / External Workflows

**Status:** MATERIALLY ADVANCED -- Ecological Interoperability & Submission
Workflows v1 (2026-08-25) closed this lane's decision; see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md).
Classification **B**.

Delivered: a real, working, submission-ready iNaturalist workflow
(eligibility preview with per-record reasons, explicit never-inferred
location/media consent, batch prepare, a destination-shaped CSV confirmed
directly against iNaturalist's own open-source bulk-import code,
fingerprint-based staleness detection, a self-reported external-result
close-the-loop step); a bounded, additive Darwin Core Occurrence-core
export; the destination-decision research itself (eBird's own current
policy explicitly excludes feeder/trail-camera data -- not offered, and
the product UI says why persistently, not merely in a hover tooltip; GBIF
direct publication requires organizational endorsement -- correctly
deferred as institutional); two real security findings made and fixed
(CSV injection in the shared CSV writer behind every export in this
codebase, retroactively hardening the pre-existing generic/Camtrap DP
paths too; a `javascript:`-scheme external-URL gap). Schema 56 -> 57 (two
additive tables). No live, authenticated destination submission exists
anywhere -- Phase 26 of that milestone's own brief: no unsafe
credential-storage workaround invented for a capability that does not yet
exist.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": live OAuth iNaturalist submission; media-byte
inclusion; a single-Visit deep-link pre-selection on the Ecological
Destinations page; broader batch-filter UI depth (stream/source/collection
scoping, already supported server-side via the reused
`ResearchExportFilters`, not yet exposed in the frontend).

### K. Ecosystem / Provider Integrations

**Status:** OPEN DECISION.

Candidates previously discussed: Frigate; Blue Iris; Scrypted; Home
Assistant. Do not implement all. Decide whether a minimum useful adapter
set materially improves first-release adoption. Native Camera Node +
standards-based acquisition remain the golden path.

### L. Appliance / Update / Recovery

**Status:** MATERIALLY CLOSED -- RELEASE-CRITICAL. Host side closed by
Release Engineering Foundation v1 (2026-08-25); Camera Node **upgrade**
workflow -- the one specifically-named remaining item -- closed by Camera
Node Upgrade & Compatibility Recovery v1 (2026-08-26), classification
**A**. See [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

Closed for the **Host**: an automatic, verified pre-migration safety
backup now runs before any in-place schema upgrade; a genuine post-
migration health check gates readiness; the upgrade fact is honestly
surfaced (console + Dashboard); restoring that automatic backup is the
documented rollback path; interrupted-upgrade behavior (backup failure,
mid-migration failure, post-migration integrity failure) all fail closed
and are regression-tested; real native-Windows evidence includes an
organically-occurring 18-schema-version migration on real pre-existing
data. Host↔Camera Node **wire-protocol** version compatibility
(`api_version`, `transport_protocol_version`) confirmed already
hard-gated; the Node's own `service_version` remains display-only by
deliberate choice (see the milestone report).

Closed for the **Camera Node**: `scripts/install_camera_node.py` (the
existing installer, extended rather than replaced) now runs a real
preflight (artifact well-formed, `SHA256SUMS` checksums, disk space, a
Node-local wire-protocol compatibility comparison against the currently
-installed build) before any mutation; stages and verifies a candidate
(`import mockingbird_node.app` inside its own fresh venv) before the live
install is touched at all; activates manifest-first/venv-second so any
interruption resolves to one of three well-defined, automatically
-reconciled states; automatically restores the prior known-good build if
the newly-activated one fails post-update health verification (never on a
first-ever install); and never silently accepts an unexpected `node_id`
change. Real acceptance against the project's actual reference Pi (never
upgraded since 2026-08-18, predating three later accepted Camera Node
milestones) found and fixed, live, a universal upgrade-blocking defect
(a transport-configuration path defaulting through `Path.home()`, always
broken under the already-accepted `ProtectHome=true` hardening regardless
of whether transport was ever configured -- would have broken every
Camera Node upgrading past Remote/Intermittent-WAN Transport Foundation
v1 through the accepted installer) and two automatic-recovery gaps
(`systemctl restart` failing outright not triggering rollback; a prior
crash loop's exhausted `StartLimitBurst` blocking an unrelated later
restart) -- all three fixed the same session with regression tests, not
merely disclosed. The device was fully upgraded end to end with node
identity/pairing/camera availability all confirmed unchanged.

Remaining, disclosed, not closed by this pass: `rollback()` restores code
but not an already-changed systemd unit template (a real gap this
milestone's own real acceptance encountered and worked around manually,
not closed structurally); `rollback()`'s own directory swap has a
narrower residual crash-window gap than the forward-upgrade path's
reconciliation closes; reinstall/replacement beyond what reprovisioning
already covers and broader operator-facing update/recovery UX remain
Camera Node install/reboot/reprovision's own already-accepted scope,
unaffected by this milestone. See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

### M. Storage / Retention UX

**Status:** MATERIALLY CLOSED -- RELEASE-CRITICAL. Integrated acceptance
performed by Storage / Retention / Disk-Pressure & Recovery Closure v1
(2026-08-28), classification **B** -- see §1/§3, above, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md).
Disk-pressure detection (a real, tested, graduated healthy/getting_low/
action_recommended/critical ladder), long-running storage growth (real,
directly-measured accounting on both the WSL dev host and the real Windows
deployment), cleanup/retention (349 real tests, independently re-run,
covering eligibility/idempotency/interruption-safety/transactional
ordering), DB/media consistency (traced precisely in both directions), and
backup visibility (Doctor-surfaced staleness/unreadable-count/interrupted-
restore, all real and tested) were each verified integrated, not merely
inspected in isolation. NAS/external-storage support remains an explicit
product decision, not an automatic blocker, and was not built. Real,
precisely-disclosed, safe-direction remaining gaps (imported-media
over-retention against its own documented contract; a `"staging"`-batch
purge-path gap; a cosmetically-misnamed `storage_cleanup_history` bound;
no orphan-media/no-DB-owner detection anywhere in the product) are why
this reads "materially closed," not "fully closed" -- none is
release-blocking, none causes data loss, and each was deliberately left
disclosed rather than risked as a rushed fix to high-stakes retention-
eligibility code -- see the milestone report's "Remaining risks" for the
complete, concrete list.

### N. Privacy / Contribution

**Status:** PARTIAL -- LOCAL-ONLY RELEASE-CRITICAL.

**Local Only.** Operational/default requirement. Core product must be
complete.

**Derived Data Contribution.** Doctrine exists. Do not assume operational
implementation or cloud backend exists. Never silently include:
image/video/audio; thumbnails/crops; raw frames; embeddings/reconstructable
media-derived features; local filesystem paths; free-text notes;
faces/people/vehicle imagery; precise property/home coordinates.

**Media contribution.** Separate future consent capability. Contribution
must never become required for core operation.

### O. Platform / Runtime Portability

**Status:** PARTIAL -- RELEASE DECISION REQUIRED.

Track honestly: native Windows; Linux; macOS; CPU; NVIDIA CUDA; Apple
Silicon; AMD. Use capability states: directly validated; structurally
supported; hardware-unverified; unsupported; deferred. Native Windows
remains the first end-user Host acceptance target. Do not claim
Apple/AMD support merely because an underlying ML framework theoretically
supports it.

### P. Release Engineering Foundation / Distribution

**Status:** SUBSTANTIALLY CLOSED, two items deliberately left open --
RELEASE-CRITICAL. Release Engineering Foundation v1 (2026-08-25) closed:
upgrade procedure (see Lane L); a real, currently-live dependency-closure
defect found and fixed via genuine native-Windows deployment (`astral`
missing from the packaged bundle -- would have broken *every* launch,
clean-install included) plus a regression test against the whole class of
drift; version single-source-of-truth; artifact provenance/checksum
parity with the Camera Node build script (`source_clean`); an independent
post-build artifact verifier (`scripts/verify_release_artifact.py`); this
repository's first CI automation (`.github/workflows/ci.yml` -- Core
gate, frontend build, a real structural packaging-smoke build);
`SECURITY.md`; release-artifact smoke testing; Host ↔ Camera Node
compatibility (investigated and confirmed adequate, not a gap). See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
for the complete record, including real native-Windows acceptance
evidence (Decision A).

Deliberately still open, not silently dropped: **`LICENSE`** (a
business/legal decision -- which license, and its interaction with the
still-unresolved BirdNET commercial-adjacent-distribution question in
§2, above -- outside a bounded engineering milestone's authority to
resolve unilaterally); **full ffmpeg bundling** (needs its own licensing
research, shaped like the already-completed BirdNET work -- today it is
honestly documented as a separate install step rather than silently
missing, and the recommended Camera Node golden path does not need it).
Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md` (README/site
polish, brand/trademark review) remains open per "Public release
readiness" in [roadmap.md](roadmap.md), not release-critical blocking.

Release Engineering Foundation may occur before all product development is
finished. Release Engineering Foundation is not the same as final Release
Hardening.

### Q. Whole-Product UI / Accessibility / Performance

**Status:** CLOSED AS AN INTEGRATED PASS -- Whole-Product UI /
Accessibility / Performance Closure v1 (2026-08-27) closed this lane; see
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md).
Classification **A**.

Validated live against a seeded, product-shaped 371-Visit QA instance and
real code inspection: responsive behavior (zero horizontal overflow, 4
required widths x 10 pages); touch (existing tap-target/mobile-drawer
conventions intact); keyboard/focus (sidebar nav, mobile drawer already
correct; two real Fast Review focus-management defects found and fixed);
accessibility semantics (spot-checked, sound); large real-data performance
(measured, at or below established precedent, no regression); several
cameras (3 active mixed-health + 1 archived Stream, coherent); large
review queues (89-item backlog, correctly bounded); error/recovery UX
(camera-vs-observation-runtime distinction already correct); visual
consistency (StatusPill never color-only). Closed the bounded acoustic
health/status gap (Lane A) with the smallest capability-aware addition
the brief allowed. Found and fixed one P0 (Review Queue default-tab
misclassification of imported Visits) along the way -- the real,
previously-unidentified root cause of one class of confusion this project
had repeatedly misattributed to `reviewed-product-loop.spec.ts` being an
unrelated flake. That spec itself remains red, now precisely diagnosed as
test-suite staleness (a hardcoded `productMode = true` makes the legacy
markup it targets permanently unreachable), not a live product defect --
disclosed, not fixed, a real but separately-scoped follow-up. Also
disclosed, not fixed: Zone-polygon drawing (not selection) has no
keyboard equivalent (optional/advanced feature); a larger-than-previously
-documented dead-CSS footprint; a narrow raw-exception-text edge case.
See the report for the complete finding-by-finding record.

### R. Complete Field Acceptance

**Status:** NOT DONE -- RELEASE-CRITICAL.

Component acceptance is not whole-product acceptance. Final integrated
release configuration should exercise: several cameras; visual inference;
audio if included; review; Today/history; long unattended operation;
disconnect/reconnect; Host reboot; Camera Node reboot; storage pressure;
model unavailable; backup/restore; upgrade; clean installation; actual
user operation. Remote LTE field acceptance remains separately scoped when
Remote Field is not part of release scope.

**Representative Field Acceptance & Release-Budget Closure v1 (2026-08-25)
attempted, returned Gate C -- OPEN, insufficient representative evidence.**
Not a product defect: the attempt was stopped before any Observation
session started because the native-Windows dev instance now enforces real
sign-in on every endpoint the session needed (streams, observation start/
stop, Visits, counterfactual ledger -- the pytest auth bypass was removed
as part of the accepted Local Identity / Multi-User work, 2026-08-23),
no credentials exist anywhere in this repository, and the user explicitly
declined to share real admin credentials, create a temporary account, or
participate live right now. Nothing about the frozen perception/admission/
Visit/evidence/classification stack was exercised or judged. Real,
positive, non-live evidence preserved from this attempt: the reference
Camera Node (`192.168.1.112:8787`) is reachable at the network level; the
native-Windows Host dev deployment is healthy at the accepted commit
(schema v53); the full accepted acceptance-tooling chain (recorder,
motion-screen/contact-sheet review, independent encounter table,
counterfactual ledger, `run_encounter_accounting.py`) is confirmed present
and ready to reuse. See
[representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md)
for the full record, including the standing decision for future sessions:
do not ask the user again for real credentials or live participation
unless a future milestone specifically requires human acceptance and they
explicitly agree first; ordinary auth-requiring development/validation
work should instead use a fresh, isolated dev instance with a disposable
bootstrapped local Administrator account.

**Representative Multi-Camera Field Acceptance & Release-Budget Evidence
v1 (2026-08-26) attempted, also returned no new live-field evidence --
classification B, an acceptable outcome per this milestone's own governing
brief, and a materially different shape from the 2026-08-25 attempt
above.** Not blocked by authentication this time: the session start
(20:26 EDT) was after sunset, the same "darkness produces an unusable bird
denominator" scenario 2026-08-19/2026-08-20 already demonstrated twice: a
post-sunset session produces a clean, real, but useless zero-track-
generation result, not evidence about daytime bird activity. No
Observation session was opened. Executed the "no representative
conditions" path instead and used the time to make the next daylight
session concretely more ready, not merely re-documented: found and fixed
one real, previously-hidden Windows build defect (a `click` dependency-
pin gap identical in mechanism to this codebase's own already-documented
`idna` pin) that would otherwise have cost the next session its own
debugging time; produced a fresh, independently-HTTP-verified, ledger-
retained deployable artifact of accepted HEAD ready for instant relaunch;
confirmed GPU/detector/storage/Camera-Node health; confirmed, via the
unauthenticated health endpoint only, that only one real Stream is
currently configured in the dev instance and that a second real, already-
supported Source (a Windows-native USB webcam, already hardware-validated
for the Acoustic milestone) should be wired up before the next session so
the still-open "does the concurrent-persistence fix hold under genuine
multi-camera load" question can actually be tested with two real cameras;
and documented the exact command/API sequence, acceptance-recorder
settings, and structured-log location (`.../userdata/logs/mockingbird.
log`) that session needs. See
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
Gate A's evidence body is unchanged by this session (still exactly the
two real 2026-08-19/2026-08-20 daylight cohorts) -- no release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

**Representative Daylight Field Acceptance & Gate A Evidence v2
(2026-08-28) attempted, also returned no new live-field evidence --
classification B.** For the first time in three consecutive attempts,
every environmental/infrastructure precondition was simultaneously
satisfied: session start ~15:20 EDT (mid-afternoon, hours before sunset --
unlike the 2026-08-26 attempt), reference Camera Node healthy and
reachable (`GET /node/v1/health`: `status: "available"`, self-test
passed, watchdog healthy, zero consecutive probe failures), GPU idle and
available (RTX 4060 Ti, zero MockingBird compute process at check time),
storage adequate, acceptance-recorder confirmed present and structurally
isolated from product truth. The sole remaining blocker, isolated more
precisely than either prior attempt could isolate it, is the identical
authentication precondition from the 2026-08-25 attempt above,
re-confirmed today against a freshly rebuilt and redeployed current
accepted HEAD (`80e1bb3`): `GET /api/streams` and `GET /api/visits` both
returned `401`, with no credentials attempted. Per the standing decision
above, no credentials were requested, no fresh disposable instance was
substituted for the real one, and production authentication was not
touched. The fresh deploy itself hit one cold-start false-negative (the
tool's own bounded 90-second verification window gave up before BioCLIP/
CUDA cold start finished) -- manually confirmed healthy and identity-exact
(`git_commit` exact match, schema 57, `ready: true`) via direct HTTP and a
follow-up `--status` check, matching an already-documented recurring
pattern, not a new defect; then stopped cleanly, leaving `80e1bb3`
retained and ledger-verified. Confirmed, again via the unauthenticated
health endpoint only, that the second real Source (the EMEET SmartCam
S600 USB webcam identified 2026-08-26) remains unwired -- adding it needs
the same authenticated path. Investigated one hypothesis for the
continuing `C:` free-space decline (43.07GB on 2026-08-20 -> 18.8GB today)
-- retained Windows dev-release accumulation -- and ruled it out (25
retained releases total only ~700-750MB; each release is ~29MB, not a
multi-GB per-release duplication); the actual cause remains open. Gate
A's evidence body is unchanged -- still exactly the two real
2026-08-19/2026-08-20 daylight cohorts, now for the third consecutive
attempt, two of the three blocked by the identical authentication
precondition. No release budgets proposed. See
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md).

**Non-Interactive Field Acceptance Authentication & Session Access v1
(2026-08-28) closed the authentication half of the recurring blocker
above, at classification A -- see §1/§3, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record.** A narrow, non-interactive, bearer-token "Field
Acceptance Operator" credential (schema v58) now lets bounded
field-acceptance tooling authenticate without an operator's personal
password, proven live against a real running instance of the exact
mechanism (the identical three previously-blocking endpoints -- `GET
/api/streams`, `GET /api/visits`, `POST .../observation/start` -- all
still correctly `401` unauthenticated, then all succeed with the new
credential, including a real Observation start/stop cycle). This closes
the *authentication* precondition specifically -- it does **not** by
itself close Lane R/Gate A, does **not** run the field session, and does
**not** authorize the next attempt; Gate A's evidence body is unchanged --
still exactly the two real 2026-08-19/2026-08-20 daylight cohorts. The
next daylight session still needs its own separate authorization plus
representative daylight/weather/health conditions (unrelated to
authentication, and not something this milestone could control), but no
longer needs to ask the operator for credentials or route around the
blocker -- see this milestone's own report for the exact one-time
provisioning command.

### S. Actual Final Release Hardening

**Status:** LAST.

Final Release Hardening begins once the intended release capability set
stabilizes -- a readiness judgment, not a version-number boundary (see
"Release readiness vs. continued capability work" in
[roadmap.md](roadmap.md)). Release-critical correctness always outranks
optional capability; capability development may continue up to that point
whenever it materially improves the product without endangering a
release-critical dependency. Once Final Release Hardening begins, no
major capability is added without explicit authorization based on
concrete necessity, and focus narrows to: defects; reliability;
performance; UX; compatibility; packaging; security; documentation;
installation; upgrade/recovery; field failures; External Pre-Release
Acceptance findings; release-artifact validation; dependency/license
closure; clean-install repetition; internal release-candidate builds (an
engineering mechanic, not a separate product stage). External Pre-Release
Acceptance -> Final Release Hardening -> the one public launch -- no
separate beta release precedes it.

## 7. One-release doctrine

MockingBird's public release target is a trustworthy single-site/home
observatory with:

- dependable visual observation;
- strong Visit/evidence quality;
- reviewed Observation truth;
- Today/history usefulness;
- native Camera Node golden path;
- ONVIF + RTSP/RTSPS;
- offline/recorded/camera-trap ingest;
- professional/research acquisition metadata;
- conservation reporting;
- effort/coverage;
- research-safe export;
- Camtrap DP;
- bounded contributor/research capability;
- Local Only privacy;
- installation/onboarding/recovery;
- diagnostics;
- storage;
- backup;
- versioning;
- security;
- OSS/release presentation;
- clean-install acceptance;
- integrated field acceptance.

Acoustics may ship as the now-accepted optional capability. Remote
LTE/solar/custom field hardware are not release blockers.

## 8. After-release queue

Explicitly keep:

- complete remote/intermittent-WAN/LTE field deployment;
- solar/battery;
- custom CM4/CM5 hardware;
- research-grade remote-field acceptance;
- broad multi-site;
- native mobile;
- advanced acoustic analytics;
- mature automatic mammal species identification.

Unless new evidence creates a dependency, do not promote these into
release scope.

## 9. Later / demand-driven queue

Examples:

- GenICam;
- GigE Vision;
- USB3 Vision;
- radiometric thermal;
- specialized industrial cameras;
- individual-animal recognition;
- population estimates;
- behavior prediction;
- causal ecological modeling;
- large cloud-first infrastructure.

## 10. Observability cross-cutting requirements

Keep visible as release requirements:

- structured error taxonomy;
- stable machine-readable codes;
- user-safe messages/actions;
- component attribution;
- recoverability;
- correlation/session identifiers where applicable;
- structured bounded logs;
- health transitions;
- reconnect/drop/failure counters;
- Visit/model/storage/coverage counters;
- support bundles;
- no uncontrolled raw/high-cardinality media telemetry.

Normal users get actionable diagnostics. Advanced support gets raw
details.

## 11. API / schema / version compatibility

Preserve:

- externally consumed schema/version discipline;
- additive compatibility where feasible;
- migration safety;
- Host ↔ Camera Node compatibility;
- upgrade/recovery semantics;
- explicit capability/version reporting.

Do not casually make breaking changes merely because all local tests can
be updated together.

## 12. Security / release questions

Keep visible:

- network exposure;
- HTTPS/TLS posture;
- secure remote-access decision;
- secret/credential storage;
- dependency/model supply chain;
- checksum/update verification;
- support-bundle disclosure;
- public SECURITY policy.

Do not claim encrypted camera/RTSP/ONVIF credentials at rest unless
current code proves it.

## 13. Development operating rules

**Bounded archaeology.** Start with governing docs and directly affected
code. Expand only when evidence reveals dependencies.

**Separate investigation and implementation.** When uncertainty is real:
(1) diagnose; (2) lock the contract; (3) implement.

**Validation tiers.** Tier 1: focused tests. Tier 2: affected subsystem
validation. Tier 3: full Core only when cross-cutting production risk
warrants it.

**Audit budget.** Default: one implementation/self-review; one acceptance
review. Additional audits require a concrete unresolved risk.

**Concurrent writers.** Never allow multiple Claude writer sessions in the
same working tree. Separate worktrees are required for parallel
implementation. Read-only agents are fine.

**Git.** Do not push without explicit user authorization. Protect the
seven preserved files (see below).

### Preserved untracked detector files

These seven known superseded/untracked detector files must remain
untouched -- not edited, deleted, renamed, staged, incorporated, or
cleaned up -- by any task working in this repository:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

They duplicate the accepted `multi_scale_strategy.py`/
`multi_scale_benchmark.py` work and were left uncommitted on purpose
rather than cleaned up; re-verify their presence untouched at the start of
each session that touches this repository.

## 14. Validation baselines

**Latest accepted Core checkpoint (Whole-Product UI / Accessibility /
Performance Closure v1):** 5166 passed / 2 failed / 3 skipped / 23
deselected (slow-marked) / 11 xfailed (26m50s), run standalone after an
earlier concurrent-with-e2e attempt produced real, directly observed
SQLite lock contention (not re-used as evidence -- see the milestone
report's "A note on validation methodology"). Both failures are the
identical, already-documented pre-existing `test_place_biodiversity_
summary_repository.py` pair (`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`),
independently re-confirmed as pre-existing across now at least nine
consecutive prior milestone checkpoints below -- not re-bisected again
this session given zero code this milestone touched has any relationship
to biodiversity-summary computation. No schema change, so no guard-rail
assertions needed touching. 7 new backend tests across two files (2 in
`tests/test_review_queue_product_mode.py`, 5 in `tests/test_product_
health.py`), each independently RED-confirmed against the pre-fix code
via `git stash` and GREEN after; `ruff check` confirmed zero new findings
via a direct clean-baseline bisection per touched file (83 pre-existing
findings total, unchanged before/after: `main.py` 26/26,
`product_repository.py` 57/57); `tsc --noEmit`/`vite build` clean. Full
e2e suite (136 specs, 8 new -- 2 new spec files plus 6 added to the
existing viewport matrix): 135 passed / 1 failed, the one failure the
same pre-existing, now precisely-diagnosed `reviewed-product-loop.spec.ts`
gap immediately below in this same list, independently reproduced
identically on the unmodified 128-spec baseline (127 passed / 1 failed,
byte-identical single assertion) -- confirming no regression from this
milestone's own product/test changes. See
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the complete record, including a real, live-verified P0 fix (Review
Queue default-tab misclassification of imported Visits), three P1 fixes
(two Fast Review keyboard focus-management defects, the acoustic health/
status gap), and two investigated-and-confirmed-not-regressions
(Stream Detail/Analytics list bounding, both intact).

**Prior accepted Core checkpoint (Multi-Camera Place Experience v2):**
5106 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (26m48s). Both failures are the identical, already-documented
pre-existing `test_place_biodiversity_summary_repository.py` pair
(`'seen_before' == 'new'` assertion mismatch) below, re-confirmed this
session. A first full Core run this session (5103 passed / 5 failed)
surfaced 3 genuinely new failures beyond that pre-existing pair, all
traced to the same root cause -- this milestone's own first attempt at
its archived-camera-history fix had made `place_activity_report`'s
*unfiltered default* archived-inclusive too, contradicting a real,
pre-existing, deliberately-authored test from the already-accepted
"Gate C -- Meaningful Change Detection / Baseline Comparison v1" milestone
(`test_place_change_summary_repository.py::test_archived_stream_
confirmations_are_excluded` and `test_historical_baseline_repository.py`'s
own identically-named test) that this session's own narrower Tier 1
re-runs had not included in scope. Corrected precisely (the unfiltered
default stays archived-exclusive, matching Bird Log/Wildlife Insights/
Biodiversity's identical default; an explicit `source_ids` selection still
reaches archived history) and reconfirmed clean by this second, full run
-- see [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)'s
"Validation" for the complete record. No schema-version guard-rail
regression (schema unchanged, so no guard-rail assertions needed
touching). 87+ new/modified tests across the directly touched files plus
two new dedicated test files (`test_multi_camera_concurrent_runtime.py`,
`test_multi_camera_place_experience_scenario.py`), all passing; `ruff
check` confirmed zero new findings via a direct clean-baseline bisection
(`git stash push -u`/pop, content-normalized comparison) both before and
after the correction above; `tsc --noEmit`/`vite build` clean; targeted
e2e (`today-report.spec.ts` 19/19, `place-activity-report.spec.ts` 3/3,
`bird-log-historical-status.spec.ts` 9/9) passing; full existing e2e suite
(128 tests) re-run at 127 passed / 1 failed, that one failure the
identical, already-independently-documented pre-existing
`reviewed-product-loop.spec.ts` gap recorded across at least three prior
milestones' own acceptance records, including `mobile-viewport-audit.
spec.ts`'s own full clean re-run (zero horizontal-overflow findings)
across exactly the surfaces this milestone modified.

**Prior accepted Core checkpoint (Ecological Interoperability & Submission
Workflows v1):** 5095 passed / 2 failed / 3 skipped / 23 deselected
(slow-marked) / 11 xfailed (27m29s). Both failures are the identical
`test_place_biodiversity_summary_repository.py` pair (`'seen_before' ==
'new'` assertion mismatch) independently re-confirmed as pre-existing
across at least eight consecutive prior milestone checkpoints below --
re-run in isolation this session and reproduced byte-identically (same two
test names, same exact assertion values), confirming the established
precedent rather than a full `git stash` bisection for code sharing zero
files or logic with this milestone. No schema-version guard-rail
regression: all 14 hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 56`
assertions across 7 files were found and bumped to `57` (the identical
class of drift every prior schema bump has tripped -- see the milestone
report). 98 new tests across eight new test files plus targeted additions
to three existing ones, all passing; `ruff check` confirmed zero new
findings via a direct line-level diff against a clean baseline (stronger
than a bisection -- every pre-existing finding reproduces byte-identically
at its new, shifted line number; an over-broad `ruff --fix` run was caught
removing ~19 unrelated pre-existing unused imports and precisely reverted
first); `tsc --noEmit`/`vite build` clean; new `ecological-destinations.
spec.ts` 5/5 passing; full existing e2e suite (127 tests) re-run with only
the one already-known pre-existing failure (`reviewed-product-loop.
spec.ts`, unrelated to this milestone, recorded across at least three
prior milestones).

**Prior accepted Core checkpoint (Calm Attention & Notifications v1):** 4991
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m02s). All 3 failures independently re-bisected this session: the two
`test_place_biodiversity_summary_repository.py` failures (identical
`'seen_before' == 'new'` mismatch, see immediately below) reproduce
byte-identically against a fresh `git stash push -u` clean-baseline run with
zero of this milestone's changes applied. The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success` -- the identical test name
already recorded as a load-induced flake in the Mobile & Remote Experience v1
checkpoint below -- passed cleanly both in isolation and as part of its own
file (7/7) when re-run directly on this milestone's own code immediately
after the full Core run, confirming the flake again rather than assuming the
precedent still held. No schema-version guard-rail regression: all 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 55` assertions across 7 files
were found and bumped to `56` (the identical class of drift every prior
schema bump has tripped -- see the milestone report). 22 new tests across two
new files (`tests/test_calm_attention.py`, `tests/test_attention_sync_
service.py`) plus one new schema-migration regression test in `tests/
test_persistence.py`, all passing; `ruff check` clean (0 new findings,
bisected file-by-file against a clean baseline); `tsc --noEmit`/`vite build`
clean; 11/11 new `notification-preferences.spec.ts` e2e tests passing
(4 of which install a fake `Notification` global and a fake clock to prove
the live-notification decision logic end to end, not only that Settings
persists a toggle); full existing e2e suite (118 tests) re-run with only the
one already-known pre-existing failure (`reviewed-product-loop.spec.ts`,
independently reproduced and unrelated to this milestone).

**Prior accepted Core checkpoint (Mobile & Remote Experience v1):** 4976
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(24m02s -- measurably longer than the historical ~9min baseline; this
sandbox was independently confirmed under real, unrelated concurrent CPU
load throughout this session via `uptime`/`ps`, not a Core-gate
regression). Two failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean pre-milestone baseline (byte-identical
failure, same `'seen_before' == 'new'` assertion mismatch, with zero of
this milestone's changes applied). The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success`, has zero code relationship
to this milestone (Camera Node transport/protocol diagnostics), passed
7/7 cleanly on immediate isolated re-run, and matches an already-
documented precedent for exactly this file under exactly this condition
(the Environmental Context v2 checkpoint below recorded a different test
in this same file failing only under confirmed heavy concurrent load,
clean in isolation) -- the identical evidentiary shape, not bisected via
`git stash` a second time given that precedent and the isolation proof
already in hand. No schema change, so no guard-rail
assertions needed touching. 138 tests pass across the six directly
touched/added test files (20 genuinely new -- 2 for the Phase 0 RED/GREEN
proof, 5 for the new timing-guard parameters, 9 for the new
`/api/product/connection` endpoint, 4 for CORS -- plus 2 pre-existing
tests corrected to match the fixed behavior, their own actual claims
unaffected); `ruff check` clean
(0 new findings; the 57 pre-existing findings elsewhere in
`product_repository.py` confirmed unrelated via `git stash` bisection);
`tsc --noEmit`/`vite build` clean. Frontend e2e: new
`mobile-viewport-audit.spec.ts` 19/19 passing (10 core surfaces at
phone-viewport emulation, real seeded/imported data, zero horizontal-
overflow findings, plus a 360px/390px/768px matrix on the two densest
surfaces per Phase 25); full existing suite (112 tests, no filter) re-run
in full -- 111 passed, 1 failed, and that one failure
(`reviewed-product-loop.spec.ts`) is an independently-
reproduced, genuinely pre-existing defect (unmodified spec, run alone,
fails identically -- a `ReviewQueuePage` `product_category`/"animals"-tab
data gap, unrelated to this milestone's own changes) -- zero regressions
from the navigation/CSS changes across every other spec, including two
pre-existing mobile-specific tests.

**Prior accepted Core checkpoint (Place Story & Seasonal Timeline v1):**
4958 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (22m29s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean `950d5c2` baseline (byte-identical failure,
same `'seen_before' == 'new'` assertion mismatch, with zero of this
milestone's changes applied; `git worktree` gives invalid baselines in
this actively-shared worktree, so `git stash push -u`/`pop` was used
instead, then dropped after a diff-against-stash confirmed zero content
loss). No schema change, so no guard-rail assertions needed touching. 32
new tests (24 pure `tests/test_place_story.py` + 8 repository/HTTP
`tests/test_place_story_repository.py`); `tsc --noEmit`/`vite build`
clean; 44/44 targeted e2e passed (6 new `place-story.spec.ts` + 38
directly-adjacent re-run clean).

**Prior accepted Core checkpoint (Place Features & Habitat Change v2):**
4926 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (23m27s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash` bisection
against the clean `b0bd312` baseline (byte-identical failures with zero
of this milestone's changes applied). 50 new tests in
`tests/test_place_feature.py`
(pure window-selection/maturity logic, repository CRUD, dual-write
reconciliation, real seeded before/after scenarios, real HTTP surface),
plus a new `test_persistence.py` schema-55 migration test and 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 54` guard-rail assertions
across 8 unrelated files bumped to `55` (the same class of drift the
prior two schema bumps also tripped -- see the milestone report). 30
directly-adjacent existing tests re-run clean
(`test_habitat_phenology.py`/`test_habitat_association.py`/
`test_place_activity_report.py`/
`test_place_activity_report_repository.py`/`test_source_activity.py`
actually total 174; the 30 figure is the re-run e2e count, see below).
Frontend `tsc --noEmit` and `vite build` clean; a new 7-test Playwright
spec (`e2e/place-features.spec.ts`) plus 30 directly-adjacent existing
e2e tests (`today-report`/`place-activity-report`/`biodiversity-summary`)
re-run clean.

**Prior accepted Core checkpoint (Environmental Context v2):** 4874
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(26m13s). Two of the three failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below.
The third (`test_transport_worker.py::test_retryable_failure_returns_
item_to_failed_retryable_and_eventually_succeeds`) is unrelated to this
milestone (a different subsystem entirely, no shared code), reproduced
only under confirmed heavy concurrent system load, and passed cleanly
both in isolation and as part of its own file when re-run -- a transient,
load-induced flake, not a regression; see the milestone report's "Tests /
validation" for the full isolation evidence. 85 new tests across three new
pure modules plus repository/schema extensions (zero bugs found in the
three new pure modules themselves; three real bugs found and fixed in the
new repository-layer integration code during this milestone's own
test-writing); 42/42 targeted Playwright e2e tests passed. A first full
run also surfaced 10 additional failures, root-caused immediately to 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 53` guard-rail assertions
across 7 files unrelated to this milestone that its own correct v53->v54
schema bump was always going to trip -- fixed by updating all 14 to `54`
(not a defect in this milestone's own migration; see the report).

**Prior accepted Core checkpoint (Place / Yard Intelligence v2):** 4791
passed / 2 failed / 2 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m23s). The 2 failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
re-confirmed via a fresh `git stash` bisection against the clean `731ee30`
baseline this same session. 173 new pure-module tests added (all passing,
zero bugs found in the modules under test); 46/46 targeted Playwright e2e
tests passed after fixing one real regression found live (a pre-existing
mock fixture predating a new additive response field -- see the milestone
report).

**Prior accepted Core checkpoint (Camera / Source Experience &
First-Hour Setup Closure v1):** 4648 passed / 2 failed / 2 skipped / 11
xfailed. The 2 failures
(`test_place_biodiversity_summary_repository.py`, an unrelated
historical-status timing case) reproduced identically against the clean
`74c192a` baseline via `git stash` bisection -- confirmed pre-existing
flakiness, not a regression.

**Prior accepted Core checkpoint (Release Engineering Foundation v1):**
4633 passed / 0 failed / 0 errors. (A first full run showed 2 teardown
errors in an unrelated file; root-caused via clean-baseline bisection to
a pytest fixture-teardown-ordering interaction this milestone's own
`tests/conftest.py` change triggered, fixed at the source -- see the
milestone report's "Validation commands/results.")

**Prior accepted Core checkpoint (Acoustic milestone):** 4608 passed / 0
failed.

**Prior accepted Full checkpoint:** 4629 passed / 2 failed. Both failures
were in unrelated Camera Node real-subprocess tests and reproduced
identically on the clean baseline.

These counts are historical accepted checkpoints, not immutable future
expected totals.

## 15. Update protocol

At each accepted milestone closure, update only the delta:

- accepted HEAD;
- schema if changed;
- latest accepted milestone;
- affected lane status;
- newly discovered blocker;
- current validation checkpoint if applicable;
- field acceptance state;
- current authorized milestone only when explicitly authorized after
  global reconciliation.

Never copy a Claude "next natural milestone" suggestion directly into the
authorization field.

## 16. Transition checkpoint

- **Accepted HEAD:** `763fe22` (Multi-Camera Place Experience v2
  implementation commit)
- **Schema:** v57 -> v57, unchanged. Every fix is a query-scope correction
  or an additive field on an already-derived, never-persisted response
  object -- no new/changed table.
- **Latest accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views
- **Multi-Camera Place Experience v2 classification:** B -- an integrated
  multi-camera product pass on the already-accepted Camera/Source +
  Multi-Camera Maturity v1 foundation (cross-camera association engine,
  Area vocabulary, provider compatibility, health WAN-vs-camera
  disambiguation -- that milestone's own report had gone missing from this
  file's own bookkeeping despite being a real, merged, accepted ancestor
  of this HEAD; corrected here, see Lane F, above). See
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
  for the full record: a real correctness defect (an archived camera's
  history was unreachable from every discovery surface, contradicting this
  codebase's own documented archive-only-preserves-history doctrine) found
  and fixed with principled nuance across two rounds of correction --
  Tier 1 test evidence first corrected an initial blanket overcorrection,
  then this milestone's own full Tier 3 Core run caught a second, more
  subtle one (`place_activity_report`'s unfiltered default had also become
  archived-inclusive, contradicting a real pre-existing test from the
  already-accepted "Gate C -- Meaningful Change Detection / Baseline
  Comparison v1" milestone -- see §14); the fix that shipped preserves
  every already-tested current-active-observatory default exactly (Bird
  Log overview, Wildlife Insights, Biodiversity, Place Activity
  Report/Today) while making that real history reachable by explicit
  camera/`source_ids` selection, with Place Story and research/
  conservation export unconditionally inclusive where no existing test
  disagreed; Today now surfaces its own already-computed per-camera
  activity/evidence-source facts for the first time (a compact "By camera"
  section and per-highlight camera attribution, both gated to 2+ cameras
  so Today stays a report, never a camera-monitoring dashboard); Bird
  Log's camera filter now reaches its overview list, not only the
  per-species drilldown; Zone Insights' Place-wide aggregate coverage was
  a naive per-camera-hours sum, now a real elapsed-time interval union
  matching Today's own already-correct semantics (proven with real
  before/after numbers: 2 hours + 2 hours overlapping by 1 hour now
  correctly reports 3, not 4); Dashboard distinguishes "some cameras need
  attention" from "every armed camera needs attention," computed from
  already-returned facts; `CameraConfigurationPage.tsx`'s own locally-
  drifted 3-tone health-tone/generic-label presentation now reuses the
  canonical `cameraHealthTone`/`cameraHealthLabel` every other health
  surface already converged on; a real, measured (not merely claimed)
  concurrency proof -- genuine concurrent `threading.Thread`s, one per
  Stream, each with its own `ProductRepository`/connection against one
  shared SQLite file, matching production's actual architecture -- found
  zero cross-Stream contamination and no starvation across 2-camera and
  4-camera-asymmetric topologies, and separately found, root-caused, and
  honestly disclosed (an attempted bounded transient-retry fix did not
  reliably close the gap and was deliberately reverted rather than shipped
  unproven on Stage 7's own live admission/persistence boundary) a real,
  reproducible occasional lost-candidate-Visit reliability gap under real
  concurrent write contention; a comprehensive, real, executable 3-camera
  product-shaped scenario (Front Feeder/Back Yard/Bird Bath, a real
  cross-camera "associated" pair, an archival, a rename, a reviewed
  correction) proves the whole chain -- identity, coverage, overlap dedup,
  health, correction propagation -- coheres end to end with zero mocking
  of product logic. Full Core 5106 passed / 2 failed (both the identical,
  independently-reconfirmed pre-existing `test_place_biodiversity_summary_
  repository.py` pair -- see §14) / 3 skipped / 23 deselected / 11 xfailed
  (26m48s); `ruff check`/`tsc --noEmit`/`vite build` clean; full existing
  e2e suite (128 tests) at 127 passed / 1 failed (the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap). Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": the occasional
  lost-candidate-Visit concurrent-write reliability gap (the single most
  concrete, actionable follow-on item); notification-level (Calm
  Attention) cross-camera grouping beyond the Dashboard status-view fix;
  Place Story wildlife-event source attribution; camera-filter UI
  consolidation (6+ independently-implemented controls); multi-camera
  Place Feature linking; real GPU/CUDA-driver-level concurrent-inference
  measurement (needs real hardware this sandbox lacks); a multi-hour
  concurrent soak; the pre-existing, disclosed 2-Stream cap on the
  separate legacy motion pipeline (RTSP/USB/local providers, not the
  modern Observation Engine's own Camera Node path).
- **Prior accepted HEAD:** `3c60d79` (Ecological
  Interoperability & Submission Workflows v1 implementation commit --
  filled in at reconciliation)
- **Schema:** v56 -> v57. Two new additive tables:
  `ecological_taxonomy_mappings` (a bounded, reusable "MockingBird label ->
  destination taxon" resolution cache, one row per `(destination, label)`)
  and `ecological_submission_records` (a durable per-Visit
  external-submission-preparation record, one mutable row per `(visit_id,
  destination)` until a self-reported external result freezes it). No
  existing table's shape changed.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology
- **Ecological Interoperability & Submission Workflows v1 classification:**
  B -- a real, working, submission-ready iNaturalist workflow composed
  entirely over the already-accepted research-eligibility gate and
  `ResearchObservation` shape (`mockingbird.ecological.destination_
  eligibility`/`adapters` never re-derive either), never a second truth
  system. See
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)
  for the full record: eligibility preview with per-record, never-bare
  status and reasons; a credential-free iNaturalist taxonomy mapping cache
  (`GET /v1/taxa`, confirmed public/no-auth against the official swagger
  spec) whose exact-name-match logic was directly corrected against a real
  live API call during this milestone's own testing (a plain "Northern
  Cardinal" query returns several candidates, not one -- requiring an exact
  match among them, not a bare single-result rule); explicit, never-
  inferred-from-the-weather-coordinate location/media consent (directly
  tested); a batch prepare/export pipeline producing the exact positional
  8-column CSV iNaturalist's own open-source bulk importer expects
  (confirmed directly against `lib/bulk_observation_file.rb`); deterministic
  content fingerprinting closing idempotency and correction-after-
  preparation staleness (a real precedence bug -- a stale-and-currently-
  ineligible record reported the less useful reason first -- found and
  fixed by this milestone's own test-writing); a self-reported external-
  result close-the-loop step, never a live automated submit; a bounded,
  additive Darwin Core Occurrence-core exporter
  (`basisOfRecord="MachineObservation"`, GBIF's own recommended camera-trap
  value, confirmed via its official camera-trap guide); eBird correctly,
  evidence-backed **not offered** (its own current "Rules and Best
  Practices," checked 2026-08-25, explicitly excludes feeder/trail-camera
  data -- a real policy conflict, not a time constraint, and the product UI
  now shows this reason persistently rather than behind a disabled
  button's hover-only tooltip, a real gap this milestone's own e2e testing
  found and fixed); direct GBIF publication correctly deferred as
  institutional (organizational Participant-Node endorsement required, not
  a backyard-user workflow); two real security findings made and fixed
  (CSV injection in the one shared `_write_csv` helper behind every export
  in this codebase, retroactively hardening the pre-existing generic
  research/Camtrap DP export paths too -- and a real regression in an
  early version of that exact fix, which corrupted legitimate negative
  coordinates, caught by this milestone's own test before shipping; a
  `javascript:`-scheme external-URL rejection on the self-reported result
  field); a real, executable 12-Visit product-shaped scenario test proving
  the whole workflow end to end with zero user interaction and zero
  provisional/superseded truth ever reaching a prepared record. 107+ new
  tests across nine new test files plus targeted additions to three
  existing ones, all passing; `ruff check` confirmed zero new findings via
  a direct line-level diff against a clean baseline (not merely a
  bisection) -- an over-broad `ruff --fix` run was caught removing ~19
  unrelated pre-existing unused imports and precisely reverted before that
  confirmation; `tsc --noEmit`/`vite build` clean; new
  `ecological-destinations.spec.ts` 4/4 passing; full existing e2e suite
  re-run at 126 passed / 1 failed, that one failure the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap recorded across at least three prior milestones' own
  acceptance records. Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": live OAuth iNaturalist
  submission; media-byte inclusion; a single-Visit deep-link pre-selection
  on the Ecological Destinations page; broader batch-filter UI depth.
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Prior accepted HEAD:** `c22bf94` (Calm Attention &
  Notifications v1 implementation commit -- filled in at reconciliation)
- **Schema:** v55 -> v56. One new additive table, `user_notification_
  preferences` (per-user delivery preferences). No existing table's shape
  changed; `ProductAlertModel.category`/`.action_type` are plain `String`
  columns with no database-level enum/check constraint, so the new
  `"insight"` category and the two new `open_place_story`/`open_place_report`
  action types needed no migration of their own.
- **Latest accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Calm Attention & Notifications v1 classification:** B -- a real canonical
  attention-selection layer (`ProductRepository.sync_attention_signals`)
  composed entirely over already-accepted facts (Place Story's already-
  deduplicated event stream, the existing daily/weekly digest, the existing
  review/monitoring/storage/journal `ProductAlert` system), never a second
  computation path. See
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)
  for the full record: a small user-centered taxonomy (Discovery/Insight/
  Needs Help/Observatory Health) and explicit urgency (immediate/digest/
  in-app-only) computed as a pure presentation-layer mapping, never stored
  and never a raw internal severity/error vocabulary leaking into copy;
  genuine semantic-deduplication work that found and fixed two real
  double-notification anti-patterns by *writing tests*, not merely by
  design review (`first_seen` excluded from the new sync because `_sync_
  journal_milestone_alert` already owns that fact; the 1st-species
  diversity milestone excluded too, since it is always dated at that same
  taxon's own first-ever confirmation); reused, not reinvented, health/
  storage debounce (`_sync_camera_health_incident`'s own already-debounced
  named-duration/consecutive-failure thresholds, untouched); a daily/weekly
  digest notification reusing `daily_digest.compute_daily_digest` unmodified
  via the exact same `place_activity_report` entry point Today/the Place
  Report already call, suppressed when there is genuinely nothing meaningful
  and never suppressed for an ordinary day of confirmed regular activity;
  Needs Help reclassified to `in_app_only` urgency and grouped into the
  digest's own "N observations could use your help" sentence instead of a
  second per-item interruption; new per-user notification preferences (this
  product's first per-user settings row -- four category toggles + quiet
  hours) with quiet hours deliberately evaluated in the viewer's own
  browser-local time rather than inventing a server/Place timezone that does
  not exist; a fixed role rule hiding Needs Help attention from Viewers
  server-side, not merely in the UI; foreground-only browser-notification
  delivery (Phase 22 Decision B, Web Push explicitly evaluated against real
  architecture facts and deferred -- no VAPID/subscription persistence, no
  outbound push-service call, no cloud infrastructure added, matching this
  lane's own standing "do not add cloud push infrastructure" instruction);
  a real, executable Monday-through-Sunday product-shaped quiet-week test
  proving the whole week stays calm (<=14 total attention items, zero ever
  reaching `immediate` urgency); a real controlled-checkbox revert bug found
  and fixed in the new Notifications settings UI by a failing Playwright
  assertion; 4 new e2e tests that install a fake `Notification` global and a
  fake clock to prove the live-notification decision logic end to end, not
  only that Settings persists a toggle. 22 new backend tests (`tests/
  test_calm_attention.py` + `tests/test_attention_sync_service.py`) plus one
  new schema-migration regression test, all passing; Core 4991 passed / 3
  failed (all 3 independently re-bisected this session -- 2 byte-identical
  pre-existing via fresh `git stash push -u`, 1 a load-induced flake
  reconfirmed clean in isolation and matching an identical documented
  precedent -- see §14) / 3 skipped / 11 xfailed; `ruff check`/`tsc --noEmit`/
  `vite build` clean; 11/11 new e2e tests passed; full existing e2e suite
  (118 tests) re-run with only the one already-known pre-existing failure
  (`reviewed-product-loop.spec.ts`, unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's "Remaining
  major PRODUCT opportunities": Web Push for a genuinely closed-browser
  interruption (deliberately deferred, not merely unattempted); detector/
  model-unavailable Observatory Health attention; per-user (not global)
  read/dismiss state; precise per-taxon/Feature Place Story deep links
  (today scoped to a category group); a live attention-sync diagnostics
  surface beyond the current structured log line.
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk
- **Mobile & Remote Experience v1 classification:** B -- strong mobile
  experience and a clear secure remote posture with bounded external-
  network/PWA gaps. See
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)
  for the full record: a verified responsive-navigation fix (top bar +
  off-canvas drawer + 4-item bottom nav, replacing a sidebar that
  previously stacked in full above every page below 980px, proven across
  10 real automated phone-width screenshots with zero horizontal-overflow
  findings); a bounded, from-scratch installable PWA shell (manifest,
  icons generated from the product's own existing brand mark, a service
  worker that caches only Vite's own immutable content-hashed assets and
  never navigation/API/data -- no offline data claim anywhere); LAN access
  made genuinely discoverable (`GET /api/product/connection`, a Settings
  "Connection & Remote Access" card, a corrected `--allow-network` help
  string that had gone stale since real authentication shipped); a
  private-overlay-network (Tailscale-compatible) remote-access posture
  investigated against real architecture and documented as the supported
  away-from-home path, with direct public-internet exposure and a cloud
  relay explicitly, plainly documented as unsupported/not-built; 4 new
  CORS regression tests closing a real, previously-zero coverage gap. Also
  closed, as its own bounded Phase 0 ahead of the broader mobile work: a
  genuine pre-existing defect in `place_change_summary._presence_status`
  that made the accepted `regularity_narrative` "returned after absence"
  wording structurally unreachable through Today/Bird Log's direct
  composition -- fixed at the source (not merely worked around a second
  time), including a second, deeper defect the naive fix alone would have
  introduced (a young-taxon false positive), closed by sharing one timing
  guard between Today/Bird Log and Place Story instead of duplicating it.
  138 tests pass across the six directly touched/added test files (20
  genuinely new, 2 pre-existing corrected -- see §14), Core 4976 passed /
  3 failed (2 pre-existing and re-confirmed via fresh `git stash push -u`
  bisection, 1 a load-induced flake in an unrelated file matching an
  already-documented precedent, isolation-confirmed clean -- see §14) /
  3 skipped / 11 xfailed; frontend `tsc`/`vite build` clean;
  19/19 new mobile-viewport e2e tests passed (10 core surfaces +
  360px/390px/768px matrix); full existing e2e suite
  (112 tests) re-run with only the one already-
  known pre-existing failure (`reviewed-product-loop.spec.ts`, a
  `ReviewQueuePage` `product_category` gap, independently reproduced and
  unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's
  "Remaining major PRODUCT opportunities": Visit/Stream/Settings page
  density (long but not broken), the `ReviewQueuePage` `product_category`
  gap itself (found, documented, not fixed), no login rate-limiting
  (pre-existing, real, more relevant now that reachability increased), and
  no live external-overlay-network acceptance was possible from this
  sandbox (validated structurally only).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place
- **Place Story & Seasonal Timeline v1 classification:** B -- major
  useful capability, bounded history/story gaps. New `GET /api/place/
  story` composes a small, deliberately bounded event taxonomy --
  wildlife (`first_seen`/`return`/`regularity_change`/
  `noteworthy_activity`/`diversity_milestone`), place
  (`feature_change`/`phenology`), context (`comparison_insight`) --
  entirely from already-accepted primitives (`historical_baseline`,
  `place_change_summary`, `regularity_narrative`,
  `PlaceFeatureChangeEventModel`, `PlacePhenologyObservationModel`,
  `feature_change_comparison`); regularity/activity-change detection
  re-applies those unmodified functions at every usable-date checkpoint
  so a transition is announced once, not once per recomputation. Found
  and worked around without modifying the frozen module: `place_change_
  summary._presence_status` has made the existing `"returned_after_
  absence"` wording unreachable in production on Today/Bird Log since
  Place / Yard Intelligence v2 shipped -- `place_story._effective_
  regularity_state` applies a narrow local supplemental check using that
  module's own already-correct fields; a dedicated fix to `place_change_
  summary.py` itself is recorded as future work, not applied here. New
  `PlaceStoryPage.tsx`: a calm, newest-first, month-grouped timeline with
  Period/Category filters and evidence drill-down. 24 pure-module tests
  (including regression tests for the gap above and a second, separately
  found and fixed checkpoint-seeding bug), 8 repository/HTTP integration
  tests against real seeded data (including three independent
  correction-safety proofs), all passing; Core 4958 passed / 2 failed
  (both pre-existing, re-confirmed via fresh `git stash push -u`
  bisection -- see §14) / 3 skipped / 11 xfailed; 44/44 targeted e2e
  passed (6 new + 38 directly-adjacent re-run). See
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
  for the full record, including recorded future opportunities (period
  summaries -- deferred on a measured performance cost, the single
  largest deferred piece --, environmental-context/weather caveats on a
  Story insight, a dedicated taxon/Feature story page, representative
  imagery on Story cards, and the `place_change_summary.py` fix itself)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding
- **Place Features & Habitat Change v2 classification:** B -- major
  useful capability, bounded feature/data-model maturity gaps. A durable
  `PlaceFeatureModel` (feeder/water/nest_box/vegetation_patch/structure/
  habitat_area/other, optionally camera/Zone-linked) and a Reviewed
  `PlaceFeatureChangeEventModel` timeline (added/removed/moved/modified/
  replenished/food_changed/vegetation_changed/other), a deliberate
  dual-write (not event-sourced) relationship between the two -- the
  first discrete before/after change-event model in this codebase,
  closing a gap `habitat_association.py`'s own docstring and the Place /
  Yard Intelligence v2 report both explicitly recorded as their own
  honest ceiling. A new before/after comparison module composes onto
  `conditional_association.compute_conditional_association` completely
  unmodified (proven byte-identical output to calling that primitive
  directly), adding only a bounded 7/14/30-day symmetric window
  escalation and a four-state maturity vocabulary (too_soon/insufficient_
  coverage/early_signal/comparable); a per-Feature yield module mirrors
  `source_activity.py` one level finer. Both new tables are PATCH-
  corrected in place because every derived comparison is computed fresh
  at read time, never cached -- proven, not just asserted, by a direct
  test that a correction changes the very next read. New Dashboard card
  and Place Report section, both mirroring existing Habitat & Phenology
  UI patterns exactly. 50 new backend tests, 7 new Playwright e2e tests,
  all passing; Core 4926 passed / 2 failed (both pre-existing, re-
  confirmed via fresh `git stash` bisection -- see §14) / 3 skipped / 11
  xfailed; 37/37 targeted e2e passed (7 new + 30 directly-adjacent
  re-run). See
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)
  for the full record, including recorded future opportunities
  (environmental-context/weather caveats on a before/after result --
  the single largest deliberately-deferred piece --, multi-camera
  Feature linking, representative evidence in Feature detail, a ranked
  feature-comparison view, deeper Today/`daily_digest` integration)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Environmental Context v2 -- Weather,
  Climate & Place Conditions
- **Environmental Context v2 classification:** B -- major useful
  capability, bounded provider/statistical/UI limitations. First general
  weather provider (Open-Meteo -- free, non-commercial, no API key,
  global coverage, CC BY 4.0 attributed) composed onto the existing
  `conditional_association` primitive alongside `habitat_associations`;
  two independent privacy opt-ins (coordinates for solar, a separate
  `weather_enabled` for any outbound network call); a bounded 92-day
  historical window (exceeds this product's entire real history today);
  six honest degraded-mode states, zero crashes, zero blocking of core
  product function. 85 new tests; Core 4874 passed / 3 failed (2
  pre-existing, 1 confirmed transient load-induced flake in an unrelated
  subsystem) / 3 skipped / 11 xfailed; 42/42 targeted e2e passed. See
  [environmental-context-v2-report.md](environmental-context-v2-report.md)
  for the full record, including the Open-Meteo terms/license research
  and recorded future opportunities (deeper historical backfill via the
  archive/ERA5 endpoint, wind/cloud-cover statistical associations, a
  dedicated diagnostics/Explore-page surface) deliberately not built by
  adjacency.
- **Camera / Source Experience release classification:** C -- usable,
  bounded further closure remains (ongoing-monitoring failure-code
  collapse; no real reachable camera/RTSP/ONVIF/local-USB/Camera-Node
  hardware exercised this session). See
  [camera-source-experience-v1-report.md](camera-source-experience-v1-report.md).
- **Native-Windows acceptance (this milestone):** none -- Ecological
  Interoperability & Submission Workflows v1 was validated via targeted
  and full Core Python tests, new Playwright e2e, `tsc`/`vite build`, and
  `ruff` on the Linux/WSL dev stack, plus a real live call to iNaturalist's
  own public taxonomy API during development (not a Windows-specific
  proof, but real external-network evidence). Every new module is plain
  Python/TypeScript with no OS-specific branch (the one external HTTP call
  uses the same stdlib `urllib.request` convention the existing weather
  provider already validated cross-platform), so it is not expected to
  behave differently on native Windows, but that remains an expectation,
  not fresh Windows evidence. The most recent real native-Windows
  acceptance remains further below (Place / Yard Intelligence v2),
  unaffected by this milestone's additive-only schema change.
- **Native-Windows acceptance (Calm Attention & Notifications v1):** none --
  validated via targeted Python tests (including a real 28-minute Core
  run), new Playwright e2e (including 4 real-browser `Notification`/
  fake-clock tests), `tsc`/`vite build`, and `ruff` on the Linux/WSL dev
  stack; every new module is plain Python/TypeScript with no OS-specific
  branch, so it is not expected to behave differently on native Windows,
  but that remains an expectation, not fresh Windows evidence.
- **Native-Windows acceptance (Place Story & Seasonal Timeline v1):** none
  -- Place Story &
  Seasonal Timeline v1 was validated via targeted Playwright e2e against
  the real running app (Linux/WSL dev stack) and full Core; it is a pure
  read-model over already-cross-platform data with no platform-specific
  code and is not expected to behave differently on native Windows, but
  that is an expectation, not fresh Windows evidence. The most recent
  real native-Windows acceptance remains the one below (Place / Yard
  Intelligence v2), unaffected by this milestone's schema-unchanged,
  additive-only change.
- **Native-Windows acceptance (Place Features & Habitat Change v2):**
  none -- validated the same way (targeted Playwright e2e + full Core on
  Linux/WSL), for the identical reason (no platform-specific code).
- **Native-Windows acceptance (Place / Yard Intelligence v2):** real
  deployment of the exact commit (confirmed via `/api/product/instance`),
  plus a second, genuinely fresh isolated instance exercised end-to-end
  (real administrator creation, real sign-in, real ffmpeg 8.1.2 subprocess
  against an intentionally unreachable RTSP host, honest
  `preview_available`, correct credential masking, no leak) -- not a
  full physical-camera acceptance; see that report's Section 6/9.
- **Prior Native-Windows acceptance (Release Engineering Foundation v1):**
  Decision A -- real deployment, a real packaging defect found and fixed,
  a real organic 18-schema-version migration with verified automatic
  backup, confirmed via real HTTP. See
  [release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md).
- **Weather provider decision:** Open-Meteo (`api.open-meteo.com`), free/
  non-commercial/no-API-key, CC BY 4.0 attributed, bounded to its own
  confirmed 92-day recent-history window. Off by default
  (`weather_enabled=False`); a second, independent opt-in from the
  existing coarse-coordinate setting. See the Environmental Context v2
  report's "Provider decision" for the full terms/license research and
  the preserved, unresolved commercial-adjacent-use caveat (mirroring the
  standing BirdNET caveat in §2, above).
- **Acoustic release posture:** Release-ready optional
- **Production detector:** MDv5a ONNX @ 0.1
- **Production visual species system:** BioCLIP-2 + Eligibility/Abstention
- **Current authorized implementation milestone:** NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED
- **State:** Milestone-closure checkpoint
- **Final release hardening:** not authorized
- **Remote LTE/solar:** not a release blocker
- **Ecological Interoperability:** delivered this milestone (classification
  B) -- see Lane J, §6; live OAuth iNaturalist submission, any eBird
  workflow, direct GBIF publication, media-byte inclusion, and a
  single-Visit deep-link pre-selection are not automatically authorized
  (see §3)
- **Ecological destination decisions:** eBird -- not offered (own current
  policy excludes feeder/trail-camera data); iNaturalist -- submission-ready
  CSV workflow delivered, live OAuth submit deliberately not built; Darwin
  Core -- built, additive to Camtrap DP; GBIF -- deferred, institutional
- **Darwin Core export:** delivered this milestone, additive to the
  already-accepted Camtrap DP export (not a replacement) -- see Lane
  "Research / Conservation," §5
- **Calm Notifications:** delivered this milestone (classification B) -- see
  Lane D, §6; a further Web Push/per-user-read-state/precise-deep-link
  campaign is not automatically authorized (see §3)
- **Calm attention capability:** B -- one canonical attention-selection
  layer over already-accepted facts, genuine semantic-dedup fixes found by
  tests, reused health/storage debounce, per-user preferences and quiet
  hours, foreground-only browser notifications with Web Push deliberately
  deferred, a real product-shaped quiet-week proof
- **Notification delivery decision:** foreground-only page-level
  `Notification` calls while the tab is open or backgrounded (Phase 22
  Decision B); no Web Push, no VAPID/subscription persistence, no outbound
  push-service call, no MockingBird-operated cloud notification backend --
  see the milestone report's "PWA / browser notification decision" for the
  full evaluation of all three options against real codebase facts
- **Mobile/PWA:** delivered this milestone (classification B) -- see Lane
  E, §6; a further Mobile/PWA/remote-access campaign is not automatically
  authorized (see §3)
- **Mobile experience capability:** B -- responsive navigation verified
  overflow-free across 10 real phone-width screenshots; dense secondary
  pages (Visit/Stream/Settings) remain long but not broken
- **Remote-access support posture:** private overlay network
  (Tailscale-compatible) is the documented, supported away-from-home
  path; direct public-internet exposure and a MockingBird-operated cloud
  relay are explicitly unsupported/not-built; LAN access via
  `--allow-network` is now discoverable in-product
- **Security implications (this milestone):** 4 new CORS regression
  tests closing a previously-zero coverage gap; new
  `GET /api/product/connection` deliberately kept authenticated (not
  public); media/evidence routes re-confirmed authenticated by policy-
  table inspection; no login rate-limiting exists (real, pre-existing,
  found and documented, not fixed -- see the milestone report)
- **Local Species Prior:** not authorized
- **Another classifier campaign:** not authorized
- **LICENSE:** still genuinely absent -- open business/legal decision, not
  resolved by this or any prior milestone (see Lane P, above)
- **Representative Field Acceptance (attempted 2026-08-25):** Gate C --
  OPEN, insufficient representative evidence; deferred by explicit user
  decision before any live session started (real-authentication/consent
  boundary, not a product defect). See Lane R and
  [representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md).
  Untracked root `uv.lock` investigated and removed per that milestone's
  own Decision A; working tree returned to exactly the seven preserved
  files then, and confirmed still exactly those seven, untouched, at this
  milestone's own start and close. An untracked `uv.lock` recurred mid-
  session during Place Features & Habitat Change v2 (an ordinary,
  never-gitignored side effect of `uv run` tool invocations in this
  actively-shared worktree, not a milestone artifact) -- removed again,
  same reasoning. It recurred a third time mid-session during Place Story
  & Seasonal Timeline v1, for the identical reason (a `git stash push -u`
  bisection re-created it) -- removed again; the working tree was
  confirmed to hold exactly the seven preserved files, untouched, at this
  milestone's own start and close, alongside this milestone's own
  committed additions. Mobile & Remote Experience v1 used `git stash
  push -u`/`pop` for its own Core-gate bisection (see §14) and confirmed,
  both before and after, that the working tree held exactly the seven
  preserved files, byte-identical to milestone start, alongside this
  milestone's own committed additions. Ecological Interoperability &
  Submission Workflows v1 confirmed the same at its own start (before any
  edit) and again at close: exactly the seven preserved files, untouched,
  alongside this milestone's own committed additions -- two peer sessions
  sharing this same working directory were confirmed idle (no file writes
  in 11+ and 105+ minutes respectively) before any write began.
  Multi-Camera Place Experience v2 confirmed the identical seven preserved
  files, untouched, at its own start, throughout (re-verified after two
  `git stash push -u`/`pop` ruff-bisection round-trips), and again at
  close alongside this milestone's own committed additions; two peer
  sessions sharing this same working directory (`mockingbird-active-65`,
  `mockingbird-active-c6`) were confirmed idle/read-only both before any
  write began and again immediately before the implementation commit
  (`git log`'s own unmoved HEAD across the full session, `763fe22`'s
  parent still `21fbc42`, was independent, objective confirmation neither
  peer had committed anything in the interim).
- **Push:** explicit authorization required
