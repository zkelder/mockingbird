# MockingBird

MockingBird is a local-first outdoor video intelligence platform.

Users connect outdoor camera or media Sources, view Streams, draw meaningful
Zones, monitor outdoor activity, review Events/Visits, correct labels or
species, and build useful local history, exports, and analytics over time.

The first vertical is backyard bird-feeder monitoring and species review. The
broader product covers wildlife, yard activity, pets, people, vehicles,
feeders, birdbaths, driveways, Privacy Zones, and Ignore Zones.

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

connect Source -> view Stream -> draw Zones -> analyze outdoor activity ->
review Events/Visits -> correct labels/species -> export datasets and analytics.

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
- a shared Dashboard and Cameras/Streams Live Camera Overview that defaults to
  the latest safe Visit evidence, opens at most four user-selected live tiles
  per browser session, and shows view-only Stream Zones without changing
  monitoring or creating evidence

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

## Active development checkout

Active MockingBird development is WSL-native at
`/home/zkelder/projects/mockingbird-active`. Cross-install restore completed
successfully. Windows DirectShow uses a locally configured Windows
`ffmpeg.exe`; native controls and a daylight 3840 x 2160 capture were verified
from WSL. Driver-managed exposure values are not readable or persisted by
MockingBird, so local exposure calibration remains field setup rather than an
application feature. Representative field-truth collection is next. Installing
Playwright Chromium in WSL remains an optional local environment task.


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

Windows users can open `Start MockingBird.cmd`. The cross-platform command is:

```sh
python -m mockingbird
```

The launcher checks the frontend and local database, starts one local-only app
process, reuses an already-running healthy instance, and opens the browser when
ready. It does not start a camera, monitor, provider, worker, or model.

Validate startup without launching the server or browser:

```sh
python -m mockingbird --check
```

### Optional Camera Node

On a Raspberry Pi or ordinary Linux edge device, start the separately bounded
Node manually with `python -m mockingbird_node`. It prints a short-lived pairing
code to that device's local console. In **Add Camera**, choose **MockingBird
Camera Node**, enter an explicit LAN IP address and that code, then choose one
advertised camera view. Pairing credentials remain local and masked; previews
are transient and monitoring stays off until explicitly enabled. There is no
automatic LAN discovery, service installer, remote shell, cloud relay, audio,
or recording. See [Camera Node boundary](docs/camera-node-boundary-design.md).

### Optional local species suggestions

The current BioCLIP 2 path is a local reviewer-assistance action inside the
existing Review Queue, not an automatically enabled production classifier.
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

Backend suite:

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

Focused feature contracts remain under `docs/` and are routed by `AGENTS.md`.

## Not the product center

MockingBird is not centered on Windows USB scripts, PowerShell, CLI operation,
ROI terminology, interval analysis, snapshot loops, debug internals, or one
camera/provider adapter. Those may exist as implementation details; the product
is the Stream, Zone, activity, review, correction, Bird Log, export, and
analytics experience.
