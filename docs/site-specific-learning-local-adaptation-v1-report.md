# Site-Specific Learning & Local Adaptation v1 — Report

Starting HEAD: `059f069` ("Biodiversity & Place Intelligence v1").
Ending HEAD: this report's own commit.
Branch: `main`. **Not pushed.**
Schema: v52 → v53 (two small, purely additive columns; no table dropped, no
column removed, nothing backfilled with a fabricated value).
Working tree at completion: clean except the same seven pre-existing,
unrelated untracked files present at every prior session's start (confirmed
untouched throughout, both at the start and end of this session):
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

This is the first milestone in a new lane: using the system's own reviewed
local history to safely improve future operation at a Place, distinct from
(and building on top of) every prior truth/evidence/identity/intelligence
foundation. It is explicitly **not** model training, fine-tuning, or a
self-reinforcing feedback loop — see "Scope boundaries," below.

## 1. Archaeology — P0 findings

1. **Scene-confusor's reviewed-negative signal was captured but functionally
   inert.** `reviewed_false_count` has existed on `scene_confusor_regions`
   since schema 34 (2026-08-19), but `evaluate_scene_confusor_suspicion`
   only ever read it to pick the disclosed `reason` string once
   `occurrence_count` had *already* independently reached suspicion — it
   never drove the `outcome`. No mechanism anywhere in the codebase
   converted repeated *human-reviewed* false-positive evidence into faster
   or independent suppression. This is the one gap the milestone exists to
   close, and the contract doc's own prior "known limitation" disclosure
   named it directly: "the mechanism's primary, load-bearing signal is
   therefore unreviewed geometric recurrence... with reviewed truth as a
   strengthening/protective bonus, not a requirement."
2. **Confirmed reversibility gap #1 — reopen.** `reopen_visit_review`
   constructs its `ReviewLabelModel` row directly and resets the Visit to
   `needs_review`, but never called `_update_scene_confusor_region_from_
   review`. Any `reviewed_real_count`/`reviewed_false_count` the original
   review had contributed survived indefinitely after the review was
   retracted — a Visit no longer counted as reviewed, but its scene-confusor
   effect never went away. Violated this milestone's own Invariant 4 and
   Phase 8 requirement #4, in code that shipped and was accepted a prior
   milestone ago.
3. **Confirmed reversibility gap #2 — revision.** A Visit reviewed "real
   bird" (setting permanent, unconditional `reviewed_real_count > 0`
   protection) later revised to `false_positive` *did* route through the
   scene-confusor hook for the *new* label (incrementing `reviewed_false_
   count`), but nothing decremented the *stale* `reviewed_real_count` the
   superseded label had produced. Because protection is unconditional and
   checked first, the region stayed permanently protected forever, even
   after a reviewer explicitly retracted the claim that produced that
   protection. Violated Invariant 4 and Phase 8 requirement #3.
4. **Doctrine is unambiguous and directly load-bearing.**
   `docs/product-doctrine.md`: "Human correction remains the truth boundary.
   Model proposals, classifications, **ecological priors**, and
   language-model output must never silently become reviewed truth."
   `CONTRIBUTING.md`: "Only explicit human correction creates reviewed
   truth." Both findings above are precisely the kind of drift this
   doctrine exists to prevent, even in already-shipped, already-accepted
   code.

## 2. Archaeology — P1 substrate reused

- Scene-confusor's non-learning half (min-occurrence gate, geometry-spread
  ceiling, dual confidence escapes, permanent reviewed-real protection,
  45-day TTL, 64/Stream LRU, reconfiguration-triggered purge, counterfactual-
  lineage wiring) is unchanged, untouched, and still exactly as
  field-validated in the 2026-08-19 milestone.
- `reviewed_real_count`/`reviewed_false_count` columns already existed;
  no new counter columns were needed, only a new column recording
  *which specific review* produced *which specific* increment.
- Reviewer attribution was already clean and unforgeable end-to-end:
  `review_status == "reviewed"` can only be produced by
  `review_provenance.is_authority_eligible()`-gated origins;
  `reviewed_by_user_id` is server-set only, never client-supplied.
- `ReviewLabelModel` is append-only with a `supersedes_review_label_id`
  lineage chain; `_review_state_token` gives any consumer a free,
  schema-change-free "did this reviewed record change" signal (not used
  directly by this milestone's chosen mechanism, but confirmed available
  for a future one).
- Per-Stream (`stream_id`) scoping is the established house pattern for
  camera-specific state; a sibling nullable-`source_id`-means-Place-wide
  pattern exists from the immediately preceding Habitat/Environmental
  milestones, confirmed but not needed here.
- Backup/restore is fully schema-driven (whole-file SQLite `.backup()`); a
  new column/table needs zero manual wiring — verified directly (§9).
- Only four explicit `/api/research/*` export endpoints, all gated through
  `research/eligibility.py`, can produce data that leaves the local
  system — confirmed a local-only table needs no privacy-tier changes.
- The Perception Replay Regression Harness's `IsolatedAdmissionRepository`
  drives proposals through the real, unmodified Stage 7 gates (including
  `scene_confusor.evaluate_scene_confusor_suspicion`) against a disposable
  repository — the right precedent for Phase 4, though it has no built-in
  reviewed-truth scoring or state-seeding hook, so Phase 4 used a
  standalone script instead (matching how the original scene-confusor
  milestone's own steady-state replay was also a bespoke one-off, per its
  contract doc).

## 3. Archaeology — P2, explicitly deferred

- **Per-source calibration (Option B)**: no existing calibration mechanism
  at all exists anywhere in the codebase — `BioClipRankedSuggestion.
  calibrated`/`BioClipProvenance.calibrated` are hardcoded `False` at every
  construction site, never set `True` by any code path. Would be built from
  scratch, not extended. This codebase's own vocabulary already claims
  "calibration" for the `identification_eligibility.py` abstention floors —
  a naming collision worth knowing before ever building this.
- **Local species/taxon prior (Option C)**: `historical_baseline.py` /
  `place_activity_report.py` are strong, reviewed-truth-gated,
  minimum-support-thresholded substrate — genuinely reusable raw
  ingredients — but zero code path connects either to
  `bioclip_adapter._rank_suggestions` or `SpeciesCandidatePack` selection
  today. Wiring a prior into suggestion ranking is a materially different
  subsystem (species identification, not admission geometry) requiring new
  integration and a real policy decision (rerank vs. candidate-pack
  filter) — not "the same substrate" as scene-confusor, so not built this
  milestone per the brief's own "one primary mechanism" rule.
- BioCLIP 2.5's full-frame score/margin saturation problem (a confident
  wrong answer numerically indistinguishable from a confident right one) is
  real, documented, and unresolved (`docs/detection-species-model-
  benchmark-promotion-v1-report.md`) — but it is a global model-calibration
  problem, not a local-adaptation seam, and unrelated to this milestone.
- `docs/classifier-training-manifest-design.md`'s offline, manual,
  one-way export-for-external-retraining boundary is real, adjacent, and
  explicitly out of scope (this milestone is not fine-tuning).

## 4. Chosen mechanism

**Option A**, extending the accepted scene-confusor suppression module
(schema 34) with two tightly-coupled halves — both required by the P0
findings above, both the same substrate (`scene_confusor.py` +
`scene_confusor_regions` + the one review choke point), so this remained
*one* primary mechanism, not two:

1. A genuinely reviewed-truth-gated independent suspicion path
   (`min_reviewed_false_to_suspect`, default 2).
2. A fix for the two confirmed reversibility gaps (§1, findings 2–3),
   required regardless of the new gate by this milestone's own doctrine.

Neither Option B nor Option C was the correct seam this milestone (§3);
neither was built.

## 5. Exact reviewed evidence eligible to teach it

Only rows in `review_labels` where:

- `target_type == "visit"` and the target is a Stage 7 candidate Visit
  (has an `ObservationCandidateVisitModel` row) with an `identification`-
  role evidence box (`_visit_identification_box`);
- `review_provenance.is_authority_eligible(review_origin)` is true (origin
  `human`, `imported_curated`, or `legacy_unattributed` — never
  `agent_diagnostic`, never omitted);
- the Visit's own evidence box geometrically matches (IoU ≥ 0.3, centroid
  distance ≤ 0.05, size ratio within 0.35) an **already-existing** recurring
  region for that Stream (a lone reviewed sighting never creates a region
  by itself — only strengthens/protects an already-recurring one);
- `label == "false_positive"` for the new suspicion path specifically (any
  other label continues to feed the pre-existing, unconditional protection
  path unchanged).

Verified structurally impossible for a provisional/unreviewed signal to
qualify: `_update_scene_confusor_region_from_review` is called from exactly
one choke point (`_create_review_label_in_session`), gated on
`is_authoritative`, before either counter is ever touched.
(`test_non_authoritative_review_cannot_feed_the_new_reviewed_false_path`.)

## 6. Minimum support / safety thresholds

| Gate | Value | Notes |
|---|---|---|
| `min_occurrences_to_suspect` | 3 (unchanged) | Real-cohort grid-searched, 2026-08-19. |
| `min_reviewed_false_to_suspect` | **2 (new); candidate, not field-validated** | Structurally floored at 2 in `SceneConfusorConfig.__post_init__` — a config value of 1 or 0 cannot even be constructed. Not empirically re-derived (see §12, remaining gaps) — this repository's real local database has zero pre-existing regions to grid-search against. Precisely because of this, it no longer influences production admission by default — see §20. |
| `geometry_spread_ceiling` | 0.008 (unchanged) | Applies regardless of which recurrence gate fired. |
| Confidence escapes (relative + absolute) | unchanged | Apply regardless of which recurrence gate fired. |
| `reviewed_real_count > 0` protection | unchanged, checked first | Unconditional; wins over any amount of reviewed-false evidence. |

## 7. Source-versus-Place scope

Source-specific throughout, unchanged: `scene_confusor_regions.stream_id`.
Verified directly for the new path specifically (not just inherited from
the pre-existing mechanism):
`test_reviewed_false_evidence_on_one_stream_does_not_leak_to_another`. No
Place-wide state was introduced — nothing about this mechanism justified a
broader scope than the camera-specific pattern it already was.

## 8. Invalidation / recomputation behavior

- **Revision**: the label being superseded (found via `_current_effective_
  review_label_model_for_visit`, captured before the new label is added) has
  its own prior contribution retracted (`_retract_scene_confusor_region_
  contribution`) before the new label's contribution is applied. Net effect
  is always "the region's counts reflect exactly the current effective
  label," never an accretion of every label a Visit has ever carried.
- **Reopen**: the current label's contribution is retracted; nothing is
  incremented afterward (reopening creates no new reviewed truth).
- **Provenance for exact retraction**: a new nullable `review_labels.
  scene_confusor_region_id` column (schema 53) records exactly which region
  one specific label touched, stamped at write time — never re-derived by
  geometry re-match at retraction time, which was considered and rejected
  (a region's own `representative_box` drifts via its running-mean update
  as more occurrences touch it, so a later re-match could land on a
  *different* region and corrupt its bookkeeping instead of the correct
  one's).
- **TTL / LRU / reconfiguration purge**: all three pre-existing invalidation
  paths are unchanged and untouched, and now also correctly bound the new
  reviewed-evidence counters (they live on the same row).
- **Explicit reset**: `purge_scene_confusor_regions_for_stream`, already
  existed for reconfiguration invalidation, now also directly
  operator-triggerable via `POST .../scene-confusor-learning/reset`.
- Proven end-to-end: `test_revision_from_real_to_false_retracts_stale_
  real_protection`, `test_reopen_retracts_reviewed_false_contribution`,
  `test_conflicting_evidence_a_later_reviewed_real_animal_reprotects_the_
  region`.

## 9. Production behavior: conservative by default (corrected 2026-08-24)

**Original milestone text (superseded — kept for the historical record, see
§20):** ~~Production, not shadow-mode — `scene_confusor_reviewed_evidence_
enabled` defaults `True` per-Stream. This was a deliberate decision, not a
default left unexamined: the mechanism's own minimum-evidence abstention
gate already makes it provably a no-op wherever a Stream has not yet earned
it, so "enabled by default" changes zero currently-observed behavior on any
installation until genuine field evidence accumulates through ordinary
future use.~~ An acceptance-correction pass (§20) found this reasoning
addressed only *currently observed* behavior, never the future: the first
time any real Stream's own field use produced two authority-eligible
`false_positive` reviews at the same geometry, a `True` default would have
begun influencing production admission on `min_reviewed_false_to_suspect` —
a threshold this same report discloses in §6/§18 as a **candidate pending
organic field validation, not a field-validated product default** — with no
operator ever having made that decision. Corrected.

**Current behavior: `scene_confusor_reviewed_evidence_enabled` defaults
`False` per-Stream.** The pre-existing, already-field-validated
occurrence-count scene-confusor mechanism (2026-08-19) is completely
unaffected and remains production behavior exactly as before, regardless of
this flag. Reviewed-evidence *state* — `reviewed_real_count`/`reviewed_
false_count` accumulation, `review_labels.scene_confusor_region_id`
provenance, and both reversibility paths (revision, reopen) — is
unconditional and keeps operating exactly as designed regardless of this
flag; only whether the independent reviewed-false recurrence gate (§4-§7)
is allowed to influence *production admission* is gated by it. An operator
may explicitly set it `True` per Stream at any time (`set_scene_confusor_
reviewed_evidence_enabled`) — e.g. to run local field testing deliberately,
with full knowledge of the threshold's own candidate status — and the
identical evidence is always visible to shadow/counterfactual evaluation
(`_scene_confusor_reviewed_evidence_summary`) regardless of the flag, so
nothing about "is this Stream accumulating evidence toward eligibility" is
ever hidden by leaving production adaptation off.

**Disclosed, checked directly against this repository's own real local
database** (`data/mockingbird.sqlite3`, read-only query, no writes):
0 pre-existing `scene_confusor_regions` rows despite 235 real Visits, 58
reviewed, 18 real authority-eligible `false_positive` corrections. The
live admission path that touches regions requires a genuinely live,
sustained Observation Engine session; this database's own history
evidently never accumulated matching-geometry recurrence at any single
spot. **The new mechanism is therefore fully wired, fully tested, and
currently behaviorally inert on this specific real dataset regardless of
this flag's value** — it will only ever begin to differ from pre-milestone
behavior once a Stream's own future field use produces two authority-
eligible `false_positive` reviews at the same recurring geometry *and* an
operator has explicitly opted that Stream in. This is reported as a genuine
finding, not smoothed over.

## 10. Counterfactual evaluation (Phase 4)

`scripts/scene_confusor_reviewed_evidence_counterfactual.py` — six
constructed, individually-disclosed scenarios (ground truth stated in each
scenario's own docstring, written before running anything, avoiding
evaluation leakage), each run twice through the real, unmodified
`ProductRepository.create_candidate_visit_from_proposal` /
`create_review_label` code paths against two independent isolated SQLite
databases (baseline: `reviewed_evidence_enabled=False`; adapted: `=True`).
Constructed, not an organic replay — see §9 for why no organic cohort
currently exists in this repository.

```
Case                                                        Truth        Baseline                          Adapted
A: repeated, reviewed-false confusor (below occ. threshold) confusor     created (abstain)                 blocked_scene_confusor_suspected (correct)
B: repeated, never-reviewed confusor                        confusor     blocked_scene_confusor_suspected  blocked_scene_confusor_suspected (correct)
C: popular real perch, many real birds                      real_animal  created (correct)                 created (correct)
D: real bird, reviewed real once, protected                 real_animal  created (correct)                 created (correct)
E: single reviewed-false example (insufficient)              ambiguous    created (abstain)                 created (abstain)
F: new strong detection after reviewed-false threshold met  real_animal  created (correct)                 created (correct)

Baseline: {'correct': 4, 'incorrect': 0, 'abstain': 2}
Adapted:  {'correct': 5, 'incorrect': 0, 'abstain': 1}
Recall-affecting regressions (adapted incorrect − baseline incorrect): 0
Review-burden reduction (cases moved from abstain to correctly blocked): 1
```

**Measured recall/precision tradeoff: none.** Adapted differs from baseline
in exactly the one case purpose-built to exercise the new capability; every
other case — including the two specifically designed to stress recall
(a popular real perch, and a genuinely new strong detection arriving right
after the reviewed-false threshold is met) — resolves identically in both
arms. Zero cases moved into "incorrect" in either direction.

## 11. Operator-visible controls / status

Three small HTTP endpoints, one new bounded on-demand status aggregate
(two indexed `COUNT` queries over an already-capped, ≤64-row region set —
never a hot or per-frame path), surfaced in the existing collapsed
"Advanced diagnostics" `<details>` on the Observation panel:

- `GET /api/streams/{id}/observation/scene-confusor-learning` — status.
- `POST .../scene-confusor-learning` (`{"enabled": bool}`) — the explicit
  production-activation opt-in/opt-out, scoped to only the new path.
  Defaults `False` per Stream (corrected 2026-08-24, see §20/§9).
- `POST .../scene-confusor-learning/reset` — "Reset local learning",
  deletes all accumulated region history for the Stream (both halves).

Three plain-language status states: "Not enough reviewed history yet,"
"Learning from reviewed activity on this camera," "Local adjustment
active," plus the enable/disable button's own label carrying the operator's
current production setting, plus one advanced-detail count of reviewed
examples supporting the adaptation. Corrected 2026-08-24: the status line
and the enable/disable setting are deliberately independent — collecting/
evaluating reviewed evidence is never described as "disabled" merely
because production adaptation is off (the default); see §20. No region ids,
geometry, occurrence counts, or ML jargon anywhere in the surface — verified
directly by a Playwright test asserting a jargon denylist (`tensor`,
`embedding`, `optimizer`, `gradient`, `epoch`, `region_id`,
`occurrence_count`) never appears, even inside the advanced view.

A real UX defect was found and fixed in self-review before it ever ran:
the panel's existing primary `error` state, when set, replaces this whole
section's body (Start/Stop control and the entire advanced-diagnostics
`<details>` together) with just an error banner. Reusing it for a failed
toggle/reset would have made a failure hide the very buttons a user needs
to retry from. Given its own, separate `learningError` state, rendered
inline next to the two buttons instead — confirmed with a clean `tsc
--noEmit`, a passing production build, and the same Playwright spec
re-run green afterward.

## 12. Privacy behavior

No changes to any privacy/contribution-tier code. The new state
(`scene_confusor_regions` counters, `review_labels.scene_confusor_
region_id`, the per-Stream enabled flag) is written only to local product
tables, never surfaced into `research/eligibility.py`, `research_export.py`,
`camtrap_dp.py`, or `conservation_report.py` — confirmed both by
architecture review and by the fact that no research/export code was
touched this milestone.

## 13. Restart / backup behavior

Fully schema-driven (whole-file SQLite `.backup()`) — no new backup-wiring
code was needed or added. Verified directly, not just inferred:
`test_backup_and_restore_preserve_reviewed_evidence_learning_state` builds
up both a region's reviewed-evidence count and a non-default per-Stream
enabled setting, takes a real backup, mutates state afterward (re-enables
the setting, purges the region), restores, and confirms the restored
database has exactly the pre-mutation state — the backup's own state, not
the live mutation, and not a blend of the two.

## 14. Focused validation (Tier 1 / Tier 2)

All new and directly affected suites, run together, all green:

- `tests/test_scene_confusor.py` — 38 tests (11 new: the independent gate,
  its own disable path, downstream escapes still applying, `reviewed_real`
  protection still winning, the structural floor of 2).
- `tests/test_scene_confusor_repository.py` — 22 tests (11 new: the new
  gate firing below the occurrence threshold, single-example abstention,
  revision retraction, reopen retraction, Source isolation, disable/
  re-enable, reset, non-authoritative-cannot-feed-the-new-path, suppression
  never writes review truth, conflicting-evidence recovery, backup/restore).
- `tests/test_observation_session_api.py` — 18 tests (6 new: HTTP route
  wiring for all three new endpoints, 404s, status defaults, round-trip).
- `tests/test_review_decision_provenance.py`, `test_alerts_inbox.py`,
  `test_local_identity_multi_user.py`, `test_historical_baseline_
  repository.py`, `test_place_biodiversity_summary_repository.py`,
  `test_place_change_summary_repository.py` (all touch `revise_visit_
  review`/`reopen_visit_review`) — unmodified, all still pass.
- `test_doctor.py`, `test_upgrade_path_acceptance.py`, `test_persistence.py`
  (schema-version-aware) — unmodified, all still pass; one real, disclosed
  fix required here (a raw-SQL doctor test needed a `server_default` on the
  new boolean column, not a test change — see the model's own docstring).
- `test_local_backup_recovery.py`, `test_cross_install_backup_restore.py`
  — unmodified, all still pass.
- Frontend: `tsc --noEmit` and `vite build` both clean; focused Playwright
  (`web/e2e/observation-panel.spec.ts`, 3 tests including 1 new) all pass
  against a real running dev server.
- `ruff check` on every touched file: two genuine new findings, both fixed
  (an unused `field` import in the new script; a `main.py` forward-reference
  type hint that should have been a real import) — confirmed via a
  stash/diff comparison that every other reported finding pre-dates this
  session.

## 15. Tier 3: Core gate result

Production behavior changes (§9), so per the governing brief, the full Tier
B "Core" gate (`scripts/verify_core.py`, `pytest -m "not slow"`) was run at
milestone closure.

**First run**: 11 failed, 4560 passed, 2 skipped, 23 deselected, 11 xfailed
(869s). Investigated every failure individually before treating any as
acceptable — the brief's own doctrine that "insufficient evidence" is a
legitimate state does not extend to unexamined test failures:

- **10 were a real, expected, purely mechanical consequence of the schema
  bump** (52 → 53): tests across `test_camera_health.py`,
  `test_camera_node.py`, `test_candidate_visit_repository.py` (×3),
  `test_species_candidate_packs.py`, `test_visit_collections.py`,
  `test_visit_tags.py`, `test_yard_map.py` hardcode `assert
  CURRENT_DATABASE_SCHEMA_VERSION == 52` as a canary pin (one even carries
  its own comment: "this pin intentionally tracks whatever the latest
  schema version is... regardless of how many later schema versions have
  been added since"). Fixed directly — 14 occurrences across 7 files, all
  `52` → `53`, no other change — exactly the same routine maintenance every
  prior schema-bumping milestone in this repository's history needed.
- **1 (`test_transport_worker.py::test_retryable_failure_returns_item_to_
  failed_retryable_and_eventually_succeeds`) is genuine, pre-existing,
  unrelated flakiness** — confirmed by re-running all 11 originally-failing
  tests together in isolation immediately afterward: this one passed
  cleanly, alongside the (by-then-fixed) other 10. Consistent with this
  repository's own previously-disclosed baseline Core-suite flake rate
  (~2/4500 per run, unrelated to any specific change; see [[habitat-
  phenology-foundation-v1-2026-08-24]]). Not fixed — out of scope, and
  reproducing/diagnosing a known, already-disclosed flake is not this
  milestone's job.

**Second run** (after the fix): **4571 passed, 0 failed**, 2 skipped, 23
deselected, 11 xfailed (940s). Clean.

## 16. Seven preserved files

Confirmed untouched at both the start and the end of this session
(`git status --porcelain`, unchanged `??` entries throughout):
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

## 17. Nothing pushed

Confirmed: all work is local-only, `main` ahead of `origin/main` throughout
(consistent with every prior milestone in this repository's history); no
`git push` was run.

## 18. Remaining bounded learning gaps

- **`min_reviewed_false_to_suspect = 2` is disclosed-conservative, not
  field-validated.** Unlike `min_occurrences_to_suspect`/`geometry_spread_
  ceiling` (both grid-searched against a real cohort in 2026-08-19), this
  repository currently has no organic cohort to derive it from (§9). Once
  real field use produces enough reviewed-false-then-later-reviewed-again
  history, re-running an updated version of this milestone's own
  counterfactual script against organic data (rather than constructed
  scenarios) is the natural way to validate or revise this default. **This
  is precisely why it no longer influences production admission by
  default** — see §20's acceptance correction (2026-08-24): a candidate
  threshold pending organic field validation should not silently gate
  production behavior, and now doesn't unless an operator explicitly opts
  a Stream in.
- **`broad_class`-scoped bounding is inherited, not revisited.** The
  pre-existing per-`(stream_id, broad_class)` region cap (not strictly
  per-Stream) is unchanged and was out of this milestone's scope.
- **Local species/taxon prior (Option C) remains a real, substrate-ready,
  unbuilt opportunity** — see §3. Deliberately not built this milestone
  (a materially different subsystem, and the brief's own "one primary
  mechanism" rule).
- **Per-source calibration (Option B) has no existing seam at all** — would
  be new infrastructure from zero, not an extension; deliberately not
  attempted this milestone.
- A silent physical camera reposition with no corresponding Guided Camera
  Editing save remains undetectable by this mechanism (inherited limitation,
  bounded only by `region_ttl_days`; unchanged this milestone).

## 19. Next natural milestone suggestion

Two reasonable, substrate-ready directions, in priority order:

1. **Let this milestone's own mechanism mature with real field data** before
   building anything further in this lane: once a real installation
   accumulates genuine reviewed-false-positive-then-corrected history, redo
   the counterfactual evaluation organically (not constructed) and use it to
   validate or retune `min_reviewed_false_to_suspect`. Low effort, high
   confidence, directly closes the one disclosed gap in §18.
2. **Local species/taxon prior (Option C)**, now that this milestone has
   proven the doctrine (reviewed-truth-only, evidence lineage, Source/Place
   scope, reversibility, abstention, operator surface, privacy boundary) at
   a different, more substrate-ready seam (`historical_baseline.py`/
   `place_activity_report.py` already compute exactly the reviewed-truth-
   gated, minimum-support-thresholded ingredients a prior needs) — the
   larger, more novel piece of work is the integration point into species
   suggestion ranking, which needs its own explicit policy decision (rerank
   vs. candidate-pack filter) this milestone deliberately left to a future
   one rather than deciding under this milestone's own time/scope pressure.

Not started automatically, per the governing brief.

## 20. Acceptance correction (2026-08-24)

**Starting HEAD:** `de84b24` (this report's own original closure commit).
**Ending HEAD:** this correction's own commit. Not pushed, same as every
prior commit in this repository's history.

**What was found.** Everything else about this milestone — architecture,
the reversibility fix, schema v53, reviewed-truth lineage, Source isolation,
counterfactual tooling, operator controls, and validation — was accepted
as-is. One promotion-policy issue remained: the new reviewed-negative
scene-confusor trigger (`min_reviewed_false_to_suspect=2`) was enabled by
default in production despite zero organic `scene_confusor_regions` history
in the real local database, no organic reviewed cohort to validate the
threshold against, only a constructed six-scenario counterfactual
evaluation, and this report's own §18 already disclosing the threshold as
not field-validated. §9's original "Production, not shadow-mode" framing
argued only that enabling it by default changed no *currently observed*
behavior (the abstention gate already made it a no-op on this repository's
own history) — it never addressed that the same `True` default would have
started influencing production admission the first time any real Stream's
own future field use happened to produce two authority-eligible
`false_positive` reviews at the same geometry, with no operator ever having
made that decision.

**What changed.** `scene_confusor_reviewed_evidence_enabled` now defaults
`False` at every construction site (`SceneConfusorConfig`'s own dataclass
default, `ObservationAuthoritySettingsModel`'s ORM/`server_default`,
schema 53's own migration SQL, and the two repository fallback/construction
sites that previously hardcoded `True`). The mechanism itself was not
touched: `evaluate_scene_confusor_suspicion`'s decision order, the
independent reviewed-false recurrence gate, every downstream escape, and
the unconditional `reviewed_real` protection are byte-for-byte unchanged.
Also unchanged: the pre-existing, already-field-validated occurrence-count
scene-confusor mechanism (§2/§6); reviewed-evidence state accumulation
(`reviewed_real_count`/`reviewed_false_count`), provenance
(`review_labels.scene_confusor_region_id`), and both reversibility paths
(revision, reopen) — none of these read the toggle at all, confirmed by
their own function signatures taking no `enabled` parameter; and status/
counterfactual reporting (`_scene_confusor_reviewed_evidence_summary`),
which computes `regions_with_reviewed_evidence`/`regions_eligible_from_
reviewed_evidence` unconditionally of the toggle, exactly as before.

The one operator control this milestone already built
(`set_scene_confusor_reviewed_evidence_enabled` / `POST .../scene-confusor-
learning`) turned out to already cleanly represent exactly the needed
distinction — production-admission influence, and nothing else — so no
redesign of the toggle's own scope was needed, only its default value and
the surrounding documentation/status wording (§9, §11, docs/scene-confusor-
suspicion-contract.md's "Reset / disable" and "Operator surface," a new
"Reviewed-negative-evidence production activation" subsection there, and the
two `api/main.py` endpoint docstrings that also named the old four-state
list).

**UI honesty fix.** `ObservationControlPanel.tsx`'s `learningStatusLabel`
previously checked `!reviewed_evidence_enabled` *first*, so a fresh
Stream's status read "Local adjustment disabled" even with zero reviewed
evidence ever accumulated — indistinguishable from a Stream whose eligible
evidence was being deliberately withheld from production. Reordered to
check evidence-based state first, independent of the toggle: "Not enough
reviewed history yet" (no evidence at all) → "Learning from reviewed
activity on this camera" (evidence accumulating and/or eligible but
production adaptation not currently applying it) → "Local adjustment
active" (eligible *and* the operator has turned production adaptation on).
The three-state design deliberately never uses the word "disabled" to
describe an evidence/evaluation state — only the enable/disable button's
own label communicates the operator's current production setting, keeping
"is evidence being collected/evaluated" and "is production adaptation
active" honestly independent, per this correction's own explicit
requirement.

**Validation.**

- `tests/test_scene_confusor.py`: 40 passed (was 38; +2 new — the
  conservative-default assertion at the pure-decision layer, and a
  dataclass-default regression test — plus 3 existing tests updated to
  explicitly engage the reviewed-evidence path they were built to exercise,
  since the module's own default no longer does).
- `tests/test_scene_confusor_repository.py`: 25 passed (was 22; +3 new —
  default-settings non-suspicion, shadow/counterfactual visibility
  independent of the toggle, and reversibility independent of the toggle's
  default — plus 2 existing tests updated to explicitly opt in where they
  specifically exercise the reviewed-evidence-engaged path, and 2 more
  given a one-line toggle-state assertion for explicitness without changing
  their own logic).
- `tests/test_observation_session_api.py`: 18 passed (unchanged count; the
  brand-new-Stream default-status test renamed and its assertion flipped to
  `False`).
- Directly affected regression suites re-run together, unmodified:
  `test_review_decision_provenance.py`, `test_alerts_inbox.py`,
  `test_local_identity_multi_user.py`, `test_historical_baseline_
  repository.py`, `test_place_biodiversity_summary_repository.py`,
  `test_place_change_summary_repository.py`, `test_doctor.py`,
  `test_upgrade_path_acceptance.py`, `test_persistence.py`,
  `test_local_backup_recovery.py`, `test_cross_install_backup_restore.py`,
  and the seven schema-version-pinned files from the original milestone
  (`test_camera_health.py`, `test_camera_node.py`,
  `test_candidate_visit_repository.py`, `test_species_candidate_packs.py`,
  `test_visit_collections.py`, `test_visit_tags.py`, `test_yard_map.py`):
  **403 passed**. `test_counterfactual_lineage.py`,
  `test_camera_configuration_edit.py`, `test_candidate_visit_authority.py`,
  `test_candidate_visit_authority_acceptance.py`: **72 passed**.
- `scripts/scene_confusor_reviewed_evidence_counterfactual.py` re-run
  end-to-end: identical table to §10 (adapted differs from baseline in
  exactly the one case designed to exercise it; zero recall-affecting
  regressions) — confirms the script's own explicit `enabled=` threading
  for both arms was never dependent on the default, so this correction does
  not disturb it.
- Frontend: `tsc --noEmit` and `vite build` both clean; the affected
  Playwright spec (`web/e2e/observation-panel.spec.ts`, 3 tests, one
  restructured for the new default/label behavior) re-run against a real
  dev server: all 3 pass.
- `ruff check` on every touched Python file: 47 findings, all confirmed
  pre-existing via a `git stash push -u`/`pop` round-trip comparison against
  the unmodified `de84b24` baseline for the identical file set (identical
  count and identical unrelated locations before and after this
  correction's own edits) — zero new findings introduced.
- Tier B Core gate (`scripts/verify_core.py`, `pytest -m "not slow"`): run in
  full despite the narrow surface area, because this correction touches
  schema 53's own migration SQL and the Visit-admission decision path
  directly — both explicitly named in docs/test-suite-validation-tiers-
  contract.md's escalation rules as requiring Core "regardless of how small
  the diff looks." **Result: 4576 passed, 0 failed**, 2 skipped, 23
  deselected, 11 xfailed (860.66s) — clean on the first run, no
  investigation needed. Exactly 5 more passing tests than the original
  milestone's own final Core run (4571), matching this correction's own net
  new test count (+2 in `test_scene_confusor.py`, +3 in `test_scene_
  confusor_repository.py`).

**Schema.** v53, unchanged — no migration added or removed; only the
existing schema-53 migration's own column *default value* changed
(`DEFAULT 1` → `DEFAULT 0`), verified directly against this repository's
own real local database (`data/mockingbird.sqlite3`): its recorded schema
version was still 49 at the time of this correction (migrations 50-53,
including this one, had not yet been applied to it), so there was no
already-migrated row anywhere carrying the stale `True` default to correct
— the new default takes effect cleanly the first time this database is
next opened.

**Preserved files.** The same seven pre-existing untracked files confirmed
untouched throughout (`git status --porcelain`, unchanged `??` entries):
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`.

**Not pushed.** Consistent with every prior milestone in this repository's
history.
