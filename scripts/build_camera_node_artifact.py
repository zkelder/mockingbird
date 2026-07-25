"""Build a deterministic, slim Camera Node wheel without the main application."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parents[1]
NODE_PACKAGE = ROOT / "src" / "mockingbird_node"
NODE_FILES = ("__init__.py", "__main__.py", "app.py", "config.py", "providers.py")
RUNTIME_REQUIREMENTS = (
    "fastapi>=0.111,<0.116",
    "pydantic>=2.7,<3.0",
    "uvicorn[standard]>=0.30,<1.0",
)


@dataclass(frozen=True)
class CameraNodeArtifact:
    wheel: Path
    requirements: Path
    configuration_example: Path
    manifest: Path
    checksums: Path


def _source_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_digest(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
    return f"sha256={digest}"


def _write_zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 1, 1, 0, 0, 0)
    info.external_attr = 0o644 << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def _metadata(version: str) -> bytes:
    lines = [
        "Metadata-Version: 2.3",
        "Name: mockingbird-camera-node",
        f"Version: {version}",
        "Summary: Local-only bounded MockingBird Camera Node.",
        "Requires-Python: >=3.11",
        *(f"Requires-Dist: {requirement}" for requirement in RUNTIME_REQUIREMENTS),
        "",
    ]
    return "\n".join(lines).encode()


def _configuration_example() -> bytes:
    return b"""# Local-only MockingBird Camera Node configuration\nMOCKINGBIRD_NODE_NAME=Pi Camera Node\nMOCKINGBIRD_NODE_BIND=0.0.0.0\nMOCKINGBIRD_NODE_PORT=8787\nMOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2\nMOCKINGBIRD_NODE_MAX_IMAGE_BYTES=1500000\nMOCKINGBIRD_NODE_MAX_IMAGE_WIDTH=1920\nMOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT=1080\nMOCKINGBIRD_NODE_PAIRING_TTL_SECONDS=600\nMOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS=2\n# Synthetic is intentionally omitted: it is test-only.\n"""


def build_camera_node_artifact(output_dir: Path) -> CameraNodeArtifact:
    """Write a standalone wheel and deployment metadata with no application files."""

    version = _source_version()
    normalized_name = "mockingbird_camera_node"
    distribution = f"{normalized_name}-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)

    files = {f"mockingbird_node/{name}": (NODE_PACKAGE / name).read_bytes() for name in NODE_FILES}
    dist_info = f"{distribution}.dist-info"
    files[f"{dist_info}/METADATA"] = _metadata(version)
    files[f"{dist_info}/WHEEL"] = b"Wheel-Version: 1.0\nGenerator: MockingBird Camera Node artifact builder\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    files[f"{dist_info}/entry_points.txt"] = b"[console_scripts]\nmockingbird-camera-node = mockingbird_node.__main__:main\n"

    wheel = output_dir / f"{distribution}-py3-none-any.whl"
    records = [f"{name},{_record_digest(data)},{len(data)}" for name, data in sorted(files.items())]
    files[f"{dist_info}/RECORD"] = ("\n".join(records + [f"{dist_info}/RECORD,,"]) + "\n").encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in sorted(files.items()):
            _write_zip_entry(archive, name, data)

    requirements = output_dir / "requirements.txt"
    requirements.write_text("\n".join(RUNTIME_REQUIREMENTS) + "\n", encoding="utf-8")
    configuration_example = output_dir / "camera-node.env.example"
    configuration_example.write_bytes(_configuration_example())
    manifest = output_dir / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "artifact": wheel.name,
                "package": "mockingbird-camera-node",
                "version": version,
                "runtime_requirements": list(RUNTIME_REQUIREMENTS),
                "wheel_contents": [
                    {"path": name, "sha256": _sha256(data), "size": len(data)}
                    for name, data in sorted(files.items())
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    checksums = output_dir / "SHA256SUMS"
    checksum_files = (wheel, requirements, configuration_example, manifest)
    checksums.write_text(
        "".join(f"{_sha256(path.read_bytes())}  {path.name}\n" for path in checksum_files),
        encoding="utf-8",
    )
    return CameraNodeArtifact(wheel, requirements, configuration_example, manifest, checksums)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    arguments = parser.parse_args()
    artifact = build_camera_node_artifact(arguments.output_dir)
    print(artifact.wheel)


if __name__ == "__main__":
    main()
