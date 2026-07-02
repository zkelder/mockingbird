# SpeciesNet Adapter Boundary Plan

## Purpose

This plan defines the safety boundary for a future optional SpeciesNet adapter
before any runtime, dependency, model-file, or media-processing work happens.

It is a product and implementation boundary, not an implementation guide.

## Product Flow

media-backed Visit/MediaAsset -> optional SpeciesNet adapter ->
SpeciesSuggestion evidence -> user review/use-as-correction -> existing
correction submit creates dataset/export truth.

SpeciesNet can help the reviewer choose a species or taxon. It cannot replace
review, correction, or dataset truth.

## Adapter Role

The SpeciesNet adapter would be an optional local species/taxon suggestion
source.

It is not:

- part of core MockingBird startup
- a truth source
- a `ReviewLabel` creator
- an export or dataset truth writer
- required for manual or mock `SpeciesSuggestion` flows

## Dependency Boundary

- Core MockingBird install must not include SpeciesNet or runtime dependencies.
- A future optional extra may be considered only after license and runtime
  questions are resolved.
- Runtime imports must be lazy.
- The app must start without SpeciesNet installed.
- Tests must pass without SpeciesNet installed.
- Missing dependencies must return unavailable or `not_configured` style status,
  not crash the app.

## Model File Boundary

- No model files are committed.
- The core app does not automatically download model files.
- Model resources are supplied only through an explicit local model path or
  config.
- Any local model directory must be ignored by git.
- Missing model path reports `not_configured`.
- Missing model file reports `unavailable`.
- Model download instructions, if ever documented, must be separate and
  explicit.

## Runtime Configuration Boundary

These are proposed future configuration names only:

- `MOCKINGBIRD_SPECIESNET_MODEL_PATH`
- `MOCKINGBIRD_SPECIESNET_LABELS_PATH` optional
- `MOCKINGBIRD_SPECIESNET_CONFIDENCE_THRESHOLD` optional
- `MOCKINGBIRD_SPECIESNET_DEVICE` optional, default `cpu`
- `MOCKINGBIRD_SPECIESNET_RUNTIME_ENABLED` optional

This phase does not implement these settings.

## Input Boundary

Future adapter inputs may include:

- `media_asset_id`
- local media path resolved by existing `MediaAsset` behavior
- `visit_id` or `event_id` context
- zone context if available
- `motion_evidence_id` if available
- optional crop or bbox later
- taxonomy target list or mapping context

This boundary phase adds no new media decoding. Any decoding or preprocessing
must be separately designed and testable. Missing media must fail safely without
truth writes.

## Output Boundary

Normalized SpeciesNet output should map to:

- `suggested_label`
- `confidence`
- `rank`
- `alternatives`
- `suggested_common_name` optional
- `suggested_scientific_name` optional
- `evidence_region` optional
- `adapter_id`
- `adapter_name`
- provenance/runtime version when available

All output becomes `SpeciesSuggestion` evidence only.

## Taxonomy Mapping Boundary

SpeciesNet labels must map into MockingBird taxonomy where possible.

Unknown or out-of-taxonomy outputs remain reviewable suggestions. No adapter
output silently creates freeform truth. User correction remains final.

## API Boundary

Future route shape, not implemented in this phase:

```text
POST /api/species-suggestions/adapters/speciesnet/runs
```

Request:

- `visit_id` or `media_asset_id`
- optional `motion_evidence_id`
- optional confidence threshold override
- optional max suggestions

Response:

- adapter run/status summary
- created `SpeciesSuggestion` records
- warnings/errors

The route creates `SpeciesSuggestion` evidence only. It does not create
`ReviewLabel`, mark records reviewed, or write `DatasetExport` or
`DatasetCoverage` truth.

## Status And Error Behavior

- `not_configured`: model path missing.
- `unavailable`: dependency or runtime missing.
- `unavailable`: model file missing.
- `unsupported_media`: media cannot be used by the adapter.
- `completed_zero_suggestions`: low confidence or no usable result.
- `runtime_error`: runtime failed without partial truth writes.
- `taxonomy_mapping_warning`: output was unknown or out of taxonomy.

## Test Boundary

Future tests should prove:

- app imports without SpeciesNet installed
- status reports `not_configured` or `unavailable` safely
- missing model path fails safely
- mocked runtime output creates `SpeciesSuggestion` only
- mocked output does not create `ReviewLabel`
- mocked output does not mark Visit reviewed
- mocked output does not change dataset/export truth
- out-of-taxonomy output remains a suggestion
- use-as-correction still requires correction submit
- no model files are needed in tests

## UI Boundary

- The Species Suggestions page may show adapter run results later.
- Visit Detail may offer "Run SpeciesNet suggestion" only when configured.
- UI must show suggestions as evidence.
- The correction form remains the explicit truth action.
- Unavailable model state should be clear and non-blocking.

## Rollback/Disable Plan

- Unset environment variables or disable runtime config.
- Remove the optional dependency.
- Existing `SpeciesSuggestion` evidence remains history.
- Reviewed corrections and exports remain intact.
- The core app continues working.

## Recommendation

Recommended next phase: Phase 9L - review/species suggestion UI polish.

A mocked SpeciesNet adapter seam is useful only if it adds meaningful
adapter-status or runtime-boundary value beyond the existing mock
`SpeciesSuggestion` adapter. Otherwise, MockingBird should keep moving through
the product review loop and defer runtime work until license, model-weight, and
dependency questions are resolved.

## Explicit Non-Goals

- no SpeciesNet runtime
- no dependency
- no model files
- no auto-download
- no training
- no automatic species truth
- no reviewed labels from suggestions alone
- no export truth from suggestions alone
- no stream capture
- no media decoding
- no cloud upload
- no production accuracy claims
