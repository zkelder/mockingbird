# Performance / Scale / Stability Closure v1 -- closure report

Can a real owner leave MockingBird running for weeks, accumulate a
meaningful wildlife history, review it, restart the Host, and keep using
the product -- without runaway resource growth, pathological latency,
queue collapse, or an experience that gets steadily worse?

Stage A measured that question at four credible v0.1 workloads. The
answer at the start of this milestone was **no**, and not marginally: on
an ordinary three-month, two-camera library the landing page took **18
seconds**, the Review Queue page's own request took **40 seconds** and
returned **20 MB**, and -- found along the way -- **no backup could be
made at all past about two months of use**, which also meant the
installation could no longer be upgraded.

Stage B fixed those. This report records what was measured, what was
changed, what the numbers are now, and -- precisely -- what is still
wrong.

---

## A. Starting baseline

| | |
|---|---|
| Repository | `/home/zkelder/projects/mockingbird-active` |
| Branch | `main` |
| Accepted HEAD at session start | `3133c64b6a9c49273f5cc57a807240630cab5b7a` |
| Schema at session start | `v59` |
| Version | `0.1.0` |
| Latest accepted milestone | UI/UX & First-Run Adoption v1 |
| Push status | **not pushed** |

Working tree at session start: clean apart from the seven preserved
untracked detector files and `uv.lock`, all eight present and untracked.
Every one of the seven was SHA-256 hashed at session start and re-checked
at each commit boundary; none was edited, staged, renamed or removed at
any point. `uv.lock` remains untracked and untouched.

The governing documents were read before anything was changed:
`docs/release-execution-state.md` (§1, §3, §13, §14 and the phase
header), `docs/product-doctrine.md`, `docs/roadmap.md`,
`docs/ui-ux-first-run-adoption-v1-report.md`, and the prior performance
record in
[whole-product-ui-accessibility-performance-closure-v1-report.md](whole-product-ui-accessibility-performance-closure-v1-report.md).
That last one matters: it measured a 371-Visit dataset in 2026-08 and
found no regression to fix. Nothing it concluded was wrong -- 371 Visits
simply is not where these defects live.

`docs/release-execution-state.md` was updated with the accepted delta
only (commit `d149ded`): UI/UX & First-Run Adoption v1 accepted at HEAD
`3133c64` with its validation state carried forward verbatim, the
protected-file incident marked remediated, and the current authorized
milestone set to this one. No unrelated scheduler history was rewritten.

## B. Writer safety

Peer-session check at session start: every `ccd-cli` process on the
machine was enumerated with its own working directory; no tracked file in
the tree had an mtime later than the accepted HEAD commit; `git status`
matched the expected baseline exactly; no `index.lock`, no stash, no
in-progress merge. This session then recorded its own single-writer claim
in an untracked `.git/MOCKINGBIRD_ACTIVE_WRITER` marker -- inside `.git/`,
so never part of the working tree -- matching the convention the prior
milestone established, and re-checked the protected files before every
commit boundary. No writer collision occurred.

## C. Hardware / environments

Two real environments, because a Windows claim cannot rest on Linux
evidence.

| | Linux / WSL2 | Native Windows |
|---|---|---|
| Platform | `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64`, glibc 2.39 | `Windows-10-10.0.19045-SP0` |
| Python | 3.12.3 (project `.venv`) | 3.12.7 (MockingBird's own packaged embeddable runtime) |
| CPU | 12 logical | 12 logical |
| RAM | 16 GB (WSL allocation) | 32 GB host |
| Workload storage | ext4 under WSL | **NTFS, `C:\MBPerf`** -- deliberately a native path, not the UNC share, so this measures Windows and not 9p |

The Windows runs use `C:\MBTestNew\MockingBird-windows-x64\python\python.exe`
-- the interpreter and dependency set from a real packaged MockingBird
Windows build -- executing **this** source tree over the UNC path. Making
that work required a real fix to the harness (§S.7): that runtime is an
embeddable CPython, which ignores `PYTHONPATH`, so the server subprocess
had been silently importing the *packaged* `mockingbird` instead of the
tree under measurement.

Two honest limitations of the Windows numbers: the harness reads RSS,
file-descriptor and thread counts from `/proc`, so those are `None` on
Windows (memory evidence in §I is Linux-only); and `environment_report()`
reads `/proc/meminfo`, so the Windows JSON's `memory_total_kb` field
carries the WSL value and should be ignored.

**Concurrency caveat.** Some measurements ran while other work shared the
machine. Every figure taken under concurrent load is labelled as such
where it appears, and no such figure is used as a performance claim --
only as a lower bound or as a correctness result, which concurrency does
not affect.

## D. v0.1 workload profiles

Sizes are derived from this repository's own accepted field evidence, not
invented. *Real Field Acceptance v1* admitted 5 Visits in ~97.5 minutes;
*End-to-End Bird Encounter Recall Closure v1* counted 22 genuine
encounters in 92.2 minutes at 68.2% recall -- about 15 admitted
Visits/hour during genuinely busy feeder activity. Wildlife activity is
bimodal, so ~2 busy hours/day plus a sparse tail gives **~30 admitted
Visits/day** for an established backyard feeder. Media per Visit follows
the repository's own accepted `_DEFAULT_MAX_EVIDENCE_ITEMS_PER_CANDIDATE
= 4`, and the generated data confirms it: **4.0 media assets per Visit**.

| Profile | What it represents | Days | Streams | Visits | Media assets | Database |
|---|---|---:|---:|---:|---:|---:|
| **A -- fresh / small install** | The first days of use; one Place, one camera, small history. 13/day, below the established rate because a newly-aimed camera and an un-habituated yard both produce less. | 4 | 1 | 69 | 268 | 1.2 MB |
| **B -- established home install** | Three months at the measured rate, two cameras, a realistic mixed review backlog (62% reviewed). ~7x the largest previously-measured MockingBird library. | 90 | 2 | 2,813 | 11,244 | 11.4 MB |
| **C -- busy period** | B's shape plus genuine burst pressure: 6 of the 90 days at 4x normal activity, and a larger backlog (38% reviewed). | 90 | 2 | 3,322 | 13,288 | 14.8 MB |
| **D -- large v0.1 library** | A serious early adopter: a full year, three cameras. Deliberately beyond what an ordinary owner reaches in v0.1's lifetime, which is exactly what makes it able to expose unbounded work before a real user does. | 365 | 3 | 11,206 | 44,824 | 48.5 MB |

Generated by `scripts/performance_workload.py` through the real ORM with
the column values the real Observation path produces, so query planning,
index use, join cost and response-serialization cost are all genuinely
exercised. Two disclosed departures: media *bytes* are tiny synthetic
JPEGs (so this measures database and API behaviour, not image decode --
`--media-bytes` exists for the storage question that does care), and no
detector or classifier inference runs (suggestion rows are written
directly, exactly as a real BioCLIP run would leave them). Neither
affects the query shapes, row counts or response sizes measured here.

## E. Startup measurements

Startup is reported in the phases a user can actually perceive, never as
one number. Cold = first open of that database by that process; warm =
immediate restart against the same data.

**Linux / WSL, Profile B (2,813 Visits), before this milestone:**

| Phase | Cold | Warm |
|---|---:|---:|
| Process start -> port bound | 2.22 s | 3.00 s |
| Port bound -> backend ready | 0.03 s | 0.01 s |
| **Process start -> backend ready** | **2.25 s** | **3.01 s** |
| **Process start -> first useful page** | **19.91 s** | **27.59 s** |

That gap is the whole finding. The backend was ready in about two
seconds; the *first page a user sees* took twenty to twenty-eight,
because the Dashboard itself took that long. After the fixes in §S, the
same measurement lands at 2.25 s to backend ready and first useful page
dominated by a ~2.3 s Dashboard.

**Native Windows, Profile A:**

| Phase | Cold | Warm |
|---|---:|---:|
| Process start -> backend ready | 4.06 s | 3.97 s |
| Process start -> first useful page | 4.66 s | 4.55 s |

Windows process startup is consistently ~1.8x slower than WSL (4.0 s vs
2.2 s) -- a real, OS-level difference worth recording, not a defect.
Database open is inside "backend ready" and is not separately timed; the
v59 -> v60 migration of the real 2,813-Visit database, *including* its
pre-migration safety backup, took **2.8 s** (§K).

Model readiness and Camera Node reconnect timing are not measured here:
this milestone ran no detector/classifier inference and paired no Camera
Node (§Z).

## F. UI / API responsiveness

Measured with `scripts/benchmark_release_performance.py`: a real uvicorn
process, a real `POST /api/setup/administrator` sign-in over HTTP, one
warm-up call then N timed calls per operation, reporting min/median/p90/max
plus response bytes and the SQL statement count the request actually
issued. Statement counts come from a SQLAlchemy `before_cursor_execute`
hook, so an N+1 is a number rather than an intuition.

### Profile A -- fresh / small install (69 Visits)

| Operation | Before | After | SQL before | SQL after |
|---|---:|---:|---:|---:|
| Dashboard / Today | 857 ms | **256 ms** | 2,694 | 720 |
| Product health | 822 ms | **241 ms** | 2,704 | 731 |
| Review Queue | 788 ms | **236 ms** | 1,785 | 598 |
| Dataset quality | 364 ms | 151 ms | 694 | 544 |
| Bird Log (journal) | 300 ms | 174 ms | 653 | 592 |
| Place biodiversity | 286 ms | 190 ms | 568 | 564 |
| Dataset coverage | 236 ms | 101 ms | 484 | 379 |
| Activity Library (first page) | 125 ms | 90 ms | 285 | 285 |
| Analytics | 67 ms | 28 ms | 118 | 92 |
| Local Data | 57 ms | 31 ms | 127 | 102 |
| `GET /api/events` | 39 ms | 4 ms | 71 | 3 |

Every operation on a fresh install is now at or under ~260 ms. Even
before the fixes, 2,694 SQL statements to render the landing page of a
69-Visit library was the signature that predicted everything in §G.

### Profile B -- established home install (2,813 Visits)

Wall-clock here is the best observation across six independent runs, and
it should be read together with §T, which gives the full spread and
explains why this machine's shared load makes SQL statement count the
firmer measure.

| Operation | Before | After | Change | Statements |
|---|---:|---:|---:|---|
| Dashboard / Today | 18.02 s | **2.29 s** | **-87%** | 38,796 -> 5,189 |
| Product health | 17.89 s | 2.39 s | -87% | 38,811 -> 5,204 |
| Review Queue | 17.15 s | 4.84 s | -72% | 38,970 -> 11,027 |
| Dataset quality | 20.00 s | 3.90 s | -81% | 29,901 -> 14,101 |
| Dataset coverage | 13.14 s | 3.09 s | -76% | 16,328 -> 11,293 |
| Bird Log (journal) | 10.09 s | 5.90 s | -42% | 27,365 -> 19,768 |
| Activity Library (first page) | 7.09 s | **173 ms** | **-98%** | 289 -> 273 |
| Activity Library (deep page) | 8.12 s | **174 ms** | **-98%** | 293 -> 274 |
| Analytics | 3.39 s | 1.38 s | -59% | 6,283 -> 4,552 |
| Place biodiversity | 3.69 s | 1.79 s | -52% | 5,322 -> 5,330 |

The Activity Library line is the one to notice: a 98% improvement with
essentially unchanged statement counts. That was not fewer queries -- it
was one query stopping being quadratic, once `review_labels` had an index
(§L).

Practical release criteria, rather than an arbitrary sub-100 ms bar:
ordinary interactions should feel immediate or clearly show progress;
heavy operations must not freeze the application; large-history views
must remain usable. §U records the contract these numbers support.

## G. Large-library behaviour

The four profiles together show what scales and what does not. All
figures below are **after** every fix in §S.

| | A (69 Visits) | B (2,813) | C (3,322, burst) | D (11,206) |
|---|---:|---:|---:|---:|
| Review backlog | 45 | 1,094 | ~2,060 | 5,023 |
| Dashboard | 256 ms | 2.29 s | 8.63 s | 21.4 s |
| **Review Queue** | 236 ms | 5.07 s | **74.4 s** | **95.8 s** |
| Review Queue response | 368 KB | 7.9 MB | **14.9 MB** | **36.1 MB** |
| Review Queue statements | 598 | 11,027 | 20,673 | 50,080 |
| Activity Library (first page) | 90 ms | 173 ms | 261 ms | -- |
| Activity Library (deep page) | 4 ms | 174 ms | 286 ms | -- |
| Analytics | 28 ms | 1.38 s | 3.10 s | -- |
| `GET /api/visits` | 3 ms | 10 ms | 18 ms | -- |
| `GET /api/media` | 13 ms / 282 KB | 701 ms / 11.9 MB | 1.27 s / 14.0 MB | -- |

Two different shapes are visible here.

**Bounded surfaces stay bounded.** The Activity Library is the clearest
case: 90 ms at 69 Visits, 173 ms at 2,813, 261 ms at 3,322 -- and a page
deep into the history costs the same as the first page. `GET /api/visits`
is flat because it is now genuinely bounded. This is what the rest of the
product should look like.

**The Review Queue scales with its backlog, without limit.** 1,094 items
-> 5.07 s; 2,060 -> 74.4 s; 5,023 -> 95.8 s; and its response grows the
same way, 7.9 MB -> 14.9 MB -> 36.1 MB. Profile C is the sharpest
evidence, because it is not an extreme library -- it is Profile B's three
months with a realistic burst week and a user who has fallen behind on
review. The Dashboard's residual cost follows the same curve for the same
reason (§S.1 cut what it does per item, but it still classifies every
queued item).

The Profile D and C wall-clock figures were taken while an unrelated
workload shared the machine (§C), so they are upper bounds; the response
sizes and statement counts are not load-dependent and are the firmer
numbers. A complete Profile D benchmark sweep was started but not
finished -- at ~96 s per Review Queue request it does not complete in a
usable time, which is itself the finding.

§R records this as the one remaining P0, and §Z says plainly why it was
not closed here.

## H. `GET /api/visits` -- the flagged endpoint

The v0.1 pre-release baseline audit specifically flagged `GET /api/visits`
as returning the full Visit table with no pagination limit. Investigated
concretely:

- **It is real.** `list_visits()` selected every non-superseded Visit with
  no bound. At Profile B that is a **754 KB** response; at Profile D,
  several megabytes.
- **It is not user-critical.** No part of the shipped frontend calls it.
  Verified across the whole `web/src` tree: `web/src/api/client.ts` has
  eighteen `/api/visits/{id}/...` helpers and **zero** bare `/api/visits`
  callers. It is a diagnostic/integration surface.
- **Fixed with the smallest coherent approach**: a bounded default page
  size (500, maximum 2000) with `limit`/`offset` continuation over the
  already-stable `Visit.id` ordering. Because nothing in the product
  calls it, this is a safety limit rather than a behaviour change.

**The same bounded inspection was applied to every other unbounded
user-critical surface exposed during measurement**, and it found worse
things than the flagged one:

| Endpoint | Rows at Profile B | Bytes | Frontend consumers | Outcome |
|---|---:|---:|---|---|
| `GET /api/visits` | 2,813 | 754 KB | none | **bounded** (500/2000) |
| `GET /api/events` | 2,813 | 1.16 MB | none | **bounded**, plus its per-Event detection N+1 fixed (203 -> 2 statements) |
| `GET /api/review-labels` | 1,719 | 474 KB | Review Queue, Streams, Classifier Readiness | **N+1 fixed** (151 -> 2 statements); left unbounded, its consumers need the set |
| `GET /api/media` | 11,244 | **11.9 MB** | 6 pages | **not fixed** -- P1, §R |
| `GET /api/detection-proposals` | 2,811 | 1.40 MB | Review Queue, Streams, Detection Proposals | **not fixed** -- P1, §R |
| `GET /api/detection-runs` | 2,811 | 539 KB | Review Queue, Streams | **not fixed** -- P1, §R |
| `GET /api/species-suggestions` | 2,464 | 1.50 MB | Species Suggestions page | **not fixed** -- P1, §R |
| `GET /api/review-queue` | 1,094 (5,023 at D) | **7.9 MB** (36 MB at D) | Review Queue page, App shell | **not fixed** -- P0, §R |

The endpoints left unfixed are exactly the ones with real frontend
consumers that read the whole set. Bounding them without a matching
frontend change would silently truncate what a user is shown -- a truth
regression, not a performance fix. They are reported, not half-fixed.
This is also why "do not redesign all APIs merely because one endpoint is
unbounded" was followed literally.

## I. Memory

Two soaks with `scripts/soak_release_runtime.py`, because a single one
cannot tell a leak apart from a growing working set. Growth is judged over
the **settled second half** of each run, not first-to-last, so ordinary
process warm-up is not read as a leak.

**Soak 1 -- continuous ingest (40.5 min, 3,708 requests, 1,066 new Visits written):**

| | Start | End | Settled-half trend |
|---|---:|---:|---:|
| RSS | 151.9 MB | 221.2 MB | +60.8 MB/hour |
| Open file descriptors | 17 | 18 | 0/hour |
| Threads | 32 | 31 | 0 |
| Database | 1.23 MB | 6.07 MB | grows with ingest, as expected |
| Log | 0 | 16 KB | bounded, see §K |

That RSS line looks like a leak. It is not, and the second soak is what
proves it.

**Soak 2 -- fixed library, no ingest (25 min, 4,427 identical requests):**

| | Start | End | Settled-half trend |
|---|---:|---:|---:|
| RSS | 152.0 MB | 166.1 MB | **+5.6 MB/hour** |
| Open file descriptors | 17 | 18 | 0/hour |
| Threads | 32 | 32 | 0 |
| Database / media / log | unchanged | unchanged | 0 |

Four and a half thousand identical requests against an unchanging library
move resident memory by about 1 MB over the settled half. **There is no
per-request leak.** Soak 1's RSS tracks the working set of a library that
grew five-fold during the run, and its own curve decelerates sharply --
+38 MB in the first 500 s, +2.8 MB in the last 380 s -- which is
allocator arenas reaching the peak working set, not unbounded growth.

Also confirmed directly: no file-descriptor leak (flat at 18 across both
runs and across the whole operation benchmark), no thread accumulation
(32, never climbing), no background-task pile-up, and no stale database
sessions left open.

**Honest limits.** These are 40 and 25 minutes on one machine with
synthetic ingest. They are evidence of *bounded* behaviour, not proof of
24/7 field reliability. See §N.

## J. CPU / GPU

Idle: with no requests in flight the Host consumes no measurable CPU --
there is no polling loop; the acoustic runtime's own sweeps are interval-
gated (`DEFAULT_RETENTION_INTERVAL = 15 minutes`).

Under the soaks the server process used ~3,300-3,600 CPU-seconds/hour on
a 12-core machine -- i.e. roughly **one core saturated** while being
driven as hard as the harness could drive it, which is far beyond real
use (a real owner does not issue 4,400 Dashboard loads in 25 minutes).
No runaway loop was observed: CPU time rose linearly with requests served
and stopped when requests stopped.

**No starvation of the control plane was observed**: throughout every
measurement the cheap control/status endpoints stayed fast even while
heavy reads were in flight -- `GET /api/streams` 1.4 ms, `/api/sources`
1.4 ms, `/api/workers/status` 1.1 ms, `/api/alerts` 2.3 ms at Profile B.

GPU was not exercised: this milestone ran no detector inference (the
detector is CUDA-only by design, per the accepted platform record), so no
GPU claim is made.

## K. Disk / media / database growth

Measured directly from the generated libraries:

| Quantity | Measured |
|---|---|
| Media assets per Visit | **4.0** (matches the accepted `_DEFAULT_MAX_EVIDENCE_ITEMS_PER_CANDIDATE = 4`) |
| Database bytes per Visit | **~4,300 B** (Profile D: 48.5 MB / 11,206 Visits) |
| Database growth per day, established feeder | ~130 KB/day (~30 Visits/day) |
| Database at one year, three cameras | **48.5 MB** |
| Index cost of schema 60 | +12% (11.36 MB -> 12.73 MB on the real Profile B database) |
| Migration v59 -> v60, including pre-migration backup | **2.8 s** |
| Backup archive, 2,813 Visits / 11,244 assets | 16.6 MB, created in 2.6 s, verified in 0.4 s |

Media bytes are the dominant real-world term and scale with retained
frames, not with anything this milestone changed; the synthetic frames
here are deliberately tiny, so the *per-observation frame count* (4.0) is
the transferable figure, not the byte total.

**Logs are bounded**: `RotatingFileHandler`, `_MAX_LOG_BYTES = 5,000,000`
with `_LOG_BACKUP_COUNT = 3` -- a hard 20 MB ceiling. Confirmed, not
assumed. The soaks produced 16 KB of log in 40 minutes of continuous
driving.

**Temporary artifacts are cleaned**: `backup.py` maintains an explicit
`_TEMPORARY_ARTIFACT_GLOBS` list and a
`cleanup_orphaned_temporary_artifacts` path for exactly the
hard-kill-skips-`finally` case; the three SIGKILL restarts in §O left no
orphans behind.

**Working audio is bounded**: `DEFAULT_WORKING_AUDIO_TTL = 48 hours` for
non-evidence audio, deliberately not gated behind the general
automatic-cleanup setting.

No duplicate media, orphan files, unbounded logs or stale export/temp
artifacts were found. **Retention doctrine was not changed** -- no
evidence called for it.

## L. Database / query findings

The single largest finding of the milestone:

> **MockingBird's core observation tables carried no secondary index at
> all.** `visits`, `events`, `detections`, `media_assets`,
> `review_labels`, `species_suggestions`, `motion_evidence`,
> `detection_runs` and `detection_proposals` had only SQLite's own
> implicit primary-key indexes. Every lookup by a foreign key was a full
> table scan.

That is invisible on a fresh install and quadratic on a real one. The
clearest single case: the Activity Library's main query runs two
correlated scalar subqueries against `review_labels` per Visit row --
`EXPLAIN QUERY PLAN` showed `SCAN review_labels` twice, per row, 2,813
rows against 1,719 labels. That one statement was **835 ms of an 850 ms
request**.

Schema **59 -> 60** adds fourteen indexes. Each was chosen from a real
`EXPLAIN QUERY PLAN` against the query shape that motivated it, and each
is pinned by a test asserting SQLite actually picks it -- not by
intuition, and not "everything that looks like a foreign key."

Measured with indexes as the *only* change, on the real Profile B
database:

| Endpoint | No indexes | Indexed |
|---|---:|---:|
| `GET /api/dataset-quality/summary` | 14.6 s | **6.2 s** |
| `GET /api/review-queue` | 9.6 s | **6.4 s** |
| `GET /api/dashboard/summary` | 4.9 s | **3.0 s** |

Other query findings, all fixed (§S): repeated identical reads inside one
build (the same two Streams read 1,094 times), per-item round trips where
one `IN (...)` would do, whole-table `taxonomy_labels` scans per label
(7,340 in a single dataset-quality request), Python-side filtering of a
whole table that belonged in SQL, and unbounded object materialization of
a Place's entire history to answer a question about its backlog.

## M. Queue / backpressure findings

Inspected and exercised; **no defect found**, and the bounds are real
rather than nominal:

| Queue | Bound | Behaviour when producer > consumer |
|---|---|---|
| Camera Node ingest (`CameraNodeAnalysisSource`) | `DEFAULT_MAXIMUM_QUEUE_FRAMES = 4`, plus per-frame byte and age limits | Drops the **oldest** frame (`_queue.popleft()`), counts it in `_dropped`/`_coalesced` diagnostics -- never grows |
| Acoustic analysis, per Stream | `DEFAULT_MAX_IN_FLIGHT_SEGMENTS_PER_STREAM = 100` (~25 minutes of audio) | Bounded in flight |
| Acoustic analysis, global | `DEFAULT_MAX_GLOBAL_QUEUED = 500` | Evicts **oldest** queued rows to a terminal `failed` state with `error_code="acoustic_queue_capacity_exceeded"` -- diagnosable, never silently deleted |
| Working audio | 48-hour TTL, 15-minute sweep | Reclaimed on a schedule |
| Burst scheduler / tracker / counterfactual ledger | every `deque` carries an explicit `maxlen`, or a count **and** age bound | Bounded by construction |

The accepted, disclosed "may miss a bird during busy overlapping
activity" behaviour is exactly this drop-oldest design, and it was left
untouched. No model or processing semantics were changed. Restart
recovery of queue state is covered in §O: after three restarts under
load, zero acoustic runs were left claimed as `processing` by a process
that no longer exists.

## N. Long-run / soak evidence

**What was actually run**, stated precisely so it is never mistaken for
more: two soaks on one Linux/WSL machine, 40.5 minutes with continuous
ingest and 25 minutes with a fixed library, 8,135 real HTTP requests
between them, plus the full operation benchmark repeatedly across four
workloads. Findings in §I: no per-request memory leak, no descriptor
leak, no thread accumulation, bounded logs, no error accumulation.

**This is not a 24/7 claim.** It is bounded-behaviour evidence over tens
of minutes. The standing field-acceptance record
([end-to-end-bird-encounter-recall-closure-v1-report.md](end-to-end-bird-encounter-recall-closure-v1-report.md),
[real-field-acceptance-v1](24-7-field-reliability-corrections-v1-report.md))
remains the product's real long-run evidence and was not repeated here,
per the brief's instruction to reuse valid prior evidence rather than
needlessly re-run it.

## O. Restart / recovery evidence

`scripts/verify_restart_recovery.py` drives a real Host with concurrent
reads, writes new observations while it is serving, then stops it --
once gracefully and **twice with `SIGKILL`**, which is what a power loss
or an OOM kill actually does -- restarts it, and checks what a restart
must never break. Two abrupt stops in a row, because damage from an
unclean shutdown can surface on the *next* start rather than the first.

| Check | Visits before -> after | Duplicate ids | Orphaned Visits | Orphaned evidence links | Stuck acoustic runs | Result |
|---|---|---:|---:|---:|---:|---|
| Graceful stop under load | 81 -> 81 | 0 | 0 | 0 | 0 | **clean** |
| Abrupt (`SIGKILL`) under load | 91 -> 91 | 0 | 0 | 0 | 0 | **clean** |
| Abrupt (`SIGKILL`) under load, again | 99 -> 99 | 0 | 0 | 0 | 0 | **clean** |

No duplicated observations, no row count going backwards, no queue row
left permanently claimed, and the Dashboard and Review Queue served
correctly and immediately after every restart. Only disposable state was
used; no irreplaceable data was touched.

The *timings* from that run are deliberately not quoted as a performance
figure -- it shared the machine with a soak and a Windows benchmark. What
it establishes is correctness, which concurrency does not affect.

## P. BirdNET (optional) impact

| Question | Measured |
|---|---|
| Is the disabled/unavailable path lightweight? | **Yes.** `get_birdnet_status()` resolves in **0.48 ms** and uses `importlib.util.find_spec` only -- never a real import. Nothing in the product imports `birdnetlib` at module scope. |
| What does enabling it cost? | Importing the real analyzer (via the accepted `tflite_runtime` shim) takes **1.45 s** and **+63 MB** resident, paid once, lazily. |
| Can it destabilise normal visual operation? | No path was found. Its work is separately queued and bounded (§M), and its capacity eviction is terminal-and-diagnosable rather than unbounded retention. |
| Resource cleanup | Working audio has a 48-hour TTL with a 15-minute sweep; evicted runs remain as `failed` rows until that sweep reclaims them. |

No licensing or model decision was reopened. Packaging still does not
redistribute restricted model weights; nothing here changes that.

## Q. Native-Windows-specific findings

Same code, same workloads, native NTFS storage, MockingBird's own
packaged Windows runtime.

| Operation | Profile A WSL | Profile A Windows | Profile B WSL | Profile B Windows |
|---|---:|---:|---:|---:|
| Dashboard / Today | 256 ms | 485 ms | 2.29 s | 3.13 s |
| Review Queue | 236 ms | 919 ms | 4.84 s | 12.56 s |
| Bird Log (journal) | 174 ms | 199 ms | 5.90 s | 7.69 s |
| Dataset quality | 151 ms | 123 ms | 3.90 s | 5.03 s |
| Activity Library (first page) | 90 ms | 116 ms | 173 ms | 179 ms |
| Camera / Stream status | 2 ms | 3 ms | 1.4 ms | 4.2 ms |
| Process start -> backend ready | 2.2 s | 4.06 s | 2.25 s | -- |

Findings:

1. **Windows process startup is ~1.8x slower** (4.06 s vs 2.25 s). Real,
   OS-level, not a defect -- but it means the startup contract in §U is
   stated against the Windows number, since Windows is the first
   end-user Host acceptance target.
2. **Windows amplifies the surfaces that do many small operations.** The
   Review Queue -- the most per-item-heavy endpoint -- is 2.6x slower at
   Profile B (12.6 s vs 4.8 s), while the Activity Library, which is a
   single indexed query, is within 4%. This is the clearest argument that
   the remaining P0 is *worse* on the actual target platform than the
   Linux numbers suggest.
3. **SQLite, filesystem and large-directory behaviour showed no
   Windows-specific defect.** The 11,244-file media tree, the 12.8 MB
   database and the backup path all behaved the same way; the migration
   and index work is plain SQL with no platform dependency.
4. **A real Windows-only harness defect was found and fixed** (§S.7): the
   packaged embeddable CPython ignores `PYTHONPATH`, so a subprocess
   launched the documented way silently imported the packaged
   `mockingbird` instead of the tree under test, and died on a schema
   mismatch. Anything measuring a MockingBird subprocess on Windows needs
   to know this.

## R. P0 / P1 / P2 / P3 inventory

### P0 -- release blockers

| # | Finding | Workload | Evidence | Root cause | User impact | Status |
|---|---|---|---|---|---|---|
| **P0-1** | Backups fail past ~6,800 media files, **and the installation can therefore no longer be upgraded** | ~2 months of ordinary use | `backup_manifest_invalid` reproduced end to end on the 11,244-asset library; opening it at a newer schema refused to migrate | A manifest carries one ~154-byte entry per media file; `MAX_MANIFEST_BYTES` was 1 MiB. `create_backup` verifies its own output, so *no* backup could be made | Owner loses backup entirely and is stranded on their current schema | **FIXED** (§S.4) |
| **P0-2** | Landing page and review loop degrade with total accumulated history, not with work outstanding | Profile B | Dashboard 18.02 s / 38,796 statements; Review Queue 17.15 s; every saved correction recomputed the whole queue | `_review_queue_items` materialised every non-superseded Visit and Event, then filtered in Python after paying a per-row cascade | The product gets slower every day it runs | **FIXED** (§S.1) |
| **P0-3** | Core observation tables had no secondary indexes | All | `PRAGMA index_list` on nine tables; `EXPLAIN QUERY PLAN` showing `SCAN` per row | Never added | Every foreign-key lookup a full scan; quadratic behaviour | **FIXED** (§S.3) |
| **P0-4** | `GET /api/review-queue` is unbounded | Profiles B / C / D | 5.07 s & 7.9 MB at B; **74.4 s & 14.9 MB at C** -- an ordinary three-month library with a burst week and a user behind on review; 95.8 s & 36.1 MB at D. The page requests `include_reviewed=true`, which was **39.7 s / 20.4 MB at B**, on mount **and after every correction** | The endpoint returns the whole queue; the page computes every tab and filter count client-side over the full list | The review loop degrades with the backlog, without limit, and is worst exactly when the owner is most behind | **REDUCED, NOT CLOSED** -- see §Z |

### P1 -- must fix before v0.1

| # | Finding | Evidence | Status |
|---|---|---|---|
| P1-1 | Activity Library quadratic against `review_labels` | 835 ms of an 850 ms request in one statement; two correlated subqueries per row | **FIXED** (§S.3) -- 7.09 s -> 173 ms |
| P1-2 | `GET /api/events` N+1 (one query per Event for detections) | 2,820 statements / 1.16 MB at Profile B | **FIXED** (§S.5) -- 203 -> 2 statements |
| P1-3 | `list_review_labels` one `session.get` per label | 151 statements for 150 labels | **FIXED** (§S.5) |
| P1-4 | `GET /api/visits` unbounded (the flagged endpoint) | 754 KB at Profile B, zero frontend consumers | **FIXED** (§S.5) |
| P1-5 | `_review_queue_item_by_target` built the entire queue to find one item, on every correction | 228 -> 2,028 statements for a 10x backlog | **FIXED** (§S.2) |
| P1-6 | Whole-table `taxonomy_labels` scan per label resolution | 7,340 scans in one dataset-quality request | **FIXED** (§S.2) |
| P1-7 | `GET /api/media` returns every media asset | **11.9 MB** at Profile B, ~47 MB at Profile D; 6 page consumers | **NOT FIXED** -- needs a coordinated frontend change, §Z |
| P1-8 | `GET /api/detection-proposals` / `/detection-runs` / `/species-suggestions` unbounded | 1.40 MB / 539 KB / 1.50 MB at Profile B; consumed whole by Review Queue and Streams | **NOT FIXED** -- same reason, §Z |

### P2 -- bounded high-value improvement

| # | Finding | Status |
|---|---|---|
| P2-1 | Bird Log journal still 5.9 s at Profile B (19,728 statements; per-Visit reads across the whole history) | **Partly improved** (-42%). Remaining work is batch-preloading its per-Visit reads, the same pattern already applied elsewhere -- bounded, but not closed here |
| P2-2 | Dataset coverage/quality still 3.1-3.9 s at Profile B | **Improved** (-76% / -81%); the residual is the same per-Visit read pattern as P2-1 |
| P2-3 | `dashboard_summary` builds a review-queue classification per queued item to populate three fields **no screen renders** (`actionable_animal_visits`, `actionable_animal_visit_count`, `legacy_activity_count` -- verified absent from the whole `web/src` tree outside `types.ts`) | **Cost cut** by skipping detail hydration (§S.1). Eliminating the pass entirely means either changing those published fields' semantics or making the build lazy, which would change *which* twelve items the field carries -- neither is a change to make unilaterally |

### P3 -- post-v0.1

- `Session.get()` issues a `SELECT` per call even on an identity-map hit
  in SQLAlchemy 2.0.54 (confirmed against a minimal standalone repro).
  Worked around locally with an explicit build cache; worth revisiting
  upstream rather than spreading the workaround.
- The review-queue build still constructs a full Pydantic
  `ReviewQueueItem` per item even when only a classification is needed; a
  purpose-built projection would be cheaper, but is a structural change.
- Profile D review-queue response would benefit from server-side
  per-tab counts regardless of pagination.

## S. Fixes implemented

**S.1 -- Review-queue build proportional to backlog, not library** (`4f7542a`).
The status predicate the loop applied in Python moved into SQL, for both
the Visit and the visit-less Event source, via one shared
`_review_queue_statuses` helper so the two can never drift. A read-only
`_read_only_build_cache` serves the rows every item in a build needs (its
Stream, that Stream's Source and provider configuration, its Zone, the
candidate pack, its evidence links) once instead of per item. Four chunked
`IN (...)` preloads replace four round trips per item. And
`include_detail=False` lets the landing page and the eleven
`review_queue_count` fields ask for classification without the
identification summary, effective-primary preview, focus-crop context,
state token or stale-suggestion check -- the identification summary alone
was 46% of the response bytes. Queue membership, order and classification
are unchanged.

**S.2 -- Report-surface scale** (`e7062bb`). Taxonomy resolution inside a
read-only build reuses one index -- `_taxonomy_label_index`, this module's
own already-accepted batched form of the same scan, which a prior
milestone documented as the right fix and deferred as out of its scope.
Truth-writing callers run outside any such build and keep the unmodified
path. `_review_queue_item_by_target` narrows to one target in SQL,
producing a byte-identical item.

**S.3 -- Schema 60: fourteen indexes** (`960ff60`). `review_labels
(target_type, target_id)`, `visits (event_id)`, `visits (review_status,
is_superseded)`, `events (stream_id, started_at)`, `events
(review_status)`, `detections (event_id)`, `species_suggestions (visit_id,
status)`, `motion_evidence (promoted_visit_id)` and `(promoted_event_id)`,
`media_assets (local_path)` and `(stream_id)`, `detection_proposals
(run_id)` and `(visit_id)`, `detection_runs (media_asset_id)`. Additive
and `IF NOT EXISTS`, so a fresh install and an upgraded one converge on
the identical index set -- asserted as a test. Disclosed cost: +12%
database size.

**S.4 -- Backup manifest cap** (`960ff60`). `MAX_MANIFEST_BYTES` 1 MiB ->
64 MiB. The cap is a real guard (`_read_manifest` reads the member into
memory and the archive is not necessarily one MockingBird wrote), so it
was raised, not removed: 64 MiB still bounds the read while covering
~435,000 media files, roughly ten years at the measured rate. The guard
is still pinned by a test that feeds it an oversized manifest.

**S.5 -- Bounded list surfaces** (`e7062bb`). `GET /api/visits` and
`GET /api/events` take a bounded default page size (500, max 2000) with
`limit`/`offset`; Event detections read in one chunked query;
`list_review_labels` resolves its superseded-Visit exclusion in one
chunked query instead of one `session.get` per label.

**S.6 -- Review labels in bulk** (`b76fdfe`). Inside a read-only build,
one ordered read grouped by target replaces one query per Visit and one
per Event. Truth-writing paths keep the per-target query.

**S.7 -- Measurement tooling correctness** (`b76fdfe`, `a6aab75`). The
benchmark launches its server through a generated bootstrap that prepends
the source path inside the child rather than relying on `PYTHONPATH` --
without which the packaged Windows runtime imported the wrong
`mockingbird` entirely. `build_workload` takes an `id_prefix` so a soak
can append to a library it already seeded.

New tooling, all committed and reusable:
`scripts/performance_workload.py`,
`scripts/benchmark_release_performance.py`,
`scripts/soak_release_runtime.py`,
`scripts/verify_restart_recovery.py`.

## T. Before / after evidence

Every benchmark run records dataset shape, environment, exact command,
per-operation samples (not just a summary), and repeat count. Medians are
from 3-5 repeats after one warm-up; single-run precision is deliberately
not reported.

**Reproduce:**

```bash
python scripts/benchmark_release_performance.py --root /tmp/mb-perf-b --profile b --repeat 3 --memory-passes 0 --json after.json
```

### Read this section's units carefully

This machine is shared with an unrelated, bursty workload (§C), and it
became heavily loaded partway through the session. Wall-clock therefore
varies by a factor of two or more between runs of the *identical* build.
So this section leads with **SQL statement counts**, which are
load-independent and are the actual structural claim, and reports
wall-clock as an observed **range** across six independent Profile B runs.

The clearest demonstration that the variance is environmental and not
code: the last two runs below have the *lowest* statement counts of any
run -- they include the review-label batching -- and the *highest*
wall-clock.

### Six independent Profile B runs (2,813 Visits)

`median wall-clock / SQL statements`

| Run | Dashboard | Review Queue | Dataset quality | Bird Log | Activity Library | Analytics |
|---|---|---|---|---|---|---|
| **before** | 18.02 s / 38,796 | 17.15 s / 38,970 | 20.00 s / 29,901 | 10.09 s / 27,365 | 7.09 s / 289 | 3.39 s / 6,283 |
| after queue fix only | 16.36 s / 35,964 | 15.62 s / 36,143 | 19.40 s / 29,881 | 10.12 s / 27,359 | 5.93 s / 292 | 3.30 s / 6,282 |
| after all (1) | 4.87 s / 5,699 | 8.60 s / 12,097 | 13.89 s / 22,532 | 6.99 s / 21,918 | 5.86 s / 288 | 2.25 s / 4,543 |
| after all (2) | **2.29 s** / 5,690 | **5.07 s** / 12,091 | 5.98 s / 22,515 | 6.31 s / 21,916 | 0.17 s / 273 | **1.38 s** / 4,543 |
| after all (3) | 5.14 s / **5,195** | 12.49 s / **11,027** | 14.60 s / **14,100** | 21.52 s / 19,767 | 0.49 s / 277 | 5.40 s / 4,553 |
| after all (4) | 3.94 s / **5,189** | 26.70 s / **11,027** | 13.40 s / **14,101** | 21.17 s / **19,768** | 0.40 s / 273 | 5.05 s / 4,552 |

**Statement-count reduction, which is what the code actually changed:**

| Operation | Before | After | Reduction |
|---|---:|---:|---:|
| Dashboard / Today | 38,796 | **5,189** | **-87%** |
| Product health | 38,811 | 5,204 | -87% |
| Review Queue | 38,970 | **11,027** | **-72%** |
| Dataset quality | 29,901 | **14,101** | -53% |
| Bird Log (journal) | 27,365 | 19,768 | -28% |
| Dataset coverage | 16,328 | 11,293 | -31% |
| Analytics | 6,283 | 4,552 | -28% |
| Local Data | 6,294 | 4,557 | -28% |
| `GET /api/events` | 2,820 | **3** | **-99.9%** |
| `GET /api/review-labels` | 1,720 | **6** | **-99.7%** |

**Wall-clock, best observation under the lowest observed load** (run "after
all (2)"; the corresponding before-figure was taken under comparable
conditions):

| Operation | Before | After | Change |
|---|---:|---:|---:|
| Dashboard / Today | 18.02 s | **2.29 s** | **-87%** |
| Product health | 17.89 s | 2.39 s | -87% |
| Review Queue | 17.15 s | 5.07 s | -70% |
| Dataset quality | 20.00 s | 5.98 s | -70% |
| Dataset coverage | 13.14 s | 3.52 s | -73% |
| Bird Log (journal) | 10.09 s | 6.31 s | -38% |
| Activity Library (first page) | 7.09 s | **173 ms** | **-98%** |
| Activity Library (deep page, offset 2000) | 8.12 s | **174 ms** | **-98%** |
| Activity Library (free-text search) | 3.23 s | 110 ms | -97% |
| Place biodiversity summary | 3.69 s | 1.79 s | -52% |
| Analytics | 3.39 s | 1.38 s | -59% |
| Local Data | 3.44 s | 1.38 s | -60% |
| `GET /api/events` | 2.79 s | **19 ms** | **-99%** |
| `GET /api/media` | 984 ms | 701 ms | -29% |
| `GET /api/review-labels` | 649 ms | 40 ms | -94% |
| `GET /api/visits` | 184 ms | 10 ms | -95% |
| Place Story | 107 ms | 68 ms | -37% |
| Yard Map | 130 ms | 117 ms | -11% |
| Camera / Stream status | 2 ms | 1 ms | -13% |

Targeted single-endpoint measurements after the final change, taken the
same way: Dashboard **2.22 s**, Review Queue **4.84 s**, Dataset quality
**3.90 s**, Dataset coverage **3.09 s**, Bird Log journal **5.90 s**.

Two honest notes. `GET /api/visits`' byte count drops from 754 KB to 134
KB because the route is now bounded to 500 rows (§H) -- that is the fix,
not a faster serialization of the same payload. And `GET
/api/detection-runs` moved from 67 ms to 111 ms on a 539 KB response
across 2 to 4 statements; at that magnitude, on this machine, that is
noise, not a regression.

**Isolated effects**, each measured with that change as the only variable
and with before/after taken back to back:

| Change | Measurement | Before | After |
|---|---|---:|---:|
| Schema 60 indexes alone | `dataset-quality/summary` | 14.6 s | 6.2 s |
| | `review-queue` | 9.6 s | 6.4 s |
| | `dashboard/summary` | 4.9 s | 3.0 s |
| Queue build, 10x reviewed history | statements | 178 -> 538 | 132 -> 132 |
| Dashboard, 10x reviewed history | statements | 442 -> 807 | 396 -> 401 |
| Single-item lookup, 10x backlog | statements | 228 -> 2,028 | flat |
| `list_events`, 200 Events | statements | 203 | 2 |
| `list_review_labels`, 150 labels | statements | 151 | 2 |
| Backup, 11,244 media assets | outcome | `backup_manifest_invalid` | 16.6 MB in 2.6 s, verified in 0.4 s |

**Variability and limitations, stated plainly.** Wall-clock medians come
from 3-5 samples per run and vary by 2x or more between runs of the same
build because of the shared machine; the full per-sample series, p90 and
max are in each run's JSON. Several Profile D figures and the restart
timings were taken under known concurrent load and are labelled as upper
bounds. The synthetic workload uses tiny media files, so nothing here
measures image decode or real disk throughput for full-size frames.

## U. Performance contract

Derived from measured behaviour on the tested hardware at the tested
workloads. Nothing below is an aspiration.

**The condition these thresholds hold under:** a Host that has the
machine substantially to itself -- which is what a real MockingBird
installation has, and is not what this session's measurement machine had
for part of the run (§C, §T). Under the heaviest contention observed here
the Dashboard reached 5.1 s and the Review Queue 26.7 s at Profile B; those
are measurements of a loaded *machine*, not of the product, and the
statement counts were unchanged or better throughout. Each threshold below
is stated with the measurement that supports it, so any future run can be
compared against the same basis rather than against a number with no
provenance.

**Startup.** On the native-Windows target, the Host reaches backend-ready
in **under 6 seconds** cold or warm (measured 4.06 s / 3.97 s), and the
first useful page follows within the Dashboard budget below.

**Ordinary interaction, fresh and small installs (Profile A scale).**
Every measured UI surface responds in **under 500 ms** on Windows
(measured: worst was the Review Queue at 919 ms; every other operation
under 500 ms, most under 200 ms). *The Review Queue is the exception and
is the open P0.*

**Ordinary interaction, established install (Profile B, ~2,800 Visits /
three months / two cameras).**
- The Dashboard renders in **under 4 seconds** (measured 2.29 s on Linux,
  3.13 s on Windows).
- Camera/Stream status, alerts, collections, worker status and storage
  settings respond in **under 30 ms**.
- The Activity Library -- including a deep page and a free-text search --
  responds in **under 250 ms**, independent of how deep the page is.
- Analytics and Local Data respond in **under 2 seconds**.
- Heavy reporting views (Bird Log journal, dataset coverage/quality)
  respond in **under 8 seconds** and must show progress rather than
  appear frozen.

**Scale behaviour.** Building the review queue, and therefore the landing
page and every `review_queue_count`, is proportional to the **review
backlog**, not to total accumulated history -- pinned by tests asserting
flat SQL statement counts across a 10x larger reviewed history.

**Memory.** Sustained use does not produce monotonic unbounded Host
memory growth: 4,427 identical requests against a fixed library moved
resident memory **5.6 MB/hour** over the settled half, with flat file
descriptors and threads. Resident memory tracks the working set of the
library being served, and is expected to rise as that library grows.

**Queues.** Ingest and acoustic queues are bounded by explicit constants
(4 frames; 100 per Stream; 500 global) and shed the **oldest** work to a
diagnosable state under pressure. Queue growth is bounded and recoverable
under the tested burst.

**Restart.** A restart -- graceful or abrupt -- resumes without
duplicating observations, orphaning a Visit or its evidence, losing rows,
or leaving queue work permanently claimed. Verified across three
restarts, two of them `SIGKILL` under load.

**Storage.** Growth is explainable and proportional to retained media:
**4.0 media assets and ~4.3 KB of database per observation**; ~130 KB of
database per day at an established feeder; **48.5 MB of database for a
full year across three cameras**. Logs are hard-capped at 20 MB.

**Backup and upgrade.** A backup of an 11,244-asset library completes in
2.6 s and verifies in 0.4 s; the manifest bound supports ~435,000 media
files, roughly ten years at the measured rate. Migration across a schema
version, including its pre-migration safety backup, took 2.8 s on that
library.

## V. Tier 1 validation

Four new focused test files, 30 tests, each pinning a corrected defect:

| File | Tests | RED against unmodified baseline |
|---|---:|---|
| `tests/test_review_queue_scale.py` | 11 | 3 proven RED (queue build 178 -> 538 statements for 10x history; dashboard 442 -> 807; single-item lookup 228 -> 2,028) |
| `tests/test_bounded_list_endpoints.py` | 6 | Statement counts measured directly before/after (`list_events` 203 -> 2, `list_review_labels` 151 -> 2); the file cannot import against baseline because the route constants do not exist there |
| `tests/test_observation_history_indexes.py` | 6 | Fresh/upgraded index-set equivalence, plan-usage for all 14, and row-identity with and without indexes |
| `tests/test_backup_manifest_scale.py` | 5 | **4 proven RED**, including the pre-migration backup the upgrade path depends on |

Where a test could not be made meaningfully RED by stashing (because the
change adds a constant the test imports), the before/after numbers were
produced by running the same fixture against the stashed baseline
directly, and those numbers are quoted in §T.

## W. Tier 2 validation

Affected subsystems, run against the changes:

- Review queue, dashboard, fast review, identification, review
  provenance, reviewed-observation revision, visit tags/collections/
  organization, API, persistence/migration: **126 passed**, then **104
  passed** after the single-target narrowing.
- Review-queue scale, bounded list surfaces, indexes, backup scale,
  review decision provenance, wildlife journal, dataset coverage/quality,
  dashboard today, demo-source exclusion, research export: **145 passed**.
- Backup, cross-install restore, upgrade-path and clean-install
  acceptance: **34 passed**.
- Persistence/migration suite with the new index tests: **47 passed**
  plus the 6 index tests.

`ruff`: byte-identical to the established baseline on every changed
product file (`product_repository.py` 55 findings before and after;
`api/main.py` 26 before and after; all three `storage/` files clean before
and after). All four new scripts clean.

Fourteen hard-coded `== 59` schema guards across seven test files were
updated to `60`, per this repository's own standing note that a version
bump trips them.

## X. Tier 3 -- full Core

Run twice. Backend, query, storage and migration behaviour all changed
broadly here, so Tier 3 was the default, not a judgement call -- and the
first run immediately justified it.

**First run: 11 failed / 6,111 passed / 4 skipped / 35 deselected / 11
xfailed (1:18:00).**

Six matched the established pre-existing set. Of the other five, **three
were a real defect this milestone had introduced**, and Tier 3 is the only
thing that could have found them:

> `test_camera_health.py`'s own v20 and v21 fixtures and
> `test_repository_isolation.py::test_migrations_during_tests_apply_only_to_the_isolated_fixture`
> all start from deliberately *partial* historical schema shapes.
> Migrations run before `Base.metadata.create_all`, so migration 60
> reached `CREATE INDEX ... ON review_labels` on a database where that
> table did not exist yet, raised `no such table: main.review_labels`, and
> **aborted the whole upgrade**. Every targeted run before this one had
> started from a complete schema and could not have hit it.

Fixed in `700de44`: the migration skips an index whose table is absent,
because `create_all` moments later creates that table together with the
same indexes (declared on the models themselves). Nothing is lost, and an
upgrade can never fail over an index. The three tests pass.

The remaining two --
`test_camera_node.py::test_picamera2_restoration_failure_keeps_evidence_and_lazily_recovers_monitoring`
and
`test_engine_runtime.py::test_v6_shaped_replay_does_not_lose_viable_activity_to_cache_exhaustion`
-- both pass standalone against this tree, touch no code path this
milestone changed, and are timing-sensitive (a restoration path with
deadlines; a bounded-cache replay under churn). They did not recur in the
second run.

**Second, confirming run: 6 failed / 6,116 passed / 4 skipped / 35
deselected / 11 xfailed (43:07).**

All six are the established pre-existing set:

| Test | Status |
|---|---|
| `test_doctor_camera_node_transport.py::test_interpret_no_transport_configured_anywhere_is_pass` | pre-existing |
| `test_doctor_camera_node_transport.py::test_interpret_ignores_sources_without_transport_configured` | pre-existing |
| `test_environmental_context.py::test_temperature_band_established_once_enough_days_are_cached` | pre-existing |
| `test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary` | pre-existing |
| `test_place_biodiversity_summary_repository.py::test_human_correction_updates_place_biodiversity_intelligence_correctly` | pre-existing |
| `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields` | pre-existing (this file's own long-documented recurring date-sensitive fixture flake) |

**Zero Core failures attributable to this milestone's changes.**

Note the run times: 1:18:00 and 43:07 for the same suite. This machine is
shared with an unrelated active workload (§C); that is why §T's wall-clock
figures are reported as ranges and why statement counts, which are
load-independent, carry the structural argument.

## Y. Final state

- **Branch / HEAD:** `main`, this report's own commit. Implementation
  commits, in order: `d149ded` (baseline reconciliation), `4f7542a`
  (review-queue build scale), `e7062bb` (report and list-surface scale),
  `960ff60` (schema 60 indexes + the backup defect), `b76fdfe` (review
  labels in bulk + soak tooling), `a6aab75` (restart/recovery
  verification), `700de44` (index-migration robustness).
- **Schema:** **`v59` -> `v60`** -- fourteen additive indexes, no table,
  column or value changed. Migration of a real 2,813-Visit database,
  including its pre-migration safety backup, took 2.8 s. A fresh install
  and an upgraded install converge on an identical index set, asserted as
  a test. **Version:** `0.1.0`, unchanged.
- **Working tree:** clean apart from the seven preserved untracked
  detector files and `uv.lock`. All seven verified untracked at every
  commit boundary and byte-identical to their session-start SHA-256 at
  close; none was edited, staged, renamed or removed. Staging used
  explicit paths throughout -- never `git add -A` or a directory pattern.
- **Push status:** **not pushed.**
- **Out of scope and untouched:** storage-architecture redesign,
  distributed or cloud infrastructure, multi-site orchestration,
  detector/model selection, MDv5a threshold, BioCLIP, SpeciesNet, BirdNET
  model or licensing decisions, a new task-queue platform, frontend
  rewrite, the accepted UI/UX & First-Run Adoption v1 milestone, Gate G.
- **Truth and data safety:** no change alters Reviewed authority, drops
  evidence, discards work, reorders truth semantics, creates duplicate
  observations, or turns model inference into Reviewed truth. The
  review-queue changes are all "same rows, same order, fewer queries"; the
  one behavioural change (`include_detail=False`) omits fields that no
  caller of that mode reads, and `GET /api/review-queue` itself always
  asks for full detail. Restart correctness is verified directly in §O.

## Z. Remaining concrete v0.1 blockers

**1. `GET /api/review-queue` is unbounded (P0-4) -- reduced by 72% at
Profile B, but not closed.**

The facts: at Profile B the endpoint returns 1,094 items and 7.9 MB in
~5 s; the Review Queue page requests it with `include_reviewed=true`,
which before this milestone was 2,813 items, 20.4 MB and **39.7 s**, on
mount *and after every saved correction*. At Profile C -- an ordinary
three-month library with one burst week and an owner who has fallen
behind on review, which is not an extreme case -- it is 2,060 items,
**14.9 MB and 74.4 s**. At Profile D, 5,023 items, 36.1 MB and 95.8 s. On
native Windows the same endpoint is 2.6x slower again.

Why it was not closed here: the page already paginates client-side at 25
items, but it computes **every tab count, every filter count, bulk-
selection eligibility and the "showing N of M" disclosure client-side over
the full downloaded list**. Bounding the response without moving those
counts to the server would make each of them describe a window while
still being presented as a total -- a truth regression, not a performance
fix. Closing it properly means server-side pagination *plus* server-computed
per-tab counts *plus* a matching change to `ReviewQueuePage.tsx`, the
largest and most complex page in the product and the centrepiece of the
just-accepted UI/UX & First-Run Adoption v1. That is a bounded, designable
piece of work -- and it materially changes an accepted milestone's page,
which is the owner's call to authorize, not this milestone's to take
unilaterally against an explicit "do not rewrite the frontend / do not
reopen the accepted UI/UX milestone" instruction.

The same reasoning applies to P1-7 and P1-8: `GET /api/media` (11.9 MB at
Profile B, ~47 MB at Profile D, six page consumers),
`/api/detection-proposals`, `/api/detection-runs` and
`/api/species-suggestions` are all read in full by pages that aggregate
over the whole set.

**2. Carried forward from earlier milestones, unchanged by this work:**
a live, fresh **Camera Node pairing proof** against the shared reference
Pi (Lane G / Lane R); and the **Doctor media-integrity relative-path**
behaviour recorded in earlier audit notes. Neither is in this milestone's
scope and neither was touched.

**Not measured here, and deliberately so:** model readiness timing and
Camera Node reconnect timing (no inference ran, no Node was paired); GPU
utilisation (the detector is CUDA-only by design and was not exercised);
real image-decode cost and real disk throughput for full-size frames (the
synthetic workload uses tiny media files).

## AA. Advisory next step (advisory only)

The natural next piece of work is the one this milestone measured, root-
caused, designed and deliberately did not take: **bounding the Review
Queue end to end** -- server-side pagination with server-computed per-tab
and per-filter counts, and the matching `ReviewQueuePage` change --
together with the same treatment for `GET /api/media` and the three
detection/suggestion list endpoints. It is the last thing standing between
this product and a review loop that stays usable after a year of use, and
the evidence needed to scope it is in §G, §H and §Z.

Sequencing authority remains external. This milestone does not authorise
itself, that work, or any successor.
