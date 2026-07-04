# MVP Demo Script

## Purpose

This script demonstrates the current local-first MockingBird MVP spine:
Source/provider setup -> explicit provider workflow -> MediaAsset or
MotionEvidence evidence -> explicit promotion -> Event/Visit review -> user
correction truth -> analytics, exports, and classifier readiness.

Phase 15C onboarding and empty states guide the same path when the local app has
little or no data.

Use [local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md) as the
demo-readiness gate before treating this walkthrough as local MVP-ready.

It does not demonstrate live playback, automation, model runtime, training, or
production provider infrastructure.

## What This Demo Proves

- Source/provider setup is understandable.
- The `external_url` still-image preview/save/evidence path works.
- The `folder_import_future` preview/import/evidence path works.
- The `webhook_future` metadata validation/evidence path works.
- MediaAssets are not truth.
- MotionEvidence is not truth.
- Event/Visit review is not truth until correction.
- Corrections drive analytics, export, and classifier readiness.
- Saved media retention and cleanup are explicit and safe.
- Live playback is not implemented yet.

## What This Demo Does Not Prove

- RTSP/live video playback.
- USB/browser camera capture.
- Continuous monitoring.
- Background workers.
- Folder watchers.
- Video decoding.
- Model/species accuracy.
- Production scaling.
- Mobile app packaging.

## Preconditions

- Repo is cloned.
- `pyenv` and a Python virtual environment are available.
- Backend dependencies are installed.
- Frontend dependencies are installed.
- Local database can be seeded or reset.
- A safe test HTTP image URL is available for `external_url`.
- A temporary local folder with tiny test images is available for folder import.
- No real camera is required.
- No cloud service is required.

## Start Commands

Backend:

```sh
cd ~/projects/mockingbird
pyenv shell 3.11.9
source .venv/bin/activate
python -m uvicorn mockingbird.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```sh
cd ~/projects/mockingbird/web
npm run dev -- --host 127.0.0.1 --port 5173
```

Vite may use `5174` if `5173` is busy. Use the URL Vite prints.

## Validation Commands Before Demo

```sh
.venv/bin/python -m pytest tests/test_source_provider_smoke_flows.py
.venv/bin/python -m pytest tests/test_webhook_provider_smoke_flow.py
.venv/bin/python -m pytest
cd web
npm run typecheck
npm run build
```

## Demo Route Map

Visit these surfaces during the walkthrough:

- Dashboard
- Streams
- Import Media
- Motion Evidence
- Review Queue
- Event Detail
- Visit Detail
- Analytics
- Dataset Exports
- Classifier Readiness
- Classifier Manifest
- Saved Media Retention
- Local Data / Settings if available

## Step 1 - Dashboard MVP Readiness

- [ ] Open Dashboard.
- [ ] Confirm the Start here/MVP path explains first actions for a sparse local app.
- [ ] Find the MVP readiness/provider workflow section.
- [ ] Confirm provider cards for `external_url`, folder/trail-cam, webhook, and
      manual media.
- [ ] Confirm live playback is not claimed.
- [ ] Confirm next action links exist.
- [ ] Confirm truth-boundary copy is visible.

## Step 2 - external_url Provider Path

- [ ] Open Streams.
- [ ] Select or configure a Source as `external_url`.
- [ ] Enter safe HTTP still-image URL metadata.
- [ ] Confirm setup review/status says explicit preview is available and
      future-safe.
- [ ] Click `Fetch still-image preview`.
- [ ] Confirm transient preview appears.
- [ ] Confirm no Event, Visit, or truth is created.
- [ ] Save preview as a local MediaAsset.
- [ ] Confirm a MediaAsset ID appears.
- [ ] Create pending MotionEvidence from saved media.
- [ ] Open Motion Evidence.
- [ ] Confirm pending evidence appears with saved media context.
- [ ] Promote explicitly.
- [ ] Open Event Detail and Visit Detail.
- [ ] Confirm no label/truth yet.
- [ ] Submit a correction.
- [ ] Confirm correction becomes truth.

## Step 3 - folder/trail-cam Provider Path

- [ ] Prepare a temporary local folder with small `jpg`, `png`, or `webp` files.
- [ ] Configure a Source as `folder_import_future`.
- [ ] Enter folder path metadata.
- [ ] Confirm the raw folder path is not displayed after save.
- [ ] Preview folder import.
- [ ] Confirm candidate and skipped counts.
- [ ] Import previewed files as MediaAssets.
- [ ] Confirm MediaAsset IDs appear.
- [ ] Dry-run evidence handoff.
- [ ] Confirm dry-run creates nothing.
- [ ] Create single pending evidence from one MediaAsset.
- [ ] Optionally create batch pending evidence after dry-run and confirmation.
- [ ] Open Motion Evidence.
- [ ] Confirm folder provenance is visible.
- [ ] Promote explicitly.
- [ ] Open Event Detail and Visit Detail.
- [ ] Submit a correction.
- [ ] Confirm correction truth.

## Step 4 - webhook Metadata Provider Path

- [ ] Configure a Source as `webhook_future`.
- [ ] Configure shared-secret marker metadata.
- [ ] Confirm the raw secret is not shown.
- [ ] Use the API/client/test pattern to validate webhook payload dry-run.
- [ ] Confirm dry-run creates nothing.
- [ ] Use the confirmed webhook motion evidence route/API pattern.
- [ ] Confirm pending MotionEvidence appears.
- [ ] Open Motion Evidence.
- [ ] Confirm webhook provenance and untrusted label/confidence are evidence
      only.
- [ ] Promote explicitly.
- [ ] Open Event Detail and Visit Detail.
- [ ] Submit a correction.
- [ ] Confirm correction truth.

For exact webhook API examples, refer to
[`tests/test_webhook_provider_smoke_flow.py`](../tests/test_webhook_provider_smoke_flow.py).

## Step 5 - Review Queue And Correction Truth

- [ ] Open Review Queue.
- [ ] Confirm unreviewed Visits appear before correction.
- [ ] Submit or view corrections.
- [ ] Confirm corrected Visit state.
- [ ] Confirm raw evidence/provider labels are not truth.

## Step 6 - Analytics, Export, And Classifier Readiness

- [ ] Open Analytics.
- [ ] Open Dataset Exports.
- [ ] Open Classifier Readiness.
- [ ] Open Classifier Manifest.
- [ ] Confirm readiness/training/export surfaces depend on reviewed
      corrections.
- [ ] Confirm unreviewed evidence alone does not become classifier truth.

## Step 7 - Saved Media Retention

- [ ] Open Saved Media Retention.
- [ ] Confirm saved `external_url` media appears.
- [ ] Review risk levels.
- [ ] Run dry-run cleanup.
- [ ] Confirm no files, records, or truth are deleted by dry-run.
- [ ] If a low-risk unlinked item exists, use `Delete local file` only if
      intentional.
- [ ] Confirm MediaAsset record/provenance behavior remains safe.
- [ ] Do not delete reviewed or protected media.

## Step 8 - Local Data / Reset

- [ ] Open Local Data / Settings if available.
- [ ] Review local data status.
- [ ] Reset demo data only if intentionally ending the demo.
- [ ] Run `git status --short --untracked-files=all` afterward to avoid
      committing generated files.

## Truth-Boundary Checklist

- Provider config creates no truth.
- Preview creates no truth.
- Save/import creates MediaAssets only.
- MotionEvidence is evidence only.
- Promote creates Event/Visit only.
- Correction creates ReviewLabel truth.
- Analytics/export/classifier readiness derive from corrections.
- External labels/confidence are untrusted evidence metadata.

## Artifact Safety Checklist

- No generated media outside `data/`.
- No model artifacts.
- No classifier manifest files unless export flow is explicitly used.
- No copied classifier media unless explicitly used.
- `git status --short --untracked-files=all` is clean before commit.
- Do not commit `data/`, media, models, manifests, or local folders.

## Troubleshooting

- Backend not running: restart the backend command and confirm the API responds.
- Frontend on `5174`: use the printed Vite URL.
- CORS issue: confirm the frontend origin is allowed by the backend.
- External URL rejected: use a safe local test image URL.
- Unsupported content type: use JPEG, PNG, or WebP still-image content.
- Folder path missing or not a directory: fix Source metadata and retry.
- Folder path redacted: expected; raw local paths should not display after save.
- Folder import skipped unsupported files: use supported still-image files.
- Webhook Source not configured: save `webhook_future` metadata first.
- Shared secret marker missing: configure the marker metadata.
- Privacy/ignore zone rejection: choose reviewable context.
- Duplicate evidence skipped: expected when existing evidence already references
  the same source item.
- No review truth until correction: expected.

## Demo Narrative / Talk Track

MockingBird is not a camera adapter demo. Sources feed media and evidence into a
stream-centered product loop. Zones and review are the product center. Evidence
is not truth. Corrections create the dataset. Live playback is future work.

## Recommended Next Phases

- Phase 15D - local MVP release/readiness checklist.
- Phase 15E - UI copy reduction/pass if onboarding text feels too heavy.
- Phase 16A - worker/lifecycle boundary design.
- Phase 16B - live/source automation boundary design.
- Phase 17A - live provider decision/design.
