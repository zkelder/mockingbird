"""Optional, offline BioCLIP 2 species-suggestion adapter.

The adapter accepts one already-decoded in-memory image or crop and returns
ranked evidence. It does not resolve product records, persist suggestions, or
create reviewed truth. Heavy dependencies are imported only during an explicit
run, and every runtime artifact must already exist at an explicit local path.
"""

from __future__ import annotations

import ast
import atexit
import base64
import binascii
from dataclasses import dataclass
import hashlib
import hmac
from importlib import import_module, metadata, util
import json
import math
import multiprocessing
from multiprocessing.connection import Connection
from multiprocessing import shared_memory
import os
from pathlib import Path
import re
import struct
import threading
import time
from types import ModuleType
from typing import Any, Callable, Literal
import zipfile

BIOCLIP_ADAPTER_ID = "bioclip_2"
BIOCLIP_ADAPTER_NAME = "BioCLIP 2"
BIOCLIP_ADAPTER_CONTRACT_VERSION = 1
BIOCLIP_MODEL_NAME = "BioCLIP 2 local"
BIOCLIP_ARCHITECTURE_ID = "bioclip-2-vit-l-14"
BIOCLIP_PREPROCESSING_ID = "openclip-bioclip-2-vit-l-14-v1"
BIOCLIP_SCORE_KIND = "candidate_relative_softmax"
BIOCLIP_CANDIDATE_FINGERPRINT_ALGORITHM = "sha256-newline-joined-utf8-v1"
BIOCLIP_FULL_SCORE_ENCODING = "float64-le-base64-v1"
BIOCLIP_MAX_TOP_K = 20
BIOCLIP_MAX_LABEL_COUNT = 10_000
BIOCLIP_MAX_LABEL_LENGTH = 512
BIOCLIP_MAX_LABELS_FILE_BYTES = 4 * 1024 * 1024
BIOCLIP_MAX_MODEL_CONFIG_BYTES = 1024 * 1024
BIOCLIP_MAX_MODEL_WEIGHTS_BYTES = 2 * 1024 * 1024 * 1024
BIOCLIP_MAX_EMBEDDING_CACHE_BYTES = 64 * 1024 * 1024
BIOCLIP_MAX_EMBEDDING_CACHE_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
BIOCLIP_EMBEDDING_DIMENSION = 768
BIOCLIP_MAX_CACHE_METADATA_MEMBER_BYTES = 4 * 1024
BIOCLIP_MAX_IMAGE_PIXELS = 16_777_216
BIOCLIP_MAX_RESULT_BYTES = 256 * 1024
BIOCLIP_RUN_TIMEOUT_SECONDS = 120.0
BIOCLIP_WORKER_STOP_GRACE_SECONDS = 5.0
BIOCLIP_OPEN_CLIP_VERSION_SERIES = "3.3"
BIOCLIP_PROMPT_RECIPE_ID = "pybioclip-openai-imagenet-80-template-v1"
# SHA-256 of canonical recipe lines (recipe id, per-prompt L2 normalization,
# ordered mean, final L2 normalization), followed by the ordered 80 templates
# rendered with ``__MOCKINGBIRD_LABEL__`` and all joined by ``\n``.
BIOCLIP_PROMPT_RECIPE_SHA256 = (
    "4db1b03a1d5f97eb00fb83cc22b641d40aff261da513238c135d0e0745b0dfaf"
)

_RUNTIME_PACKAGES = ("PIL", "numpy", "open_clip", "torch")
_MODEL_CONFIG_NAME = "open_clip_config.json"
_SAFE_MODEL_WEIGHT_NAMES = (
    "open_clip_model.safetensors",
    "open_clip_pytorch_model.safetensors",
    "model.safetensors",
)
_CHECKPOINT_SUFFIXES = {".bin", ".ckpt", ".pt", ".pth", ".safetensors"}
_REQUIRED_CACHE_MEMBERS = {
    "embeddings.npy",
    "label_sha256.npy",
    "model_config_sha256.npy",
    "model_weights_sha256.npy",
    "prompt_recipe_sha256.npy",
}
_REMOTE_CAPABLE_MODEL_CONFIG_KEYS = {
    "hf_hub_id",
    "hf_model_name",
    "hf_model_pretrained",
    "hf_tokenizer_name",
    "pretrained",
    "pretrained_cfg",
    "pretrained_hf",
    "timm_model_name",
}
_EXPECTED_BIOCLIP_MODEL_CONFIG = {
    "embed_dim": 768,
    "vision_cfg": {
        "image_size": 224,
        "layers": 24,
        "width": 1024,
        "patch_size": 14,
    },
    "text_cfg": {
        "context_length": 77,
        "vocab_size": 49_408,
        "width": 768,
        "heads": 12,
        "layers": 12,
    },
}
_EXPECTED_BIOCLIP_PREPROCESS_CONFIG = {
    "mean": [0.48145466, 0.4578275, 0.40821073],
    "std": [0.26862954, 0.26130258, 0.27577711],
    "interpolation": "bicubic",
    "resize_mode": "shortest",
}
BIOCLIP_PREPROCESSING_CONFIG_JSON = json.dumps(
    _EXPECTED_BIOCLIP_PREPROCESS_CONFIG,
    ensure_ascii=False,
    separators=(",", ":"),
    sort_keys=True,
)
BIOCLIP_PREPROCESSING_SHA256 = hashlib.sha256(
    BIOCLIP_PREPROCESSING_CONFIG_JSON.encode("utf-8")
).hexdigest()
_SCIENTIFIC_LABEL = re.compile(
    r"^(?P<common>.+?)\s+\("
    r"(?P<scientific>[A-Z][A-Za-z.-]+(?:\s+[a-z][A-Za-z.-]+)+)"
    r"\)$"
)

BioClipAdapterStatusValue = Literal["available", "not_configured", "unavailable"]


class BioClipError(RuntimeError):
    """Base error for bounded BioCLIP adapter failures."""

    error_code = "bioclip_failed"
    error_stage = "inference"


class BioClipConfigurationError(BioClipError):
    """Raised when explicit local runtime configuration is incomplete or invalid."""

    error_code = "bioclip_configuration"
    error_stage = "configuration"


class BioClipRuntimeUnavailableError(BioClipError):
    """Raised when the optional local runtime cannot be imported or loaded."""

    error_code = "bioclip_runtime_unavailable"
    error_stage = "model_load"


class BioClipBusyError(BioClipRuntimeUnavailableError):
    """Raised when another local BioCLIP request already owns the runtime."""

    error_code = "bioclip_busy"
    error_stage = "process_startup"


class BioClipTimeoutError(BioClipRuntimeUnavailableError):
    """Raised when the local model worker exceeds its hard time limit."""

    error_code = "bioclip_timed_out"
    error_stage = "inference"


class BioClipWorkerFailureError(BioClipRuntimeUnavailableError):
    """Raised when the isolated worker fails outside a narrower typed outcome."""

    error_code = "bioclip_worker_failed"
    error_stage = "inference"


class BioClipUnsupportedImageError(BioClipError):
    """Raised when the caller did not supply a supported in-memory image."""

    error_code = "bioclip_unsupported_image"
    error_stage = "input_preparation"


class BioClipNoResultError(BioClipError):
    """Raised when a valid run completes without any candidate scores."""

    error_code = "bioclip_no_result"
    error_stage = "output_parsing"


class BioClipOutputError(BioClipError):
    """Raised when the optional runtime returns unusable inference output."""

    error_code = "bioclip_invalid_output"
    error_stage = "output_parsing"


_WORKER_ERROR_DETAILS: dict[str, tuple[str, str]] = {
    "configuration": (
        "BioCLIP worker configuration validation failed.",
        "configuration",
    ),
    "runtime_unavailable": (
        "BioCLIP optional runtime was unavailable in the isolated worker.",
        "model_load",
    ),
    "unsupported_image": (
        "BioCLIP worker could not prepare the bounded in-memory image.",
        "input_preparation",
    ),
    "no_result": (
        "BioCLIP completed without candidate scores.",
        "output_parsing",
    ),
    "output": (
        "BioCLIP worker returned invalid bounded model output.",
        "output_parsing",
    ),
    "unexpected": (
        "BioCLIP local worker failed safely.",
        "inference",
    ),
}


@dataclass(frozen=True)
class BioClipAdapterConfig:
    """Explicit local-only inputs for one optional BioCLIP runtime."""

    model_dir: Path | None
    labels_path: Path | None
    embedding_cache_path: Path | None
    device: str = "cpu"


@dataclass(frozen=True)
class BioClipAdapterStatus:
    """Side-effect-free readiness summary suitable for model registry mapping."""

    status: BioClipAdapterStatusValue
    configured: bool
    runtime_available: bool
    detail: str
    model_dir: str | None
    labels_path: str | None
    embedding_cache_path: str | None
    device: str
    labels_sha256: str | None = None


@dataclass(frozen=True)
class BioClipRankedSuggestion:
    """One ranked candidate-relative classifier result."""

    rank: int
    label: str
    common_name: str | None
    scientific_name: str | None
    score: float
    score_kind: str = BIOCLIP_SCORE_KIND
    calibrated: bool = False


@dataclass(frozen=True)
class BioClipProvenance:
    """Review-safe runtime provenance without exposing local filesystem paths."""

    adapter_id: str
    adapter_name: str
    model_name: str
    device: str
    open_clip_version: str
    torch_version: str
    label_count: int
    labels_sha256: str
    embedding_cache_sha256: str
    model_config_sha256: str
    model_weights_sha256: str
    model_weights_name: str
    prompt_recipe_id: str
    prompt_recipe_sha256: str
    score_kind: str
    calibrated: bool
    adapter_contract_version: int = BIOCLIP_ADAPTER_CONTRACT_VERSION
    architecture_id: str = BIOCLIP_ARCHITECTURE_ID
    preprocessing_id: str = BIOCLIP_PREPROCESSING_ID
    preprocessing_sha256: str = BIOCLIP_PREPROCESSING_SHA256
    pillow_version: str | None = None
    numpy_version: str | None = None
    model_weights_verified: bool = True
    model_reused: bool = False
    model_load_ms: int = 0
    inference_ms: int = 0


@dataclass(frozen=True)
class BioClipPrediction:
    """Ranked model evidence returned to a higher product-level service."""

    suggestions: tuple[BioClipRankedSuggestion, ...]
    provenance: BioClipProvenance
    candidate_labels: tuple[str, ...] = ()
    candidate_scores: tuple[float, ...] = ()


@dataclass(frozen=True)
class BioClipPreparedRun:
    """Safe, complete attempt context available before image decoding."""

    adapter_id: str
    adapter_name: str
    adapter_contract_version: int
    model_name: str
    architecture_id: str
    device: str
    candidate_labels: tuple[str, ...]
    candidate_count: int
    candidate_set_sha256: str
    candidate_fingerprint_algorithm: str
    embedding_cache_sha256: str
    model_config_sha256: str
    model_weights_sha256: str
    model_weights_name: str
    model_weights_verified: bool
    prompt_recipe_id: str
    prompt_recipe_sha256: str
    preprocessing_id: str
    preprocessing_sha256: str
    preprocessing_config_json: str
    timeout_seconds: float
    open_clip_version: str | None
    torch_version: str | None
    pillow_version: str | None
    numpy_version: str | None


@dataclass(frozen=True)
class _ValidatedConfig:
    model_dir: Path
    model_config_path: Path
    model_weights_path: Path
    labels_path: Path
    embedding_cache_path: Path
    labels: tuple[str, ...]
    labels_sha256: str
    embedding_cache_sha256: str | None
    model_config_sha256: str
    expected_model_weights_sha256: str
    model_weights_sha256: str | None
    runtime_key: tuple[object, ...]


@dataclass(frozen=True)
class _OptionalRuntime:
    image_module: ModuleType
    numpy: ModuleType
    open_clip: ModuleType
    torch: ModuleType


@dataclass(frozen=True)
class _LoadedRuntime:
    runtime_key: tuple[object, ...]
    model: Any
    preprocess: Any
    text_embeddings: Any
    torch: ModuleType


@dataclass(frozen=True)
class _ImagePayload:
    width: int
    height: int
    rgb_bytes: bytes


@dataclass(frozen=True)
class _SharedImagePayload:
    width: int
    height: int
    shared_memory_name: str
    byte_count: int


@dataclass
class _PersistentWorker:
    """One local-only subprocess retained only for sequential explicit runs."""

    process: Any
    connection: Connection


_RUN_LOCK = threading.Lock()
_LOADED_RUNTIME: _LoadedRuntime | None = None
_PERSISTENT_WORKER: _PersistentWorker | None = None


def build_bioclip_config(
    *,
    model_dir: str | Path | None,
    labels_path: str | Path | None,
    embedding_cache_path: str | Path | None,
    device: str = "cpu",
) -> BioClipAdapterConfig:
    """Build configuration without importing a runtime or touching the filesystem."""

    return BioClipAdapterConfig(
        model_dir=_optional_path(model_dir),
        labels_path=_optional_path(labels_path),
        embedding_cache_path=_optional_path(embedding_cache_path),
        device=device.strip().lower() if isinstance(device, str) else str(device),
    )


def get_bioclip_status(
    config: BioClipAdapterConfig | None,
) -> BioClipAdapterStatus:
    """Inspect explicit local readiness without loading a model or running inference."""

    if config is None or not _all_paths_configured(config):
        return _status(
            config,
            status="not_configured",
            configured=False,
            runtime_available=False,
            detail=(
                "BioCLIP 2 requires explicit local model, labels, and precomputed "
                "embedding-cache paths. No artifacts are downloaded or generated."
            ),
        )

    try:
        validated = _validate_config_files(config, hash_embedding_cache=False)
    except BioClipConfigurationError as error:
        return _status(
            config,
            status="unavailable",
            configured=True,
            runtime_available=False,
            detail=str(error),
        )

    missing_runtime = _missing_runtime_packages()
    if missing_runtime:
        return _status(
            config,
            status="unavailable",
            configured=True,
            runtime_available=False,
            labels_sha256=validated.labels_sha256,
            detail=(
                "Optional BioCLIP runtime dependencies are unavailable: "
                f"{', '.join(missing_runtime)}. The core app remains available."
            ),
        )

    open_clip_version = _installed_open_clip_distribution_version()
    if open_clip_version is None or not _supports_open_clip_version(open_clip_version):
        return _status(
            config,
            status="unavailable",
            configured=True,
            runtime_available=False,
            labels_sha256=validated.labels_sha256,
            detail=(
                "The optional BioCLIP shadow requires the tested OpenCLIP "
                f"{BIOCLIP_OPEN_CLIP_VERSION_SERIES}.x runtime series."
            ),
        )

    return _status(
        config,
        status="available",
        configured=True,
        runtime_available=True,
        labels_sha256=validated.labels_sha256,
        detail=(
            "Explicit local BioCLIP artifacts are configured. A run still validates "
            "the precomputed embedding cache before returning suggestion evidence."
        ),
    )


def prepare_bioclip_run(
    config: BioClipAdapterConfig | None,
) -> BioClipPreparedRun:
    """Hash and bind local artifacts for exact completed-run reuse checks."""

    validated_config = _validate_run_request(config, 1)
    validated = _validate_config_files(
        validated_config,
        hash_model_weights=True,
    )
    return _prepared_run_from_validated(validated)


def run_bioclip_on_image(
    image: Any,
    config: BioClipAdapterConfig | None,
    top_k: int = 3,
) -> BioClipPrediction:
    """Run one local in-memory image or crop through the optional CPU adapter."""

    validated_config = _validate_run_request(config, top_k)
    _acquire_run_lock()
    try:
        return _run_bioclip_locked(image, validated_config, top_k)
    finally:
        _RUN_LOCK.release()


def run_bioclip_from_image_loader(
    image_loader: Callable[[], Any],
    config: BioClipAdapterConfig | None,
    top_k: int = 3,
    *,
    on_prepared: Callable[[BioClipPreparedRun], None] | None = None,
) -> BioClipPrediction:
    """Reserve, validate, and expose safe context before decoding an image."""

    if not callable(image_loader):
        raise BioClipConfigurationError("BioCLIP image_loader must be callable.")
    if on_prepared is not None and not callable(on_prepared):
        raise BioClipConfigurationError("BioCLIP on_prepared must be callable.")
    validated_config = _validate_run_request(config, top_k)
    _acquire_run_lock()
    image: Any | None = None
    try:
        validated = _validate_config_files(validated_config)
        if on_prepared is not None:
            on_prepared(_prepared_run_from_validated(validated))
        image = image_loader()
        return _run_bioclip_locked(
            image,
            validated_config,
            top_k,
            validated=validated,
        )
    finally:
        try:
            if image is not None:
                close_image = getattr(image, "close", None)
                if callable(close_image):
                    close_image()
        finally:
            _RUN_LOCK.release()


def _validate_run_request(
    config: BioClipAdapterConfig | None,
    top_k: int,
) -> BioClipAdapterConfig:
    if isinstance(top_k, bool) or not isinstance(top_k, int):
        raise BioClipConfigurationError("BioCLIP top_k must be an integer.")
    if top_k < 1 or top_k > BIOCLIP_MAX_TOP_K:
        raise BioClipConfigurationError(
            f"BioCLIP top_k must be between 1 and {BIOCLIP_MAX_TOP_K}."
        )
    if config is None or not _all_paths_configured(config):
        raise BioClipConfigurationError(
            "BioCLIP is not configured with all required explicit local paths."
        )
    return config


def _acquire_run_lock() -> None:
    # A second request must fail fast instead of consuming another API thread
    # or decoding another large image while the local worker owns the
    # runtime boundary.
    if not _RUN_LOCK.acquire(blocking=False):
        raise BioClipBusyError(
            "BioCLIP is already processing one local species-suggestion request."
        )


def _run_bioclip_locked(
    image: Any,
    config: BioClipAdapterConfig,
    top_k: int,
    *,
    validated: _ValidatedConfig | None = None,
) -> BioClipPrediction:
    if validated is None:
        validated = _validate_config_files(config)
    missing_runtime = _missing_runtime_packages()
    if missing_runtime:
        raise BioClipRuntimeUnavailableError(
            "Optional BioCLIP runtime dependencies are unavailable: "
            f"{', '.join(missing_runtime)}."
        )
    image_module = _load_pillow_runtime()
    prepared_image = _copy_rgb_image(image, image_module)
    image_payload = _serialize_image(prepared_image)
    return _run_worker_subprocess(
        image_payload,
        config,
        top_k,
        validated=validated,
    )


def _prepared_run_from_validated(
    validated: _ValidatedConfig,
) -> BioClipPreparedRun:
    if validated.embedding_cache_sha256 is None:
        raise BioClipConfigurationError(
            "BioCLIP embedding-cache provenance could not be established."
        )
    return BioClipPreparedRun(
        adapter_id=BIOCLIP_ADAPTER_ID,
        adapter_name=BIOCLIP_ADAPTER_NAME,
        adapter_contract_version=BIOCLIP_ADAPTER_CONTRACT_VERSION,
        model_name=BIOCLIP_MODEL_NAME,
        architecture_id=BIOCLIP_ARCHITECTURE_ID,
        device="cpu",
        candidate_labels=validated.labels,
        candidate_count=len(validated.labels),
        candidate_set_sha256=validated.labels_sha256,
        candidate_fingerprint_algorithm=(BIOCLIP_CANDIDATE_FINGERPRINT_ALGORITHM),
        embedding_cache_sha256=validated.embedding_cache_sha256,
        model_config_sha256=validated.model_config_sha256,
        model_weights_sha256=validated.expected_model_weights_sha256,
        model_weights_name=validated.model_weights_path.name,
        model_weights_verified=False,
        prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
        prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
        preprocessing_id=BIOCLIP_PREPROCESSING_ID,
        preprocessing_sha256=BIOCLIP_PREPROCESSING_SHA256,
        preprocessing_config_json=BIOCLIP_PREPROCESSING_CONFIG_JSON,
        timeout_seconds=BIOCLIP_RUN_TIMEOUT_SECONDS,
        open_clip_version=_installed_distribution_version("open-clip-torch"),
        torch_version=_installed_distribution_version("torch"),
        pillow_version=_installed_distribution_version("Pillow"),
        numpy_version=_installed_distribution_version("numpy"),
    )


def _run_bioclip_in_process(
    image: Any,
    config: BioClipAdapterConfig,
    top_k: int,
) -> BioClipPrediction:
    """Execute inside the isolated local worker process."""

    validated = _validate_config_files(config, hash_model_weights=True)
    runtime_modules = _load_optional_runtime()
    prepared_image = _copy_rgb_image(image, runtime_modules.image_module)
    embeddings = _load_embedding_cache(
        validated,
        runtime_modules.numpy,
    )
    if validated.embedding_cache_sha256 is None:
        raise BioClipConfigurationError(
            "BioCLIP embedding-cache provenance could not be established."
        )
    if validated.model_weights_sha256 is None:
        raise BioClipConfigurationError(
            "BioCLIP model-weight provenance could not be established."
        )
    load_started_ns = time.monotonic_ns()
    runtime, model_reused = _load_or_reuse_runtime(
        validated,
        runtime_modules,
        embeddings,
    )
    model_load_ms = (
        0
        if model_reused
        else max(0, (time.monotonic_ns() - load_started_ns) // 1_000_000)
    )
    open_clip_version = _runtime_package_version(
        runtime_modules.open_clip,
        package_name="OpenCLIP",
    )
    if not _supports_open_clip_version(open_clip_version):
        raise BioClipRuntimeUnavailableError(
            "BioCLIP requires the tested OpenCLIP 3.3 runtime series."
        )
    torch_version = _runtime_package_version(
        runtime_modules.torch,
        package_name="PyTorch",
    )
    pillow_version = _optional_runtime_package_version(
        runtime_modules.image_module,
        distribution_name="Pillow",
    )
    numpy_version = _optional_runtime_package_version(
        runtime_modules.numpy,
        distribution_name="numpy",
    )
    inference_started_ns = time.monotonic_ns()
    scores = _infer_scores(runtime, prepared_image)
    inference_ms = max(0, (time.monotonic_ns() - inference_started_ns) // 1_000_000)
    suggestions = _rank_suggestions(
        validated.labels,
        scores,
        top_k=min(top_k, len(validated.labels)),
    )
    return BioClipPrediction(
        suggestions=suggestions,
        provenance=BioClipProvenance(
            adapter_id=BIOCLIP_ADAPTER_ID,
            adapter_name=BIOCLIP_ADAPTER_NAME,
            model_name=BIOCLIP_MODEL_NAME,
            device="cpu",
            open_clip_version=open_clip_version,
            torch_version=torch_version,
            label_count=len(validated.labels),
            labels_sha256=validated.labels_sha256,
            embedding_cache_sha256=validated.embedding_cache_sha256,
            model_config_sha256=validated.model_config_sha256,
            model_weights_sha256=validated.model_weights_sha256,
            model_weights_name=validated.model_weights_path.name,
            prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
            prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
            score_kind=BIOCLIP_SCORE_KIND,
            calibrated=False,
            adapter_contract_version=BIOCLIP_ADAPTER_CONTRACT_VERSION,
            architecture_id=BIOCLIP_ARCHITECTURE_ID,
            preprocessing_id=BIOCLIP_PREPROCESSING_ID,
            preprocessing_sha256=BIOCLIP_PREPROCESSING_SHA256,
            pillow_version=pillow_version,
            numpy_version=numpy_version,
            model_weights_verified=True,
            model_reused=model_reused,
            model_load_ms=model_load_ms,
            inference_ms=inference_ms,
        ),
        candidate_labels=validated.labels,
        candidate_scores=tuple(scores),
    )


def _run_worker_subprocess(
    image_payload: _ImagePayload,
    config: BioClipAdapterConfig,
    top_k: int,
    *,
    validated: _ValidatedConfig,
) -> BioClipPrediction:
    """Send one bounded image to the lazily started local worker."""

    shared_payload, shared_buffer = _share_image_payload(image_payload)
    try:
        worker = _persistent_bioclip_worker()
        try:
            worker.connection.send((shared_payload, config, top_k))
            ready = worker.connection.poll(BIOCLIP_RUN_TIMEOUT_SECONDS)
        except (EOFError, OSError, ValueError) as error:
            _discard_persistent_bioclip_worker()
            raise BioClipRuntimeUnavailableError(
                "BioCLIP local worker connection failed."
            ) from error
        if not ready:
            _discard_persistent_bioclip_worker()
            raise BioClipTimeoutError(
                "BioCLIP local worker exceeded the local inference timeout."
            )
        try:
            result_bytes = worker.connection.recv_bytes(
                maxlength=BIOCLIP_MAX_RESULT_BYTES
            )
        except (EOFError, OSError) as error:
            _discard_persistent_bioclip_worker()
            raise BioClipRuntimeUnavailableError(
                "BioCLIP local worker exited without a valid result."
            ) from error
        if not worker.process.is_alive():
            _discard_persistent_bioclip_worker()
            raise BioClipRuntimeUnavailableError(
                "BioCLIP local worker exited unexpectedly."
            )
        return _decode_worker_result(
            result_bytes,
            validated=validated,
            top_k=top_k,
        )
    finally:
        _release_shared_image_buffer(shared_buffer)


def _persistent_bioclip_worker() -> _PersistentWorker:
    global _PERSISTENT_WORKER
    if _PERSISTENT_WORKER is not None and _PERSISTENT_WORKER.process.is_alive():
        return _PERSISTENT_WORKER
    _discard_persistent_bioclip_worker()

    parent_connection: Connection | None = None
    worker_connection: Connection | None = None
    process: Any | None = None
    try:
        context = multiprocessing.get_context("spawn")
        parent_connection, worker_connection = context.Pipe(duplex=True)
        process = context.Process(
            target=_bioclip_worker_loop,
            args=(worker_connection,),
            name="mockingbird-bioclip-local",
            daemon=True,
        )
        try:
            process.start()
        except (OSError, RuntimeError) as error:
            raise BioClipRuntimeUnavailableError(
                "BioCLIP local worker could not start safely."
            ) from error
        finally:
            _close_connection(worker_connection)
            worker_connection = None
        _PERSISTENT_WORKER = _PersistentWorker(
            process=process,
            connection=parent_connection,
        )
        parent_connection = None
        return _PERSISTENT_WORKER
    except Exception:
        _close_connection(parent_connection)
        _close_connection(worker_connection)
        if process is not None:
            _stop_worker(process)
            try:
                process.close()
            except (OSError, ValueError):
                pass
        raise


def _discard_persistent_bioclip_worker() -> None:
    global _PERSISTENT_WORKER
    worker = _PERSISTENT_WORKER
    _PERSISTENT_WORKER = None
    if worker is None:
        return
    _close_connection(worker.connection)
    _stop_worker(worker.process)
    if not worker.process.is_alive():
        try:
            worker.process.close()
        except (OSError, ValueError):
            pass


def _shutdown_persistent_bioclip_worker() -> None:
    """Release the retained local worker when its owning app process exits."""

    _discard_persistent_bioclip_worker()


atexit.register(_shutdown_persistent_bioclip_worker)


def _bioclip_worker_loop(receive_connection: Connection) -> None:
    _enforce_worker_offline_environment()
    try:
        while True:
            try:
                request = receive_connection.recv()
            except (EOFError, OSError):
                return
            if not (
                isinstance(request, tuple)
                and len(request) == 3
                and isinstance(request[0], _SharedImagePayload)
                and isinstance(request[1], BioClipAdapterConfig)
                and isinstance(request[2], int)
            ):
                payload = _worker_error("unexpected")
            else:
                payload = _bioclip_worker_payload(*request)
            _send_worker_payload(receive_connection, payload)
    finally:
        _close_connection(receive_connection)


def _bioclip_worker_payload(
    shared_payload: _SharedImagePayload,
    config: BioClipAdapterConfig,
    top_k: int,
) -> dict[str, Any]:
    try:
        image_payload = _read_shared_image_payload(shared_payload)
        image_module = _load_pillow_runtime()
        image = image_module.frombytes(
            "RGB",
            (image_payload.width, image_payload.height),
            image_payload.rgb_bytes,
        )
        prediction = _run_bioclip_in_process(image, config, top_k)
        return _prediction_to_worker_payload(prediction)
    except BioClipConfigurationError:
        return _worker_error("configuration")
    except BioClipRuntimeUnavailableError:
        return _worker_error("runtime_unavailable")
    except BioClipUnsupportedImageError:
        return _worker_error("unsupported_image")
    except BioClipNoResultError:
        return _worker_error("no_result")
    except BioClipOutputError:
        return _worker_error("output")
    except Exception:
        return _worker_error("unexpected")


def _send_worker_payload(connection: Connection, payload: dict[str, Any]) -> None:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > BIOCLIP_MAX_RESULT_BYTES:
            encoded = json.dumps(
                _worker_error("output"),
                separators=(",", ":"),
            ).encode("utf-8")
        connection.send_bytes(encoded)
    except (BrokenPipeError, EOFError, OSError):
        pass


def _bioclip_worker(
    send_connection: Connection,
    shared_payload: _SharedImagePayload,
    config: BioClipAdapterConfig,
    top_k: int,
) -> None:
    """Compatibility entry point for the isolated-worker test."""

    _enforce_worker_offline_environment()
    try:
        _send_worker_payload(
            send_connection,
            _bioclip_worker_payload(shared_payload, config, top_k),
        )
    finally:
        _close_connection(send_connection)


def _enforce_worker_offline_environment() -> None:
    """Prevent optional libraries from reaching a remote model/data hub."""

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"


def _prediction_to_worker_payload(prediction: BioClipPrediction) -> dict[str, Any]:
    candidate_scores = _encode_candidate_scores(prediction)
    return {
        "ok": True,
        "candidate_scores": candidate_scores,
        "suggestions": [
            {
                "rank": suggestion.rank,
                "label": suggestion.label,
                "common_name": suggestion.common_name,
                "scientific_name": suggestion.scientific_name,
                "score": suggestion.score,
                "score_kind": suggestion.score_kind,
                "calibrated": suggestion.calibrated,
            }
            for suggestion in prediction.suggestions
        ],
        "provenance": {
            "adapter_id": prediction.provenance.adapter_id,
            "adapter_name": prediction.provenance.adapter_name,
            "model_name": prediction.provenance.model_name,
            "device": prediction.provenance.device,
            "open_clip_version": prediction.provenance.open_clip_version,
            "torch_version": prediction.provenance.torch_version,
            "label_count": prediction.provenance.label_count,
            "labels_sha256": prediction.provenance.labels_sha256,
            "embedding_cache_sha256": (prediction.provenance.embedding_cache_sha256),
            "model_config_sha256": prediction.provenance.model_config_sha256,
            "model_weights_sha256": prediction.provenance.model_weights_sha256,
            "model_weights_name": prediction.provenance.model_weights_name,
            "prompt_recipe_id": prediction.provenance.prompt_recipe_id,
            "prompt_recipe_sha256": prediction.provenance.prompt_recipe_sha256,
            "score_kind": prediction.provenance.score_kind,
            "calibrated": prediction.provenance.calibrated,
            "adapter_contract_version": (
                prediction.provenance.adapter_contract_version
            ),
            "architecture_id": prediction.provenance.architecture_id,
            "preprocessing_id": prediction.provenance.preprocessing_id,
            "preprocessing_sha256": (prediction.provenance.preprocessing_sha256),
            "pillow_version": prediction.provenance.pillow_version,
            "numpy_version": prediction.provenance.numpy_version,
            "model_weights_verified": (prediction.provenance.model_weights_verified),
            "model_reused": prediction.provenance.model_reused,
            "model_load_ms": prediction.provenance.model_load_ms,
            "inference_ms": prediction.provenance.inference_ms,
        },
    }


def _encode_candidate_scores(
    prediction: BioClipPrediction,
) -> dict[str, Any]:
    labels = prediction.candidate_labels
    scores = prediction.candidate_scores
    if (
        not labels
        or len(labels) != len(scores)
        or len(labels) != prediction.provenance.label_count
        or len(labels) > BIOCLIP_MAX_LABEL_COUNT
        or _label_sha256(labels) != prediction.provenance.labels_sha256
        or any(
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(float(score))
            or float(score) < 0
            or float(score) > 1
            for score in scores
        )
    ):
        raise BioClipOutputError(
            "BioCLIP candidate-score evidence is incomplete or invalid."
        )
    try:
        packed = struct.pack(f"<{len(scores)}d", *(float(score) for score in scores))
    except (OverflowError, struct.error, TypeError, ValueError) as error:
        raise BioClipOutputError(
            "BioCLIP candidate-score evidence could not be encoded safely."
        ) from error
    return {
        "encoding": BIOCLIP_FULL_SCORE_ENCODING,
        "count": len(scores),
        "data": base64.b64encode(packed).decode("ascii"),
    }


def _decode_worker_result(
    encoded: bytes,
    *,
    validated: _ValidatedConfig,
    top_k: int,
) -> BioClipPrediction:
    if not isinstance(encoded, bytes):
        raise BioClipOutputError("BioCLIP worker returned an invalid bounded response.")
    if len(encoded) > BIOCLIP_MAX_RESULT_BYTES:
        raise BioClipOutputError(
            "BioCLIP worker response exceeded the bounded response size."
        )
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BioClipOutputError(
            "BioCLIP worker returned an invalid bounded response."
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("ok"), bool):
        raise BioClipOutputError("BioCLIP worker returned an invalid response.")
    if payload["ok"] is False:
        _raise_worker_error(payload)

    suggestions_value = payload.get("suggestions")
    provenance_value = payload.get("provenance")
    candidate_scores_value = payload.get("candidate_scores")
    if (
        not isinstance(suggestions_value, list)
        or not isinstance(provenance_value, dict)
        or len(suggestions_value) > min(top_k, len(validated.labels))
    ):
        raise BioClipOutputError("BioCLIP worker returned an invalid response.")

    candidate_scores = _decode_candidate_scores(
        candidate_scores_value,
        expected_count=len(validated.labels),
    )
    suggestions = tuple(
        _suggestion_from_worker_value(
            value,
            expected_rank=index,
            allowed_labels=validated.labels,
        )
        for index, value in enumerate(suggestions_value, start=1)
    )
    if not suggestions:
        raise BioClipNoResultError("BioCLIP worker returned no ranked suggestions.")
    expected_suggestions = _rank_suggestions(
        validated.labels,
        list(candidate_scores),
        top_k=min(top_k, len(validated.labels)),
    )
    if suggestions != expected_suggestions:
        raise BioClipOutputError(
            "BioCLIP worker rankings did not match the complete candidate scores."
        )
    provenance = _provenance_from_worker_value(
        provenance_value,
        validated=validated,
    )
    return BioClipPrediction(
        suggestions=suggestions,
        provenance=provenance,
        candidate_labels=validated.labels,
        candidate_scores=candidate_scores,
    )


def _decode_candidate_scores(
    value: Any,
    *,
    expected_count: int,
) -> tuple[float, ...]:
    if (
        not isinstance(value, dict)
        or set(value) != {"encoding", "count", "data"}
        or value.get("encoding") != BIOCLIP_FULL_SCORE_ENCODING
    ):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        )
    count = value.get("count")
    data = value.get("data")
    maximum_encoded_length = ((BIOCLIP_MAX_LABEL_COUNT * 8 + 2) // 3) * 4
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count != expected_count
        or count < 1
        or count > BIOCLIP_MAX_LABEL_COUNT
        or not isinstance(data, str)
        or len(data) > maximum_encoded_length
    ):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        )
    try:
        packed = base64.b64decode(data.encode("ascii"), validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError) as error:
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        ) from error
    if len(packed) != count * 8:
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        )
    try:
        scores = tuple(struct.unpack(f"<{count}d", packed))
    except struct.error as error:
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        ) from error
    if any(not math.isfinite(score) or score < 0 or score > 1 for score in scores):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid candidate-score transport."
        )
    return scores


def _suggestion_from_worker_value(
    value: Any,
    *,
    expected_rank: int,
    allowed_labels: tuple[str, ...],
) -> BioClipRankedSuggestion:
    if not isinstance(value, dict):
        raise BioClipOutputError("BioCLIP worker returned an invalid suggestion.")
    rank = value.get("rank")
    label = value.get("label")
    common_name = value.get("common_name")
    scientific_name = value.get("scientific_name")
    score = value.get("score")
    if (
        rank != expected_rank
        or not isinstance(label, str)
        or label not in allowed_labels
        or common_name is not None
        and not isinstance(common_name, str)
        or scientific_name is not None
        and not isinstance(scientific_name, str)
        or isinstance(score, bool)
        or not isinstance(score, (int, float))
        or not math.isfinite(float(score))
        or float(score) < 0
        or float(score) > 1
        or value.get("score_kind") != BIOCLIP_SCORE_KIND
        or value.get("calibrated") is not False
    ):
        raise BioClipOutputError("BioCLIP worker returned an invalid suggestion.")
    return BioClipRankedSuggestion(
        rank=rank,
        label=label,
        common_name=common_name,
        scientific_name=scientific_name,
        score=float(score),
    )


def _provenance_from_worker_value(
    value: dict[str, Any],
    *,
    validated: _ValidatedConfig,
) -> BioClipProvenance:
    if validated.embedding_cache_sha256 is None:
        raise BioClipOutputError("BioCLIP cache provenance is unavailable.")
    model_weights_sha256 = value.get("model_weights_sha256")
    if not _is_sha256(model_weights_sha256):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid model-weight provenance."
        )
    if not hmac.compare_digest(
        model_weights_sha256.lower(),
        validated.expected_model_weights_sha256.lower(),
    ):
        raise BioClipOutputError(
            "BioCLIP worker model-weight provenance did not match the bound cache."
        )
    open_clip_version = value.get("open_clip_version")
    torch_version = value.get("torch_version")
    pillow_version = value.get("pillow_version")
    numpy_version = value.get("numpy_version")
    if (
        not _is_runtime_version(open_clip_version)
        or not _is_runtime_version(torch_version)
        or not _is_optional_runtime_version(pillow_version)
        or not _is_optional_runtime_version(numpy_version)
    ):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid runtime-version provenance."
        )
    model_reused = value.get("model_reused")
    model_load_ms = value.get("model_load_ms")
    inference_ms = value.get("inference_ms")
    if (
        not isinstance(model_reused, bool)
        or isinstance(model_load_ms, bool)
        or not isinstance(model_load_ms, int)
        or model_load_ms < 0
        or isinstance(inference_ms, bool)
        or not isinstance(inference_ms, int)
        or inference_ms < 0
        or (model_reused and model_load_ms != 0)
        or isinstance(value.get("adapter_contract_version"), bool)
        or value.get("adapter_contract_version") != BIOCLIP_ADAPTER_CONTRACT_VERSION
        or value.get("model_weights_verified") is not True
    ):
        raise BioClipOutputError(
            "BioCLIP worker returned invalid adapter-contract provenance."
        )
    expected = {
        "adapter_id": BIOCLIP_ADAPTER_ID,
        "adapter_name": BIOCLIP_ADAPTER_NAME,
        "model_name": BIOCLIP_MODEL_NAME,
        "device": "cpu",
        "open_clip_version": open_clip_version,
        "torch_version": torch_version,
        "label_count": len(validated.labels),
        "labels_sha256": validated.labels_sha256,
        "embedding_cache_sha256": validated.embedding_cache_sha256,
        "model_config_sha256": validated.model_config_sha256,
        "model_weights_sha256": validated.expected_model_weights_sha256,
        "model_weights_name": validated.model_weights_path.name,
        "prompt_recipe_id": BIOCLIP_PROMPT_RECIPE_ID,
        "prompt_recipe_sha256": BIOCLIP_PROMPT_RECIPE_SHA256,
        "score_kind": BIOCLIP_SCORE_KIND,
        "calibrated": False,
        "adapter_contract_version": BIOCLIP_ADAPTER_CONTRACT_VERSION,
        "architecture_id": BIOCLIP_ARCHITECTURE_ID,
        "preprocessing_id": BIOCLIP_PREPROCESSING_ID,
        "preprocessing_sha256": BIOCLIP_PREPROCESSING_SHA256,
        "pillow_version": pillow_version,
        "numpy_version": numpy_version,
        "model_weights_verified": True,
        "model_reused": model_reused,
        "model_load_ms": model_load_ms,
        "inference_ms": inference_ms,
    }
    if any(
        value.get(key) != expected_value for key, expected_value in expected.items()
    ):
        raise BioClipOutputError(
            "BioCLIP worker provenance did not match the configured local artifacts."
        )
    return BioClipProvenance(**expected)


def _raise_worker_error(payload: dict[str, Any]) -> None:
    error_type = payload.get("error_type")
    detail = payload.get("detail")
    stage = payload.get("stage")
    expected_detail = (
        _WORKER_ERROR_DETAILS.get(error_type) if isinstance(error_type, str) else None
    )
    if expected_detail is None or (detail, stage) != expected_detail:
        raise BioClipOutputError("BioCLIP worker returned an invalid error response.")
    error_classes: dict[str, type[BioClipError]] = {
        "configuration": BioClipConfigurationError,
        "runtime_unavailable": BioClipRuntimeUnavailableError,
        "unsupported_image": BioClipUnsupportedImageError,
        "no_result": BioClipNoResultError,
        "output": BioClipOutputError,
        "unexpected": BioClipWorkerFailureError,
    }
    error_class = error_classes.get(error_type)
    if error_class is None:
        raise BioClipOutputError("BioCLIP worker returned an unknown error response.")
    raise error_class(detail)


def _worker_error(error_type: str) -> dict[str, Any]:
    if error_type not in _WORKER_ERROR_DETAILS:
        error_type = "unexpected"
    detail, stage = _WORKER_ERROR_DETAILS[error_type]
    return {
        "ok": False,
        "error_type": error_type,
        "stage": stage,
        "detail": detail,
    }


def _serialize_image(image: Any) -> _ImagePayload:
    width = int(image.width)
    height = int(image.height)
    if width < 1 or height < 1 or width * height > BIOCLIP_MAX_IMAGE_PIXELS:
        raise BioClipUnsupportedImageError(
            "BioCLIP in-memory image exceeds the bounded pixel count."
        )
    try:
        rgb_bytes = image.tobytes()
    except Exception as error:
        raise BioClipUnsupportedImageError(
            "BioCLIP could not serialize the in-memory image."
        ) from error
    expected_size = width * height * 3
    if len(rgb_bytes) != expected_size:
        raise BioClipUnsupportedImageError(
            "BioCLIP in-memory RGB image payload is invalid."
        )
    return _ImagePayload(width=width, height=height, rgb_bytes=rgb_bytes)


def _share_image_payload(
    image_payload: _ImagePayload,
) -> tuple[_SharedImagePayload, shared_memory.SharedMemory]:
    try:
        buffer = shared_memory.SharedMemory(
            create=True,
            size=len(image_payload.rgb_bytes),
        )
    except (OSError, ValueError) as error:
        raise BioClipRuntimeUnavailableError(
            "BioCLIP could not allocate bounded local worker image memory."
        ) from error
    try:
        buffer.buf[: len(image_payload.rgb_bytes)] = image_payload.rgb_bytes
    except Exception as error:
        _release_shared_image_buffer(buffer)
        raise BioClipRuntimeUnavailableError(
            "BioCLIP could not prepare bounded local worker image memory."
        ) from error
    return (
        _SharedImagePayload(
            width=image_payload.width,
            height=image_payload.height,
            shared_memory_name=buffer.name,
            byte_count=len(image_payload.rgb_bytes),
        ),
        buffer,
    )


def _read_shared_image_payload(
    payload: _SharedImagePayload,
) -> _ImagePayload:
    expected_size = payload.width * payload.height * 3
    if (
        payload.width < 1
        or payload.height < 1
        or payload.width * payload.height > BIOCLIP_MAX_IMAGE_PIXELS
        or payload.byte_count != expected_size
        or not isinstance(payload.shared_memory_name, str)
        or not payload.shared_memory_name
        or len(payload.shared_memory_name) > 256
    ):
        raise BioClipUnsupportedImageError("BioCLIP worker image metadata is invalid.")
    try:
        buffer = shared_memory.SharedMemory(
            name=payload.shared_memory_name,
            create=False,
        )
    except (FileNotFoundError, OSError, ValueError) as error:
        raise BioClipRuntimeUnavailableError(
            "BioCLIP worker image memory was unavailable."
        ) from error
    try:
        if buffer.size < payload.byte_count:
            raise BioClipUnsupportedImageError(
                "BioCLIP worker image memory is truncated."
            )
        return _ImagePayload(
            width=payload.width,
            height=payload.height,
            rgb_bytes=bytes(buffer.buf[: payload.byte_count]),
        )
    finally:
        try:
            buffer.close()
        except (BufferError, OSError):
            pass


def _release_shared_image_buffer(buffer: shared_memory.SharedMemory) -> None:
    try:
        buffer.close()
    except (BufferError, OSError):
        pass
    try:
        buffer.unlink()
    except (FileNotFoundError, OSError):
        pass


def _join_worker(process: Any) -> None:
    process.join(BIOCLIP_WORKER_STOP_GRACE_SECONDS)


def _stop_worker(process: Any) -> None:
    if process.is_alive():
        process.terminate()
        process.join(BIOCLIP_WORKER_STOP_GRACE_SECONDS)
    if process.is_alive():
        process.kill()
        process.join(BIOCLIP_WORKER_STOP_GRACE_SECONDS)


def _close_connection(connection: Any) -> None:
    if connection is None:
        return
    try:
        connection.close()
    except (OSError, ValueError):
        pass


def _validate_config_files(
    config: BioClipAdapterConfig,
    *,
    hash_embedding_cache: bool = True,
    hash_model_weights: bool = False,
) -> _ValidatedConfig:
    if config.device != "cpu":
        raise BioClipConfigurationError(
            "The first BioCLIP adapter supports CPU execution only."
        )
    if not _all_paths_configured(config):
        raise BioClipConfigurationError(
            "BioCLIP requires model, labels, and embedding-cache paths."
        )

    model_dir = _resolve_directory(config.model_dir, "BioCLIP model directory")
    labels_path = _resolve_file(config.labels_path, "BioCLIP labels file")
    embedding_cache_path = _resolve_file(
        config.embedding_cache_path,
        "BioCLIP precomputed embedding cache",
    )
    if embedding_cache_path.suffix.lower() != ".npz":
        raise BioClipConfigurationError(
            "BioCLIP embedding cache must be a precomputed .npz file."
        )
    if _file_identity(embedding_cache_path)[0] > BIOCLIP_MAX_EMBEDDING_CACHE_BYTES:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache exceeds the bounded local cache size."
        )

    model_config_path = _resolve_file(
        model_dir / _MODEL_CONFIG_NAME,
        "BioCLIP local OpenCLIP configuration",
    )
    model_weights_path = _find_safe_model_weights(model_dir)
    if _file_identity(model_weights_path)[0] > BIOCLIP_MAX_MODEL_WEIGHTS_BYTES:
        raise BioClipConfigurationError(
            "BioCLIP model weights exceed the bounded local file size."
        )
    _validate_model_config(model_config_path)
    _validate_cache_container(embedding_cache_path)

    labels = _read_labels(labels_path)
    labels_sha256 = _label_sha256(labels)
    model_config_sha256 = _file_sha256(model_config_path)
    cache_metadata = _read_cache_metadata(embedding_cache_path)
    _validate_cached_digest(
        name="labels",
        expected=labels_sha256,
        cached=cache_metadata["label_sha256"],
    )
    _validate_cached_digest(
        name="model configuration",
        expected=model_config_sha256,
        cached=cache_metadata["model_config_sha256"],
    )
    _validate_cached_digest(
        name="prompt recipe",
        expected=BIOCLIP_PROMPT_RECIPE_SHA256,
        cached=cache_metadata["prompt_recipe_sha256"],
    )
    expected_model_weights_sha256 = cache_metadata["model_weights_sha256"]
    embedding_cache_sha256 = (
        _file_sha256(embedding_cache_path) if hash_embedding_cache else None
    )
    model_weights_sha256 = (
        _file_sha256(model_weights_path) if hash_model_weights else None
    )
    if model_weights_sha256 is not None:
        _validate_cached_digest(
            name="model weights",
            expected=model_weights_sha256,
            cached=expected_model_weights_sha256,
        )
    runtime_key = (
        str(model_dir),
        _file_identity(model_config_path),
        _file_identity(model_weights_path),
        model_weights_sha256 or "weights_not_hashed",
        str(labels_path),
        labels_sha256,
        str(embedding_cache_path),
        _file_identity(embedding_cache_path),
        embedding_cache_sha256 or _file_identity(embedding_cache_path),
    )
    return _ValidatedConfig(
        model_dir=model_dir,
        model_config_path=model_config_path,
        model_weights_path=model_weights_path,
        labels_path=labels_path,
        embedding_cache_path=embedding_cache_path,
        labels=labels,
        labels_sha256=labels_sha256,
        embedding_cache_sha256=embedding_cache_sha256,
        model_config_sha256=model_config_sha256,
        expected_model_weights_sha256=expected_model_weights_sha256,
        model_weights_sha256=model_weights_sha256,
        runtime_key=runtime_key,
    )


def _validate_model_config(path: Path) -> None:
    try:
        payload = json.loads(
            _read_bounded_utf8(
                path,
                maximum_bytes=BIOCLIP_MAX_MODEL_CONFIG_BYTES,
                description="BioCLIP local OpenCLIP configuration",
            )
        )
    except json.JSONDecodeError as error:
        raise BioClipConfigurationError(
            "BioCLIP local OpenCLIP configuration is unreadable or invalid."
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("model_cfg"), dict):
        raise BioClipConfigurationError(
            "BioCLIP local OpenCLIP configuration is missing model_cfg."
        )
    remote_keys = _remote_capable_config_keys(payload)
    if remote_keys:
        raise BioClipConfigurationError(
            "BioCLIP local OpenCLIP configuration contains remote-capable "
            f"fields: {', '.join(remote_keys)}."
        )
    if (
        payload.get("model_cfg") != _EXPECTED_BIOCLIP_MODEL_CONFIG
        or payload.get("preprocess_cfg") != _EXPECTED_BIOCLIP_PREPROCESS_CONFIG
    ):
        raise BioClipConfigurationError(
            "BioCLIP local OpenCLIP configuration does not match the bounded "
            "BioCLIP 2 ViT-L/14 architecture and preprocessing contract."
        )


def _remote_capable_config_keys(value: Any) -> list[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                normalized_key = str(key).strip().lower()
                if normalized_key in _REMOTE_CAPABLE_MODEL_CONFIG_KEYS:
                    found.add(normalized_key)
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return sorted(found)


def _validate_cache_container(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as error:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache is not a readable .npz archive."
        ) from error
    member_names = [info.filename for info in infos]
    if (
        len(member_names) != len(set(member_names))
        or set(member_names) != _REQUIRED_CACHE_MEMBERS
    ):
        raise BioClipConfigurationError(
            "BioCLIP embedding cache must contain only the required bound arrays."
        )
    uncompressed_size = sum(info.file_size for info in infos)
    if uncompressed_size > BIOCLIP_MAX_EMBEDDING_CACHE_UNCOMPRESSED_BYTES:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache exceeds the bounded uncompressed size."
        )


def _read_cache_metadata(path: Path) -> dict[str, str]:
    member_names = (
        "label_sha256",
        "model_config_sha256",
        "model_weights_sha256",
        "prompt_recipe_sha256",
    )
    try:
        with zipfile.ZipFile(path) as archive:
            values = {
                name: _decode_npy_text_scalar(
                    archive.read(f"{name}.npy"),
                    name=name,
                )
                for name in member_names
                if archive.getinfo(f"{name}.npy").file_size
                <= BIOCLIP_MAX_CACHE_METADATA_MEMBER_BYTES
            }
    except (KeyError, OSError, zipfile.BadZipFile) as error:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache metadata could not be read safely."
        ) from error
    if set(values) != set(member_names):
        raise BioClipConfigurationError(
            "BioCLIP embedding cache metadata exceeds the bounded member size."
        )
    return values


def _decode_npy_text_scalar(payload: bytes, *, name: str) -> str:
    if (
        len(payload) > BIOCLIP_MAX_CACHE_METADATA_MEMBER_BYTES
        or len(payload) < 10
        or payload[:6] != b"\x93NUMPY"
    ):
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )
    major_version = payload[6]
    if major_version == 1:
        header_size_offset = 8
        header_size_bytes = 2
    elif major_version in {2, 3}:
        header_size_offset = 8
        header_size_bytes = 4
    else:
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )
    header_offset = header_size_offset + header_size_bytes
    if len(payload) < header_offset:
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )
    header_size = int.from_bytes(
        payload[header_size_offset:header_offset],
        "little",
    )
    data_offset = header_offset + header_size
    if data_offset > len(payload):
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )
    try:
        header_encoding = "utf-8" if major_version == 3 else "latin1"
        header = ast.literal_eval(
            payload[header_offset:data_offset].decode(header_encoding).strip()
        )
    except (UnicodeError, ValueError, SyntaxError) as error:
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        ) from error
    if (
        not isinstance(header, dict)
        or header.get("shape") != ()
        or header.get("fortran_order") is not False
        or not isinstance(header.get("descr"), str)
    ):
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )

    descriptor = header["descr"]
    data = payload[data_offset:]
    try:
        if descriptor.startswith("<U") or descriptor.startswith(">U"):
            character_count = int(descriptor[2:])
            byte_order = "utf-32-le" if descriptor[0] == "<" else "utf-32-be"
            if len(data) != character_count * 4:
                raise ValueError("invalid_unicode_size")
            value = data.decode(byte_order).rstrip("\x00")
        elif descriptor.startswith("|S"):
            character_count = int(descriptor[2:])
            if len(data) != character_count:
                raise ValueError("invalid_bytes_size")
            value = data.rstrip(b"\x00").decode("ascii")
        else:
            raise ValueError("unsupported_scalar_dtype")
    except (UnicodeError, ValueError) as error:
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        ) from error
    if not _is_sha256(value):
        raise BioClipConfigurationError(
            f"BioCLIP embedding cache {name} metadata is invalid."
        )
    return value.lower()


def _read_labels(path: Path) -> tuple[str, ...]:
    labels = tuple(
        line.strip()
        for line in _read_bounded_utf8(
            path,
            maximum_bytes=BIOCLIP_MAX_LABELS_FILE_BYTES,
            description="BioCLIP labels file",
        ).splitlines()
        if line.strip()
    )
    if not labels:
        raise BioClipConfigurationError("BioCLIP labels file is empty.")
    if len(labels) > BIOCLIP_MAX_LABEL_COUNT:
        raise BioClipConfigurationError("BioCLIP labels file contains too many labels.")
    if any(len(label) > BIOCLIP_MAX_LABEL_LENGTH for label in labels):
        raise BioClipConfigurationError(
            "BioCLIP labels file contains an oversized label."
        )
    folded = [label.casefold() for label in labels]
    if len(set(folded)) != len(folded):
        raise BioClipConfigurationError(
            "BioCLIP labels file contains duplicate candidate labels."
        )
    return labels


def _read_bounded_utf8(
    path: Path,
    *,
    maximum_bytes: int,
    description: str,
) -> str:
    try:
        with path.open("rb") as handle:
            payload = handle.read(maximum_bytes + 1)
    except OSError as error:
        raise BioClipConfigurationError(f"{description} could not be read.") from error
    if len(payload) > maximum_bytes:
        raise BioClipConfigurationError(
            f"{description} exceeds the bounded local file size."
        )
    try:
        return payload.decode("utf-8")
    except UnicodeError as error:
        raise BioClipConfigurationError(
            f"{description} must be readable UTF-8 text."
        ) from error


def _load_embedding_cache(
    validated: _ValidatedConfig,
    numpy: ModuleType,
) -> Any:
    if validated.model_weights_sha256 is None:
        raise BioClipConfigurationError(
            "BioCLIP model weights must be hashed inside the local worker."
        )
    try:
        with numpy.load(validated.embedding_cache_path, allow_pickle=False) as cache:
            required_arrays = {
                member.removesuffix(".npy") for member in _REQUIRED_CACHE_MEMBERS
            }
            if set(cache.files) != required_arrays:
                raise BioClipConfigurationError(
                    "BioCLIP embedding cache must contain only the required bound arrays."
                )
            cache_label_sha256 = _cache_digest_value(cache["label_sha256"])
            _validate_cached_label_sha256(
                expected=validated.labels_sha256,
                cached=cache_label_sha256,
            )
            _validate_cached_digest(
                name="model configuration",
                expected=validated.model_config_sha256,
                cached=_cache_digest_value(cache["model_config_sha256"]),
            )
            _validate_cached_digest(
                name="model weights",
                expected=validated.model_weights_sha256,
                cached=_cache_digest_value(cache["model_weights_sha256"]),
            )
            _validate_cached_digest(
                name="prompt recipe",
                expected=BIOCLIP_PROMPT_RECIPE_SHA256,
                cached=_cache_digest_value(cache["prompt_recipe_sha256"]),
            )
            embeddings = numpy.asarray(cache["embeddings"])
            if (
                embeddings.ndim != 2
                or embeddings.shape[0] != len(validated.labels)
                or embeddings.shape[1] != BIOCLIP_EMBEDDING_DIMENSION
            ):
                raise BioClipConfigurationError(
                    "BioCLIP embedding cache shape does not match the configured labels."
                )
            if not numpy.issubdtype(embeddings.dtype, numpy.floating):
                raise BioClipConfigurationError(
                    "BioCLIP embedding cache must contain floating-point vectors."
                )
            if not bool(numpy.isfinite(embeddings).all()):
                raise BioClipConfigurationError(
                    "BioCLIP embedding cache contains non-finite vectors."
                )
            embeddings = numpy.array(embeddings, dtype=numpy.float32, copy=True)
    except BioClipConfigurationError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache could not be validated."
        ) from error

    norms = numpy.linalg.norm(embeddings, axis=1)
    if not bool(numpy.allclose(norms, 1.0, rtol=1e-3, atol=1e-3)):
        raise BioClipConfigurationError(
            "BioCLIP embedding cache must contain normalized precomputed vectors."
        )
    return embeddings


def _cache_digest_value(value: Any) -> str:
    try:
        if getattr(value, "shape", None) != ():
            raise ValueError("digest_not_scalar")
        digest = value.item()
        if isinstance(digest, bytes):
            digest = digest.decode("ascii")
    except (AttributeError, UnicodeError, ValueError) as error:
        raise BioClipConfigurationError(
            "BioCLIP embedding cache label SHA-256 metadata is invalid."
        ) from error
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest.lower())
    ):
        raise BioClipConfigurationError(
            "BioCLIP embedding cache label SHA-256 metadata is invalid."
        )
    return digest.lower()


def _validate_cached_label_sha256(*, expected: str, cached: str) -> None:
    _validate_cached_digest(name="labels", expected=expected, cached=cached)


def _validate_cached_digest(*, name: str, expected: str, cached: str) -> None:
    if not hmac.compare_digest(expected.lower(), cached.lower()):
        raise BioClipConfigurationError(
            f"BioCLIP precomputed embedding cache does not match {name}."
        )


def _load_optional_runtime() -> _OptionalRuntime:
    try:
        return _OptionalRuntime(
            image_module=import_module("PIL.Image"),
            numpy=import_module("numpy"),
            open_clip=import_module("open_clip"),
            torch=import_module("torch"),
        )
    except (ImportError, OSError) as error:
        raise BioClipRuntimeUnavailableError(
            "Optional BioCLIP runtime dependencies are unavailable. "
            "The core app can continue without species inference."
        ) from error


def _runtime_package_version(module: ModuleType, *, package_name: str) -> str:
    version = getattr(module, "__version__", None)
    if not _is_runtime_version(version):
        raise BioClipRuntimeUnavailableError(
            f"{package_name} did not expose bounded runtime-version provenance."
        )
    return version


def _optional_runtime_package_version(
    module: Any,
    *,
    distribution_name: str,
) -> str | None:
    version = getattr(module, "__version__", None)
    if _is_runtime_version(version):
        return version
    return _installed_distribution_version(distribution_name)


def _installed_distribution_version(distribution_name: str) -> str | None:
    try:
        version = metadata.version(distribution_name)
    except (metadata.PackageNotFoundError, OSError, ValueError):
        return None
    return version if _is_runtime_version(version) else None


def _installed_open_clip_distribution_version() -> str | None:
    return _installed_distribution_version("open-clip-torch")


def _supports_open_clip_version(version: str) -> bool:
    return version == BIOCLIP_OPEN_CLIP_VERSION_SERIES or version.startswith(
        f"{BIOCLIP_OPEN_CLIP_VERSION_SERIES}."
    )


def _is_runtime_version(value: object) -> bool:
    return (
        isinstance(value, str)
        and 1 <= len(value) <= 128
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", value) is not None
    )


def _is_optional_runtime_version(value: object) -> bool:
    return value is None or _is_runtime_version(value)


def _load_pillow_runtime() -> ModuleType:
    try:
        return import_module("PIL.Image")
    except (ImportError, OSError) as error:
        raise BioClipRuntimeUnavailableError(
            "Optional BioCLIP image runtime is unavailable. "
            "The core app can continue without species inference."
        ) from error


def _copy_rgb_image(image: Any, image_module: ModuleType) -> Any:
    image_type = getattr(image_module, "Image", None)
    if image_type is None or not isinstance(image, image_type):
        raise BioClipUnsupportedImageError(
            "BioCLIP requires an already-decoded in-memory Pillow image or crop."
        )
    try:
        if image.width < 1 or image.height < 1:
            raise BioClipUnsupportedImageError("BioCLIP image is empty.")
        if image.width * image.height > BIOCLIP_MAX_IMAGE_PIXELS:
            raise BioClipUnsupportedImageError(
                "BioCLIP image exceeds the bounded pixel count."
            )
        return image.convert("RGB").copy()
    except BioClipUnsupportedImageError:
        raise
    except Exception as error:
        raise BioClipUnsupportedImageError(
            "BioCLIP could not prepare the in-memory image."
        ) from error


def _load_or_reuse_runtime(
    validated: _ValidatedConfig,
    modules: _OptionalRuntime,
    embeddings: Any,
) -> tuple[_LoadedRuntime, bool]:
    global _LOADED_RUNTIME
    if (
        _LOADED_RUNTIME is not None
        and _LOADED_RUNTIME.runtime_key == validated.runtime_key
    ):
        return _LOADED_RUNTIME, True
    _LOADED_RUNTIME = None
    _LOADED_RUNTIME = _load_runtime(validated, modules, embeddings)
    return _LOADED_RUNTIME, False


def _load_runtime(
    validated: _ValidatedConfig,
    modules: _OptionalRuntime,
    embeddings: Any,
) -> _LoadedRuntime:
    model_identifier = f"local-dir:{validated.model_dir}"
    try:
        model, preprocess = modules.open_clip.create_model_from_pretrained(
            model_identifier,
            device="cpu",
            return_transform=True,
        )
        model.eval()
        text_embeddings = modules.torch.from_numpy(embeddings).to(
            device="cpu",
            dtype=modules.torch.float32,
        )
    except (FileNotFoundError, ValueError) as error:
        raise BioClipConfigurationError(
            "BioCLIP could not load the explicit local model artifacts."
        ) from error
    except (ImportError, OSError) as error:
        raise BioClipRuntimeUnavailableError(
            "Optional BioCLIP runtime could not load on this host."
        ) from error
    except Exception as error:  # pragma: no cover - depends on optional model runtime.
        raise BioClipRuntimeUnavailableError(
            "Optional BioCLIP runtime could not initialize the local model."
        ) from error

    return _LoadedRuntime(
        runtime_key=validated.runtime_key,
        model=model,
        preprocess=preprocess,
        text_embeddings=text_embeddings,
        torch=modules.torch,
    )


def _infer_scores(runtime: _LoadedRuntime, image: Any) -> list[float]:
    try:
        prepared = (
            runtime.preprocess(image)
            .unsqueeze(0)
            .to(
                device="cpu",
                dtype=runtime.torch.float32,
            )
        )
        with runtime.torch.inference_mode():
            image_features = runtime.model.encode_image(prepared)
            image_features = image_features / image_features.norm(
                dim=-1,
                keepdim=True,
            ).clamp_min(1e-12)
            logits = (
                runtime.model.logit_scale.exp()
                * image_features
                @ runtime.text_embeddings.T
            )
            probabilities = logits.softmax(dim=-1)
        values = probabilities[0].detach().cpu().tolist()
    except Exception as error:  # pragma: no cover - depends on optional model runtime.
        raise BioClipOutputError("BioCLIP inference failed safely.") from error

    if not isinstance(values, list):
        raise BioClipOutputError("BioCLIP returned invalid candidate scores.")
    if not values:
        raise BioClipNoResultError("BioCLIP returned no candidate scores.")
    try:
        scores = [float(value) for value in values]
    except (TypeError, ValueError) as error:
        raise BioClipOutputError(
            "BioCLIP returned invalid candidate scores."
        ) from error
    if any(not math.isfinite(score) or score < 0 or score > 1 for score in scores):
        raise BioClipOutputError("BioCLIP returned invalid candidate scores.")
    return scores


def _rank_suggestions(
    labels: tuple[str, ...],
    scores: list[float],
    *,
    top_k: int,
) -> tuple[BioClipRankedSuggestion, ...]:
    if len(scores) != len(labels):
        raise BioClipOutputError(
            "BioCLIP score count does not match the configured candidate labels."
        )
    ranked_indexes = sorted(
        range(len(labels)),
        key=lambda index: (-scores[index], index),
    )[:top_k]
    suggestions: list[BioClipRankedSuggestion] = []
    for rank, index in enumerate(ranked_indexes, start=1):
        label = labels[index]
        common_name, scientific_name = _split_taxonomy_label(label)
        suggestions.append(
            BioClipRankedSuggestion(
                rank=rank,
                label=label,
                common_name=common_name,
                scientific_name=scientific_name,
                score=scores[index],
            )
        )
    return tuple(suggestions)


def _split_taxonomy_label(label: str) -> tuple[str | None, str | None]:
    match = _SCIENTIFIC_LABEL.fullmatch(label)
    if match is None:
        return (label, None)
    return (match.group("common"), match.group("scientific"))


def _missing_runtime_packages() -> list[str]:
    missing: list[str] = []
    for package in _RUNTIME_PACKAGES:
        try:
            spec = util.find_spec(package)
        except (ImportError, AttributeError, ValueError):
            spec = None
        if spec is None:
            missing.append(package)
    return missing


def _find_safe_model_weights(model_dir: Path) -> Path:
    try:
        checkpoint_files = [
            path
            for path in model_dir.iterdir()
            if path.is_file() and path.suffix.lower() in _CHECKPOINT_SUFFIXES
        ]
    except OSError as error:
        raise BioClipConfigurationError(
            "BioCLIP model directory could not be inspected safely."
        ) from error
    if (
        len(checkpoint_files) != 1
        or checkpoint_files[0].name not in _SAFE_MODEL_WEIGHT_NAMES
    ):
        raise BioClipConfigurationError(
            "BioCLIP model directory must contain exactly one supported local "
            ".safetensors weights file and no alternate checkpoint files."
        )
    return checkpoint_files[0].resolve()


def _resolve_directory(path: Path | None, description: str) -> Path:
    if path is None:
        raise BioClipConfigurationError(f"{description} is not configured.")
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as error:
        raise BioClipConfigurationError(f"{description} was not found.") from error
    if not resolved.is_dir():
        raise BioClipConfigurationError(f"{description} must be a directory.")
    return resolved


def _resolve_file(path: Path | None, description: str) -> Path:
    if path is None:
        raise BioClipConfigurationError(f"{description} is not configured.")
    try:
        resolved = path.expanduser().resolve(strict=True)
    except OSError as error:
        raise BioClipConfigurationError(f"{description} was not found.") from error
    if not resolved.is_file():
        raise BioClipConfigurationError(f"{description} must be a file.")
    return resolved


def _label_sha256(labels: tuple[str, ...]) -> str:
    return hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise BioClipConfigurationError(
            "BioCLIP local artifact could not be read."
        ) from error
    return digest.hexdigest()


def _file_identity(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except OSError as error:
        raise BioClipConfigurationError(
            "BioCLIP local artifact is unavailable."
        ) from error
    return (stat.st_size, stat.st_mtime_ns)


def _all_paths_configured(config: BioClipAdapterConfig) -> bool:
    return (
        config.model_dir is not None
        and config.labels_path is not None
        and config.embedding_cache_path is not None
    )


def _optional_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return Path(value).expanduser()


def _status(
    config: BioClipAdapterConfig | None,
    *,
    status: BioClipAdapterStatusValue,
    configured: bool,
    runtime_available: bool,
    detail: str,
    labels_sha256: str | None = None,
) -> BioClipAdapterStatus:
    return BioClipAdapterStatus(
        status=status,
        configured=configured,
        runtime_available=runtime_available,
        detail=detail,
        model_dir=_path_text(config.model_dir if config else None),
        labels_path=_path_text(config.labels_path if config else None),
        embedding_cache_path=_path_text(
            config.embedding_cache_path if config else None
        ),
        device=config.device if config else "cpu",
        labels_sha256=labels_sha256,
    )


def _path_text(path: Path | None) -> str | None:
    return str(path) if path is not None else None
