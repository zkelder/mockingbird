# Multi-Subject Visit Assembly & Review v1 — design

Status: design investigation only, read-only against the repository (no
schema/code changes made to produce this document). Answers the design
question `docs/roadmap.md` "Multi-subject Visit correctness" names as an
explicit v0.1 prerequisite. Design authority is
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
(assembly/merge-boundary mechanism) and
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
(admission/persistence), extended here — not superseded, not a parallel
system. Governed throughout by
[product-doctrine.md](product-doctrine.md)'s existing individual-identity
caution ("do not assume one Visit equals one bird," and do not build
persistent biometric identity).

## Problem

Ordinary feeder/property scenes with multiple simultaneous birds must not
become zero Visits, one falsely singular bird, several duplicate Visits for
one encounter, accidental subject merges, one species label applied to every
animal in the frame, or contradictory species labels for duplicated
representations of the same subject. 2026-08-19 field evidence (see
[end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
§5/§7) traced two real fragmentation/loss cases directly to
`visit_episode_assembler.classify_boundary`'s deliberate "structural
incompatibility" rule: one real bird produced three Visits with three
different species labels (`tufted_titmouse`, `american_robin`,
`american_robin`); a separate two-simultaneous-birds encounter (a reddish
bird on the hook, a brown bird at the feeder) produced **zero** Visits.

Scope boundary, explicit and unchanged from the roadmap: required before
v0.1 is reliable *within-encounter* multi-subject tracking/association
sufficient for trustworthy Visit construction and review. Not required:
recognizing the same individual animal tomorrow, biometric identity,
persistent cross-Visit ReID, perfect identity after arbitrarily long
occlusion, or population-estimation research features. When identity
continuity becomes ambiguous mid-encounter, MockingBird must preserve that
ambiguity rather than fabricate continuity — the same principle that
justified the conservative structural-incompatibility boundary in the first
place.

## Headline finding: the grouping container already exists

The natural first reading of the problem — illustrated in early roadmap
discussion as `Visit -> Subject A/B/C` — is not what direct verification
against the schema recommends. A smaller, better-fitting answer is already
sitting in the schema, verified directly rather than assumed:

- `EventModel` (`src/mockingbird/storage/models.py:335-351`) already sits
  **above** `VisitModel` in the documented product relationship chain
  ("Source -> Stream -> Zone -> Activity Session [Event] -> Visit ->
  Evidence -> Detection Proposal -> Interpretation -> Review Decision ->
  Observation -> Export/Analytics" —
  [review-decision-provenance-contract.md](review-decision-provenance-contract.md)).
- `VisitModel.event_id` is a plain foreign key, **not unique** — nothing in
  the schema prevents more than one Visit from sharing one Event.
- `ProductRepository.visits_for_event(event_id) -> list[Visit]`
  (`src/mockingbird/repository/product_repository.py:8746-8748`) already
  exists and is already plural.
- The frontend `EventDetailPage.tsx` **already renders `detail.visits.map(...)`
  as a list of clickable Visit cards** (lines 466-478), already has a "No
  visits are attached to this event" empty state, already shows a "`${N}
  needing species review`" badge (line 354), and already carries copy
  explicitly framing Event as non-truth-bearing context: *"This Event is
  reviewable context. Labels become truth only after Visit correction."*
  (line 24).
- The only reason none of this is exercised today is that
  `_create_candidate_visit_locked`
  (`product_repository.py`, immediately before the `event_id = self._next_id(
  session, EventModel, "event-observation-candidate")` line) **unconditionally
  mints a brand-new, disposable `EventModel` row for every single candidate
  Visit**. There is no existing code path that reuses an Event across sibling
  proposals.

`VisitModel`'s own scalar shape (`subject_label`, `species_guess`,
`confidence`, `reviewed_label` — one value per Visit, confirmed at
`storage/models.py:365-378`) was always, structurally, a per-subject-
appearance record, not an encounter-level record. **The gap is one level up
(Event-level grouping of sibling Visits), not one level down (a new Subject
sub-entity inside Visit.)**

This reframing is why the recommended design is small: it reuses
`EventModel`, `VisitModel`, `ReviewLabel`, every export/analytics path, and
most of the existing UI unchanged, instead of building a parallel
subject/truth system.

## Recommended model

```
Event (encounter)                     <- new: can now legitimately group >1 Visit
  |-- Visit (subject 1: nuthatch)     <- UNCHANGED shape, UNCHANGED review/export path
  |-- Visit (subject 2: finch)        <- sibling, shares the Event, independent review
  |-- Visit (subject 3: finch)        <- sibling, independently confirmable/unknown
```

For the overwhelming common case (one subject), Event:Visit stays 1:1,
exactly as today — zero behavioral change, zero migration, zero new fields
visible for a single-bird encounter.

Answering the Visit-vs-subject framing question directly, against the actual
code rather than by assumption:

- *"Visit remains the encounter-level container"* — not quite: Event
  reclaims that role, which the doctrine's own relationship-chain diagram
  already names it for, whether or not the code currently exploits it. Visit
  becomes "one reviewed subject-appearance within an encounter" —
  indistinguishable from today whenever there is only one subject.
- *"A new subordinate subject/entity concept is required"* — no new
  **table** is required. `VisitModel`'s existing scalar shape already is the
  right grain for one subject's appearance.
- *"Existing track generation can serve as the subject identity"* —
  partially, correctly: `constituent_generation_ids`/`constituent_track_ids`,
  already carried on the assembled proposal and the durable candidate
  ledger, remain the **machine-evidence** identity of one subject's
  appearance. Reused as-is, not re-derived.
- *"A separate durable reviewed subject entity is necessary"* — no: the
  existing, already-reviewable `VisitModel` + `ReviewLabel` pair already is
  that durable reviewed-subject entity. A track is machine evidence; a
  reviewed Visit is semantic truth — reusing the existing truth object,
  rather than adding a parallel `target_type = "subject"` truth path, is
  what keeps this from becoming the "parallel truth path" doctrine warns
  against.

### Why not extend `ReviewLabel.target_type` to `"subject"` directly

Investigated and rejected as the primary mechanism, on direct evidence:

- `ReviewLabelModel.target_type` (`storage/models.py:1061-1093`) has no DB
  constraint today (unlike its sibling `BioClipIdentificationAttemptModel`,
  which has a real `CheckConstraint` plus a target-id cross-validation
  constraint plus an index — the correct template *if* a new target kind is
  ever added this way).
- `target_type`/`target_id` branching on `{"event", "visit"}` occurs at
  roughly 127 sites in `product_repository.py`, 20 in
  `bioclip_evaluation.py`, 10 in `api/main.py`, 10 in `api/schemas.py`
  (across 5 independently-typed `target_type: str` fields with no shared
  enum), 9 in `demo_data.py`, 7 in `storage/models.py`, 49 in
  `ReviewQueuePage.tsx`, 10 in `web/src/api/types.ts` — including every
  "one label/one record per Visit" resolver Bird Log, classifier readiness,
  the training manifest, and Dataset Export depend on
  (`_wildlife_insight_records`, `_effective_review_label_models`,
  `_visit_is_dataset_ready`, `_classifier_training_manifest`).
- A `"subject"` target also has no natural `target_id` to point at without
  first inventing the subject entity this section is trying to avoid
  inventing.

The recommended design touches none of this: every sibling Visit is
reviewed through the completely unmodified `target_type = "visit"` path.

## Backend extension

### 1. Assembly layer — detect concurrent siblings (new, small, pure)

`visit_episode_assembler.classify_boundary` already, deliberately,
classifies two temporally-overlapping confirmed tracklets
`incompatible`/`temporal_overlap` (`visit_episode_assembler.py:472-477`) —
"never even a close call." `assemble_visit_episodes` already buckets by
`(stream_id, broad_class)` and compares each tracklet only against the tail
of still-open episodes in its own bucket — exactly what already lets two
simultaneous/crossing subjects each keep accumulating their own fragments
independently, with zero contamination
(`test_two_simultaneous_animals_remain_separate`,
`test_crossing_animals_do_not_collapse` — both already pass today).

**New, additive field on `AssembledVisitProposal`:**
`concurrent_sibling_proposal_ids: tuple[str, ...]` — proposals this one was
classified `incompatible`/`temporal_overlap` against specifically (not
`broad_class_mismatch`/`zone_mismatch`/`different_stream`, which are
unrelated, not "same encounter, different subject"). Computed at the same
point `ambiguous_adjacent_proposal_ids` already is — same mechanism,
complementary reason filter. No gap-window heuristic is needed: literal
timestamp overlap is definitionally simultaneous.

Threaded through the same places `ambiguous_adjacent_proposal_ids` already
flows: the `ProposalLineage` Protocol (`candidate_visit_authority.py:41-66`),
`CandidateVisitProposalFacts` (`product_repository.py:2077-2131`), and the
durable ledger `ObservationCandidateVisitModel` (new nullable
`concurrent_sibling_proposal_ids_json` column).

### 2. Persistence layer — reuse the sibling's Event (small, surgical)

In `_create_candidate_visit_locked`, immediately before minting a new
`EventModel`: if `proposal.concurrent_sibling_proposal_ids` is non-empty,
look up `ObservationCandidateVisitModel` rows already persisted for any of
those sibling ids (bounded `IN` query on the existing proposal_id-keyed
ledger — no new table) and, if found, reuse that row's `event_id` instead of
minting a new one. Otherwise mint a new Event exactly as today (the
single-subject path is untouched).

This does not touch authority (`evaluate_candidate_authority`), evidence
admission, or scene-confusor suspicion — every existing admission gate runs
unmodified, per-proposal. Grouping only happens *after* independent
admission, never as a reason to admit: a false positive that would be
rejected today is still rejected.

### 3. A distinct, smaller companion gap: non-transitive ambiguous-cluster arbitration

Important scoping distinction: **one real bird producing 2-3 Visits with
inconsistent species labels is evidenced as a different bug from true
concurrent multi-subject handling.** Those fragments are typically not
temporally overlapping, so the mechanism above does not apply to them at
all — they are sequential fragments the existing ambiguous-boundary
arbitration mechanism should already resolve to one winner.
`tracklet-visit-assembly-contract.md`'s own documented chain scope is
explicit: chain scope is local, not transitive — "A-B ambiguous, B-C
ambiguous never implies A-C is compared." A 3-fragment chain (A-B ambiguous,
B-C ambiguous, A-C never compared) is a plausible, concrete root cause for
"3 Visits, 3 different species labels from one bird": two overlapping
pairwise 2-clusters, each independently allowed one winner, can jointly
admit more than one Visit for what only ever finalized into a single
connected chain.

**Recommendation:** re-diagnose against a fresh session's own duplicate-Visit
cases before assuming; if confirmed, fix
`candidate_visit_authority.resolve_ambiguous_boundary_arbitration` to
compute the full transitive connected component across chained
`ambiguous_adjacent_proposal_ids` links before ranking a single winner,
rather than ranking within each locally-listed pairwise set. Contained
entirely within that one function, no schema change. Do not conflate this
with the concurrent-sibling mechanism above in implementation or tests —
they fix different failure shapes.

## Frontend extension

Because the backend change above makes grouping reachable through the
already-plural, already-shipped `EventDetail.visits` shape, most of the "3
subjects detected" review UX is **already implemented** — it is simply never
exercised today because no Event has ever had more than one Visit in
practice. Concretely still needed:

1. **`VisitDetailPage.tsx` sibling-awareness banner (new, small).** A
   reviewer usually reaches a Visit directly (Review Queue, Bird Log), not
   via its Event. Add a small chip/banner — reusing the existing
   `EvidenceBadge`/`StatusPill` primitives and the same "N items in a card"
   idiom already used elsewhere on this exact page (species-suggestion list
   at line 1397, detections list at line 1216, tag chips at line 1269) —
   showing "N other subjects in this encounter" with links to the siblings/
   parent Event when the Event has more than one Visit. This is the one
   genuinely new UI surface.
2. **`EventDetailPage.tsx` copy pass (small).** Existing rendering (visit
   list, per-visit "needs species review" badge, empty state) is reused
   unchanged; only wording shifts from generic "Bird visits" framing to read
   naturally as "3 subjects detected in this encounter," without overclaiming
   individual-animal identity.
3. **Review Queue (optional polish, not required for correctness).**
   Today's flat per-Visit row list already lets each sibling subject be
   triaged independently and asynchronously, which is desirable ("do not
   require perfect subject identification to confirm multiple animals were
   present"). An optional "part of a 3-subject encounter" badge would help
   context but is not required to reach correct truth.

No change is required to `saveCorrection`/`FastReviewPanel`/the correction
form itself, `POST /api/review-labels`/`/revision`/`/reopen`/
`/review-queue/fast/correct`, or any export/manifest/classifier-readiness
code — every one of those already operates correctly per-Visit today.

## Observation / Today / Place Intelligence semantics

- **One reviewed subject = one Observation?** Yes, unchanged: "Observation"
  has no separate implementation object today
  ([glossary.md](glossary.md) "Observation (product object)") — it is a
  reviewed `VisitModel`. One reviewed sibling Visit is one Observation, same
  as any Visit today.
- **Can one Visit create multiple Observations?** No, unchanged. What
  changes is that one Event/encounter can now correctly produce multiple
  Observations (one per sibling Visit) — the actual product goal.
- **Visit-level encounter context retained?** Via the now-correctly-shared
  Event (`started_at`/`ended_at`/`primary_zone_id` spanning the whole
  encounter) — an existing concept, simply reused as intended.
- **Multi-subject counting for Today/Place Intelligence?** Automatic and
  already-correct under existing doctrine:
  `analytics/place_activity_report.py`'s own docstring already states every
  count is a Visit count, never a unique-animal claim — "'6 Northern
  Cardinals' is not something this module may claim." Three correctly-
  created sibling Visits produce three correct Visit-counts with zero
  analytics code changes. Copy caveat worth flagging, not a code defect: a
  single busy encounter can now legitimately raise a "N visits today" figure
  by 2-3 at once where it previously (incorrectly) contributed only 0 or 1 —
  worth a short doctrine/copy note so genuine Gate A recall improvement
  isn't mistaken for a metrics regression.
- **Avoid counting duplicated machine tracks as separate Observations?**
  Unchanged: `create_candidate_visit_from_proposal`'s existing per-
  `proposal_id` idempotency and the ledger's `UniqueConstraint("visit_id")`
  still guarantee one proposal maps to at most one Visit; concurrent-sibling
  grouping never weakens this.
- **Unknown/unidentified subjects?** Same existing `unknown_bird`/
  `unknown_animal` `reviewed_label` vocabulary, applied per sibling Visit.
- **Species corrections attached?** Identical, unmodified `ReviewLabel`
  path, per sibling Visit.
- **Exports/training eligibility?** Identical, unmodified per-Visit
  `_visit_is_dataset_ready`/classifier-manifest path — each sibling Visit is
  independently, correctly export-eligible exactly as any Visit today.

## Migration / backward compatibility

No change to `VisitModel`'s shape at all. Every historical Visit remains
byte-identical and valid with zero backfill — there is no "subject" row to
retroactively invent, because under this design a subject **is** a Visit,
and a legacy single-subject Visit simply always had (and still has) zero
siblings, without needing a synthetic marker to say so. This satisfies
"prefer honest compatibility" and "do not fabricate historical subject
identities" more cleanly than a backfilled default-subject row would.

Schema 36: one additive nullable column on `ObservationCandidateVisitModel`
(`concurrent_sibling_proposal_ids_json`), following the schema-33
(`_migrate_to_observation_geometry_lineage`) pattern exactly — dialect-
guarded `ALTER TABLE`, no backfill, `NULL` means "predates this concept."
No re-key, no destructive step, no new table.

## Design acceptance cases

| Case | Mechanism exercised | Expected outcome under this design |
|---|---|---|
| A — nuthatch + 2 finches simultaneously | Concurrent-sibling detection (3-way), Event reuse | 3 independent proposals -> 3 independently-admitted Visits sharing 1 Event; each independently reviewable/confirmable/unknown; Today counts 3 |
| B — 1 real encounter -> 3 Visits, inconsistent species | Transitive-arbitration fix (not concurrent-sibling — not simultaneous) | **Closed 2026-08-20**: confirmed and fixed by `resolve_ambiguous_boundary_arbitration`'s connected-component closure, not concurrent-sibling grouping — see "Ambiguous-Boundary Transitive Fragmentation Closure v1" in roadmap.md |
| C — 1 real encounter -> 2 Visits | Most likely the same root cause as B; re-diagnose before assuming | Same fix as B, closed 2026-08-20 alongside it |
| D — two birds cross briefly | Concurrent-sibling detection, already proven clean at assembler level (`test_crossing_animals_do_not_collapse`) | 2 Visits, 1 shared Event, no contamination of either subject's evidence |
| E — one leaves while another remains | Concurrent-sibling detection (their overlapping window), independent tail handling per subject | 2 Visits, 1 shared Event, each with its own correct temporal span |
| F — single bird (must not regress) | No siblings found -> unchanged code path | Byte-identical to today's behavior; zero new fields exposed; existing tests must show zero diff |
| G — background false positive (must not fabricate subjects) | Admission gates entirely unmodified; grouping only applies post-admission | Still rejected pre-grouping exactly as today; explicit regression test |

## Rolling pre-trigger buffer — not justified by this investigation

`roadmap.md` already scopes this precisely: the accepted
`frame-driven-onnx-cuda` path is continuous/near-continuous; a rolling
buffer is "a candidate solution if capture timing turns out to be a material
Gate A blocker," not scoped or implemented in this pass. Nothing in this
investigation implicates capture timing for the multi-subject gap
specifically — `burst-scheduler-contract.md`'s "Multi-subject handling"
section already confirms the **live** per-generation `BurstOpportunity` path
independently captures concurrent subjects today (only the offline replay
*reconstruction tool* has a one-opportunity-per-frame limitation, explicitly
scoped to that diagnostic tool alone). The multi-subject gap this design
addresses is entirely downstream, at assembly/persistence/review — not
capture. Do not add a rolling buffer as part of this milestone; revisit only
if a future session's fresh evidence specifically implicates capture timing
for a multi-subject case.

## Implementation phases

1. **DONE (2026-08-19).** **Assembly-layer concurrent-sibling detection**
   (pure, no DB). New field on `AssembledVisitProposal` + computation in
   `assemble_visit_episodes`. RED/GREEN tests extending
   `test_visit_episode_assembler.py` (mirroring its existing purity
   self-check and fixture-catalog conventions). No schema change. See
   "Concurrent-sibling detection" in
   [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
   for the implemented mechanism, and the "Files likely owned" list below
   for the exact diff -- `ProposalLineage`/`candidate_visit_adapter.py`/
   `candidate_visit_authority.py` were deliberately left untouched (Stage 7
   authority needs no change for this phase, and threading the field that
   far buys nothing without a Phase 2 consumer); only
   `visit_episode_assembler.py` and its own tests/fixtures changed. Real
   2026-08-19 field-fixture replay (Perception Replay Regression Harness,
   real MDv5/CUDA) confirmed zero admission/assembly behavior change before
   vs. after. Confirmed as instructed: the design's headline finding (Event
   already sits above Visit, already plural, already rendered) held up
   against current code without needing revision. This phase does not fix
   duplicate-Visit persistence -- that is Phase 2.
2. **DONE (2026-08-20, Multi-Subject Visit Assembly Phase 2).**
   **Persistence-layer Event reuse + schema 36.** Threaded the new field
   through `CandidateVisitProposalFacts` and the durable ledger
   (`ObservationCandidateVisitModel.concurrent_sibling_proposal_ids_json`,
   additive nullable column) — **not** through the pure `ProposalLineage`
   Protocol in `candidate_visit_authority.py`, a deliberate, verified
   refinement of this plan: `evaluate_candidate_authority` has exactly one
   call site (`create_candidate_visit_from_proposal`), never needs sibling
   information for its own decision, and `_create_candidate_visit_locked`
   already receives the concrete `CandidateVisitProposalFacts` dataclass
   directly (never the Protocol type) — so threading the field there would
   have added coupling the actual call graph does not require.
   `_create_candidate_visit_locked` now calls a new, small, side-effect-free
   helper (`_event_id_for_concurrent_siblings`) immediately before minting
   an `EventModel`: a bounded `proposal_id IN (...)` lookup (defensively
   filtered to the same `stream_id`) against the existing ledger's own
   primary key — no new table, no secondary index — reusing the first
   already-persisted sibling's `event_id` when found, otherwise minting a
   new `EventModel` exactly as before. Admission is completely unmodified:
   grouping only ever happens after independent per-proposal admission
   already said "create," never as a reason to admit, and one sibling's
   rejection never blocks, delays, or affects another's. The `"created"`
   outcome's own `reason` string now distinguishes
   `candidate_visit_created` (new Event — the unchanged, ordinary
   single-subject string) from `candidate_visit_created_shared_event`
   (reused Event), giving this the minimum new observability the milestone
   asked for without a new counter/table. `candidate_visit_adapter.py`
   copies the field verbatim from `AssembledVisitProposal`, one line,
   mirroring exactly how `ambiguous_adjacent_proposal_ids` already crosses
   this boundary — `admission_replay.py` (the Perception Replay Regression
   Harness's own admission layer) calls the same unmodified
   `adapter.attempt_candidate`, so it inherits this fix with zero changes of
   its own. `VisitDetail` gained one additive field,
   `sibling_visits: list[Visit]` (every other Visit sharing this Visit's
   Event, empty for the ordinary case), populated in `get_visit_detail` from
   the already-existing `visits_for_event` — no new repository method.
   Tests extended `test_candidate_visit_repository.py` (nine new tests:
   schema migration, two/three-way sibling grouping order-independence, an
   unpersisted-sibling no-op, one-rejected/one-admitted independence,
   zero evidence cross-contamination, ledger lineage retention,
   cross-Stream defense in depth) and `test_candidate_visit_adapter.py`
   (four new tests driving the real, unmodified assembler — including the
   named nuthatch-plus-two-finches encounter shape — through the real
   adapter and repository to real persisted `VisitModel` rows, closing the
   confirmed gap this design doc's own Phase 2 entry named). Core gate:
   3310 passed. Frontend: `tsc --noEmit && vite build` clean.
3. **Frontend sibling-awareness (folded into Phase 2 above, 2026-08-20).**
   `VisitDetailPage.tsx` gained a small, conditional "N other subjects
   detected in this same encounter" banner (rendered only when
   `sibling_visits` is non-empty — invisible for every ordinary
   single-subject Visit) reusing existing `EvidenceBadge`/`notice-panel`/
   `detail-actions`/`secondary-action` primitives and this same page's own
   `onOpenVisit` navigation convention (already used for `resulting_visits`)
   — no new CSS, no new component. `EventDetailPage.tsx`'s copy pass (the
   "3 subjects detected" wording polish) was deliberately **not** done in
   this milestone — the page's existing `detail.visits.map(...)` rendering
   and empty state already function correctly for a multi-Visit Event with
   zero code change (verified directly against current source), so the
   copy pass is pure presentation polish, explicitly out of scope for a
   correctness-focused milestone ("A later UX polish can improve
   presentation").
4. **DONE (2026-08-20, Ambiguous-Boundary Transitive Fragmentation Closure
   v1).** Re-diagnosed directly against the real, unmodified assembler and
   arbitration code -- confirmed deterministically, no live field session
   needed, since the defect is reproducible from the algorithm alone.
   `resolve_ambiguous_boundary_arbitration` now resolves the full bounded
   connected component across chained `ambiguous_adjacent_proposal_ids`
   links (an iterative, never-recursive traversal) before ranking a single
   winner, closing the "A and C each independently beat shared neighbor B"
   defect described in section 3 above -- contained entirely within that
   one function, no schema change, tested in isolation from phases 1-3
   (nine new tests plus one updated -- the pre-existing test that had
   encoded the defect as intended behavior -- in
   `tests/test_candidate_visit_authority.py`, including a real-assembler
   mixed-graph test proving no cross-contamination with concurrent-sibling
   grouping). Full directly-affected suite (314 tests) and a full Core gate
   (3323 passed) both green. See "Chain scope" in
   [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
   for the complete mechanism.
5. **Optional polish** — Review Queue sibling badge, Today/Place
   Intelligence copy note about legitimate multi-Visit encounters.

Each phase is independently RED/GREEN-testable and independently shippable;
phase 1 alone is safe to land on its own (pure, additive, no persisted-
behavior change until phase 2 consumes the new field).

## Files likely owned by this implementation milestone

- `src/mockingbird/observation/visit_episode_assembler.py` (phase 1)
- `src/mockingbird/observation/candidate_visit_authority.py` (phase 1
  Protocol field; phase 4 arbitration fix)
- `src/mockingbird/observation/candidate_visit_adapter.py` (phase 1/2 field
  threading)
- `src/mockingbird/repository/product_repository.py`
  (`CandidateVisitProposalFacts`, `_create_candidate_visit_locked`,
  `ObservationCandidateVisitModel` — phase 2)
- `src/mockingbird/storage/database.py` (schema 36 migration — phase 2)
- `tests/test_visit_episode_assembler.py`,
  `tests/fixtures/observation_stage619/tracklet_scenarios.json` (phase 1)
- `tests/test_candidate_visit_repository.py`,
  `tests/test_candidate_visit_adapter.py` (phase 2)
- `tests/test_candidate_visit_authority.py` (phase 4, confirmed 2026-08-20)
- `web/src/pages/VisitDetailPage.tsx` (phase 3 — new sibling banner)
- `web/src/pages/EventDetailPage.tsx` (phase 3 — copy pass only)
- `docs/tracklet-visit-assembly-contract.md`,
  `docs/candidate-visit-authority-contract.md` (doc updates alongside the
  code they govern)

Explicitly not touched: `VisitModel`'s own columns,
`ReviewLabelModel.target_type`, any export/classifier-manifest/dataset-
readiness code, `place_activity_report.py`, Bird Log/Wildlife Journal
resolvers, Review Queue correction endpoints, BioCLIP/species-suggestion
code, Camera Node/capture-layer code.

## Next implementation command

Phases 1-4 are DONE (2026-08-19/20 — see "Implementation phases" above).
Remaining, independently schedulable, and correctness-neutral:

- **Phase 5 — optional polish.** `EventDetailPage.tsx`'s copy pass ("3
  subjects detected" wording); a Review Queue sibling badge; a Today/Place
  Intelligence copy note about legitimate multi-Visit encounters. None of
  these change correctness — see "Frontend sibling-awareness" above for why
  the copy pass specifically was deferred rather than folded into Phase 2.

Live/hardware field validation was not a prerequisite for Phases 1-4 --
Phase 2's own deterministic/integration coverage (real, unmodified
assembler through to real persisted rows) and Phase 4's own deterministic
reproduction against the real assembler and arbitration code already
establish the behavior this design question asked; a future live session
remains valuable as later milestone-level acceptance evidence, not as a
blocker for Phase 5.
