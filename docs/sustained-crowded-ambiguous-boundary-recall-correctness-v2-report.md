# Sustained / Crowded Ambiguous-Boundary Recall Correctness v2

Bounded RELEASE-CRITICAL Gate A correctness milestone. Reopens the
accepted, frozen Ambiguous-Boundary Real-Subject Recall Correctness v1
investigation because Representative Daylight Gate A Field Acceptance v14
supplies new, concrete, real-field evidence about the same mechanism.

## Starting state

Verified directly, not assumed:

- Branch `main`, HEAD `b832df1` (`b832df13b3e860fdfc0044c8d0f3c4c3ebbcddc3`,
  "Reconcile release-execution-state.md: accept Representative Daylight
  Gate A Field Acceptance v14 (classification A)") — exact match to the
  governing brief's expected starting HEAD.
- Schema `v58` (confirmed via `CURRENT_DATABASE_SCHEMA_VERSION` in
  `src/mockingbird/storage/database.py`), unchanged.
- `docs/release-execution-state.md`'s own newest dated entry (§1, appended
  by the `b832df1` reconciliation) confirms, verbatim: latest accepted
  milestone Representative Daylight Gate A Field Acceptance v14,
  classification **A**; **Gate A remains OPEN**; evidence-capture profile
  recovery and proposal-outcome ledger completeness both **fully CLOSED,
  both halves**; ambiguous-boundary/geometry-compatibility-tolerance
  question moved from "candidate fact for the next cohort" to "this
  cohort's own best-evidenced, most consequential open item"; current
  authorization **NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**.
  (§1's own top summary "Accepted HEAD" bullet is a separate,
  already-disclosed, pre-existing documentation lag — still reads
  `e57c911` — that prior milestones, including v14 itself, have already
  flagged as "a documentation-only lag, not a state-tracking authority";
  not corrected here, out of this milestone's own bounded scope, same
  discipline v13/v14 both already followed.)
- Not pushed: `main` ahead of `origin/main` by 340 commits at session start.
- Worktree safety: `git status --short` shows only the 7 explicitly-listed
  untracked files, confirmed present, non-zero size, untouched throughout
  this session (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`). No active writer (single session,
  no lock/PID artifacts).

No material difference from the brief's expected starting state. Proceeded.

## Reopening basis

- Ambiguous-Boundary Real-Subject Recall Correctness v1 investigated one
  chartered, isolated real case (the v12 "~37:12" bird) and correctly
  concluded (Classification I in its own lettering / "no trustworthy
  separator exists" in this milestone's) that no safe correction could be
  made without touching the explicitly out-of-scope `classify_boundary`
  geometry-compatibility tolerance. **That conclusion is not revisited or
  contradicted here** — it is directly reconfirmed, at real code-execution
  fidelity, by this milestone's own new tests (see "RED→GREEN").
- Representative Daylight Gate A Field Acceptance v14 supplies a
  materially larger, richer evidence body about the *same* mechanism:
  conservative recall 11/17 = 64.7%; 6 confirmed misses, 5 of which
  terminate at `blocked_ambiguous_boundary`; one confirmed real activity
  period lasting ~310 continuous seconds, containing an 11-proposal-deep
  ambiguous component and confirmed simultaneous two-bird moments, that
  produced zero Visits.
- This materially strengthens product impact: the mechanism is no longer
  evidenced by one isolated pair, but by the *dominant* recall-limiting
  cause of an entire representative session under real sustained/crowded
  conditions — exactly the kind of new, concrete field evidence the
  accepted-work freeze's own reopening exception exists for.
- The question this milestone answers is narrow and specific: **does the
  richer v14 evidence body expose a safe, principled correction the
  isolated v12 case could not?** The answer, established below with new
  rigor (full five-miss + 310s-case reconstruction, direct code-level
  confirmation of the exact dispatch mechanism, and one newly-identified,
  but not fixed, structural asymmetry), is **no** — for the same
  fundamental reason v1 already found, now reconfirmed at much greater
  depth and scale, not a new defect.

## Prior v1 conclusion

Reconstructed directly from
[ambiguous-boundary-real-subject-recall-correctness-v1-report.md](ambiguous-boundary-real-subject-recall-correctness-v1-report.md),
not re-litigated:

- The v12 "~37:12" bird (`visit-episode:06c209aec98c56ebcc7d9d47`) formed an
  ambiguous link to one or more already-resolved prior episodes (V016/V017,
  both admitted) purely through `classify_boundary`'s own geometry
  -compatibility tolerance (`geometry_gap_tolerance` capped at 0.6 normalized
  centroid distance for any gap ≥ ~9.6s — the same disclosed, out-of-scope
  tolerance All-Alternate Subject Evidence Recall Correctness v1 had already
  flagged). Once that link exists, arbitration resolves it *naturally* (not
  forced), correctly admits the single best-evidenced member, and correctly,
  permanently blocks the loser — a deterministic, intended consequence, not a
  separate defect.
- v1's own Root-cause classification for this specific case: **current
  policy is inherently unable to separate it safely, using only currently
  -existing trustworthy facts** (its own lettering "I"; this milestone's own
  scheme would call it J). Every brief-preferred correction class was
  checked directly against the case and found inapplicable without touching
  geometry. No heuristic was invented.
- v1 separately found and fixed a **different, in-scope dispatch defect** in
  the identical mechanism family: a component's own top-ranked member could
  itself already be permanently *dead* (never admitted, blocked on a
  strictly earlier tick) with a live, later, real bird never getting a
  chance at the bypass at all — "dead-anchor promotion"
  (`engine_runtime._live_chain_for_component`). This fix explicitly,
  adversarially, and by design left one policy question untouched and
  tested as correct: **if any component member was ever *admitted*
  (not merely dead), the whole component stays vetoed, unconditionally,
  regardless of how a newly-joined, higher-ranked live member would
  otherwise rank** (`test_a_stronger_later_arrival_never_bypasses_an_
  already_admitted_component_member`, `test_already_admitted_component_
  winner_still_blocks_every_later_member`).
- v1's own residual risk explicitly named the open question this milestone
  answers: "whether ambiguous-boundary arbitration's own geometry
  -compatibility tolerance meaningfully discriminates real subjects from
  persistent confusors within its 45-second window... is a candidate for a
  future, separately-authorized milestone" — and v14's own report
  independently, explicitly frames its own finding as answering exactly
  this candidate fact: "yes, materially, under real sustained/crowded
  activity."

## V14 five-miss case set

Reconstructed directly from the real, preserved v14 session ledger
(`data/field-acceptance/2026-09-05-gate-a-v14-corrected-evidence-path-
reproof/merged-ledger/counterfactual-merged.json` — 22,260 `raw_detections`,
218 `track_generations`, 191 `proposal_outcomes`, the full merged ledger,
not the smaller final-checkpoint-only snapshot), cross-checked against
[representative-daylight-gate-a-field-acceptance-v14-report.md](representative-daylight-gate-a-field-acceptance-v14-report.md).
**Component membership beyond directly-observable `constituent_generation_
ids`/temporal-adjacency/geometry is reconstructed, not directly recoverable**
— `ambiguous_adjacent_proposal_ids` is an in-memory-per-tick fact the live
session never wrote to any preserved artifact (the same genuine,
disclosed data-preservation gap v1 already found for the v12 session).
Every reconstruction below is disclosed as inference from decision
timestamps (proven, via the same 10-second-tick-floor argument v1 used, to
distinguish same-tick from cross-tick decisions), offsets, and geometry —
never presented as a directly-recovered edge list.

| # | offset | first irreversible reason | proposal(s) / gens | decided_at clustering | continuation cycling | component shape (reconstructed) | evidence availability | new evidence after initial ambiguity | multi-subject present | terminally-non-viable member present |
|---|---|---|---|---|---|---|---|---|---|---|
| **4** | 1467.0–1512.3s | `blocked_ambiguous_boundary` | `44fe74e3290a71e9` (2 gens: `ae1f95876e71ae`+`9833d25cf8c392`, conf 0.813) | single decision, 18:18:05 | none (arrives pre-merged) | 2-member: this proposal + **already-admitted** `4dbcd1748c26026f` (visit-005, conf 0.787, 1 gen, ended 42.9s earlier — within `ambiguous_gap_ms`) | present (not the blocker) | none additional | no | **yes — visit-005, admitted ~90s before this proposal's own first evaluation** |
| **7** | 3378.9–3453.1s | `blocked_ambiguous_boundary` | `c1f69ad0d5e51df3` (3 gens) + `5774df46aabbf457` (1 gen); winner `7e9a3546c7ab4d1d` (2 gens) admitted as visit-008 via `fallback_position_1` | all three decided within 0.53s of each other (18:52:41.64–18:52:42.17) — one tick | `c1f69ad0...` cycled `blocked_continuation_pending` 6× first | one long same-tick chain, ~166s total span (3378.9–3545.1s), sequential pairwise-≤45s gaps | present | activity continued into the admitted winner; no new evidence for the two losers specifically | no | **no — every member decided together, same tick; nothing pre-existing** |
| **10** | 4496.7–4539.1s | `blocked_ambiguous_boundary` | `b4794fbbd5415758` (1 gen) → `ccccc865fb708216` (2 gens) → `4dea4dc46fc92563` (1 gen) | all three within the same giant 19:18:14.37–19:18:15.91 tick | `b4794fbbd...` cycled once first | part of one much larger multi-hop chain (see "Long ~310s case chronology") | present | chain kept growing (into #13/the 310s case) | no (this window) | **yes — transitively reaches admitted `visit-010`/`visit-011` (offset ~4443–4456s)** |
| **13** | 4788.2–4842.8s | `blocked_ambiguous_boundary` | `2a7b9a7af86bfa61` (2 gens), `779c963c47e5a154` (2 gens), `8a00db42523cd650` (2 gens), `6baef55e5992b214` (1 gen) — plus the 10-gen `66da7b51056242ff` bridging in from #10's own side | all four (plus the bridge) within the same giant 19:18:14.24–19:18:16.67 tick | multiple, all resolved same tick | same one giant chain as #10 | present | chain kept growing to ~5130s+ | no (this window; the encompassing bout later shows a confirmed 2-bird moment) | **yes — same transitive reach to `visit-010`/`visit-011`** |
| **15** | 5325.7–5334.8s | `blocked_ambiguous_boundary` (a `blocked_missing_evidence` sibling was contributing, non-terminal) | `e664860a50f3a7af` (1 gen), `bf5557016862f4c2` (1 gen); sibling `a61e4d03aec61b6f` (1 gen) → `blocked_missing_evidence` | all decided within 12ms, 19:21:37.89–19:21:37.90 | `a61e4d03...` cycled 4× first | smaller, likely 2–3-member local component; geometrically distinct from the same-tick `visit-015` admission (drifted-left box vs. this window's boxes) | mixed (2 ambiguous-blocked, 1 missing-evidence) | `visit-015` and a 31.9s generation (`fff6102defcb4e`) also decided same tick nearby, but geometry suggests a different, disjoint sub-component | possible (`06c6927f...`/`014e4754...` share the same offset window with adjacent, overlapping boxes) | **not determinable from the preserved ledger alone — no confirmed admitted ancestor found within the recovered window** |

**5 of 5** ambiguous-boundary misses trace to a component that either (a)
already contained a proposal admitted on a strictly earlier tick (#4, #10,
#13 — the majority, by both count and total suppressed duration), or (b)
resolved a long same-tick chain to exactly one winner, leaving an equally
plausible earlier or later part of the same chain unrepresented (#7, and
plausibly part of #15). No miss was traced to a defect distinguishable from
what v1 already investigated and declined to fix.

## Long ~310s case chronology

Encounter-period #14 (4921.0–5294.1s, ~373s) is the session's richest case:
visit-014 (4921.0–4927.1s, 6.1s) and visit-015 (5288.1–5294.1s, 6.0s) are
both admitted, but the ~310 continuous seconds between them (4948.7–5259.0s
in the report's own "recall-miss causal breakdown," containing the
11-proposal-deep cluster) received zero admission.

**Reconstructed chronologically, from the full merged ledger:**

1. **4443.3–4456.1s**: `visit-010`/`visit-011` — two genuinely simultaneous,
   geometrically distinct real subjects, sharing one Event via the accepted
   Phase-2 mechanism — both admitted (`11951f0a83116d3b`/
   `44a22c0006d48783`). Visually confirmed real (two birds in one frame).
2. **4466.5–4496.7s**: a new tracklet (`21c67cf09288eb`) forms, its own end
   (4456140ms, from the visit-011 lineage) to this tracklet's own start
   gap being 10,376ms — inside `ambiguous_gap_ms`, outside `merge_gap_ms`.
   Proposal `b4794fbbd5415758` cycles `blocked_continuation_pending` once,
   then, on a later tick (19:18:14.37 — part of the giant tick below),
   resolves `blocked_ambiguous_boundary`.
3. **4496.7–4539.1s** (recall miss #10): two further tracklets extend the
   same chain (`9df16e74c93128`+`50e672c68558f4`, then `5c89ce16010baf`),
   each geometrically compatible, each gap inside `ambiguous_gap_ms`. Both
   resulting proposals resolve `blocked_ambiguous_boundary` in the same
   giant tick.
4. **4562.2–4772.2s**: a 10-generation, ~210-second merged episode
   (`66da7b51056242ff`) forms from the same chain's continued growth,
   itself resolving `blocked_ambiguous_boundary` in the same giant tick.
5. **4788.2–4842.8s** (recall miss #13): four further proposals
   (`2a7b9a7af86bfa61`, `779c963c47e5a154`, `8a00db42523cd650`,
   `6baef55e5992b214`) extend the chain further, all resolving
   `blocked_ambiguous_boundary` in the same giant tick.
6. **4921.0–4927.1s**: `a339531ebff5b8`/`3ddba48a5d133617` — a brief (6.1s),
   distinctly-positioned tracklet (its own start box is materially
   displaced from the surrounding chain's feeder-perch cluster) admitted as
   **visit-014**, at 19:18:14.24, apparently in a *separate*, disconnected
   component from the giant chain (its own geometry does not match the
   chain's tight feeder-perch cluster closely enough to plausibly share an
   edge, though this cannot be proven from the preserved ledger alone).
7. **4929968–5130479s (the bulk of the ~310s cluster)**: at least 8 further
   proposals (`80561287f189427f`, `330ede1e76f505ba`, `2354fd0e30e500ee`,
   `153b8a95c0ca3195`, `f0b31cd3464be9d6`, `29518b2426308a8a`,
   `ffdd41a664b9967f`, plus `a5777798be1a964d`) — spanning between 1 and 6
   constituent generations each, several with strong confidence and
   substantial detection counts — **all resolve `blocked_ambiguous_
   boundary` within the identical ~2.4-second wall-clock window
   (19:18:14.24–19:18:16.67)** as steps 2–5 above. By the proven
   10-second-tick-floor argument (identical to v1's own use of it), this
   proves all of these were decided by **one single `_run_assembly_tick`
   invocation** — i.e., one arbitration pass resolving a chain (or a small
   number of chains) whose own combined temporal reach spans from
   `visit-010`/`visit-011`'s own admission (offset ~4443–4456s) through to
   at least 5130s — **roughly 674–687 seconds of transitively-connected
   graph, decided in one tick, admitting nothing beyond what was already
   admitted before that tick began.**
8. **5168.3–5227.8s**: a further, separate proposal (`73c548f2b866bf24`
   →`7234287e1b64d370`) cycles `blocked_continuation_pending` across three
   more ticks (19:18:39–19:19:28) before finally resolving `blocked_
   ambiguous_boundary` at 19:21:37 — the same session-wide pattern
   continuing past the giant tick.
9. **5209.6–5221.6s**: two more proposals (`ce72fa3371b4fdbc`,
   `3c9a56a85c73fa7e`) resolve `blocked_ambiguous_boundary` at 19:19:39.76.
10. **5288.1–5294.1s**: `cecf29d028b3e3`/`046752f30fa4107a` admitted as
    **visit-015** at 19:21:36.29 — again a distinctly-positioned tracklet
    (its own box is materially displaced left of the chain's usual
    feeder-perch cluster), in what is most plausibly its own, separate,
    small component (one direct sibling, `fff6102defcb4e`, blocked
    1.4s later — see recall miss #15).

**Answering the brief's own ten questions directly:**

1. *Did one old proposal bridge otherwise-separate later activity?* **Yes** —
   `visit-010`/`visit-011`'s own admitted lineage is the earliest node a
   chain of individually-≤45s-gapped, geometrically-compatible tracklets
   plausibly traces back to, reaching forward at least to offset ~5130s.
2. *Did transitive closure keep the component alive indefinitely?* Not
   literally indefinitely — it persisted for as long as the chain of
   individually-short gaps remained unbroken (roughly 674–687s in this
   case), ending only when an **incidental** ~38–45s pause in *newly
   -confirmed* tracklets appeared (not a genuine absence of real
   activity — a further real tracklet, `dfbc5074cf86a8`, was already
   actively forming but had not yet reached its own termination condition).
3. *Did component membership monotonically grow?* Yes — every new,
   geometrically-compatible, gap-eligible tracklet joined; nothing was
   ever removed, including after a member became terminally decided.
4. *Did resolved/terminal members remain biologically authoritative?*
   **No, and this is the core finding**: a terminal member's own status
   (admitted or permanently blocked) has no bearing on whether later,
   independently-arriving activity is the same biological encounter, yet
   it is treated as fully, unconditionally authoritative for graph
   connectivity and for the "already admitted → veto everything" dispatch
   rule.
5. *Did continuation identity outlive meaningful biological continuity?*
   Yes, in the sense that graph membership ("ambiguous-adjacent")
   persisted across a cumulative span far exceeding any single bird's
   plausible one-sitting dwell time, built entirely from a chain of
   individually-defensible ≤45s hops.
6. *Did separate later birds inherit old ambiguity?* Yes — a materially
   later, richer, sometimes-simultaneous-two-bird stretch of real activity
   (encounter-period #14's own missed 310s) inherited the unresolved
   graph membership of an ancient, already-admitted, 12-second anchor.
7. *Was there ever a point where one subset was safely separable?*
   Structurally, most likely yes at some point — but this investigation
   found no non-arbitrary, principled fact establishing *when* (see
   "Root-cause classification").
8. *Did forced decision/finalization ever run?* **No** for this specific
   giant chain — it resolved *naturally* (not forced): by the giant tick's
   own horizon (~5179.2s), every member individually cleared its own
   `continuation_pending` window (>45s past its own end), so `still_
   growing` was already `False` for the whole component without needing
   the 20-minute forced-decision escape hatch.
9. *Did dead-anchor promotion participate?* Only the **first** branch of
   `_live_chain_for_component` (the unconditional "already admitted →
   veto everything" check) — not the promotion branch, which requires no
   admitted member anywhere in the ranked order. `visit-010`/`visit-011`'s
   own admission satisfies the first branch, so promotion is never reached.
10. *Would any existing accepted lifetime already justify pruning part of
    the component?* The closest candidate is `maximum_episode_duration_ms`
    /`_MAXIMUM_COMPONENT_PENDING_MS` (20 minutes, already reused by
    "Bounded component decision horizon" for *deferral*) — but the actual
    veto here fired at only ~12 minutes' elapsed time (well under that
    bound), so reusing it for this *different* purpose would not, by
    itself, have changed this session's own observed outcome (see "First
    irreversible mechanism" and "Root-cause classification").

## Biological continuity analysis

Explicitly distinguishing the five concepts the brief names:

- **Same biological encounter**: unknowable from any preserved fact for
  most of this chain — the only ground truth available is the v14
  reviewer's own visual confirmation of "real, continuous (often
  multi-minute) bird presence" and "confirmed simultaneous 2-bird moments"
  across the broader window, not per-tracklet identity.
- **Same tracker lineage**: bounded and real — each individual
  `track_generation` is the tracker's own conservative, validated unit;
  none of this investigation's findings touch tracker association.
- **Same Event**: not applicable here (no admitted sibling relationship
  was found within this specific chain beyond the confirmed `visit-010`/
  `visit-011` pair, which already correctly shares one Event).
- **Same ambiguity component**: this is precisely the concept the defect
  lives in — a purely graph-transitive relationship, recomputed fresh
  every tick from all currently-known tracklets, with **no decay or
  expiry tied to a member's own resolution state**.
- **Same continuation chain**: `continuation_pending` is a *narrower*,
  correctly-bounded concept (a single proposal's own tail, decaying at
  exactly `ambiguous_gap_ms`=45s past its own last activity) — it is
  **not** what causes this defect; the defect is entirely in how the
  *component* (built from many individually-fine `continuation_pending`
  decisions) is treated once assembled.

**These are demonstrably not equivalent**: v14 exposes a place where
*ambiguity-component* continuity (unbounded, purely transitive, blind to
terminal state) is dramatically stronger and longer-lived than any
individual continuation-chain fact, tracker-lineage fact, or biological
plausibility warrants.

## Component evolution

Modeled through time (not at one tick), directly from the giant chain
above:

- **Members added**: continuously, every ~10–30s, for the chain's own
  ~674–687s reach — no member was ever added out of geometric/temporal
  eligibility order.
- **Members removed**: never. Not even after becoming terminally decided
  (admitted or permanently blocked).
- **Terminal members**: `visit-010`/`visit-011` (admitted, offset
  ~4443–4456s); at least 6 further proposals permanently blocked on
  earlier ticks within the chain's own span before the giant tick
  resolved the rest.
- **Live members** (at the giant tick): every proposal listed in step 7
  of the chronology above — the ones that, per this investigation, should
  most plausibly have been evaluated as new, independent, currently-active
  activity.
- **Edges added**: one per newly-confirmed tracklet, to its own temporally
  -adjacent predecessor, exactly as `classify_boundary` already computes
  (unchanged by this investigation).
- **Edges that would no longer exist if recomputed only over actionable
  state**: every edge touching `visit-010`/`visit-011`'s own already
  -admitted proposal, and every edge touching any of the intermediate,
  already-permanently-blocked proposals (steps 2–5) — i.e., most of the
  early half of the chain.
- **Authoritative winner each tick**: at the giant tick, ranked by
  `_arbitration_key` (confidence-first) across the *entire* combined
  component — this investigation could not determine, from the preserved
  ledger, which specific member ranked highest, only that **none of them
  reached `create`**, which is only possible if `visit-010`/`visit-011`
  (or some other already-admitted id) appears anywhere in that ranked
  order, triggering the unconditional veto (see "Root-cause
  classification").
- **Whether topology becomes separable later**: yes, eventually and
  incidentally — the very next tick after the giant one (once
  `dfbc5074cf86a8` itself terminates) presumably re-links the still-live
  tail into a *new* component that, this time, does **not** trace back to
  `visit-010`/`visit-011` (their own already-admitted proposal, being
  purely a fact about two specific, already-fixed generations, cannot
  gain new edges) — this is consistent with the giant chain's own
  members never being retried (each is permanently attempted, once
  decided) and with the session's own later admissions (visit-016 at
  5415.3–5445.9s) occurring without further incident.

**Proof that the implementation treats a historically-true edge as
permanently authoritative even after its member is no longer actionable**:
directly confirmed via `test_v14_case310_shaped_multihop_transitive_
chain_suppresses_a_strong_later_live_tail` (see "RED→GREEN") — a
materially stronger (confidence 0.9), 30-second live proposal, linked to
an already-admitted anchor *only* through an intermediate bridge that
itself never won anything, still receives zero admission, no matter how
many already-decided hops separate it from the original admission.

## Failure-shape classification

Not forced into one global shape, per the brief's own instruction:

- **Miss #4**: **F** (resolved/terminal member continues blocking live
  members) — a clean, minimal, 2-member instance: an already-admitted
  proposal directly (one hop) vetoes a materially stronger, later
  proposal.
- **Miss #7**: **D** (transitive closure joins temporally separated
  activity) — a same-tick chain with *no* pre-existing admitted member;
  arbitration correctly narrows an ambiguous, multiply-linked sequence to
  one winner, at the cost of an equally plausible separate real presence
  elsewhere in the same chain. Structurally identical in kind to the
  chartered v12 case (also same-tick, no stale-admission complication).
- **Miss #10 / Miss #13 / the 310s case**: **C + F** together (transitive
  closure over historical/non-actionable members, compounding a
  resolved/terminal member's continued veto reach) — the same mechanism
  as #4, but reached through several intermediate hops rather than one
  direct edge, at a much larger scale (hundreds of seconds, over a dozen
  proposals, spanning a confirmed simultaneous-two-bird stretch).
- **Miss #15**: **inconclusive from preserved evidence** — plausibly A
  (single subject, sequential mutually-ambiguous proposals) or C (two
  simultaneous real subjects genuinely ambiguous, given the adjacent,
  overlapping boxes of its two 1-generation members) — this investigation
  found no confirmed link to a prior admission for this specific miss and
  does not force a classification it cannot support.
- **No instance was classified B alone** (a stale edge with no
  compounding transitive-closure or veto-reach effect) — every reconstructed
  case involves either a direct terminal-member veto (F) or multi-hop
  chaining (C), or both.
- **No instance requires G** (component never reaches a decisive
  terminalization point) — every reconstructed component *did* reach a
  terminal decision (the giant chain resolved naturally, not by
  starvation); the defect is in *what* that decision does with a stale
  bridge, not in reaching one at all.
- **H (safe live subset exists but resolution algorithm cannot expose
  it) is the closest description of the *shape* of #4/#10/#13/the 310s
  case, but J (no trustworthy separator exists) is this investigation's
  own considered conclusion for *all five misses*** — see "Root-cause
  classification" for why the one candidate mechanism found to expose the
  live subset (excluding stale members from the graph) cannot be applied
  without contradicting an existing, adversarially-tested, deliberate
  safety decision, and why the one narrower, safe variant found is not
  proven live-reachable in this session's own real data.

## Historical safety contract

Re-traced directly against the accepted contract docs and their own
cited field evidence (unchanged by this milestone):

- **One bird, multiple Visits** (Admission Recall Investigation +
  Conditional Fix v1) — motivated bounded arbitration in the first place.
- **Transitive sequential fragmentation** (Ambiguous-Boundary Transitive
  Fragmentation Closure v1) — closed by full connected-component
  resolution (`_ambiguous_component`), which is exactly the mechanism
  this milestone's own findings live inside.
- **Concurrent sibling cross-merging** — kept structurally disjoint from
  the ambiguous-link graph entirely (unaffected by anything in this
  milestone).
- **Duplicate admissions / overlapping proposal races** — idempotency plus
  "at most one winner per connected component" together guarantee no
  component ever produces two Visits, regardless of retry, restart, or
  concurrency (unaffected).
- **Sustained-activity ambiguity** (Sustained-Activity Visit Admission
  Starvation & Stop-Finalization Correctness v1) — bounded *how long a
  still-growing component may defer*, using `maximum_episode_duration_ms`.
  Does **not** bound how long an *already-resolved* member's veto reach
  may persist — a different, unaddressed axis this milestone newly names
  (see "Existing semantic lifetime/bounds," below).
- **Candidate-authority conflicts / lost winners** (Pending-Proposal
  Evidence Preservation & Arbitration Fallback Correctness v1) — the
  fallback-chain mechanism this milestone's own findings interact with but
  do not modify.
- **Multi-subject contamination / cross-subject corroboration** — both
  remain fully preserved; nothing in this investigation reads or shares
  evidence across proposal ids, and no code was changed.

Any correction this milestone might have proposed would have to preserve
every one of these properties. None was implemented (see below), so none
is at risk.

## Existing semantic lifetime/bounds

Traced directly, per the brief's own §11:

- **Proposal viability lifetime**: `RETRYABLE_OUTCOMES = {blocked_
  continuation_pending}` — every other outcome, including `blocked_
  ambiguous_boundary`, is permanent. Confirmed unchanged and load-bearing
  throughout this investigation.
- **Generation lifetime**: tracker-owned, unaffected.
- **Continuation lifetime**: `ambiguous_gap_ms` (45,000ms) — already the
  authoritative "how long could this plausibly be the same subject" bound
  `classify_boundary` itself applies pairwise. There is no tighter
  already-existing bound to reuse instead without inventing one (same
  conclusion v1 already reached for the isolated case).
- **Event/Visit temporal contract**: `maximum_episode_duration_ms`
  (1,200,000ms/20 minutes) — bounds one episode's own span, and, via
  "Bounded component decision horizon," bounds how long a *still-growing*
  component may defer before a forced decision.
- **Stop-finalization semantics**: unaffected (session was live throughout
  the reconstructed window; no stop occurred mid-chain).
- **Dead-anchor terminality**: `admitted_proposal_ids` — an existing,
  exact, binary fact distinguishing "resolved and admitted" from "resolved
  and dead." This is the *closest* existing fact to what this milestone
  needed, and is already used, but only in the direction of an
  unconditional veto (see below).
- **Evidence recency**: `_compute_protected_evidence_ids`/the bounded
  128-entry evidence cache — orthogonal to this milestone (evidence was
  present in every reconstructed case; the misses are not evidence
  -survival misses).
- **Maximum Visit duration**: same constant as "Event/Visit temporal
  contract," above.
- **Already-resolved proposal state**: `attempted_proposal_ids` — exists,
  exact, binary, and is exactly the fact this milestone's own candidate
  mechanism would need to reuse (see "Root-cause classification").

**The one genuine, disclosed asymmetry this investigation found**: the
codebase already treats "how long may a component-level decision remain
*open*" as a bounded, calibrated question on the *deferral* side
(`maximum_component_pending_ms`, reused verbatim from `maximum_episode_
duration_ms`) — but places **no bound of any kind** on the *mirror*
question, "how long may an already-*decided* component member's veto
reach persist into the future." `engine_runtime._live_chain_for_component`
takes no `known_horizon_ms`/time parameter at all — confirmed directly
against its own signature, not merely inferred (see "RED→GREEN"). This is
a real, structural, non-arbitrary fact — but, as detailed below, it does
not by itself justify a safe fix in this milestone.

## First irreversible mechanism

For every one of the five reconstructed misses, the first irreversible
step is identical in kind to what v1 already found for the v12 case:
**`classify_boundary`'s own geometry-compatibility tolerance accepting an
ambiguous link between a new tracklet and a temporally-adjacent, already
-resolved episode** (explicitly out of scope for this milestone, per §10
and per the accepted-work freeze on geometry tuning). Once that link
exists:

- If the linked prior episode was **never admitted** (miss #7's shape):
  natural, same-tick arbitration correctly narrows the whole connected
  chain to one winner — a deterministic, intended consequence.
- If the linked prior episode (or any transitively-reachable member of its
  own component) **was already admitted** (misses #4/#10/#13's shape):
  `engine_runtime._live_chain_for_component`'s own first, unconditional
  check — "any id in the ranked order, at any rank, already admitted →
  the whole component's fate is already sealed, attempt nothing further"
  — fires, and the new, potentially far-stronger proposal falls through to
  the ordinary per-proposal path with `ambiguous_boundary_resolved=False`,
  permanently blocked.

Neither step is a dispatch bug. Both are deterministic, already-existing,
already-tested consequences of policy decisions made and adversarially
validated by the immediately-prior accepted milestone.

## Root-cause classification

**Combined C (transitive closure over historical/non-actionable members)
+ F (resolved/terminal member continues blocking live members), with the
same out-of-scope geometry-tolerance root (I/J in this and the prior
milestone's own scheme) as the ultimate cause of the *link* itself.**

Every brief-preferred correction class (§15) was checked directly against
the reconstructed evidence:

- **Remove terminally non-actionable members from future ambiguity
  authority / recompute connected components over only currently
  -actionable members**: this is the one candidate that would actually
  change miss #4's outcome. **Rejected as too broad**: applied
  unconditionally, it directly, provably contradicts an existing,
  deliberate, adversarially-tested safety decision from the immediately
  -prior accepted milestone
  (`test_a_stronger_later_arrival_never_bypasses_an_already_admitted_
  component_member`) — whose own scenario (a modest admitted anchor, a
  dramatically stronger later arrival, 20–30 real seconds apart) is
  structurally identical to miss #4 (a modest admitted anchor, a stronger
  later arrival, ~43 real seconds apart). That test's own reasoning ("is
  this new arrival really the same encounter?" is a policy question,
  never a dispatch bug) is exactly as valid today as when it was written;
  v14 supplies no new fact that resolves that specific question for a
  direct, single-hop adjacency. Overturning it unconditionally would be
  "the later arrival is stronger, so let it in" — precisely the naive,
  explicitly-rejected fix that adversarial test exists to catch, and
  precisely what the brief's own §16 forbids ("may NOT allow progress
  merely because the bird has been waiting too long").
- **Permit re-partition after a blocking bridge becomes terminal, reuse an
  existing semantic lifetime to retire stale ambiguity edges**: the only
  non-arbitrary, already-calibrated lifetime available for this purpose is
  `maximum_episode_duration_ms`/`_MAXIMUM_COMPONENT_PENDING_MS` (20
  minutes) — already used for the *deferral* side of this exact question.
  A candidate fix (exclude an already-terminal member from future
  connectivity once `known_horizon_ms` minus its own `end_offset_ms`
  exceeds this same bound) was designed and checked carefully:
  - It **would not** change either existing adversarial test's outcome
    (both anchors are only 20–30 real seconds old at the moment of the
    later arrival — far under 20 minutes).
  - It **would not** have changed any of v14's own five reconstructed
    misses' recorded outcomes either: the giant ~310s chain's own veto
    fired at only ~12 minutes' elapsed time from `visit-010`/`visit-011`'s
    own admission — already under the 20-minute bound before it
    naturally, incidentally stabilized.
  - It is therefore a genuine, disclosed structural asymmetry (see
    "Existing semantic lifetime/bounds") — **but not proven live
    -reachable in this project's own real field data**, unlike v1's own
    dead-anchor-promotion fix, which *was* proven live-reachable in the
    same session it was found in. Per this project's own established
    discipline (fix what is proven live-reachable; disclose, do not
    speculatively harden, what is not), **this candidate was not
    implemented**.
- **Force resolution at an already-established semantic finalization
  point**: already happens (the giant chain *did* reach a natural
  decision) — the defect is not in *reaching* a decision, but in what that
  decision's own veto check does once reached.
- **Expose a deterministic live subcomponent after historical bridge
  removal**: this is what the rejected first candidate would have done;
  see above for why it is unsafe to do unconditionally.

**Conclusion: J — no trustworthy separator exists** for the actual,
evidenced shape of any of the five reconstructed misses, using only
currently-existing, non-arbitrary facts. This is not a failure to look
hard enough: the one candidate mechanism that would help is proven, by
direct code execution against the real, unmodified dispatch path, to be
either unsafe (unconditional exclusion) or ineffective for this session's
own actual numbers (time-bounded exclusion). The prior v1 conclusion is
reconfirmed, not contradicted, at materially greater scale and rigor.

## Locked implementation contract

**None locked; no implementation follows.** Per §14 of the brief ("If K:
do not implement"; "Classification B can be the correct milestone
result"), and consistent with the reasoning immediately above, this
milestone's own conclusion is that no safe, non-arbitrary implementation
contract can be written for the evidenced mechanism without either (a)
reopening a deliberately, adversarially-tested precision safeguard, or (b)
shipping a defensive structural change with zero proof it is live
-reachable in this project's own real field data.

## Implementation

**None. Zero production code changed.** Confirmed via `git status
--short` / `git diff --stat` against `src/mockingbird/`: no file under
`src/` differs from accepted HEAD.

## RED→GREEN

Not a fix RED→GREEN (none was implemented) — a **confirming** RED→GREEN,
in the same spirit as v1's own `test_v12_case_a_shaped_loss_is_unaffected_
by_this_fix`: three new, additive tests in `tests/test_engine_runtime.py`,
executed directly against the real, unmodified `_EngineSession._run_
assembly_tick`/`resolve_ambiguous_boundary_arbitration`/`_live_chain_for_
component` call path (never merely asserted from reading source), each
reproducing one of the reconstructed v14 shapes using the session's own
real numbers where preserved:

| test | shape reproduced | result |
|---|---|---|
| `test_v14_miss4_shaped_stronger_later_arrival_still_blocks_behind_admitted_anchor` | miss #4: a materially stronger, longer, later proposal (real confidence 0.813, 2 gens, ~45.3s) vs. an already-admitted, weaker anchor (real confidence 0.787, 1 gen, ~42.9s earlier gap) | **PASSED** — `candidates_created` stays `1`; the stronger proposal receives `blocked_ambiguous_boundary`, unsuffixed |
| `test_v14_miss7_shaped_same_tick_transitive_bridge_admits_only_one_of_two_plausible_encounters` | miss #7: a same-tick chain of three sequentially-≤45s-gapped tracklets (no pre-existing admission) | **PASSED** — exactly one Visit created; the earlier two proposals both permanently blocked |
| `test_v14_case310_shaped_multihop_transitive_chain_suppresses_a_strong_later_live_tail` | the ~310s case / misses #10 and #13: an early, tiny, admitted anchor; an intermediate, never-admitted bridge; a materially stronger (confidence 0.9), 30-second live tail linked *only* transitively through the dead bridge | **PASSED** — `candidates_created` stays `1` (the tiny original anchor only); the strong live tail receives zero admission. A structural assertion (`inspect.signature(_live_chain_for_component)`) directly confirms the function takes no time/horizon parameter of any kind, proving the "no bound on veto reach" asymmetry is a real, inspectable code fact, not an inference |

All three passed on first execution against the real, unmodified
production code — independently, directly confirming this investigation's
own root-cause analysis at the level of actual dispatch behavior, not only
documentation/contract reading.

## Same-tick ambiguity control

Preserved, unconditionally: zero lines of `resolve_ambiguous_boundary_
arbitration`, `_ambiguous_component`, `classify_boundary`, or `assemble_
visit_episodes` were touched. `test_v14_miss7_shaped_same_tick_transitive_
bridge_admits_only_one_of_two_plausible_encounters` (new) directly
confirms two genuinely ambiguous, same-tick sibling proposals still
resolve to exactly one winner, unchanged.

## Fragmentation controls

Re-run unmodified, all green (see "Tier 2"): `test_visit_episode_
assembler.py` (component/link formation), `test_candidate_visit_
authority.py`'s own transitive-chain/component tests, `test_fragmentation_
accounting.py`. No production line changed in any file these tests cover.

## Multi-subject controls

Re-run unmodified, all green (see "Tier 2"): `test_candidate_visit_
adapter.py` (concurrent-sibling Event reuse), `test_multi_camera_
concurrent_runtime.py`. The pre-existing `test_two_independent_dead_
anchored_components_rescue_independently` (unmodified) continues to pass,
confirming two genuinely simultaneous subjects, each linked only to its
own past dead (never-admitted) anchor, still rescue independently — a
different, already-correct mechanism this investigation does not touch.

## Precision controls

Re-run unmodified, all green (see "Tier 2"): `test_hard_negative_visit_
admission_precision_v1.py`, `test_human_background_admission_hard_
negative_2026_08_20.py`, `test_independent_corroboration_value_
persistent_confusor_v1.py`, `test_scene_confusor.py`/`test_scene_confusor_
repository.py`, `test_strong_confidence_non_target_scene_artifact_v1.py`,
`test_strong_confidence_subject_evidence_viability_v1.py`. Ambiguity
resolution was not touched and cannot have become an alternate admission
bypass, since nothing about it changed.

## Dead-anchor interaction

The accepted dead-anchor-promotion fix (Ambiguous-Boundary Real-Subject
Recall Correctness v1) is frozen and entirely unmodified. This
investigation's own findings sit in the **other** branch of the identical
dispatch function (`_live_chain_for_component`): dead-anchor promotion
fires when **no** component member was ever admitted (the live subsequence
of the ranked order is walked); this milestone's own reconstructed misses
fire the **first**, unconditional branch (some member **was** admitted, so
nothing is attempted at all). The two are structurally adjacent but
distinct, and this investigation keeps that distinction explicit
throughout (see "Root-cause classification," "Component evolution"). No
direct dependency was found that would require touching the accepted fix.

## Diagnostics

None added — no production code changed, so no new field is needed to
observe anything differently in a live session. The three new tests
themselves are the durable, reusable diagnostic artifact for any future
milestone that revisits this exact mechanism (a future session can extend
them directly rather than re-deriving the reconstruction from raw ledger
data again).

## Real-hardware smoke

**Judged unnecessary; not run.** Zero production code changed — there is
nothing for a live Camera Node session to validate that Tier 1/2 (both
executing the real, unmodified `_EngineSession`/`ProductRepository`/real
SQLite path) do not already cover more directly and more repeatably.
Camera Node evidence-capture and ledger-reconciliation tooling remain
untouched, per the brief's own freeze (§23), and were not re-validated
here — v14 itself is their live field proof of record.

## Tier 1

Focused reproduction: **3 new tests, all passing on first execution**
against the real, unmodified dispatch path (see "RED→GREEN"). Full
`tests/test_engine_runtime.py`: **121 passed, 0 failed** (118 pre-existing
plus the 3 new, all pre-existing assertions unchanged).

## Tier 2

Every directly-affected observation/arbitration/Visit-assembly/precision/
multi-subject subsystem file, run together (the same file list v1's own
report used, re-verified to still exist):

```
tests/test_candidate_visit_authority.py
tests/test_candidate_visit_authority_acceptance.py
tests/test_candidate_visit_adapter.py
tests/test_candidate_visit_repository.py
tests/test_candidate_visit_review_workflow.py
tests/test_candidate_visit_rollback.py
tests/test_concurrent_candidate_visit_persistence_reliability.py
tests/test_visit_episode_assembler.py
tests/test_hard_negative_visit_admission_precision_v1.py
tests/test_human_background_admission_hard_negative_2026_08_20.py
tests/test_independent_corroboration_value_persistent_confusor_v1.py
tests/test_scene_confusor.py
tests/test_scene_confusor_repository.py
tests/test_strong_confidence_non_target_scene_artifact_v1.py
tests/test_strong_confidence_subject_evidence_viability_v1.py
tests/test_observation_evidence_scoring.py
tests/test_candidate_quality_gate.py
tests/test_same_frame_species_evidence.py
tests/test_visit_classifier_supporting_evidence.py
tests/test_effective_primary.py
tests/test_fragmentation_accounting.py
tests/test_dashboard_detector_health_honesty.py
tests/test_dashboard_observation_engine_truth.py
tests/test_unified_observation_status.py
tests/test_multi_camera_concurrent_runtime.py
```

**Result: 461 passed, 0 failed (102.74s)** — combined with Tier 1
(`test_engine_runtime.py`, 121 passed): **582 tests passed, 0 failed**
across every subsystem this investigation could plausibly touch (matching
v1's own identical 461-passed Tier 2 count for the same file list,
confirming no regression was introduced by this milestone's own
additive-only tests).

## Tier 3

**Not run — judged unnecessary and explained, not skipped by default.**
Zero production code changed anywhere in the diff (`git diff --stat`
against `src/` is empty); the entire change is two new files' worth of
content: one report (this file) and one additive test section. Tier 1 and
Tier 2 already directly exercise the real, unmodified `_EngineSession`/
`resolve_ambiguous_boundary_arbitration`/`_live_chain_for_component`/
`ProductRepository` call path through real SQLite transactions — the
identical call path any Tier-3 Core run would also exercise, just via a
narrower, more targeted, and more repeatable route. Running the full
~4,500+-test Core suite for a milestone that changed zero production
source lines would be ceremony, not evidence, per this project's own
established practice for classification-B, investigation-only milestones
(see, for direct precedent, Strong-Confidence Subject-Evidence Viability
& Scene-Artifact Abstention v1: "Tier 3 (full Core) deliberately not run,
per the brief's own explicit instruction not to run it for ceremony when
a milestone concludes investigation-only with no production change").

## Lint

`ruff check tests/test_engine_runtime.py`: 2 findings, both confirmed
**pre-existing**, not introduced by this milestone's own 271-line,
append-only addition — verified directly via `git stash` isolation
(identical findings, same line numbers 13/255, against the clean,
unmodified accepted-HEAD version of the file). Zero new findings from this
milestone's own diff.

## Residual risk

- **The ambiguous-boundary sustained/crowded recall limitation remains
  fully open and unfixed.** Recall under real sustained/crowded activity
  (v14: 64.7%) is not improved by this milestone in any way.
- **The one genuinely new structural fact this investigation surfaced —
  an already-admitted component member's veto reach has no time bound,
  unlike the symmetric "still growing" deferral, which is bounded at 20
  minutes — is disclosed but not fixed.** A future milestone with
  concrete evidence of this specific asymmetry actually firing in a real
  session (e.g., a component remaining veto-active for longer than 20
  minutes) would have a stronger evidentiary basis to implement the
  narrow, time-bounded variant this investigation designed but did not
  ship.
- **Component topology for four of the five reconstructed misses (#10,
  #13, #15, and most of the ~310s case) is inferred, not directly
  recovered** — `ambiguous_adjacent_proposal_ids` is not a field the
  counterfactual ledger persists, the same disclosed gap v1 already found
  for the v12 session. A future milestone wanting exact edge-level
  certainty would need to add bounded, replay/debug-only diagnostics
  (per the brief's own §24 guidance) *before* the next field session, not
  after.
- **Miss #15's own shape could not be confidently classified** from
  preserved evidence alone — disclosed as inconclusive, not forced into a
  answer the evidence does not support.
- **`candidate_visit_authority_cli.py`'s own separate, bounded engineering
  -trial tick remains a known, pre-existing, unrelated divergence** (noted
  by v1, re-confirmed unchanged here, still out of scope: the real
  production `engine_runtime.py` path is where every reconstructed v14
  miss actually lives).

## Gate A effect

This milestone does **not** close Gate A.

- **Ambiguous-boundary sustained/crowded recall limitation: remains
  OPEN / ACCEPTED PRODUCT LIMITATION CANDIDATE FOR RELEASE-BUDGET
  DECISION.** Not silently converted into acceptance of 64.7% recall —
  that would require an explicit global budget/release review, which this
  milestone does not perform and does not authorize.
- Recall remains: **MORE EVIDENCE REQUIRED / WAITING FOR FIELD RE-PROOF**
  for a numeric budget, unchanged in substance from v14's own disposition.
- The v12 ~37:12 case itself remains exactly as it was: **OPEN / NO SAFE
  CORRECTION ESTABLISHED**, untouched.
- Gate A's remaining dependency list (items (1), (3), (5)-(11), (13) from
  v14's own accounting) is **unchanged in substance** by this milestone.
  This milestone adds one new, disclosed, not-yet-implemented candidate
  fact (the time-bounded veto-reach asymmetry) for a future session's own
  judgment, exactly mirroring how v1 disclosed the CLI-tool divergence it
  found but did not fix.

## Decision

**B**

A rigorous, full reconstruction of all five v14 ambiguous-boundary
recall misses and the ~310-second sustained/crowded case was completed
directly from the preserved real-session ledger (22,260 raw detections,
218 track generations, 191 proposal-outcome events), cross-checked against
the accepted contract docs and, for the load-bearing dispatch claims,
against direct execution of the real, unmodified production code via
three new, additive, all-green tests. The investigation confirms, with
materially greater depth and scale than the prior chartered v12 case could
provide, that the same already-identified, already-accepted mechanism
(`classify_boundary`'s out-of-scope geometry tolerance forming an
ambiguous link, followed by `_live_chain_for_component`'s deliberate,
adversarially-tested "any admitted member anywhere in the component vetoes
everything, unconditionally" policy) is the dominant cause. One genuine,
new, principled structural fact was found — an asymmetry in how long a
component-level decision may stay "open" on the deferral side versus the
veto-reach side — but it does not, by direct calculation against this
session's own real numbers, change any of the five misses' recorded
outcomes, and is not proven live-reachable in this project's own field
data. Per this project's own established discipline (fix what is proven
live-reachable; do not speculatively hardened an unobserved edge, and do
not overturn an adversarially-tested safety decision without a new fact
that actually resolves the question it protects), no production code was
changed. Zero regression risk: Tier 1 (121 passed) and Tier 2 (see above)
both fully green, no fragmentation/multi-subject/precision control
weakened in any way.
