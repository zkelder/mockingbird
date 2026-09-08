# External Pre-Release Acceptance -- Private Cohort v1

**Type:** Bounded Gate G setup milestone under the durable feature freeze.
Verifies an internal acceptance candidate from the accepted baseline,
prepares participant-specific materials, and stops at the owner approval
checkpoint the governing directive requires before any external contact,
build distribution, or participant enrollment.

**Classification: A** -- see "Classification," at the end.

This milestone does **not** contact, name, or recruit a participant;
does **not** distribute a build externally; does **not** create an
account or grant private-repository access; does **not** begin Gate G
execution; does **not** start Final Release Hardening; and does **not**
reopen Gate A. No push. No history rewrite. All seven preserved untracked
detector files remain untouched.

---

## 0. Executive summary

Verified the expected baseline exactly (§1): HEAD `2fe2729`, schema `v59`,
Gate A PASS / Lane R CLOSED, Lane P CLOSED, Gate G prepared/not started,
authorization `NONE`, worktree clean except the seven preserved untracked
files, no active writer, not pushed. Confirmed by direct diff that the one
commit since the last real-hardware proof (`6cebe0a` -> `2fe2729`, the
entry-readiness milestone's own reconciliation commit) touches only
`docs/release-execution-state.md` -- **zero production code has changed**
since *External Acceptance Entry Readiness & Uninstall Closure v1*'s own
real native-Windows proofs (landed at `6cebe0a`), so this milestone's own
candidate inherits those proofs rather than needing to redo them.

**Built and independently verified a real internal acceptance candidate**
at the current accepted HEAD, not merely cited historical evidence (§3):
a full, unskipped `scripts/build_local_product.py` run (frontend, GPU/CUDA
runtime, BioCLIP runtime, both production models, clean `git archive`
source) produced `MockingBird-windows-x64.zip` (18,727 files,
4,922,804,306 bytes unpacked; `git_commit`
`2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d`, `source_clean: true`).
`scripts/verify_release_artifact.py` -- a deliberately independent verifier
that never imports the builder's own code -- passed cleanly (exit 0). Every
checked SHA-256 (both MDv5a files, all four BioCLIP asset files) matched
the accepted constants baked into the build script; the build-time
nonredistribution guard for restricted BirdNET weights ran unconditionally
and passed, and a direct filesystem search confirmed zero BirdNET model
files anywhere in the bundle (§3.9). **Launched the actual
candidate on real native-Windows hardware** (Windows 10 Pro `10.0.19045`,
NVIDIA GeForce RTX 4060 Ti): `GET /api/product/instance` reported
`git_commit: "2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d"` and
`build_id: "77da0b86cfbb47f7"`, both byte-identical to the build's own
manifest -- direct proof the running instance is the exact candidate that
was built and verified, not merely a same-looking one. A bounded TCP
-connection spot-check during boot, API calls, and Doctor found no
non-loopback connection of any kind. Restarting against the same data home
after a forceful stop proved recovery (§3.6): the database was byte
-identical before and after, and the second boot succeeded immediately.
Neither of the product's own two documented stop methods (forceful or
non-forceful process termination -- there is no documented in-app "Stop"
action) produced a shutdown Doctor considers clean; disclosed as a
secondary, non-blocking observation (§3.6, §7), not escalated, since it
causes no data risk and the resulting message is honest and calm.

**One real, reproducible, non-release-blocking Doctor defect was found and
is disclosed, not fixed** (§3.7, §7): a fresh instance's Storage check
reports `FAIL`/`BLOCKING` ("configured media storage folder does not
exist") from the moment the server has started even once -- which happens
before a participant reaches the first-run wizard's Storage step, not
after -- because `_interpret_storage`'s own intended "not started yet, this
is expected" `PASS` branch is gated on `mockingbird.sqlite3` existing on
disk, but that file is created at server-process startup itself, not at
wizard completion. A brand-new participant who runs Doctor mid-setup (the
participant materials this milestone prepares explicitly ask them to) would
see an alarming, inaccurate "genuine problem" message during entirely
normal first-run setup. No data loss, corruption, or truth-boundary risk;
classified Sev-2 (fix before launch, not release-blocking) per the Gate G
findings-triage contract already in force; not fixed here, per this
milestone's own bounded scope and its directive's explicit instruction not
to expand into unrelated hardening.

**Prepared all nine required participant materials** (§4;
[participant-materials companion document](external-pre-release-acceptance-private-cohort-v1-participant-materials.md)),
grounded only in already-governed facts (the accepted Gate A latency/
recall/false-Visit/fragmentation budgets, the closed uninstall contract,
BirdNET's licensing posture, Local Only defaults) -- no numeric onboarding
target or exit formula is invented, matching the operating decisions this
milestone's own directive supplied. **Nothing was sent to anyone; no
participant is named or assumed available.**

**Stops at the owner approval checkpoint** (§5), exactly as the governing
directive requires: no external invitation, account, build distribution,
or participant enrollment occurs in or after this milestone without
explicit owner approval of the specific items listed there. Sections 6-7
of the governing directive (actual acceptance execution; findings and
exit) are **not performed** -- there is no participant evidence to report,
and none is fabricated.

`docs/release-execution-state.md` is updated (§8) to record this
milestone's own accepted factual delta. **Authorization returns to `NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`.** Gate G remains not
started: no participant recruited, no cohort fixed, no build distributed,
no finding collected from an actual participant.

---

## 1. Verified baseline

Verified directly against the repository at the start of this milestone,
matching the governing directive's own expected baseline exactly:

| Fact | Expected | Verified |
|---|---|---|
| Branch | `main` | `main` |
| HEAD | `2fe2729` | `2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d` (`git rev-parse HEAD`) |
| Schema | v59 | `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) |
| Latest accepted milestone | External Acceptance Entry Readiness & Uninstall Closure v1 | Confirmed -- `2fe2729` is that milestone's own reconciliation commit |
| Gate A / Lane R | PASS / CLOSED | Confirmed -- `release-execution-state.md` §6.R |
| Lane P | CLOSED | Confirmed -- real `LICENSE` (MIT) present in this milestone's own fresh build (§3) |
| Gate G | prepared, not started | Confirmed -- `release-execution-state.md` §6.S 2026-09-08 entry |
| Current authorization | NONE | Confirmed -- `release-execution-state.md` §3 top entry |
| Push state | Not pushed | `+385 -0` vs. `origin/main` at start |
| Worktree | Clean except seven preserved files | Confirmed byte-identical to the list below |
| Active writers | None expected | No `mockingbird`/`uvicorn`/`camera_node`/`deploy_windows_dev`/`build_local_product` process running at start; `git stash list` empty; HEAD unchanged throughout except this milestone's own final reconciliation commit |

**The seven preserved untracked detector files** (confirmed present,
untracked, and unmodified at the start, throughout, and immediately before
this report's own publication):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

No discrepancy was found between the governing directive's expected
baseline and repository evidence -- **no reconciliation was required before
proceeding.**

**Zero production code has changed since the last real-hardware proof.**
`git diff --stat 6cebe0a..2fe2729` touches only `docs/release-execution-
state.md` (141 insertions, 0 other files). This means *External Acceptance
Entry Readiness & Uninstall Closure v1*'s own real native-Windows uninstall
proof, and every accepted proof before it (Native-Windows Packaged
Local-Only Acceptance & Privacy Closure v1's 16-workflow internet-denied
proof, the Lane O/G closures, the Gate A PASS itself), governs the exact
same production code this milestone's own candidate is built from --
extending, not repeating, that evidence base.

**Governing sources read, in the order specified:**
`docs/release-execution-state.md` (top-of-file `CURRENT PHASE` narrative in
full; §1 head; §2; §3; §§4-6 including Lane R's and Lane S's own complete
status blocks; §13 "Preserved untracked detector files"; §14 tail; §16
confirmed self-declared stale/historical, not relied on), `docs/product-
doctrine.md` (in full), `docs/roadmap.md` ("Governing priority before
release," "Release scope discipline," "Scope-reopening rule," Gate G in
full, "Numeric release budgets" in full, "Public release readiness,"
"Field-testing doctrine," "Roadmap non-goals"); then
`docs/external-pre-release-acceptance-gate-g-plan-v1.md` (in full,
including the 2026-09-08 addendum), `docs/external-acceptance-entry-
readiness-uninstall-closure-v1-report.md` (in full), `docs/release-gate-
reconciliation-external-acceptance-preparation-v1-report.md` (in full,
including its §5 release-candidate prerequisites and §6 findings-triage
contract); `docs/using-mockingbird.md` (in full); `THIRD_PARTY_NOTICES.md`
(BirdNET section); the accepted Gate A decision chain cross-referenced
directly from `release-execution-state.md` §6.R rather than re-read
milestone-by-milestone, consistent with this project's own "do not reopen
an accepted milestone" discipline.

---

## 2. Private cohort operating decisions (from the governing directive)

The governing directive itself supplies the operating defaults this
milestone plans against, superseding nothing already governed and
inventing nothing new:

- Initial target: 3-5 independent participants.
- Recruitment: direct private invitation through trusted contacts or
  relevant birding/nature communities; no public announcement.
- Include non-developers and varied supported native-Windows hardware
  where practical.
- Local Only is a mandatory first-class acceptance path.
- Consent: explicit written opt-in before enrollment or data collection.
- Findings: private, access-restricted intake using the existing
  repository issue mechanism or an equivalent owner-controlled channel.
- Numeric onboarding/exit targets: none invented; any missing numeric
  target remains an explicit owner decision.
- Exit severity/count rules: the current Gate G contract (§6 of the
  reconciliation report) is preserved; no new rule is invented or silently
  adopted.

These match, word for word in substance, the not-yet-approved proposal
*External Acceptance Entry Readiness & Uninstall Closure v1* already
prepared in the Gate G plan's own 2026-09-08 addendum -- this milestone
does not need to invent a second, competing proposal; it reuses the
existing one and carries it to the owner approval checkpoint (§5).

---

## 3. Internal acceptance candidate

**Purpose.** Prepare and verify a concrete, current internal candidate
build from the accepted baseline before any participant sees it -- not
build or distribute a release candidate for participants yet (§5 governs
that). No production perception, schema, or product feature was changed to
do this.

### 3.1 Build identity and reproducibility

Ran `python scripts/build_local_product.py dist/mockingbird-gate-g-
candidate-2fe2729` on this sandbox's Linux/WSL build host -- the same
six-step pipeline every accepted release-engineering milestone already
uses, with **no skip flags**: real `npm ci`/`vite build` frontend, a clean
`git archive` snapshot of HEAD (not the live tree), the full GPU/CUDA
-runtime closure, and the full BioCLIP runtime closure, all from the
already-accepted local model/wheel-cache sources
(`data/models/observation-onnx-cuda`, `data/models/bioclip-2`,
`.build-cache/wheels-win_amd64-cp312-cuda13`, `.build-cache/wheels-
win_amd64-cp312-bioclip`) -- reusing the existing offline wheel caches, no
new network fetch required. Build completed cleanly (~13 minutes,
dominated by frontend build and dependency installation) and printed the
artifact path with no error.

**`manifest.json` build identity** (read directly from the produced file,
not narrated):

| Field | Value |
|---|---|
| `git_commit` | `2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d` -- exact match to HEAD |
| `source_state` | `git:2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d` |
| `source_clean` | `true` |
| `build_id` | `77da0b86cfbb47f7` |
| `built_at` | `2026-09-08T17:42:16+00:00` |
| `app_version` | `0.1.0` |
| `embedded_python_version` | `3.12.7` |
| `artifact` | `MockingBird-windows-x64.zip` |
| `zip_sha256` | `36b9668b31e5b512a89962379ce6b15229ab70b7f06c506b44b4c2192eb16313` |
| `bundle_file_count` | `18,727` |
| `bundle_total_bytes` (unpacked) | `4,922,804,306` |
| Artifact size (zip, on disk) | `2,912,842,833` bytes |

**Reproducibility** is a separately accepted, frozen property of this exact
pipeline (two independent full rebuilds proven byte-identical during
*Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1*, Lane
O now `CLOSED`) -- not re-proven from scratch here, consistent with "do not
reopen an accepted milestone without a reproduced defect." What this
milestone adds is a **fresh, current, independently-verified build
identity for the actual candidate now on record** (below), not a second
reproducibility proof of the mechanism itself.

### 3.2 Packaging/provenance verification (independent)

`scripts/verify_release_artifact.py dist/mockingbird-gate-g-candidate-
2fe2729` -- deliberately does not import the builder's own code -- passed:

```
OK: MockingBird-windows-x64.zip (18727 files, 4,922,804,306 bytes), version 0.1.0, source git:2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d
```

Exit code `0`. This independently re-derived `zip_sha256`, checked every
`SHA256SUMS` entry, and confirmed `source_clean: true` with a `git:`
-prefixed `source_state` from the files on disk -- not from trusting the
manifest's own claims about itself.

### 3.3 Required production models/assets

Both production models are present, bundled, and SHA-256-verified against
the accepted constants hard-coded in the build script -- checked directly
against `manifest.json`, not merely assumed present:

| Asset | Manifest field | Value | Matches accepted constant |
|---|---|---|---|
| MDv5a ONNX model | `observation_model_bundle.onnx_model_sha256` | `b03ef79...0abbc` | `ACCEPTED_ONNX_MODEL_SHA256` -- exact match |
| MDv5a source model | `observation_model_bundle.source_model_sha256` | `fe3e90e...94a5e` | `ACCEPTED_SOURCE_MODEL_SHA256` -- exact match |
| BioCLIP-2 model weights | `bioclip_model_bundle.model_weights_sha256` | `b7b2bf6...eaf7d` | `ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256` -- exact match |
| BioCLIP-2 model config | `bioclip_model_bundle.model_config_sha256` | `1bf947e...ce68c` | `ACCEPTED_BIOCLIP_MODEL_CONFIG_SHA256` -- exact match |
| BioCLIP-2 labels | `bioclip_model_bundle.labels_sha256` | `b90cea2...ae7fa` | `ACCEPTED_BIOCLIP_LABELS_SHA256` -- exact match |
| BioCLIP-2 embedding cache | `bioclip_model_bundle.embedding_cache_sha256` | `0260d5b...6913b` | `ACCEPTED_BIOCLIP_EMBEDDING_CACHE_SHA256` -- exact match |

GPU/CUDA runtime closure included (`gpu_runtime_included: true`,
`onnxruntime-gpu==1.28.0` exact-pinned plus the matching CUDA 13/cuDNN 9
redistributable set) and independently DLL-verified at build time
(`native_cuda_runtime.checked: true`; 20 real `.dll` files confirmed
present across 5 directories, including `cublasLt64_13.dll` -- the exact
~400-480 MB dependency a real prior native-Windows acceptance pass found
silently missing before `verify_windows_gpu_runtime_dll_closure` existed).
BioCLIP runtime closure included (`bioclip_runtime_included: true`,
`torch==2.11.0+cpu` -- correctly CPU-only, per accepted design).

### 3.4 Native-Windows launch and build-identity self-report

Copied the built artifact to real native-Windows hardware (Windows 10 Pro
`10.0.19045`, NVIDIA GeForce RTX 4060 Ti, driver `610.62`) via `robocopy`
(18,727 files, 4.584 GB, 0 failed, 0 mismatched -- a third independent
confirmation of the manifest's own file count, after the manifest itself
and the independent verifier) and launched it with `python.exe -m
mockingbird --no-browser` against a disposable `MOCKINGBIRD_HOME`, mirroring
the established never-touch-real-data isolation convention.

- Ready in 4 seconds. `GET /health` -> `{"status":"ok"}`.
- **`GET /api/product/instance`** ->
  `{"instance_id":"5b96799498d8f7354c423cab08a115b3","app_version":"0.1.0","git_commit":"2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d","build_id":"77da0b86cfbb47f7"}`
  -- `git_commit` and `build_id` are **byte-identical** to the build's own
  manifest (§3.1). This is direct, running-instance proof that the exact
  candidate that was built and independently verified is the one that
  actually boots and serves traffic, not merely a same-looking one.
- **`GET /api/product/connection`** correctly returned `401`, `"Sign in to
  continue."` -- expected, not a defect: *Local Identity acceptance-closure
  v1* (2026-08-23) requires authentication on every endpoint; this run
  never completed first-run sign-in, so the enforced-auth behavior is
  exactly what should happen, and is itself a positive confirmation that
  the auth boundary is real on this exact candidate.
- Data home populated correctly on first launch: `data/mockingbird.
  sqlite3` (909,312 bytes -- an ordinary freshly-initialized v59 database,
  the same size independently produced by *External Acceptance Entry
  Readiness & Uninstall Closure v1*'s own real-hardware test), `logs/
  mockingbird.log`, `instance_identity.json`, `runtime_state.json` -- all
  under the disposable data home, none elsewhere, consistent with the
  storage-location contract §3.1 of the uninstall-closure report already
  proved.

### 3.5 Local Only spot-check

A bounded TCP-connection-table check (`Get-NetTCPConnection -OwningProcess
<pid>`) covering boot, the API calls above, and the Doctor run below found
**only loopback (`127.0.0.1`) connections** -- one `LISTEN` on `:8000` and
several `ESTABLISHED` loopback pairs from this test's own local HTTP calls.
**Zero connections to any non-loopback address of any kind.** This is a
lighter, corroborating spot-check for this specific fresh build, not a
repeat of the already-accepted, more rigorous internet-denied 16-workflow
proof (*Native-Windows Packaged Local-Only Acceptance & Privacy Closure
v1*, Lane O `CLOSED`) -- that proof already governs this exact,
unchanged production code (§1).

### 3.6 Recovery proof (unclean stop, then restart)

To exercise recovery, not merely a clean-path smoke test: the first run
above was stopped with `Stop-Process -Force` (a hard kill, equivalent to
Task Manager's own force-terminate on a process with no closable window --
i.e., a realistic real-user stop path, not an artificial one). Doctor
afterward correctly, honestly reported `WARN` / "The previous MockingBird
run did not shut down cleanly," with actionable, non-alarming recovery
text -- not a crash, not data loss.

**Restarting against the exact same data home** (§3.1 of this report,
"recovery" claim): the database file was confirmed **byte-identical before
and after** the restart (909,312 bytes both times), the server became
ready immediately (0s to `/health` `ok`), and `GET /api/product/instance`
again reported the identical `git_commit`/`build_id`. **Recovery after an
unclean stop is proven, not assumed.**

A gentler stop was then tried on this second run, to see whether the
`WARN` above is specific to a hard kill: `taskkill` **without** `/F`
(Windows' own "polite" termination request). It reported success and the
process did exit within 3 seconds -- but Doctor afterward reported the
**identical** `WARN` again. Reading the actual documented stop procedure
(`using-mockingbird.md` "Uninstall," step 1) confirms why: MockingBird's
*only* documented stop paths are closing the browser tab (which never
touches the backend process at all) or ending `pythonw.exe`/`python.exe`
in Task Manager -- there is no documented in-app "Stop MockingBird" action,
and neither OS-level termination method this milestone tried produced a
shutdown Doctor considers clean. This is disclosed as a secondary,
non-blocking observation (§7, finding 2, revised), not escalated into a
defect: the `WARN` text is honest and calm, causes no data risk (proven
directly, above), and the product may simply have never registered a
clean-shutdown hook for this codepath -- worth a maintainer's attention at
some point, but this milestone tested exactly two termination methods on
one platform and does not treat that as a conclusive investigation.

### 3.7 One real, disclosed, non-release-blocking Doctor defect

**Found incidentally** while following this milestone's own participant
materials' own advice (running Doctor during first use) against a freshly
-booted, wizard-incomplete instance.

**Symptom:** `python -m mockingbird doctor` reports `Storage: FAIL`,
"The configured media storage folder does not exist," `recoverability:
BLOCKING`, `Action: Create the configured storage folder, or check the
MOCKINGBIRD_MEDIA_ROOT/MOCKINGBIRD_HOME setting" -- on a completely normal,
nothing-actually-wrong, pre-wizard-completion instance. Overall Doctor
status: `UNHEALTHY`, exit code `2`.

**Root cause** (`src/mockingbird/diagnostics/doctor.py:755-787`,
`_interpret_storage`): the function has a deliberate, already-written
"nothing is wrong yet" branch --

```python
if not gathered.get("media_root_exists"):
    if not database_exists:
        return DoctorCheckResult(..., status=DoctorStatus.PASS,
            summary="The media storage folder has not been created yet.",
            detail="This is expected before MockingBird's first launch or "
                   "before any camera has been added.", ...)
    return DoctorCheckResult(..., status=DoctorStatus.FAIL,
        summary="The configured media storage folder does not exist.",
        recoverability=DoctorRecoverability.BLOCKING, ...)
```

-- gated on `database_exists = sqlite_database_path(environment.db_url)
.is_file()` (doctor.py:2290), a pure file-existence check. But the database
file is created at **server-process startup itself** (confirmed directly:
present, 909,312 bytes, immediately after this test's own first launch,
before any wizard interaction whatsoever), not at wizard/Storage-step
completion. The intended `PASS`/informational branch is therefore only
reachable in the narrow window before a user's server has ever started even
once -- which ends before the wizard's Storage step is reached, not after.
**Any participant who starts MockingBird and runs Doctor before finishing
first-run setup -- exactly what this milestone's own participant materials
ask them to try -- will see an alarming "genuine problem" `BLOCKING`
message during entirely normal setup.**

**Impact:** diagnostic-accuracy only. No data loss, no corruption, no
truth-boundary risk, no effect on any Gate A dimension. Fully self
-explanatory and non-destructive; a participant following the `Action` text
literally would not damage anything, only be confused.

**Disposition:** disclosed here, **not fixed** in this milestone -- per the
governing directive's own instruction to disclose rather than expand scope
for a non-release-blocking defect, and per this milestone's own bounded
"verify, do not change product features" mandate. Classified using the
existing Gate G findings-triage rubric (`release-gate-reconciliation-
external-acceptance-preparation-v1-report.md` §6): **Sev-2 -- fix before
launch, not release-blocking.** Recommended smallest correction for a
future bounded fix: gate the `PASS`/informational branch on whether the
first-run wizard's Storage step has completed (an existing, already
-tracked piece of state) rather than on raw database-file existence, or
equivalently treat "database exists but zero cameras/Sources configured
yet" as the same informational case as "database does not exist yet." Not
implemented here -- this is a proposal for the smallest corrective scope,
not a fix.

### 3.8 Privacy/secret handling, uninstall, and rollback (cited, not re-proven)

Three remaining directive-named proof points, each already established
against production code confirmed identical to this candidate (§1), so
re-proven only where fresh evidence was practical rather than repeated
wholesale -- consistent with "do not reopen an accepted milestone without
a reproduced defect":

- **Privacy and secret handling.** Camera/RTSP credentials remain stored
  plaintext at rest by documented, non-defect design; Camera Node pairing
  secrets remain hash-only; diagnostics are regression-tested to never leak
  either class of secret. This candidate's own fresh Tier 2 re-run (§9)
  includes `test_doctor.py` in full, covering the secret-redaction
  regression tests directly -- re-confirmed passing against this exact
  code, not merely cited. No camera was configured in this milestone's own
  bounded launch test (§3.4), so there was no live credential to inspect
  directly this session; the enforced sign-in requirement observed in
  §3.4 is itself a direct, fresh confirmation of the authentication
  boundary specifically.
- **Backup, recovery, and data-preserving uninstall.** Recovery-from
  -unclean-stop is freshly proven this session (§3.6). The uninstall
  procedure itself was proven on real native-Windows hardware by *External
  Acceptance Entry Readiness & Uninstall Closure v1* (stop-before-delete
  enforced by a real Windows file lock; deleting the application folder
  alone preserves data; a fresh unpack anywhere reconnects to preserved
  data; the explicit destructive step removes both) against code this
  candidate's own build (§3.1) confirms is unchanged -- not re-run
  destructively here, since nothing in the production uninstall path could
  have changed.
- **Rollback.** Schema is unchanged (`v59`); this candidate involves no
  migration to roll back from, so rollback was not exercised live this
  session. The underlying mechanisms remain accepted and freshly
  re-confirmed passing in this session's own Tier 2 run (§9):
  `test_upgrade_path_acceptance.py` (Host automatic pre-migration backup +
  post-migration health check) and the Camera Node upgrade-path tests
  within `test_install_camera_node.py` (preflight, staged activation,
  automatic restore-on-failed-health-check, including the two small,
  already-disclosed Lane L residuals that remain unchanged and out of this
  milestone's scope).

### 3.9 Nonredistribution of restricted BirdNET weights

Confirmed directly against this exact candidate build, not only cited as a
standing property. `verify_no_nc_licensed_acoustic_model_redistribution`
(`scripts/build_local_product.py:1718`) is called unconditionally inside
`assemble_windows_bundle` (line 1918, not behind any flag) and raises
`LocalProductBuildError` on failure -- the build in §3.1 completed with no
error, so the guard passed. Independently, a direct filesystem search of
the built bundle (`python/site-packages/`) found exactly one BirdNET
-related match: `mockingbird/species/birdnet_adapter.py` -- MockingBird's
own MIT-licensed integration code, not a model file. `birdnetlib` itself
(the pip package that would carry the CC BY-NC-SA 4.0 model weights) is
**absent** from the bundle entirely, confirming the optional
`classifier-birdnet` extra is correctly not part of the default packaged
product. No BirdNET model weight of any kind is present anywhere in this
candidate.

---

## 4. Participant materials

Prepared as a standalone companion document -- concise, practical, and
grounded only in already-governed facts:
[external-pre-release-acceptance-private-cohort-v1-participant-materials.md](external-pre-release-acceptance-private-cohort-v1-participant-materials.md).

All nine required materials are present:

1. Private invitation draft (placeholder recipient/contact; not sent).
2. Written consent/participation agreement (explicit written opt-in, per
   the operating decisions in §2).
3. Installation and system-requirement instructions.
4. First-run and first-use task guide (including the accepted ~80-115s
   typical latency disclosure).
5. Correction/evidence-trust task guide (Measured/Inferred/Reviewed
   truth boundary made explicit; "sticking" corrections framed as the
   single most serious finding class).
6. Backup, recovery, and uninstall instructions (matching `using-
   mockingbird.md`'s own now-closed uninstall contract verbatim).
7. Known limitations and support boundaries (GPU requirement, latency,
   sustained/crowded recall limitation, plaintext credentials, Privacy
   Zone scope, BirdNET licensing, out-of-scope capabilities).
8. Findings submission template (channel left as an explicit owner
   decision, per §13 of the reconciliation report's findings-triage
   contract).
9. Participant withdrawal and data-handling instructions.

**What these materials do not promise**, matching the governing
directive's explicit constraint: no guaranteed species identification, no
numeric latency SLA, no cloud dependency, no surveillance/security
-alerting capability. Measured/Inferred/Reviewed truth is made explicit in
the first-use and correction guides specifically, not only asserted in
doctrine text.

**Not done under this section, per the governing directive:** no
participant contact, no personal-data collection, no account creation, no
recruitment-channel selection.

---

## 5. Owner approval checkpoint -- STOP

Per the governing directive's §5, this milestone stops here. **The
following require explicit owner approval before any external action is
taken.** Nothing below is authorized by this milestone or self
-authorized by any companion document.

| # | Item | Current state | What the owner must decide |
|---|---|---|---|
| 1 | Named participants or recruitment channel | Proposed: direct trusted contacts or relevant birding/nature communities; 3-5 participants; no public announcement (§2) | Approve this channel/shape, or specify exact participants |
| 2 | Invitation and consent materials | Drafted in full (§4, participant-materials document §§1-2) | Approve exact wording, or request changes |
| 3 | Candidate build identity and distribution method | Built and verified this milestone (§3): `git_commit 2fe27292e73a1dab9dcf71fa00bc004a3cd8e83d`, `zip_sha256 36b9668b...`, on disk at `dist/mockingbird-gate-g-candidate-2fe2729/` (git-ignored, not distributed) | Approve this exact candidate for distribution, and how it reaches a participant (direct private link + checksum, per the installation instructions' own placeholder) |
| 4 | Private findings channel and access controls | Proposed shape: private-repository issue process or existing owner-controlled mechanism, participant information restricted (§4, item 8) | Designate the specific channel |
| 5 | Exit-decision rules, if not already governed | Already governed qualitatively (Gate G plan §14); no numeric severity/count formula exists | Approve the qualitative approach, or supply a specific formula |
| 6 | Support and withdrawal arrangements | Drafted (participant-materials document §§7, 9): owner is sole support contact; withdrawal is unconditional and immediate | Confirm, or name a delegated triager |

**This milestone does not interpret its own authorization as blanket
permission** to send messages, create accounts, expose repository access,
or distribute software to any recipient. Sections 6 ("Acceptance
execution") and 7 ("Findings and exit") of the governing directive are
**not performed** -- there is no participant evidence to report, and this
report does not fabricate any.

---

## 6. What was not done, stated plainly

Matching the governing directive's own repeated instruction:

- No participant was contacted, recruited, or named.
- No account, private-repository access, or findings channel was created.
- No build was distributed to anyone outside this sandbox.
- No Gate G task from the governing plan's §§5-12 (onboarding, correction,
  multi-camera, install/update/recovery/backup at participant hands,
  privacy/consent comprehension by an actual person, diagnostics/support
  experience by an actual person, performance/stability over days) was
  run against a real participant -- only this milestone's own internal
  candidate verification (§3), which is explicitly not a substitute for
  independent participant evidence.
- Gate G is **not** marked started, executed, or passed.
- Final Release Hardening is **not** marked started or authorized.
- Gate A is **not** reopened -- the one defect found (§3.7) is a Doctor
  diagnostic-wording gap, not a Gate A dimension (recall, false-Visit
  rate, fragmentation, duplicates, useful-evidence, evidence-loss,
  monitoring coverage, latency all remain exactly as previously accepted).
- No product, schema, or tooling code was changed.
- No push was made.

---

## 7. Findings ledger (from this milestone's own internal verification)

Using the exact intake -> reproduce -> severity -> owner -> correction ->
validation -> accept/reject/defer -> acceptance-decision workflow already
governed (`release-gate-reconciliation-external-acceptance-preparation-v1-
report.md` §6), applied here to this milestone's own internal candidate
-verification findings rather than participant reports, since none exist
yet:

| # | Finding | Severity | Reproduced | Disposition |
|---|---|---|---|---|
| 1 | Doctor's Storage check reports `FAIL`/`BLOCKING` on a normal, pre-wizard-completion fresh instance (§3.7) | Sev-2 -- fix before launch, not release-blocking | Yes, directly, on real native-Windows hardware, with root cause identified in source | Deferred -- recommended smallest fix proposed (§3.7); not implemented in this bounded milestone |
| 2 | Doctor's Application check reports `WARN` "did not shut down cleanly" after *every* stop method tried (forceful `Stop-Process` and non-forceful `taskkill`) -- both are exactly the product's own only documented stop paths | Sev-3 -- informational, non-blocking; worth a maintainer's attention, not urgent | Yes, twice, two different termination methods, same result | Disclosed, not actioned -- honest/calm message, zero data risk (byte-identical DB proven across restart, §3.6), no accepted budget touched; not investigated further beyond the two documented stop methods |

No Sev-0 or Sev-1 finding was produced. No accepted Gate A budget,
denominator, or limitation was touched, contradicted, or re-litigated by
either finding above.

---

## 8. Documentation delta

- `docs/external-pre-release-acceptance-private-cohort-v1-report.md` --
  this report (new).
- `docs/external-pre-release-acceptance-private-cohort-v1-participant-
  materials.md` -- the nine required participant materials (new).
- `docs/release-execution-state.md` -- dated, additive entries recording
  this milestone (top-of-file `CURRENT PHASE`; §3; §6.S), matching this
  file's own established three-place convention. No historical text
  edited or removed.

**Not changed:** any product, schema, or tooling code; `roadmap.md`;
`using-mockingbird.md`; `THIRD_PARTY_NOTICES.md`; the Gate G plan document
(its own existing 2026-09-08 addendum already covers the same proposed
cohort/consent/intake shape this milestone reuses -- no second, competing
proposal was written).

**Build artifact disposition:** `dist/mockingbird-gate-g-candidate-
2fe2729/` (the built, independently-verified candidate: zip, manifest,
`SHA256SUMS`, and the unpacked tree) remains on local disk, `git`-ignored,
**not distributed to anyone**. The Windows-side disposable copy used for
launch verification (`C:\Temp\mockingbird-gate-g-candidate\`) and its
disposable data home were deleted at the end of verification (§3),
matching the established disposable-instance cleanup convention; real
production/dev data (`%LOCALAPPDATA%\MockingBird`,
`%LOCALAPPDATA%\MockingBirdDev`, `C:\MockingBirdDev`) was never touched by
this milestone.

---

## 9. Validation

**Fresh, this-session re-confirmation** of every directly-relevant test
file (not merely cited from a prior report), against the unchanged
production code this candidate is built from:

| Suite | Result |
|---|---|
| `tests/test_single_app_runtime.py` | 21 passed |
| `tests/test_local_product_packaging.py` | 85 passed (268.7s, including the real network/hash-backed tests) |
| `tests/test_version_provenance.py` + `tests/test_verify_release_artifact.py` | 17 passed |
| `tests/test_deploy_windows_dev.py`, `test_install_camera_node.py`, `test_camera_node_packaging.py`, `test_local_backup_recovery.py`, `test_cross_install_backup_restore.py`, `test_clean_install_acceptance.py`, `test_upgrade_path_acceptance.py`, `test_doctor.py` | 384 passed (64.7s) |
| **Total** | **507 passed, 0 failed** |
| `ruff check` (build/verify/runtime-identity files) | Clean, zero findings |

Numbers reconcile exactly with *External Acceptance Entry Readiness &
Uninstall Closure v1*'s own prior Tier 1/2 count (494 = 106 + 388), split
slightly differently here only because `test_version_provenance.py` was
run alongside `test_verify_release_artifact.py` rather than the Tier 2
list -- same suites, same result, zero regressions, confirmed fresh this
session rather than only cited.

**Full Core: not run, deliberately, matching this project's own
established Tier 3 discipline.** This milestone changed zero product/
schema/tooling code (its only artifacts are two new documentation files
and a build-owned `dist/` output already excluded from version control);
a Core run would not exercise anything a Core run over the immediately
-prior, already-fully-Core-clean milestone did not already cover, and
would not have exercised the real Windows launch/recovery/Doctor evidence
in §3, which is what actually bears on this milestone's own claims.

---

## 10. Remaining owner decisions / blockers

Consolidated from §5, unchanged in substance from the Gate G plan's own
consolidated list, carried forward rather than re-invented:

1. **The actual go/no-go for external action** -- send an invitation,
   create an account, distribute the verified candidate, or enroll a
   participant (§5).
2. Exact participant identities and recruitment channel, if different
   from the proposed shape (§5, item 1).
3. Sign-off on the exact invitation/consent wording (§5, item 2).
4. The private findings-intake channel designation (§5, item 4).
5. Any numeric onboarding-time or exit severity/count target, if the
   owner wants one beyond the governed qualitative criteria -- none
   invented here or in any prior milestone.
6. The standing BirdNET commercial-adjacent legal review -- unchanged,
   no engineering action available, does not block this milestone or Gate
   G's own start.
7. Whether/when to fix the Sev-2 Doctor Storage-check finding (§3.7, §7)
   before Gate G participants actually see it -- an owner-schedulable,
   non-blocking item, not a Gate G entry blocker.

---

## 11. Classification

**A** -- a complete, bounded milestone with no residual gap in its own
authorized scope. The verified baseline matched the governing directive's
own expectation exactly, requiring no reconciliation. A real, current,
independently-verified internal acceptance candidate was built and proven
on real native-Windows hardware -- exact build identity (`git_commit`,
`build_id`, every model/asset SHA-256) confirmed three independent ways
(the manifest, the independent verifier, and the running instance's own
self-report), not merely asserted. Recovery after an unclean stop was
proven, not assumed. One real, reproducible, non-release-blocking defect
was found during this verification and is disclosed precisely, with root
cause and a proposed smallest correction, rather than smoothed over or
silently fixed outside this milestone's bounded scope. All nine required
participant materials are complete, internally consistent with the
product's own governed facts, and correctly avoid every promise the
governing directive prohibits. The owner approval checkpoint is presented
completely, with every item the directive requires, and this milestone
correctly stops there -- no participant contacted, no build distributed,
no account created, no Gate G execution performed, no findings fabricated.
507 tests pass fresh this session with zero regressions; `ruff` clean on
every file this milestone's own verification touched. No product, schema,
or tooling code changed. No push. All seven preserved untracked detector
files remain untouched.

**At closure:**

**FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING**

**Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED`**, returned exactly as required, for the next external
(ChatGPT) acceptance review to act on -- specifically, the owner approval
checkpoint in §5, above.

---

*Prepared as a bounded Gate G setup milestone. No participant was
contacted or recruited. No build was distributed externally. No account or
private-repository access was created. No product, schema, or tooling
logic was changed. No push was made.*
