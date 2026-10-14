"""Portfolio & Demo Release Closure v1: guards for `scripts/prepare_demo_instance.py`.

The demo path must stay honest -- it feeds public-domain footage through the
real pipeline, never fabricates evidence, never writes a review decision, and
never touches an instance that already holds a real camera.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prepare_demo_instance.py"
SPEC = importlib.util.spec_from_file_location("prepare_demo_instance", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


def test_manifest_clips_are_cc0_hash_pinned_and_importable() -> None:
    clips = demo.load_manifest()
    assert clips
    for clip in clips:
        assert clip["license"].startswith("CC0"), "demo media must be a public-domain dedication"
        assert re.fullmatch(r"[0-9a-f]{40}", clip["sha1"])
        assert clip["download_url"].startswith("https://upload.wikimedia.org/")
        assert clip["demo_filename"].endswith(".mp4"), "MockingBird imports mp4/mov"
        assert clip["author"]


def test_script_never_writes_review_truth_or_bundles_media() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "/api/review-labels" not in source
    assert "review_origin" not in source
    manifest_text = demo.MANIFEST_PATH.read_text(encoding="utf-8")
    json.loads(manifest_text)
    # Media lives under the git-ignored data/ tree, never in docs/.
    assert demo.DEFAULT_MEDIA_DIR.parts[-2:] == ("data", "demo-media")


class _FakeClient:
    def __init__(self, sources: list[dict]) -> None:
        self.sources = sources

    def call(self, method: str, path: str, payload=None, **_: object):
        assert (method, path) == ("GET", "/api/sources")
        return self.sources


def test_guard_refuses_an_instance_with_a_real_camera() -> None:
    client = _FakeClient([{"name": "Backyard feeder cam", "kind": "rtsp", "id": "source-1"}])
    with pytest.raises(demo.DemoPrepError, match="non-demo camera"):
        demo.assert_instance_is_disposable(client)


def test_guard_allows_fresh_and_already_prepared_demo_instances() -> None:
    assert demo.assert_instance_is_disposable(_FakeClient([])) is None
    seeded = {"name": "Backyard demo source", "kind": "demo", "id": "source-backyard-demo"}
    prepared = {"name": demo.DEMO_CAMERA_NAME, "kind": "local_camera", "id": "source-x"}
    assert demo.assert_instance_is_disposable(_FakeClient([seeded, prepared])) == prepared
