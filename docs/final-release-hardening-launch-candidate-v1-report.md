# Final Release Hardening & Launch Candidate v1 -- Release-Candidate Acceptance Report

**Status:** executed 2026-10-17/18. **Classification: A with disclosed
limitations** (below). **Recommendation: GO to the owner's release decision**
for the candidate in section 2, conditional on the owner decisions in section 9.
This report is evidence for that decision; it is not the decision. Nothing was
pushed, tagged, published, distributed, deployed or announced, and no later
milestone is started or authorized.

## 1. Scope and identity

| Item | Value |
|---|---|
| Starting HEAD / schema | `7f7809a` / v62 (read-only reconciliation baseline) |
| Candidate source commit | **`1410c1be6b16c25b310cd876e9a2f43c213329d7`** (`1410c1b`) |
| Schema | **v62** (unchanged; no migration added) |
| Version | **`0.1.0`** (unchanged; **no bump performed** -- owner decision) |
| Gate G | owner-**waived, not passed** (unchanged) |
| One-public-release doctrine | preserved; no beta or extra distribution stage |
| Protected files | the seven untracked detector files and `uv.lock` were never opened for writing; `git status` shows them untracked and unchanged |
| Writer safety | process 64539 is a sleeping Claude session with this repo as cwd (zero CPU over a 20 s sample; task dir untouched since 2026-10-14; git index/tree unchanged since 2026-10-15). Treated as idle. Rechecked before each edit/commit. |

Last ZIP-level Windows acceptance before this was `d7e61c1`. Since then: 26
commits, schema 61->62, large presentation changes, and `fd8a57b` had never been
packaged. Everything below is of the **exact built ZIP**, not a checkout.

## 2. Changes made (all release-hardening, none a capability)

| Commit | Change | Why |
|---|---|---|
| `08f5644` | `tests/test_scene_confusor_repository.py`: `NOW` anchored to the real clock; `docs/owner-release-checklist.md`: version is an owner decision, no stale "28 commits ahead" | see defect D-1 and D-3 |
| `1410c1b` | `THIRD_PARTY_NOTICES.md`, `docs/support-matrix.md`: state precisely that the bundled OpenCV wheel carries FFmpeg libraries | defect D-2 |

No product source, schema, packaging script, model or policy changed.

## 3. Defects found

| ID | Finding | Disposition |
|---|---|---|
| D-1 | `test_revision_from_real_to_false_retracts_stale_real_protection` failed deterministically (3/3 isolated; also on exports of `d7e61c1`, `c146eff`, `73429ee`, `28463ea`, `a753792`). The test hard-coded `NOW = 2026-08-19`; the review-revision path stamps `datetime.now(UTC)` and lazily purges scene-confusor regions older than `DEFAULT_REGION_TTL_DAYS = 45`, so it began failing when real time passed 2026-10-03 (it passed on 2026-09-29). **A test time bomb, not a product defect:** production timestamps and the real clock agree. | **Fixed (test only)**, `08f5644`. 90 scene-confusor tests pass. |
| D-2 | `THIRD_PARTY_NOTICES.md` and the support matrix said FFmpeg is "never bundled". True of an `ffmpeg` executable (the build enforces it), but the ZIP ships `cv2/opencv_videoio_ffmpeg4140_64.dll` inside the unmodified `opencv-python-headless` wheel (also present in the previously accepted `d7e61c1` ZIP), whose own shipped `LICENSE-3RD-PARTY.txt` says "FFmpeg is redistributed within all opencv-python packages." Nothing in `src/` uses OpenCV video decoding. | **Fixed (docs)**, `1410c1b`. The notices are inside the ZIP, so the ZIP was rebuilt. Owner should still confirm the legal position (section 9). |
| D-3 | Owner checklist stated "28 commits ahead of origin/main" (actually 41) and "Authorize Final 1.0 Hardening (not yet authorized)". | **Fixed (docs)**, `08f5644`. |

No other release-critical defect was found. Browser, Windows and artifact checks
below found no product failure.

## 4. Validation

| Gate | Result |
|---|---|
| Full backend gate (`verify_full.py`) at `7f7809a` | 6420 passed, **1 failed (D-1)**, 4 skipped, 11 xfailed, 47m27s |
| After D-1 fix | scene-confusor files 90 passed; packaging/version/verifier files **121 passed** |
| Frontend `tsc --noEmit`, production build | clean / exit 0 |
| Browser suites (Edge/Chromium via Playwright) | default **240**, onboarding **6**, review-queue **4**, bounded-media **2** = **252/252 passed** |
| `verify_release_artifact.py` on the candidate | OK (19291 files, 4,924,401,378 bytes, `0.1.0`, `git:1410c1b…`, unsigned) |

**Honest gap:** the complete Full gate was **not re-run** after `08f5644`/`1410c1b`.
The two commits change one test constant and three documentation files; the
affected test files and every packaging test were re-run. The browser suites
ran on the pre-`1410c1b` frontend, which is byte-identical (no `web/` change
between `7f7809a` and `1410c1b`).

## 5. Artifacts (candidate `1410c1b`, ignored path `dist/`)

`dist/final-release-candidate-v1-1410c1b/`

| File | SHA-256 |
|---|---|
| `MockingBird-windows-x64.zip` | `88353648d7626ede75ea946393f87b39df87866909f75932cd4a0ed99c2c6f9e` |
| `manifest.json` | `e01b00fed97fd5f1e2892e9a5f5996f57df9b4be91c0be3e60abba516c0add8a` |
| `sbom.json` (CycloneDX 1.5, 59 components) | `0dbc6aaf1a7b4842a3e22360e1f6af98d72127d860fa88cf796c767cc09f3084` |

Camera Node artifact, `dist/final-release-candidate-v1-1410c1b-camera-node/`:
`mockingbird_camera_node-0.1.0-py3-none-any.whl`
`38dfac47a6ea6b164fe82e94642540d02be213506b7ee7d6e1090afe93f6d904`
(**identical hash to the previously accepted Node wheel**: Node code unchanged),
plus `requirements.txt`, `camera-node.env.example`, `install_camera_node.py`,
`manifest.json`, `SHA256SUMS`; all verified with `sha256sum -c`.

Independent verification (re-derived, not trusting the builder): `sha256sum -c`
on both sets; the **Windows-side** `Get-FileHash` of the copied ZIP equals the
recorded hash; `build_info.json` inside the ZIP reports `git_commit` `1410c1b…`,
`source_clean: true`, `app_version 0.1.0`; the manifest `source_state` is
`git:1410c1b…`; unsigned (`signing.requested: false`) as documented.

Inclusion rules checked against the ZIP listing: bundled MegaDetector v5a ONNX
(`md-v5a-0.1-raw-fixed-1280.onnx`) and BioCLIP 2 (`open_clip_model.safetensors`);
no BirdNET weights/labels (only the adapter source); no standalone `ffmpeg`
executable; no database, `.env`, key material, `.orig` file, `uv.lock`,
benchmark or training script (the build compiles from a `git archive` snapshot,
so the protected untracked files cannot enter). `LICENSE` and
`THIRD_PARTY_NOTICES.md` ship at the ZIP root. Superseded:
`dist/final-release-candidate-v1-08f5644*` (built before D-2; do not use).

## 6. Native-Windows acceptance of the exact ZIP

Environment: this machine's Windows 10 x64 host, RTX 4060 Ti (WDDM), Microsoft
Edge driven by Windows-side Node/Playwright. ZIP copied to `D:\MBRC`, hash
re-verified on Windows, extracted with `tar.exe` (73 s), launched with the six
persistent `MOCKINGBIRD_*` user variables **scrubbed at process scope** (they
otherwise override packaged model paths) and `MOCKINGBIRD_HOME=D:\MBRC\home`
(disposable). Evidence: `dist/final-release-candidate-v1-1410c1b-evidence/`
(18 screenshots, driver, JSON-lines logs).

| Check | Result |
|---|---|
| Identity | `/api/product/instance`: commit `1410c1be…`, build `289e4a797d4617ed`, `0.1.0`; log path under `D:\MBRC\home` |
| Start | `Start MockingBird.vbs` -> ready in **15.3 s** (3.6 s on restart) |
| Auth gate | unauthenticated `/api/visits` -> 401 "Sign in to continue." |
| First-run onboarding | Welcome -> Account (admin created) -> Storage -> Add a camera (manual-media Source, "Configuration Valid") -> Finish; reaches Dashboard |
| Readiness | health `ready:true`, storage healthy; Doctor **HEALTHY, all 16 checks PASS** (incl. `gpu_cuda`, `detector_model`, `species_identification`, `media_integrity`, `camera_node`, `backup`) |
| Evidence -> Review -> Confirmation -> Bird Log | imported still -> Visit `needs_review`, label empty, **not** in Bird Log -> Fast Review confirm `northern_cardinal` -> `reviewed`, `review_origin: human`, `is_authoritative: true` -> appears in Bird Log |
| Backup | created, **verified**, schema 62, media file included |
| Restore | after a post-backup second Visit was confirmed, restore removed it (**404**) and the Bird Log lost it; the first Visit's reviewed truth survived intact |
| Shutdown / restart | UI "Shut down MockingBird" stops the process and frees port 8000; restart reports `previous_shutdown_clean: true`, schema 62, reviewed truth persisted, Doctor HEALTHY again |
| Errors | 404/422 probes return safe messages, **no paths or stack traces**; zero browser console errors and zero 4xx/5xx after sign-in on the restart pass (the single 401 in phase one is the driver's own pre-sign-in session probe); no ERROR/Traceback/CRITICAL in the instance log |
| Field instance preserved | default `%LOCALAPPDATA%\MockingBird` byte-identical before/after (8 files, 3,075,185 bytes, newest write 2026-09-25); nothing was listening on 8000-8200 before the run; no Camera Node pairing credential touched |

## 7. Known limitations (accurate, not softened)

1. **Camera Node live path not exercised.** The reference Pi did not answer ping
   or HTTP this session. Compatibility rests on the byte-identical Node wheel
   (hash above), unchanged Node code, protocol `node v1 / transport/v1`, and the
   Doctor `camera_node` checks (which have no paired Node here). Version skew
   never fails compatibility.
2. **No live camera observation** was run: the acceptance Source was an import
   Source. Detector and GPU were verified through Doctor readiness, not a live
   stream.
3. **Launch method.** The disposable home required setting `MOCKINGBIRD_HOME`
   and `--no-browser` before invoking `Start MockingBird.vbs`; a plain
   double-click was not used (it would open the default field home). Browser
   auto-open was not observed.
4. **No human interactive pass**; automated browsers only. Windows 11 and
   other GPUs/drivers remain untested (see `support-matrix.md`). Unsigned
   (SmartScreen warning is documented).
5. Full backend gate not re-run after the two small commits (section 4).
6. Product-facing latency: the accepted 20-minute component-decision horizon is
   an architectural reference, not a promised maximum observation latency.
7. Unsupported paths remain as documented in `support-matrix.md` (BirdNET not
   bundled; FFmpeg not bundled as an executable; RTSPS refused; packaged
   Linux/macOS Host not provided).

## 8. Validation to repeat if the owner selects `1.0.0`

- Edit the four sources: `pyproject.toml`, `mockingbird.__init__._DEV_CHECKOUT_FALLBACK_VERSION`,
  `mockingbird_node.__version__`, `web/package.json`, plus `web/package-lock.json`
  (`tests/test_version_provenance.py` keeps the first four in sync). Update
  the README "Status" paragraph and the owner checklist.
- **Rebuild everything** from a clean commit: Host ZIP, `manifest.json`,
  `SHA256SUMS`, `sbom.json`, and the Camera Node wheel (its filename and hash
  change, so the previously accepted Node hash no longer applies).
- Re-run `verify_release_artifact.py`, the packaging/version tests, and
  recompute/verify every SHA-256.
- Re-run native-Windows acceptance of the **new** ZIP (section 6) -- at minimum
  identity, first run, Evidence->Review->Confirm->Bird Log, backup/restore,
  shutdown/restart, Doctor. Re-run the Host<->Node compatibility preflight when
  the reference Camera Node is reachable.
- If only version strings change, the Full gate and browser suites need not be
  repeated for product behavior; re-run Core/browser if anything else changes.
  A fixture search for the literal `0.1.0` (test fixtures that hard-code it)
  is advisable.

## 9. Remaining owner decisions (unchanged by this work)

Release version (`0.1.0` vs `1.0.0`); authorization to push `main` (41 commits
ahead when this began); tag and GitHub Release; confirming the
`github.com/zkelder/mockingbird` location and enabling private vulnerability
reporting; security contact; NVIDIA CUDA/cuDNN redistribution notice; code-signing
position; MIT holder line; BirdNET stance; **and, new, confirming the licence
position for the FFmpeg libraries inside the bundled OpenCV wheel (D-2).**
If the owner tags, tag `1410c1b` (the artifacts' source commit); later commits
on `main` are documentation only.

## 10. Go / no-go

**GO** for the owner's release decision on candidate `1410c1b` / ZIP
`88353648…`: current-artifact evidence exists for the exact build; every
automated gate is green apart from the disclosed, fixed test time bomb; no
product defect was found. Not a recommendation to publish before the section 9
owner items, and not a claim about untested hardware (section 7).
