# Owner-Only Final Release Hardening -- Fast Review Queue-End Undo v1 -- Report

**Date:** 2026-09-29. **Start:** `main` at record HEAD `b11cc66`. The
accepted candidate was `02443ea` (ZIP `785f3f37…`, build
`5200ec77a7221902`), `0.1.0`, schema `v61`. **Authorized by:** ChatGPT
global sequencing, after Browser Suite Determinism & Demo-Boundary Closure
v1 was accepted at classification A. **Classification: A.**

**Commits** (local, not pushed):

| Commit | Content |
|---|---|
| `1d325f5` | Authorization record (docs only) |
| `d7e61c1` | Fix and focused browser spec (frontend only). **New candidate source.** |
| this report's commit | Closure record |

**Summary:**

- Saving the final Visit of a filtered Fast Review session keeps the
  "Saved <label>." confirmation and an operable **Undo last correction**
  on the "Filtered queue complete" screen, and `Z` works there too.
- The fix reuses the existing undo control and `undoLastCorrection()`.
  There is no new correction or reversal path, and no backend or schema
  change.
- The complete default browser suite is **198/198** (196 + 2 new).
- New private Windows candidate `d7e61c1`, ZIP `75d998f7…`, build
  `c901ac14bce22fe4`, accepted on native Windows. It **supersedes**
  `02443ea` / `785f3f37…`, which stays accepted evidence.

## 1. Task packet

- **Roadmap phase:** Final Release Hardening, owner-only (feature freeze;
  §6.S). Gate G stays **waived, not passed**. The owner is the sole
  pre-release tester.
- **Product flow improved:** Confirm -> Remember. A reviewer who
  mislabels the last Visit of a filtered session can take the Review
  Decision back where they made it, so an accidental label does not
  silently become the Visit's reviewed truth.
- **Why next:** finding F-1 of Browser Suite Determinism & Demo-Boundary
  Closure v1, reproduced and authorized.
- **Files allowed:** `web/src/pages/ReviewQueuePage.tsx`
  (`FastReviewPanel` only), one new `web/e2e` spec, docs.
- **Non-goals:** as authorized. No duplicate alert-poller change (F-2),
  features, Fast Review redesign, reviewed-truth semantics, detector,
  threshold or identification policy, Pi or Camera Node work, Gate G or
  participant work, signing, publishing, uploading, tagging or pushing.
- **Validation tier:** focused browser test red then green; affected
  specs; the complete default suite; the three separate configurations;
  `tsc` and `vite build`; a rebuilt artifact with native-Windows
  acceptance, because packaged frontend input changed. Full Core is not
  run (Tier 3 justification in §4).

## 2. Root cause

`FastReviewPanel` had two independent gaps, both keyed on "is there an
active item":

1. The "Saved <label>." / **Undo last correction** block was rendered
   only inside the active-item branch. The final save navigates to "next",
   finds none, sets `activeItem` to `null` and renders the `!activeItem`
   "Filtered queue complete" branch, which had no undo block. The
   `undoState` token was still set and valid.
2. The keydown effect returned early when `!activeItem`, so the documented
   `Z` shortcut was detached on the completion screen.

## 3. Fix (`d7e61c1`)

- The existing undo block is now one `undoControl` element rendered by
  both the active-item and completion branches. It is unchanged: same
  markup, same `undoLastCorrection()`, same `disabled={isSaving}`.
- The keydown handler stays attached while the session is open. Order:
  typing-target protection first (unchanged), then `Z` -> the existing
  `undoLastCorrection()` on either screen, then `if (!activeItem) return`
  before every other shortcut, so correction and navigation shortcuts
  cannot run without an active item.
- After undo, the existing code already re-resolves the restored Visit
  through the navigation endpoint and makes it `activeItem`; the existing
  `activeItem?.id` focus effect moves focus to its heading. No change was
  needed there.
- An expired or superseded token still reaches the unchanged catch path,
  which shows the server's honest 409 message ("Fast Review undo is no
  longer available.").

## 4. Validation

**Red before the fix.** The new spec failed on the unfixed source, both
tests at the same assertion: the completion panel read only "Fast Review
Filtered queue complete No unresolved Visit remains in this filtered
queue. Return to Review Queue". This was captured on the first draft and
again on the final spec with only `ReviewQueuePage.tsx` stashed.

**New spec** `web/e2e/review-queue-fast-review-queue-end-undo.spec.ts`,
one real (non-demo) Source and one imported Visit per test, archived at
the end:

- Test 1: save the final item by click ("Blank / no activity") ->
  completion screen, heading focused, "Saved …." and an enabled Undo;
  the Visit is `reviewed` with one authoritative effective label.
  Pressing `c` and `b` there does nothing; `z` typed into the filter
  field is text, not undo (no undo request, truth unchanged). Click
  Undo -> `200` reversal for this Visit, the same Visit is the active
  item again with its heading focused, "0 reviewed this session · 1
  matching unresolved Visit", "Correction undone…", and the Visit state
  equals its pre-save state with no effective labels. Round 2 saves with
  the `k` shortcut and undoes with `Z` from the completion screen, with
  the same checks and a distinct reversal id. Exit shows "Start Fast
  Review (1)".
- Test 2 (invalidated token): after the final save, a newer human
  correction through `POST /api/review-labels` supersedes it. Undo returns
  `409`, the completion screen shows "Fast Review undo is no longer
  available.", no success message, and the newer label stays the truth.

**Browser runs** (each on a fresh isolated instance, `retries: 0`):

| Run | Result |
|---|---|
| New spec, unfixed source | 2 failed (red, as above) |
| New spec, fixed | 2/2 |
| Affected Fast Review and reviewed-truth specs together (new, fast-review-keyboard, reviewed-product-loop, reviewed-tab, reviewed-history-demo-exclusion, visit-evidence-review-loop, bulk-correct-stale-write, count-demo-exclusion) | 10/10 |
| New + fast-review-keyboard + count-demo-exclusion, `--repeat-each=10`, one shared instance | 40/40 |
| **Complete default suite** | **198/198**, no skip, quarantine or retry |
| Bounded Review Queue / onboarding / bounded media configs | 4/4, 6/6, 2/2 |

**Frontend:** `tsc --noEmit` clean; `vite build` clean.

**Tier 3 justification for not running full Core:**
`git diff 02443ea d7e61c1` touches exactly two files,
`web/src/pages/ReviewQueuePage.tsx` and the new spec. Nothing under
`src/`, `scripts/`, `tests/` or `pyproject.toml` changed, and all 212
packaged `mockingbird/*.py` files are byte-identical to the source. Core
at `02443ea` was green (6253 passed, 0 failed) on the same Python tree.
The change is covered by the browser layer, which is where it lives.

## 5. Artifact (packaged frontend input changed -> new candidate)

**Host ZIP** (`dist/fast-review-queue-end-undo-v1-d7e61c1/`, private,
ignored, unsigned):

- `MockingBird-windows-x64.zip` SHA-256
  **`75d998f7c2e28c6c4b5936a8f74e166238815d761ea5b8ad8c2f1e82c119127b`**.
- `build_id c901ac14bce22fe4`, `source_clean: true`, source
  `git:d7e61c15687af3560aac3c5ba41e62aa856fd745`. 19,284 files /
  4,923,723,178 bytes.
- Built with `scripts/build_local_product.py`, no skip flags (10m25s).

**Verification:**

- `SHA256SUMS` all OK.
- `verify_release_artifact.py` -> `OK … source git:d7e61c1…, unsigned`.
- All 212 packaged `mockingbird/*.py` files are byte-identical to
  `d7e61c1`.
- SBOM: 59 components, the identical set to `02443ea`.
- Manifest differences from `02443ea`: only build identity, byte total,
  SBOM hash, `source_state` and the ZIP hash.
- Tree differences from `02443ea` (15 entries): `build_info.json`, wheel
  `RECORD`/`direct_url.json`, and `web_dist/` only -- `index.html`, the
  frontend source fingerprint, and the rebuilt `index`, `ReviewQueuePage`
  chunk and three chunks whose content hashes chain from it
  (`SpeciesSuggestionsPage`, `StreamDetailPage`, `VisitDetailPage`).

**Camera Node:** `git diff 02443ea..d7e61c1` touches nothing under
`src/mockingbird_node` or its build scripts. The accepted wheel
`38dfac47…` stays valid. No Node rebuild and no Pi or hardware acceptance
is performed or claimed.

**Native-Windows acceptance** (exact ZIP, disposable home):

- **Setup:** copied from the Windows side over UNC; native `Get-FileHash`
  = `75D998F7…`, matching. `tar.exe` extraction 75 s -> 19,284 files /
  4,923,723,178 bytes, exactly the manifest. Install `D:\MBQU\install`,
  home `D:\MBQU\home`, port 8154, launched with the shipped `Start
  MockingBird.vbs`, with the six developer `MOCKINGBIRD_*` variables
  removed at process scope only. Real Edge, headless, America/New_York.
  Port 8000 was free and untouched; `%LOCALAPPDATA%\MockingBird` was
  untouched (last write 2026-08-09, before and after).
- **Identity:** `GET /api/product/instance` -> `git_commit d7e61c1…`,
  `build_id c901ac14bce22fe4`.
- **Flow:** onboarding through the UI (manual-media camera); a
  reference-Pi still imported through **Import Media** -> one real Visit
  (`needs_review`, no labels). Review Queue filtered to it -> "Start Fast
  Review (1)" -> "0 reviewed this session · 1 matching unresolved Visit".
- **Round 1 (click):** *Northern Cardinal*, Save & Next -> "Filtered
  queue complete", heading focused, "Saved Northern Cardinal." with an
  enabled **Undo last correction**. The Visit was `reviewed`,
  `review_origin: human`, `is_authoritative: true`. Undo -> `200` for
  this Visit; the Visit returned as the active item (heading focused),
  "0 reviewed this session · 1 matching unresolved Visit", and its state
  equalled the pre-save state exactly.
- **Round 2 (keyboard `Z`):** the same save, then `Z` on the completion
  screen -> the same results.
- A final kept correction (*Northern Cardinal*, human, authoritative) was
  left for the restart check.
- **Shutdown, restart, Doctor:** two in-app shutdowns (Local Data -> Shut
  down MockingBird -> Confirm), each leaving "Application shutdown
  complete", 0 remaining processes and the port free. The relaunch reported
  `previous_shutdown_clean: true` with the kept correction intact. CLI
  `doctor --json` on the stopped home: **HEALTHY**, exit 0, both times.
- **Browser errors:** **0 uncaught page errors, 0 HTTP 5xx.** First run:
  the two designed first-run resource messages only (`401 GET
  /api/auth/session` before the account exists; `404 GET
  /api/camera-nodes/pending-setup`, the "nothing to resume" answer), the
  same as on `02443ea`. Restart phase: no console errors and no 4xx/5xx.
- **Evidence:** screenshots, JSONL, driver, scripts and every browser log
  are in ignored `dist/fast-review-queue-end-undo-v1-d7e61c1-evidence/`.

## 6. Boundaries kept

- Frontend only; no backend, schema (`v61`) or reviewed-truth semantics
  change. The existing undo endpoint and its conflict rules are the only
  reversal path.
- No Fast Review redesign: the completion screen gains exactly the
  existing undo block.
- No weakened assertion, skip, quarantine or retry; the new spec owns its
  data and archives its Source.
- F-2 (duplicate alert pollers) not touched. No detector, threshold or
  identification-policy change. No Pi, Camera Node or Gate G work.
- Nothing signed, published, uploaded, tagged or pushed.
- The protected untracked files and `uv.lock` are untouched. Only explicit
  paths were staged.

## 7. Remaining limitations (disclosed, not fixed)

- **F-2: two always-mounted alert pollers**, as disclosed by the previous
  milestone. Out of scope by instruction.
- The post-correction "Favorite this Visit" / tag controls still appear
  only on the active-item screen, as before. They are organization, not
  review truth, and adding them to the completion screen was outside
  "retain the confirmation and Undo".
- On the completion screen `Z` with no undo token does nothing, which is
  the existing behavior on the active screen.
- The native invalidated-token case was not exercised on Windows; it is
  covered by the browser spec against the same frontend and backend code.
- **Gate G is waived, not passed.** MockingBird must never be described
  as externally validated. The build is unsigned.

## 8. Classification

**A.**

- The defect is closed with red/green evidence, both by click and by `Z`,
  including shortcut isolation, typing-target protection and the honest
  superseded-token error.
- The complete default suite is 198/198 and all three separate
  configurations pass.
- The new candidate `d7e61c1` / `75d998f7…` is verified and accepted on
  native Windows. It supersedes `02443ea` / `785f3f37…`.

**Authorization returns to NONE.**
