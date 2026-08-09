from __future__ import annotations

import gc
import hashlib
from io import BytesIO
import json
import os
import sys
import tempfile
from pathlib import Path
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from mockingbird.observation.contracts import FramePacket
from mockingbird.observation import onnx_provider
from mockingbird.observation.onnx_provider import (
    BUNDLE_SCHEMA_VERSION,
    OnnxCudaObservationProvider,
    OnnxModelBundle,
)
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedDetection,
    ReplayFrame,
    ReplayInput,
    ReplayRunner,
    ReplayValidationError,
)
from mockingbird.observation.replay_cli import run as replay_run


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeSession:
    def __init__(self, outputs: object, providers: tuple[str, ...] = ("CUDAExecutionProvider",)) -> None:
        self.outputs = outputs
        self.providers = providers
        self.calls: list[tuple[list[str], dict[str, object]]] = []
        self.closed = False

    def get_providers(self) -> list[str]:
        return list(self.providers)

    def run(self, outputs: list[str], inputs: dict[str, object]) -> object:
        self.calls.append((outputs, inputs))
        if isinstance(self.outputs, Exception):
            raise self.outputs
        return self.outputs

    def execution_assignment(self) -> dict[str, object]:
        return {
            "classification": "cuda_only_verified",
            "cuda_executed_nodes": max(1, len(self.calls)),
            "cpu_executed_nodes": 0,
            "unknown_executed_nodes": 0,
        }

    def close(self) -> None:
        self.closed = True


class FakeRuntime:
    def __init__(self, session: FakeSession, providers: tuple[str, ...] = ("CUDAExecutionProvider",)) -> None:
        self.session = session
        self.providers = providers
        self.session_creations = 0

    def available_providers(self) -> tuple[str, ...]:
        return self.providers

    def create_session(self, model_path: Path, *, input_name: str, output_names: tuple[str, ...]) -> FakeSession:
        self.session_creations += 1
        return self.session


# --- Fakes for `OptionalOrtCudaRuntime` itself (the real `onnxruntime`
# import boundary) -- everything above fakes the higher-level `CudaRuntime`
# Protocol and never exercises `OptionalOrtCudaRuntime.create_session`'s own
# DLL-search-path/tempfile-profiling/error-handling internals at all. These
# stand in for the `onnxruntime` *module* so those internals can be driven
# directly, without a real ONNX Runtime/CUDA install. -----------------------


class _FakeOrtSessionOptions:
    def __init__(self) -> None:
        self.intra_op_num_threads: int | None = None
        self.inter_op_num_threads: int | None = None
        self.enable_profiling = False
        self.profile_file_prefix: str | None = None
        self.config_entries: dict[str, str] = {}

    def add_session_config_entry(self, key: str, value: str) -> None:
        self.config_entries[key] = value


class _FakeOrtInferenceSession:
    def __init__(self, providers: tuple[str, ...]) -> None:
        self._providers = providers

    def get_providers(self) -> list[str]:
        return list(self._providers)

    def end_profiling(self) -> str:
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        try:
            handle.write(json.dumps([]))
        finally:
            handle.close()
        return handle.name


class _FakeOnnxRuntimeModule:
    """A minimal stand-in for the real `onnxruntime` module -- just enough
    surface for `OptionalOrtCudaRuntime` to drive end-to-end (`available_
    providers`/`create_session`) without a real ONNX Runtime/CUDA install."""

    def __init__(
        self,
        *,
        available_providers: tuple[str, ...] = ("CUDAExecutionProvider",),
        session_providers: tuple[str, ...] | None = None,
        session_error: Exception | None = None,
        on_session_create: "object | None" = None,
    ) -> None:
        self._available_providers = available_providers
        self._session_providers = session_providers if session_providers is not None else available_providers
        self._session_error = session_error
        self._on_session_create = on_session_create
        self.created_sessions: list[_FakeOrtInferenceSession] = []

    def get_available_providers(self) -> list[str]:
        return list(self._available_providers)

    def SessionOptions(self) -> _FakeOrtSessionOptions:
        return _FakeOrtSessionOptions()

    def InferenceSession(
        self, model_path: object, sess_options: object = None, providers: object = None,
    ) -> _FakeOrtInferenceSession:
        if self._on_session_create is not None:
            self._on_session_create()
        if self._session_error is not None:
            raise self._session_error
        session = _FakeOrtInferenceSession(self._session_providers)
        self.created_sessions.append(session)
        return session


class _CleanupRaisingTemporaryDirectory:
    """Stands in for `tempfile.TemporaryDirectory`, but `.cleanup()` always
    raises -- reproducing a Windows `WinError 32` (the ONNX Runtime
    profiling JSON is still open) so tests can prove MockingBird's own
    handling never lets a cleanup failure mask a real error, without
    depending on platform-specific file-locking behavior to reproduce it."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.name = "fake-profile-root"
        self.cleanup_attempted = False

    def cleanup(self) -> None:
        self.cleanup_attempted = True
        raise OSError(32, "The process cannot access the file because it is being used by another process")


def _bundle(tmp_path: Path, **updates: object) -> tuple[Path, OnnxModelBundle]:
    model = tmp_path / "detector.onnx"
    model.write_bytes(b"fake-onnx-model")
    payload: dict[str, object] = {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "model_key": "fixture-detector",
        "model_version": "1",
        "model_file": model.name,
        "model_fingerprint": hashlib.sha256(model.read_bytes()).hexdigest(),
        "model_format": "ONNX",
        "license": "fixture-only",
        "redistribution": "not-redistributable",
        "input_name": "images",
        "input_width": 4,
        "input_height": 4,
        "input_dtype": "float32",
        "input_scale": 0.00392156862745098,
        "channel_order": "NCHW",
        "color_format": "RGB",
        "letterbox_fill": [114, 114, 114],
        "normalization_mean": [0.0, 0.0, 0.0],
        "normalization_std": [1.0, 1.0, 1.0],
        "resize_mode": "letterbox",
        "output_names": ["detections"],
        "decoder_key": "xyxy-score-class-v1",
        "broad_classes": ["bird", "mammal"],
        "animal_classes": ["bird", "mammal"],
        "taxonomy": "fixture broad classes",
        "provenance": "generated test contract",
        "provider_compatibility": ["onnx-cuda"],
        "limitations": ["test fixture"],
        "score_threshold": 0.25,
        "max_observations_per_frame": 2,
    }
    payload.update(updates)
    manifest = tmp_path / "bundle.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return manifest, OnnxModelBundle.load(manifest)


def _frame(tmp_path: Path) -> FramePacket:
    image = tmp_path / "frame.png"
    Image.new("RGB", (4, 2), color=(255, 128, 0)).save(image)
    return FramePacket("stream", "replay:0", None, "frame-0", 0, 4, 2, str(image))


def test_optional_runtime_reports_dependency_absence_without_import(monkeypatch: pytest.MonkeyPatch) -> None:
    from mockingbird.observation import onnx_provider

    monkeypatch.setattr(onnx_provider.util, "find_spec", lambda _name: None)
    runtime = onnx_provider.OptionalOrtCudaRuntime()
    assert runtime.available_providers() == ()
    assert runtime.runtime_version() is None


def test_probe_is_side_effect_free_and_reports_missing_cuda_honestly() -> None:
    runtime = FakeRuntime(FakeSession([]), providers=("CPUExecutionProvider",))
    provider = OnnxCudaObservationProvider.unconfigured(runtime=runtime)
    probe = provider.probe()
    assert probe["runtime_available"] is True
    assert probe["cuda_available"] is False
    assert probe["model_bundle_configured"] is False
    assert probe["visit_proposal_authority"] is False
    assert runtime.session_creations == 0
    assert provider.session_loaded is False


@pytest.mark.anyio
async def test_unconfigured_provider_health_is_degraded_even_when_cuda_exists() -> None:
    provider = OnnxCudaObservationProvider.unconfigured(runtime=FakeRuntime(FakeSession([])))
    health = await provider.health()
    assert health.healthy is False
    assert health.state == "degraded"
    assert "model bundle" in health.message


def test_model_bundle_validation_is_versioned_hashed_and_decoder_specific(tmp_path: Path) -> None:
    manifest, bundle = _bundle(tmp_path)
    assert bundle.model_format == "ONNX"
    assert bundle.provenance == "generated test contract"
    assert len(bundle.fingerprint) == 64

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    for update, error in (
        ({"schema_version": 999}, "unsupported_model_bundle_version"),
        ({"model_fingerprint": "0" * 64}, "model_fingerprint_mismatch"),
        ({"decoder_key": "unknown"}, "unsupported_decoder"),
        ({"model_format": "TensorRT"}, "unsupported_model_format"),
        ({"animal_classes": ["fish"]}, "invalid_model_bundle"),
    ):
        manifest.write_text(json.dumps({**payload, **update}), encoding="utf-8")
        with pytest.raises(ReplayValidationError, match=error):
            OnnxModelBundle.load(manifest)


def test_load_requires_cuda_and_accepts_registered_cpu_when_cuda_is_first(tmp_path: Path) -> None:
    _, bundle = _bundle(tmp_path)
    cpu_runtime = FakeRuntime(FakeSession([], ("CPUExecutionProvider",)), ("CPUExecutionProvider",))
    with pytest.raises(ReplayValidationError, match="onnx_cuda_unavailable"):
        OnnxCudaObservationProvider(runtime=cpu_runtime, bundle=bundle).load()
    assert cpu_runtime.session_creations == 0

    mixed = FakeSession([], ("CUDAExecutionProvider", "CPUExecutionProvider"))
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(mixed), bundle=bundle)
    provider.load()
    assert provider.execution_facts()["selected_execution_providers"] == [
        "CUDAExecutionProvider", "CPUExecutionProvider"
    ]
    provider.close()
    assert mixed.closed is True


@pytest.mark.anyio
async def test_deterministic_letterbox_normalization_order_bounds_and_close(tmp_path: Path) -> None:
    _, bundle = _bundle(tmp_path)
    output = np.asarray([[
        [0.0, 0.0, 4.0, 4.0, 0.10, 0],
        [1.0, 1.0, 3.0, 3.0, 0.80, 0],
        [0.0, 1.0, 2.0, 3.0, 0.90, 1],
        [2.0, 1.0, 4.0, 3.0, 0.70, 0],
    ]], dtype=np.float32)
    session = FakeSession([output])
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(session), bundle=bundle)
    provider.load()
    first = await provider.replay_frames((_frame(tmp_path),))
    second = await provider.replay_frames((_frame(tmp_path),))
    detections = first[0].detection_observations
    assert len(detections) == bundle.max_observations_per_frame
    assert [item.label for item in detections] == ["mammal", "bird"]
    assert detections[0].bounding_box == (0.0, 0.0, 0.5, 1.0)
    assert all(item.is_animal is True for item in detections)
    assert detections[1].bounding_box == (0.25, 0.0, 0.75, 1.0)
    assert [item.observation_id for item in detections] == [item.observation_id for item in second[0].detection_observations]
    tensor = session.calls[0][1]["images"]
    assert getattr(tensor, "shape") == (1, 3, 4, 4)
    assert str(getattr(tensor, "dtype")) == "float32"
    np.testing.assert_array_equal(session.calls[0][1]["images"], session.calls[1][1]["images"])
    assert first[0].track_updates == ()
    assert first[0].visit_proposals == ()
    assert first[0].creates_truth is False
    provider.close()
    assert session.closed is True
    assert provider.session_loaded is False


@pytest.mark.anyio
async def test_detection_observation_retains_source_frame_lineage(tmp_path: Path) -> None:
    """(5) A `DetectionObservation` built from a `FramePacket` that carries
    reviewed source-lineage provenance (Stage 6.14) retains that provenance
    explicitly, distinct from its own `frame_id` -- and stays `None` for an
    ordinary frame with no such provenance, exactly like every other
    detector-output fact this test file already covers."""

    from dataclasses import replace

    _, bundle = _bundle(tmp_path)
    output = np.asarray([[[0.0, 0.0, 4.0, 4.0, 0.90, 0]]], dtype=np.float32)
    session = FakeSession([output])
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(session), bundle=bundle)
    provider.load()

    plain = _frame(tmp_path)
    lineage = replace(plain, source_capture_frame_id="reviewed-frame-1", source_content_hash="hash-1")

    plain_result = (await provider.replay_frames((plain,)))[0]
    lineage_result = (await provider.replay_frames((lineage,)))[0]
    assert plain_result.detection_observations[0].source_capture_frame_id is None
    detection = lineage_result.detection_observations[0]
    assert detection.source_capture_frame_id == "reviewed-frame-1"
    assert detection.frame_id == plain.frame_id  # the replay-local identity is unaffected
    provider.close()


@pytest.mark.anyio
async def test_live_payload_is_decoded_and_privacy_regions_are_masked(tmp_path: Path) -> None:
    _, bundle = _bundle(tmp_path)
    image = BytesIO()
    Image.new("RGB", (4, 2), color="white").save(image, format="JPEG")
    session = FakeSession([np.asarray([], dtype=np.float32).reshape((1, 0, 6))])
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(session), bundle=bundle)
    provider.load()
    packet = FramePacket(
        "stream", "shadow:frame", datetime(2026, 8, 4, tzinfo=UTC), "live-frame", 0, 4, 2,
        analysis_excluded_regions=((0.0, 0.0, 0.5, 1.0),), payload=image.getvalue(),
    )
    await provider.infer_frame(packet)
    tensor = session.calls[0][1]["images"]
    assert float(tensor[0, :, 1, 0].max()) == 0.0
    assert float(tensor[0, :, 1, 3].min()) > 0.5


@pytest.mark.anyio
async def test_detection_only_replay_scores_detection_truth_not_visit_truth(tmp_path: Path) -> None:
    manifest_path, bundle = _bundle(tmp_path, max_observations_per_frame=5)
    del manifest_path
    image = tmp_path / "frame.png"
    Image.new("RGB", (4, 2), color="white").save(image)
    content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    replay = ReplayInput("input", "stream", 4, 2, 1.0, (ReplayFrame(0, 0, content_hash, str(image)),))
    truth = (ExpectedDetection("truth-1", 0, "bird", (0.25, 0.0, 0.75, 1.0)),)
    manifest = BenchmarkManifest(1, "benchmark", replay.fingerprint, (), (), truth)
    output = np.asarray([[[1.0, 1.0, 3.0, 3.0, 0.8, 0]]], dtype=np.float32)
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(FakeSession([output])), bundle=bundle)
    provider.load()
    first = await ReplayRunner({provider.provider_id: provider}).run(replay, manifest, provider_key=provider.provider_id)
    second = await ReplayRunner({provider.provider_id: provider}).run(replay, manifest, provider_key=provider.provider_id)
    assert first.proposals == ()
    assert first.matches == ()
    assert first.metrics["proposal_precision"]["state"] == "not_evaluated"
    assert first.metrics["appearance_recall"]["state"] == "not_evaluated"
    assert first.metrics["frame_level_animal_recall"] == {"state": "evaluated", "value": 1.0}
    assert first.metrics["box_precision"] == {"state": "evaluated", "value": 1.0}
    assert first.metrics["box_recall"] == {"state": "evaluated", "value": 1.0}
    assert first.metrics["broad_class_agreement"] == {"state": "evaluated", "value": 1.0}
    assert first.semantic_fingerprint == second.semantic_fingerprint


@pytest.mark.anyio
async def test_missing_detection_truth_is_insufficient_and_failures_are_sanitized(tmp_path: Path) -> None:
    _, bundle = _bundle(tmp_path)
    frame = _frame(tmp_path)
    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(FakeSession(RuntimeError("secret details"))), bundle=bundle)
    provider.load()
    with pytest.raises(ReplayValidationError, match="onnx_cuda_inference_failed") as caught:
        await provider.replay_frames((frame,))
    assert "secret details" not in str(caught.value)

    good = OnnxCudaObservationProvider(
        runtime=FakeRuntime(FakeSession([np.asarray([[[1.0, 1.0, 3.0, 3.0, 0.8, 0]]], dtype=np.float32)])),
        bundle=bundle,
    )
    good.load()
    image = Path(frame.source_path or "")
    content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    replay = ReplayInput("without-truth", "stream", 4, 2, 1.0, (ReplayFrame(0, 0, content_hash, str(image)),))
    manifest = BenchmarkManifest(1, "without-truth", replay.fingerprint, (), ())
    report = await ReplayRunner({good.provider_id: good}).run(replay, manifest, provider_key=good.provider_id)
    assert report.metrics["frame_level_animal_recall"]["state"] == "insufficient_truth"
    assert report.metrics["detector_observation_count"] == {"state": "evaluated", "value": 1}

    malformed = OnnxCudaObservationProvider(
        runtime=FakeRuntime(FakeSession([np.asarray([[[0.0, 0.0]]], dtype=np.float32)])), bundle=bundle,
    )
    malformed.load()
    with pytest.raises(ReplayValidationError, match="malformed_detector_output"):
        await malformed.replay_frames((frame,))


def test_load_failure_is_sanitized_and_loaded_session_cannot_be_reused(tmp_path: Path) -> None:
    _, bundle = _bundle(tmp_path)

    class FailingRuntime(FakeRuntime):
        def create_session(self, model_path: Path, *, input_name: str, output_names: tuple[str, ...]) -> FakeSession:
            raise RuntimeError("private driver detail")

    with pytest.raises(ReplayValidationError, match="onnx_cuda_session_load_failed") as caught:
        OnnxCudaObservationProvider(runtime=FailingRuntime(FakeSession([])), bundle=bundle).load()
    assert "private driver detail" not in str(caught.value)

    provider = OnnxCudaObservationProvider(runtime=FakeRuntime(FakeSession([])), bundle=bundle)
    provider.load()
    with pytest.raises(ReplayValidationError, match="provider_already_loaded"):
        provider.load()


def test_provider_source_has_no_product_repository_or_truth_imports() -> None:
    source = Path("src/mockingbird/observation/onnx_provider.py").read_text(encoding="utf-8")
    forbidden = ("mockingbird.db", "mockingbird.repositories", "ReviewLabel", "MotionEvidence", "monitoring_policy")
    assert not any(token in source for token in forbidden)


def _replay_files(tmp_path: Path) -> tuple[Path, Path]:
    frames = tmp_path / "frames"
    frames.mkdir()
    image = frames / "frame.png"
    Image.new("RGB", (4, 2), color="white").save(image)
    content_hash = hashlib.sha256(image.read_bytes()).hexdigest()
    replay = ReplayInput("cli-input", "cli-stream", 4, 2, 1.0, (ReplayFrame(0, 0, content_hash),))
    payload = {
        "version": 1,
        "benchmark_id": "cli-benchmark",
        "input_fingerprint": replay.fingerprint,
        "input_id": replay.input_id,
        "stream_id": replay.stream_id,
        "width": replay.width,
        "height": replay.height,
        "nominal_fps": replay.nominal_fps,
        "frames": [{"path": image.name, "source_offset_ms": 0, "content_hash": content_hash}],
        "appearances": [],
        "visits": [],
        "detections": [{
            "annotation_id": "bird-1",
            "frame_index": 0,
            "broad_class": "bird",
            "bounding_box": [0.25, 0.0, 0.75, 1.0],
        }],
        "thresholds": {},
    }
    manifest = tmp_path / "benchmark.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    return frames, manifest


def test_cli_requires_config_and_runs_fake_cuda_twice_deterministically(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_path, _ = _bundle(tmp_path)
    frames, manifest = _replay_files(tmp_path)
    assert replay_run([
        "--provider", "onnx-cuda", "--frames", str(frames), "--manifest", str(manifest),
        "--output", str(tmp_path / "missing-config"),
    ]) == 9

    sessions: list[FakeSession] = []
    output = np.asarray([[[1.0, 1.0, 3.0, 3.0, 0.8, 0]]], dtype=np.float32)

    def runtime_factory() -> FakeRuntime:
        session = FakeSession([output])
        sessions.append(session)
        return FakeRuntime(session)

    monkeypatch.setattr("mockingbird.observation.onnx_provider.OptionalOrtCudaRuntime", runtime_factory)
    payloads = []
    for name in ("first-report", "second-report"):
        destination = tmp_path / name
        assert replay_run([
            "--provider", "onnx-cuda", "--frames", str(frames), "--manifest", str(manifest),
            "--provider-config", str(bundle_path), "--output", str(destination),
        ]) == 0
        payloads.append(json.loads((destination / "replay-report.json").read_text(encoding="utf-8")))
    assert payloads[0]["semantic_fingerprint"] == payloads[1]["semantic_fingerprint"]
    assert payloads[0]["execution"]["selected_execution_providers"] == ["CUDAExecutionProvider"]
    assert payloads[0]["provider"]["model"]["key"] == "fixture-detector"
    assert "available_execution_providers" not in payloads[0]["semantic"]["provider"]
    assert payloads[0]["metrics"]["detector_observation_count"]["value"] == 1
    assert payloads[0]["metrics"]["proposal_count"]["state"] == "not_evaluated"
    assert payloads[0]["proposals"] == []
    assert payloads[0]["creates_truth"] is False
    assert payloads[0]["execution"]["inference_count"] == 1
    assert all(session.closed for session in sessions)
    assert str(bundle_path.parent.resolve()) not in json.dumps(payloads[0]["semantic"])


# --- Windows CUDA/cuDNN DLL search-path wiring ------------------------------


def test_windows_dll_search_path_finds_every_real_nested_dll_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real `nvidia-cuda-runtime` Windows wheel nests its DLL four
    directories under `nvidia/` (`nvidia/cu13/bin/x86_64/cudart64_13.dll`),
    not the `nvidia/<component>/bin/` shape its Linux `.so` counterpart
    uses -- confirmed against the real win_amd64 wheel from PyPI. A
    same-depth-guess implementation missed this; this fixture reproduces
    that exact real layout (plus a *differently*-nested second package, to
    prove the search does not assume one fixed depth) so the recursive
    `.dll` discovery is proven, not assumed."""

    site_packages = tmp_path / "site-packages"
    cudart_dir = site_packages / "nvidia" / "cu13" / "bin" / "x86_64"
    cudart_dir.mkdir(parents=True)
    (cudart_dir / "cudart64_13.dll").write_bytes(b"fixture-dll")
    # A differently-shaped package (shallower nesting) in the same tree.
    cublas_dir = site_packages / "nvidia" / "cublas" / "bin"
    cublas_dir.mkdir(parents=True)
    (cublas_dir / "cublas64_13.dll").write_bytes(b"fixture-dll")
    # A non-DLL file elsewhere under `nvidia/` must never be added.
    (site_packages / "nvidia" / "cu13" / "include").mkdir(parents=True)
    (site_packages / "nvidia" / "cu13" / "include" / "cuda.h").write_text("", encoding="utf-8")

    added_directories: list[str] = []
    monkeypatch.setattr(onnx_provider, "_windows_dll_search_path_prepared", False)
    monkeypatch.setattr(onnx_provider.os, "name", "nt")
    monkeypatch.setattr(onnx_provider.os, "add_dll_directory", added_directories.append, raising=False)
    # This function also updates the real `PATH` env var (see the PATH
    # test below) -- `setenv` to its own current value here so monkeypatch
    # restores it afterwards regardless.
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)

    assert set(added_directories) == {str(cudart_dir), str(cublas_dir)}


def test_windows_dll_search_path_is_a_noop_off_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cudart64_13.dll").write_bytes(b"fixture-dll")

    calls: list[str] = []
    monkeypatch.setattr(onnx_provider, "_windows_dll_search_path_prepared", False)
    monkeypatch.setattr(onnx_provider.os, "name", "posix")
    monkeypatch.setattr(onnx_provider.os, "add_dll_directory", calls.append, raising=False)

    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)

    assert calls == []


def test_windows_dll_search_path_runs_at_most_once_per_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cudart64_13.dll").write_bytes(b"fixture-dll")

    added_directories: list[str] = []
    monkeypatch.setattr(onnx_provider, "_windows_dll_search_path_prepared", False)
    monkeypatch.setattr(onnx_provider.os, "name", "nt")
    monkeypatch.setattr(onnx_provider.os, "add_dll_directory", added_directories.append, raising=False)
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)
    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)

    assert len(added_directories) == 1


# --- DLL-directory handle lifetime, ORT session-creation cleanup safety,
# and no-silent-CPU-fallback (Windows CUDA DLL loading fix) ----------------


class _FakeDllDirectoryHandle:
    """Stands in for the object `os.add_dll_directory()` returns on real
    Windows: closing it removes the directory from the process DLL search
    path again, same as the real `os._AddedDllDirectory`."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeWindowsOs:
    """A narrow stand-in for the `os` module, swapped into `onnx_provider`'s
    own `os` name specifically -- never the real process-global `os` module
    -- so a test can simulate `os.name == "nt"` around a real `pathlib.Path
    (__file__)` call.

    Mutating the *real* `os.name` instead (as the pre-existing tests above
    do, safely, because they always pass an explicit `site_packages=` and so
    never reach a `Path(__file__)` call) breaks `pathlib.Path` construction
    outright on this non-Windows interpreter: `WindowsPath.__new__`'s
    refusal to instantiate is decided once, when `pathlib` is first
    imported (using the real `os.name` at that time), not re-checked on
    every call -- so a later `os.name` mutation just makes the *generic*
    `Path(...)` factory dispatch to a `WindowsPath` class that then refuses
    to construct at all, crashing the code under test (and, if that
    propagates into a failing assertion while the mutation is still active,
    pytest's own failure-reporting machinery too). Swapping the whole `os`
    reference used inside `onnx_provider` sidesteps this entirely: `pathlib`
    keeps using the real, unmutated global `os` module internally."""

    name = "nt"
    pathsep = ";"  # real Windows os.pathsep -- independent of the real host's

    def __init__(self) -> None:
        self.added_directories: list[str] = []
        self.environ: dict[str, str] = {}

    def add_dll_directory(self, path: str) -> _FakeDllDirectoryHandle:
        self.added_directories.append(path)
        return _FakeDllDirectoryHandle()


def _reset_windows_dll_search_path_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(onnx_provider, "_windows_dll_search_path_prepared", False)
    monkeypatch.setattr(onnx_provider, "_retained_windows_dll_directory_handles", [])


def test_windows_dll_search_path_default_site_packages_finds_real_layout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for the actual bug behind the reported "cublasLt64_13
    .dll missing" failure: the *default* `site_packages` auto-detection --
    the computation every real call site uses, since none of them pass an
    explicit override -- must resolve to the real `site-packages` root given
    this module's real installed location two directories below it
    (`<site-packages>/mockingbird/observation/onnx_provider.py`), not one
    directory short of it. Every *other* test in this file passes
    `site_packages=` explicitly and so never exercises this computation --
    that is exactly how the previous off-by-one (`parent.parent` instead of
    `parent.parent.parent`) shipped undetected: it silently found zero
    `nvidia/` directories and registered nothing, on every real packaged
    install."""

    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin" / "x86_64"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cublasLt64_13.dll").write_bytes(b"fixture-dll")

    fake_os = _FakeWindowsOs()
    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider, "os", fake_os)
    monkeypatch.setattr(
        onnx_provider, "__file__",
        str(site_packages / "mockingbird" / "observation" / "onnx_provider.py"),
    )

    onnx_provider._prepare_windows_onnxruntime_dll_search_path()  # no override -- the real call shape

    assert fake_os.added_directories == [str(dll_dir)]
    assert len(onnx_provider._retained_windows_dll_directory_handles) == 1


def test_windows_dll_search_path_also_updates_path_for_onnxruntimes_own_dependency_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test for a second real gap, found only by actually
    creating a CUDA session on a real Windows host with a real GPU:
    `add_dll_directory` alone was proven *insufficient* -- with every
    nvidia DLL directory already registered that way and its handle
    retained, onnxruntime's own provider-bridge dependency resolution for
    `onnxruntime_providers_cuda.dll`'s CUDA/cuDNN dependencies still
    reported `cublasLt64_13.dll` "missing" (Error 126), even though a
    direct `ctypes.WinDLL()` load of that exact DLL succeeded. Adding the
    same directories to `PATH` -- which is what onnxruntime's own loading
    actually consults, matching NVIDIA's own `cuda.pathfinder` package
    pairing the same two calls -- was what actually fixed it. The existing
    `PATH` value must be preserved, not clobbered."""

    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin" / "x86_64"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cublasLt64_13.dll").write_bytes(b"fixture-dll")

    fake_os = _FakeWindowsOs()
    fake_os.environ["PATH"] = "C:\\Windows\\System32"
    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider, "os", fake_os)

    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)

    path_entries = fake_os.environ["PATH"].split(fake_os.pathsep)
    assert str(dll_dir) in path_entries
    assert "C:\\Windows\\System32" in path_entries


def test_windows_dll_directory_handles_are_not_garbage_collected_away(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handle created and immediately discarded -- never assigned to any
    surviving variable -- is exactly the shape of the original bug: kept
    alive only in a short-lived local, it would be eligible for garbage
    collection the instant `_prepare_windows_onnxruntime_dll_search_path`
    returns, which is before `OptionalOrtCudaRuntime.create_session` ever
    loads `onnxruntime_providers_cuda.dll`. Forcing a real GC pass here is
    what would catch a regression back to discarding the return value."""

    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin" / "x86_64"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cublasLt64_13.dll").write_bytes(b"fixture-dll")

    created_handles: list[_FakeDllDirectoryHandle] = []

    def _fake_add_dll_directory(path: str) -> _FakeDllDirectoryHandle:
        handle = _FakeDllDirectoryHandle()
        created_handles.append(handle)
        return handle

    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider.os, "name", "nt")
    monkeypatch.setattr(onnx_provider.os, "add_dll_directory", _fake_add_dll_directory, raising=False)
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    onnx_provider._prepare_windows_onnxruntime_dll_search_path(site_packages=site_packages)

    assert len(created_handles) == 1
    gc.collect()  # a handle stashed only in a discarded local would die here

    assert created_handles[0].closed is False
    assert created_handles[0] in onnx_provider._retained_windows_dll_directory_handles


def test_windows_dll_directory_handles_stay_alive_through_ort_session_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through the real `OptionalOrtCudaRuntime.create_session`
    (not just the registration helper in isolation): the handles returned by
    `os.add_dll_directory` must still be retained and unclosed at the exact
    moment `onnxruntime.InferenceSession(...)` runs -- that is when
    onnxruntime actually loads `onnxruntime_providers_cuda.dll` and,
    transitively, `cublasLt64_13.dll` -- not merely before it, and must
    still be alive afterwards too (subsequent inference calls on the
    returned session need the same DLLs already resolved)."""

    site_packages = tmp_path / "site-packages"
    dll_dir = site_packages / "nvidia" / "cu13" / "bin" / "x86_64"
    dll_dir.mkdir(parents=True)
    (dll_dir / "cublasLt64_13.dll").write_bytes(b"fixture-dll")

    fake_os = _FakeWindowsOs()
    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider, "os", fake_os)
    # Exercise the real default `site_packages` auto-detection -- the same
    # code path production hits -- not the test-only override.
    monkeypatch.setattr(
        onnx_provider, "__file__",
        str(site_packages / "mockingbird" / "observation" / "onnx_provider.py"),
    )

    observed: dict[str, object] = {}

    def _on_session_create() -> None:
        gc.collect()
        handles = onnx_provider._retained_windows_dll_directory_handles
        observed["retained_count"] = len(handles)
        observed["any_closed"] = any(handle.closed for handle in handles)

    fake_ort = _FakeOnnxRuntimeModule(on_session_create=_on_session_create)
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)

    runtime = onnx_provider.OptionalOrtCudaRuntime()
    session = runtime.create_session(tmp_path / "model.onnx", input_name="images", output_names=("out",))

    assert fake_os.added_directories == [str(dll_dir)], "the real site_packages auto-detection must have found the fake nvidia DLL directory"
    assert observed["retained_count"] == 1
    assert observed["any_closed"] is False
    handles = list(onnx_provider._retained_windows_dll_directory_handles)
    assert handles and all(not handle.closed for handle in handles)
    session.close()
    assert all(not handle.closed for handle in handles), "closing the ORT session must not touch DLL search-path handles"


def test_cleanup_failure_never_masks_original_cuda_session_load_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces the reported secondary defect: a `TemporaryDirectory.
    cleanup()` failure (Windows `WinError 32`, the profiling JSON still open
    after a failed load) while handling a real CUDA session-load failure
    must never replace/mask that original error. The cleanup/exception
    -handling logic under test is not itself OS-gated, so this deliberately
    does not simulate `os.name == "nt"` -- see `_FakeWindowsOs` above for
    why mutating the real `os.name` is actively unsafe here (this test's
    default `_prepare_windows_onnxruntime_dll_search_path()` call would hit
    a real, unmocked `Path(__file__)` construction)."""

    fake_temp_dir = _CleanupRaisingTemporaryDirectory()
    monkeypatch.setattr(onnx_provider.tempfile, "TemporaryDirectory", lambda *a, **k: fake_temp_dir)

    original_error = RuntimeError(
        "LoadLibrary failed with error 126: cublasLt64_13.dll could not be found"
    )
    fake_ort = _FakeOnnxRuntimeModule(session_error=original_error)
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)

    runtime = onnx_provider.OptionalOrtCudaRuntime()
    with pytest.raises(ReplayValidationError, match="onnx_cuda_session_load_failed") as caught:
        runtime.create_session(tmp_path / "model.onnx", input_name="images", output_names=("out",))

    assert fake_temp_dir.cleanup_attempted is True
    assert caught.value.__cause__ is original_error
    assert "cublasLt64_13.dll" in str(caught.value.__cause__)


def test_profile_root_cleanup_never_raises_out_of_session_close(tmp_path: Path) -> None:
    """`_ProfiledOrtSession.close()` -- the normal, successful-session-close
    path, not just the session-creation-failure path -- must not propagate a
    Windows profiling-directory cleanup failure either."""

    fake_temp_dir = _CleanupRaisingTemporaryDirectory()
    fake_session = _FakeOrtInferenceSession(("CUDAExecutionProvider",))
    profiled = onnx_provider._ProfiledOrtSession(fake_session, fake_temp_dir)

    profiled.close()  # must not raise despite fake_temp_dir.cleanup() raising

    assert fake_temp_dir.cleanup_attempted is True


def test_onnxruntime_runtime_never_silently_falls_back_to_cpu_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end through the real `OptionalOrtCudaRuntime` (not just the
    `CudaRuntime`-Protocol test doubles used elsewhere in this file): on a
    simulated Windows host, CPU-only availability must be rejected before
    any session is ever created -- no silent fallback."""

    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider, "os", _FakeWindowsOs())
    monkeypatch.setattr(onnx_provider.util, "find_spec", lambda name: True)

    fake_ort = _FakeOnnxRuntimeModule(available_providers=("CPUExecutionProvider",))
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)

    _, bundle = _bundle(tmp_path)
    provider = OnnxCudaObservationProvider(runtime=onnx_provider.OptionalOrtCudaRuntime(), bundle=bundle)

    with pytest.raises(ReplayValidationError, match="onnx_cuda_unavailable"):
        provider.load()

    assert provider.session_loaded is False
    assert fake_ort.created_sessions == []


def test_onnxruntime_runtime_rejects_session_that_selects_cpu_first_on_windows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even once a real (fake-onnxruntime) session is created successfully
    through `OptionalOrtCudaRuntime.create_session` -- DLL search path
    prepared, profiling temp dir created -- a session that selects CPU
    first must still be rejected outright, and its profiling temp dir must
    still be cleaned up (bounded/safe), not leaked."""

    _reset_windows_dll_search_path_state(monkeypatch)
    monkeypatch.setattr(onnx_provider, "os", _FakeWindowsOs())
    monkeypatch.setattr(onnx_provider.util, "find_spec", lambda name: True)

    fake_ort = _FakeOnnxRuntimeModule(
        available_providers=("CUDAExecutionProvider", "CPUExecutionProvider"),
        session_providers=("CPUExecutionProvider", "CUDAExecutionProvider"),
    )
    monkeypatch.setitem(sys.modules, "onnxruntime", fake_ort)

    _, bundle = _bundle(tmp_path)
    provider = OnnxCudaObservationProvider(runtime=onnx_provider.OptionalOrtCudaRuntime(), bundle=bundle)

    with pytest.raises(ReplayValidationError, match="onnx_cuda_no_fallback"):
        provider.load()

    assert provider.session_loaded is False
    assert len(fake_ort.created_sessions) == 1
