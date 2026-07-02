# External URL Preview To MediaAsset Handoff Design

## Purpose

Phase 11C external URL previews are transient and not saved. A future user may
want to keep a fetched still image as local media evidence or context, but saving
preview bytes is more sensitive than showing them transiently.

This handoff design defines the boundary for a future explicit save action.
MediaAsset storage must be user-triggered, local-first, bounded, cleanup-aware,
and truth-safe.

## Product Flow

external_url Source setup -> explicit still-image preview fetch -> user reviews
transient preview -> optional future "save preview as MediaAsset" -> MediaAsset
linked to Source/Stream context -> optional future explicit evidence/import/review
flow -> Event/Visit review -> user correction -> ReviewLabel truth.

## Current Phase 11C Behavior

- Preview fetch is explicit.
- Preview is transient.
- Preview is returned as a data URL.
- No file is written.
- No MediaAsset is created.
- No Events, Visits, MotionEvidence, ReviewLabels, or truth are created.
- No background worker exists.

## Future Save-preview Action

A future explicit action could use one of these route shapes:

- `POST /api/sources/{source_id}/external-url/preview/save`
- `POST /api/sources/{source_id}/external-url/preview` followed by
  `POST /api/sources/{source_id}/external-url/preview-media-assets`

This phase does not implement either route.

The future action should:

- Be user-triggered only.
- Reuse the same URL, security, content-type, timeout, and max-byte guardrails.
- Write one bounded still-image file.
- Create one MediaAsset.
- Link the MediaAsset to Source and Stream when available.
- Record provenance from the `external_url` provider.
- Create no Event or Visit unless separately and explicitly requested.
- Create no ReviewLabel or truth.

## MediaAsset Provenance

Future saved preview metadata should record:

- `provider_key`: `external_url`
- `source_id`
- `stream_id`, if selected or inferable
- `fetched_at`
- `content_type`
- `bytes_written`
- `original_url_host` or a safe redacted URL summary
- `url_config_field`: `url`
- `preview_fetch_request_id`, if future request IDs exist
- `save_reason` or user note, if useful

It must not record raw credentials or raw auth secrets.

## Storage Policy

- Saved previews must live under ignored local media/data paths.
- Generated media must not be committed.
- File names must be safe.
- Use stable IDs or generated UUID names, not user URL paths.
- Preserve extension from content type.
- Max bytes remains bounded.
- Repeated saves must not become unbounded without cleanup policy.
- Cleanup and retention must be explicit before implementation.

## Supported Content Policy

- Initially support only `image/jpeg`, `image/png`, and `image/webp`.
- No video.
- No multipart stream responses.
- No HTML, text, or JSON.
- No image decoding is needed to save bytes.
- Optional future image validation can be designed separately.

## Source/Stream/Zone Relationship

- MediaAsset should know Source/Stream context where possible.
- Zone editing remains separate.
- Saved preview can be visual context for a Stream.
- Saved preview does not automatically create zone-specific evidence.
- Future attach-to-zone or evidence behavior requires separate design.

## Evidence/Event Boundary

- Saved MediaAsset is not MotionEvidence.
- Saved MediaAsset is not an Event.
- Saved MediaAsset is not a Visit.
- Saved MediaAsset is not a ReviewLabel.
- Saved MediaAsset does not mark anything reviewed.
- Future promotion from saved preview to MotionEvidence, Event, or Visit must be
  explicit and separately designed.
- Correction remains truth.

## Privacy/Ignore Boundary

- External preview may contain outdoor camera imagery.
- Saving should be explicit and clearly labeled.
- Privacy and ignore zones cannot be applied retroactively unless future
  crop/masking is designed.
- Future automated evidence from saved previews must respect Privacy Zones and
  Ignore Zones.
- No cloud upload by default.
- User controls saved local files.

## Security/Network Boundary

- Save-preview should reuse Phase 11C URL guardrails.
- No redirects unless explicitly scoped later.
- Use bounded timeout and max bytes.
- Do not echo credentials.
- Do not log raw secrets.
- Avoid SSRF-prone fetch behavior.
- No background refresh.
- No scheduled fetch loop.

## API Response Design

Future response fields should include:

- `media_asset_id`
- `source_id`
- `stream_id`
- `status`
- `message`
- `content_type`
- `bytes_written`
- `file_name` or `relative_path`
- `fetched_at`
- `creates_event`: false
- `creates_visit`: false
- `creates_truth`: false
- `warnings`

## UI Design

After a transient preview appears, the UI may show `Save preview as local media`.
Copy should say: "This saves the still image locally but does not create Events,
Visits, or truth."

After save, the UI should show a saved MediaAsset link or preview. It should not
auto-save, auto-refresh, say "record", imply stream capture, or claim live
playback.

## Testing Expectations For Future Implementation

Future implementation must test:

- Save action requires `external_url` provider.
- Missing URL does not save.
- Unsupported content type does not save.
- Oversized response does not save.
- Unsafe URL does not save.
- One save creates one MediaAsset.
- No Events, Visits, MotionEvidence, or ReviewLabels are created.
- No truth mutation occurs.
- File is written only under ignored local media path.
- Extension and file name are safe.
- No secret leakage.
- Redirects are not followed.
- No background fetch occurs.
- Cleanup and retention behavior is documented.

## Relationship To Manual Media Import

Manual import remains explicit user-supplied local media. Saved external URL
preview would be provider-fetched local media. Both can become MediaAsset
records, and neither creates truth without review/correction.

Existing manual media import may create reviewable Events/Visits by explicit
behavior. Saved preview should not automatically do that unless a future route
explicitly chooses it.

## Relationship To Classifier/Export Pipeline

- Saved preview MediaAssets are not training truth by themselves.
- Classifier readiness/export requires reviewed corrections.
- SpeciesSuggestion and MotionEvidence remain evidence only.
- ReviewLabel correction remains training truth.

## Recommended Future Phases

- Phase 11E: preview-to-MediaAsset save implementation, explicit save only, no
  Events/Visits/truth.
- Phase 11F: saved preview review/evidence handoff design.
- Phase 11G: explicit saved-preview-to-MotionEvidence or manual-review flow.
- Later: other source-provider handoff designs separately.

## Explicit Non-Goals

- No implementation in this phase.
- No media writes.
- No MediaAsset creation.
- No Events or Visits.
- No MotionEvidence.
- No ReviewLabels.
- No truth creation.
- No live playback.
- No workers.
- No scheduled fetch.
- No video decoding.
- No model/training work.
