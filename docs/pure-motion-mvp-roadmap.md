# Pure Motion MVP Roadmap

## Purpose

This roadmap locks the next video/event direction for MockingBird: build the first
robust outdoor activity trigger without requiring a detector model. The MVP should
use lightweight motion, saved snapshots, sessionization, and user review to create
useful bird/outdoor activity history before MegaDetector, SpeciesNet, or custom
classifier runtime become required.

This is not a rejection of future detector/classifier work. It defines the
model-free event trigger path so the product can remain plug-and-play, local-first,
and resilient when no model files are configured.

## Product Target

Primary loop:

1. Add or select a camera/source.
2. Test and capture snapshots.
3. Evaluate motion across repeated snapshots/frames.
4. Group repeated motion into one activity session/visit.
5. Save a full snapshot and optional focused crop.
6. Send the activity to Review.
7. User corrects the label/species/activity.
8. Reviewed item appears in Bird Log.
9. Reviewed data can be exported.

The user should experience this as:

```text
Camera -> activity detected -> best snapshot/crop -> review -> Bird Log -> export
```

not as:

```text
MotionEvidence -> frame planes -> payloads -> proposals -> internal lifecycle
```

## Strategic Decision

The MVP event trigger is pure motion first.

- Motion detection decides **when and where something changed**.
- Optional local classifier/model suggests **what it might be** after a candidate
  image exists.
- User correction remains the only dataset/export truth.
- MegaDetector-family detectors are optional later enrichment for boxes,
  blank-frame filtering, and false-positive reduction.
- SpeciesNet/custom classifiers are optional later species suggestion layers.

Do not require MegaDetector, SpeciesNet, or any detector model for the first
working video/event MVP.

## Plug-and-Play Requirement

User-drawn zones must not be required for the default experience.

Default behavior:

- If user zones exist, use them.
- If no zones exist, create virtual auto-regions from the frame/grid and score
  motion by region.
- Privacy and ignore zones remain available as explicit user controls.
- User-defined feeder/birdbath/ground/driveway zones improve accuracy, cooldowns,
  and analytics, but they are refinement rather than mandatory setup.

Product levels:

1. Whole-scene / grid motion by default.
2. Auto activity regions from repeated motion clusters.
3. Optional user-confirmed regions such as feeder, birdbath, ground, driveway.
4. Advanced privacy/ignore zones.

## Current Foundation

Already built or partially built:

- external URL snapshot source path: Test snapshot -> Capture snapshot -> saved image
- saved images under camera/source
- Analyze image action with demo/local model fallback
- Review Queue and explicit correction truth
- Bird Log / Activity History
- dataset/export proof path
- deterministic zone-aware motion scoring for supplied frame planes
- motion sequence evaluation for caller-provided frames
- MotionEvidence schema/API/review/promote bridge
- MediaAsset attachment to MotionEvidence
- saved-snapshot Check motion with automatic activity areas when no user Zones exist
- saved-snapshot Activity session recommendation with per-area duplicate suppression
- saved-snapshot focused Activity crop planning while preserving the full best snapshot
- source health / camera status for manual snapshot tests, captures, saved image
  counts, and saved-snapshot motion readiness
- storage guardrails for saved image counts, accumulation warnings, and
  reviewed/export-linked media protection before manual Snapshot watch
- manual bounded Snapshot watch for external_url Sources while the page is open,
  using existing capture and Check motion actions
- truth boundary: model/motion outputs are not truth; ReviewLabel correction is truth

Not yet complete:

- derived focused crop file creation
- persistent capture health sufficient for automatic/repeated capture
- enforced storage/retention limits for automatic activity capture
- live video / RTSP / USB / ESP32 adapters
- automatic workers, polling, schedulers, or continuous frame sampling

## Required Next Updates Before Live Video Troubleshooting

### 1. Saved Snapshot Motion Bridge

Use already-saved snapshots from the same camera/source/stream as the first real
frame input.

Capability:

```text
2+ saved snapshots -> motion score -> activity detected/no activity detected
```

Rules:

- explicit user action only, such as `Check motion`
- no live video
- no polling/worker/scheduler
- no automatic capture
- no model runtime
- no truth writes
- no exports

This proves that real saved camera images can feed the motion core.

### 2. Plug-and-Play Auto Regions

Add a fallback region strategy when no user zones exist.

Capability:

```text
whole image -> grid/auto regions -> motion clusters -> candidate activity area
```

Rules:

- user zones override/refine auto regions when present
- privacy/ignore zones suppress automatic activity cells when configured
- no requirement to draw feeder zones before first useful result
- user-facing copy should say `Activity area`, not internal region IDs
- Auto Regions 1 status: saved-snapshot Check motion scores a medium adaptive
  grid, merges active neighboring cells into up to three Activity areas, and
  keeps automatic-area results evidence-only until a later persistence phase.

### 3. Activity Sessionization / Anti-Flood Logic

Create a shared session layer that groups repeated motion triggers into one
meaningful activity/visit candidate.

Goal:

```text
one bird hanging around -> one activity session, not 800 images
```

Core behavior:

- state is scoped by source/stream/region-or-zone
- require motion persistence across multiple samples before opening a session
- keep a session open while motion continues
- update the best snapshot/crop when a better frame appears
- close after a quiet period
- apply cooldown to that region only, not the whole camera
- allow separate regions to trigger independently
- Activity Sessionization 1 status: explicit saved-snapshot motion checks now
  classify results as new, ongoing, cooldown-suppressed, or no activity, return
  a best snapshot, and suppress duplicate review activity creation for the same
  Stream and Activity area within the quiet/cooldown window. Repeated capture,
  crop generation, and automatic source checks remain future work.

Early output should count visits/observations, not exact individual birds.

### 4. Full Snapshot + Focused Motion Crop

Always keep full-frame context, and optionally add a padded crop around the motion
region.

Storage policy per activity session:

- one full representative snapshot
- one focused activity crop when possible
- optional small thumbnail for UI later
- a small capped number of alternate snapshots only when useful

Never save crop-only as the source record. The crop helps review/model input; the
full snapshot preserves context and auditability.

Motion Crop 1 status: explicit saved-snapshot motion checks now return a padded
focused Activity crop plan for the best snapshot. The full best snapshot remains
the source/context image, no crop media file is created yet, and future
classifier/model enrichment should use the finalized activity session's best
snapshot/crop rather than every grid cell.

### 5. Source Health / Capture Status

Before Snapshot watch or live troubleshooting, each camera/source should make
capture reliability obvious.

Show:

- last successful snapshot time
- last failed snapshot time
- friendly error message
- content type
- saved image count
- current source status

Source Health 1 status: Cameras/Streams now shows browser-state Source health
for manual checks. It confirms the last snapshot test, last capture, saved image
count, last motion check, last activity, and next recommended action without
starting live video or server automation. Snapshot watch remains user-started,
bounded, and page-local.

This prevents confusing camera/network failures with app failures.

### 6. Storage And Retention Guardrails

Before any automatic/repeated capture, define safe defaults.

Defaults should include:

- maximum snapshots per activity session
- maximum full images retained per source/day before warning
- duplicate/near-duplicate suppression where feasible
- reviewed/export-related media protected by default
- destructive cleanup remains explicit and confirmed, not automatic

Storage Guardrails 1 status: Cameras/Streams now shows read-only Storage
guardrails for each Stream: saved image counts, storage estimate when known,
accumulation warnings, review-linked/protected counts when inferable, and the
next manual action before Snapshot watch. It adds no deletion, cleanup,
live video, workers, schedulers, or automatic truth.

### 7. Repeated Snapshot Watch

Bridge manual snapshots into a short source watch without live playback.

Repeated Snapshot Watch 1 status: Cameras/Streams now has a manual, bounded
Snapshot watch for `external_url` Sources. The watch runs only while the page is
open after Start watch, captures a small preset number of snapshots, refreshes
Source health and Storage guardrails, and uses existing Check motion after at
least two saved snapshots. It creates no truth, exports, server jobs, or live
video behavior.

Snapshot watch is a bounded browser/page-local test harness, not the final
monitoring architecture. Do not expand it into the product center.

### 8. Camera Monitoring Core

The next real implementation target is Camera Monitoring Core.

Camera Monitoring Core should be backend-managed, explicit start/stop,
external_url first, and adapter-ready later. It should turn camera activity into:

```text
camera/source -> activity detected -> Review -> Bird Log -> export
```

while keeping internal developer surfaces secondary to Cameras/Streams, Review,
Bird Log, and Exports/Data.

## Detector And Classifier Position

Detector models are not required for the pure-motion MVP.

Future optional detector role:

- filter leaves/shadows/blank frames
- produce object boxes
- improve crop selection
- reduce false positives

Future classifier role:

- suggest species/activity labels from the best snapshot/crop
- never run classifier/model inference per auto-region cell
- run future classifier/model enrichment only on the best snapshot/crop for a
  finalized activity session
- remain evidence only until user correction

The shared activity/session layer must be trigger-agnostic so future inputs can
feed the same product path:

- pure motion trigger
- detector trigger
- camera webhook
- manual snapshot
- folder/trail-cam import

All roads should end at:

```text
activity candidate -> Review -> ReviewLabel truth -> Bird Log -> export
```

## Preferred Roadmap From Here

1. **Saved Snapshot Motion Bridge**
   - Compare saved snapshots from the same source/stream.
   - Return activity/no activity.
   - Optionally create pending review activity through explicit action.

2. **Auto Regions 1**
   - Allow motion checks without user-drawn zones.
   - Use grid/region clustering as default.

3. **Activity Sessionization 1**
   - Add anti-flood grouping, quiet period, region cooldown, best snapshot update.

4. **Motion Crop 1**
   - Add full-frame + padded activity crop records for review/model input.

5. **Source Health 1**
   - Status: manual Source health is visible in Cameras/Streams for snapshot,
     capture, saved-image, and motion readiness.

6. **Storage Guardrails 1**
   - Status: read-only saved-image counts, accumulation warnings, and
     reviewed/export-linked protection are visible before repeated checks.

7. **Repeated Snapshot Watch 1**
   - Status: manual start/stop Snapshot watch from external_url source is
     page-local, bounded, motion-check only, and contained as a test harness.
   - Still no RTSP/USB/ESP32/live video worker.

8. **Camera Monitoring Core**
   - Next real implementation target.
   - Backend-managed, explicit start/stop, external_url first, adapter-ready
     later.
   - Do not expand the browser Snapshot watch harness as the final architecture.

## Guardrails

Do not add for this MVP path:

- MegaDetector runtime
- SpeciesNet runtime
- model downloads
- bundled model files
- dependency/package changes unless explicitly scoped
- live video before repeated-snapshot behavior is safe
- RTSP/USB/ESP32 adapters before sessionization/storage guardrails
- automatic ReviewLabel truth
- automatic exports
- automatic reviewed Event/Visit state
- broad internal UI surfaces

## Product Success Criteria

The pure-motion MVP is successful when a user can run MockingBird with no model
configured and still get:

```text
camera/source -> activity detected -> best snapshot/crop -> review -> Bird Log
```

with manageable data volume, no duplicate flood, no automatic truth, and optional
zones/classifiers improving the result later rather than blocking first use.
