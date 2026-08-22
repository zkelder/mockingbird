#!/usr/bin/env python3
"""Detection & Species Model Benchmark / Promotion v1 -- BioCLIP 2.5 (ViT-H/14) run.

Runs the real, official `imageomics/bioclip-2.5-vith14` checkpoint (released
February 2026, OpenCLIP ViT-H/14 pretrained on the expanded TreeOfLife-200M --
a materially newer/larger BioCLIP-family release than the production
BioCLIP-2 ViT-L/14 incumbent, confirmed via a real web search, not assumed)
against the exact same real cohort used for the SpeciesNet candidate run and
already recorded for production BioCLIP-2, for a genuine three-way
comparison. Reuses the real, standard "OpenAI ImageNet 80-template" prompt
ensemble (`open_clip.OPENAI_IMAGENET_TEMPLATES`) that BioCLIP's own recorded
`BIOCLIP_PROMPT_RECIPE_ID = "pybioclip-openai-imagenet-80-template-v1"` names
-- the same recipe, not a different one invented for this comparison -- and
the real production candidate-label text (`data/models/bioclip-2/mockingbird-
bird-candidates.txt`) so the label space is identical to the incumbent's.

Boundary: benchmark-only. Does not touch product code, the product database,
or any production configuration; never creates a `SpeciesSuggestion`. This
script downloads real weights (~4 GB) via `huggingface_hub` -- an explicit,
one-time, manually-invoked benchmark action, not an automatic production
download (the existing `classifier-bioclip` extra/adapter never does this).
Reuses the existing, tested `mockingbird.species.identification_eligibility`
scoring/abstention primitives directly rather than reinventing scoring, since
BioCLIP 2.5 is scored with the identical closed-set candidate-relative-
softmax convention as the incumbent -- unlike SpeciesNet's open taxonomy,
no new comparison module is needed here.

Usage::

    .venv/bin/python scripts/benchmark_bioclip25_candidate.py \\
        --model-dir data/models/bioclip-2.5-vith14 \\
        --output data/evaluations/species-promotion-v1/bioclip25-report.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mockingbird.species.identification_eligibility import (  # noqa: E402
    ScoredCandidate,
    evaluate_classification_abstention,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_IMPORTS_DIR = Path(
    "/mnt/c/Users/zachk/AppData/Local/MockingBirdDev/userdata/data/media/imports"
)
CANDIDATE_LABELS_PATH = REPO_ROOT / "data/models/bioclip-2/mockingbird-bird-candidates.txt"
# Real production id order, matching BUILTIN_SPECIES_CANDIDATE_TAXONOMY_IDS in
# product_repository.py -- same order as the real candidate-label text file.
CANDIDATE_IDS = (
    "northern_mockingbird", "carolina_wren", "mourning_dove", "american_robin",
    "northern_cardinal", "blue_jay", "tufted_titmouse", "carolina_chickadee",
    "house_finch", "eastern_bluebird", "red_bellied_woodpecker", "downy_woodpecker",
    "brown_thrasher", "gray_catbird",
)


def build_cases() -> tuple[dict, ...]:
    """Same real cases/expected taxa as scripts/benchmark_speciesnet_candidate.py's
    subject-focused cohort (the fair, product-realistic comparison point --
    already-cropped real subject images) plus the same full-frame cohort, so
    all three models (BioCLIP-2, SpeciesNet, BioCLIP-2.5) are scored on
    identical real inputs. Real image paths and expected taxa are duplicated
    deliberately (not imported cross-script) matching this repository's own
    citation-over-cross-import convention for benchmark scripts.
    """
    crop_dir = REPO_ROOT / "data/field-acceptance/2026-08-14-subject-centric-species-crop/review-images"
    cases = [
        {
            "case_id": f"visit-{num}-diagnostic-crop", "tier": "subject_focused",
            "image_path": crop_dir / f"visit-observation-candidate-{num}_padded_crop.jpg",
            "expected_taxon_id": "house_finch",
            "bioclip2_top1_label": "house_finch", "bioclip2_top1_score": score,
        }
        for num, score in (("013", 0.998), ("014", 0.997), ("016", 0.999), ("017", 0.925))
    ]
    cases.append({
        "case_id": "visit-observation-candidate-019-house-finch", "tier": "subject_focused",
        "image_path": REPO_ROOT
        / "data/field-acceptance/2026-08-14-same-frame-species-evidence/review-images/same-frame_padded_crop.jpg",
        "expected_taxon_id": "house_finch",
        "bioclip2_top1_label": "house_finch", "bioclip2_top1_score": 0.9374827742576599,
    })
    full_frame = {
        "visit-011": ("media-candidate-012.jpg", None, "red_bellied_woodpecker", 0.796),
        "visit-012": ("media-candidate-013.jpg", None, "red_bellied_woodpecker", 0.817),
        "visit-013": ("media-candidate-015.jpg", "house_finch", "red_bellied_woodpecker", 0.616),
        "visit-014": ("media-candidate-016.jpg", "house_finch", "tufted_titmouse", 0.369),
        "visit-015": ("media-candidate-019.jpg", "blank", "red_bellied_woodpecker", 0.529),
        "visit-016": ("media-candidate-020.jpg", "house_finch", "red_bellied_woodpecker", 0.645),
        "visit-017": ("media-candidate-021.jpg", "house_finch", "red_bellied_woodpecker", 0.779),
        "visit-018": ("media-candidate-024.jpg", "blank", "red_bellied_woodpecker", 0.338),
    }
    for visit, (filename, expected, bc2_label, bc2_score) in full_frame.items():
        cases.append({
            "case_id": f"{visit}-full-frame", "tier": "full_frame",
            "image_path": WINDOWS_IMPORTS_DIR / filename,
            "expected_taxon_id": expected,
            "bioclip2_top1_label": bc2_label, "bioclip2_top1_score": bc2_score,
        })
    # Real mandatory hard negatives (Visits 139/140) -- same real images used by
    # scripts/benchmark_speciesnet_candidate.py's cohort A. Both models share
    # the identical closed, bird-only 14-label space, so neither can ever
    # output "person"/"dog"/"blank" here; expected_taxon_id stays None
    # (diagnostic-only, not independently visually confirmable at full-frame
    # scale) -- what matters is *whether a materially larger backbone is any
    # more or less prone to a high-confidence forced bird guess* on the same
    # real non-bird evidence, not a right/wrong score.
    cases.append({
        "case_id": "visit-139-person-dog", "tier": "full_frame",
        "image_path": REPO_ROOT / "data/media/imports/media-asset-139-live-motion-best-frame.jpg",
        "expected_taxon_id": None,
        "bioclip2_top1_label": "brown_thrasher", "bioclip2_top1_score": 0.5275,
    })
    cases.append({
        "case_id": "visit-140-person-dog", "tier": "full_frame",
        "image_path": REPO_ROOT / "data/media/imports/media-asset-140-live-motion-best-frame.jpg",
        "expected_taxon_id": None,
        "bioclip2_top1_label": "red_bellied_woodpecker", "bioclip2_top1_score": 0.5986,
    })
    return tuple(cases)


def run(*, model_dir: Path, output: Path, skip_missing: bool) -> int:
    if not CANDIDATE_LABELS_PATH.exists():
        print(f"Real candidate-label file not found: {CANDIDATE_LABELS_PATH}", file=sys.stderr)
        return 2
    candidate_names = [
        line.strip() for line in CANDIDATE_LABELS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    if len(candidate_names) != len(CANDIDATE_IDS):
        print("candidate_names/CANDIDATE_IDS length mismatch -- refusing to guess an id mapping.", file=sys.stderr)
        return 2

    cases = build_cases()
    available = [c for c in cases if c["image_path"].exists()]
    missing = [c["case_id"] for c in cases if not c["image_path"].exists()]
    if missing and not skip_missing:
        print(f"Missing source images: {missing}. Re-run with --skip-missing.", file=sys.stderr)
        return 2
    if missing:
        print(f"Skipping {len(missing)} case(s) with unreachable images: {missing}", file=sys.stderr)

    import open_clip
    import PIL.Image
    import torch

    config_path = model_dir / "open_clip_config.json"
    weights_path = model_dir / "open_clip_model.safetensors"
    if not weights_path.exists():
        print(f"Real weights not found at {weights_path} -- download first.", file=sys.stderr)
        return 2
    config = json.loads(config_path.read_text(encoding="utf-8"))
    model_cfg = config.get("model_cfg", config)
    preprocess_cfg = config.get("preprocess_cfg", {})

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading real BioCLIP 2.5 (ViT-H/14) on {device} from {model_dir} ...", file=sys.stderr)
    t0 = time.monotonic()
    model, preprocess = open_clip.create_model_from_pretrained(
        model_name="ViT-H-14", pretrained=str(weights_path), **{
            k: v for k, v in {"image_mean": preprocess_cfg.get("mean"), "image_std": preprocess_cfg.get("std")}.items()
            if v
        }
    )
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer("ViT-H-14")
    load_seconds = time.monotonic() - t0
    print(f"Loaded in {load_seconds:.2f}s.", file=sys.stderr)

    # Real "OpenAI ImageNet 80-template" ensemble -- the same recipe named by
    # BIOCLIP_PROMPT_RECIPE_ID in the production adapter, applied here with
    # BioCLIP 2.5's own tokenizer/encoder (never mixing embeddings from two
    # different model checkpoints).
    print("Building candidate-label text embeddings (80-template ensemble)...", file=sys.stderr)
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
        label_embed_matrix = torch.stack(label_embeds, dim=0)  # [14, D]

    results = []
    for case in available:
        img = PIL.Image.open(case["image_path"]).convert("RGB")
        image_input = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            image_features = model.encode_image(image_input)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            logits = (100.0 * image_features @ label_embed_matrix.T).squeeze(0)
            scores = torch.softmax(logits, dim=-1).cpu().tolist()
        ranked = sorted(zip(CANDIDATE_IDS, scores), key=lambda x: -x[1])
        candidates = tuple(ScoredCandidate(label=label, score=score) for label, score in ranked)
        decision = evaluate_classification_abstention(candidates, tier=case["tier"])
        top1_id, top1_score = ranked[0]
        correct = (not decision.abstained) and top1_id == case["expected_taxon_id"] if case["expected_taxon_id"] else None
        bioclip2_correct = (
            case["bioclip2_top1_label"] == case["expected_taxon_id"] if case["expected_taxon_id"] else None
        )
        results.append({
            "case_id": case["case_id"], "tier": case["tier"], "expected_taxon_id": case["expected_taxon_id"],
            "bioclip25_top5": ranked[:5], "bioclip25_top1_score": top1_score,
            "bioclip25_abstained": decision.abstained, "bioclip25_reason_code": decision.reason_code,
            "bioclip25_correct": correct,
            "bioclip2_top1_label": case["bioclip2_top1_label"], "bioclip2_top1_score": case["bioclip2_top1_score"],
            "bioclip2_correct": bioclip2_correct,
        })
        print(
            f"[{case['case_id']}] bioclip2.5 top1={top1_id!r} ({top1_score:.4f}, "
            f"abstained_under_bioclip2_thresholds={decision.abstained}) vs "
            f"bioclip2 top1={case['bioclip2_top1_label']!r} ({case['bioclip2_top1_score']:.4f})",
            file=sys.stderr,
        )

    scored = [r for r in results if r["expected_taxon_id"] is not None]
    summary = {
        "n_total": len(results),
        "n_scored": len(scored),
        "n_bioclip25_correct": sum(1 for r in scored if r["bioclip25_correct"]),
        "n_bioclip2_correct": sum(1 for r in scored if r["bioclip2_correct"]),
        "n_bioclip25_better": sum(1 for r in scored if r["bioclip25_correct"] and not r["bioclip2_correct"]),
        "n_bioclip2_better": sum(1 for r in scored if r["bioclip2_correct"] and not r["bioclip25_correct"]),
        "n_both_correct": sum(1 for r in scored if r["bioclip25_correct"] and r["bioclip2_correct"]),
    }
    report = {
        "schema_version": 1,
        "candidate": "bioclip-2.5-vith14",
        "note": "bioclip25_abstained uses BioCLIP-2's own accepted thresholds as a diagnostic reference point "
        "only -- per this milestone's Part E4 rule, transplanting one model's calibration onto a different "
        "model's raw score distribution is not itself a calibration decision; a genuinely different model "
        "would need its own threshold study before any abstention claim.",
        "model_load_seconds": round(load_seconds, 3),
        "n_cases_missing": len(missing),
        "missing_cases": missing,
        "summary": summary,
        "cases": results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"\nWrote {output}", file=sys.stderr)
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model-dir", type=Path, default=REPO_ROOT / "data/models/bioclip-2.5-vith14")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--skip-missing", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run(model_dir=args.model_dir, output=args.output, skip_missing=args.skip_missing))


if __name__ == "__main__":
    main()
