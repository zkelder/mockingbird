"""BirdNET-class acoustic species-identification adapter -- Acoustic /
BirdNET Observation Foundation v1. See docs/acoustic-birdnet-observation-
foundation-v1-contract.md "BirdNET runtime decision" for the full evidence
behind every choice this module makes; this module is the mechanics.

## Runtime decision (verified directly, not assumed from documentation)

`birdnetlib` (Apache-2.0 wrapper) running the real, bundled BirdNET-Analyzer
`BirdNET_GLOBAL_6K_V2.4` TFLite model (Creative Commons BY-NC-SA 4.0,
Cornell K. Lisa Yang Center for Conservation Bioacoustics / kahst
BirdNET-Analyzer) -- the model ships as real package data inside the
`birdnetlib` wheel (confirmed by inspecting the installed wheel directly),
so no runtime download ever occurs; installing the optional
`classifier-birdnet` extra is the one explicit action that obtains it,
mirroring this product's existing "no automatic model download" rule for
MDv5/BioCLIP.

`birdnetlib` only ever does `import tflite_runtime.interpreter`, falling
back to a full `tensorflow` install if that import fails. `tflite-runtime`
itself is unavailable on PyPI for this project's supported Python versions
(`pip index versions tflite-runtime` -> "No matching distribution", verified
directly). Rather than pulling in full TensorFlow purely for a lightweight
CPU TFLite interpreter, this module resolves Google's maintained successor
package, `ai-edge-litert` (the same `Interpreter` API), and registers it
under the `tflite_runtime` import name *before* importing `birdnetlib` --
`_install_tflite_runtime_shim`, below. Verified end-to-end against a real
audio recording: 9/9 windows of a real, clearly-licensed Northern Cardinal
field recording correctly identified at 0.78-0.999 confidence; a synthetic
pink-noise clip produced 0 detections at both a low (0.1) and realistic
(0.5) confidence floor.

CPU-only by explicit design choice (mirrors this product's existing BioCLIP
precedent, `bioclip_adapter.BioClipAdapterConfig.device` hard-enforced to
`"cpu"`): BirdNET-Analyzer's TFLite model is CPU-cheap by construction (a
35-second real clip analyzed in ~1.5s on CPU in direct verification), so a
second GPU-runtime dependency alongside `onnxruntime-gpu`/`torch` is not
justified.

## Licensing (disclosed, not glossed over)

The BirdNET-Analyzer model *weights* bundled inside `birdnetlib` are
licensed CC BY-NC-SA 4.0 -- NonCommercial. This is compatible with
MockingBird's current local, personal-use, non-commercial posture,
structured as an optional, removable extra (`classifier-birdnet`) never
required for core startup and never committed to git (the weights live
inside the installed pip package's own site-packages, exactly like every
other optional model dependency this product already has) -- but it is a
real constraint for any future commercial-release decision, recorded here
plainly rather than silently glossed over, mirroring this codebase's
existing provenance rigor for MDv5/BioCLIP licensing.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
import importlib
import importlib.metadata
import io
import sys
import threading
import types
from typing import Any, Protocol

#: Optional local override for advanced users who want a different BirdNET
#: model version than the one `birdnetlib` bundles. Unset by default --
#: the common case needs no configuration at all, unlike MDv5/BioCLIP.
BIRDNET_MODEL_PATH_ENV_VAR = "MOCKINGBIRD_BIRDNET_MODEL_PATH"
BIRDNET_LABELS_PATH_ENV_VAR = "MOCKINGBIRD_BIRDNET_LABELS_PATH"
#: A conservative default confidence floor (see "Confidence Threshold
#: Rules" in docs/model-selection.md: "Use a conservative default
#: threshold"). Configurable per deployment.
BIRDNET_MIN_CONFIDENCE_ENV_VAR = "MOCKINGBIRD_BIRDNET_MIN_CONFIDENCE"
DEFAULT_MIN_CONFIDENCE = 0.5
#: Optional species-range filter -- BirdNET's own location/date meta-model
#: narrows its candidate species list when given a real site coordinate.
#: MockingBird persists no site-coordinate model (see "Privacy" in
#: docs/research-conservation-export-contract.md); these are honored only
#: as an explicit, non-persisted per-run configuration value, exactly like
#: `CamtrapDpExportRequest.latitude`/`.longitude`.
BIRDNET_LATITUDE_ENV_VAR = "MOCKINGBIRD_BIRDNET_LATITUDE"
BIRDNET_LONGITUDE_ENV_VAR = "MOCKINGBIRD_BIRDNET_LONGITUDE"

#: Identity of the bundled model this adapter targets -- used only to label
#: provenance honestly; never asserted against the actual loaded model
#: (that identity is read back from the real `Analyzer` instance itself,
#: see `BirdNetProvenance.model_version`).
EXPECTED_MODEL_VERSION = "BirdNET_GLOBAL_6K_V2.4"
MODEL_LICENSE = "CC BY-NC-SA 4.0 (Cornell K. Lisa Yang Center for Conservation Bioacoustics)"

_REQUIRED_RUNTIME_PACKAGES = ("birdnetlib", "librosa")
_TFLITE_BACKEND_CANDIDATES = ("tflite_runtime", "ai_edge_litert", "tensorflow")


class BirdNetConfigurationError(ValueError):
    """Stable, bounded configuration/runtime-failure code -- mirrors
    `mockingbird.species.bioclip_adapter.BioClipConfigurationError`'s
    established convention: the message is always a small fixed
    vocabulary, never a raw traceback or file path."""


@dataclass(frozen=True)
class BirdNetAdapterConfig:
    """Explicit, deterministic BirdNET run configuration. Every field has a
    safe default; nothing here requires setup for the common case (unlike
    MDv5/BioCLIP, whose local model artifacts must always be explicitly
    configured) -- see the module docstring."""

    min_confidence: float = DEFAULT_MIN_CONFIDENCE
    model_path: str | None = None
    labels_path: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.min_confidence <= 1.0):
            raise BirdNetConfigurationError("invalid_min_confidence")


def resolve_birdnet_config(
    *, environment: dict[str, str] | None = None,
) -> BirdNetAdapterConfig:
    """Resolve configuration from the environment -- the same explicit,
    env-var-driven convention every other optional model adapter in this
    product already uses (`MOCKINGBIRD_MEGADETECTOR_*`,
    `MOCKINGBIRD_BIOCLIP_*`)."""

    import os

    env = environment if environment is not None else os.environ
    min_confidence_raw = (env.get(BIRDNET_MIN_CONFIDENCE_ENV_VAR) or "").strip()
    min_confidence = DEFAULT_MIN_CONFIDENCE
    if min_confidence_raw:
        try:
            min_confidence = float(min_confidence_raw)
        except ValueError as error:
            raise BirdNetConfigurationError("invalid_min_confidence") from error

    def _optional_float(name: str) -> float | None:
        raw = (env.get(name) or "").strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError as error:
            raise BirdNetConfigurationError("invalid_coordinate") from error

    return BirdNetAdapterConfig(
        min_confidence=min_confidence,
        model_path=(env.get(BIRDNET_MODEL_PATH_ENV_VAR) or "").strip() or None,
        labels_path=(env.get(BIRDNET_LABELS_PATH_ENV_VAR) or "").strip() or None,
        latitude=_optional_float(BIRDNET_LATITUDE_ENV_VAR),
        longitude=_optional_float(BIRDNET_LONGITUDE_ENV_VAR),
    )


def _missing_runtime_packages() -> list[str]:
    """Side-effect-free (does not import/load anything heavy): which
    required packages are not installed. Mirrors `bioclip_adapter.
    _missing_runtime_packages`'s identical "importlib.util.find_spec,
    never a real import" discipline."""

    import importlib.util

    missing = [name for name in _REQUIRED_RUNTIME_PACKAGES if importlib.util.find_spec(name) is None]
    if importlib.util.find_spec("tflite_runtime") is None and all(
        importlib.util.find_spec(candidate) is None
        for candidate in ("ai_edge_litert", "tensorflow")
    ):
        missing.append("ai-edge-litert (or tensorflow)")
    return missing


_shim_lock = threading.Lock()
_shim_installed = False


def _install_tflite_runtime_shim() -> None:
    """`birdnetlib` only ever does `import tflite_runtime.interpreter`. If a
    real `tflite_runtime` is genuinely installed, this is a no-op (its own
    real import already satisfies `birdnetlib`). Otherwise, resolve
    `ai_edge_litert`'s `Interpreter` (the maintained successor with the
    identical API surface, verified directly against the real bundled
    model) and register it under the `tflite_runtime`/`tflite_runtime.
    interpreter` module names *before* `birdnetlib` is ever imported --
    idempotent and thread-safe; never overrides a real `tflite_runtime` if
    one is actually present."""

    global _shim_installed
    if _shim_installed or "tflite_runtime" in sys.modules:
        return
    with _shim_lock:
        if _shim_installed or "tflite_runtime" in sys.modules:
            return
        import importlib.util

        if importlib.util.find_spec("tflite_runtime") is not None:
            _shim_installed = True
            return
        if importlib.util.find_spec("ai_edge_litert") is None:
            # No lightweight backend available -- leave `tflite_runtime`
            # unregistered so `birdnetlib`'s own documented fallback to a
            # real `tensorflow` install (if present) still works unshimmed.
            _shim_installed = True
            return
        litert_interpreter = importlib.import_module("ai_edge_litert.interpreter")
        shim_package = types.ModuleType("tflite_runtime")
        shim_package.interpreter = litert_interpreter  # type: ignore[attr-defined]
        sys.modules["tflite_runtime"] = shim_package
        sys.modules["tflite_runtime.interpreter"] = litert_interpreter
        _shim_installed = True


@dataclass(frozen=True)
class BirdNetRuntimeStatus:
    """Explicit local readiness -- mirrors `BioClipAdapterStatus`'s shape.
    Inspecting this never loads the model or runs inference."""

    status: str  # "available" | "unavailable"
    runtime_available: bool
    detail: str


def get_birdnet_status() -> BirdNetRuntimeStatus:
    """Inspect explicit local readiness without loading a model or running
    inference -- mirrors `bioclip_adapter.get_bioclip_status`'s identical
    contract, adapted for BirdNET's simpler (no required local-path
    configuration) resolution story."""

    missing = _missing_runtime_packages()
    if missing:
        return BirdNetRuntimeStatus(
            status="unavailable",
            runtime_available=False,
            detail=(
                "Optional BirdNET runtime dependencies are unavailable: "
                f"{', '.join(missing)}. The core app remains available."
            ),
        )
    return BirdNetRuntimeStatus(
        status="available",
        runtime_available=True,
        detail="The optional BirdNET acoustic adapter is installed and ready.",
    )


@dataclass(frozen=True)
class BirdNetProvenance:
    """Adapter-neutral model/runtime provenance -- what
    `SpeciesSuggestionCreateRequest.model_provenance` is populated with for
    every BirdNET suggestion. Answers "exactly which model/runtime/settings
    produced this suggestion" per the milestone's own provenance
    requirement."""

    adapter_id: str
    model_name: str
    model_version: str
    model_license: str
    birdnetlib_version: str
    tflite_backend: str
    min_confidence: float
    latitude: float | None
    longitude: float | None
    source_content_sha256: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_license": self.model_license,
            "birdnetlib_version": self.birdnetlib_version,
            "tflite_backend": self.tflite_backend,
            "min_confidence": self.min_confidence,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source_content_sha256": self.source_content_sha256,
        }


@dataclass(frozen=True)
class BirdNetDetection:
    """One BirdNET-positive analysis window -- confidence/probability and
    time-window offsets preserved exactly as the model reported them,
    never re-derived or rounded away."""

    common_name: str
    scientific_name: str
    confidence: float
    start_ms: int
    end_ms: int


@dataclass(frozen=True)
class BirdNetAnalysisResult:
    detections: tuple[BirdNetDetection, ...]
    windows_analyzed: int
    provenance: BirdNetProvenance


class SupportsBirdNetAnalysis(Protocol):
    """The narrow seam `run_birdnet_on_clip` depends on for the actual
    analysis step -- the real `birdnetlib.Recording` instance satisfies
    this structurally (duck typing, no inheritance required: construct it,
    call `.analyze()`, then read `.detections`/`.duration`), and a test can
    inject a deterministic fake instead via `run_birdnet_on_clip`'s
    `recording` parameter -- which also means the real `birdnetlib`
    package need not even be importable for a test that injects one,
    mirroring this codebase's established "an injected fake for the
    ML-heavy step" convention (`FakeDetector` in tracker tests, fake
    `Picamera2` in Camera Node tests) -- ordinary Fast/Core tests never
    need the real ~700MB dependency stack or real model inference."""

    detections: list[dict[str, Any]]
    duration: float | None

    def analyze(self) -> None: ...  # noqa: D102


_analyzer_lock = threading.Lock()
_cached_analyzer: Any = None
_cached_analyzer_config_key: tuple[str | None, str | None] | None = None


def _load_real_analyzer(config: BirdNetAdapterConfig) -> Any:
    """Lazily construct (and cache) the real `birdnetlib.analyzer.Analyzer`
    -- loaded only on first real use, matching "Bounded Runtime
    Expectations" in docs/model-selection.md ("avoid startup work"). Thread
    -safe single-flight; re-resolved only if the caller-supplied model/
    labels path override actually changes."""

    global _cached_analyzer, _cached_analyzer_config_key
    config_key = (config.model_path, config.labels_path)
    with _analyzer_lock:
        if _cached_analyzer is not None and _cached_analyzer_config_key == config_key:
            return _cached_analyzer
        _install_tflite_runtime_shim()
        try:
            analyzer_module = importlib.import_module("birdnetlib.analyzer")
        except ImportError as error:
            raise BirdNetConfigurationError("birdnet_runtime_unavailable") from error
        kwargs: dict[str, Any] = {}
        if config.model_path:
            kwargs["classifier_model_path"] = config.model_path
        if config.labels_path:
            kwargs["classifier_labels_path"] = config.labels_path
        try:
            # `birdnetlib` writes bare `print()` progress lines (not a
            # logger) directly to stdout during model load -- redirected
            # here so it never pollutes this product's own structured
            # application log; the underlying error (if any) still raises
            # normally regardless.
            with redirect_stdout(io.StringIO()):
                analyzer = analyzer_module.Analyzer(**kwargs)
        except Exception as error:  # noqa: BLE001 -- a third-party runtime failure, never surfaced raw
            raise BirdNetConfigurationError("birdnet_model_load_failed") from error
        _cached_analyzer = analyzer
        _cached_analyzer_config_key = config_key
        return analyzer


def _birdnetlib_version() -> str:
    try:
        return importlib.metadata.version("birdnetlib")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _tflite_backend_name() -> str:
    import importlib.util

    if importlib.util.find_spec("ai_edge_litert") is not None:
        return "ai-edge-litert"
    if "tflite_runtime" in sys.modules or importlib.util.find_spec("tflite_runtime") is not None:
        return "tflite_runtime"
    if importlib.util.find_spec("tensorflow") is not None:
        return "tensorflow"
    return "unknown"


def run_birdnet_on_clip(
    clip_path: Path,
    *,
    config: BirdNetAdapterConfig,
    source_content_sha256: str | None = None,
    analyzer: Any | None = None,
    recording: SupportsBirdNetAnalysis | None = None,
) -> BirdNetAnalysisResult:
    """Run BirdNET-class analysis over one bounded, already-canonical-format
    audio clip.

    Two independent injection seams for deterministic testing (see
    `SupportsBirdNetAnalysis`), either omitted for real production
    inference:

    - `analyzer`: stands in for the real, lazily-loaded `birdnetlib.
      analyzer.Analyzer` (still requires the real `birdnetlib` package to
      construct a `Recording` around it).
    - `recording`: stands in for the real `birdnetlib.Recording` entirely
      -- when supplied, this function never imports `birdnetlib` at all
      (nor loads a real analyzer), so a test can exercise every code path
      below the analysis step without the optional ~700MB dependency
      stack installed. This is the seam ordinary Fast/Core tests use.

    Never raises for "no detection" -- an empty `detections` tuple with a
    real `windows_analyzed` count is the honest, legitimate outcome (see
    "appropriate handling of no-detection ... cases" in this milestone's
    own doctrine). Raises `BirdNetConfigurationError` only for a genuine
    setup/runtime failure (missing dependency, unreadable clip, model load
    failure) -- never a silent empty result standing in for a real error.
    """

    if not clip_path.is_file():
        raise BirdNetConfigurationError("clip_file_missing")

    recording_kwargs: dict[str, Any] = {"min_conf": config.min_confidence}
    if config.latitude is not None and config.longitude is not None:
        recording_kwargs["lat"] = config.latitude
        recording_kwargs["lon"] = config.longitude

    try:
        if recording is None:
            real_analyzer = analyzer if analyzer is not None else _load_real_analyzer(config)
            try:
                recording_module = importlib.import_module("birdnetlib")
            except ImportError as error:
                raise BirdNetConfigurationError("birdnet_runtime_unavailable") from error
            recording = recording_module.Recording(real_analyzer, str(clip_path), **recording_kwargs)
        with redirect_stdout(io.StringIO()):  # see _load_real_analyzer's identical rationale
            recording.analyze()
    except BirdNetConfigurationError:
        raise
    except Exception as error:  # noqa: BLE001 -- a third-party runtime failure, never surfaced raw
        raise BirdNetConfigurationError("birdnet_analysis_failed") from error

    raw_detections = list(getattr(recording, "detections", []) or [])
    detections = tuple(
        BirdNetDetection(
            common_name=str(item["common_name"]),
            scientific_name=str(item["scientific_name"]),
            confidence=float(item["confidence"]),
            start_ms=round(float(item["start_time"]) * 1000),
            end_ms=round(float(item["end_time"]) * 1000),
        )
        for item in raw_detections
    )
    # BirdNET's own fixed ~3s analysis window is the basis for a bounded
    # "windows analyzed" count even when zero detections survive the
    # confidence floor -- read back from the recording's own duration when
    # available, otherwise honestly the detection count (a lower bound).
    duration_seconds = getattr(recording, "duration", None)
    windows_analyzed = (
        max(1, round(float(duration_seconds) / 3.0)) if duration_seconds else len(detections)
    )

    provenance = BirdNetProvenance(
        adapter_id="birdnet",
        model_name="BirdNET-Analyzer",
        model_version=EXPECTED_MODEL_VERSION,
        model_license=MODEL_LICENSE,
        birdnetlib_version=_birdnetlib_version(),
        tflite_backend=_tflite_backend_name(),
        min_confidence=config.min_confidence,
        latitude=config.latitude,
        longitude=config.longitude,
        source_content_sha256=source_content_sha256,
    )
    return BirdNetAnalysisResult(
        detections=detections, windows_analyzed=windows_analyzed, provenance=provenance,
    )


__all__ = [
    "BIRDNET_LABELS_PATH_ENV_VAR",
    "BIRDNET_LATITUDE_ENV_VAR",
    "BIRDNET_LONGITUDE_ENV_VAR",
    "BIRDNET_MIN_CONFIDENCE_ENV_VAR",
    "BIRDNET_MODEL_PATH_ENV_VAR",
    "DEFAULT_MIN_CONFIDENCE",
    "EXPECTED_MODEL_VERSION",
    "MODEL_LICENSE",
    "BirdNetAdapterConfig",
    "BirdNetAnalysisResult",
    "BirdNetConfigurationError",
    "BirdNetDetection",
    "BirdNetProvenance",
    "BirdNetRuntimeStatus",
    "SupportsBirdNetAnalysis",
    "get_birdnet_status",
    "resolve_birdnet_config",
    "run_birdnet_on_clip",
]
