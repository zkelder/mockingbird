# Contributing to MockingBird

This is the practical, first-hour guide: clone, run, test, and the rules
that keep the product's evidence/truth model intact. For *what the system
is and why*, read [README.md](README.md) and
[docs/product-doctrine.md](docs/product-doctrine.md) first -- this document
assumes that context rather than repeating it.

## Read this much before your first change

1. [README.md](README.md) -- what MockingBird is and what 1.0 supports, plus the
   [support matrix](docs/support-matrix.md) and [developer setup](docs/developer-setup.md).
2. [docs/product-doctrine.md](docs/product-doctrine.md) -- the non-negotiable
   truth model: detection/tracking are infrastructure; only explicit human
   correction creates reviewed truth.
3. [docs/runtime-map.md](docs/runtime-map.md) -- which file owns which
   responsibility, and the production-vs-research boundary, with concrete
   paths.
4. [AGENTS.md](AGENTS.md) -- the full task-packet workflow, conditional
   document router, and safety boundaries. If you are about to touch
   Observation Engine, Camera Node, species suggestions, review/truth, or
   Place Intelligence code, AGENTS.md's routing table points at the one
   focused design document for that area -- read only that one, not
   everything under `docs/`.

Everything else under `docs/` is routed by task, not required up front.

## Clone and set up

Requires Python 3.11+ and Node.js/npm.

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cd web && npm ci && cd ..
```

Optional extras (`classifier-bioclip`, `detector-megadetector`,
`observation-onnx-cuda`) are for specific local model/GPU work only -- the
core product and its test suite need none of them. See
[docs/developer-setup.md](docs/developer-setup.md) if you land here without that context.

## Run the app

```sh
python -m mockingbird
```

This starts one local process serving both the API and the built frontend.
It does not start a camera, monitor, provider, worker, or model. Validate
startup without opening a browser:

```sh
python -m mockingbird --check
```

Check whether a running installation is healthy -- database, storage,
backup, Camera Node, detector model, species identification, GPU/CUDA, and
clock -- in one bounded, privacy-safe report:

```sh
python -m mockingbird doctor
python -m mockingbird doctor --json
```

See [docs/mockingbird-doctor-operational-health-contract.md](docs/mockingbird-doctor-operational-health-contract.md)
for the full check list, severity semantics, exit codes, and JSON shape.

Write a small, bounded, privacy-safe diagnostic bundle to share for support
(Doctor's own report, structural-only Source facts, a redacted recent log
tail, version facts -- never credentials, pairing secrets, or media):

```sh
python -m mockingbird support-bundle
python -m mockingbird support-bundle --output path/to/bundle.zip
```

For frontend-only iteration, run the API and Vite dev server separately
(see "Developer split mode" in [docs/developer-setup.md](docs/developer-setup.md)).

## Run focused tests

Prefer the smallest test surface that covers what you changed; do not run
the full suite for an isolated change (see
[docs/development-workflow.md](docs/development-workflow.md)'s validation
tiers for the full rationale).

**Backend, one file or one test:**

```sh
python -m pytest tests/test_place_activity_report.py
python -m pytest tests/test_place_activity_report.py -k dst_correct
```

**Backend, a tiered gate** (before calling a bounded change or a milestone
complete -- see
[docs/test-suite-validation-tiers-contract.md](docs/test-suite-validation-tiers-contract.md)
for what each guarantees and exactly how long it takes on the reference
development machine):

```sh
python scripts/verify_fast.py   # Tier A: a couple of minutes
python scripts/verify_core.py   # Tier B: the normal milestone gate
python scripts/verify_full.py   # Tier C: full release regression, reserve for RC/release-hardening checkpoints
```

**Backend, the whole suite** (only when a change crosses many runtime
boundaries -- it is large: 3,100+ tests; `scripts/verify_full.py` above is
the same thing with a name that states what it guarantees):

```sh
python -m pytest
```

**Frontend type-check and production build** (required whenever you touch
`web/src`):

```sh
cd web
npm run typecheck
npm run build
```

**Frontend end-to-end** (Playwright; only for the specs your change could
plausibly affect -- each spec boots a real isolated backend + browser, so
this is slower):

```sh
cd web
npm run test:e2e -- <spec-name-substring>
npm run test:e2e            # every spec in web/e2e/
```

Do not invoke `playwright test` directly -- `npm run test:e2e` wraps it
with an isolated temporary data directory and port; the config refuses to
run without that wrapper.

**Lint** (if you have `ruff` installed -- not currently a declared project
dependency, but the convention every commit in this repository's history
follows):

```sh
python -m ruff check <changed .py files>
```

**Before committing anything:**

```sh
git diff --check   # catches stray whitespace/conflict markers
```

## What is production code vs. research/training tooling

Full detail with file lists: [docs/runtime-map.md](docs/runtime-map.md)'s
"Production vs. research code boundary." The short version:

- **Production**: reachable from `python -m mockingbird` (`runtime.py`) --
  `api/`, `repository/`, `storage/`, `motion/`, `monitoring/`, `playback/`,
  `source_providers/`, `species/` (minus `bioclip_evaluation.py`), the
  named production subset of `observation/` (`engine_runtime.py`,
  `camera_node_live.py`, `frame_driven_provider.py`, `onnx_provider.py`,
  and the rest of the accepted-engine pipeline listed in the runtime map),
  and all of `web/src`.
- **Research/benchmark tooling**: reachable only from a `python -m
  mockingbird <subcommand>` CLI branch, a `scripts/*.py` entry point, or
  tests -- most of `observation/` (every `*_cli.py`, `*_benchmark*.py`,
  `*_comparison*.py`, `replay*.py`, `temporal_*.py`), all of `training/`,
  and most of `scripts/`. This code shares production types
  (`observation/contracts.py`) and sometimes the production detector
  deliberately, so a benchmark measures the real thing -- treat that
  sharing as intentional, not as research code leaking into the runtime.
- A model/detector candidate never gains production authority by being
  newer or "looking better" informally -- see "Formal model lifecycle" in
  [docs/architecture.md](docs/architecture.md). If your task is training or
  benchmarking a candidate, work stays in `training/`/`scripts/` until an
  explicit, reproducible incumbent comparison decides otherwise.

## What to never bypass

These are load-bearing, not stylistic:

- **Only explicit human correction creates reviewed truth.** Never make a
  detector, tracker, classifier, admission policy, or language model write
  or imply a `ReviewLabel`/reviewed status. See
  `mockingbird.review_provenance.is_authority_eligible` -- it is the one
  place that decides truth eligibility; do not add a second, ad hoc origin
  check anywhere else.
- **Read/status/preview/dry-run routes stay side-effect free.** Provider
  actions and destructive actions are explicit, bounded, and opt-in.
- **Unknown/abstained outcomes are valid**, not defects to be papered over
  with a guess. Do not fabricate a species, count, or status to fill a gap.
- **Detection Proposals, SpeciesSuggestions, MotionEvidence, and imported/
  external labels remain evidence, never truth**, no matter how confident.
- **A candidate detector/classifier needs a reproducible incumbent
  comparison before any production-authority change** (Phase 2 in
  [docs/roadmap.md](docs/roadmap.md)).
- **Generated media, datasets, exports, caches, model artifacts, and
  checkpoints stay under ignored local paths.** Never commit `data/`,
  build caches, or model weights.
- **Do not weaken the repository-root/test-isolation safety boundaries**
  in `tests/conftest.py` or `AGENTS.md`'s workspace rules -- an automated
  test must never silently fall back to the real product database (see
  [docs/test-repository-isolation-contract.md](docs/test-repository-isolation-contract.md)).
- **Do not add a second implementation of an existing truth-precedence or
  eligibility computation.** Reuse the canonical one (for example
  `ProductRepository._stream_visit_summary_from_models` for Visit truth
  precedence, `mockingbird.wildlife_taxonomy.is_wildlife_category` for
  wildlife eligibility) instead of a locally hardcoded equivalent.

## Task packets (for any non-trivial change)

Before editing, AGENTS.md asks you to state: the roadmap phase, the product
flow improved, why this is next, which files are in scope, explicit
non-goals, and the validation tier. This is not bureaucracy for its own
sake -- it is what keeps a local-first, single-maintainer-reviewable
codebase safe to change quickly. See "Task packet" in
[AGENTS.md](AGENTS.md) and the tier definitions in
[docs/development-workflow.md](docs/development-workflow.md).

## Commit and push workflow

- Verify the repository root, branch, and HEAD before editing (`git
  status`, `git rev-parse HEAD`). The native checkout is authoritative;
  stop rather than proceed under `/mnt/c` in WSL.
- Add a failing focused test before fixing a defect where practical.
- Inspect the exact staged diff before committing (`git diff --check` too).
- Commit messages: an imperative, descriptive title, a body explaining what
  changed and why (and what was tested), following the style already in
  `git log`.
- **Commit locally; do not push** unless a human explicitly asks you to.
  Local `main` running some commits ahead of `origin/main` between
  human-authorized synchronizations is expected, not a mistake to fix.
  Never force-push or rewrite pushed history.

## Getting oriented for a specific change

| I want to... | Start here |
| --- | --- |
| Understand the whole system fast | [docs/runtime-map.md](docs/runtime-map.md), then [docs/architecture.md](docs/architecture.md) |
| Fix a UI bug | The relevant `web/src/pages` or `web/src/components` file; check `web/e2e` for existing coverage first |
| Change Camera Node detection/tracking | Read [docs/candidate-visit-authority-contract.md](docs/candidate-visit-authority-contract.md) first, then `observation/engine_runtime.py` |
| Add a Dashboard/report fact | `analytics/place_activity_report.py`, reusing existing truth-precedence helpers |
| Add a new Source/camera provider | [docs/source-adapter-boundary-design.md](docs/source-adapter-boundary-design.md), then `source_providers/` |
| Run a detector/model benchmark | `python -m mockingbird <subcommand>` -- see [docs/architecture.md](docs/architecture.md) "Formal model lifecycle"; this never touches production behavior by itself |

If you are unsure whether something is production, research, or safe to
change, say so rather than guessing -- the codebase would rather you ask or
mark something as an open question than silently assume.
