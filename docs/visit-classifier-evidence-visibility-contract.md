# Visit Same-Frame Classifier Evidence Visibility v1 contract

Status: direct continuation of Same-Frame Species Evidence v1 (`docs/same-
frame-species-evidence-contract.md`), which persists a `classifier_
same_frame` MediaAsset and wires it into BioCLIP's own input resolution, but
deliberately never surfaces it anywhere a human reviewer looks (see "Non-
promotion" in that contract). This milestone closes exactly that gap: a real
field Visit (`visit-observation-candidate-022`, 2026-08-16) proved the gap is
not theoretical -- BioCLIP suggested "House Finch" at 99.1% confidence from
the classifier's actual same-frame input, while the Visit's own displayed
"identification" evidence (a separate, later burst capture, `same_frame:
false`, `geometry_evidence_gap_ms: 3358`) happened to show an empty yard: the
bird had already left the feeder by the time the physically separate burst
fired. A correct, high-confidence suggestion looked unsupported.

## Boundary

This is an evidence-*visibility* contract, not a new evidence-persistence,
resolver, or admission-policy change. It:

- reads the exact `classifier_input` provenance Same-Frame Species Evidence
  v1 already persists on `SpeciesSuggestionModel.evidence_region_json`
  (`ProductRepository._classifier_supporting_evidence_from_session`), never
  re-derives or re-resolves it;
- exposes the referenced MediaAsset through the existing `VisitEvidenceFrame`
  serialization/`/api/media/{id}/preview` convention, reused verbatim;
- adds one new, additive `VisitDetail.classifier_supporting_evidence` field
  and one new `ClassifierSupportingEvidence` schema -- no migration, no new
  table, no new evidence subsystem;
- adds one new frontend panel (`VisitDetailPage.tsx`, "Species suggestion
  evidence") that reuses `VisitEvidenceSequence`/`useEvidenceZoom` wholesale
  for rendering/zoom -- no new image-viewer code.

It does **not** change the species suggestion itself, the classifier-input
resolver (`species/classifier_input.py`), which asset BioCLIP actually reads
pixels from, Visit assembly/admission, or the Dashboard/Today report.

## Source of truth: the suggestion's own recorded provenance, not a fresh query

`_classifier_supporting_evidence_from_session` reads `classifier_input.
source_media_asset_id` off the Visit's *latest* SpeciesSuggestion (same
ordering/pick as `mockingbird.api.main._latest_species_suggestion_for_visit`
-- the same suggestion a reviewer already sees as current), never by
independently querying "does a `classifier_same_frame` asset exist for this
Visit." The two are not equivalent: `_classifier_input_override` may reject
an existing same-frame asset (eligibility/quality checks) and fall back to
full frame, in which case the suggestion's own `evidence_region` carries no
`classifier_input` key at all -- exposing the same-frame asset anyway in
that case would show evidence that was not actually what produced the
suggestion. Reading the suggestion's own persisted decision is the only way
to stay honest about "why this suggestion was made."

## Avoiding duplicate-image clutter

Before returning anything, the referenced asset's id is checked against the
Visit's own ordinary `evidence_frames` (by asset identity, via the same
`_visit_evidence_frames_from_links` the gallery itself uses -- never a
pixel/visual comparison). If already present, the field is `null`: nothing
distinct exists to show. In practice this only ever matters for the dormant
`persisted_crop` resolver tier (an `activity_crop`/`user_refined_crop`
asset, which -- unlike `classifier_same_frame` -- is *not* excluded from the
ordinary gallery); a `classifier_same_frame` asset is structurally always
absent from `evidence_frames` (Same-Frame Species Evidence v1's own "Non-
promotion" guarantee), so the common real-world case always exposes it.

## Subject-box overlay: a narrower, stronger gate than the ordinary gallery's

The ordinary gallery's `normalized_track_box` (`_frame_local_subject_box`)
requires `alignment_status == "aligned"` -- a legacy signal reconciling two
*different* camera profiles that Observation-Engine-produced assets never
set (confirmed empirically: real candidate-Visit `evidence_frames` return
`normalized_track_box: null` today, box or no box). A `classifier_same_
frame` asset does not need that reconciliation -- it *is* the exact frame
the tracker's own box was computed against, proven at capture time via
`geometry_attribution_json.same_frame == True` (Same-Frame Species Evidence
v1's own capture-eligibility check, not a timestamp guess). This contract
therefore gates the box on that stronger, asset-specific proof instead
(`geometry_attribution_from_json(asset.geometry_attribution_json).
same_frame is True`), so "Focus on evidence"/the tracked-region overlay
work for this panel even though they are unavailable on the ordinary hero
image today. Absent that proof, no box is shown -- the same safe default.

## Degradation (never raises, never blocks review)

`None` for every "nothing honest to show" case: no SpeciesSuggestion, no
`evidence_region`, no `classifier_input` key (full-frame fallback), a
missing/malformed JSON blob, a referenced asset that no longer exists, one
whose file has since been cleaned up by retention, or one that belongs to a
different Stream than this Visit's own (the same anti-leak check the
ordinary gallery applies). Existing historical Visits that predate Same-
Frame Species Evidence v1 entirely simply have no `classifier_input` key and
degrade the same way -- no rewrite, no backfill.

## Presentation

`VisitDetailPage.tsx` renders a calm, clearly-labeled "Species suggestion
evidence" panel (`EvidenceBadge label="Supporting evidence"`) directly above
the Species Suggestions list it explains, naming the specific suggestion
when the (independently-fetched) suggestions list has already loaded. It
reuses `VisitEvidenceSequence` with a single-frame array, so zoom/pan/focus/
full-resolution-upgrade and mobile layout are the exact same, already-proven
mechanics the primary evidence hero uses -- not a second implementation.
Never rendered on the Dashboard/Today report; only inside the existing
Visit-detail "needs review" surface, where species suggestions are already
shown today.
