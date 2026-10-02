# Orphan Media Integrity & Recovery v1 -- Report

Milestone 3 of the locked pre-1.0 queue. Contract:
[orphan-media-integrity-recovery-contract.md](orphan-media-integrity-recovery-contract.md).
Start HEAD `e5cbfa3`, schema `v62` (unchanged, no migration), version `0.1.0`.
Proposed classification: **A**. Not pushed.

## Delivered

- `mockingbird.storage.orphan_media`: report-only reverse scan, bounded
  revalidated quarantine, restore, history.
- Admin API under `/api/settings/storage-retention/orphan-media/*`, CLI
  `python -m mockingbird storage-integrity`, Local Data "Storage integrity"
  panel.
- Quarantine is a sidecar-manifest move inside `media_root/.orphan-quarantine/`;
  no schema change, no database mutation, no deletion path.

## Validation

- Focused: 25 module tests (ownership conventions, exclusions, traversal,
  symlinks, unreadable directory, DB failure, file bound, duplicate
  references, recent-write grace, already-missing, race between scan and move,
  destination/batch collision, interrupted batch, partial move, restore
  conflict, symlinked quarantine root), 6 API tests, 3 CLI tests.
- Scale: 20,000 files (98% owned) scan in ~0.2s; the test fails if any media
  byte is read during a scan.
- Affected subsystems (retention, backup/restore, storage status, identity
  policy): 182 passed.
- Core: 6311 passed, 4 skipped, 11 xfailed, **1 failed**:
  `test_durable_observation_intent.py::test_start_observing_records_durable_observing_intent`
  -- passes alone and on repeat, exercises the observation-start route (no
  storage path); not attributable. Core ran before one test in the new module
  was made deterministic (a vacuous batch-collision case, see below).
- Browser: typecheck/build clean; new spec 2/2; full suite 211/211.

## Defects found and fixed in this milestone's own work

- The batch-id collision test passed vacuously (clock offset avoided the
  collision) and used a global `uuid4` patch that other code could consume;
  both fixed, and the test now asserts the collision was exercised.

## Disclosed

- The shared test instance has two sample-walkthrough `demo://` media rows;
  they are counted as non-file references.
- Bounded limitations are listed in contract section 9.
