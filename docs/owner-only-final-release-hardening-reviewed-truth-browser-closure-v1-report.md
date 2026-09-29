# Owner-Only Final Release Hardening -- Reviewed-Truth Browser Closure v1 -- Report

**Date:** 2026-09-29. **Start:** record HEAD `b47c5bd` (candidate source
`215069b`, `0.1.0`, schema `v61`). **Authorized by:** ChatGPT global
sequencing, after Owner-Only Release Polish & Acceptance v1 was accepted at
classification A. **Classification: B.** Both target specs are closed.
The complete shared browser suite is **not** green: 7 other failures remain
that also fail, identically, on the untouched baseline. The owner decided
to close at the two target specs and disclose those 7 (§5).

## 1. Task packet

- **Roadmap phase:** Feature freeze, owner-only pre-release acceptance
  before Final Release Hardening (Lane S). Gate G stays **waived, not
  passed**. The owner is the sole pre-release tester.
- **Product flow:** Confirm -> Remember. A human correction becomes
  Reviewed truth and must read the same way in Review Queue, Bird Log and
  the reviewed-only export.
- **Why next:** these were the two browser failures recorded against
  candidate `215069b`.
- **Files allowed:** the two specs. Product code only if a reproduced
  defect required it. None did.
- **Non-goals:** features, reopening O-1/O-2, Pi or Camera Node work,
  Gate G, signing, publishing, pushing, detector or identification policy.
- **Validation tier:** test-only change, so affected-subsystem validation
  (see §4 for why Core was not run).

## 2. Reproduction (red, before any change)

Both specs were run alone in a fresh, isolated instance (`run-playwright.mjs`,
new temporary database) with a freshly built `web/dist`:

| Spec | Exact failure |
|---|---|
| `review-queue-reviewed-tab.spec.ts` | `getByRole('button', { name: /^Reviewed/ })`: element(s) not found (line 50) |
| `reviewed-product-loop.spec.ts` | `article.queue-card` filtered by heading "Review bird visit": expected 1, received 0 (line 52) |

In both page snapshots, Review Queue read **"Nothing to review yet"**, with
no group tabs and only a collapsed "Reviewed history" panel.
`GET /api/review-queue/page?tab=reviewed` on a fresh instance returned
`total_items: 0` and every tab count 0.

## 3. Root causes

Both specs fail because of **stale test assumptions**, not product
defects.

**Shared cause: demo-Stream fixtures.** Both specs seeded data onto the
seeded demo Source:

- `review-queue-reviewed-tab` imported onto `stream-backyard-feeder`.
- `reviewed-product-loop` attached its suggestion to the demo Visit
  `visit-bird-feeder-001`.

Under accepted contract, demo-Source activity is excluded from the Review
Queue so that seed data never reads as the user's own record. The contract
comes from Native-Windows & Packaging Acceptance v1, Review Queue Count
Truth Consistency v1 (`2923afb`) and UI/UX & First-Run Adoption v1.
`ProductRepository._review_queue_visible_classification` drops
`is_demo_source` items, so `total_items` is 0. The page therefore shows its
empty state instead of the tab bar (`queueItemCount === 0`), and neither
spec can reach its subject. Bird Log and the exports apply the same demo
exclusion.

Three sibling specs already encode this contract explicitly with a real
`POST /api/sources` fixture:

- `review-queue-count-demo-exclusion`
- `review-queue-fast-review-keyboard`
- `review-queue-bounded-page`

**`reviewed-product-loop` only: removed markup.** The spec also expected an
inline "Review bird visit" correction card with an "Optional
identification assist" prefill and a "Resolve species" button. That markup
is no longer reachable, because `ReviewQueuePage` hardcodes
`productMode = true`. This was diagnosed on 2026-08-27 and disclosed, not
fixed. Today a `ProductReviewCard` shows the suggestion as "Evidence only.",
and its **Review** action opens Visit Detail. On Visit Detail, the
Identification Assistant offers each ranked alternative, "Use suggestion"
prefills the form, and "Confirm species" saves. Bird Log no longer has an
"Export reviewed data" button, so Dataset Exports is reached directly.

**No product defect was found on this path.** The Reviewed tab's exemption
from the Status filter
(`_review_queue_item_matches`: `request.tab is not ReviewQueueProductTab.reviewed`)
is intact, and a correction propagates coherently (§4).

## 4. Correction and evidence

**Change** (`b946932`): the two spec files only. No product, backend,
fixture-data or configuration change.

- **`review-queue-reviewed-tab`:** creates a real Source/Stream, then
  imports and confirms onto it.
  - Its assertions are unchanged, except that the "Reviewed: Blue Jay" card
    is now located by the spec's own `data-target-id`. This makes the check
    stricter, not weaker: the original matched any Blue Jay card by text,
    which a shared instance can supply several of.
- **`reviewed-product-loop`:** real Source, Stream and Zone "Feeder", an
  imported bird photo, and the same ranked BioCLIP 2 suggestion (rank 1
  Northern Cardinal, rank 2 Blue Jay). It keeps every original claim,
  moved onto today's path, and adds four truth-boundary checks.
  - **Review Queue:** the card shows the suggestion and "Evidence only.".
    The Visit is still `needs_review`, with no reviewed label.
  - **Visit Detail:** rank 2 "Use suggestion" only prefills the form, and
    the Visit is still `needs_review`. "Confirm species" then saves.
  - **Truth:**
    - The suggestion status becomes `accepted`.
    - The Visit is reviewed as `blue_jay`.
    - The ReviewLabel is `review_origin: human` and `is_authoritative: true`.
  - **Review Queue after the correction:** the Visit is gone from the
    waiting groups. The Reviewed tab shows "Reviewed: Blue Jay" and not
    Northern Cardinal.
  - **Bird Log:**
    - The Blue Jay species card is present.
    - Its history, filtered to this camera, holds exactly one "Confirmed"
      observation: `<Source> · <Stream> · Feeder`.
    - The journal for this camera is exactly `[["blue_jay", 1]]`.
  - **Export:** the manifest record is Blue Jay (not Northern Cardinal),
    with this Source and Stream, "Feeder (Feeder)", "Reviewed" and "Ready
    for local dataset export".

**Mutation check** (proof that the specs still guard the regression they
exist for):

- The Reviewed tab's Status-filter exemption was removed temporarily in
  `product_repository.py`. **Both** specs went red, at
  `cards.first()` visible and at the Reviewed-tab card count.
- The file was then restored. `git diff src/` was empty.

**Isolation and repetition:**

| Run | Result |
|---|---|
| Each spec alone, 3 separate fresh instances | 3/3 and 3/3 |
| Both specs, `--repeat-each=30`, one shared instance (60 runs; over 25 reviewed items, so past the page size) | **60 passed** |

A first draft asserted globally unique Blue Jay counts ("1 reviewed
observation", "Seen on 1 camera") and failed under repetition. That was
the draft's own accumulation bug, fixed by scoping to the spec's own
camera. It is recorded here so the scoping is understood as deliberate.

**Complete shared browser suite** (`npm run test:e2e`: build, then 194
tests on one instance):

| Source | Passed | Failed |
|---|---|---|
| Baseline: the two original specs restored from `b47c5bd` | 185 | 9 |
| After `b946932` | **187** | **7** |

The delta is exactly the two target specs. The other 7 failures are
identical in both runs. There are **zero new failures**, and nothing is
quarantined or skipped.

**Frontend:**

- `tsc --noEmit` is clean and `vite build` is clean.
- The project's `tsconfig` covers `src` only, not `e2e/`. A strict ad-hoc
  check of the two specs shows only the `Buffer`/no-`@types/node` error
  that the original specs also had.

**Backend and Core were not run.** No API, repository, review, export or
truth-propagation code changed. `git diff 215069b` touches only `docs/` and
`web/e2e/`. The e2e specs are not part of any runtime path. This is the
concrete justification for using affected-subsystem validation.

## 5. Remaining failures (disclosed, not fixed; owner decision)

All 7 fail identically on the untouched baseline. Each was also run in its
own fresh instance:

| Spec / test | Fresh instance | Probable class |
|---|---|---|
| `review-queue-count-demo-exclusion` | passes | shared-instance accumulation (asserts one card in Animals) |
| `review-queue-fast-review-keyboard` | passes | shared-instance accumulation |
| `today-report`, "quiet, intentional empty state" | passes | shared-instance accumulation (other specs create wildlife today) |
| `broader-wildlife-maturity-review` x2 (Fast Review Unknown animal; false-positive toast) | **fails** | likely the same demo-Stream fixture cause (seeds `stream-backyard-feeder`); not root-caused |
| `review-queue-bulk-correct-stale-write` | **fails** | likely the same demo-Stream fixture cause; not root-caused |
| `notification-preferences`, insight alert opens Place Story scoped to wildlife | **fails** | long-documented Lane D gap (first disclosed 2026-09-09) |

**About the brief's "82/82" target.** The prior report's "13 specs, 82
tests" was a subset of the suite, and that report did not say which specs
it included. The complete default suite is 194 tests. Three more configs
run separately: onboarding, review-queue bounded page and bounded media.
They were not rerun here, because nothing they exercise changed.

These 7 are a named candidate follow-up. They are **not** authorized by
this closure.

## 6. Other finding (disclosed, not fixed)

On the Review Queue, the collapsed **"Reviewed history"** panel
(`CorrectionAuditPanel`) lists every ReviewLabel from `GET
/api/review-labels`, including demo-seed labels. On a fresh instance that
endpoint returns the seeded `review-label-squirrel-001` label
(`imported_curated`, `mockingbird_demo_seed_data`). The red snapshots show
"Reviewed history · 2 reviewed", and both of those are demo-Visit labels.
The panel titles each entry "Correction truth", while the Reviewed tab,
Bird Log and exports correctly exclude demo data.

This is a presentation inconsistency. It is not a truth write: nothing is
promoted, and Bird Log and exports are unaffected. It is not a cause of
either target failure, and fixing it is outside "exactly these two". It
belongs with the demo-leak family that UI/UX & First-Run Adoption v1
closed at other seams.

## 7. Artifact consequences

**None.** Candidate source `215069b` and its private Windows ZIP
`d1050b99…` (build `85b92328bb185cba`) remain the valid candidate:

- No packaged input changed, because `git diff 215069b` touches only
  `docs/` and `web/e2e/`.
- `build_local_product.py` explicitly excludes `e2e/` from the frontend
  fingerprint.
- Nothing was rebuilt and no native-Windows rerun was made. Either would
  have been ceremony.

## 8. Boundaries kept

- No product code, schema, model, threshold, detector or identification
  policy change.
- No Pi or Camera Node work, and Gate G was not touched.
- Nothing was pushed, tagged, signed, published or uploaded.
- The seven protected untracked files and `uv.lock` were untouched: never
  read or written, and their mtimes are unchanged.
- A throwaway probe directory (`web/.probe-tmp/`) was used for API probing
  and has been deleted.

## 9. Classification

**B.** Both target specs are root-caused, corrected without weakening an
assertion, and robust under repetition. The Reviewed tab, Review Queue,
Bird Log and export reviewed-truth path is proven coherent in a real
browser. The mission's complete-suite-green target was not met because of
7 failures that predate this milestone and were outside its brief. The
owner chose to close here. **Authorization returns to NONE.**
