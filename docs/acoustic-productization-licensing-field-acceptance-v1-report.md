# Acoustic Productization, Licensing & Field Acceptance v1 — Closure Report

Starting HEAD `63f0a57` (schema v53). Ending HEAD recorded in the follow-up
commit per this project's established convention. Schema **unchanged at
v53** — no migration in this milestone (no durable state was genuinely
missing; every fix operates on already-persisted facts).

This was explicitly not a from-scratch acoustic milestone. Substantial
capability already existed: Acoustic/BirdNET Observation Foundation v1,
Acoustic Runtime & Quality v1, and Multimodal Observation & Soundscape v1
(the last of which had no memory entry written for it — a documentation gap
this report closes). The job here was verification against the current
repository and actual installed artifacts, an authoritative licensing
decision, and closing the bounded gaps a credible first release needs.

Full archaeology, the per-artifact licensing table, and the Phase 2
architecture reasoning live in the companion
[acoustic-productization-licensing-field-acceptance-v1-contract.md](acoustic-productization-licensing-field-acceptance-v1-contract.md).
This report answers the milestone's 26 closure questions directly and
records what changed, what was tested, and what remains open.

## 1–26: Direct answers

**1. What acoustic capability existed at the start?** A complete, real
(non-shim) BirdNET inference path (`birdnetlib` + bundled
`BirdNET-Analyzer GLOBAL_6K_V2.4`, CPU-only), live-microphone capture via
ffmpeg (structurally complete but never hardware-validated before this
milestone), a bounded automatic runtime (queue/retry/retention), a
deterministic timing-only multimodal visual↔acoustic association engine,
row-level presentation collapse in Today/Bird Log, and reviewed-truth
integration with zero changes to the review/correction boundary.

**2. What exact BirdNET/runtime/model artifacts are used?** `birdnetlib`
0.18.1 (Apache-2.0), backed by `ai-edge-litert` 2.2.0 as the
`tflite_runtime` substitute (`tflite-runtime` itself is unavailable on PyPI
for this project's Python versions), running the `BirdNET_GLOBAL_6K_V2.4`
model — two `.tflite` files plus a labels file, shipped as real package
data inside the `birdnetlib` wheel itself. No runtime download ever occurs
under MockingBird's own code path (confirmed by source inspection, not
assumed).

**3. What license applies to each artifact?** `birdnetlib` code: Apache-2.0.
`ai-edge-litert`/`librosa`/`resampy`/`audioread` (and birdnetlib's own
`matplotlib`/`pydub`/`requests`/`watchdog`): all permissive
(Apache-2.0/ISC/MIT), no commercial restriction. The **model weights**
specifically: **CC BY-NC-SA 4.0** (Cornell K. Lisa Yang Center for
Conservation Bioacoustics), confirmed from four independent first-party
sources (the model-directory LICENSE file shipped inside the wheel, the
upstream BirdNET-Analyzer repo's own README splitting code=MIT/models=CC
BY-NC-SA 4.0, the maintainer's separately-named `birdnet-models-nc-sa`
metadata repo, and MockingBird's own pre-existing `MODEL_LICENSE` constant).
Code license and model license were never conflated in this analysis.

**4. Can MockingBird redistribute the model?** Not under the accepted
architecture. The packaged Windows product (`scripts/build_local_product.py`)
was already, as a matter of fact, **not** including the model (zero
references to "birdnet"/"acoustic" anywhere in that script, confirmed by
grep) — this was accidental-by-omission, not a deliberate policy. This
milestone made it deliberate: a new `verify_no_nc_licensed_acoustic_model_
redistribution` check now actively fails the build if `birdnetlib` is ever
found in packaged site-packages, and the script's own module docstring now
explains why. The open-source MockingBird *repository* continues to declare
`classifier-birdnet` as an optional pip extra — a dependency declaration,
not a redistribution — a user who wants it runs `pip install
mockingbird[classifier-birdnet]` themselves and obtains the model from PyPI
under upstream's own terms.

**5. Is commercial use clearly allowed, prohibited, or unresolved?**
Deliberately bundling/redistributing the model into a commercially-directed
distribution (paid support, Kickstarter-funded appliance, hosted paid
service) is **not allowed** — this is the clear case CC BY-NC-SA exists to
restrict, not ambiguous. Whether an individual user's own private,
non-commercial use of MockingBird+BirdNET (model never redistributed by
MockingBird itself) could ever be implicated merely because the surrounding
open-source project also accepts donations or sells optional paid support
is genuinely **unresolved** — recorded as such, with a recommendation for
legal review before any commercial-adjacent distribution decision actually
touches the acoustic feature, not resolved by this report.

**6. What release architecture follows?** **Decision B — Optional external
model.** MockingBird's own release artifacts (repo and packaged installer)
never bundle the model; a user obtains it themselves via the optional
extra, under upstream's own terms.

**7. Which audio inputs are actually validated?** Recorded WAV/audio file
import (real xeno-canto recording, real model, correct species end-to-end —
predates this milestone). **New this milestone**: Host local microphone
live capture, validated against real hardware for the first time (real
EMEET SmartCam S600 USB webcam+mic on a real Windows machine) — real ~50s
continuous capture, correct bounded-segment behavior, canonical format
independently confirmed via `ffprobe`, real BirdNET inference on the real
captured audio, real concurrent visual+acoustic capture with zero device
contention, real "bogus device" and "reconnect after stop" behavior.

**8. Which are structural-only?** Host USB audio interface (no code
distinction from a plain mic — same status as #7's microphone path).
Camera Node microphone, RTSP audio, recorded-video embedded audio, ONVIF
audio: **unsupported/deferred**, explicitly and correctly so (zero code,
explicitly named out-of-scope in existing design docs) — not this
milestone's job to build, per its own "single dependable path" instruction.

**9. How are audio timestamps defined?** Always already-persisted, already-
anchored absolute instants (`EventModel.started_at`/`ended_at` for both
modalities) — never re-derived from raw BirdNET offsets, never analysis
time, never database-insertion time, never UI render time (confirmed by
direct source reading of `temporal_evidence.py`). Visual-side ordering is
stamped from the Host's own clock at candidate-creation time, never a
Camera Node device timestamp — an existing, disclosed mitigation for
Node/Host clock uncertainty, not something this milestone changed.

**10. How is multimodal association bounded?** A deterministic, timing-only
engine: exactly one opposite-modality candidate within a 15s window (or
overlapping) tiers `"associated"`; competing candidates or a 15–60s gap
tier `"possible"`; beyond 60s, no row is ever created. Never reads
species/taxon at association time. Never merges Visits, never writes
`reviewed_label`/`review_status`. Both constants are explicitly disclosed
as reasonable-but-not-field-tuned (no real colocated-encounter timing
measurement existed before this milestone; this milestone's field
acceptance proved the capture *mechanism* on real hardware but did not
naturally observe a real simultaneous visual+acoustic bird encounter to
calibrate against — the constants remain an open field-calibration target).

**11. Can conflicting audio/visual evidence remain unresolved?** Yes,
proven directly: a visual/acoustic pair with different species can still
tier `"associated"` on timing grounds, with `taxon_agreement="differs"`
computed fresh at read time and surfaced honestly (never hidden, never
auto-resolved) — `test_scenario_2_conflict_visual_and_acoustic_disagree_
overlapping` proves this pre-existing, and this milestone re-verified it
directly from code rather than trusting the claim.

**12. How are acoustic-only events reviewed?** Through the exact same
review queue and `ReviewLabel`/`POST /api/review-labels` path as visual
Visits — no separate acoustic review flow exists (confirmed by dedicated
archaeology of `ReviewQueuePage.tsx`: the only acoustic-specific code is a
display-copy difference, "Bird heard" vs. "Animal detected"). A dedicated
regression test (`test_scenario_8_human_correction_becomes_authoritative_
and_is_never_overwritten`) proves a human correction survives untouched
even when a new, superficially-agreeing acoustic detection arrives later.

**13. How are paired audio/visual events represented in Today/history?**
List/gallery rows for a confidently-associated pair collapse to one
(pre-existing, correct). **This milestone fixed** the adjacent count fields
in the same responses, which previously disagreed with those rows —
Bird Log's `observation_count` (both the per-label overview and the
per-species history), Today's `confirmed_bird_visit_count`/
`activity_by_zone`/`activity_by_hour`, and Place Activity Report's Gate C
per-zone/per-hour pattern totals (fixed once, at the shared root function,
covering all six call sites at once).

**14. Is obvious duplicate counting resolved?** Yes, for the confirmed real
bug (see #13). `unresolved_animal_visit_count`/`needs_help` and
`detector_qualified_animal_visit_count` were deliberately left counting
both Visits independently — these are review-workload/raw-detector-
qualification signals, not "how many animals" claims, and per-Visit
independence is the honest count there (a human may still need to
separately correct each side of a pair).

**15. What raw audio is retained?** The automatic runtime's own ephemeral
working segments (never-became-evidence, never human-imported) only, under
a 48-hour TTL. Human-imported/manually-uploaded recordings are structurally
immune (a dedicated `acoustic_working_segment` marker, set only by the
automatic capture path) regardless of age.

**16. How long is it retained?** 48 hours for the runtime's own ephemeral
segments (checked every 15 minutes); indefinitely for anything that became
evidence or was manually imported, governed by the same general
`StorageRetentionSettingsModel` every other media type uses — no
acoustic-specific retention lever beyond the 48h working-segment sweep,
which is deliberate (disclosed, not accidental).

**17. Can raw audio enter support bundles or exports unintentionally?**
No, on both counts — independently re-verified, not just trusted from
memory. The support bundle writes exactly four fixed members (manifest,
Doctor report, structural Source facts, redacted log tail); no media-root
walk exists anywhere. Every research/Camtrap DP export path was re-checked
directly: `include_media` remains fully inert (confirmed: zero references
to it anywhere in `product_repository.py`), and audio passes through the
identical, media-type-agnostic eligibility gate as visual evidence.

**18. What acoustic coverage/effort semantics exist?** **None, confirmed
precisely** — `compute_coverage_summary`'s only inputs are a generic
interval list and a history-availability flag; no microphone-operational,
model-available, or analysis-gap signal exists anywhere in it, and the two
API endpoints that could answer "is acoustic actually working right now"
(`BirdNetStatusResponse`, `AudioCaptureStatusResponse`) have **zero
frontend callers anywhere in the product** — not rendered on any page.
This is the most important gap this milestone did **not** close (see
"Remaining bounded gaps," below) — a genuinely new frontend surface was
judged out of proportion for this milestone, since no Doctor UI exists for
any subsystem yet, acoustic or otherwise.

**19. What happens when the microphone fails?** Consent/device-
misconfiguration failures return actionable HTTP 400/403 today (pre-
existing). This milestone added an honest macOS failure (`AudioDecodeError
("unsupported_platform")`, surfacing as HTTP 503) for what used to be a
silent wrong-command attempt. Real hardware testing this milestone (a
never-connected "bogus device") confirmed ffmpeg fails fast (0.1s) with a
clear, diagnosable stderr message. Visual monitoring is architecturally
untouched by any acoustic failure — the two pipelines share no failure
path (confirmed by code reading, and now also by a real concurrent-capture
hardware test showing zero contention).

**20. What happens when the model is missing?** The optional
`classifier-birdnet` extra being absent never breaks app startup or visual
monitoring (unconditionally true — it is an optional import path). The
product-experience half of this (does the *user* get told the model is
missing, anywhere in the UI?) is the same gap named in #18 — the backend
knows, nothing currently displays it.

**21. What are CPU/memory/storage costs?** Bytes/hour at canonical format:
48kHz mono 16-bit PCM ≈ 172.8 KB/s ≈ 622 MB/hour of *working* segments
before the 48h TTL sweep reclaims them (never accumulates past that unless
a segment became evidence). BirdNET inference is CPU-only, ~3s per 15s
clip on this sandbox's CPU (measured directly during real-hardware
inference this milestone). Bounded queues throughout (100/stream, 500
global, both durable row counts, not in-memory). One real memory-hygiene
issue found and fixed: `MicrophoneCaptureSession._known_segments` grew
unboundedly for the life of a capture session (Path objects only, never
audio bytes) — now pruned to the on-disk listing on every poll.

**22. What platforms/runtime combinations were actually validated?** Linux:
BirdNET inference validated for years across this project's test suite,
plus fresh real-model runs this milestone. Windows: microphone capture
**newly hardware-validated this milestone** (real USB webcam+mic, real
ffmpeg dshow). macOS: **no real hardware exists to validate against in this
environment** (unchanged) — and this milestone additionally confirmed the
code path would have silently attempted the wrong ffmpeg backend
(PulseAudio, not `avfoundation`) had it ever been reached; now fails
honestly instead. No Apple/ARM claims are made anywhere.

**23. What real field acceptance was performed?** Real, not simulated — see
the contract doc's "Real field acceptance" section and the summary in
"Validation," below. A real colocated USB camera+microphone on real
Windows hardware: continuous capture, format verification, real BirdNET
inference (including one real marginal false positive), device-failure and
reconnect behavior, and concurrent visual+acoustic capture. Not tested:
true physical mid-capture unplug (no physical hand access via remote
interop), multi-hour soak, or real wild birds (this is a desk/office
machine, not an outdoor site — no natural bird activity was reachable).

**24. What concrete false-positive/abstention findings emerged?** One real,
concrete finding: a real ~50-second indoor desk-ambience recording produced
a single marginal detection — "Flammulated Owl" at confidence 0.511, just
above the 0.5 default floor — almost certainly a false positive from
ordinary indoor sound (computer fans, HVAC), not a real owl. This is not a
product defect: it would create an honest `needs_review` Visit a human
would see and could reject, never silently become reviewed truth. It
concretely motivates this milestone's `MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE`
wiring fix (previously dead code, now an operator can actually raise the
floor in response to exactly this kind of observed marginal false
positive).

**25/26. Is the capability A/B/C/D, and why?** See "Release decision,"
below.

## Release decision

**B — Release-ready optional capability.**

The capability is real, genuinely tested (unit, injected-fake, real-model,
and now real-hardware), and the counting/licensing/privacy gaps a credible
release needed have been closed or honestly disclosed. It is **optional**
specifically because of model licensing (CC BY-NC-SA 4.0, NonCommercial) —
not because the engineering is immature. This matches the milestone's own
definition of B exactly: "supported and trustworthy, but optional due to
model licensing/runtime/hardware constraints." It is not A, because A
requires the model to be part of the default redistributable product,
which the licensing analysis rules out. It is not C or D: the mechanism
itself is not merely "architecture works with material gaps remaining" —
it is now real-hardware-proven on the one officially-supported live input
path, has a durable licensing/packaging guard, and has no known truth-
boundary or privacy violation.

## What changed (implementation)

12 files, +531/−16 lines, plus one new contract doc and this report. No
schema change.

1. **Counting fix** (`product_repository.py`): new `_deduplicated_
   observation_count` helper; a shared exclusion applied once inside
   `_historical_place_baseline_and_species_statuses` (covers Today, Bird
   Log ×2, Place Activity Report's Gate C fields, and Biodiversity Summary
   in one place); Today's `_dashboard_today_summary` now computes
   `zone_counts`/`hour_counts`/`confirmed_bird_visit_count` from the same
   collapsed view `best_moments` already used, instead of independently
   recomputing the collapse and using a raw, uncollapsed sum elsewhere in
   the same response.
2. **Licensing/packaging guard** (`build_local_product.py`): new
   `verify_no_nc_licensed_acoustic_model_redistribution`, called in the
   same place as the existing duplicate-metadata check; new module-
   docstring section explaining why.
3. **macOS honest failure** (`audio_capture.py`): `build_microphone_
   capture_command` now raises `AudioDecodeError("unsupported_platform")`
   for non-Windows/non-Linux platforms instead of silently reusing the
   Linux command.
4. **Min-confidence wiring** (`acoustic_ingest.py`, `acoustic_runtime.py`):
   the "no explicit override" fallback now actually reads
   `MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE` via `resolve_birdnet_config()`.
5. **Bounded segment bookkeeping** (`audio_capture.py`):
   `MicrophoneCaptureSession._known_segments` pruned to the current on-disk
   listing every poll.
6. **Zone/Privacy disclosure** (`privacy-ignore-zone-contract.md`,
   `product_repository.py`'s `capture_consent` field description): the
   audio-has-no-Zone-analog gap is now documented and disclosed at the one
   point consent is granted.

Deliberately not built: any new frontend status/health page (see
"Remaining bounded gaps"); new audio-zone geometry; a fifth input path;
speech recognition; a new proprietary model; Local Taxon Prior; any of the
milestone's other explicit scope exclusions. The seven preserved
small-bird-detector files were re-verified untouched (still untracked, no
content change) both before and after this session's work.

## Validation

- **Tier 1/2 (focused)**: every new/modified test run individually first —
  160 tests across the six touched test files, all passing, including 13
  net-new regression tests targeting the specific fixes above. 262
  downstream tests in the six files that consume the shared historical-
  baseline fix (`test_wildlife_journal`, `test_place_activity_report[
  _repository]`, `test_historical_baseline[_repository]`,
  `test_place_biodiversity_summary[_repository]`,
  `test_canonical_new_regular_species_consistency`,
  `test_place_change_summary[_repository]`) all green.
- **Tier 3 (Core gate)**: `python scripts/verify_core.py` — **4608 passed,
  0 failed**, 2 skipped, 23 deselected, 11 xfailed, 1061s (~17m41s).
  Matches the established baseline shape exactly (11 xfailed is the same
  documented `test_stream_playback_contract.py` set every recent milestone
  reports).
- **Full gate**: run given the packaging-script change (the validation
  doctrine's own escalation rule for any change to
  `scripts/build_local_product.py`) — `python scripts/verify_full.py`:
  **4629 passed, 2 failed**, 2 skipped, 11 xfailed, 1199s (~20min). Both
  failures (`test_camera_node_real_process.py::test_real_subprocess_
  serves_health_over_a_real_socket_and_shuts_down_cleanly` and `::test_
  real_subprocess_pings_a_real_watchdog_over_a_real_notify_socket`) are a
  real-subprocess/socket/watchdog test file this milestone never touched
  (zero file overlap with anything changed here). **Confirmed pre-existing
  and environment-specific, not re-assumed from precedent**: stashed
  exactly this milestone's 15 changed/added files by explicit path (never
  touching the seven preserved detector files, verified both by them never
  appearing in the stash and by an exact SHA-256 match before/after the
  full stash-and-restore round-trip), re-ran the same two tests against
  the clean baseline, and got the identical failure
  (`Connection refused` reaching a real subprocess's health endpoint over a
  real socket within 25s). Matches the identical failure signature multiple
  other milestones this same week already independently reconfirmed as
  pre-existing (e.g. Broader Wildlife Maturity v1, same day).
- **Real field acceptance**: see #23 above and the contract doc's dedicated
  section — genuinely run against real hardware, not simulated, with
  results (including a real marginal false positive) reported exactly as
  observed rather than smoothed over.

## Licensing sources (summary; full table in the contract doc)

First-party only, ranked by authority: (1) the license file shipped inside
the exact installed artifact (`birdnetlib/models/analyzer/LICENSE`,
`birdnetlib-0.18.1.dist-info/licenses/LICENSE`, and the four permissive
dependencies' own shipped LICENSE files); (2) the upstream repositories,
fetched live (`github.com/joeweiss/birdnetlib/LICENSE`,
`github.com/kahst/BirdNET-Analyzer` — canonically `birdnet-team/BirdNET-
Analyzer` — README's own "## License" section); (3) the maintainer's
separately-named `birdnet-models-nc-sa` model-metadata repo; (4) package
metadata (`pip show`) for corroboration only, never as the sole source.
No blog posts or third-party summaries were used anywhere in this
decision.

## Remaining bounded gaps (disclosed, not fixed this milestone)

Ranked by importance:

1. **No product-facing acoustic health/status surface.** The backend
   already knows whether the microphone/model is available
   (`BirdNetStatusResponse`, `AudioCaptureStatusResponse`, Doctor's own
   `_gather_acoustic_runtime`); nothing in the frontend shows it anywhere.
   Building this properly needs real new UI (no Doctor page exists for any
   subsystem today, acoustic or otherwise) — judged out of proportion for
   this milestone's "smallest durable representation" instruction. This is
   the natural next acoustic-adjacent follow-up, but it is a frontend
   project, not a bounded fix.
2. **STRICT_WINDOW_MS/POSSIBLE_WINDOW_MS remain field-uncalibrated.** This
   milestone's real hardware acceptance proved the capture/concurrency
   mechanism but did not naturally observe a real simultaneous visual+
   acoustic bird encounter (no natural bird activity was reachable at the
   test site). Still an open field-calibration target, exactly as
   previously disclosed.
3. **Full HTTP-API-driven live-mic-to-Visit-creation flow not re-verified
   live on real hardware.** The existing Windows deployment on the tested
   machine is stale (pre-acoustic, commit `bdb59f5`); a full redeploy was
   judged disproportionate to what this milestone's specific hardware
   probe needed. The underlying mechanism pieces (ffmpeg capture, BirdNET
   inference, concurrent access) are each now independently real-hardware-
   proven; the untested part is purely the plumbing between them, which
   was already extensively unit/injected-fake tested.
4. **Device lifecycle test coverage remains thinner than the visual Camera
   Node's equivalent** (disconnect/reconnect/permission-failure/sample-
   rate-mismatch). Real hardware testing this milestone covers some of
   this territory more genuinely than a mock ever could (bogus-device,
   clean-stop-then-restart, concurrent access) but true mid-session
   physical unplug was not and could not be tested remotely.
5. **Clock-offset-aware association degradation** is unimplemented and
   untested. Low real-world exposure today — Camera Node has zero
   microphone support, so no genuine cross-device clock skew between a
   visual and acoustic source is reachable yet. Revisit if/when Node-side
   audio is ever built.
6. Smaller, explicitly non-blocking items: the acoustic retry ladder's
   third rung (120s) is structurally unreachable given `max_attempts=3` —
   left as-is, a dead config value, not a correctness bug; the host-side
   WAN-transport whitelist already accepts `audio/wav` though no Camera
   Node producer exists yet (worth a look before any future Node-mic
   feature, not urgent now); `ai-edge-litert`'s dist-info ships no bundled
   LICENSE text file, metadata-field-only (immaterial — it's permissively
   licensed either way).

## Confirmations

- The seven preserved small-bird-detector files (`docs/wildlife-detector-
  training-contract.md.orig`, `scripts/evaluate_small_bird_detector.py`,
  `scripts/materialize_wildlife_stage2.py.orig`,
  `scripts/train_wildlife_stage2_rfdetr.py.orig`,
  `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`,
  `tests/test_small_bird_benchmark.py`) are untouched — still untracked, no
  content change, confirmed both before and after this session's work.
- Nothing was pushed. `main` remains local-only, ahead of `origin/main`.
- No schema migration. `CURRENT_DATABASE_SCHEMA_VERSION` stays 53.

## Next milestone (suggested, not started)

Per the remaining-gaps list above, the most natural next acoustic-adjacent
step is a dedicated **acoustic/Doctor product-status surface** (frontend
work: expose `BirdNetStatusResponse`/`AudioCaptureStatusResponse`
somewhere real, likely as part of whatever milestone first builds a
Doctor/health UI at all, since none exists today for any subsystem). This
is offered as one option, not a decision — the next milestone should be
selected against the global remaining-v0.1 queue in roadmap.md, not simply
by adjacency to this one.

**STOP.**
