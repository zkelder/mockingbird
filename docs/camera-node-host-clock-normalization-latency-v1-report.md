# Camera Node ↔ Host Clock Normalization for True Capture-to-Visible Latency v1

RELEASE-CRITICAL Gate A measurement-correctness milestone. Does not
reopen fragmentation accounting, does not optimize pipeline latency, does
not run a wildlife field cohort, does not change detector/model behavior.
Closes the clock-domain gap Gate A Measurement Closure v1 disclosed but did
not solve: T0 (`TrackGenerationRecord.start_captured_at`) is Camera
Node-domain wall-clock time, `decided_at` (T5's own best-available proxy)
is Host-domain wall-clock time, and no prior cohort ever proved -- or even
measured -- the relationship between them.

## Starting state

Verified before touching anything: branch `main`, HEAD `3eeb8ed` (the
reconciliation commit accepting Gate A Measurement Closure v1 -- matches
git; `release-execution-state.md` §1's own "Accepted HEAD" field names
`86955ab`, the last report-bearing commit before that reconciliation commit
itself, the doc's own established convention throughout, not a
discrepancy). Schema `v58`, unchanged by this milestone (`database.py`
untouched -- confirmed via `git diff --stat`, zero lines). Gate A/Lane R:
open, not self-closed. Fragmentation: READY FOR FORMAL BUDGET REVIEW
(unchanged, not reopened). Capture-to-visible instrumentation: partially
delivered (T0/T5 defined, cross-domain subtraction disclosed-but-unproven).
Authorization: NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED. The
seven preserved untracked detector files were present, byte-identical, and
untouched throughout (re-verified at the end). `git status --short`
confirmed a clean working tree at the start and no `.git/index.lock`; no
active writer process was found.

## Timestamp-origin trace

Traced directly in code (this milestone's own §5), not assumed:

1. **Camera Node capture timestamps** are read from the Node's own wall
   clock, `datetime.now(UTC)`, at two call sites in
   `src/mockingbird_node/app.py` (lines 462, 539) -- confirmed a genuine
   `CLOCK_REALTIME`-equivalent read, never monotonic, never a
   hardware/media timestamp, never derived from an offset.
2. Serialized as `AnalysisFrameEnvelope.captured_at` (required, tz-aware,
   `contracts.py`/`media_contracts.py`), alongside an *optional*
   `source_monotonic_ns` (the Node's own monotonic clock) -- both travel
   over the existing paired multipart-JPEG analysis-stream transport,
   unchanged by this milestone.
3. **Host receive time already exists and is already recorded**:
   `camera_node_live.CameraNodeAnalysisSource._pop_latest` stamps
   `newest.received_at` (Host wall clock, `datetime.now(UTC)` at the Host)
   onto every delivered `contracts.FramePacket.received_at` -- a
   pre-existing field, structurally present since before this milestone,
   never previously read for cross-domain calibration.
4. **An existing Node/Host offset estimate already exists too**:
   `node_to_host_clock_offset_ms = received_at - captured_at`, computed
   once per delivered frame in the same `_pop_latest` function, attached to
   `FramePacket.timing_facts`. Confirmed directly (not merely cited from
   the prior contract doc): `grep`-ing every consumer of this key found
   none -- it was computed and immediately discarded on every single frame
   before this milestone.
5. **No round-trip time-exchange primitive exists in the current
   protocol.** `/node/v1/health` (`mockingbird_node/app.py`) was read in
   full: it returns `service_started_at` (a one-time absolute stamp) and
   monotonic `os_uptime_seconds`/`service_uptime_seconds`, never the Node's
   own *current* wall-clock time as of the response. `CameraNodeClient.
   health()` (the Host-side caller) does not construct an NTP-style
   `H0`/`H1` bracket around this call today. This governed the calibration
   design choice below (§6/§9 of the governing brief).
6. **RTSP/local/USB/replay sources never populate `received_at` at all.**
   Every non-Camera-Node `FramePacket` construction site was grepped
   (`detector_benchmark_cli.py`, `motion_proposal_cli.py`,
   `frame_tracker.py`, `multi_scale_cli.py`, `recorded_video_source.py`,
   `snapshot_provider.py`, `replay.py`) -- none set `received_at`, since
   for these sources `captured_at` is already stamped by the Host's own
   clock (no second device, no cross-domain risk). This is the exact,
   already-present structural signal this milestone's design uses to
   distinguish "needs clock normalization" from "already Host-domain."
7. **Acceptance-recorder frames carry `source_offset_ms`/`captured_at`
   only** (`acceptance_recorder.py`'s `RecordableFrame` protocol) -- no
   Host-domain pairing today. Calibration facts are instead surfaced
   through the counterfactual ledger/API (below), the existing acceptance
   -tooling consumption path, rather than adding a second, redundant
   channel to the frame-image recorder.

## Root cause of ~39s discrepancy

**Measured directly against v7's own preserved raw ledger
(`data/field-acceptance/2026-08-31-gate-a-v7-measurement-closure
-reanalysis/counterfactual-merged-full-session.json`, 3,848 real raw
-detection records, recovered and archived by Gate A Measurement Closure
v1) -- not guessed, not re-derived from the prior report's own prose.**

Recomputing `(wall_elapsed_ms) - (source_offset_ms)` for every record
(`wall_elapsed_ms` = each record's own `captured_at` minus the session's
first `captured_at`; `source_offset_ms` = the same delta the ledger already
carries) reproduces the ~39s figure exactly (max +39,213ms at session end)
-- but the *shape* is not a clean monotonic drift: it stays near zero for
roughly the first quarter of the session, dips to **-6,736ms**, then swings
sharply positive and climbs to +39,213ms by the end. Local drift-rate
sampling over ~200-record sub-windows is highly non-uniform (from about
**-23,000 ppm to +69,000 ppm** between adjacent windows) -- inconsistent
with a smooth clock skew (ordinary crystal drift is ~10-100 ppm; a typical
NTP daemon's own maximum slew rate is ~500 ppm).

**This directly proves the ~39s figure was never evidence of a Camera
-Node-vs-Host wall-clock offset.** Both operands of this comparison --
`RawDetectionRecord.source_offset_ms` and `RawDetectionRecord.captured_at`
-- are Node-domain-labeled fields on the *same* record; no Host-domain
timestamp (`received_at`/`decided_at`) ever entered it. It is a different,
narrower problem: this session's own `source_offset_ms` (computed by
`camera_node_live._pop_latest` from `source_monotonic_ns` -- the Node's own
*monotonic* clock -- whenever that field is available) diverging from the
Node's own *wall*-clock `captured_at` reads. v7's own report additionally
confirms **zero reconnects** across the full 89.4-minute session, ruling
out `native_reconnect_step`'s host-time-bridging (which only fires across a
segment transition) as a contributor. A separate, cited-but-unrelated fact
from the same report ("3,848 recorder frames, mean interval 1,395ms against
the configured 1,000ms nominal") describes the *acceptance recorder's* own
save cadence, a different subsystem -- re-checked directly (line 767 of the
v7 report) and confirmed not the mechanism behind this specific number,
only loosely corroborating that real processing overhead exists somewhere
in the pipeline.

Best-supported reading, disclosed with the hedging the evidence actually
supports (not resolved further -- not required for this milestone's own
forward-looking design, and doing so would be exactly the "over-engineer
a clock discipline daemon" this milestone's own §10 warns against): a
genuine Node-internal divergence between its monotonic and wall clocks --
plausibly consistent with post-boot NTP correction on a device without a
battery-backed RTC (a known device class in this project, the Raspberry Pi
Camera Node) -- or a variable gap between when `captured_at` and
`source_monotonic_ns` are each read inside the Node's own capture/encode
pipeline. Neither a "fixed clock offset" nor "timezone/local-time
conversion" explanation fits the measured non-monotonic shape.

**Consequence, load-bearing for this milestone's own scope:** no prior
field cohort (2026-08-19, v5, v6, v7) ever actually measured a real
Node-Host wall-clock offset. `node_to_host_clock_offset_ms` was computed
transiently, per-frame, by every one of them (it is unconditional
production code, not new), but never durably captured. The true
cross-domain offset is, to date, genuinely unmeasured -- this milestone
closes the *measurement gap*, not a previously-known bad number.

## Clock-normalization contract

New pure module `clock_calibration.py` (mirrors every sibling Stage 6.x/7
decision module: no filesystem/network/CUDA/product-repository/SQLAlchemy
import). `ClockCalibrationRecord` carries, per this milestone's own §7
requirement list:

- capture timestamp in source domain -- the caller's own raw
  `t0_captured_at` (unchanged, in `capture_to_visible_latency.py`);
- normalized capture timestamp in Host-compatible domain --
  `NormalizedCapture.host_domain_captured_at` /
  `LatencySample.t0_captured_at_normalized`;
- estimated clock offset -- `offset_ms`;
- uncertainty/error bound -- `uncertainty_ms`;
- drift observation where relevant -- `compute_drift`, informational,
  reported separately from validity;
- invalid/unusable state when confidence is insufficient --
  `state="insufficient_samples"` (calibration layer) and
  `state="invalid_clock_mapping"` (latency layer), both real, auditable,
  never silently fabricated.

Nothing here invents a new network time protocol -- every input is a pair
of timestamps the protocol already carries on every delivered frame
(`captured_at`, `received_at`), matching this milestone's own explicit §6
"Existing protocol facility" instruction.

## Calibration method

`estimate_clock_calibration(pairs, ...)` takes `(node_captured_at,
host_received_at)` pairs and computes `delta_ms = received_at -
captured_at` for each. Because a frame can only travel forward in time
(`delta_ms = true_offset_ms + one_way_transit_ms`, `one_way_transit_ms >=
0` always), the **minimum** observed delta across the window is the
tightest, least-transit-contaminated point estimate of the true offset --
a standard one-way-delay estimation technique, chosen specifically because
the analysis-stream protocol is a one-way push (Node captures and streams;
no Host-initiated request/reply exists to bracket with `H0`/`N`/`H1`, see
"Timestamp-origin trace" item 5 above). `MINIMUM_CALIBRATION_SAMPLES = 5`
is a disclosed, deliberate judgment call (mirroring the precedent
`mockingbird-doctor-operational-health-contract.md`'s own 30-day
backup-staleness threshold already set): fewer than 5 samples produces a
real, auditable `state="insufficient_samples"` record, never a fabricated
number.

Fed from `engine_runtime._EngineSession`'s own per-packet loop (the same
loop that already computes `latest_known_offset_ms` and feeds the
acceptance recorder): every delivered `FramePacket` with both `captured_at`
and `received_at` populated (i.e. every real Camera Node packet, never an
RTSP/local/USB one) is buffered; `_refresh_clock_calibration` drains the
buffer into one new `CounterfactualLedger.record_clock_calibration` call
once per assembly tick (`_ASSEMBLY_TICK_SECONDS = 10.0`, reused, not a new
constant), anchored to that tick's own `source_offset_ms`. A fourth bounded
ledger inside `CounterfactualLedger` (`_BoundedOffsetLedger`, capacity 200,
the same eviction machinery every other ledger there already uses)
retains calibration history, exported via `.query()`'s new
`clock_calibrations` tuple and `GET .../observation/counterfactual`'s own
new `clock_calibrations`/`clock_calibration_required` fields.

## Uncertainty model

`uncertainty_ms = max(deltas) - min(deltas)` -- the observed one-way-delay
jitter spread across the calibration window. This is an honest,
**one-sided, non-NTP** analog of the governing brief's own preferred
round-trip formula (`uncertainty >= (H1-H0)/2`): it does not claim the same
two-sided statistical guarantee a real round trip would (this module never
overclaims that), only that the point estimate could plausibly be off by
up to this much transit-delay variance -- disclosed, not invented as zero,
per this milestone's own explicit "do not pretend network latency is
zero." A wider observed spread produces a wider reported uncertainty
(directly tested, `test_calibration_bounded_uncertainty_widens_with
_jitter_spread`); a tight, low-jitter LAN window reports tight uncertainty.

## Drift handling

`compute_drift(previous, current)` reports `offset_delta_ms`/
`drift_rate_ms_per_minute` between two calibrated samples of the same
stream -- purely informational, never itself a gate. Because a live session
recalibrates every ~10 seconds, later admissions naturally use a fresher
calibration than earlier ones (`active_calibration_for_offset` always
selects the *latest* calibration at or before a given `source_offset_ms`),
bounding drift-induced error to whatever accumulates between consecutive
refreshes rather than trusting a single session-start offset for an entire
long session -- directly satisfying this milestone's own §18 "no
multi-second artificial latency error" requirement without a full
clock-discipline daemon.

## Clock-jump handling

`detect_clock_jump(previous, current, max_jump_ms=5_000.0)` flags a
discontinuity: an offset change between consecutive calibrated samples
larger than a disclosed 5-second threshold (comfortably above ordinary LAN
jitter/inter-tick drift, comfortably below this milestone's own ±30s test
example). `active_calibration_for_offset` then enforces the actual safety
property via an **epoch model**: a stream's calibration history is
partitioned at every `clock_jump_detected=True` sample; a target offset is
only ever answered by a calibration from its own epoch, never
interpolated or extrapolated across a jump boundary, and never
extrapolated backward past the very first calibration a stream ever
recorded. An offset with no governing calibration (predates the first
sample, or falls in a jump's own ambiguous gap) is honestly
`state="no_calibration"` -- never a guess.

## Protocol/runtime changes

**Zero changes to the Camera Node/wire protocol itself.** Every input this
milestone consumes (`captured_at`, `received_at`) was already being
transmitted and already being received before this milestone; nothing new
is required from a Camera Node, so an old, unmodified Camera Node paired
with a new Host degrades gracefully by construction (there is no new field
for it to be missing). All schema/response changes are additive:
`CounterfactualWindowResponse` gains `clock_calibrations: list[...] = []`
and `clock_calibration_required: bool = False`; `CounterfactualLedger`
gains one new optional constructor parameter
(`clock_calibration_expected: bool = False`) and one new public method
(`record_clock_calibration`); `capture_to_visible_latency.build_latency_
samples` gains two new optional parameters
(`clock_calibrations=()`, `clock_calibration_required=False`). No existing
method signature lost a parameter or changed a default's meaning. Database
schema unchanged (`v58`) -- nothing here is persisted to SQLAlchemy at all,
matching the pure/ledger-only shape of every sibling Stage 6.x/7 module.
Doctor's own Clock check `diagnostic_context` string was updated (content
only, same key) to disclose the new *reason* a standalone check still
cannot read Node/Host divergence (a live-session-only in-memory fact now,
not "never computed" as before) -- Doctor does not fail core monitoring
over this, matching this milestone's own §13 instruction.

## Latency computation

`capture_to_visible_latency.py`'s `LatencyState` gains a fourth value,
`invalid_clock_mapping`, kept structurally distinct from
`unavailable_capture_time`/`invalid_negative`/`implausible` everywhere
(`LatencySummary` counts it separately; never folded into another bucket).
`build_latency_samples` gains `clock_calibration_required: bool = False`:

- **`False` (the default, unaffected)**: every one of Gate A Measurement
  Closure v1's own 11 existing tests still passes, byte-for-byte identical
  output -- a same-clock-domain source (RTSP/local/USB/replay) needs no
  mapping at all, and raw subtraction remains exactly as valid as it always
  was for one.
- **`True`** (set by `_EngineSession` when `provider_key == "camera_node"`,
  and by the field-acceptance CLI when a saved ledger says so): T0 is
  normalized through `clock_calibration.normalize_capture_time`, keyed by
  the *admitted* generation's own `source_offset_ms`, before ever touching
  `decided_at`. `state="invalid_clock_mapping"` replaces what used to be a
  silent, merely-caveated cross-domain subtraction whenever no trustworthy
  calibration covers this specific sample.

## Fallback result

Directly regression-tested per this milestone's own §16, with a
deliberate clock jump placed *between* the winner's own epoch and the
fallback's own epoch (winner at `source_offset_ms=0`, offset 1,000ms;
fallback at `source_offset_ms=45,000`, offset 9,000ms, jump-flagged) --
`test_fallback_latency_after_clock_normalization_uses_the_admitted
_members_own_capture_time_not_the_failed_winners` asserts the exact
latency value (11,000ms) that only follows from correctly selecting the
*fallback's own* calibration epoch; using the winner's epoch by mistake
would have produced a materially different, wrong number (18,000ms),
making this a real, discriminating test, not a coincidental pass. This
composes with the pre-existing persistence-boundary proof
(`test_engine_runtime.py`'s own `test_fallback_admission_persists_the
_admitted_members_own_capture_time_not_the_failed_winners`, unmodified,
still green) that the admitted `MediaAssetModel.captured_at` values
themselves are already correct at the database layer -- clock
normalization operates one layer above that, on the same already-correct
per-member facts.

## Stop-finalization result

`test_stop_finalized_candidate_still_normalizes_correctly_under_clock
_calibration` confirms a proposal resolved only at session stop (after
minutes of `blocked_continuation_pending`) still normalizes from its own
true first-capture time via its own governing calibration, unaffected by
*when* the decision was finally reached -- no special-casing exists or is
needed, mirroring the pre-existing (unmodified) stop-finalization proof in
the same file.

## Multi-subject result

`test_multi_subject_siblings_each_get_their_own_correctly_normalized
_capture_time` confirms two concurrent sibling proposals (a feeder subject
and a perch subject, 2 seconds apart) each retain their own correctly
-normalized capture time under one shared stream-level calibration --
never cross-contaminated, never averaged together.

## Compatibility

- **Same-clock-domain sources** (RTSP/local/USB/replay): `FramePacket.
  received_at` is structurally never populated for these (grepped every
  constructor site) -- the calibration buffer never accumulates anything,
  `CounterfactualLedger.clock_calibration_expected` stays `False`, and
  `capture_to_visible_latency.py`'s own default preserves exactly
  pre-milestone behavior. Verified end-to-end (`test_non_camera_node
  _session_ledger_never_expects_clock_calibration`,
  `test_same_domain_default_matches_pre_normalization_behavior_exactly`).
- **A saved ledger snapshot from before this milestone** (no
  `clock_calibrations`/`clock_calibration_required` keys at all): the CLI
  parses this the same way `_track_generation_from_dict` already treats a
  pre-Gate-A-Measurement-Closure-v1 snapshot's own missing
  `start_captured_at` -- absence means "the old codepath applies,"
  honestly, never a crash, matching this exact codebase's own established
  precedent for a new field on the same kind of object
  (`test_old_ledger_snapshot_with_no_calibration_metadata_degrades
  _gracefully_not_a_crash`, `test_old_ledger_snapshot_without_clock
  _calibration_metadata_still_runs_cleanly` -- a real CLI subprocess
  invocation, not only the in-process function). **Disclosed limitation of
  this choice, not hidden:** a hypothetical future snapshot that really
  was Camera-Node-sourced but was captured/saved by tooling that silently
  drops the `clock_calibration_required` key before this milestone's own
  Host code ever runs would default to `False` (raw subtraction) rather
  than `invalid_clock_mapping`. This is the same trade-off Gate A
  Measurement Closure v1's own `start_captured_at` already made and
  accepted, not a new one introduced here, and is unreachable for every
  real cohort to date (all predate `start_captured_at` itself, so `t0 is
  None` already short-circuits to `unavailable_capture_time` before
  calibration is ever consulted -- confirmed by construction, not merely
  argued).
- **Doctor**: reports "not measurable from a standalone check," an updated
  but still-honest disclosure (the underlying constraint -- no live
  session handle -- is unchanged by this milestone); never fails core
  monitoring over it.

## Historical-data limitation

**Not possible to retroactively fix, stated explicitly, not inferred
around** (this milestone's own §22): 2026-08-19, v5, v6, and v7 all predate
`clock_calibration.py` and never captured a single `(captured_at,
received_at)` pair durably. Even where a future replay *did* somehow
supply `clock_calibration_required=True` for one of them, every sample
would still resolve `unavailable_capture_time` first (none of them has
`start_captured_at` either, except none does -- v7/v6/2026-08-19 all
predate that field too, per Gate A Measurement Closure v1's own finding,
unchanged here). **The first cohort that can produce a real, validly
-normalized T0->T5 distribution is a field session run against
post-this-milestone accepted HEAD** -- not self-authorized by this
milestone (see "Decision," below).

## Validation

**Tier 1** (every directly touched/new file -- 4 new files [`clock_
calibration.py`, `test_clock_calibration.py`, plus the new report/contract
-doc update below], 8 modified files, 47 new tests among them):

| File | Result |
|---|---|
| `tests/test_clock_calibration.py` (new) | 26 passed |
| `tests/test_capture_to_visible_latency.py` | 20 passed (11 pre-existing unchanged + 9 new) |
| `tests/test_counterfactual_lineage.py` | 24 passed (19 pre-existing + 1 updated allowlist + 5 new) |
| `tests/test_engine_runtime.py` | 104 passed (99 pre-existing unchanged + 5 new) |
| `tests/test_run_gate_a_measurement_accounting.py` | 4 passed (2 pre-existing unchanged + 2 new) |
| `tests/test_doctor.py` | 107 passed (unchanged; covers the one updated diagnostic string) |

**Tier 1 total: 285 passed, 0 failed.**

**Tier 2** (affected subsystems per this milestone's own §25 -- Camera Node
protocol/timing, Host stream ingest, candidate authority/fallback, Visit
persistence, acceptance recorder, deployment/platform time utilities --
reusing Gate A Measurement Closure v1's own Tier 2 file list exactly, since
this milestone touches the identical subsystem boundary, plus
`test_observation_camera_node_live.py` explicitly for the Camera Node
timing/protocol side):
`test_acceptance_recorder.py`, `test_candidate_visit_adapter.py`,
`test_candidate_visit_authority.py`,
`test_candidate_visit_authority_acceptance.py`,
`test_candidate_visit_review_workflow.py`, `test_candidate_visit_rollback.py`,
`test_concurrent_candidate_visit_persistence_reliability.py`,
`test_observation_session_api.py`, `test_time_utils.py`,
`test_visit_episode_assembler.py`, `test_field_acceptance_authentication.py`,
`test_observation_camera_node_live.py` -- **266 passed, 0 failed** (16
pre-existing FastAPI `@app.on_event` deprecation warnings, unrelated to
this milestone).

**Combined Tier 1 + Tier 2: 551 passed, 0 failed, run together in one
invocation to rule out cross-file interaction, across 18 test files.**

**Ruff:** compared directly against a baseline (moved this milestone's own
2 brand-new files aside, `git stash push` -- deliberately *without* `-u`,
per this milestone's own preserved-file-safety precedent -- on the 12
modified tracked files, ran ruff, then restored both). Baseline: 30
pre-existing findings. After this milestone: **29 findings -- zero new,
one pre-existing finding (`typing.Sequence` imported but unused` in
`counterfactual_lineage.py`) incidentally fixed** by this milestone's own
legitimate new use of `Sequence` in `record_clock_calibration`'s type
hint. Every other diff line was a pure line-number shift from this
milestone's own inserted import lines, not a new or changed finding
(diffed directly, not assumed).

Every `ClockCalibrationRecord`/`CounterfactualClockCalibrationResponse`
construction site in the repository is keyword-argument-only (written that
way from the start, matching Gate A Measurement Closure v1's own verified
convention) -- the two new response fields cannot silently shift an
existing positional argument anywhere.

## Tier 3

**Decision: not run, for the same class of reason Gate A Measurement
Closure v1's own report already established, and arguably more
conservatively true here.** Every production-code behavior change is
either brand-new (a pure module with zero pre-existing callers, cannot
regress anything by construction) or explicitly gated behind a new
parameter that defaults to exactly the pre-milestone behavior
(`clock_calibration_required=False`, `clock_calibration_expected=False`)
-- every one of Gate A Measurement Closure v1's own 11 pre-existing
`capture_to_visible_latency.py` tests, and every pre-existing test in every
other touched file, passes with byte-for-byte identical output, proven,
not assumed. The one behavior-affecting change with no opt-in gate at all
(`engine_runtime.py`'s per-packet loop appending to a new buffer) is a
two-line, purely additive, side-effect-free guarded append that changes
nothing else in that loop -- and the full, unmodified 99-test pre-existing
`test_engine_runtime.py` suite (plus the entire Tier 1/2 set above) already
exercises that loop end-to-end. Tier 1 (285) + Tier 2 (266) = 551 tests
directly cover every touched file and every immediately adjacent
subsystem. Not run "solely because this is called Gate A," matching this
milestone's own explicit instruction against exactly that.

## Self-review

Performed against every item in this milestone's own §27 checklist:

- **Node/Host clocks accidentally assumed equal** -- never; the whole
  contract exists specifically to avoid this, and the default
  (`clock_calibration_required=False`) is scoped to sources that
  structurally cannot have this problem (single clock), not to Camera Node
  sessions.
- **Network RTT ignored** -- disclosed explicitly as an honest, one-sided,
  non-NTP substitute (see "Uncertainty model"), never presented as
  equivalent to a real round-trip bound.
- **Drift mistaken for fixed offset** -- `compute_drift` and periodic
  ~10s recalibration exist specifically so a session-start offset is never
  reused unchanged for a whole long session.
- **Timezone conversion** -- every timestamp in this module is a
  tz-aware, already-UTC-normalized `datetime` (both `AnalysisFrameEnvelope.
  captured_at` and `FramePacket.received_at` are constructed that way
  upstream, unchanged by this milestone); `estimate_clock_calibration`
  raises on a naive input rather than silently misinterpreting it
  (`test_calibration_rejects_naive_timestamps`).
- **Negative latency clamped** -- not touched; the pre-existing
  `invalid_negative` state (never a clamp) is preserved unchanged, and now
  additionally guarded from ever being computed off an unnormalized
  cross-domain subtraction in the first place.
- **Stale calibration reused after clock jump** -- the epoch model in
  `active_calibration_for_offset` is the direct, tested answer
  (`test_clock_jump_invalidates_the_pre_jump_calibration_for_post_jump
  _offsets`).
- **Fallback timestamp contamination** -- directly regression-tested with
  a deliberately discriminating jump between the winner's and fallback's
  own epochs (see "Fallback result," above).
- **Stop-finalization using decision time as capture time** -- not
  possible by construction (`_resolve_t0` only ever reads the admitted
  outcome's own `constituent_generation_ids`, unaffected by *when* the
  decision was reached); tested.
- **Unbounded calibration history** -- `_BoundedOffsetLedger`, capacity
  200, the same mechanism (and the same generous-headroom-over-real
  -sessions sizing rationale) every other ledger in this module already
  uses; tested (`test_clock_calibration_retention_is_bounded`).
- **Local Only dependency accidentally requiring internet/NTP** -- every
  input is a timestamp pair the existing paired Camera Node protocol
  already exchanges; no external NTP server or cloud reachability is read
  or required by this module at any point (see `clock_calibration.py`'s
  own docstring "Local Only").

One incidental finding, fixed as a side effect rather than a defect this
milestone set out to find: a pre-existing unused `typing.Sequence` import
in `counterfactual_lineage.py`, resolved by this milestone's own
legitimate new use of it (see "Validation" above) -- not itself a
correctness issue, disclosed for completeness.

## Remaining field proof

Not self-authorized by this milestone (per its own explicit instruction).
The next daylight cohort run against post-this-milestone accepted HEAD
should collect:

1. Real, valid T0->T5 latency samples (`state == "measured"` with
   `clock_calibration_state == "normalized"`) -- the first cohort able to
   produce these at all.
2. The calibration offset(s)/uncertainty actually observed against the
   real reference Camera Node, and whether any clock jump or excessive
   drift is naturally encountered.
3. Everything already named in Gate A Measurement Closure v1's own
   "Remaining field evidence": a stronger recall denominator; a directly
   comparable fragmentation rate against the now-`READY FOR FORMAL BUDGET
   REVIEW` methodology; 3+-simultaneous-subject activity if naturally
   available (the disclosed, not-yet-benchmarked crowded-feeder/NMS gap);
   continued false-Visit/useful-evidence/duplicate measurements; residual
   `blocked_missing_evidence` traces; the already-known Gate B
   admission-precision residual.

## Decision

**Classification A.**

- Node/Host clock-domain mismatch proven (not assumed) and correctly
  modeled: the ~39s discrepancy previously found was directly re-measured
  from real preserved data and shown to be a *different*, Node-internal
  problem, not evidence of the actual Node-Host offset -- which no prior
  cohort ever measured at all.
- Normalized capture timestamp uses a Host-compatible domain, computed
  from a real, disclosed, non-fabricated calibration.
- Offset uncertainty is explicit on every calibration record and every
  affected latency sample.
- Drift is measured (`compute_drift`) and bounded in practice by periodic
  recalibration; clock jumps are detected and invalidate the pre-jump
  mapping for any offset at or after the jump, tested in both directions.
- Impossible/negative latency remains rejected, never clamped -- unchanged
  and now protected one layer further upstream.
- Fallback uses the admitted member's own capture time *and* its own
  governing calibration epoch, proven with a deliberately discriminating
  test.
- Stop finalization and multi-subject siblings both correct, tested.
- Compatibility graceful in every direction checked: same-domain sources
  unaffected byte-for-byte, old ledger snapshots parse cleanly, Doctor
  stays honest without failing core monitoring.
- Local Only holds -- no external NTP/cloud dependency introduced.
- Tier 1 clean (285/285). Tier 2 clean (266/266). Combined 551/551 in one
  run. Tier 3 explicitly not warranted, decision documented. Zero new ruff
  findings (one pre-existing finding incidentally fixed).

## Next milestone

Not proposed or started here, per this milestone's own explicit
instruction.
