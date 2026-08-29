# Local Only / Privacy Closure v1 -- Report

Bounded release-critical milestone proving MockingBird's core product works
Local Only, with no cloud account, contribution pathway, remote service,
analytics dependency, external telemetry requirement, or provider
credential required for ordinary use. See the governing instruction for
the full brief; this report follows its required structure.

## Starting state

- **Branch:** `main`
- **Accepted HEAD (start):** `7f98e43` -- Retention Correctness & Bounded
  Cleanup Closure v1's own reconciliation commit.
- **Schema:** `v58`, unchanged by this milestone (no production code
  changed at all -- see "Defects," below).
- **Latest accepted milestone (start):** Retention Correctness & Bounded
  Cleanup Closure v1, classification A.
- **Release doctrine:** one public launch (`docs/roadmap.md`,
  `docs/release-execution-state.md` §7). Lane N ("Privacy / Contribution")
  status at start: `PARTIAL -- LOCAL-ONLY RELEASE-CRITICAL`. Lane R (Gate
  A / Complete Field Acceptance) status at start: `NOT DONE --
  RELEASE-CRITICAL`, blocked on representative daylight conditions (the
  authentication half of that blocker was separately closed by
  Non-Interactive Field Acceptance Authentication & Session Access v1,
  2026-08-28).
- **Sequencing guard result:** confirmed Local Only / Privacy remains an
  open, release-critical, independent lane, and no higher-priority
  independent release-critical dependency blocks it (Lane G is materially
  closed; Lanes O/P are open *business/legal decisions*, not
  implementation blockers; nothing in `docs/release-execution-state.md`
  §6 makes Lane N depend on Lane R or vice versa). Proceeded per the
  governing instruction's own premise.
- **Worktree safety:** confirmed this session was the only writer in
  `/home/zkelder/projects/mockingbird-active` (`ps`/`lsof` showed only this
  session's own process tree; the six sibling worktrees listed by `git
  worktree list` are separate directories, not this one). The seven
  preserved untracked files were hashed at the start of this session and
  re-hashed at the end -- byte-identical throughout, untouched.

## Local Only contract

Derived from `docs/product-doctrine.md` ("Privacy and portability," "Two
scorecards," "Deployment and organization doctrine") and
`docs/release-execution-state.md` (Lane N, §4 "Product/release
guardrails," §12 "Security / release questions") plus the accepted
implementation this milestone investigated. **Core Local Only** means a
fresh installation, with no cloud account, no weather/biodiversity
provider credential, and no contribution configuration, can still:

1. bootstrap a local Administrator and sign in (local session, no hosted
   identity);
2. add/configure a local Camera Node or supported local Source;
3. observe, detect wildlife, and create Visits (local MDv5a ONNX
   detection, local tracking/assembly);
4. preserve evidence (local media filesystem, local SQLite);
5. run local BioCLIP-2 species assistance and abstain honestly when
   uncertain;
6. review/correct truth (local `ReviewLabel` writes);
7. browse Today, Visit detail, and history/Bird Log;
8. use multi-camera behavior;
9. view health/Doctor (`/api/product/health`, `/api/settings/local-data`);
10. back up and restore, entirely on local disk;
11. run retention/cleanup;
12. install/upgrade/recover a Camera Node;
13. optionally run local acoustics (BirdNET) once its assets are
    installed.

**Explicitly optional, network-dependent, and correctly *not* release
blockers merely for needing a network:** weather enrichment (Open-Meteo,
off by default); iNaturalist taxonomy lookup and CSV export workflow;
Darwin Core / Camtrap DP export (pure local file generation, no network at
all); external-URL still-image Source preview (arbitrary user-supplied
URL, explicit per-action only). Each must fail independently without
degrading the thirteen core items above.

## Network dependency inventory

Performed via two independent, bounded static investigations (backend:
`src/mockingbird/`, `src/mockingbird_node/`, all of `scripts/`,
`pyproject.toml`/`uv.lock`; frontend: `web/src/`, `web/dist/` compiled
output, `package.json`) plus this session's own follow-up verification.

### Required local/core -- confirmed no network path

Solar/day-night context (`environment/solar_context.py`, pure `astral`
math); MDv5a ONNX detection (`detectors/local_image_detector.py`,
`detectors/megadetector_adapter.py` -- SHA-256-verified local `.pt`/ONNX
load, `force_model_download=False` hardcoded); BioCLIP-2
(`species/bioclip_adapter.py` -- `local-dir:` model load, plus explicit
`HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1`/`HF_DATASETS_OFFLINE=1`
defense-in-depth before the isolated inference subprocess runs); BirdNET
(`species/birdnet_adapter.py` -- weights bundled inside `birdnetlib`, no
runtime download); the ONNX Runtime CUDA provider; Camera Node local
`/dev/video*` capture and its `sd_notify` watchdog (Unix domain socket,
not network); app startup/lifespan code (`api/main.py` `_app_lifespan`
-- monitoring supervisor, retention, acoustic runtime, attention sync,
backlog consumption, all local DB/filesystem work, no phone-home/
update-check/license-check pattern anywhere in `src/` or `scripts/`).

### LAN-local -- expected, not a Local Only violation

Host&harr;Camera Node HTTP client (`source_providers/camera_node.py`);
ONVIF SOAP client + discovery, which hard-rejects any public IP/DNS name
via an explicit private-address allowlist (`onvif_client.py:_is_lan_host`);
RTSP ingestion via `ffmpeg` against a user-configured Source address (the
product's central function, not a discovery call). One deliberate nuance:
the Camera Node&rarr;Host transport-worker path (Remote/Intermittent-WAN
Transport Foundation v1) is explicitly designed to also work over a
non-LAN address the user paired -- still strictly Host&harr;self-owned-Node,
never a third party, and an already-accepted, already-documented feature
(After-release Lane B), not a fresh finding.

### Explicit optional provider

**Weather (Open-Meteo).** `environment/weather_provider.py`, called from
`ProductRepository.get_place_environmental_context_today`. Gated by
`EnvironmentalContextSettingsModel.weather_enabled`, `NOT NULL DEFAULT 0`
-- off by default at the schema level. Failure caught
(`WeatherProviderError`) and degrades to cached/stale/unavailable, never
raises. Sends only 4-decimal-rounded (~11 km) coordinates.

**iNaturalist taxonomy lookup.** `ecological/inaturalist_taxonomy.py`,
called from `ecological_eligibility_preview`/`prepare_ecological_
submissions`. Not gated by a persistent settings flag (unlike weather) --
gated by feature use: it only activates when a user works the iNaturalist
export workflow specifically (`destination == "inaturalist"`; eBird is
`offered=False` and never calls out at all). Failure caught
(`TaxonomyLookupError`) and degrades one record to `needs_input`, never
poisons the durable per-label cache, never raises. Sends only a species
-name text string. A passive read (`allow_live_taxonomy_lookup=False`)
never triggers a call at all.

**External-URL still-image preview.** `source_providers/external_url_
preview.py`. Deliberately allows public hosts (the user supplies an
arbitrary camera/image URL) but blocks loopback/multicast/link-local/
metadata-IP; triggered only by two explicit POST actions, never a
background job; every failure path returns a typed status, never raises.

### Installation/update only

`scripts/build_local_product.py` (embeddable-Python download,
`huggingface_hub` pinned for *build-time* BioCLIP dependency-closure
packaging only); `scripts/install_camera_node.py` (polls the
just-installed Node's own loopback health endpoint only); Windows
dev-deployment tooling (already-documented, dev-only).

### Development/test only

Field-acceptance/admin/maintenance CLIs (all talk to a running
MockingBird instance's own `--base-url`, default `127.0.0.1:8000`);
training-corpus downloaders and BioCLIP-candidate benchmark scripts (all
public-dataset/local-weights-path tooling, several referencing candidates
already rejected by Species Classification Re-evaluation & Promotion v2);
the seven preserved untracked detector-prototype files (re-confirmed this
session: zero network-pattern matches, hashes unchanged); a pytest-only
`TestClient` ASGI-transport patch in `api/main.py` gated by `"pytest" not
in sys.modules`, never live.

### Telemetry / analytics / crash reporting

**None found.** Full `pyproject.toml` dependency read plus a targeted
`uv.lock` scan for sentry/mixpanel/posthog/datadog/newrelic/amplitude/
segment/bugsnag/rollbar/honeycomb/opentelemetry/statsd found zero hits.
Frontend: zero hits across `package.json`/`package-lock.json`/`web/src`
for the same list plus logrocket/fullstory/hotjar/gtag/
google-analytics/googletagmanager/clarity/pendo. This is now a standing,
checked-in regression (`tests/test_local_only_privacy.py::
test_no_telemetry_or_analytics_dependency_declared`), not only a one-time
audit finding.

### Unexpected

None found requiring a code change. The two explicit-optional-provider
call sites above (iNaturalist taxonomy, external-URL preview) are working
exactly as designed -- named explicitly here, per this milestone's own
instruction, since a search for only a persistent "enabled" flag would
undercount them.

## Runtime acceptance

**Network condition.** A real, OS-level, unprivileged network namespace
(`unshare --net --map-root-user`) with loopback brought up and every other
interface absent -- the strongest practical form of "no internet route at
all," not a firewall rule that could have a gap. Verified directly: `curl`
to `api.open-meteo.com`/`huggingface.co`/`pypi.org`/`api.inaturalist.org`
all failed with `exit=6` (could not resolve host / no route) before,
during, and after every run; loopback connections succeeded normally
(confirmed via a real "connection refused" on an unbound port, proving
loopback routing itself worked, not merely "everything fails the same
way").

**Instance.** A fresh, disposable `MOCKINGBIRD_HOME` (never the operator's
real deployment), the real `.venv/bin/python -m mockingbird` entry point
(`--host 127.0.0.1 --skip-frontend-build`, the already-built `web/dist`),
run entirely inside the isolated namespace. Bootstrapped via the real
`POST /api/setup/administrator` + `POST /api/auth/sign-in` flow. The
database auto-seeds a demo Source/Stream/Visits/ReviewLabel
(`ProductRepository.seed_if_empty`, unconditional on a fresh database) --
this *is* "existing product-shaped data," reused rather than fabricated,
per the governing instruction's own allowance for a nighttime session.

**Workflows exercised (all inside the network-denied namespace, all real
HTTP against the real running app, zero mocking):**

- setup/bootstrap/sign-in;
- 22 core authenticated `GET` routes spanning health, sources, streams,
  visits, events, review queue, Bird Log, Dashboard, model
  adapters/readiness, BirdNET status, Place habitat/environmental-context/
  biodiversity, settings (backups, storage-retention, local-data,
  installation), ecological destinations, analytics, alerts, notification
  preferences -- **22/22 returned `200`, 11-178 ms each**;
  the frontend document (`GET /`, `200`) and its first referenced hashed
  JS asset (`200`);
- `POST`/`POST` Observation start/stop against the seeded demo Stream --
  `200`/`200`, with an honest, non-crashing message ("This stream uses the
  local demo panel; no real video playback is connected yet.") rather than
  a fabricated success or an unhandled error;
- a real Visit detail fetch (`200`);
- **weather explicitly enabled** (`PUT /api/settings/environmental
  -context`) then read via the real endpoint
  (`GET /api/place/environmental-context/today`, `200`, 127 ms first call,
  15-19 ms across five rapid repeats -- no growing latency, no retry
  storm) and via a real downstream composed surface
  (`GET /api/place/biodiversity-summary`, `200`);
- a real iNaturalist eligibility-preview call against the seeded,
  already-reviewed squirrel Visit (`200`, 38 ms) -- degraded the one
  affected item to `needs_input`/`taxonomy_mapping_unresolved` rather than
  erroring;
- a real local backup creation (`POST /api/settings/backups`, `201`,
  87 ms, `verification_status: "verified"`) -- the archive was written to
  `<MOCKINGBIRD_HOME>/data/backups/<id>.mbbackup`, confirmed on local disk;
- re-confirmed internet still unreachable mid-session and at the end.

**Result.** Every workflow above completed successfully with zero outbound
connection attempts required. The server's own access log (uvicorn) shows
only the expected local requests, no exceptions, no retries, no timeouts,
across both full runs (44 and 19 log lines respectively). Clean startup
(ready in 6 s) and clean shutdown in both runs.

## Observed outbound traffic

Classified by real OS-level exit code, not code inspection alone:

| Destination | Result | Classification |
|---|---|---|
| `api.open-meteo.com`, `huggingface.co`, `pypi.org`, `api.inaturalist.org` | `curl` exit 6 (name resolution / no route) at every check point | Genuinely unreachable -- proves no internet route existed, not merely that these hosts happened to be down |
| `127.0.0.1:<app port>` | Real HTTP responses throughout | Loopback -- the product's own bound port |
| `192.168.1.112:8787` (the project's real reference Camera Node) | `TCP connect succeeded` (checked live, separately, *outside* the denied namespace, immediately after the acceptance runs) | LAN -- confirms this same sandbox that just proved zero internet dependency can still reach real LAN hardware when not deliberately isolated, directly evidencing the offline-vs-LAN-local distinction §7 requires, rather than only asserting it |

> With optional integrations unconfigured, ordinary MockingBird runtime
> produced no required internet connection -- and, separately, with
> weather and iNaturalist taxonomy lookup both deliberately enabled and
> forced unreachable, every affected response still degraded gracefully
> rather than requiring one.

No unrelated OS/runtime background traffic was observed (the namespace has
no interface for it to use).

## Models

Local inference stays local. MDv5a ONNX and BioCLIP-2 load exclusively
from local paths/directories (`MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`,
`MOCKINGBIRD_BIOCLIP_MODEL_PATH`, etc.), with an explicit checksum gate on
the MegaDetector artifact and `HF_HUB_OFFLINE` defense-in-depth on
BioCLIP. On this session's disposable instance, none of those env vars
were set (a fresh instance with no assets installed), and
`/api/model-readiness/summary` reported every adapter honestly as
`status: "setup_required"`, `can_run: false`, with a local-file-path
setup hint -- **not** an attempted download, **not** an error, **not** a
degraded "unhealthy" reading. This exercises the "assets absent" path
directly; the complementary "assets present, zero network" path is not
freshly re-proven by this session (see "Remaining risks," below) but is
corroborated by substantial prior accepted-milestone evidence (BioCLIP
Status / Review Queue Performance v1, Species Suggestion v1.2, and every
Camera Node/field-acceptance milestone that ran real MDv5+BioCLIP
inference on the real Windows/GPU host without any reported network
dependency).

## Optional integrations

Behavior when absent/unreachable, all live-proven this session (not
merely code-read): weather absent &rarr; `configured: false`, no attempt;
weather enabled + unreachable &rarr; graceful `unavailable`/stale
degradation, bounded latency, no retry-storm growth across 5 rapid
repeats; iNaturalist taxonomy unreachable &rarr; one item marked
`needs_input`, `200` overall, cache never poisoned; acoustic (BirdNET) not
configured &rarr; `/api/product/health.acoustic.status ==
"not_configured"`, explicit "visual observation is unaffected" text,
overall `ready: true` unaffected. No core route in the 22-endpoint sweep
above failed, slowed materially, or mislabeled itself unhealthy because an
optional integration was absent.

## Contribution

Traced every "contribution" occurrence in `src/mockingbird/`. **No
Derived Data Contribution or media-contribution upload pathway is
implemented in the codebase at all** -- every real code hit is an
unrelated internal concept (`_retract_scene_confusor_region_contribution`,
tracking how much a given `ReviewLabel` contributes to a per-Stream
scene-confusor region's own statistics; a Visit's contribution to
representative-evidence *ranking*), not a cloud-upload feature. This
matches Lane N's own governing text exactly ("Doctrine exists. Do not
assume operational implementation or cloud backend exists"). Because no
such pathway exists, there is no default-upload behavior to audit, and
nothing for a user to opt into or out of yet -- the doctrinal requirement
("no default upload... no media leaves the Host without explicit
supported user action") is presently satisfied because the capability it
would govern does not exist, not because an implemented opt-in flow was
inspected and found correct. This distinction is stated plainly rather
than overclaimed.

## Frontend

**No mandatory external runtime asset dependency.** Independently
confirmed at the source level (`web/index.html`, `vite.config.ts`,
`styles.css`, every `.tsx`/`.ts` file: zero external `<link>`/`<script
src>`, zero `@font-face`/Google-Fonts import, zero analytics/telemetry SDK
import, exactly 3 `fetch()` call sites -- all built from a same-origin
`API_BASE_URL`, `credentials: "same-origin"`) **and** independently
re-confirmed against the real *compiled* `web/dist/assets/*.js` output:
only 3 external-origin string literals exist in the entire shipped bundle
(a React error-decoder URL never fetched, the Open-Meteo attribution
link's own text, and a Camera Node LAN-address placeholder string) --
zero of the three are runtime fetch targets. The service worker
(`web/public/sw.js`) caches only same-origin, content-hashed `/assets/*`
responses, never intercepts navigation/API/`index.html`, has no
background sync or push. This session's own runtime acceptance
independently confirms the served result: `GET /` and its first hashed JS
asset both returned `200` from the product's own port with zero external
requests possible. A live Playwright/browser render was not performed
this session (see "Remaining risks").

## Authentication

Confirmed local end to end, live, inside the network-denied namespace:
`POST /api/setup/administrator` (first-run bootstrap) &rarr;
`POST /api/auth/sign-in` &rarr; session-cookie-authenticated access to
every route in the 22-endpoint sweep. No hosted-identity call, no remote
token validation is possible in this code path (it cannot reach any
network at all in this run and every authenticated call still succeeded).
This reconfirms, rather than reopens, the already-accepted Local Identity
and Non-Interactive Field Acceptance Authentication milestones' own
findings -- no new authentication code was touched or needed to be.

## Sensitive data

Concise disposition, all local, none observed to transmit automatically:
camera imagery/evidence on the local media filesystem under
`MOCKINGBIRD_HOME` (confirmed via `/api/settings/local-data`: "Imported
media stays local and is not analyzed or transcoded in this phase");
coarse Place location, rounded to ~11 km before persistence, sent
externally only if the user explicitly opts into weather; user identity/
session and camera credentials in the local SQLite database; Camera Node
pairing state local and hash-based (already-accepted prior milestones);
review/correction history local (`ReviewLabel` table), never leaves the
Host except through an explicit, user-initiated export (Darwin Core/
Camtrap DP/generic research export, or the iNaturalist CSV a user
downloads and uploads themselves). Camera/RTSP/ONVIF credential
at-rest encryption was not newly investigated -- `docs/release-execution
-state.md` §12 already carries the standing caution against claiming it
without direct code proof, and this milestone found no evidence bearing on
that question either way; it is not a Local Only violation regardless (the
credential still never leaves the Host automatically), so it is named
here as a pre-existing open question, not a new or reproduced defect.

## Defects

**Zero reproduced Local Only/privacy defects found.** This was a real,
bounded, multi-angle investigation (two independent static-inventory
passes, a live real-OS-level network-denial runtime acceptance covering
22 API routes plus the frontend document and a hashed asset, two
deliberate optional-provider-failure drills, a real local-backup
creation, and a fresh live LAN-reachability check) -- not a shallow pass
that simply found nothing to look at. Every dimension the governing
instruction named was checked; none produced a reproducible violation.
Per the milestone's own explicit instruction ("Fix only reproduced
violations... Do not invent speculative privacy improvements"), no
production code was changed.

## Validation

**Tier 1.** No defect fixes to validate (none found). Instead, per §25's
instruction to add bounded Local Only regression coverage, added
`tests/test_local_only_privacy.py` (8 new tests, converting this
session's live proof into a fast, hermetic, dependency-injected
regression -- `httpx.ASGITransport`, never a real socket; fake weather/
taxonomy requesters that always raise, proving the *unreachable* path
specifically). Self-verified, not merely written and trusted: one test
(`..._does_not_break_habitat_context`) was caught by its own `call_count`
assertion targeting the wrong endpoint (`/api/place/habitat-context`,
which does not call weather at all, rather than the real
`/api/place/environmental-context/today`) and corrected before being
counted as passing evidence -- exactly the class of hollow-test risk this
project's own established convention (`fake.calls`/`requested_urls`
tracking in `test_environmental_context.py`/`test_ecological_
interoperability_repository.py`) already guards against, now applied
here too. The telemetry-dependency trip-wire was RED-verified separately
(confirmed it does catch an injected `sentry-sdk` entry). All 8 pass;
`ruff check tests/test_local_only_privacy.py`: clean.

**Tier 2.** 374 passed, 1 skipped, 0 failed across the affected areas:
`test_local_only_privacy.py` (new), `test_environmental_context.py`,
`test_weather_provider.py`, `test_ecological_interoperability_
{repository,api,scenario}.py`, `test_inaturalist_taxonomy.py`,
`test_product_health.py`, `test_local_identity_multi_user.py`,
`test_camtrap_dp.py`, `test_research_export{,_api,_repository}.py`,
`test_dashboard_{observation_engine_truth,today}.py`,
`test_bioclip_adapter.py`, `test_birdnet_adapter.py`,
`test_megadetector_adapter.py`. Frontend production build not rebuilt
(zero `web/src/` changes; `web/dist/` is the same fresh build this
session's own runtime acceptance already served and verified). A full
Playwright e2e subset was deliberately not run this session -- see
"Remaining risks."

**Tier 3.** Not run. This milestone changed zero production code (see
"Defects," above) -- only one new, additive test file. Per §26's own
explicit guidance ("If the milestone is primarily acceptance/docs with
narrowly isolated fixes, do not run Tier 3 gratuitously"), a full
5000+-test Core run would validate nothing this milestone actually
touched; Tier 2's 374/0-failed sweep across every area this milestone's
own investigation and new test file actually exercise is the
proportionate bar, matching this project's own established precedent for
non-cross-cutting changes (Camera Node Upgrade & Compatibility Recovery
v1, Storage / Retention / Disk-Pressure & Recovery Closure v1 both made
the identical call for the identical reason).

## Remaining risks

Concrete, disclosed, none release-blocking on their own:

1. **This session's runtime acceptance ran the Linux/WSL dev checkout
   (`.venv/bin/python -m mockingbird`), not the packaged native-Windows
   artifact** (`dist/MockingBird-windows-x64.zip`) end users actually
   receive, and doctrine names native Windows the first end-user Host
   acceptance target. The network-dependency *logic* under test is
   ordinary, platform-independent Python (no code path branches on OS for
   any of the routes/providers exercised), so this is a real but narrow
   gap, not a reason to suspect a different result on Windows -- see
   "Decision," below.
2. **This session's model-locality check exercised the "assets absent"
   path** (a fresh instance with no `MOCKINGBIRD_*_MODEL_PATH` set),
   confirmed honest/non-networking there; it did not freshly re-prove
   "assets present + zero network" in this same denied-network run. That
   exact combination is corroborated by substantial prior accepted-
   milestone field evidence (see "Models," above) but was not
   independently re-verified by this session.
3. **No live Playwright/browser render was performed** this session.
   Static source review plus an independent grep of the real *compiled*
   bundle (only 3 harmless external-origin strings in the entire shipped
   JS, zero of them a fetch target) is strong evidence against a
   client-side "endless spinner," but a real rendered-page check was not
   additionally run.
4. **Camera/RTSP/ONVIF credential at-rest encryption** remains an
   unverified, pre-existing, already-flagged-in-governing-docs question
   (`docs/release-execution-state.md` §12) -- not newly found, not a Local
   Only violation regardless (nothing transmits the credential off the
   Host automatically), not investigated further per this milestone's own
   instruction not to reopen general secrets architecture absent a
   concrete defect.
5. **Contribution privacy is presently a non-question**, not a verified
   opt-in flow -- see "Contribution," above. The moment a real
   contribution/upload capability is built, it needs its own dedicated
   privacy verification; this report should not be cited as having
   already covered it.

## Decision

**Classification B.** Every functional dimension the acceptance bar
names -- no internet required for core flow, optional-integration failure
independence, local model inference, no undisclosed telemetry, no
mandatory external frontend asset, local authentication, zero known
release-blocking defect -- is satisfied with real, live, mostly
first-of-its-kind-for-this-project evidence (a genuine OS-level network
-denial acceptance, not a firewall rule with a possible gap or code
inspection alone). This is not forced to A because one material runtime-
acceptance dimension named in "Remaining risks" above -- packaged native
-Windows acceptance specifically, as distinct from dev-checkout acceptance
-- was not re-verified fresh by this session, matching the governing
instruction's own explicit B criterion. No known or suspected Local Only/
privacy defect remains; the gap is about which environment ran the proof,
not about any discovered or expected difference in behavior.

## Lane N disposition

The contract is proven (see "Local Only contract," above) and every
reproduced-defect requirement is vacuously satisfied (zero found). Per the
governing instruction's own §29 ("If the contract is proven and any
reproduced defects are fixed, Lane N may be reconciled to closed"), Lane N
is reconciled to **closed** in `docs/release-execution-state.md` -- this
milestone performed real, meaningful runtime Local Only acceptance (not
only static inspection), satisfying §29's own stated precondition for
closing it on that basis.
