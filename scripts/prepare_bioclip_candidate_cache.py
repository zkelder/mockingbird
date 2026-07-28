#!/usr/bin/env python3
"""Prepare a frozen, local-only BioCLIP candidate embedding cache.

This is a one-time desktop setup command. It never downloads a model, reaches a
hub, changes product records, or runs during review. The resulting labels and
cache are local configuration artifacts and should remain outside Git.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import hmac
import json
import os
from pathlib import Path
import sys
import uuid

from mockingbird.species import bioclip_adapter


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one verified local BioCLIP candidate embedding cache."
    )
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--labels-path", type=Path, required=True)
    parser.add_argument("--embedding-cache-path", type=Path, required=True)
    parser.add_argument("--model-weights-sha256", required=True)
    return parser.parse_args()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_digest(value: str) -> str:
    candidate = value.strip().lower()
    if len(candidate) != 64 or any(character not in "0123456789abcdef" for character in candidate):
        raise ValueError("model_weights_sha256 must be a SHA-256 digest.")
    return candidate


def _write_cache(
    *,
    model_dir: Path,
    labels_path: Path,
    output_path: Path,
    expected_weights_sha256: str,
) -> dict[str, object]:
    model_dir = model_dir.expanduser().resolve(strict=True)
    labels_path = labels_path.expanduser().resolve(strict=True)
    output_path = output_path.expanduser()
    model_config_path = model_dir / "open_clip_config.json"
    bioclip_adapter._validate_model_config(model_config_path)
    model_weights_path = bioclip_adapter._find_safe_model_weights(model_dir)
    actual_weights_sha256 = _sha256(model_weights_path)
    if not hmac.compare_digest(actual_weights_sha256, expected_weights_sha256):
        raise ValueError("model weight checksum does not match the pinned digest.")
    labels = bioclip_adapter._read_labels(labels_path)

    # This command must be unable to turn a cache-preparation request into a
    # model/tokenizer download. The local adapter receives only these artifacts.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    try:
        import numpy
        import open_clip
        import torch
    except ImportError as error:
        raise RuntimeError(
            "Install the optional classifier-bioclip desktop dependency first."
        ) from error

    open_clip_version = bioclip_adapter._installed_open_clip_distribution_version()
    if open_clip_version is None or not bioclip_adapter._supports_open_clip_version(open_clip_version):
        raise RuntimeError("The cache builder requires OpenCLIP 3.3.x.")

    model, _preprocess = open_clip.create_model_from_pretrained(
        f"local-dir:{model_dir}",
        device="cpu",
        return_transform=True,
    )
    model.eval()
    tokenizer = open_clip.get_tokenizer(f"local-dir:{model_dir}")
    templates = tuple(open_clip.OPENAI_IMAGENET_TEMPLATES)
    if len(templates) != 80:
        raise RuntimeError("The installed OpenCLIP ImageNet prompt recipe is unsupported.")

    embeddings: list[object] = []
    with torch.inference_mode():
        for label in labels:
            label_total = None
            for template in templates:
                prompt_embedding = model.encode_text(tokenizer([template(label)]))
                prompt_embedding = prompt_embedding / prompt_embedding.norm(
                    dim=-1,
                    keepdim=True,
                ).clamp_min(1e-12)
                label_total = (
                    prompt_embedding
                    if label_total is None
                    else label_total + prompt_embedding
                )
            if label_total is None:
                raise RuntimeError("The local BioCLIP prompt recipe was empty.")
            label_embedding = label_total.squeeze(0) / len(templates)
            label_embedding = label_embedding / label_embedding.norm().clamp_min(1e-12)
            embeddings.append(label_embedding.cpu().to(dtype=torch.float32).numpy())
            del prompt_embedding, label_total, label_embedding
            gc.collect()
    values = numpy.asarray(embeddings, dtype=numpy.float32)
    if values.shape != (len(labels), bioclip_adapter.BIOCLIP_EMBEDDING_DIMENSION):
        raise RuntimeError("BioCLIP produced an unexpected local text-embedding shape.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(
        f".{output_path.stem}.{uuid.uuid4().hex}.npz"
    )
    try:
        numpy.savez_compressed(
            temporary_path,
            embeddings=values,
            label_sha256=numpy.asarray(bioclip_adapter._label_sha256(labels)),
            model_config_sha256=numpy.asarray(_sha256(model_config_path)),
            model_weights_sha256=numpy.asarray(actual_weights_sha256),
            prompt_recipe_sha256=numpy.asarray(
                bioclip_adapter.BIOCLIP_PROMPT_RECIPE_SHA256
            ),
        )
        temporary_path.replace(output_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return {
        "label_count": len(labels),
        "labels_sha256": bioclip_adapter._label_sha256(labels),
        "model_weights_sha256": actual_weights_sha256,
        "embedding_cache_sha256": _sha256(output_path),
    }


def main() -> int:
    arguments = _arguments()
    try:
        report = _write_cache(
            model_dir=arguments.model_dir,
            labels_path=arguments.labels_path,
            output_path=arguments.embedding_cache_path,
            expected_weights_sha256=_normalized_digest(arguments.model_weights_sha256),
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"BioCLIP cache preparation failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
