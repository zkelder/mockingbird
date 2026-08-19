# MockingBird Roadmap

This is the current planning authority. It intentionally describes completed
foundations briefly and keeps detailed historical phase narration in
[roadmap-history.md](roadmap-history.md) and the linked design documents.

## Product outcome

MockingBird is a local-first, hardware-agnostic, bird-first but
wildlife-native nature observatory that helps people notice, understand,
confirm, and remember wildlife around a place. Detection, tracking, and
classification are infrastructure; trustworthy Observations, coherent
Visits, good evidence, honest uncertainty, efficient review, meaningful
discoveries, durable history, and growing understanding of a place are the
product. See [product-doctrine.md](product-doctrine.md) for the full
doctrine this roadmap sequences.

The user-facing loop is **Observe → Discover → Understand → Confirm →
Remember → Improve**. The internal evidence/truth architecture is Source →
Stream → Zone → Activity Session → Visit → Evidence → Detection Proposal →
Interpretation → Review Decision → Observation → Export/Analytics
(product-doctrine.md; implementation vocabulary still uses
Event/Visit/Detection/ReviewLabel, see [glossary.md](glossary.md)).
Detectors and SpeciesSuggestions are evidence; explicit correction is the
only reviewed truth used for confirmed species, history, exports, and
analytics; unknown and abstained outcomes are valid.

## Current status

- **Current phase:** Phase 1 -- Trustworthy Single-Site Observatory (below).
- **Current exit gate:** one representative installation can run for days
  and create trustworthy useful history without developer babysitting.
- **Already complete** (see [roadmap-history.md](roadmap-history.md) for
  detail): the real Camera Node path; the native ONNX Runtime CUDA
  detection/tracking/evidence Observation Engine, hardened through repeated
  real field campaigns, with a default-off candidate-Visit authority mode;
  restart/recovery and durable monitoring lifecycle; admission/rejection
  observability (the July 30 cohort measured 10/10 promoted Visits as real
  birds); source-resolution evidence lineage; a self-contained Windows
  install bundle (Phase 27A); two real-hardware defects found and fixed in
  an earlier field session (Camera Node pairing repair, and an
  Observation/live-view capture-ownership collision); the Visit Continuity
  fix for the candidate-004/005 fragmentation defect; Review Decision
  Provenance / Truth Boundary v1 (see
  [review-decision-provenance-contract.md](review-decision-provenance-contract.md)),
  which closed the real truth-boundary gap that same defect's own audit
  found -- `ReviewLabel` now carries durable, model-neutral provenance, and
  a non-human diagnostic assessment can no longer silently become reviewed
  Observation truth, reviewed-only export truth, or training-eligible truth;
  Localization Attribution / Detection Geometry Lineage v1 (see
  [localization-attribution-contract.md](localization-attribution-contract.md)),
  which traced why 004/005 and a 2026-08-11 recurrence (007) each showed a
  real bird with a persisted box that missed it, added bounded raw-geometry
  lineage from detection through to the persisted MediaAsset, and added a
  deterministic diagnostic to classify a future localization failure --
  live-verified on the real deployed build and, in a fuller 2026-08-11
  45m47s live session run specifically to exercise it, correctly produced
  `detector_off_target` and `tracker_drift` (with a real measured drift
  distance) on real per-observation geometry for the first time, though
  that session's own 2 admitted candidates were both false positives (a
  midday dappled-shadow confusor family) with 0 genuine-animal encounters,
  leaving the diagnostic's own A-vs-B question (for a real bird, is an
  off-target box a raw-detector fault or a tracker/evidence-timing fault)
  still unanswered pending a session that actually admits one; and
  Rejected / Suppressed Detection Attribution v1 (see
  [rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md)),
  which closed the complementary gap that same 45m47s session's own
  disclosed incidental finding exposed -- a real bird visible in one
  candidate's evidence imagery, structurally unconnected to that
  candidate's own track, whose own detection/tracking/suppression history
  was unrecoverable because a live session's rejected-proposal facts were
  discarded rather than retained. A bounded, local-only, per-session
  counterfactual ledger (raw detector output, track-generation outcomes
  including ones the tracker itself never confirmed, and every admission
  outcome with full lineage) plus a deterministic attribution diagnostic
  and a read-only ROI/time-window query API now make that question
  answerable for the next real bird -- retrospective analysis of the
  2026-08-11 session itself honestly remains `insufficient_counterfactual_
  lineage`, since the ledger did not exist yet when that session ran; and
  Admission Recall Investigation + Conditional Fix v1 (see "Ambiguous
  boundary arbitration" in
  [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)),
  which used that same counterfactual ledger -- live-queried from a real,
  still-running ~94-minute accepted daily-use session's own process --
  to answer a distinct field-quality question the prior milestone
  deliberately left open: the human observer saw more genuine wildlife
  activity than MockingBird surfaced as Visits. New encounter-level
  accounting found a real, demonstrated admission-lifecycle defect:
  `blocked_ambiguous_boundary`, unlike `blocked_continuation_pending`, was a
  genuinely permanent verdict with no recovery path at all -- including for
  a confirmed detection above `strong_detection_threshold` whose 1.7s-gap,
  near-identical-geometry sibling made the pair ambiguous, and for a
  cleanly-merged 14-generation episode that inherited an ambiguous link
  from its own first constituent generation and stayed permanently blocked
  even after absorbing 13 further unambiguous merges. A bounded,
  deterministic arbitration mechanism now lets the single best-evidenced,
  fully-stabilized member of an ambiguous cluster be admitted while every
  other member still correctly blocks -- at most one Visit per cluster, the
  original duplicate-Visit protection fully preserved. A real-data before/
  after replay of the exact motivating field pair confirmed the fix
  (0.795-confidence proposal: `blocked_ambiguous_boundary` ->
  `create`; its 0.590-confidence sibling: unchanged, still blocked). A
  fresh ~94-minute field acceptance of the deployed fix ran clean and
  stable end to end (zero errors, zero reconnects needed) but stayed quiet
  (no confirmed tracking reached, so the new arbitration path was not
  naturally re-exercised live) -- an honest, disclosed limitation of a
  real, unpredictable backyard window, not a defect.
- **v0.1 Product Flow Gap Pass v1** (2026-08-18) audited the working
  product from a new/ordinary user's perspective across all seven required
  journeys (first meaningful use, Today, Visit/evidence, confirmation/
  correction, Bird Log/history, monitoring/health, responsive/
  accessibility) against real persisted field-session data at desktop and
  narrow widths. Found and fixed one P0 truthfulness defect and three P1
  usability defects, all with focused regression tests and zero measured
  regressions: (1) `GET /api/dashboard/summary`/`GET /api/product/health`
  never consulted `ObservationEngineSessionManager`, so `ProductHealthPanel`'s
  always-visible "Observing X of Y cameras" line and `TodayReportPanel`'s
  empty state undercounted a genuinely, successfully observing Camera Node
  Stream and could show "Monitoring hasn't started yet" while it already
  had -- fixed by reading the same side-effect-free engine status Stream
  Detail's own Observation panel already uses; (2) Stream Detail's "Stream
  events" list was completely unbounded and oldest-first (a real 235-event
  Camera Node history rendered a 55,000+px page) -- bounded to 50 and
  reordered newest-first, matching the sibling "Recent Visits" section's
  already-correct convention; (3) the Analytics/Insights page's Dataset QA
  panel rendered its full, unbounded issue list (420 real issues measured,
  51,000+px) -- bounded to 50 with an honest "N of M total" disclosure,
  aggregate counts unaffected; (4) a narrow-width (≤640px) CSS overflow cut
  off Stream Detail's live-camera placeholder/heading text on a real
  375px viewport -- fixed with `max-width: 100%` at the existing
  breakpoint. A handful of P2 cosmetic findings (redundant species-name
  display, an always-expanded advanced-provenance panel, minor nav/label
  polish) were documented and deliberately left unfixed as
  disproportionate to this bounded pass. See
  [v0.1 product-flow findings](v01-product-flow-gap-pass-v1-findings.md)
  for the complete audit record.
- **Camera Node Installer / Package / Reboot Hardening v1** (2026-08-18)
  closed the last structural gap in "the real Camera Node path": until
  this milestone the only way to run a Camera Node unattended was a
  developer hand-assembling a `systemd` unit over SSH (exactly what had
  quietly accumulated on the project's own real Pi 4 reference device
  across several earlier field sessions). It added a reviewed,
  reproducible install/service/OS-supervision path
  (`scripts/install_camera_node.py`; dedicated `mockingbird-node` service
  account with only the `video` group -- empirically proven sufficient by
  inspecting a real running process's open device file descriptors;
  bounded-restart `systemd` unit; root-only `EnvironmentFile=`;
  `StateDirectory=`-backed pairing persistence; a deterministic,
  log-level-independent startup diagnostic closing a real gap where
  uvicorn's own startup confirmation was silently suppressed by the
  Node's conservative default log level), hardened
  `scripts/build_camera_node_artifact.py` with git-commit provenance and a
  clean-tree reproducibility guard, and added the real-OS-process/real
  -TCP-socket smoke test the existing suite never had. Installed for real
  on the project's actual Pi 4 reference device -- adopting its
  pre-existing ad hoc install in place -- with a real functional PiCamera2
  capture proven through the new hardened service identity, and paired
  with the actual MockingBird host through the real guided camera-repair
  flow (not a synthetic path), preserving the existing Source/Stream/
  Zone/history exactly as its own preview promised. A live reboot
  experiment, run with a genuine Observation Engine session actually
  running against the paired Node, found a real defect: the host's
  `AnalysisStreamRetryPolicy` gave up (`stopped_reason=
  "camera_unavailable"`) after only ~38 seconds of real session time,
  while the same Pi took a measured ~55 seconds to become healthy again
  after a normal reboot -- because a fully unreachable Node fails each
  retry attempt in about a second rather than the ~10-second batch
  duration the old 2.0-second backoff was implicitly sized against, an
  assumption that only held for a merely *degraded* connection, not a
  genuinely offline one. Raising `backoff_seconds` to 12.0 (leaving
  `maximum_consecutive_failures` and the bounded-retry shape untouched)
  restored the "~70-90 second" budget already documented as this policy's
  design intent, and a second real reboot with the corrected build
  redeployed confirmed it directly: the host reconnected successfully
  (`camera_connected: true`) without exhausting its budget. Real crash
  (`kill -9`), clean-restart, and network-interruption (a surgical `nft`
  rule dropping only the Node's own LAN port, never touching the device's
  sole WiFi interface or its SSH control channel) acceptance all passed:
  pairing state survived byte-identical across every event, `systemd`
  correctly distinguished a genuine crash (`Failed with result 'signal'`,
  `Restart=on-failure` firing) from a normal restart (`Result=success`,
  restart counter unchanged), and the host's corrected reconnect logic
  recovered from the network interruption without manual intervention or
  re-pairing. See
  [camera-node-installer-design.md](camera-node-installer-design.md) for
  the complete design, real-hardware findings, and exact measurements, and
  [observation-session-renewal-continuity-contract.md](observation-session-renewal-continuity-contract.md)
  for the retry-policy fix. This closes "sustained operation" and
  "restart/recovery" for the Camera Node path specifically; the phase's
  broader "representative field acceptance" (admission precision/recall,
  detector quality) remains separately open, below.
- **BioCLIP Status / Review Queue Performance v1** (2026-08-18) fixed a
  severe pre-existing performance defect that real packaged Windows/GPU
  acceptance for the preceding v0.1 Release Hardening v1 milestone
  exposed: with BioCLIP enabled and a real ~87-item review backlog, `GET
  /api/dashboard/summary` took up to 119.5 seconds. Root cause:
  `_review_identification_summary_for_item` independently re-resolved the
  entire model-adapter registry (`_model_adapters()`, which validates
  BioCLIP's local model bundle, embedding cache, and runtime packages from
  scratch) from three separate internal call sites per review item, plus
  a fourth Stream-pack-scoped BioCLIP call -- on the order of ~200
  `get_bioclip_status()` calls in one Dashboard request, confirmed by
  hermetic profiling to scale linearly (19/69/152/292 calls for
  5/20/45/87 items). `_ReviewAdapterStatusContext` resolves this once per
  bounded repository operation (`_review_queue_items`, the bulk species-
  suggestion batch preflight) and threads it through, rather than once
  per item -- a per-call convenience object, never a process-level cache,
  so a fresh operation always re-resolves current status. After the fix,
  hermetic call count is a flat 2 regardless of backlog size, and a
  byte-for-byte diff of every review item's identification fields across
  a 41-item backlog is identical before/after. Real packaged Windows/GPU
  acceptance, same real userdata/87-item backlog, same starting commit
  before and fixed commit after: `GET /api/dashboard/summary` dropped
  from a measured 50.0 seconds to 1.96 seconds (25.6x), with BioCLIP
  still reporting `available`/`runtime_available=true`/`can_run=true` and
  the species-suggestion path functioning correctly on real data
  throughout. See
  [bioclip-review-queue-performance-contract.md](bioclip-review-queue-performance-contract.md).
- **v0.1 Observational Quality Closure v1** (2026-08-18/19) asked the one
  question every prior Phase 1 field-acceptance session had left open: not
  "do the Visits MockingBird creates look good" but how often it actually
  notices a real animal, turns it into a usable Visit, and offers an
  appropriately accurate (or abstaining) species suggestion. Built an
  independently-adjudicated (agent-diagnostic visual review, disclosed
  non-authoritative, box-verified via zoomed full-resolution crops, never
  claimed as reviewed truth) real-evidence denominator from the real paired
  Camera Node's own accumulated evidence: 70 admitted candidate Visits
  across four real days (2026-08-14/16/17/18), including a
  previously-unrecorded real ~5.5-hour daytime session that had not yet
  been analyzed. Found and quantified a real, material admission-
  **precision** gap distinct from the admission-recall gap Admission Recall
  Investigation + Conditional Fix v1 already closed: after a disclosed
  self-correction (a first-pass visual review left 15 cases ambiguous on
  crops too soft to safely call; a second, sharper recheck pass resolved
  every one, and the honest, less flattering result is reported here)
  **slightly over half -- 52.9% (37/70) -- of admitted Visits in this
  large, non-session-concentrated cohort show no animal at all**,
  geometrically clustering into 6 recurring static scene confusors (a
  roof/chimney shadow, a feeder-silhouette texture, driveway/grass edges)
  covering 76% of the false positives, not diffuse noise. Swept real
  persisted detector confidence against this ground truth and found **no
  threshold gives an acceptable trade-off** (the prior smaller-cohort "best"
  point, 0.3, rejects only 27% of false positives while losing 18% of real
  animals) -- the first cohort ever large/representative enough
  (`detection-quality-accounting-contract.md`'s "Production authority gate"
  condition 1) to answer this, and the answer is negative: confidence-gated
  admission is not adopted; see that contract's own updated gate section.
  Species-suggestion confidence (BioCLIP) is a real but weaker-than-first-
  measured signal for the same question -- five of eleven false-positive
  Visits with a suggestion still carry a ≥0.9-confidence species label.
  Rigorous geometry-formula-consistent clustering (reusing
  `visit_episode_assembler.boxes_geometry_compatible` directly) found
  **zero duplicate/fragmented Visits** in the same 70-Visit cohort,
  confirming Visit Continuity v1 holds at real, larger scale. A fresh
  hard-negative/positive-control detector comparison (real GPU inference,
  both models re-run full-frame from scratch against 6 freshly-discovered
  real confusors plus 5 real positive controls) found production MDv5
  rejects 5/6 cleanly versus RF-DETR Stage-2's 1/6 (whose own dominant
  false-positive mode here was a parked vehicle, a different confusor
  family, confirmed by direct visual inspection) -- a second, independent
  line of evidence confirming
  [detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md)'s
  state A; no promotion. A real resolution-aware species-inference
  comparison (executed for the first time) found conservative 2x
  interpolation is a no-op relative to its own base image in every one of 8
  real cases, and 4x downsample-then-recover measurably degrades results in
  6/8 -- confirming existing doctrine rather than motivating a new
  enhancement stage; separately found, and disclosed without acting on it
  (n=1 ground truth), that the one human-reviewed case classifies correctly
  from the lower-native-resolution same-frame asset but incorrectly from
  the higher-native-resolution identification-burst asset, most likely a
  capture-timing/pose-alignment effect worth a future species-quality
  milestone. No narrow, deterministic code fix was found for the
  admission-precision gap -- a persistent, cross-session, per-Stream
  recurring-geometry confusor-suppression capability does not exist today
  and is a real, scopeable next milestone, not a rushed policy patch. See
  [observational-quality-closure-v1-report.md](observational-quality-closure-v1-report.md)
  for the complete evidence and every number. Decision: **B -- one bounded
  observational defect remains** (admission-precision/confusor-suppression);
  genuine encounter recall, Visit-continuity correctness, detector choice,
  and resolution-aware species decisions are all confirmed sound by fresh,
  independent evidence.
- **Persistent Scene Confusor Suppression + Recall-Safe Field Validation v1**
  (2026-08-19) closed the admission-precision gap the milestone above left
  open. Independently re-derived five of that milestone's own six named
  confusor clusters from real box geometry alone (several matching to two
  decimal places) without reading the original per-event labels first; the
  sixth ("second feeder-adjacent spot... several high-confidence House
  Finch") did not reproduce as a clean cluster on fresh, independent
  re-examination -- it is a genuinely popular real feeder-perch location
  with substantial real bird activity intermixed, exactly the "bird near
  feeder silhouette" special case this milestone's own governing
  constraints warn about by name, now directly evidenced rather than
  hypothetical. Compared raw detector confidence, motion/track
  displacement, geometry persistence, and evidence-crop behavior explicitly
  and found none of them separates real from false at the single-detection/
  single-track/single-Visit level; the first stage that does is
  cross-session recurrence of near-identical geometry with bounded spread,
  which is why the fix lives at admission rather than the detector,
  tracker, or evidence-scoring stage. Added one new pure decision module
  (`mockingbird.observation.scene_confusor`) and one new durable, per-Stream
  table (`scene_confusor_regions`, schema 34): a candidate whose own
  persisted evidence geometry closely, repeatedly matches a region this
  Stream has produced many prior admission attempts from, without ever
  being confirmed a real animal by reviewed truth, is suspected and blocked
  -- a third, sibling check alongside the existing `blocked_privacy_zone`.
  A naive occurrence-count-only version was built and replay-tested first,
  and found a genuine, demonstrated recall hazard (a real bird near an
  unrelated, coincidentally-nearby false detection could be wrongly
  suspected); fixed with a geometry-spread requirement justified by real
  measured numbers (confirmed-false regions stayed under 0.0045 spread; a
  real popular perch reached 0.0524 by its 15th occurrence). A second,
  steady-state stress replay then found that fix's relative confidence
  escape alone still insufficient for one narrow real case; fixed with a
  second, absolute escape reusing this codebase's own already-established
  `strong_detection_threshold`. A real, faithful, end-to-end replay of the
  actual implemented mechanism against the full historical 70-event cohort
  found **zero real Visits incorrectly suppressed**, both cold-start (real
  57.1% -> 53.8% false-Visit rate) and steady-state (35.0% of recurring
  false positives caught). A fresh ~98-minute live field session against
  the real Camera Node then ran the mechanism continuously with zero
  interference against 6 real, cleanly-admitted candidates and zero
  scene-confusor firings of its own; a forward-looking simulation on that
  session's own real geometry both confirmed a fresh, concrete confusor
  example (19/132 real events, one tight low-confidence region) and
  honestly surfaced one disclosed boundary-tolerance case at a busy real
  perch, never live-witnessed crossing into unsafe territory. The same
  fresh session, exactly as intended, also surfaced two findings beyond
  this milestone's own scope: two long (5.0/8.67-minute), high-confidence
  (0.889/0.846), heavily-tracked real-seeming encounters were completely
  missed for reasons unrelated to scene-confusor
  (`blocked_ambiguous_boundary`/evidence-admission gates, not this
  milestone's mechanism), and a significant independently-discovered defect -- a global,
  cross-session, silently-exhaustible candidate-visit authority budget with
  no UI signal and no reset path -- had to be diagnosed and worked around
  (zero code change: the existing Stop/Start product action resets it)
  before the field evidence could be trusted. See
  [scene-confusor-suspicion-contract.md](scene-confusor-suspicion-contract.md)
  for the complete mechanism design and real-data justification and
  [scene-confusor-suppression-v1-report.md](scene-confusor-suppression-v1-report.md)
  for the complete field evidence and every number. Decision: **B --
  precision improved but recall/confusor work remains** -- scene-confusor
  suppression itself is fully evidenced as recall-safe at every layer
  (replay and live), but the fresh field validation this milestone required
  surfaced a further, different, bounded observational-quality gap (missed
  high-confidence encounters via a different admission-gate family) that
  keeps the broader phase from closing yet.
- **Remains for this phase:** a 2026-08-10 real end-to-end Camera Node
  session (25.3 minutes, the two just-fixed paths holding up cleanly)
  proved the structural path but found admission *precision* is not yet
  trustworthy -- all 3 candidate Visits created were false positives (bare
  tree bark, empty grass, the hummingbird feeder itself), root-caused to
  detector confidence never being consulted by either admission gate. That
  same day's Detection Quality Accounting v1 milestone (see
  [detection-quality-accounting-contract.md](detection-quality-accounting-contract.md))
  added the measurement/shadow-evaluation infrastructure this needs but
  did not change production admission behavior, pending a larger, less
  session-concentrated reviewed cohort (see that contract's "Production
  authority gate"); the July 30 cohort's separately-measured insufficient
  admission *recall* also still needs resolving -- Admission Recall
  Investigation + Conditional Fix v1 (above) closed one demonstrated,
  bounded piece of this (the permanent `blocked_ambiguous_boundary`
  mechanism), but did not re-open detector recall, evidence-quality
  rejection, or tracking-confirmation recall, all of which remain
  separately open; bounded CPU/RAM/storage
  behavior and truthful capability reporting against representative
  unattended field conditions remain unverified beyond shadow/synthetic
  benchmarks. A 2026-08-11 fresh field session then reproduced a sharper,
  more specific finding: a genuine, visible bird's persisted candidate box
  had zero IoU overlap with it -- the second independent session to show
  this (after 004/005) -- while that same session's one false positive sat
  at a confidence (0.544) too high for a confidence floor to plausibly
  reject, directly undermining the confidence-gating hypothesis. Localization
  Attribution / Detection Geometry Lineage v1 (see
  [localization-attribution-contract.md](localization-attribution-contract.md))
  answers the resulting open question precisely: geometry lineage (raw
  detector boxes, tracker-support-vs-detector provenance, and whether a
  persisted evidence image provably represents the same moment as the box
  drawn on it) now survives from detection through to the persisted
  MediaAsset. Tracing this path found the box a reviewer sees, for any real
  live Camera Node candidate, always comes from a high-resolution evidence
  burst captured measurably *later* than the triggering detection -- a
  concrete, previously-undetected mechanism consistent with (not yet
  proven as the sole cause of) both known off-target cases. A bounded
  10-minute live smoke against the real deployed build confirmed the new
  lineage code runs correctly on real hardware (387 track updates, 217
  evidence candidates, zero errors) but produced no fresh admitted
  candidate to exercise the new fine-grained diagnostic against a genuine
  sighting -- the honest, disclosed outcome of a deliberately short window,
  not a defect. Observational Quality Closure v1 (above) then added a real,
  quantified admission-**precision** finding distinct from all of the
  admission-recall work above: slightly over half of real admitted Visits in
  a large, non-session-concentrated cohort are false positives from a small
  number of recurring static scene confusors, and confirmed on that larger
  cohort that confidence-gated admission is not a safe fix for it, whether
  measured from raw detector confidence or species-suggestion confidence
  (see that milestone's own report for the swept thresholds). No narrow,
  deterministic code fix was found that closes this without a larger
  initiative -- left open deliberately at the time. **Persistent Scene
  Confusor Suppression + Recall-Safe Field Validation v1 (above) has since
  built, replay-validated, and field-validated exactly that capability** --
  a persistent, per-Stream, cross-session recurring-geometry
  confusor-suppression mechanism, bounded like the existing counterfactual
  ledger, fails closed, and shown recall-safe by real historical replay
  (zero real Visits incorrectly suppressed, cold-start and steady-state)
  plus a real ~98-minute live field session (zero interference with 6 real
  admissions, zero scene-confusor firings of its own). What that same fresh
  field session's own required independent validation surfaced instead is
  the new concrete next gate: two long, high-confidence, real-seeming
  encounters completely missed for reasons unrelated to scene-confusor
  (`blocked_ambiguous_boundary`/evidence-admission gates, the same general
  admission-lifecycle family Admission Recall Investigation + Conditional
  Fix v1 previously and only partially closed) and one encounter that
  fragmented into three separate admitted Visits -- both using this
  session's own two concrete, evidenced examples as starting material for
  the next Observational Quality milestone, plus a significant,
  independently-discovered candidate-visit authority budget defect (global,
  cross-session, silently-exhaustible, no UI signal, no reset path) that
  should be addressed alongside it since it directly threatens any future
  field-session methodology, not just this one.
- **Explicitly deferred:** Phases 2 and 5-8 below do not start in earnest
  until Phase 1's exit gate is met, except where already-shipped Phase 3/4
  capability (Today in Your Yard v1, Phase 27A packaging) or Phase-1-
  motivated Detection Quality Accounting v1 / Localization Attribution v1 /
  Rejected / Suppressed Detection Attribution v1 infrastructure made
  opportunistic progress -- see "Phase sequencing."
- **Most recent detector decision:** the 36m11s combined-attribution session
  produced four genuine bird encounters, three with proof-complete raw MDv5
  misses. Detection and Localization Model Benchmark / Promotion v1
  ([contract](detector-promotion-benchmark-contract.md),
  [report](detector-promotion-benchmark-report.md)) then ran exact production
  MDv5, accepted MDv5 tiling, MDV6-C/E, and RF-DETR Small against 70
  human-reviewed localization frames plus five strictly diagnostic images on
  the Windows-hosted RTX 4060 Ti. It selected state A -- MDv5 native retained
  -- because no challenger dominated the incumbent and tiling created
  unacceptable false positives/runtime. The live misses remain valid;
  production and threshold 0.1 are unchanged.
- **Next recommended implementation milestone:** have a human independently
  review and box the four latest attributed birds; add a new multi-scene,
  non-session-concentrated holdout with deliberate small/distant birds and
  surviving environmental confusors; and retain exact live analysis-frame
  bytes plus raw detector output in future field capture. Then rerun calibrated
  MDV6-C/E comparison on that frozen holdout and proceed to a bounded,
  default-off live shadow only if a challenger clearly dominates. This is the
  exact next gate recorded by
  [detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md);
  the holdout remains prohibited from training.

## Phase sequencing

A later phase may already have partial, opportunistically-shipped capability
(noted where applicable) without changing which phase currently governs
prioritization -- that remains the lowest-numbered phase whose exit
condition is not yet met.

### Phase 1 -- Trustworthy Single-Site Observatory (current)

Finish/prove: real Camera Node path, native runtime direction, sustained
operation, restart/recovery, truthful health/capability reporting, bounded
CPU/RAM/storage behavior, admission/rejection observability, representative
field acceptance, coherent Visits, useful evidence, correct source-resolution
lineage, durable review/correction truth.

Largely proven: the real Camera Node path, now including its own
OS-level install/service/reboot/crash supervision (Camera Node Installer
v1, above) alongside the previously-proven application-level restart/
recovery; the native ONNX Runtime CUDA detection/tracking/evidence
pipeline with verified CUDA-only execution; admission/rejection
observability (July 30 cohort); source-resolution lineage; durable
review/correction truth. Three real defects found through live use are
fixed: Camera Node pairing repair, an Observation/live-view
capture-ownership collision, and (Camera Node Installer v1) a host
reconnect-retry budget that gave up before a rebooting Pi could recover.

Still open: representative field acceptance has been mixed -- the first
campaign failed on admission precision, a later cohort passed precision with
insufficient recall, and tracker fragmentation took several real rounds of
fixes to bring under control. The combined-attribution session exercised current continuity and lineage on
four coherent genuine-bird Visits, but three proof-complete raw-detector
localization/recall failures leave animal detection quality unresolved. Truthful capability
reporting covers only a narrow "no runtime available" case today (see
"Capability-aware UX" in [architecture.md](architecture.md)). Bounded
CPU/RAM/storage behavior is declared (see the former Gate E budgets, below)
but not exhaustively verified under representative unattended field
conditions.

The former "Phase 24 hardening" Gates A-F are superseded by this exit gate
and by [development-workflow.md](development-workflow.md)'s validation
tiers. Gates A and D are substantially fulfilled by development-workflow.md
itself and by the entire Observation Engine v2 benchmark suite
(architecture.md), and Gate B is substantially fulfilled by the existing
Playwright suite (`web/e2e`: onboarding, the reviewed product loop, camera
controls, the Observation panel). Gate C (targeted architecture seams) is an
ongoing practice, not a one-time gate. Gate E's resource/failure budgets are
declared but not exhaustively field-verified -- part of "still open," above.

Exit condition: one representative installation can run for days and create
trustworthy useful history without developer babysitting.

### Phase 2 -- Detection Quality & Model Lifecycle

Build: stage-level quality accounting, representative benchmark, rejection
audit, difficult-case slices, incumbent/candidate comparison, calibration,
abstention, model/version provenance, shadow evaluation, promotion/rollback
rules.

Not formally started as a phase, but substantial reusable infrastructure
already exists: a deterministic detector calibration/precision-recall
benchmark, a shadow-only incumbent-vs-candidate comparison tool (already used
to reject the `spruce` MegaDetector candidate on measured precision/recall
and licensing grounds), multi-scale and adaptive motion-proposal benchmarks,
an evidence-usefulness benchmark, and the shadow-evaluation discipline the
whole Observation Engine migration was built on. Detection and Localization
Model Benchmark / Promotion v1 then added a checksum-pinned provider-neutral
candidate runner, a 75-image provenance-aware corpus (70 reviewed plus five
diagnostic-only), exact MDv5 native/tile controls, MDV6-C/E and RF-DETR-S
challengers, a Windows GPU resource pass, and A-E promotion states. It selected
state A without changing production; see
[detector-promotion-benchmark-contract.md](detector-promotion-benchmark-contract.md)
and [detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md).
Detection Quality Accounting v1 (2026-08-10, see
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)),
motivated by that day's real-field finding that all 3 candidate Visits one
Camera Node session produced were false positives, added confidence/evidence
lineage from detection through assembled Visit proposal (previously
discarded at proposal assembly), a bounded six-stage accounting report, and
a SHADOW-only confidence-aware admission-policy evaluator measured against
51 real reviewed historical examples (17 true positives / 33 false
positives / 1 ambiguous, across 4 sessions) -- see "Detection Quality
Accounting" and "Formal model lifecycle" in [architecture.md](architecture.md).

Remains: organize this prior art into the explicit 14-stage accounting in
architecture.md instead of ad hoc benchmarks; build representative
difficult-case slices as a standing structure (common/uncommon/unknown
species, partial/occluded animals, multiple animals, small/distant subjects,
feeder obstruction, motion blur, poor lighting/dawn/dusk, non-birds, empty
backgrounds); implement abstention, which does not exist anywhere in the
pipeline today; add classifier-side calibration; wiring Detection Quality
Accounting into a *live* session (rather than only an offline pass over
already-recorded facts) is now partially done for admission outcomes via
Rejected / Suppressed Detection Attribution v1's counterfactual ledger
(see [rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md));
collect a larger, more representative (not
session-concentrated) reviewed cohort before any confidence-aware admission
policy could satisfy detection-quality-accounting-contract.md's "Production
authority gate"; extend the v1 promotion-state rule into versioned
deployment, monitoring, and rollback/retirement policy; and collect the
representative (30-100 example) species-level correction truth needed to
actually validate BioCLIP -- never completed under the earlier "visual
species identification" priority -- before deciding production selection or
its abstention/calibration policy.

Exit condition: we can explain quantitatively where the vision pipeline is
good, where it fails, and whether a candidate actually improves the product.

### Phase 3 -- Observation & Today in Your Yard Product Loop

Deepen: Observation semantics, Today in Your Yard, best moments, new/regular
visitors, review, evidence/confidence explanation, corrections, first/last
seen, useful history.

Partially delivered: Today in Your Yard already ships as the Dashboard
center -- detector-qualified animal Visits, reviewed discoveries, best
evidence-backed moments, Zone/hour context, bounded confirmation work, and
compact observation health.

Remains: reframe review/history around Observation as the durable semantic
object (see product-doctrine.md and the naming note in glossary.md) rather
than reviewed-Visit framing; first/last seen; new-versus-regular visitor
distinction; plain-language evidence/confidence explanation; deeper
corrections UX; Phase 26C/26D audio and multi-signal ranking.

Exit condition: opening MockingBird after being away for a day is
intrinsically useful even to someone who does not care about the underlying
ML/camera stack.

### Phase 4 -- Install / Recovery / Appliance Experience

Deliver: package/installer, automatic services, guided camera configuration,
safe upgrade, backup/recovery, storage management, understandable health,
golden-path setup, advanced controls available without dominating normal UX.

Partially delivered: Phase 27A ships a self-contained Windows "unpack and
run" bundle, a first-run setup wizard, and a consolidated product-health view
(see [local-product-packaging-design.md](local-product-packaging-design.md)).

Remains: native Windows hardware acceptance of the produced bundle (a
pending manual step outside this environment); automatic upgrade; guided
recovery; storage management as product-managed behavior rather than
developer tooling; accessibility. `scripts/deploy_windows_dev.py` stays
developer tooling only and is not this phase's product installer (see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md)).

This phase is the **MockingBird host's** own install/upgrade/recovery
experience only. The separate Camera Node edge device's own install/
service/reboot-supervision path (`scripts/install_camera_node.py`, a
`systemd` unit) is Phase 1 work, not this phase -- it finishes proving "the
real Camera Node path" is durable infrastructure (see "Current status,"
above, and
[camera-node-installer-design.md](camera-node-installer-design.md) "Phase
ownership" for why), not a second appliance-packaging initiative. The two
components have different product identities on purpose: the host is
local desktop software a user unpacks and double-clicks (no service
manager, by explicit product-identity decision -- see
[local-product-packaging-design.md](local-product-packaging-design.md)),
while the Node is a headless edge device meant to run unattended
indefinitely, an appliance in exactly the sense the host is not.

Exit condition: a technically competent non-developer can deploy MockingBird
without WSL, cloning GitHub, or understanding internal services.

### Phase 5 -- Place Intelligence

Not started. Add baselines, Zone/time preferences, meaningful changes,
returning/seasonal patterns, cautious anomalies, useful summaries, and
external ecological enrichment with provenance, once history is adequate to
support them.

Exit condition: the product becomes more useful as history accumulates.

### Phase 6 -- Mobile / Remote Convenience

Not started. Add Today, review, highlights, history, health, notifications,
and optional secure remote access, exposing the same authoritative local
Observation/history model rather than separate mobile truth semantics. Keep
cloud optional.

### Phase 7 -- Multi-Camera / Richer Wildlife

Not started, and explicitly gated behind stable single-camera Observation
semantics (Phases 1-3). Covers multiple cameras, camera-aware observations,
defensible duplicate handling, broader wildlife, behavioral proposals, and
richer habitat/Zone understanding.

### Phase 8 -- Learning / Contributor Ecosystem

Not started, and explicitly gated behind mature evidence and dataset
governance (Phase 2). Covers dataset creation, opt-in contribution,
candidate-model workflows, benchmark sharing, research exports, and broader
ecosystem integration.

## Explicit phase gates

- Do not broaden hardware integrations merely for coverage until at least one
  golden path is excellent.
- Do not promote a detector/classifier without reproducible incumbent
  comparison.
- Do not reduce abstention simply to produce more exact species labels.
- Do not turn model confidence into reviewed truth.
- Do not prioritize sophisticated behavioral interpretation before animal
  evidence, Visit coherence, and species-quality foundations.
- Do not prioritize multi-camera intelligence before stable single-camera
  Observation semantics.
- Do not prioritize NVR/live-video capability over useful history, review,
  evidence, and place understanding.
- Do not prioritize cloud architecture over local appliance quality.
- Do not build enterprise/fleet administration prematurely.
- Do not let unbounded field testing stall independent product development.
- Do not architect the product around the current Raspberry Pi even though it
  remains a primary validation adapter.

## Explicit deprioritization

Unless a specific task shows compelling near-term evidence otherwise, keep
these out of the critical path. This is the canonical, complete list; the
shorter identity-level version in
[product-doctrine.md](product-doctrine.md) "Product boundaries" is not a
second, separate inventory.

- NVR/security-platform expansion
- continuous-recording product focus
- elaborate live-view protocols for their own sake
- security alerts/person recognition
- broad camera integration counts as a goal
- mandatory cloud inference
- enterprise RBAC/fleet management
- social feeds
- gamification
- individual-animal identity
- premature behavior claims
- huge generic analytics dashboards
- plugin-framework construction
- model marketplaces
- broad smart-home automation

## Field-testing doctrine

Every extended field test should answer a bounded question -- for example
admission recall under a policy revision, Visit fragmentation over a defined
eligible sample, source-resolution crop benefit versus 1080p, restart
recovery under controlled failures, or classifier candidate ranking on a
representative cohort -- rather than "leave it running and see what happens"
as an indefinite roadmap phase. State the bounded question before starting;
see Tier 4 in [development-workflow.md](development-workflow.md). Independent
development continues whenever it does not depend on the unanswered field
question.

## Completed foundations

- Phases 0-6 established product doctrine, the universal product model, the
  stream-first UI, local/demo media, the detection evidence model, the bird
  feeder review vertical, and broader outdoor concepts.
- Phases 7-9 established optional evidence-only model adapters, zone-aware
  motion and MotionEvidence, species suggestions, reviewed classifier
  readiness, and local export/training boundaries.
- Phases 10-16 established product-level playback/provider contracts,
  explicit external URL and folder media flows, generic webhook metadata
  evidence, retention boundaries, MVP onboarding, and disabled worker metadata.
- Phases 17-18 improved evidence review and classifier-readiness drill-down.
- Phases 19-22 added explicit in-memory camera monitoring, browser/RTSP/local
  USB playback, backend-owned live camera sessions, Zone overlays, best-frame
  evidence, and optional identification assistance.
- Phase 23 began real feeder-camera validation, camera lifecycle cleanup,
  bounded diagnostics, field calibration, and optional local MDv5 proposal
  verification.
- Phases 24A-24D added the single local runtime, verified database-and-media
  backup/restore, durable lifecycle design, and inert default-off monitoring
  policy/runtime state.
- Phases 24E-24G added a durable live-continuity supervisor, explicit
  Stream-scoped live-video enabling, and bounded idempotent review handoff,
  without automatic truth creation.
- Phase 25 hardened restart recovery and storage/retention and ran the first
  representative field-acceptance campaigns; its unattended-operation goal
  now defines the Phase 1 exit gate, above.
- Phase 26A-26B added the optional local BioCLIP species-suggestion adapter
  and a default-off automatic post-activity assist; representative
  species-level correction truth to validate its accuracy remains
  uncollected (Phase 2, above).
- Phase 27A delivered first-run setup and a self-contained Windows
  "unpack and run" bundle; native Windows hardware acceptance and
  update/recovery polish remain open (Phase 4, above).
- Observation Engine v2 (Stages 1-7, Product Vertical Slice v1, Unified
  Observation Experience v1) replaced the timer-driven snapshot observer
  with a provider-neutral, evidence-only detection/tracking/evidence-scoring
  pipeline and one bounded, default-off candidate-Visit authority mode
  reachable through a per-Stream Start/Stop Observation control, hardened
  through repeated real Camera Node field campaigns.
- Two real-hardware defects found after the above were fixed: Camera Node
  pairing repair could reject a valid unconsumed code, and starting
  Observation could collide with an already-running legacy live-view session
  for the same camera.
- Camera Health and Guided Camera Editing expose saved operational state,
  safe in-place compatible camera configuration, redacted change previews,
  and bounded revision history without changing the evidence/review truth
  boundary.
- The optional MockingBird Camera Node is a paired local-LAN snapshot adapter
  beneath the same Source/Stream/Zone/monitoring/review loop. It remains
  no-cloud, no-discovery, and no-truth.

See [roadmap-history.md](roadmap-history.md) for the concise phase record.

## Cross-cutting roadmap invariants

- Source adapters remain underneath Sources, Streams, Zones, Activity
  Sessions, Visits, review/correction, analytics, and exports.
- MediaAssets, MotionEvidence, DetectionProposals, SpeciesSuggestions, and
  external labels remain evidence/context until explicit correction; unknown
  and abstained outcomes are valid, not defects.
- Read/status/preview/dry-run routes are side-effect free. Writes are explicit,
  scoped, bounded, and tested.
- Privacy and Ignore Zones, local storage, retention, backups, and safe restart
  behavior are first-class constraints.
- Workers and durable monitoring default off, are observable and safely
  stoppable, and cannot create reviewed truth.
- Model runtimes, training dependencies, generated datasets, captured media,
  benchmark artifacts, and caches require explicit scope and ignored local
  paths.
- A candidate detector/classifier does not gain production authority without
  reproducible incumbent comparison (Phase 2).
- Track engineering truth and user value as two distinct scorecards, and
  measure whether an algorithmic component earns its cost; see "Two
  scorecards" in [product-doctrine.md](product-doctrine.md).
- Each implementation task uses the task packet and validation tiers in
  [development-workflow.md](development-workflow.md).

## Roadmap non-goals

- No one-shot repository rewrite or coverage-percentage target.
- No cloud dependency or telemetry requirement for the core product.
- No new administration page merely for lifecycle or engineering controls.
- No provider, audio, camera-integration-count, or unrelated automation
  expansion ahead of the current Phase 1 gate without explicit evidence and
  scope; see "Explicit deprioritization," above, for the complete list.

## WSL activation checkpoint

The active development checkout is WSL-native at
`/home/zkelder/projects/mockingbird-active`. A locally configured Windows
`ffmpeg.exe`, native DirectShow controls, fresh live frames, and a daylight
3840 x 2160 capture have been verified from WSL, and the packaged
Windows/CUDA product has been run and debugged against real passed-through
GPU hardware from this sandbox. Driver-managed exposure values remain outside
MockingBird and are neither readable nor persisted. This checkout remains a
development environment fact, not a product architecture constraint -- see
"Do not architect the product around the current Raspberry Pi" and the
equivalent Windows-development caution in "Explicit phase gates," above.
