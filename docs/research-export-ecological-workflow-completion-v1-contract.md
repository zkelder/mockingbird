# Research Export & Ecological Workflow Completion v1 -- Contract

Milestone 4 of the pre-1.0 queue. Governing existing contracts (frozen, reused
unmodified): [research-conservation-export-contract.md](research-conservation-export-contract.md),
[ecological-interoperability-submission-v1-contract.md](ecological-interoperability-submission-v1-contract.md),
[review-decision-provenance-contract.md](review-decision-provenance-contract.md).

Task packet: roadmap phase = pre-1.0 product completion (software-first);
product flow improved = Confirm -> Remember -> export; why next = Milestone 4
of the locked sequence; non-goals = OAuth/auto-upload/GBIF/cloud sync/new
review or collection authority/new inference/sensors/habitat outcomes/download
manager/background jobs; validation tier = Tier 2 (+ focused Playwright; Core
only if eligibility/serialization changes cross-cut).

## Reproduced at HEAD `6b927da` (schema v62)

| Residual | Verdict | Evidence |
| --- | --- | --- |
| 1. `include_media` packages no bytes | **Reproduced** | `export_research_dataset`/`export_camtrap_dp_package` never read the flag; the only bundle output is metadata. Camtrap DP `media.csv` already promises `filePath = media/<id><ext>` but no such file is ever written. The classifier-manifest `copy_media` precedent is dry-run only (`copy_media export is dry-run only`), so there is no byte-copy precedent to reuse. |
| 2. Visit -> export preselection | **Reproduced** | `VisitDetailPage`'s "Prepare for an external destination" button calls `setPage("ecological-destinations")` with no Visit context. |
| 3. Server-side filters not in UI | **Reproduced** | `ResearchExportFilters` supports start/end, stream_ids, source_ids, taxon_labels, acquisition_scope, collection_id. The only UI (Ecological Destinations) exposes start/end. There is no UI at all for the generic / Camtrap DP / Darwin Core exports (`apiClient.exportDarwinCore` has no caller). |

## Existing behavior being preserved

- **Format**: a bounded *directory* bundle under `research_export_root`, written to
  `.<id>.tmp` then atomically renamed. There is no archive (zip/tar) format and this
  milestone does not add one; "archive paths" below means paths inside the bundle.
- **Eligibility**: `evaluate_research_export_eligibility` is the only gate;
  media inclusion never feeds it. Only `eligible` observations contribute media.
- **Privacy**: Zone privacy/ignore withholding is already part of eligibility
  (trigger-level, never pixel redaction -- the UI copy keeps saying so).
- **Local Only**: all evidence media lives under the managed media root; nothing
  outside it is eligible. `ProductRepository._storage_managed_media_path` is the
  existing fail-closed resolver (relative/absolute handling, root containment,
  symlink-in-path, missing file, `.recovery`, size integrity) and is reused.
- **Sharing**: one MediaAsset can back several exported observations
  (multi-subject sibling Visits share a frame; crops reference the same asset).
  `media.csv` already dedups by media id.
- **Bounding**: no existing export-media limit exists.

## Media-byte inclusion (new)

When `include_media` is true (generic export and Camtrap DP):

1. The distinct media ids of the **already-eligible** observations are planned.
   Nothing else is ever considered.
2. Per media id, bundle path is `media/<media_id><ext>` where `ext` comes from a
   fixed content-type allowlist (the Camtrap DP one), never from a stored filename
   or path. A media id not matching `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$`, or a
   content type outside the allowlist, is **not bundled** (`omitted_unsafe_name` /
   `omitted_unsupported_type`). A case-insensitive name collision omits the later
   id (`omitted_name_collision`).
3. Source resolution uses `_storage_managed_media_path`; failures map to
   `omitted_missing` (missing/incomplete), `omitted_unsafe_path` (outside root,
   symlink, recovery path), `omitted_integrity_mismatch` (size or recorded
   `content_sha256` disagrees). The file is opened `O_NOFOLLOW` and streamed in
   chunks; bytes are never read via a user-supplied path.
4. **Missing/unsafe eligible media = partial success, not failure.** The
   observation's truth is valid; only the byte is absent. The bundle records an
   explicit per-media status and the manifest/response carry counts plus
   warnings. Every omitted file stays listed with its reason -- never silently
   dropped.
5. **Bounds**: `RESEARCH_EXPORT_MEDIA_MAX_FILES = 2000` and
   `RESEARCH_EXPORT_MEDIA_MAX_TOTAL_BYTES = 1 GiB`, checked up front from recorded
   sizes (also on dry-run). Exceeding either **refuses the export**
   (`research_export_media_limit_exceeded`) with the limit stated -- a silently
   half-filled bundle is worse than a refusal that says "narrow the filters".
6. **Linkage / checksums**: `media-bundle.csv` (deterministic, sorted by media id)
   with `media_id, observation_ids (pipe-joined, every exported observation
   referencing it), bundled_path, size_bytes, sha256 (of the bytes actually
   copied), status`. Deduplicated: one copy per media id regardless of references.
   `manifest.json` (generic) / response (Camtrap DP) carry a `media_bundle`
   summary (requested, bundled, omitted-by-reason, total bytes, warnings).
   Camtrap DP `media.csv` lists **only media actually bundled** (its `filePath`
   is the real archive member). Camtrap DP 1.0.2 requires `filePath` and has no
   "absent" value, so a media row for an omitted file is dropped and the
   observation's optional event-level `mediaID` is blanked; the omission stays
   in `media-bundle.csv` and the validation warnings. With `include_media=false`
   the package is metadata-only and keeps its intended relative `filePath`s.
7. **Eligibility change between selection and generation**: after bytes are
   copied and before the atomic rename, eligibility is recomputed; if the eligible
   set fingerprint differs the export aborts (`research_export_eligibility_changed`)
   and the temporary directory is removed. No partial bundle is ever published.
8. With `include_media=false` the output is byte-identical in shape to today
   (no `media/`, no `media-bundle.csv`, `media_bundle` is null).
9. Darwin Core stays reference-only (its request has no `include_media`; out of
   scope). iNaturalist submission media stays reference-only (unchanged).

Never transmitted anywhere; local write only.

## Single-Visit scoping (new, minimal)

`ResearchExportFilters.visit_ids` (<=50, optional) *intersects* the in-scope
Visit set. It can only narrow; it never bypasses eligibility, so a deep-linked
provisional Visit is returned as ineligible with its reasons rather than
exported. This is the one new filter semantic, required because the only other
way to scope an export to one Visit is creating a research collection (a write).

## Visit -> export workflow

Reuse the one existing workflow page (`/ecological-destinations`); no second
workflow. The Visit page's button navigates to
`/ecological-destinations?visit=<id>`. The page reads query state, runs the
eligibility preview scoped by `visit_ids`, preselects that Visit only if
eligible, and otherwise shows the server's own exclusion/needs-input reasons.

## Filters exposed in the UI

Direct mapping to existing semantics: date range, Stream, species (taxonomy
label), acquisition scope (live/offline/both). State is mirrored in the URL
query (`from`, `to`, `stream`, `taxon`, `scope`, `visit`) and restored on load.
`source_ids` is redundant with Stream for ordinary users and `collection_id` has
no UI surface anywhere (research collections are API/CLI only); both stay
server-side and are not exposed -- disclosed, not invented.

The same filter state drives a new "Research dataset bundle" panel on that page:
format (generic CSV/JSON, Camtrap DP, Darwin Core), include evidence photos,
dry-run preview, export. A successful export shows media-bundle counts/warnings
and a **Download export** action; the Host path is not shown in ordinary UI
(the API response still carries `output_directory` for CLI/operator use).

## Download (bounded retrieval)

`GET /api/research/exports/{export_id}/download` (authenticated like every
route) returns one generated export as a ZIP. Security/path model:

- The client sends an **id only**, never a path. The id must match
  `^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$` (no separators, no leading dot, so
  `.x.tmp` build directories are never served) and is resolved as a direct child
  of the managed `research_export_root`.
- A symlinked export directory is refused (`lstat`, then a resolved
  containment check); the walk never follows symlinks and archives regular files
  only; each member is opened `O_NOFOLLOW`.
- Members are `<export_id>/<relative posix path>`, sorted, fixed 1980-01-01
  timestamp, fixed mode; same export -> same bytes. Media is stored, text deflated.
- Bounds: 2100 members and 1 GiB + 64 MiB (HTTP 413 beyond); the archive is a
  temporary file deleted after the response.
- Missing/stale/malformed/unknown id -> one 404 with a path-free message.
- Scope: exports under `research_export_root` (generic, Camtrap DP, Darwin Core
  bundles). The iNaturalist submission CSV lives under a different root, has no
  export id, and is unchanged (still shows its path); not part of this fix.

## Schema

No migration. `ResearchExportFilters.visit_ids` and the manifest/response
`media_bundle` field are additive API-model changes (optional, null by default);
no exported row shape changes, so `research-export-v1` is kept unchanged.
