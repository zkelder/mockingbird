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

`GET/PUT /api/setup/state` is the only read/write surface. The frontend
(`OnboardingWizard.tsx`) gates rendering the wizard on the **dashboard route
only** (`page === "dashboard"`); every other route, including a direct deep
link during a fresh install, renders the normal application shell
unaffected. This matches how a real user actually meets the app (the launcher
always opens the browser at `/`) and keeps the existing Playwright suite
(`camera-controls.spec.ts`, `observation-panel.spec.ts`,
`reviewed-product-loop.spec.ts` -- each deep-links straight to `/streams/:id`
or `/review`, none assert on `/`) unaffected by construction, not by
coincidence.

The wizard is a thin orchestrator, not a new implementation:

1. Welcome -- what MockingBird does, in plain language.
2. Storage -- shows the resolved local data folder (not the database
   filename -- see "Storage status" below), current usage, host free space,
   and writability; does not add a relocation UI (that remains the existing
   `MOCKINGBIRD_HOME`/`MOCKINGBIRD_DB_URL` advanced/developer lever).
3. Camera -- embeds the existing, **unmodified** `CameraSetupPage`, which
   already implements choose-type -> Camera Node pairing or provider fields
   -> validate -> preview -> draw/confirm Zone -> save. Its own "Discard
   setup" action doubles as "skip for now" in this context.
4. Observe -- embeds the existing, **unmodified** `ObservationControlPanel`
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
- tests, and this document plus the linked normal-user guide.

## Non-goals

- Observation Engine, detector, tracker, or candidate-authority changes;
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
