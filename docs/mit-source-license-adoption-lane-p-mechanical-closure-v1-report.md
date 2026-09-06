# MIT Source License Adoption & Lane P Mechanical Closure v1: report

Bounded feature-freeze release-housekeeping milestone. No product capability
added. Performs exactly the mechanical follow-through Global Remaining
Product-Development & Release-Queue Reconciliation v1 named and deliberately
did not perform.

## Starting state

- **Branch:** `main`.
- **Starting HEAD:** `9eaa6e0` -- exact match to the governing brief's
  expected state (the reconciliation commit for Global Remaining
  Product-Development & Release-Queue Reconciliation v1).
- **Implementation HEAD:** `bdfa35f`.
- **Schema:** `v58`, unchanged (no model/migration code touched).
- **Current phase:** `FEATURE FREEZE -- EVIDENCE, RELEASE READINESS &
  HOUSEKEEPING`, confirmed unchanged and not touched by this milestone.
- **Lane R:** confirmed unchanged -- `OPEN -- RELEASE-CRITICAL -- TRUE
  LATENCY TAIL EVIDENCE REMAINS`, waiting for a genuine daylight window; not
  touched, not scheduled by this milestone.
- **Current authorization (starting):** `NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED`.
- **Worktree safety:** confirmed before starting and re-confirmed after --
  the seven preserved untracked files (`docs/wildlife-detector-training-
  contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) are the entire `git status
  --porcelain` output before this milestone's own changes, byte-untouched
  throughout, and remain the entire non-milestone `git status --porcelain`
  output after. No `.git/index.lock` or other lock file present. No active
  writer found. Not pushed.

No discrepancy between the governing brief's expected starting state and
repository evidence was found.

## Owner decision

**MockingBird's own source code SHALL USE THE MIT LICENSE** -- an
authoritative owner decision supplied directly by this milestone's own
governing brief, not re-derived or re-litigated here. This decision was
already recorded as resolved by the immediately-prior Global Remaining
Product-Development & Release-Queue Reconciliation v1
(`global-remaining-product-development-release-queue-reconciliation-v1-report.md`,
"Owner MIT decision": "the project owner has selected MIT... Recorded here
as fact, not reopened"), itself following Release Licensing, Distribution &
Third-Party Legal Closure v1's own complete MIT-vs-Apache-2.0-vs-copyleft
decision packet. This milestone performs only the mechanical adoption that
decision left pending -- MIT vs. Apache-2.0 vs. copyleft was not
reconsidered.

## Copyright-holder evidence

The brief requires determining the copyright line from authoritative
repository evidence, not guessing, and falling back to "the narrowest
legally/factually supportable formulation already used by the project" if
the repository does not establish a defensible copyright-holder string on
its own.

**Evidence gathered directly this session:**

- `git log --format='%an <%ae>' | sort -u` returns exactly one identity
  across all 633 commits: `zkelder <zachkelder@gmail.com>`.
- `git remote -v`: `https://github.com/zkelder/mockingbird.git` -- a GitHub
  username, not a legal name or registered organization.
- No `[project.authors]`/`[project.maintainers]` table exists in
  `pyproject.toml` (confirmed by reading the file in full).
- No "Copyright" line anywhere in the repository asserts a holder for
  MockingBird's *own* code (a repository-wide grep found only third-party
  copyright lines -- Microsoft Corporation for MDv5a, and BioCLIP-2's model
  card, both already correctly attributed in `THIRD_PARTY_NOTICES.md`).
- `THIRD_PARTY_NOTICES.md`'s own opening sentence, already present in the
  repository before this milestone: **"MockingBird is written by its own
  contributors."**

**Disposition.** The repository does not establish a defensible individual
or organizational copyright-holder string on its own -- a single git
author's email-derived name is not a legal name, and no company/
organization exists anywhere in the repository's own text. Per the brief's
own explicit fallback rule, this milestone uses the narrowest formulation
*already used by the project*: **`MockingBird contributors`**, taken
verbatim in substance from `THIRD_PARTY_NOTICES.md`'s own pre-existing
self-description. This is a well-established, defensible open-source
convention (`Copyright (c) <year> <project> contributors`) that requires no
invented legal name and no invented organization.

**Year.** `git log --reverse --format='%ad' --date=format:'%Y-%m-%d' | head
-1` returns `2026-06-30`; the latest commit is `2026-09-05`. The entire
repository history falls inside calendar year 2026, so a single year is
factually precise -- `2026`, not a range.

**Copyright line used:** `Copyright (c) 2026 MockingBird contributors`.

## LICENSE adoption

Added `LICENSE` at the repository root: the standard, unaltered MIT license
text (verified against the identical canonical text this repository already
reproduces for MDv5a in `THIRD_PARTY_NOTICES.md`, confirming one consistent
MIT text throughout this repository) with the copyright line above. No
third-party license text was altered.

## Package metadata

**Before this milestone:** `pyproject.toml` had no `license`/`license-files`
field; `web/package.json` had no `license` field.

**Change.** Added modern, SPDX-compatible metadata rather than the legacy
table/classifier forms, per the brief's own preference:

```toml
[project]
license = "MIT"
license-files = ["LICENSE"]
```

**This required raising the `hatchling` build-system floor, empirically
verified, not assumed.** `pyproject.toml`'s pre-existing floor was
`hatchling>=1.24`. Built a minimal PEP 639 fixture project against a matrix
of real hatchling versions (`uv pip install "hatchling==<version>"` into a
disposable venv, then `python -m hatchling build`):

| hatchling | Result |
| --- | --- |
| 1.24.2, 1.25.0 | **Fails outright**: `TypeError: Field 'project.license-files' must be a table` -- these versions predate PEP 639's array form entirely. |
| 1.26.0, 1.26.3 | Builds; copies `LICENSE` into the wheel's `dist-info/licenses/`, but `METADATA` is `Metadata-Version: 2.3` with **no** `License-Expression`/`License-File` header -- a silent, incomplete adoption. |
| 1.27.0, 1.28.0, 1.29.0, 1.32.0 (latest, what `>=1.24` alone resolves to today) | Builds; `METADATA` is `Metadata-Version: 2.4` with both `License-Expression: MIT` and `License-File: LICENSE` present. |

Raised the floor to `hatchling>=1.27` -- the exact minimum confirmed to
produce complete, correct metadata. This is not general dependency
modernization; it is a floor correction required for the new fields to work
at all across the versions the existing constraint would otherwise permit.

`web/package.json` gained a matching `"license": "MIT"` field for
consistency (the brief's own words, echoing the immediately-prior
reconciliation's own "and, for consistency, `web/package.json`" framing).
The frontend is `"private": true` and is never published to npm, so this is
a truth/consistency fix, not a publishing-behavior change.

No classifier was added. PEP 639 metadata (`License-Expression`) and the
legacy `License ::` trove classifiers are alternative, not complementary,
ways of declaring the same fact -- adding both would be redundant with the
modern field this milestone adds, so none was added. `pyproject.toml`
carried no `classifiers` key at all before this milestone (confirmed by
reading the file in full), so there was no obsolete classifier to correct.

## Distribution inclusion

**Python wheel/sdist -- proven with a real build of this exact repository,
not merely inspected:**

```
$ .venv/bin/python -m pip wheel . --no-deps -w <scratch-dir>
Successfully built mockingbird
```

This is the identical command `scripts/build_local_product.py`'s own
`build_wheel()` runs. Unzipping the real, resulting
`mockingbird-0.1.0-py3-none-any.whl` and inspecting it directly:

```
Metadata-Version: 2.5
Name: mockingbird
License-Expression: MIT
License-File: LICENSE
...
```

`mockingbird-0.1.0.dist-info/licenses/LICENSE` is present and **byte-
identical** to the repository's own root `LICENSE` file (`diff` confirmed
no output). No repository files were modified or left behind by this
build -- it was directed entirely into a scratch output directory outside
the repository, and `git status --porcelain` was re-confirmed clean
(modulo this milestone's own tracked changes and the seven preserved
files) immediately after.

**Official Windows bundle.** `scripts/build_local_product.py`'s
`assemble_windows_bundle` installs the built wheel via `pip install
--target site_packages --no-deps ... wheel_path`, so the proof above means
`mockingbird-0.1.0.dist-info/licenses/LICENSE` automatically reaches
`python/site-packages/` inside every official bundle already, with no code
change required -- the identical "every dependency's own license already
travels automatically via its own `dist-info/`" mechanism
`THIRD_PARTY_NOTICES.md` already documents for ordinary pip dependencies.

That automatic inclusion is not sufficient by itself: it lands buried at
`python/site-packages/mockingbird-0.1.0.dist-info/licenses/LICENSE`, not
somewhere a normal end user unpacking the release `.zip` and looking at the
top-level folder would ever find it -- the same gap
`THIRD_PARTY_NOTICES.md` itself was created to close for the MDv5a/BioCLIP-2
model licenses, which otherwise "carried zero accompanying license/notice
text at all" from an end user's vantage point. Made the smallest correct
packaging change mirroring that exact precedent: a new `package_license`
function in `scripts/build_local_product.py`, structurally identical to the
existing `package_third_party_notices` (never optional, raises
`LocalProductBuildError` -- failing the whole release build, never a
warning -- if the source `LICENSE` cannot be found), called from
`assemble_windows_bundle` right beside `package_third_party_notices`. Every
official Windows bundle's root folder now contains `LICENSE` visibly
alongside `THIRD_PARTY_NOTICES.md`, `README-FIRST.txt`, and `Start
MockingBird.vbs`.

**Source repository.** `LICENSE` is a normal tracked file at the repository
root, reachable by anyone who clones or downloads the repository, the same
as `SECURITY.md`/`CONTRIBUTING.md`/`THIRD_PARTY_NOTICES.md`.

**Camera Node artifact** (`scripts/build_camera_node_artifact.py`): grepped
directly -- contains no `THIRD_PARTY_NOTICES`/`LICENSE` reference at all, in
either direction, before or after this milestone. The prior Release
Licensing, Distribution & Third-Party Legal Closure v1 -- which had full
authority over "official packaging" -- deliberately did not add
`THIRD_PARTY_NOTICES.md` to this artifact either. Treated as established,
consistent precedent and left untouched, matching this milestone's own
explicit instruction not to touch Camera Node behavior.

**`scripts/verify_release_artifact.py`** (the independent post-build
checksum verifier): read in full. It checks manifest-schema completeness
and `SHA256SUMS`/`zip_sha256` byte parity against the assembled `.zip`
artifact and `manifest.json` only -- it has never enumerated individual
bundle-content files (it did not gain a `THIRD_PARTY_NOTICES.md` check
either, when that file was introduced), so no change here is warranted or
consistent with precedent.

## README correction

`README.md`'s "License" section previously stated the decision "has not yet
been finalized" and that "no `LICENSE` file exists in this repository yet."
Both are now false and have been corrected:

> MockingBird's own source code is licensed under the [MIT License](LICENSE).
>
> This covers MockingBird's own code only. Third-party components
> MockingBird redistributes or depends on -- including the bundled MDv5a
> and BioCLIP-2 model weights, and the optional BirdNET bird-sound
> identification feature MockingBird deliberately does **not** bundle --
> are licensed under their own separate terms, not necessarily MIT, and
> remain governed by those terms. See
> [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete account
> of what is bundled, what is not, and under what license.

This states MIT plainly, links directly to `LICENSE`, and explicitly does
**not** imply third-party dependencies or bundled models are all MIT --
`THIRD_PARTY_NOTICES.md` remains the named authority for that.

## Third-party boundary

No third-party fact was changed. Verified directly, before and after this
milestone's edits, that every one of the following is byte-for-byte
unchanged in `THIRD_PARTY_NOTICES.md`: MDv5a's MIT license text and
Microsoft Corporation copyright provenance; BioCLIP-2's MIT license-card
citation; the ffmpeg "deliberately NOT bundled" section and
`verify_no_bundled_ffmpeg_binary` reference; the BirdNET/birdnetlib section
(Apache-2.0 wrapper code, CC BY-NC-SA 4.0 model weights, Cornell K. Lisa
Yang Center for Conservation Bioacoustics attribution, and the
`verify_no_nc_licensed_acoustic_model_redistribution` reference); the core
direct-dependency license table; the ONNX Runtime/CUDA and BioCLIP/OpenCLIP
runtime-closure disclosures. The only two sentences touched in that file are
its own self-referential notes about *MockingBird's own* license status
(the opening paragraph and the "Where to look for anything not covered
here" bullet), which were factually stale after this milestone ("a
separate, still-open question" / "pending an explicit owner decision") and
are now corrected to state MIT and point at `LICENSE`. MIT-licensing
MockingBird's own code does not relicense, and was never asserted to
relicense, any third-party code or model.

Both pre-existing build-time guards were re-confirmed present and untouched
by reading `scripts/build_local_product.py` directly:
`verify_no_bundled_ffmpeg_binary` and
`verify_no_nc_licensed_acoustic_model_redistribution`, both still called
unconditionally inside `assemble_windows_bundle`.

## BirdNET distinction

Per the brief's own explicit instruction, this milestone did not attempt to
resolve BirdNET's open commercial-adjacent legal question. The scheduler
distinction is preserved exactly:

- **MockingBird source license: RESOLVED -- MIT**, now mechanically
  adopted (this milestone).
- **BirdNET optional model commercial-adjacent posture: OPEN LEGAL REVIEW
  -- NO ENGINEERING ACTION CURRENTLY AVAILABLE.** Unchanged, un-reopened,
  and not treated as a blocker for the entire visual-core public launch --
  governing doctrine (`release-execution-state.md` §2, and the immediately-
  prior reconciliation's own "BirdNET legal posture" section) already
  establishes this as **B+D**: it blocks only commercial-adjacent use of
  the optional acoustic feature, not all public launch, and remains a
  standing legal-review item with no available engineering action.

## Validation

**Tier 1 (focused packaging/license tests):**
`tests/test_local_product_packaging.py -m "not slow"` -- **81 passed, 0
failed**, 4 pre-existing `slow`-marked tests correctly deselected
(unrelated real-network/real-GPU-dependency tests, unmodified). This
includes 7 new tests (`test_package_license_copies_the_real_repository_
file`, `test_package_license_fails_the_build_when_source_is_missing`,
`test_pyproject_declares_mit_license_metadata`,
`test_web_package_json_declares_mit_license`,
`test_license_file_exists_with_correct_mit_text_and_copyright`,
`test_readme_states_mit_license_and_points_to_license_file`,
`test_third_party_notices_no_longer_calls_the_source_license_undecided`)
plus 2 new assertions added to the existing
`test_assemble_windows_bundle_produces_a_python_and_pip_free_user_
experience` bundle-assembly smoke test (LICENSE reaches the bundle root,
byte-identical to the repository's own file). Added to the existing
canonical packaging test file per the brief's own instruction, not a new
parallel test framework.

**Adjacent sanity check:** `tests/test_version_provenance.py` -- 4 passed,
confirming the neighboring version-provenance metadata is unaffected.

**`ruff check`:** clean (zero findings) on both changed Python files
(`scripts/build_local_product.py`, `tests/test_local_product_packaging.py`).

**Package build metadata inspection / release-bundle inclusion proof:** see
"Distribution inclusion," above -- a real `pip wheel .` build of this exact
repository, not a mock or a fixture project, plus direct inspection of the
resulting wheel's `METADATA` and `dist-info/licenses/LICENSE`.

**Schema:** unchanged, `v58`. **Tier 3 (Core):** not run. Every changed
file (`LICENSE`, `pyproject.toml`, `web/package.json`,
`scripts/build_local_product.py`, `tests/test_local_product_packaging.py`,
`README.md`, `THIRD_PARTY_NOTICES.md`, `docs/roadmap.md`) is packaging or
documentation with zero importers anywhere in `src/mockingbird/` -- the
identical reasoning this codebase has already applied to every prior
packaging-tooling-only milestone (Camera Node Upgrade & Compatibility
Recovery v1, `deploy_windows_dev.py` work, and Release Licensing,
Distribution & Third-Party Legal Closure v1 itself). No detector, BioCLIP,
BirdNET runtime, Visit semantics, admission, evidence, review/truth,
frontend product capability, database/schema, or Camera Node behavior code
was touched.

**Worktree safety, re-confirmed at close:** the seven preserved untracked
files remain the entire non-milestone `git status --porcelain` output,
byte-untouched.

## Lane P decision

**CLOSED -- RELEASE-CRITICAL LICENSING/DISTRIBUTION REQUIREMENTS
COMPLETE.**

All three artifacts the immediately-prior reconciliation named as the exact
remaining mechanical gap are now true: a real `LICENSE` file exists at the
repository root with correct MIT text and a defensible copyright line;
`pyproject.toml`/`web/package.json` carry correct, verified-working MIT
license metadata; `README.md`'s "License" section states the resolved
decision instead of "not yet finalized." Distribution inclusion is proven,
not assumed, for the Python wheel/sdist, the official Windows bundle, and
the source repository itself. `THIRD_PARTY_NOTICES.md` remains accurate and
untouched in every third-party fact, with its own two self-referential
sentences corrected to match. Every focused packaging/license test passes.

The BirdNET commercial-adjacent legal posture is a separate, standing
legal-review item (§2 of `release-execution-state.md`), tracked
independently of Lane P's own release-engineering/distribution scope since
before this milestone, with no available engineering action -- per the
brief's own explicit instruction, this does not by itself keep Lane P's
mechanical license/distribution work open.

**Exact remaining Lane P blocker: none.**

## Remaining release queue

Unchanged by this milestone, confirmed still accurate:

- **Lane R (Complete Field Acceptance):** `OPEN -- RELEASE-CRITICAL --
  TRUE LATENCY TAIL EVIDENCE REMAINS`, waiting for a genuine daylight
  window. Not scheduled by this milestone.
- **BirdNET commercial-adjacent legal posture:** `OPEN LEGAL REVIEW -- NO
  ENGINEERING ACTION CURRENTLY AVAILABLE`, a standing item for the owner,
  not engineering.
- **Public-repo hygiene beyond `SECURITY.md`/`CONTRIBUTING.md`/
  `THIRD_PARTY_NOTICES.md`** (README/site polish, brand/trademark review):
  real, still open, explicitly non-blocking, and deliberately not touched
  by this milestone's own feature-freeze-discipline boundary.
- **External Pre-Release Acceptance:** not yet authorized; concretely
  blocked on Lane R closing and (as of this milestone) no longer blocked on
  Lane P.
- **Final Release Hardening:** not yet authorized; correctly sequenced
  after External Pre-Release Acceptance.

This milestone does not authorize any of the above, select a next
development milestone, or reopen any deferred product lane.

## Decision

**A.** All three named mechanical artifacts (LICENSE file, package
metadata, README truth) are now correct, verified working by a real wheel
build rather than merely inspected, and reach every official deliverable
this repository actually produces (wheel/sdist, Windows bundle, source
repository) with proof, not assumption. No third-party fact was altered.
Focused tests pass; `ruff` is clean; no schema change; no Core run (correct
per the change's own packaging/documentation-only shape). Lane P closes at
release-critical completion. Authorization returns to `NONE -- GLOBAL
PRODUCT-ROADMAP RECONCILIATION REQUIRED` for the next external (ChatGPT)
acceptance review to act on.
