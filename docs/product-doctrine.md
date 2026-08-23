# MockingBird Product Doctrine

MockingBird is a local-first, hardware-agnostic, evidence-backed ecosystem
observatory for understanding how a Place changes over time -- across
wildlife, acoustics, plants and habitat, environmental measurements,
external ecological context, and human knowledge. Its purpose is to help
people notice, understand, and remember the living environment around a
place.

MockingBird is, and remains:

- wildlife-first in its existing maturity -- most of what is built today is
  wildlife observation, and that stays the strongest, most proven part of
  the product;
- bird-first historically, increasingly biodiversity-native -- the
  semantic model was built for birds but must generalize, not be rebuilt,
  as it covers more of the living world (see "Wildlife-native semantics,"
  below);
- local-first and evidence-first;
- privacy-conscious;
- hardware-agnostic;
- discovery-oriented, not surveillance;
- capable of scaling from home use to serious research/organizational
  field monitoring on the same architecture (see "Deployment and
  organization doctrine" and "Professional and research positioning,"
  below) -- not a separate product per audience.

It is not primarily:

- an NVR, or an NVR clone
- a surveillance platform
- a camera-management product
- an ML demo
- a species-classifier appliance

Streams, Zones, detectors, and classifiers exist to serve that purpose; they
are not the purpose. A user should think:

"I connect my cameras and sensors, see what's happening, review what
happened, correct what MockingBird got wrong, and build useful local
knowledge about my place over time."

## Core flow

Observe → Discover → Understand → Confirm → Remember → Improve.

Sources, Streams, and optional Zones support this user-facing loop: observe
activity, discover evidence-backed moments, understand local patterns,
explicitly confirm truth, remember it in reviewed history, then improve
future review and identification. This loop is domain-agnostic -- it
applies the same way to a bird, a flowering shrub, or a rainfall reading.
Confirm is what makes something durable Reviewed history; it is not a gate
that Measured or Inferred information must pass before it is useful (see
"Measured, Inferred, and Reviewed," below).

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
and "Governing priority before release" / Gates A-B in
[roadmap.md](roadmap.md) for the release sequencing this implies.

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

### Measured, Inferred, and Reviewed

One inference contract applies across every current and future domain --
wildlife, plant identification, phenology, habitat condition/change,
agriculture/land-management signals, and future model providers.
MockingBird distinguishes three tiers of knowledge about the world and must
never blur them into one undifferentiated "the system says":

**Measured.** Direct sensor or algorithmic measurement, with provenance,
quality, calibration, and uncertainty where appropriate. Examples:
temperature, soil moisture, a vegetation-coverage estimate, rainfall, water
level. A measurement can be wrong -- a miscalibrated sensor, a bad read --
but it is not a guess about identity or meaning.

**Inferred.** Model-derived, informed intelligence: likely Northern
Cardinal, likely Eastern Redbud, possible flowering onset, apparent
vegetation stress, multimodal evidence agreement. Inferred intelligence
must be useful immediately in ordinary product surfaces. MockingBird must
not require a human to confirm a model output before showing it as useful
information -- see "Product promise," below, already applying exactly this
to species suggestions ("turn meaningful outdoor activity into useful,
ranked animal or species suggestions before asking the user to review
it"). The UX vocabulary for Inferred output is: Likely, Possible, Unclear,
Evidence agrees, Evidence differs, alternatives, confidence/calibration,
provenance, and abstention -- used where they honestly apply, not as
decoration on every surface.

**Reviewed.** Human-validated semantic truth -- what "Human correction
remains the truth boundary," above, is about. Reviewed truth remains
authoritative for: durable confirmed history; research-grade/export-eligible
records where required; training-data eligibility; benchmark truth;
consequential downstream claims; and corrections. Later model inference --
a stronger model, a newer version, a re-run -- must never silently
overwrite Reviewed truth; it may only propose.

This generalizes the species-identification truth boundary that already
governs the rest of this document, so a future habitat, phenology, or
environmental-sensor capability inherits one contract instead of
re-deriving a second one.

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
and [roadmap.md](roadmap.md) "Remaining product maturity" (Layer 8 of
"Remaining roadmap -- canonical sequence," which now covers this; see the
historical Phase 8 entry there for how it was folded in).

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

An optional, user-drawn 2D region in one Stream's image space -- not a
required part of using MockingBird, and not the product's semantic center.
See "Spatial doctrine," below, for the full demotion and the preferred
spatial hierarchy this fits into.

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
boundaries, not physical geometry, and not proof that two cameras share a
physical area.

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

## Spatial doctrine

Zones are not MockingBird's semantic center, and must not be treated as
one. A Zone is an optional, user-drawn 2D region in one Stream's image
space, useful for: privacy masks, confusor exclusion, human-readable
fixed-view labels, simple filtering, and bounded repeat-measurement ROIs
(for example, a scheduled habitat-sampling region). Zones are **not**:

- the semantic center of MockingBird;
- physical 3D habitat geometry;
- proof that two cameras observe the same physical area;
- durable geography after a camera moves;
- a sufficient basis for distance or real-world-overlap claims.

The preferred spatial hierarchy, from most to least certain:

Place → Source → camera/view/pose → optional image-space ROI → optional
calibrated real-world geometry when actually known.

A Place is the durable, real-world thing being observed over time. A
Source is a camera or sensor input. Camera/view/pose identity distinguishes
one physical vantage point from another, including after a camera is moved
or repositioned. An image-space ROI (a Zone, or a future habitat-sampling
region) is a convenience layered on top of one view, not a claim about the
physical world. Calibrated real-world geometry -- actual measured
distance, surveyed/GPS position, or verified multi-camera overlap -- is a
stronger claim that must be earned with real calibration evidence, never
assumed from Zone or Area-name proximity alone. See, for a real precedent
of getting this right, the Area-name-only overlap signal in
[camera-source-multi-camera-maturity-v1-contract.md](camera-source-multi-camera-maturity-v1-contract.md),
which deliberately does not use field-of-view geometry as a spatial signal.

For moving, PTZ, or repositioned cameras: preserve pose/view identity where
possible; re-baseline longitudinal comparisons after a meaningful view
change rather than silently comparing incomparable frames; abstain from
spatial or longitudinal claims when image comparability is unknown -- the
same abstention discipline that already governs species identification
(see "Measured, Inferred, and Reviewed," above).

Do not force Habitat or Phenology architecture through Zones. A scheduled
habitat-sampling view (see [roadmap.md](roadmap.md) "Habitat & Phenology
Foundation") needs stable view/pose identity and comparability status --
concepts Zones were never designed to carry -- not a Zone reused past its
purpose.

## Wildlife-native semantics

Birds remain the first-class initial domain, and wildlife remains this
product's most mature domain in practice. The semantic model must naturally
support broader wildlife -- mammals, insects -- without a rewrite, and the
same object model (Source → Stream → optional Zone/ROI → Activity Session
→ Visit/Observation → Review Decision) must extend to plants/habitat and
environmental measurement as first-class domains over time (see
[roadmap.md](roadmap.md) "Habitat & Phenology Foundation" and "Biodiversity
& Place Intelligence") rather than forking a second architecture per
domain. Do not assume:

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

Accumulated understanding of a Place is a first-class product layer,
substantially begun: first/last observed, regular and new visitors,
Zone/time preferences, changes from baseline, unusual activity changes, and
year-over-year comparisons, once history is adequate to support them.
Analytics should answer natural questions about the place, not merely
surface internal database metrics. Place Intelligence combines the accepted
wildlife/acoustic system with habitat and environmental context, not only
wildlife counts, as those domains come online -- see
[roadmap.md](roadmap.md) "Biodiversity & Place Intelligence."

## Calm-observatory notifications

MockingBird does not inherit motion-alert culture from security cameras.
Prefer meaningful discoveries, new species, exceptional moments, calm
daily/weekly digests, health/storage alerts, and review requests when useful.
Per-Visit alerts may exist later as an option, never as the product center.

## Deployment and organization doctrine

One authoritative local MockingBird Host per deployment/observatory, many
Camera Nodes (and other Sources/sensors), many human clients. The Host
owns: the authoritative database/history, evidence, inference/runtime
services, Camera Node/Source relationships, storage/recovery, and user
permissions. Human users access the Host through browsers, and later
PWA/mobile clients (see "Mobile is an access surface," below) -- never a
second, separate MockingBird installation or database per workstation. See
[roadmap.md](roadmap.md) "Local Identity, Multi-User & Organization Access"
for the sequencing this implies.

Camera Nodes authenticate to the Host as devices. Humans authenticate to
the Host as users. Device credentials and human credentials are, and
remain, separate systems -- a Camera Node pairing secret is never a
substitute for, or equivalent to, a human login, and vice versa.

### Deployment profiles

One core architecture, same codebase, two primary supported profiles:

- **Personal/Home** (primary): appliance-style/guided local install,
  infrastructure mostly hidden, local hostname/discovery, browser/PWA use,
  Today in Your Yard, review/history, useful analytics, optional remote
  access. Advanced capability -- custom cameras, advanced storage, GPU
  inference, diagnostics, model/configuration choices, richer exports --
  lives inside this profile as optional depth, not a separate deployment
  architecture. Advanced flexibility must not burden ordinary-user setup.
- **Organization/Research** (earned, not primary): local server deployment
  (OCI/Docker Compose, a VM, or a supported Linux service), persistent
  storage, local DNS/TLS/reverse proxy, backup/recovery, and multiple
  users/workstations against the one authoritative Host -- provenance-rich
  exports, dataset workflows, and evaluation/contribution capabilities.

Do not introduce Kubernetes, high-availability clustering, or SaaS
multi-tenancy as early requirements. "Organization," initially, means
installation metadata and a policy boundary (who may do what on this one
Host) -- not cloud tenancy. Multi-user (several people using one Host) and
Multi-site (several physically separate Places) remain separate concepts;
do not conflate them, and do not build Multi-Site ahead of real near-term
need (see "Multi-site readiness" in
[camera-source-multi-camera-maturity-v1-contract.md](camera-source-multi-camera-maturity-v1-contract.md)
for the one deliberately-deferred structural note that already exists).

A **Managed/commercial/fleet** profile (centrally administering many
independent Hosts) remains a possible, distant future, not a current
target -- do not build enterprise/fleet administration prematurely.

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

## Professional and research positioning

Professional biodiversity monitoring and field research are part of
MockingBird's intended mature use, not a separate derivative product. The
same authoritative Observation/evidence semantics -- Measured, Inferred,
Reviewed; local-first; evidence-first -- scale from backyard/home, to
enthusiast, to conservation, restoration, university/research, and
organizational field monitoring (see "Deployment and organization
doctrine," above). There is no separate "MockingBird Pro" truth model.
Likewise, land management and agriculture (see [roadmap.md](roadmap.md)
"Land Management / Agriculture") are an application of the same Place
Intelligence, not a separate product architecture.

## Hunting and other future derivatives

MockingBird's local field-observation architecture -- Host, Camera Nodes,
evidence, review, Place Intelligence -- may, later, support other
decision-support products outside nature observation, such as
hunting/scouting. This is not a current or near-term product goal, and
should not grow into major derivative-product development on the active
roadmap. Do not generalize or extract a platform prematurely; MockingBird
should prove the ecosystem-observatory architecture first, on its own
terms, before any derivative is seriously considered.

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
- Zones as the semantic center, as 3D habitat geometry, or as proof that
  two cameras share a physical area (see "Spatial doctrine," above)
- a separate MockingBird installation or database per workstation (see
  "Deployment and organization doctrine," above)
- agriculture as a separate product, or professional biodiversity/field
  research as a separate derivative (see "Professional and research
  positioning," above)
- requiring human confirmation before Inferred, model-derived intelligence
  may be shown as useful information (see "Measured, Inferred, and
  Reviewed," above)

Adapters are implementation details. The product is the Stream, Zone,
Activity Session, Visit, evidence, review, correction, Observation, export,
and analytics experience.

New administration, readiness, provider, diagnostic, or training surfaces
must not displace delivery of the core Observation and review loop. See
[roadmap.md](roadmap.md) for the current release gates and the full
explicit deprioritization list.
