# Internal Release Candidate Rebuild & Native-Windows Acceptance v1 -- Report

**Verdict: NOT ACCEPTED -- one release-blocker candidate reproduced on the
exact frozen candidate, with two further genuine defects; bounded correction
contract in §9. Authorization returns to `NONE`.**

The frozen candidate is intact, verifies independently, runs the accepted
models on the intended hardware, and completes the bounded product loop on
native Windows with real recorded field inputs. But the product's own
documented stop method -- **Shut down MockingBird** -- hung permanently in
both real-browser acceptance sessions on native Windows, and a closely
related defect in the same layer can leave the running product permanently
unreachable. Both are root-caused to the Windows Proactor event loop in the
bundled CPython 3.12.7. Neither was fixed here (non-goal); each has a
bounded proposed correction in §9. Nothing was pushed, tagged, signed,
published or distributed; no Gate G activity occurred.

## 1. Task packet (restated)

- **Roadmap phase:** release readiness (feature freeze); §3 of
  [release-execution-state.md](release-execution-state.md), this milestone's
  own authorization, steps (3)-(4). Steps (1)-(2) (freeze commit, artifact
  build) were completed in the prior session of this milestone.
- **Product flow improved:** none changed -- this milestone proves
  Observe -> Discover -> Understand -> Confirm -> Remember on the exact
  release candidate: install -> onboarding -> media setup/preview ->
  detector evidence -> Review Queue -> explicit correction -> Bird Log /
  Today truth -> shutdown/restart/recovery -> upgrade/backup/restore.
- **Why next:** the only authorized milestone; the handoff recorded
  native-Windows acceptance as pending.
- **Files allowed:** this report and the §3 closure delta of
  `release-execution-state.md`. No source, test, schema or build change.
- **Non-goals:** fixing any finding, rebuilding the candidate, product
  feature work, model evaluation, Pi changes, publishing, Gate G.
- **Validation tier:** Tier 1 artifact/provenance checks; Tier 2 focused
  packaging/verification/installation/upgrade/recovery suites; Tier 3 reuses
  the accepted Core baseline (source unchanged).

## 2. Starting state and integrity verification

| Item | Result |
|---|---|
| Repository | `/home/<user>/projects/mockingbird-active` (native WSL, not `/mnt/c`), branch `main` |
| HEAD | `661d0540ad6b832db47539232ec7b1cc6d2594e2` = frozen source SHA; worktree clean apart from the 8 protected untracked files; nothing staged |
| Protected files | all 7 detector files + `uv.lock` present, untracked, SHA-256 recorded at start and re-verified identical at end (§8) |
| Windows ZIP | `dist/internal-rc-rebuild-v1-661d054/MockingBird-windows-x64.zip`, SHA-256 `c63fea5a62eda5397651c3d492a392768ced6e2be921fa3f802ba18645c65645` -- matches the expected value, `SHA256SUMS`, `manifest.json.zip_sha256`, and a second, native `Get-FileHash` on the copy staged to Windows |
| `SHA256SUMS` (Host) | ZIP, `manifest.json` (`462cf45e…`), `sbom.json` (`c98ea04a…`) -- all OK |
| Host manifest | version `0.1.0`; `git_commit 661d054…`, `source_clean: true`, `build_id b4630af21a31c341`; MDv5a ONNX `b03ef796…` (source `fe3e90e4…`), GPU runtime + verified CUDA 13 DLL closure, BioCLIP-2 weights `b7b2bf6f…`, embedding cache `0260d5bb…`, labels file `b90cea20…`; CycloneDX 1.5 SBOM, 59 components; unsigned (`signing.requested: false`); 19,284 files, 4,923,707,741 bytes |
| Camera Node wheel | `mockingbird_camera_node-0.1.0-py3-none-any.whl`, SHA-256 `38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904` -- matches the expected value; every `SHA256SUMS` entry OK |
| Independent verifier | `scripts/verify_release_artifact.py` -> `OK: MockingBird-windows-x64.zip (19284 files, 4,923,707,741 bytes), version 0.1.0, source git:661d054…, unsigned` -- run against both the `dist/` copy and the copy staged on Windows |
| Camera Node independent check | all 19 wheel entries match `manifest.json.wheel_contents` by SHA-256 and size, no unlisted entries; all 15 `mockingbird_node/*.py` modules byte-identical to `git show 661d054:src/…`; the bundled `install_camera_node.py` byte-identical to `661d054:scripts/install_camera_node.py` |
| Windows host | no MockingBird process running at start; **nothing listening on port 8000** -- the field instance was not running and was never started, stopped, read or modified; RTX 4060 Ti, driver 610.62; free disk on `C:` ~23 GB (the product's own low-space warning fired honestly throughout) |

**Integrity passed; the candidate was reused, not rebuilt.**

## 3. Disposable instances

All instances ran from one native extraction of the candidate ZIP
(`C:\MBRC\rc\install\`, extracted with Windows' own `tar.exe` in 36.5 s;
19,284 files / 4,923,707,741 bytes, matching the manifest exactly), each
with an explicit disposable `MOCKINGBIRD_HOME` and a port other than 8000,
launched through the shipped `Start MockingBird.vbs` (`wscript`) with
`--port N --no-browser`.

| Instance | Home | Port | Purpose |
|---|---|---|---|
| `home-a` | `C:\MBRC\home-a` | 8123 | first pass -- **retired as environment-contaminated** (below) |
| `home-b` | `C:\MBRC\home-b` | 8125 | **the authoritative clean acceptance run** |
| `home-repro` | `C:\MBRC\home-repro` | 8124 | defect reproduction only |
| v59 seed | `C:\MBRC\up-v59-seed` | 8126 | v59 build (`C:\MBTestNew`, `039ce7d`) creating real v59 data |
| upgrade copies | `C:\MBRC\up-copy-1`, `up-copy-3` | 8127 | candidate migrating disposable copies of the v59 home |

**Environment contamination found and excluded.** The Windows user profile
carries persistent developer variables -- `MOCKINGBIRD_BIOCLIP_MODEL_PATH`/
`_LABELS_PATH`/`_EMBEDDING_CACHE_PATH` (pointing into this WSL checkout over
`\\wsl.localhost`), `MOCKINGBIRD_BIOCLIP_DEVICE`,
`MOCKINGBIRD_MEGADETECTOR_MODEL_PATH` and
`MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR`. By documented precedence
(`bioclip_runtime._resolve_bioclip_path`: override > env > packaged) these
redirect BioCLIP away from the packaged bundle. A probe on `home-a` showed
exactly that. This is test-host hygiene, not a product defect. The user's
persistent environment was **not modified**; every later launch removed
those six variables at process scope only (launcher prints
`CLEAN_ENV: MOCKINGBIRD_HOME`). `home-a`'s product results are used only as
defect evidence (§7), never as acceptance evidence.

## 4. Acceptance results (clean instance `home-b` unless noted)

| # | Requirement | Result | Evidence |
|---|---|---|---|
| 1 | Disposable home, non-8000 port | `C:\MBRC\home-b`, 8125; health `ready: true` 1 s after launch; schema 61, fresh DB (`database_migrated_from_version: null`) | `home-b-instance.json` |
| 2 | Running identity = frozen manifest | `GET /api/product/instance` -> `git_commit 661d0540ad6b832db47539232ec7b1cc6d2594e2`, `build_id b4630af21a31c341`, `app_version 0.1.0` -- identical for every candidate instance, including the ones migrated from v59 | `home-b-instance.json`, `up-copy-3-after-migration.json` |
| 3 | Unpack/install, launch, onboarding, real frontend | native `tar.exe` unpack; `.vbs` launcher; the built frontend served from the bundle; full five-step wizard driven in real Microsoft Edge 154 (Welcome -> Account -> Storage -> Camera -> Observe -> Finish). Progress persisted across page reloads. The auto-seeded demo Source was replaced by the user's own Source on camera completion; `setup/state.completed = true`. **Finding F-3 (§7): Doctor reports "Not working" right after default onboarding.** | `b-01…b-06` screenshots |
| 4 | Supported camera/media setup and preview, no Pi | the only camera on the host (EMEET S600 webcam) is disconnected; Pi unavailable. Used **Manual media -- Import only** in the wizard (validated: "Configuration Valid", default Feeder Zone). Folder preview is a real dry run: 4 supported, 0 skipped, **media count unchanged by the preview**. Folder import (4 real field stills) and per-file import (the real 64 s field recording, 46.1 MiB) through the UI. **No live preview, live readiness or Observation start/resume was exercisable, and none is claimed.** | `b-07…b-09` |
| 5 | MDv5a ONNX/CUDA at 0.1 + BioCLIP-2 on RTX | exact production loader (`engine_runtime._load_real_provider`) run by the candidate's own `python.exe`: `provider-config.json` resolved from the packaged `observation_runtime`, `md-v5a` `MDv5a.0.1-onnx-opset18`, fingerprint `b03ef796…`, source `fe3e90e4…`, **`score_threshold: 0.1`**, providers `[CUDA, CPU]`, **`cuda_only_verified` -- 1772 CUDA nodes, 0 CPU, 0 unknown**, median 98 ms/frame on 4 real field stills. BioCLIP-2 paths resolved to the packaged `bioclip_runtime` (clean env); real forward passes on field stills, `model_weights_verified: True`, weights/cache hashes equal the manifest, labels fingerprint `ace5f76e…` (the newline-joined label-list fingerprint; the same 14-label file's bytes hash to the manifest's `b90cea20…` -- verified, not assumed) | `model-probe-clean.json` |
| 6 | Bounded loop, real recorded field inputs | **Observe/ingest:** `analyze-recorded` on the real recording (same route the UI's *Analyze imported media* action calls): 128 frames considered, 64 analysed, 2 Events / 2 candidate Visits, `creates_truth: false`, 50.7 s -- deterministic (identical ids on both instances). **Evidence:** each Visit carries its detector evidence frames. **Review Queue:** 7 items, all "species not confirmed". **Suggestion:** *Suggest species* (BioCLIP-2) ran on four Visits in the browser (28 s cold, 11-13 s warm) and **abstained** on every one under `identification-eligibility-v1` (top-1 Red-bellied Woodpecker at 0.34-0.59, below the 0.85 floor) -- an honest outcome, stored as evidence only. **Explicit correction:** I inspected the frames myself; two small birds are on the tube feeder but species cannot honestly be determined, so each was corrected to **Unknown Bird** in the UI. 4 ReviewLabels, `review_origin: human`, `is_authoritative: true`, attributed to the signed-in admin. **Reviewed history:** Bird Log shows "Unidentified wildlife -- 4 confirmed". **Today truth:** animal-Visit count 5 before -> **5 after** confirmation; Today reads "2 visits confirmed today, species not yet identified"; both confirmed Visits remain in Best moments -- no disappearance. The two recorded-video Visits are anchored at 1970 by design (the recording has no `creation_time`) and are honestly excluded from Today | `b-10…b-19`, `b-after-review*.json`, `b-dashboard-*-confirm.json` |
| 7 | Graceful shutdown, restart/resume, abrupt recovery, survival | **In-app graceful shutdown hung permanently (F-1, §7)** -- the blocker. Force-ending the hung process (the documented fallback) and relaunching: honest `previous_shutdown_clean: false`; Visits, media, ReviewLabels (ids and origins), queue counts and instance identity identical; all 12 media files byte-identical; `PRAGMA quick_check` ok. A graceful stop by a client that never reset a connection exited in about 1 s (`state: clean`); relaunch reported `previous_shutdown_clean: true` with identical data. **Observation resume after restart was not exercisable** (no live camera) | `snap-b1/b2/b3*.json`, `b-media-hashes-before.txt`, `home-b-hang-pyspy.txt` |
| 8 | Named timezone / DST | Windows `TimeZoneKeyName = Eastern Standard Time` -> `America/New_York` (`ZoneInfo`) with `TZ` unset, in the packaged runtime. Spring forward: `06:30Z -> 01:30 EST`, `07:30Z -> 03:30 EDT`; fall back: `05:30Z -> 01:30 EDT`, `06:30Z -> 01:30 EST`; July `12:00 EDT`, December `11:00 EST`. Doctor Clock: "Host local timezone resolved to America/New_York". Live UI rendered `02:08Z` as `Sep 28, 10:09 PM`, and Today bucketed that UTC-next-day moment into "for 2026-09-28" | `tz-dst-probe.txt` |
| 9 | v59 -> v61 upgrade, pre-migration backup, restore, recovery (disposable copies only) | the v59 build (`039ce7d`, `build_id ed8442fc…`, schema 59) created real data: admin, 2 imports, a verified manual v59 backup, and a `review_origin: human` label on an imported Visit. The home was copied; the candidate started on the copy -> health `database_schema_version 61`, `database_migrated_from_version 59`; an automatic **`pre_migration`** backup (schema 59, verified, restore-compatible) was created beside the user's manual backup; every ReviewLabel row was preserved byte-for-byte and the human label stayed authoritative and reviewed. A post-upgrade human label was then added and the pre-migration backup restored through `restore-plan` -> `restore`: an automatic verified **`pre_restore`** safety backup (schema 61) was created, the post-upgrade label was gone, the restored v59 database was re-migrated to 61, human truth intact, `quick_check` ok. **Downgrade guard:** the v59 binary pointed at the migrated database refused ("created by a newer app version…", exit 2) with the database byte-unchanged. The original v59 seed tree was byte-identical afterwards | `up-copy-*-*.json`, `downgrade-refusal.txt`, `up-v59-seed-tree.sha256` |
| 10 | Real-browser evidence of the critical visible path | 35 full-page Edge screenshots, including onboarding (all steps), media setup/validation, folder preview/import, Review Queue before/after, the BioCLIP abstention, correction truth, Today before/after, Bird Log, Doctor "Not working", Local Data shutdown | `C:\MBRC\evidence\*.png` |
| 11 | Verifier + focused validation | §6 | -- |

**Frontend console:** the only browser errors on the critical path were
designed responses (a `401` session probe before sign-in; a `404` from
`GET /api/camera-nodes/pending-setup`, which that route documents as "nothing
to resume"). No page errors.

## 5. Camera Node / Pi -- precise limitation

- The exact candidate wheel (`38dfac47…`) was **package-verified** this
  session (§2): hashes, manifest contents, and byte-identity of every module
  and the installer with the frozen source.
- The handoff records that the same artifact **reportedly passed a
  read-only `--preflight`** against the reference Pi during this milestone's
  earlier session, without changing the device. That result was not
  re-observed here: the Pi is no longer available.
- The candidate was **not** freshly installed, upgraded, paired, streamed
  or field-run on any Camera Node. No live Camera Node connection was
  simulated or implied. Pi-specific code was not touched.
- Previously accepted Camera Node hardware evidence (installer/reboot,
  boot identity, recovery, upgrade compatibility, the 2026-09-25 field
  corrections) is preserved as recorded. None of it was produced by this
  candidate artifact, and it is not re-attributed to it.

## 6. Validation

- **Tier 1 (artifact/provenance):** §2 -- all checks pass.
- **Tier 2 (focused suites at `661d054`, unchanged source, WSL `.venv`):**
  `test_verify_release_artifact`, `test_product_shutdown`, `test_doctor`,
  `test_first_run_onboarding`, `test_local_backup_recovery`,
  `test_cross_install_backup_restore`, `test_upgrade_path_acceptance`,
  `test_time_utils`, `test_single_app_runtime`, `test_bioclip_runtime`,
  `test_engine_runtime`, `test_offline_ingest` -> **377 passed** (4m38s);
  `test_camera_node_packaging`, `test_install_camera_node`,
  `test_local_product_packaging`, `test_windows_launcher_instance_identity`
  -> **227 passed** (5m28s). Total **604 passed, 0 failed**.
  **These green suites do not cover F-1/F-2** (Windows-Proactor-only
  behaviour; the suites run on Linux) **or F-3** (an untested state
  combination). Green is not evidence against these findings.
- **Tier 3:** reused, not re-run -- source is unchanged since the accepted
  CI & Core Validation Closure v1 baseline (§14; hosted `e2c543e` 6143
  passed / 0 failed; local `d0b5dd0` 6230 passed / 1 documented timing
  exception).
- No `ruff`/frontend build was needed: no code changed.

## 7. Findings

### F-1 -- In-app graceful shutdown hangs forever on native Windows after any client connection reset (RELEASE-BLOCKER CANDIDATE)

- **Observed:** twice, organically, in both real-browser acceptance sessions.
  `home-a`: `POST /api/product/shutdown` returned `200 accepted`, the log
  shows `Shutting down` and nothing after it; the process was still alive
  about 13 minutes later, with `runtime_state` stuck at `starting`, until it
  was force-ended. `home-b` (the clean instance): identical, still alive
  more than 6.5 minutes after the request before being force-ended. The
  user sees "MockingBird is shutting down. It's safe to close this tab now."
  The next launch reports an unclean shutdown.
- **Correlation across every run this session:** each session whose log
  contained a `WinError 10054` in `_call_connection_lost` hung (2/2); each
  session with none exited cleanly in about 1 s (11/11: repro, `home-b`
  after relaunch, v59, upgrade copies). In `home-b` the resets came from
  ordinary Edge usage; the first was at 22:09:13, during the UI video
  upload.
- **Root cause (proven on the bundled runtime, not assumed):**
  1. Bundled CPython 3.12.7 `asyncio/proactor_events.py`
     `_ProactorBasePipeTransport._call_connection_lost` (disassembled from
     the shipped `python312.zip`): line 165 `self._sock.shutdown(SHUT_RDWR)`
     raises `ConnectionResetError [WinError 10054]` when the peer has
     already reset. Lines 166-170 -- `sock.close()` and
     **`server._detach()`** -- therefore never run. The log records exactly
     this traceback, at line 165.
  2. The asyncio `Server`'s active-connection count leaks.
     `Server.wait_closed()` (3.12 semantics) waits for that count to reach
     zero, so it now waits forever.
  3. Bundled uvicorn 0.54.0 `Server._wait_tasks_to_complete` ends with
     `for server in self.servers: await server.wait_closed()`. It is bounded
     only by `timeout_graceful_shutdown`, which
     `mockingbird/runtime.py` leaves at its default `None`.
  4. So `lifespan.shutdown()` is never reached: no
     `Waiting for application shutdown.`, the app teardown and
     `mark_clean_shutdown()` never run, and the process never exits.
     `py-spy dump` (disposable diagnostic tool, host only) of both hung
     processes shows the main thread idle in the Proactor `select` inside
     `Runner.run`, with 0.06 CPU-seconds per 5 s and every background
     thread (`durable-monitoring`, `camera-node-recovery`,
     `acoustic-runtime`, `attention-sync`) **still alive**.
- **Why it blocks:** clean shutdown and documented recovery are named
  acceptance criteria. The in-app button is the product's documented stop
  method, and it fails under ordinary browser use on the primary platform.
  A hung process keeps its background supervisors running after the user
  was told it stopped. Data survived force-termination in every case, so
  this is not a data-loss defect. The owner decides the classification.
- **Not deterministically reproduced synthetically:** about 15 attempts
  (abortive closes after complete or partial responses, mid-download RST,
  keep-alive-timeout races, headless-Edge video streaming and upload then
  close) did not produce the line-165 reset. The organic 2/2 plus the
  stack-level proof is the evidence; a deterministic Windows repro is the
  first obligation of the correction (§9).

### F-2 -- One burst of abortive client connections permanently kills the listener; the process lives on, unreachable (GENUINE DEFECT, same layer)

- **Observed and deterministic:** `home-repro`, 3/3 fresh launches. A burst
  of at most 30 back-to-back `Connection: close` requests, each aborted with
  RST (`SO_LINGER 0`), -> bundled CPython's Proactor accept loop hits
  `OSError [WinError 64] The specified network name is no longer available`
  in `finish_accept`. It logs `Accept failed on a socket` and **closes the
  listening socket**. Every later connection is refused, including the
  in-app shutdown, while `pythonw.exe` stays alive with `runtime_state:
  starting`. Spaced single aborts (100 per launch, 3 launches) never
  triggered it.
- **Impact:** availability. Recovery requires ending the process. Because
  the dead listener frees the port, a relaunch can start a second process on
  the same home while the zombie's background threads still run. That
  double-process state was **not** exercised here, and no data effect is
  claimed. It was not seen organically on loopback in this session. It is
  more plausible under the documented `--allow-network` LAN/phone mode.
  Owner to classify. It is bundled into §9 because it is the same subsystem
  and shares candidate remedies.

### F-3 -- Doctor reports "Not working" (BLOCKING) immediately after default first-run onboarding (GENUINE DEFECT, deterministic)

- **Observed:** 2/2 fresh instances (`home-a`; clean `home-b` before
  *Finish setup*). The Storage check returns `FAIL` / `blocking` "The
  configured media storage folder does not exist.", so Doctor's overall
  status is `UNHEALTHY` ("MockingBird cannot reliably observe wildlife until
  at least one check below is fixed"). It cleared on the first media write
  (the next Doctor reported only the real low-disk `WARN`).
- **Root cause:** `diagnostics/doctor.py` treats "database exists **and** a
  Source is configured" as proof that the lazily created media root should
  exist. The default onboarding path creates a Source without writing any
  media: "Finish without watching yet", which is the safe default, or any
  import-only Source before its first import. Release Reliability &
  First-Run Recovery v1 closed the same class for "no Source yet" only.
- **Impact:** a new user or Gate G participant told to run Doctor after
  setup sees "Not working" on a healthy install. No data or behaviour
  impact. Owner to classify. Recommended to fix before Gate G.

### Non-blocking observations (disclosed, not fixed)

- **O-1:** recorded video with no `creation_time` is anchored at 1970 by
  documented design (offline contract). In a UTC-negative zone the UI
  renders that as a year-less "Dec 31, 7:00 PM", which reads like a recent
  date rather than "capture time unknown".
- **O-2:** an offline-analysis (detector-produced) Visit's review page says
  "No detections are attached to this manual media visit."
- **O-3:** abstained BioCLIP attempts persist the prepared-run provenance,
  with `model_weights_verified: false` (`bioclip_adapter.py:626`). Only a
  result-producing run records `true`. The weights hash itself matches the
  manifest. Explained, not a defect.
- **O-4:** the analysis-run duration was 72 s on the contaminated instance
  and 51 s on the clean one. The runs are not comparable, and the
  difference is not attributed to anything.
- **O-5 (test-host hygiene):** the persistent Windows developer variables
  (§3) would silently redirect any future packaged acceptance on this host.
  Clear them at process scope, as done here, or have the owner remove them.

## 8. Protected files and repository hygiene

Before and after, byte-identical and untracked:
`docs/wildlife-detector-training-contract.md.orig` `63f9e5ba…`,
`scripts/evaluate_small_bird_detector.py` `81cdff04…`,
`scripts/materialize_wildlife_stage2.py.orig` `ade97d9d…`,
`scripts/train_wildlife_stage2_rfdetr.py.orig` `a24aa6e2…`,
`src/mockingbird/detectors/small_bird_benchmark.py` `e85a2315…`,
`src/mockingbird/training/wildlife.py.orig` `548f0706…`,
`tests/test_small_bird_benchmark.py` `abad318b…`, `uv.lock` `f36f26ba…`.
No generated media, evidence, model or artifact was committed. All evidence,
disposable homes, the extracted candidate and the disposable driver scripts
live under `C:\MBRC\` on the Windows host, outside the repository. The
port-8000 field instance, `%LOCALAPPDATA%\MockingBird*`, `C:\MBTestNew`
(read/executed only) and the persistent user environment were not modified.
At the end no MockingBird process was running on the host.

## 9. Bounded correction contract (proposed -- NOT authorized, NOT started)

**Proposed milestone:** *Native-Windows Runtime Shutdown & Listener
Resilience Correction v1*. It is a correction to the frozen candidate, not
feature work. It requires a new candidate SHA, a rebuild and a repeat of this
acceptance.

- **Product flow protected:** Remember and trust. Stopping MockingBird must
  actually stop it, it must stay reachable while running, and a healthy new
  install must not be reported broken.
- **Files allowed (expected):** `src/mockingbird/runtime.py`; at most one new
  small runtime helper module, if an event-loop policy is chosen;
  `src/mockingbird/diagnostics/doctor.py`; focused tests
  (`tests/test_single_app_runtime.py`, `tests/test_product_shutdown.py`,
  `tests/test_doctor.py`); the report; the §3/§14 delta. No schema change,
  no API contract change, no Pi code, no dependency or CPython-version change
  unless the investigation below proves it is the smallest correct remedy and
  the owner approves it separately.
- **F-1, required outcome:** after any client connection reset, *Shut down
  MockingBird* and Ctrl+C complete the existing lifespan teardown and
  `mark_clean_shutdown()` within a bounded time. The next launch then reports
  a clean shutdown. **Leading candidate:** set uvicorn
  `timeout_graceful_shutdown` to a small bounded value in `runtime.py`. It
  already wraps the hanging `wait_closed()` (verified in the bundled uvicorn
  0.54.0 source) and changes no other semantics.
- **F-2, required outcome:** an abortive client connection, or a burst of
  them, never closes the listening socket. The process stays reachable.
  **Options to decide with evidence:** (a) run uvicorn on a Windows selector
  event loop -- verified no-risk precondition: the product uses no asyncio
  subprocess or Proactor-only API; the caveat is the ~512-socket `select`
  limit, far above loopback/LAN needs; (b) a narrowly scoped accept-error
  resilience; (c) a patched CPython only if upstream has verifiably fixed it,
  as an owner-approved dependency change. Option (a) may also remove F-1's
  trigger. F-1's bounded timeout stays regardless, as defense in depth.
- **F-3, required outcome:** the Storage check does not return `BLOCKING`
  merely because no media has been written yet on a configured install.
  Missing-but-expected media, meaning media rows exist whose root is gone,
  stays a real failure. Prefer the smallest change to the existing
  gate, for example "any MediaAsset recorded" instead of "any Source
  configured". Do not add a second storage check.
- **Tests first:** a failing focused test per finding before the fix -- F-3
  in-process; F-1/F-2 via a Windows-only real-socket test or an explicitly
  documented real-Windows acceptance script, since a Linux-green suite
  cannot demonstrate them (§6).
- **Validation:** Tier 1 + Tier 2 as in §6; Tier 3 Core (runtime source
  changes); rebuild the candidate from the new SHA; repeat, on native
  Windows, the F-2 burst probe (0/3 listener deaths required), a
  real-browser session followed by in-app shutdown (clean exit and
  `previous_shutdown_clean: true` on relaunch, at least 3 consecutive
  sessions), Doctor after default onboarding (no `FAIL`), and this report's
  §4 rows 1-3 and 6-9.
- **Non-goals:** O-1/O-2 copy, `Q-2`/`Q-4`/stale `camera_connected`, any
  Camera Node change, model/threshold change, performance work.

## 10. Remaining release queue

Unchanged: §6 of `release-execution-state.md`, lanes A-S, with every
classification preserved. This milestone adds F-1 (blocker candidate), F-2
and F-3 as findings against the frozen candidate. Gate G remains
**unexecuted and unwaived**. An accepted internal candidate would still not
be permission to publish.

## 11. Changed files and scope deviations

- Added: `docs/internal-release-candidate-rebuild-native-windows-acceptance-v1-report.md`.
- Modified: `docs/release-execution-state.md` (§3 closure delta only).
- **Deviations, disclosed:**
  1. `home-a` was retired as contaminated, and the acceptance was redone on
     `home-b` (§3).
  2. `py-spy` was installed with `pip --target` into the disposable
     `C:\MBRC\tools` on the test host, for stack dumps only. It is not
     part of the product and was not added to the repo.
  3. The recorded-video analysis was triggered through its product API
     route rather than the Cameras-page button. The UI's per-file import
     does not analyse, by design, and the button lives in the source
     folder-import flow; it is the identical route and handler.
  4. The first v59 seed labels were created through the raw API without
     `review_origin`. v59 and v61 both correctly treat them as non-authority
     (the v59 database shows the Visits still `needs_review`). A genuine
     `review_origin: human` label was then added in v59 and carried the
     upgrade proof.
  5. Push was not performed. The milestone's authorization allowed scoped
     pushes, but this session's instruction was not to push.
