# Field Validation Closure v1 -- closure report

**Acceptance (recorded 2026-09-26):** accepted on cumulative evidence --
this report's `d5dd1d9` field run plus the field corrections accepted at
`83a0e86` and the Today truth repair accepted at `a9878a8`. Not a claim that
the original validation below was re-run unchanged; see
`release-execution-state.md` §3.

Status: real-hardware field validation of MockingBird v0.1 against a native
Windows Host, the real reference Camera Node, a real camera, a real LAN, real
field media, and the accepted production ML pipeline. Not a broad code audit,
not a feature milestone, not Gate G, not an external participant study.

**No product-code change was made by this milestone.** Every defect found is
reported, root-caused and classified; none met the bar this milestone's own
Field Defect Policy sets for a correction (see §Q/§R for the reasoning on
each). The repository change is this report plus the accepted baseline delta
in `docs/release-execution-state.md` §3.

## A. Starting baseline

Verified directly, not assumed:

| Fact | Expected | Observed |
| --- | --- | --- |
| Repository | `/home/zkelder/projects/mockingbird-active` | same |
| Branch | `main` | `main` |
| HEAD | `d5dd1d9` | `d5dd1d9` |
| Schema (source of truth) | `v60` | `CURRENT_DATABASE_SCHEMA_VERSION = 60` (`src/mockingbird/storage/database.py:46`) |
| Latest accepted milestone | Performance / Scale / Stability Closure v1 | matches, plus the two follow-ons below |
| Writer ownership | this session | sole writer; no peer session active |

`git status` at entry showed exactly the seven protected untracked detector
files plus `uv.lock`, and no modified tracked file.

Two milestones had landed after Performance / Scale / Stability Closure v1
and were reconciled rather than re-litigated: Review Queue Scale Closure v1
and Remaining Performance P1 Closure v1 (commits `1919017`..`d5dd1d9`).
`docs/release-execution-state.md` §3 was updated with exactly that accepted
delta -- accepted HEAD `d5dd1d9`, schema `v60`, no remaining performance
P0/P1, P2 still deferred, current authorized milestone = Field Validation
Closure v1 -- and no unrelated scheduler history was rewritten.

## B. Writer safety / repository state

All seven protected untracked files were hashed at entry, mid-run, and at the
commit boundary; every hash is unchanged and every file remains untracked.
Staging used explicit paths only -- never `git add -A`, never a bare
`src`/`tests` path.

| File | SHA-256 (first 16) |
| --- | --- |
| `docs/wildlife-detector-training-contract.md.orig` | `63f9e5ba142069da` |
| `scripts/evaluate_small_bird_detector.py` | `81cdff0423f12112` |
| `scripts/materialize_wildlife_stage2.py.orig` | `ade97d9d46f44661` |
| `scripts/train_wildlife_stage2_rfdetr.py.orig` | `a24aa6e294c04df1` |
| `src/mockingbird/detectors/small_bird_benchmark.py` | `e85a2315fbe1487e` |
| `src/mockingbird/training/wildlife.py.orig` | `548f0706b5498b02` |
| `tests/test_small_bird_benchmark.py` | `abad318b8df14c20` |

## C. Previously accepted field evidence (not re-run)

The inventory below was built from the repository's own accepted record
before any hardware was touched, specifically to avoid re-running closed work.

| Item | Class | Accepted evidence |
| --- | --- | --- |
| Clean Camera Node pairing / provisioning | **A -- proven, frozen** | *Authenticated Camera Node Golden-Path Capture & Preview Acceptance v1* (2026-09-03, classification A): real Add Camera pairing/preview/complete via a genuinely fresh disposable Host, real authenticated captures decoded end to end, real Chromium/Playwright proof. **Lane G moved to `CLOSED -- RELEASE-CRITICAL` in that milestone.** |
| Camera Node disconnect / auto-reconnect | A (re-proven here at `d5dd1d9`) | *Repeat Frozen Candidate Endurance & Recovery v2* (2026-09-17): all 10 recovery criteria live at `0135801` |
| Real daylight wildlife recall / detector behaviour | A | Gate A field-acceptance chain v4..v14; *Lane R Release-Budget Adjudication & Gate A Decision v1* -- **GATE A PASS, LANE R CLOSED** |
| Native-Windows packaged Local Only / privacy | A | *Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1* (`unshare --net` offline proof) |
| Doctor media-integrity relative-path defect | fix landed, **field-unverified** | *Pre-Release Trust & Correctness Correction v1* fixed it; never verified against real Camera Node output -- carried forward as an obligation (§D) |
| BirdNET / acoustic | D -- out of scope | optional; not configured in this topology (`acoustic_analysis_runs` = 0) |

**The historic item this milestone was told to scrutinise -- the deferred
real Camera Node pairing proof -- is already closed.** It was closed on
2026-09-03, two milestones before the memory-level notes that still described
it as outstanding. This report re-confirms the *existing* pairing works end to
end at `d5dd1d9` (§F) but deliberately did not force a fresh re-pair of the
shared reference device.

## D. Outstanding field obligations entering the milestone

1. **B** -- Confirm the Doctor media-integrity fix against *real*
   observation-engine-created Camera Node evidence, not a hand-seeded
   manual-import-shaped asset. (The original root-cause record explicitly
   warned that a fix validated only on the seeded shape could leave the real
   shape open.)
2. **B** -- Prove disconnect / reconnect / Camera Node restart / **Host**
   restart recovery at the *accepted* baseline `d5dd1d9` + schema `v60`
   (prior proof was at `0135801`, 37 commits and one schema version behind).
3. **B** -- Complete the product loop on real Camera Node evidence: human
   correction to Reviewed truth, and history reflecting it.
4. **B** -- Confirm health/diagnostics truthfulness against real physical
   states, and Local Only behaviour live.
5. **B** -- Timestamp / ordering sanity across Host, Node and stored evidence.

## E. Test topology

All facts below were read from the live systems, not assumed.

**Host (native Windows -- the first-class acceptance target):**

| | |
| --- | --- |
| OS | Microsoft Windows NT 10.0.19045.0 (Windows 10 22H2) |
| Build under test | `d5dd1d9`, confirmed via the product's own `GET /api/product/instance` (`git_commit d5dd1d9fed00487c2469daede33eaa5afbd53073`), not via any deploy helper's claim |
| Runtime | packaged local product, embedded CPython 3.12, `onnxruntime-gpu 1.28.0` |
| GPU | NVIDIA GeForce RTX 4060 Ti -- **CUDA execution provider active** (`detector_provider_key: "onnx-cuda"`, `device_type: "GPU"`) |
| Detector | **MDv5a** `md-v5a` / `MDv5a.0.1-onnx-opset18`, ONNX, bundle fingerprint verified, `model_bundle_compatible: true` |
| Species ID | **BioCLIP 2** `bioclip-2-vit-l-14`, `device: cpu`, weights SHA-256 verified -- matches the accepted "species/acoustic CPU-only by design" posture |
| Data home | a disposable dev instance carrying **real prior field data** (165 Visits / 329 media assets at entry) |
| Schema | migrated **v59 -> v60** on this real field database during deployment |
| Local Only | verified live, §P |

**Camera Node (reference hardware, not product identity):**

| | |
| --- | --- |
| Hardware | Raspberry Pi 4 Model B Rev 1.5 |
| OS / kernel | Debian GNU/Linux 13 (trixie), `6.18.34+rpt-rpi-v8` |
| Python / service | 3.13.5, node service version `0.1.0` |
| Camera | real `ov64a40` CSI sensor via libcamera/picamera2 (a 64 MP module), one real camera + one permanent `v4l2-no-camera` placeholder |
| Pairing | pre-existing, `pairing_required: false` |
| Network | ordinary LAN, Host `192.168.1.50` <-> Node `192.168.1.112:8787` |

**Date/time of the field session:** 2026-09-25, roughly 04:55Z-05:30Z
(00:55-01:30 local, EDT).

**Observation-class labelling.** Everything in §F-§P is **real hardware**
unless explicitly marked otherwise. There is **no simulated and no synthetic
fixture evidence** in this report's field sections. The one important honest
limitation is daylight: the practical test window was the middle of the
night, so **no naturally-occurring wildlife was available**, and none is
claimed (§J).

## F. Pairing / provisioning result

**PREVIOUSLY ACCEPTED (Lane G `CLOSED`), re-confirmed live at `d5dd1d9`.**

A genuinely clean first-pairing was **deliberately not forced**. The reference
Node's pairing model is single-credential and the device is shared; the brief
itself directs that irreplaceable field configuration must not be destroyed
merely to manufacture a fresh-pairing test, and the accepted 2026-09-03
milestone already proved clean pairing end to end on a fresh disposable Host.
Re-pairing would have destroyed the working credential for no new information.

What *was* proven live on the accepted build:

- the existing pairing authenticates -- the Host opened a real authenticated
  analysis stream to the Node (`ESTAB 192.168.1.50:57833 -> 192.168.1.112:8787`);
- configuration exchange works -- the Host resolved the paired camera and
  Stream and loaded the Observation Engine (`engine_load_duration_ms 9947.1`);
- camera and Stream availability are real -- `available_camera_count: 1`,
  `camera_connected: true`, frames flowing (`last_healthy_frame_at` advancing);
- **pairing survived a full Camera Node OS reboot** -- `pairing_required:
  false` immediately after the reboot, with no re-pair and no user action (§H);
- health/UI state is honest in all three physical conditions (§O).

## G. Disconnect / reconnect result

Real interruption using the smallest reversible mechanism (`systemctl stop`
over SSH), never a power cut. Host remained running throughout.

| Moment | Time (UTC) | Observation |
| --- | --- | --- |
| Baseline | 05:07:39 | `state=observing`, `camera_connected=true` |
| Node service stopped | 05:07:45 | Node HTTP unreachable, confirmed |
| Host reports degraded | 05:08:00 | `camera_connected=false` within **15 s** -- honest, not a stale "connected" |
| Host transitions | 05:09:02 | `state=stopped`, `stopped_reason=camera_unavailable` -- **77 s** after outage, inside the documented ~70-90 s `AnalysisStreamRetryPolicy` budget |
| Node service restarted | 05:09:13 | same `boot_id`, `pairing_required: false` |
| **Host auto-resumed** | 05:09:45 | **32 s** after the Node returned, matching `CameraNodeRecoverySupervisor`'s first 30 s backoff |

- **Outage duration:** ~88 s. **Detection:** 77 s. **Recovery:** 32 s.
- **Manual steps required: none.** No hidden developer intervention: the
  resume is visible in the Host's own structured log as exactly one
  `camera_node_auto_resume_attempt` (05:09:39.502) followed by exactly one
  `session_start` (05:09:39.503) -- no duplicate supervision loop.
- **Lost / duplicated work: none.** `streams=2`, `sources=2` unchanged;
  Visit/Event/media counts unchanged across the cycle; `pragma quick_check` ok.

**PASS.**

## H. Camera Node restart result

Escalated beyond a service bounce to a **genuine OS reboot** of the real Pi,
which also exercises boot identity and a cold camera re-initialisation.

| Moment | Time (UTC) | Observation |
| --- | --- | --- |
| Pre-reboot | 05:11:39 | `boot_id 1d7c1de6-…`, Host observing |
| Node unreachable | ~05:12:15 | real reboot in progress |
| Node back | 05:12:39 | **new `boot_id d5aa7d34-…`**, `os_uptime 42 s` -- a genuine reboot, not a service restart |
| Pairing | 05:12:39 | `pairing_required: false` -- **pairing persisted across the reboot** |
| Host during outage | 05:12:17-05:12:55 | stayed `state=observing` with `camera_connected=false` -- honestly degraded, never falsely connected |
| Host reconnected | 05:13:11 | `camera_connected=true`, **56 s** total, *same* session (`started_at` unchanged) |

Because the outage (~24 s) was shorter than the 77 s camera-unavailable
threshold, the Host correctly recovered *within* the existing session rather
than tearing it down -- no session churn, no duplicate Stream/Source, no
duplicate Visit or Event state, and the health UI tracked the transition
accurately in both directions.

**PASS.** (Two real observations arising from this reboot -- a burst of false
candidate Visits during camera re-initialisation, and the Node's stale
startup self-test -- are reported in §Q.)

## I. Windows Host restart result

Restarted the **native Windows** Host with the Camera Node available, using
the product's own graceful-stop contract.

| Moment | Time (UTC) | Observation |
| --- | --- | --- |
| `POST /api/product/shutdown` | 05:21:06 | `{"accepted": true, …}` |
| Host down | 05:21:16 | port 8000 free; marker file `{"state": "clean"}` |
| Relaunched | 05:24:21 | packaged runtime, correct data home |
| Host answering | 05:24:32 | **+10 s** |

Verified after restart:

- build still `d5dd1d9`, `ready: true`;
- **`previous_shutdown_clean: true`** -- the graceful-stop -> restart path
  reports honestly;
- schema `v60`, **no migration needed and none run**;
- Place/Source/Stream relationships persisted -- `streams=2`, `sources=2`,
  **no duplicates**;
- Camera Node reconnected, `cameras.needs_attention_count: 0`;
- **Reviewed truth survived the restart** -- the Visit corrected in §L came
  back `review_status=reviewed`, `reviewed_label=false_positive`, with its
  original inference intact;
- **no manual database repair, no phantom-online state.**

**PASS**, with one genuine behavioural finding: **observation did not resume
by itself** (§Q-3).

*Process-honesty note.* A first relaunch attempt of mine used the packaged
`Start MockingBird.vbs` **without** setting `MOCKINGBIRD_HOME`, so it booted
against the default production data home instead of this dev instance. That
produced two alarming-looking readings -- a rejected bearer token and
`previous_shutdown_clean: false` -- which were **entirely artefacts of my own
launch error, not product defects**; both cleared once the Host was relaunched
against the correct home. The bearer token was independently proven correct by
hashing it and matching it against the stored `token_hash`. That stray run
migrated the (empty, 0-Visit) default home from `v59` to `v60`, taking a
verified pre-migration backup first; no user data existed there and none was
lost. Disclosed rather than quietly dropped.

## J. Real observation pipeline

A real Observation Engine session ran against the real camera on the accepted
build. The full path was exercised: **camera -> Camera Node -> Host ingestion
-> MDv5a detection -> identification eligibility -> BioCLIP-2 -> abstention ->
Review Queue -> human correction -> history/analytics.**

Live evidence that frames were genuinely captured and analysed (not idle):

- `runtime_kind: "camera_node_engine"`, `provider_key: "frame-driven-onnx-cuda"`;
- `last_healthy_frame_at` advancing in real time;
- a persistent LAN connection held open to the Node;
- the Pi's own temperature rising 38.9 °C -> 46.2 °C once capture began --
  independent physical corroboration;
- cumulative admission counters on the real Stream: **7,483 proposals
  observed, 166 candidates created, 7,317 suppressed** (~97.8 % suppression).

**Honest limitation -- no natural wildlife.** The practical test window was
00:55-01:30 local. The camera captured real night frames of the real
backyard (dark scene lit only by a neighbouring porch light). **No wildlife
appeared and none is claimed.** No synthetic or staged media was substituted,
and no controlled scene could be arranged, because this session had no
physical access to the camera's field of view. Real-wildlife detection and
recall therefore rest on the accepted Gate A daylight evidence (§C), which is
exactly what the brief directs.

The product loop was instead completed on **genuinely field-originated
evidence already held by this instance**: 163 of its 165 entry Visits are real
`visit-observation-candidate-*` records produced by this same Camera Node and
camera (the other two are seeded demo fixtures). That is real field evidence,
not a fixture.

**Epistemic state at each point** (per `docs/product-doctrine.md`):

| Point | Class | Evidence |
| --- | --- | --- |
| Camera frame / capture time / detector geometry | **Measured** | real JPEG assets with sizes and capture timestamps; MDv5a box in `full_frame_normalized` space |
| MDv5a subject proposal | **Measured -> Inferred** | broad `animal` class, explicitly "not species truth" per the model's own declared limitations |
| BioCLIP-2 species suggestion | **Inferred** | `suggested_label carolina_chickadee`, `confidence 0.728`, `status: pending`, full provenance (weights SHA-256, prompt recipe, `score_kind: candidate_relative_softmax`) |
| Review Queue entry | **Inferred** | `review_status: needs_review` |
| Human correction | **Reviewed** | `review_labels` row, `review_origin: human`, reviewer identity + timestamp |
| History / analytics | **Reviewed authoritative** | counted as `false_positive`, excluded from species history |

**No inference silently became Reviewed at any point.** The BioCLIP suggestion
stayed `pending` and the `species_guess` was preserved *unchanged* after human
correction -- Inferred and Reviewed coexist, with Reviewed authoritative.

## K. Detector / identification / abstention evidence

**Production detector, unmodified.** MDv5a ONNX on CUDA, accepted threshold
untouched, bundle fingerprint verified at load.

**Production visual identification, unmodified.** BioCLIP 2 on CPU, weights
verified (`model_weights_verified: true`), candidate pack "Backyard Core"
(14 local species), `score_kind: candidate_relative_softmax`.

**Identification eligibility / abstention policy is genuinely evaluated, not
decorative.** A real field suggestion carries its full policy record:

```
identification_policy: { policy_version: "identification-eligibility-v1",
  tier: "subject_focused", top1_label: "Carolina Chickadee",
  top1_score: 0.728, score_floor: 0.7, margin: 0.626, margin_floor: 0.2,
  abstained: false }
```

**Real abstention was observed on real field evidence, and no threshold was
weakened to produce it:**

1. **Whole-cohort abstention.** 76 of the 165 entry Visits (46 %) carry **no
   species guess at all** -- the system declined to name a species rather than
   guessing.
2. **Live abstention on this session's own evidence.** All three candidate
   Visits created during the live night session produced **zero
   `species_suggestions` rows** -- BioCLIP was not permitted to name a species
   on dark, low-quality night evidence. That is the accepted policy behaving
   correctly on genuinely marginal field input.

**Counter-evidence, reported honestly.** The identification policy did **not**
abstain on a scene artefact: Visit `…-165`'s subject box, which I inspected
directly at native resolution, contains an **empty blue seed feeder on a tree
branch and no bird**, yet BioCLIP returned "Carolina Chickadee" at 0.728 and
the policy admitted it (score and margin both cleared their floors). This is
**not a new finding** -- it is precisely the disclosed, still-open shape
recorded by *Strong-Confidence Subject-Evidence Viability & Scene-Artifact
Abstention v1*, which investigated this exact leaf/branch/feeder artefact
class and deliberately did not close it. The product's answer for this class
is human review, which worked (§L).

## L. Human review / correction loop

Performed on a **real field-originated Visit**, through the real product API,
signed in as a real user -- not a seeded fixture and not a direct database
write.

1. Signed in via `POST /api/auth/sign-in` -> "Frozen Endurance V2 Field
   Operator", role `administrator`.
2. **Reviewed the inferred identification** by actually looking at the
   evidence: extracted the `identification`-role asset
   (`media-candidate-327.jpg`, 3840x2160) and cropped it to the recorded
   subject box. It shows an empty feeder -- no bird.
3. **Corrected it** via `POST /api/review-labels` with
   `label=false_positive`, `review_origin=human`.
4. **Reviewed truth became authoritative:** `review_status needs_review ->
   reviewed`, `reviewed_label = false_positive`.
5. **Original evidence and inference preserved:** `species_guess` remains
   `carolina_chickadee`; the `species_suggestions` row is intact with its
   0.728 confidence; all three evidence assets remain linked. Nothing was
   overwritten or deleted.
6. **Found the record again** afterwards by id -- returns the reviewed state.
7. **Subsequent user-facing history reflects the correction:**
   `GET /api/analytics/summary` reports `species_counts: {"false_positive": 1}`
   with `label_categories: {"false_positive": "false_positive"}` and
   `species_label_ids: []` -- i.e. the corrected Visit is **excluded from
   species history**, which is the whole point of the correction.
8. **Survived a Host restart** (§I) unchanged.

**Review-queue count truth reconciles exactly.** The API reported
`review_queue_count = 165` while the database held 166 `needs_review` Visits;
the difference is exactly the one seeded demo Visit, which the accepted
demo-exclusion work removes from the queue. Likewise `visit_count = 166`
against 168 rows = 168 minus the two seeded demo Visits. **No count-truth
defect.**

**PASS.**

## M. Media / evidence integrity

This is the milestone's most important carried-forward obligation (§D-1), and
it is now **closed with real Camera Node evidence**.

**Ground truth established independently first.** All 329 entry media assets
were checked directly on disk: **329 present, 0 missing, 0 size-mismatched.**
Every one carries a *relative* `local_path` of the form
`data\media\imports\media-candidate-NNN.jpg` -- exactly the
observation-engine-created shape whose false-"missing" report was the
original defect, and exactly the shape the original root-cause record warned
must be used for re-verification.

**Doctor, run against that real evidence, reports the truth:**

```
[PASS] media_integrity
       The last 25 retained media file(s) checked out (present, correctly sized).
```

Run deliberately from working directory `C:\Windows` -- **not** the runtime
home -- which is the cwd-independence the fix specifically claims
(`_resolve_media_asset_path` tries `runtime_home / raw` first, then
`media_root / raw`). Re-confirmed `PASS` on a second, later run.

Also verified:

- original evidence exists and resolves; the `identification`, `context`,
  `classifier_same_frame` and `alternate` roles all map to real files;
- derived/evidence media corresponds to the correct observation -- the
  `identification` asset for Visit `…-165` is the exact frame the classifier
  crop was taken from (`classifier_input.source_media_asset_id =
  media-candidate-327`, matching the linked asset);
- **no absolute server path is leaked** to the client: the `Visit` payload
  exposes no filesystem path (`representative_media_path: null`), and stored
  paths are relative;
- **no false missing-media warning** was generated for intact field evidence.

**PASS -- the Doctor media-integrity relative-path regression is now verified
closed against real Camera Node output.**

## N. Timestamp / ordering sanity

| Check | Result |
| --- | --- |
| Host vs Node clock | agree within the ~±0.5 s resolution of the measurement (PowerShell start-up cost dominates the window); **no material disagreement** |
| Node self-reported time | `node_time` / `node_receive_time` consistent with Host UTC |
| Stored evidence timestamps | naive UTC in the database |
| API-served timestamps | explicit UTC with a `Z` suffix (`2026-09-17T16:27:29.368073Z`) -- **unambiguous at the API boundary** |
| Ordering | Visit/Event ordering consistent with capture order; no anomalies |
| Cross-check against reality | Visit `…-165` records `captured_at 23:25 UTC`; the image is plainly **dusk**, and 23:25 UTC = 19:25 EDT. **Consistent -- not an anomaly** |

**One real, reproduced defect found -- see §Q-1.** Server-side *local-time*
derivation on native Windows falls back to a fixed UTC offset, because
`zoneinfo` cannot resolve an IANA zone name on Windows without `tzdata`.

## O. Health / diagnostics truthfulness

Doctor and the product health surface were checked against three genuinely
different physical states. **In every case they told the truth.**

**State 1 -- Camera Node genuinely offline** (before the session started):

```
[WARN] camera_node   Camera Node offline -- last seen ~7316 minute(s) ago.
Overall: DEGRADED
```

Correct: ~5.08 days matches the last real contact. **Doctor did not say
"Healthy" while the physical observation pipeline was unavailable** -- the
single most important requirement of this stage.

**State 2 -- Camera Node genuinely online and observing:**

```
[PASS] camera_node   2 set-up cameras; no attention needed.
[PASS] media_integrity, detector_model, species_identification, gpu_cuda,
       database_schema, backup, ffmpeg, camera_node_transport
```

The check flipped WARN -> PASS with physical reality, in both directions.

**State 3 -- after a graceful shutdown and restart:** `previous_shutdown_clean:
true`, reported honestly.

Remaining non-PASS results, all **honest**:

- `[WARN] storage -- Free disk space is low (15.6 GB free)`: true.
- `[WARN] application -- The previous MockingBird run did not shut down
  cleanly`: **true, not the known false positive.** The authoritative
  in-process fact (`GET /api/product/health` -> `previous_shutdown_clean`)
  agreed, and after a genuinely graceful shutdown the same check correctly
  reported clean. The documented separate-process-CLI limitation of this
  check is pre-existing, already disclosed in the code, and was not
  re-litigated.
- `[PASS] acoustic_runtime -- BirdNET not installed`: correct and optional.
- `[PASS] clock` with detail `Host local timezone could not be resolved to a
  named zone; using a fixed UTC-offset fallback` -- honestly disclosed, and
  the substance of §Q-1.

The product also self-reports its own migration truthfully:
`database_schema_version: 60`, `database_migrated_from_version: 59`.

**PASS.**

## P. Local Only verification

Verified **live**, on the running native-Windows Host during an active
observation session, by enumerating every TCP connection owned by the
MockingBird process:

- listening socket bound to **`127.0.0.1:8000` only** -- loopback, not
  `0.0.0.0`;
- internal loopback connections between its own workers;
- **exactly one** off-box connection: `192.168.1.50 -> 192.168.1.112:8787`,
  the Camera Node on the local LAN;
- **zero connections to any non-private address.** No internet traffic.

No external weather/environmental provider is configured
(`environmental_context_settings` empty), and BirdNET is not installed. Core
functionality -- capture, detection, species identification, review, history
-- ran entirely locally, with GPU inference and BioCLIP executing on the Host.

**PASS.**

## Q. Field defects discovered

### Q-1. Native-Windows local-time rendering uses a fixed UTC offset (CONFIRMED, quantified, not v0.1-blocking by prior decision)

**Reproduced** directly in the packaged Windows runtime at `d5dd1d9`:

```
resolved tz : Eastern Daylight Time | IANA key: None
tzdata      : NOT present
  2026-07-15 16:00 UTC -> 12:00 EDT-0400   (correct)
  2026-12-15 16:00 UTC -> 12:00 "Eastern Daylight Time-0400"  (WRONG: should be 11:00 EST)
  2026-01-15 16:00 UTC -> 12:00 "Eastern Daylight Time-0400"  (WRONG)
```

**Root cause.** `resolve_host_local_timezone()` (`src/mockingbird/time_utils.py`)
resolves an IANA zone from (1) `TZ`, or (2) the `/etc/localtime` symlink --
both POSIX-only -- then falls back to a fixed-offset snapshot of the *current*
offset. Native Windows reaches neither path: it does not name its zone in IANA
terms, and `tzdata` is not in the packaged runtime. So one offset, sampled
once, is applied to every timestamp regardless of date.

**Impact.** For roughly five months of the year, any server-side local-time
rendering or DST-aware hour/day bucketing on a native-Windows Host is **off by
one hour**, and the zone is mislabelled (e.g. "Eastern Daylight Time" in
December). This matters because *when* wildlife visits is a core product
surface (per-species time-of-day patterns, Place activity, Story periods). The
API boundary itself is unaffected -- it serves explicit UTC (§N).

**Not fixed here, deliberately.** It is pre-existing and **already
deliberately disclosed** -- the resolver's own docstring documents this exact
Windows degradation as "honest," and Doctor announces it on every run. The
correct fix is not a one-line pin: adding `tzdata` alone is insufficient,
because no code path derives an IANA name on Windows at all; it needs a
Windows-registry -> IANA mapping (a new dependency or a bundled CLDR table)
plus validation across zones this session cannot exercise. That is adjacent
development, which this milestone's own policy forbids. **Recommended for the
next milestone**, with the magnitude above.

### Q-2. Camera Node startup self-test is served stale for the service's whole lifetime, and can contradict the live fields beside it (CONFIRMED, non-blocking)

**Reproduced twice, on real hardware.**

*First*, on the long-running service: for **6.4 days** every
`/node/v1/health` response returned

```
self_test: { status: "degraded", reasons: ["provider_enumeration_timed_out"],
             providers_initialized: false, camera_available: false }
```

while the *same payload* reported `status: "available"` and
`available_camera_count: 1` -- and the camera was in fact working (the Node's
own logs show it configuring streams up to 9248x6944).

*Second*, freshly, on the genuine cold boot in §H: 42 s after reboot the
self-test again reported `degraded / provider_enumeration_timed_out /
camera_available: false`, and the Host then successfully used that very camera
32 s later.

**Root cause.** `run_startup_self_test()` is executed **once** at startup
(`src/mockingbird_node/app.py:374`) and the resulting object is embedded
verbatim in every health response thereafter (`app.py:626`); the code
explicitly contrasts it with `storage`/`hardware`, which *are* re-read per
request. Its `provider.cameras()` probe is bounded at
`DEFAULT_SELF_TEST_TIMEOUT_SECONDS = 10.0`; on this real Pi 4 + 64 MP
`ov64a40`, cold-boot enumeration exceeds that budget, so the probe times out
and the resulting false `degraded` is then frozen for the process's lifetime.
The earlier 4.0 -> 10.0 s mitigation reduced but did not eliminate this.

**Impact -- bounded.** The Host **never reads `self_test`** (verified: zero
references in `src/mockingbird/` and in `web/`), so this never reaches the
product UI and never affects observation. It is visible to an operator reading
`/node/v1/health` directly and in `scripts/install_camera_node.py`'s
post-install summary line, which prints `self_test=degraded` -- so a first-time
installer can see "degraded" immediately after a *successful* install of a
*working* camera. The installer only reports it; it does not gate on it.

**Not fixed here, deliberately.** It is a diagnostic-truth wart that is
pessimistic (never a false "healthy"), invisible in the product, and harmless
to observation; the safe fix touches Node startup/health semantics and would
require a Node redeploy plus a fresh reboot-validation cycle. Recommended
direction: either re-evaluate the camera probe when a prior attempt timed out,
or reconcile the stale snapshot against the live enumeration already present
in the same payload.

### Q-3. Observation does not resume after a Host restart (CONFIRMED behaviour, product decision required)

After the graceful Host restart in §I -- with the Camera Node healthy and
reachable throughout -- the previously-observing Stream came back
`state=stopped`, and stayed stopped. A user must press **Start observing**
again.

**Mechanism, confirmed in code and by the API.**
`CameraNodeRecoverySupervisor` resumes only Streams whose most recent session
ended with `stopped_reason == "camera_unavailable"`. A Host restart leaves no
such reason, so nothing resumes it. The legacy durable-monitoring path does
not cover this either: enabling it on a Camera Node Stream is refused
outright, honestly and by design --

```
409: This Stream is a paired Camera Node. Camera Node streams use the
     Observation Engine (Start observing) rather than legacy durable monitoring.
```

**Impact.** For an unattended 24/7 field deployment on native Windows -- a
platform that reboots itself for updates -- observation stops silently after
any Host restart or power loss until a human notices. Node-side outages
recover beautifully (§G, §H); Host-side restarts do not.

**Not fixed here, deliberately.** Adding this means persisting a "should be
observing" intent across process restarts plus a startup reconciler -- new
capability, and a genuine product decision about unattended auto-start, not a
field correction. Flagged for the owner.

### Q-4. False-Visit burst during camera re-initialisation, with duplicated evidence bytes (observed, within accepted disclosed behaviour)

The live night session created **three candidate Visits** at 05:13:30,
05:13:45 and 05:14:00 from captures at 05:12:54-05:12:56 -- i.e. exactly as
the camera re-initialised after the §H reboot, on a dark static scene with no
wildlife present.

Honest reading of what this does and does not show:

- **Not corruption, not a truth violation.** All three correctly produced
  **zero species suggestions** (BioCLIP abstained), all sit in the review
  queue as `needs_review`, and no Reviewed truth was fabricated.
- **False Visits are accepted, disclosed product behaviour** (the 70-Visit
  cohort study measured a 52.9 % false-Visit rate; human review is the
  product's answer). This adds a specific, previously unrecorded *trigger*:
  post-restart camera re-initialisation transients.
- **Evidence-byte duplication.** The three Visits produced 10 media assets of
  which only **4 are distinct by content hash** -- the identification frames
  of all three Visits are byte-identical. The engine re-persists the same
  evidence per Visit rather than sharing it. Minor storage waste (~2.6 MB for
  one burst), worth noting only because storage is already `WARN`-low.

## R. Fixes, if any

**None.** No product code was modified. Each finding in §Q carries its
explicit reason for deferral: Q-1 is pre-existing, already disclosed, and its
correct fix is adjacent development; Q-2 is invisible to the product and
pessimistic in direction; Q-3 is a product decision about unattended
auto-start; Q-4 is within accepted, disclosed behaviour.

## S. Validation for fixes

Not applicable -- no code changed, so no Tier 1/2/3 run was owed. Consistent
with the brief's instruction not to burn a full Core run on a report-only
field-validation milestone with no product-code changes.

The *field* scenarios themselves were each exercised on real hardware and, for
the media-integrity obligation, re-run twice (two independent Doctor
invocations, from a non-home working directory) to confirm stability.

## T. Field acceptance matrix

| Dimension | Result | Basis |
| --- | --- | --- |
| Clean Camera Node pairing | **PREVIOUSLY ACCEPTED** | *Authenticated Camera Node Golden-Path Capture & Preview Acceptance v1* (2026-09-03, A); Lane G `CLOSED`. Existing pairing re-confirmed live at `d5dd1d9` and across a real reboot (§F, §H) |
| Node disconnect detection | **PASS** | 77 s to `camera_unavailable`, degraded at 15 s (§G) |
| Automatic reconnect | **PASS** | 32 s auto-resume, zero manual steps, single supervision event (§G) |
| Camera Node restart recovery | **PASS** | real OS reboot, new `boot_id`, pairing survived, 56 s recovery (§H) |
| Windows Host restart recovery | **PASS** | 10 s restart, relationships + Reviewed truth persisted, no repair, no duplicates (§I). See Q-3 for the non-resume behaviour |
| Real camera ingestion | **PASS** | real Node frames analysed live; physical corroboration (§J) |
| Production detector | **PASS** | MDv5a ONNX on CUDA, bundle verified, unmodified (§K) |
| Production visual ID | **PASS** | BioCLIP 2, weights verified, CPU, unmodified (§K) |
| Abstention / eligibility | **PASS** | `identification-eligibility-v1` evaluated with real floors; 46 % of cohort abstained; live night evidence abstained entirely (§K). Known scene-artefact non-abstention re-observed, already disclosed |
| Review Queue | **PASS** | queue count truthful and demo-excluded; bounded retrieval responsive (§L) |
| Correction to Reviewed truth | **PASS** | real field Visit corrected via the real API; Reviewed authoritative; inference preserved (§L) |
| Bird Log / history persistence | **PASS** | correction reflected in analytics; excluded from species history; survived restart (§L, §I) |
| Media integrity | **PASS** | 329/329 real assets intact; Doctor reports truthfully from a non-home cwd -- **carried-forward obligation closed** (§M) |
| Timestamps / ordering | **PASS with a confirmed defect** | clocks agree, API serves explicit UTC, ordering sane; native-Windows local-time fallback is Q-1 (§N) |
| Health / diagnostics | **PASS** | truthful across offline / online / post-restart states; never falsely "Healthy" (§O) |
| Local Only behaviour | **PASS** | loopback listener + one LAN connection to the Node; zero external traffic (§P) |
| Optional BirdNET | **NOT APPLICABLE** | not configured in this topology; explicitly not a closure requirement |
| 24/7 field reliability | **PREVIOUSLY ACCEPTED** | *24/7 Field Reliability Corrections v1* + *Repeat Endurance v2* recovery proof; no multi-day soak re-run, and none is claimed |

## U. Remaining v0.1 field blockers

**None identified.** No finding in §Q threatens data integrity, evidence
survival, truth boundaries, or recovery:

- no corruption (`pragma quick_check` ok throughout);
- no duplication of Streams, Sources, sessions or Reviewed truth;
- no silent promotion of inference to Reviewed truth;
- no evidence loss -- 329/329 intact at entry, 339/339 at exit.

Three items are placed before the owner as **decisions, not blockers**: Q-1
(native-Windows local time, quantified), Q-3 (no observation resume after Host
restart), and Q-2 (Node self-test staleness). Q-1 and Q-3 are the two worth a
deliberate decision before publication.

**Honest coverage limitation:** no naturally-occurring wildlife was available
in the night test window, so this milestone does not add new real-wildlife
recall evidence; that rests on the accepted Gate A body (§C, §J).

## V. Final HEAD / schema

- Repository HEAD at closure: `4ddc150` on
  `main` (report + `docs/release-execution-state.md` §3 delta only).
- Product schema: **v60**, unchanged by this milestone. The real field
  database was migrated `v59 -> v60` *by the accepted build itself* during
  deployment, with a verified 482 MB pre-migration backup, preserving all
  165 Visits / 144 Events / 329 media assets exactly.
- Camera Node service version: `0.1.0`, unchanged; **no Node code was
  deployed or modified.**

## W. Working tree / protected files

At the commit boundary: all seven protected untracked files **exist, remain
untracked, and are byte-identical** to their entry hashes (§B). `uv.lock`
remains untracked and unmodified. Only two tracked paths were touched, both
staged explicitly by full path:

- `docs/field-validation-closure-v1-report.md` (new)
- `docs/release-execution-state.md` (§3 accepted-delta insertion only)

## X. Push status

**Not pushed.** No tag, no publish, no remote operation of any kind.

## Y. Advisory next step only

Advisory, not an authorization. The two findings worth a deliberate owner
decision before publication are **Q-1** (native-Windows local-time offset --
quantified, user-visible in time-of-day surfaces) and **Q-3** (observation does
not resume after a Host restart, which matters for unattended 24/7 use). Both
fit naturally inside the expected next milestone, *Documentation / Diagnostics
/ Release Engineering Closure*, either as narrow corrections or as explicitly
documented limitations. **This report authorizes no milestone.**

---

# Addendum -- Native-Windows Field Reliability Corrections v1 (2026-09-25)

Added by *Native-Windows Field Reliability Corrections v1*, a bounded
correction milestone authorized specifically because **this report's own §Q-1
and §Q-3 had to be fixed before Field Validation Closure v1 could be
accepted**. Everything above is preserved unchanged: it is valid evidence of
what the `d5dd1d9` build actually did, and the two defects it recorded were
real and correctly characterised.

Full record:
[native-windows-field-reliability-corrections-v1-report.md](native-windows-field-reliability-corrections-v1-report.md)
(contract:
[native-windows-field-reliability-corrections-v1-contract.md](native-windows-field-reliability-corrections-v1-contract.md)).

**Both corrections were re-proven on this same real topology** -- the same
native-Windows Host, the same reference Raspberry Pi Camera Node
(`node-76ec8e53ae586dd0`), the same real `ov64a40` camera, the same real field
database. Build under test `15691d9`, confirmed via the product's own
`GET /api/product/instance`, not via any deploy helper's claim. The real field
database migrated **v60 -> v61** during deployment with every count preserved
exactly (169 Visits / 167 candidates / 343 media / 2 Streams / 2 Sources / 2
reviewed Visits, all identical before and after).

## Q-1 -- CORRECTED and field-verified

§Q-1 named the fix correctly ("adding `tzdata` alone is insufficient ... it
needs a Windows-registry -> IANA mapping"). Both halves were required, and both
were genuinely broken:

1. no Windows -> IANA name derivation existed anywhere in the product, so the
   resolver always reached its fixed-offset fallback;
2. `tzdata` was not packaged either -- `astral`/`tzlocal` declare it
   conditionally for Windows, but the Windows installer resolves environment
   markers against the *Linux build host* while only wheel tags honor
   `--platform win_amd64`, so both conditions evaluated False.

`tzlocal` (CLDR `windowsZones`) is now resolution step 3, after `TZ` and
`/etc/localtime` and before the unchanged fixed-offset fallback; `tzdata` is
packaged explicitly. Measured in the deployed packaged runtime on the real
Host, against this report's own reproduction:

| Instant | `d5dd1d9` (§Q-1) | `15691d9` |
| --- | --- | --- |
| 2026-12-15 16:00 UTC | 12:00 "Eastern Daylight Time-0400" -- **wrong** | **11:00 EST-0500** |
| 2026-07-15 16:00 UTC | 12:00 EDT-0400 | 12:00 EDT-0400 |
| resolved IANA key | `None` | `America/New_York` |
| `tzdata` | NOT present | present |

Both DST transitions are also correct on both sides (2026-03-08
06:59:59Z -> 01:59:59 EST and 07:00:00Z -> 03:00:00 EDT; 2026-11-01
05:59:59Z -> 01:59:59 EDT and 06:00:00Z -> 01:00:00 EST). Doctor's Clock check,
read live over HTTP, now reports `Host local timezone resolved to
America/New_York` where it previously could only report the fallback. Real
field observations render in correct local time with descending order preserved,
and **no stored timestamp was rewritten** -- the fix is entirely at read time,
and §N's finding that the API boundary was already unambiguous UTC still holds.

## Q-3 -- CORRECTED and field-verified

§I's diagnosis was exactly right: `CameraNodeRecoverySupervisor` reads an
**in-memory** session status, which a Host restart destroys. The resume
mechanism was never missing -- the product simply had no durable record of
whether observation was *supposed* to be happening, so it could not tell "the
Host restarted" from "a person pressed Stop."

`stream_observation_intents` (schema v61) now records that intent at the
product action and deliberately **not** at any runtime teardown, which is what
makes a crash and a clean restart one mechanism rather than two.

Repeating §I's scenario on the corrected build, and then the cases §Q-3 could
not previously reach:

| Scenario | Result |
| --- | --- |
| Observing, graceful Host restart, **no manual action** | shutdown 14:49:49 -> relaunch 14:50:01 -> **resumed automatically 14:50:12.9** (~12 s); fresh frames confirmed 14:55:55 (598 track updates, 3 candidates in the resumed session) |
| Duplicate state after resume | none: Streams 2, Sources 2, reviewed Visits 2, intent rows 1 -- identical to entry |
| Deliberately stopped, then Host restarted | **stayed stopped** across 20 consecutive polls over ~6 minutes; the Node was never even probed |
| Host starts while the Camera Node is **unavailable** | honest `stopped` for 10 polls while unreachable; Node returned 15:08:09 -> **resumed automatically 15:08:38.5** (~29 s), no manual action |
| **Abrupt kill** (`Stop-Process -Force`, no graceful shutdown) | intent `updated_at` unchanged (the dying process wrote nothing) -> relaunch 15:10:36 -> **resumed automatically 15:10:41** |

Across all four restarts on the real field database: `PRAGMA quick_check` **ok**,
0 duplicate Visit ids, Reviewed truth unchanged (2 Visits / 2 labels), no
Inferred -> Reviewed promotion, no media loss (343 -> 359 assets, growth only
from real new observation), `[PASS] media_integrity`, and no phantom-online
state.

## What this addendum does and does not change

- **§Q-1 and §Q-3 are closed.** Their "Not fixed here, deliberately" paragraphs
  describe this report's own correct scope decision at the time, not the
  current product.
- **§Q-2 and §Q-4 stand unchanged and unfixed**, as the correction milestone's
  brief directed; neither proved to be a dependency of either fix. Q-2 was
  observed again live (`self_test: degraded` on a Node whose camera then worked)
  and remains invisible in the product and pessimistic in direction.
- **§U's "no remaining v0.1 field blockers" verdict is unchanged**, and the two
  items it placed before the owner as decisions have now been decided and
  implemented.
- **§C, §F-§P's evidence is not re-litigated.** Only the two corrected
  behaviours were re-run.
- **This addendum does not accept Field Validation Closure v1.** It records the
  corrected evidence so that decision can be made.

## Acceptance-closure pass (2026-09-25)

Added when the correction milestone completed its remaining acceptance work. The
corrected build's full Core gate and two dispositions now exist, so the
acceptance decision has everything it needs.

- **Full Core gate on the corrected build:** `11 failed, 6205 passed, 4 skipped,
  35 deselected, 11 xfailed` (0:41:00). **Zero failures attributable to the
  corrections.** All eleven reproduce deterministically in isolation *and* fail
  identically at the pre-correction baseline `8a45d1a` -- i.e. at this report's
  own successor commit, before either fix. Four are the established recorded
  pre-existing set; the other seven were bisected to `3d78f8a` (Review Queue
  Scale Closure v1, 2026-09-23), two milestones earlier. Full classification:
  [native-windows-field-reliability-corrections-v1-report.md](native-windows-field-reliability-corrections-v1-report.md)
  §M.
- **§Q-2 and §Q-4 remain open and unfixed**, unchanged from the addendum above,
  and neither is a v0.1 blocker.
- **The stale `camera_connected` field** observed during the corrections' own
  field run was traced end to end and dispositioned as a **nonblocking deferred
  field-quality issue, not fixed**. It *is* user-facing (Stream detail and the
  onboarding wizard render "Camera Healthy" from it), but it is a bounded 300 s
  heartbeat freshness window with an honest post-threshold message and existing
  regression tests on both sides, and the field observation fell inside that
  window (~186 s). No recovery, resume or control path reads the field. Changing
  it would reverse an accepted product decision encoded in a passing test, which
  is a product change rather than a narrow repair. Reasoning in full:
  corrections report §O.
- **One new finding, which is NOT this report's and NOT the corrections'.**
  `dashboard_summary`'s Today counts collapse toward `0` for reviewed/confirmed
  Visits, because a review-queue bulk preload sharing the same read cache answers
  Today's motion-evidence lookups with an authoritative `None`. Introduced by
  `3d78f8a`, already present at `8a45d1a`, and therefore **present in the build
  this report validated** -- §U's "no remaining v0.1 field blockers" verdict was
  reached without knowledge of it. It is a user-facing truth regression on the
  landing page and is recorded as a **release-blocker candidate for the owner's
  decision** (corrections report §O). It was not fixed: it belongs to a
  different milestone's change.

**This pass still does not accept Field Validation Closure v1.** It completes the
evidence and states the open decisions; global acceptance remains the
owner's/ChatGPT's call.
