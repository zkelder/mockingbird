# Public Product, Deployment & Support Closure v1 -- Audit and Closure Record

Date: 2026-10-03. Starting state: `main` at `28463ea`, schema `v62`, source
version `0.1.0`. Docs/public-surface milestone; no application code, schema,
packaging build, or version change.

## Contract

- **Phase:** pre-1.0 product completion; final planned pre-freeze docs and
  release-foundation milestone. Final 1.0 Hardening is **not** started.
- **Allowed surfaces:** README, `docs/**`, SECURITY/SUPPORT/CONTRIBUTING/
  THIRD_PARTY_NOTICES, `.github/ISSUE_TEMPLATE`, `pyproject.toml` comment and
  `description` metadata.
- **Non-goals:** deferred 1.0 capabilities, version bump, tag, push, new
  schema/providers/models, a website, telemetry.
- **Validation tier:** docs tier (links, stale-claim greps, notices tests,
  packaging-doc tests); no Core because no runtime behavior changed.

## Phase 1 audit -- surfaces and findings

| Surface | Finding | Disposition |
|---|---|---|
| `README.md` | 470-line developer/history document ("Current product checkpoint", Stage 3/4/5 replay, BioCLIP dev setup); framed as a source-checkout guide, no 1.0 support statement, no support/security/privacy entry. | Rewritten as the public overview; developer content moved verbatim to `docs/developer-setup.md`. |
| `docs/using-mockingbird.md` | Had its own support table (a second source of truth); no checksum step, no Releases source; BirdNET told users to run `pip install` from THIRD_PARTY_NOTICES, which a packaged user cannot do; "Windows 10/11 supported and validated" overstated Windows 11; support-bundle called "safe to share" though it includes local paths. | Support table replaced by pointer to the matrix; download/verify, data location, models sections added; BirdNET corrected; bundle wording corrected. |
| Support matrix | None canonical; claims spread across user guide, README, runtime-map, portability report. | `docs/support-matrix.md` created. |
| `THIRD_PARTY_NOTICES.md` | BirdNET extra shown as `pip install "mockingbird[classifier-birdnet]"` (implies a PyPI package that does not exist; not usable on the ZIP); NVIDIA notice left as "this milestone's report"; Open-Meteo/iNaturalist absent. | Corrected; open items made explicit; Open-Meteo CC BY 4.0 and iNaturalist added. |
| `SECURITY.md` | "no track record of tagged releases… most recent tagged release" language; no link to posture/matrix. | Updated for 1.0; links added; unsigned release noted. |
| Privacy/security | No single public explanation of Local Only, outbound requests, remote access, credentials. Support bundle path disclosure undocumented publicly. | `docs/privacy-and-security.md` created from the Local-Only closure report and code. |
| Support path | No troubleshooting page, SUPPORT.md or issue templates. | `docs/troubleshooting.md`, `SUPPORT.md`, `.github/ISSUE_TEMPLATE/*` added. |
| Version language | `pyproject.toml` comment said the repo is "executing the MockingBird v0.1 public release"; description called it an "outdoor video intelligence API". Roadmap/release-state already say 1.0. | Comment and description corrected; no version bump. |
| `CONTRIBUTING.md` | Pointed to README sections that moved. | Repointed. |
| Camera Node guide | Reviewed; consistent with the matrix (Pi 4 reference). | Unchanged. |
| `README-FIRST.txt` (build script) | Reviewed; accurate (local data, network use, FFmpeg/BirdNET exclusions, uninstall). | Unchanged; no package rebuild needed. |
| LICENSE / `THIRD_PARTY_NOTICES.md` | MIT holder "MockingBird contributors"; tests lock the MDv5a/BioCLIP/ffmpeg/BirdNET facts. | Held. |
| Screenshots/assets | None committed besides PWA icons; no public site exists. | No action; none invented. |
| Public-site/GitHub metadata | Only CI workflow existed. | Issue templates added; no site created. |
| `src/mockingbird/api/main.py:750`, `docs/model-adapter-guardrails.md:9` | Still describe the product as "outdoor video intelligence". | Left: application code is out of scope; the guardrails doc is internal. Logged as a minor follow-up. |

## Deferred-capability references

No public document claims sensors, MQTT, multi-site, cloud relay, native mobile,
background push, packaged Linux Host or new providers. The support matrix lists
each as not part of 1.0.

## Unresolved publication dependencies

See [owner-release-checklist.md](owner-release-checklist.md): version bump,
push, final artifacts, Releases page, tag, private-vulnerability-reporting
enablement, NVIDIA notice confirmation, signing decision, BirdNET legal
stance. Windows 11 and driver minimums remain unvalidated by design.
