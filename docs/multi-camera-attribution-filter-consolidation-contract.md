# Multi-Camera Attribution & Filter Consolidation v1 -- Contract

Status: implemented 2026-10-03 (see the
[report](multi-camera-attribution-filter-consolidation-v1-report.md)).
Roadmap: Phase 7 (Multi-Camera) closure. Product flow: Observe -> Understand
-> Confirm (several cameras at one Place read as one coherent Place).
Schema: unchanged (`v62`). No new camera architecture.

This is consolidation and attribution closure only. Existing source/stream
foundations, cross-camera duplicate-encounter association, Camera health,
reviewed truth, and Place Intelligence are frozen and reused unmodified.

## Canonical identity and doctrine

- **Place** is the product's unit of understanding; a **Source** is the
  physical camera; a **Stream** is one feed of a Source (`StreamModel.source_id`).
  A **Visit** has no direct camera: Visit -> Event (`stream_id`) -> Stream ->
  Source. Display names are labels only; every filter and attribution is keyed
  by Source/Stream/Visit **id**.
- A wildlife encounter seen by overlapping cameras is **not** a merged record.
  Each camera keeps its own Visit/Event, independently reviewable. The only
  link is `CrossCameraVisitAssociationModel` (`tier` `associated`|`possible`,
  canonical primary = lexicographically smaller Visit id). Only `associated`
  is ever collapsed (counting, Today, Bird Log, and now Attention/Story);
  `possible` pairs, multi-subject downgrades, and merely similar simultaneous
  sightings are never merged. Taxon agreement is evaluated at read time.
- Place-level views (Dashboard, Today, Story as a whole, Biodiversity) stay
  Place-wide and gain no camera selector. Camera-level attribution appears only
  where an item is genuinely anchored to a concrete encounter.

## Residuals reproduced at `f886400` (all three real, none stale)

1. **Place Story attribution.** `PlaceStoryEvent.visit_id/source_id` were never
   populated for any wildlife kind; the shared all-time `GROUP BY
   reviewed_label` and trailing-window aggregates carry no Visit or Source, and
   the card's "View evidence" button therefore never rendered.
2. **Filter divergence.** No shared control: ~9 independent camera/Stream
   selects/checkbox groups with five "all" wordings ("All cameras", "All
   Streams", "Any Stream", ...), mixed Source-vs-Stream ids, URL state on 3
   pages via copy-pasted parsers, React-only state elsewhere, and a doubled
   "Camera"/"Camera / Source" pair on Activity Library that could contradict.
3. **Cross-camera Attention.** `review:{visit.id}` alerts are created per Visit
   before the association is reconciled, so an `associated` pair produced two
   review alerts (and two badge counts) while Today/Bird Log already showed one.

## 1. Place Story attribution model

- Entry gains `contributions: [{source_id, source_name, visit_id,
  source_archived}]` and a derived `source_scope`: `place_level` (none),
  `single_source`, `multiple_sources`. Legacy `source_id` is unchanged and still
  means the Feature's own camera for `feature_change` entries.
- Attributed kinds (anchored to concrete encounters): `first_seen` and
  `diversity_milestone` (the taxon's earliest reviewed Visit on its debut day),
  and `return` (that taxon's reviewed Visits on the displayed presence day).
  Contributors are one entry per Source (its earliest anchoring Visit), plus the
  Sources of any `associated` cross-camera partner Visit that is itself reviewed
  as the *same taxon*. `entry.visit_id` is the earliest contributing Visit.
- Place-level by design: `regularity_change`, `noteworthy_activity`,
  `feature_change`, `phenology`, `comparison_insight`, `year_over_year` --
  aggregate/Feature/trend facts. No camera is invented; with several
  contributors none is arbitrarily chosen.
- Composed in `ProductRepository._place_story_attach_contributions`, applied
  only to the returned page (bounded by `page_size`), read-only, from reviewed
  truth. The shared six-caller aggregation layer is deliberately **not**
  restructured.
- UI: concise "Seen on X" / "Seen by X, Y" line (archived cameras labelled),
  one "View evidence from <camera>" per contributor.

## 2. Filter consolidation model

- One vocabulary (`web/src/cameraFilter.ts`, pure) and one control
  (`web/src/components/CameraFilter.tsx`): single (`select`, first option
  "All cameras") or multiple (checkbox group, empty = every camera, never an
  empty list sent to a server). Selected ids the options cannot resolve stay
  visible as "Unavailable camera". Archived/sample cameras are labelled, never
  hidden (history remains reachable, matching the archive doctrine).
- URL convention: repeated `?source=<id>` (Source scope) or `?stream=<id>`
  (Stream scope); trimmed, de-duplicated, order-stable; absent = all.
- Migrated: Activity Library (one Source control; a deep-linked `?stream=`
  survives as a visible, clearable chip and is cleared when another camera is
  chosen), Bird Log species history (Stream), Collections detail (Stream),
  Ecological Destinations (Stream, same `?stream=`), Place Report (multi-select
  Sources, now URL-backed), Zone Insights (Source; a Stream the new camera does
  not own is cleared).
- **Intentionally not migrated:** Review Queue's composite `stream:`/`source:`
  option (server-built counts, queue-derived options, Fast Review scoping);
  create/import/setup/navigator forms that choose a *target* rather than filter
  (Manual/Folder Import, Setup, Species Suggestion/Motion Evidence create,
  Streams navigator, Place Feature camera links); Place-wide views with no
  per-camera semantics (Dashboard, Today, Story, Biodiversity, Wildlife
  Insights, Soundscape). Backend filter parameters are unchanged.

## 3. Calm Attention grouping

- Presentation-only. `ProductRepository._grouped_review_alert_condition`
  hides a review alert from the inbox list, unread count, and recent feed only
  when its Visit is the secondary of an `associated` pair whose **primary**
  Visit's review alert is still active. The alert row, Visit, review state, and
  resolution are untouched; nothing is merged or resolved.
- The visible representative carries `grouped_visits` (alert id, Visit id,
  stream, source) so each contributing camera's own Visit stays one click away.
- Per-user acknowledgement is unchanged: reading/dismissing the representative
  writes the *same user's* acknowledgement for its folded members (so resolving
  the representative later does not resurface the same sighting as fresh noise
  for that user); other users' rows are never touched; resolution stays global.
  When the representative resolves, still-unreviewed members stop being hidden
  -- an encounter that still needs a camera's review is never silently dropped.
- Unchanged: `possible` pairs, unrelated simultaneous wildlife, camera-health
  alerts (inherently per camera), first-label/digest/story alerts (already
  Place-level), alert id and `deduplication_key`.

## Supported 1.0 camera limit (documentation only)

`DEFAULT_MAX_CONCURRENT_STREAMS = 2` governs only the legacy RTSP / USB /
DirectShow armed-monitoring supervisor (and, independently, backend live
previews). Camera Node / Observation Engine Streams are exempt. Documented in
[runtime-map.md](runtime-map.md#legacy-local-camera-concurrency-limit) and the
README. The resource-aware replacement is deferred.

## Non-goals (held)

Multi-site/observatory, fleet management, LTE productization, dynamic
scheduler, sensor ingestion, cloud, background push, new providers, Camera Node
redesign, new reviewed-truth semantics, new duplicate-detection model work,
Linux packaging, a global dashboard/filter framework, any schema change.
