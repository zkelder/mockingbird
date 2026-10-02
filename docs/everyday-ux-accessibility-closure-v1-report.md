# Everyday UX & Accessibility Closure v1 -- Report

**Date:** 2026-10-01. **Start:** `main` at `c146eff`. **Version:** `0.1.0`
(unchanged). **Schema:** `v62` (unchanged -- no migration). **Authorized by:**
the owner, as milestone 2 of the locked pre-1.0 queue
([audit](pre-1.0-software-gap-audit-contract-lock-v1-report.md)). **Proposed
classification:** A (see §8). Acceptance is not recorded here.

## 1. Task packet

- **Phase:** PRE-1.0 PRODUCT COMPLETION -- SOFTWARE-FIRST.
- **Product flow:** Understand → Confirm. Everyday surfaces should lead with
  the reviewer's job and keep technical/structural detail one step away, never
  hidden from evidence, provenance or correction.
- **Why next:** it is the authorized second queue item; each residual was
  already recorded in the audit.
- **Files allowed:** `web/src/**`, `web/e2e/**`, `docs/**`.
- **Non-goals, held:** schema/migration, backend behavior, new data domain,
  Camera/Source redesign, new settings architecture, design-system rewrite,
  general stylesheet rewrite, Orphan Media Integrity, any later milestone.
- **Validation tier:** frontend affected-subsystem + full browser suite; no
  Core (§5).

## 2. Residuals investigated

| Residual | Reproduced on `c146eff`? | Outcome |
| --- | --- | --- |
| Zone area canvas pointer-only (`CameraSetupPage.tsx:732`) | **Yes** -- `role="img"`, no tab stop, pointer handlers only | Fixed |
| Visit page: structural tools shown ahead of review | **Yes** -- "Visit curation" (edit evidence / merge / re-zone) was expanded above "Species review" | Fixed (collapsed) |
| Stream page technical density | **Partly.** Observation diagnostics, species pack, timing, live debug are already `<details>`. Remaining: every Recent Visit card carried a "Merge nearby" button that ran the *same* handler as "Open Visit detail" (duplicate and mislabeled) | Fixed (duplicate removed) |
| Settings (Local Data) advanced prominence | **Yes** -- demo reset sat open above Shut Down; the launch-command / network-posture essay was always expanded under Connection | Fixed |
| Raw exception copy | **Yes** -- reproduced: a 200 response with a non-JSON body surfaced `SyntaxError` text; 207 catch sites used `error instanceof Error ? error.message : fallback`, and one used `String(caught)` | Fixed |
| Dead Bird Log CSS | **Yes** -- 38 distinct selectors (55 selector entries across base and responsive rules), no reference in any `.tsx`/`.ts`/`index.html`/e2e, no dynamically built `bird-log-*` class name | Removed |

Already-closed items were not reopened: network-level "Failed to fetch" is
already friendly (`friendlyFetch`), the Local Data `<details>` for retention
and storage detail already existed, Zone *selection* is already keyboard
accessible.

## 3. What changed

- **Zone area editor (keyboard path).** The canvas is now a focusable
  `role="group"` named "Area to watch", described by on-page instructions
  (`aria-describedby`). Arrow keys move the rectangle (2%), Shift+arrows
  resize it, Alt gives 0.5% steps; four labeled fields (Left edge, Top edge,
  Width, Height, in percent) edit exactly the same rectangle and are the
  screen-reader-robust path; a polite live region announces the position.
  Values clamp so the area never leaves the picture or drops below the
  existing 3% minimum; a typed size stops at the picture edge rather than
  moving the opposite edge. The Camera Node draft is saved once on blur, not
  per keystroke. Visible 3px focus ring. Pointer drawing is unchanged. The
  geometry is the same 4-point rectangle the pointer path already produced --
  no second model.
- **Visit curation** is a collapsed `<details>` (same pattern as the Stream
  page's secondary panels). Review, correction, evidence, provenance, notes
  and history are untouched and visible.
- **Stream Recent Visits:** the duplicate "Merge nearby" button is removed;
  "Open Visit detail" now always shows (Review in Queue still leads for
  needs-review Visits).
- **Local Data:** "Reset Demo Data" is collapsed; the connection status/URL and
  a one-line "Signing in is always required, on any device." stay visible,
  with the launch command and network guidance under "How phone and remote
  access works".
- **Error copy:** `userFacingErrorMessage(caught, fallback)` in `web/src/utils.ts`.
  An `ApiError` (human-authored backend text) or any page/`withTimeout`
  `Error` passes through; built-in runtime errors (`TypeError`, `SyntaxError`,
  `RangeError`, `ReferenceError`, ...) are replaced with the surface's own
  actionable fallback, while the raw error is still written to the console.
  The API client now converts an unreadable success body into an `ApiError`
  with a product message. Applied mechanically to all 207 sites.
- **CSS:** removed the unreferenced `.bird-log-*` block. A rule-level
  before/after comparison confirmed no other rule was lost or altered.

## 4. Files

- `web/src/pages/CameraSetupPage.tsx` -- keyboard zone editor.
- `web/src/pages/VisitDetailPage.tsx`, `StreamDetailPage.tsx`,
  `LocalDataPage.tsx` -- disclosure / duplicate removal.
- `web/src/utils.ts`, `web/src/api/client.ts` -- error seam.
- Mechanical `userFacingErrorMessage` adoption: 25 further page/component
  files (`App.tsx`, `StreamsPage.tsx`, `ReviewQueuePage.tsx`, ...).
- `web/src/styles.css` -- dead CSS removed; focus/disclosure/fieldset styles.
- `web/e2e/everyday-ux-accessibility.spec.ts` -- new, 6 tests.
- `docs/release-execution-state.md` -- scheduler reconciliation + this record.
- `docs/everyday-ux-accessibility-closure-v1-report.md` -- this file.

## 5. Validation

- `tsc --noEmit` clean; production build clean (part of `npm run test:e2e`).
- New spec `everyday-ux-accessibility.spec.ts`: 6/6, covering keyboard
  move/resize/typed commit/clamping, focus visibility (computed outline when
  reached via Shift+Tab), `aria-describedby`, Visit curation collapsed →
  keyboard-toggled, Stream duplicate absent, Local Data disclosures, the
  helper's pass-through/replace behavior, and a mocked non-JSON 200 showing
  product copy rather than a JSON parse error.
- Full default browser suite: **209/209 passed** (203 pre-existing + 6 new; 3.9 min), because the change crosses shared helpers, the stylesheet and several pages.
- **Core not run.** No Python, API, schema, runtime or persistence behavior
  changed; the diff is confined to `web/` and `docs/`.
- No hardware validation claimed or required.
- **Accessibility evidence:** the repository has no automated a11y engine
  (no axe); evidence is Playwright role/name/state/focus assertions plus
  keyboard-only operation above. Not a screen-reader (NVDA/VoiceOver) pass.

## 6. Deviations and limitations

- Only the guided setup canvas got a keyboard editor. The Stream page's
  live-view zone drawing (`StreamDetailPage`, over live video) remains
  pointer-driven; a Zone can still be created keyboard-only through guided
  setup, and existing Zones are selectable by keyboard. Extending the same
  editor to the live overlay is separate interaction work.
- Backend-authored `error_message` strings (e.g. recorded-media analysis
  results rendered on the Cameras page) are rendered as returned; this
  milestone made no backend change.
- Screen-reader behavior of the live region and group role was not verified
  with a real assistive technology.

## 7. Protected state

The seven protected detector files are untouched and unstaged; `uv.lock`
remains untracked and was not staged. Not pushed.

## 8. Proposed classification

**A**, pending ChatGPT acceptance: every reproduced residual was closed or
accurately recorded as already closed, no scope boundary was crossed, and the
disclosed limitations in §6 are bounded and do not weaken any requirement.
