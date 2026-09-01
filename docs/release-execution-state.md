# MockingBird Release Execution State

This file controls execution sequencing, not product doctrine.
[product-doctrine.md](product-doctrine.md) defines what MockingBird is.
[roadmap.md](roadmap.md) preserves the full roadmap. This file records
current accepted state, remaining lanes, release classification, and what
work is presently authorized.

Claude's "next natural milestone" suggestions are advisory only. They do
not authorize future work.

## CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT

MockingBird is still in substantial product development. Representative
Field Acceptance, External Pre-Release Acceptance, and Final Release
Hardening (Lanes R/S, below) are downstream gates and must **not** become
the default next
milestone while substantial product-roadmap capability remains
intentionally unfinished -- see §6, "Global remaining execution queue,"
for the complete remaining-capability picture this phase label is
protecting.

## 1. Current accepted state

- **Repository:** `/home/zkelder/projects/mockingbird-active`
- **Branch:** `main`
- **Accepted HEAD:** `8b5185b` -- the report commit for Representative
  Daylight Gate A Field Acceptance v9 (True-Latency & Precision
  Reconciliation Tranche; see §3/§6.R, below, and
  [representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
  for the complete record). No production code changed by this milestone
  (a live field-acceptance session plus post-hoc offline accounting) --
  `8b5185b` sits directly on top of `17ce108` (the reconciliation commit
  accepting Reference Camera Node RTT-Capability Upgrade & Compatibility
  Re-Proof v1).
- **Prior accepted HEAD (pre-v9):** `1a36b06` -- the report commit for Reference Camera
  Node RTT-Capability Upgrade & Compatibility Re-Proof v1 (see §3/§6.R,
  below, and
  [reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
  for the complete record). No production code changed by this milestone
  (it upgraded and re-verified real Camera Node hardware, not the
  repository) -- `1a36b06` sits directly on top of `1a39479` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v8). Self-correction: this file's own §1 headline bullet was
  not refreshed when v8 was reconciled at `1a39479` (only §3/§6.R were
  updated at the time) -- `1a39479`/`eb75bd6` (v8's own reconciliation/
  report commits) were real, correctly-accepted intermediate states that
  this bullet simply never advanced past; see §3's own chronological
  entries, which are and remain the authoritative record.
- **Prior accepted HEAD (pre-Reference-Camera-Node-RTT-Capability-Upgrade
  -Compatibility-Re-Proof-v1):** `ea38d21` -- the report commit for Camera
  Node <-> Host RTT-Bounded Clock Calibration v1 (see §3/§6.R, below, and
  [camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
  for the complete record), sitting directly on top of `bc6d5ee` (this
  milestone's own implementation commit -- a new `RttRoundTrip`/
  `RttClockCalibrationRecord`/`estimate_rtt_clock_calibration` section in
  `clock_calibration.py` (the accepted one-way estimator entirely
  unchanged alongside it, now scoped to relative drift/jump monitoring
  only), two additive `/node/v1/health` response fields (`mockingbird_
  node/app.py`), a new `CameraNodeClient.sample_clock_round_trip` method,
  an additive `rtt_clock_calibrations` ledger/API/CLI projection, a
  deliberately renamed-not-retyped `rtt_calibrations` parameter and new
  interval fields (`*_min_ms`/`*_max_ms`) on `capture_to_visible_
  latency.py`, a new bounded RTT-recalibration trigger/concurrent-batch on
  `engine_runtime.py`, one Doctor diagnostic-string update, and one
  contract-doc correction -- zero Camera Node/wire-protocol breaking
  change, zero schema/database change, zero Visit-grouping/admission/
  model change), which sits on top of `d25134b` (the reconciliation
  commit accepting Camera Node -> Host Clock Normalization for True
  Capture-to-Visible Latency v1).
- **Prior accepted HEAD (pre-Camera-Node-Host-RTT-Bounded-Clock
  -Calibration-v1):** `1766ad6` -- the report commit for Camera Node ->
  Host Clock Normalization for True Capture-to-Visible Latency v1 (see
  §3/§6.R, below, and
  [camera-node-host-clock-normalization-latency-v1-report.md](camera-node-host-clock-normalization-latency-v1-report.md)
  for the complete record), sitting directly on top of `1e1a78b` (this
  milestone's own implementation commit -- new `clock_calibration.py` plus
  its test file, additive `CounterfactualLedger`/`CounterfactualWindowResult`
  calibration fields on `counterfactual_lineage.py`, an additive
  `clock_calibration_required`/`invalid_clock_mapping` extension to
  `capture_to_visible_latency.py` defaulted to exactly pre-milestone
  behavior, a small additive buffer/tick hook on `engine_runtime.py`,
  additive API-schema/route projection, additive calibration parsing in
  both `run_gate_a_measurement_accounting.py`/`run_encounter_accounting.py`,
  one Doctor diagnostic-string update, and one contract-doc update -- zero
  Camera Node/wire-protocol change, zero schema/database change, zero
  Visit-grouping/admission/model change), which sits on top of `3eeb8ed`
  (the reconciliation commit accepting Gate A Measurement Closure v1).
- **Prior accepted HEAD (pre-Camera-Node-Host-Clock-Normalization-v1):**
  `86955ab` -- the report commit for Gate A Measurement Closure v1 (see
  [gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
  for the complete record), sitting directly on top of `211a368` (this
  milestone's own implementation commit -- new `fragmentation_accounting.py`/
  `capture_to_visible_latency.py`/`scripts/run_gate_a_measurement_accounting.py`
  plus their test files, an additive `TrackGenerationRecord.start_captured_at`/
  `end_captured_at` field pair on `counterfactual_lineage.py` and its API
  -schema/route projection, one pre-existing `run_encounter_accounting.py`
  bug fix, and two new regression tests on already-accepted files
  `engine_runtime.py`/`candidate_visit_repository.py` -- zero Visit-grouping/
  admission/model/schema change), which sits on top of `a5cf039` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v7).
- **Prior accepted HEAD (pre-Gate-A-Measurement-Closure-v1):** `5351e08` --
  the report commit for Representative Daylight Gate A Field Acceptance v7
  (see [representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
  for the complete record), sitting directly on top of `d192a0b` (this
  milestone's own deploy-tooling-fix commit -- `scripts/deploy_windows_dev.py`/
  its own test file only, zero product/perception/admission/Visit/evidence/
  classification code, the same bounded shape as v6's own deploy-tooling
  fix), which sits on top of `5b1c540` (the reconciliation commit accepting
  Pending-Proposal Evidence Preservation & Arbitration Fallback Correctness
  v1).
- **Prior accepted HEAD (pre-v7):** `42d6075` -- the report commit for Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1 (see its own
  "Latest accepted milestone" entry, below, and
  [pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
  for the complete record), sitting directly on top of `1b8dd47` (this
  milestone's own implementation commit -- production code
  `candidate_visit_authority.py`/`candidate_visit_adapter.py`/
  `engine_runtime.py`, their test files, and `docs/candidate-visit-
  authority-contract.md`), which sits on top of `b37656d` (the
  reconciliation commit accepting Representative Daylight Gate A Field
  Acceptance v6 at Classification B).
- **Prior accepted HEAD (pre-Pending-Proposal Evidence Preservation &
  Arbitration Fallback Correctness v1):** `b35b2d4` -- the deploy-tooling-fix commit for
  Representative Daylight Gate A Field Acceptance v6 (see its own "Latest
  accepted milestone" entry, below, and
  [representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
  for the complete record), sitting on top of `26edddf` (the implementation
  commit for Background / Empty Evidence Species-Confidence Correctness v1,
  unchanged, not itself re-run, by this milestone). This milestone's own
  report commit (`40e4f5e`) sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention -- the deploy-tooling fix itself (bounded to `scripts/deploy_
  windows_dev.py`/its own test file, zero product/perception/admission/
  Visit/evidence/classification code) is the only code this milestone
  actually changed; see "Latest accepted milestone," below, for why a
  Classification B field session still cites a real code-bearing HEAD.
- **Prior accepted HEAD (pre-v6):** `26edddf` -- the implementation commit for Background /
  Empty Evidence Species-Confidence Correctness v1 (see its own "Prior
  accepted milestone" entry, below, and
  [background-empty-evidence-species-confidence-correctness-v1-report.md](background-empty-evidence-species-confidence-correctness-v1-report.md)
  for the complete record), sitting on top of `428fcb3` (the reconciliation
  commit that authorized Representative Daylight Gate A Field Acceptance v6
  as the next Lane R milestone).
- **Prior accepted HEAD (pre-Background/Empty Evidence Species-Confidence
  Correctness v1):** `65f5ec2` -- Representative Daylight Gate A Field
  Acceptance v5's own report commit (`e203489`) plus one same-day,
  self-caught follow-up commit adding a section its own governing
  template required but the first draft omitted (`65f5ec2`; no field
  evidence changed, only the report's own completeness), sitting on top
  of `eeb5f98` (the reconciliation commit accepting Lane C Sparse-State
  Honesty & First-Hour Narrative Closure v1), for the identical reason
  v4's own report commit was cited standalone below: a real, live
  ~106.6-minute field session that changed zero production code (see its
  own "Prior accepted milestone" entry, below, and
  [representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
  for the complete record).
- **Prior accepted HEAD (pre-v5):** `cb2a561` -- the implementation commit for Ongoing
  Monitoring Failure Diagnostics for RTSP / Local USB / Windows DShow v1
  (its own separate report commit, `7dd5146`, sits directly on top and is
  not cited here as a second, separate code-bearing HEAD, matching this
  field's established convention). `6a448e3` (the implementation commit
  for Login Rate-Limiting & Authentication Abuse Resistance v1; its own
  separate report commit, `54b90fa`, sits directly on top, likewise not
  cited separately). `83b15a5` (the implementation commit for Historical
  Species-Status ("New" vs. "Seen Before") Correctness v1; its own separate
  report commit, `b619546`, sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention). `e3c293f` (the implementation commit for
  Release Licensing, Distribution & Third-Party Legal Closure v1; its own
  separate report commit, `d1a2955`, sits directly on top and is not
  cited here as a second, separate code-bearing HEAD, matching this
  field's established convention). `893eed5` (the implementation commit
  for Platform / Runtime Portability & Support Truth Closure v1; its own
  separate report commit, `d5f4a32`, sits directly on top, likewise not
  cited separately). `6f7bbb6` (the implementation commit
  for Sustained-Activity Visit Admission Starvation & Stop-Finalization
  Correctness v1; its own separate report commit, `0638759`, sits
  directly on top, likewise not cited separately).
  `81dec47` (the implementation commit for Local
  Only / Privacy Closure v1; its own separate documentation-only report
  commit, `64f0a4d`, sits directly on top and is not cited here as a
  second, separate code-bearing HEAD, matching this field's established
  convention). Native-Windows Packaged Local-Only Acceptance & Privacy
  Closure v1's own report commit (`c8016b9`) also sits on top, likewise
  not cited as a separate code-bearing HEAD -- that milestone found zero
  reproduced defects and changed zero production code, so it added only
  its own report file. Representative Daylight Gate A Field Acceptance
  v4's own report commit (`270b6ba`) sits on top next, for the identical
  reason: a real, live ~112-minute field session that changed zero
  production code (the real defect it found is disclosed, not fixed --
  see its own "Prior accepted milestone" entry, below).
  `9c52c7f` (Retention Correctness & Bounded Cleanup
  Closure v1's own implementation commit), `fe54ac9` (Storage / Retention /
  Disk-Pressure & Recovery Closure v1's own implementation commit),
  `1656f1a` (Non-Interactive Field Acceptance Authentication & Session
  Access v1's own implementation commit), `18a0025` (Whole-Product UI /
  Accessibility / Performance Closure v1's own implementation commit),
  One-Release Roadmap & Scheduler Reconciliation v1's own commit
  (documentation-only, `4312b18`), and Camera Node Upgrade &
  Compatibility Recovery v1's own three implementation commits sit
  underneath it in history; the intervening reconciliation commits for
  those closures (`7f98e43`, `8572308`, `4581424`, `4aeb658`, `e01e691`,
  `c03d0b1`, `80e1bb3`) are likewise not cited as separate code-bearing
  HEADs for the identical reason.
- **Schema:** `v58` -- unchanged by Representative Daylight Gate A Field
  Acceptance v7 (a live field-acceptance session plus one bounded deploy-
  tooling fix; zero product/perception/admission/Visit/evidence/
  classification code touched, zero schema-bearing code touched). Also
  unchanged by Pending-Proposal Evidence Preservation & Arbitration Fallback
  Correctness v1 (bounded, pending-proposal-aware preservation and
  deterministic same-component fallback added entirely within existing
  in-memory session state; no new/changed table). Also unchanged by
  Representative Daylight Gate A Field Acceptance v6. Also unchanged by
  Background / Empty Evidence Species-
  Confidence Correctness v1 (reads the already-existing, already-migrated
  `MediaAssetModel.geometry_attribution_json` column, schema 33; adds one
  new optional function parameter and one new pure-decision-function
  reason code, no new table/column/migration). Also unchanged by
  Representative Daylight Gate A Field
  Acceptance v5 (a live field-acceptance session; zero production code
  touched). Also unchanged by this milestone (Lane C Sparse-State
  Honesty & First-Hour Narrative Closure v1 is a single-branch precedence
  fix in `_dashboard_runtime_by_stream` -- api/main.py -- plus two
  frontend copy paragraphs; no DTO field, table, or column was added).
  Also unchanged by Ongoing Monitoring
  Failure Diagnostics for RTSP / Local USB / Windows DShow v1 (adds one new
  file, a new in-memory session field, and bounded application-code-only
  edits across the playback/repository/API layers; every new failure code
  is stored in the pre-existing, already-unbounded-length `StreamRuntime
  CheckpointModel.failure_code` `String` column, so no new table/column/
  migration was needed). Also unchanged by Login Rate-Limiting &
  Authentication Abuse Resistance v1 (adds one new file plus bounded edits
  to `authenticate_user`/`sign_in`; throttle state is deliberately
  in-memory only, never persisted, so it needed no new table/column/
  migration). Also unchanged by Historical Species-
  Status ("New" vs. "Seen Before") Correctness v1 (touches one test file
  only; zero production code). Also unchanged by Release Licensing,
  Distribution & Third-Party Legal Closure v1 touches only packaging
  tooling and documentation -- `scripts/build_local_product.py`, a new
  `THIRD_PARTY_NOTICES.md`, and two doc files -- no model/migration
  change). Platform / Runtime Portability & Support Truth Closure v1 (an
  evidence/documentation closure plus two narrow capability-message fixes
  in `mockingbird.diagnostics.doctor`) had likewise left schema unchanged.
  Sustained-
  Activity Visit Admission Starvation & Stop-Finalization Correctness v1
  (see its own "Prior accepted milestone" entry, below) had likewise left
  schema unchanged. Representative Daylight Gate A Field Acceptance v6 also
  left schema unchanged -- its own deploy-tooling fix touches only
  `scripts/deploy_windows_dev.py`/its test file, no model/migration.
  Pending-Proposal Evidence Preservation & Arbitration Fallback
  Correctness v1 also leaves schema unchanged -- a new arbitration field
  (`AmbiguousBoundaryArbitration.fallback_order_by_winner_id`), two new
  adapter functions, and bounded in-memory engine-runtime state
  (`_MAX_PROTECTED_EVIDENCE_IDS`, four new session-lifetime counters
  surfaced through the existing `advanced` diagnostics dict); no new
  table/column/migration.
- **Latest accepted milestone:** Pending-Proposal Evidence Preservation &
  Arbitration Fallback Correctness v1 -- see
  [pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the exact defect
  Representative Daylight Gate A Field Acceptance v6 measured (see its own
  entry, below): a real arbitration winner permanently failing at the
  downstream evidence-availability gate (the bounded, insertion-order-only
  128-entry evidence-byte cache) with no fallback to a runner-up, losing
  48/263 distinct proposals (18.3%) in that real session. Root cause:
  `evaluate_candidate_authority` has no evidence-availability gate at all;
  `blocked_missing_evidence` is not retryable; `_run_assembly_tick`
  attempted every ambiguous-component member exactly once with no code
  path reconsidering a component once its chosen winner failed downstream.
  Two mechanisms, both implemented and independently tested, per this
  milestone's own governing brief's explicit requirement for both:
  **preservation** (`engine_runtime._compute_protected_evidence_ids`, a
  bounded (`_MAX_PROTECTED_EVIDENCE_IDS=64`), per-tick-recomputed set of
  still-actionable proposals' priority evidence, consulted by the shared
  cache's own real eviction policy so it prefers evicting something
  unprotected first) and **fallback**
  (`candidate_visit_authority.AmbiguousBoundaryArbitration.fallback_
  order_by_winner_id` plus `_EngineSession._attempt_resolved_component`,
  which walks a resolved component's winner then its own remaining stable
  members, in the identical rank order arbitration already computed,
  stopping at the first admissible member or once the component's members
  are exhausted -- never rerunning arbitration, never crossing components).
  The unchanged 128-entry cache bound itself was deliberately *not* raised
  again, per the milestone's own explicit instruction. Two real design
  corrections were found and fixed during this milestone's own
  implementation and adversarial self-review (both fully documented in the
  report and in `docs/candidate-visit-authority-contract.md`): the
  priority-evidence preview must use currently-cached bytes, not `media=
  None` (real, live-captured evidence never declares `decodable=True`
  upfront, so a bytes-free preview would hard-reject every real candidate
  and protect nothing); and every resolved component must be walked as one
  atomic unit before any ordinary proposal is attempted at all, since
  `new_proposals`' own emission order has no guaranteed relationship to
  arbitration rank (a losing sibling reached first was being double-
  attempted once its own winner's chain later reached it, corrupting
  `proposals_observed`/the ledger -- found before it reached a committed
  test, fixed, and locked in by a dedicated permanent regression test).
  19 new/updated tests, all confirmed RED on accepted `b37656d` (via
  `git stash` isolating the three production files) and GREEN after the
  fix, including a 105-simulated-minute v6-shaped replay against the real
  bounded cache (two simultaneous subjects, real eviction, real
  protection) whose own pre-fix failure was independently confirmed
  genuinely RED via direct reproduction of the real mechanism (zero
  admissions, real `blocked_missing_evidence`/`blocked_ambiguous_boundary`
  mix), and dedicated exactly-once, fragmentation, multi-subject-isolation,
  and stop-finalization proofs. Tier 1 187/187, Tier 2 279/279, Tier 3 (one
  full Core run, `pytest -m "not slow"`, 5372 tests) 5357 passed, 3
  skipped, 11 xfailed, 1 failed -- the one failure
  (`test_temporal_capture_cli.py::test_run_capture_end_to_end_reconnect_
  produces_a_native_session_timeline`) independently confirmed unrelated
  (zero code-dependency relationship to any file this milestone touched;
  passes on the exact pre-fix baseline; passes 5/5 consecutive runs in
  isolation with the fix in place; only failed once, inside this
  investigation's own necessary four-way concurrent chunked Core
  execution -- an artifact of working around this environment's own
  10-minute background-task cap on a single `pytest -m "not slow"`
  invocation, not a product defect). No schema change. This closure does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, External Pre-Release Acceptance, or Final Release Hardening,
  and does **not** select a next development milestone -- authorization
  returns to the bold statement in §3, below, unchanged by this closure.
  This is nighttime/implementation correctness work only, per this
  milestone's own explicit non-goal: no field session was run. See §6.R,
  below, for the updated "Remaining Gate A dependency" this closure leaves,
  and this milestone's own report, "Next field proof required," for
  exactly what the next daylight cohort must prove.

- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v6 -- Post-Fix Replication & Multi-Subject Tranche -- see
  [representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
  for the complete record. Classification **B**. A real, live
  106.63-minute Observation session against the real reference Camera
  Node, on the accepted, unmodified build, directly confirmed the
  *specific* Sustained-Activity Visit Admission Starvation mechanism v4
  found (arbitration deferring a whole connected component forever) does
  **not** recur -- arbitration reached a decision for every ambiguous
  component on schedule throughout. But `candidates_created` ended the
  session at **zero** despite substantial, independently-confirmed,
  sometimes-simultaneous real wildlife activity (two exhaustively-reviewed
  real activity segments, each directly confirmed via full-resolution
  independent-recorder frames and containing genuine multi-bird moments,
  0/2 represented by any admitted Visit) -- the same practical symptom v4
  produced, now root-caused to a *different*, precisely source-traced
  mechanism: the sole arbitration winner for a real, resolved component can
  fail at the downstream evidence-availability gate (the bounded 128-entry
  evidence-byte cache, evicted purely by insertion order with no awareness
  of which pending proposal still needs which bytes), and because that
  outcome is not retryable and no fallback to a runner-up exists, the
  component's real activity is permanently lost. This is a concrete,
  real-field instance of an already-disclosed residual risk -- named,
  explicitly not fixed, when the evidence-cache bound was last raised
  32->128 ("a pending-proposal-aware eviction policy... is a materially
  larger change... left as a disclosed follow-up, not undertaken here") --
  not a new defect class, but a materially sharper session-wide measurement
  of its real consequence (48/263 distinct proposals, 18.3%, spread across
  the full session, versus v5's own 2.8%) than existed before, and shown
  for the first time to also reach the *ordinary* (non-forced) arbitration
  path, not only the recency-forced path the original disclosure discussed.
  Stop-finalization behaved correctly (the honest `stopping`/`stopped`
  cycle was observed live, rescuing 0 -- consistent with root cause, not a
  regression, since nothing cleanly resolvable remained pending at stop).
  Zero `blocked_shadow_mode`, zero persistence contention, zero
  ERROR/CRITICAL/WARNING lines in the full structured session log.
  Background/empty-evidence eligibility and species assistance were not
  exercisable this session (zero admitted Visits ever reached either
  layer) -- disclosed as honest measurement gaps, not fabricated proof.
  Real, directly-confirmed simultaneous multi-subject activity occurred
  (not manufactured) but, exactly like v5's own session for a different
  reason, never reached an admitted Visit, so multi-subject Visit-grouping
  correctness remains completely unexercised end-to-end across two
  consecutive post-fix cohorts now. Two bounded, tested, own-session
  deploy-tooling defects were found and fixed along the way (a
  `UnicodeDecodeError` crash in `_run_powershell`'s non-UTF-8 output
  handling that was masking a real, unrelated failure, RED->GREEN proven
  with a new regression test; a separate, disclosed-not-fixed `--dev-root`
  WSL-path usability gap) -- zero product/perception/admission/Visit/
  evidence/classification code touched. Per the milestone's own explicit
  §14 failure conditions and §35 acceptance bar, this is deliberately
  **not** rounded up to Classification A on the strength of the
  investigation's own rigor alone: `candidates_created` remaining at zero
  for a prolonged real sustained-activity session is one of this
  milestone's own five explicit failure conditions, and "post-fix admission
  behavior replicates"/"in-session admissions occur" are both explicit
  Classification A requirements that did not hold this session. This
  closure does **not** authorize the next Representative Field Acceptance /
  Gate A session, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone --
  authorization returns to the bold statement in §3, below, unchanged by
  this closure. This reopens, rather than closes, a specific Gate A
  correctness question -- see §6.R, below, for the complete "Remaining Gate
  A dependency" account.

- **Prior accepted milestone:** Background / Empty Evidence Species-
  Confidence Correctness v1 -- see
  [background-empty-evidence-species-confidence-correctness-v1-report.md](background-empty-evidence-species-confidence-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the exact v5-
  disclosed Gate B defect class below: a weak, single-detection,
  `terminal_reason: maximum_unsupported_duration` localization's crop --
  real bytes, ordinary size, subject-focused tier -- received a confident
  ("Brown Thrasher," 89.9% score, 0.857 margin) wrong BioCLIP species
  label, clearing even the strictest existing abstention floor (proving no
  score/margin/tier change could ever catch it). Root cause: `evaluate_
  identification_eligibility` had no signal independent of BioCLIP's own
  output to ask whether a crop's box corresponds to a real, contemporaneous
  detector observation. Fix reads the already-persisted (schema 33)
  `MediaAssetModel.geometry_attribution_json`; a crop backed by tracker-only
  extrapolation or a stale carried-forward box, at the two crop tiers with
  no other same-moment-correspondence guarantee, is now ineligible --
  proven RED->GREEN against the real production `identify_review_queue_
  item` path, real-cohort validated (11/40 real background Visits newly
  abstain, 0/7 mandatory real positive controls regress). Several
  alternative signals (detection count, bbox size/coverage, padding ratio)
  were tested against real data and rejected as non-discriminating before
  this fix was chosen. Tier 1 82/82, Tier 2 456/456, Tier 3 clean apart from
  2 independently-verified pre-existing, unrelated failures. Honestly
  bounded, not oversold: a detector-sourced-but-still-wrong background
  crop (a genuine, contemporaneous, but recurring/confident false read)
  remains an open, disclosed Gate B residual -- not solved by this
  milestone, unchanged from before it. No schema change. No BioCLIP/
  detector/admission/Visit-assembly change. Does not authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does not select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure.

- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v5 -- see
  [representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
  for the complete record. Classification **A**. A real, live
  ~106.6-minute Observation session against the real reference Camera
  Node -- the identical Stream/scene that exposed Representative
  Daylight Gate A Field Acceptance v4's own admission-starvation defect
  -- on freshly-deployed accepted HEAD (`eeb5f98`, schema v58 unchanged).
  Directly, conclusively confirms the accepted Sustained-Activity Visit
  Admission Starvation & Stop-Finalization Correctness v1 fix works
  end-to-end under real sustained genuine wildlife activity:
  `candidates_created` reached its first real admission ~25 seconds into
  the session (v4 stayed at exactly 0 for its entire ~112-minute
  session) and climbed steadily throughout (19 real Visits admitted by
  session end, not only at stop); the new honest `stop_finalization_
  pending` status was observed live for the first time in a real field
  session, correctly appearing then clearing while the finalize tick
  genuinely rescued 2 more pending candidates (17 -> 19); zero
  `blocked_shadow_mode`, zero persistence-contention, zero duplicate
  Visits across the whole session -- no recurrence of any of the three
  defects that milestone fixed. One real defect found and precisely
  root-caused, not fixed (per the governing brief's own bar): a single
  false-positive admission (a weak, single-detection, `terminal_reason:
  maximum_unsupported_duration` localization) received a confident
  ("Brown Thrasher," 89.9%) but wrong BioCLIP species label on a crop
  direct pixel-region inspection against its own real bounding box
  confirms is empty background -- a fresh, concretely-reproduced
  instance of the already-known Gate B "background evidence -> confident
  label" regression class `roadmap.md` already names as open work, not a
  new starvation-family defect and not release-blocking for this
  milestone's own scope. Gate A/Lane R remains open (see §6.R, below);
  this closure does not authorize the next Representative Field
  Acceptance session, External Pre-Release Acceptance, or Final Release
  Hardening, and does not select a next development milestone --
  authorization returns to the bold statement in §3, below, unchanged by
  this closure.

- **Prior accepted milestone:** Lane C Sparse-State Honesty & First-Hour
  Narrative Closure v1 -- see
  [lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md)
  for the complete record. Classification **A**. Closes both bounded DEV
  gaps the accepted read-only Lane C reconciliation left open (§6.C,
  below): sparse/no-wildlife honesty under primary detector/GPU/model
  failure, and a coherent first-hour onboarding narrative. Root-caused the
  first gap to one specific line: `_dashboard_runtime_by_stream`
  (api/main.py) computed a Camera Node Stream's Dashboard/`ProductHealth`
  failure text as `engine_status.camera_message or engine_status.message`.
  `camera_message` ("Camera Node is paired and configured.") is set
  unconditionally, early -- before the Observation Engine's own detector/
  GPU/model load is even attempted -- and is never cleared once the camera
  connects, so it stayed truthy and the `or` always picked it, discarding
  the real, already-correctly-resolved failure text
  (`engine_status.message`) whenever the *engine* (not the camera) was
  what actually failed while the camera stayed perfectly reachable --
  self-contradicting an already-correct "Camera unavailable"/alert-tone
  badge with reassuring "paired and configured" wording next to it.
  Reproduced RED against the real, unmodified pre-fix code first (a fake,
  side-effect-free `ObservationEngineSessionManager.status()` read mirroring
  a real `_EngineSession` GPU-failure shape, the same technique
  `test_dashboard_observation_engine_truth.py` already established): only
  the message-precedence assertion failed -- `camera_health.state`,
  `needs_attention_count`, and `ready` were already correct pre-fix,
  precisely scoping the real defect to message text alone. Fixed by
  reusing, not re-deriving, the exact camera-connected-wins-only-if-
  disconnected precedence `_EngineSession.snapshot`'s own "headline
  whichever subsystem is actually blocking" contract already defines
  (`engine_message if engine_status.camera_connected else camera_message`)
  -- no additive `ProductHealthStatus`/`CameraHealthSummary` field needed;
  the existing `CameraHealthState.camera_unavailable` state (already
  alert-toned in the frontend) plus a correct message fully express the
  truth. Zero frontend change needed: `DashboardPage.tsx` already renders
  `camera.failure_reason ?? camera.message` verbatim. Confirmed
  independently: a healthy detector stays unaffected; a genuine camera/
  transport failure keeps its own distinct message, never the detector/GPU
  wording; acoustic (BirdNET) status stays independent, never implied by
  or implying the visual detector's own state; BioCLIP failures are
  structurally incapable of reaching this code path at all
  (`_schedule_automatic_identification` wraps its entire body in
  `try/except Exception: return`, "must never break admission" -- it
  cannot touch `_engine_available`/`_engine_message` under any failure).
  The onboarding gap: `web/src/components/OnboardingWizard.tsx` had two
  stale paragraphs (Welcome step, post-camera-setup Observe step) telling
  first-time users a sighting "appears in"/"lands in" Review Queue,
  predating the shipped review-optional design
  (`docs/product-doctrine.md` "Core flow": Observe -> Discover -> Understand
  -> Confirm -> Remember -> Improve, discovery through Today/Bird Log/Visit
  detail; "Measured, Inferred, and Reviewed": Inferred output must be
  useful immediately, never gated on confirmation first). Rewritten to
  name Today/Bird Log as where sightings actually show up, reusing already-
  established terminology ("Likely"/"Not yet confirmed" from
  `BirdLogPage.tsx`) rather than inventing new vocabulary; Review Queue
  remains named and available for deliberate batch review, just no longer
  framed as the normal destination. No screens added, no wizard-flow
  change. 7 new tests: `tests/test_dashboard_detector_health_honesty.py`
  (4, backend) and `tests/test_onboarding_narrative_copy.py` (3, a
  lightweight static-source-text regression -- not a new frontend
  unit-test framework -- covering the Observe-step paragraph the
  established e2e suite cannot reach without disproportionate new
  camera-pairing scaffolding); the existing
  `web/e2e/onboarding.spec.ts` gained two assertions on the Welcome-step
  paragraph, verified against a real rendered browser DOM
  (`npm run test:e2e:onboarding`: 6/6 passing). Tier 1: 7/7 passing. Tier
  2 (30 files, the established health/dashboard/camera/onboarding/setup-
  adjacent subsystem sweep): 594 passed, 11 xfailed (pre-existing), 0
  failed. Tier 3 (full Core) deliberately not run -- a single-branch
  precedence fix confined to one function, zero DTO/schema change, and
  Tier 2's own 594-test sweep already covers every real consumer of the
  touched function. `ruff check`: zero new findings on
  `src/mockingbird/api/main.py` (26 pre-existing findings confirmed
  unrelated via direct `git stash push -u` bisection -- identical count
  and finding set, none within ~2,300 lines of the touched function); the
  two new test files clean. `tsc --noEmit` clean. No schema change (see
  "Schema," above). `docs/release-execution-state.md` §6.C now reconciled
  to **MATERIALLY DELIVERED / NO KNOWN DEV REMAINS** (see below). This
  closure does **not** authorize the next Representative Field Acceptance
  / Gate A session, Lane G validation, provider integrations, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- authorization returns to **NONE
  -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED** (§3, below),
  unchanged by this closure.
- **Prior accepted milestone:** Ongoing Monitoring Failure Diagnostics
  for RTSP / Local USB / Windows DShow v1 -- see
  [ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md)
  for the complete record. Classification **A**. Closes Lane G's
  remaining disclosed gap (`camera-source-experience-v1-report.md`'s own
  section 7): once a non-Camera-Node Stream (RTSP, local USB, Windows
  DirectShow) is armed and running, a concrete failure cause
  (authentication, network, codec, decode) collapsed to one generic
  ongoing-monitoring message, even though setup-time validation already
  distinguished these causes. Confirmed the starting-state premise before
  starting (branch `main`, accepted HEAD `b1c78dc`, schema v58, the seven
  preserved untracked files present and untouched, no active worktree
  writer) -- matched exactly. Root-caused to two independent chokepoints,
  both confirmed by direct code reading before any fix: the long-running
  playback processes these three providers start used
  `stderr=subprocess.DEVNULL` unconditionally (no evidence was ever
  captured to classify with in the first place -- unlike the bounded
  one-shot setup-time probe, which already opted into capturing it), and
  even a correctly classified code would have been discarded by two
  separate hardcoded Camera-Node-only allowlists (`api.main._managed_
  camera_status`; `ProductRepository.mark_monitoring_backoff_with_
  failure_code`) before ever reaching a user. Reproduced against the
  real, unmodified pre-fix code via a direct `git stash` bisection: a
  real `"401 Unauthorized"` ffmpeg stderr line was silently discarded,
  collapsing to `"Camera process ended before the session was stopped."`
  regardless of cause. Fixed with a new, bounded, continuous
  `BoundedStderrDrain` (`playback/stderr_drain.py`) -- one dedicated
  daemon thread per monitored process, never blocking the child (unlike a
  naive switch to `stderr=PIPE` alone), retaining only a small
  (4096-byte), credential-redacted tail, owned by exactly one session's
  lifecycle and stopped from every exit path. Classification reuses the
  canonical vocabulary rather than building a second one: RTSP's
  setup-time `_classify_probe_failure` is now public
  (`classify_rtsp_failure_text`) and called unmodified by both setup
  validation and ongoing monitoring, proven identical by a dedicated
  setup/ongoing-agreement regression test; local USB and Windows
  DirectShow gained new, deliberately narrow classifiers backed only by
  real, reproducible evidence -- real ffmpeg 6.1.1 V4L2 stderr text
  gathered against this project's own Linux dev sandbox (device-missing,
  permission-denied) and real ffmpeg.exe 8.1.2 DirectShow stderr text
  gathered live against the project's own reference Windows dev host
  (device-unavailable -- the one category that host's zero attached video
  devices could actually produce) -- with an honest, provider-scoped
  generic fallback for every other cause, never a fabricated one. A live,
  real, end-to-end proof beyond unit tests (zero mocking anywhere in the
  call chain): a genuine `LiveCameraSessionManager` session against a
  real, disposable, instantly-refused local port correctly classified
  `camera_setup_rtsp_unreachable`. No retry/backoff timing logic was
  touched (`monitoring/durable_supervisor.py` has zero diff); recovery
  already clears stale failure state unconditionally via the pre-existing,
  unmodified `mark_monitoring_running`, re-verified correct for the new
  codes with a real-repository integration test. 26 new tests
  (`tests/test_ongoing_monitoring_failure_diagnostics.py`), each
  independently confirmed RED (via a real `ModuleNotFoundError` before
  implementation, or via the `git stash` bisection above) and GREEN
  after -- covering RTSP classification, setup/ongoing consistency,
  local_usb/windows_dshow evidence-backed-only classification, a
  dedicated Camera-Node-unaffected regression, credential redaction, a
  real ~4MB-stderr subprocess stress proof (no deadlock, bounded memory,
  drain keeps up), repeated-cycle thread-leak and concurrent-throughput
  proofs, multi-Stream isolation, and failure-code plumbing through
  `ManagedCameraStatus`/`StreamRuntimeStatusResponse`/`CameraHealthSummary`.
  Two pre-existing `test_stream_playback_contract.py` tests had
  fixed-signature test doubles that broke on the new `capture_stderr`
  keyword parameter this milestone adds to the three bridge modules'
  process-starting functions -- fixed (test-only signature widening, not
  a product defect). Tier 1: 26/26 passing. Tier 2 (20 files, the
  established camera/source/monitoring/health subsystem suite plus this
  milestone's own new file): 503 passed, 11 xfailed, 0 failed. Tier 3
  (`scripts/verify_core.py`, one full run): 5310 passed, 3 skipped, 23
  deselected, 11 xfailed, 0 failed -- no bisection needed. `ruff check`:
  0 new findings on every touched/new file, each individually confirmed
  via clean-baseline `git stash` bisection. No schema change (see
  "Schema," above). Local USB/Windows DirectShow hardware acceptance
  (device-busy, permission-on-real-hardware, unsupported-format) and a
  real RTSP camera's own live auth/codec failure remain genuinely
  untested -- honest, disclosed, not claimed; see the report's own
  "Remaining risks." Lane G moves from `PARTIAL, MATERIALLY CLOSED` to
  **MATERIALLY CLOSED / VALIDATION REMAINS** (see §6, below). This
  closure does **not** authorize the next Representative Field
  Acceptance / Gate A session, Lane C work, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure.
- **Prior accepted milestone:** Login Rate-Limiting & Authentication
  Abuse Resistance v1 -- see
  [login-rate-limiting-authentication-abuse-resistance-v1-report.md](login-rate-limiting-authentication-abuse-resistance-v1-report.md)
  for the complete record. Classification **A**. A RELEASE-SECURITY
  milestone, directly authorized outside this file, closing a real,
  previously-disclosed pre-existing gap: `POST /api/auth/sign-in` had
  generic, enumeration-safe failure behavior (unknown user/wrong password/
  disabled user all already returned the identical outcome) but no attempt
  counting, no delay, and no throttling of any kind -- first found by
  Mobile & Remote Experience v1's own security review, re-disclosed by
  several milestones since (most recently Non-Interactive Field Acceptance
  Authentication & Session Access v1). Root-caused against all ten of the
  governing brief's own diagnostic questions before any fix, confirming the
  gap was real and precisely bounded to one endpoint/one repository method.
  New `mockingbird.security.login_rate_limiter.LoginRateLimiter`: a small,
  dependency-free, thread-safe, in-process helper (not a general-purpose
  rate-limiting framework) with two independently-keyed, jointly-evaluated
  dimensions -- account (`login_identity`, real or not, so a nonexistent
  username throttles identically to a real one) and source (the direct TCP
  peer address, never a forwarded header, since this deployment establishes
  no trusted-proxy boundary for one) -- so neither a username spray (one
  source, many accounts) nor a distributed spray (many sources, one
  account) goes unbounded. The first 3 failures add no delay (typo
  tolerance, matching every pre-existing test that already made up to three
  wrong sign-in attempts); every failure after that walks a short, fixed,
  hand-picked ladder (1s/2s/5s/15s/30s/60s) that plateaus at 60 seconds
  forever -- no permanent lockout anywhere, proven directly by driving well
  past the ladder's own length and by a real multi-source distributed-spray
  test confirming ordinary time advancement always restores access. Both
  dimensions are hard-capped at 10,000 live entries with O(1)-amortized
  least-recently-touched eviction/pruning (an `OrderedDict`-backed design)
  -- an earlier plain-`dict`-plus-`min()`-scan version was found, by this
  milestone's own bounded-state tests, to cost several real seconds at
  10,000 simulated attempts, and was fixed before being accepted, closing
  a self-inflicted CPU-cost gap the governing brief's own "high-rate
  attacker must not cause unlimited memory growth" bar reasonably extends
  to cover. **Persistence: in-memory only, deliberately** -- weighed
  explicitly against the brief's own in-memory/persistent/hybrid framework;
  a local-first appliance does not need enterprise-grade persistent
  lockout state, and persisting it would itself become a new, worse
  denial-of-service surface (a throttle row outliving the very restart an
  owner would use to recover). Restart (or a local backup restore's own
  process-wide `ProductRepository` singleton swap -- an already-established
  precedent for resetting this exact class of in-memory session-adjacent
  state) clears all throttle state, which doubles as the owner's whole
  recovery lever if ever throttled themselves -- no new account-recovery
  mechanism was built or is needed. Monotonic clock throughout (never
  wall-clock, immune to NTP/DST/manual-clock changes), constructor-
  injected for fully deterministic tests -- zero real sleeps anywhere in
  either new test file. The outward HTTP contract is unchanged: the
  identical generic `401` for unknown user, wrong password, disabled user,
  and now, additionally, a currently-throttled account/source (even with
  the genuinely correct password) -- verified by a direct response-
  equality regression test comparing all three cases' real status code,
  JSON body, and cookie absence. Three new bounded audit events
  (`auth.login_failed`/`auth.login_throttled`/`auth.login_succeeded_
  after_failures`) reuse the existing `AuditLogEntryModel` mechanism with
  zero schema change, verified to never carry a password or token in their
  metadata; a throttled-while-already-throttled attempt writes no
  additional audit row at all, since it never reaches the database (bounded
  by construction, not a separate suppression rule). No session is ever
  created on a failed or throttled attempt, verified directly against real
  session-table row counts. 31 new tests: `tests/test_login_rate_
  limiter.py` (21, pure unit, fake clock, no DB/HTTP) and `tests/test_
  login_rate_limiting.py` (10, full product integration through real
  `POST /api/auth/sign-in` calls, including genuinely simulated distinct
  source addresses via `httpx.ASGITransport`'s own `client` parameter);
  `tests/test_local_identity_multi_user.py`'s 36 pre-existing tests pass
  unmodified, direct proof of zero behavior change to bootstrap, session
  lifecycle, authorization, review attribution, or backup/restore identity
  semantics. Tier 1 (67 tests across those three files): zero failures.
  Tier 2 (376 tests across 26 files -- every directly auth/security-adjacent
  file plus a deliberately broad, diverse cross-subsystem sample of the
  ~108 pre-existing files whose fixtures depend on the shared lazy
  bootstrap-then-sign-in test client succeeding): zero failures. Tier 3
  deliberately not run -- the change is confined to one repository method,
  one endpoint, and one new, zero-existing-importers file; session
  resolution, authorization tiers, and every other endpoint are untouched
  (confirmed by direct diff inspection), and Tier 2's own 376-test result
  is itself broad empirical confirmation of that narrow blast radius, not
  only a scoping argument. `ruff check`: zero new findings on every new/
  touched file; `product_repository.py`'s 57 pre-existing findings
  confirmed unrelated via a direct `git stash push -u`/`pop` bisection
  (identical count and finding set before and after, zero findings in the
  line ranges this milestone actually touched). No schema change (see
  "Schema," above). `docs/local-identity-multi-user-contract.md` gained a
  new "Login rate limiting / abuse resistance" section plus a "Known
  bounded gaps" entry documenting the disclosed reverse-proxy-source-
  collapse and success-clears-shared-source trade-offs. This closure does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, Lane G monitoring diagnostics, Lane C work, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- authorization returns to the bold
  statement in §3, below, unchanged by this closure.
- **Prior accepted milestone:** Historical Species-Status ("New" vs.
  "Seen Before") Correctness v1 -- see
  [historical-species-status-new-seen-before-correctness-v1-report.md](historical-species-status-new-seen-before-correctness-v1-report.md)
  for the complete record. Classification **A**. A release-correctness
  milestone closing `tests/test_place_biodiversity_summary_repository.py::
  test_api_route_returns_the_summary` and `::test_human_correction_
  updates_place_biodiversity_intelligence_correctly` -- both independently
  reproduced RED against the real, unmodified pre-fix code, matching the
  identical `'seen_before' == 'new'`/empty-`new_taxa` symptom this file's
  own §14 had already independently re-confirmed as pre-existing across at
  least nine consecutive prior full-Core checkpoints, never before given
  its own dedicated root-cause investigation. Root cause: a **test-fixture
  defect, not a product-code defect** -- the test file hardcoded `NOW` to a
  fixed past instant (2026-08-24) used both as fixture data and, in two
  assertions, exercised through the real HTTP routes for `place_
  biodiversity_summary`/`wildlife_journal_history`, both of which are
  deliberately, doctrine-documented "live view" endpoints (confirmed
  independently in three governing docs, including their own contract)
  with no way to inject a test clock -- always anchoring "today" to the
  real wall clock. Once real time moved six days past 2026-08-24, those two
  HTTP-only assertions correctly, per the live-view contract, started
  reading `"seen_before"` instead of `"new"`. The shared canonical
  computation (`compute_species_historical_statuses`/`ProductRepository.
  _historical_place_baseline_and_species_statuses`) was never defective --
  confirmed both by every `now=`-pinned assertion in the same test already
  passing, and against the endpoints' own governing contract docs
  (`docs/biodiversity-place-intelligence-v1-contract.md`, `docs/canonical-
  new-regular-species-contract.md`). Fix: one test file, zero production
  code -- `NOW` now tracks the real wall clock at collection time (pinned
  to noon UTC to avoid local-midnight edge cases) instead of a fixed date,
  plus two new tests closing this endpoint pair's own "subsequent
  occurrence reads seen_before" and "correction to a previously-seen
  species reads seen_before" coverage gaps (both semantic cases already
  proven elsewhere in the shared computation's own test suite, just not
  yet through this specific endpoint pair). Self-inclusion, future-Visit
  non-retroactivity, Reviewed-truth precedence, stale-inference exclusion,
  archived-Stream/Place isolation, and unresolved-label exclusion were each
  independently re-verified (structurally and/or by an existing or new
  passing test) during root-causing, per the governing brief's own
  adversarial-review requirement; one adjacent, unreproduced, out-of-scope
  observation about `place_story`'s own (separate, untouched) consumption
  of the same unbounded all-time aggregate was disclosed rather than
  chased. Tier 1 (23 tests, the implicated file) and Tier 2 (498 tests
  across every consumer of the shared historical-status path -- canonical
  new/regular consistency, Bird Log journal, place activity report, change
  summary, place story/features, regularity/seasonal/temporal patterns,
  dashboard Today, environmental context, ecological interoperability), run
  together: zero failures. Tier 3 (one full Core run, run bare with no
  `slow`-marker deselection): **5277 passed, 0 failed**, 3 skipped, 11
  xfailed -- the first zero-failure full Core checkpoint in at least nine
  consecutive prior attempts, definitively retiring the `test_place_
  biodiversity_summary_repository.py` pair from this section's own
  recurring "pre-existing" accounting (§14, below). `ruff check` clean on
  the one touched file. This closure does **not** authorize the next
  Representative Field Acceptance / Gate A session, External Pre-Release
  Acceptance, or Final Release Hardening, and does **not** select a next
  development milestone -- authorization returns to the bold statement in
  §3, below, unchanged by this closure. `roadmap.md` was not edited -- this
  milestone is a bounded test-correctness fix, not a roadmap-scope change.
  Lane C's own remaining "New / Regular presentation" item (§6, below) is a
  distinct, still-open UX-presentation gap, not touched or closed by this
  purely computational-truth/test-correctness fix; no evidence surfaced
  that Lane C itself needs a separate reconciliation pass beyond what §6
  already records.
- **Prior accepted milestone:** Release Licensing, Distribution &
  Third-Party Legal Closure v1 -- see
  [release-licensing-distribution-third-party-legal-closure-v1-report.md](release-licensing-distribution-third-party-legal-closure-v1-report.md)
  for the complete record. Classification **B**. A pre-release-decision/
  release-blocking governance milestone (Lane P plus the still-open
  BirdNET commercial-adjacent posture in §2, below) -- confirmed via the
  hard sequencing guard as the highest-priority independent milestone
  available while Gate A's own daylight rerun (Lane R) stays externally
  blocked. Resolved, with durable machine enforcement rather than prose
  alone, both engineering-resolvable items Lane P had left deliberately
  open: **FFmpeg** was traced to every real invocation site
  (`mockingbird.playback.rtsp_bridge`/`local_camera_bridge`/
  `windows_camera_bridge`, all `shutil.which("ffmpeg")`-based) and every
  packaging/build script (zero references anywhere) -- MockingBird never
  bundles, downloads, or vendors an ffmpeg binary in any official package;
  it is a pure external system dependency, already honestly documented in
  `docs/using-mockingbird.md`. A new build-time guard,
  `verify_no_bundled_ffmpeg_binary`, mirrors the pre-existing
  `verify_no_nc_licensed_acoustic_model_redistribution`'s role for BirdNET
  so this posture can never silently reverse; 8 new tests, one of them a
  real integration proof through the unmodified `assemble_windows_bundle`
  call path, not only the guard function in isolation. **Third-party
  notices**: a new `THIRD_PARTY_NOTICES.md` (correct MIT license text and
  copyright provenance for both production-redistributed models -- MDv5a,
  copyright Microsoft Corporation per MegaDetector's own repository;
  BioCLIP-2, per its official model card -- a bounded direct-dependency
  license table verified against each package's own installed metadata
  rather than assumed, and an explicit "deliberately not bundled" account
  of ffmpeg and BirdNET/birdnetlib) now ships inside every official
  Windows bundle via a new `package_third_party_notices` step, which fails
  the build outright if its own source file is ever missing -- previously,
  the redistributed MDv5a/BioCLIP-2 model files carried zero accompanying
  license text at all, unlike every ordinary pip dependency, whose own
  license already travels automatically inside its `dist-info/`. Found and
  fixed one real, previously-undisclosed documentation gap: `docs/using-
  mockingbird.md`, the canonical user-facing guide, never mentioned the
  already-shipped, already-accepted BirdNET/acoustic feature at all --
  added a short, honest "Bird-sound identification (optional)" section
  (optional, separately obtained, differently licensed, never framed as a
  defect). Added a factual "License" section to `README.md` (no
  `LICENSE` file exists; none implied; a pointer to `THIRD_PARTY_NOTICES.md`).
  The MockingBird source-code license itself was deliberately **not**
  self-selected -- the roadmap's own evidence (`docs/roadmap.md` Gate F;
  this file's own prior Lane P text) already states this requires an
  explicit owner decision, not a bounded engineering milestone's authority
  -- the report instead delivers a complete decision packet (MIT
  recommended; Apache-2.0 and a copyleft option named and rejected with
  reasons; every current dependency's license confirmed compatible with
  either permissive option; one exact one-sentence question for the
  owner). Also named, honestly, as neither resolved nor newly blocking:
  the NVIDIA CUDA/cuDNN redistributable packages bundled with GPU builds
  use the same well-established EULA-based pattern official PyTorch/
  TensorFlow GPU wheels already use, but this milestone did not
  independently re-fetch NVIDIA's current EULA text against exactly what
  these pinned packages ship (an engineering interpretation, not a
  repository fact, disclosed as such rather than asserted with false
  certainty); and BirdNET's genuinely ambiguous commercial-adjacent
  private-use question (§2, below) remains exactly as unresolved as
  before, now simply more visibly disclosed to an actual product user
  rather than only an internal contract doc. `tests/test_local_product_
  packaging.py`: 74 passed, 0 failed (4 pre-existing `slow`-marked GPU/
  BioCLIP-dependency-closure tests correctly not re-run -- unrelated to
  this change, unmodified). `ruff check`: clean (zero findings, not merely
  zero new findings) on both changed Python files. No schema change; no
  product/perception/API/frontend code touched -- confined to
  `scripts/build_local_product.py`, its own dedicated test file, one new
  root notices file, and two documentation files. Lane P is now
  reconciled (§6, below) to **one** remaining deliberately-open item
  (down from two) -- the owner's source-code-license decision -- which
  remains a real release blocker for the public launch itself, honestly
  not closed by this milestone. This closure does **not** authorize the
  next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Platform / Runtime Portability & Support
  Truth Closure v1 -- see
  [platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md)
  for the complete record. Classification **A**. A bounded, release-critical
  evidence/documentation closure (Lane O) establishing MockingBird's
  truthful release support matrix across Host operating systems and
  inference runtimes -- not a portability expansion campaign; no new
  platform support was added. Reused rather than re-verified the extensive
  already-accepted native-Windows evidence (Native-Windows Packaged
  Local-Only Acceptance & Privacy Closure v1, Release Engineering
  Foundation v1) to confirm Windows 10/11 x64 as **Validated**: the only
  Host with a packaged, dependency-bundled, no-Python-required end-user
  distributable, with real CUDA execution-provider selection, real
  BioCLIP-2 inference, and a real 18-schema-version organic migration all
  proven at the production code path. Established, for the first time as
  one explicit, coherent, tested story, that MockingBird's accepted
  detector provider (`onnx-cuda`, backing the production `frame-driven-
  onnx-cuda` path) structurally forbids CPU execution by deliberate,
  regression-tested design (`session.disable_cpu_ep_fallback`, a
  CUDA-only provider list, `onnx_cuda_unavailable`/`onnx_cuda_no_fallback`
  raised rather than silently degrading) -- live wildlife detection
  requires a working NVIDIA CUDA GPU with zero fallback -- while both
  optional assistance models (BioCLIP-2 species suggestions, BirdNET
  acoustic identification) are CPU-only by the identical deliberate
  design, already validated, and never block Visit creation when
  unavailable. Classified Linux **structurally supported** at the
  source/dev level (continuously CI-validated on real, non-WSL
  `ubuntu-latest` for the full Core suite, frontend build, and the
  Windows-packaging pipeline's own structural smoke test; a genuine,
  first-class Linux-only feature already exists, the V4L2 local-USB-camera
  bridge) but explicitly **not** promoted to "validated release Host" --
  no packaged end-user Linux distribution exists and no dedicated native-
  Linux hardware acceptance has ever been performed, correcting a prior
  report's own looser use of "Validated" for the identical underlying
  fact. Classified macOS **unverified** overall, with one path
  (microphone capture) already **unsupported** and honestly disclosed
  (fixed in a prior accepted milestone, confirmed still in effect), and
  Apple Silicon acceleration **deferred**, extending rather than
  re-deriving `docs/species-classification-reevaluation-promotion-v2-report.md`'s
  own already-correct "no hardware, not assumed to work" precedent. AMD
  GPU acceleration confirmed **unsupported** -- zero ROCm/DirectML code
  anywhere in the stack. The Camera Node's reference-hardware-vs-hardware-
  agnostic-protocol distinction was verified against real provider code,
  not merely asserted: Raspberry Pi 4/Raspberry Pi OS is the real,
  repeatedly-validated reference device, while a genuine, independent
  `V4L2CameraProvider` (generic Linux/USB via OpenCV) sits behind the same
  `CameraNodeProvider` protocol alongside the Pi-specific backend, each
  degrading gracefully if its own runtime is absent -- no non-Pi hardware
  has ever been release-tested, and none was added this milestone. Found
  two real, reproduced, narrow capability-overclaim defects in `python -m
  mockingbird doctor` (its `SPECIES_IDENTIFICATION` and `GPU_CUDA` checks'
  own PASS branches each silently omitted an honest scope caveat the
  underlying probe already had available, understating how much a PASS
  there actually proves) and fixed both with the minimal truthful
  correction rather than a heavier, costlier re-architecture of either
  check -- each independently reproduced RED via `git stash` against the
  real pre-fix code and confirmed GREEN after, with a new dedicated
  regression test. Two further gaps (the Camera Node's
  `pairing_state_path` retaining a `Path.home()` fallback masked only by
  installer convention; `GET /api/observation-engine/status`'s name
  mismatching the legacy provider it actually wires to, confirmed to have
  zero frontend consumption) were found and precisely disclosed,
  deliberately not fixed, since neither is reproduced against any real or
  currently-shipping path. Published the canonical, plain-language,
  user-facing support matrix in a new "Platform & hardware support"
  section of `docs/using-mockingbird.md`, cross-checked line-by-line
  against the implementation evidence above. `tests/test_doctor.py` (107
  passed) and the directly adjacent `tests/test_doctor_cli.py` (8 passed)
  confirmed via direct grep to be the complete blast radius of the two
  changed functions; `ruff check` clean; full Core correctly not run,
  per the governing brief's own "primarily evidence/documentation"
  validation guidance for a Tier-1/focused change. No schema change. Lane
  O is now reconciled to **closed** (§6, below), resolving its own
  "RELEASE DECISION REQUIRED" status by making support truth explicit
  rather than by claiming any unsupported hardware is supported. This
  closure does **not** authorize the next Representative Field Acceptance
  / Gate A session, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone -- see
  §3, below.
- **Prior accepted milestone:** Sustained-Activity Visit Admission
  Starvation & Stop-Finalization Correctness v1 -- see
  [sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
  for the complete record. Classification **A**. Fixes the real P0
  Representative Daylight Gate A Field Acceptance v4 found and disclosed
  (see the "Prior accepted milestone" entry immediately below): ~112 real
  minutes of sustained, near-continuous multi-bird feeder activity
  producing zero admitted Visits for the entire live session, and a real
  Observation stop that did not visibly rescue anything either. Both
  questions are independently root-caused, deterministically reproduced
  RED against the real, unmodified pre-fix code at the real production
  call site, and fixed: (1) nothing previously bounded how long a whole
  connected *ambiguous component* could keep deferring while its own
  currently-active tail kept being refreshed by sustained real activity,
  even though each individual episode was already correctly bounded --
  fixed with a bounded decision horizon that reuses the existing,
  already-calibrated 20-minute episode-span bound verbatim (never a new
  magic number, never the 45-second gap value itself, per the governing
  brief's own explicit instruction not to treat that value as the bug);
  (2) `_EngineSession.stop()`'s own external kill-switch revert ran
  unconditionally the instant its bounded thread-join returned, racing
  the background thread's own correctly-ordered teardown and silently
  discarding an already-force-decided candidate as `blocked_shadow_mode`
  -- fixed by making the join's own actual outcome (finished vs.
  genuinely still running) authoritative, with an honest
  `stop_finalization_pending` status signal for the rare case a caller's
  own bounded patience is exceeded. Investigating the evidence-cache
  bound's own possible contribution (per this milestone's own governing
  brief, not generic cache tuning) found and fixed two further real,
  narrow, pre-existing defects that would otherwise have kept producing
  the identical "zero Visits" symptom one gate later
  (`blocked_missing_evidence`) even after the primary fix: an
  evidence-candidate truncation order that always kept the *earliest*
  (most likely already-evicted) candidates over byte-available later
  ones, and a merged proposal's evidence silently scoped to only its
  *first* constituent generation. Neither the evidence-cache bound's own
  size nor the 45-second gap value were changed by either fix. A
  105-simulated-minute, two-simultaneous-subject stress replay (brief's
  own §18/§10 field-derived stress replay) confirms bounded, non-starved,
  non-duplicated, non-cross-subject-contaminated admission end-to-end,
  with the first admission landing within 25 simulated minutes -- a
  live-session fix, not merely a session-end rescue. 22 new tests, each
  independently confirmed RED against the pre-fix code and GREEN after.
  Tier 2 (the brief's own named subsystem list, 22 files): 505 passed, 0
  failed. Tier 3 (full Core): 5238 passed, 3 failed -- all 3
  independently confirmed unrelated, not merely assumed: the two
  `test_place_biodiversity_summary_repository.py` failures reproduce
  byte-identically on a direct `git stash` pre-milestone-baseline
  bisection; the one `test_transport_worker.py` failure is a genuine,
  pre-existing, timing-sensitive flake, proven directly (three
  consecutive full-file runs of the identical current code produced
  three different outcomes; zero import relationship to any file this
  milestone changed; a direct baseline bisection also passed cleanly) --
  3 skipped, 23 deselected, 11 xfailed, zero regressions attributable to
  this milestone. `ruff check`: zero new findings (clean-baseline
  bisection). No schema change. This closure does **not** itself close
  Lane R/Gate A (no live field session ran, per this milestone's own
  explicit non-goal), and does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Representative Daylight Gate A Field
  Acceptance v4 -- see
  [representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
  for the complete record. Classification **A**. A real, live ~112-minute
  Observation session against the real reference Camera Node, deployed to
  a genuinely fresh, disposable instance (never the operator's long-lived
  `MockingBirdDev` identity) -- the first real live daylight session run
  under the new Field Acceptance Operator credential mechanism, closing
  the loop that milestone's own report left open. Two real infrastructure
  conflicts were found and resolved live, both with the user's explicit,
  specific approval rather than assumed: the reference Camera Node's
  pairing is single-slot/disk-persisted, so reaching it from a genuinely
  fresh instance required resetting it via the already-documented,
  supported recovery flow (`docs/camera-node-install-guide.md`'s "An
  already-paired Node"), leaving the operator's own `MockingBirdDev`
  instance needing a one-time re-pair before its own next use; and the
  packaged launcher's fixed `127.0.0.1:8000` binding required stopping
  the operator's own instance (confirmed idle first: not monitoring,
  human idle 1+ day; fully reversible). The independent acceptance
  recorder ran the whole session (99.78% coverage); a first-pass blind
  15-second contact-sheet review wrongly concluded zero animal activity,
  self-caught and corrected by cross-referencing the merged (evicted-
  entry-recovered) counterfactual ledger's longest-duration confirmed
  tracks against full-resolution frames at those exact offsets -- real,
  repeated, multi-bird feeder activity (593 confirmed MDv5 animal-class
  tracks, 96.6% at one feeder location, near-continuous for effectively
  the entire session) plus a separate ground-mammal sighting, directly
  visually confirmed, not inferred. Despite this genuine, sustained
  activity, `candidates_created` stayed at exactly 0 for the whole
  session -- a real, previously-undocumented P0 admission-arbitration gap
  was found and precisely root-caused by direct code reading
  (`visit_episode_assembler.py`/`candidate_visit_authority.py`):
  `continuation_pending`/`blocked_ambiguous_boundary` resolution depends
  on a 45-second gap in that specific chain's own activity that
  near-continuous multi-subject activity structurally never produces
  while a session stays live, with session-end finalize as the only
  design-intended escape -- whose real effectiveness is itself now a
  disclosed open question, since this session's own real stop did not
  visibly admit anything either. Zero product code changed: per the
  governing brief's own explicit bar, a trustworthy fix needs
  component-aware forced-decision semantics (not a naive per-proposal
  timeout, which risks reopening the already-fixed transitive-ambiguous-
  component premature-split defect), a threshold calibrated against real
  field evidence, and likely a further look at the already-disclosed
  128-entry evidence-cache bound -- comparable in scope to a full
  milestone, not a bounded change. A second, real, live-checked product
  finding shares the identical root cause: `GET /api/dashboard/summary`
  showed zero signal of any kind after ~112 minutes of real activity --
  the exact "must never look like MockingBird saw nothing" failure mode
  `roadmap.md` already names as unacceptable. Persistence-contention log
  grep: zero occurrences (single Stream, log otherwise completely clean).
  Species assistance: N/A, moot downstream of the admission failure (zero
  Visits ever existed to run BioCLIP against). No release budgets
  proposed -- three real cohorts now span 0% to 68.2% end-to-end Visit
  recall; per the report's own reasoning, that range does not converge
  into a budget until the newly-found defect is fixed and re-measured.
  Does **not** authorize External Pre-Release Acceptance or Final Release
  Hardening, and does **not** select a next development milestone -- see
  §3, below.
- **Prior accepted milestone:** Native-Windows Packaged Local-Only
  Acceptance & Privacy Closure v1 -- see
  [native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md)
  for the complete record. Classification **A**. Closes both material gaps
  Local Only / Privacy Closure v1's own "Remaining risks" left open:
  actual native-Windows packaged runtime, and assets-present MDv5a/
  BioCLIP-2 operation under internet denial. Built and deployed the
  accepted native-Windows packaging path (`scripts/deploy_windows_dev.py`
  over `scripts/build_local_product.py`'s real release logic) to a fresh,
  disposable `--dev-root` -- never the operator's long-lived
  `MockingBirdDev` identity -- with **no skip flags**, so the release
  genuinely carries the full GPU/CUDA and BioCLIP dependency closures plus
  both packaged model bundles. Internet denial used a real, disposable,
  user-mode HTTP(S) egress-filtering proxy (no Administrator token is
  available in this interop session, confirmed directly, so a kernel
  firewall rule was not available -- the same class of environment-
  appropriate substitution the prior milestone made in the other
  direction for WSL): every optional-provider `CONNECT`/request the
  MockingBird process attempted was classified by real destination IP and
  either relayed (loopback/LAN) or refused before any real connection,
  independently corroborated by a live, zero-external-connections
  `Get-NetTCPConnection` snapshot and by the same mechanism separately
  catching a real headless Edge browser's own unrelated background
  telemetry. LAN preservation was proven live, not just configured: a
  proxied request to the project's real reference Camera Node returned a
  real `200` health payload. MDv5a and BioCLIP-2 were both proven
  initializing and running real local inference at the exact production
  code path (not a status flag) -- SHA-256 fingerprints matching this
  project's own accepted provenance record, real CUDA execution-provider
  selection for MDv5a, a real forward pass for BioCLIP-2 -- both before
  and after network denial, with the proxy log showing **zero** entries
  from either run (no download, no HF/network fallback attempted). Caught
  and worked around, before accepting it as evidence, a real environment-
  contamination finding: persistent User-level environment variables left
  over from earlier, unrelated dev sessions on this same Windows machine
  were silently redirecting BioCLIP resolution to a `\\wsl.localhost\...`
  path rather than the packaged bundle -- cleared per-process (never
  touching the persistent value) for every launch this milestone made,
  disclosed plainly as a methodology fact about this specific reused dev
  machine, not a product defect. A real browser render (headless Edge,
  offline, routed through the same proxy) showed the packaged frontend
  rendering correctly -- proper typography, layout, and product copy, zero
  external dependency. All 16 named core workflows were exercised live
  against real seeded product-shaped data, including a real local backup
  (created, verified, confirmed on disk) and a real review correction
  (submitted, immediately reflected). Both live optional-provider drills
  (weather, iNaturalist) degraded gracefully under real forced
  unreachability, with no retry storm and `ready: true` throughout. The
  camera-credential-at-rest question Local Only / Privacy Closure v1 left
  open was resolved by direct code/doc investigation to a documented
  non-defect: credentials are stored plaintext, exactly as the existing
  `docs/local-identity-multi-user-contract.md` already discloses, and no
  contract anywhere promises otherwise. Zero reproduced Local Only/privacy
  defects were found, so zero production code changed;
  `tests/test_local_only_privacy.py` was re-run clean (8/8) as the
  validation evidence, per the governing brief's own explicit guidance not
  to run a full Core gate for a zero-code-change acceptance milestone.
  Worktree safety reconfirmed throughout (the seven preserved untracked
  detector files byte-identical at start and end). Lane N is now
  genuinely, fully reconciled to **closed** (§6, below) -- both proofs the
  prior closure's own classification B explicitly named as missing are
  now real. This closure does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Local Only / Privacy Closure v1 -- see
  [local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)
  for the complete record. Classification **B**. A bounded, release
  -critical privacy/product-correctness milestone (Lane N) proving
  MockingBird's core product works Local Only, with no cloud account,
  contribution pathway, remote service, analytics dependency, external
  telemetry requirement, or provider credential required for ordinary
  use. Two independent bounded static-inventory passes (backend:
  `src/mockingbird/`, `src/mockingbird_node/`, all of `scripts/`,
  `pyproject.toml`/`uv.lock`; frontend: `web/src/` plus the real
  *compiled* `web/dist/assets/*.js` output) found: local production
  inference (MDv5a ONNX, BioCLIP-2, BirdNET) loads exclusively from local
  paths, with `HF_HUB_OFFLINE`/`TRANSFORMERS_OFFLINE`/
  `HF_DATASETS_OFFLINE` defense-in-depth already present on the BioCLIP
  path; zero telemetry/analytics/crash-reporting dependency anywhere in
  the packaged dependency closure; zero mandatory external frontend
  runtime asset (only 3 harmless external-origin strings exist in the
  entire shipped JS bundle, none a fetch target); weather (Open-Meteo,
  off by default) and iNaturalist taxonomy lookup (gated by feature use,
  not a settings flag -- named explicitly since a search for only a
  persistent "enabled" flag would undercount it) are the only two live
  explicit-optional-provider call sites reachable from ordinary runtime,
  both already well-hardened (bounded timeouts, typed failure exceptions
  always caught, never poison a cache, never raise); no Derived Data
  Contribution/media-upload pathway is implemented in the codebase at
  all yet (every real "contribution" code hit is an unrelated internal
  scene-confusor-region bookkeeping concept), so contribution privacy is
  presently a non-question rather than a verified opt-in flow, stated
  plainly rather than overclaimed. A real runtime acceptance then ran a
  fresh disposable instance entirely inside a genuine, OS-level,
  unprivileged network namespace (`unshare --net --map-root-user`, real
  loopback confirmed working via an actual "connection refused" on an
  unbound port, every other interface absent -- not a firewall rule that
  could have a gap) -- proving 22 core authenticated API routes plus the
  frontend document and a hashed asset all return `200` with zero
  outbound connection possible; Observation start/stop against the
  seeded demo Stream degrades honestly rather than crashing; a real
  local backup creation succeeds and lands on local disk; and, with
  weather and iNaturalist taxonomy lookup both deliberately enabled and
  forced unreachable, every affected response still degrades gracefully
  (bounded latency across 5 rapid repeats, no retry-storm growth,
  `/api/product/health` stays `ready: true` throughout). A fresh, live,
  separate LAN-reachability check (outside the denied namespace,
  immediately afterward) confirmed the same sandbox that just proved
  zero internet dependency can still reach the project's real reference
  Camera Node over LAN -- direct evidence for the offline-vs-LAN-local
  distinction, not only an assertion of it. Zero reproduced Local Only/
  privacy defects were found, so zero production code changed; 8 new
  tests (`tests/test_local_only_privacy.py`) convert the live proof into
  a fast, hermetic, dependency-injected regression (never a real
  socket), self-verified via call-count assertions on the injected fake
  requesters that caught and fixed one test targeting the wrong endpoint
  before it was counted as passing evidence. Tier 2 (18 files across
  auth/environment-provider/ecological-interoperability/export/dashboard/
  model-adapter areas): 374 passed, 1 skipped, 0 failed. Tier 3 (full
  Core) not run -- this milestone changed zero production code, matching
  this codebase's own established precedent for non-cross-cutting
  changes. `ruff check`: clean on the one new file. Classification **B**,
  not A: every functional acceptance-bar dimension is satisfied with
  real, live evidence, but this session's own runtime acceptance ran the
  Linux/WSL dev checkout rather than the packaged native-Windows
  artifact end users receive, and exercised the model-assets-absent path
  rather than assets-present -- both named explicitly as the one
  material runtime-acceptance dimension left unverified fresh by this
  session, per the governing brief's own B criterion, not because any
  defect was found or is suspected. Lane N is now reconciled to
  **closed** (§6, below) -- see §3, below, for the full accounting. Does
  **not** authorize the next Representative Field Acceptance / Gate A
  session, External Pre-Release Acceptance, or Final Release Hardening,
  and does **not** select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Retention Correctness & Bounded Cleanup
  Closure v1 -- see
  [retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md)
  for the complete record. Classification **A**. A small, bounded,
  release-critical follow-up (Lane M) closing exactly the three
  reproduced retention defects Storage / Retention / Disk-Pressure &
  Recovery Closure v1's own "Remaining risks" disclosed and deliberately
  left unfixed under its own bounded time budget: (1) imported/folder-
  imported media (`create_media_import`/`import_folder_media`, via
  `_create_media_product_records`, which never materializes a
  `VisitEvidenceLink`) was protected forever unconditionally by
  `_storage_retention_evaluation`'s `legacy_representative_evidence`
  bucket, directly contradicting `docs/appliance-storage-privacy-
  recovery-v1-contract.md:159-163`'s own "same active/superseded/
  reviewed rules as any other Visit-linked evidence -- no separate
  contract" claim -- fixed to become eligible once every referencing
  Visit is superseded, on the identical `superseded_evidence_age_days`
  clock `superseded_only_evidence` already uses for linked evidence,
  while remaining protected forever while any referencing Visit stays
  active regardless of review state, exactly matching a linked primary
  frame's own existing protection (reviewed, corrected, unreviewed, and
  folder-imported Visits all explicitly tested; the underlying import
  code creates exactly one asset per import, so the brief's own "cannot
  distinguish original from derived evidence" stop-condition did not
  apply -- there is nothing to distinguish); (2) a `"staging"`
  (interrupted) cleanup batch could only ever be restored, never purged,
  because `purge_storage_cleanup_batch`'s own purge query only ever
  considered items already durably `"quarantined"`, a state an
  interrupted item can structurally never reach on its own -- fixed with
  a new `_resolve_staging_batch_for_purge`, invoked only for a
  `"staging"` batch before the existing, unmodified purge logic runs,
  reusing (never duplicating) the exact reconciliation
  `execute_storage_cleanup` already performs at the end of a clean run
  (refactored into two shared helpers so there is exactly one
  implementation of this transition, not two); a batch that never
  actually moved anything resolves to the real `"failed"` outcome rather
  than a misleading `"purged"`, and one still genuinely ambiguous even
  after a real reconciliation attempt correctly stays rejected rather
  than reporting a false terminal state; (3) `storage_cleanup_history`'s
  own `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` constant never actually bounded
  the underlying `storage_cleanup_batches` table -- only a read-page size
  and an unrelated automatic-purge chunk size -- fixed with a new
  `_prune_storage_cleanup_history`, called at the tail of every write
  path that can newly produce an eligible row (execute/restore/purge),
  pruning the oldest rows beyond the newest 30 among batches in a
  terminal, disk-safe state (purged/restored/failed) only -- a batch
  still holding live `.recovery/<batch_id>/` files is never pruned
  regardless of age, proven directly by a dedicated test seeding a
  400-day-old still-quarantined batch alongside 35 newer purged ones and
  confirming the old-but-live one survives. Reviewed truth verified
  unaffected across all five required cases; DB/media coherence verified
  in both directions (no new dangling reference beyond the same already-
  accepted "row kept forever as audit trail, file gone, every read path
  already handles a clean 404" contract every other purge category
  already relies on; no new orphan file possible, since none of the
  three fixes adds a file-write path -- the pre-existing, already-
  disclosed structural no-DB-owner orphan-media gap is unaffected and was
  not reopened, per the governing brief). No schema change (see
  "Schema," above). 17 new tests (`tests/test_storage_retention.py`,
  39/39 passing), each independently confirmed RED against the pre-fix
  code -- via `git stash` of the production file while it was still
  uncommitted, and later via a direct pre-fix-blob swap once committed --
  and GREEN after. Tier 2 (23 files across storage/retention/imports/
  backup/doctor/visit-curation/review-queue): 329 passed, 0 failed. Tier
  3 (full Core): 5213 passed, 3 failed, 3 skipped, 23 deselected, 11
  xfailed -- all 3 failures independently confirmed unrelated, not merely
  assumed from precedent: a Camera Node picamera2-restoration test
  passing cleanly both in isolation and as its own full file (a
  full-suite-only flake); the identical, independently-reconfirmed
  pre-existing `test_place_biodiversity_summary_repository.py` pair
  (a bird-species historical-status classification defect with zero
  code-path relationship to this milestone's own changes), confirmed
  unrelated by directly swapping the pre-fix (`8572308`) blob back in and
  reproducing the identical failure, then restoring a byte-exact match to
  `HEAD` -- zero regressions attributable to this milestone (Tier 3's own
  long-running process had already imported the module a few minutes
  before a small, purely cosmetic, zero-behavior dead-parameter cleanup
  landed in the implementation commit; that specific increment was
  independently re-verified via a full Tier 1 + partial Tier 2 re-run
  against the exact final code instead of a second full 39-minute Tier 3
  pass for a provably zero-risk difference -- see the milestone report's
  own "Precise sequencing note" for the complete accounting). `ruff
  check`: zero new findings, confirmed by direct clean-baseline
  bisection against this file's own 57 pre-existing, unrelated findings.
  Lane M is now reconciled to **closed** (§6, below) -- see §3, below,
  for the full accounting. Does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Storage / Retention / Disk-Pressure &
  Recovery Closure v1 -- see
  [storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
  for the complete record. Classification **B**. A bounded, release-critical
  storage/reliability milestone (Lane M) that also determined the cause and
  product significance of the Windows Host free-space decline this file's
  own 2026-08-28 Lane R entry (below) first surfaced (`43.07GB -> 18.8GB`,
  2026-08-20 -> 2026-08-28) but left open. Real, directly-measured disk
  accounting (native `powershell.exe` interop against the real Windows dev
  host, not estimated) found the single largest consumer anywhere in the
  investigation: `%LOCALAPPDATA%\MockingBirdDev\runtime\` (the dev-only
  `deploy_windows_dev.py` tool's runtime/model/BioCLIP-model cache) held
  38.5GB across 21 never-pruned entries, including 6.25GB of definite
  orphaned `.staging-*`/`.stale-*` leftovers from interrupted cache
  populations -- a real, previously-disclosed-and-deliberately-deferred gap
  (`docs/windows-dev-deployment-design.md`'s own "Left for follow-up"
  section had judged this "unlikely to matter in practice," a judgment
  real measurement falsifies). Combined with the field-acceptance
  recorder's own real output directory (11.5GB, genuine evidentiary
  artifacts from the project's own real 2026-08-19/08-20/08-21 daylight/
  dusk sessions, not waste), directly-dated entries created inside the
  exact 2026-08-20 -> 2026-08-28 decline window account for roughly 72%
  of the observed 24.27GB decline -- **disposition B: MockingBird
  development/test-artifact accumulation, root-caused, product
  unaffected**. Neither growth path exists in, or is reachable by, a real
  end-user installation: `%LOCALAPPDATA%\MockingBird` (the real production
  runtime home) measures 1.1MB on this same machine, and the real product's
  own upgrade mechanism (Release Engineering Foundation v1) is a
  structurally different, single-version, database-level-pre-migration-
  backup-only design with no multi-version content-addressed cache at all.
  Fixed: a new `gc_cache_command`/`--gc-cache` flag in
  `scripts/deploy_windows_dev.py` implementing exactly the bounded shape
  the design doc's own deferred-follow-up section had already named
  (referenced-hash walk over every currently-on-disk retained release, plus
  an unconditional orphaned-`.staging-*`/`.stale-*` sweep) -- 11 new tests,
  `tests/test_deploy_windows_dev.py`: 123 passed; `ruff check` clean on
  both changed files. Applied live against the real Windows dev host,
  completing cleanly (exit code 0): `%LOCALAPPDATA%\MockingBirdDev` fell
  from 55.7GB to 26.1GB and real `C:` free space rose from ~20-23GB to
  ~51-52GB (96% -> 90% full) in one real, verified pass -- 17 stale release
  directories and 16 unreferenced/orphaned cache entries actually removed
  (`releases/` correctly settling at exactly the 5 protected/kept:
  `a56081a`, `248853a`, `f609c89`, `db8588c`, `80e1bb3`), independently
  cross-confirmed by the matching rise in real `C:` free space (see the
  milestone report for the complete numbers). Separately, deep archaeology
  of the already-accepted storage-
  retention/backup/Doctor product contract (`docs/appliance-storage-
  privacy-recovery-v1-contract.md`, accepted 2026-08-23) -- re-verified,
  not rebuilt, via 349 real, independently re-run passing tests across the
  whole storage/retention/backup/doctor/deploy-tooling family -- found and
  precisely disclosed (not fixed, each safe-direction/non-release-blocking,
  none warranting a rushed change to the highest-stakes retention-
  eligibility code under this milestone's own time bound) one real
  documentation-vs-code mismatch (imported/folder-imported media is
  over-retained forever, contrary to the accepted contract's own explicit
  "same rules as any other Visit-linked evidence" claim -- empirically
  reproduced, zero pre-existing test coverage for this exact path) plus
  three smaller gaps (a `"staging"`-state cleanup batch can only ever be
  restored, never purged; `storage_cleanup_history`'s own
  `MAX_STORAGE_CLEANUP_HISTORY_ITEMS` constant does not actually bound the
  underlying table, only a read-page/chunk size; no orphan-media,
  file-with-no-DB-owner, detection exists anywhere in the product, a
  structural gap distinct from, and confirmed still bounded/low-materiality
  for, the already-accepted Concurrent Candidate Visit Persistence
  Reliability v1 milestone's own disclosed orphan possibility, not
  reopened). No schema change; Tier 3 (full Core) not run, matching this
  codebase's own established precedent for changes confined entirely to
  `scripts/` deployment tooling with zero importers in `src/mockingbird/`
  (Camera Node Upgrade & Compatibility Recovery v1 made the identical call
  for the identical reason). Does **not** authorize the next Representative
  Field Acceptance / Gate A session, External Pre-Release Acceptance, or
  Final Release Hardening, and does **not** select a next development
  milestone -- see §3, below.
- **Prior accepted milestone:** Non-Interactive Field Acceptance
  Authentication & Session Access v1 -- see
  [non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
  for the complete record. Classification **A**. A bounded, release-critical
  security/correctness dependency milestone -- not a product capability --
  closing the recurring field-acceptance authentication blocker three
  consecutive prior attempts hit (2026-08-25, 2026-08-26, 2026-08-28; see
  Lane R, §6, below) without an authentication bypass, without the
  operator's personal credentials, and without weakening production
  security. Adds one new, narrow, parallel, bearer-token-authenticated
  identity -- "Field Acceptance Operator" -- mirroring this codebase's own
  existing Camera Node device-identity-separation precedent rather than
  extending the linear Viewer/Reviewer/Administrator role ladder (the
  required permission shape -- broad Viewer-level reads plus exactly two
  otherwise-Administrator-tier mutations, Observation start/stop, and
  nothing else Administrator-tier -- is not a contiguous prefix of that
  ladder, so no single role-rank placement could express it correctly).
  Checked by the exact same central `install_authorization` gate every
  other request already passes through -- no parallel/insecure auth stack,
  no localhost/header bypass, no anonymous fallback, proven by a dedicated
  negative-test regression suite. Schema `v57 -> v58`: one new additive
  table, `field_acceptance_credentials` (hash-only token storage,
  mandatory bounded expiry -- no permanent-credential path exists in v1 at
  all -- explicit deterministic revocation, auditable creation/revocation/
  use). Provisioning is a bounded new admin CLI
  (`scripts/manage_field_acceptance_credential.py`, Administrator-only,
  never accepts a password as a CLI argument) mirroring the existing
  `repair_review_label_provenance.py` real-HTTP-instance precedent; the
  acceptance tooling itself gained a small stdlib-only client
  (`scripts/field_acceptance_client.py`) reading
  `MOCKINGBIRD_ACCEPTANCE_TOKEN` and failing clearly (never anonymously)
  on every required negative case. Real acceptance proof: provisioned and
  exercised this exact mechanism live against a real running instance of
  this milestone's own implementation commit (native Windows, real SQLite,
  real FastAPI/uvicorn process, `--skip-gpu-runtime --skip-bioclip-runtime`
  since this proof needed the auth/API layer, not detection quality) --
  the identical three endpoints that blocked the three prior field-
  acceptance attempts (`GET /api/streams`, `GET /api/visits`, `POST
  .../observation/start`) all still correctly `401` with no credential,
  then all succeed with the new credential, including a real Observation
  start/stop cycle against the auto-seeded demo Stream, with the
  credential correctly denied (`403`) on unrelated Administrator actions
  and its use distinguishable from a human Administrator's in the audit
  trail; revocation was proven immediate (the identical token fails on its
  very next use). Deployed to an isolated, disposable dev-root -- **not**
  the operator's real `MockingBirdDev` deployment, confirmed untouched
  throughout -- with a disposable bootstrapped Administrator, no live
  operator credentials used anywhere in this milestone's own work,
  matching this file's own standing decision (see the 2026-08-25 Lane R
  entry, below) against asking the operator for real credentials or live
  participation. Environment left in a secure, known, empty state after
  proof (credential revoked, disposable instance and process fully
  removed). Tier 1/2: 20 new tests
  (`tests/test_field_acceptance_authentication.py`) plus 219 across the
  eight pre-existing files this milestone's schema-literal bump touched,
  all passing. Tier 3 (full Core): 5187 passed / 2 failed -- the 2
  failures both the identical, independently-reconfirmed pre-existing
  `test_place_biodiversity_summary_repository.py` pair (a bird-species
  historical-status classification defect with zero code-path relationship
  to this milestone's own changes), confirmed unrelated by a direct
  `git checkout` bisection against this milestone's own true starting HEAD
  (`c03d0b1`), not merely inferred from precedent -- zero regressions
  attributable to this milestone. `ruff check`: zero new findings,
  confirmed by a direct clean-baseline bisection. e2e not run (zero
  `web/src/` changes; the existing suite's cookie-session `storageState`
  bootstrap is untouched and does not intersect this milestone's
  bearer-token mechanism). Concrete residual risk, both disclosed in full
  in the milestone's own report: no login rate-limiting exists anywhere in
  this product (a pre-existing, disclosed gap from Mobile & Remote
  Experience v1, untouched, out of this milestone's scope) -- a
  field-acceptance bearer token is a static secret for its bounded
  lifetime, mitigated by mandatory expiry/hash-only storage/explicit
  revocation but not by any brute-force protection on the token-lookup
  path itself; and the real acceptance proof ran against a disposable
  instance, not the operator's specific long-running real `MockingBirdDev`
  deployment (deliberately, per standing policy), so that specific
  instance still needs its own one-time `create` provisioning step before
  its first non-interactive use -- not a gap in the mechanism, the
  intended minimal human step. This closure does **not** authorize Lane R, the
  next Representative Field Acceptance / Gate A session, External
  Pre-Release Acceptance, or Final Release Hardening, and does **not**
  select a next development milestone -- see §3, below.
- **Prior accepted milestone:** Whole-Product UI / Accessibility /
  Performance Closure v1 -- see
  [whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
  for the complete record. Classification **A**. Closes Lane Q as an
  integrated pass. A bounded, live browser/keyboard investigation across a
  seeded, product-shaped 371-Visit QA instance (own isolated database, own
  bootstrapped disposable Administrator -- no live credentials used) found
  and fixed one P0 and three P1 defects, each with a RED/GREEN-verified
  regression test and a live before/after confirmation, not merely code
  inspection: (1) manually- and folder-imported Visits (the default,
  promoted camera-less acquisition path) were silently excluded from
  Review Queue's default "Animals" tab regardless of subject_label --
  the real, previously-unidentified root cause of one class of confusion
  this project had repeatedly, incorrectly attributed to
  `reviewed-product-loop.spec.ts` being an unrelated flake across at
  least three prior milestones; (2)-(3) two real keyboard focus-management
  defects in Fast Review (activation, and last-item-in-view completion)
  left focus stranded on `document.body`, found via live keyboard-driven
  browser testing, both fixed with the same "focus the new region's own
  heading" pattern the mobile nav drawer already used correctly; (4) the
  scheduler's disclosed bounded acoustic health/status gap (Lane A) closed
  with the smallest capability-aware addition the brief allowed --
  composed entirely from already-existing facts, never a factor in
  `ready`. Investigated and confirmed NOT regressions: two very-tall-
  looking pages (Stream Detail, Analytics) that turned out to still be
  correctly bounded exactly as the 2026-08-18 "v0.1 Product Flow Gap Pass
  v1" fix intended. Root-caused (not fixed, disclosed) `reviewed-product-
  loop.spec.ts`'s real mechanism for the first time: `ReviewQueuePage.
  tsx`'s `const productMode = true;`, a pre-existing (`1772c36`,
  2026-07-28, predating this milestone by a month), un-toggleable
  constant, makes the legacy markup that spec targets permanently
  unreachable -- test-suite staleness, not a live product defect; fixing
  the spec itself needs a real rewrite against the current flow, left as a
  precisely-scoped, not-yet-started follow-up. Zero horizontal overflow
  found across 40 real combinations (4 required widths x 10 pages);
  measured, not assumed, performance at an 89-item backlog sits at or
  below BioCLIP Status / Review Queue Performance v1's own accepted
  87-item precedent, no regression found or introduced. Full e2e (136
  specs, 8 new): 135 passed / 1 failed -- the one failure the precisely-
  diagnosed pre-existing gap above, independently reproduced identically
  on the unmodified 128-spec baseline (127 passed / 1 failed, byte-
  identical single assertion). Full Core run clean (see §14). `ruff
  check`: zero new findings, confirmed by a direct clean-baseline
  bisection given `product_repository.py`'s 42,600+ line scale. Schema
  unchanged (v57 -> v57). Remaining, disclosed, not blocking: Zone-polygon
  *drawing* (not selection) has no keyboard equivalent (optional/advanced
  feature, pre-existing); a materially larger dead-CSS footprint around
  `.bird-log-entry` than previously documented; a narrow raw-exception-
  text edge case on non-`ApiError` failures. This closure does **not**
  authorize Lane R, External Pre-Release Acceptance, or Final Release
  Hardening, and does **not** select a next development milestone.
- **Prior accepted milestone:** One-Release Roadmap & Scheduler
  Reconciliation v1 -- documentation/state-governance only, touching zero
  product/test/schema code. See
  [one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
  for the complete record. Classification **A**. Reconciled this file and
  `roadmap.md` to one coherent release doctrine: MockingBird has one
  public release -- no public "v0.1" product stage, no beta product
  release, no separate before-v1.0 roadmap phase. External Pre-Release
  Acceptance (roadmap.md's Gate G, renamed here from its prior "External
  Beta Acceptance") and internal release-candidate builds remain allowed
  as pre-launch validation/engineering mechanics, never a separate product
  stage; this file's own Lane S ("Actual Final Release Hardening") is
  rewritten onto that same readiness-triggered, not version-number
  -triggered, sequencing (External Pre-Release Acceptance -> Final Release
  Hardening -> the one public launch). Renamed this file's own §7
  ("First-public-v0.1 doctrine" -> "One-release doctrine") and §8
  ("Post-v0.1 / before-v1.0 queue" -> "After-release queue"); replaced
  "v0.1 CRITICAL"/"v0.1 blocker"/"v0.1 scope"/"v0.1 requirement" language
  throughout both files with "release-critical"/"release
  blocker"/"release scope"/"release requirement," matching wording
  `roadmap.md` had already adopted for its own "Release gates"/
  "After-release lanes"/"Release non-blockers" headings at an earlier,
  partial reconciliation (`326207b`); fixed several cross-references that
  earlier rename had left dangling ("v0.1 release gates" -> "Release
  gates," "v0.1 non-blockers" -> "Release non-blockers," "Post-v0.1
  lanes" -> "After-release lanes," and a "(see "v0.1 feature freeze,"
  below)" pointer redirected to the section that actually carries that
  content today). Added a short "Four release-shape categories" index to
  §6, above, mapping the existing lettered lanes onto release-critical/
  pre-release-decision/after-release/later-evidence-driven categories
  without removing, renaming, or promoting any of them. `product-
  doctrine.md` was read in full and left unedited -- it already frames the
  release as the real product launch and creates no beta/v0.1 product
  stage. Every dated historical milestone bullet, proper-noun milestone
  title (for example "v0.1 Product Flow Gap Pass v1," "v0.1 Observational
  Quality Closure v1," "v0.1 Acquisition/Ingest Interoperability Closure
  v1"), and historical decision label (the 2026-08-22 "v0.1 feature
  freeze now active" decision, and the reasoning tied to it) was left
  verbatim, since it records what was actually named and decided at the
  time, not current doctrine. No lane, gate, or roadmap capability was
  added, removed, or promoted; no code, test, or schema changed.
- **Prior accepted milestone:** Camera Node Upgrade & Compatibility
  Recovery v1 -- see
  [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).
  Classification **A**. Closes Lane L's one remaining named gap: a Camera
  Node **upgrade** workflow, distinct from the already-accepted install/
  reboot/reprovision/replacement hardening -- see Lane L, §6, below.
  Investigation found the existing installer already had real update/
  rollback *mechanics* (build_id-keyed idempotency, one retained prior
  version); what was missing was a real upgrade *contract*: artifact
  -checksum verification before any mutation (the artifact builder already
  produced `SHA256SUMS`/per-file hashes but nothing ever checked them),
  staged build-and-verify before the live install is touched at all
  (`venv.staging`, `import mockingbird_node.app` as the activation gate),
  automatic recovery when a newly-activated build fails post-update
  verification, and a bounded Node-local wire-protocol compatibility
  classification (`current`/`compatible_older`/`incompatible`/`unknown`,
  styled after the existing `provider_compatibility` convention) -- the
  Host's own real wire-protocol gate (exact-match only, no graduated tier)
  was investigated and deliberately left unchanged, a pre-existing
  accepted decision. Found and fixed, before any real-hardware attempt, a
  real reproduced defect in the already-accepted artifact builder:
  `NODE_FILES` had silently drifted behind `app.py`'s own imports (Remote /
  Intermittent-WAN Transport Foundation v1 added six transport modules
  without updating the packaged file list) -- every fresh install and
  upgrade produced by the accepted builder was completely broken
  (`ModuleNotFoundError` at startup), confirmed by direct reproduction;
  fixed, plus a new fast static import-closure test closing the whole
  class of drift, not just this instance. A 5-angle adversarial
  self-review before real-hardware acceptance found and fixed 8 further
  correctness issues in this milestone's own new code (most notably: the
  original activation-recovery design, keyed only on whether a staging
  directory still existed, missed a real crash window a manifest-first,
  build-id-reconciliation redesign closes completely; and a plain,
  successful, directly-requested `--rollback` was originally misreported
  as a failed upgrade). Real acceptance against the project's actual
  reference Pi -- which had never been upgraded since 2026-08-18, predating
  three later accepted Camera Node milestones entirely -- found and fixed
  two further real defects live: a universal, upgrade-blocking crash
  (`transport_spool_dir` defaulting through a `Path.home()`-derived path
  that is always broken under the already-accepted `ProtectHome=true`
  hardening, regardless of whether transport was ever configured -- would
  have broken *every* Camera Node upgrading past the transport milestone
  through the accepted installer, not just this device), and two
  automatic-recovery gaps (`systemctl restart` failing outright did not
  trigger automatic rollback; a preceding crash loop's exhausted
  `StartLimitBurst` blocked an unrelated later restart) -- both found live,
  both fixed the same session with dedicated regression tests, not merely
  disclosed. The device was then successfully, fully upgraded end to end
  (node identity, pairing credential hash, and camera availability all
  confirmed byte-identical/unchanged before and after; new boot-identity/
  self-test/watchdog capabilities live on real hardware for the first
  time), with a real idempotent re-run confirmed afterward. One honest
  reservation against an unqualified top classification: `rollback()`
  restores code but not an already-changed systemd unit template, a real
  gap this session's own recovery encountered and worked around manually
  (a temporary drop-in) rather than closed structurally -- disclosed, not
  hidden. Tier 1 (114 tests across `test_install_camera_node.py`/
  `test_camera_node_packaging.py`/`test_camera_node_config_transport.py`/
  `test_camera_node_real_process.py`, all passing), Tier 2 (the full
  `camera_node`/`doctor` test family, 493 passed / 0 failed fast-tier plus
  17 passed / 0 failed slow-tier), `ruff check` clean. Tier 3 not run --
  every changed line sits in `scripts/` deployment tooling or the
  deliberately main-app-isolated `mockingbird_node` package (confirmed by
  direct `grep`: zero importers of either in `src/mockingbird/`); real
  hardware acceptance is stronger evidence for this milestone's actual
  scope than an unrelated 5000+ test Core run. No schema change; no
  product/perception/database/API code touched.
- **Prior accepted milestone:** Representative Multi-Camera Field
  Acceptance & Release-Budget Evidence v1 -- see
  [representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
  Classification **B** -- no live field session ran (session start, 20:26
  EDT 2026-08-26, was after sunset -- the same "darkness produces an
  unusable bird denominator" scenario this project has already hit twice
  before, 2026-08-19/2026-08-20; this milestone's own governing brief
  names exactly this as the case to not manufacture a field result under).
  Executed the brief's own "no representative conditions" path instead:
  re-verified every precondition a live daylight session needs (Camera
  Node network reachability, GPU/detector idle and available, disk
  headroom, the exact acceptance-recorder env-var settings/structured-log
  path, the exact command/API sequence, minimum run duration), and --
  while proving "the current deployed build contains accepted HEAD" --
  found and fixed one real, previously-hidden defect: a fresh, full-
  fidelity Windows dev build of the then-current accepted HEAD
  (`db8588c`) failed outright with a genuine `LocalProductBuildError`
  (site-packages ended up with two different `click` versions, 8.4.2 and
  8.5.0, installed by two independent dependency-install tiers -- the
  identical mechanism, and identical one-line-pin fix shape, as this same
  file's own already-documented `idna` pin). Validated RED->GREEN against
  an existing test that already covered this exact shape but had never
  been run against today's live PyPI state
  (`test_real_windows_bioclip_dependency_closure_installs_offline_with_no_duplicates`);
  full `test_local_product_packaging.py` (66 fast + 4 slow) passing;
  `ruff check` clean; Tier 3 not run (change isolated to Windows packaging
  tooling, zero import relationship to the Core suite). Re-deployed after
  the fix and independently re-verified via direct HTTP (`GET
  /api/product/instance`/`/api/product/health`: `git_commit` exact match,
  schema `57`, `ready: true`) that the deployed artifact carries the fix
  (`click-8.4.2.dist-info` the only `click` entry anywhere in it), then
  stopped it cleanly, leaving `db8588c` a retained, ledger-verified
  release ready for instant relaunch. Also learned, via the
  unauthenticated health endpoint only (no credentials used, matching the
  standing decision below): only one real Stream (the reference Camera
  Node) is currently configured in this dev instance -- a second real,
  already-supported Windows-USB-webcam Source (hardware-validated for the
  prior Acoustic milestone) is not yet wired up, and should be added as a
  genuine second Stream before the next live session, so this project's
  still-open "does the concurrent-persistence fix hold under genuine
  multi-camera load" question can actually be tested with two real
  cameras. No product/perception/admission/Visit/evidence/classification
  code touched; no schema change; Gate A evidence body unchanged (zero new
  field-cohort minutes gathered) -- no release budgets proposed. See Lane
  R, §6, below, for the Gate A/field-acceptance-specific record.
- **Prior accepted milestone:** Concurrent Candidate Visit Persistence
  Reliability v1 -- see
  [concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
  Classification **A** -- a bounded correctness milestone, not a further
  Multi-Camera product pass, closing the real, disclosed occasional
  lost-candidate-Visit concurrent-write reliability gap Multi-Camera Place
  Experience v2 found, root-caused, and deliberately left unfixed (its own
  bounded transient-retry attempt did not reliably close the gap and was
  reverted). Root cause confirmed directly (a real captured
  `sqlalchemy.exc.OperationalError: database is locked` stack trace under
  real concurrent multi-Stream SQLite writes) and reproduced
  deterministically on demand (a real second SQLite connection holding a
  real write lock, independent of host load) -- not merely inferred.
  `create_candidate_visit_from_proposal` was already idempotent
  (`proposal_id`-keyed) and fully transactional (a failed attempt rolls
  back completely, already proven by a pre-existing test), which made a
  bounded, classified retry provably safe. Fixed by (1) classifying the
  one demonstrated SQLite lock/busy shape as a new, narrow, retryable code
  distinct from every other repository failure, and (2) a bounded
  (3-attempt), short jittered-backoff retry at the *caller* boundary
  (`candidate_visit_adapter.attempt_candidate`) -- deliberately not inside
  the repository method again, which is what the reverted attempt already
  tried. No schema change; no change to Reviewed truth, concurrent-sibling
  Event reuse, or ambiguous-boundary arbitration. 4 new tests (1
  deterministic real-SQLite-lock end-to-end test, 3 fast mock-based
  tests), each independently confirmed RED against the pre-fix code and
  GREEN after. Tier 1/2: 231 passed, 0 failed. Tier 3 (full Core gate):
  5109 passed, 3 failed -- 2 already-disclosed pre-existing
  (`test_place_biodiversity_summary_repository.py`) and 1
  (`test_transport_worker.py`) confirmed unrelated by import-graph proof
  (a separate Camera Node-side package, zero code path to either changed
  file) plus a clean 5/5 re-run in isolation -- zero regressions
  attributable to this milestone. See the report for full detail,
  including honestly-disclosed remaining risk (an orphaned-media-file edge
  case on a failed-then-retried attempt, pre-existing and not introduced
  by this fix; the write transaction still does more work than strictly
  minimal while holding SQLite's lock, a real but separately-scoped future
  opportunity; WAL mode/a higher `busy_timeout` were not empirically
  tested, deliberately, given this exact codebase's own documented prior
  negative result from changing the shared engine's transaction
  configuration).
- **Prior accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views (see
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)).
  Classification **B** -- an integrated multi-camera product pass on top
  of the already-accepted Camera/Source + Multi-Camera Maturity v1
  foundation (cross-camera association engine, Area vocabulary, provider
  compatibility -- that milestone's own report had gone missing from this
  file's own bookkeeping, corrected here). A real correctness defect found
  and fixed with principled nuance across two rounds of correction (Tier 1
  test evidence, then a full Tier 3 Core run) rather than a blanket
  overcorrection: an archived camera's history was unreachable from every
  discovery surface; the fix preserves every already-tested current-
  active-observatory default exactly (Bird Log overview, Wildlife
  Insights, Biodiversity, Place Activity Report/Today) while making that
  real history reachable by explicit camera selection, with Place Story
  and research/conservation export unconditionally inclusive where no
  existing test disagreed. Today now surfaces its own already-computed
  per-camera activity/evidence-source facts for the first time; Bird Log's
  camera filter now reaches its overview list; Zone Insights' Place-wide
  aggregate coverage was a naive camera-hours sum, now a real elapsed-time
  union matching Today's own semantics; Dashboard distinguishes "some
  cameras need attention" from "every armed camera needs attention"; a
  real, measured concurrency proof (genuine concurrent threads, 2-camera
  and 4-camera-asymmetric topologies) found zero cross-Stream contamination
  and no starvation, and separately found, root-caused, and honestly
  disclosed (not shipped -- an attempted fix did not reliably help) a real
  occasional lost-candidate-Visit reliability gap under real concurrent
  write contention; a comprehensive, real, executable 3-camera product-
  shaped scenario proves the whole chain -- identity, coverage, overlap
  dedup, health, correction propagation -- coheres end to end. See the
  report for full detail and honestly-disclosed remaining gaps.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology (see
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
  Classification **B** -- a real, working, submission-ready iNaturalist
  workflow (eligibility preview with per-record reasons, explicit never-
  inferred location/media consent, batch prepare, a destination-shaped CSV
  confirmed directly against iNaturalist's own open-source bulk-import
  code, fingerprint-based staleness detection, and a self-reported
  external-result close-the-loop step -- proven end to end by a real,
  executable 12-Visit product-shaped scenario test) plus a bounded,
  additive Darwin Core Occurrence-core export (`basisOfRecord=
  "MachineObservation"`, GBIF's own recommended camera-trap value); eBird
  and direct GBIF publication both honestly, evidence-backed deferred
  rather than built -- eBird's own current "Rules and Best Practices"
  (checked 2026-08-25) explicitly excludes feeder/trail-camera data
  ("eBird is designed to collect in-person observations of living wild
  birds"), and GBIF direct publication requires organizational
  Participant-Node endorsement, not a backyard-user workflow. No live,
  authenticated destination submission exists anywhere in this milestone
  (Phase 26: no unsafe credential-storage workaround invented) -- a user
  uploads the generated file themselves. Two real security findings made
  and fixed during the milestone's own work: a CSV-injection gap in the
  one shared CSV writer behind every export in this codebase (generic
  research export, Camtrap DP, Darwin Core, and the new ecological CSV
  alike), and a `javascript:`-scheme external-URL gap on the self-reported
  result field. See the report for the full official-source destination
  research (URLs, quotes, access dates) and real, honestly-recorded
  remaining gaps (no live OAuth submit, no media-byte inclusion, no
  single-Visit deep-link pre-selection).
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters (see
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
  Classification **B** -- a real canonical attention-selection layer
  (`ProductRepository.sync_attention_signals`) composed entirely over
  already-accepted facts (`place_story`, `daily_digest`/its weekly reuse,
  the existing `ProductAlertModel` review/monitoring/storage/journal alert
  system), never a second computation path; genuine semantic-dedup work
  (two real double-notification anti-patterns found and fixed by tests, not
  merely by review -- first-seen vs. the 1st-species diversity milestone, and
  the underlying "first confirmed" fact computed two different ways in two
  different subsystems); reused, not reinvented, health/storage debounce;
  new per-user notification preferences (the product's first per-user
  settings row) with quiet hours evaluated in the viewer's own browser-local
  time (deliberately avoiding a server/Place timezone that does not exist);
  foreground-only browser-notification delivery (Phase 22 Decision B --
  Web Push explicitly evaluated and deferred, no cloud/push infrastructure
  added); a real, executable Monday-through-Sunday product-shaped quiet-week
  test proving the whole week stays calm (<=14 total attention items, zero
  ever `immediate` urgency). See the report for real, honestly-recorded
  remaining gaps (Web Push, detector/model-unavailable health attention,
  global not-per-user read/dismiss state, coarse Place Story deep-link
  scoping).
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk (see
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
  Classification **B** -- strong mobile experience and a clear secure
  remote posture with bounded external-network/PWA gaps. A verified
  navigation fix (a ~20-item sidebar that previously stacked in full above
  every page's own content below 980px is now a compact top bar + off-
  canvas drawer + 4-item bottom nav, proven overflow-free across 10 real
  automated phone-width screenshots); a from-scratch bounded PWA shell
  (manifest, icons, a service worker that only ever caches Vite's own
  immutable hashed assets, never navigation/API/data); LAN access made
  genuinely discoverable (`GET /api/product/connection` + a new Settings
  card); a private-overlay-network (Tailscale-compatible) remote-access
  posture investigated against real architecture and documented, with
  direct public-internet exposure and a cloud relay explicitly not built;
  new CORS regression coverage where none existed. Also closed, ahead of
  the broader mobile work, a bounded pre-existing correctness defect in
  the accepted Place Intelligence primitive `place_change_summary.py`
  (see "Bounded return-after-absence correction," below). Schema
  unchanged. See the report for real, honestly-recorded remaining gaps
  (Visit/Stream/Settings page density, a pre-existing Review Queue
  `product_category` data gap, no login rate-limiting, no live external-
  overlay-network validation possible in this sandbox).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place (see
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
  Classification **B** -- major useful capability, bounded history/story
  gaps (period summaries not built, pending a measured performance cost;
  environmental-context/weather caveats not yet composed onto a
  before/after insight; no dedicated taxon/Feature story page; no
  representative imagery on Story cards -- see the report's "Remaining
  major PRODUCT opportunities"). Schema unchanged (v55 -> v55): a pure
  derived read-model (`mockingbird.analytics.place_story.PlaceStoryEvent`)
  composed entirely from already-authoritative facts, no new table.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding (see
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
  Classification **B** -- major useful capability, bounded feature/data-
  model maturity gaps (environmental-context/weather caveats not yet
  composed onto a before/after result; a Feature can only link to one
  camera/Zone; no representative evidence or ranked comparison view yet --
  see the report's "Remaining major PRODUCT opportunities"). Two new
  additive tables (schema 54 -> 55): `PlaceFeatureModel` and
  `PlaceFeatureChangeEventModel` -- the first discrete before/after
  change-event model in this codebase, closing a gap two prior milestones
  both explicitly recorded as their own honest ceiling.
- **Push state:** Local accepted state. Do not push without explicit
  authorization.
- **Production detector:** MDv5a ONNX
- **Production threshold:** `0.1`
- **Production visual species-identification system:** BioCLIP-2 +
  Identification Eligibility / Abstention

**BioCLIP 2.5.** Explicitly rejected for release promotion. Reason: it
improved positive bird identification but showed unacceptable
confident-wrong/non-abstaining behavior on real hard negatives.

**SpeciesNet.** Not production bird identification. It remains an
unpromoted broader-wildlife lead based on external-domain mammal evidence,
pending genuine MockingBird-field evidence.

## 2. Current acoustic release state

**Acoustic / BirdNET: ACCEPTED -- RELEASE-READY OPTIONAL.** The milestone
is complete and frozen unless concrete evidence exposes a defect.

Established facts:

- substantial acoustic/runtime/multimodal functionality exists;
- `birdnetlib` code is Apache-2.0;
- the BirdNET model weights used by MockingBird are CC BY-NC-SA 4.0 /
  NonCommercial;
- official MockingBird packaging must not redistribute those BirdNET model
  weights;
- a build-time guard (`verify_no_nc_licensed_acoustic_model_redistribution`
  in `scripts/build_local_product.py`) now enforces that packaging
  boundary;
- BirdNET/model acquisition remains external and optional (the
  `classifier-birdnet` pip extra -- a dependency declaration, not a
  redistribution);
- core visual MockingBird remains functional without BirdNET;
- real Windows USB microphone capture has been validated;
- real BirdNET inference over captured audio has been validated;
- concurrent visual + audio capture has been validated;
- device failure/reconnect behavior has been exercised;
- Today/Bird Log multimodal count/row contradiction was fixed;
- macOS unsupported mic behavior now fails honestly;
- the documented BirdNET confidence environment setting now actually
  works;
- an unbounded acoustic in-memory segment list was bounded.

Remaining bounded gaps -- classified as bounded product/field gaps, **not**
reasons to reopen the acoustic architecture:

- no product-facing frontend acoustic health/status surface yet;
- no true physical mid-session microphone unplug acceptance;
- no multi-hour acoustic soak;
- no natural wild-bird acoustic field session from the accepted test
  hardware;
- no audio equivalent of visual Privacy Zone redaction/exclusion beyond
  the currently documented privacy boundary.

Acoustics are optional in the public release because of
licensing/distribution posture, not because the core implementation is
considered merely experimental.

**Licensing posture.** Commercial use of the BirdNET model weights is
**not** legally approved. Deliberately bundling/redistributing the model
into a commercially-directed distribution (paid support, a
crowdfunded/paid appliance, a hosted paid service) is not allowed under CC
BY-NC-SA 4.0 -- the clear case that license exists to restrict. Whether an
individual user's own private, non-commercial use of MockingBird+BirdNET
(the model is never redistributed by MockingBird itself) could ever be
implicated merely because the surrounding open-source project also accepts
donations or sells optional paid support remains genuinely **unresolved**;
the existing acceptance record recommends legal review before any
commercial-adjacent distribution decision actually touches the acoustic
feature, and does not resolve the question itself. This caveat is
preserved here, not relaxed. Release Licensing, Distribution & Third-Party
Legal Closure v1 (see §1/§3, above) re-verified the enforcement mechanism
behind this posture still works (`verify_no_nc_licensed_acoustic_model_
redistribution`, unchanged) and, for the first time, surfaced this
boundary to an actual product user (`docs/using-mockingbird.md`'s new
"Bird-sound identification (optional)" section; `THIRD_PARTY_NOTICES.md`)
-- it did not resolve the unresolved question above, which remains
exactly as open as stated.

## 3. Current authorized milestone

**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED.**

**2026-09-01 update (Representative Daylight Gate A Field Acceptance v9 --
True-Latency & Precision Reconciliation Tranche, see §1/§6.R):** ran the
field session the RTT re-proof's own closure made possible, at
classification **A** -- see
[representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
for the complete record. A real ~97.1-minute Observation session (T_start
20:34:04.727Z, `stopped_at` 22:11:53.796Z) against the same real reference
Camera Node, with the acceptance recorder confirmed writing real frames to
the correct per-session path within ~4.2 minutes (97.95% temporal-span
coverage, 2,353 files, 2.02GB of a 4.3GB sized budget -- no truncation).
**Item (1) (the first real, validly RTT-normalized T0->T5 latency field
distribution) is now closed:** 447 of 460 in-session RTT-bounded batches
`calibrated` (0 `inconsistent_samples`, 0 clock jumps), producing 24 of 25
admitted Visits with a real measured latency sample (median 111,811ms,
p90 173,944ms, max 307,373ms). Root-caused, not merely reported: an
additive decomposition (beyond the accepted `capture_to_visible_
latency.py` contract, using only already-published fields) shows a tight,
consistent ~48-60s "tail latency" (last capture to decision) across
almost every sample regardless of encounter length, matching the accepted
Visit-Continuity/episode-boundary quiet-period design exactly (multiple
individual proposals' own full `blocked_continuation_pending`/`episode_
boundary_not_yet_final` revision histories directly confirm it) -- this is
the deliberate, now-quantified cost of avoiding Visit fragmentation, not a
pipeline inefficiency. **Item (2) (reconciling the diverged false-Visit-
rate/useful-evidence-rate evidence body) now has a determinate answer:**
direct multi-frame pixel-region inspection (the v5/v7/v8-established
method) of every Visit with zero "strong" detections found **5 of 25
(20.0%) confirmed false** -- closely replicating v8's own 22.2%, and
materially diverging from v5 (5.3%)/v7 (4.0%). **v8's elevated rate
reproduces: it is a real, reproducible characteristic of this scene under
current conditions, not a v8-specific cohort anomaly.** Two distinct
recurring hard-negative spatial locations were found and traced in full
(detector box, confidence, frame content, track lifetime, proposal path,
evidence, species eligibility): one a near-exact recurrence of v8's own
already-reported location (a hanging leaf cluster over the road); one new
this session (a sun-glint on the tube feeder's own glossy cap). The
false-Visit-rate/useful-evidence-rate candidate budgets remain correctly
withdrawn (v9 reinforces, not reverses, v8's own withdrawal -- v9's own
strict useful-evidence rate, 76.0%, sits below the previously-proposed
~85% candidate). A real, previously-unknown Gate B residual instance was
also field-confirmed for the first time since Background/Empty Evidence
Species-Confidence Correctness v1 was accepted: 1 of the 5 confirmed-false
Visits received a wrong confident species label, root-caused precisely to
the fix's own already-disclosed exclusion (genuinely detector-sourced,
not tracker-extrapolated, evidence) -- not a regression, but the first
live instance of an already-known gap. Fragmentation reached a
sixth/seventh convergent real cohort at 0% (14/14 `correctly_represented`,
using the accepted reviewer-disposition method, not raw clustering);
duplicates a fourth convergent cohort at 0% (0/25, zero shared tracker
evidence); `blocked_missing_evidence` a third independently-varied
post-fix confirmation (8.9%, 12/135, closely clustered with v7's 9.4% and
v8's 9.9%). The rolling `max_candidates_per_hour` limit activated for the
second time in any cohort (6 real blocks, all high-confidence, self-
cleared correctly). Direct visual confirmation of 2 simultaneous birds at
the feeder was obtained (the best 2-subject evidence to date), but the
detection-stage mechanism (independently detected-then-NMS-suppressed, or
never separately detected) could not be traced this session
(`raw_detections` did not merge losslessly, a disclosed, known gap
matching v8's own). Zero persistence contention; zero ERROR/CRITICAL/
WARNING/Traceback lines across the full structured log. One real,
reproducible product defect was found via live product usage during this
session's own review-recording step, disclosed and worked around, not
fixed (out of this milestone's own scope): `POST /api/review-labels` with
`review_origin=agent_diagnostic` and no `reviewer_identity` correctly
raises `ReviewProvenanceError`, but `create_review_label` only catches
`ReviewRevisionConflictError` explicitly, so this well-formed validation
error propagates as an unhandled `500` instead of a clean `400` --
a precise, bounded next DEV contract is named in the report's own
"Defects" section. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Per this milestone's own explicit instruction,
Gate A is **not** self-closed by this report: the false-Visit-rate
divergence reproducing, rather than resolving, is judged a complete,
determinate answer to this milestone's own second primary objective, but
still leaves a release-blocking open item, and true latency has exactly
one real cohort (Gate A's own standing rule requires cross-session
convergence before any number is proposed). Authorization remains **NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. See
§6.R, below, for the complete, updated "Remaining Gate A dependency"
account.

**2026-09-01 update (Reference Camera Node RTT-Capability Upgrade &
Compatibility Re-Proof v1, see §1/§6.R):** closes the Camera Node upgrade
dependency the v8 reconciliation immediately below named as Gate A's own
sharpest remaining item. See
[reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
for the complete record. Classification **A**. The real reference Camera
Node (`node-76ec8e53ae586dd0`, Pi 4, `192.168.1.112`) was upgraded, using
the accepted `scripts/install_camera_node.py` mechanism end to end (build
against accepted HEAD `1a39479` -> preflight -> install), from
`git_commit baf9fdb` (71 commits behind, built 2026-08-27, predating the
RTT protocol) to `git_commit 1a39479` itself -- confirmed via the fresh
`manifest.json`, `install_camera_node.py --status`, and direct inspection
of the deployed wheel. Zero unexpected config/data loss (`node.env`
byte-preserved per the installer's own report; pairing survived the
upgrade itself intact -- `node_id`/`pairing_required` unchanged
before/after); rollback to the prior build remains available and was not
exercised (no new defect appeared). Pre-upgrade RED confirmed live
(`GET /node/v1/health` lacked `node_receive_time`/`node_time`);
post-upgrade GREEN confirmed live (both fields present, valid UTC,
`node_receive_time <= node_time`, advancing across independent requests
over the following ~10 minutes -- proven live, not cached). Ran the real,
unmodified production RTT functions (`CameraNodeClient.sample_clock_
round_trip`, `estimate_rtt_clock_calibration`) directly against the
upgraded Node: **6 of 6 real calibration batches (30 round trips, ~3.35
real minutes) reached `state="calibrated"`**, zero `insufficient_samples`,
zero `inconsistent_samples`, all 6 batch intervals mutually consistent
(raw RTT 102-393ms, all well under the 1000ms ceiling). This is the first
real, valid RTT-bounded calibration evidence to exist since the protocol
was accepted -- v8's own 796-batch, 0-valid session is now understood to
be an infrastructure gap already closed, not a mechanism defect (the
mechanism itself was already independently proven correct-under-failure by
v8; this milestone proves it correct-under-success). A real camera smoke
test (a fresh, disposable, CPU-only local Host instance -- no Windows/GPU
needed for this, since the live-preview path used is independent of the
GPU-only Observation Engine detector) drove a real pairing, a real camera
-setup completion, and three real 1920x1080 live frames through the actual
Host API, with advancing frame sequence numbers and capture timestamps,
visually confirmed as real footage of the reference yard. This session
deliberately displaced the stale pairing v8's own session had left in
place (with real-time user approval, after the environment's own safety
layer correctly declined to let this proceed silently) -- documented
explicitly as a choice this session made for its own verification
purposes, distinct from and subsequent to confirming the upgrade itself
preserved pairing cleanly. Doctor ran clean for every check within this
milestone's scope; confirmed no dedicated "old Node version" warning
exists anywhere in Doctor to have newly cleared (there was never one).
Also newly, independently root-caused (not merely re-cited): **no
automated mechanism anywhere in the release process currently checks
Camera-Node-build-vs-Host-build compatibility before a Gate A/field
-acceptance session begins** -- `install_camera_node.py --preflight` only
ever runs on-demand, before an operator-chosen upgrade, never as a
precondition of starting an Observation session. Disclosed, not fixed
(explicit non-goal: no fleet-management feature built here) -- a future,
separately-scoped release-engineering milestone should weigh a lightweight
preflight/Doctor check for this. No production code was changed; no tests
were invented (real-hardware validation is this milestone's own
validation, per its own explicit instruction). Authorization remains
**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged;
this closure does **not** authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone.
**Remaining Gate A dependency, in priority order, superseding the priority
order in the v8 entry immediately below:** (1) the first real, *validly
RTT-normalized* T0->T5 capture-to-visible latency field distribution --
the Node, Host, and calibration mechanism are now all proven ready; only a
live field session's own real samples are missing; (2) reconciling the
now-diverged false-Visit-rate/useful-evidence-rate evidence body (v5/v7
vs. v8) -- unchanged, not attempted here (non-goal: no detector/model
tuning); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (4) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (5) the ~13 untraced
`blocked_missing_evidence` records, v7's own (unchanged); (6) the
already-known Gate B admission-precision residual (unchanged).

**2026-09-01 update (Representative Daylight Gate A Field Acceptance v8 --
True-Latency & Crowding Closure Tranche, see §1/§6.R):** ran the first field
session against post-RTT-calibration accepted HEAD, at classification **B**
-- see
[representative-daylight-gate-a-field-acceptance-v8-report.md](representative-daylight-gate-a-field-acceptance-v8-report.md)
for the complete record. Deployed a genuinely fresh, disposable instance
(not the operator's own identity; reused V7's already-populated runtime/
model/BioCLIP caches by renaming its directory and wiping only `userdata/`,
per two user-approved storage-headroom decisions -- see the report's own
"Defects" -- rather than paying a fresh ~8GB cache-population cost against
this milestone's own severely constrained storage headroom, itself now
root-caused for the first time: every prior field-acceptance disposable
instance was left running/retained indefinitely after acceptance, none
ever cleaned up). A real, live 158.2-minute Observation session followed
against the real reference Camera Node (the identical physical camera
every prior Gate A cohort used) -- materially longer than the 60-120
minute target, disclosed as such, not concealed. `candidates_created`
reached **27** by session end (a new high across every Gate A cohort to
date, exceeding v7's own 25), all in-session, none rescued at stop (an
honest `stop_finalization_pending` observed live then correctly resolved
with nothing further rescuable). Fragmentation accounting reached, for the
first time in any cohort, **zero residual ambiguous denominator units**
(16 of 16 `correctly_represented`, 0 fragmented/duplicate/missed/merged --
the fourth/fifth convergent real cohort at 0% confirmed fragmentation).
Fallback mechanics were exercised more deeply than any prior cohort (8
attempted, 7 admitted, 1 honestly exhausted, one chain reaching fallback
position 3 -- the deepest yet observed), and `blocked_missing_evidence`
(9.9%, 21/212 distinct proposals, using the same denominator convention v6/
v7 established) closely replicates v7's own post-fix level at nearly 2x the
sample size, a real second independently-varied confirmation the
Preservation/Fallback fix holds at scale. `observation_candidate_visit_
persistence_contention`: zero. Stop-finalization: honest, clean.

**Primary purpose not achieved, for a real, precisely root-caused reason,
not a measurement-contract defect: zero valid RTT-bounded calibration
samples were obtained (0 of 796 attempted batches; 796 `insufficient_
samples`), so zero valid true T0 -> T5 latency samples exist (27 of 27
admitted Visits honestly report `invalid_clock_mapping`).** Root-caused
three independent ways, not merely disclosed: the reference Camera Node's
live `GET /node/v1/health` response lacks the two additive fields
(`node_receive_time`/`node_time`) the accepted RTT-Bounded Clock
Calibration v1 milestone added; `grep` of the Node's own installed code
confirms the string does not exist anywhere on it; and its own install
manifest records `git_commit baf9fdb` (built 2026-08-27), independently
confirmed via `git merge-base --is-ancestor` to be **69 commits behind**
current HEAD and to predate the commit (`bc6d5ee`) that introduced the
field the calibration protocol depends on -- the reference Camera Node has
not been redeployed since the "Camera Node Upgrade & Compatibility
Recovery v1" milestone (2026-08-26), across five field-relevant milestones
accepted since. Not fixed live, deliberately: doing so mid-session would
have required restarting/redeploying the Node's own service, risking
exactly the "do not force a reconnect" action this milestone's own
governing brief explicitly prohibited, and would have contaminated
already-collected measurements. The accepted one-way (relative)
drift/jump monitor, unaffected by the missing fields, returned a complete,
clean, fully valid record throughout (796 of 796 `calibrated`, offset
stable within an 85-244ms band across the full session, zero clock
jumps) -- real, positive evidence the underlying Node-Host clock
relationship was stable and well-behaved, but this cannot substitute for
the two-sided bound the milestone needed, by the accepted design's own
explicit reasoning. **RTT calibration mechanism itself further validated
as correct and honest under exactly this failure mode** (graceful
degradation, never a crash, at every layer, across a genuinely large real
sample) -- the measurement contract is proven working; the physical
prerequisite it depends on is not yet met.

A further real, well-evidenced, and materially reopening finding: **direct
pixel-region inspection** (cropping each low-confidence, no-species
admitted Visit's own exact recorded bounding box out of its nearest
acceptance-recorder frame, matching the v5 report's own established
method) found **6 of 27 admitted Visits (22.2%) to be false or
likely-false** -- empty grass/background, not animals, 5 of them directly
pixel-confirmed and clustered at one specific recurring low-confidence
screen location (most plausibly one hanging leaf cluster or branch tip).
This directly and materially exceeds v5 (5.3%) and v7 (4.0%), the two
cohorts whose own convergence previously supported a candidate false-Visit
budget -- that candidate is **withdrawn pending more evidence**, not
reaffirmed, and the useful-evidence-rate candidate (directly downstream of
the same root cause) is withdrawn alongside it. Root cause is real, not
noise: production admission stays deliberately confidence-blind by
measured decision (`roadmap.md` "Numeric release budgets" -- confidence
gating was swept against real reviewed data and explicitly not adopted),
so a scene with a recurring weak-signal location pays a real, now-quantified
cost under that design. Gate B's own abstention behavior held cleanly
throughout despite this -- **zero confidently-wrong species labels on any
false Visit** -- the accepted Background/Empty Evidence Species-Confidence
Correctness v1 fix continues to hold under the largest real test it has
yet received. This same rigorous pixel-level check also **reversed the
session's own initial working hypothesis**: the cleanest-looking
concurrent-multi-subject signature found this session (Visits 010/011 --
identical start offset to the millisecond, shared `event_id`, clearly
disjoint bounding-box positions) turned out, on direct pixel inspection,
to be two independent false detections, not two birds -- disclosed
explicitly as a methodological finding (structural/temporal concurrency
signals alone are not sufficient proof of genuine crowding) rather than
quietly corrected. A second candidate pair (Visits 021/022, materially
higher confidence, same shared-Event structural signal) remains the
session's best 2-subject evidence but falls outside the acceptance
recorder's own coverage window (which itself stopped at ~99.4 of the
session's 158.2 minutes, cleanly, on reaching its own configured 4GB byte
bound -- a disclosed, self-inflicted, non-product coverage shortfall, not
a product regression; product-side Observation Engine continuity was
~100%, zero reconnects logged, zero errors in the live session itself) and
so could not be additionally visually confirmed. No 3+-subject moment was
observed. Recall: the one exhaustive-denominator window reviewed (0-5.0
minutes, all 23 track generations individually reviewed, not sampled)
found 3 of 3 genuine encounters represented (100%), with one further
confirmed-but-honestly-rejected track disclosed as ambiguous rather than
folded into either side of the ratio.

Two further concrete, bounded, same-session findings, both disclosed, not
release-blocking: an operator (not product) recorder-configuration mistake
(`MAX_BYTES` exceeding `AcceptanceRecorderConfig`'s own hard 5GB ceiling)
caused one real `500` on the first `observation/start` attempt, root-caused
immediately from the structured log's own traceback and fixed by
relaunching the already-built release with a corrected value -- zero
product code touched, and the storage-decline root cause named above,
mitigated for this session via two user-approved decisions (reusing V7's
caches; deleting its now-redundant 3.2GB recorder set after archiving its
small, critical raw ledger data first, closing part of the "v7's own raw
evidence never archived" gap Gate A Measurement Closure v1 had disclosed)
but left at only ~3.5GB free post-session, needing attention before any
near-term next session. All raw session artifacts (merged lossless
ledger, Visits export, reviewer-dispositions used to fully resolve
fragmentation, accounting reports, and the decisive pixel-crop images) are
archived to
`data/field-acceptance/2026-09-01-gate-a-v8-true-latency-crowding-tranche/`.
No production code was changed by this milestone; Core was not run per its
own explicit instruction for a no-code-change field session (identity,
schema, and product-visible results were independently validated live
instead -- see the report's own "Identity"/validation account). This
closure does **not** authorize the next Representative Field Acceptance /
Gate A session, External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. Per this milestone's own explicit instruction, Gate
A is **not** self-closed by this report -- closure requires external
(ChatGPT) review; see §6.R, below, for the complete, updated "Remaining
Gate A dependency" account, now led by the Camera Node upgrade
dependency and the reopened false-Visit-rate/useful-evidence-rate
evidence body.

**2026-09-01 update (Camera Node <-> Host RTT-Bounded Clock Calibration
v1, see §1/§6.R):** closes the absolute Node<->Host offset/error-bound gap
the accepted Camera Node -> Host Clock Normalization v1's own report
disclosed but did not solve -- that milestone's own one-way estimator
(`received_at_host - captured_at_node`) is, by construction, only ever a
one-sided upper bound on the true offset (`true_offset_ms <=
min(deltas)`), never a defensible two-sided error bound, however tight its
own observed jitter spread looks. See
[camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
for the complete record. Classification **A**. Reuses the existing `GET
/node/v1/health` request/response operation (two additive response
fields, `node_receive_time`/`node_time`) rather than inventing a dedicated
time-sync protocol, per this milestone's own explicit instruction -- a
real correction, disclosed rather than silently fixed, to the accepted
prior milestone's own "no request/response exchange exists" framing
(correct for the one-way analysis-stream push specifically, incorrectly
generalized to the whole Camera Node protocol). A rigorously-derived
two-sided offset interval (`[offset_min_ms, offset_max_ms]`, never a
symmetric-delay NTP formula) replaces the one-way estimator as the sole
input `capture_to_visible_latency.py` normalizes T0 through; the one-way
estimator itself is not discarded (its per-frame ~10-second cadence
continues, unchanged, as the *relative* drift/jump monitor that decides
when a live session spends the cost of a fresh RTT-bounded batch -- one of
four recalibration triggers: session start, a 5-minute bounded periodic
cadence, detected reconnect, or a one-way-detected jump). Every latency
sample now carries the full interval (`latency_min_ms`/`latency_max_ms`),
never only a collapsed point estimate; re-proved directly against
fallback, stop-finalization, and multi-subject-sibling scenarios, each now
asserting the interval, not only the point estimate. A real regression (a
sequential 5-attempt calibration batch against an unreachable Node
blocking a live session's own frame-processing tick for up to ~10 seconds)
was found via a genuinely failing pre-existing end-to-end test and fixed
(concurrent batch attempts; the first calibration moved off the session
-start critical path entirely, triggered instead at the first ordinary
tick). Zero Camera Node/wire-protocol breaking changes -- an old Node's
`/node/v1/health` response simply lacks the two new keys, degrading
honestly to `insufficient_samples`, never a crash. Schema unchanged
(`v58`) -- nothing here is persisted to SQLAlchemy. Tier 1 (404 passed) +
Tier 2 (670 passed, combined in one invocation) + Tier 3 (full Core gate,
run because this milestone -- unlike the accepted prior one -- adds
genuinely new runtime network I/O to the live engine loop, not merely
passive computation over already-flowing data): 5487 passed, 3 failed (all
3 independently confirmed pre-existing/unrelated by fresh baseline
bisection -- the same recurring `test_place_biodiversity_summary_
repository.py` pair this file's own history has already reconfirmed across
multiple prior milestones, plus one real-clock/local-day-boundary-sensitive
test in `test_stream_playback_contract.py` whose own 27m38s run happened
to straddle the actual local-midnight rollover into 2026-09-01), 3
skipped, 23 deselected, 11 xfailed. Zero new ruff findings (verified via
direct line-content diff against a stashed baseline, not merely a count
match). **Absolute Node<->Host clock-calibration state moves from OPEN to
CLOSED**: a defensible bounded interval now exists, with honest
degradation for poor-quality/high-RTT/mutually-inconsistent samples, and
epoch-based clock-jump invalidation extended to the new anchor type.
**True capture-to-visible latency remains MORE FIELD EVIDENCE REQUIRED,
unchanged in kind but now for a materially stronger reason a second
time**: the measurement mechanism itself is now both closed AND correct/
defensible, not merely closed; every historical cohort (2026-08-19, v6,
v7) still predates `rtt_clock_calibrations` entirely and cannot be
retroactively fixed. A next field session run against post-this-milestone
accepted HEAD would be the first able to produce a real, validly
RTT-normalized T0 -> T5 distribution. Does not reopen fragmentation
accounting, does not tune models/detectors, does not run a field cohort.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged; this closure does not authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone. **Remaining Gate A dependency, unchanged in
priority order and in every item's own substance -- only item (1)'s own
bar is now sharper a second time:** (1) real, *validly RTT-normalized*
capture-to-visible latency field samples -- the measurement mechanism is
now both closed and defensible; the samples themselves still do not
exist; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (3) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (4) the ~13 untraced
`blocked_missing_evidence` records (unchanged); (5) the already-known Gate
B admission-precision residual (unchanged). See §6.R, below, for the
complete, updated account.

**2026-08-31 update (Camera Node -> Host Clock Normalization for True
Capture-to-Visible Latency v1, see §1/§6.R):** closes the clock-domain
precondition Gate A Measurement Closure v1's own T0 -> `decided_at` figure
was silently resting on -- not a new field session (none run here), but
proof that the ~39-second discrepancy that figure's own caveat cited was
never evidence of a real Camera-Node-vs-Host wall-clock offset, and a
real, bounded, tested calibration/normalization mechanism for when one
actually needs measuring. Classification **A**; see §6.R, below, for the
complete account (root-cause re-measurement, calibration/uncertainty/
drift/clock-jump design, fallback/stop-finalization/multi-subject proof,
551 Tier 1 + Tier 2 tests, zero new ruff findings). Schema unchanged
(`v58`). Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; does not authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.

**2026-08-31 update (Gate A Measurement Closure v1 -- Fragmentation
Accounting & True User-Visible Latency Instrumentation, see §1/§6.R):**
directly closes the two measurement gaps the prior reconciliation's own
"Remaining Gate A dependency" named as items 1 and 3 -- see
[gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
for the complete record. Classification **A**. A new, explicit,
human-correctable fragmentation-disposition layer
(`fragmentation_accounting.py`) reproduces (RED) and corrects (GREEN) the
real methodology problem v7 disclosed: `cluster_encounters`'s own raw
`duplicate_visit_cluster_count` signal misreads sustained-activity
mega-clusters as fragmentation/duplication defects when every admitted
Visit inside them is a genuinely separate real encounter -- the corrected
accounting never promotes that raw signal to a disposition on its own,
staying honestly `ambiguous` absent a shared-evidence (`duplicate`) or
shared-Event-concurrent-sibling (`correctly_represented`) structural
signal or an explicit, non-empty-note-bearing reviewer override. Reran
this corrected accounting against every cohort with recoverable raw
ledger evidence -- the 2026-08-19 primary full-funnel cohort (from its own
already-tracked `data/field-acceptance/` evidence) and v6/v7 (whose own
raw counterfactual-ledger snapshots were never archived there, a disclosed
tooling-hygiene gap; recovered from the original field sessions' own
still-present local scratchpad directories, verified lossless against
each accepted report's own published counts, and archived under
`data/field-acceptance/2026-08-31-gate-a-{v6,v7}-measurement-closure-
reanalysis/` for future reproducibility). All three reanalyzable/reported
cohorts (2026-08-19, v5, v7) now converge on **0% confirmed
fragmentation** under one consistent methodology, most residual ambiguity
resolved via each cohort's own already-existing independent review (the
2026-08-19 cohort's own `independent-encounter-table.md`; v7's own
already-accepted "Multi-subject" section) rather than fresh guessing --
**fragmentation moves to READY FOR FORMAL BUDGET REVIEW**, candidate
~0%/low single digits. Separately, a full T0 (source capture) -> T5
(query-visible) production timeline was traced directly in code: T2/T3/T4/
T5 already collapse into one existing Host-domain value
(`ProposalOutcomeRecord.decided_at`) in this codebase's current
synchronous design, and T4/T5 equivalence is now *proven*, not assumed, by
a new repository-level read-after-write test; the one genuine missing
piece, T0, is now instrumented via one small, additive
`TrackGenerationRecord.start_captured_at`/`end_captured_at` field pair
(values already in scope on every `TrackUpdate`, never a new wall-clock
read), propagated through to the counterfactual-ledger API response so
future field-acceptance tooling actually receives it. Fallback timestamp
correctness (a genuine risk after the accepted v6/v7 fallback work) was
independently proven at two layers -- the new latency module and a new
persistence-boundary test on `engine_runtime.py` -- and a real ~39-second
offset-vs-wall-clock drift was found in v7's own preserved data, directly
justifying the module's explicit clock-domain-caveat design. **Capture-to
-visible latency remains MEASUREMENT CONTRACT CLOSED / MORE FIELD EVIDENCE
REQUIRED**: every historical cohort checked (2026-08-19, v6, v7) predates
the new field and honestly reports every sample `unavailable_capture_time`
-- confirmed directly, never inferred around. Schema unchanged (`v58`,
every change additive or a brand-new zero-existing-caller pure module).
Tier 1 (218) + Tier 2 (222) = 440 tests passed, 0 failed; zero new ruff
findings (verified against a stashed baseline); Tier 3 explicitly not run,
decision documented in the report (additive/narrow production-code
footprint, not warranted "solely because this is called Gate A," per this
milestone's own explicit instruction). One pre-existing, latent bug fixed
(`run_encounter_accounting.py`'s own `decided_at` was never parsed into a
`datetime` -- harmless until this milestone's own new consumer needed real
arithmetic on it), confined to an offline analysis script, never the live
admission/persistence path. Does not tune models, does not change Visit
grouping semantics, does not run a field cohort. Neither budget is
accepted here -- both are proposed for external review only. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged; this closure does not authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does not select a next development milestone. See
§6.R, below, for the complete, updated "Remaining Gate A dependency"
account.

**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche** is, as of this Post-v5 Global
Product-Roadmap Reconciliation & Gate A Next-Step Authorization milestone
(2026-08-30), the next RELEASE-CRITICAL milestone -- directly authorized
outside this file, as a bounded Lane R field-validation session, exactly
the same standing this file has already recorded for v4 and v5 each in
turn without ever changing this section's own bold statement above (see
[roadmap.md](roadmap.md) "Gate A," 2026-08-30 update, and "Numeric release
budgets" for the complete reconciled evidence state this authorization
rests on). **Not yet run.** Purpose: exactly the "Remaining Gate A
dependency" Representative Daylight Gate A Field Acceptance v5's own
report named -- a second post-fix daylight cohort, for replication and
closure evidence, not product tuning. Prefer a cohort that exercises
genuinely simultaneous multi-subject activity (the one dimension v5 could
not exercise at all: real simultaneous presence was confirmed in-scene,
but no two Visits shared an Event as concurrent siblings), because that
remains materially under-evidenced; a sparser single-subject replication
is also useful and an acceptable substitute if multi-subject conditions
do not naturally occur. Contract:

- no product/perception/admission/Visit/evidence/classification tuning
  while measuring -- the accepted build is measured unchanged, exactly as
  v4/v5 measured it;
- representative real daylight conditions required, directly checked (a
  dedicated pre-flight scene check, matching v5's own method) before
  committing to a long session -- if conditions are not representative,
  stop rather than contaminate the evidence body; no requirement to force
  unsuitable conditions merely to complete the cohort;
- genuinely simultaneous multi-subject admission/arbitration is a
  priority evidence target, sought, not artificially manufactured;
- sustained-activity admission behavior and stop-finalization behavior
  remain under observation -- confirm no regression, not merely re-prove
  the fix once more;
- duplicate-Visit and fragmentation checks remain required, matching
  every prior cohort's own accounting;
- an independently retained denominator/evidence accounting (the
  established acceptance-recorder + counterfactual-ledger method) is
  required, matching v4/v5's own methodology;
- honest abstention remains acceptable -- no requirement to produce a
  specific species count or a specific outcome;
- this milestone measures; it does not fix. Per this project's own
  established field-acceptance bar, any defect found (including a further
  instance of the already-disclosed Gate B background-evidence/
  confident-label liability, below) is root-caused and disclosed, not
  necessarily fixed in the same milestone.

This reconciliation does **not** authorize External Pre-Release
Acceptance or Final Release Hardening -- current evidence does not yet
support either. It does not itself run the field session, and does not
select any other next development milestone. Gate A/Lane R remains open
(§6.R, below). Two budget dimensions -- minimum monitoring coverage
(~99%) and minimum useful-evidence rate (~85%) -- are reconciled to
**READY FOR FORMAL BUDGET REVIEW** (candidate values proposed across all
four real cohorts to date, not yet formally accepted release budgets --
see [roadmap.md](roadmap.md) "Numeric release budgets"); recall,
false-Visit rate, fragmentation rate, and capture-to-visible latency
remain evidence-accumulated only, with no candidate value yet proposed.
No numeric recall budget or claim is introduced by this reconciliation --
v5's own qualitative "no missed genuine encounter found via targeted, not
exhaustive, review" conclusion is preserved exactly as reported, not
converted into a recall percentage. The known Gate B liability carried
forward unresolved: weak/spurious detections can still yield background
evidence that BioCLIP labels with a confident (wrong) species name,
reproduced fresh by v5 (a "Brown Thrasher," 89.9%, on confirmed empty
lawn/background) -- a known, already-`roadmap.md`-named regression class,
not a new v5 blocker, not release-blocking for Gate A directly, and
explicitly not to be fixed opportunistically inside v6.

**2026-08-30 update (Background / Empty Evidence Species-Confidence
Correctness v1, see §1, above):** the specific v5 instance of this
liability named directly above is now fixed -- a new geometry-
corroboration eligibility check (reading already-persisted Localization
Attribution / Detection Geometry Lineage v1 facts, schema unchanged)
withholds an automatic species claim on a crop whose own box does not
correspond to a real, contemporaneous detector observation, proven
RED->GREEN against the real production path and real-cohort validated.
Honestly bounded, not a full close: a detector-sourced-but-still-wrong
background crop (a genuinely confident, contemporaneous, but recurring or
otherwise misleading detector hit) remains an open, disclosed Gate B
residual, unchanged by this fix -- see the milestone's own report and
`roadmap.md` Gate B for the complete accounting. This closure does not
alter the Gate A v6 contract above in any way -- v6 remains authorized,
not yet run, exactly as already stated -- and does not itself authorize
Gate A v6 execution, External Pre-Release Acceptance, or Final Release
Hardening. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged.

**2026-08-31 update (Representative Daylight Gate A Field Acceptance v6 --
Post-Fix Replication & Multi-Subject Tranche, see §1/§6.R):** v6 has now
run, at classification **B**, not A. A real, live 106.63-minute
Observation session against the real reference Camera Node directly
confirmed the *specific* Sustained-Activity starvation mechanism v4 found
does not recur -- arbitration reached a decision for every ambiguous
component on schedule throughout -- but `candidates_created` ended the
session at zero anyway, despite two independently-confirmed, real,
sometimes-simultaneous-multi-subject activity segments, root-caused to a
different, precisely source-traced mechanism: an arbitration winner can
still fail at the downstream evidence-availability gate (the bounded
128-entry evidence-byte cache), with no retry/fallback to a runner-up, so
the component's real activity is permanently lost. This is a concrete
field measurement of a risk already named (not fixed) when that cache
bound was last raised, not a new defect class -- but a materially sharper
one than existed before (48/263 distinct proposals, 18.3%, this session,
versus v5's own 2.8%). See the milestone's own report for the complete
account, including two bounded, tested, own-session deploy-tooling fixes
(zero product/perception code touched) and the full honest-gap accounting
for the dimensions zero admissions made unexercisable this session
(background/empty-evidence eligibility, species assistance, useful-
evidence rate, false-Visit rate, fragmentation). This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. Authorization remains **NONE
-- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. No budget
dimension moves to READY FOR FORMAL BUDGET REVIEW this update, and no
existing candidate (monitoring coverage, useful-evidence rate) is
withdrawn -- this session neither confirms nor refutes either, having
produced zero admitted Visits to measure a useful-evidence rate over, and
having measured monitoring coverage (~99.4%) consistent with the existing
candidate. Gate A/Lane R remains open, and this update reopens rather than
narrows the "Remaining Gate A dependency" picture -- see §6.R, below, for
the complete account, now led by the evidence-cache-exhaustion/no-fallback
mechanism this session concretely measured.

**2026-08-31 update (Pending-Proposal Evidence Preservation & Arbitration
Fallback Correctness v1, see §1/§6.R):** the evidence-cache-exhaustion/
no-fallback mechanism v6 concretely measured immediately above is now
fixed, at classification **A** -- see
[pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
for the complete record. Bounded, pending-proposal-aware preservation
(protects a bounded, per-tick-recomputed set of still-actionable
proposals' priority evidence from the shared cache's own eviction) and
deterministic same-component fallback (walks a resolved component's
winner then its own remaining stable members, in arbitration's own
existing rank order, if the winner cannot actually be admitted) were both
implemented and independently tested, per this milestone's own governing
brief's explicit requirement for both mechanisms. The unchanged 128-entry
cache bound was deliberately *not* raised a fourth time. Two real design
corrections were found and fixed during implementation and this
milestone's own adversarial self-review -- see the report's own
"Preservation contract"/"Fallback contract" sections for the complete
account, including one (an iteration-order-dependent double-attempt bug)
found only by self-review, after tests were already passing, and locked
in by a dedicated permanent regression test before this milestone
concluded. Deterministically reproduced against real production logic
(both required RED reproducers, plus a 105-simulated-minute v6-shaped
replay against the real bounded cache, all confirmed genuinely RED on
accepted `b37656d` and GREEN after the fix). Tier 1 187/187, Tier 2
279/279, Tier 3 (one full Core run) 5357/5372 passed (3 skipped, 11
xfailed), 1 failed and independently confirmed unrelated (a pre-existing
timing-sensitive flake in `test_temporal_capture_cli.py`, made visible
only by this investigation's own necessary four-way concurrent chunked
Core execution -- zero code-dependency relationship to any file this
milestone touched, passes on baseline, passes 5/5 in isolation with the
fix in place). No schema change. This is nighttime/implementation
correctness work only, per this milestone's own explicit non-goal -- no
field session was run, and this closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. Gate A/Lane R
remains open -- see §6.R, below, for the updated "Remaining Gate A
dependency" account and this milestone's own report, "Next field proof
required," for exactly what the next daylight cohort must prove (chiefly:
non-zero in-session admissions under sustained activity that this fix's
own deterministic proof cannot itself provide -- field confirmation
remains outstanding).

**2026-08-31 update (Representative Daylight Gate A Field Acceptance v7 --
Evidence-Preservation / Arbitration-Fallback Re-Proof, see §1/§6.R):** the
field confirmation the pending-proposal fix's own report named as
outstanding immediately above is now provided, at classification **A** --
see
[representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
for the complete record. A real, live 89.4-minute Observation session
against the real reference Camera Node (the identical physical camera
v4/v5/v6 used) directly confirms the fix under genuine field conditions:
`candidates_created` reached 25 in-session (first admission ~6.6 minutes in,
growth throughout, not concentrated at stop) -- reversing v6's own zero and
exceeding v5's own 19. Six real, natural fallback attempts occurred (five
admitted, one honestly exhausted), three fully reconstructed end to end
(component members, canonical ranking, why the winner failed, fallback
position, admitted evidence, species outcome); zero instances of the
unacceptable "component silently discarded while a viable member exists"
outcome were found anywhere directly traced. `blocked_missing_evidence`
materially reduced (18.3% -> 9.4%, roughly halved). Genuine concurrent
multi-subject admission was directly visually confirmed for the first time
across any Gate A cohort (two independent sibling-Event pairs, one requiring
the fallback mechanism simultaneously) -- the other dimension the prior
reconciliation's own "Remaining Gate A dependency" named as still open. One
bounded, tested, own-commit deploy-tooling defect was found and fixed along
the way (a WSL/Windows path-conversion bug that left the independent
acceptance recorder silently unarmed for a discarded ~2m26s preliminary
session, before the formal session this report measures) -- zero product/
perception/admission/Visit/evidence/classification code touched. All 25
admitted Visits individually reviewed against real recorder frames: 96.0%
useful-evidence rate, one confirmed real false Visit (empty background,
correctly given no species label), zero genuine duplicate Visits (zero
shared tracker evidence across all 25 admissions -- the strongest test
applied to date). Honestly disclosed, not blocking: a concrete field
instance of the already-named, not-yet-benchmarked crowded-feeder/NMS gap (a
third simultaneous bird the detector never separately perceived); ~13
`blocked_missing_evidence` records outside this session's own two
exhaustive-denominator windows remain individually untraced; fragmentation-
rate and true user-visible latency remain evidence-accumulated only. Two
further budget dimensions move to **READY FOR FORMAL BUDGET REVIEW**
(maximum false-Visit rate, candidate ~5-10%; maximum duplicate-Visit rate,
candidate ~0%/low single digits), alongside the two already-proposed
dimensions this session's own measurements strengthen (monitoring coverage,
useful-evidence rate) -- see "Numeric release budgets" in
[roadmap.md](roadmap.md) for the still-current reconciled accounting, not
itself updated by this milestone per its own governing brief's explicit
scope (release-execution-state.md only). This closure does **not** authorize
External Pre-Release Acceptance or Final Release Hardening, and does **not**
select a next development milestone -- authorization remains **NONE --
GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged. Per the
milestone's own explicit instruction, Gate A is **not** self-closed by this
report -- closure requires external (ChatGPT) review of the accumulated
evidence; see §6.R, below, for the complete, updated "Remaining Gate A
dependency" account.

Representative Daylight Gate A Field Acceptance v5 (directly authorized
outside this file, as the next RELEASE-CRITICAL field-validation session
for the accepted, frozen Sustained-Activity Visit Admission Starvation &
Stop-Finalization Correctness v1 fix) is now accepted at classification
**A** -- see §1, above, §6.R, below, and
[representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
for the full record. This closure does not change this section's own
bottom-line authorization, which remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED** exactly as it did before it -- this milestone
was not self-authorizing, and does not authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening. Gate A/Lane R remains open; the field session
this milestone ran real-world-confirms the accepted fix works end-to-end
under sustained genuine activity (see §6.R for the complete evidence) but
does not itself declare Gate A passed, propose an accepted numeric
release budget, or select a next development milestone.

Lane C Sparse-State Honesty & First-Hour Narrative Closure v1 (directly
authorized outside this file, as a bounded, HIGH-RELEASE-VALUE
product-correctness milestone closing the two remaining bounded DEV gaps
an accepted read-only Lane C reconciliation had left open) is now accepted
at classification **A** -- see §1, above, Lane C/§6, below, and
[lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md)
for the full record. This closure does not change this section's own
bottom-line authorization, which remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED** exactly as it did before Ongoing Monitoring
Failure Diagnostics for RTSP / Local USB / Windows DShow v1 below --
neither milestone was self-authorizing, and neither authorizes the next
Representative Field Acceptance / Gate A session, Lane G validation,
provider integrations, External Pre-Release Acceptance, or Final Release
Hardening.

Ongoing Monitoring Failure Diagnostics for RTSP / Local USB / Windows
DShow v1 (directly authorized outside this file, as a RELEASE-CRITICAL
milestone closing Lane G's own remaining, previously-disclosed
ongoing-monitoring generic-collapse gap) is now accepted at
classification **A** -- see §1, above, Lane G/§6, below, and
[ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `b1c78dc`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly, as did Lane G's own stated `PARTIAL, MATERIALLY CLOSED`
status and the exact gap description. Root-caused against every one of
the governing brief's own ten stderr/process-lifecycle diagnostic
questions before any fix. A bounded, continuous `BoundedStderrDrain`
(new, `playback/stderr_drain.py`) replaces the previously-unconditional
`stderr=subprocess.DEVNULL` on the three non-Camera-Node providers' own
long-running monitored processes, proven safe against a real
~4MB-stderr-flood subprocess (no deadlock, bounded memory, no blocked
frame delivery) and against ten repeated start/stop cycles (no thread
leak). RTSP ongoing classification reuses the exact, unmodified,
already-accepted setup-time vocabulary (`classify_rtsp_failure_text`,
renamed public from `_classify_probe_failure`); local USB/Windows
DirectShow gained new classifiers strictly bounded to real, reproducible
evidence gathered this milestone (real ffmpeg 6.1.1 V4L2 stderr against
this project's own Linux dev sandbox; real ffmpeg.exe 8.1.2 DirectShow
stderr gathered live against the project's own reference Windows dev
host), with an honest generic fallback everywhere real evidence ran out
-- no false precision invented for either provider, per the brief's own
explicit bar. Two independent hardcoded Camera-Node-only allowlists
(`_managed_camera_status`; `mark_monitoring_backoff_with_failure_code`)
that discarded any other provider's classified code were widened, not
duplicated; Camera Node's own separate mechanism is completely untouched.
Recovery-clears-stale-failure was re-verified correct for the new codes
against a real repository, with zero change to the pre-existing,
provider-agnostic clearing mechanism itself or to any retry/backoff
timing. 26 new tests, Tier 1 26/26, Tier 2 (20 files) 503 passed/11
xfailed/0 failed, Tier 3 (one full `scripts/verify_core.py` run) 5310
passed/3 skipped/23 deselected/11 xfailed/**0 failed** -- no bisection
needed. `ruff check`: zero new findings on every touched/new file,
confirmed via clean-baseline bisection. No schema change. Local USB/
Windows DirectShow hardware acceptance (device-busy, permission-on-real-
hardware, unsupported-format) and a real RTSP camera's own live auth/
codec failure remain genuinely untested -- honestly disclosed, not
claimed. Lane G moves to **MATERIALLY CLOSED / VALIDATION REMAINS** (§6,
below). This closure does **not** authorize the next Representative Field
Acceptance / Gate A session, Lane C work, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- authorization returns to the bold statement
immediately above, unchanged by this closure.

Login Rate-Limiting & Authentication Abuse Resistance v1 (directly
authorized outside this file, as a RELEASE-SECURITY milestone closing the
human-login rate-limiting gap the full remaining-roadmap reconciliation
pass itself had verified was still open) is now accepted at classification
**A** -- see §1, above, and
[login-rate-limiting-authentication-abuse-resistance-v1-report.md](login-rate-limiting-authentication-abuse-resistance-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `a846655`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly. `POST /api/auth/sign-in` previously had generic,
enumeration-safe failure behavior but no attempt counting, no delay, and no
throttling at all; pairing already had its own rate limiting
(`mockingbird_node.app`'s `_MAX_PAIR_ATTEMPTS`), human login did not. Fixed
with a small, dependency-free `LoginRateLimiter` (account- and source-keyed,
jointly evaluated, a short fixed delay ladder that plateaus at 60 seconds
forever -- no permanent lockout), deliberately in-memory only (resets on
restart/backup-restore, matching this codebase's own established precedent
for that boundary; a local-first appliance does not need persistent
lockout state, and persisting it would become its own DoS surface). The
outward HTTP contract is unchanged -- the identical generic `401` for
unknown user, wrong password, disabled user, and now throttled account/
source alike, proven by a direct response-equality regression test. No
session is ever created on a failed or throttled attempt; three new
bounded audit events reuse the existing audit-log mechanism with zero
schema change and no secret ever in their metadata. 31 new tests, plus
36 pre-existing identity tests re-confirmed passing unmodified. Tier 1 (67
tests): zero failures. Tier 2 (376 tests across 26 files spanning every
directly auth-adjacent file plus a broad, diverse cross-subsystem sample):
zero failures. Tier 3 deliberately not run -- the change is confined to
one repository method, one endpoint, and one new file with zero existing
importers, and Tier 2's own breadth is itself empirical confirmation of
that narrow blast radius. `ruff check`: zero new findings (the 57
pre-existing `product_repository.py` findings confirmed unrelated via a
direct clean-baseline bisection). No schema change. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, Lane G monitoring diagnostics, Lane C work, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- authorization returns to the bold statement
immediately above, unchanged by this closure.

Historical Species-Status ("New" vs. "Seen Before") Correctness v1
(directly authorized outside this file, as a release-critical correctness
milestone closing two reproduced, multiply-recurring `tests/test_place_
biodiversity_summary_repository.py` failures the global reconciliation pass
itself surfaced -- reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, and
[historical-species-status-new-seen-before-correctness-v1-report.md](historical-species-status-new-seen-before-correctness-v1-report.md)
for the full record. Confirmed the starting-state premise before starting
(branch `main`, accepted HEAD `98f1138`, schema v58, the seven preserved
untracked files present and untouched, no active worktree writer) --
matched exactly. Root-caused before fixing, per the governing brief's own
ten diagnostic questions: both failures trace to one test-fixture defect
(a hardcoded past `NOW` constant colliding with two intentionally
real-wall-clock-anchored "live view" HTTP routes -- `place_biodiversity_
summary`/`wildlife_journal_history`, neither of which accepts a way to
inject a test clock, by design), never to the shared canonical
`compute_species_historical_statuses`/`_historical_place_baseline_and_
species_statuses` computation itself, which was independently re-verified
correct against its own governing contracts and against every `now=`
-pinned assertion in the same test file, all already passing. Fixed with
the smallest correct change: one test file, zero production code, zero
schema change. Both reproduced failures independently proven RED pre-fix
and GREEN after; every required semantic case (first occurrence, subsequent
occurrence, correction to a new species, correction to a previously-seen
species, current-Visit self-exclusion, future-Visit non-retroactivity,
archived-Stream/Place isolation, unresolved-label exclusion, cross-endpoint
agreement) independently proven, two of them by new tests this milestone
added. Tier 1/2 (498 tests across every consumer of the shared
historical-status path): zero failures. Tier 3 (one full Core run): 5277
passed, **zero failed** -- the first zero-failure full Core checkpoint in
at least nine consecutive prior attempts (see §14, below). This closure
does **not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not edited
-- this milestone is a bounded test-correctness fix, not a roadmap-scope
change. No evidence surfaced that Lane C itself requires a separate
reconciliation pass beyond what §6 already records; its own remaining "New
/ Regular presentation" item is a distinct UX-presentation gap, untouched
by this purely computational-truth/test-correctness fix.

Release Licensing, Distribution & Third-Party Legal Closure v1 (directly
authorized outside this file, as a pre-release-decision/release-blocking
governance milestone -- Lane P plus the still-open BirdNET
commercial-adjacent posture in §2, above -- the highest-priority
independent milestone available while Gate A's own daylight-conditions
rerun (Lane R) stays separately blocked, confirmed via this milestone's
own hard sequencing guard before starting) is now accepted at
classification **B** -- see §1, above, Lane P/§2, and
[release-licensing-distribution-third-party-legal-closure-v1-report.md](release-licensing-distribution-third-party-legal-closure-v1-report.md)
for the full record. Resolved both engineering-resolvable items Lane P
had left open (FFmpeg's distribution posture -- never bundled, now a
durably-enforced guard, `verify_no_bundled_ffmpeg_binary` -- and a new
`THIRD_PARTY_NOTICES.md` shipping correct MIT license text for the two
production-redistributed models, MDv5a and BioCLIP-2, that previously
carried none), re-verified the pre-existing BirdNET-weight-exclusion
enforcement still works unchanged, found and fixed one real documentation
gap (the canonical user guide never mentioned the shipped, accepted
BirdNET/acoustic feature at all), and produced a complete owner decision
packet for the one item that genuinely cannot be resolved by engineering
means alone: MockingBird's own source-code license (MIT recommended, no
other engineering ambiguity blocking it). Classification **B**, not A,
because that one owner decision remains outstanding and remains a real
release blocker for the public launch itself -- see this milestone's own
report for the complete reasoning against self-selecting it. This closure
does **not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone -- see the bold
statement immediately above, unchanged by this closure.

Platform / Runtime Portability & Support Truth Closure v1 (directly
authorized outside this file, as a bounded, release-critical evidence/
documentation closure of Lane O -- the highest-priority independent
task available while Gate A's own daylight-conditions rerun stays
separately blocked) is now accepted at classification **A** -- see §1,
above, Lane O, §6, below, and
[platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md)
for the full record. Confirmed the sequencing premise before starting:
Lane O read as `PARTIAL -- RELEASE DECISION REQUIRED` and release-critical,
Lane R correctly still gated on daylight field conditions and unrelated,
and no higher-priority independent release-critical dependency blocked
Lane O -- the premise held, so the milestone proceeded rather than
stopping. Built a truthful, explicit support matrix across Host OS
(Windows validated; Linux structurally supported at the source/dev level,
no packaged release; macOS unverified, one path already honestly
unsupported), inference runtime (CPU: the accepted detector forbids it by
deliberate, tested design, zero fallback; NVIDIA CUDA validated on
Windows; Apple Silicon deferred; AMD unsupported), and Camera Node
(Raspberry Pi 4 validated reference hardware; genuinely hardware-agnostic
provider protocol; no non-Pi hardware release-tested) -- entirely by
reusing already-accepted evidence plus bounded, targeted code/doc
archaeology, with zero new platform support added, per the milestone's own
explicit non-goals. Found and fixed two narrow, reproduced capability-
overclaim defects in `python -m mockingbird doctor` (its
`SPECIES_IDENTIFICATION` and `GPU_CUDA` checks each silently omitted an
honest scope caveat their own underlying probes already had available),
each independently proven RED via `git stash` against the real pre-fix
code and GREEN after, with a new dedicated regression test;
`tests/test_doctor.py` (107 passed) and `tests/test_doctor_cli.py` (8
passed) confirmed via direct grep to be the complete blast radius; `ruff
check` clean; full Core correctly not run for this primarily evidence/
documentation closure, per the governing brief's own validation guidance.
Two further gaps were found and precisely disclosed rather than fixed,
since neither is reproduced against any real or currently-shipping path
(a Camera Node `Path.home()` fallback masked by installer convention; a
dead-code API-endpoint naming mismatch with zero frontend consumption).
Published the canonical, plain-language user-facing support matrix as a
new "Platform & hardware support" section in `docs/using-mockingbird.md`.
No schema change. Lane O is now reconciled to **closed** (§6, below) --
resolved by making support truth explicit, not by claiming any
unsupported hardware is supported. This closure does **not** authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does **not**
select a next development milestone -- see the bold statement immediately
above, unchanged by this closure.

Sustained-Activity Visit Admission Starvation & Stop-Finalization
Correctness v1 (directly authorized outside this file, as a
release-critical correctness milestone closing exactly the defect class
Representative Daylight Gate A Field Acceptance v4 found and disclosed,
below) is now accepted at classification **A** -- see §1, above, Lane R,
§6, below, and
[sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
for the full record. Both the continuous-activity starvation and the
stop-finalization questions the prior milestone left open are
independently root-caused, deterministically reproduced RED against the
real, unmodified pre-fix code, and fixed -- plus two further real,
narrow, evidence-cache-adjacent defects this milestone's own required
investigation found and closed along the way (see the report's own
"Root cause" section for the complete four-part account). This closure
does **not** authorize External Pre-Release Acceptance or Final Release
Hardening, and does **not** select a next development milestone -- see
the bold statement immediately above, unchanged by this closure.
`roadmap.md` was not edited: this milestone is a bounded correctness fix
confined to the Observation Engine admission/evidence-scoring stack, not
a roadmap-scope change, and per its own governing brief only
`release-execution-state.md` is updated on acceptance (accepted HEAD;
schema unchanged; latest accepted milestone; Gate A defect state;
validation state; exact daylight rerun requirement) -- the already
-closed Lanes M/N/Q are untouched. This closure does **not** itself close
Lane R/Gate A (no live field session ran, per this milestone's own
explicit non-goal) and does **not** authorize the next daylight session
by itself -- that remains its own separate authorization decision, per
the bold statement above.

Representative Daylight Gate A Field Acceptance v4 (directly authorized
outside this file, as a release-critical field-evidence milestone) is
now accepted at classification **A** -- see §1, above, Lane R, §6,
below, and
[representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
for the full record. This closure does **not** authorize External
Pre-Release Acceptance or Final Release Hardening, and does **not**
select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not
edited: this milestone is a bounded field-measurement session, not a
roadmap-scope change, and per its own governing brief only
`release-execution-state.md` is updated on acceptance (accepted HEAD;
schema; latest accepted milestone; Lane R/Gate A evidence state;
candidate-budget state; exact remaining dependency) -- the already-
closed Lanes M/N/Q are untouched. The real, previously-undocumented P0
this session found and precisely root-caused (sustained near-continuous
multi-subject activity can produce zero admitted Visits for an entire
live session -- see §1, above, and the report itself for the full
mechanism) is a genuine addition to Gate A's remaining-work picture, not
a milestone-invalidating problem with this session's own execution.

Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1
(directly authorized outside this file, as a bounded release-critical
acceptance milestone closing the two specific gaps Local Only / Privacy
Closure v1's own classification B left open, reconciled here at its own
closure) is now accepted at classification **A** -- see §1, above, Lane N,
§6, above, and
[native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md)
for the full record. Confirmed the starting-state discrepancy before
proceeding: this file's own text (post the prior milestone's own
reconciliation) already said Lane N "closed," while the governing brief
for this milestone stated -- correctly, per ChatGPT's actual acceptance
review of that same prior report -- that two material proofs remained
(native-Windows packaged runtime; assets-present MDv5a/BioCLIP-2 operation
under internet denial). Treated the brief's framing as authoritative,
proceeded to actually close both gaps with real evidence rather than
treating the discrepancy as a stop-and-report contradiction, per the
brief's own explicit resolution of it. Both gaps are now closed for real:
a fresh, disposable, no-skip-flags native-Windows packaged deployment
(never the operator's long-lived dev identity); a real, disposable,
process-level internet-denial mechanism (the only kind available without
an Administrator token in this environment, independently corroborated by
live OS-level connection accounting and by the same mechanism catching a
real browser's own unrelated background traffic); both production models
proven initializing and running real local inference at the exact
production code path, both before and after denial, with independently-
confirmed zero network activity; a real offline browser render; all 16
named core workflows exercised live, including a real backup and a real
review correction; both live optional-provider drills degrading
gracefully with no retry storm; and the camera-credential-at-rest question
resolved to a documented non-defect. Zero reproduced Local Only/privacy
defects were found across either milestone -- this milestone changed zero
production code, adding only its own report. This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. `roadmap.md` was not
edited -- this milestone is a bounded acceptance/correctness closure
confined to native-Windows/privacy verification, not a roadmap-scope
change.

Local Only / Privacy Closure v1 (directly authorized outside this file,
as a bounded release-critical privacy/product-correctness milestone,
reconciled here at its own closure) is now accepted at classification
**B** -- see §1, above, Lane N, §6, below, and
[local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)
for the full record. Confirmed the sequencing premise before starting
(Lane N still open/release-critical/independent; no higher-priority
independent release-critical dependency blocks it; Lane R/Gate A still
correctly gated on representative daylight conditions, unrelated). Proved
the Local Only contract with real evidence rather than code inspection
alone: a genuine OS-level, unprivileged network namespace
(`unshare --net --map-root-user`) hosting a fresh disposable instance
with no internet route at all (loopback confirmed working via a real
"connection refused," not merely "everything fails the same way") --
22 core authenticated API routes, the frontend document, a hashed asset,
Observation start/stop against the seeded demo Stream, a real local
backup, and two deliberate optional-provider-failure drills (weather,
iNaturalist taxonomy lookup, both explicitly enabled and forced
unreachable) all completed correctly with zero outbound connection
required, zero retry storm, zero mislabeled health. A fresh, separate,
live LAN-reachability check immediately afterward confirmed the same
sandbox that just proved zero internet dependency can still reach the
project's real reference Camera Node over LAN, directly evidencing
(rather than only asserting) the offline-vs-LAN-local distinction the
governing brief required. Zero reproduced Local Only/privacy defects
were found -- this milestone changed zero production code; its own new
test file (`tests/test_local_only_privacy.py`, 8 tests, self-verified via
call-count assertions on injected fake requesters) converts the live
proof into a standing, hermetic regression, including a trip-wire against
any future undisclosed telemetry/analytics dependency ever being
declared. Classification **B**, not A, because this session's own
runtime acceptance ran the Linux/WSL dev checkout rather than the
packaged native-Windows artifact end users receive, and exercised the
model-assets-absent path rather than assets-present -- both named
explicitly in the report's own "Remaining risks," not because any defect
was found or is suspected. Lane N is now reconciled to **closed** (§6,
below): the contract is proven and every reproduced-defect requirement is
vacuously satisfied by real runtime acceptance (not static inspection
alone), matching the governing brief's own stated precondition for
closing it on that basis. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone -- see the bold statement immediately above,
unchanged by this closure. `roadmap.md` was not edited -- this milestone
is a bounded acceptance/correctness closure confined to privacy/network
-dependency verification, not a roadmap-scope change.

Retention Correctness & Bounded Cleanup Closure v1 (directly authorized
outside this file, as a small, bounded, release-critical follow-up to
Storage / Retention / Disk-Pressure & Recovery Closure v1, reconciled
here at its own closure) is now accepted at classification **A** -- see
§1, above, Lane M, §6, below, and
[retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md)
for the full record. Closes all three reproduced retention defects
Storage / Retention / Disk-Pressure & Recovery Closure v1 disclosed and
deliberately left unfixed under its own bounded time budget (imported/
folder-imported media over-retention against its own documented
contract; a `"staging"`-batch purge-path gap; a cosmetically-misnamed,
actually-unbounded `storage_cleanup_history` constant) -- see §1, above,
for the complete accounting of each fix, its RED/GREEN proof, and full
Tier 1/2/3 validation (zero regressions attributable to this milestone,
directly confirmed rather than assumed). Lane M is now reconciled to
**closed** (§6, below): the retention contract this file's own prior
entry called "materially closed, not fully closed" pending exactly these
three fixes is no longer ambiguous -- each of the five governing
questions the imported-media contract raised (which imported media is
retainable indefinitely vs. eligible under ordinary retention; whether
Reviewed truth implies indefinite evidence preservation or only product
truth preservation; whether user-imported originals are distinguished
from derived evidence in the data model; whether the current behavior was
explicitly contradicted by existing docs/tests) was answered directly
from code, traced and cited precisely, not inferred or guessed, and each
fix was proven RED before GREEN against a dedicated, deterministic
reproducer before being applied. The one remaining, already-disclosed,
structural storage gap -- no code anywhere scans the media directory and
cross-references it against the DB, so a file with no DB owner is
permanently invisible to every existing integrity/retention check -- is
real, bounded, low-materiality (per the prior closure's own
investigation), unaffected by this milestone, and was deliberately not
reopened, per this milestone's own governing brief; it remains a
reasonable candidate for a future bounded "sampled orphan sweep," not a
reason to withhold closing Lane M over these three specific, now-closed
defects. This closure does **not** authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone -- see the bold statement immediately above, unchanged by this
closure. `roadmap.md` was not edited -- this milestone is a bounded
correctness closure confined to retention/import cleanup code, not a
roadmap-scope change.

Storage / Retention / Disk-Pressure & Recovery Closure v1 (directly
authorized outside this file, as a bounded release-critical storage/
reliability milestone, reconciled here at its own closure) is now accepted
at classification **B** -- see §1, above, Lane M, §6, below, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)
for the full record. Determines, with real directly-measured evidence, the
cause of the Windows Host free-space decline this file's own 2026-08-28
Lane R entry (below) first surfaced and left open: **disposition B**
(MockingBird development/test-artifact accumulation -- `deploy_windows_
dev.py`'s own never-garbage-collected runtime/model cache, 38.5GB, the
single largest consumer found anywhere in the investigation, plus the
field-acceptance recorder's own real output directory, 11.5GB -- together
accounting for roughly 72% of the exact dated decline window; neither path
is reachable by a real end-user installation). The dominant contributor is
fixed (`--gc-cache`, applied live against the real Windows dev host). This
closure classifies **B**, not A, because the remaining ~28% of the exact
decline window was not individually attributed to a single further cause
(disclosed honestly rather than forced to round), and because three real,
precisely-disclosed, safe-direction product-side retention findings
(imported-media over-retention against its own documented contract; a
`"staging"`-batch purge-path gap; a cosmetically-misnamed, slowly-
unbounded `storage_cleanup_history` constant) were deliberately left
disclosed rather than fixed under this milestone's own bounded time
budget, each requiring either new test coverage this milestone did not
build or a change to the highest-stakes retention-eligibility code this
milestone judged not warranted without it. This closure does **not**
itself authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone. `roadmap.md` was not
edited -- this milestone is a bounded investigation/dependency-tooling fix,
not a roadmap-scope change.

Non-Interactive Field Acceptance Authentication & Session Access v1
(directly authorized outside this file, as a bounded release-critical
security/correctness dependency milestone -- not a product capability,
reconciled here at its own closure) is now accepted at classification
**A** -- see §1, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record. Closes the recurring field-acceptance authentication
blocker Lane R's own three most recent attempts (2026-08-25, 2026-08-26,
2026-08-28, all recorded below) hit, without an authentication bypass,
without the operator's personal credentials, and without weakening
production security -- see §1, above, for the complete accounting
(mechanism, schema change, real live proof against a disposable isolated
instance, full Tier 1/2/3 validation). This closure does **not** itself
authorize the next Representative Field Acceptance / Gate A session --
that session is still gated on the same global product-roadmap
reconciliation this file's own governing phase label protects (see
"CURRENT PHASE," above) -- and does **not** authorize External Pre-Release
Acceptance or Final Release Hardening. The next daylight Gate A session,
whenever separately authorized, needs exactly one new step before it
starts: an Administrator (the operator) runs, once, against the real
instance, `python scripts/manage_field_acceptance_credential.py create`,
then exports the printed token as `MOCKINGBIRD_ACCEPTANCE_TOKEN` -- no
further auth archaeology should be needed for that session. `roadmap.md`
was not edited -- this milestone is a bounded dependency fix, not a
roadmap-scope change.

Representative Daylight Field Acceptance & Gate A Evidence v2 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **B** -- see §6 Lane R, below, and
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md)
for the full record. Accepted HEAD is unchanged (`80e1bb3`) -- this
milestone touched zero product/perception/admission/Visit/evidence/
classification/schema code; it only ran and cleanly stopped a fresh
Windows dev deployment of the already-accepted build for verification.
This does **not** close Lane R/Gate A: no live field session ran. Unlike
the two immediately-preceding attempts, every environmental and
infrastructure precondition (daylight, reference Camera Node health, GPU/
detector health, storage headroom, acceptance-recorder readiness) was
independently re-confirmed healthy this time -- the sole remaining
blocker, isolated more precisely than either prior attempt could isolate
it, is the identical authentication precondition first found 2026-08-25
(real sign-in required on every session-relevant endpoint, empirically
re-confirmed today via `401` on `GET /api/streams`/`GET /api/visits`
against the freshly redeployed accepted HEAD; no credentials exist;
standing user policy against asking again or routing around it via a
disposable instance for this class of milestone). Gate A's evidence body
is unchanged -- still exactly the two real 2026-08-19/2026-08-20 daylight
cohorts, for the third consecutive milestone attempt. No release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

Whole-Product UI / Accessibility / Performance Closure v1 (directly
authorized outside this file, reconciled here at its own closure) is now
accepted at classification **A** -- see §1, above, Lane Q, §6, below, and
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the full record. This closes Lane Q as an integrated pass -- the
whole-product responsive/accessibility/performance/multi-camera/error-
recovery/acoustic-status evaluation this file's own Lane Q text had been
waiting on since it was first named. It does **not** authorize Lane R,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone -- see the bold statement
immediately above, unchanged by this closure. Do NOT automatically
authorize, by adjacency to this closure: a `reviewed-product-loop.spec.ts`
rewrite (real, disclosed, precisely diagnosed as test-suite-only
staleness this milestone -- not a live product defect, not urgent); a
keyboard-driven Zone-polygon-drawing editor (real, disclosed, pre-
existing, optional/advanced-feature scope); the larger-than-previously-
documented dead-CSS cleanup or the narrow raw-exception-text hardening
(both real, disclosed P2 items, neither automatically the next milestone
by adjacency).

One-Release Roadmap & Scheduler Reconciliation v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- a documentation/state-governance milestone,
touching zero product/test/schema code. It reconciles this file and
`roadmap.md` to one coherent release doctrine: MockingBird has one public
release; there is no public "v0.1" product stage, no beta product
release, and no separate before-v1.0 roadmap phase; External Pre-Release
Acceptance (roadmap.md's Gate G, renamed from "External Beta Acceptance")
and internal release-candidate builds remain allowed as pre-launch
validation/engineering mechanics, never a separate product stage; Final
Release Hardening (Lane S, above) is readiness-triggered, not
version-number-triggered. See §1, above, and
[one-release-roadmap-scheduler-reconciliation-v1-report.md](one-release-roadmap-scheduler-reconciliation-v1-report.md)
for the complete accounting, including confirmation that no lane, gate, or
roadmap capability was added, removed, or promoted by this pass, and every
dated historical milestone title/decision label that happened to use
"v0.1"/"beta" vocabulary at the time was left verbatim. This closure does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** select a next development milestone --
see the bold statement immediately above, unchanged by this closure.

Camera Node Upgrade & Compatibility Recovery v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, Lane L, §6, below, and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md)
for the full record, including two real defects found and fixed live
during real reference-Pi acceptance (a universal transport-path crash
under the already-accepted `ProtectHome=true` hardening, and two
automatic-recovery gaps) and one honestly-disclosed remaining reservation
(`rollback()` does not restore an already-changed systemd unit template).
This closes Lane L's one specifically-named remaining gap; it does
**not** authorize Lane R, External Pre-Release Acceptance, or Final
Release Hardening, and does **not** reopen any other part of the
already-accepted Camera Node install/reboot/reprovision/replacement
work.

Representative Multi-Camera Field Acceptance & Release-Budget Evidence v1
(directly authorized outside this file, reconciled here at its own
closure) is now accepted at classification **B** -- see §1, above, and
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md)
for the full record. This does **not** close Lane R/Gate A -- no live
field session ran (environmental conditions, not a product defect; see
Lane R, §6) -- and does **not** authorize a next milestone by itself; it
found and fixed one narrow, unrelated release-engineering defect (a
Windows dependency-pin gap) while re-verifying execution-readiness for
the next daylight session.

Concurrent Candidate Visit Persistence Reliability v1 (directly authorized
outside this file, reconciled here at its own closure) is now accepted at
classification **A** -- see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md)
for the full record. This closes the one specific, bounded item named
below (the lost-candidate-Visit concurrent-write reliability gap); it does
**not** reopen or advance any other part of Multi-Camera Place Experience
v2's own remaining scope.

Multi-Camera Place Experience v2 (directly authorized outside this file,
reconciled here at its own closure -- see §16) remains accepted at
classification **B** -- see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
and §1/§6 Lane F, above/below, for the full record. Do NOT automatically
authorize, by adjacency to this closure: notification-level (Calm
Attention) cross-camera grouping; Place Story wildlife-event source
attribution; camera-filter UI consolidation; multi-camera Place Feature
linking; or broad multi-site -- each individually real and recorded in the
report's "Remaining major PRODUCT opportunities," none automatically the
next milestone by adjacency. (The one item this same list previously named
-- "a dedicated follow-on investigation into the real, disclosed occasional
lost-candidate-Visit concurrent-write reliability gap" -- is no longer an
open item: Concurrent Candidate Visit Persistence Reliability v1, above,
is exactly that dedicated investigation, and it reached a proven, validated
fix, not merely an investigation.)

Ecological Interoperability & Submission Workflows v1 (directly authorized
outside this file, reconciled here at its own closure -- see §16) is now
accepted at classification **B** (a real, working, submission-ready
iNaturalist workflow proven end to end by an executable 12-Visit
product-shaped scenario, plus a bounded additive Darwin Core export; eBird
and direct GBIF publication both honestly, evidence-backed deferred rather
than built -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)).
Calm Attention & Notifications v1 (directly authorized outside this file,
reconciled here at its own closure -- see §16) is now accepted at
classification **B** (a real canonical attention-selection layer composed
entirely over already-accepted facts, genuine semantic-dedup fixes found by
tests, reused health/storage debounce, new per-user preferences and quiet
hours, foreground-only browser notifications with Web Push deliberately
evaluated and deferred, and a real executable product-shaped quiet-week
proof -- see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)).
Mobile & Remote Experience v1 remains accepted at classification **B**
(strong mobile experience and a clear secure remote posture with bounded
external-network/PWA gaps -- see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)).
That milestone also closed, as its own bounded Phase 0, the
`place_change_summary.py`/`_presence_status` threshold gap the Place
Story & Seasonal Timeline v1 report (below) had recommended as future
work -- that item is now resolved, not still outstanding.
Place Story & Seasonal Timeline v1 remains accepted at classification
**B** (major useful capability, bounded history/story gaps -- see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)).
Place Features & Habitat Change v2 remains accepted at classification
**B** (major useful capability, bounded feature/data-model maturity
gaps -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)).
Environmental Context v2 remains accepted at classification **B** (major
useful capability, bounded provider/statistical/UI limitations -- see
[environmental-context-v2-report.md](environmental-context-v2-report.md)).
Place / Yard Intelligence v2 remains accepted at classification **B**
(major useful capability, bounded maturity gaps -- see
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)).
Camera / Source Experience & First-Hour Setup Closure v1 remains accepted
and closed at classification **C** (usable, bounded further closure
remains -- see Lane G, §6). No new implementation milestone is currently
authorized. The next milestone will be selected only after the governing
external process verifies this execution state against the complete
remaining release queue, the remaining Calm Attention & Notifications
opportunities (Web Push for a genuinely closed-browser interruption,
deliberately deferred; detector/model-unavailable Observatory Health
attention; per-user, not global, read/dismiss state; precise per-taxon/
per-Feature Place Story deep links; a live attention-sync diagnostics
surface -- see that report's "Remaining major PRODUCT opportunities"), the
remaining Mobile & Remote Experience product
opportunities (progressive disclosure for the dense Visit/Stream/Settings
pages; a genuine pre-existing `ReviewQueuePage` `product_category`/
"animals"-tab gap, found and documented, not fixed; no login rate-
limiting, a real pre-existing gap whose relevance this milestone's own
expanded network reachability directly heightens; no live external-
overlay-network (Tailscale/WireGuard) validation was possible from this
sandbox -- see the Mobile & Remote Experience v1 report's "Remaining
major PRODUCT opportunities"), the remaining Place Story product
opportunities (period summaries -- deferred on a measured performance
cost, not simply unattempted; environmental-context/weather caveats on a
before/after insight; a dedicated taxon/Feature story page; representative
imagery on Story cards), the remaining Place Features & Habitat Change
product opportunities (composing environmental-context/weather caveats
onto a before/after result, multi-camera Feature linking, representative
evidence in Feature detail, a ranked feature-comparison view -- see the
Place Features & Habitat Change v2 report), the remaining Place/Yard
Intelligence product opportunities (seasonality maturation against real
history, a `source_quality_signals` UI surface -- the habitat before/
after change-event data model itself is now closed by that milestone),
**and** the remaining Environmental Context product opportunities
(deeper historical backfill via Open-Meteo's archive/ERA5 endpoint, wind/
cloud-cover statistical associations, a dedicated diagnostics/Explore-page
surface for weather -- see the Environmental Context v2 report). Do not
choose the next milestone by adjacency to this one.

Do NOT automatically authorize:

- a managed/fleet Camera Node updater, unattended/automatic upgrade
  scheduling, remote-triggered updates, artifact signing/PKI beyond
  checksums, or a graduated ("compatible older") wire-protocol tier beyond
  the Host's own existing exact-match gate, merely by adjacency to Camera
  Node Upgrade & Compatibility Recovery v1's closure -- each explicitly
  out of that milestone's own scope, none automatically the next milestone;
- a standalone follow-on campaign to close the two items Camera Node
  Upgrade & Compatibility Recovery v1 left honestly disclosed (`rollback()`
  not restoring an already-changed systemd unit template; its own
  directory swap's narrower residual crash-window gap) -- both real and
  recorded, neither automatically the next milestone by adjacency unless a
  concrete recurrence is found;
- live, authenticated iNaturalist OAuth submission, or any eBird workflow
  of any kind, merely to close Ecological Interoperability & Submission
  Workflows v1's own deliberately-deferred external-authorization boundary
  -- see that report for the full evidence (eBird's own current policy
  conflict; no secure server-side credential-storage pattern exists yet)
  this decision rests on;
- direct GBIF publication as a standalone follow-on -- see that report's
  destination research for why this remains institutional, not a
  backyard-user workflow;
- ecological-submission media-byte inclusion, or a single-Visit deep-link
  pre-selection on the Ecological Destinations page, as a standalone
  follow-on campaign -- each individually real and recorded, neither
  automatically the next milestone by adjacency;
- Remote Field Productization;
- standalone Web Push (VAPID/subscription persistence, a genuine outbound
  call to a third-party push service) merely to close Calm Attention &
  Notifications v1's own deliberately-deferred Phase 22 Decision B gap --
  see that report for the full local-first/privacy reasoning this decision
  rests on;
- a Review Queue product_category/"animals"-tab fix, per-user read/dismiss
  state, or precise per-taxon/Feature Place Story deep links as a
  standalone follow-on campaign -- each individually real and recorded in
  the Calm Attention & Notifications v1 report, none automatically the
  next milestone by adjacency;
- further Mobile/PWA/remote-access work as a standalone follow-on
  campaign -- specifically: progressive disclosure for the dense Visit/
  Stream/Settings pages, the `ReviewQueuePage` `product_category`/
  "animals"-tab fix, login rate-limiting, or a live external-overlay-
  network acceptance pass -- each individually real and recorded, none
  automatically the next milestone by adjacency;
- Local Species/Taxon Prior;
- another classifier benchmark;
- Provider Integrations;
- a second weather provider or user-facing provider choice;
- Open-Meteo archive/ERA5 deep historical backfill;
- a Feature/Zone multi-camera join table;
- Place Story period summaries, weather-caveat composition, or dedicated
  taxon/Feature story pages, as a standalone follow-on campaign;
- Land Management / Agriculture as a separate campaign;
- notification-level (Calm Attention) cross-camera health grouping, Place
  Story wildlife-event source attribution, or camera-filter UI
  consolidation as standalone follow-on campaigns -- each individually
  real and recorded in the Multi-Camera Place Experience v2 report, none
  automatically the next milestone by adjacency. (The lost-candidate-Visit
  concurrent-write reliability gap that report also found, root-caused,
  and deliberately did not fix is **no longer on this list** -- Concurrent
  Candidate Visit Persistence Reliability v1, see §1, closed it at
  classification A.);
- broad multi-site, merely because single-Place multi-camera work just
  closed;
- final Release Hardening.

## 4. Product/release guardrails

MockingBird is:

- local-first;
- hardware-agnostic;
- nature-first rather than surveillance-first;
- bird-first but wildlife-native;
- evidence-backed;
- Place-centered;
- cloud-optional;
- human-correctable;
- abstention-friendly.

Canonical epistemic classes: **Measured**, **Inferred**, **Reviewed**.

Human correction is authoritative. Model inference cannot silently become
reviewed truth.

Raspberry Pi is reference Camera Node hardware, not product identity.
Native Windows remains the first end-user Host acceptance target.
WSL/Linux development success does not equal native-Windows product
acceptance.

Privacy Zones currently mean trigger-level exclusion, not guaranteed pixel
redaction of all retained frames unless future code explicitly implements
that.

User data is not the primary monetization strategy. Core functionality
must remain complete under Local Only privacy.

## 5. Frozen / substantially accepted lanes

Summarized without milestone archaeology; see `roadmap.md` and the linked
accepted-milestone docs for detail if a future task genuinely needs it.

**Observation / Reviewed Truth.** Accepted foundations include Visit →
Evidence → Review → Observation; review/correction/revision; actor
attribution; evidence lineage; Today/history truth.

**Perception / Admission.** Accepted: MDv5a production detector;
small/far-bird work; ambiguous-boundary/admission fixes; per-Stream Visit
authority; evidence-cache correction; scene-confusor suppression;
perception replay; multi-subject Visit foundations.

**Site-Specific Learning.** Accepted and frozen. Reviewed-negative
scene-confusor adaptation accumulates/evaluates reviewed evidence, is
production-disabled by default, and requires explicit per-Stream
enablement for production effect. Do not automatically build Local Taxon
Prior or calibration on top of this.

**Species Classification.** Accepted and frozen: BioCLIP-2 stays
production; BioCLIP 2.5 rejected; SpeciesNet not promoted.

**Broader Wildlife.** Accepted structurally. Non-bird review/history/
product semantics work. Automatic mammal species identification remains
limited.

**Identity / Multi-User.** Accepted: Viewer / Reviewer / Administrator;
server-side sessions; authorization; actor attribution; audit; review
concurrency; backup/restore.

**Environmental Context.** Accepted; extended, not frozen -- Environmental
Context v2 (2026-08-25) added the first general weather provider
(Open-Meteo) on top of the accepted solar/daylight foundation: eight
provider-neutral metrics, always `information_class="inferred"`; a
second, independent `weather_enabled` opt-in (schema v53 -> v54) gating
every outbound network call separately from the existing coordinate
setting; bounded lazy caching; Place-relative temperature and wet/dry
precipitation associations composed onto the existing `conditional_
association` primitive alongside `habitat_associations`. See
[environmental-context-v2-report.md](environmental-context-v2-report.md).
Substantial product-roadmap opportunity remains (deeper historical
backfill via the archive/ERA5 endpoint, wind/cloud-cover statistical
associations, a dedicated diagnostics/Explore-page surface); do not treat
this lane as closed.

**Habitat & Phenology.** Accepted/frozen.

**Biodiversity & Place Intelligence.** Accepted; extended, not frozen --
Place / Yard Intelligence v2 (2026-08-25) added regularity narrative,
seasonal pattern, temporal pattern, per-Source activity/quality, and a
weekly digest on top of the already-accepted foundation. Place Features &
Habitat Change v2 (2026-08-25, same day) closed that milestone's own
recorded "habitat before/after change-event data model" gap: a durable
Place Feature entity, a Reviewed change-event timeline, and a before/after
comparison engine built on pure reuse of the existing `conditional_
association` primitive -- see
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md).
Place Story & Seasonal Timeline v1 (2026-08-25, same day) composes all of
the above -- plus Reviewed phenology observations and Reviewed Feature
change events -- into one Place-wide, dated, filterable, correction-safe
timeline (`GET /api/place/story`), no new schema; see
[place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
for the full record, including a genuine previously-undiscovered gap
found in `place_change_summary.py`'s own already-accepted threshold logic
(worked around locally, not patched at its source -- see that report's
"Truth / provenance"). Substantial product-roadmap opportunity still
remains (year-over-year seasonality; environmental-context/weather
caveats not yet composed onto a before/after result or a Story insight;
multi-camera Feature linking; a ranked feature-comparison view; Place
Story period summaries; a dedicated taxon/Feature story page;
representative imagery on Story cards -- see that report's and
[place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)'s
and
[place-yard-intelligence-v2-report.md](place-yard-intelligence-v2-report.md)'s
respective "Remaining major PRODUCT opportunities"); do not treat this
lane as closed.

**Camera / Acquisition Foundations.** Substantial accepted work: native
Camera Node path; ONVIF; RTSP/RTSPS; offline/recorded ingest; camera-trap
ingest; provider-neutral Source/Stream architecture. First-hour product
experience materially closed (Add Camera preview, credential honesty) --
see Lane G.

**Diagnostics / Storage / Recovery Foundations.** Substantial accepted
work: health/diagnostics; Doctor/support concepts; storage health;
retention; backup/restore; recovery. Final integrated product acceptance
remains open (see Lane R, below).

**Research / Conservation.** Substantial accepted work: conservation
reporting; effort/coverage; research-safe eligibility/export; Camtrap DP;
Darwin Core Occurrence-core export (2026-08-25, additive to Camtrap DP, not
redundant with it -- see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md));
contributor/research provenance.

## 6. Global remaining execution queue

This is the most important section. Lanes are not removed merely because
they are not next.

**Four release-shape categories.** Every lane below already sorts into one
of four categories; renaming the release model (§7, above) does not change
which lanes are release-critical, deferred, or later -- it only fixes the
words used to describe them:

- **A. Release-critical** -- must be complete/credible before the one
  public launch. Lanes marked **RELEASE-CRITICAL** below carry this:
  representative field correctness/whole-product acceptance (Lane R),
  camera/source golden path (Lane G), storage/retention/recovery (Lane M),
  Local Only/privacy (Lane N), platform/runtime support truth (Lane O),
  release/distribution closure (Lane P), accessibility/performance (Lane
  Q), appliance/update/recovery (Lane L) -- plus, as the internal gates
  above become credible, External Pre-Release Acceptance and Final
  Release Hardening themselves (Lane S, below; roadmap.md Gates F-G).
- **B. Pre-release decisions** -- decisions required before launch, not
  necessarily implementation milestones: the codebase `LICENSE` (Lane P;
  full ffmpeg distribution licensing, the item this line previously named
  alongside it, is now resolved -- see Lane P, below); the still-open
  BirdNET commercial-adjacent legal posture (§2, above); platform-support
  declarations (Lane O, resolved -- see Lane O, below); Ecosystem/Provider
  Integrations scope (Lane K, "OPEN DECISION"); any other genuine
  unresolved release decision as it surfaces.
- **C. After release** -- real product development explicitly not
  required for launch, kept so it is not lost: complete remote/
  intermittent-WAN/LTE, solar/battery, custom CM4/CM5 (Lane B, and §8,
  below); research-grade remote-field acceptance; broad multi-site (Lane
  F's own explicitly-deferred remainder); native mobile (Lane E's own
  explicitly-out-of-scope remainder); advanced acoustic analytics (Lane
  A's own remaining bounded follow-up); mature automatic mammal species
  identification (Lane I).
- **D. Later / evidence-driven** -- the long-range, demand-driven queue in
  §9, below: GenICam, GigE Vision, USB3 Vision, radiometric thermal,
  specialized industrial cameras, individual-animal recognition,
  population estimates, behavior prediction, causal ecological modeling,
  large cloud/fleet infrastructure.

This is a navigational grouping over the existing lettered lanes (A-S), not
a new or renumbered lane system: no lane is removed, renamed, or promoted
between categories by this grouping, and each lane's own status text below
remains authoritative over this summary.

### A. Acoustic / BirdNET Productization

**Status:** ACCEPTED -- RELEASE-READY OPTIONAL.

Remaining bounded follow-up only: frontend acoustic health/status; longer
field soak; physical unplug/replug; natural wild-bird field evidence. Do
not schedule another acoustic architecture milestone automatically.

### B. Remote / Intermittent-WAN Field Productization

**Status:** PARTIAL -- AFTER RELEASE UNLESS A NEW CORE DEPENDENCY
APPEARS.

Existing foundation includes substantial spool; store-and-forward;
transport; retry; Host consume-to-evidence behavior; diagnostics.

Remaining: real LTE/carrier acceptance; real remote Pi deployment;
bandwidth behavior; resume granularity; extended outages; unattended
recovery; remote operator experience; solar/battery/power reality.

Remote LTE/solar/custom CM4/CM5 field deployment is **not** a release
blocker.

### C. Everyday Product / Discovery UX

**Status:** MATERIALLY DELIVERED / NO KNOWN DEV REMAINS. Lane C Sparse-
State Honesty & First-Hour Narrative Closure v1 (2026-08-30) closed the
two remaining bounded DEV gaps a prior accepted read-only Lane C
reconciliation had left open; see
[lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md](lane-c-sparse-state-honesty-first-hour-narrative-closure-v1-report.md).
Classification **A**.

Delivered, across the already-accepted milestones behind each (this
section's own prose had never been reconciled as each landed piecemeal
under Gate C naming rather than explicit "Lane C" naming -- corrected
here, not re-implemented): Best Moments and report-first hierarchy (Gate C
Daily Place Report v1, Gate C Representative Species Evidence v1); calm
daily summary (Gate C Calm Daily Digest v1); New / Regular presentation
(Gate C Historical Baseline Maturity v1, Historical Species-Status
Correctness v1); unknown/unresolved handling (Gate C Per-Species Zone +
Time Pattern Intelligence v1 and the broader review-optional/unresolved-
label design); understandable suggestion explanations (Same-Frame Species
Evidence v1, Visit Same-Frame Classifier Evidence Visibility v1);
mostly-invisible review (the shipped review-optional design; Whole-Product
UI / Accessibility / Performance Closure v1's Review Queue fix). Delivered
by this milestone: sparse/no-wildlife honesty under primary detector/GPU/
model failure (a Camera Node Stream's Dashboard/`ProductHealth` failure
text no longer lets a stale "paired and configured" success message mask
a real detector/GPU/model failure); a coherent first-hour narrative in
onboarding (`OnboardingWizard.tsx` no longer frames Review Queue as the
normal destination for ordinary discovery -- Today/Bird Log are, matching
the shipped review-optional design).

Not claimed complete by this closure: future taxonomy content, a Dashboard
layout change, or general UI perfection. Do not turn this lane into a
giant redesign; do not reopen any of the delivered items above without a
directly reproduced, same-root-cause dependency.

### D. Calm Notifications

**Status:** MATERIALLY DELIVERED -- Calm Attention & Notifications v1
(2026-08-25) closed this lane's decision; see
[calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md).
Classification **B**.

Delivered: one canonical attention-selection layer over already-accepted
facts (Place Story, the daily/weekly digest, the existing review/monitoring/
storage/journal alert system); a small user-centered taxonomy (Discovery/
Insight/Needs Help/Observatory Health) and explicit urgency (immediate/
digest/in-app-only), never raw internal severity/error vocabulary; genuine
semantic deduplication (two real double-notification anti-patterns found
and fixed by tests); reused, not reinvented, health/storage debounce; a
daily/weekly digest notification reusing the existing digest computation
unmodified, suppressed when there is genuinely nothing meaningful; per-user
notification preferences (four category toggles + quiet hours, evaluated in
the viewer's own browser-local time); foreground-only browser-notification
delivery (Web Push explicitly evaluated and deferred -- Decision B, no
cloud push infrastructure added, matching this lane's own standing
instruction); an extended Attention Center and a calm "N things worth
noticing" line on Today; a real, executable product-shaped quiet-week test
proving the whole week stays calm. Schema 55 -> 56 (one additive per-user
preferences table).

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": Web Push for a genuinely closed-browser
interruption; detector/model-unavailable Observatory Health attention;
per-user (not global) read/dismiss state; precise per-taxon/Feature Place
Story deep links (today scoped to a category group); a live attention-sync
diagnostics surface.

### E. Mobile / Remote UX

**Status:** PARTIAL, MATERIALLY ADVANCED -- Mobile & Remote Experience v1
(2026-08-25) closed the core decision this lane was waiting on; see
[mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md).
Classification **B**.

Delivered: a verified (10 real automated phone-width screenshots, zero
overflow) responsive navigation fix -- top bar + off-canvas drawer +
4-item bottom nav, replacing a sidebar that previously stacked in full
above every page below 980px; a bounded, safety-reasoned installable PWA
shell (manifest, icons, a service worker that only ever caches Vite's own
immutable hashed assets, never navigation/API/data -- no offline data
claim made anywhere); LAN access made discoverable (`GET /api/product/
connection` + a Settings card, with a corrected, no-longer-stale
`--allow-network` help string); a private-overlay-network
(Tailscale-compatible) posture chosen and documented as the supported
away-from-home path, with direct public-internet exposure and a cloud
relay explicitly, plainly documented as unsupported/not-built; new CORS
regression coverage. Native mobile remains explicitly out of scope,
unchanged.

Remaining, not closed by this pass (see the report's "Remaining major
PRODUCT opportunities" for the full record): progressive disclosure for
the dense Visit/Stream/Settings pages; a pre-existing `ReviewQueuePage`
`product_category` gap (found, documented, not fixed -- independently
reproduced against an unmodified existing e2e spec); no login rate-
limiting (pre-existing, real, and directly more relevant now that this
lane increased network reachability); no live external-overlay-network
(Tailscale/WireGuard) acceptance was possible from this sandbox --
validated structurally only. Do not equate this closure with a finished,
fully-polished mobile product, and do not automatically authorize a
follow-on Mobile/PWA campaign by adjacency -- see §3.

### F. Multi-Camera / Multi-Site

**Status:** MATERIALLY ADVANCED -- Multi-Camera Place Experience v2
(2026-08-26) closed this lane's integrated-acceptance decision; see
[multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md).
Classification **B**.

Camera/Source + Multi-Camera Maturity v1 (2026-08-23) had already built the
real foundation this lane's own text below was actually waiting on
(cross-camera duplicate-encounter association, Area vocabulary, provider
compatibility, health coherence) -- that milestone's own report was
missing (only a `-contract.md` existed, no `-report.md`), which is why
this lane's status had not been updated to reflect it; corrected here.
Delivered this milestone: a real, previously-hidden defect found and fixed
with principled nuance (an archived camera's history was unreachable from
every discovery surface, contradicting this codebase's own documented
archive-only-preserves-history doctrine; the fix deliberately preserves
already-tested current-active-only *defaults* on Bird Log/Wildlife
Insights/Biodiversity while making that real history reachable by explicit
camera filter and by period-scoped reports); Today surfacing its own
already-computed per-camera activity/evidence-source facts for the first
time; a Bird Log camera filter reaching the overview list, not only the
per-species drilldown; a real coverage-union fix for Zone Insights'
Place-wide aggregate (was a naive per-camera-hours sum); Dashboard
distinguishing "some cameras need attention" from "every armed camera
needs attention"; a real, measured (2-camera and 4-camera-asymmetric,
genuinely concurrent real-thread) admission/assembly-layer concurrency
proof with zero cross-Stream contamination and no starvation found; a
comprehensive, real, executable product-shaped scenario proving the whole
chain -- identity, coverage, overlap dedup, health, correction propagation
-- coheres end to end. Schema unchanged (v57 -> v57): every fix is a query-
scope correction or an additive field on an already-derived response
object.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": notification-level (Calm Attention) cross-camera
grouping beyond the Dashboard status-view fix; Place Story wildlife-event
source attribution (the field exists, populating it needs restructuring a
shared SQL-aggregation layer, not a field-threading exercise); consolidating
at least 6 independently-implemented camera-filter UI controls into one
canonical component; multi-camera Place Feature linking; real GPU/CUDA-
driver-level concurrent-inference measurement (needs real hardware this
sandbox lacks); a multi-hour concurrent soak beyond the single-pass
measured proof; the pre-existing, disclosed 2-Stream cap on the separate
legacy motion pipeline (RTSP/USB/local providers, not the modern
Observation Engine's own Camera Node path).

**Reliability lane status (Concurrent Candidate Visit Persistence
Reliability v1, same-day follow-on):** this lane's one item touching the
critical Visit write path -- occasional silent loss of an admitted
candidate under real concurrent multi-Stream SQLite writes -- is now
**CLOSED** at classification **A**; see §1, above, and
[concurrent-candidate-visit-persistence-reliability-v1-report.md](concurrent-candidate-visit-persistence-reliability-v1-report.md).
Every other item in the "Remaining, not closed by this pass" list directly
above is unaffected and still open.

True multi-site remains a separate product/architecture decision. Do not
silently make it release scope, and do not self-authorize it by adjacency
to this lane's closure.

### G. Camera / Source Experience

**Status:** MATERIALLY CLOSED / VALIDATION REMAINS -- RELEASE-CRITICAL.
Camera / Source Experience & First-Hour Setup Closure v1 (2026-08-25)
fixed two real P0 first-hour gaps and two P1s; see
[camera-source-experience-v1-report.md](camera-source-experience-v1-report.md)
for the full archaeology, gap table, and evidence. Ongoing Monitoring
Failure Diagnostics for RTSP / Local USB / Windows DShow v1 (2026-08-30)
then closed that milestone's own disclosed remaining implementation gap;
see
[ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md](ongoing-monitoring-failure-diagnostics-rtsp-local-usb-windows-dshow-v1-report.md).
Release classification: **C** (usable; the remaining gap is real hardware
validation, not implementation).

Closed by Camera / Source Experience & First-Hour Setup Closure v1:
manual RTSP setup's separate "Auth username"/"Auth password" fields were
collected but silently discarded on every write and never reached a real
connection attempt -- now stored for real and merged into the effective
connection URL everywhere it's actually used. Only Camera Node had a
real "Check the picture" setup preview -- now RTSP/ONVIF/local/
Windows-USB have the same bounded, non-persisting preview capability, and
`CameraSetupValidationResponse.preview_available` is computed honestly
instead of hardcoded `False`. A healthy camera's own detail page had no
persistent way back to reconfigure it; a dead, unreachable duplicate
Add-Camera form was removed.

Closed by Ongoing Monitoring Failure Diagnostics for RTSP / Local USB /
Windows DShow v1: the ongoing-monitoring failure-code collapse named
below is fixed -- a new bounded, continuous `BoundedStderrDrain` replaces
the previously-unconditional `stderr=subprocess.DEVNULL` on RTSP/local
USB/Windows DirectShow's own long-running monitored processes (proven
safe: no pipe deadlock, bounded memory, no thread leak, no blocked frame
delivery); RTSP ongoing monitoring now reuses the exact, unmodified
setup-time classification vocabulary; local USB/Windows DirectShow gained
new classifiers strictly bounded to real evidence gathered this
milestone, with an honest generic fallback wherever that evidence ran
out; two independent hardcoded Camera-Node-only allowlists that had been
discarding any other provider's classified code were widened. Camera Node
itself was out of scope and is untouched.

Remaining, not closed by either pass: real local USB/Windows DirectShow
hardware acceptance (device-busy, permission-on-real-hardware,
unsupported-format were not evidence-backed on the hardware available
this session -- honestly generic behavior for those causes by design, not
a known defect) and a real RTSP camera's own live auth/codec failure
(only a real, live, disposable-endpoint *unreachable*-failure proof was
practical this session, through the completely real, unmodified product
code path). No real, reachable camera/RTSP/ONVIF/local-USB hardware or
Camera Node was available to prove actual video decode/preview
end-to-end in either session (native-Windows evidence proves the real
subprocess/HTTP/taxonomy/credential-merge mechanics genuinely work
against a real unreachable host, not that a specific real camera's
picture renders). Full integrated multi-camera/whole-product acceptance
remains Lane R.

### H. Site-Specific Learning

**Status:** FROZEN.

No adjacent learning expansion automatically authorized.

### I. Broader Wildlife Maturity

**Status:** FROZEN STRUCTURALLY.

Real mammal field evidence remains limited. Do not create another model
campaign solely to fill the matrix.

### J. Ecological / External Workflows

**Status:** MATERIALLY ADVANCED -- Ecological Interoperability & Submission
Workflows v1 (2026-08-25) closed this lane's decision; see
[ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md).
Classification **B**.

Delivered: a real, working, submission-ready iNaturalist workflow
(eligibility preview with per-record reasons, explicit never-inferred
location/media consent, batch prepare, a destination-shaped CSV confirmed
directly against iNaturalist's own open-source bulk-import code,
fingerprint-based staleness detection, a self-reported external-result
close-the-loop step); a bounded, additive Darwin Core Occurrence-core
export; the destination-decision research itself (eBird's own current
policy explicitly excludes feeder/trail-camera data -- not offered, and
the product UI says why persistently, not merely in a hover tooltip; GBIF
direct publication requires organizational endorsement -- correctly
deferred as institutional); two real security findings made and fixed
(CSV injection in the shared CSV writer behind every export in this
codebase, retroactively hardening the pre-existing generic/Camtrap DP
paths too; a `javascript:`-scheme external-URL gap). Schema 56 -> 57 (two
additive tables). No live, authenticated destination submission exists
anywhere -- Phase 26 of that milestone's own brief: no unsafe
credential-storage workaround invented for a capability that does not yet
exist.

Remaining, not closed by this pass -- see the report's "Remaining major
PRODUCT opportunities": live OAuth iNaturalist submission; media-byte
inclusion; a single-Visit deep-link pre-selection on the Ecological
Destinations page; broader batch-filter UI depth (stream/source/collection
scoping, already supported server-side via the reused
`ResearchExportFilters`, not yet exposed in the frontend).

### K. Ecosystem / Provider Integrations

**Status:** OPEN DECISION.

Candidates previously discussed: Frigate; Blue Iris; Scrypted; Home
Assistant. Do not implement all. Decide whether a minimum useful adapter
set materially improves first-release adoption. Native Camera Node +
standards-based acquisition remain the golden path.

### L. Appliance / Update / Recovery

**Status:** MATERIALLY CLOSED -- RELEASE-CRITICAL. Host side closed by
Release Engineering Foundation v1 (2026-08-25); Camera Node **upgrade**
workflow -- the one specifically-named remaining item -- closed by Camera
Node Upgrade & Compatibility Recovery v1 (2026-08-26), classification
**A**. See [camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

Closed for the **Host**: an automatic, verified pre-migration safety
backup now runs before any in-place schema upgrade; a genuine post-
migration health check gates readiness; the upgrade fact is honestly
surfaced (console + Dashboard); restoring that automatic backup is the
documented rollback path; interrupted-upgrade behavior (backup failure,
mid-migration failure, post-migration integrity failure) all fail closed
and are regression-tested; real native-Windows evidence includes an
organically-occurring 18-schema-version migration on real pre-existing
data. Host↔Camera Node **wire-protocol** version compatibility
(`api_version`, `transport_protocol_version`) confirmed already
hard-gated; the Node's own `service_version` remains display-only by
deliberate choice (see the milestone report).

Closed for the **Camera Node**: `scripts/install_camera_node.py` (the
existing installer, extended rather than replaced) now runs a real
preflight (artifact well-formed, `SHA256SUMS` checksums, disk space, a
Node-local wire-protocol compatibility comparison against the currently
-installed build) before any mutation; stages and verifies a candidate
(`import mockingbird_node.app` inside its own fresh venv) before the live
install is touched at all; activates manifest-first/venv-second so any
interruption resolves to one of three well-defined, automatically
-reconciled states; automatically restores the prior known-good build if
the newly-activated one fails post-update health verification (never on a
first-ever install); and never silently accepts an unexpected `node_id`
change. Real acceptance against the project's actual reference Pi (never
upgraded since 2026-08-18, predating three later accepted Camera Node
milestones) found and fixed, live, a universal upgrade-blocking defect
(a transport-configuration path defaulting through `Path.home()`, always
broken under the already-accepted `ProtectHome=true` hardening regardless
of whether transport was ever configured -- would have broken every
Camera Node upgrading past Remote/Intermittent-WAN Transport Foundation
v1 through the accepted installer) and two automatic-recovery gaps
(`systemctl restart` failing outright not triggering rollback; a prior
crash loop's exhausted `StartLimitBurst` blocking an unrelated later
restart) -- all three fixed the same session with regression tests, not
merely disclosed. The device was fully upgraded end to end with node
identity/pairing/camera availability all confirmed unchanged.

Remaining, disclosed, not closed by this pass: `rollback()` restores code
but not an already-changed systemd unit template (a real gap this
milestone's own real acceptance encountered and worked around manually,
not closed structurally); `rollback()`'s own directory swap has a
narrower residual crash-window gap than the forward-upgrade path's
reconciliation closes; reinstall/replacement beyond what reprovisioning
already covers and broader operator-facing update/recovery UX remain
Camera Node install/reboot/reprovision's own already-accepted scope,
unaffected by this milestone. See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
and
[camera-node-upgrade-compatibility-recovery-v1-report.md](camera-node-upgrade-compatibility-recovery-v1-report.md).

### M. Storage / Retention UX

**Status:** CLOSED -- RELEASE-CRITICAL. Integrated acceptance performed
by Storage / Retention / Disk-Pressure & Recovery Closure v1 (2026-08-28,
classification **B**), then closed by Retention Correctness & Bounded
Cleanup Closure v1 (2026-08-28, classification **A**) -- see §1/§3,
above, and
[storage-retention-disk-pressure-recovery-closure-v1-report.md](storage-retention-disk-pressure-recovery-closure-v1-report.md)/
[retention-correctness-bounded-cleanup-closure-v1-report.md](retention-correctness-bounded-cleanup-closure-v1-report.md).
Disk-pressure detection (a real, tested, graduated healthy/getting_low/
action_recommended/critical ladder), long-running storage growth (real,
directly-measured accounting on both the WSL dev host and the real Windows
deployment), cleanup/retention (now 366+ real tests across the two
closures, independently re-run, covering eligibility/idempotency/
interruption-safety/transactional ordering/bounded history), DB/media
consistency (traced precisely in both directions), and backup visibility
(Doctor-surfaced staleness/unreadable-count/interrupted-restore, all real
and tested) were each verified integrated, not merely inspected in
isolation. NAS/external-storage support remains an explicit product
decision, not an automatic blocker, and was not built. The three real,
precisely-disclosed, safe-direction gaps the first closure found and
deliberately left unfixed (imported-media over-retention against its own
documented contract; a `"staging"`-batch purge-path gap; a cosmetically-
misnamed, actually-unbounded `storage_cleanup_history` constant) are now
fixed and tested by the second, closing this lane. One real,
already-disclosed, structural gap remains, deliberately not reopened by
either closure: no orphan-media/no-DB-owner detection anywhere in the
product (no code scans the media directory and cross-references it
against the DB) -- real, bounded, and low-materiality per the first
closure's own investigation, not release-blocking, a reasonable candidate
for a future bounded "sampled orphan sweep," not a reason this lane
remains open.

### N. Privacy / Contribution

**Status:** CLOSED -- RELEASE-CRITICAL. Local Only / Privacy Closure v1
first closed this lane's Local Only requirement at classification **B**
(see
[local-only-privacy-closure-v1-report.md](local-only-privacy-closure-v1-report.md)),
proving core product functionality works with zero internet route
available via a real, live, OS-level network-denial runtime acceptance --
but that acceptance ran the Linux/WSL dev checkout rather than the
packaged native-Windows artifact, and exercised the model-assets-absent
path rather than assets-present, both named explicitly as the reason it
was not classification A. Native-Windows Packaged Local-Only Acceptance &
Privacy Closure v1 (see §1/§3, above, and
[native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md](native-windows-packaged-local-only-acceptance-privacy-closure-v1-report.md))
closed both of those specific gaps at classification **A**: a real
disposable native-Windows packaged deployment (full GPU/BioCLIP dependency
closure, no skip flags), a real (non-kernel, environment-appropriate)
internet-denial mechanism with independent OS-level corroboration, and
both production models (MDv5a, BioCLIP-2) proven initializing and running
real local inference at the exact production code path both before and
after denial, with zero outbound network activity. The camera-credential-
at-rest question this lane's prior closure left open is now resolved to a
documented non-defect (plaintext at rest, no contract promises
otherwise -- see that report's own "Camera credential storage" section).
Zero reproduced Local Only/privacy defects across either milestone.

**Local Only.** Operational/default requirement. Confirmed met -- see
above.

**Derived Data Contribution.** Doctrine exists; confirmed **not yet
operationally implemented** -- Local Only / Privacy Closure v1 traced
every "contribution" occurrence in `src/mockingbird/` and found none is a
cloud-upload pathway (every real hit is an unrelated internal
scene-confusor-region bookkeeping concept). Do not assume operational
implementation or cloud backend exists. Never silently include:
image/video/audio; thumbnails/crops; raw frames; embeddings/reconstructable
media-derived features; local filesystem paths; free-text notes;
faces/people/vehicle imagery; precise property/home coordinates. The
moment this capability is actually built, it needs its own dedicated
privacy verification -- this lane's closure does not cover a capability
that does not yet exist.

**Media contribution.** Separate future consent capability. Contribution
must never become required for core operation.

### O. Platform / Runtime Portability

**Status:** CLOSED -- Platform / Runtime Portability & Support Truth
Closure v1 (2026-08-30) closed this lane at classification **A**; see
[platform-runtime-portability-support-truth-closure-v1-report.md](platform-runtime-portability-support-truth-closure-v1-report.md).

The canonical vocabulary is now: **Validated** (real release acceptance
on the real platform/runtime); **Structurally supported** (the stack
intentionally supports it, no unguarded defect known, hardware acceptance
incomplete); **Degraded / fallback** (an explicit, honestly-reported
limitation, never silent); **Unverified** (no current claim, genuinely
untested); **Unsupported** (known not to work, or excluded, and says so);
**Deferred** (potential future support, not part of this release). This
reuses this lane's own five terms verbatim plus folds in "Degraded /
fallback," which already existed as a real status value in the product's
own health model before this closure.

**Host:** native Windows -- **Validated** (the only Host with a packaged,
no-Python-required end-user distributable; real CUDA/BioCLIP/migration
evidence at the production code path, entirely reused from already-
accepted milestones). Linux -- **Structurally supported** at the source/
dev level only (continuously CI-validated on real `ubuntu-latest` for the
full Core suite, frontend build, and the Windows-packaging pipeline's own
structural smoke test; a genuine first-class Linux-only feature, the V4L2
local-USB-camera bridge, already exists) -- explicitly **not** "validated
release Host": no packaged end-user Linux distribution exists, and no
dedicated native-Linux hardware acceptance has ever been performed. macOS
-- **Unverified** overall; microphone capture specifically **Unsupported**
and already honestly disclosed (fixed in a prior accepted milestone).

**Runtime:** CPU -- the accepted detector (`onnx-cuda`, backing the
production `frame-driven-onnx-cuda` path) is **Unsupported** on CPU by
deliberate, regression-tested design (`session.disable_cpu_ep_fallback`,
CUDA-only provider list, `onnx_cuda_unavailable`/`onnx_cuda_no_fallback`
raised rather than silently degrading) -- there is no fallback, and this
is a tested guardrail, not a gap. Species (BioCLIP-2) and acoustic
(BirdNET) assistance are **Validated**, CPU-only by the identical
deliberate design, and never block Visit creation when unavailable.
NVIDIA CUDA -- **Validated** on native Windows (the strongest currently-
evidenced accelerated path); **structurally supported, hardware-
unverified** on native Linux specifically (identical code, zero OS
branch in the CUDA path itself, never separately proven on real Linux
hardware). Apple Silicon -- **Deferred** (zero active MPS selection code
in the accepted production path; no hardware available; extends
`docs/species-classification-reevaluation-promotion-v2-report.md`'s own
precedent rather than re-deriving it). AMD -- **Unsupported** (zero
ROCm/DirectML code anywhere in the stack).

**Camera Node:** Raspberry Pi 4 / Raspberry Pi OS remains the real,
repeatedly-validated reference hardware. The Camera Node's own software is
genuinely hardware-agnostic by protocol, verified against real code, not
merely asserted: a `CameraNodeProvider` abstraction backs both the
Pi-specific `PiCamera2Provider` and a real, independent
`V4L2CameraProvider` (generic Linux/USB via OpenCV), each degrading
gracefully (`setup_required`, never a crash) if its own runtime is
absent. No non-Pi hardware has ever been release-tested, and the matrix
does not claim otherwise.

Two narrow, reproduced capability-overclaim defects were found and fixed
in `python -m mockingbird doctor` (see §1/§3, above, for the full
account); two further gaps were found and precisely disclosed, not fixed,
since neither is reproduced against any real or currently-shipping path.
No new platform support was added; do not schedule a macOS port, an
Apple Silicon model-conversion campaign, or ROCm/DirectML implementation
as a consequence of this closure -- none is a release blocker, and none
was authorized.

### P. Release Engineering Foundation / Distribution

**Status:** SUBSTANTIALLY CLOSED, one item deliberately left open --
RELEASE-CRITICAL. Release Engineering Foundation v1 (2026-08-25) closed:
upgrade procedure (see Lane L); a real, currently-live dependency-closure
defect found and fixed via genuine native-Windows deployment (`astral`
missing from the packaged bundle -- would have broken *every* launch,
clean-install included) plus a regression test against the whole class of
drift; version single-source-of-truth; artifact provenance/checksum
parity with the Camera Node build script (`source_clean`); an independent
post-build artifact verifier (`scripts/verify_release_artifact.py`); this
repository's first CI automation (`.github/workflows/ci.yml` -- Core
gate, frontend build, a real structural packaging-smoke build);
`SECURITY.md`; release-artifact smoke testing; Host ↔ Camera Node
compatibility (investigated and confirmed adequate, not a gap). See
[release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md)
for the complete record, including real native-Windows acceptance
evidence (Decision A).

Release Licensing, Distribution & Third-Party Legal Closure v1
(2026-08-30, see §1/§3, above) closed the second item this section
previously named: **full ffmpeg bundling**. Traced to every real
invocation site and every packaging/build script -- MockingBird never
bundles, downloads, or vendors an ffmpeg binary in any official package;
it is a pure external system dependency (`shutil.which("ffmpeg")`),
already honestly documented, and the recommended Camera Node golden path
needs no ffmpeg at all. A new build-time guard,
`verify_no_bundled_ffmpeg_binary`, now makes this posture durable rather
than merely accidental, mirroring the pre-existing BirdNET-weight-
exclusion guard's own role. The same milestone also added
`THIRD_PARTY_NOTICES.md` -- shipped inside every official Windows bundle,
correcting a real gap where the redistributed MDv5a/BioCLIP-2 model files
carried zero accompanying license/notice text (unlike an ordinary pip
dependency, whose own license already travels automatically).

Deliberately still open, not silently dropped: **`LICENSE`** (a
business/legal decision -- which license, and its interaction with the
still-unresolved BirdNET commercial-adjacent-distribution question in
§2, above -- outside a bounded engineering milestone's authority to
resolve unilaterally; see Release Licensing, Distribution & Third-Party
Legal Closure v1's own report for the complete decision packet: MIT
recommended, two alternatives named and reasoned through, one exact
owner-facing question). Public-repo hygiene beyond `SECURITY.md`/
`CONTRIBUTING.md`/`THIRD_PARTY_NOTICES.md` (README/site polish,
brand/trademark review) remains open per "Public release readiness" in
[roadmap.md](roadmap.md), not release-critical blocking.

Release Engineering Foundation may occur before all product development is
finished. Release Engineering Foundation is not the same as final Release
Hardening.

### Q. Whole-Product UI / Accessibility / Performance

**Status:** CLOSED AS AN INTEGRATED PASS -- Whole-Product UI /
Accessibility / Performance Closure v1 (2026-08-27) closed this lane; see
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md).
Classification **A**.

Validated live against a seeded, product-shaped 371-Visit QA instance and
real code inspection: responsive behavior (zero horizontal overflow, 4
required widths x 10 pages); touch (existing tap-target/mobile-drawer
conventions intact); keyboard/focus (sidebar nav, mobile drawer already
correct; two real Fast Review focus-management defects found and fixed);
accessibility semantics (spot-checked, sound); large real-data performance
(measured, at or below established precedent, no regression); several
cameras (3 active mixed-health + 1 archived Stream, coherent); large
review queues (89-item backlog, correctly bounded); error/recovery UX
(camera-vs-observation-runtime distinction already correct); visual
consistency (StatusPill never color-only). Closed the bounded acoustic
health/status gap (Lane A) with the smallest capability-aware addition
the brief allowed. Found and fixed one P0 (Review Queue default-tab
misclassification of imported Visits) along the way -- the real,
previously-unidentified root cause of one class of confusion this project
had repeatedly misattributed to `reviewed-product-loop.spec.ts` being an
unrelated flake. That spec itself remains red, now precisely diagnosed as
test-suite staleness (a hardcoded `productMode = true` makes the legacy
markup it targets permanently unreachable), not a live product defect --
disclosed, not fixed, a real but separately-scoped follow-up. Also
disclosed, not fixed: Zone-polygon drawing (not selection) has no
keyboard equivalent (optional/advanced feature); a larger-than-previously
-documented dead-CSS footprint; a narrow raw-exception-text edge case.
See the report for the complete finding-by-finding record.

### R. Complete Field Acceptance

**Status:** NOT DONE -- RELEASE-CRITICAL.

Component acceptance is not whole-product acceptance. Final integrated
release configuration should exercise: several cameras; visual inference;
audio if included; review; Today/history; long unattended operation;
disconnect/reconnect; Host reboot; Camera Node reboot; storage pressure;
model unavailable; backup/restore; upgrade; clean installation; actual
user operation. Remote LTE field acceptance remains separately scoped when
Remote Field is not part of release scope.

**Representative Field Acceptance & Release-Budget Closure v1 (2026-08-25)
attempted, returned Gate C -- OPEN, insufficient representative evidence.**
Not a product defect: the attempt was stopped before any Observation
session started because the native-Windows dev instance now enforces real
sign-in on every endpoint the session needed (streams, observation start/
stop, Visits, counterfactual ledger -- the pytest auth bypass was removed
as part of the accepted Local Identity / Multi-User work, 2026-08-23),
no credentials exist anywhere in this repository, and the user explicitly
declined to share real admin credentials, create a temporary account, or
participate live right now. Nothing about the frozen perception/admission/
Visit/evidence/classification stack was exercised or judged. Real,
positive, non-live evidence preserved from this attempt: the reference
Camera Node (`192.168.1.112:8787`) is reachable at the network level; the
native-Windows Host dev deployment is healthy at the accepted commit
(schema v53); the full accepted acceptance-tooling chain (recorder,
motion-screen/contact-sheet review, independent encounter table,
counterfactual ledger, `run_encounter_accounting.py`) is confirmed present
and ready to reuse. See
[representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md)
for the full record, including the standing decision for future sessions:
do not ask the user again for real credentials or live participation
unless a future milestone specifically requires human acceptance and they
explicitly agree first; ordinary auth-requiring development/validation
work should instead use a fresh, isolated dev instance with a disposable
bootstrapped local Administrator account.

**Representative Multi-Camera Field Acceptance & Release-Budget Evidence
v1 (2026-08-26) attempted, also returned no new live-field evidence --
classification B, an acceptable outcome per this milestone's own governing
brief, and a materially different shape from the 2026-08-25 attempt
above.** Not blocked by authentication this time: the session start
(20:26 EDT) was after sunset, the same "darkness produces an unusable bird
denominator" scenario 2026-08-19/2026-08-20 already demonstrated twice: a
post-sunset session produces a clean, real, but useless zero-track-
generation result, not evidence about daytime bird activity. No
Observation session was opened. Executed the "no representative
conditions" path instead and used the time to make the next daylight
session concretely more ready, not merely re-documented: found and fixed
one real, previously-hidden Windows build defect (a `click` dependency-
pin gap identical in mechanism to this codebase's own already-documented
`idna` pin) that would otherwise have cost the next session its own
debugging time; produced a fresh, independently-HTTP-verified, ledger-
retained deployable artifact of accepted HEAD ready for instant relaunch;
confirmed GPU/detector/storage/Camera-Node health; confirmed, via the
unauthenticated health endpoint only, that only one real Stream is
currently configured in the dev instance and that a second real, already-
supported Source (a Windows-native USB webcam, already hardware-validated
for the Acoustic milestone) should be wired up before the next session so
the still-open "does the concurrent-persistence fix hold under genuine
multi-camera load" question can actually be tested with two real cameras;
and documented the exact command/API sequence, acceptance-recorder
settings, and structured-log location (`.../userdata/logs/mockingbird.
log`) that session needs. See
[representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md](representative-multi-camera-field-acceptance-release-budget-evidence-v1-report.md).
Gate A's evidence body is unchanged by this session (still exactly the
two real 2026-08-19/2026-08-20 daylight cohorts) -- no release budgets
proposed. The standing decision above (do not ask the user again for
credentials/live participation absent explicit agreement) was not
re-litigated and remains in force.

**Representative Daylight Field Acceptance & Gate A Evidence v2
(2026-08-28) attempted, also returned no new live-field evidence --
classification B.** For the first time in three consecutive attempts,
every environmental/infrastructure precondition was simultaneously
satisfied: session start ~15:20 EDT (mid-afternoon, hours before sunset --
unlike the 2026-08-26 attempt), reference Camera Node healthy and
reachable (`GET /node/v1/health`: `status: "available"`, self-test
passed, watchdog healthy, zero consecutive probe failures), GPU idle and
available (RTX 4060 Ti, zero MockingBird compute process at check time),
storage adequate, acceptance-recorder confirmed present and structurally
isolated from product truth. The sole remaining blocker, isolated more
precisely than either prior attempt could isolate it, is the identical
authentication precondition from the 2026-08-25 attempt above,
re-confirmed today against a freshly rebuilt and redeployed current
accepted HEAD (`80e1bb3`): `GET /api/streams` and `GET /api/visits` both
returned `401`, with no credentials attempted. Per the standing decision
above, no credentials were requested, no fresh disposable instance was
substituted for the real one, and production authentication was not
touched. The fresh deploy itself hit one cold-start false-negative (the
tool's own bounded 90-second verification window gave up before BioCLIP/
CUDA cold start finished) -- manually confirmed healthy and identity-exact
(`git_commit` exact match, schema 57, `ready: true`) via direct HTTP and a
follow-up `--status` check, matching an already-documented recurring
pattern, not a new defect; then stopped cleanly, leaving `80e1bb3`
retained and ledger-verified. Confirmed, again via the unauthenticated
health endpoint only, that the second real Source (the EMEET SmartCam
S600 USB webcam identified 2026-08-26) remains unwired -- adding it needs
the same authenticated path. Investigated one hypothesis for the
continuing `C:` free-space decline (43.07GB on 2026-08-20 -> 18.8GB today)
-- retained Windows dev-release accumulation -- and ruled it out (25
retained releases total only ~700-750MB; each release is ~29MB, not a
multi-GB per-release duplication); the actual cause remains open. Gate
A's evidence body is unchanged -- still exactly the two real
2026-08-19/2026-08-20 daylight cohorts, now for the third consecutive
attempt, two of the three blocked by the identical authentication
precondition. No release budgets proposed. See
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md).

**Non-Interactive Field Acceptance Authentication & Session Access v1
(2026-08-28) closed the authentication half of the recurring blocker
above, at classification A -- see §1/§3, above, and
[non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
for the full record.** A narrow, non-interactive, bearer-token "Field
Acceptance Operator" credential (schema v58) now lets bounded
field-acceptance tooling authenticate without an operator's personal
password, proven live against a real running instance of the exact
mechanism (the identical three previously-blocking endpoints -- `GET
/api/streams`, `GET /api/visits`, `POST .../observation/start` -- all
still correctly `401` unauthenticated, then all succeed with the new
credential, including a real Observation start/stop cycle). This closes
the *authentication* precondition specifically -- it does **not** by
itself close Lane R/Gate A, does **not** run the field session, and does
**not** authorize the next attempt; Gate A's evidence body is unchanged --
still exactly the two real 2026-08-19/2026-08-20 daylight cohorts. The
next daylight session still needs its own separate authorization plus
representative daylight/weather/health conditions (unrelated to
authentication, and not something this milestone could control), but no
longer needs to ask the operator for credentials or route around the
blocker -- see this milestone's own report for the exact one-time
provisioning command.

**Representative Daylight Gate A Field Acceptance v4 (2026-08-29) ran
the first real live daylight session under the new credential, at
classification A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v4-report.md](representative-daylight-gate-a-field-acceptance-v4-report.md)
for the full record.** Deployed to a genuinely fresh, disposable instance
(never the operator's `MockingBirdDev` identity), resolving a real
conflict the credential-closure milestone did not anticipate: the
reference Camera Node's pairing is single-slot/disk-persisted, so a
truly fresh instance cannot reach it without a reset -- done via the
already-documented, supported recovery flow, with the user's explicit,
specific approval (not assumed), leaving the operator's own
`MockingBirdDev` instance needing a one-time re-pair before its own next
use. A real ~112-minute Observation session followed against the real
Stream, with the independent acceptance recorder running throughout
(99.78% coverage) and real, sustained, near-continuous multi-bird feeder
activity directly visually confirmed (full-resolution frames, not
inferred) for effectively the entire session. `candidates_created`
stayed at exactly 0 the whole time -- a real, previously-undocumented P0
admission-arbitration gap (sustained near-continuous activity structurally
starves the `continuation_pending`/`blocked_ambiguous_boundary`
resolution mechanism, whose only design-intended escape, session-end
finalize, did not visibly rescue this session's own real stop either --
left as a precise, disclosed open question) was found and precisely
root-caused by direct code reading, not fixed -- a trustworthy fix is
comparable in scope to a full milestone, not a bounded change, per the
governing brief's own explicit bar. Gate A's evidence body now has a
**third** real cohort, structurally different from the first two
(sustained multi-subject activity at a busy feeder, vs. the sparser
single-subject encounters 2026-08-19/2026-08-20 each captured) -- three
real cohorts now span 0% to 68.2% end-to-end Visit recall. No release
budgets proposed; the report's own reasoning is explicit that this range
does not converge into a budget until the newly-found defect is fixed
and re-measured. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone.

**Sustained-Activity Visit Admission Starvation & Stop-Finalization
Correctness v1 (2026-08-29) fixes the P0 the field session immediately
above found, at classification A -- see §1/§3, above, and
[sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md](sustained-activity-visit-admission-starvation-stop-finalization-correctness-v1-report.md)
for the full record.** Root cause confirmed structural, not a
wrong-value bug: individual episodes were already correctly bounded, but
nothing bounded how long a whole connected *ambiguous component* could
keep deferring while its own currently-active tail kept being refreshed
by sustained real activity -- deterministically reproduced (26 simulated
minutes of continuous activity, zero admissions, exactly the field
symptom) against the real, unmodified pre-fix code before being fixed
with a bounded decision horizon reusing the existing, already-calibrated
20-minute episode-span bound (never a new magic number, never the 45s
gap value itself). The field report's own separate, disclosed-open
"did stop rescue anything" question is independently root-caused (a
real external/background-thread revert-to-shadow race, deterministically
reproduced and fixed) and confirmed **not** the same mechanism as the
starvation defect. Investigating the evidence-cache bound's own possible
contribution (per this milestone's own governing brief) found and fixed
two further real, narrow, pre-existing defects that would otherwise have
kept producing the identical "zero Visits" symptom one gate later
(`blocked_missing_evidence`) even after the primary fix -- neither the
128-entry bound's own size nor the 45-second gap value were changed. A
105-simulated-minute, two-simultaneous-subject stress replay confirms
bounded, non-starved, non-duplicated, non-contaminated admission
end-to-end. Tier 2: 505 passed, 0 failed (22 files, the brief's own
named subsystem list). Tier 3 (full Core): 5238 passed, 3 failed (all 3
independently confirmed pre-existing/unrelated, not merely assumed --
see the report for the direct bisection/repeated-run evidence), 3
skipped, 23 deselected, 11 xfailed. No schema change. This closure does
**not** itself close Lane R/Gate A -- no live field session ran, per
this milestone's own explicit non-goal (§20: "do not launch a real
wildlife Observation tonight... a real daylight field rerun belongs
AFTER this implementation milestone is accepted") -- and does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. The next daylight session
against a busy, real feeder Stream is what Gate A still needs: proof
that `candidates_created` is no longer stuck at 0 under real sustained
activity, that admission happens well before session end (not only at
stop), that a real stop against genuinely pending work resolves
honestly, and that multi-subject correctness holds through to real
admitted Visits under real conditions -- the one dimension the
motivating field session could not exercise at all, since nothing there
ever reached admission. See the milestone's own report, "Field-rerun
requirement," for the complete, precise list.

**Representative Daylight Gate A Field Acceptance v5 (2026-08-30) ran the
first real daylight session against the corrected build, closing every
item that milestone's own "Field-rerun requirement" named, at
classification A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v5-report.md](representative-daylight-gate-a-field-acceptance-v5-report.md)
for the full record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node
via the identical documented recovery flow v4 used, with the user's
explicit approval. A real ~106.6-minute Observation session followed
against the same real Stream/scene v4's own busy-feeder session used,
with the independent acceptance recorder running throughout (~99.99%
temporal-span coverage, ~5,147 frames). `candidates_created` reached its
first real admission ~25 seconds into the session and climbed steadily
throughout -- 19 real Visits admitted by session end, not merely at
stop, directly confirming the accepted fix under real sustained genuine
activity. Stopped deliberately into a moment with substantial genuinely
pending work; the new `stop_finalization_pending` status was observed
live for the first time in a real field session, correctly appearing
then clearing while the finalize tick genuinely rescued 2 more pending
candidates (17 -> 19) -- directly answering v4's own left-open "did stop
rescue anything" question. Zero `blocked_shadow_mode`, zero persistence-
contention, zero duplicate Visits across the whole session -- no
recurrence of any of the three defects that milestone fixed. Multi-
subject correctness remains only partially advanced: real simultaneous
multi-bird presence was directly confirmed in-scene, but no two Visits
this session shared a single Event as genuinely concurrent siblings, so
that specific mechanism was not exercised end-to-end either. One real
defect was found and precisely root-caused, not fixed, per the governing
brief's own bar: a single false-positive admission (a weak, single-
detection, `terminal_reason: maximum_unsupported_duration` localization)
received a confident ("Brown Thrasher," 89.9%) but wrong BioCLIP species
label on a crop that direct pixel-region inspection against its own real
bounding box confirms is empty background -- a fresh, concretely-
reproduced instance of the already-known Gate B "background evidence ->
confident label" regression class `roadmap.md` already names as open
work (see Gate B, [roadmap.md](roadmap.md)), not a new starvation-family
defect and not release-blocking for this milestone's own scope. Gate A's
evidence body now includes a fourth real cohort, and the first
post-fix one: three prior cohorts spanned 0% to 68.2% end-to-end Visit
recall; this session found no missed genuine encounter via targeted
(not exhaustive) independent review, qualitatively far closer to
complete than either prior busy-feeder or sparse-encounter cohort. Two
candidate release budgets are proposed for review, from convergent
evidence across all four real cohorts, not self-accepted: minimum
monitoring coverage ~99% (all four cohorts measured 99.6%-99.99%) and
minimum useful-evidence rate ~85% (two independent measurements, 88.2%
and 94.7%, with no contrary evidence). Recall/false-Visit-rate/
fragmentation-rate budgets are explicitly *not* proposed -- this
session's own figures are the first post-fix measurement of each, not
yet a second, independently-varied confirmation. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening,
and does **not** select a next development milestone. Remaining Gate A
dependency, in priority order: (1) a second post-fix daylight session
exercising conditions v5 did not (genuinely simultaneous multi-subject
admission, and/or a sparser single-subject scene re-run post-fix) to
convert this session's own single strong data point into the broader
body of field evidence Gate A budgets require; (2) only then, propose
numeric release budgets for recall/false-Visit-rate/fragmentation-rate
with real cross-session convergent support. The one disclosed defect
this session found remains open Gate B work, not blocking Gate A
directly.

**Post-v5 Global Product-Roadmap Reconciliation & Gate A Next-Step
Authorization (2026-08-30).** Documentation/governance-only -- reconciles
this file and `roadmap.md` to agree on the v5 result above and names the
exact next Lane R milestone: see §3, above, for the full authorized
contract (**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche**, not yet run). Two budget
dimensions -- minimum monitoring coverage (~99%) and minimum
useful-evidence rate (~85%) -- move to **READY FOR FORMAL BUDGET REVIEW**
(candidate values proposed across all four real cohorts to date, not yet
formally accepted release budgets); recall, false-Visit rate,
fragmentation rate, and capture-to-visible latency remain
evidence-accumulated only, with no candidate value proposed -- see
`roadmap.md` "Numeric release budgets" for the complete reconciled
accounting. No numeric recall budget is introduced by this reconciliation;
v5's own qualitative "no missed genuine encounter found via targeted, not
exhaustive, review" conclusion is preserved exactly as reported, not
converted into a recall percentage. Gate A/Lane R remains open. This
reconciliation does not authorize External Pre-Release Acceptance or
Final Release Hardening, and does not itself run the next field session.

**Representative Daylight Gate A Field Acceptance v6 -- Post-Fix
Replication & Multi-Subject Tranche (2026-08-31) ran the second real
daylight session against the corrected build, at classification **B**,
not A -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v6-report.md](representative-daylight-gate-a-field-acceptance-v6-report.md)
for the full record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node
via the identical documented recovery flow v4/v5 used, with the user's
explicit approval. A real 106.63-minute Observation session followed
against the same real Stream/scene, a genuinely different daylight window
(09:19:59-11:06:37 EDT, mid-morning) than v4's or v5's own, with the
independent acceptance recorder running throughout (~99.4% temporal-span
coverage, 5,214 frames). Two exhaustively-reviewed real activity windows
(directly confirmed via full-resolution independent-recorder frames, not
inferred, each containing genuine simultaneous multi-bird moments -- 2
birds at 25.79min, 2-3 birds in an active flurry at 90.50min) together
produced **zero** admitted Visits: `candidates_created` stayed at exactly
0 for the entire session, despite `track_updates_observed` reaching
11,078 and `proposals_observed` reaching 521. Directly root-caused by
reading the real arbitration source (`candidate_visit_authority.py`,
`engine_runtime.py`) against the real, fully-reconstructed counterfactual
ledger (521 records, cross-verified lossless): this is **not** a
recurrence of v4's own starvation mechanism -- `resolve_ambiguous_
boundary_arbitration` reached a decision for every real ambiguous
component on schedule throughout (164 proposals correctly, permanently
`blocked_ambiguous_boundary` as non-winning cluster members; the intended
"at most one Visit per cluster" behavior working exactly as designed). The
actual loss mechanism is one gate later: 48 of 263 distinct proposals
(18.3%, spread across the *entire* session, not one isolated cluster)
reached a genuine arbitration win and then permanently failed at the
evidence-availability gate (`blocked_missing_evidence`/`no_persistable_
evidence_bytes`), because the shared, session-global, insertion-order-only
128-entry evidence-byte cache had already evicted that specific winner's
own bytes by the time its own (correctly, if belatedly, computed)
arbitration turn arrived -- and because that outcome is not in
`RETRYABLE_OUTCOMES`, no code path ever re-attempts the same resolved
component with its own second-best member. This is not a new defect
class: `engine_runtime.py`'s own `_MAX_CACHED_BURST_BYTES` history
comment already named almost exactly this mechanism when the bound was
last raised 32->128 and explicitly declined to fix it structurally ("a
pending-proposal-aware eviction policy... is a materially larger
change... left as a disclosed follow-up, not undertaken here"); v5's own
report separately named the same residual in the abstract. v6 is the
first real, concrete, session-wide *measurement* that this is not a rare
edge case (18.3% of distinct proposals this session, versus v5's own
2.8%), and the first evidence that it also reaches the *ordinary*
(non-forced, confidence-ranked) arbitration path, not only the
recency-forced path the original disclosure discussed. Stop-finalization
itself behaved correctly (the honest `stopping`/`stopped` cycle with
`stop_finalization_pending` was observed live exactly as the accepted
contract specifies, rescuing 0 -- consistent with, not a regression of,
the root cause: nothing cleanly resolvable remained pending at stop,
since every real activity window's own fate had already been permanently
decided earlier in the session). Zero `blocked_shadow_mode`, zero
persistence contention, zero ERROR/CRITICAL/WARNING lines across the full
164-line structured session log. Background/empty-evidence eligibility
and species assistance were not exercisable this session at all (zero
admitted Visits ever reached either layer) -- disclosed as honest
measurement gaps, not fabricated proof; the accepted `26edddf` fix's own
two files are confirmed byte-for-byte unmodified this session. Real,
directly-confirmed simultaneous multi-subject activity occurred (not
manufactured) but never reached an admitted Visit either, so multi-subject
Visit-grouping correctness remains completely unexercised end-to-end
across two consecutive post-fix cohorts now, for two different reasons (v5:
nothing happened to be concurrent among what *was* admitted; v6: nothing
was admitted at all). Two bounded, tested, own-session deploy-tooling
defects were found and fixed along the way (a real `UnicodeDecodeError`
crash in `_run_powershell`'s non-UTF-8 PowerShell-output handling that was
masking a real, unrelated failure, proven RED->GREEN with a new hermetic
regression test; a separate, disclosed-not-fixed `--dev-root` WSL-path
usability gap that caused the underlying masked failure) -- zero product/
perception/admission/Visit/evidence/classification code touched; full
`tests/test_deploy_windows_dev.py` 124/124 passed, `ruff` clean. Per the
milestone's own explicit §14 failure conditions ("prolonged real sustained
activity + `candidates_created` remains zero" is explicitly met) and its
own §35 acceptance bar ("post-fix admission behavior replicates"/
"in-session admissions occur" are both explicit Classification A
requirements that did not hold), this report deliberately does not round
up to Classification A on the strength of the investigation's own rigor
alone -- see the report's own "Decision" section for the complete
reasoning. This closure does **not** authorize the next Representative
Field Acceptance / Gate A session, External Pre-Release Acceptance, or
Final Release Hardening, and does **not** select a next development
milestone. **Remaining Gate A dependency, in priority order, superseding
the priority order the prior reconciliation above named:** (1) fix and
then field-re-prove the evidence-cache-exhaustion/no-runner-up-fallback
mechanism this session concretely measured -- now the single most
consequential open Gate A correctness question; (2) a daylight session
that actually achieves real in-session admissions *and* genuine concurrent
multi-subject siblings, still never jointly observed; (3) background/
empty-evidence eligibility remains field-unproven a second time (not
urgent -- the fix's own dedicated milestone already validated it
thoroughly via reproducer plus real-cohort benchmark; still open as live
confirmation); (4) the four still-immature numeric budgets (recall,
false-Visit rate, fragmentation/duplicate rate, capture-to-visible
latency) remain resting on v5's own single post-fix data point --
unchanged, not converged, by this session's own zero-admission result.
No numeric budget is withdrawn or newly proposed by this reconciliation --
monitoring coverage (~99.4% this session) remains consistent with its
existing ~99% candidate; useful-evidence rate is neither confirmed nor
refuted (no admitted Visits to measure it over) and its existing ~85%
candidate is unchanged.

**Pending-Proposal Evidence Preservation & Arbitration Fallback
Correctness v1 (2026-08-31) closes dependency (1) immediately above, at
classification A -- see §1/§3, above, and
[pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md](pending-proposal-evidence-preservation-arbitration-fallback-correctness-v1-report.md)
for the complete record.** The evidence-cache-exhaustion/no-runner-up-
fallback mechanism v6 concretely measured is fixed: bounded, pending-
proposal-aware preservation and deterministic same-component fallback,
both implemented and independently tested, deterministically reproduced
(both required RED reproducers plus a 105-simulated-minute v6-shaped
replay against the real bounded cache, all RED on `b37656d`/GREEN after
the fix). This is a deterministic, implementation-level closure only --
per this milestone's own explicit non-goal, no field session ran, so
dependency (1)'s own second half ("...then field-re-prove") remains
genuinely outstanding, now promoted to the single most important
remaining item below. **Remaining Gate A dependency, in priority order,
superseding the priority order immediately above:** (1) a daylight
session that actually achieves non-zero in-session `candidates_created`
under sustained real activity -- the field proof this fix's own
deterministic reproduction cannot itself provide, and the core open
question three consecutive real cohorts (v4, v5's own partial success,
v6) have now circled around for three different underlying reasons; (2)
that same session, or a later one, jointly observing real in-session
admissions *and* genuine concurrent multi-subject siblings, still never
jointly observed across any real cohort to date; (3) background/
empty-evidence eligibility remains field-unproven a second time (not
urgent -- unchanged from the prior reconciliation's own reasoning); (4)
the four still-immature numeric budgets (recall, false-Visit rate,
fragmentation/duplicate rate, capture-to-visible latency) remain resting
on v5's own single post-fix data point, unchanged by this closure (a pure
implementation-correctness milestone with no field session provides no
new data point for any of the four). No numeric budget is withdrawn or
newly proposed by this reconciliation. Gate A/Lane R remains open. This
closure does **not** authorize the next Representative Field Acceptance /
Gate A session, External Pre-Release Acceptance, or Final Release
Hardening, and does **not** select a next development milestone --
authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged, per §3, above.

**Representative Daylight Gate A Field Acceptance v7 -- Evidence-Preservation
/ Arbitration-Fallback Re-Proof (2026-08-31) ran the field session the
pending-proposal fix's own report named as outstanding, at classification
**A** -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v7-report.md](representative-daylight-gate-a-field-acceptance-v7-report.md)
for the complete record.** Deployed a genuinely fresh, disposable instance
(not the operator's own identity), re-pairing the reference Camera Node via
the identical documented recovery flow v4/v5/v6 each used, with the user's
explicit approval. A real ~89.4-minute Observation session followed against
the same real Stream/scene, with the independent acceptance recorder running
throughout (99.989% temporal-span coverage, 3,848 frames) after a real
deploy-tooling defect (found and fixed in its own commit, zero product code
touched) that had left it silently unarmed for a discarded ~2m26s preliminary
session. `candidates_created` reached its first real admission ~6.6 minutes
into the session and climbed steadily throughout to **25** by session end
(24 in-session, 1 rescued by stop-finalization) -- directly reversing v6's
own zero and exceeding v5's own 19. Six real, natural fallback attempts
occurred (five admitted, one honestly exhausted), three fully reconstructed
end to end against the real counterfactual ledger (merged losslessly across
11 periodic snapshots to survive the ledger's own 60-minute eviction window
over an 89-minute session): in each of the two successes, the highest-
confidence component member failed at the evidence-availability gate exactly
as v6 diagnosed, and the runtime's own next-ranked member was admitted
within tens of milliseconds, in the same tick; in the one exhaustion, both
members of a two-member component carried extremely weak evidence
(confirmed, on direct visual review, to be genuine noise, not a real
missed animal), and the mechanism correctly gave up rather than fabricate an
admission. **Zero instances of the unacceptable "component silently
discarded while a viable member exists" outcome were found anywhere directly
traced.** `blocked_missing_evidence` fell from v6's own 18.3% to **9.4%** (18
of 192 distinct proposals), roughly halved. Genuine concurrent multi-subject
admission was directly visually confirmed for the first time across any Gate
A cohort -- two independent sibling-Event pairs, each with disjoint
underlying tracker evidence, one pair's own admission additionally requiring
the fallback mechanism at the same time (the first observed interaction
between the two previously-separately-proved mechanisms) -- closing the
other half of the "Remaining Gate A dependency" the prior reconciliation
named. A real, first-ever exercise of the pre-existing
`max_candidates_per_hour: 20` rolling budget occurred (no prior cohort ever
produced enough real admissions to reach it) and was confirmed to
self-clear correctly, not stick. All 25 admitted Visits were individually
reviewed against real, native-resolution recorder frames (not a sample):
96.0% useful-evidence rate (24/25), and one real, confirmed false Visit
(empty background, correctly receiving no automatic species label under the
already-accepted geometry-corroboration fix -- the false *admission* itself,
not a false *label*, is the still-open, unaffected-by-this-milestone Gate B/
admission-precision residual `roadmap.md` already names). Zero genuine
duplicate Visits across all 25 admissions, verified by the strongest test
applied to any cohort to date (zero tracker evidence shared between any two
admitted Visits). Two exhaustive-denominator windows (6.5 minutes and 70
seconds, deliberately this session's own hardest moments -- both fallback
events, the exhaustion, and the multi-subject admission, not a favorable
sample) found 3 of 3 real encounters represented by a useful admitted Visit.
Zero persistence contention, zero `blocked_shadow_mode`, zero ERROR/
CRITICAL/WARNING lines across the full session log. Honestly disclosed, not
treated as a regression: a concrete field instance of the already-named,
not-yet-benchmarked crowded-feeder/NMS gap (a third real, simultaneous bird,
directly visually confirmed, that the detector itself never separately
perceived -- most plausibly NMS suppression at close range, per `roadmap.md`
Gate A's own already-recorded open dimension). This closure does **not**
authorize the next Representative Field Acceptance / Gate A session,
External Pre-Release Acceptance, or Final Release Hardening, and does
**not** select a next development milestone. **Two further numeric budget
dimensions move to READY FOR FORMAL BUDGET REVIEW** (maximum false-Visit
rate, candidate ~5-10%, from two convergent post-fix measurements: v5's 5.3%
and this session's own 4.0%; maximum duplicate-Visit rate, candidate ~0%/low
single digits, from two convergent zero measurements), alongside the two
already-proposed dimensions this session's own measurements strengthen
(monitoring coverage ~99%, now a 5th convergent cohort at 99.989%;
useful-evidence rate ~85%, now a 3rd convergent post-fix cohort at 96.0%) --
`roadmap.md` "Numeric release budgets" itself is not updated by this
reconciliation, per this milestone's own explicit scope. Minimum end-to-end
Visit recall and maximum fragmentation rate remain evidence-accumulated
only -- this session's own 3/3 exhaustive-window recall and its own
zero-shared-evidence duplicate/fragmentation test are real, positive,
convergent-direction data points, but methodologically distinct from v5's
own full-session-review recall figure and its own `cluster_encounters`-based
fragmentation figure respectively, so neither is yet a second directly
comparable number. Maximum capture-to-visible-Visit latency remains
unmeasured by any cohort to date. **Remaining Gate A dependency, in priority
order, superseding the priority order immediately above:** (1) a
directly-comparable second fragmentation-rate measurement (an offline pass
over this session's own already-preserved merged ledger, not a new field
session, could close this); (2) a second live cohort producing a genuinely
crowded, 3+-simultaneous-subject moment, to stress-test whether the
disclosed crowded-feeder/NMS gap recurs, worsens, or is scene-specific; (3)
true user-visible (capture-to-browser) latency instrumentation (a frontend-
side addition, not a field-session-only fix); (4) the ~13
`blocked_missing_evidence` records outside this session's own two
exhaustive windows remain individually untraced to their own component/
rescue context (also closeable via an offline pass over the already-
preserved merged ledger); (5) the already-known, unaffected-by-this-
milestone Gate B/admission-precision residual (a background/empty crop can
still become a real, if unlabeled, false Visit) remains open exactly as
`roadmap.md` already frames it. **Per this milestone's own explicit
instruction, Gate A is not self-closed by this session -- closure requires
external (ChatGPT) review of the accumulated evidence across all real
cohorts to date.** Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged.

**Gate A Measurement Closure v1 -- Fragmentation Accounting & True
User-Visible Latency Instrumentation (2026-08-31)** directly closes
dependency items (1) and (3) named immediately above -- see §1/§3, above,
and
[gate-a-measurement-closure-fragmentation-latency-v1-report.md](gate-a-measurement-closure-fragmentation-latency-v1-report.md)
for the complete record. Classification **A**. A dedicated offline pass
reapplying corrected, human-reviewable fragmentation accounting
(`fragmentation_accounting.py`, new) against v7's own already-preserved
merged ledger -- recovered from the original field session's own local
scratchpad directory and archived under `data/field-acceptance/2026-08-31-
gate-a-v7-measurement-closure-reanalysis/` for future reproducibility,
exactly as item (1) itself proposed -- resolves 7 of v7's own 10
denominator units (5 auto-confident, plus the two directly-visually
-confirmed multi-subject sibling pairs already named above, applied here
as sourced reviewer overrides) with **zero confirmed fragmentation**,
leaving 3 genuinely ambiguous (one of them the same sustained mega-cluster
this reconciliation's own "duplicate_visit_cluster_count: 5 and
fragmented_cluster_count: 17 (of 27 total encounter clusters)" raw-signal
caveat, above, already named as a methodology problem, not a defect). The
2026-08-19 primary cohort and v5 (as-previously-published) independently
show the identical zero-confirmed-fragmentation result under the same now
-consistent methodology -- three convergent cohorts move fragmentation to
**READY FOR FORMAL BUDGET REVIEW**, candidate ~0%/low single digits.
Item (3) (true user-visible latency instrumentation) is now fully defined
and implemented (T0 -> `decided_at`, T2-T5's own collapse into one
existing Host-domain value proven, not assumed, by a new repository-level
test; fallback-timestamp correctness independently proven at two layers,
including a new `engine_runtime.py` persistence-boundary test) -- but
**remains MEASUREMENT CONTRACT CLOSED / MORE FIELD EVIDENCE REQUIRED**:
v7's own preserved ledger predates the new field entirely, so every one of
its 25 admitted proposals' latency samples honestly reports
`unavailable_capture_time` when run through the new tooling, confirmed
directly rather than inferred -- the same true of the 2026-08-19 and v6
cohorts. A next field session run against post-this-milestone accepted
HEAD would be the first to produce real measured samples. Item (2) (a
second live cohort producing genuinely crowded 3+-simultaneous-subject
activity, to stress-test the disclosed crowded-feeder/NMS gap) and item
(5) (the already-known Gate B admission-precision residual) remain open,
unaffected by this milestone's own explicit scope; item (4) (~13 untraced
`blocked_missing_evidence` records) remains open, not attempted here.
Per this milestone's own explicit instruction, neither budget is accepted,
and Gate A is not self-closed by this closure -- closure requires external
(ChatGPT) review of the accumulated evidence, exactly as before. Schema
unchanged (`v58`). Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; this closure does not authorize the
next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening. **Remaining Gate A
dependency, in priority order, superseding the priority order immediately
above:** (1) real capture-to-visible latency field samples -- the single
item this milestone's own new instrumentation cannot retroactively
supply; any ordinary daylight session run against accepted HEAD after this
milestone closes it; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged from above); (3) a bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (`visit-observation-candidate-015/-016/-
017` and `-027/-028`) -- recorder frames already archived, not attempted
here as out of this milestone's own measurement-contract scope; (4) the
~13 untraced `blocked_missing_evidence` records (unchanged from above);
(5) the already-known Gate B admission-precision residual (unchanged from
above).

**Camera Node -> Host Clock Normalization for True Capture-to-Visible
Latency v1 (2026-08-31)** does not supply item (1) above (that still
requires an actual field session, not run here) -- it instead closes a
precondition item (1)'s own eventual fulfillment was silently resting on:
Gate A Measurement Closure v1's own T0 -> `decided_at` figure subtracted a
Camera Node-domain timestamp from a Host-domain one, disclosed via a fixed
caveat string but never proven safe, and a real ~39-second discrepancy
found in v7's own data was cited as justification for that caveat without
ever being root-caused. See
[camera-node-host-clock-normalization-latency-v1-report.md](camera-node-host-clock-normalization-latency-v1-report.md)
for the complete record. Classification **A**. Directly re-measured the
~39s figure against v7's own preserved raw ledger (recovered by Gate A
Measurement Closure v1, still present) and proved it was never evidence of
a Node-Host clock offset at all -- both operands of that original
comparison (`source_offset_ms`, `captured_at`) are Node-domain-labeled
fields on the same record, so nothing Host-side ever entered it; the real
Node-Host offset (`node_to_host_clock_offset_ms`, computed per frame in
`camera_node_live.py` since before this milestone) has never been durably
captured by any prior cohort, a fact now closed rather than merely
disclosed. New pure module `clock_calibration.py` supplies a bounded,
session-scoped one-way-delay calibration (point estimate: minimum observed
delta; uncertainty: observed spread -- no round trip exists in the current
push-only analysis-stream protocol, so none is invented) with drift
observation and clock-jump detection/invalidation (a disclosed 5-second
threshold, tested in both directions, never interpolated or extrapolated
across a detected jump). `capture_to_visible_latency.py`'s `LatencyState`
gains a fourth, structurally distinct value, `invalid_clock_mapping` -- a
required mapping that does not exist now honestly rejects the sample
rather than silently subtracting across an unproven clock boundary --
gated behind a new `clock_calibration_required` parameter defaulting to
`False` (exactly pre-milestone behavior, proven unaffected: all 11 of Gate
A Measurement Closure v1's own existing tests pass byte-for-byte
unchanged) and set `True` only for a real Camera Node session
(`provider_key == "camera_node"`; an RTSP/local/USB source structurally
never has this problem and is untouched). Fallback/stop-finalization/
multi-subject correctness independently re-proven under normalization,
including one deliberately discriminating fallback test (a clock jump
placed between the winner's and the admitted fallback member's own
calibration epochs, which would fail under a cross-proposal contamination
bug). Zero Camera Node/wire-protocol changes -- every input already
existed on both sides before this milestone; every schema/response change
is additive and defaulted. Schema unchanged (`v58`) -- nothing here is
persisted to SQLAlchemy. Tier 1 (285) + Tier 2 (266) = 551 tests passed, 0
failed, run together in one invocation; zero new ruff findings (one
pre-existing finding incidentally fixed). Does not reopen fragmentation
accounting, does not tune models/detectors, does not run a field cohort.
**Capture-to-visible latency remains MORE FIELD EVIDENCE REQUIRED,
unchanged in kind but now for a materially stronger reason: the
measurement mechanism itself is closed and correct, not merely defined.**
Every historical cohort (2026-08-19, v6, v7) still predates `clock_
calibration.py` entirely and is not, and cannot be, retroactively fixed
(stated explicitly, not inferred around) -- a next field session run
against post-this-milestone accepted HEAD would be the first able to
produce a real, validly-normalized T0 -> T5 distribution. Authorization
remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**,
unchanged; this closure does not authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening, and does not select a next development milestone.
**Remaining Gate A dependency, unchanged in priority order and in every
item's own substance -- only item (1)'s own bar is now sharper:** (1) real,
*validly clock-normalized* capture-to-visible latency field samples (not
merely "field samples" -- the measurement mechanism they would need is now
closed; the samples themselves still do not exist); (2) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (3) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(4) the ~13 untraced `blocked_missing_evidence` records (unchanged); (5)
the already-known Gate B admission-precision residual (unchanged).

**Camera Node <-> Host RTT-Bounded Clock Calibration v1 (2026-09-01)**
does not itself run a field session -- it closes the absolute Node-Host
offset/error-bound measurement gap the immediately-preceding milestone's
own report named as still open: that milestone's own one-way estimator
(`offset_ms = min(deltas)`) is, by construction, only ever a one-sided
upper bound on the true offset, never a defensible two-sided error bound.
See
[camera-node-host-rtt-bounded-clock-calibration-v1-report.md](camera-node-host-rtt-bounded-clock-calibration-v1-report.md)
for the complete record. Classification **A**. Reuses the existing `GET
/node/v1/health` request/response operation (two additive response
fields, `node_receive_time`/`node_time`) rather than a new time-sync
protocol -- correcting, in place, the immediately-preceding milestone's
own "no request/response exchange exists" framing (correct for the
one-way analysis-stream push specifically, incorrectly generalized to the
whole Camera Node protocol; `docs/camera-node-live-shadow-contract.md` is
corrected the same way). A rigorously-derived two-sided offset interval
(`[offset_min_ms, offset_max_ms]`, from the honest inequalities "request
left before the Node's own receive timestamp" / "response arrived after
the Node's own send timestamp," never a symmetric-delay NTP formula) is
now the sole input `capture_to_visible_latency.py` normalizes T0 through;
the accepted one-way estimator is not discarded -- it continues, unchanged,
as the *relative* drift/jump monitor that decides when a live session
spends the cost of a fresh RTT-bounded batch, one of four recalibration
triggers (session start; a disclosed 5-minute bounded periodic cadence;
detected reconnect; a one-way-detected jump). Every latency sample now
carries the full interval (`latency_min_ms`/`latency_max_ms`), never only
a collapsed point estimate -- re-proved directly against fallback,
stop-finalization, and multi-subject-sibling scenarios, each now asserting
the interval itself, not only the point estimate, and the min/max
inversion (earliest possible t0 yields the *largest* possible latency)
verified at two independent layers. A real regression -- a sequential
5-attempt calibration batch against an unreachable Node blocking a live
session's own frame-processing tick for up to ~10 seconds -- was found via
a genuinely failing pre-existing end-to-end test during this milestone's
own work and fixed (concurrent batch attempts; the first calibration
triggered at the first ordinary tick rather than gating session start).
Zero Camera Node/wire-protocol breaking changes -- an old Node's response
simply lacks the two new keys, degrading honestly to `insufficient_
samples` at every layer, never a crash. Schema unchanged (`v58`). Tier 1
(404) + Tier 2 (670, combined) + Tier 3 (full Core gate, run because this
milestone -- unlike the immediately-preceding one -- adds genuinely new
runtime network I/O to the live engine loop): 5487 passed, 3 failed (all 3
independently confirmed pre-existing/unrelated by fresh baseline
bisection -- the recurring `test_place_biodiversity_summary_repository.py`
pair, plus one real-clock/local-day-boundary test whose own run happened
to straddle the actual midnight rollover into 2026-09-01), 3 skipped, 23
deselected, 11 xfailed; zero new ruff findings. **Absolute Node<->Host
clock-calibration state moves from OPEN to CLOSED.** **Capture-to-visible
latency remains MORE FIELD EVIDENCE REQUIRED, unchanged in kind but now
for a materially stronger reason a second time**: the measurement
mechanism is now both closed and correct/defensible, not merely closed;
every historical cohort (2026-08-19, v6, v7) still predates `rtt_clock_
calibrations` entirely and cannot be retroactively fixed. Does not reopen
fragmentation accounting, does not tune models/detectors, does not run a
field cohort. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged; this closure does not authorize the
next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does not select a
next development milestone. **Remaining Gate A dependency, unchanged in
priority order and in every item's own substance -- only item (1)'s own
bar is now sharper a second time:** (1) real, *validly RTT-normalized*
capture-to-visible latency field samples -- the measurement mechanism is
now both closed and defensible; the samples themselves still do not
exist; (2) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged); (3) the bounded
visual-review pass against v7's own two remaining genuinely-unreviewed
ambiguous fragmentation units (unchanged); (4) the ~13 untraced
`blocked_missing_evidence` records (unchanged); (5) the already-known Gate
B admission-precision residual (unchanged).

**Reference Camera Node RTT-Capability Upgrade & Compatibility Re-Proof v1
(2026-09-01)** closes the Camera Node upgrade dependency the v8 entry
immediately below named as Gate A's own sharpest remaining item -- see
[reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md](reference-camera-node-rtt-capability-upgrade-compatibility-reproof-v1-report.md)
for the complete record. Classification **A**. The real reference Camera
Node was upgraded end to end via the accepted `scripts/install_camera_
node.py` mechanism (build against accepted HEAD `1a39479` -> preflight ->
install) from `git_commit baf9fdb` (71 commits behind, predating the RTT
protocol) to `git_commit 1a39479` itself, with zero unexpected config/data
loss and pairing preserved intact through the upgrade itself. Pre-upgrade
RED and post-upgrade GREEN both confirmed live against the real device
(`node_receive_time`/`node_time` absent, then present/valid/advancing).
Running the real, unmodified production RTT functions directly against
the upgraded Node produced **6 of 6 valid calibration batches (30 round
trips, ~3.35 real minutes)** -- the first real, valid RTT-bounded
calibration evidence to exist since the protocol was accepted; v8's own
796-batch, 0-valid session is now understood as an infrastructure gap,
already closed, not a mechanism defect. A real camera smoke test (fresh
disposable CPU-only Host instance, no Windows/GPU needed) drove a real
pairing, camera-setup completion, and three real advancing 1920x1080 live
frames through the actual Host API, visually confirmed as real reference
-yard footage -- this deliberately, transparently, and with real-time user
approval displaced the stale pairing v8's own session had left in place,
after the environment's own safety layer correctly declined to let that
proceed without asking. Doctor ran clean for this milestone's scope; no
dedicated "old Node version" warning exists anywhere in Doctor to have
newly cleared (there was never one). Newly, independently root-caused: no
automated mechanism anywhere in the release process checks Camera-Node
-build-vs-Host-build compatibility before a Gate A session begins --
disclosed, not fixed (explicit non-goal: no fleet-management feature).
No production code changed; no tests invented (real-hardware validation is
this milestone's own validation). Authorization remains **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged; does not authorize
the next Representative Field Acceptance / Gate A session, External
Pre-Release Acceptance, or Final Release Hardening, and does not select a
next development milestone. **Remaining Gate A dependency, in priority
order, superseding the priority order in the v8 entry immediately below:**
(1) the first real, *validly RTT-normalized* T0->T5 capture-to-visible
latency field distribution -- the Node, Host, and calibration mechanism
are now all proven ready; only a live field session's own real samples
are missing; (2) reconciling the now-diverged false-Visit-rate/
useful-evidence-rate evidence body (v5/v7 vs. v8) (unchanged); (3) a
second live cohort producing genuinely crowded 3+-simultaneous-subject
activity (unchanged); (4) the bounded visual-review pass against v7's own
two remaining genuinely-unreviewed ambiguous fragmentation units
(unchanged); (5) the ~13 untraced `blocked_missing_evidence` records, v7's
own (unchanged); (6) the already-known Gate B admission-precision residual
(unchanged).

**Representative Daylight Gate A Field Acceptance v8 -- True-Latency &
Crowding Closure Tranche (2026-09-01) ran the first field session against
post-RTT-calibration accepted HEAD, at classification **B** -- see §1/§3,
above, and
[representative-daylight-gate-a-field-acceptance-v8-report.md](representative-daylight-gate-a-field-acceptance-v8-report.md)
for the complete record.** A real, live 158.2-minute Observation session
(longer than the 60-120 minute target, disclosed) against the same real
reference Camera Node produced the highest `candidates_created` of any
cohort to date (27, all in-session), the first-ever fully-resolved
(zero-residual-ambiguous) fragmentation accounting (16/16
`correctly_represented`, a fourth/fifth convergent 0% cohort), the
deepest fallback chain yet observed (position 3 of 3), and
`blocked_missing_evidence` (9.9%, 21/212) closely replicating v7's own
9.4% at nearly double the distinct-proposal volume -- a real second,
independently-varied confirmation the Preservation/Fallback fix holds at
scale. Zero persistence contention; honest, clean stop-finalization.
**Item (1) above remains not closed, for a real, precisely root-caused
reason:** zero of 796 attempted RTT-bounded calibration batches produced
a valid sample (all `insufficient_samples`) because the reference Camera
Node's own installed software (`git_commit baf9fdb`, built 2026-08-27,
confirmed 69 commits behind current HEAD via `git merge-base
--is-ancestor`, and confirmed via direct `grep` to contain neither of the
two response fields the RTT protocol depends on) has not been redeployed
since the "Camera Node Upgrade & Compatibility Recovery v1" milestone
(2026-08-26) -- across five field-relevant milestones accepted since, none
of which touched the physical Node. Not fixed live: doing so mid-session
would have forced a reconnect (explicitly prohibited by this milestone's
own governing brief) and risked contaminating already-collected
measurements. The unaffected one-way drift/jump monitor returned a
complete, fully valid record (796/796 `calibrated`, stable 85-244ms
offset, zero jumps) -- real positive evidence of a stable underlying clock
relationship, not a substitute for the missing two-sided bound. Item (2)
(3+-subject crowding) remains unmet; a second candidate 2-subject pair
(Visits 021/022) was found but not visually confirmable (outside the
session's own recorder coverage window). **A new, materially reopening
finding, from direct pixel-region inspection of every low-confidence
admitted Visit's own recorded bounding box (matching the v5 report's own
established method):** 6 of 27 admitted Visits (22.2%) are false or
likely-false (empty background, clustered at one recurring weak-signal
screen location) -- materially exceeding v5 (5.3%) and v7 (4.0%), whose
own convergence previously supported a candidate false-Visit budget. That
candidate, and the directly-downstream useful-evidence-rate candidate, are
**withdrawn pending more evidence**, not reaffirmed, per this session's own
report ("Budget maturity"/"Candidate budgets") -- `roadmap.md` itself is not
edited by this reconciliation, per this milestone's own explicit scope
(release-execution-state.md only); a future reconciliation should confirm
whether `roadmap.md`'s own "Numeric release budgets" text already reflects
v7's own candidate proposals or still needs updating before this
withdrawal is reflected there too. Gate B's
own abstention behavior held cleanly throughout (zero confidently-wrong
species labels on any false Visit). The same rigorous check also reversed
this session's own initial working hypothesis that Visits 010/011
constituted directly-confirmed 2-subject crowding -- both are, in fact,
false detections sharing the same structural/temporal signature genuine
concurrent siblings would show, a disclosed methodological finding in its
own right. One real, previously-undiagnosed root cause was found for the
storage decline `roadmap.md`/this file had disclosed but not explained
since 2026-08-28: every prior field-acceptance disposable instance was
left running/retained indefinitely after acceptance, none ever cleaned up
-- mitigated for this session via two user-approved decisions (documented
in the report's own "Defects"), left at ~3.5GB free post-session, needing
attention before any near-term next session. No production code was
changed; Core was not run (no-code-change field session, per this
milestone's own explicit instruction) -- identity/schema/product-visible
results were independently validated live instead. This closure does
**not** authorize the next Representative Field Acceptance / Gate A
session, External Pre-Release Acceptance, or Final Release Hardening, and
does **not** select a next development milestone. Per this milestone's
own explicit instruction, Gate A is **not** self-closed by this report.
Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
REQUIRED**, unchanged. **Remaining Gate A dependency, in priority order,
superseding the priority order immediately above:** (1) a Camera Node
software upgrade (via the already-accepted, already-validated upgrade
procedure) followed by a field session, to obtain the first real valid
RTT-bounded calibration samples and true T0->T5 latency distribution --
now the single most consequential, precisely-scoped remaining Gate A
dependency, a materially narrower ask than "more field evidence required"
was before this milestone; (2) reconciling the now-diverged
false-Visit-rate/useful-evidence-rate evidence body (v5/v7 vs. v8) before
either budget can be responsibly proposed -- likely via one or more
further cohorts, not by discarding v8's own result; (3) a second live
cohort producing genuinely crowded 3+-simultaneous-subject activity
(unchanged); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged --
out of this milestone's own scope, not attempted here); (5) the ~13
untraced `blocked_missing_evidence` records, v7's own (unchanged -- v7's
raw evidence, recovered and archived this session for the first time, at
`data/field-acceptance/2026-08-31-gate-a-v7-raw-recorder-and-ledger-preservation/`,
remains available for that separate, still-open task); (6) the
already-known Gate B admission-precision residual (unchanged).

**Representative Daylight Gate A Field Acceptance v9 -- True-Latency &
Precision Reconciliation Tranche (2026-09-01) ran the field session item
(1) above named as the single most consequential remaining dependency, at
classification **A** -- see §1/§3, above, and
[representative-daylight-gate-a-field-acceptance-v9-report.md](representative-daylight-gate-a-field-acceptance-v9-report.md)
for the complete record.** A real ~97.1-minute Observation session against
the same real reference Camera Node, with the independent acceptance
recorder confirmed armed and writing real frames within ~4.2 minutes
(97.95% coverage, 2,353 files). **Item (1) closed:** 447/460 in-session
RTT-bounded batches `calibrated` (0 inconsistent, 0 jumps), 24/25 admitted
Visits produced a real measured T0->T5 latency sample (median 111,811ms,
p90 173,944ms, max 307,373ms) -- the first real, defensible latency
distribution in Gate A's history, root-caused via an additive tail-latency
decomposition to the accepted Visit-Continuity/episode-boundary quiet
-period design (a tight ~48-60s tail regardless of encounter length,
directly confirmed on individual proposals' own `blocked_continuation_
pending` revision histories), not pipeline inefficiency. **Item (2)
(reconciling the diverged false-Visit-rate/useful-evidence-rate evidence
body) now has a determinate answer:** direct multi-frame pixel-region
inspection found 5/25 (20.0%) confirmed false, closely replicating v8's
22.2% and materially diverging from v5 (5.3%)/v7 (4.0%) -- **v8's
elevated rate reproduces, a real, reproducible scene characteristic, not
a cohort anomaly.** Two distinct recurring hard-negative locations traced
in full (one a near-exact recurrence of v8's own reported location; one
new -- a feeder-cap sun-glint); the false-Visit-rate/useful-evidence-rate
candidates remain correctly withdrawn (v9's own 76.0% strict useful-
evidence rate sits below the ~85% figure v8 had already withdrawn). A
real Gate B residual instance field-confirmed for the first time since
its own governing fix was accepted (1/5 false Visits received a wrong
confident species label, root-caused to the fix's own already-disclosed
detector-sourced-evidence exclusion, not a regression). Fragmentation
reached a sixth/seventh convergent real cohort at 0% (14/14, accepted
reviewer-disposition method); duplicates a fourth convergent cohort at 0%
(0/25); `blocked_missing_evidence` a third independently-varied post-fix
confirmation (8.9%, 12/135, closely clustered with v7/v8). The rolling
hourly candidate limit activated for the second time in any cohort (6
real blocks, all high-confidence, self-cleared correctly). Direct visual
confirmation of 2 simultaneous birds at the feeder obtained (the best
2-subject evidence to date), but the detection-stage mechanism could not
be traced this session (`raw_detections` did not merge losslessly, a
disclosed gap matching v8's own). Zero persistence contention; zero
ERROR/CRITICAL/WARNING/Traceback lines in the full structured log. One
real, reproducible product defect found via live product usage (not
fixed, out of scope, a precise bounded next DEV contract named in the
report): `POST /api/review-labels` with `review_origin=agent_diagnostic`
and no `reviewer_identity` correctly raises `ReviewProvenanceError`, but
`create_review_label` only catches `ReviewRevisionConflictError`
explicitly, so this well-formed validation error propagates as an
unhandled `500` instead of a clean `400`. No production code was changed
by this milestone. This closure does **not** authorize the next
Representative Field Acceptance / Gate A session, External Pre-Release
Acceptance, or Final Release Hardening, and does **not** select a next
development milestone. Per this milestone's own explicit instruction,
Gate A is **not** self-closed by this report -- the false-Visit-rate
divergence reproducing (rather than resolving) is judged a complete,
determinate answer to this milestone's own second primary objective, but
still leaves a release-blocking open item, and true latency has exactly
one real cohort. Authorization remains **NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED**, unchanged. **Remaining Gate A dependency, in
priority order, superseding the priority order immediately above:** (1)
resolve the false-Visit-rate/useful-evidence-rate divergence itself --
now sharpened to a well-evidenced, specific candidate explanation (scene-
specific recurring hard-negative locations; the already-accepted, per-
Stream `scene_confusor_regions` mechanism exists but is currently off by
default for this Stream) rather than an unexplained scatter, but not yet
confirmed as the actual explanation nor addressed -- the single most
consequential remaining Gate A dependency; (2) a second, independently-
varied true-latency cohort (Gate A's own standing rule requires cross-
session convergence before any number is proposed; ideally at a
materially different time of day/season, to test whether the ~48-60s
tail-latency constant and the encounter-duration-dominated distribution
shape both hold); (3) a second live cohort producing genuinely crowded
3+-simultaneous-subject activity (unchanged -- still not observed in any
cohort to date); (4) the bounded visual-review pass against v7's own two
remaining genuinely-unreviewed ambiguous fragmentation units (unchanged);
(5) the ~13 untraced `blocked_missing_evidence` records, v7's own
(unchanged); (6) the newly-field-confirmed Gate B detector-sourced-
evidence residual (sharpened from a theoretical gap to one concrete field
instance -- still open, not fixed this milestone); (7) the disclosed
`agent_diagnostic` review-provenance error-handling defect (bounded,
unrelated to any measurement above, a precise next DEV contract already
named).

### S. Actual Final Release Hardening

**Status:** LAST.

Final Release Hardening begins once the intended release capability set
stabilizes -- a readiness judgment, not a version-number boundary (see
"Release readiness vs. continued capability work" in
[roadmap.md](roadmap.md)). Release-critical correctness always outranks
optional capability; capability development may continue up to that point
whenever it materially improves the product without endangering a
release-critical dependency. Once Final Release Hardening begins, no
major capability is added without explicit authorization based on
concrete necessity, and focus narrows to: defects; reliability;
performance; UX; compatibility; packaging; security; documentation;
installation; upgrade/recovery; field failures; External Pre-Release
Acceptance findings; release-artifact validation; dependency/license
closure; clean-install repetition; internal release-candidate builds (an
engineering mechanic, not a separate product stage). External Pre-Release
Acceptance -> Final Release Hardening -> the one public launch -- no
separate beta release precedes it.

## 7. One-release doctrine

MockingBird's public release target is a trustworthy single-site/home
observatory with:

- dependable visual observation;
- strong Visit/evidence quality;
- reviewed Observation truth;
- Today/history usefulness;
- native Camera Node golden path;
- ONVIF + RTSP/RTSPS;
- offline/recorded/camera-trap ingest;
- professional/research acquisition metadata;
- conservation reporting;
- effort/coverage;
- research-safe export;
- Camtrap DP;
- bounded contributor/research capability;
- Local Only privacy;
- installation/onboarding/recovery;
- diagnostics;
- storage;
- backup;
- versioning;
- security;
- OSS/release presentation;
- clean-install acceptance;
- integrated field acceptance.

Acoustics may ship as the now-accepted optional capability. Remote
LTE/solar/custom field hardware are not release blockers.

## 8. After-release queue

Explicitly keep:

- complete remote/intermittent-WAN/LTE field deployment;
- solar/battery;
- custom CM4/CM5 hardware;
- research-grade remote-field acceptance;
- broad multi-site;
- native mobile;
- advanced acoustic analytics;
- mature automatic mammal species identification.

Unless new evidence creates a dependency, do not promote these into
release scope.

## 9. Later / demand-driven queue

Examples:

- GenICam;
- GigE Vision;
- USB3 Vision;
- radiometric thermal;
- specialized industrial cameras;
- individual-animal recognition;
- population estimates;
- behavior prediction;
- causal ecological modeling;
- large cloud-first infrastructure.

## 10. Observability cross-cutting requirements

Keep visible as release requirements:

- structured error taxonomy;
- stable machine-readable codes;
- user-safe messages/actions;
- component attribution;
- recoverability;
- correlation/session identifiers where applicable;
- structured bounded logs;
- health transitions;
- reconnect/drop/failure counters;
- Visit/model/storage/coverage counters;
- support bundles;
- no uncontrolled raw/high-cardinality media telemetry.

Normal users get actionable diagnostics. Advanced support gets raw
details.

## 11. API / schema / version compatibility

Preserve:

- externally consumed schema/version discipline;
- additive compatibility where feasible;
- migration safety;
- Host ↔ Camera Node compatibility;
- upgrade/recovery semantics;
- explicit capability/version reporting.

Do not casually make breaking changes merely because all local tests can
be updated together.

## 12. Security / release questions

Keep visible:

- network exposure;
- HTTPS/TLS posture;
- secure remote-access decision;
- secret/credential storage;
- dependency/model supply chain;
- checksum/update verification;
- support-bundle disclosure;
- public SECURITY policy.

Do not claim encrypted camera/RTSP/ONVIF credentials at rest unless
current code proves it.

## 13. Development operating rules

**Bounded archaeology.** Start with governing docs and directly affected
code. Expand only when evidence reveals dependencies.

**Separate investigation and implementation.** When uncertainty is real:
(1) diagnose; (2) lock the contract; (3) implement.

**Validation tiers.** Tier 1: focused tests. Tier 2: affected subsystem
validation. Tier 3: full Core only when cross-cutting production risk
warrants it.

**Audit budget.** Default: one implementation/self-review; one acceptance
review. Additional audits require a concrete unresolved risk.

**Concurrent writers.** Never allow multiple Claude writer sessions in the
same working tree. Separate worktrees are required for parallel
implementation. Read-only agents are fine.

**Git.** Do not push without explicit user authorization. Protect the
seven preserved files (see below).

### Preserved untracked detector files

These seven known superseded/untracked detector files must remain
untouched -- not edited, deleted, renamed, staged, incorporated, or
cleaned up -- by any task working in this repository:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

They duplicate the accepted `multi_scale_strategy.py`/
`multi_scale_benchmark.py` work and were left uncommitted on purpose
rather than cleaned up; re-verify their presence untouched at the start of
each session that touches this repository.

## 14. Validation baselines

**Latest accepted Core checkpoint (Pending-Proposal Evidence Preservation
& Arbitration Fallback Correctness v1):** 5357 passed / 1 failed / 3
skipped / 11 xfailed / 23 deselected (slow-marked) -- 5372 collected via
`scripts/verify_core.py`'s own `pytest -m "not slow"` convention, **not**
a bare run (unlike the immediately-prior checkpoint below, noted
honestly: this run is not a strict superset of that one -- it deliberately
excludes the 23 `slow`-marked tests `verify_core.py` itself always
excludes). Run as four sequential-file, concurrently-executed chunks
covering the complete alphabetical test-file list with no overlap or gap
(this environment's own background-task tooling caps a single foreground
run below this suite's real ~19-minute runtime; the four chunks' own
collected-test counts sum to exactly 5372, confirming complete,
non-duplicated coverage). The one failure
(`test_temporal_capture_cli.py::test_run_capture_end_to_end_reconnect_
produces_a_native_session_timeline`) is independently confirmed unrelated,
not merely assumed: zero code-dependency relationship to any file this
milestone touched; passes cleanly on the exact pre-fix baseline (`git
stash`-isolated); passes 5/5 consecutive runs in isolation with the fix in
place; only failed once, inside the one chunk running 80 other test files
concurrently alongside three sibling chunks (12 real CPU cores, all four
chunks together saturating them) -- a genuine, pre-existing, real-wall-
clock-timing-sensitive test (its own docstring already names "Bounded
latest-frame coalescing under host backpressure," a `--duration 5`
real-time capture window) made visible only by this investigation's own
necessary concurrent chunked execution, not a product defect. See this
milestone's own "Latest accepted milestone" entry in §1, above, and its
full report's own "Validation" section for the complete account. Zero new
`ruff` findings on any touched file (2 pre-existing, unrelated findings in
`tests/test_engine_runtime.py` independently confirmed present on baseline
`b37656d` via clean-checkout bisection, left untouched). No schema change.

**Gate A Measurement Closure v1 did not run a full Core checkpoint** --
disclosed explicitly here so this is never mistaken for one. Per its own
documented Tier 3 decision (additive/narrow production-code footprint;
not warranted "solely because this is called Gate A," per its own explicit
governing instruction), it ran Tier 1 (every directly touched/new file,
including two brand-new pure modules and their own test files) + Tier 2
(every immediately affected subsystem -- candidate authority, evidence/
fallback, persistence, repository reads, API visibility, acceptance
recorder, time utilities): **440 passed, 0 failed, across 18 test files**,
zero new `ruff` findings (verified against a stashed baseline covering the
exact same file set). See its own report's "Validation"/"Tier 3" sections
for the complete file list and reasoning. The "Latest accepted Core
checkpoint" above remains the most recent actual full-suite number.

**Prior accepted Core checkpoint (Historical Species-Status ("New" vs.
"Seen Before") Correctness v1):** 5277 passed / **0 failed** / 3 skipped /
11 xfailed (37m09s -- run bare, `python3 -m pytest -q`, with no `slow`
-marker deselection, so a strict superset of every prior checkpoint cited
below). This is the first zero-failure full Core checkpoint recorded
anywhere in this section: every checkpoint immediately below, back through
"Camera / Source Experience & First-Hour Setup Closure v1," reported
exactly the same 2 failures, the `test_place_biodiversity_summary_
repository.py` pair (`test_api_route_returns_the_summary`, `test_human_
correction_updates_place_biodiversity_intelligence_correctly`), each time
independently re-confirmed pre-existing and each time correctly judged
unrelated to that session's own changes -- this milestone is the first to
have actually root-caused and fixed that pair, rather than re-bisecting
past it again. Root cause and fix: see this milestone's own "Latest
accepted milestone" entry in §1, above, and its full report. Zero other
regressions; the 231 warnings are pre-existing, unrelated stdlib/
SQLAlchemy/FastAPI deprecation notices, not new findings.

**Prior accepted Core checkpoint (Whole-Product UI / Accessibility /
Performance Closure v1):** 5166 passed / 2 failed / 3 skipped / 23
deselected (slow-marked) / 11 xfailed (26m50s), run standalone after an
earlier concurrent-with-e2e attempt produced real, directly observed
SQLite lock contention (not re-used as evidence -- see the milestone
report's "A note on validation methodology"). Both failures are the
identical, already-documented pre-existing `test_place_biodiversity_
summary_repository.py` pair (`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`),
independently re-confirmed as pre-existing across now at least nine
consecutive prior milestone checkpoints below -- not re-bisected again
this session given zero code this milestone touched has any relationship
to biodiversity-summary computation. No schema change, so no guard-rail
assertions needed touching. 7 new backend tests across two files (2 in
`tests/test_review_queue_product_mode.py`, 5 in `tests/test_product_
health.py`), each independently RED-confirmed against the pre-fix code
via `git stash` and GREEN after; `ruff check` confirmed zero new findings
via a direct clean-baseline bisection per touched file (83 pre-existing
findings total, unchanged before/after: `main.py` 26/26,
`product_repository.py` 57/57); `tsc --noEmit`/`vite build` clean. Full
e2e suite (136 specs, 8 new -- 2 new spec files plus 6 added to the
existing viewport matrix): 135 passed / 1 failed, the one failure the
same pre-existing, now precisely-diagnosed `reviewed-product-loop.spec.ts`
gap immediately below in this same list, independently reproduced
identically on the unmodified 128-spec baseline (127 passed / 1 failed,
byte-identical single assertion) -- confirming no regression from this
milestone's own product/test changes. See
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md)
for the complete record, including a real, live-verified P0 fix (Review
Queue default-tab misclassification of imported Visits), three P1 fixes
(two Fast Review keyboard focus-management defects, the acoustic health/
status gap), and two investigated-and-confirmed-not-regressions
(Stream Detail/Analytics list bounding, both intact).

**Prior accepted Core checkpoint (Multi-Camera Place Experience v2):**
5106 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (26m48s). Both failures are the identical, already-documented
pre-existing `test_place_biodiversity_summary_repository.py` pair
(`'seen_before' == 'new'` assertion mismatch) below, re-confirmed this
session. A first full Core run this session (5103 passed / 5 failed)
surfaced 3 genuinely new failures beyond that pre-existing pair, all
traced to the same root cause -- this milestone's own first attempt at
its archived-camera-history fix had made `place_activity_report`'s
*unfiltered default* archived-inclusive too, contradicting a real,
pre-existing, deliberately-authored test from the already-accepted
"Gate C -- Meaningful Change Detection / Baseline Comparison v1" milestone
(`test_place_change_summary_repository.py::test_archived_stream_
confirmations_are_excluded` and `test_historical_baseline_repository.py`'s
own identically-named test) that this session's own narrower Tier 1
re-runs had not included in scope. Corrected precisely (the unfiltered
default stays archived-exclusive, matching Bird Log/Wildlife Insights/
Biodiversity's identical default; an explicit `source_ids` selection still
reaches archived history) and reconfirmed clean by this second, full run
-- see [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)'s
"Validation" for the complete record. No schema-version guard-rail
regression (schema unchanged, so no guard-rail assertions needed
touching). 87+ new/modified tests across the directly touched files plus
two new dedicated test files (`test_multi_camera_concurrent_runtime.py`,
`test_multi_camera_place_experience_scenario.py`), all passing; `ruff
check` confirmed zero new findings via a direct clean-baseline bisection
(`git stash push -u`/pop, content-normalized comparison) both before and
after the correction above; `tsc --noEmit`/`vite build` clean; targeted
e2e (`today-report.spec.ts` 19/19, `place-activity-report.spec.ts` 3/3,
`bird-log-historical-status.spec.ts` 9/9) passing; full existing e2e suite
(128 tests) re-run at 127 passed / 1 failed, that one failure the
identical, already-independently-documented pre-existing
`reviewed-product-loop.spec.ts` gap recorded across at least three prior
milestones' own acceptance records, including `mobile-viewport-audit.
spec.ts`'s own full clean re-run (zero horizontal-overflow findings)
across exactly the surfaces this milestone modified.

**Prior accepted Core checkpoint (Ecological Interoperability & Submission
Workflows v1):** 5095 passed / 2 failed / 3 skipped / 23 deselected
(slow-marked) / 11 xfailed (27m29s). Both failures are the identical
`test_place_biodiversity_summary_repository.py` pair (`'seen_before' ==
'new'` assertion mismatch) independently re-confirmed as pre-existing
across at least eight consecutive prior milestone checkpoints below --
re-run in isolation this session and reproduced byte-identically (same two
test names, same exact assertion values), confirming the established
precedent rather than a full `git stash` bisection for code sharing zero
files or logic with this milestone. No schema-version guard-rail
regression: all 14 hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 56`
assertions across 7 files were found and bumped to `57` (the identical
class of drift every prior schema bump has tripped -- see the milestone
report). 98 new tests across eight new test files plus targeted additions
to three existing ones, all passing; `ruff check` confirmed zero new
findings via a direct line-level diff against a clean baseline (stronger
than a bisection -- every pre-existing finding reproduces byte-identically
at its new, shifted line number; an over-broad `ruff --fix` run was caught
removing ~19 unrelated pre-existing unused imports and precisely reverted
first); `tsc --noEmit`/`vite build` clean; new `ecological-destinations.
spec.ts` 5/5 passing; full existing e2e suite (127 tests) re-run with only
the one already-known pre-existing failure (`reviewed-product-loop.
spec.ts`, unrelated to this milestone, recorded across at least three
prior milestones).

**Prior accepted Core checkpoint (Calm Attention & Notifications v1):** 4991
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m02s). All 3 failures independently re-bisected this session: the two
`test_place_biodiversity_summary_repository.py` failures (identical
`'seen_before' == 'new'` mismatch, see immediately below) reproduce
byte-identically against a fresh `git stash push -u` clean-baseline run with
zero of this milestone's changes applied. The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success` -- the identical test name
already recorded as a load-induced flake in the Mobile & Remote Experience v1
checkpoint below -- passed cleanly both in isolation and as part of its own
file (7/7) when re-run directly on this milestone's own code immediately
after the full Core run, confirming the flake again rather than assuming the
precedent still held. No schema-version guard-rail regression: all 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 55` assertions across 7 files
were found and bumped to `56` (the identical class of drift every prior
schema bump has tripped -- see the milestone report). 22 new tests across two
new files (`tests/test_calm_attention.py`, `tests/test_attention_sync_
service.py`) plus one new schema-migration regression test in `tests/
test_persistence.py`, all passing; `ruff check` clean (0 new findings,
bisected file-by-file against a clean baseline); `tsc --noEmit`/`vite build`
clean; 11/11 new `notification-preferences.spec.ts` e2e tests passing
(4 of which install a fake `Notification` global and a fake clock to prove
the live-notification decision logic end to end, not only that Settings
persists a toggle); full existing e2e suite (118 tests) re-run with only the
one already-known pre-existing failure (`reviewed-product-loop.spec.ts`,
independently reproduced and unrelated to this milestone).

**Prior accepted Core checkpoint (Mobile & Remote Experience v1):** 4976
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(24m02s -- measurably longer than the historical ~9min baseline; this
sandbox was independently confirmed under real, unrelated concurrent CPU
load throughout this session via `uptime`/`ps`, not a Core-gate
regression). Two failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean pre-milestone baseline (byte-identical
failure, same `'seen_before' == 'new'` assertion mismatch, with zero of
this milestone's changes applied). The third,
`test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_
incompatibility_and_cleared_on_next_success`, has zero code relationship
to this milestone (Camera Node transport/protocol diagnostics), passed
7/7 cleanly on immediate isolated re-run, and matches an already-
documented precedent for exactly this file under exactly this condition
(the Environmental Context v2 checkpoint below recorded a different test
in this same file failing only under confirmed heavy concurrent load,
clean in isolation) -- the identical evidentiary shape, not bisected via
`git stash` a second time given that precedent and the isolation proof
already in hand. No schema change, so no guard-rail
assertions needed touching. 138 tests pass across the six directly
touched/added test files (20 genuinely new -- 2 for the Phase 0 RED/GREEN
proof, 5 for the new timing-guard parameters, 9 for the new
`/api/product/connection` endpoint, 4 for CORS -- plus 2 pre-existing
tests corrected to match the fixed behavior, their own actual claims
unaffected); `ruff check` clean
(0 new findings; the 57 pre-existing findings elsewhere in
`product_repository.py` confirmed unrelated via `git stash` bisection);
`tsc --noEmit`/`vite build` clean. Frontend e2e: new
`mobile-viewport-audit.spec.ts` 19/19 passing (10 core surfaces at
phone-viewport emulation, real seeded/imported data, zero horizontal-
overflow findings, plus a 360px/390px/768px matrix on the two densest
surfaces per Phase 25); full existing suite (112 tests, no filter) re-run
in full -- 111 passed, 1 failed, and that one failure
(`reviewed-product-loop.spec.ts`) is an independently-
reproduced, genuinely pre-existing defect (unmodified spec, run alone,
fails identically -- a `ReviewQueuePage` `product_category`/"animals"-tab
data gap, unrelated to this milestone's own changes) -- zero regressions
from the navigation/CSS changes across every other spec, including two
pre-existing mobile-specific tests.

**Prior accepted Core checkpoint (Place Story & Seasonal Timeline v1):**
4958 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (22m29s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash push -u`
bisection against the clean `950d5c2` baseline (byte-identical failure,
same `'seen_before' == 'new'` assertion mismatch, with zero of this
milestone's changes applied; `git worktree` gives invalid baselines in
this actively-shared worktree, so `git stash push -u`/`pop` was used
instead, then dropped after a diff-against-stash confirmed zero content
loss). No schema change, so no guard-rail assertions needed touching. 32
new tests (24 pure `tests/test_place_story.py` + 8 repository/HTTP
`tests/test_place_story_repository.py`); `tsc --noEmit`/`vite build`
clean; 44/44 targeted e2e passed (6 new `place-story.spec.ts` + 38
directly-adjacent re-run clean).

**Prior accepted Core checkpoint (Place Features & Habitat Change v2):**
4926 passed / 2 failed / 3 skipped / 23 deselected (slow-marked) / 11
xfailed (23m27s). Both failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
directly re-confirmed this session via a fresh `git stash` bisection
against the clean `b0bd312` baseline (byte-identical failures with zero
of this milestone's changes applied). 50 new tests in
`tests/test_place_feature.py`
(pure window-selection/maturity logic, repository CRUD, dual-write
reconciliation, real seeded before/after scenarios, real HTTP surface),
plus a new `test_persistence.py` schema-55 migration test and 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 54` guard-rail assertions
across 8 unrelated files bumped to `55` (the same class of drift the
prior two schema bumps also tripped -- see the milestone report). 30
directly-adjacent existing tests re-run clean
(`test_habitat_phenology.py`/`test_habitat_association.py`/
`test_place_activity_report.py`/
`test_place_activity_report_repository.py`/`test_source_activity.py`
actually total 174; the 30 figure is the re-run e2e count, see below).
Frontend `tsc --noEmit` and `vite build` clean; a new 7-test Playwright
spec (`e2e/place-features.spec.ts`) plus 30 directly-adjacent existing
e2e tests (`today-report`/`place-activity-report`/`biodiversity-summary`)
re-run clean.

**Prior accepted Core checkpoint (Environmental Context v2):** 4874
passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed
(26m13s). Two of the three failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below.
The third (`test_transport_worker.py::test_retryable_failure_returns_
item_to_failed_retryable_and_eventually_succeeds`) is unrelated to this
milestone (a different subsystem entirely, no shared code), reproduced
only under confirmed heavy concurrent system load, and passed cleanly
both in isolation and as part of its own file when re-run -- a transient,
load-induced flake, not a regression; see the milestone report's "Tests /
validation" for the full isolation evidence. 85 new tests across three new
pure modules plus repository/schema extensions (zero bugs found in the
three new pure modules themselves; three real bugs found and fixed in the
new repository-layer integration code during this milestone's own
test-writing); 42/42 targeted Playwright e2e tests passed. A first full
run also surfaced 10 additional failures, root-caused immediately to 14
hard-coded `CURRENT_DATABASE_SCHEMA_VERSION == 53` guard-rail assertions
across 7 files unrelated to this milestone that its own correct v53->v54
schema bump was always going to trip -- fixed by updating all 14 to `54`
(not a defect in this milestone's own migration; see the report).

**Prior accepted Core checkpoint (Place / Yard Intelligence v2):** 4791
passed / 2 failed / 2 skipped / 23 deselected (slow-marked) / 11 xfailed
(28m23s). The 2 failures are the identical, already-documented
`test_place_biodiversity_summary_repository.py` pair immediately below --
re-confirmed via a fresh `git stash` bisection against the clean `731ee30`
baseline this same session. 173 new pure-module tests added (all passing,
zero bugs found in the modules under test); 46/46 targeted Playwright e2e
tests passed after fixing one real regression found live (a pre-existing
mock fixture predating a new additive response field -- see the milestone
report).

**Prior accepted Core checkpoint (Camera / Source Experience &
First-Hour Setup Closure v1):** 4648 passed / 2 failed / 2 skipped / 11
xfailed. The 2 failures
(`test_place_biodiversity_summary_repository.py`, an unrelated
historical-status timing case) reproduced identically against the clean
`74c192a` baseline via `git stash` bisection -- confirmed pre-existing
flakiness, not a regression.

**Prior accepted Core checkpoint (Release Engineering Foundation v1):**
4633 passed / 0 failed / 0 errors. (A first full run showed 2 teardown
errors in an unrelated file; root-caused via clean-baseline bisection to
a pytest fixture-teardown-ordering interaction this milestone's own
`tests/conftest.py` change triggered, fixed at the source -- see the
milestone report's "Validation commands/results.")

**Prior accepted Core checkpoint (Acoustic milestone):** 4608 passed / 0
failed.

**Prior accepted Full checkpoint:** 4629 passed / 2 failed. Both failures
were in unrelated Camera Node real-subprocess tests and reproduced
identically on the clean baseline.

These counts are historical accepted checkpoints, not immutable future
expected totals.

## 15. Update protocol

At each accepted milestone closure, update only the delta:

- accepted HEAD;
- schema if changed;
- latest accepted milestone;
- affected lane status;
- newly discovered blocker;
- current validation checkpoint if applicable;
- field acceptance state;
- current authorized milestone only when explicitly authorized after
  global reconciliation.

Never copy a Claude "next natural milestone" suggestion directly into the
authorization field.

## 16. Transition checkpoint

- **Accepted HEAD:** `763fe22` (Multi-Camera Place Experience v2
  implementation commit)
- **Schema:** v57 -> v57, unchanged. Every fix is a query-scope correction
  or an additive field on an already-derived, never-persisted response
  object -- no new/changed table.
- **Latest accepted milestone:** Multi-Camera Place Experience v2 -- One
  Observatory, Many Views
- **Multi-Camera Place Experience v2 classification:** B -- an integrated
  multi-camera product pass on the already-accepted Camera/Source +
  Multi-Camera Maturity v1 foundation (cross-camera association engine,
  Area vocabulary, provider compatibility, health WAN-vs-camera
  disambiguation -- that milestone's own report had gone missing from this
  file's own bookkeeping despite being a real, merged, accepted ancestor
  of this HEAD; corrected here, see Lane F, above). See
  [multi-camera-place-experience-v2-report.md](multi-camera-place-experience-v2-report.md)
  for the full record: a real correctness defect (an archived camera's
  history was unreachable from every discovery surface, contradicting this
  codebase's own documented archive-only-preserves-history doctrine) found
  and fixed with principled nuance across two rounds of correction --
  Tier 1 test evidence first corrected an initial blanket overcorrection,
  then this milestone's own full Tier 3 Core run caught a second, more
  subtle one (`place_activity_report`'s unfiltered default had also become
  archived-inclusive, contradicting a real pre-existing test from the
  already-accepted "Gate C -- Meaningful Change Detection / Baseline
  Comparison v1" milestone -- see §14); the fix that shipped preserves
  every already-tested current-active-observatory default exactly (Bird
  Log overview, Wildlife Insights, Biodiversity, Place Activity
  Report/Today) while making that real history reachable by explicit
  camera/`source_ids` selection, with Place Story and research/
  conservation export unconditionally inclusive where no existing test
  disagreed; Today now surfaces its own already-computed per-camera
  activity/evidence-source facts for the first time (a compact "By camera"
  section and per-highlight camera attribution, both gated to 2+ cameras
  so Today stays a report, never a camera-monitoring dashboard); Bird
  Log's camera filter now reaches its overview list, not only the
  per-species drilldown; Zone Insights' Place-wide aggregate coverage was
  a naive per-camera-hours sum, now a real elapsed-time interval union
  matching Today's own already-correct semantics (proven with real
  before/after numbers: 2 hours + 2 hours overlapping by 1 hour now
  correctly reports 3, not 4); Dashboard distinguishes "some cameras need
  attention" from "every armed camera needs attention," computed from
  already-returned facts; `CameraConfigurationPage.tsx`'s own locally-
  drifted 3-tone health-tone/generic-label presentation now reuses the
  canonical `cameraHealthTone`/`cameraHealthLabel` every other health
  surface already converged on; a real, measured (not merely claimed)
  concurrency proof -- genuine concurrent `threading.Thread`s, one per
  Stream, each with its own `ProductRepository`/connection against one
  shared SQLite file, matching production's actual architecture -- found
  zero cross-Stream contamination and no starvation across 2-camera and
  4-camera-asymmetric topologies, and separately found, root-caused, and
  honestly disclosed (an attempted bounded transient-retry fix did not
  reliably close the gap and was deliberately reverted rather than shipped
  unproven on Stage 7's own live admission/persistence boundary) a real,
  reproducible occasional lost-candidate-Visit reliability gap under real
  concurrent write contention; a comprehensive, real, executable 3-camera
  product-shaped scenario (Front Feeder/Back Yard/Bird Bath, a real
  cross-camera "associated" pair, an archival, a rename, a reviewed
  correction) proves the whole chain -- identity, coverage, overlap dedup,
  health, correction propagation -- coheres end to end with zero mocking
  of product logic. Full Core 5106 passed / 2 failed (both the identical,
  independently-reconfirmed pre-existing `test_place_biodiversity_summary_
  repository.py` pair -- see §14) / 3 skipped / 23 deselected / 11 xfailed
  (26m48s); `ruff check`/`tsc --noEmit`/`vite build` clean; full existing
  e2e suite (128 tests) at 127 passed / 1 failed (the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap). Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": the occasional
  lost-candidate-Visit concurrent-write reliability gap (the single most
  concrete, actionable follow-on item); notification-level (Calm
  Attention) cross-camera grouping beyond the Dashboard status-view fix;
  Place Story wildlife-event source attribution; camera-filter UI
  consolidation (6+ independently-implemented controls); multi-camera
  Place Feature linking; real GPU/CUDA-driver-level concurrent-inference
  measurement (needs real hardware this sandbox lacks); a multi-hour
  concurrent soak; the pre-existing, disclosed 2-Stream cap on the
  separate legacy motion pipeline (RTSP/USB/local providers, not the
  modern Observation Engine's own Camera Node path).
- **Prior accepted HEAD:** `3c60d79` (Ecological
  Interoperability & Submission Workflows v1 implementation commit --
  filled in at reconciliation)
- **Schema:** v56 -> v57. Two new additive tables:
  `ecological_taxonomy_mappings` (a bounded, reusable "MockingBird label ->
  destination taxon" resolution cache, one row per `(destination, label)`)
  and `ecological_submission_records` (a durable per-Visit
  external-submission-preparation record, one mutable row per `(visit_id,
  destination)` until a self-reported external result freezes it). No
  existing table's shape changed.
- **Prior accepted milestone:** Ecological Interoperability & Submission
  Workflows v1 -- Reviewed Observations -> eBird / iNaturalist / External
  Ecology
- **Ecological Interoperability & Submission Workflows v1 classification:**
  B -- a real, working, submission-ready iNaturalist workflow composed
  entirely over the already-accepted research-eligibility gate and
  `ResearchObservation` shape (`mockingbird.ecological.destination_
  eligibility`/`adapters` never re-derive either), never a second truth
  system. See
  [ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md)
  for the full record: eligibility preview with per-record, never-bare
  status and reasons; a credential-free iNaturalist taxonomy mapping cache
  (`GET /v1/taxa`, confirmed public/no-auth against the official swagger
  spec) whose exact-name-match logic was directly corrected against a real
  live API call during this milestone's own testing (a plain "Northern
  Cardinal" query returns several candidates, not one -- requiring an exact
  match among them, not a bare single-result rule); explicit, never-
  inferred-from-the-weather-coordinate location/media consent (directly
  tested); a batch prepare/export pipeline producing the exact positional
  8-column CSV iNaturalist's own open-source bulk importer expects
  (confirmed directly against `lib/bulk_observation_file.rb`); deterministic
  content fingerprinting closing idempotency and correction-after-
  preparation staleness (a real precedence bug -- a stale-and-currently-
  ineligible record reported the less useful reason first -- found and
  fixed by this milestone's own test-writing); a self-reported external-
  result close-the-loop step, never a live automated submit; a bounded,
  additive Darwin Core Occurrence-core exporter
  (`basisOfRecord="MachineObservation"`, GBIF's own recommended camera-trap
  value, confirmed via its official camera-trap guide); eBird correctly,
  evidence-backed **not offered** (its own current "Rules and Best
  Practices," checked 2026-08-25, explicitly excludes feeder/trail-camera
  data -- a real policy conflict, not a time constraint, and the product UI
  now shows this reason persistently rather than behind a disabled
  button's hover-only tooltip, a real gap this milestone's own e2e testing
  found and fixed); direct GBIF publication correctly deferred as
  institutional (organizational Participant-Node endorsement required, not
  a backyard-user workflow); two real security findings made and fixed
  (CSV injection in the one shared `_write_csv` helper behind every export
  in this codebase, retroactively hardening the pre-existing generic
  research/Camtrap DP export paths too -- and a real regression in an
  early version of that exact fix, which corrupted legitimate negative
  coordinates, caught by this milestone's own test before shipping; a
  `javascript:`-scheme external-URL rejection on the self-reported result
  field); a real, executable 12-Visit product-shaped scenario test proving
  the whole workflow end to end with zero user interaction and zero
  provisional/superseded truth ever reaching a prepared record. 107+ new
  tests across nine new test files plus targeted additions to three
  existing ones, all passing; `ruff check` confirmed zero new findings via
  a direct line-level diff against a clean baseline (not merely a
  bisection) -- an over-broad `ruff --fix` run was caught removing ~19
  unrelated pre-existing unused imports and precisely reverted before that
  confirmation; `tsc --noEmit`/`vite build` clean; new
  `ecological-destinations.spec.ts` 4/4 passing; full existing e2e suite
  re-run at 126 passed / 1 failed, that one failure the identical,
  already-independently-documented pre-existing `reviewed-product-loop.
  spec.ts` gap recorded across at least three prior milestones' own
  acceptance records. Real, honestly-recorded remaining gaps -- not release
  blockers, this is substantial product development -- are detailed in the
  report's "Remaining major PRODUCT opportunities": live OAuth iNaturalist
  submission; media-byte inclusion; a single-Visit deep-link pre-selection
  on the Ecological Destinations page; broader batch-filter UI depth.
- **Prior accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Prior accepted HEAD:** `c22bf94` (Calm Attention &
  Notifications v1 implementation commit -- filled in at reconciliation)
- **Schema:** v55 -> v56. One new additive table, `user_notification_
  preferences` (per-user delivery preferences). No existing table's shape
  changed; `ProductAlertModel.category`/`.action_type` are plain `String`
  columns with no database-level enum/check constraint, so the new
  `"insight"` category and the two new `open_place_story`/`open_place_report`
  action types needed no migration of their own.
- **Latest accepted milestone:** Calm Attention & Notifications v1 -- Tell Me
  When Something Matters
- **Calm Attention & Notifications v1 classification:** B -- a real canonical
  attention-selection layer (`ProductRepository.sync_attention_signals`)
  composed entirely over already-accepted facts (Place Story's already-
  deduplicated event stream, the existing daily/weekly digest, the existing
  review/monitoring/storage/journal `ProductAlert` system), never a second
  computation path. See
  [calm-attention-notifications-v1-report.md](calm-attention-notifications-v1-report.md)
  for the full record: a small user-centered taxonomy (Discovery/Insight/
  Needs Help/Observatory Health) and explicit urgency (immediate/digest/
  in-app-only) computed as a pure presentation-layer mapping, never stored
  and never a raw internal severity/error vocabulary leaking into copy;
  genuine semantic-deduplication work that found and fixed two real
  double-notification anti-patterns by *writing tests*, not merely by
  design review (`first_seen` excluded from the new sync because `_sync_
  journal_milestone_alert` already owns that fact; the 1st-species
  diversity milestone excluded too, since it is always dated at that same
  taxon's own first-ever confirmation); reused, not reinvented, health/
  storage debounce (`_sync_camera_health_incident`'s own already-debounced
  named-duration/consecutive-failure thresholds, untouched); a daily/weekly
  digest notification reusing `daily_digest.compute_daily_digest` unmodified
  via the exact same `place_activity_report` entry point Today/the Place
  Report already call, suppressed when there is genuinely nothing meaningful
  and never suppressed for an ordinary day of confirmed regular activity;
  Needs Help reclassified to `in_app_only` urgency and grouped into the
  digest's own "N observations could use your help" sentence instead of a
  second per-item interruption; new per-user notification preferences (this
  product's first per-user settings row -- four category toggles + quiet
  hours) with quiet hours deliberately evaluated in the viewer's own
  browser-local time rather than inventing a server/Place timezone that does
  not exist; a fixed role rule hiding Needs Help attention from Viewers
  server-side, not merely in the UI; foreground-only browser-notification
  delivery (Phase 22 Decision B, Web Push explicitly evaluated against real
  architecture facts and deferred -- no VAPID/subscription persistence, no
  outbound push-service call, no cloud infrastructure added, matching this
  lane's own standing "do not add cloud push infrastructure" instruction);
  a real, executable Monday-through-Sunday product-shaped quiet-week test
  proving the whole week stays calm (<=14 total attention items, zero ever
  reaching `immediate` urgency); a real controlled-checkbox revert bug found
  and fixed in the new Notifications settings UI by a failing Playwright
  assertion; 4 new e2e tests that install a fake `Notification` global and a
  fake clock to prove the live-notification decision logic end to end, not
  only that Settings persists a toggle. 22 new backend tests (`tests/
  test_calm_attention.py` + `tests/test_attention_sync_service.py`) plus one
  new schema-migration regression test, all passing; Core 4991 passed / 3
  failed (all 3 independently re-bisected this session -- 2 byte-identical
  pre-existing via fresh `git stash push -u`, 1 a load-induced flake
  reconfirmed clean in isolation and matching an identical documented
  precedent -- see §14) / 3 skipped / 11 xfailed; `ruff check`/`tsc --noEmit`/
  `vite build` clean; 11/11 new e2e tests passed; full existing e2e suite
  (118 tests) re-run with only the one already-known pre-existing failure
  (`reviewed-product-loop.spec.ts`, unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's "Remaining
  major PRODUCT opportunities": Web Push for a genuinely closed-browser
  interruption (deliberately deferred, not merely unattempted); detector/
  model-unavailable Observatory Health attention; per-user (not global)
  read/dismiss state; precise per-taxon/Feature Place Story deep links
  (today scoped to a category group); a live attention-sync diagnostics
  surface beyond the current structured log line.
- **Prior accepted milestone:** Mobile & Remote Experience v1 -- Your
  Observatory Away From the Desk
- **Mobile & Remote Experience v1 classification:** B -- strong mobile
  experience and a clear secure remote posture with bounded external-
  network/PWA gaps. See
  [mobile-remote-experience-v1-report.md](mobile-remote-experience-v1-report.md)
  for the full record: a verified responsive-navigation fix (top bar +
  off-canvas drawer + 4-item bottom nav, replacing a sidebar that
  previously stacked in full above every page below 980px, proven across
  10 real automated phone-width screenshots with zero horizontal-overflow
  findings); a bounded, from-scratch installable PWA shell (manifest,
  icons generated from the product's own existing brand mark, a service
  worker that caches only Vite's own immutable content-hashed assets and
  never navigation/API/data -- no offline data claim anywhere); LAN access
  made genuinely discoverable (`GET /api/product/connection`, a Settings
  "Connection & Remote Access" card, a corrected `--allow-network` help
  string that had gone stale since real authentication shipped); a
  private-overlay-network (Tailscale-compatible) remote-access posture
  investigated against real architecture and documented as the supported
  away-from-home path, with direct public-internet exposure and a cloud
  relay explicitly, plainly documented as unsupported/not-built; 4 new
  CORS regression tests closing a real, previously-zero coverage gap. Also
  closed, as its own bounded Phase 0 ahead of the broader mobile work: a
  genuine pre-existing defect in `place_change_summary._presence_status`
  that made the accepted `regularity_narrative` "returned after absence"
  wording structurally unreachable through Today/Bird Log's direct
  composition -- fixed at the source (not merely worked around a second
  time), including a second, deeper defect the naive fix alone would have
  introduced (a young-taxon false positive), closed by sharing one timing
  guard between Today/Bird Log and Place Story instead of duplicating it.
  138 tests pass across the six directly touched/added test files (20
  genuinely new, 2 pre-existing corrected -- see §14), Core 4976 passed /
  3 failed (2 pre-existing and re-confirmed via fresh `git stash push -u`
  bisection, 1 a load-induced flake in an unrelated file matching an
  already-documented precedent, isolation-confirmed clean -- see §14) /
  3 skipped / 11 xfailed; frontend `tsc`/`vite build` clean;
  19/19 new mobile-viewport e2e tests passed (10 core surfaces +
  360px/390px/768px matrix); full existing e2e suite
  (112 tests) re-run with only the one already-
  known pre-existing failure (`reviewed-product-loop.spec.ts`, a
  `ReviewQueuePage` `product_category` gap, independently reproduced and
  unrelated to this milestone). Real,
  honestly-recorded remaining gaps -- not release blockers, this is
  substantial product development -- are detailed in the report's
  "Remaining major PRODUCT opportunities": Visit/Stream/Settings page
  density (long but not broken), the `ReviewQueuePage` `product_category`
  gap itself (found, documented, not fixed), no login rate-limiting
  (pre-existing, real, more relevant now that reachability increased), and
  no live external-overlay-network acceptance was possible from this
  sandbox (validated structurally only).
- **Prior accepted milestone:** Place Story & Seasonal Timeline v1 -- A
  Living History of the Place
- **Place Story & Seasonal Timeline v1 classification:** B -- major
  useful capability, bounded history/story gaps. New `GET /api/place/
  story` composes a small, deliberately bounded event taxonomy --
  wildlife (`first_seen`/`return`/`regularity_change`/
  `noteworthy_activity`/`diversity_milestone`), place
  (`feature_change`/`phenology`), context (`comparison_insight`) --
  entirely from already-accepted primitives (`historical_baseline`,
  `place_change_summary`, `regularity_narrative`,
  `PlaceFeatureChangeEventModel`, `PlacePhenologyObservationModel`,
  `feature_change_comparison`); regularity/activity-change detection
  re-applies those unmodified functions at every usable-date checkpoint
  so a transition is announced once, not once per recomputation. Found
  and worked around without modifying the frozen module: `place_change_
  summary._presence_status` has made the existing `"returned_after_
  absence"` wording unreachable in production on Today/Bird Log since
  Place / Yard Intelligence v2 shipped -- `place_story._effective_
  regularity_state` applies a narrow local supplemental check using that
  module's own already-correct fields; a dedicated fix to `place_change_
  summary.py` itself is recorded as future work, not applied here. New
  `PlaceStoryPage.tsx`: a calm, newest-first, month-grouped timeline with
  Period/Category filters and evidence drill-down. 24 pure-module tests
  (including regression tests for the gap above and a second, separately
  found and fixed checkpoint-seeding bug), 8 repository/HTTP integration
  tests against real seeded data (including three independent
  correction-safety proofs), all passing; Core 4958 passed / 2 failed
  (both pre-existing, re-confirmed via fresh `git stash push -u`
  bisection -- see §14) / 3 skipped / 11 xfailed; 44/44 targeted e2e
  passed (6 new + 38 directly-adjacent re-run). See
  [place-story-seasonal-timeline-v1-report.md](place-story-seasonal-timeline-v1-report.md)
  for the full record, including recorded future opportunities (period
  summaries -- deferred on a measured performance cost, the single
  largest deferred piece --, environmental-context/weather caveats on a
  Story insight, a dedicated taxon/Feature story page, representative
  imagery on Story cards, and the `place_change_summary.py` fix itself)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Place Features & Habitat Change v2 --
  Feeders, Water, Nest Boxes & Before/After Understanding
- **Place Features & Habitat Change v2 classification:** B -- major
  useful capability, bounded feature/data-model maturity gaps. A durable
  `PlaceFeatureModel` (feeder/water/nest_box/vegetation_patch/structure/
  habitat_area/other, optionally camera/Zone-linked) and a Reviewed
  `PlaceFeatureChangeEventModel` timeline (added/removed/moved/modified/
  replenished/food_changed/vegetation_changed/other), a deliberate
  dual-write (not event-sourced) relationship between the two -- the
  first discrete before/after change-event model in this codebase,
  closing a gap `habitat_association.py`'s own docstring and the Place /
  Yard Intelligence v2 report both explicitly recorded as their own
  honest ceiling. A new before/after comparison module composes onto
  `conditional_association.compute_conditional_association` completely
  unmodified (proven byte-identical output to calling that primitive
  directly), adding only a bounded 7/14/30-day symmetric window
  escalation and a four-state maturity vocabulary (too_soon/insufficient_
  coverage/early_signal/comparable); a per-Feature yield module mirrors
  `source_activity.py` one level finer. Both new tables are PATCH-
  corrected in place because every derived comparison is computed fresh
  at read time, never cached -- proven, not just asserted, by a direct
  test that a correction changes the very next read. New Dashboard card
  and Place Report section, both mirroring existing Habitat & Phenology
  UI patterns exactly. 50 new backend tests, 7 new Playwright e2e tests,
  all passing; Core 4926 passed / 2 failed (both pre-existing, re-
  confirmed via fresh `git stash` bisection -- see §14) / 3 skipped / 11
  xfailed; 37/37 targeted e2e passed (7 new + 30 directly-adjacent
  re-run). See
  [place-features-habitat-change-v2-report.md](place-features-habitat-change-v2-report.md)
  for the full record, including recorded future opportunities
  (environmental-context/weather caveats on a before/after result --
  the single largest deliberately-deferred piece --, multi-camera
  Feature linking, representative evidence in Feature detail, a ranked
  feature-comparison view, deeper Today/`daily_digest` integration)
  deliberately not built by adjacency.
- **Prior accepted milestone:** Environmental Context v2 -- Weather,
  Climate & Place Conditions
- **Environmental Context v2 classification:** B -- major useful
  capability, bounded provider/statistical/UI limitations. First general
  weather provider (Open-Meteo -- free, non-commercial, no API key,
  global coverage, CC BY 4.0 attributed) composed onto the existing
  `conditional_association` primitive alongside `habitat_associations`;
  two independent privacy opt-ins (coordinates for solar, a separate
  `weather_enabled` for any outbound network call); a bounded 92-day
  historical window (exceeds this product's entire real history today);
  six honest degraded-mode states, zero crashes, zero blocking of core
  product function. 85 new tests; Core 4874 passed / 3 failed (2
  pre-existing, 1 confirmed transient load-induced flake in an unrelated
  subsystem) / 3 skipped / 11 xfailed; 42/42 targeted e2e passed. See
  [environmental-context-v2-report.md](environmental-context-v2-report.md)
  for the full record, including the Open-Meteo terms/license research
  and recorded future opportunities (deeper historical backfill via the
  archive/ERA5 endpoint, wind/cloud-cover statistical associations, a
  dedicated diagnostics/Explore-page surface) deliberately not built by
  adjacency.
- **Camera / Source Experience release classification:** C -- usable,
  bounded further closure remains (ongoing-monitoring failure-code
  collapse; no real reachable camera/RTSP/ONVIF/local-USB/Camera-Node
  hardware exercised this session). See
  [camera-source-experience-v1-report.md](camera-source-experience-v1-report.md).
- **Native-Windows acceptance (this milestone):** none -- Ecological
  Interoperability & Submission Workflows v1 was validated via targeted
  and full Core Python tests, new Playwright e2e, `tsc`/`vite build`, and
  `ruff` on the Linux/WSL dev stack, plus a real live call to iNaturalist's
  own public taxonomy API during development (not a Windows-specific
  proof, but real external-network evidence). Every new module is plain
  Python/TypeScript with no OS-specific branch (the one external HTTP call
  uses the same stdlib `urllib.request` convention the existing weather
  provider already validated cross-platform), so it is not expected to
  behave differently on native Windows, but that remains an expectation,
  not fresh Windows evidence. The most recent real native-Windows
  acceptance remains further below (Place / Yard Intelligence v2),
  unaffected by this milestone's additive-only schema change.
- **Native-Windows acceptance (Calm Attention & Notifications v1):** none --
  validated via targeted Python tests (including a real 28-minute Core
  run), new Playwright e2e (including 4 real-browser `Notification`/
  fake-clock tests), `tsc`/`vite build`, and `ruff` on the Linux/WSL dev
  stack; every new module is plain Python/TypeScript with no OS-specific
  branch, so it is not expected to behave differently on native Windows,
  but that remains an expectation, not fresh Windows evidence.
- **Native-Windows acceptance (Place Story & Seasonal Timeline v1):** none
  -- Place Story &
  Seasonal Timeline v1 was validated via targeted Playwright e2e against
  the real running app (Linux/WSL dev stack) and full Core; it is a pure
  read-model over already-cross-platform data with no platform-specific
  code and is not expected to behave differently on native Windows, but
  that is an expectation, not fresh Windows evidence. The most recent
  real native-Windows acceptance remains the one below (Place / Yard
  Intelligence v2), unaffected by this milestone's schema-unchanged,
  additive-only change.
- **Native-Windows acceptance (Place Features & Habitat Change v2):**
  none -- validated the same way (targeted Playwright e2e + full Core on
  Linux/WSL), for the identical reason (no platform-specific code).
- **Native-Windows acceptance (Place / Yard Intelligence v2):** real
  deployment of the exact commit (confirmed via `/api/product/instance`),
  plus a second, genuinely fresh isolated instance exercised end-to-end
  (real administrator creation, real sign-in, real ffmpeg 8.1.2 subprocess
  against an intentionally unreachable RTSP host, honest
  `preview_available`, correct credential masking, no leak) -- not a
  full physical-camera acceptance; see that report's Section 6/9.
- **Prior Native-Windows acceptance (Release Engineering Foundation v1):**
  Decision A -- real deployment, a real packaging defect found and fixed,
  a real organic 18-schema-version migration with verified automatic
  backup, confirmed via real HTTP. See
  [release-engineering-foundation-v1-report.md](release-engineering-foundation-v1-report.md).
- **Weather provider decision:** Open-Meteo (`api.open-meteo.com`), free/
  non-commercial/no-API-key, CC BY 4.0 attributed, bounded to its own
  confirmed 92-day recent-history window. Off by default
  (`weather_enabled=False`); a second, independent opt-in from the
  existing coarse-coordinate setting. See the Environmental Context v2
  report's "Provider decision" for the full terms/license research and
  the preserved, unresolved commercial-adjacent-use caveat (mirroring the
  standing BirdNET caveat in §2, above).
- **Acoustic release posture:** Release-ready optional
- **Production detector:** MDv5a ONNX @ 0.1
- **Production visual species system:** BioCLIP-2 + Eligibility/Abstention
- **Current authorized implementation milestone:** NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED
- **State:** Milestone-closure checkpoint
- **Final release hardening:** not authorized
- **Remote LTE/solar:** not a release blocker
- **Ecological Interoperability:** delivered this milestone (classification
  B) -- see Lane J, §6; live OAuth iNaturalist submission, any eBird
  workflow, direct GBIF publication, media-byte inclusion, and a
  single-Visit deep-link pre-selection are not automatically authorized
  (see §3)
- **Ecological destination decisions:** eBird -- not offered (own current
  policy excludes feeder/trail-camera data); iNaturalist -- submission-ready
  CSV workflow delivered, live OAuth submit deliberately not built; Darwin
  Core -- built, additive to Camtrap DP; GBIF -- deferred, institutional
- **Darwin Core export:** delivered this milestone, additive to the
  already-accepted Camtrap DP export (not a replacement) -- see Lane
  "Research / Conservation," §5
- **Calm Notifications:** delivered this milestone (classification B) -- see
  Lane D, §6; a further Web Push/per-user-read-state/precise-deep-link
  campaign is not automatically authorized (see §3)
- **Calm attention capability:** B -- one canonical attention-selection
  layer over already-accepted facts, genuine semantic-dedup fixes found by
  tests, reused health/storage debounce, per-user preferences and quiet
  hours, foreground-only browser notifications with Web Push deliberately
  deferred, a real product-shaped quiet-week proof
- **Notification delivery decision:** foreground-only page-level
  `Notification` calls while the tab is open or backgrounded (Phase 22
  Decision B); no Web Push, no VAPID/subscription persistence, no outbound
  push-service call, no MockingBird-operated cloud notification backend --
  see the milestone report's "PWA / browser notification decision" for the
  full evaluation of all three options against real codebase facts
- **Mobile/PWA:** delivered this milestone (classification B) -- see Lane
  E, §6; a further Mobile/PWA/remote-access campaign is not automatically
  authorized (see §3)
- **Mobile experience capability:** B -- responsive navigation verified
  overflow-free across 10 real phone-width screenshots; dense secondary
  pages (Visit/Stream/Settings) remain long but not broken
- **Remote-access support posture:** private overlay network
  (Tailscale-compatible) is the documented, supported away-from-home
  path; direct public-internet exposure and a MockingBird-operated cloud
  relay are explicitly unsupported/not-built; LAN access via
  `--allow-network` is now discoverable in-product
- **Security implications (this milestone):** 4 new CORS regression
  tests closing a previously-zero coverage gap; new
  `GET /api/product/connection` deliberately kept authenticated (not
  public); media/evidence routes re-confirmed authenticated by policy-
  table inspection; no login rate-limiting exists (real, pre-existing,
  found and documented, not fixed -- see the milestone report)
- **Local Species Prior:** not authorized
- **Another classifier campaign:** not authorized
- **LICENSE:** still genuinely absent -- open business/legal decision, not
  resolved by this or any prior milestone (see Lane P, above)
- **Representative Field Acceptance (attempted 2026-08-25):** Gate C --
  OPEN, insufficient representative evidence; deferred by explicit user
  decision before any live session started (real-authentication/consent
  boundary, not a product defect). See Lane R and
  [representative-field-acceptance-release-budget-v1-report.md](representative-field-acceptance-release-budget-v1-report.md).
  Untracked root `uv.lock` investigated and removed per that milestone's
  own Decision A; working tree returned to exactly the seven preserved
  files then, and confirmed still exactly those seven, untouched, at this
  milestone's own start and close. An untracked `uv.lock` recurred mid-
  session during Place Features & Habitat Change v2 (an ordinary,
  never-gitignored side effect of `uv run` tool invocations in this
  actively-shared worktree, not a milestone artifact) -- removed again,
  same reasoning. It recurred a third time mid-session during Place Story
  & Seasonal Timeline v1, for the identical reason (a `git stash push -u`
  bisection re-created it) -- removed again; the working tree was
  confirmed to hold exactly the seven preserved files, untouched, at this
  milestone's own start and close, alongside this milestone's own
  committed additions. Mobile & Remote Experience v1 used `git stash
  push -u`/`pop` for its own Core-gate bisection (see §14) and confirmed,
  both before and after, that the working tree held exactly the seven
  preserved files, byte-identical to milestone start, alongside this
  milestone's own committed additions. Ecological Interoperability &
  Submission Workflows v1 confirmed the same at its own start (before any
  edit) and again at close: exactly the seven preserved files, untouched,
  alongside this milestone's own committed additions -- two peer sessions
  sharing this same working directory were confirmed idle (no file writes
  in 11+ and 105+ minutes respectively) before any write began.
  Multi-Camera Place Experience v2 confirmed the identical seven preserved
  files, untouched, at its own start, throughout (re-verified after two
  `git stash push -u`/`pop` ruff-bisection round-trips), and again at
  close alongside this milestone's own committed additions; two peer
  sessions sharing this same working directory (`mockingbird-active-65`,
  `mockingbird-active-c6`) were confirmed idle/read-only both before any
  write began and again immediately before the implementation commit
  (`git log`'s own unmoved HEAD across the full session, `763fe22`'s
  parent still `21fbc42`, was independent, objective confirmation neither
  peer had committed anything in the interim).
- **Push:** explicit authorization required
