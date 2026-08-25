# v0.1 Representative Field Acceptance & Release-Budget Closure v1

**Status: C — GATE REMAINS OPEN DUE TO INSUFFICIENT REPRESENTATIVE EVIDENCE.**
**Deferred by explicit user decision before a live session started — not a
product defect, not a FAIL.**

This milestone set out to answer, with real field evidence, whether the
frozen MockingBird production stack can observe ordinary real wildlife with
enough recall/precision/coherence/latency/stability for a first public
release. It did not reach a live session. This report records what was
verified, exactly where and why the attempt stopped, and the standing
decision for how future sessions should handle the same blocker.

## What happened, in order

1. **Pre-flight verification** — branch `main`, HEAD `941f46b`, matching the
   expected starting state exactly. `git status --short` showed the seven
   intentionally preserved untracked detector files plus one additional
   untracked `uv.lock`.
2. **`uv.lock` investigated, not assumed** — zero history on any branch
   (`git log --all -- uv.lock` empty), no `.gitignore` entry, no
   `[tool.uv]` in `pyproject.toml`, and CI (`ci.yml`)/`CONTRIBUTING.md`/
   `README.md` all consistently document a plain `python -m venv .venv` +
   `pip install -e ".[...]"` workflow with zero mention of `uv` as project
   tooling. Absent from all five sibling worktrees. mtime was the same
   morning, consistent with an incidental `uv` invocation rather than
   intentional lockfile maintenance. **Decision A executed**: removed the
   untracked root `uv.lock`. Working tree now shows exactly the seven
   preserved files, matching the expected pre-flight state.
3. **Concurrency check** — several long-lived (2h-19h old) interactive
   `ccd-cli` peer sessions share this working tree
   (`mockingbird-active-{07,96,93,f2,04,17,2a}` per `ListAgents`). No
   `.git/index.lock`, no unexpected working-tree drift across repeated
   `git status --short` checks before/after this session's work. Treated as
   idle per "idle/read-only sessions are not automatically blockers" —
   no evidence of an active concurrent writer.
4. **Governing docs read** — `docs/release-execution-state.md` and
   `docs/product-doctrine.md` in full.
5. **Phase 1 archaeology (two parallel read-only agents)** confirmed and
   catalogued the existing accepted acceptance/replay tooling in detail —
   `acceptance_recorder.py` (capability-safe frame tee,
   `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR` + three optional overrides),
   `perception_regression_cli.py`, the counterfactual-ledger endpoint
   (`GET .../observation/counterfactual`), `scripts/run_encounter_
   accounting.py`, and the standing field-acceptance funnel methodology
   from `end-to-end-bird-encounter-recall-closure-v1-report.md`
   (independent encounter denominator, built and reviewed *before* opening
   the product's own Visit list, then mapped stage-by-stage). Confirmed:
   **no accepted numeric release budget exists yet** for recall/false-Visit
   rate/fragmentation/latency/coverage — `roadmap.md`'s own "Numeric release
   budgets" section states this explicitly ("a measurement, not yet an
   accepted budget"). This governed Phase 4 of the milestone brief: any
   budget this session could have reported would necessarily have been
   *provisional*, not a governed threshold.
6. **Real Camera Node reachability reconfirmed** — `192.168.1.112:8787`:
   ICMP ping succeeded (3/3, 8.6-77.6ms), raw TCP connect to port 8787
   succeeded, and an HTTP probe returned a genuine `{"detail":"Not Found"}`
   from a real running service (confirms a live app, not a dead host —
   exact route paths were not probed further since this is out of scope
   without a live session).
7. **Real native-Windows Host reconfirmed healthy** — an already-running
   verified dev deployment was found at `f609c89` (`deploy_windows_dev.py
   --status`), independently confirmed via direct HTTP (not the deploy
   tool's own report alone): `GET /api/product/instance` →
   `git_commit: f609c89...` exact match; `GET /api/product/health` →
   `ready: true`, `database_schema_version: 53` (matches expected schema
   v53), `configured_stream_count: 1`, `monitored_stream_count: 0`. `git
   diff --stat f609c89..941f46b` confirmed the two commits differ only in
   two documentation files (114 lines, 0 source/schema changes) — so this
   running instance is runtime-equivalent to current HEAD.
8. **Relaunched the existing verified `f609c89` artifact** (not a rebuild —
   `--artifact` against the already-materialized, already-ledgered release
   directory) with the acceptance-recorder environment variables wired in
   (`MOCKINGBIRD_DEV_ACCEPTANCE_RECORDING_DIR`,
   `_INTERVAL_MS=1000`, `_MAX_FRAMES=5500`, `_MAX_BYTES=4950000000`,
   matching the established ~90-minute-cohort methodology exactly, not
   re-derived). Old process (PID 12276) stopped, new process (PID 10536)
   launched; identity reconfirmed unchanged (`instance_id` identical,
   `git_commit` identical, schema v53, `ready: true`). This relaunch is
   otherwise inert: the recorder only activates if an Observation session
   is actually started, which did not happen. No code, config, model,
   threshold, or auth behavior was changed by this step — only which OS
   process is currently serving the identical accepted build.
9. **Blocked on real authentication before any session-relevant action.**
   `GET /api/product/instance` and `GET /api/product/health` are
   intentionally public and worked without a session. Every endpoint this
   milestone actually needs — `GET /api/streams`, `GET .../observation/
   status`, `POST .../observation/start`, `GET .../observation/
   counterfactual`, `GET /api/visits` — returned `401 {"detail":"Sign in to
   continue."}`. This is expected, correct, current behavior: the accepted
   Local Identity / Multi-User work (2026-08-23) removed the pytest auth
   bypass, and no credentials for the existing
   administrator account are stored anywhere in this repository (correctly
   — they should not be). `POST /api/auth/sign-in` (`SignInRequest` →
   session cookie) is the real, working mechanism; it was located but never
   called.
10. **Asked the user** how to get authenticated access (share existing
    credentials / create a fresh account for me / drive it themselves).
    **The user declined all three** and gave an explicit standing
    instruction: do not modify or weaken production authentication; do not
    require them to sign in, share credentials, start/stop monitoring,
    review Visits, or interact with the UI unless a future milestone
    specifically requires human acceptance and they explicitly agree to
    participate; stop the live attempt now; return this milestone as
    OPEN/DEFERRED rather than a failure; make no perception changes;
    reconcile docs only for durable evidence already produced; continue
    with autonomous (non-live-field) development work next.

No Observation session was ever started. No Visit, evidence, review, or
account data was read, created, or modified. No source, model, threshold,
schema, or authentication code was touched.

## Why this is not treated as FAIL

The milestone brief itself distinguishes an insufficient-evidence gate from
a failed one: *"An OPEN acceptance result is valid,"* and *"Do not let an
empty-denominator field session trigger another perception redesign."* Here
the denominator is not merely small — it is zero, because the session never
started, by the user's explicit choice, for a reason (authentication/
consent) that has nothing to do with detector, tracker, admission, Visit,
evidence, or classifier behavior. Nothing about the frozen production stack
was exercised, so nothing about it can be judged. That is exactly the
"insufficient denominator" case, not a "release-blocking defect."

## Standing decision for future sessions (recorded so this is not re-litigated blindly)

1. Do not ask the user again for real admin credentials, nor to
   interactively sign in, start/stop monitoring, or review Visits, unless a
   future milestone specifically requires human acceptance and they
   explicitly agree to participate first.
2. For ordinary development/validation work that needs authenticated API
   access (not a live field-acceptance session), use a fresh, isolated
   MockingBird dev instance/dev root and bootstrap a disposable local
   Administrator account programmatically or through the normal first-run
   flow; use those temporary credentials only for that instance; leave it
   disposable.
3. A genuine representative field-acceptance session additionally needs the
   real paired Camera Node and real human review participation, which a
   fresh disposable instance cannot supply — that specific milestone
   remains gated on the user's availability/agreement to participate live,
   not on a technical workaround.

## What remains true and unaffected

- Frozen production stack, schema v53, accepted HEAD unchanged.
- Real Camera Node (`192.168.1.112:8787`) is reachable at the network
  level right now.
- The real native-Windows Host dev deployment is healthy at the accepted
  commit right now.
- The full accepted acceptance-tooling chain (recorder → motion-screen/
  contact-sheet review → independent encounter table → counterfactual
  ledger → `run_encounter_accounting.py` → hand-written report) is
  confirmed present, understood, and ready to reuse verbatim whenever a
  live session is actually authorized.
- No numeric release budget for Gate A exists yet in governing docs; that
  remains true and is unrelated to this session's outcome.

## Gate classification

Per the milestone's own required scale:

**C — Gate remains open due to insufficient representative evidence.**

Not D: no reproduced defect exists anywhere in the frozen perception,
admission, Visit, evidence, or classification stack — none of it was
exercised. Not A/B: no live evidence was gathered at all this session.

## Validation

No production code changed. `git diff --check` is not applicable (no
tracked source diff beyond this report and the execution-state
reconciliation, both prose). Core/replay/regression suites were not run —
per Phase 25, a purely observational session with no production code
change does not warrant running Core.

## Preserved-file verification

All seven intentionally preserved untracked files remain present, untouched:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

## Push state

Nothing pushed. Local accepted state only.
