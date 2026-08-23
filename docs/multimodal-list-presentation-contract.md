# Multimodal List Presentation v1

Everyday Discovery / Product Experience v2 (Phase B). Closes the bounded
gap the just-shipped "Multimodal Observation & Soundscape v1" milestone
explicitly disclosed rather than silently deferred: list-level
deduplication of a confidently-associated visual+acoustic pair inside
`ProductRepository.dashboard_summary`'s `best_moments`/`recent_activity`
and Bird Log's `wildlife_journal_history` gallery (see
[multimodal-observation-soundscape-v1-contract.md](multimodal-observation-soundscape-v1-contract.md)'s
own "Today / Bird Log integration" section).

## The problem

`VisitAssociationModel` (schema 46) already records, durably, when a
visual and an acoustic Visit are the same real-world encounter -- but
every list view (Today's Best moments/Recent activity, Bird Log's
gallery) rendered one row per Visit id, with no awareness of the other
side. A confidently-associated pair therefore looked like two
independent wildlife encounters, directly contradicting product-doctrine.md's
discovery-first, calm-by-default posture.

## The fix: presentation-only collapse, never a data change

`ProductRepository._bulk_multimodal_pair_summaries` resolves, in one bulk
query per list (never one query per row -- the exact N+1 shape "BioCLIP
Status / Review Queue Performance v1" already found and fixed once), each
candidate Visit's *strongest* association (`"associated"` always outranks
`"possible"`, mirroring `_strongest_multimodal_tier`'s existing rule).
`_collapse_associated_multimodal_pairs` (for `StreamVisitSummary`-family
lists: Today's `best_moments`/`recent_activity`) and `_collapse_
associated_multimodal_journal_observations` (for Bird Log's `Wildlife
JournalObservation` gallery) then apply four rules:

1. **Only `tier == "associated"` collapses.** A `"possible"` association
   always stays two separate, individually-visible rows -- matching
   doctrine's "possible association remains visibly uncertain or
   separate" requirement and the association engine's own defined
   confidence semantics (`multimodal_association.py`'s `AssociationTier`
   docstring).
2. **The partner must already be present in the caller's own list.** If a
   list's own existing eligibility/ranking rules would not have shown the
   partner anyway (out of the top-N, outside the requested page, etc.),
   collapsing would make that Visit's evidence disappear with nothing left
   pointing to it -- so the row is left exactly as it already was. This
   method never widens which Visits are eligible for a list; it only
   changes how many rows a pair that *both* independently qualified for
   occupies.
3. **Primary-row selection is deterministic and truth-safe.** If exactly
   one side of the pair still `needs_review`, that side is kept as
   primary -- an already-resolved partner's row must never hide the one
   side still genuinely needing a human's attention (Phase I). Otherwise
   (both reviewed, or Bird Log's gallery, which is confirmed-only by
   construction) the visual side is kept as primary, since evidence
   imagery is the center of the experience (product-doctrine.md). The
   *other* side is dropped from the list and named by the kept row's new
   `multimodal_partner.visit_id`.
4. **Nothing is deleted, superseded, or truth-decided.** Both Visits stay
   real, independently reviewable, and independently reachable rows in
   the database and via the Visit Detail page's own full association
   panel (`VisitDetailPage.tsx`'s "Also heard nearby"/"Also seen nearby").
   No `taxon_agreement` conflict is silently resolved into one species by
   this mechanism -- `multimodal_partner.taxon_agreement` is carried
   through unchanged (`"agrees"`/`"differs"`/`"not_comparable"`) for the
   frontend to represent honestly; reviewed truth (if any) still controls
   which species name is shown, exactly as `_effective_taxon_label`
   already established for the Visit Detail page.

## The wire contract

`StreamVisitSummary` (and therefore every subtype: `DashboardVisitSummary`,
`ActivityLibraryVisitSummary`, ...) and `WildlifeJournalObservation` both
gained:

- `evidence_modality: "visual" | "acoustic" | "seen_and_heard"` -- always
  resolvable for free from the Visit's own Event (`event_type ==
  "acoustic_observation_candidate"` -> `"acoustic"`, otherwise
  `"visual"`); a caller that opts into collapse may promote a row's value
  to `"seen_and_heard"`. An ordinary caller that never collapses (Zone
  Insights, Activity Library, Research Export, ...) always sees a plain
  `"visual"`/`"acoustic"` value and a `None` partner -- this is purely
  additive and changes no existing response shape's *values*.
- `multimodal_partner: VisitMultimodalPartnerSummary | None` -- present
  only on a collapsed (`"seen_and_heard"`) row: the absorbed Visit's id,
  the association `tier`, and `taxon_agreement`. Deliberately the compact
  list-row shape (id only, not the full nested `Visit`
  `VisitMultimodalAssociation` returns for the detail page) -- a list row
  stays cheap; a caller wanting the full picture already has Visit Detail.

Collapse is applied at exactly two call sites today: `dashboard_summary`'s
`best_moments` (collapsed *before* the top-6 truncation, so a genuinely
distinct 7th encounter can fill the slot a redundant second row would
otherwise have occupied) and `recent_activity`, and `wildlife_journal_
history`'s gallery (collapsed per page -- a pair that straddles a page
boundary collapses only on the page where both sides are visible, an
accepted bound matching every other pagination tradeoff already in that
method). Species-*grouped* surfaces (Today's `new_today`/`recent_
regulars`, Bird Log's overview grid) are unaffected -- each already shows
one row per taxon, not per encounter, so the two-rows-for-one-encounter
defect does not apply there.

## Ordinary-language wording (Phase J overlap)

Frontend rendering uses "Seen" / "Heard" / "Seen and heard" (not
`evidence_modality`'s own raw values) as the list-badge vocabulary, and
reuses Visit Detail's existing "Evidence agrees"/"Evidence differs"/"Needs
review" phrasing for `taxon_agreement` wherever a collapsed row's badge is
expanded -- see [suggestion-explanation-contract.md](suggestion-explanation-contract.md)
for the full plain-language contract this phase shares with Phase J.

## Tests

`tests/test_multimodal_observation_acceptance.py`'s Scenario 10 family
(`test_scenario_10_confident_association_collapses_to_one_today_row_seen_and_heard`,
`test_scenario_10b_possible_association_stays_two_separate_rows`,
`test_scenario_10c_confident_association_collapses_in_bird_log_gallery_too`)
exercise this end to end through the real `dashboard_summary`/`wildlife_
journal_history` repository methods against the same deterministic
acceptance-corpus fixtures Scenarios 1-9 already use -- proving collapse,
non-collapse, and that both underlying Visits remain independently real
and reachable afterward.
