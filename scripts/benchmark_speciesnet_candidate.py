#!/usr/bin/env python3
"""Detection & Species Model Benchmark / Promotion v1 -- SpeciesNet candidate run.

Runs the real, official ``speciesnet`` package's classifier component (v4.0.3a,
Apache-2.0 -- license confirmed directly from the downloaded artifact's own
``README.md`` frontmatter, resolving the "model-weight license unresolved"
blocker that previously stalled ``docs/speciesnet-source-review.md``) against
the exact same real, already-recovered MockingBird evidence used to benchmark
and accept the production BioCLIP-2 eligibility/abstention policy
(``docs/identification-eligibility-abstention-v1-report.md``), for a genuine
head-to-head comparison. Every image path and every BioCLIP comparison number
below is a real, already-committed fact (never re-derived, never invented) --
mirroring ``scripts/benchmark_identification_eligibility.py``'s own citation
discipline.

Boundary: this script is benchmark-only and does not touch product code, the
product database, or any production configuration. It never creates a
``SpeciesSuggestion``, never writes to ``data/mockingbird.sqlite3``, and never
selects a runtime. The real local SpeciesNet model files (already downloaded,
no network call made here) live outside the repository, at
``~/.cache/kagglehub/models/google/speciesnet/pyTorch/v4.0.3a/1`` (or the path
given via ``--model-dir``). Real source images live either in this repo's own
gitignored ``data/`` tree or, for the archived 2026-08-11 field session, on the
real Windows dev userdata volume mounted at
``/mnt/c/Users/<user>/AppData/Local/MockingBirdDev/userdata`` (per
``docs/windows-dev-deployment-design.md``'s established dev-machine layout);
run with ``--skip-missing`` to degrade gracefully to whichever subset is
actually reachable on the current host rather than failing the whole run.

Usage::

    .venv/bin/python scripts/benchmark_speciesnet_candidate.py \\
        --output data/evaluations/species-promotion-v1/speciesnet-vs-bioclip-report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mockingbird.species.speciesnet_candidate import (  # noqa: E402
    BioClipComparisonPoint,
    SpeciesNetPrediction,
    compare_case,
    summarize_cases,
)

DEFAULT_MODEL_DIR = Path.home() / ".cache/kagglehub/models/google/speciesnet/pyTorch/v4.0.3a/1"
WINDOWS_IMPORTS_DIR = Path(
    "/mnt/c/Users/<user>/AppData/Local/MockingBirdDev/userdata/data/media/imports"
)
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class RunCase:
    case_id: str
    image_path: Path
    tier: str  # "full_frame" | "full_frame_with_detector_box" | "subject_focused" -- diagnostic label
    expected_taxon_id: str | None  # None = unscored/diagnostic-only, matches cohort D's convention
    bioclip: BioClipComparisonPoint
    note: str
    detector_box_xyxy: tuple[float, float, float, float] | None = None  # normalized [left, top, right, bottom]


def _c(label: str, score: float, abstained: bool) -> BioClipComparisonPoint:
    return BioClipComparisonPoint(top1_label=label, top1_score=score, abstained=abstained)


def build_cases() -> tuple[RunCase, ...]:
    # Real archived 2026-08-11 field session, real filenames re-derived from
    # `selected_identification_media_asset_id` in
    # data/field-acceptance/2026-08-14-subject-centric-species-crop/
    # geometry-inventory-011-018.json (the visit-id -> media-asset-id mapping
    # is NOT a simple numeric correspondence -- verified directly per-visit,
    # not assumed). Expected taxa for 013/014/016/017 and the "no bird
    # anywhere"/blank calls for 015/018 are independently re-confirmed here
    # by direct visual inspection of the real images, not merely copied from
    # the historical report.
    full_frame_media = {
        "visit-011": ("media-candidate-012.jpg", None, "Ambiguous/sliver-only per historical review; unscored.", (0.4468, 0.5902, 0.49, 0.6221)),
        "visit-012": ("media-candidate-013.jpg", None, "Ambiguous/sliver-only per historical review; unscored.", (0.4614, 0.634, 0.4989, 0.6881)),
        "visit-013": ("media-candidate-015.jpg", "house_finch", "Bird visually confirmed at feeder base.", (0.4661, 0.5895, 0.5051, 0.6276)),
        "visit-014": ("media-candidate-016.jpg", "house_finch", "Bird visually confirmed (per FINAL-REPORT.md).", (0.4567, 0.5888, 0.5051, 0.6381)),
        "visit-015": ("media-candidate-019.jpg", "blank", "No bird visible in frame; visually re-confirmed.", (0.2812, 0.5861, 0.3353, 0.6367)),
        "visit-016": ("media-candidate-020.jpg", "house_finch", "Bird visually confirmed (per FINAL-REPORT.md).", (0.4828, 0.5847, 0.5041, 0.634)),
        "visit-017": ("media-candidate-021.jpg", "house_finch", "Bird visually confirmed (per FINAL-REPORT.md).", (0.4588, 0.5888, 0.5114, 0.6339)),
        "visit-018": ("media-candidate-024.jpg", "blank", "Empty feeder per historical review; unscored ground truth not independently re-confirmed.", (0.4755, 0.6305, 0.5031, 0.6693)),
    }
    # Real recorded BioCLIP-2 full-frame result for each (identification-eligibility-abstention-v1-report.md
    # / scripts/benchmark_identification_eligibility.py COHORT_B_DIFFICULT_FULL_FRAME -- copied literally).
    full_frame_bioclip = {
        "visit-011": _c("red_bellied_woodpecker", 0.796, True),
        "visit-012": _c("red_bellied_woodpecker", 0.817, True),
        "visit-013": _c("red_bellied_woodpecker", 0.616, True),
        "visit-014": _c("tufted_titmouse", 0.369, True),
        "visit-015": _c("red_bellied_woodpecker", 0.529, True),
        "visit-016": _c("red_bellied_woodpecker", 0.645, True),
        "visit-017": _c("red_bellied_woodpecker", 0.779, True),
        "visit-018": _c("red_bellied_woodpecker", 0.338, True),
    }
    cases: list[RunCase] = []
    for visit, (filename, expected, note, box) in full_frame_media.items():
        # Two runs per visit, both real: (a) exactly what BioCLIP's own
        # honest full-frame fallback tier saw -- no bounding box at all,
        # since that tier exists precisely for when no subject box is
        # available; (b) the same real MDv5 detector box MockingBird's own
        # pipeline already produced for this Visit, which SpeciesNet's
        # `always_crop` architecture is actually designed to consume (its
        # own bundled detector stage normally supplies this). Comparing both
        # against the same recorded BioCLIP result shows whether SpeciesNet's
        # disadvantage is "worse at species ID" or "architecturally requires
        # a box BioCLIP does not."
        cases.append(
            RunCase(
                case_id=f"{visit}-full-frame-no-box",
                image_path=WINDOWS_IMPORTS_DIR / filename,
                tier="full_frame",
                expected_taxon_id=expected,
                bioclip=full_frame_bioclip[visit],
                note=note + " No bounding box given (matches BioCLIP's own full_frame tier input).",
            )
        )
        cases.append(
            RunCase(
                case_id=f"{visit}-full-frame-detector-box",
                image_path=WINDOWS_IMPORTS_DIR / filename,
                tier="full_frame_with_detector_box",
                expected_taxon_id=expected,
                bioclip=full_frame_bioclip[visit],
                note=note + " Real MDv5 normalized_track_box supplied (SpeciesNet's designed always_crop input).",
                detector_box_xyxy=box,
            )
        )

    # Same 4 real photographs' diagnostic subject-crop reproduction (visually
    # confirmed correct in the original milestone) -- COHORT_B_SUPPLEMENT_CLEAN_CROP.
    crop_dir = REPO_ROOT / "data/field-acceptance/2026-08-14-subject-centric-species-crop/review-images"
    supplement_bioclip = {
        "visit-013": _c("house_finch", 0.998, False),
        "visit-014": _c("house_finch", 0.997, False),
        "visit-016": _c("house_finch", 0.999, False),
        "visit-017": _c("house_finch", 0.925, False),
    }
    for visit, bioclip in supplement_bioclip.items():
        num = visit.split("-")[1]  # already zero-padded to 3 digits, e.g. "013" -- do not add another "0"
        cases.append(
            RunCase(
                case_id=f"{visit}-diagnostic-crop",
                image_path=crop_dir / f"visit-observation-candidate-{num}_padded_crop.jpg",
                tier="subject_focused",
                expected_taxon_id="house_finch",
                bioclip=bioclip,
                note="Diagnostic/exploratory crop, visually confirmed correct (real photo).",
            )
        )

    # Real production same-frame positive control -- COHORT_C's
    # visit-observation-candidate-019-house-finch (a *different* Visit than
    # the archived 011-018 set; Same-Frame Species Evidence v1's own milestone).
    cases.append(
        RunCase(
            case_id="visit-observation-candidate-019-house-finch",
            image_path=REPO_ROOT
            / "data/field-acceptance/2026-08-14-same-frame-species-evidence/review-images/same-frame_padded_crop.jpg",
            tier="subject_focused",
            expected_taxon_id="house_finch",
            bioclip=_c("house_finch", 0.9374827742576599, False),
            note="Real production same-frame capture; visually re-confirmed a real bird present.",
        )
    )

    # Real mandatory hard negatives -- COHORT_A (Visits 139/140). Direct visual
    # inspection of these two real, unmodified best-frame images (wide yard/
    # feeder scenes) did not turn up an independently-confirmable person/dog
    # subject at full-frame scale (consistent with the original detector hit
    # being a small/distant/partial-frame box, not something legible at this
    # zoom level) -- so these are run and reported as real diagnostic
    # evidence (does SpeciesNet also avoid a confident bird guess on this
    # scene?), never scored against an assumed "human"/"domestic_dog" ground
    # truth this script cannot independently verify.
    cases.append(
        RunCase(
            case_id="visit-139-person-dog",
            image_path=REPO_ROOT / "data/media/imports/media-asset-139-live-motion-best-frame.jpg",
            tier="full_frame",
            expected_taxon_id=None,
            bioclip=_c("brown_thrasher", 0.5275, True),
            note="Real person+dog passage per person-background-false-positive-attribution-v1-report.md; "
            "subject not independently visually confirmed at full-frame scale by this script.",
        )
    )
    cases.append(
        RunCase(
            case_id="visit-140-person-dog",
            image_path=REPO_ROOT / "data/media/imports/media-asset-140-live-motion-best-frame.jpg",
            tier="full_frame",
            expected_taxon_id=None,
            bioclip=_c("red_bellied_woodpecker", 0.5986, True),
            note="Same real passage, second tracklet; subject not independently visually confirmed "
            "at full-frame scale by this script.",
        )
    )
    return tuple(cases)


def run(*, model_dir: Path, output: Path, skip_missing: bool) -> int:
    cases = build_cases()
    available: list[RunCase] = []
    missing: list[str] = []
    for case in cases:
        if case.image_path.exists():
            available.append(case)
        else:
            missing.append(f"{case.case_id}: {case.image_path}")
    if missing and not skip_missing:
        print("Missing source images (real evidence unreachable on this host):", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        print("Re-run with --skip-missing to proceed with only the reachable subset.", file=sys.stderr)
        return 2
    if missing:
        print(f"Skipping {len(missing)} case(s) with unreachable source images:", file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)

    # Import here, not at module scope: this is the one place a real,
    # optional, heavy model runtime is touched, matching the repository's
    # established "lazy import inside the execution path" convention for
    # every other optional model adapter.
    import PIL.Image
    from speciesnet import SpeciesNetClassifier
    from speciesnet.utils import BBox

    print(f"Loading real local SpeciesNet classifier from {model_dir} ...", file=sys.stderr)
    load_start = time.monotonic()
    classifier = SpeciesNetClassifier(model_name=str(model_dir))
    load_seconds = time.monotonic() - load_start
    print(f"Loaded in {load_seconds:.2f}s on {classifier.device}.", file=sys.stderr)

    results: list[dict] = []
    per_case_latency_ms: list[float] = []
    for case in available:
        img = PIL.Image.open(case.image_path).convert("RGB")
        bboxes = None
        if case.detector_box_xyxy is not None:
            left, top, right, bottom = case.detector_box_xyxy
            bboxes = [BBox(xmin=left, ymin=top, width=right - left, height=bottom - top)]
        pre = classifier.preprocess(img, bboxes=bboxes, resize=True)
        t0 = time.monotonic()
        raw = classifier.predict(str(case.image_path), pre)
        per_case_latency_ms.append((time.monotonic() - t0) * 1000.0)
        classes = raw["classifications"]["classes"]
        scores = raw["classifications"]["scores"]
        prediction = SpeciesNetPrediction(
            case_id=case.case_id, top5_labels=tuple(classes), top5_scores=tuple(scores)
        )
        comparison = compare_case(
            case_id=case.case_id,
            prediction=prediction,
            bioclip=case.bioclip,
            expected_taxon_id=case.expected_taxon_id,
        )
        results.append(
            {
                "case_id": case.case_id,
                "tier": case.tier,
                "expected_taxon_id": case.expected_taxon_id,
                "note": case.note,
                "speciesnet_top5": [
                    {"label": label, "score": score} for label, score in zip(classes, scores)
                ],
                "speciesnet_top1_common_name": comparison.speciesnet_top1_common_name,
                "speciesnet_top1_score": comparison.speciesnet_top1_score,
                "speciesnet_agreement": comparison.speciesnet_agreement,
                "bioclip_top1_label": comparison.bioclip_top1_label,
                "bioclip_top1_score": comparison.bioclip_top1_score,
                "bioclip_abstained": comparison.bioclip_abstained,
                "speciesnet_correct": comparison.speciesnet_correct,
                "bioclip_correct": comparison.bioclip_correct,
                "verdict": comparison.verdict,
            }
        )
        print(
            f"[{comparison.verdict:24s}] {case.case_id}: "
            f"speciesnet={comparison.speciesnet_top1_common_name!r} "
            f"({comparison.speciesnet_top1_score:.3f}, {comparison.speciesnet_agreement}) "
            f"vs bioclip={comparison.bioclip_top1_label!r} "
            f"({comparison.bioclip_top1_score:.3f}, abstained={comparison.bioclip_abstained})",
            file=sys.stderr,
        )

    comparisons = tuple(
        compare_case(
            case_id=r["case_id"],
            prediction=SpeciesNetPrediction(
                case_id=r["case_id"],
                top5_labels=tuple(x["label"] for x in r["speciesnet_top5"]),
                top5_scores=tuple(x["score"] for x in r["speciesnet_top5"]),
            ),
            bioclip=BioClipComparisonPoint(
                top1_label=r["bioclip_top1_label"],
                top1_score=r["bioclip_top1_score"],
                abstained=r["bioclip_abstained"],
            ),
            expected_taxon_id=r["expected_taxon_id"],
        )
        for r in results
    )
    summary = summarize_cases(comparisons)
    report = {
        "schema_version": 1,
        "candidate": "speciesnet-v4.0.3a-classifier-only",
        "model_dir": str(model_dir),
        "n_cases_available": len(available),
        "n_cases_missing": len(missing),
        "missing_cases": missing,
        "model_load_seconds": round(load_seconds, 3),
        "median_inference_ms": (
            sorted(per_case_latency_ms)[len(per_case_latency_ms) // 2] if per_case_latency_ms else None
        ),
        "summary": summary,
        "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nWrote {output}", file=sys.stderr)
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-missing", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(model_dir=args.model_dir, output=args.output, skip_missing=args.skip_missing))


if __name__ == "__main__":
    main()
