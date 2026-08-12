# Wildlife Detector Stage-1 Integration Report

Date: 2026-08-11
Decision: **PIPELINE_PROVEN_MODEL_WEAK**
Production authority changed: **no**

This report records the real 1,200-image corpus build, two-epoch GPU
checkpoint/resume proof, and evaluation run. Generated pixels, checkpoints,
and reports remain under ignored `data/training/wildlife-stage1/`.

## 1. Checkout identity

The work started at required HEAD
`7a19d40904ee67d261920c53fe2b4ef9ba33ab7e`. The final HEAD is the local
integration commit containing this report; no push is authorized or performed.

## 2. Bundle integration and rejection

No separately identifiable previous standalone bundle was present in the
checkout or supplied attachment, so no unverifiable code was copied blindly.
The requested concepts were integrated natively: governed source registry,
materializer and fingerprints, anti-leakage/contamination logic, RF-DETR
training and evaluation scripts, exact-frame envelopes, and a human localization
reviewer. Pre-existing untracked small-bird benchmark files were preserved and
excluded from this change. Agent/model truth, unclear-license sources,
unsupported MDV6 training, species review, and any production model/default
change were rejected.

## 3. MDV6 name and provenance reconciliation

The previous benchmark did **not** test an abstract `MDV6-C`. It tested:

- `MDV6-apa-rtdetr-c`, RT-DETRv2 PResNet-18, Apache-2.0, SHA-256
  `4814cdbc9a0dbf20e4b04495f060176d8340b00d182fc98ce808a4d14a2a6fce`;
- `MDV6-apa-rtdetr-e`, RT-DETRv2 PResNet-101, Apache-2.0, SHA-256
  `8017129225455be75998195453282f1984aa1c46ebb77b05dd7db97f1bf79117`.

Both records point to Zenodo record 18164133 and PytorchWildlife package
artifact SHA-256
`3215c1041ae52481a96d25dbe3fa509a3db5a814395a08bb2e0ab259a260d57d`.

Current official MegaDetector fine-tuning documentation names
`MDV6-yolov9-c/e`, `MDV6-yolov10-c/e`, and `MDV6-rtdetr-c`; it does not name
the benchmarked `MDV6-apa-rtdetr-c/e` artifacts as supported fine-tuning
inputs. A YOLOv9-C or non-Apache RT-DETR-C run would be a new model identity,
not continuation of the benchmarked candidate. Therefore the exact benchmarked
MDV6 line is `BLOCKED_OFFICIAL_FINE_TUNE_PATH`; no improvised conversion or
misleading short-name reuse was attempted. Sources:
[MegaDetector repository](https://github.com/microsoft/MegaDetector),
[model zoo](https://microsoft.github.io/MegaDetector/model_zoo/).

## 4. Accepted sources

- Caltech Camera Traps: bounding boxes 20200316, image labels 20210113,
  CDLA-Permissive-2.0, Southwestern United States, human boxes and curated
  empties, location/sequence/capture metadata. Canonical source:
  [LILA Caltech Camera Traps](https://lila.science/datasets/caltech-camera-traps).
- COCO 2017 animal subset: human instance boxes, CC BY 4.0 annotations, images
  restricted to license IDs 4, 7, or 8. Geography is unknown/mixed and is not
  claimed as North American. Canonical source:
  [COCO downloads](https://cocodataset.org/#download).

The registry contains 29 candidates. Only these two pass the current gate;
all other candidates are explicitly blocked with a reason.

## 5. Actual corpus counts

The materialized corpus has exactly 1,200 decoded JPEGs and 2,100 human boxes:
1,032 train / 168 validation; 800 positive / 400 curated negative. Source
composition is 350 Caltech positives, 450 COCO positives, and 400 Caltech
curated-empty negatives. Validation contains 88 positive and 80 negative
images (150 Caltech, 18 COCO).

## 6. Taxonomic distribution

Box-level source metadata: bird 1,052; dog 278; sheep 134; cat 123; coyote 68;
cow 58; zebra 45; opossum 41; raccoon 40; horse 37; deer 35; rabbit 33;
elephant 33; giraffe 32; bobcat 26; bear 20; squirrel 18; fox 11; skunk 8;
lizard 6; rodent 2. These taxa are coverage metadata; the learned ontology is
one broad `animal` class.

## 7. Source-pixel size distribution

Primary positive-image buckets: 200 very-small, 257 small, 130 medium, and
213 large. Buckets are derived before resize from original-pixel box area.

## 8. Source/site distribution

COCO contributes 450 examples in an explicit unknown-site stratum. Caltech
location counts are: location-0 37; 100 37; 120 62; 13 58; 23 62; 33 61;
38 62; 4 49; 56 61; 57 62; 60 38; 64 61; 78 38; 90 62. The split uses
official Caltech camera partitions and official COCO train/validation
partitions; neighboring camera frames are never randomly split.

## 9. Negative composition

All 400 negatives are Caltech curated empty camera-trap frames. No product
false-positive Visit label, model absence claim, or COCO unlabeled region was
converted into negative truth.

## 10. Storage gate

Before materialization the WSL filesystem had about 853 GiB free and the
Windows C: volume about 93 GiB free. The completed Stage-1 ignored directory,
including the corpus and all checkpoints, uses approximately 2.6 GiB. The
gate passed without deleting or relocating user data.

Downloaded metadata checksums include Caltech boxes
`9cc208db67b7dcf3fa403920c203a416527628f76a6b838371ab654478bf2ea3`,
Caltech images `0ed31a7371effe1938bdcc5817713ef35c21b868e9974be000fbb7886b95a34c`,
Caltech splits `4deddfc58791124b37db375d45eeccb52d980b40cdd1dbac4881d0aae7ef34b4`,
COCO annotation archive `113a836d90195ee1f884e704da6304dfaaecff1f023f49b6ca93c4aaae470268`,
COCO train instances `610fce4944abdeb15354cc765333805529359d12d88f2f711393ca586901d01d`,
and COCO validation instances
`e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f`.

## 11. Corpus and split fingerprints

- registry: `c47b83e80de061acb709aab7525057e376d976823d302768d680395eee6cad31`
- corpus: `df1edfe3df4b5287ddad3702312a8fb7f1aa273ae26827818bb42b56be773b8d`
- split: `5c0009f4c3c56366f3ab58e62c17f4aceda2b976bd9098d0a17622471954fcb8`
- experiment: `4e0c4da3453503815c65fbd638ab2b13483a80361741840bfc6cb7a392a9aa14`

## 12. Frozen-holdout contamination

The 75-image manifest SHA-256 is
`45b46c7c57a9cfe028682f4d5d3d629e5c255222d5dcfde9735786b6731bad78`; its semantic fingerprint is
`24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec`.
All 1,200 examples were checked. Result: pass, with zero exact SHA matches,
zero source/parent matches, zero site/camera/sequence matches, and zero
corroborated dHash+pHash near duplicates. The holdout was not used to select
examples, train, stop, or choose threshold.

## 13. GPU and runtime

NVIDIA GeForce RTX 4060 Ti, 8,585,084,928 bytes VRAM; PyTorch
`2.13.0+cu130`; CUDA runtime `13.0`; Linux under WSL2; Python 3.12.3.
Measured training peak: 1,153,968,128 bytes allocated and 1,302,331,392 bytes
reserved.

## 14. Exact RF-DETR configuration

RF-DETR Small, official pretrained `rf-detr-small.pth` SHA-256
`d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33`;
`rfdetr` 1.8.3 wheel SHA-256
`345e55b897ce590464e64ae4750e60b668436cbc6bf58d87f438895a93c3e9a4`.
Resolution 640; gradient checkpointing; batch 1; accumulation 8; effective
batch 8; AdamW; LR 1e-4, encoder LR 1.5e-4; weight decay 1e-4; step scheduler
with `lr_drop=1`; FP16; EMA; seed 260811; official CPU default augmentation,
multi-scale disabled; one CUDA GPU; zero data-loader workers for WSL filesystem
compatibility; validation and checkpoint each epoch. Official training
reference: [RF-DETR custom training](https://github.com/roboflow/rf-detr/blob/develop/docs/learn/train/index.md).

## 15. Training, checkpoint, and resume proof

Epoch 0 completed and wrote resumable `checkpoint_0.ckpt` (513,095,506 bytes,
SHA-256 `856a8857f6af9732383e5ae6f7d59709117032cb657ec44a248d5e8fed337660`).
The resume launch explicitly reported all states restored, completed epoch 1,
and wrote `checkpoint_1.ckpt` (513,095,570 bytes, SHA-256
`774b133d20adb8f1428cb97c835478af8d05bd9b70dd59ec13925c680f75ecec`).
Final best-total was the EMA model, 128,251,559 bytes, SHA-256
`b14581ebb0eed43675a229acec304a71fbc0b50ff8640d26acd95ee7f1564d1a`.
This is a real optimizer/scheduler resume proof, not a model-only reload.

## 16. MDV6 result

No MDV6 training ran. Status is `BLOCKED_OFFICIAL_FINE_TUNE_PATH` for the
exact previously benchmarked Apache RT-DETR artifacts. This is intentional
fail-closed behavior, not a pipeline failure.

## 17. Training curves

Regular validation mAP50:95 improved 0.4208 → 0.4330; AP50 0.7174 → 0.7220;
AP75 0.4267 → 0.4516. EMA mAP50:95 improved 0.4266 → 0.4338. Validation loss
improved 2.9675 → 2.8012 and training loss 4.5918 → 3.4757. Library F1 was
0.6870 → 0.6877. Only two epochs were intentionally run; this is feasibility
evidence, not convergence or production-readiness evidence.

## 18. Stage-1 validation metrics

Threshold 0.5 maximized F1 on Stage validation only. At IoU 0.5: precision
0.8295, recall 0.5691, F1 0.6751, mean matched IoU 0.8339, AP-like recall at
IoU 0.25/0.50/0.75 = 0.5904/0.5691/0.4468, and 0.0375 false detections per
curated-negative frame. Size recall: very-small 0.2785, small 0.7941, medium
0.6765, large 0.8537. Bird recall was 0.3438.

## 19. Frozen MockingBird benchmark

The frozen set has 64 scorable frames: 28 reviewed bird boxes and 36 reviewed
negatives; six ambiguous/unscorable cases are excluded. With threshold 0.5
unchanged, RF-DETR produced precision 0.5000, recall 0.0714, F1 0.1250,
mean matched IoU 0.7899, 2 TP / 2 FP / 26 FN, and 0.0278 false detections per
negative frame. This result is materially weak despite low false-positive load.

## 20. Unchanged production MDv5 comparison

Production remains MDv5a at threshold 0.1 with ONNX SHA-256
`b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc`.
On Stage validation it scored precision 0.4595, recall 0.8138, F1 0.5873,
and 0.4000 false detections per negative frame. RF-DETR improves validation
precision/F1 and hard-negative rate but loses substantial recall.

On frozen MockingBird, unchanged MDv5 scored precision 0.2703, recall 0.3571,
F1 0.3077, 10 TP / 27 FP / 18 FN, and 0.2778 false detections per negative
frame. RF-DETR therefore did not beat the target-domain baseline.

## 21. Small and distant performance

Stage validation small recall was 0.7941 but very-small recall only 0.2785.
On frozen local images RF-DETR small recall was 0.0 and the single reviewed
far subject was missed (far recall 0.0). The Stage split does not establish
small/distant local-camera transfer.

## 22. Hard-negative performance

RF-DETR's 0.0278 false detections per frozen negative frame is lower than
MDv5's 0.2778, and Stage curated-empty performance is also strong at 0.0375.
This precision benefit does not compensate for frozen recall of 0.0714.

## 23. Latest diagnostic birds

The five latest cases are agent-reviewed diagnostic ROIs and remain outside
all population denominators. At the Stage-selected 0.5 threshold RF-DETR
recovered 0/5. Unchanged MDv5 recovered 3/5 under the same IoU-0.5 diagnostic
test. Stage customization has not begun recovering the known difficult birds.

## 24. Exact-frame integration

The temporal capture CLI now exposes explicit, default-off
`--retain-exact-analysis`. The bounded manifest envelope binds the retained
JPEG bytes, SHA-256, dimensions, provider-threshold outputs, normalized boxes,
model fingerprint/provider, Geometry Attribution, and Counterfactual Lineage.
It is rejected if bytes or frame identity disagree, if attached to a high-res
burst, or if it claims truth/product authority. A live Camera Node run was not
needed because the integration consumes already-emitted provider-neutral facts
and has focused hardware-free coverage.

## 25. Human localization review

The existing self-contained review packet now includes a usable browser UI.
It displays the actual retained image, keeps detector/proposal overlays in a
separate non-authoritative view, accepts Animal / No animal / Ambiguous, lets a
human draw/undo/clear normalized boxes, requires named reviewer provenance,
and downloads `annotation.json` for the existing validator/exporter. It adds
no species review.

## 26. Verification

Focused tests cover the 29-source fail-closed registry, source-pixel buckets,
group splits, fingerprints, checksum and lineage contamination, dHash+pHash
corroboration, frozen holdout identity, experiment identity, evaluation,
exact-envelope bounds and checksum binding, default-off CLI behavior, retained
record validation, review UI, and existing temporal-review export flow. Ruff
is run on all changed Python files, followed by the relevant observation and
training test suites and a broader repository suite before commit.

## 27. Commit

One coherent local commit contains code, tests, registry, and both documents.
The exact commit SHA is reported by the completion handoff; nothing is pushed.

## 28. Stage-1 decision

**PIPELINE_PROVEN_MODEL_WEAK.** Corpus governance, materialization, CUDA
training, checkpoint/resume, and evaluation all work. The model learned useful
curated-domain precision but transferred poorly to the frozen local birds and
recovered none of the latest diagnostic birds. It is not a promotion candidate.

## 29. Proposed Wildlife Training Corpus v0

Target 131,500 images, contingent on each registry/license/truth gate:

- 45,000 human-boxed North American camera-trap positives;
- 25,000 human-boxed North American bird/small-animal positives;
- 16,500 permissively licensed general animal-box positives;
- 10,000 human-reviewed local field hard positives;
- 20,000 curated empty camera-trap negatives;
- 10,000 human-reviewed local static-clutter/vegetation hard negatives; and
- 5,000 weather, night, illumination, and privacy-boundary negatives.

That is 96,500 positives and 35,000 negatives. Reserve camera/site-disjoint
validation and test partitions; hold back entire local seasons/cameras; target
at least 30% very-small/small positives, explicit bird coverage, and negative
strata with repeated static structures. Block all image-label-only positives
until the integrated human localization queue supplies boxes.

## 30. Exact next milestone

Do **not** scale this checkpoint unchanged. First use the integrated reviewer
to human-box a 2,000-image, local-camera-first correction set: 1,000 small/far
bird positives (including the five diagnostic lineages, with independent
review), 750 recurring static-clutter/vegetation negatives, and 250 night/
weather/edge cases. Keep whole camera sessions disjoint, preserve the current
75-image benchmark frozen, train a new RF-DETR Small experiment identity for
at least 10 epochs with early stopping on the new camera-disjoint validation
set, and require frozen recall to exceed unchanged MDv5 without exceeding its
0.2778 negative-frame false-detection rate before considering the 131,500-image
v0 build.
