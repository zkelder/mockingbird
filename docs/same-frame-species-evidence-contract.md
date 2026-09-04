# Same-Frame Species Evidence v1 contract

Status: Phase 2 milestone, direct continuation of Automatic Species
Suggestion v1.1's subject-centric-crop resolver (`species/classifier_input.py`,
commit `ab180ac`, decision B — SAFE CROP UNAVAILABLE). That session built and
tested a resolver whose tier 2 (`exact_frame_subject_box`) requires a
persisted MediaAsset with `GeometryAttribution.same_frame is True`, then
found that fact never exists anywhere in the live product: the Observation
Engine's only durable evidence image is the high-resolution Camera Node
burst, which is *by construction* a separate, later real capture
(`localization_attribution.geometry_attribution_for_burst`, always
`same_frame=False`). This milestone closes exactly that gap — not by
building a new capture pipeline, but by persisting a frame the live pipeline
already decodes into memory and currently discards.

## Boundary

This is an evidence-persistence and classifier-input-selection contract, not
a detector, tracker, admission-policy, or Visit-assembly change. It:

- persists, at most once per track generation, the exact analysis-stream
  frame (`FramePacket`) that produced a burst-triggering `TrackUpdate`'s own
  subject box — the frame is already fully decoded and in memory at that
  point (`camera_node_live.LiveCameraNodeShadowSession._process_frame`);
- gives it a new, additive `MediaAssetModel.evidence_role` /
  `EvidenceCandidate.role` — `classifier_same_frame`
  (`contracts.CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE`) — never overloading
  `identification`/`high_resolution_original`;
- computes its `GeometryAttribution` honestly with the existing
  `localization_attribution.geometry_attribution_for_update(..., same_frame=True)`
  function, gated on a proof (not a timestamp guess): the triggering
  `TrackUpdate`'s own `support_state` must be freshly `strong_detector_
  supported`/`weak_detector_supported`/`tracker_supported` this exact frame
  (`localization_attribution.geometry_source_from_support_state`), and
  `frame.frame_id == update.frame_id`;
- wires `species/classifier_input.py`'s already-built, already-tested
  resolver into the one seam that decides what BioCLIP actually sees
  (`product_repository._review_species_crop_context`), preferring a
  same-frame asset's own exact-box crop over the ordinary full-frame
  fallback, when one is linked to the Visit and provably eligible;
- persists the resolver's own decision as classifier-input provenance
  alongside the existing suggestion/attempt evidence, never as human review
  truth.

It does **not**: change MDv5, BioCLIP, the tracker's association/
confirmation/termination policy, `evidence_scoring.score_proposal_evidence`'s
identification/context/alternate competition, `candidate_visit_authority`/
`candidate_quality_gate`'s decisions, or `visit_episode_assembler.py` (zero
lines touched — the new evidence candidate flows through the *existing*
`evidence_by_generation` accumulation in `engine_runtime._run_assembly_tick`,
which already keys off `EvidenceCandidate.track_generation_id` for every
role, not a role-specific list). It does not promote the same-frame asset or
its derived crop to canonical/human-facing Visit evidence — the high-
resolution burst remains the Visit's own `representative_media_path`/primary
evidence, unconditionally, throughout.

## Frame lifecycle traced (pre-existing, before this milestone)

```
Camera Node analysis stream (low-res, ~1-5fps)
  -> AnalysisFrameEnvelope (real JPEG bytes, node-signed headers)
  -> CameraNodeAnalysisSource.pop_latest -> FramePacket (payload=real bytes, in memory)
  -> FrameDrivenObservationProvider.observe_live_frame(frame)
       -> ProviderNeutralFrameTracker.observe(frame, detections)
       -> TrackUpdate(s) (bounding_box, support_state, frame_id == frame.frame_id)
  -> LiveCameraNodeShadowSession._process_frame(frame, ...)
       for each "meaningful" TrackUpdate:
         -> BurstOpportunity -> BurstScheduler.decide -> EvidenceBurstRequest
         -> transport.request_evidence_burst(request)   [separate, LATER, real capture]
         -> EvidenceBurstFrame (own captured_at, own bytes)
         -> EvidenceCandidate(role="high_resolution_burst", same_frame=False)
       [frame.payload, the exact bytes `TrackUpdate` was computed from,
        went out of scope here, once this call returned -- discarded]
  -> engine_runtime._EngineSession accumulates evidence_candidates + burst bytes
       (burst bytes rescued into a bounded cache via `_harvest_burst_bytes`,
        because `EvidenceCandidate` itself carries no payload field)
  -> candidate_visit_adapter.attempt_candidate -> repository.create_candidate_visit_from_proposal
       -> MediaAssetModel(evidence_role="identification", ...) [the burst, persisted]
```

Three precise findings from tracing this path (2026-08-14, this milestone):

1. **The exact frame is available, decoded, and byte-complete in memory at
   exactly the point a burst is requested** — `frame: FramePacket` in
   `LiveCameraNodeShadowSession._process_frame`, with real `payload`,
   `width`, `height`, `captured_at`, `frame_id`, and the triggering
   `update.bounding_box` in the same scope. Nothing needs to be re-fetched,
   re-decoded, or re-detected to get it — see "path traced" above. This
   confirms milestone item 1's central question directly: **no new capture
   pipeline is needed.**
2. **`frame_tracker._update` stamps the *current* frame's own `frame_id`
   onto every `TrackUpdate` regardless of `support_state`, including a
   stale/carried-forward (`temporarily_lost`) one.** `frame.frame_id ==
   update.frame_id` alone is therefore *not* proof the box is fresh — only
   `support_state` (via `geometry_source_from_support_state`) proves that.
   `frame_driven_provider._candidate` gets this right today only because
   `_update_evidence` separately filters out `temporarily_lost` updates
   before ever building a candidate from them; this milestone's own
   eligibility check (`camera_node_live.py`, the burst-capture branch)
   makes that same proof explicit rather than inheriting it implicitly, since
   the "meaningful" burst-opportunity predicate it sits inside (`lifecycle_
   state == "confirmed" or confidence >= threshold`) reads `confidence`, not
   `support_state`, and a `temporarily_lost` update can still carry a
   leftover high `confidence` from an earlier genuine detection (see
   `test_same_frame_evidence_rejects_stale_carried_forward_geometry`).
3. **The species-assist seam (`_review_species_crop_context`) always reads
   pixels from the Review Queue item's own single `best_media_asset_id`
   file** — the crop box it computes is only ever applied to *that* asset's
   own pixels (`_load_bioclip_input_image(local_path=...)` takes one path).
   Pointing BioCLIP at a *different*, Visit-linked MediaAsset (the same-frame
   asset) therefore requires the crop-context override this milestone adds
   (`_classifier_input_override`), not merely a new crop-box tier — the
   override substitutes `local_path`/`size`/`mtime`/`content_type` for the
   one file that is actually opened, while every existing concurrency/
   identity re-check keyed on `media_asset_id` (the Visit's own primary
   asset) is deliberately left pointed at the original review frame,
   unchanged.

## Persistence design

**Evidence role**: `classifier_same_frame`
(`contracts.CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE`). Reuses the existing
`MediaAssetModel.evidence_role`/`VisitEvidenceLinkModel.evidence_role` free-
text columns (no CHECK constraint on either — verified before adding this
value) and the existing `_write_media_file`/`_create_candidate_visit_locked`
persistence path unmodified.

**Capture** (`camera_node_live.LiveCameraNodeShadowSession._process_frame`):
gated on the paired burst succeeding (`burst.status == "captured"`) — a
generation whose burst never captures cannot be admitted as a Visit anyway
(no `CandidateEvidenceItem` is ever built without real backing bytes for an
`identification`/`context` pick), so a same-frame asset would only ever be
orphaned evidence for a Visit that does not exist. Bounded to at most one
capture per track generation (`_same_frame_captured_generations`, cleared on
every genuine provider reset exactly like `_temporary_payloads`). Bytes are
held in a second bounded (max 8) temporary cache
(`_same_frame_temporary_payloads`/`temporary_same_frame_payload`), mirroring
the existing `_temporary_payloads`/`temporary_burst_payload` pattern for
burst bytes exactly.

**Harvest** (`engine_runtime.py`): `_harvest_same_frame_bytes` mirrors
`_harvest_burst_bytes`; `_run_assembly_tick` unions both caches into
`evidence_bytes`. `evidence_by_generation` (which the assembler-facing
`evidence_candidate_ids_by_generation` argument is built from) is filled from
*every* `EvidenceCandidate` with a `track_generation_id`, regardless of role
— the new role reaches `AssembledVisitProposal.evidence_candidate_ids` with
zero changes to `visit_episode_assembler.py`.

**Selection** (`candidate_visit_adapter.py`): excluded from the ordinary
identification/context/alternate scoring competition
(`evidence_scoring.score_proposal_evidence` never sees it), so it can never
displace the burst as "identification" or "context". Given its own
guaranteed, non-competitive slot in `_build_evidence_items`, positioned
right after `context` and before `alternate`s so it reliably survives the
repository's bounded `max_evidence_items_per_candidate` (default 4)
truncation even when 3 alternates are also present. At most one persisted
per Visit even when multiple constituent track generations (a multi-
tracklet-merged proposal) each independently captured one — chosen
deterministically (first by `evidence_candidates` arrival order).

**Geometry provenance**: `geometry_attribution_for_update(update,
same_frame=True, evidence_source_offset_ms=frame.source_offset_ms)` — the
existing function, never a bespoke one. `same_frame=True` is earned by the
capture-time eligibility check above, never inferred from a small gap.

## Classifier-input resolution (`_review_species_crop_context`)

`_classifier_input_override` runs first, ahead of the pre-existing
megadetector/activity/full_frame tiers, and only ever returns a *non-None*
result (superseding those tiers) when `species.classifier_input.
resolve_classifier_input` itself picks something better than full frame —
otherwise it returns `None` and every pre-existing tier runs completely
unchanged. Concretely:

1. Look up the Visit's linked `classifier_same_frame` MediaAsset (at most
   one, by construction) and any `activity_crop`/`user_refined_crop` assets
   (`PERSISTED_CROP_EVIDENCE_ROLES` — always empty today, see prior
   session's DB inventory, kept real and queried honestly for when reviewer
   refinement/activity crops eventually exist).
2. Build the resolver's `ClassifierInputSubjectFrame` from the same-frame
   asset when one exists, else from the Visit's own primary/review asset
   (whose own `geometry_attribution` is always `same_frame=False` for a
   burst, so tier 2 naturally, safely fails for it).
3. Call `resolve_classifier_input` unmodified. A `full_frame` result means
   "nothing new to offer" — return `None` immediately.
4. A non-`full_frame` result carries a `media_asset_id` that may differ from
   the Visit's own primary asset; re-stat that file fresh (mirroring the
   existing anti-TOCTOU discipline `_review_species_run_context` already
   applies to the primary asset) and build a `_ReviewSpeciesCropContext`
   whose new optional `classifier_input_*` fields describe it.

**`crop_source` DB value**: `bioclip_identification_attempts.crop_source`
carries `ck_bioclip_attempt_crop_source: IN ('megadetector', 'activity',
'full_frame')`. Rather than a table-rebuild migration to widen a CHECK
constraint on a heavily-constrained table for this alone, both new tiers
reuse `"activity"` there (closest existing meaning: a crop derived from
detected/tracked subject activity, not a raw MegaDetector box, not the bare
full frame) — the precise distinction lives, honestly and completely, in the
unconstrained `crop_provenance_json`/`SpeciesSuggestionModel.
evidence_region_json` columns instead, under a new `classifier_input` key:
`source_media_asset_id`, `input_type` (`same_frame_crop` | `persisted_crop`),
`same_frame`, `crop_method`, `source_width`/`source_height`,
`classifier_input_width`/`classifier_input_height`. `SpeciesSuggestionModel.
media_asset_id` itself is deliberately left unchanged — it stays the Visit's
own primary/review asset throughout (every other consumer that joins on it
to show "the Visit's evidence" is unaffected); the classifier-input asset is
provenance, not a redefinition of that field's own meaning.

## Non-promotion (product doctrine)

A `classifier_same_frame` asset is diagnostic/classifier-input evidence
only, never *preferred over* the canonical Visit image:

- excluded from `_effective_primary_preview_from_visit`'s candidate pool
  (before its bounded top-4 truncation) and from `_visit_evidence_frames_
  from_links` (the API's own `evidence_frames` list) — it can neither
  occupy a gallery slot nor ever be recommended as the effective primary
  **while any other, non-same-frame evidence item exists for the Visit**;
- `select_effective_primary`'s own known-role priority chain never matches
  the new role name, so even without the exclusions above it could only
  ever win via the last-resort `assessed[0]` fallback;
- `SpeciesSuggestionModel.media_asset_id`/`representative_media_path` never
  point at it (see above).

**Revised premise (All-Alternate Subject Evidence Recall Correctness v1,
see docs/all-alternate-subject-evidence-recall-correctness-v1-report.md):**
the assumption originally recorded here — "a same-frame asset is only ever
captured alongside a successful burst ... so an identification-role item
always exists first" — is true of the `EvidenceCandidate` *object*
`camera_node_live.py` constructs (a same-frame candidate is only ever
created immediately after a burst capture already succeeded this same
frame), but was never actually guaranteed of the *persisted evidence item*:
the burst's own bytes can still be lost before harvest (a real, disclosed,
bounded residual — see `engine_runtime._MAX_CACHED_BURST_BYTES`'s own
docstring), or the burst's own crop can independently fail the scorer's own
eligibility checks, while the same-frame capture — proven, by its own
construction, to be *this exact tracked/detected frame* — survives. Real
field evidence (two confirmed-real-bird misses in Representative Daylight
Gate A Field Acceptance v12's own session, though this milestone found
their own specific causes to be elsewhere — see the report's own "v12
reproduced misses") motivated tracing this gap to a genuine, silent recall
defect: `candidate_quality_gate.evaluate_evidence_admission` rejected the
*entire proposal*
(`reject_no_identification_or_context`), discarding a real, geometrically
-proven subject capture, whenever a same-frame asset turned out to be a
proposal's *only* surviving evidence. The gate now accepts a same-frame
item as a narrowly-scoped last-resort `primary` in exactly that one case
(never when a real burst/other identification/context evidence exists),
and the two presentation exclusions above are each now conditional on
non-same-frame evidence actually existing, so a same-frame-only admitted
Visit keeps its one honest photo instead of showing none at all. This does
not change the *preference* order in any other case: a same-frame asset
still never outranks or displaces a real burst.

Still fully queryable directly by `evidence_role` for diagnostics/species
inference — never hidden from the database, only from human-facing
presentation surfaces (except, now, in the one same-frame-only case above).

## Retention

No new logic: `_storage_retention_evaluation` iterates every `MediaAssetModel`
generically (age, Visit linkage, review status, primary/wildlife
protections) with no role-specific special-casing beyond the pre-existing
`activity_crop`/`user_refined_crop` protection, which does not apply to this
role. A `classifier_same_frame` asset ages out under exactly the same rules
as a `context`/`alternate` asset. `_classifier_input_override` degrades
safely (falls through to full frame) whenever the row is gone, the file is
gone, or the geometry lineage fails to parse — never raises, never blocks
species inference (see `test_deleted_same_frame_file_degrades_safely_
without_blocking_inference`, `test_malformed_geometry_attribution_falls_
back_without_raising`).
