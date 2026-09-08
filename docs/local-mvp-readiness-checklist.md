# Local MVP Readiness Checklist

**Superseded, 2026-09-08, by *External Acceptance Entry Readiness &
Uninstall Closure v1*** (disclosed first as a documentation-currency
finding by
[release-gate-reconciliation-external-acceptance-preparation-v1-report.md](release-gate-reconciliation-external-acceptance-preparation-v1-report.md)
§3; see
[external-acceptance-entry-readiness-uninstall-closure-v1-report.md](external-acceptance-entry-readiness-uninstall-closure-v1-report.md)
for the closure record): this is historical record of the Phase 15D
local-demo gate from 2026-07-04, never updated since. Its own "Explicit
non-goals for MVP" list, below, states RTSP, USB camera, live playback,
and continuous/automatic monitoring from live sources are *not*
included -- all four are now real, shipped, documented capabilities (see
[using-mockingbird.md](using-mockingbird.md) "Add a camera" and "Start
observing"). Its own "Phase 15D"/"Phase 15E"/"Phase 16"/"Phase 17"
numbering also predates, and does not match, [roadmap.md](roadmap.md)'s
current Gate-lettered release structure. Do not use this document to
judge current release scope, current capability, or what remains
deferred -- it is preserved unedited below for historical accuracy only,
not rewritten to match current state. [roadmap.md](roadmap.md) is the
current authoritative source for release scope;
[using-mockingbird.md](using-mockingbird.md) for current product
capability; [release-execution-state.md](release-execution-state.md) for
current release-readiness/authorization state.

---

## Purpose

Phase 15D defines the current local MVP readiness gate. It is for local demo and
development confidence only; it is not a production release claim.

Use this checklist before choosing riskier work such as live playback,
background lifecycle work, source automation, or new provider behavior.

## Current MVP scope

The local MVP includes:

- local-first app behavior and storage assumptions
- Source/Stream provider setup and status
- `external_url` still-image preview, save, evidence, promotion, and correction
- `folder_import_future` preview, import, evidence, promotion, and correction
- `webhook_future` metadata motion validation, evidence, promotion, and
  correction
- manual media import
- MotionEvidence review, ignore, and promote
- Event/Visit review
- ReviewLabel correction truth
- analytics, dataset export, and classifier readiness from reviewed corrections
- saved media retention reporting, dry-run planning, and low-risk file-only
  cleanup

## Explicit non-goals for MVP

The local MVP does not include:

- live playback
- RTSP
- USB camera
- browser camera
- MJPEG/HLS
- continuous monitoring
- workers, watchers, or polling
- automatic motion detection from live sources
- production auth or multi-user behavior
- cloud sync
- model training or model runtime
- species accuracy claims
- mobile app packaging

## Required validation commands

Run the full backend and frontend validation before calling the local MVP
demo-ready:

```sh
.venv/bin/python -m pytest
cd web && npm run typecheck
cd web && npm run build
git diff --check
git status --short --untracked-files=all
```

Run artifact checks from the repo root:

```sh
find . -type f \( -name "*.onnx" -o -name "*.pt" -o -name "*.pth" -o -name "*.weights" -o -name "*.engine" -o -name "*.ckpt" \) -not -path "./.venv/*" -not -path "./web/node_modules/*" -print

find . -type f \( -name "manifest.jsonl" -o -name "manifest.csv" -o -name "labels.txt" -o -name "taxonomy.json" -o -name "skipped_records.jsonl" -o -name "summary.json" -o -name "classifier-training-manifest-preview.json" \) -not -path "./.venv/*" -not -path "./web/node_modules/*" -not -path "./data/classifier_manifest_exports/*" -print

find . -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.webp" -o -name "*.mp4" -o -name "*.mov" \) -not -path "./.venv/*" -not -path "./web/node_modules/*" -not -path "./data/*" -print
```

Expected result: no committed model files, generated manifests, generated media,
local database files, local media, temporary files, or unrelated dirty files.

## Provider smoke-test gate

These smoke tests must pass:

```sh
.venv/bin/python -m pytest tests/test_source_provider_smoke_flows.py
.venv/bin/python -m pytest tests/test_webhook_provider_smoke_flow.py
```

The smoke gate covers:

- `external_url`: setup/status -> explicit preview -> MediaAsset -> pending
  MotionEvidence -> promote -> correction truth
- `folder_import_future`: setup/status -> explicit preview/import -> MediaAsset
  -> pending MotionEvidence -> promote -> correction truth
- `webhook_future`: setup/status -> validation dry-run -> metadata
  MotionEvidence -> promote -> correction truth

## Demo checklist gate

Use [mvp-demo-script.md](mvp-demo-script.md). A local MVP demo should walk
through:

- Dashboard readiness
- Streams provider setup
- `external_url` preview, save, evidence, promote, and correct
- folder preview, import, evidence, promote, and correct
- webhook validate, evidence, promote, and correct
- Review Queue
- Analytics, Dataset Exports, and Classifier Readiness
- Saved Media Retention
- Local Data reset/status

## Truth-boundary gate

These must remain true:

- Provider config is not truth.
- MediaAsset is not truth.
- MotionEvidence is not truth.
- Event/Visit is not truth until correction.
- External labels and confidence are not truth.
- ReviewLabel correction is truth.
- Analytics, export, and classifier readiness derive from reviewed corrections.

## UI readiness gate

Keep this concise; do not add more broad UI copy just to satisfy the gate.

- Dashboard shows MVP readiness and next actions.
- Streams supports Source/provider workflows.
- Motion Evidence supports pending, ignored, and promoted review.
- Review Queue supports the correction path.
- Exports and classifier pages explain reviewed-data dependency where needed.
- No page claims live playback is implemented.

## Local data/artifact gate

- No model files are committed.
- No generated manifests are committed.
- No media exists outside ignored data paths.
- No local database or media artifacts are staged.
- No accidental temporary files are present.
- Local data reset works for local demo if available.

## Known limitations

- Not production-ready.
- No live camera stream.
- No background monitoring.
- No trained species classifier.
- No real auth or multi-user story.
- Provider workflows are explicit/manual.
- Webhook auth is not real production auth yet.
- Cleanup is intentionally conservative.

## Release/demo decision

Ready for local demo if all validation passes and the demo script can be
completed.

Not ready for public/product release.

Next work should be selected from known gaps, not random feature drift.

## Recommended next phases

- Phase 15E: UI copy reduction/pass if onboarding text is too heavy.
- Phase 16A: worker/lifecycle boundary design.
- Phase 16B: live/source automation boundary design.
- Phase 17A: live provider decision/design.
