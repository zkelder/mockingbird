# Detection and localization model benchmark / promotion v1 report

Date: 2026-08-11
Starting commit: 7e8398d0141102baba8f9d42a9ac4dedb283d198
Execution host: Windows-hosted NVIDIA GeForce RTX 4060 Ti (8 GB), through
WSL CUDA; driver 610.62; PyTorch 2.13.0+cu130

## Decision

Terminal state: **A — MDv5 NATIVE RETAINED**.

The engineering winner is the exact production MDv5 native path. This is a
comparative result, not a claim that MDv5's live small-bird localization is
adequate: three proof-complete live failures remain valid. No tested
challenger dominates MDv5 on the reviewed corpus at a practical
false-positive rate, and accepted MDv5 tiling does not recover the two hardest
preserved bird counterparts while multiplying reviewed negative-frame false
positives by 15.9 and median latency by about 7.4.

No candidate is promotion-qualified. Production model, threshold 0.1,
provider authority, tracking, admission, Visit semantics, and evidence
selection are unchanged.

## Corpus and provenance

The checksum-pinned corpus contains 75 real images:

- 70 human-reviewed detector-calibration frames: 28 scorable animal-positive,
  36 scorable negative, 6 ambiguous/unscorable, 28 reviewed boxes, and four
  scene groups;
- four latest-session identification burst images with agent-measured bird
  ROIs, marked diagnostic_only;
- one extra latest-session context image with a visually confirmed on-bird
  production box, also diagnostic_only and not independent IoU truth.

The manifest semantic fingerprint is
24bef2dabb37cff8dd4ae984135721aa90647294e2bded0a6e7f83fbdf6bacec.
All 75 images are evaluation/holdout-only. The 51 reviewed Detection Quality
Accounting examples support separate Visit/admission presence analysis but
have no localization truth and therefore do not enter the box metrics.

The exact live analysis-frame bytes for candidates 011-014 do not survive.
Available native 3840x2160 burst images preserve the real birds and scene
content but are not byte-identical live replays. Accordingly, the live
counterfactual ledger proves three original MDv5 detector misses while this
report describes only what each model did on the preserved burst counterpart.

## Candidates and operating points

The exact tested models were production MDv5a ONNX at 0.1,
MDV6-apa-rtdetr-c at the official/default 0.2 operating point,
MDV6-apa-rtdetr-e at 0.2, and RF-DETR Small at 0.5. All runs retained
detections from a common 0.1 anchor floor for bounded model-specific threshold
sweeps. The exact checksums, package hashes, preprocessing, postprocessing,
offline deviation, and licenses are recorded in
[detector-promotion-benchmark-contract.md](detector-promotion-benchmark-contract.md).

MDV6 Compact and Expanded supplied the two wildlife-specific successor
architectures. RF-DETR Small supplied one current, permissively licensed
general challenger sized for the deployed GPU. YOLO26 was not run because its
AGPL/Enterprise licensing needs a separate product decision and it did not
fill an uncovered role after two wildlife models plus RF-DETR.

## Reproducibility artifacts

The ignored aggregate report is
data/evaluations/detector-promotion-v1/promotion-report.json. Its semantic
fingerprint is
10e27970ace7e1045868506f83cfbcd10b5f1c40dd4e0854bdf602be000bf103;
the exact pretty-printed artifact SHA-256 is
7106508856f7f4b82f195d6517e56776991c8a87c0075c6a48e5be3aea41259f.
The final normalized run semantic fingerprints are:

| Run | Semantic fingerprint |
| --- | --- |
| MDv5 native | 74cecdf911402556f374874851bb3dd7d39ee2c2f018b7fbed0e2b438138e08e |
| MDv5 accepted tiles | 440974e9e454097c21fa1babed081abc9d375fd273fb31a9530f40006b198cf5 |
| MDV6-C native | e522f1e7f5874c332bbfc2c192725d38dcec6db4fe2bf1f80df9d7d33690a87c |
| MDV6-C accepted tiles, diagnostic subset | 7f62917aaa74afe327f4d48d7391ec0918fff820d4e381ec2526ec632cb1e0fc |
| MDV6-E native | f4bf846cc7007783928a1f5b79d85a23d6d3a2b0c4d7b011b6492831a274bad8 |
| MDV6-E accepted tiles, diagnostic subset | 38ca38c0fec64f9e2ad82c2bbd6cf94df32a12a3cbea94b3d0b0bdf613ddb11b |
| RF-DETR-S native | 06785e95e4d2f94fd2ba910ad36c0197501e067b0da05e74684e4dcb4f3303aa |
| RF-DETR-S accepted tiles, diagnostic subset | fd04873df58ba916259e789866624ff220d527b73dfb34d4cbcd96d895ead40f |

Runtime facts are present in each artifact but structurally excluded from these
fingerprints. Model weights, packages, images, configs, and run outputs remain
local/ignored under the paths specified by the contract; no model binary or
evaluation corpus is committed.

## Reviewed-corpus results

These are the only population metrics. Each row uses that model's own
operating threshold; raw confidence is not assumed comparable across models.
Precision includes unmatched extra detections on positive frames. FP/negative
is the false-detection count on the 36 reviewed negative frames.

| Candidate / input | Threshold | Precision | Recall | TP / all FP | FP/negative | Mean / median best IoU | Recall @ IoU .25 / .50 / .75 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MDv5 native | .10 | .270 | .357 | 10 / 27 | .278 | .317 / .073 | .429 / .357 / .250 |
| MDv5 accepted tiles | .10 | .035 | .500 | 14 / 382 | 4.417 | .427 / .457 | .607 / .500 / .250 |
| MDV6-C native | .20 | .111 | .179 | 5 / 40 | .417 | .148 / .000 | .179 / .179 / .143 |
| MDV6-E native | .20 | .051 | .071 | 2 / 37 | .583 | .068 / .000 | .107 / .071 / .036 |
| RF-DETR-S native | .50 | .333 | .036 | 1 / 2 | .028 | .028 / .000 | .036 / .036 / .036 |

The reviewed corpus has only one far/small-subject frame; every candidate
missed it, so far-subject recall is 0/1 for every row. That denominator is too
small for a general small-bird estimate. Threshold sweeps do not reveal a
challenger operating point that dominates MDv5: for example MDV6-C at .30
reaches precision .400 and recall .143 at .111 FP/negative, while MDv5 at .40
has the same precision and FP/negative with recall .214.

MDv5 tiling gains four reviewed true positives and raises recall from .357 to
.500, but adds 355 total false positives, raises reviewed negative-frame
false detections from 10 to 159, and leaves IoU-.75 recall unchanged. That is
not a material repair at an acceptable precision/resource cost.

## Four latest genuine birds

These are engineering diagnostics, not reviewed population metrics. A hit
requires IoU at least .50 at the model's operating threshold. Each cell is:
hit/miss; on-bird confidence and best IoU; highest off-ROI confidence/count;
current frame latency in milliseconds. A dash means no qualifying value.

| Candidate / input | 011 live miss | 012 live miss | 013 live miss | 014 positive control |
| --- | --- | --- | --- | --- |
| MDv5 native | miss; —/.000; .101/1; 211.6 | miss; —/.467; .616/2; 213.4 | hit; .784/.670; —/0; 215.3 | hit; .778/.583; —/0; 220.0 |
| MDv5 accepted tiles | miss; —/.000; .428/7; 1807.5 | miss; —/.304; .829/5; 1656.4 | hit; .911/.587; .277/4; 1396.4 | hit; .912/.559; .296/4; 1384.3 |
| MDV6-C native | miss; —/.000; .234/3; 125.6 | miss; —/.000; .242/2; 131.8 | hit; .279/.641; .224/3; 134.9 | hit; .255/.598; .313/3; 135.9 |
| MDV6-C accepted tiles | miss; —/.331; .726/49; 974.6 | miss; —/.295; .882/41; 369.9 | hit; .361/.528; .849/45; 418.6 | miss; —/.485; .861/34; 374.3 |
| MDV6-E native | miss; —/.323; .273/1; 154.4 | miss; —/—; —/0; 156.9 | hit; .696/.621; —/0; 151.0 | hit; .367/.565; .689/2; 150.7 |
| MDV6-E accepted tiles | miss; —/.347; .877/46; 1011.7 | miss; —/.285; .863/50; 635.9 | hit; .921/.616; .690/37; 636.4 | hit; .936/.542; .799/42; 646.9 |
| RF-DETR-S native | miss; —/—; —/0; 148.2 | miss; —/—; —/0; 181.9 | miss; —/—; —/0; 156.2 | miss; —/—; —/0; 171.6 |
| RF-DETR-S accepted tiles | miss; —/—; —/0; 1274.1 | miss; —/—; —/0; 547.7 | hit; .853/.600; —/0; 481.4 | miss; —/.471; .743/1; 471.5 |

No model/input combination recovers all three known live MDv5 misses on the
available images. MDv5 native, MDv5 tiles, both MDV6 native variants, both
MDV6 tile variants, and RF-DETR tiles recover the preserved candidate-013
counterpart only; candidates 011 and 012 remain misses. RF-DETR native misses
all four. These outcomes cannot be described as recovery or non-recovery of
the exact live analysis calls because those bytes are absent.

The preserved candidate-014 positive control remains detected by MDv5 native
and tiled, MDV6-C native, and MDV6-E native/tiled. MDV6-C tiled falls just
below the IoU criterion and RF-DETR native/tiled miss it. The extra
candidate-012 context control is detected by MDv5 native/tiled, both MDV6
native variants, MDV6-C tiled, and RF-DETR tiled. MDV6-E tiled has best IoU
.470 and RF-DETR native has no detection. That extra box came from a visually
confirmed production detection and supports a control check, not independent
IoU accuracy.

## Hard negatives and false detections

Only reviewed negative frames contribute this comparison.

| Candidate / input | False detections | Frames affected / 36 | Maximum confidence | At least .50 | Static-hook detections / frames / max |
| --- | ---: | ---: | ---: | ---: | ---: |
| MDv5 native | 10 | 10 | .733 | 3 | 4 / 4 / .149 |
| MDv5 accepted tiles | 159 | 30 | .841 | 19 | 84 / 7 / .616 |
| MDV6-C native | 15 | 9 | .649 | 1 | 0 / 0 / — |
| MDV6-E native | 21 | 10 | .666 | 3 | 0 / 0 / — |
| RF-DETR-S native | 1 | 1 | .507 | 1 | 0 / 0 / — |

The tiled challenger runs were deliberately limited to the five latest
diagnostic images once full-frame reviewed results failed to beat the
incumbent; they have no reviewed hard-negative denominator and are not shown
in this table.

MDV6 and RF-DETR avoid the recurring hook detections, and RF-DETR is the most
conservative, but both do so with materially lower reviewed recall. MDv5
tiling is a new unacceptable failure mode: it detects confusors on 30 of 36
negative frames and every hook-scene frame. The latest real session produced
no new meaningful high-confidence environmental false positive; that remains
a non-finding. The exact old .935 pavement/shadow, .795 clutter, and .544
feeder false-positive images were not retained, so this benchmark does not
claim those cases were fixed.

## Performance and deployment facts

Current rerun values below are non-semantic warm-environment measurements.
Median/P95 are per source frame. PyTorch peak allocation excludes driver and
runtime allocation. ONNX Runtime is outside the PyTorch allocator, so the
accepted prior total-GPU before/after readings are reported for MDv5.

| Candidate / input | Median / P95 ms | FPS at median | Startup ms | Pre / infer / post median ms | VRAM evidence | Model size |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| MDv5 native | 221.69 / 317.73 | 4.511 | 938.54 | combined pre+post 130.39 / infer 89.48 | total GPU 2931→2939 MiB in accepted reference | 562.6 MB |
| MDv5 accepted tiles | 1646.17 / 1747.82 | .607 | 933.31 | combined pre+post 54.77 / infer 90.06 per window | total GPU 2921→2963 MiB in accepted reference | 562.6 MB |
| MDV6-C native | 137.45 / 216.26 | 7.276 | 2144.00 | 86.75 / 33.98 / .93 | 161.0 MiB PyTorch peak | 322.4 MB |
| MDV6-E native | 156.94 / 260.98 | 6.372 | 3203.96 | 92.07 / 50.20 / .87 | 510.1 MiB PyTorch peak | 1225.3 MB |
| RF-DETR-S native | 190.64 / 296.40 | 5.245 | 6475.03 | only total exposed by verified API | 358.6 MiB PyTorch peak | 386.0 MB |

On the five-frame diagnostic tile subset, median latency is 397.58 ms for
MDV6-C, 646.91 ms for MDV6-E, and 514.30 ms for RF-DETR-S. The first
candidate-011 tile call is a substantial high outlier for each, so these five
frames are not a stable throughput population.

Deployment assessment:

- MDv5 native is already packaged, checksum-verified, CUDA-only, offline, and
  behind the production provider abstraction. No integration change is needed.
- MDv5 tiling reuses accepted code but adds multi-call scheduling, merge/NMS,
  approximately 7.4-fold median latency, and unacceptable false positives.
- MDV6-C is the most feasible challenger by size and speed, but production
  would need a pinned native-PyTorch bundle or a separately verified
  ONNX/TensorRT export, offline removal of the redundant backbone fetch,
  packaged Windows/CUDA validation, lifecycle integration, and calibration.
- MDV6-E has the same material runtime work plus a 1.23-GB model and higher
  allocation, without an accuracy benefit here.
- RF-DETR-S is feasible on the GPU but adds its PyTorch/Transformers runtime,
  a COCO-to-broad-class mapping, long startup, inference optimization work,
  and reconciliation of the verified checkpoint's _kp_active_mask
  partial-load warning before promotion validation.

No challenger was integrated into the live Observation Engine.

## Why state A rather than C or E

The corpus is imperfect but sufficient for an engineering comparison:
70 governed reviewed frames support incumbent/challenger precision, recall,
localization, and hard-negative outcomes, while the latest five images add
non-population failure diagnostics. This supports a cautious engineering
winner, so state E would understate the evidence.

State C would require a challenger that is clearly superior pending a larger
promotion holdout. None is. MDV6-C is faster and avoids the hook but has half
MDv5's reviewed recall and higher FP/negative at its operating point. MDV6-E
is worse on both reviewed recall and false positives. RF-DETR is precise only
because it largely abstains and misses every native latest-session bird.
Tiling does not repair candidates 011/012 and creates many competing boxes.

MDv5 native is therefore the strongest current engineering choice, while its
known live failures make additional reviewed evidence and a future detector
candidate milestone necessary.

## Exact next milestone

Have a human independently review and box the four latest attributed birds,
then add a new multi-scene, non-session-concentrated holdout with deliberate
small/distant birds and the surviving feeder, bark/branches, vegetation,
dappled-shadow, and pavement confusors. Modify field capture so the exact
analysis-frame bytes and raw detector outputs are retained alongside burst
evidence. With that frozen holdout, rerun calibrated MDV6-C/E threshold
comparison and, only if a challenger clearly dominates, conduct a bounded
default-off live shadow with Windows packaging, resource, monitoring, and
rollback validation. Do not train on that holdout.
