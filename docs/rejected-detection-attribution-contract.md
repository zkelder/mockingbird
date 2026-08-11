# Rejected / Suppressed Detection Attribution v1 contract

Status: Phase 2 "Detection Quality Accounting" milestone (see
[roadmap.md](roadmap.md)), motivated by the 2026-08-11 Localization
Attribution live-evidence session's own disclosed incidental finding: a
real, clearly-visible bird appeared in candidate-010's own evidence images,
near the feeder, but was structurally unconnected to that candidate's own
track lineage -- and the session's own final report had to conclude
"whether MDv5 ever produced a detection on this bird cannot be determined:
a live session's in-flight per-proposal facts for any track that did not
resolve to an admitted candidate are transient and unrecoverable" (see
`data/field-acceptance/2026-08-11-localization-attribution-live-evidence/
FINAL-REPORT.md` §10 and the
`localization-attribution-live-evidence-2026-08-11` project memory). This
milestone closes exactly that gap: the precise question it answers is, when
a real bird is visible in source imagery but no corresponding Visit is
persisted, did the raw detector detect it and downstream logic suppress/
lose it, or did the detector never localize it at all?

## Boundary

This is a narrow counterfactual-observability milestone, not a detector
change, a tracker-policy change, a Visit-assembly change, or an admission
-policy change. It does **not**: change `ProviderNeutralFrameTracker`'s
association/confirmation/termination policy; change
`visit_episode_assembler.py`'s assembly decisions; change
`candidate_visit_authority.evaluate_candidate_authority` or
`candidate_quality_gate.evaluate_evidence_admission`'s decision logic;
change the MDv5 `0.1` production `score_threshold`; promote any shadow
admission policy; retrain, replace, or benchmark a detector; do species
identification/BioCLIP work; or redesign Visit semantics. It adds one
bounded, local-only, diagnostic-only standing record of activity that
already happens, wired into the one live session driver
(`mockingbird.observation.engine_runtime`) that previously discarded it.

## Where the facts were lost, as traced

Tracing `raw detection -> tracker association/generation -> tracklet ->
Visit episode assembly -> candidate authority / quality gates ->
suppression/rejection -> diagnostics/retention` against the accepted
`frame-driven-onnx-cuda` provider family found three independent, precise
loss points -- none of them a bug in the sense of wrong behavior; each is a
fact computed and then genuinely discarded by the one caller that could
otherwise have kept it:

1. **Raw per-frame detector output was computed and never read at all.**
   `frame_driven_provider.FrameDrivenObservationProvider._process_frame`
   already builds `ObservationResult.detection_observations` -- every
   `DetectionObservation` the detector produced this inferred frame,
   already filtered past Privacy/Ignore exclusion, before any tracker
   association runs -- for every real live Camera Node frame the detector
   evaluates. `engine_runtime._EngineSession._run_async`'s own per-batch
   loop (`for result in results: ...`) read `result.track_updates` and
   `result.evidence_candidates` from that same `ObservationResult`, but
   never once referenced `result.detection_observations`. This is the
   single largest loss: the exact question this milestone exists to
   answer -- "did the raw detector detect it at all" -- was structurally
   unanswerable because the one fact that would answer it was computed and
   immediately dropped, every frame, for the life of every live session to
   date.
2. **A track generation the tracker itself never confirmed left no trace
   once its generation ended.** `visit_episode_assembler.build_tracklets`
   correctly (and, by design, unchanged by this milestone) only summarizes
   a generation whose terminal `TrackUpdate.lifecycle_state == "ended"`
   (confirmed); a generation whose terminal state is `"rejected"` is
   skipped entirely -- appropriately, for *Visit assembly's* purposes (the
   tracker's own confirmation bar already judged it insufficient). But
   nothing else in the live pipeline retained that generation's own
   summary either, so "the detector hit something here, and the tracker
   itself lost it before Visit assembly ever ran" was unanswerable from
   anything durable.
3. **A non-created admission outcome collapsed to one bare count.**
   `engine_runtime._EngineSession._run_assembly_tick` already computes a
   full `CandidateAttemptResult` (proposal id, outcome, reason) for every
   admission attempt via `CandidateVisitAuthorityAdapter.attempt_candidate`
   -- which itself scores real, already-retained
   `AssembledVisitProposal.confidence_evidence` and evidence geometry. The
   *only* thing that survived a non-`created` outcome was
   `self._suppressed[outcome.outcome] += 1` -- a per-session, in-memory
   `dict[str, int]`, reported to the product API only as the top-8 `(reason,
   count)` pairs on `ObservationEngineSessionStatus.counts.
   suppressed_reasons`. The proposal's own id, constituent generation/track
   ids, temporal span, and confidence/geometry evidence were all discarded
   at the end of that loop iteration -- this is exactly why the 2026-08-11
   session could report "82 `blocked_continuation_pending`, 55 `blocked_
   ambiguous_boundary`, 12 `blocked_missing_evidence`" as bare counts but
   nothing about *which* 149 proposals those were, and it is also why a
   `blocked_continuation_pending` proposal re-evaluated across several
   ticks silently inflated this same counter once per retry rather than
   once per proposal.

Durable counters already existed one layer further out
(`ObservationAuthoritySettingsModel.suppressed_count`/`candidates_
attempted_count`/etc., see
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
"Diagnostics") -- but these are pure aggregate lifetime counts with no
per-attempt lineage either, and `last_proposal_id` is only ever updated on
a *created* outcome, never a suppressed one.

## Bounded counterfactual lineage added

`mockingbird.observation.counterfactual_lineage` (pure: no filesystem,
network, CUDA/ONNX Runtime/OpenCV, product-repository, or SQLAlchemy import
-- the same structural convention every sibling Stage 6.x/7 decision module
in this package follows) adds three small, bounded, model-neutral record
types, reusing existing contracts and vocabularies rather than inventing
new ones:

- **`RawDetectionRecord`** -- one raw detector-evaluation fact per
  inferred frame: source/stream/session identity (`stream_id`,
  `node_session_id`, `provider_generation`), `source_offset_ms`/
  `captured_at`, broad detector class (`broad_class`/`is_animal`),
  `confidence`, the raw `bounding_box`, and detector/model provenance
  (`detector_id`/`provider_id`) where already available. Either a genuine
  detection (`bounding_box` set) or an explicit "the detector ran this
  frame and found nothing usable" heartbeat (`bounding_box is None`) --
  both recorded, deliberately: a frame the detector never evaluated at all
  (an idle-cadence gap) must stay distinguishable from one it evaluated and
  found nothing in, mirroring `TrackUpdate.detector_ran`'s identical
  "skipped vs. negative" distinction one layer earlier (see
  [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)).
  This required one new, purely-additive field,
  `contracts.ObservationResult.detector_ran` (defaulted `False`, set
  correctly only at the one live call site that matters,
  `frame_driven_provider._process_frame`), since no existing fact could
  honestly answer "did the detector run this frame" independent of whether
  any track happened to exist that frame.
- **`TrackGenerationRecord`** -- one finalized (started-and-ended) tracker
  generation, confirmed *or* rejected: `generation_id`/`track_ids`,
  tracker lifecycle outcome (`confirmed`, `terminal_reason`), tracker
  geometry (`start_bounding_box`/`end_bounding_box`/`geometry_envelope`,
  the last accumulated incrementally across every update this ledger
  observed -- cheap, bounded by concurrently-active generations, never a
  full retained per-frame history), detector-supported-versus-coasted
  state (`terminal_support_state`, `terminal_bounding_box_source_offset_ms`
  -- `TrackUpdate.bounding_box_source_offset_ms`, Localization Attribution
  v1's own staleness fact, reused verbatim), and `confidence_evidence`
  (`contracts.ConfidenceEvidenceSummary`, Detection Quality Accounting
  v1's own bounded per-detection sample history, also reused verbatim: a
  generation's *terminal* `TrackUpdate` alone already carries everything
  needed to build a complete summary, so no other update ever needs
  retaining -- see `visit_episode_assembler.
  confidence_evidence_from_terminal_update`, promoted from module-private
  to shared for exactly this reuse). `terminal_geometry_source` reuses
  `localization_attribution.geometry_source_from_support_state` verbatim,
  one layer earlier: which kind of observation established this
  generation's own last-known geometry, independent of whether that
  geometry ever became any persisted candidate's evidence box.
- **`ProposalOutcomeRecord`** -- one decided admission attempt, recorded
  for *every* outcome (including a genuine `created`/`idempotent_repeat`,
  not only a suppressed one): `proposal_id`, constituent
  `generation_ids`/`track_ids`, temporal bounds, `confidence_evidence`
  (`AssembledVisitProposal.confidence_evidence`, unchanged), and the exact
  `outcome`/`reason` strings `candidate_visit_authority.
  evaluate_candidate_authority`/`candidate_quality_gate.
  evaluate_evidence_admission`/`ProductRepository.
  create_candidate_visit_from_proposal` already produce -- never a new
  outcome vocabulary.

`CounterfactualLedger` (one instance per live session,
`engine_runtime._EngineSession._counterfactual`, created fresh in
`_EngineSession.__init__`) owns the three bounded ledgers plus the
session's own observed source-offset span, and is internally locked
(`threading.Lock`) so a concurrent status/query read from the product API's
own request thread is always safe against the session's own processing
thread mutating it -- mirroring `_EngineSession._state_lock`'s identical
role for every other cross-thread status field on that class.
`_run_async`'s existing per-batch loop (both the steady-state loop and the
final `session.stop()` drain) now also calls `self._counterfactual.
observe_result(result)`; `_run_assembly_tick` now also calls
`self._counterfactual.record_proposal_outcome(...)` immediately after
`adapter.attempt_candidate(...)` decides an outcome, for every outcome
-- `self._suppressed` is left unmodified, an addition not a replacement.

## Bounded retention / eviction

`CounterfactualRetentionConfig` bounds each of the three ledgers by
**both** capacity and age, evicting oldest-first on either dimension via
one small internal `_BoundedOffsetLedger` mechanism shared by all three --
deterministic FIFO, mirroring `camera_node_live.CameraNodeAnalysisSource.
_pop_latest`'s own age-eviction loop and `frame_tracker._Track.
confidence_samples`'s own count-bound shape, not a new pattern. Defaults
are reused/derived, not per-scene tuning: `max_age_ms` (60 minutes)
comfortably exceeds the longest real bounded field session run to date
(45m47s); the count caps (12,000 raw detections / 2,000 track generations /
1,000 proposal outcomes) carry generous headroom over the busiest real
session measured so far (2,670 track updates / 727 evidence candidates /
151 proposals / 149 suppressed over ~46 minutes).

`LedgerEvictionAccounting` (`retained_count`, `evicted_count`,
`recorded_count`, `oldest_retained_offset_ms`, `newest_retained_offset_ms`)
is the exact, always-honest eviction accounting an operator needs -- never
estimated. `CounterfactualCoverage.complete_for(start, end)` is the
specific, narrower guarantee a `detector_miss` conclusion requires:
whether the *raw-detection* ledger alone (never the track-generation/
proposal-outcome ledgers, which do not gate an absence claim) provably
retains complete history for the entire queried window. A positive finding
(a raw detection or generation that *does* overlap the queried region) is
never gated by this -- an incomplete window can still honestly prove a
positive; only a claimed absence needs proven completeness.

This is diagnostic-only, per-process, in-memory retention -- **not**
persisted to the product database. A new `Start` always constructs a
brand-new `_EngineSession` (unchanged, pre-existing behavior -- see
`ObservationEngineSessionManager.start`), and therefore a brand-new,
completely empty `CounterfactualLedger`: one session's counterfactual
lineage can never mix with a prior or later one, structurally, not by
caller discipline. An app process restart, or a second `Start` for the
same Stream, releases the ledger entirely -- consistent with Detection
Quality Accounting v1's own already-disclosed limitation that a live
session's in-flight facts are transient by design; this milestone makes
that transient window *bounded and large enough to matter* rather than
*zero*, not permanent.

## Diagnostic / query surface

`CounterfactualLedger.query(start_offset_ms, end_offset_ms, roi=None)` is
a side-effect-free, deterministic read: every retained record whose own
temporal span overlaps the window, plus `raw_detections_in_roi`/
`track_generations_in_roi` further filtered to records whose own geometry
overlaps `roi` (a normalized `[left, top, right, bottom]` box; `roi=None`
matches everything) -- directly answering "whether any lineage overlaps a
supplied region of interest" per-record. `_EngineSession.
counterfactual_query`/`ObservationEngineSessionManager.
counterfactual_query` expose this from the same app-owned session object
`status()` already reads; a lightweight, always-fresh eviction/coverage
summary is also folded into the existing `ObservationEngineSessionStatus.
advanced["counterfactual_ledger"]` diagnostics dict, so an operator sees
at-a-glance retention health without needing the full query.

`GET /api/streams/{stream_id}/observation/counterfactual` (query params
`start_offset_ms`, `end_offset_ms`, and optional `roi_left`/`roi_top`/
`roi_right`/`roi_bottom`, all four or none) is the one new read-only API
route, reusing the existing `/api/streams/{stream_id}/observation/...`
route family and its established side-effect-free-read/404-for-unknown
-Stream conventions exactly (`_stream_live_playback_config_or_404`,
matching `/observation/status`). A known Stream that has never started an
Observation Engine session in this process returns an honest, empty,
`insufficient_counterfactual_lineage` result (200) rather than a 404 --
"never started" and "started but nothing here" are different, both real,
facts. Direct database archaeology is not required for this diagnostic
workflow.

## Attribution outcomes

`classify_rejection_attribution(window)` is pure and deterministic
(identical inputs always produce an identical result), reading only
already-retained lineage from one `CounterfactualWindowResult` -- never
pixel content, never a species/animal-presence judgment, mirroring
`localization_attribution.classify_localization_attribution`'s own
decision-order style (most decidable/specific fact first; "insufficient"
both a first and last-resort fallback, never a guess):

1. **`insufficient_counterfactual_lineage`** -- no raw detection overlaps
   the region *and* the raw-detection ledger's own retention does not
   provably cover the entire queried window. Checked before `detector_miss`
   can ever be reached; an evicted/partial window is never read as a proven
   absence.
2. **`detector_miss`** -- no raw detection overlaps the region, and
   coverage *is* provably complete for the window.
3. **`insufficient_counterfactual_lineage`** -- a raw detection overlaps
   the region, but no retained track-generation record's own geometry does
   (a non-animal-class detection that never entered tracking, an
   active-track-cap exclusion, or a generation record that has itself
   since been evicted). Never guesses a causal link that was not actually
   observed.
4. **`detector_hit_then_tracker_lost`** -- among the region-overlapping
   generations, any the tracker itself never confirmed. Checked first among
   the "some tracking lineage exists" branches: an unconfirmed generation
   never reached Visit assembly at all, the single most decidable fact
   available.
5. **`tracker_drift`** -- among the (now all-confirmed) overlapping
   generations, any whose own region-overlapping geometry was established
   by tracker-support (patch) matching rather than a genuine detection at
   that moment.
6. **`detector_hit_then_suppressed`** -- the recorded admission outcome for
   the generation's constituent proposal is one of `candidate_visit_
   authority.BLOCKED_OUTCOMES` (`blocked_shadow_mode`, `blocked_pre_
   activation`, `blocked_invalid_lineage`, `blocked_ambiguous_boundary`,
   `blocked_continuation_pending`, `blocked_session_limit`, `blocked_
   hourly_limit`) -- the *authority* gate's own conservative structural
   policy.
7. **`admission_rejected`** -- the recorded outcome is one of `candidate_
   quality_gate.REJECTED_OUTCOMES` (`reject_no_identification_or_context`,
   `reject_subject_geometry_invalid`, `reject_insufficient_proposal_
   support`) or one of the two repository-local checks that run only
   *after* authority already said "create" (`blocked_missing_evidence`,
   `blocked_privacy_zone`), or a genuine persistence failure (`"failed"`)
   -- the *admission/evidence-quality* boundary, deliberately kept
   distinguishable from outcome 6 above (this module invents neither
   vocabulary; it only partitions the two already-existing ones, see
   `ADMISSION_REJECTED_OUTCOMES`).
8. **`visit_created`** -- the recorded outcome was actually admitted
   (`created`/`idempotent_repeat`). Not itself a rejection outcome; the
   task's own six named outcomes are all reachable without it, but this
   classifier never forces a genuinely admitted case into a rejection
   bucket just to stay inside a fixed vocabulary.
9. **`insufficient_counterfactual_lineage`** (fallback) -- a confirmed,
   region-overlapping generation with no recorded admission outcome yet
   (still pending at query time), or an outcome code this classifier does
   not recognize. Never guessed.

These names match the task's own suggested vocabulary; nothing else in this
codebase depends on the literal strings, so a future consumer may rename
them without a second migration (the identical disclosure Localization
Attribution v1 already made for its own five names).

## Detection Quality Accounting integration

Deliberately the *only* integration point this milestone adds, per its own
"do not build a parallel metrics universe" boundary:
`detection_quality_accounting.admission_records_from_counterfactual_ledger`
is a pure field projection from `ProposalOutcomeRecord` to that module's
own existing `AdmissionRecord` (`proposal_id`/`outcome`/`admitted`/
`confidence_evidence` -- `ProposalOutcomeRecord` already carries exactly
these, including the identical `outcome in ("created", "idempotent_
repeat")` admitted rule) -- never a recomputation, so `build_detection_
quality_report` itself needed zero changes to accept a live session's own
counterfactual ledger directly. This closes the specific gap Detection
Quality Accounting v1 disclosed and left open: "a standing rejected
-candidate record wired into a *live* session (today's mechanism is an
offline pass over already-recorded facts, run via `scripts/run_detection_
quality_accounting.py`)". A live session's own `ProposalOutcomeRecord`
ledger can now feed the six-stage report directly; no replay-report.json
round trip is required, though the offline path remains unchanged and
equally valid for historical sessions.

Raw-detection/track-generation lineage (facts 1-2 in "Where the facts were
lost," above) is a genuinely new capability with no existing six-stage
-report stage it retrofits into as directly as the admission-outcome side
does; `detection_quality_accounting.py`'s own `detections`/`track_updates`/
`tracklets` parameters remain served by whatever fuller, per-session lists
a caller already has (`engine_runtime`'s own unbounded-for-one-session
`all_track_updates`, or a replay report), unrelated to this bounded ledger.

## Truth / training boundary

Every fact this module retains is diagnostic evidence, exactly like
`ConfidenceEvidenceSummary` and `GeometryAttribution` already are (see "The
truth boundary" in product-doctrine.md): `counterfactual_lineage.py` has no
product-repository, filesystem, network, or SQLAlchemy import at all (the
same structural convention/test every sibling Stage 6.x/7 decision module
already carries), so nothing it does can create an `Event`, `Visit`,
`MediaAsset`, `ReviewLabel`, or reviewed `Observation`. A
`RejectionAttributionResult` is diagnostic accounting a human reviewer's
own judgment must still confirm -- an agent that inspects one and writes a
`ReviewLabel` through the real `POST /api/review-labels` path remains
bound by the existing `agent_diagnostic`/`is_authority_eligible` provenance
boundary (see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md));
nothing about this milestone changes, widens, or bypasses that boundary.

## Retrospective analysis: the real bird visible in candidate-010's evidence

Direct application of this milestone's own honesty rules to the
2026-08-11 session (`data/field-acceptance/2026-08-11-localization
-attribution-live-evidence/`) is **`insufficient_counterfactual_lineage`**,
honestly: that session ran before this milestone existed, so no
`CounterfactualLedger` was ever active, and the old runtime's own
in-process ledger (the bare `_suppressed` reason-count dict) is long gone
-- the app process has restarted repeatedly since, and even while it was
running, that dict held no per-proposal lineage to recover. This is
exactly the honest outcome this milestone's own design anticipates for
data that predates it (the same disclosure Localization Attribution v1
made for candidates 004/005/007/008); nothing here rewrites or
retroactively reconstructs `diagnosed-010.json` or any other historical
artifact.

**What can honestly be reconstructed, from the historical record's own
already-retained facts** (`diagnosed-010.json`, `FINAL-REPORT.md` §9-10):

- Candidate-010's *own* track (`stream-ca892992771c:frame-track:
  a262286ee6c3dde4016c`, `frame-track-0066`) is fully accounted for: one
  genuine matched detection for its entire ~27.3-second life
  (`start_offset_ms=1637825`, `end_offset_ms=1665140`, exactly one
  `confidence_evidence.samples` entry at `1637825`, confidence `0.795`,
  box `[0.7098, 0.609, 0.7426, 0.6583]`), then tracker-support coasting to
  termination (its persisted "identification" image is `tracker_drift`,
  `geometry_evidence_gap_ms=4354`).
- The real bird was visually confirmed present at normalized position
  `~[0.451, 0.728, 0.469, 0.801]` (agent-estimated from the image, never a
  detector output) at wall-clock 18:17:13 and 18:17:21 -- squarely inside
  candidate-010's own `1637825-1665140`ms temporal span, but at a screen
  position with **zero overlap** against either of candidate-010's own
  boxes (`[0.71-0.74, 0.61-0.66]` and `[0.73-0.76, 0.65-0.70]`). This much
  is provable from already-retained facts: **the bird was not part of
  candidate-010's own track lineage**, at any point.
- Whether the bird's own region ever independently received a raw MDv5
  detection, formed a separate tracker generation, or formed a proposal
  that was itself suppressed, is **not** recoverable. The old runtime
  discarded all three of the facts (see "Where the facts were lost," above)
  that would answer it, for every track that was not candidate-010's own,
  for the entire 45m47s session. This is not a narrower version of "the
  bird was missed" -- it is a genuine, disclosed absence of evidence
  either way, exactly the distinction `insufficient_counterfactual_
  lineage` exists to name honestly rather than default to a guessed
  `detector_miss`.

**The purpose of this milestone is that the next real bird does not leave
this same question unanswered.** With the ledger active, an equivalent
future session lets an operator query the bird's own approximate screen
region and time window directly (`GET .../observation/counterfactual` with
`roi_left=0.45&roi_top=0.72&roi_right=0.47&roi_bottom=0.81` and the
relevant `start_offset_ms`/`end_offset_ms`) and receive one of `detector_
miss`, `detector_hit_then_tracker_lost`, `detector_hit_then_suppressed`,
`tracker_drift`, `admission_rejected`, or (if the window has already
partially evicted) an honest `insufficient_counterfactual_lineage` --
never the "no live caller ever read that fact" gap this retrospective
itself demonstrates.

## Non-goals honored

No detector/model change (MDv5 untouched). No tracker-policy tuning
(`frame_tracker.py`'s only change is threading `bounding_box_source_
offset_ms`/`support_state` facts that already existed -- zero new logic).
No Visit-assembly change (`visit_episode_assembler.py`'s only change is
promoting one already-correct private helper to a public name with an
unchanged body and call site). No admission/authority-gate change
(`candidate_visit_authority.py`/`candidate_quality_gate.py` untouched
except importing their own already-public outcome-code sets). No
production threshold change. No species work. No shadow-admission-policy
promotion. No new review UI. No unbounded frame/media retention -- every
new record is a small, structured fact; no rejected detection's own image
bytes are persisted anywhere by this milestone.

## Authority and limitations

`counterfactual_lineage.py` imports no product repository, filesystem
path, network connection, or CUDA/ONNX Runtime/OpenCV runtime, and creates
no Event, Visit, MediaAsset, ReviewLabel, or reviewed truth.
`RejectionAttributionResult` is diagnostic lineage, not observational
authority: a report or an operator may read it, but nothing may treat a
`detector_miss` classification as proof an animal was never present (a raw
detector floor and class filtering both apply upstream), or any other
classification as proof of a specific root cause, without a human
reviewer's own visual confirmation -- exactly the same evidence-not-truth
boundary `ConfidenceEvidenceSummary`/`GeometryAttribution` already
establish.

Known limitations disclosed, not hidden: `TrackGenerationRecord`'s own
geometry is a start/end/incrementally-accumulated envelope, not a full
retained per-frame trajectory -- a subject that transiently entered and
left one region mid-generation without that region ever being the
generation's start, end, or any point the envelope's own min/max corners
capture cannot be told apart from one that never came near it (a
deliberate, disclosed "lightweight structured facts over full-resolution
imagery for every rejection" tradeoff, not an oversight). Retention is
per-process and per-session: a Stop followed by app-process restart, or a
second Start for the same Stream, releases the prior session's ledger
entirely, same as every other bounded in-memory diagnostic this codebase
already carries (`_suppressed`, `temporary_burst_payload`,
`_recent_endings`). `classify_rejection_attribution` reads only what one
`CounterfactualWindowResult` retained; it never re-derives a fact from a
frame image, a wall clock, or a config file of its own.
