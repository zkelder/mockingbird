# MockingBird Product Doctrine

MockingBird is a local-first, hardware-agnostic, bird-first but
wildlife-native nature observatory. Its purpose is to help people notice,
understand, confirm, and remember wildlife around a place.

It is not primarily:

- an NVR
- a surveillance platform
- a camera-management product
- an ML demo
- a species-classifier appliance

Streams, Zones, detectors, and classifiers exist to serve that purpose; they
are not the purpose. A user should think:

"I connect my outdoor cameras, see the streams, draw meaningful zones, review
what happened, correct what MockingBird got wrong, and build useful local
knowledge about my yard over time."

## Core flow

Observe → Discover → Understand → Confirm → Remember → Improve.

Sources, Streams, and Zones support this user-facing loop: observe activity,
discover evidence-backed moments, understand local patterns, explicitly
confirm truth, remember it in reviewed history, then improve future review
and identification.

## Detection is infrastructure

Detection, tracking, and classification exist to produce trustworthy
Observations and a growing understanding of a place. They are not the product
by themselves. Do not organize the roadmap, an implementation task, or a
design decision around maximizing detections, classifier sophistication,
camera integrations, or model novelty. Optimize instead for:

- trustworthy, useful Observations
- coherent Visits
- good evidence
- low false-event burden
- honest uncertainty
- efficient review/correction
- meaningful discoveries
- durable history
- increasing understanding of a place
- low maintenance
- local ownership and privacy

Quality is staged, not one score: capture availability, capture quality,
activity detection, animal presence, localization/tracking, Visit assembly,
evidence selection, source-resolution crop quality/lineage, broad
classification, species candidate ranking, calibration, abstention,
Observation creation, and human confirmation are each separately measurable.
Prefer fixing the weakest relevant stage over reflexively replacing a model.
Detection, tracking, and Visit-assembly stages must be highly reliable
before release; species-ranking stages only need to be useful, honest, and
abstention-capable -- perfect species identification is not a release
requirement, but reliable perception of the fact that wildlife appeared is.
See [architecture.md](architecture.md) for the current stage-by-stage account
and "Governing priority for v0.1" / Gates A-B in [roadmap.md](roadmap.md)
for the release sequencing this implies.

## Product promise

MockingBird should turn meaningful outdoor activity into useful, ranked
animal or species suggestions before asking the user to review it, and should
turn reviewed activity into durable, trustworthy Observations and growing
understanding of a place. Automatic identification is a core product
capability, not a future administration feature -- but it is a means to
trustworthy Observations, not the product outcome by itself. A product that
captures and organizes activity but never attempts useful identification is
incomplete; a product that maximizes identifications without trustworthy
review, coherent Visits, and honest uncertainty is equally incomplete.

The visual identification path is:

saved activity -> best frame -> animal/activity-centered crop -> ranked
species suggestions -> Review Queue -> explicit correction -> reviewed
history

## Observation-engine direction

Keep the MockingBird product. Replace its observation engine through a
modular migration. Where capabilities allow, continuous observation and
multi-frame evidence are preferred over periodic snapshots: detection
discovers a potential subject, tracking proves temporal continuity, evidence
capture begins immediately, and interpretation happens after Visit assembly.
This does not weaken the evidence-versus-truth boundary; explicit correction
remains truth.

"Observation Engine" names the detection/tracking runtime described in
[architecture.md](architecture.md), and "Observation Control" names its
Start/Stop UI. Both are infrastructure: they produce evidence, never truth.
They are a different thing from an "Observation" (see Product objects,
below), the durable object created only after evidence and review. Do not
let the shared word imply the engine's output is reviewed truth by itself.

Zones provide semantic, privacy, and ignore context. They are not required
crop boundaries. Detection or measured activity bounds should focus
identification, while the original frame remains available as evidence
context.

## The truth boundary

Human correction remains the truth boundary. Model proposals, classifications,
ecological priors, and language-model output must never silently become
reviewed truth. Unknown and abstained outcomes are valid: a Visit that
honestly reports "not clear enough to identify" is more useful than a
confident wrong guess. Explicit correction remains the only dataset-grade
truth and is the basis for measuring identification accuracy over time.

### Language models

Language models may eventually help with summaries, natural-language search,
explanations, configuration assistance, troubleshooting, comparison of
candidates, educational context, and daily/weekly nature-journal summaries.
Language models must not:

- create reviewed truth
- silently override identifications
- fabricate sightings
- turn ecological plausibility into local evidence
- conceal uncertainty behind fluent prose

### Models earn trust; they do not inherit it

Candidate detectors/classifiers do not gain production authority merely
because they are newer or appear better informally. See
[architecture.md](architecture.md) for the current candidate-to-retirement
model lifecycle and [roadmap.md](roadmap.md) Phase 2 for sequencing.

Reviewed truth may become valuable training data, but a reviewed Observation
does not automatically enter a training dataset. Dataset eligibility is a
separate, governed decision: provenance, crop/evidence quality, ambiguity,
duplicates/Visit leakage, uncertain labels, source lineage, user-contribution
policy, and train/validation/holdout separation all apply first. See
[custom-bird-classifier-dataset-plan.md](custom-bird-classifier-dataset-plan.md)
and [roadmap.md](roadmap.md) Phase 8.

Retain bounded, privacy-conscious diagnostic information about rejected
activity -- reason counters, policy/version identifiers, bounded
representative samples, temporary diagnostic retention, stage-of-rejection
information -- so MockingBird can measure false-negative behavior and whether
an admission policy is too permissive or too conservative. This is not
permanent storage of every rejected frame.

Reviewed truth is necessary for training and reporting eligibility but does
not by itself grant public-release rights; benchmark and public-corpus
licensing/consent remain separately governed -- see
[public-benchmark-governance.md](public-benchmark-governance.md).

## Product objects

Preserve this internal evidence/truth architecture where applicable:

Source → Stream → Zone → Activity Session → Visit → Evidence → Detection
Proposal → Interpretation → Review Decision → Observation →
Export/Analytics

Current implementation vocabulary and this target doctrine vocabulary are not
the same everywhere yet, and reconciling them is a future implementation task,
not something this doctrine update performs. The names below record the
mapping so future work moves toward one vocabulary instead of inventing a
second one.

### Source

A camera or video input that can produce a stream or media.

Examples may eventually include RTSP/IP cameras, USB/local cameras,
ESP32-CAM, HTTP snapshot sources, uploaded videos/images, folders, trail-cam
imports, Frigate, Home Assistant, Blue Iris, Scrypted, MQTT, and webhooks.

Sources are adapters underneath the product.

### Stream

The user-visible video feed from a source.

Streams are central to the experience. Users should see and understand their
outdoor space through streams before they care about adapter details. Streams
are not, by themselves, the product identity -- see "Detection is
infrastructure," above.

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

Zones help MockingBird understand where activity happened and what it likely
means. They are semantic, privacy, and ignore context, not required crop
boundaries.

### Activity Session (implemented today as Event)

A meaningful piece of outdoor activity detected from video, before it is
known whether an animal was involved or how many.

Examples:

- Bird visited feeder
- Squirrel entered feeder zone
- Cat crossed yard
- Person entered driveway
- Unknown animal near birdbath
- Motion ignored in privacy or ignore zone

### Visit

A reviewable animal-centered activity session, especially useful for feeder
and birdbath activity. A Visit can contain evidence, detections/proposals,
labels, species guesses, confidence, zone information, and user corrections.

Visits represent captured activity. Observations (below) represent what the
system believes happened, after evidence and review. Do not assume one Visit
equals one bird, that every Visit contains exactly one individual, or that
every occurrence can be accurately counted.

### Evidence

MediaAssets, MotionEvidence, evidence candidates, best-frame context, and
untrusted external metadata attached to a Visit. Evidence can be pending,
ignored, promoted, accepted, rejected, or superseded without ever becoming
truth by itself.

### Detection Proposal (implemented today as Detection / DetectionProposal)

A model- or rule-generated observation inside an Activity Session or Visit.
Detection Proposals are not final truth; they are evidence for user review,
and an honest "no confident proposal" outcome is valid.

### Interpretation (not yet implemented)

A proposed reading of what evidence means beyond raw identification --
behavior, counts, relationships between Visits. Interpretation begins as a
proposal/evidence, the same as a Detection Proposal, and remains
appropriately uncertain until reviewed. Do not introduce individual-animal
identity claims here without dedicated, defensible evidence.

### Review Decision (implemented today as ReviewLabel / correction)

A user-confirmed label, correction, or explicit abstention. Examples:

- northern_cardinal
- blue_jay
- squirrel
- cat
- person
- vehicle
- false_positive
- unknown_bird
- unknown_animal

A Review Decision is the only dataset-grade truth write in the system.

### Observation (target durable object)

Not yet a distinct implementation object; today's closest equivalent is a
reviewed Visit / Bird Log entry. The durable semantic product object: what
MockingBird believes happened, after evidence and review. Observation should
increasingly be treated as the durable semantic product object that history,
Place Intelligence, and exports are built from -- more than the Visit it was
assembled from. See "Observation-engine direction," above, for the naming
collision with "Observation Engine"/"Observation Control": those name
infrastructure that produces evidence, never an Observation by themselves.

### Dataset export / Analytics

A local export or summary built from reviewed Visits/Observations, evidence,
labels, corrections, and metadata. Exports and analytics are a first-class
product outcome, not an afterthought, and they derive only from Review
Decisions -- never from raw proposal or Interpretation output.

## Wildlife-native semantics

Birds remain the first-class initial domain. The semantic model must
naturally support broader wildlife -- mammals, insects -- without a rewrite.
Do not assume:

- one Visit equals one bird
- every animal can be species-identified
- every Visit contains one individual
- every occurrence can be accurately counted
- behavioral interpretation is automatically truth

Behavioral interpretations begin as proposals/evidence (see Interpretation,
above) and remain appropriately uncertain. Do not introduce individual-animal
recognition claims without dedicated, defensible evidence.

## External ecological context

Taxonomy, range, migration/seasonality, nearby public observations, weather,
and sunrise/sunset may enrich ranking, explanations, discovery, and
education. External context must retain provenance and must never become
evidence that an animal actually appeared at the user's site. Shape future
abstractions so an external source can be governed by source, licensing,
temporal/geographic resolution, freshness, retention, and whether it
influences ranking or only presentation. Do not prematurely build a large
integration platform for this.

## Place Intelligence

Accumulated understanding of a site is a first-class future product layer:
first/last observed, regular and new visitors, Zone preferences,
time-of-day/seasonal patterns, changes from baseline, unusual activity
changes, and year-over-year comparisons, once history is adequate to support
them. Analytics should answer natural questions about the place, not merely
surface internal database metrics. See [roadmap.md](roadmap.md) Phase 5.

## Calm-observatory notifications

MockingBird does not inherit motion-alert culture from security cameras.
Prefer meaningful discoveries, new species, exceptional moments, calm
daily/weekly digests, health/storage alerts, and review requests when useful.
Per-Visit alerts may exist later as an option, never as the product center.

## Product profiles

One core architecture, different capability profiles:

- **Personal/Home** (primary): single site, straightforward setup, local
  ownership, Today in Your Yard, review/history, useful analytics, optional
  remote access.
- **Advanced/Enthusiast** (secondary): custom cameras, advanced storage, GPU
  inference, diagnostics, model/configuration choices, richer exports.
- **Research/Contributor** (future): provenance-rich exports, dataset
  workflows, evaluation/contribution capabilities.
- **Managed/commercial/fleet** (possible future, not now): do not build
  enterprise/fleet administration prematurely.

Advanced flexibility must not burden ordinary-user setup.

## Installation and appliance experience are product features

Today's development checkout -- WSL, a repository clone, a Python
virtualenv, `npm ci`, manual migrations, Pi SSH, routine shell
administration -- is development mechanics, not the product. A mature
MockingBird deployment does not require any of it. Phase 27A already
delivers a self-contained "unpack and run" Windows bundle for normal use (see
[local-product-packaging-design.md](local-product-packaging-design.md) and
[using-mockingbird.md](using-mockingbird.md)); making normal service
lifecycle, upgrades, recovery, migrations, health, detector setup, and
storage management product-managed rather than developer-operated is
[roadmap.md](roadmap.md) Phase 4. The golden path is: install → open → add
camera → preview → optionally configure Zones → confirm storage → observe.

## Capability-aware UX

Provider abstractions stay hardware-agnostic underneath, but the UI must
report actual hardware capabilities honestly -- source resolution, still
capture, live/video capability, frame rate, exposure controls, a
high-resolution evidence path, hardware timestamps, and optional controls
such as PTZ/audio where relevant. Unsupported features are hidden or plainly
explained rather than shown as if they might work. MockingBird already does
this narrowly (a Stream with no integrated observation runtime says so
honestly instead of showing a Start button that would only fail); extending
the same honesty to resolution/exposure/timestamp facts is future work, not a
new principle.

## Source-resolution evidence contract

Formalize the distinction between source media, inference derivatives, crops,
and display derivatives. For important evidence, lineage should make it
possible to trace: original source resolution → selected source frame →
source-coordinate crop → crop dimensions → any subsequent transform/resize.
Users and diagnostics should be able to tell whether a crop actually came
from the highest-resolution available source rather than trusting an
ambiguous label. Reviewed-replay source lineage
([reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md))
and best-frame media attachment
([best-frame-media-attachment-design.md](best-frame-media-attachment-design.md))
already carry part of this chain; treat it as one contract going forward
rather than growing a new per-feature lineage field each time.

## Mobile is an access surface

Future mobile work exposes the same authoritative local Observation/history
model: Today in Your Yard, highlights, review, history, camera health,
notifications, optional remote access. Do not introduce separate mobile truth
semantics or require cloud operation merely to support mobile.

## Privacy and portability

Local ownership stays central. Over time, a user should be able to tell where
media lives, what leaves the device, retention, model/external calls,
remote-access behavior, contribution status, and backup behavior. Long-lived
reviewed history should be portable and recoverable across camera changes,
model changes, and future service changes.

## Two scorecards

Distinguish engineering truth from user value; do not optimize one while
ignoring the other.

Engineering truth: camera uptime, capture success, restart recovery, resource
stability, storage integrity, pipeline latency, evidence lineage, Visit
fragmentation/merge errors, admission precision/recall, selective-
classification accuracy, calibration.

User value: useful Visits/Observations, percentage of review items worth
seeing, review burden, useful best moments, meaningful discoveries, days with
worthwhile history, trusted/reviewed history coverage, ongoing maintenance
burden.

Over time, also measure whether an algorithmic component -- a detector
assist, a tracker, an extra frame, an expensive classifier -- actually
improves outcomes relative to its cost (false positives/negatives, compute,
latency, storage, review burden, failure rate, coverage). Avoid accumulating
algorithmic complexity that does not earn its place.

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
- NVR/security-platform framing, continuous-recording as the product focus,
  or security alerts/person recognition

Adapters are implementation details. The product is the Stream, Zone,
Activity Session, Visit, evidence, review, correction, Observation, export,
and analytics experience.

New administration, readiness, provider, diagnostic, or training surfaces
must not displace delivery of the core Observation and review loop. See
[roadmap.md](roadmap.md) for the current phase gates and the full explicit
deprioritization list.
