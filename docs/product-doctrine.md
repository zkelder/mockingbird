# MockingBird Product Doctrine

MockingBird is a local-first, hardware-agnostic nature observatory. Its
emotional purpose is to help people notice, understand, and remember wildlife
around a place.

The product starts with video streams. A user should think:

"I connect my outdoor cameras, see the streams, draw meaningful zones, review what happened, correct what MockingBird got wrong, and build useful local knowledge about my yard over time."

## Core flow

Observe → Discover → Understand → Confirm → Remember → Improve.

Sources, Streams, and Zones support this user-facing loop: observe activity,
discover evidence-backed moments, understand local patterns, explicitly confirm
truth, remember it in Bird Log and local history, then improve future review.

## Product promise

MockingBird should turn meaningful outdoor activity into useful, ranked animal
or species suggestions before asking the user to review it. Automatic
identification is a core product outcome, not a future administration feature.
A product that captures and organizes activity but never attempts useful
identification is incomplete.

The visual identification path is:

saved activity -> best frame -> animal/activity-centered crop -> ranked species
suggestions -> Review Queue -> explicit correction -> Bird Log

## Observation-engine direction

Keep the MockingBird product. Replace its observation engine through a modular
migration. Where capabilities allow, continuous observation and multi-frame
evidence are preferred over periodic snapshots: detection discovers a potential
subject, tracking proves temporal continuity, evidence capture begins
immediately, and interpretation happens after Visit assembly. This does not
weaken the evidence-versus-truth boundary; explicit correction remains truth.

Zones provide semantic, privacy, and ignore context. They are not required crop
boundaries. Detection or measured activity bounds should focus identification,
while the original frame remains available as evidence context.

Model suggestions may be wrong and remain evidence. Explicit correction remains
the only dataset-grade truth and is the basis for measuring identification
accuracy over time.

## Product objects

### Source

A camera or video input that can produce a stream or media.

Examples may eventually include RTSP/IP cameras, USB/local cameras, ESP32-CAM, HTTP snapshot sources, uploaded videos/images, folders, trail-cam imports, Frigate, Home Assistant, Blue Iris, Scrypted, MQTT, and webhooks.

Sources are adapters underneath the product.

### Stream

The user-visible video feed from a source.

Streams are central. Users should see and understand their outdoor space through streams before they care about adapter details.

### Zone

A user-drawn region on a stream.

Initial zone types:

- Feeder Zone
- Birdbath Zone
- Ground Zone
- Perch Zone
- Yard Zone
- Driveway Zone
- Privacy Zone
- Ignore Zone

Zones help MockingBird understand where activity happened and what it likely means.

### Event

A meaningful piece of outdoor activity detected from video.

Examples:

- Bird visited feeder
- Squirrel entered feeder zone
- Cat crossed yard
- Person entered driveway
- Unknown animal near birdbath
- Motion ignored in privacy or ignore zone

### Visit

A reviewable animal-centered event, especially useful for feeder and birdbath activity.

A visit can contain detections, snapshots, clips, labels, species guesses, confidence, zone information, and user corrections.

### Detection

A model or rule-generated observation inside an event.

Detections are not final truth. They are evidence for user review.

### Review label

A user-confirmed label or correction.

Examples:

- northern_cardinal
- blue_jay
- squirrel
- cat
- person
- vehicle
- false_positive
- unknown_bird
- unknown_animal

### Dataset export

A local export built from reviewed events, images, clips, labels, corrections, and metadata.

Exports are a first-class product outcome, not an afterthought.

### Analytics

Local summaries over time.

Examples:

- species observed by day
- feeder activity by hour
- zone activity
- repeat visitors
- false positives
- unknowns needing review
- dataset coverage by species

## Product boundaries

MockingBird should not be framed around:

- Windows USB setup
- PowerShell scripts
- CLI-first operation
- ROI wording
- interval-analysis language
- debug internals
- snapshot-loop architecture
- one camera adapter as the main product

Adapters are implementation details. The product is the stream, zone, event, review, correction, export, and analytics experience.

New administration, readiness, provider, diagnostic, or training surfaces must
not displace delivery of the core identification and review loop.
