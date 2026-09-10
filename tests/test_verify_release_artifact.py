"""Release Engineering Foundation v1: focused coverage for
scripts/verify_release_artifact.py -- the independent post-build smoke
verifier CI runs against every packaging-smoke build (see
.github/workflows/ci.yml). Each test builds a small synthetic manifest.json/
SHA256SUMS/artifact fixture by hand rather than invoking the real (slow,
network-dependent) build_local_product.py -- this file exists to prove the
*verifier's own logic* catches each failure class, independent of whether a
real build happens to be healthy right now."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verify_release_artifact import (
    ReleaseArtifactVerificationError,
    verify_release_artifact,
)

ROOT = Path(__file__).resolve().parents[1]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_valid_artifact(
    output_dir: Path,
    *,
    zip_contents: bytes = b"fake zip bytes",
    source_clean: bool | None = True,
    source_state: str = "git:" + "a" * 40,
    build_identity_present: bool = True,
    sbom_contents: bytes | None = b'{"bomFormat": "CycloneDX", "components": []}',
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "MockingBird-windows-x64.zip"
    zip_path.write_bytes(zip_contents)
    zip_sha256 = _sha256_bytes(zip_contents)

    sbom_sha256 = None
    if sbom_contents is not None:
        sbom_path = output_dir / "sbom.json"
        sbom_path.write_bytes(sbom_contents)
        sbom_sha256 = _sha256_bytes(sbom_contents)

    build_identity = (
        {
            "git_commit": "a" * 40,
            "build_id": "deadbeefcafef00d",
            "built_at": "2026-01-01T00:00:00+00:00",
            "app_version": "0.1.0",
            "source_clean": source_clean,
        }
        if build_identity_present
        else None
    )

    manifest = {
        "artifact": zip_path.name,
        "package": "mockingbird-local-product-windows-x64",
        "version": "0.1.0",
        "source_state": source_state,
        "frontend_source_state": "built",
        "embedded_python_version": "3.12.7",
        "runtime_requirements": [],
        "gpu_runtime_included": False,
        "gpu_runtime_requirements": [],
        "observation_model_bundle": {"included": False, "reason": "not_evaluated"},
        "native_cuda_runtime": {"checked": False, "reason": "not_evaluated"},
        "bioclip_runtime_included": False,
        "bioclip_runtime_requirements": [],
        "bioclip_model_bundle": {"included": False, "reason": "not_evaluated"},
        "build_identity": build_identity,
        "sbom": (
            {"format": "CycloneDX", "spec_version": "1.5", "file": "sbom.json", "component_count": 0, "sha256": sbom_sha256}
            if sbom_sha256 is not None
            else {"format": "CycloneDX", "spec_version": "1.5", "file": "", "component_count": 0, "sha256": ""}
        ),
        "signing": {"requested": False, "key_id": None},
        "bundle_file_count": 3,
        "bundle_total_bytes": 12345,
        "zip_sha256": zip_sha256,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checksums_lines = f"{zip_sha256}  {zip_path.name}\n{_sha256_bytes(manifest_path.read_bytes())}  {manifest_path.name}\n"
    if sbom_sha256 is not None:
        checksums_lines += f"{sbom_sha256}  sbom.json\n"
    checksums_path = output_dir / "SHA256SUMS"
    checksums_path.write_text(
        checksums_lines,
        encoding="utf-8",
    )


def test_a_genuinely_valid_artifact_passes(tmp_path: Path, capsys) -> None:
    _write_valid_artifact(tmp_path)

    verify_release_artifact(tmp_path)

    assert "OK:" in capsys.readouterr().out


def test_missing_manifest_is_rejected(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    with pytest.raises(ReleaseArtifactVerificationError, match="manifest.json not found"):
        verify_release_artifact(tmp_path)


def test_missing_checksums_file_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    (tmp_path / "SHA256SUMS").unlink()

    with pytest.raises(ReleaseArtifactVerificationError, match="SHA256SUMS not found"):
        verify_release_artifact(tmp_path)


def test_manifest_missing_a_required_field_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    del manifest["zip_sha256"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ReleaseArtifactVerificationError, match="missing required field"):
        verify_release_artifact(tmp_path)


def test_referenced_artifact_file_missing_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    (tmp_path / "MockingBird-windows-x64.zip").unlink()

    with pytest.raises(ReleaseArtifactVerificationError, match="does not exist"):
        verify_release_artifact(tmp_path)


def test_tampered_artifact_bytes_fail_the_zip_sha256_check(tmp_path: Path) -> None:
    """The exact real-world case this verifier exists to catch: a manifest
    that claims one hash while the actual bytes on disk are different --
    whether from corruption in transit or a build/write-ordering bug."""

    _write_valid_artifact(tmp_path)
    zip_path = tmp_path / "MockingBird-windows-x64.zip"
    zip_path.write_bytes(b"these bytes were tampered with after the manifest was written")

    with pytest.raises(ReleaseArtifactVerificationError, match="zip_sha256 mismatch"):
        verify_release_artifact(tmp_path)


def test_checksums_entry_mismatch_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    checksums_path = tmp_path / "SHA256SUMS"
    checksums_path.write_text(
        checksums_path.read_text(encoding="utf-8").replace(
            _sha256_bytes((tmp_path / "MockingBird-windows-x64.zip").read_bytes()), "f" * 64
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReleaseArtifactVerificationError, match="does not match its actual contents"):
        verify_release_artifact(tmp_path)


def test_tampered_sbom_bytes_are_rejected(tmp_path: Path) -> None:
    """SHA256SUMS' own entry-by-entry check must cover every listed file --
    not only the always-present zip/manifest pair -- so a tampered sbom.json
    is caught the same way a tampered zip already is."""

    _write_valid_artifact(tmp_path)
    (tmp_path / "sbom.json").write_bytes(b"tampered sbom contents")

    with pytest.raises(ReleaseArtifactVerificationError, match="does not match its actual contents"):
        verify_release_artifact(tmp_path)


def test_sbom_listed_in_checksums_but_missing_from_disk_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    (tmp_path / "sbom.json").unlink()

    with pytest.raises(ReleaseArtifactVerificationError, match="does not exist"):
        verify_release_artifact(tmp_path)


def test_missing_build_identity_is_rejected_by_default(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path, build_identity_present=False)

    with pytest.raises(ReleaseArtifactVerificationError, match="build_identity is missing"):
        verify_release_artifact(tmp_path)


def test_dirty_source_build_is_rejected_by_default(tmp_path: Path) -> None:
    _write_valid_artifact(
        tmp_path, source_clean=False, source_state="dirty:unverified-working-tree"
    )

    with pytest.raises(ReleaseArtifactVerificationError, match="source_clean is not true"):
        verify_release_artifact(tmp_path)


def test_dirty_source_build_is_accepted_with_explicit_allow_flag(tmp_path: Path, capsys) -> None:
    _write_valid_artifact(
        tmp_path, source_clean=False, source_state="dirty:unverified-working-tree"
    )

    verify_release_artifact(tmp_path, allow_dirty_source=True)

    assert "OK:" in capsys.readouterr().out


def test_non_git_prefixed_source_state_is_rejected_even_with_clean_flag(tmp_path: Path) -> None:
    """`source_clean=True` with a `source_state` that is not `git:<hash>`
    would be an internally inconsistent manifest -- never trust one signal
    alone."""

    _write_valid_artifact(tmp_path, source_clean=True, source_state="test-fixture-state")

    with pytest.raises(ReleaseArtifactVerificationError, match="not a verified git commit"):
        verify_release_artifact(tmp_path)


def test_cli_exits_zero_on_a_valid_artifact_and_nonzero_on_a_tampered_one(tmp_path: Path) -> None:
    """The exact invocation .github/workflows/ci.yml's packaging-smoke job
    runs -- proves the argparse/exit-code wiring works, not only the
    underlying function pytest calls directly everywhere else in this
    file."""

    _write_valid_artifact(tmp_path)

    clean = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_release_artifact.py"), str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert clean.returncode == 0
    assert "OK:" in clean.stdout

    (tmp_path / "MockingBird-windows-x64.zip").write_bytes(b"tampered after packaging")

    tampered = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_release_artifact.py"), str(tmp_path)],
        capture_output=True, text=True, check=False,
    )
    assert tampered.returncode != 0
    assert "FAILED:" in tampered.stderr


def test_empty_bundle_is_rejected(tmp_path: Path) -> None:
    _write_valid_artifact(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["bundle_file_count"] = 0
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    checksums_path = tmp_path / "SHA256SUMS"
    checksums_path.write_text(
        f"{_sha256_bytes((tmp_path / 'MockingBird-windows-x64.zip').read_bytes())}  MockingBird-windows-x64.zip\n"
        f"{_sha256_bytes(manifest_path.read_bytes())}  manifest.json\n",
        encoding="utf-8",
    )

    with pytest.raises(ReleaseArtifactVerificationError, match="bundle_file_count"):
        verify_release_artifact(tmp_path)
