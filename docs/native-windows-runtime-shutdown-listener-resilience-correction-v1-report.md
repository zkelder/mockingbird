# Native-Windows Runtime Shutdown & Listener Resilience Correction v1 -- Report

**Verdict: CORRECTION COMPLETE -- F-1, F-2 and F-3 closed on a rebuilt,
independently verified candidate at `2272126`, re-accepted on native
Windows. No release blocker from the Internal Release Candidate acceptance
remains open. Authorization returns to `NONE`.**

This milestone was authorized directly by the owner as the bounded
correction proposed in §9 of the
[Internal Release Candidate Rebuild & Native-Windows Acceptance v1 report](internal-release-candidate-rebuild-native-windows-acceptance-v1-report.md),
which is accepted as valid evidence. Candidate `661d054` is rejected. F-1
and F-2 were classified as v0.1 release blockers and F-3 as a P1 that must
close before Gate G. Nothing was pushed, tagged, signed, published or
distributed, and no Gate G activity occurred.

## 1. Task packet (restated)

- **Roadmap phase:** release readiness (feature freeze); a correction to a
  rejected candidate, not feature work.
- **Product flow improved:** Remember and trust. Stopping MockingBird
  actually stops it, it stays reachable while running, and a healthy new
  install is not reported broken (Observe -> ... -> Remember, and the
  Doctor surface that tells a user whether they can trust it).
- **Why next:** the only authorized milestone; F-1 and F-2 block v0.1 and
  F-3 must close before Gate G.
- **Files allowed:** `src/mockingbird/runtime.py`,
  `src/mockingbird/diagnostics/doctor.py`, focused tests, a bounded
  native-Windows acceptance script, this report and the accepted
  `release-execution-state.md` delta.
- **Non-goals:** schema, model, threshold, Camera Node, Pi,
  observation-engine or product-feature changes; CPython/uvicorn patch or
  upgrade; the O-1..O-5 observations; Gate G.
- **Validation tier:** Tier 1 focused tests, Tier 2 affected suites, Tier 3
  Core (production runtime code changed), rebuild and independent
  verification, then Tier 4 native-Windows socket/process/browser
  acceptance.

## 2. Starting state

- Repository `/home/<user>/projects/mockingbird-active` (native WSL, not
  `/mnt/c`), branch `main`, HEAD
  `673ccf1ddd079265ee90552d49ce218214c1cb93`, nothing staged, worktree clean
  apart from the 8 protected untracked files.
- Schema `v61`, version `0.1.0` -- both unchanged by this milestone.

## 3. Investigation

### 3.1 Premise for a selector event loop (F-2, and F-1's trigger)

Verified directly, not assumed:

- **Uvicorn really runs Proactor on Windows.** Bundled uvicorn 0.54.0
  `Server.run` is `asyncio.run(self.serve(), loop_factory=config.get_loop_factory())`,
  and `uvicorn.loops.asyncio.asyncio_loop_factory` returns
  `asyncio.ProactorEventLoop` on `win32`. The bundled CPython 3.12.7's
  default policy loop is `ProactorEventLoop` (probed with the packaged
  `python.exe`).
- **Nothing on the server loop needs Proactor.** The repository has no
  `asyncio.create_subprocess_*`, `subprocess_exec/shell`,
  `connect_read/write_pipe` or other Proactor-only API. Camera/ffmpeg
  bridges use blocking `subprocess.Popen` on their own threads. The other
  `asyncio.run(...)` call sites (the Observation Engine's own thread,
  research/benchmark CLIs, a test-only client) create their own loops and
  are untouched, because the change selects the loop for the uvicorn server
  only and never sets a process-wide policy. All 16 background threads are
  daemon threads.
- **The selector loop does not have either defect**, confirmed by
  disassembling the bundled 3.12.7 `asyncio.selector_events`:
  `_SelectorTransport._call_connection_lost` closes the socket and calls
  `server._detach()` on both the normal and the exception path; and
  `BaseSelectorEventLoop._accept_connection` returns on
  `BlockingIOError`/`ConnectionAbortedError`, pauses and retries on
  resource exhaustion, and otherwise re-raises to the loop's exception
  handler -- the listening socket's reader stays registered.
- **Caveat:** Windows `select()` handles at most 512 sockets, far above a
  loopback/LAN product's concurrent connections.

No CPython or uvicorn patch or upgrade was needed, so no dependency
decision packet was required.

### 3.2 F-1 mechanism and the graceful-shutdown bound

Uvicorn's default `timeout_graceful_shutdown=None` waits forever for open
connections and for `asyncio.Server.wait_closed()` before it runs the
FastAPI lifespan teardown, which ends in `mark_clean_shutdown()`. The
Proactor bug leaked the server's connection count, so `wait_closed()` never
returned. The investigation found a second, platform-independent path to
the same hang: a response that never ends, such as an open MJPEG live view.
A scratch reproduction with an infinite streaming response was still hung at
30 s with no bound (Linux), and finished at 5.14-5.18 s with the bound
(native Windows and Linux).

**Value selection (measured on native Windows, packaged 3.12.7 runtime with
the fixed code, selector loop, no bound yet):** the whole drain plus
lifespan teardown after `POST /api/product/shutdown` completed in
**0.45-0.59 s**, and the process exited in **0.83-1.06 s**. That held in 3
clean sessions and in 3 sessions that each had 20 keep-alive resets and 60
abortive connections first. The log is polled because uvicorn's lines
carry no timestamps. **5 s** is ~8x the worst measured drain+teardown and
well short of a user concluding the stop hung. When the bound fires,
uvicorn cancels the remaining request tasks and still runs the teardown. A
blocking handler already running on a worker thread is not interrupted; it
finishes before the process exits. Measured on the packaged Windows runtime
with an 8 s blocking handler, teardown ran at 5.24 s and the process exited
at 7.53 s, after the handler finished.

## 4. Changes

- **`src/mockingbird/runtime.py`**
  - `build_uvicorn_server(...)` constructs the same `uvicorn.Config`, plus
    `timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS` (5).
  - `serve_until_stopped(server)`: on Windows,
    `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop).run(server.serve())`,
    which is exactly uvicorn's own `Server.run` with only the loop class
    changed. Other platforms keep `server.run()` unchanged, including
    uvloop where installed.
  - `run()` uses both. The `app.state.uvicorn_server` publication, the
    shutdown endpoint, authentication, Local-Only defaults, the crash
    marker and `mark_clean_shutdown()` placement are unchanged.
- **`src/mockingbird/diagnostics/doctor.py`** -- the existing Storage check
  now gates `FAIL`/`BLOCKING` for a missing media root on "any MediaAsset
  recorded" (`_gather_has_any_media_recorded`) instead of "any real Source
  configured". This is not a second check or taxonomy. The seeded demo data
  records no MediaAsset. An unreachable database (`None`) never escalates.
- **`scripts/native_windows_runtime_resilience_acceptance.py`** -- a
  stdlib-only, native-Windows-only acceptance tool that the packaged
  `python.exe` can run. Subcommands: `launch` (shipped `.vbs`, scrubbed
  environment, explicit home), `burst` (the exact prior F-2 reproducer),
  `resets`, `shutdown` (phase timing, marker, remaining processes),
  `ctrl-c` (real console `CTRL_C_EVENT` via `AttachConsole`) and
  `processes`.
- **Tests:** `tests/test_single_app_runtime.py` (4 new),
  `tests/test_doctor.py` (2 new end-to-end, 1 replaced gather test, 3
  interpreted cases updated to the new gate, and the superseded
  "Source configured + no media -> BLOCKING" test removed, because it
  asserted exactly the F-3 defect), and `tests/test_windows_launcher_instance_identity.py`
  (mock seam moved from `Server.run` to `serve_until_stopped`).
- **Docs (one-line contract accuracy):**
  `docs/single-app-runtime-recovery-design.md` (bounded shutdown and
  Windows selector loop) and
  `docs/mockingbird-doctor-operational-health-contract.md` (blocking
  storage semantics).

## 5. Test-first evidence

Each failing test was run and observed red before its fix.

| Finding | Test | Red (before fix) | Green |
|---|---|---|---|
| F-3 | `test_doctor_storage_after_onboarding_before_first_media_write_is_informational` | `FAIL` != `PASS` on a real DB with a Source and no media | PASS |
| F-3 (guard) | `test_doctor_storage_missing_media_root_with_recorded_media_is_blocking` | passed before and after (the honest failure preserved) | PASS |
| F-2 | `test_real_launch_serves_on_a_selector_loop_whatever_the_platform_default` (drives `runtime.run()`; the Windows default is simulated by a marker loop factory) | served on the platform-default marker loop | PASS |
| F-1 | `test_graceful_shutdown_is_bounded_when_a_connection_never_detaches` (real socket; leaks `asyncio.Server._attach()` exactly as the Proactor bug did) | serve still hung 10 s after `should_exit` | PASS (teardown ran, < 5 s at a 1 s test bound) |
| F-1 | `test_built_server_carries_the_bounded_graceful_shutdown_timeout` | `None` != 5 | PASS |
| F-2 (regression) | `test_abortive_connection_burst_leaves_the_listener_serving` (the exact burst shape, real sockets) | n/a on Linux | PASS |

**Real native-Windows red, on the untouched `661d054` candidate:** the
exact burst reproducer killed the listener on burst #1 in **3/3** fresh
launches (`Accept failed on a socket`, `pythonw.exe` alive and
unreachable). Run 1 also showed the double-process hazard for real: a
relaunch on the same home started a second process next to the zombie. The
fixed code on the same packaged interpreter (pre-rebuild overlay) gave
**0/3** deaths across 900 abortive connections.

## 6. Validation

- **Tier 1:** focused tests above; `ruff` clean on every changed Python
  file.
- **Tier 2:** `test_verify_release_artifact`, `test_product_shutdown`,
  `test_doctor`, `test_first_run_onboarding`, `test_local_backup_recovery`,
  `test_cross_install_backup_restore`, `test_upgrade_path_acceptance`,
  `test_time_utils`, `test_single_app_runtime`, `test_bioclip_runtime`,
  `test_engine_runtime`, `test_offline_ingest`,
  `test_camera_node_packaging`, `test_install_camera_node`,
  `test_local_product_packaging`, `test_windows_launcher_instance_identity`,
  `test_camera_node_hardware_health`, `test_product_health` -> **639
  passed, 1 skipped, 0 failed** (9m56s).
- **Tier 3 Core** (`scripts/verify_core.py`, at the working tree that was
  committed as `2272126`): **6235 passed / 1 failed / 4 skipped / 35
  deselected / 11 xfailed** (42m16s). The single failure,
  `test_everyday_discovery_ux_closure.py::test_today_dashboard_shows_only_corrected_truth`,
  is **not attributable**. The run crossed local midnight. The fixture
  dates its Visits 30-50 minutes before "now", so near 00:40 local they
  fall into the previous local day and drop out of Today. The file passes
  19/19 in isolation. The test reproduces deterministically with the local
  clock forced to 00:20 (`TZ` offset), and it fails identically on the
  **unmodified `673ccf1`** under that same clock (tracked changes stashed;
  protected files re-hashed unchanged). It is a pre-existing test-fixture
  midnight-boundary defect, disclosed and not fixed (out of scope).

## 7. Candidate identity and independent verification

- **Frozen source SHA:** `2272126bfed784b48862fd59b99e19e03202b26f`
  (version `0.1.0`, schema `v61`).
- **Windows Host artifact**
  (`dist/native-windows-runtime-correction-v1-2272126/`, private and
  ignored):
  - `MockingBird-windows-x64.zip` SHA-256
    `124939b96bde155fceb34595a8ab41d7ca65ef2c3ff9a1d4a6bdeaeecc8dc650`.
  - `build_id c1b25f79d2db3f10`, `source_clean: true`, 19,284 files /
    4,923,709,105 bytes, embedded Python 3.12.7, unsigned
    (`signing.requested: false`), CycloneDX 1.5 SBOM with 59 components.
- **Camera Node wheel**
  (`dist/native-windows-runtime-correction-v1-2272126-camera-node/`):
  - SHA-256
    `38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904`,
    **byte-identical to the `661d054` wheel** (no Camera Node code changed
    since then).
  - All 19 entries match `manifest.json.wheel_contents`, with no unlisted
    entries.
  - All 15 `mockingbird_node/*.py` modules and the bundled
    `install_camera_node.py` are byte-identical to `2272126`.
- **Checks:**
  - `SHA256SUMS` is all OK in both directories.
  - `scripts/verify_release_artifact.py` -> `OK: MockingBird-windows-x64.zip
    (19284 files, 4,923,709,105 bytes), version 0.1.0, source
    git:2272126…, unsigned`.
  - Native `Get-FileHash` on the copy staged to Windows matches. Native
    `tar.exe` extraction took 32 s and produced 19,284 files /
    4,923,709,105 bytes, exactly the manifest.
- **Model provenance** is identical to the accepted values: MDv5a ONNX
  `b03ef796…` (source `fe3e90e4…`); BioCLIP-2 weights `b7b2bf6f…`,
  embedding cache `0260d5bb…`, labels `b90cea20…`; the GPU runtime and the
  verified CUDA 13 DLL closure are included.
- **Dependency parity with `661d054`:** runtime, GPU and BioCLIP
  requirement lists are identical, and the SBOM component set is identical
  (59/59). No dependency changed.
- **Source identity:** all 212 packaged `mockingbird/*.py` files are
  byte-identical to `git show 2272126`. Against the `661d054` ZIP, the
  only content changes are `runtime.py`, `diagnostics/doctor.py` and
  build-identity metadata (`build_info.json`, `RECORD`, `direct_url.json`,
  and the frontend fingerprint's `written_at` -- its `source_fingerprint`
  is identical).
- **Licensing exclusions:** no `ffmpeg.exe`/`ffprobe.exe` and no BirdNET
  model file in the ZIP. `LICENSE` and `THIRD_PARTY_NOTICES.md` are
  present.

## 8. Native-Windows acceptance (rebuilt `2272126` artifact)

Setup:

- **Where it ran:** one native extraction at `C:\MBRC\corr\rc\install\`,
  with disposable homes under `C:\MBRC\corr\` and ports 8141-8145.
- **Launch:** the shipped `Start MockingBird.vbs` (`wscript`), with the six
  persistent developer `MOCKINGBIRD_*` variables removed at process scope
  only (O-5).
- **Browser:** real Microsoft Edge (headless, Playwright-core) from the
  Windows side.
- **Untouched:** port 8000 (no listener before or after), the field
  instance, `%LOCALAPPDATA%\MockingBird*` and the persistent user
  environment.

| Requirement | Result |
|---|---|
| Exact prior F-2 abortive burst | **0/3 listener deaths.** Each fresh launch took 10 bursts x 30 abortive connections (`SO_LINGER 0`), with health re-probed after every burst: 900 connections, 0 refused, health reachable after each burst, 0 `Accept failed` log lines. |
| Reset/abort scenarios then in-app shutdown | 3/3: after 300 abortive connections plus 20 keep-alive-then-RST connections, `POST /api/product/shutdown` drained and tore down in 0.47-0.50 s and the process exited in 0.86-0.89 s. Marker `clean`, no remaining or child processes, port free, graceful timeout not fired. Each relaunch was one process on the home and reported `previous_shutdown_clean: true`. |
| Ctrl+C after resets | 3/3 real console `CTRL_C_EVENT` to the packaged `python.exe -m mockingbird` after 20 keep-alive resets: teardown complete in 1.12-1.16 s, exit in 1.52-1.75 s, marker `clean`, nothing remaining. The exit code `0xC000013A` is Windows' standard `STATUS_CONTROL_C_EXIT` after uvicorn re-raises the captured signal, as before. |
| >= 3 consecutive real Edge sessions | **3/3** on one home (`C:\MBRC\corr\home-edge`, port 8141). Each covered five-step onboarding (session 1) or sign-in, navigation through Today, Cameras, Review Queue, Bird Log, Activity Library, Place Story, Insights, Local Data and Doctor, a UI media upload (the real 64 s field recording, then a real field still, then the recording again), opening the stored media in the browser, and **Shut down MockingBird -> Confirm** in the UI. Clean exit every time, <= 3.3 s after Confirm (an upper bound: polling starts after the browser script's own 2.5 s wait). Marker `clean`, graceful timeout never fired, next launch `previous_shutdown_clean: true` (including a fourth relaunch), and 0 browser page errors. |
| Doctor after default onboarding, before first media write | `HEALTHY`, Storage `PASS`/informational "The media storage folder has not been created yet." both before and after *Finish setup* ("Finish without watching yet" path). 0 media assets, media root absent. **No false `FAIL`.** |
| Doctor with stored media and the media root removed | Home with 3 stored media files: `python -m mockingbird doctor --json` -> `UNHEALTHY`, Storage `FAIL`/blocking "The configured media storage folder does not exist.", exit 2. After restoring the folder, only the genuine low-disk `WARN` remains (C: had 14.9 GB free). |
| Row 1: disposable home, non-8000 port | Yes, throughout. |
| Row 2: running identity = manifest | `GET /api/product/instance` -> `git_commit 2272126…`, `build_id c1b25f79d2db3f10`, `app_version 0.1.0`, including on the home migrated from v59. |
| Row 3: unpack, launch, onboarding, real frontend | Native `tar.exe` unpack; `.vbs` launch ready in 3.8-13 s; five-step onboarding in Edge with a Manual-media Source ("Configuration Valid"); built frontend served from the bundle. |
| Row 6: bounded product loop, real recorded inputs | **Ingest:** `analyze-recorded` on the uploaded field recording (the same route as the UI action) -> 128 frames considered, 64 analysed, 2 Events / 2 candidate Visits, `creates_truth: false`, deterministic with the prior run. **Evidence and Review Queue:** 5 items. **Suggestion:** *Suggest species* (BioCLIP-2) in the UI took 53.5 s cold and 11.6 s warm, and **abstained** ("No Result -- no useful suggestion"). **Correction:** explicit *Unknown Bird* correction in the UI created 2 ReviewLabels, `review_origin: human`, authoritative, Visits `reviewed`. **Bird Log:** `confirmed_species_unresolved_visit_count: 2`. **Today:** held 3 -> 3; the recorded Visits are 1970-anchored by design (O-1) and excluded. |
| Row 7: restart/resume, abrupt recovery, survival | Graceful restarts are clean (above). Force-ending the running process left the marker `starting`; the relaunch reported `previous_shutdown_clean: false`. Visits, review states, ReviewLabel ids/origins, instance id and all 10 media files (by SHA-256) were identical, and `PRAGMA quick_check` was ok. The next graceful stop/relaunch reported `true`. Observation resume was not exercisable (no live camera). |
| Row 8: named timezone / DST | `TimeZoneKeyName = Eastern Standard Time` -> `America/New_York` (`ZoneInfo`, `TZ` unset) in the packaged runtime. Spring forward `06:30Z -> 01:30 EST`, `07:30Z -> 03:30 EDT`; fall back `05:30Z -> 01:30 EDT`, `06:30Z -> 01:30 EST`; July 12:00 EDT, December 11:00 EST. |
| Row 9: v59 -> v61 upgrade, backup, restore, downgrade guard | Fresh copy of the v59 seed home (`039ce7d`): health `schema 61`, `migrated_from 59`. Automatic `pre_migration` backup (schema 59, verified, restore-compatible). Human label `review-label-004` stayed authoritative. A post-upgrade human label was added, then the backup went through `restore-plan` -> `restore`: a verified `pre_restore` safety backup (schema 61) was created, the post-upgrade label was gone (4 labels), and the restored v59 database re-migrated to 61 with its own new pre-migration backup; `quick_check` ok. The v59 binary refused the migrated database ("created by a newer app version", exit 2) with the database byte-unchanged. The original v59 seed tree is byte-identical (8/8). |

Not exercisable here, and not claimed: live camera preview/readiness and
Observation start/resume (webcam disconnected, Pi unavailable).

## 9. Camera Node / Pi boundary

The Pi remains unavailable, and **no new Pi evidence was produced**. No
Camera Node code changed, and the rebuilt wheel is byte-identical to the
`661d054` wheel. It was package-verified only, not installed, upgraded,
paired, streamed or field-run. Previously accepted Camera Node hardware
evidence remains frozen as recorded and is not re-attributed to this
artifact.

## 10. Protected files and hygiene

Byte-identical and untracked at the end (SHA-256 prefixes match the prior
report): `docs/wildlife-detector-training-contract.md.orig` `63f9e5ba`,
`scripts/evaluate_small_bird_detector.py` `81cdff04`,
`scripts/materialize_wildlife_stage2.py.orig` `ade97d9d`,
`scripts/train_wildlife_stage2_rfdetr.py.orig` `a24aa6e2`,
`src/mockingbird/detectors/small_bird_benchmark.py` `e85a2315`,
`src/mockingbird/training/wildlife.py.orig` `548f0706`,
`tests/test_small_bird_benchmark.py` `abad318b`, `uv.lock` `f36f26ba`. All
commits used explicit paths. Artifacts stay under ignored `dist/`. The
evidence, disposable homes, the extracted candidate and the disposable
driver scripts are under `C:\MBRC\corr\`, outside the repository. No
MockingBird process was left running on the host.

## 11. Disclosed observations (not fixed)

- **Core midnight-boundary fixture defect** (§6):
  `test_today_dashboard_shows_only_corrected_truth` fails whenever it runs
  within ~50 minutes after local midnight. It is pre-existing and
  reproduced on `673ccf1`.
- **In-flight blocking work versus the bound:** if a blocking request is
  still running 5 s after a stop, the lifespan teardown runs while it
  finishes. The process still waits for it before exiting, and
  `mark_clean_shutdown()` still marks the lifespan's own completion. This
  is the bound working as designed, and it is the price of ending the
  previously unbounded wait. No such overlap was observed in any
  acceptance session (the bound never fired).
- **Double-process hazard (historical):** a relaunch after F-2 could start
  a second process on the same home next to the unreachable zombie. This
  was observed once on the rejected candidate during the red baseline. With
  the listener no longer dying, the trigger is gone. No single-instance
  lock was added (out of scope).
- The prior report's O-1 to O-5 are unchanged.

## 12. Changed files and scope deviations

- **Candidate commit `2272126`:** `src/mockingbird/runtime.py`,
  `src/mockingbird/diagnostics/doctor.py`,
  `scripts/native_windows_runtime_resilience_acceptance.py` (new),
  `tests/test_single_app_runtime.py`, `tests/test_doctor.py`,
  `tests/test_windows_launcher_instance_identity.py`,
  `docs/single-app-runtime-recovery-design.md`,
  `docs/mockingbird-doctor-operational-health-contract.md`.
- **Record commit:** this report and the `release-execution-state.md`
  delta.
- **Deviations, disclosed:**
  1. `tests/test_windows_launcher_instance_identity.py` and the two small
     contract-document lines were not named in the expected scope. They
     were needed, respectively, to keep an existing test from binding a
     real port, and to keep the contracts accurate.
  2. Pre-rebuild measurements used a disposable overlay (the packaged
     interpreter plus `sys.path.insert` of the working-tree source, and
     `MOCKINGBIRD_WEB_DIST` pointed at the packaged frontend). The overlay
     is used only for the red/green comparison and the timeout measurement.
     All acceptance rows in §8 use the rebuilt artifact itself.
  3. As before, recorded-video analysis used its product API route rather
     than the Cameras-page button (same handler).
  4. Core ran once and was not re-run: its only failure is proven
     pre-existing and non-attributable (§6).
  5. Push was not performed.

## 13. Remaining release queue

§6 of `release-execution-state.md`, lanes A-S, is unchanged. The candidate
at `2272126` is corrected and re-accepted on native Windows for the scope
above. Classifying it and deciding the next step, including whether and
when to start Gate G, remain the owner's decisions. **Gate G remains
unexecuted and unwaived. Authorization: `NONE`.**
