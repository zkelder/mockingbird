# Detection Quality Accounting v1 contract

Status: Phase 2 "Detection Quality Accounting" milestone (see
[roadmap.md](roadmap.md)), motivated by the 2026-08-10 real Camera Node
smoke: a 25.3-minute session produced 3 candidate Visits, all 3 visually
confirmed false (bare tree bark, empty grass, the hummingbird feeder
itself) -- see the `observation-engine-false-positive-admission-2026-08-10`
project memory. Root cause: `candidate_visit_authority.py`'s authority gate
and `candidate_quality_gate.py`'s quality gate never read detector
confidence, and -- traced precisely by this milestone -- the confidence
value itself is discarded one layer earlier, when a `Tracklet` becomes an
`AssembledVisitProposal` (`visit_episode_assembler._build_proposal`), which
had no field to carry it at all.

## Boundary

This is a measurement and shadow-evaluation contract, not a new production
gate. It:

- preserves detector confidence as bounded, model-neutral evidence from
  detection through track, tracklet, and assembled-proposal lineage
  (`contracts.ConfidenceEvidenceSummary`);
- adds a bounded six-stage accounting pass over already-emitted facts
  (`mockingbird.observation.detection_quality_accounting`);
- separates reviewed truth from diagnostic-only examples explicitly
  (`mockingbird.observation.evaluation_governance`);
- evaluates candidate confidence-aware admission policies in SHADOW only
  against real reviewed historical data
  (`mockingbird.observation.admission_policy`).

It does **not**: change `candidate_visit_authority.evaluate_candidate_
authority` or `candidate_quality_gate.evaluate_evidence_admission`'s actual
decision logic; raise or lower the MDv5 `score_threshold`; retrain, replace,
or swap the accepted MDv5-ONNX model; add a species/broad-class-specific
rule; or grant any candidate policy production authority. See "Production
authority gate" below for exactly what would have to be true before a
future task could change that.

## Where confidence existed, where it was discarded (as traced)

Detector confidence survives cleanly through
`onnx_provider._decode`/`_observation` (`DetectionObservation.confidence`)
and `frame_tracker._observe_detection` (`TrackUpdate.confidence`, a running
max) into `Tracklet.confidence` (`visit_episode_assembler.build_tracklets`,
another max). It is then read exactly once, for evidence *crop ranking*
only, inside `evidence_scoring._score` (`quality_facts["detector_
confidence"]`) -- never for admission. It never reaches
`AssembledVisitProposal`, `VisitProposal`, `CandidateVisitProposalFacts`, or
the `observation_candidate_visits` ledger table at all: none of those types
had a confidence field before this contract, so `candidate_visit_authority`/
`candidate_quality_gate` structurally could not have consulted it even if
their own decision logic changed independently. `evidence_scoring.py`
itself is unmodified by this contract.

## Confidence/evidence lineage

`contracts.DetectionEvidenceSample` (one bounded, retained per-detection
fact: confidence, offset, frame id, `DetectionObservation.observation_id`,
whether it met the tracker's own `strong_detection_threshold`) and
`contracts.ConfidenceEvidenceSummary` (the aggregate: exact `detection_
count`, `max_confidence`, `mean_confidence`/`median_confidence` computed
from retained samples, `strong_detection_count`/`weak_detection_count`,
`max_consecutive_detector_confirmed_frames`, a bounded `samples` tuple,
`broad_class`, first/last detection offsets, and `sample_truncated`) are the
one shared, reusable representation used at every layer:

- `frame_tracker._Track` gains `confidence_samples` (bounded at
  `MAX_TRACK_CONFIDENCE_SAMPLES = 128`, derived from the default
  `maximum_track_duration_ms` x `candidate_detector_fps`) and `max_
  consecutive_detector_confirmed_frames` (mirrors the existing `consecutive_
  negative_detector_frames` shape as the positive-evidence counterpart).
  Both flow onto `TrackView`/`TrackUpdate` as new, defaulted, additive
  fields -- every existing positional/keyword `TrackUpdate(...)` call site
  is unaffected.
- `visit_episode_assembler.build_tracklets` computes each generation's
  `Tracklet.confidence_evidence` from its terminal `TrackUpdate`'s own
  cumulative-so-far `confidence_samples` -- no new tracker bookkeeping pass.
- `AssembledVisitProposal.confidence_evidence` merges its constituent
  tracklets' summaries (`contracts.merge_confidence_evidence`); `project_to_
  visit_proposal` carries it onto `VisitProposal`.
- `candidate_visit_adapter.CandidateVisitAuthorityAdapter.attempt_candidate`
  serializes it onto `CandidateVisitProposalFacts.confidence_evidence_json`;
  `product_repository._create_candidate_visit_locked` persists it onto the
  new, nullable `observation_candidate_visits.confidence_evidence_json`
  column (schema 31, `_migrate_to_observation_confidence_evidence`).

**Addition (Independent Corroboration Value & Persistent-Confusor Admission
Correctness v1):** `ConfidenceEvidenceSummary` gains one further additive
field, `max_single_generation_detection_count` -- for a leaf (pre-merge,
single-generation) summary this always equals `detection_count` itself
(exact, since `detection_count` is always known regardless of whether
per-detection samples survived); `merge_confidence_evidence` takes the
*max*, never the sum, across constituents, mirroring `max_consecutive_
detector_confirmed_frames`'s own already-established reasoning applied to
a different field: how much any *one* generation alone contributed is not
made larger by how many other generations were chained alongside it. No
new column: it travels inside the existing `confidence_evidence_json` text
blob, so no schema/migration change was needed. See
[independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md](independent-corroboration-value-persistent-confusor-admission-correctness-v1-report.md)
for the full field-evidenced rationale and `candidate_quality_gate.
_concentrated_in_single_generation` for the one place that reads it.

### Honesty rules (no fabricated confidence for legacy records)

`None` means "not known," never a fabricated zero:

- `mean_confidence`/`median_confidence` are `None` whenever no per-detection
  samples were retained (a legacy-reconstructed `TrackUpdate` -- for example
  one rebuilt from a pre-this-contract recorded `replay-report.json` via the
  Stage 6.17 `rescore_visit_truth.py` JSON-reconstruction pattern -- simply
  has an empty `confidence_samples` tuple, the dataclass's own backward-
  compatible default).
- `strong_detection_count`/`weak_detection_count`/`max_consecutive_
  detector_confirmed_frames` are `None` (not `0`) specifically when
  `detection_count > 0` but no samples survived to say which were strong,
  weak, or consecutive -- `0` is reserved for the real, provable "zero
  detections happened" case.
- `merge_confidence_evidence` propagates `None` rather than silently
  treating an unknown constituent as zero in a sum, and takes the *max*
  (never the sum) of `max_consecutive_detector_confirmed_frames` across
  merged tracklets, since a real gap between two merged tracklets is not
  "more consecutive support."
- `sample_truncated` disambiguates "we hold a bounded/partial sample" from
  "we hold none at all despite detections happening," for either the
  128-sample cap or a legacy record.
- `max_single_generation_detection_count` is `None` only for a record from
  before this field existed (never merely because per-detection samples
  did not survive -- unlike the fields above, it is derivable from
  `detection_count` alone, which is always exact and known).

`VisitModel.confidence` (an existing column) is deliberately left alone by
this contract: elsewhere in the schema it means species-guess confidence,
not detector animal-presence confidence, and overloading it would violate
"no hidden species assumptions."

## Detection Quality Accounting report

`detection_quality_accounting.build_detection_quality_report` is a pure
function over already-emitted facts (`DetectionObservation`s, `TrackUpdate`s,
confirmed `Tracklet`s, `AssembledVisitProposal`s, and `AdmissionRecord`s --
one per admission attempt, `outcome` reusing the existing `candidate_visit_
authority`/`candidate_quality_gate`/repository outcome vocabularies
unchanged). It answers, for the six stages this milestone names --
animal-presence proposal, localization/tracking, confirmed-track formation,
Visit proposal/assembly, admission attempt, candidate Visit creation -- how
many items reached each stage, the confidence distribution at each of
detection/admitted/rejected, the suppression-reason distribution, and
track-confirmation / Visit-proposal-admission rates. Every rate and
distribution statistic is `{"state": "insufficient_data", "value": None}`
rather than a fabricated number when its denominator is empty (see the
existing `{"state": ..., "value": ...}` convention already used by
`replay.py`/`detector_benchmark.py`).

## Reviewed-truth / evaluation-set governance

`evaluation_governance.EvaluationExample` carries one of three statuses:
`reviewed_truth` (requires a named `reviewed_by`; the only status eligible
for a metric denominator or a future training-eligibility decision),
`diagnostic_only` (a useful hard case with no human Review Decision behind
it -- for example an agent's own visual inspection), or `auto_generated_
unreviewed`. `require_evaluation_metric_eligible` filters to only `reviewed_
truth` examples before any metric is computed. This does not replace
`ReviewLabel`/dataset-eligibility governance (see custom-bird-classifier-
dataset-plan.md); it is the smaller, upstream fact of "does this benchmark
example even have review provenance," checked before that larger governed
decision would ever apply.

Defense in depth (Visit Continuity / Provisional Admission Fix v1, Part 7
audit): the product's own `ReviewLabel` schema had no reviewer-identity
field at all -- a real `ReviewLabel` an agent writes through the genuine
`POST /api/review-labels` path (as this milestone's own fresh-cohort
candidate-004/005/006 labels were) was only distinguishable from a genuine
human correction by free-text prose in `notes`, which nothing enforced.
**Correction (Review Decision Provenance / Truth Boundary v1, see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md)):**
the sentence above originally also claimed "the original three" (the
25.3-minute smoke's candidate-001/002/003) were written the same way.
Direct evidence from the actual reachable product database (`GET
/api/review-labels`) found exactly three real `ReviewLabel` rows total,
matching only the fresh-cohort candidates -- no rows exist for the original
three. That claim was most likely conflating this real product write with
the separate, offline `DIAGNOSTIC_EXAMPLES` manifest registration in
`scripts/run_detection_quality_accounting.py`, which does register all six
candidate ids but only as an evaluation-manifest entry, never a product
`ReviewLabel`. A future manifest-generation script could still carelessly
(never maliciously) copy an agent's self-disclosure straight into
`reviewed_by`/`source` while claiming `status="reviewed_truth"`.
`EvaluationExample.__post_init__` rejects that combination outright
(`reviewed_truth_requires_human_reviewer`) whenever `reviewed_by`/`source`
contains an already-established self-disclosure marker (`agent`, `claude`,
`language model`, ... -- now the one canonical
`mockingbird.review_provenance.NON_HUMAN_DISCLOSURE_MARKERS` vocabulary,
reused rather than duplicated) -- a bounded, documented vocabulary, not a
content classifier, and not the only safeguard: the load-bearing rule
remains procedural (only a human-run script, over material a human
actually reviewed, constructs a `reviewed_truth` example). No committed
evaluation tooling reads live `ReviewLabel` rows at all today
(`scripts/run_detection_quality_accounting.py` sources reviewed truth only
from already-exported, human-vetted Stage 6.17 manifests); the live product
`ReviewLabel` boundary itself is now closed independently, at the schema/
repository layer, by `review-decision-provenance-contract.md`.

The three 2026-08-10 false candidates are registered `diagnostic_only`
(`source="agent-visual-inspection-2026-08-10"`) -- valuable hard negatives,
never promoted to `reviewed_truth`. Their underlying per-detection confidence
is not recoverable from this checkout (the packaged Windows product that
produced them uses its own separate userdata database, and confidence
lineage postdates when they were captured either way), so every SHADOW
policy's outcome against them is honestly `insufficient_evidence`, never a
guessed admit/reject.

## Shadow admission-policy evaluation

`admission_policy.AdmissionPolicy` parametrizes minimum confidence (against
`max`/`mean`/`median`), minimum qualifying-detection count, and minimum
consecutive detector-confirmed frames; any subset may be combined.
`BASELINE_POLICY` (every dimension unset) reproduces today's actual
production behavior -- admit whatever already reached this stage, since
neither real gate reads confidence today. `evaluate_admission_policy`
returns `admit`, `reject`, or (never a guess) `insufficient_evidence`
whenever the exact fact a policy needs was not retained. `default_policy_
sweep` is a bounded ~28-policy deterministic grid built from `detector_
benchmark.DEFAULT_THRESHOLD_GRID` (already includes the current `0.1`
production threshold) plus qualifying-count/consecutive-frame/aggregate/
combination policies -- not a full cartesian product.

`evaluate_policy_against_examples`/`evaluate_policy_sweep` score a policy
against `LabeledProposal`s (a proposal's `ConfidenceEvidenceSummary` plus a
ground-truth `TruthStatus`: `reviewed_true_positive`, `reviewed_false_
positive`, `reviewed_ambiguous`, `diagnostic_only`, or `unreviewed`),
reporting admitted/rejected/insufficient-evidence counts and, only when the
category's sample size is nonzero, reviewed true-positive retention and
reviewed false-positive rejection rates.

### Real reviewed corpus used

`scripts/run_detection_quality_accounting.py` reuses the exact hardware-free
"replay already-recorded real-CUDA facts" methodology the Stage 6.17
`rescore_visit_truth.py` acceptance tooling established (no live camera, no
CUDA/ONNX Runtime session, no product database) across the four
already-reviewed historical field sessions (attempt-2, attempt-3,
session-03, session-04): it reconstructs each session's recorded
`TrackUpdate`s, runs the *current* `build_tracklets`/`assemble_visit_
episodes` (now carrying `ConfidenceEvidenceSummary`) and the unchanged
`replay._match` reviewed-Visit-truth matcher, and writes a governed
`evaluation-manifest.json` plus `admission-policy-report.json` under
`data/evaluations/detection-quality-accounting/` (gitignored, matching the
existing `data/evaluations/bioclip-field-truth.json` precedent). See the
milestone's final report for the resulting numbers and their sample-size
caveats.

## Production authority gate

Existing production admission behavior (`candidate_visit_authority.py`,
`candidate_quality_gate.py`) remains unchanged unless **all** of the
following are true, evaluated together as one explicit decision, never
inferred from a single milestone's shadow run:

1. reviewed truth is large and representative enough (not concentrated in
   one or two sessions/scenes) for the comparison to be meaningful;
2. a candidate policy demonstrates materially improved false-positive
   rejection on that reviewed truth;
3. previously reviewed real-animal recall is not materially degraded;
4. the result is reproducible (same policy, same corpus, same numbers);
5. tests cover the policy semantics (`tests/test_admission_policy.py` and
   friends already do, for the mechanism -- a *specific* promoted policy
   would need its own regression coverage);
6. the change complies with the "Formal model lifecycle" sequence in
   [architecture.md](architecture.md) (this is a threshold/policy change,
   not a model swap, but the same "candidate earns trust, does not inherit
   it" discipline applies).

If any condition is unmet, the candidate policy stays in shadow/evaluation
mode and the report states what additional reviewed examples are needed --
never a threshold guess.

**Condition 1 answered (2026-08-19, Observational Quality Closure v1):** a
70-admitted-Visit, four-real-day (2026-08-14/16/17/18), non-session-concentrated
independently-adjudicated cohort from the real paired Camera Node -- the first
reviewed truth ever large/representative enough to evaluate this gate at all --
found conditions 2 and 3 fail together at every threshold swept against real
persisted detector confidence (`observation_candidate_visits.
confidence_evidence_json`): the best-looking prior single-session point (0.3)
rejects only 29% of real false positives while losing 19% of real animals;
0.7 rejects 67% of false positives while losing 45% of real animals; no swept
value clears both conditions simultaneously. **The gate is not cleared.
Confidence-gated admission remains shadow/evaluation-only; production
admission stays confidence-blind, unchanged.** The real, quantified problem
this cohort *did* find -- roughly a third of admitted Visits are false
positives, geometrically concentrated in a handful of recurring static scene
confusors rather than diffuse noise -- needs a different kind of fix (a
persistent, cross-session, per-Stream recurring-geometry suppression
capability, not a confidence floor); see
[observational-quality-closure-v1-report.md](observational-quality-closure-v1-report.md).

## Gate A field-acceptance metric set

The condition-1/2/3 sweep above answers one narrow question (is
confidence-gated admission a safe production policy). It does not by itself
answer the broader product question roadmap.md's Gate A asks: did
MockingBird correctly notice and represent what actually happened outside.
That broader question needs the full perception funnel measured together,
not one policy sweep. [end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
is the first field session to measure this funnel end-to-end against a
genuinely independent, pre-Visit-list encounter denominator, and its stage
table is now the standing methodology for future Gate A field acceptance,
not a one-off:

genuine encounters → presented to analysis → detector localized → coherent
confirmed track → viable proposal assembled → evidence survived to
admission attempt → admitted Visit, each measured as a rate against the
prior stage and against the original independent denominator, plus:
false-Visit rate, duplicate-Visit rate, fragmented-encounter rate, and
per-subject evidence correctness measured separately from the recall
funnel.

A future Gate A field-acceptance session should reuse this same funnel
shape (an independent encounter denominator built and reviewed *before*
opening the product's own Visit list, then mapped stage-by-stage) rather
than inventing a new measurement structure each time. See "Numeric release
budgets" in [roadmap.md](roadmap.md): several of these rates now have real
recent measurements (for example 2026-08-19's 68.2% end-to-end recall
ceiling and 9.5% false-Visit rate) but no accepted release *budget* yet --
establishing those budgets from a broader body of field evidence than any
single session is itself open Gate A work, not something this contract
invents unilaterally.

## Candidate-model lifecycle compatibility

Nothing here is MDv5-specific. `ConfidenceEvidenceSummary`/`DetectionEvidenceSample`
carry `detector_id`-agnostic facts; `AdmissionPolicy` reads only confidence/
count/streak facts any detector's `DetectionObservation.confidence` can
populate; `evaluate_policy_sweep` takes any labeled proposal set. The same
accounting and shadow-evaluation mechanism this contract adds is exactly
what a future MDv5-candidate comparison (see [detector-candidate-comparison-
contract.md](detector-candidate-comparison-contract.md)) would reuse to ask
"does candidate model X's own confidence distribution support a *different*
admission policy" -- without inventing a second mechanism, and without this
milestone needing to evaluate a second detector to prove that reuse path
exists.

## Authority and limitations

Every module here (`detection_quality_accounting.py`, `evaluation_
governance.py`, `admission_policy.py`) imports no product repository,
filesystem path beyond an explicit caller-supplied manifest path
(`evaluation_governance.load_evaluation_manifest`), network connection, or
CUDA/ONNX Runtime/OpenCV runtime, and creates no Event, Visit, MediaAsset,
ReviewLabel, or reviewed truth. `ConfidenceEvidenceSummary` is evidence, not
observational authority: a gate may read it, but nothing may treat it as a
species/animal-presence decision by itself, and no code may silently convert
a SHADOW policy decision into a production one.

Known limitations disclosed, not hidden: the reviewed corpus used
(51 examples across 4 historical sessions: 17 reviewed true positives, 33
reviewed false positives, 1 ambiguous) is real and reproducible but modest
and session-concentrated (one session alone contributed 20 of the 33 false
positives), not the representative multi-day/multi-scene cohort roadmap.md
Phase 2 ultimately calls for; temporal-consecutive and mean/median-aggregate
policies are structurally `insufficient_evidence` against this *legacy*
corpus specifically because it predates per-detection sample retention, not
because those policy dimensions are unsound -- a *newly* captured session
would populate them fully.
