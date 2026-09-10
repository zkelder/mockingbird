# MockingBird

MockingBird is a local-first, hardware-agnostic, bird-first but
wildlife-native nature observatory that helps people notice, understand,
confirm, and remember wildlife around a place. It is not primarily an NVR, a
surveillance platform, a camera-management product, an ML demo, or a
species-classifier appliance -- see
[docs/product-doctrine.md](docs/product-doctrine.md).

Users connect outdoor camera or media Sources, view Streams, draw meaningful
Zones, monitor outdoor activity, review Events/Visits, correct labels or
species, and build useful local history, exports, and analytics over time.

The first vertical is backyard bird-feeder monitoring and species review. The
broader product covers wildlife, yard activity, pets, people, vehicles,
feeders, birdbaths, driveways, Privacy Zones, and Ignore Zones.

Just want to install and use MockingBird? See
[docs/using-mockingbird.md](docs/using-mockingbird.md) -- install, first-run
setup, add a camera, start observing, review, and backup/restore, with no
assumed Python/command-line knowledge. This README is the developer/source
checkout guide.

## Product principles

- Streams and Zones are the center of the experience.
- Detections, suggestions, motion, and external labels are evidence, not truth.
- Explicit user correction creates reviewed dataset-grade truth.
- Bird Log, reviewed analytics, classifier readiness, and reviewed-only exports
  derive from corrections.
- Source adapters stay underneath the shared product model.
- Storage, review data, exports, and recovery are local-first.
- Camera, provider, model, and destructive actions are explicit and bounded.

Core flow:

Observe → Discover → Understand → Confirm → Remember → Improve.

This user-facing loop is supported by Sources and Streams, Zone-aware activity,
reviewed corrections, Bird Log, local exports, and analytics. Detector and
SpeciesSuggestion output remain evidence, never a claimed observation.

## Current product checkpoint

MockingBird currently provides:

- one same-origin local application with startup/schema validation and graceful
  shutdown
- durable Sources, Streams, and user-authored Zones
- browser-playable, RTSP, Linux local-USB, and Windows DirectShow live-camera
  paths when the configured host capabilities are available
- one explicit backend-owned in-memory live camera session per Stream for Live
  view, capture, and monitoring
- zone-aware live motion with Privacy/Ignore suppression, bounded activity
  bursts, one-best-frame evidence, and optional needs-review candidate creation
- Review Queue correction, reviewed-only Bird Log, analytics, dataset exports,
  and classifier-readiness views
- explicit manual media, external still-image, folder/trail-cam, and
  metadata-only webhook evidence workflows under the same review model
- optional local analyzer evidence, including a user-supplied MDv5 path and a
  one-item-at-a-time BioCLIP 2 local species-suggestion action with a
  default-off automatic post-activity assist; no model weights are bundled or
  downloaded automatically
- verified local database-and-managed-media backup, import, download, and
  rollback-safe restore
- Storage & Retention controls that default off, preview policy-selected media,
  preserve review/export context, and move cleanup candidates to recoverable
  local quarantine before any later expiry purge
- default-off durable monitoring policy/runtime-checkpoint records and
  side-effect-free lifecycle status
- guided Add Camera and in-place Edit Camera Setup paths that keep credentials
  local and masked, check readiness without contacting a camera, preview
  monitoring impact, and finish on the Stream view
- an optional local-LAN MockingBird Camera Node package for paired bounded
  snapshots from an edge camera, with no cloud relay, discovery, remote shell,
  recording, audio, or automatic monitoring
- one unified Stream-scoped **Start observing** / **Stop observing**
  Observation panel that works the same way for every currently-supported
  Stream type -- a paired Camera Node reuses the accepted frame-driven
  Observation Engine with its conservative candidate-quality check before
  anything reaches Review Queue, RTSP/local USB/Windows DirectShow Streams
  reuse the existing durable monitoring policy, and remaining external
  still-image Streams reuse the existing Snapshot monitor -- with plain
  camera/observation health, a sanitized failure reason, and collapsed
  advanced diagnostics; a Stream with no integrated observation runtime
  reports that honestly instead of a Start button that would only fail; no
  CLI acceptance tooling required for normal use
- a shared Dashboard centered on Today in Your Yard: detector-qualified animal
  Visits, reviewed discoveries, best evidence-backed moments, Zone/hour context,
  bounded confirmation work, and compact observation health; it remains
  read-only and never changes monitoring or creates evidence
- a guided first-run setup wizard shown only for a genuinely new local
  installation (welcome, local storage location/status, guided Add Camera,
  and Observation readiness), never re-shown to an existing installation; a
  consolidated basic product-health summary on the Dashboard (storage,
  cameras needing attention, observation counts, backup status, app
  version); and a self-contained Windows local-product bundle with no
  Python/pip/npm knowledge required to run it -- see
  [docs/using-mockingbird.md](docs/using-mockingbird.md) and
  [docs/local-product-packaging-design.md](docs/local-product-packaging-design.md)

Monitoring remains local and explicitly Stream-scoped. Every Stream starts
disabled; when a user enables supported backend-owned live monitoring, the one
app-owned supervisor restores that saved intent after startup, waits for a
healthy frame before evaluation, and uses bounded recovery. Enable/disable and
retry remain explicit, status reads have no side effects, and monitoring never
creates reviewed Bird Log truth.

Local Data also keeps storage maintenance separate from the product loop.
Automatic cleanup is off by default; it performs a fresh bounded local policy
pass only when enabled, never accepts browser-supplied media lists, and shares
the local maintenance window with backup and restore work.

## Start the local app

Requires Python 3.11+ and Node.js/npm for the initial frontend build.

Create a virtual environment and install the API with test dependencies:

```sh
python -m venv .venv
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Install frontend dependencies:

```sh
cd web
npm ci
cd ..
```

Windows users can open `Start MockingBird.cmd`; Linux/macOS checkouts can run
`./start-mockingbird.sh`. Both find the local virtual environment
automatically and launch the same unified runtime. The cross-platform command
is:

```sh
python -m mockingbird
```

A normal user with no development checkout does not run any of the above --
see [docs/using-mockingbird.md](docs/using-mockingbird.md) for the
self-contained Windows bundle (`scripts/build_local_product.py` builds it;
[docs/local-product-packaging-design.md](docs/local-product-packaging-design.md)
documents the packaging decision).

The launcher checks the frontend and local database, starts one local-only app
process, reuses an already-running healthy instance, and opens the browser when
ready. It does not start a camera, monitor, provider, worker, or model.

Validate startup without launching the server or browser:

```sh
python -m mockingbird --check
```

### Optional Camera Node

On a Raspberry Pi or ordinary Linux edge device, start the separately bounded
Node manually with `python -m mockingbird_node`, or install it as a
supervised, boot-persistent `systemd` service with
`scripts/install_camera_node.py` -- see the
[Camera Node install guide](docs/camera-node-install-guide.md). Either way it
prints a short-lived pairing code to that device's console (or its journal).
In **Add Camera**, choose **MockingBird Camera Node**, enter an explicit LAN
IP address and that code, then choose one advertised camera view. Pairing
credentials remain local and masked; previews are transient and monitoring
stays off until explicitly enabled. There is no automatic LAN discovery,
remote shell, cloud relay, audio, or recording, and the host cannot trigger
or run the installer remotely. See
[Camera Node boundary](docs/camera-node-boundary-design.md).

### Start observing wildlife

Every configured Stream shows the same **Observation** panel, and it works
the same way no matter which camera type is underneath: open that camera's
Stream page and use **Start observing**. No CLI tool is required for normal
use. The panel shows plain camera/observation health (Ready, Observing, or
Needs attention with a plain-language reason and the relevant setup action)
and **Stop observing** always cleanly stops it.

- Once a Camera Node is paired, **Start observing** runs the accepted
  Observation Engine. The packaged native-Windows product
  (`scripts/build_local_product.py`) already includes the default model
  bundle and GPU runtime, so a normal packaged install needs no manual
  setup; a development checkout still needs the local model bundle
  configured (see [Optional ONNX Runtime CUDA
  replay](#optional-onnx-runtime-cuda-replay) below for that one-time local
  setup). A useful wildlife moment appears in Review Queue only when it
  clears a conservative evidence-quality check; a quiet or distant scene
  honestly shows no candidates rather than a low-value one.
- For an RTSP, Linux local USB, or Windows DirectShow Stream, **Start
  observing** arms the existing durable monitoring policy (the same
  continuity that already survives a restart).
- For a Source configured with a plain still-image URL, **Start observing**
  starts the existing Snapshot monitor.
- A Stream with no integrated observation runtime (for example manual media
  or an unconfigured Source) reports that honestly instead of a Start
  button that would only fail.

Advanced technical detail (which runtime is underneath, provider ids,
durable-monitoring state) stays in one collapsed "Advanced diagnostics"
section. See
[observation-engine-product-control-contract.md](docs/observation-engine-product-control-contract.md)
for the accepted engine this panel wraps for Camera Node, and
[unified-observation-panel-contract.md](docs/unified-observation-panel-contract.md)
for the panel itself and the current provider support matrix.

### Optional ONNX Runtime CUDA replay

The Stage 3 accelerated provider is an offline, shadow-only benchmark path. Core
MockingBird and the Snapshot provider do not require ONNX Runtime. On a compatible
NVIDIA/CUDA development host, install only the GPU extra:

```sh
python -m pip install -e ".[observation-onnx-cuda]"
```

Supply an existing local ONNX file through its versioned model-bundle JSON; the
application never downloads a model. Then run:

```sh
python -m mockingbird replay-benchmark \
  --provider onnx-cuda \
  --frames data/replay/frames \
  --manifest data/replay/benchmark.json \
  --provider-config data/models/detector/model-bundle.json \
  --output data/replay/output
```

`CUDAExecutionProvider` is mandatory and CPU fallback is rejected. This provider
emits detector evidence only; it does not start cameras or monitoring, track
animals, create Visits, or write product truth. See the
[ONNX CUDA shadow-provider contract](docs/onnx-cuda-shadow-provider-contract.md).

Stage 4 uses a separate portable provider configuration that names the model
bundle and bounded source-time detector/tracker settings:

```sh
python -m mockingbird replay-benchmark \
  --provider frame-driven-onnx-cuda \
  --frames data/replay/frames \
  --manifest data/replay/benchmark.json \
  --provider-config data/models/observation-frame-driven/provider-config.json \
  --output data/replay/frame-driven-output
```

This path adds continuous analysis-frame tracking and shadow-only Visit proposals
inside deterministic replay. It still starts no camera, live monitor, Camera Node,
or production Visit handoff. See the
[frame-driven shadow-provider contract](docs/frame-driven-shadow-provider-contract.md).

Stage 5 adds a separate live-shadow adapter for an already paired Camera Node. It
uses one authenticated, frame-bounded multipart-JPEG analysis stream and a
profile-bound one-frame evidence burst. The PC keeps at most the newest bounded
work, applies Privacy/Ignore masking before ONNX CUDA inference, tracks source-time
frames, and emits temporary shadow evidence only. This shadow-only CLI path does
not start through the normal application launcher or create product records; the
same pipeline reachable from **Start observing** on the Stream page (see above)
is the app-owned, bounded, explicitly-activated production path. See the
[Camera Node live-shadow contract](docs/camera-node-live-shadow-contract.md).

### Optional local species suggestions

The current BioCLIP 2 path is a local reviewer-assistance action inside the
existing Review Queue, not an automatically enabled production classifier.

**A normal packaged Windows build (`scripts/build_local_product.py`) needs
none of this setup.** It already installs the complete BioCLIP runtime
dependency closure and, when a local bundle is available at build time
(`--bioclip-bundle-source`, defaulting to `data/models/bioclip-2/`), the
model/labels/embedding-cache bundle itself -- both durably, inside the
release, surviving a restart or an ordinary redeploy with no environment
variable to set by hand. See "BioCLIP runtime packaging" in
docs/local-product-packaging-design.md for the full design. The setup below
is for a development checkout running directly from source instead of a
packaged build.

Install its optional runtime with:

```sh
python -m pip install -e ".[classifier-bioclip]"
```

Configure these paths in the environment that launches MockingBird:

- `MOCKINGBIRD_BIOCLIP_MODEL_PATH`: existing local BioCLIP model directory
- `MOCKINGBIRD_BIOCLIP_LABELS_PATH`: frozen local/seasonal candidate labels
- `MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH`: matching precomputed text
  embeddings

For the supported desktop-local baseline, use the official Imageomics
[`imageomics/bioclip-2`](https://huggingface.co/imageomics/bioclip-2) artifact
version `1.0.0`, pinned to revision
`2957b322090f9cb17ae72c71981c7218a28d81e0`. Its
`open_clip_model.safetensors` SHA-256 is
`b7b2bf6fbc95799e42630e394cf95803892ab447c1a8ab629dbc82fbeaf7dfef`;
the model card licenses it under MIT. Obtain that single artifact manually from
the official model source into an ignored local cache, verify the digest before
configuration, and keep its accompanying `open_clip_config.json` beside it.

Build the frozen cache only after choosing the bounded existing MockingBird bird
taxonomy. This explicit setup command accepts local artifacts only, sets offline
mode before loading OpenCLIP, and neither downloads anything nor runs from a
review request:

```sh
python scripts/prepare_bioclip_candidate_cache.py \
  --model-dir data/models/bioclip-2 \
  --labels-path data/models/bioclip-2/mockingbird-bird-candidates.txt \
  --embedding-cache-path data/models/bioclip-2/mockingbird-bird-candidates.npz \
  --model-weights-sha256 b7b2bf6fbc95799e42630e394cf95803892ab447c1a8ab629dbc82fbeaf7dfef
```

The labels file contains the selected application taxonomy display names, with
scientific names retained when they exist in that taxonomy. Updating labels or
the model requires an explicit rebuilt cache and produces new pending evidence;
all of these local files remain ignored. Configure the three environment
variables in the environment that launches MockingBird, never in a frontend or
API request.

The optional extra stays on the tested OpenCLIP 3.3 runtime line. The app never
downloads artifacts or generates embeddings during a review request. A manual
run, or the default-off assist for a newly completed review Visit, creates ranked,
explicitly uncalibrated `SpeciesSuggestion` evidence only;
submitting a correction remains the sole species-truth action. Runtime package
versions and artifact digests are retained with the evidence for reproducible
evaluation. Each future user-triggered manual run also retains one durable
attempt record with its outcome, duration, exact crop, complete ordered
candidate bank and scores when returned, and sanitized failure context. The
assist never backfills history, retries an existing attempt, or creates truth.

### Batch Review Queue species suggestions

Review Queue can select up to 25 visible unresolved bird Visits for a local batch.
The browser validates those Visit IDs, then calls the established single-Visit
BioCLIP assistant sequentially, so the already-loaded local runtime is reused
without a general scheduler or one long-running batch request. Cancellation stops
scheduling additional Visits after the current one completes. Each result retains
its own crop-first MediaAsset provenance and remains suggestion evidence; only an
explicit correction writes reviewed truth.

Evaluate already-stored BioCLIP suggestions against final ReviewLabel
corrections without running a model or writing product state:

```sh
python scripts/evaluate_bioclip_field_truth.py
python scripts/evaluate_bioclip_field_truth.py --json-output data/evaluations/bioclip-field-truth.json
```

The command opens local SQLite storage in query-only mode, keeps JSON reports
under the ignored `data/` tree, and labels candidate-relative scores and
incomplete historical attempt coverage explicitly.

## Developer split mode

Run the API:

```sh
python -m uvicorn mockingbird.api.main:app --reload
```

Run the frontend from `web/`:

```sh
npm run dev
```

The Vite development server proxies same-origin API requests to the local API.
The production build is served by the single MockingBird application process.

## Validation

Backend suite (see
[docs/test-suite-validation-tiers-contract.md](docs/test-suite-validation-tiers-contract.md)
for the tiered `scripts/verify_fast.py`/`verify_core.py`/`verify_full.py`
gates and what each guarantees):

```sh
python -m pytest
```

Frontend type-check and production build:

```sh
cd web
npm run typecheck
npm run build
```

Validation tiers and reporting rules live in
[docs/development-workflow.md](docs/development-workflow.md). Hardware/model
checks are opt-in and must not be required for the normal non-hardware gate.

## Local data

Defaults:

- database: `data/mockingbird.sqlite3`
- managed imported media: `data/media/imports/`
- verified backups: `data/backups/`

Useful overrides:

- `MOCKINGBIRD_DB_URL`
- `MOCKINGBIRD_MEDIA_ROOT`
- `MOCKINGBIRD_BACKUP_ROOT`

The `data/` tree is ignored. Generated exports, captured media, benchmark data,
model artifacts, caches, and training workspaces must remain in ignored local
paths and must not be committed.

## Documentation map

- [docs/using-mockingbird.md](docs/using-mockingbird.md): normal-user guide
  (install, first run, add a camera, start observing, review, backup/restore)
- [docs/local-product-packaging-design.md](docs/local-product-packaging-design.md):
  first-run/packaging contract and the Windows packaging decision
- [AGENTS.md](AGENTS.md): task packets, universal guardrails, and conditional
  document routing
- [docs/product-doctrine.md](docs/product-doctrine.md): non-negotiable product
  identity and truth model
- [docs/roadmap.md](docs/roadmap.md): current priorities and sequencing
- [docs/roadmap-history.md](docs/roadmap-history.md): concise completed-phase
  record
- [docs/glossary.md](docs/glossary.md): canonical domain terms
- [docs/architecture.md](docs/architecture.md): current component, data-flow,
  storage, and lifecycle boundaries
- [docs/development-workflow.md](docs/development-workflow.md): validation tiers
  and change workflow
- [docs/runtime-map.md](docs/runtime-map.md): concrete file-level ownership map
  and the production-vs-research code boundary
- [CONTRIBUTING.md](CONTRIBUTING.md): practical setup, test, and commit workflow
  for a first-time contributor

Focused feature contracts remain under `docs/` and are routed by `AGENTS.md`.

## Not the product center

MockingBird is not centered on Windows USB scripts, PowerShell, CLI operation,
ROI terminology, interval analysis, snapshot loops, debug internals, one
camera/provider adapter, or NVR/security-platform framing. Those may exist as
implementation details; the product is the Stream, Zone, activity, review,
correction, Bird Log, export, and analytics experience -- see "Detection is
infrastructure" in [docs/product-doctrine.md](docs/product-doctrine.md) for
why detection sophistication is not the goal by itself.

## License

MockingBird's own source code is licensed under the [MIT License](LICENSE).

This covers MockingBird's own code only. Third-party components MockingBird
redistributes or depends on -- including the bundled MDv5a and BioCLIP-2
model weights, and the optional BirdNET bird-sound identification feature
MockingBird deliberately does **not** bundle -- are licensed under their own
separate terms, not necessarily MIT, and remain governed by those terms.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for the complete
account of what is bundled, what is not, and under what license.
