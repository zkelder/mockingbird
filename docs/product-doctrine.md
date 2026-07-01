# MockingBird Product Doctrine

MockingBird is a local-first outdoor video intelligence platform.

The product starts with video streams. A user should think:

"I connect my outdoor cameras, see the streams, draw meaningful zones, review what happened, correct what MockingBird got wrong, and build useful local knowledge about my yard over time."

## Core flow

Connect source → view stream → draw zones → analyze outdoor activity → review visits/events → correct labels/species → export datasets and analytics.

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
