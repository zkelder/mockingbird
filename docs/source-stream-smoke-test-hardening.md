# Source/Stream Smoke-Test Hardening

## Purpose

Phase 12A adds backend smoke coverage for the explicit external_url path from
Source/Stream setup through saved media, MotionEvidence, promotion, and
review/correction truth.

This is test and documentation hardening only. It adds no new provider runtime,
live playback, media decoding, automation, dependencies, workers, or product API
behavior.

Phase 12B mirrors this automated coverage as a manual developer/browser
checklist in
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).
Phase 12C designs saved preview media retention and cleanup policy in
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).
Phase 12D implements a read-only retention report and cleanup dry-run planner;
it remains separate from source/stream smoke behavior and does not delete files
or mutate truth.
Phase 12E exposes that report/dry-run path in the frontend while preserving the
same no-delete and no-truth boundary.
Phase 12F adds explicit file-only cleanup for low-risk unlinked saved preview
media. It is a separate storage action and does not delete MediaAsset records,
evidence, Events, Visits, labels, exports, or truth.
Phase 13A is a separate docs-only boundary for future Folder / trail-cam import.
Phase 13B adds folder/trail-cam provider configuration/status only.
Phase 13F designs the future folder-imported MediaAsset -> pending
MotionEvidence handoff only; it adds no implementation or smoke-test runtime.
Phase 14A consolidates the implemented `external_url` and
`folder_import_future` provider paths under shared smoke-test guarantees; see
[source-provider-smoke-flow-hardening.md](source-provider-smoke-flow-hardening.md).
Phase 14B lets Dashboard/Source status reflect those smoke-tested provider
paths as read-only workflow cues, while explicit actions remain in Streams,
Motion Evidence, Retention, and Review.
Phase 14C selects the next provider boundary before implementation. Any new
provider work should extend smoke coverage rather than weakening the
Source/Stream explicit-action spine.
Phase 14D designs generic webhook ingest only. When implemented later, webhook
will need its own smoke path that proves status/dry-run behavior is read-only
and ingest creates no reviewed truth.
Phase 14E adds webhook provider configuration/status only. It is not part of the
current smoke-tested provider action paths yet because there is no webhook
endpoint, payload validation, media handling, evidence creation, or reviewed
truth behavior.
Phase 14F adds a webhook payload validation/dry-run endpoint with its own
backend tests. It validates generic payload shape and Source/Stream/Zone context
without creating media, evidence, Events/Visits, labels, or truth, so it is
still not part of the provider smoke path.
Phase 14G adds a confirmed metadata motion route that can create pending
MotionEvidence only. It has focused backend tests, but it is not folded into the
external_url/folder smoke paths yet.
Phase 14H adds that webhook provider smoke coverage: setup/status and playback
stay read-only, validation dry-run creates nothing, confirmed metadata motion
ingest creates pending MotionEvidence only, explicit promotion creates
Event/Visit context only, and correction remains the first truth write.
Phase 14I surfaces webhook-origin evidence provenance in review/promote and
Event/Visit detail UI while keeping it separate from live playback semantics.
Phase 15A adds a Dashboard MVP readiness overview. It may summarize these
Source/Stream paths and route users to explicit actions, but it does not fetch
provider media, scan folders, process webhook payloads, create evidence, or
write truth.

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
- No record deletion, protected cleanup, background cleanup, live capture, or
  truth mutation. Retention report, dry-run planning, and confirmed low-risk
  file cleanup are separate from this smoke path.

## Future Smoke-Test Expansions

- Phase 12B: UI checklist/dev guide for manually validating the Source/Stream
  path. See
  [source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).
- Phase 12C: external_url saved-media retention and cleanup design.
- Phase 12D: saved media retention report/dry-run API, no deletion.
- Phase 12E: saved media retention UI, dry-run only.
- Phase 12F: low-risk saved media file cleanup only.
- Phase 13A: folder/trail-cam import provider boundary design.
- Phase 13B: folder/trail-cam provider configuration/status contract.
- Phase 13F: folder-imported MediaAsset -> MotionEvidence handoff design.
- Phase 14A: combined provider smoke coverage for `external_url` and
  `folder_import_future`.
- Phase 14C: next provider boundary decision before implementation.
- Phase 14D: generic webhook ingest provider boundary design.
- Phase 14E: generic webhook provider configuration/status contract, no ingest.
- Phase 14F: webhook payload validation/dry-run endpoint, no records.
- Phase 14G: webhook metadata motion payload to pending MotionEvidence only.
- Phase 14H: webhook provider smoke-test hardening through correction truth.
- Phase 14I: webhook review/promote UI provenance polish.
- Phase 15A: MVP readiness overview that does not run providers.
- Later: add smoke coverage for future real provider implementations only after
  their contracts are designed.
