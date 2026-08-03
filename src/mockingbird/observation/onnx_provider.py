"""Optional ONNX Runtime CUDA replay provider; evidence-only and shadow-only."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from importlib import import_module, util
import json
import math
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from mockingbird.observation.contracts import (
    DetectionObservation, FramePacket, ObservationProviderCapabilities,
    ObservationProviderDescriptor, ObservationProviderHealth, ObservationResult,
)
from mockingbird.observation.replay import ReplayValidationError, semantic_fingerprint

BUNDLE_SCHEMA_VERSION = 1
PROVIDER_VERSION = "onnx-cuda-shadow-v1"
PREPROCESS_VERSION = "image-letterbox-v1"
POSTPROCESS_VERSION = "xyxy-score-class-v1"
DECODER_KEY = "xyxy-score-class-v1"
MAX_OBSERVATIONS_PER_FRAME = 500
MAX_INPUT_PIXELS = 16_777_216
MAX_DECODE_ROWS = 10_000
MAX_REPLAY_OBSERVATIONS = 100_000


class CudaRuntime(Protocol):
    def available_providers(self) -> tuple[str, ...]: ...
    def runtime_version(self) -> str | None: ...
    def create_session(self, model_path: Path, *, input_name: str, output_names: tuple[str, ...]) -> Any: ...


class OptionalOrtCudaRuntime:
    """Lazy ONNX Runtime adapter; probe never constructs a session."""

    def available_providers(self) -> tuple[str, ...]:
        if util.find_spec("onnxruntime") is None:
            return ()
        try:
            runtime = import_module("onnxruntime")
            return tuple(runtime.get_available_providers())
        except Exception:
            return ()

    def runtime_version(self) -> str | None:
        if util.find_spec("onnxruntime") is None:
            return None
        try:
            return str(import_module("onnxruntime").__version__)
        except Exception:
            return None

    def create_session(self, model_path: Path, *, input_name: str, output_names: tuple[str, ...]) -> Any:
        try:
            runtime = import_module("onnxruntime")
            options = runtime.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
            return runtime.InferenceSession(str(model_path), sess_options=options, providers=["CUDAExecutionProvider"])
        except Exception as error:
            raise ReplayValidationError("onnx_cuda_session_load_failed") from error


@dataclass(frozen=True)
class OnnxModelBundle:
    schema_version: int
    model_key: str
    model_version: str
    model_path: Path
    model_fingerprint: str
    model_format: str
    license_name: str
    redistribution: str
    input_name: str
    input_width: int
    input_height: int
    input_dtype: str
    input_scale: float
    channel_order: str
    color_format: str
    letterbox_fill: tuple[int, int, int]
    normalization_mean: tuple[float, float, float]
    normalization_std: tuple[float, float, float]
    resize_mode: str
    output_names: tuple[str, ...]
    decoder_key: str
    broad_classes: tuple[str, ...]
    animal_classes: tuple[str, ...]
    taxonomy: str
    provenance: str
    provider_compatibility: tuple[str, ...]
    limitations: tuple[str, ...]
    score_threshold: float = 0.25
    max_observations_per_frame: int = 100

    @property
    def fingerprint(self) -> str:
        value = asdict(self)
        value.pop("model_path")
        return semantic_fingerprint(value)

    @classmethod
    def load(cls, manifest_path: Path) -> "OnnxModelBundle":
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ReplayValidationError("invalid_model_bundle_path")
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReplayValidationError("invalid_model_bundle_json") from error
        if not isinstance(data, dict) or data.get("schema_version") != BUNDLE_SCHEMA_VERSION:
            raise ReplayValidationError("unsupported_model_bundle_version")
        model_file = data.get("model_file")
        if not isinstance(model_file, str) or not model_file or Path(model_file).is_absolute() or ".." in Path(model_file).parts:
            raise ReplayValidationError("invalid_model_path")
        model_root = manifest_path.parent.resolve(strict=True)
        model_path = manifest_path.parent / model_file
        if model_path.is_symlink() or not model_path.is_file() or model_path.suffix.lower() != ".onnx":
            raise ReplayValidationError("invalid_model_path")
        model_path = model_path.resolve(strict=True)
        if not model_path.is_relative_to(model_root):
            raise ReplayValidationError("invalid_model_path")
        actual_hash = _hash_file(model_path)
        if data.get("model_fingerprint") != actual_hash:
            raise ReplayValidationError("model_fingerprint_mismatch")
        if data.get("model_format") != "ONNX":
            raise ReplayValidationError("unsupported_model_format")
        decoder = data.get("decoder_key")
        if decoder != DECODER_KEY:
            raise ReplayValidationError("unsupported_decoder")
        try:
            bundle = cls(
                schema_version=data["schema_version"], model_key=_text(data, "model_key"),
                model_version=_text(data, "model_version"), model_path=model_path.resolve(),
                model_fingerprint=actual_hash, model_format="ONNX", license_name=_text(data, "license"),
                redistribution=_text(data, "redistribution"), input_name=_text(data, "input_name"),
                input_width=_positive_int(data, "input_width"), input_height=_positive_int(data, "input_height"),
                input_dtype=_choice(data, "input_dtype", {"float32"}),
                input_scale=float(data["input_scale"]),
                channel_order=_choice(data, "channel_order", {"NCHW"}),
                color_format=_choice(data, "color_format", {"RGB", "BGR"}),
                letterbox_fill=_byte_triple(data, "letterbox_fill"),
                normalization_mean=_triple(data, "normalization_mean"),
                normalization_std=_triple(data, "normalization_std", nonzero=True),
                resize_mode=_choice(data, "resize_mode", {"stretch", "letterbox"}),
                output_names=tuple(_string_list(data, "output_names")), decoder_key=decoder,
                broad_classes=tuple(_string_list(data, "broad_classes")),
                animal_classes=tuple(_string_list(data, "animal_classes")),
                taxonomy=_text(data, "taxonomy"),
                provenance=_text(data, "provenance"),
                provider_compatibility=tuple(_string_list(data, "provider_compatibility")),
                limitations=tuple(_string_list(data, "limitations")),
                score_threshold=float(data.get("score_threshold", 0.25)),
                max_observations_per_frame=int(data.get("max_observations_per_frame", 100)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ReplayValidationError("invalid_model_bundle") from error
        if (
            "onnx-cuda" not in bundle.provider_compatibility
            or not 0 <= bundle.score_threshold <= 1
            or not 1 <= bundle.max_observations_per_frame <= MAX_OBSERVATIONS_PER_FRAME
            or bundle.input_width * bundle.input_height > MAX_INPUT_PIXELS
            or not set(bundle.animal_classes) <= set(bundle.broad_classes)
            or not math.isfinite(bundle.input_scale)
            or not 0 < bundle.input_scale <= 1
        ):
            raise ReplayValidationError("invalid_model_bundle")
        return bundle


@dataclass(frozen=True)
class _Transform:
    scale_x: float
    scale_y: float
    pad_x: float
    pad_y: float
    source_width: int
    source_height: int


class OnnxCudaObservationProvider:
    provider_id = "onnx-cuda"
    display_name = "ONNX Runtime CUDA Shadow Provider"
    capabilities = ObservationProviderCapabilities(False, True, True, False, False, False)

    def __init__(self, *, runtime: CudaRuntime | None = None, bundle: OnnxModelBundle | None = None) -> None:
        self._runtime = runtime or OptionalOrtCudaRuntime()
        self._bundle = bundle
        self._session: Any | None = None
        self._selected_providers: tuple[str, ...] = ()
        self._latencies_ms: list[float] = []

    @classmethod
    def unconfigured(cls, *, runtime: CudaRuntime | None = None) -> "OnnxCudaObservationProvider":
        return cls(runtime=runtime)

    @property
    def session_loaded(self) -> bool:
        return self._session is not None

    def probe(self) -> dict[str, object]:
        providers = self._runtime.available_providers()
        version_reader = getattr(self._runtime, "runtime_version", None)
        runtime_version = version_reader() if callable(version_reader) else None
        available = "CUDAExecutionProvider" in providers
        compatible = self._bundle is not None and self.provider_id in self._bundle.provider_compatibility
        limitations = self._bundle.limitations if self._bundle else ("explicit model bundle required",)
        return {
            "provider_key": self.provider_id, "provider_version": PROVIDER_VERSION,
            "runtime_available": bool(providers), "runtime_version": runtime_version,
            "cuda_available": available,
            "available_execution_providers": list(providers), "device_type": "GPU" if available else "unavailable",
            "accelerator": "NVIDIA CUDA", "continuous_analysis": False, "replay_inference": True,
            "tracking": False, "visit_proposal_authority": False, "rolling_buffer": False,
            "high_resolution_burst": False, "shadow_mode": True, "session_loaded": self.session_loaded,
            "model_bundle_configured": self._bundle is not None,
            "model_bundle_compatible": compatible,
            "limitations": list(limitations),
        }

    async def health(self, *, stream_id: str | None = None) -> ObservationProviderHealth:
        probe = self.probe()
        healthy = bool(probe["cuda_available"] and probe["model_bundle_compatible"])
        if healthy:
            message = "CUDA replay provider and model bundle are available."
        elif not probe["cuda_available"]:
            message = "CUDAExecutionProvider is unavailable."
        else:
            message = "A compatible model bundle is required."
        return ObservationProviderHealth("idle" if healthy else "degraded", healthy, message)

    async def describe(self, *, stream_id: str | None = None) -> ObservationProviderDescriptor:
        return ObservationProviderDescriptor(self.provider_id, self.display_name, self.capabilities,
                                             await self.health(stream_id=stream_id))

    def load(self) -> None:
        if self._session is not None:
            raise ReplayValidationError("provider_already_loaded")
        if self._bundle is None:
            raise ReplayValidationError("provider_configuration_required")
        providers = self._runtime.available_providers()
        if "CUDAExecutionProvider" not in providers:
            raise ReplayValidationError("onnx_cuda_unavailable")
        try:
            self._session = self._runtime.create_session(
                self._bundle.model_path,
                input_name=self._bundle.input_name,
                output_names=self._bundle.output_names,
            )
            selected = tuple(self._session.get_providers())
        except ReplayValidationError:
            self.close()
            raise
        except Exception as error:
            self.close()
            raise ReplayValidationError("onnx_cuda_session_load_failed") from error
        if selected != ("CUDAExecutionProvider",):
            self.close()
            raise ReplayValidationError("onnx_cuda_no_fallback")
        self._selected_providers = selected

    def close(self) -> None:
        session, self._session = self._session, None
        self._selected_providers = ()
        if session is not None and hasattr(session, "close"):
            session.close()

    def report_metadata(self) -> dict[str, object]:
        bundle = self._bundle
        return {
            **self.probe(), "selected_execution_providers": list(self._selected_providers),
            "model": None if bundle is None else {"key": bundle.model_key, "version": bundle.model_version,
                "fingerprint": bundle.model_fingerprint, "bundle_fingerprint": bundle.fingerprint,
                "format": bundle.model_format, "license": bundle.license_name,
                "redistribution": bundle.redistribution, "taxonomy": bundle.taxonomy,
                "broad_classes": list(bundle.broad_classes),
                "animal_classes": list(bundle.animal_classes),
                "provenance": bundle.provenance, "decoder": bundle.decoder_key,
                "preprocessing_version": PREPROCESS_VERSION,
                "postprocessing_version": POSTPROCESS_VERSION},
            "limitations": list(bundle.limitations if bundle else ("provider configuration required",)),
        }

    def execution_facts(self) -> dict[str, object]:
        values = sorted(self._latencies_ms)
        return {"inference_count": len(values), "latency_ms_median": _percentile(values, 0.5),
                "latency_ms_p95": _percentile(values, 0.95), "selected_execution_providers": list(self._selected_providers)}

    async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
        if self._session is None or self._bundle is None:
            raise ReplayValidationError("provider_not_loaded")
        results: list[ObservationResult] = []
        observation_count = 0
        for frame in frames:
            tensor, transform = _preprocess(frame, self._bundle)
            started = perf_counter()
            try:
                outputs = self._session.run(list(self._bundle.output_names), {self._bundle.input_name: tensor})
            except Exception as error:
                raise ReplayValidationError("onnx_cuda_inference_failed") from error
            self._latencies_ms.append((perf_counter() - started) * 1000)
            detections = _decode(outputs, frame, self._bundle, transform)
            observation_count += len(detections)
            if observation_count > MAX_REPLAY_OBSERVATIONS:
                raise ReplayValidationError("detector_output_limit")
            results.append(ObservationResult(self.provider_id, "replay", frame.stream_id,
                _captured_at(frame), frame_packets=(frame,), detection_observations=detections))
        return tuple(results)


def _preprocess(frame: FramePacket, bundle: OnnxModelBundle) -> tuple[Any, _Transform]:
    if frame.source_path is None:
        raise ReplayValidationError("replay_frame_path_unavailable")
    try:
        image_module = import_module("PIL.Image")
        numpy = import_module("numpy")
        with image_module.open(frame.source_path) as source:
            source_format = source.format
            source.load(); image = source.convert("RGB")
            source_width, source_height = image.size
            if source_format not in {"JPEG", "PNG"}:
                raise ReplayValidationError("unsupported_frame_content_type")
            if (frame.width is not None and frame.width != source_width) or (
                frame.height is not None and frame.height != source_height
            ):
                raise ReplayValidationError("frame_dimensions_mismatch")
            if source_width * source_height > MAX_INPUT_PIXELS:
                raise ReplayValidationError("frame_dimensions_limit")
            if bundle.resize_mode == "letterbox":
                scale = min(bundle.input_width / source_width, bundle.input_height / source_height)
                width, height = max(1, round(source_width * scale)), max(1, round(source_height * scale))
                resized = image.resize((width, height), image_module.Resampling.BILINEAR)
                canvas = image_module.new("RGB", (bundle.input_width, bundle.input_height), bundle.letterbox_fill)
                pad_x, pad_y = (bundle.input_width - width) // 2, (bundle.input_height - height) // 2
                canvas.paste(resized, (pad_x, pad_y)); image = canvas
                transform = _Transform(scale, scale, pad_x, pad_y, source_width, source_height)
            else:
                image = image.resize((bundle.input_width, bundle.input_height), image_module.Resampling.BILINEAR)
                transform = _Transform(bundle.input_width / source_width, bundle.input_height / source_height, 0, 0, source_width, source_height)
            array = numpy.asarray(image, dtype="float32")
        if bundle.color_format == "BGR": array = array[..., ::-1]
        mean, std = numpy.asarray(bundle.normalization_mean, dtype="float32"), numpy.asarray(bundle.normalization_std, dtype="float32")
        array = (array * bundle.input_scale - mean) / std
        return numpy.transpose(array, (2, 0, 1))[None, ...], transform
    except ReplayValidationError:
        raise
    except Exception as error:
        raise ReplayValidationError("onnx_preprocess_failed") from error


def _decode(outputs: Any, frame: FramePacket, bundle: OnnxModelBundle, transform: _Transform) -> tuple[DetectionObservation, ...]:
    try:
        if not isinstance(outputs, (list, tuple)) or not outputs:
            raise ReplayValidationError("malformed_detector_output")
        rows = outputs[0]
        if getattr(rows, "ndim", 0) == 3: rows = rows[0]
        if getattr(rows, "ndim", 0) != 2 or len(rows) > MAX_DECODE_ROWS:
            raise ReplayValidationError("malformed_detector_output")
        candidates: list[DetectionObservation] = []
        for row in rows:
            if len(row) < 6: raise ReplayValidationError("malformed_detector_output")
            x1, y1, x2, y2, score, class_id = (float(value) for value in row[:6])
            if not all(math.isfinite(value) for value in (x1, y1, x2, y2, score, class_id)):
                raise ReplayValidationError("malformed_detector_output")
            if not 0 <= score <= 1:
                raise ReplayValidationError("malformed_detector_output")
            if score < bundle.score_threshold: continue
            if not class_id.is_integer():
                raise ReplayValidationError("malformed_detector_output")
            class_index = int(class_id)
            if class_index < 0 or class_index >= len(bundle.broad_classes): raise ReplayValidationError("malformed_detector_output")
            box = _source_box((x1, y1, x2, y2), transform)
            score = round(score, 6); box = tuple(round(value, 6) for value in box)
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ReplayValidationError("malformed_detector_output")
            key = semantic_fingerprint((frame.frame_id, bundle.model_key, bundle.model_version, class_index, score, box))
            candidates.append(DetectionObservation(
                detector_id=f"{bundle.model_key}:{bundle.model_version}", label=bundle.broad_classes[class_index],
                confidence=score, captured_at=_captured_at(frame), observation_id=key, frame_id=frame.frame_id,
                provider_id="onnx-cuda", model_key=bundle.model_key, generation_id=bundle.fingerprint,
                bounding_box=box, class_source_label=str(class_index),
                is_animal=bundle.broad_classes[class_index] in bundle.animal_classes,
            ))
        candidates.sort(key=lambda item: (-float(item.confidence or 0), item.label, item.bounding_box or (), item.observation_id or ""))
        return tuple(candidates[:bundle.max_observations_per_frame])
    except ReplayValidationError:
        raise
    except Exception as error:
        raise ReplayValidationError("malformed_detector_output") from error


def _source_box(box: tuple[float, float, float, float], transform: _Transform) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = box
    values = ((x1 - transform.pad_x) / transform.scale_x / transform.source_width,
              (y1 - transform.pad_y) / transform.scale_y / transform.source_height,
              (x2 - transform.pad_x) / transform.scale_x / transform.source_width,
              (y2 - transform.pad_y) / transform.scale_y / transform.source_height)
    return tuple(min(1.0, max(0.0, value)) for value in values)


def _captured_at(frame: FramePacket) -> datetime:
    return frame.captured_at or datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=frame.source_offset_ms or 0)


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024): digest.update(block)
    return digest.hexdigest()


def _text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value or len(value) > 512: raise ReplayValidationError("invalid_model_bundle")
    return value


def _positive_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > 8192: raise ReplayValidationError("invalid_model_bundle")
    return value


def _choice(data: dict[str, Any], key: str, choices: set[str]) -> str:
    value = _text(data, key)
    if value not in choices: raise ReplayValidationError("invalid_model_bundle")
    return value


def _triple(data: dict[str, Any], key: str, *, nonzero: bool = False) -> tuple[float, float, float]:
    value = data.get(key)
    if not isinstance(value, list) or len(value) != 3: raise ReplayValidationError("invalid_model_bundle")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ReplayValidationError("invalid_model_bundle")
    if nonzero and any(item <= 0 for item in result):
        raise ReplayValidationError("invalid_model_bundle")
    return result


def _byte_triple(data: dict[str, Any], key: str) -> tuple[int, int, int]:
    value = data.get(key)
    if (
        not isinstance(value, list) or len(value) != 3
        or not all(isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 255 for item in value)
    ):
        raise ReplayValidationError("invalid_model_bundle")
    return tuple(value)


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key)
    if (
        not isinstance(value, list) or not 1 <= len(value) <= 512
        or not all(isinstance(item, str) and 0 < len(item) <= 512 for item in value)
    ):
        raise ReplayValidationError("invalid_model_bundle")
    return value


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values: return None
    return round(values[min(len(values) - 1, int((len(values) - 1) * fraction))], 3)
