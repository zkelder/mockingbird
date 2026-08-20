# Perception Replay Regression Harness v1

Gate A engineering capability named in [roadmap.md](roadmap.md) "Perception
Replay Regression Harness (Gate A engineering capability)". Turns a real
recorded field defect into a repeatable offline engineering fixture instead
of requiring another random real bird encounter after every code change.
Does not replace live field acceptance -- see "Relation to field
acceptance," below.

## Purpose

Real field sessions surface real perception defects (a delayed proposal
that loses its own already-captured evidence; one bird encounter that
fragments into several Visits; a background confusor admitted as a false
Visit). Until now, validating a fix for one of these meant waiting for
another live session to reproduce a similar shape by chance. This harness
replays already-recorded real evidence through the actual, unmodified
production perception pipeline -- as many times as needed, deterministically,
entirely offline.

## Prior art, extended not duplicated

[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md)
(`replay.py`/`replay_cli.py`/`replay_io.py`, Stage 2) already replays an
ordered frame directory through a real Observation Engine provider --
offline, deterministic, shadow-only. This milestone adds three layers on
top, as new files only; nothing in the Stage 2 module is modified:

1. **Visit episode assembly**, already built (Stage 6.19,
   `replay.assemble_visit_episode_report`) but not previously wired into a
   CLI -- now included in the combined funnel.
2. **Shadow admission** (`admission_replay.py`, new): drives an already-
   assembled proposal through the real, unmodified Stage 7 gates
   (`candidate_visit_authority.evaluate_candidate_authority`,
   `candidate_quality_gate.evaluate_evidence_admission`,
   `scene_confusor.evaluate_scene_confusor_suspicion`, and the real
   `candidate_visit_adapter.CandidateVisitAuthorityAdapter`) against a
   freshly created, isolated, disposable `ProductRepository` -- never the
   real product database. `candidate_visit_adapter.py`'s own docstring
   already names "a replay/offline harness" as a legitimate caller,
   alongside a live session driver and a test.
3. **Orchestration, provenance, fixtures, and differential comparison**
   (`perception_regression.py`, `perception_regression_io.py`,
   `perception_regression_cli.py`, new): ties the above into one coherent
   funnel with run-level provenance, a named-fixture registry, real-
   recording ingestion, bounded time-window replay, and baseline-vs-
   candidate comparison.

No production module is modified by this milestone. See "Production code
changed" in the implementation's own commit message for the exact file
list.

## Isolation guarantees

Every hard safety constraint below is structural, not merely documented
practice:

- **Never connects to a live Camera Node.** Every provider this harness
  drives (`frame-driven-onnx-cuda`, `onnx-cuda`) is the same one
  `replay_cli.py` already uses offline; nothing in this milestone adds a
  network/live-capture code path.
- **Never modifies the production database.** `admission_replay.
  IsolatedAdmissionRepository` only ever constructs a `ProductRepository`
  against a caller-supplied or freshly `tempfile.mkdtemp`-created directory
  -- there is no code path in this module that can resolve a default
  database location. `mockingbird.storage.database.database_url_from_env`'s
  own independent fail-closed guard
  ([test-repository-isolation-contract.md](test-repository-isolation-contract.md))
  is a second, structural layer of protection this milestone never needs to
  rely on but never disables either.
- **Never modifies production media.** Evidence bytes are read from the
  replay input's own source frame files; any media a `create` admission
  outcome writes lands under the isolated repository's own `media_root`,
  removed with the rest of the isolated directory when the context manager
  exits (unless the caller supplied a directory to keep for inspection).
- **Never alters monitoring state, consumes real Candidate-Visit authority
  budget, or creates production Visits/Observations.** Authority is
  activated only for the isolated repository's own synthetic Stream (see
  below) -- a real Stream's authority state is never read or written.
- **Never uses live runtime identity/state accidentally.**
  `admission_replay.require_replay_stream_id` fails closed
  (`AdmissionReplayError`) on any `stream_id` not prefixed `replay:` --
  enforced before an isolated repository is even constructed.

### Explicit synthetic Stream identity

`IsolatedAdmissionRepository` creates one synthetic `CameraSourceModel`/
`StreamModel` row pair inside the isolated database for the replay's own
`stream_id` (the real Stage 7 admission path looks a Stream up by id for its
privacy-zone check). `zone_id` is left unset on every replayed proposal --
no Zone exists in the isolated database -- an explicit, disclosed v1 scope
boundary (see "Scope boundaries," below), not a silent gap.

### Fail closed if isolation cannot be guaranteed

If a caller ever manages to pass a non-`replay:`-prefixed `stream_id`,
`require_replay_stream_id` raises before any database, directory, or
authority state is touched. If the real default-database fail-closed guard
ever fired inside a test run, the test fails loudly with
`UnsafeDefaultStorageAccessError`, never a silent fallback.

## Input manifest

Two accepted input shapes, both producing the same `ReplayBundle` type
`replay.py` already defines:

1. **Benchmark manifest** (existing Stage 2 format, unchanged) -- an ordered
   frame directory plus a versioned JSON manifest with optional hand-
   authored truth (`appearances`/`visits`/`detections`/`evidence`). See
   [observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md).
2. **Acceptance recording** (new,
   `perception_regression_io.load_acceptance_recording`) -- a real
   `acceptance_recorder.py` output directory (`manifest.jsonl` +
   `frame-{seq:06d}-offset{ms:09d}ms.jpg` files, see
   [independent-encounter-denominator-design.md](independent-encounter-denominator-design.md)),
   with **no hand-authored truth required**. Every truth-dependent metric
   `replay.py` already defines (`appearance_recall`, `proposal_precision`,
   box precision/recall, etc.) honestly reports `insufficient_truth`/
   `not_evaluated` for this input shape -- never inferred from MockingBird's
   own output. Frame `source_offset_ms` is re-based to start at 0 for
   whichever window is selected; each frame's real `captured_at_iso` is
   preserved unchanged.

Both shapes accept a bounded time window
(`--window-start-ms`/`--window-end-ms`, or
`perception_regression.select_time_window` for an existing benchmark
manifest's own truth-bearing bundle) -- truth objects that only partially
overlap the selected window are dropped, never truncated into a boundary
nobody actually drew.

### Regression fixture registry

A small, versioned JSON file (`{"version": 1, "fixtures": [...]}`,
`perception_regression_io.load_fixture_registry`) names replay inputs by
`fixture_id` instead of requiring frames/manifest/provider/window
arguments to be re-typed every time. Each entry: `fixture_id`,
`description`, `source_kind` (`"benchmark_manifest"` or
`"acceptance_recording"`), `frames_path`, `manifest_path` (required only for
`benchmark_manifest`), `provider_key`, `provider_config_path`,
`stream_id` (must be `replay:`-prefixed), `base_observed_at`,
`window_start_ms`/`window_end_ms` (optional), and optional
`denominator_reference` (a local path to an independently-adjudicated
encounter table -- see "Human denominator," below) and
`structural_expectation` (free text naming what a real defect this fixture
regression-tracks looks like).

A tiny, synthetic, committed registry exists for fast unit tests
(constructed inline in `tests/test_perception_regression_cli.py`). The real
2026-08-19/08-20 field-evidence registry
(`data/perception_replay_fixtures/fixtures.json`) is **not committed** --
`data/` is already ignored -- and points at real recorded frames living
outside this checkout entirely (see "Fixtures," below).

## Commands

```bash
python -m mockingbird.observation.perception_regression_cli run \
  --fixture known_valid_bird_visit --registry data/perception_replay_fixtures/fixtures.json \
  --output data/perception_replay_runs/known_valid_bird_visit

python -m mockingbird.observation.perception_regression_cli run \
  --frames FRAMES_DIR --manifest MANIFEST.json --stream-id replay:my-fixture \
  --provider frame-driven-onnx-cuda --provider-config MODEL_BUNDLE_CONFIG.json \
  --output OUTPUT_DIRECTORY

python -m mockingbird.observation.perception_regression_cli run \
  --recording ACCEPTANCE_RECORDING_DIR --stream-id replay:my-fixture \
  --window-start-ms 4340000 --window-end-ms 4400000 \
  --provider frame-driven-onnx-cuda --provider-config MODEL_BUNDLE_CONFIG.json \
  --output OUTPUT_DIRECTORY

python -m mockingbird.observation.perception_regression_cli list-fixtures \
  --registry data/perception_replay_fixtures/fixtures.json

python -m mockingbird.observation.perception_regression_cli compare \
  --baseline BASELINE/perception-regression-report.json \
  --candidate CANDIDATE/perception-regression-report.json \
  --output diff.json
```

`--no-admission` skips the shadow-admission stage (detection/tracking/
assembly only -- faster, useful for a provider-comparison pass that does not
need Visit-level outcomes). Output directories follow the exact `replay_
io.py` safety convention: new-or-empty only, refused inside tracked source/
docs/tests or the repository root, refused through a symlink.

There is currently no `python -m mockingbird` top-level subcommand wired to
this CLI (unlike `replay-benchmark`) -- invoke the module directly as shown
above. Wiring a top-level subcommand, if it earns its place, is left for a
future pass rather than expanding this milestone's own scope.

## Output format

One `perception-regression-report.json` per run
(`perception_regression.perception_regression_report_to_json`), `schema_
version: 1`. Top level: `replay` (Stage 2 metrics -- frames processed,
detections, confirmed tracks, box precision/recall, fragmentation/duplicate/
false-proposal counts, evidence-selection metrics), `assembly` (Stage 6.19
metrics -- tracklets in, episode merges, ambiguous/incompatible decisions,
assembled proposal count), `admission` (this milestone's own outcome per
proposal -- `create`/`blocked_ambiguous_boundary`/`blocked_continuation_
pending`/`blocked_missing_evidence`/`blocked_scene_confusor_suspected`/
`reject_no_identification_or_context`/`reject_subject_geometry_invalid`/
`reject_insufficient_proposal_support`/`idempotent_repeat`/`failed`, plus
the reason string and, for `create`, the isolated database's own `visit_id`/
`event_id`), `provenance` (harness version, code HEAD, run-started-at, seed,
provider key, Stream id, whether admission ran), and one combined
`semantic_fingerprint` covering every semantic fact above (never an
absolute path, host name, or PID -- those stay in the separate, non-
semantic `execution` section the CLI adds, exactly like `replay_io.
write_replay_report` already keeps them out of its own semantic payload).

CSV is not produced; the task this harness serves is machine comparison
(`compare`) and CLI/report inspection, not spreadsheet analysis -- add it
only if a real future need appears.

## Logical-time mode

The only mode this harness implements. Every temporal fact throughout the
funnel -- detector cadence decisions, tracker gap/expiry checks, assembler
merge-gap comparisons, and this milestone's own admission `observed_at` --
is driven by each frame's recorded `source_offset_ms` (an acceptance
recording's real, distinct `captured_at_iso` timestamps are preserved
alongside it, so a fixture's `base_observed_at` can be set to the real
recorded wall-clock moment its own window begins). Nothing in the funnel
ever sleeps for elapsed real time; a 92-minute recording replays in however
long real I/O and (if a real detector is configured) real inference take --
seconds to low minutes for the fixtures built tonight (see "Performance,"
below), not 92 minutes.

**Real-time mode is not built.** The task that produced this milestone
scoped it explicitly optional ("only if necessary for validating timing-
dependent behavior") and no timing-dependent behavior needing wall-clock-
paced replay was identified. If one is later found (for example validating
`AnalysisStreamRetryPolicy`'s own backoff timing under replay), add it as a
clearly separate, explicitly-selected mode -- never silently blur it with
logical time.

## Determinism

**What is proven deterministic tonight:** given the identical input bundle,
provider instance, and configuration, `run_perception_regression`'s combined
`semantic_fingerprint` is byte-identical across repeated runs --
`tests/test_perception_regression.py::test_semantic_fingerprint_is_stable_
across_repeated_runs_despite_provenance_timestamps` and, on real field data,
`tests/test_perception_regression_real_fixtures.py::test_real_encounter_1_
replays_repeatedly_and_deterministically` both assert this directly. Every
stage in the funnel (`FrameDrivenObservationProvider`'s pure Python
tracking/evidence logic, `assemble_visit_episodes`, the real Stage 7 gates)
is deterministic by construction given deterministic detector output --
none of them read a wall clock, use randomness, or depend on iteration
order over an unordered collection in a way that survived this milestone's
own tests.

**What is not yet established, honestly:** whether `OnnxCudaObservationProvider`'s
real GPU-backed inference itself produces bit-identical output across
repeated runs on the same hardware. This milestone did not exercise real
CUDA inference (see "Real recordings/windows replayed," below) --
`onnx_provider.py`'s own `finalize_replay` already requires and verifies a
CUDA-only execution profile, and general ONNX Runtime CUDA determinism
depends on kernel/algorithm selection this project has not itself measured.
**Do not claim GPU-inference bit-for-bit determinism this milestone did not
prove.** If a future session measures it and finds run-to-run floating-
point variation, the correct semantic-equivalence comparison is `compare`'s
own tolerant classification (`equivalent`/`changed`) applied to *derived*
outcomes (track/proposal/admission counts, Visit shape) rather than raw
detection scores -- not a fix to this harness, a documented property of the
underlying runtime.

## Fixtures

Four named fixtures were built tonight from real, existing local
`acceptance_recorder` output (2026-08-19/08-20, `stream-ca892992771c`) --
never fabricated; every window is grounded in the independently-adjudicated
[independent-encounter-table.md](../data/field-acceptance/2026-08-19-end-to-end-recall-closure/independent-encounter-table.md)
(not committed to git; a local path reference, exactly like
`denominator_reference` elsewhere in this doc):

- `e2e_2026_08_19_encounter_11_delayed_admission` -- encounter #11
  (~4351-4382s, 30.3s): recorder-confirmed, zero product Visit created.
  Closely matches the documented ~34s `blocked_continuation_pending`-delayed
  evidence-cache-eviction case in
  [visit-authority-budget-recall-closure-v1-report.md](visit-authority-budget-recall-closure-v1-report.md)
  that originally motivated the evidence-cache bound.
- `e2e_2026_08_19_encounter_2_triplicate` -- encounter #2 (~612-614s): one
  real encounter that fragmented into 3 admitted Visits in production.
  Regression target: "one real encounter should not become three
  independent Visits."
- `e2e_2026_08_19_encounter_1_sustained_valid` -- encounter #1 (385-543s,
  ~2.6min): a cleanly-confirmed, known-good positive baseline.
- `cache128_2026_08_20_nighttime_zero_activity` -- the real overnight
  cache-128 attempt (32.4 minutes, real low-light detector noise only,
  zero production tracks/candidates): a known real negative control.

Every fixture points at real absolute local paths
(`/mnt/c/Users/.../acceptance-recordings/...`, outside this checkout) --
never copied or committed. A checkout without that exact local data skips
the corresponding tests (`test_perception_regression_real_fixtures.py`),
mirroring `test_burst_scheduler_replay.py`'s own established real-session
skip convention.

## Real acceptance tonight -- what was, and was not, proven

Both real-fixture tests pass on this sandbox: real recorded frame bytes and
timestamps from an actual 2026-08-19 field session flow through the real
production tracking/Visit-assembly/shadow-admission stack, twice, with a
byte-identical semantic fingerprint both times, entirely offline, without
ever touching the real product database (`test_real_encounter_1_replays_
repeatedly_and_deterministically`); a real, known-quiet overnight session
correctly produces zero tracks/proposals/admissions
(`test_real_nighttime_negative_control_stays_quiet`).

**Explicit, important scope boundary:** the detector driving every real-
fixture run tonight is `_PositionBasedSyntheticDetector` -- a disclosed
synthetic stand-in that reports one fixed-confidence "animal" box on frames
in the middle third of a window, never real MDv5 inference. This was a
deliberate choice, not an oversight: this development sandbox does have
working Windows/CUDA interop (`python.exe` against a real passed-through
GPU, driven from WSL), but it is set up for exercising the packaged
product's own deployed build -- see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md) -- not
for running ad hoc new source from a brand-new git worktree. Bridging that
gap for this milestone's own new files was judged impractical to stand up
safely within tonight's scope
relative to the value, per this task's own "if runtime is practical"
guidance. Consequently:

- **Proven:** the harness's own mechanical correctness on real data -- real
  frame ordering/identity/timing/bytes flow correctly and repeatably
  through the real tracking/assembly/admission code paths, isolation holds,
  results are deterministic.
- **Not proven, and not claimed:** that this harness reproduces the exact
  historical defects (encounter #11's real zero-Visit miss, encounter #2's
  real triplication) byte-for-byte. Those defects arose from real MDv5
  detector confidence/timing interacting with the real evidence cache and
  admission gates -- a synthetic, idealized detection signal naturally does
  not reproduce that exact failure shape (both real-encounter fixtures
  produced one clean track/proposal/`create` outcome under the synthetic
  detector, as expected, not the two known defect shapes).

**Concrete next step, explicitly out of scope for tonight, ready to run:**
point `--provider onnx-cuda`/`--provider frame-driven-onnx-cuda` at the real
model bundle
(`/home/zkelder/projects/mockingbird-active/data/models/observation-onnx-cuda/frame-driven-provider-config.json`,
already referenced in the fixture registry) from an environment with real
CUDA access, and re-run the same four fixtures. The harness requires no
further code changes to do this -- only real hardware access this milestone
did not attempt to bridge.

## Human denominator

`RegressionFixture.denominator_reference` optionally names a local path to
an independently-adjudicated encounter table (never itself evidence of
wildlife truth -- see
[independent-encounter-denominator-design.md](independent-encounter-denominator-design.md)).
This milestone wires the *reference* (all four real fixtures above carry
one) but does not implement automatic recall/false-Visit-rate computation
against it -- that would require parsing the denominator document's own
prose table into structured data, judged a distinct, bounded future
addition rather than something to improvise into tonight's schema. Reading
`independent-encounter-table.md` by hand against a fixture's own
`perception-regression-report.json` (as this milestone's own report did for
the four fixtures above) remains the interim path.

## Regression-fixture architecture

A real defect becomes a fixture via: (1) a bounded input time window from
real recorded evidence (`window_start_ms`/`window_end_ms` against a real
`acceptance_recorder` output directory, or a real benchmark manifest); (2) an
expected structural outcome, recorded today as free-text
`structural_expectation` on the fixture entry -- for example "one real
encounter should not become three independent Visits" for
`e2e_2026_08_19_encounter_2_triplicate`. A future pass could promote this to
a machine-checked assertion (`expected_visit_count`, `expected_fragmentation_
count`) once enough fixtures exist to justify one shared schema for it --
not built speculatively tonight. Species truth is never encoded in a
fixture; none of this milestone's sources have been human-adjudicated for
species.

## Performance

Measured on this sandbox, real recorded frames, `_PositionBasedSyntheticDetector`
(no real inference cost):

| Fixture | Real frames | Real span | Wall time (both real-fixture tests together) |
| --- | --- | --- | --- |
| `e2e_2026_08_19_encounter_1_sustained_valid` | 122 | 168.0s | included in ~57s total below |
| `cache128_2026_08_20_nighttime_zero_activity` (2min window) | ~62 | 120s | included in ~57s total below |

Both real-fixture tests together: 56.9s wall time, dominated by real file
I/O (reading and PIL-dimension-probing real ~900KB-1MB JPEG frames one at a
time, run twice for the determinism assertion) rather than perception
computation itself -- `run_perception_regression`'s own compute stages
(tracking/assembly/admission) complete in well under a second per run once
frames are loaded. GPU utilization is not applicable (no real inference ran
tonight). Storage footprint added by this milestone: zero inside the
checkout (fixtures reference real external files; each isolated admission
run's own on-disk SQLite/media lives under a `tempfile.mkdtemp` directory
removed when the run's context manager exits).

No premature optimization was attempted, per this milestone's own governing
instructions; correctness and isolation came first and were not
compromised for speed anywhere in this design.

## Relation to field acceptance

This harness reduces how often a fix has to wait for another real bird to
validate a hypothesis. It does not replace live field acceptance: real
CUDA inference determinism is unmeasured (see "Determinism," above), scene-
confusor suspicion structurally cannot fire without cross-session history a
fresh isolated replay never has, and no replay can prove a genuinely new,
previously-unseen real-world failure mode the fixtures built so far do not
already represent. Promotion of any detector/policy/threshold change still
requires the live field-acceptance process
[roadmap.md](roadmap.md)/[development-workflow.md](development-workflow.md)
Tier 4 already governs.

## How to add a regression fixture

1. Identify a real, already-recorded time window -- either a real
   `acceptance_recorder` output directory, or a benchmark-manifest replay
   input with hand-authored truth. Never fabricate a fixture window.
2. Add one entry to a fixture registry JSON (a local, uncommitted one for
   real data under `data/`; the tiny synthetic registry pattern in
   `tests/test_perception_regression_cli.py` for a committed unit-test
   fixture) -- `fixture_id`, `description`, `source_kind`, `frames_path`,
   `manifest_path` (benchmark manifests only), `provider_key`,
   `provider_config_path`, `stream_id` (must start `replay:`),
   `base_observed_at`, optional `window_start_ms`/`window_end_ms`, and a
   `structural_expectation` describing the real defect or known-good shape
   this fixture exists to protect.
3. `python -m mockingbird.observation.perception_regression_cli run
   --fixture YOUR_FIXTURE_ID --registry YOUR_REGISTRY.json --output
   OUTPUT_DIR` to confirm it loads and replays.
4. If the fixture exists specifically to protect against a regression,
   write a focused test asserting the specific structural fact that matters
   (an admission-outcome count, a proposal count, a specific verdict) --
   see `tests/test_perception_regression_real_fixtures.py` for the pattern.

## Scope boundaries

Explicitly not built, or not attempted, in this v1 milestone -- named here
so a future pass does not have to rediscover the boundary:

- Real-time (wall-clock-paced) replay mode.
- Real CUDA/onnx-cuda inference against the real fixtures (see "Real
  acceptance tonight," above) -- the harness is ready for it; it was not
  attempted tonight.
- Automatic recall/precision computation against a denominator document's
  prose table (the reference is wired; parsing it is not).
- Machine-checked structural-expectation assertions on a fixture entry
  itself (today: free-text, human-read).
- Zone-aware admission replay (no Zone exists in the isolated database;
  every replayed proposal's `zone_id` is unset).
- Persistence-level fidelity beyond the real Stage 7 decision gates --
  media-file writing and privacy-zone checks are exercised (a real Zone
  lookup simply finds none), but this harness does not attempt to
  reproduce a live session's exact on-disk media layout.
- CSV output.
- A `python -m mockingbird` top-level subcommand for this harness.
- Multi-subject Visit implementation, detector threshold changes, species
  model changes, and any change to the evidence-cache bound -- all
  explicitly out of scope per this milestone's own governing instructions,
  unaffected by anything in this milestone.
