# MegaDetector Decision Record

## Decision

MockingBird's first real detector target is a MegaDetector-family local image detector for animal, person, and vehicle evidence.

This decision records the detector direction only. It does not add a model runtime, dependency, model file, download path, or implementation.

## Why MegaDetector

MegaDetector-family models are a strong fit for wildlife, camera-trap, and outdoor imagery. They are useful for finding reviewable outdoor activity in imported images because they focus on broad detection categories such as animals, people, and vehicles.

MegaDetector does not provide species identification. That is a good boundary for MockingBird: species truth stays in the taxonomy-backed review and correction flow instead of being treated as automatic model truth.

## Product Boundary

MegaDetector output is evidence, not truth.

MegaDetector-style output must become `DetectionProposal` records through an existing `DetectionRun`. Raw detector labels never bypass Review Queue or Visit Detail correction.

User review and correction remain dataset truth. Exports, dataset coverage, dataset QA, analytics, and adapter evaluation use reviewed and corrected labels as truth. Raw detector labels remain evidence even when they help users find useful review cases.

## Initial Implementation Scope

The first implementation must stay constrained:

- local-only
- imported image media only
- no live camera input
- no video frame extraction
- no background worker
- explicit user-triggered run only
- optional local configuration
- no bundled model files
- no automatic model downloads

## Dependency Decision

The implementation path is still pending.

Likely options:

- PyTorch-Wildlife / MegaDetector integration as the product-aligned route.
- ONNX/local-image-detector path only if it provides a lighter, maintainable runtime.

No heavy dependency should be added without an explicit implementation phase. Phase 7E adds no dependency.

## Output Mapping

Expected mapping for the first MegaDetector-family adapter:

- animal -> `DetectionProposal` label `animal` or `unknown_animal`
- person -> `DetectionProposal` label `person`
- vehicle -> `DetectionProposal` label `vehicle`
- confidence -> proposal confidence
- bounding box -> proposal `bbox`
- zone context -> selected/requested stream zone when available

Species remains `unknown_bird` or `unknown_animal` until user review, unless a later classifier suggests species as evidence only.

## Evaluation Plan

Adapter evaluation compares proposal labels against reviewed corrections. Match and mismatch counts are readiness signals, not production accuracy claims.

Unknown reviewed labels are tracked separately. Mismatches should drive review UX, taxonomy cleanup, detector threshold tuning, or adapter mapping changes. They must not automatically change reviewed truth.

## Rollback Plan

Rollback must be local and safe:

- remove or unset the local model configuration
- let the adapter remain unavailable or not configured
- keep already-created proposals as evidence records
- preserve reviewed labels, exports, coverage, and analytics truth
- keep source/camera behavior independent of detector availability

No reviewed truth is lost if the detector is disabled.

## Explicit Non-Goals

- no species classifier yet
- no camera adapters
- no live video
- no frame extraction
- no background worker
- no cloud
- no automatic model downloads
- no committed model weights
- no production accuracy claims
