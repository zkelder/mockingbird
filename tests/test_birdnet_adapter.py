"""Acoustic / BirdNET Observation Foundation v1: `birdnet_adapter` unit
tests. Uses the `recording` injection seam throughout (see
`birdnet_adapter.run_birdnet_on_clip`'s docstring) so these tests never
depend on the real, optional `classifier-birdnet` dependency stack being
installed -- the established "injected fake for the ML-heavy step"
convention this codebase already uses elsewhere."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from mockingbird.species import birdnet_adapter


class FakeRecording:
    """A deterministic stand-in for `birdnetlib.Recording` -- constructed
    already knowing what `.analyze()` should populate, matching the real
    object's post-`.analyze()` shape (`.detections`, `.duration`)."""

    def __init__(
        self,
        detections: list[dict[str, object]] | None = None,
        *,
        duration: float | None = 9.0,
        raise_on_analyze: Exception | None = None,
    ) -> None:
        self.detections = detections or []
        self.duration = duration
        self._raise_on_analyze = raise_on_analyze
        self.analyze_called = False

    def analyze(self) -> None:
        self.analyze_called = True
        if self._raise_on_analyze is not None:
            raise self._raise_on_analyze


@pytest.fixture
def clip_path(tmp_path: Path) -> Path:
    path = tmp_path / "clip.wav"
    path.write_bytes(b"not real audio bytes, but a real file -- analysis is faked below")
    return path


class TestBirdNetAdapterConfig:
    def test_defaults_are_valid(self) -> None:
        config = birdnet_adapter.BirdNetAdapterConfig()
        assert config.min_confidence == birdnet_adapter.DEFAULT_MIN_CONFIDENCE
        assert config.model_path is None
        assert config.latitude is None

    @pytest.mark.parametrize("value", [-0.1, 1.1])
    def test_out_of_range_confidence_rejected(self, value: float) -> None:
        with pytest.raises(birdnet_adapter.BirdNetConfigurationError):
            birdnet_adapter.BirdNetAdapterConfig(min_confidence=value)


class TestResolveBirdNetConfig:
    def test_empty_environment_uses_defaults(self) -> None:
        config = birdnet_adapter.resolve_birdnet_config(environment={})
        assert config.min_confidence == birdnet_adapter.DEFAULT_MIN_CONFIDENCE
        assert config.model_path is None
        assert config.latitude is None
        assert config.longitude is None

    def test_reads_every_field_from_environment(self) -> None:
        config = birdnet_adapter.resolve_birdnet_config(
            environment={
                birdnet_adapter.BIRDNET_MIN_CONFIDENCE_ENV_VAR: "0.72",
                birdnet_adapter.BIRDNET_MODEL_PATH_ENV_VAR: "/local/model.tflite",
                birdnet_adapter.BIRDNET_LABELS_PATH_ENV_VAR: "/local/labels.txt",
                birdnet_adapter.BIRDNET_LATITUDE_ENV_VAR: "35.3",
                birdnet_adapter.BIRDNET_LONGITUDE_ENV_VAR: "-79.2",
            }
        )
        assert config.min_confidence == pytest.approx(0.72)
        assert config.model_path == "/local/model.tflite"
        assert config.labels_path == "/local/labels.txt"
        assert config.latitude == pytest.approx(35.3)
        assert config.longitude == pytest.approx(-79.2)

    def test_invalid_min_confidence_string_raises(self) -> None:
        with pytest.raises(birdnet_adapter.BirdNetConfigurationError, match="invalid_min_confidence"):
            birdnet_adapter.resolve_birdnet_config(
                environment={birdnet_adapter.BIRDNET_MIN_CONFIDENCE_ENV_VAR: "not-a-number"}
            )

    def test_invalid_coordinate_string_raises(self) -> None:
        with pytest.raises(birdnet_adapter.BirdNetConfigurationError, match="invalid_coordinate"):
            birdnet_adapter.resolve_birdnet_config(
                environment={birdnet_adapter.BIRDNET_LATITUDE_ENV_VAR: "not-a-number"}
            )


class TestGetBirdNetStatus:
    def test_reports_unavailable_when_a_required_package_is_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(birdnet_adapter, "_missing_runtime_packages", lambda: ["librosa"])
        status = birdnet_adapter.get_birdnet_status()
        assert status.status == "unavailable"
        assert status.runtime_available is False
        assert "librosa" in status.detail

    def test_reports_available_when_nothing_is_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(birdnet_adapter, "_missing_runtime_packages", lambda: [])
        status = birdnet_adapter.get_birdnet_status()
        assert status.status == "available"
        assert status.runtime_available is True

    def test_never_raises_after_the_tflite_runtime_shim_has_already_installed(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Acoustic Runtime & Quality v1 (found via a real end-to-end
        acceptance run, not assumed): once `_install_tflite_runtime_shim`
        has installed its bare `types.ModuleType` shim (no real
        `__spec__`), a later `get_birdnet_status()` call must never raise
        -- `importlib.util.find_spec` raises `ValueError` for exactly a
        `sys.modules` entry whose `__spec__` is `None`, which is precisely
        what the shim installs. A real deployment calling `GET /api/
        birdnet/status` (or this milestone's own new runtime diagnostics)
        *after* any real acoustic analysis has already run in the same
        process would otherwise 500 instead of returning a clean status."""

        import types

        shim = types.ModuleType("tflite_runtime")
        monkeypatch.setitem(sys.modules, "tflite_runtime", shim)
        assert shim.__spec__ is None  # exactly the shape the real shim installs
        # The contract under test is the `tflite_runtime` probe against the
        # shim, not whether `birdnetlib`/`librosa` happen to be installed on
        # this host (they are not on the hosted runner) -- so only that
        # probe runs for real.
        monkeypatch.setattr(birdnet_adapter, "_REQUIRED_RUNTIME_PACKAGES", ())

        status = birdnet_adapter.get_birdnet_status()  # must not raise
        assert status.runtime_available is True


class TestRunBirdNetOnClip:
    def test_positive_detection_preserved_exactly(self, clip_path: Path) -> None:
        fake = FakeRecording(
            detections=[
                {
                    "common_name": "Northern Cardinal", "scientific_name": "Cardinalis cardinalis",
                    "confidence": 0.987654, "start_time": 3.0, "end_time": 6.0,
                }
            ],
            duration=9.0,
        )
        result = birdnet_adapter.run_birdnet_on_clip(
            clip_path, config=birdnet_adapter.BirdNetAdapterConfig(), recording=fake,
        )
        assert fake.analyze_called is True
        assert len(result.detections) == 1
        detection = result.detections[0]
        assert detection.common_name == "Northern Cardinal"
        assert detection.scientific_name == "Cardinalis cardinalis"
        assert detection.confidence == pytest.approx(0.987654)
        assert detection.start_ms == 3000
        assert detection.end_ms == 6000
        assert result.windows_analyzed == 3  # 9.0s / 3.0s BirdNET window

    def test_no_detection_is_a_legitimate_non_error_outcome(self, clip_path: Path) -> None:
        fake = FakeRecording(detections=[], duration=6.0)
        result = birdnet_adapter.run_birdnet_on_clip(
            clip_path, config=birdnet_adapter.BirdNetAdapterConfig(), recording=fake,
        )
        assert result.detections == ()
        assert result.windows_analyzed == 2

    def test_windows_analyzed_falls_back_to_detection_count_when_duration_unknown(
        self, clip_path: Path
    ) -> None:
        fake = FakeRecording(
            detections=[
                {"common_name": "A", "scientific_name": "A a", "confidence": 0.9, "start_time": 0.0, "end_time": 3.0},
                {"common_name": "B", "scientific_name": "B b", "confidence": 0.8, "start_time": 3.0, "end_time": 6.0},
            ],
            duration=None,
        )
        result = birdnet_adapter.run_birdnet_on_clip(
            clip_path, config=birdnet_adapter.BirdNetAdapterConfig(), recording=fake,
        )
        assert result.windows_analyzed == 2

    def test_provenance_captures_config_and_source_hash(self, clip_path: Path) -> None:
        config = birdnet_adapter.BirdNetAdapterConfig(min_confidence=0.65, latitude=35.3, longitude=-79.2)
        result = birdnet_adapter.run_birdnet_on_clip(
            clip_path, config=config, source_content_sha256="abc123", recording=FakeRecording(),
        )
        provenance = result.provenance
        assert provenance.adapter_id == "birdnet"
        assert provenance.model_version == birdnet_adapter.EXPECTED_MODEL_VERSION
        assert provenance.model_license == birdnet_adapter.MODEL_LICENSE
        assert provenance.min_confidence == pytest.approx(0.65)
        assert provenance.latitude == pytest.approx(35.3)
        assert provenance.longitude == pytest.approx(-79.2)
        assert provenance.source_content_sha256 == "abc123"
        provenance_dict = provenance.as_dict()
        assert provenance_dict["adapter_id"] == "birdnet"
        assert provenance_dict["source_content_sha256"] == "abc123"

    def test_missing_clip_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(birdnet_adapter.BirdNetConfigurationError, match="clip_file_missing"):
            birdnet_adapter.run_birdnet_on_clip(
                tmp_path / "does-not-exist.wav",
                config=birdnet_adapter.BirdNetAdapterConfig(),
                recording=FakeRecording(),
            )

    def test_analyze_failure_is_wrapped_never_raw(self, clip_path: Path) -> None:
        fake = FakeRecording(raise_on_analyze=RuntimeError("some raw third-party internal detail"))
        with pytest.raises(birdnet_adapter.BirdNetConfigurationError, match="birdnet_analysis_failed"):
            birdnet_adapter.run_birdnet_on_clip(
                clip_path, config=birdnet_adapter.BirdNetAdapterConfig(), recording=fake,
            )

    def test_recording_injection_never_imports_real_birdnetlib(
        self, clip_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The whole point of the `recording` seam: it must work even if
        `birdnetlib` genuinely is not importable."""

        import builtins

        real_import = builtins.__import__

        def _blocking_import(name: str, *args: object, **kwargs: object):
            if name == "birdnetlib" or name.startswith("birdnetlib."):
                raise ImportError("simulated: birdnetlib is not installed")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", _blocking_import)

        result = birdnet_adapter.run_birdnet_on_clip(
            clip_path, config=birdnet_adapter.BirdNetAdapterConfig(), recording=FakeRecording(),
        )
        assert result.detections == ()
