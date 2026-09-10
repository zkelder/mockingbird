# Local Product Packaging and First-Run Design

**Roadmap phase:** 27 -- release acceptance (packaging, first-run setup, and a
dependable local product).

**Product flow improved:** install/unpack -> launch -> guided first-run setup
-> add/pair a camera -> Start observing -> Stop -> restart, all without the
user ever typing a developer command.

**Why this is next:** the core product loop (Source/Stream -> Zone ->
Observation -> Review Queue -> correction -> history) already works. Before
this phase, reaching it required a development checkout, a Python virtual
environment, and `npm` -- MockingBird behaved like developer software in how
it was launched, configured, and first opened. This phase does not change the
product loop itself.

## Scope boundary

This phase adds first-run detection/onboarding, a packaged distributable
artifact, host-disk storage status, and a consolidated basic health view. It
composes existing capabilities -- guided Add Camera
([source-provider-configuration-contract.md](source-provider-configuration-contract.md),
[camera-node-boundary-design.md](camera-node-boundary-design.md)), the unified
Observation panel
([unified-observation-panel-contract.md](unified-observation-panel-contract.md)),
and backup/restore
([local-backup-recovery-design.md](local-backup-recovery-design.md)) -- rather
than re-implementing any of them. It does not touch the Observation Engine,
detectors, trackers, or candidate authority.

Developer tooling for deploying/verifying a build this phase produces on a
Windows development machine (never end-user packaging itself) is a separate,
later addition -- see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md).

## First-run detection and persistence

`AppSetupStateModel` (schema version 29, `app_setup_state` table) is a single
durable row: `completed`, `current_step`, `last_created_stream_id`,
`updated_at`. It is the only signal that gates onboarding -- never inferred
from current Source/Stream counts, so a user who later removes every camera
does not see onboarding again.

Seeding uses the one genuine "is this database brand new" fact
`initialize_database` (storage/database.py) already computes when deciding
whether to run numbered migrations at all:

- A **brand-new** database (no schema-version row existed yet) seeds
  `completed=False, current_step="welcome"` directly in
  `initialize_database`.
- A **pre-existing** database migrating through schema 29 (any installation
  from before this phase, including via a normal upgrade) seeds
  `completed=True, current_step="done"` inside the `_migrate_to_app_setup_state`
  migration function itself -- so an established installation never sees the
  wizard. The migration guards against a row already being present (a
  downgrade-replay test fixture, or any future re-entrant call) by never
  overwriting an existing row.

`GET/PUT /api/setup/state` is the only read/write surface. **Updated by
Local Identity, Multi-User & Organization Access v1 (2026-08-23; see
[local-identity-multi-user-contract.md](local-identity-multi-user-contract.md)):**
the frontend (`OnboardingWizard.tsx`) now gates rendering the wizard
globally (every route, not the dashboard-route-only scope originally
described here) -- once most `/api/*` reads require a real signed-in
session, a deep link during a fresh install showing the normal shell with
no way to sign in would be a dead end rather than a harmless early look.
`reviewed-product-loop.spec.ts` and the rest of the shared Playwright
suite are unaffected by this in practice: `web/e2e/global-setup.ts`
bootstraps a real Administrator and marks setup complete once before that
whole suite runs, so those deep links never actually encounter an
incomplete-setup state during a normal test run.

The wizard is a thin orchestrator, not a new implementation:

1. Welcome -- what MockingBird does, in plain language.
2. **Account** (added by the milestone above) -- creates this Host's first
   Administrator; every later step needs a real session, so this comes
   right after the purely-informational welcome step and before anything
   that reads real data. On success the browser is already signed in, with
   no separate sign-in step.
3. Storage -- shows the resolved local data folder (not the database
   filename -- see "Storage status" below), current usage, host free space,
   and writability; does not add a relocation UI (that remains the existing
   `MOCKINGBIRD_HOME`/`MOCKINGBIRD_DB_URL` advanced/developer lever).
4. Camera -- embeds the existing, **unmodified** `CameraSetupPage`, which
   already implements choose-type -> Camera Node pairing or provider fields
   -> validate -> preview -> draw/confirm Zone -> save. Its own "Discard
   setup" action doubles as "skip for now" in this context.
5. Observe -- embeds the existing, **unmodified** `ObservationControlPanel`
   for the newly created Stream, plus "Finish setup".

Completing the camera step calls the existing `POST
/api/settings/remove-sample-data` (best-effort, already exposed and already
used elsewhere in Local Data) so a fresh install's auto-seeded demo
Source/Stream is replaced by the user's real camera instead of sitting
alongside it -- no new backend behavior.

Progress persists after every step transition, so a reload, a closed tab, or
an app restart mid-wizard resumes at the saved step. A `GET /api/setup/state`
failure fails the gate open (treated as complete) rather than trapping an
existing user behind a broken wizard.

## Storage status

`StorageSummary` gained `disk_total_bytes`, `disk_free_bytes`, `is_writable`
(`storage/database.py`'s `probe_local_storage_disk`, a real bounded
write-and-delete probe against the directory holding the database file --
not `os.access`, which can misreport effective writability, notably on
Windows ACLs). This is a **host-disk** fact, distinct from the existing
managed-media-relative `storage_warning`; both now feed the same field, with
low free space (below 1 GB or below 5% of total, whichever is more
conservative) folded in additively. Nothing about existing managed-media
accounting changed.

The onboarding Storage step and Local Data page show the containing
**folder**, never the raw database filename -- showing `mockingbird.sqlite3`
would itself be a small SQLite-internals leak to a non-technical user; a
folder path answers "where is my data" without it.

## Product health

`GET /api/product/health` is one bounded, basic-first aggregate, reusing
(never recomputing) `dashboard_summary` (camera-attention list, observation
counts), `storage_summary`, the existing backup library, and
`mockingbird.__version__`. Advanced-only facts (`database_schema_version`,
`log_path`) stay out of the basic fields, matching the Observation panel's
existing basic/advanced split. `ProductHealthPanel.tsx` renders it as one
panel on the Dashboard -- not a new page, per the product non-goal against an
admin-control-center redesign.

## Runtime lifecycle: crash marker and log location

`mockingbird/runtime_state.py` is a small module with no dependency on either
`runtime.py` or `api/main.py` (both already depend on each other in narrow,
deferred ways to avoid a real import cycle; this avoids adding a third edge).

- `prepare_runtime_state(runtime_home)`: read the previous run's marker file
  (`runtime_state.json` in the runtime home), report whether it said "clean"
  (previous run reached its own shutdown path), "starting" (it did not --  a
  crash, a forced kill, or a host power loss), or absent (first run ever
  against this data directory), then write "starting" for the current run.
  Only the real launch path in `runtime.py` calls this -- **not** `--check`,
  which must stay side-effect-light so repeated validation runs never make
  the next real launch think the previous one crashed.
- `mark_clean_shutdown()`: called last in `_app_lifespan`'s shutdown path
  (`api/main.py`), after every other runtime component has actually stopped,
  using the `runtime_home` remembered from `prepare_runtime_state` rather
  than re-resolving it (re-resolving independently risks landing on a
  different default path than the one the running process actually started
  from).
- `configure_file_logging(runtime_home)`: adds one rotating file handler at
  `<runtime home>/logs/mockingbird.log` to the root logger. It never removes
  or replaces uvicorn's own console handler; it exists so a normal user has
  one predictable, fixed place to find logs regardless of launch method (a
  terminal, or a packaged bundle's silent launcher with no console at all).

## Packaging decision

**Chosen: a self-contained "unpack and run" Windows folder/zip, built by
`scripts/build_local_product.py`.** Native Windows is the first packaged host
(the product architecture stays host-neutral -- see
[architecture.md](architecture.md)); this is the first concrete, validated
platform.

Rejected:

- **Electron** -- MockingBird is already a normal browser-rendered local web
  app served by its own backend; wrapping it in a second UI runtime adds a
  large new dependency surface for no product capability the existing
  same-origin static-serving architecture (`web_app.py`) does not already
  provide. The product non-goals explicitly reject this absent clear proof
  it is needed.
- **Docker/a Windows service/systemd unit** -- the wrong mental model for
  local desktop software a non-technical user unpacks and double-clicks; it
  would also complicate the very LAN-local, plain-HTTP Camera Node pairing
  this product depends on.
- **"Install Python first"** -- fails the hard product rule outright (a
  normal user must not need to know Python/pip/venv exist).

A wheel remains an **internal** build artifact (built via `pip wheel .
--no-deps`, unaffected by this phase's packaging beyond the `web_dist`
inclusion below); it is not the deliverable, since installing it still
requires Python/pip. The actual deliverable bundles a real Python runtime and
every dependency:

1. Build the frontend and copy `web/dist` into `src/mockingbird/web_dist/`
   -- the path `web_app.resolve_frontend_dist` already prefers over the dev
   checkout's `web/dist`, previously unused. `pyproject.toml` gained
   `[tool.hatch.build.targets.wheel] artifacts` so this gitignored,
   build-time-generated directory still ships in the wheel (hatchling only
   includes VCS-tracked files by default).
2. Build the MockingBird wheel.
3. Fetch the official CPython **embeddable distribution** for Windows
   (python.org's own zero-install, app-local Python, built for exactly this
   scenario) and pre-install every runtime dependency for `win_amd64`/`cp312`
   into it at *build time*, on this (Linux) build host, via `pip install
   --target ... --platform win_amd64 --python-version 3.12 --implementation
   cp --abi cp312 --only-binary=:all:`. `uvicorn` is requested **without**
   its `[standard]` extra: that extra depends on `uvloop`, which has no
   Windows wheels and is gated by a `sys_platform != "win32"` marker that
   pip's cross-platform download does not evaluate against the *target*
   platform (only the host's) -- it would otherwise try, and fail, to
   resolve uvloop for Windows. MockingBird does not use anything from
   `uvicorn[standard]` (uvloop, httptools, websockets, watchfiles,
   python-dotenv, PyYAML, colorama); it runs on uvicorn's default asyncio
   loop and h11 HTTP implementation.
4. Patch `python312._pth` to add `site-packages` to the interpreter's search
   path -- the documented, minimal way to make a flat `pip install --target`
   layout importable without enabling the `site` module (which would also
   need pip/setuptools present, which this bundle deliberately omits: the
   end user's machine never runs pip).
5. Write one launcher, `Start MockingBird.vbs`, that runs `python\pythonw.exe
   -m mockingbird` with a hidden window -- a real double-click experience,
   no console flash, no typed command.
6. Write `manifest.json`/`SHA256SUMS` (mirroring the existing convention in
   `scripts/build_camera_node_artifact.py`) and zip the folder with fixed
   per-entry timestamps, so byte-identical input produces a byte-identical
   archive across rebuilds (verified: two independent full rebuilds from the
   same source tree produced the identical SHA-256).

None of this requires anything beyond `npm` and network access on the
**build** machine; the produced bundle requires neither on the machine that
later runs it. A discovered, unrelated latent bug was fixed as part of
validating this path: `mockingbird.observation.evidence_scoring` unconditionally
imports Pillow, which was previously declared only under the optional
`observation-onnx-cuda` extra and happened to be present in this development
checkout's environment transitively; it is now a core dependency in
`pyproject.toml` (and in the Windows bundle's requirement list) -- without
it, a genuinely minimal install cannot boot at all, on any platform.

A parallel, much smaller **host-neutral Linux/macOS launcher**,
`start-mockingbird.sh` (mirrors the existing `Start MockingBird.cmd`'s
venv-detection logic), keeps the underlying architecture demonstrably not
Windows-specific; it is what this phase's own Linux-side validation uses. The
same embeddable-runtime technique this phase validated for Windows could
extend to a Linux/macOS one-click bundle later (not built this phase).

## Observation runtime packaging (Native Windows Observation Runtime v1)

The first real native-Windows acceptance pass reached "Start observing"
against a real, durably-paired, reachable Camera Node and failed there with
`invalid_frame_driven_configuration`. Root cause, traced through
`ObservationEngineSessionManager` -> `_load_real_provider` ->
`FrameDrivenProviderConfiguration.load`: the packaged artifact shipped none
of the four things the accepted `frame-driven-onnx-cuda` provider needs
(provider config, model bundle, `onnxruntime-gpu`, CUDA/cuDNN redistributable
libraries), and the one config path it *did* look for
(`MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH`'s fallback,
`data/models/observation-frame-driven/provider-config.json`) was resolved
relative to `os.getcwd()` -- which `runtime.py`'s `run_preflight` already
`os.chdir()`s to the runtime home (`%LOCALAPPDATA%\MockingBird`) before the
API ever loads, a directory with no relationship to the install folder any
packaged asset ships in. This phase composes the already-accepted engine
(Stage 3 ONNX-CUDA, Stage 4 frame-driven, Stage 5 Camera Node live-shadow,
Stage 7 candidate authority) into the packaged artifact; it does not change
any of their internals, thresholds, or authority semantics.

- **Path resolution.** `mockingbird.observation.engine_runtime.
  packaged_observation_runtime_root` resolves `<installed package>/
  observation_runtime/` from `Path(__file__)`, the same "packaged asset next
  to this installed package" convention `web_app.resolve_frontend_dist`
  already established for `web_dist`. `resolve_provider_config_path`'s order
  is now: explicit override -> `MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH`
  (still honored, never required) -> the packaged root above -> the
  historical developer convention, now resolved against `find_workspace_root()`
  instead of cwd -> the packaged-root path anyway (an honest "missing" load
  failure, never a guess). Every step is independent of `os.getcwd()`, so
  restarting MockingBird from a different working directory cannot change
  which configuration resolves.
- **Model bundle provenance.** `scripts/build_local_product.py`'s
  `package_observation_runtime_assets` copies the already-accepted MDv5 ONNX
  bundle (docs/megadetector-runtime-findings.md's approved `md-v5a` artifact,
  MIT-licensed, exported to ONNX and validated with a real NVIDIA GPU during
  the Observation Engine v2 Stage 3 activation:
  `cuda_only_verified`, 886/886 CUDA-executed model nodes) from a local,
  ignored, developer/CI-supplied directory (`--model-bundle-source`,
  defaulting to the existing `data/models/observation-onnx-cuda` convention)
  into `<site-packages>/mockingbird/observation_runtime/`, independently
  re-verifying every SHA-256 against the two hashes this project has
  actually accepted (`ACCEPTED_SOURCE_MODEL_SHA256`/
  `ACCEPTED_ONNX_MODEL_SHA256`) before copying anything. No model file is
  ever committed to git, and no model is ever downloaded at build or run
  time; a build with no local source available still produces a working
  artifact whose Observation Engine honestly reports a missing-model state
  until an operator supplies one and rebuilds.
- **GPU/CUDA runtime.** `WINDOWS_GPU_RUNTIME_REQUIREMENTS` (`onnxruntime-gpu
  ==1.28.0`, exact-pinned to the version already validated against this
  model with a real GPU) and `WINDOWS_CUDA_REDISTRIBUTABLE_REQUIREMENTS`
  (`nvidia-cuda-runtime`/`nvidia-cuda-nvrtc`/`nvidia-cublas`/`nvidia-cufft`/
  `nvidia-curand`/`nvidia-cudnn-cu13`, the same CUDA 13/cuDNN 9 versions
  reused read-only from the primary runtime during that activation) are
  pip-installed into the bundle with the same cross-platform `pip install
  --target ... --platform win_amd64` technique as every other dependency
  (`install_windows_gpu_runtime_dependencies`, toggled by
  `--skip-gpu-runtime`). This "unpack and run" product has no system CUDA
  Toolkit and no PATH entry for one, so
  `onnx_provider._prepare_windows_onnxruntime_dll_search_path` adds each
  redistributable's DLL directory to the process's DLL search path
  (`os.add_dll_directory`, Windows-only) before `onnxruntime` is ever
  imported. The existing Stage 3 CUDA-only contract is completely unchanged:
  `disable_cpu_ep_fallback`, mandatory `CUDAExecutionProvider` first, and
  bounded execution-profile verification still reject any CPU/mixed
  execution outright -- packaging adds no new fallback path, silent or
  otherwise. A PC without a compatible GPU/driver still gets an honest,
  plain-language "unsupported GPU/runtime" state rather than a guess or a
  silent slow path.
- **Camera-vs-Observation health.** `_EngineSession` now reports the Camera
  Node as configured (`camera_connected=True`) immediately once its pairing
  is validated -- *before* attempting the Observation Engine load -- so a
  later engine failure (missing model, unsupported GPU) can never again
  leave the stale "Not yet connected to the Camera Node." fact sitting next
  to an unrelated Observation runtime problem, which is exactly what the
  real acceptance pass hit. Engine failures are classified into two honest,
  distinct plain-language categories (`missing_model_or_runtime`,
  `unsupported_gpu`) from the already-existing bounded error codes the
  provider/bundle loaders raise -- no new failure mode is invented. The
  basic-tier message never tells a user to set an environment variable;
  `ObservationControlPanel.tsx` renders "Camera" and "Observation" as two
  separate basic-tier facts.
- **Release-build source integrity.** A real build previously ran `pip wheel
  .` directly against the live checkout; hatchling's default file selection
  includes any untracked-but-not-gitignored file physically present under
  `src/mockingbird/` with no warning, and one leaked into a real release
  wheel this way. `build_wheel` now compiles from a `git archive` snapshot
  of a verified commit (`verify_clean_tracked_source`/
  `export_clean_source_tree`) rather than the live tree -- an untracked file
  is now structurally impossible to package, not merely discouraged. An
  uncommitted modification to an already-tracked packaged-input file (the
  one remaining real ambiguity `git archive` alone cannot resolve) still
  fails the build by default; `--allow-dirty-source` opts out for local
  iteration on the build script itself, never for a release artifact.
- **Frontend build freshness (v0.1 Release Hardening v1).** The clean-
  source guard above only ever covered `src/mockingbird`/`pyproject.toml`/
  `README.md` -- `web/` was never in scope, and `--skip-frontend-build`
  had no freshness check at all: it packaged whatever bytes already sat at
  `web/dist` (or a stale leftover `src/mockingbird/web_dist/`, which
  `resolve_frontend_dist` prefers whenever present) with no comparison
  against current `web/src`. `build_frontend` now stamps a real SHA-256
  fingerprint of every frontend build input (`compute_frontend_source_
  fingerprint` -- `web/src/**` plus the handful of root-level files that
  affect compiled output, deliberately excluding e2e/Playwright
  configuration) into `web/dist/frontend-source-fingerprint.json`
  immediately after a real build. `--skip-frontend-build` now verifies
  this stamp (`verify_frontend_dist_freshness`) against current source and
  refuses the build by default -- both a genuine mismatch and a `dist`
  with no stamp at all (an older build, or one assembled some other way)
  are treated as "not fresh," never assumed safe -- mirroring
  `--allow-dirty-source`'s own refuse-by-default shape exactly.
  `--allow-stale-frontend` opts out explicitly, for local/development
  iteration only, never for a release artifact; either way, `manifest.json`
  now records `frontend_source_state` (`built`, `reused:verified_fresh`,
  or `reused:stale_allowed`) so a resulting artifact's own provenance
  record discloses which happened, never silently.
- **BioCLIP/idna packaging conflict (v0.1 Release Hardening v1).** The
  Camera Node Installer milestone's own real Windows redeploy had to use
  `--skip-bioclip-runtime` after hitting a real duplicate-`.dist-info`
  failure (see "Windows redeploy" in
  [camera-node-installer-design.md](camera-node-installer-design.md)).
  Root cause, confirmed against real installed package metadata: `anyio`
  (in `WINDOWS_RUNTIME_REQUIREMENTS`, the always-installed core tier)
  unconditionally requires `idna>=2.8` with no upper bound, and
  `install_windows_runtime_dependencies` has no wheel cache -- it always
  does a live online resolve, so it silently installs whatever `idna` is
  newest on PyPI at build time. `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS`
  separately pins `idna==3.18` for its own offline-wheel-cache
  reproducibility. Two independent `pip install --target` calls into the
  same flat site-packages then produced two different `idna-*.dist-info/`
  directories -- exactly the corruption class `verify_no_duplicate_
  site_packages_metadata` already exists to catch, and did. Unlike
  `Pillow`/`numpy`/`anyio` itself (each already exact-pinned in the
  BioCLIP tier to match what the core/GPU tier resolves), `idna` had no
  matching pin in `WINDOWS_RUNTIME_REQUIREMENTS` to synchronize against --
  the precise, narrow gap. Fixed by adding that one missing pin
  (`idna==3.18`, matching the already-validated BioCLIP-tier version) to
  `WINDOWS_RUNTIME_REQUIREMENTS`; no other dependency, model, or runtime
  behavior changed. `test_real_windows_bioclip_dependency_closure_
  installs_offline_with_no_duplicates` -- previously failing for exactly
  this reason -- now passes.

## BioCLIP runtime packaging (Automatic Species Suggestion v1.2)

Same problem, same solution, for the separate optional BioCLIP species
-suggestion adapter (`mockingbird.species.bioclip_adapter`): the adapter
already worked correctly once manually installed, but a normal packaged
deploy installed neither its ~150 MB Python runtime dependency closure nor
its ~1.6 GB local model bundle, and a real acceptance pass needed a one-shot
`MOCKINGBIRD_BIOCLIP_MODEL_PATH`/`_LABELS_PATH`/`_EMBEDDING_CACHE_PATH`
environment-variable injection at every single launch to work at all. This
milestone makes that installation/configuration durable without touching
BioCLIP inference logic, the crop resolver, or same-frame evidence at all.

- **Path resolution.** New `mockingbird.species.bioclip_runtime.
  packaged_bioclip_runtime_root` resolves `<installed package>/
  bioclip_runtime/` from `Path(__file__)`, mirroring `engine_runtime.
  packaged_observation_runtime_root`'s identical convention exactly. Three
  new `resolve_bioclip_{model_dir,labels_path,embedding_cache_path}`
  functions each resolve with the same order: explicit override -> the
  existing `MOCKINGBIRD_BIOCLIP_*` environment variable (still honored,
  never required) -> the packaged root's own fixed file for it, only when
  that file genuinely exists. `product_repository._bioclip_config` now
  calls these instead of a bare `os.getenv`. Deliberately **no** third
  "development checkout convention" fallback the way the Observation Engine
  has (`data/models/observation-frame-driven/...`, resolved against
  `find_workspace_root()`): that convention's own path does not exist in a
  normal checkout, so it is a safe no-op there, but the real local BioCLIP
  evaluation bundle this project actually uses during development
  (`data/models/bioclip-2/`) *does* exist on disk in this checkout --
  auto-discovering it would have silently changed "no environment variable
  set" behavior from the existing, widely-relied-on "not configured" test
  contract to "configured". A bare development checkout keeps using the
  unchanged, explicit environment variables exactly as before; only an
  actual packaged build gets the new automatic default.
- **Model bundle provenance.** `scripts/build_local_product.py`'s new
  `package_bioclip_runtime_assets` copies the already-accepted local
  BioCLIP 2 artifact (docs/model-selection.md's "Supported local BioCLIP 2
  artifact": Imageomics `imageomics/bioclip-2`, MIT-licensed) from a local,
  ignored, developer/CI-supplied directory (`--bioclip-bundle-source`,
  defaulting to the existing `data/models/bioclip-2/` convention) into
  `<site-packages>/mockingbird/bioclip_runtime/`, independently
  re-verifying each of the four expected files' SHA-256 against the
  `ACCEPTED_BIOCLIP_*_SHA256` constants this project has actually accepted
  before copying anything -- looked up by fixed filename individually, so
  the other local evaluation-scratch files this same source directory also
  holds are never accidentally packaged. Exactly the same "missing bundle
  is an honest, non-fatal state" contract as the Observation model.
- **Dependency closure.** `install_windows_bioclip_runtime_dependencies`
  pre-installs `WINDOWS_BIOCLIP_RUNTIME_REQUIREMENTS` -- the adapter's
  complete win_amd64/cp312 runtime closure (`torch`/`open_clip_torch`/
  `safetensors`/`timm`/`huggingface_hub`/... -- every package actually
  reached transitively from `open-clip-torch`, `pyproject.toml`'s existing
  `classifier-bioclip` extra) -- into the same flat site-packages layout,
  via `--extra-index-url https://download.pytorch.org/whl/cpu` (PyPI alone
  has no CPU-only Windows `torch` wheel under the plain name; a bare
  cross-platform resolution from this Linux build host was also observed to
  waste several hundred MB speculatively evaluating `torch`'s Linux-only
  CUDA-toolkit extras during backtracking). Every package is exact-pinned,
  determined by really running this exact install rather than reading
  package metadata by eye -- not merely for the usual reproducibility
  reason, but because a real, empirically-reproduced defect makes it a
  correctness requirement: a *second*, independent `pip install --target`
  call into an already-populated site-packages (this is the third such call
  in the pipeline, after the core and GPU tiers) resolves any loosely
  -bounded dependency shared with an earlier tier (`Pillow`, `numpy`,
  `anyio`) *independently of what already exists on disk* -- observed for
  real: `Pillow` resolved to a freshly-released 12.3.0 here while the
  actual `PIL/` code on disk silently remained the core tier's
  already-installed 11.3.0, because `pip install --target` never overwrites
  an already-existing file but still writes a second, differently
  -versioned `.dist-info/` next to it. New `verify_no_duplicate_site_
  packages_metadata` (run once, after all three dependency-installing
  steps) fails the whole build outright the moment it finds two
  `.dist-info/` directories for the same PEP 503-normalized package name,
  closing this exact corruption class regardless of which pair of installs
  produces it in the future. The adapter itself never imports this closure
  outside its own isolated worker subprocess (`bioclip_adapter.
  _bioclip_worker_loop`), so packaging it cannot slow down or destabilize
  ordinary MockingBird startup, with or without BioCLIP configured.
- **Runtime/model cache.** `scripts/deploy_windows_dev.py`'s existing
  three-tier runtime/model cache (see "Runtime/model cache" in
  docs/windows-dev-deployment-design.md) gains a second, fully independent
  model tier for `bioclip_runtime/` -- its own content hash
  (`compute_bioclip_model_hash`), its own cache root
  (`BIOCLIP_MODEL_CACHE_DIRNAME`, a sibling of the Observation model's own
  `models/`), and its own junction into each release
  (`ensure_bioclip_model_cache`/`materialize_release`). A change to either
  model can never force an unnecessary re-copy of the other, and an
  ordinary app-only redeploy reuses both existing model caches untouched,
  never re-copying either ~1.6 GB or ~500 MB bundle.
- **Deployment-time verification.** New `verify_bioclip_runtime` (called by
  `deploy()` after every successful deployment, never fatal to it) runs the
  *deployed release's own* `python.exe` against a small embedded script
  (`BIOCLIP_RUNTIME_CHECK_SCRIPT`) that really `import`s every module the
  adapter needs and calls the existing, side-effect-free `get_bioclip_
  status`. This is deliberately a *real* import, not the adapter's own
  cheap `importlib.util.find_spec`-based status check
  (`_missing_runtime_packages`): `find_spec` succeeds the moment a
  package's directory/metadata exists, even when actually importing it
  would fail deep inside its own `__init__.py` for a missing transitive
  dependency -- the exact real incident (`sympy` missing for `torch`) a
  previous manual acceptance pass hit, invisible to the app's own status
  page until an actual local run was attempted. Reported in `DeployReport`
  (`bioclip_verification`), never raised -- BioCLIP remaining optional and
  unavailable-safe is a product requirement, not just a build nicety.
- **No one-shot environment injection.** The ad hoc workaround this
  milestone removes: a previous manual acceptance pass launched the
  packaged release with the three `MOCKINGBIRD_BIOCLIP_*` variables
  injected by hand into `launch_release`'s `extra_env` on every single
  start, and a separate, non-junctioned `PYTHONPATH` directory of manually
  copied `torch`/`open_clip` files. Neither survives a restart or redeploy
  on their own; both are gone. `launch_release` itself is completely
  unchanged (still only ever sets `MOCKINGBIRD_HOME`/
  `PYTHONDONTWRITEBYTECODE`) -- BioCLIP configuration now comes entirely
  from files on disk (the packaged `bioclip_runtime/` bundle, resolved by
  `packaged_bioclip_runtime_root`), which is what makes it durable across a
  restart or a redeploy by construction rather than by remembering to
  reinject anything.

## Release-artifact SBOM and signing (Final Release Hardening & Launch Readiness v1)

Roadmap's "Public release readiness" list names "release artifacts/
versioning/checksums/SBOM/signing where practical" as a real, previously
-deferred item. Checksums (`SHA256SUMS`) and provenance (`manifest.json`)
already existed; this milestone adds the remaining two, each only as far as
this project's existing toolchain makes practical and maintainable --
no new build-time dependency, no PKI/signing-infrastructure project.

**SBOM.** `generate_release_sbom`/`write_release_sbom` produce a real,
minimal CycloneDX 1.5 `sbom.json` next to `manifest.json`/`SHA256SUMS`,
hand-built with the standard library `email` parser reading every installed
package's own real `*.dist-info/METADATA` (name, version, and license --
preferring the modern PEP 639 `License-Expression`, falling back to a
`License ::` classifier, then the legacy free-text `License` field) -- the
same source `importlib.metadata` itself resolves from, never a
requirements-list guess. Also lists the embedded CPython runtime and,
only when a build actually packaged one, the two redistributed model
artifacts (MDv5a ONNX, BioCLIP 2) with their already-accepted SHA-256 and
license. Unconditional and never optional, unlike the model bundles
themselves: every official build gets one. `write_manifest` records a
`sbom` field (format/file/component count/hash) and `SHA256SUMS` gains a
third entry for it; `verify_release_artifact.py`'s own checksum loop was
generalized to verify *every* entry it lists, not only the historical
zip/manifest pair, so a tampered or missing `sbom.json` is caught the same
way a tampered zip already was.

**Signing.** `sign_release_artifact` produces a detached, ASCII-armored GPG
signature over `SHA256SUMS` (`SHA256SUMS.asc`) -- the standard "sign the
checksums file, not each large binary" open-source convention, so one small
signature covers the zip, manifest, and sbom together. Never invents,
guesses, or defaults to an ambient keyring key: a key id must be passed
explicitly (`build_local_product.py --sign-key-id <id>`, or the
`MOCKINGBIRD_RELEASE_SIGNING_KEY_ID` environment variable). No key
configured -- the default for every build to date, including this
milestone's own release candidate -- is an honestly-reported, non-fatal
state recorded in `manifest.json`'s new `signing` field
(`{"requested": false, "key_id": null}`); a *configured* key that fails to
sign raises `LocalProductBuildError` and fails the whole build, the same
"the operator explicitly asked for this" contract every other non-optional
step in this script already follows. `manifest.json`'s `signing` field
records build-time *intent* only (whether a key was configured and which
one), resolved before signing is attempted -- it cannot self-report signing
*outcome* over its own already-finalized bytes without becoming circular.
The outcome is instead proven externally: a real `SHA256SUMS.asc` existing
alongside `SHA256SUMS` and verifying against it.
`verify_release_artifact.py` only reports whether `SHA256SUMS.asc` is
present (informational); it deliberately never attempts cryptographic
verification itself, since that would require assuming or importing some
public key, and this verifier runs generically in CI and for any downstream
consumer, never only the owner.

**Owner-facing signing procedure (not performed by this milestone -- no
real key exists yet).** Generating or holding a release signing key is an
owner decision this repository's own automation must not make for itself.
When the owner is ready to sign real public releases:

1. Generate a real GPG keypair offline and keep the private key secure
   (a hardware key or an offline machine is stronger than a laptop
   keyring, but either is a real improvement over no signing at all):
   `gpg --full-generate-key` (RSA 4096 or ed25519).
2. Publish the **public** key and its fingerprint somewhere a downloader
   can independently verify belongs to the project (the GitHub release
   notes, a dedicated page linked from `README.md`, and/or a public
   keyserver) -- never only inside the artifact it is meant to authenticate.
3. Build with `--sign-key-id <fingerprint>` (or set
   `MOCKINGBIRD_RELEASE_SIGNING_KEY_ID`); the build fails loudly if signing
   does not succeed, so a release is never silently shipped half-signed.
4. Publish `SHA256SUMS.asc` alongside `SHA256SUMS`/the zip. A downloader
   verifies with `gpg --verify SHA256SUMS.asc SHA256SUMS` after importing
   the published public key, then checks the zip's own hash against the
   now-trusted `SHA256SUMS`.
5. Keep the private key offline between releases; a compromised signing
   key is worse than no signing key, since it lets a real attacker's
   artifact appear authentic.

## Files allowed

- `src/mockingbird/storage/models.py`, `storage/database.py` (schema 29);
- `src/mockingbird/repository/product_repository.py` (setup-state, storage
  disk fields);
- `src/mockingbird/api/schemas.py`, `api/main.py` (new routes);
- `src/mockingbird/runtime.py`, new `src/mockingbird/runtime_state.py`;
- `web/src/components/OnboardingWizard.tsx`,
  `web/src/components/ProductHealthPanel.tsx`, and the existing pages/client/
  types files they integrate with;
- `pyproject.toml`, `.gitignore`, new `scripts/build_local_product.py`, new
  `start-mockingbird.sh`;
- Native Windows Observation Runtime v1 additionally touched
  `src/mockingbird/observation/engine_runtime.py` (path resolution, camera/
  engine health facts, error-message categorization -- lifecycle wiring
  only, no detector/tracker/authority change), `observation/onnx_provider.py`
  (Windows DLL search-path wiring only), `web/src/components/
  ObservationControlPanel.tsx` (one additive status line), and
  `scripts/build_local_product.py` (model bundle/GPU runtime packaging,
  clean-source-snapshot release integrity);
- BioCLIP runtime packaging (Automatic Species Suggestion v1.2)
  additionally touched new `src/mockingbird/species/bioclip_runtime.py`
  (packaged-root path resolution only -- `bioclip_adapter.py` itself is
  untouched), `repository/product_repository.py` (`_bioclip_config` now
  calls the new resolvers instead of a bare `os.getenv`, one function
  body only), `scripts/build_local_product.py` (BioCLIP dependency
  closure/model bundle packaging, duplicate-site-packages-metadata
  verification), and `scripts/deploy_windows_dev.py` (a second,
  independent BioCLIP model cache tier; deployment-time runtime
  verification; no packaging/deploy mechanism invented, the existing one
  reused a second time);
- Final Release Hardening & Launch Readiness v1 additionally touched
  `pyproject.toml`/`src/mockingbird/__init__.py`/
  `src/mockingbird_node/__init__.py`/`web/package.json`/
  `web/package-lock.json` (version bump only -- see
  `tests/test_version_provenance.py`'s existing single-source-of-truth
  contract, unchanged in shape), `scripts/build_local_product.py` (SBOM
  generation, optional release signing -- see "Release-artifact SBOM and
  signing," above), `scripts/verify_release_artifact.py` (generalized
  checksum-entry verification, new required manifest fields), and
  `.github/workflows/ci.yml` (uploads `sbom.json` from the structural
  packaging-smoke build too);
- tests, and this document plus the linked normal-user guide.

## Non-goals

- New detector, tracker, threshold, Visit assembler, or candidate-authority
  changes -- this phase packages/configures the already-accepted
  Observation Engine unchanged; see
  [observation-engine-product-control-contract.md](observation-engine-product-control-contract.md)
  and [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
  for the engine boundary this phase wraps;
- a second/different production model -- only the already-accepted MDv5
  ONNX bundle is packaged;
- Electron, Docker, Kubernetes, or a systemd/Windows-service install;
- a native folder-picker/storage-relocation UI;
- remote telemetry or a cloud support channel;
- an admin-control-center redesign (the health panel is additive to
  Dashboard, not a new surface);
- Raspberry Pi, WSL, or NVIDIA as the product architecture (Windows is one
  validated packaged host; the architecture stays host-neutral).

## Validation tier

Tier 3 -- full backend suite, frontend type-check/production build, an
isolated first-run Playwright project (separate from the shared suite),
schema-migration compatibility tests (fresh vs. pre-existing database),
`python -m mockingbird --check`, and a real build of the Windows bundle with
its dependency layout fidelity-booted (proxy: the same flat `pip --target`
assembly, native-architecture equivalents of the compiled packages, run
under Linux) since this session cannot execute a native Windows binary. The
final native-Windows double-click smoke is handed off; see
[using-mockingbird.md](using-mockingbird.md) for the end-user path it
validates.

Native Windows Observation Runtime v1 additionally validated: the packaged
provider-config/model-bundle resolution order with no environment variable
and independent of `os.getcwd()`; the real local MDv5 ONNX bundle's SHA-256
against the exact accepted provenance (skipped, not failed, on a build host
without one); missing/corrupt-model and unsupported-GPU honest failure
states, each with its own distinct message, through the real (unfaked)
provider-loading path; the Camera-vs-Observation health separation (a
misconfigured Observation runtime never again reports a paired camera as
"not yet connected"); the clean-tracked-source-snapshot release-integrity
logic against real throwaway git fixtures, including the exact "an
untracked file must not be packageable" regression; and a real end-to-end
`build_local_product.py` run producing `dist/MockingBird-windows-x64.zip`
with the GPU/CUDA redistributable stack and the real model bundle both
included. The real NVIDIA-GPU inference proof itself (`cuda_only_verified`
execution) is the Observation Engine v2 Stage 3 activation this phase reuses
unchanged, not re-proven here; the final native-Windows GPU smoke -- "Start
observing" actually reaching `state="observing"` on real hardware -- is
handed off the same way the rest of this document's Windows validation
already is.
