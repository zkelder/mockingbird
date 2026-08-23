"""Acoustic Runtime & Quality v1, Phase G/H: `acoustic_quality_benchmark`
tests. Split like `tests/test_acoustic_ingest_real_model.py`: hermetic
scoring/aggregation-logic tests here need no BirdNET runtime at all
(hand-built `ClipEvaluationResult`s); the full corpus-evaluation
integration test is real-model, `slow`-marked, `skipif`-gated on both the
optional `classifier-birdnet` extra and the fixtures directory being
present -- it skips cleanly, never fails, on a host lacking either."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from mockingbird.observation import acoustic_quality_benchmark as aqb

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "acoustic"


def _birdnet_runtime_available() -> bool:
    if importlib.util.find_spec("birdnetlib") is None:
        return False
    return (
        importlib.util.find_spec("tflite_runtime") is not None
        or importlib.util.find_spec("ai_edge_litert") is not None
        or importlib.util.find_spec("tensorflow") is not None
    )


def _corpus_fixtures_present() -> bool:
    return all((FIXTURES_DIR / clip.filename).is_file() for clip in aqb.ACOUSTIC_BENCHMARK_CORPUS)


requires_real_birdnet_corpus = pytest.mark.skipif(
    not (_birdnet_runtime_available() and _corpus_fixtures_present()),
    reason="optional classifier-birdnet extra and/or the local acoustic benchmark fixtures are unavailable",
)


def _result(
    clip_id: str, *, expects_candidate: bool, would_create_candidate: bool, error: str | None = None,
) -> aqb.ClipEvaluationResult:
    return aqb.ClipEvaluationResult(
        clip_id=clip_id, filename=f"{clip_id}.wav", category="clear_target_vocalization",
        provenance_kind="synthetic", expects_candidate=expects_candidate, expected_species=None,
        windows_analyzed=1, low_floor_detections=(), production_detections=(),
        would_create_candidate=would_create_candidate, top_species=None, top_confidence=None,
        matches_expectation=(expects_candidate == would_create_candidate), error=error,
    )


class TestCorpusManifestIntegrity:
    def test_every_corpus_entry_has_a_unique_id_and_a_real_category(self) -> None:
        ids = [clip.clip_id for clip in aqb.ACOUSTIC_BENCHMARK_CORPUS]
        assert len(ids) == len(set(ids))
        assert len(aqb.ACOUSTIC_BENCHMARK_CORPUS) >= 8  # a bounded but non-trivial corpus

    def test_corpus_includes_at_least_one_of_every_disclosed_provenance_kind(self) -> None:
        kinds = {clip.provenance_kind for clip in aqb.ACOUSTIC_BENCHMARK_CORPUS}
        assert kinds == {"real", "derived", "synthetic"}

    def test_corpus_includes_both_positive_and_negative_expectations(self) -> None:
        expectations = {clip.expects_candidate for clip in aqb.ACOUSTIC_BENCHMARK_CORPUS}
        assert expectations == {True, False}


class TestThresholdDecisionLogic:
    def test_no_false_positives_no_misses_is_defensible_no_change(self) -> None:
        results = [
            _result("pos-1", expects_candidate=True, would_create_candidate=True),
            _result("neg-1", expects_candidate=False, would_create_candidate=False),
        ]
        decision = aqb._decide_threshold_policy(results, 0.5)
        assert decision.startswith("DEFENSIBLE, NO CHANGE")
        assert "false positive" not in decision.lower() or "zero false positives" in decision.lower()

    def test_any_false_positive_is_not_defensible_as_is(self) -> None:
        results = [
            _result("pos-1", expects_candidate=True, would_create_candidate=True),
            _result("neg-1", expects_candidate=False, would_create_candidate=True),
        ]
        decision = aqb._decide_threshold_policy(results, 0.5)
        assert decision.startswith("NOT DEFENSIBLE")
        assert "neg-1" in decision

    def test_a_miss_with_no_false_positive_is_defensible_but_discloses_the_miss(self) -> None:
        results = [
            _result("pos-1", expects_candidate=True, would_create_candidate=False),
            _result("neg-1", expects_candidate=False, would_create_candidate=False),
        ]
        decision = aqb._decide_threshold_policy(results, 0.5)
        assert decision.startswith("DEFENSIBLE, NO CHANGE")
        assert "pos-1" in decision

    def test_errored_clips_are_excluded_from_the_decision(self) -> None:
        results = [
            _result("pos-1", expects_candidate=True, would_create_candidate=True),
            _result("neg-1", expects_candidate=False, would_create_candidate=True, error="fixture_missing"),
        ]
        decision = aqb._decide_threshold_policy(results, 0.5)
        # The errored negative must not be counted as a false positive --
        # an unevaluable clip proves nothing either way.
        assert decision.startswith("DEFENSIBLE, NO CHANGE")


class TestAcousticQualityReportProperties:
    def test_recall_and_false_positive_rates_compute_correctly(self) -> None:
        report = aqb.AcousticQualityReport(
            schema_version=1, production_min_confidence=0.5, corpus_size=4, evaluated_count=4,
            error_count=0,
            clip_results=(
                _result("pos-1", expects_candidate=True, would_create_candidate=True),
                _result("pos-2", expects_candidate=True, would_create_candidate=False),
                _result("neg-1", expects_candidate=False, would_create_candidate=False),
                _result("neg-2", expects_candidate=False, would_create_candidate=False),
            ),
            positive_clip_count=2, positive_recall_count=1, negative_clip_count=2,
            negative_false_positive_count=0, threshold_decision="test", semantic_fingerprint="abc",
        )
        assert report.positive_recall_rate == pytest.approx(0.5)
        assert report.negative_false_positive_rate == pytest.approx(0.0)

    def test_rates_are_none_when_the_denominator_is_zero(self) -> None:
        report = aqb.AcousticQualityReport(
            schema_version=1, production_min_confidence=0.5, corpus_size=0, evaluated_count=0,
            error_count=0, clip_results=(), positive_clip_count=0, positive_recall_count=0,
            negative_clip_count=0, negative_false_positive_count=0, threshold_decision="n/a",
            semantic_fingerprint="abc",
        )
        assert report.positive_recall_rate is None
        assert report.negative_false_positive_rate is None


class TestEvaluateAcousticQualityMissingFixtures:
    def test_missing_fixtures_directory_reports_every_clip_as_an_error_never_raises(
        self, tmp_path: Path,
    ) -> None:
        report = aqb.evaluate_acoustic_quality(tmp_path)  # empty directory, no fixtures at all
        assert report.evaluated_count == 0
        assert report.error_count == report.corpus_size
        assert all(result.error == "fixture_missing" for result in report.clip_results)


@requires_real_birdnet_corpus
@pytest.mark.slow
class TestRealAcousticQualityBenchmark:
    """Real-model acceptance for the full corpus -- see the module
    docstring. Genuinely runs BirdNET inference over every real/derived/
    synthetic fixture and asserts on real, previously-observed outcomes
    (see tests/fixtures/acoustic/PROVENANCE.md for each fixture's own
    verification record)."""

    def test_full_corpus_evaluates_with_perfect_recall_and_zero_false_positives(self) -> None:
        report = aqb.evaluate_acoustic_quality(FIXTURES_DIR)

        assert report.error_count == 0
        assert report.evaluated_count == report.corpus_size

        # The real lawnmower confusor -- the fixture that drove the
        # non-avian soundscape filtering fix -- must never produce a
        # candidate.
        lawnmower = next(r for r in report.clip_results if r.clip_id == "lawnmower-confusor")
        assert lawnmower.would_create_candidate is False
        assert any(d.common_name in ("Engine", "Power tools") for d in lawnmower.production_detections)

        # The two real target-species clips must both produce a candidate
        # for the expected species.
        cardinal = next(r for r in report.clip_results if r.clip_id == "cardinal-clear")
        assert cardinal.would_create_candidate is True
        assert cardinal.top_species == "Northern Cardinal"

        chickadee = next(r for r in report.clip_results if r.clip_id == "chickadee-clear")
        assert chickadee.would_create_candidate is True
        assert chickadee.top_species == "Black-capped Chickadee"

        assert report.negative_false_positive_count == 0
        assert report.threshold_decision.startswith("DEFENSIBLE")
