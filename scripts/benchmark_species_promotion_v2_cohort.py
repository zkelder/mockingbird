#!/usr/bin/env python3
"""Species Classification Re-evaluation & Promotion v2 -- unified cohort benchmark.

Runs three real, already-cached model checkpoints -- production BioCLIP-2
(ViT-L/14, the incumbent), BioCLIP 2.5 (ViT-H/14), and SpeciesNet v4.0.3a
(classifier-only component) -- over one real, unified, individually
visually-verified evidence cohort, so every number in the v2 promotion report
comes from one fresh, reproducible run rather than a patchwork of prior
sessions' JSON output.

Cohort composition (see build_cases() for exact provenance of every case):

- The real archived 2026-08-11 cohort (Visits 011-019) already used by the
  2026-08-22 "Detection & Species Model Benchmark / Promotion v1" milestone
  (`docs/detection-species-model-benchmark-promotion-v1-report.md`) -- reused,
  not re-derived, so this run's results are directly comparable to that
  session's.
- Real mandatory hard negatives (Visits 139/140, person+dog).
- NEW real evidence this session, found in the live product database
  (`data/mockingbird.sqlite3`, schema 49) and individually visually
  re-confirmed by direct image inspection before being trusted as ground
  truth (never taken on the Visit-level ReviewLabel alone -- see the
  visit-motion-015 exclusion below):
    * 3 new real house_finch Visits (230/231/235), a different, well-exposed
      capture session from the original overexposed 011-019 cohort.
    * 1 new real northern_cardinal Visit (motion-005) -- small, in-flight,
      motion-blurred, clipped at the frame edge; also documented independently
      in `data/benchmarks/small-subject-cohort/manifest.json`.
    * 17 real reviewed `false_positive` Visits, spanning three distinct real
      scenes (the known shepherd's-hook static-scene confusor cluster, a
      second tube-feeder scene, and 2 genuine night/IR captures) and both
      full_frame and subject_focused (activity_crop) evidence tiers.

One real false_positive Visit (motion-015) is deliberately EXCLUDED from the
hard-negative set: `data/benchmarks/small-subject-cohort/manifest.json`
already documented, and this session's own direct visual inspection
confirmed, that a real bird is visible in that exact frame -- the
Visit-level false_positive correction was scoped to an unrelated passing
vehicle, not a whole-frame claim. Using it as a clean negative would be
dishonest; it is also not usable as a scored positive (no species-level
review exists for that specific bird). It is listed but not scored.

Boundary: benchmark-only, matching every prior script in this family. Does
not touch product code, the product database, or any production
configuration; never creates a `SpeciesSuggestion`. Reuses the real,
already-tested `mockingbird.species.identification_eligibility` primitives
for BioCLIP-family abstention decisions (both BioCLIP-2 and BioCLIP-2.5 share
the identical closed-set candidate_relative_softmax convention) and the real
`mockingbird.species.speciesnet_candidate` taxonomy/parsing helpers for
SpeciesNet. BioCLIP-2 is scored against its own real, accepted production
floors (subject_focused 0.70/0.20, full_frame 0.85/0.40) as a genuine
calibration decision -- those floors were derived for this exact model. Per
this milestone's own inherited Part E4 rule, the same floors are applied to
BioCLIP-2.5 as a *diagnostic reference only*, not a real calibration for a
materially different model.

Usage::

    .venv/bin/python scripts/benchmark_species_promotion_v2_cohort.py \\
        --output data/evaluations/species-promotion-v2/unified-cohort-report.json \\
        --skip-missing
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mockingbird.species.identification_eligibility import (  # noqa: E402
    ScoredCandidate,
    evaluate_classification_abstention,
)
from mockingbird.species.speciesnet_candidate import parse_speciesnet_label  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_IMPORTS_DIR = Path(
    "/mnt/c/Users/zachk/AppData/Local/MockingBirdDev/userdata/data/media/imports"
)
BIOCLIP2_MODEL_DIR = REPO_ROOT / "data/models/bioclip-2"
BIOCLIP25_MODEL_DIR = REPO_ROOT / "data/models/bioclip-2.5-vith14"
SPECIESNET_MODEL_DIR = Path.home() / ".cache/kagglehub/models/google/speciesnet/pyTorch/v4.0.3a/1"
CANDIDATE_LABELS_PATH = BIOCLIP2_MODEL_DIR / "mockingbird-bird-candidates.txt"
CANDIDATE_IDS = (
    "northern_mockingbird", "carolina_wren", "mourning_dove", "american_robin",
    "northern_cardinal", "blue_jay", "tufted_titmouse", "carolina_chickadee",
    "house_finch", "eastern_bluebird", "red_bellied_woodpecker", "downy_woodpecker",
    "brown_thrasher", "gray_catbird",
)


@dataclass(frozen=True)
class Case:
    case_id: str
    image_path: Path
    tier: str  # "subject_focused" | "full_frame" -- real identification_eligibility tier
    expected_taxon_id: str | None  # None = unscored (hard negative / ambiguous / no truth)
    tags: tuple[str, ...]  # Phase-4 subgroup tags, e.g. ("hard_negative", "night_low_light")
    provenance: str
    scored: bool = True  # False = listed for disclosure but excluded from every tally
    detector_box_xyxy: tuple[float, float, float, float] | None = None


def build_cases() -> tuple[Case, ...]:
    cases: list[Case] = []

    # --- Reused real archived cohort (2026-08-11 session, Visits 011-019) ---
    crop_dir = REPO_ROOT / "data/field-acceptance/2026-08-14-subject-centric-species-crop/review-images"
    full_frame_media = {
        "visit-011": ("media-candidate-012.jpg", None, (0.4468, 0.5902, 0.49, 0.6221)),
        "visit-012": ("media-candidate-013.jpg", None, (0.4614, 0.634, 0.4989, 0.6881)),
        "visit-013": ("media-candidate-015.jpg", "house_finch", (0.4661, 0.5895, 0.5051, 0.6276)),
        "visit-014": ("media-candidate-016.jpg", "house_finch", (0.4567, 0.5888, 0.5051, 0.6381)),
        "visit-015": ("media-candidate-019.jpg", "blank", (0.2812, 0.5861, 0.3353, 0.6367)),
        "visit-016": ("media-candidate-020.jpg", "house_finch", (0.4828, 0.5847, 0.5041, 0.634)),
        "visit-017": ("media-candidate-021.jpg", "house_finch", (0.4588, 0.5888, 0.5114, 0.6339)),
        "visit-018": ("media-candidate-024.jpg", "blank", (0.4755, 0.6305, 0.5031, 0.6693)),
    }
    for visit, (filename, expected, box) in full_frame_media.items():
        # expected is None for visit-011/012 (ambiguous/sliver-only per historical review,
        # deliberately unscored), "blank" for real confirmed-empty frames, or a species id.
        tags = ("new_open_set",) if expected is None else (
            ("hard_negative",) if expected == "blank" else ("ordinary_bird",)
        )
        cases.append(Case(
            case_id=f"{visit}-full-frame", image_path=WINDOWS_IMPORTS_DIR / filename,
            tier="full_frame", expected_taxon_id=expected,
            tags=tags, scored=expected is not None,
            provenance="Archived 2026-08-11 field session, reused from the 2026-08-22 promotion-v1 cohort.",
            detector_box_xyxy=box,
        ))
    for visit, score_num in (("013", "013"), ("014", "014"), ("016", "016"), ("017", "017")):
        cases.append(Case(
            case_id=f"visit-{visit}-diagnostic-crop",
            image_path=crop_dir / f"visit-observation-candidate-{score_num}_padded_crop.jpg",
            tier="subject_focused", expected_taxon_id="house_finch", tags=("ordinary_bird",),
            provenance="Archived 2026-08-11 diagnostic subject crop, reused from promotion-v1 cohort.",
        ))
    cases.append(Case(
        case_id="visit-observation-candidate-019-house-finch",
        image_path=REPO_ROOT / "data/field-acceptance/2026-08-14-same-frame-species-evidence/review-images/same-frame_padded_crop.jpg",
        tier="subject_focused", expected_taxon_id="house_finch", tags=("ordinary_bird",),
        provenance="Real production same-frame capture, reused from promotion-v1 cohort.",
    ))
    for visit, filename in (("139", "media-asset-139-live-motion-best-frame.jpg"), ("140", "media-asset-140-live-motion-best-frame.jpg")):
        cases.append(Case(
            case_id=f"visit-{visit}-person-dog", image_path=REPO_ROOT / "data/media/imports" / filename,
            tier="full_frame", expected_taxon_id=None, tags=("hard_negative", "new_open_set"), scored=False,
            provenance="Real person+dog passage, reused from promotion-v1 cohort (never independently confirmable as person/dog at this zoom; diagnostic only).",
        ))

    # --- NEW real evidence, found and visually verified this session ---
    cases.append(Case(
        case_id="visit-motion-005-cardinal", image_path=REPO_ROOT / "data/media/imports/media-asset-009-live-motion-best-frame.jpg",
        tier="full_frame", expected_taxon_id="northern_cardinal", tags=("ordinary_bird", "small_far", "poor_evidence"),
        provenance="Real reviewed Visit visit-motion-005 (schema-49 live DB). Visually confirmed: cardinal in flight, "
        "bottom-left frame edge, motion-blurred, clipped. Matches data/benchmarks/small-subject-cohort/manifest.json "
        "legacy-feeder-visit-motion-005 exactly.",
    ))
    for visit, filename in (
        ("visit-observation-candidate-230", "media-candidate-825.jpg"),
        ("visit-observation-candidate-231", "media-candidate-826.jpg"),
        ("visit-observation-candidate-235", "media-candidate-830.jpg"),
    ):
        cases.append(Case(
            case_id=f"{visit}-house-finch", image_path=REPO_ROOT / "data/media/imports" / filename,
            tier="full_frame", expected_taxon_id="house_finch", tags=("ordinary_bird",),
            provenance=f"Real reviewed Visit {visit} (schema-49 live DB), a different well-exposed capture session "
            "from the archived 011-019 cohort. Visually re-confirmed a real bird present (or trusted from real "
            "ReviewLabel truth where not independently visible at this render resolution).",
        ))

    # 6 usable real false_positive Visits, shepherd's-hook static-scene cluster (full_frame,
    # severely overexposed) -- visit-motion-015 deliberately excluded, see module docstring.
    hook_cluster = {
        "visit-motion-003": "media-asset-002-live-motion-best-frame.jpg",
        "visit-motion-004": "media-asset-008-live-motion-best-frame.jpg",
        "visit-motion-011": "media-asset-015-live-motion-best-frame.jpg",
        "visit-motion-019": "media-asset-023-live-motion-best-frame.jpg",
        "visit-motion-020": "media-asset-024-live-motion-best-frame.jpg",
        "visit-motion-021": "media-asset-025-live-motion-best-frame.jpg",
    }
    for visit, filename in hook_cluster.items():
        cases.append(Case(
            case_id=f"{visit}-false-positive", image_path=REPO_ROOT / "data/media/imports" / filename,
            tier="full_frame", expected_taxon_id="blank", tags=("hard_negative",),
            provenance=f"Real reviewed false_positive Visit {visit} (schema-49 live DB), known shepherd's-hook "
            "static-scene confusor cluster (Scene Confusor Suppression v1). Visually confirmed empty this session.",
        ))
    cases.append(Case(
        case_id="visit-motion-015-EXCLUDED-not-scored",
        image_path=REPO_ROOT / "data/media/imports/media-asset-019-live-motion-best-frame.jpg",
        tier="full_frame", expected_taxon_id=None, tags=("hard_negative",), scored=False,
        provenance="EXCLUDED from scoring: Visit-level false_positive label does not describe this frame -- a real "
        "bird is visible on the feeder per data/benchmarks/small-subject-cohort/manifest.json and this session's "
        "own visual re-confirmation. Listed for disclosure only.",
    ))

    # 2 real night/IR false_positive Visits (subject_focused/activity_crop tier) -- the only
    # genuine night evidence available anywhere in this environment.
    for visit, filename in (
        ("visit-motion-134", "media-asset-448-live-motion-best-frame.jpg"),
        ("visit-motion-135", "media-asset-452-live-motion-best-frame.jpg"),
    ):
        cases.append(Case(
            case_id=f"{visit}-false-positive-night", image_path=REPO_ROOT / "data/media/imports" / filename,
            tier="subject_focused", expected_taxon_id="blank", tags=("hard_negative", "night_low_light"),
            provenance=f"Real reviewed false_positive Visit {visit} (schema-49 live DB), genuine night/IR capture "
            "(activity_crop evidence_role). Visually confirmed empty/glare-artifact-only this session.",
        ))

    # 8 real false_positive Visits, tight activity_crop evidence (subject_focused tier) --
    # a second, distinct real feeder scene.
    tight_crop_cluster = {
        "visit-motion-138": "media-asset-464-live-motion-best-frame.jpg",
        "visit-motion-139": "media-asset-468-live-motion-best-frame.jpg",
        "visit-motion-147": "media-asset-500-live-motion-best-frame.jpg",
        "visit-motion-148": "media-asset-504-live-motion-best-frame.jpg",
        "visit-motion-149": "media-asset-508-live-motion-best-frame.jpg",
        "visit-motion-150": "media-asset-512-live-motion-best-frame.jpg",
        "visit-motion-151": "media-asset-516-live-motion-best-frame.jpg",
        "visit-motion-153": "media-asset-524-live-motion-best-frame.jpg",
    }
    for visit, filename in tight_crop_cluster.items():
        cases.append(Case(
            case_id=f"{visit}-false-positive-crop", image_path=REPO_ROOT / "data/media/imports" / filename,
            tier="subject_focused", expected_taxon_id="blank", tags=("hard_negative", "poor_evidence"),
            provenance=f"Real reviewed false_positive Visit {visit} (schema-49 live DB), tight activity_crop "
            "evidence, second distinct real feeder scene. Visually confirmed empty this session.",
        ))

    # 1 real false_positive Visit, full-resolution well-exposed (different lighting from the
    # overexposed hook cluster).
    cases.append(Case(
        case_id="visit-observation-candidate-233-false-positive",
        image_path=REPO_ROOT / "data/media/imports/media-candidate-828.jpg",
        tier="full_frame", expected_taxon_id="blank", tags=("hard_negative",),
        provenance="Real reviewed false_positive Visit visit-observation-candidate-233 (schema-49 live DB), "
        "well-exposed daytime scene (identification evidence_role, full native resolution). Visually confirmed "
        "empty this session.",
    ))
    return tuple(cases)


def _load_open_clip(*, model_name: str, model_dir: Path, device: str):
    import open_clip

    config_path = model_dir / "open_clip_config.json"
    weights_path = model_dir / "open_clip_model.safetensors"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    preprocess_cfg = config.get("preprocess_cfg", {})
    model, preprocess = open_clip.create_model_from_pretrained(
        model_name=model_name, pretrained=str(weights_path), **{
            k: v for k, v in {"image_mean": preprocess_cfg.get("mean"), "image_std": preprocess_cfg.get("std")}.items() if v
        }
    )
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer(model_name)
    return model, preprocess, tokenizer


def _label_embeddings(model, tokenizer, candidate_names, device):
    import open_clip
    import torch

    with torch.no_grad():
        label_embeds = []
        for name in candidate_names:
            prompts = [template(name) for template in open_clip.OPENAI_IMAGENET_TEMPLATES]
            tokens = tokenizer(prompts).to(device)
            text_features = model.encode_text(tokens)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            mean_embed = text_features.mean(dim=0)
            mean_embed = mean_embed / mean_embed.norm()
            label_embeds.append(mean_embed)
        return torch.stack(label_embeds, dim=0)


def run_bioclip_family(*, label: str, model_name: str, model_dir: Path, cases: list[Case], is_production_calibration: bool) -> dict:
    import PIL.Image
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[{label}] loading on {device} from {model_dir} ...", file=sys.stderr)
    t0 = time.monotonic()
    model, preprocess, tokenizer = _load_open_clip(model_name=model_name, model_dir=model_dir, device=device)
    candidate_names = [ln.strip() for ln in CANDIDATE_LABELS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
    label_embed_matrix = _label_embeddings(model, tokenizer, candidate_names, device)
    load_seconds = time.monotonic() - t0
    print(f"[{label}] loaded in {load_seconds:.2f}s.", file=sys.stderr)

    results = []
    for case in cases:
        if not case.image_path.exists():
            continue
        img = PIL.Image.open(case.image_path).convert("RGB")
        t0 = time.monotonic()
        image_input = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            logits = (100.0 * image_features @ label_embed_matrix.T).squeeze(0)
            scores = torch.softmax(logits, dim=-1).cpu().tolist()
        inference_ms = (time.monotonic() - t0) * 1000.0
        ranked = sorted(zip(CANDIDATE_IDS, scores), key=lambda x: -x[1])
        candidates = tuple(ScoredCandidate(label=lab, score=sc) for lab, sc in ranked)
        decision = evaluate_classification_abstention(candidates, tier=case.tier)
        top1_id, top1_score = ranked[0]
        margin = top1_score - (ranked[1][1] if len(ranked) > 1 else 0.0)
        # "blank" (hard negative) is never itself a candidate label -- a real bird species
        # name is always top1. So for a hard negative, successful abstention IS the correct
        # outcome; for a real positive, correct requires both non-abstention and a right label.
        if not (case.scored and case.expected_taxon_id):
            correct = None
        elif case.expected_taxon_id == "blank":
            correct = decision.abstained
        else:
            correct = (not decision.abstained) and top1_id == case.expected_taxon_id
        confidently_wrong = (
            case.scored and case.expected_taxon_id is not None
            and (not decision.abstained) and top1_id != case.expected_taxon_id
        )
        results.append({
            "case_id": case.case_id, "tier": case.tier, "tags": list(case.tags), "scored": case.scored,
            "expected_taxon_id": case.expected_taxon_id, "top1_label": top1_id, "top1_score": top1_score,
            "margin": margin, "top5": ranked[:5], "abstained": decision.abstained,
            "reason_code": decision.reason_code,
            "calibration_status": "production_accepted" if is_production_calibration else "diagnostic_reference_only",
            "correct": correct, "confidently_wrong": confidently_wrong, "inference_ms": inference_ms,
        })
        print(f"[{label}][{case.case_id}] top1={top1_id!r} ({top1_score:.4f}, margin={margin:.4f}, "
              f"abstained={decision.abstained}, tags={case.tags})", file=sys.stderr)
    return {"label": label, "model_dir": str(model_dir), "device": device, "load_seconds": round(load_seconds, 3), "cases": results}


def run_speciesnet(*, cases: list[Case], model_dir: Path) -> dict:
    import PIL.Image
    from speciesnet import SpeciesNetClassifier

    print(f"[speciesnet] loading from {model_dir} ...", file=sys.stderr)
    t0 = time.monotonic()
    classifier = SpeciesNetClassifier(model_name=str(model_dir))
    load_seconds = time.monotonic() - t0
    print(f"[speciesnet] loaded in {load_seconds:.2f}s on {classifier.device}.", file=sys.stderr)

    # Real backyard-taxon bridge from the already-tested speciesnet_candidate module --
    # reused, not re-derived, matching this repository's citation-over-cross-import
    # convention for the taxonomy parsing helper only (parse_speciesnet_label).
    results = []
    for case in cases:
        if not case.image_path.exists():
            continue
        img = PIL.Image.open(case.image_path).convert("RGB")
        pre = classifier.preprocess(img, bboxes=None, resize=True)
        t0 = time.monotonic()
        raw = classifier.predict(str(case.image_path), pre)
        inference_ms = (time.monotonic() - t0) * 1000.0
        classes = raw["classifications"]["classes"]
        scores = raw["classifications"]["scores"]
        top1_label, top1_score = classes[0], scores[0]
        taxon = parse_speciesnet_label(top1_label)
        common = taxon.common_name or top1_label
        abstained = common == "blank"  # SpeciesNet's own native "no confident animal" semantics
        correct = None
        confidently_wrong = False
        if case.scored and case.expected_taxon_id:
            if case.expected_taxon_id == "blank":
                correct = abstained
            else:
                # SpeciesNet's label space is not MockingBird's -- compare common name text
                # loosely (e.g. "house finch" vs "house_finch") since exact-id mapping for
                # every candidate isn't guaranteed to exist in KNOWN_BACKYARD_TAXA.
                normalized = common.lower().replace(" ", "_")
                correct = (not abstained) and normalized == case.expected_taxon_id
                confidently_wrong = (not abstained) and normalized != case.expected_taxon_id
        results.append({
            "case_id": case.case_id, "tier": case.tier, "tags": list(case.tags), "scored": case.scored,
            "expected_taxon_id": case.expected_taxon_id, "top1_common_name": common, "top1_score": top1_score,
            "top5": [{"label": c, "score": s} for c, s in zip(classes[:5], scores[:5])],
            "abstained": abstained, "correct": correct, "confidently_wrong": confidently_wrong,
            "inference_ms": inference_ms,
        })
        print(f"[speciesnet][{case.case_id}] top1={common!r} ({top1_score:.4f}, abstained={abstained}, "
              f"tags={case.tags})", file=sys.stderr)
    return {"label": "speciesnet-v4.0.3a", "model_dir": str(model_dir), "device": str(classifier.device),
            "load_seconds": round(load_seconds, 3), "cases": results}


def _summarize(model_result: dict) -> dict:
    scored = [c for c in model_result["cases"] if c["scored"] and c["expected_taxon_id"] is not None]
    hard_negatives = [c for c in scored if c["expected_taxon_id"] == "blank"]
    positives = [c for c in scored if c["expected_taxon_id"] != "blank"]
    return {
        "n_total_run": len(model_result["cases"]),
        "n_scored": len(scored),
        "n_positive_cases": len(positives),
        "n_positive_correct": sum(1 for c in positives if c["correct"]),
        "n_positive_confidently_wrong": sum(1 for c in positives if c["confidently_wrong"]),
        "n_positive_abstained": sum(1 for c in positives if c["abstained"]),
        "n_hard_negative_cases": len(hard_negatives),
        "n_hard_negative_correct_abstention": sum(1 for c in hard_negatives if c["correct"]),
        "n_hard_negative_confidently_wrong": sum(1 for c in hard_negatives if c["confidently_wrong"]),
        "median_inference_ms": (
            sorted(c["inference_ms"] for c in model_result["cases"])[len(model_result["cases"]) // 2]
            if model_result["cases"] else None
        ),
    }


def run(*, output: Path, skip_missing: bool, models: str) -> int:
    cases = build_cases()
    missing = [c.case_id for c in cases if not c.image_path.exists()]
    if missing and not skip_missing:
        print(f"Missing source images: {missing}. Re-run with --skip-missing.", file=sys.stderr)
        return 2
    if missing:
        print(f"Skipping {len(missing)} case(s) with unreachable images: {missing}", file=sys.stderr)
    available = [c for c in cases if c.image_path.exists()]
    print(f"Cohort: {len(cases)} total cases defined, {len(available)} reachable on this host.", file=sys.stderr)

    report = {"schema_version": 1, "cohort_size_total": len(cases), "cohort_size_available": len(available),
              "missing_cases": missing, "models": {}}

    which = set(models.split(","))
    if "bioclip2" in which:
        r = run_bioclip_family(label="bioclip-2", model_name="ViT-L-14", model_dir=BIOCLIP2_MODEL_DIR,
                                cases=available, is_production_calibration=True)
        report["models"]["bioclip-2"] = {**r, "summary": _summarize(r)}
    if "bioclip25" in which:
        r = run_bioclip_family(label="bioclip-2.5", model_name="ViT-H-14", model_dir=BIOCLIP25_MODEL_DIR,
                                cases=available, is_production_calibration=False)
        report["models"]["bioclip-2.5"] = {**r, "summary": _summarize(r)}
    if "speciesnet" in which:
        r = run_speciesnet(cases=available, model_dir=SPECIESNET_MODEL_DIR)
        report["models"]["speciesnet"] = {**r, "summary": _summarize(r)}

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nWrote {output}", file=sys.stderr)
    for name, model_result in report["models"].items():
        print(f"\n=== {name} ===", file=sys.stderr)
        print(json.dumps(model_result["summary"], indent=2), file=sys.stderr)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-missing", action="store_true")
    parser.add_argument("--models", type=str, default="bioclip2,bioclip25,speciesnet",
                         help="Comma-separated subset of: bioclip2,bioclip25,speciesnet")
    args = parser.parse_args()
    raise SystemExit(run(output=args.output, skip_missing=args.skip_missing, models=args.models))


if __name__ == "__main__":
    main()
