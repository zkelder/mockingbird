# Model Selection

## Goal Of First Detector Spike

The first real local detector candidate should prove that MockingBird can turn configured local model output into useful proposal evidence while preserving user review and correction as truth.

It is a product safety spike, not a production accuracy claim.

Phase 7E selected a MegaDetector-family local image detector as useful proposal
evidence, and Phase 7K archived the PyTorch-Wildlife route. Phase 23 reopens a
narrower executable path through the official `megadetector` package, an
explicit local MDv5 `.pt` file, and the existing Review Queue identification
action. See [megadetector-runtime-plan.md](megadetector-runtime-plan.md) and
[megadetector-runtime-findings.md](megadetector-runtime-findings.md).

The event-trigger path remains
[stream-motion-trigger-plan.md](stream-motion-trigger-plan.md): Stream ->
lightweight activity trigger, Zone-aware when configured -> best-frame evidence.
Detection and species classification enrich the resulting review candidate;
they are not the motion trigger and Zones are not required crop boundaries.

## Current Visual Species Identification Milestone

The first detector spike is complete: the optional local MegaDetector path can
produce animal/person/vehicle `DetectionProposal` evidence from saved best
frames. It does not identify species. The current product priority is therefore
real visual species classification, not another detector/readiness scaffold.

The first saved-media evaluation completed on July 16, 2026. SpeciesNet
recognized bird as top-1 on only one of eight reviewed bird crops and produced
no species-specific top-1 result, so it is not selected as the visual species
engine for the current field corpus.

BioCLIP 2 returned an avian species first for all reviewed and candidate bird
crops, but the candidate bank was bird-heavy and the local corrections contain
coarse bird/false-positive truth rather than species truth. Several
visually questionable results also carried high scores and large margins.
BioCLIP 2 is therefore the leading controlled follow-up, not a selected
production classifier. Exposure cleanup variants did not consistently improve
either model and cannot restore clipped source detail.

The active implementation sequence is:

1. use an explicitly triggered, one-item-at-a-time BioCLIP 2 shadow to map real
   ranked output into existing `SpeciesSuggestion` evidence; this accelerates
   correction but does not select the runtime or establish accuracy
2. collect representative species-level `ReviewLabel` corrections from
   identification-quality best frames/activity crops
3. include substantially more animal/person/vehicle/blank activity so
   abstention and false suggestions can be measured
4. freeze a genuinely local/seasonal candidate set with explicit unknown and
   non-bird choices
5. evaluate BioCLIP 2 on held-out corrections for top-1, top-3, coverage,
   abstention, high-confidence mistakes, and non-bird specificity
6. only after that gate, decide whether BioCLIP 2 is the selected visual
   classifier and define its abstention/calibration policy
7. automate bounded inference after eligible completed activity only after the
   saved-media path is accurate and failure-safe

This milestone may explicitly scope an optional runtime dependency and local
model artifact. It must never make the model mandatory for app startup,
automatically download weights, commit artifacts, or turn suggestions into
reviewed truth.

## Acceptable First Detector Type

The first candidate must be:

- imported image media only
- local-only execution
- object or animal proposal generation only
- `DetectionProposal` evidence only
- explicitly triggered through the existing model adapter run flow

Species classification, live input, and automatic background processing were
out of scope for the completed first detector candidate. SpeciesNet or another
species classifier remains a separate suggestion adapter, not the motion
trigger; the active milestone above now explicitly scopes its evaluation and
integration.

## Model Candidate Requirements

A candidate model should:

- run from a local file configured by the user
- produce labels, confidence scores, and optional bounding boxes
- support a small, understandable target label set such as bird, squirrel, cat, person, vehicle, or unknown animal
- tolerate missing or incomplete label files by falling back to safe generic labels
- fail clearly when output shape is unsupported
- be removable without changing reviewed product data

MegaDetector-family animal/person/vehicle detection is now optional second-stage
proposal enrichment for saved motion best frames. Zone-aware motion remains the
event trigger; MegaDetector does not automatically suppress or promote motion
candidates. Species suggestion remains a separate adapter and is now the active
product milestone above.

## Species Suggestion Candidates

SpeciesNet, BioCLIP 2, and a custom backyard bird classifier are species
suggestion candidates, not detector adapters and not truth writers. The phase
history below records how the evidence and export boundaries were established.
The measured evaluation above, rather than model popularity, controls which
candidate may enter the Review Queue shadow path.

Phase 9B adds the `SpeciesSuggestion` schema/repository/API foundation before any SpeciesNet or custom classifier runtime. Phase 9C adds a manual/mock UI surface for suggestion evidence and status workflow; it still adds no species runtime, model dependency, media inspection, or truth writing. Phase 9D defines the explicit correction-flow boundary for using suggestion evidence without making status updates into truth.

Phase 9H adds a mock species suggestion adapter for existing Visits before any
SpeciesNet or custom classifier runtime. It creates pending suggestion evidence
for the review loop only and does not inspect media, run a model, or create
reviewed truth.

Phase 9I investigates SpeciesNet runtime, dependency, licensing, model-file, and
output-mapping questions in
[speciesnet-runtime-investigation.md](speciesnet-runtime-investigation.md).
This does not select SpeciesNet as an implementation runtime yet.

Phase 9J reviews public SpeciesNet sources in
[speciesnet-source-review.md](speciesnet-source-review.md). SpeciesNet remains a
candidate, but the recommended next step is an optional adapter boundary plan,
not dependency or model-file integration.

Phase 9K records that boundary in
[speciesnet-adapter-boundary-plan.md](speciesnet-adapter-boundary-plan.md).
SpeciesNet is a candidate with a boundary plan; runtime is not selected,
installed, or invoked.

Phase 9M defines the custom bird classifier dataset/export path in
[custom-bird-classifier-dataset-plan.md](custom-bird-classifier-dataset-plan.md).
The custom classifier path starts from reviewed MockingBird exports, not raw
suggestions, and remains a future `SpeciesSuggestion` adapter path.

Phase 9N defines the classifier training manifest contract in
[classifier-training-manifest-design.md](classifier-training-manifest-design.md).
It selects `manifest.jsonl` as the primary future export shape and keeps
manifest generation, training, model files, dependencies, and runtime work out
of the selection phase.

Phase 9O adds a read-only classifier readiness report/API before manifest
export implementation. It summarizes reviewed media-backed examples and skip
reasons without generating datasets or running classifier runtime.

Phase 9P surfaces classifier readiness in the frontend. It makes readiness and
skip warnings visible, but still does not generate manifests, train models, or
select classifier runtime.

Phase 9Q adds a read-only classifier training manifest preview/API foundation.
It returns reviewed media-backed examples, skipped records, taxonomy metadata,
split assignment, and provenance as structured data only. It does not write
manifest files, copy media, train, run classifier runtime, or change truth.

Phase 9R adds a frontend manifest preview and browser-side JSON copy/download
for the already-loaded response. It still does not generate server-side files,
copy media, train, run classifier runtime, or select a classifier dependency.

Phase 9S defines the future backend manifest file export boundary in
[classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md).
It is design-only and keeps generated files, media copying, training, and
classifier runtime out of scope.

Phase 9T implements backend metadata file export for that manifest under an
ignored local path. It still does not copy media, generate training folders,
train, run SpeciesNet, run a custom classifier, or add model dependencies.

Phase 9U adds frontend dry-run/create controls and status for that metadata
export route. It still does not select or run a classifier, copy media, train,
or add dependencies.

Phase 9V defines the external training workflow in
[external-training-workflow.md](external-training-workflow.md). Custom
classifier work remains future until media-copy policy, external workspace
checks, and runtime adapter boundaries are explicitly scoped.

Phase 9W defines the media-copy export design in
[media-copy-export-design.md](media-copy-export-design.md). The custom
classifier path still awaits future media-copy/export workflow implementation,
external training workspace checks, and a runtime adapter boundary before any
classifier dependency or model artifact work.

Phase 9X adds copy-media dry-run planning only. The custom classifier path still
awaits actual media-copy export, external training workflow checks, and runtime
adapter boundary planning before dependency, training, or model artifact work.

Phase 9Y adds the external training workspace checklist in
[external-training-workspace-checklist.md](external-training-workspace-checklist.md).
Custom classifier work still awaits actual media-copy export, external training
setup, and runtime adapter boundary planning before dependency, training, or
model artifact work.

Phase 9Z adds the external training workspace template in
[external-training-workspace-template.md](external-training-workspace-template.md).
It is documentation only; custom classifier work still awaits actual media-copy
export, external training setup, and runtime adapter boundary planning.

They should follow [species-suggestion-adapter-design.md](species-suggestion-adapter-design.md):

- receive media-backed Event/Visit evidence, optional zone context, and optional crop context
- return ranked species or taxon suggestions with confidence/provenance when available
- remain optional and local
- avoid runtime dependencies until a dedicated implementation phase
- feed `SpeciesSuggestion`, not `ReviewLabel`, directly
- require user review/correction before dataset/export truth changes

Custom classifier training remains future work until reviewed media-backed
examples, metadata export review, media-copy workflow, dataset coverage/quality
checks, external training workspace checks/templates, and runtime boundary
planning are in place.
SpeciesNet did not clear the current saved-field-media gate. BioCLIP 2 is the
leading controlled follow-up, but it is not selected until species-level
reviewed corrections and representative non-bird examples establish useful
accuracy and abstention behavior.

## Dependency Rules

Keep the motion-trigger path as the event trigger and the MegaDetector adapter
as explicit, unavailable-safe enrichment.

PyTorch-Wildlife remains archived. The official `megadetector` package is the
selected optional MDv5 runtime after a focused API, dependency, license, and
download-behavior checkpoint. Final installer redistribution still requires a
release-time transitive dependency audit.

The Phase 26A evaluation shadow justifies a separate
`classifier-bioclip` optional extra backed by the tested OpenCLIP 3.3 minor
line. The core app does not import that runtime during startup or status reads.
A run requires an explicit local BioCLIP model directory, frozen
candidate-label file, and matching precomputed text-embedding cache. Runtime
code never downloads a model or rebuilds that cache. The evidence provenance
binds the labels, cache, model configuration, weights, prompt recipe, OpenCLIP
version, and PyTorch version. The evaluation-only `pybioclip` tooling used to
prepare the current cache is not a production runtime dependency.

Serious future detector runtime candidates:

- ONNX Runtime for local model execution, only after a compatible local MegaDetector artifact and output mapping are available
- official `megadetector` MDv5 runtime with an explicit local `.pt` path and no adapter downloads
- PyTorch-Wildlife only if a future checkpoint resolves dependency/license/download risk
- Pillow or numpy only when the explicit implementation phase proves they are needed

Avoid heavy or model-specific runtime stacks unless an explicit implementation phase justifies them. No PyTorch, TensorFlow, OpenCV, Ultralytics, YOLO package, MegaDetector package stack, BirdNET runtime, SpeciesNet runtime, or model dependency should be added by selection docs alone.

## Model File Rules

Model files are local configuration and must stay out of git.

MockingBird must not:

- commit model weights
- generate model artifacts into the repo
- download models automatically
- require a model file for app startup
- hide the configured/unconfigured state from the user

Use environment variables such as `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH` and optional labels configuration such as `MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH`. MegaDetector runtime work should use `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`, optional `MOCKINGBIRD_MEGADETECTOR_LABELS_PATH`, and optional `MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD`.
The BioCLIP evaluation shadow uses `MOCKINGBIRD_BIOCLIP_MODEL_PATH`,
`MOCKINGBIRD_BIOCLIP_LABELS_PATH`, and
`MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH`; the first runtime is CPU-only.


### Supported local BioCLIP 2 artifact

The supported desktop baseline is Imageomics
[`imageomics/bioclip-2`](https://huggingface.co/imageomics/bioclip-2), model-card
version `1.0.0`, immutable revision `2957b322090f9cb17ae72c71981c7218a28d81e0`, under the model card’s MIT
license. Use only the official `open_clip_model.safetensors` artifact with
SHA-256 `b7b2bf6fbc95799e42630e394cf95803892ab447c1a8ab629dbc82fbeaf7dfef`
and its matching official `open_clip_config.json`. Both live in an ignored
local cache; no artifact URL, filesystem path, or credential is exposed by the
application API.

The three configuration variables name existing local model, labels, and cache
artifacts in the desktop process environment. The explicit
`scripts/prepare_bioclip_candidate_cache.py` setup command can generate the
matching cache from a bounded frozen file of existing MockingBird bird taxonomy
labels and a pinned expected weight digest. It forces the model libraries
offline, cannot download an artifact, and never runs during review.

Each Stream resolves one immutable versioned bird candidate pack. Backyard Core
v1 preserves the established ordered 14-species scope; a user pack contains
2-200 existing bird-species taxonomy members and an edit creates a successor,
rather than rewriting historical evidence. New attempts retain the pack ID,
version, ordered-member hash, and candidate count. Completed-run reuse also
requires that pack hash, so a selected-pack change creates a new explicit
evidence set and supersedes only earlier pending BioCLIP evidence.

A pack may select only labels already present in the configured local candidate
bank. Selection reuses the verified matching rows from that precomputed cache;
a missing label reports setup required and never builds embeddings during a
review request. Rebuilding the full cache remains an explicit offline
configuration operation when its label bank or model artifact changes.

## Supported Media Scope

The first candidate is limited to imported image media:

- `image/jpeg`
- `image/png`
- `image/webp`

Video, live stream input, camera input, and frame extraction are not part of this candidate.

## Output Mapping Requirements

Detector output must map into:

- `DetectionRun` for the adapter execution
- `DetectionProposal` for each evidence item

The adapter must set proposal fields conservatively:

- normalized label
- confidence
- optional bounding box
- stream and zone context from the media/request
- suggested event type such as `animal_visit`
- suggested subject/species only when safe

No raw model output should become reviewed labels, export records, or analytics truth without user correction.

Species-classifier output maps separately into one pending
`SpeciesSuggestion`: top-1 is the primary candidate, lower ranks are stored as
alternatives, and the actual padded detector/activity/full-frame input box is
stored as provenance. It does not create a detector run or proposal merely to
fit the detector-shaped API.

## Confidence Threshold Rules

Use a conservative default threshold. Make threshold configuration explicit and local.

Low-confidence outputs should be dropped or left as low-confidence proposal evidence. They must not become review truth.

Confidence is evidence metadata. It is not a replacement for correction.
BioCLIP softmax values are candidate-bank-relative, uncalibrated scores rather
than confidence and must be labeled that way in Review Queue.

## Bounded Runtime Expectations

The completed first detector candidate remains boring and bounded:

- run only when requested
- process one imported image at a time
- avoid startup work
- avoid long-running background work
- fail without corrupting product state

If runtime cost is unclear, prefer disabled or unavailable status over automatic execution.

The visual classifier evaluation also starts one saved media item at a time and
records its actual cost. Automatic post-activity inference is allowed only after
selection, with one bounded attempt per eligible Visit, explicit concurrency and
timeout limits, and failure behavior that leaves capture and review available.
The local BioCLIP action reserves one single-flight slot before image decode so
concurrent requests cannot multiply full-image decode memory. Its lazy,
local-only worker loads the verified model only after the first explicit request,
reuses it for sequential requests, and is terminated and recreated after a
timeout, crash, or parent shutdown. Side-effect-free status rejects an
unsupported OpenCLIP runtime line before execution, and Windows worker startup
passes a bounded shared-memory descriptor instead of pickling full RGB bytes
into spawn arguments. A completed pending suggestion is reused only when the
exact input SHA-256, verified model/cache configuration, and candidate-pack
hash match; a changed input, artifact, or pack creates a new pending set and
supersedes only prior pending BioCLIP evidence.

## Evaluation Plan

Evaluate with product data, not model hype:

- measure real per-image top-1/top-3 species predictions against reviewed labels
- record abstentions, high-confidence mistakes, inference time, and setup cost
- compare detector/activity-centered crops with useful original-frame context
- create proposal evidence
- convert useful proposals into reviewable events/visits
- correct labels through the normal review flow
- export reviewed truth
- compare proposal labels to reviewed corrections through adapter evaluation
- watch dataset coverage and dataset QA for regressions

Unknown reviewed labels should be surfaced separately from match-rate denominator.

## Rollback Plan

Rollback must be safe:

- unset the local model path or mark the adapter unavailable
- keep already-created proposals as evidence
- preserve user corrections and exports as truth
- use adapter evaluation to identify noisy labels
- do not delete product data to undo a bad model candidate

## Historical First-detector Non-Goals

The completed first real detector spike did not add the following. These limits
do not block the explicitly scoped visual species milestone above:

- species classification
- video frame extraction
- camera or live stream input
- background workers
- cloud services
- automatic model downloads
- committed model weights
- production accuracy claims
- adapter-specific product flows
