# MockingBird Doctor / Operational Health v1

**Roadmap phase:** Gate D (First-Hour Setup & Camera Node Golden Path) /
Gate E (Reliability / Recovery / Observability) -- "MockingBird Doctor /
self-check," named and previously unbuilt in [roadmap.md](roadmap.md):

> No consolidated health/self-check capability exists today; product/camera
> health is spread across several narrower surfaces (Dashboard summary,
> Observation panel, Camera Health). A single self-check covering database
> integrity, migration/schema state, media-root reachability, filesystem
> permissions, disk space, Python/native dependency presence, model-file
> presence, GPU availability when configured, paired Camera Node
> reachability, provider configuration validity, clock sanity, backup
> state, and version/compatibility would give support and self-diagnosis
> one place to look instead of several.

**Product flow improved:** self-diagnosis. A normal user or a support
conversation can now run one command and get a bounded, calm, actionable
answer to "is this MockingBird installation healthy enough to observe
wildlife, and if not, what specifically needs attention?" instead of
manually inspecting services, the database, model files, camera
connectivity, disk state, and logs one at a time.

**Why this is next:** this gap was already named and scoped in the
roadmap's own Gate D entry (above) as a future bounded milestone; this
document is that milestone.

## Scope boundary

Doctor is a read-only, additive composition layer. It does not touch, and
must never need to touch: the Visit episode assembler, candidate Visit
authority, detection/tracking code, species inference, migrations/schema,
or Visit/Event/Observation persistence semantics. It never creates,
corrects, or reinterprets a Visit, Event, DetectionProposal,
SpeciesSuggestion, or ReviewLabel. It reuses existing truths
(`GET /api/product/health`'s own composition, `storage.database`'s
storage-pressure thresholds, the existing backup library, the existing
BioCLIP/CUDA/ffmpeg availability checks) wherever one already exists,
rather than building a second implementation of any of them.

## Design invariant: Doctor never constructs `ProductRepository`

`ProductRepository.__init__` unconditionally calls `initialize_database`
(which can run schema migrations **in place** if the recorded version is
older than `CURRENT_DATABASE_SCHEMA_VERSION`) and `seed_if_empty()` --
exactly the two side effects a read-only health check must never risk, and
precisely the scenario ("this database's schema is stale") Doctor most
needs to observe and report honestly, rather than silently "fixing" as a
side effect of merely checking. Constructing a `ProductRepository` against
a database at the wrong schema version would make the very defect Doctor
exists to surface disappear before it could ever be reported.

Every check in `mockingbird.diagnostics.doctor` instead composes:

- bare, read-only SQLAlchemy engine queries -- `storage.database`'s
  `create_database_engine`/`_sqlite_integrity_check`/
  `_read_recorded_schema_version` (the same pattern
  `tests/test_persistence.py` already uses to inspect a database without
  going through the repository), plus minimal direct `select()` reads
  against `CameraSourceModel`/`StreamModel`/`MonitoringExposureIntervalModel`/
  `StreamRuntimeCheckpointModel`;
- free functions that need no repository at all -- `probe_local_storage_disk`,
  `LocalBackupManager(db_url=..., media_root=...)` (its constructor takes
  plain strings, not a repository), `get_bioclip_status`,
  `OnnxModelBundle.load`, `OnnxCudaObservationProvider.unconfigured().probe()`,
  `is_ffmpeg_available`, `resolve_host_local_timezone`, and
  `runtime_state.resolve_build_identity`.

A database file that does not exist yet (a never-launched install) is
detected by a plain `Path.is_file()` check **before** anything ever opens a
SQLAlchemy connection to it -- SQLite auto-creates an empty file the
instant anything connects to a `sqlite:///` URL whose file is missing, so
opening first and checking second would make Doctor itself the thing that
creates a database file merely by inspecting one that was never there.

## Contract

```text
DoctorReport
  overall_status: HEALTHY | DEGRADED | UNHEALTHY
  generated_at
  app_version
  duration_ms
  checks: DoctorCheckResult[]

DoctorCheckResult
  code                  -- stable snake_case identifier, e.g. "database_schema"
  component             -- display name, e.g. "Database"
  status: PASS | WARN | FAIL | SKIPPED
  summary               -- one calm, user-safe sentence, always shown
  detail                -- optional longer explanation
  recoverability: blocking | degraded | informational | (none, for a plain PASS)
  user_action           -- short, safe next step; only set for WARN/FAIL
  diagnostic_context    -- bounded dict, advanced/JSON-only, never the primary message
  duration_ms
```

`overall_status` is derived **deterministically**
(`doctor._derive_overall_status`): `UNHEALTHY` if any check's
`recoverability` is `blocking`; else `DEGRADED` if any check is `WARN` or
`FAIL`; else `HEALTHY`. `SKIPPED` never affects `overall_status` by itself.

No pre-existing shared error/diagnostic-code taxonomy covers this surface --
confirmed by direct code archaeology: every MockingBird subsystem defines
its own bare `XxxError(ValueError)` with a free-form string "code"
(`ReplayValidationError("invalid_frame_driven_configuration")`,
`AuthorityOutcome`'s `Literal[...]`, and so on), never a shared base.
`DoctorCheckCode` is Doctor's own small, closed, local namespace, following
the same snake_case convention -- not a departure from house style, just
the first time this particular surface needed one of its own.

## Checks implemented

| Component | Code | What it checks | Can it be `blocking`? |
| --- | --- | --- | --- |
| Application | `application` | Running app version/build identity; whether the previous run shut down cleanly | No |
| Database | `database_connectivity` | The database opens and passes `PRAGMA quick_check` | **Yes** |
| Database | `database_schema` | Recorded schema version vs. `CURRENT_DATABASE_SCHEMA_VERSION`; `SKIPPED` if connectivity failed | **Yes** |
| Storage | `storage` | Media root exists, is writable (`probe_local_storage_disk`'s bounded write-then-delete probe), and has enough free space (reuses the existing `LOW_DISK_FREE_BYTES_THRESHOLD`/`LOW_DISK_FREE_RATIO_THRESHOLD` -- the same 1 GB / 5% policy `/api/product/health` already uses) | **Yes** |
| Backup | `backup` | Whether a backup exists and how old the most recent one is (via the real `LocalBackupManager.list_backups()`, never a second implementation) | No |
| Camera Node | `camera_node` | Configured Source/Stream counts, currently-monitored count (`MonitoringExposureIntervalModel`'s open-interval signal, which -- unlike the legacy `armed`-policy check -- is accurate for a paired Camera Node Stream too), legacy runtime checkpoints in `blocked`/`interrupted` state, staleness of the durable `camera_node_last_seen_at` fact when no session is currently open (Boot Identity + Autonomous Recovery v1 -- closes the gap disclosed below the open-interval check alone could not), and bounded recent-boot-transition evidence (`camera_node_recent_boot_transitions_json`, capped at 5 entries) for restart/boot-loop instability suspicion | No |
| FFmpeg | `ffmpeg` | `ffmpeg` binary availability, capability-gated: only escalates to `WARN` when a configured Source kind (`rtsp`/`local_camera`) plausibly needs it | No |
| Detector model | `detector_model` | Observation Engine provider-config + model-bundle presence and integrity (`FrameDrivenProviderConfiguration.load` + `OnnxModelBundle.load`), capability-aware on whether a Camera Node Stream is configured | No |
| Species identification | `species_identification` | BioCLIP runtime status via the existing `get_bioclip_status` | No |
| GPU / CUDA | `gpu_cuda` | `CUDAExecutionProvider` availability via `OnnxCudaObservationProvider.unconfigured().probe()`, capability-aware | No |
| Clock | `clock` | Local clock readability; host timezone resolution (`resolve_host_local_timezone`, which never raises) | No |
| Offline ingest | `offline_ingest` | Bare read of the most recent `RecordedMediaAnalysisRunModel` rows (bounded sample); WARNs on a recent-failure pattern, informational if none run yet or the database predates schema 41 | No |
| Research / export | `research_export` | Bare read of the most recent `DatasetExportModel` rows (bounded sample); same WARN/informational shape as Offline ingest | No |

**Added by First-Hour Onboarding + Whole-Product Observability Closure
v1:** the two checks above, plus the Storage check now additionally probes
`research_exports`/`classifier_manifest_exports` output roots
independently (previously only the database directory was probed, falling
back to media_root -- an export root on a genuinely different volume was
an undetected blind spot). Both new checks reuse this module's existing
`(gather, interpret)` pattern and bounded-sample convention
(`_RECENT_RUN_SAMPLE_SIZE`) rather than a new mechanism, and both fail
open to `PASS`/informational (never blocking, and never a raw exception)
when the underlying table predates the database's current migration state
-- a real installation mid-upgrade must never see a scary unexpected
failure from a table that simply does not exist yet at its recorded
schema version.

Only Database and Storage can ever report a `blocking` failure. Every
other capability is optional/degradable by product doctrine -- an install
with none of them configured, or one of them broken, remains a usable
MockingBird install (see "Severity semantics," below). This also holds for
a check's own *unexpected* failure: an exception or timeout while gathering
an optional check's data defaults to `degraded`, never `blocking`, so one
broken probe can never make the whole install read as unhealthy. Database
and Storage are the only two checks whose gather step is explicitly marked
`blocking_on_failure=True`, so an unexpected exception *there* (for example,
a genuinely corrupt SQLite file that raises instead of returning a clean
`PRAGMA quick_check` result) still correctly reports `UNHEALTHY`.

## Severity semantics

- **Blocking** (`FAIL`, `recoverability=blocking`): the install cannot be
  trusted to observe wildlife at all -- database unreachable/corrupt,
  incompatible schema, or the storage root missing/unwritable.
- **Degraded but usable** (`WARN`, `recoverability=degraded`): a real
  problem exists, but the core loop still works with a reduced capability
  -- for example, "BioCLIP runtime unavailable. Wildlife Visits can still
  be created; species suggestions are unavailable," or a Camera Node
  configured but its detector model missing.
- **Informational** (`PASS`, `recoverability=informational`): an optional
  capability was never configured in the first place -- not a problem to
  fix. For example, "CUDA is not available. No Camera Node is currently
  configured, so GPU acceleration is not required," or "No backups have
  been created yet."

## CLI

```bash
python -m mockingbird doctor
python -m mockingbird doctor --json
python -m mockingbird doctor --timeout 10
```

Mirrors the existing `python -m mockingbird <subcommand>` dispatch
convention already used for every internal dev/benchmark tool in
`__main__.py` (a lazy import + `run(argv)` returning an int exit code) --
not a new `argparse.add_subparsers()` pattern. This was a deliberate choice
between two defensible options; see "Known v1 scope limits," below.

Default output is calm and concise -- one line per check, with an indented
summary/detail/action block only for `WARN`/`FAIL`/`SKIPPED`:

```text
MockingBird Doctor

PASS    Database
PASS    Storage
PASS    Camera Node
WARN    Species identification
      BioCLIP runtime unavailable.
      Wildlife Visits can still be created; species suggestions are unavailable.
      Action: Check the configured BioCLIP model/labels files, or see docs/species-suggestion-adapter-design.md.

Overall: DEGRADED
Checked in 43ms.
```

`--json` prints the full `DoctorReport` (see "Contract," above) as
machine-readable JSON instead.

## Exit codes

| `overall_status` | Exit code | Meaning |
| --- | --- | --- |
| `HEALTHY` | `0` | Every check passed (or was informational). |
| `DEGRADED` | `1` | At least one `WARN`, or a non-blocking `FAIL`; the install is usable. |
| `UNHEALTHY` | `2` | At least one `blocking` failure; the install cannot be trusted to observe wildlife. |

This is stable and script-safe by design, matching the Nagios-style
`0=OK/1=WARNING/2=CRITICAL` convention a support script would already
expect. `runtime.py`'s own `--check` flag returns `0`/`2` only (no
"degraded" tier existed to express before this milestone); Doctor's `1` is
a genuinely new, additive tier, not a redefinition of an existing code.

## Timeouts

Every check's data-gathering step runs in a bounded, isolated call
(`doctor._run_bounded`, default 5s; 15s for the detector-model check, whose
bounded integrity verification hashes a potentially large `.onnx` file).
`_run_bounded` uses a **daemon** `threading.Thread` rather than
`concurrent.futures.ThreadPoolExecutor`: a pool's worker threads are joined
by an `atexit` hook, so a genuinely wedged synchronous call would still
block *process* exit even after `.result(timeout=...)` gave up --
silently defeating "Doctor must not hang forever." A daemon thread can
never block interpreter shutdown, so an abandoned, still-running check
cannot keep the Doctor process (or a test exercising this exact path,
`test_run_bounded_returns_promptly_when_the_call_hangs`) alive past its own
bounded return.

A healthy run against a real, populated installation completes in single-
digit milliseconds (see "Real acceptance," in the implementation report);
the 5s/15s budgets exist for the unhealthy case -- a stuck disk, a wedged
network call, or a hung subprocess -- not the normal one.

## Fail independently

Every check's timeout/unexpected-exception handling lives in one place
(`doctor._execute_check_returning_gathered`), so every check gets identical
isolation without each check needing its own try/except for the unexpected
case. Concretely:

- A corrupt/unreachable database produces a `blocking` `FAIL` on
  `database_connectivity`; `database_schema` and `camera_node` (both of
  which need real tables to query) report `SKIPPED`, not a crash or a
  confusing raw exception; every other check (Application, Storage,
  Backup, FFmpeg, Detector model, Species identification, GPU/CUDA, Clock)
  still runs and reports its own real result.
- FFmpeg's own gather degrades gracefully rather than skipping outright
  when the database is unavailable: ffmpeg-binary presence is independently
  useful information regardless of database state.

## Privacy and security

Doctor output is safe to paste into a GitHub issue or support conversation
by default:

- It never reads `node_base_address`/`node_credential`/any other
  `secret=True`-flagged Source-provider-configuration field (confirmed by
  code archaeology: these fields are marked `secret=True` in
  `SourceProviderField`'s own definition and are sanitized to the literal
  string `"configured"` by `_sanitize_source_provider_config` wherever the
  product already surfaces them). The Camera Node check reads only
  `CameraSourceModel.kind`/counts, `MonitoringExposureIntervalModel`'s
  open-interval signal, and (Boot Identity + Autonomous Recovery v1)
  `CameraSourceModel.camera_node_last_seen_at`/`camera_node_boot_id`/
  `camera_node_service_version`/`camera_node_recent_boot_transitions_json`
  -- structural/identity facts, never connection details or a credential. A
  `boot_id` is a kernel-generated UUID meaningful only in relation to a
  specific Node's own boot history; it authenticates nothing and is not
  itself sensitive.
- Local filesystem paths (the database path, the media root, the log path)
  are included un-redacted, matching the existing, already-shipped
  precedent: `ProductHealthStatus.log_path` already does the same for this
  same reason -- this is a local-only diagnostic tool, and a folder path is
  not a secret the way a credential is.
- Raw Python exceptions never appear in the always-shown `summary`/`detail`
  fields -- only a short, type-and-message string
  (`doctor._bounded_exception_detail`, capped at 200 characters) inside
  `diagnostic_context`, the advanced/JSON-only bucket.
- `test_report_json_never_includes_sensitive_value_shaped_text` asserts the
  full serialized report never contains `credential`, `bearer`, `password`,
  `api_key`, `secret`, or `token` -- mirroring the exact precedent test
  `test_product_health.py::test_product_health_never_includes_credential_
  shaped_values` already established for `/api/product/health`.

## Known v1 scope limits

Disclosed deliberately rather than silently narrowed:

- **Deep provider-configuration validation is out of scope.** The Camera
  Node check reports structural facts (Source/Stream counts, monitoring
  activity, legacy checkpoint health) but does not validate
  `node_base_address`/pairing-credential fields, since doing so safely
  would require either constructing `ProductRepository` (ruled out above)
  or reverse-engineering the provider-configuration persistence layer from
  outside it -- a second implementation of logic the product already owns
  correctly elsewhere. It also does not make a fresh live network probe of
  the Camera Node itself (`CameraNodeClient.health()` exists and is
  bounded, but calling it would require reading the very
  `secret=True`-flagged address this milestone deliberately never touches).
- **Camera Node clock divergence is not measurable in this version.**
  `node_to_host_clock_offset_ms` is computed once per delivered frame
  during a *live* Observation Engine session but is not persisted or
  exposed by any status surface today (confirmed by code archaeology,
  `camera-node-live-shadow-contract.md`'s "Clock-drift disposition"). A
  standalone Doctor process genuinely cannot read a fact nothing durable
  ever stores. The Clock check discloses this explicitly in
  `diagnostic_context` rather than fabricating a number or silently
  omitting the topic.
- **Backup integrity is not re-verified.** The Backup check reports
  presence and recency via the cheap `list_backups()` (manifest-only, no
  hashing); it does not call the heavier `verify_backup()` (which hashes
  the whole archive), matching "prefer the cheap check unless correctness
  requires load verification." Full verification remains available from
  the Local Data page.
- **Backup staleness threshold (30 days) is Doctor's own disclosed
  judgment call**, not a pre-existing product policy -- no canonical
  backup-staleness threshold exists anywhere else in the product today,
  unlike the storage low-disk-space threshold (reused, not invented; see
  the Storage row above).
- **FFmpeg capability-gating has known imprecision.** `CameraSourceModel.kind`
  is a coarse `SourceKind` (`rtsp`/`local_camera`/...), and at least one
  provider (`external_url`) is mapped to `SourceKind.rtsp` by
  `_camera_setup_source_kind` even though it never needs ffmpeg. This can
  make the FFmpeg check WARN slightly too eagerly for an `external_url`-only
  install; it can never make it wrongly silent, and the check never escalates
  past `WARN`/`degraded`.
- **CLI dispatch style.** `python -m mockingbird doctor` was added to
  `__main__.py`'s existing manual `sys.argv[1]` dispatch table (the
  precedent every other internal subcommand already uses) rather than
  introducing `argparse.add_subparsers()` for the first time in this
  codebase. The `mockingbird-app` console script defined in
  `pyproject.toml` is unused by every real launcher in this repo
  (`start-mockingbird.sh`/`Start MockingBird.cmd`/`Start MockingBird.vbs`
  all invoke `python -m mockingbird`), so Doctor was not wired through it.

## Files touched

- `src/mockingbird/diagnostics/__init__.py` (new)
- `src/mockingbird/diagnostics/doctor.py` (new) -- contract, checks, orchestrator
- `src/mockingbird/diagnostics/doctor_cli.py` (new) -- CLI entry point
- `src/mockingbird/__main__.py` -- one additive dispatch branch, mirroring
  the existing pattern exactly
- `tests/test_doctor.py`, `tests/test_doctor_cli.py` (new)
- `CONTRIBUTING.md` -- one short pointer alongside the existing `--check`
  documentation
- this document

No production shared module (`storage/database.py`,
`repository/product_repository.py`, `api/main.py`,
`observation/engine_runtime.py`, `species/bioclip_adapter.py`, and so on)
was modified -- every reuse point above is an **import**, never an edit.

## Non-goals

- A new admin-control-center surface, interactive wizard, or second review
  system -- Doctor is one bounded CLI command plus a stable, machine-readable
  report shape.
- A general observability/metrics/tracing rewrite -- the roadmap's own
  "Support bundle and tracing" (Gate E) named correlation/causal tracing
  and a privacy-safe support-bundle export as separate future capabilities
  this milestone did not attempt. **Current disposition (First-Hour
  Onboarding + Whole-Product Observability Closure v1):** a first bounded
  support bundle now exists (`diagnostics/support_bundle.py`, `python -m
  mockingbird support-bundle`) as a *separate* module that reuses this
  Doctor report wholesale for its health section -- Doctor itself gained
  no new responsibility or non-read-only behavior to make that possible.
  Full causal tracing of one Visit's complete path remains open.
- Network time synchronization infrastructure -- the Clock check validates
  that the local clock and host timezone are *readable*, never that they
  are *correct* against an external time source.
- Any change to detector/tracker/species-inference behavior, Visit
  admission, migrations/schema, or Visit/Event/Observation persistence
  semantics.

## Validation tier

Tier 2 (domain integration, no persistence writes) -- focused unit tests for
every pure `_interpret_*` function with injected fixtures, integration-level
tests against a real isolated `tmp_path`-backed SQLite database (per
`test-repository-isolation-contract.md`'s established pattern), CLI tests
mirroring `test_single_app_runtime.py`'s existing `--check` convention,
`ruff check`, and a real local acceptance run against the actual current
installation (read-only by construction, so no camera/GPU/network
hardware dependency was required for the focused suite itself).
