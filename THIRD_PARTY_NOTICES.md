# Third-Party Notices

MockingBird is written by its own contributors. This file documents the
externally-authored software and machine-learning models distributed
alongside official MockingBird packages -- and, just as importantly, the
ones deliberately **not** distributed alongside them.

MockingBird's own source code is licensed under MIT -- see `LICENSE` at the
repository root. Nothing in this file changes or implies that; it exists to
document everything *external* to MockingBird's own code.

## Machine-learning models bundled with the official Windows package

These two model artifacts are copied directly into an official Windows
release build whenever `--model-bundle-source`/`--bioclip-bundle-source`
supply them (see `scripts/build_local_product.py`). Copying a raw model
file, unlike installing a pip wheel, does not automatically carry a
`LICENSE` file along with it, so each one's terms are recorded here
instead.

### MegaDetector v5a (`md-v5a`) -- wildlife detector

- **What it is:** the ONNX-exported object-detection model MockingBird's
  Observation Engine uses to notice a candidate animal/person/vehicle in a
  video frame.
- **License:** MIT.
- **Copyright:** MegaDetector's own repository states that code and model
  releases on or before April 28, 2023 -- which covers the MegaDetector
  v5.0 release MockingBird uses -- are copyright Microsoft Corporation.
  MegaDetector was originally developed under the Microsoft AI for Earth
  program; the project is now maintained independently by its original
  developers at <https://github.com/agentmorris/MegaDetector>.
- **Full license text:**

  > Permission is hereby granted, free of charge, to any person obtaining a
  > copy of this software and associated documentation files (the
  > "Software"), to deal in the Software without restriction, including
  > without limitation the rights to use, copy, modify, merge, publish,
  > distribute, sublicense, and/or sell copies of the Software, and to
  > permit persons to whom the Software is furnished to do so, subject to
  > the following conditions:
  >
  > The above copyright notice and this permission notice shall be included
  > in all copies or substantial portions of the Software.
  >
  > THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
  > OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
  > MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
  > IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
  > CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
  > TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
  > SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

- **Provenance:** `scripts/build_local_product.py`'s
  `ACCEPTED_SOURCE_MODEL_SHA256`/`ACCEPTED_ONNX_MODEL_SHA256` constants are
  independently re-verified against the actual file before it is ever
  packaged, so only the exact accepted artifact this notice describes can
  ship.

### BioCLIP 2 -- optional species-suggestion model

- **What it is:** the vision-language model MockingBird's optional
  species-suggestion feature uses to rank likely species for a reviewed
  Visit. Never required for core startup or for a Visit to be created; a
  missing bundle degrades honestly (species suggestions are simply
  unavailable until identified by a person).
- **License:** MIT, as declared on the model's official model card:
  <https://huggingface.co/imageomics/bioclip-2> (`imageomics/bioclip-2`,
  version 1.0.0). That page does not publish a separate copyright-holder
  line beyond the license declaration itself.
- **Provenance:** `scripts/build_local_product.py`'s
  `ACCEPTED_BIOCLIP_MODEL_WEIGHTS_SHA256` and related constants are
  independently re-verified against the actual file before it is ever
  packaged.

## Core runtime dependencies (direct, not transitive)

MockingBird's Python and JavaScript dependencies are ordinary pip/npm
packages. Installing MockingBird's own wheel with `pip install --target`
-- the mechanism the official Windows build uses -- already places every
dependency's own `LICENSE`/`NOTICE` file inside that dependency's own
`<package>-<version>.dist-info/` folder, colocated with its code in the
shipped bundle (`python/site-packages/*.dist-info/` in an installed copy
of MockingBird). Nothing further is needed to preserve those individually.
This section names only the **direct** (not transitive) core dependencies,
confirmed against each package's own installed metadata, for a quick
honest summary -- it is deliberately not a line-by-line transitive
dependency dump (dozens of further packages are pulled in by the two
closures below; each ships its own license the identical way).

| Package | License |
| --- | --- |
| anyio | MIT |
| fastapi | MIT |
| Pillow | MIT-CMU |
| pydantic | MIT |
| python-multipart | Apache-2.0 |
| SQLAlchemy | MIT |
| opencv-python-headless | Apache-2.0 |
| uvicorn | BSD-3-Clause |
| astral | Apache-2.0 |
| react / react-dom | MIT |

Two larger optional runtime closures ship as part of an official Windows
build whenever GPU wildlife detection and/or BioCLIP species suggestions
are included (the default for an official release build):

- **The ONNX Runtime / CUDA execution-provider stack**
  (`onnxruntime-gpu` plus its `nvidia-cu*` CUDA/cuDNN redistributable
  dependencies). `onnxruntime-gpu` itself is MIT-licensed. The
  `nvidia-cublas`/`nvidia-cudnn-cu13`/`nvidia-cufft`/`nvidia-curand`/
  `nvidia-cuda-runtime`/`nvidia-cuda-nvrtc` packages redistribute NVIDIA's
  own proprietary CUDA/cuDNN shared libraries under NVIDIA's own
  redistribution terms -- their PyPI package metadata nominally carries a
  permissive classifier for the thin Python packaging layer only; the
  actual native `.dll`/`.so` libraries inside are governed by NVIDIA's own
  CUDA/cuDNN End User License Agreement. This is the same well-established
  distribution pattern official PyTorch/TensorFlow GPU wheels already use,
  and is not treated as a redistribution blocker here -- but this
  milestone did not independently re-confirm the exact current NVIDIA EULA
  notice text against what these specific packages ship; see this
  milestone's own report for the precise disposition.
- **The BioCLIP/OpenCLIP runtime closure** (`torch`, `torchvision`,
  `open_clip_torch`, and their own further dependencies). PyTorch and
  torchvision are BSD-3-Clause; `open_clip_torch` is MIT.

## Deliberately NOT bundled

### FFmpeg

MockingBird never bundles, downloads, or redistributes an `ffmpeg`
executable in any official package. A network camera (RTSP/ONVIF), a
USB/built-in camera, and recorded-video import each optionally use a
system `ffmpeg` only if one is already installed on this computer and
available on its PATH (`shutil.which("ffmpeg")`) -- MockingBird only ever
invokes it as a separate process the operating system already provides; it
is never linked, copied, or shipped by MockingBird itself. The
MockingBird Camera Node path needs no `ffmpeg` at all. If you install
`ffmpeg` yourself, it remains under whichever license its own distributor
used (commonly LGPL or GPL, depending on which optional codecs that
specific build enables) -- that is between you and your ffmpeg
distribution, not MockingBird. `scripts/build_local_product.py`'s
`verify_no_bundled_ffmpeg_binary` fails the release build outright if this
were ever to change silently.

### BirdNET / birdnetlib (optional bird-sound identification)

MockingBird's official packaging never bundles bird-sound identification
(BirdNET) support:

- `birdnetlib` (the wrapper code MockingBird's optional acoustic adapter
  uses) is Apache-2.0 -- permissively licensed and fine to redistribute on
  its own.
- However, `birdnetlib`'s own PyPI wheel bundles the actual **BirdNET-
  Analyzer `GLOBAL_6K_V2.4` model weights** as real package data inside
  itself, and those weights are licensed **CC BY-NC-SA 4.0 (Creative
  Commons Attribution-NonCommercial-ShareAlike), NonCommercial only**, by
  Cornell's K. Lisa Yang Center for Conservation Bioacoustics.
- Because the code and the model weights are not separable inside that one
  wheel, MockingBird's own installer/packaged build never installs
  `birdnetlib` at all. `classifier-birdnet` is an explicit, separate,
  optional extra (`pip install "mockingbird[classifier-birdnet]"`) that a
  user installs themselves, obtaining the model directly from PyPI under
  upstream's own terms -- never through MockingBird's own redistribution.
  `scripts/build_local_product.py`'s
  `verify_no_nc_licensed_acoustic_model_redistribution` fails the release
  build outright if this were ever to change silently.
- See `docs/acoustic-productization-licensing-field-acceptance-v1-contract.md`
  ("Phase 2 -- Authoritative licensing decision") for the complete
  per-artifact license table and the full reasoning behind this
  architecture (Decision B, "Optional external model").
- **Commercial-adjacent use remains a genuinely open legal question**,
  unresolved by engineering means alone: whether an individual user's own
  private, on-device use of MockingBird+BirdNET could ever be implicated
  merely because the surrounding open-source project also accepts
  donations or sells optional paid support. This is recorded as requiring
  legal review before any commercial-adjacent distribution decision (paid
  support, a crowdfunded/paid appliance, a hosted service) touches the
  acoustic feature specifically -- see `docs/release-execution-state.md`
  §2 for the standing caveat.

## Where to look for anything not covered here

- MockingBird's own source-code license: MIT -- see `LICENSE` at the
  repository root.
- Every individual Python dependency's own full license text: inside its
  own `<package>-<version>.dist-info/` folder, colocated with its code, in
  any installed copy of MockingBird.
- The complete BirdNET/model-licensing evidence and reasoning:
  `docs/acoustic-productization-licensing-field-acceptance-v1-contract.md`
  and its companion report.
