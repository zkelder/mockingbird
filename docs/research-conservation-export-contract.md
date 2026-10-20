# Research / Conservation / Export Interoperability v1

## Purpose

MockingBird's reviewed wildlife history is trustworthy but, before this
milestone, could only leave the product through two narrow paths: the
reviewed-only Dataset Export (`DatasetExportModel`) and the classifier
training manifest export -- both aimed at *training*, not at personal
natural-history record-keeping, conservation summaries, field/research
workflows, or interoperable camera-trap datasets. Camtrap DP export,
research collaboration, and conservation reporting were explicitly deferred
by the previous milestone (see "Scope exclusions" in
[offline-recorded-media-observation-contract.md](offline-recorded-media-observation-contract.md)).
This milestone closes that gap.

**Research/export surfaces consume trusted product truth. They never create
it.** The authoritative chain remains: Source → Stream → acquisition/
coverage → Event → subject Visit → Evidence → Review Decision → Observation
→ export/report. Nothing in this milestone adds a second truth system, a
second admission pipeline, or a parallel review mechanism.

## Research truth invariant

Only authority-eligible reviewed truth may enter a "trusted/research-safe"
named-species export. A `SpeciesSuggestion` alone never becomes research
truth. See `mockingbird.research.eligibility.evaluate_research_export_
eligibility` -- the one place this decision is made, mirroring
`mockingbird.review_provenance.is_authority_eligible`'s own "one function
decides this" discipline.

Every record classifies into exactly one of:

- `confirmed_taxon` -- an authority-eligible reviewed Visit resolved to a
  named wildlife taxon. Eligible for a trusted named-species export.
- `confirmed_unidentified_wildlife` -- an authority-eligible reviewed Visit
  confirming *some* animal (`unknown_bird`/`unknown_animal`) while
  abstaining on species. Real natural-history data, never a fabricated
  species; eligible for a trusted export, honestly labeled unidentified.
- `non_wildlife` -- a real reviewed record (pet/person/vehicle/object).
  Never eligible for a *wildlife* research export, and never confused with
  `rejected`.
- `provisional_suggestion` -- an unreviewed Visit with only a
  `SpeciesSuggestion`. Never eligible as a trusted named taxon.
- `unresolved` -- unreviewed with no usable suggestion, or reviewed but the
  label did not resolve to any taxonomy row, or reviewed by a
  non-authoritative origin (agent-diagnostic/omitted provenance).
- `rejected` -- explicit false-positive/rejected truth.
- `superseded` -- a structurally superseded Visit (split/merge), or a
  historical (non-current) review-history row when an audit export walks
  full history. Excluded from the current-truth export table.

`ResearchExportEligibility.required_reasons` block export outright;
`.recommended_reasons` are disclosed completeness gaps (missing scientific
name, uncertain capture timestamp, no evidence media, unknown resolution
provenance) that never block an otherwise-eligible record -- see "Required
vs. recommended" in that module's docstring.

## Provenance contract

`mockingbird.research.research_export.ResearchObservation` is the one
provider-neutral exported-Observation shape -- a Camera Node, generic RTSP,
ONVIF, or offline/recorded-media Visit all produce the identical shape, with
only `acquisition_type`/`acquisition_provider` varying (see "ONVIF/RTSP/
Camera Node integration" below). It answers: logical Source/Stream,
acquisition type, capture timestamp and its confidence, Event (for
multi-subject lineage), Visit, reviewed taxon (label/display name/
scientific name/category), review history's current authority
(`reviewed_at`/`reviewed_by`), evidence/media identity (never a local
filesystem path), source resolution, subject-crop lineage
(`ResearchEvidenceRecord.is_crop`), resolution provenance, offline-vs-live
acquisition, and the full eligibility verdict.

`ProductRepository._research_observation_for_visit` builds one from a real
Visit, reusing the same canonical resolvers every other reporting surface
already relies on: `_stream_visit_summary_from_models` (per-Visit truth
resolution), `_visit_is_dataset_ready` (authoritative/current re-check,
mirroring reviewed-only Dataset Export), `_taxonomy_label_model_for_input`
(taxon resolution), and `_current_effective_review_label_model_for_visit`
(reviewer attribution). It never re-derives truth.

### Capture-timestamp confidence

`capture_timestamp_confidence` is `"recorded"` when the Visit's primary
evidence `MediaAssetModel.captured_at` is known, `"unknown"` when it is
`None` -- exactly the same signal `offline_ingest`'s own `capture_time_
known` already surfaces (see "Frame-time semantics" in
[offline-recorded-media-observation-contract.md](offline-recorded-media-observation-contract.md)):
a live capture's wall-clock time is essentially always known; a recorded
video whose source file carried no real timestamp metadata is honestly
epoch-anchored, and that uncertainty is retained here, never silently
resolved into a real-looking date.

### Acquisition type (known limitation)

`acquisition_type` is derived from `ObservationCandidateVisitModel.
provider_key` for the Visit: `"recorded-media-offline-ingest-v1"` maps to
`recorded_video`; any other real provider key maps to `continuous_live`. A
Visit with **no** `ObservationCandidateVisitModel` row at all -- the legacy
motion-evidence-promotion path that predates Observation Engine v2 candidate
authority, or a folder-imported still image promoted directly through that
same legacy path -- honestly reports `unknown` rather than a guessed value.
There is no reliable machine-readable "this was a still-image camera-trap
capture" signal for that legacy path today; closing it is a reasonable,
bounded, disclosed follow-up, not attempted here to avoid coupling this
module to an internal note-parsing convention (`_folder_import_note_
fields`) beyond the one place it is already load-bearing (offline
acquisition-effort accounting, below).

## Effort accounting

Conservation/research summaries distinguish **live monitoring effort**
(continuous-observation coverage) from **offline/recorded acquisition
effort** (bounded, per-file capture opportunities) -- see
`mockingbird.research.acquisition_effort`. The two are never summed into one
"coverage" figure.

- **Live**: reused unmodified from `MonitoringExposureIntervalModel` via
  `ProductRepository._place_activity_coverage_summary`/`_monitoring_
  exposure_intervals_and_history` -- the same durable ledger `place_
  activity_report`/`zone_insights` already trust. Usable-day count reuses
  `mockingbird.analytics.historical_baseline.bucket_intervals_by_local_day`/
  `usable_dates_from_daily_monitored_seconds`, the same primitives Historical
  Baseline Maturity already established -- never a second threshold.
- **Offline**: aggregated from `RecordedMediaAnalysisRunModel` (recorded
  video; deduplicated to the latest *completed* run per distinct
  MediaAsset, so a reprocessing attempt never double-counts) and
  folder-imported still `MediaAssetModel` rows (one capture opportunity
  each, never an implied duration or inferred deployment span from gaps
  between files).

Imported/recorded media **never** creates a `MonitoringExposureIntervalModel`
row -- unchanged from the previous milestone; this milestone only adds the
missing cross-run *reporting* aggregate the offline-ingest contract
explicitly deferred, without touching what either ledger measures.

## Conservation Reporting v1

`ProductRepository.conservation_report` (`POST /api/research/conservation-
report`, `mockingbird conservation-report`) answers "what was recorded here,
under how much defensible observation effort?" for an explicit period. It
never claims abundance, population size, occupancy, a biodiversity index,
ecological significance, or a decline/increase trend -- no such field exists
on `ConservationReportResponse`, and a structural test
(`test_conservation_report_never_exposes_a_population_or_percentage_field`)
locks this in.

Per confirmed species, `occurrence_note` uses the one sanctioned phrasing
(`mockingbird.research.conservation_report.format_occurrence_note`):

> "Northern Cardinal was confirmed on 8 of 12 usable monitored days."

never a percentage ("occupied the site 67% of the time") and never a
population/trend claim. The effort denominator (`live_monitoring_usable_
day_count`) is always visible alongside the numerator, and `None` (not a
fabricated `0`) when no durable coverage history exists yet for the period.

`ConservationReport` is a thin synthesis layer over an already-computed
`PlaceActivityReport` (see `mockingbird.analytics.place_activity_report`) --
an independent, additional caller of that module's own canonical resolvers,
not a second Visit-classification path, exactly the way `daily_digest.py`
already sits above the same report.

## Generic research export

`ProductRepository.export_research_dataset` (`POST /api/research/export`,
`mockingbird export-research`) writes a bounded local bundle:

```
observations.csv   observations.jsonl   media.csv
sources.csv         effort.csv           manifest.json
```

There is deliberately **no** separate `visits.csv`: in this schema a
reviewed Visit *is* the Observation (see product-doctrine.md's "Observation
(target durable object)" -- no distinct persisted Observation record exists
yet), so a second, near-duplicate table would only invite drift. `media.csv`/
`sources.csv` are deduplicated, deterministically ordered, and metadata-only
by default. `include_media` copies the eligible evidence bytes into `media/`
with a `media-bundle.csv` checksum/linkage table -- see
[research-export-ecological-workflow-completion-v1-contract.md](research-export-ecological-workflow-completion-v1-contract.md).

Every export carries reproducibility metadata (`manifest.json` /
`ResearchExportManifest`): schema version
(`RESEARCH_EXPORT_SCHEMA_VERSION`), `generated_at`, application version,
eligibility policy version, the exact filters used, in-scope source ids,
counts, a skip-reasons breakdown, and a deterministic sha256 content
fingerprint (`observations_content_fingerprint`) over sorted observation
ids/classification/taxon -- the same retained truth and parameters always
produce the same fingerprint (`test_generic_export_is_deterministic_and_
writes_metadata_only_files`), and a taxon correction changes it
(`test_fingerprint_changes_when_a_taxon_correction_changes_exported_truth`).
Export never mutates product truth (`test_research_export_does_not_mutate_
product_truth`) and writes atomically (temp directory, then rename) exactly
like the classifier manifest export precedent.

### Filters

`ResearchExportFilters`: `start_at`/`end_at`, `stream_ids`, `source_ids`,
`taxon_labels`, `acquisition_scope` (`live`/`offline`/`both`),
`collection_id`. Deliberately bounded, not a query language (see "Export
filters" in the governing milestone brief). There is no "trusted-only=false"
escape hatch: this export is always trusted-only by construction.

## Camtrap DP interoperability

Target spec version **1.0.2** (https://camtrap-dp.tdwg.org/) -- fetched
directly from the published site during this milestone; no Camtrap DP
material was previously vendored or referenced anywhere in the repository
(confirmed absent, not merely undocumented). See
`mockingbird.research.camtrap_dp`.

`ProductRepository.export_camtrap_dp_package` (`POST /api/research/export-
camtrap-dp`, `mockingbird export-camtrap-dp`) writes `deployments.csv`,
`media.csv`, `observations.csv`, and a bounded `datapackage.json`
descriptor.

### Mapping

| Camtrap DP | MockingBird |
| --- | --- |
| `deploymentID` | `f"{source_id}:{stream_id}"` -- deterministic, stable |
| `locationName` | explicit `site_name` export override, else Source name |
| `latitude`/`longitude` | `None` unless explicitly supplied at export time (see Privacy) |
| `deploymentStart`/`deploymentEnd` | bounds of the *exported* observation window for that deployment -- an honest "what this package covers," never a fabricated install/removal date (MockingBird has no deployment-lifecycle model) |
| `mediaID`/`timestamp`/`fileMediatype` | `ResearchEvidenceRecord` fields |
| `filePath` | a manifest-relative reference (`media/<id>.jpg`), never a local filesystem path; with `include_media=true` a row exists only for media actually bundled (omitted media has no row -- see the media-bundle contract) |
| `observationID`/`eventID` | Visit id (suffixed `-human`/`-machine`) / Event id -- preserves shared-Event lineage for multi-subject encounters |
| `observationLevel` | always `"event"` (a Visit is an event-level identification, not a per-frame classification) |
| `observationType` | `"animal"` for every included row (only eligible records are mapped at all) |
| `scientificName` | human-validated taxon only, `None` when unresolved -- never the machine suggestion |
| `classificationMethod`/`classifiedBy`/`classificationTimestamp`/`classificationProbability` | `"human"` row: reviewer identity, review time, **no** probability. A separate `"machine"` row (when a `SpeciesSuggestion` exists and `include_machine_classifications` is true): adapter name, suggestion time, suggestion confidence. Never blended. |
| `count` | never populated -- MockingBird has no individual-animal counting model (see "Wildlife-native semantics" in product-doctrine.md) |

Only research-eligible records are mapped at all (`ResearchExportEligibility.
eligible`); a provisional/unresolved/rejected/non-wildlife/superseded record
never becomes a Camtrap DP observation of any kind.

### Validation

`validate_camtrap_dp_package` is a bounded **structural** validator (not a
claim of full external Frictionless/Camtrap DP schema conformance -- no
external validator ecosystem was available to integrate hermetically for
this milestone): duplicate-id detection, deployment/media/observation
foreign-key resolvability, `deploymentEnd >= deploymentStart` and
`eventEnd >= eventStart`, and a human-row-never-carries-a-probability check.
Missing coordinates are reported as a disclosed **warning**, not an error --
a real, known non-conformance against the spec's own `latitude`/`longitude`
"required" constraint, honestly surfaced rather than silently passed or
fabricated.

## Privacy

- **No camera credentials, auth tokens, or absolute local filesystem
  paths** ever appear in `ResearchObservation`/`ResearchEvidenceRecord` --
  neither field type exists on those dataclasses (`test_no_camera_
  credential_or_local_path_ever_appears_in_an_observation`); media is
  referenced only by id and a manifest-relative path.
- **Zone reclassification is honored retroactively.** A Visit triggered
  directly inside a Privacy/Ignore Zone is already refused at candidate-
  creation time (unchanged). This milestone additionally re-checks the
  Visit's *current* Zone type at export time: if a Zone is later
  reclassified to privacy/ignore, every Visit under it becomes
  `privacy_restricted` and is withheld from export from that point on --
  never a pixel redaction (unchanged non-goal), only export withholding.
- **Coordinates are never fabricated or inferred.** `latitude`/
  `longitude` are `None` in every export unless a caller explicitly
  supplies them at export time (`CamtrapDpExportRequest.latitude`/
  `.longitude`/`.site_name`) -- never persisted here, never inferred,
  applied uniformly to the single-site product's one logical deployment.
  Environmental Context Foundation v1 (see
  [environmental-context-foundation-v1-contract.md](environmental-context-foundation-v1-contract.md))
  later added one narrow, opt-in, deliberately coarse (~11 km) Place
  coordinate setting for local sunrise/sunset computation only -- this
  export path does not read it, still requires its own explicit per-call
  value, and still never infers one. "No persisted site/coordinate model"
  is therefore no longer true of the codebase as a whole; it remains true
  of this export/BirdNET-narrowing surface specifically. Environmental
  Context v2 (see
  [environmental-context-v2-contract.md](environmental-context-v2-contract.md))
  later added an external weather provider (Open-Meteo) reusing that same
  coordinate setting under its own separate `weather_enabled` opt-in --
  this export path does not read that setting either, does not include
  weather records in any export, and this doc's own claims here remain
  accurate unchanged. Weather data carries CC BY 4.0 attribution
  requirements of its own (see the v2 contract's "Phase 3" and "Research/
  export considerations"); a future milestone that adds weather to an
  export must carry that attribution forward explicitly, not silently.
- **Metadata-only by default.** Media bytes are copied only when
  `include_media` is explicitly requested, and only for observations that
  already passed the eligibility gate; see the Milestone 4 contract above for
  path-safety, integrity, bounds, and missing-media behavior.

## Collection / contributor model

`ResearchCollectionModel` (schema v42, additive) is a named, bounded
collection: `name`, `description`, `curator_identity` (free text, mirrors
`ReviewLabelModel.reviewer_identity`'s established convention -- there is no
user/account system in this product), and a capped explicit `visit_ids`
list (mirrors `DatasetExportModel.selected_visit_ids_json`'s identical
shape). Membership is never cached truth: every export/read re-resolves
each member through the ordinary eligibility boundary
(`ProductRepository._research_collection_counts`), so a later correction or
Zone reclassification is reflected immediately, with no backfill.

`GET/POST /api/research/collections[/{id}]`, `repository.create_research_
collection`/`get_research_collection`/`list_research_collections`.
`ResearchExportFilters.collection_id` scopes any export (generic or Camtrap
DP) to one collection's membership.

### Contributor authority (unchanged)

Contributing a record to a collection, or curating one, never creates or
implies taxonomic/review authority -- `curator_identity` is a distinct
concept from `ReviewLabelModel.review_origin`/`reviewer_identity`, and
nothing in this milestone writes a `ReviewLabelModel` row. `ResearchObservation.
reviewed_by` surfaces the *existing* reviewer identity from the Visit's own
current authoritative `ReviewLabel` -- reused, never re-derived, and never
influenced by who created or curated a collection.

## Versioning / reproducibility

Every export carries its own schema version independent of `CURRENT_
DATABASE_SCHEMA_VERSION`: `RESEARCH_EXPORT_SCHEMA_VERSION =
"research-export-v1"`, Camtrap DP's `CAMTRAP_DP_PROFILE_VERSION = "1.0.2"`,
and `RESEARCH_ELIGIBILITY_POLICY_VERSION = "research-eligibility-v1"`
(recorded per collection at creation time, and on every export manifest).
Same retained truth + same filters → the same `content_fingerprint`, always
(deterministic ordering via `sorted_observations`, never raw DB scan order).

## Explicitly deferred / known limitations

- ~~Media-byte copying into an export bundle~~ -- closed by Research Export &
  Ecological Workflow Completion v1 (generic export and Camtrap DP; Darwin Core
  stays reference-only).
- `acquisition_type="unknown"` for Visits predating Observation Engine v2
  candidate authority, or created via the legacy still-image motion-evidence
  path (see "Acquisition type" above).
- No persisted per-Source/Stream coordinate model; every Camtrap DP export
  needs an explicit per-call override to include real coordinates.
- A full external Camtrap DP/Frictionless conformance validator was not
  integrated (none was available to run hermetically in this environment);
  only the bounded structural validator above ships.
- Bounded research collaboration remains strictly local-first: no cloud
  sync, no remote researcher accounts, no distributed dataset
  synchronization (unchanged non-goal).

## Examples

Generic export, filtered to one Stream and last 30 days, dry run:

```bash
python -m mockingbird export-research --stream-id stream-backyard-feeder \
    --start-at 2026-07-23T00:00:00Z --end-at 2026-08-22T00:00:00Z --dry-run
```

Camtrap DP export with an explicit site override:

```bash
python -m mockingbird export-camtrap-dp --site-name "Example Yard" \
    --latitude 12.0150 --longitude -45.2705
```

Conservation report for the last week:

```bash
python -m mockingbird conservation-report \
    --start-at 2026-08-15T00:00:00Z --end-at 2026-08-22T00:00:00Z
```
