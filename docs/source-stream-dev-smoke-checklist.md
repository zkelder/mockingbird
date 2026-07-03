# Source/Stream Dev Smoke Checklist

## Purpose

Phase 12B gives developers a repeatable manual/browser validation path for the
same explicit external_url flow covered by the Phase 12A automated smoke test.
Use it to confirm the running app preserves Source/Stream setup, saved media,
MotionEvidence, promotion, and correction truth boundaries.

This checklist documents validation only. It does not add provider behavior,
live playback, automatic evidence creation, automatic Event/Visit creation,
runtime dependencies, or model/training work.

Folder / trail-cam import is a future provider boundary documented in
[folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md).
It is not part of this external_url smoke checklist and should receive a
separate future checklist before implementation.

## Product Flow Covered

Configure external_url Source -> setup review -> Stream playback status ->
explicit still-image preview fetch -> save preview as MediaAsset -> create
pending MotionEvidence -> review, ignore, or promote MotionEvidence -> Event
Detail and Visit Detail review -> submit correction -> analytics/export truth
updates only after correction.

## Preconditions

- Repo is clean, or local changes are known and intentional.
- Backend API is running.
- Frontend dev server is running.
- Local database is seeded or reset to a known state.
- An `external_url` Source is available or can be configured.
- A safe HTTP image URL is available for local testing.
- No real camera or live-stream behavior is expected.
- No background worker is expected.

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

Vite may use `5174` if `5173` is busy. If that happens, use the URL Vite
prints and confirm the backend CORS allowlist covers that local origin.

## Backend Validation Commands

Run the focused smoke test:

```sh
.venv/bin/python -m pytest tests/test_source_stream_smoke_flow.py
```

Run the full backend suite before committing related work:

```sh
.venv/bin/python -m pytest
```

## Browser Checklist: Source Setup

- [ ] Open the Streams page.
- [ ] Select the Source used for the smoke flow.
- [ ] Choose provider `external_url`.
- [ ] Enter URL metadata for a safe HTTP image URL.
- [ ] Save provider configuration.
- [ ] Confirm setup review shows configured `external_url`.
- [ ] Confirm live playback remains false or not implemented.
- [ ] Confirm zone editing remains available where expected.
- [ ] Confirm the next action points to explicit preview, not live stream.

## Browser Checklist: Preview Fetch

- [ ] Click `Fetch still-image preview`.
- [ ] Confirm no auto-fetch happens on page load.
- [ ] Confirm preview status and message appear.
- [ ] Confirm content type and bytes appear.
- [ ] Confirm the preview image appears only after explicit fetch.
- [ ] Confirm copy says preview is not saved and creates no Events, Visits, or
      truth.

## Browser Checklist: Save Preview

- [ ] Click `Save preview as local media`.
- [ ] Confirm a saved MediaAsset ID appears.
- [ ] Confirm media link or preview works if available.
- [ ] Confirm copy says no Events, Visits, or truth were created.
- [ ] Confirm no auto-save occurs.

## Browser Checklist: Create Pending Evidence

- [ ] Click `Create pending evidence from saved media`.
- [ ] Confirm a MotionEvidence ID appears.
- [ ] Open the Motion Evidence page.
- [ ] Confirm pending evidence appears.
- [ ] Confirm attached media appears.
- [ ] Confirm Source, Stream, and Zone context appears where available.
- [ ] Confirm copy says pending evidence is not Event, Visit, label, or truth.

## Browser Checklist: Promote Explicitly

- [ ] From the Motion Evidence page, explicitly promote pending evidence.
- [ ] Confirm Event and Visit links appear.
- [ ] Confirm evidence status changes to `promoted`.
- [ ] Confirm no label or truth is created yet.
- [ ] Open Event Detail.
- [ ] Open Visit Detail.
- [ ] Confirm saved media/provenance context appears.
- [ ] Confirm Visit still needs correction.

## Browser Checklist: Correction Truth

- [ ] Submit a correction on Visit Detail.
- [ ] Confirm the correction appears.
- [ ] Confirm review state changes only after correction.
- [ ] Confirm analytics, dataset, and classifier-readiness views should now
      count the reviewed correction, not raw preview or evidence.

## API Smoke Checklist

Use these as route-level checkpoints. For exact working payloads, follow
[tests/test_source_stream_smoke_flow.py](../tests/test_source_stream_smoke_flow.py).
Do not run preview/save calls unless you have configured a safe local test URL
and intend to make that explicit request.

```sh
curl -s http://127.0.0.1:8000/api/sources/source-backyard-demo/setup-review
curl -s http://127.0.0.1:8000/api/streams/stream-backyard-feeder/playback
```

Preview and save endpoints are explicit actions:

```sh
curl -s -X POST http://127.0.0.1:8000/api/sources/source-backyard-demo/external-url/preview \
  -H "content-type: application/json" \
  -d '{"timeout_seconds": 3, "max_bytes": 5000000}'

curl -s -X POST http://127.0.0.1:8000/api/sources/source-backyard-demo/external-url/preview/save \
  -H "content-type: application/json" \
  -d '{"stream_id": "stream-backyard-feeder", "note": "manual smoke validation"}'
```

Saved media, promotion, and correction endpoints require IDs returned by the
prior steps:

```sh
curl -s -X POST http://127.0.0.1:8000/api/media/{media_asset_id}/create-motion-evidence \
  -H "content-type: application/json" \
  -d '{"zone_id": "zone-feeder", "reason": "manual smoke validation"}'

curl -s -X POST http://127.0.0.1:8000/api/motion/evidence/{evidence_id}/promote \
  -H "content-type: application/json" \
  -d '{"event_title": "Manual saved preview activity", "visit_label_hint": "unknown_animal"}'

curl -s -X POST http://127.0.0.1:8000/api/review-labels \
  -H "content-type: application/json" \
  -d '{"target_type": "visit", "target_id": "{visit_id}", "label": "Northern Cardinal"}'
```

Optional retention report/dry-run checks after saving preview media:

```sh
curl -s http://127.0.0.1:8000/api/media/saved-preview-retention

curl -s -X POST http://127.0.0.1:8000/api/media/saved-preview-retention/dry-run-cleanup \
  -H "content-type: application/json" \
  -d '{"media_asset_ids": ["{media_asset_id}"]}'
```

These retention routes are report/dry-run only. They must not delete files,
delete records, create evidence, or mutate review truth.

Optional low-risk file-only cleanup check after saving an unlinked preview:

```sh
curl -s -X POST http://127.0.0.1:8000/api/media/{media_asset_id}/cleanup-preview \
  -H "content-type: application/json" \
  -d '{"mode": "delete_file_only", "confirm": true, "reason": "manual smoke validation"}'
```

Run this only for a low-risk `saved_unlinked` saved preview MediaAsset. The
response may delete the local file, but the MediaAsset record and all
MotionEvidence, Events, Visits, labels, exports, and truth must remain.

## Browser Checklist: Saved Media Retention

- [ ] After saving preview media, open `Saved Media Retention`.
- [ ] Confirm the saved MediaAsset appears with a risk level and media state.
- [ ] Confirm Source, Stream, provenance, size, and linkage counts are visible.
- [ ] Confirm dry-run defaults to low risk only.
- [ ] Run dry-run cleanup.
- [ ] Confirm totals and per-item plans appear.
- [ ] Confirm the page says no files deleted, no records deleted, and no truth
      changed.
- [ ] Confirm only low-risk `saved_unlinked` items show `Delete local file`.
- [ ] Confirm the delete action requires explicit checkbox confirmation.
- [ ] If you run confirmed cleanup, confirm the MediaAsset record remains and
      no evidence, Events, Visits, labels, exports, or truth changed.

## Truth-Boundary Checklist

- [ ] Preview fetch creates no records.
- [ ] Save creates MediaAsset only.
- [ ] Media-to-evidence creates MotionEvidence only.
- [ ] Promote creates Event/Visit only.
- [ ] Correction creates ReviewLabel and reviewed truth.
- [ ] No SpeciesSuggestion is created.
- [ ] No DetectionProposal is created.
- [ ] No DatasetExport is created unless the user explicitly uses export flow.
- [ ] No model or detector runtime is called.
- [ ] Low-risk file cleanup, if used, deletes no product records and changes no
      reviewed truth.

## Artifact/Storage Checklist

- [ ] Generated preview media lives under ignored local `data/media` paths only
      after explicit save.
- [ ] No model artifacts are created.
- [ ] No classifier manifest artifacts appear unless export flow is explicitly
      used.
- [ ] No copied training media is created.
- [ ] No media appears outside `data/` from smoke validation.
- [ ] Clean up local test media when it is no longer useful.
- [ ] Treat saved preview media as governed by
      [external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md):
      unlinked media is lowest risk, linked/reviewed media needs warnings, and
      only confirmed low-risk file cleanup is implemented.

## Troubleshooting

- Backend not running: restart the backend command and confirm the API responds.
- Frontend port changed to `5174`: use the printed Vite URL and confirm local
  CORS allows that origin.
- CORS/dev server issue: confirm the frontend origin matches the backend
  allowlist.
- Provider config missing URL: save `external_url` metadata with a URL field.
- Unsafe URL rejected: use a safe local HTTP image URL that satisfies provider
  guardrails.
- Unsupported content type: use JPEG, PNG, or WebP still-image content.
- Oversized image: use a smaller file or the existing max-byte guardrail.
- No stream selected: choose the Source-related Stream before saving media.
- Privacy/ignore zone rejection: choose a reviewable zone.
- Stale local database state: reset to known demo data before repeating.
- Accidental generated files in git status: inspect and remove local artifacts
  outside ignored data paths before commit.

## Reset/Cleanup Guidance

- Use the Local Data page reset when returning to seeded demo state is
  appropriate.
- Remove accidental generated files if they appear outside ignored data paths.
- Do not commit local media.
- Run `git status --short --untracked-files=all` before commit.

## What This Checklist Does Not Prove

- No live playback.
- No RTSP, USB/local camera, or browser camera support.
- No continuous fetch.
- No worker lifecycle.
- No video decoding.
- No automatic detection.
- No model or species accuracy.
- No production performance claim.

## Recommended Next Phase

Recommended next: Phase 12G — cleanup UI polish/audit trail design, or Phase
13A/13B folder-trail-cam provider boundary/status work. Phase 12F implements
only confirmed low-risk file cleanup.

Other reasonable follow-ups:

- Phase 13B: folder/trail-cam provider configuration UI/status contract.
