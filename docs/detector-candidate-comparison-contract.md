# Detector candidate comparison contract

Status: Observation Engine v2 Stage 6.3 provider contract.

## Boundary

`mockingbird.observation.detector_comparison` compares one MDv5 baseline
against one or more replacement candidates -- for example the evaluated
`spruce` (MegaDetector v1000.0.0-spruce) candidate -- each already scored
against the identical reviewed calibration cohort by the Stage 6.2
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md).
It is offline, deterministic, and diagnostic only: it never re-runs
inference, never opens a camera/Camera Node/product database, and never
mutates a runtime threshold, Ignore region, tracker, or default-model
setting. Every output remains `shadow_only=true`, `creates_truth=false`
evidence with no production proposal authority, and
`no_automatic_default_model_change=true` -- comparing candidates never
switches which detector MockingBird actually runs.

The module is split the same way as Stage 6.2: `detector_comparison.py` is
pure (no filesystem I/O, no model-runtime import; every function operates on
already-loaded `detector-benchmark-report.json` dicts),
`detector_comparison_io.py` handles safe report loading and atomic report
writes, and `detector_comparison_cli.py` wires those together.

## Input contract

Each input is one complete Stage 6.2 semantic report (the `detector-
benchmark-report.json` written by `detector-benchmark`), loaded from an
arbitrary local path -- deliberately not confined to the repository
workspace, the same way `--frames`/`--manifest`/`--provider-config` already
accept any local path, because two-root reproducibility checks require
reading reports produced from unrelated absolute roots. `compare_candidate`
reads a bounded, explicit set of fields from each report (`cohort`,
`provider.model`, the configured-threshold row of `threshold_sweep`,
`static_false_positive_clusters`, `temporal_policy_simulation`,
`sample_sufficiency`, `overall_classification`, and each report's own
non-semantic `execution` facts); any other content in the input report,
including a value that happens to look like an absolute path, is never read
and therefore never reaches the output.

## Cohort consistency

`compare_candidate` requires the baseline and candidate report's
`cohort.manifest_fingerprint` to match exactly before any metric is
compared. A mismatch does not raise -- it produces a comparison whose
`cohort_consistency.consistent` is `false`, every accuracy/stratum
comparison reports `unsupported_for_one_model`/empty, and
`final_recommendation` is `insufficient_reviewed_data` with the mismatch
recorded in `rationale`. Comparing two models scored against different
reviewed cohorts is refused as a semantic operation, not silently
attempted.

## Taxonomy documentation gate

A report whose `provider.model.taxonomy` is missing or empty is treated the
same way as a missing configured-threshold row: `compare_candidate` reports
`unsupported_for_one_model` for every accuracy metric and an empty scene/
subject-size breakdown, rather than numerically comparing precision/recall
between two models when there is no recorded basis for trusting that
"animal" means the same evidence category on both sides.

## Semantic / non-semantic boundary

This is the load-bearing rule of this module. The semantic payload (the
input to `semantic_fingerprint`) may include model identity and
fingerprint, taxonomy mapping, the reviewed-cohort fingerprint, each
model's own threshold operating point and grid, precision, recall,
positive-frame recall, false positives per negative frame, small/typical
subject recall where the cohort supports it, scene-group breakdowns, the
static false-positive cluster and shepherd's-hook diagnostic, temporal-
policy outcomes, the licensing classification, the integration-complexity
classification, and the deterministic `final_recommendation` with its
rationale.

The semantic payload must never include: absolute paths, timestamps, output
directories, model load time, inference latency, throughput, elapsed
duration, RSS, GPU memory, CUDA/CPU execution-node counts, model artifact
byte size, host/device identifiers, or environment-specific package paths.

Critically, this exclusion covers not just those raw numbers but also any
classification *derived* from them. `RuntimeComparison` computes an
acceptable/degraded/unacceptable resource-use classification from each
report's own non-semantic latency/GPU-memory/model-size facts -- but that
classification is a function of numbers that are not bit-for-bit
reproducible across two separate process runs of the identical model and
cohort (scheduling jitter, GPU thermal/contention state). A classification
that is merely *usually* stable across reruns is not the same guarantee as
one that structurally cannot change, and two-root reproducibility requires
the latter. `_semantic_comparison_dict` therefore drops the entire
`runtime` field before fingerprinting; `CandidateVerdict` carries no
`resource_usage` field at all, and `_final_recommendation` never takes a
`RuntimeComparison` as an input. The full runtime comparison -- raw
latency/GPU-memory/model-size numbers *and* the derived classification
together -- is written only to the separate, non-semantic
`execution.runtime_facts_by_candidate` section, exactly mirroring how Stage
2/3/6.2 already keep latency and execution-provider facts out of their own
`semantic_fingerprint`. A constructed regression test proves two otherwise-
identical report pairs that differ only in runtime/resource facts -- even
differences large enough to cross every acceptable/degraded/unacceptable
boundary -- produce byte-identical `semantic_fingerprint` and
`final_recommendation`.

Consequently, "whether a candidate is suitable for a bounded live shadow
trial" is answered by combining two independent, honestly-separated facts:
the reproducible semantic `final_recommendation`, and the non-semantic
`execution.runtime_facts_by_candidate` resource classification. Neither
substitutes for the other, and the tool deliberately does not collapse them
into one opaque score.

## Candidate comparison rules

MDv5 and each candidate are compared honestly, never by treating raw
confidence values as calibrated identically across models. Each model
keeps its own threshold sweep, score distribution, preprocessing contract,
taxonomy mapping, decoder provenance, and operating-point interpretation;
`ModelSummary.configured_threshold` and `.threshold_grid` are read and
reported per model and are never merged, averaged, or asserted equal.
Metric comparison instead reads each model's own configured-threshold row
outcome (precision, recall, positive-frame recall, false positives per
negative frame, false-positive frame count, duplicate detections) and
classifies the *outcome* difference as `better`/`equivalent`/`worse` within
`METRIC_EQUIVALENCE_TOLERANCE`, or `insufficient_truth`/
`unsupported_for_one_model` when a value is missing on one side.

Each candidate's report independently states: precision better/equivalent/
worse; recall better/equivalent/worse; small-subject recall better/
equivalent/worse/insufficient_truth (read from the `far` `subject_size_
breakdown` bucket; `blur` and `occlusion` are reported as explicit
`unevaluated_strata` on this cohort, since no reviewed frame recorded
either fact); static-scene (shepherd's-hook hard-negative) behavior better/
equivalent/worse; temporal-policy behavior better/equivalent/worse/
insufficient_truth (aggregated `confirmed_false_episodes` across every
`supported` policy except `single_detection`); resource use acceptable/
degraded/unacceptable/insufficient_evidence (non-semantic, see above);
licensing acceptable/restricted/unacceptable
(`classify_license`: MIT/Apache/BSD family is acceptable; GPL family is
restricted -- usable for local shadow evaluation, not cleared for
redistribution; AGPL or an explicit "unacceptable" in the recorded
redistribution text is unacceptable); and integration complexity bounded/
material/high (`classify_integration_complexity`: reusing the exact
existing decoder and taxonomy is bounded, a same-taxonomy model needing a
new decoder is material, anything else is high).

`build_comparison_semantic_report` never produces an opaque winner score.
`final_recommendation` is one of `retain_mdv5_baseline`,
`continue_candidate_shadow_evaluation`, `candidate_ready_for_live_shadow_
trial`, `candidate_unsuitable`, or `insufficient_reviewed_data`, each with
its own `rationale`. `safe_for_shadow_experimentation=true` and
`safe_for_production_authority=false` are hard-coded on every verdict --
`candidate_ready_for_live_shadow_trial` is a shadow-evaluation readiness
signal, not a production selection.

## Report and command

```sh
python -m mockingbird detector-comparison \
  --baseline-label mdv5 \
  --baseline-report MDV5_REPORT.json \
  --candidate spruce=SPRUCE_REPORT.json \
  [--candidate other-label=OTHER_REPORT.json ...] \
  --output OUTPUT_DIRECTORY
```

Writes one atomic `detector-comparison-report.json` into a new or empty
directory, using the identical safe-output-path rules as
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md).
`candidate_reports` (and therefore `candidate_labels` and `comparisons`) are
always consumed and emitted in sorted-label order regardless of input
`--candidate` argument order, so the report is stable no matter how the
caller assembled its inputs. Two comparison runs over the same pair of
Stage 6.2 reports -- including reports independently produced from two
different absolute roots -- produce byte-identical semantic payloads.

## Authority and limitations

The module imports no product repository and cannot create or mutate
Event, Visit, MediaAsset, MotionEvidence, evidence link, primary selection,
ReviewLabel, reviewed Observation, Dashboard/export truth, monitoring
policy, or policy revision. It does not select or apply a threshold, does
not create or apply an Ignore region, does not retrain or replace a
detector, and does not change the Stage 4/6.1 tracker, Stage 6 evidence
scoring, or which provider MockingBird actually runs. `candidate_ready_
for_live_shadow_trial` characterizes accuracy, static-scene, temporal, and
licensing evidence on the current reviewed cohort only; it is not a
production-readiness claim, does not itself gate resource/runtime
acceptability, and does not by itself authorize a live shadow trial --
that remains a separate, explicitly scoped decision informed by this
report's semantic and non-semantic sections together, plus a materially
larger and more representative reviewed cohort than the one committed
alongside this contract.
