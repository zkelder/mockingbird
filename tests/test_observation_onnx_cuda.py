from __future__ import annotations

import hashlib
from io import BytesIO
import json
from pathlib import Path
from datetime import UTC, datetime

import numpy as np
import pytest
from PIL import Image

from mockingbird.observation.contracts import FramePacket
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
