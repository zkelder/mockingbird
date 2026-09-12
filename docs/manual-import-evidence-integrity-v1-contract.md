# Manual Import Evidence Integrity v1

Status: closes the pre-existing correctness gap disclosed alongside the
accepted Reviewed Wildlife Semantic Consistency v1 milestone -- a Visit
created through `/api/media/import` (or its batch sibling,
`/api/media/folder-import`) could have its own legitimate, reviewed media
misreported as orphaned. Manual Import Evidence Integrity v1 milestone.

## The reproduced defect

Every Visit-creation path in `product_repository.py` that sets a Visit's
`representative_media_path` to a real media asset also creates a
`VisitEvidenceLinkModel` row for that same asset -- except one.
`_create_media_product_records` (the shared helper behind both
`create_media_import` and `import_folder_media`) set
`representative_media_path` and never created the matching link.

`storage_summary()` and the retention/cleanup evaluator both derive
ownership from `VisitEvidenceLinkModel`, not from `representative_media_
path`. So an imported Visit's media -- even a reviewed one, named-species
or confirmed-unidentified-wildlife -- could be classified as **orphaned**
in the Local Data storage summary, contradicting the fact that a
legitimate, reviewed Visit depended on it.

## Root cause and blast radius

- **Retention/deletion was already safe.** `_storage_retention_evaluation`
  (the single evaluator behind every storage-cleanup preview/execute call
  site) already had a dedicated `legacy_representative_evidence` /
  `superseded_only_evidence` fallback for exactly this "Visit has
  `representative_media_path` but no link" shape -- added by an earlier
  milestone (see `tests/test_storage_retention.py`'s "Defect 1" block) and
  explicit that this evidence follows "the same active/superseded/
  reviewed rules as any other Visit-linked evidence -- no separate
  contract." Nothing was ever wrongly deleted.
- **`storage_summary()` had no matching fallback.** It derived active/
  superseded/orphaned entirely from `VisitEvidenceLinkModel`, so it
  disagreed with the (correct) retention evaluator about the exact same
  asset. This is a presentation/truth-telling defect, not a data-loss one.
- **Zero automated test coverage existed for `orphaned_managed_media_
  count`** anywhere in the suite before this milestone -- a contributing
  reason the disagreement went unnoticed.
- **`effective_primary_preview`** (a Visit Detail "suggested better
  primary frame" recommendation, `product_repository.py`) also derives
  entirely from `VisitEvidenceLinkModel` and would return no suggestion at
  all for an unlinked imported Visit. Benign (no truth or safety issue,
  just a missing recommendation) and resolved by the same fix below.
- **Visit Evidence Gallery was already fine.** `_visit_evidence_frames_
  from_visit` already had its own legacy fallback straight to
  `representative_media_path` when no link and no `MotionEvidenceModel`
  exist, so the evidence gallery already rendered imported media
  correctly. Untouched.
- **Out of scope, disclosed only:** `_create_detection_proposal_review_
  records` (a different feature -- admitting a raw detector proposal as a
  reviewed candidate Visit) sets `representative_media_path` the same way
  and also never creates a link. Not a manual-import path, so its code is
  untouched here; any historical row it left in this shape is covered by
  the same generic backfill below, since the backfill is not scoped to
  import-created Visits specifically.

## The fix

1. **New imports** (`product_repository.py`, `_create_media_product_
   records`): after creating the asset/event/Visit, call the established
   `_ensure_visit_evidence_links` materializer -- the same one `curate_
   visit_evidence`, `create_refined_visit_crop`, `promote_visit_crop_
   history`, and `split_visit` already rely on -- instead of inventing a
   second evidence-link mechanism. Same transaction as the rest of the
   import; a failed/rolled-back import leaves no link behind either.
2. **Presentation parity** (`_compute_storage_summary`): fold in any Visit
   an asset has no link to but that still names it via `representative_
   media_path` (via the new shared `_storage_legacy_representative_
   visits` helper, also now used by `_storage_retention_evaluation`
   itself), so the summary's active/superseded/orphaned split can never
   again disagree with the retention evaluator's own. This makes existing,
   not-yet-repaired imports read correctly immediately, without waiting on
   the backfill below.
3. **A latent retention gap, closed defensively:** folding a real
   `VisitEvidenceLinkModel` into new imports means `_storage_retention_
   evaluation`'s old `legacy_representative_visits and not links` fallback
   -- gated on the asset having *zero* links -- would stop protecting a
   *different* Visit that names the same asset only via `representative_
   media_path` once *any* Visit has a real link to it. `representative_
   media_path` carries no uniqueness constraint, so this shape, while
   never produced by any current product code path, is not something the
   schema forbids either. Closed with one additional guard: any Visit
   found only via `representative_media_path`, not already reachable
   through a real link, that is still active protects the asset exactly
   like `active_visit_primary_evidence` does. Verified against the
   existing defensive test for this exact shape (`test_legacy_
   representative_media_shared_by_two_visits_protected_until_all_
   superseded`), which passes unmodified.
4. **Existing data: report + confirm-gated repair, not an automatic
   rewrite.** `GET /api/media/evidence-link-repair-report` (read-only) and
   `POST /api/media/evidence-link-repair` (`{"confirm": true}` to apply) --
   mirroring this repo's existing `scripts/repair_review_label_
   provenance.py` maintenance-command pattern: talk to a running instance
   over its real HTTP API, dry-run by default, reuse the same validated
   repository logic a live product action would. Backing repository
   method: `ProductRepository.repair_visit_evidence_links`. It is
   deliberately **not** scoped to Visits created by an import specifically
   -- the condition it acts on ("has `representative_media_path`, has no
   VisitEvidenceLink, resolves to exactly one known asset and Event") is
   the same established ownership rule everywhere else in this contract,
   regardless of which code path produced the row. It:
   - creates a link only when `representative_media_path` resolves to
     **exactly one** media asset (never guesses across more than one, and
     `local_path` carries no database uniqueness constraint of its own, so
     this is checked explicitly rather than assumed);
   - never touches a Visit that already has a link (`already_linked`);
   - reports, and leaves untouched, anything it cannot resolve
     unambiguously (`ambiguous_no_asset_match`, `ambiguous_multiple_
     asset_match`, `ambiguous_missing_event`, `ambiguous_no_evidence_
     derivable`);
   - never deletes anything and never rewrites `representative_media_
     path` or any reviewed truth.
   - Companion script: `scripts/repair_import_evidence_links.py`.
5. **Wildlife Insights wording** (`WildlifeInsightsPanel.tsx`): the
   "Review-quality outcomes" line labeled its `confirmed_unidentified_
   wildlife` count "ambiguous/unknown" -- read like genuine uncertainty
   about a Visit that was in fact reviewed and confirmed, echoing Bird
   Log's fixed defect from the prior milestone. Reworded to "confirmed
   wildlife, species unresolved" (the exact phrase Wildlife Semantic
   Consistency v1's own contract doc named as the correct alternative).
   No count or field changed -- `ambiguous_or_unknown_count` still means
   exactly what it meant before; only the displayed word changed.
6. **Activity Library "Confirmed wildlife" filter: left disclosed, not
   fixed**, per that same prior contract's own explicit reasoning --
   Activity Library already has a separate, honestly-labeled "Ambiguous /
   unknown" tab that includes `confirmed_unidentified_wildlife` Visits, so
   the fact is visible somewhere, just not doubly so. Making "Confirmed
   wildlife" also include them (a one-line change, mechanically) would
   make those Visits appear in *both* tabs, since the "Ambiguous / unknown"
   tab was not itself narrowed -- whether these tabs should remain a
   strict partition or become overlapping predicates is a product/UX
   decision the accepted contract did not make. Left as-is rather than
   expanding scope.

## What did not change

Detector behavior, BioCLIP policy, review authority, import UX/API request
shape (`MediaImportResult`/`FolderImportResult` response shapes are
unchanged), retention policy defaults, Activity Library's filter
semantics, and every surface not named above.
