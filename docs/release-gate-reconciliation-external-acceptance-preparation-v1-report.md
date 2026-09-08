# Release-Gate Reconciliation & External Acceptance Preparation v1

**Type:** Bounded, read-only release-readiness/governance reconciliation.
No product, schema, or tooling code changed. No field session run. No
deployment. No external participant contact. No full Core run. No push.

**Classification: A** -- see "Classification," at the end.

This milestone reconciles the accepted Gate A closure into `roadmap.md`'s
own prose, performs a complete remaining-execution-queue classification,
and prepares (without starting) the External Pre-Release Acceptance
(Gate G) plan and the Release Candidate / findings-triage contracts Gate
G and Final Release Hardening will need. It does not execute any of
them.

---

## 0. Executive summary

Since the last global reconciliation (*Global Product & Release
Readiness Reconciliation v2*, 2026-09-06/07, HEAD `5e36989`), six further
milestones ran on the Lane R track and closed the one remaining Gate A
dimension: *Lane R Release-Budget Adjudication & Gate A Decision v1*
(2026-09-07) accepted a specific, narrow true-latency budget and declared
**Gate A: PASS -- Lane R: CLOSED**. That milestone's own documentation
delta explicitly scoped `roadmap.md`'s stale Gate A/"Numeric release
budgets" prose out of its bounded edit and disclosed the gap rather than
leaving it silently inconsistent. This milestone closes that gap by
dated addition (§2), re-derives the complete A-S remaining-queue
classification from v2's own table plus the accepted delta (§3, finding
**zero new release-critical dependency**), and prepares the concrete Gate
G cohort/hardware/findings-intake plan named as that gate's third and
final entry precondition (§4, delivered as a standalone document).

**What this milestone does not do, stated plainly up front, matching the
governing directive exactly:** it does not mark External Pre-Release
Acceptance as executed or passed; it does not mark Final Release
Hardening as started; it does not authorize either, or any other
milestone, itself; it makes no product or schema change; it deploys
nothing; it contacts no external participant; it runs no full Core suite.
**Current authorization remains `NONE`**, returned here exactly as this
milestone's own governing directive requires, for the next external
(ChatGPT) acceptance review to act on.

---

## 1. Verified baseline

Verified directly against the repository at the start of this milestone,
matching the governing directive's own expected baseline exactly:

| Fact | Expected | Verified |
|---|---|---|
| Branch | `main` | `main` |
| HEAD | `aeff038` | `aeff038e5b2774b1779d198badc4749615e77677` (`git rev-parse HEAD`) |
| Schema | v59 | `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) |
| Latest accepted milestone | Lane R Release-Budget Adjudication & Gate A Decision v1 | Confirmed -- `aeff038` is that milestone's own reconciliation commit |
| Lane R | CLOSED | Confirmed -- `release-execution-state.md` §6.R top status line |
| Lane P | CLOSED | Confirmed -- real `LICENSE` (MIT, `Copyright (c) 2026 MockingBird contributors`), `pyproject.toml`/`web/package.json` SPDX metadata present on disk |
| Current authorization | NONE | Confirmed -- every recent milestone's own close returns this value |
| Push state | Not pushed | `+381 -0` vs. `origin/main` |
| Worktree | Clean except seven preserved files | Confirmed byte-identical to `release-execution-state.md` §13's own list (below) |
| Active writers | None expected | `ps aux` shows no `mockingbird`/`uvicorn`/`camera_node`/`deploy_windows_dev` process; `git diff --stat HEAD` empty; `git stash list` empty; HEAD unchanged across this milestone's own research phase |

**The seven preserved untracked detector files** (confirmed present,
untracked, and unmodified, both at the start and immediately before
publishing this report):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

No discrepancy was found between the governing directive's expected
baseline and repository evidence. Several other git worktrees exist on
unrelated, stale branches (last commits 2026-07-20 through 2026-08-22);
none is `main`, none shows evidence of concurrent writing to `main`
during this session, and this session's own `git status`/HEAD were
reconfirmed unchanged immediately before every edit below.

---

## 2. Roadmap reconciliation delta (Gate A)

**Governing sources read, in the order specified:**
`docs/release-execution-state.md` (top-of-file `CURRENT PHASE` narrative
in full; §1 header/tail; §2; §3 header/tail; §§4-6 in full, including
Lane R's own opening and closing status blocks; §13 "Preserved untracked
detector files"; §14 tail; §15 "Update protocol"), `docs/product-doctrine.md`
(in full), `docs/roadmap.md` (in full: "Governing priority before
release," "Current status" framing sections, "Release scope discipline,"
"Scope-reopening rule," "Release readiness vs. continued capability
work," "Release gates" Gate A-G in full, "Numeric release budgets,"
"Public release readiness," "After-release lanes," "Remaining roadmap --
canonical sequence," "Explicit phase gates," "Explicit deprioritization,"
"Release non-blockers," "Field-testing doctrine," "Completed
foundations"); then `docs/lane-r-release-budget-adjudication-gate-a-decision-v1-report.md`,
`docs/lane-r-accumulated-latency-evidence-release-budget-decision-v1-report.md`,
and `docs/global-product-release-readiness-reconciliation-v2-report.md`
(each in full). Also read: `docs/global-remaining-product-development-release-queue-reconciliation-v1-report.md`
(v2's own predecessor, which defines Gate G's three entry preconditions
and the "Ordered global sequence" this milestone continues), and
targeted, decision-relevant sections of the release, packaging,
installation, recovery, privacy, and native-Windows acceptance reports
named in §5, below.

**What was stale.** `roadmap.md`'s Gate A section and "Numeric release
budgets" subsection still read `OPEN -- TRUE LATENCY TAIL EVIDENCE
REMAINS` / "no budget adopted" as of their own 2026-09-06 entries. The
Adjudication milestone's own documentation delta (§9 of its report)
states this explicitly: *"Deliberately not updated: `docs/roadmap.md`...
reconciling `roadmap.md`'s own prose to match is exactly the kind of
global-roadmap-reconciliation action this project's own established
convention... performs as its own dedicated step, not something this
bounded adjudication milestone should reach into unilaterally."*

**What changed.** Two dated, additive corrections in `docs/roadmap.md`
(the file's own established convention -- append, never rewrite history
in place), matching this milestone's exact governing constraints:

1. **Gate A section:** a new "2026-09-07 update (GATE A: PASS -- LANE R:
   CLOSED)" paragraph, inserted immediately after the gate's framing
   paragraphs and immediately *before* the still-preserved 2026-09-06/
   2026-09-05/2026-08-19-through-2026-08-30 historical narrative (which
   remains completely unedited, including the record of the *rejected*
   2026-09-05 "PASS"). States the accepted budget in full (typical
   latency ~80-115s numeric; upper tail qualitative, not an SLA; the
   20-minute bound as an architectural reference, never a measured
   maximum), explicitly reconfirms whole-scene recall is **unchanged**
   and not re-litigated, and explicitly reconfirms the six already-`READY`
   dimensions are **unchanged**.
2. **"Numeric release budgets" -> True capture-to-visible latency
   bullet:** a matching "2026-09-07 update: BUDGET ADOPTED" paragraph
   appended after the existing "MORE EVIDENCE REQUIRED" narrative
   (preserved, not deleted), stating the same three-part budget in the
   terse, numbers-table style the other five accepted bullets already
   use, and pointing to the adjudication report for the full method.
3. **Gate G section:** a new "2026-09-07 update (plan prepared, not
   started)" paragraph noting Gate A's PASS resolves the first of Gate
   G's three entry preconditions, and pointing to the acceptance plan
   this milestone prepares (§4, below) as satisfying the third,
   explicitly stating Gate G itself remains not started.

**What did not change, by design:** no denominator, budget, or accepted
limitation on any of the other seven Gate A dimensions; no historical
paragraph was edited or removed; `release-execution-state.md`'s own
already-correct Gate A/Lane R status (it was never stale -- only
`roadmap.md` was) was not touched beyond this milestone's own three
matching additive entries (top-of-file `CURRENT PHASE`, §3, §6.S) that
record *this* milestone's own closure, per the file's own three-place
convention.

Full diffs: `docs/roadmap.md` (+87 lines, 3 insertions, 0 deletions),
`docs/release-execution-state.md` (+78 lines, 3 insertions, 0 deletions).

---

## 3. Complete remaining-queue classification

Re-derived from *Global Product & Release Readiness Reconciliation v2*'s
own complete nineteen-lane table (its §3), cross-checked against the
accepted delta since it (six Lane-R/Lane-P-track milestones, none of
which touched any other lane). **Lane R's closure is the only material
change to this table since v2.** Bucket legend matches
`release-execution-state.md` §6's own "Four release-shape categories,"
which this milestone reuses rather than inventing a parallel one: **A**
release-critical; **B** pre-release decision; **C** after-release
product work; **D** later/evidence-driven.

| Lane | Status | Remaining work | Bucket |
|---|---|---|---|
| **A** Acoustic/BirdNET | ACCEPTED -- RELEASE-READY OPTIONAL | longer field soak; physical unplug/replug; natural wild-bird field evidence | D |
| **B** Remote/Intermittent-WAN | PARTIAL -- after release unless a new core dependency appears | real LTE/remote-Pi/bandwidth/solar acceptance | C |
| **C** Everyday Product/Discovery UX | MATERIALLY DELIVERED / no known dev remains | none | -- |
| **D** Calm Notifications | MATERIALLY DELIVERED | Web Push; per-user read state; precise deep links; model-unavailable attention; sync diagnostics | D |
| **E** Mobile/Remote UX | PARTIAL, MATERIALLY ADVANCED | dense-page progressive disclosure (D); live external-overlay-network acceptance -- structurally blocked, no external network in this sandbox (**B**) | D/B |
| **F** Multi-Camera/Multi-Site | MATERIALLY ADVANCED; concurrent-write reliability CLOSED; Feature linking CLOSED | cross-camera notification grouping (D); Story wildlife-source attribution (D); ~6 camera-filter UI controls to consolidate (D); GPU/CUDA-driver concurrency measurement + multi-hour soak -- needs real hardware (**B**); broad multi-site -- separate product decision (C) | D/B/C |
| **G** Camera/Source Experience | **CLOSED -- RELEASE-CRITICAL** | none release-blocking | -- |
| **H** Site-Specific Learning | FROZEN | none unless new evidence | D |
| **I** Broader Wildlife Maturity | FROZEN STRUCTURALLY | mature mammal ID -- zero real MockingBird-domain mammal field evidence | D |
| **J** Ecological/External Workflows | MATERIALLY ADVANCED | live OAuth submit; media-byte inclusion; deep-link preselect; batch-filter depth | D |
| **K** Ecosystem/Provider Integrations | DECISION CLOSED -- deferred pending evidence, not required for launch | none (decision-only lane) | -- |
| **L** Appliance/Update/Recovery | MATERIALLY CLOSED -- RELEASE-CRITICAL | `rollback()` doesn't restore a changed systemd unit template; a narrower rollback directory-swap crash-window gap -- both small, disclosed, worked around live once (see §5) | **A** |
| **M** Storage/Retention UX | **CLOSED -- RELEASE-CRITICAL** | orphan-media sweep, deliberately not reopened | D |
| **N** Privacy/Contribution | **CLOSED -- RELEASE-CRITICAL** | none | -- |
| **O** Platform/Runtime Portability | **CLOSED** | none | -- |
| **P** Release Licensing/Distribution | **CLOSED -- RELEASE-CRITICAL** | BirdNET commercial-adjacent legal posture -- no engineering action available | B |
| **Q** Whole-Product UI/Accessibility/Performance | **CLOSED as integrated pass** | disclosed non-blocking test-hygiene/CSS/keyboard-on-zone-polygon items | D |
| **R** Complete Field Acceptance | **CLOSED** (was OPEN) -- Gate A PASS, 2026-09-07 | none blocking; an 18.5GB+ disk-reclaim opportunity across archived Windows dev-roots remains available, non-blocking housekeeping | -- |
| **S** Final Release Hardening (+ Gate G, its own precondition) | LAST; not started; **plan now prepared** (this milestone) | Gate G scoping is done; Gate G *execution* (recruit, run, triage) is the concrete remaining step, strictly before Lane S itself | **A** |

**Confirmation: no concrete release-critical dependency remains before
External Pre-Release Acceptance beyond what is already named above.**
Every release-critical lane (G, L, M, N, O, P, Q, R) is closed or
materially closed with only small, individually disclosed,
hardware/network-access-gated residuals; Lane R -- the sole item that was
genuinely open -- closed 2026-09-07. Gate G's own three entry
preconditions (Lane R closing; Lane P's mechanical adoption; a scoped
cohort/findings plan) are now **all three met** (§4).

**Bucket B -- unresolved pre-release decisions**, unchanged from v2 plus
the owner-decision items this milestone's own Gate G plan surfaces (full
list in §4's "Owner decisions" and consolidated in §8, below):

- BirdNET commercial-adjacent legal posture (standing legal-review item,
  no engineering action available, does not block core public launch).
- Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md`/
  `THIRD_PARTY_NOTICES.md` (brand/trademark review, website/docs polish)
  -- named "not now" in `roadmap.md`'s own "Public release readiness."
- Gate G's own remaining owner decisions (§8).

**Bucket C -- after-release**, unchanged from `release-execution-state.md`
§8 and v2 §7: complete remote/intermittent-WAN/LTE field deployment;
solar/battery; custom CM4/CM5 hardware; research-grade remote-field
acceptance; broad multi-site; native mobile; advanced acoustic
analytics; mature automatic mammal species identification; multi-camera
notification grouping (still genuinely untracked by name anywhere in
`roadmap.md`, per v2's own finding -- recorded here again so it is not
lost a second time); Place Story wildlife-event source attribution;
camera-filter UI consolidation; live OAuth iNaturalist submission,
media-byte inclusion, deep-link preselection; a Wildlife Insights
integration decision (unresearched); GBIF direct publication (deferred,
institutional); Land Management/Agriculture.

**Bucket D -- later/evidence-driven**, unchanged from
`release-execution-state.md` §9 and v2 §8: GenICam, GigE Vision, USB3
Vision, radiometric thermal, specialized industrial cameras,
individual-animal recognition, population estimates, behavior
prediction, causal ecological modeling, large cloud-first
infrastructure; plus evidence-gated items (year-over-year seasonality's
own real-outcome proof; Feature-specific YoY/week-level seasonality;
deeper ERA5/Open-Meteo archive backfill; a dedicated Explore page).

**The durable feature freeze is preserved.** No item in Bucket C or D is
promoted here; this milestone adds no new capability and authorizes
none. Consistent with v1's and v2's own five-question test, nothing in
the delta since v2 (six Lane-R/Lane-P-track milestones, all read-only or
tooling-bounded except the one true code fix in Convergence v4's own
disclosed orphaned-process cleanup) reopens that question.

**Two small documentation-currency findings, disclosed, not
release-blocking, not actioned by this bounded milestone:**

1. `docs/local-mvp-readiness-checklist.md` (one commit, 2026-07-04, never
   updated since) states RTSP, USB/local camera, live playback, and
   continuous/automatic monitoring from live sources are explicit MVP
   *non-goals* -- all four are now real, shipped, documented capabilities
   (`docs/using-mockingbird.md`, last modified 2026-09-05, documents RTSP
   setup, USB/built-in camera setup, and a live Start observing/Stop
   observing loop directly). The checklist's own "Phase 15D" numbering
   scheme appears nowhere in `roadmap.md`'s current Gate-lettered
   structure. This document appears fully superseded by
   `roadmap.md`/`using-mockingbird.md` and is a reasonable candidate for
   retirement or an explicit superseded-marker in a future small
   housekeeping pass -- not touched here, outside this milestone's
   authorized delta.
2. No formal **uninstall** procedure exists anywhere in the product's own
   user documentation (`using-mockingbird.md` documents how to *stop*
   MockingBird, not how to remove it). Because the product is a
   self-contained unpacked folder with no installer/registry/service
   footprint, "delete the folder" is the *believed* answer, but this has
   never been explicitly written down or verified end-to-end. Flagged
   here as a small, concrete, pre-Gate-G documentation action (see the
   Gate G plan's §8 and the "owner decisions" list, §8 below) -- not a
   missing engineering capability, and not actioned by this milestone.

---

## 4. External Pre-Release Acceptance (Gate G) entry criteria and plan

Delivered as a standalone document:
[external-pre-release-acceptance-gate-g-plan-v1.md](external-pre-release-acceptance-gate-g-plan-v1.md).
Summary here for traceability to the governing directive's own required
elements; see that document for full detail on each.

**Authority.** `roadmap.md`'s own Gate G section ("External Pre-Release
Acceptance") is the governing contract; this plan resolves its exact
current naming (the governing directive's own "Lane G" reference is a
naming drift this milestone resolves -- the actual current name is
**Gate G** in `roadmap.md`, distinct from `release-execution-state.md`'s
own, differently-lettered **Lane** system, where Lane G is "Camera/Source
Experience," a different, already-closed lane; Gate G's own downstream
precondition is named **Lane S**, "Actual Final Release Hardening," in
`release-execution-state.md`) rather than inventing a parallel gate.

**Entry criteria, all three now met** (full detail in the plan document
§1): Gate A PASS/Lane R CLOSED (met 2026-09-07); Lane P's mechanical
LICENSE adoption (met 2026-09-06); a scoped cohort/hardware/
findings-intake plan (this document, met 2026-09-07). **Meeting all three
preconditions is not the same as authorizing execution** -- the plan
document says this explicitly and repeatedly, and this report repeats it
here for emphasis.

**What the plan defines** (directive's required elements, each covered
in the named section of the plan document): purpose and entry criteria
(§1); target participant/cohort characteristics and selection rationale,
prioritizing native-Windows-host and Camera/Source-type diversity over
headcount (§2); hardware and native-Windows host coverage, native
Windows first per its own **Validated** status (§3); Local Only
installation and operation (§4); onboarding, first observation, and
first useful result, with an explicit refusal to invent an unowned
numeric time target (§5); correction/review and evidence trust (§6);
multi-camera/Place behavior within accepted scope, with true multi-site
explicitly out of scope (§7); installation, update, recovery, backup,
and uninstall, including the disclosed uninstall-documentation gap (§8);
privacy and consent, including the plaintext-camera-credential
disclosure obligation (§9); optional cloud/acoustic behavior and
licensing disclosures (§10); usability/accessibility and performance
(§11); diagnostics and support boundaries, anchored to the existing
Doctor/support-bundle redaction contract (§12); findings intake,
severity, ownership, and reproduction requirements, reusing §6's
triage contract rather than inventing a second one (§13); acceptance
criteria and exit decision, deliberately qualitative where no governing
document sets a number (§14); rollback/stop conditions at the
per-participant, cohort-wide, and full-Gate-G-abort levels (§15); and
evidence retention and participant-data handling (§16).

**No numeric acceptance target is invented** where none is governed --
matching the same discipline `roadmap.md`'s own Gate A budgets already
apply (e.g., no fabricated onboarding-time SLA, no invented pass/fail
finding-count formula). Every place the plan would otherwise need to
invent a number, it instead names the gap as an explicit owner decision
(consolidated in §8, below).

---

## 5. Release-candidate / freeze-boundary prerequisites

This section defines how the accepted build becomes an internal
acceptance candidate for Gate G. **It does not build or distribute an
RC.** Every mechanism named below already exists and is already
accepted; this section only assembles them into one place, as the
directive requires, rather than re-deriving or changing any of them.

### 5.1 Build identity and reproducibility

`scripts/build_local_product.py` produces the "unpack and run" Windows
distributable via a six-step pipeline: build the frontend into
`src/mockingbird/web_dist/`; build the MockingBird wheel (`pip wheel .
--no-deps`); fetch the CPython embeddable distribution and pre-install
every runtime dependency for `win_amd64`/`cp312`; patch `python312._pth`;
write the hidden `Start MockingBird.vbs` launcher; write
`manifest.json`/`SHA256SUMS` and zip with fixed per-entry timestamps.
**Reproducibility is proven, not assumed:** two independent full
rebuilds from the same source tree produced the identical SHA-256.
Release builds compile from a `git archive` snapshot of a verified
commit (`verify_clean_tracked_source`/`export_clean_source_tree`), not
the live tree -- added after a real leaked-untracked-file incident in a
prior release wheel; `--allow-dirty-source` opts out only for local
iteration, never for a release artifact. Frontend freshness is
separately fingerprinted (SHA-256, `web/dist/frontend-source-fingerprint.json`)
and recorded in `manifest.json`'s `frontend_source_state`.

**Version single-source-of-truth:** `mockingbird.__version__` resolves
via `importlib.metadata.version("mockingbird")` (a dev-checkout-only
fallback constant covers the unpackaged case); the FastAPI app's own
`version=` reads the same value; `tests/test_version_provenance.py`
regression-tests this against `pyproject.toml` and both fallback
constants, closing a previously-real defect (four independently
hand-typed `"0.1.0"` literals with no drift test).

### 5.2 Packaging/provenance verification

`manifest.json`/`SHA256SUMS` carry `build_identity.git_commit`/
`source_state`/`source_clean` (a boolean, `not allow_dirty_source`,
added to match the Camera Node builder's own already-stronger
convention). An **independent** post-build verifier,
`scripts/verify_release_artifact.py`, re-derives every checkable fact
from the files on disk -- recomputes `zip_sha256`, checks every
`SHA256SUMS` entry, and (unless `--allow-dirty-source` explicitly
accepts it) requires `source_clean is True` and a `git:`-prefixed
`source_state` -- **without importing the builder's own code**, so a bug
in the builder's own hashing/writing logic cannot also be invisible to
its own verifier. This runs automatically in CI's `packaging-smoke` job
(`.github/workflows/ci.yml`) after every structural build, alongside
`backend-tests` (Core gate + `python -m mockingbird --check`) and
`frontend` (`tsc --noEmit` + `npm run build`).

### 5.3 Native-Windows installation proof (already on record)

*Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1*
already proved the exact packaged artifact this section describes on
real hardware (Windows 10 Pro `10.0.19045`, native, not a VM; NVIDIA
GeForce RTX 4060 Ti, driver `610.62`, confirmed real passthrough via
native `nvidia-smi.exe`): a fresh, disposable, no-skip-flags deployment
(full GPU/CUDA and BioCLIP dependency closures included), instance
identity confirmed via `GET /api/product/instance`
(`git_commit` exact match to starting HEAD), 16 core workflows exercised
end to end with internet denied throughout via a disposable
user-mode HTTP(S) egress-filtering proxy (honestly disclosed as
process-cooperative, not kernel-level -- no Administrator token was
available in that interop environment), zero unauthorized outbound
traffic, and both production models proven executing at the real
production code path with byte-identical checksums before/after denial
(MDv5a: real `CUDAExecutionProvider` GPU execution, not CPU fallback).
This remains the standing native-Windows installation proof; **Gate G's
own §3 (hardware coverage) is the next opportunity to extend it across
more than one machine.**

### 5.4 Required model and asset availability

Both production models are bundled inside the release tree and verified
by SHA-256 at build time against fixed accepted constants -- never
downloaded at build or run time, never committed to git:

- **MDv5a** (visual detector): `package_observation_runtime_assets`
  copies the accepted MDv5 ONNX bundle from a local, git-ignored source
  directory, independently re-verifying both `ACCEPTED_SOURCE_MODEL_SHA256`
  and `ACCEPTED_ONNX_MODEL_SHA256` before copying. A build with no local
  source available still produces a working artifact whose Observation
  Engine honestly reports a missing-model state until an operator
  supplies one and rebuilds -- it does not fail silently or fetch one.
- **BioCLIP-2**: `package_bioclip_runtime_assets` copies the accepted
  local BioCLIP 2 artifact (Imageomics `bioclip-2`, MIT-licensed),
  independently re-verifying all four expected files' SHA-256 against
  the `ACCEPTED_BIOCLIP_*_SHA256` constants. Approximate sizes: ~1.6GB
  model bundle, ~150MB additional Python runtime dependency closure.
- **GPU/CUDA runtime**: `onnxruntime-gpu==1.28.0` (exact-pinned) plus the
  matching NVIDIA CUDA/cuDNN redistributable wheel set are pip-installed
  into the bundle at build time; the product carries its own DLL search
  path wiring since it does not require a system-installed CUDA Toolkit.

### 5.5 Nonredistribution of restricted BirdNET weights

`verify_no_nc_licensed_acoustic_model_redistribution` is a build-time
guard preventing the CC BY-NC-SA 4.0 (NonCommercial) BirdNET model
weights from ever being bundled or redistributed by an official
MockingBird package; it now runs on every CI `packaging-smoke` build,
not only a manual local build. Acquisition of the weights remains
external and optional; the core visual product is fully functional
without them. This mirrors, but is a distinct mechanism from, ffmpeg's
own non-bundling posture, which is structural (ffmpeg is a pure external
system dependency, `shutil.which("ffmpeg")`, never a pip dependency and
never fetched by the build script) rather than an active checker --
Doctor reports its absence honestly (a `WARN`, never silent, with a
remediation link), and the recommended Camera Node golden path needs no
ffmpeg at all.

### 5.6 Local Only guarantees

Proven directly, not merely declared, by the native-Windows acceptance
in §5.3: zero unauthorized outbound network activity across 16 core
workflows with a real, live LAN call to a paired Camera Node still
succeeding and optional-provider destinations (weather, iNaturalist)
correctly refused rather than silently stubbed. Privacy Zones remain
trigger-level exclusion, not guaranteed pixel redaction -- an existing,
already-documented limitation, not a regression to watch for.

### 5.7 Configuration and secret handling

Camera/RTSP/ONVIF credentials are stored **plaintext at rest**
(`json.dumps` into `source_provider_configurations.config_json`) --
confirmed, documented in at least three prior accepted reports, and
recorded as a non-defect: no contract promises encryption, and
credentials sit behind the same local filesystem/OS-account boundary as
every other local product fact. Camera Node **pairing** secrets, by
contrast, are hash-only (`credential_sha256`), and diagnostics are
regression-tested to never leak either class of secret
(`test_report_json_never_includes_sensitive_value_shaped_text` and the
Camera Node upgrade path's own equivalent). Session cookies are real,
server-side, and confirmed to never leave the Host.

### 5.8 Rollback and recovery

**Host:** an automatic pre-migration safety backup runs before any
in-place schema upgrade (`pre_migration_hook`, fires only when a
pre-existing database is genuinely about to migrate); a post-migration
`PRAGMA quick_check` gates readiness; **restoring that automatic backup
is the only real rollback path** -- there is no schema down-migration,
and none is invented. Interrupted-upgrade behavior (backup failure,
mid-chain migration failure, post-migration integrity failure) all fail
closed and are regression-tested.

**Camera Node:** `scripts/install_camera_node.py`'s upgrade path runs a
real preflight (checksums, wire-protocol compatibility, disk space) that
alone can block `install()` before any mutation; stages and verifies a
candidate build in a separate venv (a real `import mockingbird_node.app`
inside it) before the live install is touched; activates manifest-first,
venv-second (each an individually atomic rename); and **automatically
restores the prior known-good build** if post-activation health
verification fails. **Two small, disclosed, not-yet-closed residual
gaps** (real, found live on the reference Pi, not hypothetical):
`rollback()` restores code but not an already-changed systemd unit
template (worked around live, once, with a temporary labeled drop-in,
not structurally closed); `rollback()`'s own directory swap has a
narrower residual crash-window gap than the forward-upgrade path's own
reconciliation state machine closes. Both are Lane L's own named
remaining items (§3, above) and are appropriate Gate G/Final Hardening
follow-up, not blockers to starting Gate G.

### 5.9 Support/diagnostic artifact collection

`python -m mockingbird doctor` is a read-only composition layer (never
constructs a repository connection, never runs migrations) that checks
15 named components (application, database connectivity/schema, storage,
backup, Camera Node, Camera Node transport, ffmpeg, detector model,
species identification, GPU/CUDA, clock, offline ingest, research/
export, acoustic runtime, media integrity), reports
`HEALTHY`/`DEGRADED`/`UNHEALTHY` with Nagios-style exit codes, and
completes in single-digit milliseconds on a healthy install. `python -m
mockingbird support-bundle` reuses Doctor's own report for its health
section and is documented to never include camera passwords, pairing
secrets, or media -- only Doctor's results, an automatically-redacted
log slice, and version facts. This is the correct, already-existing
mechanism for Gate G findings intake (§6, below; the Gate G plan's own
§12) -- no new diagnostics surface is needed.

### 5.10 Known limitations and release notes

The following are already-disclosed, accepted, non-blocking facts that
belong in eventual release notes, assembled here rather than
re-investigated: whole-scene Visit recall may fall to ~64.7%
(conservative) during unusually busy/sustained multi-bird activity
(accepted known limitation, no numeric floor); true capture-to-visible
latency is typically ~80-115 seconds with an occasionally longer,
qualitatively-disclosed tail; camera/RTSP credentials are plaintext at
rest; ffmpeg is a required external dependency for RTSP/USB/import
camera types (not for the Camera Node golden path); BirdNET acoustic
assistance is optional, off by default, and CC BY-NC-SA 4.0 licensed
(never redistributed); true multi-site, remote/LTE/solar deployment, and
native mobile are all out of scope for this release; no formal uninstall
procedure is yet written down (§3, above).

---

## 6. Findings/defect triage contract

A small, practical workflow, reusing this project's own existing
conventions rather than a new issue-management platform:

**intake -> reproduce -> severity -> owner -> correction -> validation
-> accept/reject/defer -> acceptance decision.**

| Stage | What happens |
|---|---|
| **Intake** | One owner-designated channel (this milestone does not choose one -- whatever the owner already uses for accepted-milestone tracking is the right default, per this project's own "do not create a new issue-management platform" instruction). Every finding records: what was done, what was expected, what happened, the reporter's Doctor summary/support bundle where relevant, host OS/GPU, camera type. |
| **Reproduce** | Every finding must be independently reproduced against the exact accepted HEAD before triage proceeds -- matching this project's own standing discipline (every accepted milestone in this repository's history independently re-verifies a defect before fixing it, never fixes on a single unreplicated report). An unreproducible finding is recorded, not discarded, and revisited if it recurs. |
| **Severity** | **Sev-0 (stop):** a truth-boundary violation (a correction that doesn't stick, a model output silently becoming Reviewed truth), data loss/corruption, a genuine Local Only/privacy breach, or a crash loop with no recovery. **Sev-1 (release-blocking):** a reproduced defect inside an already-accepted Gate A dimension's own accepted budget (e.g., a false-Visit rate or fragmentation defect, not merely an edge of the disclosed tail). **Sev-2 (fix before launch, not release-blocking):** a real defect outside Gate A's own accepted dimensions -- a UI bug, an onboarding friction point, a documentation gap (e.g., the uninstall gap named in §3). **Sev-3 (defer/backlog):** enrichment, a Bucket C/D item surfaced by a participant, or a cosmetic issue. |
| **Owner** | The project owner triages and assigns; this contract does not name a person, since none is fixed by any governing document. |
| **Correction** | Standard implementation discipline already governs this repository (bounded archaeology, separate investigation/implementation, focused-then-broader validation tiers) -- unchanged by Gate G, not redefined here. |
| **Validation** | A fix is validated against the specific reproduction, then against the relevant accepted-milestone test suite it touches, per this project's own existing validation-tier discipline (`development-workflow.md`/`test-suite-validation-tiers-contract.md`) -- not a new Gate-G-specific test regime. |
| **Accept/reject/defer** | Accept: fixed and validated. Reject: not reproducible, not a real defect, or already a disclosed/accepted limitation (in which case the finding closes with a pointer to the accepted disposition, not silently). Defer: real, not release-blocking, recorded in the appropriate Bucket C/D queue. |
| **Acceptance decision** | Gate G's own exit decision (the plan document's §14) is a qualitative release-authority judgment against the accumulated findings ledger -- whether any Sev-0/Sev-1 finding remains unresolved, and whether the accepted Gate A budgets held under real field conditions -- not a fixed numeric formula, consistent with how recall and latency were each resolved by an explicit decision rather than an invented number. |

**Reopening discipline, explicitly carried over, not weakened:**
accepted milestones remain frozen except for concrete evidence-based
reopening grounds -- a reproduced defect, genuine new field evidence, a
real dependency, or explicit owner authorization. A Gate G participant's
single, unreplicated report is not, by itself, grounds to reopen an
accepted Gate A dimension; a reproduced pattern across participants, or
one finding that squarely contradicts an accepted budget under ordinary
(not adversarial) conditions, is.

---

## 7. Risks and stop conditions

| Risk | Mitigation already in place / recommended |
|---|---|
| A participant hits the already-accepted sustained/crowded recall limitation and reports it as "MockingBird missed a bird" | Disclosed, expected behavior -- the Gate G plan's own findings-triage addition (§13 of that document) evaluates this against the accepted budget, not the participant's raw expectation; the participant-facing disclosure (§10 of the plan, "Sustained/crowded-activity behavior") should be shown before this can be mistaken for a defect. |
| A participant on a non-CUDA machine reports detection "not working" | Expected, honest, tested behavior (`onnx_cuda_unavailable`), not a defect -- must be disclosed to that participant in advance (Gate G plan §3). |
| A finding reproduces across multiple participants | Cohort-wide stop per the Gate G plan §15 -- triage before continuing, since a cross-participant pattern is exactly the "reproduced defect" reopening ground this project's own discipline already recognizes. |
| A finding contradicts an accepted Gate A budget under ordinary conditions | Full Gate G stop/abort per the plan §15 -- returns the product to Lane R, not merely a Gate G iteration; this is the one scenario genuinely capable of reopening the 2026-09-07 PASS decision, and should be treated with the same rigor that decision itself required (independent reproduction against primary evidence, not a single report taken at face value). |
| A participant's Local Only guarantee is silently broken (an unexpected outbound call) | Sev-0 by definition (§6, above) -- stop that participant's session immediately, reproduce against the exact build, and do not resume Gate G broadly until root-caused. |
| Recruitment or scope drifts toward hundreds of users, or toward validating an explicitly out-of-scope capability (remote/LTE, broad multi-site, native mobile) | `roadmap.md`'s own "small external cohort... not hundreds" instruction and the plan's own explicit out-of-scope list (§2, §7 of the plan) are the guardrail; this report names it here so a future session inherits the constraint, not only the plan document. |
| Gate G is described externally as a "beta" | Explicitly, repeatedly prohibited by `roadmap.md`'s own Gate G text ("do not describe it, or the release that follows it, as a beta externally") -- carried into the plan's own §1 and repeated here. |
| This milestone's own scope creeps into executing Gate G, starting Final Release Hardening, or self-authorizing the next milestone | Explicitly and repeatedly refused throughout this report and its companion documents, matching the governing directive's own closing prohibitions verbatim (§8, below). |

---

## 8. Owner decisions still required

Consolidated from the Gate G plan document's own per-section flags,
plus this report's own findings. None of these is self-authorized by
this milestone or its companion documents.

1. **Begin Gate G execution -- the actual go/no-go.** All three entry
   preconditions are met and the plan is prepared; starting recruitment
   and running the first session is a distinct, explicit authorization
   this milestone does not grant.
2. **Exact cohort headcount, participant identities, and recruitment
   channel** (plan §2) -- `roadmap.md` only constrains "small... not
   hundreds."
3. **Consent mechanism** -- a formal written consent form versus a
   plain-language acknowledgment (plan §9).
4. **Any numeric onboarding-time or acceptance target**, if the owner
   wants one beyond the qualitative criteria this plan adopts (plan §5,
   §14) -- none is invented here because none is governed.
5. **The exact severity/count formula (if any) for Gate G's exit
   decision**, versus a direct qualitative release-authority judgment
   against the findings ledger (plan §14, this report's §6).
6. **Findings-intake channel selection** -- which existing tracking
   surface to reuse (§6, above).
7. **Confirm and document the exact uninstall procedure** before relying
   on it in front of participants -- small, concrete, and worth doing
   before Gate G recruitment begins (§3, above; plan §8).
8. **Whether to retire or mark superseded**
   `docs/local-mvp-readiness-checklist.md` (§3, above) -- a small
   documentation-hygiene decision, not release-critical.
9. **The BirdNET commercial-adjacent legal review itself**, whenever the
   owner wants it -- standing, no engineering action available, does not
   block core launch (unchanged from every prior reconciliation).

---

## 9. Recommended next single milestone

**Advisory only, not self-authorized**, per the governing directive's
own explicit instruction and this project's own standing convention that
a "next natural milestone" suggestion never fills the authorization
field itself.

**Top recommendation:** resolve the small, concrete owner decisions in
§8 (items 2, 3, 6, 7 in particular carry no dependency and can be
decided in parallel with nothing else), then **begin Gate G execution**
per the prepared plan -- recruit the cohort, run the first
session(s), and start populating the findings ledger this report's §6
defines. This is the correct next step in the accepted sequence
(*Global Remaining Product-Development & Release-Queue Reconciliation
v1*'s own "Ordered global sequence": "...Scope and begin External
Pre-Release Acceptance (Gate G): define cohort size/diversity and a
findings-intake process" -- now scoped by this milestone, execution is
the remaining step) and it is the only item standing between the
accepted product and Final Release Hardening.

**Small, optional, non-blocking parallel work** (any or none, at the
owner's discretion, none gating Gate G): Lane L's two disclosed
rollback/systemd-template residuals; the uninstall-procedure
documentation gap (§8, item 7); the 18.5GB+ disk-reclaim housekeeping
opportunity noted in Lane R's own record.

**Explicitly not recommended:** any Bucket C/D product-development item
(remote/LTE, broad multi-site, native mobile, further Place-Intelligence
enrichment, another classifier campaign, etc.) merely because it is
adjacent to recently-accepted work -- none clears the release-necessity
bar, and picking one now would repeat exactly the adjacency-driven
selection error `roadmap.md`'s own scope discipline and this project's
recent reconciliations both warn against.

---

## 10. Documentation delta (what this milestone changed)

- `docs/roadmap.md`: three additive, dated corrections (Gate A section;
  "Numeric release budgets" latency bullet; Gate G section). No
  historical text edited or removed. +87 lines / 3 insertions / 0
  deletions.
- `docs/release-execution-state.md`: three additive, dated corrections,
  matching this file's own established three-place convention
  (top-of-file `CURRENT PHASE`; §3 "Current authorized milestone"; §6.S
  "Actual Final Release Hardening"). No historical text edited or
  removed. +78 lines / 3 insertions / 0 deletions.
- `docs/external-pre-release-acceptance-gate-g-plan-v1.md`: new document
  (this milestone's own Gate G plan, §4 above).
- `docs/release-gate-reconciliation-external-acceptance-preparation-v1-report.md`:
  this report.

**No other file changed.** No product, schema, or tooling code touched.
No test run beyond the direct, targeted verification steps in §1. The
seven preserved untracked detector files remain present, untracked, and
byte-unmodified, reconfirmed immediately before this report's own
publication.

---

## 11. Explicit non-goals (restated from the governing directive)

Of this milestone itself: no product/schema change; no deployment; no
external participant contact; no full Core run; no push; no self
-authorization of the next milestone. Of the release sequence: External
Pre-Release Acceptance is **not** marked executed or passed; Final
Release Hardening is **not** marked started; neither is authorized here
or by any companion document this milestone produces. No numeric
acceptance target is invented where no governing document supplies one.
No accepted Gate A budget, denominator, or limitation is silently
changed -- every one is either explicitly reconfirmed unchanged (§2,
above) or untouched.

---

## 12. Classification

**A** -- a complete, bounded governance reconciliation with no residual
gap in its own scope. Every fact above is grounded in direct repository
evidence gathered this session (full reads of every governing source
named by the directive, plus two parallel, read-only research passes
extracting citation-precise facts from the packaging/release/native
-Windows/recovery reports and the diagnostics/onboarding documentation),
not in memory or historical reconstruction. The one stale-prose gap
named by the immediately-prior milestone (`roadmap.md`'s Gate A
reconciliation) is closed, by dated addition, preserving history exactly
as this project's own convention requires. The complete remaining-queue
classification found zero new release-critical dependency. The Gate G
plan meets every element the governing directive named, self-authorizes
nothing, and explicitly flags every owner decision it cannot resolve
itself. The release-candidate prerequisites and findings-triage contract
assemble already-accepted mechanisms into one place without inventing or
changing any of them. No product/schema change. No deployment. No
external participant contact. No push. Authorization returned exactly as
required: **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, for
the next external (ChatGPT) acceptance review.

---

*Prepared as a bounded, read-only release-readiness/governance
reconciliation milestone. No product, schema, or tooling code was
changed. No field session was run. No deployment occurred. No external
participant was contacted. No push was made.*
