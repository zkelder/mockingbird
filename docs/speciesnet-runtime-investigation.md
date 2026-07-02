# SpeciesNet Runtime Investigation

## Purpose

SpeciesNet is being investigated as a future optional species or taxon
suggestion adapter for MockingBird. It is not a truth source.

This record captures the runtime, dependency, licensing, model-file, and
input/output questions that must be answered before any implementation phase.
It is not an implementation guide and does not add runtime code, dependencies,
model files, media decoding, or training.

## Product Fit

Intended future flow:

media-backed Visit or MediaAsset -> SpeciesNet/classifier suggestion ->
SpeciesSuggestion evidence -> user review/correction -> dataset/export truth.

SpeciesNet output may help the reviewer choose a species or taxon, but the
existing correction submit path remains the truth boundary.

## Current Known Context

- SpeciesNet is a candidate species/taxon classifier for camera-trap style
  images.
- SpeciesNet is not required for core MockingBird.
- MockingBird already has a mock SpeciesSuggestion adapter, so runtime
  integration can wait.
- SpeciesNet output must become `SpeciesSuggestion` evidence, not
  `ReviewLabel` truth.

## Source Review Checklist

Future source review must verify:

- official repository and package location
- license for code
- license and terms for model weights
- model file size
- supported runtime
- Python version support
- CPU feasibility
- GPU requirements, if any
- dependency tree
- automatic download behavior
- local model path support
- offline/local-first feasibility
- expected input format
- expected output labels, confidence, and rank
- taxonomy and label mapping
- blank, vehicle, and non-animal handling
- commercial redistribution considerations

## Runtime/Dependency Risk Checklist

Future implementation must determine:

- whether SpeciesNet can run without a large framework stack
- whether dependencies are permissively licensed enough for MockingBird use
- whether model weights can be kept out of Git
- whether model files can be supplied by local path
- whether app startup remains clean without SpeciesNet installed
- whether tests can run without SpeciesNet or model files

## Model File Policy

- No model files are committed.
- The core app does not automatically download model files.
- Model files are supplied through an ignored local model path only.
- Running SpeciesNet requires explicit environment/configuration first.
- Missing runtime or missing model path fails safely.
- The core app must start without SpeciesNet installed.

## Input Policy

Future adapter input may include:

- existing `MediaAsset`
- best-frame local artifact
- optional crop or bbox later
- optional Visit/Event context
- taxonomy target context

No media decoding is added in this phase.

## Output Mapping

Future SpeciesNet/classifier output should map into `SpeciesSuggestion`
evidence with:

- suggested label
- confidence
- rank
- alternatives
- adapter provenance
- optional scientific and common names
- unknown, blank, and non-animal handling

All outputs become `SpeciesSuggestion` evidence only.

## Taxonomy Mapping

Suggested labels should map to MockingBird taxonomy labels where possible.
Unknown or out-of-taxonomy labels must remain reviewable. No suggestion bypasses
taxonomy, review, or correction. The reviewed correction remains truth.

## Truth Boundary

- SpeciesNet output does not create `ReviewLabel`.
- SpeciesNet output does not mark Visit reviewed.
- SpeciesNet output does not create dataset/export truth.
- Use-as-correction must go through the existing correction submit path.
- Accepted suggestion status is evidence workflow metadata, not truth.

## Failure Behavior

These cases must fail without partial truth writes:

- runtime not installed
- model path missing
- model file missing
- unsupported media
- bad output schema
- no suggestion or low confidence
- ambiguous species
- out-of-taxonomy result
- runtime error

## Test Plan For Future Implementation

Future implementation tests should prove:

- app starts without SpeciesNet installed
- normal tests require no model files
- missing runtime reports unavailable
- missing model path reports not configured
- mocked SpeciesNet output creates `SpeciesSuggestion` only
- output does not create `ReviewLabel`
- output does not mark Visit reviewed
- output does not change dataset/export truth
- use-as-correction still requires existing correction submit
- taxonomy mapping is tested
- out-of-taxonomy suggestions remain evidence

## Recommended Next Steps

- Phase 9J: SpeciesNet source/license/runtime source review.
- Phase 9K: optional SpeciesNet adapter boundary plan.
- Phase 9L: review/species suggestion UI polish, unless a mocked
  SpeciesNet-specific seam adds clear adapter-status value.
- Real runtime only after dependency, license, and model-file review is complete.

## Phase 9J Source Review Result

[speciesnet-source-review.md](speciesnet-source-review.md) recommends proceeding
only to an optional adapter boundary plan. SpeciesNet remains relevant as future
suggestion evidence, but runtime dependencies are heavy, official scripts can
download weights, and model-weight license/redistribution terms still need
deeper review.

## Phase 9K Boundary Result

[speciesnet-adapter-boundary-plan.md](speciesnet-adapter-boundary-plan.md)
defines the optional adapter boundary. No SpeciesNet runtime is selected,
installed, or invoked by this docs phase.

## Explicit Non-Goals

- no SpeciesNet runtime
- no model dependency
- no model files
- no training
- no automatic species truth
- no reviewed labels from suggestions alone
- no export truth from suggestions alone
- no stream capture
- no media decoding
- no cloud upload
- no production accuracy claims

## References

- [Google CameraTraps / SpeciesNet documentation](https://github.com/google/cameratrapai)
- [Google Research SpeciesNet announcement](https://research.google/blog/speciesnet-ai-for-identifying-animal-species-in-camera-trap-images/)
- [Kaggle SpeciesNet model page](https://www.kaggle.com/models/google/speciesnet)

These are starting points for Phase 9J review; licenses, terms, package behavior,
and model-file handling must be verified before implementation.
