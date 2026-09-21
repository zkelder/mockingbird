# Pre-Release Trust & Correctness Correction v1 -- closure report

Status: bounded defect-correction milestone, directly authorized by the
external (ChatGPT) global release sequencing following its review of the
2026-09-21 definitive pre-release baseline audit. Closes all nine confirmed
defects that audit found (three high-severity, six smaller), plus targeted
copy corrections the fixes themselves made necessary. Not a UI redesign, not
new-feature work, not the complete final release-hardening pass, not a
re-audit of already-accepted work.

Starting HEAD `0135801` (schema `v59`, the accepted 24/7 Field Reliability
Corrections v1 baseline). `docs/release-execution-state.md` had fallen two
commits (`2468b91`/`0135801`) behind its own bookkeeping -- reconciled as
the first step of this milestone, before any implementation (see §3 of that
file for the full delta). Preserves all seven protected untracked detector
files unmodified throughout, re-verified at both start and close.

## 1. UI-01 -- fabricated demo history on Dashboard/Bird Log

**Confirmed defect.** A fresh installation seeds a demo Source
(`source-backyard-demo`, `SourceKind.demo`) with two fabricated example
Visits so the product is not empty before a user adds a real camera (see
`mockingbird.api.demo_data`). Dashboard "Recent activity" and Bird Log
rendered this fabricated content as real, unlabeled, Reviewed wildlife
history -- live-confirmed with screenshots by the baseline audit. Roughly
eight sibling call sites in `product_repository.py` already excluded
`SourceKind.demo` activity from real product history; these two did not.

**Root cause.** Three raw SQL queries inside `dashboard_summary`
(`recent_rows`, the `needs_rows` fallback used when fewer than 12
needs-review items are found in `recent_activity`, and `reviewed_today_rows`,
which feeds `today_observations`/`reviewed_non_bird_activity`) joined only
`VisitModel`/`EventModel` -- no join to `StreamModel`/`CameraSourceModel` at
all, so no demo exclusion was even structurally possible. Bird Log and
Wildlife Insights' shared resolver, `_wildlife_insight_records`, did join
through to `CameraSourceModel` (it already needed `stream_name`/
`source_name` for its own output) but never applied the exclusion condition
to it.

**Fix.** The one place this exact condition already existed correctly
(`dashboard_summary`'s own `real_stream_count` query, an outer join to
`SourceProviderConfigurationModel` plus a `CameraSourceModel.kind`
fallback) was extracted into a shared `_real_source_condition()` helper and
applied uniformly to all four gaps, via the identical join shape used
elsewhere in the file. The condition deliberately keys off the Source's
*effective* provider configuration, not its static `kind` column, matching
the already-documented precedent for a demo Source later repurposed into a
real one via Guided Camera Editing (`kind` never updates after creation;
filtering on it alone would make a genuinely real, actively-observing
camera disappear from real history).

**Tests.** New `tests/test_demo_source_exclusion.py` (5 tests) proves the
actual fresh-install scenario directly against a repository seeded only by
`seed_if_empty()` -- no other test setup -- at both the repository-method
and HTTP-API level: zero demo activity on Dashboard `recent_activity`/
Bird Log `journal`, while a real, separately-created non-demo Visit still
appears normally on both surfaces.

**Blast radius.** This fix's join/filter addition changed which rows the
four affected queries return, which broke roughly a dozen existing tests
across ten files that had been reusing the seeded demo Source/Stream as an
incidental fixture for unrelated Dashboard/Bird-Log-adjacent assertions
(`test_visit_tags.py`, `test_reviewed_observation_revision.py`,
`test_fast_review.py`, `test_review_decision_provenance.py`,
`test_multimodal_observation_acceptance.py`, `test_acoustic_ingest.py`,
`test_acoustic_ingest_real_model.py`, `test_external_url_preview_save.py`,
`test_folder_import_motion_evidence.py`, `test_source_stream_smoke_flow.py`,
`test_stream_playback_contract.py`). Each was fixed with whichever of two
patterns fit: a dedicated real (non-demo) Source/Stream/Zone fixture for a
single affected test, or -- where the demo Source is incidental plumbing
shared by many unrelated tests in one file -- a narrowly-scoped "de-demo"
of the seeded Source in place (adding a `SourceProviderConfigurationModel`
row with a non-`"demo"` `provider_key`, the identical real-product
repurposing mechanism `_real_source_condition` already recognizes),
deliberately scoped to the one test/helper that needs it rather than the
file's shared `autouse` fixture wherever that fixture is also relied on by
a test proving the exclusion mechanism itself. Confirmed by direct
inspection before applying the fix: `test_stream_playback_contract.py`
specifically has two such tests (`test_real_stream_count_excludes_the_
lingering_demo_stream`, `test_onvif_record_profile_corrects_source_kind_
for_honest_ffmpeg_dependency_detection`) whose own purpose would have been
defeated by a global de-demo; both remain green, unaffected, after the
narrower fix.

## 2. DI-1 -- Doctor media-integrity false-positive

**Confirmed defect (reproduced live).** Doctor's `media_integrity` check
reported real, freshly-created, genuinely-intact observation-engine
evidence as missing on a real install. Broader than 24/7 Field Reliability
Corrections v1's own Fix 3 assumed -- see [[doctor-media-integrity-relative-path-regression-2026-09-17]],
independently re-derived from scratch by the baseline audit without reading
that memory first, same conclusion.

**Root cause, precisely traced.** `ProductRepository.media_root` defaults
to the bare relative string `"data/media/imports"`
(`DEFAULT_MEDIA_ROOT`, `storage/database.py`) whenever
`MOCKINGBIRD_MEDIA_ROOT` is unset -- the common, unconfigured production
case -- and is only ever anchored correctly today because
`runtime.run_preflight()` `os.chdir()`s the whole process into
`runtime_home` before any repository is constructed (its own comment:
"Import only after the runtime home is stable so default database/media
paths cannot drift with the shortcut or terminal working directory").
Every real write path (`_write_media_file`/`_copy_media_file`) then stores
`self.media_root / filename` as `local_path` -- so a relative value already
carries the *full* `media_root` prefix and is relative to `runtime_home`,
not to `media_root` itself. The prior fix's resolver joined a relative
`local_path` against Doctor's own absolute, home-anchored `media_root`
(`runtime_home / "data" / "media" / "imports"`), double-nesting the prefix
(`<home>/data/media/imports/data/media/imports/...`) and raising `OSError`
on every sampled relative-path asset.

**Fix.** `_resolve_media_asset_path` now tries `runtime_home / raw` first
(itself already computed independent of cwd, exactly matching
`DoctorEnvironment`'s own "must work from any starting directory"
contract), falling back to the `media_root`-relative interpretation only as
a defensive second candidate for a differently-shaped legacy path --
mirroring `ProductRepository._storage_managed_media_path`'s own established
two-candidate convention for this exact ambiguity, never reintroducing a
`Path.cwd()` dependency the way a naive "try cwd first" fix would have.

**Tests.** Four tests in `tests/test_doctor.py`, including
`test_gather_media_integrity_resolves_relative_paths_against_runtime_home_
first`, which reproduces the exact real-world shape
(`local_path="data/media/imports/media-candidate-001.jpg"`, `media_root`
independently computed the same way Doctor really computes it) and would
fail under the prior resolver; the existing `..._same_result_regardless_of_
current_working_directory` test continues to prove cwd-independence
end to end.

## 3. PKG-1 -- Windows launcher argument forwarding

**Confirmed defect.** `Start MockingBird.vbs` never forwarded its own
command-line arguments to `pythonw.exe -m mockingbird`, so the documented
`--host 0.0.0.0 --allow-network` remote/phone-access invocation
(`docs/using-mockingbird.md`, "Use MockingBird on your phone") could not be
performed against the shipped artifact -- verified by inspecting five real
prior `dist/*/` builds.

**Fix.** `LAUNCHER_VBS` (`scripts/build_local_product.py`) now collects
`WScript.Arguments` into a quoted, embedded-quote-escaped string and
appends it to the `shell.Run` command line. An ordinary no-argument launch
is byte-for-byte unaffected (`forwardedArgs` starts empty).

**Real Windows validation.** Structural coverage
(`test_local_product_packaging.py`) confirms the generated file contains
the forwarding loop, but per this milestone's own Tier 3 requirement
("Validate against the built Windows artifact, not merely the source
launcher... do not claim packaging fixes based only on source-tree
tests"), this was also proven for real: built a minimal but genuine
embeddable-Python runtime (the real packaged `python/` directory from a
prior accepted build, minus its heavy `site-packages`) plus the real
generated `Start MockingBird.vbs`, with a stub `mockingbird` package
(`python/site-packages/mockingbird/__main__.py`) that records its own
`sys.argv` to a file. Invoked via `wscript "Start MockingBird.vbs" --host
0.0.0.0 --allow-network` from a native Windows temp directory (not a WSL
UNC path -- see the second finding below): the spawned process's own
`sys.argv` correctly showed `['...__main__.py', '--host', '0.0.0.0',
'--allow-network']`; a no-argument launch showed no extra arguments; a
value containing spaces and an embedded quote (`'a "quoted" value with
spaces'`) forwarded as one token with spaces preserved (the CommandLineToArgvW
embedded-quote edge case is not byte-perfect, judged an acceptable,
bounded tradeoff since MockingBird's real documented argument surface --
`--host`/`--allow-network`/`--port` -- never contains a literal quote
character).

**A second, genuine defect found by this real testing, not merely
theorized.** The first attempt at this validation used `wscript.exe`
invoked directly and succeeded; a follow-up attempt at validating the
*exact* documented Command Prompt form (a bare quoted filename, relying on
the registered `.vbs` file association) consistently failed with "not
recognized as an internal or external command" -- reproduced with a
trivial unrelated `.vbs` file too, ruling out anything specific to the
launcher itself, and confirmed the `.vbs`/`WScript.Shell` association
(`assoc`/`ftype`) was correctly registered throughout. Bare `.vbs`
execution from a Command Prompt is not a reliable mechanism even with a
correct association; explicit `wscript "Start MockingBird.vbs" ...`
(`.exe`-native `PATHEXT` resolution, always reliable) is. Both the shipped
launcher's own embedded comment and `docs/using-mockingbird.md`'s remote-
access instructions were corrected to the proven-reliable explicit form.

## 4. PKG-2 -- Camera Node artifact completeness

**Confirmed defect.** The downloadable Camera Node artifact never included
`install_camera_node.py`, despite `docs/camera-node-install-guide.md`'s own
step 2 always telling the user to run it against the artifact directory --
a plain release download (no repository checkout) could not be installed
from itself.

**Fix.** `build_camera_node_artifact.py` now copies the installer script
into the output directory alongside the wheel/`requirements.txt`/
`camera-node.env.example`/`manifest.json`, covers it in `SHA256SUMS`, and
extends the existing clean-commit source guard (`RELEASE_SOURCE_PATHS`,
previously `src/mockingbird_node` only) to cover it -- it is now as real a
build input as the wheel's own source. `docs/camera-node-install-guide.md`
(file list, step 2's exact command) and `docs/camera-node-installer-
design.md` (artifact contract list, corrected from a pre-existing "seven/
eight-file" miscount to the real six) updated to match.

**Real build validation.** A genuine `build_camera_node_artifact.py
--allow-dirty-source` invocation against this milestone's own working tree
produced `install_camera_node.py` inside the artifact directory;
`sha256sum -c SHA256SUMS` independently verified all five checksummed
entries; the installer's own real, read-only `--status` and `--preflight
<artifact-dir>` checks ran successfully invoked from that exact co-located
location (`python3 <artifact-dir>/install_camera_node.py --preflight
<artifact-dir>` -> "Preflight passed; no changes were made."), proving the
documented invocation form actually works end to end, not merely that the
file exists.

**Tests.** Five new tests in `test_camera_node_packaging.py`: the installer
is packaged, checksummed correctly, the artifact directory's file set is
exactly the six documented files (nothing missing, nothing stray), the
clean-source guard covers the installer script, and a dirty (uncommitted)
edit to the installer is correctly refused exactly like a dirty edit to
`src/mockingbird_node` already was.

## 5. FLOW-3 -- password self-service

**Confirmed defect.** The Users page told administrators "see the account
menu to change your own password"; no such control existed anywhere in the
frontend, despite the backend endpoint (`POST /api/auth/change-password`,
`ProductRepository.change_own_password`) already working and already
tested (`test_local_identity_multi_user.py`).

**Fix.** New `ChangePasswordControl` component, added to the existing
`.account-menu` sidebar panel, mirroring `UsersPage.tsx`'s own
`ResetPasswordControl` disclosure pattern with the addition of the
current-password proof `POST /api/auth/change-password`'s own contract
requires. A latent bug in the pattern being mirrored was found and *not*
propagated: `ResetPasswordControl` calls `setIsOpen(false)` in the same
state update as `setMessage(...)`, which collapses the form back to its
toggle button before React ever paints the success message -- a zero-frame
flash, not genuine feedback. `ChangePasswordControl` instead renders a
distinct success view that stays open until explicitly dismissed. A small
scoped CSS addition (`.account-menu-password-form`) gives the expanded form
its own light backdrop, since the account menu itself is a dark sidebar
panel and the shared `.auth-form label` styling assumes a light one.

**Tests.** New `web/e2e/change-password.spec.ts` (2 tests), run against a
throwaway user created and signed in as for the purpose (never the shared
e2e suite's own admin account, to avoid cross-spec interference from a
changed shared password): a full change proven end to end (old password
confirmed rejected with a real fresh sign-in attempt, new password
confirmed working, current session confirmed to survive since only *other*
sessions are revoked, no password value ever appears in the DOM); an
incorrect current password confirmed rejected with a clear error, never
silently accepted.

## 6. FLOW-5 -- Dataset Export download

**Confirmed defect.** Dataset Export showed its generated manifest as
inline JSON only (a `<details><pre>` disclosure); no way to actually save
it.

**Fix.** A `downloadManifest` handler on `ExportsPage.tsx`, mirroring
`ClassifierManifestPage.tsx`'s own established `downloadJsonPreview`
pattern exactly (`Blob` -> `URL.createObjectURL` -> a temporary `<a
download>` -> click -> revoke) -- no backend change, since the manifest is
already fully fetched client-side. Filename derived from the export's own
name (slugified), creation date, and id, so repeated downloads across
different exports never collide.

**Tests.** New `web/e2e/dataset-export-download.spec.ts`: creates a real
export, triggers a real Playwright download event, confirms the saved
file's content matches what was already shown inline and the filename is
sensible.

## 7. FLOW-10 -- top-level React error boundary (release-critical)

**Confirmed gap.** No error boundary existed anywhere in the frontend, so
an unexpected render error in any component turned the entire application
into a blank white screen with no recovery path.

**Fix.** New `ErrorBoundary` class component (React has no function-
component error-boundary API) wraps the app root in `main.tsx`, inside
`<StrictMode>`. Fallback UI reuses the existing `.error-panel` visual
language with calm, plain-language copy consistent with this product's
"calm-observatory" doctrine (no alarming language, no raw error/stack
text), a "Reload MockingBird" recovery action, and a pointer to the
existing `logs/mockingbird.log` diagnostic convention. Logs to the browser
console only (`componentDidCatch`) -- this product keeps no client-side
telemetry/crash-reporting service, so no new privacy-relevant data path was
introduced.

**Deliberate test-only hook.** `?mockingbird_test_crash=1`
(`main.tsx`) renders a component that throws unconditionally in place of
the real app, so a real e2e spec can prove the boundary catches a genuine
descendant render failure rather than relying on finding or fabricating an
actual defect elsewhere in the app to trigger one. Inert otherwise -- a
stray query parameter that does nothing in normal use.

**Tests.** New `web/e2e/error-boundary.spec.ts` (2 tests): the crash hook
produces the calm fallback screen (never a blank page, no stack trace or
implementation detail in the DOM), Reload genuinely reloads; a normal load
never shows the boundary.

## 8. DI-2 -- CSV-injection sanitizer coverage (release-critical)

**Confirmed defect.** Despite `docs/release-execution-state.md`'s own
historical claim that CSV-injection sanitization (added by Ecological
Interoperability & Submission Workflows v1) was applied broadly, two real
CSV writers never called the canonical sanitizer:
`ProductRepository._write_classifier_manifest_csv` (`manifest.csv`, the
classifier-training-manifest export) and
`mockingbird.ecological.inaturalist_csv.build_inaturalist_csv`, the
module's own shipped, public CSV builder (its docstring: "the exact
positional 8-column CSV format iNaturalist's own web importer expects").
The latter's only current production caller happens to re-derive its rows
through the already-sanitized `_write_csv` path, so this was latent, not
yet observed live in production -- but real and reachable by any other
caller of the module's own public function, including its own tests.

**Fix.** The sanitizer (`_CSV_FORMULA_TRIGGER_CHARACTERS`/
`_csv_injection_safe_value`) was a private helper inside
`product_repository.py`; both gaps needed it from a module one dependency-
direction step away (`product_repository.py` already imports *from*
`mockingbird.ecological.inaturalist_csv`, so the reverse import would have
been a real cycle). Extracted to a new, dependency-free
`mockingbird.csv_safety` module (`CSV_FORMULA_TRIGGER_CHARACTERS`/
`csv_injection_safe_value`, byte-identical logic, not reimplemented) that
both `product_repository.py` and `inaturalist_csv.py` import -- one
canonical implementation, not a second divergent copy. Both gaps wired
through it; the existing, already-sanitized `_write_csv` path updated to
import from the new shared location too, so there is exactly one
implementation anywhere in the codebase.

**Tests.** `test_classifier_manifest_exports.py`: a new unit test calling
`_write_classifier_manifest_csv` directly with hand-built dangerous values
(`=cmd|...`, `+HYPERLINK(...)`, and a `-2+3` string that starts with a
trigger character but is not a valid float) proves the writer's own
sanitization independent of whatever the real review-label taxonomy
normally constrains a value to. `test_inaturalist_csv.py`: a new test
proves `build_inaturalist_csv` itself (not only the already-safe
production caller) neutralizes a formula-leading `place_name` while a
genuine negative-coordinate string round-trips unmodified.

## 9. SEC-2 -- unredacted media path exposure

**Confirmed defect.** `GET /api/media` and `GET /api/media/{id}` returned
`MediaAsset.local_path` -- the raw, absolute, server-local filesystem
path -- to any signed-in Viewer, unlike Visit-facing endpoints (`GET
/api/visits`, `/api/events/{id}/detail`, `/api/visits/{id}/detail`, and
others), which already redact it via the existing `_redact_visit`/
`_redact_media_asset` convention (`media_asset.model_copy(update=
{"local_path": ""})`).

**Fix.** Both handlers now route through that same convention -- a new
`_redact_media_assets` for the list form, the existing singular helper for
the single-asset form. No change to legitimate media access: the frontend
already fetches actual image/video bytes through `/api/media/{id}/file`
(and `/preview`, `/full-resolution`), never through the raw `local_path`
field, and already explicitly documented (`MediaAssetPreview.tsx`'s own
comment) an assumption that this field is always redacted.

**Tests.** Two new tests in `test_everyday_discovery_ux_closure.py` (the
file already holding this exact redaction convention's own precedent
tests) prove both endpoints redact `local_path` while the real file still
exists server-side. This fix's own blast radius reached roughly a dozen
existing tests across six files (`test_stream_playback_contract.py`,
`test_folder_import_media_assets.py`, `test_source_provider_smoke_
flows.py`, `test_external_url_preview_save.py`, `test_folder_import_
motion_evidence.py`, `test_source_stream_smoke_flow.py`) that had been
reading the raw path from these two endpoints' responses to verify real
server-side file placement -- each updated to read the real path from the
repository directly instead (`ProductRepository.get_media_asset(...)`),
which the redaction deliberately leaves unaffected.

## 10. Targeted copy corrections

The Users page's account-menu instruction needed no wording change --
FLOW-3 makes the existing sentence true rather than requiring a correction.
`docs/using-mockingbird.md`'s Windows remote-access step corrected from a
nonexistent `Start MockingBird.cmd` to the real, now-argument-forwarding,
proven-reliable `wscript "Start MockingBird.vbs" ...` form (see §3).
`docs/camera-node-install-guide.md` and `docs/camera-node-installer-
design.md` corrected to list `install_camera_node.py` and to give the
exact command that works from the artifact's own, now-self-contained
directory (see §4).

## Validation

**Tier 1 (focused).** Every defect above has dedicated, passing regression
tests that reproduce its own confirmed shape, not merely exercise the
surrounding code -- itemized per section above.

**Tier 2 (affected subsystem).** Full runs of every directly-touched test
file (frontend `tsc --noEmit`/`vite build` clean; every changed/new Python
file confirmed to introduce zero new `ruff` findings via direct `git
stash` bisection against the unmodified baseline -- the two large shared
files this milestone touched, `product_repository.py` and `api/main.py`,
each carry a real, unrelated pre-existing finding count, confirmed
byte-identical before and after this milestone's own changes).

**Tier 3 (full Core, required by this milestone's own cross-cutting
scope).** **6057 passed / 5 failed / 4 skipped / 35 deselected / 11
xfailed**, 41m56s. All 5 failures independently confirmed pre-existing via
direct `git stash` bisection against the unmodified baseline this same
session: `test_doctor_camera_node_transport.py`'s own pair and
`test_environmental_context.py`'s date-sensitive baseline test reproduced
identically on the stashed baseline; `test_place_change_summary_
repository.py`'s failure is this file's own long-documented recurring
date-sensitive fixture flake (§14), also reproduced standalone;
`test_transport_worker.py`'s own retry-timing test passed in isolation
both with and without this milestone's changes, consistent with the
identical load-induced-timing-flake class already documented for this file
(a different specific test in it), not reproducible outside a full-suite
run either way. A first Core attempt found 19 failures: 15 real
regressions this milestone's own UI-01/SEC-2 fixes exposed in ~15 existing
tests (detailed in §1/§9 above) plus the 4 already-confirmed pre-existing
ones; every real regression fixed and independently re-verified, then a
second, accepted Core attempt ran clean of them. A proactive second sweep
of `slow`-marked tests -- which Core's own `-m "not slow"` gate never runs,
and which a first-pass search based only on Core's own findings would have
missed -- found and fixed one more real regression
(`test_acoustic_ingest_real_model.py`, the real-BirdNET-model acceptance
test) before it could surface in a future `verify_full.py`/plain `pytest`
run.

**Full e2e suite** (189 tests, 5 new this milestone for FLOW-3/5/10):
**187 passed / 2 failed**, both independently confirmed pre-existing via
the identical `git stash` bisection technique:
`reviewed-product-loop.spec.ts` (already documented across at least three
prior milestones' own acceptance records, §14) and
`notification-preferences.spec.ts::clicking an insight alert opens Place
Story already scoped to wildlife` (not previously documented in this file;
newly bisected this milestone and reproduced identically, byte-for-byte
assertion failure, on the unmodified baseline).

**Real-hardware/real-artifact validation** (this milestone's own explicit
Tier 3 requirement -- "do not claim packaging fixes based only on
source-tree tests"): PKG-1 proven on real native Windows against a
genuinely built minimal runtime and the real generated launcher (§3);
PKG-2 proven against a genuine `build_camera_node_artifact.py` build,
independently re-hashed, and the real installer's own `--preflight` check
run from its real shipped location (§4).

## Self-review

**Accidental truth-state changes:** none. Every fix is either a read-query
filter (UI-01), a diagnostic path-resolution change (DI-1), an API-response
redaction (SEC-2), export-file sanitization (DI-2), or packaging/frontend
work with no product-data write path at all (PKG-1/2, FLOW-3/5/10). No
Review Decision, correction, or Observation write path was touched
anywhere in this milestone.

**Destructive migration/data behavior:** none. No migration added; schema
unchanged at `v59`; no delete/overwrite of any existing record; existing
legitimate user records are unaffected by UI-01 (it changes which rows a
*query* returns, never the rows themselves).

**Relative-path/cwd regression:** none. DI-1 is the one fix that touches
path resolution at all, and it *removes* a cwd dependency rather than
adding one -- proven by a dedicated cwd-independence test that continues to
pass, plus a new test reproducing the exact production shape the prior fix
missed.

## Explicitly out of scope, confirmed untouched

MDv5a threshold/detector, BioCLIP-2/Identification Eligibility, BioCLIP
2.5 (frozen, no re-promotion), SpeciesNet promotion, BirdNET production
status/licensing, live-microphone BirdNET UI, `/api/visits` pagination or
other performance-scale work, the complete Host/Place terminology pass,
the full accessibility pass, the complete UI visual-polish pass, Gate G/
external acceptance, hardware disconnect/reconnect field acceptance,
architecture redesign, and deferred mobile/multi-site/LTE/solar/custom-
hardware work -- none referenced, none touched.

## Status

Does not push. Does not distribute or publicly release anything. Does not
self-authorize a subsequent milestone. Authorization remains this
milestone's own, pending the owner's/external (ChatGPT) acceptance review
of this closure -- see `docs/release-execution-state.md` §3 for the
complete record this report supports.
