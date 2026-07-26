import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD_ARTIFACT = runpy.run_path(ROOT / "scripts" / "build_camera_node_artifact.py")["build_camera_node_artifact"]


def test_camera_node_artifact_is_slim_and_launcher_checks_without_starting(tmp_path) -> None:
    artifact = BUILD_ARTIFACT(tmp_path / "artifact")
    with zipfile.ZipFile(artifact.wheel) as wheel:
        names = set(wheel.namelist())
        assert {"mockingbird_node/__init__.py", "mockingbird_node/__main__.py", "mockingbird_node/app.py", "mockingbird_node/config.py", "mockingbird_node/providers.py"} <= names
        assert not any(name.startswith(prefix) for name in names for prefix in ("mockingbird/", "web/", "tests/", "data/"))
        assert not any("sqlalchemy" in wheel.read(name).decode("utf-8", errors="ignore").lower() for name in names)

    manifest = json.loads(artifact.manifest.read_text(encoding="utf-8"))
    assert manifest["artifact"] == artifact.wheel.name
    assert manifest["source_state"] == "unspecified"
    assert manifest["runtime_requirements"] == [
        "fastapi>=0.111,<0.116",
        "pydantic>=2.7,<3.0",
        "uvicorn[standard]>=0.30,<1.0",
    ]
    assert "MOCKINGBIRD_NODE_PROVIDERS=picamera2,v4l2" in artifact.configuration_example.read_text(encoding="utf-8")
    assert "synthetic" not in artifact.requirements.read_text(encoding="utf-8")

    environment_root = tmp_path / "node-environment"
    venv.EnvBuilder(with_pip=True).create(environment_root)
    python = environment_root / "bin" / "python"
    install_result = subprocess.run(
        [python, "-m", "pip", "install", "--no-deps", artifact.wheel],
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0, install_result.stderr
    environment = {**os.environ, "PYTHONNOUSERSITE": "1"}
    help_result = subprocess.run(
        [python, "-m", "mockingbird_node", "--help"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert help_result.returncode == 0
    assert "local-only MockingBird Camera Node" in help_result.stdout
    check_result = subprocess.run(
        [python, "-m", "mockingbird_node", "--check"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert check_result.returncode == 0
    assert "configuration is valid" in check_result.stdout
    picamera2_result = subprocess.run(
        [python, "-c", "from mockingbird_node.config import CameraNodeConfig; from mockingbird_node.providers import PiCamera2Provider; print(PiCamera2Provider(CameraNodeConfig.from_environment()).cameras()[0].status)"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert picamera2_result.returncode == 0, picamera2_result.stderr
    assert picamera2_result.stdout.strip() == "setup_required"
