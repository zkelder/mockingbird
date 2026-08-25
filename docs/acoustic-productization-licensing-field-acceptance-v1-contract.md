# Acoustic Productization, Licensing & Field Acceptance v1 — Contract

Status: archaeology, licensing decision, implementation, testing, and real
field acceptance all complete. See the companion
[acoustic-productization-licensing-field-acceptance-v1-report.md](acoustic-productization-licensing-field-acceptance-v1-report.md)
for the milestone closure report (26 closure questions answered, final
validation totals, real field-acceptance results). Starting HEAD `63f0a57`
(schema v53). This is not a from-scratch acoustic
milestone — substantial acoustic/BirdNET/multimodal capability already existed
(Acoustic/BirdNET Observation Foundation v1, Acoustic Runtime & Quality v1,
Multimodal Observation & Soundscape v1, plus dedup work folded into Everyday
Discovery/Product Experience v2 and Camera/Source Multi-Camera Maturity v1).
This milestone verifies that capability against the current repository and
actual installed artifacts (not prior memory), and closes the bounded gaps
required for a credible, honest release posture.

## How this was produced

Seven parallel read-only archaeology passes (acoustic core pipeline; multimodal
association & duplication; licensing evidence — code, package metadata, and
live upstream fetches; audio input/hardware matrix; privacy/retention/export;
product UX/Today/Bird Log/coverage; existing test/validation inventory), plus
direct verification of the highest-stakes claims (license files read personally,
`build_local_product.py` grepped personally, upstream license text fetched
personally, real Windows audio hardware enumerated personally). Two independent
agents (multimodal-association and product-UX) surfaced the same real bug from
different angles with no shared context — cross-validation, not a single
subagent's framing taken on faith. Two memory claims about this codebase were
found stale and corrected below (§ Corrections to prior memory).

---

## Corrections to prior memory

1. **"Visual/acoustic fusion is not started"** (memory,
   `acoustic-birdnet-observation-foundation-v1-2026-08-22` and
   `remote-transport-acoustic-integration-v1-2026-08-22`) was accurate when
   written, then overtaken the very next day: commit `0cdfb16`, "Multimodal
   Observation & Soundscape v1" (2026-08-23), built the full association engine
   — no memory entry was ever written for that session (an established gap in
   this project's memory habit, not a code contradiction).
2. **"Completed host transport files still have no dedicated consumer/retention
   lifecycle"** (memory,
   `remote-transport-acoustic-integration-v1-2026-08-22`) is no longer true.
   `main.py:679-692` now wires `on_item_completed` to
   `ProductRepository.consume_camera_node_transport_item`, a documented
   crash-safe two-phase consume-then-delete lifecycle. Landed after that
   memory's snapshot.

---

## P0 / P1 / P2 findings (explicit summary)

Per this milestone's own severity axes (legally/truthfully/privately/
operationally unsafe = P0; bounded productization gap required for a
credible first release = P1; useful later, not a blocker = P2). Fix status
reflects the closure report.

### P0

- **P0-1**: BirdNET model licensing (CC BY-NC-SA 4.0) had never been
  evaluated against MockingBird's own named future commercial-adjacent
  activities (paid support, donations, Kickstarter, appliances, hosted
  services, sponsorship); the packaging state that made this currently safe
  was accidental (an omission), not documented or protected. **Resolved**
  this milestone: Decision B formalized in this doc, a durable regression
  guard added to the packaging script (`verify_no_nc_licensed_acoustic_
  model_redistribution`), roadmap.md's long-open "BirdNET licensing
  disposition" item closed.

### P1 — fixed this milestone

- **P1-1**: Today/Bird Log/Place-Activity-Report/Biodiversity-Summary
  count fields disagreed with their own already-collapsed display rows for
  a confidently-associated visual+acoustic pair (self-contradictory within
  one API response). Fixed once at the shared root plus Today's own reuse.
- **P1-2**: The packaging exclusion of the NC-licensed model was accidental,
  not deliberate/durable (same artifact as P0-1's fix).
- **P1-3**: macOS microphone capture silently reused the broken Linux
  command instead of failing honestly. Fixed.
- **P1-4**: `MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE` was documented but dead
  code in production. Fixed (wired in both production call sites).
- **P1-5**: Zone/Privacy-Ignore has no audio analog at all, and this was
  completely undisclosed. Fixed via documentation + the one real
  "point of consent" that exists today (no new audio-zone geometry built).
- **P1-6**: `MicrophoneCaptureSession._known_segments` grew unboundedly for
  a session's lifetime. Fixed (pruned to on-disk listing every poll).

### P1 — disclosed, deliberately not fixed this milestone (reasoning in
the closure report's "Remaining bounded gaps")

- **P1-7**: Acoustic monitoring has zero input into coverage/effort
  accounting, and the two status endpoints that could tell a user
  "microphone/model unavailable" have zero frontend callers anywhere.
  Requires genuinely new frontend UI; no Doctor UI exists for any subsystem
  yet, acoustic or otherwise — out of proportion for this milestone.
- **P1-8**: Device lifecycle (disconnect/reconnect/permission-failure/
  sample-rate-mismatch) synthetic test coverage remains thinner than the
  visual Camera Node's equivalent, though real hardware field acceptance
  this milestone covers some of this territory more genuinely than mocks
  would (bogus-device, clean-stop-then-restart, concurrent access).
- **P1-9**: `STRICT_WINDOW_MS`/`POSSIBLE_WINDOW_MS` (15s/60s) remain
  field-uncalibrated — real hardware capture was proven this milestone, but
  no real simultaneous visual+acoustic bird encounter was naturally
  observed to calibrate against.
- **P1-10**: The full HTTP-API-driven live-mic-to-Visit-creation flow was
  not re-verified live on real hardware (existing Windows deployment there
  is stale/pre-acoustic; a full redeploy was judged disproportionate to
  what this milestone's specific hardware probe needed).
- **P1-11**: Clock-offset-aware association degradation is unimplemented
  and untested. Low real-world exposure today (Camera Node has zero
  microphone support, so no genuine cross-device clock skew is reachable
  yet) — revisit if/when Node-side audio is ever built.

### P2 — useful later, not blockers, correctly out of scope

- RTSP audio, recorded-video embedded audio, Camera Node microphone, ONVIF
  audio: all correctly unsupported/deferred today, explicitly named as such
  in existing design docs — matches this milestone's own "single dependable
  path" instruction, not reopened.
- The acoustic retry ladder's third rung (120s backoff) is structurally
  unreachable given `max_attempts=3` — a dead config value, not a
  correctness bug; left as-is.
- The host-side WAN-transport whitelist already accepts `audio/wav` though
  no Camera Node producer exists yet — worth a look before any future
  Node-mic feature, not urgent now.
- `ai-edge-litert`'s dist-info ships no bundled LICENSE text file
  (metadata-field-only) — immaterial, it is permissively licensed either
  way, just a minor evidentiary completeness gap.

## Phase 1 — Bounded archaeology: what actually exists today

### Architecture (confirmed against code, not docs)

Real production BirdNET inference (`src/mockingbird/species/birdnet_adapter.py`)
via `birdnetlib` + a `tflite_runtime`→`ai-edge-litert` backend-substitution shim
(inference itself is real, not faked). Live microphone capture is a real ffmpeg
subprocess using its own segment muxer (15s segments), gated by an explicit
`capture_consent == "true"` field on the Source's own provider config —
deliberately decoupled from video's "armed" state, never auto-starting.
`AcousticRuntimeService` is a background daemon thread (2s poll) that ingests
finalized segments, runs BirdNET, merges same-species windows, and applies a
bounded 3-attempt retry ladder before a durable, marker-gated 48h retention
sweep for its own ephemeral working segments only — human/manual audio imports
are structurally immune to that sweep (`acoustic_working_segment` marker,
verified only ever set by the automatic-capture path). A non-avian
soundscape-class filter (`NON_AVIAN_SOUNDSCAPE_LABELS`) is applied before
candidate creation. `DEFAULT_MIN_CONFIDENCE = 0.5`, applied per analysis run.

Multimodal association (`src/mockingbird/observation/multimodal_association.py`,
landed one day after the acoustic foundation, `0cdfb16`) is a bounded,
deterministic, timing-only engine — never reads species/taxon at association
time. Two tiers: `"associated"` (exactly one opposite-modality candidate,
within a 15s strict window or overlapping) and `"possible"` (competing
candidates, or only within a wider 60s window). Conflicting taxa (visual
cardinal + acoustic blue jay) can still tier `"associated"` on timing grounds —
by design, disclosed honestly via a separately-computed, never-hidden
`taxon_agreement: "agrees" | "differs" | "not_comparable"` fact, never used to
suppress or auto-resolve the conflict. **Directly proven, not assumed, that
association never promotes anything to reviewed truth**: a dedicated
regression test (`test_scenario_8_human_correction_becomes_authoritative_and_
is_never_overwritten`) re-runs reconciliation after a human correction and
asserts the corrected label survives untouched.

### Confirmed real, user-visible gaps (see P0/P1/P2 below for disposition)

- **Bird Log's displayed `observation_count` double-counts a confidently-
  associated visual+acoustic pair**, even though the *list rows* for the exact
  same encounter are correctly collapsed to one — the same API response
  literally disagrees with itself. Independently found by two separate
  archaeology passes.
- **Acoustic monitoring has zero input into coverage/effort accounting**, and
  the one status endpoint that could tell a user "microphone/model
  unavailable" (`BirdNetStatusResponse`/`AudioCaptureStatusResponse`) has
  **zero frontend callers anywhere** — not rendered on any page, including the
  dedicated Doctor/classifier-readiness surface.
- **Zone/Privacy-Ignore has no analog for audio, and nothing discloses this.**
  A microphone Source's captured audio can never be Zone-privacy-withheld
  (acoustic Visits hardcode `zone_id=None`, honestly, since audio has no
  geometry) — but `docs/privacy-ignore-zone-contract.md` never says so.
- **macOS microphone capture silently reuses the Linux `-f pulse` ffmpeg
  branch** — there is no `darwin`/CoreAudio branch anywhere in the codebase;
  this would not work on real macOS hardware and is not disclosed as such.
- **The packaged Windows product does not include BirdNET at all** —
  `scripts/build_local_product.py` has zero references to "birdnet" or
  "acoustic" (confirmed via case-insensitive grep of the entire file), while
  it unconditionally bundles BioCLIP's full runtime and the GPU/ONNX stack.
  This is safe today, but accidental — nothing documents or protects the
  decision, so a future packaging change could silently start redistributing
  an NC-licensed model by analogy to how BioCLIP was added.
- `MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE` (env var) and `resolve_birdnet_config()`
  are documented as the configuration path but are **dead code in production**
  — no real call site ever invokes them.
- No device disconnect/reconnect/permission-failure/sample-rate-mismatch tests
  exist for audio capture, while extensive equivalent tests exist for the
  visual Camera Node lifecycle. `durable-camera-monitor-lifecycle-design.md`'s
  own "Non-goals" section explicitly excludes audio from that restart-
  supervisor framework.
- `MicrophoneCaptureSession._known_segments` is an in-process `set[Path]` that
  only grows for the life of a capture session (Path objects only, no audio
  bytes — a memory-hygiene issue, not a privacy one).
- The acoustic retry ladder's third rung (120s backoff) is structurally
  unreachable given `max_attempts=3` — a dead configuration value, not a
  correctness bug.
- Clock-offset-aware association degradation is not implemented or tested —
  `evaluate_temporal_association()` never reads clock provenance. Currently
  low real-world exposure: Camera Node has **zero** audio support today, so
  every acoustic Source is Host-local, sharing the Host's own clock with the
  Host's own visual pipeline — true cross-device clock skew between an
  acoustic and a visual source is not yet a reachable scenario. Recorded as an
  honest, disclosed limitation to revisit if/when Node-side audio ever lands,
  not fixed defensively now.

### Confirmed clean / already correct (verified, not assumed)

Retention-sweep eligibility predicate; support-bundle/Doctor export (never
includes raw audio bytes or paths); logging discipline (no raw media paths
logged anywhere, audio included — a codebase-wide practice, not audio-specific);
research/Camtrap DP export (audio passes through the identical eligibility gate
as visual, `include_media` confirmed still fully inert — no export anywhere
bundles media bytes); BirdNET inference is strictly local/on-device, zero
network egress; Camera Node transport is inbound-only (Node→Host) and
Camera-Node-produced media is hardcoded `image/jpeg` today, so no audio can
currently traverse that channel (though the host-side whitelist already
accepts `audio/wav` for if/when that changes — a disclosed sleeper item, not
an active problem); Stage-7 review-queue acoustic fallback (Today/review-queue
counting) re-verified present and correct; audio playback is native
`<audio controls>` with graceful error fallback; review actions for acoustic
suggestions are fully unified with visual (same queue, same confirm/correct
flow, copy-only difference); Place Activity Report's headline per-species
totals **are** correctly deduplicated via `_associated_visit_ids_to_exclude_
from_counting` (the mechanism exists and works — it just isn't applied
everywhere it needs to be, see above).

### Real audio input capability matrix (validated vs. structural vs. unsupported)

| Input | Status | Basis |
| --- | --- | --- |
| Recorded WAV/audio file import | **Validated** | Real xeno-canto recording, real bundled model, correct species + confidence, confirmed reaching Bird Log truth end-to-end |
| Host USB microphone (live capture) | Structurally supported, **not hardware-validated before this milestone** | Real ffmpeg subprocess/segment path, only ever exercised via injected fakes in tests — no physical mic existed in any prior session |
| Host USB audio interface | Same as above, no code distinction from a plain mic | — |
| Camera Node microphone | **Deferred** (explicit in-doc), zero code | `docs/camera-node-boundary-design.md` names audio as deliberately deferred |
| RTSP audio stream | **Unsupported** | `rtsp_bridge.py` passes ffmpeg `-an` (explicit no-audio) unconditionally |
| Recorded video's embedded audio track | **Unsupported** | Video decode also passes `-an`; the audio-analysis endpoint hard-rejects non-audio media |
| Offline/camera-trap media audio | Not a distinct path — inherits WAV-import (validated) / video (unsupported) | No separate camera-trap pipeline exists |
| ONVIF-discovered audio | **Deferred** (explicit in-doc), zero code | `docs/onvif-provider-boundary-design.md` names this explicitly out of scope |

Per this milestone's own instruction ("a single dependable path is more
valuable than six half-supported paths"), the officially-supported v1 acoustic
inputs are: **recorded audio file import** (already validated) and **Host
local microphone live capture** (structurally complete; this milestone
attempts real-hardware validation in Phase 19, see below). Every other row
stays exactly as-is — correctly out of scope, not silently promised.

---

## Phase 2 — Authoritative licensing decision

This section is evidence-based, not a legal opinion. Ambiguity is flagged as
ambiguity; a conservative architecture is chosen where the license text does
not settle the question.

### Per-artifact record

| Artifact | Version | Source of evidence | License | Redistribution | Modification | Commercial use | Attribution | ShareAlike | License text must ship? | Currently compliant? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `birdnetlib` (wrapper code) | 0.18.1 | Shipped `dist-info/licenses/LICENSE`, byte-identical to live-fetched `github.com/joeweiss/birdnetlib` LICENSE | **Apache-2.0** | Yes | Yes | Yes | Yes (notice preservation) | No | Yes (already ships with the wheel; MockingBird doesn't need to re-bundle it since MockingBird never vendors the wheel itself) | Yes |
| BirdNET-Analyzer **model weights** (`GLOBAL_6K_V2.4`, bundled as package data inside the `birdnetlib` wheel) | 2.4 | Shipped `birdnetlib/models/analyzer/LICENSE` (full CC legal text) + `models/analyzer/README.md` (explicit attribution) + live-fetched upstream `birdnet-team/BirdNET-Analyzer` README's own "## License" section (splits code=MIT / models=CC BY-NC-SA 4.0) + the maintainer's own separately-named `birdnet-models-nc-sa` metadata repo | **CC BY-NC-SA 4.0** (Cornell K. Lisa Yang Center for Conservation Bioacoustics) | **NonCommercial only** | **NonCommercial only** (Adapted Material) | **No** (for Sharing/Adapting; see "on-device inference" discussion below) | Yes, required | **Yes**, required for any Adapted Material shared further | Yes | **Yes, today** — see "actual packaging fact" below |
| `ai-edge-litert` | 2.2.0 | `dist-info/METADATA` field only (no bundled LICENSE text file — a disclosed, immaterial evidentiary gap) | Apache-2.0 | Yes | Yes | Yes | Yes | No | N/A (not MockingBird's to redistribute directly) | Yes |
| `librosa` | 0.11.0 | Shipped `LICENSE.md` | ISC (BSD-2-equivalent) | Yes | Yes | Yes | Yes | No | N/A | Yes |
| `resampy` | 0.4.3 | Shipped `LICENSE.md` | ISC | Yes | Yes | Yes | Yes | No | N/A | Yes |
| `audioread` | 3.1.0 | Shipped `LICENSE` | MIT | Yes | Yes | Yes | Yes | No | N/A | Yes |

**Do not conflate the code license with the model license** — they are
independently, deliberately split by the upstream project itself (its own
README says so explicitly), and MockingBird's code already keeps this straight
(`birdnet_adapter.py`'s `MODEL_LICENSE` constant has correctly named CC BY-NC-SA
4.0 since the feature was first built).

### The actual packaging fact that resolves most of the risk today

`scripts/build_local_product.py` — the script that builds MockingBird's actual
distributable Windows product — has **zero** code referencing BirdNET or
acoustic anything (confirmed by a case-insensitive grep of the entire file).
It unconditionally installs BioCLIP's complete runtime and the GPU/ONNX
detector stack into the packaged artifact, with no equivalent for
`classifier-birdnet`. **The BirdNET model is never redistributed by
MockingBird's own release artifacts today.** The only way it reaches a machine
is `pip install -e .[classifier-birdnet]` — an explicit, separate action a
developer/user takes themselves, pulling directly from PyPI under
`birdnetlib`'s (and transitively Cornell's) own terms.

This is currently **safe by omission, not by design** — nothing documents or
protects it, so a future packaging change (adding `classifier-birdnet` to
`WINDOWS_RUNTIME_REQUIREMENTS`-style unconditional install, by analogy to how
BioCLIP was added) could silently start redistributing an NC-licensed model.
Closing that gap — making the exclusion deliberate, documented, and durable —
is this milestone's concrete Phase 17 deliverable.

### What the license text does and does not settle

**Not ambiguous:** if MockingBird's own distribution channel (installer,
packaged bundle, appliance image) ever bundles/vendors the model file itself,
that is "Sharing the Licensed Material" under the CC license's own definition,
restricted to NonCommercial purposes. If that distribution channel is "primarily
intended for or directed towards commercial advantage or monetary compensation"
— sold, bundled with paid support, funded via Kickstarter pre-orders, offered as
a paid hosted service, sold as a preassembled commercial appliance — bundling
the model into *that* distribution is a real, non-speculative violation risk.
This is the central case CC BY-NC exists to restrict, and it is squarely
avoidable: **do not bundle the model into any commercially-adjacent
distribution.**

**Genuinely ambiguous, flagged rather than resolved:** whether an individual
end-user's own private, on-device use of MockingBird+BirdNET — where the model
was never bundled by MockingBird itself, but obtained by the user's own
independent `pip install` action under birdnetlib's own terms — could ever be
implicated merely because the surrounding open-source project *also* accepts
donations, sells optional paid support, or sells a preassembled appliance as a
separate SKU. CC BY-NC-SA's operative verbs are "reproduce and Share" and
"produce...Adapted Material" — pure private inference (not redistributing the
model) is a defensible reading of falling outside "Share" as CC defines it, and
BirdNET-Analyzer's own upstream README states "all educational and research
purposes are considered non-commercial use" — but this is not settled case law,
and MockingBird is not a law firm. **This question is recorded as unresolved.
Recommendation: legal review before any commercial-adjacent distribution
decision (paid support, Kickstarter, appliance, hosted service, sponsorship)
that would touch the acoustic feature specifically** — e.g., before ever
bundling the model into a paid appliance's preloaded image, even if the appliance
itself is otherwise identical open-source software.

### Architecture decision: **B — Optional external model**

MockingBird's own release artifacts (git repository *and* packaged installer)
never bundle or redistribute the BirdNET model weights. `classifier-birdnet`
remains an explicit, separately-installed optional extra; a user who wants
acoustic support takes a deliberate action to obtain it, under upstream's own
terms, not MockingBird's redistribution. This is not a new architecture — it is
the *existing, accidental* state, made deliberate, documented, and durable:

- `scripts/build_local_product.py` gets an explicit comment/guard recording
  *why* `classifier-birdnet` must never be added to the unconditional packaging
  requirements the way BioCLIP was, so a future contributor doesn't
  "helpfully" close what looks like an inconsistency.
- The product-facing story for acoustic support becomes honest: "optional,
  separately obtained, under its own license" — never implying the weights
  ship as part of MockingBird itself.
- Any future commercial-adjacent activity (paid support, donations funding
  development, Kickstarter, appliances, hosted services, sponsorship) must not
  bundle the model without a separately-obtained rightsholder permission — this
  is recorded as a standing constraint on future business-model decisions, not
  merely a technical footnote, and directly closes roadmap.md's own long-open
  "BirdNET licensing disposition" item under "Public release readiness."

This is Option B exactly as this milestone's brief defines it: "MockingBird
does not redistribute the model; user explicitly installs/downloads the
external artifact under its own terms."

---

Phases 3–20 (product contract, time/sync semantics, multimodal association
safety, duplication/counting, input matrix, device lifecycle, format
normalization, confidence/abstention, privacy, storage cost, coverage
accounting, product experience, review experience, research/export,
packaging, platform matrix, and real field acceptance) were each audited
directly against current code as part of the archaeology above and the
implementation/testing/field-acceptance work summarized in the P0/P1/P2
section — none required a change beyond what is listed there, except where
explicitly named as a fix. Full narrative detail, the final validation
totals, and all 26 closure-question answers are in the companion
[acoustic-productization-licensing-field-acceptance-v1-report.md](acoustic-productization-licensing-field-acceptance-v1-report.md).
