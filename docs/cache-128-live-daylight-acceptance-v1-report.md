# Cache-128 Live Daylight Acceptance v1 — Report

Field-acceptance-only session (no source code modified). Direct follow-up to
[camera-node-connectivity-recovery-diagnosis-v1-report.md](camera-node-connectivity-recovery-diagnosis-v1-report.md)
and the two prior, inconclusive cache-128 attempts
(2026-08-19 nighttime: Decision D, wrong time-of-day; 2026-08-20 morning:
Decision D, real Camera Node connectivity failure after ~4.08 productive
minutes). Full raw evidence, checkpoints log, and independent-encounter
table: `data/field-acceptance/2026-08-20-cache-128-live-daylight-acceptance/`
(gitignored).

## 1. Question

Does the 128-entry harvested-evidence cache (`_MAX_CACHED_BURST_BYTES`/
`_MAX_CACHED_SAME_FRAME_BYTES`, raised from 32 at `51ee8ea`) survive
realistic delayed-proposal churn without reproducing the two real
evidence-eviction losses seen in the 32-entry-era reference cohort
([end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md))?

## 2. Repository / runtime state

- Local `HEAD` at session start: `79c9b48` (docs-only roadmap commits).
  `git diff --stat bdb59f5..HEAD` confirmed only `docs/roadmap.md` changed —
  runtime-equivalent to the deployed `bdb59f5`. **Did not redeploy** current
  HEAD.
- `_MAX_CACHED_BURST_BYTES = 128`, `_MAX_CACHED_SAME_FRAME_BYTES = 128`
  confirmed directly in source (`engine_runtime.py:1450-1451`), inherited
  unchanged from `51ee8ea` through `bdb59f5`/current `HEAD`.
- Deployed instance independently re-verified live at
  `bdb59f5e657e20fdc8a902a259640071881dfe6d` (`GET /api/product/instance`,
  exact `git_commit` match) before and after this session.
- 7 pre-existing untracked files confirmed present, unchanged, throughout
  (same list every prior session; see final validation below).

## 3. Acceptance-recorder relaunch (required for this session)

The runtime had been running since a short 7m08s Decision-A proof earlier
the same day, **without** the acceptance-recorder env var (that proof did
not need an independent denominator). Relaunched via the smallest supported
mechanism: drove `scripts/deploy_windows_dev.py`'s own internal
`stop_verified_deployment`/`launch_release`/`verify_deployment`/
`write_current` functions directly against the *already-materialized,
ledger-verified* `bdb59f5` release directory — skips the tool's own
unconditional rebuild step (correct here since the commit is provably
unchanged), never a bespoke reimplementation of the launch mechanism itself.
Recorder env vars set on the WSL/Linux side (`launch_release`'s own
`os.environ.get("MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR")` forwarding,
avoiding the documented Windows-env-var-propagation bug), using the exact
established ~92-minute-cohort methodology
(`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_INTERVAL_MS=1000`, `_MAX_FRAMES=5500`,
`_MAX_BYTES=4950000000`, same output root as every prior recorder session).

New PID `10352` launched; the deploy tool's own `verify_deployment` reported
a transient false negative on its last sub-check (matching the documented
cold-start pattern), independently re-confirmed healthy immediately after
via fresh `GET /api/product/instance`/`/api/product/health` calls (doctrine:
never trust the deploy tool's report alone). All 6 prior recorder session
directories confirmed present and untouched; a fresh
`stream-ca892992771c\20260820T222528Z` subdirectory appeared within seconds
of the subsequent Start and was growing within the first health check —
satisfying the required "very short health check," not a repeated 7-minute
proof.

## 4. Field cohort

- **Start**: `POST .../observation/start` → `2026-08-20T22:25:28.525602Z`
  (18:25:28 EDT). Unchanged MDv5a config (`score_threshold: 0.1`,
  `MDv5a.0.1-onnx-opset18`, CUDA execution provider) — no tuning of
  detector/tracker/admission/evidence policy/cache size/cadence at any
  point.
- **Stop**: clean, deliberate `POST .../observation/stop` at
  `2026-08-20T23:55:51.815617Z` (`stopped_reason: user_stopped`). The POST
  itself timed out client-side (known PowerShell-interop transient,
  confirmed benign via an immediate fresh `GET .../status`).
- **Duration**: 90m23s.
- **Stopping rationale**: ran to the ~90-minute target because churn stayed
  rich and daylight (directly, visually verified via the recorder's own
  frames at 25/56/75/89 minutes) held throughout the session; stopped once
  light was visibly dimming at the 89-minute mark rather than forcing
  exactly 90:00 or stretching into darkness.
- **Final counters**: `track_updates_observed=6592`,
  `evidence_candidates_observed=1752`, `proposals_observed=289`,
  `candidates_created=12`, `candidates_suppressed=277`
  (`blocked_continuation_pending=211`, `blocked_ambiguous_boundary=39`,
  `reject_no_identification_or_context=19`, `blocked_missing_evidence=7`,
  `blocked_shadow_mode=1`, a single benign post-stop-teardown evaluation).
  Materially busier than the 92-minute reference cohort's 227 proposals.
- **Recorder**: finalized cleanly, 4631 frames, 4631 manifest lines (exact
  match), 3,631,272,278 bytes (~3.63GB, under its own 4.95GB cap — recording
  stopped only because the session stopped, not because either recorder
  bound bound). Mean cadence ~1.165s/frame. Last frame 23:55:27.638Z, ~42ms
  before `last_healthy_frame_at`.

## 5. Independent encounter denominator

Built via a dedicated subagent, methodology matching established convention
exactly (blind pass — no product data touched until fully written; motion-
screen objective flagging + full-session contact-sheet backstop + full-
resolution zoom on every candidate, not thumbnail-only). Full detail:
`independent-encounter-table.md` in the session directory.

- **9 distinct encounters found blind** (A-I), 2 of which (A: ~0-620s, C:
  ~752-1400s) are long sustained-occupancy spans conservatively reported as
  one bounded encounter each rather than an unsupported per-visit split —
  multi-subject evidence (2+ simultaneous birds, 5 high-confidence moments)
  proves the true individual-visit count within each is well above 1.
  2 further sightings genuinely could not be resolved even after zooming in
  and are excluded from the 9.
- **All confirmed activity stopped after ~2970s (49.5 min)** — the session's
  last 40.5 minutes had zero confirmed animal activity (dusk approaching;
  matches this session's own live monitoring, which showed extended flat-
  counter stretches in the same window).
- **My own direct follow-up** (after the subagent's file was complete) found
  one further real, confirmed encounter its per-window coverage did not
  happen to catch (`visit-observation-candidate-137`'s own persisted
  evidence image, ~2413s, real bird, golden-hour light) — disclosed as a
  genuine gap in the blind pass's own coverage, not silently folded into the
  count. **True conservative denominator: >=10 encounters**, materially
  more if A/C's multi-individual character were decomposed.

## 6. Visit-by-visit reconciliation (12 created)

| Visit | Offset (s) | Duration | Suggestion | Finding |
|---|---|---|---|---|
| 129 | 112.2 | 0.00s | house_finch | Real (encounter A) |
| 131 | 127.5 | 2.23s | carolina_chickadee | Real (encounter A) |
| 130 | 137.6 | 0.00s | house_finch | Real (encounter A) |
| 132 | 420.9 | 2.97s | house_finch | Real (encounter A) |
| 133 | 526.5 | 15.00s | house_finch | Real (encounter A); survived a **324.2s** delay |
| 134 | 907.4 | 1.40s | house_finch | Real (encounter C) |
| 135 | 1021.7 | 3.02s | house_finch | Real (encounter C) |
| 136 | 1368.6 | 19.27s | house_finch | Real (encounter C) |
| 137 | 2413.1 | 0.00s | house_finch | **Real**, directly confirmed (fills an independent-review coverage gap) |
| 138 | 2536.1 | 1.07s | house_finch | Unresolved — own evidence frame not clearly bird or clearly not |
| 139 | 5117.9 | 2.01s | brown_thrasher | **Likely false** — see below |
| 140 | 5124.7 | 5.54s | red_bellied_woodpecker | **Likely false** — see below |

**129/130/131** (all within a 25.4s span, 2 different species labels): a
likely duplicate/fragmentation cluster, but this matches — does not exceed —
the exact, already-disclosed, deliberately-not-fixed `visit_episode_
assembler` non-merge-of-overlapping-tracklets pattern from the reference
session. Not new; not cache-related (all 3 admitted immediately, zero
delayed handling, so eviction cannot be a factor).

**139/140** (7.2s apart): directly fetched both Visits' own persisted
evidence images (`GET /api/media/{id}/preview`, not just nearby recorder
frames). Neither shows a bird; visit-140's evidence clearly shows a
person's arm/shoulder at frame edge. Both fall exactly inside the
independent review's own blind motion-screen window 37
(5132.5-5139.3s, logged as "a person walking a dog on a leash — non-
wildlife"). A real, disclosed **detector-precision false-positive**
(matching this project's long-documented "admission gates never consult
detector confidence/species" profile) — **not a cache defect**: both
Visits' own evidence survived their own 45-46s delayed handling just fine,
which is actually further positive evidence for the cache question, not
against it.

## 7. Cache-specific accounting — the 7 `blocked_missing_evidence` cases

Every `no_persistable_evidence_bytes` (`blocked_missing_evidence`) terminal
outcome traced individually via the counterfactual ledger (3 proactive full-
session pulls merged into one gap-checked cumulative dataset, taken before
the ledger's own rolling retention — confirmed non-zero and accelerating
during the session — could destroy early records; every terminal-reason
count in the merged dataset exactly reconciles against the authoritative
final status counters).

| Proposal (suffix) | Window (ms) | Gens | Pending re-evals | Delay lifetime | Evid. volume during delay | % of 128 | Real bird present (independent check) | Verdict |
|---|---|---|---|---|---|---|---|---|
| `...5b900477` | 481708-512320 | 1 | 3 | **115.6s** | 123.5 | **96.5%** | **Yes, high confidence** (0.785 max conf., 15 detections, `confirmed: true`) | **Plausible cache-eviction — genuine, disclosed, unresolved** |
| `...7ac2eaa3` | 624843-634873 | 1 | 0 | 0.0s (immediate) | n/a | n/a | Yes | Never delayed — not an eviction case |
| `...b4cec5f0` | 708244-773429 | 3 | 0 | 0.0s (immediate) | n/a | n/a | Yes | Never delayed — not an eviction case |
| `...ecc70d37` | 915162-984706 | 3 | 4 | 47.0s | 28.4 | 22.2% | Yes | Implausible by volume — likely never-harvested |
| `...6b8c30c6` | 1244192-1250628 | 1 | 4 | 46.9s | 28.5 | 22.3% | Yes | Implausible by volume — likely never-harvested |
| `...d47830f4` | 2045480-2101954 | 3 | 4 | 45.1s | 10.7 | 8.4% | Yes (for most of window) | Implausible by volume — likely never-harvested |
| `...f44148a7` | 2456851-2462334 | 1 | 1 | 57.1s | 24.5 | 19.1% | Yes (medium-high, partial occlusion) | Implausible by volume — likely never-harvested |

**Evidence-candidate volume** reconstructed from this session's own live
monitor timestamps (piecewise-interpolated `evidence_candidates_observed`
curve), compared against each proposal's own actual pending lifetime.

**The one plausible case, in full**: `visit-episode:...5b900477`'s single
constituent track generation (`...aa8b2d0145aaea67b77a`) is `confirmed: true`,
`terminal_reason: "maximum_duration"` (ran the full allowed track duration —
a genuinely sustained subject), 15 detections, `max_confidence: 0.785` — a
strong, real track, not a borderline artifact. Independently, directly
confirmed via zoomed reads of the recorder's own frames at the window's
exact start and midpoint: a real small bird perched at the seed-tube
feeder's bottom perch ring, matching the proposal's own tracked geometry.
115.6s pending lifetime with 123.5 (96.5% of 128) new evidence candidates
observed session-wide during that exact window makes FIFO cache eviction
(`engine_runtime.py:1466-1474`, confirmed true insertion-order
`cache.pop(next(iter(cache)))`) a **plausible** explanation.

**Honest limit of this methodology, disclosed rather than papered over**:
whether a `high_resolution_burst`/`classifier_same_frame`-role candidate was
ever actually harvested for this track in the first place cannot be
observed from outside the process after the fact — burst issuance is gated
by a separate scheduler fairness/throttling decision
(`camera_node_live.py:840-905`, `self.scheduler.decide(opportunity)`)
*before* anything reaches the cache under test, and no surviving log/API
signal distinguishes "never harvested" from "harvested then evicted." This
session's evidence (strong/confirmed real track + near-saturating cache
volume during its own delay window) makes cache-capacity eviction plausible,
not certain — reported exactly that way.

**Positive counter-evidence, same method, applied to successes**: of 10
created Visits traceable in the cumulative ledger sample, 6 survived genuine
delayed handling first, with pending lifetimes of 36.6s, 45.0s, 45.1s,
45.4s, 45.6s, and **324.2s** — the longest successful survival is **2.8x
longer** than the one ambiguous failure's 115.6s. The session's last two
real Visits (139/140, despite being false-positive subjects) independently
confirm the *mechanism* itself surviving the same ~45s single-generation
delay profile as several of the flagged failures.

**A separate, real, disclosed finding — not the cache bound, and not fixed
here**: 4 of the 7 `no_persistable_evidence_bytes` cases involve a real,
independently-confirmed bird (Phase 2 cross-check: 7/7 windows had a real
animal visible) yet show implausibly low cache-volume pressure during their
own delay (8.4%-22.3% of capacity) — more consistent with the burst-
scheduler's own issuance decision never producing a harvestable candidate
for these specific tracks at all, a different, upstream mechanism from the
128-entry capacity bound. Named here as a genuine finding worth a dedicated
future investigation; not diagnosed further or fixed in this
acceptance-only session.

## 8. Runtime / connectivity

Zero reconnects, zero `analysis_stream_unavailable`, zero
`onnx_cuda_verification_insufficient` across the full 90m23s session —
Camera Node connectivity held throughout under real sustained load. Doctor
(`python -m mockingbird doctor --json`, run post-session against the
deployed release) is `DEGRADED` solely from the same pre-existing,
already-disclosed "previous run did not shut down cleanly" WARN (historical
host-shutdown fact, unrelated) — every substantive check (`database_schema`,
`storage`, `camera_node` — "0 currently being monitored," clean interval
close, `ffmpeg`, `detector_model`, `species_identification`, `gpu_cuda`,
`backup`, `clock`) PASSed. Single runtime process confirmed throughout (PID
`10352` plus its own legitimate `multiprocessing.spawn` worker child, never
a second/competing instance). Disk: 43.07GB free at session start, 39.45GB
after — comfortably above the recorder's 4.95GB budget and normal product
growth.

## 9. Species evidence (secondary; recorded, not fixed)

All 12 Visits received an automatic BioCLIP suggestion. 8 of 12 suggested
`house_finch` — plausible for this real feeder/season, not independently
contradicted by anything checked, but not independently species-confirmed
either (this session's scope did not include per-Visit species
adjudication). Every evidence frame checked (129, 137, 138, 139, 140, and
the 7 Phase-2 cross-check windows) carries `normalized_crop_box: null` /
`normalized_track_box: null` — the reviewer sees a full, uncropped frame
with no highlighted subject region, a known, pre-existing product-surface
gap (feeds the disclosed-but-not-yet-built Gate B eligibility/abstention
milestone). `classifier_supporting_evidence` (the separate same-frame
crop actually used internally for the species call) is present and appears
reasonably subject-centered where checked. The two false-positive Visits
(139/140) each still received a specific, confident species label
(`brown_thrasher`, `red_bellied_woodpecker`) despite showing no bird at all
— a real, disclosed "strong suggestion on inadequate/absent evidence" case
for the Gate B backlog.

## 10. Multi-subject fixture material (preserved, not implemented)

9 multi-subject (2+ simultaneous animals) moments flagged in the
independent review, 5 high-confidence: ~767.4s, ~899.9s, ~1000.1s (2 birds +
a lower-confidence possible 3rd), ~2777.7s and ~2796.5s (hook-perch bird +
feeder-base bird, ~2.2s apart — the clearest close-crossing pair). All
preserved in the untouched recorder session directory
(`stream-ca892992771c\20260820T222528Z`) for future Multi-Subject Phase 2
work — not implemented this session.

## 11. Validation / cleanup

- Observation stopped cleanly (`user_stopped`); recorder finalized cleanly
  (no bound hit, stopped only because the session stopped).
- No orphan process: exactly one main process (PID `10352`) plus its own
  legitimate worker child confirmed post-session.
- Product runtime healthy/idle (`monitored_stream_count: 0`,
  `ready: true`).
- Camera Node state: paired, was reachable and stable throughout; no
  action needed.
- `git status` at session end: identical to session start — the same 7
  pre-existing untracked files, nothing else (this report + roadmap edit
  are the only new tracked changes, committed separately). All generated
  media/recorder output lives under gitignored `data/`.
- All prior field-acceptance evidence directories (2026-08-19 reference
  cohort, both failed cache-128 attempts, the perception-replay real-GPU
  acceptance record) confirmed present and untouched.
- No code changes this session — no test suite run (nothing to validate;
  matches "field-acceptance-only" convention for a pure acceptance
  session).

## 12. Decision

**A — CACHE-128 LIVE PROOF PASSES**, with one disclosed, unresolved,
minority-weight exception explicitly not swept under the rug.

Reasoning: the session produced meaningful daylight denominator (>=10
independent conservative encounters, materially more individual visits
likely within the 2 long sustained-occupancy spans), meaningful
delayed-proposal churn (211 `blocked_continuation_pending` + 39
`blocked_ambiguous_boundary` suppression events; 6 of 10 traceable created
Visits survived genuine delayed handling, up to 324.2s), and repeated,
same-session, positive evidence that previously-harvested evidence survives
delayed handling at delays equal to or well beyond the one case that
remains genuinely ambiguous. The historical cache-eviction signature (a
real, strong, well-tracked bird, legitimately delayed, terminally failing
for a *provably* evicted reason) does not clearly or systematically recur
the way it did in the 32-entry-era reference session (2-for-2, unambiguous
causation) — this session has at most one plausible-but-unproven instance,
set against six same-session successes at equal-or-longer delays. Four of
the other six `blocked_missing_evidence` cases are better explained by a
different, disclosed, upstream mechanism (burst-scheduler issuance) than by
the 128-entry capacity bound itself; two never entered delayed handling at
all. The two likely-false Visits and the one likely-duplicate cluster are
both pre-existing, already-disclosed, out-of-scope categories, not new
findings, and are not attributable to the cache.

Not forced: this is not "the system stayed online," it is direct,
repeated, same-session proof of delayed proposals being exercised and
previously-harvested evidence remaining available through terminal
resolution — the actual bar the milestone set — with one honestly-disclosed
residual case that could not be conclusively attributed either way.

## 13. Recommended follow-up (not undertaken here)

1. **Burst-scheduler issuance investigation** (new, disclosed finding):
   4 of 7 real, confirmed-track `blocked_missing_evidence` cases show cache
   volume far below saturation, suggesting the burst-scheduler's own
   fairness/throttling decision (`camera_node_live.py`) may be declining to
   issue a harvest request for some real, legitimate tracks independent of
   cache capacity. Worth a dedicated bounded investigation with direct
   scheduler-decision instrumentation (not available from outside the
   process today).
2. The one ambiguous `...5b900477` case does not, on its own, justify
   another capacity bump (per governing instruction: do not blindly
   increase cache capacity again) — if a future session finds a *second*,
   clearer, higher-confidence-attribution case, that would change this
   calculus.
3. Multi-subject Phase 2 (preserved fixture material above) remains queued,
   unstarted.
