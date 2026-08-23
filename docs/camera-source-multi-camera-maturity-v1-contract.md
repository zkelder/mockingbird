# Camera / Source + Multi-Camera Maturity v1 Contract

## Purpose

Make Camera/Source/Area/Place behavior coherent when a Place has more than
one real camera. This milestone matures the existing Source/Camera model
and existing multi-camera behavior; it does not redesign the data model,
build the full multi-property remote product, or start mobile/PWA or
release hardening.

## Camera / Source / Area contract

- **Camera**: the user-facing physical/virtual capture device. Implemented
  as one `CameraSourceModel` row (table `camera_sources`) paired with
  exactly one `StreamModel` -- every current creation path
  (`create_camera_source`, `complete_camera_setup`) makes exactly one Stream
  per Source, and no route exists to add a second. "Camera" and "Source"
  are the same persisted row under two names, not two distinguished
  concepts -- `CameraSourceModel` is literally the class name.
- **Source**: the durable technical acquisition identity, used internally
  (`source_id` foreign keys, provider configuration) and in surfaces where
  the distinction is genuinely useful (Review Queue, Activity Library,
  cross-camera attribution).
- **Area**: the human-meaningful place a camera covers. Not a new entity --
  a Stream's own single active, non-privacy, non-ignore Zone name (see
  `ProductRepository._representative_area_name`). A Stream with zero or
  more than one such Zone has no unambiguous Area; this is reported as
  `None`, never guessed. The Add Camera wizard already called its one
  setup-time Zone "Area" before this milestone; this contract extends that
  existing vocabulary into the several-camera surfaces this milestone adds
  (camera health, cross-camera association) without renaming Stream
  Detail's own full multi-Zone editor, which remains "Zone" -- a genuinely
  different, richer concept (multiple typed regions per Stream) that a
  repo-wide rename would conflate, not clarify.
- **Zone**: unchanged. The full, potentially-plural, typed geometric region
  system. Out of this milestone's rename scope.
- **Place**: unchanged -- the whole local installation. No `PlaceModel`
  exists or is added by this milestone (see Phase O).

## Compatibility model (Phase D)

`mockingbird.observation.provider_compatibility.classify_provider_
compatibility(provider_key)` returns one of five bounded levels:
`certified` (only `camera_node` -- real field-acceptance history, never
assigned merely because a provider key exists), `compatible` (`external_url`,
`onvif`, `local_usb`, `microphone` -- fully built, genuinely usable),
`experimental` (`webhook_future`, `demo` -- real but narrower/less proven),
`import_only` (`manual_media`, `folder_import_future` -- fully built,
deliberately non-live by design), `unsupported` (`rtsp_future`,
`esp32_future`, `browser_camera_future` -- no real implementation yet).

This reconciles five previously-disagreeing vocabularies
(`SourceProviderKind`, `SourceProviderDefinitionStatus`, `readiness_level`,
`unified_status.PROVIDER_SUPPORT_MATRIX`, `CameraSetupOption.availability`)
that all shared one token (`"future_adapter"`/`observation_unavailable`)
between genuinely-unbuilt stubs and the fully-built, tested
`folder_import_future`/`manual_media` import paths -- under-claiming a real
capability as equivalent to vaporware. `PROVIDER_SUPPORT_MATRIX` itself is
unchanged and still correctly answers its own narrower question ("does live
Observation Engine analysis run on this provider").

Surfaced via `SourceProviderDefinition.compatibility`/`compatibility_label`
and `CameraSetupOption.compatibility`/`compatibility_label` -- the Add
Camera wizard's provider list and the Streams page's "Provider setup" edit
dropdown both show the plain-language label, and the edit dropdown now
disables genuinely-unsupported providers (previously ungated, unlike Add
Camera's own list).

Not built in this pass (bounded gap): a full per-provider capability list
(live preview / continuous monitoring / recorded-media ingest / audio /
remote-WAN / hardware controls / known limitations). The classification
level is the truthful headline; the fuller capability matrix remains future
work.

## Overlapping-camera policy (Phase I)

The single most important correctness question this milestone answers:
when two cameras observe activity close in time, is it the same wildlife
encounter or two independent ones?

### What existed before this milestone

Nothing. Visit/Event assembly, arbitration, and admission authority are
scoped per-Stream at every layer (schema FK, the `classify_boundary`
assembly algorithm's first rule `different_stream -> incompatible`, the
per-Stream live runtime session, the per-Stream authority-settings primary
key). No code anywhere compared evidence from two different Sources for the
same time window, even in stub form -- confirmed by dedicated archaeology.

The one existing precedent worth extending: `VisitAssociationModel`
(schema 46, table `visit_associations`) already links a visual candidate
Visit to a temporally-related acoustic candidate Visit, using a pure,
deterministic, conservative tiering engine
(`multimodal_association.evaluate_temporal_association`) explicitly written
direction-agnostic for reuse.

### What this milestone builds

A visual+visual sibling, not a reuse of the multimodal table's own columns
(`acoustic_visit_id` is `NOT NULL` and SQLite has no `ALTER COLUMN` to
loosen it cheaply -- see `CrossCameraVisitAssociationModel`'s own
docstring). Schema 47 adds one new, empty, additive table,
`cross_camera_visit_associations`.

`mockingbird.observation.cross_camera_association.evaluate_cross_camera_
association` reuses `evaluate_temporal_association` completely unchanged
for the timing signal, then applies two additional, downgrade-only gates
before a pair can ever reach the confident `"associated"` tier:

1. **Single subject on both sides.** Two concurrent subjects on either
   camera (Phase J) makes the pairing inherently ambiguous -- capped at
   `"possible"` even if timing alone looked unambiguous.
2. **Spatial plausibility**, using the one real, user-authored signal
   available: each Stream's representative Area name (above). Three cases:
   both sides name the *same* Area (`"matching_area_name"`, the only case
   that can reach `"associated"`); both sides name a *different* Area
   (`"differing_area_name"`) -- real evidence of physical separation, so
   this candidate is dropped entirely before the ambiguity check even
   runs, never merely downgraded to `"possible"` (Journey 6's own
   no-false-merge-and-no-noise requirement); or either side has no
   unambiguous Area (`"unknown"`) -- genuine ambiguity, capped at
   `"possible"`.

`"associated"` therefore requires: exactly one competing candidate Event in
range (after differing-Area candidates are excluded), the strict timing
window, exactly one Visit on each side, and matching Area names. Species/
taxon equality is never an input to tiering, at any point (`classify_taxon_
agreement` is reused unmodified, read-time-only, exactly as for multimodal
pairs).

### What is persisted

Only positive findings (`"associated"`/`"possible"`) -- an out-of-range
pair or a confirmed-differing-Area pair gets no row at all, matching this
codebase's established "never fabricate a relationship" convention.
`spatial_signal`/`multi_subject` are persisted alongside `tier` (unlike
taxon agreement) because, together, they are *why* a pair reached its
tier -- diagnostic and review-facing honesty.

Reconciliation (`ProductRepository._reconcile_cross_camera_association_
for_event`) runs a full recompute of a subject Event's picture on every
new/joined candidate Visit, and (unlike the multimodal engine, which is
asymmetric by modality) also cascades to every nearby different-Source
Event's own picture -- a brand-new Camera C arrival can turn an
already-`"associated"` Camera A <-> Camera B pair genuinely ambiguous, and
that correction must land immediately, not only the next time A or B
itself changes (`_nearby_cross_camera_event_ids`).

### How presentation dedup works

Mirrors the existing multimodal presentation pattern exactly:
`_collapse_associated_cross_camera_pairs`/`_collapse_associated_cross_
camera_journal_observations` collapse a confidently-associated pair into
one list row (Today's `recent_activity`/`best_moments`, Bird Log's
gallery) -- run after the existing multimodal collapse, never replacing
it. Both original Visits remain fully, independently reachable via the new
`cross_camera_partner` field and the Visit Detail page's own cross-camera
association panel (mirrors the multimodal panel's plain wording: "Also
seen on {camera}", "Likely the same encounter" / "Possibly related").

For *counting* contexts (Place Activity Report, Phase H) rather than
*display* contexts, there is nothing to merge into one row -- only an
exclusion set. `_associated_visit_ids_to_exclude_from_counting` excludes
the lexicographically larger id of every confirmed `"associated"` pair
(multimodal or cross-camera) before the pure `place_activity_report`
module ever sees the fact list, so a real encounter observed by two
Sources counts once, not twice, in every downstream count (species-day
totals, historical baseline, change windows).

### Known bounded gap

Three-way fusion (a mic-associated Visit that is *also* cross-camera
associated with a second camera) is not specially handled -- the two
collapse passes run sequentially, so a Visit already absorbed by the
multimodal collapse cannot separately participate in the cross-camera
collapse in the same list render. Disclosed, not silently dropped: a real
but narrow edge case for a home installation, not attempted in this v1.

Inherited from the multimodal engine's own existing scoping, not newly
introduced: reconciliation only ever re-examines a candidate Event that is
*currently* in temporal range. If a previously-in-range candidate later
falls out of scope only because all of its own Visits become superseded
(never because either Event's own window narrows -- Event windows only
grow) without any other nearby Event ever changing again, its stale
association row is not swept. The cross-camera cascade
(`_nearby_cross_camera_event_ids`) actually closes most of this gap
relative to the multimodal case, since either side's own future activity
re-triggers a full recompute of the pair -- this residual is narrower than
the one the multimodal engine already carries, not a new risk.

YardMap field-of-view geometry (`YardMapStreamPlacementModel`) is not used
as a spatial signal in this v1 -- only the Area-name match. A future pass
could add it as a second, richer signal without changing this contract.

## Health-state coherence (Phase F/K)

`CameraHealthSummary` gains `connectivity_reason`, `backlog_pending_count`,
`backlog_last_synced_at`, and `area_name` -- all additive, all `None` by
default (every existing installation's behavior is unchanged).

`connectivity_reason == "host_unreachable"` is set only when there is
*positive* evidence the paired Camera Node is alive despite the ordinary
host<->Node API path failing: Remote/Intermittent-WAN Transport is
configured for this Source, and its last self-reported contact is fresher
than one hour (`_CAMERA_NODE_TRANSPORT_STALE_AFTER_SECONDS`, the same
threshold Doctor's own transport check already uses). Scoped to exactly
the one failure class it can honestly speak to (`failure_code ==
"node_unavailable"`) -- a rejected credential or any other failure is never
relabeled as a connectivity issue. Absence of evidence never becomes a
claim in the other direction ("camera_hardware"); it stays honestly unset,
identical to today's behavior.

`backlog_pending_count`/`backlog_last_synced_at` are surfaced regardless of
current health, reusing the same Remote Transport backlog fact Doctor's
CLI-only `_gather_camera_node_transport` already reads -- previously
invisible in all normal (non-CLI) UI. Phrased in the milestone brief's own
target language ("The camera kept working while disconnected and has 14
items waiting to sync"), never transport/protocol jargon.

`cameraHealthTone` (the one canonical severity mapping, `web/src/utils.ts`)
gains a fourth tone, `"alert"`, for `camera_unavailable`/`no_recent_frame`
(retries exhausted, genuinely needs attention) -- previously identical to
`recovering`'s calmer, self-healing amber. `LiveCameraOverview.tsx`
previously duplicated its own copy of the label/tone mapping instead of
reusing the canonical helpers (the exact divergence risk the original "B7
health model" was built to prevent); refactored to reuse `cameraHealthLabel`/
`cameraHealthTone` directly, so this fix (and any future one) applies
everywhere at once. `YardMapPage.tsx`/`DashboardPage.tsx` already reused the
canonical helpers and needed no change.

## Several-camera place-level experience (Phase E)

Matured, not rebuilt: `LiveCameraOverview.tsx` (already the Streams page's
per-camera roster) and Dashboard's "Cameras needing attention" list both
now show a camera's Area name and, when applicable, the connectivity/
backlog facts above -- reusing the already-existing, already-populated
`CameraHealthSummary` nested on `DashboardStreamSummary`/`dashboard_
summary().observation_health`, so no new endpoint was needed.
`GET /api/camera-health` (`CameraHealthListResponse`, already `source_id`/
`source_name`-aware) and its typed client method existed unused before
this milestone; still available for a future dedicated roster page, not
required for the surfaces this milestone matured.

## Source attribution (Phase G)

`VisitDetail.source_name` (new field) resolves `stream.source_id` to its
actual display name -- `VisitDetailPage.tsx`'s "Source" fact previously
rendered the raw UUID directly, the most-visited attribution surface in the
product, confirmed by independent archaeology. Mirrors `DashboardVisitSummary.
source_name`'s existing precedent, applied to the one surface missing it.

## Source filtering (Phase N)

`PlaceActivityReportRequest.source_ids` (new, optional, additive field) --
`None` (every existing caller) is byte-identical to the unfiltered report;
a non-empty list narrows the same in-scope Stream set every downstream
computation (coverage, historical baseline, representative evidence,
digest) already uses. Never changes reviewed truth, only which of it one
report call includes. Activity Library already had full `stream_id`/
`source_id` filters before this milestone; Bird Log has `stream_id` only
(Source:Stream is 1:1 in practice today, so this is a low-severity, not
fixed in this pass, naming-only gap).

Bounded gap: no frontend filter control was built for Place Activity
Report's new `source_ids` field in this pass -- the backend capability
exists and is tested; wiring a UI control is deferred.

## Multi-site readiness (Phase O)

Camera/Source name uniqueness is enforced globally, install-wide
(`create_camera_source`/`update_camera_source`) -- correct for today's
single-Place architecture (no `PlaceModel` exists to scope it narrower to),
not a bug. Both enforcement sites are already centralized, so re-scoping to
per-Place uniqueness when a future Multi-Site milestone introduces a real
Place entity is mechanical. No additive fix was needed or made in this
pass; documented here for that future milestone rather than acted on now.

## Schema

v46 -> v47. One additive migration
(`_migrate_to_cross_camera_visit_association`): the empty
`cross_camera_visit_associations` table, no backfill, no change to any
existing table or column -- mirrors `_migrate_to_visit_multimodal_
association`'s own precedent exactly.
