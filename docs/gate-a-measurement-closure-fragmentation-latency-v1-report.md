# Gate A Measurement Closure v1 — Fragmentation Accounting & True User-Visible Latency Instrumentation

RELEASE-CRITICAL MEASUREMENT / ACCEPTANCE-ENABLEMENT milestone. Does not tune
models, does not change Visit grouping semantics, does not run a wildlife
field cohort, does not accept a release budget. Closes the two measurement
gaps Representative Daylight Gate A Field Acceptance v7 left open (see
[release-execution-state.md](release-execution-state.md) §6.R "Remaining
Gate A dependency," items 1 and 3): a directly-comparable fragmentation-rate
methodology, and a true capture-to-visible latency definition.

## Starting state

Verified before touching anything: branch `main`, HEAD `a5cf039` (matches
git; `release-execution-state.md`'s own §1 "Accepted HEAD" field names
`5351e08`, the last report-bearing commit before the reconciliation commit
`a5cf039` itself — the doc's own established convention throughout,
consistent with every other reconciliation entry in that file, not a
discrepancy). Schema `v58`, unchanged by this milestone (no migration; see
"Instrumentation," below, for why). Latest accepted milestone: Representative
Daylight Gate A Field Acceptance v7. Gate A/Lane R: open. Authorization:
NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED. The seven preserved
untracked detector files were present, untouched at the start (confirmed by
byte size, `git log --all` showing zero history for any of them) and remain
byte-identical at the end (re-verified after this milestone's own work,
including one `git stash push -u`/`pop` round-trip used for a ruff-baseline
comparison, below — that round-trip changed their mtimes but not their
bytes, confirmed by exact size match before/after; disclosed rather than
silently noted, and a `git stash push` **without** `-u` is the safer choice
for any future ruff-baseline check in this repository, since none of this
milestone's own tracked-file edits ever touched those seven files anyway).
No active writer process was found in this working tree.

## Fragmentation problem

**Investigation (per this milestone's own §5), answered:**

1. **Canonical denominator unit.** Doctrinally, a *genuine encounter*,
   established by *independent human review, before opening the product's
   own Visit list* —
   [independent-encounter-denominator-design.md](independent-encounter-denominator-design.md)
   and
   [detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
   already say so explicitly, and two prior accepted reports
   ([visit-authority-budget-recall-closure-v1-report.md](visit-authority-budget-recall-closure-v1-report.md),
   [scene-confusor-suppression-v1-report.md](scene-confusor-suppression-v1-report.md))
   already correctly labeled `encounter_accounting.cluster_encounters`'s own
   output "explicitly not the denominator." That module's own docstring
   agrees with itself: `total_encounter_clusters` is "an evidence-based,
   disclosed *reconstruction*... never the 'genuine visible encounter'
   ground truth itself."
2. It is **not** Event, Visit, or a raw proposal-graph component — it is an
   independently-reviewed activity segment. `cluster_encounters`'s own
   `EncounterCluster` is the closest *machine-reconstructed suggestion* of
   one, never the thing itself.
3. **How sustained activity is grouped today:** `cluster_encounters`
   (`src/mockingbird/observation/encounter_accounting.py:169-236`)
   transitively (union-find) chains track generations whenever consecutive
   generations share a `broad_class`, don't temporally overlap, and sit
   within `VisitAssemblyConfiguration.ambiguous_gap_ms` (45,000ms,
   `visit_episode_assembler.py:389`) of each other with compatible geometry
   — the assembler's own tolerance formula, deliberately reused rather than
   reinvented, but applied *transitively* (a chain of pairwise-compatible
   generations joins one cluster even when the first and last are not
   themselves compatible), unlike the assembler's own bounded per-episode
   scope.
4. **Why v7 needed a correction, reproduced directly** (see "Pre-fix RED,"
   below): under real, sustained, near-continuous feeder activity, that
   transitive chaining produces very large multi-Visit mega-clusters — v7's
   own report measured one spanning 26.9 minutes and 65 distinct proposals.
   The raw `EncounterFunnelReport.duplicate_visit_cluster_count` field
   (`len(cluster.admitted_visit_ids) > 1`) then fires on this shape even
   when every admitted Visit inside it represents a genuinely separate real
   encounter with disjoint tracker evidence — v7 manually traced two of its
   own flagged "duplicate" clusters and confirmed exactly this. (A second,
   distinct field, `fragmented_cluster_count`
   [`len(cluster.generation_ids) > 1`], is a *track-generation*-level
   diagnostic the module's own docstring already warns must not be
   conflated with encounter count; `run_encounter_accounting.py`'s own CLI
   output already labels it correctly, "`(>1 track generation)`" — that
   field was never the actual source of v7's confusion. The genuinely
   ambiguous raw signal is `duplicate_visit_cluster_count`.)
5. **Can one algorithm support both shapes?** Not via threshold-tuning
   alone (this milestone's own §9 explicitly forbids inventing "one magic
   gap threshold"). Yes, via two layers: keep `cluster_encounters`
   completely unmodified as a *suggestion* layer (correct for sparse
   cases, already proven across four real cohorts); add a new,
   human-correctable *disposition* layer on top that never trusts a raw
   multi-Visit cluster signal by itself.
6. **What must stay human-reviewed:** whether a cluster with two or more
   admitted Visits and no shared tracker evidence represents one genuine
   activity wrongly split, or several genuinely separate real encounters
   close together in time. `cluster_encounters` cannot decide this (by
   design — it deliberately over-includes), and neither should a second
   heuristic that merely picks a different threshold.

## Fragmentation truth contract

New module: [`fragmentation_accounting.py`](../src/mockingbird/observation/fragmentation_accounting.py)
(350 lines), pure (no filesystem/network/CUDA/SQLAlchemy/product-repository
import, structurally enforced by its own test), mirroring every sibling
Stage 6.x/7 decision module's conventions.

**`DenominatorUnit`** — the durable representation this milestone's own §8
asked for: `denominator_unit_id`, `start_offset_ms`/`end_offset_ms`,
`admitted_visit_ids`, `disposition`
(`correctly_represented`/`fragmented`/`duplicate`/`merged`/`missed`/`ambiguous`),
`denominator_confidence` (`confident`/`reviewed`/`ambiguous`),
`subject_count` (only ever from independent review, never guessed),
`reviewer_note`, `evidence_pointer`, `auto_signals` (the raw facts a
disposition was decided from, kept for audit). A `reviewed` unit's
`__post_init__` **raises** if `reviewer_note` is empty — there is no code
path that silently promotes a guess into reviewed truth.

**`build_denominator_units(clusters, proposal_outcomes, *, visit_event_ids=None)`**
seeds one unit per `EncounterCluster` that produced ≥1 admitted Visit (a
zero-Visit cluster is a *recall* question, already tracked separately, and
is out of scope for fragmentation — never silently folded in as `missed`)
and auto-classifies:

- ≤1 admitted Visit → `correctly_represented`, `confident` (nothing to
  fragment against).
- Any pair of admitted Visits sharing a `constituent_generation_ids` element
  → `duplicate`, `confident` — the same zero-shared-evidence test v7's own
  report already established as its "strongest, most direct" signal,
  reused here as a first-class disposition rather than a one-off manual
  check.
- All admitted Visits sharing exactly one Event id (an optional
  `visit_event_ids` cross-reference, e.g. from a `GET /api/visits` export)
  with no shared evidence → `correctly_represented`, `confident` — Multi
  -Subject Visit Assembly Phase 2's own already-accepted "simultaneous
  subjects share one Event" signature, reused, never reinvented. Requires
  *every* admitted Visit in the unit to resolve to the *same* Event id;
  partial or conflicting Event info never triggers this path (tested).
- Everything else → `ambiguous`, `ambiguous` — deliberately never guessed.

**`apply_reviewer_dispositions`/`ReviewerDisposition`/`reviewer_denominator_unit`**
are the only way an `ambiguous` unit (or a wrong auto-classification)
becomes `fragmented`/`correctly_represented`/`duplicate`/`merged`/`missed`
with `denominator_confidence="reviewed"` — every override requires a
non-empty note; an override naming an unknown unit id raises rather than
being silently dropped. `reviewer_denominator_unit` additionally lets a
human author a `missed` or `merged` unit directly, from independent review,
for the two dispositions structurally outside any single cluster's own
scope.

**`build_fragmentation_accounting_report`** computes
`fragmentation_rate = fragmented / (correctly_represented + fragmented)`
(the `{"state": ..., "value": ...}` convention `encounter_accounting._rate`
already established, duplicated rather than imported, matching this
package's own "self-contained pure module" precedent) — `duplicate`,
`merged`, `missed`, and `ambiguous` units are counted for transparency but
never dilute this rate's own numerator or denominator, per this milestone's
own §22.

## Pre-fix RED

`tests/test_fragmentation_accounting.py::test_red_naive_duplicate_cluster_signal_wrongly_reads_as_a_defect_for_sustained_activity`
reproduces v7's own disclosed problem directly, deterministically, on a
fixture scaled down from its real shape (four genuinely separate real
visits ~25s apart, disjoint evidence): running the accepted, unmodified
`cluster_encounters`/`build_encounter_funnel_report` against it shows
`duplicate_visit_cluster_count == 1` — the exact wrong "fragmentation/
duplication defect" reading a naive consumer of that raw signal would
reach, when ground truth is four correctly-represented encounters. The very
next test,
`test_green_corrected_accounting_marks_sustained_activity_ambiguous_not_fragmented_or_duplicate`,
proves the corrected accounting never makes that mistake on the identical
fixture (honestly `ambiguous`, not `fragmented`/`duplicate`), and a third
proves the reviewer path can still confirm a *real* fragmentation defect on
the identical shape when a human genuinely finds one
(`test_sustained_over_fragmentation_reviewer_can_confirm_a_real_defect_too`).

## Corrected accounting

Every case in this milestone's own §10 is a dedicated, deterministic test
in `tests/test_fragmentation_accounting.py` (13 tests): sparse/not
fragmented; sparse fragmented (ambiguous until reviewed, then correctly
`fragmented`); two genuine sequential encounters at large separation
(auto-confident, two separate clusters, no review needed at all — gap
exceeds `ambiguous_gap_ms` so `cluster_encounters` itself never chains
them); sustained activity RED→GREEN pair (above) plus its
over-fragmentation mirror; simultaneous siblings sharing one Event
(auto-confident `correctly_represented`) and the negative case (different
Event ids never falsely trigger that signal — stays `ambiguous`); duplicate
(shared evidence, `confident`, distinct rate treatment from `fragmented`);
ambiguous excluded from the rate denominator; reviewer-authored `missed`
units and the empty-note-raises safety check; an unknown-unit-id override
correctly raising rather than silently dropping.

## Existing-cohort reanalysis

Reran the corrected accounting — via the new combined CLI,
[`scripts/run_gate_a_measurement_accounting.py`](../scripts/run_gate_a_measurement_accounting.py)
— against every cohort with preserved raw ledger evidence actually
recoverable. **Honest disclosure of where that evidence came from:**
`data/field-acceptance/` (this repository's own established, gitignored
-but-present convention for field-acceptance raw evidence) has real,
in-repo data only for the 2026-08-19 primary/full-funnel cohort. v5/v6/v7's
own raw counterfactual-ledger evidence was never archived there — a real
tooling-hygiene gap, disclosed below under "Defects discovered" — but v6's
and v7's own raw ledger snapshots (the exact "already-preserved merged
ledger" v7's own report names) were still present, unmodified, on this
local machine's filesystem, in the ephemeral working directories the
original field sessions used. Verified lossless/genuine before use (v7:
merged reconstruction's own final counts — 25 admitted, 192 distinct
proposals from 403 cumulative records, 89.4-minute span, first/last frame
timestamps — match the accepted v7 report exactly; v6: `v6_counterfactual_
final.json`'s own filename/session shape matches the accepted v6 report).
Archived into `data/field-acceptance/2026-08-31-gate-a-{v6,v7}-measurement
-closure-reanalysis/` (each with its own `PROVENANCE.md` disclosing exactly
this) so future sessions no longer depend on that scratchpad surviving. v5
published its own fragmentation figure from full manual review, without
`cluster_encounters`; no raw ledger for it is recoverable, so it is
reported as-published, not recomputed.

| Cohort | Denominator units (with ≥1 admitted Visit) | Confidently/reviewedly resolved | Fragmented | Ambiguous (honest residual) | Rate |
|---|---|---|---|---|---|
| 2026-08-19 (primary full-funnel) | 8 | 5 auto-confident + 2 reviewer-sourced = 7 | 0 | 1 (reviewer-*confirmed* still-ambiguous, not merely unresolved) | 0% (7/(7+0)) |
| v5 (2026-08-30) | 18-19 (full manual review, not this tool) | ~18/19 | 0 confirmed | ≤1 | 0%, ≤5.6% if the ambiguous pair counts |
| v6 (2026-08-31 AM) | 0 | — | — | — | undefined (0 admitted Visits) |
| v7 (2026-08-31 PM) | 10 | 5 auto-confident + 2 reviewer-sourced = 7 | 0 | 3 (1 reviewer-*confirmed* still-ambiguous; 2 genuinely unreviewed) | 0% (7/(7+0)) |

**How the reviewer overrides were sourced (never invented):**

- **2026-08-19**, two of its own three ambiguous units resolved using that
  cohort's own already-existing, already-accepted
  `data/field-acceptance/2026-08-19-end-to-end-recall-closure/independent
  -encounter-table.md` — a genuine independent human review, done *before*
  the product's own Visit list was consulted, for a different purpose
  (recall). Rows #9/#10 and #17/#18 independently describe geometrically/
  temporally distinct real encounters for what this tool's own
  auto-classifier could only call `ambiguous`; the third unit maps onto row
  #8, where the *original* independent reviewer *already* concluded the
  window is "a real, bounded source of count uncertainty rather than
  resolved by assumption" — so that unit is overridden to `ambiguous` too,
  turning an unreviewed default into a reviewer-*confirmed* one.
- **v7**, two of its own five ambiguous units resolved using the v7
  report's own accepted "Multi-subject" section (the two directly
  -visually-confirmed genuine concurrent-sibling pairs,
  `visit-observation-candidate-011`/`-013` and `-019`/`-020`). The
  remaining three units (the sustained mega-cluster the v7 report itself
  already called "honestly ambiguous... does not have a single correct
  granularity," plus one small unreviewed pair) are left genuinely
  ambiguous — not forced to a disposition no evidence supports.

**Cross-check, never fabricated:** every reviewer override cites the exact
source document/row it came from as `evidence_pointer`; nothing in this
table was decided by re-inspecting raw imagery myself. Full outputs
(denominator units, `auto_signals`, dispositions applied) are archived
under `data/field-acceptance/2026-08-19-end-to-end-recall-closure/gate-a
-measurement-closure-v1-reanalysis/` and the two new `2026-08-31-gate-a-*`
directories.

## Latency problem

Every prior cohort measured "activity-end (`end_offset_ms`) → arbitration
decision (`decided_at`)" — v6's own metric, reused verbatim by v7. That is
proposal-*resolution* latency: it starts from the activity's own *last*
frame, already inside the assembler's output, never from the real-world
moment a bird was first captured — a materially smaller number than
capture-to-visible latency, and both prior cohorts' own reports already
disclosed this as a limitation, never presented as the real thing.

## T0-T5 timeline

Traced directly in code (not assumed), independently cross-verified by a
second reading:

| Stage | Existed before this milestone? | Value | Clock domain |
|---|---|---|---|
| T0 (source capture) | Only at the *raw-detection* ledger level (`RawDetectionRecord.captured_at`) and, further upstream, on every `TrackUpdate.captured_at` (already a *required* field — never read forward past track-generation construction until now) | New: `TrackGenerationRecord.start_captured_at`/`end_captured_at` | Node (Camera Node's own OS clock) |
| T1 (proposal creation) | No — `AssembledVisitProposal` carries only source-relative offsets, by design (the assembler is a pure, wall-clock-free module) | Does not exist; not added (see "Instrumentation") | — |
| T2 (arbitration decision) | No — `resolve_ambiguous_boundary_arbitration` is pure, offset-only, no wall clock | Collapses into `decided_at` (below) | — |
| T3 (candidate admission) | Yes, as one value | `ProposalOutcomeRecord.decided_at` — one `datetime.now(UTC)` read in `engine_runtime.py`'s own `_attempt()` closure, reused for T2/T3 both | Host |
| T4 (Visit persistence commit) | Yes, but stamped *before* the transaction actually commits | Same T3 value, written onto `EventModel.started_at`/`ended_at` and `ObservationCandidateVisitModel.created_at` | Host |
| T5 (query-visible) | Not instrumented; now *proven* | ≡ T4 (see "Visibility boundary") | Host |

## Clock-domain analysis

T0 is Node-domain; T3/T4/decided_at are Host-domain.
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)
"Clock-drift disposition" already documents this exact boundary:
`node_to_host_clock_offset_ms` is computed per delivered frame but never
surfaced downstream, and "analysis-to-host clock alignment is uncertain
unless externally synchronized" — no NTP guarantee exists anywhere for the
Camera Node (`mockingbird-doctor-operational-health-contract.md` explicitly
disclaims validating clock *correctness*, only readability). Every prior
shipped comparison in this codebase deliberately stays single-domain; this
milestone's own new latency figure is the first to cross it, and does so
*disclosed*: every `LatencySample` carries an explicit
`clock_domain_caveat` string rather than presenting the subtraction as an
unqualified fact.

**Real, empirically-found evidence this boundary matters, not merely
theoretical:** cross-referencing v7's own real preserved raw-detection
records, `source_offset_ms` (the offset domain every ledger record uses)
drifts against real wall-clock `captured_at` by up to **~39 seconds over
the 89.4-minute session** (0% at session start, growing to ~0.7% relative
drift by the end) — consistent with the report's own disclosed "mean
interval 1,395ms against the configured 1,000ms nominal" processing
overhead. This is exactly why T0 is read from a genuine per-record
wall-clock field (`start_captured_at`), never derived by adding an offset
delta to a session-start epoch.

**Regression coverage:** `tests/test_capture_to_visible_latency.py`
guards negative latency (`invalid_negative`, never a real negative number),
implausibly large gaps (`implausible`, a wall/monotonic-mix-shaped safety
backstop), and missing capture time (`unavailable_capture_time`, never a
fabricated estimate) — all three states are counted separately from
`measured` in every summary, never silently averaged in.
`tests/test_counterfactual_lineage.py` additionally checks the new
per-generation `end_captured_at > start_captured_at` and wall-clock-span-
matches-offset-delta invariants within one continuous session (the one
domain where that equivalence is actually expected to hold).

## Visibility boundary

Traced `ProductRepository.list_visits()` and `GET /api/visits`
(`api/main.py`) directly: a plain, synchronous SQLAlchemy query against a
fresh session, no cache, no materialized view, no async index, no poll
cycle between commit and read — both the write path
(`create_candidate_visit_from_proposal`) and the read path share one
process-wide repository/engine. **Proven, not merely traced:** new test
`tests/test_candidate_visit_repository.py::
test_a_freshly_created_candidate_visit_is_immediately_query_visible_through_the_same_repository_read_path`
creates a candidate Visit and calls `list_visits()` in the very next line,
asserting it is present — a live, checked assumption that would fail if a
future change introduced a real T4→T5 gap, not a one-time claim. T5 is
therefore treated as identical to T4 in this codebase's current design, and
no separate T5 instrumentation was added.

**Separately documented, never folded into this figure:** the only
Visit-adjacent frontend auto-refresh anywhere in `web/src` is the Today
dashboard's own 30-second poll (`DASHBOARD_REFRESH_INTERVAL_MS`,
`DashboardPage.tsx`); Bird Log/Activity Library/per-stream views are
fetch-on-mount/filter-change only, no polling. Per this milestone's own
§17, this is backend/product availability latency, not UI polling/render
latency, and is reported here only as a separately-disclosed fact, never
summed into the T0→T5 number.

## Instrumentation

New module: [`capture_to_visible_latency.py`](../src/mockingbird/observation/capture_to_visible_latency.py)
(254 lines), pure, computing **T0 → `decided_at`** as the best-available
direct proxy for T0 → T5 in the current architecture (T2/T3/T4/T5 all
already collapse into `decided_at`, proven above) — a materially different,
and correctly *larger*, number than every prior cohort's own proxy, because
it starts from true first capture instead of the activity's own last frame.
States this substitution explicitly in its own module docstring and on
every sample, rather than silently relabeling the old metric.

**The one production-code change**, chosen to be the smallest that closes
the actual gap: `TrackGenerationRecord` gains `start_captured_at`/
`end_captured_at: datetime | None = None`
(`counterfactual_lineage.py:181-227`), populated in `_track_generation_
record()` from `first.captured_at`/`terminal.captured_at` — **values
already in scope on the two `TrackUpdate`s that function already reads**,
never a new wall-clock read, never new I/O, never a new control-flow path.
Additive/optional, so every existing call site (tests, `run_encounter_
accounting.py`'s own dict-parser) stays valid unchanged — verified: every
`TrackGenerationRecord(...)` construction site in this repository uses
keyword arguments (grepped, six sites total). Propagated one layer further
through `api/schemas.py`'s `CounterfactualTrackGenerationResponse` and
`api/main.py`'s `_counterfactual_window_response()` so a *future* field
session's own saved JSON actually carries it (§16 "available to field
acceptance tooling") — otherwise this would only ever help an in-process
Python caller, never real field-acceptance tooling.

**T1/T2 deliberately not added.** `visit_episode_assembler.py`/
`candidate_visit_authority.py` are pure, wall-clock-free *by explicit,
repeatedly-stated design* ("never reads a wall clock... itself," their own
docstrings). Adding a timestamp read there would cross an intentional
architectural boundary for a number this milestone does not need (T3
already collapses T2 into one value) — not done.

No schema/migration: everything above is either an additive dataclass
field with a default, an additive optional API-response field, or a brand
new pure module/script. Schema stays `v58`.

**One real, pre-existing bug found and fixed**, exposed (not introduced) by
this milestone's own new consumer: `run_encounter_accounting.py`'s
`_proposal_outcome_from_dict` set `decided_at=data.get("decided_at")` —
the raw JSON *string*, never parsed into a `datetime`. Harmless before
(`cluster_encounters` only ever does arithmetic on `decided_at_offset_ms`,
an int), but `capture_to_visible_latency.py` is the first real consumer to
subtract `decided_at` from another datetime, and hit a `TypeError`
immediately in its own new test. Fixed with the same `_optional_datetime`
helper added for the two new fields — confined to this offline analysis
script, never the live admission/persistence path.

Tooling: [`scripts/run_gate_a_measurement_accounting.py`](../scripts/run_gate_a_measurement_accounting.py)
(219 lines) — one reproducible command taking the same saved ledger JSON
`run_encounter_accounting.py` already accepts (that script is untouched,
still works standalone), plus two optional inputs (`--visits` for the
sibling cross-reference, `--dispositions` for reviewer overrides), writing
all three reports (`encounter-funnel-report.json`, unmodified;
`fragmentation-accounting-report.json`; `latency-report.json`) in one pass.

## Fallback timestamp result

Traced directly in code, at both the arbitration and persistence layers,
before writing any test: `engine_runtime.py`'s `_attempt_resolved_component`
walks `winner`, then each `fallback_order_by_winner_id` member, looking up
`member = new_proposals_by_id[candidate_id]` fresh **by id** on every
attempt — never a stale reference to the winner. `_attempt()`'s own
`relevant`/`evidence_bytes` are derived exclusively from `proposal.
evidence_candidate_ids` (the loop-local `member`, not a closed-over
winner), and `decided_at = datetime.now(UTC)` is re-read fresh on every
call. This property was already true before this milestone — the fix is
disclosed and tested, not introduced.

**Two independent, passing regression tests now pin it down:**

- `capture_to_visible_latency.py`'s own
  `test_fallback_latency_uses_the_admitted_members_own_capture_time_not_the_failed_winners`
  — the analysis layer.
- New `tests/test_engine_runtime.py::
  test_fallback_admission_persists_the_admitted_members_own_capture_time_not_the_failed_winners`
  — the actual persistence boundary: a winner with `captured_at=T` and a
  fallback member with a distinct, unmistakable `captured_at=T+5min`;
  after fallback admits the second member, every persisted
  `MediaAssetModel.captured_at` for the created Visit equals the
  fallback member's own value, never the winner's.

**One real, orthogonal fact found and correctly worked around, not fixed:**
`MediaAssetModel.captured_at` round-trips through SQLite as a *naive*
`datetime` (a pre-existing storage-layer fact unrelated to this milestone
— `DateTime(timezone=True)` under SQLite does not preserve `tzinfo` on
read), so the new persistence test compares via `time_utils.normalize_utc`
(the codebase's own already-established helper for exactly this case),
never a raw `==`. This does not affect `capture_to_visible_latency.py`
itself, which never reads a DB-round-tripped value — it operates purely on
already-in-memory `ProposalOutcomeRecord`/`TrackGenerationRecord` objects
from the counterfactual ledger, which is explicitly, structurally isolated
from SQLAlchemy.

## Stop-finalization result

`tests/test_capture_to_visible_latency.py::
test_stop_finalized_pending_candidate_measures_latency_from_its_own_true_capture_time`
confirms a proposal resolved only at session stop (after minutes of
`blocked_continuation_pending`) still measures latency from its own real
first-capture wall clock, never from the stop event itself — no special
casing exists or is needed, since `_resolve_t0` only ever reads the
admitted outcome's own `constituent_generation_ids`, independent of *when*
the decision was finally reached.

## Historical v7 retrospective result

**Not possible to this contract's own standard — stated explicitly, not
inferred around.** v7's own preserved merged ledger (recovered and
archived, above) predates `start_captured_at`/`end_captured_at` entirely:
every one of its 25 admitted proposals' `TrackGenerationRecord`s report
`start_captured_at=None`. Running the new instrumentation against it
therefore honestly reports all 25 latency samples as
`unavailable_capture_time` — verified directly, not assumed. The same is
true for the 2026-08-19 primary cohort (12 admitted samples, all
`unavailable_capture_time`) and v6 (0 samples; 0 admissions).

**One bounded, explicitly non-authoritative sanity check performed and
disclosed as exactly that, never presented as the real measurement:**
approximating v7's own T0 via the nearest real `raw_detections` record's
own `captured_at` (a genuine per-record fact, accurate to within roughly
one detector sampling interval, ~1.4s — not a linear-epoch extrapolation,
which the drift finding above already shows would be unsound) gives a
rough T0→`decided_at` distribution of median ≈103s / p90 ≈289s / max
≈506s across the 25 admitted proposals — directionally larger than v7's
own published activity-end→`decided_at` proxy (median 86.5s, max 323.7s
for the admitted-only cut), exactly as expected since true first capture
necessarily precedes a proposal's own activity-end offset, and the
divergence is largest in the tail (long, multi-generation admissions where
the first constituent generation started well before the proposal's own
official end). This is a sanity check on direction and rough magnitude
only, computed outside the shipped module, not shipped as a permanent
interpolation code path, and not a T0→T5 measurement.

## Validation

**Tier 1** (every directly touched/new file — 7 modified + 6 new; 30 new
tests among them): `tests/test_counterfactual_lineage.py`,
`tests/test_fragmentation_accounting.py`,
`tests/test_capture_to_visible_latency.py`,
`tests/test_run_gate_a_measurement_accounting.py`,
`tests/test_engine_runtime.py`, `tests/test_candidate_visit_repository.py`,
`tests/test_encounter_accounting.py` (unmodified, rerun as a regression
check on the module this work builds on) — **218 passed, 0 failed.**

**Tier 2** (affected subsystems per this milestone's own §29 — candidate
authority, evidence/fallback, persistence, repository reads, API
visibility, acceptance recorder, time utilities, observation session API):
`test_acceptance_recorder.py`, `test_candidate_visit_adapter.py`,
`test_candidate_visit_authority.py`,
`test_candidate_visit_authority_acceptance.py`,
`test_candidate_visit_review_workflow.py`, `test_candidate_visit_rollback.py`,
`test_concurrent_candidate_visit_persistence_reliability.py`,
`test_observation_session_api.py`, `test_time_utils.py`,
`test_visit_episode_assembler.py`, `test_field_acceptance_authentication.py`
— **222 passed, 0 failed.**

Combined: **440 passed, 0 failed, across 18 test files.**

**Ruff:** zero new findings. Compared directly against baseline (`git
stash push -u`/`pop` around the identical file set) rather than assumed:
identical 30 pre-existing findings on both baseline and this milestone's
own working tree, same files, same codes, line numbers shifted only by the
few lines this milestone itself inserted earlier in `api/main.py`/
`test_engine_runtime.py` — none of them touch anything this milestone
added or changed.

**Every `TrackGenerationRecord`/`CounterfactualTrackGenerationResponse`
construction site** in the repository was grepped and confirmed
keyword-argument-only — the two new optional fields cannot silently shift
an existing positional argument anywhere.

## Tier 3

**Decision: not run, per this milestone's own explicit §30 permission.**
Every production-code change is additive/narrow: one dataclass gains two
`| None = None` fields populated from values already in scope (zero new
control flow); one API response gains two optional fields; one pre-existing
bug fix is confined to an offline analysis script never reachable from the
live admission/persistence path; two brand-new pure modules have zero
existing callers and cannot regress anything by construction. Tier 1 + Tier
2 (440 tests) directly cover every touched file and every immediately
adjacent subsystem, plus two new tests specifically proving the two
highest-risk properties (fallback timestamp correctness at the persistence
boundary; T4/T5 visibility equivalence) that a Tier 3 run could otherwise
be relied on to catch. Not run "solely because this is called Gate A," per
this milestone's own explicit instruction against exactly that.

## Self-review

Performed against every item in this milestone's own §31 checklist; see
each item's own finding cited inline: (1) heuristic-as-truth — never;
`ambiguous` is the structural default absent a strong signal or reviewer
note. (2) simultaneous siblings — confidently `correctly_represented`,
tested. (3) duplicates — a distinct disposition, excluded from the
fragmentation rate, tested. (4)/(5) capture timestamps / fallback — traced
in code at two independent layers *and* tested at two independent layers
(analysis module + persistence boundary); one orthogonal SQLite-naive
-datetime fact found and correctly worked around (`normalize_utc`) rather
than silently mismeasured. (6) clock-domain — disclosed on every sample, a
real ~39s drift found and used to justify never deriving T0 by linear
extrapolation. (7) persistence-vs-visibility — proven by a new test, not
asserted in prose. (8) runtime semantics — additive-only, zero new control
flow in shipped runtime code, 440 tests green, zero new ruff findings. (9)
unbounded storage — none added; the counterfactual ledger's own existing
bounds are untouched. (10) historical-data overclaim — v6/v7/2026-08-19 all
honestly report `unavailable_capture_time`; the one approximate sanity
check is explicitly labeled non-authoritative and not shipped as
production code.

No new fixable defects found in this pass beyond the two already disclosed
and fixed above (`decided_at` parsing; the archival-hygiene gap for v5/v6/
v7's own raw evidence, addressed by this milestone's own archival work
under `data/field-acceptance/2026-08-31-gate-a-*`).

## Budget-dimension maturity

**Fragmentation: READY FOR FORMAL BUDGET REVIEW.** Three independently
reanalyzable/reported real cohorts (2026-08-19, v5, v7) now use one
consistent, human-correctable methodology and each show **0% confirmed
fragmentation** among their own confidently-or-reviewedly-resolved
denominator units (2026-08-19: 7/8 units resolved, 87.5%; v7: 7/10, 70%; v5:
~18/19 via full manual review, ~95-100%), with every remaining residual
honestly disclosed as `ambiguous` — and, for the two units where an
independent human review already exists, reviewer-*confirmed* ambiguous
rather than merely unresolved. v6 (0 admitted Visits, a since-field-closed
defect) remains correctly undefined, not a contrary data point. Candidate
figure, echoing the existing duplicate-Visit-rate candidate framing already
proposed: **~0%/low single digits** — proposed for external review here,
not self-accepted, per this milestone's own explicit instruction not to
accept a numeric budget.

**Capture-to-visible latency: MEASUREMENT CONTRACT CLOSED / MORE FIELD
EVIDENCE REQUIRED.** The definition, instrumentation, and every regression
property (fallback correctness, stop-finalization, multi-subject
siblings, clock-domain safety, visibility-boundary equivalence) are now
closed and tested. Zero real field cohorts exist with the new field
populated — every historical cohort checked (2026-08-19, v6, v7) honestly
reports `unavailable_capture_time` for every sample, confirmed directly,
not assumed. A next field session run against accepted HEAD after this
milestone would be the first to produce real measured samples.

## Remaining field evidence

For the *next* daylight cohort (not self-authorized by this milestone; see
"Decision," below):

1. Real T0→T5 latency samples — the single item this milestone's own new
   instrumentation cannot retroactively supply; any ordinary session run
   against post-this-milestone accepted HEAD closes it.
2. A bounded visual-review pass against the two remaining genuinely
   unreviewed v7 ambiguous units (`visit-observation-candidate-015/-016/-
   017` and `-027/-028`) — recorder frames for these already exist in the
   archived v7 evidence; not attempted here as out of this milestone's own
   scope (measurement contract, not exhaustive forensic re-review).
3. Everything already named in v7's own "Remaining Gate A dependency": a
   second live cohort producing genuinely crowded 3+-simultaneous-subject
   activity (the disclosed, not-yet-benchmarked crowded-feeder/NMS gap);
   the ~13 untraced `blocked_missing_evidence` records outside v7's own two
   exhaustive windows; the already-known Gate B admission-precision
   residual — unaffected by, and not newly closed by, this milestone.
4. End-to-end Visit recall — untouched by this milestone's own explicit
   scope, remains its own separate, still-open Gate A dimension.

## Defects discovered

1. **`run_encounter_accounting.py`'s `decided_at` was never parsed into a
   `datetime`** (fixed, `scripts/run_encounter_accounting.py`;
   pre-existing, latent, harmless until this milestone's own new consumer
   exposed it — see "Instrumentation").
2. **v5/v6/v7's own raw field-acceptance evidence was never archived**
   under this repository's own established `data/field-acceptance/`
   convention (disclosed under "Existing-cohort reanalysis"; addressed for
   these three cohorts by this milestone's own archival work, not a
   process fix for future sessions beyond the disclosure itself).
3. **`MediaAssetModel.captured_at` round-trips through SQLite as a naive
   datetime** — a pre-existing, orthogonal storage-layer fact, already
   correctly handled elsewhere in this codebase via `time_utils.
   normalize_utc` (used, not invented, by this milestone's own new
   persistence-layer regression test); not itself a defect requiring a
   fix, disclosed for completeness.

Neither (2) nor (3) is a product-correctness defect; neither is fixed
beyond what this milestone's own scope requires (archival for (2), correct
test-side handling for (3)) — per this milestone's own explicit "do not fix
product performance/behavior found via the new instrumentation."

## Decision

**Classification A.**

- Fragmentation accounting semantics are explicit and human-correctable:
  `DenominatorUnit`/`ReviewerDisposition`, enforced non-empty notes,
  raises on unknown overrides.
- Sparse and sustained activity both handled correctly: RED/GREEN pair
  plus dedicated sparse/sequential/sustained/over-fragmentation tests, all
  passing.
- Simultaneous siblings never falsely called fragmentation: confident,
  tested, both positive and negative (different-Event-ids) cases.
- Duplicates distinct from fragmentation: separate disposition, excluded
  from the rate, tested.
- v7's own methodology problem reproduced (RED) and corrected (GREEN) on a
  fixture scaled from its real shape.
- True capture→visible latency has an explicit, code-traced,
  doctrine-aligned definition (T0→`decided_at`, with T2-T5's own collapse
  proven, not assumed).
- Timestamps use compatible, disclosed clock domains; a real ~39s
  offset-vs-wallclock drift was found and used to justify the design, not
  merely theorized.
- Instrumentation captures the correct admitted member, including
  fallback — proven at two independent layers (analysis + persistence).
- Stop-finalized Visit latency works — tested.
- Instrumentation does not change Visit truth/semantics — additive-only,
  zero schema change, 440 tests green, zero new ruff findings.
- Tier 1 clean (218/218). Tier 2 clean (222/222). Tier 3 explicitly not
  warranted, decision documented.
- No numeric budget silently accepted — both readiness calls above are
  proposed for external review, not self-accepted.

## Next milestone

Not proposed or started here, per this milestone's own explicit
instruction.
