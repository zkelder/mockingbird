# Persistent Scene Confusor Suppression v1 contract

Status: Phase 1 "Trustworthy Single-Site Observatory" milestone (see
[roadmap.md](roadmap.md)), motivated directly by
[observational-quality-closure-v1-report.md](observational-quality-closure-v1-report.md):
independent visual re-adjudication of a real 70-Visit, four-real-day,
non-session-concentrated cohort found **52.9% (37/70) of admitted candidate
Visits showed no animal at all**, and 76% of those false positives clustered
into just six recurring static geometric hot spots -- a roof/chimney shadow,
a feeder-silhouette texture, driveway/grass edges -- not diffuse noise.
Confidence-gated admission was directly swept against that same cohort and
formally rejected (see "Production authority gate" in
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)):
no threshold on raw detector confidence or species-suggestion confidence
clears both "materially reject false positives" and "do not materially lose
real animals" together. This milestone answers the resulting open question:
**can MockingBird suppress recurring scene-specific false detections without
causing real animals using those same locations to disappear?**

## Boundary

This milestone does not: change `ProviderNeutralFrameTracker`, change
`visit_episode_assembler.py`'s assembly decisions (zero lines changed --
geometry stays confined to the evidence-item layer, see "Why geometry lives
at the evidence-item layer, not the proposal layer" below), change
`candidate_visit_authority.evaluate_candidate_authority` or
`candidate_quality_gate.evaluate_evidence_admission`'s own decision logic
(both remain untouched; this adds a third, sibling repository-local check,
structurally identical in kind to the existing `blocked_privacy_zone`),
change the MDv5 `0.1` production `score_threshold`, promote any confidence-
gated admission policy, reopen detector training/promotion, or expand
species-model work. It adds one new, bounded, durable, per-Stream mechanism
that a real admitted-or-attempted proposal's own persisted evidence geometry
is checked against, immediately before evidence is written to disk.

## Why recurrence, not confidence or single-visit stillness

A static scene artifact (a shadow, a feeder-silhouette texture) and a real
bird perched motionless at the same spot for a whole visit produce
*structurally identical* single-encounter evidence: a small, possibly-low-
confidence box that does not move much. Neither raw detector confidence
(already tested and rejected at cohort scale, above) nor within-visit
stillness can safely tell them apart without risking exactly the recall harm
this milestone's own governing constraints prohibit -- a bird may repeatedly
perch on exactly the same feeder, branch, lawn patch, roof edge, or fence
post. What *does* differ is repetition **across separate encounters**: one
assembled proposal is one bounded episode
([tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md))
regardless of how long the underlying visit lasted, so a single five-minute
stationary bird contributes exactly one occurrence to a region no matter how
still it sat -- it is structurally incapable of building suspicion by
itself. Suspicion only accumulates from many *separate* admission attempts
recurring at closely matching geometry, a materially safer claim than "this
subject did not move."

## Mechanism: pure decision, durable per-Stream history

`mockingbird.observation.scene_confusor` is pure -- no filesystem, network,
CUDA/ONNX Runtime/OpenCV, product-repository, or SQLAlchemy import,
structurally enforced the same way every sibling Stage 6.x/7 decision module
in this package is
(`test_scene_confusor_module_has_no_product_repository_import`). It never
fetches, creates, or evicts a durable region record itself; the one impure
seam, `mockingbird.repository.product_repository`, fetches a small, bounded,
already-capped snapshot of a Stream's own durable regions and supplies it
here as `SceneRegionSnapshot`s -- mirroring
`candidate_visit_authority.AuthorityState` exactly: a pure decision over an
already-fetched fact, never a live database handle threaded through a "pure"
module.

### Geometry matching -- reused, not invented

`find_matching_region` reuses `burst_scheduler.BurstScheduler`'s own
already-validated IoU/centroid/size-ratio formula and thresholds (IoU >=
0.3, centroid distance <= 0.05, size ratio within 0.35 -- the same
convention `detector_benchmark.cluster_static_false_positives` and
`temporal_capture.RecurringGeometryTracker` independently already use for
the same purpose at other pipeline stages), duplicated rather than imported,
matching this package's own established "each pure module stays
self-contained" convention. No exact coordinate or scene name is ever
compared; every test is a general, relative geometry test that behaves the
same for any camera layout or subject location -- satisfying "do NOT
hard-code the six current coordinates or scene names."

### Why a durable table, not another in-memory ledger

`burst_scheduler._RecurrenceGroup`, `detector_benchmark.
cluster_static_false_positives`, `temporal_capture.RecurringGeometryTracker`,
and the existing `counterfactual_lineage.CounterfactualLedger` are all
in-memory, per-session (or per-offline-batch) only -- every one is reset on
Stop/Start or a fresh process. A persistent scene confusor is, by
definition, a fact about the *camera and scene*, not about any one session;
an in-memory-only mechanism could never build cross-session suspicion at
all, since the recurring false Visits this milestone measured were spread
across five real sessions over four real days. `SceneConfusorRegionModel`
(schema 34, `scene_confusor_regions` table) is the one place in the whole
Observation Engine v2 tree that remembers recurring candidate geometry
*across* sessions and app restarts. `id` is a stable, content-addressed
identity (`scene_confusor.region_fingerprint`, deterministic from
`(stream_id, broad_class, rounded representative_box)`), never a
session/process identity, so it survives restarts unlike every in-memory
precedent above.

### Why geometry lives at the evidence-item layer, not the proposal layer

`AssembledVisitProposal` carries no geometry field at all -- discarded at
proposal assembly, exactly like the pre-Localization-Attribution-v1 state
this same lineage gap existed for once already (see "Geometry path traced"
in
[localization-attribution-contract.md](localization-attribution-contract.md)).
Two options existed: add a new proposal-level envelope field (touching
`visit_episode_assembler.py`, mirroring how `confidence_evidence` was added
there), or check the geometry of the already-selected `identification`
evidence item at the repository layer, where it is already available with
zero further plumbing. This milestone chose the second, smaller-footprint
option deliberately: it keeps `visit_episode_assembler.py`,
`candidate_visit_authority.py`, and `candidate_quality_gate.py` completely
unchanged (matching this codebase's own strong, repeated precedent for
minimal-footprint stage additions), and it checks the *exact* box a reviewer
will actually see -- the more semantically correct target for "does this
recurring image-space region look like a confusor" than an internal tracker
envelope nobody sees. A within-track motion/displacement signal was
considered and rejected for the same reason single-visit stillness was
rejected above: a genuinely stationary real bird and a static artifact both
show near-zero displacement *within one track*; the safe signal is
cross-encounter recurrence, not intra-track motion.

## Decision order

`evaluate_scene_confusor_suspicion` is pure and deterministic. In order:

1. **No geometrically-matching region at all** -> `not_suspected` (a brand
   new location always gets the benefit of the doubt -- matches
   `burst_scheduler`'s own "first occurrence never suppressed" precedent).
2. **The matched region has ever been confirmed to hold a real animal by
   authority-eligible reviewed truth** -> `not_suspected`, unconditionally,
   regardless of how much unreviewed recurrence history has also
   accumulated there. See "Reviewed-truth interaction," below -- the
   mechanism's core recall-safety guarantee.
3. **The matched region has not yet recurred `min_occurrences_to_suspect`
   times** -> `not_suspected` (a single visit, however long or still,
   cannot alone build suspicion).
4. **The matched region's own accumulated geometry across its recurrences
   is more varied than `geometry_spread_ceiling`** -> `not_suspected` (see
   "Why a geometry-spread requirement, not occurrence count alone," below).
5. **This candidate's own confidence is materially higher than anything
   this region has ever produced** (`stronger_confidence_delta`, reused
   from `burst_scheduler`'s identical novelty signal) -> `not_suspected`.
6. **This candidate's own confidence independently clears
   `strong_detection_threshold`** (reused from `frame_tracker.
   TrackerConfiguration.strong_detection_threshold` /
   `encounter_accounting.STRONG_CONFIDENCE_THRESHOLD`), regardless of this
   region's own history -> `not_suspected`. A second, absolute escape,
   distinct from step 5 -- see "A second replay finding," below, for why
   the relative escape alone was not enough.
7. **Otherwise** -> `suspected_confusor`. Never a permanent verdict on the
   region itself -- only a decision about this one candidate, at this one
   moment, given the evidence available now.

## Why occurrence count alone is not enough

A naive design (recurrence count only, no spread requirement) was built
first and directly replay-simulated against the real 70-event cohort (see
"Replay of the previous cohort," below, for the cohort itself). It found a
genuine, demonstrated recall hazard, not a hypothetical one: a real bird
landing at a popular, frequently-visited feeder perch, near (but not at)
an unrelated, coincidentally-nearby false detection, could be wrongly
suspected the moment enough total occurrences (real and false combined)
accumulated at closely matching geometry -- occurrence count alone cannot
tell "many different real visitors at a popular spot" apart from "one
static artifact re-detecting itself," especially early, before either
pattern has had a chance to show its own true shape.

Direct measurement on the real cohort found the differentiating signal:

| Region (real cohort) | Occurrences | Real:False | Centroid spread |
|---|---:|---:|---:|
| Dome-top (confirmed pure confusor) | 8 | 0:8 | stayed flat at <= 0.0045 the whole time |
| Popular real feeder perch | 15-16 | 15:1 | 0.0105 by its 3rd occurrence, 0.0524 by its 15th |

A genuinely static artifact re-detects essentially pixel-identical geometry
every time -- only detector/quantization noise separates one occurrence's
box from the next. Real, repeated animal activity at a popular real
location (different individual birds, different poses, different exact
perch positions) measurably spreads more, even while every individual
occurrence still matches the same region under `find_matching_region`'s own
tolerance. `geometry_spread_ceiling` (default 0.008) sits in the middle of a
wide, stable, non-knife-edge zero-real-harm plateau (~0.0045-0.010) an
exhaustive grid search over `min_occurrences_to_suspect` x
`geometry_spread_ceiling` x the matching thresholds themselves found against
this same real cohort -- comfortably above the tightest confirmed confusor,
comfortably below where the popular real perch's own early growth would
otherwise start being wrongly caught. `min_occurrences_to_suspect` (default
3) is the smallest value on that same plateau, deliberately more
conservative than `burst_scheduler`'s analogous `min_recurrence_to_suppress`
(2): that decision only ever costs one extra photo and is reversible on the
very next opportunity; this decision can withhold an entire reviewable Visit
from a human.

### A second replay finding: the absolute strong-detection escape

A **steady-state** stress replay (see "Replay of the previous cohort,"
below) -- the same real cohort's confirmed-real events replayed a second
time, 30 days later, against the durable history the first pass already
built -- found one further narrow case the relative `stronger_confidence`
escape alone did not cover: a real, tiny (two-member), tightly-clustered
pair of sightings at nearly the same micro-location, both with genuinely
strong (>0.78) confidence, could eventually be wrongly suspected after
enough repeated recurrence with zero intervening review, because a repeat
of the *same* real subject can never look "materially stronger than" its
own already-strong prior history -- the relative escape's own reference
point rises with the subject's own past strength. The absolute escape
(step 6, above) closes this: `docs/sustained-visit-continuity-contract.md`'s
own real measurement already established that a static/hardware confusor's
confidence essentially never reaches `strong_detection_threshold` at all
(attempt-2's real red-glass-feeder clutter measured a maximum of 0.417
across its entire session) -- so a candidate that independently clears it is
real, corroborating evidence on its own, regardless of what a region's own
history looks like. After adding it, the identical steady-state replay
shows **zero** real events wrongly blocked.

This finding is disclosed in full because it is a genuine, real limitation
this milestone found and fixed, not a hypothetical: it demonstrates the
value of the required steady-state replay (a purely cold-start replay of a
short, four-day cohort would not have surfaced it) and the value of
requiring *two* independent escape hatches (relative and absolute) rather
than declaring the mechanism safe after the first one that happened to pass
the cohort's own cold-start replay.

## Reviewed-truth interaction

`_update_scene_confusor_region_from_review` (in `product_repository.py`) is
called only from `_create_review_label_in_session`'s own single choke point
-- reached only for an authority-eligible review
(`review_provenance.is_authority_eligible`, see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md)).
An `agent_diagnostic` or omitted-provenance review is durably recorded (as
it always was) but never reaches this hook, so it can never protect or
strengthen a region -- verified directly
(`test_non_authoritative_review_does_not_protect_a_region`).

- **What creates/strengthens confusor suspicion**: recurring geometry alone
  (the primary signal, since most Visits are never reviewed at all -- this
  cohort had exactly one human review out of 70), optionally strengthened
  (never required) by an authority-eligible review whose label is
  `false_positive` (the one product label meaning "no animal was actually
  present" -- distinct from `unknown_bird`/`unknown_animal`/a species name/
  `squirrel`/`cat`, all of which confirm an animal *was* present). A
  strengthened region's `suspected_confusor` reason is disclosed as
  `recurring_geometry_with_reviewed_false_history`, distinguishable from
  the unreviewed `recurring_static_scene_geometry` case.
- **What weakens/resets it**: any authority-eligible review whose label is
  *not* `false_positive` on a Visit whose own geometry matches an existing
  region sets `reviewed_real_count > 0` on that region -- permanent,
  unconditional protection from that point forward (step 2 in "Decision
  order," above), regardless of how much unreviewed recurrence history
  exists or accumulates afterward. A single reviewed Visit never *creates*
  a new region by itself (only an existing, already-recurring region can be
  protected or strengthened) -- a lone reviewed sighting is not itself
  "recurring."
- **How long it persists**: durable, with no expiry of its own (a
  `reviewed_real_count`/`reviewed_false_count` increment is permanent
  bookkeeping); the *region* it lives on can still be aged out by
  `region_ttl_days` (default 45) or explicitly purged by reconfiguration
  invalidation (below) like any other region fact.
- **Whether it is Stream-specific**: yes -- every region is keyed by
  `(stream_id, broad_class)`; a review on one Stream can never protect or
  strengthen a region on a different Stream.

## Invalidation

Camera movement/reconfiguration must not leave stale image-space
suppression (or stale image-space protection) active indefinitely.
`purge_scene_confusor_regions_for_stream` is called from
`apply_camera_configuration` exactly when that method's own existing
`restart_required` computation is `True` -- a resolution, provider, or
camera-selection change (never a cosmetic field like a display name or
notes; see `_CAMERA_CONFIGURATION_NON_RUNTIME_FIELDS`). This reuses an
already-correct, already-tested classification rather than inventing a
second one: `restart_required=True` already means "this Stream's own
captured geometry may no longer mean what it used to." A cosmetic edit
(`restart_required=False`) leaves every durable region untouched
(`test_cosmetic_camera_edit_does_not_purge_regions`).

`region_ttl_days` (default 45) is a second, disclosed, deliberately
conservative backstop: not derived from a representative longitudinal
sample (the only real cohort available when this module was built spans
four days, far too short to responsibly derive a decay constant from) --
long enough that a genuinely persistent confusor is not forgotten between
infrequent real sessions, short enough that undetected drift does not carry
stale suspicion indefinitely even if the explicit hook above is somehow
never triggered (for example, a physical camera bump with no corresponding
Guided Camera Editing save). This is an honest, disclosed limitation, not a
claim of completeness: a silent physical reposition that never goes through
Guided Camera Editing at all is not detectable by this mechanism today --
matching every other "no camera-geometry-change detection" gap this
codebase already has for every other purpose.

## Counterfactual lineage

Extends, not replaces, the existing rejected/suppressed Detection
Attribution ledger (see
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md)):
`blocked_scene_confusor_suspected` is one line added to
`counterfactual_lineage.ADMISSION_REJECTED_OUTCOMES`, so
`classify_rejection_attribution` correctly buckets it as `admission_rejected`
instead of falling through to `insufficient_counterfactual_lineage` for an
outcome the ledger actually has a recorded fact for
(`test_scene_confusor_outcome_is_recognized_by_counterfactual_lineage`). No
new record type was needed: `ProposalOutcomeRecord.reason` is already a
free-form sanitized string (exactly like `"zone_is_privacy_or_ignore"`
elsewhere), so a scene-confusor block's own disclosed reason code
(`recurring_static_scene_geometry` /
`recurring_geometry_with_reviewed_false_history`) already carries the
"which rule influenced the decision" fact this milestone's own requirement
asks for, with no schema change. `engine_runtime.py`'s existing
`_suppressed` per-session diagnostic dict (surfaced through
`ObservationEngineSessionStatus.counts.suppressed_reasons`, already rendered
generically by `web/src/components/ObservationControlPanel.tsx`'s
"Advanced diagnostics" `<details>`) was extended with one more literal
string for the identical reason.

Every suppression is answerable, per the task's own required questions:

- **which rule influenced the decision** -- `outcome.reason`, one of the
  stable, enumerable codes above.
- **scene/confusor identifier, if one exists** -- the matched region's own
  `region_id` (`SceneConfusorDecision.matched_region_id`), a stable,
  content-addressed identity, queryable directly against
  `scene_confusor_regions`.
- **confidence/evidence at decision time** -- the candidate's own
  `confidence_evidence_json` (already retained, Detection Quality
  Accounting v1) plus the matched region's own `occurrence_count`/
  `centroid_spread`/`max_confidence_observed`/`reviewed_real_count`/
  `reviewed_false_count` at that moment (all durable, queryable columns).
- **whether suppression was final or retryable** -- final for this exact
  `proposal_id` (not in `candidate_visit_authority.RETRYABLE_OUTCOMES`,
  matching every other blocked outcome except `blocked_continuation_
  pending`'s own distinct timing reason), but never a permanent verdict on
  the *region*: a later, differently-evidenced proposal at the same
  geometry can still escape via any of steps 2/4/5/6 above, and reviewed
  truth can flip the region's own status at any time.
- **which reviewed history contributed** -- `reviewed_real_count`/
  `reviewed_false_count` on the matched region, directly.

## Performance

Every scene-confusor check is a bounded, indexed, per-candidate-attempt
cost -- never an unbounded historical scan, and never a Review-Queue-style
O(N-history) defect:

- **Read**: one indexed query (`ix_scene_confusor_regions_stream_updated`
  on `(stream_id, updated_at)`), bounded by `LIMIT max_regions_per_stream`
  (default 64, matching `burst_scheduler.max_recurrence_groups`/
  `temporal_capture._MAX_TRACKED_CLUSTERS`), plus the pure, in-Python
  geometry match over that already-bounded result set (at most 64
  comparisons, each O(1)).
- **Write**: one upsert-shaped update (find-or-create-and-touch) per
  admission attempt, inside the same transaction
  `_create_candidate_visit_locked` already opens -- no additional
  transaction, no additional round trip beyond the one read above.
- **Storage**: bounded per `(stream_id, broad_class)` by the same
  `max_regions_per_stream` cap, actively enforced by LRU eviction (the
  least-recently-updated region is deleted before a genuinely new one is
  created past the cap -- mirrors `burst_scheduler.BurstScheduler`'s
  identical `OrderedDict.popitem(last=False)` eviction, durably instead of
  in-memory) -- verified directly
  (`test_region_history_is_bounded_per_stream`, 84 distinct geometries
  attempted, region count never exceeds 64). Stale rows (`region_ttl_days`)
  are also lazily deleted on read, bounded to the already-fetched page.
- **Reviewed-truth hook**: runs only on the already-rare `POST
  /api/review-labels` write path (one query plus, at most, one update), not
  on any per-frame or per-candidate hot path.

No new worker, polling loop, or background job was added -- every operation
above is synchronous, bounded, and driven only by an admission attempt or an
explicit review/reconfiguration action a user or the engine already
performs.

## UI

No new confusor-management UI was added, matching "do not build a large
confusor-management UI; normal users should not need to manage detector
internals." `blocked_scene_confusor_suspected` automatically appears,
alongside every other suppression reason, in the existing collapsed
"Advanced diagnostics" `<details>` on the Observation panel
(`web/src/components/ObservationControlPanel.tsx`, already rendering
`status.counts.suppressed_reasons` generically) -- a bounded,
plain-language-adjacent diagnostic in the advanced/support view, never the
everyday Today experience, satisfying "a bounded 'repeated background
pattern ignored' diagnostic in advanced/support views" without new frontend
code.

## Replay of the previous cohort

Per this milestone's own explicit instruction, the replay must not silently
use the human/agent adjudication label as an inference input -- avoiding
evaluation leakage. The mechanism's own admission decisions above use only
already-legitimate pipeline facts (geometry, confidence, occurrence
recurrence, and reviewed truth exactly as it existed at each historical
moment); the independent visual re-adjudication (see the milestone's own
final report) is used *only* to score the replay's outcomes afterward,
never as a mechanism input.

**Faithful, real, end-to-end replay** (not a hand-rolled simulation): all 70
real historical events (`visit-observation-candidate-019` through `-088`,
their own real persisted `stream_id`/geometry/confidence/timestamps, read
once, read-only, from the real product's own live database) were replayed
in true chronological order through the actual, real
`ProductRepository.create_candidate_visit_from_proposal` -- including the
real `_create_candidate_visit_locked` admission hook and the real
`_create_review_label_in_session` reviewed-truth hook -- against a fresh,
isolated, throwaway SQLite database. The one genuine human `ReviewLabel` in
the cohort (`visit-observation-candidate-037`, `house_finch`,
`review_origin="human"`) was replayed at its own real timestamp through the
real `create_review_label` path. `AuthorityLimits` were widened for this
replay only (session/hourly rate caps are an orthogonal, already-covered
mechanism unrelated to this milestone; a disclosed, deliberate replay-
methodology choice, not a hidden one) so this milestone's own mechanism,
not an unrelated rate limit, is what the replay measures.

**Cold-start result** (the cohort's own real four-day history, built from
nothing):

| | Count | Denominator |
|---|---:|---:|
| False Visits before | 40 | 70 total |
| False Visits after (still admitted) | 35 | 65 admitted |
| False-Visit rate before | 57.1% | -- |
| False-Visit rate after | 53.8% | -- |
| Real Visits retained | 30 | 30 |
| Real Visits incorrectly suppressed | **0** | 30 |
| False Visits correctly suppressed | 5 | 40 (idxs 51, 54, 68, 69, 80 -- entirely the dome-top/feeder-silhouette confusor cluster) |

**Steady-state result** (the same real confusor/real-sighting patterns
recurring a second time, 30 days later, against the durable history the
first pass already built -- the representative measurement for a mechanism
explicitly designed to persist and improve over time against a *genuinely
persistent* confusor, which by definition keeps recurring beyond any one
short cohort's own window):

| | Count | Denominator |
|---|---:|---:|
| False recurrences caught | 14 | 40 (35.0%) |
| Real events wrongly blocked | **0** | 30 |

The ground-truth labels behind both tables are this milestone's own fresh,
independent visual re-adjudication of the same 70 events (the original
`visual_adjudication.csv` artifact was not recoverable this session --
gitignored, session-local; see the milestone's own final report for full
disclosure). This independent re-derivation found 30 real / 40 false
(42.9%/57.1%), close to but not byte-identical to the original 33/37
(47.1%/52.9%) -- both a genuinely fresh, disclosed second pass, and (as a
cross-check) independently re-deriving five of the original report's six
named confusor clusters by pure box-geometry proximity alone, several
matching to two decimal places, without ever reading the original per-event
labels.

**Confusor-cluster-specific results**: of the six recurring clusters this
milestone's own investigation re-identified, the dome-top/feeder-silhouette
cluster (n=8, the single largest, matching the original report's own
"largest confusor... covering the whole session" finding exactly) is the
one this mechanism catches most completely, both cold-start and especially
steady-state. Two structurally uncatchable-by-design clusters exist: the two
`n=2` clusters (roof/chimney shadow, bottom-left grass) can never reach
`min_occurrences_to_suspect=3` within a 70-event cohort at all -- a
disclosed, honest limitation of a conservative, safety-first threshold, not
a defect (see "Why occurrence count alone is not enough," above, for why a
lower threshold was tested and rejected for real-recall-safety reasons). One
of the six original clusters (a "second feeder-adjacent spot... several
high-confidence House Finch suggestions") could not be geometrically
isolated at all in this milestone's own independent re-derivation -- its
approximate region turned out, on this milestone's own fresh visual review,
to contain substantial genuine real-bird activity intermixed with the
originally-reported false positives, which is itself an important, honest
finding: this specific region is exactly the *hardest* case this
milestone's own governing constraints warn about (a popular real perch
sitting close to recurring false detections), not a clean confusor this
mechanism should suppress aggressively.

**No new duplicates or fragmentation**: the mechanism can only ever prevent
a Visit from being created, never create an extra one -- verified directly
(`test_suspected_confusor_creates_no_partial_visit_or_media`: a blocked
proposal leaves zero MediaAsset/Visit/Event trace, exactly like
`blocked_privacy_zone`/`blocked_missing_evidence` already guarantee). The
existing candidate-visit and counterfactual-lineage regression suites (181
tests across `test_candidate_visit_repository.py`,
`test_candidate_visit_authority.py`,
`test_candidate_visit_authority_acceptance.py`,
`test_candidate_visit_adapter.py`, `test_candidate_visit_rollback.py`,
`test_candidate_visit_review_workflow.py`,
`test_counterfactual_lineage.py`, `test_camera_configuration_edit.py`,
`test_review_decision_provenance.py`) all pass unmodified except the two
closed-outcome-vocabulary assertions in
`test_candidate_visit_authority_acceptance.py`, which were extended (not
weakened) to include the new, legitimate outcome code.

## Authority and limitations

`scene_confusor.py` imports no product repository, filesystem path, network
connection, or CUDA/ONNX Runtime/OpenCV runtime, and creates no `Event`,
`Visit`, `MediaAsset`, `ReviewLabel`, or reviewed truth by itself. A
`SceneConfusorDecision` is diagnostic/admission evidence, exactly like
`ConfidenceEvidenceSummary`/`GeometryAttribution` already are: nothing may
treat a `suspected_confusor` outcome as proof an animal was never present,
or a `not_suspected` outcome as proof one was -- a human reviewer's own
judgment, reached only through the exact existing, completely unmodified
`ProductRepository.create_review_label` correction path, remains the only
way to establish or correct durable reviewed truth.

Known limitations disclosed, not hidden:

- **Structurally bounded catch rate on a short cohort**: `n=2` recurring
  clusters can never reach `min_occurrences_to_suspect` within a short
  window; this is a deliberate, safety-motivated conservatism (see "Why
  occurrence count alone is not enough"), not an oversight, and the
  mechanism's own steady-state numbers (above) show its catch rate grows as
  more real history accumulates over time, which is precisely how a
  *persistent* mechanism is supposed to behave against a *persistent*
  confusor.
- **A silent physical camera reposition with no corresponding Guided Camera
  Editing save is not detected** -- bounded only by `region_ttl_days`, a
  disclosed backstop, not a fix (see "Invalidation").
- **The reviewed-truth interaction is only as good as how often Visits are
  actually reviewed** -- this real cohort had exactly one human review out
  of 70; the mechanism's primary, load-bearing signal is therefore
  unreviewed geometric recurrence plus spread, with reviewed truth as a
  strengthening/protective bonus, not a requirement -- by design, since
  requiring review would make the mechanism inert on exactly the kind of
  installation (low review engagement) it most needs to help.
- **`broad_class`-scoped, not fully global, per-Stream bounding**: regions
  are capped per `(stream_id, broad_class)` pair, not strictly per Stream
  alone -- a Stream that saw many distinct animal *and* person *and*
  vehicle confusors could in principle retain more than
  `max_regions_per_stream` rows in total. Disclosed as a real, bounded
  (still capped per class, never unbounded) scope choice, not revisited
  this milestone since every real candidate observed to date is
  `broad_class="animal"`.

## Reviewed-negative-evidence suspicion (Site-Specific Learning & Local Adaptation v1, schema 53)

The limitation disclosed immediately above -- "reviewed truth as a
strengthening/protective bonus, not a requirement" -- named a real gap this
milestone closes, not a permanent design boundary: `reviewed_false_count`
existed on every region since schema 34, but `evaluate_scene_confusor_
suspicion` only ever used it to pick the disclosed `reason` string once
`occurrence_count` had *already* reached suspicion on its own (see "Decision
order," above) -- it never independently drove the `outcome`. Reviewed-
negative evidence -- an authority-eligible human explicitly reviewing this
exact recurring geometry and labeling it `false_positive`, more than once --
is authoritative human truth, categorically stronger per-example than raw
unreviewed pattern recurrence, and this milestone's own governing doctrine
(see the milestone brief) requires that reviewed truth be able to teach the
system faster than silent pattern-matching alone.

**The new gate.** `SceneConfusorConfig.min_reviewed_false_to_suspect`
(default **2** -- see the constant's own docstring for why not lower, and
why not empirically re-derived the way `min_occurrences_to_suspect`/
`geometry_spread_ceiling` were: this repository's own real local database
has zero pre-existing `scene_confusor_regions` rows to grid-search against,
so this default is a disclosed, conservative starting point, not a field-
validated one). Step 3 of "Decision order" becomes an **OR**: a region is
recurrence-eligible once `occurrence_count >= min_occurrences_to_suspect`
**or** `reviewed_false_count >= min_reviewed_false_to_suspect` (when
`reviewed_evidence_enabled`, below). Every later step -- geometry-spread
ceiling, both confidence escapes, and reviewed-real protection (checked
*first*, unconditionally, before either recurrence gate) -- applies exactly
as before, regardless of which path satisfied step 3. Reviewed-negative
evidence only ever grants a *faster path to the same recurrence question*;
it never bypasses a single existing safety check.

**Reset / disable.** Two distinct, independently-actionable operator
controls (see "Operator surface," below), because they answer different
questions:

- **Disable** (`observation_authority_settings.scene_confusor_reviewed_
  evidence_enabled`, per-Stream, default `True`): "stop consulting reviewed
  evidence for suspicion." Restores this Stream's exact pre-milestone
  shipped behavior (occurrence-count recurrence only). Already-accumulated
  `reviewed_real_count`/`reviewed_false_count` bookkeeping is preserved,
  not deleted -- re-enabling resumes immediately from the same history.
  Never touches the pre-existing, already-accepted occurrence-count
  mechanism at all.
- **Reset** (`purge_scene_confusor_regions_for_stream`, already existed for
  reconfiguration invalidation, now also operator-triggerable): "delete
  every accumulated region for this Stream," both the pre-existing
  occurrence history and the new reviewed-evidence counts. The
  Observations/reviews/evidence that produced that history are completely
  untouched -- only this derived, reconstructible local-adaptation state
  resets.

**Reversibility (the second half of this milestone's work).** A real gap
was found and fixed alongside the new gate, in the *already-shipped*
reviewed-truth interaction, not just the new one: `_update_scene_confusor_
region_from_review` only ever incremented a region's counts and had no
corresponding decrement, so revising an already-reviewed Visit's label (a
real `house_finch` correction later revised to `false_positive`, or the
reverse) left the *superseded* label's own contribution stale forever
alongside the new one, and reopening a review (which deliberately returns a
Visit to `needs_review` -- no longer authoritative reviewed truth at all)
never retracted anything either. Both are now fixed:

- `review_labels.scene_confusor_region_id` (nullable, schema 53) records
  exactly which region, if any, one specific `ReviewLabelModel` row actually
  incremented, stamped at write time. Never re-derived by geometry re-match
  at retraction time -- a region's own `representative_box` drifts (running
  mean) as more occurrences touch it, so a later re-match could land on a
  *different* region than the one originally incremented and corrupt its
  bookkeeping instead.
- `_retract_scene_confusor_region_contribution` reverses exactly one
  label's own prior contribution (using its own stamped id, `label`
  polarity, and counters clamped at zero as cheap insurance), called (a)
  from the ordinary review choke point whenever an already-`reviewed` Visit
  is about to be re-labeled -- covering both the explicit "revision" action
  and, defensively, any other path that might re-label an already-reviewed
  Visit -- retracting the old label's contribution before the new label's
  own is applied, and (b) from `reopen_visit_review`, which only ever
  retracts (reopening creates no new reviewed truth to increment).

**Source scope.** Unchanged: regions remain keyed by `stream_id` alone (see
"Mechanism," above) -- a reviewed correction on one Stream can never
increment, protect, or suspect a region on a different Stream. Verified
directly (`test_reviewed_false_evidence_on_one_stream_does_not_leak_to_
another`).

**Operator surface.** Two new small, restrained HTTP endpoints under
`/api/streams/{stream_id}/observation/scene-confusor-learning` (`GET` for
status, `POST` for enable/disable, `POST .../reset`), and one bounded,
on-demand, indexed status aggregate (`ProductRepository._scene_confusor_
reviewed_evidence_summary` -- two `COUNT` queries over an already-capped
region set, never a hot or per-frame path) surfaced in the existing
collapsed "Advanced diagnostics" `<details>` on the Observation panel (`web/
src/components/ObservationControlPanel.tsx`), exactly where scene-confusor
diagnostics already lived. Four possible plain-language states only --
"Not enough reviewed history yet," "Learning from reviewed activity on this
camera," "Local adjustment active," "Local adjustment disabled" -- with a
count of reviewed examples supporting the adaptation as the one advanced
detail. No region ids, geometry, occurrence counts, or other model-internal
vocabulary is ever exposed.

**Counterfactual evaluation.** `scripts/scene_confusor_reviewed_evidence_
counterfactual.py` -- a constructed (not organically replayed; see the
milestone's own closure report for why) baseline-vs-adapted comparison over
six disclosed scenarios, run twice through the real, unmodified admission
pipeline against two independent isolated databases. Result: adapted
differs from baseline in exactly the one case designed to exercise the new
capability (a genuine confusor, two reviewed-false corrections, one
occurrence short of the pre-existing threshold -- correctly suppressed only
in adapted), zero recall-affecting regressions across every other case
(popular real perch, protected reviewed-real bird, insufficient single-
example evidence, and a genuinely new strong detection arriving after the
reviewed-false threshold is met all resolve identically in both).

**Tests.** `tests/test_scene_confusor.py` (pure decision logic: the new
independent gate, its own disable path, downstream escapes still applying,
`reviewed_real` protection still winning, the structural floor of 2) and
`tests/test_scene_confusor_repository.py` (end-to-end: the new gate firing
below the occurrence threshold, revision retracting stale protection,
reopen retracting a contribution, Source isolation, disable/reset,
non-authoritative reviews never feeding the new path, suppression never
writing review truth, and a conflicting-evidence recovery scenario).
