# Candidate-Visit authority contract

Status: Observation Engine v2 Stage 7 engineering-workflow contract. Composes
unchanged with
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
(Stage 6.19), [reviewed-visit-truth-contract.md](reviewed-visit-truth-contract.md)
(Stage 6.17), and [camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)
(Stage 5). This is the first stage in the Observation Engine v2 sequence that
may write a product-database record; every prior stage (1-6.19) remained
`shadow_only=true`/`creates_truth=false` with no product-repository import
anywhere in the pipeline.

## Problem

Stage 6.19 proved the shadow `VisitEpisodeAssembler` materially reduces
tracker fragmentation on real reviewed wildlife (a sustained ~5-minute visit
consolidates from dozens of raw confirmed generations into a handful of
assembled proposals) while introducing no new fresh-field incorrect merges.
Every one of those assembled `AssembledVisitProposal`s still only exists in
memory, inside whatever process ran the replay or live session -- nothing
about it is visible to a human reviewer. Authority must move exactly one
step: from "an in-memory shadow proposal" to "a bounded, explicitly
machine-marked, needs-review candidate Visit a reviewer can actually see and
correct through the existing Review Queue" -- never further. This stage does
not, and structurally cannot, create `ReviewLabel`, reviewed `Observation`,
confirmed species truth, Bird Log truth, export truth, or analytics truth.

## Authority state

`mockingbird.observation.candidate_visit_authority.ObservationAuthorityMode`
is an explicit two-value `str, Enum` -- deliberately not a boolean:

- `shadow` (default): identical to every prior stage. No candidate Visit can
  ever be created. Live/replay shadow observation, the assembler, and every
  existing production path are completely unaffected.
- `candidate_visit`: the only mode in which
  `ProductRepository.create_candidate_visit_from_proposal` may actually
  persist a Visit. Setting this mode does not itself do anything beyond
  recording the mode and a fresh activation boundary -- no proposal is
  automatically ingested.

Persisted as one durable singleton row
(`ObservationAuthoritySettingsModel`, `observation_authority_settings`
table, `singleton_id=1`) -- the exact same "one settings row, `singleton_id`
primary key" convention `StorageRetentionSettingsModel` already established.
The row is never seeded by a schema migration; `ProductRepository` creates
it lazily, defaulted to `shadow`, the first time authority state is read or
written. An installation that upgrades through Stage 7's migration (schema
version 28) and never touches this feature behaves exactly as if the table
did not exist: reads report shadow defaults from nothing on disk, and no
migration can ever set `mode='candidate_visit'`.

Future authority levels are explicitly out of scope for this stage.

## Activation boundary

`activation_boundary_at` is a deterministic activation/start fact: set fresh
(to the caller-supplied `now`) every time `mode` transitions
`shadow -> candidate_visit`, and cleared back to `None` on every
`candidate_visit -> shadow` transition (the kill switch). Re-affirming an
already-active mode does not reset it. A proposal is only eligible to create
a candidate when its own `observed_at` (the wall-clock moment the adapter
first evaluated it -- never recomputed, never read from the proposal itself,
which stays deliberately wall-clock-free per the assembly contract) is at or
after this boundary. This is what makes turning authority on never
retroactively promote historical shadow output: "no backlog replay into
authority when enabling the mode" is enforced structurally, not by caller
discipline alone.

## Kill switch

There is no separate boolean layered on top of `ObservationAuthorityMode`.
The kill switch *is*
`set_observation_authority_mode(ObservationAuthorityMode.shadow)`. It is
immediate and requires no restart: every candidate-creation attempt re-reads
this row fresh from the database inside its own transaction, never a
cached in-process value, so a change made from any process sharing the
database (a second CLI invocation, a future admin action) takes effect on
the very next attempt anywhere, including inside an already-running trial
process (`test_candidate_visit_repository.py::test_kill_switch_blocks_new_
candidates` and the CLI's own `--activate`/no-`--activate` behavior both
exercise this). Disabling authority never touches an already-created
candidate Visit or its evidence; it remains exactly as reviewable as before
(see "Existing Visit protection").

## Persistence adapter boundary

```
VisitEpisodeAssembler -> AssembledVisitProposal
                       -> candidate_visit_authority (pure gate)
                       -> candidate_visit_adapter (the one impure seam)
                       -> ProductRepository.create_candidate_visit_from_proposal
```

`mockingbird.observation.candidate_visit_authority` is pure: no filesystem,
network, CUDA/ONNX Runtime/OpenCV, product-repository, or SQLAlchemy import
-- structurally enforced the same way every earlier Stage 6.x decision
module is (`test_candidate_visit_authority_module_has_no_product_repository_
import`). It never reads a wall clock or a database itself; `observed_at`,
authority mode, the activation boundary, and durable session/hourly counts
are all explicit caller-supplied facts (`AuthorityState`). Its own decision
function, `evaluate_candidate_authority`, accepts a small structural
`ProposalLineage` protocol (`proposal_id`,
`constituent_generation_ids`, `source_capture_frame_ids`,
`ambiguous_adjacent_proposal_ids`) rather than importing
`visit_episode_assembler.AssembledVisitProposal` directly -- letting the
product repository's own plain `CandidateVisitProposalFacts` satisfy the
identical protocol and reuse the exact same gate for its own transactional
re-check, with no import in either direction beyond what the pipeline above
already requires.

`mockingbird.observation.candidate_visit_adapter.CandidateVisitAuthorityAdapter`
is the one module in the whole Observation Engine v2 tree that imports both
the assembler's output type and `mockingbird.repository.product_repository`.
It scores already-retained evidence exactly the way Stage 6 already does
(`evidence_scoring.score_proposal_evidence`, completely unmodified), builds
the bounded evidence items it can actually back with real bytes, and calls
the repository. `visit_episode_assembler.py` itself has zero references to
this module, `candidate_visit_authority`, or `mockingbird.repository`
anywhere in its own source (unchanged from Stage 6.19; see
`test_visit_episode_assembler.py::test_no_product_repository_dependency`).

`ProductRepository.create_candidate_visit_from_proposal` is the actual,
concurrency-safe authority boundary: it re-validates mode, activation
boundary, rate budgets, lineage, and Privacy/Ignore Zone safety *inside* the
same transaction that performs the write (serialized by a dedicated
in-process `threading.Lock`, matching this class's own established
single-flight convention -- `_storage_retention_lock`/
`_review_identification_assistant_lock`). The adapter's own pre-check with
the shared pure gate is advisory only; a retried, replayed, reconnected, or
racing call always converges on exactly one Visit because the repository
method itself re-decides, never because the caller was careful.

## Candidate Visit semantics

One accepted `AssembledVisitProposal` may create at most one candidate
Visit, keyed by a durable idempotency ledger row
(`ObservationCandidateVisitModel`, `observation_candidate_visits` table)
whose primary key *is* `AssembledVisitProposal.proposal_id` -- already a
deterministic sha256 of the assembler version plus sorted constituent
generation ids (see
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)),
so it needs no second identity scheme to be stable across retry, process
restart, reconnect, replayed frames, and repeated finalization.

The persisted candidate reuses the existing product model unchanged --
`VisitModel`/`EventModel`, exactly the same tables every other Visit lives
in -- rather than inventing a parallel "CandidateVisit" domain object:

- `EventModel.event_type = "observation_engine_candidate"` (a new stable
  string value, the same convention `"motion_evidence"`/
  `"manual_media_import"`/`"folder_media_import"` already establish for
  event provenance).
- `VisitModel.review_status = "needs_review"` (the existing enum value
  every unreviewed Visit already uses) and `subject_label` set to the
  proposal's own `broad_class` (never a species guess).
- The ledger row (`ObservationCandidateVisitModel`) carries everything else
  Stage 7 must retain: `stream_id`, `zone_id`, `broad_class`,
  source-relative `start_offset_ms`/`end_offset_ms`, `assembler_version`,
  `authority_gate_version`, `constituent_generation_ids_json`,
  `constituent_track_ids_json`, `source_capture_frame_ids_json`,
  `supporting_frame_ids_json`, `evidence_candidate_ids_json`,
  `detector_provenance`/`tracker_provenance`/`provider_key`,
  `selected_identification_media_asset_id`/
  `selected_context_media_asset_id`, `persisted_media_asset_ids_json`,
  `limitation_facts_json`, and `ambiguous_adjacent_proposal_ids_json`.

### Lineage validity: two distinct frame-identity fields

A real bounded trial against the paired Camera Node (see "Real controlled
trial" below) disclosed a genuine gap in the first implementation: a
proposal assembled from a genuine *live* session never populates
`source_capture_frame_ids` at all -- that identity is Stage 6.14's
reviewed-source concept, populated only when a proposal traces back through
the temporal-review/replay pipeline (a human has already retained the
frame). Requiring it unconditionally would have made every real live
proposal structurally ineligible regardless of evidence quality. The
lineage-validity gate now accepts *either* `source_capture_frame_ids` (the
more specific, reviewed-source identity, preferred when present) *or*
`supporting_frame_ids` (the ordinary per-track frame identity every Stage
4+ tracker generation already carries, live or replay) -- refusing only a
proposal with no traceable frame identity at all. Both fields are retained
on the ledger row whenever present; neither is fabricated when absent.

Species identity is never persisted as truth: `VisitModel.species_guess`
and `reviewed_label` stay `None` on creation, always. If a future provider
attaches a species suggestion elsewhere, it remains suggestion evidence only
(`SpeciesSuggestion`), completely outside this stage's write path.

### Candidate identification

A Stage 7 candidate is distinguishable from every other Visit provenance
using existing fields alone, with no duplicate concept introduced:

- `review_status == "needs_review"` (shared with every other unreviewed
  Visit -- correct, since a candidate must use the exact same review
  surface).
- `EventModel.event_type == "observation_engine_candidate"` (unique to this
  stage, mirroring the existing per-provenance `event_type` convention).
- Presence of an `ObservationCandidateVisitModel` row keyed by the Visit's
  own id (`uq_observation_candidate_visit_visit`) -- the authoritative,
  queryable "this Visit was Stage-7-created" fact and full lineage record.

## Ambiguity policy

A proposal whose own `ambiguous_adjacent_proposal_ids` is non-empty -- the
assembler itself could not confidently resolve this proposal's boundary
against a temporally-adjacent one -- is conservatively **blocked**
(`blocked_ambiguous_boundary`), not persisted with a boundary that might
legitimately need to change. Locking in a possibly-wrong episode grouping as
a persisted candidate is a worse failure than not creating one yet: Stage 7
candidates are never automatically re-merged, re-split, or have their
historical timing rewritten once created (see "Existing Visit protection"),
so an ambiguous boundary is exactly the case where persisting now would
foreclose a better answer later. The shadow proposal itself remains fully
visible through existing shadow/replay diagnostics either way; this policy
only decides Stage 7's own persistence action.

## Idempotency and concurrency

Proven at three layers (`tests/test_candidate_visit_repository.py`):
same-proposal replay, a simulated process restart (`ProductRepository`
re-opened against the identical on-disk database file), and eight
concurrent threads racing the identical request -- every case converges on
exactly one created candidate and the rest report `idempotent_repeat` with
the same `visit_id`. Session/hourly rate counts are computed live from the
ledger table on every attempt (`select count(...) where created_at >= ...`)
-- never an in-memory-only counter a restart could reset.

## Existing Visit protection

`create_candidate_visit_from_proposal` never touches an existing Visit row:
it only ever inserts a brand-new `VisitModel`/`EventModel`/
`ObservationCandidateVisitModel`/`MediaAssetModel` set, or (idempotent case)
reads one back unchanged. There is no merge-into-reviewed-Visit path, no
historical-timing-rewrite path, and no attach-new-machine-evidence-to-an-
existing-Visit path anywhere in this stage.
`test_candidate_visit_repository.py::test_candidate_creation_does_not_
mutate_an_unrelated_reviewed_visit` proves a pre-existing reviewed Visit's
full row (`review_status`, `reviewed_label`, `species_guess`, `confidence`)
is byte-identical before and after a Stage 7 create.

## Evidence persistence

Stage 7 persists only already-selected, already-bounded evidence -- never
the analysis stream. The adapter calls the unmodified Stage 6
`evidence_scoring.score_proposal_evidence` scorer, then builds a
`CandidateEvidenceItem` only for the identification/context/alternate picks
it actually has real bytes for; a pick with no retrievable bytes is
honestly skipped, never fabricated. The repository bounds the persisted set
to `max_evidence_items_per_candidate` (default 4) and
`max_evidence_bytes_per_candidate` (default 8 MB), and requires at least
one persistable item -- zero persistable evidence fails safely
(`blocked_missing_evidence`) rather than creating an evidence-less
candidate. Every persisted `MediaAssetModel` carries `trigger_id =
proposal_id` (an existing v24 provenance field, reused rather than
duplicated) and `derivation_source = "observation_engine_candidate"`, plus
`evidence_role` (`identification`/`context`/`alternate`) and
`normalized_track_box_json` from the candidate's own subject geometry when
known.

For the real live trial, evidence is sourced only from the live session's
own bounded high-resolution burst cache
(`LiveCameraNodeShadowSession.temporary_burst_payload`, keyed by content
hash) -- the "already-captured real evidence burst" this stage's own
evidence-persistence policy names first. Ordinary tracked/pretrigger
analysis frames are not retained as recoverable bytes by the live session at
all (only used for inference, matching "do not persist the entire analysis
stream"), so a live trial's candidates are backed exclusively by real burst
frames; a proposal with no captured/retained burst fails safely rather than
persisting without real evidence. This is a deliberate, disclosed scope
choice for the first trial, not a defect -- broadening evidence sourcing to
ordinary tracked frames is future, separately-scoped work.

## Privacy / Ignore

Subjects inside a Privacy or Ignore Zone are already excluded upstream of
every Observation Engine v2 provider: the frame-driven tracker discards any
detection centered inside an excluded region before a track ever forms (see
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)),
so no evidence candidate -- and no `AssembledVisitProposal` -- should ever
legitimately carry a masked Zone. `create_candidate_visit_from_proposal`
still checks `ZoneModel.zone_type` explicitly before creating anything
(`blocked_privacy_zone`) as defense in depth, exactly mirroring the same
explicit check `_promote_motion_evidence_model`/
`create_motion_evidence_from_saved_media` already perform at this
persistence boundary.

## Failure behavior

A genuine repository/storage failure (never an ordinary policy rejection,
which returns a typed outcome instead) raises one sanitized `ValueError`
from inside the failed transaction, which rolls back completely -- no
partial Visit/Event/MediaAsset/ledger row can ever survive
(`test_persistence_failure_rolls_back_and_creates_no_partial_truth`). The
adapter catches it, records a bounded, sanitized failure diagnostic
(`ProductRepository.record_observation_authority_failure`, a
separate small transaction from the failed one), and returns an ordinary
`"failed"` outcome -- it never re-raises, so a live observation loop driving
the adapter continues to its next frame/proposal
(`test_repository_failure_is_caught_and_recorded_not_raised`).

## Limits

`AuthorityLimits` (`max_candidates_per_session`, `max_candidates_per_hour`,
`max_evidence_items_per_candidate`, `max_evidence_bytes_per_candidate`) are
explicit, bounded, and caller-configurable -- generous defaults (50/20/4/8MB)
for general operation, overridden to the trial-mandated 3-candidate session
bound by `candidate-authority-trial`'s own CLI. `create_candidate_visit_
from_proposal` never ingests a historical backlog: only proposals whose
`observed_at` is at or after the current activation boundary are eligible
at all, regardless of budget headroom.

## Diagnostics

`ProductRepository.get_observation_authority_state()` is a side-effect-free
read (never creates the settings row) returning: current mode, activation
boundary, configured limits, live session/hourly counts, and bounded
lifetime counters (`proposals_observed_count`, `candidates_attempted_count`,
`candidates_created_count`, `idempotent_repeat_count`, `suppressed_count`,
`failure_count`, `last_failure_code`/`last_failure_at`,
`last_candidate_visit_id`, `last_proposal_id`). No admin UI is added in this
stage.

## Real controlled trial

`python -m mockingbird candidate-authority-trial` (see module docstring in
`candidate_visit_authority_cli.py`) reuses Stage 5's
`CameraNodeAnalysisSource`/`CameraNodeHttpTransport`/
`LiveCameraNodeShadowSession` completely unchanged -- the same convention
`temporal_capture_cli.py` already established -- for a hard-bounded
duration (`--duration-seconds`, capped at 600) and a hard-bounded candidate
stop condition (`--max-candidates`, capped at 3). It periodically reruns
`build_tracklets`/`assemble_visit_episodes` over the live session's own
accumulated `TrackUpdate`s (the assembler itself remains a post-hoc pass
over finalized, confirmed generations, exactly as Stage 6.19 designed it --
this trial does not add a live incremental assembler) and, only with
`--activate`, attempts a real candidate through the real
`CandidateVisitAuthorityAdapter` against the real product database. Without
`--activate`, authority state is read but never changed, so the trial is a
safe, hardware-connectivity/mechanics-only dry run identical in effect to
ordinary shadow observation.

### Real trial results (2026-08-08, paired Raspberry Pi Camera Node)

A dry run (45s, no `--activate`) connected to the real Node, ran real ONNX
Runtime CUDA MegaDetector inference (RTX 4060 Ti), observed 2 real
assembled proposals, and correctly reported `blocked_shadow_mode` for both
-- zero product writes beyond the additive schema migration itself (44 to
46 tables; one lazily-created `observation_authority_settings` row,
`mode=shadow`). A first activated attempt (300s) surfaced the lineage gap
above: all 24 real assembled proposals were `blocked_invalid_lineage`. With
that fixed, a second activated attempt (300s, `--max-candidates 3`)
observed 14 real assembled proposals -- 6 `blocked_missing_evidence` (no
retrievable high-resolution burst), 6 `blocked_ambiguous_boundary` (the
assembler's own conservative policy), and **2 genuine candidate Visits
created** from real 4624x3472 burst evidence of a backyard feeder tree,
both `needs_review`, both with complete lineage, neither self-reviewed. A
full structural snapshot before/after found changes exactly attributable to
the two candidates (`+2` each to `visits`/`events`/`media_assets`/
`visit_evidence_links`/the ledger table, `+2` to `product_alerts` from the
existing, unrelated "Visit ready for review" alert mechanism every
needs-review Visit already triggers) and zero changes to `review_labels` or
any reviewed Visit. The kill switch (`ObservationAuthorityMode.shadow`) was
then exercised against the same real database: a new proposal attempt
immediately reported `blocked_shadow_mode`, both real candidates remained
present and `needs_review`, and a final snapshot confirmed zero further
change. See the Stage 7 final report for the complete acceptance matrix.

## Authority and limitations

This stage opens the product database -- the first Observation Engine v2
stage to do so -- but only ever through
`create_candidate_visit_from_proposal`'s own narrow, transactional,
idempotent write path, and only when `mode == candidate_visit`. It cannot
create a `ReviewLabel`, mark a Visit reviewed, write a confirmed species
guess, create a reviewed `Observation`, or touch Bird Log/analytics/export
truth by itself under any input -- every one of those remains reachable
only through the exact existing, completely unmodified
`ProductRepository.create_review_label` correction path
(`tests/test_candidate_visit_review_workflow.py`). It changes no detector,
tracker, reconnect, burst-scheduler, evidence-scoring, session-timeline, or
Privacy/Ignore-masking behavior, and grants no further authority level --
future authority levels beyond `candidate_visit` are explicitly out of
scope for this stage.
