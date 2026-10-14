# Portfolio Demo Walkthrough

A reproducible way to experience the whole MockingBird loop --
**Observe → Discover → Understand → Confirm → Remember → Improve** -- without a
bird appearing in front of a live camera.

## What this demo is (and is not)

- **Real pipeline, public-domain footage.** Three CC0 (public-domain) recorded
  clips from Wikimedia Commons are imported and analyzed by the *unmodified*
  production path: recorded-video import, the real MegaDetector v5a Observation
  Engine (GPU), tracking, Visit admission, and the real BioCLIP 2 identification
  assistant. The Visits are the detector's genuine output on that footage.
- **Nothing is pre-confirmed and nothing is fabricated.** The script never
  writes a review decision. Species results are *suggestions*; you confirm or
  correct them in the Review Queue.
- **Conspicuously isolated.** It runs in a throwaway instance with its own
  `MOCKINGBIRD_HOME`. The instance is named "MockingBird DEMO - public-domain
  sample clips" (visible in the sidebar and on the sign-in screen), the camera
  is named "DEMO sample clips (recorded, not a live camera)", and every clip's
  notes say it is a demo. The script **refuses** to run against an instance that
  already holds a real camera.
- **Not a live-camera or Camera Node demo, and not an accuracy claim.** Three
  clips say nothing about how well MockingBird identifies birds.

The clips ([manifest with authors, licenses and SHA-1 hashes](demo/demo-media-manifest.json)):

| Clip | What it shows | Author |
|---|---|---|
| Northern mockingbird feeding juveniles (10 s) | the project's namesake; several birds in one encounter | auburn |
| Pileated woodpecker at a suet feeder (26 s) | a species **outside** the bundled candidate list | 5shot |
| American goldfinches at a birdbath (80 s) | two birds; the model declines to name them | J. M. Pearson |

## Prerequisites

- An NVIDIA GPU (live detection is GPU-only; see the
  [support matrix](support-matrix.md)) and the detector + BioCLIP model files.
  The packaged Windows ZIP carries them; a source checkout needs them set up per
  [developer-setup.md](developer-setup.md).
- `ffmpeg` on `PATH` (used to transcode the downloaded clips to mp4, once).
- Network access **only** for the one-time `--fetch-media` download.
- Python 3.11+ for the script itself (standard library only).

## Run it from a source checkout (verified on Linux/WSL2 + RTX 4060 Ti)

Use a **fresh, throwaway home** so nothing mixes with real data. From the
repository root (paths assume the models under `data/models/`, as in this
repository's own checkout):

```bash
# 1. Point the app at a disposable home and at the local models.
export MOCKINGBIRD_HOME=/tmp/mockingbird-demo-home && mkdir -p "$MOCKINGBIRD_HOME"
M="$PWD/data/models"
export MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH="$M/observation-onnx-cuda/frame-driven-provider-config-2fps.json"
export MOCKINGBIRD_BIOCLIP_MODEL_PATH="$M/bioclip-2"
export MOCKINGBIRD_BIOCLIP_LABELS_PATH="$M/bioclip-2/mockingbird-bird-candidates.txt"
export MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH="$M/bioclip-2/mockingbird-bird-candidates.npz"
# On WSL2/Linux the CUDA 13 libraries installed in the venv must be on the loader path:
SP="$PWD/.venv/lib/python3.12/site-packages/nvidia"
export LD_LIBRARY_PATH="$(find "$SP" -name lib -type d | tr '\n' ':')/usr/lib/wsl/lib"

# 2. Start the app on a spare port.
.venv/bin/python -m mockingbird --no-browser --port 8133 &

# 3. (Optional) see first-run onboarding BEFORE the next step: open
#    http://127.0.0.1:8133 once and create the administrator as username "demo" with
#    password "Mockingbird-Demo-2026!" (or pass --username/--password below).

# 4. One-time download of the CC0 clips, then prepare the demo instance.
.venv/bin/python scripts/prepare_demo_instance.py --api-base http://127.0.0.1:8133 --fetch-media
```

The script prints its progress and finishes with "Demo instance is ready".
Analysis of the three clips takes about two to three minutes on an RTX 4060 Ti
(the first request also loads the models). Re-running it is safe: it reuses the
DEMO camera and skips clips that are already imported.

Then open <http://127.0.0.1:8133> and sign in as the disposable demo account:
username `demo`, password `Mockingbird-Demo-2026!` (a documented, demo-only
credential for a throwaway instance -- never reuse it anywhere real).

To discard everything: stop the app and delete the `MOCKINGBIRD_HOME` folder.

## Run it on native Windows (packaged build)

The packaged Windows folder already contains the models and runtime. In
PowerShell, from the unpacked MockingBird folder (the one containing `python\`),
start a **separate demo instance** with its own data home -- do *not* use the
normal launcher, which uses your real data home -- then run the script with any
Python 3.11+ (standard library only; ffmpeg must be on `PATH`):

```powershell
# Clear any MOCKINGBIRD_* variables inherited from the user environment (they
# override the packaged model paths), then give this process a disposable home.
Get-ChildItem Env: | Where-Object Name -like 'MOCKINGBIRD*' | ForEach-Object { Remove-Item "Env:$($_.Name)" }
$env:MOCKINGBIRD_HOME = "$env:TEMP\MockingBirdDemoHome"
New-Item -ItemType Directory -Force $env:MOCKINGBIRD_HOME | Out-Null
Start-Process .\python\pythonw.exe -ArgumentList "-m","mockingbird","--no-browser","--port","8135" -WindowStyle Hidden

# From a copy of this repository (only scripts\prepare_demo_instance.py and
# docs\demo\demo-media-manifest.json are needed):
python scripts\prepare_demo_instance.py --api-base http://127.0.0.1:8135 --fetch-media
```

Open <http://127.0.0.1:8135>. To discard: stop the `pythonw.exe` process (Task
Manager) and delete the demo home folder.

## What to expect (observed on the verified run)

Two fresh runs on the same machine produced identical counts and suggestions. Other machines or
GPUs may differ slightly.

| Clip | Candidate Visits | Suggestion shown |
|---|---|---|
| Northern mockingbird | 4 (sharing one encounter) | "Northern Mockingbird" on all four |
| Pileated woodpecker | 2 on Linux, 1 on native Windows (the one bird can be split into sibling Visits) | "Red-bellied Woodpecker" (**wrong**) |
| American goldfinches | 2 (one per bird) | none -- "identification uncertain" |

Each imported clip also appears as one "unknown animal" item in the Review
Queue: that is the ordinary manual-import record of the file itself, separate
from the detector's Visits. Expect about **10--11** items waiting in total (11 on the Linux run, 10 on Windows).

## Presentation script (about five minutes)

1. **Observe** -- Show the sign-in screen and sidebar: the instance announces
   itself as a DEMO. Open *Cameras*: the one camera is a recorded-media camera,
   not a live feed. (To show first-run onboarding, do step 3 above on a fresh
   home first.) *Say:* in normal use this is a Camera Node or network camera;
   here the same engine reads recorded clips.
2. **Discover** -- Open *Review Queue*. *Say:* the detector noticed animal
   activity and admitted candidate Visits; each is "Animal detected -- species
   not confirmed". Detection is evidence, not an answer.
3. **Understand** -- Open a mockingbird Visit. Show the evidence frames, the
   "Likely -- AI suggestion" label, "Other possibilities", and "Needs Review /
   Resolve species before export".
4. **Confirm (the point of the demo)**
   - *Correct and confident:* confirm the mockingbird Visits as "Northern
     Mockingbird".
   - *Confidently wrong:* open the woodpecker Visit. The model says "Red-bellied
     Woodpecker"; it is plainly a pileated woodpecker. *Say:* pileated is not in
     the bundled 14-species candidate list, so a closed-set model can only give a
     wrong answer -- this is why suggestions are never truth. Correct it to
     "Pileated Woodpecker".
   - *Honest abstention:* open a goldfinch Visit. *Say:* the candidates were too
     close to call, so MockingBird declined to name a species. "Unknown" is a
     valid human answer too.
5. **Remember** -- Open *Bird Log*: it lists exactly what you confirmed
   (Northern Mockingbird, with its evidence image), and nothing the model merely
   suggested. Note "Capture time unknown": recorded clips have no trustworthy
   capture time and the product refuses to invent one.
6. **Improve** -- *Say:* every correction is dataset-grade reviewed truth that
   exports and analytics rely on; a later model can suggest but never overwrite
   it. (Optional: open *Exports* to show the reviewed-only gate.)

### Honest limits you should say out loud

- The pileated woodpecker and the goldfinches are **outside the bundled
  taxonomy**, so confirming them saves a local label but they do not appear in
  the Bird Log or reviewed analytics yet. Only the mockingbird confirmations do.
- Today and Place Story stay sparse: recorded clips carry no capture time, so
  they do not feed time-windowed analytics.
- One woodpecker became two Visits; multi-subject assembly can over-split.
- No claim is made about identification accuracy from this demo.

## Native-Windows validation

Verified on **2026-10-14** on a native Windows 10 machine (RTX 4060 Ti) with a
**packaged build of commit `a3479c1`** (identity confirmed through
`GET /api/product/instance`), started with a disposable `MOCKINGBIRD_HOME` and a
scrubbed environment as shown above:

- `scripts/prepare_demo_instance.py --fetch-media` ran natively with the
  Windows Python: it downloaded all three clips from Wikimedia Commons, verified
  their SHA-1 hashes, transcoded them with the Windows ffmpeg, created the DEMO
  camera, ran the packaged GPU Observation Engine, and requested identification.
- Result: 10 items in the Review Queue -- the mockingbird clip gave 4 Visits
  suggested as "Northern Mockingbird" (confidence 0.93--1.0); the woodpecker
  clip gave **1** Visit suggested as "Red-bellied Woodpecker" (0.93, wrong); the
  goldfinch clip gave 2 Visits with no species suggestion; plus 3 raw-import
  items. The qualitative story is the same as on Linux; the woodpecker split
  differs (1 Visit here, 2 there), so exact Visit counts are **not**
  guaranteed across machines.
- The packaged UI rendered in headless Edge. The interactive click-through
  (confirming Visits, Bird Log) was verified with Playwright against the
  source-checkout instance, **not** by hand on the native Windows instance.

Not verified: the unpack-and-run ZIP experience on a clean machine for this
commit (the build was deployed with the repository's Windows dev-deployment
tool, not downloaded as a release ZIP), Windows 11, and any GPU other than the
RTX 4060 Ti.

## Reproducibility and verification record

- Script: [`scripts/prepare_demo_instance.py`](../scripts/prepare_demo_instance.py);
  guards: `tests/test_prepare_demo_instance_script.py` (CC0 + hash-pinned
  manifest, no review-truth writes, refuses a non-demo instance).
- Screenshots in `docs/assets/screenshots/` were captured from this exact
  procedure; the Bird Log screenshot was taken after confirming the mockingbird
  and woodpecker Visits through the real UI.
- Media license and provenance: [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)
  ("Demonstration media").
