# Source Provider Configuration Contract

## Purpose

Define how MockingBird stores intended Source provider metadata before any real
provider implementation exists. This is setup metadata for product readiness, not
camera connection, media decoding, stream work, or provider execution.

## Product Flow

Source -> intended provider/config metadata -> connection readiness -> Stream
playback contract -> future real adapter implementation.

## Provider Definitions

Provider definitions describe supported setup contracts:

- `demo`
- `manual_media`
- `external_url`
- `rtsp_future`
- `esp32_future`
- `browser_camera_future`
- `folder_import_future`
- `webhook_future`

Future-labeled providers are placeholders/contracts only. They do not implement
live playback or source connection behavior.

## Provider Configuration Fields

Each provider definition can expose fields with:

- `key`
- `label`
- `required`
- `secret`
- `description`
- `placeholder`

Configuration returns `configured_fields`, `missing_fields`, and
`safe_config_preview` so the UI can show readiness without exposing unsafe
details.

## Secret/Redaction Policy

Secret fields are never returned raw. When a secret field is supplied,
MockingBird stores and returns only a configured/not-configured marker. This
phase does not store real credentials or validate them.

## Relationship To Source Connection Status

Source connection status reads provider configuration metadata to report
configured and missing fields. A Source can be `configured` while
`supports_live_playback` remains false because real provider behavior is still a
future phase.

## Relationship To Stream Playback Status

Stream playback status remains stream-specific. Provider configuration can make
the upstream Source better described, but Stream Detail should still show demo or
placeholder playback until a real provider exists.

## What This Phase Does

- Adds provider definition and configuration API contracts.
- Stores safe Source provider metadata locally.
- Redacts secret fields to configured/not-configured markers.
- Shows a compact Source setup surface on Streams.
- Updates Source connection readiness from provider configuration metadata.

## What This Phase Does Not Do

- Connect to real sources.
- Validate URLs by network call.
- Decode media or capture frames.
- Add providers, stream workers, schedulers, or new dependencies.
- Run models or training.
- Create MotionEvidence, Events, Visits, ReviewLabels, SpeciesSuggestions,
  exports, analytics truth, or dataset truth.

## Future Adapter Implementation Relationship

Future RTSP, USB/local camera, ESP32-CAM, browser, folder, webhook, or external
URL providers may consume this metadata later. They must remain underneath the
Source, Stream, Zone, Event, Visit, review/correction, export, and analytics
loop.

## Zone Editing Relationship

Zone editing can continue with demo or placeholder stream panels. Provider
configuration helps describe the intended Source but does not block zone
planning when Streams already exist.

## Privacy/Ignore Relationship

Privacy and ignore zones remain stream-level user intent. Future provider
implementations must respect those zones when later phases create evidence or
reviewable activity.

## Testing Expectations

- Provider definitions include expected keys and field metadata.
- Source provider configuration returns safe status for known sources.
- Unknown sources return 404.
- Unknown provider keys are rejected.
- Secret fields are never returned or stored raw.
- Source connection status reflects configured and missing fields.
- Stream playback remains honest and does not claim live playback.
- Provider configuration does not create evidence, review truth, exports, media
  files, model artifacts, or runtime calls.

## Explicit Non-Goals

- No real live video playback.
- No real camera/source connection.
- No URL validation by network call.
- No frame capture, media decoding, worker, scheduler, or provider
  implementation.
- No model inference, training, model files, or generated media.
- No changes to review/correction truth semantics.
