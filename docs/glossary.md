# MockingBird Glossary

## Camera

A user-facing outdoor camera concept.

## Source

An adapter-backed input that can provide video, images, clips, or stream data.

## Stream

The central video experience shown in the app.

## Zone

A user-drawn area on a stream that gives outdoor activity context.

## Feeder Zone

A zone around a bird feeder.

## Birdbath Zone

A zone around a birdbath or water source.

## Privacy Zone

A zone where detection, storage, or review should be limited or disabled.

## Ignore Zone

A zone where activity should not create normal review events.

## Event

A meaningful outdoor activity record.

## Visit

A reviewable animal-centered event, especially around feeders, birdbaths, perches, or yard zones.

## Detection

A machine-generated observation that may be right or wrong.

## Motion Candidate

A debounced motion signal from scored frame differences in a stream zone.

## Best Frame

The candidate frame most useful for review context or later species suggestion; it is evidence context, not truth.

## Local Frame Artifact

A future local visual evidence reference for a selected frame; it is distinct from frame planes and is not truth.

## Sampled Frame

A lightweight local representation of a stream or media moment that can become a frame plane for motion scoring; it is not reviewed truth.

## Frame Plane

A rectangular 2D array of numeric grayscale values used for zone-aware motion scoring.

## Sampler

A local component that can produce frame planes from configured stream or media context; it is not a source adapter, detector, or truth source.

## Motion Evidence

Local evidence that a motion candidate occurred in a stream zone; it is not reviewed truth.

## Motion Evidence Promotion

An explicit action that turns pending Motion Evidence into unreviewed Event/Visit evidence; it does not create reviewed truth.

## SpeciesSuggestion

Local classifier evidence that a media item or crop may contain a species or taxon; its pending/accepted/rejected/superseded status is not reviewed truth.

## SpeciesSuggestionAdapter

A local optional adapter that creates SpeciesSuggestion evidence from media-backed Event/Visit context without creating labels, exports, or dataset truth.

## Apply Suggestion As Correction

A future explicit user action that pre-fills the existing correction flow from a SpeciesSuggestion; truth is created only when the correction is submitted.

## Review

The user process of confirming, correcting, merging, hiding, or rejecting events.

## Correction

A user-provided truth label that improves the local dataset.

## Dataset Export

A local export of reviewed media, labels, corrections, and metadata.

## Analytics

Local summaries of outdoor activity over time.
