# Onboarding Empty-State Polish

## Purpose

Phase 15C makes the current local MVP easier to understand in a fresh or sparse
database. It adds read-only onboarding and empty-state copy across existing app
surfaces without adding provider behavior, backend routes, dependencies,
generated artifacts, or truth writes.

Phase 15E reduces UI verbosity while preserving these docs and guardrails. The
app should keep concise next-action and truth-boundary cues; detailed rationale
belongs here and in related design/checklist docs.

## Product flow explained by onboarding

The app should guide users through:

Source setup -> explicit provider action -> MediaAsset or MotionEvidence ->
explicit promotion -> Visit correction -> analytics/export/classifier
readiness.

## Dashboard onboarding

Dashboard should show a compact first-run path: configure Sources in Streams,
try External URL preview, try Folder / trail-cam import, try Manual Import,
review pending MotionEvidence, and correct Visits.

It must say that live playback is future work, evidence is not truth, and
corrections create analytics/export/classifier truth.

## Provider/source empty states

Streams and Source setup surfaces should explain that provider setup is
metadata/status first:

- `external_url`: explicit preview/save/evidence.
- `folder_import_future`: explicit preview/import/evidence.
- `webhook_future`: API validation and metadata evidence; UI ingest controls
  remain future.
- `manual_media`: explicit local import.

These surfaces must not fetch URLs, scan folders, process webhook payloads, or
claim live playback from onboarding/status copy.

## MotionEvidence empty states

MotionEvidence empty states should explain that evidence can come from saved
External URL media, folder-imported media, manual/dev creation, or sampled-frame
evaluation. MotionEvidence is not an Event, Visit, label, or truth. Promotion is
explicit and still creates unreviewed review context only.

## Review/correction empty states

Review Queue empty states should explain that the queue contains Visits needing
correction. Users can promote MotionEvidence or import media to create
reviewable Visits. Corrections are the first analytics/export/classifier truth.

## Analytics/export/classifier empty states

Analytics, Dataset Exports, Classifier Readiness, and Classifier Manifest should
say that reviewed corrections drive counts, export records, and readiness.
Raw MediaAssets, MotionEvidence, provider labels, suggestions, and unreviewed
Visits are not training/export truth.

## Retention empty states

Saved Media Retention should explain that it tracks saved `external_url` preview
media. Dry-run cleanup writes nothing, and confirmed low-risk file-only cleanup
does not delete records, evidence, Events, Visits, labels, exports, or truth.
Folder-import retention remains separate future policy.

## Truth-boundary copy

Preferred short phrases:

- Live playback is future work.
- Evidence is not truth.
- Corrections create analytics/export/classifier truth.
- MediaAssets and MotionEvidence are context until review/correction.

## What this phase does not add

- no backend behavior
- no provider behavior
- no URL fetches from onboarding/status views
- no folder scans from onboarding/status views
- no webhook processing from onboarding/status views
- no media decoding
- no live playback
- no MotionEvidence, Event, Visit, ReviewLabel, export, or analytics truth
  creation from onboarding
- no dependencies or generated artifacts

## Future onboarding improvements

Later phases can add deeper guided setup only after the related provider,
playback, automation, retention, and truth boundaries are designed. Future
onboarding should keep explicit actions separate from read-only status guidance.
