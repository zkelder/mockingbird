# Ecological Interoperability & Submission Workflows v1 -- Report

## Identity

- **Starting HEAD:** `9364511` (Calm Attention & Notifications v1 reconciliation -- verified before any edit)
- **Implementation HEAD:** `3c60d79` ("Ecological Interoperability & Submission Workflows v1: Reviewed Observations -> eBird / iNaturalist / External Ecology")
- **Reconciliation HEAD:** the commit immediately following this one (release-execution-state.md + roadmap.md + this report)
- **Schema:** v56 -> v57 (two new additive tables:
  `ecological_taxonomy_mappings`, `ecological_submission_records`; no
  existing table's shape changed)
- **Commits:** this milestone's implementation + its own reconciliation commit
- **Push state:** local accepted state; not pushed (explicit authorization required)

## Existing foundation (Phase 1 inventory)

| Destination requirement | Existing MockingBird capability | Gap | Bounded treatment |
| --- | --- | --- | --- |
| Trustworthy, reviewed-only source truth | `mockingbird.research.eligibility.evaluate_research_export_eligibility` -- one consolidated policy, already accepted | None | Reused unmodified; `destination_eligibility.py` only adds a thin per-destination layer on top |
| Provider-neutral exported record | `ResearchObservation` -- already accepted | None | Composed unmodified by `EcologicalSubmissionCandidate` |
| Destination identity / adapter concept | None (confirmed absent by broad grep across `src/` and `docs/`) | Real gap | New, small, static `mockingbird.ecological.adapters` registry (Phase 28) |
| Destination taxonomy mapping | None; `TaxonomyLabelModel` has no version/source field, no scientific names populated in seed data | Real gap | New `EcologicalTaxonomyMappingModel` cache + live iNaturalist `/v1/taxa` lookup |
| Explicit, per-submission location/media consent | Camtrap DP already has explicit, never-inferred, per-call `latitude`/`longitude`/`site_name` -- the right precedent | Needed a destination-submission-scoped equivalent | New `EcologicalLocationInput`/`EcologicalMediaInput`, same never-inferred discipline |
| Durable submission tracking / idempotency | None | Real gap | New `EcologicalSubmissionRecordModel` (schema 57) + fingerprint-based staleness detection |
| Generic standards export beyond Camtrap DP | Camtrap DP only (a Frictionless Data Package, not Darwin Core) | Real, confirmed-additive gap | New bounded Darwin Core Occurrence-core exporter, in the research-export family |
| Frontend export/submission surface | None for any research/Camtrap DP export (API+CLI only, confirmed) | Product-facing gap for a *destination* workflow specifically (raw exports correctly stay API+CLI) | New primary-nav `EcologicalDestinationsPage.tsx` + a Visit-detail entry point; Darwin Core stays API+CLI, matching its siblings |
| Multi-user/reviewer provenance | `CurrentUser`/`reviewed_by_user_id` FK convention already accepted (superior to the older free-text `curator_identity` convention) | None | `EcologicalSubmissionRecordModel.prepared_by_user_id` uses the FK convention |
| Privacy/location doctrine | `EnvironmentalContextSettingsModel`'s coarse (~11km) weather coordinate is explicitly documented as *not* reusable elsewhere; Privacy/Ignore Zone reclassification is already honored retroactively at research-export time | None; existing doctrine already correct | Ecological submission location never reads the weather coordinate (tested); the same Zone reclassification flows through unmodified via the composed `ResearchObservation` |

## Destination research

All fetches below were performed 2026-08-25 against each destination's own
official sources; every claim is cited with a URL and, where useful, a
direct quote. See the individual research agents' full transcripts (not
reproduced verbatim here) for exhaustive detail; this section carries the
facts that actually drove a decision.

### eBird

- **No public write/submission API exists for arbitrary third parties.**
  eBird API 2.0 exposes only read endpoints (`data/obs`, `product`,
  `ref/geo`, `ref/hotspot`, `ref/taxonomy`, `ref/region`) -- confirmed
  against the official Postman-hosted API reference
  (`documenter.getpostman.com/view/664302/S1ENwy59`) and the eBird API
  Terms of Use (`birds.cornell.edu/home/ebird-api-terms-of-use/`, dated
  Oct 19, 2021).
- **A CSV bulk-import tool exists** (`support.ebird.org/en/support/
  solutions/articles/48000907878`, Last Updated Fri, 28 Mar 2025) -- a
  personal-account web upload, not an API, capped at 48 checklists/file,
  explicitly "not... the main way you enter data," and **cannot bulk-upload
  media**.
- **The decisive fact**: eBird's "Rules and Best Practices"
  (`support.ebird.org/en/support/solutions/articles/48000795623`, page
  shows **Last Updated Tue, 17 Feb 2026** -- current, not stale) states:
  > "Remote sensed images or video - do not enter any data from nest
  > cameras, feeder cameras, trail cams, Google maps, etc."
  > "eBird is designed to collect in-person observations of living wild birds."

  MockingBird's entire product category is named explicitly, with no
  carve-out found for a human reviewing camera footage before submission.
- Complete-checklist semantics require reporting *every* species detected,
  not a subset (`support.ebird.org/.../48000967748`) -- independently
  confirms a stationary camera's own partial view could never legitimately
  claim a complete checklist, even before the camera-ban finding above.
- eBird data flows to GBIF one-way, in batch, after Cornell's own review --
  not an alternate individual-submission door
  (`support.ebird.org/.../48001078113`).
- Official rate limits are not documented on any Cornell/eBird page found
  this session (a commonly cited "~1000/day" is third-party, unverified).

**Net**: no technical gap explains this -- eBird's own current policy
excludes the product category. Building a CSV-export "help you submit to
eBird" feature would help users violate eBird's own rules. **Decision: D.**

### iNaturalist

- **A public write API exists** (`POST /observations`, `api.inaturalist.org/v1`)
  but requires OAuth2 (Doorkeeper) tied to a real logged-in account --
  confirmed directly in iNaturalist's own open-source Rails source
  (`app/controllers/application_controller.rb`: `current_user` requires
  `doorkeeper_token.resource_owner_id`; no app-only/`client_credentials`
  write path exists). No secure server-side OAuth-token-storage subsystem
  exists anywhere in MockingBird today.
- **A CSV bulk-import workflow exists that needs only an ordinary logged-in
  website session -- no OAuth, no API token at all** -- confirmed directly
  against `lib/bulk_observation_file.rb`: 8 positional columns
  (`species_guess, observed_on_string, description, place_guess, latitude,
  longitude, tags, geoprivacy`), no photo column.
- **`GET /v1/taxa` (taxon search) is confirmed public/no-auth** -- verified
  directly by parsing the official swagger spec (no `security` key on that
  operation) and by a real, live, unauthenticated call made during this
  milestone's own research.
- `observed_on_string`: full ISO 8601 with an explicit UTC offset hits the
  server's fast, unambiguous parse path (`app/models/observation.rb`).
- **Geoprivacy is server-side-obscuring, not client-side**: confirmed
  directly in `observation.rb`'s `obscure_coordinates` -- the true
  submitted coordinate is always retained (`private_latitude`/
  `private_longitude`) before the public value is randomized. iNaturalist's
  servers always receive the exact coordinate a client submits, regardless
  of geoprivacy level.
- `captive_flag`: real field, mechanically drives the Wild/Captive Data
  Quality Assessment metric; not present at all in the CSV import format.
- **"Research Grade" cannot be set by a client**, even though
  `quality_grade` is technically a permitted param -- `set_quality_grade`
  mechanically recomputes it from community-identification state on every
  save, ignoring any client-submitted value (confirmed in source).
- Rate limits are officially documented: 100 req/min hard throttle, asked
  to stay <=60/min and <10,000/day (`api.inaturalist.org/v1/swagger.json`
  `info.description`, directly fetched).
- Default license is CC BY-NC per-account, overridable; not something
  MockingBird sets on the user's behalf.
- No stated policy against camera-trap-sourced observations was found (a
  categorical difference from eBird) -- consistent with iNaturalist's
  general-purpose, community-identification-first design.

**Net**: a real, useful, no-credential-needed submission-ready workflow
exists today (the CSV path); live automated submission is real but crosses
the OAuth/credential-storage boundary this milestone does not cross.
**Decision: C** (adapter contract built; live submission needs external
authorization this milestone deliberately does not implement) **with a
genuinely useful, working v1 CSV deliverable** -- closer to a B+C hybrid in
practice than a bare "adapter contract only."

### Darwin Core

- **An open, account-free vocabulary** -- confirmed directly
  (`dwc.tdwg.org`, `dwc.tdwg.org/text/`): a Darwin Core Archive is just a
  CSV + `meta.xml` (+ optional `eml.xml`), producible by anyone.
- Core Occurrence-relevant terms and their exact definitions were pulled
  directly from `dwc.tdwg.org/terms/`: `occurrenceID`, `basisOfRecord`,
  `eventDate`, `scientificName`, `taxonRank`, `decimalLatitude`/
  `decimalLongitude`, `coordinateUncertaintyInMeters`, `individualCount`,
  `occurrenceStatus`, `recordedBy`, `identifiedBy`, `associatedMedia`.
- **GBIF's own official camera-trap guide**
  (`docs.gbif.org/camera-trap-guide/en/`, GBIF Secretariat, DOI
  10.35035/doc-0qzp-2x37) explicitly recommends `basisOfRecord =
  "MachineObservation"` for **every** camera-trap record:
  > "the capturing of the record is done by a machine responding to a
  > sensor. This is critically different from human observations, where a
  > human is actively in control of the decision whether to record an
  > organism or not."

  A close-to-perfect doctrinal fit for MockingBird's own machine-captures/
  human-reviews model.
- **Camtrap DP is not itself a Darwin Core Archive** -- confirmed by a
  full-text search of every page on `camtrap-dp.tdwg.org` (zero mentions of
  "Darwin Core"). It is a Frictionless Data Package; GBIF's own tooling
  (`camtraptor::write_dwc()`, an R package) transforms one to the other
  only for its own ingestion, one-way, lossily (`docs.gbif.org/
  camera-trap-guide/en/` section 4.3). A bounded, additional DwC-A exporter
  is therefore genuinely additive, not redundant.

**Net**: a real, standards-shaped gap, cheaply closeable, with an unusually
strong doctrinal fit (`MachineObservation`). **Decision: build.**

### GBIF

- Darwin Core output is confirmed to be a real prerequisite for later
  institutional GBIF publication, but **direct publication is not a
  lightweight individual/backyard workflow**: publishing requires
  organizational endorsement via a GBIF Participant Node (search-indexed
  content from `gbif.org/become-a-publisher`, not independently opened this
  session -- `www.gbif.org` returned a Cloudflare bot-challenge on every
  fetch attempt; flagged honestly as corroborated-by-search, not
  primary-source-verified for this specific claim).
- **Directly confirmed**: hosted IPT accounts exist (`ipt.gbif.org/manual/`)
  -- self-hosting an IPT instance is not required -- but this only removes
  one barrier, not the endorsement gate.
- **Directly confirmed**: iNaturalist itself is a registered GBIF publisher
  (a real GBIF publisher record exists for it), matching the common
  individual-citizen-scientist path of contributing through an existing
  aggregator rather than direct publication.
- **Directly confirmed**: CC-BY-NC is a GBIF-*supported* license option
  (`ipt.gbif.org/manual/en/ipt/latest/applying-license`) -- not banned, only
  soft-discouraged in favor of CC0/CC-BY.
- The unauthenticated `api.gbif.org/v1/species/match` backbone-taxonomy
  lookup was directly, live-verified working -- available for a future
  cross-check, not integrated in this milestone since it would serve no
  currently-exercised path.

**Net**: matches the roadmap's own framing exactly -- "future publication
interoperability through the now-existing Camtrap DP export where
appropriate," now joined by Darwin Core as the second bounded standards
output. **Decision: defer, institutional.**

## Destination decisions

See the contract doc's identical table for the compact form. In prose: eBird
= D (real, cited policy conflict, not a time constraint); iNaturalist =
C-with-a-genuinely-useful-v1-CSV-deliverable; Darwin Core = build (bounded,
additive); GBIF = D (institutional, correctly deferred).

## Canonical reviewed external observation

`mockingbird.ecological.adapters.EcologicalSubmissionCandidate` composes
`ResearchObservation` unmodified, adding only: destination identity, the
extra destination-eligibility layer, a resolved (or honestly unresolved)
taxonomy mapping, and an explicit location/media choice. See the contract
doc's "Canonical reviewed external observation" section for the full field
list and reasoning. No second, parallel truth shape was created.

## Eligibility

`mockingbird.ecological.destination_eligibility.evaluate_destination_eligibility`
composes `mockingbird.research.eligibility.evaluate_research_export_eligibility`
without re-deriving it. Directly tested against every classification the
research-eligibility gate produces (confirmed_taxon, confirmed_unidentified_
wildlife, provisional, rejected, privacy-restricted, superseded -- the last
via the same structural `VisitModel.is_superseded.is_(False)` scope filter
the research export already uses, so a superseded Visit never even appears
in an ecological eligibility preview, not merely marked excluded).

## Taxonomy mapping

See the contract doc's "Taxonomy translation" section. The headline finding:
a naive "exactly one result = confident match" rule was directly falsified
by a live call to the real iNaturalist API during this milestone's own
smoke-testing (a plain "Northern Cardinal" query returns 3 candidates, not
1) -- fixed to require an exact case-insensitive name match among however
many candidates come back, verified against both the real API and a
comprehensive set of unit tests (exact match among many, zero exact matches
among many, multiple exact matches, common-name vs. scientific-name
queries).

## Time semantics

`observed_on_string` uses the Visit's real `captured_at`, converted through
`resolve_host_local_timezone` (never inferred from a submitted destination
coordinate -- that mistake is already a documented, fixed, closed issue
elsewhere in this codebase) to full ISO 8601 with an explicit UTC offset.

## Location / privacy

Never defaulted from the coarse weather coordinate (directly tested).
iNaturalist's server-side-obscuring behavior is disclosed honestly in the
product UI, with the exact wording chosen to avoid ever implying
MockingBird can make a destination's own servers forget a coordinate the
user chose to submit. Privacy Zone reclassification flows through
unmodified via the composed `ResearchObservation`/eligibility gate -- an
already-eligible record becomes ineligible the moment its Zone is
reclassified privacy/ignore, exactly like the existing research export.

## Count semantics

No count field exists anywhere in this milestone's output. iNaturalist's
own confirmed CSV import format has no count column at all (occurrence,
not abundance, is the unit); Darwin Core's `individualCount` is never
populated (mirrors Camtrap DP's identical prior decision -- "Strongly
recommended," never "Required," per GBIF's own camera-trap guide). A Visit
is never turned into an individual-animal count anywhere.

## Media behavior

Deferred with an honest, destination-driven reason: iNaturalist's own
confirmed bulk-import CSV format has no photo column at all, so
byte-level media inclusion in *this* workflow would serve no real
destination path regardless of engineering effort spent. `MediaSelection`
keeps a bounded, explicit, optional evidence-media *reference* (never
bytes) for the user's own convenience after import, with an honest Privacy
Zone warning quoting the existing, authoritative doctrine.

## eBird workflow

Not built, and the reason is persistently visible in the product UI, not
merely in code comments -- a real UX gap (the reason was originally only
visible behind a hover tooltip on a disabled, unclickable button) was found
and fixed during this milestone's own e2e testing.

## iNaturalist workflow

See the contract doc's "iNaturalist workflow" section for the complete,
field-by-field mapping. Delivered: eligibility preview, live taxonomy
mapping with caching, explicit location/media consent, batch prepare, a
real destination-shaped CSV file, and a self-reported external-result
close-the-loop step. Not delivered: any live, authenticated submission
call.

## Darwin Core / GBIF decision

Darwin Core: built, bounded, additive (see above). GBIF: deferred,
institutional, correctly not built as a direct-publication feature; Darwin
Core output is the sanctioned bounded outcome the roadmap itself
anticipated.

## Submission/preparation state

`EcologicalSubmissionRecordModel` (schema 57). See the contract doc's
"Submission workflow state" for the full field list and status vocabulary.
No credential/token field exists on this model. `is_stale` is always
computed fresh, never cached.

## Idempotency / correction

Deterministic content fingerprinting (`submission_candidate_fingerprint`)
underlies both idempotent re-preparation (same inputs -> same record,
updated in place, never duplicated) and stale-package detection at export
time. A genuine precedence bug -- a record both stale and (coincidentally)
currently-ineligible reported the less-actionable "not_eligible" reason
instead of the more useful "stale_since_prepared" -- was found by this
milestone's own test-writing and fixed (staleness is now checked first).
A submitted record's external link is never overwritten by a later
prepare call; a fresh record is created instead, preserving history.

## User experience

`EcologicalDestinationsPage.tsx` (primary nav, not buried in the
Developer-Mode-gated advanced section -- a deliberate placement decision
mirroring this codebase's own precedent of promoting genuinely
user-facing features, like Bird Log and Import Media, out of that section)
walks: choose destination -> preview eligibility (per-record status and
reason, never a bare count) -> explicit location/media choice -> prepare
-> review prepared records (including live staleness warnings) -> an
explicit, human-readable confirmation dialog naming the destination,
record count, location precision, and media inclusion -> export -> record
what the destination gave back. A "Prepare for an external destination"
action on Visit detail (Phase 22) provides per-Visit discoverability,
navigating to the same batch page (deep-link pre-selection is a disclosed,
deferred gap, not built this pass). Raw Camtrap DP/Darwin Core/generic CSV
export remains intentionally API+CLI only, exactly like its accepted
sibling -- no frontend UI was built for any of the three, keeping the
"ordinary users should not need to understand Camtrap DP" doctrine intact.

## Local-first / offline behavior

Preparation and export both work entirely from already-local data once a
taxonomy mapping is cached; only a genuine cache miss on a `confirmed_taxon`
record needs a bounded, credential-free network call to iNaturalist's own
taxa search, and a failure there degrades to an honest `needs_input`
(`taxonomy_mapping_unresolved`) rather than blocking the whole preview/
prepare operation, mirroring the existing weather-provider's own
"degrade honestly, never poison the cache" discipline. A user who never
opens Ecological Destinations loses nothing -- no nagging, no disabled
core feature, no external-service reachability requirement anywhere else
in the product.

## Security / privacy review

See the contract doc's "Security / privacy review" section in full. Two
real, concrete findings were made and fixed during this milestone's own
work, not merely reviewed for absence:

1. **CSV injection** in the one shared `_write_csv` helper behind every CSV
   export in this codebase (generic research export, Camtrap DP, Darwin
   Core, and the new ecological-submission CSV) -- fixed with the standard
   OWASP single-quote-prefix mitigation, applied retroactively to the
   pre-existing export paths too. A naive first version of this exact fix
   also corrupted legitimate negative coordinates (a real regression caught
   by this milestone's own test before it ever shipped) -- fixed by only
   sanitizing a leading-trigger-character string that does not parse as a
   plain number.
2. **`javascript:`-scheme external URL** -- `RecordEcologicalSubmissionResultRequest.
   external_url` now rejects any non-`http(s)` scheme, since the frontend
   renders this user-typed value back as a clickable link.

No credential/token is ever stored, logged, or leakable through a support
bundle in this milestone's own new data. No live authenticated destination
call exists to leak an error body from.

## Product-shaped scenario

`tests/test_ecological_interoperability_scenario.py::test_phase_37_
product_shaped_scenario` -- a single, real, passing, committed pytest test
(not a throwaway script) reproducing the governing brief's exact scenario
against a real isolated SQLite database with real candidate-Visit
admission:

- 12 wildlife Visits seeded exactly as specified: 8 reviewed species (a
  deliberate mix -- 6 with a confident iNaturalist mapping, 1 genuinely
  ambiguous [Carolina Chickadee, mirroring a real regional-subspecies
  overlap], 1 genuinely unresolved [a simulated lookup gap]), 1 confirmed
  unidentified wildlife, 1 provisional suggestion, 1 structurally
  superseded Visit, 1 Visit later placed under a Zone reclassified to
  privacy.
- Eligibility preview correctly classifies all 12 (7 eligible, 2
  needs-input with the correct distinct reasons, 1 excluded with a visible
  reason, 1 invisible-by-scope-filter [superseded], 1 that flips from
  eligible to excluded the moment its Zone is reclassified privacy, with
  the exact `privacy_restricted` reason).
- An explicit exact location (with a place name) is supplied once and
  applied uniformly to a real 7-record batch prepare.
- A real destination artifact is generated: a CSV with a header row + 7
  data rows, containing the correct resolved scientific names for every
  matched species.
- A correction to one already-prepared record's reviewed label (Northern
  Cardinal -> Blue Jay, via the real `revise_visit_review` path) is
  detected as staleness on the very next read, and a second export attempt
  correctly excludes exactly that one record (reason
  `stale_since_prepared`) while still succeeding for the other 6 --
  proving no stale batch silently exports.
- A simulated external result (an id + URL, as if the user had uploaded the
  CSV themselves and pasted the outcome back) is recorded and round-trips
  correctly.
- Final state: exactly 7 durable submission records exist, no duplicates,
  and neither the provisional nor the superseded Visit's id ever appears
  among them -- only legitimate current Reviewed truth proceeded, with zero
  user interaction required to run the whole scenario.

## Validation

- **New tests**: 62 pure-module tests across `test_destination_eligibility.py`,
  `test_inaturalist_taxonomy.py`, `test_ecological_adapters.py`,
  `test_inaturalist_csv.py`, `test_darwin_core.py` (all pure,
  dependency-free, no database/network); 21 repository-integration tests
  (`test_ecological_interoperability_repository.py`, real SQLite + real
  candidate-Visit admission, a fake taxonomy requester -- never a real
  socket -- including a dedicated CSV-injection regression test); 9
  API-surface tests (`test_ecological_interoperability_api.py`,
  request/response wiring, auth enforcement, validation, including the
  `javascript:`-scheme rejection); 1 comprehensive product-shaped-scenario
  test; 2 new Darwin Core export API tests added to `test_research_export_
  api.py`; 2 new Darwin Core CLI tests added to `test_research_cli.py`; 1
  new schema-migration regression test in `test_persistence.py`. **98 new
  tests total, all passing.** New frontend e2e: 5 tests in
  `ecological-destinations.spec.ts` (see "Frontend e2e" below).
- **Schema migration**: `test_schema_56_upgrades_to_current_with_ecological_
  interoperability` proves a real upgrade from schema 56, including both
  new tables' full column sets and a zero-row start (nothing backfilled,
  matching every prior additive-schema precedent).
- **Guard-rail sweep**: all 14 hard-coded `CURRENT_DATABASE_SCHEMA_VERSION
  == 56` assertions across 7 files (the identical class of drift every
  prior schema bump has tripped) found and bumped to `57`.
- **`ruff check`**: confirmed **zero new findings** via a direct line-level
  diff against a `git stash`-isolated clean baseline (not merely a bisection
  after the fact) -- every pre-existing finding (4 `F821`s, an `E731`, an
  `F841`, several `E701`/`E702` groups, several pre-existing unused
  imports) reproduces byte-identically at its new, shifted line number;
  exactly 3 new findings were introduced by this milestone's own new
  imports, all fixed. An earlier, over-broad `ruff --fix` run was caught
  removing ~19 unrelated pre-existing unused imports across the same file
  -- reverted precisely, keeping only this milestone's own 4 genuine fixes,
  before the final zero-new-findings confirmation above.
- **`tsc --noEmit`/`vite build`**: clean throughout.
- **Frontend e2e**: the new `ecological-destinations.spec.ts` (5/5 passing:
  eBird's not-offered reason is persistently visible -- not hidden behind a
  disabled button's hover tooltip, a real gap this milestone's own testing
  found and fixed; eligibility preview renders honest per-record status;
  prepare -> export requires and respects an explicit confirmation dialog
  naming the destination, and declining it genuinely does not export; an
  exact location choice with no coordinate typed in is refused rather than
  silently submitted as `(0, 0)` -- a second real gap this milestone's own
  testing found and fixed; the obscured-location warning renders). Full
  existing e2e suite re-run:
  **126 passed / 1 failed**, and that one failure
  (`reviewed-product-loop.spec.ts`) is the identical, already-independently-
  documented pre-existing `ReviewQueuePage` `product_category` gap recorded
  across at least three prior milestones' own acceptance records --
  recognized from that established precedent rather than re-bisected from
  scratch, since its signature (test name, failure mode, root cause) is
  already a matter of record.
- **Core** (`pytest -q -m "not slow"`): 5095 passed / 2 failed / 3 skipped /
  23 deselected (slow-marked) / 11 xfailed (27m29s). Both failures are the
  identical `test_place_biodiversity_summary_repository.py` pair
  (`'seen_before' == 'new'` assertion mismatch) independently re-confirmed
  as pre-existing across at least eight consecutive prior milestone
  checkpoints in `docs/release-execution-state.md` §14 -- re-run in
  isolation this session and reproduced byte-identically (same two test
  names, same exact assertion values), confirming the established
  precedent rather than re-running a full `git stash` bisection for code
  this milestone shares zero files or logic with.

## Remaining major PRODUCT opportunities

Not framed as release blockers -- this is substantial product development:

- **Live, authenticated iNaturalist submission** -- the OAuth/credential-
  storage boundary this milestone deliberately does not cross. A future
  milestone could build this once a secure server-side token-storage
  pattern is established as its own reviewed capability, not invented ad
  hoc here.
- **Media-byte inclusion** -- deferred honestly; would need either a richer
  iNaturalist integration (the live API's separate `observation_photos`
  upload, which itself needs the OAuth boundary above) or a different
  destination whose bulk-import format actually accepts media.
- **Single-Visit deep-link pre-selection** on the batch Ecological
  Destinations page -- today's per-Visit entry point navigates there but
  does not pre-filter to that one Visit.
- **A durable, unspoofable curator/preparer identity beyond the FK already
  used here** -- already resolved better than the older
  `ResearchCollectionModel.curator_identity` free-text convention (this
  milestone's own `prepared_by_user_id` uses the real FK), but a future
  pass could backfill the older convention to match.
- **Batch UI depth** -- filters are bounded to a date range today; stream/
  source/collection-scoped ecological batches would reuse
  `ResearchExportFilters` unchanged but need frontend controls this pass
  did not build (kept small deliberately, matching the milestone's own
  "smallest useful interface" instruction).
- **A GBIF backbone-taxonomy cross-check** -- `api.gbif.org/v1/species/match`
  was verified live and working but not integrated; would only be worth
  adding if a real product need for a second, independent taxonomy source
  emerges.
- **Darwin Core Event-core linkage** -- today's exporter is flat
  Occurrence-core only; a multi-subject/Event-scoped DwC-A would need a
  deliberate design decision, not an incidental addition.

## Capability maturity

**B** -- major, useful, real submission-ready interoperability (a genuine
iNaturalist CSV workflow a user can use today, plus a bounded, additive
Darwin Core standards export) with a clearly bounded, honestly-disclosed
account/live-destination limitation (no OAuth submit) and two destinations
correctly, evidence-backed deferred rather than forced (eBird's real policy
conflict; GBIF's real institutional gate). Not **A**: no live destination
round-trip was actually validated against a real account (by design, per
the Autonomous Development Rule -- no live credentials/participation was
requested or used). Not **C**: this is materially more than "adapter/export
foundation with substantial user workflow remaining" -- the iNaturalist
workflow is genuinely usable end-to-end today, proven by a real, executable
product-shaped scenario. Not **D**: nothing prevented acceptance; every
constraint found was evidence-based and correctly resolved into either a
real capability or an honest, cited deferral.

## Scheduler reconciliation

**CURRENT PHASE = SUBSTANTIAL PRODUCT DEVELOPMENT** -- confirmed unchanged.
Representative Field Acceptance, External Beta, and Final Release Hardening
remain downstream while substantial roadmap capability remains
intentionally unfinished (see the remaining-opportunities list above and
`docs/release-execution-state.md` §6 for the full, unrelated remaining
queue this milestone does not touch).

**CURRENT AUTHORIZED NEXT MILESTONE: NONE -- GLOBAL PRODUCT-ROADMAP
RECONCILIATION REQUIRED.** Not self-authorized: further provider
integrations (a live iNaturalist OAuth submit, any eBird workflow, direct
GBIF publication), release hardening, or any other milestone.

## Preserved files

Confirmed present, untouched, exactly the seven expected files, both before
and after this milestone's work:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

## Exact git status --short

Immediately after the reconciliation commit (this report + `release-
execution-state.md` + `roadmap.md`), the working tree returns to exactly
the seven preserved files, untouched, and nothing else:

```
?? docs/wildlife-detector-training-contract.md.orig
?? scripts/evaluate_small_bird_detector.py
?? scripts/materialize_wildlife_stage2.py.orig
?? scripts/train_wildlife_stage2_rfdetr.py.orig
?? src/mockingbird/detectors/small_bird_benchmark.py
?? src/mockingbird/training/wildlife.py.orig
?? tests/test_small_bird_benchmark.py
```

Nothing pushed (local accepted state; explicit authorization required).
