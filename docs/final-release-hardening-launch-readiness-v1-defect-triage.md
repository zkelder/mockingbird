# Final Release Hardening & Launch Readiness v1 — Known Defect Triage

Companion to `docs/final-release-hardening-launch-readiness-v1-report.md`
§6. Compiled from a dedicated investigation agent's sweep of every accepted
milestone report since 2026-08-24, cross-checked by hand against current
source where a claim was checkable cheaply. Classified per the governing
milestone brief's five tiers: RELEASE BLOCKER, FIX NOW, ACCEPTED KNOWN
LIMITATION, TEST DEBT, DEFERRED. **RELEASE BLOCKER: none found. FIX NOW:
none taken this pass** — every candidate either (a) does not affect the
actual supported/shipped path, or (b) was already deliberately scoped out
by name in its own originating, dedicated milestone, and reopening it here
would be outside this milestone's own bounded packaging/release-hardening
focus without new evidence.

Two items were independently re-verified against current source and found
**already fixed** (not carried into this table as open): the Doctor
Storage false-`FAIL` on a fresh instance (`_interpret_storage`, fixed by
*Release Reliability & First-Run Recovery v1*), and "no documented stop
method yields a clean shutdown" (fixed by the new `POST
/api/product/shutdown` + "Shut Down MockingBird" UI control, same
milestone) — both confirmed present in
`src/mockingbird/diagnostics/doctor.py`/`api/main.py` respectively. One
memory note ("no login rate-limiting") was checked and found **stale** —
`LoginRateLimiter` exists and is wired into `authenticate_user` (*Login
Rate-Limiting & Authentication Abuse Resistance v1*, already accepted) —
not carried into this table.

## ACCEPTED KNOWN LIMITATION (disclosed, deliberate, not release-blocking)

- Ambiguous-boundary sustained/crowded Visit-recall limitation (Gate A's own accepted
  budget) — root-caused twice, omission-only, no further engineering fix justified.
- True capture-to-visible latency upper tail: qualitative only, not a fitted SLA (accepted
  as part of Gate A PASS / Lane R CLOSED).
- Person-associated false-Visit-rate genuinely unmeasured (n=0) under the current stack.
- Camera Node `rollback()` does not restore an already-changed systemd unit template, and
  has a narrower directory-swap crash-window gap.
- No orphan-media/no-DB-owner detection anywhere in the product (Lane M, low materiality).
- Doctor's `Application` check reads `WARN` ("The previous MockingBird run did not shut
  down cleanly") for the *entire* lifetime of any running instance, not merely a brief
  mid-shutdown window as its own originating reports characterized it — **reproduced live
  on the real built artifact this milestone** (two independent Doctor calls, both on a
  currently-healthy instance, both showed this WARN). Root cause, traced precisely this
  pass: `runtime.prepare_runtime_state` reads the marker file, computes whether the *prior*
  run was clean, and unconditionally overwrites it to `{"state": "starting"}` for the
  *current* run — but that computed prior-run verdict is used once for a startup console
  line and then discarded, never persisted anywhere (`app.state` included) for
  `doctor._peek_previous_shutdown_state` to read later. Doctor's own read-only peek at the
  marker file therefore cannot distinguish "a live, healthy instance is currently running"
  from "a process crashed while marked as running" — both read as the literal string
  `"starting"` — so the WARN fires for the ordinary case of "the app is open right now,"
  not only after a genuine crash. Not fixed this pass: the real fix (capturing the prior
  -run verdict at boot and threading it to the API-invoked Doctor handler via `app.state`,
  which only the API path — not the separate-process CLI form — could even use) touches the
  boot sequence, `doctor.py`, and `api/main.py` together and needs new test coverage; it is
  a real, well-scoped candidate for a small dedicated follow-up, not a one-line fix, and two
  dedicated prior milestones already looked at this exact symptom and deliberately deferred
  it. Recorded here with the precise mechanism (not previously identified this exactly) so a
  future pass does not have to re-diagnose it.
- Camera Node live hardware-health check degrades to `storage: None`/`hardware: None` for
  the real reference Pi specifically (its installed build predates those fields — a fact
  about that one device, not a defect).
- Host storage-tier thresholds reused for Camera Node, not independently re-derived for
  Pi-scale SD cards (disclosed reuse of an existing judgment call).
- Structural asymmetry: an already-resolved ambiguous-component member's veto reach has no
  time bound (proven not to change any recorded outcome; not live-reachable in real data).
- Corroboration-floor indistinguishability (structurally irreducible, expected).
- Crowded-feeder/NMS gap: a third simultaneous bird the detector itself never separately
  perceived (Gate A's own already-recorded open dimension).
- Gate B admission-precision residual: a confident background/empty-crop hit can still
  become an unlabeled false Visit (long-documented, repeatedly reconfirmed, partially but
  not fully closed by Identification Eligibility + Abstention v1).
- `pairing_state_path`'s own `Path.home()` fallback (Camera Node config) shares the same
  latent shape already fixed for `transport_spool_dir`/`transport_credential_state_path` in
  the same file — masked today only because the installer always sets the env var
  explicitly, so the supported install path is unaffected. Investigated this pass (see
  below); left unfixed deliberately, matching the originating milestone's own bounded scope.
- Counterfactual/rejected-evidence ledger exposes bounded Privacy-Zone activity metadata
  (never pixels) to diagnostic-API (Administrator) access — consistent with, and now
  cross-referenced from, this milestone's own SECURITY.md disclosure that Privacy Zones are
  trigger-level exclusion, not guaranteed pixel redaction.
- Support-bundle `--no-local-paths` does not scrub every embedded filesystem path (already
  honestly scoped in its own CLI help text and module docstring).
- `frame_driven_provider.py`'s center-point-only Privacy-Zone exclusion filter is weaker
  than the pixel-level masking it sits on top of (latent/theoretical, no live-impact
  evidence).

## DEFERRED (real, recorded, correctly out of this milestone's scope)

- BirdNET commercial-adjacent legal posture — no engineering action available; a standing
  legal-review question, not resolved by this or any code milestone.
- Public-repo hygiene beyond SECURITY.md/CONTRIBUTING.md/THIRD_PARTY_NOTICES.md (brand/
  trademark review, broader site polish) — explicitly non-release-critical; this milestone
  incidentally improved it (see the main report's §4) without treating it as required.
- Doctor has no "cleanup-outcome" signal; no single consolidated source-readiness page;
  Camera Node hardware-health facts are live-only, not durably persisted on the Host —
  each a legitimate future product/UX decision, not a defect.
- `field_acceptance_instance_lifecycle.py mark-archived --evidence-archive` Windows-path
  gap — internal field-acceptance tooling only, never shipped to an end user.
- No Playwright e2e spec for the "Shut Down MockingBird" control — a deliberate, already-
  made proportionality call by its own originating milestone; not reopened here.
- `notification-preferences.spec.ts` gap (Calm Attention/Notifications Place Story deep-
  link scoping) — Lane D territory, real but non-blocking.
- ~18.5-24GB of archived Windows dev-root disk space on the shared real-hardware test
  machine — pure test-infrastructure housekeeping, not part of the release artifact;
  opportunistically not touched this pass (out of scope, and destructive cleanup of shared
  test-machine state was not this milestone's mandate).
- Several Gate A "13-item" sub-dependencies never individually re-closed (a 3+-simultaneous-
  subject cohort; full convergence of the person-confound-free false-Visit rate to 3
  cohorts; a few specific untraced ledger records) — Gate A already PASSED with these
  named and disclosed; not reopened absent new field evidence.
- Two recent Place Intelligence capabilities (Year-over-Year Seasonality chief among them)
  proven only synthetically pending a real year of accumulated field history — a data-
  availability constraint, not an engineering gap.
- Multi-camera notification grouping — real enrichment opportunity, explicitly not
  release-critical.
- Camera Node's earliest camera-missing checks carry no `X-MockingBird-Node-Error` header;
  `_default_capture_profile_alignment`'s silent `not_checked` degrade; Doctor's
  `camera_node` check raising (not degrading) against a pre-schema-37 DB; three legacy
  field-acceptance dev-roots invisible to the lifecycle-manifest tool — each small, real,
  and explicitly scoped to a future, separately-authorized milestone by its own originating
  report.
- Three of four review-provenance endpoints keep a generic `except ValueError` fallback
  instead of the more precise handling one endpoint already has — minor, disclosed.
- `featureAssociationSentence` copy renders identically for `early_signal`/`comparable`
  maturity — a cosmetic Place Story wording nuance two prior dedicated product milestones
  already found and deliberately did not fix; not reopened here absent new evidence.
- `classifier_manifest_export_root` excluded from backup scope (low severity, regenerable
  export artifact); two free-text research-export fields flagged for a future contribution
  payload; full media-content-decode integrity checking not implemented (Doctor is stat-
  only); no periodic re-verification job for aging backups — each already disclosed in
  `appliance-storage-privacy-recovery-v1-contract.md` as a deliberate, bounded gap.
- `GET /api/observation-engine/status` naming/wiring mismatch (zero live user impact,
  frontend never calls it); `observation-onnx-cuda` extra missing a `sys_platform` marker
  (a developer-experience rough edge on non-Windows/non-x86_64 dev checkouts only) —
  confirmed non-release-blocking by their own originating closure report.
- Zone-polygon drawing has no keyboard equivalent (optional/advanced feature); a larger-
  than-previously-documented dead-CSS footprint; a narrow raw-exception-text edge case —
  all disclosed by the already-closed Whole-Product UI/Accessibility/Performance pass.
- General frontend structured-error-taxonomy sweep remains incomplete beyond backup/
  restore/storage.

## TEST DEBT (environment-sensitive flakes; do not re-bisect absent behavior change)

- `test_place_biodiversity_summary_repository.py` (a pair) — flaky, not always reproducing.
- `test_place_change_summary_repository.py::test_api_round_trip_exposes_change_detection_fields`
  — recurring, date-sensitive fixture flake.
- `test_transport_worker.py::test_sticky_diagnostic_set_on_protocol_incompatibility_and_cleared_on_next_success`
  — load-induced timing flake.
- `test_observation_camera_node_live.py` — single-run-only, non-reproducible flake.
- `test_camera_node_capture_contention.py::test_analysis_stream_disconnect_during_inflight_capture_releases_camera_lock`
  — concurrent-load timing flake.
- `reviewed-product-loop.spec.ts` (e2e) — root-caused as test-suite staleness (a hardcoded
  `productMode=true` targets permanently-unreachable legacy markup), not a live defect.
- Full-repo `ruff check .` (never wired into Fast/Core/Full/CI — confirmed by grep, no
  `ruff` invocation exists in any of those) surfaces 163 pre-existing findings across files
  untouched by any recent milestone, confirmed 100% pre-existing via `git stash` bisection
  against this milestone's own changes (0 introduced, 0 in any file this milestone touched).
  Every prior "ruff clean" claim in this project's history was scoped to the files that
  milestone touched, never a full-repo sweep — worth disclosing precisely so a future
  reader does not assume repo-wide ruff cleanliness that was never actually claimed.

## Investigated this pass, left unfixed (reasoning)

`pairing_state_path`'s `Path.home()` fallback (`src/mockingbird_node/config.py`) has an
already-proven fix pattern sitting a few lines away in the same function (the identical
class of defect was fixed for `transport_spool_dir`/`transport_credential_state_path` by
*Platform/Runtime Portability & Support Truth Closure v1*, which anchored both to
`pairing_state_path.parent` instead of a second independent `Path.home()`-based guess).
`pairing_state_path` itself, being the anchor, cannot use that same fix — it would need a
different bottom-of-chain default not yet designed or validated. The real, currently-
supported install path (`install_camera_node.py`) is unaffected: it always writes
`MOCKINGBIRD_NODE_PAIRING_STATE_PATH` explicitly, so this fallback is dead code on every
real device. Its own originating report already disclosed it as "a latent structural risk...
not fixed under this milestone's bounded scope." Absent a reproduction against a real,
supported launch path, or new evidence, inventing a new fallback design here risks a
regression in a real-hardware-validated component for a scenario the supported path never
exercises — left as an ACCEPTED KNOWN LIMITATION rather than fixed speculatively.
