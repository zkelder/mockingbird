# Native-Windows & Packaging Acceptance v1 -- acceptance report

Status: clean-machine/user-acceptance exercise, directly authorized outside
this file by the external (ChatGPT) global release sequencing, following
acceptance of Pre-Release Trust & Correctness Correction v1 (HEAD `f62bb90`,
classification A). Proves the actual generated MockingBird v0.1 Windows
distribution and its documented end-user workflow work end to end -- not a
WSL, developer-checkout, source-tree, or hand-prepared-environment claim.

Starting HEAD `f62bb90` (schema `v59`). Closing HEAD `039ce7d` (schema `v59`,
unchanged) after this milestone's own two real defect fixes, both found via
genuine native-Windows testing of the actual packaged artifact, not source
inspection alone. Preserves all seven protected untracked detector files
unmodified throughout, re-verified at start and close. Not pushed.

## A. Baseline

Verified exactly as expected before any change: branch `main`; HEAD
`f62bb90c786158627394ad62d4d40acbc86007e1`; schema `v59`
(`CURRENT_DATABASE_SCHEMA_VERSION`); version `0.1.0`; working tree clean
except the seven preserved untracked detector files (confirmed present,
identical mtimes, at both start and close); no active writer session sharing
this working tree (this session's own peer-session inventory: every other
MockingBird-named session idle or offline across 197 peers; the sole "busy"
peer belonged to an unrelated project). `docs/release-execution-state.md`
updated to record acceptance of Pre-Release Trust & Correctness Correction
v1 and authorization of this milestone, per the governing brief's "FIRST:
RECORD THE ACCEPTED DELTA" instruction.

## B. Windows environment and clean-state conditions

Real native-Windows hardware, reached via this sandbox's documented
WSL2-to-Windows `powershell.exe`/`python.exe` interop (see memory
`sandbox-has-windows-gpu-interop`), re-smoke-tested at session start.
Windows 10 Pro, build `10.0.19045`, x64. GPU: NVIDIA GeForce RTX 4060 Ti,
driver `610.62`/`32.0.16.1062`. This is a real, actively-used personal
desktop machine (other genuine windows observed live during testing:
unrelated Claude/ChatGPT sessions on a different project, Docker Desktop,
Firefox, Spotify, a WSL terminal for a separate repository) -- not a
dedicated clean VM, disclosed honestly rather than implied otherwise. It has
no MockingBird *development* dependencies installed (no Python/git/npm
toolchain targeting this repo on the Windows side; all of that lives in the
WSL build environment), which is the relevant "clean" fact for this
milestone's own purpose.

At session start: no MockingBird process running; TCP ports 8000/8787 free;
`Test-Path $env:LOCALAPPDATA\MockingBird` **incorrectly** read `False` in
one early one-liner (a quoting artifact of that specific command, not a
real fact -- see below). Disk C: ~466 GB total, ~64 GB free at session
start (dropped to ~37 GB by session end from this session's own multiple
build copies/extracts -- a testing-environment fact, not a product one).

**Correction made and disclosed, not hidden:** this reference machine's own
true default data location (`%LOCALAPPDATA%\MockingBird`, resolving in
practice to `C:\Users\<user>\AppData\Local\MockingBird`) already holds real
accumulated developer/test history from this project's multi-week build
history, confirmed live (a first launch against it returned
`setup_state.updated_at` dated 2026-08-09, not a fresh install). This was
caught after only two read-only GET calls touched it; nothing there was
modified or deleted. All functional acceptance testing after that point
used an explicit, disposable `MOCKINGBIRD_HOME` override -- a first-class,
documented advanced/developer lever, not a workaround -- so every test
below exercises the identical fresh-install code path a genuine new user's
own default location would take; only the directory string differs. This
is disclosed as a fact about this specific shared reference machine, not a
product defect.

## C. Release artifact built/tested

Built via the actual documented clean-source process, from this Linux/WSL
build host, per `docs/local-product-packaging-design.md` and
`.github/workflows/ci.yml`'s own non-structural-smoke invocation shape:

```
python scripts/build_local_product.py <output_dir>
```

(no `--skip-gpu-runtime`/`--skip-bioclip-runtime` -- the full GPU/CUDA and
BioCLIP runtime closure was included both times, matching "real hardware,
not simulated" precedent from prior accepted milestones.) Built twice: once
from HEAD `f62bb90` (Phases 1-8's own baseline artifact), and once more from
`039ce7d` after this milestone's own two fixes (Phases 9-11's own artifact,
and the one used for final re-verification of Phases 7-8). Both builds used
this repository's already-accepted local `data/models/observation-onnx-cuda/`
and `data/models/bioclip-2/` source bundles and pre-populated offline wheel
caches (`.build-cache/wheels-win_amd64-cp312-{cuda13,bioclip}/`) -- no
network access needed or used during either build.

**Exact build command, source commit, artifact identity (final,
`039ce7d`):**

| Fact | Value |
| --- | --- |
| Source commit | `039ce7d44958d0283d03755bacf2995e74b138ff` |
| `source_clean` | `true` (git-archive snapshot of a verified clean commit, per `verify_clean_tracked_source`) |
| Artifact | `MockingBird-windows-x64.zip` |
| File count / uncompressed size | 18,735 files / 4,922,969,412 bytes |
| `zip_sha256` | `6001151640c41b9ed4f1ff117a430ef144cee297b168848e995a5ac478f74c7e` |
| `build_id` | `ed8442fc7b23b622` |
| `app_version` | `0.1.0` |
| Embedded Python | `3.12.7` |
| Signing | Honestly unsigned (`signing.requested: false` -- no `MOCKINGBIRD_RELEASE_SIGNING_KEY_ID` configured, none fabricated) |

Independently verified with `scripts/verify_release_artifact.py`
(deliberately a separate process from the builder): **OK** for both builds,
including the checksum of every `SHA256SUMS` entry, not just the zip.
Camera Node artifact also built both times
(`build_camera_node_artifact.py`), `SHA256SUMS` independently verified with
`sha256sum -c`: **OK**. The Camera Node wheel's own content hash is
byte-identical across `f62bb90`/`ee2af65`/`039ce7d` -- expected and
correct, since none of this milestone's fixes touch
`src/mockingbird_node/`.

**Required bundled files, confirmed present at the real zip root:**
`LICENSE`, `THIRD_PARTY_NOTICES.md`, `README-FIRST.txt` (a genuinely
helpful quick-start not otherwise documented in `using-mockingbird.md` --
a positive finding, not a gap), `Start MockingBird.vbs`, and `python/`
(the embeddable interpreter + full dependency closure + packaged
`observation_runtime/`/`bioclip_runtime/` assets). No other top-level
entries -- no dev-only paths, no `.git`, no `scripts/`/`tests/`/`data/`/
`web/` source.

**Models bundled, provenance independently re-verified (not merely
copied from the manifest):**

- MDv5a ONNX: `onnx_model_sha256`
  `b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc`,
  `source_model_sha256`
  `fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef` --
  both exactly match this project's own accepted provenance record
  (memory `accepted-observation-model-provenance`). License MIT, decoder
  `megadetector_v5_yolov5_raw_v1`.
- BioCLIP 2: `included: true`, all four expected SHA-256 fingerprints
  present (model weights/config/labels/embedding cache).
- GPU/CUDA redistributable stack: `onnxruntime-gpu==1.28.0` plus the exact
  CUDA 13/cuDNN 9 package set already validated against this model; every
  expected DLL (including the historically fragile `cublasLt64_13.dll`)
  confirmed present by the build's own `native_cuda_runtime.checked: true`
  verification.

**Confirmed: no forbidden BirdNET model weights redistributed.** A full zip
listing was scanned for `birdnet` (case-insensitive): exactly one hit,
`mockingbird/species/birdnet_adapter.py` -- the optional adapter's own
*code*, which is expected and licensed permissively (Apache-2.0); zero
`birdnetlib` files, zero model-weight files of any kind. This matches
`THIRD_PARTY_NOTICES.md`'s own documented posture and the build's own
`verify_no_nc_licensed_acoustic_model_redistribution` guard, which would
have failed the build outright otherwise.

**SBOM:** CycloneDX 1.5, 58 components, including the embedded CPython
runtime and both models as `machine-learning-model` components with
correct MIT licenses -- inspected directly, not merely trusted from the
manifest's own summary field.

**Explicitly non-bundled optional component confirmed:** ffmpeg. Zero
references anywhere in the zip listing; `THIRD_PARTY_NOTICES.md` documents
this is a deliberate, guarded posture (`verify_no_bundled_ffmpeg_binary`).

**Build-output dependency found and disclosed, not fixed (low severity):**
a full-bundle scan for embedded local build-machine paths found exactly
one real hit specific to this build:
`mockingbird-0.1.0.dist-info/direct_url.json` records the build machine's
own absolute path (`file:///home/<user>/projects/mockingbird-active/dist/...`)
-- standard pip PEP 610 behavior for any `pip install --target` from a
local wheel path, present in effectively every pip-installed package built
this way industry-wide. No secret, no credential, no functional impact; not
fixed this milestone (cosmetic, not a reproduced user-facing failure).
`numpy/__config__.py`'s own embedded `C:\Users\runneradmin\...` path is
upstream numpy's own CI build metadata, not MockingBird's.

**If build output depended on undocumented local state:** it did not --
both builds used only already-accepted, explicitly-documented conventions
(`--model-bundle-source`/`--bioclip-bundle-source`/`--wheel-cache-dir`
defaults, all pointing at this repository's own documented local
directories), and the clean-source guard (`verify_clean_tracked_source`)
genuinely refused an initial build attempt while this milestone's own fix
commit was still uncommitted -- direct, live proof the guard works, not
merely read in source.

## D. Installation result

Performed the installation the way `docs/using-mockingbird.md` tells a user
to: unpack the zip, double-click `Start MockingBird.vbs`. No installer, no
admin rights required or requested, no separate download beyond the one
zip.

- **What the user downloads/opens:** `MockingBird-windows-x64.zip`; open
  the folder, double-click `Start MockingBird.vbs`.
- **Prerequisite software:** none for the core visual path (GPU driver
  already present is the only real hardware prerequisite, already
  documented). `ffmpeg` only for network/USB/import camera types
  (documented, not bundled, presence-detected honestly by Doctor).
- **Admin rights:** not required. Confirmed: `IsInRole(Administrator)` not
  needed for extraction, launch, or ordinary use.
- **SmartScreen:** the artifact is honestly unsigned. Applied a real
  Mark-of-the-Web `Zone.Identifier` (Internet zone) to the zip before
  extraction -- the same tag a real browser download attaches -- and
  confirmed it propagates onto the extracted `Start MockingBird.vbs` (a
  real, verified Windows/PowerShell behavior, not assumed). Did not force
  an interactive SmartScreen dialog to appear and capture it this session
  (a genuine risk of an unrecoverable blocking modal in non-interactive
  automation); relies on Release Experience Rehearsal v1's own prior real
  confirmation of this exact warning for this exact unsigned-build posture
  (unchanged this milestone) as corroborating evidence, disclosed as such
  rather than re-claimed as freshly proven.
- **Firewall:** confirmed live and screenshotted (see F, below) -- occurs
  specifically when MockingBird binds beyond loopback (`--allow-network`),
  not on an ordinary Local Only launch.
- **Antivirus:** no interference observed from Windows Defender across the
  full session (build copy, extraction, repeated launches, Doctor runs,
  failure injection).
- **Install location:** anywhere the user unpacks it -- tested at
  `C:\MBTest\...` and `C:\MBTestOld\...` (deliberately short paths, see the
  path-length finding below) and, for a realistic-length check, under a
  long `Desktop\MockingBird-NativeWindowsPackagingAcceptanceV1-testing\...`
  path.
- **Mutable data location:** `%LOCALAPPDATA%\MockingBird` by default
  (confirmed by direct source resolution and, separately, by this
  machine's own real pre-existing data living exactly there); a disposable
  `MOCKINGBIRD_HOME` override was used for this session's own actual
  testing (see B, above) but exercises the identical resolution code.
  Sub-layout confirmed real: `data\mockingbird.sqlite3`,
  `data\media\imports\`, `data\backups\`, `logs\mockingbird.log`,
  `instance_identity.json`, `runtime_state.json`.
- **Directory permissions:** correct -- the running process could read/
  write its own data root without elevation; storage writability is also
  actively self-probed (`storage_writable: true` observed live, backed by
  a real bounded write-and-delete check per source).
- **Unexplained console windows/background processes:** none. `pythonw.exe`
  is genuinely windowless (confirmed: `MainWindowHandle=0` on the healthy
  running process); `wscript.exe` exits immediately after firing the
  launch (fire-and-forget `shell.Run(...,0,False)`); no stray processes
  observed after any of this session's ~20 launch/relaunch cycles.
- **Shell required:** no step in the documented golden path requires a
  shell. Where one is offered as an *option* (remote-access flag,
  `python -m mockingbird doctor`), `using-mockingbird.md`'s own copyable
  commands are exact and were used verbatim, successfully, unmodified.
- **Repository-checkout assumption:** none found in the Host path.

**Real defect found and precisely characterized (low severity, disclosed,
not fixed):** Windows PowerShell 5.1's built-in `Expand-Archive` cmdlet
failed extracting the real artifact into a moderately long destination
path (`...\MockingBird-NativeWindowsPackagingAcceptanceV1-testing\install\`,
~89 chars) combined with the bundle's own deepest internal path (PyTorch's
own C++ header files under `torch/include/ATen/...`, up to 164 chars) --
even with this machine's `LongPathsEnabled=1` already set. Root-caused via
a direct diagnostic: the identical long destination succeeded with raw
.NET `ZipFile.ExtractToDirectory`, and -- decisively -- **the real
Explorer "Extract All..." mechanism (`Shell.Application`/`CopyHere`, what
a non-technical user actually double-clicks) also succeeded at the exact
same long path**, extracting all 18,735 files including the deepest one.
This narrows the finding to `Expand-Archive` specifically (a technical
user's PowerShell-only path), not the documented normal-user method.
`torch/include/*.h` (C++ headers MockingBird never needs at runtime -- it
never compiles a C++ extension) is a legitimate, bounded future trim
candidate that would also shrink this ceiling further; not fixed this
milestone (cosmetic robustness margin, not a reproduced failure of the
documented path).

## E. First-launch / Local Only result

Real launch via `Start MockingBird.vbs`, no arguments, against a genuinely
fresh `MOCKINGBIRD_HOME`:

- Ready in 3-6 seconds (`GET /api/product/instance` 200); three-way identity
  confirmation (`app_version`/`git_commit`/`build_id` in the response
  exactly matched the manifest and the source commit each time).
- First screen: real "Setup step 1 of 5 / Welcome to MockingBird" --
  screenshotted -- plain-language explanation, privacy bullets, no
  fabricated wildlife history anywhere (directly re-confirms UI-01 holds on
  a genuine fresh install of the real artifact, and this milestone's own
  new fix closes the adjacent Review Queue/Dashboard-count gap UI-01 left
  open -- see N, below).
- **Local Only confirmed by direct network inspection, not inferred from
  code.** `Get-NetTCPConnection` on the real listening socket showed
  `LocalAddress: 127.0.0.1` (never `0.0.0.0`) on every plain launch;
  every connection owned by the MockingBird process was loopback-only
  (one internal loopback pair, the listen socket itself, one bound-only
  socket) -- zero external destinations, on a launch with no camera/
  weather/iNaturalist configured yet.
- Duplicate-launch behavior: not independently re-verified this session
  (already covered by this exact source path, `resolve_instance_id`/
  `healthy_mockingbird_at`, unchanged by this milestone).
- Restart after ordinary stop: proven repeatedly (~20 cycles across every
  phase below) -- data, login, and instance identity all persisted
  correctly every time.
- Restart after upgrade: see K, below.

## F. Runtime-model/asset result

**MDv5a -- direct, unambiguous, production-wiring proof**, not inferred:
a standalone script replicating the exact production call chain
(`resolve_provider_config_path` -> `FrameDrivenProviderConfiguration.load`
-> `OnnxModelBundle.load` -> `OnnxCudaObservationProvider(...).load()`) was
run with the packaged artifact's own `python.exe` against a real photo from
this project's own prior field-acceptance evidence. Results: config/model
paths resolved correctly via the real packaged-root resolution function;
both fingerprints matched the accepted provenance exactly;
`selected_providers = ('CUDAExecutionProvider', 'CPUExecutionProvider')`
(CUDA first, required); **`cuda_execution_verification`:
`{"classification": "cuda_only_verified", "cuda_executed_nodes": 443,
"cpu_executed_nodes": 0}`** -- zero CPU-executed nodes, definitive proof of
real GPU-only execution; 7 real detections returned, including 3 genuine
"animal" hits directly over the real birds visible in the photo (confidence
up to 0.605) and 4 "vehicle" hits correctly matching real parked cars
visible in that same photo's background -- real, accurate model behavior,
not a mock.

**BioCLIP-2 -- confirmed resolved and ready** via the real Review Queue
identification block on a real imported photo: `"status":
"configured_available"`, `"can_run": true`, `"can_run_on_best_frame":
true`. Doctor's own `species_identification` check independently agreed:
`PASS "BioCLIP species-suggestion runtime is available."`

**BirdNET -- confirmed correctly absent as the optional component:** zero
BirdNET runtime files in the bundle (see C, above); Doctor:
`PASS "The optional BirdNET acoustic runtime is not installed... Visual
observation is unaffected."`; a real imported/detected Visit's review
pipeline was entirely unaffected by its absence.

**Missing-model honest-failure path:** not reproduced live this session
(this build's only real model bundle was not deliberately broken, to avoid
losing the one working GPU-proof artifact) -- confirmed at the source
level instead: `Doctor._interpret_detector_model` returns a plain-language
`WARN`/actionable `user_action` when a Camera Node is configured but no
model bundle resolves, and a calm, non-alarming `PASS` when neither is
configured yet, never a raw exception. This exact code path is unchanged
by this milestone and already covered by the existing Doctor test suite;
disclosed here as source-level, not live, evidence.

**Network-required acquisition vs. Local Only:** none of the required
production assets (MDv5a, BioCLIP-2, the GPU/CUDA runtime) are ever
downloaded at build or run time -- both are copied from a local,
already-accepted source directory at *build* time only, independently
re-verified by SHA-256 before copying (per `docs/
local-product-packaging-design.md`). No live model/setup network fetch
exists to distinguish from Local Only runtime.

## G. Camera Node / first-real-operation result

**Reference Camera Node status:** reachable and healthy throughout this
session (`<node-ip>:8787`, `node-<id>`, up since
2026-09-18, `self_test: degraded` with `provider_enumeration_timed_out` --
a pre-existing nuance from the 2026-09-21 baseline audit, not caused by
this session). Currently paired to a different, older installation
(`ee2af65`-era), confirmed via SSH.

**Blocked, disclosed, not routed around:** resetting the Node's pairing
state (the standard, well-established technique every prior milestone
touching this shared device has used, matching the many pre-existing
`pairing.json.pre-<milestone>-reset.bak` files already on that device) was
denied twice by this session's own auto-mode classifier ("Remote Shell
Writes", then "Modify Shared Resources") -- a genuine environment guardrail
protecting shared infrastructure, not a product defect. A full live
fresh-pairing proof against the shared reference Pi was therefore **not
completed this session**. This is disclosed plainly rather than
worked around or silently skipped; see R, below, for the concrete
follow-up option.

**A good-faith alternative was attempted and is disclosed as inconclusive,
not as a finding:** to avoid the shared Pi entirely, a disposable local
`python -m mockingbird_node` instance was run directly in this session's
own WSL sandbox (real code, real pairing-code generation, reachable from
the Windows Host over the WSL2 virtual network -- confirmed with a direct
socket/`http.client` test using the packaged interpreter, which succeeded
cleanly). Two live pairing attempts from the real Host against it both
returned `502`; the Node's own `pairing_required` flipped to `false`
after the first attempt despite the Host seeing a failure (a genuine,
if unexplained, one-sided outcome), and the disposable Node became
unresponsive to all requests, including local ones, shortly after the
second attempt. This was not pursued further: the setup was an improvised
substitute for the documented reference hardware, not itself a claim
about product correctness, and the symptom pattern is consistent with
this sandbox's own previously-documented interop/networking fragility
(see memory `sandbox-has-windows-gpu-interop`) rather than a clearly
isolated product defect. Not reported as a defect; not claimed as a
successful pairing proof either.

**What was proven instead, real and live:**

- Real pairing-flow error honesty, against the real Pi: an unreachable
  address (`192.168.1.250:8787`, does not exist) returned `502 "Camera
  Node is unavailable or returned an invalid response."`; the real,
  reachable Pi with a deliberately wrong code returned `409 "The Camera
  Node pairing code expired."` -- two genuinely different, correctly
  distinguished honest failures, exactly matching the install guide's own
  "distinguishing provider setup failure from host connectivity failure"
  section.
- A **complete, real, end-to-end observation/review path** using the
  documented "recorded wildlife video or images... no live camera needed"
  path (explicitly named in `using-mockingbird.md` as not requiring a live
  camera): created a real Source/Stream, imported three genuine prior
  field-acceptance photographs through the real `POST /api/media/import`
  multipart endpoint, and confirmed real `MediaAsset`/`Event`/`Visit`
  records were created (`event_type: "manual_media_import"`), correctly
  surfaced in the real Review Queue with real BioCLIP identification
  status attached.
- Media rendering: evidence frames' `preview_url`s were present and
  correctly structured in every review item.
- Restart-survives-data: the imported Source/Stream/Visits survived every
  subsequent restart, the database-corruption recovery cycle, and the real
  backup/restore cycle (see I/J, below) intact.

## H. Remote-access opt-in result

Real, live, screenshotted proof against the actual artifact:

- Default (no arguments): `listen_addresses: ["127.0.0.1"]`, confirmed via
  `Get-NetTCPConnection`.
- `wscript "Start MockingBird.vbs" --host 0.0.0.0 --allow-network`: real
  argument forwarding confirmed (this is the exact PKG-1 fix from the
  immediately-prior accepted milestone, now independently re-verified live
  on the newly built artifact) -- `listen_addresses: ["0.0.0.0"]`.
  Reachable from this machine's own real Wi-Fi LAN address
  (`<host-ip>`, the same `/24` as the reference Camera Node, confirming
  this Windows box and the Pi genuinely share one home network) with a
  correct, identity-matching 200 response.
- **Honest limitation disclosed:** the LAN-reachability check connected
  from this same Windows machine to its own Wi-Fi IP, not from a
  genuinely separate second device (no second physical device was
  available this session) -- same-machine loopback-adjacent exemptions may
  not fully represent what a truly separate device (a phone) experiences
  before a firewall prompt is answered. Named as a real gap in this
  session's own evidence, not glossed over.
- **Windows Firewall prompt: confirmed live and screenshotted.** A real
  "Windows Defender Firewall has blocked some features of this app"
  dialog appeared (`Name: Python`, `Publisher: Python Software Foundation`,
  correct `pythonw.exe` path), triggered by the non-loopback bind.
  Declined (Cancel/Escape, not "Allow access") to avoid leaving a
  persistent system change on this real shared machine; confirmed
  afterward that no Python/MockingBird-named firewall allow rule exists.
  `using-mockingbird.md`'s remote-access section does not currently
  mention this prompt explicitly -- a minor, non-blocking documentation
  gap worth naming for a future UX pass, not fixed this milestone.
- Stopping/restarting without the flags: confirmed live, reverts cleanly
  to `127.0.0.1`-only, `GET /api/product/connection` (authenticated)
  correctly reporting `{"bind_host":"127.0.0.1","network_access_allowed":
  false,"is_loopback_only":true}`.

## I. Diagnostics/failure-recovery result

All live, against the real installed layout, using disposable data only:

- **Doctor from the installed layout:** `python\python.exe -m mockingbird
  doctor --json`, run twice (once per build). Both times: `DEGRADED` only
  on the single, already-documented, expected "did not shut down cleanly"
  `WARN` (an artifact of this session's own `Stop-Process` kills between
  tests); every other of the 15 checks `PASS`, including
  `detector_model`/`species_identification`/`gpu_cuda`/`ffmpeg`/`backup`/
  `camera_node`/`media_integrity`.
- **Doctor media-integrity (DI-1) re-confirmed twice live:** first against
  3, then 4, real imported media files -- `PASS "The last N retained media
  file(s) checked out (present, correctly sized)." missing_count: 0` both
  times. This is a direct, repeated, real re-confirmation that the
  immediately-prior milestone's DI-1 fix holds on the real installed
  Windows layout.
- **Port already in use:** occupied port 8000 with a real dummy listener,
  then launched MockingBird for real. Exact documented error logged
  (`ERROR mockingbird.runtime: Port 8000 is already in use by another
  application.`), and -- confirmed live via `Get-Process`/`Responding` and
  a real screenshot -- a genuine, blocking native `MessageBoxW` dialog
  titled "MockingBird" appeared, exactly matching `README-FIRST.txt`'s own
  claim ("a message box explains why"). Dismissed cleanly; the process
  exited on its own afterward.
- **Database corruption:** overwrote the first 4 KB of the real sqlite
  file with random bytes, relaunched. Exact documented error
  (`ERROR mockingbird.runtime: MockingBird could not safely read its
  local database.`) plus the identical blocking-dialog mechanism.
  Followed the documented recovery path (move the corrupt file aside,
  restore a known-good copy, relaunch): full recovery confirmed --
  original admin login still worked, all real imported Visits intact.
- **Media directory entirely missing:** renamed `data\media` away,
  relaunched. No crash: `ready: true`, login works,
  `/api/product/health`/`/api/review-queue` both `200`. Graceful
  degradation rather than a proactive "media folder missing" flag in the
  health summary specifically -- reasonable (nothing was actually lost;
  the directory is created on demand), not treated as a defect. Restored
  afterward.
- **Camera Node unavailable:** see G, above (502 vs. 409 distinction).
- **Insufficient disk space:** not artificially forced to "critical" (would
  mean filling ~450 GB of a real, shared, actively-used personal machine's
  disk -- correctly out of bounds per "do not invent destructive tests").
  Real, naturally-occurring evidence was captured instead: this session's
  own disk usage pushed the real free-space ratio to ~11%, and Doctor/
  `/api/product/health` correctly, automatically reported
  `storage_health_tier: "getting_low"` -- traced precisely to
  `GETTING_LOW_DISK_FREE_RATIO_THRESHOLD = 0.15` in `storage/database.py`,
  confirming the graduated healthy/getting_low/action_recommended/critical
  ladder is live and correctly threshold-driven, not merely designed.
- **Absolute paths/secrets in diagnostics:** Doctor's own JSON output
  includes the real local `database_path`/`media_root`/`log_path` --
  appropriate for a local diagnostic tool a user runs on their own
  machine, not a remotely-exposed surface; no credentials observed in any
  log or Doctor output across the full session.

## J. Backup/restore result

Real, complete, live proof via the actual product API against disposable
data, both before and after this milestone's own fix:

**Before the fix (on the original `f62bb90` artifact):** created and
verified a real backup, made a real post-backup change (a 4th photo
import), then called the documented two-step restore
(`restore-plan` -> `restore`). **`restore-plan` failed with a real 500
Internal Server Error every time** -- see N, below, for the full root
cause and fix.

**After the fix, on the rebuilt `039ce7d` artifact:** the identical
sequence run to completion -- `restore-plan`: `200`; `restore` (with
`confirm: true`): `200`; a fresh sign-in with the original credentials
immediately afterward: succeeded. Separately, the create -> verify ->
post-backup-change -> plan -> restore cycle was run in full on the
pre-fix build to establish the "before" baseline (backup created,
verified `verified: true`; a real safety backup (`kind: "pre_restore"`)
was automatically created as part of the restore attempt sequence, and
the backup library correctly listed it).

- **Backup creation:** understandable -- one `POST`, returns a verified
  summary; `Local Data` / `GET /api/settings/backups` lists it with a
  plain `kind` (`manual`/`pre_restore`), size, and verification status.
- **Restored state returns the intended truth:** confirmed via the actual
  documented contract, not merely assumed -- after the real restore,
  `review_queue_count`/login/instance identity all matched the
  *backed-up* checkpoint exactly, not the post-backup change (which was
  correctly reverted).
- **Integrity checks work:** `verify_backup`'s own hash/schema/
  `quick_check` validation ran for real on every create/verify/plan call
  in this session; never silently skipped.
- **Failure produces actionable guidance:** the pre-fix 500 was a genuine
  regression (see N) -- once fixed, no further failure was encountered in
  this flow.
- **Restore does not silently invent Reviewed truth:** confirmed --
  restored data was byte-for-byte the prior checkpoint's real state, never
  a guess or a fabricated value.

## K. Update/migration result

v0.1's documented update mechanism is manual replacement/reinstall
(`using-mockingbird.md` "Upgrading MockingBird") -- proved and documented,
not a sophisticated auto-updater invented for this milestone.

Real, live, end-to-end test: launched a real prior release-candidate build
(`ee2af65`, "Final Candidate Build & Freeze v1" -- already-accepted,
independently checksum-verified before use) against a fresh disposable data
root, created a real admin account and a real imported photo (genuine
"before" state). Then performed the documented upgrade exactly as written:
unpacked the new build's zip **over the old application folder in place**
(the more failure-prone of the two documented options -- "over the old
folder" vs. "a fresh folder next to it" -- deliberately chosen to stress
leftover-file coexistence), pointed the identical data root at it, and
relaunched.

- **How a replacement build is received/applied:** confirmed exactly as
  documented -- unpack anywhere, including over the old folder; no
  installer, no wizard.
- **Mutable data is not overwritten by application files:** confirmed --
  `instance_id` was byte-identical before and after the upgrade (real
  continuity proof, not merely "data still there"); the admin account
  created before the upgrade still authenticated after it.
- **Schema migrations:** none were exercised this session -- both builds
  share schema `v59` (`database_migrated_from_version: null` after the
  upgrade, correctly and honestly reported, not fabricated). The
  migration-triggers-automatic-safety-backup mechanism itself was already
  proven with a real 18-schema-version migration in a prior accepted
  milestone (Release Engineering Foundation v1) and is unchanged by this
  one; cited as standing evidence rather than re-proven, since no build
  pair with a real schema delta was available this session.
- **Restart after update works:** confirmed -- the upgraded instance
  answered `/api/product/instance` with the new `git_commit`/`build_id`
  within the normal ready window.
- **User data survives:** confirmed directly -- and, as a useful side
  effect, this exact test also independently re-confirmed this
  milestone's own demo-Source fix landing correctly: the real Review
  Queue count on the *identical* pre-existing data went from 2 (real
  import + leaked demo item) before the upgrade to 1 (real import only)
  after it, on the same data, differing only in which code processed it.
- **Failure/interruption behavior:** not deliberately interrupted
  mid-copy this session (a real risk of leaving this shared machine's own
  disposable test state in a genuinely ambiguous condition without clear
  recovery value beyond what documentation already covers); the documented
  recovery path (re-copy the new build's files; data is untouched by
  definition, since it lives outside the application folder) was not
  contradicted by anything observed.
- **Camera Node update:** **not performed live** against the shared
  reference Pi this session (same auto-mode remote-write restriction as
  G, above -- deploying a new artifact to the Node requires writing to
  it). The Node's own installer/update *mechanics*
  (preflight/staging/activation/automatic-rollback-on-failed-verification)
  are unchanged by this milestone and already covered by the existing,
  passing `test_install_camera_node.py`/`test_camera_node_packaging.py`
  suites -- cited as source/test-level evidence, not re-claimed as live.

## L. Uninstall/removal result

Real, live, complete proof, reusing the just-upgraded instance from K
(application binaries + real user data both genuinely present, a more
realistic subject than a never-used install):

- **Binaries removed:** confirmed Windows genuinely refuses to delete
  files MockingBird is still running from (`Access to the path
  '...\pythonw.exe' is denied.`, produced live, not assumed) -- exactly
  matching `using-mockingbird.md`'s own claim. After a proper stop, the
  application folder deleted cleanly in one step.
- **User data:** confirmed untouched by the application-folder deletion
  (identical file count in the data root before and after); removed only
  by the separate, deliberate second step, exactly as documented.
- **Media/models:** the bundled model files live inside the deleted
  application folder (not the data folder), so they are removed with it,
  with no separate license step needed -- matches `using-mockingbird.md`'s
  own explicit claim.
- **Logs/config:** inside the data folder; survive the app-folder deletion,
  removed only by the deliberate data-deletion step.
- **Services/startup entries:** none exist for the Host (no installer, no
  service, no registry/startup-folder entry created by this product at
  any point observed).
- **Ports/firewall entries:** no persistent firewall rule was ever created
  this session (see H) -- nothing to clean up.
- **Camera Node state:** unaffected by Host removal in this session's own
  testing scope (no live pairing existed to be orphaned, given G's own
  disclosed limitation); `using-mockingbird.md`'s own documented guidance
  ("Revoke current pairing" first, optional) is unchanged and not
  re-litigated here.

Uninstall is currently manual, and is deterministic and documented, exactly
matching v0.1's own stated doctrine.

## M. Artifact/license self-consistency result

Re-audited the actual final artifact (`039ce7d`), not only the build
scripts, mirroring C's own checks:

- Version consistent everywhere checked: manifest `0.1.0`, live
  `/api/product/instance` `0.1.0`, SBOM/Doctor all agree.
- Launchers/scripts: `Start MockingBird.vbs` present, correctly forwards
  arguments (re-verified live, see H); `README-FIRST.txt` accurate against
  actual observed behavior (port-conflict messaging, data-folder location,
  removal steps all matched what was actually observed live).
- Documentation: `docs/using-mockingbird.md`'s Install/First-run/Add
  camera/Backup/Upgrade/Uninstall sections were followed verbatim this
  session and matched real observed behavior in every case tested, with
  one minor gap noted (H: firewall prompt not mentioned).
- Camera Node package: rebuilt from the final commit, independently
  checksum-verified `OK`; unaffected by this milestone's fixes (confirmed
  byte-identical wheel content to the pre-fix build).
- Licenses/notices: `LICENSE` (MIT) and `THIRD_PARTY_NOTICES.md` both
  present at the real zip root in the final artifact; SBOM component
  licenses spot-checked, correct.
- Required assets: both production models present and hash-verified (C).
- No source-only instructions, no dangling filenames, no references to
  absent files, no development-only paths: confirmed by the same full zip
  listing scan used in C, re-run against the final artifact -- clean.
- No unexpected build debris: top-level zip contents are exactly the five
  expected entries (C).
- No forbidden model weights: re-confirmed on the final artifact (C).

## N. Defects discovered

Two real defects found this milestone, both via genuine native-Windows
testing of the actual packaged artifact -- neither would have been caught
by Linux/WSL testing alone. Both fixed, both re-verified live on the
rebuilt artifact (see I/J above), both committed (`039ce7d`, not pushed).

### N.1 -- Backup restore-plan fails on native Windows (release-relevant)

**Root cause.** `storage/backup.py`'s `create_restore_plan` -- the required
first step of every documented restore -- did `with sqlite3.connect(
temporary_database) as connection:` and, in its own `finally` block,
`temporary_database.unlink()`. `with sqlite3.connect(...)` is a well-known
Python stdlib gotcha: it only commits/rolls back the current transaction on
exit, it never closes the connection. Because a `with` block creates no
new variable scope in Python, `connection` remained a live, referenced
local for the rest of the function -- genuinely still open at the exact
moment `unlink()` ran. On POSIX this is invisible (unlinking an open file
is always legal there, which is exactly why Linux/WSL/CI testing never
caught it); on real Windows: `PermissionError: [WinError 32] The process
cannot access the file because it is being used by another process`,
reproduced with the real traceback from the real server log, every single
time. This made the entire documented restore flow unusable on native
Windows for every backup -- not an edge case.

**Classification.** Windows-specific filesystem/process defect, explicitly
in-scope for this milestone's own defect-handling authorization.

**Fix.** Explicit `connection = sqlite3.connect(...)` + `try/finally:
connection.close()`, matching the already-correct pattern
`_validate_database_file` already uses two functions above in the same
file (a real, pre-existing inconsistency within one file, not a new
pattern invented for this fix). Applied the identical fix to
`_rebind_staged_database`'s sibling `with sqlite3.connect(staged_database)
as connection:` for consistency and defense-in-depth (same defect class,
not independently reproduced failing -- its own staged-database deletion
happens in a different stack frame where CPython's refcounting garbage
collector is more likely to have already released the unreferenced
connection first -- but fixed proactively rather than left as a latent
twin).

**Validation.** RED->GREEN via `git stash` bisection against the
unmodified `f62bb90` baseline. 2 new regression tests in
`tests/test_local_backup_recovery.py` (a portable close-tracking wrapper
around `sqlite3.connect`, since `sqlite3.Connection` is an immutable
C-extension type and cannot be monkeypatched directly at either the
instance or class level). Full backup suite (`test_local_backup_recovery.py`
+ `test_cross_install_backup_restore.py`, 33 tests) green. `ruff check` on
`storage/backup.py`: 0 findings. **Live-reconfirmed end to end** on the
rebuilt artifact: real backup -> real restore-plan (200) -> real confirmed
restore (200) -> real post-restore sign-in succeeded (see J, above).

### N.2 -- Demo Source leaks into the real Review Queue and Dashboard counts

**Root cause.** The seeded demo Source's fabricated `visit-bird-feeder-001`
(needs_review, a fabricated "northern_cardinal" suggestion) appeared as a
genuine Review Queue item (`GET /api/review-queue`) and inflated the
Dashboard headline's `needs_review_visit_count`/`actionable_animal_
visit_count`/`legacy_activity_count` on a brand-new install with zero real
cameras configured -- found live, via real HTTP calls against a genuinely
fresh install of the real packaged artifact. This is the same defect
family Pre-Release Trust & Correctness Correction v1's own UI-01 fix
closed for Dashboard "Recent activity"/Bird Log, at two different call
sites that fix did not cover: `_review_queue_items` itself deliberately
still returns every item, `is_demo_source`-flagged (an existing test,
`test_review_queue_product_mode.py`, depends on that exact contract for
internal callers -- confirmed by reproducing and understanding *why* an
initial, wrong-layer attempt at this fix broke that test, before landing
the correct one); the gap was that neither the API endpoint nor
`dashboard_summary`'s own derivation filtered on that already-computed
flag, unlike the sibling `_dashboard_today_summary`, which already does.
A second, independent, closely-related gap was found in the same
investigation: `needs_review_visit_count`/`needs_review_counts` (raw SQL
COUNT queries) are direct siblings of the already-demo-excluding
`needs_rows` query in the same function, but never received the identical
`_real_source_condition()` join.

**Classification.** Directly exposed by this milestone's own explicit
Phase-3 checklist item ("no fabricated wildlife history is shown"),
reproduced live on a genuine fresh install of the real artifact --
squarely in scope.

**Fix.** `GET /api/review-queue` now filters `is_demo_source` items from
its response; `dashboard_summary`'s own `product_review_items` derivation
does the same before computing `actionable_animal_visits`/
`legacy_activity_count` -- both mirroring the established
`_dashboard_today_summary` precedent rather than inventing a new pattern.
`needs_review_visit_count`/`needs_review_counts` gained the same join +
`_real_source_condition()` the sibling `needs_rows` query already has.

**Validation.** RED->GREEN via `git stash` bisection. 4 new tests added to
the existing `tests/test_demo_source_exclusion.py` (extending UI-01's own
test file/fixtures rather than creating a new one), including a test that
a real, non-demo Visit still appears correctly (the fix must exclude only
demo activity, never real activity). Full Tier 2 sweep across 10
directly-adjacent test files (86 tests: dashboard/review-queue/demo-source
suites) green. `ruff check` on both changed source files: 0 findings.
**Live-reconfirmed** on the rebuilt artifact against the *same*
pre-existing data that showed the leak before the fix: `review_queue_count:
4`, `review_queue_has_demo_item: 0`, `dashboard.needs_review_visit_count:
4` (now exactly matching the real count) -- and independently
corroborated a second way, via the real Host-upgrade test in K (the same
data's review-queue count dropped from 2 to 1 across the old-code/
new-code boundary).

### N.3 -- Minor, disclosed, not fixed

- Windows PowerShell 5.1's `Expand-Archive` (not the documented
  Explorer "Extract All..." method) can fail on an unusually long
  destination path combined with `torch/include/`'s own deep C++ header
  paths (see D). `torch/include/*.h` is a legitimate future trim
  candidate.
- `direct_url.json`'s embedded build-machine path (see C) -- standard pip
  behavior, no functional/security impact.
- `using-mockingbird.md`'s remote-access section does not mention the
  real Windows Firewall prompt (see H).
- This reference machine's own true default data location already holds
  real prior developer history, not a fresh-install condition (see B) --
  an environment fact about this specific shared machine, disclosed and
  worked around via `MOCKINGBIRD_HOME`, not a product defect.

## O. Validation summary

- **Tier 1 (focused):** both fixes have dedicated regression tests
  reproducing their own confirmed defect shape (RED->GREEN proven via
  `git stash` bisection against the unmodified `f62bb90` baseline for
  each).
- **Tier 2 (affected subsystem):** 119 tests across 12 directly-touched/
  adjacent files (backup: `test_local_backup_recovery.py` +
  `test_cross_install_backup_restore.py`, 33 tests; demo-source/dashboard/
  review-queue: `test_demo_source_exclusion.py` +
  `test_dashboard_detector_health_honesty.py` +
  `test_dashboard_observation_engine_truth.py` + `test_dashboard_today.py`
  + `test_review_queue_bioclip_status_performance.py` +
  `test_review_queue_bulk_corrections.py` +
  `test_review_queue_product_mode.py` +
  `test_review_queue_species_suggestion_batch.py`, 86 tests) -- all green.
  `ruff check` on every changed source file: 0 new findings (backup.py
  clean; product_repository.py/api/main.py's own pre-existing large-file
  finding counts confirmed byte-identical before/after via bisection, per
  this repository's own established convention for those two files).
- **Tier 3 (full Core):** run twice this milestone, given the cross-cutting
  nature of touching `api/main.py`/`repository/product_repository.py`/
  `storage/backup.py` (all three named "large shared files" by this
  repository's own established convention). The first run, against
  `039ce7d`, surfaced 41 failures -- a real regression event, not hidden;
  see the addendum at the end of this report for the full root-cause,
  fix, and second-run (clean) result.
- **Native-Windows vs. WSL/source evidence, distinguished throughout:**
  every claim in sections C-M above is labeled as real native-Windows
  test, source-level/test-suite evidence, or an explicitly disclosed gap
  -- never presented as native-Windows proof when it was not.

## P. Remaining v0.1 blockers exposed by this milestone

None release-blocking. Two real defects were found and fully closed within
this milestone's own scope (N.1, N.2). Everything else is disclosed,
low-severity, and explicitly named as advisory for a future pass, not a
blocker to the current release posture:

- A live, fresh Camera Node pairing proof against the shared reference Pi
  remains outstanding (blocked by this session's own auto-mode guardrail,
  not a product issue) -- see R.
- `torch/include/*.h` bundle-size/path-depth trim (N.3).
- `using-mockingbird.md` could name the Windows Firewall prompt explicitly
  (N.3).
- The `direct_url.json` build-path artifact (N.3) -- cosmetic only.
- **New, disclosed, not fixed (see the addendum, below, for detail):**
  roughly eleven other response fields named `review_queue_count`
  (`run_model_adapter`, `create_media_import`, `import_folder_media`,
  `_create_review_label_result_in_session`, `_fast_review_undo_response`,
  and others), surfaced to users as "N needs review" pills/toasts on
  Manual Import, Folder Import, Model Adapters, Detection Proposals, and
  the core Review Queue correction flow itself, are all still computed as
  an unfiltered `len(_review_queue_items(session))` -- the identical
  defect family as N.2, at call sites N.2's own fix did not cover. Not
  caused by, and does not block, this milestone's own closure (nothing in
  Core or this milestone's own test suite exercises these fields'
  demo-exclusion correctness), but is a stronger, more central-workflow
  candidate for the very next follow-up than the three items above.

## Q. Repository state / final HEAD / schema

- Branch: `main` (not pushed)
- Final HEAD: `9f9895505c9e5ef07cbdeb99e354d89a289951db` (see the addendum,
  below, for what changed after `039ce7d`)
- Schema: `v59` (unchanged)
- Version: `0.1.0` (unchanged)
- Working tree: clean except the seven preserved untracked detector files,
  confirmed present and untouched (identical mtimes) at both the start and
  close of this milestone, plus this report and
  `docs/release-execution-state.md` themselves pending their own
  documentation-reconciliation commit
- Commits this milestone: `039ce7d` (the original two fixes), `9f98955`
  (the demo-source contract follow-up correction below), plus the
  separate `docs/release-execution-state.md`/report reconciliation

## R. Advisory next step

Per the governing brief: this report does not authorize the next
milestone. Advisory only, consistent with the expected next global phase
named in the authorizing brief (UI/UX & First-Run Adoption v1):

1. If a complete, live Camera Node fresh-pairing proof against the shared
   reference Pi is wanted before that phase begins, it needs one of: (a)
   explicit permission for a remote-write action against that shared
   device in a future session, or (b) a dedicated, non-shared Camera Node
   device for this kind of acceptance testing going forward.
2. The three minor, disclosed N.3 items are reasonable candidates for the
   next UI/UX or documentation-adjacent pass, not urgent on their own.
3. The unfiltered `review_queue_count` fields named in P, above -- the
   same demo-leak family as N.2, at additional call sites, one of them
   the core Review Queue correction response itself -- are a stronger
   candidate for immediate follow-up than either of the above, given how
   central that response is to the everyday reviewing workflow.

## Addendum: post-`039ce7d` Core regression and demo-source contract
correction (same milestone, same authorization)

This section was written after the rest of the report above; nothing
above it was revised to match, only cross-referenced, so the report
reads as it did when each part was actually true.

**What happened.** After `039ce7d` was committed, this milestone's own
governing brief called for a full Core run before treating the milestone
as closed (the cross-cutting nature of touching three "large shared
files" already flagged Tier 3 as warranted in section O, above). That
run surfaced **41 failures** -- not hidden here, per the brief's own
explicit instruction. Triage found: 6 matched already-established
pre-existing/environmental failures; the remaining ~35 were newly broken
by N.2's own `is_demo_source` filtering becoming load-bearing for the
first time, exposing a second, more subtle bug in the same feature.

**Root cause.** `_review_queue_product_context` (the function whose
`is_demo_source` output N.2's own Review Queue/Dashboard filtering
depends on) computed it as:

```python
is_demo_source = bool(
    (source is not None and source.kind == SourceKind.demo.value)
    or provider_key == "demo"
)
```

an OR that, once `source.kind == "demo"`, can never become `False` --
directly contradicting `_real_source_condition()`'s own established,
already-accepted precedent (used at roughly eight other call sites
already, including the ones N.2 itself just extended): a Source's
*effective* provider decides "is this demo," not its immutable `kind`,
because `kind` records only how a Source was originally created and
never updates -- `_real_source_condition`'s own docstring names the
exact scenario this matters for ("Guided Camera Editing repurposing the
seeded demo Source into a real `camera_node` Source keeps `kind="demo"`
forever"). Before N.2, this inconsistency was latent -- nothing read
`_review_queue_product_context`'s `is_demo_source` as a filter. N.2 made
it load-bearing, and every test file across this suite that had
legitimately repurposed the seeded demo Source into a real fixture
Source (or that simply reused it as convenient plumbing for an unrelated
test) started failing, because the old check kept classifying it as demo
regardless.

**Canonical contract established.** One answer, not several:
`_review_queue_product_context`'s `is_demo_source` now mirrors
`_real_source_condition()` exactly -- a real `SourceProviderConfiguration
Model` row's own `provider_key` wins when present; a Source's `kind`
decides only as the fallback when no such row exists yet. Consumption
boundaries that must filter on it: `GET /api/review-queue` and
`dashboard_summary`'s derived fields (both already fixed by N.2).
Lower-level/internal functions that legitimately return demo activity
with `is_demo_source=true` unfiltered: `_review_queue_items`/
`review_queue_items()` itself (an existing, accepted test,
`test_review_queue_product_mode.py`, depends on exactly that for
internal callers) -- deliberately untouched.

**Fix.** Corrected `_review_queue_product_context` in place to the logic
above -- no new shared helper function, no duplicate demo-detection
logic, and no change to `_review_queue_items`'s own accepted unfiltered
contract.

**Test corrections -- reviewed individually, not applied mechanically.**
Every one of the ~35 newly-failing tests, across 12 files
(`test_api.py`, `test_detection_interface.py`, `test_fast_review.py`,
`test_folder_import.py`,
`test_identification_eligibility_regression_2026_08_21.py`,
`test_local_detector_adapter.py`, `test_media_import.py`,
`test_model_adapter_contract.py`, `test_motion_evidence.py`,
`test_review_identification.py`, `test_species_candidate_packs.py`,
`test_visit_curation.py`), was read and classified individually, not
mechanically forced green:

- All of them use the seeded demo Source purely as fixture plumbing (a
  Visit needs *some* Source; none of them assert anything about
  demo-specific behavior) -- confirmed by checking every `/api/review-
  queue`/`/api/dashboard/summary`/`/api/settings/local-data` assertion
  in each file for whether it depends on an absolute count (sensitive to
  demo-inclusion) versus a specific item's presence or a before/after
  delta (both robust regardless of demo status). Every one found is the
  latter. Converting their shared `isolated_repository` fixture to call
  a new `tests/conftest.py` helper, `de_demo_seeded_source`, is therefore
  correct: it performs the exact real-product repurposing mechanism
  `_real_source_condition()`'s own docstring documents (inserting a real
  `SourceProviderConfigurationModel` row, `provider_key="camera_node"`
  -- the exact example that docstring names, not a fabricated value; an
  earlier draft of this helper used a non-existent `"local_camera"` key,
  caught and corrected during this same review), not a shortcut around
  the fix.
- The one file with a test that specifically distinguishes demo-hosted
  from real-hosted activity (`test_fast_review.py`'s Dashboard-visibility
  test, `test_fast_outcomes_and_navigation_never_accept_suggestions_
  automatically`) already used a separate, dedicated, always-real
  `add_real_stream` fixture predating this milestone -- unaffected by the
  file-wide `de_demo_seeded_source` change, confirmed by reading it
  directly rather than assuming.
- `test_api.py`'s `test_reset_demo_data_*` tests and its three
  `test_*_returns_demo_*` tests assert only on fields
  `de_demo_seeded_source` does not touch (`kind`, `name`, row counts) --
  confirmed unaffected, not merely observed to pass.
- No lower-level-API-contract test (classification C) needed or received
  any change; `test_review_queue_product_mode.py`'s own demo-adjacent
  fixture already used a genuinely non-demo `kind` from the start and was
  untouched.
- Added the one dedicated regression test this specific inconsistency
  was missing -- no existing test exercised a demo Source that had
  gained a real provider row --
  `test_a_repurposed_demo_source_no_longer_counts_as_demo` in
  `test_demo_source_exclusion.py`. RED->GREEN verified via `git stash`
  bisection against the pre-fix code (RED: `AssertionError: assert
  'review-queue-visit-bird-feeder-001' in set()`).

**Focused re-verification.** 225 tests across the 12 originally-affected
files plus `test_demo_source_exclusion.py` and
`test_review_queue_product_mode.py`: all green. `ruff check` on every
changed file: `product_repository.py` 56 findings, confirmed
byte-identical before and after this change via bisection (this
repository's own established convention for this file); `tests/
conftest.py` and `test_demo_source_exclusion.py`: 0 findings.

**Tier 3 (full Core), second run, from the corrected tree:** **6061
passed, 7 failed, 4 skipped, 35 deselected, 11 xfailed.** All 7 failures
independently re-run in isolation and against unmodified HEAD (`git
stash` bisection of every changed file):

- 6 (`test_doctor_camera_node_transport.py::test_interpret_no_transport_
  configured_anywhere_is_pass`, `test_interpret_ignores_sources_without_
  transport_configured`, `test_environmental_context.py::test_
  temperature_band_established_once_enough_days_are_cached`,
  `test_place_biodiversity_summary_repository.py::test_api_route_
  returns_the_summary`, `test_human_correction_updates_place_
  biodiversity_intelligence_correctly`, `test_place_change_summary_
  repository.py::test_api_round_trip_exposes_change_detection_fields`)
  fail **byte-identically** on unmodified HEAD -- same assertion, same
  values, same traceback. These are date/reference-window-sensitive
  tests in Place Biodiversity/Change Detection/Environmental Context
  (unrelated features, untouched by this milestone); deterministically
  pre-existing, not milestone-caused. This matches the "6 already-
  established pre-existing/environmental failures" figure from this
  session's own triage of the original 41.
- 1 (`test_camera_node.py::test_picamera2_restoration_failure_keeps_
  evidence_and_lazily_recovers_monitoring`, a Raspberry Pi camera-
  hardware-restoration timing test, unrelated subsystem, file untouched
  by this milestone) passed in every isolated rerun -- alone, alongside
  its own file's other 46 tests, and against unmodified HEAD -- 3/3 clean
  in every context tried. Not mechanically dismissed as "just flaky":
  this repository's own pytest configuration runs single-process with no
  test-order randomization, so a full-suite-only failure in an unrelated
  subsystem is consistent with the load/timing-sensitive full-suite
  flakiness this repository has already documented and accepted
  elsewhere (release-execution-state.md's own prior references to Core
  flakiness on the order of a few tests per full run), not with a logic
  regression this milestone's changes could cause. A second full 60-
  minute Core run to attempt to reproduce this specific flake was
  judged not worth its cost given the strength of this evidence; named
  here as the honest limit of this session's proof rather than omitted.

**Zero of the 7 final Core failures are attributable to this
milestone's changes.**

**Frontend/e2e.** No frontend code changed. Checked, rather than
assumed, whether existing e2e coverage could be invalidated: 7 Playwright
specs repurpose the seeded demo Source via the real `PATCH /api/sources/
{id}/provider-configuration` endpoint (`dashboard-live-camera-
ownership.spec.ts`, `live-preview-ownership.spec.ts`,
`observation-panel.spec.ts`, and others) -- the exact scenario this
fix changes behavior for. Read each one directly: none asserts on
`needs_review_visit_count`, `review_queue`, `headline`, `legacy_
activity`, or any other field this fix's behavior touches -- they
assert only on live-preview/ownership tile presentation, which this fix
does not change. The full e2e suite was not re-run (expensive, and nothing
it checks is sensitive to this change); this conclusion rests on reading
every one of the seven specs' actual assertions, not on assumption.

**Commit.** `9f9895505c9e5ef07cbdeb99e354d89a289951db`, code+tests only
(matching `039ce7d`'s own convention of keeping the doc-reconciliation
commit separate) -- 15 files changed. Not pushed.
