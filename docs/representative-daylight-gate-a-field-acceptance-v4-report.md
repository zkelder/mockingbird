# Representative Daylight Gate A Field Acceptance v4

Status: **Classification A** (real, live, valid, well-evidenced session -- Gate A itself remains
open). Real Observation, real independent denominator, meaningful genuine encounter activity,
trustworthy self-correcting accounting, a genuine new release-critical defect found and precisely
root-caused, no measurement-invalidating problem. See "Decision," below, for the full reasoning.

## Identity

- Repo HEAD at start and end: `4f1c5145c097d4102795575727a341e8e139579c` (unchanged; no product code
  was modified this session).
- Deployed build: `git_commit` `4f1c5145c097d4102795575727a341e8e139579c` (exact match, confirmed via
  `GET /api/product/instance` and independently re-confirmed via the live Observation Engine's own
  `model_runtime_metadata`), `build_id` `415c77e7153480da`, `app_version` `0.1.0`.
- Schema: `58` (unchanged).
- Deployment: a genuinely fresh, disposable dev-root
  (`C:\Users\<user>\AppData\Local\MockingBirdFieldAcceptanceV4`), **not** the operator's long-lived
  `MockingBirdDev` identity -- disposable local Administrator
  (`field-acceptance-v4@mockingbird.local`, created via `POST /api/setup/administrator`), a
  disposable Field Acceptance Operator bearer credential (`field-acceptance-56f947f3f37242d1`,
  6-hour TTL) minted for the actual session, no operator password/token/browser-cookie/manual step
  ever requested from or supplied by the user.
- Time/weather: Saturday 2026-08-29, 14:25:32-16:17:32 EDT (mid-afternoon, well inside the local
  daylight window). Overcast/hazy bright conditions, good visibility, no precipitation -- confirmed
  directly from real captured frames at three separate points across the session (start, ~51min,
  ~85min), not merely assumed from a forecast. A visible breeze was present throughout (branch/vine
  motion between spot-checked frames).
- Camera/Stream count: **1 real Stream** (`stream-87d3dd6fcdab`, "Field Acceptance V4"), backed by
  the real reference Camera Node (`node-<id>`, `<node-ip>:8787`), camera
  `picamera2-camera-0` ("Pi camera 1") of 8 the Node advertised. One full-frame Zone (`yard` type,
  polygon 0.02-0.98 both axes). A second real camera (the EMEET SmartCam S600 USB webcam) was
  checked and found not currently enumerable on the Windows host (PnP status "Unknown," i.e. not
  presently connected/redirected) -- consistent with the governing brief's "do not spend the
  daylight window... implementing a second camera"; one strong real-camera cohort was pursued
  instead, per the brief's own explicit allowance.
- Frozen config, unmodified throughout: MDv5a ONNX, `score_threshold` **0.1** (confirmed live from
  the Engine's own `model_runtime_metadata.model.score_threshold`), `nms_iou_threshold` 0.45,
  BioCLIP-2 + Identification Eligibility/Abstention, evidence-cache bound 128 (unmodified),
  concurrent-persistence bounded retry (unmodified), tracking/admission/assembly configuration
  (unmodified -- `ambiguous_gap_ms` 45000, `maximum_episode_duration_ms` 1,200,000, both hardcoded
  dataclass defaults, never overridden). MDv5a model fingerprints, read directly from the live
  Engine, are an **exact match** to the accepted provenance record: model fingerprint
  `b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc`, source-model fingerprint
  `fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef`. `CUDAExecutionProvider` was
  the selected execution provider (real GPU inference, RTX 4060 Ti, ~1.5GB CUDA residency delta
  during the session, back to idle after stop).

### Infrastructure decisions made live (both explicitly approved by the user, not assumed)

1. **Camera Node re-pairing.** The reference Camera Node's pairing is single-slot and disk-persisted
   (`/var/lib/mockingbird-camera-node/pairing.json`), confirmed by direct code reading
   (`_PairingState` in `src/mockingbird_node/app.py`) before touching anything. A genuinely fresh
   disposable Host instance cannot reach the same physical Node without either reusing the existing
   pairing secret (in substance, using the operator's own identity) or resetting the Node's pairing
   -- a real conflict between the governing brief's "disposable instance" and "do not use the
   operator's identity" instructions that no default resolves safely. Asked the user directly (not
   for a credential -- for permission on an infrastructure/hardware action); they chose "Reset &
   re-pair fresh." Executed via the exact, already-documented, supported recovery flow
   (`docs/camera-node-install-guide.md`'s "An already-paired Node" section: delete
   `pairing.json`, `systemctl restart mockingbird-camera-node`, retrieve the fresh one-time code via
   `journalctl`) -- not a novel workaround. The operator's own `MockingBirdDev` instance will need a
   one-time "Pair or repair Node" (Edit Camera Setup) before its own next use; Zones/history on that
   side are unaffected by design (per the same doc).
2. **Stopping the operator's already-running instance.** The packaged launcher only ever binds
   `127.0.0.1:8000` (no working `--port` override -- a pre-existing, already-documented limitation),
   and the operator's own `MockingBirdDev` instance (release `9ef0b17`, running since 10:52am) was
   occupying it. Confirmed first, not assumed: `monitored_stream_count: 0` (not actively observing),
   human idle 1+ day (`query user`). Asked the user directly; they approved. Stopped gracefully with
   identity re-verified immediately before the stop call (exact path + start time matched). Fully
   reversible -- release/userdata on disk untouched, relaunches with the same command.

### Operational note (own tooling-usage mistake, not a product defect, disclosed for completeness)

The first deploy attempt passed `--dev-root` as a bare relative name; `Path.resolve()` resolved it
against the WSL-side working directory rather than a Windows-local path, producing a real
`New-Item : Incorrect function` NTFS-junction-creation error partway through `materialize_release`
(junctions cannot target a `\\wsl.localhost\...` UNC path). Root-caused by direct code reading
(`args.dev_root.resolve()` vs. `windows_host.local_appdata()`'s own drvfs-mapped default in
`scripts/deploy_windows_dev.py`) -- not a bug in the tool itself. Fixed by passing an absolute
drvfs path (`/mnt/c/Users/<user>/AppData/Local/MockingBirdFieldAcceptanceV4`) on retry. Cleaned up
the resulting 4.7GB stray WSL-side directory (`git status` confirmed back to the exact expected
baseline afterward; the seven preserved untracked detector files were reconfirmed byte-identical,
same size/mtime as session start, throughout).

## Independent denominator

The accepted acceptance-recorder ran concurrently with Observation the entire session:
`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR` armed before deploy, cadence/bound settings reused
unchanged from the last two real sessions (1000ms / 5500 frames / 4.95GB cap). Real output: **4878
frames, 3.72GB**, first frame at +8.4s, last at +6704.8s of 6719.7s total session span = **99.78%
independent recording coverage**.

**Review methodology, including a real methodological correction made mid-analysis (disclosed, not
hidden):**

1. First pass: a blind, uniform 15-second-interval contact-sheet sample (426 frames, 15 composite
   sheets, covering the entire session) found **zero visible animals**. This was wrong/insufficient
   as a final conclusion, not a valid "quiet day" result -- disclosed explicitly rather than allowed
   to stand.
2. Cross-checked against the full counterfactual ledger, merged across all 12 periodic snapshots
   taken during the live session (necessary: the ledger's own raw-detection/track/proposal buffers
   are bounded and were actively evicting by session end -- 470 of 470 proposal outcomes and 1041 of
   1041 track generations were only fully recoverable by merging the 12 snapshots; the single final
   pull alone retained only 274/572 of them). The 15 confirmed tracks with the longest duration
   revealed a tight, consistent bounding-box cluster (**573 of 593 confirmed tracks, 96.6%**,
   centered at x~0.38-0.58, y~0.38-0.88) at a fixed screen location -- the frame's seed feeder.
3. Full-resolution frames pulled at those exact offsets (not the coarse blind sample) show real,
   repeated, multi-bird activity: 2-5 small brown/rosy finches or sparrows simultaneously, confirmed
   directly at t=336.5s, t=367.9s, t=2623.7s, and t=2656.2s. A further check of the 20/593 confirmed
   tracks whose bounding box centered *outside* the feeder region found a likely ground mammal
   (squirrel-shaped silhouette) at t~1709s and t~4472s, and further bird activity elsewhere in the
   canopy at t~3637s.
4. This is not circular reasoning under `acceptance_recorder.py`'s own stated caution (using
   pipeline output as the encounter denominator "would answer 'what did the pipeline notice'
   circularly") -- the detector/tracker's own raw output was used only to know *where in a
   112-minute recording to look at full resolution*; every genuine/not-genuine call was my own
   independent visual judgment, and the pipeline's own admission verdict (uniformly "not admitted")
   was never consulted as evidence either way.

**Genuine encounter picture, honestly bounded rather than forced to a false-precision integer:**
gap-segmenting the 573 feeder-region confirmed tracks by their own start/end times (120s threshold)
produces essentially **one continuous activity period with a single ~193-second lull**: segment 1
spans 2.2s-1792.0s (203 confirmed tracks), segment 2 spans 1985.5s-6661.0s (390 confirmed tracks).
Mean confirmed-track duration was 19.3s (min 5.0s, max 32.45s -- the tracker's own duration cap).
This does not cleanly decompose into "N discrete encounters" the way the sparser 2026-08-19/08-20
cohorts did; a precise per-visit count is not reliably extractable from either the blind sample or
the track-boundary data alone, and forcing one would overstate the precision this evidence actually
supports. **Conservative floor: at least 2 broad genuine wildlife-activity windows plus at least 1
separate ground-mammal sighting, near-continuous multi-individual bird activity for effectively the
entire 112-minute session, very likely representing dozens of true individual visits given the mean
confirmed-track duration.** No ambiguous/unusable case was force-resolved either way.

## Funnel: first irreversible loss stage

Stages 1-5 and 7 all demonstrably worked correctly this session, with direct evidence:

1. **Monitoring coverage** -- OK, 99.78% (recorder) / clean, unbroken Engine session (log).
2. **Detector opportunity** -- OK, MDv5a ran continuously at the confirmed 0.1 threshold.
3. **Detector localization** -- OK, real, tight, feeder-anchored bounding boxes.
4. **Tracking** -- OK, 593 confirmed animal-class tracker generations.
5. **Proposal generation** -- OK, up to 496 proposals observed across the session.
6. **Admission/rejection -- FIRST IRREVERSIBLE LOSS STAGE.** Every single proposal that ever formed
   from this near-continuous activity stayed in `blocked_continuation_pending` or
   `blocked_ambiguous_boundary` for its entire life and was never resolved to a terminal
   admit/reject decision -- see "Major finding," below, for the precise mechanism.
7. **Evidence capture** -- partially exercised regardless (`evidence_candidates_observed: 5202`),
   but moot: nothing downstream of it could ever be reached.
8-14. Never reached: evidence survival, candidate persistence, Event/Visit assembly, user-visible
   Visit, correct subject/evidence, species suggestion/abstention, reviewability -- all zero, all
   for the same single upstream reason.

This is **not** "the detector missed something" (it did not) and **not** "the false-positive-first
account overrode a fixed number" -- it is a genuine assembly/admission-arbitration gap, precisely
isolated to stage 6.

## Major finding: complete admission failure under sustained near-continuous activity (P0, new)

**Symptom, directly measured:** `candidates_created` stayed at exactly 0 for the entire ~112-minute
session. Final/settled counters (re-confirmed twice, once immediately at stop and again ~9 minutes
later, ruling out an async-completion race): `track_updates_observed=17177`,
`evidence_candidates_observed=5202`, `proposals_observed` up to 496, `candidates_created=0`,
`candidates_suppressed` all of them (`blocked_continuation_pending=256`/
`episode_boundary_not_yet_final`, `blocked_ambiguous_boundary=184`/
`proposal_boundary_ambiguous_with_adjacent_proposal`, `blocked_missing_evidence=30`/
`no_persistable_evidence_bytes`). Zero `blocked_shadow_mode`. **Zero real Visits exist for this
Stream** (`GET /api/visits` returns only the two pre-existing, unrelated demo rows).

**Root cause, established by direct code reading (not speculation):**

- `continuation_pending` (`visit_episode_assembler.py:919-921`) is computed as
  `known_horizon_ms - proposal.end_offset_ms <= ambiguous_gap_ms`, where `ambiguous_gap_ms` is a
  hardcoded **45,000ms** dataclass default (`visit_episode_assembler.py:389`), never overridden by
  any real production caller. `known_horizon_ms` advances on every analyzed frame and is threaded
  into assembly on a **10-second tick** (`engine_runtime.py:143,1157-1165`). The gate that turns
  this into `blocked_continuation_pending` (`candidate_visit_authority.py:445-448`) simply reads
  this precomputed flag.
- Because `assemble_visit_episodes` reruns from scratch every tick and each newly-extended chain
  gets a fresh, differently-hashed `proposal_id` (`visit_episode_assembler.py:862-864`), **as long
  as some new tracklet keeps merging onto (or forming an ambiguous link with) the same still-open
  chain within each rolling 45-second window, the current proposal representing that chain never
  accumulates 45 seconds of silence and never resolves on its own.** `maximum_episode_duration_ms`
  (20 minutes) does not help -- it only forks a new, equally-startable chain once a single glued
  span gets too long; it bounds fragment *size*, not time-to-*decision*.
- `resolve_ambiguous_boundary_arbitration` (`candidate_visit_authority.py:170-232`) runs every tick
  too, but only ever picks a winner once **every member of the full connected ambiguous component**
  (transitive closure, per the accepted "Ambiguous-Boundary Transitive Fragmentation Closure v1"
  fix) has `continuation_pending == False`. Continuous activity keeps enlarging that component for
  exactly the same reason, starving arbitration through the identical mechanism one level up.
- **The only design-intended escape is session end**: the finalize tick passes
  `known_horizon_ms=None`, which forces `continuation_pending=False` for every proposal
  unconditionally (`visit_episode_assembler.py:920`; documented explicitly in
  `docs/tracklet-visit-assembly-contract.md:334-336` as exactly the fix for "nothing is left
  waiting forever"), and the code's own `finally:` block (`engine_runtime.py:1166-1240`) is written
  to run this finalize tick unconditionally on stop, even if `session.stop()` itself raises.

**Open, disclosed, unresolved question:** per the code above, stopping the session *should* have
forced every pending/ambiguous proposal to a final decision and admitted at least the
best-evidenced member of each now-closed component -- yet the real stop response
(`stopped_reason: "user_stopped"`, `state: "stopped"`) still showed `candidates_created: 0`, and a
re-check ~9 minutes later showed the same. Zero `blocked_shadow_mode` entries argue against the one
concretely-identified race in this path (the 20-second `stop()`-join timeout reverting authority to
shadow mid-finalize). Whether the finalize tick's *intended* rescue genuinely fired and still
produced zero admits for a separate reason, or did not fire as designed, could not be determined
from outside the running process without adding new instrumentation/debug logging -- which this
milestone deliberately did not do (no product code was touched). **This is disclosed as a precise,
unresolved sub-question for the eventual fix work, not glossed over or guessed at.**

**Was this anticipated?** No. `docs/tracklet-visit-assembly-contract.md`'s "Episode finality" and
"Ambiguous boundary arbitration" sections document the general risk class and cite three real prior
incidents (2026-08-10 duplicate, 2026-08-17 permanent block, 2026-08-19 cache eviction) -- in every
one of those, the session still produced admitted Visits; none involved an entire live session
admitting zero. `roadmap.md`'s only adjacent, already-open item ("crowded-feeder/NMS... no
dedicated benchmark slice") is a detection/NMS-level concern (multiple subjects competing for one
detection box), a different mechanism from this assembly-layer chain-regrowth starvation. This
appears to be a genuinely new, previously-undocumented failure mode -- the third and most severe
member of a now-recognizable family, and the first field case where the family's own designed
resolution mechanism (not a downstream side effect of it) itself did not visibly fire.

**Fix disposition, per the governing brief's own bar (Section 16): not attempted.** A trustworthy
fix needs (per direct assessment against the existing code, not a guess): component-level
force-decision semantics that respect the transitive-ambiguous-component invariant (a naive
per-proposal timeout risks reopening the exact premature-split defect the transitive-closure fix
was built to close); a calibrated threshold validated against real field sessions, given every
existing bound in this module is justified by specific prior field evidence and this exact
conservative-delay tradeoff is a deliberate, documented product decision
(`docs/candidate-visit-authority-contract.md`: "locking in a possibly-wrong episode grouping... is
a worse failure than not creating one yet"); and very likely a second look at the already-disclosed
128-entry evidence-cache bound, since forcing more proposals to a decision sooner only helps if
their evidence bytes are still cached at that moment (this session already shows 30
`blocked_missing_evidence` outcomes with no forced-decision fix in play at all). This is comparable
in scope to a full milestone (comparable to "Admission Recall Investigation + Conditional Fix v1"),
not a bounded one-line change, and does not belong inside a field-measurement session. **Stopping
here with this precise defect contract, per the brief's own explicit instruction for exactly this
situation.**

## Gate A metrics (this session)

### Encounter/Visit
- Genuine encounters: at least 2 broad activity windows + 1 separate ground-mammal sighting (see
  "Independent denominator" -- a precise integer is not honestly extractable; true individual-visit
  count is very likely in the dozens).
- Encounters represented by >=1 useful Visit: **0**.
- **End-to-end Visit recall: 0%** (robust to exactly how the denominator is counted, since the
  numerator is 0 under any reasonable accounting).
- Misses: all of them, all traced to the single stage-6 cause above -- not "detector misses."
- False Visits: 0/0 (no Visits exist at all). False-Visit rate: undefined (no denominator).
- Fragmented encounters / fragmentation rate: not meaningfully computable -- nothing reached
  Visit-assembly to be judged fragmented or not.
- Duplicate Visits / duplicate rate: 0 (no Visits exist).
- Incorrect merges: 0 observed.
- Simultaneous-subject result: not exercised to a Visit outcome (multiple birds were simultaneously
  present in several full-resolution spot-checks, but the multi-subject assembly logic was never
  reached, since nothing admitted at all).

### Evidence
- Visits with useful evidence: 0/0.
- Useful-evidence/evidence-survival rate: undefined (no admitted candidate ever reached the
  evidence-survival stage to be judged).
- Wrong-subject evidence: none observed (nothing was ever surfaced to judge).
- Empty/background evidence: none -- every full-resolution frame independently inspected showed a
  real subject, not background.
- Attribution correctness: N/A, no Visit exists to attribute.

### Monitoring
- Intended duration: ~90-100 minutes (matching precedent), extended modestly and deliberately to
  ~112 minutes given the "enough genuine encounters" priority over a fixed clock, given zero
  admissions were still occurring at the 90-minute mark.
- Actual covered duration: 111.99 minutes (6719.7s), clean start/stop, `stopped_reason:
  user_stopped`.
- Coverage percentage: 99.78% (independent recorder).
- Outages/reconnects: zero (`camera_connected: true` throughout; zero
  `analysis_stream_unavailable`-class log lines; log file entirely clean, zero ERROR/CRITICAL
  lines).
- Excluded periods: none.

### Latency
Not meaningfully computable this session in the capture-to-visible-Visit sense the brief asks for,
for the direct reason that nothing ever became visible -- there is no admitted-Visit timestamp to
subtract from. This is itself evidence, not a gap in measurement: latency is undefined exactly
because of the stage-6 failure documented above. Species-enrichment latency is separately N/A for
the same reason (see "Species," below). Consistent with the research-agent finding that neither
prior cohort report ever populated a metric under this exact label either -- this remains, across
all cohorts to date, an unestablished measurement, not merely unlucky this session.

## Persistence

Grepped the full session log (`mockingbird.log`, `%LOCALAPPDATA%\MockingBirdFieldAcceptanceV4\
userdata\logs\`) for `observation_candidate_visit_persistence_contention`: **zero occurrences**.
Zero ERROR/CRITICAL lines anywhere in the log. This is a single-Stream session, so genuine
cross-Stream SQLite write contention was structurally unlikely to occur regardless -- reporting
zero as a valid, real result, per the governing brief's own explicit allowance, not silence.

## Species

**N/A this session.** Zero Visits were ever created for this Stream, so BioCLIP never ran against
anything from this session, and there is no suggestion/abstention behavior to report. The entire
species-assistance question is moot downstream of the stage-6 admission failure -- this is itself
the honest answer, not an omission.

## Product findings (P0/P1 only)

- **P0** -- the admission-starvation defect documented above in full.
- **P0/P1 (product-surface, live-checked)** -- after ~112 minutes of real, sustained, multi-bird
  activity, `GET /api/dashboard/summary` for this Stream shows `open_activity_session_count: 0`,
  `needs_review_visit_count: 0`, `latest_visit: null`, `camera_attention: []`, `warnings: []` -- a
  user watching this exact scenario live would see **zero signal** that anything happened at all.
  This is the precise failure mode `roadmap.md` already names as unacceptable ("A delayed Visit
  must never look, to the user, like MockingBird saw nothing") -- except here it is not a delay,
  nothing is ever surfaced. Same root cause as the P0 above (nothing ever reaches a state the
  dashboard has any fact to show), not a second, independent defect -- listed separately here
  because it is the concrete, user-facing consequence a product reviewer would actually see.
- No other P0/P1 found. Camera health, storage health (`getting_low` tier -- a real, pre-existing,
  host-wide condition also present on the operator's own instance, not caused by or specific to this
  session, not blocking), environmental context, and product identity all behaved as documented
  throughout.

## Cross-cohort comparison

| Metric | 2026-08-19 (primary cohort) | 2026-08-20 (cache-128 cohort) | **2026-08-29 (this session)** |
|---|---|---|---|
| Duration | 92.2 min | 90m23s | **112.0 min** |
| Recorder coverage | 99.64% | full, no early stop | **99.78%** |
| Genuine encounters | 22 (conservative ceiling) | >=9-10 | **>=2 broad windows (likely dozens of individual visits) + 1 mammal** |
| Visits created | 21 | 12 | **0** |
| End-to-end Visit recall | 68.2% (15/22) | not separately restated | **0%** |
| False-Visit rate | 9.5% (2/21) | 2/12 likely-false | **undefined (0/0)** |
| Fragmentation | 2 encounters | not separately restated | **not computable (nothing assembled)** |
| Duplicates | 3 Visits | 0 confirmed | **0 (no Visits)** |
| Species suggestion availability | 18/18 = 100% | 12/12 = 100% | **N/A (0 Visits)** |
| Persistence contention | n/a (fix not yet built) | n/a (fix not yet built) | **0 occurrences (fix in place, unexercised by contention)** |
| Decision | B | A (cache-128 proof) | **A (this milestone's own execution)** |

This session is not a like-for-like replacement for the prior two -- it adds a third, structurally
different data point (a busy, popular feeder producing near-continuous activity) rather than a
repeat of the sparser single-subject-at-a-time scenario the first two cohorts captured. The 0%
result does not average against or dilute the 68.2%/cache-128 results; it exposes a distinct,
previously-unmeasured failure mode those sessions' own conditions never happened to trigger.

## Candidate release budgets

**Not proposed. Evidence remains actively insufficient, and this session makes that more true, not
less.** Three real cohorts (68.2%, an implicit high recall for its own smaller/sparser denominator,
0%) span the entire possible range of end-to-end Visit recall. Per `roadmap.md`'s own standing
instruction, one session's measurement is not yet a budget on any of the three; a third,
maximally-divergent data point does not converge them into one. More specifically: **proposing a
minimum-recall budget right now would either (a) be set so low it is meaningless (to
accommodate a 0% real session), or (b) be set from the two better cohorts alone, silently
discounting a real, reproduced, severe defect as if it were noise.** Neither is honest. The
concrete, precise evidence this milestone adds instead: a newly-discovered, real, previously
unmeasured failure mode (sustained near-continuous activity => 0% recall) that must be fixed and
then re-measured before a minimum-recall number means anything. All other budget dimensions
(false-Visit rate, fragmentation, duplicate rate, useful-evidence rate, capture-to-visible latency,
monitoring coverage) remain exactly as unestablished as `roadmap.md` already states, for the
reasons given in each metric's own subsection above -- this session did not newly establish any of
them either, since nothing reached the stages those metrics describe.

## Remaining Gate A gap

Precisely, in order of priority: (1) fix the stage-6 admission-starvation defect this milestone
found and root-caused (design a component-aware, field-validated forced-decision mechanism;
re-examine the evidence-cache bound in the same pass; resolve the open finalize-on-stop question
above with real instrumentation); (2) re-run a representative daylight session against the same or
a similarly busy real Stream, post-fix, to obtain the field proof that fix actually works, exactly
the same live-proof discipline this project has applied to every other admission-layer fix; (3)
only then does the accumulated evidence (four-plus real cohorts, no known unresolved defect)
become a reasonable basis for proposing numeric release budgets. Multi-subject Visit-assembly
correctness under genuinely simultaneous multi-bird presence (several full-resolution frames this
session showed 2-5 birds at once) remains separately untested end-to-end, since nothing here ever
reached Visit assembly to exercise it.

## Decision

**Classification A.** Representative daylight conditions (directly, visually confirmed, not
assumed); real Observation against the real reference Camera Node, deployed via the exact
disposable-instance path the governing brief specifies; a valid independent denominator,
established correctly only after a real mid-session methodological self-correction (disclosed
plainly, not hidden); a meaningful genuine-encounter count (near-continuous multi-bird activity for
effectively the entire session, plus a separate mammal); trustworthy, self-checking accounting
throughout (own tooling mistakes found and fixed, own initial blind-review conclusion caught and
corrected, disk/GPU/log state independently re-verified rather than assumed); no
measurement-invalidating defect -- the defect found *is* the measurement, not a corruption of it;
every metric captured as far as this session's real instrumentation permits, with every genuinely
unmeasurable one (latency, fragmentation, species) stated as such rather than invented. Per the
governing brief's own §19: "A milestone can be A while Gate A remains open" -- Gate A is further
from closed than before this session in the sense that a real, previously-unknown, severe defect is
now on the record, which is exactly what a genuinely rigorous field-acceptance session is for.
