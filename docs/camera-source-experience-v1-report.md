# Camera / Source Experience & First-Hour Setup Closure v1

Closes Lane G ("Camera / Source Experience", PARTIAL -- v0.1 CRITICAL) in
[release-execution-state.md](release-execution-state.md) to the extent
described below. This is a v0.1 productization pass over an
already-substantial acquisition foundation -- not a provider-architecture
rewrite, not a new perception milestone, not multi-site, not Remote
LTE/solar, not final release hardening.

## 1. Scope and method

Starting state: branch `main`, HEAD `74c192a`, schema v53, nothing to push.
Concurrency check passed (only the seven preserved untracked files present;
six other `mockingbird-active-*` sessions confirmed idle via two-sample
`/proc` CPU deltas before any write).

Bounded archaeology covered the live backend (`src/mockingbird/...`),
live frontend (`web/src/...`), and the directly germane existing design
docs (camera-source-multi-camera-maturity-v1, the Camera Node
pairing/reprovision/installer docs, the ONVIF/RTSP acquisition docs, the
offline/recorded-media doc, the Doctor and error-taxonomy docs, and the
golden-path sections of `using-mockingbird.md` /
`local-product-packaging-design.md`) -- not the full historical milestone
archive.

## 2. What already existed (confirmed, not rebuilt)

- A single shared `Source` -> `SourceProviderConfiguration` model across
  all five provider shapes, with a real (if two-layered:
  `SourceKind` + `provider_key`) discriminator, not five parallel systems.
- A genuinely rich, taxonomy-backed connection-validation path for manual
  RTSP at **setup time**: `probe_rtsp_stream` connects, negotiates, and
  decodes one real frame, distinguishing unreachable / auth-failed /
  negotiation-failed / unsupported-codec / decode-failed / timed-out /
  ffmpeg-missing, all through `diagnostics/error_taxonomy.py`.
- RTSPS honestly refused at three independent layers (setup-write,
  status/capability, and runtime-command-build), because this host's
  ffmpeg build silently downgrades `rtsps://` to plaintext `tcp://`.
- A five-level, already-accepted support-maturity taxonomy
  (`certified | compatible | experimental | import_only | unsupported`)
  surfaced in the Add Camera provider picker and the legacy Streams
  provider-setup panel, with unsupported providers disabled outright.
- A real Camera Node "Check the picture" preview (fetch-without-persist,
  `Cache-Control: no-store`) -- the one provider that already had a true
  visual confirmation step during setup.
- A working, three-entry-point Add Camera flow (Dashboard hero,
  zero-camera empty state, Streams panel) that always lands on the same
  guided `CameraSetupPage` wizard, never a second weaker path -- with a
  `finishBlockers` mechanism that names every reason Finish is disabled,
  never silently disabling it.
- Archive-only camera removal (`CameraSourceUpdate.archived`) that never
  deletes/orphans Visits, Observations, or evidence -- there is no delete
  endpoint for a Source or Stream at all, by design, and this is correct
  per doctrine.
- Non-color-only, per-camera-scoped health presentation
  (`CameraHealthState`, 9 values / 4 tones) that never lets one broken
  camera make the whole product look down (`ProductHealthPanel` is a
  single calm count line, never a red top-of-page banner).
- A real first-run wizard (welcome -> account -> storage -> camera ->
  observe) that embeds the unmodified `CameraSetupPage`/
  `ObservationControlPanel`, persists progress server-side, and fails
  open rather than trapping a user.
- Offline/recorded import already promoted out of Developer-Mode-gated
  nav into the primary product loop, with its own honest "this is not a
  live camera" framing and a real per-frame analysis path
  (`analyze-recorded`) distinct from folder-import metadata-only preview.

None of this was rebuilt. The gap search was for what breaks the
first-hour product experience specifically, at the boundary the golden
path actually touches.

## 3. Gap table (Phase 1)

| Capability | Existing behavior | User-visible problem | Severity | Fix |
|---|---|---|---|---|
| Manual RTSP "Auth username"/"Auth password" | Collected in the UI, but every write collapsed the value to the literal `"configured"` and it was never read by any connection code -- only a URL with credentials the user had hand-embedded themselves ever worked | A user who fills in the separate credential boxes (the friendlier, jargon-free path Phase 3.9 asks for) gets a silent, permanent, unexplained authentication failure | **P0** | Store the two fields for real (mirroring the existing `camera_node` exemption pattern); merge them into the effective connection URL at every real usage site (setup probe, new preview, live playback/monitoring) via a new `rtsp_bridge.embed_rtsp_credentials`, reusing the exact mechanism ONVIF's own client-side embedding already proved |
| Setup-time visual confirmation | Only Camera Node had an actual "Check the picture" step; `CameraSetupValidationResponse.preview_available` existed in the schema but was hardcoded `False` for every provider and never read by the frontend | RTSP, ONVIF (via RTSP), and local/Windows USB users get only a text status before Finish -- Phase 5's core ask ("show an actual preview... where possible") was met for 1 of 4 provider families | **P0** | New bounded, transient, non-persisting preview capability (`rtsp_bridge.capture_rtsp_preview_frame`, reused local/Windows USB single-frame capture) behind a new `POST /api/camera-setup/preview-frame`; `preview_available` now computed honestly; a "Check the picture" button added to `CameraSetupPage.tsx` for RTSP/ONVIF/local/Windows, matching Camera Node's own copy and blob-lifecycle pattern |
| Local/USB live-openness check | `local_camera_status`/`windows_camera_status` are static-only (device path shape, platform, ffmpeg presence) -- no live-open probe exists at setup time, unlike RTSP's `probe_rtsp_stream` | A local/USB setup can pass validation while the device is genuinely unusable, and the user only finds out after Finish | **P1** (folded into the P0 above) | The new preview-frame endpoint doubles as a real live-openness signal for local/USB, since a successful capture *is* proof the device actually opened and produced a frame |
| `StreamDetailPage` reconfigure entry point | "Edit camera setup" was only reachable when the camera already needed attention (`ObservationControlPanel`'s conditional link); a healthy camera's own detail page had no visible rename/reconfigure control at all | A user viewing their (healthy) camera's own page has to navigate back to Cameras/Dashboard to rename it or change credentials | **P1** | Added a persistent "Edit camera setup" header action, reusing the `onOpenCameraSetup` prop that was already wired end-to-end but only consumed conditionally |
| Dead inline "Add camera" form (`StreamsPage.tsx`) | A second, bare, name-only Add Camera form (`isAddCameraOpen`) existed in the code but was permanently unreachable -- nothing ever set its trigger state `true` | None today (it can't render), but it is dead weight sitting next to the real, working "Add Camera" button in the same panel, and a future edit could accidentally wire it back in as a weaker, un-validated, no-preview, no-Zone path | **P1** | Removed the dead state, handler, and JSX; the panel's existing real "Add Camera" button (which already opens the full guided wizard) is unaffected |
| Stale field disclosure text | `auth_username`/`auth_password`'s own `description`/`placeholder` honestly said "Not used for preview fetch yet" -- accurate before this milestone, now stale given the P0 fix above | Minor: a developer or future API consumer reading the field schema would be told something false | **P2** | Updated the field description/placeholder to describe the real, now-working behavior |
| Ongoing-monitoring failure-code collapse | Once a Stream is armed and running, a dead RTSP/local/Windows ffmpeg process's real cause (auth/network/codec/decode) is discarded -- `_reader_loop` only preserves the Camera-Node-only failure vocabulary; every other provider's live-session failure surfaces as the single generic string `"Camera process ended before the session was stopped."`, and `DurableMonitoringSupervisor` further collapses to `"camera_unavailable"`. Disclosed in the code itself (`docs/observability-error-taxonomy-contract.md`) as a known, pre-existing gap. | A camera that fails *after* a healthy start (not at setup) loses the specific reason Phase 9 asks the product to surface | **P1, deferred** | See "Deferred: bounded proposed fix," below -- requires enabling ffmpeg stderr capture on the *long-running* playback process (currently deliberately off for every live-playback caller) plus new classification logic for local/Windows failures that does not exist today. That is a materially larger, riskier change than this milestone's other fixes, and touches the shared retry/backoff supervisor -- correctly out of this pass's bounded scope |
| Place/site naming in onboarding | No naming UI exists anywhere in the frontend; no `PlaceModel` exists yet (per the accepted multi-camera contract's own deferred note) | Dashboard hardcodes "Today in Your Yard" | **Correctly out of scope** | Doctrine explicitly says not to build Place/multi-site naming to improve this; left untouched |
| Camera Node self-test/watchdog payload | The Node's own `/node/v1/health` already reports `self_test`/`watchdog`, but the Host never reads it -- Doctor instead infers equivalent facts from a durable DB side-channel (`camera_node_last_seen_at`, boot transitions) | A live poll would be marginally fresher than the DB-inferred facts | **Correctly out of scope** | Would mean reopening accepted Camera Node transport/recovery architecture, which Phase 7 explicitly says not to do |
| SSRF posture asymmetry | `external_url`/RTSP allows WAN hosts (blocks only loopback/metadata/reserved ranges); Camera Node/ONVIF are LAN-only | Inconsistent, but plausibly intentional (a remote/port-forwarded RTSP camera or NVR feed is a legitimate real-world case; Camera Node/ONVIF pairing genuinely has no such use case) | **Open observation, not fixed** | Recorded for the security/release lane rather than changed without stronger evidence either way |

## 4. Implementation contract (locked before broad edits)

1. Reuse the shared RTSP bridge and the existing credential-embedding
   pattern ONVIF already uses (`embed_credentials_in_uri`) -- never a
   second credential mechanism.
2. Reuse the shared connect/negotiate/decode-one-frame machinery for the
   new preview capability -- never a second RTSP decoder. Keep
   `probe_rtsp_stream`'s own documented "never carries image bytes"
   contract untouched; add a sibling function instead of reshaping it.
3. Reuse the existing local/Windows USB single-frame capture primitives
   (`capture_local_camera_frame`, `capture_windows_dshow_frame`) verbatim
   for preview -- they already existed as an on-demand action, just not
   wired into setup.
4. Reuse the existing structured error taxonomy for every RTSP failure
   code the new preview endpoint can produce; only local/Windows failure
   mapping uses an inline dict, matching that area's own established
   idiom (the pre-existing `/local-camera/capture-frame` endpoint).
5. Never persist a preview frame; never let a preview create Visit/Event/
   evidence/truth; mirror the Camera Node preview's own reassurance copy.
6. Mask `auth_username`/`auth_password` on every read path exactly as
   before -- only their *write*-time fate changes (stored for real
   instead of collapsed), never their exposure to the frontend.
7. No perception/detector/species/admission code touched.
8. No delete semantics introduced; archive-only history preservation is
   correct and untouched.

## 5. What was implemented

**Backend** (`src/mockingbird/playback/rtsp_bridge.py`,
`src/mockingbird/repository/product_repository.py`,
`src/mockingbird/api/main.py`):

- `rtsp_bridge.embed_rtsp_credentials(url, *, username, password)` --
  embeds separately-entered credentials as URL userinfo when the URL
  doesn't already carry them; a URL that already has embedded credentials
  always wins (never double-embedded).
- `_sanitize_source_provider_config` now stores `external_url.
  auth_username`/`auth_password` for real (mirroring the `camera_node`
  exemption), instead of collapsing them to `"configured"` and discarding
  the value forever.
- The credential merge is applied at all three real connection-attempt
  sites: `_rtsp_setup_probe_if_applicable` (setup validation),
  `get_stream_live_playback_config` (live playback/monitoring), and the
  new preview capture below. Status/capability-only functions (which do
  zero network I/O) were deliberately left untouched.
- `rtsp_bridge.capture_rtsp_preview_frame` -- a bounded, one-shot sibling
  of `probe_rtsp_stream` that returns the real decoded JPEG bytes on
  success instead of deliberately withholding them.
- `ProductRepository.capture_camera_setup_preview_frame` -- branches by
  provider/live-stream-type to the RTSP capture above or the existing
  local/Windows USB capture functions; raises a stable code on failure.
- `_camera_setup_preview_available` -- the shared, honest capability
  check now driving both `CameraSetupValidationResponse.preview_available`
  and the new endpoint's own early, honest refusal for unsupported
  providers.
- New endpoint `POST /api/camera-setup/preview-frame` -- returns raw JPEG
  bytes (`Cache-Control: no-store`) or a safe, taxonomy-backed error;
  never creates media, evidence, or truth.

**Frontend** (`web/src/pages/CameraSetupPage.tsx`,
`web/src/pages/StreamDetailPage.tsx`, `web/src/pages/StreamsPage.tsx`,
`web/src/api/client.ts`):

- `apiClient.previewCameraSetupFrame` (reuses the existing `requestImage`
  blob helper, widened from a Camera-Node-only type to accept any of
  these request shapes).
- A "Check the picture" button + result `<img>` in `CameraSetupPage.tsx`
  for RTSP/ONVIF/local/Windows USB setups, gated on a lightweight
  client-side capability mirror (including the same "an `rtsp://` URL
  counts even with Live stream type left blank" inference the backend
  already does) -- never on a prior "Check camera settings" click, to
  avoid a gratuitous extra step.
- A persistent "Edit camera setup" header action in `StreamDetailPage.tsx`.
- Removed the dead, permanently-unreachable inline "Add camera" form and
  its state/handler in `StreamsPage.tsx`.

## 6. v0.1 support matrix

| Source type | Support | Discovery | Validation | Preview | Monitoring | Recovery | Notable limitations | Real-hardware validation |
|---|---|---|---|---|---|---|---|---|
| MockingBird Camera Node | Certified (golden path) | Manual LAN address entry (deliberately no network scan) | Rich, dedicated failure vocabulary | Yes (pre-existing, unchanged) | Observation Engine | Bounded reconnect; boot/self-test/watchdog inferred by Doctor from a durable DB side-channel, not a live poll | Host never reads the Node's own live `/node/v1/health` self-test/watchdog fields | Not exercised this session -- the LAN reference Camera Node (192.168.1.112:8787) timed out (TCP unreachable) when checked this session (documented elsewhere as fragile/session-dependent); real hardware confirmed reachable in numerous prior sessions; not re-exercised here since Camera Node code was not touched |
| ONVIF | Compatible | Manual host/port + "Discover this camera" profile enumeration; WS-Discovery UDP exists in code but is unwired/unverified against real hardware, and honestly not offered | Same rich RTSP probe (converges to `external_url`) | **New**: real "Check the picture" via the shared RTSP preview | Durable Monitoring Supervisor (shared with RTSP) | Bounded backoff retry | Credentials are embedded client-side before submission (unchanged, already correct) | Not exercised -- no real ONVIF camera reachable this session. Converges into the RTSP code path below once a profile resolves, so that path's native-Windows evidence applies transitively |
| Direct RTSP/RTSPS | Compatible | Manual URL entry only | Rich, 7+ distinguishable failure modes | **New**: real "Check the picture" during setup | Durable Monitoring Supervisor | Bounded backoff retry; **ongoing**-monitoring failures still collapse to a generic code (disclosed, deferred -- see gap table) | RTSPS honestly refused (unchanged, 3 layers); separate Auth username/password fields **now actually work** (P0 fix) | **Real native-Windows evidence, no real camera**: on a genuinely fresh Windows install (new `instance_id`, `setup.state.completed=false`) at commit `f609c89` (confirmed via `/api/product/instance`), with real ffmpeg 8.1.2 present, a real administrator account created, signed in, then `POST /api/camera-setup/validate` and `POST /api/camera-setup/preview-frame` were called with a manually-entered RTSP URL plus separate `auth_username`/`auth_password` against `rtsp://192.0.2.55:554/...` (a TEST-NET-3 address guaranteed unreachable). `validate` returned `preview_available:true` (the honest capability signal now working) with both credential fields correctly masked (`"configured"`) in `safe_config_preview`. `preview-frame` returned a real HTTP 502 with body `"Could not reach this camera's RTSP stream. Check the URL, network, and that the camera is powered on."` -- a real ffmpeg subprocess was spawned, attempted the connection, timed out, and was classified through the real (unmocked) taxonomy path. An unmistakable canary credential value never appeared in either response. No real reachable RTSP camera was available this session to prove actual video decode/preview beyond what the existing real-local-ffmpeg synthetic-pattern test already proves |
| Local/Windows USB | Compatible | Linux: none (must already know `/dev/videoN`); Windows: real DirectShow device-listing endpoint | Previously static-only; **now** the preview capture doubles as a genuine live-openness signal | **New**: real "Check the picture" during setup | Durable Monitoring Supervisor | Bounded backoff retry; same ongoing-monitoring collapse gap as RTSP | No secret-marked fields; nothing to redact | Not exercised -- no local/USB camera device present in this sandbox or the connected Windows host |
| Offline/recorded import | Import-only (deliberately, permanently non-live) | N/A -- explicit file/folder selection | Dry-run preview + explicit import; separate real per-frame `analyze-recorded` action | Distinct concept from live-camera preview; already existed | N/A | N/A | Still-image batches and opt-in video decode already closed by a prior milestone; unchanged this pass | Not directly re-exercised this session; verified via the existing, still-green test suite only |

## 7. Deferred: ongoing-monitoring failure-code collapse (bounded proposed fix)

Root cause: `rtsp_bridge.start_rtsp_mjpeg_process`'s live-playback call
site deliberately discards ffmpeg stderr (`capture_stderr` defaults
`False`, and that default is itself documented as "unchanged: every
existing live-playback caller keeps discarding ffmpeg's stderr"). A
proper fix would need to: (1) capture stderr on the *long-running*
playback process without risking a pipe-buffer deadlock (a materially
different problem than the bounded one-shot probe/preview already
solved); (2) add new failure-text classification for local/Windows
ffmpeg output, which does not exist today (only RTSP has
`_classify_probe_failure`); (3) thread the result through
`_reader_loop` -> `DurableMonitoringSupervisor` -> `_managed_camera_status`
without disturbing the retry/backoff timing that machinery already owns.
That is real, shared, accepted recovery infrastructure -- a larger and
materially riskier change than this milestone's other fixes, correctly
left for its own bounded follow-up rather than rushed in here.

## 8. Security/privacy findings

- No new credential leak found or introduced. The one credential-honesty
  defect found (dead auth fields, see gap table) was a silent
  no-op, not an exposure; the fix keeps the exact same read-side masking
  (`"configured"`/`"not_configured"`) that already existed, storing the
  real value only where it is genuinely used (mirroring the
  already-accepted `camera_node` field pattern).
- The pre-existing SSRF asymmetry (`external_url` allows WAN hosts;
  Camera Node/ONVIF are LAN-only) was reviewed and left unchanged --
  ambiguous whether it's a gap or an intentional accommodation for
  legitimate remote/NVR-fed RTSP sources; recorded for the security/
  release lane rather than changed on weak evidence.
- No encryption-at-rest change made or implied; credentials remain
  plaintext local SQLite, matching this product's existing, documented
  trust boundary. Not claimed otherwise anywhere in this change.
- New regression test (`test_rtsp_setup_validation_never_leaks_credentials_
  in_response_or_logs`'s sibling for the new endpoint,
  `test_preview_frame_endpoint_reports_an_honest_failure_without_leaking_
  credentials`) proves an unmistakable fake credential never reaches the
  new endpoint's HTTP response.

## 9. Validation

- **Focused**: `tests/test_rtsp_probe.py` (+9 new tests: credential
  embedding, preview capture success/RTSPS-refusal/unreachable/
  no-leak-on-failure), `tests/test_camera_setup.py` (+9 new tests:
  end-to-end credential-reaches-live-playback, URL-already-credentialed
  wins, honest `preview_available`, new endpoint success/failure/
  unsupported-provider/local-usb/no-leak).
- **Subsystem**: full focused + adjacent camera/source/monitoring/health
  suite run twice (188 tests), zero failures:
  `test_rtsp_probe`, `test_camera_setup`, `test_source_provider_
  configuration`, `test_onvif_client`, `test_live_camera_session`,
  `test_source_connection_contract`, `test_camera_configuration_edit`,
  `test_source_setup_review`, `test_source_stream_smoke_flow`,
  `test_source_provider_smoke_flows`, `test_stream_monitoring_contract`,
  `test_durable_monitoring_supervisor`, `test_camera_health`,
  `test_camera_source_creation`, `test_doctor`,
  `test_request_correlation_and_error_handling`,
  `test_folder_import_preview`, `test_recorded_video_source`.
- **Frontend**: `tsc --noEmit` clean; `npm run build` (typecheck + vite
  build) clean; `git diff --check` clean. No frontend unit-test
  framework exists in this repo (Playwright e2e only). 17/17 relevant
  Playwright specs green: `camera-setup-onvif.spec.ts`,
  `camera-setup-monitoring-control.spec.ts`, `onboarding.spec.ts`,
  `camera-controls.spec.ts`, `dashboard-live-camera-ownership.spec.ts`,
  `live-camera-overview-monitoring-toggle.spec.ts`,
  `live-preview-ownership.spec.ts` -- every spec whose name suggested
  camera/source/onboarding relevance across the repo's 21 e2e specs.
- **Core**: `scripts/verify_core.py` -- 4648 passed, 2 failed, 2 skipped,
  11 xfailed. The 2 failures
  (`test_place_biodiversity_summary_repository.py::test_api_route_returns
  _the_summary` and `::test_human_correction_updates_place_biodiversity_
  intelligence_correctly`, an unrelated historical-status timing case in
  biodiversity/place reporting) reproduced identically against the clean
  `74c192a` baseline (`git stash push -u`, re-run, `git stash pop`),
  confirming pre-existing flakiness rather than a regression from this
  change.
- **Native Windows**: real, not simulated. Deployed commit `f609c89` via
  `scripts/deploy_windows_dev.py` to the existing dev host, confirmed via
  `/api/product/instance`'s `git_commit`. Then deployed a *second*,
  genuinely fresh, isolated instance (empty DB, `setup.state.completed:
  false`) to prove first-hour behavior from true zero state: created a
  real administrator account, signed in, and exercised
  `POST /api/camera-setup/validate` and the new
  `POST /api/camera-setup/preview-frame` with a manually-entered RTSP URL
  plus separate credential fields against a real, intentionally
  unreachable host, through real native-Windows ffmpeg 8.1.2 -- see
  Section 6's RTSP row for the exact evidence (honest
  `preview_available:true`, correct credential masking, a real 502 from
  a real timed-out ffmpeg subprocess, no credential leak). The original
  dev-root deployment was restored afterward (same `instance_id`, same
  accumulated release history) so session continuity is preserved.

## 10. Remaining bounded gaps

- Ongoing-monitoring failure-code collapse for non-Camera-Node providers
  (Section 7).
- No real, reachable camera/RTSP/ONVIF/local-USB hardware or Camera Node
  was available this session to prove actual video decode/preview
  end-to-end -- native-Windows evidence (Section 6) proves the real
  subprocess/HTTP/taxonomy/credential-merge mechanics genuinely work, not
  that a specific real camera's picture renders correctly.
- The new "Check the picture" button itself has no dedicated new e2e
  spec (covered by the backend integration tests and the manual
  native-Windows exercise above, not by a browser-level test).
- No real camera/RTSP/ONVIF/local-USB hardware was reachable this
  session to exercise the new preview end-to-end against genuine video;
  the RTSP preview path's real-ffmpeg-subprocess mechanics are proven
  (via the existing real-ffmpeg decode test the new capture function
  shares), but not against a live network camera.
- SSRF posture asymmetry (Section 8) -- recorded, not resolved.
