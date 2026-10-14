# MockingBird -- Case Study (source for a portfolio page)

*Source material, not a published page. Every claim below is traceable to the
repository; items marked **[OWNER TO CONFIRM]** are personal facts only the
owner can state. No impact metrics, customers, accuracy benchmarks, or
deployment claims are made, because none are established.*

## Summary

MockingBird is a local-first nature observatory. It watches outdoor cameras,
notices candidate wildlife visits with a computer-vision detector, shows the best
evidence with a labeled species *suggestion*, and asks a person to confirm or
correct it. Only that human decision becomes the record that the Bird Log,
analytics, and exports are built from. It runs entirely on the user's own
computer -- no account, no cloud, no telemetry.

## Problem and motivation

Backyard and trail cameras produce thousands of mostly-empty frames. Existing
approaches tend to fall into two failure modes: security-camera tooling that
treats animals as motion alerts, and ML demos that present a model's guess as
fact. Both erode trust in the resulting "species list." The motivating question
for this project: *what would a wildlife record look like if its trustworthiness
were the product?*

## Product solution

- **Observe:** connect a camera (a Raspberry Pi Camera Node, an RTSP/ONVIF
  network camera, USB) or import recorded photos/video; draw Zones that matter.
- **Discover:** a wildlife detector and tracker admit candidate *Visits* with
  their best evidence frames.
- **Understand:** Today, Bird Log, Place Story, and Zone/hour patterns build
  context.
- **Confirm:** a species model proposes ranked suggestions; a human confirms,
  corrects, or answers "unknown." Suggestions never become truth on their own.
- **Remember / Improve:** reviewed history is durable, backed up, and
  exportable; corrections are the dataset-grade truth for exports.

## Role and engineering ownership

**[OWNER TO CONFIRM exact role title and which parts you personally hand-wrote
or hand-ran; the repository cannot establish either.]** What the repository
itself shows:

- **AI-assisted development, disclosed.** Most of the code was written by AI
  coding agents working from the owner's task packets. 469 of the 772 commits
  at this writing carry a Claude co-author trailer; the remaining commits carry
  no such trailer, and the repository does not record which tool or person
  produced them, so no claim is made about them either way. Nothing here
  presents the project as hand-typed or single-handedly coded.
- **Architecture and direction (owner).** One owner set the product doctrine
  ([product-doctrine.md](../product-doctrine.md)), the truth model, the
  roadmap, and the scope of each milestone, and recorded them in-repo. Those
  choices are what the agents were asked to implement, for example "model
  output is evidence; only explicit review is truth".
- **Engineering process (owner-directed, agent-executed).** Agents worked
  under written guardrails ([AGENTS.md](../../AGENTS.md)): a task packet before
  any edit, a conditional design-document router, validation tiers, and an
  acceptance record per milestone. The owner wrote those rules and made the
  acceptance calls.
- **Implementation (agents, under that direction).** Agents wrote most of the
  backend, frontend, Camera Node, and test code, plus the design contracts that
  explain it.
- **Integration and validation (shared).** Agents ran the test tiers and the
  hardware sessions recorded in
  [release-execution-state.md](../release-execution-state.md), including field
  runs on a Raspberry Pi 4 Camera Node and a native Windows machine with an
  NVIDIA GPU; those runs happen on the owner's own equipment and the owner
  decides whether a result is accepted.
- **Accountable owner decisions** include: the truth model, what is frozen
  versus re-opened, which candidate models are *not* promoted, and the
  licensing posture (MIT for the code; third-party model terms kept separate).

The engineering story is therefore *specifying, constraining, integrating,
verifying, and accepting* agent-written work, not typing every line.

## Architecture and major technical decisions

Overview and diagram: [README -- How it works](../../README.md#how-it-works);
authoritative detail: [architecture.md](../architecture.md).

1. **Evidence versus truth as a hard boundary.** Detections, proposals,
   suggestions, and imported labels are *evidence*. A single predicate
   (`review_provenance.is_authority_eligible`) decides what counts as reviewed
   truth; omitted or agent-supplied provenance never defaults to human
   authority. This makes "the Bird Log is only what a person confirmed" a
   structural property instead of a convention.
2. **Local-first by construction.** FastAPI + SQLite + a React UI served by one
   process. Forward-only migrations (currently schema 62), a verified
   pre-upgrade backup, and rollback-safe restore are built in.
3. **Camera Node as replaceable infrastructure.** The edge device is a
   lightweight capture/transport service, systemd-supervised, never the system
   of record; a replacement reattaches to the existing logical camera instead of
   forging history.
4. **Provider-neutral Observation Engine.** Live and recorded video enter the
   same detect -> track -> assemble -> admit seam, so one admission rule set is
   exercised by live cameras, offline clips, and the replay harness.
5. **No model gets production authority by being newer.** A candidate
   detector/classifier must beat the incumbent on identical data first. The
   benchmark record shows several candidates evaluated and none promoted
   ([detection-species-model-benchmark-promotion-v1](../detection-species-model-benchmark-promotion-v1-report.md)).

## Computer vision and acoustic capabilities

- **Detection:** MegaDetector v5a exported to ONNX and run with ONNX Runtime on
  an NVIDIA GPU; tracking and Zone-aware Visit admission on top. Detector output
  is evidence only.
- **Species suggestion:** BioCLIP 2 (CPU) ranks a closed candidate list against
  the saved evidence frame. Scores are explicitly *uncalibrated*; the product
  abstains ("identification uncertain") when candidates are too close.
- **Acoustic (optional):** BirdNET produces suggestion evidence from a
  microphone. Its model weights are non-commercial licensed, so they are never
  bundled in official packaging.
- **What the demo honestly shows:** with the bundled demo, one clip yields a
  correct high-confidence suggestion (northern mockingbird), one yields a
  *confidently wrong* closed-set suggestion (a pileated woodpecker called
  "red-bellied woodpecker", because pileated is not in the candidate list), and
  one yields an abstention (goldfinches). That spread is the argument for the
  human review step.

## Privacy and local-first design

Video and data stay on disk the user controls; nothing uploads automatically.
Privacy Zones and Ignore Zones are *trigger-level* exclusions and are documented
as such -- never claimed as pixel-level redaction
([privacy-ignore-zone-contract.md](../privacy-ignore-zone-contract.md)). Secrets
are redacted from status, logs, and the support bundle. A "Local Only" posture
and exactly which optional features may touch the network are documented in
[privacy-and-security.md](../privacy-and-security.md).

## Technical challenges and tradeoffs

- **Duplicate or fragmented Visits.** One animal can become several Visits, and
  several animals can share one encounter. The repository records a sequence of
  fixes (continuity, ambiguous-boundary arbitration, multi-subject assembly) and
  an honest remaining over-split: in the demo, one woodpecker became two
  sibling Visits on one machine and one Visit on another.
- **Honest time.** Recorded video has no trustworthy capture time, so the
  system refuses to fabricate one; those Visits are excluded from time-windowed
  analytics. A deliberate trade of completeness for correctness.
- **A closed species list.** A bounded candidate set keeps suggestions
  explainable but means out-of-list birds get a wrong or uncertain answer. The
  mitigation is the review step, not a bigger model.
- **Hardware reality.** Live detection is NVIDIA-GPU-only and the validated
  Host is Windows 10; real-hardware validation covered a single Pi 4 Camera
  Node and one RTX 4060 Ti desktop.
- **Reproducibility under change.** A perception replay harness re-runs recorded
  footage through the real admission stack in a disposable database so fixes can
  be checked without waiting for another real bird.

## Screenshots and recommended demo sequence

Captured from the demo instance
([walkthrough](../portfolio-demo-walkthrough.md)); files in
`docs/assets/screenshots/`.

1. `01-first-run-welcome.png` -- first-run onboarding.
2. `04-review-queue.png` -- candidate Visits waiting for a human.
3. `05-visit-evidence-suggestion.png` -- evidence plus a labeled suggestion.
4. `06-visit-wrong-suggestion.png` -- a suggestion that is wrong, and the
   correction path.
5. `07-visit-abstained.png` -- the honest "not sure".
6. `08-bird-log.png` -- the record built only from confirmations.

Suggested live demo order (about five minutes): onboarding sign-in screen ->
Review Queue -> open the mockingbird Visit (correct suggestion) -> open the
woodpecker Visit (wrong suggestion; correct it) -> open a goldfinch Visit
(abstained) -> confirm the mockingbird Visits -> Bird Log.

## Testing and engineering quality evidence

- ~350 backend test modules, 50 Playwright browser specs; last recorded full
  runs: 6,278 backend and 203 browser tests passing at schema 62 (recorded in
  [release-execution-state.md](../release-execution-state.md); not re-run in
  full for this portfolio pass).
- Test-database isolation contract so tests cannot touch real data.
- A replay harness for perception regressions; field-acceptance tooling for
  real-camera runs.
- Written design contracts for every consequential decision, with the evidence
  behind them.

## Current status and future direction

Pre-release: the source reports `0.1.0`; the first public release (1.0) is not
published and its remaining steps are owner-side
([owner-release-checklist.md](../owner-release-checklist.md)). Direction is
bounded by the roadmap ([roadmap.md](../roadmap.md)); this case study does not
promise any item beyond it.
