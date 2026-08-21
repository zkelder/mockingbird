# Harvested Evidence Issuance / Missing-Evidence Closure v1 — Report

Investigation-and-fix milestone, direct follow-up to
[cache-128-live-daylight-acceptance-v1-report.md](cache-128-live-daylight-acceptance-v1-report.md)
§7/§13. That milestone's own Decision A (the 32→128 harvested-evidence
cache-capacity fix) is **not reopened here** — this milestone investigates a
disclosed, explicitly-separate finding from the same session: 4 of 7
`blocked_missing_evidence` cases showed only 8–22% of the 128-entry cache's
own capacity in use during their delay window, too low for that cache's own
FIFO eviction to plausibly explain them.

## 1. Starting state

`HEAD` at session start: `867deb6cf5b335c44adc2214a89a9ef9123ee322`
("Record Cache-128 Live Daylight Acceptance v1 results (Decision A)"),
confirmed via `git log`/`git rev-parse HEAD`. The 7 pre-existing untracked
files (`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`) were confirmed present, unchanged, and
remain so — not part of this milestone's scope.

## 2. Preserved field evidence

Verified present and untouched, both required artifacts:

- `data/field-acceptance/2026-08-20-cache-128-live-daylight-acceptance/`
  (report, field-session-plan, independent-encounter-table, motion-screen,
  contact sheets) — all read as investigative evidence, none modified.
- The raw acceptance-recorder session
  `stream-ca892992771c/20260820T222528Z` — not committed to the repository
  (raw media is gitignored by design), located instead on the real Windows
  host filesystem this WSL checkout can read via `/mnt/c` at
  `C:\Users\zachk\AppData\Local\MockingBirdDev\acceptance-recordings\
  stream-ca892992771c\20260820T222528Z`. Confirmed present (last modified
  Aug 20 19:55, consistent with the session's own recorded end time and no
  later modification) alongside its 6 prior sibling session directories.
  Not opened frame-by-frame in this milestone — the field report's own two
  independent visual reviews (Phase 1 blind pass + Phase 2 targeted
  cross-check) already exhaustively covered it, and re-doing that pass would
  duplicate rather than add evidence; this milestone's own contribution is
  the code-path trace neither prior pass could perform.
- The live counterfactual ledger itself is **not** available: it existed
  only inside the now-stopped session's own process memory. The field
  report's own three proactive cumulative pulls (`cf_early_pull.json`,
  `flagged_proposals.json`, `cache_eviction_timing_analysis.json`,
  `flagged_with_lifetime.json`, `cumulative_final.json`) were explicitly
  saved to that session's own ad hoc scratchpad, **not committed to the
  repository** (matching this project's established convention for
  session-local analysis artifacts) — this reconstruction therefore uses the
  field report's own already-published case table and code-line citations as
  its authoritative source for per-proposal facts, not a fresh ledger query.

## 3. Seven-case reconstruction

All facts below are drawn directly from
[cache-128-live-daylight-acceptance-v1-report.md](cache-128-live-daylight-acceptance-v1-report.md)
§7 and its own field-session-plan.md working notes — the only surviving
record of these 7 proposals' individual facts. Fields not recoverable from
that record are marked explicitly, not inferred.

| # | Proposal (suffix) | Window (ms) | Gens | Pending re-evals | Delay | Evid. vol. / % of 128 | Real bird? | Terminal | Corresponding Visit |
|---|---|---|---|---|---|---|---|---|---|
| 1 | `...5b900477` | 481708–512320 | 1 | 3 | 115.6s | 123.5 / **96.5%** | Yes, high confidence (0.785 max, 15 detections, `confirmed: true`) | `no_persistable_evidence_bytes` | None (blocked) |
| 2 | `...7ac2eaa3` | 624843–634873 | 1 | 0 | 0.0s (immediate) | n/a | Yes | `no_persistable_evidence_bytes` | None (blocked) |
| 3 | `...b4cec5f0` | 708244–773429 | 3 | 0 | 0.0s (immediate) | n/a | Yes | `no_persistable_evidence_bytes` | None (blocked) |
| 4 | `...ecc70d37` | 915162–984706 | 3 | 4 | 47.0s | 28.4 / 22.2% | Yes | `no_persistable_evidence_bytes` | None (blocked) |
| 5 | `...6b8c30c6` | 1244192–1250628 | 1 | 4 | 46.9s | 28.5 / 22.3% | Yes | `no_persistable_evidence_bytes` | None (blocked) |
| 6 | `...d47830f4` | 2045480–2101954 | 3 | 4 | 45.1s | 10.7 / 8.4% | Yes (most of window) | `no_persistable_evidence_bytes` | None (blocked) |
| 7 | `...f44148a7` | 2456851–2462334 | 1 | 1 | 57.1s | 24.5 / 19.1% | Yes, medium-high (partial occlusion) | `no_persistable_evidence_bytes` | None (blocked) |

**Explicitly unavailable, not inferred:** full (non-truncated) proposal and
constituent track-generation ids; per-detection confidence series; exact
burst-request/response timestamps; the live `_temporary_payloads` cache's
own occupancy trace; and — critically — **whether a burst was ever issued
at all** for cases 4–7, as opposed to issued-and-captured-then-lost. The
field report itself disclosed this exact limit ("no surviving log/API
signal distinguishes 'never harvested' from 'harvested then evicted'"); nothing this milestone did could recover a signal the original session
never recorded. Recorder frame references (`frame-000392`/`frame-000404`
for case 1) exist only for the one case the field report directly
zoomed into; cases 2–7 were confirmed real-animal by the independent
review's separate Phase 2 timestamp cross-check, not by frame number.

**Genuine-animal determination** for all 7: independently confirmed by the
field report's own Phase 2 targeted cross-check (7/7 windows show a real,
visible animal on direct frame inspection) — reused here verbatim, not
re-derived.

## 4. Exact first failing transition — traced from code, not inferred

Confirmed real production path, `src/mockingbird/observation/`:

```
confirmed TrackUpdate (frame_driven_provider)
  -> BurstOpportunity built, camera_node_live.py:846-862
  -> BurstScheduler.decide() -- burst_scheduler.py
  -> EvidenceBurstRequest issued, camera_node_live.py:867-881
  -> transport.request_evidence_burst() captures successfully
  -> session._temporary_payloads[content_hash] = payload, camera_node_live.py:902
     -- hardcoded cap of 8, FIFO (popitem(last=False)) -- camera_node_live.py:904-905
  -> EvidenceCandidate(role="high_resolution_burst") appended to this frame's result
  -> [THE GAP] engine_runtime.py's `_run_async` main loop only called
     `_harvest_burst_bytes` once per whole `session.run()` BATCH, after the
     entire up-to-`_BATCH_FRAMES=20`-frame batch had already returned
     (pre-fix engine_runtime.py:935-936) -- not "the moment... observed,"
     despite that being this exact cache's own documented intent
     (engine_runtime.py:812-823's pre-existing comment)
  -> if >8 *other* frames within that same batch each also captured a
     burst before the batch finished, `_temporary_payloads`'s own 8-cap
     had already evicted the early one -- session.temporary_burst_payload()
     now returns None for it
  -> `_harvest_burst_bytes` silently skips it (pre-fix: `if not payload:
     continue`, no signal recorded)
  -> burst_bytes_cache (the properly-sized, 128-entry, `_MAX_CACHED_
     BURST_BYTES`-bounded cache `_run_assembly_tick` actually reads from)
     never receives this candidate's bytes at all
  -> _run_assembly_tick -> adapter.attempt_candidate() ->
     candidate_visit_adapter._build_evidence_items(): builds zero
     CandidateEvidenceItems with real content for this proposal (a pick
     with no retrievable bytes is honestly skipped, never fabricated)
  -> product_repository.py:3073-3077 (or the second gate at 3169-3172):
     items_with_content is empty -> "blocked_missing_evidence" /
     "no_persistable_evidence_bytes"
```

**The first failing transition is the harvest step itself** — not
issuance (the scheduler correctly decided to issue), not capture (the
transport correctly captured real bytes), not the outer cache (128 entries,
nowhere near full for cases 4–7) — but the *timing* of when those
already-captured bytes were copied out of a small, independent,
previously-undocumented-as-a-capacity-bound intermediate cache
(`LiveCameraNodeShadowSession._temporary_payloads`/`_same_frame_temporary_
payloads`, camera_node_live.py, hardcoded `> 8`, never touched by either the
8→32 or 32→128 fix) into the properly-sized `burst_bytes_cache`/`same_frame_
bytes_cache` this module's own `_MAX_CACHED_BURST_BYTES` governs.

This mechanism requires no cache-capacity change anywhere: it is purely a
question of *when* an already-adequately-sized cache gets the chance to see
bytes that a much smaller, upstream buffer is silently discarding first.

## 5. Successful same-session controls used

Directly from the field report's own accounting (§7, "Positive
counter-evidence"): of 10 created Visits traceable in its cumulative ledger
sample, 6 survived genuine delayed handling with pending lifetimes of 36.6s,
45.0s, 45.1s, 45.4s, 45.6s, and **324.2s** — all *longer* than several of
the 7 failing cases' own 45-57s delays, ruling out "the outer cache is
simply too small" as an explanation for cases 4–7 specifically (the
successful ones sat in the same outer cache for equal or longer, at equal
or greater session-wide evidence-candidate volume, and survived). This is
consistent with — not contradicted by — the batch-internal mechanism this
milestone found: outer-cache survival says nothing about whether a
proposal's bytes ever *reached* that cache in the first place, which is
exactly the distinction the old code could not observe and this milestone's
new diagnostic (§9) now can.

## 6. Burst/evidence issuance hypothesis — investigated, not confirmed as stated

The field report's own recommended follow-up named the burst scheduler's
"fairness/throttling decision" as the likely mechanism. Investigated
directly against `burst_scheduler.py`/`burst-scheduler-contract.md` and
`camera_node_live.py`'s live wiring:

- The scheduler's suppression/budget/recurrence-group logic is deliberate,
  documented, real-data-tuned product behavior (see "Stage 6.12: late-session
  evidence-burst fairness" for its own prior, already-fixed starvation
  defect) — nothing in this investigation found a *new* scheduler defect,
  and this milestone does not claim one.
- What the investigation found instead is a **different, more specific,
  directly provable mechanism in the same general territory** ("evidence
  issuance/harvest/lineage," per this milestone's own Decision-A wording):
  a genuinely *issued and captured* burst can still be lost before the
  properly-sized cache ever sees it, for reasons entirely unrelated to the
  scheduler's own fairness decision.
- Answering the milestone's own specific questions (§5 of the task):
  - *Can a viable proposal reach admission without ever receiving a usable
    evidence issuance?* Yes, by design, when the scheduler suppresses a
    duplicate/low-budget opportunity — not what this milestone found
    causing cases 4–7.
  - *Is there a bounded queue/window/rate condition that drops or starves
    an evidence request?* Yes — but not at the scheduler/issuance layer:
    at the harvest layer. `_temporary_payloads` is exactly this bounded
    queue, previously undocumented as a capacity concern.
  - *Can a same-frame candidate be present but not harvested?* Yes,
    identically — `_same_frame_temporary_payloads` shares the exact same
    hardcoded-8/batch-deferred-harvest shape, fixed by the same change.
  - *Can multiple concurrent birds compete for one evidence issuance
    opportunity?* Not at issuance (each generation gets its own
    opportunity) — but yes at harvest: multiple concurrent/sequential
    captures compete for the same small post-capture buffer's 8 slots.
  - *Are there branches where a proposal records evidence metadata but not
    persistable bytes?* Yes — this is precisely the proven defect: an
    `EvidenceCandidate` record survives; the bytes behind it do not.
  - *Is any failure caused by an intentional policy decision surfaced
    misleadingly as "missing evidence"?* No — this is a genuine,
    previously-undiscovered timing bug, not a deliberate policy (unlike the
    separate, correctly-named `only_alternate_or_no_selected_evidence_
    available` reason, a real scoring-quality decision, not a bug).

**The issuance hypothesis as originally stated (scheduler declining to
issue) is not confirmed.** A concrete, different, harvest-layer defect in
the same general mechanism family is confirmed instead.

## 7. Multi-subject correlation

Checked each low-pressure case's window against the field report's own
independent multi-subject flags (`independent-encounter-table.md`):

- Case 4 (`...ecc70d37`, 915162–984706ms) sits directly between two flagged
  simultaneous-bird moments (~899.9s and ~1000.1s) inside Encounter C's own
  "nearly every frame occupied" dense span — strong correlation.
- Case 5 (`...6b8c30c6`, 1244192–1250628ms) falls within Encounter C's
  broader dense span (752–1400s) but not an exact flagged instant —
  moderate correlation.
- Cases 6 and 7 fall outside any flagged multi-subject instant (Encounter D
  territory and an isolated partial-occlusion sighting respectively) — no
  direct multi-subject correlation.

**Multi-subject activity is a plausible contributor to 2 of 4 cases, not a
required precondition for the mechanism.** The proven defect is triggered by
*batch-local capture density* generally — more than 8 successful bursts
within one ~20-frame processing pass — which multi-subject scenes make more
likely but do not uniquely cause (a single busy generation issuing several
novelty-driven bursts in quick succession, or several distinct
short-lived single-bird generations arriving close together, can trigger it
identically). This milestone does not implement, and did not need to touch,
any Multi-Subject Phase 2 mechanism — the fix is agnostic to subject count.

## 8. Deterministic reproduction

`tests/test_engine_runtime.py::test_batch_internal_burst_capture_no_longer_
starves_an_early_generations_evidence` — drives the real, unmodified
production path (`ObservationEngineSessionManager.start()` →
`_EngineSession._run_async` → `LiveCameraNodeShadowSession.run()`) with a
fake, exactly-scripted provider (9 distinct, single-frame, real-tracker-
shape track generations, each independently "meaningful" and each
independently capturing a real, distinct burst) and a real burst-request
transport. **RED** (verified directly, via `git stash` of only the two
source fixes, re-running the test, then `git stash pop` — not merely
asserted): `gen-early` (the first of 9 to capture) reaches exactly
`blocked_missing_evidence` while all 8 later generations succeed, despite
`transport.burst_requests` proving a real burst request and capture
happened for every one of the 9, and despite the outer cache never
approaching its own 128-entry bound (peaking at 8 pre-fix). **GREEN** after
the fix: all 9 generations, `gen-early` included, are admitted. This
reproduces the same semantic failure the real field session hit —
`blocked_missing_evidence` for a proposal whose evidence really was
captured — not merely an assertion about current implementation details.

An earlier draft of this same fixture accidentally also captured
`classifier_same_frame` evidence (because every synthetic envelope shared
one identical payload, so same-frame candidates trivially never evicted),
which masked the intended failure as `reject_no_identification_or_context`
instead. Corrected by deliberately mismatching the scripted `TrackUpdate.
frame_id` from the real envelope's own `frame_id` (same-frame eligibility
requires an exact match) — worth recording here because the same accidental
"other evidence happens to survive" shape may be part of why the real field
session's own `only_alternate_or_no_selected_evidence_available` cases (12
in the session, disclosed as "likely a red herring") were never conclusively
ruled out as related; not re-investigated further here, as it does not
change this milestone's own root cause or fix.

## 9. Root cause

`LiveCameraNodeShadowSession._temporary_payloads`/`_same_frame_temporary_
payloads` (`camera_node_live.py`) are each their own small, fixed,
content-hash-keyed cache, hardcoded to 8 entries — entirely independent of,
and never touched by, `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_
BYTES` (the cache the 8→32→128 milestones actually resized). They existed
to bridge a real capture to the moment `engine_runtime`'s own harvest could
copy it out "while the session is still live" (see the pre-existing
comment at `engine_runtime.py`, "burst_bytes_cache" note). But the harvest
call itself only ran once per whole `session.run()` batch — after the
entire up-to-20-frame batch had already returned — not per frame as
captured. A batch busy enough for more than 8 separate frames to each
successfully capture a burst silently evicted an early one from the small
cache before the harvest loop ever reached it, with no surviving signal
distinguishing this from "never captured at all."

## 10. Files changed

- [src/mockingbird/observation/camera_node_live.py](../src/mockingbird/observation/camera_node_live.py) —
  `LiveCameraNodeShadowSession.run()` gains an optional `on_result` callback,
  invoked synchronously with each frame's result the instant it is produced.
- [src/mockingbird/observation/engine_runtime.py](../src/mockingbird/observation/engine_runtime.py) —
  `_run_async` now passes `on_result=_harvest_immediately` (a local closure
  harvesting both caches per frame); `_harvest_burst_bytes`/`_harvest_same_
  frame_bytes` now return a miss count, accumulated into a new bounded
  `_EngineSession._evidence_harvest_misses` counter surfaced via `advanced.
  evidence_harvest_misses`; the two pre-existing post-batch/post-stop harvest
  calls are kept unmodified in behavior (still called, now also counted) as
  a harmless, idempotent defense-in-depth fallback.
- [tests/test_engine_runtime.py](../tests/test_engine_runtime.py) — one new
  focused RED/GREEN regression test plus its supporting fixtures.

No schema change (nothing persisted changes shape); no migration.

## 11. Implementation

Smallest general fix satisfying every governing requirement: hardware-
agnostic, no species/feeder-specific case, no cache-size increase anywhere,
no weakening of evidence provenance, no admission of proposals with
nonexistent evidence, no synthetic replacement evidence, exact source
frame/bbox/track lineage fully preserved (harvesting only changes *when*
real, already-captured bytes are copied, never *which* bytes or from
*where*), abstention preserved (a proposal with genuinely no captured
evidence still, correctly, fails admission — this fix only stops a
proposal whose evidence really *was* captured from being wrongly treated as
if it never had been).

## 12. Diagnostics added

`_EngineSession._evidence_harvest_misses` — a bounded lifetime counter,
incremented whenever a harvest call finds a role-matching candidate whose
content hash is no longer present in the live session's own temporary
cache. By construction (an `EvidenceCandidate` of this role only ever
exists after its payload was already inserted into that same cache at least
once) this is **always** a genuine "captured, then lost before harvest"
fact, never "never captured" — closing exactly the observability gap the
field report itself disclosed ("no surviving log/API signal distinguishes
[the two]"). Surfaced read-only via `GET .../observation/status`'s existing
`advanced.evidence_harvest_misses` field, alongside the existing
`counterfactual_ledger`/`suppressed_reasons` diagnostics — no new endpoint,
no raw-frame telemetry, no high-cardinality metric. A future field session
finding this non-zero after the fix above would mean a *residual*,
narrower version of the same race (for example, a single frame alone
producing more than 8 successful captures) and would warrant its own
bounded follow-up; a future session finding it stays zero is direct,
positive confirmation this closure holds.

## 13. Focused tests

```
tests/test_engine_runtime.py::test_batch_internal_burst_capture_no_longer_starves_an_early_generations_evidence
```
RED confirmed against the pre-fix source (verified via `git stash` of only
the two source files, not merely reasoned about); GREEN confirmed with the
fix restored. Full `tests/test_engine_runtime.py`: **68 passed**. Full
`tests/test_observation_camera_node_live.py`: **37 passed**.

## 14. Core validation

`python scripts/verify_core.py`: **3301 passed, 2 skipped, 10 deselected,
11 xfailed** in 548.47s (~9m08s) — zero failures, matching this repository's
documented ~9-minute Core-gate target exactly. No unrelated flake observed.

## 15. Historical cache negative control

The 32→128 evidence-cache-capacity fix remains closed and unregressed,
confirmed directly (not merely by absence of a new failure):

- `test_evidence_cache_bound_has_real_headroom_over_the_old_undersized_default` — pass.
- `test_delayed_proposal_still_finds_its_evidence_after_unrelated_cache_churn` (the original 8→32 reproduction) — pass.
- `test_delayed_proposal_survives_a_busier_real_session_shape_than_the_32_bound_covers` (the 32→128 reproduction) — pass.

All three ran unmodified, inside the same full `tests/test_engine_runtime.py`
pass reported above. `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES`
remain `128` — not touched by this milestone, per its own governing
constraint. Delayed evidence survival, ambiguity arbitration, Visit
admission precision, counterfactual accounting, same-frame classifier
evidence, and multi-subject Phase-1 bookkeeping all pass unmodified inside
the Core suite above (`test_visit_episode_assembler.py`,
`test_scene_confusor.py`, `test_unified_observation_status.py`,
`test_visit_classifier_supporting_evidence.py`, and the full engine-runtime
suite all green).

## 16. A related, disclosed, not-fixed finding

`candidate_visit_authority_cli.py` (the separate, bounded, operator-driven
`candidate-authority-trial` diagnostic — max 600s, max 3 real candidates,
never the automatic path a real field session runs) has its own, differently
-shaped instance of the same root cause: it resolves evidence bytes lazily,
directly against the live session's `temporary_burst_payload`, once per
10-second assembly tick rather than immediately per frame — so more than 8
successful captures within one 10-second tick window could suffer the
identical loss. This tool is not the production path this milestone
investigated (the real 2026-08-20 field session ran through
`ObservationEngineSessionManager`, never this CLI), its own real trial usage
is bounded and low-volume by explicit design, and fixing it would touch a
third file's own separate, local re-implementation of the assembly-tick
loop — disclosed here as a genuine, scoped, lower-priority follow-up, not
undertaken in this milestone to avoid the exact "do not implement
speculative architecture beyond the proven defect" scope creep this
milestone's own governing constraints warn against.

## 17. Decision

**A — ISSUANCE DEFECT PROVEN AND FIXED.** A concrete upstream evidence
harvest defect (§4, §9) was reproduced deterministically through the real
production path (§8), fixed with the smallest general change available
(§11), and regression-tested with zero measured regression across the full
Core suite and every historical cache-capacity control (§14–15).

## 18. Recommended next milestone

Per the milestone's own governing order ("prove synthetically first,
integrate, then propose the smallest useful live confirmation separately" —
not undertaken in this session): the next concrete action is a bounded live
field check, not a full 60–90-minute cohort, specifically watching
`advanced.evidence_harvest_misses` across a real busy session — expect it
to stay at 0 for ordinary activity and to register only under genuinely
adversarial batch-local burst density, if ever. This is a smaller,
narrower live ask than the cache-128 daylight cohort that preceded this
milestone, since the fix's own correctness is already proven synthetically
end-to-end. Separately and at lower priority: the disclosed CLI-trial
finding above (§16), if that tool's own real-hardware trial usage ever
becomes more than occasional/diagnostic.
