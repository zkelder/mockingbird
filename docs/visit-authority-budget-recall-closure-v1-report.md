# Visit Authority Budget + Ambiguous-Boundary Recall Closure v1 — Report

Starting HEAD: `5c8f344` ("Record real field-validation results for Scene Confusor Suppression v1").
Implementation HEAD: `417d642` ("Add Visit Authority Budget + Ambiguous-Boundary Recall Closure v1").
Branch: `main`. **Not pushed.**

This milestone fixes the two defects Persistent Scene Confusor Suppression v1's own required
fresh field validation surfaced: (1) a candidate-visit authority budget that was a global,
cross-Stream, cross-session-lifecycle singleton rather than being scoped to one genuine
Observation session, and (2) two long, high-confidence, heavily-tracked real encounters
(~5.0min/34-generation/0.889-confidence and ~8.67min/40-generation/0.846-confidence) that
produced zero Visits despite the already-accepted ambiguous-boundary arbitration mechanism.

## 1. Candidate-budget root cause

`ObservationAuthoritySettingsModel` was a single global singleton row (`singleton_id=1`)
shared by every Stream. `activation_boundary_at` reset only on an actual `shadow ->
candidate_visit` *mode transition*; re-affirming an already-active mode left it untouched by
design (to prevent a caller from sneaking a wider backlog window in by reactivating
repeatedly). `_EngineSession._run_async` calls `set_observation_authority_mode(candidate_visit)`
exactly once per real "Start observing" action; `stop()` always reverts to shadow, but only
if something in-process actually calls it.

**The exact defect**: a process that never reached `stop()`'s kill switch (a crash, `kill -9`,
or -- concretely, in this project's own real workflow -- a mid-session Windows dev redeploy)
left the DB row stuck at `candidate_visit` with a stale, possibly-already-exhausted
`activation_boundary_at`. The next literal Start -- even in a brand-new process -- found mode
already `candidate_visit` and, under the old re-affirmation rule, never got a fresh boundary,
silently inheriting whatever budget the "crashed" session had already spent (in the real
2026-08-19 case, exhausted since the *previous day*).

**The secondary defect**, traced while tracing the first: `_authority_state`'s session/hourly
count queries had no `stream_id` filter at all, despite `ObservationCandidateVisitModel.
stream_id` already existing on every ledger row. Combined with the single global settings row,
this meant one Stream's Stop silently reverted a *different*, still-running Stream's authority
to shadow, and Streams could consume each other's candidate budgets. Never observed live (only
one real Camera Node Stream has ever existed in this project's field history), but the code
already supports concurrent multi-Stream sessions (`ObservationEngineSessionManager._sessions:
dict[stream_id]`), so this was a real, latent, structurally-present defect, not a hypothetical.

## 2. Old vs. new lifecycle semantics

| | Old | New |
|---|---|---|
| Settings row scope | One global singleton (`singleton_id=1`) | One row per Stream (`stream_id` primary key), schema 35 |
| Session/hourly candidate count | Global, across every Stream | Filtered by `stream_id` |
| Boundary reset on Start | Only on an actual `shadow->candidate_visit` transition | Also whenever `_EngineSession`'s own Start path asserts `fresh_session=True` -- unconditionally safe there, since a live in-process session for a Stream is structurally prevented from calling Start twice, so the only way mode is already `candidate_visit` for that Stream is a stale leftover |
| Stop of Stream B | Could revert Stream A's authority to shadow too | Touches only Stream B's own row |
| Upgrade behavior | N/A | Migration drops+recreates the settings table -- every Stream reverts to the safe `shadow` default, which is also the direct fix for any installation carrying a stale stuck row forward |

See "Session/Stream scope" and "Fresh-session activation" in
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md) for the complete
design and reasoning.

## 3. Health/diagnostic behavior

`ObservationEngineSessionStatus`/`ObservationSessionStatusResponse` gained
`candidate_authority_exhausted: bool` (sticky for the running session once a
`blocked_session_limit` outcome is observed) and `candidate_authority_message: str | None`.
Surfaced in the *basic* Observation panel (`ObservationControlPanel.tsx`), not buried in
advanced diagnostics, since a Stream can be genuinely `observing`/`engine_available` while
unable to create any further Visit -- exactly the shape that must never read as ordinary full
productivity. Raw counters (configured budget, consumed count, activation identity, exhaustion
reason) remain in the existing `advanced` object (`activation_boundary_at`,
`counts.suppressed_reasons`), never new UI clutter in the basic view.

## 4. Replay of both newly-missed strong encounters

Reconstructed from the real 2026-08-19 field session's own still-live counterfactual ledger
(the deployed process, pid 6888, had never been restarted since that session ended, so its
in-memory ledger was queryable directly via `GET .../observation/counterfactual`) -- see
"Defect 2" in the scratch analysis this report is drawn from, condensed here.

**Cluster A (~33-334s of Part 2, ~5.0min/34-generation/0.889-confidence per the prior
milestone's own report)**: real proposal `visit-episode:0d1e1556e5e617` [97079,226173]ms, 7
constituent generations, reached the evidence-admission gate (proving it either was never
ambiguous or won arbitration) and permanently failed:
`reject_no_identification_or_context`/`only_alternate_or_no_selected_evidence_available` at
14:44:56Z UTC (~53s after its own tracklet activity ended at ~226s stream-offset). Every smaller
sibling fragment in this region shows `blocked_ambiguous_boundary` (permanent, correctly so) or
an earlier `blocked_continuation_pending` retried into the above. No proposal_outcome record
exists for this region after ~14:45:51Z -- nothing ever re-attempts it, including at the
session-ending finalize tick.

**Cluster B (~1025-1545s of Part 2, ~8.67min/40-generation/0.846-confidence)**: identical
pattern. Real proposal `visit-episode:00cbbf870d892b` [1226507,1356419]ms, 5 constituent
generations, same terminal outcome, at 15:05:19Z UTC.

### Exact first irreversible loss stage (both clusters)

1. The ambiguous-boundary arbitration mechanism (Admission Recall Investigation + Conditional
   Fix v1) is proven **working as designed** for both clusters -- direct proof: a proposal can
   only reach `reject_no_identification_or_context` by never being ambiguous or by *winning*
   arbitration, since `evaluate_candidate_authority`'s ambiguity check runs strictly before the
   "create" path, and the repository's evidence-quality gate runs only after authority already
   said create.
2. The proposal that escapes ambiguity in each cluster is the encounter's own best-evidenced
   merge (correct arbitration behavior).
3. That proposal's own admission attempt is *legitimately delayed* past its own evidence-capture
   moment -- by design, since ambiguous-boundary/continuation-pending resolution must wait for
   the assembler's own stabilization window (up to `ambiguous_gap_ms`, 45s, per retry cycle, or
   longer for a still-growing cluster).
4. By the time the delayed attempt runs, the proposal's own already-captured burst evidence has
   been evicted from `engine_runtime`'s harvested `burst_bytes_cache`/`same_frame_bytes_cache`
   -- a session-global cache bounded to only 8 entries, evicted purely by insertion count, with
   zero awareness of which pending proposal still needs which bytes. Unrelated activity
   elsewhere in the busy real stream (9,363 raw detections, 125 track generations across the
   whole ~98-minute 2026-08-19 session) cycles the cache many times over within a 45+ second
   delay window.
5. `reject_no_identification_or_context` is not in `RETRYABLE_OUTCOMES` -- permanent, exactly
   like `blocked_ambiguous_boundary` was before Conditional Fix v1, but with no rescue
   mechanism, and none is meaningful after the fact: the bytes are genuinely gone.

**Neither cluster's loss is attributable to the ambiguous-boundary arbitration mechanism
itself** -- it is one stage downstream, at evidence retention capacity.

## 5. Fix: evidence-cache capacity, not an admission threshold

`_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES` raised from 8 to 32 (`engine_runtime.py`).
This is a bounded in-memory *capacity* change: every evidence-quality requirement
`candidate_quality_gate.evaluate_evidence_admission` enforces (a real, decodable,
geometrically-valid identification/context candidate) is completely unchanged. The ambiguous-
boundary arbitration decision logic (`candidate_visit_authority.resolve_ambiguous_boundary_
arbitration`, `visit_episode_assembler.classify_boundary`) was **not** touched -- real evidence
(§4) shows it is not the failure point for either missed encounter.

Reproduced exactly with a focused regression test using the real generation/timing shape
(single generation, `blocked_continuation_pending` delay, unrelated cache churn from
concurrent activity): `test_delayed_proposal_still_finds_its_evidence_after_unrelated_cache_
churn` fails with the exact real outcome (`blocked_missing_evidence`) against the old bound
(8) and passes against the new one (32) -- verified directly by temporarily reverting the fix
and re-running (RED), then restoring it (GREEN).

**Honest limitation**: the real burst bytes for clusters A and B were never retained anywhere
(by design -- see rejected-detection-attribution-contract.md) and are now permanently
unrecoverable, since the sandbox process was redeployed for this milestone's own field
validation. The fix's real efficacy for *these specific* clusters can only be confirmed
prospectively, by a fresh field session encountering a similarly-shaped real encounter -- not
retroactively proven against the historical bytes. This is disclosed rather than overclaimed;
see §9 for whether the fresh session actually exercised this shape.

## 6. Negative controls

- **0.795-confidence historical ambiguous-boundary pair** (the original Admission Recall
  Investigation + Conditional Fix v1 motivating case): replayed unchanged
  (`data/field-acceptance/2026-08-17-admission-recall-investigation/
  replay_real_pair_before_after.py`, pure `candidate_visit_authority` functions only, no
  repository/DB layer -- nothing in this milestone's changes could have touched it). Result
  identical to the original: 0.795 proposal -> `create` (arbitration winner), 0.590 sibling ->
  still `blocked_ambiguous_boundary`.
- **Ambiguous-negative / fragmentation-duplicate regression**: covered by the existing,
  unmodified regression suite -- `test_continuation_pending_defers_admission_until_encounter_
  resolves` (the real candidate-004/005 fragmentation shape) and
  `test_stage619_synthetic_two_separate_appearances_stay_separate_candidates` (the real
  session-04 genuinely-separate-appearances shape) both still pass unmodified.
- **Multi-Stream isolation** (new invariant this milestone establishes): `test_multi_stream_
  authority_is_isolated` (repository level) and `test_multi_stream_stop_does_not_kill_a_
  different_streams_authority` (engine level) prove Stream B's Stop/exhaustion never touches
  Stream A.

## 7. Historical precision replay (scene-confusor 70-event cohort)

Re-ran the prior milestone's own real replay script and data
(`data/evaluations/scene-confusor-suspicion-v1/real_repository_replay.py`, still present
locally under gitignored `data/`, patched only for the new required `stream_id=` parameter and
a local data path) against this milestone's fixed code. **Byte-identical to the original
milestone's reported numbers**:

- Cold-start: 40->35 false Visits (57.1%->53.8%), 30/30 real retained, 0 wrongly blocked, 5
  correctly blocked (idxs 51, 54, 68, 69, 80).
- Steady-state: 14/40 (35.0%) false recurrences caught, 0/30 real wrongly blocked.

Confirms the budget-lifecycle and evidence-cache-capacity fixes have **zero effect** on
scene-confusor precision/recall -- proven by real-data replay, not assumed from code review
alone.

## 8. Independent biological encounter denominator

See [independent-encounter-denominator-design.md](independent-encounter-denominator-design.md)
for the complete design. Summary: a capability-safe tee inside the Observation Engine's own
frame-processing loop (`mockingbird.observation.acceptance_recorder`), sampling already-decoded
analysis frames at a bounded interval (3s default) to a local, diagnostic-only directory, with
zero import path into the product repository or any admission-pipeline module -- structurally
incapable of becoming evidence. Off by default; enabled only via
`MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR`, forwarded through `scripts/deploy_windows_dev.py`'s own
narrowly-scoped, opt-in `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` for this field session only
(unset by default, no normal dev-deploy behavior change).

## 9. Performance

Both fixes are bounded and, if anything, more selective than before:

- **Authority lookup**: still exactly one primary-key row fetch per admission attempt
  (`session.get(ObservationAuthoritySettingsModel, stream_id)`), same shape as before
  (`session.get(..., 1)`) -- a string PK lookup instead of an int PK lookup, not a materially
  different cost. The session/hourly count queries gained a `stream_id` filter, which narrows
  (never widens) the scanned row set relative to the old global count -- strictly cheaper or
  equal, never more expensive, and still uses the existing `ix_observation_candidate_visits_
  created_at` index shape (a `stream_id` equality filter combines with the existing indexed
  range scan; no new index was required for correctness, though a future composite `(stream_id,
  created_at)` index would be a pure optimization if this table grows large -- not required at
  today's scale).
- **Evidence-cache bound**: raising `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES`
  from 8 to 32 is a bounded in-memory dictionary size increase, not a per-request compute cost
  -- `dict` insertion/lookup/eviction remain O(1) regardless of the bound. The only real cost is
  memory footprint (32 source-resolution-adjacent JPEGs instead of 8, a few tens of MB at most),
  bounded and disclosed in the constant's own code comment.
- **Acceptance recorder**: entirely additive and off by default; when enabled, each considered
  frame is O(1) (one dict-free interval comparison) and a save is one bounded file write plus
  one JSONL append -- no scan of history, no unbounded growth (hard count/byte caps enforced
  directly).

No unbounded history scan was added anywhere in this milestone's changes.

## 10. Fresh field validation

**Session**: stream `stream-ca892992771c`, real paired Pi Camera Node. Started
`2026-08-19T17:14:00.938300Z`, stopped `2026-08-19T18:35:52.411723Z`
(`stopped_reason: user_stopped`) — **81m51s**, against a stated-before-starting bound of
"at least 45-60 real minutes" (`field-session-plan.md`). Pre-flight confirmed the deployed
build directly: `git_commit 417d6426...` (== this milestone's implementation HEAD),
`database_schema_version: 35`.

### Budget-lifecycle live verification

Direct proof the fresh-session fix (§1-2) works in the real deployed build, not just in
tests: `advanced.activation_boundary_at` came up at `2026-08-19T17:14:03.751518+00:00` —
**3 seconds after Start**, a fresh timestamp, not a stale inherited one — and stayed at that
exact value for the entire session (confirmed both by the poll log below and the final
post-stop status). `candidate_authority_exhausted` was `false` at every one of 84 status
polls across the full 82 minutes and in the final post-stop status; `blocked_session_limit`
never occurred. 8 candidates were created against the default budget of 50 — nowhere near
exhaustion. Only one real Camera Node Stream exists in this project's field history, so
cross-Stream isolation was not exercised *live* this round; that invariant is covered instead
by `test_multi_stream_authority_is_isolated`/`test_multi_stream_stop_does_not_kill_a_
different_streams_authority` (§6).

### Independent recorder: real operation, and a real defect it surfaced

The acceptance recorder saved 936 frames spanning source-offset `0` to `3,117,664ms`
(**51m58s of the 81m51s session, ~63.5%**) before it silently stopped. Root cause: analysis
JPEGs measured **~801KB average, ~841KB max** — not the "well under 200KB" the original
`max_total_bytes` default (750MB) assumed — so the byte bound bound first, well before
`max_frames` (2400) or the session's actual end. This is a real, disclosed, now-fixed defect
in the recorder itself (`max_total_bytes` raised to 2.5GB with measured headroom; see the new
`test_default_byte_bound_has_real_headroom_over_the_old_undersized_default`) — it cost this
session independent coverage of its last three admitted Visits, and is fixed for the next one.
The recorder's own zero-coupling guarantee held throughout: nothing it did or didn't capture
influenced any admission decision.

### Independent visual review

First-pass review used wide, full-frame "contact sheets" (24 sheets) and found no bird
anywhere — a false negative caught by spot-checking a full-resolution frame near a known
candidate's timestamp, which clearly showed a bird invisible at that thumbnail scale. Rebuilt
as 39 "crop sheets" (cropped to the feeder region, 6x4 grid, validated against the same
known-positive frame before use) and re-reviewed the entire independently-recorded span from
the start. This self-correction is disclosed because it changes how much confidence the
"no bird visible" spans below should carry: the crop-sheet method is the one actually load-bearing
for this report's conclusions.

### Cross-reference: all 8 admitted Visits against independent coverage

6 of 8 candidates' exact proposal spans were recoverable from the counterfactual ledger before
its own 60-minute age-bound evicted them (095/096 were not — both fall before offset
`1,336,298ms`, the earliest surviving record). Bracketing 095/096's true creation time against
the field-session poll log (the interval between the last poll still showing the old count and
the first poll showing the new one) still bounds them precisely:

| Visit | Span (session offset) | Independent visual result |
|---|---|---|
| 095 | bracketed (101s, 603s] | **Not found.** Full crop-sheet coverage of this bracket (sheets 00-07); no bird visible. Most likely explanation: an encounter briefer than the 3.37s effective sample gap (see 872.6s below, where a real encounter landed on only one sample) — not evidence against the Visit. |
| 096 | bracketed (603s, 979s] | **Plausible match, not proven.** A single-frame bird sighting at t=872.6s (frame #263, hovering posture near the hummingbird feeder) falls inside this bracket; absent at both neighboring samples (869.2s, 876.0s), so genuinely single-sample. No counterfactual match either way — this timestamp falls inside the ledger's evicted region. |
| 097 | 1336.3-1347.2s | **Confirmed.** Full-resolution frames #402-403 (t=1336-1339s) show a bird at the feeder; matches the recovered span exactly. |
| 098 | 1607.8-1686.2s | **Confirmed.** Full-resolution frame #490 (t=1629.8s) shows a bird actively feeding; visible continuously across frames #484-505 (~72s), consistent with the full recovered span. |
| 099 | 2241.8-2250.4s | **Inconclusive.** Both independent samples that fall inside this 8.6s window (t=2244.3s, t=2247.7s) show an empty scene — but two samples 3.4s apart cannot rule out a sub-3.4s perch in the remaining gaps. Not treated as contradicting the Visit. |
| 100 | 4432.8-4456.6s | Outside the ~52min independent coverage window (a direct consequence of the byte-bound defect above). |
| 101 | 4678.5-4689.0s | Outside coverage. |
| 102 | 4683.1-4700.9s | Outside coverage. |

**Net**: 2 of 8 directly photographically confirmed, 1 of 8 plausibly correlated, 1 of 8
inconclusive (sampling too sparse for an 8.6s window), 1 of 8 unconfirmed despite full coverage
(attributed to sampling-interval limits, not disproven), 3 of 8 outside coverage. **Zero of 8
independently contradicted** — no span where independent sampling was dense enough relative to
the Visit's own duration to be confident nothing was there.

101/102 also deserve a direct note: their spans overlap by ~5.9s, which a coarse clustering
pass (below) flags as one cluster producing two Visits. Their underlying track data rules out
assembler-level fragmentation directly: two entirely distinct frame-tracks
(`frame-track-0081`/`frame-track-0082`), independent geometry, independent
`maximum_unsupported_duration` terminal reasons on each — consistent with two birds visiting
in close succession, not one encounter incorrectly split.

### False Visits, duplicates, fragmentation, evidence quality, scene-confusor

- **False Visits**: 0 confirmed among 8 (direct confirmation for 2, no contradiction for the
  remaining 6 per the table above).
- **Duplicates**: none confirmed — 101/102 investigated directly above and ruled distinct.
- **Fragmentation** (the original failure shape this milestone targets — a strong encounter
  split by `blocked_ambiguous_boundary` into permanently-unadmitted fragments): not observed
  this session for any of the 8 admissions; each has a single winning proposal.
- **Evidence-quality-failure rate**: 13 of 142 proposals (9.2%) hit
  `reject_no_identification_or_context`. Two of the underlying rejected clusters fall entirely
  inside the independently-covered span (t=1786-1938s, max confidence 0.178; t=2559-2804s, max
  confidence 0.158) — independent review of both exact spans (crop-sheets 22-24, 32-35) found no
  bird, consistent with low detector confidence reflecting genuinely non-bird activity rather
  than a missed real encounter.
- **Scene-confusor regression**: 0 firings. The final live status's own `suppressed_reasons`
  breakdown is authoritative and complete: `blocked_continuation_pending` (113),
  `reject_no_identification_or_context` (13), `blocked_ambiguous_boundary` (7),
  `blocked_shadow_mode` (1, an expected artifact of one proposal spanning the ~3s activation
  gap at session start) — no scene-confusor-specific reason appears. Second consecutive live
  session with zero interference.

### Complementary detector-side view (explicitly not the denominator)

`encounter_accounting.cluster_encounters` reconstructs 19 detector-side clusters from the
(partially-evicted) ledger's 80 track generations / 132 proposal outcomes. This tool's own
`tracking_recall` (0.68) / `proposal_recall` (1.0) / `admission_recall` (0.38) are a
**detector-internal, self-referential measure** — "of what the detector already tracked, how
much became a proposal / got admitted" — not the biologically-grounded recall this milestone
requires, and **not used as the denominator or as grounds for the decision below**. It served
only as a cross-check, and agreed with the independent review everywhere the two overlapped
(the two birdless rejected clusters above; the 101/102 non-duplication).

### Performance (live)

82 minutes, 2,067 track updates, 600 evidence candidates, 18,487 raw detections, 142 proposals,
8 admissions — no latency or timeout issue observed. Consistent with §9's bounded-cost
reasoning (single-row authority lookup per attempt, narrowed not widened count queries).

### Remaining uncertainties

- **Defect 2's fix was not exercised live** by a matching encounter this session — no cluster
  reached the specific "escapes ambiguity, then delayed past its own evidence-capture moment"
  shape that clusters A/B (§4) originally followed. Its correctness rests on synthetic RED/GREEN
  reproduction using the real generation/timing shape (§5) plus zero measured regression (§6-7),
  not a fresh live catch of the same failure mode.
- Independent coverage reached 52 of 82 minutes this round (now fixed for the next session);
  3 of 8 Visits were entirely outside it, 1 of 8 unconfirmed despite being inside it, 1 of 8
  inconclusive.
- 096's correlation to the t=872.6s sighting is plausible pattern-matching (bracket containment,
  single-sample brevity consistent with a hummingbird), not proof of identity.

## 11. Decision

**B** — the candidate-budget/session-lifecycle defect is fixed and **live-verified**: fresh
activation proven within 3 seconds of Start, zero exhaustion across a real 82-minute, 8-Visit
session, zero cross-Stream interference (proven by test, not exercised live — only one Stream
exists). The admission-recall (evidence-cache-capacity) fix is soundly verified against the
real reconstructed shape of both originally-missed encounters, with zero measured precision
regression across every replayed cohort — but this fresh session did not happen to produce
another long, high-confidence encounter that traverses the exact ambiguity-then-delayed-
evidence path clusters A and B originally failed on, so it still lacks a live proof point under
real conditions. Recommended next bounded step: one more fresh field session (recorder now
fixed for full-duration coverage) with no code changes needed first — the fix is already in
place and only needs a matching real encounter to confirm end-to-end. This is not a
detector/counterfactual-only conclusion: it rests specifically on what the independent
recording could and could not confirm (§10), which is the reason it stops short of A.
