# Attention Integrity & Health Reliability v1 -- Report

**Date:** 2026-09-30. **Start:** `main` at `6acdeb1`. **Version:** `0.1.0`
(unchanged). **Schema:** `v61` → **`v62`**. **Authorized by:**
[Pre-1.0 Software Gap Audit & Contract Lock v1](pre-1.0-software-gap-audit-contract-lock-v1-report.md#first-authorized-implementation-milestone),
first milestone of the locked pre-1.0 queue. **Proposed classification:**
see §8. Acceptance is not recorded here.

## 1. Task packet

- **Phase:** PRE-1.0 PRODUCT COMPLETION -- SOFTWARE-FIRST.
- **Product flow:** Discover → Understand → Improve. Attention has to
  describe the current product state accurately, and one local user's action
  must not erase another user's unread state.
- **Why next:** this is the authorized milestone. It fixes a correctness
  defect in existing multi-user behavior: alert read/dismiss was stored
  globally.
- **Validation tier:** Tier 2 affected subsystem plus the Core gate, `tsc`,
  the production frontend build, and the browser suite.
- **Non-goals, held:** Web Push, VAPID, and subscription persistence;
  cross-camera grouping; UX redesign; detector/classifier/threshold/Visit/
  truth-policy changes; hardware; packaging, version, signing, tagging,
  pushing, and release.

## 2. What changed

### Per-user acknowledgement (outcomes 1-2)

- A new table, `product_alert_acknowledgements`, has primary key
  `(alert_id, user_id)` (one row per user per alert), foreign keys to
  `product_alerts` and `users`, and an index on `(user_id, alert_id)`. It
  holds only `read_at`, `dismissed_at`, and `updated_at`.
- Condition, severity, action/evidence target, resolution, and
  deduplication stay on the shared `product_alerts` row and are never
  copied. An acknowledgement no longer touches the shared row at all, not
  even `updated_at`.
- `product_alert_unread` and `list_product_alerts` compute each viewer's
  status (`unread`/`read`/`dismissed`/`resolved`, with unchanged
  precedence) from that viewer's own row. A GET never creates a row.
- The three mutation routes now require the signed-in user
  (`current_user_or_401`). They return that same user's refreshed summary.
  Before this change they returned an unfiltered summary that ignored the
  caller's preferences and role ceiling.
- A field-acceptance bearer credential is not a human user, so it gets
  `401` on acknowledgement and never writes a shared acknowledgement.
- On the ORM, the old physical `read_at`/`dismissed_at` columns are now
  `legacy_global_read_at`/`legacy_global_dismissed_at`. They serve only as
  the migration source, so a stale caller fails loudly instead of quietly
  reintroducing shared state.
- `CameraHealthSummary.unread_alert` is observatory-global (the background
  health sync computes it with no user). It now means "an open camera
  alert exists" and no longer reads anyone's acknowledgement. Its UI label
  changed from "Unread camera alert" to "Open camera alert". See §6.

### Shared app-shell attention source (outcome 3)

- `web/src/attention/AttentionProvider.tsx` owns the one 60 s poll of
  `/api/alerts/unread` plus preferences for the signed-in shell.
- Both `AlertsControl` instances (mobile header and sidebar) and
  `TodayAttentionSummary` read from it.
- Mutations apply the server's own response, so the badge, drawer, and
  Today line change together without a reload.
- Foreground notifications are delivered once per new alert. Before this
  change, each mounted control delivered its own copy (coalesced only by
  `tag`).
- The provider is keyed by user id, so switching accounts never inherits
  the previous user's counts or "seen" set.
- The Alerts Inbox keeps its own paginated fetch and reports its mutations
  to the shared source.

### Model/runtime Observatory Health alert (outcome 4)

- `mockingbird.monitoring.model_runtime_health` turns existing facts into
  sustained conditions and computes no new fact of its own. The facts come
  from two places:
  - Doctor's own interpreted Detector model, Species identification, and
    GPU / CUDA checks, through the new `doctor.model_runtime_health_checks`
    wrapper. It reuses the same gather/interpret pairs, and only a
    completed WARN/FAIL counts.
  - Each Stream's in-memory Observation Engine Start-failure category
    (`missing_model_or_runtime`, `unsupported_gpu`).
- There is one alert per kind (`detector_model`, `gpu_runtime`,
  `species_model`), with key `observatory-health:model-runtime:<kind>`.
  Two different problems never hide each other, and the same problem seen
  by both Doctor and a failed Start stays one alert.
- **Sustained:** the kind must be observed on at least two evaluations at
  least 120 s apart. With the unchanged 15-minute attention-sync cadence,
  that means two ticks.
- **Deduplicated and versioned:** these alerts use the ordinary
  `_refresh_product_alert` path. A changed code or affected Stream creates
  a new condition version, and the old version resolves.
- **Auto-resolving:** one complete clean evaluation resolves the alert. An
  incomplete check (timeout or error) raises instead. It is recorded as a
  sync failure and is never read as "healthy", which would wrongly resolve
  a real alert.
- **Action and severity:**
  - A real Stream that failed to start gets `open_stream` at `high`
    severity (`immediate` urgency, which reuses the existing mapping).
  - A Doctor-only configuration fact gets the new `open_doctor` action at
    `warning` severity.
  - In the UI, a non-Administrator's `open_doctor` lands on Today, because
    Doctor is Administrator-only.
  - If the Stream later disappears, the action falls back to Doctor, not
    to storage.
- The alert is attention only. It never writes evidence, Visits, or review
  labels, and it never converts a diagnostic inference into Reviewed
  truth.

### Attention-sync diagnostics (outcome 5)

- `AttentionSyncService.diagnostics()` records:
  - last attempt, last success, and last failure;
  - last error code and its registered safe message
    (`attention_sync_database_error` / `attention_sync_failed` in
    `error_taxonomy`, never raw exception text);
  - the exception class name, for support only;
  - the consecutive-failure count;
  - process-lifetime success and failure counters.
- Each failure is also logged as a structured `attention.sync_failed`
  event.
- `_run_attention_sync` runs the Place Story/digest sync and the
  model/runtime health step independently, so either failing never starves
  the other. It then re-raises the first failure so it is recorded.
- `GET /api/product/health` gains an additive `attention_sync` summary
  with status `pending` / `healthy` / `failing`. It is side-effect free and
  never a factor in `ready`.
- The MockingBird status panel shows a notice only while reconciliation is
  failing, along with the last successful reconciliation time. Advanced
  diagnostics show the counters.

### Unchanged (outcome 6)

The following are unchanged:

- quiet hours, foreground notification rules, severity/urgency mapping,
  resolution, pagination, and the existing deep links;
- the Viewer Needs-Help ceiling and per-user category preferences;
- the attention-sync cadence.

## 3. Upgrade / compatibility (schema 61 → 62)

The upgrade defines an explicit, tested rule for the legacy global
acknowledgement:

1. **Users exist at migration time.** Every existing user receives the
   legacy read/dismiss state as their own row, because each of them was
   shown exactly that state before v62. `updated_at` is the later legacy
   timestamp. The legacy columns are then cleared, so from v62 on nothing
   is shared, and a user created later starts with every current alert
   unread.
2. **No users exist yet** (a pre-identity database upgraded before first-run
   setup). The state stays in the legacy columns. It is adopted exactly once
   by the bootstrap Administrator (the pre-identity operator) inside
   `create_first_administrator`'s transaction, then cleared.
3. **Idempotent migration.** The migration uses `IF NOT EXISTS` and
   table-existence guards. It is purely additive and deletes no alert row.
   A backup's `PRAGMA foreign_key_check` stays clean.

Additional compatibility notes:

- Restoring a v61 backup into a v62 Host follows the same migration.
- A v62 database is refused by an older app (the existing
  newer-than-supported guard).
- API compatibility:
  - `ProductAlert.read_at`/`dismissed_at`/`status` keep their shape and now
    mean "this viewer's".
  - `AlertActionType` gains `open_doctor`.
  - `ProductHealthStatus` gains the optional `attention_sync` field.
  - Mutation routes that previously accepted any authenticated caller still
    do so at the same tier, but now require a human session. The
    field-acceptance bearer credential gets `401` on them.
- The eight test files that hard-coded schema `61` were updated to `62`.

## 4. Files

- **Backend:**
  - `storage/models.py`, `storage/database.py`;
  - `repository/product_repository.py`;
  - `api/main.py`, `api/schemas.py`;
  - `monitoring/attention_sync_service.py`;
  - new `monitoring/model_runtime_health.py`;
  - `diagnostics/doctor.py` (a public wrapper only; Doctor behavior is
    unchanged);
  - `diagnostics/error_taxonomy.py` (two codes).
- **Frontend:**
  - new `web/src/attention/AttentionProvider.tsx`;
  - `App.tsx`, `api/types.ts`;
  - `components/AlertsInbox.tsx`, `TodayAttentionSummary.tsx`,
    `ProductHealthPanel.tsx`, `LiveCameraOverview.tsx` (one label).
- **Tests:**
  - new `tests/test_attention_integrity.py` (25 tests);
  - new `web/e2e/attention-integrity.spec.ts` (5 tests);
  - updated `tests/test_alerts_inbox.py`, `tests/test_calm_attention.py`,
    `web/e2e/notification-preferences.spec.ts` (single-poller
    expectations), and eight schema-literal tests.
- **Docs:** this report; a supersession note in
  `calm-attention-notifications-v1-report.md`; a closure entry in
  `release-execution-state.md` §3.

## 5. Validation

All runs are local (WSL, `.venv`), on the implementation working tree.

| Command | Result |
|---|---|
| Red proof: a standalone multi-user HTTP test against `git archive HEAD` source (`PYTHONPATH=<export>/src pytest …`) | **FAILED on HEAD**: the Viewer's unread count dropped to 0 after the Administrator's read. **PASSED** on the working tree. |
| `.venv/bin/python -m pytest -q tests/test_attention_integrity.py` | 25 passed |
| `.venv/bin/python -m pytest -q tests/test_alerts_inbox.py tests/test_calm_attention.py tests/test_attention_sync_service.py tests/test_durable_observation_intent.py tests/test_camera_health.py tests/test_local_identity_multi_user.py` | 107 passed |
| Tier 2 affected set: `pytest -q -m "not slow"` over the 64 test files that reference alerts, attention, product health, the error taxonomy, Doctor, backup/restore, bootstrap, schema status, or camera health | **1671 passed**, 11 xfailed, 0 failed (21m46s) |
| `.venv/bin/python scripts/verify_core.py` | **6278 passed**, 4 skipped, 35 deselected (slow), 11 xfailed, **0 failed** (35m20s) |
| `.venv/bin/ruff check` on every changed Python file | No new findings. Per-file counts are identical to HEAD (pre-existing findings in `main.py`/`product_repository.py`/`test_alerts_inbox.py` untouched). |
| `cd web && npm run build` (`tsc --noEmit && vite build`) | Clean |
| `node e2e/run-playwright.mjs e2e/attention-integrity.spec.ts e2e/notification-preferences.spec.ts` | 17/17 |
| `node e2e/run-playwright.mjs` (complete default suite, no retries) | **203/203** (198 + 5 new) |
| `--config playwright.onboarding.config.ts` / `review-queue` / `bounded-media` | 6/6, 4/4, 2/2 |
| `node e2e/run-playwright.mjs e2e/attention-integrity.spec.ts e2e/notification-preferences.spec.ts --repeat-each=5` | 85/85 |

What the coverage proves:

- **Migration/upgrade:** both branches of the legacy rule, idempotency, a
  fresh install, and a clean foreign-key check.
- **Multi-user isolation:** at the repository, over HTTP, and in the
  browser with two real users; also account switching in one browser.
- **Authorization:** `401` for anonymous callers and for the
  field-acceptance bearer credential; the Viewer can acknowledge only
  their own state and the Needs-Help ceiling still applies.
- **Alert lifecycle:** in-place refresh keeps each user's acknowledgement,
  a new version is unread for everyone, and resolution is global.
- **Side-effect-free reads:** GETs write no acknowledgement row and never
  touch `updated_at`; health reads never trigger a sync.
- **Health alert:** sustain, deduplication, versioning, auto-resolution,
  the stream/Doctor action and its fallback, an incomplete check recorded
  as a failure, and no truth writes.
- **Sync failure/recovery:** counters, the registered codes, the safe
  message, independence of the two sync steps, and the product-health
  exposure.
- **Frontend state:** one poll per interval shared by both controls and
  Today, exactly one foreground delivery, the `open_doctor` navigation,
  the failing-sync notice, and existing deep links (the Place Story,
  stream, and inbox specs in the full suite).
- **Hardware:** no hardware validation was required or claimed.

## 6. Deviations and limitations

- **`CameraHealthSummary.unread_alert` semantics.** This is a necessary
  compatibility correction. It is observatory-global and is computed with
  no viewer, including by the background health sync. Keeping it
  acknowledgement-based would either keep sharing state or require
  threading a viewer through about six camera-health producers, which is
  out of scope. It now means "an open camera alert exists", and the UI
  label says so. Per-user unread state lives in the Attention Center.
- **Health-alert latency.** The cadence is unchanged (the first sync runs
  15 minutes after start, then every 15 minutes), so a sustained
  model/runtime alert appears about 30 minutes after the problem is first
  observed. The Stream and Observation surfaces still show an engine Start
  failure immediately. First-seen state is in-process, so after a restart a
  condition must be re-observed before it alerts again.
- **Cost of each sync tick.** Doctor's detector check fingerprints the
  model bundle on each tick (about once every 15 minutes, off the request
  path, bounded by Doctor's own 15 s timeout).
- **Doctor itself** (CLI/HTTP report) does not show attention-sync
  diagnostics. Doctor can run out-of-process, where the in-process service
  does not exist. The in-process product-health surface carries them.
- **No hardware validation** was required or claimed.

## 7. Protected state

- The eight pre-existing untracked files were not touched, staged, or
  committed.
- Nothing was pushed.
- No version bump, package, tag, or signature was made.

## 8. Proposed classification

**A (proposed, for ChatGPT acceptance review).**

- Every locked outcome is implemented against existing facts, with no
  second computation path.
- The multi-user defect was reproduced red on the pre-change code before
  the fix.
- The legacy upgrade rule is explicit and tested in both branches.
- The Tier 2 set, Core, the type-check/build, and the browser coverage are
  green.
- The disclosed limitations are bounded and do not weaken any locked
  requirement. The one semantic correction (`unread_alert`) is disclosed
  in §6.
