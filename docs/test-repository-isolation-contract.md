# Test / Development Repository Isolation v1 contract

Status: Phase 1 "Trustworthy Single-Site Observatory" milestone (see
[roadmap.md](roadmap.md)), motivated by a real test-isolation defect the
Review Decision Provenance / Truth Boundary v1 milestone's own test
execution exposed: routine `pytest` runs reached and migrated the real local
development database (`data/mockingbird.sqlite3`) through the same lazy
`get_repository()` default a real product launch relies on. The migration
itself was valid and harmless that time, but nothing structurally prevented
a future test from doing the same thing to a database that now holds
durable reviewed history, review provenance, field evidence, and Detection
Quality data.

## The question this closes

> Can any automated test accidentally fall back to MockingBird's persistent
> development/product database?

No, unless a test explicitly and deliberately opts into an integration
fixture designed for a persistent database.

## Boundary

This is a repository/test-safety contract, not a test-cleanup milestone and
not a product behavior change. It does not touch admission thresholds,
Visit semantics, Review Decision provenance, or any of the ~27 pre-existing
unrelated test failures this milestone's own instructions named out of
scope. Every mechanism below is inert outside a pytest process.

## How the real database was reachable

`mockingbird.storage.database.DEFAULT_DB_URL` is a *relative* SQLite URL
(`sqlite:///data/mockingbird.sqlite3`), overridable only by the
`MOCKINGBIRD_DB_URL` environment variable. `get_repository()`
(`mockingbird.api.main`) is a lazy module-global singleton: the first call
with no repository configured constructs a bare `ProductRepository()`,
which resolves this same relative default against the process's current
working directory. When `pytest` runs from the checkout root (the normal
case) and nothing has configured an explicit repository first, that default
resolves to the exact real, persistent `data/mockingbird.sqlite3` file --
and `ProductRepository.__init__` unconditionally opens, migrates, and reseeds
against whatever `resolve_database_url` returns, via `initialize_database`
and `seed_if_empty`. Migration is not the only write: `seed_if_empty`'s own
taxonomy-label upsert (`_seed_taxonomy_labels`) unconditionally re-assigns
every existing row's columns whether or not the values actually changed, so
even a merely-*reopened*, already-current-schema database is not a no-op --
SQLite's own file change counter advances on every such transaction. Merely
*importing* `mockingbird.api.main` never triggers any of this (the singleton
is lazy); only a call reaching `get_repository()` does.

### The live case: an orphaned background task outliving its own test

An instrumented whole-suite sweep (`ProductRepository.__init__` wrapped to
redirect any dangerous resolution to a throwaway file *before* any real
engine ever opens, so the sweep itself could never touch the real database
no matter what it found) caught a real, currently-existing case in four
`test_camera_node.py` tests plus one delayed-symptom failure in
`test_observation_session_api.py`'s teardown:

`pair_camera_node` (`POST /api/camera-nodes/pair`) fires a detached
`asyncio.create_task(_refresh_camera_node_pairing_profiles(...))` and
returns without awaiting it -- correct product behavior, warming up
advertised camera profiles is not on the pairing response's critical path.
That task calls `get_repository()` once, then loops with `await asyncio.
sleep(1.0)` between up to twelve attempts. A test that pairs successfully,
finishes its own body, and resets the repository singleton in its `finally`
can do so *before* that task wakes up for its own first `get_repository()`
call -- at which point the singleton is `None` again, isolation is gone,
and the task resolves the real, unconfigured default. This is a genuine
race, not a certainty every run, which is exactly why it needs a
deterministic close, not a longer sleep: see "Repository singleton
lifecycle" below.

### Two further call sites, both latent today

- `mockingbird.api.main._app_lifespan` -- the real FastAPI startup hook,
  calls `get_repository()` unconditionally. This is correct for a real
  launch. No test in this suite currently drives a real ASGI lifespan
  startup (`httpx.ASGITransport` does not implement the lifespan protocol,
  and `_patch_testclient_for_pytest` deliberately neutralizes Starlette
  `TestClient`'s own lifespan-triggering `__enter__`/`__exit__` to work
  around an unrelated local hang) -- confirmed by the same instrumented
  probe, not merely by inspection. It remains one call site this contract
  must cover, because nothing prevents a future integration test from using
  a lifespan-aware harness (`asgi-lifespan`'s `LifespanManager`, or a real
  `uvicorn` server) on purpose.
- `mockingbird.runtime.run_preflight()` -- calls `get_repository()` directly
  after `os.chdir`-ing into `resolve_runtime_home()`'s result. Two real
  tests (`test_single_app_runtime.py`, `test_windows_launcher_instance_
  identity.py`) exercise this for real, and both currently stay safe only
  because they set `MOCKINGBIRD_HOME` to an isolated `tmp_path`-derived
  directory *before* calling it -- a convention enforced by each test
  author remembering to do so, not by anything structural.

All three are covered by the same guard (below); none required a different
mechanism per call site.

Every other repository-backed test (~90 files) already defines its own
`tmp_path`-backed isolation fixture (`configure_repository(...)` or
`monkeypatch.setattr(api_main, "_repository", ...)`) -- a real, working,
pre-existing convention this contract does not replace or refactor. A
smaller number of files (for example `test_observation_frame_driven.py`,
`test_tracked_activity.py`, `test_motion_proposal_cli.py`) never define one
because they never construct a repository or touch `app` at all. Exactly one
file, `test_observation_engine.py`, hits `app` through a real ASGI
transport without its own fixture -- confirmed safe today only because its
one endpoint (`GET /api/observation-engine/status`) never calls
`get_repository()`. None of this was structurally guaranteed before this
milestone; all of it now also has the two-layer guard below underneath it.

## The two-layer guard

**Layer 1 -- `tests/conftest.py`'s `_default_isolated_repository` (autouse,
function-scoped).** Configures a throwaway repository, under its own
`tmp_path_factory.mktemp(...)` directory, before every test in `tests/`,
and tears it down afterward. This is the friendly default: a new test file
that never thinks about isolation at all still gets a real, working,
isolated repository, not a crash. It runs before any test-module-local
autouse fixture (broader conftest scope wins), so a file with its own
`isolated_repository`-style fixture simply reconfigures over top of it for
that test with no leak (`configure_repository` closes whatever it
replaces); its own teardown closes its own repository directly if
something else has since taken over the singleton, and through
`configure_repository(None)` otherwise -- either way, without touching a
teardown that is not its own.

An earlier draft nested this fixture's directory *inside* the requesting
test's own `tmp_path` instead of a separate `tmp_path_factory` allocation.
A whole-suite regression run caught the real consequence immediately:
`test_storage_status_disk.py::test_probe_never_leaves_its_sentinel_file_
behind` asserts its own `tmp_path` starts and ends empty, and this
fixture's subdirectory was already sitting there before the test body even
ran. `tmp_path_factory.mktemp` allocates a fresh, uniquely-numbered
directory outside every test's own `tmp_path` tree, so this autouse
fixture can never again be the reason a test's own `tmp_path` isn't empty.

An autouse fixture alone cannot protect against a test that *deliberately*
undoes its setup mid-test to exercise real default-resolution behavior --
exactly what the two `run_preflight()` tests above do on purpose. That is
what Layer 2 is for.

**Layer 2 -- `mockingbird.storage.database.database_url_from_env`'s
fail-closed guard.** The one function every default-resolution path already
funnels through (`resolve_database_url` -> `ProductRepository.__init__` ->
`create_database_engine`). On the fallback branch only -- no explicit
`db_url` argument, no `MOCKINGBIRD_DB_URL` environment variable -- it checks
whether `"pytest" in sys.modules` (the same detection
`_patch_testclient_for_pytest` already established for an unrelated purpose
in this codebase) and, if so, whether the resolved absolute path lies under
`tempfile.gettempdir()` (exactly what pytest's own `tmp_path` already builds
under). If neither condition holds, it raises
`UnsafeDefaultStorageAccessError` *before* any engine, file, or directory is
touched, rather than opening the real file. An explicit `db_url` argument or
environment variable is never second-guessed, no matter where it points --
this only ever fires on the silent, nobody-decided-anything fallback.

This is genuinely fail-*closed*, not fail-safe-by-convention: `run_preflight
()`-style tests that correctly point `MOCKINGBIRD_HOME` at an isolated
directory first still resolve safely and never raise (the relative default
now lands under that directory once `os.chdir` has run); a test that resets
isolation and forgets to redirect `MOCKINGBIRD_HOME` gets a loud, immediate,
actionable exception instead of a silently-migrated production database.

Both layers are conditioned on `"pytest" in sys.modules`, directly or
transitively. Production and ordinary local development (`python -m
mockingbird`, the packaged Windows runtime) never import pytest -- it is a
`[project.optional-dependencies] test`-only dependency -- so `DEFAULT_DB_URL`
resolves exactly as it always has outside a test process. `tests/conftest.py`
itself is never imported by anything under `src/mockingbird/`.

## Repository singleton lifecycle: draining detached background work

`configure_repository` already resets every other module-global manager
(`_stop_runtime_activity`) and closes whatever repository it replaces, so a
test built on it or on the autouse fixture starts and ends clean. The one
gap was the orphaned task described above, which outlives the request that
spawned it and calls `get_repository()` again on its own schedule.

`_track_background_task` (`mockingbird.api.main`) keeps a strong reference
to a detached task in a module-global set (`asyncio.create_task`'s own docs
warn a task can otherwise be garbage-collected mid-flight, independent of
this contract) and discards it automatically once it finishes.
`drain_background_tasks()` awaits every currently-tracked task and
deliberately does not swallow an exception raised inside one -- a real
failure (including this contract's own guard, if something drains too
late) must still surface loudly. Its only current caller is
`pair_camera_node`'s task; a test that pairs successfully must `await
drain_background_tasks()` before resetting its repository, exactly as
`test_camera_node.py`'s four affected tests now do. This is not a new
worker/background-task lifecycle -- see
[worker-lifecycle-boundary-design.md](worker-lifecycle-boundary-design.md)
for that governance -- it is making one already-existing fire-and-forget
task properly awaitable, for the one purpose this contract needs.

## Scope boundary: the media root is deliberately not guarded the same way

`mockingbird.storage.database.DEFAULT_MEDIA_ROOT` has the identical
relative-default shape as `DEFAULT_DB_URL`, and an earlier draft of this
contract guarded it identically. That draft was reverted after an
exhaustive sweep of every `ProductRepository(...)` construction in the test
suite (an AST walk, not a text grep) showed:

- **0** of them omit an explicit `db_url` -- the database guard protects a
  convention the whole suite already follows, so it never fires against
  today's suite; it exists purely to hold the line for tomorrow's tests.
- **16** existing files (22 call sites) omit an explicit `media_root`,
  relying on exactly the fallback a symmetric guard would reject -- because,
  unlike `database_url_from_env`, resolving the media-root default does not
  by itself open, write, or migrate anything; only an actual media-writing
  operation would, and none of those 16 files perform one (confirmed
  against `data/media/imports`'s own last-modified time, which predates
  this milestone's test runs).

Guarding `media_root` symmetrically would have broken 16 already-safe files
for no matching safety gain -- the opposite of "the smallest general
solution." `media_root_from_env` stays exactly as it was; a future test that
deliberately writes media without configuring `media_root` is exactly as
responsible for that as it always was. If a real media-write-without-
isolation gap is ever found, it should be fixed the same way the database
was: proven first, then guarded at its own single resolution point.

## Explicit, deliberate persistent-database integration

An integration test that genuinely wants a real, on-disk, persistent-format
repository -- to validate migration, backup/restore, or cross-install
behavior against real SQLite semantics -- remains fully able to construct
one, exactly as roughly ninety existing test files already do: pass
`db_url=f"sqlite:///{tmp_path / '...'}"` explicitly (or set
`MOCKINGBIRD_DB_URL` explicitly). Neither guard layer ever inspects or
rejects an explicit choice, no matter what it points at. This is
deliberately still "on disk under a test-owned `tmp_path`," never the real
user data directory -- no fixture in this codebase opens
`%LOCALAPPDATA%\MockingBird`/`~/.local/share/mockingbird` and none should.

## What this does not change

- `CURRENT_DATABASE_SCHEMA_VERSION` and every existing migration are
  unchanged; the real local development database's schema v32 is not rolled
  back or otherwise touched by this milestone.
- Production/packaged startup, `python -m mockingbird`, and
  `scripts/deploy_windows_dev.py` resolve `DEFAULT_DB_URL`/
  `DEFAULT_MEDIA_ROOT` exactly as before -- neither ever imports pytest.
- The ~90 existing per-file isolation fixtures are untouched; this
  contract adds a safety net underneath them, not a replacement for them.
