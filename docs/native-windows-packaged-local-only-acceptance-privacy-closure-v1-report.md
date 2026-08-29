# Native-Windows Packaged Local-Only Acceptance & Privacy Closure v1 -- Report

Bounded release-critical acceptance milestone answering one question: can the
actual release-shaped native-Windows MockingBird Host operate its core
product locally, using already-packaged production model assets, with
internet access denied? See the governing instruction for the full brief;
this report follows its required structure.

## Identity

- **Starting HEAD:** `9ef0b17` (branch `main`) -- the reconciliation commit
  that (prematurely, per this milestone's own governing brief) marked Lane N
  "closed" at the end of Local Only / Privacy Closure v1. No production code
  differs from `81dec47` (that milestone's own implementation commit);
  `9ef0b17` is documentation-only.
- **Schema:** `v58`, unchanged by this milestone -- zero production code
  changed (see "Defects," below).
- **Implementation/reconciliation HEAD:** unchanged from starting HEAD --
  this milestone added one new file (this report) and zero test/production
  changes; see "Validation" for why no new regression coverage was needed.
- **Windows version:** Windows 10 Pro, `10.0.19045` (native, real hardware --
  not a VM/container claiming to be Windows).
- **GPU:** NVIDIA GeForce RTX 4060 Ti, driver `610.62`, real passthrough
  (confirmed via native `nvidia-smi.exe`).
- **Packaged runtime identity:** embeddable CPython `3.12.7`; ONNX Runtime
  GPU `1.28.0` with the accepted CUDA13/cuDNN9 wheel set; BioCLIP dependency
  closure (`torch 2.11.0+cpu`, `open_clip_torch 3.3.0`, `huggingface_hub
  1.27.0`).
- **Packaged model paths:** MDv5a ONNX at
  `<release>\python\site-packages\mockingbird\observation_runtime\
  md-v5a-0.1-raw-fixed-1280.onnx` (+ `provider-config.json`/
  `model-bundle.json`); BioCLIP-2 at `<release>\python\site-packages\
  mockingbird\bioclip_runtime\` (model weights, labels, precomputed
  embedding cache) -- both packaged *inside* the release tree by
  `scripts/build_local_product.py`, not referenced externally.
- **Frontend build identity:** freshly built this session (`tsc --noEmit &&
  vite build`, no `--skip-frontend-build` path exists in
  `scripts/deploy_windows_dev.py`, so every deploy rebuilds from current
  source) -- entry bundle `assets/index-DahCb4EC.js` (222,099 bytes).
- **Live instance identity (via `GET /api/product/instance` on the
  disposable instance):** `instance_id=e0d10f027805370ab68f713b76d3222a`,
  `git_commit=9ef0b17eca508ae7c6f2c9ae3a49dc9c9b88cc70` (exact match to
  starting HEAD), `build_id=a36c09a1d4a7bbe8`.
- **Push state:** local only, not pushed (unchanged).

## Prior gap

Local Only / Privacy Closure v1 (2026-08-28/29) proved the Local Only
contract for real, at classification B, via a genuine OS-level
network-denial namespace (`unshare --net`) -- but ran the **Linux/WSL dev
checkout**, not the packaged native-Windows artifact, and exercised the
**model-assets-absent** path (no `MOCKINGBIRD_*_MODEL_PATH` set), not
assets-present. Its own reconciliation commit (`9ef0b17`) nonetheless
recorded Lane N as "closed" -- ChatGPT acceptance review of that same
report did **not** accept that as a full closure, precisely because those
two dimensions remained materially unverified. This milestone exists to
close exactly that gap. The starting-state check at the top of this
session confirmed the discrepancy is real (the file's own text says
"closed" while its cited reasoning matches "near closure, two material
proofs remain") and proceeded on the governing brief's own resolution of
it, per its own explicit instruction, rather than treating it as a
stop-and-report contradiction.

## Worktree safety

Confirmed at session start and re-confirmed at session end: the seven
preserved untracked detector files are present and byte-identical
(SHA-256, both checkpoints) --
`docs/wildlife-detector-training-contract.md.orig`,
`scripts/evaluate_small_bird_detector.py`,
`scripts/materialize_wildlife_stage2.py.orig`,
`scripts/train_wildlife_stage2_rfdetr.py.orig`,
`src/mockingbird/detectors/small_bird_benchmark.py`,
`src/mockingbird/training/wildlife.py.orig`,
`tests/test_small_bird_benchmark.py`. `git status`/`git diff --stat`
identical before and after (only the same eight pre-existing untracked
entries, zero tracked-file changes prior to this report). Three other
Claude Code processes share this machine (`ps`/`ListAgents`), but none had
touched any file in this worktree in the preceding 60+ minutes and none
did so during this session (re-confirmed via the identical hash/git-status
checkpoints); this session was the only writer.

## Packaged runtime

**Build/deploy path.** Used the accepted native-Windows packaging/
deployment path unmodified: `scripts/deploy_windows_dev.py` (itself a thin
Windows-materialization layer over `scripts/build_local_product.py`'s real
release-packaging logic -- "never duplicate packaging logic," confirmed by
reading both files). Deployed to a **fresh, disposable** `--dev-root`
(`MockingBirdLocalOnlyAcceptanceV1Test`), never the operator's long-lived
shared `MockingBirdDev` instance -- matching this project's own standing
policy (do not touch a real dev identity for ordinary acceptance work) and
exact precedent (Non-Interactive Field Acceptance Authentication & Session
Access v1 used the identical isolated-`--dev-root` pattern). Built with
**no skip flags** (`--skip-gpu-runtime`/`--skip-bioclip-runtime` both
omitted), so the release genuinely contains: packaged frontend (freshly
built), the full CUDA/cuDNN ONNX Runtime GPU dependency closure, the full
BioCLIP/torch dependency closure, the packaged MDv5a ONNX model bundle, and
the packaged BioCLIP-2 model bundle -- release-shaped in every dimension
the brief names. Because `MockingBirdDev`'s own default root was already
running (a leftover from the prior session, commit `9ef0b17`, pid `50868`),
it was stopped first (confirmed via `Get-Process -Id ... | Select Path`
before touching it) so the disposable instance could bind the packaged
launcher's hardcoded `127.0.0.1:8000`, then **fully restored** afterward
(see "Cleanup," below).

**Environment-contamination finding (methodology, not a product defect).**
This Windows dev machine carries persistent **User-level** environment
variables from earlier, unrelated milestones' own iterative dev work:
`MOCKINGBIRD_BIOCLIP_MODEL_PATH`/`_LABELS_PATH`/`_EMBEDDING_CACHE_PATH`
(pointing at a `\\wsl.localhost\Ubuntu\...` UNC path into this very dev
checkout) and `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`. A first pass at the
BioCLIP-2 proof (below) silently resolved through this override --
`resolve_bioclip_model_dir()` correctly honors an explicit environment
override ahead of the packaged-bundle default, exactly as documented, so
this is not a code defect; it just meant the *first* run proved "BioCLIP
loads from *a* local path" rather than "BioCLIP loads from *the packaged*
local path," which is what a real end-user's clean machine (with zero
`MOCKINGBIRD_*` variables ever set) would actually do. Caught by
inspecting the resolved `model_dir` in the proof's own JSON output before
accepting it as evidence. Fixed for every subsequent process this session
launched by clearing these variables (`Remove-Item Env:...`) at the start
of every launch/test script, for that process only -- the persistent
User-level values were never touched, and are unrelated to anything this
milestone's own governing brief authorizes changing. All results below are
from the corrected, packaged-path resolution.

## Network denial

**Mechanism.** No Administrator token is available in this interop session
(`([Security.Principal.WindowsPrincipal]...).IsInRole(Administrator)` ->
`False`, confirmed directly), so `New-NetFirewallRule`/`netsh`/a hosts-file
edit are not available -- the same class of environment-appropriate
substitution the prior milestone made for WSL (`unshare --net` in place of
a Windows firewall rule; here, the reverse). Built and used a small,
disposable **user-mode HTTP(S) egress-filtering proxy**
(`python.exe egress_filter_proxy.py`, stdlib only, ~190 lines): binds
`127.0.0.1:18080`; for every `CONNECT`/absolute-URI request it sees the
real destination host, resolves it, and either relays the connection
(loopback/RFC1918-private/link-local) or refuses it with `403` **before any
real socket to the destination is attempted** (public destinations); every
decision is logged with the resolved IP. The release was relaunched (via
the exact same `Start MockingBird.vbs` + `-PassThru`-and-poll pattern
`_launch_release_real` already uses, reused directly rather than
re-implemented) with `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` pointed at this
proxy and `NO_PROXY` empty -- `httpx`'s default `trust_env=True` picks these
up for every request MockingBird's own code makes.

**Honest scope.** This blocks HTTP(S) clients that cooperate with proxy
configuration (confirmed exclusively what MockingBird's own optional-
provider code uses -- `httpx`, per Local Only / Privacy Closure v1's own
static inventory, reconfirmed this session). It is not a kernel-level
block; a hypothetical raw-socket call that ignored `HTTP_PROXY` would not
be stopped by this mechanism alone. Two independent corroborations close
that gap for this specific acceptance: (1) real OS-level
`Get-NetTCPConnection` sampled *after* the full workflow sweep below shows
**zero** established connections from the MockingBird process to anything
but `127.0.0.1` (one internal loopback pair -- the isolated BioCLIP worker
subprocess's own IPC -- plus the bound listen socket); (2) the same proxy,
pointed at by a real headless Edge browser instance (`--proxy-server`),
independently caught and blocked *Edge's own* background calls
(`edge.microsoft.com`, `clients2.google.com`, `www.bing.com`,
`config.edge.skype.com`) during the browser-render check below -- live
proof the mechanism is a real, comprehensive intermediary, not one narrowly
tuned to only the destinations this milestone expected.

**Localhost/LAN preservation.** Proven live, not merely configured:
`Invoke-WebRequest` to `http://127.0.0.1:8000/api/product/health` through
the proxy returned `200` throughout; `CONNECT`/absolute-URI requests to the
project's real reference Camera Node (`192.168.1.112:8787`) were classified
`ALLOW` by the proxy and returned a real, live `200` JSON health payload
(`status: "available"`, `camera_count: 8`, self-test `passed`) -- LAN
reachability through the denial mechanism, not just before/after it.
`Test-NetConnection` direct (bypassing the proxy) to the same host also
succeeded, confirming the base LAN path itself was never at risk.

**No permanent change.** The proxy is a disposable process, started and
stopped within this session; no firewall rule, hosts entry, or persistent
environment variable was created (see "Cleanup").

## Core workflows

All 16 items exercised live against the disposable instance, internet
denied throughout, authenticated as the disposable local Administrator
(below) unless noted. All via real HTTP through the proxied environment
(`wintest.py`, a small `powershell.exe`/`Invoke-WebRequest`-backed driver
written this session, since direct WSL-to-Windows-bound-port loopback is
unreliable in this sandbox -- see the session's own memory on this).

| # | Workflow | Result |
|---|---|---|
| 1 | Product startup | `GET /api/product/health` -> `200`, `ready: true` |
| 2 | Local sign-in | Bootstrapped disposable Administrator (`POST /api/setup/administrator` -> `201`) + `POST /api/auth/sign-in` -> `200`, session cookie issued |
| 3 | Product health | `GET /api/product/health` -> `200` throughout, including after every blocked optional-provider attempt below |
| 4 | Streams/source listing | `GET /api/streams` -> `200`, 1 real seeded Stream (`stream-backyard-feeder`) |
| 5 | Today | `GET /api/dashboard/summary` -> `200`; `GET /api/place/environmental-context/today` -> `200` |
| 6 | Visit/history access (seeded/product-shaped data) | `GET /api/visits` -> `200`, 2 real seeded Visits (`bird`/`northern_cardinal` needs-review, `squirrel` already-reviewed); `GET /api/visits/{id}/detail` -> `200` |
| 7 | Review/correction path | `POST /api/review-labels` (confirm the cardinal guess) -> `201`, real `ReviewLabel` created; Visit detail re-fetch confirms `review_status: "reviewed"` immediately |
| 8 | Bird Log/history | `GET /api/bird-log/journal` -> `200`; `GET /api/bird-log/likely` -> `200` |
| 9 | Camera/Stream health | `GET /api/camera-health` -> `200`, real per-Stream state (`stopped`, `readiness_status: "demo"`) |
| 10 | Local environmental baseline | `GET /api/place/habitat-context` -> `200`; `GET /api/place/environmental-context/today` -> `200` (solar computed locally; weather correctly degraded -- see "Optional integrations") |
| 11 | Storage health | `GET /api/settings/local-data` -> `200` |
| 12 | Backup/status | `GET /api/settings/backups` -> `200`; **real backup created** `POST /api/settings/backups` -> `201`, `verification_status: "verified"`, archive confirmed on local disk at `userdata\data\backups\<id>.mbbackup` |
| 13 | Retention/status | `GET /api/settings/storage-retention/summary` -> `200` |
| 14 | MDv5a local inference | See "Model locality," below -- proven at the production code path, not merely a status flag |
| 15 | BioCLIP-2 local assistance/abstention path | See "Model locality," below |
| 16 | Frontend document and JS assets | `GET /` -> `200`; real hashed asset `GET /assets/index-DahCb4EC.js` -> `200`, 222,089 bytes; real browser render (see "Frontend") |

Host<->Camera Node communication while internet was denied: proven at the
network layer (LAN-preservation check above, a real `200` JSON response
from the actual reference Node). A full pairing/streaming integration onto
this disposable instance was deliberately not attempted -- pairing is
stateful on the Node side and this milestone's own scope lock (no new
acceptance infrastructure, no live Gate A measurement) does not call for
touching the one real Node's pairing state for a throwaway instance.

## Model locality

**MDv5a.** Wrote a standalone script that replicates the exact production
wiring `main.py`'s own Observation-session startup uses --
`FrameDrivenProviderConfiguration.load(engine_runtime.
resolve_provider_config_path())` -> `OnnxModelBundle.load(...)` (independent
SHA-256 re-verification against the accepted provenance) ->
`OnnxCudaObservationProvider(bundle=...).load()` (real ONNX Runtime CUDA
session creation) -- run via the release's own packaged `python.exe`, no
mocking. Result, assets-present/pre-denial and again offline/post-denial
(byte-identical): `bundle_model_fingerprint_sha256 =
b03ef7968a54be1ae15e6987d520be0fa3cd71d8d229ec3aeb0bf0faa710abbc` and
`bundle_source_model_fingerprint_sha256 =
fe3e90e4b1955821ab7c1f88b446dc0c8cb25e109fdd1872916a55305294a5ef` (both
exact matches to this project's own accepted provenance record);
`score_threshold: 0.1` (the accepted production threshold);
`load_succeeded: true`; `selected_execution_providers: ["CUDAExecutionProvider",
"CPUExecutionProvider"]` (real GPU execution, not a silent CPU fallback --
the loader raises `onnx_cuda_no_fallback` otherwise); resolved entirely
from `<release>\...\observation_runtime\` and the packaged `models\<hash>\`
cache tier, never a `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH` override, never a
network path. **Proxy log shows zero entries from either run** -- no
download, no HF/network fallback was attempted, not merely "none was
needed."

**BioCLIP-2.** Same technique, one level up: a standalone script running
`run_bioclip_on_image(image, config, top_k=3)` -- a real forward pass
through the actual isolated-worker-subprocess architecture, not the deploy
tool's own deliberately light `get_bioclip_status()` (import + config
check only, no model load, by explicit design "this milestone explicitly
does not need a full ~1.6 GB inference on every deploy" -- this milestone
does). On a synthetic in-memory RGB image: real, plausible-shaped output
(`Tufted Titmouse 60.3%`, `Gray Catbird 14.7%`, `Brown Thrasher 12.5%`),
`model_weights_verified: true`, real timing (`model_load_ms: 3141`,
`inference_ms: 547`), resolved from `<release>\...\bioclip_runtime\`
(packaged path, after the environment-contamination fix above) both before
and after network denial, byte-identical model/labels/embedding-cache
SHA-256 both times. **Proxy log shows zero entries from either run.**

Together: production MDv5a and BioCLIP-2 both genuinely initialize and run
real inference from packaged local assets, before *and* after internet
denial, with independently-verified zero outbound network activity --
directly satisfying the brief's explicit instruction not to substitute a
status flag for this proof.

## Frontend

**Real browser render.** Headless Edge (`msedge.exe --headless
--proxy-server=127.0.0.1:18080 --screenshot=...`, real native Windows
browser, same egress-filtering proxy as the server -- so an external
font/CDN/analytics fetch would be refused exactly like the app's own
optional-provider calls) against `http://127.0.0.1:8000/`, internet
denied. Result: a fully, correctly rendered "Welcome to MockingBird" setup
page -- proper typography (no fallback-serif "missing font" look), correct
layout/colors/button styling, real product copy ("Your video and data stay
on this device," "Nothing is uploaded or shared automatically"). No blank
page, no broken asset icons, no console-visible load failure. (This
screenshot is the unauthenticated app shell -- a fresh Edge profile has no
session cookie; the authenticated product surfaces above were proven at
the HTTP/API layer instead, not by a logged-in screenshot, stated plainly
rather than overclaimed.)

**External-runtime-dependency result.** Re-scanned the actual freshly-built
`web/dist/assets/*.js` this session produced (not reusing the prior
milestone's older finding): the same three harmless external-origin
strings as before (a React error-decoder URL, the Open-Meteo attribution
link's own text, a Camera Node LAN-address placeholder), plus one SVG XML
namespace URI (`http://www.w3.org`, inert) -- zero of the four are runtime
fetch targets. The real browser render corroborates this directly: nothing
the page itself needed was blocked by the proxy (only Edge's own unrelated
background telemetry was).

## Outbound traffic

Real, observed evidence (not code inspection alone), classified per the
brief's own categories:

| Destination | Classification | Evidence |
|---|---|---|
| `127.0.0.1:8000`, `127.0.0.1:<ephemeral>` (BioCLIP worker IPC) | Localhost | Real `200` responses throughout; final `Get-NetTCPConnection` snapshot shows only these, owned by the MockingBird PID |
| `192.168.1.112:8787` (real reference Camera Node) | LAN | Real `200` JSON health response, proxied |
| `api.open-meteo.com` (188.40.99.226), `api.inaturalist.org` (13.66.155.195) | Optional external provider | 6 real `CONNECT` attempts total across the drills below, **every one refused** by the proxy before connecting; DNS resolution itself still worked (proving these are genuine live call sites, not stubs) |
| `edge.microsoft.com`, `clients2.google.com`, `www.bing.com`, `config.edge.skype.com` | Unexpected, but **not MockingBird** | Edge browser's own background/update/telemetry traffic during the render check, correctly excluded from the MockingBird accounting per the brief's own instruction not to attribute OS/app background traffic to the product under test |
| Anything else | None observed | Final process-scoped `Get-NetTCPConnection` snapshot (after the full workflow sweep) shows nothing else |

> With optional integrations enabled and forced unreachable, ordinary
> packaged MockingBird runtime attempted exactly the two known optional
> destinations, zero times more than the number of user-triggered
> requests (no retry storm), and required no internet connection for any
> core workflow.

## Optional integrations

**Weather (Open-Meteo).** Enabled (`PUT /api/settings/environmental-
context`, `weather_enabled: true`) then forced unreachable. `GET
/api/place/environmental-context/today` -> `200` throughout (5 rapid
repeats, 39.5-54.0 ms, no growth), `weather.status: "unavailable"`, solar/
daylight fields still correctly computed locally. `/api/product/health`
stayed `ready: true`. Proxy log: exactly one `BLOCK CONNECT
api.open-meteo.com` per app-level call (6 calls -> 6 blocks) -- no retry
storm.

**iNaturalist taxonomy lookup.** `POST /api/ecological/eligibility-preview`
(`destination: "inaturalist"`) against the two real seeded Visits, forced
unreachable -> `200`, both items degraded to `needs_input`/
`taxonomy_mapping_unresolved` rather than erroring; `eligible_count: 0`,
`needs_input_count: 2`. `/api/product/health` unaffected.

No unbounded logging observed (the proxy's own log, the only place these
attempts are newly recorded, stayed at exactly one line per real attempt).

## Authentication

Disposable local identity only, exactly per the governing brief's own
constraint: bootstrapped one Administrator
(`local-only-acceptance-admin`) via the standard `POST
/api/setup/administrator` first-run flow, on the fresh disposable instance
described above. No operator credentials were requested, stored, or used.
No new auth mechanism, principal type, token, or bypass was created -- the
recently-frozen Field Acceptance Operator mechanism was not touched. The
disposable Administrator account was destroyed along with the entire
disposable instance at cleanup.

## Sensitive data

Concise, as instructed -- no giant privacy audit. All observed local-only,
consistent with Local Only / Privacy Closure v1's own established
findings, re-confirmed rather than re-derived from scratch this session:
camera evidence and the review/correction history created this session
(the demo Visit's confirmed ReviewLabel) live in the local SQLite database
under the disposable `userdata\` tree; the real local backup this session
created landed on local disk only; Place coordinates entered for the
weather drill (rounded to ~11 km per the existing contract) were sent
nowhere, since the one live call attempt was blocked before it left the
process; local identity/session state (the disposable Administrator, its
session cookie) never left the Host; no Camera Node was paired to this
disposable instance, so there was no pairing credential to observe this
session (see "Core workflows" for why); no acoustic data path was
exercised (out of this milestone's minimum-workflow list). No automatic
external transmission of any of the above was observed.

## Camera credential storage

**Actual implementation.** Camera/RTSP/ONVIF credentials (the
username/password used to connect to an actual IP camera, distinct from
Camera Node pairing, which is hash-only) are stored **plaintext**,
serialized via a plain `json.dumps(...)` into
`source_provider_configurations.config_json`
(`product_repository.py:12023`). Independently confirmed by a direct grep
of `src/mockingbird/` for any encryption library usage (`cryptography`,
`Fernet`, `AES`, or any `encrypt_credential`/`decrypt_credential` helper):
**zero hits anywhere in the codebase.**

**Contract comparison.** No document anywhere in this repository promises
encrypted-at-rest camera credentials -- confirmed by a full read of
`docs/product-doctrine.md` and `docs/roadmap.md` (neither makes any such
claim) plus three independent, explicit, already-existing statements of
the actual plaintext posture: `docs/local-identity-multi-user-contract.md:
569` ("Camera/RTSP/ONVIF credentials remain stored plaintext at rest,
exactly as before this milestone... user password hashes are the first
genuinely hashed secret in this schema"); `docs/release-execution-
state.md:2117-2118` ("Do not claim encrypted camera/RTSP/ONVIF credentials
at rest unless current code proves it" -- a standing caution against
*overclaiming* encryption, not a promise that it exists);
`docs/non-interactive-field-acceptance-authentication-session-access-v1-
report.md:127-129` ("password hashes and session-token hashes only...
camera/RTSP/ONVIF credentials remain plaintext, unchanged, out of scope").

**Disposition: non-defect.** The repository does not promise encryption;
credentials are ordinary rows in the local SQLite database, protected by
the same local filesystem/OS-account boundary as every other local
product fact (the database file itself, the backup archives, the
review history) -- consistent with this product's existing, already-
accepted local-single-user-desktop-application security posture, not a
new requirement invented by this milestone. Documented here as the
brief's §14 requires; no code change made or proposed.

## Defects

**Zero reproduced Local Only/privacy defects found.** Every dimension the
acceptance bar names was checked with real, live evidence (not code
inspection alone): packaged native-Windows runtime, genuine internet
denial with independent OS-level corroboration, LAN/localhost preservation,
a real browser render, both production models proven initializing and
running real inference from packaged assets with zero network activity
both before and after denial, all 16 core workflows plus a real backup and
a real review correction, two live optional-provider-failure drills with
graceful degradation and no retry storm, and the camera-credential
question resolved to a documented non-defect. The one genuine methodology
issue found (persistent dev-machine environment variables silently
redirecting the *first* BioCLIP proof attempt to a non-packaged path) was
a fact about this specific reused Windows dev machine's own history, not
about the product; caught before being accepted as evidence, and worked
around without touching any persistent state. Because nothing was broken,
zero production code changed this milestone -- per the governing
instruction's own "fix only reproduced violations" constraint.

## Validation

**Tier 1/2/3:** not applicable in the traditional sense -- no production
code changed. Per the governing brief's own §17 ("If no production code
changes: do not run full Core merely for ceremony... use native-Windows
packaged runtime acceptance; browser acceptance; assets-present model
inference; outbound network evidence; focused existing Local Only
tests"), the acceptance evidence above **is** the validation. The one
already-existing, still-relevant automated check was re-run for a fast
sanity confirmation that this milestone's own live findings did not
silently regress the prior milestone's own hermetic proof:
`tests/test_local_only_privacy.py` -- **8/8 passed**, unchanged.

## Remaining privacy risks

Concrete only, none release-blocking:

1. **Camera/RTSP/ONVIF credentials remain plaintext at rest** -- a
   pre-existing, already-disclosed, non-defect posture (see "Camera
   credential storage," above), not newly found or newly risky, and not a
   Local Only violation (the credential never leaves the Host
   automatically either way).
2. **The egress-filtering-proxy denial mechanism is process-cooperative
   (`HTTP_PROXY`), not kernel-enforced**, because no Administrator token
   is available in this environment. Real OS-level connection accounting
   (zero established external connections observed) and the mechanism's
   own comprehensive catch of Edge's own unrelated background traffic
   both corroborate it worked completely for this acceptance run, but a
   literal kernel/firewall-level denial was not possible to obtain here.
3. **No live Camera Node pairing/streaming was exercised on the
   disposable instance** (deliberately, per this milestone's own scope
   lock against new acceptance infrastructure and live field measurement)
   -- Host<->Node communication under denial was proven at the network
   layer (a real, live, proxied `200` from the actual reference Node),
   not via a full paired-streaming session.
4. **Contribution privacy remains a non-question**, unchanged from the
   prior milestone's own finding -- no Derived Data Contribution pathway
   exists in the codebase to test.

## Decision

**Classification A.** Every condition the acceptance bar names is met with
real, live, native-Windows evidence: actual packaged runtime (not the
WSL/dev checkout); internet genuinely denied, with independent OS-level
corroboration beyond the mechanism's own log; localhost/LAN still usable,
proven with a real live Camera Node response; an actual browser render,
correctly styled, zero external dependency; MDv5a and BioCLIP-2 both
proven present and performing real local inference, before and after
denial, at the exact production code path, with independently-confirmed
zero network activity; all 16 core workflows usable, including a real
backup and a real review correction; optional integrations degrading
independently with no retry storm; no undisclosed automatic data
transmission; the one pre-existing open question (camera-credential
storage) resolved to a documented non-defect rather than left open; zero
release-blocking Local Only/privacy defect found or suspected. The one
honest caveat (item 2 above -- a process-level rather than kernel-level
denial mechanism, forced by this specific environment's lack of an
Administrator token) was investigated as thoroughly as the environment
allows and independently corroborated rather than merely asserted, so it
is disclosed as a remaining risk rather than treated as disqualifying.

## Lane N disposition

Both material gaps Local Only / Privacy Closure v1's own "Remaining risks"
named -- packaged native-Windows acceptance, and assets-present model
operation under internet denial -- are now closed with real evidence.
Lane N is genuinely, fully closed by this milestone (see
`docs/release-execution-state.md` for the reconciled record).
