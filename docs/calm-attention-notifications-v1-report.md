# Calm Attention & Notifications v1 — Tell Me When Something Matters

## Identity

- **Starting HEAD:** `e31413a` (Mobile & Remote Experience v1 reconciliation — verified before any edit)
- **Implementation HEAD:** `c22bf94` ("Calm Attention & Notifications v1: Tell Me When Something Matters")
- **Reconciliation HEAD:** the commit immediately following this one (release-execution-state.md + roadmap.md + this report)
- **Schema:** `55 → 56` — one new additive table, `user_notification_preferences` (per-user delivery preferences). Zero changes to any existing table; `ProductAlertModel.category`/`.action_type` are plain `String` columns with no database-level enum/check constraint, so the new `"insight"` category and the two new `open_place_story`/`open_place_report` action types needed no migration of their own.
- **Commits:** implementation commit + reconciliation commit (this report, `release-execution-state.md`, `roadmap.md`)
- **Push state:** local accepted state only; not pushed (matches every prior milestone's standing instruction)
- **Preserved untracked files:** verified present and byte-for-byte untouched at both start and close (see "Preserved files" at the end of this report)

## Existing signal inventory (Phase 1)

Bounded archaeology found that MockingBird already had **two entirely separate worlds** that this milestone's job was to connect, not rebuild:

1. **Every "worth mentioning" fact computation was already a pure, stateless, recompute-from-scratch function**, explicitly documented as never cached: `place_story` (first_seen/return/regularity_change/noteworthy_activity/diversity_milestone/feature_change/phenology/comparison_insight — already deduplicated and idempotent via stable, content-derived event ids), `daily_digest`/its weekly reuse (already ranked, already gated on coverage/maturity), `historical_baseline`/`place_change_summary`/`regularity_narrative` (the shared computation underneath all of the above), `feature_change_comparison` (the four-state before/after maturity vocabulary), and `place_biodiversity_summary`. None of these had any notion of "have I already told the user this."
2. **A real, working durable attention-item system already existed and was already live in the product**: `ProductAlertModel` (`review`/`monitoring`/`storage`/`journal` categories, `info`/`warning`/`high` severity, a `deduplication_key` + `condition_fingerprint` + `condition_version` upsert idiom, `read_at`/`dismissed_at`/`resolved_at` lifecycle, a typed `action_type`/`action_parameters_json` deep-link payload) — surfaced today as an "Alerts" bell (`AlertsControl`, top bar + sidebar, 60s poll) and a full inbox (`AlertsInboxPage`, `/alerts`). It was wired to exactly four narrow condition-sync methods (`_sync_review_alert`, `_sync_camera_health_incident` via `_sync_monitoring_alert`, `_sync_storage_alert`, `_sync_journal_milestone_alert`), called synchronously as side effects of specific write-path methods — never from a scheduled sweep, and **it consumed none of** `place_story`/`daily_digest`/`historical_baseline`/`regularity_narrative`/`feature_change_comparison`.

| Signal | Existing source | Reliability | Urgency (chosen) | Already suppressed/grouped? | Attention behavior chosen |
|---|---|---|---|---|---|
| First reviewed species ever | `_sync_journal_milestone_alert` (raw label COUNT, not `historical_baseline`) | High (reviewed-only) | Digest | Yes — one alert per label, ever | **Reused unmodified** as the canonical Discovery source (see "Semantic deduplication") |
| Returned after meaningful absence | `place_story.detect_regularity_transition_events` (`return` kind) | High (reviewed-only, timing-guarded) | Digest | Yes — one-per-transition, idempotent id | **New sync** wired to `AlertCategory.insight`→Discovery-flavored copy |
| Becoming regular / quieter lately | `place_story.detect_regularity_transition_events` (`regularity_change`) | High | Digest | Yes | **New sync** → `insight` |
| Diversity milestones (1st/5th/10th/25th/50th/100th species) | `place_story.compute_diversity_milestone_events` | High | Digest | Yes | **New sync** → `journal`/Discovery, **except ordinal 1** (see below) |
| Place-wide unusual activity | `place_story.detect_overall_activity_events` (`noteworthy_activity`) | High | Digest | Yes | **New sync** → `insight` |
| Mature Feature before/after comparison | `place_story.comparison_insight_event` (gated on `FeatureChangeComparison.maturity`) | High (`"inferred"`, gated) | Digest | Yes | **New sync** → `insight` |
| Reviewed Feature change event | `place_story.feature_change_event_to_story_event` | High (Reviewed) | Digest | Yes | **New sync** → `insight` |
| Daily calm summary | `daily_digest.compute_daily_digest` via `place_activity_report` | High, coverage-gated | Digest | No (recomputed every page load) | **New sync**, once/local-day, suppressed when nothing meaningful |
| Weekly summary | Same function, `period_label="this week"`, reused unmodified | High | Digest | No | **New sync**, once/ISO-week |
| Needs Help / review queue | `_sync_review_alert` (per-Visit), `DashboardTodaySummary.unresolved_animal_visit_count` | High | In-app only | Per-Visit dedup only, no grouping | **Reclassified** urgency to `in_app_only`; grouped into the daily digest's own "N observations could use your help" clause instead of a new per-item interruption |
| Camera offline / degraded | `_sync_camera_health_incident` (already debounced — see "Debounce/hysteresis") | High | Immediate only at `high` severity | Yes — `CameraHealthIncidentModel` fingerprint/resolve | **Reused unmodified**; only re-classified into the new taxonomy |
| Storage pressure | `_sync_storage_alert` | High | Immediate only at `high` severity | Yes | **Reused unmodified** |
| Detector/BirdNET/model unavailable | Doctor-only point-in-time checks, zero `ProductAlert` integration | N/A | — | N/A | **Not built** — recorded as a real gap (see "Remaining major PRODUCT opportunities") |
| Best Moments | `_best_moments_diversity_capped` — a media/evidence-quality ranker, not a "worth mentioning" signal | N/A | — | N/A | **Deliberately not wired to attention** — it answers "which photo," not "was this interesting"; conflating the two would be a real category error |

## Attention product contract (Phase 4)

One canonical, bounded attention-selection layer was added — **not** a new parallel computation, an adapter over what already existed:

- `ProductRepository.sync_attention_signals(now=None)` is the single entry point. It reads through the exact same public, already-accepted methods Place Story/Today/the Place Report call themselves (`place_story(...)`, `place_activity_report(...)`) in their own short-lived sessions, then reconciles durable attention state in one separate write transaction. It never re-derives a statistic, never queries `VisitModel`/`EventModel` directly, and never invents a second definition of "regular"/"new"/"meaningful change."
- Every attention item **is** a `ProductAlertModel` row (extended, not replaced): `id`, `category` (now `review`/`monitoring`/`storage`/`journal`/`insight`), `severity`, `title`, `message`, `created_at`/`updated_at`, `read_at`/`dismissed_at`/`resolved_at`, `stream_id`/`zone_id`/`visit_id`/`source_id`, `deduplication_key`/`condition_fingerprint`/`condition_version`, `action_type`/`action_parameters_json`. Two more fields are added at the **response** layer only, computed fresh on every read, never stored: `attention_category` (`discovery`/`insight`/`needs_help`/`observatory_health`) and `urgency` (`immediate`/`digest`/`in_app_only`).
- "Deep-link target," "maturity/support," and "reviewed/provisional basis" are not separate fields — they are inherited for free from whichever underlying fact produced the item (a `place_story` event already carries `information_class`/`importance`; a digest already carries `coverage.state`/`maturity`). This is the literal meaning of "attention items are a presentation/delivery decision over existing product facts."

## Taxonomy / urgency (Phase 2/3)

```
AttentionCategory = discovery | insight | needs_help | observatory_health
AttentionUrgency  = immediate | digest | in_app_only
```

Both are pure functions of the existing `(AlertCategory, AlertSeverity)` pair (`ProductRepository._attention_category_for`/`_attention_urgency_for`), unit-tested directly with no database:

| `AlertCategory` | `AttentionCategory` | Urgency rule |
|---|---|---|
| `review` | Needs Help | always `in_app_only` |
| `monitoring` | Observatory Health | `immediate` only at `high` severity, else `in_app_only` |
| `storage` | Observatory Health | `immediate` only at `high` severity, else `in_app_only` |
| `journal` | Discovery | always `digest` |
| `insight` (new) | Insight | always `digest` |

No wildlife/Discovery/Insight content can ever reach `immediate` — this is enforced structurally, not by convention, and is directly unit-tested (`test_attention_urgency_wildlife_content_never_immediate`).

## Selection rules (Phase 9/10/11)

**Wildlife Discovery.** First-ever species stays exactly as it already worked (`_sync_journal_milestone_alert`, Reviewed-only). Returned-after-absence, becoming-regular, and biodiversity milestones are new, sourced from `place_story`'s already-Reviewed-gated event stream — Phase 31's "wait for Reviewed truth, not a shaky unreviewed guess" is satisfied for free, since `place_story` only ever emits wildlife events from `_Classification.CONFIRMED_WILDLIFE` facts.

**Needs Help.** No new selection logic at all — the existing per-Visit `_sync_review_alert` calls are untouched; only their *urgency* classification changed (`in_app_only`), and the existing `DigestOtherActivity.unresolved_visit_count` field (already computed, already on every digest) is surfaced in the daily digest's own sentence. Investigated the pre-existing `ReviewQueuePage`/`product_category` gap from Mobile & Remote Experience v1: it does **not** materially affect this milestone, because Needs Help attention counts off `review_status`/the server-computed `unresolved_animal_visit_count`, never the frontend's buggy `product_category === "animal"` filter — left recorded in its own lane, not fixed here, per the brief's explicit instruction not to expand into a Review Queue redesign by adjacency.

**Observatory Health.** No new selection logic — `_sync_camera_health_incident`/`_sync_storage_alert` are reused exactly as they already worked; only re-classified into the new taxonomy. Detector/BirdNET-unavailable attention was investigated and deliberately **not** built this milestone (see "Remaining major PRODUCT opportunities") — a real, bounded, honestly-recorded gap, not an oversight.

## Deduplication / grouping (Phase 6/7)

The single most important design decision in this milestone, found twice:

1. **First-ever species** is computed two different ways in this codebase (`_sync_journal_milestone_alert`'s raw label `COUNT`, and `historical_baseline`'s canonical `first_confirmed_at`). Rather than unify them (which would mean recomputing full historical intelligence synchronously on every Visit-review commit — a real Phase 38 performance regression, since today's check is a cheap targeted query), `sync_attention_signals` **excludes `first_seen` entirely** from its own sync and documents exactly why in code, so the two mechanisms can never both fire for the same fact.
2. **The 1st-species diversity milestone is *always* dated at that same taxon's own first-ever confirmation** (`compute_diversity_milestone_events` sorts by `first_confirmed_at`), so it is *always* coincident with the `journal:first-label:{taxon}` alert above — a second "1st species recorded!" notification for the exact same moment is the identical anti-pattern. This was caught by a failing test (`test_first_seen_is_not_duplicated_as_a_second_discovery_alert`), not by static review, and fixed by excluding exactly `diversity-milestone:1` while keeping ordinals 5/10/25/50/100 (proven by `test_fifth_species_diversity_milestone_still_fires` — genuinely new information a per-taxon alert does not otherwise convey).

Dedup keys are stable and content-derived, never random IDs, mirroring `place_story`'s own discipline:

```
place-story:<place_story event id>        (e.g. place-story:regularity:northern_cardinal:regular:2025-03-01)
digest:daily:<local ISO date>
digest:weekly:<iso year>-W<iso week>
```

**Grouping.** Needs Help is grouped into the daily digest's own sentence rather than a separate summary alert (avoids double-counting the unread badge). A busy morning of several already-regular species produces zero new alerts at all (nothing *transitioned*), and the calm daily digest is what actually names them together — "Northern Cardinal, Blue Jay, and Tufted Titmouse recorded" — reusing `daily_digest`'s own name-joining, never a second grouping mechanism.

## Cooldowns / hysteresis (Phase 8/12)

- **Health.** Fully reused, not reinvented. `_sync_camera_health_incident` already gates on named duration constants (`CAMERA_HEALTH_DEGRADED_FRAME`, `CAMERA_HEALTH_PROLONGED_CAPACITY_WAIT`) and consecutive-failure counters (`consecutive_failure_count >= 2`) before ever creating an incident, and `CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS=300s` sits comfortably above the retry policy's own worst-case benign-reconnect time (6 × 12s ≈ 72s) by design (documented in `unified_status.py`). This milestone did not touch any of these numbers.
- **Digest.** A `condition_fingerprint` of a constant string (`"digest_has_content"`) per period-scoped `deduplication_key` means the *first* meaningful moment in a day/week creates the alert, and every later re-sync that same period only refreshes its title/message in place — never re-versioning, never re-marking unread, no matter how many times the 15-minute sync ticks before midnight. Proven by `test_becoming_regular_produces_one_insight_alert`'s idempotency assertion and the whole-file re-run pattern.
- **Insight/Discovery.** Each event's own stable id *is* its fingerprint basis (`condition_fingerprint="place_story_event"`, constant) — a real transition, once recorded, never needs a second version under the same key.

## Wildlife discovery (Phase 9)

Implemented: first reviewed species (existing, reused), returned after meaningful absence, becoming regular / quieter lately, Place-wide unusual activity, and biodiversity milestones (5th+). Not implemented as attention: "Best Moment" — investigated `_best_moments_diversity_capped` and concluded it answers a different question (which evidence to show) than "was this worth mentioning," and conflating them would either flood Discovery with routine good photos or silently repurpose a ranking function never designed for notability. Recorded as a real, bounded future opportunity, not built by adjacency.

## Needs Help (Phase 10)

Per-Visit `review` alerts are unchanged in creation; their delivery urgency is now `in_app_only` (badge/list only, never a live interruption), and the daily digest names the count in plain language ("3 observations could use your help") whenever `other_activity.unresolved_visit_count > 0` — reusing a field the digest already computed. The `ReviewQueuePage`/`product_category` gap was investigated (see above) and left in its own lane.

## Observatory health (Phase 11/12)

Reused unmodified: camera health incidents, storage pressure. Investigated and deliberately not built this milestone: a `ProductAlert` for "detector/model unavailable while a Camera Node is configured" (Doctor's `_interpret_detector_model` already has the exact right three-way distinguishing logic — not-configured-and-unused vs. configured-but-broken — but has zero `ProductAlert` wiring today). This is real, bounded, recorded future work, not an oversight; adding it would have meant either duplicating Doctor's own gathered facts into a second live code path or adding a new `/api/doctor`-style route this milestone did not otherwise need.

## Daily / Weekly Digest (Phase 13/14/15)

Both reuse the identical `daily_digest.compute_daily_digest` function Today/the Place Report/`WeeklySummaryCard` already call, via the exact same `place_activity_report(...)` entry point — zero new ranking/statistics module. `sync_attention_signals` calls it once per tick with today's period; the response already carries *both* `.digest` (today) and `.weekly_digest` (trailing usable week, computed unconditionally inside that same call) — no second network/DB round trip needed for the weekly half.

**Suppression** (Phase 14's explicit "never send '0 birds detected today'"): an alert is created/refreshed only when `coverage.state` is `unresolved_activity_only` or `confirmed_wildlife`; `no_monitoring`/`sparse_monitoring`/`no_confirmed_activity` resolve any existing alert for that period instead. An *ordinary* day of already-regular activity is **not** suppressed — Phase 15's own example ("cardinals remained regular") is exactly this case, and the digest's job is a calm routine recap, not only notable-event gating (that gating already happened one layer up, in the Insight/Discovery selection rules).

## User preferences (Phase 16)

New per-user table `user_notification_preferences` (schema 56) — the first per-user settings row in the product (every prior settings table is a Host-wide singleton). Four category toggles mirror the taxonomy exactly (Discovery / Insight / Needs Help / Observatory Health), plus `browser_notifications_enabled` (default `False`) and quiet hours. `GET`/`PUT /api/notification-preferences`, both `authenticated`-tier (any signed-in user manages only their own row). Settings UI: a new "Notifications" card in Local Data, immediately below "Connection & Remote Access," with optimistic-update toggles (a real controlled-checkbox revert bug was found and fixed here — see "Validation").

## Quiet hours (Phase 17)

Deliberately evaluated in the **viewer's own browser-local time**, not a stored server/Place timezone setting — there isn't one (`resolve_host_local_timezone`'s own docstring: "MockingBird has no per-Place timezone setting... 'local' is inferred from the host environment"), and inventing one only for quiet hours would risk exactly the longitude-derived-pseudo-timezone bug class `solar_context.py` already documents as a real, previously-fixed mistake. Since quiet hours are pure *delivery* timing (Phase 17: "They affect delivery only"), the viewer's own device clock is the honestly-correct notion of "local" for whoever is about to be interrupted — this sidesteps the whole timezone gap rather than half-solving it. A window that wraps past midnight (e.g. 22:00–07:00) is handled directly. Quiet hours never affect Observation Engine/monitoring, the Attention Center, or any digest content — only whether a live browser `Notification` fires right now.

## Multi-user behavior (Phase 18)

Confirmed and implemented exactly as the brief predicted: **delivery preferences are per-user; the underlying attention condition stays observatory-level**, unchanged from before this milestone (no `user_id` on `ProductAlertModel`). One fixed role rule is enforced server-side, not just in the UI: a Viewer never sees `review`/Needs Help attention at all (`_visible_alert_categories`), regardless of their own stored toggle — they cannot submit a correction, so there is nothing to act on, only something to be nagged by. Reviewer and Administrator see it per their own preference toggle.

**Honest limitation, not fixed here:** `read_at`/`dismissed_at` remain global, shared columns — a pre-existing characteristic of `ProductAlertModel`, not something this milestone introduced. One user reading an alert does mark it read for every other user's badge too. Making read state genuinely per-user would mean a new per-`(user_id, alert_id)` table, a materially bigger schema change than this milestone's own scope; recorded as a real, bounded future opportunity.

## Attention Center (Phase 19)

Already existed (`AlertsControl` bell + badge, `AlertsInboxPage` full history) — extended, not rebuilt: a new "Insight" filter chip, an `AttentionCategory` label shown next to every item ("Discovery"/"Insight"/"Needs Help"/"Observatory Health" — the internal `AlertCategory`/`kind` strings are never rendered directly), and calmer empty-state copy ("Nothing worth noticing right now... MockingBird stays quiet otherwise"). The existing "Alerts" label/route/component names were deliberately kept (not renamed to "Updates") to avoid gratuitous churn on an already-shipped, tested surface — a real, considered naming decision, not an oversight.

## Mobile integration (Phase 21)

Mobile & Remote Experience v1 already placed `AlertsControl` in both the mobile top header and the desktop sidebar — Phase 21's "compact notification indicator in mobile top bar" was already delivered before this milestone. This milestone's own mobile-relevant additions (the Insight chip, the Today "N things worth noticing" line, the Notifications settings card, deep links) are proven overflow-free at 375px by two new dedicated Playwright checks, alongside the pre-existing mobile-viewport-audit suite (unaffected, re-run clean). No fifth bottom-nav item was added — deliberately, per the brief's own instruction and Mobile & Remote v1's explicit "small, four-destination" design intent.

## PWA / browser notification decision (Phase 22)

Investigated all three options against real, verified facts about this codebase:

- The existing service worker (`web/public/sw.js`) caches **only** Vite's own immutable `/assets/*` bundles and passes every other request through untouched — confirmed by direct inspection, matching memory. No push-subscription, `Notification`, or `notificationclick` code exists anywhere today.
- **No scheduler infrastructure exists** (no APScheduler/Celery/cron) — every "run periodically" need in this codebase is a hand-rolled `threading.Thread` + `stop_event.wait(interval)` (`LocalStorageRetentionService`, `AcousticRuntimeService`, `DurableMonitoringSupervisor`). This shape was reused for `AttentionSyncService` rather than introducing a new scheduling primitive.
- **No per-user settings precedent existed at all** before this milestone (verified: every settings table is a Host-wide singleton) — a genuinely new pattern was needed regardless of the Web Push decision.
- Web Push (Option A) would require: VAPID key management, a persisted push-subscription-per-browser table, and — critically — a genuine **outbound network call from this local Host to a third-party push service** (Google FCM / Mozilla autopush / Apple) every time a notification fires, revealing "MockingBird sent something at time T" metadata to that provider even with an encrypted payload. This directly contradicts the standing instruction "do not add cloud push infrastructure merely to satisfy this roadmap heading" and MockingBird's own local-first/privacy-conscious doctrine, and could not be validated live in this sandbox regardless.

**Decision: B — local/in-app/browser-active notification delivery; background Web Push explicitly deferred.** Plain page-level `new Notification(...)` calls (`web/src/notifications/foregroundNotifications.ts`), fired only while this tab's own JavaScript is still running (open or backgrounded, not closed), never via a service-worker `push` event. This has one concrete architectural advantage over Web Push worth recording: because the page is still alive, a notification's `onclick` handler runs this same page's own in-app router directly (`App.tsx`'s `openAlertAction`) — no `clients.openWindow(url)`, no deep-link query-string scheme was needed at all for the in-app case, only for the (not required, since the page must be running) closed-app case.

## Supported delivery channels (Phase 24)

Exactly two, matching Option B: `in_app` (the Attention Center, Today's summary line, digest content) and `browser_notification` (foreground-only, opt-in, permission-gated). No SMS/email/Slack/Discord/ntfy/Pushover/Home Assistant/webhook marketplace was built or stubbed.

## Local-first / privacy implications (Phase 23/28)

Every capability in this milestone works with **zero** external accounts, zero cloud dependency, and zero new outbound network calls of any kind — the Attention Center, Today's summary, preferences, and digest content are all fully local. Browser notifications, when a user explicitly opts in, never leave the device (no push service, no relay). Copy is calm and non-specific about location by construction (titles/messages already come from `daily_digest`/`place_story`'s own existing, already-reviewed wording conventions — none of this milestone's new code introduces coordinates, credentials, file paths, or camera identifiers into notification text). No new externally-reachable unauthenticated endpoint was added — both new routes (`GET`/`PUT /api/notification-preferences`) default to the same `authenticated` policy tier as every other `/api/*` route.

## Deep links (Phase 25)

| Action type | Target |
|---|---|
| `review_visit` | The specific Visit |
| `open_stream` | The specific Stream |
| `open_storage_retention` | Local Data (Storage & Retention section) |
| `open_wildlife_journal` | Bird Log, optionally filtered by label (existing) |
| `open_place_story` (new) | Place Story, pre-filtered to the right **category group** (wildlife/place/context) derived from the underlying event's own `kind` — Place Story has no per-taxon/per-Feature filter control today, so this is the most precise deep link available without adding one; recorded as a real, bounded future opportunity |
| `open_place_report` (new) | The Place Activity Report (daily/weekly digest's own detail view) |

Verified via real Playwright network-request assertions (not just "the page loads") that clicking a `regularity_change`-sourced alert re-requests `/api/place/story` with exactly the `wildlife` group's kinds. Not verified live over a private-overlay-network URL or an installed PWA (no such environment reachable from this sandbox) — the routing mechanism itself is identical regardless of network path, since it is client-side JavaScript navigation, not a server-templated URL.

## Correction safety (Phase 32)

- **Place Story-derived items:** every sync recomputes the full current set of valid dedup keys and resolves any previously-active `place-story:`-prefixed alert not in that set (bounded to items created within the same 30-day lookback, so an older, already-handled item is never disturbed). Directly proven by `test_stale_place_story_alert_is_resolved_on_next_sync`, which seeds a fabricated "stale fact" row and confirms the very next sync resolves it — this is a real, executable proof of Phase 32's "for derived in-app attention not yet delivered: correct/invalidate it," not just a design intention.
- **Digest items:** re-synced in place every tick; a correction that changes the day's facts is reflected on the next sync within the same period, same key.
- **Already-delivered external notification:** honestly limited, and documented as such — once a live browser `Notification` has fired, it cannot be un-shown from wherever the OS displayed it. The Attention Center itself always reflects current truth on the very next read (nothing here caches a stale claim).

## Product-shaped quiet-week scenario (Phase 36)

Implemented as a real, executable test (`test_product_shaped_quiet_week_stays_calm`), not only prose — a synthetic Place with two long-established regulars, exercised end-to-end through the real `sync_attention_signals` entry point across a compressed Monday→Sunday:

- **Monday** (ordinary regular activity): zero Insight/Discovery alerts.
- **Tuesday** (first-ever bluebird, reviewed): exactly one Discovery alert, `digest` urgency.
- **Thursday** (three Needs Help items): three per-Visit alerts, all `in_app_only`, plus the daily digest's own "could use your help" clause — never three separate interruptions.
- **Saturday** (a busy but ordinary morning, same regular species): zero spurious "biodiversity milestone" or transition alerts.
- **Sunday**: exactly one weekly digest.
- **Whole-week assertion:** total active attention items across the entire week ≤ 14 (not "dozens"), and **zero** ever reached `immediate` urgency.

Scoped honestly: Wednesday's "brief disconnect, no interruption" and Friday's "sustained outage, one message" camera-health claims were **not** re-simulated in this new test (that would mean fabricating Camera Node hardware state this milestone has no real stake in) — they are already covered by the pre-existing, unmodified `_sync_camera_health_incident`/`CameraHealthIncidentModel` test suite this milestone reused rather than rebuilt.

## Performance / observability (Phase 38/39)

`sync_attention_signals` runs on a bounded 15-minute periodic tick (`AttentionSyncService`, a new thread mirroring `LocalStorageRetentionService`'s exact shape — no new scheduling primitive), never per-Visit/per-frame. Its cost is the same `place_story`/`place_activity_report` computation Today/the Place Report/`WeeklySummaryCard` already trigger on every ordinary page load — this is not a new order of magnitude of work, only a new caller of already-accepted, already-bounded functions. Observability is one structured log line per tick (`log_event("attention", "sync_completed", place_story_alerts_active=..., daily_digest_active=..., weekly_digest_active=...)`), matching the existing `camera_node`/`health_incident_opened` precedent rather than a new API surface; a dedicated diagnostics endpoint was considered and deliberately not built, since nothing in this milestone needed it beyond what the structured log already gives support/debugging.

## Validation

**Tier 1 (focused).** New: `tests/test_calm_attention.py` (19 tests: pure category/urgency mapping, digest-message join-grammar/needs-help-clause/singular-plural/fallback composition, Place Story→attention sync + its two dedup fixes, digest suppression/creation, preferences CRUD, role-based Needs Help visibility, per-user category hiding, the full quiet-week scenario), `tests/test_attention_sync_service.py` (3 tests, mirroring `test_storage_retention_service.py`'s exact pattern), a new `tests/test_persistence.py::test_schema_55_upgrades_to_current_with_notification_preferences` migration test. All new tests passing; two real bugs were found and fixed *by* writing these tests, not merely covered by them afterward:
1. The 1st-species diversity-milestone/first-seen double-notification (see "Deduplication").
2. A controlled-checkbox revert bug in `NotificationPreferences.tsx` (every toggle click visually reverted itself for a moment because `onChange` didn't update state until the async `PUT` resolved) — found by a real Playwright `.check()` assertion, fixed with an optimistic update.

**Tier 2 (affected).** `tests/test_alerts_inbox.py` (8/8, unmodified, still passing against the extended schema), `tests/test_place_story.py` + `tests/test_place_story_repository.py` (re-run clean, confirming the new sync's read-only reuse changed nothing about Place Story's own behavior), `tests/test_persistence.py` full file (all schema-migration regression tests, including the new one, passing). Frontend: `tsc --noEmit` clean, `vite build` clean, new `web/e2e/notification-preferences.spec.ts` (11/11 passing — including 4 tests that install a fake `Notification` global and a fake clock to prove `shouldDeliverForegroundNotification`'s own decision logic end to end: a sustained-health `immediate` alert delivers a live notification when enabled; a `digest`-urgency Insight/Discovery alert never does, even though it is genuinely new; quiet hours suppress what would otherwise fire; and the feature stays off unless the user explicitly enabled it, even with permission already granted), full existing e2e suite re-run (118 tests, 1 pre-existing failure — `reviewed-product-loop.spec.ts`, the already-documented `ReviewQueuePage`/`product_category` gap, independently reproduced and unrelated to this milestone — zero regressions from any of this milestone's shared-file changes to `App.tsx`/`AlertsInbox.tsx`/`PlaceStoryPage.tsx`/`DashboardPage.tsx`).

**Tier 3 (Core).** Warranted and run — this milestone changes shared persistence (new table, schema bump), the API surface (two new routes, two modified routes), and adds a new backend service to the app lifespan. Result: 4991 passed / 3 failed / 3 skipped / 23 deselected (slow-marked) / 11 xfailed (28m02s). All 3 failures independently bisected this session, not merely cited from memory: the two `test_place_biodiversity_summary_repository.py` failures (`'seen_before' == 'new'`) reproduce byte-identically against a fresh `git stash push -u` clean-baseline run with zero of this milestone's changes applied; `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success` passed cleanly both in isolation and as part of its own file (7/7) when re-run directly on this milestone's own code — a load-induced timing flake (this Core run overlapped with concurrent Playwright/ruff/build activity in the same session), matching an identical precedent already recorded for this exact test in the Mobile & Remote Experience v1 checkpoint. See §14 of `release-execution-state.md` for the full recorded checkpoint.

`ruff check` on every touched/new Python file: zero new findings (bisected file-by-file against a clean `git stash` baseline — `product_repository.py`'s 57 pre-existing findings and `main.py`'s 26 pre-existing findings both confirmed byte-identical before and after; every genuinely new file — `schemas.py`, `models.py`, `database.py`, `attention_sync_service.py`, both new test files — is fully clean). `git diff --check`: clean, no whitespace errors.

## Remaining major PRODUCT opportunities

Recorded honestly as real, bounded future product opportunities — not release blockers, and not implemented here by adjacency:

- **Web Push** for a genuinely closed-browser interruption — deliberately deferred (see "PWA / browser notification decision"); would need VAPID/subscription persistence and a documented outbound-network/privacy posture change.
- **Detector/model-unavailable Observatory Health attention** — Doctor already has the exact right three-way distinguishing logic; it has no `ProductAlert` wiring today.
- **Per-user read/dismiss state** — today's global `read_at`/`dismissed_at` predate this milestone; a genuinely private per-viewer unread state would need a new per-`(user_id, alert_id)` table.
- **Precise per-taxon/per-Feature Place Story deep links** — today's `open_place_story` action scopes to a category group (wildlife/place/context); Place Story itself has no taxon/Feature filter UI to link into yet.
- **"Off / Calm / More" preset simplification** — four explicit toggles were chosen over a three-tier preset for transparency; a future pass could offer both.
- **A live diagnostics surface for attention-sync health** (candidate counts, last-run time, delivery failures) beyond the current structured log line.
- **Best Moments as an attention signal** — deliberately not connected this milestone; would need its own notability gating, not a repurposing of the existing evidence-quality ranker.

## Capability maturity

**B** — major, genuinely useful calm-attention capability (a real canonical selection layer, real semantic dedup with two anti-pattern bugs actually caught and fixed, real cooldown reuse, real per-user preferences and quiet hours, a real product-shaped quiet-week proof) with a bounded, explicitly-chosen external-delivery limitation (foreground-only browser notifications; Web Push deliberately deferred) and a few honestly-recorded presentation gaps (global read state, coarse deep-link scoping). Not A: external delivery is bounded to the tab-open case by deliberate architecture choice, not yet directly validated end-to-end on a real installed PWA/remote-overlay path. Not C/D: the core mechanism is real, tested, reused rather than duplicated throughout, and the product-shaped scenario proves the calm behavior end-to-end, not just in isolated unit tests.

## Scheduler reconciliation

`CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT` is preserved. Representative Field Acceptance, External Beta, and Final Release Hardening remain downstream. This milestone does not authorize any further milestone; see `release-execution-state.md`'s own reconciliation entry for the exact statement, set to `NONE — GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED`.

## Preserved files

Verified present, unmodified, and untouched at both the start and the close of this milestone:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

An untracked `uv.lock` recurred repeatedly mid-session (an ordinary, never-gitignored side effect of `uv run` invocations in this actively-shared worktree, matching the identical pattern recorded in every recent milestone report) — removed each time it appeared; confirmed absent at this report's own writing.

## Exact `git status --short` (after the implementation commit `c22bf94`, immediately before the reconciliation commit)

```
 M docs/release-execution-state.md
 M docs/roadmap.md
?? docs/calm-attention-notifications-v1-report.md
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```

Every implementation file (backend + frontend + tests) is already committed
in `c22bf94`. Only the three reconciliation files remain: `release-execution-
state.md`, `roadmap.md`, and this report — exactly matching the established
"Reconcile release-execution-state.md + roadmap.md + report" commit pattern
(see e.g. `e31413a`, the starting-HEAD commit for this very milestone). The
7 preserved detector files are untracked by design and untouched throughout.
