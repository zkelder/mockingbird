"""Acoustic Runtime & Quality v1 -- bounded, reproducible acoustic quality
benchmark (Phase G/H). See docs/acoustic-runtime-quality-v1-contract.md and
tests/fixtures/acoustic/PROVENANCE.md for the full corpus/policy and every
fixture's individual provenance/license.

This is a **product-quality benchmark sufficient to tune/promote runtime
policy** -- explicitly not a research-grade corpus (eight clips: three real
third-party recordings under disclosed CC licenses, two mechanical/mix
derivatives of those real recordings, three synthetic -- see
`ACOUSTIC_BENCHMARK_CORPUS` for the exact, current count and composition,
which this docstring must never silently drift from). It never opens or
writes the product database, is never used for training, and is kept
entirely separate from ordinary private user Observations -- see
`mockingbird.observation.evaluation_governance`'s truth-boundary doctrine,
which this module respects by construction: nothing here ever asserts
`reviewed_truth`; every expectation below is a bounded, hand-set,
disclosed benchmark label, not reviewed product truth.

Reuses the real, unmodified production adapters
(`species.birdnet_adapter.run_birdnet_on_clip`,
`observation.acoustic_ingest._is_non_avian_soundscape_class`) -- this
module never reimplements inference or filtering logic, only scores their
real output against the corpus's bounded expectations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal
import hashlib
import json

ACOUSTIC_BENCHMARK_SCHEMA_VERSION = 1

#: A lower analysis floor than the production default, used only to observe
#: BirdNET's full confidence distribution for this corpus (Phase H:
#: "confidence distributions") -- never itself a candidate-admission
#: threshold; scoring against the real production default happens
#: separately, below.
LOW_FLOOR_FOR_ANALYSIS = 0.05

FixtureCategory = Literal[
    "clear_target_vocalization",
    "distant_quiet_vocalization",
    "overlapping_vocalization",
    "multi_species",
    "background_noise",
    "wind_rain_like_noise",
    "silence",
    "mechanical_environmental_confusor",
]

ProvenanceKind = Literal["real", "derived", "synthetic"]


@dataclass(frozen=True)
class AcousticBenchmarkClip:
    """One bounded corpus entry. `filename` is relative to the fixtures
    directory. Full attribution/license text lives in `tests/fixtures/
    acoustic/PROVENANCE.md` -- deliberately not duplicated here (one source
    of truth); `provenance_kind` is the short, machine-checkable summary of
    that same fact."""

    clip_id: str
    filename: str
    category: FixtureCategory
    provenance_kind: ProvenanceKind
    #: Bounded, hand-set ground truth this clip is scored against -- from
    #: direct real-model verification recorded in PROVENANCE.md at the time
    #: each fixture was added, never inferred or auto-generated.
    expects_candidate: bool
    expected_species: str | None = None
    notes: str = ""


ACOUSTIC_BENCHMARK_CORPUS: tuple[AcousticBenchmarkClip, ...] = (
    AcousticBenchmarkClip(
        clip_id="cardinal-clear",
        filename="northern_cardinal_48k_mono_15s.wav",
        category="clear_target_vocalization",
        provenance_kind="real",
        expects_candidate=True,
        expected_species="Northern Cardinal",
        notes="CC BY-SA 3.0 field recording; 3/3 windows 0.81-0.999 confidence in prior verification.",
    ),
    AcousticBenchmarkClip(
        clip_id="chickadee-clear",
        filename="black_capped_chickadee_48k_mono_12s.wav",
        category="multi_species",
        provenance_kind="real",
        expects_candidate=True,
        expected_species="Black-capped Chickadee",
        notes="CC BY-SA 3.0 field recording; includes real same-family confusor windows later in the clip.",
    ),
    AcousticBenchmarkClip(
        clip_id="cardinal-distant-quiet",
        filename="cardinal_distant_quiet_48k_mono_derived.wav",
        category="distant_quiet_vocalization",
        provenance_kind="derived",
        expects_candidate=True,
        expected_species="Northern Cardinal",
        notes="-20dB volume-attenuated derivative of the clear Cardinal clip above.",
    ),
    AcousticBenchmarkClip(
        clip_id="overlapping-cardinal-chickadee",
        filename="overlapping_cardinal_chickadee_48k_mono_derived.wav",
        category="overlapping_vocalization",
        provenance_kind="derived",
        expects_candidate=True,
        expected_species=None,  # either/both species may be recognized -- scored as "at least one candidate species"
        notes="Equal-weight mix of the two real clips above, both genuinely audible simultaneously.",
    ),
    AcousticBenchmarkClip(
        clip_id="pink-noise-negative",
        filename="no_bird_synthetic_noise_48k_mono_10s.wav",
        category="background_noise",
        provenance_kind="synthetic",
        expects_candidate=False,
        notes="Synthetic pink noise; 0 detections in prior verification.",
    ),
    AcousticBenchmarkClip(
        clip_id="wind-like-negative",
        filename="wind_like_synthetic_noise_48k_mono_12s.wav",
        category="wind_rain_like_noise",
        provenance_kind="synthetic",
        expects_candidate=False,
    ),
    AcousticBenchmarkClip(
        clip_id="silence-negative",
        filename="silence_synthetic_48k_mono_10s.wav",
        category="silence",
        provenance_kind="synthetic",
        expects_candidate=False,
    ),
    AcousticBenchmarkClip(
        clip_id="lawnmower-confusor",
        filename="lawnmower_confusor_48k_mono_15s.wav",
        category="mechanical_environmental_confusor",
        provenance_kind="real",
        expects_candidate=False,
        notes=(
            "CC BY 4.0 recording; scores Engine 0.51-0.69/Power tools 0.29-0.53 -- the fixture "
            "that drove the non-avian soundscape-class filtering fix (see acoustic_ingest.py)."
        ),
    ),
)


@dataclass(frozen=True)
class ClipDetectionRecord:
    """One raw BirdNET detection, unmodified, plus whether it is one of
    BirdNET's own known non-avian soundscape classes."""

    common_name: str
    scientific_name: str
    confidence: float
    is_non_avian_soundscape: bool


@dataclass(frozen=True)
class ClipEvaluationResult:
    clip_id: str
    filename: str
    category: FixtureCategory
    provenance_kind: ProvenanceKind
    expects_candidate: bool
    expected_species: str | None
    windows_analyzed: int
    #: Every detection BirdNET reported at `LOW_FLOOR_FOR_ANALYSIS` --
    #: confidence-distribution evidence (Phase H), not a candidate-admission
    #: decision.
    low_floor_detections: tuple[ClipDetectionRecord, ...]
    #: The subset that clears the real production confidence floor --
    #: what an actual analysis run would have seen.
    production_detections: tuple[ClipDetectionRecord, ...]
    would_create_candidate: bool
    top_species: str | None
    top_confidence: float | None
    matches_expectation: bool
    error: str | None = None


@dataclass(frozen=True)
class AcousticQualityReport:
    schema_version: int
    production_min_confidence: float
    corpus_size: int
    evaluated_count: int
    error_count: int
    clip_results: tuple[ClipEvaluationResult, ...]
    positive_clip_count: int
    positive_recall_count: int
    negative_clip_count: int
    negative_false_positive_count: int
    threshold_decision: str
    semantic_fingerprint: str

    @property
    def positive_recall_rate(self) -> float | None:
        return (self.positive_recall_count / self.positive_clip_count) if self.positive_clip_count else None

    @property
    def negative_false_positive_rate(self) -> float | None:
        return (
            self.negative_false_positive_count / self.negative_clip_count
            if self.negative_clip_count else None
        )

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["positive_recall_rate"] = self.positive_recall_rate
        payload["negative_false_positive_rate"] = self.negative_false_positive_rate
        return payload


def _decide_threshold_policy(
    results: list[ClipEvaluationResult], production_min_confidence: float,
) -> str:
    """One explicit, evidence-proportionate decision (Phase H) --
    deliberately data-driven from whatever `results` actually shows, never
    a pre-written conclusion. Never claims general BirdNET calibration from
    this bounded corpus; every branch says so explicitly."""

    negatives = [r for r in results if not r.expects_candidate and r.error is None]
    positives = [r for r in results if r.expects_candidate and r.error is None]
    false_positives = [r for r in negatives if r.would_create_candidate]
    misses = [r for r in positives if not r.would_create_candidate]

    if false_positives:
        ids = ", ".join(r.clip_id for r in false_positives)
        return (
            f"NOT DEFENSIBLE AS-IS: {len(false_positives)} of {len(negatives)} negative/confusor "
            f"clip(s) produced a false candidate at min_confidence={production_min_confidence} "
            f"({ids}). This corpus is too small to derive a statistically confident new global "
            "threshold, but each flagged case should be investigated before shipping unattended."
        )
    if misses:
        ids = ", ".join(r.clip_id for r in misses)
        return (
            f"DEFENSIBLE, NO CHANGE: zero false positives across {len(negatives)} negative/"
            f"confusor clip(s) at min_confidence={production_min_confidence}, but {len(misses)} "
            f"positive clip(s) were missed ({ids}). Consistent with imperfect recall on quiet/"
            "distant real audio, not evidence to lower the confidence floor -- doing so on a "
            "corpus this small would trade a known, bounded miss for an unmeasured false-positive "
            "risk, exactly the false-certainty this milestone's doctrine warns against."
        )
    return (
        f"DEFENSIBLE, NO CHANGE: every positive clip in this bounded {len(positives)}-clip corpus "
        f"produced a candidate and every negative/confusor clip in this bounded {len(negatives)}-"
        f"clip corpus (including a real non-bird mechanical recording) produced none, at the "
        f"existing default min_confidence={production_min_confidence}. This corpus is too small "
        "to justify moving the threshold in either direction; the existing default is not "
        "contradicted by the evidence available. General BirdNET calibration is NOT claimed from "
        "this corpus size."
    )


def evaluate_acoustic_quality(
    fixtures_dir: Path,
    *,
    corpus: tuple[AcousticBenchmarkClip, ...] = ACOUSTIC_BENCHMARK_CORPUS,
    production_min_confidence: float | None = None,
    analyzer: Any | None = None,
) -> AcousticQualityReport:
    """Run the real, unmodified `birdnet_adapter.run_birdnet_on_clip` over
    every corpus clip and score it against the corpus's bounded
    expectations. Never raises for a missing fixture or an unavailable
    BirdNET runtime -- each such clip is recorded with `error` set instead,
    exactly the same "abstention over false certainty" doctrine this
    module is itself evaluating."""

    from mockingbird.observation.acoustic_ingest import _is_non_avian_soundscape_class
    from mockingbird.species.birdnet_adapter import (
        BirdNetAdapterConfig,
        BirdNetConfigurationError,
        run_birdnet_on_clip,
    )

    resolved_min_confidence = (
        production_min_confidence if production_min_confidence is not None
        else BirdNetAdapterConfig().min_confidence
    )

    results: list[ClipEvaluationResult] = []
    for clip in corpus:
        clip_path = fixtures_dir / clip.filename
        if not clip_path.is_file():
            results.append(
                ClipEvaluationResult(
                    clip_id=clip.clip_id, filename=clip.filename, category=clip.category,
                    provenance_kind=clip.provenance_kind, expects_candidate=clip.expects_candidate,
                    expected_species=clip.expected_species, windows_analyzed=0,
                    low_floor_detections=(), production_detections=(),
                    would_create_candidate=False, top_species=None, top_confidence=None,
                    matches_expectation=False, error="fixture_missing",
                )
            )
            continue
        try:
            analysis = run_birdnet_on_clip(
                clip_path,
                config=BirdNetAdapterConfig(min_confidence=LOW_FLOOR_FOR_ANALYSIS),
                analyzer=analyzer,
            )
        except BirdNetConfigurationError as error:
            results.append(
                ClipEvaluationResult(
                    clip_id=clip.clip_id, filename=clip.filename, category=clip.category,
                    provenance_kind=clip.provenance_kind, expects_candidate=clip.expects_candidate,
                    expected_species=clip.expected_species, windows_analyzed=0,
                    low_floor_detections=(), production_detections=(),
                    would_create_candidate=False, top_species=None, top_confidence=None,
                    matches_expectation=False, error=str(error),
                )
            )
            continue

        low_floor_records = tuple(
            ClipDetectionRecord(
                common_name=detection.common_name, scientific_name=detection.scientific_name,
                confidence=detection.confidence,
                is_non_avian_soundscape=_is_non_avian_soundscape_class(detection),
            )
            for detection in analysis.detections
        )
        production_records = tuple(
            record for record in low_floor_records if record.confidence >= resolved_min_confidence
        )
        avian_production_records = tuple(
            record for record in production_records if not record.is_non_avian_soundscape
        )
        would_create_candidate = len(avian_production_records) > 0
        top = max(avian_production_records, key=lambda r: r.confidence, default=None)
        matches = would_create_candidate == clip.expects_candidate
        results.append(
            ClipEvaluationResult(
                clip_id=clip.clip_id, filename=clip.filename, category=clip.category,
                provenance_kind=clip.provenance_kind, expects_candidate=clip.expects_candidate,
                expected_species=clip.expected_species, windows_analyzed=analysis.windows_analyzed,
                low_floor_detections=low_floor_records, production_detections=production_records,
                would_create_candidate=would_create_candidate,
                top_species=top.common_name if top else None,
                top_confidence=top.confidence if top else None,
                matches_expectation=matches,
            )
        )

    evaluated = [r for r in results if r.error is None]
    positives = [r for r in evaluated if r.expects_candidate]
    negatives = [r for r in evaluated if not r.expects_candidate]
    positive_recall_count = sum(1 for r in positives if r.would_create_candidate)
    negative_fp_count = sum(1 for r in negatives if r.would_create_candidate)

    fingerprint_payload = json.dumps(
        [
            {
                "clip_id": r.clip_id, "expects_candidate": r.expects_candidate,
                "would_create_candidate": r.would_create_candidate,
                "top_species": r.top_species, "error": r.error,
            }
            for r in results
        ],
        sort_keys=True,
    )
    return AcousticQualityReport(
        schema_version=ACOUSTIC_BENCHMARK_SCHEMA_VERSION,
        production_min_confidence=resolved_min_confidence,
        corpus_size=len(corpus),
        evaluated_count=len(evaluated),
        error_count=len(results) - len(evaluated),
        clip_results=tuple(results),
        positive_clip_count=len(positives),
        positive_recall_count=positive_recall_count,
        negative_clip_count=len(negatives),
        negative_false_positive_count=negative_fp_count,
        threshold_decision=_decide_threshold_policy(results, resolved_min_confidence),
        semantic_fingerprint=hashlib.sha256(fingerprint_payload.encode("utf-8")).hexdigest(),
    )


def render_terminal_report(report: AcousticQualityReport) -> str:
    lines = [
        f"Acoustic quality benchmark (schema {report.schema_version}) -- "
        f"{report.evaluated_count}/{report.corpus_size} clips evaluated "
        f"({report.error_count} unavailable), min_confidence={report.production_min_confidence}",
        "",
    ]
    for result in report.clip_results:
        if result.error:
            lines.append(f"  [SKIP ] {result.clip_id:<28} {result.error}")
            continue
        mark = "OK" if result.matches_expectation else "MISS"
        top = (
            f"{result.top_species} ({result.top_confidence:.3f})"
            if result.top_species else "(none)"
        )
        lines.append(
            f"  [{mark:<4}] {result.clip_id:<28} expects_candidate={result.expects_candidate!s:<5} "
            f"got={result.would_create_candidate!s:<5} top={top}"
        )
    lines.append("")
    if report.positive_clip_count:
        lines.append(
            f"Positive recall: {report.positive_recall_count}/{report.positive_clip_count} "
            f"({report.positive_recall_rate:.0%})"
        )
    if report.negative_clip_count:
        lines.append(
            f"Negative false-positive rate: {report.negative_false_positive_count}/"
            f"{report.negative_clip_count} ({report.negative_false_positive_rate:.0%})"
        )
    lines.append("")
    lines.append(f"Threshold decision: {report.threshold_decision}")
    return "\n".join(lines)


__all__ = [
    "ACOUSTIC_BENCHMARK_CORPUS",
    "ACOUSTIC_BENCHMARK_SCHEMA_VERSION",
    "LOW_FLOOR_FOR_ANALYSIS",
    "AcousticBenchmarkClip",
    "AcousticQualityReport",
    "ClipDetectionRecord",
    "ClipEvaluationResult",
    "evaluate_acoustic_quality",
    "render_terminal_report",
]
