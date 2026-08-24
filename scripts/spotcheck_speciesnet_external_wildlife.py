#!/usr/bin/env python3
"""Species Classification Re-evaluation & Promotion v2 -- informal, EXTERNAL-DOMAIN
broader-wildlife spot-check.

Not part of the real MockingBird evaluation cohort. This repository and this
environment contain zero real MockingBird-camera mammal photos (independently
confirmed twice this session -- live-DB/filesystem sweep, and Broader Wildlife
Maturity v1's own contract doc). This script exists only to ask a narrower,
honest, clearly-caveated question: on CLEAR, well-lit/well-framed external
camera-trap photos (never MockingBird's own capture domain, never run through
MockingBird's real detector/crop/eligibility pipeline), can SpeciesNet's
open taxonomy structurally recognize common backyard mammals at all? BioCLIP-2
is run alongside only to confirm its known, expected, structural inability
(a closed 14-species BIRD-only candidate pack cannot name a mammal correctly
under any circumstance -- the interesting question is whether it at least
abstains rather than forcing a bird label).

Images are drawn from data/training/wildlife-stage2/ (external camera-trap
corpora: Channel Islands, ENA24 -- real third-party research datasets, not
MockingBird evidence, no MockingBird product truth). Ground truth below is
this session's own direct visual identification, disclosed as such -- these
images carry no per-image species label in the local manifest (it is a
detector-training corpus: animal-or-not, not species-labeled).

This script never touches the wildlife-stage2 training pipeline, the 7
preserved detector files, or product code/database. Read-only, informal,
n=6.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mockingbird.species.identification_eligibility import (  # noqa: E402
    ScoredCandidate,
    evaluate_classification_abstention,
)
from mockingbird.species.speciesnet_candidate import parse_speciesnet_label  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGE2_TRAIN = REPO_ROOT / "data/training/wildlife-stage2/dataset/train"
BIOCLIP2_MODEL_DIR = REPO_ROOT / "data/models/bioclip-2"
SPECIESNET_MODEL_DIR = Path.home() / ".cache/kagglehub/models/google/speciesnet/pyTorch/v4.0.3a/1"
CANDIDATE_IDS = (
    "northern_mockingbird", "carolina_wren", "mourning_dove", "american_robin",
    "northern_cardinal", "blue_jay", "tufted_titmouse", "carolina_chickadee",
    "house_finch", "eastern_bluebird", "red_bellied_woodpecker", "downy_woodpecker",
    "brown_thrasher", "gray_catbird",
)

CASES = [
    ("ena24-5e74cb2ad4e2c9e2d3f5.jpg", "squirrel (fox/gray squirrel, forest floor, daylight)"),
    ("ena24-135a2e2a2115b0f7ba75.jpg", "cat (tabby-striped, long banded tail -> domestic cat, not bobcat, suburban yard)"),
    ("ena24-b0981fa41b7abd6f7823.jpg", "opossum (pointed snout, eyeshine, night IR)"),
    ("ena24-c2db26c514cd4c02a97f.jpg", "chicken x2 (domestic backyard poultry -- off-target for both models)"),
    ("channel-6c24f07864bbf5b4d0e6.jpg", "empty (stream/grass scene, daylight, no animal visible)"),
    ("channel-b0a6e049e70030eb2999.jpg", "empty (rock scene, night IR, no animal visible)"),
]


def run() -> None:
    import PIL.Image
    import torch
    from speciesnet import SpeciesNetClassifier

    print("Loading SpeciesNet...", file=sys.stderr)
    speciesnet = SpeciesNetClassifier(model_name=str(SPECIESNET_MODEL_DIR))

    print("Loading BioCLIP-2...", file=sys.stderr)
    import open_clip
    device = "cuda" if torch.cuda.is_available() else "cpu"
    config = json.loads((BIOCLIP2_MODEL_DIR / "open_clip_config.json").read_text())
    preprocess_cfg = config.get("preprocess_cfg", {})
    model, preprocess = open_clip.create_model_from_pretrained(
        model_name="ViT-L-14", pretrained=str(BIOCLIP2_MODEL_DIR / "open_clip_model.safetensors"),
        **{k: v for k, v in {"image_mean": preprocess_cfg.get("mean"), "image_std": preprocess_cfg.get("std")}.items() if v},
    )
    model = model.to(device).eval()
    tokenizer = open_clip.get_tokenizer("ViT-L-14")
    candidate_names = [ln.strip() for ln in (BIOCLIP2_MODEL_DIR / "mockingbird-bird-candidates.txt").read_text().splitlines() if ln.strip()]
    with torch.no_grad():
        label_embeds = []
        for name in candidate_names:
            prompts = [t(name) for t in open_clip.OPENAI_IMAGENET_TEMPLATES]
            tokens = tokenizer(prompts).to(device)
            tf = model.encode_text(tokens)
            tf = tf / tf.norm(dim=-1, keepdim=True)
            me = tf.mean(dim=0)
            me = me / me.norm()
            label_embeds.append(me)
        label_matrix = torch.stack(label_embeds, dim=0)

    results = []
    for filename, description in CASES:
        path = STAGE2_TRAIN / filename
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        img = PIL.Image.open(path).convert("RGB")

        pre = speciesnet.preprocess(img, bboxes=None, resize=True)
        raw = speciesnet.predict(str(path), pre)
        sn_label = raw["classifications"]["classes"][0]
        sn_score = raw["classifications"]["scores"][0]
        sn_taxon = parse_speciesnet_label(sn_label)
        sn_common = sn_taxon.common_name or sn_label

        image_input = preprocess(img).unsqueeze(0).to(device)
        with torch.no_grad():
            feat = model.encode_image(image_input)
            feat = feat / feat.norm(dim=-1, keepdim=True)
            logits = (100.0 * feat @ label_matrix.T).squeeze(0)
            scores = torch.softmax(logits, dim=-1).cpu().tolist()
        ranked = sorted(zip(CANDIDATE_IDS, scores), key=lambda x: -x[1])
        candidates = tuple(ScoredCandidate(label=lab, score=sc) for lab, sc in ranked)
        decision = evaluate_classification_abstention(candidates, tier="full_frame")

        row = {
            "image": filename, "visual_description": description,
            "speciesnet_top1_common_name": sn_common, "speciesnet_top1_score": sn_score,
            "bioclip2_top1_label": ranked[0][0], "bioclip2_top1_score": ranked[0][1],
            "bioclip2_abstained": decision.abstained,
        }
        results.append(row)
        print(f"[{filename}] ({description})\n"
              f"  speciesnet: {sn_common!r} ({sn_score:.3f})\n"
              f"  bioclip-2:  {ranked[0][0]!r} ({ranked[0][1]:.3f}, abstained={decision.abstained})",
              file=sys.stderr)

    out = REPO_ROOT / "data/evaluations/species-promotion-v2/external-broader-wildlife-spotcheck.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "note": "Informal, external-domain (non-MockingBird) spot-check. Not part of the scored evaluation "
        "cohort. Ground truth is this session's own visual identification of third-party camera-trap "
        "photos, disclosed as such.",
        "n": len(results), "cases": results,
    }, indent=2), encoding="utf-8")
    print(f"\nWrote {out}", file=sys.stderr)


if __name__ == "__main__":
    run()
