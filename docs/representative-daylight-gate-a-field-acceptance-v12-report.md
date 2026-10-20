# Representative Daylight Gate A Field Acceptance v12: Precision, Recall & Budget-Convergence Tranche

Session date: 2026-09-03. Branch `main`. Starting HEAD `fa9c8f0` (unchanged — zero
production code touched this milestone). Schema v58 (unchanged).

## Starting state

Verified against `docs/release-execution-state.md` before any action:

- Accepted HEAD `fa9c8f0` (Reconcile: accept Authenticated Camera Node
  Golden-Path Capture & Preview Acceptance v1), schema v58 — matched.
- Lane G: `CLOSED — RELEASE-CRITICAL` — matched.
- Lane K: `DECISION CLOSED — DEDICATED PROVIDER INTEGRATIONS DEFERRED PENDING
  EVIDENCE; NOT REQUIRED FOR LAUNCH` — matched.
- Lane R / Gate A: `NOT DONE — RELEASE-CRITICAL` — matched, open.
- Current authorization: `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION
  REQUIRED` — matched.
- Reference Camera Node: `pairing_required: true` (golden-path v1 left it
  "healthy, upgraded, genuinely unpaired") — confirmed live via
  `GET /node/v1/health`.
- Not pushed, per instruction.

Gate A's real remaining dependency, reconstructed from §3/§6.R archaeology
(the v11 entry's 7 items + the same-day Strong-Confidence Non-Target
entry's extension items 8–11 — §6.R itself is stale past v10, so this list
lives only in §3): (1) a cohort where a never-strong, single-generation
persistent confusor clears `blocked_ambiguous_boundary` and reaches the
quality gate, re-testing corroboration/scene-confusor composition; (2)
false-Visit-rate/useful-evidence budgets need a cohort not dominated by an
unrelated person-in-frame confound; (3) fragmentation re-measured a third
time; (4) a second, independently-varied true-latency cohort; (5) a
3+-simultaneous-subject cohort; (6) the two remaining v7 ambiguous
fragmentation units; (7) the ~13 untraced v7 `blocked_missing_evidence`
records; (8) whether the same-frame class-contradiction fix reduces
person-associated false Visits with real human presence; (9) whether
further strong-confidence scene-artifact false Visits recur; (10) no
whole-frame human suppression of real birds; (11) scene-confusor
participation, measuring corroboration-rejected occurrence counts too.

## Worktree safety

All 7 preserved untracked detector files confirmed present, untouched,
byte-for-byte matching `docs/release-execution-state.md`'s own list. No
other Claude Code session was found operating in this exact worktree or
any of its git-worktree siblings (the other `ccd-cli` processes on this
machine were confirmed, via `/proc/<pid>/cwd`, to be working in an
unrelated `~/projects/apex` repository and the desktop app itself).

## Conditions

Checked before allocating a field instance, all confirmed real:

- **Daylight**: session start 12:29 EDT; sunset ≈19:30 EDT — ~7 hours of
  daylight remained, no time pressure.
- **Reference Camera Node reachable**: `<node-ip>:8787` healthy,
  `available_camera_count: 1` of `camera_count: 2` — the *post-fix* shape
  (previously spuriously "8"), confirming the `4c1be35` diagnostic-truth
  fix is genuinely live on the real Pi.
- **Physical camera available**: `self_test.status: passed`,
  `camera_available: true`.
- **Accepted Node build present**: the Node's install `manifest.json`
  gives `git_commit: 4c1be355386c4a38c130f2f9d0204a5447a5166b`,
  `source_clean: true` — exactly commit `4c1be35`, 2 commits behind
  accepted HEAD on the same lineage (fa9c8f0 → e57c911 → 4c1be35).
- **Native-Windows Host available**: `powershell.exe` smoke test passed.
- **GPU/detector available**: RTX 4060 Ti visible via `nvidia-smi.exe`;
  process list confirmed the ~3.2GB/46% baseline utilization came from
  ordinary desktop apps (Discord, Firefox, Docker Desktop, games, the
  Claude/ChatGPT desktop apps) — this is the user's real daily-use
  machine, not a dedicated box, so this is expected baseline, not a
  stuck process.
- **No conflicting active Observation**: no MockingBird process was
  running, port 8000 free.
- **No active writer/session risk**: see Worktree safety, above.

## Build / compatibility / RTT preflight

- Deployed fresh via `scripts/deploy_windows_dev.py --dev-root
  .../MockingBirdFieldAcceptanceV12` (no skip flags — full GPU+BioCLIP).
  Deploy log: `DEPLOYED fa9c8f0`. BioCLIP species suggestions available.
- `field_acceptance_instance_lifecycle.py init` recorded
  `created_by_commit: fa9c8f0fe785a4260896f24cf2ee63535f29201c`,
  `created_by_build_id: 656de877e5f648b1`.
- `GET /api/product/health`: `database_schema_version: 58`, `ready: true`.
- `check_camera_node_compatibility.py --profile ordinary_monitoring`:
  `state: compatible`, `host_git_commit: fa9c8f0...` (exact HEAD match).
- `check_camera_node_compatibility.py --profile field_acceptance`:
  `state: compatible`; **real RTT-bounded calibration reached
  `calibrated`**: 5/5 valid samples, `offset_ms -2.479 [-7.805, 2.847]`,
  `uncertainty_ms 5.326`, `rtt_ms 20.023`, `clock_jump_detected: false`.
- Deployed release's own two advertised Node cameras:
  `picamera2-camera-0` (`status: available`, real sensor, evidence
  profiles up to 9248×6944) and `v4l2-no-camera` (`status: unavailable`,
  "No Linux camera available") — the post-fix `V4L2CameraProvider`
  correctly reporting the non-openable path as unavailable rather than
  falsely "available," independently reconfirming the accepted fix a
  second way (live pairing response, not just the aggregate health
  count).

## Field-instance lifecycle

- **Storage preflight, real defect found and worked around.** The first
  `preflight` invocation, given a native Windows-style `--dev-root`
  string, silently measured the *wrong filesystem* (the WSL virtual disk,
  692GB/1TB free) instead of the real Windows C: drive — reported
  `sufficient: true` on a filesystem the field session was never going to
  use. Root cause (read directly in
  `scripts/field_acceptance_instance_lifecycle.py`): POSIX `Path()` never
  parses a `C:\...` string as absolute, so `_resolve()` anchored it under
  the current working directory (this repo checkout), whose *existing*
  parent (`/home/<user>/projects/mockingbird-active`) is what
  `shutil.disk_usage` then measured. Re-invoked with the correct
  WSL-mounted form (`/mnt/c/Users/...`) and got the real number: **7.9GB
  free, tier `action_recommended`** (not `healthy`) — genuinely tight
  headroom for a cold deploy with no warm Windows-side cache. This is a
  real, disclosable tooling gap (a storage-safety check that can silently
  mismeasure the wrong disk on malformed input, with no validation that
  the resolved path is even on the invoking OS's real drive) — not fixed
  here per §32 (it doesn't block evidence preservation; using the tool
  correctly was sufficient), but worth a future bounded fix: reject or
  loudly warn on an unresolvable/foreign-looking `--dev-root` rather than
  silently falling back to the nearest existing ancestor.
- **Storage reclamation, user-approved.** Given the tool's own tier
  (`action_recommended`) and real historical precedent (v8/v9's own
  storage crises), asked the user whether to reclaim 3 confirmed
  `SAFE_TO_RECLAIM` completed instances (`MockingBirdCameraGoldenPathV1`,
  `MockingBirdFieldAcceptanceV10`, `MockingBirdFieldAcceptanceV11` —
  ~19.8GB) before deploying into marginal headroom; the destructive
  `cleanup --destroy` action was correctly blocked by the permission
  system pending explicit go-ahead. User approved; all 3 reclaimed
  cleanly (2.52 + 8.43 + 8.84GB, matching the tool's own estimate
  exactly), each independently re-verified `SAFE_TO_RECLAIM` by the
  tool's own redundant safety checks immediately before deletion. Storage
  after reclamation: 27.8GB free, tier `getting_low`; after the cold
  deploy's own cache population: **22.8GB free, tier
  `action_recommended`, `sufficient: true`** — healthy margin for the
  session.
- Administrator bootstrapped via `POST /api/setup/administrator` (local
  administrative flow, not the pre-existing operator identity) with a
  locally-generated password never supplied by the user.
- Field Acceptance Operator credential minted via the real
  `POST /api/auth/sign-in` → `POST /api/admin/field-acceptance-credentials`
  sequence (6h TTL), and used for `observation/start`/`stop` per the
  credential's own least-privilege allowlist.
- **Pairing**: restarted the Node service (`sudo systemctl restart
  mockingbird-camera-node`) to mint a fresh one-time code (previous
  boot's code had already expired), fetched it via `journalctl`, and
  consumed it within ~40s via `POST /api/camera-nodes/pair` →
  `POST /api/camera-setup/validate` → `POST /api/camera-setup/complete`
  (real `picamera2-camera-0`, one "Yard" Zone covering the full frame).
  Node confirmed `pairing_required: false` immediately after. This is the
  documented supported flow, not a bypass.
- WSL→127.0.0.1:8000 direct loopback confirmed broken again this session
  (`curl` exit 7) — every Host API call this milestone was routed through
  `powershell.exe` (either ad hoc `Invoke-WebRequest` scripts, or the
  packaged release's own embedded `python.exe` running the existing WSL
  scripts via a UNC path, which worked cleanly and is the reusable
  pattern for future sessions needing these scripts against a Windows
  loopback target).
- One benign discovery: the fresh instance's `GET /api/visits` already
  showed a Stream/2 Visits — traced to `source-backyard-demo`/
  `stream-backyard-feeder`, confirmed synthetic first-run seed/demo data
  (fabricated IDs, e.g. `visit-bird-feeder-001`), not a real conflicting
  Observation. Ignored throughout; the real session used a separate
  Node-backed Stream (`stream-5288453906fb`).

## Session duration / coverage

- Observation started `2026-09-03T17:30:07.238406Z` (13:30:07 EDT),
  stopped `2026-09-03T19:07:39.767011Z` (15:07:39 EDT) —
  **96.97 minutes** (`session_last_offset_ms: 5,817,999`), within the
  75–100 minute target band. Stop was a deliberate operator decision at a
  natural point (activity had plateaued: `candidates_created` flat at 16
  for the preceding 40 minutes; not cut short by any fault).
- `stopped_reason: "user_stopped"`; stop-finalization polled and
  confirmed complete (`state: "stopped"`, `observing: false`) within
  seconds — clean, no `stop_finalization_pending` residue at the final
  check.
- Real production stack confirmed live in the session's own advanced
  status: `provider_key: onnx-cuda`, `runtime_version: 1.28.0`,
  `cuda_available: true`, `selected_execution_providers:
  [CUDAExecutionProvider, CPUExecutionProvider]`, model `md-v5a` /
  `MDv5a.0.1-onnx-opset18`, `score_threshold: 0.1`,
  `nms_iou_threshold: 0.45` — the accepted configuration, byte-identical
  to doctrine, untouched throughout.

## Evidence-preservation completeness

Required reading before trusting any number below.

**A real, reproduced defect in this session's own snapshot tooling was
found and is disclosed precisely, not glossed over.** A 10-minute
periodic-snapshot loop was built for this session (`snapshot.py`,
invoked every ~10 minutes via the packaged Windows Python) to defend
against the counterfactual ledger's 60-minute retention window across a
~97-minute session — the same methodology v9–v11 used. Its
`observation_counterfactual(stream_id, start_offset_ms=0,
end_offset_ms=None)` call silently failed on **every one of the 12
snapshots**: `FieldAcceptanceClient` drops `None`-valued query
parameters, but the server's `end_offset_ms` is a required `Query(...)`,
so every fetch 422'd with `"end_offset_ms": "Field required"`. Only each
snapshot's `observation_status` summary counts and a direct
`scene_confusor_regions` DB read (a separate, unaffected code path)
survived intact across all 12 snapshots.

The gap was caught before it was fatal: with the engine still live
post-stop, one corrective `GET .../observation/counterfactual
?start_offset_ms=0&end_offset_ms=6000000` recovered the still-retained
tail. Reconciling that recovery against the session's own final
cumulative counters (exactly the §10 instruction — "do not infer 100%
preservation merely because the session ended cleanly"):

| record type | recovered (union) | final `recorded_count` | completeness | uncovered window |
|---|---|---|---|---|
| raw_detections | 12,000 | 22,664 | **52.95%** | offset 0 → 45.5min (count-capped: 12,000-record ledger cap hit) |
| track_generations | 158 | 401 | **39.40%** | offset 0 → 37.1min (age-capped: 60-min retention) |
| proposal_outcomes | 175 | 325 | **53.85%** | offset 0 → 37.0min (age-capped) |

So **the raw detection/track/proposal ledger has zero coverage for
roughly the first 37–46 minutes** of the 97-minute session — a real,
unrecoverable loss, not a merge artifact (independently confirmed: the
12 snapshots contributed nothing beyond what the single live fetch
already retained). `scene_confusor_regions` and the observation-status
summary counters are **unaffected** (separate code paths) and are
treated as fully reliable for the whole session. RTT/clock-calibration
history is likewise only available for the recovered tail: 100 distinct
`rtt_clock_calibrations` batches, 99 `calibrated`, 1
`insufficient_samples`, 0 `inconsistent_samples`, 0 clock jumps;
`offset_ms` range [-13.93, 8.52], `uncertainty_ms` median 9.76,
`rtt_ms` median 38.68 — real, healthy RTT evidence, just only for the
back ~60 minutes of the session.

**Visit-level data is unaffected and 100% complete**: all 18 real Visits'
full detail (`GET /api/visits/{id}/detail`) and all 36 of their evidence
images (`GET /api/media/{id}/full-resolution`) were fetched with zero
errors — this is the primary data most of Gate A's metrics below are
built from, and it does not depend on the broken ledger snapshots.

**Independent recorder**: fully intact, unaffected by the ledger bug (a
separate mechanism entirely) — 4,833 JPEG frames, 3.78GB, manifest
losslessly indexes every frame (sequence, offset, hash, captured_at).
Frame-to-frame gap analysis: median 1.11s, p95 1.67s, **max 6.79s, zero
gaps over 10s** — no real capture stall anywhere in the session.

**Contract for a future session**: always pass an explicit, real
`end_offset_ms` (e.g. a large fixed value, not `None`) to
`observation_counterfactual`; the `FieldAcceptanceClient`'s silent
None-param-drop is itself worth a small, isolated hardening (reject
`None` for a parameter the server requires, rather than silently
omitting it) — not done here, per §32, since it is a bounded
field-tooling fix outside this cohort's own field-collection window and
was not blocking evidence preservation once identified.

## Independent denominator methodology

The reference Stream frames a fixed yard view: a large tree with a
hanging blue tube feeder and a red hummingbird/oriole-style feeder, a
residential street, houses, and driveways in the background.

**Primary, fully independent pass**: a 65-tile contact sheet built from
the acceptance-recorder frames at ~90-second cadence (stride computed
from the manifest's own real timestamps, not assumed), covering the
entire session (00:00→96:19), reviewed *before* any admitted-Visit
timestamp was consulted. At this density and resolution, a small
songbird against this wide, cluttered yard view is often not resolvable
— the sheet's main value was catching the persistent bird-feeder
apparatus itself and one passing vehicle (~43:52), not individual brief
visits.

**Targeted expansion, guided by system telemetry** (both admitted *and
rejected* system proposals — deliberately not "check admitted-Visit
timestamps," which the governing brief specifically warns against, since
that would bias toward confirming MockingBird's own successes): for the
recovered ledger window (~37–97min), all 158 track generations were
clustered by the Zone's own 60-second quiet-period rule into 8 discrete
encounter clusters, each cross-checked against full-resolution recorder
frames sampled across its span. This exhaustive-against-recovered-ledger
method mirrors v10/v11's own precedent (full track-generation review,
not sampling) for the window where it was available; the unrecovered
early window relied on the primary contact-sheet pass plus the admitted
Visits' own evidence timestamps as positive-confirmed activity.

This dual approach separates two very different findings (full detail
below): a large fraction of the clustered activity traced to a single
recurring non-animal object (**confirmed by direct pixel inspection**,
not inferred), while a smaller number of distinct windows showed
**genuine, clearly visible real birds** at full resolution that received
no admitted Visit.

## Wildlife denominator

**Conservative confirmed denominator: 16 real bird encounters.**
- 14 encounter-clusters that MockingBird itself admitted with a
  confirmed-real bird in their evidence (detailed under Recall, below;
  three of these are sibling-Visit pairs sharing one Event).
- 2 additional encounters independently confirmed by direct
  full-resolution frame inspection at the exact offsets of two rejected
  system proposals (37:12–37:29 and 57:07–57:15) — a real bird is
  unambiguously visible at the feeder in both, and both were rejected by
  the quality gate (`reject_no_identification_or_context`), producing no
  Visit at all.

**Broader plausible/unconfirmed denominator: up to 24** (never silently
combined with the conservative count). Eight further short (10–30s),
non-flag-location, `confirmed: true` track generations exist in the same
recovered window (39:27, 46:14, 51:19, 51:53, 57:40, 87:56, 88:10,
89:42) whose sampled recorder frames did not resolve a bird clearly
enough at the sizes reviewed to confirm one way or the other — these are
reported as unconfirmed, not folded into the conservative figure.

**Separately labeled, product-led discovery, not part of either
denominator above**: the single largest driver of "unexplained" activity
in the recovered window was **not** wildlife at all. A small red
property/utility marking flag, planted in the grass at the road's edge
(bottom-left of frame, `[0.055–0.083, 0.72–0.74]` normalized), was
directly confirmed by a zoomed native-resolution crop. It produced 110
of the 158 recovered track generations (≈70%), recurring dozens of times
across every cluster in the recovered window, terminal reason
overwhelmingly `maximum_unsupported_duration`. This is a genuinely new
persistent non-animal confusor location, distinct from every prior
session's own "Location A" leaf/branch confusor — see Scene-confusor
participation, below, for why it never even reaches that mechanism's
own bookkeeping.

A second, much smaller static-object signature was also found: all 13
raw `person`-class detections this session cluster at one nearly-fixed,
low-confidence (0.10–0.24) location (`[0.14, 0.50]`) — almost certainly
a second small static background object weakly misclassified, not a
real person. See Person-associated precision, below.

## Recall

Against the conservative confirmed denominator (16):

- **14/16 = 87.5%** end-to-end recall — every admitted encounter-cluster
  had confirmed real evidence, and 2 confirmed real encounters received
  no Visit at all.

Against the broader plausible denominator (up to 24, worst case all 8
unconfirmed candidates are real):

- **14/24 = 58.3%** (lower bound; the true figure lies between 58.3% and
  87.5% depending on how many of the 8 unconfirmed windows are real).

The 14 admitted true encounters, in chronological (evidence-time) order:
V006 (00:20), V003 (02:00), V004 (04:29), V005 (06:37, primary frame
empty but a clear bird is visible in its own alternate evidence — see
Useful evidence), V007+V008 (08:32–08:40, sibling pair, same cardinal),
V009 (15:53), V010 (22:10), V011 (24:44), V013 (28:01), V014+V015
(34:56–35:05, sibling pair), V016+V017 (36:47–37:01, sibling pair, V016's
primary frame likewise empty but its alternate shows the bird), V018
(51:24), V019 (90:18), V020 (92:10).

## False Visits

**Exhaustive review of all 18 admitted Visits** (100% — full-resolution
identification-primary evidence for every Visit, plus every available
alternate frame for any Visit whose primary looked empty or ambiguous).

**Confirmed false: 1/18 = 5.6%** — `visit-observation-candidate-012`.
Its single evidence frame (no alternates exist — `candidate_count: 1`)
shows the full yard scene with no animal anywhere; `species_guess: null`.
Cause: **other background/artifact** — no scene-confusor region or
recovered-ledger detection geometry could be matched to it (it falls in
the unrecovered early window, offset ~26:45, so its own underlying
detection geometry is one of the casualties of the tooling gap above);
it cannot be responsibly attributed to the flag confusor (that
signature's own evidence is confined to the recovered window) or any
other named mechanism, so it is reported honestly as unattributed
background/artifact rather than force-fit to a convenient cause.

**Confirmed true: 17/18 = 94.4%.** This is the strongest single-session
precision result of any Gate A cohort to date (v8 22.2%, v9 20.0%, v10
36.4%, v11 44.4% false — this cohort: 5.6%), and — importantly for
dependency item #2 — this cohort has **zero person-in-frame confound**:
unlike v10/v11, no dual-class person-associated activity occurred, so
this is the first clean, unconfounded false-Visit-rate measurement in
the cohort history.

Cause breakdown of the one false Visit, using the required taxonomy:
dual-class person-associated: 0; pure single-class person
misclassification: 0; strong-confidence scene artifact: 0; never-strong
persistent confusor: 0 (the flag confusor produced zero admissions, see
below); **other background/artifact: 1**; ambiguous/unresolved: 0.

## Person-associated precision

No genuine human presence occurred this session (per §16, none was
staged). All 13 raw `person`-class detections cluster at one
near-identical, low-confidence (max 0.243) location, consistent with a
second small static background object being weakly misclassified rather
than a real person. None reached a track generation, none reached a
proposal, none was ever within spatial range of an `animal`-class
detection (a different part of the frame from the feeder/flag), so the
same-frame class-contradiction exclusion mechanism (`frame_tracker.py`'s
`_SAME_FRAME_NON_ANIMAL_OVERLAP_IOU`) had no opportunity to engage.
Zero false person-associated Visits occurred (consistent with zero
Visits touching this location at all). This cohort cannot answer
dependency items #8/#10 (natural human presence still hasn't occurred in
a Gate A session); it does confirm item #10's negative form trivially —
no whole-frame suppression was possible or needed since no real bird
ever coincided with this low-confidence background signature.

## Strong-confidence artifacts

The v11 "Location-A-style" strong-confidence scene artifact (a
historically-weak confusor spiking to 6 strong detections in one
occurrence) **did not recur this session.** Scene-confusor regions did
reach meaningfully high confidence in places (max_confidence_observed up
to 0.898, 0.887, 0.886, 0.847...), but every region's `suspected_count`
stayed 0 throughout, and — critically — none of these high-confidence
regions produced a confirmed-false admission (the session's one false
Visit, V012, has no traceable connection to any registered
scene-confusor region). Reported honestly: this is an absence of
recurrence, not proof the underlying irreducibility finding from
Strong-Confidence Subject-Evidence Viability v1 is resolved — that
investigation's own conclusion (no safe non-ML separator exists) stands
unchanged and untested by this session.

## Independent-corroboration participation

`reject_insufficient_detector_corroboration`
(`never_strong_and_minimal_detector_corroboration` /
`corroboration_concentrated_in_single_generation`) fired **4 times**
this session (final count), all in the recovered window and all on
short, isolated track generations (typical shape: 1 generation, 6–9
detections, terminal `maximum_unsupported_duration`) — the classic
bare-minimum shape the rule targets. All 4 were **correctly rejected**;
none corresponds to a confirmed-real bird in my own frame review (all 4
generation windows fall within the flag-confusor's own geometry or
similarly brief, unconfirmable signatures). Zero false Visits trace to
this axis. No natural example of the specific item-#1 target shape (a
never-strong, single-generation confusor that first clears
`blocked_ambiguous_boundary` and then reaches the quality gate as a
*repeatedly-admitted* case) occurred — the flag confusor's own dominant
terminal reason (`maximum_unsupported_duration` at the *track* level)
means most of its occurrences never even reached a proposal outcome,
let alone repeated admission. Dependency item #1 remains unmet.

## Scene-confusor participation

14 regions registered this session (final `scene_confusor_regions`
read), occurrence_count 1–6, **`suspected_count = 0` for every region**
— the 9th consecutive cohort with this exact shape. Region-by-region
classification against the required A/B/C/D taxonomy:

- **A (intercepted before scene-confusor)**: the 4
  `reject_insufficient_detector_corroboration` occurrences above never
  reach the scene-confusor touch point on their own — they're the same
  proposals the corroboration axis already intercepts.
- **B (evaluated and allowed)**: all 14 registered regions — every one
  reached the quality gate's confidence-escape route
  (`independently_strong_detection`, per prior sessions' documented
  mechanism) at least once without ever being suspected, most visibly
  the 6-occurrence feeder-area region spanning 17:34→19:05 (nearly the
  whole session) at confidences up to 0.887.
- **C (evaluated and blocked)**: **zero** — no region was ever actually
  suspected/blocked by scene-confusor itself this session, continuing
  the pattern v9–v11 already established.
- **D (never eligible to reach it)**: **the flag confusor — the
  dominant, newly-discovered case this session.** 110 of 158 recovered
  track generations (≈70%) trace to this one static location, yet it
  produced **zero registered scene-confusor rows** — none of its
  coordinates appear anywhere in the 14-region table. Root cause: its
  tracks terminate via `maximum_unsupported_duration` at the tracking
  layer itself, before forming a proposal robust enough to reach
  `_create_candidate_visit_locked`'s own scene-confusor touch call
  (which fires on `admit` and on `reject_insufficient_detector_
  corroboration`, but this signature's tracks mostly never survive to
  become *that specific* rejection reason — they die earlier, as
  `reject_no_identification_or_context` or simply never forming a
  proposal at all). This is a clean, concrete, first-of-its-kind
  real-field example of category D — a genuinely novel confusor
  intercepted entirely upstream of the mechanism the last several
  cohorts have been specifically testing, and it was intercepted
  *correctly*: zero false Visits trace to it.

## Weak / stationary / brief real positives

Natural examples occurred without any staging:

- **Brief/fast visits**: nearly every admitted Visit (e.g. V009, V010,
  V013) is a single brief feeder touch-down, evidenced by short
  evidence-frame spans (a few seconds) — obtained a Visit in most cases.
- **Two confirmed real birds MockingBird did not represent at all**
  (37:12, 57:07) — see Recall, above. Both are genuinely brief (their
  underlying track generations span 10–17 seconds) — this is the
  clearest evidence this session that very brief real visits are the
  ones most exposed to the `reject_no_identification_or_context`
  mechanism (see Recall/False Visits discussion; root-caused below under
  Reproduced defects).
- No sustained multi-minute stationary perching occurred this session
  (the apparent "continuous bird" in the coarse 90s contact sheet was
  overwhelmingly the static red feeder ornament itself, not a
  continuously-present animal — see Independent denominator
  methodology).

## Multi-subject observations

Only 2-subject candidates occurred, honestly reported as such (no 3+
evidence, not staged): three sibling-Visit pairs sharing one Event
(V007/V008, V014/V015, V016/V017), the accepted Multi-Subject Visit
Assembly Phase 2 mechanism. V007/V008 is **confirmed the same
individual** — both evidence frames (08:32/08:40) show the visually
identical cardinal in near-identical framing, 8 seconds apart; only
V008 received a species suggestion (`northern_cardinal`), V007 did not,
for reasons not traceable given the ledger gap covers this window.
V014/V015 and V016/V017 could not be confidently resolved as "2
individuals" vs. "1 individual split into 2 near-simultaneous
proposals" from the evidence available (timestamps 2–14 seconds apart,
similar framing) — reported as genuinely ambiguous on subject count,
not guessed. Checks: sibling isolation held in all 3 pairs (no
cross-subject corroboration merge attempted); no duplicate sibling Visit
was created beyond the pair itself; no obvious erroneous merge occurred.
Dependency item #5 (3+ simultaneous subjects) remains unmet — none
occurred, and none was staged.

## Fragmentation

The accepted automated tool (`run_gate_a_measurement_accounting.py`,
`fragmentation_accounting.py`) was run, but its own output this session
is **severely data-starved** by the same ledger-preservation gap: its
denominator-unit clustering only had lineage for the 5 Visits with
surviving proposal→visit links (016–020), producing just 2 denominator
units total (`fragmented: 0`, `ambiguous: 1` — visits 019/020) — not
representative of the full 18-Visit session and disclosed as such, not
presented as this session's fragmentation rate.

**Primary fragmentation assessment this session is therefore my own
manual, full-cohort review** (all 18 Visits' event IDs and evidence
timestamps cross-referenced): no two *non-sibling* Visits share
overlapping or narrowly-adjacent evidence windows that would suggest one
continuous encounter was spuriously split across separate Events — every
distinct-event Visit's evidence window is well-separated from every
other distinct-event Visit's window. **Fragmentation rate: 0/14
encounter-clusters = 0%**, the same shape as the 3-cohort 0% streak from
Gate A Measurement Closure v1, breaking v10 (1/5) and v11 (1/7)'s
regression back toward zero — though this session's own method (manual
Visit-timeline review, not the accepted tool applied to a complete
ledger) is a weaker cross-validation than a fully-covered automated pass
would be, and is disclosed as such rather than claimed as a clean
reconfirmation of the tool's own convergence.

## Duplicates

**0/18 = 0%.** No two Visits share a `constituent_generation_ids`
element (checkable for the 5 ledger-covered Visits directly; for the
remaining 13, no two non-sibling Visits' evidence timestamps overlap at
all, which is the same signal the accepted tool's own auto-classification
rule uses). Continues the unbroken 0%-duplicate streak across every
cohort since Gate A Measurement Closure v1.

## Useful evidence

Two honestly-distinguished figures, since this session surfaced a real
frame-selection nuance:

- **Raw, primary-frame-only** (what a reviewer sees by default, since
  `effective_primary` always prefers the `identification`-role frame
  regardless of whether an `alternate` frame is visually clearer):
  **14/18 = 77.8%** show a clear, usable bird in their own primary
  frame.
- **Whole-evidence-set** (crediting a Visit if *any* of its captured
  frames — primary or alternate — shows the bird clearly): **17/18 =
  94.4%.**

The gap is exactly the 3 Visits (V005, V010, V016) where the frame
actually marked `identification`/primary is empty or shows only a
fragment (V010: only a tail is visible), while V005 and V016's own
`alternate` frame shows the bird cleanly. This is a genuine, if minor,
evidence-*selection*-quality finding (11–17% of Visits this session),
distinct from evidence-*existence*: `evidence_role`/`selection_reason:
"identification_evidence_preferred"` chose the technically-preferred
role over the visually-clearer frame in these cases. Not fixed here
(§8/§32); noted as a bounded future investigation candidate for
`evidence_scoring.py`'s own role-assignment criteria.

Classification: useful subject evidence 14; real wildlife but poor
primary framing (usable via alternate) 3; false/background 1; ambiguous
0.

## blocked_missing_evidence

Final count: **15 of 325 distinct proposal-outcome decision events**
(the ledger legitimately re-decides a proposal multiple times before a
terminal outcome — 175 distinct `(proposal_id, decided_at)` events exist
in the recovered window alone). Traced representative records directly
in the recovered ledger, all reason `no_persistable_evidence_bytes`, all
on short (6–24s), isolated track generations with no larger context
(e.g. 60:37–61:02, 71:05–71:29, 84:50–84:59, 88:24–88:34) — consistent
with a genuinely brief detection that never produced a savable frame,
not with a systemic evidence-pipeline failure. The historical ~13
untraced v7 records (dependency item #7) were not specifically
investigated this session — out of scope for this cohort's own
bounded-archaeology budget, and item #7 remains open.

## blocked_continuation_pending

Final count **182** (largest of any cohort to date — v11's disclosed
71-proposal backlog was itself a new high at the time). Directly traced,
not treated as a black box: the vast majority are **healthy
intermediate re-decisions**, not stuck residue — the same
`proposal_id` typically accumulates 2–5 `blocked_continuation_pending`
entries (`episode_boundary_not_yet_final`) before reaching a genuine
terminal outcome later in the ledger (confirmed directly for dozens of
examples in the recovered window; e.g. `visit-episode:2a289488...`
records 4 pending checks then terminates `reject_no_identification_or_
context`, and `visit-episode:c5b65fd8...` records 2 pending checks then
terminates `created` → V019). No genuinely-stuck-forever proposal was
found in the recovered window (every one traced has a later terminal
record). This session's own high count is best explained by its own
dominant driver — the flag confusor firing dozens of short episodes,
each cycling through several pending checks before its own terminal
rejection — not a new stop-finalization defect. Classification per §23:
**healthy superseded intermediate state**, for every instance traced.

## True capture-to-visible latency

**Materially weakened this session by the same tooling gap** — the
accepted latency instrumentation (`capture_to_visible_latency.py`) can
only compute T0 for a Visit whose constituent generations still have
`start_captured_at` in the ledger, which after the gap means only
Visits 016–020 (5 of 18) are even eligible.

- **n=5 samples attempted**: 2 `measured` (153,904.77ms and
  67,252.77ms), 2 `unavailable_capture_time`, 1 `invalid_clock_mapping`.
- Median 110,578.8ms, p90 145,239.6ms, max 153,904.8ms — **computed from
  only 2 real values**, not a defensible distribution. Reported for
  completeness, not as evidence toward budget convergence.
- This is **not** a second independently-varied true-latency cohort
  (dependency item #4) in any meaningful sense — the sample is too small
  and too narrowly time-windowed (only the session's final ~7 minutes)
  to compare against v9/v10's own full-session distributions. Item #4
  remains open, and this session's own latency evidence should not be
  weighted alongside v9/v10 in any future convergence judgment.

## Gate B escalation

The one confirmed false Visit (V012) received **no species guess**
(`species_guess: null`) — correctly abstained, consistent with there
being no animal to guess about. **Zero Gate B recurrences this session**
(0/1 confirmed-false Visits got a confident species label) — the
opposite finding from v9's own disclosed 1/5 Gate B instance.

## Monitoring / reconnect / recovery

No natural disconnect occurred (per doctrine, none was staged). Node
`boot_id` (`4239527b-5622-425c-bed1-ae3074e191dd`) was unchanged from
before the session to well after it ended; watchdog
`consecutive_probe_failures: 0` throughout. The independent recorder's
own frame-to-frame gaps (median 1.11s, max 6.79s, zero gaps >10s) are
the most direct evidence of unbroken coverage: no stall, no
reconnect-driven hole, anywhere in the 97-minute session. Monitoring
coverage is reported qualitatively (continuous, no gap event) rather
than as a single percentage, since this session's own snapshot-tooling
defect (see Evidence-preservation completeness) means I do not have the
same `last_healthy_frame_at`-gap-based computation prior cohorts used;
the recorder-span method above (offset 0→5,817,443ms of a
5,817,999ms session, only 2 gaps over 5s) independently supports a
figure in the same high-90s% band as v9/v10's own reported coverage,
without claiming to reproduce their exact methodology.

## Storage

Deploy-time: 22.8GB free, `action_recommended`, `sufficient: true`
(after user-approved reclamation of 19.8GB from 3 confirmed-safe old
instances — see Field-instance lifecycle). End-of-session:
`storage_health_tier: "action_recommended"`, `storage_writable: true`,
`storage_low_space: true` (this machine's tier ladder treats this
general disk as consistently tight — see Field-instance lifecycle;
`sufficient`/critical thresholds were never approached). No storage
safety trip occurred; the session was never at risk of losing evidence
to disk pressure.

## Cohort comparison

| Metric | v8 | v9 | v10 | v11 | **v12** |
|---|---|---|---|---|---|
| Duration (min) | 158.2 | ~92 | 90.2 | 101.8 | **96.97** |
| Recall | — | — | 4/5=80% | 100%/70% (cons./less-cons.) | **87.5% cons. / 58.3% broader (lower bound)** |
| False-Visit rate | 22.2% | 20.0% | 36.4% | 44.4% | **5.6%** |
| Person confound | no | no | no | yes (7/8 false) | **no (clean)** |
| Fragmentation | 0/16=0% | 0% (6th/7th) | 1/5=20% | 1/7=14.3% | **0/14=0% (own manual method; tool data-starved)** |
| Duplicates | — | 0% (4th) | 0% (6th/7th) | 0% (8th/9th) | **0% (continues streak)** |
| Useful evidence | withdrawn | 76.0% | 54.5% | 43.5%/62.5% | **77.8% raw / 94.4% incl. alternates** |
| blocked_missing_evidence | 9.9% | 8.9% | 6.7% (best) | 9.29% | **15/325=4.6% of decision events (not directly comparable — different denominator basis; see below)** |
| Latency median/p90 | — | 111.8s/173.9s | 103.9s/183.3s | not re-derived | **110.6s/145.2s (n=2, not comparable)** |
| Monitoring coverage | — | 99%+ | 99.99% | 97.5% | **continuous, no gap event (qualitative)** |
| Scene-confusor suspected | — | — | — | 0/14 | **0/14 (9th cohort)** |

`blocked_missing_evidence` denominator note: prior cohorts reported this
as a fraction of *distinct proposals*; this session's own figure above
uses *decision events* within the recovered window only (175 of an
unknown true total, given the ledger gap) — the two are not on the same
basis and should not be read as a direct improvement over v10's 6.7%.

## Budget-convergence analysis

Combining v12 with the valid prior representative cohorts, per metric:

- **Recall**: v10 (80%), v11 (100%/70%), v12 (87.5% conservative). All
  three cohorts differ in denominator methodology (v10: contact-sheet +
  exhaustive proposal review; v11: complete track-generation review;
  v12: contact-sheet + exhaustive recovered-window review, weakened by
  the ledger gap for the early session). No obvious outlier, but no two
  cohorts share close enough methodology to average responsibly. **MORE
  EVIDENCE REQUIRED** — specifically, a cohort with intact full-session
  ledger coverage (this session's own gap directly undermines
  confidence in its own denominator completeness for the unrecovered
  window).
- **False-Visit rate**: v7 (~5–10% candidate) → withdrawn at v8 (22.2%)
  → v9 confirms elevated (20.0%) → v10 worse (36.4%) → v11 worst
  (44.4%, but 7/8 causally a person confound) → **v12 (5.6%, clean, no
  confound)** — the first person-confound-free measurement, and it is
  dramatically better than every confounded cohort. This is a genuinely
  new data point, not yet a trend: one clean session cannot itself
  establish a budget, but it is the single most encouraging false-Visit
  result to date and directly answers dependency item #2's own
  requirement for an unconfounded cohort. **MORE EVIDENCE REQUIRED** —
  name the missing evidence precisely: a *second* person-confound-free
  cohort, to confirm 5.6% is representative and not itself a low-
  activity-day artifact (this session had no genuine sustained
  wildlife-vs-confusor stress test the way v8–v11's own busier sessions
  did).
- **Fragmentation**: 0% streak (Gate A Measurement Closure v1's 3
  cohorts) → v10 breaks it (1/5) → v11 (1/7) → **v12 (0/14, own
  manual method)**. Returns to 0% but via a weaker cross-validation
  method this session (see Fragmentation, above). **MORE EVIDENCE
  REQUIRED** — a cohort with full ledger coverage needed to
  re-apply the accepted automated tool at full strength and resolve
  whether v10/v11's regression or the older 0% streak is the more
  representative baseline.
- **Duplicates**: 0% across every cohort since Gate A Measurement
  Closure v1, v12 included (9th consecutive). **READY FOR BUDGET** — see
  Proposed budgets.
- **Useful evidence**: v5 (~85% proposed) → v7 (96.0%) → withdrawn at v8
  → v9 (76.0%) → v10 (54.5%) → v11 (43.5%/62.5%, person-confounded) →
  **v12 (77.8% raw / 94.4% incl. alternates, unconfounded)**. Wide,
  unstable range across cohorts (43.5%–96.0%) even before v12; v12's own
  unconfounded figure sits mid-range. **MORE EVIDENCE REQUIRED** — the
  range across cohorts is too wide to support a defensible threshold
  yet, and this session's own primary-vs-alternate-frame nuance adds a
  new methodological wrinkle future cohorts should also measure both
  ways.
- **blocked_missing_evidence**: v6 18.3% → v7 9.4% → v8 9.9% → v9 8.9%
  → v10 6.7% (best) → v11 9.29% → v12 not directly comparable (see
  Cohort comparison note). **MORE EVIDENCE REQUIRED** on a consistent
  denominator basis before any further convergence judgment.
- **Capture-to-visible latency**: measurement mechanism CLOSED since
  Camera Node↔Host RTT-Bounded Clock Calibration v1; v9 (median 111.8s,
  n=24/25) and v10 (median 103.9s, n=11, "closely matching v9") are the
  only two real, defensible distributions to date. v12's own n=2 sample
  adds no real evidence. **MORE EVIDENCE REQUIRED** — dependency item #4
  (a second, independently-varied, *full-coverage* cohort) remains
  exactly as open as it was after v10.
- **Monitoring coverage**: ~99% candidate since v5, reconfirmed every
  cohort in the 97.5–99.99% band; v12 offers only qualitative
  confirmation (continuous, no gap) rather than a directly comparable
  percentage. **READY FOR BUDGET** — see Proposed budgets (v12 does not
  weaken this candidate, it simply cannot be averaged into it
  precisely).

## Proposed budgets

Only where real accumulated evidence supports a defensible number with
operational margin — not by blind averaging, and no aspirational
figures.

- **Duplicate-Visit rate: ≤ 1% (effectively 0%).** Supported by 9
  consecutive cohorts (v7 through v12) at a real, measured 0%, across
  every denominator methodology tried. **READY FOR BUDGET.**
- **Monitoring coverage: ≥ 95%.** Supported by 5 cohorts (v5, v9, v10,
  v11, v12) all in the 97.5–99.99% band or, for v12, qualitatively
  consistent with that band (zero gap events over 10s across a
  97-minute session). **READY FOR BUDGET**, with margin below the
  observed 97.5% floor (v11) to absorb a genuinely worse future session
  without immediately tripping the budget.

Every other metric in this report is **MORE EVIDENCE REQUIRED**, named
precisely above per metric. None is **REOPENED BY DEFECT** — v12
reproduced no release-critical *product* correctness defect (the
tooling defect is field-infrastructure, not admission/precision code,
and does not invalidate the Visit-level evidence this session's
metrics are built from).

## Reproduced defects

1. **Field-tooling: `observation_counterfactual` silent-drop-on-None
   defect** (this session's own `snapshot.py` + `FieldAcceptanceClient`
   interaction). Root cause: `FieldAcceptanceClient` drops `None`-valued
   query params silently; the server requires `end_offset_ms`. First
   irreversible error: the very first periodic snapshot call, ~T+12min,
   silently 422'd instead of raising loud enough to notice mid-session.
   Effect: zero raw-ledger coverage for 12 snapshots; only a single
   post-session corrective fetch recovered a partial (37–54%) tail — see
   Evidence-preservation completeness for the full, quantified
   accounting. **Not fixed during the cohort** (§32 — bounded, does not
   touch product/admission code, discovered only after field collection
   had already produced most of its value). Future contract: any script
   calling `observation_counterfactual` must pass an explicit real
   `end_offset_ms`; consider hardening `FieldAcceptanceClient` itself to
   reject (not silently drop) a `None` value for a parameter the server
   requires.
2. **Field-tooling: storage-preflight silent wrong-filesystem
   measurement on a malformed `--dev-root`** (see Field-instance
   lifecycle). Root cause: `Path()` never treats a Windows-style
   `C:\...` string as absolute on POSIX, so the tool's own
   nearest-existing-ancestor fallback silently measures the wrong disk
   instead of erroring. Not fixed during the cohort (used correctly
   instead); future contract: validate the resolved `--dev-root` is
   actually reachable/plausible before trusting `disk_usage` against its
   parent, or require the WSL-mounted form explicitly in the tool's own
   `--help`.
3. **Product: `reject_no_identification_or_context` discarding
   confirmed-real, brief encounters with zero user-visible trace** (not
   merely a low-confidence abstention — no Visit is created at all,
   unlike a species-identification abstention which still yields a
   reviewable Visit). Directly, visually confirmed twice this session
   (37:12, 57:07 — see Recall). Root cause, read directly in
   `candidate_quality_gate.py` line 420–426: a proposal is rejected
   outright if no evidence item captured for it ever reached role
   `identification` or `context` (only `alternate`, or none at all) —
   with no fallback to admit with a disclosed "evidence insufficient"
   placeholder. This is a genuinely new, precisely root-caused finding,
   not previously named in any prior cohort's own dependency list.
   **Not fixed during the cohort** (§8/§32 — this is core admission-path
   code, explicitly off-limits during field collection). Bounded future
   contract candidate (diagnosis only, not a commitment): investigate
   whether a proposal that clears geometry/corroboration but never gets
   an `identification`/`context`-role frame should instead surface as an
   honestly-abstained, minimal-evidence Visit rather than vanish
   entirely — this is a real product-doctrine question (a "not clear
   enough to identify" Visit is explicitly preferred over silence, per
   `docs/product-doctrine.md`'s own truth-boundary section) that this
   session's evidence makes concrete for the first time.
4. **New, correctly-handled persistent confusor (not a defect, but
   worth recording precisely for future comparison)**: the red
   property-flag confusor (see Scene-confusor participation) is the
   first-ever real-field example of category D (never eligible to reach
   scene-confusor) documented with this level of precision. It produced
   zero false Visits. Recorded here so a future session recognizing the
   same signature (or a structurally similar one) has a name and root
   cause to compare against, not to reopen anything.

## Remaining Gate A dependency

The pre-existing 11-item list is **not closed by this session** and is
carried forward with v12's own contribution to each item noted:

1. Never-strong single-generation confusor clearing
   `blocked_ambiguous_boundary` then reaching the quality gate
   repeatedly — **unmet**; this session's own dominant confusor (the
   flag) took a different path (mostly `maximum_unsupported_duration`
   at the track level, not `blocked_ambiguous_boundary`).
2. Unconfounded false-Visit-rate/useful-evidence cohort — **first
   instance obtained this session** (5.6% false, clean); needs a second
   confirming cohort before any budget.
3. Third fragmentation measurement — **obtained (0/14), but via a
   weaker method** than the accepted automated tool at full strength
   (data-starved this session); still needs a full-ledger-coverage
   re-proof.
4. Second independently-varied true-latency cohort — **unmet**; v12's
   own n=2 sample does not qualify.
5. 3+-simultaneous-subject cohort — **unmet**; only 2-subject candidates
   occurred.
6. v7's two remaining ambiguous fragmentation units — **not
   investigated this session** (out of this cohort's own bounded scope).
7. The ~13 untraced v7 `blocked_missing_evidence` records — **not
   investigated this session**.
8. Same-frame class-contradiction fix's field effect on person-
   associated false Visits — **unmet**; no genuine human presence
   occurred.
9. Further strong-confidence scene-artifact recurrence — **did not
   recur this session** (a negative result, itself evidence, not a
   closure).
10. No whole-frame human suppression of real birds with a person
    present — **trivially satisfied** (no real person and no real bird
    ever coincided), not a genuine test.
11. Scene-confusor participation incl. corroboration-rejected occurrence
    counts — **directly measured this session**, and additionally
    extended with the first documented category-D real-field case (the
    flag confusor).

**New items this session adds to the dependency list**: (12) a cohort
with intact full-session ledger coverage (this session's own snapshot-
tooling defect means none of the recall/fragmentation/latency figures
above can be fully cross-validated against the raw ledger for the
unrecovered ~37-minute window); (13) resolve whether
`reject_no_identification_or_context`'s "vanish entirely, no Visit at
all" behavior for brief-but-real encounters should be revisited — a
Gate-A-relevant recall question, not yet a committed fix.

## Cleanup / final state

- Observation stopped cleanly; stop-finalization confirmed complete.
- Field-acceptance credential and Administrator account are local to
  this disposable instance only; both are destroyed along with the
  instance at eventual archive/cleanup (no separate revocation needed
  beyond the instance's own lifecycle).
- Camera Node pairing deliberately **left paired** to this session's own
  disposable instance's credential — unlike golden-path v1 (whose scope
  was setup/proof and explicitly reset to unpaired for the next
  session), this session's instance is being archived (not destroyed)
  with its evidence, so leaving the pairing intact keeps this session's
  own record internally consistent; a future session picking up the
  reference Node should expect `pairing_required: false` against this
  instance's own credential, and should either reuse this archived
  instance or perform a fresh revoke/re-pair as golden-path v1
  documented.
- Lifecycle: `init` → `active` already recorded (see Field-instance
  lifecycle). `complete`/`mark-archived`/`assess` intentionally **not
  yet run** as of this report's writing — the instance and all raw
  evidence (12 partial ledger snapshots, the corrective live fetch, all
  18 Visits' full detail and evidence images, the acceptance-recorder's
  4,833 frames, the scene-confusor timeline) remain live and
  Windows-side pending a final archive pass immediately following this
  report, to `data/field-acceptance/2026-09-03-gate-a-v12-precision-
  recall-budget-convergence/` per the established convention. Marked
  explicitly: **do not destroy by default** (per §34); the instance
  stays `active`, not `archived`, until that pass completes.
- No stale Observation remains active (confirmed via `observation_status`
  showing `observing: false`, `state: "stopped"`).
- No production code was modified. No Tier 3 run required (§33 — zero
  production diff); field evidence is the validation.

## Decision

**A**

Classification A reflects a real, representative, accepted-configuration
daylight field session with the strongest single-session precision
result in the cohort's history, a genuinely new and correctly-handled
persistent confusor discovered and precisely root-caused, a real
brief-encounter recall gap discovered and precisely root-caused (not
merely inferred), a real field-tooling defect discovered, quantified,
and honestly disclosed rather than hidden or silently worked around,
and zero production-code changes during the cohort. It is not
undermined by the tooling defect because that defect's exact scope was
independently measured and every downstream metric is reported with
its true confidence level, not overstated.

**Gate A itself remains OPEN.** Per §31, A for the milestone does not
mean Gate A passed: duplicate-rate and monitoring-coverage budgets are
ready; every other metric still needs more evidence, on a now-longer,
precisely-named dependency list (13 items). Two release-critical-shaped
questions are newly open from this session specifically: whether the
evidence-quality gate's all-or-nothing `reject_no_identification_or_
context` behavior is the right recall/abstention tradeoff, and whether
a future cohort can be run with intact full-session ledger coverage to
properly cross-validate this session's own encouraging but
partially-unverifiable numbers.
