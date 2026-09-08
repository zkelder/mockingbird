# External Pre-Release Acceptance (Gate G) Plan v1

**Status: PLAN ONLY. Gate G is not started.** This document is the
concrete cohort/hardware/findings-intake plan named as the third and
final entry precondition for Gate G in *Global Remaining
Product-Development & Release-Queue Reconciliation v1* ("External
Pre-Release readiness criteria") and reconciled here by *Release-Gate
Reconciliation & External Acceptance Preparation v1* (see that
milestone's own
[preparation report](release-gate-reconciliation-external-acceptance-preparation-v1-report.md)
for the complete baseline/reconciliation record this plan sits inside).

Preparing this plan does **not** recruit a participant, does **not** fix
a cohort size, does **not** start a session, and does **not** authorize
execution. Current authorization to begin Gate G remains `NONE` -- see
[release-execution-state.md](release-execution-state.md) §3/§6.S. Several
sections below name a concrete owner decision this plan cannot
self-authorize; those are called out explicitly, not silently assumed.

---

## 1. Purpose and entry criteria

**Purpose.** Gate G is private validation of the still-unreleased product
by a small external cohort, under conditions this project cannot fully
simulate itself -- real homes, real cameras, real networks, real users who
did not build the product. It is not a released public beta: participants
are testing the unreleased product, not using a shipped beta product, and
neither Gate G nor the release that follows it should ever be described
externally as a beta (see
["Gate G -- External Pre-Release Acceptance"](roadmap.md) in
`roadmap.md`). Findings from Gate G feed Final Release Hardening (Lane S)
directly; Gate G is not itself the release decision.

**Entry criteria (all three, per the governing reconciliation chain).**

| # | Criterion | Status |
|---|---|---|
| 1 | Gate A (representative field correctness) reaches an accepted disposition, closing Lane R | **MET** -- Gate A PASS / Lane R CLOSED, 2026-09-07 (*Lane R Release-Budget Adjudication & Gate A Decision v1*) |
| 2 | Lane P's mechanical LICENSE/packaging-metadata adoption lands -- a participant should not clone/receive a build whose own README says its license "has not yet been finalized" | **MET** -- Lane P CLOSED, 2026-09-06 (*MIT Source License Adoption & Lane P Mechanical Closure v1*): real `LICENSE` file, SPDX metadata in `pyproject.toml`/`web/package.json`, corrected `README.md`, proven present in a real built wheel and the Windows bundle |
| 3 | A concrete cohort/hardware/findings-intake plan is actually scoped | **THIS DOCUMENT** |

All three preconditions are now met by the plan existing; **scoping the
plan is not the same as executing it.** Recruiting participants, fixing
a start date, and running the first session all remain separate,
explicit, not-yet-granted authorizations.

Per `roadmap.md`'s own gate-priority discipline ("Gate order is priority
order: do not spend material effort on a later gate while an earlier one
has a known, evidenced gap"), Gate G may now proceed because Gate A (the
higher-priority gate) no longer has a known, evidenced gap blocking it.
The small, individually-disclosed release-critical residuals in Lanes L,
F, and E (below) do not reopen that gap -- each is independently
hardware- or network-access-gated, not a Gate A correctness question, and
each is compatible with running concurrently as a Gate G finding if a
participant happens to hit one.

---

## 2. Target participant/cohort characteristics and selection rationale

**Rationale.** `roadmap.md` is explicit: "move to a small external cohort
-- not hundreds of users. Prioritize diversity of real setups over
headcount." The goal is coverage of real installation/hardware/network
diversity this sandbox cannot produce, not statistical significance.

**Recommended cohort shape (advisory -- exact headcount and identities are
an owner decision, see §3 below):**

- **Size:** small, single digits to low double digits (roadmap's own
  "not hundreds" is the only governed constraint; no specific number is
  adopted here without owner input -- see the flagged decision below).
- **Diversity axes to prioritize, in this order:**
  1. **Native-Windows host hardware diversity** -- different CPU/GPU
     generations, at minimum one machine with a CUDA-capable NVIDIA GPU
     (the only currently **Validated** accelerated path -- see Lane O,
     `release-execution-state.md` §6) and, if available, one
     CPU-only/no-CUDA machine to exercise the honest
     `onnx_cuda_unavailable`/setup-required failure path rather than a
     silent species/detector gap.
  2. **Camera/Source diversity** -- at least one participant on the
     native Camera Node golden path (a Raspberry Pi, matching this
     project's own reference hardware), at least one on ONVIF or
     RTSP/RTSPS, and at least one on local USB/Windows DirectShow --
     Lane G's own remaining gap is precisely that no real, reachable
     RTSP/local-USB/ONVIF hardware or live authenticated video decode
     has ever been proven end-to-end from this sandbox (see Lane G,
     `release-execution-state.md` §6) — Gate G is the first realistic
     opportunity to close that specific evidence gap with real
     participant hardware.
  3. **Network/deployment shape diversity** -- at least one LAN-only
     participant and, if available, one participant who configures the
     documented private-overlay-network (Tailscale-compatible) remote
     -access posture, to exercise it under real conditions for the first
     time (Lane E's own disclosed gap: "no live external-overlay-network
     acceptance was possible from this sandbox").
  4. **Multi-camera** -- at least one participant with 2+ cameras against
     one Place, to exercise the accepted Camera/Source + Multi-Camera
     Maturity v1 / Multi-Camera Place Experience v2 foundation under a
     real household's own camera count, not only this project's own
     synthetic scenario tests.
  5. **Real feeder/yard activity variety** -- participants should have an
     actual bird feeder, birdbath, or comparable wildlife-visited area;
     Gate G validates real animal encounters, not an empty yard.
- **Technical sophistication mix:** at least one participant comfortable
  with self-serve troubleshooting (a "serious naturalist/technically
  sophisticated user" persona, per `roadmap.md`'s "Deployment classes"
  guidance) and at least one participant representing an ordinary
  non-developer Personal/Home user, since the Personal/Home profile
  ("appliance-style/guided local install... a technically competent
  non-developer can deploy MockingBird without WSL, cloning GitHub, or
  understanding internal services" -- `roadmap.md` Phase 4 exit
  condition) is the primary release target, not the Organization/Research
  profile.
- **Explicitly out of scope for this cohort:** no participant should be
  asked to validate remote/LTE/solar field hardware, broad multi-site
  deployment, or native mobile app behavior (browser/PWA only) -- all
  three are accepted after-release/deferred lanes (Bucket C/D, see the
  preparation report §4), not Gate G scope, and recruiting for them would
  silently expand release scope by cohort selection rather than by
  evidence.

**Owner decision flagged:** exact headcount, participant identities, and
recruitment channel (existing contacts vs. a public call) are not
determined by this plan and require explicit owner selection before
recruitment begins.

---

## 3. Hardware and native-Windows host coverage

Native Windows is this product's **Validated** release Host (the only
Host with a packaged, no-Python-required end-user distributable; see
Lane O, `release-execution-state.md` §6). Gate G's own host coverage
should therefore be native-Windows-first:

- **Required:** every participant installs and runs the packaged
  Windows bundle (`local-product-packaging-design.md`'s "unpack and run"
  distributable), not a development checkout (WSL/venv/`npm ci`). This
  is the actual release artifact shape and the only one with prior
  accepted native-Windows acceptance evidence (Release Engineering
  Foundation v1; Native-Windows Packaged Local-Only Acceptance & Privacy
  Closure v1; Place / Yard Intelligence v2's own native-Windows proof --
  see `release-execution-state.md` §16 and §6.O).
- **Recommended, not required:** at least one participant on Linux at the
  source/dev level, since Linux is **Structurally supported** (CI
  -validated, a real first-class Linux-only feature -- the V4L2
  local-USB-camera bridge -- already exists) but has never had a
  dedicated native hardware acceptance pass; a Gate G participant running
  from source on real Linux hardware would be the first such evidence.
  This must not become a requirement that blocks recruitment -- native
  Windows remains the priority coverage.
- **Explicitly not required, and not a Gate G finding if it doesn't
  work:** macOS (**Unverified** overall; microphone capture specifically
  **Unsupported** and already disclosed), AMD GPU (**Unsupported**, no
  ROCm/DirectML code), Apple Silicon (**Deferred**). A participant
  attempting one of these should be told in advance it is unsupported,
  not silently discovered as a "bug" mid-cohort.
- **GPU coverage:** at least one participant's host must have an
  NVIDIA CUDA-capable GPU, since the production detector
  (`onnx-cuda`/`frame-driven-onnx-cuda`) is deliberately, by tested
  design, **Unsupported on CPU** (`session.disable_cpu_ep_fallback`; no
  fallback) -- a participant without a CUDA GPU will honestly see a
  setup-required/unavailable state for detection specifically, which is
  expected behavior, not a defect, and should be disclosed to that
  participant in advance so it is not mis-reported as broken. Species
  (BioCLIP-2) and acoustic (BirdNET) assistance remain CPU-only and
  should still work on that same host.

---

## 4. Local Only installation and operation

Gate G must validate the product's actual default posture: **Local
Only**, no cloud account, no MockingBird-operated backend. Concretely:

- Every participant installs from the official packaged artifact,
  verifies it (see the preparation report's Release-Candidate section for
  the exact checksum/provenance mechanism a participant-facing build
  should carry), and confirms the product operates with no MockingBird
  -run cloud dependency at any point in first-run setup, camera
  configuration, review, or Today/history browsing.
- The four-step first-run wizard (Welcome -> Storage -> Add a camera ->
  Start observing, per `using-mockingbird.md`) is exercised as a real
  participant would use it, not narrated by an operator -- this is
  precisely the "conditions this project cannot fully simulate itself"
  Gate G exists for.
- Optional network-touching features (weather/Open-Meteo, remote
  overlay-network access, any future acoustic model acquisition) must
  remain off by their existing defaults unless the participant explicitly
  opts in, and the plan's findings intake should record whether any
  participant experienced an unexpected outbound network call --
  a genuine Local Only regression would be a release-blocking finding
  (see §13).
- LAN discoverability (`GET /api/product/connection` + the Settings
  "Connection & Remote Access" card) should be confirmed understandable
  by a participant without developer context, since this is the first
  real external test of that surface.

---

## 5. Onboarding, first observation, and first useful result

**What "first useful result" means for this plan** (roadmap.md/the
governing directive do not define a numeric target here, and this plan
does not invent one): a participant reaches a genuinely useful state when
they can (a) complete first-run setup and see their own camera's live
preview, (b) observe at least one real Visit appear without developer
assistance, and (c) understand, from the product's own UI, what that
Visit is and whether it needs their review -- matching the documented
Review Queue / Bird Log / Today loop, not a Review-Queue-first framing
(Lane C's own accepted first-hour narrative fix already corrects
onboarding copy to point new users at Today/Bird Log as the normal
discovery destination, not Review Queue).

**What this plan tracks, per participant:**

- time/attempts from unpack to a working first-run wizard completion;
- time/attempts from wizard completion to a confirmed, honest camera
  preview (or an honest, understandable failure message if the
  participant's camera type is not supported);
- whether and when the participant's first real Visit appeared, and
  whether they understood it without asking a developer;
- whether the participant could tell "MockingBird saw nothing yet"
  apart from "MockingBird is still processing" apart from "something is
  wrong" -- this is a named Gate A quality concern (observation
  freshness / capture-to-visible latency) that Gate G is the first
  opportunity to observe under real non-operator patience/expectations,
  now that a latency budget exists to set that expectation against
  (roughly 80-115 seconds typical, occasionally several minutes longer
  during busy activity -- see the preparation report's Gate A section).

**Owner decision flagged:** no numeric time-to-first-Visit target is
adopted (e.g., "under N minutes") because no governing document sets
one; if the owner wants a numeric onboarding-time acceptance bar, that is
a decision for the owner to set, not one this plan infers from adjacent
numbers.

---

## 6. Correction/review and evidence trust

Gate G must validate that a real, non-developer user can and will
actually use the correction loop, not merely that the API exists:

- each participant should correct or confirm at least a handful of real
  Visits through Review Queue, using the actual evidence gallery (all
  captured frames, not only one system-selected "primary" frame -- the
  accepted Visit Evidence Gallery behavior);
- confirm the participant understands that an unreviewed suggestion is
  labeled as a guess, not silently treated as truth (the Measured/
  Inferred/Reviewed distinction, product-doctrine.md) -- this is a
  product-trust question Gate G should observe directly, not merely
  assume from doctrine text;
- confirm at least one participant encounters and correctly interprets
  an honest abstention ("bird, species uncertain") rather than expecting
  a wrong confident guess to have been "fixed" by correction alone;
- record whether any participant's correction failed to "stick" (i.e.,
  a genuine truth-boundary regression) -- this class of finding is
  automatically Sev-0 (see §13), since Human correction remaining the
  truth boundary is this product's most load-bearing invariant.

---

## 7. Multi-camera/Place behavior (within accepted scope)

For any participant with 2+ cameras:

- confirm Today, Bird Log, Dashboard, and Zone Insights present one
  coherent "observatory," not several disconnected camera views (the
  accepted Multi-Camera Place Experience v2 acceptance target);
- confirm a real cross-camera duplicate encounter, if one naturally
  occurs, is deduplicated rather than double-counted (accepted
  `cross_camera_visit_associations` behavior) -- this cannot be forced,
  so record it as an opportunistic observation, not a required test step;
- confirm archiving/renaming a camera does not silently hide that
  camera's own history (the accepted archived-camera-history-reachability
  fix).
- **Explicitly out of scope:** true multi-site (several physically
  separate Places) is a separate, not-yet-authorized product/architecture
  decision -- no participant should be asked to validate it, and a
  participant request for it is a Bucket-C/D product signal to record,
  not a Gate G defect.

---

## 8. Installation, update, recovery, backup, uninstall

- **Installation:** the documented "unpack anywhere, no installer, no
  prerequisites" flow (`using-mockingbird.md`) is exercised as-is by each
  participant on their own machine.
- **Update:** if a schema/version update becomes available during the
  Gate G window, at least one participant's update should be observed
  directly -- confirm the automatic pre-migration safety backup, the
  post-migration health check, and the honest on-screen "MockingBird
  updated your data" disclosure all fire exactly as documented.
- **Recovery:** exercise the documented database-corruption recovery
  procedure (close -> move `mockingbird.sqlite3` aside -> reopen ->
  restore from Local Data) with at least one participant in a controlled
  way (not a real corruption) to confirm the documented steps actually
  work for a non-developer following the written instructions verbatim,
  not only for an engineer who already knows the mechanism.
- **Backup:** every participant should create at least one manual backup
  via Settings -> Local Data and confirm the download succeeds and is a
  real, restorable file.
- **Uninstall:** **this is a real, confirmed documentation gap, not a
  missing product capability** -- `using-mockingbird.md` documents how to
  *stop* MockingBird (close the browser tab; end `pythonw.exe`; or
  reboot) but no formal uninstall/cleanup procedure exists anywhere in
  the product's own user documentation. Because the product is a
  self-contained unpacked folder with no system-level installer, registry
  entries, or services to remove, uninstall is *believed* to be "delete
  the folder" plus, optionally, the user's own data directory -- but this
  plan does not assert that as verified fact. **Recommended: confirm and
  document the exact, complete uninstall procedure (including where the
  data directory lives and what, if anything, survives folder deletion)
  before Gate G asks a participant to rely on it, and definitely before
  Final Release Hardening's own "release notes" close this gap
  implicitly.** This is flagged as a concrete pre-Gate-G documentation
  action, not a blocker requiring new engineering.

---

## 9. Privacy and consent

- Every participant receives, before installing anything, a plain
  -language explanation that they are testing an **unreleased** product
  privately (never described as a beta), what data the product stores
  locally, what (if anything) ever leaves their device by default
  (nothing, unless they opt into weather/remote-access/acoustic-model
  acquisition), and that Local Only is the default and supported posture.
- Camera/RTSP credentials are stored in plaintext at rest by documented,
  confirmed design (no contract promises otherwise) -- participants
  should be told this explicitly before entering real camera credentials,
  consistent with this project's own privacy-and-portability doctrine
  ("a user should be able to tell where media lives, what leaves the
  device... and backup behavior").
- Privacy Zones mean trigger-level exclusion, not guaranteed pixel
  redaction of every retained frame -- a participant using Privacy/Ignore
  Zones over, e.g., a neighboring property or a household member's usual
  path should be told this limitation explicitly before relying on it.
- **Participant consent for findings sharing:** each participant should
  explicitly agree that bug reports, screenshots, and log/support-bundle
  excerpts they submit may be reviewed by the project owner for the
  purpose of fixing defects -- see §16 for exactly what is and is not
  collected.
- **Media/PII handling:** a participant's own camera captures real
  images of their property, and may incidentally capture people (a
  visitor, a household member, a delivery). This plan does not ask
  participants to submit raw evidence media as a routine finding artifact
  (see §16); where a specific frame is genuinely needed to reproduce a
  defect, request it explicitly, describe why, and let the participant
  decline or redact.
- **Owner decision flagged:** whether a written consent form is required
  (versus a plain-language written explanation the participant
  acknowledges) is a policy choice this plan does not resolve --
  reasonable given the small, trusted, non-commercial cohort scale, but
  the owner should confirm that judgment explicitly before recruitment.

---

## 10. Optional cloud/acoustic behavior and licensing disclosures

- Acoustic (BirdNET) assistance remains off by default, CPU-only, and
  optional; any participant who enables it must see the existing
  licensing disclosure (BirdNET model weights are CC BY-NC-SA 4.0,
  NonCommercial; MockingBird's own official packages never redistribute
  the weights, enforced by a durable build-time guard) before or at the
  point of enabling it, exactly as `using-mockingbird.md` and
  `THIRD_PARTY_NOTICES.md` already document.
- The standing, unresolved BirdNET commercial-adjacent legal question
  (whether an individual's private, non-commercial use could ever be
  implicated because the surrounding open-source project accepts
  donations or sells optional paid support) is **not** a Gate G blocker
  and needs no participant-facing disclosure beyond the existing
  NonCommercial license notice -- it is a standing legal-review item with
  no available engineering action (see the preparation report §8).
- Weather/Open-Meteo context remains a second, independent opt-in,
  separate from the coarse-coordinate solar setting; confirm at least one
  participant experiences the opt-in flow and that enabling it is never
  silently implied by enabling the other.
- No participant should be asked to use, or told to expect, any
  MockingBird-operated cloud service, push-notification backend, or
  remote relay -- none exists, and Gate G should surface, as a real
  finding, any spot where the product's own copy implies otherwise.

---

## 11. Usability/accessibility and performance

- Confirm the responsive/mobile-viewport behavior already proven in
  isolation (zero horizontal overflow across 10 real phone-width
  screenshots) holds on each participant's own real phone, not only this
  project's own synthetic viewport matrix.
- Confirm the installable PWA shell behaves as documented (installs,
  offers no false offline-data claim) on at least one participant's
  phone.
- Record any accessibility friction a participant reports in their own
  words (keyboard/focus, screen-reader use, color-only status cues) --
  this project's own accessibility pass was spot-checked, not
  exhaustively audited, so Gate G is real incremental evidence here, not
  a formality.
- Record real-hardware performance observations (page responsiveness
  with the participant's own real Visit backlog size, browser memory
  behavior over a multi-day session) -- this is exactly the "days without
  developer babysitting" exit condition Phase 1 names, and this sandbox
  cannot produce a multi-day, real-household soak on its own.

---

## 12. Diagnostics and support boundaries

- Every participant should run `python -m mockingbird doctor` at least
  once during the cohort window and confirm its plain-language summary
  matches their own understanding of their install's health.
- When a participant reports a problem, the first ask should be their
  Doctor summary and, if needed, a `support-bundle` export -- **not**
  raw database files, raw media, or camera credentials. The support
  bundle is documented to exclude camera passwords, pairing secrets, and
  media, and to redact its log slice automatically; findings intake
  (§13) should never ask a participant to bypass that boundary (e.g., by
  manually attaching `mockingbird.sqlite3` or raw evidence frames) unless
  a specific, disclosed exception is genuinely required to reproduce a
  defect, and the participant explicitly agrees case-by-case.
- **Support boundary during Gate G:** the project owner (or a delegated
  triager) is the sole support contact; participants are not expected to
  self-diagnose beyond running Doctor and, where comfortable, reading
  the plain-language guidance it already prints.

---

## 13. Findings intake, severity, ownership, and reproduction requirements

This reuses the small, practical workflow defined in the preparation
report (§7, "Findings/defect triage contract") without inventing a
second one. Summary, Gate-G-specific additions only:

- **Intake channel:** a single place the owner designates before
  recruitment (this plan does not choose one -- a shared form, a private
  repository issue tracker, or direct messages are all compatible with
  this project's existing "do not create a new issue-management platform"
  guidance; whichever the owner already uses for accepted-milestone
  tracking is the right default).
- **What every finding must include to be actionable:** what the
  participant did; what they expected; what happened instead; their
  Doctor summary or support bundle if relevant; their host OS/GPU and
  camera type (from §2/§3's cohort record, not re-collected per finding).
- **Severity, reproduction, ownership, and disposition (accept/reject/
  defer)** follow the identical rubric in the preparation report §7 --
  Gate G findings are triaged exactly like any other accepted-milestone
  defect, with one addition: a finding that reproduces a Gate A dimension
  already carrying an accepted disposition (recall, false-Visit rate,
  fragmentation, duplicates, useful-evidence, evidence-loss, monitoring
  coverage, latency) is evaluated against that accepted budget, not
  against a participant's own expectation -- e.g., an occasional slow
  Visit inside the accepted ~80-115s-typical/qualitative-tail budget is
  expected behavior to disclose to the participant, not a defect to fix,
  unless it falls outside even the disclosed tail characterization.
- **What Gate G findings feed:** Final Release Hardening (Lane S)
  directly, per the accepted one-release doctrine. A Sev-0 finding
  (see §7 of the preparation report) discovered during Gate G is a stop
  condition for that specific participant's continued testing until
  triaged (see §15, below), not necessarily for the whole cohort.

---

## 14. Acceptance criteria and exit decision

**No numeric acceptance target is invented here where none is governed.**
Consistent with this project's own standing discipline ("do not invent a
numeric release budget merely to close a gate"), Gate G's exit decision
is a **qualitative release-authority judgment**, informed by:

- whether any Sev-0/Sev-1 finding (per §7 of the preparation report)
  was found and left unresolved;
- whether the already-accepted Gate A budgets (recall, false-Visit rate,
  fragmentation, duplicates, useful-evidence, evidence-loss, monitoring
  coverage, latency) held up under real, diverse, non-operator field
  conditions, or whether Gate G evidence contradicts one of them (a
  genuine reopening ground -- see the preparation report §3's
  reopening-grounds discipline);
- whether the documented golden path (install -> open -> add camera ->
  preview -> confirm storage -> observe) was actually achievable by every
  participant without developer intervention;
- whether Local Only/privacy guarantees held for every participant;
- a qualitative read of whether participants found the product genuinely
  useful, not merely functional -- Gate G is validation, not only defect
  hunting.

**Owner decision flagged:** the exact number/severity of findings that
would constitute "exit: not ready, iterate" versus "exit: proceed to
Final Release Hardening" is a release-authority judgment call this plan
does not pre-commit to a formula for, consistent with the governing
directive's own instruction not to invent numeric acceptance targets
where none exists. The recommendation is that the owner (or the external
acceptance-review process this preparation report is itself addressed
to) render that judgment directly against the findings ledger Gate G
produces, the same way the recall and latency dimensions of Gate A were
each resolved by an explicit release-authority decision rather than a
formula.

---

## 15. Rollback/stop conditions

- **Per-participant stop:** any Sev-0 finding (truth-boundary violation,
  data loss/corruption, a genuine Local Only/privacy breach, or a crash
  loop with no recovery) pauses that participant's session immediately;
  the owner triages before that participant continues.
- **Cohort-wide stop:** any finding that reproduces across two or more
  independent participants, or any single finding that contradicts an
  accepted Gate A budget/limitation (not merely a disclosed edge of it),
  pauses the entire cohort pending triage -- this mirrors the "reopening
  grounds" discipline already governing accepted milestones generally
  (a reproduced defect, new field evidence, or a genuine dependency, not
  mere adjacency or a single unreplicated report).
- **Full Gate G stop/abort:** reserved for a finding that calls the Gate
  A PASS decision itself into question (e.g., a reproducible false-Visit
  rate or recall failure materially outside the accepted budget under
  ordinary, non-adversarial conditions) -- this returns the product to
  Lane R, not merely to a Gate G iteration, exactly as the governing
  directive's reopening-grounds language anticipates.
- **Participant-initiated stop:** any participant may withdraw at any
  time without needing to justify it; their data/findings up to that
  point are retained per §16 unless they ask for deletion.

---

## 16. Evidence retention and participant-data handling

- **What is collected from participants, by default:** Doctor summaries,
  support-bundle exports (already redacted of credentials/pairing
  secrets/media), written finding descriptions, and the cohort-diversity
  facts in §2 (host OS/GPU, camera type, deployment shape). This is
  intentionally the same class of "bounded, privacy-conscious diagnostic
  information" this project's own doctrine already applies to rejected
  -detection accounting -- not permanent storage of a participant's raw
  media or database by default.
- **What is not collected unless explicitly, individually requested and
  agreed:** raw evidence frames/video, the participant's own
  `mockingbird.sqlite3`, camera credentials, or any personally
  identifying detail beyond what a participant volunteers in a finding
  description. If reproducing a specific defect genuinely requires a raw
  artifact, ask for that one artifact, explain why, and let the
  participant decline.
- **Retention duration:** findings and diagnostic artifacts collected
  during Gate G should be retained at least through Final Release
  Hardening's own findings-triage close, since Gate G's stated purpose is
  to feed that stage directly; a specific retention/deletion policy
  beyond that point is an owner decision this plan does not set.
- **Participant data at rest:** nothing about Gate G changes where a
  participant's own MockingBird data lives -- it remains on their own
  machine, under the same Local Only guarantees the rest of this plan
  validates. Gate G collects diagnostic *reports about* that data, never
  the data itself, absent an explicit, individually-scoped exception.

---

## Owner decisions this plan cannot self-authorize (consolidated)

1. Exact cohort headcount, participant identities, and recruitment
   channel (§2).
2. Whether a formal written consent form is required, versus a
   plain-language acknowledgment (§9).
3. Any numeric onboarding-time or acceptance target, if the owner wants
   one beyond the qualitative criteria in §14 (§5, §14).
4. The exact severity/count formula (if any) for the exit decision,
   versus a direct qualitative release-authority judgment against the
   findings ledger (§14).
5. Confirming and documenting the exact uninstall procedure before
   relying on it in front of participants (§8) -- a small, concrete,
   pre-Gate-G action, not a plan gap.
6. The actual go/no-go to begin recruitment and execution -- this
   document prepares the plan; it does not authorize starting it.
