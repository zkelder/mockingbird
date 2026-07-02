# SpeciesNet Source Review

## Purpose

This review decides whether SpeciesNet is safe to keep as a future optional
species or taxon suggestion adapter for MockingBird.

The answer is yes, but only as an evidence-only candidate. The next step should
be an optional adapter boundary plan, not runtime integration.

## Sources Reviewed

Reviewed public sources:

- [Google CameraTraps / SpeciesNet repository](https://github.com/google/cameratrapai)
- [Google CameraTraps README](https://github.com/google/cameratrapai/blob/main/README.md)
- [Google CameraTraps LICENSE](https://github.com/google/cameratrapai/blob/main/LICENSE)
- [Google CameraTraps pyproject.toml](https://github.com/google/cameratrapai/blob/main/pyproject.toml)
- [SpeciesNet package source](https://github.com/google/cameratrapai/tree/main/speciesnet)
- [SpeciesNet model cards](https://github.com/google/cameratrapai/tree/main/model_cards)
- [Kaggle SpeciesNet model page](https://www.kaggle.com/models/google/speciesnet), as linked from the official README
- [Google Research SpeciesNet announcement URL](https://research.google/blog/speciesnet-ai-for-identifying-animal-species-in-camera-trap-images/)

The Google Research URL was checked, but the static HTML available in this
review environment did not expose article content. Treat that announcement as a
source to verify manually before runtime implementation.

## Product Fit Summary

SpeciesNet is relevant to MockingBird as a species or taxon suggestion source
for media-backed Visits or MediaAssets. It is not needed for core MockingBird.

MockingBird already has a mock `SpeciesSuggestion` flow, Visit Detail display,
and use-as-correction prefill. SpeciesNet can wait behind that product path.
Any SpeciesNet output must become `SpeciesSuggestion` evidence only; it must not
write `ReviewLabel` truth.

## License Review

- Code license discovered: Apache-2.0 in the repository license and package
  metadata.
- Model weights terms discovered: not confirmed from static Kaggle access in
  this environment.
- Model-card terms discovered: model cards describe architecture, training,
  input/output shape, and dataset distribution, but this review did not find a
  separate weight license in the accessible model-card text.
- License posture: code appears permissive; model weights remain unclear and
  require deeper review.
- Commercial redistribution concern: do not redistribute SpeciesNet model files
  with MockingBird until the Kaggle model page, weight files, and any model-card
  terms are reviewed explicitly.
- Attribution/notice: Apache-2.0 code reuse requires license and notice
  handling if distributed. SpeciesNet citation guidance exists in the README.

## Runtime/Dependency Review

- Likely runtime entry point: `python -m speciesnet.scripts.run_model` or a
  future library wrapper around `SpeciesNetClassifier`/`SpeciesNet`.
- Python support discovered: package metadata lists Python `>=3.9,<3.14`.
- Major dependencies discovered: `torch >= 2.0`, `yolov5`, `onnx2torch`,
  `pillow`, `numpy`, `pandas`, `kagglehub`, `huggingface_hub`, `cloudpathlib`,
  `requests`, and related utilities.
- Heavy runtimes: PyTorch is required by package metadata and model cards; YOLOv5
  is part of the detector side.
- CPU feasibility: official README shows CPU load examples, so CPU appears
  possible. Performance for MockingBird hardware remains unmeasured.
- GPU: NVIDIA GPU is optional in the README, not required, but GPU support adds
  PyTorch/CUDA packaging complexity.
- Dependency risk compared with PyTorch-Wildlife findings: high. SpeciesNet
  directly depends on PyTorch and YOLOv5-era detector tooling, so it should not
  be added to the core app.
- App startup can remain clean only if MockingBird uses optional dependency,
  lazy import, and unavailable-safe adapter status.

## Model File/Download Behavior

- Official README says the main scripts automatically download detector and
  classifier weights.
- Official source supports Kaggle identifiers, Hugging Face identifiers, and a
  local model folder for loading model resources.
- Official source can also download detector weights from a URL listed in model
  metadata when the detector file is missing.
- Official README points to direct Kaggle downloads for offline use.
- Offline/local-first operation appears possible only if the user supplies a
  local model folder and MockingBird avoids remote identifiers.
- MockingBird must not automatically download SpeciesNet weights in the core
  app.
- Model files must stay under ignored local paths supplied by explicit
  configuration.

## Input/Output Review

Expected input:

- image filepath, folders, filepath list, or instances JSON in the script
- local, HTTP(S), or cloud-style file references in utility loading code
- classifier preprocessing uses RGB images resized to 480x480
- crop mode can use detector bounding boxes; full-image mode is also present
- batch classifier inference is supported

Expected output:

- predictions JSON with one entry per image
- top classifications with class labels and scores
- final ensemble prediction and prediction score when full ensemble succeeds
- detector outputs for animal, human, and vehicle when detector runs
- failure markers for classifier, detector, or geolocation failures
- model version metadata
- labels include species, higher taxa, blank, and vehicle classes

Scientific/common-name mapping may be derivable from the taxonomy resources, but
the exact mapping format needs implementation-phase review.

## Taxonomy Mapping Risk

SpeciesNet taxonomy differs from MockingBird's current review taxonomy. Its
labels appear to include structured taxon strings, higher taxa, non-animal
classes, and many species outside MockingBird's initial bird-focused target set.

Future output must map to MockingBird taxonomy labels where possible.
Out-of-taxonomy results remain reviewable suggestions. No SpeciesNet output
bypasses taxonomy, review, or correction.

## Local-First And Privacy Review

Any future SpeciesNet adapter must run locally. MockingBird must not upload
user-provided `MediaAsset` files to a cloud service by default.

Missing runtime, missing model path, missing model files, unsupported media, or
bad output must produce clear unavailable/error states without writing partial
truth.

## Implementation Recommendation

Proceed to a limited optional adapter boundary plan.

Do not add SpeciesNet dependencies, model files, model download behavior, media
decoding, or runtime calls yet. The boundary plan should specify adapter status,
configuration, local model folder requirements, mocked output tests, taxonomy
mapping policy, and unavailable-safe failure behavior.

This recommendation is conservative because:

- SpeciesNet is product-relevant for species/taxon suggestions.
- MockingBird already has the evidence/review UI path it needs.
- The code license appears permissive.
- The runtime stack is heavy.
- Model weight license/redistribution terms remain unresolved.
- Official scripts include automatic download behavior that MockingBird must not
  inherit.

## Required Guardrails For Any Future Implementation

- optional dependency only
- lazy import only
- app starts without runtime
- no model files committed
- no automatic downloads
- explicit local model path/config
- outputs `SpeciesSuggestion` only
- no `ReviewLabel` or truth writes
- tests mock runtime output
- no media decoding beyond already-supported `MediaAsset` path unless
  separately designed

## Open Questions

- exact model weight license
- exact runtime package/dependency tree after install
- local path support shape for a packaged MockingBird adapter
- model size for each classifier/detector resource
- CPU performance on expected local hardware
- taxonomy export/mapping format
- blank and non-animal behavior in real outputs
- commercial redistribution risk
- whether Google Research announcement content adds any licensing or use terms

## Recommended Next Phase

Phase 9K - SpeciesNet optional adapter boundary plan.

This is the right next step because it can define the adapter seam, config
contract, mock tests, and truth boundary without adding runtime dependencies or
model files. A separate dependency/license spike can follow if the boundary plan
finds that a real adapter is still worth pursuing.

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
