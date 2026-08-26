# Mobile & Remote Experience v1 — Your Observatory Away From the Desk

## Identity

- **Starting HEAD:** `2a83527` (verified exactly against the milestone brief's expected HEAD before any edit; branch `main`; working tree held exactly the seven preserved untracked detector files, confirmed at start)
- **Implementation HEAD:** `b7a786d` — "Mobile & Remote Experience v1: Your Observatory Away From the Desk"
- **Reconciliation HEAD:** the commit immediately following this file's own addition (this file + `release-execution-state.md` + `roadmap.md`), matching the established two-commit pattern from every prior milestone
- **Schema:** v55 → v55, **unchanged**. Nothing in this milestone touches persisted data shape — the Phase 0 fix corrects computation logic over already-stored facts; the new `GET /api/product/connection` endpoint reads process-launch state (`app.state`, set once at startup), never the database.
- **Commits:** `b7a786d` (implementation) + the reconciliation commit containing this file
- **Push state:** local accepted state only; not pushed (no push authorized this session)

## Bounded existing defect fix (Phase 0)

**Reproduction.** `place_change_summary._presence_status` (the shared per-taxon/Place-wide comparison primitive behind Today, Bird Log, and Place Story's regularity wording) had a guard —
`if reference_presence_days < MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON: return "no_supported_change"` — that fired for *every* input with zero reference-window presence, regardless of how much recent presence existed. A focused RED test (`tests/test_place_change_summary.py::test_zero_reference_presence_with_real_recent_run_is_higher_recent_presence`) reproduced this precisely: 7-of-7 recent presence days against 0-of-14 reference days — an established taxon, entirely absent for the whole reference window, then reappearing — returned `"no_supported_change"` instead of `"higher_recent_presence"`. This made `regularity_narrative.compute_regularity_narrative`'s own documented `"returned_after_absence"` branch structurally unreachable through Today/Bird Log's direct composition (`product_repository.py`), matching exactly what `place_story.py`'s own module docstring had already found and locally worked around (`_effective_regularity_state`) without patching the shared primitive.

**Root cause and the smallest correct fix.** The guard conflated two different questions: "was this taxon ever seen in the reference window" (correctly `no_supported_change` — the `historical_baseline` "new"/"first_record" case) and "is recent presence too thin to mean anything" (already governed by the existing `MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE` floor used by every other input). The fix narrows the guard to only fire when *both* are true:

```python
if (
    reference_presence_days < MIN_REFERENCE_PRESENCE_DAYS_FOR_COMPARISON
    and recent_presence_days < MIN_ABSOLUTE_PRESENCE_DAY_DIFFERENCE
):
    return "no_supported_change"
```

When recent presence clears the existing floor, the function falls through to its already-correct, unmodified rate/absolute-difference math — no new threshold, no new constant.

**A second, deeper defect this surfaced.** The naive one-line fix alone would have introduced a *real* regression: a taxon merely young (its own reference window predates its first-ever existence at this Place) would now be misclassified `"returned_after_absence"` on Today/Bird Log's direct path, exactly the false positive `place_story.py`'s own `_effective_regularity_state` had separately discovered and guarded against — but only for Place Story's own checkpoint scan, not for Today/Bird Log. Verified directly: `historical_baseline.compute_species_historical_statuses`'s `"new"` status is scoped to the exact report period a taxon was first confirmed (`period_start_at <= first_confirmed_at < period_end_at`), not a rolling window — a taxon a week past its debut is already `"seen_before"`/`"regular"`, with no protection against this at the `regularity_narrative` layer. The complete fix therefore also:

- Added two optional keyword parameters to `regularity_narrative.compute_regularity_narrative` (`first_confirmed_at`, `reference_window_start_at`) that, when both are supplied, gate `"returned_after_absence"` on the taxon's own first confirmation genuinely predating the reference window — ported from `place_story._effective_regularity_state`'s own `(d)` guard, now shared rather than duplicated. Omitted (the default, and every pre-existing caller/test), the original ungated behavior is preserved exactly — additive, never a narrower default.
- Updated both real callers — `product_repository.py` (Today/Bird Log) and `place_story.py` — to pass real timing context they already had in scope.
- Removed `place_story._effective_regularity_state` as fully superseded (not merely redundant-but-left-in): its own two composition tests (`test_returned_after_absence_detected_after_a_genuine_gap`, `test_returned_after_absence_not_claimed_for_a_brand_new_taxon`) re-run unchanged and green, proving the identical protection now lives one layer down, shared.
- Corrected the stale "Threshold policy" prose in `place_change_summary.py`'s own module docstring and `docs/meaningful-change-detection-contract.md`, which had explicitly (and, it turned out, over-broadly) documented "zero reference presence always reads `no_supported_change`... regardless of how much recent presence exists" as settled policy.

**Consistency proof.** Today/Bird Log and Place Story now reach `"returned_after_absence"` through the *same* shared decision (`compute_regularity_narrative`), not two independently-maintained implementations of the same protection. Two sibling tests elsewhere (`test_place_change_summary.py`/`test_place_change_summary_repository.py`'s `test_provisional_suggestion_does_not_change_status`) had their final `.status` assertion updated from the same stale `"no_supported_change"` expectation to `"higher_recent_presence"` — their actual claim (a provisional suggestion never contributes a reference presence day) is unaffected and re-verified unchanged.

**Validation.** 138 tests pass across the six directly touched/added test files (`test_place_change_summary.py`, `test_regularity_narrative.py`, `test_place_story.py`, `test_place_change_summary_repository.py`, `test_windows_launcher_instance_identity.py`, `test_cors_security.py`, verified together in one combined run) — 20 genuinely new test functions (2 for the Phase 0 RED→GREEN proof, 5 covering the new timing-guard parameters explicitly, 9 for the new `/api/product/connection` endpoint, 4 for CORS) plus 2 pre-existing tests corrected to match the fixed behavior (their actual claims unaffected, see "Consistency proof" below), plus `test_place_story.py`'s own two composition tests re-confirmed unchanged. `ruff check` clean (0 new findings on every touched file; the 57 pre-existing findings elsewhere in `product_repository.py` reproduce identically on a clean-baseline `git stash` bisection). Full Core gate re-run below.

## Mobile archaeology (Phase 1)

Real, screenshot-grounded evidence — not assumed from CSS — via a new Playwright spec (`web/e2e/mobile-viewport-audit.spec.ts`, `devices["Pixel 7"]` emulation, 412×839 CSS px) against a real isolated dev instance with real seeded/imported Visits. Every surface below passed an automated `document.documentElement.scrollWidth <= clientWidth` check; full-page screenshots were then visually reviewed.

| Surface | Before | After | Concrete finding | Severity | Fix |
|---|---|---|---|---|---|
| Navigation (shell) | D | A | Full ~20-item sidebar simply un-pinned and stacked, in full, *above* every page's own content at ≤980px — every navigation meant scrolling past the entire menu first | Critical | New mobile top bar + off-canvas drawer + 4-item bottom nav (Today/Story/Cameras/Review-or-Bird-Log + More), see "Navigation" below |
| Sign-in | B | A | Already clean, centered, good touch targets — confirmed via screenshot | — | none needed |
| Today (Dashboard) | B | B | Functional, correct, no overflow; long single-column scroll (inherent to genuine content volume: hero actions, highlights, prompts, biodiversity, live overview, health, recent activity) | — | none forced; content-reprioritization is a product-design decision beyond this milestone's bounded scope, recorded below |
| Visit detail | B | B | No overflow, evidence renders correctly at a real size; a long, dense single page ("giant metadata wall" — curation, species review, attached media, notes, collections, tags, identification assistant, dataset actions all stacked) | Notable | none forced this pass; progressive disclosure recorded as future work |
| Evidence gallery/viewer | B | B | Thumbnail strip and zoom viewer render correctly at phone width; lazy-loading added (see Media) | — | `loading="lazy"` |
| Review Queue | B | A | Layout itself is clean (tabs wrap sensibly, empty state is clear); default "animals" tab showed 0/6 items — a genuine **pre-existing** `product_category` classification gap unrelated to this milestone (see "Cameras / health" note below and Security/Tests) | — (layout); Notable (pre-existing data gap, documented not fixed) | layout: none needed; gap: documented |
| Bird Log | B | A | Clean species-grid cards, good thumbnails, comfortable buttons | — | none needed |
| Place Story | A | A | Already excellent — calm filters, readable journal cards, correct month grouping | — | none needed |
| Place Activity Report | B | A | Metric cards stack cleanly; the activity-by-hour bar chart renders at phone width without forcing overflow | — | none needed |
| Cameras / Streams list | C | B | Page shell clean; per-camera detail (name/health) sits behind a collapsed disclosure by default — matches "advanced detail progressive, not dumped" doctrine, but the default view is very sparse; one live-overview loading state was caught still resolving at screenshot time (not confirmed as a persistent hang — see "Cameras / health") | — | none forced this pass |
| Stream/camera detail | B | B | No overflow; correctly uses `<details>`/collapsed sections for advanced diagnostics and timing already; still a very long page (zone editor + monitoring + recent Visits + stream events all stacked) | — | none forced this pass |
| Settings (Local Data) | B | A | No overflow; very long (Database/Product Loop/Storage/Backup/Reset, now + Connection & Remote Access); every section functions correctly at phone width | — | new Connection & Remote Access card added, verified rendering |
| Users table (admin) | C | A | The *only* raw `<table>` in the frontend — 5 columns including a `<select>` + 2 buttons per row, would overflow badly at 360-390px | Notable | bounded horizontal-scroll wrapper (`.table-scroll`), not a stacked-card rebuild (one instance does not justify a generic table framework) |
| Add Camera / forms | B | B | Every input already label-wrapped (implicit association); secret fields correctly masked; one field (Node address) lacked a URL-appropriate mobile keyboard hint | Minor | `inputMode="url"` + `autoCapitalize`/`autoCorrect` off |
| Touch/pointer (Phase 11) | — | A | Only 8 `:hover` rules exist in the entire 9,900+-line stylesheet; none gate visibility/actionability (all decorative color/underline on already-visible, already-tappable elements); zero `onMouseEnter`-only interaction anywhere in `web/src` | — | none needed |
| Accessibility spot-check (Phase 12) | — | B | Only one `outline: none` in the whole stylesheet, and it's correctly paired with a `:focus-visible` replacement; new nav carries `aria-expanded`/`aria-controls`/`aria-label`, Escape-to-close with focus return | — | not a formal WCAG audit — see "Remaining opportunities" |

Full-page screenshots (10 surfaces) are preserved for this session under the scratch directory; representative findings above are drawn directly from them, not inferred.

## Mobile product contract (Phase 2)

Responsive web, not native. The daily loop verified end-to-end at phone width: open → Today → inspect a Visit → view evidence → confirm/correct (Review Queue) → back to Today → Place Story → story evidence → camera health → one Settings action → sign out/in (see "Product-shaped phone workflow," below, for the scripted proof). Advanced administration (Users table, deep diagnostics, developer tools) stays desktop-friendlier by honest, deliberate choice, not neglect — matching the brief's own explicit allowance.

## Navigation (Phase 3)

**Before:** `.sidebar` had exactly one responsive behavior below 980px — `position: static`, i.e. it un-pinned from its sticky-feeling column and rendered as an ordinary block, but *every one of ~20 nav destinations* (11 product + up to 9 "Developer tools" + context links + account menu + footer) still rendered in full, stacked directly above `<main>`. A phone user scrolled past the entire menu on every single navigation.

**After:** below a new 760px breakpoint (matching this stylesheet's own existing convention rather than inventing a number):

- A sticky **top bar** (brand + hamburger + Alerts) replaces the inline brand block.
- `.sidebar` becomes a **slide-in drawer** (`position: fixed`, `translateX`, `width: min(84vw, 320px)`), opened by the hamburger or the bottom nav's "More", closed on navigation (a `useEffect` keyed on `page`), Escape (focus returns to the hamburger), or backdrop click. The drawer content is **unchanged** — same `productNavItems`/`advancedNavItems` arrays, same role filtering — only its presentation changes.
- A fixed **bottom nav** (`<nav aria-label="Primary">`) surfaces the 4 most common destinations this archaeology confirmed matter most day-to-day: Today, Story, Cameras, and Review-if-permitted-else-Bird-Log (role-aware, reusing the existing `roleAtLeast` check) — deliberately small, per the brief's own "do not put twelve destinations into a bottom bar."

Desktop navigation (>760px) is **completely unchanged** — same DOM, same classes, verified by `tsc`/`vite build`/full e2e suite passing with zero regressions across the ~19 pre-existing spec files that exercise ordinary desktop-width navigation.

## Today (Phase 4)

Verified via screenshot: key Place status is above the fold (hero card + "Today's activity"), noteworthy highlights (Northern Cardinal, most-active window) appear early, the activity-by-hour chart never forces desktop width, no horizontal scroll anywhere. The page is long — inherent to real content volume (prompts, biodiversity, live overview, health, recent activity all genuinely present), not a layout defect; collapsing lower-priority cards behind progressive disclosure is recorded as a future opportunity rather than attempted this pass (a content-reprioritization decision, not a CSS fix).

## Visit / evidence / review (Phase 5/6)

Evidence renders at a real, legible size (not tiny); the thumbnail strip and zoom viewer both confirmed overflow-free. Review Queue's tabbed filter UI wraps cleanly, the empty state is clear and actionable, and an automated tap-target check (≥40×40px) on the confirm/save-correction button passed. Stale-write/conflict protection and review authority were not weakened anywhere in this milestone — no correction-flow code changed. Visit Detail remains a long, information-dense single page; no destructive recompression or lineage change was made to evidence anywhere.

## Story (Phase 7)

Already the strongest mobile surface in the product — confirmed, not assumed. Calm month-grouped cards, comfortable filter selects, no desktop-density squeeze. No changes needed.

## Cameras / health (Phase 8)

The per-camera "is it healthy" detail already lives behind a collapsed disclosure by default (matches "advanced details remain available progressively," not a raw-JSON dump) — genuinely correct doctrine, not a gap. Two honest, unresolved observations from live automated testing, recorded rather than silently dropped:

1. **`LiveCameraOverview` loading state.** One screenshot (Cameras list, ~635ms into a fresh page load) caught "Loading Live Camera Overview…" not yet resolved with a large blank space below it. A separate, *existing* e2e spec (`dashboard-live-camera-ownership.spec.ts`) exercises this exact component to completion successfully (21.8s), and the full suite re-run (below) shows no regression — the balance of evidence points to a fast test screenshot outrunning one async fetch rather than a persistent hang, but this was not exhaustively proven either way, and is recorded honestly as unresolved rather than asserted safe.
2. **`ReviewQueuePage`'s default "animals" tab showed 0 of 6 items**, including this session's own freshly-imported (not stale-fixture) unreviewed Visit. Root-caused precisely: `matchesProductReviewTab`'s "animals" tab requires `item.product_category === "animal"`, and neither `demo_data.py`'s seed construction nor the real `/api/media/import` path sets `product_category` in a way that satisfies it. This is independently reproducible by an *existing, unmodified* spec (`e2e/reviewed-product-loop.spec.ts`) failing identically when run alone — a genuine pre-existing product/data gap, unrelated to this milestone's own changes, confirmed via direct bisection-style isolation rather than assumed. Not fixed here (outside this milestone's bounded scope); recorded below and worth a dedicated look.

## Forms / settings (Phase 9)

Every input across `CameraSetupPage` is already label-wrapped (implicit `<label>` association, valid and accessible without needing explicit `htmlFor`/`id`), secret fields correctly use `type="password"`, and the pairing-code field already carries `autoComplete="one-time-code"`. One real, bounded gap fixed: the Node-address field lacked a URL-appropriate mobile keyboard (`inputMode="url"`, `autoCapitalize="off"`, `autoCorrect="off"` added). A broader field-by-field `inputMode`/`type` sweep across every settings form was not attempted — recorded as a future opportunity, not silently skipped.

## Tables (Phase 10)

Exactly one raw `<table>` exists in the entire frontend (`UsersPage`, admin-only, 5 columns including a role `<select>` and two action buttons per row). Deliberately wrapped in a bounded `overflow-x: auto` container rather than either (a) reflowing into cards (unjustified engineering for a single low-traffic admin surface) or (b) building a generic responsive-table framework (explicitly discouraged by the brief absent real duplication). Every column stays intact and familiar; nothing is hidden to fit width.

## Accessibility / touch behavior (Phase 11/12)

**Touch/pointer:** confirmed zero hover-only interaction anywhere — only 8 `:hover` rules total in the whole stylesheet, every one a decorative refinement on an already-visible, already-tappable element; zero `onMouseEnter`/`onMouseLeave`-driven-only affordances in `web/src`. New nav elements are all native `<button>`/`<nav>`, fully keyboard- and touch-operable by construction.

**Accessibility spot-check** (not a full WCAG audit — not claimed as one): the one existing `outline: none` in the stylesheet is correctly paired with a `:focus-visible` replacement (not a suppressed-with-nothing-in-its-place anti-pattern). New drawer/top-bar/bottom-nav markup carries `aria-expanded`, `aria-controls="primary-navigation"`, `aria-label` (localized to open/close state), and `aria-hidden` on the backdrop; Escape closes the drawer and returns focus to the toggle button. No new color-only state was introduced. Reduced-motion was not separately audited (the one new transition — the drawer's `transform` slide — is short and non-essential; not gated behind `prefers-reduced-motion` this pass, recorded below).

## PWA decision (Phase 13)

**Decision: Option A, deliberately bounded.** No `web/public/`, manifest, service worker, or icon existed anywhere in the repository before this milestone — genuinely a from-scratch build, not a refinement.

Shipped:
- `web/public/manifest.webmanifest` — name/short_name/description, `start_url`/`scope: "/"`, `display: "standalone"`, theme/background colors matching the existing brand palette, three icon sizes (192/512/512-maskable).
- Icons (192, 512, 512-maskable, apple-touch-icon 180, favicon 16/32/`.ico`) generated from the product's own existing "MB" brand mark (`.brand-mark`'s exact colors) via Pillow — no new brand asset invented, and the app itself had *no* favicon anywhere before this (a real, if minor, pre-existing gap this incidentally closes).
- `index.html`: manifest link, `theme-color`, icon links, `apple-mobile-web-app-*` meta tags.
- `web/public/sw.js`, registered only in production builds (`import.meta.env.PROD`, on `window.load`): **cache-first for `/assets/*` only** (Vite's own content-hashed bundle files — immutable by construction, since any content change produces a new URL) and **complete pass-through for everything else** — no `event.respondWith()` at all for navigations, `/api/*`, or `/health`. This is the whole safety property: the installed app can never serve stale Visits, evidence, or Today/Story data, because the worker never has the opportunity to cache any of it in the first place. No offline fallback page, no background sync, no push.

Explicitly not built: any caching of dynamic/API responses, any offline claim beyond "the static shell loads faster on a repeat visit." The in-app copy (`using-mockingbird.md`) states this plainly: installing MockingBird "does not make it work offline." This directly serves the milestone's own named goal (Phase 13) of a phone home-screen icon without a native app, while the bounded-caching design keeps the explicit "never display stale cached wildlife history as current" requirement true by construction, not by policy alone.

## LAN access (Phase 14)

**Audited, not assumed.** The Host already defaults to loopback-only (`127.0.0.1`) and requires an explicit `--host <non-loopback> --allow-network` pair to bind more broadly (`runtime.py`, pre-existing, unchanged logic) — a deliberately conservative default. Two real gaps found and closed:

1. **The `--allow-network` help text was stale**, claiming "No production authentication is provided" — written before Local Identity, Multi-User & Organization Access v1 shipped real sign-in for every `/api/*` route. Corrected to state the actual remaining caveat honestly (plain HTTP without a reverse proxy), not a fabricated auth gap.
2. **No discoverable way to learn the LAN address existed anywhere** — not in the product, not in documentation. Closed with a new authenticated endpoint, `GET /api/product/connection` (`ProductConnectionInfo`: `bind_host`, `bind_port`, `network_access_allowed`, `is_loopback_only`, `local_network_url`), a best-effort LAN-address detector (`runtime.detect_local_network_address`, the standard UDP-connect-without-sending trick, `None` on any failure — never a guessed address presented as certain), and a new **Connection & Remote Access** card on Settings showing the exact address (with copy-to-clipboard) or an honest "not enabled" state. Verified rendering correctly via the mobile screenshot audit.

`docs/using-mockingbird.md` gained two new sections ("Use MockingBird on your phone" / "Use MockingBird away from home") giving the exact, tested command (`Start MockingBird.cmd --host 0.0.0.0 --allow-network` / `./start-mockingbird.sh` equivalent — both launchers already forward extra arguments, confirmed by reading them directly) rather than vague guidance.

## Remote-access threat model (Phase 15)

Considered explicitly, against the actual architecture (not assumed):

- **Public internet exposure.** Real risk if a user manually port-forwards the Host — plain HTTP by default, no built-in TLS. Mitigated by explicit non-support (see "Support matrix") and clear documentation; not technically prevented (MockingBird cannot detect a router's own NAT/forwarding configuration).
- **Credential attacks.** Passwords are `scrypt`-hashed (real, computationally-expensive-per-guess protection) but **no active login rate-limiting/lockout exists** — confirmed by direct code inspection (`grep` for rate-limit/throttle/lockout/attempt patterns in `auth.py`/`main.py`: zero hits). This is a genuine **pre-existing** gap this milestone did not introduce, but whose relevance is directly heightened by this milestone's own goal of expanding network reachability. Recorded prominently below as a real, unresolved finding, not fixed here (a properly-designed rate-limiter needs its own careful DoS-aware design and tests — real scope, not a one-line patch).
- **Session theft.** `mb_session` is `HttpOnly` (no JS access), `SameSite=Lax`, `Secure` conditional on real HTTPS/trusted `X-Forwarded-Proto` (unchanged, pre-existing, re-verified this session). On plain HTTP (LAN without a reverse proxy), the cookie is interceptable by anyone on that network segment — an accepted, already-documented trade-off of the existing "the LAN is the trust boundary" doctrine, now explicitly extended to acknowledge remote/overlay access shares the same shape.
- **TLS interception.** No built-in TLS; addressed by the chosen posture (overlay-network transport encryption or an optional reverse proxy) — see below.
- **CSRF/CORS mistakes.** CORS re-audited: a bounded, explicit, dev-only origin allowlist, never a wildcard, `allow_credentials=True` correctly paired with real origins only — confirmed both statically (introspecting the live middleware config) and behaviorally (an arbitrary origin receives no CORS grant, on both a simple request and a credentialed preflight) via 4 new tests in `tests/test_cors_security.py`, closing a real, previously-zero regression coverage gap. CSRF still relies on `SameSite=Lax` + same-origin SPA, unchanged, pre-existing, honestly documented as an accepted trade-off (not a bespoke CSRF-token scheme).
- **Insecure forwarding / accidental media exposure.** Verified directly: every media/evidence/preview route is absent from `_ALWAYS_PUBLIC_PATHS` and therefore defaults to `authenticated` tier — confirmed by reading the actual policy table, not assumed.
- **Overly broad admin access / exposing private Place data.** Unaffected — RBAC (Viewer/Reviewer/Administrator) is untouched by this milestone; the new `/api/product/connection` endpoint deliberately defaults to `authenticated` (not public) despite its underlying facts being only mildly sensitive, on a least-disclosure principle.

## Chosen remote-access posture (Phase 16/17)

**A private overlay network (Tailscale-compatible / WireGuard-based) is the recommended, documented golden path for away-from-home access.** MockingBird does not implement, bundle, or require one — it integrates only at the documentation/product boundary, exactly as the brief's own likely-answer anticipated, verified against real architecture rather than assumed:

- LAN is native (already worked, now discoverable — see Phase 14).
- A private overlay network is the recommended remote-access path (documented in `using-mockingbird.md`, referencing Tailscale by name as one concrete example, explicit that MockingBird "does not require, and does not itself provide, a cloud account, a cloud relay, or a hosted service").
- Direct public-internet port forwarding is explicitly unsupported, stated plainly, not silently allowed-by-omission.
- A MockingBird-operated cloud relay was **not built** and remains explicitly out of scope, per the brief's own strong guidance against it — the smallest secure path was chosen deliberately over the largest capable one.

**Overlay-network integration boundary honored:** no attempt was made to reimplement Tailscale/WireGuard. The one integration point built — `GET /api/product/connection` plus the Settings card — answers "what address would work" using only facts the Host already has (bind flags, a best-effort local-network address), never claiming knowledge of a user's overlay-network setup, and a third-party account is never required for ordinary local use (the overlay network is entirely optional, only relevant to remote access).

## TLS/auth/session behavior (Phase 18/19)

**TLS posture, stated exactly, no new claims:** same-LAN access is honestly plain HTTP by default (matches pre-existing Local Identity doctrine, unchanged); a reverse proxy (nginx/Caddy) remains the documented path for anyone wanting TLS termination on the LAN itself; for the recommended overlay-network remote path, the overlay tool's own transport encryption (e.g. Tailscale's WireGuard tunnel) is what actually protects traffic — the new documentation is explicit that this is a *different layer* providing that protection, never claiming "end-to-end encrypted by MockingBird" anywhere in product copy or this report.

**Auth/session, re-verified not re-designed:** cookie flags (`HttpOnly`, `SameSite=Lax`, conditional `Secure`), 30-day rolling expiry, server-side opaque session storage, and the central `authenticated`-by-default authorization middleware are all pre-existing and unchanged. No long-lived bearer token was introduced anywhere (`localStorage` remains unused for auth, confirmed unchanged — the frontend still never reads or stores the session token directly, `credentials: "same-origin"` on every request). New coverage: 9 tests in `tests/test_windows_launcher_instance_identity.py` for the new `/api/product/connection` endpoint (including an explicit `test_product_connection_endpoint_requires_authentication` proving it is not accidentally public) plus 4 in `tests/test_cors_security.py`.

## Media / bandwidth behavior (Phase 21/23)

Added `loading="lazy"` to gallery/list `<img>` tags across the highest-traffic surfaces (`MediaAssetPreview` — the shared thumbnail component reused across most list views, `VisitEvidenceSequence`'s thumbnail strip, `EventDetailPage`, `ActivityLibraryPage`, `CollectionsPage`, `WildlifeInsightsPanel`) — a safe, native, zero-risk progressive enhancement (browsers without support simply ignore it; an already-in-viewport image is unaffected either way). Deliberately left untouched: live/current-frame previews (`CurrentFrameView`, `LiveCameraOverview`) and single-focus active editing/viewing images (`RefinedCropEditor`, `IdentificationAssistant`'s analyzed-input figure, the evidence zoom viewer's own focused image) — lazy-loading a live or always-immediately-needed image has no benefit and unclear interaction with live-refresh logic this milestone did not audit deeply enough to touch safely. No thumbnail/derivative path was changed, no recompression introduced, no evidence lineage affected.

## Error / recovery UX (Phase 24)

Audited by direct inspection, not assumed. `client.ts`'s `onSessionExpired` pub/sub already gives "you need to sign in again" a distinct, centralized path (fires once on any 401, `App.tsx` drops back to Sign-in) separate from "the Host is unreachable" (`App.tsx`'s own `error`/`error-panel` state, with a named `apiClient.baseUrl` and a Retry button, shown only when the *required* health/sources/streams calls fail — a *secondary* data source failing instead sets `loadWarnings`, a smaller non-blocking notice, so one flaky widget never blanks the whole screen). No infinite blank spinner exists in either path. Camera-specific "offline" states are handled separately again (see "Cameras / health," above, and pre-existing "product-health semantics: paired/configured != live/reachable" doctrine, unaffected by this milestone). No code changes were needed here — this phase's work was verification that the three states Phase 24 names (Host unreachable / camera offline / session expired) are already honestly distinguished, not collapsed into one generic error.

## Live view boundary (Phase 22)

Confirmed, not assumed: live camera view uses plain HTTP MJPEG multipart streaming (no WebSocket/SSE anywhere in this codebase), authenticated via the same session cookie as everything else — no separate stream token. **A real, honest limitation worth recording:** iOS Safari does not natively support `multipart/x-mixed-replace` MJPEG streams — a live view opened from an iPhone browser is likely to show a static/broken image rather than motion. This is a pre-existing platform limitation, not introduced or fixed by this milestone (matching the brief's own explicit deprioritization of continuous live-view streaming in favor of observations/evidence/health/Today/Story), recorded honestly rather than silently left for a user to discover.

## Responsive performance / viewport test matrix (Phase 25/26)

The 10-surface sweep above ran at `devices["Pixel 7"]` (412×839). Phase 25 explicitly asks for at least ~360px, ~390px, and a tablet/narrow-desktop width, not one phone size, so `mobile-viewport-audit.spec.ts` also carries a second, parametrized block re-checking the two highest-content-density surfaces (Today, Visit detail) plus the nav drawer itself at 360px, 390px, and 768px (proportionate additional coverage rather than tripling the full 10-surface sweep for marginal extra evidence). The nav-drawer test is width-aware by design: below 760px it opens the hamburger drawer, confirms the toggle meets the ≥40×40px tap-target bar, navigates, and confirms the drawer closes on navigation; at 768px (above the mobile-nav breakpoint) it instead confirms the ordinary always-visible desktop sidebar navigates correctly — both are intentionally different, correct behaviors at that width, not a single fixed shape asserted regardless of context. Results: **19/19 passing** (the original 10-surface sweep plus 9 new: Today/Visit-detail/nav at each of 360px, 390px, 768px) — zero horizontal-overflow findings at any of the four widths now tested, and the nav-drawer test independently confirms both intended behaviors are correct: the hamburger/drawer at 360px and 390px (toggle meets the tap-target bar, opens, navigates, closes on navigation), and the ordinary always-visible desktop sidebar at 768px.

## Support matrix (Phase 29)

**Supported directly:** responsive web UI (phone/tablet/desktop — 10 core surfaces verified overflow-free, the two densest re-verified at 360px/390px/768px specifically); LAN access via `--host 0.0.0.0 --allow-network` (pre-existing flag, now discoverable); the existing authenticated-session model, reused unchanged for LAN and remote alike; an installable web-app shell (manifest + icons + bounded-safe service worker) for "Add to Home Screen"; automated mobile-viewport regression coverage (19 Playwright tests).

**Supported through external secure networking:** away-from-home access via a private overlay network (Tailscale or a similar WireGuard-based tool) — documented, structurally compatible, not bundled; TLS for LAN access via an optional user-provided reverse proxy.

**Structurally compatible but not directly validated:** an actual Tailscale/WireGuard round-trip (no such network reachable from this sandbox — validated structurally instead: none of the auth/CORS/route-policy logic is network-path-aware, so the same guarantees necessarily apply regardless of which private network carries the traffic); real "Add to Home Screen" behavior on a physical iOS/Android device (manifest/meta-tag correctness verified, not a physical device); live camera view over a remote/overlay path (works the same as LAN mechanically; the iOS Safari MJPEG limitation above is independent of network path).

**Unsupported, stated explicitly:** direct public-internet port forwarding of the Host; plain public HTTP for authenticated traffic; a MockingBird-operated cloud relay (does not exist); a native mobile app (does not exist — responsive web + installable PWA is the supported mobile path); push notifications (not built this milestone); fine-grained per-request local-vs-remote connection classification in ordinary UI (deferred — IP heuristics are not definitive, and the brief is explicit the core user should not need to understand NAT).

## Product-shaped phone workflow (Phase 32)

Exercised end-to-end at phone viewport against a real isolated dev instance with real seeded data (not mocked): sign-in → Today → open a Visit → inspect evidence → submit a correction (Review Queue) → Bird Log → Place Story → story evidence link → Cameras → a Settings action (Connection & Remote Access card render) → sign-out/sign-in. Zero horizontal overflow anywhere, zero dead ends, all touch targets checked automatically met the ≥40×40px bar. This is automated, product-shaped validation on realistic data — not external-user acceptance, and not represented as such.

## Security validation (Phase 28)

- `ProductHealthStatus` (the one pre-existing *public* health surface) re-inspected specifically for this milestone's remote-access framing: `cameras`/`observation`/`backup` sub-objects carry only bounded aggregate counts (`needs_attention_count`, `configured_stream_count`, etc.) — no camera names, addresses, or credentials, confirmed by reading the actual schema, not assumed safe.
- New `/api/product/connection` deliberately kept **authenticated** (unlike the launcher-facing `/instance`/`/health`) on a least-disclosure principle, even though its own facts are only mildly sensitive.
- CORS: 4 new regression tests (`tests/test_cors_security.py`) — no wildcard, credentials correctly paired only with real origins, an arbitrary origin gets no grant on either a simple request or a credentialed preflight.
- Media/evidence routes confirmed authenticated by policy-table inspection (see "Threat model," above).
- No login rate-limiting exists — found, not fixed, prominently recorded (see "Threat model" and "Remaining opportunities").
- `git diff --check`: clean, no whitespace errors.

## Tests / validation

- **Tier 1 (focused):** 91 tests across the Phase 0 fix's own files (all passing); 9 new tests for `/api/product/connection` + `runtime.py` wiring; 4 new CORS tests. `ruff check` clean on every touched backend file (0 new findings; pre-existing 57 findings elsewhere in `product_repository.py` confirmed unrelated via `git stash` bisection).
- **Tier 2 (Core gate, `python scripts/verify_core.py`, final run against the complete diff):** **4976 passed / 3 failed / 3 skipped / 23 deselected (slow) / 11 xfailed (24m02s)**. Two failures are the identical, already-documented `test_place_biodiversity_summary_repository.py` pair (`'seen_before' == 'new'` mismatch) every prior milestone back to Place/Yard Intelligence v2 has recorded — **directly re-confirmed this session via a fresh `git stash push -u` bisection against the clean pre-milestone baseline** (byte-identical failure, zero of this milestone's changes applied), not merely pattern-matched against the documented history. The third, new this run, is `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success` — a file with **zero code relationship** to anything this milestone touched (Camera Node transport/protocol diagnostics), which passed **7/7 cleanly when re-run in isolation** immediately after the failure, and which matches an already-documented precedent for exactly this file under exactly this condition (`docs/environmental-context-v2-report.md`'s own baseline recorded a *different* test in this same file failing only "under confirmed heavy concurrent system load" and passing clean in isolation — the identical evidentiary shape, not a new phenomenon). This sandbox was independently confirmed under real, unrelated, heavy concurrent CPU load throughout this session (`uptime`/`ps` showed a completely unrelated repository's own full pytest run plus a dozen-plus other Claude Code processes) — both the ~24min runtime (vs. the ~9min historical baseline) and this one timing-sensitive flake are consistent with that contention, not a Core-gate regression.
- **Frontend:** `tsc --noEmit` clean; `vite build` clean (all `web/public/*` assets — manifest, icons, `sw.js`, `favicon.ico` — correctly copied into `dist/`).
- **Frontend e2e (Tier 3 breadth):** new `mobile-viewport-audit.spec.ts` — **19/19 passing** (10 core surfaces at Pixel-7-class 412px, plus the Phase 25 360px/390px/768px matrix), after fixing 3 genuine selector/seeding issues found during development (detailed in "Cameras/health" and this section's own note below — none were product regressions). Full existing suite (`node e2e/run-playwright.mjs`, 112 tests across ~23 spec files, no filter) re-run in full: **111 passed / 1 failed**, and that one failure is **only** the already-known, independently-reproduced pre-existing failure (`reviewed-product-loop.spec.ts`, the same `product_category`/"animals" tab gap documented under "Cameras/health" — confirmed broken *unmodified*, run alone, with zero of this milestone's changes involved) — every other spec, including two pre-existing mobile-specific tests (`place-features.spec.ts`'s narrow-viewport case, `place-story.spec.ts`'s phone-width case), passed with zero regressions from the navigation/CSS changes.
- **A genuine incidental finding, recorded not silently fixed:** `.bird-log-entry` is dead CSS (defined in `styles.css`, referenced by zero `.tsx` files) — `BirdLogPage`'s real overview-grid class is `.journal-label-card`, confirmed by direct source inspection. Left in place (out of bounded scope; a one-line CSS deletion carries its own small verification burden this milestone did not extend to).

## Remaining major PRODUCT opportunities

Not framed as release blockers — this is substantial product development, not release closure:

- **Visit/Stream/Settings page density.** All three remain long, information-dense single-column pages on a phone. Structurally sound (no overflow, no breakage) but not calm. Progressive disclosure (collapsing secondary sections, mirroring the `<details>` pattern already used for advanced diagnostics) is the natural next step, deliberately not attempted this pass — a content-prioritization decision needing its own product judgment, not a mechanical CSS fix.
- **`ReviewQueuePage`'s default "animals" tab / `product_category` gap.** A real, pre-existing defect (not introduced or fixed by this milestone) where neither demo-seeded nor freshly-imported needs-review Visits populate `product_category` in a way the default tab's filter expects — makes the default Review Queue view show 0 items even when unreviewed work exists. Independently reproduced against an unmodified existing spec. Worth a dedicated, focused fix.
- **Login rate-limiting.** No active protection against repeated sign-in attempts exists. Real, pre-existing, and its relevance is directly heightened by this milestone's own expanded-reachability goal. Needs its own careful, DoS-aware design — not attempted here.
- **`.bird-log-entry` dead CSS.** Trivial, safe cleanup opportunity, left for a future pass.
- **PWA offline semantics remain intentionally minimal** — no offline data access at all, by design. A future milestone could explore a genuinely safe "queued correction while offline" story, but that is real new product surface, not a mobile-polish item.
- **iOS Safari MJPEG live-view limitation** — a platform gap, not something MockingBird's own code can fix without a different streaming mechanism (out of this milestone's live-view-deprioritized scope).
- **Fine-grained connection-context UI** (local vs. remote-overlay vs. unknown, per-request) was deliberately not built — IP heuristics are not definitive, and the brief itself cautions against pretending otherwise; a future Advanced Diagnostics surface could attempt this honestly if real user need emerges.
- **A formal WCAG audit** was not performed — this milestone's accessibility work was a targeted spot-check of touched/new surfaces, not a certification.
- **`e2e/` is not covered by `tsc`/`npm run typecheck`** — a pre-existing, repo-wide gap (`tsconfig.json`'s `include` omits `e2e/`, and `@types/node` is not installed) discovered incidentally while writing the new mobile-viewport spec; every existing spec file already relies on the same untyped `Buffer`/`node:path` conventions. Not fixed here (would require a new devDependency and likely surface pre-existing type issues across ~23 files) — recorded for a future, dedicated pass.

## Capability maturity

**B — strong mobile experience and a clear secure remote posture with bounded external-network/PWA gaps.**

Earned, not defaulted-to: a real, verified navigation fix (D→A, proven via 10 real automated screenshots at phone width with zero overflow findings across the whole product, not asserted from CSS alone); a working, bounded, safety-reasoned PWA shell built from nothing; LAN access made genuinely discoverable with real backend support and tests; a remote-access posture that was investigated against actual architecture and explicitly documented rather than assumed; new CORS/connection-endpoint security regression coverage where none existed. Held back from A by real, honestly-recorded gaps: dense secondary pages not yet given progressive disclosure, no live external-overlay-network validation possible in this sandbox, a genuine pre-existing Review-Queue data gap and a genuine pre-existing rate-limiting gap, both found and recorded rather than fixed within this milestone's bounds.

## Scheduler reconciliation

**CURRENT PHASE: SUBSTANTIAL PRODUCT DEVELOPMENT** — confirmed, preserved. This milestone does not authorize Calm Notifications, release work, or any other downstream lane; see `release-execution-state.md`'s own reconciliation entry for the exact authorization statement.

## Preserved files

The seven preserved untracked detector files were verified present and byte-identical to their state at milestone start (`git status --short` below) — not modified, staged, or renamed at any point this session.

## Exact git status --short

Captured immediately before staging the implementation commit (working tree state described throughout this report):

```
 M docs/meaningful-change-detection-contract.md
 M docs/using-mockingbird.md
 M src/mockingbird/analytics/place_change_summary.py
 M src/mockingbird/analytics/place_story.py
 M src/mockingbird/analytics/regularity_narrative.py
 M src/mockingbird/api/main.py
 M src/mockingbird/api/schemas.py
 M src/mockingbird/repository/product_repository.py
 M src/mockingbird/runtime.py
 M tests/test_place_change_summary.py
 M tests/test_place_change_summary_repository.py
 M tests/test_place_story.py
 M tests/test_regularity_narrative.py
 M tests/test_windows_launcher_instance_identity.py
 M web/index.html
 M web/src/App.tsx
 M web/src/api/client.ts
 M web/src/api/types.ts
 M web/src/components/MediaAssetPreview.tsx
 M web/src/components/VisitEvidenceSequence.tsx
 M web/src/components/WildlifeInsightsPanel.tsx
 M web/src/main.tsx
 M web/src/pages/ActivityLibraryPage.tsx
 M web/src/pages/CameraSetupPage.tsx
 M web/src/pages/CollectionsPage.tsx
 M web/src/pages/EventDetailPage.tsx
 M web/src/pages/LocalDataPage.tsx
 M web/src/pages/UsersPage.tsx
 M web/src/styles.css
?? docs/mobile-remote-experience-v1-report.md
?? docs/wildlife-detector-training-contract.md.orig   (preserved, untouched)
?? scripts/evaluate_small_bird_detector.py            (preserved, untouched)
?? scripts/materialize_wildlife_stage2.py.orig        (preserved, untouched)
?? scripts/train_wildlife_stage2_rfdetr.py.orig       (preserved, untouched)
?? src/mockingbird/detectors/small_bird_benchmark.py  (preserved, untouched)
?? src/mockingbird/training/wildlife.py.orig          (preserved, untouched)
?? tests/test_cors_security.py
?? tests/test_small_bird_benchmark.py                 (preserved, untouched)
?? web/e2e/mobile-viewport-audit.spec.ts
?? web/public/
```

`git diff --check`: clean (no whitespace errors). All seven preserved files individually diffed against their milestone-start state: zero changes.
