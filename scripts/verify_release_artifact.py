#!/usr/bin/env python3
"""Independent post-build smoke verification for a MockingBird release
artifact -- Release Engineering Foundation v1.

Reads `manifest.json`/`SHA256SUMS` produced by `scripts/build_local_product.py`
and re-derives every checkable fact from the actual files on disk, trusting
nothing the manifest merely claims about itself. Deliberately does not
import `build_local_product.py`: a bug in the builder's own hashing/writing
logic should not also be invisible to its own independent verifier.

Checks: manifest schema completeness; the referenced artifact file exists
and is non-empty; the recorded `zip_sha256` matches the artifact's actual
bytes; every `SHA256SUMS` entry matches its actual file's bytes; and (unless
`--allow-dirty-source` explicitly accepts it, for local iteration only) that
this artifact was built from a verified-clean git commit, never an
unverified working tree -- see docs/local-product-packaging-design.md
"Release-build source integrity".

Usage:
    python scripts/verify_release_artifact.py <output_dir>
    python scripts/verify_release_artifact.py <output_dir> --allow-dirty-source

Exit code 0 on a fully verified artifact; non-zero with a specific message
identifying the first failure otherwise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REQUIRED_MANIFEST_FIELDS = (
    "artifact",
    "package",
    "version",
    "source_state",
    "frontend_source_state",
    "embedded_python_version",
    "runtime_requirements",
    "gpu_runtime_included",
    "gpu_runtime_requirements",
    "observation_model_bundle",
    "native_cuda_runtime",
    "bioclip_runtime_included",
    "bioclip_runtime_requirements",
    "bioclip_model_bundle",
    "build_identity",
    "bundle_file_count",
    "bundle_total_bytes",
    "zip_sha256",
)


class ReleaseArtifactVerificationError(RuntimeError):
    """A release artifact failed independent post-build verification."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_checksums(checksums_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in checksums_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator:
            raise ReleaseArtifactVerificationError(
                f"SHA256SUMS line does not match the expected 'HASH<two spaces>name' format: {line!r}"
            )
        entries[name] = digest
    return entries


def verify_release_artifact(output_dir: Path, *, allow_dirty_source: bool = False) -> None:
    manifest_path = output_dir / "manifest.json"
    checksums_path = output_dir / "SHA256SUMS"
    if not manifest_path.is_file():
        raise ReleaseArtifactVerificationError(f"manifest.json not found at {manifest_path}")
    if not checksums_path.is_file():
        raise ReleaseArtifactVerificationError(f"SHA256SUMS not found at {checksums_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    missing_fields = [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
    if missing_fields:
        raise ReleaseArtifactVerificationError(
            f"manifest.json is missing required field(s): {missing_fields}"
        )

    zip_path = output_dir / manifest["artifact"]
    if not zip_path.is_file():
        raise ReleaseArtifactVerificationError(
            f"manifest.json references artifact {manifest['artifact']!r}, which does not exist "
            f"at {zip_path}"
        )

    if not isinstance(manifest["bundle_file_count"], int) or manifest["bundle_file_count"] <= 0:
        raise ReleaseArtifactVerificationError(
            f"bundle_file_count ({manifest['bundle_file_count']!r}) is not a positive integer -- "
            "an empty or malformed bundle"
        )
    if not isinstance(manifest["bundle_total_bytes"], int) or manifest["bundle_total_bytes"] <= 0:
        raise ReleaseArtifactVerificationError(
            f"bundle_total_bytes ({manifest['bundle_total_bytes']!r}) is not a positive integer -- "
            "an empty or malformed bundle"
        )

    actual_zip_sha256 = _sha256(zip_path)
    if actual_zip_sha256 != manifest["zip_sha256"]:
        raise ReleaseArtifactVerificationError(
            f"zip_sha256 mismatch for {zip_path.name}: manifest.json claims "
            f"{manifest['zip_sha256']}, the actual file hashes to {actual_zip_sha256}"
        )

    checksums = _parse_checksums(checksums_path)
    for path in (zip_path, manifest_path):
        recorded = checksums.get(path.name)
        if recorded is None:
            raise ReleaseArtifactVerificationError(f"SHA256SUMS has no entry for {path.name}")
        actual = _sha256(path)
        if recorded != actual:
            raise ReleaseArtifactVerificationError(
                f"SHA256SUMS entry for {path.name} does not match its actual contents "
                f"(recorded {recorded}, actual {actual})"
            )

    if not allow_dirty_source:
        build_identity = manifest["build_identity"]
        if build_identity is None:
            raise ReleaseArtifactVerificationError(
                "build_identity is missing -- a release artifact must record verified git "
                "provenance (pass --allow-dirty-source only to accept a deliberately "
                "unverified local build; never for a public release)"
            )
        if build_identity.get("source_clean") is not True:
            raise ReleaseArtifactVerificationError(
                "build_identity.source_clean is not true -- this artifact was built from an "
                "unverified or dirty source tree (pass --allow-dirty-source to accept this "
                "deliberately for a local build; never for a public release)"
            )
        if not str(manifest["source_state"]).startswith("git:"):
            raise ReleaseArtifactVerificationError(
                f"source_state {manifest['source_state']!r} is not a verified git commit "
                "(expected a 'git:<hash>' prefix)"
            )

    print(
        f"OK: {zip_path.name} ({manifest['bundle_file_count']} files, "
        f"{manifest['bundle_total_bytes']:,} bytes), version {manifest['version']}, "
        f"source {manifest['source_state']}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "output_dir", type=Path, help="directory containing manifest.json and SHA256SUMS"
    )
    parser.add_argument(
        "--allow-dirty-source",
        action="store_true",
        help=(
            "accept an artifact built from a dirty/unverified source tree "
            "(--allow-dirty-source at build time) -- local iteration only, never for a "
            "release artifact"
        ),
    )
    arguments = parser.parse_args()
    try:
        verify_release_artifact(arguments.output_dir, allow_dirty_source=arguments.allow_dirty_source)
    except ReleaseArtifactVerificationError as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
