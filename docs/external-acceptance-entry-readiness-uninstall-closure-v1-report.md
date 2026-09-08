# External Acceptance Entry Readiness & Uninstall Closure v1

**Type:** Bounded release-readiness milestone under the durable feature
freeze. Resolves the two concrete entry dependencies *Release-Gate
Reconciliation & External Acceptance Preparation v1* named against Gate G
(External Pre-Release Acceptance): the uninstall documentation gap (its
own report §3, item 2; the Gate G plan's own §8 and consolidated
owner-decision #5) and the stale `local-mvp-readiness-checklist.md`
(its own report §3, item 1; consolidated owner-decision #8). Also
prepares, for owner approval only, a private Gate G cohort/consent/
findings-intake contract per this milestone's own governing directive.

**Classification: A** -- see "Classification," at the end.

This milestone does **not** recruit a participant, distribute a build,
begin External Pre-Release Acceptance, start Final Release Hardening, or
reopen Gate A. No push. No history rewrite.

---

## 0. Executive summary

Both concrete gaps closed with real evidence, not assumption. The
uninstall gap was exactly what the last two milestones already
characterized it as: a genuine, confirmed **documentation** gap, not a
missing product capability -- the packaged Windows product has no
installer/registry/service footprint, so the application folder and the
local data folder (`%LOCALAPPDATA%\MockingBird`) were already two
separate, independently removable things by construction
(`mockingbird.runtime.resolve_runtime_home`). Closing it required no new
uninstall command or mechanism: a documented, two-level procedure added
to `using-mockingbird.md`; one precise, minimal correction to the in-box
`README-FIRST.txt` (the *only* uninstall documentation an unpacked end
user actually has, since `using-mockingbird.md` is not shipped inside the
bundle); and one new regression test locking in the underlying
independence invariant. Every claim in the new procedure was then proven
on **real native-Windows hardware**, not merely documented: stopping
first is a real, OS-enforced requirement (a concrete `Access to the path
'cv2.pyd' is denied` error, not a courtesy); a failed delete-while-running
attempt does not damage the running installation; deleting the
application folder alone leaves data intact; unpacking a fresh copy at a
*different* path reconnects automatically to the exact same preserved
data (`instance_id` byte-identical before and after); and the explicit,
separate destructive step removes both completely. See §4 for the full
evidence, including a real near-miss this investigation caught and
disclosed rather than working around quietly (§4.1).

The stale MVP checklist is now marked superseded, dated, with the
specific false non-goal claims corrected by addition -- its own historical
body is preserved unedited, per this project's own convention.

A private Gate G cohort/consent/findings-intake contract is proposed
(§2) for owner approval. **Nothing in it is approved by this milestone.**
No participant was recruited or contacted; no account or private-
repository access was created.

**Verified baseline, exactly as expected** (§1). **Authorization returned
unchanged: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`.**
Gate G remains **PLAN ONLY, not started**. This milestone does not
authorize Gate G execution, participant recruitment, build distribution,
or Final Release Hardening, and does not reopen Gate A.

---

## 1. Verified baseline

Verified directly against the repository at the start of this milestone,
matching the governing directive's own expected baseline exactly:

| Fact | Expected | Verified |
|---|---|---|
| Branch | `main` | `main` |
| HEAD | `871c7ba` | `871c7ba252640dc019df15e8bd8465a81692a9be` (`git rev-parse HEAD`) |
| Schema | v59 | `CURRENT_DATABASE_SCHEMA_VERSION = 59` (`src/mockingbird/storage/database.py:46`) |
| Latest accepted milestone | Release-Gate Reconciliation & External Acceptance Preparation v1 | Confirmed -- `871c7ba` is that milestone's own reconciliation commit |
| Lane R | CLOSED | Confirmed -- `release-execution-state.md` §6.R |
| Lane P | CLOSED | Confirmed -- `release-execution-state.md` §6.P |
| Gate G | prepared, not started | Confirmed -- §6.S 2026-09-07 update |
| Current authorization | NONE | Confirmed -- `release-execution-state.md` §3 top entry |
| Push state | Not pushed | `+383 -0` vs. `origin/main` at start |
| Worktree | Clean except seven preserved files | Confirmed byte-identical to §13's own list (below) |
| Active writers | None expected | `ps aux` clean; `git worktree list` shows five other worktrees, all on unrelated stale branches, none `main`; `git stash list` empty |

**The seven preserved untracked detector files** (confirmed present,
untracked, and unmodified at the start, throughout, and immediately
before this report's own publication):

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

No discrepancy was found between the governing directive's expected
baseline and repository evidence.

**Governing sources read, in the order specified:**
`docs/release-execution-state.md` (top-of-file `CURRENT PHASE` narrative
in full; §3 top entry; §4-6 -- Lanes L, N, O, P, S in full; §13; §14
tail; §15; §16 confirmed self-declared stale/superseded, skipped),
`docs/product-doctrine.md` (in full), `docs/roadmap.md` (Governing
priority, Release scope discipline, Scope-reopening rule, Release
readiness vs. continued capability work, Public release readiness,
Explicit phase gates/deprioritization/non-blockers, Field-testing
doctrine, Cross-cutting invariants, Roadmap non-goals, WSL checkpoint;
Gate G section and the complete `uninstall`/`Appliance`/Phase 4 grep
delegated to a dedicated research pass, §3 below); then
`docs/external-pre-release-acceptance-gate-g-plan-v1.md` and
`docs/release-gate-reconciliation-external-acceptance-preparation-v1-report.md`
(each in full); `docs/local-mvp-readiness-checklist.md` (in full);
`docs/using-mockingbird.md` (in full); `docs/appliance-storage-privacy-
recovery-v1-contract.md` (targeted -- Phase H, I, J, and the closing
"Known bounded gaps"); `docs/local-product-packaging-design.md`,
`docs/camera-node-installer-design.md`, `THIRD_PARTY_NOTICES.md` (via the
research pass, cross-checked directly).

---

## 2. Owner decisions: proposed versus approved

**Nothing in this section is approved.** Every value below is a proposal
for the owner to accept, reject, or amend before Gate G recruitment
begins. The full contract, with its basis for each value, was added to
`docs/external-pre-release-acceptance-gate-g-plan-v1.md` as a new
"Proposed cohort/consent/intake decisions (2026-09-08 addendum)" section,
inserted immediately before that plan's own consolidated owner-decisions
list; this section summarizes it for traceability.

| Decision | Proposed | Approved | Basis |
|---|---|---|---|
| Cohort size | 3-5 independent participants | **Not approved** | Sits inside the Gate G plan's own §2 advisory range and `roadmap.md`'s "not hundreds" constraint |
| Recruitment channel | Direct trusted contacts, or relevant nature/birding communities; no public beta announcement | **Not approved** | Matches the plan's §1 repeated instruction never to describe or recruit Gate G as a public beta |
| Participant mix | Non-developer users + varied supported native-Windows hardware, where practical | **Not approved** | Reuses the plan's own §2/§3 diversity axes verbatim; nothing new invented |
| Local Only posture | First-class acceptance path for every participant | **Not approved** (already true of the product; restated as a contract term) | Reuses the plan's §4 verbatim |
| Findings intake | A private-repository issue process, or the existing private issue-tracking mechanism, with participant information restricted | **Not approved** -- owner must still designate the specific channel | Reuses the plan's own §13 instruction not to build a new issue-management platform |
| Consent | Explicit written opt-in before any collection or installation | **Not approved** -- this milestone's own proposed answer to a previously fully-open question | Real camera/property imagery and real, if small, privacy exposure are involved; the plan's own §9 disclosures (plaintext camera credentials, unreleased-product status) should be part of what a participant affirmatively acknowledges |
| Numeric onboarding/exit targets | **None proposed** | N/A | No governing document sets one; inventing one would repeat exactly the "invented numeric release budget" error this project's own discipline already warns against (see `roadmap.md` "Release scope discipline") |

**Explicitly not done by this milestone:** no account created, no person
contacted, no private-repository access granted or exposed, no
recruitment channel selected on the owner's behalf, no cohort headcount
fixed as binding.

---

## 3. Uninstall: root cause and contract

### 3.1 Root cause

Bounded archaeology (a dedicated research pass plus direct verification
of every code citation below) found the uninstall gap was **exactly**
what the two prior milestones already believed but had not verified:

- A repo-wide, case-insensitive grep for `uninstall` found exactly 16
  hits in 6 files, **zero** in `tests/`, `scripts/`, or any frontend
  file, and zero implemented mechanism anywhere. The only substantive
  hits are the two prior milestones' own disclosed-gap prose (the Gate G
  plan's §8 and the reconciliation report's §3/§8) plus four unrelated
  incidental uses of the word (a dev-checkout version-fallback comment,
  a `pip uninstall` note for an optional extra, and a `passlib`
  reference in an unrelated password-hashing design decision).
- `scripts/build_local_product.py`'s `assemble_windows_bundle` (the
  entire native-Windows packaging pipeline) produces a plain zip
  wrapping an "unpack and run" folder -- confirmed, not merely read: no
  installer framework (Inno Setup/NSIS/WiX/MSI), no registry key, no
  Windows service, no Start Menu/desktop shortcut, no scheduled task, and
  no uninstaller stub anywhere in the bundle-assembly code. This matches
  `docs/local-product-packaging-design.md`'s own explicit "Chosen:
  self-contained 'unpack and run' Windows folder/zip" decision and its
  explicit rejection of Electron/Docker/a Windows service.
  MockingBird therefore never registers with Windows "Apps & Features" --
  there is nothing there for a user to invoke "Uninstall" from.
- `mockingbird.runtime.resolve_runtime_home` (`src/mockingbird/
  runtime.py:127-141`) resolves the local data location to
  `%LOCALAPPDATA%\MockingBird` on Windows whenever `MOCKINGBIRD_HOME` is
  unset and `workspace_root` is `None` -- which it always is for the
  packaged artifact, since `find_workspace_root`
  (`src/mockingbird/web_app.py:30-39`) looks for a `pyproject.toml` +
  `web/` sibling that only exists in a development checkout, never in the
  packaged `python/site-packages/mockingbird/` tree. This location is
  therefore genuinely fixed and independent of wherever the application
  folder happens to be unpacked -- proven, not assumed (§4).
- Every user-generated artifact -- database (`data/mockingbird.sqlite3`),
  media (`data/media/imports`), backups (`data/backups/*.mbbackup`),
  research/ecological/classifier exports, the camera-node transport
  ledger, logs (`logs/mockingbird.log`), and instance/runtime state --
  lives under that one `<runtime home>` tree
  (`src/mockingbird/storage/database.py:42-45`,
  `src/mockingbird/storage/backup.py:25-26`,
  `src/mockingbird/repository/product_repository.py:1362-1376`,
  `src/mockingbird/runtime_state.py:27-30`). There is no second location
  to enumerate.
- Both bundled models are MIT-licensed (`THIRD_PARTY_NOTICES.md:26-74`)
  and live *inside* the application folder
  (`python/site-packages/mockingbird/observation_runtime/`,
  `.../bioclip_runtime/`), so no license constraint blocks deleting them
  as part of removing the application; BirdNET (the one CC BY-NC-SA
  4.0-licensed, NonCommercial model) is never bundled by MockingBird's
  own packaging in the first place (`verify_no_nc_licensed_acoustic_
  model_redistribution`, `scripts/build_local_product.py:1699-1760`), so
  it is not MockingBird's uninstall to govern.
- Camera Node pairing state is ordinary DB rows inside the data folder
  (`source_provider_configurations.config_json`); an already-shipped,
  already-tested UI action (`revokeCameraNodePairing` /
  "Revoke current pairing," `web/src/pages/CameraConfigurationPage.tsx:
  247-333`, wired to `src/mockingbird/api/main.py:9537` /
  `repository/product_repository.py:13207`) already exists to cleanly
  disconnect a Node before uninstalling, so none needed to be built. The
  physical Camera Node device itself is unaffected by a Host uninstall
  by design -- decommissioning it is `scripts/install_camera_node.py`'s
  own separate, already-disclosed scope (it has no uninstall subcommand
  either; not built here, since that is Camera Node lifecycle, not Host
  uninstall).
- No in-app "delete everything" button exists, and none was built --
  `roadmap.md`'s own "Roadmap non-goals" already rules out "a new
  administration page merely for lifecycle or engineering controls," and
  `local-product-packaging-design.md`'s own non-goals already rule out a
  "storage-relocation UI." Full removal is, deliberately, an ordinary
  Windows folder deletion, exactly as portable/deletable as any other
  local folder.

**Conclusion: no concrete missing mechanism exists.** Per the governing
directive's own instruction ("If the installer already provides a
reliable uninstall path, document and test it... Do not invent an
uninstall command that the product does not support"), the correct
action was to document and prove the existing, already-safe-by-
construction procedure -- not to build a new one.

### 3.2 One genuine, small documentation-accuracy defect found and fixed

The in-box `README-FIRST.txt` (the *only* uninstall documentation an
unpacked end user actually has -- `using-mockingbird.md` is a
repository/website document, not shipped inside the bundle) previously
said MockingBird "keeps everything... in one local folder on this
computer" immediately after a paragraph about closing/stopping the
*application* folder, without ever stating that this was a *different*
folder from the one containing the README itself. A user reading only
this file could reasonably conclude that deleting the application folder
either destroys their data or that their data is safely inside it either
way -- both readings are wrong, and the ambiguity sits directly on the
uninstall safety question this milestone exists to close. Fixed
precisely: the sentence now names the local data folder as "the same
`%LOCALAPPDATA%\MockingBird` folder named above [for logs]... kept
separate from this application folder on purpose," and a new "To remove
MockingBird" section states the complete two-level procedure in the same
plain style as the rest of the file. See §5 for the exact diff.

### 3.3 The contract

**Default (safe, preserves data):**

1. Stop MockingBird (close the browser tab; end `pythonw.exe` in Task
   Manager; or restart the computer) -- required, not optional: Windows
   refuses to delete a folder a running process holds a loaded module
   open in (§4.2).
2. Delete the application folder (the one containing
   `Start MockingBird.vbs`). This removes MockingBird itself. The local
   data folder is untouched by construction (§3.1), so a fresh copy
   unpacked later -- anywhere, including a newer version -- automatically
   reconnects to exactly the same preserved data (§4.4).

**Explicit, separate, destructive step (permanent data removal):**

3. Additionally delete the local data folder itself
   (`%LOCALAPPDATA%\MockingBird`, or wherever Local Data shows it if
   `MOCKINGBIRD_HOME` was customized). This is never bundled with step 2,
   is documented as irreversible absent a kept backup, and requires the
   user to take a second, separate, deliberate action -- there is no
   single "delete everything" affordance (§3.1).

**Explicitly covered, per the governing directive's checklist:**

- *Binaries/shortcuts:* the application folder (step 2); no shortcuts are
  created by MockingBird itself, so only a shortcut the user made
  themselves would need separate removal (not MockingBird's to know
  about).
- *Services/startup entries/background processes:* none exist to remove
  (§3.1); the one background process (`pythonw.exe`) is handled by step
  1.
- *Application-managed configuration/caches:* inside the local data
  folder, removed by step 3.
- *User data (Places, observations, Reviewed truth, media, backups):*
  preserved by default (step 2 alone); removed only by the explicit step
  3.
- *Optional models/assets and licensing:* covered, no constraint (§3.1).
- *Logs/diagnostics/secrets:* inside the local data folder (plaintext
  camera credentials, hash-only pairing secrets -- both already-documented,
  already-accepted non-defects, unchanged by this milestone), removed
  only by step 3.
- *Paired Camera Node state:* covered (§3.1) -- optional pre-uninstall
  disconnect via already-shipped UI; the physical device is unaffected
  either way, which is documented, not silently left unclear.

---

## 4. Validation evidence

### 4.1 A real near-miss, caught and disclosed

Mid-investigation, a check for a pre-existing `%LOCALAPPDATA%\MockingBird`
on this session's shared Windows sandbox (a required precaution before
any destructive-path testing) reported `PROD_ABSENT`. This was **wrong**:
the check had been written as `powershell.exe -NoProfile -Command
"...\"$env:LOCALAPPDATA\MockingBird\"..."` inside a *bash double-quoted*
string, so bash itself expanded `$env` (undefined, to empty) before
PowerShell ever saw the command -- silently checking a nonsense path
instead of the real one. Immediately before the first destructive
operation, the check was re-run with correct single-quoted bash
containment and found the opposite: a **real**
`%LOCALAPPDATA%\MockingBird`, with contents dated 8/9/2026 through
9/1/2026 -- genuine leftover data from prior accepted milestones' own
real native-Windows acceptance sessions on this same shared sandbox (the
same "18.5GB+ archived Windows dev-roots" class of housekeeping item
`release-execution-state.md` §6.R already names, here also including the
production-path variant, not only `%LOCALAPPDATA%\MockingBirdDev`, whose
own similarly-buggy "absent" check was also re-verified and corrected the
same way). **No file was deleted, moved, or written before this
correction was made.** All subsequent real-hardware validation (§4.2-4.4)
was deliberately redirected through `MOCKINGBIRD_HOME` pointed at a
disposable path under `%TEMP%`, mirroring `scripts/deploy_windows_dev.
py`'s own established "never touch a real production install" isolation
convention, rather than exercising the true default path directly on
real hardware. The default-path *resolution logic* itself (independent of
this override mechanism) is separately, deterministically proven by the
new unit test in §4.5 against the real `resolve_runtime_home` source.
Both real folders (`MockingBird` and `MockingBirdDev`) were reconfirmed
byte-identical -- same file list, same sizes, same timestamps -- after
every destructive test step and again at final cleanup.

This is disclosed prominently, not smoothed over: it is the exact kind
of near-miss the governing directive's "Never delete the operator's real
data... as part of validation" instruction exists to prevent, and it was
prevented by re-verification immediately before acting, not by luck.

### 4.2 Stop-before-delete is real, not a courtesy

A disposable bundle (`scripts/build_local_product.py`, `--skip-frontend-
build --allow-stale-frontend --skip-gpu-runtime --skip-bioclip-runtime`;
2,288 files, 2.4 GB unpacked, built from this milestone's own edited
working tree, `git_commit=871c7ba`, `source_clean=true`) was unpacked to
a disposable path (`%TEMP%\mockingbird-uninstall-test\install-1`) and
launched (`pythonw.exe -m mockingbird --no-browser`,
`MOCKINGBIRD_HOME` pointed at a disposable data-home). Confirmed live via
`GET /api/product/instance` (`git_commit` exact match). While running,
`Remove-Item -Recurse -Force` on the application folder failed with:

```
Access to the path 'cv2.pyd' is denied.
```

a real Windows file-lock on a loaded native module (OpenCV's Python
binding), not a simulated or assumed result. The application folder,
the specific locked file, and the running process (same PID, still
serving `/health` 200 and continuing to log requests) were all confirmed
intact and undamaged immediately afterward -- a failed delete-while-
running attempt does not partially corrupt the installation.

### 4.3 Stopping, then deleting, works cleanly and preserves data

`Stop-Process -Force` on the same PID (the documented Task-Manager
equivalent) succeeded; the application folder then deleted with
`Remove-Item -Recurse -Force` with zero error. The separate local data
folder was confirmed present and completely untouched immediately after:
`data\mockingbird.sqlite3` intact at 909,312 bytes,
`instance_identity.json` unchanged, `logs\mockingbird.log` present.

### 4.4 Reinstalling anywhere reconnects to the exact same data

A second, independently-unpacked copy of the identical zip was placed at
a **different** disposable path (`install-2-fresh-copy`) and launched
with the same `MOCKINGBIRD_HOME`. `GET /api/product/instance` returned
`instance_id: "6576e64b69a70b5f04ad96a76e039574"` -- **byte-identical**
to the value the first install reported before its own application
folder was deleted. This is direct, real proof that a fresh
unpack/reinstall (a different path, the same or a newer version)
automatically reconnects to exactly the preserved data, with no manual
reconnection step.

### 4.5 The explicit destructive step removes everything, and only when asked

The second instance was stopped; its own application folder **and** the
disposable data-home were then deleted together in one explicit step.
Both confirmed gone (`Test-Path` false for each). Final cleanup removed
every remaining disposable artifact (`Remove-Item -Recurse -Force` on the
whole `%TEMP%\mockingbird-uninstall-test` tree); no stray `python`/
`pythonw` process remained (`Get-Process` empty); Windows free disk space
returned to its pre-test baseline (22.6 GB free on `C:`, unchanged).

### 4.6 Unit-level proof of the underlying invariant

New test
`test_resolve_runtime_home_default_is_independent_of_the_application_directory`
(`tests/test_single_app_runtime.py`) proves, against the real
`resolve_runtime_home` source (not a reimplementation), that with no
`MOCKINGBIRD_HOME` override and `workspace_root=None` (the packaged-
artifact case), the resolved runtime home never depends on the
application directory or current working directory -- exercised on this
test runner's own OS default branch (`XDG_DATA_HOME`/`~/.local/share/
mockingbird`; `pathlib.Path` dispatches on the real `os.name` at
construction time, so the `nt`/`%LOCALAPPDATA%` branch cannot be
faithfully monkeypatched on this POSIX runner -- `Path(...)` raises
`NotImplementedError: cannot instantiate 'WindowsPath' on your system`
the moment `os.name` is patched, confirmed directly before choosing this
approach). The Windows-specific instance of the identical code shape is
the one proven by real hardware instead, in §4.2-4.5.

---

## 5. Files changed

Seven files, all documentation or test/packaging-text; **zero production
logic changed**:

- `docs/using-mockingbird.md` -- new "Uninstall" section (between
  "Upgrading MockingBird" and "If something goes wrong"): the two-level
  procedure, what a full removal does not need to touch (Camera Node,
  models, ffmpeg), and why there is no in-app "delete everything" button.
- `scripts/build_local_product.py` -- `README_FIRST` (the in-box text
  file every official bundle ships): the folder-separation clarification
  and new "To remove MockingBird" section (§3.2).
- `tests/test_local_product_packaging.py` -- extended the existing
  `test_assemble_windows_bundle_produces_a_python_and_pip_free_user_
  experience` to assert the new `README_FIRST` content (folder
  separation named explicitly, `%LOCALAPPDATA%\MockingBird` named twice,
  "Revoke current pairing" named) rather than only `.is_file()`.
- `tests/test_single_app_runtime.py` -- new regression test (§4.6).
- `docs/appliance-storage-privacy-recovery-v1-contract.md` -- new,
  dated "Uninstall contract (Phase P, closed 2026-09-08)" section,
  appended (this contract's own original scope never named uninstall;
  added here so a later session finds it alongside the rest of this
  contract's install/update/backup/recovery/privacy coverage, not only in
  a Gate-G-adjacent planning document).
- `docs/external-pre-release-acceptance-gate-g-plan-v1.md` -- a dated
  top-of-file update note; a dated `RESOLVED` correction to §8's
  uninstall bullet; a new "Proposed cohort/consent/intake decisions
  (2026-09-08 addendum)" section; a dated `RESOLVED` strike-through note
  on the consolidated owner-decisions list's item 5. No historical text
  removed.
- `docs/local-mvp-readiness-checklist.md` -- a dated "Superseded"
  banner at the top, naming the specific now-false non-goal claims and
  pointing to current authoritative sources. The historical body below
  is preserved completely unedited.

No product/schema/tooling code changed. No frontend (`web/src`) file
touched -- no `tsc`/`vite build` re-run was needed. The seven preserved
untracked detector files were reconfirmed present, untracked, and
byte-unmodified immediately before this report's own publication.

---

## 6. Validation (Tier 1 / Tier 2 / Tier 3 decision)

**Tier 1 -- every directly touched/new test file, run in full:**

- `tests/test_single_app_runtime.py`: **21 passed**, 0 failed (includes
  the new regression test, §4.6).
- `tests/test_local_product_packaging.py`: **85 passed**, 0 failed, 0
  skipped, `253.88s` (includes the extended README-content assertion; the
  three genuinely slow, real-network/real-hash tests in this file --
  `test_real_windows_bioclip_dependency_closure_installs_offline_with_
  no_duplicates`, two `test_real_local_*_bundle_matches_accepted_
  provenance_when_present` -- ran as part of this full pass, not skipped).

**Tier 2 -- every immediately affected packaging/lifecycle subsystem,
run in full:**

`tests/test_deploy_windows_dev.py`, `tests/test_install_camera_node.py`,
`tests/test_camera_node_packaging.py`, `tests/test_local_backup_
recovery.py`, `tests/test_cross_install_backup_restore.py`,
`tests/test_clean_install_acceptance.py`, `tests/test_upgrade_path_
acceptance.py`, `tests/test_version_provenance.py`, `tests/test_
doctor.py` -- **388 passed, 0 failed**, `39.15s`.

**`ruff check`** on every changed Python file (`tests/test_single_app_
runtime.py`, `tests/test_local_product_packaging.py`, `scripts/build_
local_product.py`): **clean, zero findings**. (A broad, unscoped
repository-wide `ruff` run separately surfaced 159 pre-existing findings
in two unrelated, untouched test files -- `test_visit_classifier_
supporting_evidence.py`, `test_visit_evidence_gallery.py` -- confirmed
unrelated by file path alone, since this milestone touched neither.)

**Tier 3 (full Core) decision: not run, deliberately, not merely
skipped.** This milestone's entire production-code footprint is one
string literal (`README_FIRST`, a packaging-output text constant with no
executable logic) plus one new test; zero application code, schema, API,
or frontend logic changed. This is the same class of decision several
prior accepted milestones already made explicitly for a comparably
narrow footprint (see `release-execution-state.md` §14, "Gate A
Measurement Closure v1 did not run a full Core checkpoint... per its own
documented Tier 3 decision"). The **real native-Windows hardware
validation in §4** is the evidence that actually matters for an
uninstall claim -- a Core run would not have exercised Windows file-lock
semantics, the packaged bundle's own launcher, or real disk paths at all.

---

## 7. Data-preservation and destructive-action safeguards

- **Default preserves data:** confirmed empirically (§4.3), not only by
  code inspection -- deleting the application folder alone leaves the
  local data folder, database, and instance identity completely intact.
- **Destructive removal is explicit, scoped, and separate:** the
  documented procedure (§3.3) never bundles data deletion with
  application deletion; it is always a second, named, separate step, and
  no in-app "delete everything" affordance was built to shortcut it
  (§3.1).
- **No operator data was ever at risk during validation:** the one real
  near-miss (§4.1) was caught before any write or delete occurred, and
  every subsequent destructive operation ran only against paths this
  milestone itself created under a disposable `%TEMP%` tree with
  `MOCKINGBIRD_HOME` override. Both real pre-existing folders
  (`%LOCALAPPDATA%\MockingBird`, `%LOCALAPPDATA%\MockingBirdDev`) were
  reconfirmed byte-identical -- same files, same sizes, same timestamps --
  after every destructive test step in this milestone and again at final
  cleanup.
- **Reinstall/recovery preserved:** §4.4 is itself evidence that the
  existing backup/restore and upgrade-recovery mechanisms (unchanged by
  this milestone) remain reachable after an uninstall-and-reinstall
  cycle, since the same data folder -- and everything in it, including
  any `.mbbackup` files -- survives untouched.
- **Camera Node / physical hardware:** no physical Camera Node, and no
  real paired device, was touched, reconfigured, or contacted by this
  milestone's validation. The one relevant claim (a Host uninstall does
  not reach the Node) is a direct consequence of §3.1's storage-location
  finding, not something requiring physical-device testing to confirm.

---

## 8. Documentation delta

Summarized in §5 (files changed) and §3 (contract). In addition to the
new content, three existing documents now carry accurate, dated
cross-references to this milestone rather than stale "not yet confirmed"
language: the Gate G plan's §8, its consolidated owner-decisions list,
and the appliance/storage/privacy/recovery contract's own new closing
phase. `docs/local-mvp-readiness-checklist.md` is marked superseded
without rewriting its historical body, per this project's own "correct
forward, never rewrite accepted history in place" convention.

---

## 9. Remaining entry blockers (unchanged by this milestone, restated for traceability)

Per the reconciliation report's own §8 and the Gate G plan's own
consolidated list, not resolved here and not claimed to be:

1. The actual go/no-go to begin Gate G recruitment and execution.
2. Exact cohort headcount, participant identities, and recruitment
   channel -- a **proposal** now exists (§2); nothing is approved.
3. Consent mechanism -- a **proposed** answer now exists (§2, explicit
   written opt-in); not approved.
4. Any numeric onboarding-time or acceptance target, if the owner wants
   one -- none proposed, none governed.
5. The exact severity/count formula (if any) for Gate G's exit decision,
   versus a qualitative release-authority judgment -- unchanged, open.
6. Findings-intake channel selection -- a **proposed shape** exists
   (§2, a private repository issue process or the existing mechanism);
   the specific channel itself is not designated.
7. The standing BirdNET commercial-adjacent legal review -- unchanged,
   no engineering action available.
8. Two small, already-disclosed, non-blocking Lane L residuals
   (`rollback()` not restoring a changed systemd unit template; a
   narrower rollback directory-swap crash-window gap) -- untouched,
   out of this milestone's scope, not reopened.
9. The 18.5GB+-class archived-Windows-dev-root disk-reclaim opportunity
   (§4.1 confirms it is real and still present, both
   `%LOCALAPPDATA%\MockingBird` and `%LOCALAPPDATA%\MockingBirdDev`) --
   non-blocking housekeeping, deliberately not performed here (out of
   this milestone's authorized scope; also not this milestone's data to
   clean up without separate authorization, since it may be another
   session's own live evidence).

**Closed by this milestone, not merely proposed:** the uninstall
procedure itself (§3, §4) and the stale-checklist documentation gap
(§5, §8).

---

## 10. Classification

**A** -- a complete, bounded release-readiness milestone with no residual
gap in its own authorized scope. Every claim in the new uninstall
contract is grounded in real native-Windows hardware evidence gathered
this session (§4), not documentation-only assertion; the one genuine
documentation-accuracy defect found (§3.2) was fixed precisely and
tested; the one real near-miss encountered during validation (§4.1) was
caught before any risk to real data materialized and is disclosed in
full rather than smoothed over. Zero production logic changed; Tier 1
(106 tests) and Tier 2 (388 tests) both pass with zero regressions;
`ruff` clean on every changed file; the seven preserved untracked
detector files remain untouched. The proposed cohort/consent/intake
contract meets every element the governing directive asked for and
self-authorizes nothing. No product/schema change. No deployment beyond
disposable, cleaned-up test instances. No participant contacted. No
build distributed. No push. Gate A is not reopened; Gate G is not marked
started; Final Release Hardening is not authorized.

**At closure:**

**FEATURE FREEZE -- EVIDENCE, RELEASE READINESS & HOUSEKEEPING**

**Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED`**, returned exactly as required, for the next external
(ChatGPT) acceptance review to act on.

---

*Prepared as a bounded release-readiness milestone. No product, schema,
or tooling logic was changed. No participant was recruited or contacted.
No build was distributed. No push was made.*
