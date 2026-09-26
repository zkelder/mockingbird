# Today Truth Regression Repair v1 -- Contract

One bounded correctness milestone during the v0.1 feature freeze.

**Product purpose.** Preserve Discover -> Confirm -> Remember: confirming
wildlife must not make that wildlife disappear from Today's relevant
summaries and highlights.

**Authorization.** Recorded in
[release-execution-state.md](release-execution-state.md) §3. Native-Windows
Field Reliability Corrections v1 is accepted at `83a0e86`, schema `v61`.
Field Validation Closure v1 remains **unaccepted** because this regression
is a v0.1 blocker. This is the only authorized milestone; it authorizes no
successor.

## The defect

`dashboard_summary`'s Today counts collapsed toward `0` for
reviewed/confirmed Visits.

Introduced by `3d78f8a` (*Review Queue Scale Closure v1 (1/n)*,
2026-09-23), bisected exactly: `73dbcd4` **PASS** -> `3d78f8a` **FAIL**,
direct parent. Present at `8a45d1a`, therefore present in the build Field
Validation Closure v1 validated -- its §U "no remaining v0.1 field
blockers" verdict was reached without knowledge of it.

### Root cause

`_preloaded_motion_evidence_for_review_queue_item` returned an
**authoritative `None`** -- not its own `_PRELOAD_MISS` sentinel -- for any
Visit/Event simply absent from the preloaded set. Its guards checked only
that the cache existed and that a Visit/Event id was supplied; they never
checked whether *this* target was one the preload actually covered.

That is unsafe because the preload map cannot distinguish two different
facts. A target with no `MotionEvidence` is absent from the map, exactly
like a target the preload never fetched. Read as "no rows exist," the
second case answers for somebody else's Visits.

And there is somebody else. `_read_only_build_cache`'s own contract is that
"nested builds share the outermost cache and never clear it early."
`dashboard_summary` opens that outermost cache, calls
`_visible_review_queue_items` **first** (which runs
`_preload_review_queue_rows`, populating the map for the *queue's* member
set only), and **then** calls `_dashboard_today_summary`, whose counting
loops call `_motion_evidence_for_review_queue_item` for Today's Visits.
Reviewed/confirmed Visits are not queue members, so they received
`evidence=None`, `_review_queue_product_context` classified them
`detector_class != "animal"`, and `detector_qualified_animal_visit_count`
collapsed.

### Blast radius

Three lookups consult that shared cache. Their exposure differs:

| Preload | Consumer | Exposure |
| --- | --- | --- |
| `review_queue_motion_evidence` | `_motion_evidence_for_review_queue_item` | **The defect.** Reached by Today's two day loops and by the queue's visit-less Event lane, both outside the preloaded set. |
| `review_queue_pending_suggestion` | `_review_queue_items_uncached` | Latent only. The queue build's membership predicate matches the preload's, so no current caller reads an uncovered Visit -- but a nested build replaces the record with its own narrower set. |
| `media_asset_by_local_path` | `_media_asset_for_path_from_session` | Not exposed. It checks `media_path in by_path` directly, so an unfetched path already fell through. |

The visit-less Event lane is a second, in-queue manifestation of the same
root cause: those Events are by definition not any queued Visit's Event, so
they were never covered, and their review cards lost their snapshot media
and activity context.

## The repaired lookup contract

**A cache answer must equal the answer the original database query would
have given.** Three states must stay distinguishable:

1. **outside preload coverage** -> `_PRELOAD_MISS`, caller falls through;
2. **covered, no evidence** -> a real `None`, served without a query;
3. **covered, with evidence** -> the row, served without a query.

Any lookup whose requested Visit/Event union is not **fully** covered falls
through. A partial answer over a union predicate is a wrong answer, not a
slower one.

Preserved unchanged: media filtering, union deduplication, newest-first
ordering by `(created_at, id)` including `created_at` ties, nested-cache
lifetime and cleanup, queue membership, order and classification.

## Non-goals

- Disabling the preload or reverting the accepted optimization.
- Any schema, public API, review-authority, model, camera-status, recovery
  or production-configuration change.
- `Q-2` (stale Camera Node startup self-test), `Q-4` (camera
  re-initialisation false-Visit burst) and the stale `camera_connected`
  field: all remain open, deferred, non-blocking.
- Live deployment, hardware session, packaging rebuild, or the Full
  packaging gate -- none is required by this cache-only scope.

## Validation

Tier 3. The seven recorded regression tests must pass; new focused
behavioural coverage must compare cached against uncached results for the
uncovered, covered-empty, mixed covered/uncovered, media-filter and
ordering cases; established scale guarantees must be retained with any
query-count change measured on identical data and explained.
