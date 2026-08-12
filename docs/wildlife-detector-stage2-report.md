# Wildlife Detector Stage-2 Integration Report

Date: 2026-08-12
Decision: **PIPELINE_PROVEN_MODEL_WEAK**
Production authority changed: **no**

This report records completion of a Stage-2 run interrupted mid-training by
the previous agent's exhausted execution credits: the checkpoint-staging
defect that caused the interruption, independent recovery verification of
the epoch-0 checkpoint, a real optimizer/scheduler resume proof, training
through early stopping, and a full three-way comparative evaluation against
Stage-1 RF-DETR and unchanged production MDv5. Generated pixels,
checkpoints, and reports remain under ignored `data/training/wildlife-stage2/`.

## 1. Checkout identity

Work resumed from committed baseline `0c387a68e1d60dd8df8202c6f74636bd5731441a`
("feat: prove Stage-1 wildlife detector training pipeline"). The interrupted
run had left tracked edits to this contract and to
`src/mockingbird/training/wildlife.py`, five new untracked Stage-2 scripts/
registry files, and `.orig` backups pinpointing exactly where each edit
stopped. The final HEAD is the local integration commit containing this
report; no push is authorized or performed.

A stale, fully hung process from the interrupted session (6+ hours idle in
`epoll_wait`, zero forward progress, a separate sandbox wrapper unrelated to
this session) was found and terminated during inspection; this is OS-process
cleanup, not a worktree change.

## 2. Checkpoint atomic-staging fix

`pytorch_lightning`'s `_atomic_save` writes each checkpoint through an
`fsspec` local-filesystem transaction. Inside that transaction,
`fsspec.implementations.local.LocalFileOpener._open` stages the write with a
bare `tempfile.mkstemp()` -- no `dir=` -- so the staging file lands wherever
`tempfile.gettempdir()` resolves, independent of the checkpoint's
destination directory. Commit then does `shutil.move(staged, destination)`:
same-filesystem, a cheap atomic `os.rename`; cross-filesystem (confirmed live
in this sandbox: WSL2's native ext4 root versus `/mnt/c`, the Windows drive
mounted over 9p, really do report different `st_dev` and really do raise
`OSError(EXDEV)` on a direct rename), it falls back to a full copy of the
~500 MB file, which is exactly what failed once under host memory pressure
and produced the epoch-0 recovery this report continues from.

The fix, `_stage_checkpoint_tempdir` in `scripts/train_wildlife_stage2_rfdetr.py`,
runs before the `torch`/`rfdetr` imports on every invocation and stages
inside the checkpoint output directory itself (`.checkpoint-staging/`),
which guarantees the same device for every write this process makes -- not
merely "the same top-level filesystem" -- by setting `tempfile.tempdir`
directly (authoritative regardless of import order) and `TMPDIR`/`TEMP`/`TMP`
(covers any subprocess or C extension reading the environment directly).
Four focused tests in `tests/test_wildlife_stage2_checkpoint_staging.py`
cover it, including a direct reproduction of fsspec's stage-then-rename
sequence. It then held for all 12 real checkpoint writes plus 3 best-model
exports made resuming training in this report (Section 6); nothing strayed
onto `/mnt/c` or the default `/tmp`.

## 3. Recovered checkpoint verification and resume proof

`checkpoint_0.ckpt` was independently verified by direct `torch.load`
(`map_location="cpu"`, `weights_only=False`, `mmap=True`), not by trusting
the pending recovery script alone:

- SHA-256 `c402f83a19ac67719caabe6517870968bccf8970cddb105c75e43036bbdfadd5`,
  517,421,265 bytes -- exact match to the claimed recovery.
- `epoch=0`, `global_step=888`.
- Optimizer state present (AdamW, 486 tracked parameter states with
  `exp_avg`/`exp_avg_sq`/`step`).
- Scheduler state present (step schedule, `last_epoch=888`, `_step_count=889`).
- Model `state_dict` present (488 tensors, ~32.28M elements).
- AMP `GradScaler` state present (`MixedPrecision` key: `scale=2048.0`,
  `_growth_tracker=393`) and EMA shadow-weight callback state present
  (`RFDETREMACallback.average_model_state_dict`) -- both beyond the
  contract's minimum bar.
- Experiment identity matches the sealed corpus: `corpus_fingerprint`
  `2261e716a398185ccb9def87d6555726da35c74c801169b8ac97483dce179af5`,
  `split_fingerprint`
  `18513c4e5f07f8c9d4e7eadfbbaf75d9745cbb4f593126b37aabe5add1adba92`.

The script's own `--finalize-recovered-initial` path was then run to produce
official evidence (`initial-result.json`,
`completion_status: recovered_after_cross_filesystem_atomic_commit_failure`).

The real resume smoke test is direct, not synthetic: resuming produced an
epoch-1 metrics row whose learning rate (`5e-05`, fully warmed up) continues
exactly where epoch 0 left off rather than restarting warmup, and the
post-resume run went on to write `checkpoint_1.ckpt` (517,421,265 bytes)
through the new staging path with no failure -- concrete, real-hardware
proof of both correct optimizer/scheduler restoration and the staging fix,
not a mocked check.

## 4. Corpus (already sealed, unchanged by this session)

8,000 examples: 6,000 positive / 2,000 negative, 100% target-domain,
48.2% small/very-small positives, 781 independent validation groups.
Semantic fingerprint starts `2261e716`; split fingerprint starts `18513c4e`.
Zero frozen-75 exact, lineage, or corroborated perceptual collisions
(`contamination.passed` and `internal_split_contamination.passed` both
`true`; all four collision categories empty). Accepted sources: Oregon
Critters, Channel Islands Camera Traps, ENA24-detection, human-corrected
NACTI boxes, plus Stage-1's Caltech Camera Traps; COCO is `transfer_only`
and excluded from this materialization. Validation-split positive size
buckets: 245 large, 155 medium, 238 small, 12 very_small (650 positives).

## 5. Exact RF-DETR configuration

RF-DETR Small, initialized from Stage-1's `checkpoint_best_total.pth`
(SHA-256 `b14581ebb0eed43675a229acec304a71fbc0b50ff8640d26acd95ee7f1564d1a`);
`rfdetr` 1.8.3, wheel SHA-256
`345e55b897ce590464e64ae4750e60b668436cbc6bf58d87f438895a93c3e9a4`.
Resolution 768; gradient checkpointing; batch 1; accumulation 8; effective
batch 8; AdamW; LR 5e-5, encoder LR 7.5e-5; weight decay 1e-4; step
scheduler with `lr_drop=11`; FP16; EMA; seed 260812; bounded
brightness/contrast only (no horizontal flip -- removed from the config
before the epoch-0 run that produced the recovered checkpoint); 1,000
governed source-pixel context crops, train-only; multi-scale disabled;
early stopping enabled only after a 10-epoch floor, patience 3, min_delta
0.001, monitored on EMA Stage-2-validation mAP50:95. Experiment fingerprint
`2019b7a83b3d8d0c47f155c282d3b777b8b0aa43b16caa2978c040d022a96f07`,
confirmed identical across preflight-refresh, the recovered epoch-0 run, and
the full resume run via `rfdetr`'s own independent `training_config.json`
dump.

## 6. Training, checkpoint, and resume proof

Epoch 0 (recovered, Section 3) reached EMA mAP50:95 0.4430. Resuming from
`checkpoint_0.ckpt`, training ran epochs 1 through 12 (13 total completed
epochs) and stopped there: epoch 9 was the best EMA-mAP50:95 epoch
(0.4910), and epochs 10, 11, and 12 -- exactly `early_stopping_patience`
consecutive non-improving epochs after the mandatory 10-epoch floor -- each
failed to beat it by `min_delta`, so training stopped at the earliest
point the contract's early-stopping rule allows. This is legitimate
early stopping, not a truncated or failed run. Every one of the 12
additional `checkpoint_N.ckpt` writes plus the 3 best-model exports
completed cleanly through the new staging fix.

| epoch | mAP50:95 | EMA mAP50:95 | F1 | precision | recall |
|---|---|---|---|---|---|
| 0 (recovered) | 0.4228 | 0.4430 | 0.7493 | 0.8388 | 0.6771 |
| 1 | 0.4489 | 0.4665 | 0.7694 | 0.8283 | 0.7184 |
| 2 | 0.4585 | 0.4760 | 0.7880 | 0.8399 | 0.7422 |
| 3 | 0.4552 | 0.4717 | 0.7891 | 0.8455 | 0.7397 |
| 4 | 0.4630 | 0.4749 | 0.8091 | 0.8737 | 0.7534 |
| 5 | 0.4563 | 0.4819 | 0.7818 | 0.8721 | 0.7084 |
| 6 | 0.4682 | 0.4842 | 0.7978 | 0.8782 | 0.7309 |
| 7 | 0.4723 | 0.4826 | 0.7898 | 0.8825 | 0.7146 |
| 8 | 0.4690 | 0.4786 | 0.8037 | 0.8612 | 0.7534 |
| **9 (best)** | **0.4837** | **0.4910** | 0.8082 | 0.8569 | 0.7647 |
| 10 | 0.4658 | 0.4807 | 0.7866 | 0.8303 | 0.7472 |
| 11 | 0.4781 | 0.4796 | 0.7947 | 0.8408 | 0.7534 |
| 12 | 0.4812 | 0.4804 | 0.7984 | 0.8724 | 0.7359 |

Best checkpoints (all from epoch 9, the point early stopping locked in):

| checkpoint | bytes | SHA-256 |
|---|---|---|
| `checkpoint_best_ema.pth` | 129,345,175 | `ac30e0749e46fdea328fbb72ea7227be879641e2c8876c9a4a96918d8864ac55` |
| `checkpoint_best_regular.pth` | 129,379,727 | `fd7f5d5d6c640e1a87908330fe5fb904b143df4c54e0279caae71045b7f9060a` |
| `checkpoint_best_total.pth` | 129,333,031 | `95880d6915c24bea6f3b53bccce0611fad98f3a9f51c6a9798c60796f78c4952` |

Full per-epoch resumable checkpoints (`checkpoint_0.ckpt` through
`checkpoint_12.ckpt`, ~517 MB each) and their individual hashes are recorded
in `resume-result.json`. GPU: NVIDIA GeForce RTX 4060 Ti; PyTorch
`2.13.0+cu130`; CUDA runtime `13.0`; peak measured allocation
1,225,731,584 bytes / reserved 1,350,565,888 bytes.

## 7. Evaluator defects found and fixed running this for the first time

Both were genuine, previously-unexercised bugs (this evaluation code path
had never run to completion before -- Stage-2 checkpoints didn't exist
until this session), not pre-existing regressions, and neither weakens any
production check:

- **`EvaluationBox` boundary tolerance.** Three of 799 real Stage-2
  validation truth boxes touch an image's right/bottom edge exactly; float
  summation in `(x + w) / image_width` lands a few ULPs past 1.0
  (`overshoot ~1e-15`), and the strict `right > 1` check rejected them. Fixed
  with the same `1e-6` tolerance this file already uses for the identical
  source-pixel boundary case elsewhere (`PixelBox.normalized_xyxy`,
  `context_crop_bounds`); still rejects a genuinely invalid box. Two new
  tests in `tests/test_wildlife_training.py`.
- **MDv5 input normalization.** `onnx_provider._preprocess` (production
  code, left untouched) correctly rejects two conditions that real Stage-2
  corpus frames hit: MPO, the multi-picture-JPEG container some Oregon
  Critters trail-camera frames use (PIL decodes it fine, same as the
  RF-DETR side of this comparison, but reports a distinct format string),
  and `MAX_INPUT_PIXELS` (16,777,216 px), which 4 Oregon Critters frames
  (5280x3960, ~20.9MP) exceed by about 25%. Both are corpus-provenance
  artifacts -- a real Camera Node never produces either -- not production
  bugs. `_onnx_provider_compatible_bytes` in `scripts/evaluate_wildlife_stage2.py`
  re-encodes/downscales exactly those frames to what production already
  accepts before they reach the adapter, importing the real
  `MAX_INPUT_PIXELS` constant rather than duplicating it, so every model in
  the comparison still scores the same corpus on the same pixel content.
  Five new tests in `tests/test_evaluate_wildlife_stage2.py`.
- **CUDA pre-warm ordering.** `torch.cuda.reset_peak_memory_stats(0)` --
  explicit device index -- raises `RuntimeError: Invalid device argument` on
  this torch build (`2.13.0+cu130`) when called before any real CUDA
  allocation in the process; reproduced in isolation. The no-arg form
  resolves through `current_device()`, which lazily initializes CUDA as a
  side effect and so works pre-warm, and is equivalent here since this
  codebase is single-GPU only. One-line fix in `_run_rfdetr`.

## 8. Stage-2 validation metrics

900 images (650 positive / 250 negative, 799 truth boxes). Threshold 0.3
maximized F1 on Stage-2 validation only (never the frozen set):

| model | precision | recall | F1 | mean IoU | FDR/neg |
|---|---|---|---|---|---|
| Stage-2 RF-DETR (0.3) | 0.8468 | 0.7747 | 0.8092 | 0.8024 | 0.0840 |
| Stage-1 RF-DETR (0.5, fixed) | 0.7937 | 0.4380 | 0.5645 | 0.7965 | 0.1080 |
| Production MDv5 (0.1, unchanged) | 0.8665 | 0.8773 | **0.8719** | 0.8402 | 0.0800 |

Stage-2 clearly beats Stage-1 in-domain, but unchanged MDv5 still leads on
its own governed validation set. Size recall (Stage-2): large 0.9140,
medium 0.8231, small 0.6098, **very_small 0.0 (0/12)**. By taxonomic group:
mesocarnivore F1 0.9075, ungulate F1 0.9206, bird F1 0.8016, small_mammal
F1 0.8077, **reptile_amphibian F1 0.0 (0/10, complete miss)**. By source:
Caltech F1 0.744, Channel Islands F1 0.829, Oregon Critters F1 0.796 --
consistent across the three target-domain sources in-domain.

## 9. Frozen MockingBird benchmark (the holdout that matters)

64 scorable frames of 75. Frozen thresholds are fixed (Stage-2 selected 0.3
from validation only, then applied unchanged; Stage-1 fixed at 0.5; MDv5
unchanged at 0.1):

| model | precision | recall | F1 | mean IoU | FDR/neg | TP/FP/FN |
|---|---|---|---|---|---|---|
| Stage-2 RF-DETR | 0.0405 | 0.1071 | 0.0588 | 0.6417 | **0.8611** | 3/71/25 |
| Stage-1 RF-DETR | 0.5000 | 0.0714 | 0.1250 | 0.7899 | 0.0278 | 2/2/26 |
| Production MDv5 | 0.2703 | 0.3571 | **0.3077** | 0.7856 | 0.2778 | 10/27/18 |

Recall at IoU 0.25/0.50/0.75 (Stage-2): 0.1786 / 0.1071 / 0.0357.
Recall by size (Stage-2 and Stage-1 alike): large 0.0, medium ~0.09-0.13,
**small 0.0** -- no frozen very_small truth boxes exist to score. By
distance (Stage-2): "typical" F1 0.0870 (3 TP / 39 FP / 24 FN); "far" F1
0.0 (0 TP / 1 FP / 1 FN).

## 10. Key question, answered directly

Stage-2 recall improved marginally over Stage-1 (0.0714 -> 0.1071, +0.036)
but F1 got **worse** (0.1250 -> 0.0588), because precision collapsed
(0.5000 -> 0.0405): false detections per frozen negative frame rose
**31x** (0.0278 -> 0.8611), well past even unchanged MDv5's 0.2778. Stage-2
does **not** close the recall/F1 gap to MDv5, and it does **not** retain
Stage-1's hard-negative advantage on real local footage.

This is not a corpus-quality failure in general -- it is a precise,
diagnosable domain gap. On the governed 2,000-frame hard-negative pool
(camera-trap-style, same distribution as training), Stage-2 is the
**best** of all three models by a wide margin: false detections per
negative frame 0.0057-0.0218 versus Stage-1's 0.0271-0.0515 and MDv5's
0.0871-0.1014. The skill Stage-2 learned is real, but it is
"camera-trap-style empty vs. animal," not "MockingBird's own local camera
empty vs. animal" -- and the frozen 75-image set, drawn from the latter,
is exactly what catches that gap. Small/far recall, the primary decision
metric, remains 0.0 on frozen for both RF-DETR candidates.

## 11. Hard-negative performance (governed pool)

2,000 frames (700 `camera_trap_empty_false_trigger`, 1,282
`camera_trap_empty_scene`, 18 `local_static_clutter_night`). Stage-2: FDR
0.0057 / 0.0218 / 0.0000. Stage-1: 0.0271 / 0.0515 / 0.0000. MDv5: 0.0871 /
0.1014 / 0.0000. This pool is training-adjacent, not an unbiased holdout
(see Section 10); it is reported because the contract requires it, not as
a substitute for the frozen result.

## 12. Latest diagnostic birds (excluded from all population metrics)

Stage-2 recovered 2/5: `latest-candidate-014-identification` (conf 0.871,
IoU 0.561) and `latest-candidate-012-context-control` (conf 0.502, IoU
0.561). Stage-1 recovered 0/5 (unchanged from the Stage-1 report).
Unchanged MDv5 recovered 3/5 (`013`, `014`, `012-context-control`). Stage-2
is a real improvement over Stage-1 here but still trails MDv5 by one case,
and both `011` and `013` remain undetected by Stage-2 despite `013` being
one of MDv5's hits.

## 13. Latency, FPS, VRAM, model size

| model | median inference (validation) | FPS | peak VRAM alloc/reserved | model size |
|---|---|---|---|---|
| Stage-2 RF-DETR (768px) | 65.66 ms | 15.23 | 493,471,232 / 767,557,632 bytes | 129,345,175 bytes |
| Stage-1 RF-DETR (640px) | 64.24 ms | 15.57 | 459,548,160 / 715,128,832 bytes | 128,251,559 bytes |
| Production MDv5 (1280px ONNX) | 157.80 ms | 6.34 | n/a (ONNX Runtime session) | 562,557,546 bytes |

Both RF-DETR variants comfortably out-run and out-fit unchanged MDv5 on
this GPU; that was never the open question -- generalized detection
quality on real local footage was, and it is not yet resolved favorably.

## 14. Local-correction queue status

The deterministic 2,000-frame queue (`mockingbird-local-wildlife-correction-v0.2`,
fingerprint `93859bdb334cfaa8151e9c783492cd33e71282a36b994e9658b1205f00473b08`)
is unchanged by this session: 1,000 small/far bird lane, 750
clutter/vegetation negative lane, 250 night/weather/edge lane. 18 frames
already have prior human-reviewed negative truth; **1,982 still require
named human review** and were not manufactured. Given Section 10's
diagnosis, this queue's negative lanes (local clutter/vegetation, 750
frames; night/weather/edge, 250 frames) are precisely the missing signal:
Stage-2 has already proven it can learn strong empty-vs-animal
discrimination when given matching-style negatives, and the frozen holdout
is telling us the training corpus's negatives are not yet that style.

## 15. Verification

New/changed regression coverage: 4 tests for the checkpoint-staging fix, 2
for the `EvaluationBox` boundary tolerance, 5 for MDv5 input normalization
-- 11 new tests, all passing. Full focused suite (Stage-2 corpus/provenance,
anti-leakage/contamination, checkpoint staging, exact-frame capture, human
localization provenance, detector promotion, Geometry Attribution,
Counterfactual Lineage) run before commit; results and count in the
completion handoff. Ruff is clean on every file this session touched;
pre-existing repository-wide ruff findings outside this session's scope
were left alone.

## 16. Commit

One coherent local commit contains code, tests, the corpus-composition
tweak already baked into the recovered checkpoint, the registry, and both
documents. Datasets, checkpoints, and caches under ignored `data/` are not
committed. The exact commit SHA is reported in the completion handoff;
nothing is pushed.

## 17. Stage-2 decision

**PIPELINE_PROVEN_MODEL_WEAK.** Corpus governance, materialization, the
recovered-checkpoint resume proof, 13-epoch CUDA training with legitimate
early stopping, and full three-way evaluation all worked correctly end to
end -- including finding and fixing three real defects along the way. The
model itself is not yet a shadow-validation candidate: it improves
meaningfully in-domain and on the governed hard-negative pool, but loses
precision catastrophically on real local footage, and still does not
detect small/far animals there at all.

## 18. Should the full Wildlife Training Corpus v0 be materialized now?

**No.** Scaling the current corpus composition and recipe to 131,500 images
would scale the domain gap, not close it: Stage-2 already demonstrates the
pipeline learns fast and generalizes well *within* professional
camera-trap-style imagery, so more of that same style is unlikely to move
the frozen result. The evidence points at corpus *composition* (needs
MockingBird's own local negative/positive style, not merely more volume),
not corpus *size* or pipeline mechanics.

## 19. Exact next milestone

Do not scale this checkpoint's recipe unchanged, and do not re-tune further
against the frozen 75-image benchmark. Get the 1,982 pending frames in the
existing local-correction queue through **named human** full-frame review
(1,000 small/far bird positives, 750 static-clutter/vegetation negatives,
250 night/weather/edge negatives) -- no agent- or model-generated label may
enter this truth. Materialize a Stage-3 corpus that blends the current
sealed Stage-2 target-domain examples with this newly-reviewed local set,
holding whole camera sessions disjoint from validation exactly as Stage-2
already does. Train a new RF-DETR Small experiment identity for at least 10
epochs with early stopping on the new local-inclusive validation split, and
require frozen recall and false-detection rate to both improve over this
Stage-2 result (recall > 0.1071, false detections/negative frame < 0.8611,
ideally back toward or past Stage-1's 0.0278) before any shadow-deployment
consideration.
