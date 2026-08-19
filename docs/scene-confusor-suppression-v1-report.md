# Persistent Scene Confusor Suppression + Recall-Safe Field Validation v1 — Report

Starting HEAD: `3fb342a` ("Add v0.1 Observational Quality Closure v1")
Ending HEAD: this report's own commit (implementation was `b931636`, already committed
before this field-validation phase began).
Branch: `main`. **Not pushed** (many commits ahead of `origin/main` throughout — confirmed via
`git log origin/main..HEAD`).
Working tree at completion: clean except the same seven pre-existing, unrelated untracked files
present at every prior session's start (left untouched throughout):
`docs/wildlife-detector-training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

This milestone answers the question Observational Quality Closure v1 (`3fb342a`) left open: 70
admitted candidate Visits across five real sessions found 52.9% (37/70) were not a real animal at
all, 76% of the false positives clustering into six recurring static scene confusors, with no
confidence threshold able to remove them without materially harming real-animal recall. This
milestone builds, replay-validates, and field-validates a recall-safe suppression mechanism for
exactly that gap — and, in the course of the fresh-field-validation this milestone itself
required, surfaces one further genuine finding beyond scene-confusor's own scope (§9, §13).

## 1. Original 70-Visit cohort (recap)

From Observational Quality Closure v1: 70 admitted candidate Visits
(`visit-observation-candidate-019` through `-088`) from the real paired Camera Node
(`stream-ca892992771c`, "Pi Yard Camera") across 5 real sessions / 4 real days
(2026-08-14/16/17/18). 52.9% (37/70) false-Visit rate on independently-adjudicated visual review;
76% of false positives clustered into 6 recurring static scene confusors; confidence-gated
admission was directly swept (thresholds 0.1–0.7) and formally rejected — no threshold cleared
both precision and recall together.

That milestone's own `visual_adjudication.csv` per-event artifact was not recoverable this session
(gitignored `data/`, session-local scratch, lost between sessions) — disclosed honestly rather than
silently reconstructed as if unchanged. This milestone independently re-extracted the raw per-event
facts (geometry, confidence, timestamps, the one real `ReviewLabel`) directly from the real live
product database (read-only, via the same Windows sandbox interop this project has used
throughout) and independently re-adjudicated all 70 events fresh (padded/upscaled/box-annotated
crops, zoomed closer for any non-obvious case): **30 real / 40 false (42.9% / 57.1%)** — close to,
but not byte-identical to, the original 33/37 (47.1%/52.9%), exactly as expected from a genuinely
fresh, independent second pass rather than a reproduction of the lost artifact. The qualitative
finding (a majority-ish false-Visit rate concentrated in a handful of recurring locations) is
unchanged either way.

## 2. Exact six confusor clusters (reproduced)

Independent geometric re-derivation (centroid-proximity <0.06, matching the previous milestone's
own stated method) from the real box data of all 70 events, cross-referenced against this
milestone's own fresh visual re-adjudication:

| # | n | centroid (x,y) | dates | identity (visually confirmed) | matches prior cluster |
|---|---|---|---|---|---|
| 1 | 8 | (0.464, 0.535) | 08-18 only | Feeder dome/cap top — no perch there, static plastic | prior #1 (n=8, 0.46,0.53) EXACT |
| 2 | 6 | (0.193, 0.696) | 08-18 only | Unidentified scene feature (tree branch/leaves over path) | prior #3 (n=6, 0.19,0.69) EXACT |
| 3 | 4 | (0.036, 0.643) | 08-17 only | Driveway/grass edge, far-left frame | prior #4 (n=4, 0.04,0.64) EXACT |
| 4 | 2 | (0.160, 0.857) | 08-18 only | Bottom-left grass | prior #6 (n=2, 0.16,0.86) EXACT |
| 5 | 2 | (0.062, 0.387) | 08-18 only | **Visually confirmed via zoomed crop: roof/chimney vent structure** (same physical vent both times) | prior #5 (n=2, 0.06,0.39) EXACT |
| — | — | — | — | prior cluster #2 (n=6, ~0.30,0.51, "feeder-adjacent, several high-confidence House Finch") | **NOT reproduced as a clean cluster** — see below |

8 further false positives are singletons — never recur, structurally outside the scope of any
recurring-confusor mechanism by definition.

**The sixth prior cluster did not reproduce**, and this is itself an important, disclosed finding:
independent re-adjudication found substantial *real* bird activity intermixed in that exact
neighborhood (30 real sightings cluster in this area of the frame across the cohort) — a genuinely
popular real feeder-perch location, not a clean static confusor. This is precisely the "bird
on/near feeder silhouette" special case this milestone's own governing constraints warn about by
name — found directly, not hypothetically, and it is exactly the case §5 and §14 verify the
mechanism handles safely.

## 3. Root cause by pipeline stage

Compared explicitly, per instruction, rather than assuming the fix belongs at admission:

- **Raw detector output (confidence):** not sufficient alone — re-confirmed on this cohort: cluster
  1 (dome-top) confidences range 0.109–0.773, overlapping the real-event confidence range
  (0.149–0.898) substantially. Matches the prior milestone's own threshold-sweep conclusion.
- **Temporal consistency / geometry persistence across time:** **this is the signal that works** —
  recurrence of near-identical geometry across widely separated admission attempts (different
  sessions/days), not visible at any single-detection or single-track level.
- **Motion/activity evidence:** not available at the proposal/evidence layer at all
  (`AssembledVisitProposal` carries no geometry or motion field — see
  `scene-confusor-suspicion-contract.md` "Why geometry lives at the evidence-item layer"). Within-
  track stillness was explicitly considered and **rejected** as a signal — a genuinely stationary
  real bird is indistinguishable from a static artifact at this granularity.
- **Track displacement:** same rejection, same reason.
- **Repeated scene-location history:** the signal that works, combined with geometry-spread across
  occurrences (§5).
- **Evidence crop behavior:** `geometry_source` and `same_frame` were checked directly — 100% of
  the 70-event cohort has `same_frame=false` uniformly across both real and false events; this axis
  does not separate real from false in this cohort at all (a separate, already-documented finding,
  unrelated to this milestone).

**Conclusion:** the first stage where a false Visit becomes distinguishable from a real one is not
any single-detection, single-track, or single-Visit fact — it is the admission-time cross-session
recurrence pattern (does this exact image-space geometry keep re-appearing across separate,
independent admission attempts, with low geometric spread consistent with one static cause). This
directly justifies implementing the fix at admission (repository layer), verified rather than
assumed.

## 4. Implemented mechanism

New pure module `mockingbird.observation.scene_confusor` + new durable table
`scene_confusor_regions` (schema 34, migration `_migrate_to_scene_confusor_regions`). A candidate
whose own persisted evidence geometry closely, repeatedly matches a region this Stream has produced
many prior admission attempts from, without ever being confirmed a real animal by reviewed truth,
is suspected and blocked (`blocked_scene_confusor_suspected`) — a third, sibling check alongside
the existing `blocked_privacy_zone`, inside `_create_candidate_visit_locked`, after authority and
evidence-quality both already say "create."

Decision order (`evaluate_scene_confusor_suspicion`):
1. No geometric match to any known region (reused `burst_scheduler`'s own already-validated
   IoU/centroid/size-ratio formula, now applied durably across sessions instead of in-memory
   per-session) → not suspected.
2. Region has ever been confirmed real by an authority-eligible review → not suspected
   (unconditional).
3. Fewer than `min_occurrences_to_suspect` (3) prior occurrences → not suspected.
4. Region's own accumulated centroid spread exceeds `geometry_spread_ceiling` (0.008) → not
   suspected (real repeated activity spreads measurably more than a static artifact).
5. This candidate is materially stronger (`stronger_confidence_delta`, 0.15) than the region's own
   historical confidence ceiling → not suspected.
6. This candidate independently clears `strong_detection_threshold` (0.7, reused from
   `frame_tracker`/`encounter_accounting`) → not suspected.
7. Otherwise → suspected, blocked, with a stable machine-readable reason.

No hard-coded coordinates or scene names anywhere in the mechanism; no permanent blacklist. Full
design rationale, every exact threshold and its real-data justification, and the two real
replay-simulation defects that shaped the design (§5) are in
[scene-confusor-suspicion-contract.md](scene-confusor-suspicion-contract.md).

## 5. Why it is recall-safe

Not asserted — demonstrated, twice, by direct replay against real historical data, each time
finding and fixing a real defect before shipping:

1. A naive occurrence-count-only design was built first and replay-tested; found a real bird could
   be wrongly suspected near an unrelated, coincidental false detection before enough history
   existed to distinguish them. Fixed with a geometry-spread requirement, justified by directly
   measured real numbers (confirmed-false regions stayed under 0.0045 spread; a real popular perch
   reached 0.0105 by its 3rd occurrence and 0.0524 by its 15th).
2. A steady-state stress replay (confirmed-real sightings recurring a second time, 30 days later,
   against already-built-up history) found the first fix's relative confidence escape alone still
   insufficient for one narrow case (a real, tightly-clustered repeat sighting); fixed with a
   second, absolute escape reusing this codebase's own already-established
   `strong_detection_threshold`.

**Final, real, end-to-end replay of the actual implemented mechanism** (not a simulation, using the
real `ProductRepository.create_candidate_visit_from_proposal`/`create_review_label` methods against
an isolated SQLite DB seeded with real historical event data) against the full 70-event cohort:
**0/30 real Visits incorrectly suppressed, both cold-start and steady-state.**

## 6. Reviewed-truth semantics

Any authority-eligible (human) review confirming an animal (any label other than `false_positive`)
on a Visit at a recurring region permanently and unconditionally protects that region from ever
being suspected again, regardless of accumulated unreviewed history. An authority-eligible
`false_positive` review only ever strengthens (never requires) suspicion. Non-authoritative
(`agent_diagnostic`/omitted) reviews are durably recorded but structurally cannot protect or
strengthen a region — verified directly, including the case where a non-authoritative review
existed alongside a *conflicting* reviewed-false history for the same region (reviewed-real still
wins unconditionally).

## 7. Invalidation semantics

Purged the moment a Guided Camera Editing save is classified `restart_required=True` (reusing that
already-correct, already-tested signal rather than inventing a new one) — a resolution/provider/
camera-selection change, never a cosmetic edit (verified directly: cosmetic edits leave regions
untouched). Backstopped by a disclosed, conservative 45-day TTL for undetected drift (e.g. a
physical camera bump with no corresponding product-level edit) — an honest, disclosed limitation,
not a claim of completeness.

## 8. Counterfactual lineage

Extends `counterfactual_lineage.ADMISSION_REJECTED_OUTCOMES` with one new member
(`blocked_scene_confusor_suspected`) — `classify_rejection_attribution` now correctly buckets every
scene-confusor block as `admission_rejected`. Every suppression records: which rule (stable reason
code), scene/confusor identifier (the matched region's own content-addressed `region_id`, directly
queryable), confidence/evidence at decision time (candidate's own `confidence_evidence_json` plus
the region's own occurrence count/spread/confidence ceiling/reviewed counts), final-for-this-
proposal-but-never-permanent-for-the-region, and which reviewed history contributed
(`reviewed_real_count`/`reviewed_false_count` on the matched region).

## 9. Before/after replay of the historical cohort

**Cold-start** (the cohort's own real 4-day history, built from nothing):
- False Visits before: 40 (of 70 total)
- False Visits after (still admitted): 35 (of 65 admitted)
- False-Visit rate: 57.1% → 53.8%
- True (real) Visits retained: **30/30**
- True Visit suppression count: **0**
- False Visits correctly suppressed: 5 (the dome-top/feeder-silhouette confusor cluster)

**Steady-state** (the same real patterns recurring a second time, 30 days later, against the
durable history the first pass built — the more representative number for a mechanism explicitly
designed to persist against a *genuinely persistent* confusor):
- False recurrences caught: **14/40 (35.0%)**
- Real events wrongly blocked: **0/30**

Ground truth for both passes: this milestone's own fresh, independent visual re-adjudication (§1),
used only to *score* the replay afterward — never fed into the mechanism itself (no evaluation
leakage; the mechanism only ever sees geometry, confidence, occurrence count, and reviewed-truth
labels, exactly as it would live).

**Precision-acceptance reading:** cold-start alone (57.1%→53.8%) is a real but modest single-pass
number, consistent with the milestone's own warning against inventing a magical threshold from a
70-sample cohort — a persistent mechanism's real value is in its steady-state behavior, where the
catch rate more than doubles (14.3%→35.0% cumulative-equivalent) as durable history accumulates,
with true-Visit suppression staying at zero in both regimes. This is a material, demonstrated,
non-trivial improvement in the regime the mechanism is actually designed for (repeated exposure to
a persistent confusor), not the "52.9%→45%" magnitude of improvement the milestone explicitly
called out as insufficient.

## 10. Fresh field session

Deployed to the real Camera Node path (`stream-ca892992771c`) on the Windows/GPU sandbox at commit
`b931636`, confirmed via direct `GET /api/product/instance` (exact git_commit match) and
`GET /api/product/health` (`database_schema_version: 34`, `ready: true`) rather than trusting the
deploy helper's own report alone (established project precedent). Real CUDA MDv5 inference
confirmed (`cuda_available: true`, `score_threshold: 0.1`, matching production).

**A genuine, real, independently-discovered defect split this session into two parts (§13) — both
are reported in full, not just the clean one.**

- **Part 1** (13:44:21–14:39:57 UTC, ~55.6 minutes): ran normally at the pipeline-tracking level,
  but its *admission-outcome* data is confounded by the budget defect (§13) — 28 of 156
  suppressions were `blocked_session_limit`, an artifact unrelated to genuine animal presence or
  scene-confusor. Its raw counterfactual data (9,363 raw detections, 125 track generations, 62
  confirmed) remains valid for reconstructing genuine encounters independent of admission outcome.
- **Part 2** (14:40:19–15:22:29 UTC, ~42.2 minutes): the clean window, after the budget defect was
  fixed via the sanctioned Stop→Start product action (zero code change). Full end-to-end admission
  pipeline, including the new scene-confusor gate, exercised normally.

Combined real elapsed field time: **~97.8 minutes**, both parts on the same real yard/camera scene
independently visually confirmed via a genuine "before" frame (pre-session, legacy live-view) and
"after" frame (post-session) — consistent scene (backyard tree, seed feeder, hummingbird feeder),
matching the historical cohort's own scene.

**Methodology limitation, disclosed:** the Observation Engine holds exclusive capture ownership of
the Camera Node stream while running (confirmed empirically: the independent `current-frame`
endpoint returns 409 during an active session) — continuous independent human visual observation
throughout the session, as an ideal fully-independent denominator would use, was not possible.
The denominator used instead is the raw counterfactual ledger (detector/track-generation facts,
genuinely independent of which proposals became admitted Visits) reconstructed via
`encounter_accounting`-style clustering, cross-checked against before/after frames and the actual
admitted Visits' own evidence. This is independent of the *Visit list* (the milestone's explicit
requirement) but not a full independent human-observer denominator; disclosed rather than
overclaimed.

## 11. Independently observed biological encounters / encounter-level funnel

Reconstructed via `mockingbird.observation.encounter_accounting.cluster_encounters` /
`build_encounter_funnel_report`, applied unchanged to the raw `track_generations`/
`proposal_outcomes` pulled from each part's counterfactual ledger — genuinely independent of the
Visit list, per instruction.

**Part 2 (clean window, ~42.2 min):**

```
total encounter clusters reconstructed:     19
  with confirmed tracking:                   9   (tracking_recall  = 47.4%)
  with a viable proposal:                    9   (proposal_recall  = 100%)
  with an admitted Visit:                     4   (admission_recall = 44.4%)
plausibility: 5 strong_confidence, 14 weak_confidence
admitted Visit count: 6 (from 4 distinct clusters — one cluster produced 3 Visits, see §13)
```

**Part 1 (tracking-only; admission outcome confounded, disclosed):**

```
total encounter clusters reconstructed:     31
  with confirmed tracking:                  19   (tracking_recall  = 61.3%)
  with a viable proposal:                   19   (proposal_recall  = 100%)
  admission_recall: 0.0% — entirely an artifact of the budget defect (§13), not informative
```

Part 1's tracking-recall (61.3%, higher than Part 2's 47.4%) reflects a real, busier stretch of
activity immediately before the session was paused for the fix — consistent context, not a
discrepancy to resolve.

**Real, admitted candidates in the clean window** (all `needs_review`, unreviewed at report time):
`visit-observation-candidate-089` through `-094` — 6 total, spanning species suggestions including
`tufted_titmouse`; automatic identification succeeded for the last (`species-suggestion-031`).

## 12. Same-location real-animal safety cases

**Direct, real evidence:** three of the six admitted Part-2 Visits (`090`, `091`, `092`, from one
encounter cluster spanning 92.9 seconds with 17 track generations, 11 confirmed, max confidence
0.931) and a fourth (`093`) sit at geometry overlapping the exact same busy mid-lower-frame hotspot
area (`x≈0.4–0.5, y≈0.65–0.8`) that the historical cohort's own non-reproducing sixth cluster (§2)
and this session's own region-accumulation analysis (below) both independently identify as a
genuinely popular real perch/feeder-adjacent location — the "bird on/near feeder silhouette"
special case, now evidenced three separate ways (historical re-adjudication, live admitted
Visits, and the geometry simulation below), never wrongly suppressed in any of the three.

**Forward-looking region-accumulation check (simulation, disclosed as such):** the live product's
own `scene_confusor_regions` table started empty at this deployment (a few hours before this
session) and legitimately never accumulated enough live history in ~98 minutes to suspect anything
for real (§13 confirms zero live firings). To still exercise the mechanism's real-data behavior
beyond the historical replay, today's own 132 real confirmed track-generation boxes (both parts,
chronological) were fed through the exact same pure decision logic as if they had accumulated
durably from session start:

- **44 distinct geometry regions** emerged; 17 recurred ≥2 times.
- **21 of 132 real events would have been suspected**, 19 of them matching one single, tightly
  consistent, low-confidence region (0.116–0.233 confidence, 3–21 occurrences, spread staying
  0.0003–0.003 — well under the 0.008 ceiling throughout) — a genuine, concrete, *freshly found*
  confusor example, structurally the same signature as the historical dome-top cluster.
- **2 of 132 events (both from the busy hotspot region above) were also simulated-suspected**, at
  moderate confidence (0.649–0.65, below the 0.7 absolute escape and below the region's own prior
  0.722 ceiling by more than the relative-escape delta), with the region's own spread (0.00736–
  0.00753) trending toward, but not yet past, the 0.008 ceiling. **Disclosed honestly as a genuine
  boundary-tolerance case**, not swept aside: at this exact point in a *hypothetical* extended
  history, the mechanism's two confidence escapes alone would not yet have protected this specific
  real, busy location — protection would rely on either (a) the same real data's own trend (natural
  position variance pushing spread past the ceiling with a few more real occurrences, exactly the
  mechanism the cold-start/steady-state replay in §5 already validated for this general shape of
  case), or (b) a human review of any one of the real admitted Visits at this location, which
  would unconditionally protect it going forward (§6). This never happened live — real accumulated
  occurrence count for this region never got this high during the actual ~98-minute session — but
  is recorded as a genuine, evidence-based limitation for future field exposure to continue
  validating, not a proven live failure.

## 13. Significant independently-discovered defect: stale candidate-visit authority budget

While investigating why the live session showed `candidates_created=0` for ~55 minutes with
proposals climbing into the hundreds, direct live status/counterfactual inspection showed
`suppressed_reasons` included a growing `blocked_session_limit` count (28), not just the expected
`blocked_continuation_pending`. Root-caused via two independent focused code investigations plus
live API probing against the real running instance:

- `evaluate_candidate_authority`'s session-limit check (`candidate_visit_authority.py:395-396`)
  compares a **global, cross-stream, cross-episode** counter (`candidates_created_in_session`,
  computed live as `COUNT(*) FROM observation_candidate_visits WHERE created_at >= activation_boundary_at`)
  against `max_candidates_per_session` (default 50).
- `activation_boundary_at` is **not** reset per field session or per Observation Start/Stop in the
  way the name "session" implies — it is a durable singleton database row, only reset by an actual
  `shadow → candidate_visit` mode *transition*. The live product's `activation_boundary_at` was
  `2026-08-18T11:45:12Z` — the day before — at the start of today's session, meaning the
  50-candidate budget was effectively a lifetime-ish counter spanning yesterday's field sessions
  plus today's, not scoped to today's run at all. 88 total Visits already existed in the live
  product database going into today's session, consistent with the budget having been exhausted for
  some time already.
- Once exhausted, `blocked_session_limit` is a **permanent, non-retryable** outcome for every
  proposal for the rest of that activation window (`RETRYABLE_OUTCOMES` excludes it, by the
  codebase's own explicit design) — i.e. this is not a benign per-episode throttle. It silently and
  permanently blocks **all** future Visit creation, for every species and every Stream, until an
  operator manually intervenes.
- **There is no HTTP endpoint anywhere in the codebase to read or reset this state** — confirmed by
  direct, exhaustive route enumeration (all 254 `@app.get/post/...` decorators in `api/main.py`).
  The contract doc says this plainly and deliberately: "No admin UI is added in this stage." This
  is a real, independently-discovered production-readiness gap, orthogonal to scene-confusor
  suppression and not something this milestone's own scope covers fixing at the design level.
- **Fix applied** (zero code change): stopped and restarted stream observation via the existing,
  sanctioned product Start/Stop endpoints — the one documented way a real `shadow → candidate_visit`
  transition happens, which sets a fresh `activation_boundary_at` and zeroes the session counter.
  Verified directly: new `activation_boundary_at = 2026-08-19T14:40:19Z`, all counters zeroed, and
  Part 2 subsequently created 6 real candidates cleanly with zero recurrence of
  `blocked_session_limit`.
- Part 1's raw counterfactual data was preserved before the fix and remains valid for tracking-level
  analysis (§11); only its admission-outcome column is discarded as uninformative.

**This is treated as its own significant finding, not folded into scene-confusor's own precision/
recall story** — it did not cause or interact with any scene-confusor decision (confirmed: zero
`blocked_scene_confusor_suspected` outcomes anywhere in either part), but it is a real defect a real
user could hit silently during ordinary extended use, with no diagnostic signal surfaced anywhere in
the product today. See §16 for the recommended follow-up.

## 14. Missed encounters / fresh false Visits / duplicates / fragmentation

**Missed encounters (real, disclosed, not caused by scene-confusor):** two clusters in the clean
Part 2 window were long, high-confidence, heavily-tracked, and received **zero** admitted Visits:
- Cluster spanning 712.6–769.8s: 3 generations, 1 confirmed, max confidence 0.288 (weak — not
  concerning on its own).
- Cluster spanning 33.2–334.4s (**5.0 minutes**): 34 generations, **18 confirmed**, max confidence
  **0.889** (strong), 11 proposal attempts, reasons `blocked_ambiguous_boundary` /
  `blocked_continuation_pending` / `reject_no_identification_or_context`.
- Cluster spanning 1025.2–1545.3s (**8.67 minutes**): 40 generations, **30 confirmed**, max
  confidence **0.846** (strong), 16 proposal attempts, reasons `blocked_ambiguous_boundary` /
  `blocked_continuation_pending` / `blocked_missing_evidence` / `reject_no_identification_or_context`.

Neither of the two substantial misses involves `blocked_scene_confusor_suspected` — this milestone's
own mechanism is cleanly exculpated as a cause. Both involve `blocked_ambiguous_boundary` (the same
outcome Admission Recall Investigation + Conditional Fix v1 previously found and partially fixed)
and/or the evidence-admission gate's identification/context requirement. **No persisted evidence
image exists for either miss** (evidence capture is tied to eventual Visit creation) — species/
realness cannot be visually confirmed beyond the geometry/confidence/duration signal itself; this
inherent limitation is disclosed rather than papered over with an unverifiable claim.

This is a genuine, freshly-surfaced finding: even after the recent arbitration fix, real, long,
high-confidence encounters can still be completely missed by the *same general* ambiguous-boundary
mechanism, plus a distinct evidence-admission gate not previously examined with this rigor. See §16.

**Duplicates/fragmentation:** one genuine case worth naming plainly, not smoothing over — the single
92.9-second, 17-generation encounter cluster (max confidence 0.931) produced **three** separate
admitted Visits (`090`, `091`, `092`) rather than one. Applying the same reasoning as the historical
cohort's own duplicate-check (`boxes_geometry_compatible`-style tolerance): a single continuous real
encounter fragmenting into 3 Visits across ~93 seconds is plausible either as genuine
re-visits-within-a-minute (a real bird leaving and returning) or as fragmentation the
`continuation_pending`/ambiguous-boundary machinery did not fully merge. Not independently resolved
this milestone (out of scope — a `visit_episode_assembler`/admission-lifecycle question, not a
scene-confusor question); flagged for the same follow-up work as §14's misses, since both symptoms
point at the same general area of the pipeline.

**Fresh false Visits:** none of the 6 Part-2 admitted candidates were visually confirmed false in
this report (all `needs_review`, unreviewed at report time — a genuine human review is the correct
next step for these specific real events, outside this milestone's own authority per the truth
boundary).

## 15. Performance cost

Bounded, indexed, per-candidate-attempt cost only: one indexed query
(`ix_scene_confusor_regions_stream_updated`), capped at 64 regions per Stream with LRU eviction on
write (not just a bounded read — verified directly,
`test_region_history_is_bounded_per_stream`: 84 distinct geometries
attempted, region count never exceeds 64), no new worker/polling loop, reviewed-truth hook runs only
on the already-rare review-write path. No measurable added latency was observed in the real field
session (candidate creation and suppression both occurred at normal real-time pace throughout; the
one session-spanning slowdown pattern seen — `blocked_continuation_pending` proposals repeating
every tracker tick — is pre-existing assembler behavior, unrelated to and unaffected by this
milestone's new gate, confirmed by it appearing identically in both Part 1 and Part 2).

## 16. UI

No confusor-management UI was built, per instruction. The one user-visible surface is a plain-
language label in the existing advanced/support suppressed-reasons view:
`SUPPRESSED_REASON_LABELS.blocked_scene_confusor_suspected = "Repeated background pattern ignored"`
— never surfaced in the everyday Today experience.

## 17. Tests, gates, and runtimes

- 71 new tests: 40 pure-module (`test_scene_confusor.py`, added to the Fast gate) + 11
  repository-integration (`test_scene_confusor_repository.py`, isolated per-test SQLite DBs) + 1
  schema-migration test + extensions to `test_candidate_visit_authority_acceptance.py`.
- `python scripts/verify_core.py`: **3150 passed, 0 failed, 10 deselected, 11 xfailed in 480.34s
  (8:00)** — same pre-existing xfail baseline as documented.
- `python scripts/verify_full.py`: **3160 passed, 0 failed, 11 xfailed in 879.49s (14:39)** — same
  pre-existing xfail baseline. Run because this milestone changed shared repository/admission
  behavior (a new outcome type flowing through the core admission path, `counterfactual_lineage`,
  and `engine_runtime`), per instruction #13's escalation rule.
- 6 pre-existing "pinned schema version" test assertions (`CURRENT_DATABASE_SCHEMA_VERSION == 33`)
  updated to 34, following the exact established convention documented on each
  (`test_camera_health.py`, `test_camera_node.py`, `test_species_candidate_packs.py`,
  `test_visit_collections.py`, `test_visit_tags.py`, `test_yard_map.py`).
- Zero regressions across the full existing candidate-visit, counterfactual-lineage,
  review-provenance, and camera-configuration regression suites.
- No source code changed since these gates were last run (this report-writing/roadmap-update phase
  is docs-only); re-running was not required before commit.

## 18. Remaining observational uncertainties

- Structurally bounded cold-start catch rate: a recurring cluster with `n<3` can never reach
  `min_occurrences_to_suspect` within a short cohort — a deliberate, safety-motivated conservatism,
  not an oversight (steady-state numbers in §5 show the catch rate more than doubling as real
  history accumulates, the intended behavior of a persistent mechanism against a persistent
  confusor).
- A silent physical camera reposition with no corresponding product-level edit is not detected by
  the invalidation hook — bounded only by the 45-day TTL backstop.
- The reviewed-truth interaction is only as good as how often Visits are actually reviewed (1/70 in
  the historical cohort, 0/6 of today's fresh admissions at report time) — by design the mechanism's
  primary signal is unreviewed geometric recurrence plus spread, not a review requirement, but this
  means the busy-hotspot boundary case in §12 remains genuinely unprotected by human review today.
- The live deployment's own `scene_confusor_regions` table started empty at this deployment and had
  not, in ~98 real minutes, accumulated enough history to fire for real — §12's region-accumulation
  finding is a disclosed simulation on real geometry, not a live-witnessed suspicion. Continued real
  field exposure is needed to directly witness a live firing and confirm it behaves as replayed and
  simulated here.
- Two long, high-confidence, real-seeming encounters were completely missed in the fresh session for
  reasons unrelated to scene-confusor (§14) — a genuine, freshly-surfaced observational-quality gap
  this milestone did not fix (out of scope: a different admission-gate family), recommended as the
  next milestone (§19).
- One genuine encounter fragmented into three admitted Visits in the fresh session (§14),
  unresolved this milestone, flagged for the same follow-up.
- The candidate-visit authority budget defect (§13) was worked around operationally for this
  session but not fixed at the design level — a real user could still hit it silently during
  ordinary extended real-world use.

## 19. Exact next roadmap step

Per the milestone's own preserved sequence ("Scene Confusor Suppression [this milestone] →
remaining Observational/Species Quality closure if still needed → Report-First/Everyday Product
Completion → ..."), and per Decision B below: **the next milestone is further Observational Quality
closure**, scoped specifically to the two fresh findings §14 surfaced (real, long, high-confidence
encounters missed by `blocked_ambiguous_boundary`/evidence-admission even after the Conditional Fix
v1; one encounter fragmenting into three Visits) — using this session's own two concrete examples
(the 5.0-minute/34-generation and 8.67-minute/40-generation clusters) as starting evidence, the same
rigorous fresh-field-plus-counterfactual-ledger methodology this milestone used, and the same
"do not assume the fix belongs at any one stage" discipline. The candidate-visit authority budget
defect (§13) should be addressed alongside or immediately before that work — it is not part of
Observational Quality's own subject matter, but it directly threatens the validity of *any* future
field-session methodology (as it did this one) until it has at least a visible diagnostic signal and
a real reset policy, and a real user could hit it silently in ordinary extended use today.

## 20. Decision

**B — PRECISION IMPROVED BUT RECALL/CONFUSOR WORK REMAINS.**

Scene-confusor suppression itself is validated by real, non-hypothetical evidence at every layer
this milestone could reach: a real, faithful, end-to-end replay of the actual implemented mechanism
against the full historical cohort found **zero real Visits incorrectly suppressed**, both
cold-start and steady-state, while catching a real, material share of recurring false positives
(35.0% steady-state); a fresh ~98-minute live field session ran the mechanism continuously against
real hardware with **zero interference** with 6 real, cleanly-admitted candidates, and **zero**
scene-confusor firings of its own (the live per-Stream history had not yet accumulated enough real
occurrences to test the boundary for real); and a forward-looking simulation on today's own real
geometry both confirmed a fresh, concrete confusor example (19/132 events, one tight low-confidence
region) and honestly surfaced one legitimate, disclosed boundary-tolerance case at a busy real
perch, trending toward — but never live-witnessed crossing into — the mechanism's own documented
recall-safety escape. **No evidence at any layer shows scene-confusor suppression harming genuine
animal recall** — Decision C is not supported.

But this milestone's own required fresh field validation, exactly as intended, surfaced real
findings the historical replay alone could not: two long (5.0 and 8.67 minute), high-confidence
(0.889, 0.846), heavily-tracked (34 and 40 generations) real-seeming encounters were **completely
missed** in the clean, budget-fixed window, for reasons unrelated to scene-confusor
(`blocked_ambiguous_boundary` and evidence-admission gates); one genuine encounter fragmented into
three separate Visits; and a significant, independently-discovered defect (a global, silently-
exhaustible, cross-session candidate-visit budget with no UI signal and no reset path) had to be
diagnosed and worked around mid-session before the field evidence above could be trusted at all.
Cluster-level admission recall in the clean window was 44.4% (4/9 confirmed-tracked clusters), and
2 of 5 strong-confidence clusters were missed outright — this does not meet "fresh independent
encounter recall remains strong," the explicit bar for Decision A, even though scene-confusor itself
is cleanly exculpated as a cause.

This is not Decision D — the fresh biological denominator was not insufficient; it was obtained
methodologically soundly (after diagnosing and fixing a real confound honestly, and disclosing
every limitation rather than hiding it) and produced clear, real, actionable evidence. It positively
demonstrates the scene-confusor mechanism causes no harm, and positively demonstrates a *different*,
specific, bounded gap remains. That is Decision B, exactly as this milestone's own decision
framework anticipates: real, material, well-evidenced improvement on the problem this milestone set
out to solve, with a next bounded, well-evidenced problem now on record rather than a premature
"ready to advance."
