# Concurrent Candidate Visit Persistence Reliability v1

## Identity

- **Starting HEAD:** `dc2043a` (Multi-Camera Place Experience v2, reconciled)
- **Implementation HEAD:** `cfe45a0` -- "Concurrent Candidate Visit
  Persistence Reliability v1: classify + bounded retry SQLite lock
  contention" (a self-referential hash cannot be made perfectly exact
  inside its own commit message/file content -- see `git log` for the
  authoritative value; not chased further than this one correction, per
  this milestone's own explicit instruction).
- **Schema:** `v57 → v57, unchanged.` No new/changed table. The fix is a
  narrower exception classification inside one existing method plus a
  bounded retry loop inside one existing caller method -- no persisted
  shape changed.
- **Push state:** local accepted state only, per standing instruction. Not
  pushed.

This is a bounded correctness milestone, not a Multi-Camera follow-on. The
rest of Multi-Camera Place Experience v2's own scope (UI, camera
attribution/filter, Place Story, notification grouping, etc.) was not
reopened.

## Why this milestone exists

Multi-Camera Place Experience v2's own real, measured concurrency test
(`tests/test_multi_camera_concurrent_runtime.py`) found, root-caused, and
*deliberately did not fix* a real, reproducible defect: an admitted
candidate could be silently lost under real concurrent multi-Stream SQLite
writes. A bounded transient-retry fix was attempted and reverted because it
did not reliably close the gap and, under host load, made things worse. See
that milestone's own report, "Fairness / backpressure," for the full
original finding.

## Reproducer

**Primary (pre-existing, exact Multi-Camera v2 shape):**
`tests/test_multi_camera_concurrent_runtime.py::test_four_cameras_asymmetric_load_quiet_streams_are_not_starved_by_a_busy_one`
-- 4 real OS threads, one per Stream, each with its own `ProductRepository`
connection against one shared SQLite file, driving the real
`_EngineSession._run_assembly_tick` -> `CandidateVisitAuthorityAdapter` ->
`ProductRepository.create_candidate_visit_from_proposal` path.

This test passed **10/10** on this sandbox idle (confirmed at the start of
this investigation) and needed **real induced host CPU contention** (10-28
background `yes`/`dd` processes started deliberately for this
investigation) to reproduce even once -- it failed once in 8 runs under
moderate induced load (`stream-quiet-1 created 2 candidates, expected
exactly its own 3`), and escalated to a full 60-second thread-join timeout
under heavier induced load. This confirms the defect is real but is not a
reliable regression gate by itself in this environment -- exactly why a
second, deterministic reproducer was built (below).

**New (deterministic, no artificial host load needed):**
`tests/test_concurrent_candidate_visit_persistence_reliability.py::test_candidate_visit_survives_a_real_concurrent_sqlite_write_lock`
-- forces the exact same real mechanism on demand: a genuine second SQLite
connection to the same on-disk file executes `BEGIN IMMEDIATE` (acquiring a
real RESERVED write lock) and holds it for 5.3s -- longer than the engine's
own configured `PRAGMA busy_timeout=5000` -- while the real, unmodified
adapter/repository path attempts to persist a real, assembler-produced
candidate for a second Stream. Independently verified **RED** against the
pre-fix implementation (`git stash` of only the two production files, tests
left in place) and **GREEN** after, both confirmed by direct re-run, not
assumed:

- Pre-fix: `outcome='failed', reason='observation_candidate_visit_persistence_failed'`
  -- the candidate is lost, exactly the demonstrated defect.
- Post-fix: `outcome.created is True`, same Stream attribution, zero
  recorded failures.

Command: `python -m pytest tests/test_concurrent_candidate_visit_persistence_reliability.py -q` (~9s).

## Demonstrated root cause

Captured directly (a temporary diagnostic print, added and removed during
investigation, confirmed the exact exception before any fix existed):

```
DIAG-CAPTURE type=sqlalchemy.exc.OperationalError repr=OperationalError('(sqlite3.OperationalError) database is locked')
  File ".../product_repository.py", line 6641, in create_candidate_visit_from_proposal
    outcome = self._create_candidate_visit_locked(...)
  File ".../product_repository.py", line 6757, in _create_candidate_visit_locked
    self._touch_scene_confusor_region(...)
  File ".../product_repository.py", line 9339, in _touch_scene_confusor_region
    session.flush()
  ...
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) database is locked
[SQL: UPDATE observation_authority_settings SET proposals_observed_count=?, candidates_attempted_count=? WHERE observation_authority_settings.stream_id = ?]
[parameters: (9, 9, 'stream-busy')]
```

**Mechanism:** each production Stream already uses its own independent
`ProductRepository`/connection to one shared SQLite file (confirmed
architectural fact, not new). SQLite allows only one writer at a time; a
second connection's own first write inside its transaction
(`session.flush()`, triggered here from inside
`_touch_scene_confusor_region` but really just flushing whatever is
pending -- in this case the in-memory `proposals_observed_count`/
`candidates_attempted_count` mutations already made earlier in the same
transaction) must acquire SQLite's write lock. Under real contention this
can exceed the configured 5000ms `busy_timeout`, raising `sqlite3.
OperationalError: database is locked`, wrapped by SQLAlchemy as
`sqlalchemy.exc.OperationalError`.

**Answering the investigation questions:**

1. **What exact operation loses the Visit?** The write-lock acquisition for
   the transaction's own first flushed write (an `UPDATE observation_
   authority_settings ...`, or later a `MediaAssetModel`/`EventModel`/
   `VisitModel` insert depending on how far the transaction had progressed
   before its first flush) inside `create_candidate_visit_from_proposal`'s
   `with session.begin():` block.
2. **Mechanism:** SQLite `database is locked` (`SQLITE_BUSY`) under real
   concurrent multi-Stream writes -- confirmed directly, not inferred.
   Rejected as the mechanism: transaction/session lifecycle bug (the
   transaction behaves correctly -- see point 4), concurrent rollback bug
   (rollback is correct and already tested -- see below), exception
   swallowing as the *root cause* (it is a real, separate, compounding
   defect -- see point 3 -- but not what generates the error), shared-
   session misuse (each connection is correctly independent; the *lock*
   that exists, `_observation_authority_lock`, is a no-op across
   connections but is not what causes this failure), connection-pool
   behavior (not implicated -- each `ProductRepository` in both the test
   and production owns one dedicated engine/pool), write ordering (not
   implicated), uniqueness/idempotency conflict (idempotency is intact and
   is in fact what makes the fix safe -- see the invariant below),
   persistence-after-another-state-transition or a proposal/admission race
   (no such race exists -- the whole candidate-authority decision and the
   write happen inside one transaction).
3. **Boundary where the candidate becomes unrecoverable:** *not* inside the
   repository (which correctly raises a typed, chainable `ValueError`) --
   it was `candidate_visit_adapter.attempt_candidate`'s single `except
   ValueError` handler, which (pre-fix) recorded the failure and returned
   `"failed"` on the very first attempt, with no retry of any kind. That is
   the exact, sole point a genuinely transient, recoverable condition
   became a permanent, silent loss.
4. **Partial state left behind:** none of the listed partial states occur.
   SQLAlchemy's `session.begin()` context manager rolls back the *entire*
   transaction on any exception -- confirmed both by this milestone's own
   deterministic real-lock test (re-querying the ledger after a recovered
   retry shows exactly one row, never two) and by a **pre-existing,
   already-accepted test**,
   `tests/test_candidate_visit_repository.py::test_persistence_failure_rolls_back_and_creates_no_partial_truth`,
   which simulates a disk failure mid-transaction and asserts `_counts(repository)
   == before` -- i.e. *zero* partial rows survive a failure at this exact
   boundary, for any exception type. One honestly-disclosed, bounded,
   *pre-existing* (not introduced by this fix) side effect: `_write_media_
   file` writes evidence bytes to disk *inside* the transaction; a
   filesystem write is not rolled back by a SQLite transaction abort, so an
   attempt that fails *after* writing one or more media files (but before
   the whole transaction commits) can leave an orphaned file with no DB row
   referencing it. This existed before this milestone on every failure
   path; seeing it needs to be listed under "remaining risk," not
   attributed to this fix.
5. **Can the existing operation safely be retried?** Yes -- proven, not
   assumed. `create_candidate_visit_from_proposal`'s own docstring already
   asserted this; this milestone independently confirmed it with a real
   forced-contention test that recovers via retry with zero duplication,
   and with the pre-existing rollback test above.
6. **What makes it idempotent?** The `existing = session.get(
   ObservationCandidateVisitModel, proposal.proposal_id)` check at the very
   top of the transaction, keyed on the proposal's own stable
   `proposal_id`, combined with full transactional atomicity (point 4). A
   retried call for the same proposal either creates fresh (the normal
   case here -- the failed attempt left zero trace) or discovers a
   racing attempt already succeeded and returns `idempotent_repeat` --
   already-existing, untouched behavior.
7. **N/A** -- retrying is intrinsically safe (point 5/6).
8. **Did the caller distinguish contention / permanent / duplicate?**
   Duplicate/already-created state was already distinguished
   (`idempotent_repeat`, pre-existing). Contention vs. permanent was **not**
   distinguished before this milestone -- every non-`ValueError` exception
   collapsed into the identical string `observation_candidate_visit_
   persistence_failed`, discarding the real exception type/message at the
   only place (`candidate_visit_adapter`) that decides what to do next.
   This is now fixed (see "Implementation").
9. **Is SQLite configured appropriately?** `busy_timeout=5000` is present
   and reasonable for ordinary contention (`src/mockingbird/storage/
   database.py`). WAL mode is **not** enabled (effective default rollback-
   journal mode). The write transaction also does more work than strictly
   minimal while holding the lock (evidence-byte disk I/O via `_write_
   media_file`, plus several explicit `session.flush()` round trips for
   id-generation), which lengthens the exposure window. This is a real,
   disclosed opportunity, **not fixed this pass** (see "Rejected /
   deferred," below).
10. **Would changing global SQLite configuration fix this, or mask it?**
    Not attempted this pass, deliberately. This exact codebase already
    carries a directly on-point, documented negative result:
    `database.py::_run_migrations_with_transactional_ddl`'s own docstring
    records that an earlier milestone tried applying `isolation_level=None`
    + explicit `BEGIN` to the *shared* engine (the one `ProductRepository`
    uses) and measured a **worse** failure rate (0/4 -> 2/3) on an
    unrelated concurrent-authority test -- global engine/transaction
    reconfiguration in this codebase has already once produced a
    regression nobody expected. Given the smaller, strictly more local,
    already-idempotent caller-side retry demonstrably closes the gap
    (RED -> GREEN on the deterministic reproducer), a global config change
    was judged unnecessary to prove for *this* fix, not evaluated and
    rejected on its own merits. It remains open, honest future work --
    see "Remaining risk."

## Persistence / transaction invariant (locked)

> One admitted candidate whose `create_candidate_visit_from_proposal`
> attempt raises a *classified-retryable* error (SQLite lock/busy
> contention) must be retried, unmodified, from a fresh session, up to a
> small bounded number of times before being recorded and returned as a
> genuine failure. Every other repository failure remains recorded and
> returned as a genuine failure on the very first attempt, exactly as
> before this milestone. No retry may ever be able to produce two Visits,
> two Events, or duplicate evidence for one proposal -- guaranteed by the
> method's own pre-existing `proposal_id`-keyed idempotency check plus full
> transaction atomicity, both already true before this milestone and
> re-verified, not re-implemented, by it.

## Rejected hypotheses

- Transaction/session lifecycle defect as the *generator* of the failure
  -- disproven; the transaction behaves correctly (point 4 above).
- Shared/misused session across threads -- disproven; each Stream's own
  connection is correctly independent both in production and in the
  reproducer. The per-instance `_observation_authority_lock` is a
  documented no-op across connections (see Multi-Camera v2's own report,
  "Concurrent runtime") but is not itself the cause of this failure and was
  left untouched -- removing it is out of this milestone's bounded scope
  and not required by the fix.
- Missing idempotency around the candidate->Visit boundary -- disproven;
  idempotency was already present and is what makes the fix safe (point
  5/6 above).
- A race between proposal/admission state and Visit creation -- disproven;
  the whole decision and the write happen inside one transaction.
- "Just retry harder" (more attempts, longer backoff) *inside the
  repository method itself* -- this is what Multi-Camera v2 already tried
  and reverted. Not re-attempted in the same location; see "Why the prior
  approach was insufficient," below.

## Implementation

Two small, additive changes, no schema change:

**1. `src/mockingbird/repository/product_repository.py` --
`create_candidate_visit_from_proposal`.** The existing `except Exception`
boundary is now preceded by a narrow `except OperationalError` branch that
inspects the underlying `sqlite3` error message for `"locked"`/`"busy"`.
Only that shape is reclassified to a new, stable code,
`observation_candidate_visit_persistence_contention`; every other
`OperationalError` (for example a real disk/corruption fault) and every
other exception type keep the exact prior code and behavior,
`observation_candidate_visit_persistence_failed`. A `log_error_event` call
(the existing structured-log/error-taxonomy helper, already used twice
elsewhere in this same file) now also surfaces the real exception detail --
previously discarded entirely once wrapped into the generic `ValueError`.

**2. `src/mockingbird/observation/candidate_visit_adapter.py` --
`CandidateVisitAuthorityAdapter.attempt_candidate`.** The single `try`
around the repository call is now a bounded loop (3 total attempts, short
deterministic+jittered backoff: `(0.05, 0.15)` seconds between attempts,
worst case ~0.4s added latency). Only the new
`observation_candidate_visit_persistence_contention` code is retried; every
other failure returns on the first attempt exactly as before. Each retry
calls the repository method completely fresh, so it always opens a brand-
new session/transaction. `record_observation_authority_failure` (the
existing, already-accepted, bounded per-Stream diagnostic --
`failure_count`/`last_failure_code`/`last_failure_at`) is called exactly
once per genuinely-lost candidate, never once per internal attempt; a
retry-exhausted contention failure gets a distinguishable
`...:retries_exhausted` suffix on `last_failure_code` so the diagnostic can
tell "tried and gave up" apart from "never retryable in the first place."

No schema change. No change to `ReviewLabel`/Observation truth semantics.
No change to concurrent-sibling Event reuse or ambiguous-boundary
arbitration (neither module was touched). No cross-Stream behavior change
(the fix is entirely inside one Stream's own attempt).

## Why the prior retry approach was insufficient

Multi-Camera Place Experience v2's own attempt wrapped retry *inside*
`create_candidate_visit_from_proposal` itself -- the same method whose own
report explicitly named "caller-side retry in `candidate_visit_adapter.py`
instead" as an untried alternative. This milestone implements exactly that
untried alternative, for a concrete, defensible reason: retrying inside the
repository method risks reusing a `Session` a failed `flush()` may have
left in a rollback-required state unless the retry loop is scrupulously
careful to open a fresh session per attempt; retrying at the caller
boundary gets a fresh session *for free*, since calling the method again
already does that by construction. This milestone cannot fully reconstruct
*why* the prior attempt specifically failed to reliably close the gap (that
code was reverted before commit and left no diff), so this report does not
claim to have found its exact bug -- only that this milestone's own
differently-located, differently-scoped, classification-first fix is
independently proven (RED/GREEN, deterministic) to close the demonstrated
gap without the prior attempt's disclosed side effect (no latency
regression measured -- see "Validation").

## Tests added

- `tests/test_concurrent_candidate_visit_persistence_reliability.py`
  (new file, 1 test): the deterministic, real-SQLite-lock, real-adapter-
  and-repository, two-Stream end-to-end reproduction and proof described
  above.
- `tests/test_candidate_visit_adapter.py` (3 new tests, mock-based,
  deterministic, fast -- complement the slower real-lock test by proving
  the retry/classification *logic* precisely):
  - `test_non_contention_failure_is_not_retried` -- a permanent failure
    still fails on attempt 1, exactly as before.
  - `test_transient_persistence_contention_recovers_via_bounded_retry` --
    two contention failures then success -> `created`, exactly 3 calls,
    zero recorded failures.
  - `test_persistent_contention_exhausts_bounded_retry_and_is_recorded_failed`
    -- contention that never clears -> exactly `_MAX_PERSISTENCE_ATTEMPTS`
    calls (bounded, not one, not unbounded), one recorded failure with the
    `:retries_exhausted` suffix.

All four new tests independently confirmed **RED** against the pre-fix
implementation via `git stash` (the mock-based three fail at import/
collection since the retry constants do not yet exist; the real-lock test
fails with the exact demonstrated defect, `outcome='failed'`) and **GREEN**
after restoring the fix.

## Validation

**Tier 1 (focused):** the 4 new tests above, plus the pre-existing
reproducer and the pre-existing rollback-atomicity test, all pass:

```
tests/test_candidate_visit_adapter.py (19 tests, incl. 3 new)          PASS
tests/test_concurrent_candidate_visit_persistence_reliability.py (1)   PASS
tests/test_multi_camera_concurrent_runtime.py (2, clean host, 5x)      PASS
tests/test_candidate_visit_repository.py::test_persistence_failure_
  rolls_back_and_creates_no_partial_truth                              PASS (unmodified)
```

**Tier 2 (directly affected subsystems -- candidate Visit authority/
persistence, repository, Event/Visit, multi-subject, observation-engine
integration, multi-camera concurrency):**

```
python -m pytest tests/test_candidate_visit_adapter.py \
  tests/test_candidate_visit_authority.py \
  tests/test_candidate_visit_authority_acceptance.py \
  tests/test_candidate_visit_repository.py \
  tests/test_candidate_visit_review_workflow.py \
  tests/test_candidate_visit_rollback.py \
  tests/test_concurrent_candidate_visit_persistence_reliability.py \
  tests/test_dashboard_observation_engine_truth.py \
  tests/test_engine_runtime.py \
  tests/test_multi_camera_concurrent_runtime.py \
  tests/test_multi_camera_place_experience_scenario.py \
  tests/test_observation_engine.py -q
```

Result: **231 passed, 0 failed** (2m41s, clean host). An earlier run of
this same command produced one failure
(`test_four_cameras_asymmetric_load_quiet_streams_are_not_starved_by_a_busy_one`,
"did not finish within 60s") -- traced immediately to this investigation's
own leftover artificial CPU/disk load (24 `yes` + 4 `dd` background
processes started earlier to reproduce the original defect and not yet
killed at that point); killed, host confirmed idle (98.5% CPU idle), and
the full slice re-run clean with the result above. Recorded here for
honesty, not silently omitted.

**`ruff check` / whitespace:** `git diff --check` clean. `ruff check` on
every touched Python file, content-normalized before/after comparison via
`git stash` (excluding line:col numbers): **byte-identical** -- the 57
pre-existing findings in `product_repository.py` reproduce unchanged; zero
new findings. The new dedicated test file is clean on its own
(`ruff check` reports no issues).

**Tier 3 (full Core gate, `scripts/verify_core.py` /
`pytest -m "not slow"`):** **5109 passed, 3 failed, 3 skipped, 23
deselected, 11 xfailed** (25m46s, clean idle host). All 3 failures
confirmed unrelated to this milestone:

- `tests/test_place_biodiversity_summary_repository.py::test_api_route_returns_the_summary`
  and `::test_human_correction_updates_place_biodiversity_intelligence_correctly`
  -- the identical, already-disclosed pre-existing pair
  (`'seen_before' == 'new'` assertion mismatch) Multi-Camera Place
  Experience v2's own report already confirmed pre-existing against a clean
  baseline; not re-bisected a further time here, matching that report's own
  precedent for this exact pair, and this milestone touched neither
  `product_repository.py`'s biodiversity code nor anything it depends on.
- `tests/test_transport_worker.py::test_retryable_failure_returns_item_to_failed_retryable_and_eventually_succeeds`
  -- new to this run, confirmed unrelated by two independent checks rather
  than assumed: (1) **zero import-level connection** -- `test_transport_
  worker.py` and the `mockingbird_node.transport_worker` module it exercises
  belong to the separate Camera Node-side `mockingbird_node` package and do
  not import `product_repository` or `candidate_visit_adapter` anywhere
  (grepped directly, confirmed empty); (2) re-run in isolation on the same
  now-idle host, **5/5 passed** (0.37-0.62s each). The failure itself is a
  classic load-sensitive async-timing flake -- a fixed `_run_until(...,
  timeout=3.0, interval=0.02)` poll racing a background worker task inside
  a 5,100-plus-test, 25-minute suite run, not a deterministic defect. Not
  re-run inside the full suite a second time (a 25-minute re-run to
  re-confirm an already architecturally-proven-unrelated, already reliably-
  reproduced-passing flake would be exactly the "burn remaining context
  repeatedly rerunning known unrelated failures" this milestone's own brief
  warns against).

**Net result: zero regressions attributable to this milestone's changes.**

## Remaining risk

- **Orphaned media file on a failed-then-retried attempt.** Pre-existing,
  not introduced by this fix: `_write_media_file` writes to disk *inside*
  the SQLite transaction; a filesystem write is not rolled back by a
  transaction abort. An attempt that fails after writing one or more media
  files, whether it is eventually retried to success or exhausted, can
  leave an orphaned file with no DB row. Bounded (one small file per failed
  attempt, not unbounded), not a correctness/duplication risk (no Visit/
  Event/DB row survives), and strictly no worse than before this milestone
  -- if anything, fewer total failures now occur. Not fixed this pass;
  would need moving the disk write outside the transaction's critical
  section, a larger, riskier restructuring of the most critical write path
  this milestone's own governing brief explicitly cautions against
  attempting without dedicated, isolated proof.
- **The transaction still does more work than strictly minimal while
  holding SQLite's write lock** (evidence-byte disk I/O, several `session.
  flush()` round trips for id generation) -- a real, disclosed
  contributing factor to how easily `busy_timeout` is exhausted under
  bursty load, investigated (see investigation question 9) but not
  restructured this pass. This is the most concrete "transaction/session-
  scope" opportunity for a future, dedicated, carefully-isolated milestone.
- **WAL mode / a higher `busy_timeout` were not empirically tested** this
  pass (see investigation question 10) -- deliberately, given this exact
  codebase's own documented prior negative result from touching the shared
  engine's transaction configuration. The retry fix is proven sufficient
  for the demonstrated mechanism without needing this; it remains
  legitimate, uninvestigated future work, not a rejected-and-disproven
  option.
- **Bounded recovery means bounded, not unlimited, tolerance.** Under
  sufficiently extreme, sustained artificial contention (this
  investigation's own escalation to 24-28 background CPU/disk-stress
  processes on a 12-core host), even this fix's retry budget can be
  exhausted and a thread can still miss the reproducer's own 60-second
  join bound. This matches the brief's own "no infinite retry loops"
  requirement and the disclosed fact that real production Camera Node
  frame cadence is far slower than this synthetic stress test's back-to-
  back writes; it is not evidence the fix is insufficient for the real
  product concurrency model, only that no finite local retry can survive
  unbounded adversarial contention, which was never the goal.
- **This milestone cannot fully reconstruct why Multi-Camera v2's own
  reverted retry attempt specifically failed to reliably close the gap**
  (its code was reverted before commit, leaving no diff to inspect) -- see
  "Why the prior approach was insufficient."

## Classification: **A**

Root cause demonstrated and captured directly (a real stack trace, not
inference); the exact defect deterministically reproduced on demand,
independent of host load or scheduler luck; a small, additive, narrowly-
scoped fix implemented at the boundary the evidence pointed to, not a
repeat of the already-reverted broader retry; the fix's safety rests on two
independently-verified pre-existing facts (idempotency, full transaction
atomicity), not a new assumption; every new test independently confirmed
RED against the pre-fix implementation and GREEN after; zero regressions
across Tier 1 (fast, focused), Tier 2 (231 directly-affected tests), and
Tier 3 (full Core gate, 5109 passed) -- the only 3 failures anywhere are
independently confirmed pre-existing/unrelated, two by established prior
precedent and one by fresh import-graph proof plus reliable re-reproduction.
Not held back from **A** by the honestly-disclosed remaining risk items
above -- none of them are correctness gaps in what this milestone actually
claims to fix; they are real, bounded, separately-scoped opportunities for
future, dedicated work (the deeper transaction-scope restructuring; WAL/
busy_timeout experimentation), exactly the kind of honest disclosure this
milestone's own brief asks for rather than a reason to downgrade a
demonstrated, validated fix.

## Scheduler reconciliation

Per this milestone's own explicit instruction: this report does **not**
authorize a next milestone. `docs/release-execution-state.md` is updated,
in a separate reconciliation commit, with only the accepted delta (HEAD,
latest-accepted-milestone entry, Multi-Camera/reliability lane status,
Tier 1/2/3 result) -- schema stays `v57`, and
`CURRENT AUTHORIZED NEXT MILESTONE` stays
`NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`.

## Preserved files

The seven preserved untracked detector files were confirmed present and
untouched (name, line count, byte size) at the start and the close of this
milestone; none were staged, modified, renamed, or deleted:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`
