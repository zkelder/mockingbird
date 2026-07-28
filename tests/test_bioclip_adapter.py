from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import threading
import time
import tomllib
from types import SimpleNamespace
from typing import Any
import zipfile

import pytest

from mockingbird.species import bioclip_adapter
from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_ADAPTER_NAME,
    BIOCLIP_PROMPT_RECIPE_ID,
    BIOCLIP_PROMPT_RECIPE_SHA256,
    BIOCLIP_SCORE_KIND,
    BioClipBusyError,
    BioClipConfigurationError,
    BioClipNoResultError,
    BioClipOutputError,
    BioClipPrediction,
    BioClipPreparedRun,
    BioClipProvenance,
    BioClipRuntimeUnavailableError,
    BioClipTimeoutError,
    BioClipUnsupportedImageError,
    build_bioclip_config,
    get_bioclip_status,
    run_bioclip_from_image_loader,
    run_bioclip_on_image,
)


@pytest.fixture(autouse=True)
def reset_bioclip_worker_state() -> None:
    bioclip_adapter._discard_persistent_bioclip_worker()
    bioclip_adapter._LOADED_RUNTIME = None
    yield
    bioclip_adapter._discard_persistent_bioclip_worker()
    bioclip_adapter._LOADED_RUNTIME = None

def _npy_unicode_scalar(value: str) -> bytes:
    assert len(value) <= 64
    header_text = "{'descr': '<U64', 'fortran_order': False, 'shape': (), }"
    padding = (16 - ((10 + len(header_text) + 1) % 16)) % 16
    header = (header_text + " " * padding + "\n").encode("latin1")
    data = value.ljust(64, "\x00").encode("utf-32-le")
    return b"\x93NUMPY\x01\x00" + len(header).to_bytes(2, "little") + header + data


def _write_configured_artifacts(
    tmp_path: Path,
    *,
    labels: tuple[str, ...] = (
        "northern cardinal (Cardinalis cardinalis)",
        "blue jay (Cyanocitta cristata)",
        "blank scene with no animal",
    ),
) -> tuple[Any, tuple[str, ...]]:
    model_dir = tmp_path / "bioclip-model"
    model_dir.mkdir()
    model_config_path = model_dir / "open_clip_config.json"
    model_config_path.write_text(
        json.dumps(
            {
                "model_cfg": bioclip_adapter._EXPECTED_BIOCLIP_MODEL_CONFIG,
                "preprocess_cfg": (bioclip_adapter._EXPECTED_BIOCLIP_PREPROCESS_CONFIG),
            }
        ),
        encoding="utf-8",
    )
    model_weights_path = model_dir / "open_clip_model.safetensors"
    model_weights_path.write_bytes(b"local weights")

    labels_path = tmp_path / "labels.txt"
    labels_path.write_text("\n".join(labels) + "\n", encoding="utf-8")
    metadata = {
        "label_sha256": hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest(),
        "model_config_sha256": hashlib.sha256(
            model_config_path.read_bytes()
        ).hexdigest(),
        "model_weights_sha256": hashlib.sha256(
            model_weights_path.read_bytes()
        ).hexdigest(),
        "prompt_recipe_sha256": BIOCLIP_PROMPT_RECIPE_SHA256,
    }
    embedding_cache_path = tmp_path / "embeddings.npz"
    with zipfile.ZipFile(embedding_cache_path, "w") as archive:
        archive.writestr("embeddings.npy", b"precomputed vectors")
        for name, digest in metadata.items():
            archive.writestr(f"{name}.npy", _npy_unicode_scalar(digest))

    return (
        build_bioclip_config(
            model_dir=model_dir,
            labels_path=labels_path,
            embedding_cache_path=embedding_cache_path,
        ),
        labels,
    )


def test_module_import_does_not_require_optional_runtime() -> None:
    code = """
import builtins
original = builtins.__import__
blocked = {"PIL", "numpy", "open_clip", "torch"}
def guarded(name, *args, **kwargs):
    if name.split(".", 1)[0] in blocked:
        raise AssertionError(f"optional runtime imported: {name}")
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
import mockingbird.species.bioclip_adapter as adapter
assert adapter.get_bioclip_status(None).status == "not_configured"
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_pyproject_keeps_bioclip_runtime_optional_and_out_of_core() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    core_dependencies = "\n".join(pyproject["project"].get("dependencies", [])).lower()
    optional_dependencies = pyproject["project"].get("optional-dependencies", {})

    assert optional_dependencies["classifier-bioclip"] == [
        "open-clip-torch>=3.3,<3.4; python_version < '3.14'"
    ]
    assert "open-clip" not in core_dependencies
    assert "torch" not in core_dependencies


def test_config_builder_is_pure_and_missing_paths_are_not_configured() -> None:
    config = build_bioclip_config(
        model_dir="",
        labels_path=None,
        embedding_cache_path=" ",
    )

    assert config.model_dir is None
    assert config.labels_path is None
    assert config.embedding_cache_path is None
    status = get_bioclip_status(config)
    assert status.status == "not_configured"
    assert status.configured is False
    assert status.runtime_available is False
    assert "downloaded or generated" in status.detail


def test_prepare_run_hashes_model_artifacts_for_completed_result_reuse(
    tmp_path: Path,
) -> None:
    config, labels = _write_configured_artifacts(tmp_path)

    prepared = bioclip_adapter.prepare_bioclip_run(config)

    assert prepared.candidate_labels == labels
    assert prepared.candidate_set_sha256 == hashlib.sha256(
        "\n".join(labels).encode("utf-8")
    ).hexdigest()
    assert prepared.model_weights_sha256 == hashlib.sha256(
        config.model_dir.joinpath("open_clip_model.safetensors").read_bytes()  # type: ignore[union-attr]
    ).hexdigest()
    config.model_dir.joinpath("open_clip_model.safetensors").write_bytes(b"changed")  # type: ignore[union-attr]
    with pytest.raises(BioClipConfigurationError, match="model weights"):
        bioclip_adapter.prepare_bioclip_run(config)


def test_status_is_available_without_importing_or_loading_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, labels = _write_configured_artifacts(tmp_path)
    inspected: list[str] = []

    def find_spec(name: str):
        inspected.append(name)
        return SimpleNamespace()

    monkeypatch.setattr(bioclip_adapter.util, "find_spec", find_spec)
    monkeypatch.setattr(
        bioclip_adapter.metadata,
        "version",
        lambda name: (
            "3.3.0"
            if name == "open-clip-torch"
            else pytest.fail("unexpected distribution lookup")
        ),
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_load_optional_runtime",
        lambda: pytest.fail("status must not import or load the runtime"),
    )

    status = get_bioclip_status(config)

    assert status.status == "available"
    assert status.configured is True
    assert status.runtime_available is True
    assert status.device == "cpu"
    assert status.model_dir == str(config.model_dir)
    assert status.labels_path == str(config.labels_path)
    assert status.embedding_cache_path == str(config.embedding_cache_path)
    assert (
        status.labels_sha256
        == hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()
    )
    assert inspected == ["PIL", "numpy", "open_clip", "torch"]


def test_status_never_hashes_large_model_weights(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    hashed: list[Path] = []
    real_file_sha256 = bioclip_adapter._file_sha256

    def record_hash(path: Path) -> str:
        hashed.append(path)
        return real_file_sha256(path)

    monkeypatch.setattr(bioclip_adapter, "_file_sha256", record_hash)
    monkeypatch.setattr(
        bioclip_adapter.util,
        "find_spec",
        lambda _name: SimpleNamespace(),
    )
    monkeypatch.setattr(
        bioclip_adapter.metadata,
        "version",
        lambda name: (
            "3.3.0"
            if name == "open-clip-torch"
            else pytest.fail("unexpected distribution lookup")
        ),
    )

    assert get_bioclip_status(config).status == "available"
    assert [path.name for path in hashed] == ["open_clip_config.json"]


def test_status_reports_missing_runtime_without_importing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    monkeypatch.setattr(
        bioclip_adapter.util,
        "find_spec",
        lambda name: None if name in {"open_clip", "torch"} else SimpleNamespace(),
    )

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert status.configured is True
    assert status.runtime_available is False
    assert "open_clip, torch" in status.detail


def test_status_rejects_unsupported_open_clip_series_without_importing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    monkeypatch.setattr(
        bioclip_adapter.util,
        "find_spec",
        lambda _name: SimpleNamespace(),
    )
    monkeypatch.setattr(
        bioclip_adapter.metadata,
        "version",
        lambda name: (
            "3.4.0"
            if name == "open-clip-torch"
            else pytest.fail("unexpected distribution lookup")
        ),
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_load_optional_runtime",
        lambda: pytest.fail("status must not import or load the runtime"),
    )

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert status.runtime_available is False
    assert "OpenCLIP 3.3.x" in status.detail


@pytest.mark.parametrize(
    ("mutation", "expected_detail"),
    [
        ("missing_cache", "precomputed embedding cache was not found"),
        ("unsafe_weights", "exactly one supported local .safetensors"),
        ("gpu", "supports CPU execution only"),
    ],
)
def test_status_reports_safe_configuration_failures(
    tmp_path: Path,
    mutation: str,
    expected_detail: str,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    if mutation == "missing_cache":
        assert config.embedding_cache_path is not None
        config.embedding_cache_path.unlink()
    elif mutation == "unsafe_weights":
        assert config.model_dir is not None
        (config.model_dir / "open_clip_model.safetensors").unlink()
        (config.model_dir / "pytorch_model.bin").write_bytes(b"unsafe")
    else:
        config = build_bioclip_config(
            model_dir=config.model_dir,
            labels_path=config.labels_path,
            embedding_cache_path=config.embedding_cache_path,
            device="cuda",
        )

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert status.configured is True
    assert status.runtime_available is False
    assert expected_detail in status.detail


@pytest.mark.parametrize(
    ("suffix", "filename"),
    [
        (".bin", "alternate.bin"),
        (".pt", "alternate.pt"),
        (".pth", "alternate.pth"),
        (".ckpt", "alternate.ckpt"),
        (".safetensors", "alternate.safetensors"),
    ],
)
def test_status_rejects_every_ambiguous_checkpoint_file(
    tmp_path: Path,
    suffix: str,
    filename: str,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    assert config.model_dir is not None
    assert Path(filename).suffix == suffix
    (config.model_dir / filename).write_bytes(b"alternate checkpoint")

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert "no alternate checkpoint files" in status.detail


@pytest.mark.parametrize(
    ("remote_key", "remote_value"),
    [
        ("hf_model_name", "remote/model"),
        ("hf_tokenizer_name", "remote/tokenizer"),
        ("timm_model_name", "remote-timm-model"),
        ("pretrained", "remote-tag"),
        ("pretrained_hf", True),
    ],
)
def test_status_rejects_remote_capable_local_model_configuration(
    tmp_path: Path,
    remote_key: str,
    remote_value: Any,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    assert config.model_dir is not None
    (config.model_dir / "open_clip_config.json").write_text(
        json.dumps(
            {
                "model_cfg": {
                    "embed_dim": 768,
                    "vision_cfg": {remote_key: remote_value},
                }
            }
        ),
        encoding="utf-8",
    )

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert remote_key in status.detail
    assert "remote-capable" in status.detail


def test_status_rejects_cache_with_unbounded_uncompressed_members(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    monkeypatch.setattr(
        bioclip_adapter,
        "BIOCLIP_MAX_EMBEDDING_CACHE_UNCOMPRESSED_BYTES",
        1,
    )

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert "bounded uncompressed size" in status.detail


@pytest.mark.parametrize(
    ("constant_name", "expected_detail"),
    [
        ("BIOCLIP_MAX_MODEL_CONFIG_BYTES", "configuration exceeds"),
        ("BIOCLIP_MAX_LABELS_FILE_BYTES", "labels file exceeds"),
    ],
)
def test_status_bounds_parent_process_text_reads(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    constant_name: str,
    expected_detail: str,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    monkeypatch.setattr(bioclip_adapter, constant_name, 1)

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert expected_detail in status.detail


def test_status_bounds_model_weight_size_without_hashing_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    monkeypatch.setattr(bioclip_adapter, "BIOCLIP_MAX_MODEL_WEIGHTS_BYTES", 1)

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert "model weights exceed" in status.detail


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("model_cfg", "embed_dim", 65_536),
        ("vision_cfg", "image_size", 16_384),
        ("vision_cfg", "layers", 1_000),
        ("text_cfg", "vocab_size", 100_000_000),
        ("preprocess_cfg", "resize_mode", "squash"),
    ],
)
def test_status_rejects_non_bioclip_or_unbounded_architecture(
    tmp_path: Path,
    section: str,
    key: str,
    value: Any,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    assert config.model_dir is not None
    config_path = config.model_dir / "open_clip_config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if section in {"vision_cfg", "text_cfg"}:
        payload["model_cfg"][section][key] = value
    else:
        payload[section][key] = value
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    status = get_bioclip_status(config)

    assert status.status == "unavailable"
    assert "bounded BioCLIP 2 ViT-L/14" in status.detail


def test_run_requires_complete_configuration_before_runtime_import() -> None:
    config = build_bioclip_config(
        model_dir=None,
        labels_path=None,
        embedding_cache_path=None,
    )

    with pytest.raises(BioClipConfigurationError, match="not configured"):
        run_bioclip_on_image(object(), config)


@pytest.mark.parametrize("top_k", [True, 0, 21, 1.5])
def test_run_rejects_unbounded_top_k(top_k: Any) -> None:
    config = build_bioclip_config(
        model_dir="model",
        labels_path="labels",
        embedding_cache_path="cache",
    )

    with pytest.raises(BioClipConfigurationError, match="top_k"):
        run_bioclip_on_image(object(), config, top_k=top_k)


def test_embedding_cache_label_digest_must_match() -> None:
    with pytest.raises(BioClipConfigurationError, match="does not match"):
        bioclip_adapter._validate_cached_label_sha256(
            expected="a" * 64,
            cached="b" * 64,
        )


@pytest.mark.parametrize(
    ("metadata_key", "expected_name"),
    [
        ("label_sha256", "labels"),
        ("model_config_sha256", "model configuration"),
        ("model_weights_sha256", "model weights"),
        ("prompt_recipe_sha256", "prompt recipe"),
    ],
)
def test_embedding_cache_is_bound_to_every_runtime_input(
    tmp_path: Path,
    metadata_key: str,
    expected_name: str,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(
        config,
        hash_model_weights=True,
    )

    class FakeScalar:
        shape = ()

        def __init__(self, value: str) -> None:
            self.value = value

        def item(self) -> str:
            return self.value

    class FakeEmbeddings:
        ndim = 2
        shape = (
            len(validated.labels),
            bioclip_adapter.BIOCLIP_EMBEDDING_DIMENSION,
        )
        dtype = "float32"

    class FakeBooleanArray:
        @staticmethod
        def all() -> bool:
            return True

    metadata = {
        "label_sha256": validated.labels_sha256,
        "model_config_sha256": validated.model_config_sha256,
        "model_weights_sha256": validated.model_weights_sha256,
        "prompt_recipe_sha256": BIOCLIP_PROMPT_RECIPE_SHA256,
    }
    metadata[metadata_key] = "f" * 64

    class FakeCache(dict):
        files = [
            "embeddings",
            "label_sha256",
            "model_config_sha256",
            "model_weights_sha256",
            "prompt_recipe_sha256",
        ]

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

    cache = FakeCache(
        embeddings=FakeEmbeddings(),
        **{key: FakeScalar(value) for key, value in metadata.items()},
    )

    class FakeNumpy:
        floating = "floating"
        float32 = "float32"
        linalg = SimpleNamespace(
            norm=lambda _embeddings, axis: [1.0] * len(validated.labels)
        )

        @staticmethod
        def load(_path, *, allow_pickle: bool):
            assert allow_pickle is False
            return cache

        @staticmethod
        def asarray(value):
            return value

        @staticmethod
        def issubdtype(_dtype, _kind) -> bool:
            return True

        @staticmethod
        def isfinite(_value):
            return FakeBooleanArray()

        @staticmethod
        def array(value, *, dtype, copy: bool):
            assert dtype == "float32"
            assert copy is True
            return value

        @staticmethod
        def allclose(_values, _expected, *, rtol: float, atol: float) -> bool:
            return True

    with pytest.raises(BioClipConfigurationError, match=expected_name):
        bioclip_adapter._load_embedding_cache(validated, FakeNumpy())


def test_ranked_output_is_structured_sorted_and_explicitly_uncalibrated() -> None:
    suggestions = bioclip_adapter._rank_suggestions(
        (
            "northern cardinal (Cardinalis cardinalis)",
            "blue jay (Cyanocitta cristata)",
            "blank scene with no animal",
        ),
        [0.31, 0.62, 0.07],
        top_k=2,
    )

    assert [suggestion.label for suggestion in suggestions] == [
        "blue jay (Cyanocitta cristata)",
        "northern cardinal (Cardinalis cardinalis)",
    ]
    assert [suggestion.rank for suggestion in suggestions] == [1, 2]
    assert suggestions[0].common_name == "blue jay"
    assert suggestions[0].scientific_name == "Cyanocitta cristata"
    assert suggestions[0].score == pytest.approx(0.62)
    assert suggestions[0].score_kind == BIOCLIP_SCORE_KIND
    assert suggestions[0].calibrated is False


def test_ranked_output_rejects_score_label_mismatch() -> None:
    with pytest.raises(BioClipOutputError, match="score count"):
        bioclip_adapter._rank_suggestions(("bird", "vehicle"), [1.0], top_k=1)


def test_in_process_worker_uses_precomputed_cache_and_reuses_loaded_model(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, labels = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(
        config,
        hash_model_weights=True,
    )
    image = object()
    load_calls: list[object] = []
    runtime = SimpleNamespace(runtime_key=validated.runtime_key)
    modules = SimpleNamespace(
        numpy=object(),
        image_module=object(),
        open_clip=SimpleNamespace(__version__="3.3.0"),
        torch=SimpleNamespace(__version__="2.13.0+cpu"),
    )

    monkeypatch.setattr(
        bioclip_adapter,
        "_validate_config_files",
        lambda _config, **_kwargs: validated,
    )
    monkeypatch.setattr(bioclip_adapter, "_load_optional_runtime", lambda: modules)
    monkeypatch.setattr(
        bioclip_adapter,
        "_copy_rgb_image",
        lambda supplied, _module: supplied,
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_load_embedding_cache",
        lambda _validated, _numpy: "precomputed-embeddings",
    )

    def load_runtime(_validated, _modules, embeddings):
        assert embeddings == "precomputed-embeddings"
        load_calls.append(object())
        return runtime

    monkeypatch.setattr(bioclip_adapter, "_load_runtime", load_runtime)
    monkeypatch.setattr(
        bioclip_adapter,
        "_infer_scores",
        lambda loaded, supplied: (
            [0.15, 0.80, 0.05]
            if loaded is runtime and supplied is image
            else pytest.fail("unexpected runtime input")
        ),
    )
    first = bioclip_adapter._run_bioclip_in_process(image, config, top_k=2)
    second = bioclip_adapter._run_bioclip_in_process(image, config, top_k=2)

    assert isinstance(first, BioClipPrediction)
    assert first.suggestions == second.suggestions
    assert first.candidate_scores == second.candidate_scores
    assert [item.label for item in first.suggestions] == [labels[1], labels[0]]
    assert len(load_calls) == 1
    assert first.provenance.model_reused is False
    assert second.provenance.model_reused is True
    assert first.provenance.model_load_ms >= 0
    assert second.provenance.model_load_ms == 0
    assert first.provenance.inference_ms >= 0
    assert second.provenance.inference_ms >= 0
    assert first.provenance.adapter_id == BIOCLIP_ADAPTER_ID
    assert first.provenance.adapter_name == BIOCLIP_ADAPTER_NAME
    assert first.provenance.score_kind == BIOCLIP_SCORE_KIND
    assert first.provenance.calibrated is False
    assert first.provenance.device == "cpu"
    assert first.provenance.open_clip_version == "3.3.0"
    assert first.provenance.torch_version == "2.13.0+cpu"
    assert (
        first.provenance.embedding_cache_sha256
        == hashlib.sha256(
            config.embedding_cache_path.read_bytes()  # type: ignore[union-attr]
        ).hexdigest()
    )


class _FakeReceiveConnection:
    def __init__(self, data: bytes, *, ready: bool = True) -> None:
        self.data = data
        self.ready = ready
        self.closed = False
        self.poll_timeout: float | None = None
        self.maxlength: int | None = None
        self.sent: list[object] = []

    def poll(self, timeout: float) -> bool:
        self.poll_timeout = timeout
        return self.ready

    def send(self, value: object) -> None:
        self.sent.append(value)

    def recv_bytes(self, *, maxlength: int) -> bytes:
        self.maxlength = maxlength
        return self.data

    def close(self) -> None:
        self.closed = True


class _FakeSendConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeProcess:
    def __init__(
        self,
        *,
        exitcode: int = 0,
        alive: bool = True,
        survive_terminate: bool = False,
    ) -> None:
        self.exitcode = exitcode
        self.alive = alive
        self.survive_terminate = survive_terminate
        self.started = False
        self.terminated = False
        self.killed = False
        self.closed = False
        self.join_timeouts: list[float] = []

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float) -> None:
        self.join_timeouts.append(timeout)

    def terminate(self) -> None:
        self.terminated = True
        if not self.survive_terminate:
            self.alive = False
            self.exitcode = -15

    def kill(self) -> None:
        self.killed = True
        self.alive = False
        self.exitcode = -9

    def close(self) -> None:
        self.closed = True


class _FakeSpawnContext:
    def __init__(
        self,
        receive: _FakeReceiveConnection,
        send: _FakeSendConnection,
        process: _FakeProcess,
    ) -> None:
        self.receive = receive
        self.send = send
        self.process = process
        self.process_request: dict[str, Any] | None = None

    def Pipe(self, *, duplex: bool):
        assert duplex is True
        return self.receive, self.send

    def Process(self, **kwargs):
        self.process_request = kwargs
        return self.process


def _prediction_fixture(
    validated,
) -> BioClipPrediction:
    return _prediction_for_scores(
        validated,
        (0.8, 0.15, 0.05),
        top_k=2,
    )


def _prediction_for_scores(
    validated,
    scores: tuple[float, ...],
    *,
    top_k: int,
) -> BioClipPrediction:
    suggestions = bioclip_adapter._rank_suggestions(
        validated.labels,
        list(scores),
        top_k=top_k,
    )
    assert validated.embedding_cache_sha256 is not None
    model_weights_sha256 = (
        validated.model_weights_sha256
        or bioclip_adapter._file_sha256(validated.model_weights_path)
    )
    return BioClipPrediction(
        suggestions=suggestions,
        provenance=BioClipProvenance(
            adapter_id=BIOCLIP_ADAPTER_ID,
            adapter_name=BIOCLIP_ADAPTER_NAME,
            model_name=bioclip_adapter.BIOCLIP_MODEL_NAME,
            device="cpu",
            open_clip_version="3.3.0",
            torch_version="2.13.0+cpu",
            label_count=len(validated.labels),
            labels_sha256=validated.labels_sha256,
            embedding_cache_sha256=validated.embedding_cache_sha256,
            model_config_sha256=validated.model_config_sha256,
            model_weights_sha256=model_weights_sha256,
            model_weights_name=validated.model_weights_path.name,
            prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
            prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
            score_kind=BIOCLIP_SCORE_KIND,
            calibrated=False,
        ),
        candidate_labels=validated.labels,
        candidate_scores=scores,
    )


def _worker_bytes(prediction: BioClipPrediction) -> bytes:
    return json.dumps(
        bioclip_adapter._prediction_to_worker_payload(prediction),
        separators=(",", ":"),
    ).encode("utf-8")


def test_worker_round_trip_preserves_complete_ordered_candidate_bank_and_ties(
    tmp_path: Path,
) -> None:
    config, labels = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_for_scores(
        validated,
        (0.4, 0.4, 0.2),
        top_k=2,
    )

    encoded = _worker_bytes(prediction)
    decoded = bioclip_adapter._decode_worker_result(
        encoded,
        validated=validated,
        top_k=2,
    )

    assert decoded == prediction
    assert decoded.candidate_labels == labels
    assert decoded.candidate_scores == (0.4, 0.4, 0.2)
    assert [item.label for item in decoded.suggestions] == [labels[0], labels[1]]
    payload = json.loads(encoded)
    assert payload["candidate_scores"]["encoding"] == (
        bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING
    )
    assert "candidate_labels" not in payload


def test_complete_score_transport_is_bounded_at_maximum_candidate_count(
    tmp_path: Path,
) -> None:
    labels = tuple(
        f"candidate species {index}"
        for index in range(bioclip_adapter.BIOCLIP_MAX_LABEL_COUNT)
    )
    config, _ = _write_configured_artifacts(tmp_path, labels=labels)
    validated = bioclip_adapter._validate_config_files(config)
    scores = tuple(1.0 / bioclip_adapter.BIOCLIP_MAX_LABEL_COUNT for _ in labels)
    prediction = _prediction_for_scores(validated, scores, top_k=20)

    encoded = _worker_bytes(prediction)
    decoded = bioclip_adapter._decode_worker_result(
        encoded,
        validated=validated,
        top_k=20,
    )

    assert len(encoded) <= bioclip_adapter.BIOCLIP_MAX_RESULT_BYTES
    assert decoded.candidate_labels == labels
    assert decoded.candidate_scores == scores
    assert [item.label for item in decoded.suggestions] == list(labels[:20])


def test_worker_subprocess_success_uses_spawn_and_bounded_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    receive = _FakeReceiveConnection(_worker_bytes(prediction))
    send = _FakeSendConnection()
    process = _FakeProcess()
    context = _FakeSpawnContext(receive, send, process)
    requested_contexts: list[str] = []
    for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE"):
        monkeypatch.setenv(name, "parent-value")

    def get_context(name: str):
        requested_contexts.append(name)
        return context

    monkeypatch.setattr(bioclip_adapter.multiprocessing, "get_context", get_context)
    image_payload = bioclip_adapter._ImagePayload(
        width=1,
        height=1,
        rgb_bytes=b"\x00\x00\x00",
    )

    result = bioclip_adapter._run_worker_subprocess(
        image_payload,
        config,
        2,
        validated=validated,
    )

    assert result == prediction
    assert requested_contexts == ["spawn"]
    assert process.started is True
    assert process.closed is False
    assert send.closed is True
    assert receive.closed is False
    assert receive.poll_timeout == bioclip_adapter.BIOCLIP_RUN_TIMEOUT_SECONDS
    assert receive.maxlength == bioclip_adapter.BIOCLIP_MAX_RESULT_BYTES
    assert context.process_request is not None
    assert context.process_request["target"] is bioclip_adapter._bioclip_worker_loop
    assert context.process_request["daemon"] is True
    assert context.process_request["args"] == (send,)
    assert len(receive.sent) == 1
    shared_payload, request_config, request_top_k = receive.sent[0]
    assert request_config == config
    assert request_top_k == 2
    assert shared_payload.width == image_payload.width
    assert shared_payload.height == image_payload.height
    assert shared_payload.byte_count == len(image_payload.rgb_bytes)
    assert isinstance(shared_payload, bioclip_adapter._SharedImagePayload)
    assert not hasattr(shared_payload, "rgb_bytes")
    assert {
        name: bioclip_adapter.os.environ[name]
        for name in (
            "HF_HUB_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_DATASETS_OFFLINE",
        )
    } == {
        "HF_HUB_OFFLINE": "parent-value",
        "TRANSFORMERS_OFFLINE": "parent-value",
        "HF_DATASETS_OFFLINE": "parent-value",
    }


def test_worker_enforces_offline_hub_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_DATASETS_OFFLINE")
    for name in names:
        monkeypatch.delenv(name, raising=False)

    bioclip_adapter._enforce_worker_offline_environment()

    assert {name: bioclip_adapter.os.environ[name] for name in names} == {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
    }


def test_worker_never_transports_raw_typed_exception_detail(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class RecordingConnection:
        encoded: bytes | None = None

        def send_bytes(self, encoded: bytes) -> None:
            self.encoded = encoded

        def close(self) -> None:
            return None

    connection = RecordingConnection()
    raw_detail = f"failed at {tmp_path / 'private-model.safetensors'}"
    monkeypatch.setattr(
        bioclip_adapter,
        "_read_shared_image_payload",
        lambda _payload: bioclip_adapter._ImagePayload(
            width=1,
            height=1,
            rgb_bytes=b"\x00\x00\x00",
        ),
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_load_pillow_runtime",
        lambda: SimpleNamespace(frombytes=lambda *_args: object()),
    )

    def fail_with_raw_detail(*_args) -> BioClipPrediction:
        raise BioClipConfigurationError(raw_detail)

    monkeypatch.setattr(
        bioclip_adapter,
        "_run_bioclip_in_process",
        fail_with_raw_detail,
    )

    bioclip_adapter._bioclip_worker(
        connection,
        bioclip_adapter._SharedImagePayload(1, 1, "unused", 3),
        build_bioclip_config(
            model_dir="model",
            labels_path="labels",
            embedding_cache_path="cache",
        ),
        1,
    )

    assert connection.encoded is not None
    payload = json.loads(connection.encoded)
    assert payload == bioclip_adapter._worker_error("configuration")
    assert raw_detail not in connection.encoded.decode("utf-8")


def test_locked_run_serializes_in_memory_rgb_before_worker_start(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)

    class FakeRgbImage:
        width = 2
        height = 1

        @staticmethod
        def tobytes() -> bytes:
            return b"\x00\x01\x02\x03\x04\x05"

    captured: dict[str, Any] = {}

    def run_worker(image_payload, worker_config, top_k, *, validated):
        captured.update(
            image_payload=image_payload,
            config=worker_config,
            top_k=top_k,
            validated=validated,
        )
        return prediction

    monkeypatch.setattr(
        bioclip_adapter,
        "_validate_config_files",
        lambda _config: validated,
    )
    monkeypatch.setattr(bioclip_adapter, "_missing_runtime_packages", lambda: [])
    monkeypatch.setattr(
        bioclip_adapter,
        "_load_pillow_runtime",
        lambda: "lazy-pillow",
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_copy_rgb_image",
        lambda image, image_module: (
            FakeRgbImage()
            if image == "decoded-crop" and image_module == "lazy-pillow"
            else pytest.fail("unexpected image input")
        ),
    )
    monkeypatch.setattr(
        bioclip_adapter,
        "_run_worker_subprocess",
        run_worker,
    )

    result = bioclip_adapter._run_bioclip_locked(
        "decoded-crop",
        config,
        2,
    )

    assert result == prediction
    assert captured == {
        "image_payload": bioclip_adapter._ImagePayload(
            width=2,
            height=1,
            rgb_bytes=b"\x00\x01\x02\x03\x04\x05",
        ),
        "config": config,
        "top_k": 2,
        "validated": validated,
    }


def test_worker_subprocess_maps_nonzero_exit_and_closes_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    receive = _FakeReceiveConnection(_worker_bytes(prediction))
    send = _FakeSendConnection()
    process = _FakeProcess(exitcode=7, alive=False)
    context = _FakeSpawnContext(receive, send, process)
    monkeypatch.setattr(
        bioclip_adapter.multiprocessing,
        "get_context",
        lambda _name: context,
    )

    with pytest.raises(BioClipRuntimeUnavailableError, match="unexpectedly"):
        bioclip_adapter._run_worker_subprocess(
            bioclip_adapter._ImagePayload(1, 1, b"\x00\x00\x00"),
            config,
            2,
            validated=validated,
        )

    assert process.closed is True
    assert send.closed is True
    assert receive.closed is True


def test_worker_subprocess_timeout_terminates_then_kills(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    receive = _FakeReceiveConnection(b"", ready=False)
    send = _FakeSendConnection()
    process = _FakeProcess(alive=True, survive_terminate=True)
    context = _FakeSpawnContext(receive, send, process)
    monkeypatch.setattr(
        bioclip_adapter.multiprocessing,
        "get_context",
        lambda _name: context,
    )

    with pytest.raises(BioClipTimeoutError, match="timeout"):
        bioclip_adapter._run_worker_subprocess(
            bioclip_adapter._ImagePayload(1, 1, b"\x00\x00\x00"),
            config,
            2,
            validated=validated,
        )

    assert process.terminated is True
    assert process.killed is True
    assert process.alive is False
    assert send.closed is True
    assert receive.closed is True


def test_worker_result_rejects_tampered_label_or_provenance(
    tmp_path: Path,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    payload = bioclip_adapter._prediction_to_worker_payload(prediction)
    payload["suggestions"][0]["label"] = "not in configured candidates"

    with pytest.raises(BioClipOutputError, match="invalid suggestion"):
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )

    payload = bioclip_adapter._prediction_to_worker_payload(prediction)
    payload["provenance"]["labels_sha256"] = "0" * 64
    with pytest.raises(BioClipOutputError, match="provenance"):
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )

    payload = bioclip_adapter._prediction_to_worker_payload(prediction)
    payload["provenance"]["torch_version"] = "../../local/path"
    with pytest.raises(BioClipOutputError, match="runtime-version provenance"):
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )


def test_worker_result_rejects_malformed_complete_score_transport(
    tmp_path: Path,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    original = bioclip_adapter._prediction_to_worker_payload(prediction)
    malformed_values = (
        {
            "encoding": "unbounded-json",
            "count": 3,
            "data": original["candidate_scores"]["data"],
        },
        {
            "encoding": bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING,
            "count": 2,
            "data": original["candidate_scores"]["data"],
        },
        {
            "encoding": bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING,
            "count": 3,
            "data": "not-base64!",
        },
        {
            "encoding": bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING,
            "count": 3,
            "data": base64.b64encode(struct.pack("<2d", 0.8, 0.2)).decode("ascii"),
        },
        {
            "encoding": bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING,
            "count": 3,
            "data": base64.b64encode(
                struct.pack("<3d", float("nan"), 0.15, 0.05)
            ).decode("ascii"),
        },
        {
            "encoding": bioclip_adapter.BIOCLIP_FULL_SCORE_ENCODING,
            "count": 3,
            "data": base64.b64encode(struct.pack("<3d", 1.01, 0.0, 0.0)).decode(
                "ascii"
            ),
        },
    )

    for malformed in malformed_values:
        payload = json.loads(json.dumps(original))
        payload["candidate_scores"] = malformed
        with pytest.raises(BioClipOutputError, match="candidate-score transport"):
            bioclip_adapter._decode_worker_result(
                json.dumps(payload).encode("utf-8"),
                validated=validated,
                top_k=2,
            )


def test_worker_result_recomputes_top_k_from_complete_scores(
    tmp_path: Path,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    payload = bioclip_adapter._prediction_to_worker_payload(
        _prediction_fixture(validated)
    )
    payload["candidate_scores"]["data"] = base64.b64encode(
        struct.pack("<3d", 0.01, 0.98, 0.01)
    ).decode("ascii")

    with pytest.raises(BioClipOutputError, match="rankings"):
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )


def test_worker_no_result_is_typed_and_raw_detail_is_rejected(
    tmp_path: Path,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    payload = bioclip_adapter._worker_error("no_result")

    with pytest.raises(BioClipNoResultError) as caught:
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )

    assert caught.value.error_code == "bioclip_no_result"
    assert caught.value.error_stage == "output_parsing"
    assert str(tmp_path) not in str(caught.value)

    payload["detail"] = f"raw local path: {tmp_path}"
    with pytest.raises(BioClipOutputError, match="invalid error response"):
        bioclip_adapter._decode_worker_result(
            json.dumps(payload).encode("utf-8"),
            validated=validated,
            top_k=2,
        )


def test_empty_inference_scores_raise_explicit_no_result() -> None:
    class FakeTensor:
        def unsqueeze(self, _axis: int):
            return self

        def to(self, **_kwargs):
            return self

        def norm(self, **_kwargs):
            return self

        def clamp_min(self, _value: float):
            return self

        def __truediv__(self, _other):
            return self

        def __rmul__(self, _other):
            return self

        def __matmul__(self, _other):
            return self

        @property
        def T(self):
            return self

        def softmax(self, **_kwargs):
            return self

        def __getitem__(self, _index: int):
            return self

        def detach(self):
            return self

        def cpu(self):
            return self

        @staticmethod
        def tolist() -> list[float]:
            return []

    class FakeInferenceMode:
        def __enter__(self):
            return None

        def __exit__(self, *_args):
            return None

    tensor = FakeTensor()
    runtime = SimpleNamespace(
        preprocess=lambda _image: tensor,
        model=SimpleNamespace(
            encode_image=lambda _prepared: tensor,
            logit_scale=SimpleNamespace(exp=lambda: 1.0),
        ),
        text_embeddings=tensor,
        torch=SimpleNamespace(
            float32="float32",
            inference_mode=lambda: FakeInferenceMode(),
        ),
    )

    with pytest.raises(BioClipNoResultError, match="no candidate scores"):
        bioclip_adapter._infer_scores(runtime, object())


def test_image_serialization_is_raw_memory_only_and_pixel_bounded() -> None:
    class FakeImage:
        width = 2
        height = 1

        @staticmethod
        def tobytes() -> bytes:
            return b"\x00\x01\x02\x03\x04\x05"

    payload = bioclip_adapter._serialize_image(FakeImage())
    assert payload == bioclip_adapter._ImagePayload(
        width=2,
        height=1,
        rgb_bytes=b"\x00\x01\x02\x03\x04\x05",
    )

    class OversizedImage:
        width = bioclip_adapter.BIOCLIP_MAX_IMAGE_PIXELS + 1
        height = 1

    with pytest.raises(BioClipUnsupportedImageError, match="pixel count"):
        bioclip_adapter._serialize_image(OversizedImage())


def test_worker_image_shared_memory_round_trip_is_bounded_and_explicit() -> None:
    image_payload = bioclip_adapter._ImagePayload(
        width=2,
        height=1,
        rgb_bytes=b"\x00\x01\x02\x03\x04\x05",
    )
    descriptor, buffer = bioclip_adapter._share_image_payload(image_payload)
    try:
        assert descriptor.byte_count == 6
        assert bioclip_adapter._read_shared_image_payload(descriptor) == image_payload
    finally:
        bioclip_adapter._release_shared_image_buffer(buffer)


def test_runtime_loader_uses_only_explicit_local_dir_and_precomputed_embeddings(
    tmp_path: Path,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    calls: list[tuple[str, object]] = []

    class FakeModel:
        def eval(self) -> None:
            calls.append(("eval", None))

    class FakeTensor:
        def to(self, **kwargs):
            calls.append(("tensor_to", kwargs))
            return self

    class FakeOpenClip:
        @staticmethod
        def create_model_from_pretrained(
            identifier: str,
            *,
            device: str,
            return_transform: bool,
        ):
            calls.append(
                (
                    "create_model",
                    (identifier, device, return_transform),
                )
            )
            return FakeModel(), "local-preprocess"

    class FakeTorch:
        float32 = "float32"

        @staticmethod
        def from_numpy(embeddings):
            calls.append(("from_numpy", embeddings))
            return FakeTensor()

    embeddings = object()
    runtime = bioclip_adapter._load_runtime(
        validated,
        SimpleNamespace(open_clip=FakeOpenClip(), torch=FakeTorch()),
        embeddings,
    )

    assert runtime.preprocess == "local-preprocess"
    assert calls == [
        (
            "create_model",
            (f"local-dir:{validated.model_dir}", "cpu", True),
        ),
        ("eval", None),
        ("from_numpy", embeddings),
        ("tensor_to", {"device": "cpu", "dtype": "float32"}),
    ]


def test_single_flight_rejects_second_request_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = build_bioclip_config(
        model_dir="model",
        labels_path="labels",
        embedding_cache_path="cache",
    )
    provenance = BioClipProvenance(
        adapter_id=BIOCLIP_ADAPTER_ID,
        adapter_name=BIOCLIP_ADAPTER_NAME,
        model_name="local",
        device="cpu",
        open_clip_version="3.3.0",
        torch_version="2.13.0+cpu",
        label_count=1,
        labels_sha256="a" * 64,
        embedding_cache_sha256="b" * 64,
        model_config_sha256="c" * 64,
        model_weights_sha256="d" * 64,
        model_weights_name="model.safetensors",
        prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
        prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
        score_kind=BIOCLIP_SCORE_KIND,
        calibrated=False,
    )
    prediction = BioClipPrediction(suggestions=(), provenance=provenance)
    entered = threading.Event()
    release = threading.Event()

    def run_locked(_image, _config, _top_k):
        entered.set()
        assert release.wait(timeout=2)
        return prediction

    monkeypatch.setattr(bioclip_adapter, "_run_bioclip_locked", run_locked)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(run_bioclip_on_image, object(), config, 1)
        assert entered.wait(timeout=1)
        started = time.perf_counter()
        with pytest.raises(BioClipBusyError, match="already processing"):
            run_bioclip_on_image(object(), config, 1)
        assert time.perf_counter() - started < 0.1
        release.set()
        assert first.result(timeout=2) == prediction

    assert bioclip_adapter._RUN_LOCK.locked() is False


def test_loader_single_flight_reserves_slot_before_image_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    entered = threading.Event()
    release = threading.Event()
    close_calls: list[str] = []
    first_load_calls: list[str] = []
    second_load_calls: list[str] = []

    def run_locked(
        _image: object,
        _config: object,
        _top_k: int,
        **_kwargs: object,
    ) -> BioClipPrediction:
        entered.set()
        assert release.wait(timeout=2)
        return prediction

    def first_loader() -> object:
        first_load_calls.append("loaded")
        return SimpleNamespace(close=lambda: close_calls.append("closed"))

    def second_loader() -> object:
        second_load_calls.append("loaded")
        return object()

    monkeypatch.setattr(bioclip_adapter, "_run_bioclip_locked", run_locked)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first = executor.submit(run_bioclip_from_image_loader, first_loader, config, 1)
        assert entered.wait(timeout=1)
        with pytest.raises(BioClipBusyError, match="already processing"):
            run_bioclip_from_image_loader(second_loader, config, 1)
        assert second_load_calls == []
        release.set()
        assert first.result(timeout=2) == prediction

    assert first_load_calls == ["loaded"]
    assert close_calls == ["closed"]
    assert bioclip_adapter._RUN_LOCK.locked() is False


def test_loader_reports_safe_prepared_context_before_image_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    labels = (
        "northern cardinal (Cardinalis cardinalis)",
        "blue jay (Cyanocitta cristata)",
        "unknown bird",
    )
    config, _ = _write_configured_artifacts(tmp_path, labels=labels)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    events: list[str] = []
    prepared_runs: list[BioClipPreparedRun] = []

    def on_prepared(prepared: BioClipPreparedRun) -> None:
        events.append("prepared")
        prepared_runs.append(prepared)

    def image_loader() -> object:
        events.append("decoded")
        return SimpleNamespace(close=lambda: events.append("closed"))

    def run_locked(
        _image: object,
        _config: object,
        _top_k: int,
        *,
        validated,
    ) -> BioClipPrediction:
        events.append("worker")
        assert validated.labels == labels
        return prediction

    monkeypatch.setattr(bioclip_adapter, "_run_bioclip_locked", run_locked)

    result = run_bioclip_from_image_loader(
        image_loader,
        config,
        2,
        on_prepared=on_prepared,
    )

    assert result == prediction
    assert events == ["prepared", "decoded", "worker", "closed"]
    assert len(prepared_runs) == 1
    prepared = prepared_runs[0]
    assert prepared.candidate_labels == labels
    assert prepared.candidate_count == len(labels)
    assert (
        prepared.candidate_set_sha256
        == hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()
    )
    assert prepared.candidate_fingerprint_algorithm == (
        bioclip_adapter.BIOCLIP_CANDIDATE_FINGERPRINT_ALGORITHM
    )
    assert prepared.model_weights_verified is False
    assert prepared.timeout_seconds == bioclip_adapter.BIOCLIP_RUN_TIMEOUT_SECONDS
    assert prepared.preprocessing_config_json == json.dumps(
        bioclip_adapter._EXPECTED_BIOCLIP_PREPROCESS_CONFIG,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    assert str(tmp_path) not in repr(prepared)


def test_candidate_fingerprint_is_deterministic_and_order_sensitive() -> None:
    labels = ("bird", "vehicle", "blank scene")
    expected = hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest()

    assert bioclip_adapter._label_sha256(labels) == expected
    assert bioclip_adapter._label_sha256(labels) == expected
    assert bioclip_adapter._label_sha256(tuple(reversed(labels))) != expected


def test_loader_close_failure_still_releases_single_flight_slot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config, _ = _write_configured_artifacts(tmp_path)
    validated = bioclip_adapter._validate_config_files(config)
    prediction = _prediction_fixture(validated)
    monkeypatch.setattr(
        bioclip_adapter,
        "_run_bioclip_locked",
        lambda _image, _config, _top_k, **_kwargs: prediction,
    )

    def raise_on_close() -> None:
        raise RuntimeError("mock close failure")

    with pytest.raises(RuntimeError, match="mock close failure"):
        run_bioclip_from_image_loader(
            lambda: SimpleNamespace(close=raise_on_close),
            config,
            1,
        )

    assert run_bioclip_from_image_loader(lambda: object(), config, 1) == prediction
    assert bioclip_adapter._RUN_LOCK.locked() is False


def test_image_contract_rejects_paths_instead_of_reading_media() -> None:
    fake_image_module = SimpleNamespace(Image=type("FakeImage", (), {}))

    with pytest.raises(BioClipUnsupportedImageError, match="in-memory"):
        bioclip_adapter._copy_rgb_image("image.jpg", fake_image_module)


def test_image_contract_rejects_oversized_input_before_rgb_copy() -> None:
    convert_calls: list[str] = []

    class FakeImage:
        width = bioclip_adapter.BIOCLIP_MAX_IMAGE_PIXELS + 1
        height = 1

        @staticmethod
        def convert(_mode: str) -> object:
            convert_calls.append("converted")
            return object()

    with pytest.raises(BioClipUnsupportedImageError, match="pixel count"):
        bioclip_adapter._copy_rgb_image(
            FakeImage(),
            SimpleNamespace(Image=FakeImage),
        )

    assert convert_calls == []
