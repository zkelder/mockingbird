# Ecological Interoperability & Submission Workflows v1

## Purpose

Research / Conservation / Export Interoperability v1 (see
[research-conservation-export-contract.md](research-conservation-export-contract.md))
gave MockingBird a research-safe eligibility policy, a provider-neutral
exported-Observation shape (`ResearchObservation`), and generic/Camtrap DP
export -- but explicitly deferred every *named external destination*
(eBird, iNaturalist, GBIF, Darwin Core). This milestone closes that gap for
the destinations where it is honestly appropriate to close it, and records
why it is not appropriate for the others.

**External sharing always consumes data already permitted by the existing
reviewed-truth/research-eligibility contract; this milestone never builds a
second "human verification" mechanism per destination.** A Reviewed
MockingBird Visit remains the local observatory's own truth regardless of
what a destination later does with a copy of it.

## Governing distinction: destination submission vs. research export

Two different concepts now share the `ResearchObservation` foundation but
remain architecturally separate, on purpose:

- **Generic research export** (`mockingbird.research`, `/api/research/*`):
  a dataset/standards-shaped export -- CSV/JSON, Camtrap DP, and now Darwin
  Core. No destination identity, no submission state, no per-destination
  consent. Stays exactly where it was; Darwin Core is simply a new sibling
  export format alongside Camtrap DP.
- **Ecological destination submission** (`mockingbird.ecological`,
  `/api/ecological/*`): preparing/tracking one Reviewed Visit's journey
  toward one *named* destination (iNaturalist) -- a destination identity,
  an extra per-destination eligibility layer, an explicit location/media
  consent, a durable submission record, and (for iNaturalist) a
  destination-shaped, ready-to-upload file.

Do not confuse the two: a generic CSV/Camtrap DP/Darwin Core export never
implies consent to submit anything to a named third party, and preparing an
ecological submission never silently becomes a generic dataset export.

## Destination decisions

| Destination | Decision | Why |
| --- | --- | --- |
| **eBird** | **D -- defer, not offered** | eBird's own "Rules and Best Practices" (support.ebird.org, checked 2026-08-25, page shows "Last Updated Tue, 17 Feb 2026") explicitly excludes this entire product category: *"Remote sensed images or video - do not enter any data from nest cameras, feeder cameras, trail cams..."* and *"eBird is designed to collect in-person observations of living wild birds."* No carve-out was found for a human reviewing camera footage before submission. This is a real, cited policy conflict -- not an unfinished feature, not a time constraint. |
| **iNaturalist** | **B/C hybrid, reported as C** ("adapter contract can be built but live submission requires external authorization") | A real, useful v1 workflow: full eligibility/taxonomy-mapping/consent/prepare pipeline plus a genuine submission-ready CSV in iNaturalist's own confirmed bulk-import format, needing zero credentials. Live OAuth direct-submit is the external-authorization boundary this milestone does not cross (Phase 26: no unsafe credential-storage workaround invented). |
| **Darwin Core** | **Build** | Confirmed additive, not redundant: Camtrap DP (already accepted) is a Frictionless Data Package, not a Darwin Core Archive. A small, deterministic Occurrence-core exporter serves any generic DwC-A consumer directly. |
| **GBIF** | **D -- defer, institutional** | Direct publication requires organizational Participant-Node endorsement; not a lightweight individual/backyard workflow. The Darwin Core export above *is* the "GBIF-ready through later institutional workflows" bounded outcome this lane's own roadmap language anticipates. |

See the durable report
([ecological-interoperability-submission-v1-report.md](ecological-interoperability-submission-v1-report.md))
for the full official-source research trail (URLs, quotes, access dates)
behind each decision.

## Canonical reviewed external observation

`mockingbird.ecological.adapters.EcologicalSubmissionCandidate` composes
`mockingbird.research.research_export.ResearchObservation` unmodified --
`ResearchObservation` already carries everything Phase 4 of the governing
milestone brief asked for (Visit/Event identity, reviewed taxon
label/scientific name/category, capture timestamp and its confidence,
reviewer provenance, acquisition provenance, evidence identity, and the
full research-eligibility verdict). This module adds only what a
destination workflow needs beyond a research export:

- `destination: "inaturalist" | "ebird"`
- `destination_eligibility` -- the extra per-destination layer (below)
- `taxonomy_mapping` -- a resolved (or honestly unresolved) destination taxon
- `location: LocationSelection` -- explicit, never defaulted
- `media: MediaSelection` -- explicit, never defaulted

`mockingbird.ecological.adapters.build_submission_candidate` is the one
place a `ResearchObservation` becomes a candidate for one destination.

## Reviewed-truth gate

`mockingbird.ecological.destination_eligibility.evaluate_destination_eligibility`
composes -- never re-derives or duplicates --
`mockingbird.research.eligibility.evaluate_research_export_eligibility`.
A record that fails the underlying research eligibility (not yet reviewed,
a provisional suggestion, rejected, non-wildlife, unresolved, structurally
superseded, or privacy-restricted) is always `"excluded"`, for exactly the
research-eligibility gate's own reason. This module only adds:

- `destination_not_offered` (eBird, always)
- `taxonomy_mapping_unresolved` / `taxonomy_mapping_ambiguous` (needs input)
- `species_level_taxon_required` (a destination requiring species-level
  identity a confirmed-unidentified-wildlife record cannot honestly provide
  -- no current destination sets this)
- `location_required` / `count_required` (no current destination sets
  either; the plumbing exists and is tested so a future destination that
  does can use it without a design change)

## Confirmed unidentified wildlife

A `confirmed_unidentified_wildlife` record (`unknown_bird`/`unknown_animal`)
never needs a taxonomy mapping at all -- it maps to iNaturalist's own
`species_guess=""` ("Unknown"), a first-class, community-resolvable state
on that platform, never a fabricated taxon.

## Taxonomy translation

Keyed by MockingBird's own stable taxon `label` (not scientific name --
`TaxonomyLabelModel.scientific_name` is `None` for essentially every seeded
taxon today, confirmed by direct grep of `api/demo_data.py`). Destination
taxonomy mapping is a pure translation layer: `EcologicalTaxonomyMappingModel`
(schema 57) never mutates `TaxonomyLabelModel`.

- **iNaturalist**: `GET /v1/taxa` is confirmed public/no-auth (no
  `security` requirement in the official swagger spec). Queried by
  scientific name when known, else the taxon's own display name.
  `mockingbird.ecological.inaturalist_taxonomy.parse_taxa_response`
  requires an **exact** case-insensitive name match among the returned
  candidates for `"matched"` -- not merely "exactly one result," since
  iNaturalist's own fuzzy search routinely returns several candidates even
  for an unambiguous name (confirmed live against the real API this
  milestone: a plain "Northern Cardinal" query returns 3+ rows). Zero exact
  matches, or more than one, is honestly `"ambiguous"`/`"not_found"` --
  never a guessed top pick. A resolution is cached in
  `EcologicalTaxonomyMappingModel` (one row per `(destination, label)`,
  resolved at most once per distinct label per call, reused thereafter) --
  never re-queried for the same stable fact. A transient lookup failure is
  never cached as a false `"not_found"`.
- **eBird**: no mapping is ever attempted -- moot, since eBird is never
  offered.

## Time semantics

`observed_on_string` is built from the Visit's own `captured_at`, converted
via `mockingbird.time_utils.resolve_host_local_timezone` (never a
longitude-derived guess -- that specific mistake is already documented,
found, and fixed elsewhere in this codebase) to full ISO 8601 with an
explicit UTC offset, hitting iNaturalist's confirmed unambiguous fast-parse
path.

## Location is a separate consent boundary

`EcologicalLocationInput`/`LocationSelection` is explicit and per-call,
every time -- never read from `EnvironmentalContextSettingsModel`'s coarse
(~11km) weather coordinate, which is itself already documented as "a
deliberate, narrow exception" not to be reused elsewhere. Directly tested:
`test_prepare_never_silently_uses_the_configured_weather_coordinate`.

**Critical, directly-confirmed fact**: iNaturalist's "obscured" geoprivacy
is a *display* setting, not a *transmission* setting -- confirmed against
iNaturalist's own open-source `observation.rb` (`obscure_coordinates`): the
client's submitted coordinate is copied verbatim into
`private_latitude`/`private_longitude` (permanently retained,
owner/trusted-user-visible) *before* the public-facing coordinate is
randomized. MockingBird's own UI states this explicitly rather than
implying "obscured" hides a coordinate from the destination itself.

## Media behavior

Deferred, and said so: iNaturalist's confirmed bulk-import CSV format has
**no photo column at all** -- media bytes are not part of this milestone's
real deliverable regardless of ambition, so building byte-copying now would
serve no actual destination path. `EcologicalMediaInput`/`MediaSelection`
keeps only an explicit, optional `media_asset_id` *reference* (never bytes)
so a user can find and attach the right photo themselves, after import, on
iNaturalist's own site. A UI warning cites the exact, already-authoritative
Privacy Zone doctrine (`docs/privacy-ignore-zone-contract.md`): a Zone
prevents activity there from *triggering* a Visit, it does not redact
pixels elsewhere in a saved frame.

## eBird workflow

Not built. `mockingbird.ecological.adapters.EBirdAdapter.requirements()`
always returns `offered=False` with the cited reason above, so:

- the destination picker always shows eBird, disabled, with its reason
  **persistently visible** -- not hidden behind a hover-only tooltip on a
  button that can never be clicked (a real UX gap found and fixed by this
  milestone's own e2e test);
- eligibility preview/prepare always classifies every record `excluded`,
  reason `destination_not_offered`, regardless of review quality;
- no eBird species-code mapping table, CSV format, or CLI command exists --
  building one would serve no real destination path and risk implying a
  workflow MockingBird deliberately does not offer.

## iNaturalist workflow

`mockingbird.ecological.inaturalist_csv.build_inaturalist_csv` produces the
**exact** positional 8-column format confirmed directly against
iNaturalist's own open-source Rails application
(`lib/bulk_observation_file.rb`, checked 2026-08-25):

```
species_guess, observed_on_string, description, place_guess,
latitude, longitude, tags, geoprivacy
```

- `species_guess`: the resolved destination scientific name when matched;
  MockingBird's own reviewed display name/label as an honest free-text
  guess when unresolved (the record itself is already flagged
  `needs_input` upstream -- this is what a caller sees if they export
  anyway); blank for confirmed-unidentified-wildlife.
- `geoprivacy`: `"open"` for an exact location choice, `"obscured"` for a
  coarse one -- always carrying the real coordinate either way, per the
  server-side-obscuring fact above.
- `captive_flag`: not applicable -- the confirmed CSV import format has no
  such column; imported observations default to non-captive, which matches
  MockingBird's wild backyard subjects with no extra code needed.
- **"Research Grade"**: never claimed, anywhere. Confirmed via iNaturalist's
  own source (`set_quality_grade`) that this status is mechanically
  recomputed server-side from community identification consensus and
  cannot be durably set by any client, even though `quality_grade` is
  technically a permitted request parameter.
- No live OAuth submit exists. A user uploads the generated CSV themselves
  at `inaturalist.org/observations/import`, then optionally pastes the
  resulting observation id/link back into MockingBird
  (`record_ecological_submission_result`) -- an honest, explicit
  self-report, never an automated round-trip.

## Darwin Core export

`mockingbird.research.darwin_core` (lives with the research-export family,
not `mockingbird.ecological` -- it is a bounded standards export, not a
destination-submission workflow). One flat Occurrence-core table, no
Event-core linkage (mirrors Camtrap DP's own "no deployment lifecycle"
disclosure). `basisOfRecord` is unconditionally `"MachineObservation"` for
every row -- GBIF's own official camera-trap guide
(docs.gbif.org/camera-trap-guide, checked 2026-08-25) recommends exactly
this value for every camera-trap record. `individualCount` is never
populated (mirrors Camtrap DP's identical, already-accepted decision).
`occurrenceStatus` is unconditionally `"detected"`. `identifiedBy` carries
the human reviewer; `associatedMedia` references evidence by manifest-
relative id, never a local path. A minimal, structurally-valid `meta.xml`
(Darwin Core Archive descriptor) and `eml.xml` (dataset metadata, no
license asserted) accompany `occurrence.csv` -- the same "smallest
structural completeness, not full external conformance" precedent Camtrap
DP's own validator already established.

## GBIF boundary

No direct publication path exists or is planned. `docs.gbif.org`/
`ipt.gbif.org`/`techdocs.gbif.org` confirm a hosted IPT account removes the
self-hosting barrier, but the organizational Participant-Node endorsement
gate remains real and institutional. The unauthenticated
`api.gbif.org/v1/species/match` backbone-taxonomy lookup was directly
verified working but is not integrated here -- iNaturalist's own taxa
search already serves this milestone's real mapping need; adding a second
live taxonomy dependency for no exercised path would be scope creep.

## Submission workflow state

`EcologicalSubmissionRecordModel` (schema 57): one durable row per
`(visit_id, destination)` while unsubmitted; a submitted record (one with a
self-reported `external_id`/`external_url`) is **never overwritten** by a
later prepare call for the same Visit/destination -- a fresh, separate
record is created instead, so the submitted record's own link/history is
preserved (Phase 19/32). Statuses: `prepared`, `needs_input`, `excluded`,
`exported`, `submitted`. No destination credential/token field exists on
this model at all -- there is nothing to accidentally log or leak.

`is_stale` is never a stored column -- it is computed fresh at every read
(list/get) by rebuilding a candidate from *current* truth (Visit, review,
taxonomy-mapping cache) and comparing its fingerprint against the record's
stored one. This mirrors the established `conditional_association`/Place
Feature convention in this codebase of never caching a derived comparison.

## Idempotency / correction

`mockingbird.ecological.fingerprint.submission_candidate_fingerprint` is a
deterministic sha256 over exactly the facts that make one submission
package identical to, or different from, another (observation identity/
classification/taxon/review timestamp, taxonomy mapping, location choice,
media choice). Preparing the same Visit/destination/location/media twice
updates the same record in place, never duplicates it
(`test_prepare_is_idempotent...`). A correction after preparation changes
the fingerprint, which `export_ecological_submissions` re-verifies
**immediately before writing anything** -- a stale record is excluded with
reason `stale_since_prepared`, even when the corrected truth also happens
to be currently ineligible for an unrelated reason (staleness is checked
first: the more actionable signal, a real precedence bug found and fixed
during this milestone's own test-writing). Re-exporting the same
up-to-date, already-exported records again is safe and reproduces an
identical file -- there is no live destination side effect to duplicate.

## Destination adapter boundary

`mockingbird.ecological.adapters.DESTINATION_ADAPTERS` is a static,
built-in dict -- `INaturalistAdapter`/`EBirdAdapter`, each a frozen
dataclass exposing `requirements() -> DestinationRequirements`. No dynamic
third-party loading, no plugin marketplace (Phase 28). Adding a third
destination means adding one adapter and one line in the registry.

## Security / privacy review

- **Location exfiltration**: never silent (above). UI honestly discloses
  iNaturalist's server-side-obscuring behavior rather than overclaiming
  privacy.
- **CSV injection**: `ProductRepository._write_csv` (the one shared CSV
  writer behind *every* export in this codebase -- generic research
  export, Camtrap DP, Darwin Core, and the new ecological-submission CSV)
  now runs every cell through `_csv_injection_safe_value`, prefixing a
  string cell that would otherwise be interpreted as a spreadsheet formula
  (leading `=`, `+`, `-`, `@`, tab, or CR) with a single quote -- the
  standard OWASP mitigation. A user-supplied `place_name`/`site_name`/
  `locality` is exactly the kind of free-text field this protects.
  **Directly caught by this milestone's own testing**: a naive first version
  of this fix also mangled a plain negative coordinate ("-105.000000",
  formatted for CSV, legitimately starts with `-`) into an invalid,
  unparseable string -- fixed by only sanitizing a leading-trigger-character
  string that does **not** parse as a plain number. This fix applies
  retroactively to the pre-existing generic/Camtrap DP export paths too,
  not only the new ecological one.
- **External URL scheme**: `RecordEcologicalSubmissionResultRequest.
  external_url` rejects any scheme other than `http`/`https` -- the
  frontend renders this value back as a clickable `<a href>`, and without
  this check a `javascript:`-scheme value typed into the field would
  execute in the viewer's own session when clicked.
- **No credential storage**: no destination token/credential field exists
  anywhere in this milestone's schema or code.
- **HTML/URL escaping**: the frontend is plain React JSX throughout (no
  `dangerouslySetInnerHTML`) -- auto-escaped by construction.
- **Support-bundle/destination-error-body leakage**: not applicable -- no
  live authenticated destination call exists to leak an error body from,
  and the two new tables contain no credential/settings data a support
  bundle exclusion list would need to cover.

## Versioning / reproducibility

`INATURALIST_TAXONOMY_SOURCE_VERSION = "inaturalist-v1-taxa-api"` and
`DARWIN_CORE_ARCHIVE_SCHEMA_VERSION = "darwin-core-archive-v1"` are
recorded independently of `CURRENT_DATABASE_SCHEMA_VERSION`, mirroring
`RESEARCH_EXPORT_SCHEMA_VERSION`/`CAMTRAP_DP_PROFILE_VERSION`'s established
convention. The same retained Reviewed truth + the same destination +
the same taxonomy mapping + the same location/media choice always produces
the same `content_fingerprint` (directly tested); any of those changing
always changes it.

## Explicitly deferred / known limitations

- Live, authenticated, automated iNaturalist submission (the OAuth
  boundary) -- Phase 26 of the governing brief: no unsafe credential-
  storage workaround was invented for a capability that does not yet
  exist. Preparing a submission-ready CSV is this milestone's real v1
  capability instead.
- Media-byte inclusion in any ecological submission package -- iNaturalist's
  own confirmed CSV import format has no photo column at all, so there is
  no real destination path to serve yet.
- A single-Visit deep-link that pre-selects that exact Visit on the batch
  Ecological Destinations page -- the "Prepare for an external destination"
  action on Visit detail navigates there for discoverability (Phase 22),
  but does not yet pre-filter/pre-select that one Visit; the date-range
  preview naturally includes it.
- Direct GBIF publication, and any eBird workflow of any kind (see
  "Destination decisions").
- A user-facing count/individual-animal field -- deliberately never built;
  neither offered destination has one, and MockingBird has no defensible
  population-count model regardless (Phase 14).

## Examples

```bash
python -m mockingbird export-darwin-core --site-name "Example Yard" \
    --latitude 40.0150 --longitude -105.2705 --dry-run
```
