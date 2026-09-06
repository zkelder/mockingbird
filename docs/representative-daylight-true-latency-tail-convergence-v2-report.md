# Representative Daylight True-Latency Tail Convergence v2 — Blocked at the Hard Daylight Gate, No Live Tranche Attempted

Bounded RELEASE-CRITICAL Lane R evidence milestone. Follows accepted Gate A
True-Latency Tail Closure & Final Lane R Decision v1 (report `b6b4727`,
reconciliation `e103092`). Sole purpose: one additional intact, genuinely
daylight, current-stack RTT-normalized T0→T5 latency distribution large
enough to evaluate tail convergence.

**Outcome: the governing brief's own hard daylight gate (§4) failed before
any deployment was attempted.** Session time was 21:26–21:29 EDT on
2026-09-05 — night, roughly 1.5–1.7 hours past civil twilight end for this
latitude/date. Per §4's own explicit instruction ("If it is currently night
... DO NOT RUN THE FIELD TRANCHE"), no fresh instance was deployed, no
Camera Node pairing/RTT preflight was attempted, and no Observation was
opened. Only bounded, read-only readiness/archaeology checks were
performed. **Classification: B — WAITING FOR REPRESENTATIVE DAYLIGHT.**

Zero production code changed. Zero new latency samples. Zero deployment.

## Starting state

Verified directly, before any other action:

- Repository: `/home/zkelder/projects/mockingbird-active`; branch `main`.
- Starting HEAD: `e103092767fc52d2ec76db00743cd3e33d87dcd1` (matches the
  brief's expected `e103092` exactly).
- `git status`: working tree otherwise clean; the seven preserved untracked
  detector files present and unmodified (`docs/wildlife-detector-training-contract.md.orig`,
  `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) — none touched by this milestone.
- Branch ahead of `origin/main` by 348 commits; not pushed (and this
  milestone does not push).
- Schema: `v58`, confirmed unchanged via direct grep of
  [release-execution-state.md](release-execution-state.md) (most recent
  occurrences at its own §1/§3 entries, all `v58`).
- `docs/release-execution-state.md` §1/§3 confirmed, verbatim:
  - Accepted HEAD: `b6b4727` — report commit for Gate A True-Latency Tail
    Closure & Final Lane R Decision v1. Classification **B**.
  - Gate A: **OPEN — TRUE LATENCY TAIL EVIDENCE REMAINS**.
  - Recall: **ACCEPTED KNOWN LIMITATION — NO NUMERIC RECALL FLOOR YET**.
  - §3 "Current authorized milestone": **NONE — GLOBAL PRODUCT-ROADMAP
    RECONCILIATION REQUIRED.**
- All of the above match the brief's §2 "Expected accepted state" exactly.
  No divergence found — proceeded rather than stopping under §2's "if
  materially different: STOP and report."
- Worktree safety (§3 of the brief): no `.git/*.lock` present; `ps aux`
  shows no other MockingBird-related process (Python/Node/uvicorn/vite) —
  the only matches were an unrelated Codex CLI MCP process and the
  system's own `unattended-upgrade-shutdown`, neither touching this repo.
  No active writer. `data/field-acceptance/` shows the most recent session
  directory as `2026-09-05-gate-a-true-latency-tail-closure-v1` (the
  immediately-prior, already-accepted milestone) — no in-flight directory
  for this milestone, confirming no partial prior attempt exists to
  reconcile.

## Daylight gate

**FAIL — night. This is the operative finding of the entire milestone.**

Two independent clock sources were read, following the identical
cross-check method v10 and v14 both used and recorded as their own
daylight proof ("system clock cross-check (WSL/Windows-host times
agreed)"):

- **Sandbox (WSL/Linux) clock:** `Sat Sep 5 21:26:06 EDT 2026`.
  `timedatectl`: `Time zone: America/New_York (EDT, -0400)`; `System clock
  synchronized: yes`; `NTP service: active`.
- **Native Windows host clock**, read independently via
  `powershell.exe -Command "Get-Date; [System.TimeZoneInfo]::Local.Id"`,
  ~3 minutes later: `Saturday, September 5, 2026 9:29:19 PM`,
  `Eastern Standard Time` (Windows's static zone-ID name for the zone that
  observes EDT in September; this is normal Windows naming, not a
  DST-handling defect).

Both sources agree: local wall-clock time at the reference site was
**21:26–21:29 EDT**. Civil twilight ends at approximately 19:50–20:00 EDT
in early September at this latitude (sunset itself ≈19:20–19:30 EDT); the
observed time is **roughly 1.5–1.7 hours past civil twilight end** —
unambiguous night, not dusk or trailing civil twilight. This is exactly
the condition §4 names outright as disqualifying ("Do not begin the
measured Observation during: ... night").

No live-scene visual inspection or independent-recorder frame was
captured, and none was needed: §4 names "night" as disqualifying on its
own, the two-clock cross-check is the project's own established sufficient
method (see v10/v14 precedent above), and opening a live session against
the reference hardware purely to additionally photograph darkness would
itself be exactly the kind of unnecessary "long deployment/session" §4
instructs against when the outcome is not in doubt.

**Location/timezone assumption, checked, not merely assumed:** the
reference Camera Node is LAN-local (`192.168.1.112`, confirmed reachable
below), consistent with sharing the sandbox/Windows-host's physical site
and timezone. Cross-checked against source: both v10's report ("Local
time at session start: 2026-09-02 07:39:59 EDT") and v14's report
("session start 2026-09-05 13:51:55 EDT") record the reference site in
America/New_York/EDT — matching this session's own reading exactly, with
no prior report ever recording a different timezone.

**Conclusion: HARD DAYLIGHT GATE = FAIL.** Per §4, the measured Observation
must not begin tonight.

## Build identity

Not applicable — no build was deployed. As a bounded, read-only readiness
signal only (not a deployment), the reference Camera Node was confirmed
reachable on the LAN:

- `ping -c 2 -W 2 192.168.1.112`: 0% packet loss, RTT 95.8–120.6ms.
- TCP port 8787 (the Node's own API port): confirmed open via a raw
  connect probe.

No pairing, authentication, health/self-test query, or deployment was
attempted against the Node. No fresh Windows field-acceptance instance was
created, so there is no `git_commit`/`/api/product/instance` build
identity to report for this milestone. Windows-host interop itself
(`powershell.exe` → Windows) was confirmed live via the clock read above.
Full GPU/detector build-identity smoke-testing is deferred to the session
that actually attempts the live tranche, consistent with §4's instruction
not to build out a long session tonight.

## Storage / lifecycle

No new field-acceptance instance was `init`-ed; no lifecycle was entered.
§10's storage/reclaim safety obligations apply "before measured
Observation" — since none was attempted, no archive/instance was
inspected, reclaimed, or destroyed, and none needed to be. This is
deferred to the session that runs the live tranche. (For continuity: the
last known disclosure, from Gate A True-Latency Tail Closure & Final Lane
R Decision v1's own reconciliation, is an 18.5GB reclaim opportunity from
two already-archived, `SAFE_TO_RECLAIM` v13/v14 Windows dev-roots,
untouched again tonight.)

## RTT preflight

Not attempted. RTT-bounded calibration requires an authenticated, paired
session against the reference Camera Node; none was opened tonight.
Network-level reachability only (ICMP + open TCP port, above) was
confirmed, which is necessary but not sufficient for calibration, and
proves nothing about calibration validity.

## Existing qualifying latency body

Reproduced directly from each cohort's own original accepted report,
re-confirmed from source (not from a later summary) via
[gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md](gate-a-true-latency-tail-closure-final-lane-r-decision-v1-report.md)
and [gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md](gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md):

| Cohort | Valid n | Median | p90 | p95 | Max | Status |
|---|---|---|---|---|---|---|
| v9 (2026-09-01) | 24 of 25 (1 `invalid_clock_mapping`) | 111,811ms (111.8s) | 173,944ms (173.9s) | 200,408ms (200.4s) | 307,373ms (307.4s) | Intact, live-measured |
| v10 (2026-09-01) | 11 of 11 | 103,900ms (103.9s) | 183,300ms (183.3s) | not stated | **742,300ms (742.3s / 12.37min)** | Intact, live-measured |
| v14 (2026-09-05) | 14 of 14 | 82,920.6ms (82.9s) | 235,454.9ms (235.5s) | 253,408.4ms (253.4s) | 261,211.4ms (261.2s) | Intact, live-measured |
| v11 (2026-09-02, reconstructed) | 23 | 115,699ms (115.7s) | 318,469ms (318.5s) | 524,369ms (524.4s) | **865,199ms (865.2s / 14.42min)** | Supporting/reconstructed only — offline scratch reanalysis by the Correction v1 milestone, never visually re-verified against footage; **not equivalent to an intact originally-measured cohort** |

The brief's own §7 approximate figures (v9 ~111.8/173.9/307.4s; v10
~103.9/183.3/742.3s; v14 ~82.9/235.5/261.2s) are confirmed exact matches
to source. No cohort anywhere (intact or reconstructed) reports p75/IQR.

The immediately-prior night/dusk tranche (Gate A True-Latency Tail Closure
& Final Lane R Decision v1) obtained **n=1** (269.3s), independently
judged likely a false/static-object sample and never counted toward
convergence — retained historically only, per the brief's §7 instruction,
and unchanged by tonight (no attempt was made to reinterpret or requalify
it).

**Sized-cohort tail range:** 261.2s (v14) – 865.2s (v11, reconstructed/
supporting only); among strictly intact, live-measured cohorts alone,
261.2s (v14) – 742.3s (v10). **Median range:** 82.9s (v14) – 115.7s (v11).

## Session duration

**Zero.** No measured Observation was opened. (The brief's §8 45–75 minute
target applies only once the daylight gate passes; it was never reached.)

## Independent-recorder representativeness

Not run — no live session, so no independent-recorder frames exist for
tonight. Nothing to assess.

## Ledger completeness

Not applicable — no live session ran tonight, so no `raw_detections`/
`track_generations`/`proposal_outcomes` ledger data was produced to
reconcile. The accepted collector tooling itself was not exercised.

## Raw procedural latency samples

None. n=0 for tonight.

## Biological validity of samples

Not applicable — no samples were produced tonight.

## Qualifying latency distribution

Unchanged from the accepted pre-milestone state (reproduced in full
above): three intact cohorts (v9 n=24, v10 n=11, v14 n=14) plus one
supporting/reconstructed cohort (v11 n=23). No new sample was added
tonight, and none is fabricated here — per the brief's own §16 instruction
not to fabricate percentile precision unsupported by n, reporting n=0 new
samples honestly rather than inventing a distribution.

## >300s tail analysis

No new >300s sample was produced tonight, so no new causal tracing was
performed. For completeness, the existing accepted tail attributions
(unchanged, reproduced from source, not re-derived here) are:

- **v9 max (307.4s, candidate-027):** named as the session's own maximum;
  no more granular causal category stated in the source report beyond
  being a chained, 9-track-generation admission.
- **v10 max (742.3s, candidate-010):** root-caused, not assumed — 681.3s
  of the total traces to a second, separate, visually-confirmed genuine
  bird encounter beginning ~350s after candidate-010's own track ends, at
  the same feeder, with the accepted Visit-Continuity quiet-period/
  episode-boundary design extending the decision horizon while nearby
  activity is arbitrated. Category **A/B** (expected sustained-activity /
  quiet-period behavior under the accepted design), not a defect.
- **v11 max (865.2s, reconstructed):** attributed only to the same general
  Visit-Continuity/episode-boundary mechanism, without an individually
  identified causal Visit (unlike v9/v10) and explicitly not independently
  visually re-verified against footage. Category **A/B, with lower
  confidence** than v9/v10's individually-traced maxima.

## Prior static-object location check

**Not checked tonight** — no live session ran, so there is no admitted-
Visit stream from tonight to inspect for a recurrence at the same
feeder-perch location the immediately-prior (dusk) tranche's disputed n=1
sample came from. §18's check is specifically framed as something to do
"during this genuinely daylight run"; with no run, it is moot for
tonight and deferred to the next attempt.

## Cross-cohort convergence

**Unchanged — still unconverged.** This milestone produced no new sample
and therefore cannot move the convergence question in either direction.
Sized-cohort maxima still span 261.2s–865.2s (or 261.2–742.3s restricted
to strictly-intact cohorts); medians remain informative and reasonably
stable (~82.9–115.7s across the four sized cohorts). The tail distribution
tonight is identical to the tail distribution Gate A True-Latency Tail
Closure & Final Lane R Decision v1 left behind.

## Proposed latency budget

**None proposed — MORE EVIDENCE REQUIRED, unchanged.** Per the brief's own
§19 instruction not to ask "what number lets everything pass," and with
zero new samples obtained tonight, no median/p90/max budget can
responsibly be set, adopted, or revised in either direction from this
milestone.

## Eight-metric final Gate A state

Unchanged from the accepted pre-milestone state; reproduced from
[release-execution-state.md](release-execution-state.md) §6.R /
[gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md](gate-a-whole-scene-budget-remaining-evidence-correction-v1-report.md):

| # | Dimension | Status | Note |
|---|---|---|---|
| A | Recall | **ACCEPTED KNOWN LIMITATION — no numeric floor** | v12 87.5%, v14 64.7% conservative / 61.1% broader; unchanged |
| B | False-Visit rate | **READY FOR RELEASE BUDGET** (ordinary scenes) | ≤15%, from v12 (5.6%) + v14 (7.1%); person-in-frame regime separately tracked, non-blocking |
| C | Fragmentation | **READY FOR RELEASE BUDGET** | ≤5% |
| D | Duplicates | **READY FOR RELEASE BUDGET** | ≤2% |
| E | Useful evidence | **READY FOR RELEASE BUDGET** | ≥85% combined |
| F | Evidence survival | **READY FOR RELEASE BUDGET** | ≤15%, distinct-proposal basis, six cohorts converge 6.7–9.9% |
| G | True latency | **MORE EVIDENCE REQUIRED, unchanged** | Median informative (~82.9–115.7s); tail unconverged (261.2–865.2s across 4 sized cohorts); this milestone added zero samples |
| H | Monitoring | **READY FOR RELEASE BUDGET** | ≥97% |

Six of eight ready; recall is an accepted known limitation (not a
blocker); true latency remains the sole open Gate A item.

## Gate A decision

**Remains OPEN — TRUE LATENCY TAIL EVIDENCE REMAINS.** Unchanged. This
milestone never reached the point where it could move Gate A in either
direction — it stopped at the pre-deployment daylight gate, exactly as its
own governing brief's §4 instructs for a night start.

## Lane R decision

**Remains OPEN — RELEASE-CRITICAL — TRUE LATENCY TAIL EVIDENCE REMAINS.**
Unchanged.

## Residual limitations

- Same open item as before this milestone: true-latency tail convergence
  is the sole remaining Gate A blocker; nothing here narrows or widens it.
- Recall's accepted-known-limitation status (no numeric floor) is
  unaffected and unchanged.
- `using-mockingbird.md`'s existing crowded/sustained-activity recall
  disclosure ("This only affects unusually crowded moments at a single
  spot; ordinary, everyday activity is unaffected") was read directly and
  confirmed still accurate; no expansion made, per the brief's §21
  instruction, since this tranche produced no new information.
- The next attempt at this exact milestone should simply be re-run during
  genuine daylight hours (per the reference site's own established
  pattern, roughly mid-morning through mid-afternoon EDT, e.g. v10's
  07:39 EDT start or v14's 13:51 EDT start) — no other precondition
  changed tonight.

## Cleanup

Nothing was deployed, so there is nothing to stop, reconcile, or archive.
No credentials or scratch secrets were created. Camera Node pairing state
is unchanged from before this milestone (no pairing was attempted
tonight). The two read-only checks performed (ICMP ping + TCP connect
probe to `192.168.1.112:8787`; a `Get-Date`/`TimeZoneInfo` read via
`powershell.exe`) leave no residual state on either machine. No lock
files, partial lifecycle manifests, or stray processes were created by
this session; the worktree is exactly as it was at the start (verified:
same seven preserved untracked files, no new untracked files, no staged
changes) aside from this report file and the reconciliation edit described
below.

## Decision

**B**
