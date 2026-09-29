# External Pre-Release Acceptance (Gate G) -- Launch Package Refresh v1 -- Report

**Type:** bounded Gate G launch-package refresh under the feature freeze.
Not a product-development milestone. **Gate G is not started.**

**Classification: A.** See §8.

## 1. Task packet (restated)

- **Roadmap phase:** release-critical sequence, Gate G (External
  Pre-Release Acceptance) preparation. Feature freeze in force.
- **Product flow improved:** a participant's Observe -> Discover ->
  Understand -> Confirm -> Remember path starts from accurate
  instructions for the exact accepted candidate. The package keeps the
  Measured/Inferred/Reviewed boundary visible, and it says plainly that
  honest abstention is correct behavior.
- **Why this is next:** candidate `2272126` was re-accepted on native
  Windows (F-1/F-2/F-3 closed). The 2026-09-08 participant materials
  were written for `2fe2729` and no longer matched it.
- **Files allowed:** `docs/gate-g-launch-package-v1/*` (new); this
  report (new); a supersession note on
  `docs/external-pre-release-acceptance-private-cohort-v1-participant-materials.md`;
  `docs/release-execution-state.md` (additive delta). Ignored output
  under `dist/gate-g-launch-package-v1-2272126/`.
- **Non-goals:** any product, schema, model, detection, identification,
  or Camera Node change; a rebuild; new Pi evidence; contact,
  recruitment, upload, accounts, repository access; push, tag, sign,
  publish.
- **Validation tier:** docs-only work plus artifact identity checks.
  No test suite was run, because no code changed.

## 2. Starting state

| Fact | Verified |
|---|---|
| Root / branch | `/home/zkelder/projects/mockingbird-active` (native WSL, not `/mnt/c`), `main` |
| HEAD | `1f63b62ee97243187570208cf9851c568d19fdb9` |
| `2272126..1f63b62` | Docs only: the correction report and the `release-execution-state.md` delta |
| Staged / worktree | Nothing staged; only the 7 protected files and `uv.lock` untracked |
| Active writers | No `index.lock`, no MockingBird/pytest/git process running |
| Authorization at start | `NONE` (the owner's directive for this refresh is the only authorization) |

## 3. Artifact identity (no rebuild)

The artifact was present and passed verification, so it was **not
rebuilt**.

- **Windows ZIP:**
  `dist/native-windows-runtime-correction-v1-2272126/MockingBird-windows-x64.zip`
  - SHA-256
    `124939b96bde155fceb34595a8ab41d7ca65ef2c3ff9a1d4a6bdeaeecc8dc650`,
    2,913,303,719 bytes.
  - `build_id c1b25f79d2db3f10`, `git_commit 2272126b…`,
    `source_clean: true`, version `0.1.0`, 19,284 files /
    4,923,709,105 bytes unpacked, unsigned, SBOM `ce26f5d6…` with 59
    components.
- **Camera Node wheel:** SHA-256
  `38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904`,
  `git_commit 2272126b…`, `source_clean: true`. It is not part of the
  participant bundle (§5).

**Checks run this session:**

1. `sha256sum -c SHA256SUMS` in both build directories: all 8 entries
   OK.
2. `scripts/verify_release_artifact.py` (the independent verifier) ->
   `OK: MockingBird-windows-x64.zip (19284 files, 4,923,709,105 bytes),
   version 0.1.0, source git:2272126bfed784b48862fd59b99e19e03202b26f,
   unsigned`, exit 0.
3. Read directly from the ZIP without extracting: all **212/212**
   packaged `mockingbird/*.py` files are byte-identical to
   `git show 2272126:src/mockingbird/…`. None is missing and there are
   no extras. The packaged `build_info.json` names `2272126` /
   `c1b25f79d2db3f10`. `LICENSE` and `THIRD_PARTY_NOTICES.md` are
   byte-identical to `2272126`. The only BirdNET-related entry is
   MockingBird's own `birdnet_adapter.py`; there are no BirdNET weights
   and no `ffmpeg.exe`/`ffprobe.exe`.

No mismatch and no product defect was found.

## 4. Reconciliation of participant materials against `2272126`

The 2026-09-08 materials contain no candidate hash. The obsolete hash
(`36b9668b…`, candidate `2fe2729`) and the obsolete defect warnings (the
Doctor Storage false `FAIL`, and the "did not shut down cleanly" note
after every stop) appear only in the historical private-cohort report.
That report is left unchanged. The refreshed package names only
`2272126` / `124939b9…`, and it describes the current, fixed behavior:
Doctor is healthy after onboarding, and the in-app shutdown is clean.

The following statements in the old materials were wrong for `2272126`
and are corrected in the package:

| Old statement | Corrected against |
|---|---|
| Four-step onboarding | Five steps with Account (`using-mockingbird.md` "First-run setup"; the correction report's Edge sessions) |
| Stop via Task Manager / `pythonw.exe` | Local Data -> **Shut down MockingBird** -> **Confirm shut down** is preferred. Task Manager is a fallback (`LocalDataPage.tsx`; the correction report's §8) |
| BirdNET "downloads a model the first time you use it" | Never bundled or downloaded; out of scope for the test; the CC BY-NC-SA 4.0 disclosure is kept (`THIRD_PARTY_NOTICES.md`, `using-mockingbird.md`) |
| `python -m mockingbird doctor` | The in-app Doctor first. The CLI fallback is `python\python.exe -m mockingbird doctor` from the application folder (the launcher sets no environment, so the CLI resolves the same data home) |
| No checksum step, no SmartScreen notice | `Get-FileHash` against `124939b9…`; the unsigned-build SmartScreen notice |
| No support-bundle procedure | `python\python.exe -m mockingbird support-bundle --no-local-paths`; its output location; what it excludes |

Other additions: the disclosed non-blocking observations O-1 (imported
video with no capture time gets a placeholder date) and O-2 (the "No
detections are attached" wording); the person/pet confound; the cold
BioCLIP latency (~54 s); and the fact that live camera and Observation
were not re-exercised on this exact build. Every factual claim traces to
`using-mockingbird.md`, `THIRD_PARTY_NOTICES.md`, the Gate G plan, or
the two latest acceptance reports. Nothing new was invented. The latency
figures (80-115 s typical, several minutes occasionally) are the
accepted Gate A figures, unchanged.

**One disclosed observation, not fixed (artifact content):** the ZIP's
own `README-FIRST.txt` describes stopping MockingBird only through Task
Manager. It predates the in-app shutdown. The behavior it describes is
still safe, and changing it would require a rebuild, so it is out of
scope here. The package tells participants about it in two places
(install and known limitations). Recommended for Final Release Hardening.

## 5. Ready-to-share bundle

**Tracked sources:** `docs/gate-g-launch-package-v1/`.
**Assembled bundle (ignored, local only, not sent):**
`dist/gate-g-launch-package-v1-2272126/`.

| File | Purpose |
|---|---|
| `MockingBird-windows-x64.zip` | The verified artifact (a hard link to the build output; same inode, same hash) |
| `manifest.json`, `sbom.json` | The build's own provenance, copied unchanged |
| `SHA256SUMS` | Covers all 12 files; `sha256sum -c` all OK |
| `PROVENANCE.txt` | Build identity, model hashes, licenses, exclusions |
| `00-START-HERE.txt` | Index and reading order |
| `01-CONSENT-AGREEMENT.txt` | Explicit written opt-in consent |
| `02-INSTALL-AND-VERIFY.txt` | Requirements, checksum check, unpack, SmartScreen, five-step setup, clean stop |
| `03-KNOWN-LIMITATIONS.txt` | Known limitations and support boundaries |
| `04-FIRST-USE-TASKS.txt` | Measured/Inferred/Reviewed, then tasks 1-6 (setup, first Visit, review/correction, multi-day, backup/shutdown, Doctor) |
| `05-DIAGNOSTICS-AND-SUPPORT.txt` | Doctor and support-bundle instructions |
| `06-BACKUP-UNINSTALL-WITHDRAW.txt` | Backup, recovery, update, uninstall, withdrawal |
| `07-FINDINGS-TEMPLATE.txt` | Private findings template |

Doctrine preserved: Local Only is the default; the only outbound paths
are opt-in (weather, and LAN/phone access); plaintext credentials and
trigger-only Zones are disclosed; guesses stay guesses until reviewed;
"no useful suggestion" is framed as correct; licensing disclosures are
unchanged.

The Camera Node wheel is deliberately excluded. The Pi path stays
owner-assisted, and no new Pi evidence exists for this candidate (its
Camera Node code is byte-identical to the previously accepted wheel).

## 6. Owner checkpoint -- remaining placeholders

Every placeholder is a literal `{{TOKEN}}`. Find them with
`grep -n "{{" docs/gate-g-launch-package-v1/*.txt`.

| # | Input needed | Token / location | Count |
|---|---|---|---|
| 1 | Participant identities and setups (3-5 proposed; Windows/GPU/camera mix) | `{{PARTICIPANT_NAME}}` in `00-START-HERE.txt`; the cohort roster itself is not in the package | 1 |
| 2 | Owner name, as participants should see it | `{{OWNER_NAME}}` in 00, 01, 02, 05, 06 | 7 |
| 3 | Owner contact information | `{{OWNER_CONTACT}}` in 00, 01, 05, 06 | 5 |
| 4 | Private artifact-delivery channel (must carry ~2.9 GB) | `{{DELIVERY_CHANNEL}}` in 02 | 1 |
| 5 | Private findings-intake channel | `{{FINDINGS_CHANNEL}}` in 07 | 1 |

Still open (carried forward, not new): approval of the exact consent
and invitation wording; the go/no-go to recruit or send; any numeric
onboarding or exit target (none is invented); whether a participant may
use the Camera Node path (if so, deliver wheel `38dfac47…` with the
install guide); the BirdNET commercial-adjacent legal review (no
engineering action).

**After filling the placeholders**, regenerate the text-file lines in
the bundle's `SHA256SUMS`, then run `sha256sum -c SHA256SUMS`. The ZIP
line (`124939b9…`) must not change.

## 7. Validation and hygiene

- Artifact checks: §3 (SHA256SUMS, the independent verifier, and the
  212-module source comparison).
- The bundle's `SHA256SUMS` verified OK. The placeholder inventory was
  grep-verified.
- Every quoted UI or Doctor string was confirmed in source: "did not
  shut down cleanly", "has not been created yet", "No useful
  suggestion…", "Import backup", "Before update", "Shut down
  MockingBird".
- No test suite was run: no code changed.
- Protected files: the 7 detector files and `uv.lock` have SHA-256
  values identical before and after, and remain untracked.
- Nothing was contacted, sent, uploaded, created, pushed, tagged,
  signed, or published. No MockingBird process was started.

## 8. Classification and closure

**A.** The package matches `2272126` exactly. Obsolete statements are
corrected, the doctrine and licensing disclosures are preserved, and
the only remaining gaps are owner inputs (§6). **Gate G is not
started.** **Authorization returns to `NONE`.**
