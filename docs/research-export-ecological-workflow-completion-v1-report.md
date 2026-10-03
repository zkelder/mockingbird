# Research Export & Ecological Workflow Completion v1 -- Report

Starting HEAD `6b927da`, schema `v62` (unchanged, no migration). Contract:
[research-export-ecological-workflow-completion-v1-contract.md](research-export-ecological-workflow-completion-v1-contract.md).

## Residuals

All three were **reproduced** (none stale): `include_media` was never read by the
generic or Camtrap DP export; the Visit page's export button carried no Visit;
the UI exposed only a date range and had no surface for generic / Camtrap DP /
Darwin Core export.

## Delivered

- **Media bytes** (generic + Camtrap DP): eligible observations only; `media/<id><ext>`
  names from a content-type allowlist; fail-closed source resolution
  (`_storage_managed_media_path`) plus `O_NOFOLLOW` streaming copy; `media-bundle.csv`
  with media id, every referencing observation id, path, size, sha256 of the bytes
  copied, status; one copy per media id. Missing/unsafe/mismatched/unsupported media
  is partial success with explicit per-file status and warnings; bounds of 2000 files /
  1 GiB refuse the export (also on dry-run); eligibility is re-checked before the atomic
  rename and a change aborts without publishing. Darwin Core stays reference-only.
- **Visit -> export**: `/ecological-destinations?visit=<id>` from reviewed and unreviewed
  Visit pages; new narrowing-only `ResearchExportFilters.visit_ids`; page explains
  ineligible/needs-input Visits using server reasons and never preselects them.
- **Filters in UI**: date range, Stream, species, live/imported scope, mirrored in the URL.
  `source_ids` and `collection_id` intentionally not exposed. A "Research dataset bundle"
  panel (format, include photos, preview, write) reuses the same filters.
- CLI: `--visit-id`, media summary output.

## Validation

- New `tests/test_research_media_bundle.py` (28) + API (2) + CLI; mutation-checked
  the eligibility re-check and path-safety tests.
- Research/export/privacy/eligibility/support/health subset: 231 passed (before final
  test additions); `tsc --noEmit` clean; production build clean.
- Browser: full suite 218/218 (211 + 7 new); two older ecological specs were scoped to
  the preview table because the new Species select repeats taxon names.
- Core (`verify_core.py`): 6342 passed / 0 failed, 4 skipped, 11 xfailed.

## Completion pass (acceptance gaps closed)

Starting HEAD `bbc803b`, schema `v62` (unchanged, no migration).

- **Retrievable export**: `GET /api/research/exports/{export_id}/download`
  (`mockingbird.research.export_archive`) serves a deterministic, bounded ZIP of
  one generated export; id-only, resolved inside `research_export_root`,
  symlinks refused/skipped, `O_NOFOLLOW`, safe `<export_id>/...` members, path-free
  404 for stale ids. The page now shows **Download export** after a successful
  write and no longer renders the Host path (API still returns
  `output_directory` for CLI/operators). Contract section "Download".
- **Truthful Camtrap DP media**: `restrict_package_to_bundled_media` drops the
  `media.csv` row of any media not actually bundled (missing, unsafe, integrity
  mismatch, unsupported, name collision) and blanks that observation's optional
  `mediaID`, then validation is recomputed. `media-bundle.csv` and warnings are
  unchanged. `include_media=false` keeps the intended relative `filePath`s.
- Tests: partial-success regression (one asset deleted, one bundled; mutation-checked),
  all-omitted (missing and checksum), metadata-only, generate->zip round trip;
  `tests/test_research_export_download.py` (auth, traversal, absolute path, stale,
  symlinked dir/members, determinism, temp cleanup); Playwright download spec.

## Bounded limitations

- Darwin Core / iNaturalist submissions reference media but do not copy bytes.
- The iNaturalist prepared-submission CSV (separate root, no export id) is not
  downloadable and still shows its path; outside this pass.
- The Playwright download test mocks the generate response (the shared e2e
  database has no reviewed data); the real generate->ZIP path is covered by
  backend tests.
- No external Camtrap DP conformance validator (unchanged).
