# MegaDetector Local Setup Checklist

## Purpose

This checklist prepares a local optional MegaDetector runtime test without changing core MockingBird behavior.

Use it before any real local MegaDetector install, model-path configuration, or manual smoke test. The goal is to keep the core app usable, keep model files out of source control, and preserve the truth boundary: detector output is evidence until a user reviews and corrects it.

Phase 23 implements this as an optional explicit Review Queue verifier using the
official `megadetector` package. The earlier PyTorch-Wildlife path remains
archived; see [megadetector-runtime-findings.md](megadetector-runtime-findings.md).

## Safety Rules

- No model files are committed.
- No automatic downloads are added.
- No runtime dependency is added to the core install.
- No camera/source adapter work is included.
- No video frame extraction is included.
- No background worker is included.
- No species classifier is included.
- Outputs are `DetectionProposal` evidence only.
- User corrections remain dataset truth.

## Local Install Boundary

Install the optional runtime only in the local MockingBird environment:

```sh
pip install -e ".[detector-megadetector]"
```

This installs the official `megadetector` package only through an explicit
optional extra. The core install continues to work without it. Installation may
create package settings outside the repository, so check the worktree before
committing.

Do not pass known model aliases to the package. MockingBird requires an existing
local MDv5 `.pt` file and passes a resolved path with forced downloads disabled.

## Model File Location

Use an ignored local path for model files, such as:

- `data/models/megadetector/`
- another local path outside Git-tracked source

The `data/` directory is ignored. Never place model files under `src/`, `docs/`, `tests/`, or `web/`.

Never commit `.pt`, `.pth`, `.onnx`, `.weights`, or `.engine` files.

## Environment Variables

- `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`: explicit local path to an MDv5 `.pt` model file.
- `MOCKINGBIRD_MEGADETECTOR_LABELS_PATH`: reserved optional metadata path; the fixed MDv5 category map does not require it.
- `MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD`: optional local confidence threshold for proposal evidence filtering.

These variables configure the optional adapter runtime only. They do not change reviewed truth, exports, coverage, QA, analytics, or normal app startup.

## Pre-Run Checks

- Core app starts without the optional dependency installed.
- Model Adapters page shows MegaDetector as `not_configured` by default.
- `git status --short --untracked-files=all` shows no model artifacts.
- A saved Review Queue best frame or imported image exists for the explicit adapter run.
- No camera or live video is involved.
- The local model path is under `data/` or another ignored path.

## Local Smoke Test

Manual smoke test:

1. Install the optional extra locally.
2. Place the model under an ignored local path.
3. Set the MegaDetector environment variables.
4. Start the API and frontend.
5. Import a test image.
6. Open the Review Queue candidate and run identification assist explicitly.
7. Confirm a `DetectionRun` and `DetectionProposal` records are created.
8. Confirm no `Event`, `Visit`, or `ReviewLabel` is created until proposal conversion.
9. Convert a proposal.
10. Correct the visit label.
11. Export the dataset.
12. Confirm the export uses the corrected label as truth.

## Failure Expectations

- Missing model-path environment variable -> `not_configured`.
- Missing optional dependency -> `unavailable`.
- Missing or non-`.pt` model file -> `unavailable`.
- Unsupported media -> clear 400.
- Runtime failure -> no truth writes.
- Empty detections -> no proposals or a completed run with a clear note, depending on implementation.

## Rollback

- Unset `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`.
- Uninstall the optional extra if needed.
- Delete ignored local model files.
- Existing proposals remain evidence records.
- Reviewed corrections and exports remain intact.
- Core app continues working.

## Commit Safety Checklist

Run:

```sh
git status --short --untracked-files=all
find . -type f \( -name "*.onnx" -o -name "*.pt" -o -name "*.pth" -o -name "*.weights" -o -name "*.engine" \) -not -path "./.venv/*" -not -path "./web/node_modules/*" -print
```

Expected result:

- no model artifacts listed
- no model artifacts staged or tracked

## Explicit Non-Goals

- no production accuracy claims
- no species classifier
- no camera adapters
- no live video
- no frame extraction
- no background worker
- no automatic downloads
- no committed model weights
- no cloud
