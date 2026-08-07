# Deterministic evidence-quality benchmark contract

Status: Observation Engine v2 Stage 6.13 engineering-workflow contract, closing
a standalone tooling gap Stage 6.7/6.10 acceptance work repeatedly disclosed:
there was no standalone evidence-scoring benchmark CLI, so evidence usefulness
was sometimes reported with bounded descriptive analysis instead of the same
deterministic benchmark/report machinery already established for detector,
tracker, multi-scale, and burst evaluation.

## Boundary

`mockingbird.observation.evidence_benchmark` is pure: no filesystem I/O, no
network, no CUDA/ONNX Runtime/OpenCV, no product-repository or product-database
import (`evidence_benchmark_io.py`/`evidence_benchmark_cli.py` own that). It
**calls** the existing Stage 6 scorer,
[`evidence_scoring.score_proposal_evidence`](multi-frame-evidence-scoring-contract.md),
once per reconstructed episode, and never ranks or selects a candidate itself.
The benchmark layer owns only reviewed-truth ingestion, matching candidates to
annotations, metric calculation, comparison, and deterministic reporting.
Every output remains `shadow_only=true`, `creates_truth=false`; it opens no
product database and cannot create or mutate an Event, Visit, MediaAsset,
MotionEvidence, evidence link, primary selection, ReviewLabel, reviewed
Observation, or monitoring-policy row.

## Reviewed evidence manifest

`ReviewedEvidenceManifest` (`manifest_version=1`) is the smallest additive,
versioned truth input: a flat list of `ReviewedEvidenceCandidate` records.
Every field beyond identity/role is optional; a caller supplies only what the
source annotation actually supports, and no review truth not present in the
source annotation is ever invented. Fields split into two groups:

- **Reconstruction facts** (`role`, `width`/`height`, `subject_geometry`,
  `source_offset_ms`, `high_resolution`, `temporal_alignment`, `sharpness`,
  `decodable`, `privacy_masked`, `request_to_capture_ms`) feed the existing
  scorer as `EvidenceCandidate.quality_facts`, exactly the way a live
  provider's own declared facts would.
- **Reviewed truth** (`useful_broad_confirmation`, `useful_identification`,
  `useful_context`, `preferred_identification`, `preferred_context`,
  `reviewed_subject_visible`, `reviewed_blurred`, `reviewed_clipped`,
  `reviewed_occluded`, `reviewed_subject_contained`, `timing_uncertainty_ms`,
  `reviewer`/`reviewed_at_iso`/`truth_source` provenance, `ambiguous`,
  `limitations`) is never fed to the scorer; it exists only to check the
  scorer's own output honestly. A candidate marked `ambiguous=True` is
  excluded from every scoring denominator, matching
  `ExpectedEvidence.ambiguous`'s existing convention.

Candidates group into one evaluated episode (one `VisitProposal` passed to the
scorer) by `episode_id` -- default `f"{session_id}:{track_generation_id or
'context'}"` -- so a candidate whose own `track_generation_id` disagrees with
its assigned episode is offered to the scorer but rejected by its existing,
unmodified stale-generation guard, never silently scored against the wrong
episode. An optional `appearances` list (`ReviewedAppearance`, mirroring
`temporal_annotation.AppearanceInterval`/`replay.ExpectedAppearance`) records
the earliest genuine subject presence per session, letting the benchmark
honestly measure evidence latency from first appearance rather than only from
burst request time.

`build_reviewed_evidence_manifest_from_temporal_review(session, annotations,
...)` mechanically derives this manifest from an already-loaded Stage 6.6/6.8
capture-session-manifest dict and `AnnotationSet` -- a caller never
hand-copies data that already exists in the reviewed packet. Only reviewed
(`is_reviewed`) frames become candidates. Role is reconstructed from
`trigger_reasons`/`high_resolution` (a documented, honestly-disclosed
simplification: a static reviewed packet cannot replay the live tracker's own
`tracked_best`/`final_supported` distinction); a frame active in more than one
simultaneous track generation is attributed to its lexicographically first
generation id, the same convention `burst_scheduler_replay.
reconstruct_opportunities` already uses; width/height are left unset and
resolved from the referenced `frames/<frame_id>.jpg` image at scoring time.

## Benchmark inputs

`evaluate_evidence_benchmark(manifest, *, media=None, replay_candidates=(),
replay_proposals=(), bounds=None, provider_identity=None,
replay_report_fingerprint=None)` supports both required input categories:

- **Stage 6.6 reviewed packets**: `manifest` (optionally derived per above)
  plus `media` resolved from the reviewed-frame-root -- no camera or GPU is
  required when candidate metadata/images are already present.
- **Existing replay/evidence results**: `replay_candidates`/`replay_proposals`
  reconstructed from an already-produced `replay-report.json`'s own
  `evidence_candidates`/`proposals` sections (real `EvidenceCandidate`/
  `VisitProposal` dataclasses, not a shortcut that reuses the report's
  already-computed selections) form additional episodes the scorer is called
  on exactly as for manifest-derived ones. Truth can only link to a
  replay-sourced candidate when its own identity (`media_asset_id` or
  `frame_id`) matches a `candidate_id` in `manifest`; when it does not
  (for example, a replay produced through `replay-benchmark` assigns each
  frame a new, replay-derived identity distinct from its original captured
  `frame_id` -- a pre-existing fact of that pipeline this benchmark does not
  change), the affected metrics honestly report `not_evaluated`/
  `insufficient_truth` rather than a fabricated value, and a limitation is
  recorded.

## Metrics and states

Every metric is `{"state": ..., "value": ...}`. States are `evaluated`,
`not_evaluated` (the underlying structural population is empty -- nothing was
ever selected, or no candidate anywhere carries the relevant field),
`insufficient_truth` (truth exists globally but is all-ambiguous, or does not
link to anything the scorer actually selected), or `unsupported` (reserved for
a completely empty benchmark input: zero reviewed candidates and zero
replay-sourced candidates). A rate is never fabricated as `0.0`/`1.0` when its
denominator is genuinely empty, matching the existing `useful_primary_rate`
zero-denominator downgrade `replay._evidence_metrics` already established.

Availability: `episodes_evaluated`, `episodes_with_any_evidence`,
`episodes_with_identification_candidate`, `episodes_with_context_candidate`,
`episodes_with_alternates`, `no_useful_evidence_count`.

Identification: `reviewed_useful_identification_candidate_count`,
`useful_identification_rate`, `selected_identification_correctness` (where a
reviewed `preferred_identification` candidate exists),
`identification_subject_contained_rate`, `identification_clipped_rate`,
`identification_blurred_unusable_rate`,
`identification_high_resolution_selection_rate`,
`identification_analysis_frame_selection_rate`.

Context: `reviewed_useful_context_candidate_count`, `useful_context_rate`,
`selected_context_correctness`, `context_subject_visible_rate`,
`context_role_distribution`.

Temporal: `selected_evidence_temporal_alignment_rate`,
`selected_evidence_temporal_uncertain_rate`,
`evidence_latency_from_appearance_ms`, `burst_request_to_capture_latency_ms`,
`temporal_uncertainty_ms_average`, `stale_generation_rejection_count`.

Candidate quality: `candidates_per_episode_mean`, `eligible_candidates_count`,
`rejected_candidates_count`, `rejection_reason_distribution`,
`selected_identification_role_distribution`,
`selected_context_role_distribution`, `alternate_role_distribution`.

Human-review workload proxy (deterministic structural facts only, never a
subjective review-effort score): `candidates_presented_per_episode_mean`,
`episodes_with_no_useful_automatic_identification`,
`episodes_requiring_alternate_inspection`.

## Comparison

`compare_evidence_benchmark_reports(baseline, candidate)` classifies every
metric present in either report's `metrics` section independently --
`baseline better`, `candidate better`, `equivalent`, `insufficient truth`, or
`unsupported for one side` -- mirroring `replay.compare_replay_reports`'s
established shape exactly (renamed left/right to baseline/candidate). It never
produces an aggregate winner score. A non-numeric metric (a role-distribution
dict) that differs between the two reports classifies `unsupported for one
side`, the same fallback the existing precedent uses.

## Semantic/non-semantic split

The semantic payload (`to_semantic_dict()`) carries input/review fingerprints
(`manifest_fingerprint`, `replay_report_fingerprint`), provider/policy identity
(`policy_identity` -- the evidence-scoring version and bounds in force;
`provider_identity` -- the replay report's own provider block, when supplied),
every reconstructed evidence candidate and selection (reusing
`EvidenceCandidate`/`EvidenceSelection` unchanged), metric values/states,
deterministic comparison classifications, and limitations. It never contains
an absolute path, wall-clock timestamp, or machine-resource fact. The
separate, non-semantic `execution` section (added only by
`evidence_benchmark_cli.py`) may carry the absolute output path, wall-clock
duration, image decode latency, process RSS, and environment details; a
regression test (`test_runtime_differences_do_not_affect_semantic_fingerprint`
in `tests/test_evidence_benchmark.py`) asserts none of those tokens ever reach
the semantic payload or its fingerprint. Report and manifest ordering
(candidates, episodes, evidence candidates/selections) is canonicalized by id
rather than input order, so two runs over the same logical input in a
different order produce identical semantic dicts and fingerprints.

## Safe I/O

`evidence_benchmark_io.py` mirrors `replay_io`/`detector_comparison_io`/
`burst_scheduler_replay_io`'s established conventions: symlink-free,
`.json`-suffixed input files; a new-or-empty, symlink-free output directory
that refuses the repository root, any in-repository path outside `data/`
(source, docs, tests directories included), and a non-empty existing
directory; an atomic fsync-then-rename report write. `resolve_media_mapping`
rejects an unsafe frame path (absolute, traversal, wrong suffix, symlink)
outright but silently skips one that is merely absent on disk -- candidate
metadata alone remains sufficient to score, and a missing image is never
treated as a safety violation. No command ever opens the product database or
writes into a reviewed source-media directory; `--review`/`--frames` are read
paths only.

## Commands

```sh
python -m mockingbird evidence-benchmark \
  --review <reviewed-temporal-review-directory> \
  --output <new-or-empty-output-directory>

python -m mockingbird evidence-benchmark \
  --frames <reviewed-frame-root> --manifest <reviewed-evidence-manifest.json> \
  [--replay-report <existing-replay-report.json>] \
  --output <new-or-empty-output-directory>

python -m mockingbird evidence-comparison \
  --baseline <baseline-evidence-benchmark-report.json> \
  --candidate <candidate-evidence-benchmark-report.json> \
  --output <new-or-empty-output-directory>
```

`--review` is mutually exclusive with `--frames`/`--manifest`. Neither command
starts a camera, Camera Node, worker, or model runtime.

## Authority and limitations

This stage adds no detector, tracker, reconnect, burst-scheduler, or evidence-
scoring change; it changes no runtime threshold, Ignore region, or monitoring
policy; and it grants no Stage 7 proposal authority. Truth linkage between a
`--replay-report`'s candidates and a reviewed manifest's truth depends on
matching identity, which a report produced through `replay-benchmark` on a
Stage 6.6 export does not currently share with the original reviewed
`frame_id` namespace (see "Benchmark inputs" above) -- a pre-existing,
disclosed limitation of the upstream pipeline this stage does not attempt to
fix. Role/track-generation reconstruction from a static reviewed packet is a
documented simplification, not a replay of live tracker decisions.
