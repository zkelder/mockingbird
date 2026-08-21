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

## Governing priority for v0.1

Two different kinds of quality govern this product, and they do not carry
equal release weight.

**Trustworthy detection, encounter reconstruction, Visit correctness, and
evidence correctness must be highly reliable before v0.1.** A user must be
able to trust that MockingBird noticed the wildlife that was actually there,
represented it as a coherent Visit (or Visits, for genuinely separate
subjects), and preserved evidence that actually shows what happened.

**Species identification only needs to be useful, honest, calibrated,
abstention-capable assistance for human review.** Perfect species top-1
accuracy is not a v0.1 requirement; a confident wrong species is worse than
an honest "bird, species uncertain."

MockingBird will not spend months chasing another few points of species
top-1 accuracy while real animals are missed, one encounter becomes three
Visits, several simultaneous birds collapse into one subject, empty frames
become bird Visits, evidence points at the wrong frame, or processing delay
looks indistinguishable from a detection miss. See Gate A and Gate B in
"v0.1 release gates," below, for what this means operationally.

## Current status

- **Current phase:** Phase 1 -- Trustworthy Single-Site Observatory (below).
- **Current exit gate:** one representative installation can run for days
  and create trustworthy useful history without developer babysitting.
- **v0.1 release-gate mapping:** see "v0.1 release gates," below, for the
  authoritative small gate set this phase's still-open work maps onto --
  principally Gate A (detection/encounter/Visit correctness, including the
  new multi-subject requirement) and part of Gate E (reliability/
  observability). Phase numbering below is preserved as historical record,
  not renumbered.
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
- **Visit Authority Budget + Ambiguous-Boundary Recall Closure v1** (2026-08-19)
  closed the candidate-visit authority budget defect the milestone above
  surfaced and investigated the two long, high-confidence, heavily-tracked
  encounters that same milestone's fresh field session missed. Root cause of
  the budget defect: `ObservationAuthoritySettingsModel` was a single global
  singleton row shared by every Stream, and `activation_boundary_at` reset
  only on an actual `shadow -> candidate_visit` mode transition -- so a
  process that never reached its own `stop()` kill switch (a crash, or a
  mid-session dev redeploy) left the row stuck at `candidate_visit` with a
  stale, possibly-already-exhausted boundary, and the next Start, even in a
  brand-new process, silently inherited whatever budget the "crashed"
  session had already spent. A related latent defect shared the same root:
  session/hourly count queries carried no `stream_id` filter, so one
  Stream's Stop could revert a *different*, still-running Stream's
  authority to shadow. Fixed by making the settings row and every query
  against it per-Stream (schema 35; every existing installation reverts to
  the safe `shadow` default on upgrade, which is also the direct fix for
  any stale stuck row) and resetting the boundary whenever a Stream's own
  Start path asserts a fresh session -- structurally safe, since a live
  in-process session for a Stream cannot call Start twice. A truthful
  `candidate_authority_exhausted`/message pair now surfaces in the basic
  Observation panel, not buried in advanced diagnostics, for the case where
  a Stream is genuinely observing but budget-exhausted. Reconstructing both
  missed encounters from the real 2026-08-19 session's own still-live
  counterfactual ledger found the ambiguous-boundary arbitration mechanism
  (Admission Recall Investigation + Conditional Fix v1) had worked
  correctly for both -- each cluster's best-evidenced proposal legitimately
  escaped ambiguity, then permanently failed
  `reject_no_identification_or_context` instead. The actual first
  irreversible loss stage was one layer downstream: resolving ambiguity
  legitimately delays a proposal's own admission attempt past its evidence-
  capture moment, and `engine_runtime`'s harvested-evidence cache was bound
  to only 8 entries with no awareness of which pending proposal still
  needed which bytes -- unrelated activity elsewhere in a busy real stream
  (9,363 raw detections that session) cycled the cache many times over
  within the legitimate delay window, and by the time the delayed attempt
  ran, its own already-captured bytes were gone. Raised the bound to 32
  (a bounded memory-footprint change, not an admission-threshold change);
  reproduced the exact real failure and fix directly with a focused
  regression test using the real generation/timing shape (RED against the
  old bound, GREEN against the new one). Replayed every required negative
  control unchanged: the original 0.795-confidence ambiguous pair, the
  existing fragmentation/duplicate regression suite, and the full historical
  70-event scene-confusor cohort (byte-identical cold-start/steady-state
  numbers) -- confirming both fixes carry zero precision regression. Built
  a new independent biological-encounter denominator
  (`mockingbird.observation.acceptance_recorder`) explicitly because the
  prior milestone's own field validation could not establish one -- a
  capability-safe tee inside the Engine's existing frame-processing loop,
  structurally incapable of becoming evidence (zero import path into the
  product repository or any admission-pipeline module), off by default. A
  fresh real 81m51s field session against the real Camera Node
  live-verified the budget fix directly (`activation_boundary_at` came up
  fresh 3 seconds after Start and never moved; `candidate_authority_
  exhausted` stayed false across all 84 status polls and 8 real admissions,
  nowhere near the default budget of 50) and used the new recorder for
  real, independent confirmation of two of those 8 admissions by full-
  resolution photograph, with zero admission independently contradicted --
  but also found a real defect in the recorder itself (its `max_total_
  bytes` default assumed ~200KB analysis frames; real frames measured
  ~801KB, so the byte bound stopped recording at 52 of 82 minutes, before
  the session's last three admissions -- now fixed with measured headroom).
  Zero false Visits, zero duplicates, zero fragmentation, and zero
  scene-confusor firings were found in this session by either lens. See
  [visit-authority-budget-recall-closure-v1-report.md](visit-authority-budget-recall-closure-v1-report.md)
  for the complete evidence and every number. Decision: **B -- budget
  defect fixed and live-verified; admission-recall fix needs one more
  bounded field session** -- the evidence-cache fix is soundly verified
  against the real reconstructed shape of both originally-missed encounters
  plus zero measured regression everywhere replayed, but this fresh session
  did not happen to produce another long, high-confidence encounter that
  traverses the exact ambiguity-then-delayed-evidence path the two original
  misses followed, so it still lacks a live proof point under real
  conditions -- no code change is expected to be needed first, only a
  matching real encounter with the recorder's coverage gap now fixed.
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
  field-session methodology, not just this one. **Visit Authority Budget +
  Ambiguous-Boundary Recall Closure v1 (above) has since fixed and
  live-verified the budget defect, and root-caused and fixed both missed
  encounters to an evidence-cache capacity gap one stage downstream of the
  (correctly functioning) arbitration mechanism** -- soundly verified by
  synthetic reproduction of the real failure shape and zero regression
  across every replayed cohort, but not yet confirmed by a live encounter
  of the same shape at the time. **End-to-End Bird Encounter Recall
  Closure v1 (above) has since supplied exactly that live encounter --
  twice, with full counterfactual-ledger traces -- and found the fix's own
  32-entry bound was not yet enough under a busier real session's load;
  raised to 128 and RED/GREEN-verified against this session's own real
  failure shape.** The concrete next gate is now the *raised* bound's own
  live re-proof under real conditions (no code change expected first,
  exactly mirroring how this milestone was itself the live-proof follow-up
  for the fix that preceded it) -- plus, separately and at lower priority,
  the newly-diagnosed (not yet fixed) duplicate-Visit pattern from
  temporally-overlapping tracker generations, a known, deliberately
  conservative `visit_episode_assembler` design boundary rather than an
  undiscovered bug.
- **End-to-End Bird Encounter Recall Closure v1** (2026-08-19) asked the question every prior
  Phase 1 field-acceptance session had approached only indirectly: of the birds actually
  present in front of the real paired Camera Node, how many did MockingBird notice and turn
  into one truthful Visit? Built a genuinely independent biological-encounter denominator (a
  reconfigured, denser-cadence `acceptance_recorder` -- three new, individually optional env
  vars widen its cadence/bounds for one explicitly-scoped field session, unset for every
  ordinary process) and reviewed it *before* opening the product's own Visit list, correcting
  itself once already (a full-frame-only first pass missed a bird perched on a thin hook and
  birds mid-flight; a zoom re-pass, applied to every real candidate timestamp, recovered
  both -- the same "contact sheets -> crop sheets" lesson Observational Quality Closure v1
  first taught, independently re-confirmed). A real ~92-minute session (busier than every
  prior one: 21 candidates, 227 proposals, 1336 evidence candidates) produced a conservative
  22-genuine-encounter independent denominator (bird-only this session; no hummingbird
  sighting occurred). End-to-end recall: 15/22 (68.2%, a disclosed ceiling -- the one
  multi-visit cluster is counted at its conservative minimum) became a Visit; detector
  localization succeeded 17/19 lineage-available times (89.5%); every detector-localized,
  tracked subject went on to form a viable proposal (100%). Precision is now genuinely strong
  -- 2/21 created Visits independently confirmed false (9.5%), down from 52.9%/57.1% in the
  two immediately-preceding large cohorts -- and Scene Confusor Suppression v1 fired zero
  times against a third real session, continuing its clean recall-safety record. The dominant,
  quantified, *material* loss stage was not the detector (one clean miss, n=1) but evidence
  admission: this session's own required fresh field validation found and proved -- with full
  counterfactual-ledger traces and RED/GREEN regression evidence, not guesswork -- that the
  prior milestone's evidence-cache fix (`_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_
  BYTES`, 8->32) was *still insufficient* under this busier real session's own load: two
  genuine, strong (0.816/0.815 confidence), well-tracked birds, legitimately delayed by
  `blocked_continuation_pending` resolution (183.5s and ~34s), still lost their own
  already-captured evidence before their delayed admission attempt ran. Raised to 128 (the
  same relative 4x jump the original fix used, sized against this session's own measured
  evidence-candidate rate) -- disclosed as still a capacity bound, not a structural fix (a
  pending-proposal-aware eviction policy would close the gap for an arbitrarily busier session,
  left as a follow-up). Also found and diagnosed, but explicitly did not fix, two duplicate-
  Visit cases (one real sighting each producing 2-3 Visits, one with inconsistent species
  labels) traced to `visit_episode_assembler`'s own deliberate, documented non-merge of
  temporally-overlapping tracklets -- a known conservative design boundary this milestone's own
  governing constraints protect from casual change, not an undiscovered bug. See
  [end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
  for the complete evidence, the full encounter-by-encounter funnel, and every number. Decision:
  **B -- one bounded pipeline recall defect remains** -- found, evidenced, and fixed this same
  milestone (evidence-cache capacity), with the fix's own live re-proof (mirroring exactly what
  this milestone itself was the live-proof follow-up for) now the concrete next gate; detector
  quality and denominator methodology are both confirmed sound.
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
- **Detector-benchmark follow-up (a future detector-quality action, not the
  current top-priority next step -- see below):** have a human independently
  review and box the four latest attributed birds; add a new multi-scene,
  non-session-concentrated holdout with deliberate small/distant birds and
  surviving environmental confusors; and retain exact live analysis-frame
  bytes plus raw detector output in future field capture. Then rerun calibrated
  MDV6-C/E comparison on that frozen holdout and proceed to a bounded,
  default-off live shadow only if a challenger clearly dominates. This is the
  exact next gate recorded by
  [detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md);
  the holdout remains prohibited from training. It stays valid future work,
  but End-to-End Bird Encounter Recall Closure v1 (above, the chronologically
  latest milestone) found the detector was not this session's material loss
  stage (one clean miss, n=1, of 22 real encounters) and performed no
  detector-comparison work, so this is not queued ahead of the action below.
- **Current recommended next action:** one more real field session, now with
  the raised 128-entry evidence-cache bound in place, specifically to obtain
  a live (not only RED/GREEN-synthetic) proof point that the raised bound
  holds under real busy-session load -- mirroring exactly how the 2026-08-19
  session was itself the live-proof follow-up for the fix that preceded it.
  See "v0.1 release gates" (Gate A) below and
  [end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)'s
  own "Recommended next bounded step."
- **Camera Node Connectivity & Recovery Diagnosis v1** (2026-08-20) answered
  why the second (2026-08-20 daylight) cache-128 live-proof attempt above
  also failed: a real, external Camera Node/network outage (`analysis_
  stream_unavailable`, unrelated to the evidence-cache fix under test)
  after 4.08 genuinely healthy, busy minutes. The bounded reconnect/retry
  state machine itself was correct and not the cause -- but tracing the
  terminal `onnx_cuda_verification_insufficient` message the prior session
  had explicitly left unresolved found and fixed a real diagnostic defect:
  a session that lost its connection before any frame ever reached the
  detector still ran the detector's own end-of-session CUDA self-check on
  teardown, which could not tell "no inference ever ran" apart from a real
  CUDA failure, raised the same misleading code, and (via an unguarded
  teardown path) overwrote the already-correct connectivity diagnosis --
  sending the prior session down a GPU-investigation path for a problem
  that was never GPU-related. Also found and fixed, in the same teardown
  path: any exception from session teardown silently skipped `provider.
  close()` (a resource leak) and the finalize assembly tick. Doctor's
  Camera Node check was also found structurally blind to this lane's own
  runtime health (it only ever read the legacy `live_monitoring` lane's
  checkpoint table) and gained one small, read-only, additive freshness
  check. Decision D (diagnostic defect, now fixed); zero change to the
  reconnect/retry logic's own correctness or to the evidence-cache fix.
  Real bounded acceptance was not performed -- the shared Windows dev
  instance was independently confirmed unreachable this same session
  (consistent with a reported mid-session host reboot), so neither this
  fix nor Camera Node reachability itself could be live-verified yet. See
  [camera-node-connectivity-recovery-diagnosis-v1-report.md](camera-node-connectivity-recovery-diagnosis-v1-report.md).
  The next cache-128 attempt should still confirm Camera Node reachability
  independently before committing another long session -- this milestone
  improved diagnosis for the *next* failure, it did not make the Camera
  Node itself more available.
- **Camera Node Field Hardware Resilience / Bad-Boot Recovery (roadmap
  amendment, 2026-08-20).** The same day, physically checking the Pi 4
  reference device (the next action the diagnosis above recommended) found
  the concrete failure case that diagnosis had only inferred from logs: a
  solid red power LED, no green ACT activity, and the device completely
  absent from the LAN -- `192.168.1.112` failed ICMP, TCP 8787, and
  `/node/v1/health` alike -- while the Windows host and MockingBird product
  stayed healthy throughout, and six bounded reconnect attempts correctly,
  honestly classified the failure as `timeout` (among the bounded
  `connect_refused`/`connection_reset`/`dns_unresolved`/`http_status`/
  `content_type_mismatch`/`os_error` vocabulary that milestone added). With
  the earlier `onnx_cuda_verification_insufficient` misclassification
  already fixed, nothing downstream was misdiagnosed this time -- the
  diagnosis pointed at the node, and the node was in fact the problem.
  Only a physical power cycle recovered the device; no software action
  could have, and none claimed otherwise. This is direct field evidence of
  a genuinely new case -- **powered but never successfully booted** --
  distinct from every previously-tested reboot/crash/network-interruption
  case, all of which assumed the device eventually comes back on its own.
  This is a planning amendment, not a code change: it adds one bounded
  governing requirement, beneath the existing Gate D and Gate E, for
  Camera Node field-hardware resilience -- automatic recovery from
  controllable failures, honest exposure of uncontrollable ones, durable
  host-side truth through node failure, and straightforward
  reprovisioning/replacement. See the new subsections under Gate D and
  Gate E, below, the new cross-cutting invariant, below, and the extended
  "v0.1 non-blockers," below, for what stays explicitly deferred.
- **Independent Power / Node Supervisor + Solar/Battery Field Profile
  (roadmap amendment, 2026-08-20).** Same-day follow-up to the bad-boot
  amendment above: makes explicit what "External recovery boundary" (Gate
  E) and the "Power / solar" lane (Post-v0.1 lanes) already gestured at but
  never stated -- when an external power supervisor counts as genuine
  independent recovery rather than another single point of failure, and
  how that concept connects to remote, solar, battery, and PoE field
  deployments. Planning-only: no code change, no new gate, no new v0.1
  requirement. See "Independent Power / Node Supervisor" under Gate E and
  the extended "Power / solar" lane, below.
- **Cache-128 Live Daylight Acceptance v1 (2026-08-20) closes the "current
  recommended next action" above.** After the Camera Node recovery blocker
  was cleared (bad-boot amendment above, then a clean post-power-cycle
  short proof), a real 90m23s daylight field session on the raised
  128-entry evidence-cache bound produced a materially busier cohort than
  the 32-entry-era reference (289 vs. 227 proposals; 250 delayed-handling
  suppression events). Direct, repeated, same-session evidence that
  previously-harvested evidence survives delayed admission at delays up to
  324.2s -- 2.8x longer than the one residual case that could not be
  conclusively attributed either way after a strong-track/independent-
  visual/cache-volume-timing analysis. The historical 32-bound-era
  eviction signature (a real, strong, delayed proposal *provably* losing
  its own already-captured evidence) does not clearly or systematically
  recur. **Decision A -- accepted.** Also surfaced, disclosed, and
  explicitly deferred rather than fixed here: a real pattern where several
  confirmed real-bird tracks produced no persistable evidence despite low
  cache-volume pressure, more likely attributable to the burst-scheduler's
  own issuance/fairness decision than to cache capacity -- a genuinely
  different, upstream mechanism, named as a candidate for future bounded
  investigation, not a reason to reopen this bound again. See
  [cache-128-live-daylight-acceptance-v1-report.md](cache-128-live-daylight-acceptance-v1-report.md)
  for the complete accounting.
- **Harvested Evidence Issuance / Missing-Evidence Closure v1 (2026-08-20)**
  investigated the disclosed finding immediately above -- 4 of the same
  session's 7 `blocked_missing_evidence` cases showed only 8-22% of the
  128-entry cache's own capacity in use during their delay window, too low
  for that cache's own eviction to plausibly explain them. Traced the exact
  real production path (confirmed track -> burst scheduler -> capture ->
  harvest -> assembly tick -> admission) and found a concrete, different,
  previously-undiscovered defect rather than confirming the burst
  -scheduler-fairness hypothesis the prior milestone's report suggested:
  `LiveCameraNodeShadowSession._temporary_payloads`/`_same_frame_temporary_
  payloads` (`camera_node_live.py`) are each their own small, fixed,
  content-hash-keyed cache, hardcoded to 8 entries -- entirely independent
  of, and never touched by, either the 8->32 or 32->128 fix -- and were
  only ever harvested into the properly-sized cache once per whole
  `session.run()` *batch*, after the entire up-to-20-frame batch had
  already returned, not "the moment... observed" as the code's own
  pre-existing comment already claimed. A batch busy enough for more than 8
  separate frames to each successfully capture a burst (several concurrent
  generations, or several distinct subjects in sequence -- correlated with,
  but not exclusively caused by, 2 of the 4 real multi-subject-rich moments
  this same session's own independent review flagged) silently evicted an
  early capture from that small cache before the harvest loop ever reached
  it -- so a proposal could legitimately reach admission with its own
  evidence already captured, and already lost, long before the much larger
  cache under test in the milestone above ever had a chance to hold it.
  Fixed by harvesting immediately, per frame, via a new `on_result`
  callback on `LiveCameraNodeShadowSession.run()` -- not by enlarging any
  cache, preserving this milestone's own governing "no magic cache-size
  increase" constraint. Reproduced deterministically through the real,
  unmodified production path (`ObservationEngineSessionManager.start()` ->
  `_run_async` -> `session.run()`): a RED test (independently verified
  against the pre-fix source via `git stash`, not merely reasoned about)
  showed the first of 9 distinct, single-frame, real-tracker-shape
  generations reaching exactly `blocked_missing_evidence` despite a real,
  proven burst capture and an outer cache nowhere near its own bound; GREEN
  after the fix. Added one new bounded diagnostic,
  `advanced.evidence_harvest_misses`, directly closing the field report's
  own disclosed "no surviving log/API signal distinguishes 'never
  harvested' from 'harvested then evicted'" limitation for any future
  session. Zero regression: the full Core suite (3301 passed, 2 skipped, 10
  deselected, 11 xfailed) and all three existing evidence-cache-capacity
  regression tests (8->32, 32->128, and the headroom-margin test) passed
  unmodified. Decision: **A -- issuance/harvest defect proven and fixed**.
  Also disclosed, not fixed: `candidate_visit_authority_cli.py`'s own
  separate, bounded, operator-driven trial tool has a differently-shaped
  instance of the identical root cause (lazy per-10-second-tick lookup
  rather than per-batch), left as a genuine but lower-priority follow-up
  since it is not the path any real field session actually runs. See
  [harvested-evidence-issuance-missing-evidence-closure-v1-report.md](harvested-evidence-issuance-missing-evidence-closure-v1-report.md)
  for the complete case-by-case accounting and code trace.

## v0.1 scope freeze

Public v0.1 means, approximately: install MockingBird → connect a supported
camera → reliably notice wildlife → preserve useful evidence → assemble
correct Visits → provide honest species assistance → let the user
confirm/correct → create durable Observations → return later and understand
what has been happening at the Place.

A new requirement enters v0.1 scope only when at least one of these is true:

- direct field evidence shows product correctness depends on it;
- safety, privacy, or security requires it;
- release, install, or recovery correctness requires it;
- a previously accepted assumption is empirically invalidated.

An idea does not become a v0.1 requirement merely because it is interesting,
ambitious, or would make the product more capable later. The 2026-08-19
multi-animal, duplicate-Visit, evidence-latency, and detection-recall field
findings (see "Current status," above) qualify under the first criterion --
they are direct field evidence, not speculation. The 2026-08-20 Camera Node
bad-boot incident (see "Current status," above) qualifies the same way: a
real reference device failed to boot in the field, not hypothetically, and
the product's own reconnect diagnosis needed to -- and did -- tell that
apart from a host or GPU problem; see "Camera Node field hardware
resilience / bad-boot recovery" under Gate D, below. Remote/cellular/solar
hardware does not qualify under any criterion today; see "Post-v0.1 lanes,"
below.

## Scope-reopening rule

Accepted architecture/product decisions are not reopened merely because
another interesting option exists. A decision reopens only when:

- new field evidence contradicts it;
- correctness, safety, or privacy requires it;
- release validation reveals an invalid assumption;
- materially stronger technology justifies a bounded candidate evaluation
  (see "Formal model lifecycle" in [architecture.md](architecture.md)).

Settled direction, not up for casual reconsideration:

- Observation is the semantic center; detection is infrastructure.
- Local-first; cloud is optional, never required.
- Human review creates truth; nothing else does.
- Hardware- and provider-agnostic; Raspberry Pi is a reference
  implementation, not product identity.
- Remote field hardware (LTE/solar/custom carrier) is post-v0.1.
- Research-grade credibility is earned through sustained real deployment,
  not declared.
- Custom hardware requires accumulated deployment evidence first, not the
  reverse.
- SpeciesNet remains an unadopted, evidence-only candidate (see Gate B,
  below); any future look is a fresh re-evaluation, not resuming a prior
  adoption that never happened.

This is intentionally the last general, open-ended roadmap/doctrine audit
before v0.1. Future audits should be gate-specific ("what prevents Gate X
from passing," not "what else could we improve") unless new empirical field
evidence invalidates something above.

## v0.1 release gates

The remaining path to v0.1 is a small, ordered set of release gates, not an
open-ended list of phases. Gate order is priority order: do not spend
material effort on a later gate while an earlier one has a known, evidenced
gap, except where independent work genuinely does not depend on the
unanswered question (see "Field-testing doctrine," below).

Historical Phase numbering ("Phase sequencing," below) remains the
structural/historical record of how the product got here and is not
renumbered. Each phase's still-open v0.1-relevant work maps onto one or more
gates here; use this section, not phase number, to answer "what's actually
left before v0.1."

### Gate A -- Trustworthy Detection, Encounter & Visit Correctness

The hardest and highest-priority v0.1 gate. The product question is not "is
the detector benchmark good" -- it is **did MockingBird correctly notice and
represent what actually happened outside.** Passing this gate requires
measuring the full perception funnel, not an isolated model score: capture
coverage → activity detection → animal presence → detector localization →
tracking → proposal generation → admission → evidence survival → Visit
assembly → evidence selection → source-resolution lineage → multi-subject
handling → false Visits → fragmentation → duplicate Visits → accidental
merging → capture-to-visible-Visit latency → backpressure behavior →
admission/suppression correctness → provenance.

Top-level field metrics (see
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
for the formal accounting and "Numeric release budgets," below, for what
does and does not yet have an accepted number): genuine wildlife encounters
presented vs. captured vs. missed; end-to-end Visit recall; false-Visit
rate; fragmentation rate; duplicate-Visit rate; useful-evidence rate;
per-subject evidence correctness; capture-to-user-visible-Visit latency;
monitoring coverage.

**Current disposition (2026-08-19 evidence,
[end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)):**
genuine encounter recall 15/22 = 68.2% (a disclosed ceiling), detector
localization 17/19 = 89.5%, evidence-survival-to-admission 15/17 = 88.2%,
false-Visit rate 2/21 = 9.5%. Precision is now strong; recall and Visit-shape
correctness are the open work. Gate A is not passed. Three concrete,
evidenced gaps remain (none of them "the detector is bad"):

1. **Evidence-cache capacity fix (32→128) needs one more live field proof.**
   RED/GREEN-verified against the exact real failure shape that motivated
   it, zero measured regression across every replayed cohort -- but not yet
   confirmed by a live encounter of the same shape under the raised bound.
   This is the single concrete next field-acceptance action (see "Current
   recommended next action," above, and "Numeric release budgets," below).
   A 2026-08-19 attempt redeployed and started a real session against this
   exact fix but produced no usable denominator: the session was started
   after local sunset (a real gap in that attempt's own session-quality
   judgment, not a product defect -- every prior successful session started
   during daylight). 32.8 real minutes produced zero track generations,
   zero proposals, and zero candidates; the counterfactual ledger shows the
   detector was not idle (2268 raw detections at MDv5's permissive 0.1
   threshold, consistent with low-light sensor/IR noise), and correctly
   never promoted any of them to a confirmed track -- a clean, if
   unintended, precision data point, but not a proof of the cache fix under
   real churn. The live proof itself remains outstanding; the deployed
   build (`c5278cb`, includes the fix) is healthy and ready for the next
   daylight attempt without a rebuild.
2. **Multi-subject Visit correctness** -- see the dedicated subsection
   immediately below. New, hard requirement; current schema/UI cannot
   represent it. A concrete, repository-grounded implementation design now
   exists:
   [multi-subject-visit-assembly-review-v1.md](multi-subject-visit-assembly-review-v1.md).
   **Phase 1** (assembly-layer `concurrent_sibling_proposal_ids` detection,
   pure/additive, no schema/persistence change) implemented 2026-08-19. The
   schema/UI gap this subsection describes is **not yet closed** -- Phase 2
   (Event-reuse persistence, schema 36) and Phase 3 (frontend) remain not
   started; Phase 1 alone does not change which Visits are created.
3. **Background/empty evidence receiving a confident species label** -- a
   real, repeatedly-observed regression class (2/21 false Visits in the
   latest session, 5/70 in the prior large cohort, all carrying a confident
   wrong species name because BioCLIP has no abstention path). See Gate B;
   the fix belongs partly in Gate A (credible-animal gating) and partly in
   Gate B (abstention).

Gate A also owns **observation freshness / capture-to-visible latency** as a
first-class quality concern, not merely an implementation detail: a user
must be able to tell "missed" apart from "queued," "admitted but not yet
persisted," "persisted but not yet visible," and "species still processing."
Track (or plan observability for) timestamps across: source capture →
activity → animal detection → proposal → admission → Visit persistence →
Visit UI visibility → evidence ready → species suggestion ready. A delayed
Visit must never look, to the user, like MockingBird saw nothing. Visit
visibility must not wait on species enrichment, which finishes
asynchronously. Under backpressure, priority order is: (1) capture, (2)
encounter/Visit correctness, (3) durable evidence, (4) user-visible Visit,
(5) species enrichment, (6) optional analytics/enrichment -- never sacrifice
observation correctness for optional inference that is behind.

The accepted `frame-driven-onnx-cuda` Camera Node path is already, today,
continuous/near-continuous frame-driven detection with burst-triggered
high-resolution evidence capture -- not isolated snapshot-timer polling;
`SnapshotObservationProvider`'s timer-driven path remains a deliberately
preserved compatibility/lower-capability/CPU-fallback provider, not the
primary architecture (see "Observation Engine v2 boundary" in
[architecture.md](architecture.md)). Snapshot-based acquisition is
therefore not a permanent architectural requirement, and was never
asserted as one -- but it is also not yet fully evolved: evidence bursts
are captured measurably *after*, not at, the triggering detection, a
documented mechanism behind at least one real off-target localization
finding (see [localization-attribution-contract.md](localization-attribution-contract.md)).
A short rolling pre-trigger source buffer -- memory/local-storage bounded,
persisting evidence only when needed, never continuous video storage, never
an NVR -- is a candidate solution if capture timing turns out to be a
material Gate A blocker; it is not scoped or implemented in this pass.

#### Multi-subject Visit correctness (new, hard v0.1 requirement)

`Visit = exactly one animal` is not a valid product assumption --
[product-doctrine.md](product-doctrine.md) already says so ("Do not assume
one Visit equals one bird... every Visit contains exactly one individual").
What is new, from direct 2026-08-19 field evidence, is that this is now a
**hard v0.1 release gate**, not only a modeling caution: ordinary
feeder/property scenes with multiple simultaneous birds (the real, current
example: a nuthatch plus two finches present at once) must not become zero
Visits, one falsely singular bird, several duplicate Visits for one
encounter, accidental subject merges, one species label applied to every
animal in the frame, or contradictory species labels for duplicated
representations of the same subject.

**Current state, verified directly against the domain model, not assumed:
the schema and UI cannot represent this today.**

- `visit_episode_assembler.classify_boundary`'s documented "structural
  incompatibility" rule treats *any* temporal overlap between two confirmed
  tracklets as non-mergeable, because it cannot safely tell "two simultaneous
  real subjects" apart from "one tracker-association artifact" -- and, by
  design, never tries; see
  [tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
  "Structural incompatibility." This is a deliberate, historically-correct
  design boundary (it protects against fabricating false continuity), not a
  bug -- but its downstream effect is now an explicit v0.1 correctness gap:
  2026-08-19 evidence traced two fragmentation cases directly to it, one
  producing three Visits with three different species labels
  (`tufted_titmouse`, `american_robin`, `american_robin`) for what is almost
  certainly one bird, and a separate two-different-birds-at-once encounter
  (a reddish bird on the hook, a brown bird at the feeder, simultaneously)
  that produced **zero** Visits at all. See
  [end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md)
  §5/§7 for the complete evidence.
- `VisitModel` has scalar `subject_label`/`species_guess`/`confidence`/
  `reviewed_label` fields (one value per Visit, not per subject);
  `SpeciesSuggestionModel` has no subject/track discriminator (the product
  already treats "the Visit's latest suggestion" as *the* suggestion);
  `ReviewLabelModel.target_type` is hard-constrained to `{event, visit}` with
  no subject-level target; `VisitRelationshipModel.relationship_type` only
  ever takes `split`/`merge`, with no "concurrent, different subjects"
  relationship; the frontend Visit case file renders exactly one correction
  form per Visit. None of this is an oversight -- it is a consistent,
  whole-stack single-subject assumption that now needs to change.
- Notably, the live tracker/burst-evidence layer *can already* track and
  capture evidence for concurrent generations somewhat independently (one
  `BurstOpportunity` per generation; see "Multi-subject handling" in
  [burst-scheduler-contract.md](burst-scheduler-contract.md), which
  documents a real, previously-reviewed two-simultaneous-bird frame with two
  independent boxes). The gap is downstream, at assembly, persistence, and
  review -- not at capture.

**Scope boundary, explicit:** required before v0.1 is reliable
*within-encounter* multi-subject tracking/association sufficient for
trustworthy Visit construction and review. Not required, and out of scope:
recognizing the same individual animal tomorrow, biometric individual
identification, persistent cross-Visit ReID, perfect identity across
arbitrarily long occlusion, or research-grade population estimation (all
remain explicitly deprioritized; see "v0.1 non-blockers," below). If subject
identity becomes ambiguous mid-encounter, MockingBird must preserve that
ambiguity rather than fabricate continuity -- the same principle that
justified the conservative boundary in the first place.

This is a design problem, not something to solve in a documentation pass. A
focused **Multi-Subject Visit Assembly & Review v1** milestone is now an
explicit v0.1 prerequisite. Its design authority is the existing
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md)
(assembly/merge-boundary mechanism) and
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md)
(admission/persistence), extended -- not a new parallel system -- governed
throughout by [product-doctrine.md](product-doctrine.md)'s existing
individual-identity caution. Do not implement it opportunistically inside an
unrelated task.

**Multi-subject candidate techniques, explicitly not mandated for v1.** The
accepted [multi-subject-visit-assembly-review-v1.md](multi-subject-visit-assembly-review-v1.md)
design resolves the concrete 2026-08-19 evidence (simultaneous subjects,
species-inconsistent fragmentation) through Event-level grouping and
transitive ambiguous-cluster arbitration, neither of which requires tracking
through occlusion. Short-term intra-encounter occlusion/reacquisition (a
subject briefly leaving and re-entering frame within one encounter), scored
tracklet association, and short-term motion prediction remain named
candidate techniques for a future iteration if field evidence shows the
current preserve-ambiguity-rather-than-fabricate-continuity default is
insufficient -- not required, and not scoped, for v1. Do not build a custom
optical-flow stack for this (see "Explicit deprioritization," below); any
future motion-prediction candidate stays a bounded, lightweight technique
evaluated the same way a detector candidate is (see "Formal model
lifecycle" in [architecture.md](architecture.md)).

**Small/far, crowded/NMS, and day/night detection quality remain in-scope
Gate A dimensions with existing but not-yet-decisive infrastructure.**
[multi-scale-detector-benchmark-contract.md](multi-scale-detector-benchmark-contract.md)
(tiling/scale strategy) and
[adaptive-motion-proposal-benchmark-contract.md](adaptive-motion-proposal-benchmark-contract.md)
(cadence responsive to measured activity) already exist as Phase 2
infrastructure for small/distant subjects and adaptive activity cadence;
Detection and Localization Model Benchmark / Promotion v1 already evaluated
a tiling strategy and rejected it on false-positive/runtime grounds (state
A, incumbent retained -- see "Numeric release budgets," below). Crowded-
feeder/NMS behavior and day/night quality accounting have no dedicated
benchmark slice yet; both fold into the difficult-case-slice work Phase 2
still owns (see "Phase 2," below) rather than becoming a new parallel
initiative. Hard-negative/confusor cohorts are, by contrast, already a
mature, evidenced capability -- see Scene Confusor Suppression v1, above.

#### Perception Replay Regression Harness (Gate A engineering capability)

Every serious field defect this project finds should leave behind, where
practical, one of: a focused regression test, a deterministic replay
sequence/fixture, a property/state-machine case, or a fault-injection case
-- not only a narrative report. Prior art already exists and is the correct
extension point, not a green field:
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md)
(Stage 2) already replays an ordered frame directory through a real,
explicitly-selected Observation Engine provider -- offline, deterministic,
shadow-only, and structurally unable to create product records or reviewed
truth -- and already scores matched/missed Visits, false/duplicate
proposals, fragmentation, and incorrect merging against an optional truth
manifest. What that prior art does not yet provide: a logical-time replay
mode driven by recorded timestamps rather than frame order alone; a
differential `baseline` vs. `candidate` comparison for the same replay
manifest; named regression fixtures built from real 2026 field defects (the
cache-eviction encounters, a real encounter that fragmented into multiple
Visits, a known background false Visit, a known valid bird Visit); an
explicit run manifest recording code HEAD/model/config/seed provenance per
run; and a documented determinism/semantic-equivalence statement for
GPU-backed inference. Extending the existing benchmark into this fuller
regression-harness capability -- reusing its production computation path
rather than building a second perception implementation -- is queued
engineering work, isolated from the live runtime (a separate branch/
worktree, never the checkout used for field acceptance). Live field
acceptance remains required for promotion regardless of replay coverage;
the harness reduces how often a fix has to wait for another real bird to
validate a hypothesis, it does not replace the live proof.

### Gate B -- Useful Species Assistance

Perfect top-1 species identification is not a v0.1 requirement. The purpose
of automatic identification before review is useful, honest assistance --
not the product outcome by itself (see
[product-doctrine.md](product-doctrine.md) "Product promise"). Acceptance
requires: useful top-k, not necessarily correct top-1; a sufficiently low
confidently-wrong rate; meaningful abstention ("Bird -- species uncertain"
is a valid, often-preferable output); safe non-bird/background behavior (a
credible-animal gate, or classifier abstention, on empty/background
evidence); provenance and correct evidence input; bounded inference latency
and safe failure; no creation of reviewed truth -- suggestion only, exactly
as already governed.

**Current disposition:** BioCLIP 2 (`adapter_id=bioclip_2`) is the live,
default-off-automatic/always-available-manual suggestion adapter. It is
genuinely useful on plausible common species, but **has no abstention path
at all today** -- confirmed repeatedly, not theoretical: it returned a
specific, confident species name for every one of 5 empty-frame Visits in
the 70-Visit Observational Quality Closure v1 cohort and for both of the 2
confirmed-false Visits in the 2026-08-19 End-to-End session. This is the
concrete Gate B blocker, not species accuracy: **abstention does not exist
anywhere in the species pipeline today** (also true of the detection
pipeline's own stage 12; see [architecture.md](architecture.md) "Detection
Quality Accounting"). Representative species-level correction truth (30-100
reviewed examples) to actually validate accuracy also remains uncollected.

**Requirements the eventual abstention/eligibility mechanism must satisfy**
(named now so a future implementer does not have to rediscover them from
scratch): one canonical species-inference eligibility policy, not a
per-caller check scattered the way review-truth authority used to be before
[review-decision-provenance-contract.md](review-decision-provenance-contract.md)
centralized it; machine-readable eligibility/abstention reason codes, not
free-text; no credible-animal evidence must mean no forced species answer;
evidence-quality gating on source subject pixel size, blur/sharpness,
exposure, occlusion, and bounding-box completeness, all traceable through
valid lineage back to a real captured frame; a genuine open-set/null outcome
(`animal_uncertain`, `bird_uncertain`) distinct from a low-confidence guess;
hierarchical specificity where evidence supports it (a genus/family-level
answer is more honest than a forced species guess); per-subject
classification once Multi-Subject Visit Assembly ships (one suggestion per
sibling Visit, never one label smeared across every animal in frame);
multi-frame classification with quality-ranked frame selection and
duplicate-frame suppression before consensus, rather than one arbitrary
frame; temporal-prediction disagreement across frames as positive evidence
for abstention, not something discarded; and quality-regime calibration (a
confidence number should mean the same thing across a good-light and a
poor-light regime). Place/geography/season/history context may only rerank
already-credible candidates -- see "External ecological context" in
[product-doctrine.md](product-doctrine.md) -- never substitute for visual
evidence or override a credible-animal/abstention decision, and raw visual
prediction provenance stays preserved even when context reranks. Any future
model comparison (Species Classification Re-evaluation / Promotion v2,
below) happens only once classifier-input correctness is proven for the
adapter being compared -- see
[same-frame-species-evidence-contract.md](same-frame-species-evidence-contract.md)
for that proof on the current adapter -- not before.

Do not let species-model optimization block release once identification
assistance is demonstrably useful and safe. Do not reduce abstention just to
produce more exact-looking labels.

#### Background/empty evidence → confident species label (regression class)

Real, repeatedly-observed, not hypothetical: empty/background evidence has
received confident bird species labels in more than one field cohort. For
each case, distinguish rather than lump together: (1) genuine detector false
positive; (2) inference eligibility/gating error (species inference ran when
it should not have); (3) classifier failure to abstain on non-animal
evidence (the confirmed mechanism behind every case traced so far); (4)
wrong source frame/crop/evidence-lineage defect; (5) delayed/stale evidence
mismatch, where applicable.

v0.1 invariant: background/empty evidence must either fail the
credible-animal gate or cause species inference to abstain/not run. If a
real animal existed, the Visit must preserve and display the correct source
evidence used for interpretation. Do not fix this solely by raising the
detector confidence threshold before root cause is understood -- that
specific approach has already been swept against real reviewed data and
rejected (see
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
"Production authority gate": no threshold clears both the
false-positive-rejection and real-animal-recall conditions together). This
regression class is now a standing cohort for the eventual fix, not a
one-off finding.

#### SpeciesNet / BioCLIP history (accurate record, preserved)

SpeciesNet was a deliberate, seriously-evaluated direction, not something
newly discovered: MegaDetector-family detection and SpeciesNet species
identification were investigated together (Phases 9I-9K), then SpeciesNet
was actually run against real saved field media on 2026-07-16 and got top-1
bird on only 1 of 8 reviewed crops with no species-specific top-1 result at
all -- it failed the usefulness gate on MockingBird's own corpus. BioCLIP 2
returned an avian species top-1 on every reviewed/candidate crop in the same
evaluation and became the stronger candidate, then the production suggestion
adapter (Phase 26A/26B). Any future SpeciesNet work is a fresh
re-evaluation against then-current evidence, not resuming an adoption that
never happened.

#### Species Classification Re-evaluation / Promotion v2 (bounded future milestone, not v0.1-blocking)

One bounded candidate-model milestone, once Gate B's abstention/safety
requirements are otherwise met: compare the current deployed BioCLIP path,
current SpeciesNet, a justified newer BioCLIP-family model, and (only with
evidence) another materially stronger model. Benchmark across the actual
MockingBird visual domain -- feeder, yard/porch, nest/box, RTSP/
security-style, remote/trail-cam-like, manual/DSLR import, close, small/far,
day, night/IR, motion blur, juvenile/sex variation, multiple subjects,
birds, non-bird wildlife, and difficult sibling taxa (a real example already
exists: House Finch vs. Carolina Chickadee vs. Tufted Titmouse, per
[observational-quality-closure-v1-report.md](observational-quality-closure-v1-report.md)).
Measure top-1, top-k, coverage, calibration, abstention, confidently-wrong
rate, crop-vs-full-frame, geography on/off where relevant, and runtime cost.
Do not build a SpeciesNet/BioCLIP ensemble or router first -- determine
whether one model materially wins overall, or a repeatable domain split
justifies the added complexity, before building either. Once a v0.1
selection is accepted, it is settled direction (see "Scope-reopening rule,"
above) absent materially new evidence.

#### Resolution-aware species inference (preserved, partially tested doctrine)

Lineage doctrine already exists and is unchanged ("Source-resolution
evidence contract" in [product-doctrine.md](product-doctrine.md)): trace
original source resolution → selected source frame → source-coordinate crop
→ any subsequent transform. A real, first-of-its-kind resolution-enhancement
comparison
([observational-quality-closure-v1-report.md](observational-quality-closure-v1-report.md)
§12) tested part of a broader ordering and found: native/source-resolution
evidence remains canonical; conservative 2x interpolation is a measured
no-op (0/8 cases improved); a synthetic 4x-downsample-then-recover
measurably degrades results (6/8 cases worse); multi-frame/burst
reconstruction was named but not attempted. Two further stages --
conservative learned super-resolution, and generative/diffusion
super-resolution as experimental-only -- have no existing evidence base and
are net-new framing here, to be evaluated (if ever) only with real
comparative evidence against native evidence, never as a default replacement
for it. One specific, disclosed, unresolved lead from that same test (n=1):
a lower-native-resolution same-moment crop classified a real bird correctly
while the higher-native-resolution burst crop classified it wrong, plausibly
a capture-timing/pose-alignment effect rather than a resolution effect --
recorded as a future species-quality lead, not acted on.

### Gate C -- Today / Report-First / Place Intelligence

Detection work must not pull the product back into being a detector
dashboard. MockingBird must eventually answer, for a Place: what visited,
how often, where, what's new, what's regular, what's changed, and how much
monitoring coverage supports those claims. Preserve: Today, Place history,
counts, species-visit summaries, Zone/hour patterns, baseline maturity,
new-vs-regular species, coverage-aware claims, a clear
confirmed-vs-provisional distinction, calm review, calm digests/
notifications, and useful sparse/first-run states (see
[product-doctrine.md](product-doctrine.md) "Place Intelligence" and
"Calm-observatory notifications"). Language models and external ecological
context may explain and enrich; they never become observational authority
(see "Language models" in product-doctrine.md). **Current disposition:**
substantially delivered as Today in Your Yard, with Place Intelligence's
backend hardening also complete (DST-correct bucketing, wildlife-eligibility
denylist, taxonomy N+1 eliminated, union-based coverage); the frontend
surface for that newer Place Intelligence work is the open piece -- see
Phase 5, below.

**Temporal correctness surfaces this gate must preserve, named explicitly:**
event time (source capture) vs. ingestion time vs. processing-completion
time vs. presentation/UI freshness must stay distinguishable, not collapsed
into one ambiguous timestamp (see the freshness chain in Gate A, above, for
the perception side of this same principle); day-boundary semantics must
honor Place timezone and DST, not UTC-midnight, matching the DST-correct
bucketing already delivered (above); late-arriving evidence (a delayed
Visit persisted after its own day's report was already viewed) must revise
rather than silently omit. Camera Node clock drift already has a dedicated,
disclosed measurement-only investigation -- see "Clock-drift disposition"
in [camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md)
-- not yet a correction mechanism; today's mitigation is server-side
timestamp assignment at capture, not trusting device clocks for ordering.
Derived insights (baselines, trends, coverage claims) must remain
reproducible from persisted facts, never recomputed silently in a way that
changes a past report.

### Gate D -- First-Hour Setup & Camera Node Golden Path

Scope is the *current* supported Camera Node and host: install,
pairing/configuration, health, reboot recovery, provider/capability
reporting, monitoring, first useful Observation/report, support-safe
recovery. This is not the same gate as Remote Field Node (LTE/solar/
battery/remote enclosure/custom hardware) -- that is post-v0.1; see
"Post-v0.1 lanes," below. **Current disposition:** the Camera Node's own
install/service/reboot-supervision path is proven on real Pi 4 hardware
(crash, clean-restart, and network-interruption recovery all verified
live); the MockingBird host's own install/upgrade/recovery experience
(Phase 4) has a self-contained Windows bundle and first-run wizard, with
native Windows hardware acceptance, automatic upgrade, and guided recovery
still open.

**MockingBird Doctor / self-check, named and still open.** No consolidated
health/self-check capability exists today; product/camera health is spread
across several narrower surfaces (Dashboard summary, Observation panel,
Camera Health). A single self-check covering database integrity,
migration/schema state, media-root reachability, filesystem permissions,
disk space, Python/native dependency presence, model-file presence, GPU
availability when configured, paired Camera Node reachability, provider
configuration validity, clock sanity, backup state, and version/
compatibility would give support and self-diagnosis one place to look
instead of several -- not yet scoped or built; a future bounded milestone,
not a v0.1 blocker by itself unless field evidence shows otherwise.
Transactional configuration (`preview -> validate -> apply -> verify ->
recover/rollback`) is already the shape of Guided Camera Editing's redacted
impact-preview/bounded-save flow (see "Source adapters" in
[architecture.md](architecture.md)); treat that as the template for any
future config flow with real runtime effect, including explicit progress
states for the asynchronous steps, rather than inventing a second pattern.

#### Camera Node field hardware resilience / bad-boot recovery (new, evidence-driven requirement)

Direct 2026-08-20 field evidence (see "Current status," above) showed a
case none of the reboot/crash/network-interruption acceptance above
actually covers: the real reference Pi 4 was powered (solid red LED) but
never came back on the network at all -- no ACT activity, no ICMP, no TCP
8787, no `/node/v1/health` -- until a physical power cycle recovered it.
MockingBird software cannot repair hardware that never boots, and must
never claim to; but it must recover automatically once the node returns,
accurately say so when it cannot, and never again let an unrelated
diagnosis (as the now-fixed `onnx_cuda_verification_insufficient`
misclassification once did) obscure that the node itself, not the host or
GPU, is the problem.

Camera Nodes are replaceable field infrastructure; they are not where
MockingBird's truth lives (see "Cross-cutting roadmap invariants," below).
A Camera Node must: (1) automatically recover from failures it can
control; (2) accurately expose failures it cannot control; (3) preserve
host-side observational truth through node failure; (4) be straightforward
to reprovision or replace. (1)-(3) extend the install/service/reboot proof
already delivered (above); (4) is new. This governs both this gate's
setup/identity/recovery-state surface and Gate E's field-recovery ladder,
below -- one bounded capability, not two.

Bounded additions to the Camera Node golden path, all capability-driven
and hardware-agnostic -- no proprietary MockingBird hardware required:

- a node boot/readiness self-test, run before the node reports itself
  healthy;
- a stable node identity, distinct from the pairing credential, that
  survives reinstall/update;
- `boot_id`, process uptime, installed software-image/OS version, and
  Camera Node service (package) version, readable locally and reportable
  to the host;
- a record of the node's last successful startup;
- a host-visible heartbeat / last-seen fact that exists independently of
  whether an Observation session happens to be running right now;
- an explicit distinction between "paired/configured" and "actually
  reachable right now" (see "Product-health semantics" under Gate E,
  below) -- exactly the distinction the 2026-08-20 incident needed, and
  the host's bounded reconnect logic already gets right *while a session
  is retrying*, but which has no persistent, host-visible surface once a
  session has already given up -- a gap "Camera Node Connectivity &
  Recovery Diagnosis v1" (above) already discloses;
- startup validation of the camera/provider, node storage, and other
  supported capabilities, reusing the existing per-provider
  `setup_required`/unavailable reporting (see
  [camera-node-boundary-design.md](camera-node-boundary-design.md)) rather
  than inventing a second capability model;
- clear operator recovery states and actions -- what to check, and in what
  order, when a node stops reporting;
- a configuration backup/export, or equivalent mechanism, so a working
  node's own configuration is not itself a single point of failure;
- a replacement-node workflow that preserves the existing Place/Source/
  Stream/Zone/history exactly as Guided Camera Editing's existing repair
  path already does for a lost credential (see "Source adapters" in
  [architecture.md](architecture.md)), while retaining an honest
  hardware/provenance lineage across the swap -- reviewed history must
  never read as if it came from a device that was actually replaced;
- golden-Pi guidance for supported-quality power supply, storage/boot
  media, and networking, added to
  [camera-node-install-guide.md](camera-node-install-guide.md) alongside
  its existing prerequisites/bind-address guidance;
- a high-endurance boot-media recommendation (storage rated for sustained
  write endurance, not a bargain consumer card) for the Pi reference
  deployment specifically -- guidance for the golden path, not a
  requirement the installer enforces.

Every item above is either a software self-check, a documentation
addition, or a workflow already structurally proven by the installer or
Guided Camera Editing (above); none requires custom MockingBird hardware,
and Raspberry Pi remains the reference implementation, not the product
architecture (see "Scope-reopening rule," above).

### Gate E -- Reliability / Recovery / Observability

Existing structured error/diagnostics doctrine remains and now explicitly
includes perception latency and freshness (see Gate A, above) alongside:
capture freshness, activity/detections/tracks/proposals, admission,
suppressed/rejected reasons, evidence survival, Visit creation,
duplicate/fragmentation signals, queue depth, processing latency, classifier
latency, UI freshness, Camera Node health, reconnects, storage/database
failures, and coverage gaps. A user should never need to stare at the
feeder and guess whether the system is still working. Avoid high-cardinality
or raw-image telemetry. **Current disposition:** sustained operation,
restart/recovery, and truthful health reporting are largely proven for the
Camera Node path; bounded CPU/RAM/storage behavior is declared but not
exhaustively field-verified under representative unattended conditions (see
Phase 1, below).

**Bounded resource behavior, named as one family of concerns.** The
evidence-cache capacity history (8 -> 32 -> 128, all three raised from real
2026-08-19 recurrences under increasing real session load -- see "Current
status," above) is the concrete, lived reason correctness-critical evidence
cannot behave like an ordinary disposable cache sized by guess: undersizing
it silently drops already-captured evidence for a proposal still
legitimately resolving admission. Treat that history as the standing
justification for an eventual application-wide bounded-cache/queue audit --
every bounded structure in the runtime (evidence caches, the counterfactual
ledger, scene-confusor region history, tracker generation state, burst-
scheduler suppression memory) named with its units, purpose, capacity,
eviction rule, whether correctness depends on it staying populated, and
whether it exposes pressure telemetry -- not yet performed as one pass;
each bound so far has been raised individually, reactively, from real field
failure. A storage-pressure state machine (`healthy -> pressure -> critical
-> survival`) with an explicit preservation priority (reviewed truth and
durable evidence outrank caches, caches outrank optional enrichment) is
named here as the target shape for host-level storage behavior; today's
Storage & Retention (see [architecture.md](architecture.md)) is policy-led
and fails closed on ambiguous media, but does not yet implement the full
four-state escalation.

**Fault injection, named as a canonical case list.** Camera loss, Camera
Node loss, network loss, FFmpeg hang, classifier crash, unavailable GPU, DB
lock, disk full, interrupted media write, process kill, Pi reboot, host
reboot, clock jump, and malformed provider response should each have a
regression case where technically practical. Real, live-witnessed evidence
already exists for several of these -- Pi reboot, process crash (`kill
-9`), and a surgical network interruption all passed acceptance under
Camera Node Installer v1 (above); a real host reboot mid-session was
survived cleanly during End-to-End Bird Encounter Recall Closure v1 (above)
-- but they are not yet organized as one deliberate, repeatable
fault-injection suite, and several types (FFmpeg hang, classifier crash,
unavailable GPU, DB lock, disk full, interrupted media write, clock jump,
malformed provider response) have no dedicated case yet, live-witnessed or
synthetic.

**Explainability, as structured provenance, not narration.** "Why did
MockingBird create this Visit / suggest this species" should be answerable
from real structured facts already flowing through the pipeline --
animal-detected-in-N-frames, track confidence
(`ConfidenceEvidenceSummary`), subject count (once Multi-Subject Visit
Assembly ships), which evidence candidate was selected and why
(`evidence_scoring`), classifier input provenance (see
[same-frame-species-evidence-contract.md](same-frame-species-evidence-contract.md)),
species ranking, and abstention reason (once Gate B's abstention mechanism
exists) -- composed into one diagnostic view or export. This is a UI/API
composition of already-real provenance, not a new inference stage, and
never an LLM-generated narrative explanation standing in for it; language
models remain governed by "Language models" in
[product-doctrine.md](product-doctrine.md). Not yet built as one coherent
view; the underlying facts already exist, scattered across the
advanced-provenance surfaces named above.

**Support bundle and tracing.** A privacy-safe support bundle (bounded
diagnostic export -- health-check output, redacted logs, schema/version
facts, no raw media or credentials by default) and correlation/causal
tracing across a single request or session (so one Visit's full path from
capture through admission can be followed in logs) are both named, open
capabilities -- neither exists today. Avoid high-cardinality or raw-image
telemetry in either, per the existing structured-diagnostics doctrine
above.

#### Camera Node field-recovery ladder (extends "Fault injection," above)

The 2026-08-20 bad-boot incident (see "Current status," above, and the new
Gate D subsection, above) motivates naming a complete recovery ladder for
Camera Node field-hardware failure, rung by rung -- what MockingBird
recovers automatically, what it can only report honestly, and what already
has live evidence versus what is still open.

**Application/service failure.** Already proven: bounded
`Restart=on-failure`/`RestartSec=5`, capped by `StartLimitIntervalSec=300`/
`StartLimitBurst=5` so a persistent crash loop fails visibly instead of
hot-restarting forever (the systemd unit, live-verified under a real `kill
-9` -- see "Camera Node Installer / Package / Reboot Hardening v1," above).
Open: surfacing the node's own restart count / last-failure reason to the
paired host -- today this is visible only via direct `journalctl` access to
the device itself.

**OS hang.** Open, not yet built: a hardware watchdog where the platform
supports one (Pi 4's SoC has one, `bcm2835_wdt`) is not enabled or
acceptance-tested today. The Raspberry Pi golden path should enable and
acceptance-test it if practical; this stays a capability-gated addition,
not a requirement of every supported platform.

**Network outage.** Already proven: bounded reconnect
(`AnalysisStreamRetryPolicy`, 6 attempts, `backoff_seconds=12.0`), accurate
`advanced.last_healthy_frame_at`, and automatic recovery once connectivity
returns are all live-verified (Camera Node Installer v1's network-
interruption acceptance, above). "No misleading detector/species/CUDA
diagnosis when no frames arrived" is also already closed: this is exactly
what Camera Node Connectivity & Recovery Diagnosis v1 (above) root-caused
and fixed -- a session that never received a frame no longer misreports a
CUDA failure.

**Unexpected power loss.** Partially proven: pairing state is already
written atomically (`os.O_EXCL` + `os.replace`, per
[camera-node-installer-design.md](camera-node-installer-design.md) "State
paths") and survived a real `kill -9` and reboot untouched. Open: bounding
`journald`'s own on-disk growth (no size/retention bound is configured for
this unit today), minimizing unnecessary writes to boot media, and naming
an explicit acceptance case confirming a Camera Node reboot never requires
host-side database repair (true by construction today -- the host's own
database is entirely independent of Node state -- but not yet a named
acceptance case; see the field acceptance matrix, below).

**Boot failure / powered-but-not-booted.** This is the exact 2026-08-20
case. Already proven: while a session is actively retrying, the host
correctly and honestly classifies this as `timeout`/`camera_unavailable`
(above) rather than a host or GPU fault. Open, and the concrete gap this
incident exposes: once a session has already exhausted its retries and
stopped, there is no persisted "Camera Node offline, last seen at T" state
-- Doctor's own staleness check only covers a currently-*open* exposure
interval, a disclosed v1 scope limit (see
[camera-node-connectivity-recovery-diagnosis-v1-report.md](camera-node-connectivity-recovery-diagnosis-v1-report.md)).
The product must say "Camera Node offline / last seen X" in that gap,
never merely "paired and ready," and must preserve whatever boot/health
evidence it already had rather than discarding it the moment a session
closes. It must never claim software recovery when the node itself did
not boot.

**Boot loop / repeated restart.** Partially proven: `systemd`'s own
`StartLimitBurst=5`/`StartLimitIntervalSec=300` already bounds a hot-
restart loop at the process level (above) -- it cannot loop silently
forever. Open: nothing today exposes *evidence* of flapping (a changing
`boot_id`, a rising restart count) through a host-visible surface, so an
operator currently has no way to tell "the node is stuck restarting" apart
from "the node is simply offline" without direct device access -- this is
what the Gate D `boot_id`/identity addition (above) exists to close.

**Camera-device failure.** Partially proven: a camera provider that is
absent, permission-denied, or otherwise unusable already reports
`setup_required`/unavailable rather than a false ready state (see
[camera-node-boundary-design.md](camera-node-boundary-design.md)), and
`/node/v1/health`'s existing `camera_count`/`available_camera_count`
already lets a reachable-but-camera-broken node be distinguished from an
unreachable one in principle. Open: formalizing that distinction as one of
the named node-health states (see "Product-health semantics," below) and
adding a live acceptance case for it (see the field acceptance matrix,
below) rather than relying on it holding only by inspection of the
contract.

**Storage/media failure.** Open, not yet built: nothing today checks the
node's own free space, write pressure, or (where the platform exposes it)
filesystem/storage health -- the existing storage-pressure discipline (see
"Bounded resource behavior," above) is host-side only. A Camera Node
should fail safely -- stop attempting writes it cannot complete, and say
so -- before its own boot media fills, bounded and capability-gated the
same way provider capability reporting already is.

**Hardware-quality telemetry.** Open, not yet built, and explicitly
capability-driven rather than a fixed field set: for a platform that
exposes it, undervoltage/throttling, CPU temperature, storage health, and
reboot reason are useful operator-facing signals. Keep this
capability-aware (see "Capability-aware UX" in
[product-doctrine.md](product-doctrine.md)) -- a Raspberry-Pi-specific
field (for example `vcgencmd`'s throttling bitmask) stays a Pi provider
detail surfaced through a generic capability, never a core product
semantic every platform must implement.

**Replacement.** The terminal rung when nothing above recovers the node:
treat the field node itself as replaceable, reuse the same fast re-pair/
reprovision workflow named under Gate D, above, and preserve host-side
Place/Observation history and honest provenance across the swap. A
replaced node is a routine field event, not a data-loss incident.

#### External recovery boundary

Recovery from a node that is powered but never boots requires an
independent actor -- today, a person physically present to power-cycle it,
exactly what closed the 2026-08-20 incident. MockingBird does not, and for
v0.1 will not, claim to recover a node no software action can reach.
Managed PoE power cycling, smart power control, or an external hardware
supervisor may become useful for a future advanced/remote deployment (the
"Power / solar" lane already names a possible future low-power supervisory
MCU with hard-reset capability for that context; see "Post-v0.1 lanes,"
below) -- but automated, independent power-cycling of the golden home Pi
path stays post-v0.1 and optional unless future field evidence
demonstrates it is actually necessary there, not merely convenient (see
the extended "v0.1 non-blockers," below).

#### Independent Power / Node Supervisor (optional, post-v0.1)

For remote, solar, battery, PoE, or otherwise unattended installations,
MockingBird may integrate with an external supervisor that remains
operational when the Camera Node itself has failed -- the concrete
mechanism "External recovery boundary," above, and the "Power / solar"
lane (see "Post-v0.1 lanes," below) already anticipated without naming or
defining. The architecture stays hardware-agnostic: this is a
capability-driven interface, not a dependency on any specific device.
Possible capabilities MAY include -- MockingBird must not require all of
them:

- hard power-cycle of a Camera Node;
- controlled power on/off;
- node-power-state telemetry;
- battery state of charge, where available;
- battery voltage/current, where available;
- solar/charging state, where available;
- low-voltage disconnect/protection;
- delayed restart until battery voltage/state has recovered sufficiently;
- bounded automatic recovery policy;
- power-budget/load-shedding signals;
- reboot/power-cycle history.

MockingBird must not require or assume a specific solar charge controller,
BMS, relay, smart plug, PoE switch, MCU, Raspberry Pi HAT, or proprietary
MockingBird power controller.

**Independence rule.** A power supervisor only provides recovery from
failures below the Camera Node OS if it remains independently operable
when the Camera Node itself is unavailable. A relay controlled only by the
failed Pi is not independent recovery: if the supervisor's own control
path routes through the thing it exists to recover, it is not a recovery
path at all. Examples of genuinely independent implementations may include
managed PoE, a solar-controller load output, a smart BMS/controller, a
separate low-power MCU, an external watchdog/power supervisor, or future
integrated field-power hardware -- these are examples, not product
dependencies.

**Recovery semantics.** Where an independent supervisor exists, it extends
-- never replaces -- the existing ladder ("Camera Node field-recovery
ladder," above): node heartbeat disappears; bounded software
recovery/reconnect is attempted first; only if that does not recover the
node does an optional independent hard power-cycle run, according to
policy; then a fresh `boot_id`/heartbeat is verified; the operator is
notified only if recovery still fails. Automatic power-cycling is never
mandatory. A policy that performs it must bound attempts and rate the same
way the existing service-level restart bounding already does
(`StartLimitBurst`/`StartLimitIntervalSec`; see "Application/service
failure" under "Camera Node field-recovery ladder," above) -- an endless
power-cycle loop is exactly the failure mode this must not reproduce at
the power layer.

This entire capability stays post-v0.1 and optional (see the extended
"v0.1 non-blockers," below); it does not change the v0.1 obligation
already stated in "External recovery boundary," above.

#### Field-failure acceptance matrix (Gate D/E, extends "Fault injection," above)

Camera Node field-hardware resilience closes only once each of the
following has a real or deliberately-injected acceptance case, verifying
for each: what recovers automatically, what requires operator
intervention, the correct user-visible state, the correct diagnostic
evidence, that no authoritative host history is lost or corrupted, and
that no false downstream detector/species/CUDA diagnosis results. Injected
faults use disposable/synthetic media or a safe fault-injection technique
-- never physical damage to hardware and never intentional corruption of
the production SD card.

1. kill the Camera Node service -- already live-verified (`kill -9`,
   above).
2. the analysis stream closes mid-session -- already live-verified
   (network-interruption and multiple real reconnect episodes, above).
3. a temporary LAN outage -- already live-verified (the `nft`-rule
   experiment, above).
4. a host restart -- already live-verified (survived cleanly mid-session
   during End-to-End Bird Encounter Recall Closure v1, above).
5. abrupt Pi power removal -- **open**: distinct from a clean reboot (no
   orderly unmount, real filesystem/boot-media risk) and not yet exercised
   as its own case.
6. a Pi reboot -- already live-verified twice, with precise recovery
   timing (Camera Node Installer v1, above).
7. an OS/service hang or watchdog trip, where safely testable -- open;
   blocked on the watchdog itself being enabled first (above).
8. powered-but-no-successful-boot / node absent -- real field evidence now
   exists (2026-08-20, above) that the host correctly classifies this as
   `timeout`, but it has not yet been exercised as a deliberate, repeatable
   case, and the between-sessions "offline, last seen" gap named above
   remains open.
9. repeated boot/restart-loop evidence -- open; no `boot_id`/restart-count
   evidence surface exists yet to verify against.
10. a physical camera disconnect while the node itself stays up -- open;
    not yet exercised live.
11. a low-storage/storage-pressure condition on the node -- open; no
    node-side storage check exists yet to exercise.
12. replacement/reprovision of a Camera Node -- partially evidenced: a
    real credential re-pair through Guided Camera Editing's repair flow is
    live-proven (Camera Node Installer v1's "Pairing with the real host,"
    above), but a genuine physical-device swap preserving Place/history
    and provenance lineage end to end is not yet a deliberate acceptance
    case.

#### Product-health semantics: paired/configured != live/reachable

A Source can be paired and fully configured while the physical Camera Node
behind it is unreachable right now -- the 2026-08-20 incident, and every
ordinary network hiccup before it. Node health must ultimately distinguish
at least: healthy/reachable; degraded; camera unavailable while the node
itself is reachable; temporarily disconnected/reconnecting; node offline/
unreachable; boot/restart instability suspected; and replacement/
reprovision required, where determinable. This extends, and must reuse
rather than duplicate, Doctor's existing PASS/WARN/FAIL and
blocking/degraded/informational severity model (see
[mockingbird-doctor-operational-health-contract.md](mockingbird-doctor-operational-health-contract.md))
and the existing capability-aware-UX discipline (see
[product-doctrine.md](product-doctrine.md)), not a second health taxonomy.

Do not fabricate certainty. If the host only knows a heartbeat
disappeared, say "Camera Node offline, last seen <time>" -- never a
specific claim like "boot media failed" or "SD card corrupted" the host
has no way to actually know. An honest "offline, last seen" is more
useful, and more truthful, than a confident wrong diagnosis -- the same
principle Gate B already applies to species identification (see
"Governing priority for v0.1," above), extended here to node health.

### Gate F -- OSS / Security / Compatibility / Packaging Closure

Preserve: LICENSE, SECURITY, CONTRIBUTING, a clean repository, a
supported-version/security-disclosure policy, installation/packaging,
upgrade/recovery, backup compatibility, API/schema/event versioning with
additive-compatibility rules, privacy/security, dependency reproducibility,
accessibility/responsiveness, support-safe diagnostics, public benchmark
governance, and accurate user docs. Do not revive unnecessary cloud
dependency, Kubernetes, microservices, or speculative enterprise
architecture. Also preserve, more specifically than that list implies:
mechanized API/schema parity checks across backend and frontend; migration
clean-install and supported-version upgrade validation with existing data
preserved; update preflight and post-update verification with a documented
recovery/rollback path; model/dependency provenance, artifact checksum
identity, and OSS dependency-license hygiene; local/LAN exposure
expectations and authentication where a surface needs it; CSRF/origin
protection, secret redaction, safe file/path handling, and bounded
request/upload size; frontend error isolation and performance (Visit/image
loading stays usable at real backlog sizes -- see the P1 unbounded-list
fixes in "v0.1 Product Flow Gap Pass v1," above, as the precedent); and
reviewed-truth-safe archive/delete/retention semantics, so truth cannot
disappear through an accidental cascade -- the existing fails-closed
Storage & Retention behavior (see [architecture.md](architecture.md)) is
the template, not a separate rule. The focused/core/integration/browser/
hardware/field validation tiers, test-runtime discipline, and
property/state-machine test style already exist and are current -- see
[test-suite-validation-tiers-contract.md](test-suite-validation-tiers-contract.md).

**Current disposition:** CONTRIBUTING.md exists and is
current; **no `LICENSE` or `SECURITY.md` file exists in the repository
today** -- a real, open Gate F item, not yet started, distinct from and
smaller than Phase 4's packaging work. Public benchmark/training governance
(frozen holdout, provenance, contamination) exists for internal use (see
[wildlife-detector-training-contract.md](wildlife-detector-training-contract.md));
the legal-releasability/license/consent layer needed before any public
release did not exist before this pass -- see
[public-benchmark-governance.md](public-benchmark-governance.md).

### Gate G -- External Beta Acceptance

After the internal gates above are credible, move to a small external
cohort -- not hundreds of users. Prioritize diversity of real setups over
headcount. External usage should validate installation, Camera Node
pairing, detection, multi-subject encounters, evidence quality, review,
Today/report usefulness, recovery, and diagnostics under conditions this
project cannot fully simulate itself. Beta findings outrank speculative
architecture work. Not started; no existing doctrine to reconcile.

### Numeric release budgets

Where a valid numeric threshold already exists, it is preserved here rather
than reinvented:

- MDv5 production `score_threshold`: **0.1** (unchanged; state A, "MDv5
  native retained," per
  [detector-promotion-benchmark-report.md](detector-promotion-benchmark-report.md)
  -- no challenger dominated on the 70-image reviewed cohort).
- Tracker-internal `strong_detection_threshold`: **0.7** (gates
  confirmation/continuity bookkeeping, not admission).
- Confidence-gated admission was formally swept against real reviewed data
  and explicitly **not adopted**: at 0.3 it rejects 29% of false positives
  while losing 19% of real animals; at 0.7 it rejects 67% of false positives
  while losing 45% of real animals; no swept value clears both the
  false-positive-rejection and real-animal-recall conditions together (see
  [detection-quality-accounting-contract.md](detection-quality-accounting-contract.md)
  "Production authority gate"). Production admission stays confidence-blind
  by measured decision, not by omission.

What does **not** yet exist, and must be established from representative
field evidence -- not invented -- before Gate A can be declared passed: an
accepted minimum end-to-end Visit recall; a maximum false-Visit rate; a
maximum fragmentation/duplicate-Visit rate; a minimum evidence-survival/
useful-evidence rate; a maximum capture-to-visible-Visit latency; a minimum
monitoring-coverage figure. The most recent single session (68.2% recall
ceiling, 9.5% false-Visit rate, 88.2% evidence survival) is a
*measurement*, not yet an *accepted budget* -- one session, however
carefully independently validated, is not a representative body of evidence
on its own. Do not adopt "looks pretty good" as a substitute for a stated
number, and do not invent a precise-sounding target (such as 99.9%) that no
field cohort has actually justified. Establishing these budgets, from a
broader body of field evidence than any single session, is itself part of
what closes Gate A.

## Post-v0.1 lanes

Real future direction, deliberately not implemented now and not gating
v0.1. Kept here so it is not lost, not so it grows into a second roadmap.

**Remote / Intermittent-WAN Camera Node.** The *current* Camera Node
reference implementation is explicitly LAN/Wi-Fi-scoped today
(loopback-default bind, `network-online.target`-gated systemd startup, no
battery/RTC/power-loss handling) -- an accurate baseline to extend from, not
contradict. Architecture should already be tested against "would this still
work on a large property, on solar/battery, connected intermittently by
LTE, physically untouched for months" without claiming any of that works
today. Future direction: LTE/cellular transport, no Ethernet/Wi-Fi
requirement, secure outbound-only connectivity, no required inbound public
port, local store-and-forward, resumable/idempotent sync, retained
evidence/provenance, explicit pending-sync state, network-health and
data-budget awareness, and continued local operation through hours/days
offline. Never default to continuous source-video upload over cellular.
Cellular support, when built, should be bounded (a validated modem/SIM/
carrier matrix; standard Linux abstractions such as NetworkManager/
ModemManager, not a custom stack) with diagnostics that distinguish
modem-missing, SIM-missing/locked, registration failure, weak signal,
APN/data-session failure, internet failure, host/tunnel failure, quota, and
reconnect loops -- Observation continues locally through any of them. Route
the actual design to a focused future `docs/remote-field-node-design.md`
when this work is genuinely scoped; do not speculatively author it now.

**Power / solar.** Future first-class capability: report power source,
battery state, charge/solar input, autonomy, power-health, and storage
remaining where measurable; deployment profiles (bird/daylight, full
24-hour, other capability-aware duty cycles -- never globally disable night
just because the product is bird-first); deferred uploads, reduced optional
compute, survival mode, graceful shutdown, and auto-restart after power
recovery; possibly an ultra-low-power supervisory MCU later (watchdog,
battery/solar monitoring, wake/sleep, hard reset, modem reset). Planning
envelopes only, not guarantees: ≤20W-class is an excellent optimized stretch
target, ~30-50W-class is the desirable normal Remote Field Node range,
~100W-class is specialized/research territory, and routinely exceeding
100W per camera means reconsidering architecture rather than just adding
panel area. None of this is implemented now.

**Remote / energy-constrained field profile.** A bounded post-v0.1
deployment profile, not a new architecture: it complements the existing
local-first, hardware-agnostic design rather than replacing it, and
implies nothing about normal mains-powered home deployments, which stay
the primary product target unchanged. Assumptions this profile may
eventually design against: intermittent solar generation, finite battery
capacity, possible low-voltage/brownout conditions, intermittent WAN,
local-first operation, store-and-forward synchronization, energy-aware
capture/processing, and optional independent power supervision (see
"Independent Power / Node Supervisor" under Gate E, above). Energy-aware
product direction -- recorded here as future capability direction only,
not current implementation, and not a full energy-management subsystem
designed now:

- degraded operating modes under low energy;
- prioritize capture/evidence/truth over optional inference/analytics
  when energy-constrained;
- postpone expensive optional processing -- not core capture or evidence
  preservation -- under the same condition;
- resume deferred work once power recovers;
- never sacrifice authoritative host-side truth merely to conserve node
  power -- the Camera Node stays replaceable field infrastructure, not the
  system of record, even under energy constraint (see "Cross-cutting
  roadmap invariants," below).

**Hardware progression, evidence-driven.** Pi 4/5 remains reference/
golden-path hardware. Next, if evidenced: a remote prototype using existing
Pi + LTE + storage + solar/battery. CM4/CM5 only after measured evidence
from that prototype. Custom carrier boards only after deployment evidence.
No custom SBC, modem, sensor, battery chemistry, solar controller, or
proprietary radio unless justified much later. Pi/CM is an implementation
ecosystem, not product identity (see "Scope-reopening rule," above).

**Deployment classes, one core.** Home/Property Observatory (primary
product), Remote Field Node (advanced field deployment, earned),
Research/Conservation Deployment (earned future capability) -- one
architecture, not forked products (see
[product-doctrine.md](product-doctrine.md) "Product profiles"). Research
credibility specifically requires evidence before the label is used:
~60-90+ day unattended deployments, no silent evidence loss,
coverage/sampling accounting, reliable timestamps, known deployment
configuration, model/provenance history, documented power/network behavior,
reproducible workflows, recoverable failures, disclosed detector/classifier
limitations, useful standardized exports, and fleet health where necessary.
Prefer roughly 3-5 external deployments (serious naturalist/large-property,
technically sophisticated user, ecology/conservation collaborator) as
external-demand evidence before custom field hardware.

**OSS / productization boundary.** The scientifically important core stays
open: Camera Node software, Observation/review/evidence semantics,
provenance, transport abstractions, store-and-forward, diagnostics,
power-aware logic, model lifecycle, benchmark methodology, export schemas,
provider profiles, reference configurations/BOMs. Possible later commercial
value: preassembled/tested hardware, enclosures, modem/antenna selection,
provisioning, updates, remote/fleet services, support, warranty,
replacement, installation. No artificial lock-in; MockingBird does not
become a commodity trail-camera hardware company.

**Audio.** Remains on the roadmap, not implemented. The canonical
design/consent boundary already exists and is more detailed than a one-line
mention:
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md)
"Audio-aware boundary" -- separate consent from video, cannot inherit
video's `armed` state, video privacy polygons are insufficient for audio,
off-by-default retention, BirdNET-family output would be suggestion-only
(never reviewed truth), video arming never enables audio capture. Future
direction otherwise: optional local microphones/audio providers, capability
reporting, retention, source-evidence provenance, audio model lifecycle,
ranked species/taxon evidence, eventual visual/audio/context fusion, safe
failure, human review authority throughout. Audio feeds Evidence →
Interpretation → Review Decision → Observation; it never creates a second
truth system. Nothing in current repository evidence moves audio into v0.1.

**Ecological export & sharing interoperability.** A real, working local
export exists today -- structured metadata/manifest export (JSONL +
taxonomy + skip-reasons + summary) built only from reviewed `ReviewLabel`
truth -- but it is reference-only (it points at local media paths; it does
not yet bundle/copy the actual media bytes). Camtrap DP, GBIF, eBird,
Wildlife Insights, Darwin Core, and iNaturalist interoperability do not
exist anywhere in the repository today (confirmed absent, not merely
undocumented) -- this is genuinely new post-v0.1 direction, not a
correction. External sharing always consumes data already permitted by the
existing reviewed-truth contract; do not build a second "human
verification" mechanism per destination. eBird: eventual assisted/reviewed
export where the checklist context is eligible under then-current eBird
rules -- no autonomous reporting of unreviewed machine detections, and
eBird's data model never becomes MockingBird's internal truth model. Camtrap
DP: the important standardized interchange target for autonomous
field/research deployments -- deployment/site, coverage/sampling,
timestamps, evidence/media, taxonomy, machine provenance, human review, and
events/observations should all be representable when this is built. GBIF:
future publication interoperability through Camtrap DP/Darwin Core where
appropriate. Wildlife Insights: a downstream interoperability target, not
something MockingBird replaces -- note this name collides with
MockingBird's own existing internal Wildlife Insights analytics panel
(`/analytics`); disambiguate explicitly in any future implementation, this
is not the same thing. Other legitimate destinations (iNaturalist, research
datasets): keep the architecture extensible; verify each destination's
actual current rules/API when actually built. None of this delays v0.1.

**Public benchmark / training governance.** See
[public-benchmark-governance.md](public-benchmark-governance.md) (new --
no dedicated governance existed before this pass beyond the internal frozen-
holdout/contamination rules already in
[wildlife-detector-training-contract.md](wildlife-detector-training-contract.md)
and [detector-promotion-benchmark-contract.md](detector-promotion-benchmark-contract.md)).
Human review is required for training/reporting eligibility but does not by
itself grant public-release rights; benchmark/public-corpus licensing and
consent remain separately governed.

## Phase sequencing

A later phase may already have partial, opportunistically-shipped capability
(noted where applicable) without changing which phase currently governs
prioritization -- that remains the lowest-numbered phase whose exit
condition is not yet met.

This phase framework is the historical/structural record of how the
roadmap arrived here. For v0.1 release sequencing specifically, use "v0.1
release gates," above, as the authoritative answer to "what's actually
left" -- each phase's still-open, v0.1-relevant work maps onto one or more
gates there.

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

The former "Phase 24 hardening" sub-gates A-F (an unrelated, unlettered-in-
spirit internal checklist from that phase -- do not confuse with the v0.1
release gates A-G defined above) are superseded by this exit gate and by
[development-workflow.md](development-workflow.md)'s validation tiers.
Sub-gates A and D are substantially fulfilled by development-workflow.md
itself and by the entire Observation Engine v2 benchmark suite
(architecture.md), and sub-gate B is substantially fulfilled by the existing
Playwright suite (`web/e2e`: onboarding, the reviewed product loop, camera
controls, the Observation panel). Sub-gate C (targeted architecture seams)
is an ongoing practice, not a one-time gate. Sub-gate E's resource/failure
budgets are declared but not exhaustively field-verified -- part of "still
open," above.

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
- Redis, Kafka, or another message-broker/cache service adopted for
  architecture's own sake rather than a measured need
- Kubernetes, microservices, or a second primary database
- a custom optical-flow stack
- max-FPS continuous GPU inference
- complicated model ensembles
- a learned evidence selector
- continuous online retraining
- proprietary hardware architecture

## v0.1 non-blockers

Distinct from "Explicit deprioritization," above (the longer-standing
critical-path list): these specific items do not delay v0.1 release, absent
new empirical evidence that changes a real dependency --

LTE, solar, battery/BMS integration, managed PoE, custom CM hardware,
custom PCB, manufactured hardware, research-grade claims, advanced field
fleets, audio, eBird/GBIF/Wildlife Insights integration, persistent
individual ReID, every possible camera provider, a native mobile app,
perfect species classification, model ensembles, a custom global
classifier, sophisticated ecological forecasting, cloud services,
enterprise features, mandatory UPS, mandatory PoE, a mandatory managed
switch, dual-node redundancy, redundant boot media, a cloud fleet manager,
an A/B OS updater beyond what the existing update/rollback architecture
already provides (see "Update behavior" in
[camera-node-installer-design.md](camera-node-installer-design.md)),
power-budget-aware inference, specialized remote field-power hardware, and
automated/independent power-cycling or an external hardware supervisor for
the golden home path (see "External recovery boundary" and "Independent
Power / Node Supervisor" under Gate E, above) -- these remain techniques or
future options, not requirements, unless field evidence later elevates one
of them.

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
- Camera Nodes are replaceable field infrastructure, not the system of
  record: Place history, reviewed truth, Observations, and evidence
  provenance are durable on the host and must survive a Camera Node's
  failure, unavailability, or physical replacement -- see "Camera Node
  field hardware resilience / bad-boot recovery" under Gate D and Gate E,
  below.
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
- Detection, encounter reconstruction, and Visit correctness are the harder,
  higher-priority v0.1 gate; species identification needs to be useful and
  honest, not perfect -- see "Governing priority for v0.1," above.
- Reviewed truth is necessary for training/reporting eligibility but does
  not by itself grant public-release rights -- see
  [public-benchmark-governance.md](public-benchmark-governance.md).

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
