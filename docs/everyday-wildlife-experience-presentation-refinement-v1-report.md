# Everyday Wildlife Experience & Presentation Refinement v1

Status: implemented locally, **acceptance pending** (not pushed). Authorized by
the owner's bounded-refinement brief at HEAD `1575b3f`, schema `v62`.
Presentation and selector-unit correctness only: no detector/model change, no
schema change, no new identification feature, no change to review authority.

Primary journey this serves: Open MockingBird -> see wildlife -> inspect a
Visit -> confirm, correct, or abstain -> find that observation again.

## What changed, by workstream

### A. Visual correctness
- **Today "Recent activity" thumbnails overlapped.** The preview wrapper is a
  direct child `<div>` of the visit row, so the generic `.dashboard-visit-row >
  div { flex: 1 1 auto }` rule overrode its fixed 82x62 box and the image
  rendered at natural height over the rows below. It is now pinned to a clipped
  fixed box. The regression test fails without the CSS fix (image measured 156 px).
- **1969/1970 placeholder dates.** Alerts and Local Data (oldest managed media)
  rendered an epoch-anchored instant as a date ("Dec 31, 7:00 PM",
  "12/31/1969"). They now say "Capture time unknown" / "Time not recorded".
  The guard mirrors the server's own placeholder prefilter
  (`CAPTURE_TIME_PLACEHOLDER_PREFILTER_CEILING`, 1971-01-01). No timestamp is
  invented.

### B. Visit and review experience
- Visit detail now leads with the wildlife image beside a single **decision
  panel**: "Is this a *Name*?" with the guess labelled "MockingBird's guess --
  not confirmed", other possibilities, the species field (shown by display
  name, never the taxonomy key), and **Confirm species / Change / Not sure**.
  The primary decision is inside the first 1440x900 viewport.
- **Not sure** saves an honest `unknown_bird`/`unknown_animal` through the same
  explicit review-label path (the precedent is Fast Review's one-click
  "Unknown bird") and never marks a prefilled suggestion accepted.
- Moved behind progressive disclosure, nothing removed: "More suggestions &
  help identifying" (Identification Assistant, ranked suggestions),
  "Visit details, evidence trail & export readiness" (summary cards, source
  evidence trace, media provenance, suggestions-as-evidence, correction
  history, high-resolution crop editor, export actions), "Notes, collections &
  tags". Visit curation was already a disclosure. The frame a species
  suggestion was actually based on stays visible beside the decision.
- Review Queue cards: no MIME type/byte size, no candidate-pack name, no
  "MockingBird saw: animal"/raw detector score by default. A card with an
  explicit suggestion leads "Likely *Name* -- needs your check" (still plainly
  provisional, "Evidence only."). Technical facts remain under "Advanced
  evidence".
- Fast Review: the four label/value context cards became one sentence; the
  Identification Assistant shows display names ("Best match", "Option 2"), and
  its model-input/candidate-pack/truth-boundary table moved under "How
  suggestions work".

### C. Wildlife imagery
- **Defect fixed in the canonical selector's input.**
  `resolve_subject_region` now measures a subject in the frame's own pixels. A
  derived crop's `normalized_crop_box` is parent-relative; the crop image is
  already the subject, so its area is its own pixel area (previously its
  dimensions were scaled by the parent-relative fraction a second time, so a
  wide frame with a tiny speck could outrank a clean subject-centred crop). A
  crop under 64 px short side earns no credit; malformed boxes are ignored.
  See [representative-species-evidence-contract.md](representative-species-evidence-contract.md).
- Truth precedence is unchanged (candidates still come only from confirmed
  Visits; the existing precedence/sibling/provisional tests pass).
- Presentation: `subjectFraming.ts` centres a *server-vouched* track box with
  generous padding, shows crops whole, and shows small sources whole on a soft
  backdrop instead of stretching them. Applied to Bird Log, Today species
  thumbnails, and the Taxon/Feature story thumbnails.

### D. Calm hierarchy
- Today: the empty "Biodiversity here" card and the "long-term patterns will
  appear" Year-over-Year placeholder are omitted on Today until there is
  something to say (the Place report keeps both). The three optional Place
  prompts (location, habitat, features) are one collapsed "About your place"
  line until any of them is recorded.
- Insights: with no confirmed wildlife the grid of zero cards and the
  "same as previous period" (0 vs 0) notice are replaced by the one actionable
  empty state, which now states how many Visits wait for review; non-zero
  figures only otherwise; the review-context breakdown is on demand.
- Local-only status, abstention wording, export eligibility, and the review
  warnings (custom label not in the species list, evidence-only) are intact.

### E. Navigation and rediscovery
Evaluation of the six-destination model against the existing routes: it fits
with no route removed or renamed. Primary: **Today, Cameras, Review Queue, Bird
Log, Place, Settings**. Secondary list under the active destination:

| Destination | Secondary pages |
|---|---|
| Cameras | Cameras, Import Media (camera setup/configuration/detail keep it highlighted) |
| Bird Log | Bird Log, Activity Library (Collections keep it highlighted) |
| Place | Place Story, Place Report, Insights, Ecological Destinations (Taxon/Feature stories keep it highlighted) |
| Settings | Local Data, Users (admin), Doctor (admin) |

Role gating is unchanged. Developer Mode tools and the "Recently opened" entries
are untouched. Place data model and insights are not changed.

Bird Log rediscovery: "Find a species" (client-side over the loaded overview,
shown from 4 species) and a "Recently seen" strip (from 6 species; a species
whose latest time is the recorded-video placeholder never claims a recency slot).

## Deliberately not done
- No schema/backend contract change; `resolve_subject_region` is a pure
  function the repository calls, with no change to the selector's ordering.
- Place sub-navigation inside pages was not consolidated (it would rewrite
  established features).
- The Fast Review outcome buttons were kept as-is (existing actions and
  keyboard shortcuts).

Validation results, screenshots, the native-Windows record, and remaining
gaps are in the scheduler entry in
[release-execution-state.md](release-execution-state.md).
