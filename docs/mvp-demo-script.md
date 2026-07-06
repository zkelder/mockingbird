# MVP Demo Script

## Purpose

This script demonstrates the current local-first MockingBird MVP spine:
Source/provider setup -> explicit provider workflow -> MediaAsset or
MotionEvidence evidence -> explicit promotion -> Event/Visit review -> user
correction truth -> analytics, exports, and classifier readiness.

The current short proof loop is:
browser import -> demo proposal evidence -> Review Queue context -> explicit
correction -> reviewed-only Dataset Export proof.

Phase 15C onboarding and empty states guide the same path when the local app has
little or no data.

Use [local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md) as the
demo-readiness gate before treating this walkthrough as local MVP-ready.

It demonstrates browser-direct Live view for supported stream URLs, optional
local RTSP bridge playback, and optional local USB/webcam Live view when system
`ffmpeg` is installed. Windows webcam Live view can use optional Windows
`ffmpeg.exe` DirectShow metadata, but this script does not prove automation,
model runtime, training, persistent
transcoding, or production provider infrastructure.

## What This Demo Proves

- Source/provider setup is understandable.
- Browser-playable Live view can be configured for an `external_url` Source.
- RTSP Live view can use the optional host `ffmpeg` bridge when available.
- Local USB/webcam Live view can use a Linux `/dev/video0`-style device through
  optional host `ffmpeg`.
- Windows webcam Live view can use `windows_dshow` with a DirectShow camera name
  and optional Windows `ffmpeg.exe` path.
- Local camera Live view can save one explicit still frame as a local saved
  image without creating truth or exports.
- MockingBird-served Live view can run page-started live monitoring that compares
  recent live frames, saves the best activity frame as evidence, and offers an
  explicit low-confidence Review Queue handoff without creating truth or exports.
- Stream Detail can draw and edit user-authored Zones directly over the real
  live stream, and monitoring uses those Zones when available.
- The `external_url` still-image preview/save/evidence path works.
- Manual bounded Snapshot watch works for `external_url` while the page is open.
- The `folder_import_future` preview/import/evidence path works.
- The `webhook_future` metadata validation/evidence path works.
- Browser media import can create demo DetectionProposal evidence.
- Review Queue exposes evidence context before correction.
- MediaAssets are not truth.
- MotionEvidence is not truth.
- Event/Visit review is not truth until correction.
- Corrections drive analytics, export proof, and classifier readiness.
- Reviewed-only exports include corrected truth and skip unreviewed candidates.
- Saved media retention and cleanup are explicit and safe.
- Stream saved-media timeline reuse is explicit and evidence-only.
- Optional local detector runs from saved image media are explicit and
  evidence-only when configured.
- Live playback stays separate from snapshot capture, monitoring, review truth,
  and exports.

## What This Demo Does Not Prove

- Persistent RTSP transcoding or production stream infrastructure.
- Pi camera/libcamera, cellular, or field-camera agent setup.
- USB/browser camera capture.
- Persistent/background continuous monitoring.
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
- Demo streams and zones exist. If not, reset or seed local data before the demo.
- A safe test HTTP image URL is available for `external_url`.
- A safe browser-playable or RTSP stream URL is optional for the Live view check.
- System `ffmpeg` on the MockingBird host is optional and only needed for RTSP
  bridge playback or local USB/webcam playback.
- A Linux `/dev/video0`-style webcam path is optional for local camera Live view.
- A Windows DirectShow camera name is optional for Windows webcam Live view; find
  it with `ffmpeg -list_devices true -f dshow -i dummy`.
- If the API runs in WSL, configure a Windows `ffmpeg.exe` path such as
  `/mnt/c/ffmpeg/bin/ffmpeg.exe`; WSL USB passthrough is not the recommended
  webcam path.
- A temporary local folder with tiny test images is available for folder import.
- A local test image is available for Import Media and CLI smoke fallback.
- No real camera is required.
- No cloud service is required.

## Start Commands

Backend:

```sh
cd ~/projects/mockingbird
.venv/bin/python -m uvicorn mockingbird.api.main:app --reload
```

Frontend:

```sh
cd web && npm run dev
```

Vite may use `5174` if `5173` is busy. Use the URL Vite prints.

## Read-Only API Smoke Check

With the API running, confirm the local demo spine has the required read-only
basics:

```sh
.venv/bin/python scripts/check_mvp_smoke.py
```

This checks health, Streams, Zones, Review Queue, Detection Proposals, Dataset
Exports, Analytics, and Classifier Readiness. It creates no media, proposals,
corrections, exports, or truth. It exits nonzero only for hard blockers: API
unreachable, `/health` not ok, no Streams, or no Zones.

## Validation Commands Before Demo

```sh
.venv/bin/python scripts/check_mvp_smoke.py --help
.venv/bin/python -m pytest tests/test_source_provider_smoke_flows.py
.venv/bin/python -m pytest tests/test_webhook_provider_smoke_flow.py
.venv/bin/python -m pytest tests/test_detection_interface.py -q
.venv/bin/python -m pytest
cd web
npm run typecheck
npm run build
```

## Demo Route Map

Visit these surfaces during the walkthrough:

- Dashboard
- Streams
- Review Queue
- Bird Log
- Event Detail
- Visit Detail
- Dataset Exports
- Local Data / Settings if available

Advanced / Developer tools remain available for validation:

- Import Media
- Motion Evidence
- Analytics
- Classifier Readiness
- Classifier Manifest
- Saved Media Retention

## Short Import-To-Export Proof Loop

- [ ] Start the API and frontend with the commands above.
- [ ] If demo Streams/Zones are missing, use Local Data reset/seed behavior and
      rerun the read-only smoke check.
- [ ] Open Import Media.
- [ ] Select a local image, Stream, and optional Zone.
- [ ] Import the image.
- [ ] Click `Create demo proposal`.
- [ ] Optionally click `Create + convert for review` to create Event/Visit
      context.
- [ ] Open Review Queue.
- [ ] Confirm media/proposal evidence is visible.
- [ ] Submit an explicit correction.
- [ ] Confirm the correction panel names ReviewLabel truth.
- [ ] Open Bird Log.
- [ ] Confirm the reviewed observation appears with label, time, camera/source,
      and source image when available.
- [ ] Open Dataset Exports.
- [ ] Create a reviewed-only export with detections and zone context included.
- [ ] Inspect the manifest proof records.
- [ ] Confirm the corrected label appears in the export record while proposal
      detections remain evidence.
- [ ] Confirm skipped reasons explain any unreviewed candidates.

CLI fallback for the same evidence path:

```sh
.venv/bin/python scripts/run_local_image_smoke.py --file /path/to/image.jpg --convert
```

The CLI fallback imports media and creates synthetic demo proposal evidence. It
does not create ReviewLabel truth; finish the loop through Review Queue and
Dataset Exports.

## External URL Snapshot-To-Review Browser Path

- [ ] Start the API.
- [ ] Start the frontend.
- [ ] Open Model Adapters.
- [ ] Confirm the Local Detector setup panel shows
      `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH`,
      `MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH`, and
      `MOCKINGBIRD_LOCAL_DETECTOR_CONFIDENCE_THRESHOLD`.
- [ ] Confirm the setup panel says model files are not bundled or downloaded,
      detector output is DetectionProposal evidence, and ReviewLabel correction
      remains truth.
- [ ] Open Streams and configure or select an external snapshot camera/source.
- [ ] Configure a browser-playable or RTSP Live stream URL and stream type if
      available.
- [ ] Optionally configure `local_usb` with a device path such as `/dev/video0`.
- [ ] On Windows, optionally configure `local_usb` with `windows_dshow`, a
      DirectShow camera name, and a Windows `ffmpeg.exe` path when running the
      API in WSL.
- [ ] Confirm Live view appears in the Stream card.
- [ ] Confirm a missing Live stream URL shows `No live stream URL configured.`
- [ ] Confirm an RTSP URL shows bridge playback when host `ffmpeg` is available,
      or `RTSP bridge unavailable` when it is not.
- [ ] Confirm local USB camera playback shows bridge playback when host
      `ffmpeg` and the device are available, or a local camera unavailable state
      when they are not.
- [ ] Confirm Windows DirectShow playback shows bridge playback when camera name
      and Windows `ffmpeg.exe` path are available, or a clear setup state when
      they are not.
- [ ] Open Stream Detail, open Live view, and confirm existing Zones render over
      the real camera surface.
- [ ] Draw or edit a feeder/ignore/privacy Zone over the live stream and save it.
- [ ] Refresh Stream Detail and confirm the Zone remains aligned to the live
      surface.
- [ ] With a MockingBird-served Live view open, click `Start monitoring`.
- [ ] Confirm monitoring compares recent live frames from this stream and shows
      recent frame count plus last checked time.
- [ ] Move in front of the camera or move an object in frame.
- [ ] Confirm activity is detected, the best live frame is saved, and review
      activity remains an explicit handoff.
- [ ] Confirm live monitoring names the triggered Zone, such as
      `Activity detected in Feeder`, and says the best frame was saved from
      that Zone.
- [ ] If motion occurs only in an ignore/privacy Zone, confirm the UI reports
      ignored motion and no review activity or Bird Log entry is created.
- [ ] Keep moving or click `Create review activity` twice and confirm duplicate
      activity shows a quiet/cooldown state instead of creating duplicate review
      candidates.
- [ ] Click `Create review activity` and confirm Review Queue shows an
      uncertain needs-review activity with the saved best frame, Zone name, and
      low-confidence suggestion.
- [ ] Confirm `Open Review Queue` lands on the new needs-review item without a
      browser reload, and High sensitivity shows strongest change/threshold
      diagnostics for small feeder movement.
- [ ] Confirm Bird Log does not update until later review/correction.
- [ ] Click `Stop monitoring` and confirm Live view can remain open.
- [ ] From a local camera Live view, click `Capture frame`.
- [ ] Confirm one saved image appears for the Stream and no ReviewLabel/export
      truth is created.
- [ ] Confirm the capture success says the frame will not appear in Bird Log
      until activity is created/reviewed.
- [ ] Confirm the motion action is disabled/helpful after one capture and says
      to capture another frame before checking motion.
- [ ] Capture a second local camera frame and confirm `Compare captured frames`
      becomes available from the capture handoff.
- [ ] Run the frame comparison from the capture handoff and confirm captured
      JPEG frames decode as fallback saved evidence, while review activity,
      Bird Log, and export still require explicit later actions.
- [ ] Confirm Source health / Camera status is visible for the selected Stream.
- [ ] Confirm Field test readiness appears and shows the next step for this
      Stream.
- [ ] Confirm Storage guardrails shows saved image count and monitoring
      readiness.
- [ ] Confirm Camera Monitoring shows Start monitoring, Stop monitoring, and
      Refresh status for the external snapshot Stream.
- [ ] Click `Test snapshot`.
- [ ] Confirm Field test readiness updates the Snapshot test row.
- [ ] Confirm success/failure, timestamp, content type, and preview image when available.
- [ ] Confirm Last snapshot test updates in Source health.
- [ ] Click `Capture snapshot`.
- [ ] Confirm the saved image appears under that camera/source and Stream.
- [ ] Confirm Last capture and Saved images update in Source health.
- [ ] Capture a second snapshot and confirm Field test readiness says saved
      images are ready for motion.
- [ ] Confirm Storage guardrails updates saved image count and motion readiness.
- [ ] Click `Start monitoring`.
- [ ] Confirm monitoring status becomes Starting or Monitoring.
- [ ] Confirm Last checked, Last snapshot, snapshots saved, motion checks, and
      Last activity update over time.
- [ ] If user-zone-backed activity appears, confirm `Create review activity`
      is available, click it, and confirm `Open Review Queue` shows an
      unknown/low-confidence activity without creating reviewed truth.
- [ ] If automatic activity areas appear without a named Zone, confirm the UI
      explains that review activity creation needs a named Zone in this build.
- [ ] Choose Feeder, Birdbath, Ground, Yard, Driveway, Ignore, Privacy, or
      Other, optionally rename the area, and click `Mark this area`.
- [ ] Confirm a real Zone is saved and the UI says to run `Check motion` again
      or continue monitoring.
- [ ] For Feeder, Birdbath, Ground, Yard, Driveway, or Other, rerun `Check
      motion` or continue monitoring and confirm future user-zone-backed
      activity can offer `Create review activity`.
- [ ] For Ignore or Privacy, confirm the area is saved as a skip/suppression
      Zone and no reviewed truth or export is created automatically.
- [ ] Click `Stop monitoring`.
- [ ] Confirm monitoring stops and does not create reviewed truth or exports.
- [ ] Click `Start watch`.
- [ ] Confirm Snapshot watch is shown as an advanced test harness and captures a
      small bounded run while the page stays open.
- [ ] Confirm `Stop watch` stops the run and keeps captured snapshots visible.
- [ ] Confirm no capture continues after Stop watch or navigation.
- [ ] Capture at least one more saved snapshot for the same Stream.
- [ ] Click `Check motion`.
- [ ] Confirm `New activity detected`, `Ongoing activity`, `Cooldown active`,
      or `No activity detected` appears with an Activity area and best snapshot
      context.
- [ ] Confirm Field test readiness moves from Check motion toward Mark activity
      area, Start monitoring, or Create review activity as appropriate.
- [ ] Confirm Last motion check, Last activity, and next recommended action update
      in Source health.
- [ ] Confirm Storage guardrails still shows manual next actions and no cleanup button.
- [ ] Confirm `Focused crop planned` appears when activity is detected and that
      the full best snapshot remains the source/context image.
- [ ] Run `Check motion` again for the same saved snapshots and confirm the
      same-area result does not encourage duplicate review activity.
- [ ] If no Zones exist, confirm automatic activity areas are used.
- [ ] Confirm automatic activity areas are motion-only; do not run model analysis
      per activity area.
- [ ] If activity is detected and review activity is available, click `Create review activity`, then `Open Review Queue`.
- [ ] Confirm no reviewed data or Bird Log history is created until a later correction.
- [ ] Confirm no capture starts before explicit Start watch, and Live view does
      not start monitoring or review activity.
- [ ] Confirm Snapshot watch starts only after explicit Start watch and stops at
      its bounded capture count.
- [ ] Confirm reviewed/export-linked media protection copy appears before export.
- [ ] Confirm image status shows Not analyzed, Suggestion available, Needs review, or Reviewed.
- [ ] Confirm local detector readiness is visible for saved image media.
- [ ] If not configured, confirm setup guidance and demo analysis fallback.
- [ ] If configured with `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH`, run the local
      detector explicitly and confirm suggested labels.
- [ ] Otherwise click `Analyze image (demo)`.
- [ ] Send the suggestion to Review when needed.
- [ ] Open Review.
- [ ] Submit an explicit correction.
- [ ] Open Bird Log and confirm the reviewed observation appears with label,
      time, source, and image context.
- [ ] Return to the Stream saved images and confirm reviewed/export status when
      inferable from existing corrections.
- [ ] Create a reviewed-only Dataset Export and inspect the proof record.

This path uses existing explicit browser actions only. Demo proposal creation is
synthetic evidence, runs no model, and does not create ReviewLabel truth.
Preview, save, evidence creation, and promotion also do not create truth. They
are separate from Live view. Saved timeline media can be reused later for
proposal evidence or MotionEvidence, and the timeline shows duplicate-safe
lifecycle status, but reuse is still user-triggered and evidence-only.
Optional local detector runs require an explicit local model path, can use an
optional labels path and confidence threshold, do not download models, and
create proposal evidence only.

## Step 1 - Dashboard MVP Readiness

- [ ] Open Dashboard.
- [ ] Confirm the Start here/MVP path explains first actions for a sparse local app.
- [ ] Find the MVP readiness/provider workflow section.
- [ ] Confirm provider cards for `external_url`, folder/trail-cam, webhook, and
      manual media.
- [ ] Confirm Live view is limited to configured browser-playable stream URLs or
      optional RTSP/local camera bridge playback.
- [ ] Confirm next action links exist.
- [ ] Confirm truth-boundary copy is visible.
- [ ] Open Model Adapters and confirm Local Detector setup guidance is visible
      without configuring or running a model.
- [ ] For a real local model smoke check, configure the local model path if you
      have one, restart the API, capture/import an image, run Analyze image from
      the saved image, review/correct the suggested label, confirm Bird Log, and
      export reviewed data.

## Step 2 - external_url Provider Path

- [ ] Open Streams.
- [ ] Select or configure a Source as `external_url`.
- [ ] Enter safe HTTP still-image URL metadata.
- [ ] Optionally enter a Live stream URL and choose MJPEG, Browser video,
      HLS/browser-supported, RTSP bridge, or configure a local USB camera device.
- [ ] Confirm setup review/status says explicit preview is available and
      future-safe.
- [ ] Confirm the Live view panel attempts browser-direct playback for
      browser-playable URLs and uses RTSP/local camera bridges only when host
      `ffmpeg` is available.
- [ ] Confirm Source health / Camera status shows readiness for manual checks.
- [ ] Confirm Storage guardrails shows saved image counts and no cleanup/delete controls.
- [ ] Confirm Snapshot watch controls are visible and explain that the watch only
      runs while the page is open after Start watch.
- [ ] Click `Test snapshot`.
- [ ] Confirm transient preview appears with success/failure, timestamp, and
      content type.
- [ ] Confirm Last snapshot test updates in Source health.
- [ ] Confirm no Event, Visit, or truth is created.
- [ ] Click `Capture snapshot`.
- [ ] Confirm the saved image appears under the selected camera/source and
      Stream.
- [ ] Confirm Last capture and Saved images update in Source health.
- [ ] Confirm Storage guardrails updates saved image count.
- [ ] Start Snapshot watch.
- [ ] Confirm it is marked as a bounded page-local test harness, not Camera
      Monitoring Core.
- [ ] Confirm captured snapshot count, motion check count, and last activity
      result update during the bounded run.
- [ ] Stop Snapshot watch or wait for the capture limit.
- [ ] Confirm no watch continues after Stop watch or navigation.
- [ ] Capture at least one more saved snapshot for the same Stream.
- [ ] Click `Check motion`.
- [ ] Confirm `New activity detected`, `Ongoing activity`, `Cooldown active`,
      or `No activity detected` appears with an Activity area.
- [ ] Confirm Last motion check, Last activity, and next recommended action update
      in Source health.
- [ ] Confirm Storage guardrails recommends review/export when useful activity exists.
- [ ] Confirm Focused crop planning appears for detected activity while the full
      snapshot remains saved.
- [ ] Run `Check motion` again for the same Activity area and confirm duplicate
      review activity is not encouraged.
- [ ] Confirm this path remains manual only; Live view stays separate from
      snapshot capture and Snapshot watch starts only after Start watch.
- [ ] Confirm cleanup/deletion remains separate and is not available in this flow.
- [ ] If no Zones exist, confirm automatic activity areas are used.
- [ ] Confirm model analysis remains separate and is not run per automatic
      activity area.
- [ ] If activity is detected and review activity is available, create the
      uncertain Review Queue activity before correction.
- [ ] Confirm image status is visible before analyzing.
- [ ] Confirm local detector readiness and analyze only if configured.
- [ ] Otherwise use `Analyze image (demo)`.
- [ ] Send the suggestion to Review.
- [ ] Open Event Detail and Visit Detail.
- [ ] Confirm no label/truth yet.
- [ ] Open Review and filter by search text, item type, evidence/media state,
      and stream/source context to find the review item.
- [ ] Submit a correction.
- [ ] Confirm correction becomes truth.
- [ ] Open Bird Log and confirm the corrected activity appears in history.

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
- [ ] Confirm evidence context is visible for imported/demo proposal records.
- [ ] Submit or view corrections.
- [ ] Confirm the saved correction is shown as ReviewLabel truth.
- [ ] Confirm corrected Visit state.
- [ ] Confirm raw evidence/provider labels are not truth.

## Step 6 - Analytics, Export, And Classifier Readiness

- [ ] Open Analytics.
- [ ] Open Dataset Exports.
- [ ] Create a reviewed-only export.
- [ ] Inspect manifest records, Event/Visit IDs, Source/Stream/Zone context,
      media references, skipped reasons, and detection evidence.
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
- Dataset exports are explicit user/developer actions.
- Analytics/export/classifier readiness derive from corrections.
- External labels/confidence are untrusted evidence metadata.
- Demo proposals are evidence; no model inspects browser/CLI smoke media.

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
- API unavailable: start the backend command and rerun
  `.venv/bin/python scripts/check_mvp_smoke.py`.
- No Streams or Zones: reset or seed demo data before the browser proof loop.
- No media file: choose an existing local image for Import Media or CLI smoke.
- No Review Queue items: import and convert evidence first, or check whether all
  items were already corrected.
- Export has skipped records: inspect skipped reasons; reviewed-only exports
  intentionally exclude unreviewed candidates.

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
