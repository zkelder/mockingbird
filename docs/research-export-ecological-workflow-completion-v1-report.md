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

## Bounded limitations

- Output is a directory bundle on the Host (no zip/download); the UI shows its path.
- Darwin Core / iNaturalist submissions reference media but do not copy bytes.
- Camtrap DP `filePath` for an omitted file still names the intended path; the omission
  is a validation warning and a `media-bundle.csv` row.
- No external Camtrap DP conformance validator (unchanged).
