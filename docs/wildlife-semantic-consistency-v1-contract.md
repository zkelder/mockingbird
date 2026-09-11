# Wildlife Semantic Consistency v1

Status: closes the cross-surface disagreement `docs/release-experience-
rehearsal-v1-report.md` Section 3.5 found and deliberately left unfixed
("Cross-surface disagreement on 'confirmed wildlife' for unresolved
species"), listed there as open item #1. Reviewed Wildlife Semantic
Consistency v1 milestone.

## The reproduced defect

A reviewed Visit whose species a human reviewer honestly could not
identify (a Fast Review "Unknown bird"/"Unknown animal" correction) read
differently across three real product surfaces for the identical fact:

- **Today** (`analytics.place_activity_report`): "Confirmed wildlife --
  species not yet identified" -- already correct, already shipped, already
  tested (see "Wildlife classification boundary" in
  [place-activity-report-contract.md](place-activity-report-contract.md)).
- **Bird Log**: "No confirmed wildlife observations yet."
- **Local Data**: counted in neither "reviewed wildlife" nor "reviewed
  other."

## The locked semantic contract

MockingBird already distinguishes, in doctrine (`product-doctrine.md`'s
Review Decision vocabulary: `unknown_bird`/`unknown_animal`) and in one
already-shipped implementation (`place_activity_report.py`), two facts a
reviewed Visit can separately establish:

1. **Wildlife presence confirmed** -- an authority-eligible `ReviewLabel`
   exists and the label resolves to a wildlife-category taxon, or to the
   dedicated `"unknown"` category (`unknown_bird`/`unknown_animal`/
   `ambiguous`): a human explicitly attested an animal was present.
2. **Species identity confirmed** -- the same, but the label additionally
   resolves to a real, named taxon (not the `"unknown"` category).

These are not the same fact, and this contract does not collapse them.
Corresponding to the milestone brief's own lettered cases:

- **A** (reviewed wildlife + reviewed species): both facts true. Unaffected
  by this milestone.
- **B** (reviewed wildlife + unknown species): fact 1 true, fact 2 false.
  This is the exact case that was inconsistent -- now consistent everywhere
  (see "Surfaces changed," below). Never fabricated into a named taxon,
  historical "new"/"regular" verdict, or per-species Bird Log entry.
- **C**/**D** (inferred presence, with or without an inferred/abstained
  species): governed entirely by the existing, untouched identification-
  eligibility/abstention policy (`species/identification_eligibility.py`)
  -- an unreviewed Visit never becomes Reviewed by this contract, and
  nothing here changes when automatic identification runs or abstains.
- **E** (rejected/non-wildlife): `false_positive`, `blank`, or a
  non-wildlife-category taxon (person/vehicle/pet/object). Never confirmed
  wildlife on any surface, before or after this milestone.

No new epistemic class was introduced. `confirmed_unidentified_wildlife`
(the new `VisitReviewOutcome` value) reuses the identical concept
`ResearchClassification.confirmed_unidentified_wildlife`
(`research/eligibility.py`) and `analytics.place_activity_report`'s
`CONFIRMED_SPECIES_UNRESOLVED`/`confirmed_species_unresolved_visit_count`
already established and shipped.

## Root cause

**One resolver, `ProductRepository._visit_review_outcome`, mapped
`unknown_bird`/`unknown_animal`/`ambiguous` to `VisitReviewOutcome.
ambiguous`** -- the same bucket a genuinely uncertain, unresolvable
free-text label would produce. This resolver is the sole, shared source of
`StreamVisitSummary.review_outcome`, which Bird Log
(`_is_confirmed_wildlife_summary`), Local Data (indirectly, via a separate
but analogous taxonomy-category check in `_storage_visit_is_wildlife`), the
Dashboard's recent-activity label, Activity Library, and Wildlife Insights
all read. `analytics.place_activity_report` never consults this resolver at
all -- it resolves the taxonomy category directly -- which is precisely why
it alone had the correct, doctrine-consistent answer already. Reconciling
the disagreement meant making the shared resolver agree with the one
surface that already had it right, not inventing a third answer.

## Surfaces changed

- **`_visit_review_outcome`** (`product_repository.py`): now returns the
  new `VisitReviewOutcome.confirmed_unidentified_wildlife` for
  `unknown_bird`/`unknown_animal`/`ambiguous`/`unknown` (by literal key, and
  by taxonomy category for any future custom label under category
  `"unknown"`), never `ambiguous`. Two other direct readers of
  `VisitReviewOutcome.ambiguous` (Activity Library's `ambiguous_unknown`
  in-memory filter match, Wildlife Insights'
  `ambiguous_or_unknown_count`) were updated to read the new value instead,
  so neither silently lost these Visits.
- **Bird Log** (`wildlife_journal_overview`): a new
  `WildlifeJournalOverviewResponse.confirmed_species_unresolved_visit_count`
  field, computed the same way Today's own field is (never grouped into
  `labels` as a fake species -- `_is_confirmed_wildlife_summary`'s existing
  "never fabricate a taxon" contract is unchanged). The frontend
  (`BirdLogPage.tsx`) surfaces this as a distinct, honestly-labeled
  "Unidentified wildlife" panel, separate from the per-species grid, and
  the empty state no longer claims "no confirmed wildlife observations"
  when this count is positive. Chosen over the milestone brief's
  alternative B ("Bird Log is species-only, say so") because Bird Log's own
  existing empty-state copy ("create a confirmed local wildlife
  observation") and doctrine's wildlife-inclusive framing already assume A;
  the code, not the intent, was the defect.
- **Local Data** (`_storage_visit_is_wildlife`): now also treats taxonomy
  category `"unknown"` as wildlife for storage-summary/retention purposes
  -- the "own dedicated confirmed-but-unresolved handling"
  `wildlife_taxonomy.is_wildlife_category`'s own docstring names as the
  correct place for a caller that needs this, since that shared predicate
  itself deliberately excludes `"unknown"` for taxon-reporting purposes.
  This is a deliberate, documented, one-category exception to "matches
  `is_wildlife_category` exactly," not a reversion of the prior
  consolidation that predicate exists to enforce for every other category.
  A side effect, not separately re-scoped: this Visit's secondary evidence
  now also follows the (longer) wildlife retention schedule rather than
  the "reviewed other" one, since both read the same corrected predicate.
- **Dashboard recent-activity label** (`DashboardPage.tsx`): a reviewed
  `unknown_bird` Visit no longer reads "Ambiguous or unknown outcome" --
  it reads "Confirmed wildlife -- species not yet identified," reusing
  Today's own established phrase verbatim.
- **Visit Detail** (`VisitDetailPage.tsx`) and **Event Detail**
  (`EventDetailPage.tsx`): both previously conflated "has a `reviewed_
  label`" with "species confirmed" (`isBirdReviewLabel` returns true for
  `unknown_bird`, by design, for a different purpose -- gating the
  species-review workflow/correction form, which correctly still applies).
  A new, additive `isUnidentifiedWildlifeLabel` taxonomy-category check
  (`taxonomy.ts`) distinguishes the two: an unidentified-wildlife Visit
  now shows "Wildlife confirmed -- species unknown" rather than a bare
  "Confirmed" badge, "Wildlife confirmed" rather than "Reviewed species:
  Unknown Bird," and "Ready for wildlife dataset export" rather than the
  species-specific claim, wherever species genuinely is not identified.
  Event Detail's "Reviewed species" count now excludes these Visits (a
  named-species-only count), matching the per-visit card wording.
- **Review Queue / Fast Review**: no change needed. `saveAndNext(
  "unknown_bird", ...)` already wrote the correct `reviewed_label`; the
  defect was entirely downstream, in how that label was later
  reinterpreted.

## What did not change

Detector behavior, BioCLIP thresholds, identification eligibility/
abstention policy, Gate A Visit construction, Bird Log's broad design,
taxonomy infrastructure, and every other analytics surface not named
above. `place_activity_report.py`/`analytics.historical_baseline` (already
correct) were read for reference and left untouched. Bird Log's per-
species drill-down/gallery and Place Story's representative-evidence
selector (`_wildlife_journal_confirmed_records`'s three other call sites)
are unchanged -- there is no named taxon for an unidentified-wildlife
record to drill into or represent, so continuing to exclude it from those
specifically per-taxon views is correct, not a residual gap.

## Remaining known inconsistencies (disclosed, not fixed here)

- **Activity Library's "Confirmed wildlife" tab** still excludes
  `unknown_bird`/`unknown_animal`/`ambiguous` (its SQL filter denies
  category `"unknown"`, matching `is_wildlife_category` exactly). This is
  not the same defect Bird Log had: Activity Library already has a
  separate, honestly-labeled "Ambiguous / unknown" tab that includes these
  Visits, so the fact is visible somewhere, just not doubly so. Left
  unchanged -- Activity Library is a developer-facing activity audit
  surface, not one of this milestone's named primary surfaces.
- **Wildlife Insights'** own `ambiguous_or_unknown_count` framing
  ("ambiguous or unknown," not "confirmed wildlife, species unresolved")
  was preserved exactly as it already behaved (see "Surfaces changed"),
  not re-examined for whether its own wording/placement has a similar
  first-glance-contradictory shape to Bird Log's former defect. Worth a
  glance in a future dedicated pass; not reproduced or required by this
  milestone's brief.

## Tests

`tests/test_wildlife_semantic_consistency_v1.py` (new) -- one canonical
four-Visit fixture (case A, case B, case E, and an unreviewed Visit),
reused across five tests: Today's own counts (regression guard),
Bird Log agreeing with Today on the identical fact, the precise reported
symptom (zero named species, one real confirmed-unidentified Visit, Bird
Log must not read "nothing confirmed"), Local Data's counts, and rejection
vs. abstention never conflating on any of the three surfaces.
`tests/test_storage_retention.py` and `tests/test_everyday_discovery_ux_
closure.py` were updated in place -- see their own diffs/docstrings for
what changed and why.
