# Ecosystem / Provider Integrations Release-Scope Decision v1

Pre-release product-scope decision for Lane K ("Ecosystem / Provider
Integrations"). This is documentation/reconciliation work, not an
integration implementation campaign: zero production code changed, no
adapter or plugin framework was built, and no provider credential/network
surface was added. This report records the decision, the evidence behind
it, and the concrete bar for reopening it later.

## Starting state

Verified before any edit:

- Repository: `/home/zkelder/projects/mockingbird-active`, branch `main`.
- Starting HEAD: `8764a05` (the reconciliation commit accepting Camera /
  Source Release Hardware Validation Closure v1). `docs/
  release-execution-state.md`'s own established convention names the
  *report* commit, `e79420e`, as "Accepted HEAD" -- `8764a05` is the
  reconciliation commit that recorded it, one commit later, consistent
  with the pattern already confirmed across multiple prior cycles.
- Schema: v58 (unchanged since the accepted HEAD).
- Latest accepted milestone: Camera / Source Release Hardware Validation
  Closure v1 (classification B).
- Lane G status: `MATERIALLY CLOSED / VALIDATION REMAINS -- RELEASE-CRITICAL`.
- Lane K status: `OPEN DECISION` -- "Candidates previously discussed:
  Frigate; Blue Iris; Scrypted; Home Assistant. Do not implement all.
  Decide whether a minimum useful adapter set materially improves
  first-release adoption. Native Camera Node + standards-based
  acquisition remain the golden path" (`docs/release-execution-state.md`
  §6.K).
- Current authorization: `NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED` (§3).
- Not pushed: `main` is 314 commits ahead of `origin/main`; confirmed via
  `git log origin/main..HEAD` before any local change.

All of this matched the milestone brief's expected starting state exactly;
no discrepancy, so no STOP was triggered.

**Worktree safety.** `git status` showed exactly the seven untracked files
the brief names as preserved-untouched (`docs/
wildlife-detector-training-contract.md.orig`, `scripts/
evaluate_small_bird_detector.py`, `scripts/
materialize_wildlife_stage2.py.orig`, `scripts/
train_wildlife_stage2_rfdetr.py.orig`, `src/mockingbird/detectors/
small_bird_benchmark.py`, `src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`) and nothing else; all seven share one
identical timestamp (`2026-08-31 18:57:23`), consistent with an earlier
session's single batch and not touched since. No `.git/index.lock` or any
other `.git/*.lock` file exists, and no `pytest`/`vite`/`npm run`/`uv run`
process was found running against this checkout -- no active writer shares
this worktree. These seven files were not read, moved, or modified by this
milestone.

## Governing product doctrine

Read in the required order (`docs/release-execution-state.md`, `docs/
product-doctrine.md`, `docs/roadmap.md`) before any provider-specific
evidence. The doctrine already settles most of this decision by itself:

- **Identity.** "It is not primarily: an NVR, or an NVR clone; a
  surveillance platform; a camera-management product" (product-doctrine.md
  "Product outcome"). "Product boundaries" repeats this concretely:
  MockingBird should not be framed around "NVR/security-platform framing,
  continuous-recording as the product focus, or security alerts/person
  recognition."
- **Adapters are implementation details, not the product.** "Detection is
  infrastructure" is explicit that the roadmap must not be organized
  "around maximizing detections, classifier sophistication, camera
  integrations, or model novelty." "Adapters are implementation details.
  The product is the Stream, Zone, Activity Session, Visit, evidence,
  review, correction, Observation, export, and analytics experience."
- **The four named candidates are already anticipated, not novel.**
  product-doctrine.md's own "Source" definition already lists examples:
  "RTSP/IP cameras, USB/local cameras, ESP32-CAM, HTTP snapshot sources,
  uploaded videos/images, folders, trail-cam imports, **Frigate, Home
  Assistant, Blue Iris, Scrypted**, MQTT, and webhooks," immediately
  followed by "Sources are adapters underneath the product." Doctrine
  already treats all four as *possible* future adapters, never as
  required ones, and always subordinate to Stream/Zone/Visit/Review/
  Observation identity.
- **Explicit deprioritization** (roadmap.md) already names, verbatim:
  "NVR/security-platform expansion," "broad camera integration counts as a
  goal," "plugin-framework construction," "model marketplaces," "broad
  smart-home automation."
- **Explicit phase gates** (roadmap.md) already state: "Do not broaden
  hardware integrations merely for coverage until at least one golden path
  is excellent" and "Do not prioritize NVR/live-video capability over
  useful history, review, evidence, and place understanding."
- **Release non-blockers** (roadmap.md) already lists "every possible
  camera provider" as explicitly not a release blocker absent new
  empirical evidence.
- **Governing priority before release** (roadmap.md): detection/encounter/
  Visit correctness (Gate A) and useful species assistance (Gate B) carry
  release weight; provider/integration breadth does not.

This milestone's job is therefore to apply already-settled doctrine to
Lane K's specific open question, not to invent new doctrine.

## Existing acquisition architecture

Traced directly from real, currently-merged code and design docs (not
re-derived from memory), confirming launch users already have reasonable
non-proprietary acquisition options across every category the brief
requires:

- **Native Camera Node (golden path).** `src/mockingbird_node/` --
  install/service/systemd hardening, `boot_id`/self-test/watchdog, RTT
  clock calibration, pairing, reprovision/replacement recovery. Proven
  live, repeatedly, most recently against the real reference Pi in Camera
  / Source Release Hardware Validation Closure v1 (2026-09-02): health,
  both compatibility-preflight profiles, an honest pairing-conflict
  rejection, and a clean bounded restart-recovery cycle.
- **ONVIF.** `mockingbird.source_providers.onvif_client` -- discover,
  authenticate, enumerate media profiles, resolve a stream URI. Per
  `docs/onvif-provider-boundary-design.md`'s own "Architecture invariant:
  converge immediately, never fork," a resolved ONVIF profile is persisted
  as an ordinary `provider_key="external_url"`, `live_stream_type="rtsp"`
  Source -- "from here, indistinguishable from a manually-entered RTSP
  camera: same `rtsp_bridge`, same Doctor check, same Observation Engine
  eligibility, same RTSPS honesty." ONVIF is a discovery/configuration
  assistant on top of one playback pipeline, never a second one -- the
  exact discipline §9's architecture rule (below) asks any future
  ecosystem adapter to follow too.
- **RTSP / RTSPS.** A real, working ffmpeg-based RTSP-to-browser bridge
  (`mockingbird.playback.rtsp_bridge`) predates ONVIF (Phases 19-22).
  RTSPS is explicitly, honestly refused rather than silently faked:
  `rtsp_bridge.RTSPS_TRANSPORT_SUPPORTED = False`, with its own error
  taxonomy and regression test (`docs/onvif-provider-boundary-design.md`
  "RTSPS: explicitly not faked").
  Manual RTSP setup's "Auth username"/"Auth password" fields were fixed to
  actually merge into the live connection URL (previously silently
  discarded) by Camera / Source Experience & First-Hour Setup Closure v1.
- **Local USB / platform camera.** `SourceProviderKind.local_camera`
  (`src/mockingbird/api/schemas.py`) covers both platforms: V4L2 on
  Linux/Pi (`mockingbird_node.providers.V4L2CameraProvider`, its own
  diagnostic-truth defect -- counting non-capture device nodes as
  cameras -- found and fixed live this same prior milestone) and Windows
  DirectShow (`ffmpeg -f dshow -list_devices`, with real live
  enumeration-honesty evidence). Both gained the same bounded setup
  preview and ongoing-monitoring failure-code diagnostics as RTSP/ONVIF
  (Ongoing Monitoring Failure Diagnostics for RTSP / Local USB / Windows
  DShow v1, 2026-08-30).
- **Offline / recorded ingest and camera-trap ingest.**
  `SourceProviderKind.local_folder` (`provider_key="folder_import_future"`)
  -- explicit folder preview, EXIF/content-hash/video-duration provenance,
  explicit MediaAsset import, explicit MotionEvidence handoff. Per `docs/
  next-provider-boundary-decision.md`'s own 2026-08-22 status update, this
  is where offline/camera-trap import provenance actually shipped.
- **Provider-neutral Source/Stream architecture.** Every provider above --
  plus `demo`, `manual_upload`, and `webhook` -- shares one
  `SourceProviderKind` enum and terminates into the identical Source ->
  Stream -> Zone -> Activity Session -> Visit -> Evidence -> Detection
  Proposal -> Review Decision -> Observation spine (product-doctrine.md
  "Product objects"). `SourceProviderKind.integration` specifically labels
  the *native* paired Camera Node's own Source kind
  (`diagnostics/doctor.py:_CAMERA_NODE_SOURCE_KIND = "integration"`) --
  it is not a third-party plugin slot, and no plugin/adapter marketplace
  exists.
- **A general external-event ingress already exists, vendor-neutral.**
  `POST /api/sources/{source_id}/webhook/validate` and `.../webhook/
  motion-evidence` (`src/mockingbird/api/main.py`,
  `source_providers/webhook_validation.py`) implement the generic webhook
  boundary `docs/generic-webhook-provider-boundary-design.md` designed.
  Its own "Relationship To Home Assistant / Frigate / Blue Iris /
  Scrypted" section states the governing intent directly: "Generic webhook
  should come first. Ecosystem-specific adapters can later wrap or format
  payloads into the generic webhook boundary... Core MockingBird should
  not be coupled to one ecosystem first." This means a user who already
  runs Frigate, Home Assistant, Blue Iris, or Scrypted can, today, point
  that system's own outbound automation at MockingBird's existing webhook
  endpoint without MockingBird building or maintaining a single line of
  vendor-specific adapter code -- landing strictly as evidence
  (MotionEvidence), never as reviewed truth.

`docs/release-execution-state.md` §5 independently confirms this same
inventory as "substantial accepted work" under "Camera / Acquisition
Foundations": "native Camera Node path; ONVIF; RTSP/RTSPS; offline/
recorded ingest; camera-trap ingest; provider-neutral Source/Stream
architecture." Lane G (first-hour camera/source experience) is
release-critical and currently `MATERIALLY CLOSED / VALIDATION REMAINS`
-- its own remaining gap is *live-hardware validation* of paths that
already exist (a usable Camera Node pairing credential, a reachable RTSP/
ONVIF/USB endpoint), not missing capability, and not something any of the
four candidate ecosystem adapters would close -- none of them was
reachable or credentialed in that session either, and none is a substitute
for validating MockingBird's own already-built acquisition paths.

## Frigate assessment

Frigate is an open-source NVR with its own built-in object detection,
RTSP restream, and an MQTT event bus; it commonly sits in front of
ordinary RTSP/ONVIF IP cameras.

- **Likely integration value:** Medium. Real value only for a user who
  already runs Frigate as their NVR and wants its own already-computed
  detections/clips surfaced in MockingBird without MockingBird re-running
  its own detector.
- **Capability MockingBird fundamentally lacks:** No. A camera behind
  Frigate is still an ordinary RTSP/ONVIF camera, already reachable
  directly through MockingBird's existing RTSP/ONVIF path -- Frigate is
  not required to acquire the video. MockingBird's own wildlife-tuned
  detector/tracker/Visit-assembly pipeline is also a different quality bar
  than Frigate's general security-object detection (person/car-class,
  not species-aware).
- **Does standards-based acquisition already cover the core camera path:**
  Yes.
- **Surveillance/NVR-oriented product pressure:** Yes -- Frigate is
  explicitly an NVR product; deep coupling pulls product framing toward
  "continuous recording / security event," exactly what product-doctrine.md
  rejects.
- **New credential/network/security surface:** Yes -- Frigate API/MQTT
  broker credentials, and a new event-trust boundary for detections that
  would otherwise look authoritative.
- **Release decision:** DEFERRED -- NOT REQUIRED FOR LAUNCH.

## Blue Iris assessment

Blue Iris is a proprietary, paid, Windows-only NVR with a closed HTTP/JSON
API, also offering its own motion/AI add-ons.

- **Likely integration value:** Low-to-medium -- a real but narrower,
  Windows-tied hobbyist-security user base, less aligned with MockingBird's
  ecosystem-observatory audience than Frigate's open-source community.
- **Capability MockingBird fundamentally lacks:** No -- identical
  reasoning to Frigate; cameras behind Blue Iris are ordinary RTSP/ONVIF/
  USB devices already reachable directly.
- **Does standards-based acquisition already cover the core camera path:**
  Yes.
- **Surveillance/NVR-oriented product pressure:** Yes, and arguably
  stronger -- Blue Iris is explicitly branded as a security DVR product.
- **New credential/network/security surface:** Yes -- a closed, unversioned
  proprietary API MockingBird would need to reverse-engineer and maintain
  against silent upstream changes, plus Windows-only coupling.
- **Release decision:** DEFERRED -- NOT REQUIRED FOR LAUNCH.

## Scrypted assessment

Scrypted is an open-source home-video orchestration platform and plugin
host, bridging cameras/NVRs into HomeKit, Google Home, and Alexa.

- **Likely integration value:** Medium -- mainly as a bridge to *other*
  ecosystems (HomeKit/Google), not as a camera-acquisition source in its
  own right. The natural integration shape would be a MockingBird plugin
  living *inside* Scrypted's own plugin framework -- exactly the kind of
  "plugin-framework construction" / "model marketplace" participation
  roadmap.md's "Explicit deprioritization" already advises against joining
  prematurely.
- **Capability MockingBird fundamentally lacks:** No -- a camera behind
  Scrypted is still an RTSP/ONVIF/USB camera underneath.
- **Does standards-based acquisition already cover the core camera path:**
  Yes.
- **Surveillance/NVR-oriented product pressure:** Medium -- Scrypted itself
  is more automation/bridging-oriented than continuous-recording-oriented,
  but its plugin-marketplace shape still risks the "camera integrations as
  a goal" framing "Detection is infrastructure" rejects.
- **New credential/network/security surface:** Yes -- Scrypted's own
  plugin API/auth, plus whatever bridged ecosystem's (HomeKit/Google)
  credential model that would entail.
- **Release decision:** DEFERRED -- NOT REQUIRED FOR LAUNCH.

## Home Assistant assessment

Home Assistant (HA) is a large open-source smart-home automation hub with
a broad integration ecosystem, MQTT support, and its own entity/state
model.

- **Likely integration value:** Medium-to-high of the four, but mostly on
  the *notification/automation* side (e.g., surfacing a MockingBird
  Observation as an HA automation trigger) rather than camera acquisition
  -- HA is generally a consumer of MockingBird's events, not a supplier of
  camera video MockingBird lacks.
- **Capability MockingBird fundamentally lacks:** No, for acquisition.
  The closest thing to a real gap is automation/distribution *reach*
  (pushing an Observation into a user's existing automation hub), which is
  a notification/egress capability, not an acquisition capability, and is
  outside Lane K's acquisition-focused scope. Product-doctrine.md's own
  "Calm-observatory notifications" section already governs notification
  scope narrowly (no motion-alert culture), and roadmap.md's "Explicit
  deprioritization" names "broad smart-home automation" directly.
- **Does standards-based acquisition already cover the core camera path:**
  Yes -- cameras HA manages are the same RTSP/ONVIF/USB devices already
  supported directly.
- **Surveillance/NVR-oriented product pressure:** Low-to-medium -- HA
  itself is not surveillance-branded, but deep integration invites
  automation/alerting feature pressure off product-identity center.
- **New credential/network/security surface:** Yes -- HA's own long-lived
  API tokens and MQTT broker, plus a new outbound-push surface distinct
  from the local-first, foreground-only notification posture Calm
  Attention & Notifications v1 already deliberately chose (no Web Push, no
  MockingBird-operated cloud notification backend).
- **Release decision:** DEFERRED -- NOT REQUIRED FOR LAUNCH.

## Security / privacy implications

Common to all four candidates: each would add a new class of
externally-issued credential (API key/token, MQTT broker auth, or a
Scrypted/HA session) that MockingBird would need to store, redact from
logs/UI, validate, and maintain against upstream API drift the adapter's
vendor owes MockingBird no compatibility guarantee for. Product-doctrine.md's
"Deployment and organization doctrine" already establishes that device
credentials and human credentials are, and remain, separate systems; a
third credential class (an ecosystem adapter's own API/broker credential)
would need to extend that same discipline rather than create an
inconsistent fourth pattern alongside the Camera Node pairing secret and
the RTSP/ONVIF credential-redaction already proven in this codebase.

Each candidate also raises an *event-trust* question the existing
standards-based paths do not raise the same way: an RTSP/ONVIF/local
camera supplies raw video that MockingBird's own detector/tracker
independently interprets, whereas Frigate/Blue Iris/Scrypted/Home
Assistant would each supply their *own* already-interpreted
detections/events -- which, if ever wired in, must land as evidence
(MotionEvidence / Detection Proposals) only, never as Review Decisions or
Observations, exactly as the one general external-event path that already
exists (the generic webhook boundary) already requires: "no unbounded
ingest without lifecycle design," provenance retained, and imported
labels/objects/events never treated as reviewed truth
(`generic-webhook-provider-boundary-design.md`). No future dedicated
adapter should be permitted to shortcut that boundary the way an
"authoritative imported detection" feed might otherwise tempt one to.

## Product-identity implications

product-doctrine.md is explicit and repeated that MockingBird "is not
primarily... an NVR, or an NVR clone... a surveillance platform... a
camera-management product," and that it "should not be framed around...
NVR/security-platform framing, continuous-recording as the product focus,
or security alerts/person recognition." All four candidates are, to
varying degrees, NVR/security/home-automation products first. Building a
dedicated, named adapter for any of them before real demand exists risks:

- perception drift toward "security-camera hub with wildlife extras"
  instead of "ecosystem observatory";
- roadmap attention pulled toward integration-count/compatibility-matrix
  work instead of the Gate A/B correctness work roadmap.md's "Governing
  priority before release" designates as release-critical;
- a plugin-framework or marketplace shape (most concretely via Scrypted)
  that "Explicit deprioritization" already names as something not to
  build.

None of this forecloses a future adapter. product-doctrine.md's own
"Source" definition already lists all four as legitimate *possible* future
adapters "underneath" the product -- doctrine already anticipated them as
possible, never as required, and always subordinate to the Stream/Zone/
Visit/Review/Observation product identity this milestone's architecture
contract (below) locks in.

## Release decision

**No dedicated ecosystem/provider adapter (Frigate, Blue Iris, Scrypted,
Home Assistant, a generic NVR adapter, or a plugin framework) is required
for the one public MockingBird launch.**

Launch acquisition posture is, and remains:

- native Camera Node as the golden path;
- standards-based acquisition as the general path -- ONVIF, RTSP/RTSPS,
  supported local USB/platform camera paths, offline/recorded ingest, and
  camera-trap ingest.

All of this is already substantially built and accepted (see "Existing
acquisition architecture," above; `docs/release-execution-state.md` §5
"Camera / Acquisition Foundations"; Lane G `MATERIALLY CLOSED / VALIDATION
REMAINS -- RELEASE-CRITICAL`, whose one remaining gap is real-hardware
validation, not new capability). This decision rests on that existing
architecture and scheduler evidence, not on any claim that provider
integrations are technically impossible -- each of the four remains a
legitimate, evidence-driven, after-release opportunity (see "Reopening
criteria," below).

## Reopening criteria

Concrete evidence that may reopen a dedicated provider adapter after
release:

- repeated real users (a pattern, not one isolated report) unable to
  connect an otherwise-supported camera through ONVIF/RTSP/local-USB/
  platform standards, where a specific ecosystem adapter would concretely
  resolve it;
- a provider exposes source-resolution/timestamp/capability facts
  materially unavailable through ONVIF/RTSP/local standards and would
  measurably improve MockingBird's own evidence quality -- the same bar
  already implied by the existing "Source-resolution evidence contract"
  and "Capability-aware UX" doctrine, not a new standard invented here;
- a large, *measured* reduction in installation burden for a proven real
  user segment, not a speculative one;
- organization/research deployments repeatedly, demonstrably depending on
  one specific ecosystem as a practical adoption prerequisite;
- a dedicated adapter would materially improve reliability, not merely add
  to an integration count.

Not acceptable by itself, for any of the four: provider popularity,
integration-count marketing, "competitors have it," technical curiosity,
availability of an API, or a desire to build a plugin framework. This is a
deferral pending evidence, not a claim that these integrations will
"never" happen.

## Architecture contract for future adapters

Locked for any dedicated provider adapter built later, for any of the four
candidates or another: it must terminate into the same authoritative
Source -> Stream -> Zone -> Activity Session -> Visit -> Evidence ->
Detection Proposal -> Review Decision -> Observation spine every existing
provider (`external_url`, `local_folder`, `rtsp`/ONVIF, `local_camera`,
`webhook`, `integration`) already uses -- the identical "converge
immediately, never fork" discipline ONVIF already proved out against the
RTSP bridge (see "Existing acquisition architecture," above), applied to a
future ecosystem adapter instead of a live-video pipeline. Concretely, a
future adapter may not create:

- parallel Visit truth;
- parallel Reviewed truth -- imported detections/labels remain Evidence/
  Detection Proposals until MockingBird's own Review Decision, exactly as
  the existing generic webhook boundary already requires;
- a second camera database -- it must be an ordinary
  `SourceProviderKind`-shaped row against the one existing Source table,
  the way ONVIF's own `camera_onvif_profiles` table is bounded,
  informational provenance only, never a second authoritative store;
- cloud-required operation -- would violate local-first doctrine and the
  Personal/Home deployment profile;
- a surveillance-specific product mode -- would violate "not primarily...
  a surveillance platform";
- separate per-provider analytics truth -- all analytics/exports must
  continue to derive only from Review Decisions (product-doctrine.md
  "Product objects" > "Dataset export / Analytics").

## Scheduler effect

Resolving Lane K removes **zero** launch blockers. `docs/
release-execution-state.md` §6 already classified it as category **B**
("pre-release decisions" -- a decision required before launch, not an
implementation milestone), never category A ("release-critical"); closing
it converts an open decision into a closed one, exactly as Lane O
(platform-support declarations) and Lane P's ffmpeg-licensing item were
each closed in place without changing their category. No release-shape
recategorization is needed, mirroring that precedent.

Remaining release-critical lanes/decisions, unchanged by this milestone:

- Lane R / Gate A -- Complete Field Acceptance (daylight re-proof still
  open);
- Lane G -- Camera / Source Experience's own remaining real-hardware
  live-capture/preview validation;
- Lane P -- the codebase `LICENSE` decision (still genuinely absent);
- the still-open BirdNET commercial-adjacent legal posture (§2);
- External Pre-Release Acceptance;
- Final Release Hardening (Lane S / roadmap.md Gates F-G).

Current authorization returns to, and remains, **NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED**. This milestone does not
authorize a provider implementation, Lane R, External Pre-Release
Acceptance, or Final Release Hardening, and does not select a next
development milestone.

## Validation

Since this is a documentation-only milestone (zero production code
changed), Tier 3 and Core were not run, per the governing brief. Performed
instead:

- **Internal link/reference correctness:** every filename this report and
  the two reconciliation edits cite (`docs/onvif-provider-boundary-
  design.md`, `docs/next-provider-boundary-decision.md`, `docs/
  generic-webhook-provider-boundary-design.md`, `docs/
  source-adapter-boundary-design.md`, `docs/camera-source-release-
  hardware-validation-closure-v1-report.md`) was confirmed to exist in the
  repository before citing it.
- **Lane K status consistency:** `docs/release-execution-state.md` §1
  (new accepted-HEAD bullet), §3 (new reconciliation entry), and §6.K (the
  lane's own status line) all updated to agree; §6's category-B list
  parenthetical updated to match, mirroring how Lane O/Lane P's
  parentheticals were updated in place when each was resolved.
- **No accidental lane removal:** `git diff` on both edited files reviewed
  in full; no lane heading, lettered section, or roadmap section was
  deleted -- only Lane K's own status text and one new roadmap.md
  paragraph changed.
- **No stale prose claims a provider decision is required before
  launch:** grepped both files (and the wider `docs/` tree) for
  Frigate/Blue Iris/Scrypted/Home Assistant/NVR mentions before editing;
  none asserted that any of the four was required before launch --
  Lane K's prior text said only that the choice was *undecided*, which
  this milestone resolves.
- **Roadmap still preserves future provider opportunity:**
  `docs/roadmap.md`'s existing "Remaining product maturity" (Layer 8)
  bullet naming "ecosystem/provider integrations" as a retained lane is
  untouched; the new "After-release lanes" paragraph added by this
  milestone explicitly restates that these four remain legitimate,
  evidence-driven, after-release opportunities, not removed capabilities.

## Decision

**A**

- Current scheduler verified against the exact expected starting state
  (HEAD, schema, Lane G/Lane K status, authorization) -- no discrepancy.
- Lane K evidence reviewed: its own status text, the four named
  candidates, and the historical `next-provider-boundary-decision.md` /
  `source-adapter-boundary-design.md` / `generic-webhook-provider-
  boundary-design.md` archaeology behind it.
- Existing standards-based acquisition confirmed from real code and design
  docs across every category the brief named: Camera Node, ONVIF, RTSP/
  RTSPS, local USB/platform camera, offline/recorded ingest, camera-trap
  ingest -- plus a general-purpose, vendor-neutral webhook ingress already
  available to any of the four ecosystems today.
- Each named provider (Frigate, Blue Iris, Scrypted, Home Assistant)
  explicitly, individually assessed against value, capability gap,
  standards coverage, surveillance-pressure, and new credential/security
  surface.
- Launch decision explicit: deferred pending evidence, not implemented,
  not scheduled, and not claimed impossible.
- No provider adapter, plugin framework, MQTT client, message broker, or
  integration marketplace was implemented.
- Future opportunity preserved in both `product-doctrine.md` (already did,
  untouched) and `roadmap.md` (a new, additive "After-release lanes"
  paragraph).
- Reopening criteria are concrete and evidence-based, not "never."
- Provider-neutral architecture explicitly locked for any future adapter
  (Source/Stream/Visit/Review/Observation spine; no parallel truth; no
  second camera database; no cloud-required operation; no
  surveillance-specific mode; no separate analytics truth).
- Scheduler and roadmap made mutually consistent; no release-critical lane
  was silently dropped.
