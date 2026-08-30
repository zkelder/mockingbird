# Release Licensing, Distribution & Third-Party Legal Closure v1: report

Pre-release decision / release-blocking governance milestone. Resolves the
remaining legal/distribution questions determining what MockingBird can
truthfully ship in its one public launch. Not a generic dependency-license
audit, not product doctrine, not Final Release Hardening.

## Starting state

- **Branch:** `main`.
- **Starting HEAD:** `42de65e` (the reconciliation commit accepting
  Platform / Runtime Portability & Support Truth Closure v1).
- **Implementation HEAD:** `e3c293f`.
- **Schema:** `v58`, unchanged by this milestone (no model/migration code
  touched).
- **Governing release doctrine consulted:**
  [docs/release-execution-state.md](release-execution-state.md) (current
  accepted state, §2 acoustic release state, §3 current authorized
  milestone, §6 Lane P and the "Four release-shape categories" index),
  [docs/product-doctrine.md](product-doctrine.md) (read in full; nothing in
  it bears on licensing/distribution mechanics), and
  [docs/roadmap.md](roadmap.md) (Gate F "OSS / Security / Compatibility /
  Packaging Closure," "Release scope discipline," "Scope-reopening rule").

### Hard sequencing guard

Per this milestone's own governing brief, the complete remaining
release-critical/pre-release queue was inspected before starting (§6's
lettered lanes A-S plus the "Four release-shape categories" index):

- **Lane R (Complete Field Acceptance)** -- `NOT DONE -- RELEASE-CRITICAL`,
  but blocked on a representative daylight field session, an external
  condition (weather/time-of-day) this milestone cannot supply. Confirmed
  still correctly gated and unrelated to licensing.
- **Lane G (Camera / Source Experience)** -- `PARTIAL, MATERIALLY CLOSED`,
  classification C; its one remaining item (ongoing-monitoring
  failure-code collapse for non-Camera-Node providers) is bounded,
  disclosed, and not flagged as blocking -- not a higher-priority
  independent release-critical item.
- **Lane L (Appliance / Update / Recovery)** -- `MATERIALLY CLOSED`; its
  disclosed remaining items (`rollback()` not restoring an already-changed
  systemd unit template, a narrower residual crash-window gap) are
  real but not flagged as needing immediate action.
- **Lanes M, N, O, Q** -- all `CLOSED`.
- **Lane P (Release Engineering Foundation / Distribution)** --
  `SUBSTANTIALLY CLOSED, two items deliberately left open --
  RELEASE-CRITICAL`: the codebase `LICENSE` decision and full ffmpeg
  distribution licensing, plus the still-open BirdNET commercial-adjacent
  legal posture named in §2. Both items require no live field session, no
  daylight conditions, no GPU/camera hardware, and no external dependency
  this session lacks.
- **Lane K (Ecosystem / Provider Integrations)** -- `OPEN DECISION`, also a
  "pre-release decision" per the categories index, but a distinct product-
  scope question (which adapters to build) unrelated to licensing/
  distribution and out of this milestone's named scope (A-F).

No higher-priority independent release-critical milestone was found that
could proceed instead of this one while Lane R stays externally blocked.
**The sequencing premise held; this milestone proceeded.**

### Worktree safety

Confirmed before starting and re-confirmed after: the seven preserved
untracked files (`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`) remained untouched throughout --
never staged, edited, or cleaned. No `uv.lock` or other new residue was
present at the start. No active writer was found (a solo session; `git
status` showed only those seven files plus this milestone's own eventual
changes). Not pushed.

## MockingBird code license

**Current state (repository fact):** no `LICENSE` file exists at the
repository root. `pyproject.toml`'s `[project]` table declares no
`license`/`license-files` field. `README.md` and `CONTRIBUTING.md`
contained zero license-decision text before this milestone (README.md's
one pre-existing "license" mention was about the *BioCLIP-2 model*, not
MockingBird's own code). No source header anywhere declares a license. No
conflicting historical statement exists anywhere in `docs/`.

**Authoritative evidence already in the repository:** `docs/roadmap.md`
Gate F: *"no `LICENSE` or `SECURITY.md` file exists in the repository
today -- a real, open Gate F item"* (this file's own `SECURITY.md` half is
now stale -- Release Engineering Foundation v1, 2026-08-25, already added
`SECURITY.md`; the `LICENSE` half remains accurate).
`docs/release-execution-state.md` Lane P: *"Deliberately still open, not
silently dropped: **`LICENSE`** (a business/legal decision ... outside a
bounded engineering milestone's authority to resolve unilaterally)."*
Both are explicit, and both agree: the roadmap does **not** select a
license; it explicitly defers the decision to the project owner.

**Disposition:** per this milestone's own governing bar (§16), this
repository's own evidence requires an owner decision rather than
authorizing this milestone to self-select one. No `LICENSE` file was
added. The decision packet below is the complete, actionable substitute.

### Decision packet

**Recommended: MIT.**

| Option | What it means for MockingBird | Dependency compatibility | Practical consequence |
| --- | --- | --- | --- |
| **MIT** (recommended) | Maximum permissiveness -- anyone may use, modify, and redistribute, including commercially, with attribution preserved. | Compatible with every dependency this project actually ships: every core/optional Python dependency confirmed in this milestone's own third-party matrix (below) is MIT/BSD/Apache-2.0/ISC; the frontend's only two production dependencies (React, React DOM) are MIT. No copyleft dependency exists anywhere in the current dependency closure that MIT would conflict with. | Simplest possible position for contributors and downstream users; matches the license already used by the two model assets MockingBird itself redistributes (MDv5a, BioCLIP-2), so the whole stack reads as one consistent permissive story rather than mixing regimes. Does not, by itself, prevent a future commercial/hosted offering by MockingBird itself or by a third party -- if that is a concern, see Apache-2.0 or a dual-license path below. |
| Apache-2.0 | Similarly permissive, plus an explicit patent grant and contribution-attribution structure. | Equally compatible with the current dependency closure (several core dependencies -- `python-multipart`, `opencv-python-headless`, `astral` -- are already Apache-2.0 themselves). | A somewhat more contributor-formal choice (an explicit patent grant matters more for a project with meaningful patent-eligible technique, less obviously so for MockingBird's own code, which mostly composes existing ML models/protocols rather than claiming novel patentable methods). Slightly longer license text than MIT; otherwise a close sibling choice. |
| AGPL-3.0 (or another copyleft license) | Requires anyone who runs a modified version as a network service to release their modifications. | **Would not itself conflict** with the current dependency closure (permissive dependencies can be included in a copyleft work), but cuts against this project's own stated identity: `product-doctrine.md`'s "Deployment and organization doctrine" explicitly supports an "Organization/Research" deployment profile (local server, multiple users) that a copyleft network-use clause would burden without a clear matching product reason, and the roadmap's own "professional and research positioning" anticipates adoption by conservation/research organizations who may prefer a permissive license for their own downstream tooling. | Would meaningfully narrow adoption relative to MIT/Apache-2.0 for a project whose own doctrine already emphasizes broad ecosystem/professional adoption over restricting downstream commercial use of the *code* (the actual commercial-sensitivity concern in this codebase is the *BirdNET model weights*, already handled separately and correctly by never redistributing them -- not something a copyleft *code* license would additionally protect). |

**Why MIT over Apache-2.0 specifically:** both are compatible with
everything MockingBird ships; MIT is chosen as the recommendation because
it already matches the license of both production-redistributed model
assets (MDv5a, BioCLIP-2), keeping the whole distributed artifact's
licensing story to one well-understood regime instead of two adjacent-but-
different ones, and it is the more familiar default for a local-first,
hobbyist-to-professional home/research tool with no known present need for
Apache's patent-grant machinery.

**Exact owner decision required:** *"Should MockingBird's own source code
be MIT-licensed (recommended), Apache-2.0-licensed, or something else? Say
the word and a `LICENSE` file is added in one commit."* No other
engineering ambiguity blocks this -- the decision packet above is
complete, and either recommended option is immediately implementable
without further archaeology.

## Third-party distribution matrix

| Component | License | Bundled in official packaging? | Redistribution status | Required action/notice |
| --- | --- | --- | --- | --- |
| **FFmpeg** | Depends on the user's own separately-obtained build (commonly LGPL or GPL, depending on which optional codecs that build enables) | **No.** Confirmed by tracing every invocation site (`mockingbird/playback/rtsp_bridge.py`, `local_camera_bridge.py`, `windows_camera_bridge.py`: all resolve via `shutil.which("ffmpeg")`/a user-configurable path, never a bundled path) and every packaging/build script (`build_local_product.py`, `build_camera_node_artifact.py`, `install_camera_node.py`, `deploy_windows_dev.py`: zero references to `ffmpeg` in any of them, confirmed by direct grep). | Not redistributed; invoked as a separate subprocess against a copy the user's own OS provides. No linking, no copying, no shipping. | Already honestly documented (`docs/using-mockingbird.md`, "Add a camera": *"additionally need a free program called **ffmpeg** installed on this computer ... MockingBird says so plainly ... and links to where to get it"*). New this milestone: `verify_no_bundled_ffmpeg_binary` (an active build-time guard, `scripts/build_local_product.py`) and `THIRD_PARTY_NOTICES.md`'s own "Deliberately NOT bundled" section make this posture durable and explicit rather than merely accidental. |
| **birdnetlib** (wrapper code) | Apache-2.0 | No (never installed by official packaging; `classifier-birdnet` is a separate, user-installed optional extra) | Not MockingBird's to redistribute at all today | Disclosed in `THIRD_PARTY_NOTICES.md` for transparency about the optional path; no obligation arises since it is never shipped. |
| **BirdNET-Analyzer model weights** (`GLOBAL_6K_V2.4`, bundled as package data *inside* the `birdnetlib` wheel) | CC BY-NC-SA 4.0 (NonCommercial), Cornell K. Lisa Yang Center for Conservation Bioacoustics | **No.** `verify_no_nc_licensed_acoustic_model_redistribution` (pre-existing, re-verified working this milestone: read in full, its call site in `assemble_windows_bundle` confirmed live, both its passing and failing test cases confirmed passing) fails the whole release build outright if `birdnetlib` (and therefore this model) is ever found in the assembled `site_packages`. | User obtains it themselves via `pip install "mockingbird[classifier-birdnet]"`, directly from PyPI, under upstream's own terms -- never through MockingBird's redistribution. | Already correctly enforced (pre-existing). Newly, honestly documented for the *end user* for the first time this milestone (`docs/using-mockingbird.md`'s new "Bird-sound identification (optional)" section; `THIRD_PARTY_NOTICES.md`) -- previously this fact existed only in internal contract docs and code comments, invisible to an actual product user. |
| **MDv5a** (`md-v5a`, MegaDetector v5.0) | MIT (Microsoft Corporation copyright for pre-2023-04-28 releases, which covers this one; MegaDetector now maintained independently at `github.com/agentmorris/MegaDetector`) | **Yes**, when `--model-bundle-source` supplies it (the default for an official release build) | Permitted -- MIT allows redistribution with notice preservation | Fixed this milestone: full license text + correct copyright provenance now ships in every official bundle via `THIRD_PARTY_NOTICES.md` (previously: copied with zero accompanying notice text at all -- see "Package-content proof," below). |
| **BioCLIP-2** | MIT, per its official model card (`huggingface.co/imageomics/bioclip-2`, version 1.0.0) | **Yes**, when `--bioclip-bundle-source` supplies it (the default for an official release build) | Permitted -- MIT allows redistribution | Fixed this milestone: license text ships in `THIRD_PARTY_NOTICES.md` in every official bundle (previously: copied with zero accompanying notice text). |
| Core direct Python dependencies (`anyio`, `fastapi`, `Pillow`, `pydantic`, `python-multipart`, `SQLAlchemy`, `opencv-python-headless`, `uvicorn`, `astral`) | MIT / MIT-CMU / Apache-2.0 / BSD-3-Clause (verified directly against each package's own installed metadata in this repository's `.venv`, not assumed -- see per-package table in `THIRD_PARTY_NOTICES.md`) | Yes (ordinary pip dependencies of the shipped wheel) | Permitted; each ships its own `LICENSE`/`NOTICE` inside its own `<package>.dist-info/`, structurally preserved by the `pip install --target` packaging mechanism itself | Summarized in `THIRD_PARTY_NOTICES.md`; full text already travels per-package automatically, needing no further action. |
| Frontend production dependencies (`react`, `react-dom`) | MIT | Yes (compiled into the shipped JS bundle) | Permitted | Summarized in `THIRD_PARTY_NOTICES.md`. Confirmed these are the *only* two frontend production dependencies (`web/package.json`); no vendored icon library, no bundled font file (`web/src/styles.css` uses only system-font fallback stacks -- zero `@font-face` declarations), so no separately-licensed frontend asset exists to account for. |
| ONNX Runtime GPU / CUDA-cuDNN redistributable stack (`onnxruntime-gpu`, `nvidia-cublas`, `nvidia-cudnn-cu13`, `nvidia-cufft`, `nvidia-curand`, `nvidia-cuda-runtime`, `nvidia-cuda-nvrtc`) | `onnxruntime-gpu`: MIT. The `nvidia-cu*` packages: proprietary NVIDIA CUDA/cuDNN binaries under NVIDIA's own redistribution terms (their PyPI metadata's permissive classifier covers only the thin Python packaging layer, not the native libraries themselves) | Yes, when `--include-gpu-runtime` (the default) | The identical, well-established distribution pattern official PyTorch/TensorFlow GPU wheels already use for the same libraries -- not treated as a blocker | Disclosed plainly in `THIRD_PARTY_NOTICES.md` as an **engineering interpretation, not independently re-verified against NVIDIA's current EULA text this milestone** -- see "Remaining legal decisions," below. |
| BioCLIP/OpenCLIP runtime closure (`torch`, `torchvision`, `open_clip_torch`, and their own further pinned dependencies) | BSD-3-Clause (`torch`, `torchvision`); MIT (`open_clip_torch`) | Yes, when `--include-bioclip-runtime` (the default) | Permitted | Named at the closure level in `THIRD_PARTY_NOTICES.md` (not a line-by-line transitive dump, per this milestone's own bounded-archaeology instruction); each package's own `dist-info/LICENSE` already ships colocated, structurally. |

## Package-content proof

Per this milestone's own guidance ("prefer inspecting an existing accepted
artifact if current enough... do not run a long Windows acceptance cycle
merely for ceremony"): no existing retained release artifact contains this
milestone's own brand-new code, so there is nothing "current enough" to
inspect instead of exercising the real packaging function directly. Ran
the actual, unmodified `assemble_windows_bundle` production function
(`scripts/build_local_product.py`) against structurally realistic fixtures
via `tests/test_local_product_packaging.py` and inspected its real
filesystem output directly (not merely asserted against a mock):

- `THIRD_PARTY_NOTICES.md` is present in the assembled bundle root,
  byte-identical to the repository's own file (`test_package_third_party_
  notices_copies_the_real_repository_file`), containing the required
  "BirdNET" and "ffmpeg" disclosures (`test_assemble_windows_bundle_
  produces_a_python_and_pip_free_user_experience`'s new assertions).
- No `ffmpeg`/`ffmpeg.exe` file exists anywhere in a clean assembled bundle
  (`test_verify_no_bundled_ffmpeg_binary_passes_when_absent`), and a
  planted one anywhere in the tree -- including via a dependency-installer
  callback exercising the real `assemble_windows_bundle` call path, not
  only the unit-level guard function in isolation -- fails the whole build
  (`test_assemble_windows_bundle_fails_the_whole_build_on_a_bundled_
  ffmpeg_binary`; 3 case variants of the unit-level guard, covering exact-
  case, `.exe`, and mixed-case basenames).
- The pre-existing `birdnetlib`-exclusion guard was re-read in full and
  its call site in `assemble_windows_bundle` reconfirmed live (unchanged
  by this milestone); its own 3 pre-existing tests still pass.
- `package_third_party_notices` fails the whole build outright if its
  source file is ever missing (`test_package_third_party_notices_fails_
  the_build_when_source_is_missing`), matching the "never optional" bar
  `write_build_identity` already set for `build_info.json`.

## Enforcement

Two build-time guards, both invoked unconditionally inside
`assemble_windows_bundle` (never opt-in, never skippable by a build flag):

1. `verify_no_nc_licensed_acoustic_model_redistribution` -- pre-existing,
   re-verified working this milestone (BirdNET/NC-model exclusion).
2. `verify_no_bundled_ffmpeg_binary` -- **new this milestone** (ffmpeg
   exclusion), plus `package_third_party_notices` (notices-file inclusion,
   fails closed if the source is missing).

Both are regression-tested (8 new tests, listed above), both raise
`LocalProductBuildError` -- failing the whole release build, never a
warning or a silently-degraded artifact -- and both run over the fully
assembled bundle tree, not a narrower subset that a future refactor could
accidentally bypass.

## User-facing documentation

- `docs/using-mockingbird.md`: added "Bird-sound identification
  (optional)" -- explains BirdNET is optional, not included by default,
  needs a separate one-time technical setup step, and is licensed
  differently from MockingBird itself, without framing it as a defect.
  The pre-existing ffmpeg paragraph (under "Add a camera") was re-read and
  confirmed already honest and accurate; left unchanged.
- `THIRD_PARTY_NOTICES.md` (new, repository root, also shipped inside
  every official bundle): the single place a user or auditor can read
  MockingBird's own license status, what is bundled with what license,
  and what is deliberately not bundled and why.
- `README.md`: added a factual "License" section pointing at the still-
  open owner decision and at `THIRD_PARTY_NOTICES.md`.

No UI/doc text was found claiming BirdNET ships with official packaging
when it does not -- the actual finding was *silence* (the canonical
user guide never mentioned the acoustic feature at all), not an active
false claim, so this closes a documentation-completeness gap (explicitly
required by this milestone's own §13) rather than fixing a false-claim
defect.

## Remaining legal decisions

**Resolved engineering facts** (this milestone, direct evidence):

- FFmpeg is never bundled/downloaded/redistributed by MockingBird's
  official packaging, now durably enforced.
- BirdNET/birdnetlib's NC-licensed model weights are never redistributed
  by MockingBird's official packaging (pre-existing, re-verified).
- MDv5a and BioCLIP-2 are both MIT-licensed and now carry their required
  notice text inside every official package.
- MockingBird's frontend has no vendored font or icon library requiring a
  separate license accounting.

**Owner decision required:**

- MockingBird's own source-code license (MIT recommended; see the decision
  packet above). Nothing else in this milestone's scope depends on this
  being resolved immediately, but it remains a real release blocker for
  the public launch itself (a public repository without a `LICENSE`
  leaves every recipient's rights genuinely undefined by default).

**Counsel-required issue** (unchanged by this milestone, restated for
completeness -- already correctly flagged, not newly discovered):

- Whether an individual end user's own private, on-device use of
  MockingBird+BirdNET could ever be implicated merely because the
  surrounding open-source project also accepts donations or sells
  optional paid support, given CC BY-NC-SA 4.0's NonCommercial term. This
  question was investigated in full previously
  (`docs/acoustic-productization-licensing-field-acceptance-v1-contract.md`,
  "What the license text does and does not settle") and remains correctly
  labeled there as requiring legal review before any commercial-adjacent
  distribution decision (paid support, a crowdfunded/paid appliance, a
  hosted service) touches the acoustic feature specifically. This
  milestone did not attempt to resolve it further -- doing so would
  require actual legal counsel, not additional repository archaeology --
  but did make it visible to the end user for the first time (previously
  it existed only in an internal contract doc).

**Engineering interpretation, not independently re-verified this
milestone** (named honestly rather than glossed over):

- The NVIDIA CUDA/cuDNN redistributable packages bundled with GPU builds
  are treated as using the same well-established EULA-based redistribution
  pattern official PyTorch/TensorFlow GPU wheels already use. This
  milestone did not fetch and re-read NVIDIA's current CUDA/cuDNN EULA
  text against exactly what these specific pinned package versions ship,
  since doing so credibly needs its own bounded pass, not a rushed
  addendum to this one. Not treated as a release blocker -- this is an
  extremely well-established distribution pattern across the entire PyPI
  ML ecosystem -- but named explicitly rather than asserted with false
  certainty.

## Release blocker disposition

- **Not a release blocker (resolved this milestone):** FFmpeg
  distribution posture; missing MDv5a/BioCLIP-2 notice text; the
  documentation gap where the shipped acoustic feature was never
  explained to an actual product user.
- **Not a release blocker (already correctly enforced, pre-existing,
  re-verified):** BirdNET/birdnetlib NC-model exclusion.
- **Remains a release blocker:** MockingBird's own source-code license,
  pending the owner's one-sentence decision (decision packet above).
- **Remains a disclosed, non-blocking, counsel-flagged question:**
  BirdNET's genuinely ambiguous commercial-adjacent private-use question,
  unchanged from its prior status, now more visibly disclosed to end
  users.

## Validation

Tier 1 (focused packaging/license tests): `tests/test_local_product_
packaging.py`, excluding 4 pre-existing `slow`-marked tests unrelated to
this change (real ~1.6GB model/BioCLIP-bundle hashing and real Windows
GPU/BioCLIP dependency-closure installs -- neither touches licensing/
notices/ffmpeg code and neither was modified) -- **74 passed, 0 failed**, including
8 new tests, each proven meaningful by its own `pytest.raises` assertion
(a guard that did not actually fire would fail its own test). `ruff
check`: clean on both changed Python files (`scripts/build_local_product.py`,
`tests/test_local_product_packaging.py`) -- zero findings, not merely zero
*new* findings.

Tier 2/Tier 3: not run. This milestone's only production-code change is
confined to `scripts/build_local_product.py` (a Windows packaging/build
tool with zero importers anywhere in `src/mockingbird/`, confirmed by the
identical reasoning this codebase has already applied to every prior
packaging-tooling-only milestone -- Camera Node Upgrade & Compatibility
Recovery v1, Storage/Retention's `deploy_windows_dev.py` work, and others).
No schema, API, frontend, or cross-cutting runtime code was touched. A
full Core gate would exercise thousands of tests with zero relationship to
this change.

Package-content proof: see "Package-content proof," above -- the real
`assemble_windows_bundle` function's real filesystem output was directly
inspected, not merely asserted.

## Decision

**B.** Engineering work is complete: official package contents are
legally characterized; BirdNET weights are demonstrably excluded (both by
pre-existing enforcement, re-verified, and now by an equally durable new
guard for ffmpeg); FFmpeg's distribution posture is established (never
bundled, now durably enforced) rather than merely assumed; required
notices/attributions are represented inside every official package for the
first time; no false user-facing licensing claim was found, and the one
real documentation gap found (BirdNET's total absence from the canonical
user guide) is fixed. The one remaining item -- MockingBird's own
source-code license -- is proven to require an explicit owner decision,
with a complete decision packet (one recommendation, two named
alternatives, dependency compatibility, and the exact one-sentence
question the owner needs to answer) and no other unresolved engineering
ambiguity blocking it. Per this milestone's own acceptance bar (§20),
Classification A requires the code-license question to be either
authoritatively selected and implemented, or proven to need an owner
decision with a complete packet -- the latter applies here, so this
milestone closes at **B**, not A, honestly reflecting that one real,
named, owner-facing decision remains outstanding.
