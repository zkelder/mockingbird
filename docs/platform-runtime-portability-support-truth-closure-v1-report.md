# Platform / Runtime Portability & Support Truth Closure v1

A bounded, release-critical **evidence and documentation closure** (Lane O).
Its job was to establish and encode MockingBird's truthful release support
matrix across Host operating systems and inference runtimes -- not to expand
portability. Per its own governing brief, no new platform support was added;
the two production defects found were narrow, reproduced capability-honesty
gaps in an existing diagnostic surface, not new capability.

## Starting state

- **Repository:** `/home/<user>/projects/mockingbird-active`, branch `main`.
- **Starting HEAD:** `d879251` (the reconciliation commit for
  Sustained-Activity Visit Admission Starvation & Stop-Finalization
  Correctness v1; its own implementation commit is `6f7bbb6`) -- matches
  this milestone's own expected starting state exactly.
- **Schema:** `v58`, confirmed directly
  (`CURRENT_DATABASE_SCHEMA_VERSION = 58` in
  `src/mockingbird/storage/database.py:45`) -- **unchanged by this
  milestone** (no model/migration touched).
- **Release platform doctrine (read first, per the governing sequencing
  guard):** `docs/release-execution-state.md` \S1/\S3 confirmed the exact
  expected state (accepted HEAD, schema, latest accepted milestone,
  authorization `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`,
  not pushed -- `git status` confirmed 238 commits ahead of
  `origin/main`, unpushed). Lane O (\S6) read as `PARTIAL -- RELEASE
  DECISION REQUIRED`, listed as release-critical (category A) and
  simultaneously as the one open "pre-release decision" (category B) whose
  resolution mechanism is precisely this kind of truth-matrix milestone --
  not a business/legal call outside this milestone's authority, unlike the
  `LICENSE` decision in Lane P. Lane M, N, and Q all confirmed closed; Lane
  R confirmed open, blocked only on a daylight field-conditions rerun
  (unrelated to this milestone, correctly not attempted here per explicit
  non-goal). `docs/product-doctrine.md` and `docs/roadmap.md` \S"Governing
  priority before release" were read in full; neither required any
  edit -- this milestone's scope is evidence/documentation, not roadmap
  reconciliation. **Sequencing guard: premise held, proceeded.**
- **Worktree safety.** The seven preserved untracked files were present and
  byte-for-byte the expected set at start, confirmed by direct listing
  (identical shared mtime `2026-08-29 21:53:08`, matching a prior session's
  own worktree-restoration moment, not a live edit). No file anywhere in the
  repository had changed in the 90 minutes preceding this session's first
  write (`find -newermt`), and `git status`/`HEAD` were unchanged across
  repeated checks throughout the session -- no active writer.
- **`uv.lock` disposition.** Found untracked, unmodified-tracked (`git
  ls-files uv.lock` empty), not gitignored (`git check-ignore` exit 1), with
  an mtime identical to the seven preserved files' own restoration moment --
  the same "ordinary `uv run`-invocation residue in a shared worktree, never
  a milestone artifact" pattern this file's own history already documents
  across at least six prior milestones (Representative Field Acceptance
  v1/2026-08-25, Place Features & Habitat Change v2, Place Story & Seasonal
  Timeline v1, Mobile & Remote Experience v1, Ecological Interoperability
  v1, Multi-Camera Place Experience v2 -- see
  `docs/release-execution-state.md`'s own repeated disclosures of this exact
  fact). No tracked file (`pyproject.toml`) was modified, ruling out an
  in-progress dependency edit as its cause. Removed per that established
  precedent to restore the normal expected worktree state before
  implementation began; regenerable on demand by `uv`, never committed.

## Canonical support vocabulary

`docs/roadmap.md` \S"Platform / Runtime Portability" (Lane O) already
defines five of these terms verbatim ("directly validated; structurally
supported; hardware-unverified; unsupported; deferred"); this report reuses
that vocabulary rather than inventing a second one, and folds in a sixth,
"Degraded / fallback," which already exists as a real status value in the
product's own health model (`ObservationProviderHealth`'s `"idle"`/
`"degraded"` states in `src/mockingbird/observation/onnx_provider.py:489`;
`DoctorRecoverability.DEGRADED` throughout
`src/mockingbird/diagnostics/doctor.py`) and which the governing brief's own
\S5 explicitly asks this closure to make canonical:

| Term | Meaning |
|---|---|
| **Validated** | Release acceptance completed on the real platform/runtime, with live evidence -- not inference from a similar environment. |
| **Structurally supported** | The repository and dependency stack intentionally support it, and no unguarded platform-specific defect is known, but release-quality hardware acceptance is incomplete. |
| **Degraded / fallback** | Works today with an explicit, honestly-reported capability limitation -- never a silent reduction. |
| **Unverified** | No current release claim; genuinely untested, never assumed to work because a library theoretically could. |
| **Unsupported** | Known not to work, or intentionally excluded, and the product says so rather than failing silently. |
| **Deferred** | Potential future support; explicitly not part of this release's claim. |

One correction this report makes to a prior document's own looser use of
this vocabulary: `docs/species-classification-reevaluation-promotion-v2-report.md`
Phase 10 labeled Linux "Validated (this repo's own dev environment)" for
BioCLIP-2. Under the doctrine this milestone's own governing brief states
explicitly ("Do not promote WSL development success to 'validated native
Linux release support'"), a source-checkout dev-environment success is
**structurally supported / dev-validated**, not a packaged-release
validation. This does not contradict that report's own underlying evidence
(BioCLIP-2 genuinely does run correctly in this repo's Linux dev
environment) -- it tightens the label going forward, consistent with this
milestone's own charter.

## Host matrix

### Windows 10/11 x64 -- **Validated**

The only Host with a real, dependency-bundled, no-Python-required end-user
distributable (`scripts/build_local_product.py` -> `MockingBird-windows-x64.zip`,
documented for end users in `docs/using-mockingbird.md`). Evidence, reused
rather than re-verified, per this milestone's own explicit instruction not
to redo accepted Windows work:

- **Full local-only product acceptance**, no-skip-flags, on a fresh
  disposable install: all 16 named core workflows (startup, sign-in, health,
  streams, Today, Visit/history, review/correction, Bird Log, camera health,
  environmental baseline, storage health, real backup creation, retention
  status, MDv5a local inference, BioCLIP-2 local inference, frontend
  render) -- see
  `docs/native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md`
  \S"Core workflows"/"Model locality".
- **Real CUDA execution-provider selection proven at the production code
  path**, not a status flag: `selected_execution_providers:
  ["CUDAExecutionProvider", "CPUExecutionProvider"]`, model fingerprints
  byte-identical to this project's accepted provenance record, both before
  and after a real internet-denial proof (same report, \S"Model locality").
- **Real 18-schema-version organic migration** (v35 -> v53 at the time) with
  automatic pre-migration backup and a post-migration integrity re-check,
  confirmed via real HTTP against `git_commit`/`database_schema_version`/
  `database_migrated_from_version` -- `docs/release-engineering-foundation-v1-report.md`
  \S"Native-Windows acceptance".
- **Real Windows CUDA DLL-loading defects found and fixed** via native
  hardware repro, not theorized: `os.add_dll_directory()` alone does not
  make `onnxruntime-gpu`'s own provider-bridge DLL resolution work; `PATH`
  must also be set -- see `src/mockingbird/observation/onnx_provider.py`'s
  `_prepare_windows_onnxruntime_dll_search_path` and its own regression
  tests (`tests/test_observation_onnx_cuda.py:673-955`), and the accepted
  provenance record for the validated `onnxruntime-gpu`/CUDA13/cuDNN9
  version combination.
- **CI continuously proves the Windows packaging pipeline's own structural
  correctness** (`.github/workflows/ci.yml`'s `packaging-smoke` job: a real
  `build_local_product.py --skip-gpu-runtime --skip-bioclip-runtime` run
  plus independent `verify_release_artifact.py` verification, on every
  push/PR) -- covering the GPU/BioCLIP-hardware-absent configuration the
  real deployments above do not exercise.

**Limitations, disclosed rather than hidden:** the literal double-click
`Start MockingBird.vbs` experience itself (as opposed to
`deploy_windows_dev.py`'s equivalent programmatic launch of the same real
entry point) and real physical mid-session camera acceptance (RTSP/USB/
DirectShow picture end-to-end) were not exercised in the acceptance session
cited above -- that is Lane G's own separately-tracked scope (classification
**C**, "usable, bounded further closure remains" --
`docs/camera-source-experience-v1-report.md`), not a Lane O gap.

### Linux -- **Structurally supported** (source/dev level); **no packaged
end-user release exists**

Separating dev-under-WSL from native Linux execution from a packaged
release, precisely, per this milestone's own explicit instruction:

1. **Is Linux intentionally supported as an end-user Host at release?** No
   -- `docs/local-product-packaging-design.md:159-163`: "Native Windows is
   the first packaged host... this is the first concrete, validated
   platform," and its own non-goals (`:546-547`) explicitly exclude "Raspberry
   Pi, WSL, or NVIDIA as the product architecture." `docs/release-execution-state.md:2078`:
   "Native Windows remains the first end-user Host acceptance target."
2. **Is it only a development/reference environment?** For the Host app,
   yes today -- `start-mockingbird.sh` (read in full) self-describes as a
   **development-checkout** launcher requiring an already-created `.venv`,
   explicitly distinguished from `build_local_product.py`'s real end-user
   packaging (`README.md`/`docs/using-mockingbird.md` both frame it this
   way: "Linux/macOS checkouts can run `./start-mockingbird.sh`").
3. **Has a clean Linux install ever been release-accepted?** No packaged,
   dependency-bundled, no-Python-required Linux artifact exists at all --
   confirmed by a full `scripts/` inventory: the only Host-packaging scripts
   (`build_local_product.py`, `deploy_windows_dev.py`,
   `verify_release_artifact.py`) are all Windows-target-only, with zero
   `--platform linux`/`--platform macos` flag anywhere in
   `build_local_product.py`'s argparse. No Linux Host counterpart to
   `docs/native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md`
   exists (`find docs -iname '*linux*'` returns nothing).
4. **Are installer/runtime paths portable?** Yes, genuinely --
   `src/mockingbird/runtime.py:127-146`'s `resolve_runtime_home`/
   `_npm_executable` correctly branch on `os.name`/`XDG_DATA_HOME`/
   `Path.home()` with a real POSIX (XDG Base Directory) path, not a
   Windows-only assumption with an untested fallback.
5. **Are there Windows-specific assumptions in production code?** A bounded
   scan of `src/mockingbird/`, `src/mockingbird_node/`, and `scripts/` found
   real Windows-only code (`windows_camera_bridge.py`'s PowerShell/DirectShow
   bridge, `discover_windows_cameras`, DirectShow status branches in
   `product_repository.py`) but **every instance is explicitly platform-
   gated with a graceful, typed, non-crashing `"unsupported_platform"`
   response on Linux** -- zero unguarded Windows-only assumption was found.
   Zero `winreg`/`win32api`/`pywin32`/`shell=True`/`wmic`/`os.symlink()` calls
   exist anywhere in `src/` or `scripts/`.
6. **Does frontend/runtime work?** Yes, continuously, not anecdotally:
   `.github/workflows/ci.yml` runs the full Core pytest gate
   (`backend-tests`), a real `python -m mockingbird --check` structural
   preflight against a fresh runtime home, and the frontend `tsc`/`vite
   build` (`frontend` job) -- **all three `runs-on: ubuntu-latest`**, a real
   native (non-WSL) Linux runner, on every push/PR. `pyproject.toml`/
   `web/package.json` carry zero OS-conditional dependency markers beyond
   `python_version` -- the identical dependency graph installs on Windows
   and Linux.
7. **Does MDv5a run?** The accepted `onnx-cuda` provider is pure Python plus
   `onnxruntime-gpu`, with zero OS-specific branch in
   `src/mockingbird/observation/onnx_provider.py`'s CUDA session-creation
   path itself (the Windows-only code there is exclusively the DLL
   search-path helper, a documented no-op off Windows). Structurally
   expected to behave identically on Linux with a real CUDA/cuDNN install;
   **never separately, directly proven** the way Windows has been --
   classified **structurally supported, hardware-unverified**, not
   validated.
8. **Does BioCLIP run?** Same answer as (7): CPU-only by design (see Runtime
   matrix, below), pure Python/`open_clip`/`torch`, no OS branch -- expected
   to work identically, not separately proven on native Linux hardware
   outside this sandbox's own dev checkout.
9. **Does Camera Node connectivity work?** Yes, and this is genuinely
   validated, not merely structural: this sandbox has real, working LAN
   reachability to the project's reference Camera Node
   (`<node-ip>:8787`) from this Linux environment, exercised repeatedly
   across many prior accepted milestones.

**A real, working, Linux-only feature already exists and is not merely
"Python is portable" residue**: `src/mockingbird/playback/local_camera_bridge.py`
implements a genuine V4L2 local-USB-camera bridge, gated the opposite
direction from the Windows-only code above (`unsupported_platform` on
anything that isn't Linux), wired through the API and repository layers and
documented as "fully built, genuinely usable"
(`docs/camera-source-multi-camera-maturity-v1-contract.md:46`). Native
Linux is not merely tolerated by this codebase; it has at least one
first-class capability Windows does not.

### macOS -- **Unverified** (Host, overall); **Unsupported** (one specific,
disclosed path); **Deferred** (Apple Silicon acceleration)

Bounded archaeology, not a port attempt, per this milestone's explicit
instruction:

- **Packaging support:** none. Zero `dmg`/`.app` bundle/`homebrew`/`coreml`
  hits anywhere in the repository; no macOS build/package/sign/notarize
  script of any kind.
- **Path/process assumptions:** the one real macOS-facing code path
  (`src/mockingbird/observation/audio_capture.py:279-297`) explicitly
  detects any platform that is neither `win*` nor `linux*` and raises
  `AudioDecodeError("unsupported_platform")` -- and this is itself the
  **fix** for a real, previously-disclosed defect (macOS microphone capture
  used to silently reuse Linux's PulseAudio branch instead of failing
  honestly), closed in the already-accepted Acoustic Productization,
  Licensing & Field Acceptance v1 (2026-08-24). Two dedicated regression
  tests (`tests/test_audio_capture.py:125-139`,
  `tests/test_stream_playback_contract.py:6143,7144`) confirm macOS is
  explicitly, honestly refused rather than silently mishandled. This is the
  exact "unsupported and says so" behavior this milestone's own doctrine
  asks for, already precedented in this codebase before this milestone
  began.
- **Model/runtime compatibility:** `onnxruntime-gpu` (the accepted
  detector's own optional dependency) has no published macOS wheel at all,
  so even the accelerated detector path cannot structurally install there.
  BioCLIP's `open-clip-torch`/BirdNET's `ai-edge-litert` stacks are CPU-only
  and generally cross-platform-installable in principle, but neither has
  ever been packaged or tested on real macOS hardware.
- **Frontend/backend compatibility:** no reason to expect a specific defect
  (plain React/FastAPI/SQLite, no Windows-only or Linux-only dependency in
  that layer), but genuinely never exercised on real macOS hardware.
- **Camera/provider support:** none built or claimed.
- **Dependency compatibility:** `pyproject.toml` carries zero
  `sys_platform` markers of any kind -- the same dependency set is declared
  for every OS; nothing in it structurally forbids macOS except
  `onnxruntime-gpu`'s own missing wheel, above.
- **No real macOS machine is available in this environment; no acceptance
  was faked.** `docs/species-classification-reevaluation-promotion-v2-report.md`
  Phase 10 already set the correct precedent this report extends rather
  than re-derives: Apple Silicon marked "Deferred -- no hardware available
  to test" for all three species-classifier candidates, with its own
  explicit statement, "not assumed to work because PyTorch theoretically
  supports it."

**Classification:** Host-level macOS = **Unverified** (no real evidence
either way for the product as a whole); microphone capture specifically =
**Unsupported**, honestly disclosed; Apple Silicon acceleration =
**Deferred** (see Runtime matrix). No macOS port undertaken this milestone,
per explicit non-goal.

## Runtime matrix

### CPU

The most significant, previously-implicit truth this closure makes
explicit: **live wildlife detection cannot run on CPU at all, by deliberate
design -- there is no fallback, and this is a tested guardrail, not a
gap.**

- `src/mockingbird/observation/onnx_provider.py:206`:
  `options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")`
  -- explicitly disables ONNX Runtime's own silent CPU-fallback behavior.
- `onnx_provider.py:213-214`: the session is created with
  `providers=["CUDAExecutionProvider"]` only -- no CPU alternative is ever
  requested.
- `onnx_provider.py:501-502`: `OnnxCudaObservationProvider.load()` raises
  `ReplayValidationError("onnx_cuda_unavailable")` **before attempting a
  session at all** if `"CUDAExecutionProvider" not in providers`.
- `onnx_provider.py:516-518`: raises `onnx_cuda_no_fallback` if CUDA is not
  the first selected provider even after a session is created.
- `src/mockingbird/observation/replay_cli.py:42`, in so many words:
  `"CUDAExecutionProvider is mandatory; CPU fallback is prohibited"`.
- This is regression-tested, not merely asserted:
  `tests/test_observation_onnx_cuda.py::test_onnxruntime_runtime_never_silently_falls_back_to_cpu_on_windows`,
  `::test_onnxruntime_runtime_rejects_session_that_selects_cpu_first_on_windows`,
  and `::test_load_requires_cuda_and_accepts_registered_cpu_when_cuda_is_first`
  (the last proves a CPU-only-available runtime raises `onnx_cuda_unavailable`
  with **zero** session-creation attempts:
  `cpu_runtime.session_creations == 0`).
- This is the real, single production wiring, not one option among several:
  `src/mockingbird/observation/engine_runtime.py:204-205` constructs
  `OnnxCudaObservationProvider(bundle=bundle)` as the one detector backing
  the accepted `frame-driven-onnx-cuda` provider
  (`frame_driven_provider.py:227`, whose own capabilities declare
  `cuda_detector=True` at line 238).

**Species and acoustic assistance are the deliberate opposite: CPU-only by
design, not a fallback, and this is the validated, production-only mode:**

- BioCLIP-2: `BioClipAdapterConfig.device: str = "cpu"`
  (`src/mockingbird/species/bioclip_adapter.py:229`); `_validate_config_files`
  raises `BioClipConfigurationError("The first BioCLIP adapter supports CPU
  execution only.")` for anything else (lines 1445-1448). Real inference
  proof exists at the packaged-Windows production code path (`model_load_ms:
  3141`, `inference_ms: 547`, plausible real output --
  `docs/native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md`
  \S"Model locality").
- BirdNET: `src/mockingbird/species/birdnet_adapter.py:32-36`'s own
  docstring: "CPU-only by explicit design choice (mirrors this product's
  existing BioCLIP precedent...): BirdNET-Analyzer's TFLite model is
  CPU-cheap by construction (a 35-second real clip analyzed in ~1.5s on CPU
  in direct verification)." No device/delegate parameter is ever passed to
  the underlying `birdnetlib.analyzer.Analyzer`. Real, unmocked, gated
  inference proof exists (`tests/test_acoustic_ingest_real_model.py`'s
  `TestRealBirdNetAcceptance`).

**Net, honest release claim:** CPU alone runs the full reviewed-history
product -- Bird Log, review, corrections, imports, exports, analytics,
settings, backup/restore -- and both optional assistance models (species,
acoustic). It cannot create new Visits from live camera activity; that
requires a working NVIDIA CUDA GPU. This is not a theoretical reading of
the code: Doctor's own module docstring
(`src/mockingbird/diagnostics/doctor.py:28-32`) states the design invariant
outright -- "Only Database and Storage can fail 'blocking.' Every other
capability (backup, Camera Node, FFmpeg, detector model, species
identification, GPU/CUDA) is optional/degradable by product doctrine -- an
install with none of them configured, or one of them broken, remains a
usable MockingBird install" -- and its own `SPECIES_IDENTIFICATION` WARN
branch says plainly, "Wildlife Visits can still be created; species
suggestions are unavailable" (`doctor.py:1658`).

`onnxruntime-gpu` is declared as an **optional** dependency
(`pyproject.toml`'s `[project.optional-dependencies].observation-onnx-cuda`,
never a core dependency) -- the base package installs and runs with zero
GPU-related dependency at all. CPU is not claimed "supported" merely because
ONNX can instantiate a CPU provider; the accepted provider explicitly
forbids exactly that.

### NVIDIA CUDA -- **Validated** (Windows); **structurally supported,
hardware-unverified** (Linux)

The strongest currently-evidenced accelerated path, reused rather than
retested per this milestone's own instruction:

- Real CUDA execution-provider selection proven at the production code path
  on native Windows, both before and after internet denial, byte-identical
  model fingerprints (see Host matrix, above).
- The validated `onnxruntime-gpu`/CUDA13/cuDNN9 version combination and its
  Windows packaging closure (per-package DLL nesting depth handled by an
  `rglob`-based search, not an assumed fixed depth) are already recorded
  provenance, reused unmodified this milestone.
- Three real, independently-discovered Windows DLL-loading bugs were found
  and fixed via native hardware reproduction in a prior milestone (not
  retested here, per this milestone's explicit "reuse accepted evidence"
  instruction) -- `AddDllDirectory` alone does not satisfy
  `onnxruntime-gpu`'s own internal provider-bridge dependency resolution;
  `PATH` must also be updated.
- GPU health/reporting: Doctor's `GPU_CUDA` check
  (`doctor.py:1670-1707`, corrected this milestone -- see Defects, below)
  and the real per-Stream Observation-session health path
  (`engine_runtime.py:907-943`) both report this honestly.

**Minimum truthful release claim** (not maximum theoretical compatibility,
per this milestone's own instruction): NVIDIA CUDA on native Windows is
validated for production wildlife detection. The identical code path is
expected to behave the same on Linux with a real CUDA/cuDNN install (zero
OS-specific branch in the CUDA session-creation logic itself), but this has
never been separately, directly proven on real Linux hardware --
**structurally supported, hardware-unverified** there, not validated.

### Apple Silicon / Metal / MPS -- **Deferred**

- No active MPS selection code exists anywhere in the accepted production
  path. The only `"mps"` string in the entire repository is a passive
  label-echo in `src/mockingbird/detectors/megadetector_adapter.py:449-450`
  (`if "mps" in device_value: return "mps"`) -- a post-hoc string match on
  whatever device the **superseded, non-accepted, legacy PyTorch**
  `megadetector` package already reports, never an active request for MPS.
  This adapter is not the accepted production detector (that is the
  `onnx-cuda` provider, above); it is the same legacy path the pre-existing
  `small-bird-benchmark-files-superseded` project memory already documents
  as coupled to a different, non-production runtime.
- Zero `coreml`/`rocm`/`directml`/real "Metal" hits anywhere in `src/`,
  `scripts/`, or `docs/` (a "metal" hit in one field-acceptance report is a
  literal physical camera-mount pole, unrelated).
- `onnxruntime-gpu` has no published macOS wheel, so the accepted
  detector's own optional dependency cannot install on Apple Silicon
  regardless of MPS.
- No accepted hardware evidence exists, and this report does not manufacture
  any: `docs/species-classification-reevaluation-promotion-v2-report.md`
  already disclosed this precisely ("Apple Silicon and AMD remain genuinely
  untested -- this session had no such hardware... disclosed as deferred,
  not assumed to work because PyTorch theoretically supports it"); this
  closure extends that same discipline to the detector and to the platform
  matrix as a whole rather than re-deriving it. **No model-conversion
  campaign undertaken**, per explicit non-goal.

### AMD GPU -- **Unsupported**

Zero ROCm, DirectML, or other AMD-specific runtime path exists anywhere in
the current stack -- confirmed by direct, repository-wide grep, zero hits.
No inference from generic ONNX compatibility is made. Stated plainly: AMD
GPU acceleration is not implemented, not tested, and not claimed. No ROCm/
DirectML implementation undertaken this milestone, per explicit non-goal.

## Camera Node

### Reference hardware

Raspberry Pi 4 Model B, Raspberry Pi OS (Debian 13 "trixie", `aarch64`) --
this project's real, repeatedly-used reference device, with genuine,
repeated hardware acceptance across install, reboot, reprovision/
replacement, upgrade, and boot-identity/watchdog milestones (see
`docs/release-execution-state.md` Lane L). This is validated hardware, not
merely a documented target.

### Structural portability -- genuinely hardware-agnostic where it counts

`src/mockingbird_node/providers.py` defines one `CameraNodeProvider`
Protocol with three real backends behind it, plus a graceful degradation
wrapper:

- `PiCamera2Provider` (Raspberry-Pi-specific: `picamera2`/`libcamera`).
- `V4L2CameraProvider` -- a real, independent, **generic Linux/USB-camera**
  path: enumerates `/dev/video*` and captures via OpenCV, entirely
  Pi-independent.
- `SyntheticCameraProvider` -- test-only, rejected outside
  `MOCKINGBIRD_NODE_TESTING`.
- `UnavailableCameraProvider` -- when a provider's runtime dependency is
  missing, `cameras()` returns `"setup_required"` rather than crashing the
  whole Node.

The default configuration (`MOCKINGBIRD_NODE_PROVIDERS=auto`) runs **both**
`v4l2` and `picamera2` concurrently via `CompositeCameraProvider`, each
independently degrading if its own runtime is absent. Both
`docs/camera-node-install-guide.md` and `docs/camera-node-installer-design.md`
are already explicit and correctly worded on this point -- "Pi 4 is not an
architectural requirement," "A generic Debian-family Linux box works too...
this installer never fails the whole install over an optional provider
dependency" -- this milestone confirms that claim against the real code
rather than restating it uncritically.

This satisfies this milestone's \S15 requirement directly: the support
matrix does not say "MockingBird requires Raspberry Pi." The actual
contract, already correct in existing docs and now cross-verified against
`src/mockingbird_node/providers.py` itself, is: Camera Node software is
hardware-agnostic by protocol/architecture; Raspberry Pi 4 is the
reference, validated hardware.

### Validated limits

No non-Raspberry-Pi hardware has ever been acceptance-tested end to end.
The `V4L2CameraProvider` path is real, exercised code (unit-level), but
"hardware-agnostic" here means the protocol/software does not
architecturally require Pi hardware -- it does **not** mean arbitrary
Linux/ARM camera hardware has been release-validated. This report does not
claim otherwise, and no new Camera Node hardware was tested or added this
milestone, per explicit non-goal.

## Capability reporting

**What is already honest today, verified rather than assumed:**

- The real, per-Stream Observation-session capability signal
  (`ObservationSessionStatusResponse.engine_available`/`engine_message`,
  fed by `engine_runtime.py:907-943`'s classification of the real CUDA
  session-load outcome via `_UNSUPPORTED_GPU_CODES`) is genuine, not a
  static flag -- it reflects whatever `OnnxCudaObservationProvider.load()`
  actually did. `web/src/components/ObservationControlPanel.tsx` reports
  Camera health and Observation health **separately** by explicit design
  ("a successfully paired, reachable camera must never read 'Needs
  attention' merely because the *Observation* runtime... is what actually
  failed"), and deliberately hides CUDA/ONNX/Stage vocabulary from ordinary
  users, reserving it for the collapsed advanced-diagnostics disclosure --
  matching `docs/product-doctrine.md`/`docs/architecture.md`'s existing
  Capability-aware UX doctrine exactly. `docs/using-mockingbird.md`'s
  pre-existing claim ("If your PC's graphics card is not supported,
  MockingBird says so directly instead of guessing or silently running in
  a reduced mode") is real, verified behavior, not aspirational copy.
- `python -m mockingbird doctor` is the deepest capability-truth surface
  (`DETECTOR_MODEL`, `SPECIES_IDENTIFICATION`, `GPU_CUDA` checks), and its
  own module docstring states the governing design invariant outright:
  every one of those capabilities is "optional/degradable by product
  doctrine" -- absence of an optional model does not imply total product
  failure, matching this milestone's \S13 requirement precisely.
- `GET /api/product/health` deliberately does **not** carry GPU/detector/
  species fields -- confirmed by direct schema inspection, not an
  oversight: it is documented as a "basic-first" aggregate reusing
  dashboard/storage/backup facts, and the real GPU-specific truth already
  reaches the user at the correct, more specific surface (per-Stream
  Observation health) rather than a global flag that could go stale across
  unrelated Streams.

**Found and fixed -- two narrow, reproduced capability-overclaim defects, both
in `python -m mockingbird doctor`** (see Defects, below).

**Found, disclosed, not fixed -- zero live user impact confirmed:**
`GET /api/observation-engine/status` (`ObservationEngineStatusResponse`)
is a naming red herring: `get_observation_engine_registry()`
(`src/mockingbird/api/main.py:1724-1727`) wires a `SnapshotObservationProvider`
wrapping the legacy external-URL snapshot monitor, **not**
`OnnxCudaObservationProvider` -- its `health`/`capabilities` never reflect
real MDv5a/CUDA state despite the name. Confirmed via direct grep that
**the frontend never calls this endpoint at all**
(`grep -rn "observation-engine/status" web/src/` -- zero hits): this is a
real internal naming/wiring inconsistency, but not a reproduced
user-facing defect (nothing renders it as if it were the real detector's
status). Recorded here as a precise, actionable future-cleanup item, not
fixed this milestone -- rewiring it correctly would mean touching core
registry construction for a currently-dead code path, out of proportion to
a bounded evidence closure.

## Defects

Two reproduced, narrow capability-honesty defects were found and fixed,
matching this milestone's own named example almost verbatim ("capability
health claims BioCLIP available when runtime cannot load it"). Both are
pure disclosure fixes -- neither changes what is checked, only what is
truthfully said about what was checked -- and both were proven RED against
the real pre-fix code via `git stash`, then GREEN after, per this
project's established convention.

1. **`doctor.py::_interpret_species_identification`'s `"available"` branch
   silently dropped the caveat its own upstream data already computed.**
   `get_bioclip_status()` (`bioclip_adapter.py:417-483`) is explicitly
   documented to "inspect explicit local readiness **without loading a
   model**," and its own `"available"` response already discloses this
   scope honestly in its `detail` text: "Explicit local BioCLIP artifacts
   are configured. A run still validates the precomputed embedding cache
   before returning suggestion evidence." `_gather_species_identification`
   (`doctor.py:1625-1632`) captured that exact `detail` string -- then
   `_interpret_species_identification`'s PASS branch (`doctor.py:1637-1643`)
   discarded it, returning an unqualified "BioCLIP species-suggestion
   runtime is available" with no `detail` at all, unlike its own two
   sibling branches in the same function (both of which do carry
   `detail=`). Concretely: a truncated, bit-flipped, or wrong-version
   weights file of a plausible size would still make this status check
   read "available," since weight-content hashing only happens on a real
   run (`_validate_config_files`'s `hash_model_weights` defaults to
   `False` here, by the same function's own deliberate design for
   performance -- `get_bioclip_status()` is also called from
   `dashboard_summary()`, a hot path the accepted "BioCLIP Status / Review
   Queue Performance v1" milestone specifically optimized down to
   sub-2-second response time; hashing weights on every call would
   reintroduce exactly that regression). **Fix:** restore
   `detail=gathered.get("detail")` on the PASS branch -- zero behavior
   change to the underlying check, zero performance cost (the string was
   already computed), just stops throwing away context every sibling
   branch already keeps.
   - RED confirmed: `git stash push -- src/mockingbird/diagnostics/doctor.py`,
     then `test_interpret_species_identification_available_discloses_what_pass_does_not_verify`
     failed (`AssertionError: assert None == 'Explicit local BioCLIP...'`).
   - GREEN confirmed after `git stash pop`.
2. **`doctor.py::_interpret_gpu_cuda`'s `"available"` branch overclaimed
   what its own probe actually checked.** `_gather_gpu_cuda`
   (`doctor.py:1670-1675`) calls
   `OnnxCudaObservationProvider.unconfigured().probe()`, whose
   `cuda_available` field is computed purely as `"CUDAExecutionProvider" in
   onnxruntime.get_available_providers()` (`onnx_provider.py:180-188,464`)
   -- this reports which execution-provider shared libraries were
   **compiled into the installed package**, not whether this host's real
   NVIDIA driver/CUDA/cuDNN stack can actually initialize a session. The
   codebase's own real per-Stream load path (`onnx_provider.py:495-519`)
   treats this exact gap as real enough to guard against -- it performs an
   actual `InferenceSession(...)` call and separately verifies
   `session.get_providers()[0] == "CUDAExecutionProvider"`, precisely
   because a provider can be nominally "available" yet still fail to
   resolve its real CUDA/cuDNN dependencies at session-load time (the
   whole reason the Windows DLL-search-path machinery exists). Doctor's
   own `_interpret_gpu_cuda`, though, returned an unqualified "CUDA
   execution provider is available" PASS with no such caveat. Concretely: a
   host with `onnxruntime-gpu` installed but a broken/mismatched/absent
   NVIDIA driver would have Doctor report an unqualified PASS, right up
   until the next real Observation start hit `onnx_cuda_session_load_failed`
   via a code path Doctor never exercises. **Fix:** add a `detail=` to the
   PASS branch disclosing exactly this scope (confirms the provider is
   detected, not that a session was proven to load; points to the real
   per-Stream Observation health as the surface that proves the stronger
   claim) -- a wording-honesty fix, deliberately **not** a heavier "attempt
   a real GPU session load inside every `doctor` invocation" rewrite, which
   would conflict with Doctor's own documented "bounded, side-effect-free"
   design invariant and meaningfully change its resource/performance
   profile for a secondary, on-demand diagnostic tool -- out of proportion
   to what this defect actually needs.
   - RED confirmed the same way:
     `test_interpret_gpu_cuda_available_discloses_it_is_not_a_real_session_load`
     failed (`assert None is not None`) against the stashed pre-fix code.
   - GREEN confirmed after `git stash pop`.

**Disclosed, not fixed (not reproduced against any real or currently-shipping
path, correctly bounded per this milestone's own defect rule):**

- `src/mockingbird_node/config.py:211-221` -- `pairing_state_path` still
  falls back through `state_home = Path.home() / ".local" / "state"` when
  `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` is unset, the identical shape of
  defect already found and fixed for `transport_spool_dir`/
  `transport_credential_state_path` in the same file (commit `baf9fdb`,
  confirmed still fixed by direct reading of the current tree). It is
  masked only by operational convention: `scripts/install_camera_node.py`
  always writes this environment variable explicitly into every `node.env`
  it produces (`_default_node_env_content`/`_render_node_env`). Not proven
  broken today -- no installer-managed device is affected -- so it is
  disclosed as a latent structural risk (a hand-built systemd unit bypassing
  the installer, or a future regression to the installer's own env-writing
  code, would reproduce it), not fixed under this milestone's bounded
  scope.
- `pyproject.toml`'s `observation-onnx-cuda` extra
  (`onnxruntime-gpu>=1.18,<2.0`) carries no `sys_platform` marker, so
  `pip install .[observation-onnx-cuda]` would fail to resolve on macOS or
  non-x86_64 platforms. This affects only a developer's own optional-extra
  install -- the real shipped Windows product pins its own exact copy
  separately and explicitly in `scripts/build_local_product.py`, untouched
  by this gap. A developer-experience rough edge, not a release defect.

## Release claims

Exact user-facing claims now published in `docs/using-mockingbird.md`'s new
"Platform & hardware support" section (placed immediately after the guide's
intro, ahead of the Windows install steps, with "Other supported hosts" at
the end cross-referenced back to it rather than duplicating it):

- **Windows 10/11 (64-bit):** Supported and validated -- MockingBird's
  primary, release-tested platform, including GPU-accelerated wildlife
  detection.
- **Linux:** Structurally supported for a development checkout; tested
  continuously by MockingBird's own automated tests; no packaged download,
  no dedicated hardware acceptance yet.
- **macOS:** Not yet verified, not part of this release; microphone-based
  bird-sound identification specifically is known not to work and says so.
- **Wildlife detection:** requires a supported NVIDIA graphics card, no
  CPU fallback, by design -- says so directly rather than guessing.
  Everything else (history, review, import, backup, settings) works
  without one.
- **Species/sound identification:** run on any regular processor, no
  graphics card needed; their absence never blocks Visit creation.
- **Apple Silicon and AMD graphics cards:** not supported today, not
  claimed merely because underlying libraries theoretically could.
- **MockingBird Camera Node:** Raspberry Pi 4 is the validated reference
  hardware; the software itself does not require a Raspberry Pi
  specifically, but only the Pi 4 path has been tested end to end.

## Validation

This closure is primarily evidence/documentation; the one production change
is two narrow, isolated `detail=`/wording additions in
`src/mockingbird/diagnostics/doctor.py`, confirmed by direct grep to be
called from nowhere except `doctor.py` itself (via `run_doctor`) and tested
only in `tests/test_doctor.py` -- a textbook Tier 1 (focused) situation, not
a cross-cutting change, so a ceremonial full Core run was correctly not
performed, per this milestone's own \S19 instruction.

- **`tests/test_doctor.py`** (full file, including 2 new regression tests
  proving the two fixes above RED-then-GREEN): **107 passed, 0 failed.**
- **`tests/test_doctor_cli.py`** (directly adjacent, the CLI wrapper around
  the functions changed): **8 passed, 0 failed.**
- **`ruff check`** on both changed files
  (`src/mockingbird/diagnostics/doctor.py`, `tests/test_doctor.py`): clean,
  zero findings.
- **Worktree safety reconfirmed** at close: exactly the seven preserved
  untracked files plus this milestone's own new/modified files; no peer
  writer activity detected throughout (repeated `git status`/`HEAD`
  checks unchanged; no file-mtime activity anywhere in the repository
  outside this session's own edits).

No CPU-only-inference measurement was newly run: the accepted detector
provider structurally forbids CPU execution (see Runtime matrix), so there
is no CPU inference path to measure for the detector, and BioCLIP-2/BirdNET
CPU performance is already real, accepted, cited evidence (`inference_ms:
547` for BioCLIP-2 at the packaged-Windows production code path; "~1.5s"
for a 35-second BirdNET clip) reused rather than re-measured, per this
milestone's own instruction not to repeat validations that already exist.

## Remaining gaps

**Release blocker:** none identified. Native Windows -- the only Host the
current scheduler names as a launch requirement -- has strong, extensively
evidenced support across install, startup, migration, backup, GPU/CUDA,
BioCLIP, frontend, and Camera Node connectivity, reused correctly rather
than re-verified.

**Unsupported/deferred (not release blockers, by explicit product/scheduler
doctrine):**

- macOS as a Host (Unverified overall; microphone capture specifically
  Unsupported and says so).
- Apple Silicon GPU acceleration (Deferred, no hardware available).
- AMD GPU acceleration (Unsupported, no runtime path exists).
- A packaged, end-user Linux distribution (Structurally supported at the
  source/dev level only; not attempted this milestone, per explicit
  non-goal -- "Do not add major new platform support").
- Camera Node hardware beyond the Raspberry Pi 4 reference device
  (Structurally plausible via the real `V4L2CameraProvider` abstraction;
  never release-tested).

**Unverified future capability, precisely scoped for whoever picks it up
next:**

- Direct NVIDIA CUDA acceptance on native Linux hardware (expected to work
  given zero OS-specific branch in the CUDA code path itself; never
  separately proven).
- `src/mockingbird_node/config.py`'s `pairing_state_path` `Path.home()`
  fallback, latent but unreproduced (see Defects, above).
- `GET /api/observation-engine/status`'s naming/wiring mismatch with the
  legacy `SnapshotObservationProvider` (see Capability reporting, above) --
  a real internal-cleanup opportunity, zero live user impact confirmed.

## Decision

**Classification A.**

Every intended release platform/runtime now has an honest, cross-verified
status; the native Windows release claim is strongly evidenced (entirely
reused from already-accepted milestones, correctly, per this milestone's
own instruction not to redo accepted work); unsupported/unverified
platforms (macOS, Apple Silicon, AMD, packaged Linux) are precisely
disclosed, never overclaimed; CPU/GPU behavior is now truthfully and
explicitly described for the first time as a single coherent story (the
detector requires CUDA with zero fallback, by tested design; both optional
assistance models are CPU-only, by tested design); the Camera Node
reference-hardware-vs-hardware-agnostic-protocol distinction is explicit
and verified against real provider code, not merely asserted; product
capability reporting was found materially honest already at its primary
(per-Stream Observation health) surface, and the two narrow overclaims
found in the secondary Doctor CLI surface were fixed with reproduced
RED/GREEN evidence; user-facing support docs
(`docs/using-mockingbird.md`) now state exactly what the implementation
evidence supports, no more and no less; and no release-blocking portability
ambiguity remains for the one platform the current scheduler actually
requires for launch. Lane O's own "RELEASE DECISION REQUIRED" status is
resolved by this report, not deferred further.

---

# Final response

- **Classification:** **A**.
- **Starting HEAD:** `d879251` (schema `v58`, unchanged).
- **Implementation HEAD (this session, pre-reconciliation-commit):**
  the working tree at the two `doctor.py`/`test_doctor.py` edits described
  above, not yet committed at the time this report was written (commit
  sequencing follows this project's own established
  implementation-then-report-then-reconciliation convention).
- **Schema:** `v58`, unchanged.
- **`uv.lock` disposition:** untracked generated residue, removed to
  restore the expected worktree state, matching six prior milestones'
  identical, already-documented disposition of the same file.
- **Native Windows status:** Validated -- strongly evidenced, entirely
  reused from already-accepted milestones (Native-Windows Packaged
  Local-Only Acceptance & Privacy Closure v1, Release Engineering
  Foundation v1), no re-verification needed or performed.
- **Linux status:** Structurally supported at the source/dev level,
  continuously CI-validated on real (non-WSL) `ubuntu-latest` for the full
  Core suite, frontend build, and the Windows-packaging pipeline's own
  structural smoke test; **no packaged end-user Linux distribution
  exists**, and no dedicated native-Linux hardware acceptance has ever been
  performed -- not promoted to "validated release Host."
- **macOS status:** Unverified overall (no real hardware available, none
  faked); microphone capture specifically Unsupported and already says so
  (fixed in a prior accepted milestone); Apple Silicon acceleration
  Deferred.
- **CPU status:** Detector (MDv5a): Unsupported, by deliberate, tested
  design -- zero fallback, fails loudly and honestly instead. Species
  (BioCLIP-2) and acoustic (BirdNET) assistance: Validated, CPU-only by
  design, not a fallback -- both already have real production/packaged
  evidence.
- **NVIDIA CUDA status:** Validated on native Windows (the strongest
  currently-evidenced accelerated path); structurally supported,
  hardware-unverified on native Linux specifically.
- **Apple Silicon status:** Deferred -- zero active MPS selection code in
  the accepted production path; no hardware available; no model-conversion
  campaign undertaken.
- **AMD status:** Unsupported -- zero ROCm/DirectML/AMD-specific code
  anywhere in the stack; nothing implemented this milestone.
- **Camera Node support truth:** Raspberry Pi 4 / Raspberry Pi OS is the
  real, repeatedly-validated reference hardware; the Camera Node's own
  software is genuinely hardware-agnostic by protocol (a real
  `CameraNodeProvider` abstraction with an independent, generic
  `V4L2Camera Provider` USB/Linux path alongside the Pi-specific one, both
  gracefully degrading if unavailable); no non-Pi hardware has ever been
  release-tested. No Camera Node hardware expansion undertaken.
- **Capability-reporting result:** materially honest already at the
  primary user-facing surface (per-Stream Observation health, verified
  real, not a status flag); two narrow capability-overclaim gaps found and
  fixed in the secondary `python -m mockingbird doctor` CLI tool (both
  wording-honesty fixes, zero behavior/performance change); one dead-code
  naming/wiring inconsistency (`/api/observation-engine/status`) found,
  confirmed to have zero live frontend consumption, and disclosed rather
  than fixed.
- **Defects found/fixed:** 2 (Doctor's `SPECIES_IDENTIFICATION` and
  `GPU_CUDA` PASS branches silently dropping/omitting an honest scope
  caveat), both reproduced RED via `git stash` against the real pre-fix
  code and confirmed GREEN after, each with a dedicated new regression
  test. 2 further gaps found and precisely disclosed, deliberately not
  fixed (not reproduced against any real or currently-shipping path,
  correctly bounded per this milestone's own defect rule).
- **Validation performed:** `tests/test_doctor.py` full file (107 passed),
  `tests/test_doctor_cli.py` (8 passed), `ruff check` clean on both changed
  files -- Tier 1/focused, matching the change's own confirmed, isolated
  blast radius; full Core not run, correctly, per \S19's own instruction
  for a primarily evidence/documentation closure.
- **Exact release support claims:** as published in
  `docs/using-mockingbird.md`'s new "Platform & hardware support" section
  (quoted in full under "Release claims," above).
- **Remaining platform risks:** none release-blocking. Two disclosed,
  unreproduced, non-blocking code-level gaps (Camera Node
  `pairing_state_path` `Path.home()` fallback; the `/api/observation-engine/status`
  naming mismatch) recorded precisely for future cleanup; macOS/Apple
  Silicon/AMD/packaged-Linux remain honestly unverified/deferred/
  unsupported, not release blockers per current product/scheduler doctrine.
- **Lane O:** **Closed** -- the matrix is complete, the one platform the
  scheduler requires for launch (native Windows) remains unambiguous and
  strongly evidenced, and no unsupported hardware was claimed supported to
  reach this closure.
- **Current authorization state:** unchanged --
  **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.** This closure
  does not authorize Gate A's next daylight rerun, External Pre-Release
  Acceptance, or Final Release Hardening, and does not select a next
  development milestone.
- **Ready/not ready for ChatGPT acceptance review:** ready.
