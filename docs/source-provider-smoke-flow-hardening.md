# Source Provider Smoke Flow Hardening

## Purpose

Phase 14A adds consolidated backend smoke coverage for the two implemented
provider paths: `external_url` and `folder_import_future`.

This is test and documentation hardening only. It adds no provider behavior,
live playback, workers, watchers, polling, automation, model runtime,
dependencies, media decoding, or frontend work.

Phase 14B uses these smoke-tested paths for dashboard/source status polish only:
the UI can show provider workflow readiness and next actions, but it still
routes users to explicit preview/import/evidence/review workflows.

## Product Flows Covered

- `external_url`: configure Source -> setup/status -> explicit preview ->
  explicit save as MediaAsset -> explicit pending MotionEvidence -> explicit
  promote -> review/correction truth.
- `folder_import_future`: configure Source -> setup/status -> explicit folder
  preview -> explicit MediaAsset import -> explicit single or batch pending
  MotionEvidence -> explicit promote -> review/correction truth.

## external_url Smoke Path

The smoke path stubs URL fetches so tests never call the network. It proves that
preview is transient, save creates exactly one MediaAsset, evidence handoff
creates pending MotionEvidence only, promotion creates unreviewed Event/Visit
context only, and ReviewLabel correction is the first truth write.

## folder_import_future Smoke Path

The smoke path uses `tmp_path` folders with tiny files. It proves preview is a
dry run, import copies supported files into the test media root as MediaAssets
only, single and batch handoff create pending MotionEvidence only, promotion
creates unreviewed Event/Visit context only, and ReviewLabel correction is the
first truth write.

## Shared Truth-Boundary Assertions

Both paths assert that provider setup, preview/import, MediaAssets, and
MotionEvidence do not create reviewed truth. No SpeciesSuggestion,
DetectionProposal, DatasetExport, analytics truth, or dataset coverage truth is
created before explicit correction.

## Read-only Status Route Boundaries

Source setup review, Source connection status, and Stream playback status are
read-only contracts. The smoke tests install tripwires proving those routes do
not fetch external URLs, scan folders, create media, create evidence, or claim
live playback.

## Storage/Artifact Boundaries

Tests use isolated temp databases and media roots. Saved/imported files must
stay under the test media root, original folder files must remain in place, and
the smoke flow must not create model artifacts, classifier manifests, dataset
exports, training media, or generated workspace files.

## What This Phase Proves

- Provider behavior requires explicit user action.
- Source/Stream status stays honest and read-only.
- Stream playback does not claim live playback.
- MediaAssets are media context, not truth.
- MotionEvidence is evidence, not truth.
- Events/Visits created by promotion still need review.
- ReviewLabel correction remains the dataset/export/analytics truth boundary.
- Dashboard/source status can reflect these paths without running providers or
  creating media, evidence, Events/Visits, labels, exports, or truth.

## What This Phase Does Not Prove

- No live video playback.
- No real external network fetch.
- No real folder outside test temp folders.
- No media decoding.
- No new provider.
- No worker, watcher, polling, or automatic refresh.
- No automatic evidence creation.
- No automatic Event/Visit creation.
- No model runtime, training, or dependency behavior.

## Future Smoke-Test Expansions

- Add provider smoke coverage when another provider reaches explicit
  user-action behavior under the Source/Stream contract.
- Future provider smoke tests should follow the `external_url` and
  `folder_import_future` pattern: status routes are read-only, provider actions
  are explicit, MediaAssets/MotionEvidence are not truth, and ReviewLabel
  correction is the first reviewed truth write.
- Future webhook smoke tests should follow
  [generic-webhook-provider-boundary-design.md](generic-webhook-provider-boundary-design.md):
  metadata/status stays read-only, validation/dry-run creates no records, and
  any later ingest creates evidence/media context only when explicitly scoped.
- Add live playback smoke coverage only after a separately designed playback
  lifecycle exists.
- Add automation smoke coverage only after worker, privacy, retention, and truth
  boundaries are designed.

## Explicit Non-goals

This phase does not add RTSP, USB, ESP32, browser camera capture, live playback,
folder watchers, polling, background jobs, model dependencies, detector
runtime, training flows, media libraries, generated artifacts, or frontend UI.
