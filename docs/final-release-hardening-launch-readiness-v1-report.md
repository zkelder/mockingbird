# Final Release Hardening & Launch Readiness v1 — Report

**Status:** implementation-time record. This report is extended by this
milestone's own reconciliation commit with the real-build and real-hardware
evidence gathered after this commit (the release artifact must be built
from a clean, committed HEAD — see "Release-build source integrity" in
`docs/local-product-packaging-design.md` — so that evidence necessarily
follows this commit, mirroring the existing two-commit convention this
project already uses for every prior milestone).

**Classification:** to be assigned at reconciliation, pending the
real-build/hardware-validation evidence below being added.

Directly authorized (this is the final engineering/hardening pass for the
one public MockingBird release, following ChatGPT's acceptance of *Product
Operations & First-Observation Completion v1* at classification A). Starting
baseline verified exactly as expected: HEAD `fa83eec`, schema `v59`, Gate A
`PASS`/Lane R `CLOSED`, Lane P `CLOSED`, Gate G prepared/not started, no
active competing writer (confirmed with the user directly — see below), the
seven preserved untracked detector files present and unmodified throughout.

## 0. Competing-writer check

`ListAgents` showed one other interactive session (`mockingbird-active-39`,
started ~11h before this one) not marked offline, unlike every other listed
peer. This project's own operating rules (§13,
`docs/release-execution-state.md`) forbid concurrent writer sessions in one
working tree, and this session has no way to message that one directly to
check its state. Asked the user directly; confirmed idle. Proceeded.

## 1. Release versioning and metadata (governing brief §2)

`0.1.0` was dev-scaffolding never revisited since the project's earliest
commits — not an intentional public version, and actively misleading under
ordinary SemVer convention (0.x signals "anything may change") for a
feature-frozen, Gate-A-passed, one-time public release. Bumped to `1.0.0`
across every literal the project's own existing single-source-of-truth
contract names (`pyproject.toml`'s `[project].version`,
`mockingbird.__init__._DEV_CHECKOUT_FALLBACK_VERSION`,
`mockingbird_node.__init__.__version__`, `web/package.json` +
`package-lock.json`) — `tests/test_version_provenance.py`'s existing
regression guard (unchanged) still passes, and `mockingbird.__version__`/
the FastAPI `app.version`/`X-MockingBird-Api-Version` header/Doctor's own
`app_version` field all resolve live from installed package metadata, never
a second hardcoded literal. Confirmed independent of the Host↔Camera-Node
wire-protocol compatibility gate: `NODE_API_VERSION`/
`TRANSPORT_PROTOCOL_VERSION` are separate, unchanged fixed literals never
derived from the package version. Grepped the whole tree for stale `0.1.0`/
"pre-1.0" literals a version bump could leave inconsistent (the discipline
an earlier schema bump's own 14 hard-coded-literal miss already established
as necessary) — found and fixed one real hit outside the version files
themselves: `SECURITY.md`'s "MockingBird is pre-1.0 software" would have
become false the moment this bump landed (see §5, below). This is a
version-number choice, not a new versioning architecture; documented
inline in `pyproject.toml` and flagged here as trivially reversible (a
single-line change plus a rebuild) if the owner prefers a different number
before publishing.

## 2. Security / licensing / supply-chain hardening (governing brief §3)

Verified already-in-place, unchanged: `LICENSE` (MIT) and
`THIRD_PARTY_NOTICES.md` both exist, are copied into the bundle root by
`package_license`/`package_third_party_notices` (never optional — both
fail the whole build if their source is missing), and are mutually
consistent (confirmed by direct comparison: `THIRD_PARTY_NOTICES.md`'s own
two self-referential sentences about MockingBird's license match `LICENSE`
verbatim). `verify_no_nc_licensed_acoustic_model_redistribution` (BirdNET
weights never bundled) and `verify_no_bundled_ffmpeg_binary` (ffmpeg never
bundled) both already existed, unchanged, and still run unconditionally as
part of bundle assembly. The release build compiles from a `git archive`
snapshot of a verified-clean commit (`verify_clean_tracked_source`/
`export_clean_source_tree`), so no local secret, dev database, or
machine-specific file can enter the package regardless of what sits in a
working tree at build time — confirmed structurally, and re-confirmed by
inspecting the real assembled bundle after building (§4 of the
reconciliation extension, below).

**New this milestone — SBOM.** `generate_release_sbom`/`write_release_sbom`
produce a real, minimal CycloneDX 1.5 `sbom.json`, hand-built with the
standard library `email` parser reading every installed package's own real
`*.dist-info/METADATA` (name/version/license — preferring PEP 639
`License-Expression`, falling back to a `License ::` classifier, then the
legacy `License` field), plus the embedded CPython runtime and — only when
actually packaged — the two redistributed model artifacts with their
already-accepted SHA-256/license. No new build-time dependency. Written
next to `manifest.json`/`SHA256SUMS`, unconditional (every build gets one,
unlike the genuinely-optional model bundles), and now itself covered by
`SHA256SUMS`.

**New this milestone — optional release signing.** `sign_release_artifact`
produces a detached, ASCII-armored GPG signature over `SHA256SUMS`
(`SHA256SUMS.asc`) when a key id is explicitly configured
(`--sign-key-id`/`MOCKINGBIRD_RELEASE_SIGNING_KEY_ID`) — never invented,
never defaulted to an ambient keyring key. No key configured (every build
to date, including this milestone's own candidate) is the honest,
non-fatal default, recorded in `manifest.json`'s new `signing` field as
build-time *intent* (`{"requested": false, "key_id": null}`); a
*configured* key that fails to sign raises and fails the whole build,
never silently shipping unsigned while claiming otherwise. Real signing
requires a real owner-held key this milestone does not and must not
fabricate — see "Release-artifact SBOM and signing" in
`docs/local-product-packaging-design.md` for the complete owner-facing
procedure (generate a keypair, publish the public key/fingerprint
independently of the artifact, build with the key id, publish
`SHA256SUMS.asc`, keep the private key offline) prepared but not executed.
`verify_release_artifact.py` was generalized to check *every* `SHA256SUMS`
entry against its real file (previously only the always-present zip/
manifest pair — a real, if minor, docstring/implementation gap this
milestone's own new `sbom.json` entry exposed and closed) and to report
`SHA256SUMS.asc` presence informationally, deliberately never attempting
cryptographic verification itself (that would require assuming or
importing some public key, illegitimate for a generic verifier every
downstream consumer, not only the owner, runs).

13 new tests added (`tests/test_local_product_packaging.py`,
`tests/test_verify_release_artifact.py`), including one genuine,
disposable-keyring end-to-end GPG sign→verify proof (skipped, not failed,
on a host without `gpg`). `ruff check` clean on every changed file
(confirmed both individually and via `git stash` bisection against the
full-repo baseline — see §7, below, for why a full-repo `ruff check .`
itself is *not* clean, and why that is pre-existing, not introduced here).

## 3. Install / first-run / recovery polish (governing brief §4)

No release-blocking defect was found in this pass requiring a product-code
fix (see §7, defect triage, below) — the accepted end-to-end path (install →
first run → configure source → health → observation → review/correction →
shutdown → restart → recovery) was exercised via direct code inspection and
cross-referenced against the two most recent accepted milestones that
already validated most of it end to end on real hardware (*Release
Reliability & First-Run Recovery v1*, *Product Operations &
First-Observation Completion v1*) rather than re-proving already-accepted
behavior from scratch. The real, built-artifact walk of this exact path on
real native-Windows hardware is recorded in this report's reconciliation
extension, below (governing brief §8 requires it against the *built
artifact*, not the dev-deployment tooling this project's memory already
flags as a distinct, narrower thing from a genuine packaged-artifact
launch).

## 4. Documentation and support contract (governing brief §5)

A dedicated read-only investigation cross-checked `README.md`,
`docs/using-mockingbird.md`, `THIRD_PARTY_NOTICES.md`, `LICENSE`,
`SECURITY.md`, `CONTRIBUTING.md`, and `docs/local-product-packaging-design.md`
against the governing brief's full 21-item public-documentation checklist.
Real gaps found and fixed:

- **First-run setup steps were stale.** `docs/using-mockingbird.md` never
  mentioned the Account/Administrator-creation step *Local Identity,
  Multi-User & Organization Access v1* (2026-08-23) inserted between
  Welcome and Storage — a reader following the guide verbatim would hit an
  unexplained account-creation screen. Added as step 2, renumbered the rest.
- **Two brand-new controls were undocumented.** The Doctor UI page (new
  `GET /api/product/doctor` + `DoctorPage.tsx`, 2026-09-09) and the
  graceful "Shut Down MockingBird" control (new `POST
  /api/product/shutdown`, 2026-09-08) both shipped by the immediately-prior
  milestone with zero end-user documentation. Added both, and promoted
  graceful shutdown to the *preferred* stop method (it is the only one that
  avoids the "did not shut down cleanly last time" note on next start),
  cross-referenced from two places.
- **A dead cross-reference.** The BirdNET setup paragraph pointed a reader
  to `README.md` for setup instructions that do not exist there — the real
  `pip install "mockingbird[classifier-birdnet]"` command lives only in
  `THIRD_PARTY_NOTICES.md`. Fixed the pointer.
- **A mislabeled "normal-user" path.** `docs/camera-node-install-guide.md`
  called itself "the normal-user path" while its own Step 1 was "clone this
  repository and run a Python build script" — no pre-built Camera Node
  artifact has ever been published. Reframed Step 1 around downloading the
  artifact that ships alongside the main release (this milestone's own
  release-candidate build includes it as a labeled companion download — see
  §5 of the reconciliation extension), with building from source presented
  as the technical/developer alternative it actually is.
- **A leaked internal status note.** `README.md`'s "Active development
  checkout" section stated this exact sandbox's own absolute WSL path and a
  work-in-progress status log — not durable public documentation for a
  release-hardening pass. Deleted; its one substantive fact (MockingBird
  does not read or control a camera's own exposure/brightness settings) was
  relocated into `docs/using-mockingbird.md`'s "Add a camera" section,
  where a normal user can actually act on it.
- **A broken policy citation, and a claim about to become false.**
  `SECURITY.md` pointed security researchers at `docs/roadmap.md`'s
  "Security / release questions" — that heading only ever existed in the
  much larger, internal `docs/release-execution-state.md`, and even there
  is a short internal topic list, not a researcher-facing disclosure.
  Replaced with three concrete, source-verified current-posture
  disclosures (plain HTTP by default/private-network-only remote access;
  camera credentials stored locally but not encrypted at rest — confirmed
  by direct grep, no at-rest encryption code exists anywhere in the
  repository; Privacy Zones are trigger-level exclusion, not guaranteed
  pixel redaction). Also fixed `SECURITY.md`'s own "MockingBird is pre-1.0
  software" framing, which the version bump above would otherwise have
  made false the moment it landed — reworded to describe the real, durable
  policy (no tagged-release history yet, so only `main` plus the latest tag
  are supported) without asserting a version-number status.

Independently re-verified after the fact (not merely trusted from the
investigation): grepped the whole tree of public-facing docs for `0.1.0`/
"pre-1.0" residue post-bump — zero remaining hits anywhere in `README.md`,
`docs/using-mockingbird.md`, `THIRD_PARTY_NOTICES.md`, `LICENSE`,
`SECURITY.md`, `CONTRIBUTING.md`, `docs/local-product-packaging-design.md`,
or `docs/camera-node-install-guide.md`.

Confirmed already correct, no action needed: what MockingBird is; Windows/
Linux/macOS support statements (verbatim-matching the canonical Platform/
Runtime Portability vocabulary); the CUDA/GPU requirement and no-CPU-
fallback claim; Local Only/privacy/network-behavior description; install/
first-run/upgrade/rollback mechanics; backup/recovery; the two-level
uninstall procedure (already closed by *External Acceptance Entry
Readiness & Uninstall Closure v1*); known limitations/troubleshooting; no
instance anywhere of an overclaimed deferred/unsupported capability (native
mobile, broad multi-site, remote LTE/solar, unvalidated macOS, AMD GPU, CPU
visual-detector fallback).

`docs/local-product-packaging-design.md` gained a new dated section
("Release-artifact SBOM and signing") documenting the §2 additions above,
following this file's own established convention of appending a dated
section per milestone rather than rewriting prior content, plus a matching
"Files allowed" entry.

## 5. Hardware / compatibility claims (governing brief §6)

No new hardware-validation campaign launched. Existing accepted evidence
(Platform / Runtime Portability & Support Truth Closure v1's five-term
vocabulary) is unchanged and was not re-litigated. This milestone's own
real-hardware work (native-Windows artifact validation, a bounded reference
-Pi health check) is scoped narrowly to validating the *packaging output*
this milestone changed, not a fresh general compatibility sweep — recorded
in the reconciliation extension, below. Every deferred/unsupported item
named in the governing brief (native mobile, broad multi-site, remote LTE/
solar, Apple Silicon beyond the existing accepted-evidence precedent, AMD
GPU, CPU visual-detector fallback, unvalidated macOS) remains exactly as
deferred/unsupported as before this milestone; none was touched, tested, or
promoted.

## 6. Known defect triage (governing brief §7)

A dedicated read-only investigation compiled every currently-disclosed,
not-yet-fixed defect/gap/reservation named across every accepted milestone
report since 2026-08-24 — 42 distinct items, cross-checked for
staleness (two items the investigation flagged for confirmation — the
Doctor Storage false-`FAIL`, and "no stop method yields a clean shutdown" —
were independently confirmed **already fixed** by the immediately-prior two
milestones, not carried forward as open; a stale memory note claiming "no
login rate-limiting" was independently checked against current source and
found **already closed** by *Login Rate-Limiting & Authentication Abuse
Resistance v1*, not carried forward either).

**RELEASE BLOCKER: none found.** **FIX NOW: none taken this pass.** Every
remaining item classifies as ACCEPTED KNOWN LIMITATION (a deliberate,
already-disclosed trade-off — the large majority trace to Gate A's own
already-accepted recall/latency budget, Camera Node's two disclosed
`rollback()` reservations, or similarly already-governed decisions),
DEFERRED (real, recorded, genuinely out of this milestone's own bounded
scope — future product/UX opportunities, tooling-only gaps, or a standing
legal question with no engineering action available), or TEST DEBT
(environment-sensitive flakes, independently re-confirmed pre-existing this
session — see §7 below).

One candidate — `mockingbird_node/config.py`'s `pairing_state_path` still
carrying the same `Path.home()`-fallback shape already fixed for
`transport_spool_dir`/`transport_credential_state_path` in the identical
file — was investigated directly (not merely cited) because it has an
already-proven fix pattern sitting a few lines away. Left unfixed
deliberately: the real, supported install path
(`scripts/install_camera_node.py`) always sets the corresponding
environment variable explicitly, so this fallback is dead code on every
real device; its own originating report already disclosed it by name as
"a latent structural risk... not fixed under this milestone's bounded
scope," and `pairing_state_path` (unlike the two paths already fixed)
*is* the anchor those two derive from, so the identical fix cannot simply
be copied — it would require designing and validating a new bottom-of-
chain default this milestone did not set out to invent, against a
real-hardware-validated component, for a scenario the supported path never
exercises. See `docs/final-release-hardening-launch-readiness-v1-defect-triage.md`
for the complete classified list of all 42 items.

## 7. Release-candidate validation (governing brief §8)

**Tier 1/2.** `tests/test_version_provenance.py` (version bump); the full
`tests/test_local_product_packaging.py` + `tests/test_verify_release_artifact.py`
(107 tests, all passing, `-m "not slow"`); a broad adjacent sweep
(`test_camera_node_packaging.py`, `test_doctor_cli.py`,
`test_deploy_windows_dev.py`, `test_install_camera_node.py`,
`test_doctor.py`, `test_node_compatibility.py`,
`test_camera_node_boot_identity.py`, `test_observation_camera_node_live.py`,
`test_windows_launcher_instance_identity.py`,
`test_field_acceptance_instance_lifecycle.py`, `test_camtrap_dp.py`) — 621
passed, 4 deselected (`slow`), 0 failed. Frontend `tsc --noEmit && vite
build` clean.

**`ruff check` on every file this milestone changed: clean.** A full-repo
`ruff check .` (never wired into Fast/Core/Full/CI — confirmed by direct
grep, no `ruff` invocation exists in any of them) surfaces 163 findings;
independently confirmed via `git stash` bisection that this is **100%
pre-existing** — identical count with this milestone's changes stashed out,
zero of the 163 in any file this milestone touched. Every prior "ruff
clean" claim in this project's history was necessarily scoped to the files
that milestone touched, not a full-repo sweep — this is the first time that
full-repo number has been directly measured and disclosed; it is TEST DEBT,
not a regression, and not fixed here (out of this milestone's own bounded
scope — see "Do not use this section as permission for a whole-repository
audit").

**Tier 3 — full Core, run once against this exact commit's tree** (the
final release-hardening milestone; packaging/runtime/versioning changes are
cross-cutting): **5995 passed / 4 failed / 4 skipped / 35 deselected / 11
xfailed, 2729s (45m29s).** All 4 failures independently re-confirmed this
session via direct `git stash` bisection against the unmodified baseline —
byte-identical to the long-documented, pre-existing, environment-sensitive
flakes recorded in `docs/release-execution-state.md` §14
(`test_place_biodiversity_summary_repository.py`'s pair and
`test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields`
reproduced the identical assertion failure standalone against the stashed
baseline; `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success`
passed standalone against the same stashed baseline, matching its own
already-documented "load-induced, not reproducible in isolation" nature) —
**zero failures attributable to this milestone.** No schema change (`v59`,
unchanged); no product/detector/tracker/identification-policy code changed
anywhere in this milestone.

**Built-artifact / native-Windows-hardware / Pi validation:** recorded in
this report's reconciliation extension, added after this commit (the
release build requires a clean, already-committed source tree — see §1's
opening note).
