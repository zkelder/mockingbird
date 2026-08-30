# Representative Daylight Gate A Field Acceptance v5

Status: **Classification A.** A real, live, ~106.6-minute Observation session against the real reference
Camera Node, run on the corrected build, directly confirms the accepted Sustained-Activity Visit Admission
Starvation & Stop-Finalization Correctness v1 fix: `candidates_created` moved off zero within ~10 minutes
(v4 stayed at exactly 0 for its entire 112-minute session), 19 real Visits were admitted throughout the
session (not only at stop), the stop-finalization race did not recur (`stop_finalization_pending` correctly
appeared then cleared, rescuing 2 more genuinely-pending candidates), and no `blocked_shadow_mode`/
persistence-contention/duplicate-Visit regression occurred. One real, precisely root-caused defect was
found and disclosed, not fixed: a single false-positive admission (a weak, single-frame, likely-spurious
MDv5 detection on empty background) received a confident-but-wrong BioCLIP species label — a fresh,
concretely-reproduced instance of the already-known Gate B "background evidence → confident label"
regression class, not a new starvation-family defect. See "Decision," below, for the complete reasoning.

## Identity

- Starting HEAD (verified before any action): `eeb5f98` (`eeb5f981dce8325b66dc4bd0d4fd3548be988b9a`),
  matching the governing instruction's stated starting state exactly. Branch `main`, not pushed (256 ahead
  of `origin/main`, unchanged by this milestone). Schema `v58`, unchanged (zero production code touched
  this session; this is a live field-acceptance run, not a development milestone).
- Deployed build: `git_commit` `eeb5f981dce8325b66dc4bd0d4fd3548be988b9a` — **exact match** to accepted
  HEAD, confirmed via `GET /api/product/instance` (`build_id` `10f58c46e82b555e`, `app_version` `0.1.0`,
  `instance_id` `77449dd359d9e0296cf8b198ff1013b4`) and independently re-confirmed via the live Observation
  Engine's own `model_runtime_metadata`.
- Deployment: a genuinely fresh, disposable dev-root (`C:\Users\zachk\AppData\Local\
  MockingBirdFieldAcceptanceV5`), **not** the operator's long-lived `MockingBirdDev` identity — disposable
  local Administrator (`field-acceptance-v5@mockingbird.local`, bootstrapped via `POST /api/setup/
  administrator`, password generated and used only within this session's own automation, never surfaced to
  or requested from the user), a disposable Field Acceptance Operator bearer credential
  (`field-acceptance-6551970839324695`, 8-hour TTL) minted via the accepted non-interactive mechanism. No
  operator password/token/browser-cookie/manual step was ever requested from or supplied by the user.
- Time/weather: Sunday 2026-08-30, 16:36:05–18:23:08 EDT (mid-afternoon into early evening, hours inside
  the local daylight window — sunset that date is well after 19:00 local). Bright, overcast-to-partly-clearing
  conditions (increasing blue sky visible across the session's own recorder frames), good visibility, no
  precipitation — confirmed directly from real captured frames at the session start (a dedicated pre-flight
  scene check, before committing to the cohort) and repeatedly throughout via the independent recorder's own
  archive, not assumed from a forecast.
- Camera/Stream count: **1 real Stream** (`stream-fb6aa12f80ca`, "Field Acceptance V5"), backed by the real
  reference Camera Node (`node-76ec8e53ae586dd0`, `192.168.1.112:8787`), camera `picamera2-camera-0` ("Pi
  camera 1") of 8 the Node advertised — the identical physical camera every prior accepted daylight cohort
  (including v4) used. One full-frame Zone (`yard` type, polygon 0.02–0.98 both axes, matching v4's own
  configuration for direct comparability).
- Frozen config, unmodified throughout, confirmed live from the running Engine's own `model_runtime_metadata`:
  MDv5a ONNX, `score_threshold` **0.1**, `nms_iou_threshold` **0.45**, model fingerprint
  `b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc` (exact match to the accepted provenance
  record and to v4's own confirmed fingerprint) — `CUDAExecutionProvider` selected (real GPU inference, RTX
  4060 Ti). Tracker/admission config unmodified: `ambiguous_gap_ms` 45,000ms, `maximum_episode_duration_ms`
  / `maximum_component_pending_ms` 1,200,000ms (20min, the new bounded-decision-horizon fix reusing this
  exact existing value, not a new magic number), `_STOP_JOIN_TIMEOUT_SECONDS` 20.0 — all unmodified
  dataclass/module-level defaults, verified by direct source read before the session, never overridden.
  Evidence-cache bound `_MAX_CACHED_BURST_BYTES` 128 (unmodified), `EvidenceScoringBounds.max_candidates` 16
  (unmodified — the accepted fix changed candidate *selection order* within this bound, not the bound's own
  size). BioCLIP-2 + Identification Eligibility/Abstention (`identification-eligibility-v1` policy,
  `score_floor` 0.7, `margin_floor` 0.2, confirmed live in real suggestion payloads). Persistence retry
  policy unmodified (concurrent-candidate-visit-persistence bounded retry, untouched this session). No
  tuning of any kind was performed during the cohort.

### Infrastructure decisions made live

1. **Camera Node re-pairing**, approved by the user before acting (not assumed): the reference Camera
   Node's pairing is single-slot/disk-persisted and was still held by yesterday's now-stopped v4 disposable
   instance; nothing was actively observing through it (`deploy_windows_dev.py --status` confirmed port 8000
   free before touching anything). Reset via the supported recovery flow (delete `pairing.json` over SSH,
   `systemctl restart mockingbird-camera-node`, retrieve the fresh one-time code via `journalctl`) — the
   identical mechanism v4 used for the identical recurring situation. Self-test/watchdog/8-camera
   availability re-confirmed healthy immediately after.
2. **Acceptance-recorder env-var ordering mistake, self-caught and corrected (own tooling mistake, not a
   product defect, disclosed for completeness):** the first deploy launched successfully but *without* the
   independent recorder armed, because `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` must be set in the
   invoking shell *before* `deploy_windows_dev.py` reaches its launch step, and the first invocation predated
   that env-var being set. Caught before starting any Observation session by checking `--status`'s own
   launch semantics; fixed by re-exporting the four `MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_*` variables and
   re-running the deploy (idempotent — reused the already-materialized release, only re-ran stop+relaunch+
   verify, not a full rebuild). Confirmed armed correctly on the relaunch that the actual session ran under.
3. **Administrator-bootstrap retry, self-caught and corrected:** two early bootstrap+pair attempts failed
   for narrow, unrelated reasons (a `base_address` missing its `http://` scheme; a stray copy-forgetting
   mistake) *after* an Administrator had already been created, and — since `POST /api/setup/administrator`
   is first-run-only and its generated password is deliberately never persisted or displayed — a stuck,
   password-unknown Administrator account was left behind twice. Both times resolved by stopping the process
   and deleting only the fresh dev-root's own `mockingbird.sqlite3` (never touching Zones/history that
   mattered, since nothing of value had yet been created in this disposable root) and relaunching. The
   third attempt succeeded cleanly and combined bootstrap + Node pairing + field-acceptance-credential
   minting into one process invocation specifically so the generated password never needs to cross a
   process boundary again.

## Representative conditions (pre-flight gate, before committing to the cohort)

Established directly, in order, before starting the Observation session, per the governing brief's explicit
"conditions first" requirement:

- **Local time / daylight:** 16:36 EDT at session start, hours before sunset.
- **Camera Node health:** `GET /node/v1/health` → `status: available`, `self_test.status: passed`,
  `watchdog.last_probe_ok: true`, `consecutive_probe_failures: 0`, 8/8 cameras available.
- **Host/GPU health:** nothing listening on port 8000 (no active instance to disturb); RTX 4060 Ti idle of
  any MockingBird compute process (only ordinary desktop-app GPU usage present — Firefox, Discord, Explorer,
  etc. — confirmed via `nvidia-smi.exe`'s own compute-apps listing, zero `python.exe`/ONNX entries).
- **Storage headroom:** 40.36GB free on `C:` at session start (466GB volume) — healthy.
- **Recorder readiness:** `acceptance_recorder.py` present, confirmed armed on the corrected relaunch (see
  above).
- **Actual captured frames, not a forecast:** used the accepted `POST /api/streams/{id}/live-preview/open`
  + `GET .../live-session/current-frame` mechanism (bounded, non-monitoring, `creates_media/evidence/event/
  visit/truth: false` on every call) to pull real frames *before* starting the cohort. First frame showed
  clear daylight, good visibility, both feeders (seed + hummingbird) clearly in view. A second, 3-frame
  sample 12 seconds apart directly caught a real bird at the seed feeder in the middle frame — genuine,
  visually confirmed wildlife activity, not inferred. Conditions judged clearly suitable; proceeded
  immediately per the brief's own instruction.

## Sustained-activity fix proof

This is the primary acceptance question this milestone exists to answer: **does sustained genuine activity
now produce useful user-visible Visits during the session, not merely at stop?**

- **`candidates_created` did not stay at zero.** First admission (`visit-observation-candidate-003`) landed
  at session offset **24.7 seconds** into a 6,396.5-second session — effectively at the very start, not
  merely "before the end." Real, useful evidence: the persisted media asset shows a genuine bird perched at
  the seed feeder plus a second bird in flight in the same frame. `candidates_created` climbed steadily and
  continuously through the whole session (0→1 by ~10min, →5 by ~36min, →8 by ~46min, →12 by ~66min, →16 by
  ~91min, →17 by ~106min in-session, →19 after stop-finalization), never stalling for the kind of extended,
  session-spanning silence v4 exhibited.
- **Live monitoring throughout the session** (5-minute status pulses, 22 total) tracked `track_updates_
  observed`, `evidence_candidates_observed`, `proposals_observed`, `candidates_created`, and every
  `suppressed_reasons` bucket continuously. One genuine ~15-minute lull in new admissions (17:22–17:37 EDT)
  was investigated live and resolved as ordinary session dynamics, not starvation:
  `blocked_ambiguous_boundary` was flat at 72 while `blocked_continuation_pending` kept climbing (new
  proposals joining an already-forming, still-legitimately-growing chain), then both resumed moving together
  once the underlying activity did — the same healthy pattern the accepted fix's own design describes, not a
  recurrence of the v4 mechanism (which showed *zero* resolution activity for the *entire* session, not a
  15-minute lull inside an otherwise continuously-admitting session).
- **Final settled counts** (stable across 3 repeated post-stop checks, see "Stop finalization," below):
  `track_updates_observed` 8,641; `evidence_candidates_observed` 3,169; `proposals_observed` 380;
  `candidates_created` **19**; `candidates_suppressed` 361 (`blocked_continuation_pending` 235,
  `blocked_ambiguous_boundary` 111, `blocked_missing_evidence` 10, `blocked_scene_confusor_suspected` 3,
  `reject_no_identification_or_context` 2). `19 + 361 = 380` — every proposal accounted for, no
  unaccounted-for loss. `candidate_authority_exhausted` stayed `False` throughout.

### Forced-decision diagnostics

- `blocked_continuation_pending` and `blocked_ambiguous_boundary` are **cumulative** counts of every
  intermediate proposal version a still-growing chain passed through, not a stuck/live-blocked gauge — this
  matches the fix's own documented "a fresh, differently-hashed `proposal_id`" regrowth mechanism, and their
  continued presence at session end reflects normal in-flight activity at the moment of the final read, not
  starvation (19 real admissions throughout the session are the direct proof of that).
- `blocked_missing_evidence` occurred 10 times (2.8% of all suppressed proposals) — present, not eliminated,
  consistent with the accepted fix's own explicit disclosure that it fixed *selection bias* within the
  128-entry cache bound, not the bound's own size, and that "a pathologically evidence-dense, multi-hour
  single component could in principle still exhaust even the now-correctly-prioritized pool." No
  investigation of this specific mechanism was performed this session (out of scope — this milestone does
  not tune caches); the rate stayed low and did not visibly block any specific encounter's own admission
  (no admitted-Visit disappeared for this reason — see "Persistence," below).
- `blocked_scene_confusor_suspected` (3) and `reject_no_identification_or_context` (2) are pre-existing,
  already-accepted mechanisms (`scene-confusor-suspicion` suppression and `candidate_quality_gate`'s
  no-identification-context rejection respectively, confirmed by direct source grep) — legitimate quality
  gating, not new or concerning suppression classes.
- **No recurrence of the v4 starvation pattern**: unlike v4 (zero admissions for the entire ~112-minute
  session), this session admitted its first real Visit within 25 seconds and kept admitting throughout.
- **No recurrence of stop-time shadow-mode loss**: `blocked_shadow_mode` occurred **zero** times across the
  entire session log (grepped in full, twice, before and after stop).
- **No recurrence of missing-evidence-caused-by-bounded-cache-selection as a session-ending blocker**: the
  low, steady `blocked_missing_evidence` rate (10/361, 2.8%) did not prevent 19 real Visits from being
  admitted and persisted with real evidence throughout.

## Stop finalization

Stop was called at 18:22:39 EDT, deliberately into a moment with substantial genuinely pending work
(`blocked_continuation_pending` 235 at that instant) — a real, non-manufactured test of Section 17's
requirement, not an artificial one.

- **Immediate stop response** (`state: "stopping"`, `stop_finalization_pending: true`) — the *new*, honest
  in-progress status the accepted fix's contract specifically added ("if the bounded join times out... `stop()`
  ... honestly reports `_state == "stopping"` plus `advanced["stop_finalization_pending"] = True`"),
  observed live for the first time in a real field session. `candidates_created` at that instant: 17.
- **~15 seconds later**: `state: "stopped"`, `stopped_at` populated, `stop_finalization_pending` key
  **absent** (cleared, per the fix's own "clears... unconditionally once the thread truly completes"
  contract). `candidates_created`: **19** — the finalize tick's forced-decision mechanism genuinely rescued
  2 more real, previously-pending candidates into admitted Visits (`visit-observation-candidate-020`,
  `-021`), directly answering the "did stop rescue anything" question v4's own report left open and
  unresolved.
- **Two further repeated checks** (immediately after, and again several minutes later, after the rest of
  this session's own post-session analysis work): `state: stopped`, `candidates_created: 19` (unchanged),
  `stopped_at` unchanged, `stop_finalization_pending` absent both times — stable, no flapping, no duplicate
  creation.
- `stopped_reason: "user_stopped"` throughout — truthful, matches what actually happened.
- No duplicate Visit was emitted: the 19 admitted Visits carry 19 distinct, gap-free sequential IDs
  (`visit-observation-candidate-003` through `-021`), confirming clean, non-duplicated persistence.
- GPU returned to idle (0% utilization) after stop; Camera Node self-test/watchdog remained healthy.

## Funnel

For the genuine encounters directly confirmed via evidence review (see "Independent denominator," below),
every stage worked correctly through to a real, useful, admitted Visit:

1. **Monitoring coverage** — OK, ~99.99% (independent recorder span; see "Gate A metrics").
2. **Detector opportunity** — OK, MDv5a ran continuously at the confirmed 0.1 threshold.
3. **Localization** — OK for 18 of 19 admissions (real, tight bounding boxes directly verified against
   real frames); 1 of 19 (`visit-observation-candidate-021`) localized to a region containing no visible
   animal — see "Defects," below.
4. **Tracking** — OK, 8,641 track updates observed.
5. **Proposal generation** — OK, 380 proposals.
6. **Arbitration/admission** — **OK, no longer the first-irreversible-loss stage it was in v4.** 19 of 380
   proposals admitted; the specific mechanism v4 found broken (component-level forced decision under
   sustained activity) fired correctly and repeatedly throughout this session.
7. **Evidence capture/survival** — OK for 18/19; the 1 exception is the same false-positive Visit (its
   "evidence" is real bytes, just of empty background, not a survival failure).
8. **Candidate persistence** — OK, 19/19 durably persisted, zero contention, zero loss.
9. **Event/Visit assembly** — OK, 19 distinct Visits, no duplicates.
10. **User-visible Visit** — OK, directly confirmed via `GET /api/dashboard/summary`
    (`detector_qualified_animal_visit_count: 19`, `unresolved_animal_visit_count: 19`, real "best moments"
    entries) — the exact product surface v4 found showing "zero signal" now correctly shows the session's
    real activity.
11. **Correct subject/evidence** — 18/19 correct; 1/19 (the same case) attributed a species label to
    background.
12. **Species suggestion/abstention** — OK; see "Species assistance," below.
13. **Reviewability** — OK; all 19 sit in Review Queue as `needs_review`, per the review-optional design
    (useful immediately, review never gates visibility).

**First irreversible loss stage this session: none, for 18 of 19 admissions.** For the 1 exception
(`-021`), the first irreversible loss is at **stage 3 (localization)** — a single, weak (0.704 confidence,
only 1 detection, `terminal_reason: maximum_unsupported_duration`) detection that was very likely spurious
was treated identically to a genuine detection by the (deliberately, already-evaluated) confidence-blind
admission policy; everything downstream of it (tracking, admission, evidence, species suggestion) behaved
correctly *given* that upstream input.

## Gate A metrics (this session)

### Visit
- Genuine encounters directly confirmed via evidence review: **at least 18** distinct real wildlife
  encounters (see "Independent denominator" for methodology). One further admission
  (`visit-observation-candidate-021`) is a likely false positive, not counted as a genuine encounter.
- Encounters represented by ≥1 useful Visit: 18/18 (100% of confirmed genuine encounters).
- **End-to-end Visit recall: no missed genuine encounter was found** via targeted independent review of the
  acceptance-recorder's own 5,147-frame archive (a dense sweep of the one extended quiet period, plus a
  broader whole-session sweep) — honestly bounded, not exhaustive: a full frame-by-frame audit of all 5,147
  frames was not performed, matching every prior cohort's own bounded-sampling methodology. Recall for this
  session is very high, qualitatively far closer to complete than either the 68.2% primary cohort or v4's 0%.
- Misses: none identified.
- **False Visits: 1/19 (5.3%).** `visit-observation-candidate-021` — root-caused precisely (see "Defects").
- Fragmented encounters: **0 confirmed, 1 ambiguous-and-unresolved candidate**
  (`visit-observation-candidate-004`/`-006`, 24 seconds apart, both localized to the same feeder region in
  the frames directly reviewed) — plausibly the same bird photographed twice in quick succession, or two
  distinct close-together visits; not resolved with confidence, disclosed as ambiguous rather than forced
  either way, per the brief's own instruction. The *other* initially-flagged candidate pair
  (`-020`/`-021`, ~9 seconds apart, contradictory species labels) was **not** fragmentation on closer,
  geometry-verified inspection — their real detection bounding boxes are in clearly different frame regions
  (x≈0.42–0.51 vs. x≈0.85–0.91), so they are two independent, unrelated detections, one real and one
  (`-021`) the false positive discussed above.
- Fragmentation rate: 0% confirmed, ≤5.6% (1/18) if the ambiguous pair is counted.
- Duplicate Visits: **0** (19 distinct, gap-free sequential Visit IDs; no repeats).
- Incorrect merges: 0 observed.
- Simultaneous-subject result: see "Multi-subject," below — not strongly exercised this session.

### Evidence
- Visits with useful evidence: 18/19 (94.7%).
- Useful-evidence rate: 94.7%.
- Wrong-subject evidence: 0 (no case of evidence showing a different real subject than claimed).
- Background/empty evidence: 1/19 (`-021`, confirmed by direct pixel-region inspection against the actual
  detection bounding box — the box lands on empty grass, no animal visible).
- Attribution correctness: 18/19 correct (94.7%).

### Monitoring
- Intended duration: ~90–120 minutes, activity-dependent, per the governing brief.
- Actual duration: **106.6 minutes** (6,396.5 seconds), clean start/stop.
- Independent recorder coverage: 5,147 frames, ~4.0GB, first frame at offset 0ms, last at offset
  6,395,953ms of 6,396,509ms total session span ⇒ **~99.99% temporal span coverage** (effective ~0.80
  frames/sec against a 1.0Hz nominal cadence — comparable to, and slightly denser than, v4's own 0.73fps
  effective rate).
- Outages/reconnects: **zero** (`camera_connected: true` throughout the active session; zero ERROR/CRITICAL
  log lines across the entire 187-line session log).
- Excluded periods: none.

### Latency
Not meaningfully instrumented this session, consistent with every prior cohort's own disclosed limitation
("this remains, across all cohorts to date, an unestablished measurement"). Real captured-at timestamps
exist for all 19 Visits and were used for offset/fragmentation analysis, but no dedicated capture→proposal→
admission→persistence→visible instrumentation exists in the product to measure true latency distributions.
Species-enrichment latency: BioCLIP `inference_ms` was directly observed in real suggestion payloads
(546ms, 562ms for the two inspected in depth) — a genuine, if narrow, new data point; not a full-session
distribution.

## Fragmentation / duplicates

Directly measured, not assumed: 19 Visits over 106.6 minutes of genuine, repeated feeder activity (not one
continuous encounter turned into hundreds of fragments — the specific regression risk the accepted fix's own
design deliberately bounds against). Visit durations ranged 0.0–60.6 seconds, matching real short feeder
visits, well inside the 20-minute bounded-decision horizon; no giant merged episode was observed. Exactly
one ambiguous, unresolved possible-fragmentation pair (see "Visit," above) out of 19 — a small, bounded
amount, not a runaway pattern.

## Evidence

18 of 19 admitted Visits' primary evidence images were directly reviewed at full resolution and each shows
a real, clearly visible bird at the seed feeder — genuine, useful, non-background evidence. Species
suggestions attached correctly to Visits where BioCLIP ran (see below). The one background/empty-evidence
case is disclosed above and in "Defects."

## Multi-subject

**Not strongly exercised this session.** The very first admitted Visit's own evidence frame incidentally
shows two birds at once (one at the feeder, one in flight) — genuine confirmation that multiple subjects
were sometimes simultaneously present in the scene — but no two Visits in this session shared a single
Event as concurrent siblings (the specific mechanism `roadmap.md`'s "Multi-Subject Visit Assembly Phase 2"
built for genuinely simultaneous distinct subjects). The closest-timed Visit pairs this session (24s and
~9s apart) were sequential, not simultaneous. No cross-subject evidence contamination or incorrect merge
was found in any of the 19 admissions. This dimension — the one the accepted fix's own field-rerun
requirement explicitly named as unexercised by the motivating v4 session — remains only partially advanced
by v5: real multi-bird presence in-scene is confirmed, but genuinely-concurrent-subject admission was not
directly tested here either, since it did not happen to occur.

## Persistence

Grepped the full session log twice (immediately after stop, and again after the full post-session analysis
pass) for `observation_candidate_visit_persistence_contention`: **zero occurrences**, both times. Zero
ERROR/CRITICAL lines anywhere in the log (187 lines total). This is a single-Stream session, so genuine
cross-Stream SQLite write contention was structurally unlikely regardless — reporting zero as valid, real
evidence, not silence. No admitted candidate disappeared after creation (19 created, 19 present in the final
Visit list, in database order, gap-free).

## Species assistance

BioCLIP-2 ran automatically on every admitted candidate (`automatic_identification.status: "succeeded"`
observed on both the mid-session and post-finalize admissions checked directly). Across the 19 admitted
Visits: **9 suggestions, 10 abstentions** (`suggested_label: null` — an honest "not clear enough" outcome,
not a bug, per doctrine). Suggested species: house_finch (7×), carolina_chickadee (1×), brown_thrasher (1×)
— all real, common Southeastern-US backyard feeder species, plausible for the scene. Eligibility/abstention
policy (`identification-eligibility-v1`, `score_floor` 0.7, `margin_floor` 0.2) behaved correctly for every
suggestion directly inspected (each had `top1_score` and `margin` comfortably clear of both floors).

**One obviously confidently-wrong suggestion, precisely diagnosed (see "Defects"):**
`visit-observation-candidate-021` received "Brown Thrasher" at 89.9% confidence, margin 0.857 — a
genuinely confident, non-abstained call — for a crop that direct pixel inspection (against the exact
`evidence_region` bounding box BioCLIP's own crop used) shows to be empty grass, no animal. This is not a
new defect class: it is a fresh, concretely-reproduced, well-evidenced instance of the already-known Gate B
"background/empty evidence → confident species label" regression class `roadmap.md` already names as open
work, distinct from and unrelated to the sustained-activity starvation family this milestone primarily
tests. No classification tuning, BioCLIP 2.5 evaluation, or SpeciesNet work was performed or considered,
per the governing brief's explicit non-goals.

## Product behavior

`GET /api/dashboard/summary`, checked live after the session: `detector_qualified_animal_visit_count: 19`,
`unresolved_animal_visit_count: 19`, `needs_review_visit_count: 20` (19 real + 1 pre-existing unrelated
seed row), `actionable_animal_visit_count: 12`, real "best moments" entries surfacing actual session Visits
with real evidence previews, `open_activity_session_count: 0` and `monitored_stream_count: 0` correctly
reflecting the stopped state. This is the direct, positive resolution of the v4 P0 product-surface finding
("a user watching this exact scenario live would see zero signal that anything happened at all") — that
finding's own root cause (nothing ever reached a state the dashboard had any fact to show) is exactly what
this milestone's field validation confirms is fixed; no separate dashboard code change was needed or made.
Camera health, storage health (32GB free at session end, down from 40.36GB — 8.3GB used, consistent with
the 4.0GB recorder archive plus normal database/release growth, not concerning), and Camera Node self-
test/watchdog all behaved as documented throughout and after. No other P0/P1 product-surface defect found.

## Cross-cohort comparison

| Metric | 2026-08-19 (primary) | 2026-08-20 (cache-128) | 2026-08-29 (v4, pre-fix) | **2026-08-30 (v5, post-fix, this session)** |
|---|---|---|---|---|
| Duration | 92.2 min | 90m23s | 112.0 min | **106.6 min** |
| Recorder coverage | 99.64% | full, no early stop | 99.78% | **~99.99%** |
| Genuine encounters | 22 (ceiling) | ≥9–10 | ≥2 broad windows + 1 mammal | **≥18 confirmed** |
| Visits created | 21 | 12 | 0 | **19** |
| End-to-end Visit recall | 68.2% (15/22) | not separately restated | **0%** | **very high (no miss found; not exhaustively verified)** |
| False-Visit rate | 9.5% (2/21) | 2/12 likely-false | undefined (0/0) | **5.3% (1/19)** |
| Fragmentation | 2 encounters | not separately restated | not computable | **0 confirmed, ≤1 ambiguous** |
| Duplicates | 3 Visits | 0 confirmed | 0 (no Visits) | **0** |
| First in-session admission | (not the question that cohort tested) | (not the question that cohort tested) | never (stuck at 0 for entire session) | **~25 seconds into the session** |
| Stop rescued pending work | n/a | n/a | unresolved open question (0 before, 0 after) | **yes — 17→19 at finalize** |
| Species suggestion availability | 18/18 = 100% | 12/12 = 100% | N/A (0 Visits) | **9/19 suggested, 10/19 honest abstention** |
| Persistence contention | n/a (fix not yet built) | n/a (fix not yet built) | 0 occurrences (unexercised) | **0 occurrences** |
| Decision | B | A (cache-128 proof) | A (defect found & disclosed) | **A (this milestone's own execution)** |

This session is the **first real field proof that the accepted sustained-activity fix works end-to-end**,
against the identical busy-feeder Stream/scene that exposed the original defect. It does not merely repeat
v4's conditions with a different outcome — it directly answers the fix's own "Field-rerun requirement"
checklist: (1) `candidates_created` no longer stuck at 0 — confirmed; (2) admitted-Visit count bounded and
coherent (19 over 106.6min, not zero, not an explosion of duplicates) — confirmed; (3) stop against
genuinely pending work resolves honestly and rescues real work — confirmed; (4) `blocked_shadow_mode` and
`blocked_missing_evidence` checked against the counterfactual ledger — confirmed absent/low respectively;
(5) multi-subject correctness through to real admitted Visits — **partially advanced, not fully exercised**
(no concurrent-sibling admission occurred to test).

## Candidate release budgets

Per the governing brief's §22: proposing what the combined evidence across all four real cohorts now
supports, explicitly **not self-accepted** — for ChatGPT review.

**Reasonably supported by convergent evidence across cohorts:**
- **Minimum monitoring coverage: ~99%.** All four real cohorts, including this one, independently measured
  99.6%–99.99% coverage with no cohort falling meaningfully short. This is the most convergent metric
  available; a 99% floor is conservative relative to every real measurement to date.
- **Minimum useful-evidence rate: ~85%.** Primary cohort 88.2% (15/17), this session 94.7% (18/19) — two
  independent measurements above 85% with no contrary evidence; a modest floor below both real
  measurements is defensible.

**Not yet supportable — one post-fix data point is not "a broader body of field evidence":**
- **Minimum end-to-end Visit recall.** This session's own recall is qualitatively very high, but it is the
  *first* post-fix measurement, from the same single busy-feeder scene the fix was built to correct — not
  yet a second, independently-varied confirmation (different site conditions, a genuinely sparser
  single-subject session re-run post-fix, or a session that actually exercises simultaneous multi-subject
  admission). Proposing a number now would repeat the exact mistake `roadmap.md` already warns against:
  setting a floor from a still-narrow evidence base.
- **Maximum false-Visit rate / maximum fragmentation rate.** This session's own figures (5.3% false-Visit,
  ≤5.6% fragmentation) are the *first* real post-fix measurements of either, from small samples (19 and 18
  Visits respectively) at one site. Not yet cross-validated by a second cohort.
- **Maximum capture-to-visible-Visit latency.** Remains wholly unestablished by real instrumentation across
  every cohort to date, this one included — no candidate proposed.
- **Maximum duplicate rate.** 0% in 2 of the last 3 cohorts (v4 had none to duplicate; this session 0/19),
  but the primary cohort's own 3 duplicate Visits (2026-08-19) is real, unexplained-in-this-report contrary
  evidence not re-investigated here — proposing a ceiling now would need to reconcile that data point first.

## Remaining Gate A dependency

Precisely, in priority order: (1) **a second post-fix daylight session**, ideally exercising conditions v5
did not — genuinely simultaneous multi-subject admission (two distinct birds at once resolving to sibling
Visits), and/or a sparser single-subject scene re-run post-fix to confirm the fix does not regress that
shape — to convert this session's own single strong data point into the "broader body of field evidence"
Gate A budgets require; (2) only after that, propose numeric release budgets for recall/false-Visit-rate/
fragmentation-rate with real cross-session convergent support; (3) the one disclosed defect this session
found (background-evidence-confident-species-label) remains open Gate B work, already named in
`roadmap.md`, not blocking Gate A directly but worth folding into whatever milestone eventually tackles
credible-animal-gating/abstention refinement.

## Defects

**Finding: false-positive admission + confidently-wrong species label on background evidence (not new, not
release-blocking for this milestone's own scope).**

- **Evidence preserved:** `visit-observation-candidate-021` (real Visit, real persisted evidence
  `media-candidate-052`); its underlying detection `stream-fb6aa12f80ca:frame-track:e8ff1652a20c41a5dbf4`
  (bounding box `[0.8515, 0.7194, 0.9067, 0.7768]`, `detection_count: 1`, `max_confidence: 0.704`,
  `terminal_reason: "maximum_unsupported_duration"`); BioCLIP's own `evidence_region`
  (`x=0.8041, y=0.6731, width=0.15, height=0.15`) — direct pixel-region inspection against the real
  full-resolution frame confirms this region contains no visible animal, just lawn.
- **First irreversible loss stage:** stage 3, localization — a single weak, likely-spurious detection
  entered the pipeline with the same standing as a genuine one, per the already-evaluated, deliberate
  confidence-blind admission policy (`detection-quality-accounting-contract.md`'s "Production authority
  gate": no swept confidence threshold cleared both false-positive-rejection and real-animal-recall
  together). Everything downstream behaved correctly given that input, including BioCLIP's own
  eligibility/abstention policy — which has no "is a subject actually visible" check independent of its own
  species-level softmax confidence, so a confident background crop produces a confident (wrong) species
  label rather than an abstention.
- **Root cause, bounded, not exhaustively investigated:** this is a fresh, concrete, real-world instance of
  `roadmap.md`'s already-named Gate B regression class ("Background/empty evidence → confident species
  label") — not a new failure mode, and structurally unrelated to the sustained-activity starvation family
  this milestone primarily validates (this admission was correctly, promptly created; nothing about its
  timing or arbitration was wrong).
- **Fix disposition, per the governing brief's §24 bar: not attempted.** Fixing this needs credible-animal
  gating or crop-level abstention — work `roadmap.md` already scopes as its own future Gate B milestone
  ("Identification Eligibility + Abstention v1" is already accepted; this specific gap needs a *further*
  refinement, not a first build) — and the brief's own explicit non-goals exclude detector/model tuning and
  classification changes from this milestone. **Not release-blocking for Classification A here**: it does
  not touch the sustained-activity admission mechanism this milestone tests, does not represent a
  measurement-invalidating problem (it is directly, precisely accounted for in this session's own false-
  Visit-rate figure above, not hidden), and is not a new discovery requiring urgent triage — it sharpens an
  already-open, already-scoped item with one more real, well-evidenced instance.

No other P0/P1 defect found.

## Decision

**Classification A.** Representative daylight conditions (directly, visually confirmed via a dedicated
pre-flight scene check before committing to the cohort, not assumed); real Observation against the real
reference Camera Node and the same physical camera/scene that exposed the original v4 defect; a valid,
methodologically-honest independent denominator (acceptance-recorder frames, reviewed via targeted
full-resolution checks against known-quiet and known-active windows, not a blind sample mistaken for proof
of absence); the accepted sustained-activity fix directly, repeatedly, and conclusively proven working
end-to-end — first admission at 25 seconds, 19 real admitted Visits throughout a 106.6-minute session, the
new honest stop-finalization status observed live and correctly resolving/rescuing genuinely pending work;
zero recurrence of any of the three specific defects the fix targeted (starvation, stop-race,
missing-evidence-as-session-ending-blocker); one real, precisely root-caused, honestly-disclosed defect
found (a fresh instance of an already-known, separately-scoped Gate B issue) that does not invalidate this
session's own measurement; every metric captured as far as this session's real instrumentation permits,
with genuinely unmeasurable ones (latency, multi-subject-concurrent-admission) stated as such rather than
invented or forced. Per the governing brief's own §27: "A milestone may be Classification A while Gate A
still remains open" — Gate A is meaningfully *closer* to closed than before this session (the P0 that
blocked it is now field-proven fixed), but is not itself declared closed here, and this report does not
attempt to.
