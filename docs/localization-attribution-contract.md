# Localization Attribution / Detection Geometry Lineage v1 contract

Status: Phase 2 "Detection Quality Accounting" milestone (see
[roadmap.md](roadmap.md)), motivated by the 2026-08-11 post-fix field
validation's own "single best next milestone": genuine birds appeared and
were tracked in two independent real Camera Node sessions (2026-08-10,
2026-08-11), and in both, the persisted candidate's evidence box failed to
localize the bird -- zero IoU overlap, both times (candidates 004/005 and
007; see `data/field-acceptance/2026-08-11-post-fix-field-validation/
FINAL-REPORT.md` §9-10, §16, and the `post-fix-field-validation-2026-08-11`
project memory). That report could not distinguish *why*: "the currently
-retained confidence lineage carries confidence, offset, frame id, and
strength -- but no raw per-detection box geometry... not yet possible to
tell whether MDv5's own raw per-frame output was well-localized on the bird
in some frame and the tracker/evidence-frame-selection picked a stale
moment... or whether MDv5 itself never produced a good box near the bird at
all." This milestone closes exactly that gap.

## Boundary

This is a measurement/diagnostic contract, not a detector change, a
tracker-policy change, or a Visit-assembly change. It:

- preserves the raw per-detection box behind every retained Detection
  Quality Accounting v1 confidence sample (`contracts.
  DetectionEvidenceSample.bounding_box`);
- preserves, per `TrackUpdate`, the exact source offset at which its own
  `bounding_box` was last genuinely established by a detector or
  tracker-support observation, as distinct from the update's own emission
  time (`contracts.TrackUpdate.bounding_box_source_offset_ms`);
- adds one new, small, bounded fact -- `contracts.GeometryAttribution` --
  answering, for one persisted evidence image, which observation supplied
  its box and whether that image provably represents the same moment as
  that observation;
- adds a deterministic, pure diagnostic (`mockingbird.observation.
  localization_attribution.classify_localization_attribution`) that
  classifies a localization failure into one of five categories using only
  already-retained lineage facts -- never pixel content, never a
  species/animal-presence judgment.

It does **not**: change `ProviderNeutralFrameTracker`'s association,
confirmation, or termination policy; change `evidence_scoring.
score_proposal_evidence`'s selection/eligibility logic; change
`candidate_visit_authority.evaluate_candidate_authority` or
`candidate_quality_gate.evaluate_evidence_admission`'s decision logic;
change `visit_episode_assembler.py` in any way (structurally proven -- see
"Why `visit_episode_assembler.py` needed zero changes," below); replace,
retrain, or tune MDv5; or grant this diagnostic's output any admission,
scoring, or Visit-assembly authority. The classification is diagnostic
accounting, exactly like `detection_quality_accounting.py`'s six-stage
report and `admission_policy.py`'s shadow sweep -- evidence a report or a
future shadow evaluation may read, never itself observational truth (see
"The truth boundary" in product-doctrine.md).

## Geometry path traced (pre-existing, before this milestone)

```
MDv5 raw tensor -> mdv5_decoder.decode_md_v5_raw (source-coordinate box)
                 -> onnx_provider._observation -> DetectionObservation.bounding_box
                 -> frame_tracker._observe_detection -> _Track.bounding_box (overwritten every match)
                 -> TrackUpdate.bounding_box (one box: this track's *current* box)
                 -> EvidenceCandidate.subject_geometry
                 -> CandidateEvidenceItem.subject_geometry
                 -> MediaAssetModel.normalized_track_box_json (persisted)
```

Five precise findings from tracing this path against the accepted
`frame-driven-onnx-cuda` provider family (`frame_driven_provider.py`,
`camera_node_live.py`) -- the pipeline that actually produced every real
field candidate to date:

1. **`_Track.bounding_box` is a single current value, overwritten on every
   match, never a retained history.** `frame_tracker._observe_detection`/
   `_observe_tracker_support` each simply assign `track.bounding_box = ...`.
   Before this milestone, the *only* per-observation box history anywhere
   was `Tracklet.start_bounding_box`/`end_bounding_box`/`geometry_envelope`
   -- three collapsed summary boxes per confirmed track generation, built by
   `visit_episode_assembler.build_tracklets` from `TrackUpdate.bounding_box`
   values. Every intermediate per-frame box was already lost by the time a
   `Tracklet` existed.
2. **`AssembledVisitProposal` (and `VisitProposal`) carry no geometry field
   at all.** Even the three collapsed tracklet-level boxes above are
   discarded at proposal assembly -- `visit_episode_assembler._build_
   proposal` copies temporal span, lineage ids, and `confidence_evidence`,
   but no bounding box. The box a reviewer eventually sees is supplied
   entirely independently, by evidence selection, with no cross-check
   against tracklet/proposal geometry at all.
3. **On a genuinely live Camera Node session, only `high_resolution_burst`
   -role `EvidenceCandidate`s can ever be persisted.** `evidence_scoring.
   score_proposal_evidence` and `candidate_visit_adapter._build_evidence_
   items` both require real backing bytes (`evidence_bytes.get(candidate_
   id)`); `engine_runtime._harvest_burst_bytes`/`candidate_visit_authority_
   cli._burst_evidence_bytes` populate that mapping *only* for `role ==
   "high_resolution_burst"` (keyed by the burst's own `content_hash`). The
   low-resolution `tracked_best`/`detector_confirmed`/`pretrigger`/`final_
   supported`/`alternative` candidates `frame_driven_provider._candidate`
   also emits are structurally correct evidence (their own box and image
   are always the same analysis frame -- see finding 5) but their raw
   analysis-frame bytes are never cached anywhere retrievable by
   `media_asset_id`, so they can never actually be selected as a real,
   byte-backed candidate for a live session. This is not a defect this
   milestone fixes (out of scope: redesigning evidence retention); it is
   the reason the burst path's own timing gap, below, is the operationally
   dominant failure mode today.
4. **The burst path's box and its own persisted image are, by construction,
   two different real moments, and the gap between them was computed and
   then thrown away.** `camera_node_live.py`'s `LiveCameraNodeShadowSession.
   _process_frame` builds a `BurstOpportunity`/`EvidenceBurstRequest` whose
   `subject_geometry=update.bounding_box` is the *triggering* analysis
   frame's box; `transport.request_evidence_burst` then performs a real,
   separate HTTP round trip to the Camera Node and returns `EvidenceBurstFrame`
   with its own real `captured_at` and an already-computed
   `request_to_capture_ms`/`temporal_alignment` (`camera_node_live.
   CameraNodeHttpTransport.request_evidence_burst`, `media_contracts.py`).
   The persisted `EvidenceCandidate` reuses the *trigger-time* box
   (`subject_geometry=request.subject_geometry`) stamped onto the *later*
   burst image, and `quality_facts` records `request_to_capture_ms`/
   `temporal_alignment` -- but `candidate_visit_adapter._build_evidence_
   items` never reads `quality_facts` at all when building a
   `CandidateEvidenceItem`, so neither fact ever reached persistence.
   `temporal_alignment` itself is also a coarser fact than its name
   suggests: `"supported"` means only "captured before the request's own
   deadline," never "the tracked subject is still where the box says" --
   `evidence_scoring._score` already treats `"supported"` as `"aligned"`
   and awards it a positive score component.
5. **`frame_driven_provider._candidate`'s own low-resolution roles are, by
   construction, always genuinely aligned -- except `pretrigger`.**
   `_seed_evidence`/`_update_evidence` call `_candidate(frame, update, role)`
   with `frame` and `update` from the same per-frame processing step for
   every role except `pretrigger`, which deliberately reads an *earlier*
   retained frame (`prior[-1]`) while still using the *current* `update`'s
   box -- the opposite-direction version of the same misalignment shape the
   burst path shows. This path is structurally sound; its practical
   irrelevance to real field candidates today is finding 3, above, not a
   flaw in this path itself.

### Why `visit_episode_assembler.py` needed zero changes

Geometry attribution is a per-evidence-item fact (`EvidenceCandidate.
geometry_attribution`), computed entirely upstream of Visit assembly, at the
exact two sites that already construct `EvidenceCandidate.subject_geometry`
(`frame_driven_provider._candidate`, `camera_node_live.py`'s burst evidence
construction). `Tracklet`/`AssembledVisitProposal`/`VisitProposal` reference
evidence only by id (`evidence_candidate_ids`); they never carry per-item
facts at all, so nothing about assembly needed to change for this
lineage to exist. Separately, `DetectionEvidenceSample.bounding_box`
(finding 6, below) flows onto `Tracklet.confidence_evidence`/
`AssembledVisitProposal.confidence_evidence` automatically, for free,
through the existing, completely unmodified `merge_confidence_evidence`
and `asdict(...)`-based JSON serialization the Detection Quality Accounting
v1 contract already established -- confirmed by inspection, not asserted:
neither function was touched by this milestone, and both already operate
generically over whatever fields their dataclass arguments carry.

## Geometry lineage added

1. **`contracts.DetectionEvidenceSample.bounding_box`** (new, additive,
   defaulted `None`): the exact raw source-coordinate box behind one
   genuine matched detection, already in scope at the one call site that
   builds every other field on this dataclass (`frame_tracker.
   _evidence_sample`). Free-rides the existing bounded/truncation machinery
   (`MAX_TRACK_CONFIDENCE_SAMPLES`, `ConfidenceEvidenceSummary.sample_
   truncated`) -- no new cap invented. This alone answers "for relevant
   detector observations, preserve raw detector box, detector confidence,
   detector class [already `Tracklet.broad_class`/`ConfidenceEvidenceSummary.
   broad_class`, unchanged], frame/source offset, and associated track
   ID/generation [already `Tracklet.generation_id`/`track_ids`, unchanged]."
2. **`contracts.TrackUpdate.bounding_box_source_offset_ms`** (new,
   additive, defaulted `None`): the `source_offset_ms` at which `bounding_
   box` was actually last (re)established by a genuine detector or
   tracker-support observation, exposing `frame_tracker._Track.last_
   offset_ms`'s own already-correct internal invariant (updated only
   inside `_observe_detection`/`_observe_tracker_support`, left untouched
   on a "coasting" widened-tolerance frame). This is the fact that makes a
   stale, carried-forward box provably distinguishable from a fresh one --
   see `test_bounding_box_source_offset_ms_lags_during_a_coasted_frame`.
3. **`contracts.GeometryAttribution`** (new): a small, bounded, single
   record -- not a list -- naming, for one `EvidenceCandidate`: `geometry_
   source` (`"detector"` / `"tracker"` / `"carried_forward"`, derived
   losslessly from `TrackUpdate.support_state`, which is already correct by
   construction -- see "Why `support_state` alone is sufficient," below),
   `geometry_source_offset_ms`, `geometry_source_observation_id`, `geometry_
   source_confidence` (the exact `DetectionEvidenceSample` this geometry
   came from, when one exists), `same_frame` (a structural fact the
   producer already knows, never guessed), and `geometry_evidence_gap_ms`
   (the real magnitude: the transport's own already-measured
   `request_to_capture_ms` for a burst, or the derived `|offset delta|`
   otherwise). Attached to `EvidenceCandidate.geometry_attribution`
   (additive, defaulted `None`), computed by
   `localization_attribution.geometry_attribution_for_update`/
   `geometry_attribution_for_burst` at exactly the two sites named above.
4. **Persistence** (schema 33, `_migrate_to_observation_geometry_lineage`,
   mirroring `_migrate_to_observation_confidence_evidence`'s own additive-
   column pattern exactly): `CandidateEvidenceItem.geometry_attribution_
   json` (repository-level, serialized by `candidate_visit_adapter._build_
   evidence_items`, the one place that already imports the engine-side
   `EvidenceCandidate`) flows onto the new, nullable `media_assets.
   geometry_attribution_json` column -- co-located with the existing
   `normalized_track_box_json` it explains, at the same per-evidence-item
   granularity (not the coarser per-candidate `observation_candidate_visits`
   ledger, since misalignment is fundamentally a property of one specific
   persisted image). `DetectionEvidenceSample.bounding_box` needs no schema
   change at all (see "Why `visit_episode_assembler.py` needed zero
   changes," above) -- it already rides inside the existing `observation_
   candidate_visits.confidence_evidence_json` column.

### Why `support_state` alone is sufficient for `geometry_source`

`TrackUpdate.support_state` already distinguishes exactly the three kinds
this contract needs, by construction, with no possible disagreement:
`strong_detector_supported`/`weak_detector_supported` are set only inside
`frame_tracker._observe_detection`, which also freshly sets `bounding_box`/
`last_offset_ms` in the same call; `tracker_supported` only inside
`_observe_tracker_support`, same guarantee; `temporarily_lost` is the one
state reached when neither ran this frame, so `bounding_box` is simply
whatever it was last genuinely set to. A second, independently-derived
offset-freshness check could only ever disagree with `support_state` if the
tracker's own invariant were broken -- which would be a tracker bug to fix
in `frame_tracker.py`, not a fact to paper over in a diagnostic reading its
output.

### Honesty rules (no fabricated geometry for legacy records)

Identical discipline to Detection Quality Accounting v1: every new field is
additive and defaults to `None`/empty, never a fabricated zero or box.
`GeometryAttribution` itself validates that a negative gap or a `same_
frame=True` result with a nonzero gap can never be constructed
(`__post_init__`). `localization_attribution.geometry_attribution_from_json`
returns `None` for missing, empty, or malformed JSON rather than raising or
guessing. A record created before schema 33 reads back `geometry_
attribution_json IS NULL` after migration, proven by `test_schema_v33_adds_
geometry_attribution_column_without_fabricating_legacy_data` (mirrors the
existing schema-v31 test exactly).

## Attribution diagnostic

`localization_attribution.classify_localization_attribution(attribution,
*, confidence_evidence=None, misalignment_gap_threshold_ms=5000)` is pure
(no filesystem, network, CUDA/ONNX Runtime/OpenCV, product-repository, or
SQLAlchemy import -- the same structural convention every sibling Stage
6.x/7 decision module follows, checked by `test_localization_attribution_
module_has_no_product_repository_import`) and deterministic. `misalignment_
gap_threshold_ms` reuses -- not invents -- `TrackerConfiguration.maximum_
unsupported_detector_ms`/`FrameDrivenSettings.maximum_unsupported_
detector_ms`'s own already-calibrated default (5000ms, "how long may a
track go with no fresh detector confirmation"), applied one layer up as
"how long may an evidence image's own capture drift from its geometry's own
source moment before that geometry can no longer be trusted to represent
what the image actually shows."

### Attribution decision order

1. **`insufficient_geometry_lineage`** -- no lineage retained at all (a
   legacy record predating this contract, or a caller that never computed
   one). Checked first and never bypassed by a guess.
2. **`evidence_geometry_misaligned`** -- the evidence image is not provably
   the same moment as the geometry's own source observation (`same_frame is
   not True`), and the gap is unknown or exceeds the bounded threshold.
   Checked *before* asking what kind of observation supplied the geometry:
   if the image itself cannot be trusted to show the same moment, the kind
   of observation that produced the box is moot until that is resolved.
3. **`detector_hit_then_lost`** -- the geometry is a stale, carried-forward
   box, *and* this tracklet's own confidence evidence proves the detector
   had genuinely confirmed the subject earlier, strictly before the
   geometry's own source moment.
4. **`tracker_drift`** -- the geometry came from tracker-support (patch)
   matching, not a genuine detection, this exact moment.
5. **`detector_off_target`** -- by elimination: a genuine, temporally
   -aligned detector hit with no known intervening lineage artifact. If it
   still misses a visible subject, the raw detector output on that exact
   frame is the most defensible attribution available from lineage alone
   -- this is diagnostic accounting, not a claim that MDv5 is *at fault* in
   some deeper sense a human reviewer's own judgment would still be needed
   to confirm.
6. **`insufficient_geometry_lineage`** (fallback) -- a carried-forward box
   with no confidence evidence to corroborate step 3 against, or an
   unrecognized `geometry_source`.

These five category names match the task's own suggested vocabulary
exactly; nothing else in this codebase currently depends on the literal
strings, so a future consumer may rename them without a second migration.

## Retrospective analysis: candidates 004/005 and 007/008

Direct application of `classify_localization_attribution` to these four
historical candidates is **`insufficient_geometry_lineage`** for all four,
honestly: they were captured before this contract existed, so no
`GeometryAttribution` was ever computed or persisted for them, and no
per-detection raw box was ever retained on their `confidence_evidence`
samples either. This milestone's own honesty rules (above) forbid
reconstructing one after the fact -- there is no way to know, for any of
the four, which real observation actually supplied the persisted box, so
none of the four more specific categories may honestly be claimed for any
of them. **Nothing here rewrites `data/field-acceptance/.../candidates-
extract.json` or any other historical artifact.**

What honestly *can* be computed, without inventing any fact, is a coarser,
manually-reconstructed timing signal from fields the historical record
already retains verbatim: each candidate's own persisted media asset
`captured_at` (a real wall-clock timestamp) converted to a session
-relative offset using that session's own recorded `observation/start`
timestamp, compared against `confidence_evidence.last_detection_offset_ms`
(already retained, unaffected by this contract). This is exactly the
"coarse, retained-facts-only" analysis this contract's own honesty rules
permit -- and it is *not* the same claim `classify_localization_attribution`
itself makes; see the caveat below.

| Candidate | Session start (UTC) | Media `captured_at` (UTC) | Reconstructed offset | `last_detection_offset_ms` | Gap |
|---|---|---|---|---|---|
| 007 | 2026-08-11T10:42:03.462757Z | 2026-08-11 10:55:02.678040 | ~779,215 ms | 769,641 ms | **~9.57s** |
| 008 | 2026-08-11T10:42:03.462757Z | 2026-08-11 11:03:44.929593 | ~1,301,467 ms | 1,291,916 ms | **~9.55s** |
| 004 | 2026-08-10T20:28:53.834987Z | 2026-08-10 21:01:23.928039 | ~1,950,093 ms | 1,960,940 ms | ~-10.85s (image *precedes* this candidate's own last sample; see below) |
| 005 | 2026-08-10T20:28:53.834987Z | 2026-08-10 21:01:23.928039 | ~1,950,093 ms | 1,972,979 ms | ~-22.89s (same shared image, see below) |

**Reading candidates 007/008**: both independently show the persisted
evidence image captured roughly **9.5-9.6 seconds** after the last
detector-confirmed sample this candidate's own confidence lineage retains
-- a gap of the same order of magnitude as `LiveCameraNodeShadowSession`'s
own `burst_deadline_ms` budget (10,000ms default), consistent with, though
not proof of, this contract's own `evidence_geometry_misaligned` mechanism.
For candidate-008 (the clean feeder-hardware false positive, a static
object), a multi-second-stale box would not visibly matter; for candidate
-007 (a real, presumably-moving bird), it plausibly explains the
independently-measured ~150px / ~2-box-height offset. **This is not the
same claim the diagnostic itself makes** -- it is a hand-reconstructed
approximation of `geometry_evidence_gap_ms` from wall-clock arithmetic the
historical record happens to retain, not the exact, real, transport
-measured `request_to_capture_ms` this contract's own new field would
capture automatically for a fresh session going forward, and it says
nothing about which specific observation (fresh detector hit vs.
tracker-support vs. already-stale) supplied the box in the first place.
Both remain honestly `insufficient_geometry_lineage` under
`classify_localization_attribution` itself.

**Reading candidates 004/005**: these predate the Visit Continuity fix
(`b990ad1`) and are already known, separately, to be a duplicate-admission
artifact (candidate-005's tracks are a strict superset of candidate-004's;
see `[[visit-continuity-provisional-admission-fix-v1]]`) -- both share the
*identical* persisted evidence image, whose own `captured_at` sits *inside*
004's own detection span and *before* 005's own later last-detection
sample (a different shape from 007/008, consistent with evidence selection
re-picking the same already-successful earlier burst for a later,
extended proposal rather than requesting a fresh one -- see "Two
independent mechanisms," below). This confirms these two historical
candidates are not a second, independent instance of the *burst-delay*
shape 007/008 show; they are better explained by the already-fixed
continuity defect. No further conclusion is drawn from 004/005 here.

### Two independent mechanisms, not one

This retrospective pass surfaces that "the persisted box doesn't match a
visible bird" was already known to have at least two structurally distinct
causes in this codebase's own history: (a) the Visit Continuity /
Provisional Admission Fix v1 defect (004/005 -- a *duplicate-admission*
shape, already fixed), and (b) the burst-capture timing gap this milestone
newly instruments (007/008 -- a *staleness* shape, not yet fixed, not in
this milestone's scope to fix). Conflating them would have been a mistake;
this contract's own lineage is what makes them distinguishable going
forward.

## Live validation

Deployed commit `cf60b21` to the real Windows/CUDA dev environment
(`scripts/deploy_windows_dev.py`; two attempts hit the same already
-documented transient `WSL ERROR: UtilAcceptVsock:273: accept4 failed 110`
interop fault the 2026-08-10 session recorded, each leaving a safe,
inert, empty partial release directory the tool itself refused to silently
overwrite -- removed manually per its own instruction, exactly the
established recovery precedent; the third attempt deployed cleanly).
Independently verified via the real product API: `GET /api/product/
instance` -> `git_commit: cf60b21f07495db366abea0bc798d355ca418b85`; `GET
/api/product/health` -> `database_schema_version: 33`, `ready: true` --
schema 33 migrated cleanly against the real, already-populated production
database (the same database holding candidates 001-008) with no data loss.

Ran a single bounded ~10-minute live Camera Node session (2026-08-11
13:27:31Z-13:37:33Z, `stream-ca892992771c`, `stopped_reason: "user_stopped"`
-- deliberately short, not another field cohort). CUDA execution confirmed
live (`selected_execution_providers: [CUDAExecutionProvider,
CPUExecutionProvider]`, `device_type: "GPU"`), model provenance unchanged
(`fingerprint` matches `[[accepted-observation-model-provenance]]`
exactly), `score_threshold: 0.1` unchanged. Real activity: 387 track
updates, 217 evidence candidates, and 52 assembled proposals processed
through the modified pipeline; 0 candidates created (26 `blocked_
continuation_pending`, 19 `blocked_ambiguous_boundary`, 7 `blocked_missing_
evidence` -- all ordinary, already-understood suppression reasons, none of
them a new "failed" outcome). The deployed app's own log
(`mockingbird.log`, checked directly) contains zero `ERROR`/`Exception`/
`Traceback` lines and zero `invalid_geometry_attribution` validation
failures across the entire session; the engine stayed healthy and serving
requests the whole time.

**What this proves and what it does not**: the new lineage code path
(`geometry_attribution_for_update`/`geometry_attribution_for_burst`,
called on every one of 217 real evidence candidates this session) runs
correctly against real hardware, a real Camera Node, and real MDv5
inference without ever raising or crashing -- confirmed directly from the
log, not inferred. It does **not** include a freshly-*persisted* candidate
from this exact session: none of this session's 52 proposals resolved to
an admitted candidate Visit within the deliberately short bounded window
(consistent with the 2026-08-11 field session's own finding that a real
encounter's tail boundary can take 15+ minutes to certify final) -- an
honest, expected limitation of a short smoke, not a defect. No genuine
animal was independently confirmed present or absent in this session
(no visual review was performed, matching scope: this smoke's purpose is
telemetry population, not a new field cohort). Consistent with Detection
Quality Accounting v1's own already-documented limitation, a live session's
own in-flight per-proposal facts are transient and unrecoverable once the
session ends without an admitted candidate -- there is no way to inspect
this specific session's own near-miss proposals after the fact.

## Non-goals honored

No detector/model change (MDv5 untouched). No tracker-policy tuning
(`TrackerConfiguration`/`ReconnectBridgeConfig` untouched; `frame_tracker.py`'s
only changes are additive fields threaded through unchanged control flow,
proven by the complete pre-existing `tests/test_frame_tracker.py` suite
passing unmodified). No Visit-assembly change (`visit_episode_assembler.py`
has zero lines changed -- see "Why `visit_episode_assembler.py` needed zero
changes," above). No evidence-selection/scoring change (`evidence_scoring.py`
untouched). No admission/authority-gate change (`candidate_visit_authority.py`/
`candidate_quality_gate.py` untouched). No production threshold change
(`score_threshold` untouched). No species work. No shadow-admission-policy
promotion. No large field cohort (see the final report for the bounded
smoke session actually run).

## Authority and limitations

`localization_attribution.py` imports no product repository, filesystem
path, network connection, or CUDA/ONNX Runtime/OpenCV runtime, and creates
no Event, Visit, MediaAsset, ReviewLabel, or reviewed truth.
`GeometryAttribution`/`LocalizationAttributionResult` are diagnostic
lineage, not observational authority: a report or a future shadow
evaluation may read them, but nothing may treat a `detector_off_target`
classification as proof an animal was actually missed, or any other
classification as proof of a specific root cause, without a human
reviewer's own visual confirmation -- exactly the same evidence-not-truth
boundary `ConfidenceEvidenceSummary` already establishes.

Known limitations disclosed, not hidden: `geometry_source_confidence`/
`geometry_source_observation_id` are populated only when the matching
`DetectionEvidenceSample` can be found by exact offset equality
(`localization_attribution._matching_confidence_sample`) -- a legacy or
externally-reconstructed `TrackUpdate` with an empty `confidence_samples`
tuple honestly reports `None` for both rather than guessing. The
`detector_hit_then_lost` category requires `confidence_evidence` to be
supplied by the caller; a caller that omits it (for example a bare
`GeometryAttribution` inspected in isolation, without its owning
tracklet/proposal) will honestly fall back to `insufficient_geometry_
lineage` for a carried-forward box rather than a false negative wearing
the wrong label. Neither `frame_driven_provider.py`'s low-resolution roles
nor this contract's own lineage change *which* evidence a live Camera Node
session can actually persist (finding 3, above) -- that remains a
byte-retention limitation this milestone does not attempt to fix.
