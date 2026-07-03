# Source Provider Configuration Contract

## Purpose

Define how MockingBird stores intended Source provider metadata before any real
provider implementation exists. This is setup metadata for product readiness, not
camera connection, media decoding, stream work, or provider execution.

## Product Flow

Source -> intended provider/config metadata -> setup review -> connection
readiness -> Stream playback contract -> future real adapter implementation.

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

`manual_media` is an available metadata path for explicit local media import. It
can guide users toward importing media for a Source/Stream, but it does not imply
live playback, capture, or automatic media analysis.

`external_url` is the contract for future explicit HTTP still-image
preview/status. See
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md).
Its configuration metadata may include `url`, optional `label` or
`display_name`, optional `auth_username`, optional `auth_password`, optional
`refresh_hint_seconds`, and optional `notes`. This metadata does not fetch or
validate URLs by itself. The non-secret `url` can feed the explicit preview
route; secret authentication metadata is still not used for fetch unless a
future phase scopes it.
Provider configuration can feed the explicit preview and save-as-MediaAsset
routes, but it does not store media itself.
Saved preview media still needs a separate explicit review/evidence handoff
before it can become MotionEvidence, Event/Visit context, or correction truth.

`folder_import_future` is the recommended future provider key for Folder /
trail-cam import. It should store setup metadata such as sensitive
`folder_path`, optional `display_name`, `recursive`, `allowed_extensions`,
`default_stream_id`, `default_zone_id`, future `import_mode`, and `notes`.
This metadata must not scan folders, validate paths by reading them, import
media, create records, or imply a background watcher. See
[folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md).
Phase 13B represents this provider in configuration/status contracts only:
`folder_path` is required and redacted to configured/not-configured, while
boolean/list-like fields are stored as metadata strings until a future parser is
scoped.

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

For `folder_import_future`, `folder_path` is sensitive local data and follows
the same marker policy. API responses and the Streams UI must not echo raw local
folder paths.

## Relationship To Source Connection Status

Source connection status reads provider configuration metadata to report
configured and missing fields. A Source can be `configured` while
`supports_live_playback` remains false because real provider behavior is still a
future phase.

## Relationship To Source Setup Review

Source setup review is a read-only product summary over provider configuration,
source connection readiness, and related Stream playback readiness. It can report
next setup steps, missing metadata, and future provider requirements, but it does
not connect, capture, decode, inspect media, create evidence, or write truth.
For `manual_media`, setup review should point to explicit import/review flows
while preserving correction as the truth boundary.

In the app, provider configuration appears inside the consolidated Source setup
flow beside setup readiness, next action, related Streams, playback honesty, and
manual import cues.

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

Future provider implementation must follow
[source-adapter-boundary-design.md](source-adapter-boundary-design.md).
Provider configuration metadata feeds future adapters, but it does not implement
them or make provider runtime claims by itself.
External URL implementation must also follow
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md)
before any URL fetch or validation behavior is added.
Folder/trail-cam implementation must follow
[folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md)
before any folder scan, import, copy/reference behavior, watcher, polling, media
record creation, or truth-affecting behavior is added.

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
- `folder_import_future` exposes `folder_path` as required/sensitive metadata.
- Source provider configuration returns safe status for known sources.
- Unknown sources return 404.
- Unknown provider keys are rejected.
- Secret fields are never returned or stored raw.
- Source connection status reflects configured and missing fields.
- Stream playback remains honest and does not claim live playback.
- Manual media setup points to explicit import/review, not live playback.
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
