# Review Queue Scale Closure v1 -- closure report

Performance / Scale / Stability Closure v1 fixed three of its four
release-blocking findings and said plainly, in its own §Z, why it had not
fixed the fourth:

> `GET /api/review-queue` is unbounded. At the burst/backlog profile it is
> 2,060 items, **14.9 MB and 74.4 s**, and the Review Queue page requests
> it with `include_reviewed=true` on mount *and after every saved
> correction*. Bounding the response without moving the counts to the
> server would make each of them describe a window while still being
> presented as a total -- a truth regression, not a performance fix.

This milestone is that bounded continuation. It changes data access, not
product meaning: the tabs, filters, reviewed history, correction flows,
counts, demo-source exclusion and Measured/Inferred/Reviewed boundaries are
the accepted ones, and the numbers the page shows still describe the whole
queue. What changed is that the page no longer downloads the queue to
produce them.

---

## A. Starting HEAD / schema

| | |
|---|---|
| Repository | `/home/<user>/projects/mockingbird-active` |
| Branch | `main` |
| HEAD at session start | `73dbcd4` ("Publish the Performance / Scale / Stability Closure v1 report and record it in release-execution-state.md") |
| Schema at session start | **`v60`** |
| Version | `0.1.0` |
| Push status at session start | not pushed |

Working tree at session start: clean apart from the seven preserved
untracked detector files and `uv.lock` -- all eight present and untracked,
exactly as expected. Each of the seven was SHA-256'd at session start and
re-verified at every commit boundary (§R).

**Writer safety.** `git status` matched the expected baseline exactly at
session start: no `index.lock`, no stash, no in-progress merge, no tracked
file with an mtime later than the accepted HEAD commit. This session
recorded its single-writer claim in an untracked
`.git/MOCKINGBIRD_ACTIVE_WRITER` marker -- inside `.git/`, so never part of
the working tree -- matching the convention the prior milestone
established. `git log`'s own HEAD was `73dbcd4` at session start and moved
only by this session's own commits. No writer collision occurred.

**Schema: unchanged at `v60`.** This milestone adds no table, no column, no
migration. It is entirely a read-path change plus response shapes.

---

## B. The existing Review Queue contract, as locked before implementation

Read out of `web/src/pages/ReviewQueuePage.tsx`, `web/src/App.tsx` and
`GET /api/review-queue` as they stood at `73dbcd4`. This is the behaviour
the implementation had to preserve, not a proposal.

### B.1 Tabs / groups

`ProductReviewTab`, rendered by `ReviewFilterTabs` with a count on each chip:

| Tab | Membership (`matchesProductReviewTab`) |
|---|---|
| **Animals** | `review_status === "needs_review"` **and** `target_type === "visit"` **and** `product_category === "animal"` |
| **Other activity** | `needs_review` and `product_category === "other_activity"` |
| **Unchecked** | `needs_review` and `product_category === "unchecked"` |
| **Sample and older activity** | `product_category === "legacy_activity"`, **and only offered at all** once "Show sample and older activity" is ticked |
| **Reviewed** | `product_category === "reviewed"` |

`product_category` itself is decided in `_review_queue_product_context` and
is not touched by this milestone.

### B.2 Default tab behaviour

- Initial tab is **Animals**.
- `pendingProductTabs` = Animals, Other activity, Unchecked, plus
  Sample-and-older *only when it is being shown*.
- `pendingReviewCount` = the sum of those tabs' counts, shown as "N visits
  are waiting for you".
- `firstPendingProductTab` = the first of those with a non-zero count; it
  drives the "there is still work in another group" recovery affordance
  when the current tab is empty.

### B.3 Filters

A collapsed "Advanced evidence filters" panel plus a collapsed "Filter
review items" panel, applied in this exact order in `filteredItems`:

1. the in-session **skip** set (`skippedTargetIds`);
2. the product **tab**;
3. a **hand-off scope** (`scopedVisitIds`, capped at 50, set when another
   screen says "review these Visits");
4. the **triage** filter (`ReviewFilter`: All / Animal evidence / Vehicle
   or person / No clear proposal / Not checked / False positives), derived
   per item by `reviewTriageSummary` from linked detection proposals,
   detection runs and the taxonomy;
5. the **type** filter (All / Visit / Event);
6. the **status** filter (Unreviewed / Reviewed / All) -- **deliberately
   not applied on the Reviewed tab**, an Everyday Product / Discovery UX
   Closure v1 fix: the tab already determines status, and the collapsed
   control's "Unreviewed" default would otherwise AND into an
   unsatisfiable condition and empty the tab with no visible reason;
7. the **evidence** filter (Has best frame / Has suggestion evidence / Has
   activity evidence / No suggestion evidence);
8. the **source or stream** filter, whose options are a facet built from
   the queue with per-option counts;
9. free-text **search** over a large joined, lowercased per-item string.

Then **order**: "Newest first" (the queue's own order) or "Analyzer
evidence first" (`reviewTriageSortRank`, then descending confidence, as a
*stable* sort so ties stay newest-first).

### B.4 Reviewed / history behaviour

`GET /api/review-queue?include_reviewed=true` on mount, so the whole
reviewed history was in memory before the user touched anything. The
Reviewed tab then filtered that download. Cards there read
`Reviewed: <label>` from `reviewed_label`.

### B.5 Count semantics

Every one of these was computed client-side over the **whole** downloaded
queue, and every one is presented as a total:

- per-tab counts on the tab chips;
- `pendingReviewCount`;
- the triage-filter counts on the advanced chips;
- the source/stream facet counts;
- `"N showing / M total"` and `"Showing N of M review items"`;
- `"N selected / M eligible"` and `"M visible eligible"`;
- `"N selected / M visible unresolved Visits"` (species-suggestion batch);
- `Page X of Y · N matching Visits`.

### B.6 Ordering

`_review_queue_items` sorts by `(event.started_at, item.id)` descending --
newest first, deterministic, ties broken by id. Client paging was
`filteredItems.slice()` at `PRODUCT_REVIEW_PAGE_SIZE = 25`.

### B.7 Correction / undo / reopen behaviour

Confirm, correct, false positive, bulk correct, skip, reopen, undo,
suggestion reject, proposal reject, identification assist, and the species
suggestion batch. **Every one of them re-downloaded the entire queue with
`include_reviewed=true` afterwards.** Fast Review additionally kept its own
bounded 200-item snapshot for `navigateFastReviewQueue`, and re-downloaded
the whole queue on save, on undo, and after the identification assistant.

### B.8 Demo-source handling

`GET /api/review-queue` excludes `is_demo_source` items at the HTTP
boundary (Native-Windows & Packaging Acceptance v1), while the repository's
own `review_queue_items` deliberately still returns them flagged, for
internal consumers. A demo Source repurposed into a real camera stops being
demo, decided from its effective provider row rather than its frozen
`kind`.

### B.9 The app shell's own read

`App.tsx` additionally called `apiClient.getReviewQueue()` (unbounded, no
reviewed history) on **every** page load, and passed the result to three
places: the Review Queue page's initial snapshot, StreamsPage's per-Stream
"N needs review", and StreamDetailPage's per-Stream count plus a five-card
preview panel.

---

## C. Root cause

Two distinct causes, and the P0 needed both fixed.

**C.1 The response was the whole queue.** `GET /api/review-queue` returns
every member, each as a fully hydrated review card: identification summary,
evidence frames, media asset, focus-crop resolution, effective-primary
preview, review state token. At Profile B that is ~7.2 KB per item; the
page asked for reviewed history too, so 2,813 items and 20.4 MB.

**C.2 The request scaled with history even without the response.** This is
why bounding the response alone would not have been enough, and it is the
part that had to be fixed first. Server-side tabs, filters and counts need
*every* member classified, so a bounded page still needs one pass over the
queue. After the prior milestone's own prefetch, that pass -- a detail-free
build -- still issued **almost exactly three statements per member**, and
always the same three:

1. the newest *pending* `SpeciesSuggestionModel` for the Visit;
2. its `MotionEvidenceModel`, via `_motion_evidence_for_review_queue_item`;
3. the `MediaAssetModel` behind `Visit.representative_media_path`.

Measured on the real Profile B database: 5.22 s and **8,505 statements**
just to classify 2,813 members.

Two smaller contributors were found and fixed in the same pass:
`_zone_context` built a complete `Zone` schema (polygon, schedule,
suppression fields) **per item** for the same handful of Zones -- 14% of
the classification pass -- and `_review_focus_crop_context` read its Zone
with a bare `session.get` rather than the build cache, one statement per
displayed card.

**C.3 The correction loop.** `navigate_fast_review_queue`, which runs after
*every* Fast Review correction, built a full review card for every
unresolved item purely to decide which one was next.

---

## D. API design

Two new read endpoints. `GET /api/review-queue` is **unchanged** and still
returns the whole queue -- it stays as the stable list-everything API shape
for external/offline callers and this repository's own contract tests -- but
no product surface reads it any more.

### `GET /api/review-queue/page` -> `ReviewQueuePage`

Limit + offset, not a cursor: the accepted UI already has a numbered
`Page X of Y` control with Previous/Next, the queue's order is
deterministic and total (`(started_at, id)` descending), and offset paging
is what that control means. No new pagination framework.

Query parameters, each corresponding one-to-one to a control the page
already had -- nothing new is filterable:

| Parameter | Default | Corresponds to |
|---|---|---|
| `tab` | `animals` | the product tab (plus `all`, which has no tab counterpart and exists for the Streams surfaces) |
| `show_legacy_and_test_activity` | `false` | "Show sample and older activity" |
| `status` | `unreviewed` | the Status control |
| `triage` | `all` | the advanced evidence group |
| `evidence` | `all` | the evidence filter |
| `target` | `all` | the type filter |
| `source_stream` | `all` | the source/stream facet |
| `search` | `""` | the search box |
| `sort` | `newest` | "Review order" |
| `page` / `page_size` | `0` / `25` (max 100) | the pager |
| `stream_id` | none | the Streams surfaces' own scoping |
| `scoped_target_ids` | none | the cross-screen hand-off scope |
| `skipped_target_ids` | none | the in-session skip set |
| `include_eligible_target_ids` | `false` | "Select visible eligible" (§F.3) |

Response: `items` (bounded by `page_size`), `page`, `page_size`,
`page_count`, `total_items`, `matching_items`, `eligible_matching_items`,
`species_suggestion_matching_items`, `needs_review_items`,
`pending_review_count`, `tab_counts`, `triage_counts`,
`source_stream_options`, `matching_suggested_labels`,
`eligible_suggested_labels`, an optional `eligible_target_ids`,
`fast_review_targets` (bounded at 200) and `fast_review_stream_id`.

Guarantees, each asserted as a test (§L):

- **bounded default page size** (25; hard ceiling 100, `422` above it);
- **deterministic ordering** -- the queue's own order, and the triage sort
  is stable within equal rank so ties keep it;
- **no duplicates between pages and nothing skipped** -- traversing every
  page of a stable snapshot reproduces the single-request list exactly;
- a page past the end **clamps** to the last page rather than returning an
  empty list under a stale page number;
- filters, tabs and reviewed/unreviewed state respected server-side;
- demo items excluded exactly where the user-visible contract requires;
- **an ordinary request never hydrates the historical queue.**

### `GET /api/review-queue/summary` -> `ReviewQueueSummary`

`total_items`, `pending_review_count`, `tab_counts` and
`needs_review_by_stream` -- integers only, no review cards. This is what
the app shell needs, and it deliberately does not build the filter index at
all (it needs nothing from detection proposals, detection runs,
MotionEvidence or the taxonomy).

### Implementation shape

`review_queue_page` is two passes over one session, and only the first
touches every member:

1. a **classification** build (`include_detail=False`: no identification
   summary, no effective-primary preview, no focus-crop resolution, no
   review-state token) plus one `ReviewQueueFilterIndex`;
2. an **`only_targets`** build for the at-most-`page_size` members the page
   returns -- the identical per-item code path a full-detail build runs,
   and the same one every saved correction already goes through via
   `_review_queue_item_by_target`.

`_review_queue_items` gained `only_targets` (the existing single-target
narrowing, generalised to a set) and `detail_targets` (per-item detail) to
make that possible without a second code path for building an item.

The three per-member round trips from §C.2 are now three bulk statements in
`_preload_review_queue_item_context`, a pure prefetch in the same shape as
the prior milestone's `_preload_review_queue_rows`: each consumer falls
straight through to its own original query whenever the preload is absent
or does not hold the key, and the maps are filled, never consulted for
existence. `_pending_suggestion_outranks` is a literal transcription of the
pending-suggestion query's `ORDER BY created_at DESC, rank, id DESC`, kept
as one named function so the bulk pick and the per-Visit `.first()` cannot
drift.

**Proof that this changed nothing.** The complete queue at Profile B --
2,813 items in both detail modes, 5,626 serialized records -- is
**byte-identical before and after, same SHA-256**. That is not an argument;
it is the same bytes.

---

## E. Server-computed counts

`review_queue_filters.py` is a pure, session-free, ORM-free module whose
every function is a deliberate literal port of a named function in
`ReviewQueuePage.tsx` or `web/src/components/taxonomy.ts`, with the
TypeScript original named in its docstring:

| Python | TypeScript original |
|---|---|
| `taxonomy_key` / `format_label` | `taxonomyKey` / `formatLabel` |
| `TaxonomyIndex.find/display/is_false_positive/is_bird_review_label` | `findTaxonomyLabel` / `displayTaxonomyLabel` / `isFalsePositiveLabel` / `isBirdReviewLabel` |
| `triage_category_for_label` / `_triage_proposal` | `triageCategoryForLabel` / `triageProposal` |
| `ReviewQueueFilterIndex._proposal_evidence` / `._motion_evidence` | `reviewEvidenceProposals` (+`proposalRelationForReviewItem`) / `reviewMotionEvidenceForQueueItem` |
| `._triage` / `._search_text` / `._facts_for_item` | `reviewTriageSummary` / `reviewQueueSearchText` / `reviewItemFilterMetadata` |
| `matches_product_tab` / `matches_status_filter` / `matches_target_filter` | `matchesProductReviewTab` / `matchesStatusFilter` / `matchesTargetFilter` |
| `.matches_evidence_filter` / `.matches_source_stream_filter` / `.triage_sort_key` | `matchesEvidenceFilter` / `matchesSourceStreamFilter` / the triage comparator |
| `product_tab_counts` / `.triage_counts` / `.source_stream_options` | `productQueueCounts` / `queueCounts` / `sourceStreamFilterOptions` |
| `is_bulk_correction_eligible` / `.is_species_suggestion_batch_eligible` / `unique_label_values` | `isBulkCorrectionEligible` / `isSpeciesSuggestionBatchEligible` / `uniqueLabelValues` |

Counts are produced by counting classified items, never by hydrating review
cards to count them; `review_queue_summary` additionally skips the filter
index entirely. `_taxonomy_key` in `product_repository.py` now delegates to
this module's `taxonomy_key`, so a label cannot normalize one way for
review truth and another way for a filter or a count.

Two transcription details worth stating explicitly, because both are
faithful rather than corrected:

- `productQueueCounts`' own `else` branch means a non-Visit item whose
  `product_category` is `animal` falls into the **reviewed** bucket. That
  is what the accepted page counted, so it is what the server counts.
- `sourceStreamFilterOptions` sorts identifiers with JavaScript's
  `localeCompare`; the port sorts case-insensitively then by codepoint,
  which agrees with the browser for the ASCII identifiers these are.

**One disclosed departure.** The client's search text also included the
*identification-assistant* summary's own fields (adapter id/name/status,
setup hint, assistant focus-crop labels) and the resolved focus-crop
fields. Those exist only on a fully hydrated card -- resolving them is four
statements per item and was 46% of the old response's bytes -- so bounded
search does not resolve them for items that are only being *searched*.
Every label a user would actually search for is still covered: the Visit's
own `suggested_label`, its pending species suggestion, and each linked
detection proposal's `label` / `suggested_subject_label` /
`suggested_species`, plus every id, title, stream, source, zone, media
filename and MotionEvidence note. The affected tokens are adapter/status
metadata and crop geometry.

---

## F. Frontend integration

### F.1 The Review Queue page

`queueItems` (the whole queue) is replaced by `queuePage` (one bounded page
plus the server's whole-queue counts). Every control that used to re-filter
a downloaded queue -- tab, status, triage, evidence, source/stream, search,
order, page, the hand-off scope, the in-session skip set -- is now a
dependency of a single memoised query object, so changing any of them is
exactly one bounded request. The counts on the tab chips, the triage chips,
the facet, `N showing / M total`, `Showing N of M review items`, `N
eligible` and `Page X of Y · N matching Visits` all come from the server
and still describe the whole queue.

The client-side copies of `matchesProductReviewTab`, `matchesStatusFilter`,
`matchesTargetFilter`, `matchesEvidenceFilter`,
`matchesSourceStreamFilter`, `reviewTriageSortRank` and
`sourceStreamFilterOptions` were **deleted**, not left beside their Python
ports: two copies of the same semantics is precisely how the two would
drift. `reviewItemFilterMetadata` stays, because the ≤25 cards on screen
still render triage titles and source context from it -- it now runs over
the page rather than over the history.

### F.2 Fast Review

Fast Review only ever needed an *ordered target list* plus the one card it
is displaying: `navigateFastReviewQueue` already returned the next card
itself. It now takes the server's bounded ordered target list -- the same
200-target ceiling the panel already applied to itself, and the same
ceiling `FastReviewQueueNavigationRequest.ordered_targets` enforces -- and
the Stream it is scoped to. Starting a session prefers the card already on
the Review Queue's own page and otherwise resolves it through the same
navigation endpoint; undo and the identification assistant re-resolve their
one card the same way instead of downloading the queue to find it.

`navigate_fast_review_queue` itself now classifies the backlog and hydrates
only the Visit it returns.

### F.3 "Select visible eligible"

The count beside this button is still `eligible_matching_items` -- every
eligible item in the whole filtered set, exactly as before, not a window.
The identifiers needed to act on it are fetched on that **one click**
(`include_eligible_target_ids=true`), so the ordinary bounded load stays
bounded. `selectedBulkTargetType` records which kind was selected, because
such a selection can reach past the current page; every selected id comes
from an eligible item by construction (a page checkbox, or the server's own
eligible list), and the selection is cleared whenever the tab or any filter
changes.

### F.4 The app shell and the Streams surfaces

`App.tsx` now calls `GET /api/review-queue/summary` instead of
`getReviewQueue()`. StreamsPage reads `needs_review_by_stream` directly.
StreamDetailPage takes its count from the same map and asks for its own
Stream-scoped page of `STREAM_REVIEW_PREVIEW_COUNT` cards for the preview
panel, with "+N more waiting" computed from the whole-queue count. A live
candidate created moments earlier in the same session is newest-first and
so is inside that preview window, which is what the existing
`hasLocalLiveReviewQueueItem` check depends on.

### F.5 What did not change

No visual, copy, layout, tab, filter, ordering or truth change. The one
DOM addition is `data-target-id` on the review card `<article>`, a test
hook with no rendered effect, added so browser-level proof that two bounded
pages carry disjoint work is possible at all.

---
## G. Before measurements

### How these were produced, and why they are trustworthy

Two harnesses, both committed:

- `scripts/benchmark_release_performance.py` (the prior milestone's, extended
  here with the new Review Queue operations) -- the whole-product run, used
  to confirm nothing else regressed;
- `scripts/benchmark_review_queue_scale.py` (new) -- only the requests the
  Review Queue and the app shell actually make, so a before/after pair at
  two workload profiles is affordable. It reuses the release benchmark's own
  server, client and SQL-counting machinery rather than reimplementing them.

Both measure latency and bytes against a **real server process over real
HTTP**, and statement counts **in process** via a SQLAlchemy engine hook --
a structural measurement whose own timing is deliberately not reported.

**"Before" means the actual baseline tree**, not a reconstruction: a
`git worktree` at `73dbcd4`, measured against a byte-identical copy of the
same seeded database. The new routes correctly return `404` there, which
the harness records rather than silently skipping.

**Workloads.** `scripts/performance_workload.py`, unchanged, at the two
profiles this milestone was required to exercise:

| Profile | Shape | Visits | Media assets | Backlog |
|---|---|---:|---:|---:|
| **B** -- established home install | 90 days, 2 Streams, ~30 Visits/day, 62% reviewed | 2,811 | 11,244 | 1,093 |
| **C** -- busy period (burst/backlog) | B's shape, 6 days at 4x activity, 38% reviewed | 3,322 | 13,288 | **2,058** |

Profile C reproduces the P0's own figures exactly: **2,058 items and
14,921,425 bytes (14.9 MB)** from `GET /api/review-queue`, against the
prior report's "2,060 items, 14.9 MB", and **20,671 SQL statements**
against its 20,673.

### The numbers, at `73dbcd4`

**Profile B (2,811 Visits, 1,093-item backlog):**

| Request | Latency | Bytes | Items | SQL |
|---|---:|---:|---:|---:|
| App shell, `GET /api/review-queue` (every page load) | 4,841 ms | **7,930,944** | 1,093 | 10,994 |
| Review Queue mount, `?include_reviewed=true` (mount *and* every saved correction) | 12,296 ms | **20,397,705** | 2,811 | 28,227 |
| Fast Review "next unresolved Visit" (after every fast correction) | 4,991 ms | 114 | -- | 10,998 |

**Profile C (3,322 Visits, 2,058-item backlog):**

| Request | Latency | Bytes | Items | SQL |
|---|---:|---:|---:|---:|
| App shell, `GET /api/review-queue` | 9,009 ms | **14,921,425** | 2,058 | 20,671 |
| Review Queue mount, `?include_reviewed=true` | 14,929 ms | **24,105,224** | 3,322 | 33,353 |
| Fast Review "next unresolved Visit" | 8,959 ms | 114 | -- | 20,671 |

**On wall-clock, stated plainly.** The prior milestone published **74.4 s**
for the Profile C shell request; the same code at the same profile measured
**9.0 s** here. The difference is the machine, not the code: this machine
is shared with an unrelated bursty workload (the prior report's own §C and
§T say the same, and record a 2x+ spread across six identical runs), and
the structural facts -- 2,058 items, 14,921,425 bytes, 20,671 statements --
reproduce almost exactly. **Every latency conclusion below is therefore
drawn from a within-run comparison**, where the before-shape and the
after-shape were measured in the same process, in the same minute, against
the same database (§I, §J). Bytes and statement counts are load-independent
and need no such care.

## H. After measurements

Same harness, same databases, at `04bcf65`. "Review Queue mount" is the
**Unchecked** tab here because that is where this synthetic workload's
backlog actually sits (`performance_workload.py` writes no MotionEvidence
`detector_evidence`, so every generated Visit classifies as `unchecked`);
the Reviewed tab is shown alongside it as the other fully-hydrated page.

**Profile B:**

| Request | Latency | Bytes | Items | SQL |
|---|---:|---:|---:|---:|
| App shell, `GET /api/review-queue/summary` | 1,181 ms | **236** | -- | 98 |
| Review Queue mount, first page (Unchecked) | 1,649 ms | **194,176** | 25 | 305 |
| Review Queue, Reviewed tab, first page | 1,586 ms | 184,712 | 25 | 304 |
| Review Queue, next page | 1,442 ms | 1,036 | 0 | 98 |
| Review Queue, search | 1,543 ms | 1,036 | 0 | 101 |
| Fast Review "next unresolved Visit" | **519 ms** | 114 | -- | **57** |

**Profile C:**

| Request | Latency | Bytes | Items | SQL |
|---|---:|---:|---:|---:|
| App shell, `GET /api/review-queue/summary` | 1,416 ms | **238** | -- | 105 |
| Review Queue mount, first page (Unchecked) | 1,979 ms | **194,918** | 25 | 312 |
| Review Queue, Reviewed tab, first page | 1,866 ms | 184,675 | 25 | 316 |
| Review Queue, next page | 1,755 ms | 1,036 | 0 | 113 |
| Review Queue, search | 1,781 ms | 1,036 | 0 | 113 |
| Fast Review "next unresolved Visit" | **918 ms** | 114 | -- | **77** |

The bounded page's cost is **flat in the backlog**: B's 1,093-item backlog
and C's 2,058-item backlog produce the same 25 cards, ~194 KB, and ~305-312
statements. What still grows slightly is the O(history) classification pass
in Python (§T, P2-4), visible as 1.6 s -> 2.0 s across a 18% larger library.

## I. Profile B result

Within-run comparison -- the before-shape and the after-shape measured in
the same process, same minute, same database, so machine load cancels:

| | Before shape | After shape | Change |
|---|---:|---:|---|
| **Review Queue mount, latency** | 10,001 ms | 1,649 ms | **-84%** |
| **Review Queue mount, bytes** | 20,397,705 | 194,176 | **-99.0%** (105x) |
| **Review Queue mount, items** | 2,811 | 25 | bounded by page size |
| **Review Queue mount, SQL** | 19,808 | 305 | **-98.5%** |
| **App shell, latency** | 3,847 ms | 1,181 ms | **-69%** |
| **App shell, bytes** | 7,930,944 | 236 | **-99.997%** |
| **App shell, SQL** | 7,722 | 98 | **-98.7%** |
| **Fast Review navigate, latency** | 4,991 ms (baseline) | 519 ms | **-90%** |
| **Fast Review navigate, SQL** | 10,998 (baseline) | 57 | **-99.5%** |

Against the true baseline tree rather than the same-run shapes, the mount
was 12,296 ms / 20.4 MB / 28,227 statements, so the improvement is larger
still; the within-run figures above are the conservative ones.

Whole-product run at Profile B confirms nothing else regressed: Dashboard
1,246 ms (was 2.22 s at the prior milestone's close), Activity Library
92-144 ms including a deep page, Camera/Stream status 1.4 ms, alerts 3.0 ms.
The still-unbounded surfaces are unchanged and still open (§T):
`GET /api/media` 11.9 MB, `/api/species-suggestions` 1.50 MB,
`/api/detection-proposals` 1.40 MB.

## J. Burst / backlog result

Profile C is the profile the P0 was written from -- an ordinary three-month
library with one burst week and an owner who has fallen behind, 2,058 items
waiting.

| | Before shape | After shape | Change |
|---|---:|---:|---|
| **Review Queue mount, latency** | 12,000 ms | 1,979 ms | **-84%** |
| **Review Queue mount, bytes** | 24,105,224 | 194,918 | **-99.2%** (124x) |
| **Review Queue mount, items** | 3,322 | 25 | bounded by page size |
| **Review Queue mount, SQL** | 23,400 | 312 | **-98.7%** |
| **App shell, latency** | 7,639 ms | 1,416 ms | **-81%** |
| **App shell, bytes** | **14,921,425** | **238** | **-99.998%** |
| **App shell, SQL** | 14,509 | 105 | **-99.3%** |
| **Fast Review navigate, latency** | 8,959 ms (baseline) | 918 ms | **-90%** |
| **Fast Review navigate, SQL** | 20,671 (baseline) | 77 | **-99.6%** |

**Against the acceptance criteria, which are not millisecond targets:**

| Requirement | Result |
|---|---|
| Initial Review Queue load is bounded | **Yes.** 25 cards, ~195 KB, ~312 statements, at both profiles |
| Payload bounded by requested page size rather than total history | **Yes.** 194,176 B at a 1,093-item backlog and 194,918 B at a 2,058-item backlog -- a 0.4% difference against an 88% larger backlog. Asserted structurally in §L (10x the history must not move the response by more than 64 bytes) |
| Latency usable at the tested realistic backlog | **Yes.** ~2.0 s at the burst profile, against 12-15 s before, on a machine that is *not* quiet. The remaining second is the O(history) classification pass, disclosed as P2-4 |
| Correction does not trigger a full-history reload | **Yes.** Every mutation refetches one bounded page (§K); Fast Review's own post-correction navigation fell from 20,671 statements to 77 |
| Loading additional pages scales incrementally | **Yes.** "Next page" is 98-113 statements and, at a tab with results, one more bounded page; it does not re-read the queue |

## K. Mutation / refetch behaviour

Before, **every** saved mutation re-downloaded the whole queue with
`include_reviewed=true`: confirm, correct, false positive, bulk correct,
skip, reopen, undo, suggestion reject, proposal reject, identification
assist, and the species-suggestion batch -- eleven call sites, plus two
more inside Fast Review and one after the identification assistant.

After, each of them performs exactly one bounded refetch of the current
page and its counts (`refreshQueuePage`, which reuses the live query
through a ref so it cannot drift from what is on screen). Nothing reloads
history.

| Action | Before | After |
|---|---|---|
| Confirm / correct / false positive | whole queue + history | current page + counts |
| Bulk correct | whole queue + history | current page + counts (`needs_review_items` supplies the "N still need review" summary line) |
| Skip | client-only (but re-filtered the whole download) | current page + counts, with the skip set sent as a bounded parameter |
| Reopen | whole queue + history | current page + counts |
| Fast Review save / undo | whole queue + history | current page + counts, plus one single-target card resolution |
| Suggestion / proposal reject | whole queue + history | current page + counts |
| Identification assist | whole queue + history | current page + counts, plus one single-target card resolution |
| Species-suggestion batch | whole queue + history | current page + counts |

Counts remain correct after every one of them because they are recomputed
server-side over the whole visible queue, not adjusted client-side.
`test_correction_moves_the_item_and_updates_counts` and
`test_reopen_restores_the_item_to_its_pending_tab` assert the count
transitions directly, and the browser test asserts them on the rendered
chips.

Two smaller details that matter for correctness rather than speed:

- **Out-of-order responses.** A queue request is a real round trip at a
  real backlog, so two can be in flight at once -- change a filter while a
  post-correction refresh is running. A monotonic sequence guard means only
  the newest response may write state; a slow earlier one cannot quietly
  reinstate the previous view.
- **One request per filter change.** Returning to page 1 when a tab or
  filter changes is a render-phase adjustment rather than an effect. With
  an effect, changing a filter while on page 3 would fetch page 3 of the
  new result set and only then fetch page 1 -- two bounded requests where
  one will do.

## L. Tier 1

`tests/test_review_queue_page_scale.py` -- **28 tests, all passing**, one
new file covering every item §8 of the brief names:

| Requirement | Test |
|---|---|
| first page | `test_first_page_is_bounded_and_reports_whole_queue_totals` |
| next page | `test_paging_covers_every_item_exactly_once` |
| stable ordering | `test_page_order_matches_the_unbounded_queue_order` (also asserts the paged sequence equals the unbounded endpoint's own order, and that repeating a request returns the same window) |
| no duplicate items | `test_paging_covers_every_item_exactly_once` (57 items, 6 pages, `len(set(...)) == 57`) |
| no skipped items | same test -- traversing every page reproduces the single-request list exactly |
| tab counts | `test_tab_counts_and_scoping_match_the_accepted_tab_definitions` (one item per tab, each landing where the accepted definition puts it) |
| reviewed count | `test_reviewed_tab_is_served_lazily_and_ignores_the_status_control` |
| filters | `test_triage_counts_and_filter`, `test_source_stream_facet_counts_the_whole_queue`, `test_search_matches_the_same_text_the_page_searched`, `test_scoped_and_skipped_targets`, `test_sort_by_triage_is_stable_within_equal_rank` |
| demo exclusion | `test_demo_source_activity_is_excluded_and_a_repurposed_source_is_not` |
| real items included | `test_real_activity_appears_alongside_the_seeded_demo_source` |
| repurposed demo Source | same test as demo exclusion, via the established `de_demo_seeded_source` helper |
| mutation changes counts correctly | `test_correction_moves_the_item_and_updates_counts` (and asserts the page's counts and the shell's summary agree) |
| correction removes/moves the expected item | same test -- gone from Animals, present in Reviewed |
| undo/reopen restores expected state | `test_reopen_restores_the_item_to_its_pending_tab`, which takes the `review_state_token` from the bounded Reviewed page, proving a page item carries what a real mutation needs |
| empty queue | `test_empty_queue` |
| queue smaller than page size | `test_queue_smaller_than_one_page` |
| queue larger than multiple pages | `test_paging_covers_every_item_exactly_once`, `test_page_beyond_the_last_page_clamps_instead_of_returning_nothing` |

Plus the HTTP surface (`test_http_page_and_summary`,
`test_http_page_rejects_an_out_of_range_page_size`), the opt-in eligible-id
list, the bounded Fast Review target snapshot, the legacy tab's opt-in, and
Stream scoping.

**Proven RED against the unmodified baseline** where that is meaningful:
the file cannot import at `73dbcd4` at all (the schemas and the repository
method do not exist there), so equivalence was instead established by
measurement -- the complete Profile B queue is byte-identical before and
after the prefetch (§D), and §G records the baseline endpoint's own numbers
from the baseline tree.

### The performance regression test (§12 of the brief)

Two structural tests, neither depending on wall-clock:

- `test_response_and_statements_do_not_grow_with_total_history` -- ten
  times the reviewed history at an identical backlog must not move the
  response by more than **64 bytes** (only the digits in
  `tab_counts.reviewed` may change) and must not roughly double the
  statement count. Against whole-history hydration this fails immediately:
  the response would be 10x.
- `test_only_the_bounded_fast_review_snapshot_grows_with_the_backlog` --
  ten times the *backlog* (250 -> 2,500) must also stay within 64 bytes,
  because the one part that grows at all is the Fast Review target
  snapshot and it saturates at its documented 200-target ceiling.

Plus `test_payload_grows_with_page_size_not_with_history` (payload tracks
`page_size`, and a page is a small fraction of the whole queue) and
`test_summary_returns_counts_without_any_items` (under 1 KB, under 60
statements).

## M. Tier 2

Review Queue, fast review, correction, revision, imports/detection
proposals, dashboard counts and the demo-source contract -- every suite the
brief names, plus the neighbours that share this code:

`test_automatic_review_identification`, `test_candidate_visit_review_workflow`,
`test_dashboard_today`, `test_dashboard_observation_engine_truth`,
`test_demo_source_exclusion`, `test_detection_interface`, `test_fast_review`,
`test_media_import`, `test_folder_import`, `test_review_decision_provenance`,
`test_review_identification`, `test_review_provenance`,
`test_review_queue_bioclip_status_performance`,
`test_review_queue_bulk_corrections`, `test_review_queue_page_scale`,
`test_review_queue_product_mode`, `test_review_queue_scale`,
`test_review_queue_species_suggestion_batch`,
`test_reviewed_observation_revision`, `test_motion_evidence`,
`test_activity_library`.

**279 passed, 6 failed** -- and all six are in `test_dashboard_today.py`
and **reproduce identically against the unmodified baseline at `73dbcd4`**,
run from a `git worktree` of that commit with the same interpreter. They
are this file's known date-sensitive fixtures (e.g.
`assert new_labels.get("eastern_gray_squirrel") in ("new", "first_record")`
returning an empty map). Pre-existing; not attributable to this milestone.

`ruff`: byte-identical to the established baseline on every changed file --
`product_repository.py` 55 findings before and after, `api/main.py` 26
before and after, `api/schemas.py` clean before and after. Both new modules
(`review_queue_filters.py`, `benchmark_review_queue_scale.py`) and the new
test file are clean.

`npx tsc --noEmit` and `npm run build`: clean.

## N. e2e / browser evidence

`web/e2e/review-queue-bounded-page.spec.ts`, **4 tests, all passing**,
driving the real page in Chromium against a real server.

| Required proof | How it is asserted |
|---|---|
| initial page renders | 25 `article.queue-card` elements on the default Animals tab |
| counts match server truth | the Animals chip, `"N showing / M total"` and `"Page 1 of Y · N matching Visits"` are compared against an independently-fetched `GET /api/review-queue/page` for the same view -- not against a fixture number |
| item review works | "False positive" on the first card; the Animals chip drops by one, the corrected card is gone from the list, and `GET /api/review-queue/summary` confirms the move |
| next batch/page can be reached | "Next" renders the server's own page 1, `data-target-id` by `data-target-id`, in its order |
| no duplicates between pages | page 2's ids are disjoint from page 1's and internally unique |
| Reviewed/history works | the Reviewed tab is not part of the initial load; opening it issues `tab=reviewed` and renders the card as `Reviewed: Blue Jay` |
| filters work | the search box issues `search=...` and the disclosure follows it to `0 showing / M total`, then recovers |
| correcting keeps the page coherent | the page refills to 25 cards rather than leaving a hole, and the pager's total drops by one |
| **no full-history payload after each action** | a `page.on("request")` listener classifies every `/api/review-queue...` request; `/api/review-queue` exactly (with or without `include_reviewed`) is the unbounded shape, and **zero** such requests occur across mount, paging, correction, tab switches and filtering |

This spec earned its place immediately: it found the
`saveCorrectionWithLabel` refresh defect described in §F/§K, which every
unit test passed straight through because the defect lived in the chain
between two React components.

### Where this spec runs, and why

Its own instance, via `web/playwright.review-queue.config.ts` and
`npm run test:e2e:review-queue` -- the same isolation the repository
already gives `onboarding.spec.ts`, for the mirror-image reason. A spec
that must build a backlog larger than one page cannot share a database
with specs that assert on a near-empty queue; the first full-suite run
proved it by taking five neighbours down with it. `playwright.config.ts`
excludes it by name, and `global-setup.ts` now takes the instance to
bootstrap from the invoking config's own `baseURL` rather than a
hard-coded port, so a second config can reuse it safely.

### Full browser suite, and how its failures were classified

Run at this HEAD and again at the baseline `73dbcd4` (from a `git
worktree` of that commit, same machine, same session, same interpreter):

| | Failed | Passed |
|---|---:|---:|
| **Baseline `73dbcd4`** | **10** | 181 |
| **This milestone** | **9** | 182 |

**This milestone's nine are a strict subset of the baseline's ten.** The
extra baseline failure is `dataset-export-download.spec.ts`, which passed
here. **Zero browser failures attributable to this milestone.**

The nine long-standing failures:

| Spec | |
|---|---|
| `broader-wildlife-maturity-review.spec.ts` (2 tests) | pre-existing |
| `notification-preferences.spec.ts:149` | pre-existing |
| `review-queue-bulk-correct-stale-write.spec.ts:32` | pre-existing |
| `review-queue-count-demo-exclusion.spec.ts:17` | pre-existing |
| `review-queue-fast-review-keyboard.spec.ts:61` | pre-existing |
| `review-queue-reviewed-tab.spec.ts:41` | pre-existing |
| `reviewed-product-loop.spec.ts:3` | pre-existing |
| `today-report.spec.ts:1091` | pre-existing |

Most of the Review Queue ones share one root cause worth recording for
whoever fixes them, though it is outside this milestone's scope: they seed
their fixtures on the **seeded demo Stream**, whose activity Native-Windows
& Packaging Acceptance v1 made demo-excluded from the visible queue *by
design*, so their cards can no longer render at all. That is a stale test
premise, not a product defect, and it predates this work.

## O. Tier 3 -- full Core

Required, not a judgement call: this milestone changes one of the
product's central repository read paths and the page that is the review
loop.

**Run 1: 12 failed / 6,173 passed / 4 skipped / 11 xfailed (46:47).**

Every one classified, none left as "probably fine":

| Test | Classification | Evidence |
|---|---|---|
| `test_doctor_camera_node_transport.py::test_interpret_no_transport_configured_anywhere_is_pass` | pre-existing | the established set recorded in Performance / Scale / Stability Closure v1 §X |
| `test_doctor_camera_node_transport.py::test_interpret_ignores_sources_without_transport_configured` | pre-existing | same |
| `test_environmental_context.py::test_temperature_band_established_once_enough_days_are_cached` | pre-existing | same |
| `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields` | pre-existing | same (that file's own long-documented date-sensitive fixture flake) |
| `test_dashboard_today.py` (**6 tests**) | pre-existing | **reproduced identically at the baseline `73dbcd4`**, run from a `git worktree` of that commit with the same interpreter, same 6 tests, same assertions |
| `test_canonical_new_regular_species_consistency.py::test_today_and_bird_log_agree_on_new_species` | pre-existing | **reproduced identically at the baseline**, standalone: `assert None in ('new', 'first_record')` -- the same date-sensitive "is this species new today" family as the six above |
| `test_transport_worker.py::test_retryable_failure_returns_item_to_failed_retryable_and_eventually_succeeds` | full-run timing flake | **passes standalone at this HEAD and at the baseline**; a retry worker with real deadlines, touching no code path this milestone changed |

The two `test_place_biodiversity_summary_repository.py` tests from the
prior milestone's established set passed here.

**Run 2 (confirming): 12 failed / 6,173 passed / 4 skipped / 11 xfailed
(45:58).**

The same counts, and eleven of the twelve are the *same tests*. The two
runs differ by exactly one swap inside the transport family:

| Test | Run 1 | Run 2 |
|---|---|---|
| `test_transport_worker.py::test_retryable_failure_returns_item_to_failed_retryable_and_eventually_succeeds` | failed | **passed** |
| `test_camera_node_transport_acceptance.py::test_scenario_8_host_incompatibility_is_diagnosable_not_silently_lost` | passed | **failed** |

Both are classified, and neither is attributable:

- **Both pass standalone at this HEAD**, run together in 1.62 s.
- **Neither test mentions the review queue at all** -- no reference to
  `review_queue` or `/api/review-queue` anywhere in either file. They
  exercise the Camera Node transport spool and its retry worker; this
  milestone touched the review-queue read path, the filter module, two new
  read endpoints and the Review Queue page.
- **`test_camera_node_transport_acceptance.py` is an already-documented
  member of this repository's load-sensitive flake family.** UI/UX &
  First-Run Adoption v1's own Core record classified
  `test_scenario_1_ordinary_disconnect_reconnect` the same way, for the
  same reason: these tests bind a free port, start a real worker, and wait
  on 5-second deadlines.
- **Run 2's failure is provably a harness race, not a product fault.** The
  assertion that failed was
  `assert item.state in {"pending", "failed_retryable"}`, and it read
  `'transmitting'` -- the test sampled the spool item while a retry attempt
  was in flight. The same item already carried
  `last_error='transport_protocol_unsupported'`, which is precisely the
  diagnosis the test exists to prove, and the test's own comment
  acknowledges it is sampling inside a 0.5 s window
  (`assert item.attempt_count < 20  # backed off, not hot-looping in 0.5s`).
  The product did the right thing; the test looked at the wrong instant.
- This machine is shared with an unrelated bursty workload (recorded in
  §G), which is why wall-clock-sensitive tests swap places between runs and
  why every performance claim in this report is a within-run comparison.

**Zero Core failures attributable to this milestone, in both runs.**

## P. Truth / data-integrity impact

**No change to review truth, evidence, admission, or any published
meaning.** Concretely:

- **Nothing in this milestone writes.** Every new code path is a read:
  two `GET` endpoints, one filter/count module with no session and no ORM,
  and prefetches. No migration, no schema change, no new persisted field.
- **The queue itself is unchanged.** Membership, order and classification
  come from the same `_review_queue_items` build as before. The bulk
  prefetch was verified by dumping the complete Profile B queue in both
  detail modes -- 5,626 serialized records -- before and after: **the same
  SHA-256.**
- **Demo-source semantics are the accepted ones.** The bounded page and the
  summary both exclude `is_demo_source` at the same seam
  (`_visible_review_queue_items`' own rule), and a demo Source repurposed
  into a real camera stops being demo, decided from its effective provider
  row. Both are asserted as tests, including the repurposed case.
- **Measured / Inferred / Reviewed boundaries are untouched.** A species
  suggestion remains evidence; only an explicit correction creates
  reviewed truth; `ReviewQueuePage.creates_truth` and `creates_export` are
  `False` and asserted so over HTTP.
- **Counts got more trustworthy, not less.** Before, "N eligible",
  "Showing N of M" and each tab count were derived from whatever the
  browser happened to have downloaded; they are now computed over the whole
  visible queue in one place that the Streams surfaces share, so a tab
  count cannot mean one thing on the Review Queue and another on the
  Streams page.
- **The one disclosed behaviour change** is the scope of free-text search
  (§E): it no longer matches identification-assistant run metadata or
  resolved focus-crop geometry, because resolving those is exactly the
  per-item hydration that made the endpoint unbounded. Every species,
  label, id, name, zone, filename and note a user would search for is
  still matched. Nothing about which items *exist*, their order, or their
  review state depends on it.
- **No evidence is dropped and no work is discarded.** Paging returns the
  same items the single unbounded request returned, in the same order,
  with no duplicates and nothing skipped -- asserted by traversing every
  page and comparing against the single-request list.

## Q. Final HEAD / schema

| | |
|---|---|
| Branch | `main` |
| Implementation commits | `3d78f8a` (bulk preload), `9bab8f5` (bounded retrieval + counts), `04bcf65` (frontend integration), `92657ae` (browser proof + the correction refresh it found), `cd9c174` (the spec's own isolated instance), plus this report's own commit |
| **Schema** | **`v60`, unchanged** -- no table, no column, no migration |
| Version | `0.1.0`, unchanged |
| Push status | **not pushed** |

**Out of scope and untouched:** the accepted Review Queue visual design, copy
and layout; tab or product semantics; review truth behaviour; general API
pagination; any other unbounded endpoint (`/api/media`,
`/api/detection-proposals`, `/api/detection-runs`,
`/api/species-suggestions` -- all still open, §T); models and detectors;
schema; Field Validation; docs/release-engineering closure; Gate G; push.

**New files:** `src/mockingbird/repository/review_queue_filters.py`,
`tests/test_review_queue_page_scale.py`,
`web/e2e/review-queue-bounded-page.spec.ts`,
`scripts/benchmark_review_queue_scale.py`, and this report.

## R. Protected-file state

The seven preserved untracked detector files were SHA-256'd at session
start, before any edit, and re-verified at every commit boundary and at
close. **All seven present, untracked, and byte-identical throughout.**
None was edited, staged, renamed or removed.

| File | SHA-256 (first 16) |
|---|---|
| `docs/wildlife-detector-training-contract.md.orig` | `63f9e5ba142069da` |
| `scripts/evaluate_small_bird_detector.py` | `81cdff0423f12112` |
| `scripts/materialize_wildlife_stage2.py.orig` | `ade97d9d46f44661` |
| `scripts/train_wildlife_stage2_rfdetr.py.orig` | `a24aa6e294c04df1` |
| `src/mockingbird/detectors/small_bird_benchmark.py` | `e85a2315fbe1487e` |
| `src/mockingbird/training/wildlife.py.orig` | `548f0706b5498b02` |
| `tests/test_small_bird_benchmark.py` | `abad318b8df14c20` |

`uv.lock` remains untracked as it has across every recent milestone.

**Staging used explicit paths throughout** -- every `git add` in this
session named the exact files, never `git add -A` and never a directory
pattern, per this repository's standing rule after the 2026-09-22 incident
in which `git add -A src tests` staged three of these files.

For the baseline comparisons in §G a `git worktree` was created at
`73dbcd4` under this session's scratchpad directory, outside the
repository working tree. It was used read-only apart from copying this
milestone's own two benchmark scripts into it, and removed at close; the
main working tree was never checked out to a different commit.

## S. Push status

**Not pushed.** No `git push` was run, no remote was contacted, no branch
or tag was published. Explicit authorization is required and was not given.

## T. Remaining Performance / Scale / Stability blockers

### Closed by this milestone

**P0-4 -- `GET /api/review-queue` is unbounded.** Closed. The Review Queue
page and the app shell now read bounded, server-counted endpoints; the
unbounded shape remains available as an API but is not on any product
path, and two structural tests fail if the page ever returns to
whole-history hydration (§L).

### Still open, carried forward unchanged

These were open before this milestone, were explicitly out of its scope,
and are untouched by it.

| | Finding | Status |
|---|---|---|
| **P1-7** | `GET /api/media` returns every media asset -- **11.9 MB** at Profile B, ~47 MB at Profile D, six page consumers | **open**, unchanged |
| **P1-8** | `GET /api/detection-proposals` (1.40 MB), `/api/detection-runs` (539 KB) and `/api/species-suggestions` (1.50 MB) are unbounded at Profile B | **open**, unchanged. The Review Queue still loads the first two in full for its per-card triage context; this milestone moved the *counting* off them but did not bound the endpoints themselves, which several other pages also consume whole |
| **P2-1** | Bird Log journal ~5.8 s at Profile B (19,728 statements; per-Visit reads across the whole history) | **open**. The batch-preload pattern this milestone applied to the queue build is the same fix, and is now demonstrated twice |
| **P2-2** | Dataset coverage / quality ~3.1 s / ~3.8 s at Profile B | **open**, same residual pattern |
| **P2-3** | `dashboard_summary` builds a review-queue classification to populate three fields no screen renders | **open**; measurably cheaper now (§G) but the fields' semantics are still what would have to change to remove the pass |

### New, found by this milestone

| | Finding | Status |
|---|---|---|
| **P2-4** | The bounded page's own classification pass is still O(total history) in *Python*, not in queries: a handful of statements, but one `ReviewQueueItem` (and its evidence frames) constructed per queue member. That is what keeps the bounded page at roughly a second at Profile B rather than tens of milliseconds | **open, not release-blocking.** It is bounded, predictable, and an order of magnitude below the release requirement; closing it means a lighter-than-`include_detail=False` projection, which would change what `dashboard_summary`'s published `actionable_animal_visits` field carries -- not a change to make inside a milestone scoped to "change data access, not product meaning" |

### Carried forward from earlier milestones, outside this scope

A live, fresh **Camera Node pairing proof** against the shared reference Pi
(Lane G / Lane R), and the **Doctor media-integrity relative-path**
behaviour recorded in earlier audit notes. Neither is in this milestone's
scope and neither was touched.

### Not authorized, not started

Field Validation Closure, docs/release-engineering closure, Gate G, and
push. This milestone does not authorize itself, any successor, or any of
the open items above.

