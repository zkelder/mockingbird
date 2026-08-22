# Representative Species Evidence v1

Status: implemented (Decision A -- see "Decision" in the milestone's final
report). Visually connects a species summary (Today, Bird Log) to one real
piece of reviewed wildlife evidence -- "Northern Cardinal, [photo], 6
confirmed visits, Regular here, Feeder · 7-8 AM" -- without ever confusing a
provisional AI label, a sibling subject's evidence, historical timing, a
privacy-ineligible image, or synthetic resolution with authoritative
wildlife evidence. This is not a user-curated species profile-photo system:
selection is fully automatic, deterministic, and re-derived on every read.

## Truth contract

A representative image for a named taxon may only come from a Visit whose
*authoritative reviewed identity* resolves to that taxon -- the identical
truth precedence every other Place Activity Report / Bird Log fact already
uses (see "Report truth precedence" in
[place-activity-report-contract.md](place-activity-report-contract.md)). A
`SpeciesSuggestion` alone can never establish "this is the representative
Northern Cardinal": `ProductRepository.place_activity_report` only ever
gathers representative-evidence candidates from Visits it has already
classified `CONFIRMED_WILDLIFE` (the same taxon-resolution branch used to
build `TaxonReportEntry` itself), and `wildlife_journal_overview` only ever
gathers them from `_wildlife_journal_confirmed_records`' existing
`confirmed_bird`-outcome filter. Neither path is re-derived here; this
milestone adds no second truth-resolution rule.

Because nothing is persisted (see "Schema" below), a human correction is
reflected on the very next report read with no backfill: the corrected
Visit's evidence simply stops being gathered under the old taxon's label and
starts being gathered under the new one.

## Evidence contract

Every representative-evidence candidate is exactly one already-confirmed
Visit's own already-resolved primary/effective evidence frame
(`StreamVisitSummary.primary_evidence`) -- the same already-computed pick
the Evidence Gallery, Bird Log, and Wildlife Insights already reuse (see
`ProductRepository._stream_visit_summary_from_models`). "Effective primary
evidence" (tier 1 of the product brief's preference order) is therefore
satisfied by construction, not re-derived: this milestone does not
re-implement `mockingbird.motion.effective_primary.select_effective_primary`
(a separate, heavier, on-demand Evidence-Gallery *preview/recommendation*
tool, `creates_truth=false`, never used by any report) and does not build a
second per-Visit "which frame is primary" cascade. A Visit whose own primary
frame turns out unusable (deleted media -- see "No-image semantics" below)
simply contributes no candidate; this milestone does not fall back to a
different frame within the same Visit, since containment/edge-clipping were
already enforced upstream, at capture time, by whichever mechanism marked
that frame primary in the first place (`evidence_scoring`/curation).

No new camera captures, no classifier inference, and no image
generation/upscaling are ever performed to produce a representative image.

## Canonical selector

`mockingbird.analytics.representative_evidence.select_representative_evidence`
is the one pure, deterministic ranking function -- reused, unmodified, by
both Today and Bird Log (see "Backend architecture" below). Given a bounded
list of `EvidenceCandidateFact`s (one per qualifying Visit), it orders by:

1. genuine, *proven* native/source resolution (`GeometryAttribution.
   resolution_provenance == "synchronized"` -- see "Source-resolution
   interaction" below);
2. a resolved subject region over a raw, uncropped full frame;
3. subject pixel size;
4. overall asset pixel size;
5. capture recency;
6. Visit id / media asset id, as a final, arbitrary-but-stable tie-break.

Sharpness/exposure are deliberately not ranking fields: `mockingbird.
observation.evidence_scoring` computes them once, at capture time, to help
choose each Visit's own primary frame, but never persists that score per
asset (`creates_truth=false` shadow evidence -- see
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md)).
Recomputing them here would mean decoding image bytes during report
computation, which every caller of this module must not do (see
"Performance" below). Human truth determines *taxon eligibility* (the truth
contract above); evidence quality, ranked here, determines *which image*.

## Source-resolution interaction

Reuses the accepted source-resolution evidence path exactly: `VisitEvidenceFrame`
now carries the asset's own already-persisted `GeometryAttribution.
resolution_provenance`, read back verbatim (`mockingbird.observation.
localization_attribution.geometry_attribution_from_json`) at the same point
every other `VisitEvidenceFrame` is already constructed --
`ProductRepository._visit_evidence_frame_from_link_and_asset`. This
milestone does not reimplement source-resolution/FOV-alignment ranking and
never claims an image is native unless its own provenance says so: only
`"synchronized"` (a genuinely separate, higher-resolution capture with
*proven* field-of-view alignment) counts as `is_native_resolution` for
ranking purposes; `"exact_same_frame"`/`"near_time_capture"`/`"fallback"`
describe temporal/identity trust, not resolution, and are never conflated
with a resolution claim. Analysis-resolution evidence with no attribution at
all (`resolution_provenance is None`, the ordinary case) remains a fully
valid representative -- native evidence is never required.

## Multi-subject correctness

Mandatory after Multi-Subject Visit Assembly (see
[multi-subject-visit-assembly-review-v1.md](multi-subject-visit-assembly-review-v1.md)):
for one Event containing sibling Visits (a Cardinal and a Finch that
appeared simultaneously and now share one `EventModel` row), each taxon's
representative image may only come from its own Visit's own evidence.
Guaranteed by construction, not by a special case: every representative-
evidence candidate is built from `summary.primary_evidence`, which
`_stream_visit_summary_from_models` resolves through `_visit_evidence_
frames_from_visit` -> `_visit_evidence_link_models(session, visit.id)` -- a
plain `visit_id`-keyed query, never `event_id`-keyed, so a sibling's
evidence is structurally unreachable regardless of relative quality. See
`tests/test_place_activity_report_repository.py::
test_multi_subject_sibling_representative_evidence_never_crosses_visits`
for the direct proof (the Cardinal sibling is deliberately given the
*higher-quality* evidence, so a bug that leaked "the Event's best evidence"
across Visits would be caught immediately).

## Privacy

Reuses the existing media-serving/privacy boundary exactly -- no second,
new privacy check was added, and none was needed. Direct verification
against the real routes (`GET /api/media/{id}/preview|file|full-resolution`,
`src/mockingbird/api/main.py`) confirms none of them, nor the repository
calls behind them, filter by Zone at read time: per
[privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md), a
Privacy/Ignore Zone is *trigger-level exclusion only* -- it prevents a Visit
whose only trigger was inside that Zone from being created at all
(`blocked_privacy_zone`, before any `MediaAsset` file is even written), but
never redacts or hides an already-legitimately-admitted Visit's evidence
afterward. Representative-evidence selection reuses exactly this same
boundary: it only ever reads already-persisted `VisitEvidenceLinkModel`
rows belonging to already-admitted Visits (the identical evidence path the
Evidence Gallery/Bird Log already expose), so a privacy-blocked candidate
-- which never became a Visit or a `MediaAsset` in the first place -- is
structurally unreachable, and a legitimately-admitted Visit's evidence is
displayed exactly as it already is everywhere else in the product. See
`test_representative_evidence_reuses_the_existing_privacy_boundary_not_a_
new_one` for the direct proof that this milestone did not (incorrectly)
invent a *stricter* rule than the rest of the product enforces.

## Time scope

**Today** (`ProductRepository.place_activity_report`) gathers representative-
evidence candidates only from Visits inside the report's own explicit
`[start_at, end_at)` period -- the identical Visit rows the report's own
`compute_place_activity_report` already resolves into `TaxonReportEntry`,
gathered in the same pass at zero additional query cost. Deliberately no
historical fallback: a taxon confirmed only outside today's period simply
gets `representative_evidence = None` today (the taxon entry itself is
already period-scoped, so this is consistent, not a special case) rather
than needing new UI wording to honestly disclose an image's true capture
date. This was evaluated against the milestone brief's own conditional
allowance for a clearly-labeled historical fallback and rejected as an
unnecessary complication for a "SMALL integration milestone, not a new
evidence architecture" brief: Today's report-first, calm surface (see
"Today UI" in the milestone instructions) has no natural place for a second
"not from today" caption without adding new UI complexity this milestone
explicitly avoids, and product-doctrine.md's own "Derived insights... must
remain reproducible from persisted facts" is best served by the simpler,
unambiguous rule "Today only ever shows today's own evidence."

**Bird Log** (`wildlife_journal_overview`) has no period restriction at
all -- it is already a historical browsing surface, and its representative
selection reuses the exact same taxon-scoped Visit history
`_wildlife_journal_confirmed_records` already gathers. Temporal provenance
is already explicit: `WildlifeJournalRepresentative.observed_at` (unchanged
by this milestone) always carries the real capture date, and Bird Log's
existing UI already surfaces dates throughout, so no new field was needed
for honest presentation.

## Selection policy / tie-breakers

See "Canonical selector" above for the exact ordered tuple. "Effective
primary status" is satisfied by construction (every candidate already is a
Visit's own primary evidence) rather than being a ranking field; "crop
completeness" is approximated by "has a resolved subject region" (the
cheapest honest proxy available without re-deriving edge-clipping, which was
already enforced upstream); "review recency" was considered and rejected in
favor of "capture recency" alone, since a second recency axis would not
meaningfully change the ranking and capture time is what a photo caption
actually means to a viewer.

## No-image semantics

A reviewed species with no safe persisted evidence is a completely normal,
valid report entry: `representative_evidence = None`
(`PlaceActivityReportTaxonEntry`/API), never an error, and the taxon is
never dropped from the report. This is the honest outcome for: a purely
provisional taxon (no confirmed Visit yet), a confirmed Visit with zero
evidence frames at all, and a confirmed Visit whose only evidence's
underlying file is missing/deleted from disk
(`Path(asset.local_path).is_file()`, checked once per candidate, never
during bulk historical scans -- see "Performance" below). The frontend
renders no image (Today) or the existing calm `journal-thumbnail-fallback`
placeholder (Bird Log) in this case -- never an error state.

## API shape

Additive, bounded, and reuses the exact `VisitEvidenceFrame` shape/
serialization the Evidence Gallery and Bird Log already use (never a
second, drifting evidence representation), adding only the one fact a bare
frame does not carry on its own:

```
representative_evidence: {
  visit_id: string,
  evidence: VisitEvidenceFrame   # media_asset_id, preview_url, captured_at,
                                  # evidence_role, width, height,
                                  # normalized_crop_box, normalized_track_box,
                                  # resolution_provenance (new field)
} | null
```

`VisitEvidenceFrame.resolution_provenance` (new, additive, `None` for every
pre-existing frame construction path that has no recorded attribution) is
the one field added to the shared frame shape, since it benefits every
existing consumer (Evidence Gallery, Bird Log's own pre-existing
`representative.primary_evidence`) for free, not only this milestone's new
field. No filesystem path is ever exposed (`VisitEvidenceFrame` already
excludes it); no separate byte endpoint was invented --
`evidence.preview_url` is the same, already-existing `GET /api/media/{id}/
preview` route every other evidence image already uses. An explicit
`source_dimensions`/`crop_dimensions` pair (as sketched in the milestone
brief) was considered and simplified away: `VisitEvidenceFrame.width`/
`height` plus `normalized_crop_box` already let a consumer derive pixel
crop dimensions if it ever needs to, and no consumer in this milestone's
scope does.

`PlaceActivityReportTaxonEntry.representative_evidence` (Today) is a new
field. `WildlifeJournalLabelSummary.representative` (Bird Log) is
*unchanged in shape* -- only its selection algorithm now delegates to the
same canonical selector (see "Backend architecture"), so Bird Log's
existing frontend automatically benefits with zero required frontend
changes, and `representative.primary_evidence.resolution_provenance`
carries the same new honesty for free.

## Backend architecture

```
reviewed Visit + evidence facts (StreamVisitSummary.primary_evidence)
  -> ProductRepository._representative_evidence_candidate  (per-Visit facts,
     bounded metadata-only checks: file-existence, geometry attribution)
  -> mockingbird.analytics.representative_evidence.select_representative_evidence
     (pure ranking, reused unmodified by both callers below)
  -> ProductRepository._representative_evidence_response
       |-- ProductRepository.place_activity_report (Today)
       `-- ProductRepository.wildlife_journal_overview /
           _wildlife_journal_representative (Bird Log)
  -> frontend (TodayReportPanel.tsx, BirdLogPage.tsx)
```

No image is ever selected inside React. No N+1: Today gathers every
confirmed Visit's already-resolved `primary_evidence` in the exact same
per-Visit pass that already builds `VisitFact`s (zero additional queries);
the one `session.get(MediaAssetModel, ...)` per candidate is a same-session
SQLAlchemy identity-map lookup, not a new round trip, since that exact row
was already loaded moments earlier while resolving `primary_evidence`
itself. `MAX_REPRESENTATIVE_EVIDENCE_CANDIDATES` (20) bounds how many of one
taxon's most-recent confirmed Visits are ever considered, so Bird Log's
unbounded reviewed history can never become an unbounded scan.

## Performance

No image bytes are decoded, and no image is rendered, during report
computation -- ranking uses only already-persisted metadata (`image_width`/
`image_height`, `normalized_track_box_json`/`normalized_crop_box_json`,
`geometry_attribution_json`) already loaded as part of resolving each
Visit's evidence. The one filesystem touch per candidate
(`Path(local_path).is_file()`) is a metadata `stat()` call, not a read, and
is bounded by `MAX_REPRESENTATIVE_EVIDENCE_CANDIDATES` per taxon -- never an
unbounded historical scan.

## Schema

No migration. Every fact this milestone reads (`VisitEvidenceLinkModel`,
`MediaAssetModel.image_width/height/normalized_track_box_json/
normalized_crop_box_json/geometry_attribution_json/local_path`) already
existed and was already durable. "The representative image for taxon X" is
never persisted as permanent truth -- recomputed from scratch on every
report read, so a correction, a newly-deleted media file, or newly-arrived
evidence is reflected on the very next read with no backfill step. This
product already has an established canonical persisted-primary concept
(`VisitEvidenceLinkModel.is_primary`, "effective primary evidence" for one
Visit); this milestone deliberately does not add a second, taxon-level
persisted-primary concept on top of it.

## Known limitations

- `ProductRepository._visit_evidence_frames_from_model` (the older, rarer
  live-stream-motion-session-config-JSON evidence path, used only when a
  Visit has zero `VisitEvidenceLinkModel` rows and a matching legacy
  `MotionEvidenceModel`) does not populate `resolution_provenance` -- it
  defaults to `None`, an honest "not proven native" rather than a
  fabricated value, not a lie. Left untouched deliberately, to keep this
  milestone bounded; the dominant, modern evidence-link path is fully
  covered.
- The legacy one-frame fallback at the bottom of `_visit_evidence_frames_
  from_visit` (`visit.representative_media_path`-only Visits, predating
  live activity sequences) is unchanged for the same reason -- also
  defaults `resolution_provenance` to `None` honestly.
- Today's representative click/tap does not navigate to the backing Visit;
  Bird Log's existing gallery-image click-through (already Visit-scoped)
  was left as-is. Adding Today navigation would require threading a new
  callback prop through `DashboardPage.tsx` for a compact, non-interactive
  row -- judged not worth the added surface for this milestone's brief
  ("Click/tap may use the existing Visit/Evidence navigation *if
  trivial*").
- No alt-text/UI change was made to Bird Log's existing `JournalThumbnail`;
  its already-established `thumbnailAlt(label, observedAt)` helper already
  satisfies the accessibility requirement for the (unchanged) image it
  renders.
