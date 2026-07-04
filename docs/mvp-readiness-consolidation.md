# MVP Readiness Consolidation

## Purpose

Phase 15A makes the Dashboard a read-only overview of current provider workflow
readiness. It tells users what works now, what remains future, and where the
next explicit action lives.

Phase 15C adds onboarding and empty-state polish that reinforces the same
readiness and truth-boundary story throughout sparse local app states.

This does not add provider behavior, live playback, model runtime, media
decoding, generated artifacts, or truth writes.

## Current MVP Provider Workflows

The MVP readiness overview summarizes four Source/provider paths:

- `external_url`
- `folder_import_future`
- `webhook_future`
- `manual_media`

Each workflow points to existing app or API actions and keeps review/correction
as the truth boundary.

## external_url Readiness

Current support:

- explicit still-image preview
- explicit save as local `MediaAsset`
- explicit pending `MotionEvidence` handoff
- explicit promotion to unreviewed Event/Visit context
- correction creates reviewed truth

Next action: open Streams and fetch still-image preview.

Not supported here: live playback, automatic labels, automatic evidence, or
truth creation from preview/media alone.

## folder_import_future Readiness

Current support:

- explicit folder preview
- explicit import as local `MediaAsset` records
- single or batch pending `MotionEvidence` handoff
- explicit promotion to unreviewed Event/Visit context
- correction creates reviewed truth

Next action: open Streams and preview folder import.

Not supported here: live playback, hidden background import, automatic Visits,
labels, or truth creation from folder media alone.

## webhook_future Readiness

Current support:

- Source setup/status metadata
- payload validation dry-run
- explicit metadata motion payload to pending `MotionEvidence`
- explicit promotion to unreviewed Event/Visit context
- correction creates reviewed truth

Next action: use the API validation/motion evidence route; UI ingest controls
remain future.

Not supported here: media upload/download, external labels as truth,
ecosystem-specific mapping, or live playback.

## manual_media Readiness

Current support:

- explicit local media import
- reviewable Events/Visits from import
- normal review/correction flow
- analytics, exports, and classifier readiness from reviewed corrections

Next action: open Import Media.

Not supported here: live provider playback or camera automation.

## Truth Boundary

Media and evidence are not truth. Review corrections create truth for analytics,
exports, and classifier readiness.

Provider setup, preview, import, validation, MediaAssets, and MotionEvidence are
context or evidence until explicit review/correction creates `ReviewLabel`
truth.

## What Works Now

- Source setup/status can show provider readiness.
- Streams can route users to explicit provider actions.
- External URL preview/save can create local media only.
- Folder import can create local media only.
- Webhook metadata motion can create pending evidence only.
- MotionEvidence can be reviewed, ignored, or promoted explicitly.
- Review corrections feed analytics, exports, and classifier readiness.
- Saved Media Retention can report and act on low-risk local files without
  deleting records or reviewed truth.

## What Remains Future

- live provider playback
- real source adapter runtimes beyond scoped explicit actions
- webhook media upload/download
- background provider automation
- automatic MotionEvidence creation from setup/status views
- automatic Event/Visit creation from provider status
- automatic ReviewLabel/truth creation
- model runtime, training, or classifier execution

## Dashboard/Source Overview Role

The Dashboard is a read-only overview layer. It may summarize provider workflow
readiness, current support, next actions, live playback status, and truth
boundaries.

It must not fetch URLs, scan folders, process webhook payloads, create
MediaAssets, create MotionEvidence, promote Events/Visits, write review truth,
run models, or generate exports.

## Smoke-Test Relationship

The readiness overview summarizes paths already covered by provider smoke
tests: explicit provider action, media/evidence as non-truth, explicit
promotion, and correction as the first reviewed truth write.

See [source-provider-smoke-flow-hardening.md](source-provider-smoke-flow-hardening.md)
for backend smoke expectations and
[source-stream-smoke-test-hardening.md](source-stream-smoke-test-hardening.md)
for the external URL Source/Stream path.
Use [mvp-demo-script.md](mvp-demo-script.md) for the higher-level local
walkthrough across Dashboard, provider workflows, review/correction, retention,
analytics, exports, and classifier readiness.
Use [onboarding-empty-state-polish.md](onboarding-empty-state-polish.md) for the
read-only first-run and sparse-data copy rules.
Use [local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md) as the
local demo/dev readiness gate before selecting riskier provider, worker, or
playback work.

## Explicit Non-goals

- no new provider behavior
- no new backend endpoint
- no live playback implementation
- no URL fetch from Dashboard/status views
- no folder scan from Dashboard/status views
- no webhook processing from Dashboard/status views
- no media decoding
- no model runtime or training behavior
- no dependency changes
- no generated model, dataset, or media artifacts
- no automatic MotionEvidence, Event/Visit, or ReviewLabel creation
