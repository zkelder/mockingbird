# Observation Engine product control contract

Status: Product Vertical Slice v1. This is the first place a normal user
reaches the accepted Observation Engine (Stage 5 Camera Node live-shadow,
Stage 4 frame-driven detection/tracking, Stage 6.19 shadow Visit assembly,
Stage 7 candidate-Visit authority) without CLI acceptance tools. It composes
those stages unchanged; see
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
and [camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)
for the engine internals this contract wraps.

## Problem

Every prior Observation Engine v2 stage was reachable only from a CLI
(`candidate-authority-trial`, `temporal-capture`, `replay-benchmark`) or a
Python test/harness. A normal MockingBird user could not turn it on, see
whether their camera was healthy, or trust that the Review Queue would show
them a real, reviewable moment instead of a dumping ground of low-value
machine proposals. This contract closes that gap without opening a new
engineering stage: it is app plumbing and one conservative admission
boundary, not a new detector, tracker, or evidence-scoring change.

## Observation control

`mockingbird.observation.engine_runtime.ObservationEngineSessionManager` is
an app-owned singleton (`get_observation_engine_session_manager()` in
`main.py`), mirroring `LiveCameraSessionManager`'s established convention:
one bounded background thread per Stream, running its own private asyncio
event loop, explicit start/stop, and side-effect-free status reads.

- `POST /api/streams/{id}/observation/start` -- resolves the Stream's
  already-configured Camera Node pairing (`ProductRepository.
  get_stream_live_playback_config`) and this Stream's active Privacy/Ignore
  Zones (`ProductRepository.stream_privacy_ignore_regions`, a new
  side-effect-free bounding-box read over existing Zone polygons), then
  starts the accepted `frame-driven-onnx-cuda` provider against the paired
  Camera Node. A Stream that is not a paired Camera Node, or has no local
  model bundle configured (`MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH`,
  defaulting to `data/models/observation-frame-driven/provider-config.json`
  -- the same file the existing `candidate-authority-trial` CLI already
  documents), reports an honest `state="error"` with a plain-language reason
  instead of silently starting a different runtime or crashing.
- `POST /api/streams/{id}/observation/stop` -- bounded (joins the
  background thread with a hard timeout) and is this feature's kill switch:
  it always returns candidate authority to `shadow`
  (`ObservationAuthorityMode.shadow`), whether or not the thread joins in
  time. The background loop itself also reverts authority to `shadow`
  whenever it ends for *any* reason (natural stream end, a transport error,
  or an explicit Stop) -- a session that has already died never leaves
  authority silently active.
- `GET /api/streams/{id}/observation/status` -- side-effect-free. Reports
  `state`/`observing`/`message` for the basic UI, `camera_connected`/
  `camera_message` and `engine_available`/`engine_message` as the two
  health facts Product requirement 1 asks for, and a bounded `advanced`
  object (provider ids, activation boundary, transient per-session counts
  including suppressed-candidate reasons) for the collapsed diagnostics
  disclosure. No Stage numbers, CUDA, or ONNX vocabulary appear in the
  basic fields.

"Start observing" is the one explicit action that also activates Stage 7's
`candidate_visit` authority (`ProductRepository.
set_observation_authority_mode`, the same call `candidate-authority-trial
--activate` already makes); the schema/migration default remains `shadow`
untouched by this contract. Unlike the CLI trial, an app-started session has
no wall-clock/candidate hard cap -- it is bounded by the same durable
session/hourly authority limits every other Stage 7 caller already has, and
runs until the user explicitly stops it.

## Candidate-quality admission boundary

`mockingbird.observation.candidate_quality_gate.evaluate_evidence_admission`
sits between an authority-approved proposal and its actual persistence,
inside `ProductRepository._create_candidate_visit_locked` (after the
existing `blocked_privacy_zone`/lineage/ambiguity checks, before any
MediaAsset file is written). It is pure and invents no new detector or
evidence-quality threshold -- every fact it reads (`role`,
`subject_geometry`, `constituent_generation_ids`, `broad_class`) is already
produced by the unmodified Stage 6.19 assembler and Stage 6 evidence
scorer:

1. The proposal itself carries genuine track/class support (defense in
   depth; the assembler already guarantees this).
2. At least one *meaningfully selected* candidate exists: an
   `identification` or `context` pick, never only `alternate`s or nothing
   -- an `alternate` is by definition a candidate the scorer did not select
   as its best evidence.
3. That candidate's own subject geometry is a real, non-degenerate
   normalized box, so a reviewer can see *where* the claimed subject is.

A rejected proposal writes nothing: no MediaAsset file, Visit, or Event is
created. It remains shadow-only and is counted in the existing durable
`suppressed_count` diagnostic alongside authority-gate blocks, plus a
transient, per-running-session `(reason, count)` breakdown surfaced through
`ObservationEngineSessionStatus.counts.suppressed_reasons` (advanced
diagnostics only). The product prefers "nothing surfaced" over "please
review this meaningless dark patch."

## Stage 7 evidence roles in the existing Review UI

Two existing, motion-evidence-era selection functions did not recognize
Stage 7's `identification`/`context`/`alternate` evidence roles, and have
been extended additively (existing roles/behavior unchanged):

- `mockingbird.motion.effective_primary.select_effective_primary` now
  prefers an `identification`-role candidate immediately after a
  temporally-proven legacy crop, and a `context`-role candidate as a
  fallback tier below `pretrigger` -- both with the same tri-state
  temporal/geometry/availability rejection logic every other role already
  uses, so a missing/undecodable identification file still cannot become
  the presented primary.
- `ProductRepository._review_queue_items`'s `best_media_asset_id`
  resolution now falls back to a Visit's own primary `VisitEvidenceLinkModel`
  when neither a legacy `representative_media_path` nor MotionEvidence
  exists (Stage 7 Visits have neither) -- the exact fallback
  `_review_identification_item_for_visit` already established.
- `ProductRepository._review_queue_product_context`'s `detector_class`
  derivation (which drives both the Review Queue's "Animals" tab and Today
  in Your Yard's "detector-qualified" queries) previously read only legacy
  `MotionEvidence.scoring_config_json`, which Stage 7 Visits never
  populate. It now falls back to the Visit's own persisted
  `event_type == "observation_engine_candidate"` and `subject_label`
  (`AssembledVisitProposal.broad_class`, never a species guess) when the
  legacy signal is absent -- a Stage 7 candidate that reached the Review
  Queue at all has already passed detector confirmation, tracking, shadow
  assembly, and the admission boundary above, a materially higher bar than
  the single-frame legacy signal this function was built around.

`web/src/components/VisitEvidenceSequence.tsx`'s role-label map gained
entries for `identification`/`context`/`alternate` (previously falling
through to the generic "Monitoring context" label).

## Truth boundary (unchanged)

None of the above can create a `ReviewLabel`, mark a Visit reviewed, or
write species/analytics/export truth. Only the exact existing, unmodified
`ProductRepository.create_review_label` correction path can -- Fast Review
now also offers one-click `bird`/`unknown_bird` quick actions alongside the
existing blank/false-positive/non-bird/ambiguous ones, all through that same
call. Today in Your Yard's existing `_dashboard_today_is_countable_animal_
visit`/`VisitReviewOutcome` derivation is otherwise unmodified: a reviewed
`false_positive` Visit drops out of wildlife presentation, a reviewed
`unknown_bird` Visit remains a valid wildlife moment without an invented
species, and a reviewed species label populates `new_today`/species history
-- exactly as it already did for every non-Stage-7 Visit.
