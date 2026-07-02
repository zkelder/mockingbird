# Source/Stream Smoke-Test Hardening

## Purpose

Phase 12A adds backend smoke coverage for the explicit external_url path from
Source/Stream setup through saved media, MotionEvidence, promotion, and
review/correction truth.

This is test and documentation hardening only. It adds no new provider runtime,
live playback, media decoding, automation, dependencies, workers, or product API
behavior.

## Product Flow Covered

Configured Source -> setup review -> Stream playback status -> explicit
external URL preview -> save as MediaAsset -> create MotionEvidence -> promote
explicitly -> Event/Visit review -> user correction truth.

## What The Smoke Test Proves

- Source setup and connection status stay honest for `external_url` metadata.
- Stream playback status does not claim live playback.
- Zone editing remains available through the existing Stream contract.
- Explicit preview fetch is transient and creates no product records.
- Explicit save creates one local MediaAsset only.
- Saved MediaAsset handoff creates one pending MotionEvidence only.
- Promotion creates unreviewed Event/Visit context only.
- ReviewLabel correction is the first truth write.
- Dataset coverage and analytics truth change only after correction.

## Explicit Side-Effect Boundaries

Read-only status and detail routes must not fetch external URLs, run detectors,
write media, create evidence, create Events/Visits, create ReviewLabels, create
SpeciesSuggestions, create DetectionProposals, create DatasetExports, or mutate
dataset truth.

## Source/Stream Status Boundaries

Setup review, Source connection status, and Stream playback status are status
contracts. They describe readiness and next actions without connecting to the
URL or creating product records.

## External URL Preview Boundaries

Preview fetch is explicit and stubbed in tests. It is transient browser context:
available preview bytes do not create MediaAssets, MotionEvidence, Events,
Visits, labels, exports, or truth.

## MediaAsset Save Boundaries

Save preview is explicit. A successful save writes one local MediaAsset under
the configured media root and still creates no evidence, Events, Visits, labels,
exports, or truth.

## MotionEvidence Handoff Boundaries

Saved preview media can become pending MotionEvidence only through the existing
explicit handoff route. The MotionEvidence keeps `snapshot_media_asset_id` and
Source/Stream/Zone context, but it remains evidence only.

## Promotion Boundaries

Promotion uses the existing MotionEvidence promote route. It creates unreviewed
Event/Visit context and links the promoted evidence. It does not create a
ReviewLabel, reviewed status, export truth, model output, or species truth.

## Correction Truth Boundary

The existing correction route creates the ReviewLabel. Only after that route do
Visit/Event review state, dataset coverage, and analytics truth change.

## What This Phase Does Not Prove

- No live video playback.
- No real external URL network fetch.
- No new Source provider.
- No automatic evidence creation.
- No media decoding or frame extraction.
- No model, detector, or classifier runtime.
- No frontend behavior beyond existing API contracts.
- No retention or cleanup policy.

## Future Smoke-Test Expansions

- Phase 12B: UI checklist/dev guide for manually validating the Source/Stream
  path.
- Phase 12C: external_url saved-media retention and cleanup design.
- Later: add smoke coverage for future real provider implementations only after
  their contracts are designed.
