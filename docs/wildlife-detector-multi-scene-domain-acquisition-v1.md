# Multi-Scene Backyard Domain Acquisition + Holdout v2 v1 Report

Date: 2026-08-12
Decision: capability, governance, and tooling built; **no Stage-3 training run in this milestone**
Production authority changed: **no**

This report records the response to the generalization risk the Stage-3
Tranche A build disclosed: the existing 700-frame tranche (and the
2,000-frame queue it draws from, and the frozen-75 benchmark) come
primarily from one physical feeder/camera environment. See
[wildlife-detector-training-contract.md](wildlife-detector-training-contract.md)
"Scene identity and multi-scene acquisition" / "Feeder correction subset
v1" / "Holdout v2 scene/session governance" / "A practical first
multi-scene target" / "Stage-3 future corpus policy" / "Future split
policy" for the governing contract sections this implements, and
[wildlife-detector-stage3-tranche-a-report.md](wildlife-detector-stage3-tranche-a-report.md)
Section 5 for the confirmed feeder/frozen-75 near-duplicate rate that
motivated this milestone.

## 1. Starting point

Work started from committed baseline `dbd626ced94877d30ee54b6cab0970c94ca21380`
("Add Stage-3 local domain-correction Tranche A v1"). The existing
700-frame Stage-3 Tranche A (`data/training/wildlife-stage3/tranche-a.json`,
tranche id `mockingbird-wildlife-stage3-correction-tranche-a-v1`) and its
review packet/tooling (`stage3-tranche-review-build`) were consumed
unchanged and left untouched. The three pre-existing untracked
small-bird-benchmark prototype files and the four pre-existing `.orig`
backup files were left byte-for-byte untouched throughout.

## 2. Feeder correction subset v1 -- real composition

`scripts/select_wildlife_feeder_correction_subset.py` (`mockingbird.
training.wildlife_multiscene.select_feeder_correction_subset`) was run
against the real local 700-frame Tranche A. Result: **200 frames selected,
exactly on target (100/70/30)**, fingerprint
`6d67c2b22046a0c61e455bdbe722bfaba6256a0385fbcece528c35fe95733f65`.

| Lane | Target | Candidates (already in Tranche A) | Removed: perceptual similarity | Removed: above target | Selected |
| --- | ---: | ---: | ---: | ---: | ---: |
| `small_far_positive_opportunity` | 100 | 325 | 180 | 45 | 100 |
| `local_hard_negative_confusor` | 70 | 275 | 163 | 42 | 70 |
| `night_weather_edge_condition` | 30 | 100 | 31 | 39 | 30 |
| **Total** | **200** | **700** | **374** | **126** | **200** |

(`removed_by_temporal_cluster` is 0 for all three lanes -- Tranche A's own
700 rows are already same-session/same-time-bucket deduplicated, so no
further layer-1 collapse was available; the further reduction here is
entirely the stricter perceptual-similarity pass, consistent with
"prefer non-redundant encounters.")

**Session/scene concentration.** All 200 frames share one physical scene
by construction (`feeder_subset_scene_id="legacy-feeder-camera-pre-scene-
identity"`, a disclosed backfilled accounting label -- see the contract).
At the next-strongest lineage this legacy corpus carries (capture
session), 10 of Tranche A's 11 sessions are represented:

| Frames | Session |
| ---: | --- |
| 54 | `2026-08-06-stage6.10-representative-acceptance/session-03` |
| 40 | `2026-08-07-representative-shadow-acceptance/session-02-attempt-2` |
| 39 | `2026-08-07-representative-shadow-acceptance/session-02-attempt-3` |
| 29 | `2026-08-07-representative-shadow-acceptance/session-02-attempt-1` |
| 15 | `2026-08-06-stage6.10-representative-acceptance/session-04` |
| 11 | `2026-08-06-daylight-temporal-collection/session-02` |
| 6 | `2026-08-06-stage6.9-burst-scheduler-mechanics-smoke` |
| 4 | `2026-08-06-stage6.10-representative-acceptance/smoke-test` |
| 1 | `2026-08-06-daylight-temporal-collection/session-01` |
| 1 | `2026-08-06-stage6.12-fairness-mechanics-smoke` |

Most-concentrated single session: 54/200 (27%) -- no session dominates the
200-frame subset excessively, even though every frame shares one physical
scene.

The remaining ~500 Tranche A frames (and the full 2,000-row Stage-2 queue)
stay available under `data/training/wildlife-stage3/` and `data/training/
wildlife-stage2/` unchanged, but are not automatically training-eligible
for the default Stage-3 plan this contract now describes. No human truth
was created: every one of the 200 selected rows keeps `review_status:
"unreviewed"`/`training_eligible: False`, verified programmatically (`test_
select_feeder_correction_subset_hits_targets`/`_rejects_an_already_
reviewed_row`).

## 3. Scene identity design

`RetainedFrameRecord.scene_id`/`CaptureSessionConfig.scene_id`/
`capture_purpose` (`mockingbird.observation.temporal_capture`, `SCENE_ID_
PATTERN = ^[a-z0-9]([a-z0-9-]{0,62}[a-z0-9])?$`) are new, additive fields
recorded at both the session and per-frame level -- session level so a
session that retains zero frames (a genuinely quiet scene) never loses
which scene was checked; per-frame level mirroring the existing `holdout_
v2_candidate` pattern exactly. `CaptureSessionManifest.__post_init__`
cross-checks both for internal consistency.

`mockingbird.training.wildlife_multiscene.SceneFrameProvenance` is the
per-frame accounting record: `scene_id`, `capture_session_id`, `source_
camera` (`stream_id`), `capture_time`, `frame_id`, `content_hash` (exact
frame SHA-256), `width`/`height`, `capture_purpose` (training/holdout
eligibility), `high_resolution`, `capture_manifest` (lineage), and,
additively, `review_status`/`reviewer`/`reviewed_at` when an already-loaded
review `AnnotationSet` is supplied -- exactly the task's required field
list. `scan_scene_manifests` reads it back from real capture manifests,
scanning each distinct manifest at most once.

A scene is never inferred from a session id, stream id, or small camera
nudge -- always operator-supplied via `--scene-id`, now a required
`temporal-capture` argument.

## 4. Multi-scene acquisition workflow

`temporal-capture` (unchanged Camera Node/exact-analysis-capture
architecture, no new transport or provider) gained two new arguments:

- `--scene-id <id>` (required): the stable physical scene this session
  belongs to.
- `--capture-purpose {training_candidate,holdout_v2_candidate}` (default
  `training_candidate`): the explicit-purpose successor to the prior
  boolean `--holdout-v2-session` flag, reusing the identical underlying
  `RetainedFrameRecord.holdout_v2_candidate` mechanism.

A running capture also now stops early and finalizes its manifest cleanly
(`stop_condition="manual_stop"`) on one Ctrl-C (SIGINT) or SIGTERM, closing
a real gap: before this milestone, an interrupted capture raised an
uncaught `KeyboardInterrupt` straight through `_run_capture`, skipping
manifest assembly entirely and losing the whole session's lineage (the
retained JPEG bytes on disk survived; the manifest that makes them usable
did not). `STOP_MANUAL` already existed in `temporal_capture.py`'s stop-
condition vocabulary, unused, since the module was first built -- this
milestone is the first to wire it up.

Capture remains local, bounded (unchanged `CaptureBounds`), observable
(unchanged manifest/print output), and explicitly enabled (still requires
an authenticated Camera Node connection config). Nothing here retains
unlimited video or every frame forever -- the existing bounded-trigger
retention policy (`_CaptureLoop`) is completely unchanged.

## 5. Holdout v2 isolation rules

A scene/session is Holdout v2 the moment every capture ever taken for it
used `--capture-purpose holdout_v2_candidate` (derived from real captured
provenance via `scene_capture_purposes`/`holdout_v2_scene_ids`, never a
separately maintained registry). A scene captured under conflicting
purposes is a surfaced error (`assert_no_scene_purpose_conflict`), never
silently resolved.

Once declared:

- **Fails closed at the scene/session level**:
  `assert_scene_session_holdout_isolation` raises the moment any row's own
  `scene_id`/`capture_session_id` matches a declared Holdout v2 scene/
  session -- independent of that row's own per-row flag (a second,
  coarser-grained layer on top of the existing frame-level `holdout_v2_
  candidate` exclusion `wildlife_stage3_tranche.select_tranche` already
  enforces).
- **Fails closed on derived crops and neighboring sequence frames**:
  `holdout_v2_records` builds the same `HoldoutRecord` shape `wildlife.
  verify_frozen_benchmark` returns for the frozen-75, so the existing,
  already-tested `wildlife.contamination_report` protects a captured
  Holdout v2 scene with zero new contamination logic -- exact SHA-256,
  source/parent identity (catches a derived crop once crop generation
  exists), site/camera/sequence lineage (catches a neighboring burst/
  sequence frame from the same session even when its own pixels differ
  enough to dodge the hash checks -- proven directly against a real,
  deliberately unrelated-pixel synthetic example, not merely claimed; see
  `test_holdout_v2_records_catch_a_neighboring_sequence_frame_via_
  lineage`), and dual-hash near-duplicate.
- **No threshold tuning or early stopping**: a process discipline this
  report documents; no code path in the current pipeline reads per-scene
  local data for threshold selection yet, so there is nothing additional
  to guard today beyond the isolation check above.

No real Holdout v2 corpus was collected in this milestone -- this is
capability and governance only, exactly like the prior "Holdout v2
groundwork" milestone's own scope, extended from the frame level to the
scene/session level.

## 6. Proposed first scene plan / training-vs-holdout allocation

Six scenes -- four training, two Holdout v2 -- meets the lower-bound
readiness bar (5 total / 3 training / 2 holdout) inside the task's own 5-8
scene target range:

| Scene id | Purpose | Why |
| --- | --- | --- |
| `feeder-close` | training | Continuity check against the legacy corpus; confirms the workflow before spending time on new ground. |
| `lawn-open` | training | Open-ground small/far bird and squirrel opportunity; vegetation motion, no feeder clutter. |
| `deck-patio` | training | Pavement/hardscape confusors, different lighting geometry. |
| `fence-garden` | training | Fence-line confusors, dense vegetation/shadow texture distinct from the feeder scene. |
| `woods-tree-line` | **holdout v2** | Materially distinct camera position; branch/bark/dappled-shadow confusors (a known recurring frozen-75 failure family) captured somewhere the model has never trained on. |
| `driveway-or-ground-level` | **holdout v2** | A structurally different vantage, maximizing independence from every training scene above. |

`feeder-close` deliberately continues the existing corpus rather than
replacing it -- "adapt style, do not redefine the detector as a feeder
detector" (Stage-3 future corpus policy, layer B/C) still needs feeder-scene
coverage, just no longer *disproportionate* coverage. No scene is required
to contain an animal before it is useful; empty frames, vegetation motion,
branches/bark, shadows, fences, pavement, and different lighting/weather
are all explicitly acceptable and expected. Wildlife is never manufactured.

## 7. Review workflow

Reuses the existing browser localization reviewer unchanged.
`scripts/build_wildlife_scene_review_tranche.py` (`mockingbird.training.
wildlife_multiscene.build_scene_review_tranche`) filters already-scanned
scene provenance to one scene and/or one session and re-packages it into
the exact tranche JSON shape `stage3-tranche-review-build` already
consumes -- proven directly, not merely claimed:
`test_build_scene_review_tranche_packet_is_consumable_by_the_existing_
reviewer` feeds a real built packet through the unmodified `build_stage3_
tranche_review_packet` + `validate_annotations` pipeline and confirms it
validates cleanly. Human truth rules are completely unchanged: Animal
requires human box(es), No animal requires explicit human action,
Ambiguous is training-ineligible, model suggestions remain non-
authoritative. No species identification was added.

## 8. Scene-diversity / readiness report

`scripts/report_wildlife_scene_diversity.py` (`mockingbird.training.
wildlife_multiscene.scene_diversity_report`) was run against the real
local corpus on 2026-08-12:

```
Multi-scene diversity / readiness report
  total_scenes=1 training_scenes=1 holdout_scenes=0
    legacy-feeder-camera-pre-scene-identity: purpose=training_candidate sessions=10 frames=200 reviewed(+0/-0/?0) boxes=0 size_buckets={}
  concentration: most=legacy-feeder-camera-pre-scene-identity fraction=1.00 warning=True (visibility only, threshold=0.5)
  feeder subset session concentration: most=.../2026-08-06-stage6.10-representative-acceptance/session-03/capture-out fraction=0.27 of 200 frames
  FIRST_MULTISCENE_TARGET_MET=False
  not yet met because:
    - fewer than 5 total scenes (1)
    - fewer than 3 training scenes (1)
    - fewer than 2 Holdout v2 scenes (0)
```

Honest and expected: no new scene has been physically captured yet. The
100% training-scene concentration is flagged (the visibility heuristic
this task asked for, `SCENE_CONCENTRATION_WARNING_FRACTION=0.5`), never
enforced -- nothing in this pipeline blocks review or training because of
it. The report is designed to reflect real progress automatically the
moment new scenes are captured, with no code change required (`--scene-
manifest-root` already scans `data/field-acceptance` recursively for any
manifest carrying a `scene_id`).

## 9. Tests and validation

70 new focused tests: `tests/test_wildlife_multiscene.py` (39: stable scene
identity, exact-frame retention/dimensions, scan-once-per-manifest
determinism, review-provenance join, size-bucket computation, feeder-subset
targets/determinism/tampered-fingerprint/wrong-tranche/already-reviewed/
lane-unavailable rejection, session concentration, scene-purpose
conflict detection, holdout scene/session fail-closed isolation
(including a "wrong scene but matching session" case), derived-crop/
neighboring-sequence-frame exclusion via `HoldoutRecord`/`contamination_
report` reuse, scene-diversity concentration/target-met accounting, and
scene/session review-tranche building including a real end-to-end packet
consumed by the unmodified existing reviewer), plus 8 new tests in `tests/
test_temporal_capture_cli.py` (`--scene-id` required/threading, `--capture-
purpose` default/choices/rejection, manual-stop-before-duration, and one
real end-to-end `run_capture` proving the written manifest carries both new
fields).

Full relevant existing suites run clean alongside the above (see the final
report for the exact combined command/counts): exact-frame capture
(`test_temporal_capture.py`, `test_temporal_capture_cli.py`, `test_
temporal_capture_io.py`), Stage-3 tranche (`test_wildlife_stage3_tranche.py`,
`test_wildlife_stage3_readiness.py`), benchmark governance (`test_wildlife_
training.py`, `test_detector_promotion.py`), human localization review
(`test_temporal_annotation.py`, `test_temporal_review_io.py`), Geometry
Attribution (`test_localization_attribution.py`), and Counterfactual
Lineage (`test_counterfactual_lineage.py`). Ruff is clean on every file
this session touched. The real end-to-end feeder-subset-selection and
scene-diversity-report pipelines were run against real local data, not
mocked (Sections 2 and 8, above).

## 10. Commit

One coherent local commit contains the scene-identity capture/manifest
changes, the new `wildlife_multiscene` module, the three new scripts, the
contract/report documentation, and the tests. The generated feeder-subset
JSON stays under ignored `data/training/wildlife-feeder-subset/` and is
not committed. The three pre-existing untracked small-bird-benchmark files
and four `.orig` backup files remain untouched and untracked. The exact
commit SHA is reported in the completion handoff; nothing is pushed.

## 11. Operator instructions

### Start a training-candidate acquisition session for a named scene

```bash
.venv/bin/python -m mockingbird temporal-capture \
  --camera-node-config <camera-node-config.json> \
  --provider frame-driven-onnx-cuda --provider-config <frame-driven-config.json> \
  --output data/field-acceptance/<field-session-name>/<scene-id>-training \
  --duration 600 \
  --scene-id lawn-open \
  --capture-purpose training_candidate
```

### Start a Holdout-v2 acquisition session

```bash
.venv/bin/python -m mockingbird temporal-capture \
  --camera-node-config <camera-node-config.json> \
  --provider frame-driven-onnx-cuda --provider-config <frame-driven-config.json> \
  --output data/field-acceptance/<field-session-name>/<scene-id>-holdout-v2 \
  --duration 600 \
  --scene-id woods-tree-line \
  --capture-purpose holdout_v2_candidate
```

### Stop/finalize

Press **Ctrl-C once** in the terminal running `temporal-capture` (or send
`SIGTERM`) at any point once a scene is judged sufficiently covered; the
session stops cleanly and writes its manifest immediately
(`stop_condition=manual_stop`) instead of running the full `--duration`.
Otherwise it stops and finalizes on its own once `--duration` elapses or a
resource bound (`--max-analysis-frames`/`--max-bytes-stored`/
`--max-high-resolution-frames`) is reached -- no separate stop command is
needed either way; this is a bounded foreground command, not a daemon.

### Build a human-review packet for one scene

```bash
.venv/bin/python scripts/build_wildlife_scene_review_tranche.py \
  --scene-manifest-root data/field-acceptance \
  --scene-id lawn-open \
  --output data/training/wildlife-multiscene/lawn-open-tranche.json

.venv/bin/python -m mockingbird stage3-tranche-review-build \
  --tranche data/training/wildlife-multiscene/lawn-open-tranche.json \
  --output data/training/wildlife-multiscene/lawn-open-review
```

Then open `data/training/wildlife-multiscene/lawn-open-review/index.html`
in a browser -- the identical reviewer Stage-3 Tranche A already uses.
Validate with:

```bash
.venv/bin/python -m mockingbird temporal-review-validate \
  --review data/training/wildlife-multiscene/lawn-open-review
```

### Check multi-scene readiness

```bash
.venv/bin/python scripts/report_wildlife_scene_diversity.py
```

Add `--scene-review lawn-open:data/training/wildlife-multiscene/lawn-open-review`
(repeatable, one per reviewed scene) once review packets exist, to fold
real reviewed positive/negative/ambiguous/box counts into the report.
Add `--json` for machine-readable output.

## 12. What the human should physically do next

Physically move the camera (or add a second Camera Node) to cover the six
proposed scenes (Section 6), running one bounded `temporal-capture`
session per scene with the commands above -- four `training_candidate`
sessions, two `holdout_v2_candidate` sessions, each a natural single field
visit's duration (the existing `--duration`/bounds defaults, or an early
Ctrl-C once a scene feels covered). No Stage-3 correction subset review
needs to be complete first; the two workflows (feeder-subset review and
new-scene capture) are independent and can proceed in either order or in
parallel.

## 13. Exact next milestone

Once real multi-scene captures exist: run `scripts/report_wildlife_scene_
diversity.py` to confirm the first multi-scene target is met, build and
complete human review of each training scene (Section 7) and the existing
feeder correction subset (200 frames, prioritizing `small_far_positive_
opportunity` first, exactly as the Stage-3 Tranche A report already
recommends), then materialize the five-layer Stage-3 corpus this report's
"Stage-3 future corpus policy" section defines (A sealed public Stage-2
corpus + B/C reviewed local training scenes, capped feeder subset + D
separate local validation scenes + E isolated Holdout v2), and train a new
RF-DETR Small experiment identity for at least 10 epochs with early
stopping -- requiring frozen-75 recall and false-detection rate to both
improve over Stage-2, *and* requiring a first honest Holdout v2 evaluation
before any shadow-deployment consideration. No detector is trained in this
milestone.
