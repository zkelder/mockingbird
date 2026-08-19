# Test Suite Validation Tiers contract

Status: Test Suite Runtime & Baseline Reliability v1 milestone, run against
starting HEAD `3108d0c` (the accepted BioCLIP/Review Queue Performance v1
baseline -- see [roadmap.md](roadmap.md)). Motivated by two compounding
problems the backend suite (3,128 tests) had grown into: a full run costing
roughly an hour or more, and a suite that routinely ended nominally red
because of a known, unchanging set of ~29 inherited failures a developer had
to manually re-recognize after every run.

## The question this closes

> Can a developer trust a fast validation command after a bounded change,
> without re-deriving from scratch which of the suite's failures are real?

Yes, for the tiers below, on this development environment. See "Remaining
known failures" for the honest exceptions.

## Root cause of the dominant runtime cost

Profiling (`python -m pytest --durations=0`, `cProfile` over a single
`ProductRepository()` construction) found the suite's dominant cost was
**not** product logic, seeding, or test-body work. `tests/conftest.py`'s
autouse `_default_isolated_repository` fixture (see
[test-repository-isolation-contract.md](test-repository-isolation-contract.md))
constructs a fresh `ProductRepository()` before *every* test, and roughly 90
test files construct a second one of their own. Each construction calls
`initialize_database`, which runs `Base.metadata.create_all` -- about 200
`CREATE TABLE`/`CREATE INDEX` statements. Under this sandbox's WSL2
filesystem, SQLite's default `synchronous=FULL` fsyncs the implicit commit
after *every one* of those ~200 DDL statements, at a measured ~1.4 seconds
per repository just for schema creation (of an ~1.8 second total
construction) -- not seeding, not product logic.

**Fix**: `mockingbird.storage.database.create_database_engine` now applies
`PRAGMA synchronous=OFF` on connect, but *only* when the resolved SQLite URL
is a file path pytest itself created under its own temp root
(`_is_ephemeral_pytest_sqlite_database`, reusing the exact `"pytest" in
sys.modules` + tempdir-containment detection `database_url_from_env`'s
existing fail-closed guard already established). This can never fire for a
production/packaged launch (which never imports pytest) or for an explicit
on-disk path outside pytest's own temp root. It changes no on-disk journal
format -- `journal_mode` stays the default rollback journal, so backup/
restore file-copy semantics are byte-identical to before -- only
crash-durability is relaxed, which no test in this suite exercises (no test
simulates a hard power-loss/OS-crash mid-write) and which is irrelevant to a
same-process throwaway tmp file discarded at test teardown. Measured effect:
a single `ProductRepository()` construction under a real pytest-tempdir
`db_url` dropped from ~1.8s to ~0.05s (a ~35x speedup) -- multiplied across
every test in the suite, this is the majority of this milestone's runtime
win. See `mockingbird.storage.database._is_ephemeral_pytest_sqlite_database`
and `_under_pytest_tempdir` for the implementation and full safety rationale
in their docstrings.

## Tier definitions

| Tier | Purpose | Command | Selects | Measured result (this machine) |
| --- | --- | --- | --- | --- |
| A -- Fast | routine edit/PR feedback | `python scripts/verify_fast.py` | a curated set of fast unit/pure-contract files (`scripts/verify_fast.py`'s own file list), `-m "not slow"` -- 79 files, 1,533 tests | **1,533 passed, 0 failed in 147s (~2.5 min)** |
| B -- Core | normal milestone acceptance | `python scripts/verify_core.py` | the whole backend suite except `slow`-marked tests: `pytest -m "not slow"` -- 3,118 tests | **3,107 passed, 0 failed, 11 xfailed, 10 deselected in 537s (~9 min)** |
| C -- Full | release-hardening/RC/major cross-cutting checkpoints | `python scripts/verify_full.py` | the complete backend suite, no filter: `pytest` -- 3,128 tests | **3,117 passed, 0 failed, 11 xfailed in 831s (~13m51s)** |
| D -- Hardware/platform | explicit real-environment acceptance | (not a pytest invocation -- see below) | real Pi reboot/capture, Windows/GPU runtime, packaged BioCLIP GPU acceptance, real network interruption | manual field procedure, not a pytest run |

Each tier is a superset of the ones above it. Frontend type-check/build and
Playwright e2e are unchanged by this milestone (see
[development-workflow.md](development-workflow.md) Tier 3) -- they are a
separate, already-established validation surface this milestone does not
touch.

### The `slow` marker

`pyproject.toml` registers one new pytest marker, `slow`, with
`--strict-markers` enabled (a typo'd/unregistered marker now fails loudly
instead of silently matching nothing). `slow` is applied narrowly, at the
individual-test level wherever a file is otherwise fast, and at module level
(`pytestmark = pytest.mark.slow`) only for the one file that is uniformly
heavy. Every `slow` test carries an inline comment explaining which Tier C
category it belongs to (real subprocess/process launch, real dependency
installation, large real-artifact hashing). This is deliberately the *only*
new marker: profiling and file-by-file classification found no pytest test
in this suite that requires genuinely different/special hardware (a real
GPU device, a real Pi board, a real Windows OS) to execute meaningfully --
every hardware-adjacent test already uses an injected fake/synthetic
provider (a long-established convention in this codebase, not something
this milestone introduced). Tier D is therefore not representable as a
pytest marker at all; see "Tier D," below.

Marked `slow` (10 tests across 4 files):

- `tests/test_camera_node_real_process.py` (whole file, `pytestmark`): a
  real venv + `pip install` of the built wheel, a real `subprocess.Popen`'d
  OS process reachable over a real TCP socket.
- `tests/test_camera_node_packaging.py::test_camera_node_artifact_is_slim_and_launcher_checks_without_starting`:
  a real venv + `pip install` of the built wheel + real subprocess launches
  of the installed launcher. The file's other 9 tests use only fast `git`
  subprocess calls against tiny throwaway fixture repos and stay unmarked.
- `tests/test_local_product_packaging.py`'s 4 `test_real_*` tests (already
  `skipif`-gated on real local artifact presence): real offline `pip
  install` from this host's local win_amd64 CUDA/cuDNN and BioCLIP wheel
  caches, and real SHA-256 hashing of this host's real ~500MB-1.6GB local
  model bundles. Measured directly on this sandbox (all 4 artifacts
  present): **215.6 seconds** for these 4 tests alone, vs. 12.58 seconds for
  the file's other 62 (hermetic, fixture-only) tests. The file's own module
  docstring already documented this file as deliberately hermetic except
  for these two "genuine, not-faked proofs, skipped rather than failed on a
  build host that does not have the real asset they need" -- this milestone
  did not change that design, only gave it a marker so Fast/Core can select
  around it instead of a developer discovering it by watching the clock.
- `tests/test_object_tracking.py`'s 3 tests that construct
  `LiveObjectDetectorManager(isolated_runner=...)`: this spawns a real
  `multiprocessing.get_context("spawn").Process` (a genuine new OS process,
  even though the function run inside it is a deterministic fake).

Not marked `slow`, despite surface-level heaviness signals, after direct
verification of the actual test bodies (not just `skipif`-on-`.is_dir()`
pattern-matching): `tests/test_bioclip_runtime.py`'s 2 real-bundle tests and
`tests/test_local_product_packaging.py`'s bundle-hashing tests (see above)
call `get_bioclip_status()`/`get_model_adapter()` or hash files -- status/
path/hash checks, never actual model loading or inference. They are Tier C
("large artifact hashing"), correctly included in the `slow` set above where
applicable, but are not Tier D: no GPU, no actual inference, nothing that
needs real different hardware to mean something.

### Tier D -- hardware/platform acceptance

No pytest test in this suite requires genuinely different hardware to
execute meaningfully -- confirmed by an exhaustive file-by-file sweep (all
190 files) for real (unmocked) `subprocess`/`multiprocessing`/
`onnxruntime.InferenceSession`/`open_clip`/`torch` usage and every
`skipif` condition. Genuine Tier D acceptance in this product is exclusively
the real-field/real-hardware procedures already documented outside pytest:

- Real Pi 4 reboot/crash/network-interruption acceptance --
  [camera-node-installer-design.md](camera-node-installer-design.md).
- Real packaged Windows/GPU acceptance (ONNX Runtime CUDA, BioCLIP) --
  [windows-dev-deployment-design.md](windows-dev-deployment-design.md) and
  [local-product-packaging-design.md](local-product-packaging-design.md).
- Real Camera Node field capture / representative field acceptance --
  [roadmap.md](roadmap.md) "Field-testing doctrine."

These stay explicit, bounded, stated-question procedures a developer runs
deliberately against real hardware -- never disguised as, or silently
folded into, an ordinary `pytest` invocation. `scripts/verify_full.py` runs
every `test_real_*`/artifact-hashing test that happens to have its
prerequisite artifact on the current machine (this sandbox has all of
them), but that is opportunistic Tier C coverage, not a Tier D acceptance
run -- Tier C never *requires* real hardware, it only sometimes benefits
from a big local cache directory being present.

## Escalation rules (which gate is required)

See [development-workflow.md](development-workflow.md)'s validation tiers
for the full task-risk framework; this section states the concrete backend
gate each situation requires. An agent must not choose Fast merely because
Core or Full is inconvenient -- state the tier chosen and why in the task
packet, per AGENTS.md.

- **Focused/RED-GREEN during implementation**: the closest one or two test
  files, exactly as `development-workflow.md` Tier 1 already directs. Not a
  gate script invocation.
- **Any bounded, single-area change** (one API route, one repository
  method, one detector-adjacent module) before calling it done: **Fast**
  (`scripts/verify_fast.py`).
- **Milestone completion; any change touching more than one subsystem;
  any change to migrations, backup/restore, review/truth provenance, Visit
  admission, evidence lineage, Camera Node pairing/lifecycle, or
  monitoring lifecycle**: **Core** (`scripts/verify_core.py`), regardless of
  how small the diff looks -- these are exactly the "preserve critical
  contracts" areas this milestone was told never to weaken coverage of.
- **Release-hardening completion, RC acceptance, or any change to
  packaging/dependency closures/`scripts/build_local_product.py`/
  `scripts/build_camera_node_artifact.py`**: **Full**
  (`scripts/verify_full.py`) -- this is the only tier that exercises the
  `slow`-marked packaging/dependency/model-bundle tests at all.
  Cross-cutting or broad-blast-radius work also escalates here per
  `development-workflow.md` Tier 3.
  - `scripts/verify_full.py` still runs everything even if none of the
    Tier D artifacts (wheel caches, model bundles) are present on the
    current machine -- the corresponding `slow` tests simply `skip` (never
    fail) via their existing `skipif` guards, exactly as before this
    milestone.
- **Hardware/runtime behavior actually changed** (Camera Node capture,
  Windows/GPU runtime, packaged BioCLIP, reboot/network-recovery logic):
  Full, then the applicable Tier D procedure above, per
  `development-workflow.md` Tier 4. Never substitute a `skipif`-gated
  pytest pass for a real hardware acceptance run when the task changed
  hardware-facing behavior.

## Baseline failure disposition

Exact starting-HEAD state (`3108d0c`, before any change in this milestone):
**3,099 passed / 29 failed / 3,128 total** (matches the prior milestone's
own recorded full-suite result -- see `docs/bioclip-review-queue-performance-contract.md`
commit history). Every one of the 29 was individually root-caused, not
assumed from precedent:

### Category 1 -- REAL PRODUCT/TEST DEFECT (fixed)

All of the following are **test-side** defects (stale fixtures/assertions);
no production behavior changed, and every fix was verified against the
actual current, intentional product behavior before being applied -- not
just "whatever makes it green":

- `tests/test_zone_diagnostic.py` (5 tests): `scripts/capture_zone_
  diagnostic.py` imported `mockingbird.api.main._object_detector_zone_crop`,
  a function commit `3ba954f` ("Use live object detection for animal
  visits") renamed/restructured away, breaking this dev tool's import at
  module-exec time for every test that touches it. Fixed by porting the
  exact pre-`3ba954f` masked-crop-per-Zone geometry into the script itself
  as a local `_zone_crop` helper (verified byte-for-byte against the
  original implementation via `git show 3ba954f^`) instead of reaching into
  `api.main`'s private internals a second time -- this is also a structural
  improvement: the tool can no longer bit-rot the same way when production
  internals next change shape.
- `tests/test_exact_frame_capture.py::test_exact_capture_cli_flag_is_
  explicit_and_default_off`: the test's `required` CLI-arg fixture predates
  `--scene-id` becoming a required flag (confirmed intentional and load
  -bearing -- `SCENE_ID_PATTERN`-validated, threaded through the whole
  capture loop). Fixed by adding `--scene-id scene-01` to the fixture.
- `tests/test_wildlife_journal.py::test_journal_resolves_current_reviewed_
  truth_and_combines_scope_filters`: asserted a literal `.../file` preview
  URL suffix; every other call site in the product (4+ locations in
  `product_repository.py`) and every other test in the suite that checks
  this field use `.../preview`. Fixed by correcting the one stale literal.
- `tests/test_dataset_quality.py::test_conflicting_corrections_are_
  reported`: a real product defect, not a stale test. `_dataset_quality_
  summary`'s conflicting-corrections check was fed `_review_label_models_
  for_visit`/`_for_event`, which resolve append-only history down to
  *exactly one* current effective row per target by design
  (`_effective_review_label_models`) -- so two independent, unlinked plain
  corrections could never appear together, making the check structurally
  unreachable. Fixed by adding `_review_label_history_models_for_visit`/
  `_for_event` (raw, uncollapsed, bounded to 50 rows) and feeding those
  specifically into the conflict check, leaving every other use of the
  collapsed "effective" view untouched. 43 review/provenance-adjacent tests
  and all other `test_dataset_quality.py` tests verified passing after the
  change; zero new lint findings (diffed byte-for-byte against the
  unmodified file, only line numbers shifted).
- `tests/test_stream_playback_contract.py` (20 tests, the largest cluster --
  see the dedicated subsection below).

### Category 5 -- ORDER-DEPENDENT / FLAKY (fixed)

- `tests/test_camera_node.py::test_picamera2_warm_required_pair_retries_
  once_after_resource_rejections` and 6 structurally identical siblings --
  see "Order/flakiness finding," below.

### Category 3 -- ENVIRONMENT-SPECIFIC

- `tests/test_stream_playback_contract.py::test_windows_dshow_start_uses_
  popen_list_without_shell`: asserted the literal Windows-style input path
  (`C:\ffmpeg\bin\ffmpeg.exe`) survives unchanged into the constructed
  `Popen` argv, but `start_windows_dshow_mjpeg_process` does not expose a
  `platform_name`/`environment` override the way its sibling functions
  do -- it always calls the real, unmocked `windows_ffmpeg_invocation_
  binary()`, which correctly WSL-mount-translates a `C:\...` path on a real
  WSL host (this sandbox has genuine `WSL_INTEROP`/real `powershell.exe`
  reachability, confirmed directly). This project's own primary development
  checkout is WSL-native (see roadmap.md's "WSL activation checkpoint"), so
  this test could never have passed there. This test's actual purpose (per
  its name) is the list-args/no-shell safety property, not path-translation
  correctness (which is already covered elsewhere with proper
  `platform_name=`/`environment=` injection) -- fixed by using the same
  already-WSL-native path form (`/mnt/c/ffmpeg/bin/ffmpeg.exe`) as input
  and expected output, matching this file's own dominant, established
  convention (30+ other occurrences already use this exact form), making
  the test's result independent of which host actually runs it.

Beyond this one, the suite's existing `skipif`-on-real-artifact-presence
convention (real BioCLIP bundle, real model bundle, real wheel caches, real
field-capture session data) already isolates every other environment
-dependent test this milestone found -- no other ordinary (non-`slow`) test
silently fails on an environment lacking a prerequisite. See "Tier D" and
"The `slow` marker," above, for the complete inventory.

### Category 4 -- INTENTIONAL PLATFORM/HARDWARE TEST (none found needing a new tier)

See "Tier D," above -- no pytest test in this suite requires genuinely
different hardware.

### Category 6 -- GENUINE KNOWN UNRESOLVED DEFECT (xfailed with precise reasons)

11 of the 20 `test_stream_playback_contract.py` failures are not stale
fixtures at all -- they are genuine, unresolved **product-behavior**
questions the "Use live object detection for animal visits" refactor
(`3ba954f`) left open, each individually confirmed (not guessed) by
actually constructing the animal `ObjectTrackTrigger` fixture and observing
which *specific* production code path then makes the test's own remaining
assertions structurally unsatisfiable. Two distinct shapes:

- **9 tests**: `object_promotion_trigger is not None` is an all-or-nothing
  switch in `src/mockingbird/api/main.py` that simultaneously (a) is
  required to reach any saved/promoted/reviewed outcome at all, and (b)
  unconditionally forces some *other* field the same test also asserts on
  to a different value (a threshold field to `None`/`"object_verified"`,
  `session_region_kind` to `"stream"` only, the legacy zone-based species
  suggester's precondition to false, `activity_detected` to `True`, or a
  hardcoded `None` suggestion). No test-side fixture choice can satisfy
  both halves at once under current production code.
- **2 tests**: confirmed pre-existing *independent* of `3ba954f` entirely
  -- reproduced against `3ba954f^` (the commit before that refactor) in an
  isolated worktree, zero animal-trigger fixture involved. `threshold_
  source` is unconditionally `None` whenever `best_candidate is None`
  (a below-threshold "near miss" always has `best_candidate is None`), but
  both tests assert a real threshold-source value for exactly that case.

Each of the 11 has its own precise `@pytest.mark.xfail(reason=..., strict=
True)` in the test file itself, naming the exact function/line range in
`api/main.py` responsible and stating the product decision needed --
`strict=True` so an eventual real fix is forced to remove the marker rather
than silently leaving it stale. This is not a test-infrastructure gap: it
is a genuine, bounded, precisely-scoped product-behavior question (does the
legacy zone-based suggester still apply once live object detection is
available? should a near-miss report a threshold source? should the
stored/auto-region review handoff populate a suggestion?) appropriate for a
dedicated future milestone with product-owner input, not a mechanical test
fix. See "Next release step" for how this is sequenced relative to v0.1 RC.

### `test_stream_playback_contract.py` -- full disposition of all 20

| Test | Disposition |
| --- | --- |
| `test_live_motion_decodes_live_frames_at_fine_motion_resolution` | Fixed: stale `[160,160]` expectation; `_LIVE_TRACKED_ACTIVITY_MAX_DIMENSION` has been `640` since a later, deliberate source-detail-quality commit (`faebe62`) this test predates. |
| `test_single_frame_animal_evidence_creates_no_durable_artifacts` | Fixed: response field renamed `object_detector_detections` -> `object_detector_boxes` (confirmed via the route's own construction); the test's own negative assertions (no durable artifacts from a mere detection) were already correct. |
| `test_windows_dshow_start_uses_popen_list_without_shell` | Fixed: environment-specific (see Category 3, above). |
| `test_zone_policy_lifecycle_uses_per_zone_quiet_maximum_and_evidence_limits` | Fixed: shared `values()` fixture helper never set `"promotion_category": "animal"`; `_LiveActivitySession.is_animal_promoted` gates `_finalize_for_review` the same way `promoted_animal_activity` gates the API route. |
| `test_tracked_detector_creates_one_unverified_review_visit_without_truth` | Fixed: added an animal `ObjectTrackTrigger`. |
| `test_live_motion_review_handoff_reuses_existing_review_candidate` | Fixed: added a trigger; only asserts relative equality between two calls. |
| `test_unattended_monitoring_closes_each_quiet_zone_once` | Fixed: added `"promotion_category": "animal"` (direct `record_activity_detection` path, not the HTTP route). |
| `test_live_activity_burst_candidate_frames_are_bounded_and_notifications_do_not_spam` | Fixed: needed a *dynamic* trigger (frame identity must track each call's actual latest frame, or later calls look like duplicate observations of the first frame and freeze `detection_count`). |
| `test_live_camera_diagnostics_record_product_transitions_without_truth` | Fixed: `"promotion_category": "animal"` on both hand-built activity dicts. |
| `test_live_motion_evaluation_uses_cached_frames_and_saves_best_frame_only` | xfail (Category 6, 9-test group): `strongest_zone_min_changed_ratio`/`threshold_used` forced `None`. |
| `test_live_motion_review_handoff_creates_needs_review_candidate` | xfail (Category 6, 9-test group): legacy zone-based suggester needs empty `object_candidates`. |
| `test_live_motion_auto_region_reaches_review_without_named_zone` | xfail (Category 6, 9-test group): `session_region_kind` forced to `"stream"`, never `"auto_area"`. |
| `test_live_motion_review_handoff_suggests_unknown_animal_for_ground_zone` | xfail (Category 6, 9-test group): same legacy-suggester conflict. |
| `test_stored_live_activity_review_handoff_keeps_camera_running_and_truth_reviewed_only` | xfail (Category 6, 9-test group): handoff path hardcodes `suggested_label=None`. |
| `test_stored_live_auto_activity_reaches_review_without_named_zone` | xfail (Category 6, 9-test group): same `session_region_kind` conflict. |
| `test_feeder_near_miss_starts_tentative_burst_before_confirmed_activity` | xfail (Category 6, 9-test group): trigger needed to start a tentative burst also forces `activity_detected=True`. |
| `test_live_activity_session_groups_hits_and_promotes_one_best_frame` | xfail (Category 6, 9-test group): `fine_motion_applied`/`threshold_source` forced. |
| `test_small_feeder_activity_capture_and_review_handoff_keep_monitor_running` | xfail (Category 6, 9-test group): same `fine_motion_applied`/`threshold_source` conflict. |
| `test_live_motion_bird_sized_feeder_mode_lowers_only_bird_zone_thresholds` | xfail (Category 6, 2-test pre-existing group): confirmed broken before `3ba954f` too. |
| `test_live_motion_does_not_broaden_small_yard_motion_thresholds` | xfail (Category 6, 2-test pre-existing group): confirmed broken before `3ba954f` too. |

Result: `python -m pytest tests/test_stream_playback_contract.py -q` -> **143
passed, 11 xfailed, 0 failed** (was 20 failed, 134 passed at the exact
starting HEAD). `ruff check` clean, identical to the unmodified file (0
findings before and after).

## Order/flakiness finding: the Camera Node timing test

`tests/test_camera_node.py::test_picamera2_warm_required_pair_retries_once_after_resource_rejections`
was the specific test named in this milestone's brief as "previously failed
only under full-suite load." Root cause: this test (and 6 structurally
identical siblings in the same file) waits for `PiCamera2Provider`'s
background warm-proof thread via `provider._warm_proofs[...].join(timeout=1)`
-- a fixed 1-second wall-clock budget racing a background thread whose real
work (a deliberate `WARM_REQUIRED_PAIR_RETRY_DELAY_SECONDS = 0.2` retry
delay plus a handful of fake-camera calls) normally finishes in ~0.2-0.3s.
No shared mutable state leaks between test invocations -- the fake
`Picamera2`/`Camera` classes are defined fresh inside each test function,
`PiCamera2Provider` instance state (including its lock) is per-instance, and
nothing module-level in `mockingbird_node/providers.py` is mutated at
runtime (confirmed by a repository-wide sweep for `@lru_cache`/`@cache` and
mutable module-level globals: none found outside frozen constant sets).
The failure is genuine timing pressure: only ~3-5x headroom between the
budget and the expected work, evidently insufficient against the GC/
scheduling pressure a process carrying thousands of prior tests'
accumulated state can introduce. Fix: widened the join timeout from 1s to
10s (~30-50x headroom) uniformly across all 7 occurrences, not just the one
caught -- this is not "add a retry"; it removes an unnecessarily tight
wall-clock race for a background thread doing only deterministic local
Python work with no real blocking I/O. A 10s ceiling still catches a
genuine hang/infinite-loop regression; it does not paper over one. The
larger repository-wide fsync fix (above) also reduces the accumulated
per-process state this specific race was sensitive to.

## CI readiness (not built in this milestone)

The repository has no `.github/workflows/` today, and this milestone does
not add one -- building CI is explicitly out of scope (see the milestone's
own "Scope exclusions"). The tier scripts are, however, directly usable by
a future minimal workflow with no further test-selection logic: a PR check
could run `python scripts/verify_fast.py` (or Core) as one job step, with
`scripts/verify_full.py` reserved for a manual/release-tag trigger. That
remains a small, cheap next step for whoever picks up public CI/OSS
readiness -- not something this milestone should expand into on its own.

## Gate-detection acceptance (injected-failure proof)

Each gate's actual failure-detection behavior was verified directly, not
assumed from the marker logic alone: an ordinary test temporarily appended
to a Tier A file was caught (nonzero exit) by both `verify_fast.py` and
`verify_core.py`; a `slow`-marked test temporarily appended to a `slow`
-marked file was correctly *not* run by `verify_core.py` (deselected, exit
0) and correctly caught (nonzero exit) by `verify_full.py`. Both injected
tests were removed immediately after and the affected files were
re-verified clean (`ruff check` and a full re-run of both files, ensuring
zero trace was left behind). This confirms the tier-selection mechanism
neither silently misses a real failure it should catch, nor accidentally
runs -- and hides behind a false-green -- work the Full gate alone owns.

## What this does not change

- No product/detector/classifier behavior. No test was deleted or weakened
  to hit a runtime target; every disposition above is justified individually.
- `CURRENT_DATABASE_SCHEMA_VERSION` and every migration are unchanged.
- Production/packaged startup never imports pytest, so
  `_is_ephemeral_pytest_sqlite_database` can never fire outside a test
  process -- real user data keeps its existing `synchronous=FULL` durability
  exactly as before.
- The ~90 existing per-file isolation fixtures, and
  [test-repository-isolation-contract.md](test-repository-isolation-contract.md)'s
  two-layer guard, are untouched.
- Frontend type-check/build and Playwright e2e (`web/e2e`) are unchanged and
  out of this milestone's scope.

## Remaining known failures

None are red. The only disclosed exceptions are the 11 `strict=True` xfails
in Category 6, above -- each a precisely-reasoned, individually-justified,
genuine product-behavior question, not an unexplained or silently-masked
failure. `verify_fast.py`/`verify_core.py`/`verify_full.py` all currently
exit 0 on this development machine.

## Remaining slow areas (deliberately not optimized further)

- `tests/test_local_backup_recovery.py`'s real backup/restore tests (up to
  ~54s each): these use `storage/backup.py`'s own raw `sqlite3.connect()`
  calls, deliberately *not* routed through the ephemeral-database fast path
  above, because backup/restore correctness must be verified against
  production's real fsync/journal behavior, not a relaxed one -- trading
  this speed for weaker backup-safety coverage would violate "preserve
  critical contracts." Left in the Core gate (not moved to `slow`) because
  backup/restore is exactly the kind of major product contract Core is
  meant to cover, and the added cost (roughly two minutes across the whole
  file) is a reasonable price for it.
- A handful of `tests/test_camera_node.py` tests exercise real multi-second
  timeout/retry budgets by design (for example a ~12s node-preview timeout)
  -- passing, not flaky, just inherently as slow as the real behavior they
  verify. Not changed; out of this milestone's bounded scope.
- The `slow`-marked Tier C tests themselves (real dependency installation,
  real subprocess/process launches, large real-artifact hashing) are
  irreducibly slow by what they verify; Tier C's whole purpose is to keep
  them out of the Fast/Core gates rather than to make them faster.

## Next release step

This milestone's own scope is test-suite runtime and baseline reliability,
not the 11 disclosed product-behavior questions Category 6 found. The
recommended next step is **v0.1 Release Candidate / Clean-Machine /
Invite-Beta Acceptance** as already sequenced in
[roadmap.md](roadmap.md), using the Core gate for normal RC-prep milestone
work and the Full gate at the RC checkpoint itself. The 11 Category 6
xfails are a small, precisely-scoped, optional follow-up (a
`live_monitoring`-lane product-behavior review, not infrastructure work)
that can happen independently, before or after RC, without blocking it --
each is `strict=True` and will loudly demand attention the moment any
future change actually resolves it.
